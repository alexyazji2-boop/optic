// Dossier, Investing. The long-term picture: the trend score and what it is
// built from, return and risk, the weekly structure, drawdown, the multiple
// against its own history, fair value and stars, the discounted cash flow
// summary, valuation scenarios, and accumulation levels.
//
// Data: /api/longterm (trend score, returns, weekly bars), /api/pe-history,
// /api/fair-value, /api/valuation (DCF), /api/valuation-inputs. None calls a
// model. The trend score is labelled as in the Overview, beside the
// business-and-price case, so the two long-term readings never blur.
import { $, html, render as draw, raw } from '../core/dom.js';
import { CLASSIC } from '../core/classic.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { sections } from '../ui/sections.js';
import { num, signed, money, compact, clean, capFirst, shortDate, fullDate, isNum, score100, ordinal, dir } from '../core/format.js';
import { lineChart, meter, mountCharts } from '../ui/chart.js';
import { createPriceChart } from '../ui/pricechart.js';
import { nyDate, weekMonday } from '../ui/studies.js';
import { icon } from '../ui/icons.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { core, header, tabs, isFund, livePrice } from './dossier-frame.js';
import * as VS from './valuation-scenarios.js';
import { kindOf, can } from '../core/instrument.js';
let lp = null;   // the header's price refresh (dossier-frame livePrice), stopped in dispose()

const RANGES = { '1Y': 52, '3Y': 156, '5Y': 260, '10Y': 520, All: Infinity };
let D = {}, live = true, mainEl = null;
// The weekly structure chart (I6): the Chart tab's interactive chart, kept across the page's repaints so a pan or a
// zoom survives the other sections arriving; built again only for another symbol, interval, range or history.
let WK = { chart: null, host: null, key: '' };
// The classic keys, so a choice made in either app holds in the other: the style and the range are the long-term
// chart's own (optic.lt.*, ranges in lower case, 'candle' for candles); retracements, support and resistance and
// volume are the flags the classic Options chart shares.
const LT_STYLE_KEY = 'optic.lt.mode', LT_RANGE_KEY = 'optic.lt.range', LT_IV_KEY = 'optic.lt.interval';
const LVL_KEYS = { fib: 'optic.chart.fib.v2', sr: 'optic.chart.sr.v2', vol: 'optic.chart.vol.v2' };
const MONTHS = { '1Y': 12, '3Y': 36, '5Y': 60, '10Y': 120, All: Infinity };
const ltRange = () => ({ '1y': '1Y', '3y': '3Y', '5y': '5Y', '10y': '10Y', all: 'All' })[String(setting(LT_RANGE_KEY, '5y')).toLowerCase()] || '5Y';
const ltIv = () => (setting(LT_IV_KEY, 'weekly') === 'monthly' ? 'monthly' : 'weekly');
const ltStyle = () => ({ candle: 'candles', line: 'line', area: 'area' })[setting(LT_STYLE_KEY, 'line')] || 'line';
const lvlOn = (k) => (k === 'vol' ? setting(LVL_KEYS.vol, 'on') !== 'off' : setting(LVL_KEYS[k], 'off') === 'on');

function setting(k, d) { try { return localStorage.getItem(k) || d; } catch (e) { return d; } }
function setSetting(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private */ } }

const sma = (vals, n) => vals.map((_, i) => (i + 1 < n ? null : vals.slice(i + 1 - n, i + 1).reduce((a, b) => a + b, 0) / n));
function monthly(dates, closes) {
  const out = []; dates.forEach((d, i) => { const m = d.slice(0, 7); if (out.length && out[out.length - 1].m === m) out[out.length - 1] = { m, d, c: closes[i] }; else out.push({ m, d, c: closes[i] }); });
  return out;
}
const kv = (rows, n = 3) => html`<dl class="kv" style="--kv:${n}">${rows.filter(Boolean).map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
const ask = (sym, label, q) => miloButton(label, { ask: q, context: `${sym} Dossier, Investing`, symbol: sym });
const pct = (v, dp = 1) => (isNum(v) ? `${num(v, dp)}%` : 'n/a');

/* ---------------- sections ---------------- */
function trend(sym) {
  const h = (D.lt || {}).holding;
  if (D.ltErr) return failed('The long-term model', D.ltErr, { retry: 'lt' });
  if (!h) return skeleton('lines', 4, 'Loading the long-term model');
  const sc = h.conviction_scale || {};
  const s = score100(h.conviction_score, sc.min_possible, sc.max_possible);
  const st = ((D.fv || {}).stars) || {}, vh = h.valuation_history || {};
  const conv = (((D.fw || {}).long_term) || {}).conviction || {};
  const clash = s !== null && s >= 60 && ((st.available && st.stars <= 2) || (vh.available && vh.percentile >= 80));
  return html`<section class="section" aria-labelledby="lt-h">
    <div class="section-head"><div><h2 class="t-h2" id="lt-h">Long-term trend score, from price history</h2><p class="section-sub">How the ${kindOf(sym, D) === 'fund' ? 'fund' : 'stock'} has traded over the years: trend, strength against the S&amp;P 500 and risk. It does not measure valuation.</p></div>${ask(sym, 'Ask Milo about this score', `What is ${sym}'s long-term trend score built from, and what does it leave out?`)}</div>
    <div class="figure"><p class="t-display-m">${s === null ? 'n/a' : num(s, 0)} <small class="t-muted">of 100</small></p><p class="delta"><span>${capFirst(h.conviction || '')} conviction</span><span class="t-muted">${capFirst((h.long_trend || {}).phase || '')}</span></p></div>
    <p><b>The model's rule:</b> ${clean(h.plan || '')}</p>
    ${clash ? html`<p class="reconcile"><b>Read it beside the price.</b> The score is built from trend and the five-year record${st.available ? `, while the price earns ${st.stars} of 5 stars against its own usual valuation` : ''}${vh.available ? ` and the P/E sits at the ${ordinal(vh.percentile)} percentile of its own history` : ''}.${conv.label ? ` The business-and-price case on the Overview reads ${conv.label}.` : ''}</p>` : ''}
    ${(h.data_quality || {}).warnings && h.data_quality.warnings.length ? h.data_quality.warnings.map((w) => html`<p class="stale">${clean(w)}</p>`) : ''}
    <div class="tscroll"><table class="t"><thead><tr><th>Factor</th><th>Type</th><th>Points</th><th>Why</th></tr></thead>
      <tbody>${(h.conviction_factors || []).map((f) => html`<tr><td>${f.label}</td><td>${f.kind}</td><td>${signed(f.points, 0, '')}</td><td style="text-align:left">${clean(f.detail)}</td></tr>`)}
      <tr><td><b>Total</b></td><td></td><td><b>${signed(h.conviction_score, 0, '')}</b></td><td style="text-align:left" class="t-muted">On a scale of ${sc.min_possible} to ${sc.max_possible}; ${num(s, 0)} of 100 when mapped.</td></tr></tbody></table></div>
  </section>`;
}

function returnsRisk() {
  const h = (D.lt || {}).holding; if (!h) return '';
  const hz = h.horizons || {}, r = h.risk || {};
  return html`<section class="section" aria-labelledby="rr-h"><h2 class="t-h2" id="rr-h">Return and risk</h2>
    ${kv([['1 year', html`<span class="${dir(hz.return_1y_pct)}">${signed(hz.return_1y_pct, 1)}</span>`], ['3 years, a year', signed(hz.cagr_3y_pct, 1)], ['5 years, a year', signed(hz.cagr_5y_pct, 1)], ['Against the S&P 500, 5 years', html`${signed(h.excess_cagr_5y_pct, 1)} a year <span class="t-muted">(index ${signed(h.benchmark_cagr_5y_pct, 1)})</span>`]], 4)}
    ${kv([['Volatility, a year', pct(r.annualised_vol_pct)], ['Downside volatility', pct(r.downside_vol_pct)], ['Return per unit of risk', num(r.sharpe_proxy, 2)], ['Downside-adjusted', num(r.sortino_proxy, 2)], ['Beta to the S&P 500', num(r.beta_vs_spy, 2)], ['Correlation', num(r.correlation_vs_spy, 2)], ['Best day', signed(r.best_day_pct)], ['Worst day', signed(r.worst_day_pct)], ['Up days', pct(r.pct_positive_days)]], 3)}
  </section>`;
}

function weekly(sym) {
  const h = (D.lt || {}).holding; if (!h) return '';
  const lt = h.long_trend || {}, range = ltRange(), iv = ltIv(), style = ltStyle(), unit = iv === 'monthly' ? 'month' : 'week';
  const lv = [['fib', 'Retracements'], ['sr', 'Support and resistance'], ['vol', 'Volume']], n = lv.filter(([k]) => lvlOn(k)).length;
  return html`<section class="section" aria-labelledby="ws-h"><div class="section-head"><div><h2 class="t-h2" id="ws-h">Weekly structure</h2><p class="section-sub">${clean(lt.guidance || '')} The 40-${unit} and 200-${unit} averages are the lines that separate secular bull phases from bear ones.</p></div></div>
    <div class="ctools lt-tools" role="toolbar" aria-label="Weekly structure settings">
      <div class="seg" role="group" aria-label="Interval">${[['weekly', 'Weekly'], ['monthly', 'Monthly']].map(([k, l]) => html`<button type="button" data-v2-lt-iv="${k}" aria-pressed="${iv === k}">${l}</button>`)}</div>
      <div class="seg" role="group" aria-label="Range">${Object.keys(RANGES).map((k) => html`<button type="button" data-v2-lt-range="${k}" aria-pressed="${range === k}">${k}</button>`)}</div>
      <div class="seg seg-ic" role="group" aria-label="Style">${[['candles', 'Candles', 'candles'], ['line', 'Line', 'lineChart'], ['area', 'Area', 'area']].map(([k, l, ic]) => html`<button type="button" data-v2-lt-style="${k}" aria-pressed="${style === k}" aria-label="${l}" title="${l}">${icon(ic)}</button>`)}</div>
      <details class="menu lt-lvl"><summary class="btn btn-sm">Technical levels${n ? html` <span class="ch-count">${n}</span>` : ''}</summary><div class="menu-body">
        ${lv.map(([k, l]) => html`<label class="check"><input type="checkbox" data-v2-lt-lvl="${k}" ${lvlOn(k) ? 'checked' : ''}> <span>${l}</span></label>`)}
        <p class="menu-help">Retracements of the three-year range, and support and resistance found on these weekly bars, as bands.</p>
      </div></details>
    </div>
    <div id="lt-chart" class="lt-chart">${skeleton('chart')}</div>
    <p class="legend-line" id="lt-legend">${ltLegend()}</p>
    <p class="asof" id="lt-note"></p>
    <p class="asof">Drag to pan, scroll or pinch to zoom, arrow keys to step through each ${unit}.</p>
    ${kv([['Against the 40-week average', signed(lt.vs_40w_sma)], ['Against the 200-week average', signed(lt.vs_200w_sma)], ['Weekly RSI', num(lt.weekly_rsi, 1)], ['40-week slope over 3 months', signed(lt.slope_40w_pct_3m)]], 4)}
  </section>`;
}
// The bars for the chart: twelve years of weekly bars from the long-term model (all of them once All has loaded
// them), rolled up to calendar months when asked; and the two averages over the whole history, cut with the rest.
function weeklyBars() {
  const h = (D.lt || {}).holding; if (!h) return null;
  const src = ltRange() === 'All' && D.allWeeks ? D.allWeeks : ((h.long_trend || {}).series || {});
  let bars = (src.dates || []).map((d, i) => ({ t: Date.parse(`${String(d).slice(0, 10)}T00:00:00Z`), d: String(d).slice(0, 10), o: Number(src.open[i]), h: Number(src.high[i]), l: Number(src.low[i]), c: Number(src.close[i]), v: Number((src.volume || [])[i]) || 0 }))
    .filter((b) => isNum(b.c) && b.c > 0 && Number.isFinite(b.t)).map((b) => Object.assign(b, { o: isNum(b.o) ? b.o : b.c, h: isNum(b.h) ? b.h : b.c, l: isNum(b.l) ? b.l : b.c }));
  if (ltIv() === 'monthly') bars = monthlyBars(bars);
  return bars;
}
export function monthlyBars(bars) {
  const out = [];
  bars.forEach((b) => {
    const m = b.d.slice(0, 7), last = out[out.length - 1];
    if (last && last.m === m) Object.assign(last, { h: Math.max(last.h, b.h), l: Math.min(last.l, b.l), c: b.c, v: last.v + b.v });
    else out.push({ m, t: b.t, d: b.d, o: b.o, h: b.h, l: b.l, c: b.c, v: b.v });
  });
  return out;
}
// What the chart draws besides the bars, from the switches: the style, volume, retracements and the bands.
function weeklyLooks() {
  const h = (D.lt || {}).holding || {}, lv = h.levels || {};
  const fib = lvlOn('fib') ? (h.accumulation_zones || []).filter((z) => isNum(z.price) && z.ratio !== null && z.ratio !== undefined).map((z) => ({ price: z.price, cls: 'fib', label: `${num(z.ratio * 100, 1)}% ${num(z.price)}`, end: true, crowd: true })) : [];
  const bands = lvlOn('sr') ? (lv.support_resistance || []).filter((x) => isNum(x.band_low) && isNum(x.band_high)).slice(0, 8).map((x) => ({ lo: x.band_low, hi: x.band_high, role: x.role, label: `${x.role === 'resistance' ? 'Resistance' : 'Support'} ${num(x.price)}` })) : [];
  return { style: ltStyle(), panes: { volume: lvlOn('vol'), rsi: false, macd: false }, lines: fib, bands };
}
function mountWeekly() {
  const slot = $('#lt-chart', mainEl);
  if (!slot) return;
  const bars = weeklyBars();
  if (!bars) return;
  if (bars.length < 5) { draw(slot, empty('Not enough weekly history to draw', 'The long-term model has fewer than five weeks of bars for this symbol.')); return; }
  const iv = ltIv(), range = ltRange(), key = [D.sym, iv, range, ltRange() === 'All' && D.allWeeks ? 'all' : 'model', bars.length].join('|');
  const looks = weeklyLooks();
  if (WK.chart && WK.key === key && WK.host) { slot.replaceWith(WK.host); WK.chart.set(looks); note(bars); return; }
  if (WK.chart) WK.chart.destroy();
  const host = document.createElement('div'); host.id = 'lt-chart'; host.className = 'lt-chart'; slot.replaceWith(host);
  const closes = bars.map((b) => b.c), win = iv === 'monthly' ? MONTHS[range] : RANGES[range];
  WK.chart = createPriceChart(host, Object.assign({
    bars, intraday: false, overlays: {}, levels: {}, events: [], drawings: [], tool: 'select',
    series: [{ values: sma(closes, 40), cls: 'o1' }, { values: sma(closes, 200), cls: 'o2' }],
    window: Number.isFinite(win) ? win : bars.length, label: `${D.sym}, ${iv} bars`, when: (t) => barName(iv, t),
    height: Math.round(Math.max(300, Math.min(440, (host.clientWidth || 800) * 0.42))),
  }, looks));
  WK.host = host; WK.key = key;
  note(bars);
}
// Why an average starts partway across, or has no line: it has no value until it has as many bars as its length.
const monthYear = (t) => new Date(t).toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
const NY_HOUR = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', hourCycle: 'h23' });
/**
 * A bar named for the time it covers. The model's weeks carry their Friday's date and the full history's their
 * Monday's, so the current week could read as a date still to come: a week is named by its Monday, a month by
 * itself, and the one still trading says so (a week until its Friday's 4pm close in New York).
 */
export function barName(iv, t, now = Date.now()) {
  const today = nyDate(now), d = new Date(t).toISOString().slice(0, 10);
  if (iv === 'monthly') return `${monthYear(t)}${d.slice(0, 7) === today.slice(0, 7) ? ', so far' : ''}`;
  const monday = Date.parse(`${weekMonday(d)}T00:00:00Z`), friday = new Date(monday + 4 * 86400000).toISOString().slice(0, 10);
  const open = friday > today || (friday === today && Number(NY_HOUR.format(new Date(now))) < 16);
  return `Week of ${new Date(monday).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })}${open ? ', so far' : ''}`;
}
export function maNote(sym, bars, shown, unit) {
  const first = bars.length - Math.min(bars.length, shown);
  const parts = [40, 200].map((n) => (n > bars.length ? `the ${n}-${unit} has none yet` : n - 1 > first ? `the ${n}-${unit} starts in ${monthYear(bars[n - 1].t)}` : null)).filter(Boolean);
  return parts.length ? `Optic's price history for ${sym} begins in ${monthYear(bars[0].t)}. An average has no value until it has as many ${unit}s of closes as its length, so ${parts.join(' and ')}.` : '';
}
function note(bars) {
  const el = $('#lt-note', mainEl); if (!el) return;
  const iv = ltIv(), win = iv === 'monthly' ? MONTHS[ltRange()] : RANGES[ltRange()];
  el.textContent = maNote(D.sym, bars, Number.isFinite(win) ? win : bars.length, iv === 'monthly' ? 'month' : 'week');
}
// The key under the chart, drawn again when a level is switched without redrawing the menu it was switched in.
function ltLegend() {
  const unit = ltIv() === 'monthly' ? 'month' : 'week', style = ltStyle();
  return html`${style === 'candles' ? html`<span><i class="kup"></i>Up ${unit}</span><span><i class="kdn"></i>Down ${unit}</span>` : html`<span><i></i>Close</span>`}<span><i class="o1"></i>40-${unit} average</span><span><i class="o2"></i>200-${unit} average</span>${lvlOn('fib') ? html`<span><i class="kfib"></i>Retracements</span>` : ''}${lvlOn('sr') ? html`<span><i class="kbs"></i><i class="kbr"></i>Support and resistance</span>` : ''}${lvlOn('vol') ? html`<span><i class="kvol"></i>Volume</span>` : ''}`;
}

function drawdown() {
  const h = (D.lt || {}).holding; if (!h || !h.drawdown) return '';
  const dd = h.drawdown;
  return html`<section class="section" aria-labelledby="dd-h"><h2 class="t-h2" id="dd-h">Drawdown, daily</h2>
    ${kv([['From the high now', signed(dd.current_drawdown_pct, 1)], ['Largest drawdown', html`${signed(dd.max_drawdown_pct, 1)} <span class="t-muted">${fullDate(dd.max_drawdown_date)}</span>`], ['All-time high', html`${num(dd.all_time_high)} <span class="t-muted">${fullDate(dd.ath_date)}</span>`]], 3)}
    <div class="chart-slot" data-chart="dd"></div></section>`;
}
function ddMaker() {
  const dd = (((D.lt || {}).holding) || {}).drawdown; if (!dd) return {};
  const pts = (dd.dates || []).map((d, i) => ({ d: String(d).slice(0, 10), c: Number(dd.series[i]) })).filter((p) => isNum(p.c));
  return { dd: (w) => lineChart(pts, { measure: 'points', msUnit: ' pts', w, h: 170, area: false, dp: 1, label: 'Drawdown from the running high, percent', pad: { t: 12, r: 52, b: 24, l: 0 } }) };
}

function multiple(sym) {
  const pe = D.pe, h = (D.lt || {}).holding || {}, vh = h.valuation_history || {}, rm = h.revenue_multiple || {};
  if (pe === undefined) return html`<section class="section">${skeleton('lines', 3, 'Loading the multiple history')}</section>`;
  return html`<section class="section" aria-labelledby="pe-h"><div class="section-head"><div><h2 class="t-h2" id="pe-h">The multiple against its own history</h2><p class="section-sub">${pe && pe.available ? `${num(pe.weeks / 52, 0)} years of weekly trailing P/E from the company's filings.` : 'No P/E history for this company.'}</p></div>${ask(sym, 'Ask Milo about the multiple', `Is ${sym}'s P/E high against its own history, and why might that be?`)}</div>
    ${pe && pe.available ? html`${kv([['Trailing P/E now', html`${num(pe.pe_current, 1)} <span class="t-muted">${ordinal(pe.pe_percentile)} percentile</span>`], ['Its own median, 5 years', html`${num(pe.pe_median, 1)} <span class="t-muted">quartiles ${num((pe.pe_bands || {})[25], 1)} to ${num((pe.pe_bands || {})[75], 1)}</span>`], ['Cross-check with the quote feed', (pe.anchor || {}).available ? `${num(pe.anchor.provider, 1)} (${pe.anchor.agrees ? 'agrees' : 'differs'})` : 'n/a']], 3)}
      <div class="chart-slot" data-chart="pe"></div><p class="legend-line"><span><i></i>Trailing P/E</span><span><i class="o1"></i>Median</span><span><i class="o3"></i>25th and 75th percentile</span></p>
      ${(pe.revenue_growth || []).length ? html`<details class="more-inline"><summary>Revenue growth, last 8 quarters</summary><div class="tscroll"><table class="t"><thead><tr><th>Quarter</th><th>Revenue</th><th>Growth, year on year</th></tr></thead><tbody>${pe.revenue_growth.slice(-8).map((r) => html`<tr><td>${r.label}</td><td>${compact(r.revenue)}</td><td>${signed(r.growth_pct)}</td></tr>`)}</tbody></table></div></details>` : ''}
      <p class="asof">${clean(pe.method || '')}</p>` : ''}
    ${vh.available ? html`<h3>Fiscal years</h3><p>${capFirst(clean(vh.read || ''))}: ${num(vh.current_pe, 1)} times earnings against a median of ${num(vh.median_pe, 1)} over ${vh.usable_years} years (${signed(vh.premium_to_median_pct, 0)}).</p>
      <div class="tscroll"><table class="t"><thead><tr><th>Fiscal year</th><th>EPS</th><th>Average price</th><th>P/E</th></tr></thead><tbody>${(vh.years || []).map((y) => html`<tr><td>${shortDate(y.period)} ${String(y.period).slice(0, 4)}</td><td>${num(y.eps)}</td><td>${num(y.avg_price)}</td><td>${num(y.pe, 1)}</td></tr>`)}</tbody></table></div>` : ''}
    ${rm.available ? html`<details class="more-inline"><summary>Revenue and the multiple, by fiscal year</summary><div class="tscroll"><table class="t"><thead><tr><th>Year</th><th>Revenue</th><th>P/E</th></tr></thead><tbody>${rm.years.map((y) => html`<tr><td>${y.label}</td><td>${compact(y.revenue)}</td><td>${num(y.pe, 1)}</td></tr>`)}</tbody></table></div><p class="asof">${clean(rm.method || '')}</p></details>` : ''}
  </section>`;
}
function peMaker() {
  const pe = D.pe; if (!pe || !pe.available) return {};
  const pts = (pe.pe_series || []).map((r) => ({ d: r.date, c: r.pe })).filter((p) => isNum(p.c));
  const b = pe.pe_bands || {};
  const flat = (v) => pts.map(() => v);
  return { pe: (w) => lineChart(pts, { w, h: 220, dp: 1, label: 'Trailing P/E, weekly', overlays: [{ values: flat(b[50]), cls: 'o1' }, { values: flat(b[25]), cls: 'o3' }, { values: flat(b[75]), cls: 'o3' }], monthStep: 12, pad: { t: 14, r: 52, b: 24, l: 0 } }) };
}

function fairValue(sym) {
  const d = D.fv;
  if (d === undefined) return html`<section class="section">${skeleton('lines', 3, 'Loading fair value')}</section>`;
  if (!d) return '';
  const fv = d.fair_value || {}, st = d.stars || {}, an = d.analysts || {}, dv = d.dividend || {}, ms = d.morningstar || {};
  const price = (D.quote || {}).price || fv.price;
  return html`<section class="section" aria-labelledby="fv-h"><div class="section-head"><div><h2 class="t-h2" id="fv-h">Fair value and stars</h2><p class="section-sub">${clean(st.note || '')}</p></div>${ask(sym, 'Ask Milo about fair value', `How should I read ${sym}'s fair value range and star rating?`)}</div>
    ${st.available ? html`<p class="stars">${raw(`<svg class="star-row" viewBox="0 0 120 22" aria-hidden="true">${[0, 1, 2, 3, 4].map((i) => `<path class="${i < st.stars ? 'on' : 'off'}" transform="translate(${i * 24} 0)" d="M11 1.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L11 16.4 5.1 19.5l1.2-6.5L1.5 8.4l6.6-.9z"/>`).join('')}</svg>`)}<span class="sr">${st.stars} of 5 stars.</span> <b>${clean(st.word)}</b></p><p class="asof">${clean(st.rule)}</p>` : html`<p><b>No star rating.</b> ${clean(st.reason || '')}</p>`}
    ${fv.available ? html`${!fv.wide ? raw(meter({ lo: fv.low, mid: fv.mid, hi: fv.high, price, w: 420, showMid: true })) : ''}
      ${kv([['Fair value range', `${num(fv.low)} to ${num(fv.high)}`], ['Middle', num(fv.mid)], ['Price now', html`${num(price)} <span class="t-muted">${isNum(fv.gap_to_mid_pct) ? signed(fv.gap_to_mid_pct, 1) + ' against the middle' : ''}</span>`]], 3)}
      ${fv.wide ? html`<p class="stale">${clean(fv.wide_note)}</p>` : ''}<p class="asof">${clean(fv.basis || '')}</p>
      <details class="more-inline"><summary>What this range cannot say</summary><ul class="plain">${(fv.limits || []).map((l) => html`<li>${clean(l)}</li>`)}</ul></details>` : html`<p>${clean(fv.reason || 'No fair value estimate for this company.')}</p>`}
    ${isNum(an.target_mean) ? html`<h3>What analysts say</h3>${kv([['Average target', html`${num(an.target_mean)} <span class="t-muted">${signed(an.upside_pct, 1)}</span>`], ['Range of targets', `${num(an.target_low)} to ${num(an.target_high)}`], ['Ratings', isNum(an.buys) ? `${an.buys} buy, ${an.holds} hold, ${an.sells} sell` : `${num(an.buy_share_pct, 0)}% buy`]], 3)}${an.note ? html`<p class="asof">${clean(an.note)}</p>` : ''}` : ''}
    ${dv.available ? html`<h3>Dividend score: ${dv.score} of 100, ${dv.band}</h3><div class="tscroll"><table class="t"><thead><tr><th>Part</th><th>Value</th><th>Points</th><th>Why</th></tr></thead><tbody>${(dv.parts || []).map((p) => html`<tr><td>${p.label}</td><td>${clean(p.value)}</td><td>${num(p.points, 0)}</td><td style="text-align:left">${clean(p.why)}</td></tr>`)}</tbody></table></div><p class="asof">${clean(dv.method || '')}</p>` : ''}
    ${ms.available ? html`<h3>Morningstar</h3><p>${ms.stars} stars, ${clean(ms.risk_word || ms.risk || '')}. ${clean(ms.note || '')}</p>` : ''}
  </section>`;
}

// A fund has no business to value: its holdings' multiples stand in, labelled as theirs (core/instrument.js).
function fundValuation(sym) {
  const h = (D.lt || {}).holding; if (!h) return '';
  const v = h.valuation || {}, q = D.quote || {};
  const y = isNum(q.dividend_yield) ? q.dividend_yield * 100 : isNum(v.dividend_yield) ? v.dividend_yield * 100 : null;
  return html`<section class="section" aria-labelledby="fvl-h"><div class="section-head"><div><h2 class="t-h2" id="fvl-h">What its holdings cost</h2><p class="section-sub">The fund's holdings, weighted by size. A fund has no fair value range, cash-flow model or P/E history of its own.</p></div></div>
    ${kv([['P/E of the holdings, trailing', num(v.trailing_pe, 1)], ['Price to book', num(v.price_to_book, 2)], ['Distribution yield', isNum(y) ? `${num(y, 2)}%` : 'n/a']])}
    <p class="asof">${clean(v.caveat || '')} Source: Yahoo Finance's fund figures.</p></section>`;
}

function dcf(sym) {
  const v = D.val;
  if (v === undefined) return html`<section class="section">${skeleton('lines', 3, 'Loading the cash flow model')}</section>`;
  if (!v || !v.available) return '';
  const d = v.dcf || {}, sc = v.scenarios || {}, rv = v.reverse || {}, tor = (v.tornado || []).slice(0, 4);
  const price = (v.market || {}).price;
  return html`<section class="section" aria-labelledby="dcf-h"><div class="section-head"><div><h2 class="t-h2" id="dcf-h">Fair-value model, discounted cash flow</h2><p class="section-sub">${clean((((v.classification || {}).models || {}).dcf || {}).name || '')}. ${clean((((v.classification || {}).models || {}).dcf || {}).why || '')}</p></div>
      <a class="btn" href="${CLASSIC}#/${sym}/investing">Edit the model in the classic app</a></div>
    ${kv([['Base case, a share', html`${money(d.per_share)} <span class="t-muted">${isNum(d.upside) ? signed(d.upside * 100, 0) : 'n/a'} against ${num(price)}</span>`], ['Discount rate', isNum(d.discount_rate) ? pct(d.discount_rate * 100, 2) : 'n/a'], ['Share of value after the forecast', isNum(d.terminal_share) ? pct(d.terminal_share * 100, 0) : 'n/a']], 3)}
    <div class="tscroll"><table class="t"><thead><tr><th>Case</th><th>A share</th><th>Against the price</th><th>What it assumes</th></tr></thead>
      <tbody>${['bear', 'base', 'bull'].filter((k) => sc[k]).map((k) => html`<tr><td>${capFirst(k)}</td><td>${money(sc[k].per_share)}</td><td>${isNum(sc[k].upside) ? signed(sc[k].upside * 100, 0) : 'n/a'}</td><td class="l">${clean((v.scenario_text || {})[k] || '')}</td></tr>`)}</tbody></table></div>
    ${(rv.solves || []).length ? html`<h3>What today's price implies</h3><ul class="plain">${rv.solves.map((s) => html`<li>${clean(s.text)} <span class="t-muted">Holding ${clean(s.held)}.</span></li>`)}</ul>` : ''}
    ${tor.length ? html`<h3>What moves the value most</h3><div class="tscroll"><table class="t"><thead><tr><th>Input</th><th>Lower</th><th>Higher</th><th>Swing</th></tr></thead><tbody>${tor.map((t) => html`<tr><td>${t.label}</td><td>${money(t.value_low)}</td><td>${money(t.value_high)}</td><td>${money(t.swing)}</td></tr>`)}</tbody></table></div>` : ''}
    ${(v.warnings || []).map((w) => html`<p class="stale">${clean(w.text || w)}</p>`)}
    <p class="asof">Model output from the company's filings, with stated defaults. The full workspace (assumptions, sensitivity tables, statements, other methods, peers, saved models) is in the classic app.</p>
  </section>`;
}

function scenarios(sym) {
  if (D.vin === undefined) return html`<section class="section">${skeleton('lines', 3, 'Loading valuation inputs')}</section>`;
  if (!D.vin || !D.vin.available) return '';
  return html`<section class="section" aria-labelledby="vs-h"><div class="section-head"><div><h2 class="t-h2" id="vs-h">Valuation scenarios</h2></div>${ask(sym, 'Ask Milo about these scenarios', `Do my ${sym} bear, base and bull assumptions look reasonable against its history?`)}</div>
    ${VS.view(sym, D.vin, D.vsBody, D.vsStatus)}</section>`;
}

function accumulation() {
  const h = (D.lt || {}).holding; if (!h) return '';
  const z = h.accumulation_zones || [], va = h.valuation || {};
  return html`<section class="section" aria-labelledby="ac-h"><h2 class="t-h2" id="ac-h">Valuation and accumulation levels</h2>
    ${kv([['Forward P/E', num(va.forward_pe, 1)], ['Trailing P/E', num(va.trailing_pe, 1)], ['Price to book', num(va.price_to_book, 1)], ['Dividend yield', isNum(va.dividend_yield) ? pct(va.dividend_yield * 100, 2) : 'n/a'], ['Analysts\' average target', num(((h.fundamentals || {}).analyst_target))]], 3)}
    <ul class="plain">${(va.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul><p class="asof">${clean(va.caveat || '')}</p>
    ${z.length ? html`<div class="tscroll"><table class="t"><thead><tr><th>Level</th><th>Price</th><th>Distance</th><th>Role</th></tr></thead><tbody>${z.map((l) => html`<tr><td>${l.label}${l.is_golden ? ' (golden zone)' : ''}</td><td>${num(l.price)}</td><td>${signed(l.distance_pct)}</td><td>${capFirst(l.kind)}</td></tr>`)}</tbody></table></div>
      <p class="asof">Levels where long-term buyers have historically stepped in, from the weekly chart. Not targets and not advice.</p>` : ''}
    <p class="asof">${clean(h.disclaimer || '')}</p></section>`;
}

/* ---------------- page ---------------- */
function paint() {
  if (!live) return;
  const sym = D.sym;
  const keep = document.activeElement && mainEl.contains(document.activeElement) ? document.activeElement : null;
  const keepKey = keep && (keep.name || Object.entries(keep.dataset || {}).map((e) => e.join('=')).join('&'));
  const y = window.scrollY;
  const company = can(kindOf(sym, D)).valuation;
  draw(mainEl, html`<div class="dstick">${header(sym, D, 'long')}${tabs(sym, 'long', { fund: isFund(D) })}</div>
    ${trend(sym)}${returnsRisk()}${weekly(sym)}${drawdown()}${company ? html`${multiple(sym)}${fairValue(sym)}${dcf(sym)}${scenarios(sym)}` : fundValuation(sym)}${accumulation()}`);
  mountCharts(mainEl, Object.assign({}, ddMaker(), peMaker()));
  mountWeekly();
  if (keepKey) {
    const el = keep.name ? mainEl.querySelector(`[name="${CSS.escape(keep.name)}"]`) : null;
    const el2 = el || [...mainEl.querySelectorAll('button')].find((b) => Object.entries(b.dataset).map((e) => e.join('=')).join('&') === keepKey);
    if (el2) el2.focus({ preventScroll: true });
  }
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

export async function render(main, route) {
  live = true; mainEl = main;
  const sym = route.symbol, enc = encodeURIComponent(sym);
  D = { sym };
  store.pushRecent(sym);
  document.title = `${sym} Investing, Optic`;
  if (lp) lp.stop();
  lp = livePrice(main, route.symbol, () => D, 'long', undefined);
  provideContext(() => ({ view: 'long', ticker: sym, quote: D.quote, long_term: D.lt, fair_value: D.fv, valuation: D.val ? { dcf: (D.val.dcf || {}).per_share, scenarios: D.val.scenarios, reverse: D.val.reverse } : null, scenarios: D.vsBody }));
  paint(); wire(main);
  // the strip, folds and Panels (Classic parity B3); the two specialist sections open from Advanced, as Classic's did
  sections(main, 'long', { levels: { 'the multiple against its own history': 2, 'valuation and accumulation levels': 2 }, norm: (t) => { const n = ((main.querySelector('.dhead .name span') || {}).textContent || '').trim(); return n ? t.split(n).join('the company') : t; } });
  const step = (p, ok, bad) => p.then((d) => { if (D.sym === sym) ok(d); }, (e) => { if (D.sym === sym) bad(e); }).finally(() => { if (D.sym === sym) paint(); });
  step(core(sym), (c) => { D.quote = c.quote; D.session = c.session; D.quoteError = c.quoteError; }, () => {});
  step(api.get(`/api/longterm/${enc}?indices=false`, { ttl: 600000, timeout: 60000 }), (d) => { D.lt = d; }, (e) => { D.ltErr = e; });
  // A symbol already known to be a fund skips the company valuation reads it would only show as failures.
  if (kindOf(sym) !== 'fund') {
    step(api.get(`/api/pe-history/${enc}?years=10`, { ttl: 3600000, timeout: 45000 }), (d) => { D.pe = d; }, () => { D.pe = null; });
    step(api.get(`/api/fair-value/${enc}`, { ttl: 600000, timeout: 30000 }), (d) => { D.fv = d; }, () => { D.fv = null; });
    step(api.get(`/api/valuation/${enc}`, { ttl: 600000, timeout: 45000 }), (d) => { D.val = d; }, () => { D.val = null; });
    step(api.get(`/api/valuation-inputs/${enc}`, { ttl: 600000, timeout: 30000 }), (d) => { D.vin = d; }, () => { D.vin = null; });
    step(VS.load(sym), (b) => { D.vsBody = b || null; }, () => {});
  }
  step(api.get(`/api/framework/${enc}?mode=combined`, { ttl: 300000, timeout: 60000 }), (d) => { D.fw = d; }, () => {});
  if (ltRange() === 'All') loadAll();
}
async function loadAll() {
  if (D.allWeeks) return;
  try { D.allWeeks = await api.get(`/api/weekly-bars/${encodeURIComponent(D.sym)}?span=max`, { ttl: 3600000, timeout: 45000 }); } catch (e) { toast('The full weekly history did not load.'); }
  paint();
}
export function dispose() { if (lp) { lp.stop(); lp = null; } live = false; if (WK.chart) WK.chart.destroy(); WK = { chart: null, host: null, key: '' }; }
export const retry = { lt: (m, r) => { api.invalidate('/api/longterm'); render(m, r); } };

function wire(main) {
  // a level switched: the chart, the count and the key change in place, so the menu stays open where it was
  main.addEventListener('change', (e) => {
    const el = e.target.closest('[data-v2-lt-lvl]'); if (!el) return;
    setSetting(LVL_KEYS[el.dataset.v2LtLvl], el.checked ? 'on' : 'off');
    if (WK.chart) WK.chart.set(weeklyLooks());
    const n = ['fib', 'sr', 'vol'].filter(lvlOn).length, sum = $('.lt-lvl > summary', main);
    if (sum) { let c = sum.querySelector('.ch-count'); if (!n && c) c.remove(); else if (n) { if (!c) { c = document.createElement('span'); c.className = 'ch-count'; sum.append(' ', c); } c.textContent = String(n); } }
    const lg = $('#lt-legend', main); if (lg) draw(lg, ltLegend());
  });
  main.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s);
    let b;
    if ((b = t('[data-v2-lt-range]'))) { setSetting(LT_RANGE_KEY, b.dataset.v2LtRange.toLowerCase()); if (b.dataset.v2LtRange === 'All') loadAll(); paint(); return; }
    if ((b = t('[data-v2-lt-iv]'))) { setSetting(LT_IV_KEY, b.dataset.v2LtIv); paint(); return; }
    if ((b = t('[data-v2-lt-style]'))) { setSetting(LT_STYLE_KEY, { candles: 'candle', line: 'line', area: 'area' }[b.dataset.v2LtStyle]); paint(); return; }
    if (t('[data-v2-vs-fill]')) {
      // the classic app's valuationFillFromHistory: one decimal, and the exit
      // P/E from the company's own median multiple when there is one
      const f = $('[data-v2-vs]', main); const hist = (D.vin || {}).history || {};
      const vh = (((D.lt || {}).holding || {}).valuation_history) || {};
      const filled = [];
      const put = (k, v) => { if (!Number.isFinite(v)) return; f[`base.${k}`].value = String(Math.round(v * 10) / 10); filled.push(`base.${k}`); };
      put('growth', (hist.revenue_growth || {}).value); put('margin', (hist.margin || {}).value); put('share_change', (hist.share_change || {}).value);
      if (vh.available && vh.median_pe > 0) put('pe', vh.median_pe);
      const body = VS.readForm(f, D.vsBody);
      body.from_history = [...new Set([...body.from_history, ...filled])];
      D.vsBody = body;
      D.vsStatus = filled.includes('base.pe') ? 'Base case filled from history, exit P/E from its median multiple. Save to keep it.' : 'Base case filled from history. Add an exit P/E, then save.'; paint();
    }
  });
  main.addEventListener('input', (e) => {
    const f = e.target.closest('[data-v2-vs]'); if (!f) return;
    clearTimeout(D.vsT);
    D.vsT = setTimeout(() => {
      D.vsBody = VS.readForm(f, D.vsBody); D.vsStatus = 'Not saved yet.';
      // only the results change while typing, so the caret stays where it is
      const start = VS.startOf(D.vin, D.vsBody);
      VS.CASES.forEach(([c]) => { const o = f.querySelector(`[data-v2-vs-out="${c}"]`); if (o) draw(o, VS.caseOut(start, D.vsBody[c], D.vsBody.shared)); });
      const st = f.querySelector('.vs-status'); if (st) st.textContent = D.vsStatus;
    }, 350);
  });
  main.addEventListener('submit', async (e) => {
    const f = e.target.closest('[data-v2-vs]'); if (!f) return;
    e.preventDefault();
    const body = VS.readForm(f, D.vsBody);
    if (Object.keys(VS.errors(body)).length) { D.vsStatus = 'Not saved: fix the boxes marked first.'; paint(); return; }
    D.vsBody = body; D.vsStatus = await VS.save(D.sym, body); paint();
    toast(D.vsStatus);
  });
}
