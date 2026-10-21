// The Overview's deeper research (Classic parity B6a, 2026-10-21; Classic app.js:11706-12108, 17114-17175,
// 17471-17720, 17884-18200). Classic's calculations and analytical wording, laid out the v2 way:
// - "What to look at next": the dates coming up, the research steps, and what has been moving the price.
// - "Advanced research": Optic's short-term read (the Pulse inputs), the Optic Score on both horizons, all eighteen
//   key statistics, one reading from each tab, and how the page is built. It opens at the Advanced level and is one
//   press away below it (sections.js levels).
// Everything here comes from payloads the Overview already loads (/api/ticker, /api/longterm, /api/fair-value,
// /api/stage) by fixed rules. No model is called, and an Ask Milo action only drafts a question.
import { html } from '../core/dom.js';
import { num, signed, money, compact, clean, capFirst, shortDate, ago, isNum, score100 } from '../core/format.js';
import { how } from '../ui/states.js';
import { term } from '../ui/term.js';
import { button as miloButton } from '../ui/milo.js';
import { hrefFor } from '../nav.js';
import { valuationRead } from './thesis.js';

const g = (o, ...ks) => ks.reduce((x, k) => (x && typeof x === 'object' ? x[k] : undefined), o);
const fin = (v) => typeof v === 'number' && Number.isFinite(v);
export const convictionWords = (v) => { const w = String(v || '').trim().toLowerCase(); return !w ? '' : w === 'none' ? 'no conviction' : `${w} conviction`; };
const TAB = { chart: 'Chart', swing: 'Options', long: 'Investing', earnings: 'Earnings', financials: 'Financials', news: 'News', overview: 'Overview' };

/* ---------------- readings ---------------- */
/** The share price over the series shown (Classic's ovPriceRead): the change, the last three months, and the distance
 *  from the period's highest close. */
export function priceRead(pts) {
  const close = (pts || []).map((p) => p.c).filter(fin);
  if (close.length < 20) return null;
  const last = close[close.length - 1];
  return { yr: (last / close[0] - 1) * 100, m3: close.length > 64 ? (last / close[close.length - 64] - 1) * 100 : null, off: (last / Math.max(...close) - 1) * 100 };
}
/** The next earnings date and the days to it, from the news block or, failing that, the earnings history. */
export function earningsNext(t, today = new Date()) {
  const news = g(t, 'news') || {};
  if (news.earnings_date && fin(news.days_to_earnings)) return { date: news.earnings_date, days: news.days_to_earnings };
  const up = (g(t, 'company', 'earnings_history', 'upcoming') || [])[0];
  const m = up && String(up.date || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const then = Date.UTC(+m[1], +m[2] - 1, +m[3]), now = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return { date: up.date.slice(0, 10), days: Math.round((then - now) / 86400000) };
}

/** What is working for the company and against it (Classic's ovFactors): only what the payload shows, never ranked by
 *  importance, four of each at most. Each names the tab that holds its evidence. */
export function factors(t, { lt = null, stars = null, price = null, fund = false, today } = {}) {
  const fn = g(t, 'company', 'financials') || {}, gr = fn.growth || {}, bs = fn.balance_sheet || {}, q = g(t, 'quote') || {};
  const news = g(t, 'news') || {}, si = g(t, 'company', 'short_interest') || {}, ow = g(t, 'company', 'ownership') || {};
  const eh = g(t, 'company', 'earnings_history') || {}, sc = g(t, 'sector_confirm') || {};
  const st = stars && stars.available ? stars : null;
  const net = fin(g(fn, 'margins', 'net_pct')) ? fn.margins.net_pct : fin(q.profit_margin) ? q.profit_margin * 100 : null;
  const pos = [], neg = [];
  if (fn.available && fin(gr.revenue_yoy_pct) && gr.revenue_yoy_pct >= 1) pos.push({ text: `Revenue grew ${num(gr.revenue_yoy_pct, 1)}% in the latest fiscal year`, view: 'financials' });
  if (fin(net) && net > 0) pos.push({ text: `Profitable: about ${num(net, 0)} cents of profit per dollar of sales`, view: 'financials' });
  if (eh.available && eh.sample_size >= 4 && eh.beat_count > eh.sample_size / 2) pos.push({ text: `Beat analysts' earnings estimates in ${eh.beat_count} of the last ${eh.sample_size} quarters`, view: 'earnings' });
  if (fin(bs.net_cash) && bs.net_cash > 0) pos.push({ text: `Holds more cash than debt (${compact(bs.net_cash)} net cash)`, view: 'financials' });
  if (ow.available && ow.insider_signal === 'buying') pos.push({ text: 'Company insiders bought more shares than they sold over six months', view: 'financials' });
  if (st && st.stars >= 4) pos.push({ text: `Optic star rating ${st.stars} of 5: ${String(st.word || '').toLowerCase()}`, view: 'long' });
  if (price && price.yr >= 5) pos.push({ text: `Share price up ${num(price.yr, 0)}% over the period shown`, view: 'chart' });
  if (sc.available && /outperform|leading|ahead/i.test(String(sc.rs_vs_sector_label || ''))) pos.push({ text: `Ahead of its sector over the last ${num(sc.window_sessions || 21, 0)} sessions` });

  const ne = earningsNext(t, today), days = ne ? ne.days : null;
  if (ne && fin(days) && days >= 0 && days <= 45) neg.push({ text: `Earnings report on ${shortDate(ne.date)}, in ${days} day${days === 1 ? '' : 's'}`, why: 'Results and guidance can move the price sharply in either direction.', view: 'earnings' });
  // the price against its own history, once, and not beside a star rating that already says it
  const val = fund || (st && (st.stars >= 4 || st.stars <= 2)) ? null : valuationRead(lt);
  if (val && val.prem >= 20) neg.push({ text: `Priced above its own history: ${num(val.cur, 1)} times earnings against a ${val.years}-year average of ${num(val.med, 1)}`, why: 'A strong business can still be an expensive stock. A higher multiple means more good news is already in the price, so a disappointment tends to cost more.', view: 'long' });
  else if (val && val.prem <= -20) pos.push({ text: `Priced below its own history: ${num(val.cur, 1)} times earnings against a ${val.years}-year average of ${num(val.med, 1)}`, view: 'long' });
  if (fin(net) && net < 0) neg.push({ text: 'The company lost money over the latest period', why: 'Losses are paid for from cash, borrowing or new shares until the business turns a profit.', view: 'financials' });
  if (fn.available && fin(gr.revenue_yoy_pct) && gr.revenue_yoy_pct <= -1) neg.push({ text: `Revenue fell ${num(Math.abs(gr.revenue_yoy_pct), 1)}% in the latest fiscal year`, why: 'Falling sales make it harder to grow profit.', view: 'financials' });
  if (fn.available && fin(gr.net_income_yoy_pct) && gr.net_income_yoy_pct <= -1) neg.push({ text: `Net income fell ${num(Math.abs(gr.net_income_yoy_pct), 1)}% in the latest fiscal year`, why: 'One-off gains and charges move profit more than sales, so check the statements before reading much into it.', view: 'financials' });
  if (fin(bs.net_cash) && bs.net_cash < 0 && fin(net) && net < 0) neg.push({ text: `Owes ${compact(-bs.net_cash)} more than it holds in cash while losing money`, why: 'Debt has to be paid or refinanced whether or not the business recovers.', view: 'financials' });
  if (st && st.stars <= 2) neg.push({ text: `Optic star rating ${st.stars} of 5: ${String(st.word || '').toLowerCase()}`, why: "Optic's fair-value model places the price above the range it treats as usual for this company. A model estimate, not a verdict.", view: 'long' });
  if (si.available && si.squeeze_potential && !/^low/i.test(String(si.squeeze_potential)) && fin(si.percent_of_float)) neg.push({ text: `${num(si.percent_of_float * 100, 1)}% of the tradable shares are sold short`, why: 'Many investors are betting the price will fall, and short sellers buying back can also cause sudden rises.', view: 'financials' });
  if (sc.available && /lag/i.test(String(sc.rs_vs_sector_label || ''))) neg.push({ text: `Has lagged its sector over the last ${num(sc.window_sessions || 21, 0)} sessions`, why: sc.conflict || 'Peers in the same industry have done better over the same weeks.' });
  if (g(t, 'gex', 'regime', 'state') === 'negative') neg.push({ text: 'Options positioning may amplify price swings', why: "Under Optic's model of how options dealers hedge, their trading could add to moves in either direction. An assumption, not reported positions.", view: 'swing' });
  if (String(news.overall_tone || '').includes('bear')) neg.push({ text: 'Recent headlines lean negative', why: `Scored from ${num(news.article_count || 0, 0)} headlines by a fixed word list. It measures tone, not whether the news is true or important.`, view: 'news' });
  if (price && price.off <= -20) neg.push({ text: `Trading ${num(Math.abs(price.off), 0)}% below its highest close of the period`, why: 'A long fall can reflect a real change in the business, or a market that has moved on from it.', view: 'chart' });
  return { pos: pos.slice(0, 4), neg: neg.slice(0, 4) };
}

/** What has been moving the stock, as far as the data can say (Classic's ovDrivers); each hedged in its own words. */
export function drivers(t) {
  const out = [], story = g(t, 'digest', 'story'), sc = g(t, 'sector_confirm') || {}, p = g(t, 'pulse') || {};
  if (story && story.title) out.push({ kind: 'News', text: story.title, note: [story.publisher, story.age_words].filter(Boolean).join(', '), url: story.url });
  if (sc.available && sc.rs_vs_spy_label && sc.rs_vs_sector_label) {
    out.push({ kind: 'Market and sector', text: `Over the last ${num(sc.window_sessions || 21, 0)} sessions: ${String(sc.rs_vs_spy_label).replace('SPY', 'the S&P 500')}, and ${String(sc.rs_vs_sector_label).toLowerCase()} (${sc.etf_name || sc.sector || 'sector'}).`,
      note: `Stock ${signed(sc.stock_return_pct, 1)}, sector fund ${signed(sc.etf_return_pct, 1)}, S&P 500 ${signed(sc.spy_return_pct, 1)}.` });
  }
  const tops = ((g(t, 'why', 'reasons') || []).slice(0, 2)).map((r) => r.headline).filter(Boolean);
  if (p.stance) out.push({ kind: "Optic's short-term signals", text: `${capFirst(String(p.stance))}${p.conviction ? `, ${convictionWords(p.conviction)}` : ''}${tops.length ? `. Strongest inputs: ${tops.join('; ').toLowerCase()}` : ''}.`,
    note: 'A model reading of charts, options activity, news tone and the economy for the next 2 to 8 weeks, not a forecast or a reason for today\'s move.', view: 'swing' });
  const reg = g(t, 'gex', 'regime', 'state');
  if (reg === 'negative' || reg === 'positive') out.push({ kind: 'Options positioning', text: reg === 'negative' ? 'Options positioning may amplify price swings.' : 'Options positioning may dampen price swings.', note: 'Based on an assumption about how options dealers hedge, not on positions anyone has reported.', view: 'swing' });
  return out;
}
/** Dates ahead that could matter (Classic's ovEvents): the company's report first, by its date alone (a report's
 *  time of day is not sourced, B1), then the week's releases. Options expiry and positioning reports at Advanced. */
export function events(t, advanced, today) {
  const out = [], ne = earningsNext(t, today), up = (g(t, 'company', 'earnings_history', 'upcoming') || [])[0];
  if (ne) out.push({ date: ne.date, label: 'Earnings report', detail: [fin(ne.days) && ne.days >= 0 ? `in ${ne.days} day${ne.days === 1 ? '' : 's'}` : '', up && fin(up.eps_estimate) ? `analysts expect EPS of ${num(up.eps_estimate, 2)}` : ''].filter(Boolean).join(', '), view: 'earnings' });
  (g(t, 'whats_next', 'this_week') || []).forEach((e) => {
    const special = e.kind === 'expiry' || /\b(COT|Opex|expiry)\b/i.test(String(e.label || ''));
    if (special && !advanced) return;
    out.push({ date: e.date, label: String(e.label || '').replace(/\s*\(([^)]*)\)\s*$/, (m, inner) => (String(e.label).toLowerCase().includes(inner.toLowerCase()) ? '' : ` (${inner})`)), detail: e.detail || '' });
  });
  return out.slice(0, advanced ? 8 : 4);
}
/** Where to go next, from what the page found (Classic's ovNextSteps): each a link to a tab. */
export function nextSteps(sym, t, f, fund, today) {
  const steps = [], ne = earningsNext(t, today), news = g(t, 'news') || {};
  if (ne && fin(ne.days) && ne.days >= 0 && ne.days <= 45) steps.push({ text: `Review past results before the report on ${shortDate(ne.date)}`, view: 'earnings' });
  if (!fund) steps.push({ text: f.neg.some((x) => x.view === 'financials') ? 'Check the statements behind the weaker figures' : 'Read the full financial statements', view: 'financials' });
  steps.push({ text: 'See how the price compares with its own valuation history', view: 'long' });
  if (news.article_count) steps.push({ text: `Read the ${news.article_count} latest headline${news.article_count === 1 ? '' : 's'}`, view: 'news' });
  steps.push({ text: `Compare ${sym} side by side with a competitor`, compare: true });
  return steps.slice(0, 4);
}

/** All eighteen key statistics (Classic's keyStatRows), each with its definition; a figure the feed lacks is left out. */
export function keyStats(q, short, session) {
  const has = fin, ms = (v) => (Math.abs(v) >= 1e6 ? `$${compact(v)}` : money(v));
  const day = session === 'regular' || session === 'after' ? 'today' : 'last session';
  const si = short && short.available !== false ? short : {}, settled = si.settlement_date ? `, as of ${shortDate(si.settlement_date)}` : '';
  q = q || {};
  return [
    ['market_cap', 'Market cap', has(q.market_cap) ? ms(q.market_cap) : null],
    ['pe_trailing', 'P/E (trailing)', has(q.trailing_pe) && q.trailing_pe > 0 ? num(q.trailing_pe, 1) : null],
    ['pe_forward', 'P/E (forward)', has(q.forward_pe) && q.forward_pe > 0 ? num(q.forward_pe, 1) : null],
    ['eps_trailing', 'EPS (trailing)', has(q.trailing_eps) ? money(q.trailing_eps) : null],
    ['eps_forward', 'EPS (forward)', has(q.forward_eps) ? money(q.forward_eps) : null],
    ['dividend_yield', 'Dividend yield', has(q.dividend_yield) && q.dividend_yield > 0 ? `${num(q.dividend_yield * 100, 2)}%` : null],
    ['open', 'Open price', has(q.open) ? money(q.open) : null],
    ['day_high', `High ${day}`, has(q.day_high) ? money(q.day_high) : null],
    ['day_low', `Low ${day}`, has(q.day_low) ? money(q.day_low) : null],
    ['volume', 'Volume', has(q.volume) ? compact(q.volume) : null],
    ['avg_volume', 'Average volume', has(q.avg_volume) ? compact(q.avg_volume) : null],
    ['high_52', '52-week high', has(q.fifty_two_high) ? money(q.fifty_two_high) : null],
    ['low_52', '52-week low', has(q.fifty_two_low) ? money(q.fifty_two_low) : null],
    ['beta', 'Beta', has(q.beta) ? num(q.beta, 2) : null],
    ['short_float', 'Short interest', has(si.percent_of_float) ? `${num(si.percent_of_float * 100, 2)}% of float${settled}` : null],
    ['days_to_cover', 'Days to cover', has(si.days_to_cover) ? num(si.days_to_cover, 1) : null],
    ['profit_margin', 'Profit margin, 12 months', has(q.profit_margin) ? `${num(q.profit_margin * 100, 1)}%` : null],
    ['revenue_growth', 'Revenue growth, last quarter', has(q.revenue_growth) ? signed(q.revenue_growth * 100, 1) : null],
  ].filter((r) => r[2] !== null);
}

/* ---------------- the Pulse read (Classic's pulseReadMore), assembled from the payload, not written ---------------- */
/** Why the stance reads as it does: what carries it, what is against it, what conviction means here, and the limits. */
export function pulseWhy(p) {
  const live = ((p && p.factors) || []).filter((f) => !f.unavailable && fin(Number(f.score)) && f.score !== null);
  if (!live.length) return null;
  const stance = String(p.stance || 'neutral'), side = stance === 'bullish' ? 1 : stance === 'bearish' ? -1 : 0;
  const pull = (f) => (Number(f.score) || 0) * (Number(f.weight_pct) || 0) / 100;
  const sg = (n) => `${n > 0 ? '+' : ''}${num(n, 0)}`;
  const ranked = live.slice().sort((a, b) => Math.abs(pull(b)) - Math.abs(pull(a))), top = ranked[0], second = ranked[1];
  const also = second && Math.abs(pull(second)) >= Math.abs(pull(top)) * 0.4 && Math.sign(Number(second.score)) === Math.sign(Number(top.score));
  const out = { carrying: `${top.label} is doing most of the work, at ${sg(top.score)} on ${num(top.weight_pct, 0)}% of the weight${also ? `, with ${second.label} behind it at ${sg(second.score)} on ${num(second.weight_pct, 0)}%` : ''}.`, measures: top.measures || '' };
  const opposed = side ? ranked.filter((f) => Math.sign(Number(f.score)) === -side && Math.abs(pull(f)) >= 1) : [];
  if (opposed.length) out.against = { lead: 'Against it:', text: `${opposed.map((f) => `${f.label} at ${sg(f.score)} on ${num(f.weight_pct, 0)}%`).join(', ')}.` };
  else if (side) {
    const al = (f) => side * pull(f), weakest = live.slice().sort((a, b) => al(a) - al(b))[0];
    out.against = al(weakest) < 0
      ? { lead: 'Nothing material is pulling the other way.', text: `${weakest.label} is the nearest to it at ${sg(weakest.score)}, which on ${num(weakest.weight_pct, 0)}% of the weight is close to no opinion rather than a disagreement.` }
      : { lead: 'Every input that had data points the same way.', text: `The weakest of them is ${weakest.label} at ${sg(weakest.score)} on ${num(weakest.weight_pct, 0)}% of the weight.` };
  } else out.against = { lead: 'The inputs do not agree on a direction,', text: 'which is what a neutral reading is. It is not a forecast of no movement.' };
  const bits = [];
  if (fin(p.agreement_pct)) bits.push(`${num(p.agreement_pct, 0)}% of the inputs point the same way`);
  if (p.factors_priced && p.factors_total) bits.push(`${p.factors_priced} of ${p.factors_total} had data`);
  if (bits.length && p.conviction) {
    const chain = live.filter((f) => f.key === 'gamma' || f.key === 'flow');
    out.conviction = { lead: capFirst(convictionWords(p.conviction)), text: `${bits.join(' and ')}.${p.pending_catalyst && p.pending_catalyst.pending === true ? ' It is held short of high while a scheduled event is still ahead, because nothing measured here predicts which way that resolves.' : ''} Conviction is agreement between the inputs, not a probability.${chain.length === 2 ? ` ${chain.map((f) => f.label).join(' and ')} are both read off the same option chain, so those two agreeing is less corroboration than two separate ticks look like.` : ''}` };
  }
  const missing = (p.factors || []).filter((f) => f.unavailable), limits = [];
  (p.conflicts || []).forEach((c) => { const x = typeof c === 'string' ? c : (c && (c.text || c.note)) || ''; if (x) limits.push(x); });
  if (missing.length) limits.push(`${missing.map((f) => f.label).join(' and ')} had no data on this run (${missing.map((f) => f.why_unavailable || 'reason not given').join('; ')}). A missing input redistributes its weight rather than counting as zero, so the remaining inputs each carry more than the percentage shown.`);
  limits.push('These are weights this app chose, not a fitted model. The bars show each input\'s own measurement, and the skill note is this project\'s own finding about how much the blend is worth.');
  out.limits = limits;
  return out;
}
function catalystLine(c) {
  if (!c || c.material !== true) return '';
  const h = c.freshest_hours, when = !fin(h) ? 'recently' : h < 1.5 ? 'an hour ago' : h < 24 ? `${Math.round(h)} hours ago` : h < 42 ? 'a day ago' : `${Math.round(h / 24)} days ago`, n = c.count || 1;
  return html`<p class="pl-cat"><b>${n === 1 ? 'One headline' : `${n} headlines`} tagged ${(c.kinds || []).join(' and ')}</b>, ${n === 1 ? 'filed' : 'the freshest'} ${when}. The chart readings below are measured over windows that mostly predate it, so momentum carries less weight here than usual.</p>`;
}
function pendingLine(c) {
  if (!c || c.pending !== true) return '';
  const n = c.count || 1;
  const kinds = (c.kinds || []).join(' and ');
  return html`<p class="pl-cat"><b>${/^[aeiou]/i.test(kinds) ? 'An' : 'A'} ${kinds} event is still ahead</b>, flagged by ${n === 1 ? 'one headline' : `${n} headlines`}. Nothing below predicts which way it resolves, so conviction is held short of high until it does.</p>`;
}
/** A diverging bar: the middle is zero, a cell for every 20 points out to either side. */
function bar(score, direction) {
  if (!fin(Number(score)) || score === null) return html`<span class="pl-bar is-none" aria-hidden="true"></span>`;
  const n = Math.max(0, Math.min(5, Math.round(Math.abs(Number(score)) / 20))), neg = Number(score) < 0;
  const cells = (on) => Array.from({ length: 5 }, (_, i) => html`<i class="${on(i) ? 'on' : ''}"></i>`);
  return html`<span class="pl-bar tone-${direction === 'up' ? 'up' : direction === 'down' ? 'down' : 'flat'}" aria-hidden="true"><span class="pl-half">${cells((i) => neg && 4 - i < n)}</span><i class="pl-mid"></i><span class="pl-half">${cells((i) => !neg && i < n)}</span></span>`;
}

/* ---------------- sections ---------------- */
const tabLink = (sym, view, text, label) => html`<a class="textlink" href="${hrefFor(view, sym)}"${label ? html` aria-label="${label}"` : ''}>${text}</a>`;

/** "What should I look at next?": the dates coming up, the research steps, and what has been moving it. */
export function nextSection(sym, ctx) {
  const t = ctx.t; if (!t) return '';
  const adv = ctx.advanced, evs = events(t, adv, ctx.today), steps = nextSteps(sym, t, ctx.f, ctx.fund, ctx.today), drv = drivers(t);
  return html`<section class="section" aria-labelledby="ov-next-h"><h2 class="t-h2" id="ov-next-h">What to look at next</h2>
    <div class="ovx-cols">
      <div><h3 class="t-h3">Coming up</h3>
        ${evs.length ? html`<ul class="ovx-events">${evs.map((e) => html`<li><span class="ovx-date">${e.date ? shortDate(e.date) : ''}</span> <span><b>${e.label}</b>${e.detail ? html` <span class="t-muted">${e.detail}</span>` : ''}</span></li>`)}</ul>
          <p class="asof">Scheduled dates only. A date is not a forecast of what happens on it, and a report's time of day is not given because the feed does not confirm it.</p>`
          : html`<p class="t-muted">No scheduled company events or economic releases in the data for the coming days.</p>`}</div>
      <div><h3 class="t-h3">Research steps</h3>
        <ul class="ovx-steps">${steps.map((s) => html`<li>${s.compare ? html`<a class="ovx-step" href="#/compare?t=${encodeURIComponent(sym)}"><span>${s.text}</span> <span class="t-muted">Compare</span></a>`
          : html`<a class="ovx-step" href="${hrefFor(s.view, sym)}"><span>${s.text}</span> <span class="t-muted">${TAB[s.view] || ''}</span></a>`}</li>`)}</ul>
        ${miloButton(`Ask Milo a question about ${sym}`, { ask: `What should I look at next on ${sym}, given what this page shows?`, context: `${sym}, what to look at next`, symbol: sym, cls: 'btn-sm' })}
        <p class="asof">Ask Milo writes a question for you to edit. Nothing is sent until you press Send.</p></div>
    </div>
    ${drv.length ? html`<details class="more-inline"><summary>What has been moving it recently</summary><div class="how-body">
      <ul class="ovx-drv">${drv.map((x) => html`<li><span class="t-label">${x.kind}</span> <span>${x.url ? html`<a class="textlink" href="${x.url}" target="_blank" rel="noopener noreferrer nofollow">${x.text}</a>` : x.text}</span>${x.note ? html` <span class="t-muted">${x.note}</span>` : ''}</li>`)}</ul>
      <p class="asof">None of these proves why the price moved. Prices also move on things no data feed records.</p></div></details>` : ''}
  </section>`;
}

function pulseBlock(sym, t) {
  const p = t.pulse; if (!p) return '';
  const dg = t.digest || {}, why = pulseWhy(p), src = dg.sources || {}, story = dg.story, stance = String(p.stance || 'neutral');
  return html`<div class="ovx-block" aria-labelledby="ovx-pl-h"><h3 class="t-h3" id="ovx-pl-h">Optic's short-term read</h3>
    ${dg.as_of ? html`<p class="asof">Updated ${ago(dg.as_of)}. For the next 2 to 8 weeks.</p>` : ''}
    <p class="pl-lede is-${stance}">${clean(dg.lede || p.stance_label || capFirst(stance))}</p>
    ${catalystLine(p.catalyst)}${pendingLine(p.pending_catalyst)}
    <div class="pl-bars" role="group" aria-label="How the ${p.factors_total || 5} inputs scored">${(p.factors || []).map((f) => html`<div class="pl-factor${f.unavailable ? ' is-none' : ''}">
      <span class="pl-flabel">${f.label}</span> ${bar(f.unavailable ? null : f.score, f.direction)} <span class="pl-fval">${f.unavailable ? 'no data' : `${f.score > 0 ? '+' : ''}${num(f.score, 0)}`}${f.unavailable ? '' : html`<span class="t-muted"> on ${num(f.weight_pct, 0)}%</span>`}</span></div>`)}</div>
    <p class="asof">Each input scores from -100 to +100: a bar fills right of the line when the input leans bullish and left when it leans bearish. ${clean(g(p, 'skill', 'text') || '')}${p.factors_priced < p.factors_total ? ` ${p.factors_priced} of ${p.factors_total} inputs had data; a missing input redistributes its weight rather than counting as zero.` : ''}</p>
    <p class="pl-meta">${p.conviction ? html`<span>${capFirst(convictionWords(p.conviction))}</span>` : ''}${fin(p.agreement_pct) ? html`<span>${num(p.agreement_pct, 0)}% of inputs agree</span>` : ''}${src.count ? html`<span>${src.count} news source${src.count === 1 ? '' : 's'}</span>` : ''}</p>
    ${story && story.title ? html`<p class="pl-story"><a class="textlink" href="${story.url || '#'}" target="_blank" rel="noopener noreferrer">${story.title}</a> <span class="t-muted">${[story.publisher, story.age_words, story.catalyst].filter(Boolean).join(', ')}</span></p>` : ''}
    ${why ? html`<details class="more-inline"><summary>Why it reads this way</summary><div class="how-body">
      <p><b>${why.carrying}</b> ${clean(why.measures)}</p>
      <p><b>${why.against.lead}</b> ${why.against.text}</p>
      ${why.conviction ? html`<p><b>${why.conviction.lead}:</b> ${why.conviction.text}</p>` : ''}
      <p class="t-muted">${why.limits.map(clean).join(' ')}</p>
      ${(src.names || []).length ? html`<p class="t-muted">The news input read ${src.count} source${src.count === 1 ? '' : 's'}: ${src.names.join(', ')}.</p>` : ''}
      ${dg.method ? html`<p class="t-muted">${clean(dg.method)}</p>` : ''}</div></details>` : ''}
    <p class="asof">A model's reading of the inputs, not a forecast or a recommendation. ${tabLink(sym, 'swing', 'How it is scored, on Options')}</p></div>`;
}
/** The Optic Score on one 0 to 100 scale for both horizons (Classic's ovScoreHTML). */
export function scores(t, lt) {
  const v = g(t, 'verdict') || {}, p = g(t, 'pulse') || {}, h = g(lt, 'holding');
  const short = score100(v.composite_score), sc = (h && h.conviction_scale) || {};
  const long = h && !h.error ? score100(h.conviction_score, sc.min_possible, sc.max_possible) : null;
  const val = valuationRead(lt);
  let apart = '';
  if (short !== null && long !== null && Math.abs(short - long) >= 25) apart = short > long
    ? 'The two horizons disagree: the recent signals are stronger than the long-run record. A short-term lift inside a weaker long-term picture can fade.'
    : 'The two horizons disagree: the long-run record is stronger than the recent signals. A strong long-term picture can still go through weak weeks.';
  const priceNote = long !== null && long >= 60 && val && val.prem >= 20 ? `The long-term score is built mostly from the price trend and the five-year record. It does not say the price is low: at ${num(val.cur, 1)} times earnings against ${num(val.med, 1)} on average, the price asks more than usual.` : '';
  return { short, shortWords: [capFirst(String(p.stance || v.stance || '')), convictionWords(p.conviction || v.conviction)].filter(Boolean).join(', '),
    long, longWords: h && !h.error ? capFirst([h.conviction ? convictionWords(h.conviction) : '', capFirst(g(h, 'long_trend', 'phase') || '')].filter(Boolean).join(', ')) : lt ? `Not available: ${clean((h && h.error) || 'no data')}.` : 'Working out the long-term score…',
    apart, priceNote };
}
function scoreBlock(sym, t, lt) {
  if (!t.verdict) return '';
  const s = scores(t, lt);
  const tile = (label, horizon, n, words, basis, view, viewLabel) => html`<div class="ovx-score"><p class="t-label">${label} <span class="t-muted">${horizon}</span></p>
    <p class="ovx-n ${n === null ? '' : n >= 55 ? 'up' : n <= 45 ? 'down' : ''}">${n === null ? 'n/a' : html`${num(n, 0)}<small> of 100</small>`}</p>
    ${words ? html`<p>${words}</p>` : ''}<p class="asof">${basis} ${tabLink(sym, view, viewLabel)}</p></div>`;
  return html`<div class="ovx-block" aria-labelledby="ovx-sc-h"><h3 class="t-h3" id="ovx-sc-h">Optic Score, both horizons</h3>
    <div class="ovx-scores">${tile('Short term', 'the next 2 to 8 weeks', s.short, s.shortWords, 'Built from the daily chart trend, current options positioning, the tone of recent headlines and the economy, weighted into one reading for a 2-to-8-week swing.', 'swing', 'How it is scored, on Options')}
      ${tile('Long term', 'holding for several years', s.long, s.longWords, 'Built from up to five years of history: the 200-week and 40-week price trends, the five-year return against the S&P 500, the last year\'s return for the risk taken, valuation, distance from the high and the dividend.', 'long', 'How it is scored, on Investing')}</div>
    ${s.apart ? html`<p class="ovx-note">${s.apart}</p>` : ''}${s.priceNote ? html`<p class="ovx-note">${s.priceNote}</p>` : ''}
    <p class="asof">50 means no edge either way; above 50 the inputs lean favourable, below 50 unfavourable, and 100 is every input at its best. Each score is a rule-based summary of past data, not a forecast, a price target or a recommendation to buy or sell.</p></div>`;
}
function statsBlock(t, session) {
  const rows = keyStats(t.quote, g(t, 'company', 'short_interest'), session);
  if (!rows.length) return '';
  return html`<div class="ovx-block" aria-labelledby="ovx-ks-h"><h3 class="t-h3" id="ovx-ks-h">All key statistics</h3>
    <dl class="ovx-stats">${rows.map(([id, label, v]) => html`<div><dt>${term(`stat:${id}`, label)}</dt><dd>${v}</dd></div>`)}</dl>
    <p class="asof">Select a label for what it measures. From the quote feed; short interest as of its settlement date.</p></div>`;
}
/** One reading from each tab, so the row says what is there rather than only where to go (Classic's overview cards). */
function restBlock(sym, t, D, fund) {
  const q = t.quote || {}, news = t.news || {}, p = t.pulse || {}, st = g(D, 'fairValue', 'stars');
  const lo = q.fifty_two_low, hi = q.fifty_two_high, band = fin(lo) && fin(hi) && hi > lo && fin(q.price) ? Math.round(((q.price - lo) / (hi - lo)) * 100) : null;
  const ne = earningsNext(t);
  const cards = [
    ['chart', 'Chart', band === null ? null : `${band}%`, band === null ? '52-week range unavailable' : 'of its 52-week range'],
    ['swing', 'Options', p.stance ? capFirst(String(p.stance)) : null, p.conviction ? convictionWords(p.conviction) : 'setup, levels and the chain'],
    ['earnings', 'Earnings', ne ? shortDate(ne.date) : null, ne && fin(ne.days) ? `in ${ne.days} days` : 'no date published'],
    ...(fund ? [] : [['financials', 'Financials', fin(q.revenue_growth) ? signed(q.revenue_growth * 100, 1) : null, fin(q.profit_margin) ? `revenue growth, ${num(q.profit_margin * 100, 1)}% margin` : 'revenue growth']]),
    ['news', 'News', news.article_count ? String(news.article_count) : null, news.overall_tone ? `headlines, ${news.overall_tone}` : 'headlines'],
    st && st.available ? ['long', 'Investing', `${st.stars} of 5 stars`, `Optic star rating, ${String(st.word || '').toLowerCase()}${fin(q.trailing_pe) ? `, P/E ${num(q.trailing_pe, 1)}` : ''}`]
      : ['long', 'Investing', fin(q.trailing_pe) ? num(q.trailing_pe, 1) : null, 'trailing P/E, valuation and holding case'],
  ];
  return html`<div class="ovx-block" aria-labelledby="ovx-rest-h"><h3 class="t-h3" id="ovx-rest-h">The rest of this ticker</h3>
    <ul class="ovx-cards">${cards.map(([view, label, value, note]) => html`<li><a class="ovx-card" href="${hrefFor(view, sym)}"><span class="t-label">${label}</span> <b class="${value === null ? 't-muted' : ''}">${value === null ? 'not available' : value}</b> <span class="t-muted">${note}</span></a></li>`)}</ul></div>`;
}
function methodNote(t) {
  const built = ago(t.generated_at);
  return how(html`<ul class="plain">
    <li>Every sentence here comes from the figures on this page by fixed rules. No AI model writes them, so the same data gives the same words.</li>
    <li>Business figures come from the company's filed statements via Yahoo Finance. The latest fiscal year can be months old, and the latest quarter is shown beside it when the two disagree.</li>
    <li>Price figures are daily closes from ${clean(t.data_source || 'the quote feed')}${built ? `, gathered ${built}` : ''}. Outside market hours the price is the last close.</li>
    <li>The wording uses fixed cut-offs, chosen for plain language rather than taken from research: an earnings report within 45 days is listed as a risk; a price 20% or more below its highest close is listed as a risk; a price-to-earnings ratio 20% or more above or below the company's own average over at least three fiscal years is called asking more or less than usual.</li>
    <li>Optic's short-term signal score, its star rating and its options readings are models. Each carries its own method and limits on its page.</li>
    <li>Nothing here is a recommendation to buy or sell.</li></ul>`);
}
/** "Advanced research": opened at the Advanced level, one press away below it. */
export function advancedSection(sym, ctx) {
  const t = ctx.t; if (!t) return '';
  return html`<section class="section ovx-adv" aria-labelledby="ov-adv-h"><div class="section-head"><div><h2 class="t-h2" id="ov-adv-h">Advanced research</h2>
      <p class="section-sub">Optic's short-term signal score, both Optic Scores, all key statistics and every tab at a glance.</p></div></div>
    ${pulseBlock(sym, t)}${scoreBlock(sym, t, ctx.lt)}${statsBlock(t, ctx.session)}${restBlock(sym, t, ctx.D, ctx.fund)}
    ${methodNote(t)}</section>`;
}
/** For a fund, the risk Classic's takeaways named: the first point against it the page found. */
export function fundRisk(sym, f) {
  const r = f && f.neg[0];
  if (!r) return '';
  return html`<p class="ovx-risk"><b>A risk to weigh: ${r.text}.</b> ${r.why || ''}${r.view ? html` ${tabLink(sym, r.view, `The evidence, on ${TAB[r.view]}`)}` : ''}</p>`;
}
void isNum;
