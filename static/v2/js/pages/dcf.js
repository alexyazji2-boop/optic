// The fair-value model on Investing: a sourced, deterministic discounted cash flow the reader can read in one sentence
// and interrogate as far as they like (Classic parity B7a, 2026-10-21; Classic static/valuation.js). Every figure comes
// from the server (/api/valuation, app/valuation/), which does all of the arithmetic; this module shows it, collects the
// reader's edits and sends them back to be recomputed (POST /run), so the page and the engine cannot disagree.
//
// Laid out the v2 way: the sentence and the four figures that frame it, then what moves the value, the methods side by
// side, what today's price implies, the sensitivity tables and the three cases. The forecast, the discount rate, the
// bridge, the linked statements, the sources and the formulas are folded, and so is the assumptions form, which
// recalculates as the reader types and keeps the caret where it was.
//
// The reader's edits are kept in Classic's key and format, optic.dcf.v1 {edits: {SYM: {drivers, wacc, base, equity}},
// models: [...]}, so either app reads the other's. Saved models (B7b) are the account's (/api/valuation-models) when
// signed in and this browser's `models` otherwise, 40 at most, each a snapshot that can be rerun exactly.
//
// The section is one node for the visit, put back after each of the page's redraws, so a box being typed in keeps its
// value, focus and caret (owner's amendment 6). No model is called.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, compact, clean } from '../core/format.js';
import { FIELDS, GROUPS } from '../core/dcf-fields.js';
import { registerValuation, unregisterValuation } from '../ui/milo.js';

export const STORE_KEY = 'optic.dcf.v1';
export const MAX_LOCAL_MODELS = 40;

/* ---------------- storage, Classic's ---------------- */
export function readStore() {
  try {
    const p = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
    if (p && typeof p === 'object' && !Array.isArray(p)) return { edits: p.edits && typeof p.edits === 'object' ? p.edits : {}, models: Array.isArray(p.models) ? p.models : [] };
  } catch (e) { /* private mode or a bad copy: start empty */ }
  return { edits: {}, models: [] };
}
function writeStore(next) { try { localStorage.setItem(STORE_KEY, JSON.stringify(next)); } catch (e) { /* full or blocked */ } }
const blankEdits = () => ({ drivers: {}, wacc: {}, base: {}, equity: {} });
export const anyEdits = (e) => !!e && ['drivers', 'wacc', 'base', 'equity'].some((k) => Object.keys(e[k] || {}).length);
/** Keep one symbol's edits, or forget them when there are none; the other symbols and the saved models stay. */
export function rememberEdits(sym, e) {
  const s = readStore();
  if (anyEdits(e)) s.edits[sym] = e; else delete s.edits[sym];
  writeStore(s);
}

/* ---------------- formatting: a model value is an estimate, so the headline rounds it ---------------- */
const has = (v) => v !== null && v !== undefined && !Number.isNaN(v) && v !== '';
export const pct = (x, d = 1) => (has(x) ? `${(x * 100).toFixed(d)}%` : 'n/a');
export const signedPct = (x, d = 0) => (has(x) ? `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(d)}%` : 'n/a');
export const pts = (x, d = 1) => (has(x) ? `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(d)} pts` : 'n/a');
export function money(v, ccy) {
  if (!has(v)) return 'n/a';
  const sym = !ccy || ccy === 'USD' ? '$' : '', a = Math.abs(v), body = a >= 100 ? num(a, 0) : a >= 10 ? num(a, 1) : num(a, 2);
  return `${v < 0 ? '−' : ''}${sym}${body}${sym ? '' : ` ${ccy}`}`;
}
/** Two significant figures: "about $440". */
export function about(v) {
  if (!has(v)) return 'n/a';
  if (v <= 0) return 'nothing per share';
  const digits = Math.max(0, 2 - Math.floor(Math.log10(Math.abs(v))) - 1);
  return `about $${num(Number(v.toPrecision(2)), Math.min(2, digits))}`;
}
const big = (v) => (has(v) ? `${v < 0 ? '−' : ''}$${compact(Math.abs(v))}` : 'n/a');
function when(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' });
}
function day(iso) {
  if (!iso) return '';
  const d = new Date(`${String(iso).slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
}
/** When the price is from: the quote's own trade time when the feed gives one, else only when it was fetched. */
export const priceWhen = (m) => (m && m.market_time ? `last trade ${when(m.market_time)}` : m && m.as_of ? `quote fetched ${when(m.as_of)}` : 'time not given');
const KIND_LABEL = { reported: 'Reported', history: 'From history', external_estimate: 'Analyst estimate', market: 'Market', assumption: 'Assumption', derived: 'Derived', not_reported: 'Not reported', included_elsewhere: 'Included in debt', external: 'Quote feed' };
const kindTag = (k) => (k ? html`<span class="dcf-kind">${KIND_LABEL[k] || k}</span>` : '');

/* ---------------- the form's fields: Classic's, word for word, in core/dcf-fields.js (Milo checks a proposal against them) ---------------- */
export { FIELDS, GROUPS };
/** The equity-side models' assumptions (B7c): residual income for banks and insurers, the dividend model, and a REIT's
 *  price-to-FFO. Same mechanics as the DCF form; kept in edits.equity. */
export const EQ_FIELDS = [
  { group: 'Residual income', model: 'residual_income', key: 'ri.roe_start', label: 'Starting return on equity', unit: '%' },
  { group: 'Residual income', model: 'residual_income', key: 'ri.roe_terminal', label: 'Return on equity after ten years', unit: '%' },
  { group: 'Residual income', model: 'residual_income', key: 'ri.book_growth_start', label: 'Book value growth, first year', unit: '%' },
  { group: 'Residual income', model: 'residual_income', key: 'ri.growth_terminal', label: 'Growth after the forecast', unit: '%' },
  { group: 'Dividend model', model: 'ddm', key: 'ddm.growth_high', label: 'Dividend growth, first years', unit: '%' },
  { group: 'Dividend model', model: 'ddm', key: 'ddm.years_high', label: 'Years of that growth', unit: 'yrs' },
  { group: 'Dividend model', model: 'ddm', key: 'ddm.growth_terminal', label: 'Dividend growth after that', unit: '%' },
  { group: 'REIT', model: 'reit', key: 'reit.p_ffo', label: 'Price-to-FFO to value FFO at', unit: 'x' },
];
const EQ_SOURCE = { 'ri.roe_start': 'roe_start', 'ri.roe_terminal': 'roe_terminal', 'ri.book_growth_start': 'book_growth_start', 'ri.growth_terminal': 'growth_terminal', 'ddm.growth_high': 'growth_high', 'ddm.years_high': 'years_high', 'ddm.growth_terminal': 'growth_terminal' };
const COST_FIELDS = ['wacc.risk_free', 'wacc.beta_raw', 'wacc.erp', 'wacc.extra_premium'];
export function eqValue(d, f, which) {
  const m = d[f.model];
  if (!m || !m.available) return null;
  if (f.key === 'reit.p_ffo') return which === 'default' ? (m.own_history || {}).median : (m.at_multiple || {}).multiple;
  return which === 'default' ? (m.defaults || {})[EQ_SOURCE[f.key]] : m[EQ_SOURCE[f.key]];
}
const getPath = (o, key) => key.split('.').reduce((x, k) => (x && typeof x === 'object' ? x[k] : undefined), o);
export const fieldOf = (key) => FIELDS.find((x) => x.key === key) || EQ_FIELDS.find((x) => x.key === key) || null;
export function fieldValue(d, f, which) {
  const a = which === 'default' ? d.defaults : d.assumptions;
  if (!a) return null;
  return f.wacc ? getPath(a.wacc, f.key.slice(5)) : getPath(a.drivers, f.key);
}
/** A value as the box shows it: a percent as 12.5, a multiple or a count as itself. */
export const shown = (f, v) => (!has(v) ? '' : f.unit === '%' ? String(Number((v * 100).toFixed(3))) : String(Number(Number(v).toFixed(3))));
const unitText = (f) => (f.unit === 'x' ? '×' : f.unit);
/** Apply one box's text to the edits; returns what to tell the reader when it is not a number, else null. An empty box
 *  is the default (or, for a field with a `blank` meaning, an explicit null). */
export function setEdit(e, f, raw) {
  const text = String(raw).trim();
  let value;
  if (text === '') value = f.blank ? null : undefined;
  else {
    const n = Number(text.replace(/[,%x×\s]/g, ''));
    if (!Number.isFinite(n)) return `${f.label} needs a number.`;
    value = f.unit === '%' ? n / 100 : n;
  }
  if (f.model) {
    const [model, field] = f.key.split('.');
    e.equity = e.equity || {}; e.equity[model] = e.equity[model] || {};
    if (value === undefined || value === null) delete e.equity[model][field]; else e.equity[model][field] = value;
    if (!Object.keys(e.equity[model]).length) delete e.equity[model];
    return null;
  }
  if (f.wacc) { const k = f.key.slice(5); if (value === undefined) delete e.wacc[k]; else e.wacc[k] = value; return null; }
  const [head, tail] = f.key.split('.');
  if (tail) {
    e.drivers[head] = e.drivers[head] || {};
    if (value === undefined) delete e.drivers[head][tail]; else e.drivers[head][tail] = value;
    if (!Object.keys(e.drivers[head]).length) delete e.drivers[head];
  } else if (value === undefined) delete e.drivers[head];
  else e.drivers[head] = value;
  return null;
}
/** A missing reported line typed in from the filing: "24.4B" is 24.4e9; B, M, K or T. */
export function parseAmount(text) {
  const m = /^\s*(-?[0-9][0-9,]*\.?[0-9]*)\s*([kmbt])?\s*$/i.exec(String(text || ''));
  if (!m) return null;
  const n = Number(m[1].replace(/,/g, '')), mult = { k: 1e3, m: 1e6, b: 1e9, t: 1e12 }[(m[2] || '').toLowerCase()] || 1;
  return Number.isFinite(n) ? n * mult : null;
}

/* ---------------- state ---------------- */
const V = { sym: null, node: null, data: null, defaults: null, edits: null, loading: false, error: '', seq: 0, timer: null, open: {}, tab: 'wacc_growth', focus: null, sel: null, extra: {}, saved: null, status: '', replays: {}, compares: {}, armed: null, comps: null, sotp: null, peers: '', sotpM: {} };
const editsFor = () => { if (!V.edits) V.edits = Object.assign(blankEdits(), readStore().edits[V.sym] || {}); ['drivers', 'wacc', 'base', 'equity'].forEach((k) => { V.edits[k] = V.edits[k] || {}; }); return V.edits; };

async function load(force) {
  const sym = V.sym; V.loading = true; paint();
  const e = editsFor();
  try {
    const fresh = await api.get(`/api/valuation/${encodeURIComponent(sym)}${force ? '?refresh=true' : ''}`, { ttl: force ? 0 : 600000, force: !!force, timeout: 60000 });
    if (V.sym !== sym) return;
    V.defaults = fresh; V.data = fresh;
    // remembered edits are applied even when the defaults alone cannot run (a supplied figure is what lets them run)
    if (anyEdits(e) && fresh.available) await runNow();
  } catch (err) { if (V.sym !== sym) return; V.data = { available: false, failed: true, reason: api.explain(err, 'The fair-value model') }; }
  V.loading = false;
  if (V.sym === sym) { paint(); loadSaved(); }
}
function schedule() { clearTimeout(V.timer); V.timer = setTimeout(() => { runNow().then(() => paintResults()); }, 350); }
/** Recompute with the reader's edits (free; nothing is kept on the server). Only the newest answer is shown. */
export async function runNow(extra) {
  const sym = V.sym, seq = ++V.seq, e = extra || editsFor();
  try {
    const body = await api.post(`/api/valuation/${encodeURIComponent(sym)}/run`, { drivers: e.drivers, wacc: e.wacc, base: e.base || {}, equity: e.equity || {} }, { timeout: 60000 });
    if (extra) return body;
    if (seq !== V.seq || V.sym !== sym) return null;
    V.data = body; V.error = ''; rememberEdits(sym, e);
    return body;
  } catch (err) {
    if (extra) throw err;
    if (seq === V.seq) V.error = err.message && err.kind !== 'server' ? err.message : api.explain(err, 'The run');
    return null;
  }
}

/* ---------------- the summary ---------------- */
function lede(d) {
  const dcf = d.dcf || {}, m = d.market || {}, name = d.name || d.ticker, sc = d.scenarios || {}, cls = d.classification || {};
  const fits = ((cls.models || {}).dcf || {}).fit;
  if (!dcf.available && d.defaults && ['primary', 'supporting', 'limited'].includes(fits)) {
    return dcf.invalid ? html`<p class="dcf-lede">These assumptions have no meaningful answer: ${clean(dcf.reason || '')} Change them below, or reset to the defaults.</p>`
      : html`<p class="dcf-lede">The model could not run yet: ${clean(dcf.reason || '')} ${dcf.needs_input ? 'Open the assumptions below and enter it; nothing is filled in with a guess.' : ''}</p>`;
  }
  if (!dcf.available && (dcf.missing || []).length && fits !== 'not_applicable') return html`<p class="dcf-lede">The model could not run: ${clean(dcf.reason || '')}</p>${missingForm(d)}`;
  if (!dcf.available) {
    const ri = d.residual_income && d.residual_income.available ? d.residual_income : null, r = d.reit && d.reit.available ? d.reit : null;
    const why = clean(((cls.models || {}).dcf || {}).why || dcf.reason || '');
    if (ri) return html`<p class="dcf-lede">A cash-flow-to-the-firm model does not suit ${name}: ${why} Valuing the equity directly with residual income, this model estimates ${name} at <b>${about(ri.per_share)}</b> a share. The stock last traded at ${money(m.price, m.currency)} (${priceWhen(m)}).</p>`;
    if (r) {
      const o = r.own_history;
      return html`<p class="dcf-lede">A cash-flow-to-the-firm model does not suit ${name}: ${why} On funds from operations, the REIT yardstick, it earned ${money(r.ffo_per_share)} a share last year and trades at <b>${num(r.price_to_ffo, 1)} times FFO</b> (${money(m.price, m.currency)}, ${priceWhen(m)}).${o ? ` At the multiples it traded on over the last ${(r.years || []).filter((y) => y.p_ffo).length} fiscal years, today's FFO would be worth ${money(o.per_share_low)} to ${money(o.per_share_high)}, about ${money(o.per_share_mid)} at the median. That compares the REIT with its own past, not with what its properties are worth.` : ''}</p>`;
    }
    return html`<p class="dcf-lede">A cash-flow-to-the-firm model does not suit ${name}: ${why}</p>`;
  }
  if (cls.primary === 'ddm' && d.ddm && d.ddm.available) {
    const line = has(dcf.per_share) ? (dcf.per_share > 0 ? ` The cash-flow model, which suits it less well, gives ${about(dcf.per_share)} a share.`
      : ` The cash-flow model, which suits it less well, leaves nothing for shareholders under these assumptions${has(dcf.incremental_return) ? `: its new capital earns ${pct(dcf.incremental_return)} against a ${pct(dcf.discount_rate, 1)} cost of capital` : ''}.`) : '';
    return html`<p class="dcf-lede">For ${name}, the dividend model leads: under these assumptions it estimates <b>${about(d.ddm.per_share)}</b> a share, against a price of <b>${money(m.price, m.currency)}</b> (${priceWhen(m)}).${line}</p>`;
  }
  const v = dcf.per_share;
  if (has(v) && v <= 0) return html`<p class="dcf-lede">Under these assumptions, this model leaves nothing for ${name}'s shareholders: the debts and other claims are worth more than the operations. That says more about the assumptions than about the stock, which trades at ${money(m.price, m.currency)} (${priceWhen(m)}).</p>`;
  const rng = has((sc.bear || {}).per_share) && has((sc.bull || {}).per_share) ? ` Its bear and bull cases span ${money(sc.bear.per_share)} to ${money(sc.bull.per_share)}.` : '';
  let vs = '';
  if (has(m.price) && has(v) && v > 0) { const gap = m.price / v - 1; vs = html` The stock last traded at <b>${money(m.price, m.currency)}</b> (${priceWhen(m)}), ${Math.abs(gap) < 0.05 ? 'close to that estimate' : `${pct(Math.abs(gap), 0)} ${gap > 0 ? 'above' : 'below'} it`}.`; }
  return html`<p class="dcf-lede">Under these assumptions, this model estimates ${name} is worth <b>${about(v)}</b> a share.${rng}${vs}</p>`;
}
function missingForm(d) {
  const dcf = d.dcf || {}, e = editsFor(), labels = dcf.missing_labels || {};
  return html`<div class="dcf-missing stack"><p class="t-muted">Read ${(dcf.missing || []).map((k) => labels[k] || k).join(' and ')} for the fiscal year to ${day(dcf.fy0_end)} from the company's 10-K${dcf.filing_url ? html` (<a class="textlink" href="${dcf.filing_url}" target="_blank" rel="noopener">filing</a>)` : ''} and enter it here. It will be marked as entered by you. Amounts accept B, M or K, for example 24.4B.</p>
    ${(dcf.missing || []).map((k) => { const sg = (dcf.suggestions || {})[k]; return html`<label class="dcf-field"><span class="dcf-flabel">${labels[k] || k}</span><span class="dcf-finput"><input type="text" inputmode="decimal" data-dcf-base="${k}" value="${has((e.base || {})[k]) ? String(e.base[k]) : ''}" placeholder="for example 24.4B" autocomplete="off"></span></label>
      ${sg && sg.available && (sg.candidates || []).length ? html`<p class="t-muted">The 10-K reports these under the company's own labels, which the SEC's standard data leaves out. Pick the one that is the whole year's total (the model does not choose for you):</p>
        <div class="cluster">${sg.candidates.map((c) => html`<button type="button" class="btn btn-sm btn-quiet" data-dcf-suggest="${k}" data-value="${String(c.value)}">${big(c.value)}, ${c.element}</button>`)}</div>` : ''}`; })}
    <div class="cluster"><button type="button" class="btn btn-primary" data-dcf-base-run>Run the model</button></div></div>`;
}
function confidence(d) {
  const c = d.classification || {};
  if (!c.confidence || c.confidence === 'normal') return '';
  return html`<p class="dcf-flag"><b>${c.confidence === 'low' ? 'Low' : 'Limited'} confidence.</b> ${clean(c.label || '')}: ${clean(((c.models || {})[c.primary] || {}).why || '')} ${(c.confidence_reasons || []).map(clean).join(' ')}</p>`;
}
function checks(d) {
  const cs = ((d.dcf || {}).checks || []).filter((c) => c.level !== 'info'), ws = d.warnings || [];
  if (!cs.length && !ws.length) return '';
  return html`${cs.map((c) => html`<p class="dcf-flag"><b>${c.level === 'error' ? 'Not meaningful' : 'Check'}:</b> ${clean(c.text)}</p>`)}${ws.map((w) => html`<p class="dcf-flag"><b>Data:</b> ${clean(w.text || w)}</p>`)}`;
}
function tiles(d) {
  const dcf = d.dcf || {}, m = d.market || {}, sc = d.scenarios || {}, mos = dcf.margin_of_safety;
  return html`<dl class="kv dcf-tiles">
    <div><dt>Model value, base case</dt><dd>${money(dcf.per_share)}</dd><dd class="note">${money((sc.bear || {}).per_share)} bear, ${money((sc.bull || {}).per_share)} bull</dd></div>
    <div><dt>Market price</dt><dd>${money(m.price, m.currency)}</dd><dd class="note">${priceWhen(m)}</dd></div>
    <div><dt>Upside to the base value</dt><dd>${signedPct(dcf.upside)}</dd><dd class="note">Base value ÷ price − 1: how far the price would move to reach it</dd></div>
    <div><dt>Margin of safety</dt><dd>${has(mos) && mos > 0 ? pct(mos, 0) : 'None'}</dd><dd class="note">${has(mos) && mos > 0 ? '1 − price ÷ value: the cushion below the estimate' : 'The price is at or above the estimate, so there is no cushion'}</dd></div></dl>
    <p class="dcf-tv">${dcf.terminal_share > 1 ? html`<b>All of the value, and more, comes after year ${dcf.rows.length}:</b> the forecast years consume cash (their present value is ${big(dcf.pv_forecast)}).`
      : html`<b>${pct(dcf.terminal_share, 0)} of enterprise value</b> comes from the years after the ${dcf.rows.length}-year forecast (the terminal value).`}${dcf.terminal_share > 0.75 ? ' The result depends mostly on the long-run assumptions.' : ''}</p>`;
}

/* ---------------- what moves it, the methods, the price, the sensitivity ---------------- */
/** Each assumption moved down and up by a stated step, one at a time, centred on the base value; the two sides are told
 *  apart by which step produced them, with the value printed at each end, so colour is never the only cue. */
function tornado(d) {
  const bars = (d.tornado || []).slice(0, 6);
  if (!bars.length) return html`<p class="t-muted">No sensitivities could be run.</p>`;
  const c = d.dcf.per_share, lo = Math.min(c, ...bars.map((b) => Math.min(b.value_low, b.value_high))), hi = Math.max(c, ...bars.map((b) => Math.max(b.value_low, b.value_high)));
  const x = (v) => ((v - lo) / ((hi - lo) || 1)) * 100, step = (s) => pts(s, Math.abs(Math.round(s * 1000) % 10) ? 1 : 0);
  const seg = (v, cls) => { const a = x(Math.min(v, c)), w = Math.abs(x(v) - x(c)); return html`<span class="dcf-tbar ${cls}" style="left:${a.toFixed(2)}%;width:${Math.max(w, 0.4).toFixed(2)}%"></span>`; };
  return html`<p class="t-muted">Each bar moves one assumption by the step shown, holding the rest. Longest first.</p>
    <p class="dcf-legend"><span><i class="is-down"></i>Step down</span> <span><i class="is-up"></i>Step up</span> <span><i class="is-center"></i>Base ${money(c)}</span></p>
    <ul class="dcf-tornado" aria-label="Value per share when each assumption moves">${bars.map((b) => html`<li><span class="dcf-tlabel">${b.label}</span>
      <span class="dcf-ttrack" aria-hidden="true">${seg(b.value_low, 'is-down')}${seg(b.value_high, 'is-up')}<span class="dcf-tcenter" style="left:${x(c).toFixed(2)}%"></span></span>
      <span class="dcf-tvals">${[[b.step_low, b.value_low], [b.step_high, b.value_high]].sort((p, q) => p[1] - q[1]).map(([s, v]) => html`<span>${step(s)}: ${money(v)}</span> `)}</span></li>`)}</ul>`;
}
/** One row per method, on one axis, with the market price as a reference line; never combined (B7c adds peers and the
 *  sum of the parts through `extra`). */
export function rangeRows(d, extra = {}) {
  const sc = d.scenarios || {}, rows = [];
  if (has((sc.base || {}).per_share)) rows.push({ label: 'DCF, bear to bull', lo: sc.bear && sc.bear.per_share, mid: sc.base.per_share, hi: sc.bull && sc.bull.per_share, fit: 'primary' });
  const one = (k, label) => { const x = d[k]; if (x && x.available && has(x.per_share)) rows.push({ label, mid: x.per_share, fit: (x.fit || {}).fit }); };
  one('fcfe', 'Equity DCF (FCFE)'); one('ddm', 'Dividend discount');
  const ri = d.residual_income;
  if (ri && ri.available && ri.scenarios && has((ri.scenarios.bear || {}).per_share)) rows.push({ label: 'Residual income, bear to bull', lo: ri.scenarios.bear.per_share, mid: ri.per_share, hi: ri.scenarios.bull.per_share, fit: (ri.fit || {}).fit });
  else one('residual_income', 'Residual income');
  if (d.reit && d.reit.available && d.reit.at_multiple && d.reit.at_multiple.source === 'reader') rows.push({ label: `FFO at your ${num(d.reit.at_multiple.multiple, 1)} times`, mid: d.reit.at_multiple.per_share, fit: 'primary' });
  if (d.reit && d.reit.available && d.reit.own_history) { const o = d.reit.own_history; rows.push({ label: 'P/FFO, its own history', lo: o.per_share_low, mid: o.per_share_mid, hi: o.per_share_high, fit: 'primary' }); }
  (extra.rows || []).forEach((r) => rows.push(r));
  return rows;
}
function range(d) {
  const m = d.market || {}, rows = rangeRows(d, { rows: extraRows() });
  if (!rows.length) return html`<p class="t-muted">Nothing to compare yet.</p>`;
  const vals = rows.flatMap((r) => [r.lo, r.mid, r.hi]).filter(has).concat(has(m.price) ? [m.price] : []);
  let lo = Math.min(0, ...vals), hi = Math.max(...vals); const padv = (hi - lo) * 0.06; lo -= lo < 0 ? padv : 0; hi += padv;
  const x = (v) => ((v - lo) / ((hi - lo) || 1)) * 100, fitWord = { primary: 'fits', supporting: 'supporting', limited: 'limited fit' };
  return html`<p class="t-muted">Model values per share, each on its own assumptions. They are not averaged.</p>
    <ul class="dcf-range" aria-label="Value per share by method">${rows.map((r) => html`<li><span class="dcf-rlabel">${r.label} <span class="t-muted">${fitWord[r.fit] || ''}</span></span>
      <span class="dcf-rtrack" aria-hidden="true">${has(r.lo) && has(r.hi) ? html`<span class="dcf-rbar" style="left:${x(Math.min(r.lo, r.hi)).toFixed(2)}%;width:${Math.abs(x(r.hi) - x(r.lo)).toFixed(2)}%"></span>` : ''}<span class="dcf-rdot" style="left:${x(r.mid).toFixed(2)}%"></span>${has(m.price) ? html`<span class="dcf-rprice" style="left:${x(m.price).toFixed(2)}%"></span>` : ''}</span>
      <span class="dcf-rval">${has(r.lo) ? `${money(r.lo)} to ` : ''}<b>${money(r.mid)}</b>${has(r.hi) ? ` to ${money(r.hi)}` : ''}</span></li>`)}</ul>
    ${has(m.price) ? html`<p class="dcf-legend"><span><i class="is-price"></i>Price ${money(m.price, m.currency)}</span> <span><i class="is-dot"></i>Central value</span> <span><i class="is-bar"></i>Range</span></p>` : ''}`;
}
function reverse(d) {
  const r = d.reverse || {};
  if (!(r.solves || []).length) return html`<p class="t-muted">${clean(r.reason || 'Not available.')}</p>`;
  return html`<p class="t-muted">Many combinations can explain one price. Each line moves a single assumption until the model value equals the price and holds everything else at the current settings.</p>
    <ul class="plain">${r.solves.map((s) => html`<li><b>${s.label}.</b> ${clean(s.text)}${s.held ? html` <span class="t-muted">Held fixed: ${clean(s.held)}.</span>` : ''}</li>`)}</ul>`;
}
/** Each cell is a full model run, shaded by how far it sits from today's price (two hues, neutral near the price);
 *  the number is always printed, so shading is never the only cue. */
function heat(g, price, fmtAxis) {
  const shade = (v) => { if (!has(v) || !has(price)) return ''; const r = Math.max(-1, Math.min(1, (v / price - 1) / 0.5)), a = Math.round(Math.abs(r) * 100) / 100; return a < 0.06 ? '' : html`style="--dcf-heat:${a}" data-side="${r > 0 ? 'above' : 'below'}"`; };
  return html`<div class="tscroll"><table class="t dcf-heat"><caption class="sr">${g.row_label} down, ${g.col_label} across, value per share</caption>
    <thead><tr><th class="l" scope="col">${g.row_label} down, ${g.col_label} across</th>${g.cols.map((c, j) => html`<th scope="col" class="${j === 2 ? 'is-base' : ''}">${fmtAxis('col', c)}</th>`)}</tr></thead>
    <tbody>${g.rows.map((r, i) => html`<tr><th scope="row" class="l ${i === 2 ? 'is-base' : ''}">${fmtAxis('row', r)}</th>${g.values[i].map((v, j) => html`<td class="${i === 2 && j === 2 ? 'is-centre' : ''}" ${shade(v)}>${has(v) ? money(v) : html`<span class="t-muted" aria-label="Not meaningful: growth at or above the discount rate">n/a</span>`}</td>`)}</tr>`)}</tbody></table></div>
    <p class="asof">Outlined: the current assumptions. Shaded by how far each value sits from today's price of ${money(price)}: <span class="dcf-swatch" data-side="above"></span> above, <span class="dcf-swatch" data-side="below"></span> below. n/a means growth would reach the discount rate.</p>`;
}
function sensitivity(d) {
  const s = d.sensitivity || {}, tabs = [['wacc_growth', 'Discount rate and long-run growth'], ['margin_growth', 'Margin and growth'], ['capex_wacc', 'Capex and discount rate']].filter(([k]) => s[k]);
  if (!tabs.length) return '';
  const t = s[V.tab] ? V.tab : tabs[0][0], g = s[t];
  return html`<div class="seg dcf-tabs" role="group" aria-label="Which two assumptions">${tabs.map(([k, label]) => html`<button type="button" data-dcf-tab="${k}" aria-pressed="${k === t}">${label}</button>`)}</div>
    ${heat(g, (d.market || {}).price, (k, v) => (t === 'margin_growth' && k === 'col' ? pts(v, 0) : pct(v, 1)))}`;
}
function cases(d) {
  const sc = d.scenarios || {};
  if (!sc.base) return '';
  const cs = ['bear', 'base', 'bull'], dr = (c) => c.drivers || {};
  const row = (label, fn) => html`<tr><th scope="row" class="l">${label}</th>${cs.map((c) => html`<td>${sc[c] ? fn(sc[c]) : 'n/a'}</td>`)}</tr>`;
  return html`<h3>Bear, base and bull</h3><p class="t-muted">The cases move growth, margins, capex and the long run together, by the same amount in each direction, so the base case is not quietly the optimistic end of the range.</p>
    <div class="tscroll"><table class="t"><thead><tr><th class="l"><span class="sr">Measure</span></th><th scope="col">Bear</th><th scope="col">Base</th><th scope="col">Bull</th></tr></thead><tbody>
      ${row('Value per share', (c) => html`<b>${money(c.per_share)}</b>`)}${row('Against the price', (c) => signedPct(c.upside))}
      ${row('Revenue growth, first year', (c) => pct(dr(c).growth && dr(c).growth.y1))}${row('Operating margin it settles at', (c) => pct(dr(c).margin && dr(c).margin.target))}
      ${row('Capex it settles at', (c) => pct(dr(c).capex_pct && dr(c).capex_pct.target))}${row('Growth after the forecast', (c) => pct(dr(c).terminal && dr(c).terminal.growth))}
      ${row('Return on new capital, long run', (c) => pct(dr(c).terminal && dr(c).terminal.ronic))}${row('Terminal value share', (c) => pct(c.terminal_share, 0))}</tbody></table></div>
    <ul class="plain">${cs.map((c) => html`<li><b>${c[0].toUpperCase() + c.slice(1)}:</b> ${clean((d.scenario_text || {})[c] || '')}</li>`)}</ul>
    ${(d.what_ifs || []).length ? html`<h4 class="t-label">Single changes people ask about</h4><ul class="plain">${d.what_ifs.map((w) => html`<li>${w.label}: <b>${money(w.per_share)}</b> (${signedPct(w.change, 1)} against the base value).</li>`)}</ul>` : ''}`;
}

/* ---------------- the folded detail ---------------- */
function forecast(d) {
  const dcf = d.dcf, r = dcf.rows, tv = dcf.terminal, tm = dcf.timing || {};
  const line = (label, fn, cls) => html`<tr class="${cls || ''}"><th scope="row" class="l">${label}</th>${r.map((y) => html`<td>${fn(y)}</td>`)}</tr>`;
  const t = (d.inputs || {}).trailing || {}, tv0 = t.values || {}, g1 = getPath((d.assumptions || {}).drivers || {}, 'growth.y1');
  return html`<p class="t-muted">Fiscal years ending ${day(r[0].fiscal_year_end)} onward. ${tm.stub_fraction < 0.999 ? `The first year counts ${pct(tm.stub_fraction, 0)} of its cash flow: the balance sheet is from ${day((d.inputs || {}).balance_date)}, so only the part after it is new. ` : ''}Discounting: ${tm.convention === 'mid_year' ? 'mid-year (each year’s cash arrives at its middle)' : 'end of year'}, at ${pct(dcf.discount_rate, 2)}. D&A ${dcf.da_method === 'ppe' ? 'follows net PP&E (depreciation rate × last year’s PP&E)' : 'is a share of revenue'}.</p>
    ${t.available ? html`<p class="t-muted"><b>Trailing twelve months to ${day(t.period_end)}:</b> revenue ${big((tv0.revenue || {}).value)} (${signedPct(t.revenue_change_vs_fy0, 1)} on the fiscal year to ${day(t.fy0_end)}), operating margin ${pct(t.ebit_margin)}. The forecast starts from the fiscal year and assumes ${pct(g1)} growth in the first year, so the two can be compared directly. Built as the fiscal year + this year to date − the same months a year earlier, each from the filings.</p>` : t.reason ? html`<p class="t-muted">Trailing year: ${clean(t.reason)}</p>` : ''}
    ${has(dcf.incremental_return) ? html`<p class="t-muted"><b>What the forecast's own investment earns:</b> ${pct(dcf.incremental_return)} a year (operating profit after tax added by the last year, over the net capital invested on the way), against a ${pct(dcf.discount_rate, 1)} cost of capital. Below the cost of capital, extra capex lowers the value unless the margin or growth it buys is raised too.</p>` : ''}
    <div class="tscroll"><table class="t dcf-fc"><thead><tr><th class="l" scope="col">Year</th>${r.map((y) => html`<th scope="col">${String(y.fiscal_year_end).slice(0, 4)}</th>`)}</tr></thead><tbody>
      ${line('Revenue', (y) => big(y.revenue))}${line('Growth', (y) => pct(y.revenue_growth))}${line('Operating margin', (y) => pct(y.ebit_margin))}${line('EBIT', (y) => big(y.ebit))}
      ${line('Taxes on EBIT', (y) => big(-y.taxes))}${line('NOPAT', (y) => big(y.nopat))}${line('+ D&A', (y) => big(y.da))}${line('− Capex', (y) => big(-y.capex))}
      ${line('− Change in working capital', (y) => big(-y.change_nwc))}${line('Free cash flow to the firm', (y) => html`<b>${big(y.fcff)}</b>`, 'is-total')}
      ${line('Share of year counted', (y) => pct(y.counted_fraction, 0))}${line('Discount factor', (y) => num(y.discount_factor, 3))}${line('Present value', (y) => big(y.pv))}${line('Return on invested capital', (y) => pct(y.roic))}</tbody></table></div>
    <p><b>Terminal value</b> (${tv.method === 'value_driver' ? 'value driver' : 'growing last cash flow'}): ${tv.method === 'value_driver'
      ? `NOPAT next year ${big(tv.nopat_next)} × (1 − ${pct(tv.growth)} ÷ ${pct(tv.ronic)}) = ${big(tv.fcff_next)}, reinvesting ${pct(tv.reinvestment_rate, 0)} of profit to grow ${pct(tv.growth)} a year`
      : `${big(tv.fcff_next)} next year${has(tv.implied_ronic) ? `, which implies a ${pct(tv.implied_ronic, 0)} return on new capital` : ''}`}, ÷ (${pct(tv.rate, 2)} − ${pct(tv.growth)}) = ${big(tv.value)}, worth ${big(tv.pv)} today. That is ${has(tv.implied_exit_ev_ebitda) ? `${num(tv.implied_exit_ev_ebitda, 1)} times the last year’s EBITDA` : 'not a positive multiple of EBITDA'}.</p>
    ${dcf.exit_check ? html`<p><b>Exit-multiple cross-check:</b> at ${num(dcf.exit_check.multiple, 1)} times EBITDA (today's market multiple), the value would be ${money(dcf.exit_check.per_share)} a share${has(dcf.exit_check.implied_growth) ? `, which a perpetuity reaches only with ${pct(dcf.exit_check.implied_growth)} growth forever` : ''}. Using the market's own multiple is circular, which is why it is a check and not the answer.</p>` : ''}`;
}
function wacc(d) {
  const w = d.dcf.wacc, p = (d.assumptions || {}).wacc || {}, rf = (d.inputs || {}).risk_free || {}, rating = p.rating || {};
  if (w.override) return html`<p>The discount rate is set directly at ${pct(w.wacc, 2)}.</p>`;
  const row = (label, tag, v, note, cls) => html`<tr class="${cls || ''}"><th scope="row" class="l">${label} ${tag}</th><td>${v}</td><td class="l">${note}</td></tr>`;
  return html`<div class="tscroll"><table class="t dcf-wacc"><tbody>
    ${row('Risk-free rate', kindTag('market'), pct(w.risk_free, 2), `${rf.source || ''}${rf.as_of ? `, ${day(rf.as_of)}` : ''}`)}
    ${row('Beta', kindTag('market'), num(w.beta, 2), `Raw ${num(w.beta_raw, 2)}: ${((((d.inputs || {}).quote || {}).beta_meta || {}).source) || 'the quote feed'} (a regression on past returns, so an estimate), ${p.beta_adjust === 'raw' ? 'used as is' : 'adjusted toward 1 (Blume: 0.67 × raw + 0.33), since measured betas drift toward the market’s over time'}.`)}
    ${row('Equity risk premium', kindTag('assumption'), pct(w.erp, 2), 'Damodaran\'s implied premium for the S&P 500, January 2026. An estimate, not an observable fact.')}
    ${w.extra_premium ? row('Extra premium', '', pct(w.extra_premium, 2), 'Yours.') : ''}
    ${row('Cost of equity', '', pct(w.cost_equity, 2), 'Risk-free + beta × premium (CAPM).', 'is-total')}
    ${row('Pre-tax cost of debt', kindTag(p.kd_source === 'filing_implied' ? 'derived' : 'assumption'), pct(w.pre_tax_cost_debt, 2), p.kd_source === 'filing_implied' ? `Interest expense ÷ debt from the filings (${pct(p.implied_cost_debt, 2)}): with operating losses, an interest-coverage rating is undefined.`
      : `Risk-free + a ${pct(rating.spread, 2)} spread for a synthetic ${rating.rating || ''} rating${has(rating.coverage) ? ` (operating income covers interest ${num(rating.coverage, 1)} times)` : ''}. Damodaran's table, January 2026.${has(p.implied_cost_debt) ? ` The filings' interest ÷ debt is ${pct(p.implied_cost_debt, 2)}, which reflects older coupons.` : ''}`)}
    ${row('After-tax cost of debt', '', pct(w.after_tax_cost_debt, 2), `× (1 − ${pct(w.tax_rate, 0)}).`)}
    ${row('Weights', '', `${pct(w.weight_equity, 1)} and ${pct(w.weight_debt, 1)}`, has(w.equity_market_value) ? `Equity at market value (${big(w.equity_market_value)}), debt and finance leases at book (${big(w.debt_book_value)}). Gross debt, because cash is counted separately in the bridge.` : 'Your debt weight.')}
    ${row('Discount rate (WACC)', '', html`<b>${pct(w.wacc, 2)}</b>`, 'Equity weight × cost of equity + debt weight × after-tax cost of debt.', 'is-total')}</tbody></table></div>`;
}
function factLink(f) {
  if (!f) return '';
  const label = [f.tag, f.form, f.end ? day(f.end) : ''].filter(Boolean).join(', '), note = f.note || f.reason || f.rule || '';
  return html`${f.url ? html`<a class="textlink" href="${f.url}" target="_blank" rel="noopener">${label || 'filing'}</a>` : label}${f.restated ? html` <span class="dcf-kind">restated</span>` : ''}${note ? html` <span class="t-muted">${clean(note)}</span>` : ''}`;
}
function bridge(d) {
  const br = d.dcf.bridge, facts = (d.inputs || {}).bridge || {}, sh = (d.inputs || {}).shares || {}, op = (d.inputs || {}).operating_lease;
  return html`<div class="tscroll"><table class="t dcf-bridge"><tbody>
    ${br.lines.map((l) => html`<tr class="${l.key === 'enterprise_value' ? 'is-total' : ''}${l.included === false && l.value !== null ? ' is-off' : ''}"><th scope="row" class="l">${l.key === 'enterprise_value' ? '' : l.sign > 0 ? '+ ' : '− '}${l.label}</th>
      <td>${l.value === null ? 'not reported' : big(l.value)}</td><td class="l">${l.key === 'enterprise_value' ? 'Present value of the forecast and the terminal value' : factLink(facts[l.key])}
      ${l.key !== 'enterprise_value' && l.value !== null ? html` <label class="check dcf-inc"><input type="checkbox" data-dcf-bridge="${l.key}" ${l.included === false ? '' : 'checked'}> <span>Count it</span></label>` : ''}</td></tr>`)}
    <tr class="is-total"><th scope="row" class="l">Equity value</th><td>${big(d.dcf.equity_value)}</td><td></td></tr>
    <tr><th scope="row" class="l">÷ Diluted shares</th><td>${compact(d.dcf.shares)}</td><td class="l">${clean(sh.method || '')}. ${clean(sh.note || '')}</td></tr>
    <tr class="is-total"><th scope="row" class="l">Value per share</th><td><b>${money(d.dcf.per_share)}</b></td><td></td></tr></tbody></table></div>
    <ul class="plain"><li><b>Operating leases</b>${op && has(op.value) ? ` (${big(op.value)})` : ''} are not subtracted: their cost is already inside EBIT. Subtracting the liability as well would charge them twice.</li>
      <li><b>Stock-based compensation</b> is left in EBIT as an expense and not added back. Awards already granted are in the diluted share count; future grants are paid for through that expense.</li>
      <li><b>Cash</b> is all treated as surplus; a business that needs some cash to operate is worth slightly less than this.</li>
      <li>Investments, preferred stock and non-controlling interests are at book value; a listed stake's market value can differ a lot.</li></ul>`;
}
function statements(d) {
  const ts = d.three_statement || {};
  if (!ts.available) return html`<p class="t-muted">${clean(ts.reason || 'Not available.')}</p>`;
  const y = ts.years, line = (label, k, cls) => html`<tr class="${cls || ''}"><th scope="row" class="l">${label}</th>${y.map((r) => html`<td>${big(r[k])}</td>`)}</tr>`;
  const sub = (t) => html`<tr class="dcf-sub"><th colspan="${y.length + 1}" class="l">${t}</th></tr>`;
  return html`<p class="${ts.balances ? 't-muted' : 'dcf-flag'}"><b>${clean(ts.label)}.</b> ${ts.balances ? `Assets equal liabilities plus equity in every year (largest gap ${big(ts.max_imbalance)}).` : `The balance sheet does not balance: ${big(ts.max_imbalance)}. Treat these statements as unreliable.`} ${ts.reconciles_with_dcf ? 'Free cash flow from these statements equals the DCF’s every year.' : clean(ts.reconcile_note || '')}</p>
    <div class="tscroll"><table class="t dcf-fc"><thead><tr><th class="l"><span class="sr">Line</span></th>${y.map((r) => html`<th scope="col">Year ${r.year}</th>`)}</tr></thead><tbody>
      ${sub('Income statement')}${line('Revenue', 'revenue')}${line('EBIT', 'ebit')}${line('Interest expense', 'interest_expense')}${line('Interest income', 'interest_income')}${line('Taxes', 'taxes')}${line('Net income', 'net_income', 'is-total')}
      ${sub('Cash flow')}${line('Operating cash flow', 'cfo')}${line('Capex', 'cfi')}${line('Dividends', 'dividends')}${line('Buybacks', 'buybacks')}${line('Net borrowing', 'net_borrowing')}${line('Change in cash', 'change_cash', 'is-total')}
      ${sub('Balance sheet')}${line('Cash', 'cash')}${line('Net PP&E', 'ppe')}${line('Total assets', 'total_assets', 'is-total')}${line('Debt', 'debt')}${line('Total liabilities', 'total_liabilities')}${line('Equity', 'equity', 'is-total')}${line('Assets − liabilities − equity', 'balance_check')}</tbody></table></div>
    <ul class="plain">${(ts.notes || []).map((n) => html`<li>${clean(n)}</li>`)}<li>Starting balance sheet ${day((ts.start || {}).date)}: other assets and other liabilities are what remains of the reported totals, so the start balances by construction${has((ts.start || {}).unexplained_equity) && Math.abs(ts.start.unexplained_equity) > 1 ? `; reported equity differs from assets less liabilities by ${big(ts.start.unexplained_equity)} (temporary or mezzanine equity)` : ''}.</li></ul>`;
}
function sources(d) {
  const h = (d.inputs || {}).history || [];
  if (!h.length) return '';
  const rows = [['Revenue', 'revenue'], ['Operating income', 'operating_income'], ['Pre-tax income', 'pretax_income'], ['Income tax', 'income_tax'], ['Net income', 'net_income'], ['D&A', 'da'], ['Capex', 'capex'], ['Operating cash flow', 'cfo'], ['Stock compensation', 'sbc'], ['Interest expense', 'interest_expense'], ['Dividends paid', 'dividends_paid'], ['Buybacks', 'buybacks']];
  const ratios = [['Revenue growth', 'revenue_growth'], ['Operating margin', 'ebit_margin'], ['Effective tax rate', 'effective_tax_rate'], ['Capex / revenue', 'capex_pct'], ['Working capital / revenue', 'nwc_pct'], ['Return on invested capital', 'roic'], ['FCFF (rebuilt)', 'fcff', 'money'], ['Operating cash flow − capex', 'fcf_simple', 'money'], ['Tagged restructuring and impairment', 'unusual_items', 'money'], ['Operating margin excluding them', 'ebit_margin_normalized'], ['Acquisitions / revenue', 'acquisitions_pct']];
  const cell = (f) => (f && has(f.value) ? html`<td>${f.url ? html`<a class="textlink" href="${f.url}" target="_blank" rel="noopener" aria-label="${[f.tag, f.form, f.filed && `filed ${f.filed}`].filter(Boolean).join(', ')}">${big(f.value)}</a>` : big(f.value)}${f.restated ? '*' : ''}</td>` : html`<td class="t-muted">not reported</td>`);
  return html`<p class="t-muted">Fiscal years from the company's 10-K filings (SEC EDGAR, US-GAAP XBRL). Each figure links to its filing. * restated in a later filing (the latest figure is used). Filings retrieved ${when((d.inputs || {}).retrieved)}.</p>
    <div class="tscroll"><table class="t dcf-fc"><thead><tr><th class="l"><span class="sr">Line</span></th>${h.map((y) => html`<th scope="col">FY ${String(y.fy_end).slice(0, 4)}</th>`)}</tr></thead>
    <tbody>${rows.map(([label, k]) => html`<tr><th scope="row" class="l">${label}</th>${h.map((y) => cell((y.facts || {})[k]))}</tr>`)}
      <tr class="dcf-sub"><th colspan="${h.length + 1}" class="l">Derived (reported figures, same periods)</th></tr>
      ${ratios.map(([label, k, kind]) => html`<tr><th scope="row" class="l">${label}</th>${h.map((y) => html`<td>${kind === 'money' ? big((y.derived || {})[k]) : pct((y.derived || {})[k])}</td>`)}</tr>`)}</tbody></table></div>
    <p class="asof">Restructuring and impairment are only what the filings tag under standard names; a charge tagged with the company's own label is not caught, so the normalised margin is a partial adjustment and never the default.</p>
    <p class="asof">${clean((d.inputs || {}).source_note || '')} Rebuilt FCFF uses the reported working-capital change, which can swing with one-off items; the forecast holds working capital at a steady share of revenue instead.</p>`;
}
const formulas = () => html`<ul class="plain dcf-formulas">
  <li><b>Free cash flow to the firm</b> = EBIT × (1 − tax rate) + D&A − capex − change in operating working capital.</li>
  <li><b>Operating working capital</b> = (current assets − cash − short-term investments) − (current liabilities − current debt − current lease liabilities).</li>
  <li><b>Taxes</b> apply to EBIT; a loss carries forward and shelters later profit. Interest's tax saving sits in the discount rate instead.</li>
  <li><b>D&A</b> = depreciation rate × last year's net PP&E; PP&E grows by capex less D&A.</li>
  <li><b>Discounting</b>: factor = (1 + WACC) to the power −t, t in fiscal years from the valuation date; mid-year puts each flow at its year's middle. The first year counts only the part after the balance sheet.</li>
  <li><b>Terminal value</b> = NOPAT in year N+1 × (1 − g ÷ RONIC) ÷ (WACC − g), valued at the end of year N (half a year sooner under mid-year). Growth at or above WACC is refused.</li>
  <li><b>Equity</b> = enterprise value + cash + investments − debt − finance leases − preferred − non-controlling interests − unfunded pensions. <b>Per share</b> = equity ÷ diluted shares.</li>
  <li><b>WACC</b> = E/V × (risk-free + β × ERP) + D/V × cost of debt × (1 − t).</li>
  <li><b>Upside</b> = value ÷ price − 1. <b>Margin of safety</b> = 1 − price ÷ value.</li>
  <li><b>Residual income</b>: value = book + Σ (ROE − cost of equity) × opening book, discounted; justified P/B = (ROE − g) ÷ (cost of equity − g).</li>
  <li><b>Dividend discount</b>: two stages, dividends discounted at the cost of equity, a growing perpetuity after five years.</li>
  <li>Full notes: app/valuation/METHODS.md in the source.</li></ul>`;
/** Classic's questions, as quiet buttons that draft into Milo; nothing is sent. */
function asks(d) {
  const n = d.ticker, ok = (d.dcf || {}).available, ri = d.residual_income;
  const qs = !ok ? [`Why doesn't a DCF suit ${n}?`, ri && ri.available ? `What return on equity does ${n}'s price imply?` : `Which method fits ${n} best, and why?`, ri && ri.available ? `Is ${n}'s return on equity sustainable?` : `What does ${n}'s price imply?`, `Which assumptions matter most in ${n}'s valuation?`]
    : [`Why is ${n}'s model value ${(d.dcf || {}).upside < 0 ? 'below' : 'above'} the market price?`, `Which assumptions matter most in ${n}'s valuation?`, `What happens to ${n}'s value if capital spending stays elevated?`, `How much of ${n}'s value comes from the terminal period?`, `What growth would justify ${n}'s price today?`, `Is a DCF appropriate for ${n}?`];
  return html`<div class="dcf-asks"><p class="t-label">Ask Milo about this model</p><div class="cluster">${qs.map((q) => html`<button type="button" class="btn btn-sm btn-quiet" data-v2-milo="${q}" data-v2-milo-ctx="${n} fair-value model" data-v2-milo-sym="${n}">${q}</button>`)}</div>
    <p class="asof">Each puts the question in Milo's box with this model attached; nothing is sent until you press Send.</p></div>`;
}
const fold = (key, title, body) => html`<details class="more-inline dcf-fold" data-dcf-sec="${key}" ${V.open[key] ? 'open' : ''}><summary>${title}</summary><div class="how-body">${body}</div></details>`;

/* ---------------- the form ---------------- */
function formStatus(d) {
  const n = ((d.assumptions || {}).changed || []).length;
  return n ? html`${n} assumption${n === 1 ? '' : 's'} changed from the defaults. <button type="button" class="btn btn-sm btn-quiet" data-dcf-reset>Reset to the defaults</button>` : 'All assumptions are at their defaults.';
}
const OVERRIDE_ROWS = [['revenue_growth', 'Revenue growth'], ['ebit_margin', 'Operating margin'], ['capex_pct', 'Capex / revenue']];
function overrides(d) {
  const rows = (d.dcf || {}).rows || [];
  if (!rows.length) return '';
  const ov = (editsFor().drivers || {}).overrides || {};
  return fold('overrides', 'Set individual years', html`<div class="tscroll"><table class="t dcf-ov"><thead><tr><th class="l"><span class="sr">Line</span></th>${rows.map((r) => html`<th scope="col">${String(r.fiscal_year_end).slice(0, 4)}</th>`)}</tr></thead>
    <tbody>${OVERRIDE_ROWS.map(([k, label]) => html`<tr><th scope="row" class="l">${label} %</th>${rows.map((r) => { const typed = (ov[k] || {})[String(r.year)]; return html`<td><input type="text" inputmode="decimal" class="dcf-ovin" data-dcf-ov="${k}" data-year="${r.year}" value="${has(typed) ? String(Number((typed * 100).toFixed(3))) : ''}" placeholder="${(r[k] * 100).toFixed(1)}" aria-label="${label}, ${String(r.fiscal_year_end).slice(0, 4)}" autocomplete="off"></td>`; })}</tr>`)}</tbody></table></div>
    <p class="asof">A year you type here wins over the path the drivers above draw. Empty boxes follow the drivers.</p>`);
}
function form(d) {
  if (!d.defaults) return '';
  const why = {}; (d.defaults.rationale || []).forEach((r) => { why[r.key] = r; });
  const changed = new Set((d.assumptions || {}).changed || []), e = editsFor(), drv = (d.assumptions || {}).drivers || {}, wa = (d.assumptions || {}).wacc || {};
  const field = (f) => {
    const cur = fieldValue(d, f, 'current'), def = fieldValue(d, f, 'default'), w = f.why ? why[f.why] : null;
    const raw = f.wacc ? e.wacc[f.key.slice(5)] : getPath(e.drivers, f.key), id = `dcf-why-${f.key.replace(/\./g, '-')}`;
    return html`<label class="dcf-field${changed.has(f.key) ? ' is-edited' : ''}"><span class="dcf-flabel">${f.label} ${w ? kindTag(w.kind) : ''}</span>
      <span class="dcf-finput"><input type="text" inputmode="decimal" data-dcf-field="${f.key}" value="${raw === undefined ? '' : shown(f, raw)}" placeholder="${has(cur) ? shown(f, cur) : (f.blank || '')}" aria-describedby="${id}" autocomplete="off"><span class="dcf-unit" aria-hidden="true">${unitText(f)}</span></span>
      <span class="dcf-fwhy" id="${id}">Default ${has(def) ? `${shown(f, def)}${f.unit === '%' ? '%' : f.unit === 'x' ? ' times' : ''}` : (f.blank || 'none')}. ${w ? clean(w.why) : ''}</span></label>`;
  };
  const sel = (key, opts, val) => html`<select data-dcf-select="${key}">${opts.map(([v, l]) => html`<option value="${v}" ${v === val ? 'selected' : ''}>${l}</option>`)}</select>`;
  const openForm = V.open.form || ((d.dcf || {}).needs_input && V.open.form !== false);
  return html`<details class="more-inline dcf-fold dcf-form" data-dcf-sec="form" ${openForm ? 'open' : ''}><summary>Assumptions: see why each was chosen, and change any of them</summary><div class="how-body">
    <p class="t-muted">Leave a box empty to use the default shown in grey. Values recalculate as you type. Your changes are kept in this browser until you reset them.</p>
    <p class="dcf-status" data-dcf-status role="status">${formStatus(d)}</p>
    ${GROUPS.map((g) => html`<fieldset class="dcf-group"><legend class="t-label">${g}</legend>${FIELDS.filter((f) => f.group === g).map(field)}</fieldset>`)}
    <fieldset class="dcf-group"><legend class="t-label">Method</legend>
      <label class="dcf-field"><span class="dcf-flabel">Discounting</span>${sel('convention', [['mid_year', 'Mid-year (cash arrives through the year)'], ['end_year', 'End of year']], drv.convention === 'end_year' ? 'end_year' : 'mid_year')}</label>
      <label class="dcf-field"><span class="dcf-flabel">Terminal value</span>${sel('terminal.method', [['value_driver', 'Value driver: growth costs reinvestment'], ['fcf_growth', 'Grow the last year\'s cash flow']], (drv.terminal || {}).method === 'fcf_growth' ? 'fcf_growth' : 'value_driver')}</label>
      <label class="dcf-field"><span class="dcf-flabel">Beta</span>${sel('wacc.beta_adjust', [['blume', 'Adjusted toward 1 (Blume)'], ['raw', 'Raw, as measured']], wa.beta_adjust === 'raw' ? 'raw' : 'blume')}</label></fieldset>
    ${overrides(d)}</div></details>`;
}

/* ---------------- the other methods, peers and the sum of the parts (B7c; Classic valuation.js:904-1013, 1087-1150) ---------------- */
/** Peers' multiples (not price to book, not a spread too wide to read) and the sum of the parts, as rows beside the DCF. */
export function extraRowsOf(comps, sotp) {
  const rows = [];
  if (comps && comps.available) (comps.implied || []).filter((c) => c.implied && c.key !== 'pb' && !c.wide).forEach((c) => rows.push({ label: `Peers' ${c.label}`, lo: c.implied.low.per_share, mid: c.implied.mid.per_share, hi: c.implied.high.per_share, fit: 'supporting' }));
  if (sotp && sotp.available && has(sotp.per_share)) rows.push({ label: 'Sum of the parts', mid: sotp.per_share, fit: 'supporting' });
  return rows;
}
const extraRows = () => extraRowsOf(V.comps, V.sotp);
async function loadComps() {
  const sym = V.sym, peers = String(V.peers || '').trim();
  V.comps = { loading: true }; V.open.methods = true; paintResults();
  try { V.comps = await api.get(`/api/valuation/${encodeURIComponent(sym)}/comps${peers ? `?peers=${encodeURIComponent(peers)}` : ''}`, { ttl: 0, force: true, timeout: 90000 }); }
  catch (err) { V.comps = { available: false, reason: api.explain(err, 'The peer multiples') }; }
  if (V.sym === sym) { paintResults(); const b = V.node.querySelector('[data-dcf-comps]'); if (b) b.focus({ preventScroll: true }); }
}
async function loadSotp(withInputs) {
  const sym = V.sym, e = editsFor(), body = { drivers: e.drivers, wacc: e.wacc, base: e.base || {}, equity: e.equity || {} };
  if (withInputs) { body.multiples = {}; Object.entries(V.sotpM).forEach(([k, v]) => { if (k !== '__u') body.multiples[k] = String(v).trim(); }); if (V.sotpM.__u !== undefined) body.unallocated_multiple = String(V.sotpM.__u).trim(); }
  if (!withInputs) V.sotp = { loading: true };
  V.open.methods = true; paintResults();
  try { V.sotp = await api.post(`/api/valuation/${encodeURIComponent(sym)}/sotp`, body, { timeout: 90000 }); V.sotpM = {}; }
  catch (err) { V.sotp = { available: false, reason: api.explain(err, 'The segments') }; }
  if (V.sym === sym) { paintResults(); const b = V.node.querySelector(withInputs ? '[data-dcf-sotp-run]' : '[data-dcf-sotp]'); if (b) b.focus({ preventScroll: true }); }
}
const mult = (v) => (has(v) && v > 0 ? `${num(v, 1)} times` : 'n/a');
function compsHTML() {
  const c = V.comps, sym = V.sym;
  const ask = html`<div class="dcf-save-row"><label class="dcf-save-name"><span class="t-label">Peers (optional, comma-separated)</span><input type="text" data-dcf-peers value="${V.peers}" placeholder="for example ORCL, ADBE, CRM" autocomplete="off" autocapitalize="characters" spellcheck="false"></label>
    <button type="button" class="btn" data-dcf-comps>${c && c.available ? 'Compare again' : 'Compare with peers'}</button></div>`;
  if (!c) return html`${ask}<p class="t-muted">Without a list, the largest companies in the same industry within 25 times of its size, the eight closest.</p>`;
  if (c.loading) return html`${ask}<p class="t-muted" role="status">Reading peer multiples…</p>`;
  if (!c.available) return html`${ask}<p class="dcf-flag">${clean(c.reason || 'No peers.')}</p>`;
  return html`${ask}
    <p class="t-muted">${clean(c.note || '')} Source: ${clean(c.source || '')}. Peers: ${c.peer_source === 'reader' ? 'yours' : c.peer_source === 'industry_and_sector' ? 'the industry’s largest within the size band, with the sector’s largest added because the industry has too few of this size' : 'the industry’s largest within the size band'}.</p>
    ${(c.flags || []).length ? html`<p class="dcf-flag"><b>Peers disagree widely.</b> ${c.flags.map(clean).join(' ')} Read these values as a range, not an answer, or enter peers you consider comparable above.</p>` : ''}
    <div class="tscroll"><table class="t"><thead><tr><th class="l">Multiple</th><th>${sym}</th><th>Peers: 25th, median, 75th</th><th>Implied a share</th></tr></thead><tbody>
      ${(c.implied || []).map((i) => html`<tr><th scope="row" class="l">${i.label}</th><td>${mult(i.own_multiple)}</td>
        <td>${i.implied ? `${mult(i.implied.low.multiple)}, ${mult(i.implied.mid.multiple)}, ${mult(i.implied.high.multiple)}` : 'n/a'} <span class="t-muted">${String(i.peers_with_value)} peers${(i.outliers || []).length ? `; set aside as outliers: ${i.outliers.join(', ')}` : ''}</span></td>
        <td>${i.implied ? html`${money(i.implied.low.per_share)} to <b>${money(i.implied.mid.per_share)}</b> to ${money(i.implied.high.per_share)}` : clean(i.reason || '')}${i.note ? html` <span class="t-muted">${clean(i.note)}</span>` : ''}</td></tr>`)}</tbody></table></div>
    <div class="tscroll"><table class="t"><thead><tr><th class="l">Peer</th><th>Market value</th><th>EV / EBITDA</th><th>EV / revenue</th><th>P / E</th><th>P / B</th></tr></thead><tbody>
      ${(c.peers || []).map((x) => html`<tr><th scope="row" class="l"><b class="tick">${x.symbol}</b> <span class="t-muted">${x.name || ''}${x.origin === 'sector' ? ', sector peer' : ''}</span></th><td>${big(x.market_cap)}</td><td>${mult(x.ev_ebitda)}</td><td>${mult(x.ev_revenue)}</td><td>${mult(x.pe)}</td><td>${mult(x.pb)}</td></tr>`)}
      ${(c.excluded || []).map((x) => html`<tr class="is-off"><th scope="row" class="l">${x.symbol}</th><td colspan="5" class="l t-muted">Not used: ${clean(x.why)}</td></tr>`)}</tbody></table></div>`;
}
function sotpHTML() {
  const r = V.sotp;
  if (!r) return html`<div class="cluster"><button type="button" class="btn" data-dcf-sotp>Value the segments</button></div><p class="t-muted">Reads segment operating income from the last four quarterly filings.</p>`;
  if (r.loading) return html`<p class="t-muted" role="status">Reading the segment filings…</p>`;
  if (!r.available) return html`<p class="dcf-flag">${clean(r.reason || 'Not available.')}</p><div class="cluster"><button type="button" class="btn btn-sm" data-dcf-sotp>Try again</button></div>`;
  const per = r.period || {}, rec = r.reconciles === true ? `The parts add up to the company's operating income for the same year (${big(r.company_ebit_fy0)}).`
    : r.reconciles === false ? `The parts add up to ${big(r.segments_ttm_total)} against operating income of ${big(r.company_ebit_fy0)}, so a line is missing or counted twice; treat the result with care.` : '';
  const mIn = (key, v, label) => html`<input type="text" inputmode="decimal" class="dcf-ovin" data-dcf-sotp-m="${key}" value="${V.sotpM[key] !== undefined ? V.sotpM[key] : has(v) ? num(v, 1) : ''}" aria-label="${label}" autocomplete="off"> <span class="t-muted">times</span>`;
  return html`<p class="t-muted">${clean(r.note || '')} ${clean(r.period_note || '')} ${rec} ${per.kind === 'trailing_four_quarters' && r.q4_derived ? 'A fourth quarter is derived as the year less the first three.' : ''}</p>
    <div class="tscroll"><table class="t dcf-sotp"><thead><tr><th class="l">${r.axis_label || 'Segment'}</th><th>Operating income, ${per.kind === 'fiscal_year' ? `fiscal year to ${day(per.end)}` : 'last 4 quarters'}</th><th>EV / EBIT</th><th>Value</th></tr></thead><tbody>
      ${(r.segments || []).map((g) => html`<tr><th scope="row" class="l">${g.name}</th><td>${big(g.operating_income)}</td><td>${has(g.operating_income) ? mIn(g.name, g.multiple, `EV/EBIT for ${g.name}`) : clean(g.note || '')}</td><td>${big(g.value)}</td></tr>`)}
      <tr><th scope="row" class="l">Corporate and eliminations</th><td>${big(r.unallocated)}</td><td>${mIn('__u', r.unallocated_value && r.unallocated ? r.unallocated_value / r.unallocated : r.dcf_implied_ev_ebit, 'EV/EBIT for unallocated costs')}</td><td>${big(r.unallocated_value)}</td></tr>
      <tr class="is-total"><th scope="row" class="l">Enterprise value</th><td>${big(r.segments_ttm_total)}</td><td></td><td>${big(r.enterprise_value)}</td></tr>
      <tr class="is-total"><th scope="row" class="l">Value per share (same bridge as the DCF)</th><td></td><td></td><td><b>${money(r.per_share)}</b></td></tr></tbody></table></div>
    <p><b>Sum of the parts: ${money(r.per_share)} a share</b> (enterprise value ${big(r.enterprise_value)}, ${signedPct(r.upside, 0)} against the price).</p>
    <p class="t-muted">Multiples start at the DCF's implied ${num(r.dcf_implied_ev_ebit, 1)} times EV/EBIT, which reproduces the whole; change the segments you think are worth more or less.</p>
    <div class="cluster"><button type="button" class="btn btn-sm" data-dcf-sotp-run>Recalculate</button></div>`;
}
function methodsHTML(d) {
  const c = d.classification || {}, fits = c.models || {};
  const order = ['dcf', 'fcfe', 'ddm', 'residual_income', 'reit_ffo', 'comps', 'sotp', 'reverse_dcf'];
  const word = { primary: 'Fits', supporting: 'Supporting', limited: 'Limited', not_applicable: 'Does not apply' };
  const out = {
    fcfe: () => (d.fcfe && d.fcfe.available ? `${money(d.fcfe.per_share)} a share at a ${pct(d.fcfe.cost_equity, 2)} cost of equity. ${clean((d.fcfe.notes || []).join(' '))}` : d.fcfe ? clean(d.fcfe.reason || '') : ''),
    ddm: () => (d.ddm && d.ddm.available ? `${money(d.ddm.per_share)} a share: dividends of ${money(d.ddm.dps0)} growing ${pct(d.ddm.growth_high)} for five years, then ${pct(d.ddm.growth_terminal)}, at ${pct(d.ddm.cost_equity, 2)}. ${clean(d.ddm.growth_note || '')}` : d.ddm ? clean(d.ddm.reason || '') : ''),
    residual_income: () => { const r = d.residual_income; if (!r) return ''; if (!r.available) return clean(r.reason || '');
      return html`${money(r.per_share)} a share: book value ${money(r.book_value_0)} plus the value of a ${pct(r.roe_start)} return on equity against a ${pct(r.cost_equity, 2)} cost, fading to ${pct(r.roe_terminal)}. Today's price is ${num(r.price_to_book, 2)} times book, which in perpetuity needs a ${pct(r.implied_roe)} return on equity. ${clean((r.notes || []).join(' '))} ${(r.flags || []).map((f) => html`<b>Check:</b> ${clean(f)} `)}`; },
    reit_ffo: () => { const r = d.reit; if (!r) return ''; if (!r.available) return clean(r.reason || '');
      return `FFO ${money(r.ffo_per_share)} a share; the price is ${num(r.price_to_ffo, 1)} times FFO, and dividends take ${pct(r.ffo_payout, 0)} of FFO. ${r.own_history ? `At the multiples of the last few years (${num(r.own_history.low, 1)} to ${num(r.own_history.high, 1)} times, median ${num(r.own_history.median, 1)}), today's FFO is worth ${money(r.own_history.per_share_low)} to ${money(r.own_history.per_share_high)}. ${clean(r.own_history.note || '')}` : ''} ${clean(r.affo_reason || '')}`; },
    comps: compsHTML, sotp: sotpHTML,
  };
  return html`<p class="t-muted">${clean(c.label || '')}. Which methods suit this business, and why. Values from different methods answer different questions, so they are shown side by side and never averaged.</p>
    <ul class="dcf-methods">${order.filter((k) => fits[k]).map((k) => html`<li><p><b>${fits[k].name}</b> <span class="dcf-kind">${word[fits[k].fit] || ''}</span></p><p class="t-muted">${clean(fits[k].why || '')}</p>${out[k] ? html`<div class="dcf-m-out">${out[k]()}</div>` : ''}</li>`)}</ul>`;
}
/** The equity models' form: residual income, the dividend model and a REIT's multiple, with the cost of equity when the
 *  cash-flow model does not suit. */
function equityForm(d) {
  const fields = EQ_FIELDS.filter((f) => d[f.model] && d[f.model].available && has(eqValue(d, f, 'default')));
  if (!fields.length) return '';
  const e = editsFor(), ok = (d.dcf || {}).available, parts = d.equity_wacc_parts || {}, defParts = d.wacc_parts_default || {};
  const fmtv = (f, v) => (has(v) ? `${shown(f, v)}${f.unit === '%' ? '%' : f.unit === 'x' ? ' times' : ''}` : 'none');
  const field = (f, cur, def, typed, edited) => html`<label class="dcf-field${edited ? ' is-edited' : ''}"><span class="dcf-flabel">${f.label}</span>
    <span class="dcf-finput"><input type="text" inputmode="decimal" data-dcf-field="${f.key}" value="${typed === undefined ? '' : shown(f, typed)}" placeholder="${has(cur) ? shown(f, cur) : ''}" autocomplete="off"><span class="dcf-unit" aria-hidden="true">${unitText(f)}</span></span>
    <span class="dcf-fwhy">Default ${fmtv(f, def)}.</span></label>`;
  const groups = [...new Set(fields.map((f) => f.group))];
  const costs = ok ? '' : html`<fieldset class="dcf-group"><legend class="t-label">Cost of equity</legend>${COST_FIELDS.map((k) => { const f = FIELDS.find((x) => x.key === k), sub = k.slice(5); return field(f, parts[sub], defParts[sub], e.wacc[sub], has(e.wacc[sub])); })}</fieldset>`;
  const open = V.open.equityform || (!ok && V.open.equityform !== false);
  return html`<details class="more-inline dcf-fold" data-dcf-sec="equityform" ${open ? 'open' : ''}><summary>${ok ? 'Assumptions for the dividend model' : 'Assumptions: see the defaults, and change any of them'}</summary><div class="how-body">
    <p class="t-muted">Leave a box empty to use the default. Values recalculate as you type.</p>
    ${groups.map((g) => html`<fieldset class="dcf-group"><legend class="t-label">${g}</legend>${fields.filter((f) => f.group === g).map((f) => { const [model, sub] = f.key.split('.'); const typed = ((e.equity || {})[model] || {})[sub]; return field(f, eqValue(d, f, 'current'), eqValue(d, f, 'default'), typed, has(typed)); })}</fieldset>`)}
    ${costs}<p class="dcf-status"><button type="button" class="btn btn-sm btn-quiet" data-dcf-reset>Reset to the defaults</button></p></div></details>`;
}

/* ---------------- saved models (B7b; Classic valuation.js:1194-1364) ---------------- */
async function loadSaved() {
  const sym = V.sym;
  if (store.signedIn()) {
    try { const b = await api.get(`/api/valuation-models?symbol=${encodeURIComponent(sym)}`, { ttl: 0, force: true }); if (V.sym === sym) V.saved = { where: 'account', models: (b && b.models) || [], limit: b && b.limit }; }
    catch (e) { if (V.sym === sym) V.saved = { where: 'account', models: [], error: api.explain(e, 'Saved models') }; }
  } else V.saved = { where: 'browser', models: readStore().models.filter((m) => m && m.symbol === sym) };
  if (V.sym === sym) paintSaved();
}
/** What a snapshot keeps: the reported figures, the assumptions and the result together, so it can be rerun exactly. */
export function snapshotOf(sym, d, name, supplied) {
  return { symbol: sym, name, base: d.base, assumptions: d.assumptions, model_version: d.model_version,
    inputs: Object.assign({}, d.inputs_digest || {}, { supplied: supplied || {} }),
    result: { per_share: d.dcf.per_share, wacc: d.dcf.wacc.wacc, terminal_share: d.dcf.terminal_share, bear: ((d.scenarios || {}).bear || {}).per_share, bull: ((d.scenarios || {}).bull || {}).per_share } };
}
/** A guest's saved model, as Classic keeps it in optic.dcf.v1.models, newest first, 40 at most. */
export function keepLocalModel(snap, now = new Date()) {
  const s = readStore();
  s.models.unshift(Object.assign({}, snap, { id: `local-${now.getTime()}`, created_at: now.toISOString(), changed: (snap.assumptions || {}).changed || [], snapshot: snap }));
  s.models = s.models.slice(0, MAX_LOCAL_MODELS);
  writeStore(s);
  return s.models[0];
}
const fmtField = (f, v) => (!has(v) ? (f.blank || 'none') : f.unit === '%' ? pct(v, 2) : f.unit === 'x' ? `${num(v, 2)} times` : num(v, f.step === 1 ? 0 : 2));
/** A saved model's assumptions against the ones on screen, field by field; both sides are the server's numbers. */
export function compareModel(m, d) {
  const a = (m.snapshot || {}).assumptions || {}, rows = [];
  FIELDS.forEach((f) => {
    const was = f.wacc ? getPath(a.wacc || {}, f.key.slice(5)) : getPath(a.drivers || {}, f.key), now = fieldValue(d, f, 'current');
    const same = (!has(was) && !has(now)) || (has(was) && has(now) && Math.abs(was - now) < 1e-9);
    if (!same) rows.push({ label: f.label, saved: fmtField(f, was), now: fmtField(f, now) });
  });
  const inp = (m.snapshot || {}).inputs || {}, cur = d.inputs_digest || {}, notes = [];
  if (inp.balance_date && cur.balance_date && inp.balance_date !== cur.balance_date) notes.push(`Newer filings since then: balance sheet ${day(inp.balance_date)} then, ${day(cur.balance_date)} now.`);
  if (has(inp.price) && has(cur.price) && Math.abs(inp.price - cur.price) > 0.005) {
    const same = money(inp.price) === money(cur.price), pr = (v) => (same ? `$${num(v, 2)}` : money(v));   // cents when the two would round alike
    notes.push(`Price ${pr(inp.price)} then, ${pr(cur.price)} now.`);
  }
  return { rows, notes, savedValue: ((m.snapshot || {}).result || {}).per_share, nowValue: (d.dcf || {}).per_share };
}
async function modelById(id) {
  if (String(id).startsWith('local-')) return readStore().models.find((m) => m && m.id === id) || null;
  try { return await api.get(`/api/valuation-models/${encodeURIComponent(id)}`, { ttl: 0, force: true }); } catch (e) { return null; }
}
async function save(n) {
  const d = V.data;
  if (!d || !d.dcf || !d.dcf.available) { V.status = 'Nothing to save: the model has no result.'; paintSaved(); return; }
  const name = ((n.querySelector('[data-dcf-save-name]') || {}).value || '').trim(), snap = snapshotOf(V.sym, d, name, editsFor().base);
  try {
    if (store.signedIn()) await api.post('/api/valuation-models', snap);
    else keepLocalModel(snap);
    V.status = `Saved ${new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}.`;
    const box = n.querySelector('[data-dcf-save-name]'); if (box) box.value = '';
  } catch (err) { V.status = `Not saved: ${err.message && err.kind !== 'server' ? err.message : api.explain(err, 'The save')}`; }
  V.open.saved = true;
  await loadSaved();
  const b = n.querySelector('[data-dcf-save]'); if (b) b.focus({ preventScroll: true });
}
async function replay(id) {
  const m = await modelById(id);
  if (!m) { V.replays[id] = { error: 'That model could not be read.' }; paintSaved(); return; }
  try { V.replays[id] = m.replay || await api.post('/api/valuation-models/replay', m.snapshot); } catch (err) { V.replays[id] = { error: api.explain(err, 'The rerun') }; }
  paintSaved(`[data-dcf-replay="${CSS.escape(id)}"]`);
}
async function compare(id) {
  const m = await modelById(id), d = V.data;
  V.compares[id] = !m || !m.snapshot || !d || !d.available ? { error: 'That model could not be read.' } : compareModel(m, d);
  paintSaved(`[data-dcf-compare="${CSS.escape(id)}"]`);
}
async function useModel(id) {
  const m = await modelById(id);
  if (!m || !m.snapshot) { V.status = 'That model could not be read.'; paintSaved(); return; }
  const a = m.snapshot.assumptions || {};
  V.edits = { drivers: JSON.parse(JSON.stringify(a.drivers || {})), wacc: JSON.parse(JSON.stringify(a.wacc || {})), base: JSON.parse(JSON.stringify(((m.snapshot.inputs || {}).supplied) || {})), equity: {} };
  delete V.edits.drivers._deltas;
  await runNow(); paint();
  V.status = `Using the assumptions of ${m.name ? `"${m.name}"` : 'the model saved'} ${when(m.created_at)}, on today's figures.`; paintSaved();
}
async function remove(id) {
  try {
    if (String(id).startsWith('local-')) { const s = readStore(); s.models = s.models.filter((m) => m && m.id !== id); writeStore(s); }
    else await api.del(`/api/valuation-models/${encodeURIComponent(id)}`);
    V.status = 'Deleted.';
  } catch (err) { V.status = `Not deleted: ${api.explain(err, 'The delete')}`; }
  V.armed = null; delete V.replays[id]; delete V.compares[id];
  await loadSaved();
  const b = V.node && V.node.querySelector('[data-dcf-save]'); if (b) b.focus({ preventScroll: true });
}
function compareHTML(c) {
  if (c.error) return html`<p class="t-muted">${c.error}</p>`;
  return html`<div class="dcf-compare"><p><b>Then ${money(c.savedValue)}, now ${money(c.nowValue)}.</b></p>${c.rows.length ? html`<div class="tscroll"><table class="t"><thead><tr><th class="l">Assumption</th><th>Saved</th><th>Now</th></tr></thead><tbody>${c.rows.map((r) => html`<tr><th scope="row" class="l">${r.label}</th><td>${r.saved}</td><td>${r.now}</td></tr>`)}</tbody></table></div>` : html`<p class="t-muted">Every assumption is the same.</p>`}${c.notes.map((x) => html`<p class="t-muted">${x}</p>`)}</div>`;
}
function savedHTML(d) {
  if (!d || !d.available || !(d.dcf || {}).available) return '';
  const sv = V.saved, ms = (sv && sv.models) || [];
  return fold('saved', `Saved models for ${V.sym}${ms.length ? ` (${ms.length})` : ''}`, html`<div data-dcf-saved>
    <div class="dcf-save-row"><label class="dcf-save-name"><span class="t-label">Name this model (optional)</span><input type="text" data-dcf-save-name maxlength="80" autocomplete="off"></label>
      <button type="button" class="btn btn-primary" data-dcf-save>Save a snapshot</button></div>
    <p class="dcf-status" role="status">${V.status}</p>
    <p class="asof">A snapshot keeps the reported figures, your assumptions and the result together, so it can be rerun exactly later. Saving again makes a new snapshot; an earlier one is never changed. ${store.signedIn() ? 'Saved to your account.' : 'Signed out, so snapshots are kept in this browser.'}</p>
    ${sv && sv.error ? html`<p class="dcf-flag">Saved models could not be loaded: ${sv.error}</p>` : ''}
    ${ms.length ? html`<ul class="dcf-saved">${ms.map((m) => { const rp = V.replays[m.id], cp = V.compares[m.id]; return html`<li>
      <p class="dcf-saved-h"><b>${m.name || 'Unnamed model'}</b> <span class="t-muted">saved ${when(m.created_at)}</span></p>
      <p class="t-muted">${money((m.result || {}).per_share)} a share then; ${day((m.inputs || {}).balance_date)} balance sheet, price ${money((m.inputs || {}).price)}; ${(m.changed || []).length ? `changed: ${m.changed.join(', ')}` : 'on the defaults'}.</p>
      <div class="cluster"><button type="button" class="btn btn-sm btn-quiet" data-dcf-replay="${m.id}">Rerun exactly</button><button type="button" class="btn btn-sm btn-quiet" data-dcf-compare="${m.id}">Compare with now</button><button type="button" class="btn btn-sm btn-quiet" data-dcf-use="${m.id}">Use these assumptions</button>
        ${V.armed === m.id ? html`<button type="button" class="btn btn-sm" data-dcf-del-yes="${m.id}">Delete it</button><button type="button" class="btn btn-sm btn-quiet" data-dcf-del-no>Keep it</button>` : html`<button type="button" class="btn btn-sm btn-quiet" data-dcf-del="${m.id}" aria-label="Delete ${m.name || 'the model'} saved ${when(m.created_at)}">Delete</button>`}</div>
      ${V.armed === m.id ? html`<p class="dcf-flag" role="status">Delete this saved model? This cannot be undone.</p>` : ''}
      ${rp ? html`<p class="${rp.error ? 'dcf-flag' : 't-muted'}" role="status">${rp.error ? rp.error : html`Rerun: ${money(rp.per_share)} ${rp.matches ? 'the same as when saved' : '(differs from the saved result)'}${rp.version_changed ? `; the engine has moved from ${rp.saved_version} to ${rp.engine_version}` : ''}.`}</p>` : ''}
      ${cp ? compareHTML(cp) : ''}</li>`; })}</ul>
      <p class="asof">"Rerun exactly" uses the reported figures stored with the snapshot. "Use these assumptions" applies them to today's figures.</p>` : sv ? html`<p class="t-muted">No saved models for ${V.sym} yet.</p>` : html`<p class="t-muted" role="status">Loading saved models…</p>`}</div>`);
}
/** Only the saved-models fold, so the rest of the section (and a box being typed in) is left alone. */
function paintSaved(focusSel) {
  const n = V.node; if (!n) return;
  const host = n.querySelector('[data-dcf-saved-host]'); if (!host) return;
  const a = document.activeElement, keepName = a && host.contains(a) && a.matches('[data-dcf-save-name]') ? a.value : null;
  draw(host, savedHTML(V.data));
  if (keepName !== null) { const b = host.querySelector('[data-dcf-save-name]'); if (b) { b.value = keepName; b.focus({ preventScroll: true }); } }
  if (focusSel) { const f = host.querySelector(focusSel); if (f) f.focus({ preventScroll: true }); }
}

/* ---------------- the whole ---------------- */
function results(d) {
  const dcf = d.dcf || {}, m = d.market || {}, ri = d.residual_income;
  if (!dcf.available && V.open.methods === undefined) V.open.methods = true;
  const err = V.error ? html`<p class="dcf-flag" role="alert">${V.error} The figures below are from the last assumptions that worked.</p>` : '';
  const noDcf = !dcf.available && (rangeRows(d, { rows: extraRows() }).length || (ri && ri.available))
    ? html`<h3>The methods that fit, side by side</h3>${range(d)}${ri && ri.available && ri.sensitivity ? html`<h3>Sensitivity</h3>${heat(ri.sensitivity, m.price, (k, v) => pct(v, 1))}` : ''}` : '';
  return html`${err}${lede(d)}${confidence(d)}${dcf.available ? tiles(d) : ''}${checks(d)}${noDcf}
    ${dcf.available ? html`<div class="dcf-cols"><div><h3>What moves the value most</h3>${tornado(d)}</div><div><h3>Scenarios and other methods, side by side</h3>${range(d)}</div></div>
      <h3>What today's price implies</h3>${reverse(d)}
      <h3>Sensitivity</h3>${sensitivity(d)}
      ${cases(d)}
      ${fold('forecast', 'The forecast, year by year', forecast(d))}${fold('wacc', 'How the discount rate is built', wacc(d))}
      ${fold('bridge', 'From enterprise value to a value per share', bridge(d))}${fold('statements', 'Linked income statement, balance sheet and cash flow', statements(d))}` : ''}
    ${fold('methods', 'Other valuation methods and when each fits', methodsHTML(d))}
    ${fold('sources', 'Reported history and sources', sources(d))}${fold('formulas', 'Formulas and conventions', formulas())}
    ${asks(d)}`;
}
function bodyHTML() {
  const d = V.data;
  if (!d) return html`<p class="t-muted" role="status">Loading the fair-value model…</p>`;
  if (!d.available) return html`<p class="${d.failed ? 'dcf-flag' : 't-muted'}">${clean(d.reason || 'A model cannot be built for this symbol.')}</p>${d.failed ? html`<button type="button" class="btn btn-sm" data-dcf-retry>Try again</button>` : ''}`;
  const dg = d.inputs_digest || {};
  return html`<div data-dcf-results>${results(d)}</div>${form(d)}${equityForm(d)}<div data-dcf-saved-host>${savedHTML(d)}</div>
    <p class="asof dcf-foot">Model ${d.model_version || ''}, filings retrieved ${day(dg.filings_retrieved)}, balance sheet ${day(dg.balance_date)}, ${priceWhen(d.market || {})}. A model-implied value under stated assumptions. It is not a price target, a forecast Optic stands behind, or a signal to buy or sell.</p>`;
}
/** The whole section: on load, reset and a method change. Focus and the caret are put back. */
function paint() {
  const n = V.node; if (!n) return;
  const box = n.querySelector('.dcf-body'); if (!box) return;
  const a = document.activeElement, inBox = a && box.contains(a), key = inBox && (a.getAttribute('data-dcf-field') ? `[data-dcf-field="${a.getAttribute('data-dcf-field')}"]` : a.getAttribute('data-dcf-ov') ? `[data-dcf-ov="${a.getAttribute('data-dcf-ov')}"][data-year="${a.getAttribute('data-year')}"]` : null);
  const caret = key && typeof a.selectionStart === 'number' ? [a.selectionStart, a.selectionEnd] : null;
  draw(box, bodyHTML());
  if (key) { const again = box.querySelector(key); if (again) { again.focus({ preventScroll: true }); if (caret) try { again.setSelectionRange(caret[0], caret[1]); } catch (e) { /* not a text box */ } } }
}
/** While the reader types, only the results and the form's markers change, so the box being typed in is untouched. */
function paintResults() {
  const n = V.node, d = V.data; if (!n || !d) return;
  const out = n.querySelector('[data-dcf-results]'); if (!out) { paint(); return; }
  const a = document.activeElement, sel = a && out.contains(a) ? (a.matches('[data-dcf-peers]') ? '[data-dcf-peers]' : a.getAttribute('data-dcf-sotp-m') ? `[data-dcf-sotp-m="${CSS.escape(a.getAttribute('data-dcf-sotp-m'))}"]` : null) : null;
  const caret = sel && typeof a.selectionStart === 'number' ? [a.selectionStart, a.selectionEnd] : null;
  draw(out, results(d));
  if (sel) { const again = out.querySelector(sel); if (again) { again.focus({ preventScroll: true }); if (caret) try { again.setSelectionRange(caret[0], caret[1]); } catch (e) { /* not a text box */ } } }
  const st = n.querySelector('[data-dcf-status]'); if (st) draw(st, formStatus(d));
  const changed = new Set((d.assumptions || {}).changed || []);
  n.querySelectorAll('[data-dcf-field]').forEach((el) => {
    const f = fieldOf(el.getAttribute('data-dcf-field')), row = el.closest('.dcf-field'); if (!f || !row) return;
    row.classList.toggle('is-edited', f.model ? ((d[f.model] || {}).edited || []).includes(f.key.split('.')[1]) : changed.has(f.key));
  });
}

function wire(n) {
  n.addEventListener('input', (e) => {
    const t = e.target;
    if (t.matches('[data-dcf-peers]')) { V.peers = t.value; return; }
    if (t.matches('[data-dcf-sotp-m]')) { V.sotpM[t.getAttribute('data-dcf-sotp-m')] = t.value; return; }
    if (t.matches('[data-dcf-field]')) {
      const f = fieldOf(t.getAttribute('data-dcf-field')); if (!f) return;
      const msg = setEdit(editsFor(), f, t.value);
      t.setAttribute('aria-invalid', msg ? 'true' : 'false');
      if (msg) { V.error = msg; paintResults(); return; }
      V.error = ''; schedule();
    } else if (t.matches('[data-dcf-ov]')) {
      const ed = editsFor(), k = t.getAttribute('data-dcf-ov'), y = t.getAttribute('data-year'), raw = String(t.value).trim(), v = Number(raw.replace(/[,%\s]/g, ''));
      ed.drivers.overrides = ed.drivers.overrides || {}; ed.drivers.overrides[k] = ed.drivers.overrides[k] || {};
      if (raw === '') delete ed.drivers.overrides[k][y]; else if (Number.isFinite(v)) ed.drivers.overrides[k][y] = v / 100; else { t.setAttribute('aria-invalid', 'true'); return; }
      if (!Object.keys(ed.drivers.overrides[k]).length) delete ed.drivers.overrides[k];
      if (!Object.keys(ed.drivers.overrides).length) delete ed.drivers.overrides;
      t.setAttribute('aria-invalid', 'false'); schedule();
    }
  });
  n.addEventListener('change', (e) => {
    const t = e.target, ed = editsFor();
    if (t.matches('[data-dcf-select]')) {
      const key = t.getAttribute('data-dcf-select');
      if (key === 'wacc.beta_adjust') ed.wacc.beta_adjust = t.value;
      else if (key === 'convention') ed.drivers.convention = t.value;
      else if (key === 'terminal.method') { ed.drivers.terminal = ed.drivers.terminal || {}; ed.drivers.terminal.method = t.value; }
      runNow().then(() => paint());
    } else if (t.matches('[data-dcf-bridge]')) {
      ed.drivers.bridge_include = ed.drivers.bridge_include || {}; ed.drivers.bridge_include[t.getAttribute('data-dcf-bridge')] = t.checked;
      runNow().then(() => { paintResults(); const again = n.querySelector(`[data-dcf-bridge="${CSS.escape(t.getAttribute('data-dcf-bridge'))}"]`); if (again) again.focus({ preventScroll: true }); });
    }
  });
  // which folds the reader opened stay open across repaints; toggle does not bubble
  n.addEventListener('toggle', (e) => { const t = e.target; if (t.matches && t.matches('details[data-dcf-sec]')) V.open[t.getAttribute('data-dcf-sec')] = t.open; }, true);
  n.addEventListener('click', (e) => {
    const t = (q) => e.target.closest(q);
    let b;
    if ((b = t('[data-dcf-tab]'))) { V.tab = b.dataset.dcfTab; paintResults(); const again = n.querySelector(`[data-dcf-tab="${V.tab}"]`); if (again) again.focus({ preventScroll: true }); return; }
    if (t('[data-dcf-reset]')) { V.edits = blankEdits(); rememberEdits(V.sym, V.edits); V.data = V.defaults || V.data; V.error = ''; paint(); const s = n.querySelector('[data-dcf-status]'); if (s) { s.tabIndex = -1; s.focus({ preventScroll: true }); } return; }
    if (t('[data-dcf-retry]')) { load(true); return; }
    if (t('[data-dcf-save]')) { save(n); return; }
    if (t('[data-dcf-comps]')) { loadComps(); return; }
    if (t('[data-dcf-sotp]')) { loadSotp(false); return; }
    if (t('[data-dcf-sotp-run]')) { loadSotp(true); return; }
    if ((b = t('[data-dcf-replay]'))) { replay(b.dataset.dcfReplay); return; }
    if ((b = t('[data-dcf-compare]'))) { compare(b.dataset.dcfCompare); return; }
    if ((b = t('[data-dcf-use]'))) { useModel(b.dataset.dcfUse); return; }
    if ((b = t('[data-dcf-del]'))) { V.armed = b.dataset.dcfDel; paintSaved(`[data-dcf-del-yes="${CSS.escape(V.armed)}"]`); return; }
    if (t('[data-dcf-del-no]')) { const id = V.armed; V.armed = null; paintSaved(id ? `[data-dcf-del="${CSS.escape(id)}"]` : null); return; }
    if ((b = t('[data-dcf-del-yes]'))) { remove(b.dataset.dcfDelYes); return; }
    if ((b = t('[data-dcf-suggest]'))) { const box = n.querySelector(`[data-dcf-base="${CSS.escape(b.dataset.dcfSuggest)}"]`); if (box) { box.value = b.dataset.value; box.focus(); } return; }
    if (t('[data-dcf-base-run]')) {
      const ed = editsFor(); ed.base = {}; let bad = '';
      n.querySelectorAll('[data-dcf-base]').forEach((el) => { if (!el.value.trim()) return; const v = parseAmount(el.value); if (v === null) bad = `${el.value} is not an amount.`; else ed.base[el.getAttribute('data-dcf-base')] = v; });
      if (bad) { V.error = bad; paint(); return; }
      runNow().then(() => paint());
    }
  });
  // Chrome sends no blur when the page's redraw takes a focused box out of the document; where it was is kept here
  const caret = (e) => { const x = e.target; if (x && 'selectionStart' in x && V.focus === x) try { V.sel = [x.selectionStart, x.selectionEnd]; } catch (err) { V.sel = null; } };
  n.addEventListener('focusin', (e) => { V.focus = e.target; V.sel = null; caret(e); });
  n.addEventListener('focusout', () => setTimeout(() => { if (n.isConnected && !n.contains(document.activeElement)) { V.focus = null; V.sel = null; } }, 0));
  ['keyup', 'mouseup', 'select', 'input'].forEach((k) => n.addEventListener(k, caret));
}

/** Put the section (one node for the visit) where Investing left its slot. */
export function mountDcf(root, sym) {
  const slot = root.querySelector('[data-dcf-slot]');
  if (V.sym !== sym || !V.node) {
    clearTimeout(V.timer);
    Object.assign(V, { sym, data: null, defaults: null, edits: null, loading: false, error: '', open: {}, tab: 'wacc_growth', focus: null, sel: null, extra: {}, saved: null, status: '', replays: {}, compares: {}, armed: null, comps: null, sotp: null, peers: '', sotpM: {} });
    const n = document.createElement('section');
    n.className = 'section dcf'; n.id = 'dcf'; n.setAttribute('aria-labelledby', 'dcf-h');
    n.innerHTML = '<div class="section-head"><div><h2 class="t-h2" id="dcf-h">Fair-value model, discounted cash flow</h2></div></div><div class="dcf-body"></div>';
    V.node = n; wire(n); paint(); load(false);
    registerValuation(VAL_API);
  }
  if (!slot) { if (V.node.isConnected) V.node.remove(); return; }
  if (slot !== V.node) {
    slot.replaceWith(V.node);
    const a = document.activeElement, f = V.focus;
    if (f && V.node.contains(f) && (!a || a === document.body)) { f.focus({ preventScroll: true }); if (V.sel) try { f.setSelectionRange(V.sel[0], V.sel[1]); } catch (e) { /* not a text box */ } }
  }
}
export function disposeDcf() { clearTimeout(V.timer); unregisterValuation(VAL_API); V.sym = null; V.node = null; }
/** Milo's proposal applied to a copy of the edits (Classic's miloCardPress), as the model takes it. */
export function withChanges(edits, changes) {
  const e = JSON.parse(JSON.stringify(edits || blankEdits()));
  ['drivers', 'wacc', 'base', 'equity'].forEach((k) => { e[k] = e[k] || {}; });
  (changes || []).forEach((c) => {
    const f = fieldOf(c.key); if (!f || f.model) return;
    if (f.wacc) e.wacc[c.key.slice(5)] = c.value;
    else { const [head, tail] = c.key.split('.'); if (tail) { e.drivers[head] = e.drivers[head] || {}; e.drivers[head][tail] = c.value; } else e.drivers[head] = c.value; }
  });
  return e;
}
/** The proposal card's three presses, registered with Milo while this model is on screen. */
const VAL_API = {
  ready: () => !!(V.node && V.data && V.data.dcf && V.data.dcf.available),
  sym: () => V.sym,
  async preview(changes) {
    const cur = V.data, res = await runNow(withChanges(editsFor(), changes));
    const before = cur.dcf.per_share, after = res && res.dcf && res.dcf.available ? res.dcf.per_share : null;
    if (after === null) return { ok: false, text: `The model cannot run with this change: ${clean(((res || {}).dcf || {}).reason || '')}` };
    return { ok: true, text: `Base value ${money(before)} to ${money(after)} (${signedPct(after / before - 1, 1)}); terminal share ${pct(cur.dcf.terminal_share, 0)} to ${pct(res.dcf.terminal_share, 0)}. Computed by Optic's engine.` };
  },
  async apply(changes) { const prev = JSON.parse(JSON.stringify(editsFor())); V.edits = withChanges(prev, changes); await runNow(); paint(); return prev; },
  async undo(prev) { V.edits = prev ? Object.assign(blankEdits(), prev) : blankEdits(); await runNow(); paint(); },
};

/** What Milo is told about the model on screen (Classic's context): the inputs with their kinds and sources, the
 *  result, what moves it, what the price implies and the checks. Only the server's numbers; nothing recomputed. */
export const dcfContext = () => contextOf(V.data, V.sym, V.comps, V.sotp);
export function contextOf(d, sym, comps, sotp) {
  if (!d) return null;
  if (!d.available) return d.reason ? { ticker: sym, available: false, reason: d.reason } : null;
  const dcf = d.dcf || {}, r4 = (x) => (has(x) ? Math.round(x * 10000) / 10000 : x), r2 = (x) => (has(x) ? Math.round(x * 100) / 100 : x);
  const why = {}; ((d.defaults || {}).rationale || []).forEach((r) => { why[r.key] = r; });
  const changed = new Set((d.assumptions || {}).changed || []);
  const assumptions = FIELDS.map((f) => {
    const v = fieldValue(d, f, 'current'), def = fieldValue(d, f, 'default'), w = f.why ? why[f.why] : null;
    return { key: f.key, label: f.label, value: f.unit === '%' ? r4(v) : r2(v), default: f.unit === '%' ? r4(def) : r2(def), unit: f.unit === '%' ? 'fraction' : f.unit, kind: w ? w.kind : (f.wacc ? 'assumption' : null), why: w ? w.why : null, edited_by_reader: changed.has(f.key) };
  }).filter((a) => has(a.value) || has(a.default));
  const cls = d.classification || {}, m = d.market || {};
  const out = { what: 'Optic fair-value model on the Investing tab. Deterministic: computed by Optic’s engine, not by Milo.', model_version: d.model_version, ticker: d.ticker, name: d.name,
    price: m.price, price_as_of: m.as_of, inputs_as_of: d.inputs_digest,
    classification: { type: cls.label, confidence: cls.confidence, reasons: cls.confidence_reasons, models: Object.fromEntries(Object.entries(cls.models || {}).map(([k, v]) => [k, { fit: v.fit, why: v.why }])) },
    assumptions, warnings: d.warnings };
  if (dcf.available) {
    const w = dcf.wacc || {}, tv = dcf.terminal || {}, rows = dcf.rows || [];
    out.base_case = { value_per_share: r2(dcf.per_share), enterprise_value: dcf.enterprise_value, equity_value: dcf.equity_value, upside_vs_price: r4(dcf.upside), margin_of_safety: r4(dcf.margin_of_safety),
      price_vs_value: has(dcf.per_share) && dcf.per_share > 0 && has(m.price) ? r4(m.price / dcf.per_share - 1) : null, terminal_value_share_of_ev: r4(dcf.terminal_share), pv_forecast_years: dcf.pv_forecast, pv_terminal: tv.pv,
      incremental_return_on_forecast_investment: r4(dcf.incremental_return), terminal: { method: tv.method, growth: r4(tv.growth), ronic: r4(tv.ronic), implied_exit_ev_ebitda: r2(tv.implied_exit_ev_ebitda) },
      exit_multiple_check: dcf.exit_check ? { multiple: r2(dcf.exit_check.multiple), value_per_share: r2(dcf.exit_check.per_share), implied_perpetual_growth: r4(dcf.exit_check.implied_growth) } : null,
      discount_rate: { wacc: r4(w.wacc), cost_equity: r4(w.cost_equity), risk_free: r4(w.risk_free), beta: r2(w.beta), beta_raw: r2(w.beta_raw), erp: r4(w.erp), pre_tax_cost_debt: r4(w.pre_tax_cost_debt), weight_debt: r4(w.weight_debt) },
      checks: dcf.checks };
    out.forecast = rows.filter((x, i) => i < 3 || i === rows.length - 1).map((y) => ({ fiscal_year_end: y.fiscal_year_end, revenue: y.revenue, growth: r4(y.revenue_growth), ebit_margin: r4(y.ebit_margin), capex: y.capex, da: y.da, fcff: y.fcff, roic: r4(y.roic) }));
    out.bridge = (dcf.bridge || {}).lines;
    out.shares = { diluted: dcf.shares, method: ((d.inputs || {}).shares || {}).method };
    out.scenarios = Object.fromEntries(Object.entries(d.scenarios || {}).map(([k, v]) => [k, { value_per_share: r2(v.per_share), upside_vs_price: r4(v.upside), deltas_from_base: v.deltas, growth_y1: r4(((v.drivers || {}).growth || {}).y1), margin_target: r4(((v.drivers || {}).margin || {}).target), capex_target: r4(((v.drivers || {}).capex_pct || {}).target) }]));
    out.most_sensitive = (d.tornado || []).slice(0, 6).map((b) => ({ assumption: b.label, step_down: b.step_low, value_down: r2(b.value_low), step_up: b.step_high, value_up: r2(b.value_high) }));
    out.what_ifs = (d.what_ifs || []).map((x) => ({ change: x.label, value_per_share: r2(x.per_share), vs_base: r4(x.change) }));
    out.reverse_dcf = ((d.reverse || {}).solves || []).map((x) => ({ solved_for: x.label, value: r4(x.value), text: x.text, held_fixed: x.held }));
  } else out.dcf_not_run = dcf.reason;
  ['fcfe', 'ddm', 'residual_income'].forEach((k) => { const x = d[k]; if (x) out[k] = x.available ? { value_per_share: r2(x.per_share), fit: (x.fit || {}).fit } : { available: false, reason: x.reason }; });
  if (d.reit) out.reit = d.reit.available ? { ffo_per_share: r2(d.reit.ffo_per_share), price_to_ffo: r2(d.reit.price_to_ffo), ffo_payout: r4(d.reit.ffo_payout), own_history: d.reit.own_history } : { available: false, reason: d.reit.reason };
  if (d.residual_income && d.residual_income.available) Object.assign(out.residual_income, { implied_roe: r4(d.residual_income.implied_roe), roe_start: r4(d.residual_income.roe_start), price_to_book: r2(d.residual_income.price_to_book) });
  const tt = (d.inputs || {}).trailing || {};
  if (tt.available) out.trailing_twelve_months = { period_end: tt.period_end, revenue: ((tt.values || {}).revenue || {}).value, revenue_change_vs_fiscal_year: r4(tt.revenue_change_vs_fy0), operating_margin: r4(tt.ebit_margin), how: 'fiscal year + this year to date - same months a year earlier, from the filings' };
  out.history = ((d.inputs || {}).history || []).slice(0, 3).map((y) => ({ fiscal_year_end: y.fy_end, revenue_growth: r4((y.derived || {}).revenue_growth), operating_margin: r4((y.derived || {}).ebit_margin), operating_margin_excluding_tagged_charges: r4((y.derived || {}).ebit_margin_normalized), capex_share: r4((y.derived || {}).capex_pct), roic: r4((y.derived || {}).roic), acquisitions_share: r4((y.derived || {}).acquisitions_pct) }));
  out.sources = `Statements: SEC EDGAR XBRL (us-gaap), fiscal years ${((d.inputs || {}).fy_ends || []).slice(0, 3).join(', ')}; balance sheet ${(d.inputs || {}).balance_date || ''}. Price and beta: Yahoo Finance quote. Risk-free: FRED DGS10. ERP and credit spreads: Damodaran, January 2026.`;
  if (comps && comps.available) out.peers = { implied: (comps.implied || []).map((i) => ({ multiple: i.label, own: r2(i.own_multiple), implied_per_share: i.implied ? { low: r2(i.implied.low.per_share), mid: r2(i.implied.mid.per_share), high: r2(i.implied.high.per_share) } : null })), peers: (comps.peers || []).map((x) => x.symbol) };
  if (sotp && sotp.available) out.sum_of_the_parts = { value_per_share: r2(sotp.per_share), segments: (sotp.segments || []).map((g) => ({ name: g.name, operating_income: g.operating_income, multiple: r2(g.multiple), value: g.value })) };
  return out;
}
export const dcfData = () => V.data;
