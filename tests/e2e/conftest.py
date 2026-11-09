"""Browser journeys for Pass 1 (2026-11-09): the real server in a subprocess, a real Chromium driven by Playwright.

What is real: the app, its routes, its database (a fresh one per run), the browser, the clicks. What is not:
* Anthropic is tests/support/anthropic_stub.py on a local port, which records every request (ANTHROPIC_BASE_URL).
* Every other outbound host (Yahoo, Tradier, EDGAR, FRED, the feeds) is pinned to the closed port 127.0.0.1:9
  through the proxy variables, so the server cannot reach a real provider; its panels answer as an outage would.
* The handful of symbol and quote answers the stock page needs are served to the page from fixtures in
  tests/e2e/fixtures.py (invented values, labelled as such), at the page's own API boundary.
Every credential variable the app reads is assigned, empty or fake, before the server starts, so neither a
developer's shell nor a .env file can point a run at a real host or account.

Run: `python -m pytest tests/e2e -q` (Chromium from `python -m playwright install chromium`). Skipped, with the
reason, where Playwright or its browser is not installed; CI installs both and runs them.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests.support.anthropic_stub import AnthropicStub

ROOT = Path(__file__).resolve().parents[2]
CLOSED = "http://127.0.0.1:9"
PASSWORD = "tungsten-carbide-9"   # a test account's, made by the run itself

pw = pytest.importorskip("playwright.sync_api", reason="Playwright is not installed (requirements-dev.txt)")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _example_keys():
    keys = set()
    for line in (ROOT / ".env.example").read_text().splitlines():
        m = re.match(r"^\s*([A-Z][A-Z0-9_]+)=", line)
        if m:
            keys.add(m.group(1))
    return keys


@pytest.fixture(scope="session")
def stub():
    s = AnthropicStub().start()
    yield s
    s.stop()


@pytest.fixture
def server(stub, tmp_path_factory):
    """A server per journey. One server for the whole run built a queue: every Home load asks the market feeds, which
    are refused at the closed port but are read one at a time behind the provider lock (app/providers/yf.py), and by
    the twentieth journey a page waited behind the earlier ones' refusals. Measured: 9 of 28 journeys timed out on a
    shared server, none on their own."""
    data = tmp_path_factory.mktemp("optic-e2e-data")
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.upper().endswith(("_KEY", "_TOKEN", "_SECRET")) and not k.startswith(("ANTHROPIC", "OPTIC_", "STRIPE", "SNAPTRADE", "TRADIER"))}
    # every credential the app reads is assigned empty, so a .env file cannot fill it (an existing variable wins over
    # the file, app/main.py _load_dotenv); the other settings are left unset, so their defaults apply
    for k in _example_keys():
        if re.search(r"(KEY|TOKEN|SECRET|PASSWORD|EMAILS|SMTP_HOST|SMTP_USERNAME|WEBHOOK|CLIENT_ID|_DSN)", k):
            env[k] = ""
        else:
            env.pop(k, None)
    env.update({
        "TRACKER_DATA_DIR": str(data), "ACCOUNTS_DB_PATH": str(data / "accounts.db"),
        "ANTHROPIC_BASE_URL": stub.url, "ANTHROPIC_API_KEY": "test-key-not-real", "ANTHROPIC_AUTH_TOKEN": "",
        "ANTHROPIC_MAX_RETRIES": "0", "ANTHROPIC_TIMEOUT_SECONDS": "3",
        "HTTP_PROXY": CLOSED, "HTTPS_PROXY": CLOSED, "http_proxy": CLOSED, "https_proxy": CLOSED, "ALL_PROXY": CLOSED,
        "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
        "APP_URL": "http://127.0.0.1:{}".format(port), "OPTIC_OVERNIGHT_FEED": "off", "PYTHONUNBUFFERED": "1",
    })
    log = open(data / "server.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    base = "http://127.0.0.1:{}".format(port)
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=2) as r:
                if r.status == 200:
                    break
        except Exception:                                         # noqa: BLE001 - not up yet
            time.sleep(0.3)
    else:
        proc.kill()
        raise RuntimeError("the server did not start; see " + str(data / "server.log"))
    yield {"base": base, "data": data, "db": data / "accounts.db", "proc": proc}
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()


@pytest.fixture(scope="session")
def chrome():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:                                  # noqa: BLE001
            pytest.skip("Chromium for Playwright is not installed: {}".format(str(exc).splitlines()[0]))
        yield b
        b.close()


# ------------------------------------------------------------------ accounts, seeded through the API and the database

_seq = [0]


def make_account(server, verified=True):
    """A fresh account with a unique address, registered through the API; its cookies for a browser context."""
    _seq[0] += 1
    email = "reader{}-{}@example.com".format(_seq[0], int(time.time() * 1000) % 10 ** 9)
    body = json.dumps({"first_name": "Test", "last_name": "Reader", "email": email,
                       "password": PASSWORD, "confirm_password": PASSWORD}).encode()
    # each account from its own documentation address (RFC 5737), so the sign-up limit per address is not what is tested
    req = urllib.request.Request(server["base"] + "/api/auth/register", data=body,
                                 headers={"Content-Type": "application/json", "X-Forwarded-For": "198.51.100.{}".format(_seq[0] % 250 + 1)})
    with urllib.request.urlopen(req, timeout=15) as r:
        cookies = r.headers.get_all("Set-Cookie") or []
    if verified:
        with sqlite3.connect(str(server["db"])) as c:
            c.execute("UPDATE users SET email_verified = 1 WHERE email = ?", (email,))
    jar = []
    for raw in cookies:
        name, _, rest = raw.partition("=")
        value = rest.split(";", 1)[0]
        jar.append({"name": name.strip(), "value": value, "url": server["base"]})
    return email, jar


def usage_rows(server, event=None):
    with sqlite3.connect(str(server["db"])) as c:
        c.row_factory = sqlite3.Row
        sql = "SELECT * FROM usage_event" + (" WHERE event = ?" if event else "") + " ORDER BY id"
        return [dict(r) for r in c.execute(sql, (event,) if event else ())]
