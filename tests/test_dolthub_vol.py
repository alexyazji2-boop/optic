"""DoltHub's volatility history (app/dolthub_vol.py) and the IV rank that uses it."""
from __future__ import annotations

from datetime import date

import pytest

from app import dolthub_vol as dv
from app import iv_history


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(iv_history, "DB_PATH", str(tmp_path / "iv_history.db"))
    return tmp_path


def _fake(days):
    """A getter answering the paged day query from {day: [(sym, iv, hv)]}."""
    calls = []

    def get(sql):
        calls.append(sql)
        day = sql.split("date = '")[1][:10]
        after = sql.split("act_symbol > '")[1].split("'")[0]
        rows = sorted(r for r in days.get(day, []) if r[0] > after)[:dv.PAGE]
        return {"query_execution_status": "RowLimit" if len(rows) == dv.PAGE else "Success",
                "rows": [{"act_symbol": s, "iv_current": str(iv), "hv_current": str(hv)} for s, iv, hv in rows]}
    get.calls = calls
    return get


def test_a_day_is_read_in_pages_of_a_thousand(store, monkeypatch):
    monkeypatch.setattr(dv, "PAGE", 3)
    rows = [("S%02d" % i, 0.3, 0.2) for i in range(7)]
    get = _fake({"2026-10-12": rows})
    got = dv.fetch_day(date(2026, 10, 12), get)
    assert [r[0] for r in got] == [r[0] for r in rows]
    assert len(get.calls) == 3


def test_an_error_stops_the_sync_where_it_was(store):
    def bad(sql):
        return {"query_execution_status": "Error", "query_execution_message": "context deadline exceeded"}
    res = dv.sync(until=date(2024, 10, 3), getter=bad, pause=0)
    assert res == {"days": 0, "rows": 0, "pending": 3}


def test_sync_skips_weekends_and_days_already_fetched(store):
    days = {"2024-10-01": [("AAA", 0.5, 0.4)], "2024-10-04": [("AAA", 0.6, 0.4)]}
    get = _fake(days)
    res = dv.sync(until=date(2024, 10, 7), getter=get, pause=0)
    # Tue 1 to Mon 7: five weekdays, the weekend skipped.
    assert res["days"] == 5
    again = _fake(days)
    dv.sync(until=date(2024, 10, 7), getter=again, pause=0)
    # Only the last three days are asked again, and only if they were empty.
    asked = {c.split("date = '")[1][:10] for c in again.calls}
    assert asked == {"2024-10-07"}


def test_the_series_and_iv_against_hv(store):
    days = {}
    d = date(2025, 1, 6)
    k = 0
    while k < 60:
        if d.weekday() < 5:
            days[d.isoformat()] = [("XYZ", 0.30 + 0.001 * k, 0.25)]
            k += 1
        d = date.fromordinal(d.toordinal() + 1)
    dv.sync(until=d, getter=_fake(days), pause=0)
    s = dv.series("xyz")
    assert len(s) == 60 and s[0]["iv"] == pytest.approx(0.30) and s[-1]["iv"] == pytest.approx(0.359)
    r = dv.iv_hv("XYZ")
    assert r["available"] and r["iv30"] == pytest.approx(35.9) and r["hv30"] == 25.0
    assert r["gap"] == pytest.approx(10.9) and r["iv_above_hv_pct"] == 100.0
    assert r["gap_percentile"] == pytest.approx(59 / 60 * 100, abs=0.1)
    assert "CC BY-SA" in r["source"]


def test_the_rank_uses_dolthub_only_when_switched_on(store, monkeypatch):
    days = {}
    d = date(2025, 1, 6)
    k = 0
    while k < 150:
        if d.weekday() < 5:
            days[d.isoformat()] = [("XYZ", 0.20 + 0.002 * k, 0.2)]
            k += 1
        d = date.fromordinal(d.toordinal() + 1)
    dv.sync(until=d, getter=_fake(days), pause=0)
    monkeypatch.delenv("OPTIC_DOLTHUB", raising=False)
    assert iv_history.rank_for("XYZ", 40.0)["available"] is False
    monkeypatch.setenv("OPTIC_DOLTHUB", "1")
    r = iv_history.rank_for("XYZ", 40.0)
    assert r["source"] == "dolthub" and r["days"] == 150
    # Today is DoltHub's own last reading, the top of a rising series.
    assert r["today"] == pytest.approx(49.8) and r["rank"] == 100.0
    assert r["optic_today"] == 40.0 and "CC BY-SA" in r["attribution"]


def test_a_full_year_of_optics_own_readings_comes_first(store, monkeypatch):
    monkeypatch.setenv("OPTIC_DOLTHUB", "1")
    monkeypatch.setattr(iv_history, "stored", lambda sym, limit=252: [30.0 + (i % 10) for i in range(252)])
    monkeypatch.setattr(dv, "series", lambda *a, **k: pytest.fail("DoltHub asked despite a full year"))
    r = iv_history.rank_for("XYZ", 35.0)
    assert r["source"] == "optic_daily"
