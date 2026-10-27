"""Milo reads every compared name's figures, the ones the table shows.

Seen on 26 October 2026: asked about an NVDA and MSFT comparison, Milo named
the leaders correctly and said the scores do not predict returns, then said it
lacked MSFT's underlying figures while the table beside it showed them. The
page's context carried the tickers, the headline and the ranks and none of the
rows. The fixture is that comparison as /api/compare answered it that evening
(performance series cut to five points)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app import ai
from tests.test_frontend_v2_stage0 import V2, _run

FIX = Path(__file__).parent / "fixtures" / "compare_NVDA_MSFT_2026-10-26.json"


def _context(tmp_path):
    return _run(tmp_path, f"""
      const c = await import('{(V2 / "js/pages/compare.js").as_posix()}');
      const payload = {FIX.read_text()};
      print(JSON.stringify({{ ctx: c.miloCompare(payload), none: c.miloCompare({{ available: false }}) }}));
    """)


def test_every_name_arrives_with_the_same_figures(tmp_path):
    got = _context(tmp_path)
    ctx = got["ctx"]
    assert got["none"] is None
    rows = {r["ticker"]: r for r in ctx["rows"]}
    assert set(rows) == {"NVDA", "MSFT"}
    keys = {m["key"] for m in ctx["metrics"]}
    for sym, r in rows.items():
        assert set(r["values"]) | set(r["not_available"]) == keys, sym
    payload = json.loads(FIX.read_text())
    msft = next(r for r in payload["rows"] if r["ticker"] == "MSFT")
    assert rows["MSFT"]["values"]["rs_vs_spy"] == round(msft["rs_vs_spy"], 3)
    assert rows["MSFT"]["values"]["forward_pe"] == round(msft["forward_pe"], 3)


def test_units_lookbacks_scores_and_limits_are_said(tmp_path):
    ctx = _context(tmp_path)["ctx"]
    by = {m["key"]: m for m in ctx["metrics"]}
    assert by["rs_vs_spy"]["label"] == "Versus SPY, 21 sessions" and by["rs_vs_spy"]["better"] == "higher"
    assert by["cagr_5y_pct"]["label"].endswith("per year") and by["forward_pe"]["unit"] == "times expected earnings"
    assert {h["id"] for h in ctx["horizons"]} == {"swing", "position", "longterm"}
    assert all(h["built_from"] for h in ctx["horizons"])
    for hid, ranks in ctx["scores"].items():
        assert {x["ticker"] for x in ranks} == {"NVDA", "MSFT"}, hid
    assert ctx["scores"]["longterm"][0]["ticker"] == "NVDA" and ctx["scores"]["swing"][0]["ticker"] == "MSFT"
    assert ctx["computed_at"].startswith("2026-10-27T02:44")
    assert "not shown that they predict future returns" in ctx["limits"]


def test_a_missing_figure_says_why(tmp_path):
    got = _run(tmp_path, f"""
      const c = await import('{(V2 / "js/pages/compare.js").as_posix()}');
      const p = {FIX.read_text()};
      p.rows[0].forward_pe = null; p.rows[0].why_na = {{ forward_pe: 'no earnings estimate' }}; p.rows[1].iv_pct = null;
      const x = c.miloCompare(p);
      print(JSON.stringify(x.rows.map((r) => r.not_available)));
    """)
    assert got[0]["forward_pe"] == "no earnings estimate"
    assert got[1]["iv_pct"] == "not reported by the feed"


def test_it_fits_milos_section_cap_for_four_names(tmp_path):
    got = _run(tmp_path, f"""
      const c = await import('{(V2 / "js/pages/compare.js").as_posix()}');
      const p = {FIX.read_text()};
      const more = (t) => Object.assign({{}}, p.rows[0], {{ ticker: t, name: t + ' Incorporated Holdings' }});
      p.rows = [...p.rows, more('AMD'), more('AVGO')]; p.tickers = p.rows.map((r) => r.ticker);
      for (const h of Object.keys(p.ranks)) p.ranks[h] = [...p.ranks[h], {{ ticker: 'AMD', score: 40, inputs: [5, 5] }}, {{ ticker: 'AVGO', score: 30, inputs: [5, 5] }}];
      print(JSON.stringify(c.miloCompare(p)));
    """)
    body, slimmed = ai._fit_section(ai._prune(got), ai.CONTEXT_SECTION_CAP)
    assert body is not None and slimmed is False, len(json.dumps(got))
    assert len(ai._prune(got)["rows"]) == 4


def test_the_model_request_carries_both_names_figures(tmp_path):
    """The request Milo would send, built and read, never sent."""
    ctx = _context(tmp_path)["ctx"]
    hist = [{"role": "user", "content": "Why does MSFT lead the swing and position setups while NVDA leads the "
                                        "long-term trend? Which figures explain the disagreement?"}]
    kw, meta = ai.build_chat_request(hist, context={"view": "compare", "compare": ctx,
                                                    "focus": {"scope": "auto", "view": "compare"}})
    assert "compare" in meta["context"]["kept"] and "compare" not in meta["context"]["slimmed"]
    def texts(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            for x in v.values():
                yield from texts(x)
        elif isinstance(v, list):
            for x in v:
                yield from texts(x)
    blob = "\n".join(texts(kw))
    payload = json.loads(FIX.read_text())
    for r in payload["rows"]:
        assert '"ticker":"{}"'.format(r["ticker"]) in blob
        assert '"rs_vs_spy":{}'.format(round(r["rs_vs_spy"], 3)) in blob, r["ticker"]
    assert "predict future returns" in blob


def test_named_compared_tickers_are_not_fetched_again(monkeypatch, tmp_path):
    import app.main as m
    fetched = []
    monkeypatch.setattr(m, "_swing_snapshot", lambda sym, *a, **k: fetched.append(sym) or {})
    ctx = {"view": "compare", "compare": _context(tmp_path)["ctx"], "focus": {"scope": "auto"}}
    out = asyncio.run(m._augment_chat_context_lookups(
        [{"role": "user", "content": "Why does MSFT lead NVDA on the swing setup?"}], ctx))
    assert fetched == [] and "auto_loaded" not in out
    assert out["compare"]["rows"], "the comparison is still the context"
