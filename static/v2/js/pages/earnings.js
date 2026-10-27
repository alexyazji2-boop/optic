// Dossier, Earnings. The next report (or the latest result), what options
// price for it against history, estimate revisions, the surprise record,
// growth, and the analyst view, all from /api/earnings.
//
// The pre-earnings brief is written by a model (/api/earnings/{T}/brief) and
// costs Optic money on a cache miss. The classic app requested it on every
// visit; here it loads only when the reader asks, and says so.
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { sections } from '../ui/sections.js';
import { num, signed, dir, compact, clean, bolded, capFirst, longDate, fullDate, shortDate, isNum, ago, plural } from '../core/format.js';
import * as RP from '../core/reports.js';
import { mountCharts } from '../ui/chart.js';
import { signedBars, groupedBars } from '../ui/bars.js';
import * as FV from '../core/finviz.js';
import { term } from '../ui/term.js';
import { how } from '../ui/states.js';
import { skeleton, empty, failed, generated } from '../ui/states.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { core, header, tabs, isFund, livePrice } from './dossier-frame.js';
import { etStamp, sessionWord } from '../core/marketTime.js';
import { historyRatio } from './dossier.js';
let lp = null;   // the header's price refresh (dossier-frame livePrice), stopped in dispose()

let D = {}, live = true, mainEl = null;
const timing = { before_open: 'before the open', after_close: 'after the close', during: 'during the session' };
const kv = (rows, n = 4) => html`<dl class="kv" style="--kv:${n}">${rows.filter(Boolean).map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
const ask = (sym, label, q) => miloButton(label, { ask: q, context: `${sym} Dossier, Earnings`, symbol: sym });
const pct = (v, dp = 1) => (isNum(v) ? `${num(v, dp)}%` : 'n/a');   // num(null) + '%' printed "n/a%"
// The session that traded on a report: that day for one before the open, the next for one after the close.
const REACTION = 'Reaction';
const reactionWhen = (t) => (t === 'before_open' ? 'that session' : t === 'after_close' ? 'the next session' : 'the session that traded on it');

// The page opens on four questions a newcomer has (owner's beginner brief, 2026-10-20, item 7): when the company
// reports, what a report is, what analysts expect (EPS consensus in words, with the term and the figure kept), and
// what happened after earlier reports. The beat rate is never shown without what the price did after: Apple beat in
// 8 of 8 quarters and still fell after most of them.
function rows8() { return (((D.e || {}).surprise || {}).rows || []).map((r) => Object.assign({}, r, FV.surprise(r.eps_estimate, r.eps_reported, r.surprise_pct))); }
export function afterBeats(rows) {
  const beats = rows.filter((r) => r.cls === 'beat' && isNum(r.next_day_move_pct));
  return { n: beats.length, fell: beats.filter((r) => r.next_day_move_pct < 0).length, avg: beats.length ? beats.reduce((a, r) => a + r.next_day_move_pct, 0) / beats.length : null };
}
function hero(sym) {
  const e = D.e, nr = e.next_report || {}, lr = e.latest_result || {}, s = e.surprise || {}, name = (D.quote || {}).name || sym;
  const upcoming = nr.date && !lr.just_reported;
  const R = rows8(), beats = R.filter((r) => r.cls === 'beat').length, misses = R.filter((r) => r.cls === 'miss').length, inl = R.filter((r) => r.cls === 'in line').length;
  const ab = afterBeats(R);
  const when = upcoming ? html`<p class="ern-when"><b>${name} reports on ${longDate(nr.date)}</b>, in ${nr.days_away} ${nr.days_away === 1 ? 'day' : 'days'}: ${RP.dateStatus(nr)}${nr.confirmed ? '' : ', so it may move'}. ${RP.habitLine(nr, `${name}'s`)}</p>`
    : lr.date ? html`<p class="ern-when"><b>${name} last reported on ${fullDate(lr.date)}.</b> ${nr.date ? '' : 'No next date is in the data yet.'}</p>`
      : html`<p class="ern-when"><b>No report date on record for ${sym}.</b> There is no next report date and no latest result in the feed for this company.</p>`;
  const expect = upcoming && isNum(nr.eps_consensus) ? html`<p>Analysts expect ${term('earnings per share', 'earnings per share')} (${term('eps', 'EPS')}) of <b>$${num(nr.eps_consensus)}</b> for the quarter, the average of their estimates (the ${term('consensus', 'consensus')})${isNum(nr.eps_low) && isNum(nr.eps_high) ? `, within a range of $${num(nr.eps_low)} to $${num(nr.eps_high)}` : ''}${nr.revenue_consensus_label ? html`, on revenue of about <b>${nr.revenue_consensus_label}</b>` : ''}.${nr.consensus_note ? html` <span class="t-muted">${clean(nr.consensus_note)}</span>` : ''}</p>` : '';
  const before = R.length ? html`<p>In the last ${R.length} reports, ${name} ${beats === R.length ? `beat the estimate every time` : `beat the estimate ${beats} ${beats === 1 ? 'time' : 'times'}${misses ? `, missed ${misses}` : ''}${inl ? `, and was in line ${inl}` : ''}`}.${ab.n ? html` ${ab.fell * 2 > ab.n ? html`<b>But the share price fell after ${ab.fell} of ${ab.n === beats ? 'those' : 'the'} ${ab.n} beats${ab.n === beats ? '' : ' with a price move on record'}</b>` : `The share price fell after ${ab.fell} of ${ab.n === beats ? 'those' : 'the'} ${ab.n} beats${ab.n === beats ? '' : ' with a price move on record'}`}${isNum(ab.avg) ? `, ${ab.avg < 0 ? 'down' : 'up'} ${num(Math.abs(ab.avg), 1)}% on average in the session that traded on the report` : ''}. Beating estimates does not mean the price rises: the price already reflects what investors expected, and the reaction depends on the whole report.` : ''}</p>` : '';
  const latest = !upcoming && (lr.date || isNum(lr.eps_reported)) ? (() => { const sv = FV.surprise(lr.eps_estimate, lr.eps_reported, lr.surprise_pct); return html`<p>Latest result: EPS $${num(lr.eps_reported)} against $${num(lr.eps_estimate)} expected, ${sv.cls === 'missing' ? 'no estimate to compare with' : sv.pct === null ? `${sv.cls}, by $${num(Math.abs(sv.diff))}` : `${sv.cls}${sv.cls === 'in line' ? '' : ` by ${num(Math.abs(sv.pct), 1)}%`}`}; the price moved ${signed(lr.next_day_move_pct)} in the session that traded on it.</p>`; })() : '';
  return html`<section class="section ern-lead" aria-labelledby="nr-h"><h2 class="t-h2" id="nr-h">${upcoming ? 'The next report' : 'The latest report'}</h2>
    ${when}<p class="t-muted ern-what">An ${term('earnings report', 'earnings report')} is a company's results for the quarter: what it sold, the profit it kept, and often what it expects next.</p>
    ${expect}${latest}${before}
    <p class="asof">${e.generated_at ? `Read ${ago(e.generated_at)}. ` : ''}Estimates, reported EPS and prices from Yahoo Finance${s.quarters ? `, ${s.quarters} quarters of history` : ''}. ${clean(s.eps_basis || '')}</p>
    ${(e.extended_hours || {}).available ? html`<p class="asof">${sessionWord(e.extended_hours.kind)} ${num(e.extended_hours.price)}, ${signed(e.extended_hours.move_pct)} from the close${e.extended_hours.as_of ? `, struck ${etStamp(e.extended_hours.as_of)}` : ''}. The header shows the latest print, which can be from a later session. ${clean(e.extended_hours.caveat || '')}</p>` : ''}
  </section>`;
}

// What Optic's earnings verdict reads from these figures: a model's reading, kept with the deeper research
function verdictBlock() {
  const v = (D.e || {}).verdict || {}, nr = (D.e || {}).next_report || {}, lr = (D.e || {}).latest_result || {};
  if (!v.headline && !nr.dispersion_note && !lr.reaction_fights_result) return '';
  return html`<section class="section" aria-labelledby="vd-h"><h2 class="t-h2" id="vd-h">Optic's reading of the setup</h2><p class="section-sub">A model's reading of the figures on this page, not a recommendation.</p>
    ${v.headline ? html`<p><b>${clean(v.headline)}</b></p><ul class="plain">${(v.reasons || []).map((r) => html`<li>${clean(r)}</li>`)}</ul>` : ''}
    ${nr.dispersion_note ? html`<p>${clean(nr.dispersion_note)}</p>` : ''}
    ${lr.reaction_fights_result ? html`<p class="stale">The stock moved against the result: a beat that fell or a miss that rose.</p>` : ''}</section>`;
}

// Reported against expected, and what the price did after: two figures on the same quarters, each with its
// own scale, the window and the sample said (data-viz brief items 2 and 7)
function history(sym) {
  const R = rows8(); if (!R.length) return '';
  const s = (D.e || {}).surprise || {}, last = R[0], ab = afterBeats(R);
  const small = R.some((r) => r.small);
  const lastWords = last.cls === 'missing' ? '' : last.pct === null ? ` The latest, ${last.fiscal || fullDate(last.date)}, ${last.cls === 'in line' ? 'was in line' : `${last.cls === 'beat' ? 'beat' : 'missed'} by $${num(Math.abs(last.diff))} a share`}.` : ` The latest, ${last.fiscal || fullDate(last.date)}, ${last.cls === 'in line' ? 'was in line' : `${last.cls === 'beat' ? 'beat' : 'missed'} by $${num(Math.abs(last.diff))} a share (${num(Math.abs(last.pct), 1)}%)`}.`;
  const moves = R.filter((r) => isNum(r.next_day_move_pct)), up = moves.filter((r) => r.next_day_move_pct > 0).length;
  return html`<section class="section" id="ern-history" aria-labelledby="eh-h"><h2 class="t-h2" id="eh-h">Earlier reports</h2>
    <div class="fv-grid">
      <figure class="fv"><figcaption><h3>Reported against expected</h3><p class="fv-take">${R.filter((r) => r.cls === 'beat').length} beats, ${R.filter((r) => r.cls === 'miss').length} misses and ${R.filter((r) => r.cls === 'in line').length} in line in the last ${R.length} quarters.${lastWords}</p>
        <p class="legend-line fv-key"><span><i class="sw s0 hollow"></i>Analysts' estimate</span><span><i class="sw s1"></i>Reported EPS</span></p><p class="fv-unit">EPS in dollars a share, by quarter, on analysts' basis. Under each quarter: beat, miss or in line.</p></figcaption>
        <div class="chart-slot" data-chart="eps"></div></figure>
      <figure class="fv"><figcaption><h3>What the price did after</h3><p class="fv-take">The price rose after ${up} of ${moves.length} reports and fell after ${moves.length - up}${ab.n ? `; after the ${ab.n} beats it fell ${ab.fell} ${ab.fell === 1 ? 'time' : 'times'}` : ''}. Largest move ${signed(s.largest_move_pct)}.</p>
        <p class="fv-unit">The move in the session that traded on each report: that session for a report before the open, the next one for a report after the close. After-hours and longer moves are not in this data. ${moves.length} reports.</p></figcaption>
        <div class="chart-slot" data-chart="react"></div></figure>
    </div>
    <details class="more-inline fv-data"><summary>View data</summary><div class="tscroll"><table class="t"><thead><tr><th scope="col">Quarter</th><th scope="col">Reported on</th><th scope="col">Estimate</th><th scope="col">Reported</th><th scope="col">Difference</th><th scope="col">Surprise</th><th scope="col">Result</th><th scope="col">${REACTION}</th></tr></thead>
      <tbody>${R.map((x) => html`<tr><th scope="row">${x.fiscal || shortDate(x.date)}</th><td>${fullDate(x.date)}${x.timing && timing[x.timing] ? html`<small class="t-muted"> ${timing[x.timing]}</small>` : ''}</td><td>${num(x.eps_estimate)}</td><td>${num(x.eps_reported)}</td><td>${isNum(x.diff) ? signed(x.diff, 2, '') : 'n/a'}</td><td>${x.pct === null ? (x.small ? 'n/a, estimate under $0.10' : 'n/a') : signed(x.pct, 1)}</td><td>${FV.CLASS_WORD[x.cls]}</td><td>${isNum(x.next_day_move_pct) ? signed(x.next_day_move_pct) : 'Not reported'}</td></tr>`)}</tbody></table></div>
      <p class="asof">A result is in line when the difference rounds to nothing, a beat above the estimate and a miss below it. ${small ? 'Where the estimate is under ten cents a share, a percentage of almost nothing misleads, so only the dollar difference is given. ' : ''}${clean(s.eps_basis || '')}</p>
      <ul class="plain">${(s.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul></details></section>`;
}

// What options price for the report day, against what past report days did: both one session (the options
// market's report-day move from the term structure, never the straddle to a later expiry), labelled as market
// pricing. Kept with the options detail, which a newcomer can leave closed (beginner brief item 7).
function eventDay() { const ev = (((D.t || {}).vol_surface || {}).event) || {}; return ev.available && isNum(ev.move_pct) && ev.move_pct > 0 ? ev : null; }
function pricing(sym) {
  const e = D.e, pr = e.pricing || {}, im = e.implied || {}, nr = e.next_report || {}, ev = eventDay();
  if (!pr.available && !im.available && !ev) return '';
  const imx = im.available ? { pct: im.implied_move_pct, expiry: im.expiry } : null;
  const R = rows8(), cmp = FV.reactionVsImplied(R.map((r) => r.next_day_move_pct), ev ? ev.move_pct : null);
  return html`<section class="section" id="ern-options" aria-labelledby="ep-h"><div class="section-head"><div><h2 class="t-h2" id="ep-h">What options price for the report</h2><p class="section-sub">For readers who use options. The ${term('implied move', 'implied move')} is what options cost, not a forecast or a guaranteed range.</p></div>${ask(sym, 'Ask Milo about the event pricing', `Are ${sym}'s options priced rich or cheap for the coming report?`)}</div>
    ${ev && cmp ? html`<figure class="fv"><figcaption><p class="fv-take">Options price a move of about <b>±${num(ev.move_pct, 1)}% for the report day itself</b>${nr.date ? ` (${shortDate(nr.date)})` : ''}. The last ${cmp.n} reports moved ${num(cmp.avg, 1)}% on average in the session that traded on them; ${cmp.over} of ${cmp.n} moved more than ±${num(ev.move_pct, 1)}%.</p>
        <p class="legend-line fv-key"><span><i class="sw s1"></i>Size of each past report-day move</span><span><i class="ref-sw"></i>Today's report-day price, ±${num(ev.move_pct, 1)}%</span></p><p class="fv-unit">One session each: the past moves and the priced move cover the same window. Read from the ${shortDate(ev.after)} expiry against the ${shortDate(ev.before)} one.</p></figcaption>
      <div class="chart-slot" data-chart="evday"></div></figure>` : ''}
    ${im.available ? html`<p><b>±${num(im.implied_move_pct)}% through the ${shortDate(im.expiry)} expiry.</b> The ${num(im.strike, 0)} ${term('straddle', 'straddle')} costs $${num(im.straddle_cost)}, ${plural(im.dte, 'day')} out, at ${num(im.atm_iv_pct, 1)}% ${term('implied volatility', 'implied volatility')}. It covers ${plural(im.dte, 'day')} of ordinary trading as well as the report, so it is not the report day's move and is not compared with one.</p>
      <p class="asof">${im.priced_from === 'last_trades' ? `Priced from the contracts' last trades${im.last_trade ? `, the oldest ${etStamp(im.last_trade)}` : ''}: no two-sided quotes right now, so this is where they last traded, not where they are quoted.` : 'Priced from two-sided quotes, at the mid.'}</p>` : ''}
    ${historyRatio(pr, imx, (e.surprise || {}).quarters)}
    ${pr.stale ? html`<p class="stale">${clean(pr.stale_note || '')}</p>` : ''}${how(html`<p>${clean(pr.caveat || '')}</p>`, ev ? html`<p>The report day's move is the variance the ${shortDate(ev.after)} expiry carries beyond what the ${shortDate(ev.before)} expiry's rate implies for the ordinary days in between.</p>` : '')}</section>`;
}
function brief(sym) {
  const b = D.brief;
  return html`<section class="section" aria-labelledby="br-h"><div class="section-head"><div><h2 class="t-h2" id="br-h">Pre-earnings brief</h2><p class="section-sub">A short summary of this page's figures, written by an AI model when a reader asks, then kept for six hours per report date for everyone.</p></div></div>
    ${b === undefined ? html`<p class="t-muted" role="status">Looking for a brief already written...</p>`
    : b === 'loading' ? skeleton('lines', 4, 'Writing the brief')
      : b.error && b.error.kind === 'auth' ? html`<p>Writing a brief uses one Milo message, so it needs a free account. A brief someone has already written shows here for everyone.</p><a class="btn btn-primary" href="#/signin">Sign in or create an account</a>`
        : b.error && b.error.kind === 'limit' ? html`<p class="stale" role="status">${clean(b.error.message || 'Your Milo messages for today are used.')} A brief someone else writes for this report will show here.</p>`
          : b.error ? failed('The brief', b.error, { retry: 'brief' })
            : !b.available && b.written === false && b.can_write ? html`<p class="t-muted">${clean(b.reason || '')}</p><button type="button" class="btn" data-v2-brief>Write the pre-earnings brief</button>`
              : !b.available ? html`<p class="${b.refused ? 'stale' : 't-muted'}" role="status">${clean(b.reason || 'No brief right now.')}</p>`
          : html`<p class="t-label">${capFirst(b.stance || '')}</p><p class="t-h3">${clean(b.headline || '')}</p>${(b.paragraphs || []).map((p) => html`<p>${raw(bolded(p))}</p>`)}${generated(b.written_by ? b : Object.assign({ written_by: 'model' }, b), { at: b.generated_at })}<p class="asof">${clean(b.method || '')} ${clean(b.disclaimer || '')}</p>`}
  </section>`;
}

function revisions(sym) {
  const r = D.e.revisions || {};
  if (!r.available) return '';
  return html`<section class="section" aria-labelledby="rv-h"><h2 class="t-h2" id="rv-h">Estimate revisions</h2>
    <p>${clean(r.note || '')}${isNum(r.analysts_up_30d) && isNum(r.analysts_down_30d) ? ` ${r.analysts_up_30d} ${r.analysts_up_30d === 1 ? 'analyst' : 'analysts'} raised and ${r.analysts_down_30d} cut in the last 30 days.` : ''}</p>
    <div class="chart-slot" data-chart="rev"></div>
    <div class="tscroll"><table class="t"><thead><tr><th>Period</th><th>Estimate</th><th>30 days</th><th>90 days</th><th>Up, 30 days</th><th>Down, 30 days</th></tr></thead>
      <tbody>${r.rows.map((x) => html`<tr><td>${x.label}</td><td>${num(x.current)}</td><td>${signed(x.chg_30d_pct)}</td><td>${signed(x.chg_90d_pct)}</td><td>${x.analysts_up_30d}</td><td>${x.analysts_down_30d}</td></tr>`)}</tbody></table></div>
    <p class="asof">${clean(r.caveat || '')}</p></section>`;
}

// A growth table: a column with no figure in any row is left out rather than shown as a column of n/a.
const GROWTH_COLS = [['revenue', 'Revenue', (v) => compact(v)], ['revenue_yoy_pct', 'Growth', (v) => signed(v)], ['net_income', 'Net income', (v) => compact(v)], ['net_income_yoy_pct', 'Growth', (v) => signed(v)], ['gross_margin_pct', 'Gross margin', (v) => pct(v)], ['operating_margin_pct', 'Operating margin', (v) => pct(v)]];
export function growthTable(rows) {
  const cols = GROWTH_COLS.filter(([k]) => rows.some((x) => isNum(x[k])));
  return html`<thead><tr><th scope="col">Period</th>${cols.map(([, l]) => html`<th scope="col">${l}</th>`)}</tr></thead><tbody>${rows.map((x) => html`<tr><th scope="row">${x.fiscal || `${shortDate(x.period)} ${String(x.period).slice(0, 4)}`}<small class="t-muted fin-end">to ${shortDate(x.period)} ${String(x.period).slice(2, 4)}</small></th>${cols.map(([k, , f]) => html`<td>${f(x[k])}</td>`)}</tr>`)}</tbody>`;
}
// The business the reports describe: reported quarters, then what analysts expect, drawn hollow and labelled as
// estimates so a forecast is never read as a result
function growth() {
  const g = D.e.growth || {};
  if (!(g.quarterly || []).length && !(g.annual || []).length) return '';
  const q = g.quarterly || [], fw = (g.forward || []).filter((f) => /q$/.test(f.period || '') && isNum(f.revenue_avg));
  const lab = q.map((r) => r.fiscal || shortDate(r.period));
  const yoy = q[0] && isNum(q[0].revenue_yoy_pct) ? `Revenue ${q[0].revenue_yoy_pct >= 0 ? 'grew' : 'fell'} ${num(Math.abs(q[0].revenue_yoy_pct), 1)}% from the same quarter a year before, to ${FV.usd(q[0].revenue)} in ${lab[0]}.` : q[0] ? `Revenue was ${FV.usd(q[0].revenue)} in ${lab[0]}.` : '';
  const ni = q[0] && isNum(q[0].net_income) ? ` Net income was ${FV.usd(q[0].net_income)}${isNum(q[0].net_income_yoy_pct) ? `, ${q[0].net_income_yoy_pct >= 0 ? 'up' : 'down'} ${num(Math.abs(q[0].net_income_yoy_pct), 1)}%` : ''}.` : '';
  const ahead = fw[0] ? ` Analysts expect about ${fw[0].revenue_label || FV.usd(fw[0].revenue_avg)} of revenue for the ${fw[0].label.toLowerCase()}${isNum(fw[0].revenue_growth_pct) ? `, ${signed(fw[0].revenue_growth_pct)} on a year before` : ''}: an estimate, not a result.` : '';
  return html`<section class="section" aria-labelledby="gr-h"><h2 class="t-h2" id="gr-h">The business behind the reports</h2>
    ${q.length ? html`<figure class="fv"><figcaption><p class="fv-take">${yoy}${ni}${ahead}</p>
      <p class="legend-line fv-key"><span><i class="sw s1"></i>Revenue</span><span><i class="sw s3"></i>Net income</span>${fw.length ? html`<span><i class="sw s1 hollow"></i>Revenue, analysts' estimate</span>` : ''}</p><p class="fv-unit">By quarter, US dollars. Reported quarters first, then estimates.</p></figcaption>
      <div class="chart-slot" data-chart="growth"></div></figure>` : ''}
    <details class="more-inline fv-data"><summary>View data</summary>
      ${q.length ? html`<h3>Quarters</h3><div class="tscroll"><table class="t">${growthTable(q)}</table></div>` : ''}
      ${(g.annual || []).length ? html`<h3>Fiscal years</h3><div class="tscroll"><table class="t">${growthTable(g.annual)}</table></div>` : ''}
      ${(g.forward || []).length ? html`<h3>What analysts expect</h3><div class="tscroll"><table class="t"><thead><tr><th>Period</th><th>EPS</th><th>EPS growth</th><th>Revenue</th><th>Revenue growth</th><th>Analysts</th></tr></thead><tbody>${g.forward.map((f) => html`<tr><td>${f.label}</td><td>${num(f.eps_avg)}</td><td>${signed(f.eps_growth_pct)}</td><td>${f.revenue_label || 'n/a'}</td><td>${signed(f.revenue_growth_pct)}</td><td>${f.eps_analysts || 'n/a'}</td></tr>`)}</tbody></table></div>` : ''}
      <ul class="plain">${(g.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul></details></section>`;
}

function analysts(sym) {
  const a = D.e.analyst || {};
  if (!isNum(a.target_mean) && !(a.ratings || []).length) return '';
  return html`<section class="section" aria-labelledby="an-h"><div class="section-head"><h2 class="t-h2" id="an-h">Analyst view</h2>${ask(sym, 'Ask Milo about the analysts', `How much weight should I give analysts' view of ${sym}?`)}</div>
    ${kv([['Average target', html`${num(a.target_mean)} <span class="t-muted">${signed(a.upside_pct, 1)}</span>`], ['Range', `${num(a.target_low)} to ${num(a.target_high)}`], ['Ratings', `${a.buys} buy, ${a.holds} hold, ${a.sells} sell`], ['Analysts', a.analyst_count]], 4)}
    <div class="tscroll"><table class="t"><thead><tr><th>Month</th><th>Strong buy</th><th>Buy</th><th>Hold</th><th>Sell</th><th>Strong sell</th></tr></thead>
      <tbody>${(a.ratings || []).map((r) => html`<tr><td>${r.period === '0m' ? 'This month' : `${r.period.replace('-', '').replace('m', '')} months ago`}</td><td>${num(r.strong_buy, 0)}</td><td>${num(r.buy, 0)}</td><td>${num(r.hold, 0)}</td><td>${num(r.sell, 0)}</td><td>${num(r.strong_sell, 0)}</td></tr>`)}</tbody></table></div>
    <ul class="plain">${(a.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul></section>`;
}

function makers() {
  const e = D.e || {};
  const rv = (e.revisions || {}).rows || [], R = rows8().slice().reverse(), q = ((e.growth || {}).quarterly || []).slice().reverse();
  const fw = ((e.growth || {}).forward || []).filter((f) => /q$/.test(f.period || '') && isNum(f.revenue_avg));
  const G = R.map((r) => ({ x: r.fiscal || shortDate(r.date), sub: FV.CLASS_WORD[r.cls], subCls: r.cls.replace(' ', '-') }));
  const ev = eventDay();
  const out = {
    rev: (w) => signedBars(rv.map((r) => ({ x: r.label, v: r.chg_90d_pct, label: `${r.label}: ${signed(r.chg_90d_pct)} over 90 days` })), { w, h: 150, label: 'Estimate change over 90 days by period', fmt: (v) => signed(v), xfmt: (x) => x.replace('Current ', '').replace('Next ', 'next ') }),
    eps: (w) => groupedBars(G, [{ name: "Analysts' estimate", cls: 's0', hollow: true, values: R.map((r) => r.eps_estimate), missingText: 'No estimate' }, { name: 'Reported EPS', cls: 's1', values: R.map((r) => r.eps_reported) }], { w, h: 230, fmt: (v) => `$${num(v, 2)}`, axisFmt: (v) => `$${num(v, 2)}`, valueLabels: 'none', label: 'EPS estimate against reported, by quarter', note: (i) => { const r = R[i]; return r.cls === 'missing' ? 'No estimate to compare' : `${FV.CLASS_WORD[r.cls]}${isNum(r.diff) ? `, ${signed(r.diff, 2, '')} a share` : ''}${r.pct !== null && r.cls !== 'in line' ? ` (${signed(r.pct, 1)})` : ''}`; } }),
    react: (w) => groupedBars(R.map((r) => ({ x: r.fiscal || shortDate(r.date), sub: FV.CLASS_WORD[r.cls], subCls: r.cls.replace(' ', '-') })), [{ name: 'Price move in the reaction session', cls: 's2', values: R.map((r) => r.next_day_move_pct), missingText: 'Not reported' }], { w, h: 230, fmt: (v) => signed(v), axisFmt: (v) => `${num(v, 0)}%`, label: 'Share price move in the session that traded on each report', note: (i) => `${fullDate(R[i].date)}, ${timing[R[i].timing] || ''}` }),
    growth: (w) => groupedBars([...q.map((r) => ({ x: r.fiscal || shortDate(r.period) })), ...fw.map((f) => ({ x: f.label.replace('Current quarter', 'This quarter'), sub: 'Estimate' }))],
      [{ name: 'Revenue', cls: 's1', values: [...q.map((r) => r.revenue), ...fw.map(() => null)] }, { name: 'Net income', cls: 's3', values: [...q.map((r) => r.net_income), ...fw.map(() => null)], missingText: 'No estimate' }, { name: "Revenue, analysts' estimate", cls: 's1', hollow: true, values: [...q.map(() => null), ...fw.map((f) => f.revenue_avg)], missingText: 'Reported, see Revenue' }],
      { w, h: 230, fmt: FV.usd, valueLabels: 'none', label: 'Quarterly revenue and net income, then analysts\' revenue estimates' }),
  };
  if (ev) out.evday = (w) => groupedBars(R.map((r) => ({ x: r.fiscal || shortDate(r.date) })), [{ name: 'Size of the report-day move', cls: 's1', values: R.map((r) => (isNum(r.next_day_move_pct) ? Math.abs(r.next_day_move_pct) : null)) }], { w, h: 200, fmt: (v) => `${num(v, 1)}%`, axisFmt: (v) => `${num(v, 0)}%`, refs: [{ v: ev.move_pct, text: `Priced today: ±${num(ev.move_pct, 1)}%` }], label: 'Size of past report-day moves against the move options price for the next report day' });
  return out;
}

function paint() {
  if (!live) return;
  const sym = D.sym;
  const y = window.scrollY;
  let body;
  if (D.err) body = failed('The earnings data', D.err, { retry: 'earnings' });
  else if (!D.e) body = skeleton('lines', 6, 'Loading the earnings data');
  else if (D.e.not_applicable) body = empty(`No earnings for ${sym}`, clean(D.e.reason || 'Funds and indices do not report earnings.'));
  // the newcomer's questions first; Optic's reading, revisions, analysts and options after (beginner brief item 7)
  else body = html`${hero(sym)}${history(sym)}${growth()}${brief(sym)}${revisions(sym)}${analysts(sym)}${verdictBlock()}${pricing(sym)}<p class="asof disclaimer">${clean(D.e.data_caveat || '')} ${clean(D.e.disclaimer || '')}</p>`;
  draw(mainEl, html`<div class="dstick">${header(sym, D, 'earnings')}${tabs(sym, 'earnings', { fund: isFund(D) })}</div><div class="earn">${body}</div>`);
  if (D.e && !D.e.not_applicable) mountCharts(mainEl, makers());
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

// A brief already written is read for free when the page opens; writing one is a POST, metered like Milo, only when
// the reader presses Write (the GET used to write one on a cache miss for anyone who opened the tab).
async function keptBrief(box) {
  try { box.brief = await api.get(`/api/earnings/${encodeURIComponent(box.sym)}/brief`, { ttl: 300000, timeout: 60000 }); }
  catch (e) { box.brief = { available: false, reason: api.explain(e, 'The brief'), written: false, can_write: true }; }
  if (D === box) paint();
}
async function loadBrief() {
  const box = D;
  box.brief = 'loading'; paint();
  try { box.brief = await api.post(`/api/earnings/${encodeURIComponent(box.sym)}/brief`, {}, { timeout: 90000 }); api.invalidate(`/api/earnings/${encodeURIComponent(box.sym)}/brief`); }
  catch (e) { box.brief = { error: e }; }
  if (D !== box) return;
  paint();
  const b = mainEl.querySelector('#br-h'); if (b) { b.setAttribute('tabindex', '-1'); b.focus({ preventScroll: true }); }
}

export async function render(main, route) {
  live = true; mainEl = main;
  const sym = route.symbol;
  D = { sym };
  store.pushRecent(sym);
  document.title = `${sym} Earnings, Optic`;
  if (lp) lp.stop();
  lp = livePrice(main, route.symbol, () => D, 'earnings', undefined);
  provideContext(() => ({ view: 'earnings', ticker: sym, quote: D.quote, earnings: D.e }));
  paint();
  // the strip, folds and Panels (Classic parity B3); the implied move opens from Advanced, as Classic's event pricing did
  sections(main, 'earnings', { levels: { 'what options price for the report': 2 }, norm: (t) => { const n = ((main.querySelector('.dhead .name span') || {}).textContent || '').trim(); return n ? t.split(n).join('the company') : t; } });
  main.addEventListener('click', (e) => { if (e.target.closest('[data-v2-brief]')) loadBrief(); });
  core(sym).then((c) => { if (D.sym !== sym) return; D.quote = c.quote; D.session = c.session; D.quoteError = c.quoteError; paint(); });
  // the options term structure, for the move priced for the report day itself (one session, as the reactions are);
  // the same snapshot the other Dossier pages read, so it is usually cached already
  api.get(`/api/ticker/${encodeURIComponent(sym)}?max_expiries=4&macro=true`, { ttl: 120000, timeout: 60000 }).then((t) => { if (D.sym === sym) { D.t = t; if (D.e) paint(); } }, () => {});
  try { D.e = await api.get(`/api/earnings/${encodeURIComponent(sym)}`, { ttl: 600000, timeout: 60000 }); }
  catch (e) { if (D.sym === sym) D.err = e; }
  if (D.sym === sym) paint();
  if (D.sym === sym && D.e && !D.e.not_applicable && D.brief === undefined) keptBrief(D);
}
export function dispose() { if (lp) { lp.stop(); lp = null; } live = false; }
export const retry = { earnings: (m, r) => { api.invalidate('/api/earnings'); render(m, r); }, brief: () => loadBrief() };
void ago;
