// WaveTrend's pane under the price and what followed its signals (app/analytics/wavetrend.py has the method).
// pages/chart-studies.js fetches /api/indicators/wavetrend on the chart's own bars and lays it on them (onBars);
// ui/pricechart.js lays the pane out with the others and draws it (paneSvg), so it pans, zooms and reads at the
// crosshair with the candles; the chart's foot shows evidenceBlock while the pane is on.
// The pane: WT1 a blue area against zero with its edge, WT2 a lighter cyan line, the overbought and oversold
// levels dashed and zero solid, a dot at each cross on WT2 (green up, red down, larger when strong) and a line
// between the two WT2 pivots of each divergence, dotted on to the bar where it became known.
import { num, signed, esc, clean, fullDate, isNum } from '../core/format.js';
import { html } from '../core/dom.js';
import { how } from './states.js';

const fin = (v) => typeof v === 'number' && Number.isFinite(v);
const stamp = (d) => Date.parse(String(d).length === 10 ? `${d}T00:00:00Z` : d);

/** The pane's name with its three lengths, the way the MACD pane names its own. */
export function paneName(wt) {
  const p = (wt && wt.params) || {};
  return `WaveTrend ${p.channel_len || 9}, ${p.avg_len || 12}, ${p.ma_len || 3}`;
}

/** An /api/indicators/wavetrend answer laid on the chart's bars: WT1 and WT2 bar for bar (null where the answer has
 *  no bar or no reading), each cross and divergence at its bar's index; a mark whose bar is not on the chart is
 *  left out, and a divergence's tick where its confirming bar is not. */
export function onBars(ans, bars) {
  const at = new Map(bars.map((b, j) => [b.t, j]));
  const to = (ans.timestamps || []).map((d) => { const j = at.get(stamp(d)); return j === undefined ? -1 : j; });
  const wt1 = bars.map(() => null), wt2 = bars.map(() => null);
  to.forEach((j, i) => { if (j < 0) return; const a = (ans.wt1 || [])[i], b = (ans.wt2 || [])[i]; if (fin(a)) wt1[j] = a; if (fin(b)) wt2[j] = b; });
  const on = (i) => (Number.isInteger(i) && i >= 0 && i < to.length ? to[i] : -1);
  const crosses = (ans.crosses || []).map((x) => ({ at: on(x.i), type: x.type, strong: !!x.strong })).filter((x) => x.at >= 0 && fin(wt2[x.at]));
  const divs = (ans.divergences || []).map((d) => ({ type: d.type, a: on((d.from || {}).i), b: on((d.to || {}).i), known: on((d.confirmed || {}).i) }))
    .filter((d) => d.a >= 0 && d.b >= 0 && fin(wt2[d.a]) && fin(wt2[d.b]));
  return { wt1, wt2, crosses, divs, levels: ans.levels || {}, params: ans.params || {} };
}

/** The pane's marks for the bars from..to, placed by X, between p.y0 and p.y1; `right` is where the price axis
 *  starts, `cross` the crosshair's bar (-1 for none: the title then reads the last bar in view), `clip` an id. */
export function paneSvg(p, wt, { from, to, X, right, cross = -1, clip }) {
  const ob = (wt.levels.overbought || [53, 60]).filter(fin), os = (wt.levels.oversold || [-53, -60]).filter(fin);
  // a scale symmetric about zero, wide enough for the outer levels and every value in view
  let mx = Math.max(1, ...ob.map(Math.abs), ...os.map(Math.abs));
  for (let i = from; i <= to; i++) [wt.wt1[i], wt.wt2[i]].forEach((v) => { if (fin(v)) mx = Math.max(mx, Math.abs(v)); });
  mx *= 1.08;
  const Y = (v) => p.y0 + (1 - (v + mx) / (2 * mx)) * (p.y1 - p.y0), y = (v) => Y(v).toFixed(1), x = (i) => X(i).toFixed(1);
  const line = (vals) => { let d = '', pen = false; for (let i = from; i <= to; i++) { const v = vals[i]; if (!fin(v)) { pen = false; continue; } d += `${pen ? 'L' : 'M'}${x(i)} ${y(v)}`; pen = true; } return d; };
  let o = '';
  // zero solid, the levels dashed; a level is labelled at the axis only where its label clears the others
  const placed = [];
  [[0, 'wt-z'], [ob[0], 'wt-lv'], [os[0], 'wt-lv'], [ob[1], 'wt-lv'], [os[1], 'wt-lv']].filter(([v]) => fin(v)).forEach(([v, cls]) => {
    o += `<line class="g ${cls}" x1="0" x2="${right}" y1="${y(v)}" y2="${y(v)}"/>`;
    const ly = Y(v) + 4;
    if (placed.every((q) => Math.abs(q - ly) >= 11)) { placed.push(ly); o += `<text class="ax" x="${right + 6}" y="${ly.toFixed(1)}">${esc(num(v, 0))}</text>`; }
  });
  o += `<defs><clipPath id="${clip}"><rect x="0" y="${p.y0}" width="${right}" height="${p.y1 - p.y0}"/></clipPath></defs><g clip-path="url(#${clip})">`;
  // WT1 against zero, a run at a time (a bar with no reading ends one)
  const z = y(0); let run = [];
  const shut = () => { if (run.length) o += `<path class="wt-a" d="M${run[0][0]} ${z}${run.map(([a, b]) => `L${a} ${b}`).join('')}L${run[run.length - 1][0]} ${z}Z"/>`; run = []; };
  for (let i = from; i <= to; i++) { if (fin(wt.wt1[i])) run.push([x(i), y(wt.wt1[i])]); else shut(); }
  shut();
  o += `<path class="ov wt1" d="${line(wt.wt1)}"/><path class="ov wt2" d="${line(wt.wt2)}"/>`;
  wt.divs.forEach((d) => {
    if (d.b < from || d.a > to) return;
    const k = d.type === 'bullish' ? 'u' : 'd', vb = y(wt.wt2[d.b]);
    o += `<line class="wt-dv ${k}" x1="${x(d.a)}" y1="${y(wt.wt2[d.a])}" x2="${x(d.b)}" y2="${vb}"/>`;
    if (d.known > d.b) o += `<line class="wt-dv wt-dk ${k}" x1="${x(d.b)}" y1="${vb}" x2="${x(d.known)}" y2="${vb}"/><line class="wt-dv ${k}" x1="${x(d.known)}" y1="${(Number(vb) - 4).toFixed(1)}" x2="${x(d.known)}" y2="${(Number(vb) + 4).toFixed(1)}"/>`;
  });
  wt.crosses.forEach((c) => { if (c.at < from || c.at > to) return; o += `<circle class="wt-x ${c.type === 'bullish' ? 'u' : 'd'}${c.strong ? ' big' : ''}" cx="${x(c.at)}" cy="${y(wt.wt2[c.at])}" r="${c.strong ? 4 : 2.2}"/>`; });
  o += '</g>';
  // SVG collapses runs of spaces, so the values are set off with a colon and a comma
  const at = cross >= 0 ? cross : to, vals = [fin(wt.wt1[at]) ? `WT1 ${num(wt.wt1[at], 1)}` : '', fin(wt.wt2[at]) ? `WT2 ${num(wt.wt2[at], 1)}` : ''].filter(Boolean);
  o += `<text class="pane-t" x="6" y="${p.y0 + 12}">${esc(paneName(wt))}${vals.length ? `: ${esc(vals.join(', '))}` : ''}</text>`;
  return o;
}

/** A sentence for the chart's accessible summary: the values on the last bar in view and the marks in view. */
export function summaryLine(wt, from, to) {
  const a = wt.wt1[to], b = wt.wt2[to];
  const xs = wt.crosses.filter((c) => c.at >= from && c.at <= to), strong = xs.filter((c) => c.strong).length;
  const ds = wt.divs.filter((d) => d.b >= from && d.a <= to).length;
  const now = fin(a) && fin(b) ? `WT1 ${num(a, 1)} and WT2 ${num(b, 1)} on the last bar shown` : 'no reading on the last bar shown';
  return ` ${paneName(wt)}: ${now}; ${xs.length} cross${xs.length === 1 ? '' : 'es'} in view, ${strong} strong, and ${ds} divergence${ds === 1 ? '' : 's'}.`;
}

const BARS = { '1m': 'one-minute', '5m': 'five-minute', '15m': '15-minute', '30m': '30-minute', '60m': 'hourly', '4h': 'four-hour', '1d': 'daily', '1wk': 'weekly' };
const day = (s) => fullDate(String(s || '').slice(0, 10));

/** What followed each kind of signal on these bars, against entries at random, for the chart's foot. */
export function evidenceBlock(ans) {
  const ev = ans && ans.evidence;
  if (!ev || !Array.isArray(ev.signals)) return '';
  const hs = (ev.horizons || []).map(String), win = ev.window || {};
  const cell = (r, h) => {
    const m = (r.by_horizon || {})[h] || {};
    if (!isNum(m.mean_pct)) return html`<td class="num t-muted">${m.too_few ? `Too few (${num(m.n, 0)})` : 'Not measured'}</td>`;
    return html`<td class="num"><b>${signed(m.mean_pct, 2)}</b>, ${num(m.hit_rate_pct, 0)}% ${r.direction === 'up' ? 'rose' : 'fell'}<small>Random ${signed(m.baseline_mean_pct, 2)}, ${num(m.baseline_hit_rate_pct, 0)}%</small><small>Beat ${num(m.beats_random_pct, 0)}% of draws</small></td>`;
  };
  return html`<section class="ch-wt" aria-labelledby="ch-wt-h">
    <h3 class="t-h3 ch-wt-h" id="ch-wt-h">What followed WaveTrend's signals</h3>
    <p class="ch-wt-find">${clean(ev.finding || '')}</p>
    <div class="tscroll"><table class="t ch-wt-t">
      <thead><tr><th scope="col">Signal</th><th scope="col" class="num">Count</th>${hs.map((h) => html`<th scope="col" class="num">${h} bars on</th>`)}</tr></thead>
      <tbody>${ev.signals.map((r) => html`<tr><th scope="row">${r.label}</th><td class="num">${num(r.count, 0)}</td>${hs.map((h) => cell(r, h))}</tr>`)}</tbody>
    </table></div>
    <p class="asof">On ${num(win.bars, 0)} ${BARS[ans.interval] ? `${BARS[ans.interval]} ` : ''}bars, ${day(win.from)} to ${day(win.to)}. Each figure is the mean change in the close from the bar the signal became known, with the share that moved its way; random is every bar of the same window.</p>
    ${how(html`<p>${clean(ev.method || '')}</p>`)}
  </section>`;
}
