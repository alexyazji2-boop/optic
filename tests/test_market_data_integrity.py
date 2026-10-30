"""Market data integrity (post-demo Phase 09, 2026-10-30): what the reconciliation against the providers' own
responses and the audit of Optic's calculations found, pinned.

- A dividend yield is a year of dividends at the current rate over the price shown beside it. Yahoo's own percent is
  worked at another moment's price and rounded to two places (KO 2.31% beside 2.12 / 92.82 = 2.28%), so Optic works it
  from the rate when the feed gives one; a fund has no rate and keeps the feed's trailing distribution yield, which the
  reconciliation matched to its last four distributions.
- The RSI's first fourteen bars have no average yet and stay empty; they used to read 50, a made-up neutral reading.
- The feed's quotes run from real time to fifteen minutes behind, and each states its own trade time and delay, so a
  general statement says "up to 15 minutes" (BUG-098): "delayed about 15 minutes" as a flat claim contradicted a quote
  that states no delay.
"""
from __future__ import annotations

import math
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analytics import technicals as T
from app.providers import yf as Y

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def clean(monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": 100.0, "rate": 100.0, "last": time.time()})
    monkeypatch.setattr(Y, "_THROTTLE", {"until": 0.0, "hits": 0, "last_seen": None})


def _quote(monkeypatch, info):
    monkeypatch.setattr(Y.YFinanceProvider, "_info", lambda self, ticker: dict(info))
    return Y.PROVIDER.quote("ZZZ")


def test_a_stocks_yield_is_its_dividend_rate_over_the_price_shown(clean, monkeypatch):
    q = _quote(monkeypatch, {"regularMarketPrice": 92.82, "regularMarketPreviousClose": 92.0, "dividendYield": 2.31,
                             "dividendRate": 2.12, "quoteType": "EQUITY"})
    assert q["dividend_yield"] == pytest.approx(2.12 / 92.82)
    assert round(q["dividend_yield"] * 100, 2) == 2.28


def test_a_fund_with_no_rate_keeps_the_feeds_distribution_yield(clean, monkeypatch):
    q = _quote(monkeypatch, {"regularMarketPrice": 769.36, "regularMarketPreviousClose": 760.0, "dividendYield": 0.99,
                             "quoteType": "ETF"})
    assert q["dividend_yield"] == pytest.approx(0.0099)


def test_an_implausible_yield_is_still_dropped(clean, monkeypatch):
    q = _quote(monkeypatch, {"regularMarketPrice": 1.0, "regularMarketPreviousClose": 1.0, "dividendYield": 50.0,
                             "dividendRate": 0.5, "quoteType": "EQUITY"})
    assert q["dividend_yield"] is None


def test_the_rsi_warm_up_is_empty_and_its_ends_hold():
    c = pd.Series([100 + i * 0.5 + (2 if i % 3 == 0 else -1) for i in range(60)], dtype=float)
    r = T.rsi(c, 14)
    assert r.iloc[:14].isna().all(), "no reading before fourteen changes"
    assert r.iloc[14:].notna().all()
    assert T.rsi(pd.Series(np.arange(30, dtype=float)), 14).iloc[-1] == 100.0
    assert T.rsi(pd.Series([5.0] * 30), 14).iloc[-1] == 50.0
    assert T.rsi(pd.Series(np.arange(30, 0, -1, dtype=float)), 14).iloc[-1] == 0.0
    out = T.analyse(pd.DataFrame({"Open": c.values, "High": (c + 1).values, "Low": (c - 1).values, "Close": c.values,
                                  "Volume": [1000] * len(c)}, index=pd.bdate_range("2026-01-01", periods=len(c))))
    series = out["rsi"]["series"]
    assert series[:14] == [None] * 14 and all(isinstance(v, float) for v in series[14:])


# Statements about the quote feed as a whole. Option chains are a different feed (their quotes are delayed about 15
# minutes), and the legal pages are counsel's (COMPLIANCE_REVIEW), so neither is scanned here.
FLAT = re.compile(r"(?i)\b(?:quotes?|prices?)\b[^.'\"`]{0,40}\b(?:delayed|behind)\b(?![^.'\"`]{0,12}\bup to\b)[^.'\"`]{0,12}"
                  r"(?:\babout|\broughly|~)\s*15|\bDelayed ~?15 min\b|(?<!up to )\babout 15 minutes behind\b")


@pytest.mark.parametrize("path", ["static/v2/js", "static/app.js", "app/main.py", "app/ai.py", "app/milo_tools.py",
                                  "app/analytics/watches.py", "app/research/service.py", "app/providers/yf.py"])
def test_no_general_statement_calls_every_quote_15_minutes_late(path):
    files = sorted((ROOT / path).rglob("*.js")) if (ROOT / path).is_dir() else [ROOT / path]
    found = []
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if FLAT.search(line) and "option" not in line.lower() and "chain" not in line.lower():
                found.append("{}:{}: {}".format(f.relative_to(ROOT), n, line.strip()[:120]))
    assert not found, found


def test_the_workspace_spot_states_the_quotes_own_delay():
    src = (ROOT / "app/main.py").read_text(encoding="utf-8")
    body = src[src.index("def _ws_spot("):src.index("def _ws_div(")]
    assert '"delayed_minutes": q.get("delayed_minutes")' in body and '"delayed_minutes": 15' not in body


# ------------------------------------------------------------------ the session against NYSE's own calendar
# NYSE Group's published holiday and early-close calendar for 2026 and 2027 (ICE press release of 2025, and
# nyse.com/trade/hours-calendars, read 2026-10-30): ten full closures a year, half days ending at 1:00pm with the late
# sessions at 5:00pm.
from datetime import date, datetime as _dt  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from app import session as S  # noqa: E402

ET = ZoneInfo("America/New_York")
NYSE = {
    2026: ({"2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
            "2026-11-26", "2026-12-25"}, {"2026-11-27", "2026-12-24"}),
    2027: ({"2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06",
            "2027-11-25", "2027-12-24"}, {"2027-11-26"}),
}


@pytest.mark.parametrize("year", sorted(NYSE))
def test_the_calendar_is_nyses_published_one(year):
    holidays, early = NYSE[year]
    assert {d.isoformat() for d in S.market_holidays(year)} == holidays
    assert {d.isoformat() for d in S.early_closes(year)} == early


def _at(stamp):
    return S.state(_dt.strptime(stamp, "%Y-%m-%d %H:%M").replace(tzinfo=ET))


@pytest.mark.parametrize("stamp, phase, label", [
    ("2026-10-28 08:00", "pre", "Pre-market"),
    ("2026-10-28 11:00", "regular", "Regular session"),
    ("2026-10-28 17:30", "after", "After hours"),
    ("2026-10-28 22:00", "overnight", "Overnight"),
    ("2026-10-31 12:00", "closed", "Weekend. Closed"),
    ("2026-11-26 12:00", "holiday", "Thanksgiving Day. Closed"),
    ("2026-11-25 20:30", "closed", "Closed for Thanksgiving Day"),        # no overnight session before a holiday
    ("2026-11-27 12:30", "regular", "Regular session"),
    ("2026-11-27 13:30", "after", "After hours"),
    ("2026-11-27 17:30", "closed", "Closed after the half day"),
    ("2026-12-24 20:30", "closed", "Closed for Christmas Day"),
    # the clocks go back on Sunday 2026-11-01: the session follows New York time on either side
    ("2026-10-30 09:31", "regular", "Regular session"),
    ("2026-11-02 09:31", "regular", "Regular session"),
])
def test_each_phase_is_named_for_what_is_trading(stamp, phase, label):
    st = _at(stamp)
    assert (st["phase"], st["label"]) == (phase, label), st["label"]
    assert st["is_regular"] == (phase == "regular")
    assert st["is_open"] == (phase in ("regular", "after", "pre", "overnight"))
    if phase == "closed":
        assert "weekend" not in st["description"].lower() or label == "Weekend. Closed"


def test_the_half_days_strip_has_its_own_hours():
    segs = {g["phase"] + ("" if g["phase"] != "overnight" else str(g["start"])): (g["start"], g["end"]) for g in _at("2026-11-27 10:00")["segments"]}
    assert segs["regular"] == (570, 780) and segs["after"] == (780, 1020) and segs["closed"] == (1020, 1200)
    normal = [g["phase"] for g in _at("2026-10-28 10:00")["segments"]]
    assert "closed" not in normal and len(normal) == 5


@pytest.mark.parametrize("stamp, close", [
    ("2026-11-02 08:00", "2026-10-30T16:00"),      # Monday morning: Friday's close
    ("2026-11-27 09:00", "2026-11-25T16:00"),      # the morning after Thanksgiving: Wednesday's
    ("2026-11-27 15:00", "2026-11-27T13:00"),      # the half day's own 1pm close
    ("2026-12-28 09:00", "2026-12-24T13:00"),      # after Christmas: Christmas Eve's half day
])
def test_the_close_a_price_belongs_to_is_the_last_session_that_traded(stamp, close):
    assert _at(stamp)["last_close"]["at"].startswith(close)


def test_bars_without_volume_have_no_vwap_rather_than_an_average_called_one():
    from app.analytics import indicators as I
    idx = pd.bdate_range("2026-07-01", periods=30)
    c = pd.Series(np.linspace(100, 110, 30), index=idx)
    with_vol = pd.DataFrame({"Open": c, "High": c + 1, "Low": c - 1, "Close": c, "Volume": [1000.0] * 30}, index=idx)
    without = with_vol.drop(columns=["Volume"])
    typical = (with_vol["High"] + with_vol["Low"] + with_vol["Close"]) / 3
    assert I.vwap(with_vol).iloc[-1] == pytest.approx(typical.mean())
    assert I.vwap(without).isna().all()


# ------------------------------------------------------------------ the pattern study's figures (BUG-067)
import json as _json  # noqa: E402

from tests.test_frontend_v2_stage0 import V2  # noqa: E402
from tests.test_v2_p3 import _run  # noqa: E402

RATES = ROOT / "tests" / "fixtures" / "pattern_base_rates_2026-10-29.json"


def test_the_pattern_panels_say_the_studys_own_figures(tmp_path):
    rates = _json.loads(RATES.read_text())
    t = {"patterns": {"available": True, "method": "", "zones": [], "tolerances": {},
                      "chart_patterns": [{"name": "Double top", "confirmed": True, "conventional": "bearish", "start_date": "2026-09-01",
                                          "end_date": "2026-10-20", "span_bars": 35}],
                      "candles": [{"name": "Hammer", "date": "2026-10-29", "bar_offset": 0, "note": "", "conventional": "bullish", "direction": "bullish"}]}}
    got = _run(tmp_path, f"""
      const P = await import('{(V2 / "js" / "pages" / "options-panels.js").as_posix()}');
      const D = await import('{(V2 / "js" / "core" / "dom.js").as_posix()}');
      const F = await import('{(V2 / "js" / "core" / "format.js").as_posix()}');
      const rates = {_json.dumps(rates)};
      const r = P.rateRanges(rates);
      const withRates = D.toString(P.patterns({_json.dumps(t)}, 'NVDA', {{ rates, loading: false }}));
      const without = D.toString(P.patterns({_json.dumps(t)}, 'NVDA', {{ rates: null, loading: false }}));
      // the page's own rounding, so the sentence and the table cells agree
      const words = [F.num(r.confirmed.lo, 0), F.num(r.confirmed.hi, 0)];
      print(JSON.stringify({{ r, withRates, without, words }}));
    """)
    r = got["r"]
    conf = [v["h21"]["hit_rate"] * 100 for k, v in rates["patterns"].items() if k.endswith("|confirmed") and v["h21"]["hit_rate"] is not None]
    unc = [v["h21"]["hit_rate"] * 100 for k, v in rates["patterns"].items() if k.endswith("|unconfirmed") and v["h21"]["hit_rate"] is not None]
    cand = [v["h21"] for k, v in rates["patterns"].items() if k.endswith("|candle") and v["h21"]["hit_rate"] is not None]
    assert r["confirmed"]["lo"] == pytest.approx(min(conf)) and r["confirmed"]["hi"] == pytest.approx(max(conf))
    assert r["unconfirmed"]["hi"] == pytest.approx(max(unc))
    assert r["candle"]["nlo"] == min(h["n"] for h in cand) and r["candle"]["nhi"] == max(h["n"] for h in cand)
    page = got["withRates"]
    assert "confirmed structures land between {}% and {}%".format(*got["words"]) in page
    assert "between 51% and 55%" not in page and "between 46% and 51% on samples of two to twelve thousand" not in page
    assert "across 43 names and ten years" in page, "the study's size, read from the rates"
    # no rates: no figure stated about the study
    assert "names and ten years" not in got["without"] and "confirmed structures land" not in got["without"]
    assert "Every candlestick pattern here measures" not in got["without"]


def test_classic_says_the_same_figures():
    src = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    copy = re.sub(r"/\*.*?\*/", "", src, flags=re.S)                  # the comment that records the old figures aside
    assert "between 51% and 55%" not in copy and "one of them at 31%" not in copy and "two to twelve thousand occurrences" not in copy
    assert "function patternRateRanges(rates)" in src and "const rr = patternRateRanges(rates);" in src


def test_both_surfaces_say_why_compares_scores_differ_from_the_overviews():
    """BUG-011: one company, two models: NVDA read 81 long term on the Overview and 72.6 on Compare (2026-10-30), and
    only Compare said why. Both apps now say it on both pages."""
    v2_over = (ROOT / "static/v2/js/pages/overview-research.js").read_text(encoding="utf-8")
    v2_cmp = (ROOT / "static/v2/js/pages/compare.js").read_text(encoding="utf-8")
    classic = (ROOT / "static/app.js").read_text(encoding="utf-8")
    said = "Compare ranks names on scores of its own, built only from inputs every compared name has, so its numbers for this company differ from these."
    assert said in v2_over and said in classic
    assert "These are Compare's own scores, built only from inputs every compared name has." in v2_cmp
    assert "These are Compare's own scores, built only from inputs every compared name has." in " ".join(classic.split())


def test_one_score_reads_one_way_on_every_page():
    """BUG-064: the composite was "no edge either way" at 50 on Options while the Overview says 50 is a neutral
    midpoint and not a measured break-even; the long-term score was coloured at 55 and 45 on Investing and by its
    own model's bands on the Overview; two values on Investing were both called fair value without saying they differ."""
    opts = (ROOT / "static/v2/js/pages/options-panels.js").read_text(encoding="utf-8")
    inv = (ROOT / "static/v2/js/pages/investing.js").read_text(encoding="utf-8")
    dcf = (ROOT / "static/v2/js/pages/dcf.js").read_text(encoding="utf-8")
    classic = (ROOT / "static/app.js").read_text(encoding="utf-8")
    for src in (opts, classic):
        assert "no edge either way. Bullish" not in src and "50 means no edge either way" not in src
    assert "The same score the Overview shows as its short-term reading. 50 is its neutral midpoint" in opts
    assert "the same score the Overview shows as its long-term reading" in inv
    assert "tone100(s, score100(th.moderate, sc.min_possible, sc.max_possible), score100(th.cautious, sc.min_possible, sc.max_possible))" in inv
    assert "${tone100(s)}" not in inv.split("Long-term trend score")[1][:1200]
    assert "so its value differs from this range" in inv and "so the two values differ" in dcf


# ------------------------------------------------------------------ one rounding rule per figure (BUG-012)

def test_a_whole_s_parts_add_up_and_one_change_reads_one_way(tmp_path):
    got = _run(tmp_path, f"""
      const F = await import('{(V2 / "js" / "core" / "format.js").as_posix()}');
      const R = await import('{(V2 / "js" / "pages" / "retirement.js").as_posix()}');
      print(JSON.stringify({{
        split: F.wholeParts([93.5, 6.5]), three: F.wholeParts([33.4, 33.3, 33.3]), gap: F.wholeParts([60.2, null, 39.8]),
        tiles: R.splitTiles({{ equity_pct: 93.5, bond_pct: 6.5, gold_pct: 0 }}).map((t) => t[1]),
      }}));
    """)
    assert got["split"] == [94, 6] and sum(got["three"]) == 100 and got["gap"] == [60, None, 40]
    assert got["tiles"] == ["94%", "6%"]
    cmp = (ROOT / "static/v2/js/pages/compare.js").read_text(encoding="utf-8")
    assert "${num(Math.abs(x.change_pct), 1)}%" in cmp and "${num(Math.abs(x.change_pct), 0)}%" not in cmp


def test_the_breadth_note_rounds_as_the_page_does():
    """6 of 11 sectors: 54.5 in the payload. The note said 54 (Python's half to even) beside the page's 55."""
    from app.analytics import regime
    import inspect
    src = inspect.getsource(__import__("app.analytics.sectors", fromlist=["x"]))
    assert '.format(share_200)' in src and 'breadth_note = "Mixed participation ({:.0f}% above 200-day)' in src
    assert "{:.0f}".format(6 / 11 * 100) == "55"
    rs = inspect.getsource(regime)
    assert 'int(math.floor(float(breadth) + 0.5))' in rs


# ------------------------------------------------------------------ caches (the Phase 09 cache audit)

def test_signed_in_answers_are_private_and_every_api_answer_varies_on_the_cookie():
    from fastapi.testclient import TestClient
    from app import main
    from app.auth import config as auth_config
    c = TestClient(main.app)
    guest = c.get("/api/session")
    assert guest.status_code == 200 and "cookie" in guest.headers.get("vary", "").lower()
    assert "no-store" not in (guest.headers.get("cache-control") or "")
    c.cookies.set(auth_config.COOKIE_NAME, "not-a-real-session")
    signed = c.get("/api/session")
    assert signed.headers.get("cache-control") == "private, no-store" and "cookie" in signed.headers.get("vary", "").lower()
    page = c.get("/")
    assert "cookie" not in (page.headers.get("vary") or "").lower() or page.headers.get("cache-control"), "only /api/ is touched"


def test_disconnecting_or_deleting_drops_the_readers_assembled_holdings(monkeypatch):
    from app.brokerage import service, workspace
    workspace._cache["u1:core:abc"] = (0, {"holdings": [1]})
    workspace._cache["u2:core:abc"] = (0, {"holdings": [2]})
    monkeypatch.setattr(service.store, "purge_local", lambda uid: None)
    service.delete_all("u1")
    assert "u1:core:abc" not in workspace._cache and "u2:core:abc" in workspace._cache
    workspace._cache.pop("u2:core:abc", None)


def test_a_stand_in_frame_says_when_it_was_read(clean):
    idx = pd.bdate_range("2026-10-01", periods=20)
    frame = pd.DataFrame({"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": np.linspace(10, 12, 20), "Volume": 100.0}, index=idx)
    key = Y._hist_key("ZZZ", "1y", "1d")
    Y._keep_good(key, frame)
    got = Y._stand_in(key, pd.DataFrame())
    assert got.attrs.get("stand_in_since") and "stand_in_since" not in frame.attrs, "the kept frame itself is untouched"
    from app import main
    body = main._bars_body("ZZZ", got, 4)
    assert body["stale"] is True and body["stale_since"] == got.attrs["stand_in_since"]
    assert "stale" not in main._bars_body("ZZZ", frame, 4)
    from app import milo_data
    out = milo_data.price_history(lambda t, period, interval: got, lambda t: {}, "ZZZ", "1m", "daily")
    assert out["stale"] is True and got.attrs["stand_in_since"] in out["stale_note"]
    board = Y._stand_in("missing", {})
    assert board == {}


def test_the_browsers_caches_drop_failures_and_milo_hears_the_datas_age():
    js = (ROOT / "static/v2/js").as_posix()
    api = (ROOT / "static/v2/js/core/api.js").read_text(encoding="utf-8")
    assert "if (e && (e.status === 401 || e.status === 403)) cache.delete(path);" in api
    fin = (ROOT / "static/v2/js/ui/finfigs.js").read_text(encoding="utf-8")
    assert "cache.delete(url); return { __error: e };" in fin and "Date.now() - hit.at > 300000" in fin
    milo = (ROOT / "static/v2/js/ui/milo.js").read_text(encoding="utf-8")
    assert "chartCache.delete(key); return null;" in milo
    dossier = (ROOT / "static/v2/js/pages/dossier.js").read_text(encoding="utf-8")
    assert "data_as_of: (D.ticker || {}).generated_at || null" in dossier
    from app import ai
    from datetime import datetime as dt, timezone as tz
    head = ai.context_header({"focus": {"scope": "auto", "view": "overview", "ticker": "NVDA", "captured_at": "2026-10-30T14:00:00+00:00"},
                              "data_as_of": "2026-10-30T13:00:00+00:00"}, now=dt(2026, 10, 30, 14, 0, tzinfo=tz.utc))
    assert "fetched about 60 minutes before this question" in head


def test_a_part_that_raised_is_handed_back_not_kept(clean, monkeypatch):
    class T:
        def __init__(self, sym):
            pass

        @property
        def eps_trend(self):
            raise RuntimeError("Too Many Requests")
        eps_revisions = growth_estimates = earnings_estimate = revenue_estimate = None
    monkeypatch.setattr(Y.yf, "Ticker", T)
    got = Y.PROVIDER.estimates("ZZZ")
    assert got == {"eps_trend": None, "eps_revisions": None, "growth": None, "eps_estimate": None, "revenue_estimate": None}
    assert "est:ZZZ" not in Y._CACHE, "a refusal is not an hour of no estimates"
