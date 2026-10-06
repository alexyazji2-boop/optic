"""A Home leg that comes back empty is reported, not only one that raises.

Reproduced from the code before the fix: `leg()` added to `degraded` only on an
exception, so a throttled feed returning a board with no rows, or instruments
with no price, read as a healthy page whose strip quietly lost cells.
"""

from app import main


def test_empty_or_unpriced_legs_are_named():
    out = {"degraded": [],
           "indices": {"available": True, "rows": [{"symbol": "SPY", "price": 780.0},
                                                   {"symbol": "QQQ", "price": None}]},
           "macro": {"instruments": {"^VIX": {"last": 15.4}, "^TNX": {"last": None},
                                     "DX-Y.NYB": {"last": None}}}}
    main._note_thin_legs(out)
    assert out["degraded"] == ["indices (QQQ without a price)",
                               "macro (2 of 3 instruments without a price)"]


def test_a_board_with_no_rows_is_missing():
    out = {"degraded": [], "indices": {"available": False, "rows": []}, "macro": {"instruments": {}}}
    main._note_thin_legs(out)
    assert out["degraded"] == ["indices", "macro"]


def test_a_full_answer_is_not_flagged_and_a_raised_leg_is_not_doubled():
    out = {"degraded": ["macro"], "indices": {"available": True, "rows": [{"symbol": "SPY", "price": 1.0}]},
           "macro": None}
    main._note_thin_legs(out)
    assert out["degraded"] == ["macro"]
