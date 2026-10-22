// Positions, Retirement: a rules-based Roth IRA model allocation to compare
// your own against. The horizon, risk tolerance, contribution, candidate
// stocks and current holdings go to POST /api/retirement, which computes the
// plan and keeps no copy; the inputs are kept in this browser under the
// classic key (optic.roth.inputs, a personal key). No model call.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, signed, compact, clean, capFirst, isNum } from '../core/format.js';
import { skeleton, failed } from '../ui/states.js';
import { xyChart } from '../ui/xychart.js';
import { mountCharts } from '../ui/chart.js';
import { provideContext } from '../ui/milo.js';
import { sectionHead } from './tabs.js';

const KEY = 'optic.roth.inputs';
const DEFAULTS = { years: 30, risk: 'balanced', annual: 7000, holdings: '', stock_candidates: '' };
let inputs = { ...DEFAULTS }, D = {}, live = true, mainEl = null, seq = 0;
const $ = (v) => (isNum(v) ? `$${Math.round(v).toLocaleString('en-US')}` : 'n/a');
const pct = (v, dp = 1) => (isNum(v) ? `${num(v, dp)}%` : 'n/a');

/** The form's clamps, as the classic submit handler applies them. */
export function clampInputs(f) {
  const years = Math.round(Number(f.years)), annual = Number(f.annual);
  return {
    years: Number.isFinite(years) ? Math.min(45, Math.max(1, years)) : 30,
    risk: ['conservative', 'balanced', 'growth'].includes(f.risk) ? f.risk : 'balanced',
    annual: Number.isFinite(annual) ? Math.min(100000, Math.max(0, annual)) : 7000,
    holdings: String(f.holdings || ''), stock_candidates: String(f.stock_candidates || ''),
  };
}
const holdingsText = (h) => (typeof h === 'string' ? h : h && typeof h === 'object' ? Object.entries(h).map(([s, v]) => `${s} ${v}`).join('\n') : '');

function form() {
  const i = inputs;
  return html`<form class="roth-form" data-v2-roth novalidate>
    <div class="roth-grid"><label class="field"><span class="t-label">Years until you'd draw on it</span><input name="years" type="number" min="1" max="45" inputmode="numeric" value="${i.years}"></label>
      <label class="select"><span class="t-label">Risk tolerance</span><select name="risk">${['conservative', 'balanced', 'growth'].map((r) => html`<option value="${r}" ${r === i.risk ? 'selected' : ''}>${capFirst(r)}</option>`)}</select></label>
      <label class="field"><span class="t-label">Annual contribution ($)</span><input name="annual" type="number" min="0" max="100000" step="500" inputmode="numeric" value="${i.annual}"></label>
      <label class="field roth-wide"><span class="t-label">Individual stock candidates (optional)</span><input name="stock_candidates" placeholder="e.g. AAPL, KO, MSFT" value="${i.stock_candidates}" autocapitalize="characters" spellcheck="false"></label></div>
    <label class="field"><span class="t-label">Your current holdings. One per line, symbol then dollar value</span><textarea name="holdings" rows="4" spellcheck="false" placeholder="VTI 12000&#10;VXUS 4000&#10;BND 1500">${i.holdings}</textarea></label>
    <div class="cluster"><button type="submit" class="btn btn-primary" ${D.loading ? 'disabled' : ''}>${D.loading ? 'Calculating…' : 'Recalculate'}</button></div>
    <p class="asof">Your holdings are saved in this browser. To work out the numbers they are sent to Optic's server, which computes the plan and keeps no copy.</p></form>`;
}

const BASIS = { total: 'with distributions', price: 'price only', mixed: 'partly price only' };
/** The headline split, from the server's final weights: the table summed (pitch audit, 2026-10-22). */
export function splitTiles(a) {
  const eqNote = [isNum(a.equity_funds_pct) ? `${num(a.equity_funds_pct, 1)}% stock funds` : '', a.stock_sleeve_pct > 0 ? `${num(a.stock_sleeve_pct, 1)}% stocks` : '', a.reit_pct > 0 ? `${num(a.reit_pct, 1)}% REITs` : ''].filter(Boolean).join(', ');
  return [['Equity', `${num(a.equity_pct, 0)}%`, eqNote], ['Bonds', `${num(a.bond_pct, 0)}%`, 'ballast'], ...(a.gold_pct > 0 ? [['Gold', `${num(a.gold_pct, 0)}%`, 'no cash flow']] : [])];
}
function model(d) {
  const a = d.allocation || {}, bl = d.blended || {}, w = bl.window || {};
  return html`<dl class="kv" style="--kv:4">${splitTiles(a).map(([k, v, n]) => html`<div><dt>${k}</dt><dd>${v}</dd><p class="kv-note">${n}</p></div>`)}
      <div><dt>Blended expense ratio</dt><dd>${pct(bl.expense_ratio_pct, 2)}</dd>${isNum(bl.expense_ratio_pct) ? html`<p class="kv-note">about ${$((bl.expense_ratio_pct / 100) * 100000)} per $100k a year</p>` : ''}</div><div><dt>Blended yield</dt><dd>${pct(bl.yield_pct, 2)}</dd><p class="kv-note">not taxed as it arrives inside a Roth</p></div></dl>
    ${isNum(bl.cagr_long_pct) ? html`<h3>The fund weights as one portfolio, ${w.start ? `${w.start.slice(0, 4)} to ${w.end.slice(0, 4)}` : ''}</h3>
      <dl class="kv" style="--kv:3"><div><dt>Return a year</dt><dd>${pct(bl.cagr_long_pct)}</dd><p class="kv-note">${BASIS[bl.return_basis] || ''}, hypothetical</p></div><div><dt>Volatility</dt><dd>${pct(bl.volatility_pct)}</dd><p class="kv-note">of the combined daily returns</p></div><div><dt>Worst fall</dt><dd class="down">${pct(bl.max_drawdown_pct)}</dd><p class="kv-note">peak to trough in that window</p></div></dl>` : ''}
    <h3>Target weights</h3>
    <div class="tscroll"><table class="t"><thead><tr><th scope="col">Fund</th><th scope="col">Weight</th><th scope="col">Per year</th><th scope="col">Expense</th><th scope="col">Yield</th><th scope="col">10y return a year</th><th scope="col">Volatility</th><th scope="col">Worst drawdown</th></tr></thead>
      <tbody>${(d.rows || []).map((r) => html`<tr><td><a href="#/${r.symbol}">${r.symbol}</a> ${r.name || ''}<br><small class="t-muted">${clean(r.note || '')}</small></td><td>${pct(r.weight_pct)}</td><td>${$(r.annual_dollars)}</td><td>${pct(r.expense_ratio_pct, 2)}</td><td>${pct(r.yield_pct, 2)}</td><td>${pct(r.cagr_10y_pct)}</td><td>${pct(r.volatility_pct)}</td><td class="down">${pct(r.max_drawdown_pct)}</td></tr>`)}</tbody></table></div>
    ${bl.caveat ? html`<p class="asof">${clean(bl.caveat)}</p>` : ''}${d.disclaimer ? html`<p class="stale">${clean(d.disclaimer)}</p>` : ''}`;
}

function projection(pr) {
  if (!pr.available) return html`<p>${clean(pr.note || 'Projection unavailable.')}</p>`;
  return html`<p class="section-sub">Contributing ${$(pr.annual_contribution)} a year for ${pr.years} years at ${num(pr.rate_pct, 1)}% a year. ${clean(pr.rate_basis || '')}</p>
    <dl class="kv" style="--kv:4"><div><dt>You put in</dt><dd>${$(pr.total_contributed)}</dd><p class="kv-note">${pr.years} × ${$(pr.annual_contribution)}</p></div><div><dt>Lower scenario</dt><dd>${$(pr.balance_low)}</dd><p class="kv-note">at ${num(pr.rate_low_pct, 1)}%</p></div>
      <div><dt>At the historical rate</dt><dd>${$(pr.balance_base)}</dd><p class="kv-note">at ${num(pr.rate_pct, 1)}%, nominal dollars</p></div><div><dt>Upper scenario</dt><dd>${$(pr.balance_high)}</dd><p class="kv-note">at ${num(pr.rate_high_pct, 1)}%</p></div></dl>
    <p class="legend-line roth-legend"><span><i class="r1"></i>At the historical rate</span><span><i class="r2"></i>Lower and upper scenario</span><span><i class="r3"></i>Contributions only</span></p>
    <div class="chart-slot" data-chart="proj"></div>
    <ul class="plain asof">${[pr.band_note, pr.contribution_timing, pr.inflation_note, pr.caveat].filter(Boolean).map((t) => html`<li>${clean(t)}</li>`)}</ul>`;
}
function projChart(pr) {
  const xs = (pr.series || []).map((p) => p.year);
  const ys = (k, arr) => (arr || []).map((p) => p[k]);
  return (w) => xyChart([
    { name: 'At the historical rate', xs, ys: ys('balance', pr.series), cls: 'main' },
    // the bands come as plain balances, one a year, aligned with the central series
    { name: 'Lower scenario', xs, ys: (pr.series_low || []).map((v) => (typeof v === 'object' && v ? v.balance : v)), cls: 'alt' },
    { name: 'Upper scenario', xs, ys: (pr.series_high || []).map((v) => (typeof v === 'object' && v ? v.balance : v)), cls: 'alt' },
    { name: 'Contributions only', xs, ys: ys('contributed', pr.series), cls: 'faint' },
  ], { w, h: Math.max(180, Math.min(300, innerHeight - 190)), label: 'Contribution projection', xfmt: (x) => `yr ${Math.round(x)}`, yfmt: (v) => `$${compact(v)}`, summary: `After ${pr.years} years: ${$(pr.balance_base)} at the historical rate, scenarios ${$(pr.balance_low)} to ${$(pr.balance_high)}, from ${$(pr.total_contributed)} put in.` });
}

function sections(d) {
  const dr = d.drift || {}, rb = d.rebalance || {}, ov = d.overlap || {}, sl = d.stock_sleeve || {}, corr = d.correlations || {};
  return html`
    ${dr.available ? html`<section class="section" aria-labelledby="rd-h"><h2 class="t-h2" id="rd-h">Drift from target</h2><p class="section-sub">Portfolio value ${$(dr.total_value)}. ${clean(dr.summary || '')}</p>
      ${dr.unmapped_note ? html`<p class="stale">${clean(dr.unmapped_note)}</p>` : ''}
      <div class="tscroll"><table class="t"><thead><tr><th scope="col">Exposure</th><th scope="col">You hold</th><th scope="col">Current</th><th scope="col">Target</th><th scope="col">Drift</th><th scope="col"><span class="sr">Drift drawn</span></th></tr></thead>
        <tbody>${(dr.rows || []).map((r) => html`<tr><td>${r.label}</td><td>${$(r.current_value)}</td><td>${pct(r.current_pct)}</td><td>${pct(r.target_pct)}</td><td class="${r.drift_pct > 0 ? 'up' : r.drift_pct < 0 ? 'down' : ''}">${signed(r.drift_pct, 1)}</td><td class="roth-bar"><span class="rb-track"><span class="rb-fill ${r.drift_pct >= 0 ? 'pos' : 'neg'}" style="width:${Math.min(50, (Math.abs(r.drift_pct) / 25) * 50)}%"></span></span></td></tr>`)}</tbody></table></div>
      <p class="asof">Funds that track the same thing are counted as one exposure. Holding VOO where the model lists VTI isn't drift, it's the same bet under a different ticker.</p></section>` : ''}
    <section class="section" aria-labelledby="rc-h"><h2 class="t-h2" id="rc-h">Where to put this year's contribution</h2>
      ${rb.available ? html`<p class="section-sub">${clean(rb.note || '')}</p>
        ${(rb.rows || []).length ? html`<div class="tscroll"><table class="t"><thead><tr><th scope="col">Buy</th><th scope="col">Exposure</th><th scope="col">Amount</th><th scope="col">Share of contribution</th><th scope="col"><span class="sr">Share drawn</span></th></tr></thead>
          <tbody>${rb.rows.map((r) => html`<tr><td>${r.symbol ? html`<a href="#/${r.symbol}">${r.symbol}</a>` : 'Your picks'}</td><td>${r.label}</td><td>${$(r.dollars)}</td><td>${pct(r.pct_of_contribution)}</td><td class="roth-bar"><span class="rb-track"><span class="rb-fill pos one" style="width:${Math.min(100, r.pct_of_contribution)}%"></span></span></td></tr>`)}</tbody></table></div>` : ''}
        ${rb.overweight_note ? html`<p class="stale">${clean(rb.overweight_note)}</p>` : ''}
        <p class="asof">Buy-only by design: directing new money at the underweights fixes drift without selling anything. Selling inside a Roth is tax-free, so it's an option, just not the default.</p>`
        : html`<p class="quiet">${clean(rb.note || 'Enter your current holdings to get a rebalancing plan.')}</p>`}</section>
    ${ov.available ? html`<section class="section" aria-labelledby="ro-h"><h2 class="t-h2" id="ro-h">Overlap in your holdings</h2><p class="section-sub">${clean(ov.note || '')}</p>
      ${(ov.pairs || []).length ? ov.pairs.map((p) => html`<p class="${p.same_role ? 'stale' : ''}"><b>${p.a} + ${p.b}</b>, correlation ${num(p.correlation, 2)}. ${clean(p.note || '')}</p>`) : html`<p class="quiet">Nothing is doubled up.</p>`}</section>` : ''}
    <section class="section" aria-labelledby="rs-h"><h2 class="t-h2" id="rs-h">Individual stock sleeve</h2><p class="section-sub">${clean(sl.note || '')}</p>
      ${(sl.rows || []).length ? html`<div class="tscroll"><table class="t"><thead><tr><th scope="col">Stock</th><th scope="col">Conviction</th><th scope="col">Score</th><th scope="col">10y price return a year</th><th scope="col">Worst drawdown</th><th scope="col">History</th><th scope="col">Suggested</th></tr></thead>
        <tbody>${sl.rows.map((r) => html`<tr class="${r.eligible ? '' : 'is-dim'}"><td><a href="#/${r.symbol}">${r.symbol}</a> ${r.name || ''}</td><td><span class="pill">${r.conviction || 'n/a'}</span></td><td>${num(r.conviction_score, 0)}</td><td>${pct(r.cagr_10y_pct)}</td><td class="down">${pct(r.max_drawdown_pct)}</td><td>${isNum(r.years_of_history) ? `${num(r.years_of_history, 1)} years` : 'n/a'}</td><td>${isNum(r.suggested_pct) && r.eligible ? pct(r.suggested_pct) : 'Not included'}</td></tr>`)}</tbody></table></div>
        ${sl.rows.filter((r) => r.reject_reason || r.error).map((r) => html`<p class="t-muted"><b>${r.symbol}</b>: ${clean(r.reject_reason || r.error)}</p>`)}
        ${sl.rows.flatMap((r) => (r.warnings || []).map((w) => html`<p class="stale"><b>${r.symbol}</b>: ${clean(w)}</p>`))}` : ''}
      ${sl.caveat ? html`<p class="stale">${clean(sl.caveat)}</p>` : ''}</section>
    <section class="section" aria-labelledby="rw-h"><h2 class="t-h2" id="rw-h">What the Roth wrapper changes</h2><p class="section-sub">Reasoning specific to a Roth, as opposed to generic allocation advice.</p>
      <dl class="reads-dl">${(d.roth_notes || []).map((n) => html`<div><dt>${n.title}</dt><dd>${clean(n.body)}</dd></div>`)}</dl></section>
    <section class="section" aria-labelledby="ru-h"><h2 class="t-h2" id="ru-h">Fund universe</h2><p class="section-sub">Every candidate measured over its own available history, so the rows cover different spans: see History. Returns include reinvested distributions where marked. Highlighted rows are in the model above.</p>
      <div class="tscroll"><table class="t"><thead><tr><th scope="col">Fund</th><th scope="col">In model</th><th scope="col">Expense</th><th scope="col">Return a year, full history</th><th scope="col">5y CAGR</th><th scope="col">Volatility</th><th scope="col">Return / vol</th><th scope="col">Worst drawdown</th><th scope="col">History</th></tr></thead>
        <tbody>${(d.funds || []).map((r) => html`<tr class="${r.in_model_pct ? 'is-now' : ''}"><td><a href="#/${r.symbol}">${r.symbol}</a> ${r.name || ''}<br><small class="t-muted">${r.category || ''}</small></td><td>${r.in_model_pct ? pct(r.in_model_pct) : html`<span class="t-muted">no</span>`}</td><td>${pct(r.expense_ratio_pct, 2)}</td><td>${pct(r.cagr_full_pct)}${r.return_basis === 'price' ? html` <small class="t-muted">price only</small>` : ''}</td><td>${pct(r.cagr_5y_pct)}</td><td>${pct(r.volatility_pct)}</td><td>${num(r.return_per_vol, 2)}</td><td class="down">${pct(r.max_drawdown_pct)}</td><td>${isNum(r.years_of_history) ? `${num(r.years_of_history, 1)} years` : 'n/a'}</td></tr>`)}</tbody></table></div></section>
    ${(corr.symbols || []).length ? html`<section class="section" aria-labelledby="rr-h"><h2 class="t-h2" id="rr-h">Correlation</h2><p class="section-sub">How the funds have moved together over ${num(corr.sessions, 0)} sessions${corr.start ? `, ${corr.start} to ${corr.end}` : ''}. 0.85 or more is marked: two funds that close behave much like one. 0.35 or less is marked as genuine diversification.</p>
      <div class="tscroll"><table class="t corr-t"><thead><tr><th scope="col"><span class="sr">Fund</span></th>${corr.symbols.map((s) => html`<th scope="col">${s}</th>`)}</tr></thead>
        <tbody>${corr.symbols.map((s, i) => html`<tr><th scope="row">${s}</th>${corr.matrix[i].map((v, j) => (i === j ? html`<td class="t-muted">n/a</td>` : html`<td class="${isNum(v) && v >= 0.85 ? 'corr-hot' : isNum(v) && v <= 0.35 ? 'corr-cool' : ''}">${num(v, 2)}</td>`))}</tr>`)}</tbody></table></div></section>` : ''}`;
}

function paint() {
  if (!live) return;
  const d = D.d, y = window.scrollY;
  draw(mainEl, html`<header class="page-head">${sectionHead('portfolio', 'roth')}
      <p class="section-sub">A rules-based model allocation to compare your own against. Not retirement or tax advice.</p></header>
    <section class="section first" aria-labelledby="rm-h"><h2 class="t-h2" id="rm-h">Roth IRA model allocation</h2><p class="section-sub">Set your horizon and risk tolerance. The model is derived from those, not assumed.</p>
      ${form()}${d && d.limit_note ? html`<p class="asof">${clean(d.limit_note)}</p>` : ''}
      ${D.err ? failed('The model', D.err, { retry: 'load' }) : !d ? skeleton('rows', 5, 'Loading ten years of history for the fund universe') : model(d)}</section>
    ${d ? html`<section class="section" aria-labelledby="rp-h"><h2 class="t-h2" id="rp-h">Contribution projection</h2>${projection(d.projection || {})}</section>${sections(d)}` : ''}`);
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
  if (d && (d.projection || {}).available) mountCharts(mainEl, { proj: projChart(d.projection) });
}

async function load() {
  const my = ++seq; D.loading = true; D.err = null; paint();
  try {
    const d = await api.post('/api/retirement', inputs, { timeout: 90000 });
    if (my !== seq || !live) return;
    D.d = d;
    const i = d.inputs || {};
    // the server's reading of the inputs goes back into the form, as the classic page does
    if (i.annual_contribution !== undefined) inputs.annual = i.annual_contribution;
    if (Array.isArray(i.stock_candidates)) inputs.stock_candidates = i.stock_candidates.join(', ');
    if (i.holdings && typeof i.holdings === 'object') inputs.holdings = holdingsText(i.holdings);
  } catch (e) { if (my === seq) D.err = e; }
  D.loading = false; paint();
}
function readInputs() {
  inputs = { ...DEFAULTS };
  if (!holds(store.state.user)) return;
  try { const v = JSON.parse(localStorage.getItem(KEY) || 'null'); if (v && typeof v === 'object') inputs = { ...DEFAULTS, ...clampInputs({ ...DEFAULTS, ...v }) }; } catch (e) { /* defaults */ }
}

export async function render(main) {
  live = true; mainEl = main; D = {};
  document.title = 'Retirement, Optic';
  readInputs();
  provideContext(() => ({ view: 'roth', roth: D.d ? { inputs: D.d.inputs, allocation: D.d.allocation, blended: D.d.blended, projection: { years: (D.d.projection || {}).years, balance_base: (D.d.projection || {}).balance_base } } : null }));
  main.addEventListener('submit', (e) => {
    const f = e.target.closest('[data-v2-roth]'); if (!f) return;
    e.preventDefault();
    inputs = clampInputs({ years: f.years.value, risk: f.risk.value, annual: f.annual.value, holdings: f.holdings.value, stock_candidates: f.stock_candidates.value });
    if (holds(store.state.user)) { try { localStorage.setItem(KEY, JSON.stringify(inputs)); } catch (err) { /* private mode */ } }
    load();
  });
  load();
}
export function dispose() { live = false; }
export const retry = { load: () => load() };
export function onAuth() { if (live) { readInputs(); load(); } }
