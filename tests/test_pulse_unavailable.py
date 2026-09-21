"""Pulse must not look ready when it has no key.

Measured on production, where `ANTHROPIC_API_KEY` is unset and
`/api/health` reports `assistant.enabled: false`: clicking Pulse opened the
panel with an enabled textarea, an enabled Send and an enabled Deep research,
and said nothing at all. A visitor could type a question, send it, and only
then find out.

The cause was one line. `/api/ai-allowance` has always returned
`{allowance, ai}` and `loadAllowance` read `reply.allowance` and dropped
`reply.ai` on the floor, so nothing in the client ever knew.

The second half was the copy. `available()["hint"]` said "Set
ANTHROPIC_API_KEY in your environment", which is the right instruction for
whoever runs the terminal on their own machine and a useless one for a
visitor to the public site, who has no environment to set it in.
"""

from __future__ import annotations

from app import ai

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
HTML = open("static/index.html", encoding="utf-8").read()


# ------------------------------------------------------------- the server


def test_the_hint_knows_who_is_reading_it(monkeypatch):
    """Same branch and same reason as `originIsEphemeral()` on the client: two
    audiences, and one sentence is wrong for one of them."""
    for var in ("RAILWAY_ENVIRONMENT", "RAILWAY_GIT_COMMIT_SHA", "RENDER",
                "FLY_APP_NAME"):
        monkeypatch.delenv(var, raising=False)
    local = ai.available()["hint"]
    assert "ANTHROPIC_API_KEY" in local, "the operator can act on this"

    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    hosted = ai.available()["hint"]
    assert "ANTHROPIC_API_KEY" not in hosted, \
        "a visitor has no environment to set a variable in"
    assert "not configured on this deployment" in hosted
    assert "every other panel" in hosted.lower(), \
        "the rest of the terminal still works, and the sentence has to say so"


def test_availability_is_still_reported_either_way(monkeypatch):
    """The flag itself is unchanged; only the sentence beside it moved."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    state = ai.available()
    assert set(state) >= {"enabled", "model", "credential_source", "hint"}
    assert isinstance(state["enabled"], bool)


# ------------------------------------------------------------- the client


def test_the_client_keeps_the_flag_it_used_to_discard():
    fn = APP.split("async function loadAllowance() {", 1)[1].split("\n}", 1)[0]
    assert "ACCOUNT.ai = reply.ai" in fn, \
        "reply.ai was fetched on every call and thrown away"
    assert "renderPulseUnavailable()" in fn, "and nothing acted on it"


def test_the_composer_is_actually_disabled_not_merely_unhelpful():
    """A panel that looks ready and is not costs the reader a question and a
    wait to discover it."""
    fn = APP.split("function renderPulseUnavailable() {", 1)[1].split("\nfunction ", 1)[0]
    for control in ("#chat-input", "#chat-send", "#chat-research"):
        assert control in fn, control
    assert "disabled = true" in fn and "disabled = false" in fn, \
        "it has to switch back on when a key appears"


def test_an_unknown_state_is_not_treated_as_off():
    """`ai` is absent until the first fetch lands. `!enabled` would be true
    then, and the notice would flash on every cold load before the endpoint
    answered."""
    fn = APP.split("function renderPulseUnavailable() {", 1)[1].split("\nfunction ", 1)[0]
    assert "ai.enabled === false" in fn
    assert "!ai.enabled" not in fn


def test_the_panel_still_opens_so_the_reason_can_be_read():
    """Disabling the header button instead would hide the explanation behind
    the one control that reveals it, and leave a dead button with no reason."""
    fn = APP.split("function renderPulseUnavailable() {", 1)[1].split("\nfunction ", 1)[0]
    assert "chat-open" not in fn, "this must not touch whether the panel opens"
    assert "pulse-btn" not in fn and "data-open-pulse" not in fn


def test_the_reason_is_the_servers_sentence_not_a_second_copy():
    """The server already branches on the audience. Guessing at the wording
    here would be a second copy to keep in step."""
    fn = APP.split("function renderPulseUnavailable() {", 1)[1].split("\nfunction ", 1)[0]
    assert "ai.hint" in fn
    assert "ANTHROPIC_API_KEY" not in APP, \
        "the client must not hard-code the operator's instruction"


def test_the_reason_is_announced_to_a_screen_reader():
    """A disabled input with an unexplained state beside it is the version of
    this bug that only some readers get."""
    fn = APP.split("function renderPulseUnavailable() {", 1)[1].split("\nfunction ", 1)[0]
    # Both halves named in full. A bare `"aria-describedby" in fn` passes on
    # the removeAttribute line alone, which is how a mutation deleting the
    # setAttribute survived this test the first time it was run against one.
    assert "setAttribute('aria-describedby', 'chat-off')" in fn
    assert "removeAttribute('aria-describedby')" in fn, \
        "and it comes off again when Pulse works"


def test_the_disabled_composer_reads_as_disabled():
    assert "#chat-input:disabled," in CSS
    block = CSS[CSS.index("#chat-input:disabled,"):]
    block = block[:block.index("}")]
    assert "not-allowed" in block and "opacity" in block


def test_the_controls_the_client_disables_actually_exist():
    """Both directions, the rule this codebase already applies to every
    control: a handler with no control is as dead as a control with no
    handler."""
    for el_id in ("chat-input", "chat-send", "chat-research"):
        assert 'id="{}"'.format(el_id) in HTML, el_id
