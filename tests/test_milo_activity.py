"""Milo's companion: one figure at the top of the panel, for the whole conversation (2026-11-03).

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


# ----------------------------------------------------------------- one companion, for the whole conversation

def test_every_event_that_moves_him_is_one_the_server_sends():
    for kind in ("delta", "status", "retrieved"):
        assert "actOn(S.live.act, '%s'" % kind in MILO, kind
    for ev in ("delta", "status", "retrieved", "done", "error"):
        assert '_sse("%s"' % ev in AI, ev
    assert 'yield _sse("status", {"state": "writing"})' in AI, "a model round starting is what Thinking and Analyzing read"


def test_he_lives_in_the_header_not_in_the_answer():
    """The defect this stage fixes: he used to be built inside the answer bubble, so he appeared when the
    answer began and went when it was replaced by the finished one. The drawer's header is a sibling of the
    scrolling log, so nothing the conversation does can reach him."""
    assert "head: html`${raw(companionHTML({" in MILO, "the header IS the companion"
    assert "const coEl = () => (S.panel && document.contains(S.panel) ? $('.milo-co', S.panel) : null);" in MILO
    assert "O.attach(el, { slot: 'companion' })" in MILO
    # and nothing draws a second one: the old welcome, header-bust and in-answer figures are gone
    for gone in ("welcomeEl", "headEl", "replyEl", "scoutInActivity", "syncActivity", "activityHTML"):
        assert gone not in MILO, gone
    assert ".milo-doing" not in CSS and ".milo-doing" not in ACT, "the in-log card is gone"
    assert "const fig = '';" in MILO, "the empty screen no longer draws a second large Milo"


def test_streaming_only_moves_him_it_never_rebuilds_him():
    """A chunk of text must not touch his element: rebuilding it reloads his sprite and restarts his blink."""
    live = MILO[MILO.index("function paintLive() {"):MILO.index("/* ---------------- figures inside answers")]
    assert "paintCompanion(L.act);" in live
    assert "syncCompanion" not in live, "paintLive goes through paintCompanion, which patches in place"
    sync = ACT[ACT.index("export function syncCompanion("):]
    assert "if (root.dataset.doing !== live.state)" in sync, "attributes are written only when they change"
    assert "if (name && name.textContent !== spec.title)" in sync
    assert "root.innerHTML" not in sync and "insertAdjacentHTML" not in sync, "the region is never rebuilt"
    assert "return null;" in sync and "removeChild" not in sync, "and never removed"


def test_the_answer_finishing_keeps_him():
    fin = MILO[MILO.index("function paintFinished(i, live, ok) {"):MILO.index("/* ---------------- figures inside answers")]
    assert "const linesNode = $('.milo-live-lines', old); if (linesNode) linesNode.remove();" in fin
    assert "scout" not in fin.lower().replace("milo-", ""), "nothing about him is drawn or removed here"
    end = MILO[MILO.index("function companionEnd(ok, ended) {"):]
    end = end[:end.index("\n}")]
    assert "const state = ok ? 'complete' : ended === 'stopped' ? 'cancelled' : 'error';" in end
    assert "paintCompanion({ state, said: '' }, state === 'complete' ? 'ack' : undefined);" in end
    # he settles, he does not leave
    assert "SC.rest = 'idle'; paintCompanion({ state: 'idle', said: '' })" in end
    assert "const SETTLE_MS = 2500;" in MILO


def test_a_finished_answer_cannot_reach_into_the_next_question():
    """The settle timer runs seconds after an answer lands, by which time a new question may be in flight."""
    end = MILO[MILO.index("function companionEnd(ok, ended) {"):]
    end = end[:end.index("\n}")]
    assert "settleT = setTimeout(() => { if (!S.busy && !S.live) {" in end, "the timer checks nothing newer is running"
    assert "clearTimeout(settleT)" in end, "and a new outcome drops the old timer"
    assert "clearTimeout(settleT); SC.rest = 'idle';" in MILO, "so does sending the next question"


def test_a_new_or_reopened_conversation_does_not_inherit_the_last_one():
    assert MILO.count("SC.rest = 'idle'; clearTimeout(settleT);") == 2, "new conversation, and one opened from history"
    assert "const coState = () => (S.live && S.live.act ? S.live.act : { state: SC.rest, said: '' });" in MILO


def test_he_acknowledges_without_delaying_the_request():
    send = MILO[MILO.index("export async function send("):]
    nod = send.index("paintCompanion(S.live.act, 'nod');")
    fetch = send.index("await fetch(")
    assert nod < fetch, "the nod is set up before the request, not awaited before it"
    assert "await" not in send[nod:fetch].replace("await fetch(", ""), "nothing waits on the gesture"


def test_the_greeting_is_an_acknowledgement_not_a_performance():
    assert "const GREET_GAP_MS = 60000;" in MILO
    assert "Date.now() - SC.lastWave > GREET_GAP_MS ? 'wave' : undefined" in MILO


def test_typing_is_attentive_and_is_never_called_listening_to_audio():
    fn = MILO[MILO.index("function scoutListen(v) {"):]
    fn = fn[:fn.index("\n}")]
    assert "if (c.state === 'idle') c.set('listening');" in fn
    assert "S.busy" in fn, "he does not drop a working pose to look at the composer"
    assert "Optic records no audio" in MILO, "the name is about the composer, and says so"


def test_the_status_says_one_thing_and_only_what_is_true(tmp_path):
    got = _run(tmp_path, """
      const A = await import('%s');
      const out = {};
      for (const k of Object.keys(A.ACTIVITY)) out[k] = A.ACTIVITY[k].title;
      print(JSON.stringify(out));
    """ % (JS / "ui/milo-activity.js").as_posix())
    assert got["idle"] == "Ready" and got["complete"] == "Answer ready"
    assert got["cancelled"] == "Stopped" and got["error"].startswith("Couldn")
    for k in ("thinking", "researching", "analyzing", "writing"):
        assert got[k][0].isupper()
    # the detail line under it is the server's own words, or the state's, or nothing at all
    sync = ACT[ACT.index("export function syncCompanion("):]
    assert "const under = said || spec.line || '';" in sync


def test_thinking_is_a_pose_and_the_working_poses_wear_the_headphones():
    poses = (V2.parent / "components/scout.js").read_text()
    frames = json.loads((V2.parent / "scout/frames.json").read_text())["frames"]
    assert "thinking: 'chin'" in poses, "hand under the jaw, not a head tilt"
    for suffix in ("", "-half", "-closed"):
        assert "chin" + suffix in frames
    src = (Path(__file__).resolve().parent.parent / "optic-brand/scout/render_scout.py").read_text()
    spec = src[src.index("FRAMES = ["):src.index("# (window in world units")]
    for worked in ("desk", "tablet", "write"):
        row = [l for l in spec.splitlines() if l.strip().startswith('("%s"' % worked)][0]
        assert "phones=True" in row, worked
    assert '("chin", dict(chin=1.0' in spec and "phones" not in spec[spec.index('("chin"'):spec.index('("chin"') + 120], \
        "he puts the headphones on when research begins, so thinking has none"


def test_reduce_motion_keeps_him_and_his_state():
    assert ':root[data-motion="reduce"] .milo-co-status' in CSS
    assert "@media (prefers-reduced-motion: reduce) { .milo-co-status" in CSS
    # nothing hides him: reduced motion is not a reason to take the character away
    assert ".milo-co { display: none" not in CSS
    poses = (V2.parent / "components/scout.js").read_text()
    assert "return motion() === 'still' && !WORK[name] ? 'idle' : name;" in poses


def test_the_stage_reserves_its_space_so_the_conversation_never_jumps():
    assert ".milo-co-stage { display: grid; place-items: center; width: 88px; height: 116px; }" in CSS, "the stage is the frame's own shape, so nothing overflows and gets clipped"
    assert ".milo-co-stage .scout-full { width: 88px; }" in CSS
    # and the compact arrangements the brief asks for
    assert "@media (max-height: 720px), (max-width: 480px)" in CSS
    assert "padding: 0 148px 0 4px" in CSS, "the compact row clears the panel controls (four buttons since Save conversation)"
    assert ".milo-co-stage { width: 58px; height: 77px; }" in CSS
    assert ".milo-co-stage { width: 48px; height: 63px; }" in CSS


def test_he_is_reachable_from_the_keyboard_and_named():
    assert "label: 'Milo guide: what to ask, examples and animation'" in MILO
    assert ".milo-co-stage .scout-btn:focus-visible { outline: 2px solid var(--c-gold)" in CSS
    assert '<span class="milo-co-status" role="status">' in ACT
    assert 'class="milo-co-name" id="${id}" tabindex="-1"' in ACT, "the drawer still has a heading to focus"


# ------------------------------------------- the sequence keeps up with the round (2026-11-03, owner)

def test_the_turn_toward_research_is_its_own_step(tmp_path):
    """The owner's report: "it is just stuck on thinking and then sometimes switches to writing".

    One cause was on the server. A round began with `writing` (which is Thinking until text arrives) and
    then sent nothing at all until the tool ran, so a round that reasoned for twenty seconds and then
    asked for three lookups spent all of it on Thinking. The model naming a tool is the end of thinking,
    and it is now sent as it happens; the tool's own words follow when it runs."""
    got = _states(tmp_path, """[["status",{"state":"writing"}],["status",{"state":"thinking"}],
      ["status",{"state":"looking up what it needs"}],
      ["status",{"state":"Checking NVDA's options data"}],
      ["retrieved",[{"label":"NVDA options analytics","ok":true}]],
      ["status",{"state":"writing"}],["delta",null],["done",null]]""")
    assert got == ["thinking", "thinking", "researching", "researching", "researching",
                   "analyzing", "writing", "complete"]


def test_the_server_sends_the_turn_toward_research_as_the_model_makes_it():
    assert 'elif btype == "tool_use" and will_fetch:' in AI
    assert 'yield _sse("status", {"state": "looking up what it needs"})' in AI


def test_the_turn_is_announced_only_for_a_lookup_that_will_actually_run():
    """Researching has to mean research. A tool call the round's limits would refuse is never run, so it
    is never announced: `will_fetch` is settled before the round, from the same limits the loop applies."""
    guard = AI[AI.index("will_fetch = ("):AI.index("async with client.beta.messages.stream")]
    assert 'kwargs.get("tool_choice") != {"type": "none"}' in guard
    assert "rounds < toolbox.max_rounds" in guard and "not toolbox.exhausted()" in guard
    assert "toolbox is not None" in guard
