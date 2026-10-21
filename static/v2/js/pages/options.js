// Dossier, Options. Readings first (what options are pricing), then the page's tools in three groups
// near the top (owner's brief, 2026-10-19, item 12): Contracts and pricing (the chain at one expiry, the
// position builder on the same expiry, what options cost), Positioning and flow, and Setups and strategy.
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
import { num, signed, money, signedMoney, clean, shortDate, isNum, capFirst } from '../core/format.js';
import { etStamp } from '../core/marketTime.js';
import { mountCharts } from '../ui/chart.js';
import { xyChart } from '../ui/xychart.js';
import { skeleton, empty, failed, staleLine, how } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { core, header, tabs, isFund, fresher, livePrice } from './dossier-frame.js';
import * as P from './options-panels.js';
import { poll } from '../core/poll.js';
import { createPriceChart } from '../ui/pricechart.js';
import { sections } from '../ui/sections.js';
import { insiderMarks, barKey, barTime } from './chart-widgets.js';
import { mountSetups, disposeSetups, setupsContext } from './setups.js';
import * as TR from '../core/track.js';
let lp = null;   // the header's price refresh (dossier-frame livePrice), stopped in dispose()

const FILTER_KEY = 'optic.options.filters.v1';   // a tool setting, as in the classic app
const BUDGET_KEY = 'optic.entry.budget.v1';      // personal: read only while this browser holds it
const TEMPLATES = [
  ['long_call', 'Long call'], ['long_put', 'Long put'], ['bull_call', 'Bull call spread'], ['bear_put', 'Bear put spread'],
  ['covered_call', 'Covered call'], ['csp', 'Cash-secured put'], ['straddle', 'Straddle'], ['strangle', 'Strangle'],
  ['iron_condor', 'Iron condor'], ['calendar', 'Call calendar'],
];
// What a position was being built from, per symbol, for this visit: the expiry and the legs come back on a
// return from another page (they used to be lost on every visit), and are dropped when the expiry is no
// longer listed. Held in memory only: it is the reader's own work, and a sign-out (which reloads the page)
// must not hand it to the next account.
const KEPT = new Map();
const readState = (sym) => KEPT.get(sym) || null;
function saveState() { KEPT.set(D.sym, { expiry: R.expiry, legs: B.legs.map((l) => Object.assign({}, l)), template: B.template }); }
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
  if (main && isNum(main.pct)) cells.push(html`<div class="rd main"><span class="k">Implied move through ${shortDate(main.expiry)}</span><span class="v">±${num(main.pct)}%</span><span class="d">${isNum(spot) ? `${num(spot * (1 - main.pct / 100), 0)} to ${num(spot * (1 + main.pct / 100), 0)}. ` : ''}All ${P.dayCount(main.dte)}${main.event && e.next_report ? `, the ${shortDate(e.next_report.date)} report included` : ''}.</span></div>`);
  if (pr.available && isNum(pr.event_day_avg_pct)) cells.push(html`<div class="rd"><span class="k">Average report-day move</span><span class="v">±${num(pr.event_day_avg_pct)}%</span><span class="d">Last ${(e.surprise || {}).quarters || 8} quarters. History, not a price.</span></div>`);
  if (pr.available && isNum(pr.ratio)) cells.push(html`<div class="rd"><span class="k">Priced against history</span><span class="v">${num(pr.ratio, 2)}×</span><span class="d">the typical ±${num(pr.baseline_move_pct)}% for ${pr.baseline_sessions} sessions</span></div>`);
  const iv = vs.iv30 || {};
  if (iv.available) cells.push(html`<div class="rd"><span class="k">Implied volatility, 30 days</span><span class="v">${num(iv.iv_pct, 1)}%</span><span class="d">${(t.iv_rank || {}).available ? `Rank ${num(t.iv_rank.rank, 0)}` : 'No rank yet: history still building'}</span></div>`);
  // one expiry across the readings where the surface has it
  const rs = (main && (vs.expiries || []).find((x) => x.expiry === main.expiry)) || r30;
  if (rs && isNum(rs.rr25_pts)) cells.push(html`<div class="rd"><span class="k">Skew, ${shortDate(rs.expiry)}</span><span class="v">${P.skewWords(rs.rr25_pts)}</span><span class="d">25-delta risk reversal ${signed(rs.rr25_pts, 1, ' pts')}</span></div>`);
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
    <div class="section-head"><div><h2 class="t-h2" id="pb-h">Position builder</h2><p class="section-sub">${R.expiry ? `Priced on the ${shortDate(R.expiry)} expiry chosen above.` : 'Priced on the expiry chosen above, once the contracts load.'} Pick a template or press Add in the table. Figures are per position.</p></div></div>
    ${noQuotes() ? html`<p class="stale">${noQuotes()} The templates need two-sided quotes, so they are off until there are some.</p>` : ''}
    <div class="tpl" role="group" aria-label="Templates">${TEMPLATES.map(([id, label]) => html`<button type="button" class="chip" data-v2-tpl="${id}" aria-pressed="${B.template === id}" ${R.expiry && !noQuotes() ? '' : 'disabled'}>${label}</button>`)}</div>
    ${B.legs.length ? html`<ul class="legs-list" aria-label="Legs">${B.legs.map((l, i) => { const q = legQuote(l); return html`<li><div class="leg-main"><span class="leg-l">${legLabel(l)}</span>${q ? html`<small class="t-muted leg-q">${q}</small>` : ''}</div>
        <div class="leg-acts"><button type="button" class="btn btn-sm" data-v2-leg-flip="${i}">${l.side === 'long' ? 'Make it a sale' : 'Make it a buy'}</button>
        <span class="qty"><button type="button" class="icon-btn" data-v2-leg-step="${i}:-1" aria-label="One fewer" ${l.qty <= 1 ? 'disabled' : ''}>${icon('minus')}</button><label class="field field-xs"><span class="sr">Quantity for ${legLabel(l)}</span><input type="number" inputmode="numeric" min="1" max="${l.type === 'stock' ? 100000 : 100}" value="${l.qty}" data-v2-leg-qty="${i}"></label><button type="button" class="icon-btn" data-v2-leg-step="${i}:1" aria-label="One more">${icon('plus')}</button></span>
        <button type="button" class="icon-btn" data-v2-leg-del="${i}" aria-label="Remove ${legLabel(l)}">${icon('close')}</button></div></li>`; })}</ul>` : ''}
    <div id="op-result">${result(sym)}</div>
    <details class="more-inline costs"><summary>Costs and timing</summary><form class="cluster" data-v2-costs>
      <label class="field field-sm"><span class="t-label">Slippage, share of half-spread</span><input name="slippage" inputmode="decimal" value="${B.slippage}"></label>
      <label class="field field-sm"><span class="t-label">Fee per contract</span><input name="fee" inputmode="decimal" value="${B.fee}"></label>
      <label class="field field-sm"><span class="t-label">Days from now for the grid</span><input name="days" inputmode="numeric" placeholder="Halfway" value="${B.days || ''}"></label>
      <button type="submit" class="btn btn-sm">Apply</button></form></details>
  </section>`;
  void a; void exps;
}

// The chain's own reason when nothing is quoted (the free feed outside market hours), or ''.
const noQuotes = () => { const d = R.data; if (!d) return ''; if (d.unusable) return clean(d.unusable); const rows = (d.table || {}).rows || []; return rows.length && !rows.some((r) => isNum(r.mid)) ? 'No contract at this expiry has a two-sided quote right now.' : ''; };
// A leg's own quote, from what the server priced it at: bid and ask, the mid, the 100-share contract, liquidity.
function legQuote(l) {
  const a = B.analysis; if (!a || l.type === 'stock') return '';
  const m = (a.legs || []).find((x) => x.type === l.type && x.strike === l.strike && x.expiry === l.expiry && x.side === l.side);
  const liq = (a.leg_liquidity || []).find((x) => x.type === l.type && x.strike === l.strike && x.expiry === l.expiry);
  if (!m || !isNum(m.mid)) return '';
  return `Bid ${num(m.bid)}, ask ${num(m.ask)}, mid ${num(m.mid)}: ${money(m.mid * 100 * l.qty, 2)} for ${l.qty} contract${l.qty === 1 ? '' : 's'} of 100 shares${liq && liq.label ? `. Liquidity: ${liq.label.toLowerCase()}` : ''}.`;
}
const quotedAt = (iso) => (iso ? `Quotes read ${etStamp(iso)}${((D.session || {}).prices || {}).phase === 'regular' ? ', delayed about 15 minutes' : ', from the last session the feed has'}` : '');
function result(sym) {
  if (B.analyzing) return skeleton('chart', 1, 'Pricing the position');
  if (B.error) return html`<div class="state err" role="alert"><p class="t-h3">The position could not be priced</p><p>${clean(B.error)}</p></div>`;
  const a = B.analysis;
  if (!B.legs.length || !a) return html`<p class="quiet">No position yet. A template fills the legs from the ${R.expiry ? shortDate(R.expiry) : 'selected'} expiry; Add in the table puts in one contract.</p>`;
  const en = a.entry || {}, gk = a.greeks || {};
  // the expiry figures are from the mid entry; "no limit" is said for what the position does, not for one kind of leg
  const mp = a.max_profit_unbounded ? 'No cap: it gains as long as the price rises' : money(a.max_profit, 2);
  const ml = a.max_loss_unbounded ? 'No limit: it loses as long as the price rises' : a.cannot_lose_at_quotes ? 'Nothing, at these quotes' : money(-a.max_loss, 2);
  const withinUp = !!(a.calendar && a.bounds_note && !a.max_profit_unbounded), withinDown = !!(a.calendar && a.bounds_note && !a.max_loss_unbounded && !a.cannot_lose_at_quotes), within = withinUp || withinDown;
  const spotY = (() => { const c = a.curves || {}; if (!c.price) return null; let k = 0; c.price.forEach((x, i) => { if (Math.abs(x - a.spot) < Math.abs(c.price[k] - a.spot)) k = i; }); return c.today[k]; })();
  const sc = a.scenarios || {}, when = B.when;
  const rows = (sc.rows || []).filter((r) => r.when === when);
  const whens = [...new Set((sc.rows || []).map((r) => r.when))];
  return html`${a.quotes_note ? html`<p class="stale" role="alert">${clean(a.quotes_note)}</p>` : ''}
    <dl class="kv tiles" style="--kv:3">
      <div><dt>Entry at the mid</dt><dd>${paid(en.mid)}</dd></div>
      <div><dt>Crossing the spread (buy at the ask, sell at the bid)</dt><dd>${paid(en.natural)}</dd></div>
      <div><dt>With your slippage and fees</dt><dd>${paid(en.with_slippage_and_fees)}</dd></div>
      <div><dt>Most it can make at expiry, from the mid</dt><dd class="up">${mp}${withinUp ? html`<small class="t-muted"> Within the drawn prices.</small>` : ''}</dd></div>
      <div><dt>Most it can lose at expiry, from the mid</dt><dd class="down">${ml}${withinDown ? html`<small class="t-muted"> Within the drawn prices.</small>` : ''}<small class="t-muted"> Not your broker's margin requirement.</small></dd></div>
      <div><dt>Breakeven at expiry</dt><dd>${(a.breakevens_at_expiry || []).length ? a.breakevens_at_expiry.map((b) => num(b)).join(' and ') : 'None in range'}</dd></div></dl>
    ${within ? html`<p class="asof">${clean(a.bounds_note)}</p>` : ''}
    <p class="asof">${quotedAt(a.fetched_at)}${a.fetched_at ? '. ' : ''}Priced ${B.pricedAt ? etStamp(new Date(B.pricedAt).toISOString()) : 'now'}: a model value is an estimate, the mid is half way between a quoted bid and ask, and neither is a fill.</p>
    <div class="chart-slot" data-chart="payoff"></div>
    <p class="asof">Solid: at expiry. Gold: today. Dashed: in ${P.dayCount(num((a.first_expiry_days || 0) / 2, 0))}. The line marked Now is the price now.</p>
    ${isNum(spotY) && Math.abs(spotY) > Math.max(1, 0.01 * Math.abs(en.mid || 0)) ? html`<p class="asof">At today's price the model values the position at ${signedMoney(spotY, 2)} against its mid entry: the model holds one implied volatility per strike, the out-of-the-money side's, which is not exactly where each leg is quoted.</p>` : ''}
    ${how(html`<p>The expiry line is exact from the mid entry. Today's and the dashed lines are model values that hold each leg's current implied volatility; the dashed line is halfway to the first expiry.</p>`)}
    <p><b>Greeks:</b> delta ${num(gk.delta_shares, 0)} shares, gamma ${num(gk.gamma_per_dollar, 2)} per dollar, decay ${money(gk.theta_per_day, 2)} a day, ${money(gk.vega_per_vol_pt, 2)} per volatility point.</p>
    ${rows.length ? html`<h3>If the price and the volatility change</h3>
      <div class="seg" role="group" aria-label="When">${whens.map((w) => html`<button type="button" data-v2-when="${w}" aria-pressed="${w === when}">${capFirst(w)}</button>`)}</div>
      <div class="tscroll"><table class="t scen"><caption class="sr">Profit or loss in dollars, by the move in price (columns) and the change in implied volatility (rows)</caption><thead><tr><th scope="col">IV change</th>${(sc.moves_pct || []).map((m) => html`<th scope="col">Price ${signed(m, 0)}</th>`)}</tr></thead>
        <tbody>${rows.map((r) => html`<tr><th scope="row">${signed(r.iv_shift_pts, 0, ' pts')}</th>${r.pnl.map((p) => html`<td class="${p > 0 ? 'up' : p < 0 ? 'down' : ''}">${signedMoney(p, 0)}</td>`)}</tr>`)}</tbody></table></div>` : ''}
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
// The quoted contract nearest a delta, within 0.15 of it, and never one too wide to trade: a stale deep
// in-the-money call at delta 1.00 was the "0.50" pick for a long call, and both legs of a bull call spread.
const usable = (r) => isNum(r.mid) && isNum(r.delta) && ((r.liquidity || {}).grade !== 'not_tradable');
const nearest = (list, target) => { const best = list.filter(usable).reduce((b, r) => (!b || Math.abs(Math.abs(r.delta) - target) < Math.abs(Math.abs(b.delta) - target) ? r : b), null); return best && Math.abs(Math.abs(best.delta) - target) <= 0.15 ? best : null; };
// a template's strikes in the order its shape needs, each its own
const ordered = (legs, rule) => legs.every(Boolean) && rule(legs.filter((l) => l.type !== 'stock').map((l) => l.strike));

async function template(id) {
  const exp = R.expiry;
  if (!exp) { B.analyzing = false; B.error = 'The contracts for an expiry have not loaded yet, so there is nothing to build from.'; paintBuilder(); return; }
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
    else if (id === 'straddle') { const k = c(0.5); legs = [L(k, 'long'), L(puts.filter(usable).find((r) => r.strike === (k || {}).strike), 'long')]; }
    else if (id === 'strangle') legs = [L(c(0.25), 'long'), L(p(0.25), 'long')];
    else if (id === 'iron_condor') legs = [L(p(0.10), 'long'), L(p(0.20), 'short'), L(c(0.20), 'short'), L(c(0.10), 'long')];
    else if (id === 'calendar') {
      const cur = ((R.data || {}).listed_expiries || []).find((x) => x.expiry === exp) || { dte: 0 };
      const later = ((R.data || {}).listed_expiries || []).find((x) => x.dte >= cur.dte + 20);
      if (!later) throw new Error('No later expiry 20 or more days after this one for a calendar.');
      const back = await rows(later.expiry, 'call'); const k = c(0.5);
      legs = [L(k, 'short'), L(back.filter(usable).find((r) => r.strike === (k || {}).strike) || nearest(back, 0.5), 'long')];
    }
    if (!stillHere(g) || mine !== B) return;
    if (legs.some((l) => !l)) throw new Error('This expiry has no tradable quoted contract near the deltas the template needs.');
    const RULES = { bull_call: ([a, b]) => a < b, bear_put: ([a, b]) => a > b, strangle: ([c2, p2]) => c2 > p2, iron_condor: ([a, b, c2, d]) => a < b && b < c2 && c2 < d };
    if (RULES[id] && !ordered(legs, RULES[id])) throw new Error('The quoted strikes at this expiry are too close together for this shape: its legs would share a strike or come out of order.');
    B.legs = legs;
    await analyze();
  } catch (e) { if (!stillHere(g) || mine !== B) return; B.analyzing = false; B.error = e.message; paintBuilder(); }
}

// quiet: the two-minute re-price in session. The figures stay on screen until the new ones land: a skeleton in
// their place collapsed the result every two minutes and threw the reader about 1,000 px down the page (live
// check, 2026-10-20). A failed re-read keeps the last figures, whose quotes line says when they were read. Only
// the latest request lands, so a re-read that answers after the reader's own change cannot undo it.
async function analyze({ quiet } = {}) {
  const my = ++B.seq;
  if (!B.legs.length) { B.analysis = null; paintBuilder(); return; }
  if (!quiet) { B.analyzing = true; B.error = null; paintResult(); }
  const g = GEN, mine = B;
  try {
    const out = await api.post(`/api/options/${encodeURIComponent(D.sym)}/analyze`, { legs: B.legs, slippage: B.slippage, fee_per_contract: B.fee, days_forward: B.days || undefined }, { timeout: 45000 });
    if (!stillHere(g) || mine !== B || my !== B.seq) return;
    B.analysis = out; B.pricedAt = Date.now(); saveState();
    const whens = [...new Set(((B.analysis.scenarios || {}).rows || []).map((r) => r.when))];
    if (!whens.includes(B.when)) B.when = whens[0] || 'now';
  } catch (e) { if (!stillHere(g) || mine !== B || my !== B.seq || quiet) return; B.analysis = null; B.error = e.message || 'The server could not price it.'; }
  B.analyzing = false;
  paintBuilder();
}

/* ---------------- research table ---------------- */
// One expiry for the table and the builder. Before the chain answers it says so, and if it fails it says
// that, instead of an empty list.
function expirySelect() {
  const exps = ((R.data || {}).listed_expiries) || [];
  const opts = exps.length ? exps.map((x) => html`<option value="${x.expiry}" ${x.expiry === R.expiry ? 'selected' : ''}>${shortDate(x.expiry)}, ${P.dayCount(x.dte)}${x.monthly ? ', monthly' : ''}</option>`)
    : html`<option>${R.error ? 'Expiries unavailable' : 'Loading expiries'}</option>`;
  return html`<label class="select"><span class="t-label">Expiry</span><select data-v2-op-expiry aria-label="Expiry for the table and the position builder" ${exps.length ? '' : 'disabled'}>${opts}</select></label>`;
}

// a contract the feed has no live bid and ask for (or whose ask sits below its intrinsic value: a stale print)
const unquotedRow = (r) => !!r.quote_state && r.quote_state !== 'two_sided';

function research() {
  const d = R.data;
  const f = DELTAS[R.delta] || DELTAS.any;
  // How many contracts the box adds. The box shows only when it would change the list, with that count, so
  // ticking it is never a no-op: in a session nearly every contract near the money is quoted, and the few that
  // are not sit far from it (owner, 2026-10-20: "there is no difference when i check or uncheck this").
  if (d && !R.loading && !d.unusable) R.nUnq = R.unquoted ? ((d.table || {}).rows || []).filter(unquotedRow).length : ((d.table || {}).filtered_out || {}).unquoted || 0;
  const nUnq = R.nUnq;
  const head = html`<div class="section-head"><div><h2 class="t-h2" id="rc-h">Research contracts</h2><p class="section-sub">Calls or puts at one expiry, by strike. Nothing here is ranked best; the position builder below uses the same expiry.</p></div></div>
    <form class="op-filters" data-v2-op-form>
      ${expirySelect()}
      <div class="seg" role="group" aria-label="Side"><button type="button" data-v2-op-side="call" aria-pressed="${R.side === 'call'}">Calls</button><button type="button" data-v2-op-side="put" aria-pressed="${R.side === 'put'}">Puts</button></div>
      <label class="select"><span class="t-label">Delta</span><select data-v2-op-set="delta">${Object.entries(DELTAS).map(([k, v]) => html`<option value="${k}" ${R.delta === k ? 'selected' : ''}>${v[2]}</option>`)}</select></label>
      <label class="select"><span class="t-label">Widest spread</span><select data-v2-op-set="maxSpread">${[[0, 'Any'], [5, '5%'], [10, '10%'], [25, '25%']].map(([v, l]) => html`<option value="${v}" ${Number(R.maxSpread) === v ? 'selected' : ''}>${l}</option>`)}</select></label>
      <label class="select"><span class="t-label">Least open interest</span><select data-v2-op-set="minOi">${[0, 100, 500, 1000].map((v) => html`<option value="${v}" ${Number(R.minOi) === v ? 'selected' : ''}>${v ? num(v, 0) : 'Any'}</option>`)}</select></label>
      ${R.unquoted || nUnq ? html`<label class="check"><input type="checkbox" data-v2-op-set="unquoted" ${R.unquoted ? 'checked' : ''}> <span>${isNum(nUnq) && nUnq ? `Include ${nUnq} ${nUnq === 1 ? 'contract' : 'contracts'} without a two-sided quote` : 'Include contracts without a two-sided quote'}</span></label>` : ''}
      <button type="button" class="textlink" data-v2-op-more aria-pressed="${R.more}">${R.more ? 'Fewer columns' : 'More columns'}</button></form>`;
  if (R.error) return html`${head}${failed('The contracts', R.error, { retry: 'research' })}`;
  if (!d || R.loading) return html`${head}${skeleton('rows', 6, 'Loading contracts')}`;
  if (d.unusable) return html`${head}${empty('No usable quotes for this expiry', clean(d.unusable))}`;
  const s = d.summary || {}, tbl = d.table || {}, all = tbl.rows || [];
  void f;
  // A thinly quoted chain (the first minutes of a session, small names all day) has open interest, so the
  // server does not call it unusable, but nothing passes the filters: say why, from what was filtered out,
  // instead of an empty table under "At-the-money IV n/a%" (market-hours check, 2026-10-19).
  if (!all.length) {
    const fo = tbl.filtered_out || {}, why = [];
    if (fo.unquoted) why.push(`${fo.unquoted} without a two-sided quote`);
    if (fo.delta) why.push(`${fo.delta} outside the delta range`);
    if (fo.spread) why.push(`${fo.spread} with a wider spread than you allow`);
    if (fo.open_interest) why.push(`${fo.open_interest} under the least open interest`);
    return html`${head}${empty(`No ${R.side === 'call' ? 'calls' : 'puts'} to show at this expiry`, `${tbl.total ? `Of ${tbl.total} contracts, ${why.length ? why.join(', ') : 'none passed the filters'}.` : 'The chain has no contracts at this expiry.'}${fo.unquoted ? ' Quotes fill in as the session goes on; the box above lists them anyway.' : ' A wider filter may find some.'}`)}`;
  }
  const ivLine = isNum(s.atm_iv_pct) && isNum(s.straddle_move_pct) ? ` At-the-money IV ${num(s.atm_iv_pct, 1)}%, straddle priced for ±${num(s.straddle_move_pct, 2)}%.` : ' Too few quotes near the money for an at-the-money IV yet.';
  // the strikes nearest the money first; the whole chain one press away
  let rs = all;
  if (!R.allStrikes && all.length > 15) {
    const k = all.reduce((b, r, i) => (Math.abs(r.moneyness_pct) < Math.abs(all[b].moneyness_pct) ? i : b), 0);
    const lo = Math.max(0, Math.min(all.length - 15, k - 7));
    rs = all.slice(lo, lo + 15);
  }
  return html`${head}
    <p class="asof">${shortDate(s.expiry)}, ${P.dayCount(s.dte)}.${ivLine} Price ${num(d.spot)}. Showing ${tbl.shown} of ${tbl.total}.${d.fetched_at ? ` ${quotedAt(d.fetched_at)}.` : ''}</p>
    ${(d.events || []).filter((e) => /report/i.test(e.text || '')).length ? html`<ul class="plain events-note">${d.events.filter((e) => /report/i.test(e.text || '')).map((e) => html`<li>${clean(e.text)}</li>`)}</ul>` : ''}
    <div class="tscroll"><table class="t contracts"><caption class="sr">${R.side === 'call' ? 'Calls' : 'Puts'} expiring ${shortDate(s.expiry)}</caption>
      <thead><tr><th>Strike</th><th>Delta</th><th>Bid / ask</th><th>Spread</th><th>IV</th><th>Breakeven</th><th>Cost</th>${R.more ? html`<th>Decay a day</th><th>Per vol pt</th><th>ITM, model</th><th>OI / volume</th><th>Early exercise</th>` : ''}<th><span class="sr">Add</span></th></tr></thead>
      <tbody>${rs.map((r, n) => html`<tr class="${Math.abs(r.moneyness_pct) < 1.5 ? 'atm' : ''}">
        <td><b>${num(r.strike, r.strike % 1 ? 1 : 0)}</b> <small class="t-muted">${signed(r.moneyness_pct, 1)}</small><button type="button" class="icon-btn op-rowbtn" data-v2-op-row="${n}" aria-expanded="false" aria-controls="op-rd-${n}" aria-label="The ${num(r.strike, 0)} ${r.type}'s details">${icon('chev')}</button></td><td class="op-wide">${num(r.delta, 2)}</td>
        <td>${num(r.bid)} / ${num(r.ask)} <small class="t-muted">${unquotedRow(r) ? 'no two-sided quote' : `mid ${num(r.mid)}`}</small></td>
        <td><span class="liq liq-${(r.liquidity || {}).grade}" title="${((r.liquidity || {}).reasons || []).join(' ')}">${(r.liquidity || {}).label || ''}</span> <small class="t-muted">${num(r.spread_pct, 1)}%</small></td>
        <td class="op-wide">${num(r.iv_pct, 1)}%${r.iv_source === 'filled' ? html` <small class="t-muted">assumed</small>` : r.iv_source === 'feed' ? html` <small class="t-muted">feed</small>` : ''}</td>
        <td class="op-wide">${num(r.breakeven_ask)} <small class="t-muted">${signed(r.breakeven_move_pct, 1)}</small></td><td class="op-wide">${money(r.cost_ask_contract, 0)}</td>
        ${R.more ? html`<td>${money(r.theta_per_contract, 2)}</td><td>${money(r.vega_per_contract, 2)}</td><td>${isNum(r.p_itm_model) ? `${num(r.p_itm_model * 100, 0)}%` : 'n/a'}</td><td>${num(r.open_interest, 0)} / ${num(r.volume, 0)}</td><td>${r.exercise === 'european' ? 'European' : isNum(r.early_exercise_premium_contract) ? (r.early_exercise_premium_contract < 0.5 ? 'Under $1' : money(r.early_exercise_premium_contract, 0)) : 'n/a'}</td>` : ''}
        <td>${r.mid && (r.liquidity || {}).grade !== 'not_tradable' ? html`<button type="button" class="btn btn-sm" data-v2-add-leg="${r.strike}" aria-label="Add the ${num(r.strike, 0)} ${r.type} to the position">Add</button>` : html`<span class="t-muted">Not tradable</span>`}</td></tr>
        <tr class="op-detail" id="op-rd-${n}" hidden><td colspan="${R.more ? 13 : 8}"><dl class="kv"><div><dt>Delta</dt><dd>${num(r.delta, 2)}</dd></div><div><dt>IV</dt><dd>${num(r.iv_pct, 1)}%${r.iv_source === 'filled' ? ' (assumed)' : ''}</dd></div><div><dt>Breakeven at expiry</dt><dd>${num(r.breakeven_ask)} (${signed(r.breakeven_move_pct, 1)})</dd></div><div><dt>One contract at the ask</dt><dd>${money(r.cost_ask_contract, 0)}</dd></div><div><dt>Open interest / volume</dt><dd>${num(r.open_interest, 0)} / ${num(r.volume, 0)}</dd></div><div><dt>In the money, model</dt><dd>${isNum(r.p_itm_model) ? `${num(r.p_itm_model * 100, 0)}%` : 'n/a'}</dd></div></dl>${((r.liquidity || {}).reasons || []).length ? html`<p class="t-muted">${r.liquidity.reasons.map(clean).join(' ')}</p>` : ''}</td></tr>`)}</tbody></table></div>
    <div id="op-sum">${sumBar()}</div>
    ${all.length > 15 ? html`<button type="button" class="textlink" data-v2-op-all aria-expanded="${!!R.allStrikes}">${R.allStrikes ? 'Show the 15 nearest the money' : `Show all ${all.length} strikes`}</button>` : ''}
    ${how((d.events || []).filter((e) => !/report/i.test(e.text || '')).map((e) => html`<p>${clean(e.text)}</p>`),
      D.t && D.t.data_caveat ? html`<p>${clean(D.t.data_caveat)}</p>` : '',
      html`<p>Cost is one contract (100 shares) at the ask, before fees. Breakeven at expiry is the strike plus or minus the ask. ITM (model) is N(d2) under risk-neutral pricing: not a forecast, and not a chance of profit. ${clean(((d.liquidity_method || {}).text) || '')}</p>`)}`;
}

// What the position is now, at the foot of the chain. An Add says it too, in its toast, with a way to the
// builder: the page used to jump to the builder on every Add, which lost the reader's place in the chain.
function sumBar() {
  const a = B.analysis;
  if (!B.legs.length || !a) return '';
  return html`<div class="op-sum" role="status"><span>${B.legs.length} leg${B.legs.length === 1 ? '' : 's'}: ${paid((a.entry || {}).mid)} at the mid${a.max_loss_unbounded ? ', no limit to the loss' : a.cannot_lose_at_quotes ? ', the quotes look stale' : isNum(a.max_loss) ? `, most it can lose ${money(-a.max_loss, 2)}` : ''}.</span> <button type="button" class="btn btn-sm" data-v2-op-sum>See the position</button></div>`;
}
const paintSum = () => { const h = $('#op-sum', mainEl); if (h) draw(h, sumBar()); };
const sumLine = () => { const a = B.analysis; return a ? ` ${B.legs.length} leg${B.legs.length === 1 ? '' : 's'}, ${paid((a.entry || {}).mid)} at the mid.` : ''; };
function toBuilder() { const h = $('#pb-h', mainEl); if (h) { h.setAttribute('tabindex', '-1'); h.scrollIntoView({ block: 'start' }); h.focus({ preventScroll: true }); } }

async function loadResearch({ quiet } = {}) {
  if (!quiet) { R.loading = true; R.error = null; paintResearch(); }
  const my = ++R.seq, g = GEN;
  const [lo, hi] = DELTAS[R.delta] || DELTAS.any;
  const q = new URLSearchParams({ side: R.side, delta_lo: lo, delta_hi: hi, min_oi: R.minOi || 0, include_unquoted: R.unquoted ? 'true' : 'false' });
  if (R.expiry) q.set('expiry', R.expiry);
  if (Number(R.maxSpread)) q.set('max_spread', R.maxSpread);
  try {
    // 60 s, as the ticker snapshot it waits on gets: at 30 s the table timed out twice just after the open (2026-10-19)
    const d = await api.get(`/api/options/${encodeURIComponent(D.sym)}/research?${q}`, { ttl: quiet ? 0 : 60000, force: !!quiet, timeout: 60000 });
    if (my !== R.seq || !stillHere(g)) return;
    R.data = d; R.expiry = d.expiry; saveState();
    // ticking the box shows what it added: those contracts are usually past the 15 strikes nearest the money
    if (R.revealUnq) { R.revealUnq = false; const rows = (d.table || {}).rows || []; if (!R.allStrikes && rows.length > 15 && rows.some(unquotedRow)) R.allStrikes = R.allByUnq = true; }
  } catch (e) { if (my !== R.seq || !stillHere(g)) return; if (!quiet) R.error = e; }
  R.loading = false;
  paintResearch(); paintBuilder();
}

/* ---------------- painting ---------------- */
function paintResearch() { const h = $('#op-research', mainEl); if (h) draw(h, research()); }
function paintResult() { const h = $('#op-result', mainEl); if (h) { draw(h, result(D.sym)); mountCharts(h, payoffMaker()); } }
function paintBuilder() {
  const h = $('#op-builder', mainEl); if (!h) return;
  const f = document.activeElement && h.contains(document.activeElement) ? Object.entries(document.activeElement.dataset || {})[0] : null;
  draw(h, builder(D.sym)); mountCharts(h, payoffMaker()); paintSum();
  if (f) { const el = $(`[data-${f[0].replace(/[A-Z]/g, (m) => '-' + m.toLowerCase())}="${CSS.escape(f[1])}"]`, h); if (el) el.focus(); }
}
function paintTop() {
  const h = $('#op-top', mainEl), hd = $('#op-head', mainEl); if (!h) return;
  if (hd) draw(hd, html`${header(D.sym, D, 'swing')}${tabs(D.sym, 'swing', { fund: isFund(D) })}`);   // sticks (.dstick) above the long page
  draw(h, html`${hd ? '' : html`${header(D.sym, D, 'swing')}${tabs(D.sym, 'swing', { fund: isFund(D) })}`}
    ${D.tErr ? failed('Options data', D.tErr, { retry: 'ticker' }) : ''}
    ${D.t && D.t.digest && D.t.digest.lede ? html`<p class="lede-line">${clean(D.t.digest.lede)}</p>` : ''}
    ${readings(D.sym)}`);
}

const OPT_GROUPS = [
  { id: 'contracts', label: 'Contracts and pricing', sub: '', panels: [
    ['What options are pricing', (t, s) => P.pricing(t, s), (t) => P.pricingCharts(t)],
    ['How value moves', () => P.lab(D.lab), () => P.labCharts(D.lab)],
  ] },
  { id: 'positioning', label: 'Positioning and flow', sub: 'Dealer gamma is estimated from open interest, not reported positions; flow is the day\'s options volume, not a record of trades.', panels: [
    ['Dealer gamma', (t, s) => P.gex(t, s), (t) => P.gexCharts(t)],
    ['Flow', (t, s) => P.flow(t, s), (t) => P.flowCharts(t)],
    ['Delta and gamma', (t, s) => P.greeksPanel(t, s)],
  ] },
  { id: 'strategy', label: 'Setups and strategy', sub: 'The swing read, the entry it points to and the ideas sized to a budget are model output from these figures, not recommendations.', panels: [
    ['Swing verdict', (t, s) => P.verdict(t, s)],
    ['Strike and entry', (t, s) => P.entry(t, s)],
    ['Ideas', (t, s) => P.ideas(t, s, D.budget), (t) => P.ideaCharts(t, (t.quote || {}).price)],
    ['Price', (t, s) => priceBody(t, s), null, () => mountPrice()],
    ['Levels and momentum', (t, s) => P.levels(t, s), (t) => P.levelCharts(t)],
    ['Swing setups', (t, s) => P.swingSetups(t, s), null, () => mountSetups(mainEl, D.sym, { budget: () => D.budget || 0, live: () => String((D.quote || {}).market_state || '').toUpperCase() === 'REGULAR' })],
    ['Chart patterns and seasonality', (t, s) => P.patterns(t, s, D.extra), null, () => loadExtra()],
  ] },
];
const GROUP_KEY = 'optic.options.group.v1';   // a tool setting
/** The group that holds a section, by its title (Home's What changed opens Swing setups: the group is chosen first). */
export const groupFor = (title) => (OPT_GROUPS.find((g) => g.panels.some((x) => x[0] === title)) || {}).id || null;
const readGroup = () => { try { const i = OPT_GROUPS.findIndex((x) => x.id === localStorage.getItem(GROUP_KEY)); return i < 0 ? 0 : i; } catch (e) { return 0; } };

function groupBar() {
  return html`<div class="op-groups" role="tablist" aria-label="Options tools">${OPT_GROUPS.map((x, i) => html`<button type="button" role="tab" id="opg-t${i}" aria-controls="opg-p${i}" aria-selected="${i === panelState}" tabindex="${i === panelState ? 0 : -1}" data-v2-opg="${i}">${x.label}</button>`)}</div>`;
}
// The sections of the selected group after its fixed parts (the table and builder, for Contracts). A group
// is drawn when it is shown, so its charts measure a visible width.
function paintMore() {
  const i = panelState, grp = OPT_GROUPS[i];
  const h = $(`#opg-x${i}`, mainEl); if (!h) return;
  if (!D.t) { draw(h, D.tErr ? '' : skeleton('lines', 3, `Loading ${grp.label.toLowerCase()}`)); return; }
  // An unquoted chain (the free feed outside market hours) leaves every positioning panel with the same
  // reason; it is said once for the group.
  if (grp.id === 'positioning' && D.t.gex && D.t.gex.error && !(D.t.vol_surface || {}).available) { draw(h, empty('No positioning read right now', clean(D.t.gex.error))); return; }
  draw(h, grp.panels.map(([label, body], k) => html`<section class="section op-sec" aria-labelledby="opg-h${i}-${k}"><div class="section-head"><h2 class="t-h2" id="opg-h${i}-${k}">${label}</h2><span class="op-milo" data-opg-milo="${k}"></span></div><div data-opg-body="${k}">${body(D.t, D.sym)}</div></section>`));
  grp.panels.forEach(([label, , charts, onOpen], k) => {
    const b = $(`[data-opg-body="${k}"]`, h); if (charts && b) mountCharts(b, charts(D.t)); if (onOpen) onOpen();
    // a panel's Milo action sits at the right of its heading, as every section's does, and names the panel it was
    // asked from (editorial pass, 2026-10-19); the panels write it last in their body
    const m = b && [...b.children].reverse().find((x) => x.matches('.btn-milo')), slot = $(`[data-opg-milo="${k}"]`, h);
    if (m && slot) { m.dataset.v2MiloCtx = `${D.sym} Dossier, Options: ${label}`; slot.appendChild(m); }
  });
  // each group's sections fold, remembered as Classic's Options panels were (Classic parity B3); choosing a group is
  // already the reader asking for it, so no level folds them and the group needs no strip
  sections(h, 'swing', { strip: false });
}
function showGroup(i, focus) {
  panelState = i;
  try { localStorage.setItem(GROUP_KEY, OPT_GROUPS[i].id); } catch (e) { /* private mode */ }
  $$('.op-groups [role=tab]', mainEl).forEach((t, j) => { t.setAttribute('aria-selected', String(i === j)); t.tabIndex = i === j ? 0 : -1; if (focus && i === j) t.focus(); });
  $$('.op-gpanel', mainEl).forEach((p, j) => { p.hidden = i !== j; });
  if (i === 0) { paintResult(); }
  paintMore();
}
async function loadExtra() {
  if (D.extra.loading) return;
  D.extra.loading = true;
  const enc = encodeURIComponent(D.sym), g = GEN;
  // the base rates are the same for every symbol and can take ninety seconds to build when none are cached
  const [se, rp, br] = await Promise.allSettled([api.get(`/api/seasonality/${enc}`, { ttl: 3600000 }), api.get(`/api/relperf/${enc}`, { ttl: 600000 }), api.get('/api/patterns/base-rates', { ttl: 3600000, timeout: 150000 })]);
  if (!stillHere(g)) return;
  D.extra = { loading: true, seasonality: se.status === 'fulfilled' ? se.value : null, relperf: rp.status === 'fulfilled' ? rp.value : null, rates: br.status === 'fulfilled' ? br.value : { failed: true } };
  if (live && panelState === 2) paintMore();
}

async function loadTicker({ quiet } = {}) {
  const enc = encodeURIComponent(D.sym), g = GEN;
  try {
    const t = await api.get(`/api/ticker/${enc}?max_expiries=4&macro=true${D.budget ? `&budget=${D.budget}` : ''}`, { ttl: quiet ? 0 : 120000, force: !!quiet, timeout: 60000 });
    if (!stillHere(g)) return;
    D.t = t; D.tErr = null; D.lab = D.lab || P.labDefaults(t);
    if (t.quote) D.quote = fresher(D.quote, t.quote);
  } catch (e) { if (!stillHere(g)) return; if (!quiet) D.tErr = e; }
  paintTop();
  if (!quiet) paintMore();
}

export async function render(main, route) {
  live = true; mainEl = main; panelState = readGroup(); GEN += 1;
  const sym = route.symbol, g = GEN;
  const f = readFilters();
  D = { sym, extra: {}, budget: readBudget() };
  R = { side: f.side, delta: f.delta, maxSpread: f.maxSpread, minOi: f.minOi, unquoted: f.unquoted, more: false, expiry: null, data: null, seq: 0 };
  B = { legs: [], analysis: null, analyzing: false, seq: 0, error: null, slippage: f.slippage, fee: f.fee, days: null, when: 'now', cache: {}, template: null };
  const kept = readState(sym);
  if (kept && kept.expiry) { R.expiry = kept.expiry; B.legs = Array.isArray(kept.legs) ? kept.legs.map((l) => Object.assign({}, l)) : []; B.template = kept.template || null; }
  store.pushRecent(sym);
  document.title = `${sym} Options, Optic`;
  if (lp) lp.stop();
  lp = livePrice(main, route.symbol, () => D, 'swing', undefined);
  provideContext(() => ({ view: 'swing', ticker: sym, quote: D.quote, gex: (D.t || {}).gex, greeks: (D.t || {}).greeks, flow: (D.t || {}).flow, vol_surface: (D.t || {}).vol_surface, iv_rank: (D.t || {}).iv_rank, entry_plan: (D.t || {}).entry_plan, verdict: (D.t || {}).verdict, naked_ideas: (D.t || {}).naked_ideas, strategy_ideas: (D.t || {}).strategy_ideas, rate: (D.t || {}).rate, swing_setups: setupsContext(), track_record: TR.context(),
    options_research: R.data ? { expiry: R.expiry, side: R.side, summary: R.data.summary, events: R.data.events, rows: ((R.data.table || {}).rows || []).slice(0, 20),
      // when the quotes were read, and why figures are missing when they are (no two-sided quotes overnight)
      quotes_read_at: R.data.fetched_at || null, quotes_unusable: noQuotes() || null, position: B.analysis ? { legs: B.legs, analysis: { entry: B.analysis.entry, max_profit: B.analysis.max_profit, max_loss: B.analysis.max_loss, breakevens: B.analysis.breakevens_at_expiry, greeks: B.analysis.greeks, scenarios: B.analysis.scenarios, flags: B.analysis.flags } } : null } : null }));
  draw(main, html`<div class="dstick" id="op-head"></div><div id="op-top"></div>${groupBar()}
    ${OPT_GROUPS.map((x, i) => html`<div class="op-gpanel" id="opg-p${i}" role="tabpanel" aria-labelledby="opg-t${i}" ${i === panelState ? '' : 'hidden'}>${x.sub ? html`<p class="section-sub op-gsub">${x.sub}</p>` : ''}
      ${i === 0 ? html`<section class="section" id="op-research" aria-labelledby="rc-h"></section><div id="op-builder"></div>` : ''}<div id="opg-x${i}"></div></div>`)}`);
  paintTop(); paintBuilder(); paintResearch(); paintMore();
  wire(main);
  core(sym).then((c) => { if (!stillHere(g)) return; D.quote = fresher(D.quote, c.quote); D.session = c.session; D.quoteError = c.quoteError; paintTop(); });
  api.get(`/api/earnings/${encodeURIComponent(sym)}`, { ttl: 600000, timeout: 45000 }).then((e) => { if (stillHere(g)) { D.earn = e; paintTop(); } }).catch(() => {});
  loadTicker();
  loadResearch().then(() => {
    // a position kept from earlier in the visit is priced again, if its expiry is still listed
    if (!stillHere(g) || !B.legs.length) return;
    const listed = (((R.data || {}).listed_expiries) || []).map((x) => x.expiry);
    if (B.legs.some((l) => l.type !== 'stock' && !listed.includes(l.expiry))) { B.legs = []; B.template = null; saveState(); paintBuilder(); return; }
    analyze();
  });
  // While the market trades: the readings every minute, and the contracts and the position every two, so a
  // quote on screen is never more than a couple of minutes older than the feed.
  if (refresh) refresh.stop();
  let beat = 0;
  // the header's price refreshes every 20 s on its own (livePrice); the readings here are a full option read, so
  // every minute, never two at once, paused while hidden and caught up on return (core/poll.js)
  refresh = poll(async (current) => {
    const ph = ((D.session || {}).prices || {}).phase || ((D.session || {}).session || {}).phase;
    if (!live || !current() || !['pre', 'regular', 'after'].includes(ph)) return;
    loadTicker({ quiet: true });
    beat += 1;
    if (beat % 2 === 0) { loadResearch({ quiet: true }); if (B.legs.length && !B.analyzing) analyze({ quiet: true }); }
  }, { every: 60000, closed: 600000 });
}

export function dispose() { if (lp) { lp.stop(); lp = null; } live = false; disposeSetups(); if (refresh) { refresh.stop(); refresh = null; } if (pc) { pc.destroy(); pc = null; } }

/* ---------------- the price chart (Classic's Options price chart, app.js:12383, 12786-12865) ----------------
 * The daily bars of the ticker payload on the shared price chart: pan, zoom, measure and the price scale as on the
 * Chart tab (docs/frontend-v2/CHART-GESTURES.md), the 20, 50 and 200-day averages, earnings, and the insider trades
 * as arrows; pressing an arrow opens the stock's insider filings. A refresh of the payload keeps the zoom. */
let pc = null, pcBars = null;
const dailyBars = (t) => {
  const ps = ((t || {}).technicals || {}).price_series || {};
  return (ps.dates || []).map((x, i) => ({ t: Date.parse(x), o: ps.open[i], h: ps.high[i], l: ps.low[i], c: ps.close[i], v: (ps.volume || [])[i] || 0 }))
    .filter((b) => isNum(b.c) && isNum(b.t) && b.c > 0).map((b) => ({ t: b.t, o: isNum(b.o) ? b.o : b.c, h: isNum(b.h) ? b.h : b.c, l: isNum(b.l) ? b.l : b.c, c: b.c, v: b.v }));
};
function priceBody(t, sym) {
  if (dailyBars(t).length < 5) return empty('No daily bars', `The price history for ${sym} did not load.`);
  return html`<p class="t-muted">Daily bars, split-adjusted, with the 20, 50 and 200-day averages. Drag to pan; wheel, pinch or the zoom buttons to zoom; Shift-drag or Measure to measure. An arrow is an insider trade: press it to open ${sym}'s insider filings.</p><div class="op-pc" id="op-pc"></div>`;
}
function mountPrice() {
  const host = $('#op-pc', mainEl); if (!host || !D.t) return;
  const bars = dailyBars(D.t); if (bars.length < 5) return;
  const kept = pc && pcBars && pcBars.length === bars.length && pcBars[0].t === bars[0].t ? pc.keep() : {};
  if (pc) pc.destroy();
  pcBars = bars;
  const keys = bars.map((b) => barKey(b.t, false)), sym = D.sym;
  const insiders = insiderMarks(D.t).map((m) => Object.assign({}, m, { t: barTime(bars, keys, m.at, { within: 4 }) })).filter((m) => m.t !== null);
  // the Chart tab's earnings marks: reported quarters with their EPS against the estimate, and the next report's date
  const eh = (D.t.company || {}).earnings_history || {};
  const er = [...(eh.quarters || []).map((q) => ({ t: Date.parse(q.date), kind: 'E', label: `Earnings ${q.date}: EPS ${num(q.eps_reported)} against ${num(q.eps_estimate)}` })),
    ...(eh.upcoming || []).map((q) => ({ t: Date.parse(q.date), kind: 'E', label: `Next report ${q.date}` }))].filter((e) => isNum(e.t));
  pc = createPriceChart(host, Object.assign(kept, {
    bars, style: 'candles', overlays: { ma: true, events: true, ins: true }, panes: { volume: true, rsi: false, macd: false },
    insiders, events: er, window: 126, label: `${sym}, daily bars`, height: Math.max(280, Math.min(420, Math.round(window.innerHeight * 0.5))),
    onInsider: () => { location.hash = `#/insiders?symbol=${encodeURIComponent(sym)}&view=insiders`; },
  }));
}

export const retry = { ticker: () => loadTicker(), research: () => loadResearch() };

function wire(main) {
  main.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s);
    let b;
    if ((b = t('[data-v2-tpl]'))) { B.template = b.dataset.v2Tpl; B.analyzing = true; paintBuilder(); await template(b.dataset.v2Tpl); return; }
    if ((b = t('[data-v2-leg-flip]'))) { const l = B.legs[Number(b.dataset.v2LegFlip)]; l.side = l.side === 'long' ? 'short' : 'long'; B.template = null; await analyze(); return; }
    if ((b = t('[data-v2-leg-del]'))) { B.legs.splice(Number(b.dataset.v2LegDel), 1); B.template = null; saveState(); await analyze(); return; }
    if ((b = t('[data-v2-leg-step]'))) { const [i, d] = b.dataset.v2LegStep.split(':').map(Number); const l = B.legs[i]; const max = l.type === 'stock' ? 100000 : 100; const q = Math.max(1, Math.min(max, l.qty + d * (l.type === 'stock' ? 100 : 1))); if (q !== l.qty) { l.qty = q; await analyze(); const again = $(`[data-v2-leg-step="${i}:${d}"]`, main); if (again && !again.disabled) again.focus(); } return; }
    if ((b = t('[data-v2-op-row]'))) { const r = document.getElementById(b.getAttribute('aria-controls')); const open = b.getAttribute('aria-expanded') !== 'true'; if (r) r.hidden = !open; b.setAttribute('aria-expanded', String(open)); return; }
    if (t('[data-v2-op-sum]')) { toBuilder(); return; }
    if ((b = t('[data-v2-when]'))) { B.when = b.dataset.v2When; paintResult(); const again = $(`[data-v2-when="${B.when}"]`, main); if (again) again.focus(); return; }
    if ((b = t('[data-v2-op-side]'))) { R.side = b.dataset.v2OpSide; saveFilters(); loadResearch(); return; }
    if (t('[data-v2-op-all]')) { R.allStrikes = !R.allStrikes; R.allByUnq = false; paintResearch(); const again = $('[data-v2-op-all]', main); if (again) again.focus(); return; }
    if ((b = t('[data-v2-op-more]'))) { R.more = !R.more; paintResearch(); const again = $('[data-v2-op-more]', main); if (again) again.focus(); return; }
    if ((b = t('[data-v2-add-leg]'))) {
      if (B.legs.filter((l) => l.type !== 'stock').length >= 4 && !B.legs.some((l) => String(l.strike) === b.dataset.v2AddLeg && l.type === R.side)) { toast('Up to four option legs.'); return; }
      const r = ((R.data.table || {}).rows || []).find((x) => String(x.strike) === b.dataset.v2AddLeg);
      if (!r) return;
      // the builder's repaint puts focus back where it was; it is here, so the page does not jump to the builder
      b.focus({ preventScroll: true });
      // the same contract again is one more of it, not a second leg (bought and sold, it would cancel)
      const same = B.legs.find((l) => l.type === r.type && l.strike === r.strike && l.expiry === r.expiry);
      let said;
      if (same) { same.qty = Math.min(100, same.qty + 1); said = `${legLabel(same)} now.`; }
      else { B.legs.push({ type: r.type, side: 'long', qty: 1, strike: r.strike, expiry: r.expiry }); said = `Added the ${num(r.strike, 0)} ${r.type}.`; }
      B.template = null;
      // the reader stays on the chain; the toast says what the position is now, and goes to it on a press
      await analyze();
      if (stillHere(GEN)) toast(`${said}${sumLine()}`, { action: 'See the position', run: toBuilder });
      return;
    }
    if ((b = t('[data-v2-opg]'))) { showGroup(Number(b.dataset.v2Opg)); return; }
    if ((b = t('[data-v2-budget]'))) { D.budget = Number(b.dataset.v2Budget) || 0; saveBudget(D.budget); toast(D.budget ? `Ideas sized to ${money(D.budget, 0)} a contract.` : 'Ideas shown with no budget limit.'); panelState = 2; await loadTicker(); return; }
    if ((b = t('[data-v2-lab]'))) { const [k, v] = b.dataset.v2Lab.split(':'); D.lab[k] = k === 'dte' ? Number(v) : v; paintMore(); const again = $(`[data-v2-lab="${b.dataset.v2Lab}"]`, main); if (again) again.focus(); }
  });
  main.addEventListener('keydown', (e) => {
    const tab = e.target.closest && e.target.closest('.op-groups [role=tab]');
    if (!tab) return;
    const i = Number(tab.dataset.v2Opg), n = OPT_GROUPS.length;
    const to = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i - 1 + n) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1;
    if (to >= 0) { e.preventDefault(); showGroup(to, true); }
  });
  main.addEventListener('change', async (e) => {
    const el = e.target;
    if (el.matches('[data-v2-op-expiry]')) {
      // legs priced on the old expiry would be read as the new one: they go, and the reader is told
      const had = B.legs.filter((l) => l.type !== 'stock').length;
      R.expiry = el.value; B.cache = {};
      if (had) { B.legs = B.legs.filter((l) => l.type === 'stock'); B.analysis = null; B.template = null; toast(`The ${had} option leg${had === 1 ? ' was' : 's were'} on another expiry, so the position was cleared. Pick a template or Add a contract on ${shortDate(el.value)}.`); paintBuilder(); }
      saveState(); loadResearch(); return;
    }
    if (el.matches('[data-v2-op-set]')) { const k = el.dataset.v2OpSet; R[k] = el.type === 'checkbox' ? el.checked : el.value; if (k === 'unquoted') { R.revealUnq = el.checked; if (!el.checked && R.allByUnq) R.allStrikes = false; R.allByUnq = false; } saveFilters(); loadResearch(); return; }
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
    if (bf) { e.preventDefault(); const v = Math.round(Number(bf.b.value)); if (!(v >= 1 && v <= 1e6)) { toast('A budget is whole dollars, 1 to 1,000,000.'); return; } D.budget = v; saveBudget(v); panelState = 2; await loadTicker(); }
  });
}
void $$; void staleLine;
