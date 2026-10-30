"""Milo's answer while it streams, and the panel around it (post-demo overhaul, Phase 07, 2026-10-29).

The answer is drawn as it arrives: the finished part once, appended, and the paragraph still arriving each frame. The
finished part may only end where drawing the answer in pieces gives what drawing it whole gives, or the answer reads
one way while it arrives and another once it is drawn again from history (a list joined to the paragraph above it in
the whole drawing and not in the pieces, found by the Phase 07 headless check C03). These feed answers with every kind
of markdown Milo writes, a character at a time and in the stand-in model's own token sizes, and compare. The paragraph
still arriving never shows a raw marker.

Then the panel's rules: a reader following the end is followed and one who moved up is not; history and a new
conversation wait for the answer and say why; the panel opens again where the reader was; the question's limit is
said; a pasted image is attached. And the server: the chat route says its first step at once, reports its own timing,
and a failure gathering the figures is an error the reader is shown.
"""
import asyncio
import json

from fastapi.testclient import TestClient

from app import main as m
from tests.test_ai_policy import _run_chat
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
MILO = (JS / "ui/milo.js").read_text()
TEXT = (JS / "core/milo-text.js").read_text()
CSS = (V2 / "css/components.css").read_text()

# The stand-in model's long answer (tools/milo_standin_ultra.py, STREAMTEST): headings, a list straight after a
# paragraph, a numbered list straight after a heading, bold.
STANDIN = ('**The short answer.** At a trailing P/E of about 27, NVDA trades below its own four-year median of 36, '
           'while revenue and net income both grew about 65% in its latest fiscal year.\n\n## What the multiple says\n\n'
           'A lower multiple than usual can mean two things. The figures here cannot tell those apart on their own.\n\n'
           '- **Revenue:** up about 65% in the fiscal year.\n- **Net margin:** about 56 cents of profit on each dollar.\n'
           '- **Next report:** Nov 17, which can move the price sharply either way.\n\n## What would change the read\n\n'
           '1. A report that cuts the forward estimates.\n2. A multiple that falls further while earnings hold.\n'
           '3. A move in rates that reprices growth stocks as a group.\n\nEvery figure above is from the context Optic sent.')
# Everything else the renderer knows: a chart and figures alone in their paragraphs (three figures, of which two are
# drawn), three actions (two drawn), source chips, a table, a code block with blank lines and stars inside it, a
# starred list, emphasis, a link, a lead-in joined to its list, three blank lines, and follow-ups in both arrow forms.
EVERYTHING = ('Apple trades at **30 times** earnings [[src framework]], *above* its median.\n\n[[chart AAPL 6m]]\n\n'
              'Two things matter:\n\n* the next report\n* the margin\n\n[[figure margins AAPL]]\n\n[[figure growth AAPL]]\n\n'
              '[[figure margins MSFT]]\n\n| Year | Revenue |\n|---|---:|\n| 2025 | $391bn |\n| 2026 | $410bn |\n\n'
              '```\nx = 2 ** 3\n\ny = x ** 2\n```\n\nRead [the filing](https://www.sec.gov/x) first.\n\n\n'
              '[[action watch AAPL]]\n\n[[action open MSFT options]]\n\n[[action level 210 "Support"]]\n\n'
              'Revenue in € and ¥, 株価 up 3%, a check ✓ and a smile 😀.\n\nA last paragraph.\n\n→ What would change this?\n-> How does MSFT compare?')
# Bold across a blank line, an answer that ends in blank lines, and one that is a single paragraph
ODD = ['**A bold run\n\nacross a blank line** and after it.\n\nThe end.', 'Only one paragraph, never finished early.',
       'Ends with blank lines.\n\n\n']

SIM = """
  const T = await import('%s');
  const norm = (h) => h.replace(/>\\s+</g, '><').replace(/\\s+/g, ' ').trim();
  // what the live panel ends with, drawn in pieces as paintLive and paintFinished draw it
  function streamed(full, sizes) {
    let cut = 0, k = 0, settled = '', raw = [], n = 0; const seen = {};
    while (n < full.length) {
      n = Math.min(full.length, n + sizes[k++ %% sizes.length]);
      const text = full.slice(0, n), followAt = text.search(T.FOLLOW_AT), end = T.settledEnd(text, followAt);
      if (end < cut) return { error: `the finished part went back from ${cut} to ${end}` };
      if (end > cut) { settled += T.renderAnswer(text.slice(cut, end), 'AAPL', seen).html; cut = end; }
      const tail = T.streamingHTML(text.slice(cut, followAt >= 0 ? Math.max(cut, followAt) : text.length), 'AAPL');
      const shown = tail.replace(/<pre[\\s\\S]*?<\\/pre>/g, '').replace(/<[^>]+>/g, '');
      if (/\\*\\*|```|(^|\\n)#{1,3} /.test(shown)) raw.push(shown.slice(-60));
    }
    const body = T.splitFollowUps(full).body;
    if (body.length > cut) settled += T.renderAnswer(body.slice(cut), 'AAPL', seen).html;
    return { same: norm(settled) === norm(T.renderAnswer(full, 'AAPL').html), raw: raw.slice(0, 3), cut };
  }
  const out = {};
  for (const [name, full] of Object.entries(%s)) {
    out[name] = { by_char: streamed(full, [1]), by_token: streamed(full, [2, 4, 6, 3, 5]), by_line: streamed(full, [40, 1, 17]) };
  }
  print(JSON.stringify(out));
"""


def test_an_answer_drawn_as_it_arrives_is_the_answer_drawn_whole(tmp_path):
    cases = {'standin': STANDIN, 'everything': EVERYTHING, **{f'odd{i}': t for i, t in enumerate(ODD)}}
    got = _run(tmp_path, SIM % ((JS / "core/milo-text.js").as_posix(), json.dumps(cases)))
    for name, runs in got.items():
        for how, r in runs.items():
            assert 'error' not in r, (name, how, r)
            assert r['same'], (name, how)
            assert not r['raw'], (name, how, r['raw'])
    # the finished part did move on: most of the long answer was drawn once, not held to the end
    assert got['standin']['by_char']['cut'] > len(STANDIN) * 0.7
    assert got['odd1']['by_char']['cut'] == 0, "a single paragraph is never finished early"


def test_the_finished_part_never_ends_where_the_drawing_would_change(tmp_path):
    got = _run(tmp_path, """
      const T = await import('%s');
      print(JSON.stringify({
        list: T.settledEnd('Lead-in:\\n\\n- one\\n- two'),
        numbered: T.settledEnd('## Head\\n\\n1. one\\n2. two'),
        undecided: T.settledEnd('A paragraph.\\n\\n- '),
        short_next: T.settledEnd('A paragraph.\\n\\nAb'),
        decided: T.settledEnd('A paragraph.\\n\\nAbcd'),
        code: T.settledEnd('```\\nx\\n\\ny\\n'),
        bold: T.settledEnd('**open\\n\\nstill open'),
        follow: T.settledEnd('One.\\n\\nTwo.\\n\\n→ A question?\\n\\n→ Another?'),
        tail_bold: T.streamingHTML('This is **half bo'),
        tail_star: T.streamingHTML('Starting **'),
        tail_head: T.streamingHTML('Text\\n##'),
        tail_code: T.streamingHTML('```\\nx = 1'),
        tail_tag: T.streamingHTML('A chart [[chart AA'),
      }));
    """ % (JS / "core/milo-text.js").as_posix())
    assert got['list'] == 0 and got['numbered'] == 0, "a list is not split from the line above it"
    assert got['undecided'] == 0 and got['short_next'] == 0, "a line too short to tell waits"
    assert got['decided'] == len('A paragraph.\n\n')
    assert got['code'] == 0 and got['bold'] == 0, "never inside a code block or a bold run"
    assert got['follow'] == len('One.\n\n'), "never into the follow-ups"
    assert got['tail_bold'] == '<p>This is <strong>half bo</strong></p>', "bold reads bold while it arrives"
    assert got['tail_star'] == '<p>Starting </p>' and got['tail_head'] == '<p>Text</p>', "a marker only begun waits"
    assert got['tail_code'].startswith('<pre class="milo-code">') and got['tail_tag'] == '<p>A chart</p>'


def test_the_live_answer_appends_what_is_finished_and_draws_only_the_arriving_paragraph():
    live = MILO[MILO.index("function paintLive() {"):MILO.index("/* ---------------- figures inside answers")]
    assert "settled.insertAdjacentHTML('beforeend', renderAnswer(text.slice(L.cut, end), L.symbol, L.seen).html);" in live
    assert "if (tail.v2Html !== th) { tail.innerHTML = th; tail.v2Html = th; }" in live, "the arriving paragraph only when it changed"
    assert "if (lines.dataset.html !== lh)" in live and "if (L.formState !== fs)" in live, "the activity lines and the form only when they change"
    assert "settled.replaceWith(...settled.childNodes);" in live, "the finished paragraphs stay, with any chart in them"
    assert "renderAnswer(body.slice(live.cut), live.symbol, live.seen || {})" in live, "the two-a-piece limit counts the whole answer"
    assert ".milo-bubble .milo-settled p:last-child { margin-bottom: 10px; }" in CSS, "no gap closing and opening as a paragraph finishes"
    assert "seen.figures = (seen.figures || 0) + 1; return seen.figures > 2" in TEXT and "seen.actions = (seen.actions || 0) + 1; return seen.actions > 2" in TEXT


def test_the_view_follows_only_a_reader_following_the_end():
    note = MILO[MILO.index("function noteScroll(l) {"):MILO.index("// a chart or a figure is drawn once its data comes")]
    assert "if (l.scrollTop < was - 1 && d > 4) S.follow = false;" in note, "moving up stops the following"
    assert "else if (d < 60) S.follow = true;" in note, "back at the end follows again"
    assert "if (log && S.follow) log.scrollTop = log.scrollHeight;" in MILO, "the live answer follows only then"
    assert "if (S.toEnd || (stick && S.follow)) log.scrollTop = log.scrollHeight;" in MILO
    assert "if (paintFinished(ai, liveWas)) { if (S.follow) lg.scrollTop = lg.scrollHeight;" in MILO
    assert "if (l && l.scrollTop > 0) S.follow = false;" in MILO, "a wheel turned up stops it before the view moves"
    assert MILO.count("keepEnd();") >= 3, "a chart or a figure drawn later keeps a following reader at the end"
    assert "new ResizeObserver(() => keepEnd())" in MILO and "if (sizeOff) { sizeOff(); sizeOff = null; }" in MILO, "and so does the log getting shorter"
    assert "S.follow = true; if (log) log.scrollTo({ top: log.scrollHeight" in MILO, "Latest follows again"


def test_history_and_a_new_conversation_wait_for_the_answer_and_say_why():
    head = MILO[MILO.index("function paintHead() {"):MILO.index("const WAIT_NEW")]
    assert "nb.setAttribute('aria-disabled', String(!!S.busy))" in head and "hb.setAttribute('aria-disabled', String(!!S.busy))" in head
    assert "nb.disabled" not in head, "still reachable by keyboard and screen reader"
    assert "if (S.busy) { toast(WAIT_NEW); return; }" in MILO and "if (open && S.busy) { toast(WAIT_HISTORY); return; }" in MILO
    assert "if (S.busy && id === S.conv.id) { toast(WAIT_HISTORY); return; }" in MILO, "the open conversation is never deleted under its answer"
    assert "const h = host(), L = S.live; if (!h || !L || S.showHistory) return;" in MILO, "nothing is drawn over the history list"
    assert '.icon-btn[aria-disabled="true"] { opacity: .45; cursor: default; }' in CSS


def test_the_panel_opens_again_where_the_reader_was():
    assert "paintLog(); restoreView(); paintForm();" in MILO
    rv = MILO[MILO.index("function restoreView() {"):MILO.index('// "Latest": back to the end')]
    assert "log.scrollTop = S.follow ? log.scrollHeight : v.top;" in rv
    assert "if (!open) restoreView();" in MILO, "back from history too"


def test_the_question_limit_is_said_and_a_pasted_image_is_attached():
    assert 'maxlength="${MAX_Q}"' in MILO and "MAX_Q = 4000" in MILO
    assert '<p class="milo-limit" id="milo-limit" role="status" hidden></p>' in MILO and 'aria-describedby="milo-attached milo-allow milo-limit"' in MILO
    lim = MILO[MILO.index("function paintLimit(ta) {"):MILO.index("function paintForm() {")]
    assert "were left out." in lim and "the most a question can hold." in lim
    paste = MILO[MILO.index("root.addEventListener('paste'"):MILO.index("root.addEventListener('scroll'")]
    assert "if (files.length && !text) { e.preventDefault(); if (!blocked()) addFiles(files); return; }" in paste
    assert "if (!ta.value.trim()) { ta.focus(); return; }" in MILO, "an empty Send goes back to the box"


def test_the_chat_route_says_its_first_step_at_once(monkeypatch):
    async def fake_stream(history, context=None, **kw):
        yield m.ai._sse("delta", {"text": "Hi."})
        yield m.ai._sse("done", {})

    async def ctx(*a, **k):
        return {}
    monkeypatch.setattr(m.ai, "stream_chat", fake_stream)
    monkeypatch.setattr(m, "_chat_context", ctx)
    monkeypatch.setattr(m, "_spend_guard", lambda request: None)
    r = TestClient(m.app).post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}], "context": {}})
    assert r.status_code == 200
    first = r.text.split("\n\n")[0]
    assert first.startswith("event: status") and '"gathering"' in first, first

    async def broken(*a, **k):
        raise RuntimeError("the research pack timed out")
    monkeypatch.setattr(m, "_chat_context", broken)
    r = TestClient(m.app).post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}], "context": {}})
    events = [e.split("\n")[0] for e in r.text.strip().split("\n\n")]
    assert events == ["event: status", "event: error"], events
    assert "could not gather the figures" in r.text and "timed out" not in r.text, "the reader is told, without the internals"


def test_classic_shows_its_steps_as_before():
    # the two server steps are v2's; Classic's list would have read "Gathering" and "Writing" (twice, around a tool)
    app = (V2.parent / "app.js").read_text()
    assert "} else if (event === 'status' && (payload.state === 'gathering' || payload.state === 'writing')) {" in app
    assert app.index("payload.state === 'gathering' || payload.state === 'writing'") < app.index("const words = PULSE_STEP_WORDS[state] || cap(state);")


def test_every_character_travels_escaped():
    # every event is JSON with non-ASCII characters escaped, so no character can be split between two network chunks
    # (the browser also decodes with TextDecoder in stream mode)
    ev = m.ai._sse("delta", {"text": "Revenue in € and ¥, 株価 ✓ 😀"})
    assert ev.isascii() and json.loads(ev.split("data: ", 1)[1])["text"] == "Revenue in € and ¥, 株価 ✓ 😀"
    assert "dec.decode(step.value, { stream: true })" in MILO


def test_the_answer_reports_its_own_timing(monkeypatch):
    events, _ = _run_chat(monkeypatch, "What does the P/E say?", ["The P/E is 27. ", "That is below its median."])
    kinds = [k for k, _ in events]
    assert kinds.index("status") < kinds.index("delta") and dict(events)["status"]["state"] == "writing", "each model round says so"
    timing = dict(events)["done"]["timing"]
    assert {"context_ready_ms", "first_model_event_ms", "first_model_text_ms", "first_text_sent_ms", "total_ms",
            "model_rounds", "text_events_sent", "gate_hold_max_ms", "tools"} <= set(timing)
    assert timing["model_rounds"] == 1 and timing["text_events_sent"] >= 1
    assert timing["context_ready_ms"] <= timing["first_model_text_ms"] <= timing["first_text_sent_ms"] <= timing["total_ms"]
    assert asyncio.iscoroutinefunction(m._chat_context)
