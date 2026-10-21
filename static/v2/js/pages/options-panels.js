// The Options page's deeper analysis, one tab each: what options are pricing,
// dealer gamma, flow, delta and gamma, ideas, strike and entry, the swing
// verdict, levels and momentum, how an option's value moves, and setups and
// patterns. Every figure and sentence comes from /api/ticker (or the endpoint
// named) with the classic app's wording; nothing is re-derived except the
// value lab, which is the classic app's own client-side Black-Scholes.
import { html, raw } from '../core/dom.js';
import { CLASSIC } from '../core/classic.js';
import { num, signed, dir, money, compact, clean, capFirst, shortDate, fullDate, isNum, score100 } from '../core/format.js';
import { signedBars, periodLines } from '../ui/bars.js';
import { xyChart } from '../ui/xychart.js';
import { lineChart } from '../ui/chart.js';
import { button as miloButton } from '../ui/milo.js';
import { empty, how } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import * as TR from '../core/track.js';

const pct = (v, dp = 1) => (isNum(v) ? `${num(v, dp)}%` : 'n/a');
const usd = (v, dp = 0) => (isNum(v) ? money(v, dp) : 'n/a');
const ask = (sym, label, q) => miloButton(label, { ask: q, context: `${sym} Dossier, Options`, symbol: sym });
const kv = (rows, n = 3) => html`<dl class="kv" style="--kv:${n}">${rows.filter(Boolean).map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
// the average of the call's and the put's implied volatility, from the sides that have one
const atmIv = (r) => { const v = [(r.call || {}).iv, (r.put || {}).iv].filter(isNum).map(Number); return v.length ? pct(v.reduce((a, b) => a + b, 0) / v.length * 100) : 'n/a'; };
const note = (t) => (t ? html`<p class="asof">${clean(t)}</p>` : '');

/** The expiry row the readings and pricing use: nearest 30 days. */
export function row30(vs) {
  const ex = (vs && vs.expiries) || [];
  return ex.length ? ex.reduce((a, r) => (Math.abs(r.dte - 30) < Math.abs(a.dte - 30) ? r : a), ex[0]) : null;
}
export const skewWords = (rr) => (!isNum(rr) ? 'n/a' : rr > 0.5 ? 'Puts dearer' : rr < -0.5 ? 'Calls dearer' : 'About equal');
// "1 day", "31 days": a one-day expiry read "Oct 21, 1 days" on the live chain (2026-10-20)
export const dayCount = (n) => `${n} ${Number(n) === 1 ? 'day' : 'days'}`;

/* ---------- what options are pricing ---------- */
export function pricing(t, sym) {
  const vs = t.vol_surface || {};
  if (!vs.available) return empty('No options pricing right now', 'The chain did not have enough two-sided quotes to read.');
  const r = row30(vs), iv = vs.iv30 || {}, rank = t.iv_rank || {}, term = vs.term || {}, ev = vs.event || {};
  // each read is its finding and, at most, one fact that bears on it; how a figure is computed and what its sign
  // means go in the fold below, so the list reads as what options are pricing (owner, 2026-10-20: "the point of
  // optic is simplicity", on the report day's formula shown under its finding)
  const evMove = ev.available && isNum(ev.move_pct) && ev.move_pct > 0;
  const items = [
    iv.available ? [`Options are priced for about ${num(iv.iv_pct, 1)}% a year of movement over the next ${iv.days || 30} days.`, rank.available ? `${clean(rank.label || 'IV rank')} ${num(rank.rank, 0)}${isNum(rank.percentile) ? `, percentile ${num(rank.percentile, 0)}` : ''}. ${clean(rank.note || '')}` : clean(rank.reason || '')] : null,
    t.iv_hv && t.iv_hv.available ? [`Implied ${num(t.iv_hv.iv30, 1)}% against realised ${num(t.iv_hv.hv30, 1)}%.`, clean(t.iv_hv.note || '')] : null,
    t.iv_cheapness && t.iv_cheapness.available ? [`Cheap or dear? ${clean(t.iv_cheapness.text || '')}`, clean(t.iv_cheapness.finding || '')] : null,
    r && isNum(r.straddle_move_pct) ? [`The ${shortDate(r.expiry)} at-the-money straddle is priced for a move of about ±${num(r.straddle_move_pct, 2)}%.`, `${isNum(r.one_sd_move_pct) ? `One standard deviation is ±${num(r.one_sd_move_pct, 2)}%.` : ''}${t.straddle_calibration && t.straddle_calibration.available ? ' ' + clean(t.straddle_calibration.text) : ''}`.trim()] : null,
    term.available ? [clean(term.text), ''] : null,
    r && isNum(r.rr25_pts) ? [`25-delta risk reversal: ${skewWords(r.rr25_pts)} (${signed(r.rr25_pts, 1, ' vol pts')}).`, ''] : null,
    ev.available ? [evMove ? `About ${num(ev.move_pct, 1)}% is priced for the report day itself.` : clean(ev.text), ''] : null,
  ].filter(Boolean);
  return html`<ul class="reads">${items.map(([a, b]) => html`<li><p>${a}</p>${b ? html`<p class="t-muted">${b}</p>` : ''}</li>`)}</ul>
    ${(vs.expiries || []).filter((e) => isNum(e.atm_iv_pct)).length > 2 ? html`<figure class="fv opt-term"><figcaption><p class="t-label">Implied volatility by expiry</p><p class="fv-unit">At-the-money implied volatility, a year's worth, for each expiry; "Report" marks the first that spans the next earnings report. What options cost, not a forecast.</p></figcaption><div class="chart-slot" data-chart="term"></div></figure>` : ''}
    <details class="more-inline"><summary>Compare expiries</summary><div class="tscroll"><table class="t">
      <thead><tr><th>Expiry</th><th>Days</th><th>ATM IV</th><th>Straddle move</th><th>1-SD move</th><th>Put skew</th><th>Quoted</th><th>Report inside</th></tr></thead>
      <tbody>${(vs.expiries || []).map((e) => html`<tr><td>${shortDate(e.expiry)}</td><td>${e.dte}</td><td>${pct(e.atm_iv_pct)}</td><td>±${num(e.straddle_move_pct, 2)}%</td><td>±${num(e.one_sd_move_pct, 2)}%</td><td>${signed(e.rr25_pts, 1, '')}</td><td>${e.two_sided} of ${e.contracts}</td><td>${e.contains_event ? 'Yes' : 'No'}</td></tr>`)}</tbody></table></div>
      ${(vs.notes || []).map((n) => note(n))}</details>
    ${note(`${vs.clock || ''} ${(t.rate || {}).label ? 'Rate ' + t.rate.label + '.' : ''}`)}
    ${how(r && isNum(r.straddle_move_pct) ? html`<p>A straddle's price and one standard deviation are what options cost, not limits on the price: a move that size or larger happens about a third of the time.</p>` : '',
      term.available ? html`<p>The term structure compares the front expiry's implied volatility with a later one's.</p>` : '',
      r && isNum(r.rr25_pts) ? html`<p>The risk reversal is the 25-delta put's implied volatility less the 25-delta call's: positive means downside puts cost more than upside calls.</p>` : '',
      evMove ? html`<p>The report day's move is read from the ${shortDate(ev.after)} expiry's IV against the ${shortDate(ev.before)} expiry's. ${clean(ev.method || '')}</p>` : '',
      vs.iv_method ? html`<p>${clean(vs.iv_method)}</p>` : '')}
    ${ask(sym, 'Ask Milo about implied volatility', `What is implied volatility telling me about ${sym} right now?`)}`;
}

// the term structure as a line: each expiry's at-the-money implied volatility, oldest expiry first
export function pricingCharts(t) {
  const rows = ((t.vol_surface || {}).expiries || []).filter((e) => isNum(e.atm_iv_pct));
  if (rows.length < 3) return {};
  const firstEvent = rows.findIndex((e) => e.contains_event);
  const G = rows.map((e, i) => ({ x: shortDate(e.expiry), sub: i === firstEvent ? 'Report' : '' }));
  return { term: (w) => periodLines(G, [{ name: 'At-the-money IV', cls: 's1', values: rows.map((e) => e.atm_iv_pct) }], { w, h: 190, zero: false, fmt: (v) => `${num(v, 1)}%`, axisFmt: (v) => `${num(v, 0)}%`, label: 'At-the-money implied volatility by expiry', summary: `Implied volatility by expiry, from ${num(rows[0].atm_iv_pct, 1)}% for ${shortDate(rows[0].expiry)} to ${num(rows[rows.length - 1].atm_iv_pct, 1)}% for ${shortDate(rows[rows.length - 1].expiry)}${firstEvent >= 0 ? `; the ${shortDate(rows[firstEvent].expiry)} expiry is the first to span the report` : ''}.` }) };
}

/* ---------- dealer gamma ---------- */
export function gex(t, sym) {
  const g = t.gex || {};
  if (g.error) return empty('Dealer gamma is not available', clean(g.error));
  const tot = g.totals || {}, reg = g.regime || {}, lv = g.levels || {};
  const wall = (k, w) => (w && isNum(w.strike) ? [k, html`${num(w.strike, 0)} <span class="t-muted">(${signed(w.distance_pct)})</span>`] : null);
  return html`${kv([
      ['Net dealer gamma', html`${signedMoneyCompact(tot.net_gex)} per 1% move${isNum(tot.pct_of_avg_dollar_volume) ? html` <span class="t-muted">(${num(tot.pct_of_avg_dollar_volume, 1)}% of average dollar volume)</span>` : ''}`],
      ['Regime', capFirst(reg.state || 'n/a')],
      ['Flip point', isNum(reg.flip_point) ? html`${num(reg.flip_point)} <span class="t-muted">(${signed(reg.flip_distance_pct)}, ${reg.flip_direction || ''})</span>` : 'No crossing within 12%'],
    ])}
    <p>${clean(reg.note || '')} <b>Walls:</b> ${clean(reg.swing_implication || '')}</p>${note(reg.sign_note)}
    ${TR.slot('regime')}${TR.slot('walls')}
    <h3>Key levels</h3>${kv([wall('Call wall', lv.call_wall), wall('Put wall', lv.put_wall), wall('Gamma pin', lv.gamma_pin), lv.max_oi_strike ? ['Most open interest', html`${num(lv.max_oi_strike.strike, 0)} <span class="t-muted">(${compact(lv.max_oi_strike.total_oi)} contracts)</span>`] : null], 4)}
    <h3>Net dealer gamma by strike</h3><div class="chart-slot" data-chart="gexStrikes"></div>
    ${(g.profile || {}).spots ? html`<h3>Gamma profile across price</h3><div class="chart-slot" data-chart="gexProfile"></div><p class="asof">Net dealer gamma if the price moved to each level, everything else held. ${isNum(reg.flip_point) ? `It crosses zero near ${num(reg.flip_point)}.` : 'It does not cross zero within 12% of the price.'}</p>` : ''}
    ${nearTerm(g.near_term)}
    <h3>Dealer vanna and charm</h3>${kv([['Net vanna', html`${signedMoneyCompact(tot.net_vanna)} delta per vol point`], ['Net charm', html`${signedMoneyCompact(tot.net_charm)} delta per day`]], 2)}
    ${how(html`<p>The strike chart shows the strikes with the most gamma only, so they are not evenly spaced in price; the gold line is the current price.</p>`,
      html`<p>There is deliberately no vanna flip point. ${clean((g.convention || {}).represents || '')}</p>`,
      html`<p>Sign convention: ${g.assumption || ''} It is the common retail convention and it is sometimes wrong.</p>`,
      html`<p>Expiries used: ${(g.expiries_used || []).map(shortDate).join(', ')}. Rate ${num((g.inputs || {}).rate_pct, 2)}%.</p>`)}
    ${ask(sym, 'Ask Milo about dealer gamma', `What does dealer gamma positioning mean for ${sym} this week?`)}`;
}
function nearTerm(n) {
  if (!n) return '';
  if (!n.available) return note(n.reason);
  return html`<h3>Expiring within five days</h3>${kv([['Net gamma', signedMoneyCompact(n.net_gex)], ['Share of all gamma', pct(n.share_of_gross_pct)], ['Combined with later expiries', signedMoneyCompact(n.combined_net_gex)]])}${note(n.note)}`;
}
const signedMoneyCompact = (v) => (isNum(v) ? `${v < 0 ? '−' : '+'}$${compact(Math.abs(v))}` : 'n/a');
export function gexCharts(t) {
  const g = t.gex || {};
  const bs = (g.by_strike || []).slice().sort((a, b) => a.strike - b.strike);
  const pr = g.profile || {};
  return {
    gexStrikes: (w) => signedBars(bs.map((r) => ({ x: r.strike, v: r.net_gex, label: `${num(r.strike, 0)} strike: calls ${signedMoneyCompact(r.call_gex)}, puts ${signedMoneyCompact(r.put_gex)}, open interest ${compact((r.call_oi || 0) + (r.put_oi || 0))}` })), { w, h: 190, label: 'Net dealer gamma by strike', fmt: signedMoneyCompact, marker: { x: g.spot, text: 'Now' } }),
    gexProfile: (w) => xyChart([{ name: 'Net gamma', xs: pr.spots || [], ys: pr.net_gex || [], cls: 'main' }], { w, h: 220, label: 'Gamma profile across price', yfmt: signedMoneyCompact, xfmt: (x) => num(x, 0), markers: [{ x: g.spot, text: 'Now', cls: 'gold' }, ...(isNum(pr.flip_point) ? [{ x: pr.flip_point, text: 'Flip', cls: 'faint' }] : [])], fill: true }),
  };
}

/* ---------- flow ---------- */
export function flow(t, sym) {
  const f = t.flow || {};
  if (f.error) return empty('Flow is not available', clean(f.error));
  const v = f.volume || {}, oi = f.open_interest || {}, pm = f.premium || {}, np = f.new_positions || {};
  // each note is its own sentence: joined with spaces they ran together ("Mild call lean New positions skew put-side")
  const sentence = (n) => { const t = clean(n).trim(); return t ? `${capFirst(t)}${/[.!?]$/.test(t) ? '' : '.'}` : ''; };
  return html`<p><b>${capFirst(f.stance || '')}.</b> ${(f.notes || []).map(sentence).filter(Boolean).join(' ')}</p>
    ${kv([['Calls per 100 puts traded', isNum(v.calls) && v.puts ? num((v.calls / v.puts) * 100, 0) : 'n/a'], ['Put/call open interest', num(oi.put_call_ratio, 2)], ['Time value bought in calls', pct(pm.call_share_pct, 0)], ['New positions, calls share', pct(np.call_share_pct, 0)], ['Put minus call IV', signed((f.iv_skew || {}).put_minus_call_vol_pts, 1, ' pts')]], 3)}
    <p class="asof">"Premium" here is time value, not the whole price. ${clean(f.method || '')}</p>
    <h3>Net premium by strike</h3><div class="chart-slot" data-chart="flowStrikes"></div>
    ${(f.unusual || []).length ? html`<h3>${(f.activity_screen || {}).label || 'Most active contracts'}</h3><div class="tscroll"><table class="t"><thead><tr><th>Contract</th><th>Days</th><th>Volume</th><th>Open int.</th><th>Vol / OI</th><th>Premium</th><th>IV</th></tr></thead>
      <tbody>${f.unusual.slice(0, 10).map((u) => html`<tr><td>${num(u.strike, 0)} ${(u.type || '').toLowerCase()} ${u.moneyness || ''}${u.is_new_position ? ', new' : ''}</td><td>${num(u.dte, 0)}</td><td>${compact(u.volume)}</td><td>${compact(u.open_interest)}</td><td>${num(u.vol_oi_ratio, 1)}×</td><td>${usd(u.premium_total ?? u.premium)}</td><td>${(isNum(u.iv) ? pct(u.iv * 100) : 'n/a')}</td></tr>`)}</tbody></table></div>
      ${note(`${(f.activity_screen || {}).rule || ''} Cannot show: ${((f.activity_screen || {}).cannot_show || []).join('; ')}.`)}` : ''}
    ${t.options_brief && t.options_brief.available ? html`<h3>Options intelligence</h3>${kv(t.options_brief.items.map((i) => [i.label, html`${i.value} <span class="t-muted">${clean(i.note)}</span>`]), 2)}${note(t.options_brief.method)}` : ''}
    ${ask(sym, 'Ask Milo about the flow', `What is the options flow saying about ${sym}?`)}`;
}
export function flowCharts(t) {
  const bs = ((t.flow || {}).by_strike || []).slice().sort((a, b) => a.strike - b.strike);
  return { flowStrikes: (w) => signedBars(bs.map((r) => ({ x: r.strike, v: r.net_premium, label: `${num(r.strike, 0)}: calls ${usd(r.call_premium)}, puts ${usd(r.put_premium)}` })), { w, h: 170, label: 'Net premium by strike, calls minus puts', fmt: (v) => signedMoneyCompact(v), marker: { x: (t.quote || {}).price, text: 'Now' } }) };
}

/* ---------- delta and gamma ---------- */
export function greeksPanel(t, sym) {
  const gk = t.greeks || {};
  if (gk.error) return empty('Greeks are not available', clean(gk.error));
  const d = gk.delta || {}, g = gk.gamma || {};
  return html`<h3>Delta</h3><p>${clean(d.read || '')}</p>
    ${kv([['Net delta, shares', compact(d.net_delta_shares)], ['Net delta, dollars', signedMoneyCompact(d.net_delta_notional)], ['Dealer delta (DEX)', signedMoneyCompact(((t.gex || {}).totals || {}).net_dex)], ['Open interest', compact(d.total_open_interest)]], 4)}
    <h3>At-the-money greeks by expiry</h3><div class="tscroll"><table class="t"><thead><tr><th>Expiry</th><th>Days</th><th>Strike</th><th>Call delta</th><th>Put delta</th><th>Gamma</th><th>IV</th><th>Call decay a day</th></tr></thead>
      <tbody>${(gk.atm_greeks || []).map((r) => html`<tr><td>${shortDate(r.expiry)}</td><td>${r.dte}</td><td>${num((r.call || {}).strike, 0)}</td><td>${num((r.call || {}).delta, 2)}</td><td>${num((r.put || {}).delta, 2)}</td><td>${num((r.call || {}).gamma, 4)}</td><td>${atmIv(r)}</td><td>${usd((r.call || {}).theta_per_day, 2)}</td></tr>`)}</tbody></table></div>
    <h3>Gamma</h3><p>${clean(g.read || '')}</p>
    ${kv([['Peak gamma strike', html`${num(g.peak_gamma_strike, 0)} <span class="t-muted">(${signed(g.peak_gamma_distance_pct)})</span>`], ['Within 2% of the price', pct(g.gamma_within_2pct_share, 0)]], 2)}
    ${(g.by_expiry || []).length ? html`<div class="tscroll"><table class="t"><thead><tr><th>Expiry</th><th>Days</th><th>Share of gamma</th><th>Open interest</th></tr></thead><tbody>${g.by_expiry.map((r) => html`<tr><td>${shortDate(r.expiry)}</td><td>${r.dte}</td><td>${pct(r.share_pct, 0)}</td><td>${compact(r.open_interest)}</td></tr>`)}</tbody></table></div>` : ''}
    ${note((gk.second_order || {}).note)}`;
}

/* ---------- ideas: single options and strategies, with the budget ---------- */
const BUDGETS = [0, 100, 250, 500, 1000, 2500];
export function ideas(t, sym, budget) {
  const all = [...(t.naked_ideas || []).map((i) => Object.assign({ group: 'Buy calls or puts' }, i)), ...(t.strategy_ideas || []).map((i) => Object.assign({ group: 'Strategies' }, i))];
  const fits = all.filter((i) => i.fits_budget !== false), over = all.filter((i) => i.fits_budget === false);
  return html`<div class="budget"><p class="t-label">Most you'll risk on one contract</p>
      <div class="seg" role="group" aria-label="Budget">${BUDGETS.map((b) => html`<button type="button" data-v2-budget="${b}" aria-pressed="${(budget || 0) === b}">${b ? money(b, 0) : 'No limit'}</button>`)}</div>
      <form class="budget-own" data-v2-budget-form><label class="field field-sm"><span class="sr">Your own budget in dollars</span><input name="b" inputmode="numeric" placeholder="Your own" value="${budget && !BUDGETS.includes(budget) ? budget : ''}"></label><button class="btn btn-sm" type="submit">Use it</button></form></div>
    ${over.length ? html`<p class="asof">Over your budget: ${over.map((i) => i.name).join(', ')}.</p>` : ''}
    ${fits.length ? fits.map((i, n) => idea(i, n)) : empty('No idea fits', budget ? 'Nothing fits this budget. Raise it or choose No limit.' : 'The setup has no directional idea right now.')}
    <p class="asof">Example structures for this setup, sized to one contract at the mid. Model output, not a recommendation to trade. ${clean(t.disclaimer_area || '')}</p>
    ${ask(sym, 'Ask Milo about these ideas', `Which of these option ideas for ${sym} fits a two-to-eight-week swing, and why?`)}`;
}
function idea(i, n) {
  if (i.conceptual) return html`<article class="idea"><h3>${i.name}</h3><p>${clean(i.rationale || i.note || '')}</p></article>`;
  const debit = isNum(i.net_debit) || isNum(i.cost_for_one);
  const be = Array.isArray(i.breakeven) ? i.breakeven.map((b) => num(b)).join(' and ') : num(i.breakeven);
  const mp = i.max_profit === 'unlimited' ? 'No cap' : usd(i.profit_for_one ?? (isNum(i.max_profit) ? i.max_profit * 100 : null));
  const ml = usd(i.risk_for_one ?? (isNum(i.max_loss) ? Math.abs(i.max_loss) * 100 : null));
  return html`<article class="idea"><p class="t-label">${i.group}, ${i.structure || ''}${i.expiry ? `, ${shortDate(i.expiry)}, ${dayCount(i.dte)}` : ''}</p><h3>${i.name}</h3>
    <p>${clean(i.rationale || '')}</p>
    <p class="legs">${(i.legs || []).map((l) => `${l.action === 'SELL' ? 'Sell' : 'Buy'} ${num(l.strike, 0)} ${(l.type || '').toLowerCase()} at ${num(l.mid)}`).join(', ')}.</p>
    ${kv([[debit ? 'Cost for one' : 'Credit for one', usd(i.cost_for_one ?? i.credit_for_one ?? (isNum(i.net_debit) ? i.net_debit * 100 : isNum(i.net_credit) ? i.net_credit * 100 : null))], ['Most it can make', mp], ['Most it can lose', ml], ['Breakeven', be || 'n/a']], 4)}
    <div class="chart-slot" data-chart="idea${n}"></div>
    ${i.assignment_note ? note(i.assignment_note) : ''}${i.risk_plan ? note(`${i.risk_plan.invalidation || ''} ${i.risk_plan.sizing_note || ''}`) : ''}</article>`;
}
// payoff at expiry per position, the classic formula (charts.js payoffAt)
export function ideaCharts(t, spot) {
  const all = [...(t.naked_ideas || []), ...(t.strategy_ideas || [])].filter((i) => i.fits_budget !== false && !i.conceptual);
  const out = {};
  all.forEach((i, n) => {
    const legs = i.legs || [];
    if (!legs.length) return;
    const ks = legs.map((l) => l.strike);
    const lo = Math.min(spot * 0.8, ...ks) * 0.97, hi = Math.max(spot * 1.2, ...ks) * 1.03;
    const xs = Array.from({ length: 161 }, (_, j) => lo + (j / 160) * (hi - lo));
    const at = (p) => legs.reduce((a, l) => { const intr = (l.type || '').toUpperCase() === 'CALL' ? Math.max(p - l.strike, 0) : Math.max(l.strike - p, 0); return a + (l.action === 'SELL' ? -1 : 1) * (intr - l.mid) * (l.qty || 1) * 100; }, 0);
    out['idea' + n] = (w) => xyChart([{ name: 'At expiry', xs, ys: xs.map(at), cls: 'main' }], { w, h: 160, label: `${i.name} payoff at expiry`, yfmt: (v) => signedMoneyCompact(v), markers: [{ x: spot, text: 'Now', cls: 'gold' }], fill: true });
  });
  return out;
}

/* ---------- strike and entry, volatility context ---------- */
export function entry(t, sym) {
  const ep = t.entry_plan || {};
  const ivc = ep.iv_context || {}, vol = (t.technicals || {}).volatility || {};
  const volBlock = html`<h3>Volatility context</h3>${kv([['At-the-money IV', pct(ivc.atm_iv_pct)], ['Realised, 20 days', pct(ivc.realised_vol_20d_pct)], ['IV against realised', isNum(ivc.iv_to_realised_ratio) ? `${num(ivc.iv_to_realised_ratio, 2)}×` : 'n/a'], ['Realised vol, 10 / 20 / 30 / 60 days', `${num(vol.hv_10d, 1)} / ${num(vol.hv_20d, 1)} / ${num(vol.hv_30d, 1)} / ${num(vol.hv_60d, 1)}%`]], 2)}
    <p>${clean(ivc.verdict || '')} ${clean(ivc.guidance || '')}</p>${TR.historySlot('iv_verdict')}${note(vol.hv_trend_note)}${note(ivc.term_structure)}`;
  if (!ep.actionable) {
    return html`<p><b>${clean(ep.headline || 'No entry right now.')}</b> ${clean(ep.reason || '')}</p>
      ${(ep.reasoning || []).length ? html`<ul class="plain">${ep.reasoning.map((r) => html`<li>${clean(r)}</li>`)}</ul>` : ''}
      ${(ep.waiting_for || []).length ? html`<h3>Waiting for</h3><ul class="plain">${ep.waiting_for.map((w) => html`<li>${clean(w.condition)}: ${clean(w.then)}</li>`)}</ul>` : ''}${volBlock}`;
  }
  const r = ep.recommended || {}, og = ep.order_guidance || {}, tg = ep.target || {}, rk = ep.risk || {};
  return html`<p><b>${clean(ep.headline || '')}</b></p>
    ${kv([['Contract', `${num(r.strike, 0)} ${ep.direction === 'short' ? 'put' : 'call'}, ${shortDate(r.expiry)} (${dayCount(r.dte)})`], ['Limit price', html`${num(og.limit_price ?? r.entry_mid)}${og.never_pay_more_than ? html` <span class="t-muted">never above ${num(og.never_pay_more_than)}</span>` : ''}`], ['Cost per contract', usd(r.capital_per_contract)], ['Breakeven', num(r.breakeven)], ['If the target is hit', signed(r.return_at_target_pct, 0)], ['If IV drops 20%', signed(r.return_if_iv_drops_20pct, 0)]], 3)}
    ${(ep.entry_options || []).length ? html`<h3>Where to enter</h3><ul class="plain">${ep.entry_options.map((o) => html`<li><b>${capFirst(o.style || '')}.</b> ${clean(o.detail || '')} ${clean(o.confirmation || '')}</li>`)}</ul>` : ''}
    <h3>Target and risk</h3>${kv([['Target', html`${num(tg.target_price)} <span class="t-muted">(${signed(tg.move_required_pct)}, ${clean(tg.target_source || '')})</span>`], ['Stock stop', html`${num(rk.underlying_stop)} <span class="t-muted">${clean(rk.stop_basis || '')}</span>`], ['Typical time', isNum(tg.estimated_trading_days) ? `${tg.estimated_trading_days} sessions` : 'n/a']], 3)}
    <p>${clean(rk.invalidation || '')}</p>
    ${(ep.candidates || []).length ? html`<details class="more-inline"><summary>Candidate strikes, ranked</summary><div class="tscroll"><table class="t"><thead><tr><th>Rank</th><th>Strike</th><th>Expiry</th><th>Mid</th><th>Cost</th><th>Spread</th><th>Delta</th><th>Breakeven</th><th>At target</th><th>Flat</th></tr></thead>
      <tbody>${ep.candidates.map((c) => html`<tr><td>${c.rank}</td><td>${num(c.strike, 0)}</td><td>${shortDate(c.expiry)}</td><td>${num(c.entry_mid)}</td><td>${usd(c.cost_per_contract)}</td><td>${pct(c.spread_pct)}</td><td>${num(c.delta, 2)}</td><td>${num(c.breakeven)}</td><td>${signed(c.return_at_target_pct, 0)}</td><td>${signed(c.return_if_flat_pct, 0)}</td></tr>`)}</tbody></table></div></details>` : ''}
    ${(ep.warnings || []).map((w) => html`<p class="stale">${clean(w)}</p>`)}${note(og.note)}${(ep.assumptions || []).map(note)}
    ${volBlock}${ask(sym, 'Ask Milo about this entry', `Walk me through the suggested ${sym} entry and what would invalidate it.`)}`;
}

/* ---------- swing verdict and Optic's perspective ---------- */
export function verdict(t, sym) {
  const v = t.verdict || {}, c = t.cases || {};
  const s = score100(v.composite_score);
  return html`<p><b>${capFirst(v.stance || '')}, ${v.conviction || ''} conviction.</b> ${clean(v.summary || '')}</p>
    ${kv([['Composite', isNum(s) ? `${num(s, 0)} of 100` : 'n/a'], ['Signal agreement', pct(v.signal_agreement_pct, 0)]], 2)}
    ${TR.slot('composite')}
    <div class="tscroll"><table class="t"><thead><tr><th>Input</th><th>Score</th><th>Weight</th><th>Adds</th><th>Status</th></tr></thead>
      <tbody>${(v.breakdown || []).map((b) => html`<tr><td>${capFirst(b.component)}</td><td>${signed(b.score, 0, '')}</td><td>${num(b.weight_pct, 0)}%${Math.abs((b.nominal_weight_pct || 0) - (b.weight_pct || 0)) >= 1 ? html` <span class="t-muted">(of ${num(b.nominal_weight_pct, 0)}%)</span>` : ''}</td><td>${signed(b.contribution, 1, '')}</td><td>${b.unavailable ? clean(b.status_reason || 'Excluded') : 'Included'}</td></tr>`)}</tbody></table></div>
    <p class="asof">50 is no edge either way. Bullish at +30, leaning at +10 on the composite's own scale. ${clean(v.scale_note || '')}</p>
    <details class="more-inline"><summary>What each input measures</summary><ul class="plain">${(v.breakdown || []).map((b) => html`<li><b>${capFirst(b.component)}.</b> ${clean(b.measures || '')}</li>`)}</ul></details>
    ${t.why && t.why.available ? html`<h3>What's pulling hardest</h3><ul class="plain">${t.why.reasons.map((r) => html`<li><b class="${r.direction === 'up' ? 'up' : r.direction === 'down' ? 'down' : ''}">${clean(r.headline)}.</b> ${(r.evidence || []).map(clean).join('; ')}</li>`)}</ul>` : ''}
    ${c.available ? html`<h3>Optic's perspective</h3><div class="cases"><div><p class="case-h up">Bull case</p><ul class="plain">${c.bull.map((x) => html`<li><b>${clean(x.claim)}.</b> ${clean(x.detail)} <span class="t-muted">${x.source}</span></li>`)}</ul></div><div><p class="case-h down">Bear case</p><ul class="plain">${c.bear.map((x) => html`<li><b>${clean(x.claim)}.</b> ${clean(x.detail)} <span class="t-muted">${x.source}</span></li>`)}</ul></div></div>${note(c.balance)}` : ''}
    ${t.whats_next && t.whats_next.available ? html`<h3>What matters next</h3><ul class="plain">${[...(t.whats_next.today || []), ...(t.whats_next.this_week || [])].map((x) => html`<li><b>${clean(x.label)}.</b> ${clean(x.detail || '')}</li>`)}</ul>` : ''}
    ${((t.digest || {}).follow_ups || []).length ? html`<h3>Follow up</h3><div class="cluster">${t.digest.follow_ups.map((f) => miloButton(clean(f.question), { ask: f.prompt, context: `${sym} Dossier, Options`, symbol: sym, cls: 'btn-sm' }))}</div>` : ''}
    ${note(t.data_caveat)}`;
}

/* ---------- levels and momentum ---------- */
export function levels(t, sym) {
  const te = t.technicals || {}, st = t.structure || {}, fib = te.fibonacci || {}, ma = te.moving_averages || {};
  const sr = (te.support_resistance || []).slice().sort((a, b) => b.price - a.price);
  const vp = st.volume_profile || {}, pv = st.pivots || {}, cd = t.close_defence || {};
  return html`<p><b>The chart reads ${te.bias || 'n/a'}.</b> ${(te.reasons || []).map(clean).join('; ')}.</p>
    ${kv([['RSI (14)', html`${num((te.rsi || {}).value, 1)} <span class="t-muted">${(te.rsi || {}).state || ''}</span>`], ['MACD (12, 26, 9)', html`${num((te.macd || {}).macd, 2)} against ${num((te.macd || {}).signal, 2)} <span class="t-muted">${clean((te.macd || {}).event || '')}</span>`], ['Bollinger %B', num((te.bollinger || {}).percent_b, 0)], ['Value area', vp.available ? html`${num(vp.val)} to ${num(vp.vah)} <span class="t-muted">${vp.location || ''}</span>` : 'n/a'], ["Today's pivot", pv.available ? html`${num(pv.pp)} <span class="t-muted">R1 ${num(pv.r1)}, S1 ${num(pv.s1)}</span>` : 'n/a'], ['Expected 2-week range', `±${num((te.volatility || {}).expected_2w_move_pct, 1)}%`]], 3)}
    ${cd.available ? html`<h3>Close defence</h3><p>To keep the ${cd.direction === 'up' ? 'up' : 'down'} leg, it needs to ${clean(cd.requirement || '')}. Losing it breaks ${clean(cd.consequence || '')}. Cushion ${pct(cd.cushion_pct, 2)}.</p>` : ''}
    <h3>Support and resistance</h3><div class="tscroll"><table class="t"><thead><tr><th>Price</th><th>Role</th><th>Distance</th><th>Strength</th><th>Touches</th><th>Last touch</th></tr></thead>
      <tbody>${sr.map((l) => html`<tr><td>${num(l.price)}</td><td>${capFirst(l.role)}</td><td>${signed(l.distance_pct)}</td><td>${num(l.strength, 0)}</td><td>${l.touches}</td><td>${l.last_touch_bars_ago} bars ago</td></tr>`)}</tbody></table></div>
    <h3>Fibonacci, ${fib.direction || ''} from ${num(fib.anchor_low)} to ${num(fib.anchor_high)}</h3><div class="tscroll"><table class="t"><thead><tr><th>Level</th><th>Price</th><th>Distance</th><th>Role</th></tr></thead>
      <tbody>${(fib.levels || []).map((l) => html`<tr><td>${l.label}${l.is_golden ? ' (golden zone)' : ''}</td><td>${num(l.price)}</td><td>${signed(l.distance_pct)}</td><td>${capFirst(l.role || '')}</td></tr>`)}</tbody></table></div>
    <h3>Moving averages</h3><div class="tscroll"><table class="t"><thead><tr><th>Average</th><th>Value</th><th>Distance</th><th>Slope, 10 days</th></tr></thead>
      <tbody>${Object.entries(ma).map(([k, m]) => html`<tr><td>${k.toUpperCase()}</td><td>${num(m.value)}</td><td>${signed(m.distance_pct)}</td><td>${signed(m.slope_10d_pct)}</td></tr>`)}</tbody></table></div>
    ${momentum(t)}`;
}

/* ---------- RSI and MACD over the last 70 sessions: the classic swing page's momentum row (owner, 2026-10-20:
   "include the RSI and MACD charts from the classic version") ---------- */
const MOMENTUM_BARS = 70;   // the classic MACD_WINDOW
const RSI_SIGNAL = 9;       // the same length as the MACD's signal, so the two panels compare
const tail = (a, n) => (Array.isArray(a) ? a.slice(-n) : []);
const smaOf = (v, n) => v.map((_, i) => { if (i < n - 1) return null; let sum = 0; for (let j = i - n + 1; j <= i; j++) { if (!Number.isFinite(v[j])) return null; sum += v[j]; } return sum / n; });

/** The latest crossing of a fast line over its signal in a window, and how many bars back it was. */
export function lastCross(a, b) {
  for (let i = a.length - 1; i > 0; i--) {
    if (![a[i - 1], b[i - 1], a[i], b[i]].every(Number.isFinite)) continue;
    const was = a[i - 1] - b[i - 1], now = a[i] - b[i];
    if ((was <= 0 && now > 0) || (was >= 0 && now < 0)) return { index: i, bullish: now > 0, barsAgo: a.length - 1 - i };
  }
  return null;
}

/** The last 70 daily RSI and MACD readings with their dates, from the server's series; null when the series and
 * the dates do not line up (a reading is never placed on the wrong day). */
export function momentumData(t) {
  const te = t.technicals || {}, dates = (te.price_series || {}).dates || [];
  const rs = (te.rsi || {}).series, ms = (te.macd || {}).series || {};
  const n = Math.min(MOMENTUM_BARS, dates.length);
  const out = { n, dates: tail(dates, n), rsi: null, macd: null };
  if (Array.isArray(rs) && rs.length === dates.length && n > 20) {
    const v = tail(rs, n), sig = tail(smaOf(rs, RSI_SIGNAL), n);
    out.rsi = { v, sig, cross: lastCross(v, sig) };
  }
  if (['macd', 'signal', 'hist'].every((k) => Array.isArray(ms[k]) && ms[k].length === dates.length) && n > 20) {
    const v = tail(ms.macd, n), sig = tail(ms.signal, n);
    out.macd = { v, sig, hist: tail(ms.hist, n), cross: lastCross(v, sig) };
  }
  return out.rsi || out.macd ? out : null;
}

// the classic panels' read of a crossing, word for word: has momentum turned, and how recently
export function crossLine(cross, line, sig, dates, what) {
  const gap = line[line.length - 1] - sig[sig.length - 1];
  const prev = line.length > 1 ? line[line.length - 2] - sig[sig.length - 2] : gap;
  const widening = Math.abs(gap) > Math.abs(prev);
  if (!cross) return `No crossover in the last ${line.length} days: ${what} has stayed ${gap >= 0 ? 'above' : 'below'} its signal line throughout, so momentum has not changed direction in this window. The gap is currently ${widening ? 'widening' : 'narrowing'}${widening ? '' : ', which is what precedes a cross'}.`;
  const when = cross.barsAgo === 0 ? 'on the latest day' : `${cross.barsAgo} ${cross.barsAgo === 1 ? 'day' : 'days'} ago`;
  const date = dates[cross.index] ? ` (${shortDate(dates[cross.index])})` : '';
  return `Last crossover: ${what} crossed ${cross.bullish ? 'above' : 'below'} its signal line ${when}${date}. A ${cross.bullish ? 'bullish' : 'bearish'} momentum shift, marked on the chart. The gap has ${widening ? 'widened since' : 'narrowed since'}, meaning the shift is ${widening ? 'still building' : 'losing conviction and could cross back'}.`;
}

function momentum(t) {
  const m = momentumData(t);
  if (!m) return '';
  const te = t.technicals || {}, r = te.rsi || {}, mc = te.macd || {};
  return html`<h3>Momentum, last ${m.n} days</h3><div class="momentum">
    ${m.rsi ? html`<div class="mo"><p class="mo-h"><b>RSI (14)</b> <span class="t-muted">${num(r.value, 1)} out of 100: ${r.state || 'n/a'}</span></p>
      <p class="legend-line"><span><i></i>RSI (14)</span><span><i class="o2"></i>Signal, ${RSI_SIGNAL}-day average</span></p>
      <div class="chart-slot" data-chart="rsi"></div><p class="asof">${crossLine(m.rsi.cross, m.rsi.v, m.rsi.sig, m.dates, 'RSI')}</p></div>` : ''}
    ${m.macd ? html`<div class="mo"><p class="mo-h"><b>MACD (12, 26, 9)</b> <span class="t-muted">${num(mc.macd, 2)} against ${num(mc.signal, 2)}: ${mc.state || 'n/a'}</span></p>
      <p class="legend-line"><span><i></i>MACD</span><span><i class="o2"></i>Signal</span><span><i class="kbs"></i><i class="kbr"></i>Histogram, MACD less signal</span></p>
      <div class="chart-slot" data-chart="macd"></div><p class="asof">${crossLine(m.macd.cross, m.macd.v, m.macd.sig, m.dates, 'MACD')}</p></div>` : ''}
  </div>
  ${how(html`<p>RSI (14) is Wilder's relative strength index on daily closes, from 0 to 100. Above 70 is overbought, below 30 oversold; 50 divides bullish from bearish momentum. Its signal line is a ${RSI_SIGNAL}-day average of RSI itself, the same length the MACD uses for its signal. RSI crossing its own average is the earlier, noisier read on a momentum turn; it usually leads the MACD cross.</p>`,
    html`<p>MACD (12, 26, 9) is the 12-day exponential average of the close less the 26-day one; the signal is a 9-day exponential average of MACD, and the histogram is the gap between them.</p>`)}`;
}

export function levelCharts(t) {
  const m = momentumData(t);
  if (!m) return {};
  const ser = (vals) => m.dates.map((d, i) => ({ d, c: vals[i] }));
  const pin = (x, vals, unit) => (x ? [{ i: x.index, v: vals[x.index], dir: x.bullish ? 'up' : 'down', text: `${x.bullish ? 'Bullish' : 'Bearish'} cross${x.barsAgo ? `, ${x.barsAgo} ${unit}${x.barsAgo === 1 ? '' : 's'} ago` : ', latest'}` }] : []);
  const last = (a) => a[a.length - 1];
  // round axis values through zero (MACD's own scale is the stock's price units)
  const roundTicks = (vals) => {
    const v = vals.filter(Number.isFinite), lo = Math.min(0, ...v), hi = Math.max(0, ...v), raw = Math.max(Math.abs(lo), Math.abs(hi)) / 3 || 1;
    const p = 10 ** Math.floor(Math.log10(raw)), f = raw / p, step = (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p;
    const out = []; for (let k = Math.ceil(lo / step); k * step <= hi; k++) out.push(k * step);
    return out;
  };
  const out = {};
  if (m.rsi) out.rsi = (w) => lineChart(ser(m.rsi.v), { measure: 'points', msUnit: ' pts', w, h: 200, label: 'RSI (14)', dp: 1, domain: [10, 90], ticksAt: [30, 50, 70],
    refs: [{ v: 70, cls: 'band' }, { v: 50, cls: 'mid' }, { v: 30, cls: 'band' }], overlays: [{ values: m.rsi.sig, cls: 'o2' }], pins: pin(m.rsi.cross, m.rsi.v, 'day'),
    tipMore: (i) => (Number.isFinite(m.rsi.sig[i]) ? `Signal ${num(m.rsi.sig[i], 1)}` : ''),
    summary: `RSI (14) over the last ${m.n} days, from ${num(m.rsi.v[0], 1)} on ${fullDate(m.dates[0])} to ${num(last(m.rsi.v), 1)} on ${fullDate(last(m.dates))}, against its signal at ${num(last(m.rsi.sig), 1)}. ${crossLine(m.rsi.cross, m.rsi.v, m.rsi.sig, m.dates, 'RSI')}` });
  if (m.macd) out.macd = (w) => lineChart(ser(m.macd.v), { measure: 'points', w, h: 200, label: 'MACD (12, 26, 9)', dp: 2, ticksAt: roundTicks([...m.macd.v, ...m.macd.sig, ...m.macd.hist]), refs: [{ v: 0, cls: 'mid' }], bars: m.macd.hist,
    overlays: [{ values: m.macd.sig, cls: 'o2' }], pins: pin(m.macd.cross, m.macd.v, 'day'),
    tipMore: (i) => `Signal ${num(m.macd.sig[i], 2)}, histogram ${signed(m.macd.hist[i], 2, '')}`,
    summary: `MACD over the last ${m.n} days, ${num(last(m.macd.v), 2)} against a signal of ${num(last(m.macd.sig), 2)} on ${fullDate(last(m.dates))}. ${crossLine(m.macd.cross, m.macd.v, m.macd.sig, m.dates, 'MACD')}` });
  return out;
}

/* ---------- how an option's value moves (the classic Greeks lab) ---------- */
function ncdf(x) { const t = 1 / (1 + 0.2316419 * Math.abs(x)); const d = 0.3989423 * Math.exp(-x * x / 2); const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))); return x > 0 ? 1 - p : p; }
export function bs(kind, S, K, T, r, v) {
  if (T <= 0) return { price: Math.max(kind === 'call' ? S - K : K - S, 0), delta: kind === 'call' ? (S > K ? 1 : 0) : (S < K ? -1 : 0), gamma: 0 };
  const d1 = (Math.log(S / K) + (r + v * v / 2) * T) / (v * Math.sqrt(T)), d2 = d1 - v * Math.sqrt(T);
  const price = kind === 'call' ? S * ncdf(d1) - K * Math.exp(-r * T) * ncdf(d2) : K * Math.exp(-r * T) * ncdf(-d2) - S * ncdf(-d1);
  return { price, delta: kind === 'call' ? ncdf(d1) : ncdf(d1) - 1, gamma: Math.exp(-d1 * d1 / 2) / (Math.sqrt(2 * Math.PI) * S * v * Math.sqrt(T)) };
}
export function labDefaults(t) {
  const S = (t.quote || {}).price;
  const iv = ((t.vol_surface || {}).iv30 || {}).iv_pct || ((t.iv_hv || {}).iv30) || 30;
  return { kind: 'call', dte: 30, iv: Math.round(iv), S, r: (t.rate || {}).rate || 0.04 };
}
export function lab(L) {
  const step = L.S > 500 ? 5 : L.S > 100 ? 1 : L.S > 20 ? 0.5 : 0.1;
  const rnd = (x) => Math.round(x / step) * step;
  const atm = rnd(L.S);
  const v = L.iv / 100, T = L.dte / 365;
  const now = bs(L.kind, L.S, atm, T, L.r, v), tomorrow = bs(L.kind, L.S, atm, Math.max(0, T - 1 / 365), L.r, v);
  const last7 = bs(L.kind, L.S, atm, Math.min(T, 7 / 365), L.r, v);
  const g5 = bs(L.kind, L.S, atm, 5 / 365, L.r, v);
  return html`<div class="lab-controls">
      <div class="seg" role="group" aria-label="Kind"><button type="button" data-v2-lab="kind:call" aria-pressed="${L.kind === 'call'}">Call</button><button type="button" data-v2-lab="kind:put" aria-pressed="${L.kind === 'put'}">Put</button></div>
      <div class="seg" role="group" aria-label="Days to expiry">${[7, 14, 30, 45, 60].map((d) => html`<button type="button" data-v2-lab="dte:${d}" aria-pressed="${L.dte === d}">${d} days</button>`)}</div>
      <label class="field field-sm"><span class="t-label">IV</span><input type="number" min="5" max="200" value="${L.iv}" data-v2-lab-iv aria-label="Implied volatility, percent"></label></div>
    <p>An at-the-money ${L.kind} (the ${num(atm, step < 1 ? 1 : 0)} strike) with ${L.dte} days left at ${L.iv}% IV is worth about ${money(now.price)} a share (${money(now.price * 100, 0)} a contract). It loses about ${money(now.price - tomorrow.price)} a day now; ${L.dte > 7 ? `${num((last7.price / now.price) * 100, 0)}% of its value is still left with 7 days to go, and that last stretch is where decay is fastest` : 'all of its time value goes in the days left'}. Its delta is ${num(now.delta, 2)}, and at 5 days its gamma is ${num(now.gamma ? g5.gamma / now.gamma : 0, 1)} times what it is now.</p>
    <div class="chart-slot" data-chart="labDecay"></div><div class="chart-slot" data-chart="labDelta"></div>
    ${how(html`<p>Black-Scholes with Optic's rate, no dividends, the price held at ${num(L.S)}. A teaching model: real contracts carry their own implied volatility, skew and early exercise.</p>`)}`;
}
export function labCharts(L) {
  const step = L.S > 500 ? 5 : L.S > 100 ? 1 : L.S > 20 ? 0.5 : 0.1;
  const rnd = (x) => Math.round(x / step) * step;
  const ks = [['In the money', rnd(L.S * (L.kind === 'call' ? 0.95 : 1.05))], ['At the money', rnd(L.S)], ['Out of the money', rnd(L.S * (L.kind === 'call' ? 1.05 : 0.95))]];
  const days = Array.from({ length: 61 }, (_, i) => 60 - i);
  const prices = Array.from({ length: 61 }, (_, i) => L.S * (0.85 + i * 0.005));
  const v = L.iv / 100;
  return {
    labDecay: (w) => xyChart(ks.map(([n, k], j) => ({ name: `${n} (${num(k, 0)})`, xs: days.map((d) => -d), ys: days.map((d) => bs(L.kind, L.S, k, d / 365, L.r, v).price), cls: ['alt', 'main', 'faint'][j] })), { w, h: 200, label: 'Option value as expiry approaches', xfmt: (x) => `${num(-x, 0)}d`, yfmt: (y) => money(y) }),
    labDelta: (w) => xyChart([{ name: `Delta, ${L.dte} days`, xs: prices, ys: prices.map((p) => bs(L.kind, p, rnd(L.S), L.dte / 365, L.r, v).delta), cls: 'main' }, { name: 'Delta, 5 days', xs: prices, ys: prices.map((p) => bs(L.kind, p, rnd(L.S), 5 / 365, L.r, v).delta), cls: 'alt' }], { w, h: 200, label: 'Delta across price', yfmt: (y) => num(y, 2), markers: [{ x: L.S, text: 'Now', cls: 'gold' }] }),
  };
}

/* ---------- swing setups (Classic parity B6b): the tool itself is pages/setups.js, one node put in this slot ---------- */
export function swingSetups(t, sym) {
  return html`<p class="section-sub">Bullish and bearish entry rules on completed candles, each with its context, setup, trigger and invalidation. For review: nothing here places a trade, and every rule is a hypothesis to test, not a strategy known to work.</p>
    ${TR.slot('setups')}
    <div data-ss-slot></div>
    ${ask(sym, 'Ask Milo about the setups', `Is there a swing setup worth acting on in ${sym}, and what would invalidate it?`)}`;
}

/* ---------- chart patterns, each beside what followed it (Classic's renderPatterns and baseRateCell) ---------- */
/** What followed a pattern across 43 names and ten years, 21 sessions on: its hit rate against 50%, and its edge
 *  over the stock's own drift. A pattern still forming has nothing to measure. */
export function baseRate(rates, name, state) {
  const entry = ((rates && rates.patterns) || {})[`${name}|${state}`], h = entry && entry.h21;
  if (!h || h.hit_rate === null || h.hit_rate === undefined) return { text: `too few to measure${entry ? ` (${num(entry.sample, 0)})` : ''}`, tone: 'none' };
  // against 50%, not zero: the question is whether the conventional reading beat a coin toss
  return { text: `${num(h.hit_rate * 100, 0)}% of ${num(h.n, 0)}`, edge: `${h.edge_mean_pct > 0 ? '+' : ''}${num(h.edge_mean_pct, 2)}% against its own drift`, tone: h.hit_rate > 0.53 ? 'up' : h.hit_rate < 0.47 ? 'down' : 'flat' };
}
const rateCell = (r) => html`<span class="pat-rate ${r.tone}">${r.text}${r.edge ? html` <span class="t-muted">${r.edge}</span>` : ''}</span>`;
export function ratesMissing(rates) {
  if (!rates) return 'Base rates are on their way, so the measured column is empty for now. With none cached, the server builds them from ten years of daily bars first, which takes about ninety seconds, and the column fills in when they land.';
  if (rates.failed) return 'Base rates could not be loaded, so the measured column is empty. They are asked for again when the page is reloaded.';
  return `${clean(rates.reason || 'Base rates are not available.')} The measured column stays empty until they are.`;
}
export function patterns(t, sym, extra) {
  const p = t.patterns || {}, rates = extra.rates, se = extra.seasonality, rp = extra.relperf;
  const loading = extra.loading === undefined;
  const pats = !p.available ? html`<p class="t-muted">${clean(p.reason || 'Not enough history to read structure.')}</p>` : html`
    <p class="section-sub">Structure, candles and zones read mechanically off the daily bars, each beside what actually happened afterwards across 43 names and ten years. The two often disagree, and this panel does not resolve that for you.</p>${TR.historySlot('candles')}
    ${(p.chart_patterns || []).length ? html`<h3>Structure</h3><div class="tscroll"><table class="t pat-t"><thead><tr><th class="l">Pattern</th><th class="l">State</th><th>Conventional reading held, 21 sessions</th></tr></thead>
      <tbody>${p.chart_patterns.slice().reverse().map((x) => { const st = x.confirmed === null ? 'candle' : x.confirmed ? 'confirmed' : 'unconfirmed';
        return html`<tr><td class="l"><b>${x.name}</b><span class="t-muted pat-sub">${shortDate(x.start_date)} to ${shortDate(x.end_date)}, ${num(x.span_bars, 0)} bars${isNum(x.amplitude_atr) ? `, ${num(x.amplitude_atr, 1)} times a typical day's range` : ''}</span><span class="pat-sub">Conventionally: ${x.conventional}</span></td>
          <td class="l">${x.confirmed === null ? 'Forming' : x.confirmed ? `Confirmed${x.confirmed_on ? ` ${shortDate(x.confirmed_on)}` : ''}` : 'Not confirmed'}</td>
          <td>${x.confirmed === null ? html`<span class="t-muted">nothing to measure until it resolves</span>` : rateCell(baseRate(rates, x.name, st))}</td></tr>`; })}</tbody></table></div>
      ${note('A reversal pattern is only confirmed once a close has cleared its neckline, and cleared it promptly; a crossing months later is a coincidence, not a resolution. Confirmation is the whole difference on this data: confirmed structures land between 51% and 55%, unconfirmed ones at or below 50%. A pattern that fails to confirm is not a weaker version of the same signal, it is the trend carrying on.')}`
    : html`<p class="t-muted">No structural pattern currently passes the size, prior-move and freshness tests over the last year.</p>`}
    ${(p.zones || []).length ? html`<h3>Supply and demand</h3><div class="tscroll"><table class="t pat-t"><thead><tr><th class="l">Zone</th><th>Range</th><th>From the price</th></tr></thead>
      <tbody>${p.zones.map((z) => html`<tr><td class="l"><b>${z.side === 'supply' ? 'Supply' : 'Demand'} zone</b><span class="t-muted pat-sub">Based ${shortDate(z.formed)}, left ${shortDate(z.left_on)} on a move of ${num(z.departure_atr, 1)} times a typical day's range over ${num(z.base_bars, 0)} bars of base</span><span class="pat-sub">${z.side === 'supply' ? 'Sellers were waiting here and price could not hold above it.' : 'Buyers were waiting here and price could not stay below it.'}</span></td>
        <td>${num(z.bottom, 2)} to ${num(z.top, 2)}</td><td class="${dir(z.distance_pct)}">${signed(z.distance_pct, 1)}</td></tr>`)}</tbody></table></div>
      ${note(`A zone is not the same thing as support: support is a price that held; a zone is a price where one side was so outnumbered that price could not stay there. A base no wider than ${num((p.tolerances || {}).base_max_atr, 1)} times a typical day's range, then a departure of at least ${num((p.tolerances || {}).departure_atr, 1)} times it within 4 bars.${p.zones_out_of_horizon ? ` ${p.zones_out_of_horizon} further zone${p.zones_out_of_horizon === 1 ? ' is' : 's are'} too far from the price to be reached in ${p.zone_horizon_bars} sessions and not listed.` : ''}`)}` : ''}
    ${(p.candles || []).length ? html`<h3>Recent candles</h3><div class="tscroll"><table class="t pat-t"><thead><tr><th class="l">Bar</th><th class="l">Direction</th><th>That direction held, 21 sessions</th></tr></thead>
      <tbody>${p.candles.slice(0, 6).map((c) => html`<tr><td class="l"><b>${c.name}</b><span class="t-muted pat-sub">${shortDate(c.date)}, ${c.bar_offset === 0 ? 'the latest bar' : `${num(c.bar_offset, 0)} bars ago`}. ${clean(c.note)}</span><span class="pat-sub">Conventionally: ${c.conventional}</span></td>
        <td class="l ${c.direction === 'bullish' ? 'up' : c.direction === 'bearish' ? 'down' : ''}">${capFirst(c.direction)}</td><td>${rateCell(baseRate(rates, c.name, 'candle'))}</td></tr>`)}</tbody></table></div>
      ${note('Every candlestick pattern here measures between 46% and 51% on samples of two to twelve thousand. That is a coin toss, and it is the most useful thing this panel can tell you about them: they describe what the bar did, and on this evidence they do not forecast what the next twenty do.')}` : ''}
    ${how(html`<p>${clean(p.method || '')}</p>${rates && rates.available ? html`<p>Base rates: ${clean(rates.method || '')} Cached, ${num(rates.cache_age_days || 0, 0)} days old.</p>` : html`<p>${ratesMissing(rates)}</p>`}`)}
    ${rates && rates.available ? '' : html`<p class="asof" role="status">${loading ? 'Loading the base rates…' : ratesMissing(rates)}</p>`}`;
  return html`${pats}
    ${rp && rp.available ? html`<h3>Relative performance</h3><p>${clean(rp.headline)}</p>${note(rp.method)}` : ''}
    ${se && se.monthly ? html`<h3>Seasonality, ${num(se.years, 0)} years</h3><div class="tscroll"><table class="t"><thead><tr><th>Month</th><th>Average</th><th>Median</th><th>Up years</th><th>Against baseline</th><th>Reading</th></tr></thead>
      <tbody>${se.monthly.rows.map((m) => html`<tr><td>${m.short}</td><td>${signed(m.raw.mean)}</td><td>${signed(m.raw.median)}</td><td>${num(m.raw.hit_rate, 0)}%</td><td>${signed(m.raw.vs_baseline)}</td><td>${m.raw.verdict}</td></tr>`)}</tbody></table></div>
      ${note(`${se.significant_count} reading${se.significant_count === 1 ? '' : 's'} clear the significance test. "Noise" means the average could be chance.`)}` : ''}
    ${ask(sym, 'Ask Milo about the patterns', `Do any of ${sym}'s chart patterns have a measured edge, and what does the base rate say?`)}`;
}
void fullDate; void dir; void raw; void icon;
