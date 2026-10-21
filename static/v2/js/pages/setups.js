// Swing setups, on the Options tab (Classic parity B6b, 2026-10-21; Classic app.js:5845-6525): explainable bullish and
// bearish entry rules on completed candles, for review, with nothing traded. The rules and their lifecycle are the
// server's (app/analytics/setups.py); this is the scan, its filters, the reader's own rule settings, and one row
// opened to its checks, chart, back-test and option contracts, each fetched only when asked for.
//
// Kept as Classic keeps it, so either app reads the other's: optic.setups.view.v1 {scope, direction, timeframe, family,
// status} and optic.setups.params.v1 {enabled: [ids] | null, params: {preset | '*': {key: value}}}, only the changes
// from each default (a default moving on the server reaches everyone who never touched it).
//
// The section is one node for the visit, put back after the Options page redraws its group, so an opened row, its
// contract filters and the rules form being edited survive a redraw (owner's amendment 6). No model is called.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, compact, money, clean, capFirst, shortDate } from '../core/format.js';
import { lineChart, mountCharts } from '../ui/chart.js';
import { toast } from '../ui/toast.js';
import { addAlert } from '../core/watches.js';

export const VIEW_KEY = 'optic.setups.view.v1';
export const PARAMS_KEY = 'optic.setups.params.v1';
const FRESH_MS = 5 * 60 * 1000;   // a scan is reused for five minutes; completed candles change once a day
export const STATUS_LABELS = { watching: 'Watching', armed: 'Armed', triggered: 'Triggered', invalidated: 'Invalidated', expired: 'Expired', inactive: 'Context not met' };
export const STATUS_FILTERS = [['recent', 'Live and just ended'], ['active', 'Armed or triggered'], ['triggered', 'Triggered'], ['armed', 'Armed'], ['watching', 'Watching'], ['ended', 'Invalidated or expired'], ['all', 'Everything']];
const FAMILY_NAMES = { trend: 'Trend pullback', crossover: 'Moving-average crosses', momentum: 'RSI and MACD', fibonacci: 'Fibonacci', stochastic: 'Triple stochastic', donchian: 'Donchian', avwap: 'Anchored VWAP', levels: 'Support and resistance', volatility: 'Squeeze' };
export const OPTION_DEFAULTS = { dte_min: 21, dte_max: 60, min_oi: 100, min_volume: 10, max_spread_pct: 10 };

/* ---------------- what is kept ---------------- */
const BASE_VIEW = { scope: 'symbol', direction: 'both', timeframe: 'daily', family: '', status: 'recent' };
export function readView() {
  try { const raw = JSON.parse(localStorage.getItem(VIEW_KEY) || '{}'); return Object.assign({}, BASE_VIEW, raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}); } catch (e) { return Object.assign({}, BASE_VIEW); }
}
export function saveView(v) { try { localStorage.setItem(VIEW_KEY, JSON.stringify(v)); } catch (e) { /* private mode */ } }
export function readParams() {
  try {
    const raw = JSON.parse(localStorage.getItem(PARAMS_KEY) || '{}') || {};
    return { enabled: Array.isArray(raw.enabled) ? raw.enabled : null, params: raw.params && typeof raw.params === 'object' && !Array.isArray(raw.params) ? raw.params : {} };
  } catch (e) { return { enabled: null, params: {} }; }
}
export function saveParams(v) {
  try {
    if (!v || (!v.enabled && !Object.keys(v.params || {}).length)) localStorage.removeItem(PARAMS_KEY);
    else localStorage.setItem(PARAMS_KEY, JSON.stringify(v));
  } catch (e) { /* private mode */ }
}

/* ---------------- the scan ---------------- */
/** Which symbols a scan covers: this one by default, or a watchlist's (40 at most). */
export function symbolsFor(view, sym, lists) {
  if (view.scope && String(view.scope).startsWith('list:')) {
    const list = (lists || []).find((l) => String(l.id) === String(view.scope).slice(5));
    return [...new Set(((list && list.symbols) || []).map((s) => String(s).toUpperCase()))].slice(0, 40);
  }
  return sym ? [String(sym).toUpperCase()] : [];
}
export function presetIds(cat, view, prm) {
  if (!cat) return null;
  let ids = cat.presets.map((p) => p.id);
  if (prm.enabled) ids = ids.filter((id) => prm.enabled.includes(id));
  if (view.family) ids = ids.filter((id) => { const p = cat.presets.find((x) => x.id === id); return view.family === id || (p && p.family === view.family); });
  return ids;
}
/** The scan's request; the forming candle is read only while there is one (`live`), and marked provisional. */
export function scanUrl(view, syms, cat, prm, live) {
  if (!syms.length) return null;
  const tf = view.timeframe === '4h' && syms.length === 1 ? '4h' : 'daily', ids = presetIds(cat, view, prm);
  const q = [`symbols=${encodeURIComponent(syms.join(','))}`, `timeframe=${tf}`, `direction=${encodeURIComponent(view.direction || 'both')}`, `status=${encodeURIComponent(view.status || 'recent')}`];
  if (ids && ids.length) q.push(`presets=${encodeURIComponent(ids.join(','))}`);
  if (Object.keys(prm.params || {}).length) q.push(`params=${encodeURIComponent(JSON.stringify(prm.params))}`);
  if (live) q.push('provisional=1');
  return `/api/setups?${q.join('&')}`;
}
export const rowKey = (r) => [r.symbol, r.preset, r.direction, r.timeframe].join('|');
export function stampWords(stamp) {
  if (!stamp) return '';
  if (String(stamp).includes('T')) { const [d, t] = String(stamp).split('T'); return `${shortDate(d)} ${t.slice(0, 5)} ET`; }
  return `${shortDate(stamp)} close`;
}
/** When, for a row: the trigger's candle, the bar it armed on, or when its state last changed. */
export function whenFor(r) {
  if (r.status === 'triggered' || (r.trigger && r.status !== 'armed')) return stampWords((r.trigger || {}).stamp || r.status_at);
  if (r.status === 'armed') return `armed ${stampWords(r.armed_at || r.status_at)}`;
  return stampWords(r.status_at);
}
/** The rules form's values as Classic keeps them: which presets run (null for all) and only what differs from each
 *  default. `value(scope, spec)` reads one field; undefined is "left alone". */
export function paramsFrom(cat, value, isOn) {
  const params = {}, enabled = [];
  const read = (scope, spec) => {
    let v = value(scope, spec);
    if (v === undefined) return;
    if (spec.type === 'int' || spec.type === 'float') { v = Number(v); if (!Number.isFinite(v)) return; if (Number.isFinite(spec.min)) v = Math.max(spec.min, v); if (Number.isFinite(spec.max)) v = Math.min(spec.max, v); if (spec.type === 'int') v = Math.round(v); }
    if (v === spec.default || (spec.type === 'date' && !v)) return;
    (params[scope] = params[scope] || {})[spec.key] = v;
  };
  ((cat.presets[0] || {}).context || []).forEach((s) => read('*', s));
  cat.presets.forEach((p) => { if (isOn(p.id)) enabled.push(p.id); (p.params || []).forEach((s) => read(p.id, s)); });
  return { enabled: enabled.length === cat.presets.length ? null : enabled, params };
}
/** Across every rule, how many are in each state ("2 triggered, 3 armed"). */
export function stateLine(counts) {
  const all = {};
  Object.values(counts || {}).forEach((c) => Object.entries(c || {}).forEach(([k, v]) => { all[k] = (all[k] || 0) + v; }));
  return ['triggered', 'armed', 'watching', 'invalidated', 'expired', 'inactive'].filter((k) => all[k]).map((k) => `${all[k]} ${STATUS_LABELS[k].toLowerCase()}`).join(', ');
}

/* ---------------- state ---------------- */
const SS = { sym: null, node: null, ctx: null, view: null, cat: undefined, data: null, url: null, at: 0, loading: null, error: null, open: {}, details: {}, options: {}, rulesOpen: false, seq: 0, alerted: new Set() };
const lists = () => store.state.lists || [];

async function loadCatalogue() {
  if (SS.cat !== undefined) return SS.cat;
  try { SS.cat = await api.get('/api/setups/catalogue', { ttl: 3600000 }); } catch (e) { SS.cat = null; }
  return SS.cat;
}
async function load(force) {
  const sym = SS.sym;
  await loadCatalogue();
  if (SS.sym !== sym) return;
  const syms = symbolsFor(SS.view, sym, lists()), url = scanUrl(SS.view, syms, SS.cat, readParams(), SS.ctx.live());
  if (!url) { SS.data = null; SS.url = null; paint(); return; }
  if (!force && SS.url === url && SS.data && Date.now() - SS.at < FRESH_MS) { paint(); return; }
  if (SS.loading === url) return;
  SS.loading = url; SS.error = null; paint();
  try {
    const d = await api.get(url, { ttl: 0, force: true, timeout: 90000 });
    if (SS.loading !== url || SS.sym !== sym) return;   // a newer filter owns the panel
    SS.data = d; SS.url = url; SS.at = Date.now();
  } catch (e) { if (SS.loading !== url) return; SS.error = e; }
  SS.loading = null; paint();
}
async function openDetail(key) {
  const r = ((SS.data || {}).rows || []).find((x) => rowKey(x) === key); if (!r) return;
  const prm = readParams().params, q = [`preset=${encodeURIComponent(r.preset)}`, `direction=${r.direction}`, `timeframe=${r.timeframe}`];
  if (Object.keys(prm).length) q.push(`params=${encodeURIComponent(JSON.stringify(prm))}`);
  SS.details[key] = { loading: true }; paint(`[data-ss-open="${CSS.escape(key)}"]`);
  try { SS.details[key] = { data: await api.get(`/api/setups/${encodeURIComponent(r.symbol)}/detail?${q.join('&')}`, { ttl: 300000, timeout: 90000 }), at: String(Date.now()) }; }
  catch (e) { SS.details[key] = { error: e }; }
  paint(`[data-ss-open="${CSS.escape(key)}"]`);
}
async function loadOptions(key, filters) {
  const r = ((SS.data || {}).rows || []).find((x) => rowKey(x) === key); if (!r) return;
  const f = Object.assign({}, OPTION_DEFAULTS, filters || {});
  SS.options[key] = { loading: true, filters: f }; paint();
  const q = Object.entries(f).map(([k, v]) => `${k}=${encodeURIComponent(v)}`);
  q.push(`direction=${r.direction}`);
  const cap = SS.ctx.budget(); if (cap) q.push(`budget=${encodeURIComponent(cap)}`);   // the tab's per-contract budget, so the two agree
  try { SS.options[key] = { data: await api.get(`/api/setups/${encodeURIComponent(r.symbol)}/options?${q.join('&')}`, { ttl: 0, force: true, timeout: 90000 }), filters: f }; }
  catch (e) { SS.options[key] = { error: e, filters: f }; }
  paint(`[data-ss-options-form="${CSS.escape(key)}"] [type=submit]`);
}

/* ---------------- words ---------------- */
const sel = (name, label, opts, value) => html`<label class="select ss-filter"><span class="t-label">${label}</span><select data-ss-filter="${name}">${opts.map(([v, l, off]) => html`<option value="${v}" ${String(v) === String(value) ? 'selected' : ''} ${off ? 'disabled' : ''}>${l}</option>`)}</select></label>`;
function filtersHTML() {
  const v = SS.view, one = symbolsFor(v, SS.sym, lists()).length <= 1, fams = SS.cat ? SS.cat.families.map((f) => [f, FAMILY_NAMES[f] || capFirst(f)]) : [];
  return html`<div class="ss-filters" role="group" aria-label="Filter the swing setups">
    ${sel('scope', 'Symbols', [['symbol', `This symbol (${SS.sym})`], ...lists().map((l) => [`list:${l.id}`, `${l.name} (${(l.symbols || []).length})`])], v.scope)}
    ${sel('direction', 'Direction', [['both', 'Both'], ['bull', 'Bullish'], ['bear', 'Bearish']], v.direction)}
    ${sel('timeframe', 'Timeframe', [['daily', 'Daily, weekly trend'], ['4h', one ? '4-hour, daily trend' : '4-hour (one symbol only)', !one]], one ? v.timeframe : 'daily')}
    ${sel('family', 'Strategy', [['', 'All'], ...fams], v.family)}
    ${sel('status', 'Status', STATUS_FILTERS, v.status)}
    <button type="button" class="btn btn-sm" data-ss-rules aria-expanded="${SS.rulesOpen}" aria-controls="ss-rules">Rule settings${Object.keys(readParams().params).length || readParams().enabled ? ', changed' : ''}</button></div>`;
}
function field(scope, spec, prm) {
  const mine = (prm.params[scope] || {})[spec.key], value = mine === undefined ? spec.default : mine, name = `${scope}::${spec.key}`;
  const hint = spec.help ? html`<span class="t-muted ss-help">${spec.help}</span>` : '';
  if (spec.type === 'bool') return html`<label class="check ss-param"><input type="checkbox" name="${name}" ${value ? 'checked' : ''}> <span>${spec.label}${hint}</span></label>`;
  if (spec.type === 'choice') return html`<label class="ss-param"><span class="t-label">${spec.label}</span><select name="${name}">${spec.choices.map((c) => html`<option value="${c}" ${c === value ? 'selected' : ''}>${c}</option>`)}</select>${hint}</label>`;
  if (spec.type === 'date' || spec.type === 'symbol') return html`<label class="ss-param"><span class="t-label">${spec.label}</span><input type="${spec.type === 'date' ? 'date' : 'text'}" name="${name}" value="${value || ''}">${hint}</label>`;
  return html`<label class="ss-param"><span class="t-label">${spec.label}</span><input type="number" inputmode="decimal" name="${name}" value="${value}" min="${spec.min ?? ''}" max="${spec.max ?? ''}" step="${spec.step || (spec.type === 'int' ? 1 : 0.05)}">${hint}</label>`;
}
function rulesHTML() {
  const cat = SS.cat;
  if (!cat) return html`<p class="t-muted" id="ss-rules">The rule catalogue did not load.</p>`;
  const prm = readParams(), on = prm.enabled || cat.presets.map((p) => p.id);
  return html`<form class="ss-rules stack" id="ss-rules" data-ss-rules-form>
    <p class="t-muted">Every preset is a hypothesis to test, not a strategy known to work. Changes are kept in this browser and apply to the scan here; alerts use each preset's defaults.</p>
    <fieldset class="ss-fs"><legend class="t-label">Context and lifecycle, for every preset</legend><div class="ss-params">${(cat.presets[0].context || []).map((s) => field('*', s, prm))}</div></fieldset>
    ${cat.presets.map((p) => html`<details class="ss-preset"><summary><span class="ss-preset-h">${p.label}</span> <span class="t-muted">${p.kind}${p.experimental ? ', experimental' : ''}${on.includes(p.id) ? '' : ', off'}</span></summary>
      <label class="check"><input type="checkbox" name="enabled::${p.id}" ${on.includes(p.id) ? 'checked' : ''}> <span>Run this preset</span></label>
      <p><b>Bullish.</b> ${clean(p.rules.bull)}</p><p><b>Bearish.</b> ${clean(p.rules.bear)}</p>
      <div class="ss-params">${(p.params || []).map((s) => field(p.id, s, prm))}</div></details>`)}
    <div class="cluster"><button type="submit" class="btn btn-primary">Apply</button><button type="button" class="btn" data-ss-rules-reset>Back to the defaults</button><button type="button" class="btn btn-quiet" data-ss-rules>Close</button></div></form>`;
}
const mark = (p) => (p === true ? html`<span class="ss-pass">Met</span>` : p === false ? html`<span class="ss-fail">Not met</span>` : html`<span class="t-muted">No data</span>`);
function historyHTML(h, tf) {
  if (!h) return '';
  if (!h.available) return html`<p class="asof">${clean(h.reason || 'No historical evaluation.')}</p>`;
  const cols = [['All', h.all], ['Earlier 70%', h.earlier], ['Held out, last 30%', h.held_out]], cell = (s, k, f) => (s && s.n ? f(s[k]) : 'n/a'), a = h.assumptions || {};
  return html`<h4 class="t-label">How this rule did on ${tf === '4h' ? '4-hour' : 'daily'} candles, ${shortDate(h.from)} ${String(h.from).slice(0, 4)} to ${shortDate(h.to)} ${String(h.to).slice(0, 4)}</h4>
    ${h.small_sample ? html`<p class="ss-warn">${clean(h.small_sample)}</p>` : ''}
    <div class="tscroll"><table class="t ss-hist"><thead><tr><th class="l"><span class="sr">Measure</span></th>${cols.map(([l]) => html`<th>${l}</th>`)}</tr></thead><tbody>
      <tr><td class="l">Trades</td>${cols.map(([, s]) => html`<td>${s && s.n ? s.n : 0}</td>`)}</tr>
      <tr><td class="l">Won</td>${cols.map(([, s]) => html`<td>${cell(s, 'win_rate_pct', (v) => `${num(v, 0)}%`)}</td>`)}</tr>
      <tr><td class="l">Average, in R</td>${cols.map(([, s]) => html`<td>${cell(s, 'avg_r', (v) => num(v, 2))}</td>`)}</tr>
      <tr><td class="l">Median, in R</td>${cols.map(([, s]) => html`<td>${cell(s, 'median_r', (v) => num(v, 2))}</td>`)}</tr>
      <tr><td class="l">Deepest drawdown, in R</td>${cols.map(([, s]) => html`<td>${cell(s, 'max_drawdown_r', (v) => num(v, 2))}</td>`)}</tr></tbody></table></div>
    <p class="asof">R is the distance from entry to the invalidation level, so 1R is what the stop would have cost. Entry at ${a.entry}; exit at ${a.exits}; ${num(a.slippage_bps_each_way, 0)} basis points of slippage each way, ${a.fees}; ${a.same_bar}. ${clean(h.caveat || '')}</p>`;
}
function optionsHTML(r) {
  const key = rowKey(r), o = SS.options[key], f = (o && o.filters) || OPTION_DEFAULTS;
  const n = (name, label, v, extra = '') => html`<label class="ss-param"><span class="t-label">${label}</span><input type="number" inputmode="decimal" name="${name}" value="${v}" ${extra}></label>`;
  const form = html`<form class="ss-opt-form" data-ss-options-form="${key}">
    ${n('dte_min', 'Days to expiry, from', f.dte_min, html`min="0" max="730"`)}${n('dte_max', 'to', f.dte_max, html`min="1" max="730"`)}
    ${n('min_oi', 'Open interest at least', f.min_oi, html`min="0"`)}${n('min_volume', 'Volume today at least', f.min_volume, html`min="0"`)}
    ${n('max_spread_pct', 'Spread at most (%)', f.max_spread_pct, html`min="0.5" max="100" step="0.5"`)}
    <button type="submit" class="btn btn-sm">${o && o.data ? 'Apply' : 'Show contracts'}</button></form>`;
  const head = html`<h4 class="t-label">Option contracts${o && o.data ? `: ${o.data.side}s` : ''}</h4>`;
  if (!o) return html`${head}<p class="t-muted">The signal comes from the stock. Contracts are a separate question, asked of the chain with filters you set.</p>${form}`;
  if (o.loading) return html`${head}${form}<p class="t-muted" role="status">Reading the chain…</p>`;
  if (o.error) return html`${head}${form}<p class="ss-warn">${api.explain(o.error, 'The chain')}</p>`;
  const d = o.data, dropped = Object.entries(d.dropped || {}).filter(([, v]) => v).map(([why, k]) => `${why} (${k} out)`).join('; ');
  return html`${head}${form}
    ${d.available ? html`<p class="asof">${d.passed} of ${d.considered} ${d.side}s pass${dropped ? `: ${dropped}` : ''}. ${d.passed > d.shown ? `The first ${d.shown} are listed. ` : ''}Listed ${clean(d.order || '')}${d.fetched_at ? ` Chain read ${new Date(d.fetched_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' })} ET.` : ''}</p>` : html`<p class="ss-warn">${clean(d.reason || '')}</p>`}
    ${d.earnings_in_hold ? html`<p class="ss-warn">Earnings on ${shortDate(d.earnings)} fall inside the ${d.hold_days}-day holding period. A report can move the stock and the options' implied volatility at once.</p>` : ''}
    ${(d.contracts || []).length ? html`<div class="tscroll"><table class="t ss-opt"><thead><tr><th class="l">Expiry</th><th>Days</th><th>Strike</th><th>Bid and ask</th><th>Spread</th><th>Volume</th><th>Open interest</th><th>IV</th><th>Delta</th><th>Theta</th><th>Cost for one</th><th class="l">Last trade</th></tr></thead>
      <tbody>${d.contracts.map((c) => html`<tr><td class="l">${shortDate(c.expiry)}${c.through_earnings ? html` <span class="t-muted">through earnings</span>` : ''}</td><td>${c.dte}</td><td>${num(c.strike, 2)}</td><td>${num(c.bid, 2)} to ${num(c.ask, 2)}</td><td>${num(c.spread_pct, 1)}%</td>
        <td>${compact(c.volume)}</td><td>${compact(c.open_interest)}</td><td>${c.iv_pct === null || c.iv_pct === undefined ? html`<span class="t-muted">not quoted</span>` : `${num(c.iv_pct, 1)}%`}</td>
        <td>${c.delta === null || c.delta === undefined ? 'n/a' : num(c.delta, 2)}</td><td>${c.theta === null || c.theta === undefined ? 'n/a' : num(c.theta, 3)}</td><td>${money(c.cost_for_one, 0)}</td>
        <td class="l">${c.last_trade ? new Date(c.last_trade).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' }) : 'not given'}</td></tr>`)}</tbody></table></div>`
      : d.available ? html`<p class="t-muted">No contract passes these filters. The stock setup above stands on its own.</p>` : ''}
    ${(d.notes || []).length ? html`<ul class="plain ss-notes">${d.notes.map((x) => html`<li>${clean(x)}</li>`)}</ul>` : ''}`;
}
function detailHTML(r, i) {
  const key = rowKey(r), det = SS.details[key];
  if (!det || det.loading) return html`<p class="t-muted" role="status">Reading the setup…</p>`;
  if (det.error) return html`<p class="ss-warn">${api.explain(det.error, 'The setup')}</p>`;
  const d = det.data, row = d.row || r, cond = row.conditions || {}, vol = row.volume || {}, set = SS.alerted.has(`${row.symbol}|${row.preset}`);
  const vals = Object.entries(row.values || {}).filter(([, v]) => v !== null && v !== undefined);
  return html`<div class="ss-detail">
    <p><b>The rule.</b> ${clean(d.rules || '')}</p>
    <div class="cluster"><button type="button" class="btn btn-sm" data-ss-alert="${key}" ${set ? html`aria-disabled="true"` : ''}>${set ? 'Alert set' : 'Alert me when this triggers'}</button></div>
    ${row.provisional ? html`<p class="ss-warn">${clean(row.provisional.text)}</p>` : ''}
    <div class="ss-chart chart-slot" data-chart="ss-${i}" role="group" aria-label="${row.symbol} with the ${row.label} setup marked"></div>
    <p class="ss-legend">${Object.keys(g(d, 'chart', 'lines') || {}).slice(0, 4).map((name, k) => html`<span><i class="o${k + 1}"></i>${name}</span> `)}${Number.isFinite(Number(g(d, 'chart', 'trigger_level'))) ? html`<span><i class="trig"></i>Trigger ${num(d.chart.trigger_level, 2)}</span> ` : ''}${Number.isFinite(Number(g(d, 'chart', 'invalidation'))) ? html`<span><i class="inval"></i>Invalidation ${num(d.chart.invalidation, 2)}</span>` : ''}</p>
    <p class="asof">Marked on the chart: where it armed, triggered or ended, the trigger level and the invalidation level${(g(d, 'chart', 'anchors') || []).length ? ', and the anchors the rule measured from, each usable only from the date it was confirmed' : ''}.</p>
    <div class="ss-cols"><div><h4 class="t-label">${cond.met ?? ''} of ${cond.of ?? ''} conditions met</h4>
        <div class="tscroll"><table class="t ss-checks"><tbody>${(row.checks || []).map((c) => html`<tr class="${c.required ? '' : 'is-info'}"><td class="l">${clean(c.group || '')}</td><td class="l">${clean(c.rule || '')}${c.required ? '' : html` <span class="t-muted">(filter off, not counted)</span>`}</td><td class="l">${mark(c.passed)}</td><td>${c.value === null || c.value === undefined ? '' : String(c.value)}</td></tr>`)}</tbody></table></div>
        ${cond.note ? html`<p class="asof">${clean(cond.note)}</p>` : ''}</div>
      <div>${vals.length ? html`<h4 class="t-label">Readings</h4><dl class="sg-dl">${vals.map(([k, v]) => html`<div><dt>${k}</dt><dd>${String(v)}</dd></div>`)}</dl>` : ''}
        <h4 class="t-label">Volume</h4><p>${vol.ratio ? `${num(vol.ratio, 2)} times the 20-bar average on the ${row.status === 'triggered' ? 'trigger candle' : 'latest candle'}.` : 'Not enough volume history.'}</p>
        ${row.note ? html`<p class="asof">${clean(row.note)}</p>` : ''}</div></div>
    ${historyHTML(d.history, row.timeframe)}
    ${optionsHTML(row)}</div>`;
}
const g = (o, ...ks) => ks.reduce((x, k) => (x && typeof x === 'object' ? x[k] : undefined), o);
function tableHTML(rows) {
  const own = readParams().params;
  return html`<div class="tscroll"><table class="t ss-table"><thead><tr><th class="l">Symbol</th><th class="l">Setup</th><th class="l">Status</th><th>Trigger</th><th>Invalidation</th><th class="l">When</th><th><span class="sr">Details</span></th></tr></thead>
    <tbody>${rows.map((r, i) => {
      const key = rowKey(r), open = !!SS.open[key];
      const mine = !!(own[r.preset] && Object.keys(own[r.preset]).length) || !!(own['*'] && Object.keys(own['*']).length);
      return html`<tr class="ss-row${open ? ' is-open' : ''}"><td class="l"><b class="tick">${r.symbol}</b></td>
        <td class="l ss-setup"><span class="${r.direction === 'bull' ? 'up' : 'down'}">${r.direction === 'bull' ? 'Bullish' : 'Bearish'}</span> ${r.label} <span class="t-muted">${r.kind}${r.experimental ? ', experimental' : ''}${mine ? ', your settings' : ''}</span></td>
        <td class="l"><span class="ss-state is-${r.status}">${STATUS_LABELS[r.status] || capFirst(r.status)}</span>${r.provisional ? html` <span class="t-muted">provisional: ${r.provisional.event}</span>` : ''}</td>
        <td data-label="Trigger">${r.trigger_level === null || r.trigger_level === undefined ? 'n/a' : num(r.trigger_level, 2)}</td><td data-label="Invalidation">${r.invalidation === null || r.invalidation === undefined ? 'n/a' : num(r.invalidation, 2)}</td>
        <td class="l" data-label="When">${whenFor(r)}</td>
        <td><button type="button" class="btn btn-sm btn-quiet" data-ss-open="${key}" aria-expanded="${open}" aria-controls="ss-d-${i}" aria-label="${open ? 'Hide' : 'Show'} details for ${r.symbol} ${r.label}, ${r.direction === 'bull' ? 'bullish' : 'bearish'}">${open ? 'Hide' : 'Details'}</button></td></tr>
      <tr class="ss-why"><td colspan="7">${clean(r.explanation || '')}</td></tr>
      ${open ? html`<tr class="ss-drow" id="ss-d-${i}"><td colspan="7">${detailHTML(r, i)}</td></tr>` : ''}`;
    })}</tbody></table></div>`;
}
function bodyHTML() {
  const syms = symbolsFor(SS.view, SS.sym, lists()), d = SS.data;
  const head = html`${filtersHTML()}${SS.rulesOpen ? rulesHTML() : ''}`;
  if (!syms.length) return html`${head}<p class="t-muted">That watchlist is empty. Add symbols to it, or scan this symbol.</p>`;
  if (SS.error && !d) return html`${head}<p class="ss-warn">${api.explain(SS.error, 'The scan')}</p><button type="button" class="btn btn-sm" data-ss-retry>Try again</button>`;
  if (!d) return html`${head}<p class="t-muted" role="status">Reading ${syms.length === 1 ? syms[0] : `${syms.length} symbols`}…</p>`;
  const rows = d.rows || [], line = stateLine(d.counts), asOf = [...new Set(Object.values(d.as_of || {}))].sort().pop();
  const through = !asOf ? '' : String(asOf).includes('T') ? ` to the candle that closed ${stampWords(asOf)}` : ` to the ${shortDate(asOf)} close`;
  return html`${head}
    <p class="asof ss-line" role="status">${SS.loading ? 'Updating… ' : ''}${d.timeframe === '4h' ? '4-hour candles, daily trend.' : 'Daily candles, weekly trend.'} Completed candles${through}${d.forming ? `; ${clean(d.forming.note)}` : ''}.${line ? ` Across every rule: ${line}.` : ''}${(d.failed || []).length ? ` No candles for ${d.failed.join(', ')}.` : ''}</p>
    ${rows.length ? tableHTML(rows) : html`<p class="t-muted">No setups match these filters. Status "Everything" lists every rule, including those waiting on context.</p>`}
    <p class="asof">${clean(d.method || '')}</p>`;
}

/* ---------------- the chart for an opened row ---------------- */
function chartMaker(d) {
  const ch = d.chart || {}, row = d.row || {}, stamps = (ch.stamps || []).map((s) => String(s).slice(0, 10)), close = ch.close || [];
  const pts = stamps.map((s, i) => ({ d: s, c: Number(close[i]) })).filter((p) => p.d && Number.isFinite(p.c));
  if (pts.length < 10) return null;
  const n = pts.length, lines = Object.entries(ch.lines || {}).slice(0, 4).map(([name, values], k) => ({ name, values: (values || []).map(Number), cls: `o${k + 1}` }));
  const lvl = [ch.trigger_level, ch.invalidation].map(Number).filter(Number.isFinite);
  const room = Array(n).fill(null); lvl.forEach((v, k) => { room[k * 2] = v; });   // isolated points draw nothing; they keep both levels in range
  const marks = ch.marks || [], fired = marks.filter((m) => m.type === 'triggered'), latest = fired[fired.length - 1];
  const lastArm = row.status === 'armed' ? [...marks].reverse().find((m) => m.type === 'armed') : null;
  const killed = latest ? marks.find((m) => m.type === 'invalidated' && m.index > latest.index) : null;
  const off = (ch.close || []).length - n;
  const pins = [...fired, ...(lastArm ? [lastArm] : []), ...(killed ? [killed] : [])].map((m) => ({ i: m.index - off, v: Number.isFinite(Number(m.price)) ? Number(m.price) : pts[Math.max(0, m.index - off)] && pts[Math.max(0, m.index - off)].c,
    text: m === latest ? 'Trigger' : m === lastArm ? 'Armed' : m === killed ? 'Invalidated' : '', dir: m.type === 'triggered' ? 'up' : m.type === 'invalidated' ? 'down' : '' }));
  return (w) => lineChart(pts, { w, h: Math.round(Math.max(220, Math.min(300, w * 0.36))), label: `${row.symbol} closing price, ${row.label}`, dp: 2,
    overlays: [...lines, { values: room, cls: 'ss-room' }], refs: [...(Number.isFinite(Number(ch.trigger_level)) ? [{ v: Number(ch.trigger_level), cls: 'ss-trig' }] : []), ...(Number.isFinite(Number(ch.invalidation)) ? [{ v: Number(ch.invalidation), cls: 'ss-inval' }] : [])],
    pins, tipMore: (i) => lines.map((l) => (Number.isFinite(l.values[i + (l.values.length - n)]) ? `${l.name} ${num(l.values[i + (l.values.length - n)], 2)}` : '')).filter(Boolean).join(', ') });
}
function mountOpenCharts() {
  const rows = (SS.data || {}).rows || [], makers = {};
  rows.forEach((r, i) => { const det = SS.details[rowKey(r)]; if (SS.open[rowKey(r)] && det && det.data) { const m = chartMaker(det.data); if (m) makers[`ss-${i}`] = m; } });
  if (Object.keys(makers).length) mountCharts(SS.node, makers);
}
function paint(focusSel) {
  if (!SS.node) return;
  const box = SS.node.querySelector('.ss-body'); if (!box) return;
  const a = document.activeElement, keep = !focusSel && a && box.contains(a) ? [...a.attributes].map((x) => x.name).find((k) => k.startsWith('data-ss-') || k === 'name') : null, kv = keep ? a.getAttribute(keep) : null;
  draw(box, bodyHTML());
  mountOpenCharts();
  const f = focusSel ? box.querySelector(focusSel) : keep ? box.querySelector(`[${keep}="${CSS.escape(kv || '')}"]`) : null;
  if (f) f.focus({ preventScroll: true });
}

/* ---------------- what the reader does ---------------- */
function wire(n) {
  n.addEventListener('change', (e) => {
    const s = e.target.closest('[data-ss-filter]'); if (!s) return;
    SS.view[s.dataset.ssFilter] = s.value;
    if (symbolsFor(SS.view, SS.sym, lists()).length > 1 && SS.view.timeframe === '4h') SS.view.timeframe = 'daily';
    saveView(SS.view); SS.open = {};
    load(true);
  });
  n.addEventListener('click', async (e) => {
    const t = (q) => e.target.closest(q);
    let b;
    if (t('[data-ss-rules]')) { SS.rulesOpen = !SS.rulesOpen; paint(SS.rulesOpen ? '#ss-rules input, #ss-rules select' : '[data-ss-rules]'); return; }
    if (t('[data-ss-rules-reset]')) { saveParams(null); SS.details = {}; SS.open = {}; SS.options = {}; SS.rulesOpen = false; toast('Rule settings back to their defaults.'); paint('[data-ss-rules]'); load(true); return; }
    if (t('[data-ss-retry]')) { load(true); return; }
    if ((b = t('[data-ss-open]'))) {
      const key = b.dataset.ssOpen; SS.open[key] = !SS.open[key];
      if (SS.open[key] && !(SS.details[key] && SS.details[key].data)) openDetail(key); else paint(`[data-ss-open="${CSS.escape(key)}"]`);
      return;
    }
    if ((b = t('[data-ss-alert]'))) {
      if (b.getAttribute('aria-disabled') === 'true') return;
      const r = ((SS.data || {}).rows || []).find((x) => rowKey(x) === b.dataset.ssAlert); if (!r) return;
      b.setAttribute('aria-disabled', 'true');
      try {
        await addAlert({ symbol: r.symbol, kind: 'swing_setup', params: { preset: r.preset } });
        SS.alerted.add(`${r.symbol}|${r.preset}`); b.textContent = 'Alert set';
        toast(`Alert set: ${r.symbol}, ${r.label}. A trigger on a completed daily candle lands in Alerts.`, { action: 'Open Alerts', run: () => { location.hash = '#/alerts'; } });
      } catch (err) { b.removeAttribute('aria-disabled'); toast(err.kind ? api.explain(err, 'The alert') : err.message, { kind: 'bad' }); }
    }
  });
  n.addEventListener('submit', (e) => {
    const f = e.target.closest('[data-ss-options-form], [data-ss-rules-form]'); if (!f) return;
    e.preventDefault();
    if (f.matches('[data-ss-options-form]')) {
      const out = {}; Object.keys(OPTION_DEFAULTS).forEach((k) => { const v = Number((f.elements[k] || {}).value); if (Number.isFinite(v)) out[k] = v; });
      loadOptions(f.dataset.ssOptionsForm, out); return;
    }
    const cat = SS.cat; if (!cat) return;
    const value = (scope, spec) => { const el = f.elements[`${scope}::${spec.key}`]; if (!el) return undefined; return spec.type === 'bool' ? el.checked : el.value; };
    const v = paramsFrom(cat, value, (id) => { const el = f.elements[`enabled::${id}`]; return !el || el.checked; });
    // a row opened under the old settings is closed: its detail was read with them (Classic left it reading forever)
    saveParams(v); SS.details = {}; SS.open = {}; SS.options = {}; SS.rulesOpen = false;
    toast(v.enabled || Object.keys(v.params).length ? 'Your rule settings apply to this scan.' : 'Every preset on its defaults.');
    paint('[data-ss-rules]'); load(true);
  });
}

/** Put the section (one node for the visit) where the Options page left its slot, and scan when first shown. */
export function mountSetups(root, sym, ctx) {
  const slot = root.querySelector('[data-ss-slot]');
  if (SS.sym !== sym || !SS.node) {
    Object.assign(SS, { sym, ctx, view: readView(), data: null, url: null, at: 0, loading: null, error: null, open: {}, details: {}, options: {}, rulesOpen: false, alerted: new Set() });
    const n = document.createElement('div'); n.className = 'ss'; n.innerHTML = '<div class="ss-body"></div>';
    SS.node = n; wire(n);
  }
  SS.ctx = ctx;
  if (!slot) return;
  if (slot !== SS.node) slot.replaceWith(SS.node);
  if (!SS.data && !SS.loading) load(false); else paint();
}
export function disposeSetups() { SS.sym = null; SS.node = null; }
export const setupsContext = () => ((SS.data || {}).rows || []).slice(0, 12).map((r) => ({ symbol: r.symbol, setup: r.label, direction: r.direction, status: r.status, trigger: r.trigger_level, invalidation: r.invalidation }));
