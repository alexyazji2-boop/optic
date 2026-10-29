"""What a page shows (density) and how things are explained (the knowledge level) are two settings (Phase 04, D-019).

Post-demo overhaul, directive 04 section 7: "The knowledge-level slider introduced in Phase 05 should control language
complexity independently from visual information density. Do not create conflicting mode systems." Before, the
Dossier's "Show advanced analysis" switch wrote the knowledge level, so a density control also changed how Milo and
every page explained things (BUG-002). Density now has one state of its own, on Classic's key `optic.mode.v1` with
Classic's values ('simple', 'pro'), which Classic declares but no longer reads; Home's layouts open a smaller set of
panels in Simple (D-020).

The JavaScript runs in JavaScriptCore against the modules themselves; the pages were measured in headless Chrome by
~/Optic/work/post-demo-ultra-2026-10-29/tools/density.py (SIMPLICITY_AUDIT.md).
"""
import json

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
PREFS = (JS / "core/prefs.js").as_posix()


def prefs_run(tmp_path, setup, body):
    return _run(tmp_path, f"""
      {setup}
      const p = await import('{PREFS}');
      const seen = []; p.onChange((w) => seen.push(w));
      const ls = (k) => localStorage.getItem(k);
      {body}
    """)


def test_a_first_visit_is_simple_and_the_choice_is_kept_on_classics_key(tmp_path):
    got = prefs_run(tmp_path, "", "print(JSON.stringify({ d: p.density(), stored: ls('optic.mode.v1'), adv: p.advancedOn() }));")
    assert got == {"d": "simple", "stored": "simple", "adv": False}


def test_a_reader_who_had_opened_the_advanced_sections_keeps_them_once(tmp_path):
    # "Show advanced analysis" used to write the knowledge level; a reader left at Advanced still sees advanced sections
    got = prefs_run(tmp_path, "localStorage.setItem('optic.knowledge.v1', 'advanced');",
                    "print(JSON.stringify({ d: p.density(), stored: ls('optic.mode.v1') }));")
    assert got == {"d": "advanced", "stored": "pro"}


def test_density_and_the_knowledge_level_move_apart(tmp_path):
    got = prefs_run(tmp_path, "localStorage.setItem('optic.knowledge.v1', 'literate');", """
      p.setDensity('advanced');
      const a = { d: p.density(), k: ls('optic.knowledge.v1'), m: ls('optic.mode.v1'), seen: seen.slice() };
      p.setAdvancedLanguage(true);
      const b = { d: p.density(), k: ls('optic.knowledge.v1'), m: ls('optic.mode.v1'), seen: seen.slice() };
      p.setAdvanced(false);   // the Dossier's switch
      const c = { d: p.density(), k: ls('optic.knowledge.v1'), lang: p.advancedLanguageOn() };
      p.setAdvancedLanguage(false);
      const d = { d: p.density(), k: ls('optic.knowledge.v1') };
      print(JSON.stringify({ a, b, c, d }));
    """)
    assert got["a"] == {"d": "advanced", "k": "literate", "m": "pro", "seen": ["density"]}
    assert got["b"] == {"d": "advanced", "k": "advanced", "m": "pro", "seen": ["density", "knowledge"]}
    assert got["c"] == {"d": "simple", "k": "advanced", "lang": True}, "the density switch leaves Milo's level alone"
    assert got["d"] == {"d": "simple", "k": "literate"}, "turning Milo's level off returns to the rung the reader had"


def test_setting_the_same_density_again_says_nothing(tmp_path):
    got = prefs_run(tmp_path, "localStorage.setItem('optic.mode.v1', 'pro');",
                    "p.setDensity('advanced'); p.setDensity('advanced'); print(JSON.stringify({ seen }));")
    assert got == {"seen": []}


def test_the_folds_follow_density_not_the_level():
    sections = (JS / "ui/sections.js").read_text()
    assert "const rung = () => (density() === 'advanced' ? 3 : 1);" in sections
    assert "what === 'density'" in sections and "'optic.mode.v1'" in sections
    assert "knowledge()" not in sections, "a section's openness no longer reads the knowledge level"


def test_settings_has_both_controls_and_says_each_leaves_the_other_alone():
    st = (JS / "pages/settings.js").read_text()
    assert "seg('View', [['simple', 'Simple'], ['advanced', 'Advanced']], prefs.density(), 'density')" in st
    assert "prefs.setDensity(b.dataset.v2Density)" in st
    assert "prefs.setAdvancedLanguage(t.checked)" in st and "prefs.advancedLanguageOn() ? 'checked' : ''" in st
    frame = (JS / "pages/dossier-frame.js").read_text()
    assert "Milo's level is set in Settings." in frame


def home_layout(tmp_path, density, stored=None):
    return _run(tmp_path, f"""
      localStorage.setItem('optic.session.holder.v1', 'guest');
      localStorage.setItem('optic.mode.v1', '{density}');
      {f"localStorage.setItem('optic.v2.workspace.v1', {json.dumps(json.dumps(stored))});" if stored is not None else ''}
      const w = await import('{(JS / "pages/workspace.js").as_posix()}');
      const S = w._test.load();
      const L = S.layouts[S.preset] || [];
      print(JSON.stringify({{ shown: L.filter((x) => !x.hidden).map((x) => x.id), all: L.map((x) => x.id) }}));
    """)


def test_home_opens_six_panels_in_simple_and_every_panel_in_advanced(tmp_path):
    market = ["indices", "regime", "expected", "sectors", "quote", "watch", "calendar", "earnings", "priority", "news", "desk", "movers", "portfolio"]
    simple = home_layout(tmp_path, "simple")
    assert simple["shown"] == ["indices", "quote", "watch", "priority", "desk", "portfolio"]
    assert set(market) <= set(simple["all"]), "the other panels are hidden, not removed: Add panel brings each back"
    adv = home_layout(tmp_path, "pro")
    assert adv["shown"] == market and adv["all"] == simple["all"]


def test_a_layout_the_reader_changed_is_kept_whatever_the_density(tmp_path):
    mine = [{"id": "quote", "span": 12, "h": "m", "hidden": False}, {"id": "news", "span": 6, "h": "s", "hidden": False}]
    got = home_layout(tmp_path, "simple", stored={"v": 5, "preset": "market", "link": "SPY", "layouts": {"market": mine}})
    assert got["shown"][:2] == ["quote", "news"], got
