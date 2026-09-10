"""The alerts centre: what fired, and why it was worth telling you.

Everything this needed was already on the server and thrown away by the client.
`/api/alerts` has always returned each alert's `title`, `body` and `payload`, an
`urgency` per row, a `why` per kind explaining what that class of alert means,
and a `delivery` block naming precisely which blocker stands between the inbox
and an email. The view showed a timestamp, a ticker, a kind slug — and an empty
message, because it read `a.message || a.text || a.reason` and an alert record
has none of those fields.

Deliberately not AI. The explanation is the rule that fired and the numbers it
fired on, so a reader can check it. `compare.take` is computed for the same
reason, and `assistant.enabled` is false on the deployment, so a generated
explanation would be a blank panel.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import alerts

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()
STYLES = (ROOT / "static" / "styles.css").read_text()


def _view() -> str:
    return APP_JS.split("function renderAlerts() {", 1)[1].split("\n}\n", 1)[0]


def _row() -> str:
    return APP_JS.split("function alertRow(", 1)[1].split("\nfunction ", 1)[0]


def _code(text: str) -> str:
    """The block with its comments removed.

    CLAUDE.md: "Reading source text to prove a control-flow property is a bad
    test", after one grepped for a `return` and matched the word inside that
    branch's own comment. This is the mirror of it — the row template carries a
    comment naming the three fields that do not exist, precisely so nobody
    reintroduces them, and a naive search finds them there.
    """
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


# --------------------------------------------------------------- the blank row

def test_the_row_renders_the_fields_an_alert_actually_has():
    """`a.message`, `a.text` and `a.reason` are not columns on the alerts table.
    Every row rendered an empty message and nobody noticed, because the inbox is
    usually empty and an empty inbox looks the same either way."""
    body = _code(_row())
    # The rendered element, not just a mention. A first pass asserted `a.body in
    # body` and passed with the line deleted, because `canExplain` also reads it.
    assert 'class="al-text">${gloss(a.title' in body, "the title is not rendered"
    assert 'class="al-sub">${gloss(a.body)' in body, "the body is not rendered"
    for ghost in ("a.message", "a.text", "a.reason"):
        assert ghost not in body, f"{ghost} is not a field on an alert"


def test_every_field_the_row_reads_exists_on_a_real_alert(tmp_path, monkeypatch):
    """Read from the module rather than asserted from memory: this is the check
    that would have caught the blank row in the first place."""
    monkeypatch.setattr(alerts, "DB_PATH", str(tmp_path / "a.db"))
    assert alerts.raise_alert("idea", "T. New long shares", ticker="T",
                              body="Composite 62.", payload={"composite": 62})
    got = alerts.recent()[0]
    for key in ("title", "body", "kind", "kind_label", "urgency", "ticker",
                "payload", "seen", "created_at", "id"):
        assert key in got, f"the row template reads {key} and the record has none"


# ------------------------------------------------------------------- urgency

def test_alerts_are_grouped_by_urgency():
    """Straight recency put a pattern confirming above a position closing, and
    the field that says which is which was on every row already."""
    assert "const ALERT_URGENCY = [" in APP_JS
    ids = re.findall(r"\{ id: '(\w+)', label:", APP_JS.split("const ALERT_URGENCY = [", 1)[1]
                     .split("\n];", 1)[0])
    assert ids == ["high", "normal", "low"], ids
    assert "ALERT_URGENCY.map" in _view()


def test_every_kind_the_server_can_raise_has_an_urgency_the_ui_groups_on():
    """A kind whose urgency is not one of the three would vanish from the view
    entirely: the groups are built by filtering on them."""
    known = {"high", "normal", "low"}
    for kind, meta in alerts.KINDS.items():
        assert meta.get("urgency") in known, f"{kind} has urgency {meta.get('urgency')!r}"


def test_an_unknown_urgency_falls_back_rather_than_disappearing():
    assert "(a.urgency || 'normal')" in _view()


# ------------------------------------------------------------------- the why

def test_every_kind_explains_itself():
    for kind, meta in alerts.KINDS.items():
        assert meta.get("why"), f"{kind} has no explanation"
        assert len(meta["why"]) > 40, f"{kind}'s explanation is a label, not a reason"


def test_the_client_keeps_the_kinds_and_delivery_blocks():
    """Both have always been in the response and both were dropped."""
    block = APP_JS.split("async function loadAlertsFeed(", 1)[1].split("\n}\n", 1)[0]
    assert "kinds: data.kinds" in block
    assert "delivery: data.delivery" in block


def test_the_explanation_is_the_rule_and_the_readings():
    """Both halves, and both as rendered rather than as bound. `const why =
    meta.why` survives deleting the element that prints it."""
    body = _code(_row())
    assert "meta.why" in body, "the kind's explanation is not read"
    assert "${gloss(why)}" in body, "the kind's explanation is read and not printed"
    assert "alertReadings(a.payload)" in body, "the numbers it fired on are not read"
    assert "${readings}" in body, "the readings are computed and not printed"


def test_the_readings_are_bounded_and_skip_the_plumbing():
    body = APP_JS.split("function alertReadings(", 1)[1].split("\nfunction ", 1)[0]
    assert ".slice(0, 8)" in body, "an arbitrary payload could render fifty rows"
    assert "ALERT_PAYLOAD_SKIP" in body
    assert "dedupe_key" in APP_JS.split("ALERT_PAYLOAD_SKIP = new Set(", 1)[1][:220]


def test_the_readings_only_render_scalars():
    """A payload nests. Interpolating an object gives "[object Object]"."""
    body = APP_JS.split("function alertReadings(", 1)[1].split("\nfunction ", 1)[0]
    assert "typeof v === 'number'" in body and "typeof v === 'string'" in body


def test_nothing_here_asks_a_model():
    """The brief said "AI alerts". The explanation is the rule and its numbers,
    which can be checked. The deployment also reports assistant.enabled false,
    so a generated one would be a blank panel."""
    body = _code(_row() + APP_JS.split("function alertReadings(", 1)[1]
                 .split("\nfunction ", 1)[0])
    for call in ("/api/chat", "askPulse", "openPulseWith"):
        assert call not in body, f"the alert explanation calls {call}"


# ------------------------------- two defects the legible view made visible ---

def test_a_missing_pnl_is_not_rendered_as_the_word_none():
    """Measured on the live inbox: "Exited at 0.05 for None. Held \u2014." Two
    faults in nine words. `None` interpolated as text reads as a broken template
    rather than as missing data, and the em dash is the punctuation this codebase
    took a deliberate pass to remove from user-facing copy."""
    body = alerts._closed_body({"exit_price": 0.05, "pnl": None, "held": None})
    assert "None" not in body
    assert "\u2014" not in body
    assert body == "Exited at 0.05."


def test_a_full_exit_still_reads_as_a_sentence():
    body = alerts._closed_body({"exit_price": 214.4, "pnl": "+8.2%", "held": "11 sessions"})
    assert body == "Exited at 214.40 for +8.2%. Held 11 sessions." or \
        body == "Exited at 214.4 for +8.2%. Held 11 sessions."


def test_an_exit_with_nothing_recorded_says_so():
    """An empty body is indistinguishable from the blank rows this view used to
    render, which is the bug immediately above."""
    assert alerts._closed_body({}).strip()


def test_no_user_facing_alert_copy_carries_an_em_dash():
    for kind, meta in alerts.KINDS.items():
        assert "\u2014" not in meta["why"], kind
        assert "\u2014" not in meta["label"], kind


def test_the_dedupe_key_identifies_the_exit_not_the_scan():
    """It was "closed:{id}:{exit_at or ran_at}". A position closed with neither
    an id nor an exit timestamp fell through to ran_at, which changes on every
    scan, so the same exit was inserted again each run. Measured on the live
    inbox: two identical BWMN rows out of nineteen."""
    pos = {"ticker": "BWMN", "instrument": "option",
           "exit_reason": "Premium stop (-50%)", "exit_price": 0.05}
    assert alerts._closed_key(pos, "scan-1") == alerts._closed_key(pos, "scan-2")


def test_an_id_or_a_timestamp_is_preferred_when_there_is_one():
    """The fallback is a fallback. Two genuinely different exits of the same name
    at the same price collapse into one under it, which is the right trade
    against duplicating on every scan but not the first choice."""
    assert alerts._closed_key({"id": 41, "ticker": "X"}, "SCANSTAMP") == "closed:41"
    keyed = alerts._closed_key({"ticker": "X", "exit_at": "2026-09-09T12:00:00Z"},
                               "SCANSTAMP")
    assert "2026-09-09T12:00:00Z" in keyed
    # The scan's timestamp must never reach the key: that is the whole defect.
    assert "SCANSTAMP" not in keyed


def test_the_same_exit_cannot_be_recorded_twice(tmp_path, monkeypatch):
    """The end-to-end version of the two tests above, through the real insert."""
    monkeypatch.setattr(alerts, "DB_PATH", str(tmp_path / "a.db"))
    result = {"closed_positions": [{"ticker": "BWMN", "instrument": "option",
                                    "exit_reason": "Premium stop (-50%)",
                                    "exit_price": 0.05}]}
    first = alerts.from_scan(result)
    second = alerts.from_scan(result)
    assert first == 1
    assert second == 0, "the same exit was recorded a second time"
    assert len(alerts.recent()) == 1


# ------------------------------------------------------------------ delivery

def test_the_view_names_what_delivery_is_missing():
    """Two blockers, different in kind, and only one is a credential. "Not
    configured" would not tell anyone which."""
    body = APP_JS.split("function alertDeliveryNote(", 1)[1].split("\nfunction ", 1)[0]
    assert "delivery.blockers" in body
    assert "delivery.enabled" in body, "a working delivery would still show the note"


def test_the_server_checks_delivery_rather_than_asserting_it():
    status = alerts.delivery_status()
    for key in ("enabled", "has_credential", "has_recipient", "blockers"):
        assert key in status


# ------------------------------------------------------------------ controls

@pytest.mark.parametrize("attr,handler", [
    ("data-alert-why", "alertsOpen"),
    ("data-alert-seen", "/api/alerts/seen"),
    ("data-alert-kind", "alertKindFilter"),
    ("data-alert-unread", "alertUnreadOnly"),
])
def test_every_control_has_a_handler(attr, handler):
    assert f"closest('[{attr}]')" in APP_JS, f"{attr} has no handler"
    block = APP_JS.split(f"closest('[{attr}]')", 1)[1][:600]
    assert handler in block, f"{attr} does not reach {handler}"


def test_marking_one_read_sends_that_one_id():
    """mark_seen(None) marks the whole inbox. Sending no ids from a per-row
    button would clear everything and look like the page had lost its state."""
    block = APP_JS.split("closest('[data-alert-seen]')", 1)[1][:600]
    assert "ids: [id]" in block


def test_marking_read_refreshes_both_feeds():
    """loadAlerts fills the header badge and the Charting dock; the view reads
    STATE.alertsFeed through loadAlertsFeed. Refreshing one left the other
    showing a stale unread count until the next full reload."""
    assert "const refreshAlerts = () =>" in APP_JS
    block = APP_JS.split("const refreshAlerts = () =>", 1)[1][:300]
    assert "loadAlerts(true)" in block and "loadAlertsFeed(true)" in block


def test_an_empty_filter_result_is_distinguished_from_an_empty_inbox():
    """"Nothing has fired" under a filter that hid four alerts is a lie."""
    body = _view()
    assert "matches this filter" in body
    assert "Nothing has fired" in body


@pytest.mark.parametrize("cls", [".al-group", ".al-group-h", ".al-group-n", ".al-sub",
                                 ".al-tags", ".al-why", ".al-explain", ".al-readings",
                                 ".al-blockers"])
def test_the_centre_is_styled(cls):
    assert re.search(re.escape(cls) + r"[\s,{:]", STYLES), f"{cls} has no rule"
