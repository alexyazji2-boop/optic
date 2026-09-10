"""Named watchlists: several lists, renamed, reordered, searched.

The single list was the whole model. WATCH_KEY held a flat array of symbols and
every reader in the app went through watchList(); the account side already had a
`watchlists` table with a `position` column on both it and its items, and nothing
in the product ever created a second list or set a position.

Lists are a layer *above* the flat key rather than a replacement for it. WATCH_KEY
still holds the active list, so the Charting dock widget (same key under its own
name), the home summary, the feed and the alert builder are untouched. That is the
property most worth protecting here, and most of these tests are about it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()
STYLES = (ROOT / "static" / "styles.css").read_text()
ACCOUNT_PY = (ROOT / "app" / "account.py").read_text()


# --------------------------------------------------- the flat key still works

def test_the_active_list_is_still_the_flat_key():
    """Everything outside this feature reads WATCH_KEY. If a list switch did not
    write it, the Charting dock and the home summary would show the list the
    reader was looking at yesterday."""
    body = APP_JS.split("function watchSave(", 1)[1].split("\n}", 1)[0]
    assert "localStorage.setItem(WATCH_KEY" in body
    assert "localListsPutActive(clean)" in body, \
        "a write to the active list no longer reaches the lists store"


def test_watch_list_stayed_synchronous_and_unchanged():
    """Render paths all over app.js call it. The lists layer sits above it."""
    body = APP_JS.split("function watchList() {", 1)[1].split("\n}", 1)[0]
    assert "ACCOUNT.watchlist" in body and "localWatchList()" in body
    assert "await" not in body


def test_switching_a_list_rewrites_the_flat_key():
    body = APP_JS.split("async function watchListSwitch(", 1)[1].split("\n}\n", 1)[0]
    assert "WATCH_KEY" in body or "watchSave(" in body


def test_the_local_store_migrates_the_single_list():
    """A reader who has only ever had one list keeps their symbols, as the first
    named list, rather than being handed an empty one."""
    body = APP_JS.split("function localLists() {", 1)[1].split("\n}\n", 1)[0]
    assert "localWatchList()" in body
    assert "'Watchlist'" in body


def test_an_empty_list_stays_empty():
    """The bug this feature surfaced, and the one no contract caught until it was
    driven by hand.

    localWatchList() read `Array.isArray(raw) && raw.length`, so a stored [] fell
    through to WATCH_DEFAULT. With one list that was nearly invisible: you only
    reach [] by removing every symbol, and getting SPY/QQQ/NVDA/AMD back merely
    looked like a reset. With named lists it is load-bearing — creating a list
    stores [] — so the second list ever made came up already holding four
    symbols, and the first add appended to them.
    """
    body = APP_JS.split("function localWatchList() {", 1)[1].split("\n}\n", 1)[0]
    assert "if (Array.isArray(raw)) {" in body, \
        "an explicitly empty list is being treated as an absent one"
    assert "WATCH_DEFAULT.slice()" in body, \
        "a first-time reader should still get the starter list"


def test_a_guest_gets_lists_too():
    """The terminal is open to everyone. Inventing an account to hold six ticker
    symbols is the thing this app has always refused to do."""
    body = APP_JS.split("function watchAllLists() {", 1)[1].split("\n}\n", 1)[0]
    assert "signedIn()" in body and "localLists()" in body


# ------------------------------------------------------------- the operations

@pytest.mark.parametrize("fn", ["watchListCreate", "watchListRename", "watchListDelete",
                                "watchListMove", "watchListSwitch", "watchSymbolMove"])
def test_every_operation_exists(fn):
    assert f"function {fn}(" in APP_JS


@pytest.mark.parametrize("attr,handler", [
    ("data-watch-list", "watchListSwitch"),
    ("data-watch-list-new", "watchListCreate"),
    ("data-watch-list-rename", "watchListRename"),
    ("data-watch-list-del", "watchListDelete"),
    ("data-watch-list-move", "watchListMove"),
    ("data-watch-up", "watchSymbolMove"),
    ("data-watch-down", "watchSymbolMove"),
])
def test_every_control_has_a_handler(attr, handler):
    """A dead control does not error. It takes the click and nothing happens,
    which reads as a slow app."""
    assert f"closest('[{attr}]')" in APP_JS, f"{attr} has no handler"
    # Generous window: handlers in this file carry their reasoning above the
    # call, and the delete branch's comment alone is 300 characters.
    block = APP_JS.split(f"closest('[{attr}]')", 1)[1][:900]
    assert handler in block, f"{attr} does not reach {handler}"


def test_the_last_list_cannot_be_deleted():
    """Deleting it leaves the view with nothing to render and the next add with
    nowhere to go. Emptying a list is what the row remove already does."""
    body = APP_JS.split("async function watchListDelete(", 1)[1].split("\n}\n", 1)[0]
    assert "watchAllLists().length <= 1" in body


def test_deleting_a_list_is_confirmed_and_removing_a_symbol_is_not():
    """One is destructive and takes the symbols with it; the other is four
    keystrokes to undo. Confirming both trains people to click through."""
    block = APP_JS.split("closest('[data-watch-list-del]')", 1)[1][:500]
    assert "window.confirm(" in block
    row = APP_JS.split("function watchRemove(", 1)[1].split("\n}\n", 1)[0]
    assert "confirm(" not in row


def test_a_duplicate_name_is_refused():
    for fn in ("watchListCreate", "watchListRename"):
        body = APP_JS.split(f"async function {fn}(", 1)[1].split("\n}\n", 1)[0]
        assert "toLowerCase()" in body and "already have a list" in body, fn


# ------------------------------------------------------------ order and search

def test_my_order_is_a_sort_with_no_comparator():
    """The rows are already built in list order, so the reader's own order is
    the absence of a sort rather than another comparator."""
    block = APP_JS.split("const WATCH_SORTS = [", 1)[1].split("\n];", 1)[0]
    assert "{ id: 'custom', label: 'My order', cmp: null }" in block
    body = APP_JS.split("function watchRowsSorted(", 1)[1].split("\n}\n", 1)[0]
    assert "if (!spec.cmp)" in body
    assert "watchList().map((sym, i)" in body, "my order does not read the stored order"


def test_reorder_handles_only_appear_when_a_move_would_be_visible():
    """Moving a row up while a filter hides the row above it moves it past
    something invisible; reordering under "biggest movers" changes a stored order
    nothing on screen reflects. Both read as a control that does not work."""
    body = APP_JS.split("function watchlistFeedHTML(", 1)[1].split("\n}\n", 1)[0]
    assert "watchSort === 'custom'" in body
    assert "watchFilter === 'all'" in body
    assert "!watchQuery.trim()" in body


def test_search_does_not_repaint_the_whole_view():
    """The box would lose focus on the first keystroke."""
    block = APP_JS.split("evt.target.id !== 'wv-q'", 1)[1][:500]
    assert "getElementById('wv-feed')" in block
    assert "renderWatchlist()" not in block


def test_search_names_itself_when_it_finds_nothing():
    body = APP_JS.split("function watchlistFeedHTML(", 1)[1].split("\n}\n", 1)[0]
    assert "No name on this list matches" in body
    assert "data-watch-clear-q" in body


def test_the_shown_label_names_whichever_narrowing_is_on():
    """A count with no reason beside it reads as names having gone missing."""
    body = APP_JS.split("function watchShownLabel() {", 1)[1].split("\n}\n", 1)[0]
    assert "watchQuery" in body and "spec.id === 'all'" in body


# ---------------------------------------------------------------- the server

def test_the_reorder_endpoints_exist():
    """Both tables have ordered by `position` since the schema was written and
    nothing could ever set one: _put_symbols appends, and that was the only
    writer. "My order" was whatever order things were added in, permanently."""
    assert '@router.put("/watchlists/{watchlist_id}/order")' in ACCOUNT_PY
    assert '@router.put("/watchlists/order")' in ACCOUNT_PY


def test_reorder_is_a_reorder_not_an_upsert():
    """A stale tab replaying an old order must not resurrect a symbol the reader
    has since deleted."""
    body = ACCOUNT_PY.split("async def reorder_items(", 1)[1].split("\n@router", 1)[0]
    assert "if symbol not in held" in body
    assert "INSERT" not in body


def test_reorder_keeps_unmentioned_rows_stable():
    """A partial payload must not silently shuffle the remainder."""
    for fn in ("reorder_items", "reorder_lists"):
        body = ACCOUNT_PY.split(f"async def {fn}(", 1)[1].split("\n@router", 1)[0]
        assert "- seen" in body, f"{fn} drops or reshuffles what it was not sent"


def test_reorder_is_csrf_guarded_and_owner_scoped():
    """Cookie-authorised writes pair with csrf_guard, per the rest of this file."""
    for fn in ("reorder_items", "reorder_lists"):
        body = ACCOUNT_PY.split(f"async def {fn}(", 1)[1].split("\n@router", 1)[0]
        assert "deps.require_user(request)" in body, fn
        assert "deps.csrf_guard(request)" in body, fn


@pytest.mark.parametrize("cls", [".wl-bar", ".wl-chip", ".wl-chip-n", ".wl-tool",
                                 ".wv-search", ".wl-move", ".wl-move-btn"])
def test_the_list_ui_is_styled(cls):
    assert re.search(re.escape(cls) + r"[\s,{:]", STYLES), f"{cls} has no rule"
