"""The record restarts on a new list of names, and the old one is kept.

Asked for on 2026-09-29: restart the portfolio and trade only big names and
index plays. There is no reset in this app on purpose (the record is its only
backtest, see test_books.test_there_is_no_way_to_wipe_the_ledger), so the
restart deletes nothing. Every live row is stamped with the time it was set
aside, open positions are closed first at their last mark so the old record
ends on a number, and the page shows that record's final figures under the new
one. It happens once, the first time a build that lists it opens the ledger,
and a later build cannot run it again by accident.

The list is 61 stocks and 25 funds, checked against Yahoo that day: all quote,
and the thinnest trades about $101M a day. It gets its own screen file, because
the exchange-wide ranking is also what the Scan, Explore and Priority pages
read, and under the shared name 86 symbols would have replaced 3,000 on all of
them. The scan still refreshes that ranking for them.
"""
from __future__ import annotations

import sqlite3

import pytest

from app import paper, universe
from app.analytics import screen

OLD_SCHEMA = (paper.SCHEMA
              .replace(",\n    archived_at   TEXT                    -- set when the record restarted; NULL is live", "")
              .replace(",\n    archived_at TEXT", "")
              .split("CREATE TABLE IF NOT EXISTS ledger_meta")[0])


@pytest.fixture()
def old_ledger(tmp_path, monkeypatch):
    """A ledger written by the build before this one: no archive column, no
    marker, three books with open and closed positions and a few scans."""
    path = str(tmp_path / "tracker.db")
    monkeypatch.setattr(paper, "DB_PATH", path)
    assert "archived_at" not in OLD_SCHEMA and "ledger_meta" not in OLD_SCHEMA
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    rows = [
        # book, ticker, status, pnl, pnl_pct, mark_price, entry_price
        ("balanced", "AAA", "closed", -300.0, -3.0, None, 10.0),
        ("balanced", "BBB", "open", -120.0, -2.4, 9.5, 10.0),
        ("balanced", "CCC", "open", 80.0, 1.6, None, 10.0),          # never marked
        ("aggressive", "DDD", "closed", 500.0, 5.0, None, 10.0),
        ("aggressive", "EEE", "open", -60.0, -1.2, 9.0, 10.0),
        ("conservative", "FFF", "closed", -40.0, -0.4, None, 10.0),
    ]
    for book, ticker, status, pnl, pct, mark, entry in rows:
        conn.execute(
            "INSERT INTO positions (book,ticker,instrument,direction,qty,entry_price,entry_spot,"
            "entry_at,status,pnl,pnl_pct,risk_dollars,mark_price,mark_spot) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (book, ticker, "shares", "long", 100, entry, entry, "2026-09-03T14:00:00+00:00",
             status, pnl, pct, 100.0, mark, mark))
    for i in range(3):
        conn.execute("INSERT INTO scans (ran_at, trigger, considered, opened, closed) "
                     "VALUES (?,?,?,?,?)", ("2026-09-2%dT14:00:00+00:00" % i, "scheduled", 30, 1, 0))
    conn.commit()
    conn.close()
    return path


def _count(sql):
    return paper._rows(sql)[0]["n"]


def test_the_restart_sets_the_record_aside_and_deletes_nothing(old_ledger):
    paper.init_db()
    assert _count("SELECT COUNT(*) AS n FROM positions") == 6
    assert _count("SELECT COUNT(*) AS n FROM scans") == 3
    assert _count("SELECT COUNT(*) AS n FROM positions WHERE archived_at IS NULL") == 0
    assert _count("SELECT COUNT(*) AS n FROM scans WHERE archived_at IS NULL") == 0
    assert _count("SELECT COUNT(*) AS n FROM positions WHERE status='open'") == 0
    restarted = paper._rows("SELECT * FROM positions WHERE exit_reason=? ORDER BY ticker",
                            (paper.RESTART_EXIT_REASON,))
    assert [r["ticker"] for r in restarted] == ["BBB", "CCC", "EEE"], "only what was open"
    bbb, ccc = restarted[0], restarted[1]
    assert bbb["exit_price"] == 9.5 and bbb["pnl"] == -120.0, "closed at its last mark"
    assert ccc["exit_price"] == 10.0 and ccc["pnl"] == 80.0, "never marked: its entry"


def test_the_new_record_starts_empty_and_the_old_one_is_on_the_page(old_ledger):
    paper.init_db()
    s = paper.summary("balanced")
    assert s["open_count"] == 0 and s["closed_count"] == 0 and s["equity"] == paper.START_EQUITY
    assert paper.first_entry("balanced") is None
    assert paper.equity_for("aggressive") == paper.START_EQUITY
    state = paper.state()
    assert state["open"] == [] and state["closed"] == [] and state["scans"] == []
    [record] = state["archive"]
    assert record["label"] == "NASDAQ screen" and record["trades"] == 6
    assert record["from"] == "2026-09-03"
    books = {b["id"]: b for b in record["books"]}
    # Realised plus the open positions at their marks: the figures the page
    # showed the moment before the restart.
    assert books["balanced"]["pnl"] == pytest.approx(-340.0)
    assert books["aggressive"]["pnl"] == pytest.approx(440.0)
    assert books["conservative"]["return_pct"] == pytest.approx(-0.04)


def test_it_happens_once(old_ledger):
    paper.init_db()
    with paper._LOCK, paper._connect() as conn:
        conn.execute(
            "INSERT INTO positions (book,ticker,instrument,direction,qty,entry_price,entry_spot,"
            "entry_at,status,risk_dollars) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("balanced", "NVDA", "shares", "long", 10, 180.0, 180.0,
             "2026-09-29T14:00:00+00:00", "open", 50.0))
    paper.init_db()
    paper.init_db()
    assert paper.summary("balanced")["open_count"] == 1, "a later open is not a restart"
    assert paper.first_entry("balanced") == "2026-09-29"


def test_a_fresh_ledger_records_the_restart_without_archiving_anything(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "DB_PATH", str(tmp_path / "fresh.db"))
    paper.init_db()
    keys = [r["key"] for r in paper._rows("SELECT key FROM ledger_meta")]
    assert keys == ["restart:" + paper.RESTARTS[-1]["id"]]
    assert paper.archived_records()[0]["trades"] == 0


def test_every_live_reader_filters_the_archive():
    """A reader without the filter would mix the two records: the equity, the
    risk budget, the held list, the months and the position lists."""
    import inspect
    for fn in (paper.mark_open_positions, paper.equity_for, paper.open_risk, paper._capacity,
               paper.first_entry, paper.summary, paper._month_span, paper.monthly_breakdown,
               paper.month_detail, paper.state):
        src = inspect.getsource(fn)
        for stmt in [line for line in src.splitlines() if "FROM positions" in line or "FROM scans" in line]:
            assert "LIVE" in stmt or "archived_at" in stmt, (fn.__name__, stmt.strip())
    held = inspect.getsource(paper.run_scan)
    assert "\"SELECT ticker FROM positions WHERE status='open' AND \" + LIVE" in held


# ------------------------------------------------------------- the universe

def test_the_default_universe_is_the_curated_list():
    got = paper.resolve_universe(None)
    assert got["name"] == "curated" and got["count"] == 86 == len(set(paper.CURATED_UNIVERSE))
    for asked in ("META", "AAPL", "HOOD", "COIN", "SPCX", "SOXL", "IGV", "TQQQ", "SPY"):
        assert asked in paper.CURATED_UNIVERSE, asked
    assert "curated" in universe.UNIVERSES


def test_the_curated_list_is_screened_apart_and_the_shared_ranking_kept_fresh(monkeypatch):
    calls = []

    def fake_run(provider, symbols, top_n=30, exclude=None, progress=None, force=False,
                 cache_name=None, **kw):
        calls.append((len(symbols), cache_name))
        return {"shortlist": [], "funnel": {}}
    monkeypatch.setattr(paper.screen, "run", fake_run)
    monkeypatch.setattr(paper.universe, "nasdaq_symbols",
                        lambda: {"symbols": ["X%d" % i for i in range(3000)], "count": 3000})
    monkeypatch.setattr(paper, "mark_open_positions", lambda provider, rate: {"marked": 0, "closed": 0})
    monkeypatch.setattr(paper, "_feed_throttled", lambda: False)
    paper.run_scan(lambda t: {}, provider=None, allow_entries=True)
    assert calls == [(3000, None), (86, "curated")], calls


def test_a_named_list_gets_its_own_ranking_file():
    assert screen.cache_path_for(None) == screen.CACHE_PATH
    own = screen.cache_path_for("curated")
    assert own != screen.CACHE_PATH and own.endswith("screen_ranking_curated.json")


def test_the_ledger_is_copied_whole_before_a_row_changes(old_ledger, tmp_path):
    paper.init_db()
    copy = tmp_path / ("tracker-before-%s.db" % paper.RESTARTS[-1]["id"])
    assert copy.exists()
    conn = sqlite3.connect(str(copy))
    try:
        assert conn.execute("SELECT COUNT(*) FROM positions WHERE status='open'").fetchone()[0] == 3
        cols = [r[1] for r in conn.execute("PRAGMA table_info(positions)")]
    finally:
        conn.close()
    assert "archived_at" in cols, "taken after the column was added, before any row changed"


def test_no_copy_means_no_restart(old_ledger, monkeypatch):
    def refuse(conn, restart_id):
        raise OSError("disk full")
    monkeypatch.setattr(paper, "_keep_copy", refuse)
    paper.init_db()
    assert paper.summary("balanced")["open_count"] == 2, "nothing was touched"
    assert not paper._rows("SELECT key FROM ledger_meta")
    monkeypatch.undo()
    monkeypatch.setattr(paper, "DB_PATH", old_ledger)
    paper.init_db()
    assert paper.summary("balanced")["open_count"] == 0, "and the next start does it"


def test_the_page_shows_the_earlier_record_and_the_new_list():
    js = open("static/app.js").read()
    assert "${archivePanelHTML(t.archive)}" in js
    assert "function archivePanelHTML(archive)" in js
    hint = js[js.index("function trackerUniverseHint(cfg) {"):][:700]
    assert "cfg.universe === 'curated'" in hint
    assert "f.universe === 'curated' ? 'names on the list'" in js
    assert "max_notional_pct) || 0.25) * 100" in js, "the selected book's cap, not a fixed 25%"
    assert "existing record belongs to the balanced book" not in js


def test_the_watchlist_escape_hatch_still_skips_the_wide_screen(monkeypatch):
    """DEPLOY.md's answer to the scan's memory peak: TRACKER_UNIVERSE=watchlist."""
    calls = []
    monkeypatch.setattr(paper.screen, "run", lambda provider, symbols, cache_name=None, **kw:
                        calls.append((len(symbols), cache_name)) or {"shortlist": [], "funnel": {}})
    monkeypatch.setattr(paper.universe, "nasdaq_symbols",
                        lambda: pytest.fail("the wide screen ran in watchlist mode"))
    monkeypatch.setattr(paper, "mark_open_positions", lambda provider, rate: {"marked": 0, "closed": 0})
    monkeypatch.setattr(paper, "_feed_throttled", lambda: False)
    paper.run_scan(lambda t: {}, provider=None, allow_entries=True, universe_name="watchlist")
    assert calls == [(10, "watchlist")], calls
