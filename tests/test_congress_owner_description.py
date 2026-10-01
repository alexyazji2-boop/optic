"""Whose each House trade was, and what the filer said about it.

Asked for after Nancy Pelosi's BE purchases came up: "add the owner and
description to the table". The form has an Owner column (SP spouse, JT joint,
DC dependent child, blank for the member's own) and a description line under
each row ("Purchased 100 call options with a strike price of $100 and an
expiration date of 6/17/27."). The parser kept neither, so a spouse's options
read as the member's shares.

Measured on the 2026 archive: 2,821 rows, the same rows as before; 219 a
spouse's, 410 joint, 384 a child's (330 of them one member's), 237 with a
description. The text below is the shape pypdf returns: each label prints as
its first letter and NULs, rows break across lines, and a long description
wraps.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.analytics import congress

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

F = "F\x00\x00\x00\x00\x00 S\x00\x00\x00\x00\x00: New"
D = "D\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00: "
SO = "S\x00\x00\x00\x00\x00\x00\x00\x00\x00 O\x00: "
HEAD = ("Name: Hon. Nancy Pelosi\nStatus: Member\nState/District: CA11\n"
        "ID Owner Asset Transaction\nType\nDate Notification\nDate\nAmount Cap.\nGains >\n$200?\n")

FILING = HEAD + "\n".join([
    "SP Bloom Energy Corporation Class A", "Common Stock (BE) [ST]",
    "P 07/24/2026 07/24/2026 $1,000,001 -", "$5,000,000", F,
    D + "Purchased 10,000 shares.",
    "SP Bloom Energy Corporation Class A", "Common Stock (BE) [OP]",
    "P 07/24/2026 07/24/2026 $1,000,001 -", "$5,000,000", F,
    # Wrapped, as the form wraps a long one.
    D + "Exercised 50 call options purchased 1/14/25 (5,000 shares) at a strike price of $150 with an expiration date of",
    "1/16/26.",
    # The member's own, under an account line, with nothing said about it.
    "Boston Scientific Corporation Common", "Stock (BSX) [ST]",
    "S 08/01/2026 08/02/2026 $1,001 - $15,000", F,
    SO + "150 Main Street Trust > Bank of America",
    "JT Paychex, Inc. - Common Stock", "(PAYX) [ST]",
    "P 08/03/2026 08/04/2026 $15,001 -", "$50,000", F,
    D + "Corporate Bond",
    "DC CDW Corporation - Common Stock", "(CDW) [ST]",
    "S (partial) 08/05/2026 08/06/2026 $1,001 - $15,000", F,
    "Filing ID #20035143",
])


def _rows():
    return congress._parse_text(FILING)["rows"]


def test_each_row_says_whose_it_was():
    assert [(r["ticker"], r["owner"]) for r in _rows()] == [
        ("BE", "SP"), ("BE", "SP"), ("BSX", None), ("PAYX", "JT"), ("CDW", "DC")]


def test_each_row_carries_what_the_filer_said_about_it():
    got = {(r["ticker"], r["asset_kind"]): r["description"] for r in _rows()}
    assert got[("BE", "ST")] == "Purchased 10,000 shares."
    # Both lines of a wrapped one, and nothing of the next row's name.
    assert got[("BE", "OP")] == ("Exercised 50 call options purchased 1/14/25 (5,000 shares) at a "
                                 "strike price of $150 with an expiration date of 1/16/26.")
    assert got[("BSX", "ST")] is None, "the account line is not a description"
    # An unfinished one ends where the next asset's name begins.
    assert got[("PAYX", "ST")] == "Corporate Bond"
    assert got[("CDW", "ST")] is None


def test_the_rows_are_the_rows_they_were():
    """Owner and description are read beside the rows, not instead of them:
    on the whole 2026 archive the parser finds the same 2,821."""
    rows = _rows()
    assert [r["transaction"] for r in rows] == [
        "purchase", "purchase", "sale", "purchase", "partial sale"]
    assert rows[0]["amount_low"] == 1000001 and rows[-1]["amount_high"] == 15000
    assert congress._parse_text(FILING)["member"] == "Hon. Nancy Pelosi"


def test_a_parse_from_before_owners_were_kept_is_read_again():
    assert congress.PARSE_VERSION == 2


# ------------------------------------------------------------------ the table


def _row_html(trade):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      print('RESULT:' + JSON.stringify({ html: insCongressRow(%s) }));
    """ % json.dumps(trade)
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])["html"]


TRADE = {"member": "Hon. Nancy Pelosi", "ticker": "BE", "transaction": "purchase", "side": "buy",
         "amount_low": 1000001, "amount_high": 5000000, "traded_iso": "2026-07-24",
         "filed": "2026-08-21", "disclosure_lag_days": 0}


def test_the_table_shows_the_owner_and_the_description():
    html = _row_html({**TRADE, "owner": "SP",
                      "description": "Purchased 100 call options with a strike price of $100 and an expiration date of 6/17/27."})
    assert ">Spouse</td>" in html
    assert ('<td class="ins-desc">Purchased 100 call options with a strike price of $100 '
            "and an expiration date of 6/17/27.</td>") in html
    own = _row_html({**TRADE, "owner": None, "description": None})
    assert ">Self</td>" in own and "None given" in own
    assert ">Child</td>" in _row_html({**TRADE, "owner": "DC"})
    assert ">Joint</td>" in _row_html({**TRADE, "owner": "JT"})


def test_the_description_is_escaped():
    """It is the filer's free text."""
    html = _row_html({**TRADE, "owner": "SP", "description": "Sold <b>all</b>."})
    assert "&lt;b&gt;all&lt;/b&gt;" in html and "<b>all</b>" not in html


def test_the_header_has_both_columns_in_the_rows_order():
    app = (ROOT / "static/app.js").read_text()
    head = app[app.index("<thead><tr><th>Member</th><th title=\"Whose account"):]
    head = head[:head.index("</tr></thead>")]
    order = [head.index(x) for x in (">Member<", ">Owner<", ">Symbol<", ">Transaction<",
                                     ">Description<", ">Amount<")]
    assert order == sorted(order)


def test_a_symbols_own_page_shows_them_too():
    """The dossier's Congressional disclosures table is the same trades."""
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      print('RESULT:' + JSON.stringify({ html: renderCongress({ available: true, count: 1, buys: 1,
        sells: 0, amount_low: 1000001, amount_high: 5000000, trades: [%s] }) }));
    """ % json.dumps({**TRADE, "owner": "SP", "description": "Purchased 10,000 shares."})
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    html = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])["html"]
    assert "<th>Owner</th>" in html and "<th>Description</th>" in html
    assert ">Spouse</td>" in html and '<td class="ins-desc">Purchased 10,000 shares.</td>' in html
    assert '<div class="table-scroll"><table class="data">' in html
