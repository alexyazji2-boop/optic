"""Three levels, and the five stored before them (Pass 1, 2026-11-09; decision card A).

Every value a browser or an account may hold from before (Phase 05's five, and the ids before Phase 05) reads as one
of Beginner, Intermediate or Advanced, in the browser (core/prefs.js, run in JavaScriptCore against the module itself)
and on the server (app/knowledge.py, app/auth/store.py), and only the three are written from now on. The server's
five wording tiers stay: each of the three writes at its own tier of the same name. The screens' level matrix and
Show more are driven in a real browser in tests/e2e/test_pass1_journeys.py; the contracts that keep them wired are
read here, as this project reads client contracts (tests/test_ui_refactor.py)."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import db, knowledge
from app.auth import config, store
from tests.test_v2_density import prefs_run

client = TestClient(main.app)
GOOD = "tungsten-carbide-9"
JS = main.STATIC_DIR / "v2" / "js"
MAP = {"new": "beginner", "beginner": "beginner", "intermediate": "intermediate", "advanced": "advanced", "expert": "advanced"}


# ------------------------------------------------------------------ the browser's copy

@pytest.mark.parametrize("stored,expected", sorted(MAP.items()) + [("simple", "beginner"), ("literate", "intermediate"),
                                                                   ("professional", "advanced"), ("adaptive", "intermediate")])
def test_a_stored_level_reads_as_one_of_three_and_is_rewritten_once(tmp_path, stored, expected):
    got = prefs_run(tmp_path, f"localStorage.setItem('optic.knowledge.v1', '{stored}');", """
      const level = p.level(), after = ls('optic.knowledge.v1'), index = p.levelIndex();
      print(JSON.stringify({ level, after, index, ids: p.LEVEL_IDS }));
    """)
    assert got["level"] == expected and got["after"] == expected
    assert got["ids"] == ["beginner", "intermediate", "advanced"] and got["index"] == got["ids"].index(expected)


@pytest.mark.parametrize("value,written", [("new", "beginner"), ("expert", "advanced"), ("beginner", "beginner"), ("advanced", "advanced")])
def test_only_the_three_are_written(tmp_path, value, written):
    got = prefs_run(tmp_path, "", f"p.setKnowledge('{value}'); print(JSON.stringify({{ k: ls('optic.knowledge.v1') }}));")
    assert got["k"] == written


def test_an_unknown_value_reads_as_the_default_and_a_first_visit_is_intermediate(tmp_path):
    got = prefs_run(tmp_path, "localStorage.setItem('optic.knowledge.v1', 'zzz');", "print(JSON.stringify({ k: p.level() }));")
    assert got["k"] == "intermediate"


# ------------------------------------------------------------------ the server's copy

@pytest.mark.parametrize("stored,expected", sorted(MAP.items()))
def test_the_server_maps_each_stored_level_to_three(stored, expected):
    assert knowledge.three(stored) == expected
    # and the wording tier stays the server's own: each of the three is its own tier
    assert knowledge.normalise(expected) == expected


def test_the_catalogue_offers_three_and_keeps_the_five_tiers():
    cat = client.get("/api/knowledge/modes").json()
    assert cat["levels"] == ["beginner", "intermediate", "advanced"]
    assert [m["id"] for m in cat["modes"]] == knowledge.ORDER


@pytest.fixture
def signed_in(accounts):
    client.cookies.clear()
    client.post("/api/auth/register", json={"first_name": "A", "last_name": "B", "email": "lv@example.com",
                                            "password": GOOD, "confirm_password": GOOD})
    yield client.cookies.get(config.CSRF_COOKIE)
    client.cookies.clear()


@pytest.mark.parametrize("stored,expected", sorted(MAP.items()))
def test_an_accounts_level_stored_before_reads_as_three(signed_in, stored, expected):
    uid = store.get_user_by_email("lv@example.com")["id"]
    db.execute("INSERT INTO user_preferences (user_id, updated_at) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING", (uid, db.utcnow()))
    db.execute("UPDATE user_preferences SET knowledge_level = ? WHERE user_id = ?", (stored, uid))   # as Phase 05 wrote it
    assert client.get("/api/auth/preferences").json()["preferences"]["knowledge_level"] == expected
    assert client.get("/api/auth/me").json()["preferences"]["knowledge_level"] == expected


@pytest.mark.parametrize("sent,written", sorted(MAP.items()))
def test_an_account_is_written_only_the_three(signed_in, sent, written):
    r = client.patch("/api/auth/preferences", headers={"X-Optic-CSRF": signed_in}, json={"knowledge_level": sent})
    assert r.json()["preferences"]["knowledge_level"] == written
    uid = store.get_user_by_email("lv@example.com")["id"]
    assert db.row("SELECT knowledge_level FROM user_preferences WHERE user_id = ?", (uid,))["knowledge_level"] == written


# ------------------------------------------------------------------ the contracts that keep the screens wired

def test_one_level_control_with_real_buttons_and_announced_state():
    lc = (JS / "ui" / "levelcontrol.js").read_text()
    assert 'role="group" aria-labelledby="${id}-q"' in lc and 'aria-pressed="${lv === now}"' in lc
    assert "How should Optic speak to you?" in lc and "announce(" in lc
    for page in ("workspace.js", "dossier.js"):
        src = (JS / "pages" / page).read_text()
        assert "levelControl({ id:" in src, page
        assert "data-v2-adv-toggle" not in src and "levelSlider(" not in src, "the overlapping controls are retired on " + page


def test_show_more_is_a_button_that_says_whether_it_is_open():
    sm = (JS / "ui" / "showmore.js").read_text()
    assert '<button type="button" class="btn btn-sm" data-v2-show-more="${id}" aria-expanded="false"' in sm


def test_the_milo_prompts_and_their_fallbacks():
    from pathlib import Path
    mp = (JS / "ui" / "miloprompt.js").read_text()
    for words in ("'Why did my holdings move today?'", "'Why did the names I follow move today?'", "'Why did the market move today?'",
                  "`Why is ${shortName(name) || String(sym || '').toUpperCase()} moving today?`"):
        assert words in mp
    assert "openMilo({ question: ask.question, opener, about: ask.about, symbol: ask.symbol || '', figures: ask.figures || null, send: true })" in mp
    assert "go(`#/signin?next=${encodeURIComponent(location.hash || '#/')}`)" in mp and "sessionStorage" in mp
    assert Path(main.STATIC_DIR / "v2" / "js" / "ui" / "milo.js").read_text().count("mode: prefs.knowledge()") == 2, \
        "both Milo requests carry the reader's level"


def test_show_more_scrolls_smoothly_then_focuses_without_a_second_scroll():
    # Focus with preventScroll: false, and the swap keeping its place, moved the page in one frame: 1,335 px on AAPL at
    # Beginner, 1440 x 900 (gauntlet, 2026-11-10). The opened panel is scrolled to smoothly, then focused.
    sm = (JS / "ui" / "showmore.js").read_text()
    assert "target.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' })" in sm
    assert "focus.focus({ preventScroll: true })" in sm
    ov = (JS / "pages" / "dossier.js").read_text()
    branch = ov[ov.index("const more = e.target.closest('[data-v2-show-more]');"):ov.index("const a = e.target.closest('[data-v2-answer]');")]
    assert "revealOpened(el)" in branch and "preventScroll: false" not in branch
    assert "advMoved" not in branch, "Show more opens a section under the simple view; it never swaps the view"
    assert "Opened. Your level is unchanged." in branch
    ws = (JS / "pages" / "workspace.js").read_text()
    branch = ws[ws.index("if ((b = t('[data-v2-show-more]')))"):ws.index("if ((b = t('[data-ws-preset]')))")]
    assert "revealOpened(" in branch and "preventScroll: false" not in branch
    assert "Your level is unchanged." in branch


def test_show_less_closes_one_panel_and_gives_focus_back_to_its_show_more():
    """Round-one corrections, 2026-11-10: nothing offered Show less, so the only way to put a panel back was to change
    the level, which closed everything else too. Show less removes that one id, repaints, and focuses its stub; the
    level is never written by either handler."""
    sm = (JS / "ui" / "showmore.js").read_text()
    assert "remove: (id) => open.delete(id)" in sm
    assert '<button type="button" class="btn btn-sm" data-v2-show-less="${id}" aria-expanded="true" aria-label="${label}: ${title}">${label}</button>' in sm
    assert "sub = 'Each opens on its own; your level stays as it is.'" in sm
    ov = (JS / "pages" / "dossier.js").read_text()
    branch = ov[ov.index("const less = e.target.closest('[data-v2-show-less]');"):ov.index("const a = e.target.closest('[data-v2-answer]');")]
    assert "OPEN.remove(id); paint(main, sym);" in branch and "revealOpened($(`[data-v2-show-more=\"${id}\"]`, main));" in branch
    assert "Closed. Your level is unchanged." in branch
    ws = (JS / "pages" / "workspace.js").read_text()
    branch = ws[ws.index("if ((b = t('[data-v2-show-less]')))"):ws.index("if ((b = t('[data-ws-preset]')))")]
    assert "OPEN.remove(id); paintAll();" in branch and "revealOpened($(`[data-v2-show-more=\"${id}\"]`, root));" in branch
    assert "${lessOf(x) ? lessButton(lessOf(x), p.title) : ''}" in ws, "an opened Home panel carries Show less in its header"
    code = "\n".join(line.split("//")[0] for line in branch.splitlines())   # the comments say "level" on purpose
    assert "prefs." not in code and "Level(" not in code, "Show less never touches the level"


def test_each_advanced_section_has_its_own_show_more_below_advanced():
    """One stub opened the whole advanced analysis as one block, so "Each opens on its own" was not true of it. Each
    section now has a stable id and opens alone, under the simple analysis, with its Show less."""
    ov = (JS / "pages" / "dossier.js").read_text()
    assert "['advanced', 'Advanced analysis'" not in ov and "OPEN.has('advanced')" not in ov
    parts = ov[ov.index("function advParts(sym, c, fund) {"):ov.index("/** What Show more opened, with its Show less under it. */")]
    ids = re.findall(r"\['(adv:[a-z]+)'", parts)
    assert ids == ["adv:questions", "adv:score", "adv:stats", "adv:record", "adv:combined", "adv:read", "adv:changed", "adv:next",
                   "adv:rest", "adv:filings", "adv:method"], ids
    assert "...parts.filter((x) => !OPEN.has(x.id)).map((x) => [x.id, x.title, x.blurb])," in ov, "unopened sections are stubs"
    assert "${parts.filter((x) => OPEN.has(x.id)).map((x) => opened(x.id, x.title, x.body))}" in ov, "opened ones are drawn alone"
    assert '<div data-v2-ov-panel="${id}">${body}<p class="sm-less">${lessButton(id, title)}</p></div>' in ov
    # the other panels Show more opens on the Overview carry Show less too, and only when Show more opened them
    for words in ("opened('cases', 'Bull and bear case'", "opened('thesis', 'Your thesis check'", "opened('investigate', 'Investigate this company'",
                  "opened('timeline', 'Company events'", "lessButton('thesis:edit', 'Your thesis check')"):
        assert words in ov, words
    tc = (JS / "pages" / "thesis.js").read_text()
    assert "export function setThesisEdit(on, more = '', less = '')" in tc and "${TC.canEdit ? TC.less : ''}" in tc


def test_a_spent_allowance_is_said_from_the_allowance_not_only_from_a_failed_send():
    # A spent free account (evaluation copy, 2026-11-10) opened Milo to an "Ask about AAPL" box and a dead Send with no
    # sentence; the reason came only after a 429. The note and the placeholder are painted from the allowance itself.
    mi = (JS / "ui" / "milo.js").read_text()
    line = mi[mi.index("function allowanceLine()"):mi.index("async function loadAllowance()")]
    assert "return b.kind === 'spent' ? b.text : '';" in line
    form = mi[mi.index("function paintForm()"):mi.index("const draw = (el, tpl)")]
    assert "ta.placeholder = b && b.kind === 'spent' ? b.short : placeholder();" in form
    assert "ta.disabled = !!b && b.kind !== 'spent';" in form, "the reader may still draft"
    assert "send.disabled = S.busy || !!b;" in form
    assert "$('#milo-allow', h); if (al) al.textContent = !S.busy ? allowanceLine()" in form
    assert "short: `Today's ${a.allowed} questions are used${at ? `; the next one frees at ${at}` : ''}`" in mi
    assert "Milo could not answer. Your question is back in the box." in mi


def test_the_kept_milo_question_waits_for_the_device_question():
    # Signed in from the AAPL bar with a guest's things on the browser, Milo asked at once, docked over the "Keep what
    # you made?" sheet, and the reader's next move reloaded the page and lost the answer (the copy, 2026-11-10). The
    # kept question now waits for the answer to the sheet; a reload drops the wait and leaves the question kept.
    dv = (JS / "core" / "device.js").read_text()
    assert "export function whenSettled(fn) {\n  if (ending) return;\n  if (!askPending) { fn(); return; }\n  waiting.push(fn);\n}" in dv
    bring = dv[dv.index("export function bringGuestThings()"):dv.index("export function keepGuestThingsOut()")]
    assert "setTimeout(runWaiting, 0);" in bring
    out = dv[dv.index("export function keepGuestThingsOut()"):dv.index("export function keepDeviceSession(")]
    assert "waiting = [];" in out and "location.reload();" in out
    mp = (JS / "ui" / "miloprompt.js").read_text()
    res = mp[mp.index("export function resume(screen, symbol) {"):]
    assert res.index("whenSettled(() => resume(screen, symbol))") < res.index("const ask = take(screen, symbol);"), \
        "the question is not taken from sessionStorage until the page is known to stay"
    # the rule itself is unchanged: another person's session still reloads before anything is read
    assert "ending = true;\n  location.reload();\n  return 'reload';" in dv
