// Valuation scenarios: Bear, Base and Bull, each the reader's own inputs over
// reported starting figures (/api/valuation-inputs). The arithmetic and the
// stored shape are the classic app's (valuationScenario, valuationSave):
//   revenue N = revenue x (1 + growth)^N; net income = revenue N x margin;
//   shares N = shares x (1 + share change)^N; EPS = net income / shares N;
//   price N = EPS x exit P/E; value today = price N / (1 + required)^N.
// Signed in, saved to /api/valuations/{SYM}; signed out, to optic.valuation.v1.
import { html } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, signed, money, compact, isNum, ago } from '../core/format.js';

const KEY = 'optic.valuation.v1';
export const CASES = [['bear', 'Bear'], ['base', 'Base'], ['bull', 'Bull']];
export const FIELDS = [['growth', 'Revenue growth', '% a year', -95, 500], ['margin', 'Net margin', '%', -500, 100], ['share_change', 'Share count change', '% a year', -50, 100], ['pe', 'Exit P/E', 'times earnings', 0.1, 1000]];
const SHARED = [['years', 'Years ahead', 'years', 1, 15], ['required_return', 'Required return', '% a year', 0, 50]];

const n = (v) => { const t = String(v ?? '').trim().replace(/,/g, '').replace(/[%x×]$/i, ''); if (!t) return null; const x = Number(t); return Number.isFinite(x) ? x : NaN; };
export const emptyBody = () => ({ shared: { years: 5, required_return: 10, revenue: null, shares: null }, bear: {}, base: {}, bull: {}, from_history: [] });

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
  CASES.forEach(([c]) => FIELDS.forEach(([k, , , lo, hi]) => { const v = (body[c] || {})[k]; if (v !== null && v !== undefined && (Number.isNaN(v) || v < lo || v > hi)) out[`${c}.${k}`] = `Between ${lo} and ${hi}`; }));
  return out;
}

export async function save(sym, body) {
  const empty = CASES.every(([c]) => FIELDS.every(([k]) => !isNum((body[c] || {})[k])));
  if (store.signedIn()) {
    try {
      if (empty) await api.del(`/api/valuations/${encodeURIComponent(sym)}`).catch(() => {});
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

export function readForm(form) {
  const body = emptyBody();
  SHARED.forEach(([k]) => { body.shared[k] = n(form[`shared.${k}`].value); });
  CASES.forEach(([c]) => { FIELDS.forEach(([k]) => { body[c][k] = n(form[`${c}.${k}`].value); }); body[c].note = String(form[`${c}.note`].value || '').slice(0, 1000) || null; });
  return body;
}

export const startOf = (inputs) => { const inp = (inputs || {}).inputs || {}; return { revenue: (inp.revenue || {}).value, shares: (inp.shares || {}).value, price: (inp.price || {}).value }; };
export function caseOut(start, c, shared) {
  const r = work(start, c || {}, shared);
  return !r.ok ? html`<p class="t-muted">Needs ${r.missing.join(', ')}.</p>` : r.loss ? html`<p>A loss in year ${shared.years}: no earnings multiple to apply.</p>`
    : html`<dl class="kv" style="--kv:2"><div><dt>EPS in year ${shared.years}</dt><dd>${num(r.eps)}</dd></div><div><dt>Price then</dt><dd>${money(r.price)}</dd></div><div><dt>Value today</dt><dd>${money(r.today)}</dd></div><div><dt>Against today's price</dt><dd class="${r.vs >= 0 ? 'up' : 'down'}">${signed(r.vs, 0)}</dd></div></dl><p class="asof">Price-only rate ${signed(r.cagr, 1)} a year; dividends are not in it.</p>`;
}

export function view(sym, inputs, body, status) {
  const inp = (inputs || {}).inputs || {}, hist = (inputs || {}).history || {};
  const start = { revenue: (inp.revenue || {}).value, shares: (inp.shares || {}).value, price: (inp.price || {}).value };
  const b = body || emptyBody();
  const errs = errors(b);
  const field = (name, label, unit, value) => html`<label class="vs-f ${errs[name] ? 'bad' : ''}"><span class="t-label">${label}</span><span class="field field-sm"><input name="${name}" inputmode="decimal" value="${value ?? ''}" aria-describedby="${name}-u"><small id="${name}-u" class="t-muted">${errs[name] || unit}</small></span></label>`;
  return html`<form class="vs" data-v2-vs>
    <p class="section-sub">Starting from reported figures: revenue ${compact(start.revenue)} (${(inp.revenue || {}).source || 'filings'}), ${compact(start.shares)} shares, price ${num(start.price)}. Every assumption below is yours.</p>
    <div class="cluster">${SHARED.map(([k, l, u]) => field(`shared.${k}`, l, u, b.shared[k]))}</div>
    <div class="vs-cases">${CASES.map(([c, label]) => { return html`<fieldset class="vs-case"><legend>${label}</legend>
      ${FIELDS.map(([k, l, u]) => field(`${c}.${k}`, l, u, (b[c] || {})[k]))}
      <label class="vs-f"><span class="t-label">Note</span><span class="field field-sm"><input name="${c}.note" value="${(b[c] || {}).note || ''}" maxlength="1000"></span></label>
      <div class="vs-out" data-v2-vs-out="${c}" aria-live="polite">${caseOut(start, b[c] || {}, b.shared)}</div>
    </fieldset>`; })}</div>
    <div class="cluster"><button type="button" class="btn btn-sm" data-v2-vs-fill ${isNum((hist.revenue_growth || {}).value) ? '' : 'disabled'}>Fill the base case from history</button><button type="submit" class="btn btn-primary btn-sm">Save</button><span class="asof vs-status" role="status">${status || ((body || {}).saved_at ? `Saved ${ago(body.saved_at)}.` : '')}</span></div>
    <p class="asof">History: revenue growth ${signed((hist.revenue_growth || {}).value, 1)} a year, net margin ${num((hist.margin || {}).value, 1)}%, share count ${signed((hist.share_change || {}).value, 1)} a year. A figure filled from history is the company's past, not a forecast.</p>
  </form>`;
}
