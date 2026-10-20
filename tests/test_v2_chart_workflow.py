"""The chart research workflow (backlog task 5, 2026-10-20).

The time axis (ui/timeaxis.js) runs in JavaScriptCore on daily, weekly and hourly bars built here; the page's
wiring is read as text. The chart itself was driven in headless Chrome at 360, 390, 430, 768 and 1440 px
(~/Optic/work/v2-backlog/chart_check.py: bar size kept, a drawing added and moved and undone, its day kept
across bar sizes, two tabs, a tap reading a bar, vertical scrolling over the chart, full screen on a phone).
"""
import json

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
H = 3600000
DAY = 86400000


def axis(tmp_path, body):
    return _run(tmp_path, f"""
      const A = await import('{(JS / "ui/timeaxis.js").as_posix()}');
      // weekdays Mon 5 Oct to Fri 16 Oct 2026 as daily bars (UTC midnight), and 9:30 to 15:30 ET hourly bars on them
      const days = [5, 6, 7, 8, 9, 12, 13, 14, 15, 16].map((d) => Date.UTC(2026, 9, d));
      const daily = days.map((t) => ({{ t }}));
      const hourly = days.flatMap((d) => [0, 1, 2, 3, 4, 5, 6].map((h) => ({{ t: d + (13.5 + h) * {H} }})));   // 13:30 UTC is 9:30 ET in October
      {body}
    """)


def test_a_point_keeps_its_day_across_bar_sizes(tmp_path):
    got = axis(tmp_path, f"""
      const D = A.makeAxis(daily, false), I = A.makeAxis(hourly, true);
      const tue1030 = Date.UTC(2026, 9, 6, 14, 30);      // Tue 6 Oct, 10:30 ET: an hourly point
      const tueDate = Date.UTC(2026, 9, 6);               // Tue 6 Oct as a date: a daily point
      const tueNoon = Date.UTC(2026, 9, 6, 12);           // the same date as the classic app stores it
      print(JSON.stringify({{ onDaily: D.f(tue1030), dateOnDaily: D.f(tueDate), noonOnDaily: D.f(tueNoon),
        dateOnHourly: I.f(tueDate), firstTue: hourly.findIndex((b) => b.t === Date.UTC(2026, 9, 6, 13, 30)) }}));
    """)
    assert got["onDaily"] == 1 and got["dateOnDaily"] == 1 and got["noonOnDaily"] == 1   # Tuesday, not Wednesday
    assert got["dateOnHourly"] == got["firstTue"]                                       # Tuesday's opening bar, not Monday 3:30


def test_past_the_bars_a_line_keeps_its_slope(tmp_path):
    got = axis(tmp_path, """
      const D = A.makeAxis(daily, false);
      const beyond = Date.UTC(2026, 9, 23);   // a week after the last bar: five trading days on
      const before = Date.UTC(2026, 8, 28);   // a week before the first
      print(JSON.stringify({ after: D.f(beyond), before: D.f(before), back: D.t(D.f(beyond)) === beyond,
        weekend: D.f(Date.UTC(2026, 9, 10)) }));
    """)
    assert abs(got["after"] - 14) < 1e-9 and abs(got["before"] + 5) < 1e-9   # extrapolated, not clamped to the edge
    assert got["back"] is True                                               # the inverse returns the moment
    assert 4 < got["weekend"] < 5                                            # a Saturday sits between Friday and Monday


def test_a_dated_event_outside_the_bars_is_not_drawn_on_the_last_one(tmp_path):
    got = axis(tmp_path, """
      const D = A.makeAxis(daily, false);
      print(JSON.stringify([D.bar(Date.UTC(2026, 9, 30)), D.bar(Date.UTC(2026, 9, 14)), D.bar(Date.UTC(2026, 8, 1))]));
    """)
    assert got == [-1, 7, -1]   # the next report is not placed on the last bar


def test_the_page_keeps_the_bar_size_and_says_what_cannot_be_drawn():
    src = (JS / "pages/chart.js").read_text()
    assert "interval: V.wantInterval || V.interval" in src and "d.interval = '60'; //" not in src
    assert "Colours candles: choose Candles to see it." in src and "reports no volume" in src
    assert "Showing daily bars instead." in src                     # no intraday feed: daily, said
    assert "e.key === DRAW_KEY" in src                              # another tab's drawings
    assert "chart.keep()" in src and "D.intra" in src
    pc = (JS / "ui/pricechart.js").read_text()
    assert "svg.style.touchAction = S.tool !== 'select' || sel >= 0 ? 'none' : 'pan-y'" in pc   # the page scrolls over the chart
    assert "if (e.pointerType === 'touch') return;" in pc           # a tap's reading stays when the finger lifts
    assert "touchy ? 20 : 9" in pc and "ext-band" in pc
    assert "lineChart:" in (JS / "ui/icons.js").read_text()


def test_a_mouse_with_no_button_down_never_pans():
    """A press whose release went missing (a right click's menu, another window, a lost capture) left the chart
    panning with the cursor and no button held (owner, 2026-10-20). Driven in headless Chrome by drag_check.py:
    before the fix both cases panned, after it neither does, and a held drag still pans."""
    src = (V2 / "js/ui/pricechart.js").read_text()
    down = src[src.index("svg.addEventListener('pointerdown'"):src.index("svg.addEventListener('pointermove'")]
    move = src[src.index("svg.addEventListener('pointermove'"):src.index("svg.addEventListener('pointerup'")]
    assert "if (e.pointerType === 'mouse' && e.button !== 0) return;" in down
    assert "if (e.pointerType === 'mouse' && e.buttons === 0 && (drag || pointers.has(e.pointerId))) up(e);" in move
    assert "svg.addEventListener('lostpointercapture', up);" in src
    assert src.index("const up = (e) =>") < src.index("svg.addEventListener('pointermove'"), "up is defined before the handler calls it"
    nav = src[src.index("nav.addEventListener('pointerdown'"):src.index("nav.addEventListener('pointerup', navUp)")]
    assert "e.button !== 0" in nav and "e.buttons === 0" in nav and "lostpointercapture" in src.split("nav.addEventListener('pointerup', navUp)")[1].split("\n")[0]
