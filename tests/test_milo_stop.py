"""Milo's answers can be stopped, and an unfinished one says so (2026-10-12).

Audit: no Stop anywhere; a stream cut off mid-answer was saved as complete;
the allowance was not refreshed after a send.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
HTML = (ROOT / "static/index.html").read_text()


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def test_stop_aborts_the_request_and_only_shows_while_answering():
    assert 'id="chat-stop" hidden aria-label="Stop Milo\'s answer">Stop</button>' in HTML
    stream = _fn("async function streamTo(url, body, node) {")
    assert "const ctl = new AbortController();" in stream and "signal: ctl.signal," in stream
    assert "if (chatState.abort) chatState.abort.abort();" in APP
    for fn in ("async function sendChat(text) {", "async function runResearch() {"):
        body = _fn(fn)
        assert "setChatStop(true);" in body and "setChatStop(false);" in body, fn


def test_an_unfinished_answer_is_marked_on_screen_and_in_the_thread():
    stream = _fn("async function streamTo(url, body, node) {")
    assert "if (!finished && !node.dataset.ended) node.dataset.ended = 'cut';" in stream
    assert "Stopped by you. This answer is incomplete." in stream
    assert "The connection ended before Milo finished. This answer is incomplete." in stream
    send = _fn("async function sendChat(text) {")
    assert "[${ended === 'stopped' ? 'Stopped by the reader' : 'Cut off'}: incomplete]" in send
    assert "loadAllowance();" in send


def test_the_mascot_reads_a_stop_as_a_stop_not_an_error():
    done = _fn("function pulseReplyScoutDone(el, node) {")
    assert "node.dataset.ended === 'stopped'" in done and "c.set('idle', 'look')" in done
    assert "node.dataset.ended === 'cut') { c.set('error');" in done
