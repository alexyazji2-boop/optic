"""Milo's activity states: what he is doing, from the server's own events (2026-11-03).

The owner asked for a Milo who visibly works through a question rather than a spinner: five states, each
with the mascot doing the matching thing, and the sequence following the real work. The rule that makes it
honest is that nothing here is invented: Researching appears only when the server says it is fetching, and
Analyzing only when something was actually fetched and the model has gone round again. A question answered
with no lookup shows Thinking then Writing and nothing else.

The reducer runs in JavaScriptCore (it is pure); the rest is read from the source and from the stylesheet.
The browser work (the card at a docked width, the line on a phone, Stop in each state, an error, Reduce
motion) is written up in docs/milo/MILO_VISUAL_QA.md with what was measured.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
ACT = (JS / "ui/milo-activity.js").read_text()
MILO = (JS / "ui/milo.js").read_text()
CSS = (V2 / "css/components.css").read_text()
AI = (Path(__file__).resolve().parent.parent / "app/ai.py").read_text()


def _states(tmp_path, steps):
    """Run the reducer over `steps` ([kind, payload]) and return the state after each."""
    body = """
      const A = await import('%s');
      let a = A.begin();
      const out = [];
      for (const [k, p] of %s) { a = A.on(a, k, p); out.push(a.state); }
      print(JSON.stringify(out));
    """ % ((JS / "ui/milo-activity.js").as_posix(), steps)
    return _run(tmp_path, body)


# ----------------------------------------------------------------- the sequence follows the real work

def test_a_question_with_no_lookup_never_shows_researching(tmp_path):
    # the server sends `writing` as each model round begins, `thinking` for a thinking block, then text
    got = _states(tmp_path, """[["status",{"state":"writing"}],["status",{"state":"thinking"}],
      ["delta",null],["done",null]]""")
    assert got == ["thinking", "thinking", "writing", "complete"]
    assert "researching" not in got and "analyzing" not in got


def test_a_lookup_gives_researching_then_analyzing(tmp_path):
    got = _states(tmp_path, """[["status",{"state":"writing"}],["status",{"state":"thinking"}],
      ["status",{"state":"Checking NVDA's options data"}],
      ["retrieved",[{"label":"NVDA options analytics","ok":true}]],
      ["status",{"state":"writing"}],["delta",null],["done",null]]""")
    assert got == ["thinking", "thinking", "researching", "researching", "analyzing", "writing", "complete"]


def test_analyzing_needs_something_to_have_come_back(tmp_path):
    """A second round with no lookup behind it is still Thinking: there is nothing to analyse."""
    got = _states(tmp_path, """[["status",{"state":"writing"}],["status",{"state":"searching the web"}],
      ["status",{"state":"writing"}]]""")
    assert got == ["thinking", "researching", "thinking"]


def test_a_tool_called_after_the_text_starts_is_still_honest(tmp_path):
    """The model can ask for one more figure mid-answer: the loop goes round, and so does the state."""
    got = _states(tmp_path, """[["delta",null],["status",{"state":"Reading your watchlists"}],
      ["retrieved",[{"label":"your watchlists","ok":true}]],["status",{"state":"writing"}],["done",null]]""")
    assert got == ["writing", "researching", "researching", "writing", "complete"]


def test_a_failed_lookup_is_not_counted_as_something_fetched(tmp_path):
    got = _states(tmp_path, """[["retrieved",[{"label":"NVDA quote","ok":false}]],["status",{"state":"writing"}]]""")
    assert got[-1] == "thinking", "a lookup that returned nothing cannot put him in Analyzing"


def test_a_file_problem_is_not_a_step(tmp_path):
    got = _states(tmp_path, """[["status",{"state":"thinking"}],
      ["status",{"state":"some files were not sent: one was too large"}]]""")
    assert got == ["thinking", "thinking"]


def test_stopping_and_failing_never_reach_answer_ready(tmp_path):
    assert _states(tmp_path, """[["status",{"state":"writing"}],["cancelled",null]]""")[-1] == "cancelled"
    assert _states(tmp_path, """[["delta",null],["error",null]]""")[-1] == "error"


def test_the_states_the_owner_asked_for_are_all_there_and_say_so(tmp_path):
    got = _run(tmp_path, """
      const A = await import('%s');
      const out = {};
      for (const k of Object.keys(A.ACTIVITY)) out[k] = [A.ACTIVITY[k].title, A.ACTIVITY[k].line, A.ACTIVITY[k].scout];
      print(JSON.stringify(out));
    """ % (JS / "ui/milo-activity.js").as_posix())
    for state in ("thinking", "researching", "analyzing", "writing", "complete", "error", "cancelled"):
        assert state in got, state
    assert got["thinking"][0] == "Thinking" and got["thinking"][1] == "Understanding your question"
    assert got["complete"][0] == "Answer ready"
    # the mascot's own states (components/scout.js POSE), never a name he does not have
    poses = set(re.search(r"var POSE = \{(.+?)\};", (V2.parent / "components/scout.js").read_text(), re.S).group(1).split())
    for k, v in got.items():
        assert any(v[2] + ":" in p or v[2] + "," in p for p in poses), v


# ----------------------------------------------------------------- the panel is wired to the real events

def test_every_event_that_moves_him_is_one_the_server_sends():
    for kind in ("delta", "status", "retrieved"):
        assert "actOn(S.live.act, '%s'" % kind in MILO, kind
    # and those are the events app/ai.py actually yields
    for ev in ("delta", "status", "retrieved", "done", "error"):
        assert '_sse("%s"' % ev in AI, ev
    assert 'yield _sse("status", {"state": "writing"})' in AI, "a model round starting is what Thinking and Analyzing read"


def test_the_card_is_for_the_wait_and_the_line_is_for_the_answer():
    assert "const expandedNow = (L, width) => !L.text && !isPhoneNow() && (width || 0) >= CARD_MIN;" in MILO
    assert "const CARD_MIN = 400;" in MILO
    assert "scout(expanded ? 'full' : 'compact')" in ACT, "the whole figure in the card, the bust in the line"


def test_answer_ready_shows_only_after_an_answer_that_landed():
    assert "paintFinished(ai, liveWas, !failed && !ended && !!reply.trim())" in MILO
    block = MILO[MILO.index("function paintFinished(i, live, ok) {"):MILO.index("/* ---------------- figures inside answers")]
    assert "if (linesNode && ok && live.act) {" in block
    assert "state: 'complete'" in block and "DONE_MS" in block
    assert "const DONE_MS = 1600;" in MILO


def test_the_answer_never_waits_for_the_character():
    """The finished answer, its sources and its follow-ups are drawn in the same frame as before; only the row
    he was already standing in is removed a moment later."""
    block = MILO[MILO.index("function paintFinished(i, live, ok) {"):MILO.index("/* ---------------- figures inside answers")]
    assert "el.replaceWith(fresh);" in block
    assert block.index("setTimeout(") < block.index("el.replaceWith(fresh);"), "the timer only removes the row"
    assert "setTimeout" not in MILO[MILO.index("const reply = S.live ? S.live.text : '', liveWas = S.live;"):MILO.index("if (paintFinished(ai, liveWas")]


def test_the_figure_is_not_torn_down_when_only_the_words_change():
    assert "export function syncActivity(" in ACT
    assert "host.insertAdjacentHTML('afterbegin', activityHTML(live, opts))" in ACT
    assert "if (title && title.textContent !== w.title) title.textContent = w.title;" in ACT
    assert "syncActivity(lines, L.act," in MILO and "scoutInActivity(lines);" in MILO
    assert "O.attach(el, { slot: 'activity' })" in MILO, "his own slot: the header bust keeps its gestures"


def test_the_names_do_not_collide_with_the_action_cards():
    """`.milo-act` was already Milo's action cards (open, compare, watch): the activity took `.milo-doing`
    after the first draft inherited their border and padding (browser check, 2026-11-03)."""
    assert "milo-act" not in ACT.replace("milo-activity.js", ""), "the activity uses no .milo-act class"
    assert ".milo-doing {" in CSS and ".milo-act { border:" in CSS


# ----------------------------------------------------------------- what it may not claim

def test_nothing_is_listed_that_a_lookup_did_not_return():
    assert "const rowsFor = (a) => (a.state === 'analyzing' ? a.fetched.slice(-3) : []);" in ACT
    assert ".filter((r) => r && r.ok !== false)" in ACT, "a lookup that failed is not a tick"


def test_what_he_works_with_is_rendered_not_drawn():
    """The desk, the tablet and the notebook are frames of the character himself (static/scout, rendered by
    optic-brand/scout/render_scout.py), so those three states carry no drawing beside him: a drawn laptop
    next to a rendered one was two laptops. Only the thought bubble and the sparkles, which are no pose he
    has, are still drawn."""
    assert "window.OpticScout ? window.OpticScout.html({ size })" in ACT
    for name in ("bubble", "done"):
        assert "<svg viewBox=" in ACT.split(name + ": `")[1][:80], name
    for gone in ("prop-desk", "prop-tablet", "prop-note"):
        assert gone not in ACT and gone not in CSS, gone
    assert 'aria-hidden="true"' in ACT
    poses = (V2.parent / "components/scout.js").read_text()
    frames = json.loads((V2.parent / "scout/frames.json").read_text())["frames"]
    for state, frame in (("researching", "desk"), ("analyzing", "tablet"), ("writing", "write")):
        assert "%s: '%s'" % (state, frame) in poses, state
        for suffix in ("", "-half", "-closed"):
            assert frame + suffix in frames, frame + suffix   # a blink needs its own lids in every pose


def test_the_three_worked_states_show_no_drawn_prop(tmp_path):
    got = _run(tmp_path, """
      const A = await import('%s');
      print(JSON.stringify(['researching', 'analyzing', 'writing'].map((k) => A.ACTIVITY[k].prop)));
    """ % (JS / "ui/milo-activity.js").as_posix())
    assert got == [None, None, None]


def test_reduce_motion_stops_every_animation_in_one_place():
    for prefix in ("@media (prefers-reduced-motion: reduce)", ':root[data-motion="reduce"] .milo-doing'):
        assert prefix in CSS, prefix
    block = CSS[CSS.index("/* One place for Reduce motion"):]
    assert ".milo-doing, .milo-doing *, .milo-doing-prop svg * { animation: none !important;" in block
    assert "The states still change" in block, "a state is what he is doing, not decoration"


def test_the_words_are_optics_own(tmp_path):
    assert "—" not in ACT, "no em dashes in the copy"
    for word in ("Thinking", "Researching", "Analyzing", "Writing", "Answer ready"):
        assert word in ACT
    assert "%" not in re.sub(r"[^%]", "", "".join(re.findall(r"line: '([^']*)'", ACT))), "no invented progress"
