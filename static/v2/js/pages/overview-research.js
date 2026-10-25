// The Overview's Classic research, in v2 (Classic parity, 2026-10-25). The owner sent screenshots of Classic's INTC
// Overview and asked for these here: the four questions, the past year's chart with its marked dates, the key figures,
// the bull case and the bear case, what to look at next, and Optic's read. Classic's rules and analytical words are
// kept word for word (static/app.js ovBusinessRead to renderOverviewView, static/research.js, renderOpticPulse); the
// layout is v2's. Two deliberate differences: a report that has not happened yet is never given a time of day (the
// owner's rule of 2026-10-21, core/reports.js), and the Optic Score is the owner's refined design of 2026-10-25,
// which Classic now shares.
//
// Everything here reads payloads the Overview already loads (/api/ticker, /api/framework, /api/longterm,
// /api/fair-value, /api/extras) by fixed rules. Nothing calls a model; an Ask Milo entry only drafts a question.
import { html } from '../core/dom.js';
import { num, signed, money, clean, capFirst, shortDate, fullDate, ago, score100 } from '../core/format.js';
import { how } from '../ui/states.js';
import { term } from '../ui/term.js';
import { hrefFor } from '../nav.js';

const g = (o, ...ks) => ks.reduce((x, k) => (x && typeof x === 'object' ? x[k] : undefined), o);
const fin = (v) => typeof v === 'number' && Number.isFinite(v);
export const TAB = { chart: 'Chart', swing: 'Options', long: 'Investing', earnings: 'Earnings', financials: 'Financials', news: 'News', overview: 'Overview' };
// Classic's fmtCompact and usdCompact (static/charts.js): "61.23M" at two places, "$32.3B" at one
const fmtCompact = (v, dp = 1) => { const a = Math.abs(v); return a >= 1e12 ? `${(v / 1e12).toFixed(dp)}T` : a >= 1e9 ? `${(v / 1e9).toFixed(dp)}B` : a >= 1e6 ? `${(v / 1e6).toFixed(dp)}M` : a >= 1e3 ? `${(v / 1e3).toFixed(dp)}K` : num(v, a < 10 ? 2 : 0); };
const usdCompact = (v, dp = 1) => (v === 0 ? '$0' : `${v < 0 ? '−' : ''}$${fmtCompact(Math.abs(v), dp)}`);
const usdBig = (v) => (Math.abs(v) >= 1e6 ? usdCompact(v, 2) : money(v));   // Classic's keyStatRows money()
export const convictionWords = (v) => { const w = String(v || '').trim().toLowerCase(); return !w ? '' : w === 'none' ? 'no conviction' : `${w} conviction`; };
const tabLink = (sym, view, text, label) => html`<a class="textlink" href="${hrefFor(view, sym)}"${label ? html` aria-label="${label}"` : ''}>${text}</a>`;

/* ---------------- the readings (Classic's ov* functions) ---------------- */
const OV_SESSIONS = 252;
/** The past year of daily closes (Classic's overviewSeries), with the close before it: 252 sessions of change, so the
 *  year's change here starts on the same close as the chart's (the pitch audit's rule of 2026-10-22, dossier.js
 *  windowOf). Classic counts 252 closes, one session fewer. */
export function series(t) {
  const ps = g(t, 'technicals', 'price_series') || {};
  const dates = (ps.dates || []).map((x) => String(x).slice(0, 10)), close = ps.close || [];
  const rows = dates.map((d, i) => [d, Number(close[i])]).filter(([d, v]) => d && fin(v) && v > 0).slice(-(OV_SESSIONS + 1));
  return { dates: rows.map((r) => r[0]), close: rows.map((r) => r[1]) };
}
function move(x, up = 'grew', down = 'fell', flat = 'was roughly flat') { return !fin(x) ? '' : x >= 1 ? up : x <= -1 ? down : flat; }

/** How the business is doing: the latest fiscal year, with the latest quarter beside it when they disagree. */
export function businessRead(t) {
  const fn = g(t, 'company', 'financials') || {}, q = g(t, 'quote') || {}, gr = fn.growth || {}, m = fn.margins || {};
  const period = (fn.annual_periods || [])[0], fy = period ? `fiscal year to ${period}` : 'latest fiscal year';
  const qRev = fin(q.revenue_growth) ? q.revenue_growth * 100 : null;
  let rev = fn.available ? gr.revenue_yoy_pct : null;
  const ni = fn.available ? gr.net_income_yoy_pct : null;
  const net = fn.available && fin(m.net_pct) ? m.net_pct : fin(q.profit_margin) ? q.profit_margin * 100 : null;
  let basis = 'in the latest fiscal year';
  if (!fin(rev) && fin(qRev)) { rev = qRev; basis = 'in the latest quarter, against the same quarter a year earlier'; }
  if (!fin(rev) && !fin(net)) return null;
  let text;
  if (fin(rev) && fin(ni) && basis.startsWith('in the latest fiscal')) {
    if (rev >= 1 && ni >= 1) text = 'Revenue and profit both grew in the latest fiscal year.';
    else if (rev >= 1 && ni <= -1) text = 'Revenue grew in the latest fiscal year, but profit fell.';
    else if (rev <= -1 && ni >= 1) text = 'Revenue fell in the latest fiscal year, but profit grew.';
    else if (rev <= -1 && ni <= -1) text = 'Revenue and profit both fell in the latest fiscal year.';
    else text = `Revenue ${move(rev)} and profit ${move(ni)} in the latest fiscal year.`;
  } else if (fin(rev)) {
    text = `Revenue ${move(rev)} ${basis}${fin(net) && net < 0 ? ', and the company is not yet profitable' : ''}.`;
  } else text = net >= 0 ? 'The company is profitable.' : 'The company is losing money.';
  const why = !fin(net) ? '' : net >= 0 ? `It kept about ${num(net, 0)} cents of profit from each dollar of sales.` : `It lost about ${num(-net, 0)} cents on each dollar of sales.`;
  let conflict = '';
  if (basis.startsWith('in the latest fiscal') && fin(rev) && fin(qRev) && ((rev >= 1 && qRev <= -1) || (rev <= -1 && qRev >= 1))) {
    conflict = `The latest quarter points the other way: revenue ${qRev >= 0 ? 'rose' : 'fell'} ${num(Math.abs(qRev), 1)}% against the same quarter a year earlier. Annual figures move slowly, so a turn shows in the quarters first.`;
  }
  const evidence = [];
  if (fn.available && fin(gr.revenue_yoy_pct)) evidence.push([`Revenue growth, ${fy}`, signed(gr.revenue_yoy_pct, 1)]);
  if (fn.available && fin(ni)) evidence.push([`Net income growth, ${fy}`, signed(ni, 1)]);
  if (fn.available && !fin(ni) && fin(gr.revenue_yoy_pct)) evidence.push(['Net income growth', 'Not meaningful: the earlier year was a loss or is missing']);
  if (fin(net)) evidence.push([fn.available && fin(m.net_pct) ? `Net margin, ${fy}` : 'Profit margin, 12 months', `${num(net, 1)}%`]);
  if (fin(qRev)) evidence.push(['Revenue, latest quarter against a year earlier', signed(qRev, 1)]);
  return { text, why, conflict, evidence, source: fn.available ? "The company's annual statements and latest quarter, via Yahoo Finance." : 'Yahoo Finance.' };
}

/** How the share price has behaved: the year, the last three months, the distance from the year's highest close. */
export function priceRead(t, { index = false } = {}) {
  const { dates, close } = series(t);
  if (close.length < 20) return null;
  const last = close[close.length - 1], yr = (last / close[0] - 1) * 100;
  const span = close.length >= OV_SESSIONS - 12 ? 'over the past year' : `over the last ${num(close.length, 0)} sessions`;
  const m3 = close.length > 64 ? (last / close[close.length - 64] - 1) * 100 : null;
  const off = (last / Math.max(...close) - 1) * 100;
  const yrWords = Math.abs(yr) < 2 ? `little changed ${span}` : `${yr >= 0 ? 'up' : 'down'} ${num(Math.abs(yr), 0)}% ${span}`;
  const subj = index ? 'The index' : 'The share price';
  let text;
  if (fin(m3) && yr >= 5 && m3 <= -5) text = `${subj} is ${yrWords}, but has fallen ${num(Math.abs(m3), 0)}% over the last three months.`;
  else if (fin(m3) && yr <= -5 && m3 >= 5) text = `${subj} is ${yrWords}, but has risen ${num(m3, 0)}% over the last three months.`;
  else text = `${subj} is ${yrWords}${off > -3 ? ', close to its highest close of that period' : `, ${num(Math.abs(off), 0)}% below its highest close`}.`;
  const evidence = [[`Change ${span}`, signed(yr, 1)]];
  if (fin(m3)) evidence.push(['Change over the last three months', signed(m3, 1)]);
  evidence.push(['Below the highest close of the period', off > -0.05 ? 'At it' : signed(off, 1)]);
  const q = g(t, 'quote') || {};
  if (fin(q.fifty_two_low) && fin(q.fifty_two_high)) evidence.push(['52-week range', `${money(q.fifty_two_low)} to ${money(q.fifty_two_high)}`]);
  const why = fin(m3) && !text.includes('three months') ? `Over the last three months it is ${Math.abs(m3) < 2 ? 'little changed' : `${m3 >= 0 ? 'up' : 'down'} ${num(Math.abs(m3), 0)}%`}.` : '';
  return { text, why, evidence, yr, m3, off, through: dates[dates.length - 1] };
}

/** The price against its own history (Classic's ovValuationRead), from the long-term payload's P/E history. */
export function valuationRead(lt) {
  const vh = g(lt, 'holding', 'valuation_history');
  if (!vh || !vh.available || !(vh.usable_years >= 3)) return null;
  const cur = Number(vh.current_pe), med = Number(vh.median_pe);
  if (!fin(cur) || !fin(med) || cur <= 0 || med <= 0) return null;
  const prem = (cur / med - 1) * 100, years = vh.usable_years;
  const band = fin(vh.low_pe) && fin(vh.high_pe) ? ` (its range was ${num(vh.low_pe, 1)} to ${num(vh.high_pe, 1)})` : '';
  const tone = prem >= 20 ? 'bad' : prem <= -20 ? 'good' : 'mixed';
  const text = tone === 'bad' ? `The price asks more than usual: ${num(cur, 1)} times earnings, against ${num(med, 1)} on average over its last ${years} fiscal years.`
    : tone === 'good' ? `The price asks less than usual: ${num(cur, 1)} times earnings, against ${num(med, 1)} on average over its last ${years} fiscal years.`
      : `The price is in line with its own history: ${num(cur, 1)} times earnings, against ${num(med, 1)} on average over its last ${years} fiscal years.`;
  const why = tone === 'bad' ? 'A strong business can still be an expensive stock. A higher multiple means more good news is already in the price, so a disappointment tends to cost more.'
    : tone === 'good' ? 'A lower multiple can mean the market expects weaker results ahead, so check the business card beside this before reading it as cheap.'
      : 'Neither stretched nor discounted against its own record, so the price is not the main question here.';
  return { text, why, tone, prem, cur, med, years,
    evidence: [['Price to earnings now (trailing)', num(cur, 1)], [`Average over ${years} fiscal years${band}`, num(med, 1)], ['Now against that average', signed(prem, 0)]],
    source: "Each fiscal year's diluted EPS against that year's average closing price, from the company's statements via Yahoo Finance. Trailing only." };
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
 *  importance, four of each at most, each naming the tab that holds its evidence. */
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
  if (fin(bs.net_cash) && bs.net_cash > 0) pos.push({ text: `Holds more cash than debt (${usdCompact(bs.net_cash)} net cash)`, view: 'financials' });
  if (ow.available && ow.insider_signal === 'buying') pos.push({ text: 'Company insiders bought more shares than they sold over six months', view: 'financials' });
  if (st && st.stars >= 4) pos.push({ text: `Optic star rating ${st.stars} of 5: ${String(st.word || '').toLowerCase()}`, view: 'long' });
  if (price && price.yr >= 5) pos.push({ text: `Share price up ${num(price.yr, 0)}% over the period shown`, view: 'chart' });
  if (sc.available && /outperform|leading|ahead/i.test(String(sc.rs_vs_sector_label || ''))) pos.push({ text: `Ahead of its sector over the last ${num(sc.window_sessions || 21, 0)} sessions` });

  const ne = earningsNext(t, today), days = ne ? ne.days : null;
  if (ne && fin(days) && days >= 0 && days <= 45) neg.push({ text: `Earnings report on ${shortDate(ne.date)}, in ${days} day${days === 1 ? '' : 's'}`, why: 'Results and guidance can move the price sharply in either direction.', view: 'earnings' });
  // the price against its own history, once per page and not beside a star rating that already says the same thing
  const val = fund || (st && (st.stars >= 4 || st.stars <= 2)) ? null : valuationRead(lt);
  if (val && val.tone === 'bad') neg.push({ text: `Priced above its own history: ${num(val.cur, 1)} times earnings against a ${val.years}-year average of ${num(val.med, 1)}`, why: val.why, view: 'long' });
  else if (val && val.tone === 'good') pos.push({ text: `Priced below its own history: ${num(val.cur, 1)} times earnings against a ${val.years}-year average of ${num(val.med, 1)}`, view: 'long' });
  if (fin(net) && net < 0) neg.push({ text: 'The company lost money over the latest period', why: 'Losses are paid for from cash, borrowing or new shares until the business turns a profit.', view: 'financials' });
  if (fn.available && fin(gr.revenue_yoy_pct) && gr.revenue_yoy_pct <= -1) neg.push({ text: `Revenue fell ${num(Math.abs(gr.revenue_yoy_pct), 1)}% in the latest fiscal year`, why: 'Falling sales make it harder to grow profit.', view: 'financials' });
  if (fn.available && fin(gr.net_income_yoy_pct) && gr.net_income_yoy_pct <= -1) neg.push({ text: `Net income fell ${num(Math.abs(gr.net_income_yoy_pct), 1)}% in the latest fiscal year`, why: 'One-off gains and charges move profit more than sales, so check the statements before reading much into it.', view: 'financials' });
  if (fin(bs.net_cash) && bs.net_cash < 0 && fin(net) && net < 0) neg.push({ text: `Owes ${usdCompact(-bs.net_cash)} more than it holds in cash while losing money`, why: 'Debt has to be paid or refinanced whether or not the business recovers.', view: 'financials' });
  if (st && st.stars <= 2) neg.push({ text: `Optic star rating ${st.stars} of 5: ${String(st.word || '').toLowerCase()}`, why: "Optic's fair-value model places the price above the range it treats as usual for this company. A model estimate, not a verdict.", view: 'long' });
  if (si.available && si.squeeze_potential && !/^low/i.test(String(si.squeeze_potential)) && fin(si.percent_of_float)) neg.push({ text: `${num(si.percent_of_float * 100, 1)}% of the tradable shares are sold short`, why: 'Many investors are betting the price will fall, and short sellers buying back can also cause sudden rises.', view: 'financials' });
  if (sc.available && /lag/i.test(String(sc.rs_vs_sector_label || ''))) neg.push({ text: `Has lagged its sector over the last ${num(sc.window_sessions || 21, 0)} sessions`, why: sc.conflict || 'Peers in the same industry have done better over the same weeks.' });
  if (g(t, 'gex', 'regime', 'state') === 'negative') neg.push({ text: 'Options positioning may amplify price swings', why: "Under Optic's model of how options dealers hedge, their trading could add to moves in either direction. An assumption, not reported positions.", view: 'swing' });
  if (String(news.overall_tone || '').includes('bear')) neg.push({ text: 'Recent headlines lean negative', why: `Scored from ${num(news.article_count || 0, 0)} headlines by a fixed word list. It measures tone, not whether the news is true or important.`, view: 'news' });
  if (price && price.off <= -20) neg.push({ text: `Trading ${num(Math.abs(price.off), 0)}% below its highest close of the period`, why: 'A long fall can reflect a real change in the business, or a market that has moved on from it.', view: 'chart' });
  return { pos: pos.slice(0, 4), neg: neg.slice(0, 4) };
}

/** What has been moving the stock, as far as the data can say (Classic's ovDrivers), each hedged in its own words. */
export function drivers(t) {
  const out = [], story = g(t, 'digest', 'story'), sc = g(t, 'sector_confirm') || {}, p = g(t, 'pulse') || {};
  if (story && story.title) out.push({ kind: 'News', text: story.title, note: [story.publisher, story.age_words].filter(Boolean).join(', '), url: story.url });
  if (sc.available && sc.rs_vs_spy_label && sc.rs_vs_sector_label) {
    out.push({ kind: 'Market and sector', text: `Over the last ${num(sc.window_sessions || 21, 0)} sessions: ${String(sc.rs_vs_spy_label).replace('SPY', 'the S&P 500')}, and ${String(sc.rs_vs_sector_label).toLowerCase()} (${sc.etf_name || sc.sector || 'sector'}).`,
      note: `Stock ${signed(sc.stock_return_pct, 1)}, sector fund ${signed(sc.etf_return_pct, 1)}, S&P 500 ${signed(sc.spy_return_pct, 1)}.` });
  }
  const tops = (g(t, 'why', 'reasons') || []).slice(0, 2).map((r) => r.headline).filter(Boolean);
  if (p.stance) out.push({ kind: "Optic's short-term signals", text: `${capFirst(String(p.stance))}${p.conviction ? `, ${convictionWords(p.conviction)}` : ''}${tops.length ? `. Strongest inputs: ${tops.join('; ').toLowerCase()}` : ''}.`,
    note: 'A model reading of charts, options activity and news tone for the next 2 to 8 weeks, not a forecast or a reason for today’s move.' });
  const reg = g(t, 'gex', 'regime', 'state');
  if (reg === 'negative' || reg === 'positive') out.push({ kind: 'Options positioning', text: reg === 'negative' ? 'Options positioning may amplify price swings.' : 'Options positioning may dampen price swings.', note: 'Based on an assumption about how options dealers hedge, not on positions anyone has reported.' });
  return out;
}

/** Dates ahead that could matter (Classic's ovEvents): the company's report first, then the week's releases. A
 *  report's time of day is left out: the feed's time on an upcoming row is a placeholder (core/reports.js). */
export function events(t, advanced, today) {
  const out = [], ne = earningsNext(t, today), up = (g(t, 'company', 'earnings_history', 'upcoming') || [])[0];
  const date = g(t, 'news', 'earnings_date') || (up && up.date);
  if (date) {
    const days = ne ? ne.days : g(t, 'news', 'days_to_earnings');
    out.push({ date, label: 'Earnings report', detail: [fin(days) && days >= 0 ? `in ${days} day${days === 1 ? '' : 's'}` : '', up && fin(up.eps_estimate) ? `analysts expect EPS of ${num(up.eps_estimate, 2)}` : ''].filter(Boolean).join(', '), view: 'earnings' });
  }
  (g(t, 'whats_next', 'this_week') || []).forEach((e) => {
    const special = e.kind === 'expiry' || /\b(COT|Opex|expiry)\b/i.test(String(e.label || ''));
    if (special && !advanced) return;
    out.push({ date: e.date, label: String(e.label || '').replace(/\s*\(([^)]*)\)\s*$/, (m, inner) => (String(e.label).toLowerCase().includes(inner.toLowerCase()) ? '' : ` (${inner})`)), detail: e.detail || '' });
  });
  return out.slice(0, advanced ? 8 : 4);
}
/** Where to go next, from what the page found (Classic's ovNextSteps): each step a link to a tab. */
export function nextSteps(sym, t, f, fund, today) {
  const steps = [], ne = earningsNext(t, today), news = g(t, 'news') || {};
  if (ne && fin(ne.days) && ne.days >= 0 && ne.days <= 45) steps.push({ text: `Review past results before the report on ${shortDate(ne.date)}`, view: 'earnings' });
  if (!fund) steps.push({ text: f.neg.some((x) => x.view === 'financials') ? 'Check the statements behind the weaker figures' : 'Read the full financial statements', view: 'financials' });
  steps.push({ text: 'See how the price compares with its own valuation history', view: 'long' });
  if (news.article_count) steps.push({ text: `Read the ${news.article_count} latest headline${news.article_count === 1 ? '' : 's'}`, view: 'news' });
  steps.push({ text: `Compare ${sym} side by side with a competitor`, compare: true });
  return steps.slice(0, 4);
}

/** Every key statistic (Classic's keyStatRows), keyed by its id; a figure the feed lacks is null. */
export function keyStatRows(q, shortInt, phase) {
  q = q || {};
  const has = fin, day = phase === 'regular' || phase === 'after' ? 'today' : 'last session';
  const si = shortInt && shortInt.available !== false ? shortInt : {}, settled = si.settlement_date ? `, as of ${shortDate(si.settlement_date)}` : '';
  return {
    market_cap: ['Market cap', has(q.market_cap) ? usdBig(q.market_cap) : null],
    pe_trailing: ['P/E (trailing)', has(q.trailing_pe) && q.trailing_pe > 0 ? num(q.trailing_pe, 1) : null],
    pe_forward: ['P/E (forward)', has(q.forward_pe) && q.forward_pe > 0 ? num(q.forward_pe, 1) : null],
    eps_trailing: ['EPS (trailing)', has(q.trailing_eps) ? money(q.trailing_eps) : null],
    eps_forward: ['EPS (forward)', has(q.forward_eps) ? money(q.forward_eps) : null],
    dividend_yield: ['Dividend yield', has(q.dividend_yield) && q.dividend_yield > 0 ? `${num(q.dividend_yield * 100, 2)}%` : null],
    open: ['Open price', has(q.open) ? money(q.open) : null],
    day_high: [`High ${day}`, has(q.day_high) ? money(q.day_high) : null],
    day_low: [`Low ${day}`, has(q.day_low) ? money(q.day_low) : null],
    volume: ['Volume', has(q.volume) ? fmtCompact(q.volume, 2) : null],
    avg_volume: ['Average volume', has(q.avg_volume) ? fmtCompact(q.avg_volume, 2) : null],
    high_52: ['52-week high', has(q.fifty_two_high) ? money(q.fifty_two_high) : null],
    low_52: ['52-week low', has(q.fifty_two_low) ? money(q.fifty_two_low) : null],
    beta: ['Beta', has(q.beta) ? num(q.beta, 2) : null],
    short_float: ['Short interest', has(si.percent_of_float) ? `${num(si.percent_of_float * 100, 2)}% of float${settled}` : null],
    days_to_cover: ['Days to cover', has(si.days_to_cover) ? num(si.days_to_cover, 1) : null],
    profit_margin: ['Profit margin, 12 months', has(q.profit_margin) ? `${num(q.profit_margin * 100, 1)}%` : null],
    revenue_growth: ['Revenue growth, last quarter', has(q.revenue_growth) ? signed(q.revenue_growth * 100, 1) : null],
  };
}
// The four figures most readers look a stock up for, plus its range and yield (Classic's OV_ESSENTIALS)
export const OV_ESSENTIALS = ['market_cap', 'pe_trailing', 'revenue_growth', 'profit_margin', 'dividend_yield', 'high_52', 'low_52'];
const statList = (rows, ids) => html`<dl class="ovx-stats">${ids.filter((id) => rows[id] && rows[id][1] !== null).map((id) => html`<div><dt>${term(`stat:${id}`, rows[id][0])}</dt><dd>${rows[id][1]}</dd></div>`)}</dl>`;

/* ---------------- the past year's chart: its line, its marks and its source ---------------- */
/** "INTC is up 128% over the past year, 38% below its highest close" (Classic's overviewChartTitle). */
export function chartTitle(sym, close) {
  if (close.length < 2) return '';
  const chg = (close[close.length - 1] / close[0] - 1) * 100;
  const span = close.length >= OV_SESSIONS - 12 ? 'over the past year' : `over the ${num(close.length, 0)} sessions shown`;
  const mv = `${sym} is ${chg >= 0 ? 'up' : 'down'} ${num(Math.abs(chg), 0)}% ${span}`;
  const off = (close[close.length - 1] / Math.max(...close) - 1) * 100;
  return off > -1 ? `${mv}, at its highest close of it` : `${mv}, ${num(Math.abs(off), 0)}% below its highest close`;
}
const PAST_TIMING = { before_open: 'before the open', after_close: 'after the close', during: 'during the session' };
/** Earnings reports (E), ex-dividend dates (D) and splits (S) inside the window (Classic's overviewEvents). A
 *  reported quarter's time of day is from the record, so it is said. */
export function chartMarks(t, extras, first, last) {
  const inside = (iso) => iso && iso >= first && iso <= last, out = [];
  (g(t, 'company', 'earnings_history', 'quarters') || []).forEach((r) => {
    const d = String(r.date || '').slice(0, 10); if (!inside(d)) return;
    const beat = fin(r.surprise_pct) ? (r.surprise_pct >= 0 ? 'beat' : 'missed') : '';
    const eps = [fin(r.eps_reported) ? `EPS ${num(r.eps_reported, 2)}` : '', fin(r.eps_estimate) ? `against ${num(r.eps_estimate, 2)} expected` : '', beat ? `(${beat} by ${num(Math.abs(r.surprise_pct), 1)}%)` : ''].filter(Boolean).join(' ');
    // `text` is Classic's line for the marked-dates table; `detail` the figures alone, for the drawer that names the session itself
    out.push({ d, kind: 'E', label: 'Earnings report', r, detail: eps, text: [PAST_TIMING[r.timing] ? `Reported ${PAST_TIMING[r.timing]}` : 'Reported', eps].filter(Boolean).join(' ') });
  });
  const acts = (extras && !extras.error && extras.actions) || {};
  (acts.dividends || []).forEach((r) => { const d = String(r.date || '').slice(0, 10), text = fin(r.amount) ? `${money(r.amount)} a share` : 'Amount not given'; if (inside(d)) out.push({ d, kind: 'D', label: 'Ex-dividend date', text, detail: text }); });
  (acts.splits || []).forEach((r) => { const d = String(r.date || '').slice(0, 10), text = fin(r.ratio) ? `${num(r.ratio, 2)}-for-1` : 'Ratio not given'; if (inside(d)) out.push({ d, kind: 'S', label: 'Split', text, detail: text }); });
  return out.sort((a, b) => a.d.localeCompare(b.d));
}
/** The line under the title: what is drawn, through when, from where, what the letters mean, and the next report by
 *  its date alone. */
export function chartSource(t, through, nextDate) {
  const src = g(t, 'data_source') === 'tradier' ? 'Tradier, with Yahoo Finance where it has no data' : 'Yahoo Finance';
  return `Daily closes, split-adjusted, through ${fullDate(through)}. Source: ${src}. Marked: E an earnings report, D an ex-dividend date, S a split.${nextDate && nextDate > through ? ` Next report ${fullDate(nextDate)}.` : ''}`;
}
/** Every marked date in words, for a keyboard and a screen reader (Classic's #ov-events table). */
export function marksFold(marks) {
  if (!marks.length) return '';
  return html`<details class="more-inline"><summary>The ${marks.length} marked date${marks.length === 1 ? '' : 's'}</summary><div class="how-body">
    <table class="t ovx-marks"><thead><tr><th scope="col">Date</th><th scope="col">Marked</th><th scope="col">What</th></tr></thead>
    <tbody>${marks.slice().reverse().map((e) => html`<tr><td>${fullDate(e.d)}</td><td>${e.label}</td><td>${e.text}</td></tr>`)}</tbody></table></div></details>`;
}

/* ---------------- four questions, answered separately (Classic's static/research.js) ---------------- */
const QUESTIONS = [['business', 'Is it a strong business?'], ['price', 'Is the price attractive?'], ['trade', 'Is there a trade?'], ['earnings', 'What about earnings?']];
const PRICE_WORDS = ['very rich', 'rich', 'full', 'reasonable', 'cheap'];
const list = (items) => { const rows = (items || []).filter(Boolean); return rows.length ? html`<ul class="plain">${rows.map((x) => html`<li>${clean(x)}</li>`)}</ul>` : ''; };
const pct = (v, d = 1) => (fin(v) ? `${num(v, d)}%` : 'n/a');
const usd = (v) => (fin(v) ? money(v) : 'n/a');
function componentRows(cs, kind) {
  return (cs || []).map((c) => {
    const scored = c.status === 'scored' && fin(c.score);
    const grade = scored ? (kind === 'price' ? PRICE_WORDS[Math.max(0, Math.min(4, Math.round(c.score)))] : (c.grade || num(c.score, 1))) : c.status === 'not_applicable' ? 'n/a' : 'no data';
    return html`<tr><th scope="row">${c.label}</th><td class="q-g">${grade}</td><td>${clean((c.status === 'scored' ? c.headline : c.reason) || '')}</td></tr>`;
  });
}
const qtable = (rows) => html`<table class="t q-table"><tbody>${rows}</tbody></table>`;
const qh = (t) => html`<p class="q-h">${t}</p>`;
const fine = (t) => html`<p class="asof">${t}</p>`;

/** A finding's figures, behind "Show the figures" (Classic's ovEvidenceHTML). */
function evidenceFold(sym, rows, source, view, viewLabel) {
  if (!rows || !rows.length) return '';
  return html`<details class="more-inline q-ev"><summary>Show the figures</summary><div class="how-body">
    <dl class="q-evlist">${rows.map(([k, v]) => html`<div><dt>${clean(k)}</dt><dd>${clean(v)}</dd></div>`)}</dl>
    ${source || view ? html`<p class="asof">${source ? `${source} ` : ''}${view ? tabLink(sym, view, viewLabel) : ''}</p>` : ''}</div></details>`;
}
/** The plain answer under each question (Classic's ovPlainHTML): the business, the multiple against its own history,
 *  the share price's trend; a risk goes to the card whose evidence it is. */
function plain(id, c) {
  const t = c.t; if (!t || !t.quote) return '';
  const biz = c.fund ? null : businessRead(t), val = biz ? valuationRead(c.lt) : null, price = priceRead(t, { index: c.index });
  const risk = c.f.neg.find((x) => !(val && x.view === 'long'));
  const home = risk ? ({ financials: 'business', long: 'price', earnings: 'earnings' }[risk.view] || 'trade') : '';
  const line = (text, why) => html`${text ? html`<p class="q-plain">${text}</p>` : ''}${why ? html`<p class="q-why">${why}</p>` : ''}`;
  const riskLine = home === id && id !== 'earnings' ? html`<p class="q-why"><b>A risk to weigh:</b> ${risk.text}.${risk.why ? ` ${risk.why}` : ''}</p>` : '';
  if (id === 'business' && biz) return html`${line(biz.text, [biz.why, biz.conflict].filter(Boolean).join(' '))}${riskLine}${evidenceFold(c.sym, biz.evidence, biz.source, 'financials', 'Open Financials')}`;
  if (id === 'price' && val) return html`${line(val.text, val.why)}${riskLine}${evidenceFold(c.sym, val.evidence, val.source, 'long', 'Open Investing')}`;
  if (id === 'trade' && price) return html`${line(price.text, `${price.why ? `${price.why} ` : ''}This describes the stock, not the business.`)}${riskLine}${evidenceFold(c.sym, price.evidence, `Daily closes through ${fullDate(price.through)}. Source: ${g(t, 'data_source') === 'tradier' ? 'Tradier, with Yahoo Finance where it has no data' : 'Yahoo Finance'}.`, 'chart', 'Open the chart')}`;
  if (id === 'earnings' && home === 'earnings') return line('', risk.why || '');
  return riskLine;
}
function tile(id, label, value, sub, more, c) {
  return html`<div class="q-card" data-q="${id}"><p class="q-label">${label}</p>
    <p class="q-val${/^Insufficient|not graded|Grading/i.test(value) ? ' is-none' : ''}">${value}</p>
    ${plain(id, c)}${sub ? html`<p class="q-sub">${clean(sub)}</p>` : ''}
    ${more ? html`<details class="more-inline q-more"><summary>Why</summary><div class="how-body">${more}</div></details>` : ''}</div>`;
}
function businessTile(lt, c) {
  if (!lt || !lt.available) {
    const why = g(lt, 'conviction', 'why') || '';
    return tile('business', 'Is it a strong business?', 'Insufficient Data', 'Its annual filings could not be read here, so the business is not graded. That is missing evidence, not a bad grade.', why ? html`<p>${clean(why)}</p>` : '', c);
  }
  const q = lt.quality || {}, conv = lt.conviction || {};
  const value = q.status === 'scored' ? `Quality ${q.grade}` : 'Insufficient Data';
  const sub = q.status === 'scored' ? `Quality and price together: ${conv.label}. ${conv.why || ''}` : (q.reason || '');
  const more = html`${qtable(componentRows(q.components))}
    ${(lt.loss_paths || []).length ? html`${qh('Two ways this could lose money over three years')}${list(lt.loss_paths.map((l) => `${l.risk}: ${l.text}`))}` : ''}
    ${g(lt, 'accumulation', 'offered') ? html`${qh('Levels to reassess at')}${list(lt.accumulation.zones.map((z) => `${usd(z.price)}: ${z.basis} (${pct(z.distance_pct)})`))}${fine(clean(lt.accumulation.condition))}` : ''}
    ${fine(clean(`${lt.policy_note || ''} ${lt.separation_note || ''}`))}`;
  return tile('business', 'Is it a strong business?', value, sub, more, c);
}
function priceTile(lt, c) {
  const v = (lt || {}).valuation || {};
  if (!lt || !lt.available || !v.status) return tile('price', 'Is the price attractive?', 'Insufficient Data', 'Valuation needs the company\'s filings.', '', c);
  const lead = (v.components || []).find((x) => x.status === 'scored');
  const sub = v.status === 'scored' ? (lead ? lead.headline : v.summary) : (v.reason || '');
  const chart = lt.chart || {};
  const more = html`${qtable(componentRows(v.components, 'price'))}
    ${chart.text ? html`${qh('The chart, as context')}<p>${clean(chart.text)}</p>` : ''}${chart.volume ? fine(clean(chart.volume.text)) : ''}
    ${fine('Graded on its own, separately from the business: 4 of 4 is cheapest. A strong business can be an expensive stock.')}`;
  return tile('price', 'Is the price attractive?', v.status === 'scored' ? v.label : 'Insufficient Data', sub, more, c);
}
function tradeTile(sw, c) {
  if (!sw) return tile('trade', 'Is there a trade?', 'Insufficient Data', 'No swing assessment.', '', c);
  const plan = sw.plan, objections = (sw.objections || []).slice().sort((a, b) => b.severity - a.severity);
  const parts = [objections.length ? html`${qh('Reasons to skip it, most damaging first')}${list(objections.map((o) => o.text))}` : html`<p>No specific objection was found in the data.</p>`];
  if (plan) {
    const inv = plan.invalidation || {}, sens = plan.sensitivity || {}, row = (k, v) => html`<tr><th scope="row">${k}</th><td colspan="2">${v}</td></tr>`;
    parts.push(qtable([row('Setup', `${plan.kind} (${plan.side})`), row('Entry zone', `${usd((plan.entry_zone || [])[0])} to ${usd((plan.entry_zone || [])[1])}`), row('Confirmation', clean(plan.confirmation)),
      row('Invalidation', `${usd(inv.price)}: ${clean(inv.structure || '')}. ${clean(inv.note || '')}`), row('Targets', `${(plan.targets || []).map(usd).join(', ')} (${clean(plan.target_basis || '')})`),
      row('Reward to risk', `${fin(plan.reward_to_risk) ? num(plan.reward_to_risk, 2) : 'n/a'} = ${clean(plan.rr_formula || '')}; ${fin(sens.low) ? `${num(sens.low, 2)} to ${num(sens.high, 2)} across fills and costs` : ''}`),
      row('Holding', clean(g(plan, 'holding', 'basis') || '')), row('Earnings', clean(g(plan, 'earnings', 'text') || ''))]));
    parts.push(fine(clean(plan.reassess || '')));
    const s = plan.sizing_example;
    if (s && s.available) parts.push(fine(clean(`${s.label} ${s.shares} shares risk about $${Math.round(s.planned_loss)} at the stop. ${s.gap_note || ''}`)));
  } else if (sw.reassess_when) parts.push(html`${qh('What would make it worth another look')}<p>${clean(sw.reassess_when)}</p>`);
  parts.push(fine(clean(sw.framework_note || '')));
  const value = ['S', 'A', 'B'].includes(sw.grade) ? `Grade ${sw.grade}` : sw.grade;
  return tile('trade', 'Is there a trade?', value, sw.why, html`${parts}`, c);
}
function earningsTile(er, c) {
  if (!er) return tile('earnings', 'What about earnings?', 'Insufficient Data', 'No earnings data.', '', c);
  const pre = er.pre, post = er.post;
  if (pre && pre.available) {
    const rel = pre.release || {}, p = pre.predictions || {}, conf = g(pre, 'view', 'confidence') || {}, opt = pre.options || {}, view = pre.view || {}, cases = view.cases || {};
    const row = (k, label) => (p[k] ? html`<tr><th scope="row">${label}</th><td class="q-g">${p[k].lean}</td><td>Confidence: ${conf[k] || p[k].confidence}. ${clean((p[k].evidence || []).map((x) => x.text).join(' '))}</td></tr>` : '');
    const more = html`${qtable([row('results', 'Results'), row('guidance', 'Guidance'), row('reaction', 'Stock reaction')])}
      ${qh('The bar it has to clear')}<p>${clean(g(pre, 'hurdle', 'text') || '')}</p>${list((g(pre, 'hurdle', 'points') || []).map((x) => x.text))}
      ${opt.available ? html`${qh('What options are priced for')}<p>${pct(opt.event_move_pct || opt.expiry_move_pct)} either way${opt.range ? ` (${usd(opt.range.low)} to ${usd(opt.range.high)})` : ''}. ${clean(opt.event_isolated ? (opt.event_move_method || '') : (opt.event_note || ''))}</p>` : ''}
      ${qh('Cases')}${list([`Base: ${cases.base || ''}`, `Bull: ${cases.bull || ''}`, `Bear: ${cases.bear || ''}`])}
      ${qh('What would prove it wrong')}${list(view.invalidators)}
      ${fine(clean(`${view.thesis_vs_trade || ''} ${view.probabilities_note || ''} Not in the data: ${(pre.not_available || []).join(', ')}.`))}`;
    // the server leaves an upcoming report's session 'unknown' (its time on the feed is a placeholder), so only a
    // sourced session is said
    const timing = { before_open: 'before the open', after_close: 'after the close' }[rel.timing] || (rel.timing && rel.timing !== 'unknown' ? rel.timing.replace('_', ' ') : '');
    const when = `${shortDate(rel.date) || rel.date || ''}${timing ? `, ${timing}` : ''}${rel.confirmed ? '' : ' (estimated)'}`;
    return tile('earnings', 'What about earnings?', `Reports ${when}`, view.headline, more, c);
  }
  if (post && post.available) {
    const q = post.quality || {}, a = post.headline_audit || {}, e = a.eps || {}, rx = post.reaction || {};
    const more = html`${qtable([html`<tr><th scope="row">EPS</th><td class="q-g">${e.state || ''}</td><td>${fin(e.actual) ? num(e.actual, 2) : 'n/a'} against ${fin(e.consensus) ? num(e.consensus, 2) : 'n/a'} (${clean(e.basis || '')})</td></tr>`,
      html`<tr><th scope="row">Revenue</th><td class="q-g">${g(a, 'revenue', 'state') || ''}</td><td>${clean(g(a, 'revenue', 'reason') || '')}</td></tr>`,
      html`<tr><th scope="row">Guidance</th><td class="q-g">n/a</td><td>${clean(g(a, 'guidance', 'reason') || '')}</td></tr>`])}
      ${e.resolution ? fine(clean(e.resolution)) : ''}${a.basis_warning ? fine(clean(a.basis_warning)) : ''}
      ${qh('The reaction')}<p>${clean(`${rx.text || ''} ${rx.caveat || ''}`)}</p>
      ${list((post.positives || []).map((x) => `Positive: ${x}`))}${list((post.weaknesses || []).map((x) => `Weakness: ${x}`))}
      ${fine(clean(`Red flags: ${(post.red_flags || []).join(' ')} ${post.separation_note || ''}`))}
      ${g(post, 'forecast_review', 'available') ? fine(`Saved forecast from ${clean(post.forecast_review.saved_at)} reviewed separately for results, guidance and reaction.`) : ''}`;
    const rec = g(post, 'release', 'recency') || {}, lead = rec.state === 'probably_missing' ? `${rec.text} ` : '';
    return tile('earnings', 'What about earnings?', q.grade ? `Report quality ${q.grade}` : 'Report not graded', `${lead}Reported ${shortDate(g(post, 'release', 'date'))}. ${rx.text || ''}`, more, c);
  }
  return tile('earnings', 'What about earnings?', 'Insufficient Data', (pre || post || {}).reason || er.reason || 'No earnings view.', '', c);
}
const qgrid = (cards) => html`<div class="q-grid">${cards}</div>`;
function pendingGrid(c, note) {
  return html`${qgrid(QUESTIONS.map(([id, label]) => html`<div class="q-card" data-q="${id}"><p class="q-label">${label}</p><p class="q-val is-none">${note ? 'Not graded' : 'Grading…'}</p>${plain(id, c)}</div>`))}${note ? html`<p class="asof">${note}</p>` : ''}`;
}
/** "Four questions, answered separately": each graded by the research framework's own rules (/api/framework). */
export function fourQuestions(c) {
  const out = c.fw;
  let body;
  if (c.fwError) body = pendingGrid(c, `The four grades are not available right now: ${clean(c.fwError.message || 'no data').replace(/\.$/, '')}.`);
  else if (out === undefined) body = pendingGrid(c, '');
  else if (!out || out.available === false) body = pendingGrid(c, `The four grades are not available for this symbol: ${clean((out || {}).reason || 'no data').replace(/\.$/, '')}.`);
  else {
    const gaps = g(out, 'data', 'gaps') || [];
    // The combined verdict is said once, under "Taken together" further down, with its reasons beside it.
    body = html`${qgrid([businessTile(out.long_term, c), priceTile(out.long_term, c), tradeTile(out.swing, c), earningsTile(out.earnings, c)])}
      <p class="asof">The Optic Score below summarises trend and signals. These four are graded separately, each by its own stated rules (method ${out.method_version || ''}, policy ${g(out, 'policy', 'version') || ''}), and none has been shown to predict returns. "Insufficient Data" means evidence is missing, not that the answer is bad.${g(out, 'freshness', 'text') ? ` ${clean(out.freshness.text)}` : ''}${gaps.length ? ` Not loaded: ${clean(gaps.join('; '))}.` : ''}</p>`;
  }
  return html`<section class="section qsec" aria-labelledby="qs-h"><h2 class="t-h2" id="qs-h">Four questions, answered separately</h2>${body}</section>`;
}

/* ---------------- key figures; the bull case and the bear case; what to look at next ---------------- */
export function keyFigures(c) {
  const q = g(c.t, 'quote');
  if (!q || !fin(q.price)) return '';
  const rows = keyStatRows(q, g(c.t, 'company', 'short_interest'), c.phase);
  if (!OV_ESSENTIALS.some((id) => rows[id][1] !== null)) return '';
  return html`<section class="section" aria-labelledby="kf-h"><h2 class="t-h2" id="kf-h">Key figures</h2>${statList(rows, OV_ESSENTIALS)}
    <p class="asof">Select a label for what it means. All eighteen figures are under Advanced research below.</p></section>`;
}

export function casesSection(c) {
  if (!c.t) return '';
  const f = c.f, sym = c.sym, drv = drivers(c.t);
  const item = (x, withWhy) => html`<li><span class="cs-text">${x.text}</span>${withWhy && x.why ? html`<span class="cs-why">${x.why}</span>` : ''}${x.view ? html` <a class="textlink cs-ev" href="${hrefFor(x.view, sym)}" aria-label="Evidence for: ${x.text}">Evidence</a>` : ''}</li>`;
  const cols = html`<div class="cs-cols">
    <div><h3 class="case-h up">Bull case</h3>${f.pos.length ? html`<ul class="cs-list is-pos">${f.pos.map((x) => item(x, false))}</ul>` : html`<p class="t-muted">No bull-case point stands out in the data Optic holds.</p>`}</div>
    <div><h3 class="case-h down">Bear case</h3>${f.neg.length ? html`<ul class="cs-list is-neg">${f.neg.map((x) => item(x, true))}</ul>` : html`<p class="t-muted">No bear-case point stands out in the data Optic holds. That is not the same as no risk: every stock can fall.</p>`}</div></div>`;
  // folded below the Advanced level, with the count in the summary; open at Advanced and above (Classic)
  return html`<section class="section" aria-labelledby="cs-h"><h2 class="t-h2" id="cs-h">Bull case and bear case</h2>
    <details class="more-inline cs-fold" data-adv ${c.advanced ? 'open' : ''}><summary>Show the case for and against (${f.pos.length} for, ${f.neg.length} against)</summary><div class="how-body">${cols}</div></details>
    ${drv.length ? html`<details class="more-inline"><summary>What has been moving it recently</summary><div class="how-body">
      <ul class="cs-drv">${drv.map((x) => html`<li><span class="t-label">${x.kind}</span><span>${x.url ? html`<a class="textlink" href="${x.url}" target="_blank" rel="noopener noreferrer nofollow">${clean(x.text)}</a>` : clean(x.text)}</span>${x.note ? html`<span class="t-muted">${x.note}</span>` : ''}</li>`)}</ul>
      <p class="asof">None of these proves why the price moved. Prices also move on things no data feed records.</p></div></details>` : ''}
    <p class="asof">Listed from the data on this page by fixed rules, not ranked by importance and not written by a model. Not investment advice.</p></section>`;
}

export function nextSection(c) {
  if (!c.t) return '';
  const sym = c.sym, evs = events(c.t, c.advanced, c.today), steps = nextSteps(sym, c.t, c.f, c.fund, c.today);
  return html`<section class="section" aria-labelledby="nx-h"><h2 class="t-h2" id="nx-h">What should I look at next?</h2>
    <div class="nx-cols">
      <div><h3 class="t-label nx-h">Coming up</h3>
        ${evs.length ? html`<ul class="nx-events">${evs.map((e) => html`<li><span class="nx-date">${e.date ? shortDate(e.date) : ''}</span><span class="nx-what"><b>${clean(e.label)}</b>${e.detail ? html`<span class="t-muted">${clean(e.detail)}</span>` : ''}</span></li>`)}</ul>
          <p class="asof">Scheduled dates only. A date is not a forecast of what happens on it.</p>`
          : html`<p class="t-muted">No scheduled company events or economic releases in the data for the coming days.</p>`}</div>
      <div><h3 class="t-label nx-h">Research steps</h3>
        <ul class="nx-steps">${steps.map((s) => html`<li>${s.compare ? html`<a class="nx-step" href="#/compare?t=${encodeURIComponent(sym)}"><span>${s.text}</span><span class="nx-to">Compare ${'→'}</span></a>`
          : html`<a class="nx-step" href="${hrefFor(s.view, sym)}"><span>${s.text}</span><span class="nx-to">${TAB[s.view] || ''} ${'→'}</span></a>`}</li>`)}
          <li><button type="button" class="nx-step" data-v2-milo="Using the figures Optic has for ${sym}, what are the main things a long-term investor should understand about it, and what would change that picture?" data-v2-milo-ctx="${sym} Dossier, Overview: what to look at next" data-v2-milo-sym="${sym}"><span>Ask Milo a question about ${sym}</span><span class="nx-to">Ask Milo ${'→'}</span></button></li></ul>
        <p class="asof">Ask Milo writes a question for you to edit. Nothing is sent until you press Send.</p></div>
    </div></section>`;
}

/* ---------------- the Optic Score (the owner's refinement, 2026-10-25) ---------------- */
// One reading per horizon: the span, the score, what it means, what moved it, and how it is calculated behind one fold.
// Verified against app/analytics/swing.py verdict() and app/analytics/longterm.py:
// - "Conviction" is not a measured confidence. Short term it is a band of the composite's size (10, 30 and 50 points
//   from zero), long term a band of the points total; so the words here describe the reading's strength.
// - 50 is each model's neutral midpoint (a composite or a points total of zero). Neither model has been shown to
//   predict returns (the composite's own scale note; the validation programme of 2026-10-14), so 50 is not "no edge".
// - The long-term number was coloured at Classic's 55 and 45 while the model's own neutral band runs from about 42 to
//   56, so a neutral 43 showed red: each score is now coloured by its own model's bands.
const POS = 'pos', NEG = 'neg';
/** Up to three drivers by their pull on the score (`size`, in points of 0 to 100). When all three pull one way and
 *  the other side has a material one (2 points or more), it takes the third place, so a material negative is never
 *  left out behind smaller positives (owner's brief, 2026-10-25). */
export function pickDrivers(rows, size) {
  const by = rows.filter((r) => fin(size(r)) && Math.abs(size(r)) >= 0.5).sort((x, y) => Math.abs(size(y)) - Math.abs(size(x)));
  const top = by.slice(0, 3);
  [1, -1].forEach((sign) => {
    if (top.length < 3 || top.some((r) => Math.sign(size(r)) === sign)) return;
    const other = by.find((r) => Math.sign(size(r)) === sign && Math.abs(size(r)) >= 2);
    if (other) top[2] = other;
  });
  return top.sort((x, y) => Math.abs(size(y)) - Math.abs(size(x)));
}
/** The short-term reading: the swing composite (-100 to +100) on 0 to 100, which is 50 plus half the composite. */
export function shortScore(t, now = Date.now()) {
  const v = g(t, 'verdict'), p = g(t, 'pulse') || {};
  if (!v || !fin(v.composite_score)) return null;
  const c = v.composite_score, a = Math.abs(c), n = score100(c);
  const stance = String(v.stance || 'neutral'), side = c >= 10 ? POS : c <= -10 ? NEG : '';
  const lean = side === POS ? 'bullish' : 'bearish';
  const line = !side ? 'The inputs roughly cancel out: no lean either way.' : a >= 50 ? `The inputs lean strongly ${lean}.` : a >= 30 ? `The inputs lean ${lean}.` : `The inputs lean ${lean}, but only slightly.`;
  const why = {}; (g(t, 'why', 'reasons') || []).forEach((r) => { if (r && r.factor) why[r.factor] = r.headline; });
  const rows = (p.factors || []).map((f) => ({ key: f.key, label: f.label, score: f.score, weight: f.weight_pct, missing: !!f.unavailable || !fin(f.score), whyMissing: f.why_unavailable,
    pts: !f.unavailable && fin(f.score) && fin(f.weight_pct) ? (f.score * f.weight_pct) / 200 : null, note: why[f.key] || '' }));
  const drivers = pickDrivers(rows, (r) => r.pts)
    .map((r) => ({ label: r.label, pts: r.pts, detail: `Reads ${r.score > 0 ? '+' : ''}${num(r.score, 0)} with ${num(r.weight, 0)}% of the weight.${r.note ? ` ${clean(r.note)}.` : ''}` }));
  const missing = rows.filter((r) => r.missing);
  const notes = [];
  if (missing.length) notes.push(`${missing.map((r) => r.label).join(' and ')} had no data on this run${missing.some((r) => r.whyMissing) ? ` (${missing.map((r) => clean(r.whyMissing || 'reason not given')).join('; ')})` : ''}, so ${missing.length === 1 ? 'its' : 'their'} weight went to the other inputs. ${missing.length === 1 ? 'It is' : 'They are'} left out, not counted as neutral.`);
  if (g(v, 'pending_catalyst', 'pending')) notes.push('A scheduled event is still ahead, and nothing here predicts which way it resolves.');
  const age = Date.parse(t.generated_at || '');
  if (fin(age) && now - age > 60 * 60000) notes.push(`Worked out ${ago(t.generated_at, now)}; the inputs may have moved since.`);
  const nominal = (v.breakdown || []).filter((b) => fin(b.nominal_weight_pct)).map((b) => `${(rows.find((r) => r.key === b.component) || {}).label || b.component} ${num(b.nominal_weight_pct, 0)}%`);
  return { n, tone: side, label: capFirst(stance), line, drivers, notes, rows, nominal, band: [45, 55], priced: rows.filter((r) => !r.missing).length, total: rows.length };
}
/** The long-term reading: the trend model's points total on 0 to 100, with zero points at 50. */
export function longScore(lt, now = Date.now()) {
  const h = g(lt, 'holding');
  if (!lt) return { pending: true };
  if (lt.error || !h || h.error) return { unavailable: clean((h && h.error) || lt.error || 'no data') };
  const sc = h.conviction_scale || {}, th = sc.thresholds || { high: 40, moderate: 12, cautious: -12, low: -40 };
  const at = (s) => score100(s, sc.min_possible, sc.max_possible), s = h.conviction_score, n = at(s);
  if (n === null) return { unavailable: 'no score in the data' };
  const conv = String(h.conviction || ''), side = conv === 'high' || conv === 'moderate' ? POS : conv === 'cautious' || conv === 'low' ? NEG : '';
  const label = { high: 'Strongly positive', moderate: 'Positive', neutral: 'No clear lean', cautious: 'Negative', low: 'Strongly negative' }[conv] || capFirst(conv);
  const facs = (h.conviction_factors || []).filter((f) => fin(f.points));
  const raw = facs.reduce((x, f) => x + f.points, 0), q = h.data_quality || {}, capped = Math.abs(raw - s) > 0.6;
  const k = s >= 0 ? 50 / (sc.max_possible || 100) : 50 / Math.abs(sc.min_possible || -100);   // one model point on the 0 to 100 scale
  const drivers = pickDrivers(facs, (f) => f.points * k)
    .map((f) => ({ label: f.label, pts: capped ? null : f.points * k, model: f.points, detail: clean(f.detail || '') }));
  const missing = [], trend = h.long_trend || {}, reliable = q.reliable !== false;
  if (trend.above_200w_sma === null || trend.above_200w_sma === undefined) missing.push('the 200-week trend');
  if (!fin(h.excess_cagr_5y_pct) || !reliable) missing.push('the five-year return against the S&P 500');
  if (!fin(g(h, 'risk', 'sharpe_proxy')) || !reliable) missing.push("the past year's return for the risk taken");
  if (!fin(g(h, 'valuation', 'forward_pe'))) missing.push('valuation (no forward P/E in the feed)');
  const notes = [];
  if (missing.length) notes.push(`Not scored for lack of data, so ${missing.length === 1 ? 'it adds' : 'they add'} nothing either way: ${missing.join(', ')}. The score rests on the rest.`);
  if (!reliable) notes.push(`Only ${num(q.history_years, 1)} years of usable price history, so the model holds the score between ${num(at(-25), 0)} and ${num(at(25), 0)}.`);
  const age = Date.parse(lt.generated_at || '');
  if (fin(age) && now - age > 24 * 3600000) notes.push(`Worked out ${ago(lt.generated_at, now)}; prices may have moved since.`);
  return { n, tone: side, label, line: clean(h.plan || ''), phase: capFirst(g(h, 'long_trend', 'phase') || ''), drivers, notes, factors: facs, capped, k,
    band: [at(th.cautious), at(th.moderate)], cuts: { strongNeg: at(th.low), neg: at(th.cautious), pos: at(th.moderate), strongPos: at(th.high) }, min: sc.min_possible, max: sc.max_possible };
}
/** Where the two readings point different ways, and when a high long-term score sits beside a stretched price. */
export function scoreNotes(s, l, lt) {
  const out = [];
  if (s && l && l.n !== undefined && s.tone && l.tone && s.tone !== l.tone) {
    out.push(`The two point different ways. That is common: the short-term reading weighs the last few weeks of trading, the long-term one up to five years of the price's path.`);
  }
  const val = valuationRead(lt);
  if (l && fin(l.n) && l.n >= 60 && val && val.tone === 'bad') out.push(`The long-term score reads the price's path, not its value. It does not say the price is low: at ${num(val.cur, 1)} times earnings against ${num(val.med, 1)} on average, the price asks more than usual.`);
  return out;
}
const ptsWord = (x) => `${x > 0 ? '+' : x < 0 ? '−' : ''}${num(Math.abs(x), 0)}`;
/** A 0 to 100 track: the model's neutral band shaded, a mark at 50 and one at the score. Drawn for the eye only; the
 *  number and the words carry it for a screen reader. */
function scaleBar(n, band, tone) {
  const at = (x) => `${Math.max(0, Math.min(100, x)).toFixed(1)}%`;
  return html`<span class="osc-scale" aria-hidden="true"><span class="osc-band" style="left:${at(band[0])};width:${at(band[1] - band[0])}"></span><span class="osc-mid"></span><span class="osc-dot ${tone}" style="left:${at(n)}"></span></span><span class="osc-ends" aria-hidden="true"><span>0</span><span>50</span><span>100</span></span>`;
}
function driverList(ds, model) {
  if (!ds.length) return '';
  return html`<ul class="osc-drv" aria-label="What moved it most">${ds.map((d) => { const x = fin(d.pts) ? d.pts : d.model; return html`<li><span class="osc-drv-l">${d.label}</span><span class="osc-drv-v ${x >= 0 ? POS : NEG}">${fin(d.pts) ? ptsWord(d.pts) : `${ptsWord(d.model)} model points`}</span><span class="osc-drv-d">${d.detail}</span></li>`; })}</ul>`;
}
function scoreCard({ id, span, n, tone, label, line, meta, drivers: ds, notes, band, method, empty }) {
  return html`<div class="osc-card" aria-labelledby="osc-${id}-h">
    <h3 class="osc-span" id="osc-${id}-h">${span}</h3>
    ${empty ? html`<p class="osc-n is-none">n/a</p><p class="t-muted">${empty}</p>` : html`
      <p class="osc-n ${tone}">${num(n, 0)}<small> of 100</small></p>
      ${scaleBar(n, band, tone)}
      <p class="osc-label">${label}${meta ? html`<span class="t-muted">, ${meta}</span>` : ''}</p>
      ${line ? html`<p class="osc-line">${line}</p>` : ''}
      ${driverList(ds)}
      ${notes.map((x) => html`<p class="osc-note">${x}</p>`)}`}
    ${method}</div>`;
}
export function scoreSection(c) {
  const t = c.t; if (!t) return '';
  const s = shortScore(t, c.now), l = longScore(c.lt, c.now), sym = c.sym;
  if (!s && (!l || l.pending || l.unavailable)) return '';
  const sMethod = s ? html`<details class="more-inline osc-how"><summary>How this is calculated</summary><div class="how-body">
      <p>Four inputs, each scored from −100 to +100, are averaged with fixed weights (${s.nominal.join(', ')}). The average is placed on 0 to 100, so an average of zero is 50.</p>
      <p>An input with no data is left out and the others' weights grow to fill its share. After a material news event, part of the momentum weight moves to news.</p>
      <p>55 and above reads leaning bullish, 65 and above bullish; 45 and below leaning bearish, 35 and below bearish; in between, neutral.</p>
      <table class="t osc-t"><thead><tr><th scope="col">Input</th><th scope="col">Reading</th><th scope="col">Weight</th><th scope="col">Points</th></tr></thead>
        <tbody>${s.rows.map((r) => html`<tr><th scope="row">${r.label}</th><td>${r.missing ? 'no data' : `${r.score > 0 ? '+' : ''}${num(r.score, 0)}`}</td><td>${r.missing ? 'n/a' : `${num(r.weight, 0)}%`}</td><td>${fin(r.pts) ? ptsWord(r.pts) : 'n/a'}</td></tr>`)}</tbody></table>
      <p class="t-muted">Points are each input's share of the distance from 50. Options and Positioning are both read from one option chain, so their agreement is one source, not two. Optic's own evaluation has not found that this blend beats a single momentum reading.</p>
      <p>${tabLink(sym, 'swing', 'The full breakdown, on Options')}</p></div></details>` : '';
  const lok = l && !l.pending && !l.unavailable;
  const lMethod = lok ? html`<details class="more-inline osc-how"><summary>How this is calculated</summary><div class="how-body">
      <p>The model adds and subtracts points for the 200-week and 40-week price trends, the five-year return against the S&amp;P 500, the past year's return for the risk taken, the forward P/E, a deep fall from the high while the long trend holds, the dividend and any resolved news event. The total can run from ${ptsWord(l.min)} to ${ptsWord(l.max)}, and it is placed on 0 to 100 with zero points at 50.</p>
      <p>About ${num(l.cuts.pos, 0)} and above reads positive, ${num(l.cuts.strongPos, 0)} and above strongly positive; about ${num(l.cuts.neg, 0)} and below negative, ${num(l.cuts.strongNeg, 0)} and below strongly negative; in between, no clear lean.</p>
      <table class="t osc-t"><thead><tr><th scope="col">Factor</th><th scope="col">Model points</th><th scope="col">What it found</th></tr></thead>
        <tbody>${l.factors.map((f) => html`<tr><th scope="row">${f.label}</th><td>${ptsWord(f.points)}</td><td>${clean(f.detail || '')}</td></tr>`)}</tbody></table>
      <p>${tabLink(sym, 'long', 'The full breakdown, on Investing')}</p></div></details>` : '';
  const notes = scoreNotes(s, lok ? l : null, c.lt);
  return html`<section class="section osc" aria-labelledby="osc-h"><div class="section-head"><div><h2 class="t-h2" id="osc-h">Optic Score</h2>
      <p class="section-sub">Two separate readings from different inputs over different spans, so they are not directly comparable.</p></div></div>
    <div class="osc-grid">
      ${s ? scoreCard({ id: 'short', span: 'Short term: 2 to 8 weeks', n: s.n, tone: s.tone, label: s.label, line: s.line, drivers: s.drivers, notes: s.notes, band: s.band, method: sMethod })
        : scoreCard({ id: 'short', span: 'Short term: 2 to 8 weeks', empty: 'No short-term reading in the data for this symbol.', method: '' })}
      ${lok ? scoreCard({ id: 'long', span: 'Long term: several years', n: l.n, tone: l.tone, label: l.label, meta: l.phase, line: l.line, drivers: l.drivers, notes: l.notes, band: l.band, method: lMethod })
        : scoreCard({ id: 'long', span: 'Long term: several years', empty: l && l.unavailable ? `The long-term score is not available: ${l.unavailable.replace(/\.$/, '')}.` : 'Working out the long-term score…', method: '' })}
    </div>
    ${notes.map((x) => html`<p class="osc-both">${x}</p>`)}
    <p class="asof">50 is each model's neutral midpoint, where its inputs balance; it is not a measured break-even. Neither score is a probability, an expected return or a forecast, and neither has been shown to predict returns. Not a recommendation to buy or sell.</p></section>`;
}

/* ---------------- Optic's read: the short-term signals, assembled from the payload (Classic's renderOpticPulse) ---------------- */
function catalystLine(cat) {
  if (!cat || cat.material !== true) return '';
  const h = cat.freshest_hours, n = cat.count || 1;
  const when = !fin(h) ? 'recently' : h < 1.5 ? 'an hour ago' : h < 24 ? `${Math.round(h)} hours ago` : h < 42 ? 'a day ago' : `${Math.round(h / 24)} days ago`;
  return html`<p class="pl-cat"><b>${n === 1 ? 'One headline' : `${n} headlines`} tagged ${(cat.kinds || []).join(' and ')}</b>, ${n === 1 ? 'filed' : 'the freshest'} ${when}. The chart readings below are measured over windows that mostly predate it, so momentum carries less weight here than usual.</p>`;
}
function pendingLine(pend) {
  if (!pend || pend.pending !== true) return '';
  const n = pend.count || 1;
  return html`<p class="pl-cat is-pending"><b>A ${(pend.kinds || []).join(' and ')} event is still ahead</b>, flagged by ${n === 1 ? 'one headline' : `${n} headlines`}. Nothing below predicts which way it resolves, so conviction is held short of high until it does.</p>`;
}
/** "Read more": what carries the read, what is against it, what its conviction rests on and what it cannot tell you
 *  (Classic's pulseReadMore), every clause a figure already in the payload. */
export function readMore(p) {
  const live = ((p && p.factors) || []).filter((f) => !f.unavailable && f.score !== null && f.score !== undefined);
  if (!live.length) return '';
  const stance = String(p.stance || 'neutral'), side = stance === 'bullish' ? 1 : stance === 'bearish' ? -1 : 0;
  const pull = (f) => (Number(f.score) || 0) * (Number(f.weight_pct) || 0) / 100, sg = (n) => `${n > 0 ? '+' : ''}${num(n, 0)}`;
  const ranked = live.slice().sort((a, b) => Math.abs(pull(b)) - Math.abs(pull(a))), top = ranked[0], second = ranked[1];
  const also = second && Math.abs(pull(second)) >= Math.abs(pull(top)) * 0.4 && Math.sign(Number(second.score)) === Math.sign(Number(top.score));
  const parts = [html`<p><b>${top.label} is doing most of the work</b>, at ${sg(top.score)} on ${num(top.weight_pct, 0)}% of the weight${also ? `, with ${second.label} behind it at ${sg(second.score)} on ${num(second.weight_pct, 0)}%` : ''}. ${clean(top.measures || '')}</p>`];
  const opposed = side ? ranked.filter((f) => Math.sign(Number(f.score)) === -side && Math.abs(pull(f)) >= 1) : [];
  if (opposed.length) parts.push(html`<p><b>Against it:</b> ${opposed.map((f) => `${f.label} at ${sg(f.score)} on ${num(f.weight_pct, 0)}%`).join(', ')}.</p>`);
  else if (side) {
    const al = (f) => side * pull(f), weakest = live.slice().sort((a, b) => al(a) - al(b))[0];
    parts.push(al(weakest) < 0
      ? html`<p><b>Nothing material is pulling the other way.</b> ${weakest.label} is the nearest to it at ${sg(weakest.score)}, which on ${num(weakest.weight_pct, 0)}% of the weight is close to no opinion rather than a disagreement.</p>`
      : html`<p><b>Every input that had data points the same way.</b> The weakest of them is ${weakest.label} at ${sg(weakest.score)} on ${num(weakest.weight_pct, 0)}% of the weight.</p>`);
  } else parts.push(html`<p><b>The inputs do not agree on a direction</b>, which is what a neutral reading is. It is not a forecast of no movement.</p>`);
  const bits = [];
  if (fin(p.agreement_pct)) bits.push(`${num(p.agreement_pct, 0)}% of the inputs point the same way`);
  if (p.factors_priced && p.factors_total) bits.push(`${p.factors_priced} of ${p.factors_total} had data`);
  if (bits.length && p.conviction) {
    const held = p.pending_catalyst && p.pending_catalyst.pending === true ? ' It is held short of high while a scheduled event is still ahead, because nothing measured here predicts which way that resolves.' : '';
    const chain = live.filter((f) => f.key === 'gamma' || f.key === 'flow');
    const shared = chain.length === 2 ? ` ${chain.map((f) => f.label).join(' and ')} are both read off the same option chain, so those two agreeing is less corroboration than two separate ticks look like.` : '';
    parts.push(html`<p><b>${capFirst(convictionWords(p.conviction))}</b>: ${bits.join(' and ')}.${held} Conviction is agreement between the inputs, not a probability.${shared}</p>`);
  }
  const missing = (p.factors || []).filter((f) => f.unavailable), limits = [];
  (p.conflicts || []).forEach((x) => { const s = typeof x === 'string' ? x : (x && (x.text || x.note)) || ''; if (s) limits.push(clean(s)); });
  if (missing.length) limits.push(`${missing.map((f) => f.label).join(' and ')} had no data on this run (${missing.map((f) => f.why_unavailable || 'reason not given').join('; ')}). A missing input redistributes its weight rather than counting as zero, so the remaining inputs each carry more than the percentage shown.`);
  limits.push('These are weights this app chose, not a fitted model. The panel below shows each input\'s own measurement, and the skill note there is this project\'s own finding about how much the blend is worth.');
  parts.push(html`<p class="t-muted">${limits.join(' ')}</p>`);
  return html`<details class="more-inline pl-more"><summary>Read more</summary><div class="how-body">${parts}</div></details>`;
}
/** A diverging bar: the middle is zero, a cell for every 20 points out to either side. */
function bar(score, direction) {
  if (!fin(Number(score)) || score === null) return html`<span class="pl-bar is-none" aria-hidden="true"></span>`;
  const n = Math.max(0, Math.min(5, Math.round(Math.abs(Number(score)) / 20))), neg = Number(score) < 0;
  const cells = (on) => Array.from({ length: 5 }, (_, i) => html`<i class="${on(i) ? 'on' : ''}"></i>`);
  return html`<span class="pl-bar tone-${direction === 'up' ? 'up' : direction === 'down' ? 'down' : 'flat'}" aria-hidden="true"><span class="pl-half">${cells((i) => neg && 4 - i < n)}</span><i class="pl-mid"></i><span class="pl-half">${cells((i) => !neg && i < n)}</span></span>`;
}
export function opticRead(c) {
  const t = c.t, p = t && t.pulse; if (!p) return '';
  const stance = String(p.stance || 'neutral'), skill = p.skill || {}, dg = t.digest || {}, story = dg.story || null, src = dg.sources || {};
  const fresh = ago(dg.as_of, c.now), tiers = g(t, 'news', 'tiers') || [], tier = story && story.tier ? tiers.find((x) => x.id === story.tier) : null;
  return html`<div class="ovx-block pl" aria-labelledby="pl-h"><div class="pl-top"><h3 class="t-label" id="pl-h">Optic's read</h3>${fresh ? html`<span class="asof">Updated ${fresh}</span>` : ''}</div>
    <p class="pl-lede is-${stance}">${clean(dg.lede || p.stance_label || stance.toUpperCase())}</p>
    ${catalystLine(p.catalyst)}${pendingLine(p.pending_catalyst)}${readMore(p)}
    ${story && story.title ? html`<p class="pl-story">${tier ? html`<span class="chip-tag pl-tier" title="${story.tier_why || ''}">${tier.label}</span>` : ''}<a class="textlink" href="${story.url || '#'}" target="_blank" rel="noopener noreferrer">${clean(story.title)}</a><span class="t-muted">${[story.publisher, story.age_words, story.catalyst].filter(Boolean).join(', ')}</span></p>` : ''}
    <div class="pl-meta">${p.conviction ? html`<span>${convictionWords(p.conviction)}</span>` : ''}${fin(p.agreement_pct) ? html`<span>${num(p.agreement_pct, 0)}% of inputs agree</span>` : ''}
      ${src.count ? html`<details class="more-inline pl-src"><summary>${src.count} source${src.count === 1 ? '' : 's'}</summary><div class="how-body"><p>${(src.names || []).join(', ')}</p></div></details>` : ''}</div>
    <div class="pl-bars" role="group" aria-label="How the ${p.factors_total || 5} inputs scored">${(p.factors || []).map((f) => html`<div class="pl-factor${f.unavailable ? ' is-none' : ''}">
      <span class="pl-flabel" title="${f.measures || ''}">${f.label}</span>${bar(f.unavailable ? null : f.score, f.direction)}<span class="pl-fval">${f.unavailable ? 'no data' : `${f.score > 0 ? '+' : ''}${num(f.score, 0)}`}</span></div>`)}</div>
    <p class="asof">Each input scores from -100 to +100: a bar fills right of the line when the input leans bullish and left when it leans bearish.</p>
    <p class="pl-skill">${clean(skill.text || '')}</p>
    ${p.factors_priced < p.factors_total ? html`<p class="asof">${p.factors_priced} of ${p.factors_total} inputs had data. A missing input redistributes its weight rather than counting as zero.</p>` : ''}
    ${dg.method ? how(html`<p>${clean(dg.method)}</p>`) : ''}</div>`;
}

/* ---------------- Advanced research: one press away, open at the Advanced level (Classic) ---------------- */
function restBlock(c) {
  const t = c.t, sym = c.sym, q = t.quote || {}, news = t.news || {}, p = t.pulse || {}, st = c.stars;
  const lo = q.fifty_two_low, hi = q.fifty_two_high, band = fin(lo) && fin(hi) && hi > lo && fin(q.price) ? Math.round(((q.price - lo) / (hi - lo)) * 100) : null;
  const days = news.days_to_earnings;
  const cards = [
    ['chart', 'Chart', band === null ? null : `${band}%`, band === null ? '52-week range unavailable' : 'of its 52-week range'],
    ['swing', 'Options', p.stance ? capFirst(String(p.stance)) : null, p.conviction ? convictionWords(p.conviction) : 'setup, levels and the chain'],
    ['earnings', 'Earnings', news.earnings_date ? fullDate(news.earnings_date) : null, fin(days) ? `in ${days} days` : 'no date published'],
    ...(c.fund ? [] : [['financials', 'Financials', fin(q.revenue_growth) ? `${num(q.revenue_growth * 100, 1)}%` : null, fin(q.profit_margin) ? `revenue growth, ${num(q.profit_margin * 100, 1)}% margin` : 'revenue growth']]),
    ['news', 'News', news.article_count ? String(news.article_count) : null, news.overall_tone ? `headlines, ${news.overall_tone}` : 'headlines'],
    st && st.available ? ['long', 'Investing', `${st.stars} of 5 stars`, `Optic star rating, ${String(st.word || '').toLowerCase()}`] : ['long', 'Investing', fin(q.trailing_pe) ? num(q.trailing_pe, 1) : null, 'trailing P/E, valuation and holding case'],
  ];
  return html`<div class="ovx-block" aria-labelledby="rest-h"><h3 class="t-label" id="rest-h">The rest of this ticker</h3>
    <p class="asof">One reading from each section, so the row says what is there rather than only where to click.</p>
    <ul class="ovx-cards">${cards.map(([view, label, value, note]) => html`<li><a class="ovx-card" href="${hrefFor(view, sym)}"><span class="t-label">${label}</span><b class="${value === null ? 't-muted' : ''}">${value === null ? 'n/a' : value}</b><span class="t-muted">${note}</span></a></li>`)}</ul></div>`;
}
function headlines(c) {
  const news = c.t.news || {}, heads = (news.articles || []).slice(0, 3);
  if (!heads.length) return '';
  return html`<div class="ovx-block" aria-labelledby="hl-h"><h3 class="t-label" id="hl-h">Latest headlines</h3>
    <ul class="plain">${heads.map((a) => html`<li><a class="textlink" href="${a.url}" target="_blank" rel="noopener">${clean(a.title)}</a> <span class="t-muted">${a.publisher || ''}${a.age_words ? `, published ${a.age_words}` : ''}</span></li>`)}</ul>
    <p>${tabLink(c.sym, 'news', `All ${news.article_count || heads.length} headlines`)}</p></div>`;
}
function methodNote(t) {
  const built = ago(t.generated_at), src = t.data_source === 'tradier' ? 'Tradier, with Yahoo Finance where it has no data' : 'Yahoo Finance';
  return html`<div class="ovx-block"><h3 class="t-label">How this page is built</h3><ul class="plain">
    <li>Every sentence above comes from the figures on this page by fixed rules. No AI model writes them, so the same data gives the same words.</li>
    <li>Business figures come from the company's filed statements via Yahoo Finance. The latest fiscal year can be months old, and the latest quarter is shown beside it when the two disagree.</li>
    <li>Price figures are daily closes from ${src}${built ? `, gathered ${built}` : ''}. Outside market hours the price is the last close.</li>
    <li>The wording uses fixed cut-offs, chosen for plain language rather than taken from research: business changes under 1% either way are "roughly flat", price changes under 2% "little changed"; a year and the last three months are called out as pointing different ways when one is up at least 5% and the other down at least 5%; an earnings report within 45 days is listed as a risk; a price 20% or more below its highest close is listed as a risk; a price-to-earnings ratio 20% or more above or below the company's own average over at least three fiscal years is called asking more or less than usual.</li>
    <li>Optic's short-term signal score, its star rating and its options readings are models. Each carries its own method and limits on its page.</li>
    <li>Nothing here is a recommendation to buy or sell.</li></ul></div>`;
}
export function advancedSection(c) {
  const t = c.t; if (!t) return '';
  const rows = keyStatRows(t.quote, g(t, 'company', 'short_interest'), c.phase), ids = Object.keys(rows).filter((id) => rows[id][1] !== null);
  return html`<section class="section ovx-adv" aria-label="Advanced research"><details class="adv-fold" data-adv ${c.advanced ? 'open' : ''}>
    <summary><span class="t-h2">Advanced research</span><span class="section-sub">Optic's short-term signal score, all key statistics, every section at a glance, headlines and method</span></summary>
    ${opticRead(c)}
    ${ids.length ? html`<div class="ovx-block" aria-labelledby="ks-h"><h3 class="t-label" id="ks-h">Key stats</h3>${statList(rows, ids)}</div>` : ''}
    ${restBlock(c)}${headlines(c)}${methodNote(t)}</details></section>`;
}

/** The context every section reads, built once per paint. */
export function context({ sym, t, fw, fwError, lt, stars, fund, advanced, phase, now = Date.now() }) {
  const price = t ? priceRead(t, { index: /^\^/.test(sym) }) : null;
  return { sym, t, fw, fwError, lt, stars, fund, advanced, phase, now, today: new Date(now), index: /^\^/.test(sym), price,
    f: t ? factors(t, { lt, stars, price, fund, today: new Date(now) }) : { pos: [], neg: [] } };
}

/** The stage reading in Classic's words: "Stage 3 · Topping" and its short transition ("breakdown"). */
export function stageWords(r) {
  if (!r || r.available !== true) return null;
  return { main: `Stage ${r.stage} · ${r.name || ''}`.trim(), tag: r.transition_short || '', stage: r.stage,
    about: [r.explain, r.transition, r.limits].filter(Boolean).join(' '), aria: `${r.label || `Stage ${r.stage}`}${r.transition ? `. ${r.transition}` : ''}`,
    ask: (sym) => `Explain Weinstein stage (Stage ${r.stage} (${r.name})${r.transition_short ? `, ${r.transition_short}` : ''}) for ${sym} on the Overview page: what it measures, why someone would use it, what this value suggests, and what it cannot tell me.` };
}

/** For a fund, the risk Classic's takeaways named: the first point against it the page found (Classic parity B6a.6,
 *  kept when the Overview port of 2026-10-25 replaced the rest of B6a's research module). */
export function fundRisk(sym, f) {
  const r = f && f.neg[0];
  if (!r) return '';
  return html`<p class="ovx-risk"><b>A risk to weigh: ${r.text}.</b> ${r.why || ''}${r.view ? html` ${tabLink(sym, r.view, `The evidence, on ${TAB[r.view]}`)}` : ''}</p>`;
}
