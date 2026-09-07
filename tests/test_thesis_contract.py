"""The thesis feature's client-side contract.

There is no JS test runner here, so what is asserted is the source contract —
the same pattern as tests/test_ui_refactor.py. These are the properties that
make the feature work rather than merely exist, and each one has a specific
failure it prevents.
"""

import re

APP = open("static/app.js", encoding="utf-8").read()


def _block(marker, end="\n}"):
    start = APP.index(marker)
    return APP[start:APP.index(end, start)]


def test_saving_captures_a_snapshot():
    """The whole feature. Without the readings as they stood, the panel is a
    notes field and the app can never tell you anything changed."""
    save = _block("function thesisSave(")
    assert "snapshot: thesisSnapshot(d)" in save


def test_the_snapshot_holds_scalars_not_prose():
    """Diffing sentences produces noise. "The tone is constructive" becoming
    "the tone is positive" is not a change of thesis, and a diff full of
    rewordings buries the two or three numbers that matter."""
    fields = _block("const THESIS_FIELDS = [", "\n];")
    for banned in ("summary", "paragraphs", "narrative", "read:"):
        assert banned not in fields, banned
    # Every field must name a key and a getter.
    assert fields.count("key:") == fields.count("get:")
    assert fields.count("key:") >= 6


def test_numeric_readings_have_a_threshold():
    """Without one, every reload reports a change and the feature cries wolf on
    the first page view."""
    changes = _block("function thesisChanges(")
    assert "0.05" in changes, "price needs a percentage threshold"
    assert ">= 8" in changes, "an oscillator needs an absolute threshold"


def test_a_reading_that_arrives_is_not_reported_as_a_change():
    """A field missing when you saved and present now has not changed, it has
    arrived. Reporting it would fire on the first load after any data outage."""
    changes = _block("function thesisChanges(")
    assert "was === null || was === undefined" in changes
    assert "is === null || is === undefined" in changes


def test_an_unchanged_thesis_says_so():
    """Silence is ambiguous: it could mean nothing moved or that the check did
    not run."""
    assert "th-steady" in APP
    assert "Nothing material has moved" in APP


def test_the_panel_says_where_the_thesis_is_stored():
    """There is no account. A reader who assumes this syncs will lose it."""
    assert "Saved in this browser only" in APP


def test_the_panel_does_not_tell_the_reader_what_to_conclude():
    """It reports what moved. Whether that breaks the case is the reader's
    judgment — that is the point of having written it down."""
    assert "is your call" in APP
    for verdict in ("your thesis is wrong", "you should sell", "thesis invalidated"):
        assert verdict.lower() not in APP.lower(), verdict


def test_saving_an_empty_form_does_nothing():
    """Otherwise a stray Enter stores a blank thesis and the panel starts
    reporting changes against nothing."""
    # A fixed window rather than slicing to the next "});" — the handler contains
    # a forEach whose own closing brace ended the slice before the guard.
    start = APP.index("const form = evt.target.closest && evt.target.closest('[data-thesis-save]')")
    handler = APP[start:start + 900]
    assert "if (!Object.values(fields).some(Boolean)) return;" in handler
    assert "thesisSave(sym, fields" in handler, "the window must reach the save call"


def test_the_thesis_is_keyed_per_symbol():
    """One store for every name would overwrite the last thesis on every load."""
    assert "thesisStore()[String(symbol || '').toUpperCase()]" in APP
