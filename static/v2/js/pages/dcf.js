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
import { button as miloButton } from '../ui/milo.js';

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

/* ---------------- the form's fields: Classic's, word for word ---------------- */
export const FIELDS = [
  { group: 'Growth', key: 'growth.y1', label: 'Revenue growth, first year', unit: '%', why: 'growth.y1' },
  { group: 'Growth', key: 'growth.y2', label: 'Revenue growth, second year', unit: '%', why: 'growth.y2', blank: 'fades from year 1' },
  { group: 'Growth', key: 'growth.fade_years', label: 'Years for growth to fade to the long run', unit: 'yrs', step: 1, why: 'growth.fade_years', blank: 'the whole forecast' },
  { group: 'Growth', key: 'terminal.growth', label: 'Growth after the forecast, forever', unit: '%', why: 'terminal.growth' },
  { group: 'Growth', key: 'horizon', label: 'Forecast years', unit: 'yrs', step: 1 },
  { group: 'Profitability', key: 'margin.start', label: 'Operating margin, first year', unit: '%', why: 'margin.start' },
  { group: 'Profitability', key: 'margin.target', label: 'Operating margin it settles at', unit: '%', why: 'margin.target' },
  { group: 'Profitability', key: 'margin.years', label: 'Years to get there', unit: 'yrs', step: 1 },
  { group: 'Reinvestment', key: 'capex_pct.start', label: 'Capex, first year (share of revenue)', unit: '%', why: 'capex.start' },
  { group: 'Reinvestment', key: 'capex_pct.target', label: 'Capex it settles at', unit: '%', why: 'capex.target' },
  { group: 'Reinvestment', key: 'capex_pct.years', label: 'Years to get there', unit: 'yrs', step: 1 },
  { group: 'Reinvestment', key: 'dep_rate', label: 'Depreciation (share of last year’s net PP&E)', unit: '%', why: 'dep_rate' },
  { group: 'Reinvestment', key: 'nwc_pct', label: 'Working capital (share of revenue)', unit: '%', why: 'nwc_pct' },
  { group: 'Reinvestment', key: 'terminal.ronic', label: 'Return on new capital after the forecast', unit: '%', why: 'terminal.ronic' },
  { group: 'Taxes', key: 'tax.start', label: 'Tax rate on operating profit, first year', unit: '%', why: 'tax.start' },
  { group: 'Taxes', key: 'tax.terminal', label: 'Long-run tax rate', unit: '%', why: 'tax.terminal' },
  { group: 'Discount rate', key: 'wacc.risk_free', label: 'Risk-free rate (10-year Treasury)', unit: '%', wacc: true },
  { group: 'Discount rate', key: 'wacc.beta_raw', label: 'Beta (raw, before adjustment)', unit: 'x', wacc: true, step: 0.01 },
  { group: 'Discount rate', key: 'wacc.erp', label: 'Equity risk premium', unit: '%', wacc: true },
  { group: 'Discount rate', key: 'wacc.extra_premium', label: 'Extra premium (size, country, your own)', unit: '%', wacc: true },
  { group: 'Discount rate', key: 'wacc.pre_tax_cost_debt', label: 'Pre-tax cost of debt', unit: '%', wacc: true },
  { group: 'Discount rate', key: 'wacc.marginal_tax', label: 'Tax rate for the interest shield', unit: '%', wacc: true },
  { group: 'Discount rate', key: 'wacc.debt_weight', label: 'Debt weight (blank: today’s market weights)', unit: '%', wacc: true, blank: 'market weights' },
  { group: 'Discount rate', key: 'wacc.override', label: 'Or set the discount rate directly', unit: '%', wacc: true, blank: 'built from the parts above' },
  { group: 'Cross-check', key: 'exit_multiple', label: 'Exit EV/EBITDA (cross-check only)', unit: 'x', why: 'exit_multiple', step: 0.1 },
];
export const GROUPS = ['Growth', 'Profitability', 'Reinvestment', 'Taxes', 'Discount rate', 'Cross-check'];
const getPath = (o, key) => key.split('.').reduce((x, k) => (x && typeof x === 'object' ? x[k] : undefined), o);
export const fieldOf = (key) => FIELDS.find((x) => x.key === key) || null;
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
const V = { sym: null, node: null, data: null, defaults: null, edits: null, loading: false, error: '', seq: 0, timer: null, open: {}, tab: 'wacc_growth', focus: null, sel: null, extra: {}, saved: null, status: '', replays: {}, compares: {}, armed: null };
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
  const m = d.market || {}, rows = rangeRows(d, V.extra);
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
  const err = V.error ? html`<p class="dcf-flag" role="alert">${V.error} The figures below are from the last assumptions that worked.</p>` : '';
  const noDcf = !dcf.available && (rangeRows(d, V.extra).length || (ri && ri.available))
    ? html`<h3>The methods that fit, side by side</h3>${range(d)}${ri && ri.available && ri.sensitivity ? html`<h3>Sensitivity</h3>${heat(ri.sensitivity, m.price, (k, v) => pct(v, 1))}` : ''}` : '';
  return html`${err}${lede(d)}${confidence(d)}${dcf.available ? tiles(d) : ''}${checks(d)}${noDcf}
    ${dcf.available ? html`<div class="dcf-cols"><div><h3>What moves the value most</h3>${tornado(d)}</div><div><h3>Scenarios and other methods, side by side</h3>${range(d)}</div></div>
      <h3>What today's price implies</h3>${reverse(d)}
      <h3>Sensitivity</h3>${sensitivity(d)}
      ${cases(d)}
      ${fold('forecast', 'The forecast, year by year', forecast(d))}${fold('wacc', 'How the discount rate is built', wacc(d))}
      ${fold('bridge', 'From enterprise value to a value per share', bridge(d))}${fold('statements', 'Linked income statement, balance sheet and cash flow', statements(d))}` : ''}
    ${(V.extraFolds || []).map((x) => x(d))}
    ${fold('sources', 'Reported history and sources', sources(d))}${fold('formulas', 'Formulas and conventions', formulas())}
    ${asks(d)}`;
}
function bodyHTML() {
  const d = V.data;
  if (!d) return html`<p class="t-muted" role="status">Loading the fair-value model…</p>`;
  if (!d.available) return html`<p class="${d.failed ? 'dcf-flag' : 't-muted'}">${clean(d.reason || 'A model cannot be built for this symbol.')}</p>${d.failed ? html`<button type="button" class="btn btn-sm" data-dcf-retry>Try again</button>` : ''}`;
  const dg = d.inputs_digest || {};
  return html`<div data-dcf-results>${results(d)}</div>${form(d)}${(V.extraForms || []).map((x) => x(d))}<div data-dcf-saved-host>${savedHTML(d)}</div>
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
  draw(out, results(d));
  const st = n.querySelector('[data-dcf-status]'); if (st) draw(st, formStatus(d));
  const changed = new Set((d.assumptions || {}).changed || []);
  n.querySelectorAll('[data-dcf-field]').forEach((el) => { const row = el.closest('.dcf-field'); if (row) row.classList.toggle('is-edited', changed.has(el.getAttribute('data-dcf-field'))); });
}

function wire(n) {
  n.addEventListener('input', (e) => {
    const t = e.target;
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
    Object.assign(V, { sym, data: null, defaults: null, edits: null, loading: false, error: '', open: {}, tab: 'wacc_growth', focus: null, sel: null, extra: {}, saved: null, status: '', replays: {}, compares: {}, armed: null });
    const n = document.createElement('section');
    n.className = 'section dcf'; n.id = 'dcf'; n.setAttribute('aria-labelledby', 'dcf-h');
    n.innerHTML = '<div class="section-head"><div><h2 class="t-h2" id="dcf-h">Fair-value model, discounted cash flow</h2></div></div><div class="dcf-body"></div>';
    V.node = n; wire(n); paint(); load(false);
  }
  if (!slot) { if (V.node.isConnected) V.node.remove(); return; }
  if (slot !== V.node) {
    slot.replaceWith(V.node);
    const a = document.activeElement, f = V.focus;
    if (f && V.node.contains(f) && (!a || a === document.body)) { f.focus({ preventScroll: true }); if (V.sel) try { f.setSelectionRange(V.sel[0], V.sel[1]); } catch (e) { /* not a text box */ } }
  }
}
export function disposeDcf() { clearTimeout(V.timer); V.sym = null; V.node = null; }
/** What Milo is told about the model on screen (B7d gives it the whole model). */
export function dcfContext() {
  const d = V.data;
  if (!d) return null;
  if (!d.available) return { ticker: V.sym, available: false, reason: d.reason };
  return { ticker: V.sym, per_share: (d.dcf || {}).per_share, scenarios: d.scenarios, reverse: d.reverse, changed: (d.assumptions || {}).changed || [] };
}
export const dcfData = () => V.data;
void miloButton;
