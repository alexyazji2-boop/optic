// Compare: two to four stocks or ETFs side by side, ranked on three horizons
// scored separately, with Optic's take, how they have moved, where each leads,
// and the metric table. One request, GET /api/compare, only when the reader
// presses Compare; no model call. Rules for leaders and ties are the classic
// page's (CMP_GROUPS, cmpLeader, CMP_TIE_POINTS in static/app.js).
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, signed, clean, fullDate, ordinal, isNum } from '../core/format.js';
import { lineChart, mountCharts } from '../ui/chart.js';
import { hbars } from '../ui/bars.js';
import { button as miloButton, provideContext } from '../ui/milo.js';

const MAX = 4, TIE = 5;
export const GROUPS = [
  { title: 'Where it trades', rows: [
    { key: 'price', label: 'Price', kind: 'usd', means: 'Last close.' },
    { key: 'change_pct', label: 'Today', kind: 'pct', means: 'One session. Shown for context and kept out of the position and long-term scores.' }] },
  { title: 'Momentum and trend', rows: [
    { key: 'rsi', label: 'RSI (14)', kind: 'num0', means: 'Above 70 is stretched, below 30 is washed out, 50 is neutral. The middle-upper 50s to 60s is the trending zone.' },
    { key: 'rs_vs_spy', label: 'Versus SPY, 21 sessions', kind: 'pct', lead: 'high', means: 'How much it beat or lagged the index over the last month.' },
    { key: 'vs_sma20', label: 'Above / below the 20-day', kind: 'pct', means: 'Short-term trend. Far above means extended, below means the near-term trend has broken.' },
    { key: 'vs_sma50', label: 'Above / below the 50-day', kind: 'pct', means: 'The line most swing traders watch for whether the trend is intact.' },
    { key: 'vs_sma200', label: 'Above / below the 200-day', kind: 'pct', means: 'The dividing line between a long uptrend and a long downtrend.' },
    { key: 'vs_sma40w', label: 'Above / below the 40-week', kind: 'pct', means: 'The same idea on a weekly chart. Slower, and harder to whipsaw.' }] },
  { title: 'How much it moves', rows: [
    { key: 'atr_pct', label: 'Typical daily range', kind: 'pct_plain', means: 'How far it travels on an average day, as a share of price. Sets how wide a stop has to be.' },
    { key: 'iv_pct', label: 'Implied volatility', kind: 'pct_plain', means: 'What the option market is charging for future movement.' },
    { key: 'hv_pct', label: 'Realised volatility, 20 sessions', kind: 'pct_plain', means: 'What it actually did. Implied above realised means options are priced for more movement than has been happening.' },
    { key: 'annual_vol_pct', label: 'Annualised volatility, up to 12 years', kind: 'pct_plain', lead: 'low', means: 'The same measure over up to 12 years of daily closes, or since listing if shorter.' },
    { key: 'beta_vs_spy', label: 'Beta versus SPY', kind: 'num2', means: 'Roughly how much it moves for a 1% index move. Above 1 amplifies the market, below 1 dampens it.' }] },
  { title: 'What it costs', rows: [
    { key: 'forward_pe', label: 'Forward P/E', kind: 'num1', lead: 'low', means: 'Price against next year’s expected earnings. Lower is cheaper, which is not the same as better. A low multiple often means low expected growth.' },
    { key: 'pe_percentile', label: 'That multiple against its own past', kind: 'pctile', lead: 'low', sub: 'pe_read', means: 'Where today’s multiple sits in this company’s own range. 25th means cheaper than it has been three quarters of the time.' }] },
  { title: 'The multi-year record', rows: [
    { key: 'cagr_5y_pct', label: 'Five-year price return', kind: 'pct', lead: 'high', note: 'per year', means: 'Annualised, so a name listed for five years and one listed for twenty are comparable. Price only: dividends are not included.' },
    { key: 'excess_cagr_5y_pct', label: 'Five-year price return versus SPY', kind: 'pct', lead: 'high', note: 'per year', means: 'The part of that return the index did not give you, both on price alone. Negative means the index would have done better.' },
    { key: 'cagr_per_vol_5y', label: 'Return per unit of volatility, five years', kind: 'num2', lead: 'high', means: 'The five-year price return divided by the volatility of the same five years. Two names can compound at the same rate through very different rides.' },
    { key: 'drawdown_pct', label: 'Below its 12-year high', kind: 'pct', lead: 'high', means: 'Where it sits now against its highest close in up to 12 years of daily history (since listing if shorter). Near the high is a stronger trend; far below it leaves more room to recover.' },
    { key: 'max_drawdown_pct', label: 'Worst fall in 12 years', kind: 'pct_neutral', lead: 'high', means: 'The deepest peak-to-trough in the same up to 12 years. What a bad stretch looks like here.' },
    { key: 'trend_phase', label: 'Multi-year phase', kind: 'text', means: 'Where the weekly chart sits against its long averages.' }] },
  { title: "Optic's own score", rows: [
    { key: 'composite', label: 'Composite', kind: 'signed', lead: 'high', means: 'The swing-tab score for this name. Included so you can see whether it agrees with the horizon ranks above.' }] },
];

export function cell(kind, v, why) {
  if (v === null || v === undefined || v === '') return why ? html`<span class="t-muted">n/a, ${why}</span>` : html`<span class="t-muted" aria-label="not available">n/a</span>`;
  if (kind === 'text') return clean(String(v));
  if (kind === 'usd') return `$${num(v, 2)}`;
  if (kind === 'pct') return html`<span class="${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${signed(v, 2)}</span>`;
  if (kind === 'pct_plain') return `${num(v, 1)}%`;
  if (kind === 'pct_neutral') return `${num(v, 2)}%`;
  if (kind === 'pctile') return `${ordinal(v)}`;
  if (kind === 'num0') return num(v, 0);
  if (kind === 'num1') return num(v, 1);
  if (kind === 'num2') return num(v, 2);
  if (kind === 'signed') return html`<span class="${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${v > 0 ? '+' : ''}${num(v, 0)}</span>`;
  return num(v, 2);
}
/** The row's leader. The server's (`leaders`, analytics/compare.py LEAD_ROWS) is the one rule the table and
 * Optic's take share; this local reading is for a payload from before it, and leaves an exact tie
 * without a leader rather than giving it to the first column. */
export function leader(row, cols, served) {
  if (!row.lead) return null;
  if (served && Object.prototype.hasOwnProperty.call(served, row.key)) return served[row.key] || null;
  const vals = cols.map((r) => r[row.key]).filter((v) => typeof v === 'number' && Number.isFinite(v));
  if (vals.length < 2) return null;
  const best = row.lead === 'high' ? Math.max(...vals) : Math.min(...vals);
  const rest = vals.filter((v) => v !== best);
  if (!rest.length) return null;
  if (vals.filter((v) => v === best).length > 1) return null;
  const runner = row.lead === 'high' ? Math.max(...rest) : Math.min(...rest);
  const scale = Math.max(Math.abs(best), Math.abs(runner));
  if (Math.abs(best - runner) < Math.max(scale * 0.05, 0.25)) return null;
  const hit = cols.find((r) => r[row.key] === best);
  return hit ? hit.ticker : null;
}
// the gap between two scores as the page shows them, one decimal: 70.3 and 65.3 are five points apart
export const gapOf = (a, b) => Math.round((Math.round(a * 10) - Math.round(b * 10))) / 10;
// One tie rule for the prose, the winner cards, the bars and the table (owner, 2026-10-19: "too close to
// separate" sat beside "best" and "#2"). Names within TIE points of the top share first place, so nobody
// is "best" alone then; the server's winner cards use the same 5 points (analytics/compare.py, decisive).
export function standing(ranks) {
  const r = (ranks || []).slice().sort((a, b) => b.score - a.score), out = {};
  if (!r.length) return out;
  if (r.every((x) => x.standing)) { r.forEach((x) => { out[x.ticker] = x.standing; }); return out; }
  const level = r.filter((x) => gapOf(r[0].score, x.score) < TIE);
  r.forEach((x, i) => { out[x.ticker] = level.includes(x) ? (level.length > 1 ? 'level' : 'best') : `#${i + 1}`; });
  return out;
}
export function rankRead(ranks) {
  if (!ranks || ranks.length < 2) return '';
  const [a, b] = ranks, gap = gapOf(a.score, b.score);
  return gap < TIE ? `${a.ticker} and ${b.ticker} are level here (${num(a.score, 0)} against ${num(b.score, 0)}). Too close to separate.` : `${a.ticker} leads, ${num(gap, 0)} points clear of ${b.ticker}.`;
}

// kept for the session, as the classic page keeps STATE.compare
let inputs = ['', ''], result = null, running = false, seq = 0, live = true, mainEl = null, sugg = [], suggT = null, showMeans = false;
const wanted = () => [...new Set(inputs.map((x) => x.trim().toUpperCase()).filter(Boolean))];
// the result on screen is for other names than the boxes now hold (one removed, added or changed)
const stale = () => !!(result && result.available && result.tickers && result.tickers.join(',') !== wanted().join(','));

function controls() {
  const recent = store.recent().filter((s) => !inputs.map((x) => x.toUpperCase()).includes(s)).slice(0, 6);
  return html`<form class="cmp-form" data-v2-cmp-form aria-label="Tickers to compare">
      <div class="cmp-inputs">${inputs.map((v, i) => html`<div class="cmp-in"><label class="field field-sm"><span class="sr">Ticker ${i + 1}</span><input id="cmp-${i}" data-v2-cmp-input="${i}" value="${v}" placeholder="Ticker ${i + 1}" title="A ticker, or a company name" maxlength="24" autocomplete="off" list="cmp-sugg" autocapitalize="characters" spellcheck="false"></label>
        ${inputs.length > 2 ? html`<button type="button" class="icon-btn" data-v2-cmp-drop="${i}" aria-label="Remove ticker ${i + 1}${v ? ` (${v.toUpperCase()})` : ''}">×</button>` : ''}</div>`)}</div>
      <datalist id="cmp-sugg">${sugg.map((s) => html`<option value="${s.symbol}">${s.name || ''}</option>`)}</datalist>
      <div class="cluster"><button type="submit" class="btn btn-primary" ${running ? 'disabled' : ''}>${running ? 'Comparing…' : 'Compare'}</button>${inputs.length < MAX ? html`<button type="button" class="btn" data-v2-cmp-add>Add ticker</button>` : ''}</div>
    </form>
    ${recent.length ? html`<div class="chips chips-scroll" role="group" aria-label="Recently viewed"><span class="t-label">Recently viewed</span>${recent.map((s) => html`<button type="button" class="chip" data-v2-cmp-pick="${s}">${s}</button>`)}</div>` : result ? '' : html`<p class="asof">Nothing is fetched until you press Compare.</p>`}`;
}

function take(c) {
  const t = c.take || {};
  if (!t.available) return '';
  const hz = Object.fromEntries((c.horizons || []).map((h) => [h.id, h]));
  return html`<section class="section" aria-labelledby="ct-h"><div class="section-head"><div><h2 class="t-h2" id="ct-h">Optic's take</h2>${t.agreement ? html`<p class="section-sub">${clean(t.agreement)}</p>` : ''}</div>
      ${miloButton('Ask Milo about this comparison', { ask: `Compare ${c.tickers.join(', ')}. ${t.headline || ''} Which would you look at first for my timeframe, and what is each one's biggest risk?`, context: 'Compare' })}</div>
    <p class="lead-line">${clean(t.headline || '')}</p>
    <div class="cmp-winners">${Object.entries(t.winners || {}).map(([hid, w]) => html`<div class="cmp-win ${w.decisive ? '' : 'is-close'}"><p class="t-label">${(hz[hid] || {}).name || w.name || hid}</p><p class="cmp-win-t">${w.decisive ? w.ticker : 'Level'}</p><p class="t-muted">${w.decisive ? `ahead by ${num(w.gap, 1)} points` : `${num(w.gap, 1)} points apart, under ${TIE}: not a ranking`}</p></div>`)}</div>
    ${(t.standouts || []).length ? html`<ul class="plain">${t.standouts.map((s) => html`<li><b>${s.ticker}</b> has ${clean(s.phrase)}</li>`)}</ul>` : ''}
    ${t.method ? html`<p class="asof">${clean(t.method)}</p>` : ''}</section>`;
}

function perf(c) {
  const p = c.performance || {}, s = p.series || [];
  if (s.length < 2) return html`<section class="section"><h2 class="t-h2">How they have moved</h2><p class="quiet">Not enough shared history to draw.</p></section>`;
  const sorted = s.slice().sort((a, b) => b.change_pct - a.change_pct), best = sorted[0], worst = sorted[sorted.length - 1];
  const verb = (x) => (isNum(x.change_pct) ? `${x.ticker} ${x.change_pct >= 0 ? 'rose' : 'fell'} ${num(Math.abs(x.change_pct), 0)}%` : `${x.ticker}'s move is not reported`);
  return html`<section class="section" aria-labelledby="cp-h"><h2 class="t-h2" id="cp-h">How they have moved</h2>
    <p class="lead-line">${verb(best)} over the period; ${verb(worst)}.</p>
    <p class="section-sub">Each close divided by its close on ${fullDate(p.start)}, times 100, to ${fullDate(p.end)}: ${p.sessions} sessions, one point a week. Price only: dividends are not included.</p>
    <p class="legend-line cmp-legend">${s.map((x, i) => html`<span><i class="c${i + 1}"></i>${x.ticker} ${signed(x.change_pct, 1)}</span>`)}<span><i class="c0"></i>Start, 100</span></p>
    <div class="chart-slot" data-chart="cmp"></div></section>`;
}
function perfChart(c) {
  const p = c.performance, s = p.series;
  return (w) => lineChart(p.dates.map((d, i) => ({ d, c: s[0].values[i] })), {
    w, h: 240, dp: 0, label: `${s[0].ticker} indexed to 100`,
    overlays: [...s.slice(1).map((x, i) => ({ values: x.values, cls: `c${i + 2}` })), { values: p.dates.map(() => 100), cls: 'c0' }],
    summary: `Each name indexed to 100 on ${fullDate(p.start)}: ${s.map((x) => `${x.ticker} ${signed(x.change_pct, 1)}`).join(', ')}.`,
  });
}

function bars(c) {
  const rows = c.rows || [];
  if (rows.length < 2) return '';
  return html`<section class="section" aria-labelledby="cb-h"><h2 class="t-h2" id="cb-h">Where each name leads</h2>
    <p class="section-sub">Every bar is the same 0-100 composite for its horizon, so the bars compare across names within a horizon. Two scores within ${TIE} points are treated as level.</p>
    <div class="cmp-bars">${(c.horizons || []).map((h) => { const r = ((c.ranks || {})[h.id] || []).slice().sort((a, b) => b.score - a.score); const gap = r.length > 1 ? gapOf(r[0].score, r[1].score) : 0;
      return html`<div class="cmp-hz ${gap >= TIE ? 'is-clear' : ''}"><h3>${h.name} <span class="t-muted">${h.horizon}</span></h3><p class="t-muted">${gap < TIE ? `level: ${num(gap, 1)} point${num(gap, 1) === '1.0' ? '' : 's'} apart, under ${TIE}` : `${r[0].ticker} ${num(gap, 1)} points clear`}</p>
        ${raw(hbars(r.map((x) => ({ label: x.ticker, v: Math.max(1, Math.min(100, x.score)) })), { fmt: (v) => num(v, 0), max: 100 }))}</div>`; })}</div></section>`;
}

function grid(c) {
  const rows = c.rows || [];
  if (!rows.length) return '';
  const anyLead = GROUPS.some((g) => g.rows.some((r) => leader(r, rows, c.leaders)));
  const what = (r) => (r.is_benchmark ? 'The benchmark' : r.kind === 'fund' ? 'Fund' : r.sector || '');
  return html`<section class="section" aria-labelledby="cg-h"><div class="section-head"><h2 class="t-h2" id="cg-h">Side by side</h2>
      <button type="button" class="btn btn-sm cmp-means-btn" data-v2-cmp-means aria-pressed="${showMeans}">${showMeans ? 'Hide what each row measures' : 'What each row measures'}</button></div>
    <div class="tscroll cmp-wrap"><table class="t cmp-t ${showMeans ? 'show-means' : ''}"><caption class="sr">Every metric for ${c.tickers.join(', ')}</caption>
      <thead><tr><th scope="col">Metric</th>${rows.map((r) => html`<th scope="col"><a href="#/${r.ticker}">${r.ticker}</a>${r.name && r.name !== r.ticker ? html`<small class="t-muted cmp-name">${r.name}</small>` : ''}${what(r) ? html`<small class="t-muted cmp-sector">${what(r)}</small>` : ''}</th>`)}</tr></thead>
      <tbody>${(c.horizons || []).map((h) => { const rk = (c.ranks || {})[h.id] || [];
        const st = standing(rk);
        return html`<tr class="cmp-rank"><th scope="row">${h.name}<small class="t-muted cmp-means">${rankRead(rk.slice().sort((x, y) => y.score - x.score))}</small></th>${rows.map((r) => { const x = rk.find((y) => y.ticker === r.ticker), w = x ? st[x.ticker] : ''; const part = x && x.inputs && x.inputs[0] < x.inputs[1]; return html`<td>${x ? html`<span class="${w === 'best' ? 'cmp-best' : w === 'level' ? 'cmp-level' : 't-muted'}">${w}</span> ${num(x.score, 0)}${part ? html`<small class="t-muted cmp-part">from ${x.inputs[0]} of ${x.inputs[1]} inputs</small>` : ''}` : 'n/a'}</td>`; })}</tr>`; })}
      ${GROUPS.map((g) => html`<tr class="cmp-group"><th scope="rowgroup" colspan="${rows.length + 1}">${g.title}</th></tr>
        ${g.rows.map((m) => { const lead = leader(m, rows, c.leaders);
          return html`<tr><th scope="row">${m.label}${m.note ? html` <small class="t-muted">${m.note}</small>` : ''}<small class="t-muted cmp-means">${m.means}</small></th>${rows.map((r) => html`<td>${cell(m.kind, r[m.key], (r.why_na || {})[m.key])}${lead === r.ticker ? html` <span class="cmp-dot" title="${m.lead === 'high' ? 'Higher' : 'Lower'} on this measure">·<span class="sr">, leads this row</span></span>` : ''}${m.sub && r[m.sub] ? html`<br><small class="t-muted">${clean(r[m.sub])}</small>` : ''}</td>`)}</tr>`; })}`)}</tbody></table></div>
    ${(c.failed || []).length ? html`<p class="stale">Could not load: ${c.failed.map((f) => `${f.ticker} (${f.reason})`).join(', ')}.</p>` : ''}
    ${anyLead ? html`<p class="asof">A dot marks the higher or lower reading on the rows where one direction is better. No dot when fewer than two names have the figure, when the top two read the same, or when they are within 5% of each other.</p>` : ''}
    ${c.method ? html`<p class="asof">${clean(c.method)}</p>` : ''}</section>`;
}

function paint() {
  if (!live) return;
  const c = result;
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">Compare</h1>
      <p class="section-sub">Two to four stocks or ETFs ranked across momentum, technical structure, volatility and longer-term value. The three horizons are scored separately, so a name can lead one and trail another. That disagreement is the useful part.</p></header>
    <section class="section first" aria-label="Choose tickers">${controls()}
      ${c && c.available && (c.horizons || []).length ? html`<div class="cmp-hzs">${c.horizons.map((h) => html`<div><p class="t-label">${h.name}</p><p><b>Horizon: ${h.horizon}</b></p><p class="t-muted">${clean(h.basis || '')}</p></div>`)}</div>` : ''}</section>
    <div aria-live="polite">${running ? html`<div class="sk-wrap" role="status" aria-label="Comparing"><p>Pulling ${inputs.filter(Boolean).map((x) => x.toUpperCase()).join(' and ')} in full. The same analysis the Options and Investing tabs run, for each name.</p><div class="sk sk-row"></div><div class="sk sk-row"></div><div class="sk sk-row"></div></div>`
      : !c ? '' : !c.available ? html`<div class="state err" role="alert"><p class="t-h3">Not compared</p><p>${clean(c.reason || 'Not enough names loaded to compare.')}</p>${(c.failed || []).map((f) => html`<p class="t-muted">${f.ticker}: ${clean(f.reason)}</p>`)}${inputs.filter((x) => x.trim()).length >= 2 ? html`<button type="button" class="btn btn-sm" data-v2-cmp-again>Try again</button>` : ''}</div>`
        : html`${stale() ? html`<div class="stale cmp-stale" role="status"><p>These results are for ${c.tickers.join(', ')}. ${wanted().length >= 2 ? html`Press Compare for ${wanted().join(', ')}.` : 'Add a second name to compare again.'}</p>${wanted().length >= 2 ? html`<button type="button" class="btn btn-sm" data-v2-cmp-again>Compare ${wanted().join(', ')}</button>` : ''}</div>` : ''}<div class="${stale() ? 'cmp-old' : ''}">${take(c)}${perf(c)}${bars(c)}${grid(c)}</div>`}</div>`);
  // a phone's table header sticks under the top bar, whatever its height
  const bar = document.querySelector('.topbar'); if (bar && mainEl) mainEl.style.setProperty('--cmp-top', `${Math.round(bar.getBoundingClientRect().height)}px`);
  if (c && c.available && ((c.performance || {}).series || []).length >= 2) mountCharts(mainEl, { cmp: perfChart(c) });
}

async function run({ force } = {}) {
  const t = wanted();
  if (t.length < 2) { result = { available: false, reason: 'Give at least two tickers.' }; paint(); return; }
  running = true; paint();
  const mine = ++seq;
  let got;
  const path = `/api/compare?tickers=${encodeURIComponent(t.join(','))}`;
  // "Try again" asks again: a refusal kept for five minutes used to come straight back from the cache
  try { got = await api.get(path, { ttl: 300000, timeout: 90000, force: !!force }); }
  catch (e) { got = { available: false, reason: api.explain(e, 'The comparison') }; }
  if (mine !== seq) return;
  if (!got || !got.available) api.invalidate(path);
  result = got; running = false; paint();
  // the address says what is compared, so a reload or a shared link comes back to it (replaceState fires no route)
  if (got && got.available) { const want = `#/compare?t=${got.tickers.join(',')}`; if (location.hash !== want) { try { history.replaceState(history.state, '', `${location.pathname}${location.search}${want}`); } catch (e) { /* a sandboxed frame */ } } }
  const h = mainEl && mainEl.querySelector('#ct-h, #cp-h'); if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: false }); }
}

export async function render(main, route) {
  live = true; mainEl = main;
  document.title = 'Compare, Optic';
  // #/compare?t=AAPL,MSFT pre-fills and runs; otherwise seed the first box from the last company opened
  const pre = String((route.params || {}).t || '').split(',').map((x) => x.trim().toUpperCase()).filter(Boolean).slice(0, MAX);
  // a result is for the tickers it was asked for: another set in the address clears it
  if (pre.length) { if (result && result.tickers && result.tickers.join(',') !== pre.join(',')) { result = null; seq++; running = false; } inputs = pre.length >= 2 ? pre : [pre[0], '']; }
  else if (inputs.every((x) => !x)) { const r = store.recent()[0]; if (r) inputs[0] = r; }
  provideContext(() => ({ view: 'compare', compare: result && result.available ? { tickers: result.tickers, take: (result.take || {}).headline, ranks: result.ranks } : null }));
  main.addEventListener('submit', (e) => { if (e.target.closest('[data-v2-cmp-form]')) { e.preventDefault(); run(); } });
  main.addEventListener('input', (e) => {
    const i = e.target.dataset.v2CmpInput; if (i === undefined) return;
    const was = stale();
    inputs[i] = e.target.value;
    if (stale() !== was) { const at = e.target.selectionStart; paint(); const el = mainEl.querySelector(`#cmp-${i}`); if (el) { el.focus(); try { el.setSelectionRange(at, at); } catch (err) { /* number input */ } } }
    clearTimeout(suggT); const q = e.target.value.trim();
    if (q.length < 1) return;
    suggT = setTimeout(async () => {
      try { const r = await api.get(`/api/search?q=${encodeURIComponent(q)}&limit=10`, { ttl: 60000 }); sugg = (r.results || r || []).slice(0, 10); const dl = mainEl.querySelector('#cmp-sugg'); if (dl) dl.innerHTML = sugg.map((s) => `<option value="${String(s.symbol).replace(/"/g, '')}">${String(s.name || '').replace(/[<&]/g, '')}</option>`).join(''); } catch (err) { /* suggestions are optional */ }
    }, 160);
  });
  main.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s); let b;
    if (t('[data-v2-cmp-again]')) { run({ force: !(result && result.available) }); return; }
    if (t('[data-v2-cmp-means]')) { showMeans = !showMeans; paint(); const b2 = mainEl.querySelector('[data-v2-cmp-means]'); if (b2) b2.focus(); return; }
    if (t('[data-v2-cmp-add]')) { if (inputs.length < MAX) { inputs.push(''); paint(); const i = mainEl.querySelector(`#cmp-${inputs.length - 1}`); if (i) i.focus(); } return; }
    if ((b = t('[data-v2-cmp-drop]'))) { const k = Number(b.dataset.v2CmpDrop); inputs.splice(k, 1); paint(); const i = mainEl.querySelector(`#cmp-${Math.min(k, inputs.length - 1)}`); if (i) i.focus(); return; }
    if ((b = t('[data-v2-cmp-pick]'))) {
      const k = inputs.findIndex((x) => !x.trim());
      if (k >= 0) inputs[k] = b.dataset.v2CmpPick; else if (inputs.length < MAX) inputs.push(b.dataset.v2CmpPick); else return;
      paint(); const next = inputs.findIndex((x) => !x.trim()); const f = mainEl.querySelector(`#cmp-${next >= 0 ? next : inputs.length - 1}`); if (f) f.focus();
    }
  });
  paint();
  if (pre.length >= 2) run();
}
export function dispose() { live = false; clearTimeout(suggT); }
