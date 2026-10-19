// Dossier, Options. Readings first (what options are pricing, compact so the
// builder is close on a phone), then the position builder, the research
// table of contracts, and the deeper analysis in tabs.
//
// Data: /api/ticker (the same snapshot as the Overview), /api/options/{T}/
// research for one expiry and side, POST /api/options/{T}/analyze for a
// position, /api/earnings for the report-day comparison. None calls a model.
// The builder's templates pick strikes by nearest delta exactly as the classic
// app does (optTemplate), and every P/L figure is the server's.
import { $, $$, html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, signed, money, clean, shortDate, isNum } from '../core/format.js';
import { mountCharts } from '../ui/chart.js';
import { xyChart } from '../ui/xychart.js';
import { skeleton, empty, failed, staleLine } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { tabset } from '../ui/tabset.js';
import { toast } from '../ui/toast.js';
import { core, header, tabs, isFund } from './dossier-frame.js';
import * as P from './options-panels.js';

const FILTER_KEY = 'optic.options.filters.v1';   // a tool setting, as in the classic app
const BUDGET_KEY = 'optic.entry.budget.v1';      // personal: read only while this browser holds it
const TEMPLATES = [
  ['long_call', 'Long call'], ['long_put', 'Long put'], ['bull_call', 'Bull call spread'], ['bear_put', 'Bear put spread'],
  ['covered_call', 'Covered call'], ['csp', 'Cash-secured put'], ['straddle', 'Straddle'], ['strangle', 'Strangle'],
  ['iron_condor', 'Iron condor'], ['calendar', 'Call calendar'],
];
const DELTAS = { any: [0, 1, 'Any'], far: [0.1, 0.3, 'Far, .10 to .30'], mid: [0.3, 0.5, 'Middle, .30 to .50'], atm: [0.4, 0.6, 'At the money, .40 to .60'], deep: [0.6, 0.9, 'Deep, .60 to .90'] };

// GEN: one per render. Every await checks it, so an answer for the symbol (or page) before never lands on this one:
// a slow AAPL ticker load used to paint into MSFT's Options page (owner's cross-ticker audit, 2026-10-19).
let D = {}, R = {}, B = {}, live = true, refresh = null, mainEl = null, panelState = 0, GEN = 0;
const stillHere = (g) => live && g === GEN;

function readFilters() {
  try { return Object.assign({ side: 'call', delta: 'any', maxSpread: 25, minOi: 0, unquoted: false, slippage: 0.25, fee: 0.65 }, JSON.parse(localStorage.getItem(FILTER_KEY) || '{}')); }
  catch (e) { return { side: 'call', delta: 'any', maxSpread: 25, minOi: 0, unquoted: false, slippage: 0.25, fee: 0.65 }; }
}
function saveFilters() {
  try { localStorage.setItem(FILTER_KEY, JSON.stringify({ side: R.side, delta: R.delta, maxSpread: R.maxSpread, minOi: R.minOi, unquoted: R.unquoted, slippage: B.slippage, fee: B.fee })); } catch (e) { /* private */ }
}
function readBudget() {
  if (!holds(store.state.user)) return 0;
  try { return Number(localStorage.getItem(BUDGET_KEY)) || 0; } catch (e) { return 0; }
}
function saveBudget(v) {
  if (!holds(store.state.user)) return;
  try { if (v) localStorage.setItem(BUDGET_KEY, String(v)); else localStorage.removeItem(BUDGET_KEY); } catch (e) { /* private */ }
}

/* ---------------- readings ---------------- */
function readings(sym) {
  const t = D.t || {}, vs = t.vol_surface || {}, g = t.gex || {}, e = D.earn || {};
  if (!D.t) return html`<section class="readings" aria-label="What options are pricing">${skeleton('lines', 2, 'Loading what options are pricing')}</section>`;
  const im = (e.implied && e.implied.available) ? e.implied : null;
  const r30 = P.row30(vs);
  const spot = (D.quote || t.quote || {}).price;
  const pr = e.pricing || {};
  const main = im ? { pct: im.implied_move_pct, expiry: im.expiry, dte: im.dte, event: !!(e.next_report && e.next_report.date && e.next_report.date <= im.expiry) }
    : r30 ? { pct: r30.straddle_move_pct, expiry: r30.expiry, dte: r30.dte, event: r30.contains_event } : null;
  const cells = [];
  if (main) cells.push(html`<div class="rd main"><span class="k">Implied move through ${shortDate(main.expiry)}</span><span class="v">±${num(main.pct)}%</span><span class="d">${isNum(spot) ? `${num(spot * (1 - main.pct / 100), 0)} to ${num(spot * (1 + main.pct / 100), 0)}. ` : ''}All ${main.dte} days${main.event && e.next_report ? `, the ${shortDate(e.next_report.date)} report included` : ''}.</span></div>`);
  if (pr.available && isNum(pr.event_day_avg_pct)) cells.push(html`<div class="rd"><span class="k">Average report-day move</span><span class="v">±${num(pr.event_day_avg_pct)}%</span><span class="d">Last ${(e.surprise || {}).quarters || 8} quarters. History, not a price.</span></div>`);
  if (pr.available && isNum(pr.ratio)) cells.push(html`<div class="rd"><span class="k">Priced against history</span><span class="v">${num(pr.ratio, 2)}×</span><span class="d">±${num(pr.implied_move_pct)}% ÷ ±${num(pr.baseline_move_pct)}% typical for ${pr.baseline_sessions} sessions</span></div>`);
  const iv = vs.iv30 || {};
  if (iv.available) cells.push(html`<div class="rd"><span class="k">Implied volatility, 30 days</span><span class="v">${num(iv.iv_pct, 1)}%</span><span class="d">${(t.iv_rank || {}).available ? `Rank ${num(t.iv_rank.rank, 0)}` : 'No rank yet: history still building'}</span></div>`);
  // one expiry across the readings where the surface has it
  const rs = (main && (vs.expiries || []).find((x) => x.expiry === main.expiry)) || r30;
  if (rs) cells.push(html`<div class="rd"><span class="k">Skew, ${shortDate(rs.expiry)}</span><span class="v">${P.skewWords(rs.rr25_pts)}</span><span class="d">25-delta risk reversal ${signed(rs.rr25_pts, 1, ' pts')}</span></div>`);
  if (!g.error && g.regime) cells.push(html`<div class="rd"><span class="k">Dealer gamma</span><span class="v">${(g.regime.state || '').replace(/^./, (c) => c.toUpperCase())}</span><span class="d">${g.levels && g.levels.call_wall ? `Walls ${num(g.levels.call_wall.strike, 0)} and ${num((g.levels.put_wall || {}).strike, 0)}` : ''}</span></div>`);
  if (!cells.length) return '';
  return html`<section class="readings" style="--rn:${Math.min(cells.length, 6)}" aria-label="What options are pricing">${cells}</section>`;
}

/* ---------------- position builder ---------------- */
const legLabel = (l) => (l.type === 'stock' ? `${l.side === 'long' ? 'Long' : 'Short'} ${l.qty} shares` : `${l.side === 'long' ? 'Buy' : 'Sell'} ${l.qty} × ${num(l.strike, l.strike % 1 ? 2 : 0)} ${l.type} ${shortDate(l.expiry)}`);
const paid = (v) => (isNum(v) ? `${money(Math.abs(v), 2)} ${v >= 0 ? 'paid' : 'received'}` : 'n/a');

function builder(sym) {
  const exps = ((R.data || {}).listed_expiries) || [];
  const a = B.analysis;
  return html`<section class="section builder" aria-labelledby="pb-h">
    <div class="section-head"><div><h2 class="t-h2" id="pb-h">Position builder</h2><p class="section-sub">Pick a template or add contracts from the table below. Every figure is per position, from the server's own pricing.</p></div>
      <label class="select"><span class="t-label">Expiry</span><select data-v2-op-expiry aria-label="Expiry for templates and the table">${exps.map((x) => html`<option value="${x.expiry}" ${x.expiry === R.expiry ? 'selected' : ''}>${shortDate(x.expiry)}, ${x.dte} days${x.monthly ? ', monthly' : ''}</option>`)}</select></label></div>
    <div class="tpl" role="group" aria-label="Templates">${TEMPLATES.map(([id, label]) => html`<button type="button" class="chip" data-v2-tpl="${id}" aria-pressed="${B.template === id}">${label}</button>`)}</div>
    ${B.legs.length ? html`<ul class="legs-list" aria-label="Legs">${B.legs.map((l, i) => html`<li><span class="leg-l">${legLabel(l)}</span>
        <button type="button" class="textlink" data-v2-leg-flip="${i}">${l.side === 'long' ? 'Make it a sale' : 'Make it a buy'}</button>
        <label class="field field-xs"><span class="sr">Quantity for ${legLabel(l)}</span><input type="number" min="1" max="${l.type === 'stock' ? 100000 : 100}" value="${l.qty}" data-v2-leg-qty="${i}"></label>
        <button type="button" class="icon-btn" data-v2-leg-del="${i}" aria-label="Remove ${legLabel(l)}">${icon('close')}</button></li>`)}</ul>` : ''}
    <div id="op-result">${result(sym)}</div>
    <details class="more-inline costs"><summary>Costs and timing</summary><form class="cluster" data-v2-costs>
      <label class="field field-sm"><span class="t-label">Slippage, share of half-spread</span><input name="slippage" inputmode="decimal" value="${B.slippage}"></label>
      <label class="field field-sm"><span class="t-label">Fee per contract</span><input name="fee" inputmode="decimal" value="${B.fee}"></label>
      <label class="field field-sm"><span class="t-label">Days from now for the grid</span><input name="days" inputmode="numeric" placeholder="Halfway" value="${B.days || ''}"></label>
      <button type="submit" class="btn btn-sm">Apply</button></form></details>
  </section>`;
  void a;
}

function result(sym) {
  if (B.analyzing) return skeleton('chart', 1, 'Pricing the position');
  if (B.error) return html`<div class="state err" role="alert"><p class="t-h3">The position could not be priced</p><p>${clean(B.error)}</p></div>`;
  const a = B.analysis;
  if (!B.legs.length || !a) return html`<p class="quiet">No position yet. A template fills the legs from the ${R.expiry ? shortDate(R.expiry) : 'selected'} expiry; Add in the table puts in one contract.</p>`;
  const en = a.entry || {}, gk = a.greeks || {};
  const mp = a.max_profit_unbounded ? 'No cap (it rises with the price)' : money(a.max_profit, 0);
  const ml = a.max_loss_unbounded ? 'No limit (a short call has no ceiling)' : money(Math.abs(a.max_loss), 0);
  const sc = a.scenarios || {}, when = B.when;
  const rows = (sc.rows || []).filter((r) => r.when === when);
  const whens = [...new Set((sc.rows || []).map((r) => r.when))];
  return html`<dl class="kv tiles" style="--kv:3">
      <div><dt>Entry at the mid</dt><dd>${paid(en.mid)}</dd></div>
      <div><dt>Crossing the spread (buy at the ask, sell at the bid)</dt><dd>${paid(en.natural)}</dd></div>
      <div><dt>With your slippage and fees</dt><dd>${paid(en.with_slippage_and_fees)}</dd></div>
      <div><dt>Most it can make at expiry</dt><dd class="up">${a.bounds_note ? clean(a.bounds_note) : mp}</dd></div>
      <div><dt>Most it can lose at expiry</dt><dd class="down">${a.bounds_note ? 'See the note' : ml}<small class="t-muted"> Not your broker's margin requirement.</small></dd></div>
      <div><dt>Breakeven at expiry</dt><dd>${(a.breakevens_at_expiry || []).length ? a.breakevens_at_expiry.map((b) => num(b)).join(' and ') : 'None in range'}</dd></div></dl>
    <div class="chart-slot" data-chart="payoff"></div>
    <p class="asof">Solid: at expiry, exact from the mid entry. Gold: today. Dashed: halfway to the first expiry, ${num((a.first_expiry_days || 0) / 2, 0)} days. Model values hold each leg's current IV. The gold line marks the price now.</p>
    <p><b>Greeks:</b> delta ${num(gk.delta_shares, 0)} shares, gamma ${num(gk.gamma_per_dollar, 2)} per dollar, decay ${money(gk.theta_per_day, 2)} a day, ${money(gk.vega_per_vol_pt, 2)} per volatility point.</p>
    ${rows.length ? html`<h3>If the price and the volatility change</h3>
      <div class="seg" role="group" aria-label="When">${whens.map((w) => html`<button type="button" data-v2-when="${w}" aria-pressed="${w === when}">${w === 'now' ? 'Now' : w === 'expiry' || w === 'at expiry' ? 'At expiry' : `In ${num(B.days || (a.first_expiry_days || 0) / 2, 0)} days`}</button>`)}</div>
      <div class="tscroll"><table class="t scen"><thead><tr><th>IV change</th>${(sc.moves_pct || []).map((m) => html`<th>${signed(m, 0)}</th>`)}</tr></thead>
        <tbody>${rows.map((r) => html`<tr><td>${signed(r.iv_shift_pts, 0, ' pts')}</td>${r.pnl.map((p) => html`<td class="${p > 0 ? 'up' : p < 0 ? 'down' : ''}">${signed(p, 0, '')}</td>`)}</tr>`)}</tbody></table></div>` : ''}
    ${(a.flags || []).map((f) => html`<p class="stale">${clean(f.text || f)}</p>`)}
    ${(a.events || []).length ? html`<ul class="plain">${a.events.map((ev) => html`<li>${clean(ev.text)}</li>`)}</ul>` : ''}
    <details class="more-inline"><summary>Liquidity and assumptions</summary>
      <ul class="plain">${(a.leg_liquidity || []).map((l) => html`<li><b>${num(l.strike, 0)} ${l.type}: ${l.label}.</b> ${(l.reasons || []).map(clean).join(' ')}</li>`)}</ul>
      ${a.multi_leg_note ? html`<p>${clean(a.multi_leg_note)}</p>` : ''}<ul class="plain">${(a.assumptions || []).map((x) => html`<li>${clean(x)}</li>`)}</ul>
      <p class="asof">${clean(en.note || '')} Rate ${(a.rate || {}).label || ''}.</p></details>
    ${miloButton('Ask Milo about this position', { ask: `Explain this ${sym} position in plain English: ${B.legs.map(legLabel).join(', ')}. How would it react to a 5% drop with implied volatility up 10 points?`, context: `${sym} Dossier, Options, the position`, symbol: sym })}`;
}

function payoffMaker() {
  const a = B.analysis; if (!a || !a.curves) return {};
  const c = a.curves, spot = a.spot;
  const lo = spot * 0.75, hi = spot * 1.25;
  return { payoff: (w) => xyChart([
    { name: 'At expiry', xs: c.price, ys: c.at_expiry, cls: 'main' },
    { name: 'Today', xs: c.price, ys: c.today, cls: 'alt' },
    { name: 'Halfway', xs: c.price, ys: c.halfway, cls: 'faint' },
  ], { w, h: Math.round(Math.max(220, Math.min(320, w * 0.4))), xlo: lo, xhi: hi, label: 'Position profit and loss by price', fill: true,
    yfmt: (v) => `${v < 0 ? '−' : v > 0 ? '+' : ''}$${num(Math.abs(v), 0)}`, markers: [{ x: spot, text: 'Now', cls: 'gold' }],
    dots: (a.breakevens_at_expiry || []).map((b) => ({ x: b, y: 0 })),
    summary: `Profit and loss of the position at expiry, today and halfway, across prices from ${num(lo, 0)} to ${num(hi, 0)}. Breakeven ${(a.breakevens_at_expiry || []).map((b) => num(b)).join(' and ') || 'none in range'}.` }) };
}

async function rows(expiry, side) {
  const key = `${expiry}|${side}`, mine = B;
  if (mine.cache[key]) return mine.cache[key];
  const d = await api.get(`/api/options/${encodeURIComponent(D.sym)}/research?side=${side}&expiry=${expiry}&delta_lo=0&delta_hi=1`, { ttl: 120000, timeout: 30000 });
  mine.cache[key] = (d.table || {}).rows || [];   // into this render's cache, never the next symbol's
  return mine.cache[key];
}
const nearest = (list, target) => list.filter((r) => r.mid).reduce((best, r) => (!best || Math.abs(Math.abs(r.delta) - target) < Math.abs(Math.abs(best.delta) - target) ? r : best), null);

async function template(id) {
  const exp = R.expiry; if (!exp) return;
  B.error = null; B.template = id;
  const g = GEN, mine = B;
  try {
    const calls = await rows(exp, 'call'), puts = await rows(exp, 'put');
    const L = (r, side, qty = 1) => (r ? { type: r.type, side, qty, strike: r.strike, expiry: r.expiry } : null);
    const c = (t) => nearest(calls, t), p = (t) => nearest(puts, t);
    let legs = [];
    if (id === 'long_call') legs = [L(c(0.5), 'long')];
    else if (id === 'long_put') legs = [L(p(0.5), 'long')];
    else if (id === 'bull_call') legs = [L(c(0.5), 'long'), L(c(0.3), 'short')];
    else if (id === 'bear_put') legs = [L(p(0.5), 'long'), L(p(0.3), 'short')];
    else if (id === 'covered_call') legs = [{ type: 'stock', side: 'long', qty: 100 }, L(c(0.3), 'short')];
    else if (id === 'csp') legs = [L(p(0.3), 'short')];
    else if (id === 'straddle') { const k = c(0.5); legs = [L(k, 'long'), L(puts.find((r) => r.strike === (k || {}).strike), 'long')]; }
    else if (id === 'strangle') legs = [L(c(0.25), 'long'), L(p(0.25), 'long')];
    else if (id === 'iron_condor') legs = [L(p(0.10), 'long'), L(p(0.20), 'short'), L(c(0.20), 'short'), L(c(0.10), 'long')];
    else if (id === 'calendar') {
      const cur = ((R.data || {}).listed_expiries || []).find((x) => x.expiry === exp) || { dte: 0 };
      const later = ((R.data || {}).listed_expiries || []).find((x) => x.dte >= cur.dte + 20);
      if (!later) throw new Error('No later expiry 20 or more days after this one for a calendar.');
      const back = await rows(later.expiry, 'call'); const k = c(0.5);
      legs = [L(k, 'short'), L(back.find((r) => r.strike === (k || {}).strike) || nearest(back, 0.5), 'long')];
    }
    if (!stillHere(g) || mine !== B) return;
    if (legs.some((l) => !l)) throw new Error('This expiry has no quoted contract near the deltas the template needs.');
    B.legs = legs;
    await analyze();
  } catch (e) { if (!stillHere(g) || mine !== B) return; B.error = e.message; paintBuilder(); }
}

async function analyze() {
  if (!B.legs.length) { B.analysis = null; paintBuilder(); return; }
  B.analyzing = true; B.error = null; paintResult();
  const g = GEN, mine = B;
  try {
    const out = await api.post(`/api/options/${encodeURIComponent(D.sym)}/analyze`, { legs: B.legs, slippage: B.slippage, fee_per_contract: B.fee, days_forward: B.days || undefined }, { timeout: 45000 });
    if (!stillHere(g) || mine !== B) return;
    B.analysis = out;
    const whens = [...new Set(((B.analysis.scenarios || {}).rows || []).map((r) => r.when))];
    if (!whens.includes(B.when)) B.when = whens[0] || 'now';
  } catch (e) { if (!stillHere(g) || mine !== B) return; B.analysis = null; B.error = e.message || 'The server could not price it.'; }
  B.analyzing = false;
  paintBuilder();
}

/* ---------------- research table ---------------- */
function research() {
  const d = R.data;
  const f = DELTAS[R.delta] || DELTAS.any;
  const head = html`<div class="section-head"><div><h2 class="t-h2" id="rc-h">Research contracts</h2><p class="section-sub">One expiry and side at a time, in strike order. Nothing here is ranked best.</p></div></div>
    <form class="op-filters" data-v2-op-form>
      <div class="seg" role="group" aria-label="Side"><button type="button" data-v2-op-side="call" aria-pressed="${R.side === 'call'}">Calls</button><button type="button" data-v2-op-side="put" aria-pressed="${R.side === 'put'}">Puts</button></div>
      <label class="select"><span class="t-label">Delta</span><select data-v2-op-set="delta">${Object.entries(DELTAS).map(([k, v]) => html`<option value="${k}" ${R.delta === k ? 'selected' : ''}>${v[2]}</option>`)}</select></label>
      <label class="select"><span class="t-label">Widest spread</span><select data-v2-op-set="maxSpread">${[[0, 'Any'], [5, '5%'], [10, '10%'], [25, '25%']].map(([v, l]) => html`<option value="${v}" ${Number(R.maxSpread) === v ? 'selected' : ''}>${l}</option>`)}</select></label>
      <label class="select"><span class="t-label">Least open interest</span><select data-v2-op-set="minOi">${[0, 100, 500, 1000].map((v) => html`<option value="${v}" ${Number(R.minOi) === v ? 'selected' : ''}>${v ? num(v, 0) : 'Any'}</option>`)}</select></label>
      <label class="check"><input type="checkbox" data-v2-op-set="unquoted" ${R.unquoted ? 'checked' : ''}> <span>Show contracts without a two-sided quote</span></label>
      <button type="button" class="textlink" data-v2-op-more aria-pressed="${R.more}">${R.more ? 'Fewer columns' : 'More columns'}</button></form>`;
  if (R.error) return html`${head}${failed('The contracts', R.error, { retry: 'research' })}`;
  if (!d || R.loading) return html`${head}${skeleton('rows', 6, 'Loading contracts')}`;
  if (d.unusable) return html`${head}${empty('No usable quotes for this expiry', clean(d.unusable))}`;
  const s = d.summary || {}, tbl = d.table || {}, all = tbl.rows || [];
  void f;
  // the strikes nearest the money first; the whole chain one press away
  let rs = all;
  if (!R.allStrikes && all.length > 15) {
    const k = all.reduce((b, r, i) => (Math.abs(r.moneyness_pct) < Math.abs(all[b].moneyness_pct) ? i : b), 0);
    const lo = Math.max(0, Math.min(all.length - 15, k - 7));
    rs = all.slice(lo, lo + 15);
  }
  return html`${head}
    <p class="asof">${shortDate(s.expiry)}, ${s.dte} days. At-the-money IV ${num(s.atm_iv_pct, 1)}%, straddle priced for ±${num(s.straddle_move_pct, 2)}%. Price ${num(d.spot)}. Showing ${tbl.shown} of ${tbl.total}.</p>
    ${(d.events || []).length ? html`<ul class="plain events-note">${d.events.map((e) => html`<li>${clean(e.text)}</li>`)}</ul>` : ''}
    <div class="tscroll"><table class="t contracts"><caption class="sr">${R.side === 'call' ? 'Calls' : 'Puts'} expiring ${shortDate(s.expiry)}</caption>
      <thead><tr><th>Strike</th><th>Delta</th><th>Bid / ask</th><th>Spread</th><th>IV</th><th>Breakeven</th><th>Cost</th>${R.more ? html`<th>Decay a day</th><th>Per vol pt</th><th>ITM, model</th><th>OI / volume</th><th>Early exercise</th>` : ''}<th><span class="sr">Add</span></th></tr></thead>
      <tbody>${rs.map((r) => html`<tr class="${Math.abs(r.moneyness_pct) < 1.5 ? 'atm' : ''}">
        <td><b>${num(r.strike, r.strike % 1 ? 1 : 0)}</b> <small class="t-muted">${signed(r.moneyness_pct, 1)}</small></td><td>${num(r.delta, 2)}</td>
        <td>${num(r.bid)} / ${num(r.ask)} <small class="t-muted">mid ${num(r.mid)}</small></td>
        <td><span class="liq liq-${(r.liquidity || {}).grade}" title="${((r.liquidity || {}).reasons || []).join(' ')}">${(r.liquidity || {}).label || ''}</span> <small class="t-muted">${num(r.spread_pct, 1)}%</small></td>
        <td>${num(r.iv_pct, 1)}%${r.iv_source === 'feed' || r.iv_source === 'filled' ? html` <small class="t-muted">feed</small>` : ''}</td>
        <td>${num(r.breakeven_ask)} <small class="t-muted">${signed(r.breakeven_move_pct, 1)}</small></td><td>${money(r.cost_ask_contract, 0)}</td>
        ${R.more ? html`<td>${money(r.theta_per_contract, 2)}</td><td>${money(r.vega_per_contract, 2)}</td><td>${num((r.p_itm_model || 0) * 100, 0)}%</td><td>${num(r.open_interest, 0)} / ${num(r.volume, 0)}</td><td>${r.exercise === 'european' ? 'European' : isNum(r.early_exercise_premium_contract) ? (r.early_exercise_premium_contract < 0.5 ? 'Under $1' : money(r.early_exercise_premium_contract, 0)) : 'n/a'}</td>` : ''}
        <td>${r.mid ? html`<button type="button" class="btn btn-sm" data-v2-add-leg="${r.strike}" aria-label="Add the ${num(r.strike, 0)} ${r.type} to the position">Add</button>` : ''}</td></tr>`)}</tbody></table></div>
    ${all.length > 15 ? html`<button type="button" class="textlink" data-v2-op-all aria-expanded="${!!R.allStrikes}">${R.allStrikes ? 'Show the 15 nearest the money' : `Show all ${all.length} strikes`}</button>` : ''}
    ${D.t && D.t.data_caveat ? html`<p class="asof">${clean(D.t.data_caveat)}</p>` : ''}
    <p class="asof">Cost is one contract (100 shares) at the ask, before fees. Breakeven at expiry is the strike plus or minus the ask. ITM (model) is N(d2) under risk-neutral pricing: not a forecast, and not a chance of profit. ${clean(((d.liquidity_method || {}).text) || '')}</p>`;
}

async function loadResearch() {
  R.loading = true; R.error = null; paintResearch();
  const my = ++R.seq, g = GEN;
  const [lo, hi] = DELTAS[R.delta] || DELTAS.any;
  const q = new URLSearchParams({ side: R.side, delta_lo: lo, delta_hi: hi, min_oi: R.minOi || 0, include_unquoted: R.unquoted ? 'true' : 'false' });
  if (R.expiry) q.set('expiry', R.expiry);
  if (Number(R.maxSpread)) q.set('max_spread', R.maxSpread);
  try {
    const d = await api.get(`/api/options/${encodeURIComponent(D.sym)}/research?${q}`, { ttl: 60000, timeout: 30000 });
    if (my !== R.seq || !stillHere(g)) return;
    R.data = d; R.expiry = d.expiry;
  } catch (e) { if (my !== R.seq || !stillHere(g)) return; R.error = e; }
  R.loading = false;
  paintResearch(); paintBuilder();
}

/* ---------------- painting ---------------- */
function paintResearch() { const h = $('#op-research', mainEl); if (h) draw(h, research()); }
function paintResult() { const h = $('#op-result', mainEl); if (h) { draw(h, result(D.sym)); mountCharts(h, payoffMaker()); } }
function paintBuilder() {
  const h = $('#op-builder', mainEl); if (!h) return;
  const f = document.activeElement && h.contains(document.activeElement) ? Object.entries(document.activeElement.dataset || {})[0] : null;
  draw(h, builder(D.sym)); mountCharts(h, payoffMaker());
  if (f) { const el = $(`[data-${f[0].replace(/[A-Z]/g, (m) => '-' + m.toLowerCase())}="${CSS.escape(f[1])}"]`, h); if (el) el.focus(); }
}
function paintTop() {
  const h = $('#op-top', mainEl); if (!h) return;
  draw(h, html`${header(D.sym, D, 'swing')}${tabs(D.sym, 'swing', { fund: isFund(D) })}
    ${D.tErr ? failed('Options data', D.tErr, { retry: 'ticker' }) : ''}
    ${D.t && D.t.digest && D.t.digest.lede ? html`<p class="lede-line">${clean(D.t.digest.lede)}</p>` : ''}
    ${readings(D.sym)}`);
}

const PANELS = [
  ['What options are pricing', (t, s) => P.pricing(t, s)],
  ['Dealer gamma', (t, s) => P.gex(t, s), (t) => P.gexCharts(t)],
  ['Flow', (t, s) => P.flow(t, s), (t) => P.flowCharts(t)],
  ['Delta and gamma', (t, s) => P.greeksPanel(t, s)],
  ['Ideas', (t, s) => P.ideas(t, s, D.budget), (t) => P.ideaCharts(t, (t.quote || {}).price)],
  ['Strike and entry', (t, s) => P.entry(t, s)],
  ['Swing verdict', (t, s) => P.verdict(t, s)],
  ['Levels and momentum', (t, s) => P.levels(t, s)],
  ['How value moves', () => P.lab(D.lab), () => P.labCharts(D.lab)],
  ['Setups and patterns', (t, s) => P.setups(t, s, D.extra), null, () => loadExtra()],
];
function paintMore() {
  const h = $('#op-more', mainEl); if (!h || !D.t) { if (h) draw(h, skeleton('lines', 3)); return; }
  if (D.t.gex && D.t.gex.error && !(D.t.vol_surface || {}).available) { draw(h, empty('No options analysis right now', clean(D.t.gex.error))); return; }
  const ts = tabset(PANELS.map(([label, body, charts, onOpen]) => ({ label, render: () => body(D.t, D.sym), mount: (p) => { if (charts) mountCharts(p, charts(D.t)); if (onOpen) onOpen(); } })), { label: 'More options analysis', selected: panelState });
  draw(h, html`<section class="section" aria-label="More options analysis"><h2 class="t-h2">More options analysis</h2>${ts.html}</section>`);
  ts.wire(h, (i) => { panelState = i; });
}
async function loadExtra() {
  if (D.extra.loading) return;
  D.extra.loading = true;
  const enc = encodeURIComponent(D.sym), g = GEN;
  const [st, se, rp] = await Promise.allSettled([api.get(`/api/setups?symbols=${enc}&status=recent`, { ttl: 300000 }), api.get(`/api/seasonality/${enc}`, { ttl: 3600000 }), api.get(`/api/relperf/${enc}`, { ttl: 600000 })]);
  if (!stillHere(g)) return;
  D.extra = { loading: true, setups: st.status === 'fulfilled' ? st.value : null, seasonality: se.status === 'fulfilled' ? se.value : null, relperf: rp.status === 'fulfilled' ? rp.value : null };
  if (live && panelState === PANELS.length - 1) paintMore();
}

async function loadTicker({ quiet } = {}) {
  const enc = encodeURIComponent(D.sym), g = GEN;
  try {
    const t = await api.get(`/api/ticker/${enc}?max_expiries=4&macro=true${D.budget ? `&budget=${D.budget}` : ''}`, { ttl: quiet ? 0 : 120000, force: !!quiet, timeout: 60000 });
    if (!stillHere(g)) return;
    D.t = t; D.tErr = null; D.lab = D.lab || P.labDefaults(t);
    if (t.quote) D.quote = Object.assign({}, D.quote || {}, t.quote);
  } catch (e) { if (!stillHere(g)) return; if (!quiet) D.tErr = e; }
  paintTop();
  if (!quiet) paintMore();
}

export async function render(main, route) {
  live = true; mainEl = main; panelState = 0; GEN += 1;
  const sym = route.symbol, g = GEN;
  const f = readFilters();
  D = { sym, extra: {}, budget: readBudget() };
  R = { side: f.side, delta: f.delta, maxSpread: f.maxSpread, minOi: f.minOi, unquoted: f.unquoted, more: false, expiry: null, data: null, seq: 0 };
  B = { legs: [], analysis: null, analyzing: false, error: null, slippage: f.slippage, fee: f.fee, days: null, when: 'now', cache: {}, template: null };
  store.pushRecent(sym);
  document.title = `${sym} Options, Optic`;
  provideContext(() => ({ view: 'swing', ticker: sym, quote: D.quote, gex: (D.t || {}).gex, greeks: (D.t || {}).greeks, flow: (D.t || {}).flow, vol_surface: (D.t || {}).vol_surface, iv_rank: (D.t || {}).iv_rank, entry_plan: (D.t || {}).entry_plan, verdict: (D.t || {}).verdict, naked_ideas: (D.t || {}).naked_ideas, strategy_ideas: (D.t || {}).strategy_ideas, rate: (D.t || {}).rate,
    options_research: R.data ? { expiry: R.expiry, side: R.side, summary: R.data.summary, events: R.data.events, rows: ((R.data.table || {}).rows || []).slice(0, 20), position: B.analysis ? { legs: B.legs, analysis: { entry: B.analysis.entry, max_profit: B.analysis.max_profit, max_loss: B.analysis.max_loss, breakevens: B.analysis.breakevens_at_expiry, greeks: B.analysis.greeks, scenarios: B.analysis.scenarios, flags: B.analysis.flags } } : null } : null }));
  draw(main, html`<div id="op-top"></div><div id="op-builder"></div><section class="section" id="op-research" aria-labelledby="rc-h"></section><div id="op-more"></div>`);
  paintTop(); paintBuilder(); paintResearch(); paintMore();
  wire(main);
  core(sym).then((c) => { if (!stillHere(g)) return; D.quote = Object.assign({}, c.quote || {}, D.quote || {}); D.session = c.session; D.quoteError = c.quoteError; paintTop(); });
  api.get(`/api/earnings/${encodeURIComponent(sym)}`, { ttl: 600000, timeout: 45000 }).then((e) => { if (stillHere(g)) { D.earn = e; paintTop(); } }).catch(() => {});
  loadTicker();
  loadResearch();
  // A light refresh while the market trades, of the readings only.
  clearInterval(refresh);
  refresh = setInterval(() => {
    const ph = ((D.session || {}).prices || {}).phase || ((D.session || {}).session || {}).phase;
    if (live && document.visibilityState === 'visible' && ['pre', 'regular', 'after'].includes(ph)) loadTicker({ quiet: true });
  }, 60000);
}

export function dispose() { live = false; clearInterval(refresh); }

export const retry = { ticker: () => loadTicker(), research: () => loadResearch() };

function wire(main) {
  main.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s);
    let b;
    if ((b = t('[data-v2-tpl]'))) { B.template = b.dataset.v2Tpl; B.analyzing = true; paintBuilder(); await template(b.dataset.v2Tpl); return; }
    if ((b = t('[data-v2-leg-flip]'))) { const l = B.legs[Number(b.dataset.v2LegFlip)]; l.side = l.side === 'long' ? 'short' : 'long'; B.template = null; await analyze(); return; }
    if ((b = t('[data-v2-leg-del]'))) { B.legs.splice(Number(b.dataset.v2LegDel), 1); B.template = null; await analyze(); return; }
    if ((b = t('[data-v2-when]'))) { B.when = b.dataset.v2When; paintResult(); const again = $(`[data-v2-when="${B.when}"]`, main); if (again) again.focus(); return; }
    if ((b = t('[data-v2-op-side]'))) { R.side = b.dataset.v2OpSide; saveFilters(); loadResearch(); return; }
    if (t('[data-v2-op-all]')) { R.allStrikes = !R.allStrikes; paintResearch(); const again = $('[data-v2-op-all]', main); if (again) again.focus(); return; }
    if ((b = t('[data-v2-op-more]'))) { R.more = !R.more; paintResearch(); const again = $('[data-v2-op-more]', main); if (again) again.focus(); return; }
    if ((b = t('[data-v2-add-leg]'))) {
      if (B.legs.filter((l) => l.type !== 'stock').length >= 4) { toast('Up to four option legs.'); return; }
      const r = ((R.data.table || {}).rows || []).find((x) => String(x.strike) === b.dataset.v2AddLeg);
      if (!r) return;
      B.legs.push({ type: r.type, side: 'long', qty: 1, strike: r.strike, expiry: r.expiry }); B.template = null;
      toast(`Added the ${num(r.strike, 0)} ${r.type} to the position.`);
      await analyze();
      const s = $('#pb-h', main); if (s) s.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    if ((b = t('[data-v2-budget]'))) { D.budget = Number(b.dataset.v2Budget) || 0; saveBudget(D.budget); toast(D.budget ? `Ideas sized to ${money(D.budget, 0)} a contract.` : 'Ideas shown with no budget limit.'); panelState = 4; await loadTicker(); return; }
    if ((b = t('[data-v2-lab]'))) { const [k, v] = b.dataset.v2Lab.split(':'); D.lab[k] = k === 'dte' ? Number(v) : v; paintMore(); const again = $(`[data-v2-lab="${b.dataset.v2Lab}"]`, main); if (again) again.focus(); }
  });
  main.addEventListener('change', async (e) => {
    const el = e.target;
    if (el.matches('[data-v2-op-expiry]')) { R.expiry = el.value; B.cache = {}; loadResearch(); return; }
    if (el.matches('[data-v2-op-set]')) { const k = el.dataset.v2OpSet; R[k] = el.type === 'checkbox' ? el.checked : el.value; saveFilters(); loadResearch(); return; }
    if (el.matches('[data-v2-leg-qty]')) { const l = B.legs[Number(el.dataset.v2LegQty)]; const q = Math.round(Number(el.value)); const max = l.type === 'stock' ? 100000 : 100; if (q >= 1 && q <= max) { l.qty = q; await analyze(); } else { toast(`Quantity is 1 to ${num(max, 0)}.`); el.value = l.qty; } return; }
    if (el.matches('[data-v2-lab-iv]')) { const v = Number(el.value); if (v >= 5 && v <= 200) { D.lab.iv = v; paintMore(); } }
  });
  main.addEventListener('submit', async (e) => {
    const c = e.target.closest('[data-v2-costs]');
    if (c) {
      e.preventDefault();
      const s = Number(c.slippage.value), f = Number(c.fee.value), d = c.days.value ? Math.round(Number(c.days.value)) : null;
      if (!(s >= 0 && s <= 1)) { toast('Slippage is 0 to 1, a share of half the spread.'); return; }
      if (!(f >= 0 && f <= 10)) { toast('Fee is 0 to 10 dollars a contract.'); return; }
      B.slippage = s; B.fee = f; B.days = d && d > 0 ? d : null; saveFilters(); await analyze(); return;
    }
    const bf = e.target.closest('[data-v2-budget-form]');
    if (bf) { e.preventDefault(); const v = Math.round(Number(bf.b.value)); if (!(v >= 1 && v <= 1e6)) { toast('A budget is whole dollars, 1 to 1,000,000.'); return; } D.budget = v; saveBudget(v); panelState = 4; await loadTicker(); }
  });
}
void $$; void staleLine;
