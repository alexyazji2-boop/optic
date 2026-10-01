"""The owner's view of reader-reported problems.

Asked for three times as "where do I go to see the issues people report", and
the honest answer each time was nowhere: reports were written to SQLite and the
only way to read one was a curl with the write token. A command is not a
destination, and answering a third time with the same command would have been
the same non-answer.

**The entrance is hidden; the data is guarded.** `owner: true` keeps the group
off every nav but the owner's, and that is presentation only. `/api/feedback`
is behind `_write_guard` server-side, so a reader who guesses the view id still
meets a refusal rather than other people's words. Both halves are asserted here
because only one of them is security and it is not the one you can see.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
HTML = (ROOT / "static/index.html").read_text()
CSS = (ROOT / "static/styles.css").read_text()
MAIN = (ROOT / "app/main.py").read_text()


def _code(text: str) -> str:
    """Comments stripped, for the reason CLAUDE.md gives twice over."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


# ------------------------------------------- registered in all five places


def test_the_section_exists_in_the_document():
    assert 'id="view-reports"' in HTML


def test_it_is_in_the_views_map():
    assert "reports: $('#view-reports')" in _code(APP)


def test_it_is_in_a_nav_group():
    code = _code(APP)
    assert ("{ id: 'reports', label: 'Reports', views: ['reports', 'usage'], owner: true }"
            in code)


def test_switchview_dispatches_to_its_loader():
    code = _code(APP)
    assert "if (view === 'reports') return loadReports(force);" in code


def test_it_is_in_the_command_palette():
    assert "{ view: 'reports', label: 'Problem Reports'," in APP


def test_it_renders_without_a_loaded_symbol():
    """The allow-list by omission in CLAUDE.md: a new view is ticker-specific
    by default, so this one would render "No symbol loaded" on a page that has
    nothing to do with a symbol. Watchlist, Alerts and Explore were each caught
    that way."""
    block = APP[APP.index("const TICKERLESS_VIEWS = ["):]
    assert "'reports'" in block[:block.index("]")]


def test_it_has_a_label_rather_than_its_raw_id():
    """`SUB_LABELS[v] || v` falls back to the lowercase view id, which has
    shipped twice as a nav reading "insiders" and "paper"."""
    block = APP[APP.index("const SUB_LABELS = {"):]
    assert "reports: 'Problem Reports'" in block[:block.index("\n};")]


# ------------------------------------------------- who can see it, and see it


def test_the_nav_entry_is_for_the_signed_in_owner_only():
    """Not for a browser holding the write token. It used to be either, and a
    token pasted in once kept the tab on that browser signed out: "im not
    signed in, why can i see the reports button? it should only show when the
    domain e-mail is logged in" (2026-09-29).

    The cost, and why the token was the other way in: being the owner needs
    the address in ADMIN_EMAILS and verified, and with no SMTP configured the
    verification link is written to the server log rather than emailed."""
    fn = _code(APP[APP.index("function navVisibleGroups()"):])
    fn = fn[:fn.index("}")]
    assert "!g.owner || isOwner()" in fn
    assert "writeToken" not in fn
    assert "function hasOwnerTools(" not in APP


def test_a_refused_read_does_not_ask_for_the_token():
    """The page is the signed-in owner's, so a refusal is a lapsed session or
    the wrong account, and a prompt for the token would reopen the route the
    nav has just closed."""
    fn = _code(APP[APP.index("async function fetchReports("):])
    fn = fn[:fn.index("\n}")]
    for gone in ("window.prompt(", "setWriteToken(", "writeToken(", "X-Optic-Token"):
        assert gone not in fn, gone


def test_the_page_is_drawn_for_the_signed_in_owner_only():
    """Checked before the cached list is reused, so reports the owner read are
    not left on screen for whoever signs out after them. Anyone else is told
    which of the two things stands in the way, and nothing is fetched."""
    fn = _code(APP[APP.index("async function loadReports("):])
    fn = fn[:fn.index("\n}")]
    guard = fn.index("if (!isOwner()) {")
    assert guard < fn.index("if (!force && STATE.reportsLoaded) return;")
    assert "host.innerHTML = reportsForOwnerHTML();" in fn[guard:guard + 200]
    assert guard < fn.index("fetchReports(")
    msg = _code(APP[APP.index("function reportsForOwnerHTML("):])
    msg = msg[:msg.index("\n}")]
    assert 'data-auth-open="signin"' in msg
    assert "has not been verified yet" in msg


def test_the_palette_offers_it_to_the_owner_only():
    places = APP[APP.index("const PALETTE_PLACES = ["):]
    places = places[:places.index("\n];")]
    assert "{ view: 'reports', label: 'Problem Reports', owner: true," in places
    code = _code(APP)
    assert "PALETTE_PLACES.filter((p) => (!p.owner || isOwner())" in code
    assert "PALETTE_PLACES.filter((p) => !p.owner || isOwner()).slice(0, 6)" in code


def test_owner_is_read_from_the_server_not_inferred_on_the_client():
    """A browser that set this itself would gain nothing, because every owner
    path is re-checked server-side. It would make the nav claim a privilege the
    API refuses, which is worse than showing nothing."""
    fn = _code(APP[APP.index("function isOwner()"):])
    fn = fn[:fn.index("\n}")]
    assert "OpticAuth" in fn and "admin" in fn
    assert "@" not in fn, "the client must not compare an address itself"


def test_the_nav_repaints_when_auth_resolves():
    """`paintNav` runs at boot and `/api/auth/me` answers over the network some
    time after, so the first paint is always made as a guest. Without this the
    owner's tab is missing until they happen to navigate. And the page itself
    is redrawn, so signing out on it takes the list off the screen."""
    code = _code(APP)
    at = code.index("window.OpticAuth.on(() => {")
    block = code[at:code.index("});", at)]
    assert "paintNav(STATE.view || 'home');" in block
    assert "if (STATE.view === 'reports') loadReports(true);" in block


def test_the_data_is_guarded_server_side_and_not_only_hidden():
    """The half that is actually security. Hiding the entrance is presentation;
    this is what stops a reader who types the view id from reading other
    people's words."""
    route = MAIN[MAIN.index('@app.get("/api/feedback")'):]
    route = route[:route.index("\n@app.")]
    code = re.sub(r'""".*?"""', " ", route, flags=re.S)
    assert "_write_guard(request)" in code


# ------------------------------------------------------------- the fetch


def test_the_read_sends_the_csrf_header():
    """`_write_guard`'s owner branch pairs with `csrf_guard`, so a signed-in
    owner's cookie is refused on this GET without the header."""
    fn = _code(APP[APP.index("async function fetchReports("):])
    fn = fn[:fn.index("\n}")]
    assert "X-Optic-CSRF" in fn
    assert "credentials: 'same-origin'" in fn


def test_the_read_does_not_go_through_the_retrying_helper():
    """`getJSON` retries on failure, which asks the same unauthorised question
    three times more slowly, and it sends no CSRF header at all."""
    fn = _code(APP[APP.index("async function fetchReports("):])
    fn = fn[:fn.index("\n}")]
    assert "getJSON(" not in fn


def test_a_refusal_keeps_the_servers_own_sentence():
    """`_write_guard` and the read route already say which of the three things
    is missing. Replacing that with "could not load" throws away the only part
    the reader can act on -- and this app shipped that exact defect once, which
    is why the route has its own copy at all."""
    fn = _code(APP[APP.index("async function loadReports("):])
    fn = fn[:fn.index("\n}\n")]
    assert "err.message" in fn
    assert "err.status === 401" in fn and "503" in fn


def test_a_report_keeps_the_line_breaks_the_reader_typed():
    """A report is typed prose. Collapsing its newlines loses the shape of what
    somebody was trying to show you."""
    rule = CSS[CSS.index(".rp-item-msg {"):]
    rule = rule[:rule.index("}")]
    assert "white-space: pre-wrap" in rule


def test_the_list_says_when_it_is_showing_a_page_of_a_longer_record():
    """The endpoint pages at 50, and a reader who cannot see the total reads
    the page as the whole record."""
    fn = _code(APP[APP.index("function reportsHTML("):])
    fn = fn[:fn.index("\n}\n")]
    assert "data.total" in fn
    assert "Showing the newest" in fn
