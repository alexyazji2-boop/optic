"""Every figure on the Financials tab says what it is.

Asked for after the key stats got theirs: "add definitions to the Financials
tab stats too". The tiles, label-and-figure lists, statement lines and figure
columns there explained one word inside a label, when they explained anything:
"% of float short" defined "float", and "Revenue growth (y/y)" defined
"revenue". Each label is now explained as a whole, by the reader's knowledge
mode, the way the key stats are.

Three figures were not what their labels said, and are fixed here:

* net income growth from a loss year came out with the wrong sign (a loss of
  100 turning into a profit of 50 read as "fell 150%");
* "Insider-held float" was a share of all the stock, and insiders' shares are
  exactly the ones the float leaves out;
* "Payments on record" was the length of the list shown, which stops at 24.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from app.analytics import extras, fundamentals

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

CO = {
    "short_interest": {"available": True, "squeeze_potential": "low", "settlement_date": "2026-09-15",
                       "percent_of_float": 0.034, "days_to_cover": 1.8, "change_vs_prior_pct": -4.2,
                       "shares_short": 1.2e7, "shares_short_prior": 1.25e7, "float_shares": 3.5e8,
                       "notes": [], "caveat": "c"},
    "earnings_history": {"available": True, "beat_count": 3, "sample_size": 4, "beat_rate_pct": 75,
                         "avg_surprise_pct": 4.1, "upcoming": [], "notes": [],
                         "quarters": [{"date": "2026-06-30", "eps_estimate": 1.0, "eps_reported": 1.1,
                                       "surprise_pct": 10}]},
    "financials": {"available": True, "annual_periods": ["2025", "2024"],
                   "annual": {"revenue": [1e9, 9e8], "gross_profit": [5e8, 4e8],
                              "operating_income": [2e8, 1e8], "net_income": [1e8, 5e7],
                              "free_cash_flow": [9e7, 4e7], "diluted_eps": [1.2, 0.6]},
                   "growth": {"revenue_yoy_pct": 11.1, "net_income_yoy_pct": 100},
                   "margins": {"net_pct": 10, "gross_pct": 50, "operating_pct": 20},
                   "balance_sheet": {"cash": 3e8, "total_debt": 1e8, "net_cash": 2e8,
                                     "debt_to_equity": 0.4},
                   "notes": []},
    "ownership": {"available": True, "insider_signal": "neutral",
                  "insider_6m": {"net_shares": -1000, "purchase_shares": 500, "purchase_count": 2,
                                 "sale_shares": 1500, "sale_count": 3},
                  "institutional_pct_held": 0.7, "insider_pct_held": 0.05, "holders_adding": 2,
                  "holders_trimming": 1, "recent_transactions": [], "notes": [], "caveat": "c",
                  "top_holders": [{"holder": "V", "date_reported": "2026-06-30", "shares": 1e7,
                                   "pct_held": 0.08, "pct_change": 0.01}]},
}
X = {
    "ticker": "KO",
    "actions": {"pays_dividend": True, "growth_streak_years": 3, "last_cut_year": None,
                "dividends": [{"date": "2026-09-15", "amount": 0.53}] * 24, "payment_count": 254,
                "annual": [{"year": 2024, "total": 1.94}, {"year": 2025, "total": 2.04}],
                "splits": [{"date": "2012-08-13", "ratio": 2.0}], "note": "n"},
    "short_volume": {"rows": [{"date": "2026-10-05"}], "latest_pct": 48.1, "average_pct": 45.0,
                     "days": 20, "caveat": "c"},
    "relative": {"benchmark": "SPY", "excess": {"5d": 1.0, "20d": -2.0, "60d": 3.0, "120d": 4.0,
                                                 "252d": 5.0}, "note": "n"},
}

COMPANY_LABELS = [
    "% of float short", "Days to cover", "Vs prior period", "Shares short", "Prior settlement",
    "Float", "EPS est.", "EPS actual", "Surprise", "Revenue growth (y/y)", "Net income growth",
    "Net margin", "Revenue", "Gross profit", "Operating income", "Net income", "Free cash flow",
    "Diluted EPS", "Cash", "Total debt", "Net cash position", "Debt / equity", "Gross margin",
    "Operating margin", "Insider net (6m)", "Institutional held", "Top holders",
    "Insider purchases (6m)", "Insider sales (6m)", "Held by insiders", "% held", "Change",
]
EXTRAS_LABELS = [
    "Latest payment", "Growth streak", "Annual total", "Payments on record", "Total paid", "Change",
    "Ratio", "Latest", "20-day average", "Vs its average", "Days on record", "5 days", "20 days",
    "60 days", "120 days", "252 days",
]


def _jsc(script, before=""):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
    """ + before + """
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var CO = %s, X = %s, R = {};
      STATE.swing = {};
    """ % (json.dumps(CO), json.dumps(X)) + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-1500:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def _terms(html):
    """Each defined label and the definition it carries, as the page has them."""
    found = re.findall(r'<dfn class="gloss-term" tabindex="0" data-def="([^"]*)">([^<]*)</dfn>', html)
    return [(label, d) for d, label in found]


def _render(policy="on_demand"):
    return _jsc("""
      explainPolicy = function () { return '%s'; };
      R.company = renderCompany(CO);
      R.extras = renderExtras(X);
      R.defs = FIN_DEFS;
      R.excess = excessReturnDef(252, 'SPY');
    """ % policy)


def test_every_figure_on_the_tab_explains_itself():
    out = _render()
    company = [label for label, _ in _terms(out["company"])]
    extras_ = [label for label, _ in _terms(out["extras"])]
    for label in COMPANY_LABELS:
        assert label in company, label
    for label in EXTRAS_LABELS:
        assert label in extras_, label
    # Explained as the whole label, not one word inside it.
    assert ">float</dfn>" not in out["company"] and ">revenue</dfn>" not in out["company"]


def test_each_label_carries_its_own_definition():
    out = _render()
    by_label = dict(_terms(out["company"]))
    d = out["defs"]
    unescape = lambda s: s.replace("&#39;", "'").replace("&quot;", '"').replace("&amp;", "&")
    assert unescape(by_label["Total debt"]) == d["total_debt"]
    assert unescape(by_label["% of float short"]) == d["short_pct_float"]
    assert unescape(by_label["Held by insiders"]) == d["insider_held"]
    extras_ = _terms(out["extras"])
    assert any(label == "252 days" and "SPY" in unescape(text) for label, text in extras_)


def test_the_definitions_keep_the_glossarys_rules():
    """tests/test_glossary_fundamentals.py's rules: what it is and why it
    matters in two sentences at least, no em dash, and no advice."""
    out = _render()
    banned = ("you should", "you want", "look for a", "buy when", "sell when", "a good sign that you")
    for key, body in list(out["defs"].items()) + [("excess", out["excess"])]:
        assert body.count(".") >= 2 and len(body) >= 110, (key, body)
        assert "—" not in body, key
        for phrase in banned:
            assert phrase not in body.lower(), (key, phrase)


def test_the_definitions_say_what_was_checked():
    """Checked against Yahoo's data on 2026-10-06: PLTR has no loans and $229M
    of "total debt", all leases; UBER's 3.11 against a 0.69 estimate was a
    one-off gain. And the dividend dates are ex-dividend dates."""
    d = _render()["defs"]
    assert "lease" in d["total_debt"]
    assert "not always on the same basis as the estimate" in d["eps_actual"]
    assert "ex-dividend" in d["div_latest"] and "ex-dividend" in d["div_annual"]
    assert "complete calendar years" in d["div_streak"]
    # KO's record holds its September 2001 dividend twice, so 2002 reads as a cut.
    assert "doubled or missing" in d["div_streak"]
    assert "off-exchange" in d["sv_latest"] and "FINRA" in d["sv_latest"]
    assert "loss" in d["net_income_growth"]
    assert "latest annual balance sheet" in d["cash"]


def test_the_glossary_wording_is_reused_where_it_exists():
    out = _jsc("""
      R.defs = FIN_DEFS;
      R.g = {revenue: GLOSSARY.revenue, fcf: GLOSSARY['free cash flow'], float: GLOSSARY.float,
             gm: GLOSSARY['gross margin'], de: GLOSSARY['debt to equity']};
      R.ks = {si: KEY_STAT_DEFS.short_float, dtc: KEY_STAT_DEFS.days_to_cover};
    """)
    d, g, ks = out["defs"], out["g"], out["ks"]
    assert d["revenue"] == g["revenue"] and d["free_cash_flow"] == g["fcf"] and d["float"] == g["float"]
    assert d["gross_margin"] == g["gm"] and d["debt_to_equity"].startswith(g["de"])
    assert d["short_pct_float"] == ks["si"] and d["days_to_cover"] == ks["dtc"]


def test_simple_opens_in_place_and_professional_leaves_them_plain():
    inline = _render("inline")
    assert inline["company"].count("data-gloss-open") >= len(COMPANY_LABELS)
    assert "data-gloss-pair" in inline["company"], "kv labels mark where the definition goes"
    off = _render("off")
    assert "gloss-term" not in off["company"].replace("gloss-term is-inline", "")
    assert "data-def" not in off["company"]


def test_a_list_definition_opens_under_the_figure_across_both_columns():
    """Inside the <dt>, the label's auto-sized column grew to the paragraph's
    width and squeezed every figure in the list."""
    out = _jsc("""
      function el(tag, cls) {
        var e = { tagName: tag.toUpperCase(), className: cls || '', textContent: '', attrs: {},
          getAttribute: function (k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
          setAttribute: function (k, v) { this.attrs[k] = String(v); },
          insertAdjacentElement: function (where, node) { LIST.splice(LIST.indexOf(this) + 1, 0, node); node.parent = LIST; },
          remove: function () { LIST.splice(LIST.indexOf(this), 1); } };
        e.classList = { contains: function (c) { return (e.className || '').split(' ').indexOf(c) >= 0; } };
        return e;
      }
      var dt = el('dt'), dd = el('dd'), term = el('button', 'gloss-term is-inline');
      var LIST = [dt, dd];
      term.attrs['data-def'] = 'What total debt is.'; term.attrs['aria-expanded'] = 'false';
      dt.nextElementSibling = dd;
      Object.defineProperty(dd, 'nextElementSibling', { get: function () { return LIST[LIST.indexOf(dd) + 1] || null; } });
      term.closest = function (sel) {
        return sel === '[data-gloss-open]' ? term : sel === 'dt[data-gloss-pair]' ? dt : null;
      };
      document.createElement = function (tag) { return el(tag); };
      var gloss = CLICKS.filter(function (fn) { return String(fn).indexOf('data-gloss-open') >= 0; });
      gloss[0]({ target: term });
      R.opened = LIST.map(function (n) { return n.tagName + (n.className ? '.' + n.className : '') + (n.textContent ? ':' + n.textContent : ''); });
      gloss[0]({ target: term });
      R.closed = LIST.map(function (n) { return n.tagName; });
    """, before="""
      var CLICKS = [];
      document.addEventListener = function (type, fn) { if (type === 'click') CLICKS.push(fn); };
    """)
    assert out["opened"] == ["DT", "DD", "DD.gloss-inline:What total debt is."], out
    assert out["closed"] == ["DT", "DD"]
    assert ".kv > .gloss-inline { grid-column: 1 / -1;" in CSS


def test_an_opened_definition_reads_as_prose_wherever_it_opens():
    """A table header is right-aligned and nowrap, a tile is centred."""
    block = CSS[CSS.index(".gloss-inline {\n  display: block;"):]
    block = block[:block.index("\n}\n")]
    for rule in ("text-align: left;", "white-space: normal;", "text-transform: none;", "font-weight: 400;"):
        assert rule in block, rule
    assert "table.data .gloss-inline { min-width: 12rem; max-width: 20rem; }" in CSS


# ------------------------------------------------------------ the three fixes

def test_growth_from_a_loss_is_not_a_percentage():
    g = fundamentals._growth
    assert g([50.0, -100.0]) is None, "a loss turning into a profit read as -150%"
    assert g([-50.0, -100.0]) is None, "a narrowing loss read as a 50% fall"
    assert g([-50.0, 0.0]) is None
    assert g([110.0, 100.0]) == 10.0
    assert g([-50.0, 100.0]) == -150.0, "a profit turning into a loss is a fall from a real base"


def test_the_notes_say_nothing_about_growth_from_a_loss():
    raw = {"income_annual": {"periods": ["2025", "2024"],
                             "rows": {"Total Revenue": [1e9, 9e8], "Net Income": [5e7, -1e8]}}}
    out = fundamentals.analyse_financials(raw)
    assert out["growth"]["net_income_yoy_pct"] is None
    assert not any("net income" in n.lower() for n in out["notes"]), out["notes"]
    assert out["growth"]["revenue_yoy_pct"] == pytest.approx(11.11, abs=0.01)


def test_insiders_holdings_are_not_called_float():
    out = _render()
    assert "Held by insiders" in out["company"] and "Insider-held float" not in out["company"]


def test_every_dividend_on_record_is_counted(monkeypatch):
    dates = pd.date_range("2000-03-15", periods=100, freq="QS-MAR")
    divs = pd.Series([0.25] * 100, index=dates)

    class Ticker:
        def __init__(self, sym):
            self.dividends = divs
            self.splits = pd.Series([], dtype=float)

    import yfinance
    monkeypatch.setattr(yfinance, "Ticker", Ticker)
    extras._CACHE.pop("actions:ZZCOUNT", None)
    out = extras.corporate_actions(None, "ZZCOUNT")
    assert out["payment_count"] == 100
    assert len(out["dividends"]) == 24, "the list shown is still the latest 24"


def test_the_tile_shows_the_count_not_the_list():
    out = _render()
    html = out["extras"]
    at = html.index(">Payments on record</dfn>")
    tile = html[at:at + 400]
    assert '<span class="value ">254</span>' in tile, tile
    assert "Most recent 24 shown" in tile, "and the list still says how much of it is shown"


# ------------------------------------------------------- the tab that rendered blank

def test_no_holders_is_an_empty_list_not_a_dict():
    """Found checking these definitions in a browser: KO's holders call came
    back empty, `or {}` made the empty list a dict, the page called .slice on
    it, and the whole Financials tab rendered blank."""
    out = fundamentals.analyse_ownership({"summary_6m": {"Purchases": {"shares": 10, "transactions": 1}}},
                                         {"breakdown": {}, "top_holders": []})
    assert out["available"] is True and out["top_holders"] == []
    assert fundamentals.analyse_ownership({"summary_6m": {"x": {}}}, None)["top_holders"] == []


def test_the_tab_renders_whatever_shape_the_holders_come_in():
    out = _jsc("""
      explainPolicy = function () { return 'on_demand'; };
      CO.ownership.top_holders = {};
      try { R.html = renderCompany(CO); } catch (e) { R.err = String(e); }
    """)
    assert "err" not in out, out.get("err")
    assert "Largest Reported Holders" in out["html"] or "Largest reported holders" in out["html"]


# ------------------------------------------------- the panel that went missing

def _lifted(names, decls, scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    fn = lambda n: re.search(r"^(?:async )?function " + n + r"\([^\n]*\) \{.*?^\}", APP, re.M | re.S).group()
    decl = lambda n: re.search(r"^(?:let|const) " + n + r" = .*?;", APP, re.M | re.S).group()
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n"
           "var STATE = {ticker: 'AAPL'};\nvar pending = [];\n"
           "function getJSON(url) { return new Promise(function (resolve, reject) {"
           " pending.push({url: url, resolve: resolve, reject: reject}); }); }\n"
           + "\n".join(decl(d) for d in decls) + "\n" + "\n".join(fn(n) for n in names)
           + "\n(async function () {\n" + scenario + "\n})().then(function () { print('TEST_OK'); },"
           " function (e) { print('FAIL ' + e + '\\n' + e.stack); });")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_a_second_caller_waits_for_the_request_in_flight():
    """loadSwing starts the request; opening Financials met the cache guard,
    painted before the data existed and was never repainted."""
    _lifted(["loadExtras", "extrasForTicker"], ["extrasInFlight"], """
      loadExtras();                                   // loadSwing's, fire and forget
      var painted = null;
      var tab = loadExtras().then(function () { painted = extrasForTicker(); });
      assert(pending.length === 1, 'asked twice: ' + pending.length);
      await Promise.resolve(); await Promise.resolve();
      assert(painted === null, 'the tab painted before the data existed');
      pending[0].resolve({ticker: 'AAPL', actions: {}});
      await tab;
      assert(painted && painted.ticker === 'AAPL', 'repainted once it landed');
    """)


def test_the_last_stocks_extras_are_never_this_ones():
    _lifted(["loadExtras", "extrasForTicker"], ["extrasInFlight"], """
      var first = loadExtras();
      pending[0].resolve({ticker: 'AAPL', actions: {dividends: ['aapl']}}); await first;
      STATE.ticker = 'KO';
      var second = loadExtras();
      assert(extrasForTicker() === null, 'showed AAPL dividends under KO');
      // A late reply for a stock the reader has left does not land.
      STATE.ticker = 'MSFT';
      var third = loadExtras();
      pending[1].resolve({ticker: 'KO'}); await second;
      assert(STATE.extras.ticker === 'AAPL', 'the KO reply replaced it after the reader moved on');
      pending[2].resolve({ticker: 'MSFT'}); await third;
      assert(extrasForTicker().ticker === 'MSFT');
    """)


def test_the_tab_renders_only_this_stocks_extras():
    view = APP[APP.index("function renderFinancialsView(force) {"):]
    view = view[:view.index("\n}\n")]
    assert "renderExtras(STATE.extras)" not in view
    assert view.count("renderExtras(extrasForTicker())") == 2


def test_the_insider_tables_value_is_not_a_moving_averages():
    """TH_HINTS explains a bare "Value" header as "The current value of the
    average, in dollars", which the insider table picked up."""
    out = _render()
    by_label = dict(_terms(out["company"]))
    assert "average" not in by_label["Value"] and "transaction" in by_label["Value"]
    # Two tables say "Shares", and each means its own.
    shares = [d for label, d in _terms(out["company"]) if label == "Shares"]
    assert len(shares) == 2 and any("Form 4" in d for d in shares) and any("quarterly" in d for d in shares)
