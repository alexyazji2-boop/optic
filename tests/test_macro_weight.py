"""The macro market score is not an input to any stock's composite (2026-10-24).

A pre-registered back-test (~/Optic/work/macro-backtest-2026-10-23/REPORT.md) found no sign that leaning risk-on or
risk-off was followed by better or worse stock returns over the next month, so the 0.10 weight came out.
"""
from __future__ import annotations

import inspect

import pytest

from app import signal_archive
from app.analytics import swing


def test_the_composite_has_four_inputs_in_their_old_proportions():
    assert set(swing.WEIGHTS) == {"technicals", "gamma", "flow", "news"}
    assert sum(swing.WEIGHTS.values()) == pytest.approx(1.0)
    old = {"technicals": 0.34, "gamma": 0.24, "flow": 0.20, "news": 0.12}
    for k, v in old.items():
        assert swing.WEIGHTS[k] == pytest.approx(v / 0.90, abs=0.005)
    assert "macro" not in inspect.signature(swing.verdict).parameters
    assert "macro" not in swing.COMPONENT_MEANING and "macro" not in swing.COMPONENT_UNAVAILABLE


def test_the_breakdown_names_no_macro_input(monkeypatch):
    monkeypatch.setattr(swing, "_gamma_score", lambda gex, spot: 20.0)
    out = swing.verdict({"trend_score": 40.0}, {}, {"flow_score": 10.0}, {"net_sentiment": 1.0, "articles": []}, 100.0)
    assert [b["component"] for b in out["breakdown"]] == ["technicals", "gamma", "flow", "news"]
    assert "macro" not in out["components"]
    assert sum(b["weight_pct"] for b in out["breakdown"]) == pytest.approx(100, abs=1)


def test_archived_reads_are_compared_only_within_one_rule_version():
    assert signal_archive.RULE_VERSION == "2026-10-24"
    src = inspect.getsource(signal_archive)
    assert '"group": (r["day"], r["macro_included"], r.get("rule_version"))' in src
