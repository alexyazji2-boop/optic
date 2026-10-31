"""Post-demo Phase 11 (the adversarial final audit): the defects it found in the terminal and in Phase 10's own work,
each pinned. Browser checks are in the work folder's tools (phase11_*.py); TEST_RESULTS Phase 11 has the runs.

The others are pinned where their code already had tests:
- BUG-181: tests/test_health_version.py
- BUG-183 and BUG-184: tests/test_phase10_hardening.py
- BUG-185: tests/test_phase10_hardening.py
- BUG-186: tests/test_desk_freshness.py
- BUG-180: tests/milo_eval/run.py's price line
- BUG-200, BUG-201 and BUG-202 (the next report date): tests/test_next_report_date.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text()


def test_the_paper_desk_does_not_re_mark_while_the_reader_types():
    """BUG-182: the two-minute re-mark redrew the page, which took text not yet saved and moved the focus into the
    ticket's field of the same name. Found by the Phase 11 review of Phase 10's commit."""
    src = read("static/v2/js/pages/paper.js")
    assert "const editing = () => { const a = document.activeElement;" in src
    assert "&& !marking && !editing()) await mark();" in src


def test_a_search_answer_is_kept_only_for_the_directory_it_was_ranked_on(monkeypatch):
    """BUG-188: an answer finished on yesterday's rows after today's had cleared the memo was kept and served all day."""
    from app import universe
    idx = {"rows": [{"symbol": "AA", "name": "Alcoa Corp", "etf": False}, {"symbol": "AAPL", "name": "Apple Inc", "etf": False}]}
    monkeypatch.setattr(universe, "_ANSWERS", type(universe._ANSWERS)())
    monkeypatch.setattr(universe, "_PREP", {"rows": None, "prep": []})
    real = universe._prepared

    def prepared_then_the_day_turns(rows):
        out = real(rows)
        universe._PREP["rows"] = [{"symbol": "ZZ", "name": "Today's directory", "etf": False}]
        return out
    monkeypatch.setattr(universe, "_prepared", prepared_then_the_day_turns)
    got = universe.search("aa", 5, _idx=idx)
    assert got and got[0]["symbol"] == "AA"            # the reader still gets an answer
    assert not universe._ANSWERS                        # but it is not kept for the new directory
    monkeypatch.setattr(universe, "_prepared", real)
    universe.search("aa", 5, _idx=idx)
    assert len(universe._ANSWERS) == 1                  # an answer on the directory in use is kept as before


def test_a_malformed_turn_does_not_break_the_personal_blocks_check():
    """BUG-189: a history turn that was not a dict raised outside the answer's try, after the question was counted."""
    from app import main
    context = {"reader_watchlist": {"rows": [{"symbol": "NVDA"}]}, "focus": {"ticker": "NVDA"}}
    trimmed, left = main._personal_blocks_for(["junk", 7, {"role": "user", "content": "What moved NVDA today?"}], context)
    assert "reader_watchlist" not in trimmed and left == ["your watchlist"]
    kept, none = main._personal_blocks_for(["junk", {"role": "user", "content": "How is my watchlist doing?"}], context)
    assert kept is context and none == []
    trimmed2, left2 = main._personal_blocks_for(["junk", None, 3], context)
    assert "reader_watchlist" not in trimmed2 and left2 == ["your watchlist"]
    weird, _ = main._personal_blocks_for([{"role": "user", "content": ["a", "list"]}], context)
    assert "reader_watchlist" not in weird


def test_the_scorecards_inputs_are_written_out_not_printed_as_json():
    """BUG-190: the Brokerage scorecard's "Inputs and method" printed each assessment's inputs as JSON
    ('Inputs: {"stocks_assessed":3,"holdings":[...]}'). Browser check: tools/phase11_braces.py (folds opened)."""
    src = read("static/v2/js/pages/brokerage.js")
    card = src[src.index("function scorecard(s)"):src.index("function optionsRisk(o)")]
    assert "JSON.stringify" not in card
    assert "<p>Inputs:</p>${readable(a.inputs)}" in card and "<p>Weights:</p>${readable(a.weights)}" in card
    assert "const inWords = (k) => String(k).replace(/_pct$/, ' %').replace(/_/g, ' ');" in src


def test_text_taken_as_typed_asks_for_no_logo():
    """BUG-191: the palette's Open row for "nvidia" asked /api/logo/NVIDIA, a 404 in the console on every search by
    name. A listing the search named keeps its logo."""
    sym = read("static/v2/js/ui/symbols.js")
    pal = read("static/v2/js/ui/palette.js")
    assert "export function logoHTML(symbol, { lazy = true, image = true } = {})" in sym
    assert "${image && LOGO_SYM.test(sym) && !NO_LOGO.has(sym) ? `<img" in sym
    assert "logoHTML(r.symbol, { image: !r.typed })" in sym
    assert "sym: { symbol: sym, name: detail, kind, typed: !kind }" in pal


def test_the_options_readings_do_not_stay_loading_after_the_load_failed():
    """BUG-193: with the ticker's options data failed, "Loading what options are pricing" stayed for good under the
    page's stated failure. Browser check: tools/phase11_features.py's failure pass on #/NVDA/options."""
    src = read("static/v2/js/pages/options.js")
    assert "if (!D.t) return D.tErr ? '' : html`<section class=\"readings\" aria-label=\"What options are pricing\">" in src
    assert "${D.tErr ? failed('Options data', D.tErr, { retry: 'ticker' }) : ''}" in src


def test_a_503_on_an_owner_page_is_a_failure_not_a_refusal():
    """BUG-194: "The accounts database is unavailable" (503) read as "These are not yours to read" to the owner."""
    src = read("static/v2/js/pages/reports.js")
    assert "const refused = (e) => e && (e.status === 401 || e.status === 403);" in src
    assert "return failed(what, e, { retry: 'load' });" in src


def test_no_logo_is_no_content_not_a_console_error(monkeypatch, tmp_path):
    """BUG-196: every fund without a logo in a list of results was a 404, which the browser logs as "Failed to load
    resource"; 204 still fires the image's error event, so both apps keep the initial. Browser check: Phase 11's
    journey, search steps."""
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "_LOGO_DIR", str(tmp_path))
    monkeypatch.setattr(main, "_logo_fetch", lambda sym: None)
    monkeypatch.setattr(main.universe_mod, "known_symbol", lambda sym: True)
    r = TestClient(main.app).get("/api/logo/NVPS")
    assert r.status_code == 204 and r.content == b"" and r.headers["cache-control"] == "public, max-age=86400"


def test_a_level_changed_in_another_tab_rewords_this_page():
    """BUG-197: a level changed in another tab moved only this tab's sliders; the Dossier's Simple Analysis kept its old
    wording under a slider showing the new level. Browser check: tools/phase11_adversarial.py X07."""
    src = read("static/v2/js/core/prefs.js")
    assert "window.addEventListener('storage', (e) => { if (e.key === KNOW_KEY && levelOf(e.newValue)) emit('knowledge-synced'); });" in src
    dossier = read("static/v2/js/pages/dossier.js")
    assert "else if (what === 'knowledge' || what === 'knowledge-synced') paint(main, sym);" in dossier


def test_the_offline_and_refused_sentences_fit_any_subject():
    """BUG-199: "The headlines needs a connection", "The contracts is not available on this account": explain() put a
    singular verb after subjects that are mostly plural, or actions ("Saving"). Seen: tools/phase11_adversarial.py X09."""
    src = read("static/v2/js/core/api.js")
    assert "case 'offline': return `Optic needs a connection for ${what.toLowerCase()}. It will try again when you are back online.`;" in src
    assert "case 'forbidden': return `${what}: not available on this account.`;" in src
    assert "needs a connection. Optic" not in src and "is not available on this account" not in src
