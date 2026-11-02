// Dossier, Overview: the Simple Analysis (post-demo Phase 06, directive 06 section 2). The three questions a beginner
// asks, answered from the figures the Overview has already loaded, by fixed rules: What's happening? Why does it
// matter? What else should I know? Worded for the reader's knowledge level (Phase 05, app/knowledge.py's five
// levels): the level changes the words and how much is explained, never a figure, a caveat or a source.
//
// No model writes this and nothing is fetched for it. Every figure is one the page already holds (the quote, the
// chart's closes, Financials, Investing, Earnings), read the way overview-research.js reads it; an estimate is called
// an estimate, a model's reading is named as a model's, and what is missing is said. Advanced Analysis replaces this
// on the same page (pages/dossier.js); the two are never shown together.
import { html } from '../core/dom.js';
import { num, signed, shortDate, fullDate, capFirst } from '../core/format.js';
import { sessionFreshness } from '../core/marketTime.js';
import { hrefFor } from '../nav.js';
import { icon } from '../ui/icons.js';
import * as OR from './overview-research.js';

const fin = (v) => typeof v === 'number' && Number.isFinite(v);
const g = (o, ...ks) => ks.reduce((x, k) => (x && typeof x === 'object' ? x[k] : undefined), o);
const pct = (v, dp = 0) => `${num(Math.abs(v), dp)}%`;
const lowerFirst = (s) => { const t = String(s || ''); return /^[A-Z][a-z]/.test(t) ? t.charAt(0).toLowerCase() + t.slice(1) : t; };
const up = (x) => (x >= 0 ? 'up' : 'down');

/** The level's own words, falling back toward the middle: Expert to Advanced to Intermediate, New to Beginner. */
export function say(level, w) {
  const order = { new: ['new', 'beginner', 'intermediate'], beginner: ['beginner', 'intermediate'], advanced: ['advanced', 'intermediate'],
    expert: ['expert', 'advanced', 'intermediate'] }[level] || ['intermediate'];
  for (const k of order) if (w[k] !== undefined) return typeof w[k] === 'function' ? w[k]() : w[k];
  return '';
}

/** What the Simple Analysis says, gathered once per paint from the Overview's payloads. `price` and `f` are the
 *  page's own readings (overview-research.js priceRead and factors), so the year's change here is the chart's. */
export function simpleFacts({ sym, kind, t, lt, quote, session, earnings, price, f, today = new Date() }) {
  const q = quote || g(t, 'quote') || {}, fn = g(t, 'company', 'financials') || {}, gr = fn.growth || {}, m = fn.margins || {};
  const prof = g(session, 'profile') || {}, vh = g(lt, 'holding', 'valuation_history') || {};
  const k = kind === 'fund' || kind === 'index' || kind === 'crypto' ? kind : 'company';
  const name = String(q.name || prof.name || sym || '').replace(/ USD$/, '');
  const val = k === 'company' ? OR.valuationRead(lt) : null;
  const net = fn.available && fin(m.net_pct) ? m.net_pct : fin(q.profit_margin) ? q.profit_margin * 100 : null;
  const ne = t ? OR.earningsNext(t, today) : null, im = g(earnings, 'implied') || {};
  const pe = val ? val.cur : fin(q.trailing_pe) && q.trailing_pe > 0 ? q.trailing_pe : null;
  // the first point against it that the other two answers do not already make: the report and the price's own fall
  // are said there, the valuation when it is, and a loss when the business line says so
  const risk = ((f || {}).neg || []).find((x) => x.view !== 'earnings' && x.view !== 'chart' && !(val && x.view === 'long' && /own history/.test(x.text))
    && !/^The company lost money/.test(x.text)) || null;
  return {
    sym, kind: k, name, price: fin(q.price) ? q.price : null, chg: fin(q.change_pct) ? q.change_pct : null,
    regular: !!g(session, 'session', 'is_regular'), fresh: q && fin(q.price) ? sessionFreshness(q).text : '',
    yr: price && fin(price.yr) ? price.yr : null, m3: price && fin(price.m3) ? price.m3 : null, off: price && fin(price.off) ? price.off : null,
    span: (price && price.span) || 'over the past year', fullYear: !price || !price.span || price.span === 'over the past year',
    finAvailable: !!fn.available, rev: fn.available && fin(gr.revenue_yoy_pct) ? gr.revenue_yoy_pct : null,
    ni: fn.available && fin(gr.net_income_yoy_pct) ? gr.net_income_yoy_pct : null, net,
    gross: fn.available && fin(m.gross_pct) ? m.gross_pct : null, op: fn.available && fin(m.operating_pct) ? m.operating_pct : null,
    qRev: fin(q.revenue_growth) ? q.revenue_growth * 100 : null,
    fy: (fn.annual_fiscal || [])[0] || '', fyEnd: (fn.annual_periods || [])[0] || '',
    pe, peMed: val ? val.med : null, peYears: val ? val.years : null, peTone: val ? val.tone : null, prem: val ? val.prem : null,
    peLow: fin(vh.low_pe) ? vh.low_pe : null, peHigh: fin(vh.high_pe) ? vh.high_pe : null,
    fwdPe: fin(q.forward_pe) && q.forward_pe > 0 ? q.forward_pe : null, losing: fin(net) && net < 0,
    report: ne && fin(ne.days) && ne.days >= 0 ? ne : null,
    implied: im.available && fin(im.implied_move_pct) ? { pct: im.implied_move_pct, expiry: im.expiry } : null,
    risk, category: prof.category || '', family: prof.fund_family || '',
    holdPe: fin(q.trailing_pe) ? q.trailing_pe : null, yieldPct: fin(q.dividend_yield) ? q.dividend_yield * 100 : null,
    vol: fin(g(lt, 'holding', 'risk', 'annualised_vol_pct')) ? lt.holding.risk.annualised_vol_pct : null,
    ddNow: fin(g(lt, 'holding', 'drawdown', 'current_drawdown_pct')) ? lt.holding.drawdown.current_drawdown_pct : null,
  };
}

/* ---------------- what's happening ---------------- */
function subject(F, L) {
  if (F.kind === 'index') return say(L, { new: `The ${F.name}`, beginner: 'The index', intermediate: 'The index' });
  if (F.kind === 'crypto') return say(L, { new: `${F.name}'s price`, intermediate: 'The price' });
  if (F.kind === 'fund') return say(L, { new: `${F.sym}'s price`, beginner: "The fund's price", intermediate: 'The fund' });
  return say(L, { new: `${F.sym}'s share price`, beginner: 'The share price', intermediate: 'The shares' });
}
function priceLines(F, L) {
  if (!fin(F.yr)) {
    return [say(L, { new: 'There is not enough price history yet to say how the price has moved over time.', intermediate: 'Not enough price history to describe the trend.', expert: 'Insufficient price history for a trend.' })];
  }
  const S = subject(F, L), yr = F.yr, off = F.off, m3 = F.m3, near = !fin(off) || off > -3;
  const lead = Math.abs(yr) < 2 ? 'about where it was' : `${up(yr)} ${pct(yr)}`;
  const out = [say(L, {
    new: () => `${S} is ${Math.abs(yr) < 2 ? `little changed ${F.span}` : `${up(yr)} ${pct(yr)} ${F.span}`}. ${near ? 'It is close to the highest price it closed at in that time.' : `It is ${pct(off)} below the highest price it closed at in that time.`}`,
    beginner: () => `${S} is ${lead} ${F.span}, ${near ? 'close to its highest close of that period' : `${pct(off)} below its highest close of that period`}.`,
    intermediate: () => `${S} ${F.kind === 'company' ? 'are' : 'is'} ${Math.abs(yr) < 2 ? 'little changed' : `${up(yr)} ${pct(yr, 1)}`} ${F.span}, ${near ? 'near' : `${pct(off, 1)} below`} ${F.kind === 'company' ? 'their' : 'its'} highest close of the period.`,
    advanced: () => `${signed(yr, 1)} ${F.span}${fin(m3) ? `, ${signed(m3, 1)} over the last three months` : ''}; ${fin(off) && off <= -0.05 ? `${signed(off, 1)} from` : 'at'} the period's highest close.`,
    expert: () => `${F.fullYear ? '1Y' : capFirst(F.span.replace(/^over the /, ''))} ${signed(yr, 1)}${fin(m3) ? `, 3M ${signed(m3, 1)}` : ''}, ${fin(off) ? signed(off, 1) : 'n/a'} from the period high close.`,
  })];
  // a year and the last three months pointing different ways is the one thing a beginner would miss (overview-research
  // priceRead's own cut-offs: 5% each way)
  if (fin(m3) && ((yr >= 5 && m3 <= -5) || (yr <= -5 && m3 >= 5))) {
    out.push(say(L, { new: `But over the last three months it has ${m3 < 0 ? 'fallen' : 'risen'} ${pct(m3)}, so the recent direction is the other way.`,
      beginner: `Over the last three months, though, it has ${m3 < 0 ? 'fallen' : 'risen'} ${pct(m3)}.`, intermediate: `The last three months point the other way: ${signed(m3, 1)}.`,
      advanced: '', expert: '' }));
  }
  return out;
}
function todayLine(F, L) {
  if (!fin(F.chg)) return '';
  const c = F.chg, d = up(c);
  if (F.kind === 'crypto') return say(L, { new: `It is ${d} ${pct(c, 1)} on the day.`, intermediate: `${capFirst(d)} ${pct(c, 1)} on the day.`, advanced: `${signed(c, 2)} on the day.` });
  if (F.regular) return say(L, { new: `So far today it is ${d} ${pct(c, 1)}.`, beginner: `Today it is ${d} ${pct(c, 1)} so far.`, intermediate: `${capFirst(d)} ${pct(c, 1)} so far today.`, advanced: `${signed(c, 2)} so far today.`, expert: `${signed(c, 2)} intraday.` });
  return say(L, { new: `On its last trading day it ended ${d} ${pct(c, 1)}.`, beginner: `It closed ${d} ${pct(c, 1)} on its last trading day.`, intermediate: `${capFirst(d)} ${pct(c, 1)} at the last close.`,
    advanced: `${signed(c, 2)} on the last session.`, expert: `${signed(c, 2)} last session.` });
}
export function happening(F, L) {
  if (!fin(F.price)) return [say(L, { new: `No price came back for ${F.sym} just now, so there is nothing to describe yet.`, intermediate: `No quote for ${F.sym} right now.` })];
  return [...priceLines(F, L), todayLine(F, L)].filter(Boolean);
}

/* ---------------- why does it matter ---------------- */
const verb = (x) => (x >= 1 ? 'grew' : x <= -1 ? 'fell' : 'was roughly flat');
const rose = (x) => (x >= 1 ? 'rose' : x <= -1 ? 'fell' : 'was roughly flat');
function businessLine(F, L) {
  if (!F.finAvailable && !fin(F.net)) {
    return say(L, { new: `Optic could not read ${F.sym}'s financial statements, so there is nothing to say yet about the business itself. That is missing information, not a bad result.`,
      intermediate: 'Its financial statements could not be read here, so the business is not described. That is missing data, not a bad result.', expert: 'No financial statements in the data.' });
  }
  const { rev, ni, net, fy } = F, fyw = fy ? `fiscal year ${/^FY\d\d$/i.test(fy) ? `20${fy.slice(2)}` : fy}` : 'its latest fiscal year';
  const amt = (x, dp = 0) => (fin(x) && Math.abs(x) >= 1 ? ` ${pct(x, dp)}` : '');
  return say(L, {
    new: () => {
      const sales = fin(rev) ? `Its sales (revenue) ${verb(rev)}${amt(rev)} in its latest financial year${fin(ni) ? `, and its profit ${verb(ni)}${amt(ni)}` : ''}.` : '';
      const keep = !fin(net) ? '' : net >= 0 ? ` It keeps about ${num(net, 0)} cents as profit from every dollar of sales.` : ` It is losing money: about ${num(-net, 0)} cents on every dollar of sales.`;
      const why = F.losing ? ' A company that loses money pays for it with cash, borrowing or new shares until it turns a profit.'
        : fin(rev) && rev >= 1 && (!fin(ni) || ni >= 1) ? ' Growing sales and profits are what usually support a share price over time, though the price can still fall if investors expected even more.' : '';
      return `${sales}${keep}${why}`.trim();
    },
    beginner: () => {
      const sales = fin(rev) ? `Revenue, the money it makes from sales, ${verb(rev)}${amt(rev)} in ${fyw}${fin(ni) ? `, and net income, its profit after all costs, ${verb(ni)}${amt(ni)}` : ''}.` : '';
      const keep = !fin(net) ? '' : net >= 0 ? ` Its net margin, the share of each sales dollar it keeps as profit, is ${num(net, 0)}%.` : ` It is losing money: its net margin is ${signed(net, 0)}, so its costs are larger than its sales.`;
      return `${sales}${keep}`.trim();
    },
    intermediate: () => {
      const sales = fin(rev) ? `Revenue ${rose(rev)}${amt(rev, 1)}${fin(ni) ? ` and net income ${rose(ni)}${amt(ni, 1)}` : ''} in ${fy || 'the latest fiscal year'}` : '';
      const margin = !fin(net) ? '' : net >= 0 ? `${sales ? ', on a' : 'A'} ${num(net, 1)}% net margin` : `${sales ? ', and the' : 'The'} company is not yet profitable (net margin ${signed(net, 1)})`;
      const conflict = fin(rev) && fin(F.qRev) && ((rev >= 1 && F.qRev <= -1) || (rev <= -1 && F.qRev >= 1))
        ? ` The latest quarter points the other way: revenue ${F.qRev >= 0 ? 'rose' : 'fell'} ${pct(F.qRev, 1)} against the same quarter a year earlier.` : '';
      return `${sales}${margin}.${conflict}`.replace(/^\./, '').trim();
    },
    advanced: () => {
      const margins = [fin(F.gross) ? `${num(F.gross, 1)}% gross` : '', fin(F.op) ? `${num(F.op, 1)}% operating` : '', fin(net) ? `${num(net, 1)}% net` : ''].filter(Boolean).join(', ');
      return `${fy || 'Latest fiscal year'}: revenue ${fin(rev) ? signed(rev, 1) : 'n/a'}, net income ${fin(ni) ? signed(ni, 1) : 'not meaningful'}${margins ? `; margins ${margins}` : ''}.${fin(F.qRev) ? ` Latest quarter revenue ${signed(F.qRev, 1)} against a year earlier.` : ''}`;
    },
    expert: () => `${fy || 'FY'} rev ${fin(rev) ? signed(rev, 1) : 'n/a'} y/y, NI ${fin(ni) ? signed(ni, 1) : 'n/m'}; ${[fin(F.gross) ? `GM ${num(F.gross, 1)}%` : '', fin(F.op) ? `OM ${num(F.op, 1)}%` : '', fin(net) ? `NM ${num(net, 1)}%` : ''].filter(Boolean).join(', ')}${fin(F.qRev) ? `; last quarter rev ${signed(F.qRev, 1)} y/y` : ''}.`,
  });
}
function valuationLine(F, L) {
  const { pe, peMed: med, peYears: yrs, peTone: tone, prem, fwdPe: fwd } = F;
  if (!fin(pe)) {
    if (F.losing) return say(L, { new: 'Because it is losing money, there is no price-to-earnings figure to judge its price by.', beginner: 'It has no P/E (price-to-earnings ratio), because there are no profits to divide its price by.',
      intermediate: 'There is no P/E to read: its earnings are negative.', advanced: `No meaningful P/E: earnings are negative${fwd ? `; forward P/E ${num(fwd, 1)} on analysts' estimates` : ''}.`, expert: 'P/E not meaningful (negative earnings).' });
    return say(L, { new: 'There is no price-to-earnings figure for it in the data, so its price cannot be compared with its profits here.', intermediate: 'No P/E in the data.', expert: 'P/E n/a.' });
  }
  if (fin(med)) {
    const vs = tone === 'good' ? 'less' : tone === 'bad' ? 'more' : 'about the same';
    return say(L, {
      new: () => `Buyers are paying about $${num(pe, 0)} for every $1 of profit the company made over the past year. That is ${vs === 'about the same' ? 'close to' : `${vs} than`} the $${num(med, 0)} they paid in a typical year over its last ${yrs} years${tone === 'good' ? ', so expectations are lower than they were. A lower price can also mean investors expect weaker results ahead.' : tone === 'bad' ? ', so a lot of good news is already expected, and a disappointment could hurt the price more.' : '.'}`,
      beginner: () => `The shares trade at ${num(pe, 1)} times the past year's earnings, a price-to-earnings ratio (P/E) of ${num(pe, 1)}. Its typical P/E over its last ${yrs} fiscal years was ${num(med, 1)}, so the price asks ${tone === 'good' ? 'less than usual. A lower P/E can also mean investors expect weaker results' : tone === 'bad' ? 'more than usual. A higher P/E means more good news is already expected' : 'about what it usually does'}.`,
      intermediate: () => `At ${num(pe, 1)} times trailing earnings, the shares trade ${Math.abs(prem) < 20 ? `close to their ${yrs}-year median multiple of ${num(med, 1)} (${signed(prem, 0)})` : `${pct(prem)} ${prem < 0 ? 'below' : 'above'} their ${yrs}-year median multiple of ${num(med, 1)}`}.${tone === 'good' ? ' A lower multiple can mean the market expects weaker results ahead.' : tone === 'bad' ? ' A higher multiple means more good news is already in the price, so a disappointment tends to cost more.' : ''}`,
      advanced: () => `Trailing P/E ${num(pe, 1)} against a ${yrs}-year median of ${num(med, 1)}${fin(F.peLow) && fin(F.peHigh) ? ` (range ${num(F.peLow, 1)} to ${num(F.peHigh, 1)})` : ''}: ${signed(prem, 0)} on its own history.${fwd ? ` Forward P/E ${num(fwd, 1)} on analysts' estimates.` : ''}`,
      expert: () => `${num(pe, 1)}x trailing P/E vs ${num(med, 1)}x ${yrs}y median${fin(F.peLow) && fin(F.peHigh) ? ` (${num(F.peLow, 1)}x to ${num(F.peHigh, 1)}x)` : ''}, ${signed(prem, 0)}${fwd ? `; ${num(fwd, 1)}x forward` : ''}.`,
    });
  }
  return say(L, {
    new: () => `Buyers are paying about $${num(pe, 0)} for every $1 of profit the company made over the past year. Optic has no record of what they usually pay for it, so it cannot say whether that is high or low.`,
    beginner: () => `The shares trade at ${num(pe, 1)} times the past year's earnings (a price-to-earnings ratio, or P/E). Optic has no history of its P/E to compare that with.`,
    intermediate: () => `${num(pe, 1)} times trailing earnings, with no multiple history in the data to compare it with.`,
    advanced: () => `Trailing P/E ${num(pe, 1)}${fwd ? `, forward ${num(fwd, 1)} on estimates` : ''}; no multi-year P/E history in the data.`,
    expert: () => `${num(pe, 1)}x trailing${fwd ? `, ${num(fwd, 1)}x forward` : ''}; no history to rank it against.`,
  });
}
function fundLine(F, L) {
  const kind = F.category ? `${F.category.toLowerCase()} fund` : 'fund', from = F.family ? ` from ${F.family}` : '';
  const pe = F.holdPe, y = F.yieldPct;
  return say(L, {
    new: () => `${F.sym} is a fund: one share holds a small slice of many companies${F.category ? ` (a ${kind}${from})` : ''}, so its price moves with all of them together.${fin(pe) ? ` On average, the companies it holds cost about $${num(pe, 0)} for every $1 of their yearly profit.` : ''}${fin(y) ? ` It pays out about ${num(y, 1)}% of its price each year to the people who hold it.` : ''}`,
    beginner: () => `It is a fund${F.category ? `: ${F.category}${from}` : ''}. Its price follows what it holds.${fin(pe) ? ` The companies it holds trade at ${num(pe, 1)} times their earnings, weighted by the fund.` : ''}${fin(y) ? ` Its distribution yield, what it pays out a year as a share of its price, is ${num(y, 2)}%.` : ''}`,
    intermediate: () => `A ${kind}${from}${fin(pe) ? `, its holdings at ${num(pe, 1)} times trailing earnings` : ''}${fin(y) ? `, with a ${num(y, 2)}% distribution yield` : ''}.`,
    advanced: () => `Fund (${F.category || 'category not stated'}${F.family ? `, ${F.family}` : ''}): holdings P/E ${fin(pe) ? num(pe, 1) : 'n/a'} trailing, distribution yield ${fin(y) ? `${num(y, 2)}%` : 'n/a'}.`,
    expert: () => `Fund, ${F.category || 'n/a'}; holdings ${fin(pe) ? `${num(pe, 1)}x` : 'n/a'} trailing; yield ${fin(y) ? `${num(y, 2)}%` : 'n/a'}.`,
  });
}
export function matters(F, L) {
  if (F.kind === 'fund') return [fundLine(F, L)];
  if (F.kind === 'index') {
    return [say(L, { new: `The ${F.name} is not a company: it measures the share prices of a group of companies together, so it has no sales or profits of its own. You cannot own an index itself; funds that follow it are bought and sold instead.`,
      beginner: 'It is an index: a measure of a group of stocks taken together, with no earnings or financial statements of its own. Funds that track it are what is traded.',
      intermediate: 'An index, with no earnings or statements of its own: it moves with its member stocks.', advanced: 'Index: no fundamentals of its own; its members and the funds that track it carry them.', expert: 'Index; no fundamentals of its own.' })];
  }
  if (F.kind === 'crypto') {
    return [say(L, { new: `${F.name} is a digital currency, not a company: it has no sales, profits or reports to judge its price by, so its price rests on what buyers and sellers will pay.`,
      beginner: 'It is a cryptocurrency: there is no company behind it, no earnings and no financial statements, so the usual valuation measures do not apply.',
      intermediate: 'A cryptocurrency: no earnings, cash flows or statements, so no valuation measure applies.', advanced: 'No earnings or cash flows to value: its price is set by trading alone.', expert: 'No cash flows; price set by trading alone.' })];
  }
  return [businessLine(F, L), valuationLine(F, L)].filter(Boolean);
}

/* ---------------- what else should I know ---------------- */
function reportLine(F, L) {
  const r = F.report;
  if (!r) return say(L, { new: 'No date for its next results is in the data yet.', intermediate: 'No report date in the data.', expert: 'No report date in the data.' });
  const when = r.days === 0 ? 'today' : `on ${shortDate(r.date)}, in ${r.days} day${r.days === 1 ? '' : 's'}`;
  const im = F.implied, imA = im ? `; options price a ±${num(im.pct, 1)}% move through the ${shortDate(im.expiry)} expiry` : '', imE = im ? `; implied ±${num(im.pct, 1)}% to ${shortDate(im.expiry)}` : '';
  return say(L, {
    new: `It reports its results ${when}. Share prices often jump or drop after results, in either direction.`,
    beginner: `It reports results ${when}. Results and guidance (what the company says to expect next) can move the price sharply either way.`,
    intermediate: `${r.days === 0 ? 'It reports today' : `Next report: ${shortDate(r.date)}, in ${r.days} day${r.days === 1 ? '' : 's'}`}. Results and guidance can move the price sharply either way.`,
    advanced: `${r.days === 0 ? 'Reports today' : `Reports ${shortDate(r.date)} (${r.days} day${r.days === 1 ? '' : 's'})`}${imA}.`,
    expert: `Earnings ${r.days === 0 ? 'today' : `${shortDate(r.date)}, ${r.days}d out`}${imE}.`,
  });
}
// The reason beside a risk is said at every level: for some it is the caveat itself ("an assumption, not reported
// positions", "it measures tone, not whether the news is true"), which no level may drop (app/knowledge.py INVARIANT).
function riskLine(F, L) {
  const r = F.risk; if (!r) return '';
  const text = lowerFirst(r.text), why = r.why ? ` ${r.why}` : '';
  return say(L, { new: `Something else to weigh: ${text}.${why}`, beginner: `Also worth weighing: ${text}.${why}`, intermediate: `A risk to weigh: ${text}.${why}`, advanced: `Risk: ${text}.${why}` });
}
function swingLine(F, L) {
  if (!fin(F.vol)) return '';
  const dd = fin(F.ddNow) && F.ddNow <= -1 ? F.ddNow : null;
  return say(L, {
    new: `Its price swings by about ${num(F.vol, 0)}% a year, by a standard measure called volatility: the higher it is, the bigger the ups and downs.${dd !== null ? ` It is ${pct(dd)} below the highest price it has closed at.` : ''}`,
    beginner: `Its annualised volatility, a measure of how much the price swings, is about ${num(F.vol, 0)}%.${dd !== null ? ` It sits ${pct(dd)} below its highest close.` : ''}`,
    intermediate: `Annualised volatility is about ${num(F.vol, 0)}%${dd !== null ? `, and it is ${pct(dd, 1)} below its highest close` : ''}.`,
    advanced: `Annualised volatility ${num(F.vol, 1)}% over its daily closes (up to 12 years)${dd !== null ? `; ${signed(dd, 1)} from its highest close` : ''}.`,
    expert: `Vol ${num(F.vol, 1)}% ann.${dd !== null ? `; drawdown ${signed(dd, 1)}` : ''}.`,
  });
}
function limitsLine(F, L) {
  const fresh = F.fresh, period = F.kind === 'company' && F.fy && F.fyEnd ? F.fyEnd : '';
  return say(L, {
    new: `${fresh ? `About these prices: ${lowerFirst(fresh)}. ` : ''}${period ? `The business figures come from its yearly report for the year that ended ${fullDate(period)}, which can be months old. ` : ''}Optic wrote this from those figures by fixed rules. It explains them; it does not tell you what to buy or sell.`,
    beginner: `${fresh ? `${capFirst(fresh)}. ` : ''}${period ? `Business figures are from its fiscal year that ended ${fullDate(period)}. ` : ''}Optic wrote this by fixed rules from the figures on this page; it is not a recommendation to buy or sell.`,
    intermediate: `${fresh ? `${capFirst(fresh)}. ` : ''}${period ? `Business figures: the fiscal year to ${fullDate(period)}. ` : ''}Written by fixed rules from these figures; not a recommendation.`,
    expert: `${fresh ? `${capFirst(fresh)}. ` : ''}${period ? `Fiscal year to ${fullDate(period)}. ` : ''}Rule-written; not a recommendation.`,
  });
}
export function know(F, L) {
  const out = F.kind === 'company' ? [reportLine(F, L), riskLine(F, L)] : [swingLine(F, L), riskLine(F, L)];
  return [...out, limitsLine(F, L)].filter(Boolean);
}

/** The three answers, each a short run of sentences, for one level. */
export function simpleAnalysis(F, L) {
  return [["What's happening?", happening(F, L)], ['Why does it matter?', matters(F, L)], ['What else should I know?', know(F, L)]];
}

/* ---------------- the section ---------------- */
// where to go from here: the tabs that hold the evidence for what was just said, and one question for Milo (drafted,
// not sent; nextSection's own words)
function steps(F) {
  if (F.kind === 'fund') return [['long', 'Its long-term record', 'Investing'], ['chart', 'The full chart', 'Chart']];
  if (F.kind !== 'company') return [['chart', 'The full chart', 'Chart'], ['news', 'The latest headlines', 'News']];
  return [F.report && F.report.days <= 45 ? ['earnings', 'Past results and the next report', 'Earnings'] : null, ['financials', 'The financial statements', 'Financials'], ['chart', 'The full chart', 'Chart']].filter(Boolean);
}
/** The Simple Analysis section. `level` is the knowledge level's id and `label` its name; at New to Markets and
 *  Beginner the text explains its own terms, so the page's term marks stay off it (ui/glossmark.js data-no-gloss). */
export function simpleSection(F, level, { label = '', loading = false, error = '' } = {}) {
  const own = level === 'new' || level === 'beginner';
  const head = html`<div class="section-head"><div><h2 class="t-h2" id="sa-h">Simple analysis</h2>
    <p class="section-sub">${label ? `Worded for ${label}. ` : ''}<a class="textlink" href="#/settings">Change the level</a></p></div></div>`;
  if (loading) return html`<section class="section ov-simple" aria-labelledby="sa-h" aria-busy="true">${head}<p class="t-muted" role="status">Reading the figures for ${F.sym}...</p></section>`;
  if (error) return html`<section class="section ov-simple" aria-labelledby="sa-h">${head}<p>${error}</p></section>`;
  const ask = `Using the figures Optic has for ${F.sym}, what are the main things a long-term investor should understand about it, and what would change that picture?`;
  return html`<section class="section ov-simple" aria-labelledby="sa-h" ${own ? 'data-no-gloss' : ''}>${head}
    ${simpleAnalysis(F, level).map(([q, lines], i) => html`<div class="sa-q"><h3 class="t-h3" id="sa-q${i}">${q}</h3>${lines.map((l) => html`<p>${l}</p>`)}</div>`)}
    <div class="sa-next"><h3 class="t-label">Go further</h3><ul class="sa-steps">
      ${steps(F).map(([view, text, tab]) => html`<li><a class="nx-step" href="${hrefFor(view, F.sym)}"><span>${text}</span><span class="nx-to">${tab} ${icon('arrow')}</span></a></li>`)}
      <li><button type="button" class="nx-step" data-v2-milo="${ask}" data-v2-milo-ctx="${F.sym} Dossier, Overview: simple analysis" data-v2-milo-sym="${F.sym}"><span>Ask Milo a question about ${F.sym}</span><span class="nx-to">Ask Milo ${icon('arrow')}</span></button></li></ul>
      <p class="asof">Ask Milo writes a question for you to edit. Nothing is sent until you press Send.</p></div></section>`;
}
