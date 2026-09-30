"""What stages 1 to 4 mean, as the server defines them.

Asked for once with a screenshot of the Nasdaq 100 futures chart: "include a
legend of what stages 1-4 is when it is selected". A key of all four, from the
server, sat under the instrument page's chart and the Options chart while
Stages was on. Both charts lost Stages later, asked for as "remove the stages
from the sub charts. it should be viewing only", and the key went with them.
The definitions are still the server's and still carried on every reading,
written beside the rule that decides them, which is what is tested here.
"""
from __future__ import annotations

from pathlib import Path

from app.analytics import stage

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()


def test_every_stage_has_a_definition_in_the_terms_the_rule_uses():
    assert sorted(stage.MEANINGS) == [1, 2, 3, 4] == sorted(stage.NAMES)
    ten, pct = "ten weeks", "{:g}%".format(stage.FLAT_PCT)
    assert stage.SLOPE_WEEKS == 10 and stage.SMA_WEEKS == 30
    assert "above" in stage.MEANINGS[2] and "risen more than " + pct in stage.MEANINGS[2]
    assert "below" in stage.MEANINGS[4] and "fallen more than " + pct in stage.MEANINGS[4]
    assert all(ten in stage.MEANINGS[n] for n in (2, 4))
    assert "After a decline" in stage.MEANINGS[1] and "After an advance" in stage.MEANINGS[3]
    assert all("30-week" in m for m in stage.MEANINGS.values())


def test_the_reading_carries_them(monkeypatch):
    import pandas as pd

    idx = pd.date_range("2016-01-04", periods=520, freq="W-FRI")
    closes = [100 + i * 0.5 for i in range(520)]
    frame = pd.DataFrame({"Close": closes}, index=idx)

    class Provider:
        def history(self, symbol, period="10y", interval="1wk"):
            return frame

    out = stage.for_symbol(Provider(), "ABC")
    assert out["available"] is True and out["stage"] == 2
    assert out["meanings"] == {str(k): v for k, v in stage.MEANINGS.items()}


def test_the_key_went_with_the_sub_charts_stages():
    assert "function stageLegendHTML(" not in RAW and "function paintStageLegend(" not in RAW
    assert 'id="stage-inst-legend"' not in RAW and 'id="stage-price-legend"' not in RAW
