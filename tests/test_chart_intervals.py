"""The bar size, from one minute to one week.

Two entries used to be choosable here, Daily and Weekly. The intraday sizes
were not choosable at all: picking the 1D or 5D *range* pill got you 5-minute
or 15-minute bars because the server said so, and the toolbar reported the
resolution you had been handed on a disabled pill.

Every pair in INTRADAY_SPECS was probed against the live feed on AAPL before
being offered, because an interval the provider silently refuses renders as
"no intraday bars" and reads as a broken symbol rather than an unsupported
timeframe. Measured through the API: 1m 249 bars, 5m 362, 15m 563, 30m 282,
1h 449, 4h 499. The 4h case is worth naming -- it is not in yfinance's
documented interval list and does come back as genuine four-hour buckets,
exactly 04:00:00 apart, two per session at 09:30 and 13:30.
"""

from __future__ import annotations

import re

from app.main import INTRADAY_SPECS

APP = open("static/app.js", encoding="utf-8").read()


def _code(text):
    """Comments stripped. A comment explaining why a variable must NOT be
    assigned here quotes that variable, and a bare substring check cannot
    tell the explanation from the assignment -- this is the fourth time that
    has caught a test in this repo."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"^\s*//.*$", "", text, flags=re.M)


def _block(marker):
    start = APP.index(marker)
    return APP[start:APP.index("\n];", start)]


def _entries(block):
    return [ln for ln in block.splitlines() if "key: '" in ln]


def _keys(block):
    return re.findall(r"key: '([^']+)'", block)


LADDER = _block("const CHART_INTERVALS = [")
RANGES = _block("const CHART_RANGES = [")


# ------------------------------------------------------------- the ladder


def test_the_ladder_runs_from_one_minute_to_one_week():
    labels = re.findall(r"label: '([^']+)'", LADDER)
    assert labels == ["1m", "5m", "15m", "30m", "1h", "4h", "1D", "1W"]


def test_an_intraday_rung_is_keyed_in_minutes():
    """The obvious key for one minute is `1m`, and `1m` is already a RANGE key
    meaning one MONTH. Both lists are searched by the same string with
    `.find`, so whichever came first would win and the 1M pill would have
    loaded a one-minute chart. Caught in a browser: the range row rendered
    `1m` for a month directly under an interval row rendering `1m` for a
    minute."""
    intraday = [ln for ln in _entries(LADDER) if "intraday: true" in ln]
    assert len(intraday) == 6
    for ln in intraday:
        key = re.search(r"key: '([^']+)'", ln).group(1)
        assert key.isdigit(), "{} is not a minute count".format(key)


def test_no_interval_key_collides_with_a_range_key():
    """The bug above, as a property rather than an example."""
    intraday_keys = {re.search(r"key: '([^']+)'", ln).group(1)
                     for ln in _entries(LADDER) if "intraday: true" in ln}
    daily_ranges = {re.search(r"key: '([^']+)'", ln).group(1)
                    for ln in _entries(RANGES) if "intraday: true" not in ln}
    clash = intraday_keys & daily_ranges
    assert not clash, "same string means two things: {}".format(sorted(clash))


def test_every_rung_is_also_a_range_so_the_existing_guards_apply():
    """`isIntradayRange` gates the whole daily-overlay path -- the averages,
    Fibonacci, RSI and MACD are all suppressed through it. An intraday size
    that is not a range would be drawn with daily overlays over minute bars."""
    range_intraday = {re.search(r"key: '([^']+)'", ln).group(1)
                      for ln in _entries(RANGES) if "intraday: true" in ln}
    for ln in _entries(LADDER):
        if "intraday: true" not in ln:
            continue
        key = re.search(r"key: '([^']+)'", ln).group(1)
        assert key in range_intraday, "{} is not a range".format(key)


# --------------------------------------------------- the two variables

def test_an_intraday_choice_never_lands_in_chart_interval():
    """`chartInterval` holds `daily` or `weekly` and twenty-six places read it
    as `=== 'weekly'` meaning "otherwise daily": they compute 20-day averages,
    label them "20-day SMA" and measure RSI in days. Writing `5` into it would
    have every one of them describing a five-minute chart in days."""
    handler = APP.split("const wsInt = evt.target.closest('[data-ws-interval]');", 1)[1]
    handler = handler[:handler.index("\n  const wsTl")]
    assert "if (spec && spec.intraday) {" in handler
    intra = _code(handler.split("if (spec && spec.intraday) {", 1)[1].split("} else {", 1)[0])
    assert "chartRange = key;" in intra
    assert "chartInterval" not in intra, "an intraday key must not reach chartInterval"
    other = handler.split("} else {", 1)[1]
    assert "chartInterval = key;" in other


def test_leaving_an_intraday_rung_lands_on_a_daily_range():
    """Otherwise the chart stays on the intraday series and the 1D button you
    just pressed appears to do nothing."""
    handler = APP.split("const wsInt = evt.target.closest('[data-ws-interval]');", 1)[1]
    handler = handler[:handler.index("\n  const wsTl")]
    tail = handler.split("} else {", 1)[1]
    assert "if (isIntradayRange(chartRange)) {" in tail
    assert "chartRange = '6m'" in tail


# -------------------------------------------------- client against server


def test_every_rung_the_client_offers_the_server_serves():
    """Both directions of the same contract. A rung with no spec answers
    "Unknown range", which renders as a symbol with no intraday data."""
    offered = {re.search(r"key: '([^']+)'", ln).group(1)
               for ln in _entries(LADDER) if "intraday: true" in ln}
    for key in offered:
        assert key in INTRADAY_SPECS, "the client offers {} and the server has no spec".format(key)
    # And the reverse, allowing the two legacy aliases a stored preference
    # may still ask for.
    assert set(INTRADAY_SPECS) - offered == {"1d", "5d"}


def test_the_client_declares_what_the_feed_calls_each_rung():
    """`chartIntervalLabel` compares the two so it can show the rung's own
    name when they agree and the feed's answer when they do not."""
    for ln in _entries(LADDER):
        if "intraday: true" not in ln:
            continue
        key = re.search(r"key: '([^']+)'", ln).group(1)
        feed = re.search(r"feed: '([^']+)'", ln)
        assert feed, "{} does not declare the feed's name".format(key)
        assert feed.group(1) == INTRADAY_SPECS[key]["interval"], \
            "{}: client says {!r}, server asks the feed for {!r}".format(
                key, feed.group(1), INTRADAY_SPECS[key]["interval"])


def test_the_window_each_rung_is_fetched_with_is_named_for_a_reader():
    """`chartRange` is a bare minute count on an intraday rung, so the legend
    read "4h · 240"."""
    spoken = {"1d": "1 day", "5d": "5 days", "1mo": "1 month",
              "3mo": "3 months", "1y": "1 year"}
    for ln in _entries(LADDER):
        if "intraday: true" not in ln:
            continue
        key = re.search(r"key: '([^']+)'", ln).group(1)
        window = re.search(r"window: '([^']+)'", ln).group(1)
        assert window == spoken[INTRADAY_SPECS[key]["period"]], \
            "{}: says {!r}, server fetches {!r}".format(
                key, window, INTRADAY_SPECS[key]["period"])


def test_the_server_only_asks_the_feed_for_intervals_it_serves():
    """Probed on AAPL before being offered; anything outside this set has not
    been, and an interval the provider refuses returns no bars at all."""
    probed = {"1m", "5m", "15m", "30m", "60m", "4h"}
    for key, spec in INTRADAY_SPECS.items():
        assert spec["interval"] in probed, \
            "{} asks for {!r}, which was never probed".format(key, spec["interval"])


# ------------------------------------------- what the Options chart offers


def test_the_options_chart_is_not_offered_the_ladder():
    """That tab reaches intraday through its own 1D and 5D range pills and
    has no ladder behind them. Listing the minute rungs in its Interval
    select would write `5` into `chartInterval`, which is the variable
    twenty-six places read as daily-or-weekly.

    Measured after scoping: the select offers 1D and 1W, and the range row
    offers 1D 5D 1M 3M 6M 1Y All -- exactly what it offered before."""
    assert "const SWING_INTERVALS = CHART_INTERVALS.filter((i) => !i.intraday);" in APP
    assert "const SWING_RANGES = CHART_RANGES.filter((r) => !r.intraday || r.legacy);" in APP
    assert "${SWING_INTERVALS.map((i) => `<option" in APP
    assert "rangePills(SWING_RANGES, chartRange, 'data-chart-range'" in APP
    # Derived, not written out: a rung added to the ladder must not be able to
    # appear on a tab with no way to serve it.
    assert "SWING_INTERVALS = [" not in APP and "SWING_RANGES = [" not in APP


def test_the_options_chart_keeps_the_two_legacy_intraday_pills():
    """`legacy: true` is what keeps 1D and 5D in its range row while the
    minute rungs are filtered out of it."""
    legacy = [ln for ln in _entries(RANGES) if "legacy: true" in ln]
    assert len(legacy) == 2
    keys = {re.search(r"key: '([^']+)'", ln).group(1) for ln in legacy}
    assert keys == {"1d", "5d"}
    for ln in legacy:
        assert "intraday: true" in ln, "a legacy pill is still an intraday range"


def test_a_stored_preference_cannot_carry_a_rung_into_chart_interval():
    """The minute rungs are valid interval KEYS and are never valid values
    for `chartInterval`. Validating a restored preference against the whole
    ladder would put a stored `5` straight back into it on the next load."""
    line = [ln for ln in APP.splitlines()
            if "=== savedInterval" in ln and "chartInterval = savedInterval" in ln]
    assert line, "the restore guard is gone"
    assert "SWING_INTERVALS.some" in line[0], line[0].strip()
