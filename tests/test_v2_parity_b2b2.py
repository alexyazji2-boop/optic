"""Classic parity, batch B2b, part 2 (2026-10-21): the Chart tab's live ticks and a freshness that comes from the
feed, the price chart on Options with its insider arrows, and the rotation map's readings. The wording of freshness
runs in JavaScriptCore and the quote's new fields in Python; the rest are source checks. The interactions were
driven in headless Chrome (~/Optic/work/classic-parity/b2b2_check.py: a fake clock and served quotes for the live
ticks, touch emulated) and in Mobile Safari on the iOS simulator. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B2b.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"


def test_freshness_comes_from_the_feed_never_from_the_refresh_rate(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "core/marketTime.js").as_posix()}');
      const now = Date.parse('2026-10-21T15:00:00Z'), at = (s) => new Date(now - s * 1000).toISOString();
      const w = (q) => M.sessionFreshness(q, now);
      print(JSON.stringify({{
        live: w({{ trade_time: at(20), delayed_minutes: 0 }}), stale: w({{ trade_time: at(600), delayed_minutes: 0 }}),
        stated: w({{ trade_time: at(900), delayed_minutes: 15 }}), unknown: w({{ trade_time: at(900) }}), bare: w({{}}),
        older: w({{ market_time: at(30), delayed_minutes: 0 }}), prefer: M.tradeTime({{ trade_time: 'a', market_time: 'b' }}) }}));
    """)
    assert got["live"]["word"] == "live" and got["live"]["text"].startswith("Live, last trade "), "no delay stated and a trade 20 s old"
    assert got["stale"]["word"] == "quiet" and got["stale"]["text"].startswith("Last trade "), "no delay, but ten minutes since a trade: not live"
    assert got["stated"]["text"].startswith("Delayed 15 minutes, last trade "), "the feed's own number"
    assert got["unknown"]["text"].startswith("Delayed about 15 minutes, last trade "), "the site's standing wording when the feed is silent"
    assert got["bare"] == {"word": "delayed", "text": "Delayed about 15 minutes"}
    assert got["older"]["word"] == "live", "the older market_time still counts"
    assert got["prefer"] == "a"


def test_a_quote_carries_its_trade_time_and_the_feeds_stated_delay(monkeypatch):
    from app.providers import yf as adapter
    for k in [k for k in adapter._CACHE if k.startswith("quote:ZZTT")]:
        del adapter._CACHE[k]
    p = adapter.YFinanceProvider()
    monkeypatch.setattr(p, "_info", lambda t: {"regularMarketPrice": 101.5, "regularMarketTime": 1792526401, "exchangeDataDelayedBy": 15, "marketState": "REGULAR"})
    q = p.quote("ZZTT")
    assert q["trade_time"] == "2026-10-20T20:00:01+00:00" and q["delayed_minutes"] == 15.0
    assert q["market_time"] is None, "the classic app's field keeps its old meaning (the feed's own wording, or nothing)"
    assert adapter._epoch_iso("10:07AM EDT") is None and adapter._epoch_iso(True) is None and adapter._epoch_iso(0) is None
    for k in [k for k in adapter._CACHE if k.startswith("quote:ZZTT")]:
        del adapter._CACHE[k]


def test_the_chart_tab_ticks_live_and_never_under_the_readers_hand():
    page = (JS / "pages/chart.js").read_text()
    pc = (JS / "ui/pricechart.js").read_text()
    frame = (JS / "pages/dossier-frame.js").read_text()
    assert "lp = livePrice(main, route.symbol, () => D, 'chart', { bar: true, every: 15000, onQuote });" in page
    assert "const { every = 20000, onQuote = null } = opts || {};" in frame and "}, { every });" in frame
    assert "if (!/-USD$|=F$/.test(D.sym) && phase !== 'regular') return;" in page, "regular-hours bars take no extended print"
    assert "if (now >= last.t + Number(iv.key) * 60000) { refetchQuiet(); return; }" in page
    assert "view: edge ? { from: Math.max(0, v.from + grow), to: bars.length - 1 } : v" in page, "only a view at the live edge follows"
    assert "document.title = `${D.sym} ${num(p)}" in page
    assert "if (!(Number(price) > 0) || drag || tg || pointers.size) return false;" in pc, "nothing is drawn under a drag"
    assert "closes[N - 1] = price; Object.assign(ind, indicators());" in pc
    assert "sessionFreshness(q).text" in frame and "Delayed about 15 minutes${last}" not in frame


def test_options_has_a_price_chart_whose_insider_arrows_open_the_filings():
    opt = (JS / "pages/options.js").read_text()
    pc = (JS / "ui/pricechart.js").read_text()
    assert "['Price', (t, s) => priceBody(t, s), null, () => mountPrice()]," in opt
    assert "onInsider: () => { location.hash = `#/insiders?symbol=${encodeURIComponent(sym)}&view=insiders`; }," in opt
    assert "if (pc) { pc.destroy(); pc = null; }" in opt, "stopped when the page goes"
    assert "onInsider: () => { location.hash = `#/insiders?symbol=${encodeURIComponent(D.sym)}&view=insiders`; }," in (JS / "pages/chart.js").read_text()
    assert "if (!touch && drag && drag.mode === 'pan' && !drag.moved && layout && openInsider(flagAt(pt(e))))" in pc, "a press, not a pan"
    assert "else if ((k === 'Enter' || k === ' ') && S.onInsider && flags.some((g) => g.i === cross))" in pc, "and Enter on its bar"


def test_the_rotation_map_reads_by_hover_focus_and_tap():
    mac = (JS / "pages/macro.js").read_text()
    css = (V2 / "css/pages.css").read_text()
    assert 'class="rr-s" data-rr="${k}" tabindex="0" role="img" aria-label="${esc(rrWords(s))}"' in mac
    for ev in ("pointerover", "pointerleave", "pointerdown", "focusin", "focusout", "keydown"):
        assert f"wrap.addEventListener('{ev}'" in mac, ev
    assert mac.count("document.addEventListener('pointerdown'") == 1, "one listener for the page, not one a redraw"
    assert ".rrg .rr-s:focus-visible .rr-dot { stroke: var(--c-focus); stroke-width: 3; }" in css
    assert "const tries = [[cx2 + 6, cy2 - 6, false], [cx2 - 6, cy2 - 6, true], [cx2 + 6, cy2 + 15, false], [cx2 - 6, cy2 + 15, true]];" in mac
