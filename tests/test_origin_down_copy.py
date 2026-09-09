"""What the app says when the server is unreachable.

The banner explained that "this address is a temporary tunnel, and it changes
every time the server restarts. So if it has rotated, this link is dead and no
reload will bring it back." That was true when it was written: the app was
served through a Cloudflare quick tunnel from a laptop. On a custom domain it is
wrong twice over. The link is fine, and reloading is exactly what fixes it once
the origin answers, so the copy sent the operator hunting for a replacement URL
that does not exist.

Same stale premise in `app/alerts.py`, which told the operator the server "runs
on a laptop behind a temporary tunnel" and to set ALERT_ALWAYS_ON "once it is
deployed somewhere that stays up" on the site that is already deployed.
"""

from __future__ import annotations

import importlib
import os
import re

import pytest

APP_JS = open("static/app.js").read()
ALERTS_PY = open("app/alerts.py").read()


def _reader_strings(path: str):
    """String literals in a module, minus the docstrings.

    A regex over quote characters cannot tell the two apart, and the first
    version of this matched the module docstring and failed on its own
    past-tense account of the history. `ast` knows which strings are
    docstrings, so this asks it."""
    import ast

    tree = ast.parse(open(path).read())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            first = body[0] if body else None
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docstrings.add(id(first.value))
    out = [n.value for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)
           and id(n) not in docstrings and len(n.value) >= 40]
    assert out, "no reader-facing strings parsed, so this checks nothing"
    return out


def _fn(src: str, name: str) -> str:
    start = src.index("function %s(" % name)
    nxt = src.find("\nfunction ", start + 1)
    return src[start:nxt if nxt > 0 else len(src)]


# --------------------------------------------------------------- the banner


def test_the_tunnel_claim_is_conditional_now():
    """Not deleted: it is still correct for anyone running this through a quick
    tunnel, which is what the flag distinguishes."""
    fn = _fn(APP_JS, "errorHTML")
    assert "originIsEphemeral()" in fn
    assert "temporary tunnel" in fn          # kept for the case where it is true
    assert "This address is not going to change" in fn


def test_only_a_quick_tunnel_counts_as_ephemeral():
    """A custom domain, Railway's generated domain and localhost all keep their
    name across a restart."""
    fn = _fn(APP_JS, "originIsEphemeral")
    match = re.search(r"return (/.*/i)\.test\(location\.hostname\)", fn)
    assert match, fn
    pattern = match.group(1)
    assert "trycloudflare" in pattern
    # Nothing else may be classified as disposable.
    for stable in ("railway.app", "theopticterminal.com", "localhost"):
        assert stable not in pattern, stable


def test_the_ephemeral_test_reads_the_address_not_a_setting():
    """The one thing the client always knows for certain is the host the
    browser actually used."""
    assert "location.hostname" in _fn(APP_JS, "originIsEphemeral")


def test_the_stable_copy_does_not_tell_anyone_to_find_a_new_link():
    fn = _fn(APP_JS, "errorHTML")
    stable = fn[fn.index("This address is not going to change"):]
    stable = stable[:stable.index("`")]
    for wrong in ("expired", "new address", "current link", "dead"):
        assert wrong not in stable, wrong


def test_the_stable_copy_only_promises_what_the_poller_does():
    """It says the page reloads itself, so something has to reload it. Verified
    live as well: the navigation type after recovery is `reload`."""
    fn = _fn(APP_JS, "errorHTML")
    assert "startOriginWatch()" in fn
    watch = _fn(APP_JS, "startOriginWatch")
    assert "location.reload()" in watch


def test_the_streaming_path_branches_the_same_way():
    """A bare "HTTP 530" reads as the assistant breaking, so this message is
    worth having; it just cannot claim the domain expired."""
    # Anchored on the branch itself. Anchoring on "This link has expired"
    # started the window *after* the call that decides which copy runs.
    block = APP_JS[APP_JS.index("detail = originIsEphemeral()"):]
    block = block[:block.index("throw new Error")]
    assert "This link has expired" in block    # kept, for the tunnel case
    assert "The address is fine" in block


def test_all_three_502_sites_branch_on_the_host():
    """There are three, not two. A test that anchored on the shared status
    range found `getJSON` instead of the streaming path, which is how the third
    one turned up at all."""
    sites = [m.start() for m in
             re.finditer(r"res\.status >= 502 && res\.status <= 530", APP_JS)]
    assert len(sites) == 2, sites          # getJSON and the streaming reader
    for start in sites:
        window = APP_JS[start:start + 900]
        assert "originIsEphemeral()" in window, APP_JS[start:start + 200]


def test_both_messages_share_one_host_test():
    """Two copies of the hostname rule would drift, and the one that was not
    updated would give the wrong advice silently."""
    assert APP_JS.count("function originIsEphemeral(") == 1
    assert APP_JS.count("originIsEphemeral()") >= 2
    assert APP_JS.count("trycloudflare") == 1


def test_no_em_dashes_in_the_new_copy():
    fn = _fn(APP_JS, "errorHTML")
    note = fn[fn.index("const note ="):fn.index("return `<div class=\"error-box\">")]
    assert "—" not in note


# ---------------------------------------------------------------- the alerts


@pytest.fixture
def alerts_module():
    import app.alerts as mod
    yield mod
    importlib.reload(mod)


def test_the_alerts_blocker_reads_where_it_is_running(monkeypatch, alerts_module):
    """It asserted a laptop. On the deployed site that told the operator to wait
    for a deployment that had already happened."""
    monkeypatch.delenv("ALERT_ALWAYS_ON", raising=False)

    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    importlib.reload(alerts_module)
    local = " ".join(alerts_module.delivery_status()["blockers"])
    assert "local process that stops when you close it" in local

    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    importlib.reload(alerts_module)
    hosted = " ".join(alerts_module.delivery_status()["blockers"])
    assert "on a hosting platform" in hosted
    assert "laptop" not in hosted


def test_no_reader_facing_copy_asserts_a_laptop():
    """Scoped to strings a reader can see.

    The first version banned the phrase from the whole file, which failed on the
    module docstring's own account of the history: "this ran on a laptop behind
    a temporary tunnel" is a true past-tense sentence explaining why the code
    looks the way it does, and comments recording what changed are the house
    style rather than something to purge."""
    for text in _reader_strings("app/alerts.py"):
        assert "laptop" not in text, text
        assert "temporary tunnel" not in text, text
