// Dossier, Overview. One company: a compact header, the year's chart with the
// options-implied range ahead of it, four questions answered directly, the two
// long-term views told apart, Optic's combined read, what changed lately, and
// the rest one step away. The other Dossier pages open in the current app until
// they move (nav.js).
//
// Every answer is worded by a stated rule from the server's own fields; the
// drawer behind each answer shows the evidence and the method. No number here
// is computed differently from the classic app.
import * as FV from '../core/finviz.js';
import { term } from '../ui/term.js';
import { $, $$, html, render as draw, raw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { sections } from '../ui/sections.js';
import { num, signed, dir, money, compact, clean, capFirst, longDate, fullDate, shortDate, isNum, score100, inDays, plural } from '../core/format.js';
import * as RP from '../core/reports.js';
import { lineChart, meter, mountCharts } from '../ui/chart.js';
import { skeleton, empty, failed, staleLine, how } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { header as frameHeader, tabs as frameTabs, isFund, fresher, livePrice } from './dossier-frame.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import * as drawer from '../ui/drawer.js';
import { hrefFor } from '../nav.js';
import { kindOf, learn } from '../core/instrument.js';
import { mountThesis, disposeThesis, thesisContext } from './thesis.js';
import * as OR from './overview-research.js';
import { knowledge } from '../core/prefs.js';
import { defineLive } from '../ui/term.js';
let lp = null;   // the header's price refresh (dossier-frame livePrice), stopped in dispose()

let live = true;
let D = {};
let range = '1Y';
// Sessions of change each range spans. The chart draws one more close than that, so its first point is the
// close the one-year answer measures from: the chart started a session later and read 33.7% against the
// answer's 31.5% (pitch audit, 2026-10-22).
const RANGES = { '3M': 63, '6M': 126, '1Y': 252 };
export const windowOf = (pts, r) => pts.slice(-(RANGES[r] + 1));

// Each answer describes; none says yes or no. The question was "Is the share price expensive?" and the answers
// had been written for "is it cheap?", so AAPL above its range read "No. Above its fair value range." (pitch
// audit, 2026-10-22). A description cannot point the wrong way when the question is reworded.
const qualityWord = { A: "Strong on Optic's quality measures.", B: "Good on Optic's quality measures.", C: "Middling on Optic's quality measures.", D: "Weak on Optic's quality measures.", F: "Poor on Optic's quality measures." };
export const starsWord = { 5: 'Below its usual valuation range.', 4: 'Inside its usual range, in the lower half.', 3: 'Near the middle of its usual range.', 2: 'Inside its usual range, in the upper half.', 1: 'Above its usual valuation range.' };
export const PRICE_Q = 'How is it priced against its own history?';
/** The valuation answer for every state the fair-value payload can be in. */
export function priceAnswer(fvd, failed) {
  if (failed) return 'Not available right now.';
  if (!fvd) return null;
  const st = fvd.stars || {}, fv = fvd.fair_value || {};
  if (st.available) return starsWord[st.stars] || clean(st.word);
  if (fv.available) return fv.wide ? 'Its usual range is too wide to place the price in.' : 'Not placed against its range.';
  return 'No valuation range for this company.';
}
const stanceWord = { fair: 'priced about in line with that history', expensive: 'priced above that history', cheap: 'priced below that history' };
const timing = { before_open: 'before the open', after_close: 'after the close', during: 'during the session' };

/* ---------------- chart ---------------- */
function series() {
  const ps = ((D.ticker || {}).technicals || {}).price_series || {};
  const dates = (ps.dates || []).map((x) => String(x).slice(0, 10));
  return dates.map((d, i) => ({ d, c: Number((ps.close || [])[i]) })).filter((p) => p.d && isNum(p.c) && p.c > 0);
}
function chartEvents(pts) {
  const eh = (((D.ticker || {}).company || {}).earnings_history) || {};
  const first = pts.length ? pts[0].d : '';
  return (eh.quarters || []).filter((r) => r.date && String(r.date).slice(0, 10) >= first).map((r) => ({
    d: String(r.date).slice(0, 10), kind: 'E', label: 'Earnings report',
    detail: [isNum(r.eps_reported) ? `EPS ${num(r.eps_reported)}` : '', isNum(r.eps_estimate) ? `against ${num(r.eps_estimate)} expected` : '', isNum(r.surprise_pct) ? `(${r.surprise_pct >= 0 ? 'beat' : 'missed'} by ${num(Math.abs(r.surprise_pct), 1)}%)` : ''].filter(Boolean).join(' '),
    r,
  })).sort((a, b) => a.d.localeCompare(b.d));
}
function implied() {
  const im = (D.earnings || {}).implied || {};
  const q = D.quote || {};
  if (!im.available || !isNum(im.implied_move_pct) || !isNum(q.price)) return null;
  return { pct: im.implied_move_pct, expiry: im.expiry, dte: im.dte, sessions: Math.max(1, Math.round(im.dte * 5 / 7)), lo: q.price * (1 - im.implied_move_pct / 100), hi: q.price * (1 + im.implied_move_pct / 100), strike: im.strike, cost: im.straddle_cost };
}
function chartBlock(sym) {
  const pts = series();
  if (!D.ticker) return html`<div class="chart-slot">${skeleton('chart', 1, 'Loading the price history')}</div>`;
  if (pts.length < 20) return empty('No price history to draw', 'The quote above is current; the chart returns when the history does.');
  const im = implied();
  const shown = windowOf(pts, range), first = shown[0], last = pts[pts.length - 1];
  return html`<div class="chart-bar"><p class="section-sub">Daily closes from ${fullDate(first.d)} through ${fullDate(last.d)}. E marks an earnings report.${im ? html` The gold cone is the ±${num(im.pct)}% range options price through the ${shortDate(im.expiry)} expiry.` : ''}</p>
    <div class="seg" role="group" aria-label="Chart range">${Object.keys(RANGES).map((r) => html`<button type="button" data-v2-range="${r}" aria-pressed="${r === range}">${r}</button>`)}</div></div>
    <div class="chart-slot" data-chart="price"></div>
    ${D.freshText ? html`<p class="asof">${D.freshText}</p>` : ''}`;
}
function mountChart(main, sym) {
  const pts = windowOf(series(), range);
  if (pts.length < 20) return;
  const im = implied();
  const evs = chartEvents(pts);
  mountCharts(main, { price: (w) => lineChart(pts, {
    w, h: Math.round(Math.max(220, Math.min(340, w * 0.3))), area: true, label: `${sym} closing price`,
    events: evs, monthStep: range === '1Y' ? 3 : 1, pad: { t: 26, r: 52, b: 24, l: 0 },
    future: im ? im.sessions : 0, cone: im ? { lo: im.lo, hi: im.hi, pct: im.pct, expiry: im.expiry, from: (D.quote || {}).price } : null, focusEnd: true,
    onEvent: (iso, el) => { const e = evs.find((x) => x.d === iso); if (e) drawer.open({ kicker: `${sym}, earnings`, title: `Reported ${longDate(iso)}`, opener: el, body: html`<p>${sym} reported ${timing[e.r.timing] || ''} on ${fullDate(iso)}. ${e.detail}.</p>${miloButton('Ask Milo about this report', { ask: `How did ${sym} react to the ${shortDate(iso)} report?`, context: `${sym}, the ${shortDate(iso)} report`, symbol: sym })}` }); },
  }) });
}

/* ---------------- the four answers ---------------- */
// A fund gets a fund's questions (core/instrument.js): what it holds, what its holdings cost, whether there
// is a trade, what it pays. The company questions answered "Not graded" and printed an SEC 404 (2026-10-19).
const isFundHere = (sym) => kindOf(sym, D) === 'fund';
function fundAnswers(sym, tradeItem) {
  const prof = (D.session || {}).profile || {}, h = (D.longterm || {}).holding || {}, val = h.valuation || {}, q = D.quote || {};
  const yieldPct = isNum(q.dividend_yield) ? q.dividend_yield * 100 : isNum(val.dividend_yield) ? val.dividend_yield * 100 : null;
  return [
    { k: 'quality', q: 'What is it?', a: !D.session ? null : `${prof.category ? `A ${prof.category.toLowerCase()} fund` : 'A fund'}${prof.fund_family ? ` from ${prof.fund_family}` : ''}.`,
      because: clip(clean(prof.summary || 'The feed has no description for this fund.'), 190) },
    { k: 'price', q: 'What do its holdings cost?', a: !D.longterm ? null : isNum(val.trailing_pe) ? `${num(val.trailing_pe, 1)} times trailing earnings.` : 'No valuation for its holdings in the feed.',
      because: `${isNum(val.price_to_book) ? `Price to book ${num(val.price_to_book, 2)}. ` : ''}A fund's price follows what it holds, so Optic gives no fair value range of its own.` },
    tradeItem,
    { k: 'next', q: 'What does it pay?', a: !D.quote && !D.longterm ? null : isNum(yieldPct) ? `${num(yieldPct, 2)}% a year.` : 'No yield in the feed.',
      because: 'Distributions pass on what the holdings pay. A fund reports no earnings of its own; its holdings do.' },
  ];
}
const clip = (t, n) => (t.length > n ? `${t.slice(0, t.lastIndexOf(' ', n))}…` : t);

// How the share price has moved over a year, against its 200-day average: a finding about the price, never
// about the business (the reader is told which is which)
export function trendFinding(pts, sma200) {
  const closes = (pts || []).filter((p) => isNum(p.c));
  if (closes.length < 60) return null;
  const last = closes[closes.length - 1], back = closes[Math.max(0, closes.length - 253)];
  const ch = FV.pctChange(last.c, back.c), vsAvg = isNum(sma200) && sma200 > 0 ? ((last.c - sma200) / sma200) * 100 : null;
  return { ch, from: back, to: last, vsAvg, span: closes.length >= 253 ? 'a year' : `${Math.round((closes.length - 1) / 21)} months` };
}
function trendItem(sym) {
  const ps = ((D.ticker || {}).technicals || {}).price_series || {}, sma = (ps.sma200 || []).filter(isNum);
  // a failed price history ended the chart's wait but left this card shimmering beside the error (audit 2026-10-22)
  if (D.tickerError && !D.ticker) return { k: 'trend', q: 'How has the share price moved?', a: 'Not available right now.', because: `${clean(String(D.tickerError.message || 'The price history did not load').replace(/\.$/, ''))}. The chart below has a Try again.` };
  const t = D.ticker ? trendFinding(series(), sma[sma.length - 1]) : undefined;
  if (t === undefined) return { k: 'trend', q: 'How has the share price moved?', a: null };
  if (!t || !isNum(t.ch)) return { k: 'trend', q: 'How has the share price moved?', a: 'Not enough price history.', because: 'Optic needs a few months of daily closes for this.' };
  return { k: 'trend', q: 'How has the share price moved?', a: `${t.ch >= 0 ? 'Up' : 'Down'} ${num(Math.abs(t.ch), 1)}% over ${t.span}.`,
    because: html`From ${num(t.from.c)} on ${fullDate(t.from.d)} to ${num(t.to.c)}.${isNum(t.vsAvg) ? ` ${num(Math.abs(t.vsAvg), 1)}% ${t.vsAvg >= 0 ? 'above' : 'below'} its 200-day average, ${t.vsAvg >= 0 ? 'so the longer trend is up' : 'so the longer trend is down'}.` : ''} This is the share price, not the business's results.` };
}

function answers(sym) {
  const fw = D.framework || {}, lt = fw.long_term || {}, sw = fw.swing || {};
  const qy = lt.quality || {}, fv = (D.fairValue || {}).fair_value || {}, st = (D.fairValue || {}).stars || {};
  const nr = (D.earnings || {}).next_report || {};
  const pr = (D.earnings || {}).pricing || {};
  const im = implied();
  const q = D.quote || {};
  const out = [];
  const gone = (e) => ({ a: 'Not available right now.', because: `${clean((e && e.message) || 'Its source did not answer.')} The other answers do not depend on it.` });
  if (D.fwError) {
    const g = gone(D.fwError);
    out.push({ k: 'quality', q: 'How is the business doing?', ...g });
  } else out.push({ k: 'quality', q: 'How is the business doing?', a: D.framework ? (qy.grade ? qualityWord[qy.grade] || `Grade ${qy.grade}.` : 'Not graded.') : null,
    because: qy.grade ? html`<span class="chip-tag">Grade ${qy.grade}</span>${clean(((qy.components || [])[0] || {}).headline || qy.summary || '')}` : clean(qy.summary || '') });
  const priceA = priceAnswer(D.fairValue, D.fvError);
  out.push({ k: 'price', q: PRICE_Q, a: priceA,
    because: st.available && fv.available ? html`${raw(meter({ lo: fv.low, mid: fv.mid, hi: fv.high, price: q.price || fv.price, w: 214 }))}<span class="chip-tag">${st.stars} of 5 stars</span>Usual range ${num(fv.low, 0)} to ${num(fv.high, 0)}, from its own 5-year P/E. A reading against its past, not an intrinsic value.`
      : D.fvError ? gone(D.fvError).because : clean([st.reason, fv.wide ? fv.wide_note : fv.reason].filter(Boolean).join(' ')) });
  const setup = sw.setup || {};
  // the four basic questions in the beginner brief's order (item 5): the business, its price, the share price's
  // trend, what is next. The short-term trade setup is deeper research, under More.
  if (isFundHere(sym)) { out.length = 0; out.push(...fundAnswers(sym, trendItem(sym))); return answerGrid(out); }
  out.push(trendItem(sym));
  const nextA = D.earnError ? 'Not available right now.' : !D.earnings ? null : nr.date ? `Earnings on ${longDate(nr.date)}.` : 'No report date yet.';
  out.push({ k: 'next', q: "What's next?", a: nextA,
    because: D.earnError ? gone(D.earnError).because : nr.date ? html`${inDays(nr.days_away)}, ${RP.dateStatus(nr)}.${RP.habitLine(nr) ? ` ${RP.habitLine(nr)}` : ''}${im ? html` Options price ±${num(im.pct)}% through the ${shortDate(im.expiry)} expiry; report days have averaged ±${num(pr.event_day_avg_pct)}%.` : ''}` : '' });
  return answerGrid(out);
}
function answerGrid(out) {
  return html`<section class="answers" aria-label="Four questions, answered">${out.map((x) => x.a === null
    ? html`<div class="answer is-loading"><span class="answer-in"><span class="q">${x.q}</span>${skeleton('lines', 3)}</span></div>`
    : html`<button type="button" class="answer" data-v2-answer="${x.k}" aria-expanded="false" aria-labelledby="aq-${x.k} aa-${x.k}" aria-describedby="ab-${x.k}"><span class="answer-in"><span class="q" id="aq-${x.k}">${x.q}</span><span class="a" id="aa-${x.k}">${x.a}</span><span class="because" id="ab-${x.k}">${x.because}</span><span class="go">Evidence and method ${icon('arrow')}</span></span></button>`)}</section>`;
}

/** The "priced against history" line, with its basis beside the ratio (point 4). */
export function historyRatio(pr, im, quartersIn) {
  if (!pr || !pr.available || !isNum(pr.ratio)) return '';
  const k = pr.baseline_kind;
  const n = pr.baseline_sessions;
  const quarters = quartersIn || ((D.earnings || {}).surprise || {}).quarters || 8;
  const basis = k === 'event-plus-ordinary'
    ? `typical for the same ${n} sessions: the ±${num(pr.event_day_avg_pct)}% report-day average (${quarters} quarters) combined with a typical ${Math.max(n - 1, 1)}-session move over two years`
    : k === 'event-day' ? `the average move on the session after past reports (${quarters} quarters)`
      : `a matched ${n}-session move over the past two years`;
  return html`<div class="ratio"><p class="t-label">Priced against history</p>
    <p class="ratio-eq"><b>${num(pr.ratio, 2)}×</b> <span>Options price ±${num(pr.implied_move_pct)}%${im ? ` through ${shortDate(im.expiry)}` : ''}, against a typical ±${num(pr.baseline_move_pct)}% for the same period.</span></p>
    <p class="t-note">Options are ${stanceWord[pr.stance] || pr.stance}.</p>
    ${how(html`<p>The ratio is the priced move (±${num(pr.implied_move_pct)}%) divided by ${basis} (±${num(pr.baseline_move_pct)}%).</p>`)}</div>`;
}

function fundEvidence(k, sym) {
  const prof = (D.session || {}).profile || {}, h = (D.longterm || {}).holding || {}, val = h.valuation || {}, q = D.quote || {};
  if (k === 'quality') {
    return html`<p>${clean(prof.summary || 'The feed has no description for this fund.')}</p>
      <dl class="kv"><div><dt>Category</dt><dd>${prof.category || 'n/a'}</dd></div><div><dt>Fund family</dt><dd>${prof.fund_family || 'n/a'}</dd></div><div><dt>Type</dt><dd>${prof.kind_label || 'Fund'}</dd></div></dl>
      <p class="asof">Source: the fund's profile in Yahoo Finance's feed. Its holdings list is not in Optic's feed.</p>`;
  }
  if (k === 'price') {
    return html`<dl class="kv"><div><dt>P/E of its holdings, trailing</dt><dd>${num(val.trailing_pe, 1)}</dd></div><div><dt>Price to book</dt><dd>${num(val.price_to_book, 2)}</dd></div><div><dt>52-week range</dt><dd>${num((h.fundamentals || {}).fifty_two_low)} to ${num((h.fundamentals || {}).fifty_two_high)}</dd></div></dl>
      <p>These are the holdings' figures, weighted by the fund. A fund's price follows what it holds, so there is no business of its own to value and no fair value range.</p><p class="asof">${clean(val.caveat || '')}</p>`;
  }
  if (k === 'next') {
    return html`<p>${isNum(q.dividend_yield) ? html`<b>${num(q.dividend_yield * 100, 2)}% a year</b>, the trailing distribution yield.` : 'No distribution yield in the feed.'}</p>
      <p>A fund reports no earnings; the companies it holds do. Their reports this week are on Home's Earnings panel and in Markets.</p>`;
  }
  return null;
}

function evidence(k, sym) {
  if (isFundHere(sym)) { const f = fundEvidence(k, sym); if (f) return f; }
  const fw = D.framework || {}, lt = fw.long_term || {}, sw = fw.swing || {};
  const qy = lt.quality || {}, val = lt.valuation || {};
  const fvd = D.fairValue || {}, fv = fvd.fair_value || {}, st = fvd.stars || {};
  const e = D.earnings || {}, pr = e.pricing || {}, nr = e.next_report || {}, im = implied();
  const comp = (list) => html`<ul class="evlist">${(list || []).map((c) => html`<li><b>${c.label}</b>${c.grade ? html` <span class="chip-tag">${c.grade}</span>` : ''}<span>${clean(c.headline || c.status || '')}</span></li>`)}</ul>`;
  if (k === 'quality') {
    return html`<p>${clean(qy.summary)}</p>${comp(qy.components)}
      <h3>Method</h3><p>Seven measures of the business, each graded A to F and weighted: ${Object.entries(qy.weights || {}).map(([id, w]) => `${id} ${w}%`).join(', ')}.</p>
      <p class="asof">${clean(lt.separation_note || '')}</p>`;
  }
  if (k === 'price' && !st.available) {
    return html`<p><b>${priceAnswer(D.fairValue, D.fvError)}</b> ${clean(st.reason || '')}</p>${fv.available ? html`<dl class="kv"><div><dt>Low</dt><dd>${num(fv.low)}</dd></div><div><dt>Middle</dt><dd>${num(fv.mid)}</dd></div><div><dt>High</dt><dd>${num(fv.high)}</dd></div><div><dt>Price</dt><dd>${num((D.quote || {}).price)}</dd></div></dl>
      <p>${clean(fv.wide_note || '')}</p><h3>Method</h3><p>${clean(fv.basis || '')}</p>` : html`<p>${clean(fv.reason || 'No fair value estimate for this company.')}</p>`}
      ${val.label ? html`<h3>The framework's valuation</h3><p>${clean(val.summary || `Valuation ${val.label}.`)}</p>` : ''}`;
  }
  if (k === 'price') {
    return html`${raw(meter({ lo: fv.low, mid: fv.mid, hi: fv.high, price: (D.quote || {}).price, w: 400, showMid: true }))}
      <p><b>${st.stars} of 5 stars: ${starsWord[st.stars] || clean(st.word || '')}</b> ${isNum(fv.gap_to_mid_pct) ? `The price is ${num(Math.abs(fv.gap_to_mid_pct), 1)}% ${fv.gap_to_mid_pct >= 0 ? 'above' : 'below'} the middle of the range.` : ''}</p>
      <h3>Method</h3><p>${clean(fv.basis || '')}</p><p>${clean(st.rule || '')} ${clean(st.note || '')}</p>
      ${val.label ? html`<h3>The framework's valuation</h3><p>${clean(val.summary || `Valuation ${val.label}.`)} It looks at more than the P/E (intrinsic value, multiples against peers and history), so it can differ from the stars.</p>${comp(val.components)}` : ''}
      <ul class="plain">${(fv.limits || []).map((l) => html`<li>${clean(l)}</li>`)}</ul><p class="asof">Source: ${fv.source || 'company filings'}.</p>`;
  }
  if (k === 'trend') {
    const ps = ((D.ticker || {}).technicals || {}).price_series || {}, sma = (ps.sma200 || []).filter(isNum), t = trendFinding(series(), sma[sma.length - 1]);
    return html`<p>${t && isNum(t.ch) ? `The share price ${t.ch >= 0 ? 'rose' : 'fell'} ${num(Math.abs(t.ch), 1)}% from ${num(t.from.c)} on ${fullDate(t.from.d)} to ${num(t.to.c)} on ${fullDate(t.to.d)}.` : 'Not enough history.'}</p>
      ${t && isNum(t.vsAvg) ? html`<p>It is ${num(Math.abs(t.vsAvg), 1)}% ${t.vsAvg >= 0 ? 'above' : 'below'} its 200-day average, the average close of about the last ten months, which smooths out day-to-day swings.</p>` : ''}
      <p>A rising share price and a growing business are different things: the price moves with what investors expect, and can rise while results weaken, or fall while they improve. How is the business doing answers the second; Financials and Earnings have the figures.</p>`;
  }
  if (k === 'trade') {
    const plan = sw.plan || {};
    return html`<p><b>Grade ${sw.grade}.</b> ${clean(sw.why || '')}</p>
      ${plan.entry ? html`<dl class="kv"><div><dt>Entry</dt><dd>${num(plan.entry)}</dd></div><div><dt>Invalidation</dt><dd>${num((plan.invalidation || {}).price)}</dd></div>${(plan.targets || []).slice(0, 2).map((t, i) => html`<div><dt>Target ${i + 1}</dt><dd>${num(t.price ?? t)}</dd></div>`)}</dl>
        <p>${clean(plan.confirmation || '')}</p>` : ''}
      ${(sw.objections || []).length ? html`<h3>Against it</h3><ul class="plain">${sw.objections.map((o) => html`<li>${clean(o.text)}</li>`)}</ul>` : ''}
      <h3>Method</h3><p>${clean(sw.framework_note || '')}</p><p class="asof">Model output, not a recommendation to trade.</p>`;
  }
  // what's next: the two figures kept apart, then the comparison with its basis
  return html`${nr.date ? html`<p><b>${longDate(nr.date)}</b>, ${RP.dateStatus(nr)}. ${RP.habitLine(nr)} Consensus EPS ${num(nr.eps_consensus)}, revenue ${nr.revenue_consensus_label || 'n/a'}. ${clean(nr.dispersion_note || '')}</p>` : ''}
    <h3>Two different figures</h3>
    ${im ? html`<p><b>±${num(im.pct)}% through the ${shortDate(im.expiry)} expiry.</b> What the at-the-money straddle (the ${num(im.strike, 0)} strike, $${num(im.cost)}) costs as a share of the price, ${plural(im.dte, 'day')} out. It covers ordinary trading as well as the report.</p>` : ''}
    ${isNum(pr.event_day_avg_pct) ? html`<p><b>±${num(pr.event_day_avg_pct)}% on report days.</b> ${sym}'s average move on the session after its last ${((e.surprise || {}).quarters) || 8} reports. History, not a price.</p>` : ''}
    ${historyRatio(pr, im)}
    <p class="asof">${clean(pr.caveat || '')}</p>`;
}

/* ---------------- two long-term views (point 3) ---------------- */
function fundRecord(sym) {
  const h = (D.longterm || {}).holding;
  if (!h) return html`<section class="section">${skeleton('lines', 3, 'Loading the long-term record')}</section>`;
  const sc = h.conviction_scale || {}, s100 = !h.error ? score100(h.conviction_score, sc.min_possible, sc.max_possible) : null;
  const hz = h.horizons || {}, dd = h.drawdown || {}, rk = h.risk || {};
  const pct = (v) => (isNum(v) ? signed(v, 1) : 'n/a');
  return html`<section class="section" aria-labelledby="lv-h">
    <div class="section-head"><div><h2 class="t-h2" id="lv-h">The long-term record</h2><p class="section-sub">From ${num((h.data_quality || {}).history_years, 0)} years of daily closes.</p></div></div>
    <div class="views">
      <div class="view"><p class="t-label">Long-term trend score, from price history</p>
        <p class="n">${s100 === null ? 'n/a' : num(s100, 0)}<small> of 100</small></p><p>${clean(h.plan || '')}</p>
        <p class="asof">The 200-week and 40-week trends, return per unit of risk and distance from the high.</p></div>
      <div class="view"><p class="t-label">Returns a year, and the falls along the way</p>
        <dl class="kv"><div><dt>1 year</dt><dd>${pct(hz.return_1y_pct)}</dd></div><div><dt>3 years</dt><dd>${pct(hz.cagr_3y_pct)}</dd></div><div><dt>5 years</dt><dd>${pct(hz.cagr_5y_pct)}</dd></div><div><dt>10 years</dt><dd>${pct(hz.cagr_10y_pct)}</dd></div>
          <div><dt>Largest fall</dt><dd>${pct(dd.max_drawdown_pct)}${dd.max_drawdown_date ? html` <small>to ${shortDate(dd.max_drawdown_date)} ${String(dd.max_drawdown_date).slice(0, 4)}</small>` : ''}</dd></div><div><dt>Below its high now</dt><dd>${pct(dd.current_drawdown_pct)}</dd></div>
          <div><dt>Volatility, annualised</dt><dd>${isNum(rk.annualised_vol_pct) ? `${num(rk.annualised_vol_pct, 1)}%` : 'n/a'}</dd></div></dl>
        <p class="asof">Compound annual returns from closing prices, before tax; distributions are not reinvested in these figures.</p></div>
    </div></section>`;
}

function longViews(sym) {
  if (isFundHere(sym)) return fundRecord(sym);
  const h = (D.longterm || {}).holding;
  const lt = (D.framework || {}).long_term || {};
  if (!h && !D.framework) return html`<section class="section">${skeleton('lines', 3, 'Loading the long-term views')}</section>`;
  const sc = (h && h.conviction_scale) || {};
  const s100 = h && !h.error ? score100(h.conviction_score, sc.min_possible, sc.max_possible) : null;
  const facs = (h && h.conviction_factors) || [];
  const pts = (kind) => facs.filter((f) => kind.includes(f.kind)).reduce((a, f) => a + (Number(f.points) || 0), 0);
  const priceBehaviour = pts(['trend', 'relative strength', 'risk']);
  const valuation = facs.find((f) => f.kind === 'valuation');
  const conv = lt.conviction || {};
  const q = (lt.quality || {}).grade, v = (lt.valuation || {}).label;
  if (s100 === null && !conv.label) return '';
  const syn = synthesis(s100, q, (D.fairValue || {}).stars || {}, v, conv.label);
  return html`<section class="section" aria-labelledby="lv-h">
    <div class="section-head"><div><h2 class="t-h2" id="lv-h">How the long-term views fit together</h2><p class="section-sub">Each model answers a different question, over a different span. A strong company or a strong price trend can still be an expensive stock.</p></div></div>
    ${syn ? html`<p class="synth">${syn}</p>` : ''}
    <div class="views">
      <div class="view"><p class="t-label">Price trend score: how the share price has behaved over about five years</p>
        <p class="n">${s100 === null ? 'n/a' : num(s100, 0)}<small> of 100</small></p>
        <p>${s100 === null ? 'Not available.' : `${trendBand(s100)}. A finding about the share price's path, not about the business, its price today or whether it suits you.`}</p>
        ${how(html`<p>From the 200-week and 40-week trends, five years against the S&amp;P 500, return per unit of risk, forward P/E, distance from the high, the dividend and catalysts.</p>`, h && h.plan ? html`<p>The trend model's own wording: "${clean(h.plan)}" It reads the price trend only.</p>` : '')}</div>
      <div class="view"><p class="t-label">Long-term case: the business and what it costs, over years</p>
        <p class="n">${conv.label || 'n/a'}</p>
        <p>${clean(conv.why || '')}</p>
        <p class="asof">Business quality${q ? ` (grade ${q})` : ''} weighed against valuation${v ? ` (${v.toLowerCase()})` : ''} and the weekly chart.</p></div>
    </div>
    ${h && conv.label ? html`<p class="reconcile"><b>Why they differ.</b> The trend score reads how the stock has behaved: ${num(priceBehaviour, 0)} of its ${num(h.conviction_score, 0)} points come from trend, relative strength and risk-adjusted return${valuation && isNum(valuation.points) ? `, and valuation added ${num(valuation.points, 0)}` : ''}.${valuation ? html` On valuation the trend model says: “${clean(valuation.detail)}”` : ''} The long-term case asks whether today's price pays for the business${v ? `, and grades the valuation ${v.toLowerCase()}` : ''}. Optic's combined read below uses the long-term case.</p>` : ''}
  </section>`;
}

const trendBand = (x) => (x >= 70 ? 'A strong long-term price trend' : x >= 45 ? 'A middling long-term price trend' : 'A weak long-term price trend');
/** One sentence on where the views agree and where they do not, from their own labels (beginner brief item 6):
 * nothing is reweighted or left out to make them agree. */
export function synthesis(s100, grade, stars, valLabel, convLabel) {
  const good = [], bad = [];
  if (grade) (['A', 'B'].includes(grade) ? good : ['D', 'F'].includes(grade) ? bad : []).push(['A', 'B'].includes(grade) ? `the business grades ${grade}` : `the business grades ${grade}`);
  if (isNum(s100)) (s100 >= 70 ? good : s100 < 45 ? bad : []).push(s100 >= 70 ? `the long-term price trend is strong (${num(s100, 0)} of 100)` : `the long-term price trend is weak (${num(s100, 0)} of 100)`);
  const st = stars && stars.available ? stars.stars : null, val = valLabel ? valLabel.toLowerCase() : '';
  // 4 stars is inside the range, below its middle: it was worded "below its fair value range" like 5
  if (isNum(st)) (st >= 4 ? good : st <= 2 ? bad : []).push(st >= 4 ? `the price is ${st === 5 ? 'below' : 'in the lower half of'} its fair value range` : `the price is ${st === 1 ? 'above' : 'in the upper half of'} its fair value range${val ? ` (valuation ${val})` : ''}`);
  else if (/stretch|expensive|rich/.test(val)) bad.push(`the valuation reads ${val}`);
  const join = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}` : xs[0] || '');
  const cap = (t) => t.charAt(0).toUpperCase() + t.slice(1);
  if (!good.length && !bad.length) return convLabel ? `Optic's combined long-term case is ${convLabel.toLowerCase()}.` : '';
  const lead = good.length && bad.length ? `${cap(join(good))}, but ${join(bad)}.` : `${cap(join(good.length ? good : bad))}.`;
  return `${lead}${convLabel ? ` Weighing them, Optic's combined long-term case is ${convLabel.toLowerCase()}.` : ''}`;
}

function combined() {
  const c = (D.framework || {}).combined;
  if (!c || isFundHere(D.sym)) return '';   // the combined verdict weighs a business case a fund does not have
  return html`<section class="section verdict" aria-labelledby="cv-h"><h2 class="t-h3" id="cv-h">Taken together</h2>
    <p class="verdict-line">${clean(c.verdict)}</p>
    <ul class="plain">${(c.lines || []).map((l) => html`<li>${clean(l)}</li>`)}</ul>
    <p class="asof">${clean(c.note || '')}</p></section>`;
}

/* ---------------- what changed lately ---------------- */
function digest(sym) {
  const d = D.digest;
  if (d === undefined) return html`<section class="section">${skeleton('lines', 2, 'Loading what changed')}</section>`;
  if (!d || !d.available) return '';
  const items = [...(d.changed || []).map((c) => ({ when: d.session_date, what: clean(c.text), sub: clean(c.detail || '') })),
    ...(d.explanations || []).slice(0, 3).map((x) => ({ when: String(x.published || '').slice(0, 10), what: clean(x.headline), sub: `${x.publisher || ''}${x.tone ? `, scored ${x.tone}` : ''}`, url: x.url }))];
  if (!items.length) return '';
  return html`<section class="section" aria-labelledby="dg-h"><div class="section-head"><div><h2 class="t-h2" id="dg-h">What changed lately</h2><p class="section-sub">${clean((d.period || {}).label || '')}</p></div>
    ${miloButton('Ask Milo about this', { ask: `What changed for ${sym} lately, and does it matter?`, context: `${sym}, what changed lately`, symbol: sym })}</div>
    ${items.map((x, i) => html`<div class="ev"><button type="button" class="ev-head" aria-expanded="false" aria-controls="dg-${i}" data-v2-ev><span class="who">${x.when ? shortDate(x.when) : ''}</span><span class="what">${x.what}<small>${x.sub}</small></span><span class="ch"></span>${icon('chev')}</button>
      <div class="ev-body" id="dg-${i}" hidden>${x.url ? html`<p><a class="textlink" href="${x.url}" target="_blank" rel="noopener">Read at the source ${icon('out')}</a></p>` : html`<p>${x.sub}</p>`}</div></div>`)}
    <p class="asof">${clean(d.describes || '')}</p></section>`;
}

/* ---------------- what the company is, and its latest news: first on the page (owner, 2026-10-20) ---------------- */
function firstSentences(t, n = 2, max = 320) {
  const parts = String(t || '').match(/[^.!?]+[.!?]+(\s|$)/g) || [String(t || '')];
  let out = ''; for (const x of parts.slice(0, n)) { if ((out + x).length > max && out) break; out += x; }
  return out.trim();
}
function revenueLine() {
  const s = D.segments, f = (((D.ticker || {}).company || {}).financials) || {};
  if (!s || !s.available) return '';
  const t = (s.tables || []).filter((x) => x.metric === 'revenue' && ((x.annual || {}).ends || []).length).sort((a, b) => (a.axis === 'product' ? -1 : 1) - (b.axis === 'product' ? -1 : 1))[0];
  if (!t) return '';
  const ends = t.annual.ends, rows = t.annual.rows, k = ends.map((_, i) => rows.some((r) => isNum(r.values[i]))).lastIndexOf(true); if (k < 0) return '';
  const day = (x) => Date.parse(String(x).slice(0, 10)), ai = (f.annual_periods || []).findIndex((p) => Math.abs(day(p) - day(ends[k])) <= 15 * 864e5);
  const total = ai >= 0 ? ((f.annual || {}).revenue || [])[ai] : null;
  const c = FV.composition(rows.map((r) => clean(r.member)), rows.map((r) => r.values[k]), total);
  if (!c.rows.length || !c.canShare) return '';
  const base = c.reconciles ? c.total : c.sum, top = c.rows.slice(0, 2).map((r) => `${r.label}, ${num((r.v / base) * 100, 0)}%`);
  const label = ai >= 0 ? (f.annual_fiscal || [])[ai] : String(ends[k]).slice(0, 4);
  return `${top.join('; ')} of ${label} revenue, ${t.axis_label.toLowerCase().replace(/^by /, 'by ')}.`;
}
function about(sym) {
  const t = D.ticker || {}, q = D.quote || {}, prof = (D.session || {}).profile || {};
  const news = t.news || {}, name = q.name || prof.name || sym, fund = isFundHere(sym);
  const summary = clean(prof.summary || '').replace(/^The Company\b/, name);
  const lead = firstSentences(summary);
  const rev = fund ? '' : revenueLine();
  const ses = ((D.session || {}).session) || {};
  const price = isNum(q.price) ? html`${money(q.price)}${isNum(q.change_pct) ? html`, <span class="${dir(q.change_pct)}">${signed(q.change_pct)}</span> ${ses.is_regular ? 'today' : 'at the last close'}` : ''}<small>US dollars; quotes delayed about 15 minutes</small>` : '';
  const items = [
    ...(summary && summary.length > lead.length + 20 ? [[`${fund ? 'What it is' : 'What it does'}, in full`, html`<p>${summary}</p>${prof.summary_source && prof.summary_source.form_name ? html`<p class="asof">From its ${prof.summary_source.form_name}${prof.summary_source.filed ? `, filed ${fullDate(prof.summary_source.filed)}` : ''}.</p>` : ''}`, '']] : []),
    ...((news.articles || []).length ? [['Latest headlines', html`<ul class="plain">${news.articles.slice(0, 6).map((a) => html`<li><a href="${a.url}" target="_blank" rel="noopener">${clean(a.title)}</a> <span class="t-muted">${a.publisher}, published ${a.age_words || ''}${a.tone && (a.keywords || []).length ? `, ${a.tone} wording` : ''}</span></li>`)}</ul><a class="textlink" href="${hrefFor('news', sym)}">All headlines on News ${icon('out')}</a>`, news.overall_tone || '']] : []),
  ];
  if (!lead && !items.length && !price) return '';
  return html`<section class="section about" aria-labelledby="ab-h"><h2 class="t-h2" id="ab-h">${fund ? `What ${name} is` : `What ${name} does`}</h2>
    ${lead ? html`<p class="about-lead">${lead}</p>` : ''}
    <dl class="about-kv">
      ${prof.industry || prof.sector || prof.category ? html`<div><dt>${fund ? 'Kind of fund' : 'Industry'}</dt><dd>${fund ? prof.category || 'Fund' : [prof.industry, prof.sector].filter(Boolean).join(', ')}</dd></div>` : ''}
      ${rev ? html`<div><dt>Where its revenue comes from</dt><dd>${rev}</dd></div>` : ''}
      ${price ? html`<div><dt>Share price</dt><dd>${price}</dd></div>` : ''}
      ${isNum(q.market_cap) && !fund ? html`<div><dt>${term('market cap', 'Market value')}</dt><dd>$${compact(q.market_cap)}<small>all its shares at today's price</small></dd></div>` : ''}
    </dl>
    ${items.length ? html`<div class="more">${items.map(([t1, b, hint]) => html`<details><summary>${t1}<span>${hint ? html`<small>${hint}</small>` : ''}${icon('chev')}</span></summary><div class="inner">${b}</div></details>`)}</div>` : ''}</section>`;
}

/* ---------------- the rest, one step away ---------------- */
// Optic's short-term setup (a swing grade), for readers who trade: deeper research, not a basic question
function tradeNow(sym) {
  const sw = (D.framework || {}).swing || {}, setup = sw.setup || {};
  if (!D.framework || !sw.grade || isFundHere(sym)) return '';
  const a = sw.grade === 'S' || sw.grade === 'A' ? `A grade ${sw.grade} ${setup.kind || 'setup'} by Optic's rules.` : sw.grade === 'B' ? `${capFirst(setup.kind || 'A setup')} is forming.` : "No setup by Optic's rules.";
  return html`<p><b>${a}</b> <span class="chip-tag">Grade ${sw.grade}</span> ${clean(setup.why || sw.why || '')}</p><p class="asof">A model's reading of the next few weeks' price action, not a recommendation. The full reading is on <a class="textlink" href="${hrefFor('swing', sym)}">Options</a>.</p>`;
}
function more(sym) {
  const t = D.ticker || {}, q = D.quote || {}, prof = (D.session || {}).profile || {};
  const cases = t.cases || {}, news = t.news || {}, fil = (t.filings || {}).filings || [];
  const name = q.name || sym;
  const kv = isFundHere(sym)
    ? [['P/E of its holdings', num(q.trailing_pe, 1)], ['Distribution yield', isNum(q.dividend_yield) ? `${num(q.dividend_yield * 100, 2)}%` : 'n/a'], ['52-week range', `${num(q.fifty_two_low)} to ${num(q.fifty_two_high)}`],
      ['Volume', compact(q.volume)], ['Average volume', compact(q.avg_volume)], ['Category', prof.category || 'n/a']]
    : [['Market cap', compact(q.market_cap)], ['P/E, trailing', num(q.trailing_pe, 1)], ['P/E, forward', num(q.forward_pe, 1)], ['52-week range', `${num(q.fifty_two_low)} to ${num(q.fifty_two_high)}`],
      ['Volume', compact(q.volume)], ['Average volume', compact(q.avg_volume)], ['Dividend yield', isNum(q.dividend_yield) ? `${num(q.dividend_yield * 100, 2)}%` : 'n/a'], ['Beta', num(q.beta, 2)]];
  const items = [
    ['Key figures', html`<dl class="kv">${kv.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`, ''],
    ...(tradeNow(sym) ? [['Short-term trade setup', tradeNow(sym), 'Swing grade']] : []),
    ...(cases.available ? [['Bull case and bear case', html`<div class="cases"><div><h3 class="case-h up">Bull case</h3><ul class="plain">${(cases.bull || []).map((c) => html`<li><b>${clean(c.claim)}.</b> ${clean(c.detail)}</li>`)}</ul></div><div><h3 class="case-h down">Bear case</h3><ul class="plain">${(cases.bear || []).map((c) => html`<li><b>${clean(c.claim)}.</b> ${clean(c.detail)}</li>`)}</ul></div></div>`, `${(cases.bull || []).length} for, ${(cases.bear || []).length} against`]] : []),
    ...(fil.length ? [['Recent SEC filings', html`<ul class="plain">${fil.slice(0, 5).map((f) => html`<li><a href="${f.url}" target="_blank" rel="noopener">${f.form}</a> ${clean(f.what)}, filed ${fullDate(f.filed)}</li>`)}</ul>`, `${Math.min(5, fil.length)} newest`]] : []),
  ];
  return html`<section class="section" aria-labelledby="mr-h"><h2 class="t-h2" id="mr-h">More on ${name}</h2>
    <div class="more">${items.map(([t1, b, hint]) => html`<details><summary>${t1}<span>${hint ? html`<small>${hint}</small>` : ''}${icon('chev')}</span></summary><div class="inner">${b}</div></details>`)}</div></section>`;
}

/* ---------------- the deeper research (Classic parity B6a) ---------------- */
const RUNG = { simple: 0, literate: 1, advanced: 2, professional: 3, adaptive: 1 };
function researchCtx(sym) {
  const t = D.ticker || null, fund = isFundHere(sym), lt = D.longterm || null;
  const ms = String((D.quote || {}).market_state || '').toUpperCase();
  const pr = t ? OR.priceRead(series()) : null;
  return { t, lt, D, fund, advanced: (RUNG[knowledge()] ?? 1) >= 2, session: ms === 'REGULAR' ? 'regular' : /POST/.test(ms) ? 'after' : 'closed',
    f: t ? OR.factors(t, { lt, stars: (D.fairValue || {}).stars, price: pr, fund }) : { pos: [], neg: [] } };
}
/** The Weinstein stage as a text label in the header line (owner's amendment: no chip), on the Overview alone as
 *  in Classic; what it means for this symbol opens from the label. */
function stageLabel(sym) {
  const r = D.stage;
  if (!r || r.available !== true) return '';
  defineLive(`stage:${sym}`, [r.explain, r.transition, r.limits].filter(Boolean).join(' '));
  return `Stage ${r.stage}, ${String(r.name || '').toLowerCase()}${r.transition_short ? `, ${String(r.transition_short).toLowerCase()}` : ''}`;
}

/* ---------------- page ---------------- */
function paint(main, sym) {
  if (!live) return;
  const keepFocus = document.activeElement && main.contains(document.activeElement) ? document.activeElement : null;
  const key = keepFocus && (keepFocus.dataset.v2Answer || keepFocus.dataset.v2Range || keepFocus.dataset.v2Watch);
  // what the reader opened stays open while later data arrives
  const openDetails = $$('details[open] summary', main).map((x) => x.textContent.trim());
  const openEvs = $$('[data-v2-ev][aria-expanded="true"]', main).map((x) => x.getAttribute('aria-controls'));
  const scrollY = window.scrollY;
  const rc = researchCtx(sym);
  draw(main, html`<div class="dstick">${frameHeader(sym, D, 'overview', { stage: stageLabel(sym) })}${frameTabs(sym, 'overview', { fund: isFund(D) })}</div>
    ${D.quoteError && !D.quote ? (D.quoteError.kind === 'notfound' ? empty(`Optic has no listing for ${sym}`, 'No quote came back for this symbol. It may be misspelled, delisted, or listed outside the US under another form.', html`<button type="button" class="btn btn-sm" data-v2-open-palette>Search for the company</button>`) : failed(`${sym}'s quote`, D.quoteError, { retry: 'dossier' })) : ''}
    ${((D.framework || {}).freshness || {}).state === 'stale' ? staleLine({ text: clean(D.framework.freshness.text) }) : ''}
    ${about(sym)}
    <section class="section dchart" aria-label="Price chart">${D.tickerError ? failed('The price history', D.tickerError, { retry: 'dossier' }) : chartBlock(sym)}</section>
    ${D.fwError && D.fvError && D.earnError ? failed('The four answers', D.fwError, { retry: 'dossier' }) : answers(sym)}${rc.fund ? OR.fundRisk(sym, rc.f) : ''}
    ${longViews(sym)}${combined()}${digest(sym)}${isFundHere(sym) ? '' : html`<div data-tc-slot></div>`}${OR.nextSection(sym, rc)}${D.ticker ? more(sym) : ''}${OR.advancedSection(sym, rc)}
    <p class="asof disclaimer">${clean((D.ticker || {}).disclaimer || 'Not financial advice. For research and education only.')}</p>`);
  mountThesis(main, sym, () => D);   // the thesis check: one node for the visit, so a half-typed note survives this redraw
  if (D.ticker) mountChart(main, sym);
  $$('details summary', main).forEach((x) => { if (openDetails.includes(x.textContent.trim())) x.parentElement.open = true; });
  openEvs.forEach((id) => { const b = $(`[aria-controls="${id}"]`, main); const body = document.getElementById(id); if (b && body) { b.setAttribute('aria-expanded', 'true'); body.hidden = false; } });
  if (Math.abs(window.scrollY - scrollY) > 2) window.scrollTo(0, scrollY);
  if (key) { const el = $(`[data-v2-answer="${key}"],[data-v2-range="${key}"],[data-v2-watch="${key}"]`, main); if (el) el.focus(); }
}

export async function render(main, route) {
  live = true;
  const sym = route.symbol;
  D = { sym };
  store.pushRecent(sym);
  provideContext(() => ({ view: 'overview', ticker: sym, quote: D.quote, verdict: (D.ticker || {}).verdict, company: (D.ticker || {}).company, news: (D.ticker || {}).news, framework: D.framework, fair_value: D.fairValue, earnings: D.earnings, digest: D.digest, thesis_check: thesisContext() }));
  document.title = `${sym} Dossier, Optic`;
  if (lp) lp.stop();
  lp = livePrice(main, route.symbol, () => D, 'overview', { stage: () => stageLabel(sym) });
  paint(main, sym);
  wire(main, sym);
  sections(main, 'overview', { levels: { 'advanced research': 2 }, norm: (t) => { const n = ((main.querySelector('.dhead .name span') || {}).textContent || '').trim(); return n ? t.split(n).join('the company') : t; } });   // folds, Expand all, Panels (Classic parity B3)
  const enc = encodeURIComponent(sym);
  const step = (p, ok, bad) => { p.then((d) => { if (D.sym === sym) ok(d); }, (e) => { if (D.sym === sym) bad(e); }).finally(() => { if (D.sym === sym) paint(main, sym); }); };
  step(api.get(`/api/quote/${enc}`, { ttl: 20000, timeout: 15000 }), (d) => { if (d && d.available !== false) D.quote = fresher(D.quote, d.quote || d); else { D.quoteError = new api.ApiError('notfound', 404, `No quote for ${sym}`); store.forgetRecent(sym); } }, (e) => { D.quoteError = e; });
  step(api.get(`/api/session/${enc}`, { ttl: 60000 }), (d) => { D.session = d; learn(sym, { session: d, quote: D.quote }); }, () => {});
  step(api.get(`/api/ticker/${enc}?max_expiries=4&macro=true`, { ttl: 120000, timeout: 60000 }), (d) => {
    D.ticker = d; if (d.quote) D.quote = fresher(D.quote, d.quote);
    if (d.data_caveat) D.freshText = clean(String(d.data_caveat).split(/(?<=\.)\s/)[0]);   // the delay; Greeks and Black-Scholes belong to Options
  }, (e) => { D.tickerError = e; });
  step(api.get(`/api/framework/${enc}?mode=combined`, { ttl: 300000, timeout: 60000 }), (d) => { D.framework = d.available === false ? null : d; if (d.available === false) D.fwError = new api.ApiError('notfound', 404, d.reason || 'No framework read'); }, (e) => { D.fwError = e; D.framework = {}; });
  step(api.get(`/api/fair-value/${enc}`, { ttl: 600000, timeout: 30000 }), (d) => { D.fairValue = d; }, (e) => { D.fvError = e; D.fairValue = {}; });
  step(api.get(`/api/longterm/${enc}?indices=false`, { ttl: 600000, timeout: 45000 }), (d) => { D.longterm = d; }, () => { D.longterm = {}; });
  step(api.get(`/api/earnings/${enc}`, { ttl: 600000, timeout: 45000 }), (d) => { D.earnings = d; }, (e) => { D.earnError = e; D.earnings = {}; });
  step(api.get(`/api/digest/${enc}`, { ttl: 300000, timeout: 30000 }), (d) => { D.digest = d; }, () => { D.digest = null; });
  step(api.get(`/api/segments/${enc}`, { ttl: 600000, timeout: 60000 }), (d) => { D.segments = d; }, () => { D.segments = null; });
  step(api.get(`/api/stage?symbol=${enc}`, { ttl: 3600000, timeout: 45000 }), (d) => { D.stage = d; }, () => { D.stage = null; });
}

export function dispose() { if (lp) { lp.stop(); lp = null; } live = false; disposeThesis(); drawer.close({ silent: true }); }

function wire(main, sym) {
  main.addEventListener('click', (e) => {
    const r = e.target.closest('[data-v2-range]');
    if (r) { range = r.dataset.v2Range; paint(main, sym); return; }
    const a = e.target.closest('[data-v2-answer]');
    if (a) {
      const k = a.dataset.v2Answer;
      const titles = { quality: 'How is the business doing?', price: PRICE_Q, trend: 'How has the share price moved?', next: "What's next?" };
      const asks = { quality: `How is ${sym}'s business doing?`, price: `How is ${sym} priced against its own history?`, trend: `How has ${sym}'s share price moved?`, next: `What's next for ${sym}?` };
      if (isFundHere(sym)) Object.assign(titles, { quality: 'What is it?', price: 'What do its holdings cost?', next: 'What does it pay?' });
      drawer.open({ kicker: `${sym}, evidence and method`, title: titles[k], opener: a,
        body: html`${evidence(k, sym)}${miloButton('Ask Milo about this', { ask: isFundHere(sym) ? `${titles[k].replace('?', '')}, for ${sym}?` : asks[k], context: `${sym}, ${titles[k]}`, symbol: sym })}` });
      return;
    }
    const evb = e.target.closest('[data-v2-ev]');
    if (evb) {
      const open = evb.getAttribute('aria-expanded') === 'true';
      evb.setAttribute('aria-expanded', String(!open));
      const b = document.getElementById(evb.getAttribute('aria-controls')); if (b) b.hidden = open;
    }
  });
}

export const retry = { dossier: (main, route) => { api.invalidate(`/api/quote/${route.symbol}`); api.invalidate(`/api/ticker/${route.symbol}`); render(main, route); } };
