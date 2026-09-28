"""Pulse scrolls as one region between its header and its input.

Reported as "be able to scroll down on Pulse when the cursor is above it in
this area", circling the lens, the notice and the suggestions. Measured at
900px tall before the fix: the lens 169px, the notice 208px and the footer
521px were all fixed flex items, so `#chat-log` -- the only thing that
scrolled -- was crushed to 28px around 668px of content, and the panel's
1,025px overflowed its own height with the input cut off below the fold.

The A/B, driven with a real wheel over the lens on the same NVDA view:
production moved the page underneath 300px and Pulse not at all; this build
moved Pulse 300px and the page not at all. Twenty notches past the end of the
panel then left the page at 0, which is the `overscroll-behavior` half.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
HTML = (ROOT / "static/index.html").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _strip(text: str) -> str:
    """Comments out, JS and HTML both. Every assertion below names something the
    surrounding prose also names -- the body's own comment explains all of it."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


def _panel() -> str:
    body = _strip(HTML)
    return body[body.index('<aside id="chat"'):body.index("</aside>")]


def _between(src: str, start: str, end: str) -> str:
    i = src.index(start)
    return src[i:src.index(end, i)]


def _rule(selector: str) -> str:
    clean = _strip(CSS)
    start = clean.index(selector + " {") + len(selector) + 2
    return clean[start:clean.index("}", start)]


def _fn(name: str) -> str:
    code = _strip(APP)
    body = code[code.index("function " + name + "("):]
    return body[:body.index("\n}") + 2]


# ------------------------------------------------------------- the markup


def test_everything_between_the_header_and_the_input_is_in_one_body():
    body = _between(_panel(), 'id="chat-body"', 'class="chat-foot"')
    for part in ('id="chat-persona"', 'id="pulse-history"', 'id="pulse-legal"',
                 'id="chat-log"', 'id="chat-suggest"'):
        assert part in body, "{} is outside the scroll region".format(part)


def test_the_suggestions_left_the_footer():
    """Pinned beside the input they were 400px that could never be scrolled
    past, which is most of why the footer measured 521px."""
    panel = _panel()                   # already ends at </aside>
    foot = panel[panel.index('class="chat-foot"'):]
    assert 'id="chat-suggest"' not in foot


def test_the_input_is_still_pinned_below_the_body():
    """The body scrolls; the thing you type into must not scroll with it."""
    panel = _panel()
    assert panel.index('id="chat-body"') < panel.index('class="chat-foot"') \
        < panel.index('id="chat-input"')
    assert 'id="chat-input"' not in _between(panel, 'id="chat-body"', 'class="chat-foot"')


# ----------------------------------------------------------------- the css


def test_the_body_is_the_scroller():
    rule = _rule("#chat .chat-body")
    assert "overflow-y: auto" in rule


def test_the_body_can_shrink_below_its_content():
    """A flex item's automatic minimum is its content height. Without
    `min-height: 0` the body grows past the panel instead of scrolling inside
    it -- the same shape of fault that crushed the log."""
    assert "min-height: 0" in _rule("#chat .chat-body")


def test_reaching_either_end_does_not_scroll_the_page_behind():
    """Twenty notches past the end left the page at 0. Without this the wheel
    is handed to the document and the terminal moves under a fixed panel."""
    assert "overscroll-behavior: contain" in _rule("#chat .chat-body")


def test_the_log_is_no_longer_a_scroller_of_its_own():
    """Nested inside the body it is content-sized. `flex: 1` in a column whose
    other children were all fixed is what squeezed it to 28px."""
    rule = _rule("#chat .chat-log")
    assert "overflow-y" not in rule
    assert not re.search(r"(^|;)\s*flex:\s*1", rule)


# ------------------------------------------------------------------ the js


def test_the_scroller_is_the_body_not_the_log():
    assert "$('#chat-body')" in _fn("pulseScroller")


def test_new_messages_follow_the_body():
    """Asked of the log, which is content-sized and never overflows now,
    `isPinnedToBottom` would always answer yes -- and the stream would drag a
    reader back down while they were re-reading the first paragraph."""
    fn = _fn("addMsg")
    assert "isPinnedToBottom(scroller)" in fn
    assert "followStream(scroller, wasPinned)" in fn
    assert "log.appendChild(wrap)" in fn, "messages still go into the log"


def test_the_stream_follows_the_body():
    code = _strip(APP)
    block = code[code.index("const pinned = isPinnedToBottom(logEl)") - 120:]
    block = block[:block.index("followStream(logEl, pinned)")]
    assert "const logEl = pulseScroller();" in block


def test_a_resumed_conversation_opens_at_its_end():
    code = _strip(APP)
    i = code.index("chatState.messages = (hit.messages || [])")
    block = code[i:i + 900]
    assert "pulseScroller()" in block
    assert "scroller.scrollTop = scroller.scrollHeight" in block
