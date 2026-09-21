"""The price header, after the Quote panel was folded into it.

Reported as "this is a repetition": the Quote panel sat below a header that
already carried every row in it. Removing it was only safe if the four things
it alone had came with it -- ATR (14), the expected two-week range, the sector,
and the extended-hours caveat that says the other figures are measured from the
regular close.

**Executed, not grepped, and the first version of this was grepped.** A source
check for `vol.atr14` passed while ATR rendered nothing at all: the mutation
that proved it replaced the *guard* `Number.isFinite(vol.atr14)` with `false`,
and the identifier was still sitting in the template further down the same
expression. Asserting on output is the only form of this test that means what
its name says.

Skipped where `jsc` is absent, like the other executed client tests here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")

APP = open("static/app.js", encoding="utf-8").read()


def _jsc():
    return JSC if os.path.exists(JSC) else shutil.which("jsc")


QUOTE = {
    "ticker": "INTC", "name": "Intel Corporation", "exchange": "NasdaqGS",
    "sector": "Technology",
    "price": 122.98, "change": 14.38, "change_pct": 13.24,
    "day_low": 114.93, "day_high": 124.73, "prev_close": 108.60,
    "volume": 114_700_000, "avg_volume": 109_000_000,
    "fifty_two_low": 28.73, "fifty_two_high": 142.35,
    "market_cap": 650_090_000_000,
}
PAYLOAD = {
    "ticker": "INTC",
    "quote": QUOTE,
    "technicals": {"volatility": {"atr14": 6.576319, "atr_pct": 5.356617,
                                  "expected_2w_move_pct": 16.939112}},
}
EXT = {"kind": "After hours", "price": 126.50, "pct": 2.86}


@pytest.fixture(scope="module")
def rendered():
    exe = _jsc()
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      if (typeof renderPriceHead !== 'function') {
        print('RESULT:' + JSON.stringify({error: 'renderPriceHead is not defined'}));
      } else {
        var payload = %s, ext = %s;
        function strip(h) {
          return h.replace(/<[^>]*>/g, ' ')
                  .replace(/&amp;/g, '&').replace(/&#39;/g, "'")
                  .replace(/&nbsp;/g, ' ')
                  .replace(/\\s+/g, ' ').trim();
        }
        var open = renderPriceHead(payload, null);
        var after = renderPriceHead(payload, ext);
        // No volatility at all: the two inherited facts must simply be absent
        // rather than rendering "NaN" or an empty row.
        var bare = JSON.parse(JSON.stringify(payload));
        delete bare.technicals;
        print('RESULT:' + JSON.stringify({
          open: {html: open, text: strip(open)},
          after: {html: after, text: strip(after)},
          bare: {html: renderPriceHead(bare, null),
                 text: strip(renderPriceHead(bare, null))}
        }));
      }
    """ % (json.dumps(PAYLOAD), json.dumps(EXT))
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                          timeout=180)
    blob = proc.stdout + proc.stderr
    assert "RESULT:" in blob, blob[-1500:]
    body = json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])
    assert "error" not in body, body
    return body


# ------------------------------------------- what the Quote panel alone had


def test_it_renders_the_average_daily_range(rendered):
    """How far this name moves on an ordinary day is what decides whether
    today's change is large, and it is the fact a price header usually omits.
    INTC's ATR is 6.58, which is 5.4% -- against a 13.2% move today."""
    text = rendered["open"]["text"]
    assert "ATR" in text and "(14)" in text
    assert "6.58" in text
    assert "5.4% a day" in text, "the percent is what makes the absolute legible"


def test_it_renders_the_expected_two_week_range(rendered):
    assert "Expected 2-week range" in rendered["open"]["text"]
    # 16.939112 to one decimal. Asserted on the rounded string rather than the
    # input, because rounding is the half a reader sees.
    assert "\u00b116.9%" in rendered["open"]["text"]


def test_it_renders_the_sector_beside_the_exchange(rendered):
    """Where `securityHeader`'s own `sec-meta` puts it, so the two agree. It
    is not on this page otherwise: the Options tab renders the header
    compact, which drops the whole identity line."""
    assert "NasdaqGS · Technology" in rendered["open"]["text"]


def test_the_extended_hours_caveat_only_appears_out_of_hours(rendered):
    """The one line saying every other figure is measured from the regular
    close rather than from the after-hours print. In hours there is no
    after-hours print, so the caveat would be a claim about nothing."""
    assert "px-ext-note" not in rendered["open"]["html"]
    assert "px-ext-note" in rendered["after"]["html"]
    text = rendered["after"]["text"]
    assert "extended-hours trade" in text
    assert "122.98 close" in text, "it has to name the price it means"


# ------------------------------------------------ and what it still carries


@pytest.mark.parametrize("fact", [
    "INTC", "Intel Corporation", "122.98", "+14.38", "+13.24%",
    "Day range", "114.93", "124.73", "Prev close", "108.60",
    "Volume", "1.1× average", "52 weeks", "28.73", "142.35",
    "Market cap",
])
def test_it_still_carries_everything_it_did_before(rendered, fact):
    """The nine readings that were duplicated. Removing the panel must not
    have quietly removed any of these from the survivor."""
    assert fact in rendered["open"]["text"], fact


def test_missing_volatility_drops_the_rows_rather_than_printing_nan(rendered):
    """A cold cache and a thinly traded symbol both reach this. `fmt(undefined)`
    would put a dash or a NaN in a header that is otherwise all real numbers."""
    text = rendered["bare"]["text"]
    assert "ATR" not in text
    assert "Expected 2-week range" not in text
    assert "NaN" not in text and "undefined" not in text
    # The rest of the header is unaffected.
    assert "122.98" in text and "Market cap" in text
