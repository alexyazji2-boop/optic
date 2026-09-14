"""The observer that watched for late panels, and watched itself.

Reported as "Choose panels and Show everything are not working". Both were
wired correctly the whole time: `data-panels-open` and `data-set-mode` each had
a handler, and calling either from the console did exactly the right thing.

What was broken is that the buttons did not survive being clicked.
`applyUiMode` builds its note as `class="panel mode-note"`, and
`watchForLatePanels` re-runs `applyUiMode` whenever a node containing `.panel`
is added. So the note it inserted matched its own trigger: insert note, observer
fires, remove and rebuild note, observer fires. Measured at ~3Hz, the note was a
different DOM node on every 350ms sample, and the page scroll drifted 5169px in
three seconds on its own because each cycle re-inserted the note above the
viewport and scroll anchoring compensated. A real click pressed one node and
released on another.

CLAUDE.md already records this failure from a different observer: "Recreating an
observer with a reset baseline is a self-sustaining loop; one ran at ~7Hz and
destroyed the chart toolbar between mousedown and mouseup, making every click a
no-op." Same shape, same symptom, second occurrence.

Verified in a browser by clicking both buttons through the accessibility tree,
which uses real hit-testing rather than `el.click()`:

    Choose panels   -> chooser open, 460x666, in view, 22 toggle rows
    Show everything -> level 1 to 3, 14 visible panels to 23, note gone
    note recreations over 8 samples: 10 of 10 before, 1 of 8 after
"""

import re

APP_JS = open("static/app.js", encoding="utf-8").read()


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP_JS)


def body_of(name):
    start = CODE.index("function %s(" % name)
    return CODE[start:].split("\nfunction ", 1)[0]


def test_the_observer_ignores_the_note_it_causes():
    """The one line between a callback and a loop."""
    fn = body_of("watchForLatePanels")
    assert "data-mode-note" in fn, "the note is not excluded from the trigger"
    assert "n.matches?.('[data-mode-note]')" in fn


def test_a_container_holding_only_the_note_is_not_a_late_panel():
    """The subtree branch needs the same exclusion. Without it, a wrapper that
    happens to contain the note re-arms the loop through the other half of the
    check."""
    fn = body_of("watchForLatePanels")
    assert ".panel:not([data-mode-note])" in fn


def test_the_observer_still_fires_for_a_real_late_panel():
    """The reason it exists: several panels are mounted by their own request
    into a host div and do not exist when applyUiMode first runs. Measured
    before the observer: Investing hid one of its two advanced panels and
    missed the one behind a fetch.

    Asserted on the shape of the assignment, not only on the expressions
    inside it. Checking for the expressions alone passed against
    `const added = false && records.some(...)`, which keeps every string this
    test looks for and disables the check entirely. Source text cannot prove a
    predicate is reachable, so this pins the one thing it can: nothing sits
    between the assignment and the scan.

    The behaviour itself was measured in a browser. After the fix the note was
    still rebuilt once across eight 350ms samples, which is a genuine late
    panel arriving and the observer doing its job, where before the fix it was
    rebuilt on all ten.
    """
    fn = body_of("watchForLatePanels")
    assert "const added = records.some(" in fn, (
        "something was inserted between the assignment and the scan")
    assert "n.classList?.contains('panel')" in fn
    assert "applyUiMode(view)" in fn
    assert "requestAnimationFrame" in fn, "the coalescing frame is gone"


def test_the_note_still_carries_the_panel_class():
    """It is styled as one. The fix is in the observer rather than by renaming
    the note's class, because `.panel mode-note` is what gives it the card it
    is drawn as, and a class rename would be a styling change dressed up as a
    bug fix."""
    fn = body_of("applyUiMode")
    assert "note.className = 'panel mode-note'" in fn


def test_the_note_leads_the_panels_rather_than_trailing_them():
    """`host.appendChild` put it last, which on the Options tab is the far end
    of a 10,600px view: a reader needs to know nine panels are hidden before
    scrolling the page, not once they reach the bottom."""
    fn = body_of("applyUiMode")
    assert "host.insertBefore(note, firstPanel)" in fn
    assert "el.classList.contains('panel') && el !== note" in fn, (
        "the note would be inserted before itself")
    assert "else host.appendChild(note);" in fn, (
        "a view with no panel at all must still get its note")


def test_both_buttons_still_have_their_handlers():
    """Both directions, which is the house rule. A dead control does not error;
    it takes the click and nothing happens, which reads as a slow app."""
    assert "closest('[data-panels-open]')" in CODE
    assert "openPanelChooser(STATE.view)" in CODE
    assert "closest('[data-set-mode]')" in CODE
    assert "setUiMode(detailBtn.dataset.setMode)" in CODE


# ------------------------------------------------- one Pulse button, not three

def test_the_chart_header_offers_one_pulse_action():
    """It rendered "Explain chart", "Pulse" and "Ask Pulse" side by side, all
    three of which open Pulse with a prompt, and they overran the "daily bars,
    500 of 500 shown" caption beside them.

    "Explain chart" is the one kept, on the label: it says what comes back,
    where "Pulse" named the assistant and not the action.
    """
    fn = body_of("chartPulse")
    assert "data-explain-chart" in fn
    assert "data-ask-chart" not in fn, "the duplicate button is back"
    assert "Explain chart" in fn
    # And the header no longer adds a third.
    head = CODE[CODE.index("Price, moving averages & Fibonacci"):]
    head = head[:head.index("</h2>")]
    assert "askPulse(" not in head


def test_the_market_profile_question_sits_with_the_value_area():
    """`PULSE_TOPICS.profile` asks about the market profile and the value area,
    which is the tile block rather than the price chart it was filed under."""
    assert "askPulse('profile')" in APP_JS, "the topic lost its only control"
    at = APP_JS.index("askPulse('profile')")
    around = APP_JS[at - 400:at]
    assert "volume_profile" in around


def test_the_removed_button_did_not_orphan_its_handler():
    """`data-ask-chart` keeps a control on the Charting tab, so the handler and
    `chartPulsePrompt` are still reachable rather than dead code."""
    assert len(re.findall(r"data-ask-chart=", APP_JS)) >= 1
    assert "closest('[data-ask-chart]')" in CODE
    assert "chartPulsePrompt(" in CODE


# --------------------------------------------- Line / Candles on the chart tab

def test_the_charting_tab_selects_a_style_rather_than_flipping():
    """It was one button labelled with the state it was in that did the
    opposite when clicked: in candles it read "Candles", and switching to line
    meant pressing a button that said Candles. Two buttons say what they
    select and which is active."""
    assert 'data-ws-mode="line"' in APP_JS
    assert 'data-ws-mode="candle"' in APP_JS
    assert 'data-ws-mode="${chartMode === \'candle\' ? \'line\' : \'candle\'}"' not in APP_JS


def test_the_charting_tab_keeps_its_own_handler():
    """It does not borrow the Options tab's `data-chart-mode`, whose handler
    re-renders the Swing view. A `data-*` attribute is a namespace and it is
    already crowded."""
    ws = CODE[CODE.index("const wsMode = evt.target.closest('[data-ws-mode]')"):]
    ws = ws[:ws.index("return;") + 7]
    assert "wsRedrawChart()" in ws
    assert "chartMode = wsMode.dataset.wsMode" in ws


def test_the_thesis_panel_is_hidden_but_still_wired():
    """Hidden at the reader's request, by an early return rather than by
    deleting the call site, so the panel, its diff, its store and the account
    sync behind it stay tested. Turning it back on is two lines."""
    assert "const THESIS_PANEL_HIDDEN = true;" in CODE
    fn = body_of("renderThesis")
    assert "if (THESIS_PANEL_HIDDEN) return '';" in fn
    assert "${renderThesis(d)}" in APP_JS, "the call site was removed instead"
