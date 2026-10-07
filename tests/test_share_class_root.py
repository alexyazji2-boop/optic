"""A share class's ticker matches its option root.

/api/ticker/BRK-B returned a 500, live as well as locally, measured 2026-10-07.
The OCC root carries no punctuation, so BRK-B's contracts are BRKB..., and the
contract-size check compared the root with the ticker as written.
"""
from __future__ import annotations

import pandas as pd


def test_a_share_class_ticker_matches_its_option_root():
    """BRK-B's contracts are BRKB...; compared as written every one read as an
    adjusted contract of unknown size and /api/ticker/BRK-B returned a 500."""
    from app.analytics import quotes
    f = pd.DataFrame({"contract": ["BRKB261218C00500000", "BRKB261218P00480000",
                                   "BRKB1261218C00100000"]})
    assert quotes.multipliers(f, "BRK-B").tolist()[:2] == [100.0, 100.0]
    assert pd.isna(quotes.multipliers(f, "BRK-B").tolist()[2]), "an adjusted root is still unknown"


def test_no_contracts_is_an_empty_answer_not_a_crash():
    import numpy as np
    from app.analytics import greeks
    assert greeks._norm_cdf(np.array([])).tolist() == []
