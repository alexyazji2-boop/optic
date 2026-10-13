"""Optic Desk's daily edition (docs/desk/EDITORIAL-SPEC.md).

Story clustering first: the same wire story on several sites is one report,
and repeated coverage is not independent confirmation."""
from __future__ import annotations

import pytest

from app.desk import model


# Headline pairs measured on the live wires, 2026-10-13 (276 stories in 36 hours).
SAME = [
    ("Bank of America to Pay $1.21 Billion to Settle Violations of Money Laundering, Sanctions Rules",
     "Bank of America fined $1.2 billion over money-laundering violations"),
    ("Bank of America fined $1.2 billion over money-laundering violations",
     "Bank of America fined $1.2bn over money laundering failures"),
    ("Kimberly Guilfoyle resigns as ambassador to Greece at White House's request",
     "White House asks US envoy to Greece Kimberly Guilfoyle to resign"),
    ("FBI arrests Saudi OpenAI employee who allegedly planted recording devices",
     "US indicts Saudi employee of OpenAI for allegedly bugging its offices"),
]
DIFFERENT = [
    # A short headline about a theme against three different stories on it.
    ("What could Trump's energy ceasefire mean for Ukraine?",
     "Zelenskyy accuses Russia of violating Trump's energy ceasefire as drone attacks continue"),
    ("What could Trump's energy ceasefire mean for Ukraine?",
     "Brent tops $106 after deadly Saudi airport attack, Ukraine says Russia struck energy sites"),
    ("Social Security cost-of-living adjustment for 2027 may be above average",
     "Cost of living struggles inspire 'social supermarket'"),
    ("Why Trump is going for Zelenskyy's jugular",
     "Zelenskyy accuses Russia of violating Trump's energy ceasefire as drone attacks continue"),
]


@pytest.mark.parametrize("a,b", SAME)
def test_the_same_event_across_outlets_is_one_story(a, b):
    assert model.same_story(a, b), (model.similar(a, b), a, b)


@pytest.mark.parametrize("a,b", DIFFERENT)
def test_different_pieces_on_one_theme_stay_apart(a, b):
    assert not model.same_story(a, b), (model.similar(a, b), a, b)


def test_a_cluster_counts_outlets_and_keeps_the_original():
    rows = [
        {"title": SAME[1][0], "url": "https://www.cnbc.com/a?utm=x", "source": "CNBC",
         "published": "2026-10-13T14:05:00+00:00"},
        {"title": SAME[1][1], "url": "https://www.ft.com/b", "source": "Financial Times",
         "published": "2026-10-13T13:40:00+00:00"},
        {"title": SAME[0][0], "url": "https://www.wsj.com/c", "source": "WSJ",
         "published": "2026-10-13T15:00:00+00:00"},
        {"title": "Six Flags shares decline following deadly roller coaster incident",
         "url": "https://www.cnbc.com/six", "source": "CNBC", "published": "2026-10-13T16:00:00+00:00"},
        # The same link again from a second feed of the same outlet.
        {"title": "Six Flags stock drops after roller coaster incident",
         "url": "http://cnbc.com/six/", "source": "CNBC", "published": "2026-10-13T16:10:00+00:00"},
    ]
    got = model.cluster(rows)
    assert len(got) == 2
    bofa = next(c for c in got if "Bank of America" in c["title"])
    assert bofa["copies"] == 3 and sorted(bofa["outlets"]) == ["CNBC", "Financial Times", "WSJ"]
    assert bofa["source"] == "Financial Times", "the earliest copy represents the story"
    six = next(c for c in got if "Six Flags" in c["title"])
    assert six["copies"] == 2 and six["outlets"] == ["CNBC"], "one outlet twice is still one outlet"


def test_figures_in_headlines_are_normalised():
    assert model._tokens("fined $1.21 Billion") == model._tokens("fined $1.2bn")
    assert model.canonical_url("https://www.Example.com/x/?utm_source=a#top") == "example.com/x"


# ----------------------------------------------------------------- stages
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.desk import assemble, check, edition, outline, research
from app.desk import evidence as ev_mod

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = json.loads((ROOT / "tests/fixtures/desk_bundle_2026-10-13_close.json").read_text())
ET = edition.ET


def _bundle(**edits):
    b = copy.deepcopy(BUNDLE)
    for fn in edits.get("apply", []):
        fn(b)
    return b


def _ev(b, **match):
    return next(e for e in b["evidence"] if all(e.get(k) == v for k, v in match.items()))


def test_the_real_close_of_2026_10_13_outlines_the_bank_results_and_cpi():
    o = outline.build(BUNDLE)
    evm = {e["id"]: e for e in BUNDLE["evidence"]}
    assert o["tension"]["what"] == "Consumer Price Index", "CPI the next morning is the tension"
    syms = {evm[c].get("symbol") for c in o["companies"]}
    assert {"JPM", "UNH"} <= syms, "the day's major results are in focus"
    assert {c["evidence"] for c in o["conflicts"]} == {_ev(BUNDLE, kind="earnings", symbol="JPM")["id"],
                                                       _ev(BUNDLE, kind="earnings", symbol="UNH")["id"]}
    assert 3 <= len(o["numbers"]) <= 6
    assert not o["quiet"]
    # Leaders and laggards ranked from the sector funds, not asserted.
    assert evm[o["leaders"][0]]["value"] >= evm[o["leaders"][-1]]["value"]
    assert any("consensus" in l for l in o["limits"])


def test_the_assembled_edition_passes_every_check():
    o = outline.build(BUNDLE)
    ed = assemble.build(BUNDLE, o)
    r = check.run(ed, BUNDLE, o)
    assert r["ok"], r["errors"]
    assert r["stats"]["numbers_checked"] >= 30
    assert ed["voice"] == "assembled"


def test_a_quiet_day_is_a_short_edition_not_a_padded_one():
    def calm(b):
        b["evidence"] = [e for e in b["evidence"] if e["kind"] not in ("earnings", "company", "news")]
        for e in b["evidence"]:
            if e["kind"] in ("index", "sector") and e.get("value") is not None:
                e["value"] = round(e["value"] / 20, 3)
            if (e.get("compare") or {}).get("change") is not None:
                e["compare"]["change"] = round(e["compare"]["change"] / 20, 3)
            if e["kind"] in ("fx", "commodity", "credit") and e.get("value") is not None:
                e["value"] = round(e["value"] / 20, 3)
    b = _bundle(apply=[calm])
    o = outline.build(b)
    assert o["quiet"] and o["target_words"][1] <= 650
    ed = assemble.build(b, o)
    r = check.run(ed, b, o)
    assert r["ok"], r["errors"]
    assert r["stats"]["words"] < 800


def test_conflicting_consensus_figures_block_a_beat_or_miss_call():
    o = outline.build(BUNDLE)
    jpm = _ev(BUNDLE, kind="earnings", symbol="JPM")
    draft = assemble.build(BUNDLE, o)
    draft["sections"][0]["paragraphs"].append({"text": "JPMorgan missed expectations.", "cites": [jpm["id"]]})
    errs = check.run(draft, BUNDLE, o)["errors"]
    assert any("consensus figures disagree" in e for e in errs), errs
    draft["sections"][0]["paragraphs"][-1]["text"] = (
        "Whether JPMorgan beat depends on which of the free data's two consensus figures is used: they differ.")
    assert check.run(draft, BUNDLE, o)["ok"]


def test_a_number_from_a_different_report_is_refused():
    """The wires carried 'WSJ Dollar Index Rises 0.21%' while DXY fell 0.38%:
    two indexes, two numbers. A paragraph citing DXY may not borrow the WSJ's."""
    o = outline.build(BUNDLE)
    dxy = _ev(BUNDLE, symbol="DX-Y.NYB")
    draft = assemble.build(BUNDLE, o)
    draft["sections"][0]["paragraphs"].append({"text": "The dollar rose 0.21%.", "cites": [dxy["id"]]})
    errs = check.run(draft, BUNDLE, o)["errors"]
    assert any("0.21% is not a figure" in e for e in errs), errs


def test_units_dates_options_dealers_and_advice():
    o = outline.build(BUNDLE)
    tnx = _ev(BUNDLE, symbol="^TNX")
    opt = next(e for e in BUNDLE["evidence"] if e["kind"] == "options" and (e.get("detail") or {}).get("expiry"))
    unrate = _ev(BUNDLE, symbol="UNRATE")
    cases = [
        ("The 10-year yield fell 2.3% on the day.", [tnx["id"]], "written as a percent"),
        ("SPY options price a move of about 0.5%, the straddle.", [opt["id"]], "without its expiry"),
        ("Options are pricing the earnings move: the expected move to {} is about {:.1f}%.".format(
            opt["detail"]["expiry"], opt["value"]), [opt["id"]], "alongside earnings"),
        ("Dealers are short gamma here.", [opt["id"]], "dealer positioning written as fact"),
        ("You should buy the dip in chip stocks.", [tnx["id"]], "instruction to trade"),
        ("Unemployment was 4.2% in October.", [unrate["id"]], "describes September"),
        ("Yields fell — sharply.", [tnx["id"]], "em dash"),
        ("This is HUGE for banks.", [tnx["id"]], "capitals for emphasis"),
    ]
    for text, cites, want in cases:
        d = assemble.build(BUNDLE, o)
        d["sections"][0]["paragraphs"] = [{"text": text, "cites": cites}]
        errs = check.run(d, BUNDLE, o)["errors"]
        assert any(want in e for e in errs), (text, errs)
    d = assemble.build(BUNDLE, o)
    d["sections"][0]["paragraphs"] = [{"text": "The 10-year yield fell about 2.3bp to {:.2f}%.".format(tnx["value"]),
                                      "cites": [tnx["id"]]}]
    assert check.run(d, BUNDLE, o)["ok"]


def test_stale_figures_are_not_todays():
    def age(b):
        for e in b["evidence"]:
            if e.get("symbol") == "UNRATE":
                e["stale"] = True
    b = _bundle(apply=[age])
    o = outline.build(b)
    d = assemble.build(b, o)
    unrate = _ev(b, symbol="UNRATE")
    d["sections"][0]["paragraphs"] = [{"text": "Today's unemployment rate is 4.2%.", "cites": [unrate["id"]]}]
    errs = check.run(d, b, o)["errors"]
    assert any("as today's" in e for e in errs), errs


class _Session:
    @staticmethod
    def market_holidays(year):
        from datetime import date
        return {date(2026, 11, 26): "Thanksgiving"}

    @staticmethod
    def last_regular_close(when):
        when = when.astimezone(ET)
        day = when.date()
        for _ in range(10):
            close = datetime(day.year, day.month, day.day, 16, 0, tzinfo=ET)
            if day.weekday() < 5 and day not in _Session.market_holidays(day.year) and close <= when:
                return close
            day = day - timedelta(days=1)
            when = datetime(day.year, day.month, day.day, 23, 59, tzinfo=ET)
        return None

    @staticmethod
    def state(now=None):
        return {"phase": "after", "label": "After hours"}


def test_slots_follow_the_market_calendar():
    t = lambda *a: datetime(*a, tzinfo=ET)
    assert edition.due_slot(t(2026, 10, 13, 7, 0), _Session) is None
    assert edition.due_slot(t(2026, 10, 13, 9, 0), _Session) == "premarket"
    assert edition.due_slot(t(2026, 10, 13, 17, 0), _Session) == "close"
    assert edition.due_slot(t(2026, 10, 17, 11, 0), _Session) == "closed", "a Saturday"
    assert edition.due_slot(t(2026, 11, 26, 11, 0), _Session) == "closed", "Thanksgiving"
    assert edition.due_slot(t(2026, 11, 26, 9, 0), _Session) is None
    nxt = edition.next_due(t(2026, 10, 16, 17, 0), _Session)
    assert nxt["slot"] == "closed" and nxt["key"].startswith("2026-10-17"), nxt
    # A close edition's news starts at the previous session's close.
    since = ev_mod.news_window_start(t(2026, 10, 13, 17, 0), "close", _Session)
    assert since == t(2026, 10, 12, 16, 0)
    since = ev_mod.news_window_start(t(2026, 10, 14, 8, 15), "premarket", _Session)
    assert since == t(2026, 10, 13, 16, 0)
    since = ev_mod.news_window_start(t(2026, 10, 19, 8, 15), "premarket", _Session)
    assert since == t(2026, 10, 16, 16, 0), "Monday morning reads from Friday's close"


def _writer_returning(*drafts):
    calls = []

    def writer(o, shown, errors, prev):
        calls.append(errors)
        d = drafts[min(len(calls) - 1, len(drafts) - 1)]
        return (copy.deepcopy(d(o)) if callable(d) else d), {"cost_usd": 0.1, "model": "test"}
    writer.calls = calls
    return writer


def test_a_good_draft_is_published_as_written():
    w = _writer_returning(lambda o: assemble.build(BUNDLE, o))
    out = edition.compose(BUNDLE, w)
    assert out["voice"] == "written" and out["check"]["ok"] and len(w.calls) == 1


def test_a_bad_draft_gets_one_repair():
    def bad(o):
        d = assemble.build(BUNDLE, o)
        d["sections"][0]["paragraphs"][0]["text"] += " Stocks rose 9.99%."
        return d
    w = _writer_returning(bad, lambda o: assemble.build(BUNDLE, o))
    out = edition.compose(BUNDLE, w)
    assert out["voice"] == "written" and len(w.calls) == 2
    assert w.calls[1] and any("9.99%" in e for e in w.calls[1]), "the repair is told what was wrong"
    assert out["check"]["first_errors"]


def test_two_bad_drafts_publish_the_assembled_edition_and_say_why():
    def bad(o):
        d = assemble.build(BUNDLE, o)
        d["headline"] = "Markets mixed today"
        return d
    w = _writer_returning(bad, bad)
    out = edition.compose(BUNDLE, w)
    assert out["voice"] == "assembled" and out["check"]["ok"]
    assert any("generic" in e for e in out["check"]["draft_refused"])


def test_no_model_means_the_assembled_edition():
    out = edition.compose(BUNDLE, None)
    assert out["voice"] == "assembled" and out["check"]["ok"] and out["calls"] == []
    cited = set()
    for _, u in check.units(out["edition"]):
        cited |= set(u.get("cites") or [])
    kept = {e["id"] for e in out["evidence"]}
    assert cited <= kept, "every source a reader sees beside a claim resolves"


class _Provider:
    def __init__(self, fail=()):
        self.fail = set(fail)

    def batch_history(self, syms, period="1y", interval="1d"):
        if "prices" in self.fail:
            raise RuntimeError("feed down")
        return {}

    def earnings_history(self, t):
        return []


def _sources(fail=()):
    def boom(*a, **k):
        raise RuntimeError("feed down")
    return edition.Sources(
        provider=_Provider(fail), macro=boom if "macro" in fail else (lambda: {}),
        fred_series=lambda code: {}, events=boom if "calendar" in fail else (lambda: {"events": []}),
        earnings_week=lambda: {}, wires=boom if "wires" in fail else (lambda: []), official=lambda: [],
        rate_path=lambda ev: {"available": False, "reason": "no quote"}, index_surface=lambda s: None,
        quotes=lambda syms: {}, session_mod=_Session, sectors=[], themes=[])


def test_missing_feeds_are_recorded_and_named_in_the_edition(tmp_path, monkeypatch):
    monkeypatch.setattr(edition, "DB_PATH", str(tmp_path / "e.db"))
    now = datetime(2026, 10, 13, 17, 0, tzinfo=ET)
    b = edition.gather(_sources(fail=("prices", "macro", "wires")), "close", now)
    failed = {c["leg"] for c in b["coverage"] if not c["ok"]}
    assert {"prices", "macro", "wires"} <= failed
    o = outline.build(b, now)
    assert any("Not available for this edition: prices" in l for l in o["limits"])


def test_one_edition_per_slot_and_a_page_load_never_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(edition, "DB_PATH", str(tmp_path / "e.db"))
    monkeypatch.setattr(edition, "gather", lambda src, slot, now=None: copy.deepcopy(BUNDLE))
    now = datetime(2026, 10, 13, 17, 0, tzinfo=ET)
    claims = []
    first = edition.publish(_sources(), "close", now=now, claim=lambda k: claims.append(k) or True)
    assert first["status"] == "assembled" and first["metrics"]["check"]["ok"]
    again = edition.publish(_sources(), "close", now=now, claim=lambda k: claims.append(k) or True)
    assert again.get("skipped") == "already published" and claims == ["2026-10-13:close"]
    refused = edition.publish(_sources(), "premarket", now=now, claim=lambda k: False)
    assert refused.get("skipped", "").startswith("claimed")
    served = edition.served(now + timedelta(minutes=5), _Session)
    assert served["available"] and served["is_current"] and served["is_today"]
    # The next morning, before the premarket edition: yesterday's is not today's.
    later = edition.served(datetime(2026, 10, 14, 7, 0, tzinfo=ET), _Session)
    assert later["available"] and not later["is_today"] and "2026-10-13" in later["freshness"]
    assert later["next"]["slot"] == "premarket"


def test_the_routes_read_and_only_the_guarded_one_writes():
    src = (ROOT / "app/main.py").read_text()
    get = src[src.index('@app.get("/api/desk/edition")'):src.index('@app.get("/api/desk/editions")')]
    assert "publish" not in get and "served(" in get
    post = src[src.index('@app.post("/api/desk/edition/publish")'):]
    post = post[:post.index("\n\n\n")]
    assert "_write_guard(request)" in post
    assert 'DESK_EDITION_AUTO = os.environ.get("DESK_EDITION_AUTO", "false")' in src


def test_the_read_page_and_home_carry_the_edition():
    js = (ROOT / "static/app.js").read_text()
    assert "<div id=\"desk-edition-host\"></div>" in js
    assert "function deskCites(u)" in js and 'rel="noopener noreferrer"' in js
    assert 'data-desk-ask="${esc(sid)}"' in js and "ctx.desk_section = STATE.deskAsk" in js
    assert "Read the full edition &rarr;" in js
    assert "Latest edition, ${esc(deskWhen(ed.date))}" in js, "an older edition says so on Home"


# --------------------------------------------------------------- research

def test_milo_picks_evidence_by_the_kind_of_question():
    assert research.intent("Is Micron a good long-term investment at this price?", None, "MU") == "long_term"
    assert research.intent("What should I watch in JPM's earnings on Tuesday?", None, "JPM") == "pre_earnings"
    assert research.intent("Is NVDA worth trading intraday right now?", None, "NVDA") == "day_trade"
    assert research.intent("Does the AAPL setup hold for a swing?", None, "AAPL") == "swing"
    assert research.intent("What does CPI mean for yields?", None, None) == "macro"
    assert research.intent("Explain this", None, None, {"key": "2026-10-13:close", "section": "why"}) == "desk"
    assert research.intent("thoughts?", "long", "MU") == "long_term", "the saved horizon decides when words do not"


class _Fin:
    def __init__(self, sector="Technology", industry="Semiconductors"):
        self.sector, self.industry = sector, industry

    def financials(self, t):
        rows = lambda **r: {"periods": ["2025-08-31", "2024-08-31"], "rows": r}
        return {"income_annual": rows(**{"Total Revenue": [37.4e9, 25.1e9], "Gross Profit": [14.9e9, 5.6e9],
                                        "Operating Income": [9.8e9, 1.3e9], "Net Income": [8.5e9, 0.8e9],
                                        "Diluted Average Shares": [1.13e9, 1.12e9]}),
                "cashflow_annual": rows(**{"Operating Cash Flow": [17.5e9, 8.5e9], "Capital Expenditure": [-15.9e9, -8.4e9],
                                          "Free Cash Flow": [1.7e9, 0.1e9], "Repurchase Of Capital Stock": [-0.3e9, -0.4e9],
                                          "Stock Based Compensation": [0.9e9, 0.8e9]}),
                "balance_annual": rows(**{"Total Debt": [15.3e9, 13.4e9], "Cash And Cash Equivalents": [9.6e9, 8.1e9]})}

    def quote(self, t):
        return {"price": 100.0, "sector": self.sector, "industry": self.industry, "trailing_pe": 13.2,
                "forward_pe": 8.1, "market_cap": 1.1e11, "as_of": "2026-10-13T20:00:00+00:00"}


def test_a_long_term_pack_measures_capex_against_free_cash_flow():
    p = research.build("Is it a good long-term investment?", "MU", research.Deps(provider=_Fin()), kind="long_term")
    got = {i["label"]: i.get("value") for i in p["items"]}
    assert got["Capex as a share of revenue"] == pytest.approx(42.5, abs=0.1)
    assert got["Capex growth"] == pytest.approx(89.3, abs=0.1)
    assert got["Free cash flow as a share of net income"] == pytest.approx(20, abs=1)
    assert got["Change in diluted share count"] == pytest.approx(0.89, abs=0.01)
    assert got["Forward P/E"] == 8.1
    assert all(i.get("source") and i.get("period") for i in p["items"] if i.get("value") is not None)
    assert any("multiple alone" in n for n in p["not_available"])


def test_a_bank_gets_no_free_cash_flow():
    p = research.build("Long term?", "JPM", research.Deps(provider=_Fin("Financial Services", "Banks - Diversified")),
                       kind="long_term")
    labels = {i["label"] for i in p["items"]}
    assert "Free cash flow" not in labels and "Capex as a share of revenue" not in labels
    assert any("not meaningful for a bank" in n for n in p["not_available"])


def test_a_desk_question_carries_the_section_and_rereads_moved_prices(tmp_path, monkeypatch):
    monkeypatch.setattr(edition, "DB_PATH", str(tmp_path / "e.db"))
    out = edition.compose(BUNDLE, None)
    edition.keep("2026-10-13:close", {**out["edition"], "evidence": out["evidence"], "date": "2026-10-13",
                                       "slot_label": "After the close", "cutoff": BUNDLE["cutoff"]}, "assembled", {})

    class P:
        def batch_quote(self, syms):
            return {s: {"last": 101.0, "prev_close": 100.0, "as_of": "2026-10-14T14:00:00+00:00"} for s in syms}

    sec = next(s["id"] for s in out["edition"]["sections"] if s["id"] == "focus")
    p = research.build("Is this right?", None, research.Deps(provider=P(), desk_load=edition.load),
                       desk_section={"key": "2026-10-13:close", "section": sec})
    assert p["intent"] == "desk"
    assert p["items"][0]["group"] == "desk" and "Optic Desk 2026-10-13" in p["items"][0]["label"]
    moved = [i for i in p["items"] if "Now: +1.00% on the day" in (i.get("text") or "")]
    assert moved, "a price the section cites is read again, so Milo can say what changed"


def test_a_slow_source_is_skipped_and_named(monkeypatch):
    import time as _t
    monkeypatch.setattr(research, "TIME_BUDGET_SECONDS", 0.2)

    class Slow(_Fin):
        def financials(self, t):
            _t.sleep(1.0)
            return {}
    p = research.build("long term", "MU", research.Deps(provider=Slow()), kind="long_term")
    assert any("skipped" in m for m in p["missing"])


def test_milo_is_told_how_to_use_the_research():
    from app import ai
    assert "Choose the evidence by the question" in ai.SYSTEM_PROMPT
    assert "Lead with the assessment" in ai.SYSTEM_PROMPT
    assert "Optic Desk is analysis, not a source" in ai.SYSTEM_PROMPT
    order = ai._ORDER_BASE
    assert order.index("desk_section") < order.index("quote") and order.index("research") < order.index("quote")
    src = (ROOT / "app/main.py").read_text()
    assert "context = await _with_research(history, context, horizon)" in src
