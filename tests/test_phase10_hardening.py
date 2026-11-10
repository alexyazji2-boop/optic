"""Phase 10 (post-demo overhaul, 2026-10-30): performance, security, accessibility and resilience fixes, pinned.

Each test names the defect it closes (docs/post-demo-ultra/BUG_REGISTER.md).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "static" / "v2" / "js"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_try_again_wires_a_page_once():
    """BUG-037: Try again drew Scan, Read and Indices into the same view and attached every listener again."""
    for rel in ("static/v2/js/pages/scan.js", "static/v2/js/pages/read.js"):
        src = read(rel)
        body = src[src.index("function wire(main) {"):][:400]
        assert "if (main.__v2Wired) return;" in body and "main.__v2Wired = true;" in body, rel
    ind = read("static/v2/js/pages/indices.js")
    assert "if (!main.__v2Wired) main.addEventListener('click'" in ind and "main.__v2Wired = true;" in ind


def test_the_app_level_try_again_retries():
    """BUG-046: both cards were links to the address already open, so pressing them did nothing."""
    src = read("static/v2/js/app.js")
    assert not re.search(r"<a class=\"btn\" href=\"\$\{hrefFor\(route\.view, route\.symbol\)\}\">Try again</a>", src)
    assert 'data-v2-reload>Try again</button>' in src and 'data-v2-retry="page">Try again</button>' in src
    assert "if (t('[data-v2-reload]')) { location.reload(); return; }" in src


def test_a_wrong_password_in_settings_says_so():
    """BUG-048: a signed-in reader's 401 on changing the password or deleting the account read "Sign in to see"."""
    src = read("static/v2/js/pages/settings.js")
    assert src.count("(err.status === 401 && store.signedIn())") == 2


# ------------------------------------------------------------------ security (SEC-xx: phase10/security review)

import logging

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import metrics as metrics_mod

CHAT = {"messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture
def stub_model(monkeypatch):
    async def fake_stream(*args, **kwargs):
        yield "data: stub\n\n"
    monkeypatch.setattr(main.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(main.ai, "deep_research", fake_stream)
    main._ai_calls.clear()
    yield
    main._ai_calls.clear()


def _member(email):
    c = TestClient(main.app)
    c.post("/api/auth/register", json={"first_name": "A", "email": email,
                                       "password": "tungsten-carbide-9", "confirm_password": "tungsten-carbide-9"})
    return c


def test_a_server_wide_ceiling_sits_over_every_account(accounts, stub_model, monkeypatch):
    """SEC-01: free, unverified accounts each brought a fresh allowance with nothing over them all."""
    monkeypatch.setattr(main, "MILO_QUESTIONS_PER_DAY", 2)
    head = {"x-forwarded-for": "203.0.113.70"}
    first, second, third = (_member("ceiling{}@example.com".format(i)) for i in range(3))
    assert first.post("/api/chat", json=CHAT, headers=head).status_code == 200
    assert second.post("/api/chat", json=CHAT, headers=head).status_code == 200
    refused = third.post("/api/chat", json=CHAT, headers=head)
    assert refused.status_code == 429 and "as this server allows" in refused.json()["detail"]
    # refused before the reader's own allowance was charged
    assert third.get("/api/ai-allowance").json()["allowance"]["used"] == 0
    assert third.post("/api/research", json={"ticker": "SPY"}, headers=head).status_code == 429


def test_the_owners_questions_do_not_count_toward_the_ceiling(accounts, monkeypatch):
    from app import db
    monkeypatch.setenv("ADMIN_EMAILS", "owner@example.com")
    db.execute("INSERT INTO users (id, email, first_name, created_at, updated_at) VALUES "
               "('u-owner', 'Owner@example.com', 'O', ?, ?)", (db.utcnow(), db.utcnow()))
    for uid in ("u-owner", "u-owner", None):
        metrics_mod.note_question(uid, "chat")
    assert metrics_mod.questions_since("2000-01-01T00:00:00Z") == 1
    assert metrics_mod.questions_since("2999-01-01T00:00:00Z") == 0


def test_zero_switches_the_ceiling_off(accounts, stub_model, monkeypatch):
    monkeypatch.setattr(main, "MILO_QUESTIONS_PER_DAY", 0)
    monkeypatch.setattr(metrics_mod, "questions_since", lambda since: 10 ** 6)
    who = _member("ceiling-off@example.com")
    assert who.post("/api/chat", json=CHAT, headers={"x-forwarded-for": "203.0.113.71"}).status_code == 200


def test_a_long_question_is_refused_before_anything_is_charged(monkeypatch):
    """BUG-112: the newest turn was kept whole whatever its length."""
    def charged(request):
        raise AssertionError("the allowance was charged for a refused question")
    monkeypatch.setattr(main, "_spend_guard", charged)
    c = TestClient(main.app)
    long = "x" * (main.ai.QUESTION_MAX_CHARS + 1)
    r = c.post("/api/chat", json={"messages": [{"role": "user", "content": long}]})
    assert r.status_code == 413 and "characters" in r.json()["detail"]
    assert c.post("/api/research", json={"question": long}).status_code == 413
    assert main.ai.question_too_long("x" * main.ai.QUESTION_MAX_CHARS) is None


def test_a_body_over_the_limit_is_refused_before_a_handler_reads_it(monkeypatch):
    """SEC-03: no route capped a body, signed in or not."""
    monkeypatch.setattr(main, "BODY_MAX_BYTES", 4096)
    c = TestClient(main.app)
    big = b'{"email": "' + b"a" * 5000 + b'"}'
    r = c.post("/api/auth/login", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413 and "larger than this server accepts" in r.json()["detail"]
    assert r.headers.get("x-content-type-options") == "nosniff"      # inside the security headers

    def chunks():
        for _ in range(10):
            yield b"a" * 1000
    r = c.post("/api/auth/login", content=chunks(), headers={"content-type": "application/json"})
    assert r.status_code == 413
    small = c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert small.status_code != 413
    # the chat route has room for its attachments
    assert main._BodyLimit.limit("/api/chat") > main.ai.ATTACH_MAX_FILES * main.ai.ATTACH_MAX_BYTES


def test_a_chunked_body_under_the_limit_reaches_the_handler(monkeypatch):
    monkeypatch.setattr(main, "BODY_MAX_BYTES", 4096)
    c = TestClient(main.app)

    def chunks():
        yield b'{"email": "nobody@example.com", '
        yield b'"password": "x"}'
    r = c.post("/api/auth/login", content=chunks(), headers={"content-type": "application/json"})
    assert r.status_code in (400, 401, 429), r.status_code     # the login route's own answer, not 413 or 422


def test_one_time_tokens_are_kept_out_of_the_access_log():
    """SEC-02: uvicorn prints the request target, query string included."""
    rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                            ("1.2.3.4:5", "GET", "/api/auth/reset/check?token=abc123&x=1", "1.1", 200), None)
    assert main._RedactQuery().filter(rec)
    assert rec.args[2] == "/api/auth/reset/check?token=[redacted]&x=1"
    rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, "%s", ("plain",), None)
    assert main._RedactQuery().filter(rec) and rec.args == ("plain",)
    cb = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                           ("1.2.3.4:5", "GET", "/api/auth/google/callback?state=s1&code=c2", "1.1", 302), None)
    main._RedactQuery().filter(cb)
    assert "s1" not in cb.args[2] and "c2" not in cb.args[2]
    assert any(isinstance(f, main._RedactQuery) for f in logging.getLogger("uvicorn.access").filters)
    q = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                          ("1.2.3.4:5", "GET", "/api/search?q=my+holdings&limit=8", "1.1", 200), None)
    main._RedactQuery().filter(q)
    assert q.args[2] == "/api/search?q=[redacted]&limit=8"          # search text, the analytics review's quick fix


def test_a_non_ascii_token_is_a_refusal_not_a_server_error(monkeypatch):
    """SEC-11: compare_digest raises TypeError on two str with a non-ASCII character."""
    from app import billing
    monkeypatch.setattr(main, "WRITE_TOKEN", "right-token")
    c = TestClient(main.app, raise_server_exceptions=False)
    r = c.post("/api/tracker/mark", headers={"x-optic-token": "été".encode("latin-1")})
    assert r.status_code != 500, r.status_code
    import time as _t
    now = int(_t.time())
    assert billing.verify_signature(b"{}", "t={},v1=é".format(now), "whsec_test", now=now) is False


def test_a_line_break_in_an_address_is_refused_at_register(accounts):
    """SEC-12: the old test let a newline through; it became a 500 at the mail header after the row existed."""
    c = TestClient(main.app)
    r = c.post("/api/auth/register", json={"first_name": "A", "email": "a@example.com\nBcc: b@example.com",
                                          "password": "tungsten-carbide-9", "confirm_password": "tungsten-carbide-9"})
    assert r.status_code == 400 and "valid email" in r.json()["detail"]


def test_a_failed_send_logs_the_address_masked(monkeypatch):
    """SEC-17: every SMTP failure wrote the reader's full address to the log."""
    from app.auth import mailer
    seen = []

    class Grab(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())
    h = Grab()
    mailer.log.addHandler(h)
    try:
        monkeypatch.setattr(mailer, "available", lambda: {"available": True})
        def boom(message):
            raise OSError("relay down")
        monkeypatch.setattr(mailer, "_send_smtp", boom)
        assert mailer.send("reader@example.com", "Subject", "Body") is False
    finally:
        mailer.log.removeHandler(h)
    assert seen and "reader@example.com" not in seen[-1] and "r***@example.com" in seen[-1]


def test_the_search_ranking_is_unchanged_by_the_speedups():
    """BUG-053: the per-row work moved to once a directory, the answers kept for the day; the ranking must not move."""
    from app import universe
    idx = {"rows": [{"symbol": s, "name": n, "etf": e} for s, n, e in (
        ("T", "AT&T Inc", False), ("TSLA", "Tesla, Inc", False), ("TSLL", "Direxion Daily TSLA Bull 2X Shares", True),
        ("TESL", "Simplify Volt TSLA Revolution ETF", True), ("BRK.B", "Berkshire Hathaway Inc", False),
        ("GOOGL", "Alphabet Inc", False), ("AA", "Alcoa Corp", False), ("AAOI", "Applied Optoelectronics", False),
        ("ABCD", "Blank Check Acquisition Corp", False))]}
    assert universe.search("tsla", 1, _idx=idx)[0]["symbol"] == "TSLA"
    assert universe.search("brk b", 1, _idx=idx)[0]["symbol"] == "BRK-B"
    assert universe.search("google", 1, _idx=idx)[0]["symbol"] == "GOOGL"
    first = universe.search("aa", 5, _idx=idx)
    first[0]["symbol"] = "mutated"
    assert universe.search("aa", 5, _idx=idx)[0]["symbol"] == "AA"      # a caller's edit does not reach the memo
    assert universe.known_symbol is not None


def test_search_is_limited_per_address(monkeypatch):
    monkeypatch.setattr(main, "SEARCH_PER_MINUTE", 3)
    main._search_calls.clear()
    c = TestClient(main.app)
    head = {"x-forwarded-for": "203.0.113.90"}
    codes = [c.get("/api/search?q=a", headers=head).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
    assert c.get("/api/search?q=a", headers={"x-forwarded-for": "203.0.113.91"}).status_code == 200
    main._search_calls.clear()


def test_the_logo_route_takes_listed_symbols_on_its_own_pool(monkeypatch, tmp_path):
    """SEC-06: any made-up symbol wrote files that were never removed, on the shared pool, with no budget."""
    monkeypatch.setattr(main, "_LOGO_DIR", str(tmp_path))
    fetched = []
    monkeypatch.setattr(main, "_logo_fetch", lambda sym: fetched.append(sym) or (b"\x89PNG\r\n\x1a\nxx", "image/png"))
    monkeypatch.setattr(main.universe_mod, "known_symbol", lambda sym: sym == "AAPL")
    c = TestClient(main.app)
    assert c.get("/api/logo/ZZZZQ").status_code == 204 and not list(tmp_path.iterdir())
    assert c.get("/api/logo/AAPL%0A").status_code == 204          # fullmatch: no second key with a newline
    assert c.get("/api/logo/AAPL").status_code == 200 and fetched == ["AAPL"]
    monkeypatch.setattr(main, "_LOGO_FETCHES_PER_HOUR", 0)
    monkeypatch.setattr(main.universe_mod, "known_symbol", lambda sym: True)
    r = c.get("/api/logo/MSFT")
    assert r.status_code == 204 and not (tmp_path / "MSFT.none").exists()   # over budget, not kept
    assert r.headers["cache-control"] == "no-store"      # nor kept by the browser for a day (BUG-184, Phase 11)
    monkeypatch.setattr(main.universe_mod, "known_symbol", lambda sym: sym == "AAPL")
    assert c.get("/api/logo/ZZZZQ").headers["cache-control"] == "public, max-age=86400"   # an unlisted symbol stays a kept miss


def test_the_client_address_comes_from_the_edge_not_the_first_hop(monkeypatch):
    """BUG-054: the first X-Forwarded-For hop is whatever the client wrote."""
    from starlette.requests import Request
    from app.auth import ratelimit

    def req(headers):
        return Request({"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
                        "client": ("10.0.0.1", 1)})
    monkeypatch.setattr(ratelimit, "CLIENT_IP_HEADER", "cf-connecting-ip")
    monkeypatch.setattr(ratelimit, "TRUSTED_PROXY_HOPS", 0)
    assert ratelimit.client_ip(req({"cf-connecting-ip": "198.51.100.7", "x-forwarded-for": "1.1.1.1"})) == "198.51.100.7"
    assert ratelimit.client_ip(req({"cf-connecting-ip": "not an address", "x-forwarded-for": "1.1.1.1"})) == "1.1.1.1"
    monkeypatch.setattr(ratelimit, "TRUSTED_PROXY_HOPS", 2)
    assert ratelimit.client_ip(req({"x-forwarded-for": "6.6.6.6, 198.51.100.8, 162.158.0.1"})) == "198.51.100.8"
    monkeypatch.setattr(ratelimit, "CLIENT_IP_HEADER", "")
    monkeypatch.setattr(ratelimit, "TRUSTED_PROXY_HOPS", 0)
    assert ratelimit.client_ip(req({})) == "10.0.0.1"


def test_a_session_ends_at_its_absolute_limit_however_much_it_is_used(accounts):
    """SEC-14: the expiry slid forward on every use with no end."""
    from app.auth import store
    who = _member("absolute@example.com")
    assert who.get("/api/auth/me").json()["authenticated"] is True
    accounts.execute("UPDATE sessions SET created_at = ?", (accounts.in_seconds(-91 * 86400),))
    assert who.get("/api/auth/me").json()["authenticated"] is False
    assert store.config.SESSION_MAX_DAYS == 90


def test_the_headers_switch_off_unused_browser_features():
    """SEC-09: no Permissions-Policy and no opener policy."""
    r = TestClient(main.app).get("/api/health")
    assert "camera=()" in r.headers["permissions-policy"] and "publickey" not in r.headers["permissions-policy"]
    assert r.headers["cross-origin-opener-policy"] == "same-origin-allow-popups"


def test_classic_puts_escaped_values_only_in_double_quoted_attributes():
    """SEC-15: Classic's esc leaves ' alone, so a value it escapes must never sit in a single-quoted attribute (the
    one that did, data-spark, is double-quoted now); and the release link takes the scheme check."""
    for rel in ("static/app.js", "static/auth.js"):
        assert not re.search(r"""[a-z-]+='\$\{""", read(rel)), rel
    src = read("static/app.js")
    assert '<span data-spark="${esc(JSON.stringify(r.series || []))}">' in src
    assert '<a href="${safeHref(res.headline_url)}"' in src


def test_exception_text_in_a_response_loses_hosts_urls_and_paths():
    """SEC-16: about thirty public answers carried str(exc), which can name an upstream host, a URL and its query,
    or a file on the server."""
    from app.public_errors import public
    raw = ("HTTPSConnectionPool(host='query2.finance.yahoo.com', port=443): Max retries exceeded with url: "
           "/v7/finance/quote?symbols=AAPL&crumb=abc (Caused by ...)")
    out = public(Exception(raw))
    assert "yahoo" not in out and "crumb" not in out and "Max retries exceeded" in out
    assert "/app/data" not in public(OSError("[Errno 2] No such file or directory: '/app/data/screen_ranking.json'"))
    assert "https://" not in public(ValueError("see https://example.com/x?token=1 for more"))
    # Optic's own sentences are left as written
    for own in ("needs a positive free cash flow", "P/E and EV/EBITDA need earnings", "1/2 of the inputs"):
        assert public(ValueError(own)) == own
    assert len(public(ValueError("x" * 500))) == 120
    import app.main as m
    src = Path(m.__file__).read_text()
    assert '"reason": str(exc)' not in src and "detail=str(exc)" not in src


def test_the_owners_unread_count_is_the_owners(monkeypatch):
    """BUG-072: the shared inbox's unread count (the owner's read state) went to every caller."""
    monkeypatch.setattr(main, "_is_owner", lambda request: False)
    assert TestClient(main.app).get("/api/alerts").json()["unseen"] is None
    monkeypatch.setattr(main, "_is_owner", lambda request: True)
    assert isinstance(TestClient(main.app).get("/api/alerts").json()["unseen"], int)


def test_watch_checks_are_limited_per_address(monkeypatch):
    """BUG-072: each check builds a 20-second snapshot, for anyone, unmetered."""
    monkeypatch.setattr(main, "WATCH_CHECKS_PER_10_MIN", 2)
    monkeypatch.setattr(main, "_is_owner", lambda request: False)
    monkeypatch.setattr(main, "_swing_snapshot", lambda *a, **k: {"quote": {"price": 1.0}})
    monkeypatch.setattr(main.YF_PROVIDER, "earnings_date", lambda t: None)
    main._watch_checks.clear()
    c = TestClient(main.app)
    head = {"x-forwarded-for": "203.0.113.95"}
    codes = [c.post("/api/watches/check", json={"ticker": "SPY", "watches": []}, headers=head).status_code
             for _ in range(3)]
    assert codes[:2] == [200, 200] and codes[2] == 429, codes
    main._watch_checks.clear()


def test_only_listed_names_join_the_post_close_reading(monkeypatch):
    """BUG-072: sixty invented symbols a call took places real names were waiting for."""
    noted = []
    monkeypatch.setattr(main.briefing_mod, "note_requested", lambda syms, when=None: noted.extend(syms))
    monkeypatch.setattr(main.universe_mod, "known_symbol", lambda s: s in ("AAPL", "MSFT"))
    monkeypatch.setattr(main, "_setup_frames", lambda syms, bench: {})
    monkeypatch.setattr(main.briefing_mod, "build", lambda symbols, held, b, s, per: {"unread": []})
    monkeypatch.setattr(main, "_BRIEFING_CACHE", {})
    TestClient(main.app).post("/api/briefing", json={"symbols": ["AAPL", "QQQQZ", "MSFT"]})
    assert noted == ["AAPL", "MSFT"]


def test_the_brokerage_controls_say_what_they_do():
    """BUG-074: Reconnect skipped the consent box, the armed buttons took a second press mid-request, and the delete
    sentence said everything went when the theses, alert settings and consent record stay."""
    src = read("static/v2/js/pages/brokerage.js")
    assert "data-v2-bk-reconnect=\"${c.id}\" ${needAgree ? 'disabled aria-disabled=\"true\"' : ''}" in src
    assert "(canAdd || conns.some((c) => RECONNECT.includes(c.status))) ? consent(" in src
    for handler in ("data-v2-bk-disconnect=\"${CSS.escape(S.armed)}\"]`); return; }\n      b.disabled = true;",
                    "paint('[data-v2-bk-delete=\"confirm\"]'); return; }\n      b.disabled = true;"):
        assert handler in src
    for app in (src, read("static/app.js")):
        assert "deletes everything Optic stored" not in app and "the record that you agreed to the linking terms" in app


def test_wrong_write_tokens_are_limited_per_address(monkeypatch):
    """BUG-030: a guess at the shared token had no cost."""
    monkeypatch.setattr(main, "WRITE_TOKEN", "right-token")
    monkeypatch.setattr(main, "TOKEN_MISSES_PER_HOUR", 2)
    main._token_misses.clear()
    c = TestClient(main.app)
    head = {"x-forwarded-for": "203.0.113.99", "x-optic-token": "wrong"}
    codes = [c.post("/api/alerts/clear", headers=head).status_code for _ in range(3)]
    assert codes[:2] == [401, 401] and codes[2] == 429, codes
    main._token_misses.clear()


# ------------------------------------------------------------------ performance

from app import feeds as _feeds_at_import

_REAL_FETCH = _feeds_at_import._fetch      # captured before conftest's _no_live_feeds swaps it out for each test

def test_the_adapter_cache_drops_what_can_never_be_served_again(monkeypatch):
    """S01: nothing ever left _CACHE, and the key space included caller-chosen strings."""
    from app.providers import yf
    monkeypatch.setattr(yf, "_CACHE", {})
    monkeypatch.setattr(yf, "_KEY_LOCKS", {})
    now = 1_000_000.0
    yf._CACHE.update({"old": (now - 90_000, 1), "fresh": (now - 10, 2), "day": (now - 80_000, 3)})
    yf._key_lock("old"); yf._key_lock("fresh")
    assert yf.sweep_cache(now) == 1
    assert set(yf._CACHE) == {"fresh", "day"} and "old" not in yf._KEY_LOCKS and "fresh" in yf._KEY_LOCKS
    monkeypatch.setattr(yf, "CACHE_MAX", 1)
    yf.sweep_cache(now)
    assert set(yf._CACHE) == {"fresh"}                  # the oldest stored goes first past the cap


def test_a_chart_period_comes_from_the_allowed_set(monkeypatch):
    """S01: `period` and `range` reached history() and the cache key as sent."""
    asked = []
    monkeypatch.setattr(main.YF_PROVIDER, "history", lambda *a, **k: asked.append(k.get("period")))
    c = TestClient(main.app)
    assert c.get("/api/trendlines/SPY?period=zz9").json()["available"] is False
    assert c.get("/api/indicators/SPY?ids=rsi&range=forever").json()["available"] is False
    assert asked == []
    assert {"1y", "2y", "10y", "max"} <= main._DAILY_PERIODS


def test_a_feed_host_that_just_failed_is_not_asked_again_at_once(monkeypatch):
    """S16: a dead host cost its whole timeout on every call."""
    import urllib.error
    import urllib.request
    from app import feeds
    monkeypatch.setattr(feeds, "_DOWN", {})
    monkeypatch.setattr(feeds, "POLITE_GAP_SECONDS", 0.0)
    calls = []

    def dead(req, timeout=None):
        calls.append(req.full_url)
        raise urllib.error.URLError("timed out")
    monkeypatch.setattr(urllib.request, "urlopen", dead)
    for _ in range(3):
        with pytest.raises(urllib.error.URLError):
            _REAL_FETCH("https://fred.example/series.csv", "text/csv")
    assert len(calls) == 1
    monkeypatch.setattr(feeds, "HOST_DOWN_SECONDS", 0.0)

    class Ok:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"ok"
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: Ok())
    assert _REAL_FETCH("https://fred.example/series.csv", "text/csv") == b"ok" and not feeds._DOWN

    def gone(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", gone)
    with pytest.raises(urllib.error.HTTPError):
        _REAL_FETCH("https://fred.example/missing.csv", "text/csv")
    assert not feeds._DOWN                               # one missing document is not the host down

    def busy(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", busy)
    with pytest.raises(urllib.error.HTTPError):
        _REAL_FETCH("https://sec.example/cgi-bin/browse-edgar?type=4", "application/atom+xml")
    assert not feeds._DOWN       # BUG-183 (Phase 11): one query's 503 held the other eleven forms back for a minute

    def refused(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", refused)
    with pytest.raises(urllib.error.HTTPError):
        _REAL_FETCH("https://sec.example/cgi-bin/browse-edgar?type=8-K", "application/atom+xml")
    assert "sec.example" in feeds._DOWN                  # a refusal is the caller's, so the host is left alone a while


def test_a_failed_directory_refresh_is_not_retried_on_every_search(monkeypatch):
    """S19: each search retried the download, holding the directory lock for its whole timeout."""
    from app import universe
    monkeypatch.setattr(universe, "_MEMO", {})
    tries = []
    monkeypatch.setattr(universe, "search_index", lambda force=False: tries.append(1) or {"rows": [], "error": "down"})
    for _ in range(5):
        assert universe._rows_today()["rows"] == []
    assert len(tries) == 1
    monkeypatch.setattr(universe, "REFRESH_RETRY_SECONDS", 0.0)
    universe._rows_today()
    assert len(tries) == 2


def test_the_questions_symbols_are_looked_up_off_the_event_loop(monkeypatch):
    """BUG-113: each capitalised word was a directory search run on the event loop, holding every other request."""
    import asyncio
    seen = []

    def search(token, limit=3):
        try:
            asyncio.get_running_loop()
            seen.append("loop")
        except RuntimeError:
            seen.append("thread")
        return [{"symbol": token}] if token == "NVDA" else []
    monkeypatch.setattr(main.universe_mod, "search", search)
    # only the page's own symbol is named, so nothing is fetched: the test is about where the lookup runs
    history = [{"role": "user", "content": "Is NVDA gamma positive TODAY"}]
    out = asyncio.run(main._augment_chat_context_lookups(history, {"focus": {"scope": "page"}, "ticker": "NVDA"}))
    assert seen and set(seen) == {"thread"}, seen
    assert out is not None


def test_the_earnings_week_says_it_is_building_instead_of_waiting_silently():
    """BUG-016: a cold build took over 30 s behind seven skeletons, with no word of why."""
    src = read("static/v2/js/pages/earningsweek.js")
    assert "&quick=1`" in src and "if (D.building) return html`<p class=\"asof\" role=\"status\">" in src
    assert "api.invalidate(url);" in src and "setTimeout(() => { if (live && my === seq) load(again + 1); }, BUILD_POLL_MS);" in src
    assert "aria-busy=\"${!D || D.building ? 'true' : 'false'}\"" in src


def test_the_calendar_and_info_are_read_once_for_their_readers(monkeypatch):
    """S09: the next report date and the consensus band read Yahoo's calendar separately, and the fund facts and the
    futures month each re-read `.info` beside the quote's own read."""
    import app.providers.yf as y
    from app.main import YF_PROVIDER as P
    monkeypatch.setattr(y, "_CACHE", {})
    monkeypatch.setattr(y, "_wait_turn", lambda: None)
    calls = {"calendar": 0}

    class Stub:
        def __init__(self, *a, **k):
            pass

        @property
        def calendar(self):
            calls["calendar"] += 1
            return {"Earnings Date": [pd.Timestamp("2026-11-19")], "Earnings Average": 1.1}
    import pandas as pd
    monkeypatch.setattr(y.yf, "Ticker", Stub)
    assert P.earnings_date("ZZCAL") == "2026-11-19"
    P.earnings_calendar("ZZCAL")
    assert calls["calendar"] == 1
    infos = []
    monkeypatch.setattr(type(P), "_info", lambda self, t: infos.append(t) or {"underlyingSymbol": "ZQV26.CBT", "category": "Large Blend",
                                                                             "annualReportExpenseRatio": 0.0009, "yield": 0.013})
    assert P.contract_month("ZQ=F") == "2026-10-01"
    assert P.fund_meta("ZZFUND")["category"] == "Large Blend"
    assert infos == ["ZQ=F", "ZZFUND"]


def test_a_paying_reader_is_neither_refused_nor_counted_by_the_ceiling(accounts, stub_model, monkeypatch):
    """The cost audit: the server-wide ceiling refused Pro readers too, and their questions used the free pool."""
    from app.auth import store as auth_store
    monkeypatch.setattr(main, "MILO_QUESTIONS_PER_DAY", 1)
    head = {"x-forwarded-for": "203.0.113.72"}
    pro = _member("paying@example.com")
    uid = accounts.rows("SELECT id FROM users WHERE email = ?", ("paying@example.com",))[0]["id"]
    auth_store.set_plan(uid, "pro")
    assert pro.post("/api/chat", json=CHAT, headers=head).status_code == 200
    assert pro.post("/api/chat", json=CHAT, headers=head).status_code == 200        # over the ceiling, not refused
    assert metrics_mod.questions_since("2000-01-01T00:00:00Z") == 0               # and not counted against it
    free = _member("free-reader@example.com")
    assert free.post("/api/chat", json=CHAT, headers=head).status_code == 200
    assert free.post("/api/chat", json=CHAT, headers=head).status_code == 429


def test_classic_asks_for_the_kept_catalyst_read_and_writes_only_on_request():
    """Cost audit C4: opening Classic's catalyst panel wrote a paid read whenever none was kept, against the owner's
    rule that reading a page costs nothing. v2 asked for the kept one; Classic now does too."""
    src = read("static/app.js")
    load = src[src.index("async function loadCatalystMode() {"):][:400]
    assert "getJSON('/api/catalyst-mode?cached=true')" in load
    assert "data-catread-write>Write the read</button>" in src and "read.on_request ?" in src
    assert src.count("getJSON('/api/catalyst-mode')") == 1          # the button's write, nothing else


def test_an_unreadable_answer_is_a_failure_not_an_empty_one():
    """Resilience check R8: a 200 whose body was not JSON resolved null, and the Dossier's handler read `d.quote` from
    it, threw, and left its skeletons running. It is now an error every page already shows with Try again."""
    src = read("static/v2/js/core/api.js")
    req = src[src.index("async function request("):][:2600]
    assert "catch (e) { data = null; unreadable = true; }" in req
    assert "if (unreadable) throw new ApiError('server', res.status," in req


def test_the_dossier_header_keeps_its_rows_while_the_quote_loads():
    """BUG-031: where the header wraps (to 1,100 px), the short loading placeholder fitted beside the ticker, so the
    name and price arriving added two rows and pushed the page down about 70 px. Measured after the fix with the quote
    held (tools/phase10_coldhead.py): 148 to 149 px at 1024, 158 to 159 px at 800."""
    css = read("static/v2/css/pages.css")
    # 1,199 px since the hierarchy review of 2026-11-10 (change 17): the price is 44px on the Overview now
    assert "@media (max-width: 1199px) { .dhead.bar .dh-price { flex-basis: 100%; } }" in css
    assert "@media (max-width: 1199px) { .dhead.bar.is-wide .dh-price { flex-basis: 100%; } }" in css
    assert "@media (min-width: 861px) and (max-width: 1199px) { .dhead.bar { flex-wrap: wrap; }" in css
    # the wide header's own rule comes first, so the row of its own wins over it
    assert css.index(".dhead.bar.is-wide .dh-price { flex: 0 1 auto; }") < css.index("{ .dhead.bar.is-wide .dh-price { flex-basis: 100%; } }")


def test_the_wide_insider_tables_scroll_on_a_phone_instead_of_squeezing():
    """BUG-014: squeezed to 358 px, the House trades' filing date and its note took 51 px and every row stood about
    200 px tall (224 at Large text). Measured after: 69 px (78 at Large text)."""
    js = read("static/v2/js/pages/insiders.js")
    assert js.count('<table class="t ins-scroll">') == 2
    css = read("static/v2/css/pages.css")
    block = css[css.index("@media (max-width: 640px) {\n  /* the House trades"):][:600]
    assert ".ins-scroll td { white-space: nowrap; }" in block
    assert ".pk-in small { color: var(--c-ink-3); font-weight: 400; font-size: var(--t-xs); }" in css


def test_settings_reduce_also_stops_smooth_scrolling():
    """BUG-177: the section and strip scrollers read only the system setting, so Settings' Motion: Reduce left smooth
    scrolling on."""
    for rel in ("static/v2/js/ui/sections.js", "static/v2/js/ui/strips.js"):
        src = read(rel)
        assert "import { reducedMotion } from '../core/dom.js';" in src, rel
        assert "const reduced = () => { try { return reducedMotion(); } catch (e) { return false; } };" in src, rel
        assert "matchMedia('(prefers-reduced-motion: reduce)')" not in src, rel


def test_a_readers_home_never_writes_the_desk_note(monkeypatch):
    """BUG-032: the first Home of the day, and up to twelve after it, made a paid call to write or rewrite the desk
    note, against the owner's rule that reading a page costs nothing. Home now only reads what is kept; the keep-warm
    job writes it (DESK_PROSE_AUTO)."""
    asked = []
    monkeypatch.setattr(main.ai, "write_morning_desk", lambda desk: asked.append(desk) or {"lead": ["x"], "scenarios": [], "note": "", "overall": ""})
    monkeypatch.setattr(main.ai, "available", lambda: {"enabled": True})
    monkeypatch.setattr(main, "_DESK_PROSE", {})
    monkeypatch.setattr(main.ai_store, "kept", lambda kind, key: None)
    monkeypatch.setattr(main.ai_store, "claim", lambda *a, **k: True)
    assert main._desk_prose({"date": "2026-10-30"}) is None and asked == []          # a reader's request
    assert main._desk_prose({"date": "2026-10-30"}, write=True) is not None and len(asked) == 1   # the job's
    import inspect
    assert "_morning_desk(out.get(\"macro\")))" in inspect.getsource(main.home_summary)            # Home reads only
    assert "_morning_desk(macro_out.get(\"macro\"), write=True)" in inspect.getsource(main._warm_shared)


def test_a_partial_answer_that_fails_is_kept_as_cut_off_and_reports_stay_with_their_conversation():
    """BUG-051: part of an answer followed by an error was shown and saved as if complete, and an open report form
    reappeared on the same position of the next conversation. Browser check: tools/phase10_partial.py."""
    src = read("static/v2/js/ui/milo.js")
    assert "if (failed && !ended) ended = 'cut';" in src
    assert "S.report && S.report.i === it.i && S.report.conv === S.conv.id ? reportHTML(it.i)" in src
    assert src.count("S.report = { conv: S.conv.id, i") == 1 and "? null : { conv: S.conv.id, i, text: '' }" in src
    # the conversation a report was written in is taken before its request, not after it returns (BUG-185, Phase 11)
    send = src[src.index("async function sendReport"):src.index("export function concerns")]
    assert send.index("const conv = S.conv.id;") < send.index("await api.post('/api/feedback'") and send.count("S.report = { conv, i") == 3
    assert "S.view = null; S.report = null;" in src


def test_closing_the_keep_sheet_unanswered_settles_whose_browser_it_is():
    """BUG-047: closed without an answer, the browser stayed between the guest and the account: the account's settings
    could not be read and Milo's history stopped saving. Browser check: tools/phase10_keepsheet.py."""
    app = read("static/v2/js/app.js")
    assert "closed: () => { if (!guestAnswering && askIsPending()) keepGuestThingsOut(); }," in app
    assert "Closing this leaves them for the next guest." in app
    assert "guestAnswering = true;\n      drawer.close({ silent: true, force: true });" in app
    assert "export const askIsPending = () => !!askPending;" in read("static/v2/js/core/device.js")


def test_the_overview_draws_a_refreshed_copy_when_it_lands():
    """BUG-065: a copy kept past its time was drawn and refreshed behind it, but nothing drew the fresh one, so a
    company opened earlier showed its old figures until a reload."""
    src = read("static/v2/js/pages/dossier.js")
    assert "onUpdate: (d) => { if (mine()) { ok(d); paint(main, sym); } }" in src
    body = src[src.index("const fresh = (url, opts, ok, bad)"):][:4000]
    assert body.count("fresh(`/api/") >= 10 and "step(api.get(`" not in body


def test_classic_logos_come_through_optics_proxy():
    """BUG-028: Classic read logos from three outside favicon services keyed on the company's domain, which saw every
    reader and which companies they looked at; Chrome blocked one of them."""
    src = read("static/app.js")
    block = src[src.index("const LOGO_SOURCES = ["):][:120]
    assert "(t) => `/api/logo/${encodeURIComponent(t)}`," in block
    for host in ("unavatar.io/${", "favicone.com/${", "s2/favicons?domain=${"):
        assert host not in src, host


def test_macros_breadth_says_why_it_has_no_figures():
    """BUG-039: with the macro picture failed, the Breadth tab drew two "n/a" with no reason. Browser check with every
    Read and Macro source failing: tools/phase10_blank.py (every section states the failure, none left loading)."""
    src = read("static/v2/js/pages/macro.js")
    body = src[src.index("function breadth() {"):][:700]
    assert "if (D.err || (D.m && D.m.available === false)) return html`<p class=\"t-muted\">Breadth comes with the macro picture above, which did not load." in body
    assert "if (!D.m) return html`<p class=\"t-muted\" role=\"status\">Breadth comes with the macro picture, which is still loading.</p>`;" in body


def test_the_tracking_pages_say_when_and_what_they_left_out():
    """BUG-073: Optic Portfolio's figures had no time and its progress poll failed in silence; Paper Desk ignored the
    server's dropped and capped and marked only on load and after a trade; Retirement showed the last result under an
    error card and clamped inputs in silence; Watchlist's "Checked" time was the browser's."""
    tr = read("static/v2/js/pages/tracker.js")
    assert "Open positions last marked ${stamp(at)}; the figures above are as of then." in tr
    assert "else { pollFails += 1; D.pollErr = e; }" in tr and "run && pollFails >= 3 ?" in tr
    pp = read("static/v2/js/pages/paper.js")
    assert "if (out.capped) why.push(" in pp and "if (out.dropped && !out.capped) why.push(" in pp
    assert "remark = poll(async (current) => {" in pp and "if (remark) { remark.stop(); remark = null; }" in pp
    rt = read("static/v2/js/pages/retirement.js")
    assert "D.err = null; D.d = null; paint();" in rt and "D.clamped = changed.length ?" in rt
    wl = read("static/v2/js/pages/watchlist.js")
    assert "S.checked = res.map((r) => r && r.generated_at).filter(Boolean).sort()[0] || new Date().toISOString();" in wl
    assert '"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),' in read("app/analytics/watchlist.py")


def test_the_readers_own_blocks_go_only_with_a_question_about_them():
    """BUG-071: a watchlist's rows, a paper book and its journal, a retirement plan went with every question asked from
    those pages, about anything."""
    page = {"view": "paper", "reader_holdings": [{"ticker": "AAPL", "qty": 10}], "journal": {"trades": []},
            "watchlist": {"rows": [{"symbol": "KO"}]}, "roth": {"inputs": {}}}
    ask = lambda q: main._personal_blocks_for([{"role": "user", "content": q}], dict(page))   # noqa: E731
    ctx, left = ask("What is a P/E ratio?")
    assert not any(k in ctx for k in ("reader_holdings", "journal", "watchlist", "roth")) and ctx["view"] == "paper"
    assert left == ["the list on this page", "your paper book", "your trade journal", "your retirement plan"]
    for about_mine in ("How did my paper trades do?", "Which of these looks strongest?", "Should I trim AAPL?",
                       "How is the list doing today?", "Is my Roth allocation too risky?"):
        ctx, left = ask(about_mine)
        assert "reader_holdings" in ctx and left == [], about_mine
    src = read("app/main.py")
    assert 'yield ai._sse("attachments", {"problems": ["{}, since the question is not about it".format(x) for x in left]})' in src
    assert "m.notSent = [...(m.notSent || []), ...p.problems.map(String)].slice(0, 6);" in read("static/v2/js/ui/milo.js")
