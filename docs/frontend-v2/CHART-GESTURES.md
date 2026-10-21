# Chart gestures: who gets which input

This is written before the shared charts change. It is a condition of the Classic parity migration (owner, 2026-10-21): measuring must not unexpectedly take page scrolling, chart panning or existing interactions, and every mode has an explicit activation, a button and a keyboard route. The check scripts (`~/Optic/work/classic-parity/b2a_check.py`, `b2b_check.py`) assert each rule below.

## Shared time-series charts (`ui/chart.js` lineChart)
These charts don't pan or zoom: Overview's year chart, RSI and MACD on Options, Investing's drawdown and P/E, Macro, Indices, Compare, Brokerage, Retirement, Home's panels, and Milo's price chart.

| Input | Result | Never |
|---|---|---|
| Mouse hover | Readout of the bar under the pointer (crosshair and tip) | n/a |
| Mouse drag | Nothing. A plain drag selects nothing and scrolls nothing | Measuring by surprise |
| Shift + mouse drag | Measure from the press to the pointer; the result stays until the pointer leaves, Escape, or the next press | n/a |
| Measure button (corner of the chart; shown on hover and focus, always shown on touch screens) | Turns measuring on for this chart: the next drag measures without Shift. Pressing it again turns it off | n/a |
| Touch, vertical swipe | Scrolls the page (`touch-action: pan-y`); a reading the touch started goes when the page takes it | Being held by the chart |
| Touch, tap or horizontal slide | Readout of the bar under the finger; the tip sits above the finger and inside the chart, its dates on a second line when it is wider than the chart | n/a |
| Touch, hold about 400 ms without moving, then slide | Measure from where the finger held. While a finger is on any chart nothing on the page is selectable (`html.pc-touching`), so iOS's long press cannot select nearby text or show its loupe; checked in Mobile Safari on the iOS simulator | Starting a measure from a scroll |
| Touch, two fingers | Measure between the two fingers | Zooming the page (pinch is off over a chart, as in Classic; zoom works everywhere else) |
| Touch, with the Measure button on | A drag measures (`touch-action: none` only while it is on) | n/a |
| Keyboard, chart focused | Left and Right step one bar (Shift for 20), Home and End jump; M toggles measuring, which anchors at the current bar, then the arrows move the other end; Escape clears; Tab leaves as usual; the gold focus ring shows for the keyboard, never after a mouse press | Taking Tab, or any key while a field has focus |
| Event marker (earnings E) | Click, Enter or Space opens its detail, as before | Starting a measure |

A measurement reads: start and end dates, the change, and the percent change. Percent change is shown only for series that are levels: prices, values, ratios and multiples. A series already in percent or points (drawdown, short-volume share, returns, RSI, MACD) shows the change in points only, because a percent of a percent misleads. The result is announced once to assistive technology when the measurement ends.

Grouped bars and periods (`ui/bars.js`) and the payoff chart (`ui/xychart.js`) get no measuring: their periods are categories, not a time axis. They keep hover, tap and the keys.

## The Chart tab and price charts (`ui/pricechart.js`)
These are zoomable: the Chart tab, Investing's weekly chart, and the price chart B2b adds to Options.

| Input | Result | Never |
|---|---|---|
| Vertical wheel or trackpad stroke | Zooms only when the gesture started on the plot. A stroke that starts elsewhere keeps scrolling the page as it crosses the chart, and the gesture lock lasts 200 ms | Trapping the page's scroll |
| Horizontal trackpad stroke, or Shift + wheel | Pans | Zooming |
| Pinch (ctrl + wheel, or Safari's gesture events) | Zooms about the pointer at the pinch's own rate | Zooming the page |
| Mouse drag | Pans, after a few pixels of slack | n/a |
| Shift + drag, or the Measure tool | Measures | n/a |
| Drag on the price scale (a strip over the axis gutter, `touch-action: none`) | Up stretches the prices, down squeezes them; double-click, Fit or Reset zoom puts them back | n/a |
| Touch, one finger | A tap reads the bar. Direction lock over the first 8 px: sideways pans, up and down scrolls the page and clears the reading; hold about 300 ms, then the finger reads the bars and the page holds still. With every bar shown, sideways reads | n/a |
| Touch, two fingers | Pinch zooms about the midpoint, and moving both pans; holding one finger, then adding a second, measures; the finger left after a pinch pans | Zooming the page |
| Measure button (bottom left of the price; on hover and focus, always on touch screens) | Turns measuring on: the next drag measures instead of panning | n/a |
| Touch screens | Zoom out and zoom in buttons beside it, 44 px, about the latest bar | Gestures as the only route |
| Keyboard, chart focused | Left and Right read the bars (Shift pans), Up and Down stretch the price scale, + and − zoom, Home and End jump, M measures from the current bar (the arrows move its other end), Escape cancels a drag, then a measurement, then a tool | n/a |
| Keyboard, page-wide (the Chart tab) | Cmd or Ctrl + Z undoes a drawing change, with Shift or Y redoes, Delete removes the selected drawing, from the page or a toolbar button | Acting while a field, an open menu, a dialog or another widget has focus |
| Drawing tools | A press places a point; a drag from it places the next where it lifts, so a two-point shape takes one drag (or two presses); Escape mid-drag puts a moved drawing back | n/a |

Live ticks never move the view the reader set, and wait while a drag is in progress.
