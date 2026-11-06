"""The knowledge level on the client: one value, five positions, and where it is set and shown (Phase 05).

The value is `optic.knowledge.v1`, shared with Classic (static/components/knowledge.js), and a signed-in reader's
account (core/store.js). It is set by one slider (ui/levelslider.js) wherever it appears: Home's first-visit card,
Settings and Milo's Response settings. The JavaScript runs in JavaScriptCore against the modules themselves; the
keyboard, refresh, second-tab, signed-in and Milo runs in headless Chrome are tools/phase05_checks.py (TEST_RESULTS.md,
Phase 05).
"""
import json

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
src = lambda p: (JS / p).read_text()   # noqa: E731
CLASSIC = (V2.parent / "components/knowledge.js").as_posix()


def test_five_ids_old_ids_map_once_and_each_level_says_how_terms_explain(tmp_path):
    got = _run(tmp_path, f"""
      localStorage.setItem('optic.knowledge.v1', 'literate');
      const p = await import('{(JS / "core/prefs.js").as_posix()}');
      const seen = []; p.onChange((w) => seen.push(w));
      const first = p.knowledge(), stored = localStorage.getItem('optic.knowledge.v1');
      const moved = p.setKnowledge('beginner'), again = p.setKnowledge('beginner'), bad = p.setKnowledge('nonsense');
      const quiet = p.setKnowledge('expert', {{ quiet: true }});
      print(JSON.stringify({{ ids: p.LEVEL_IDS, first, stored, moved, again, bad, quiet, seen, index: p.levelIndex(), chosen: p.knowledgeChosen(),
        policy: p.LEVEL_IDS.map((x) => p.explainPolicy(x)), legacy: ['simple', 'professional', 'adaptive'].map((x) => p.explainPolicy(x)) }}));
    """)
    assert got["ids"] == ["new", "beginner", "intermediate", "advanced", "expert"]
    assert got["first"] == "intermediate" and got["stored"] == "intermediate", "an id from before Phase 05, rewritten on its first read"
    assert got["moved"] is True and got["again"] is False and got["bad"] is False and got["quiet"] is True
    assert got["seen"] == ["knowledge", "knowledge-synced"], "a reader's change and the account's arrival are told apart"
    assert got["index"] == 4 and got["chosen"] is True
    assert got["policy"] == ["inline", "on_demand", "on_demand", "on_demand", "off"]
    assert got["legacy"] == ["inline", "off", "on_demand"]


def test_classic_reads_the_same_value_and_maps_an_old_id(tmp_path):
    got = _run(tmp_path, f"""
      localStorage.setItem('optic.knowledge.v1', 'professional');
      await import('{CLASSIC}');
      const K = window.OpticKnowledge;
      const a = {{ mode: K.mode(), stored: localStorage.getItem('optic.knowledge.v1'), level: K.level() }};
      K.set('beginner');
      print(JSON.stringify({{ a, b: {{ mode: K.mode(), level: K.level() }}, unknown: (localStorage.setItem('optic.knowledge.v1', 'zzz'), K.mode()) }}));
    """)
    assert got["a"] == {"mode": "expert", "stored": "expert", "level": 3}
    assert got["b"] == {"mode": "beginner", "level": 0}, "Beginner shares Simple's Classic layout"
    assert got["unknown"] == "intermediate"


def classic_account_run(tmp_path, status, account_level=None, local=None, chosen=False, then="", updated_at=None, pending=None):
    """Classic's component with a stand-in OpticAuth (static/auth.js): the session as `state()` gives it."""
    st = {"status": status, "sessionId": "s1", "user": {"id": "u1"} if status == "user" else None,
          "preferences": {"knowledge_level": account_level, "updated_at": updated_at} if status == "user" else None}
    return _run(tmp_path, f"""
      {f"localStorage.setItem('optic.knowledge.v1', '{local}');" if local else ''}
      {f"localStorage.setItem('optic.knowledge.pending.v1', {json.dumps(json.dumps(pending))});" if pending else ''}
      {"localStorage.setItem('optic.knowledge.asked.v1', '1');" if chosen else ''}
      const calls = [], ST = {json.dumps(st)};
      window.OpticAuth = {{ state: () => ST, on: (fn) => fn(ST),
        api: async (path, o) => {{ calls.push([o.method, path, JSON.stringify(o.body)]); return {{}}; }} }};
      await import('{CLASSIC}');
      const K = window.OpticKnowledge, first = K.mode();
      {then}
      print(JSON.stringify({{ first, last: K.mode(), calls }}));
    """)


def test_classic_takes_the_accounts_level_at_sign_in_and_sends_nothing_back(tmp_path):
    got = classic_account_run(tmp_path, "user", account_level="advanced", local="new", chosen=True)
    assert got["first"] == "advanced" and got["calls"] == []


def test_classic_sends_this_browsers_chosen_level_to_an_account_that_never_chose(tmp_path):
    got = classic_account_run(tmp_path, "user", local="beginner", chosen=True)
    assert got["first"] == "beginner"
    assert got["calls"] == [["PATCH", "/api/auth/preferences", '{"knowledge_level":"beginner"}']]


def test_classic_saves_a_signed_in_change_and_keeps_a_guests_in_the_browser(tmp_path):
    signed = classic_account_run(tmp_path, "user", account_level="intermediate", then="K.set('expert');")
    assert signed["last"] == "expert" and signed["calls"] == [["PATCH", "/api/auth/preferences", '{"knowledge_level":"expert"}']]
    guest = classic_account_run(tmp_path, "guest", local="beginner", chosen=True, then="K.set('expert');")
    assert guest["last"] == "expert" and guest["calls"] == []


def test_classic_sends_an_unsaved_level_to_an_unchanged_account_and_yields_to_a_changed_one(tmp_path):
    base = {"user": "u1", "base": "2026-10-29T15:00:00Z", "level": "expert"}
    same = classic_account_run(tmp_path, "user", account_level="beginner", local="beginner", chosen=True,
                               updated_at="2026-10-29T15:00:00Z", pending=base)
    assert same["first"] == "expert", "the unsaved level itself, not the one another account left in this browser"
    assert same["calls"] == [["PATCH", "/api/auth/preferences", '{"knowledge_level":"expert"}']]
    moved = classic_account_run(tmp_path, "user", account_level="advanced", local="expert", chosen=True,
                                updated_at="2026-10-29T15:30:00Z", pending=base)
    assert moved["first"] == "advanced" and moved["calls"] == []


def account_run(tmp_path, prefs_body, local=None, chosen=False, me_prefs=None, pending=None, patch_fails=False, then=""):
    me = {"authenticated": True, "user": {"id": "u1", "first_name": "A"}}
    if me_prefs is not None:
        me["preferences"] = me_prefs
    return _run(tmp_path, f"""
      globalThis.document.cookie = '';
      // JavaScriptCore has neither; core/api.js needs both for a request
      globalThis.AbortController = class {{ constructor() {{ this.signal = {{ aborted: false, reason: null, addEventListener() {{}} }}; }} abort(r) {{ this.signal.aborted = true; this.signal.reason = r; }} }};
      globalThis.CustomEvent = class {{ constructor(type, o) {{ this.type = type; this.detail = (o || {{}}).detail; }} }};
      globalThis.clearTimeout = globalThis.clearTimeout || (() => {{}});   // nor this; quit() below ends the run without waiting on timers
      {f"localStorage.setItem('optic.knowledge.v1', '{local}');" if local else ''}
      {"localStorage.setItem('optic.knowledge.asked.v1', '1');" if chosen else ''}
      {f"localStorage.setItem('optic.knowledge.pending.v1', {json.dumps(json.dumps(pending))});" if pending else ''}
      const calls = [];
      globalThis.fetch = async (url, opts = {{}}) => {{
        calls.push({{ url, method: opts.method || 'GET', body: opts.body || null }});
        if ({'true' if patch_fails else 'false'} && opts.method === 'PATCH') return {{ ok: false, status: 503, statusText: 'Unavailable', headers: {{ get: () => null }}, text: async () => '{{"detail":"down"}}' }};
        const body = url.startsWith('/api/auth/me') ? {json.dumps(me)}
          : url.startsWith('/api/auth/preferences') && (opts.method || 'GET') === 'GET' ? {json.dumps(prefs_body)}
          : opts.method === 'PATCH' ? {{ preferences: {{ knowledge_level: JSON.parse(opts.body).knowledge_level, updated_at: '2026-10-29T16:00:00Z' }} }} : {{ ok: true }};
        return {{ ok: true, status: 200, statusText: 'OK', headers: {{ get: () => null }}, text: async () => JSON.stringify(body) }};
      }};
      const p = await import('{(JS / "core/prefs.js").as_posix()}');
      const store = await import('{(JS / "core/store.js").as_posix()}');
      await store.loadMe();
      await new Promise((r) => setTimeout(r, 50));
      {then}
      print(JSON.stringify({{ level: p.knowledge(), calls: calls.map((c) => [c.method, c.url, c.body]), pending: JSON.parse(localStorage.getItem('optic.knowledge.pending.v1') || 'null') }}));
      quit();
    """)


def test_at_sign_in_an_account_with_a_level_wins(tmp_path):
    got = account_run(tmp_path, {"preferences": {"knowledge_level": "advanced"}}, local="new", chosen=True)
    assert got["level"] == "advanced"
    assert not [c for c in got["calls"] if c[0] == "PATCH"], "the account's value is written here, not sent back"


def test_an_account_that_never_chose_takes_the_level_chosen_in_this_browser(tmp_path):
    got = account_run(tmp_path, {"preferences": {"knowledge_level": None}}, local="beginner", chosen=True)
    assert got["level"] == "beginner"
    patch = [c for c in got["calls"] if c[0] == "PATCH"]
    assert patch and patch[0][1] == "/api/auth/preferences" and json.loads(patch[0][2]) == {"knowledge_level": "beginner"}


def test_an_account_that_never_chose_and_a_browser_that_never_chose_send_nothing(tmp_path):
    got = account_run(tmp_path, {"preferences": {"knowledge_level": None}})
    assert got["level"] == "intermediate" and not [c for c in got["calls"] if c[0] == "PATCH"]


def test_a_failed_save_is_remembered_with_the_version_this_browser_saw(tmp_path):
    """The slider's save fails: the level stays in this browser, and the account and its version are remembered."""
    got = account_run(tmp_path, {}, local="beginner", chosen=True,
                      me_prefs={"knowledge_level": "beginner", "updated_at": "2026-10-29T15:00:00Z"}, patch_fails=True,
                      then="p.setKnowledge('expert'); const r = await store.pushLevel(); print(JSON.stringify({ ok: r.ok }));")
    assert got["level"] == "expert"
    assert got["pending"] == {"user": "u1", "base": "2026-10-29T15:00:00Z", "level": "expert"}


def test_at_the_next_load_an_unchanged_account_takes_the_browsers_unsaved_level(tmp_path):
    # this browser now holds another account's level (beginner); the unsaved one is the pending entry's own
    got = account_run(tmp_path, {}, local="beginner", chosen=True, pending={"user": "u1", "base": "2026-10-29T15:00:00Z", "level": "expert"},
                      me_prefs={"knowledge_level": "beginner", "updated_at": "2026-10-29T15:00:00Z"})
    assert got["level"] == "expert", "nothing changed the account since, so this browser's level is the newer one"
    patch = [c for c in got["calls"] if c[0] == "PATCH"]
    assert patch and json.loads(patch[0][2]) == {"knowledge_level": "expert"} and got["pending"] is None


def test_at_the_next_load_an_account_changed_elsewhere_wins_over_an_unsaved_level(tmp_path):
    got = account_run(tmp_path, {}, local="expert", chosen=True, pending={"user": "u1", "base": "2026-10-29T15:00:00Z", "level": "expert"},
                      me_prefs={"knowledge_level": "advanced", "updated_at": "2026-10-29T15:30:00Z"})
    assert got["level"] == "advanced" and not [c for c in got["calls"] if c[0] == "PATCH"] and got["pending"] is None


def test_another_readers_unsaved_level_is_never_sent_to_this_account(tmp_path):
    got = account_run(tmp_path, {}, local="expert", chosen=True, pending={"user": "someone-else", "base": "2026-10-29T15:00:00Z", "level": "new"},
                      me_prefs={"knowledge_level": "beginner", "updated_at": "2026-10-29T15:00:00Z"})
    assert got["level"] == "beginner" and not [c for c in got["calls"] if c[0] == "PATCH"]


def test_the_sessions_own_preferences_are_used_without_asking_again(tmp_path):
    got = account_run(tmp_path, {"preferences": {"knowledge_level": "new"}}, local="beginner", chosen=True,
                      me_prefs={"knowledge_level": "expert"})
    assert got["level"] == "expert", "the session's answer, not the separate endpoint's"
    assert [c[1] for c in got["calls"]] == ["/api/auth/me"], "one request at load"


def test_one_slider_everywhere_with_an_accessible_name_and_value(tmp_path):
    got = _run(tmp_path, f"""
      localStorage.setItem('optic.knowledge.v1', 'beginner');
      const dom = await import('{(JS / "core/dom.js").as_posix()}');
      const s = await import('{(JS / "ui/levelslider.js").as_posix()}');
      print(JSON.stringify({{ html: dom.toString(s.levelSlider({{ id: 't', label: 'Explain things for' }})) }}));
    """)
    h = got["html"]
    assert '<label class="lvl-label" for="t-in">Explain things for</label>' in h
    assert 'type="range" min="1" max="5" step="1" value="2"' in h and 'aria-describedby="t-prev"' in h
    assert 'aria-valuetext="Level 2 of 5"' in h, "before the catalogue lands it still names the position"
    assert '<span class="t-label">Illustration</span>' in h and h.count("<i></i>") == 5
    assert "Explain things for" in src("pages/settings.js") and "levelSlider({ id: 'set-lvl'" in src("pages/settings.js")
    assert "levelSlider({ id: 'ob-lvl', label: 'How should Optic speak to you?', compact: true })" in src("pages/workspace.js")
    assert "levelSlider({ id: 'milo-lvl', label: 'Level', compact: true })" in src("ui/milo.js")
    assert "data-v2-milo-mode>${ms.map(" not in src("ui/milo.js"), "Milo's old Level select is gone"
    sl = src("ui/levelslider.js")
    assert "if (!id || !prefs.setKnowledge(id) || !store.signedIn()) return;" in sl and "store.pushLevel().then((r) => { if (!r.ok) toast(" in sl
    assert "window.addEventListener('storage', (e) => { if (e.key === 'optic.knowledge.v1') sync(); });" in sl


def test_milo_keeps_each_answers_level_and_never_rewrites_it():
    m = src("ui/milo.js")
    assert "web: !deep && !!S.web, level: prefs.knowledge() });" in m, "the level is recorded when the question is sent"
    assert "if (inf.level) o.level = String(inf.level).slice(0, 20);" in m and "level: saved.level || '' }" in m, "and kept in the history"
    assert "Explained for ${was}. Your level is now ${is}." in m and 'data-v2-milo-follow="${q ?' in m, "a later level is offered as a draft"
    assert "From here on Milo explains for ${is}. Earlier answers stay as they were written." in m
    assert "context, mode: prefs.knowledge() }" in m, "deep research is sent the level too"


def test_shared_text_offers_an_explanation_at_the_readers_level_as_a_draft():
    st = src("ui/states.js")
    assert "if (now === 'intermediate' || !name) return '';" in st
    assert 'data-v2-milo="${`Explain this for the ${name} level, keeping every figure and caveat as it is:' in st
    assert ">Explain it for ${name}</button>" in st


def test_new_to_markets_shows_definitions_from_the_one_glossary(tmp_path):
    got = _run(tmp_path, f"""
      const g = await import('{(JS / "ui/glossmark.js").as_posix()}');
      print(JSON.stringify({{ dv: g.gloss('dollar volume'), ex: g.gloss('expectancy'), none: g.gloss('not a term'), mark: ['new', 'beginner', 'expert', 'professional'].map(g.marking) }}));
    """)
    assert got["dv"] == "share price multiplied by shares traded"
    assert got["ex"] == "the average profit or loss per trade across every completed trade"
    assert got["none"] == "" and got["mark"] == [True, True, False, False]
    got = _run(tmp_path, f"""
      const g = await import('{(JS / "ui/glossmark.js").as_posix()}');
      print(JSON.stringify(['adx', 'regression channel', 'stochastic', 'keltner channel'].map(g.gloss)));
    """)
    assert got[0].startswith("Wilder's measure of how ORDERLY"), "a name keeps its capital"
    assert got[1] == "a least-squares straight line through the window, with bands at two standard errors of the residuals", "and a lone 'A' loses it"
    assert got[2] == "where the close sits inside the last 14 sessions' high-low range, as a percentage"
    assert got[3] == "", "a first sentence longer than 140 characters is left to the mark"


def test_the_chart_studies_are_defined_in_the_servers_own_words():
    """The Chart page's explanations are its studies' readings under the chart ("ADX and DI: ADX 18: no trend worth
    the name"). The glossary had no entry for most of them, so New to Markets defined none; the entries are the
    server's own description of what it computes (app/analytics/indicators.py CATALOGUE "represents"), word for word,
    in both glossaries (tests/test_v2_chart_widgets.py keeps those two the same)."""
    import re
    from app.analytics.indicators import CATALOGUE_BY_ID
    text = src("core/glossary.js")
    for key, cid in [("bollinger bands", "bollinger"), ("keltner channel", "keltner"), ("donchian channel", "donchian"),
                     ("regression channel", "sec"), ("adx", "adx"), ("stochastic", "stochastic"),
                     ("on-balance volume", "obv"), ("money flow index", "mfi")]:
        m = re.search(r"^  '%s': \"(.*)\",$" % re.escape(key), text, re.M)
        assert m and m.group(1) == CATALOGUE_BY_ID[cid]["represents"], key
    gm = src("ui/glossmark.js")
    assert "sp.dataset.v2TermInline = ''; sp.textContent = ` (${def})`;" in gm, "text, never HTML"
    assert "prefs.onChange((what) => { if (what === 'knowledge' || what === 'knowledge-synced') relevel(); });" in gm
    assert "const NO_INLINE = 'table, dl, .kv, .rd .k';" in gm and "const def = inline && !insideParens && !btn.closest(NO_INLINE) && endsPhrase(rest.nodeValue) ? gloss(k) : '';" in gm, \
        "a definition joins prose only: a table cell or a figure's label keeps the mark (directive 05 section 4)"


def test_the_briefing_asks_at_the_readers_level_and_says_who_it_was_worded_for():
    bk = src("pages/brokerage.js")
    assert "briefing${query({ level: knowledge() })}" in bk and "{ accounts: scopeIds(), level: knowledge() }" in bk
    assert "Worded for ${levelName(w.level)}." in bk
    assert "levels()]); }" in bk, "the level names are waited for, so the first paint can say them"
    assert "'was worded for another level'" in bk, "the same figures at another level are never called different figures"
    assert "The same figures at the same level are kept and not charged again." in bk


def test_classic_asks_for_the_briefing_and_deep_research_at_the_readers_level():
    bk = (V2.parent / "brokerage.js").read_text()
    assert "bkwQuery({ level: bkwLevel() })" in bk and "{ accounts: bkScopeIds(), level: bkwLevel() }" in bk
    assert "Worded for ${esc(bkwLevelName(w.level))}." in bk
    assert "'was worded for another level'" in bk and "this one would be for ${esc(bkwLevelName(bkwLevel()))}" in bk
    assert "The same figures at the same level are kept and not charged again." in bk
    app = (V2.parent / "app.js").read_text()
    research = app[app.index("await streamTo('/api/research', {"):][:400]
    assert "mode: window.OpticKnowledge ? window.OpticKnowledge.mode() : 'intermediate'," in research
