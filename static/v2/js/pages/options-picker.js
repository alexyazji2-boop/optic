// Options, Contracts and pricing: the contract picker (roadmap stage 2, 2026-10-22). The reader states a plan
// (which way, how long, the most premium at risk, an optional target and invalidation, whether to hold through
// the next report) and gets up to three contracts that fit it, each with its cost, its expiry against the plan,
// its main risk and why it was chosen, or a plain "none fits" with the reasons. Nothing is sent until "Find
// contracts" is pressed, and the plan is kept in this browser only (optic.v2.picker.v1, a personal key: a
// trading plan goes with the reader, not the device).
import { $, html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, dir, clean, shortDate, isNum, plural } from '../core/format.js';
import { skeleton, empty, failed, how } from '../ui/states.js';

const KEY = 'optic.v2.picker.v1';
const HOLDS = [7, 14, 30, 60];
const usd = (v) => (isNum(v) ? `$${Math.round(Math.abs(v)).toLocaleString('en-US')}` : 'n/a');
const pl = (v) => (isNum(v) ? `${v < 0 ? '−' : '+'}${usd(v)}` : 'n/a');
const readPlan = () => { try { return { thesis: 'bull', hold_days: 30, max_premium: 500, target: '', invalidation: '', through_event: false, ...(JSON.parse(localStorage.getItem(KEY) || 'null') || {}) }; } catch (e) { return { thesis: 'bull', hold_days: 30, max_premium: 500, target: '', invalidation: '', through_event: false }; } };
const savePlan = (p) => { try { localStorage.setItem(KEY, JSON.stringify(p)); } catch (e) { /* private mode */ } };

/** The query the server reads, from the form's plan; blanks are left out, not sent as zero. */
export function pickerQuery(p) {
  const q = new URLSearchParams({ thesis: p.thesis === 'bear' ? 'bear' : 'bull', hold_days: String(Math.max(1, Math.round(Number(p.hold_days) || 30))), max_premium: String(Math.max(1, Number(p.max_premium) || 500)) });
  if (Number(p.target) > 0) q.set('target', String(Number(p.target)));
  if (Number(p.invalidation) > 0) q.set('invalidation', String(Number(p.invalidation)));
  if (p.through_event) q.set('through_event', 'true');
  return q.toString();
}

function form(S) {
  const p = S.plan, nr = S.nextReport;
  return html`<form class="pk-form" data-pk-form novalidate>
    <div class="pk-row"><div class="seg" role="group" aria-label="Your view"><button type="button" data-pk-thesis="bull" aria-pressed="${p.thesis !== 'bear'}">Expect a rise</button><button type="button" data-pk-thesis="bear" aria-pressed="${p.thesis === 'bear'}">Expect a fall</button></div>
      <div class="seg" role="group" aria-label="Holding period">${HOLDS.map((d) => html`<button type="button" data-pk-hold="${d}" aria-pressed="${Number(p.hold_days) === d}">${d} days</button>`)}</div></div>
    <div class="pk-row">
      <label class="pk-in"><span class="t-label">Most premium at risk</span><span class="field pk-field"><span aria-hidden="true">$</span><input name="max_premium" inputmode="decimal" value="${p.max_premium}" aria-label="Most premium at risk, in dollars"></span></label>
      <label class="pk-in"><span class="t-label">Target price <small>optional</small></span><span class="field pk-field"><input name="target" inputmode="decimal" value="${p.target}" placeholder="${S.spot ? num(S.spot * (p.thesis === 'bear' ? 0.93 : 1.07), 0) : ''}" aria-label="Target price for the stock, optional"></span></label>
      <label class="pk-in"><span class="t-label">Invalidation <small>optional</small></span><span class="field pk-field"><input name="invalidation" inputmode="decimal" value="${p.invalidation}" aria-label="Price at which the idea is wrong, optional"></span></label>
    </div>
    <label class="check"><input type="checkbox" name="through_event" ${p.through_event ? 'checked' : ''}> <span>I mean to hold through the next earnings report${nr ? ` (${shortDate(nr)})` : ''}</span></label>
    <div class="cluster"><button type="submit" class="btn btn-primary" ${S.loading ? 'disabled' : ''}>${S.loading ? 'Finding…' : 'Find contracts'}</button></div></form>`;
}

function pickRow(c, i, d) {
  const sc = c.scenarios || {}, liq = c.liquidity || {}, after = c.dte - ((d.plan || {}).hold_days || 0);
  const report = (c.events || []).find((e) => e.kind === 'earnings');
  return html`<li class="pk-pick">
    <div class="pk-h"><h3>${num(c.strike, c.strike % 1 ? 1 : 0)} ${c.type}, ${shortDate(c.expiry)} <small class="t-muted">${plural(c.dte, 'day')} left</small></h3>
      <span class="pk-fit" title="${clean(d.fit_note || '')}">Fit ${num(c.fit.score, 0)} <small>of 100</small></span></div>
    <p class="pk-cost"><b>${usd(c.ask * 100)}</b> for one contract at the ask, which covers 100 shares. <span class="t-muted">Bid ${num(c.bid)}, ask ${num(c.ask)}, mid ${num(c.mid)}: a fill can be worse than the mid.</span></p>
    <p>${clean(c.why.fit)}</p><p class="pk-trade"><b>Main tradeoff.</b> ${clean(c.why.tradeoff)}</p>
    ${report ? html`<p class="stale">${clean(report.text)}</p>` : ''}
    <dl class="kv pk-kv">
      <div><dt>Breakeven at expiry</dt><dd>${num(c.breakeven_ask)}</dd><p class="kv-note">${signed(c.breakeven_move_pct, 1)} from today</p></div>
      <div><dt>Time decay</dt><dd>${usd(c.theta_per_contract)}</dd><p class="kv-note">a day, per contract, today</p></div>
      <div><dt>Implied volatility</dt><dd>${num(c.iv_pct, 1)}%</dd><p class="kv-note">delta ${num(Math.abs(c.delta), 2)}</p></div>
      <div><dt>Spread</dt><dd>${num(c.spread_pct, 1)}%</dd><p class="kv-note">${clean(liq.label || '')} quote</p></div>
      <div><dt>Traded today</dt><dd>${num(c.volume, 0)}</dd><p class="kv-note">contracts so far</p></div>
      <div><dt>Open interest</dt><dd>${num(c.open_interest, 0)}</dd><p class="kv-note">at the last close</p></div>
      <div><dt>Expiry after your exit</dt><dd>${plural(after, 'day')}</dd><p class="kv-note">${shortDate(c.expiry)}</p></div>
    </dl>
    <div class="tscroll"><table class="t pk-sc"><caption class="sr">What one contract would be worth</caption>
      <thead><tr><th scope="col">If</th><th scope="col">Stock</th><th scope="col">Worth at your exit, model</th><th scope="col">Gain or loss</th></tr></thead>
      <tbody>${(sc.before_expiry || []).map((s) => html`<tr><th scope="row">${s.label}<small>${clean(s.why || '')}</small></th><td>${num(s.underlying)}</td><td>${usd(s.value)}</td><td class="${dir(s.pnl)}">${pl(s.pnl)}</td></tr>`)}</tbody></table></div>
    <p class="pk-exp"><b>At expiry</b>, its value is only what it is in the money: ${(sc.at_expiry || []).map((s) => `${s.label.toLowerCase()} (${num(s.underlying)}) ${usd(s.value)}, ${pl(s.pnl)}`).join('; ')}.</p>
    <div class="cluster"><button type="button" class="btn btn-sm" data-pk-practice="${i}">Practice this trade</button><span class="t-muted">Opens the Paper Desk with this contract and your plan filled in. Nothing is bought.</span></div></li>`;
}

function results(S) {
  // a 404 here is the feed listing no expiries (Yahoo refusing requests did this on 2026-10-22), not a missing page
  if (S.error && S.error.kind === 'notfound') return html`<div class="state err" role="alert"><p class="t-h3">No option expiries came back</p><p>${clean(S.error.message || '')} The data feed may be refusing requests for a moment; nothing is wrong with your plan.</p><button type="button" class="btn btn-sm" data-v2-retry="picker">Try again</button></div>`;
  if (S.error) return failed('The contract picker', S.error, { retry: 'picker' });
  if (S.loading) return skeleton('lines', 5, 'Reading the chain for contracts that fit');
  const d = S.data;
  if (!d) return html`<p class="t-muted">Set your plan and press Find contracts. Nothing is checked until you do.</p>`;
  const picks = d.picks || [];
  const meta = html`<p class="asof">${clean(d.quote_note || '')}${d.fetched_at ? ` Read at ${new Date(d.fetched_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}.` : ''} ${plural(d.considered || 0, 'contract')} considered across ${plural((d.expiries || []).length, 'expiry', 'expiries')}.</p>`;
  const method = how(html`<p>${clean(d.rules || '')}</p><p>${clean(d.fit_note || '')}</p><p>${clean(d.model_note || '')}</p><p>${clean(d.fill_note || '')} ${clean(d.oi_note || '')}</p>`);
  if (!picks.length) return html`${d.earnings_note ? html`<p class="stale">${clean(d.earnings_note)}</p>` : ''}${d.conflict ? html`<p class="pk-lead">${clean(d.conflict)}</p>` : ''}${empty('No contract fits this plan', clean(d.why_none || ''))}${meta}${method}`;
  return html`${d.earnings_note ? html`<p class="stale">${clean(d.earnings_note)}</p>` : ''}<p class="pk-lead">${picks.length === 1 ? 'One contract fits' : `${picks.length} contracts fit`} your plan${d.event_in_hold ? `, held through the ${shortDate(d.earnings)} report` : ''}.${picks.length < 3 ? ' Nothing else qualified, so no more are shown.' : ''}</p>
    <ol class="pk-list">${picks.map((c, i) => pickRow(c, i, d))}</ol>${meta}${method}`;
}

/** The draft the Paper Desk reads (pages/paper.js DRAFT_KEY): the pick and the plan that chose it. */
export function draftFrom(d, c, sym) {
  const p = d.plan || {};
  return { ticker: sym, instrument: 'option', direction: 'long', option_type: c.type, expiry: c.expiry, strike: c.strike, qty: 1, entry: c.ask,
    // the Paper Desk prices an option's risk from a premium stop: the model's value of this contract at the plan's
    // exit if the stock reaches the invalidation (or a one-standard-deviation move against it), per share
    stop: premiumStop(c), target: '', hold_days: p.hold_days,
    invalidation: p.invalidation ? `The stock through ${p.invalidation}` : 'A one-standard-deviation move against the view over the hold',
    thesis: `${p.thesis === 'bear' ? 'Expect a fall' : 'Expect a rise'} in ${sym}${p.target ? ` toward ${p.target}` : ''} within ${p.hold_days} days.`,
    catalyst: d.event_in_hold ? 'Earnings report' : '', catalyst_date: d.event_in_hold ? d.earnings : '', hold_through: !!p.through_event,
    source: 'the contract picker' };
}
export function premiumStop(c) {
  const against = (((c.scenarios || {}).before_expiry) || []).find((s) => s.label === 'Stock moves against you');
  const per = against && isNum(against.value) ? against.value / 100 : null;
  return per && per > 0.01 && per < c.ask ? Math.round(per * 100) / 100 : '';
}
function practice(S, sym, i) {
  const d = S.data, c = d && (d.picks || [])[i]; if (!c) return;
  try { localStorage.setItem('optic.v2.paper.draft.v1', JSON.stringify(draftFrom(d, c, sym))); } catch (e) { /* private mode: the desk opens empty */ }
  location.hash = '#/paper';
}

/** Mounts the picker into `host` for `sym`; `ctx()` gives the spot and the next report date when known. */
export function mountPicker(host, sym, ctx) {
  const S = { plan: readPlan(), data: null, loading: false, error: null, spot: null, nextReport: null, seq: 0 };
  const paint = () => {
    const c = ctx() || {}; S.spot = c.spot || S.spot; S.nextReport = c.nextReport || S.nextReport;
    draw(host, html`<div class="section-head"><div><h2 class="t-h2" id="pk-h">Pick a contract</h2><p class="section-sub">Say what you expect and for how long; Optic shows up to three contracts that fit, or says none does.</p></div></div>
      ${form(S)}<div aria-live="polite">${results(S)}</div>`);
  };
  const read = () => { const f = $('[data-pk-form]', host); if (!f) return; S.plan = { ...S.plan, max_premium: f.max_premium.value, target: f.target.value, invalidation: f.invalidation.value, through_event: f.through_event.checked }; };
  const run = async () => {
    read(); savePlan(S.plan);
    const my = ++S.seq; S.loading = true; S.error = null; paint();
    try { const d = await api.get(`/api/options/${encodeURIComponent(sym)}/picker?${pickerQuery(S.plan)}`, { ttl: 60000, timeout: 60000 }); if (my === S.seq) S.data = d; } catch (e) { if (my === S.seq) S.error = e; }
    if (my === S.seq) { S.loading = false; paint(); }
  };
  host.addEventListener('click', (e) => {
    const pr = e.target.closest('[data-pk-practice]');
    if (pr) { practice(S, sym, Number(pr.dataset.pkPractice)); return; }
    const t = e.target.closest('[data-pk-thesis],[data-pk-hold],[data-v2-retry="picker"]'); if (!t) return;
    e.stopPropagation();   // the page's own retry handler does not know this one
    read();
    if (t.dataset.pkThesis) S.plan.thesis = t.dataset.pkThesis;
    if (t.dataset.pkHold) S.plan.hold_days = Number(t.dataset.pkHold);
    if (t.dataset.v2Retry === 'picker') { run(); return; }
    S.data = null; savePlan(S.plan); paint();
  });
  host.addEventListener('submit', (e) => { if (e.target.closest('[data-pk-form]')) { e.preventDefault(); run(); } });
  paint();
  // the spot and the report date arrive after the page draws: repaint without losing what was typed
  return { refresh: () => { read(); paint(); }, state: () => S };
}
