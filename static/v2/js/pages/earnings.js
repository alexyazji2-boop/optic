// Dossier, Earnings. The next report (or the latest result), what options
// price for it against history, estimate revisions, the surprise record,
// growth, and the analyst view, all from /api/earnings.
//
// The pre-earnings brief is written by a model (/api/earnings/{T}/brief) and
// costs Optic money on a cache miss. The classic app requested it on every
// visit; here it loads only when the reader asks, and says so.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, signed, compact, clean, capFirst, longDate, fullDate, shortDate, isNum, ago } from '../core/format.js';
import { mountCharts } from '../ui/chart.js';
import { signedBars } from '../ui/bars.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { core, header, tabs, isFund } from './dossier-frame.js';
import { etStamp, sessionWord } from '../core/marketTime.js';
import { historyRatio } from './dossier.js';

let D = {}, live = true, mainEl = null;
const timing = { before_open: 'before the open', after_close: 'after the close', during: 'during the session' };
const kv = (rows, n = 4) => html`<dl class="kv" style="--kv:${n}">${rows.filter(Boolean).map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
const ask = (sym, label, q) => miloButton(label, { ask: q, context: `${sym} Dossier, Earnings`, symbol: sym });

function hero(sym) {
  const e = D.e, nr = e.next_report || {}, lr = e.latest_result || {}, s = e.surprise || {}, im = e.implied || {}, pr = e.pricing || {}, v = e.verdict || {};
  const upcoming = nr.date && !lr.just_reported;
  return html`<section class="section" aria-labelledby="nr-h">
    <p class="t-label" id="nr-h">${upcoming ? 'Next report' : 'Latest result'}</p>
    ${upcoming ? html`<p class="t-display-m">${longDate(nr.date)}</p><p class="delta"><span>${capFirst(timing[nr.timing] || '')}${timing[nr.timing] ? ', ' : ''}in ${nr.days_away} days</span><span class="t-muted">${nr.confirmed ? 'Confirmed' : 'Not yet confirmed'}</span>${pr.available ? html`<span class="pill">Priced ${pr.stance === 'fair' ? 'about in line' : pr.stance === 'expensive' ? 'rich' : 'cheap'} against history</span>` : ''}</p>`
    : html`<p class="t-display-m">EPS ${num(lr.eps_reported)} <small class="t-muted">against ${num(lr.eps_estimate)}</small></p><p class="delta"><span class="${lr.beat ? 'up' : 'down'}">${lr.beat ? 'Beat' : 'Missed'} by ${num(Math.abs(lr.surprise_pct), 1)}%</span><span>Next day ${signed(lr.next_day_move_pct)}</span><span class="t-muted">${fullDate(lr.date)}</span></p>`}
    ${kv([
      upcoming ? ['EPS consensus', html`${num(nr.eps_consensus)} <span class="t-muted">${num(nr.eps_low)} to ${num(nr.eps_high)}</span>`] : ['Surprise', signed(lr.surprise_pct, 1)],
      upcoming ? ['Revenue consensus', nr.revenue_consensus_label || 'n/a'] : ['Move after', signed(lr.next_day_move_pct)],
      im.available ? [`Implied move through ${shortDate(im.expiry)}`, `±${num(im.implied_move_pct)}%`] : null,
      s.available ? ['Beat rate', `${num(s.beat_rate_pct, 0)}% of ${s.quarters} quarters`] : null,
    ], 4)}
    ${nr.dispersion_note ? html`<p>${clean(nr.dispersion_note)}</p>` : ''}
    ${lr.reaction_fights_result ? html`<p class="stale">The stock moved against the result: a beat that fell or a miss that rose.</p>` : ''}
    ${v.headline ? html`<p><b>${clean(v.headline)}</b></p><ul class="plain">${(v.reasons || []).map((r) => html`<li>${clean(r)}</li>`)}</ul>` : ''}
    ${(e.extended_hours || {}).available ? html`<p class="asof">${sessionWord(e.extended_hours.kind)} ${num(e.extended_hours.price)}, ${signed(e.extended_hours.move_pct)} from the close${e.extended_hours.as_of ? `, struck ${etStamp(e.extended_hours.as_of)}` : ''}. The header shows the latest print, which can be from a later session. ${clean(e.extended_hours.caveat || '')}</p>` : ''}
  </section>`;
}

function brief(sym) {
  const b = D.brief;
  return html`<section class="section" aria-labelledby="br-h"><div class="section-head"><div><h2 class="t-h2" id="br-h">Pre-earnings brief</h2><p class="section-sub">A short written read of the facts on this page, by Optic's writer. Kept for six hours per report date.</p></div></div>
    ${b === undefined ? html`<button type="button" class="btn" data-v2-brief>Write the pre-earnings brief</button><p class="asof">Loads only when you ask, because writing it uses a paid model.</p>`
    : b === 'loading' ? skeleton('lines', 4, 'Writing the brief')
      : b.error ? failed('The brief', b.error, { retry: 'brief' })
        : !b.available ? html`<p class="t-muted">${clean(b.reason || 'No brief right now.')}</p>`
          : html`<p class="t-label">${capFirst(b.stance || '')}</p><p class="t-h3">${clean(b.headline || '')}</p>${(b.paragraphs || []).map((p) => html`<p>${clean(p)}</p>`)}<p class="asof">${clean(b.method || '')} ${b.generated_at ? `Written ${ago(b.generated_at)}.` : ''} ${clean(b.disclaimer || '')}</p>`}
  </section>`;
}

function pricing(sym) {
  const e = D.e, pr = e.pricing || {}, im = e.implied || {};
  if (!pr.available && !im.available) return '';
  const imx = im.available ? { pct: im.implied_move_pct, expiry: im.expiry } : null;
  return html`<section class="section" aria-labelledby="ep-h"><div class="section-head"><h2 class="t-h2" id="ep-h">Event pricing</h2>${ask(sym, 'Ask Milo about the event pricing', `Are ${sym}'s options priced rich or cheap for the coming report?`)}</div>
    ${im.available ? html`<p><b>±${num(im.implied_move_pct)}% through the ${shortDate(im.expiry)} expiry.</b> The ${num(im.strike, 0)} straddle costs $${num(im.straddle_cost)}, ${im.dte} days out, at ${num(im.atm_iv_pct, 1)}% IV. It covers ordinary trading as well as the report.</p>` : html`<p>${clean(im.reason || '')}</p>`}
    ${isNum(pr.event_day_avg_pct) ? html`<p><b>±${num(pr.event_day_avg_pct)}% on report days.</b> The average move on the session after the last ${(e.surprise || {}).quarters || 8} reports. History, not a price.</p>` : ''}
    ${historyRatio(pr, imx, (e.surprise || {}).quarters)}
    ${pr.stale ? html`<p class="stale">${clean(pr.stale_note || '')}</p>` : ''}<p class="asof">${clean(pr.caveat || '')}</p></section>`;
}

function revisions(sym) {
  const r = D.e.revisions || {};
  if (!r.available) return '';
  return html`<section class="section" aria-labelledby="rv-h"><h2 class="t-h2" id="rv-h">Estimate revisions</h2>
    <p>${clean(r.note || '')} ${r.analysts_up_30d} analysts raised and ${r.analysts_down_30d} cut in the last 30 days.</p>
    <div class="chart-slot" data-chart="rev"></div>
    <div class="tscroll"><table class="t"><thead><tr><th>Period</th><th>Estimate</th><th>30 days</th><th>90 days</th><th>Up, 30 days</th><th>Down, 30 days</th></tr></thead>
      <tbody>${r.rows.map((x) => html`<tr><td>${x.label}</td><td>${num(x.current)}</td><td>${signed(x.chg_30d_pct)}</td><td>${signed(x.chg_90d_pct)}</td><td>${x.analysts_up_30d}</td><td>${x.analysts_down_30d}</td></tr>`)}</tbody></table></div>
    <p class="asof">${clean(r.caveat || '')}</p></section>`;
}

function surprises() {
  const s = D.e.surprise || {};
  if (!s.available) return '';
  return html`<section class="section" aria-labelledby="sh-h"><h2 class="t-h2" id="sh-h">Surprise history</h2>
    ${kv([['Beat rate', `${num(s.beat_rate_pct, 0)}% (${s.beat_count} of ${s.quarters})`], ['Average surprise', signed(s.avg_surprise_pct, 1)], ['Average move after', `±${num(s.avg_abs_move_pct)}%`], ['Average move on a beat', signed(s.avg_move_on_beat_pct)]], 4)}
    <div class="chart-slot" data-chart="surp"></div>
    <div class="tscroll"><table class="t"><thead><tr><th>Report</th><th>Estimate</th><th>Reported</th><th>Surprise</th><th>Next day</th></tr></thead>
      <tbody>${s.rows.map((x) => html`<tr><td>${fullDate(x.date)}</td><td>${num(x.eps_estimate)}</td><td>${num(x.eps_reported)}</td><td class="${x.surprise_pct >= 0 ? 'up' : 'down'}">${signed(x.surprise_pct, 1)}</td><td>${signed(x.next_day_move_pct)}</td></tr>`)}</tbody></table></div>
    <ul class="plain">${(s.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul></section>`;
}

function growth() {
  const g = D.e.growth || {};
  const row = (x) => html`<tr><td>${shortDate(x.period)} ${String(x.period).slice(0, 4)}</td><td>${compact(x.revenue)}</td><td>${signed(x.revenue_yoy_pct)}</td><td>${compact(x.net_income)}</td><td>${signed(x.net_income_yoy_pct)}</td><td>${num(x.gross_margin_pct, 1)}%</td><td>${num(x.operating_margin_pct, 1)}%</td></tr>`;
  const head = html`<thead><tr><th>Period</th><th>Revenue</th><th>Growth</th><th>Net income</th><th>Growth</th><th>Gross margin</th><th>Operating margin</th></tr></thead>`;
  if (!(g.quarterly || []).length && !(g.annual || []).length) return '';
  return html`<section class="section" aria-labelledby="gr-h"><h2 class="t-h2" id="gr-h">Financial growth</h2>
    <div class="chart-slot" data-chart="growth"></div>
    <h3>Quarters</h3><div class="tscroll"><table class="t">${head}<tbody>${(g.quarterly || []).map(row)}</tbody></table></div>
    <h3>Fiscal years</h3><div class="tscroll"><table class="t">${head}<tbody>${(g.annual || []).map(row)}</tbody></table></div>
    ${(g.forward || []).length ? html`<h3>What analysts expect</h3><div class="tscroll"><table class="t"><thead><tr><th>Period</th><th>EPS</th><th>EPS growth</th><th>Revenue</th><th>Revenue growth</th><th>Analysts</th></tr></thead><tbody>${g.forward.map((f) => html`<tr><td>${f.label}</td><td>${num(f.eps_avg)}</td><td>${signed(f.eps_growth_pct, 1)}</td><td>${f.revenue_label || compact(f.revenue_avg)}</td><td>${signed(f.revenue_growth_pct, 1)}</td><td>${f.eps_analysts || ''}</td></tr>`)}</tbody></table></div>` : ''}
    <ul class="plain">${(g.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul></section>`;
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
  const rv = (e.revisions || {}).rows || [], sr = ((e.surprise || {}).rows || []).slice().reverse(), q = ((e.growth || {}).quarterly || []).slice().reverse();
  return {
    rev: (w) => signedBars(rv.map((r) => ({ x: r.label, v: r.chg_90d_pct, label: `${r.label}: ${signed(r.chg_90d_pct)} over 90 days` })), { w, h: 150, label: 'Estimate change over 90 days by period', fmt: (v) => signed(v), xfmt: (x) => x.replace('Current ', '').replace('Next ', 'next ') }),
    surp: (w) => signedBars(sr.map((r) => ({ x: shortDate(r.date), v: r.surprise_pct, label: `${fullDate(r.date)}: ${signed(r.surprise_pct, 1)} surprise, next day ${signed(r.next_day_move_pct)}` })), { w, h: 150, label: 'Earnings surprise by quarter', fmt: (v) => signed(v, 1) }),
    growth: (w) => signedBars(q.map((r) => ({ x: shortDate(r.period), v: r.revenue_yoy_pct, label: `${fullDate(r.period)}: revenue ${signed(r.revenue_yoy_pct)} year on year` })), { w, h: 150, label: 'Quarterly revenue growth, year on year', fmt: (v) => signed(v, 1) }),
  };
}

function paint() {
  if (!live) return;
  const sym = D.sym;
  const y = window.scrollY;
  let body;
  if (D.err) body = failed('The earnings data', D.err, { retry: 'earnings' });
  else if (!D.e) body = skeleton('lines', 6, 'Loading the earnings data');
  else if (D.e.not_applicable) body = empty(`No earnings for ${sym}`, clean(D.e.reason || 'Funds and indices do not report earnings.'));
  else body = html`${hero(sym)}${brief(sym)}${pricing(sym)}${revisions(sym)}${surprises()}${growth()}${analysts(sym)}<p class="asof disclaimer">${clean(D.e.data_caveat || '')} ${clean(D.e.disclaimer || '')}</p>`;
  draw(mainEl, html`${header(sym, D, 'earnings')}${tabs(sym, 'earnings', { fund: isFund(D) })}${body}`);
  if (D.e && !D.e.not_applicable) mountCharts(mainEl, makers());
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

async function loadBrief() {
  D.brief = 'loading'; paint();
  try { D.brief = await api.get(`/api/earnings/${encodeURIComponent(D.sym)}/brief`, { ttl: 3600000, timeout: 90000 }); }
  catch (e) { D.brief = { error: e }; }
  paint();
  const b = mainEl.querySelector('#br-h'); if (b) b.setAttribute('tabindex', '-1');
}

export async function render(main, route) {
  live = true; mainEl = main;
  const sym = route.symbol;
  D = { sym };
  store.pushRecent(sym);
  document.title = `${sym} Earnings, Optic`;
  provideContext(() => ({ view: 'earnings', ticker: sym, quote: D.quote, earnings: D.e }));
  paint();
  main.addEventListener('click', (e) => { if (e.target.closest('[data-v2-brief]')) loadBrief(); });
  core(sym).then((c) => { if (D.sym !== sym) return; D.quote = c.quote; D.session = c.session; D.quoteError = c.quoteError; paint(); });
  try { D.e = await api.get(`/api/earnings/${encodeURIComponent(sym)}`, { ttl: 600000, timeout: 60000 }); }
  catch (e) { D.err = e; }
  if (D.sym === sym) paint();
}
export function dispose() { live = false; }
export const retry = { earnings: (m, r) => { api.invalidate('/api/earnings'); render(m, r); }, brief: () => loadBrief() };
void ago;
