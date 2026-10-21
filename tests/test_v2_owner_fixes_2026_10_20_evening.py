"""The owner's v2 requests of 2026-10-20 evening: the price on the day of each congressional trade, the Paper Desk
ticket laid out with every label above its control, and the Brokerage what-if lab removed from both apps and the
server. (The charts that stopped printing their figures are tested in test_v2_dataviz.py.)
"""
import pandas as pd
from fastapi.testclient import TestClient

import app.main as main
from tests.test_frontend_v2_stage0 import V2

JS = V2 / "js"
PAPER = (JS / "pages/paper.js").read_text()
CSS = (V2 / "css/pages.css").read_text()


class _Bars:
    def history(self, sym, period="2y", interval="1d"):
        idx = pd.DatetimeIndex(["2026-01-15", "2026-01-16", "2026-01-20", "2026-01-21"], tz="America/New_York")
        return pd.DataFrame({"Close": [101.0, 108.744, 105.78, 99.0]}, index=idx)


def test_each_trade_gets_the_close_on_its_date_and_says_which_day(monkeypatch):
    monkeypatch.setattr(main, "YF_PROVIDER", _Bars())
    trades = [{"traded_iso": "2026-01-20"}, {"traded_iso": "2026-01-18"}, {"traded_iso": "2025-06-02"},
              {"traded_iso": "2026-01-20", "date_suspect": True}, {"traded": "Jan 20"}]
    main._congress_closes("HOOD", trades)
    assert trades[0]["close"] == 105.78 and trades[0]["close_date"] == "2026-01-20"
    assert trades[1]["close"] == 108.74 and trades[1]["close_date"] == "2026-01-16", "a Sunday trade: Friday's close, dated"
    assert "close" not in trades[2], "older than the bars Optic holds: no price, never a guess"
    assert "close" not in trades[3], "a mistyped trade date would price the wrong day"
    assert "close" not in trades[4]


def test_the_close_is_labelled_as_the_market_close_not_the_members_price():
    mod = (JS / "core/congress.js").read_text()
    assert "Close that day is the stock's closing price on the trade date" in mod and "filings give no price, so the member's own price may differ" in mod
    assert "'Not available'" in mod
    fin = (JS / "pages/financials.js").read_text()
    assert "<th>Amount</th><th>Close that day</th><th>Filed after</th>" in fin and "${CLOSE_NOTE}" in fin


def test_the_ticket_puts_each_label_above_its_control():
    form = PAPER[PAPER.index("function ticketForm() {"):PAPER.index("function preview() {")]
    assert 'class="pt-grid' not in form and form.count('class="pt-row') >= 2
    assert '<label class="t-label" for="pt-ticker">Symbol</label><span class="field"><input id="pt-ticker"' in form, "the box is the input only"
    assert 'placeholder="required"' not in form and 'placeholder="optional"' not in form, "a placeholder is not a label"
    assert "Target <span class=\"t-muted\">(optional)</span>" in form
    assert ".pt-row.pt-nums { grid-template-columns: repeat(4, minmax(0, 1fr)); }" in CSS and ".pt-row > .pt-sym { grid-column: 1 / -1; }" in CSS
    assert ".pt-f > .field { min-width: 0;" in CSS and ".pt-f > .field input { width: 100%; }" in CSS, "number boxes overlapped their neighbours (live check at 1440 and 390)"


def test_the_what_if_lab_is_gone_from_both_apps_and_the_server():
    for f in (JS / "pages/brokerage.js", V2.parent / "brokerage.js"):
        src = f.read_text()
        assert "scenario" not in src.lower(), f
    assert "'events', 'connections'].includes(section)" in (V2.parent / "app.js").read_text()
    paths = {getattr(r, "path", "") for r in main.app.routes}
    assert "/api/brokerage/workspace/scenario" not in paths
    r = TestClient(main.app).post("/api/brokerage/workspace/scenario", json={})
    assert r.status_code in (404, 405)


def test_periods_the_history_cannot_reach_wait_and_say_why(tmp_path):
    # "these percentages remain a constant": five days of values made 1M, 3M, YTD, 1Y and All one window
    from tests.test_frontend_v2_stage0 import _run
    got = _run(tmp_path, f"""
      const B = await import('{(JS / "pages/brokerage.js").as_posix()}');
      const starts = {{ '1m': '2026-09-21', '3m': '2026-07-21', ytd: '2025-12-31', '1y': '2025-10-21' }};
      print(JSON.stringify({{ five: B.shortPeriods({{ history_start: '2026-10-16', starts }}),
        months: B.shortPeriods({{ history_start: '2026-06-02', starts }}), weekend: B.shortPeriods({{ history_start: '2026-09-24', starts }}),
        none: B.shortPeriods({{ starts }}) }}));
    """)
    assert got["five"] == ["1m", "3m", "ytd", "1y"], "five days of history: only All is a different question"
    assert got["months"] == ["ytd", "1y"]
    assert got["weekend"] == ["3m", "ytd", "1y"], "1M starting three days before the first value is a weekend, not a gap"
    assert got["none"] == []
    src = (JS / "pages/brokerage.js").read_text()
    assert "would measure the same days as All." in src and 'disabled title="Needs history back to' in src
    assert "${twr.annualized && isNum(mwr.irr_annualized_pct) ?" in src, "no annualised figure from five days"
    assert "${twr.annualized && mwr.irr_annualized_pct !== null" in (V2.parent / "brokerage.js").read_text()


def test_the_server_says_where_the_history_begins():
    perf = (V2.parent.parent / "app/brokerage/performance.py").read_text()
    assert '"history_start": _iso(history_start),' in perf and '"starts": {p: period_start(p, today).isoformat() for p in PERIODS if p != "all"}' in perf
