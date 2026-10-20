// Valuation scenarios: Bear, Base and Bull, each the reader's own inputs over
// reported starting figures (/api/valuation-inputs). The arithmetic and the
// stored shape are the classic app's (valuationScenario, valuationSave):
//   revenue N = revenue x (1 + growth)^N; net income = revenue N x margin;
//   shares N = shares x (1 + share change)^N; EPS = net income / shares N;
//   price N = EPS x exit P/E; value today = price N / (1 + required)^N.
// Signed in, saved to /api/valuations/{SYM}; signed out, to optic.valuation.v1.
// The body is the classic app's valuationBodyOf exactly (v: 1, blank boxes as
// null, notes as '', the reader's own revenue and share count in shared), so a
// save in either app keeps everything the other wrote.
import { html } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, signed, money, compact, isNum, ago, dir } from '../core/format.js';

const KEY = 'optic.valuation.v1';
export const CASES = [['bear', 'Bear'], ['base', 'Base'], ['bull', 'Bull']];
export const FIELDS = [['growth', 'Revenue growth', '% a year', -95, 500], ['margin', 'Net margin', '%', -500, 100], ['share_change', 'Share count change', '% a year', -50, 100], ['pe', 'Exit P/E', 'times earnings', 0.1, 1000]];
const SHARED = [['years', 'Years ahead', 'years', 1, 15, '5'], ['required_return', 'Required return', '% a year', 0, 50, '10']];
// the classic app's VALUATION_OVERRIDES: the reader's own starting figures
const OWN = [['revenue', 'Your own revenue (optional)', 'replaces the reported figure; 394B, 2.5T', 1, 1e14], ['shares', 'Your own share count (optional)', 'replaces the reported figure; 15.2B', 1, 1e13]];

const n = (v) => { const t = String(v ?? '').trim().replace(/,/g, '').replace(/[%x×]$/i, ''); if (!t) return null; const x = Number(t); return Number.isFinite(x) ? x : NaN; };
// '394B' as 394e9, like the classic app's valuationAmount; null when blank, NaN when unreadable
export const amount = (v) => { const t = String(v ?? '').trim().replace(/[,$\s]/g, ''); if (!t) return null; const m = /^(-?\d+(?:\.\d+)?)([kmbt]?)$/i.exec(t); return m ? Number(m[1]) * { '': 1, k: 1e3, m: 1e6, b: 1e9, t: 1e12 }[m[2].toLowerCase()] : NaN; };
// blank boxes, as the classic app starts; the years and return are placeholders, not saved values
export const emptyBody = () => ({ v: 1, shared: { years: null, required_return: null, revenue: null, shares: null }, bear: { note: '' }, base: { note: '' }, bull: { note: '' }, from_history: [] });
// the classic app's valuationIsEmpty: nothing in any box and no note
export const isEmpty = (b) => Object.values(b.shared || {}).every((v) => v === null || v === undefined)
  && CASES.every(([c]) => !((b[c] || {}).note) && FIELDS.every(([k]) => { const v = (b[c] || {})[k]; return v === null || v === undefined; }));

function local() { if (!holds(store.state.user)) return {}; try { const r = JSON.parse(localStorage.getItem(KEY) || '{}'); return r && typeof r === 'object' ? r : {}; } catch (e) { return {}; } }

export async function load(sym) {
  if (store.signedIn()) {
    try { const r = await api.get('/api/valuations', { ttl: 0, force: true }); return (r.valuations || {})[sym] || null; } catch (e) { return local()[sym] || null; }
  }
  return local()[sym] || null;
}

export function work(start, c, shared) {
  const missing = FIELDS.filter(([k]) => !isNum(c[k])).map(([, l]) => l.toLowerCase());
  if (!shared.years) missing.push('years ahead');
  if (!(start.revenue > 0)) missing.push('a revenue figure');
  if (missing.length) return { ok: false, missing };
  const N = shared.years;
  const revenue = start.revenue * (1 + c.growth / 100) ** N;
  const income = revenue * (c.margin / 100);
  const shares = start.shares * (1 + c.share_change / 100) ** N;
  const eps = income / shares;
  if (!(eps > 0)) return { ok: true, revenue, income, shares, eps, loss: true };
  const price = eps * c.pe;
  const today = price / (1 + (shared.required_return || 0) / 100) ** N;
  const cagr = start.price > 0 ? ((price / start.price) ** (1 / N) - 1) * 100 : null;
  return { ok: true, revenue, income, shares, eps, price, today, vs: start.price > 0 ? (today / start.price - 1) * 100 : null, cagr };
}

export function errors(body) {
  const out = {};
  SHARED.forEach(([k, , , lo, hi]) => { const v = body.shared[k]; if (v !== null && v !== undefined && (Number.isNaN(v) || v < lo || v > hi)) out[`shared.${k}`] = `Between ${lo} and ${hi}`; });
  OWN.forEach(([k]) => { const v = body.shared[k]; if (v !== null && v !== undefined && (Number.isNaN(v) || v < 1)) out[`shared.${k}`] = 'A positive amount, like 394B'; });
  CASES.forEach(([c]) => FIELDS.forEach(([k, , , lo, hi]) => { const v = (body[c] || {})[k]; if (v !== null && v !== undefined && (Number.isNaN(v) || v < lo || v > hi)) out[`${c}.${k}`] = `Between ${lo} and ${hi}`; }));
  return out;
}

export async function save(sym, body) {
  const empty = isEmpty(body);
  if (store.signedIn()) {
    try {
      if (empty) { await api.del(`/api/valuations/${encodeURIComponent(sym)}`).catch(() => {}); store.forgetLocalCopy(KEY, sym); }
      else await api.put(`/api/valuations/${encodeURIComponent(sym)}`, body);
      return empty ? 'Cleared.' : 'Saved to your account just now.';
    } catch (e) { return `Not saved to your account (${e.message}).`; }
  }
  if (!holds(store.state.user)) return 'Not saved: this browser is holding another account\'s things.';
  try {
    const all = local();
    if (empty) delete all[sym]; else all[sym] = Object.assign({}, body, { saved_at: new Date().toISOString() });
    localStorage.setItem(KEY, JSON.stringify(all));
    return empty ? 'Cleared.' : 'Saved in this browser just now.';
  } catch (e) { return 'Not saved: this browser refused the write.'; }
}

/** The boxes as the stored body. `prev` is what the boxes were filled from:
 *  a box still showing a figure filled from history keeps its tag; one the
 *  reader has changed is theirs (the classic app drops the tag on typing). */
export function readForm(form, prev) {
  const body = emptyBody();
  SHARED.forEach(([k]) => { body.shared[k] = n(form[`shared.${k}`].value); });
  OWN.forEach(([k]) => { body.shared[k] = amount(form[`shared.${k}`].value); });
  CASES.forEach(([c]) => { FIELDS.forEach(([k]) => { body[c][k] = n(form[`${c}.${k}`].value); }); body[c].note = String(form[`${c}.note`].value || '').slice(0, 1000); });
  const at = (b, key) => { const [scope, k] = key.split('.'); return ((b || {})[scope] || {})[k]; };
  body.from_history = ((prev || {}).from_history || []).filter((key) => at(body, key) !== null && at(body, key) === at(prev, key));
  return body;
}

/** Where the cases start: the reader's own figure where they gave one, else the reported one. */
export const startOf = (inputs, body) => {
  const inp = (inputs || {}).inputs || {}, own = ((body || {}).shared) || {};
  return { revenue: own.revenue > 0 ? own.revenue : (inp.revenue || {}).value, shares: own.shares > 0 ? own.shares : (inp.shares || {}).value, price: (inp.price || {}).value, ownRevenue: own.revenue > 0, ownShares: own.shares > 0 };
};
export function caseOut(start, c, shared) {
  const r = work(start, c || {}, shared);
  return !r.ok ? html`<p class="t-muted">Needs ${r.missing.join(', ')}.</p>` : r.loss ? html`<p>A loss in year ${shared.years}: no earnings multiple to apply.</p>`
    : html`<dl class="kv" style="--kv:2"><div><dt>EPS in year ${shared.years}</dt><dd>${num(r.eps)}</dd></div><div><dt>Price then</dt><dd>${money(r.price)}</dd></div><div><dt>Value today</dt><dd>${money(r.today)}</dd></div><div><dt>Against today's price</dt><dd class="${dir(r.vs)}">${signed(r.vs, 0)}</dd></div></dl><p class="asof">Price-only rate ${signed(r.cagr, 1)} a year; dividends are not in it.</p>`;
}

export function view(sym, inputs, body, status) {
  const inp = (inputs || {}).inputs || {}, hist = (inputs || {}).history || {};
  const b = body || emptyBody();
  const start = startOf(inputs, b);
  const errs = errors(b);
  const tagged = (name) => (b.from_history || []).includes(name);
  const field = (name, label, unit, value, hint) => html`<label class="vs-f ${errs[name] ? 'bad' : ''}"><span class="t-label">${label}</span><span class="field field-sm"><input name="${name}" inputmode="decimal" value="${value ?? ''}" placeholder="${hint || ''}" aria-describedby="${name}-u"><small id="${name}-u" class="t-muted">${errs[name] || (tagged(name) ? `${unit}, from history` : unit)}</small></span></label>`;
  return html`<form class="vs" data-v2-vs>
    <p class="section-sub">Starting from ${start.ownRevenue ? 'your own revenue' : 'reported revenue'} ${compact(start.revenue)}${start.ownRevenue ? '' : ` (${(inp.revenue || {}).source || 'filings'})`}, ${compact(start.shares)} shares${start.ownShares ? ' (your figure)' : ''}, price ${num(start.price)}. Every assumption below is yours.</p>
    <div class="cluster">${SHARED.map(([k, l, u, , , hint]) => field(`shared.${k}`, l, u, b.shared[k], hint))}</div>
    <details class="vs-own" ${start.ownRevenue || start.ownShares ? 'open' : ''}><summary>Your own starting figures</summary><div class="cluster">${OWN.map(([k, l, u]) => field(`shared.${k}`, l, u, b.shared[k]))}</div></details>
    <div class="vs-cases">${CASES.map(([c, label]) => { return html`<fieldset class="vs-case"><legend>${label}</legend>
      ${FIELDS.map(([k, l, u]) => field(`${c}.${k}`, l, u, (b[c] || {})[k]))}
      <label class="vs-f"><span class="t-label">Note</span><span class="field field-sm"><input name="${c}.note" value="${(b[c] || {}).note || ''}" maxlength="1000"></span></label>
      <div class="vs-out" data-v2-vs-out="${c}" aria-live="polite">${caseOut(start, b[c] || {}, b.shared)}</div>
    </fieldset>`; })}</div>
    <div class="cluster"><button type="button" class="btn btn-sm" data-v2-vs-fill ${isNum((hist.revenue_growth || {}).value) ? '' : 'disabled'}>Fill the base case from history</button><button type="submit" class="btn btn-primary btn-sm">Save</button><span class="asof vs-status" role="status">${status || ((body || {}).saved_at ? `Saved ${ago(body.saved_at)}.` : '')}</span></div>
    <p class="asof">History: revenue growth ${signed((hist.revenue_growth || {}).value, 1)} a year, net margin ${num((hist.margin || {}).value, 1)}%, share count ${signed((hist.share_change || {}).value, 1)} a year. A figure filled from history is the company's past, not a forecast.</p>
  </form>`;
}
