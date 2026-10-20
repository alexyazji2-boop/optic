// Dossier, Financials (rebuilt 2026-10-19, owner's brief item 15). A summary first (the latest fiscal
// year's key figures and what the statements say), then a jump list of the sections, the statements as
// four chart cards and a table whose first column stays put, segments, the earnings record, ownership,
// short interest, corporate actions, filings and congressional disclosures. Statements come with the shared
// /api/ticker snapshot (company); the rest from /api/extras, /api/congress and
// /api/segments. Funds have no Financials page, as in the classic app.
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, signed, dir, money, compact, clean, capFirst, fullDate, shortDate, isNum } from '../core/format.js';
import { lineChart, mountCharts } from '../ui/chart.js';
import { signedBars, hbars } from '../ui/bars.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { core, header, tabs, isFund } from './dossier-frame.js';
import { kindOf, can, kindWord } from '../core/instrument.js';

let D = {}, live = true, mainEl = null;
// Fiscal years or quarters, for the statements and the segments: a display choice kept on this device.
const PERIOD_KEY = 'optic.v2.financials.period.v1';
const readPeriod = () => { try { return localStorage.getItem(PERIOD_KEY) === 'quarter' ? 'quarter' : 'year'; } catch (e) { return 'year'; } };
let period = readPeriod();

/** A period end as the company's fiscal period, as app/analytics/fundamentals.py fiscal_label writes it:
 * "Q1 FY26" for Microsoft's quarter to 30 September 2025, "Q3 2026" for a calendar-year filer, "FY26" or
 * "2026" for a year. `fyEnd` is any fiscal year end the company has reported. */
export function fiscalLabel(periodEnd, fyEnd, annual = false) {
  const day = (s) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || '')); return m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) : null; };
  const d = day(periodEnd), fe = day(fyEnd);
  if (d === null || fe === null) return null;
  const F = new Date(fe), DAY = 86400000;
  const cal = (F.getUTCMonth() === 11 && F.getUTCDate() >= 24) || (F.getUTCMonth() === 0 && F.getUTCDate() <= 7);
  const at = (y) => { const last = new Date(Date.UTC(y, F.getUTCMonth() + 1, 0)).getUTCDate(); return Date.UTC(y, F.getUTCMonth(), Math.min(F.getUTCDate(), last)); };
  let end = at(new Date(d).getUTCFullYear());
  if (end < d - 10 * DAY) end = at(new Date(end).getUTCFullYear() + 1);
  const E = new Date(end);
  const year = cal && E.getUTCMonth() === 0 ? E.getUTCFullYear() - 1 : E.getUTCFullYear();
  const yy = String(year % 100).padStart(2, '0');
  if (annual) return cal ? String(year) : `FY${yy}`;
  const q = 4 - Math.round((end - d) / DAY / 91.31);
  if (q < 1 || q > 4) return null;
  return cal ? `Q${q} ${year}` : `Q${q} FY${yy}`;
}
const seg = (val, opts) => html`<div class="seg fin-period" role="group" aria-label="Fiscal years or quarters">${opts.map(([v, l]) => html`<button type="button" data-fin-period="${v}" aria-pressed="${val === v}">${l}</button>`)}</div>`;
const kv = (rows, n = 3) => html`<dl class="kv" style="--kv:${n}">${rows.filter(Boolean).map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
const ask = (sym, label, q) => miloButton(label, { ask: q, context: `${sym} Dossier, Financials`, symbol: sym });
const pct = (v, dp = 1) => (isNum(v) ? `${num(v, dp)}%` : 'n/a');
// a split's ratio in words: 1.5 is 3 for 2, 0.1 a 1-for-10 reverse split (num(ratio, 0) printed "2 for 1" and "0 for 1")
export function splitWords(r) {
  if (!isNum(r) || Number(r) <= 0) return 'ratio not reported';
  const x = Number(r);
  if (x < 1) { const inv = 1 / x; for (let d = 1; d <= 10; d += 1) { const n = inv * d; if (Math.abs(n - Math.round(n)) < 0.01) return `${d} for ${Math.round(n)}, a reverse split`; } return `${num(x, 3)} for 1, a reverse split`; }
  for (let d = 1; d <= 10; d += 1) { const n = x * d; if (Math.abs(n - Math.round(n)) < 0.01) return `${Math.round(n)} for ${d}`; }
  return `${num(x, 3)} for 1`;
}
const usd = (v) => (isNum(v) ? `${v < 0 ? '−' : ''}$${compact(Math.abs(v))}` : 'n/a');

function readings() {
  const c = (D.t || {}).company || {}, f = c.financials || {}, m = f.margins || {}, g = f.growth || {}, eh = c.earnings_history || {}, si = c.short_interest || {}, ow = c.ownership || {};
  const items = [];
  if (f.available) items.push(['Margins', `Gross ${pct(m.gross_pct)}, operating ${pct(m.operating_pct)}, net ${pct(m.net_pct)}.`]);
  if (f.available) items.push(['Growth', `Revenue ${signed(g.revenue_yoy_pct)} and net income ${signed(g.net_income_yoy_pct)} in the last fiscal year${isNum(g.net_income_yoy_pct) && isNum(g.revenue_yoy_pct) && g.net_income_yoy_pct - g.revenue_yoy_pct > 2 ? ': net income outpaced revenue, so the net margin widened' : isNum(g.net_income_yoy_pct) && isNum(g.revenue_yoy_pct) && g.revenue_yoy_pct - g.net_income_yoy_pct > 2 ? ': revenue outpaced net income, so the net margin narrowed' : ''}.`]);
  if (eh.available && eh.sample_size) items.push(['Against estimates', `Beat in ${eh.beat_count} of ${eh.sample_size} quarters${eh.in_line_count ? `, in line in ${eh.in_line_count}` : ''}, by ${signed(eh.avg_surprise_pct, 1)} on average.`]);
  // only what was reported: a missing share of float is not 0%, and no squeeze reading is drawn without it
  if (si.available) { const parts = [isNum(si.percent_of_float) ? `${pct(si.percent_of_float * 100)} of float` : 'Share of float not reported', isNum(si.days_to_cover) ? `${num(si.days_to_cover, 1)} days to cover` : '', isNum(si.change_vs_prior_pct) ? `${signed(si.change_vs_prior_pct, 1)} since the last report` : ''].filter(Boolean); items.push(['Short interest', `${parts.join(', ')}.${isNum(si.percent_of_float) && si.squeeze_potential ? ` Squeeze potential ${si.squeeze_potential}.` : ''}`]); }
  if (ow.available) { const i6 = ow.insider_6m || {}; items.push(['Insiders', `${capFirst(ow.insider_signal || '')} over six months: ${num(i6.purchase_count, 0)} purchases and ${num(i6.sale_count, 0)} sales, net ${compact(i6.net_shares)} shares.`]); }
  if (!items.length && !f.available) return '';
  const a = f.annual || {}, per = f.annual_periods || [], bs = f.balance_sheet || {};
  const yr = (f.annual_fiscal || [])[0] || (per[0] ? String(per[0]).slice(0, 4) : '');
  const latest = (k) => (a[k] || [])[0];
  const cells = f.available ? [
    ['Revenue', usd(latest('revenue')), `${signed(g.revenue_yoy_pct)} on the year before`],
    ['Net income', usd(latest('net_income')), `${signed(g.net_income_yoy_pct)} on the year before`],
    ['Free cash flow', usd(latest('free_cash_flow')), isNum(latest('free_cash_flow')) && latest('revenue') ? `${num((latest('free_cash_flow') / latest('revenue')) * 100, 1)}% of revenue` : ''],
    ['Operating margin', pct(m.operating_pct), `Gross ${pct(m.gross_pct)}, net ${pct(m.net_pct)}`],
    [isNum(bs.net_cash) && bs.net_cash < 0 ? 'Net debt' : 'Net cash', usd(isNum(bs.net_cash) ? Math.abs(bs.net_cash) : null), `Cash ${usd(bs.cash)}, debt ${usd(bs.total_debt)}`],
  ] : [];
  return html`<section class="section fin-sum" id="fin-summary" aria-labelledby="fr-h"><h2 class="t-h2" id="fr-h">Summary${yr ? `, ${/^FY/.test(yr) ? yr : `fiscal ${yr}`}` : ''}</h2>${per[0] ? html`<p class="section-sub">The fiscal year to ${fullDate(per[0])}.</p>` : ''}
    ${cells.length ? html`<div class="readings fin-figs" style="--rn:${cells.length}">${cells.map(([k, v, d]) => html`<div class="rd"><span class="k">${k}</span><span class="v">${v}</span><span class="d">${d}</span></div>`)}</div>` : ''}
    ${items.length ? html`<h3>What the figures say</h3><dl class="reads-dl">${items.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>` : ''}</section>`;
}

// Where each section is, for the jump list: only the sections this company has.
function sectionsHere() {
  const c = (D.t || {}).company || {};
  return [
    ['fin-summary', 'Summary', true],
    ['fin-statements', 'Statements', (c.financials || {}).available],
    ['fin-segments', 'Segments', D.sg && D.sg.available],
    ['fin-earnings', 'Earnings record', (c.earnings_history || {}).available],
    ['fin-ownership', 'Ownership', (c.ownership || {}).available],
    ['fin-short', 'Short interest', (c.short_interest || {}).available],
    ['fin-actions', 'Corporate actions', !!D.x],
    ['fin-filings', 'SEC filings', ((D.t || {}).filings || {}).available],
    ['fin-congress', 'Congress', D.cg && D.cg.available],
  ].filter((x) => x[2]);
}
function jumpList() {
  const xs = sectionsHere();
  if (xs.length < 3) return '';
  return html`<nav class="fin-nav" aria-label="Sections of Financials">${xs.map(([id, l]) => html`<button type="button" class="chip" data-fin-jump="${id}">${l}</button>`)}
    <label class="tabsel fin-jumpsel"><span class="tabsel-k">Jump to</span><select data-fin-jumpsel aria-label="Jump to a section of Financials"><option value="">Choose a section</option>${xs.map(([id, l]) => html`<option value="${id}">${l}</option>`)}</select></label></nav>`;
}

// The figures for the period chosen: fiscal years from the annual statements, or quarters from the quarterly
// income statement (Yahoo carries no quarterly cash flow, so free cash flow is a yearly figure only).
export function periodView(f, which) {
  const q = which === 'quarter' && (f.quarterly_periods || []).length;
  const per = q ? f.quarterly_periods : f.annual_periods || [];
  const names = q ? f.quarterly_fiscal || [] : f.annual_fiscal || [];
  return { q: !!q, per, vals: q ? f.quarterly || {} : f.annual || {},
    label: (i) => names[i] || (q ? `${shortDate(per[i])} ${String(per[i]).slice(0, 4)}` : String(per[i]).slice(0, 4)),
    // a quarter against the same quarter a year before (four columns back); a year against the one before
    back: q ? 4 : 1, against: q ? 'on the same quarter a year before' : 'on the year before' };
}
function statements(sym) {
  const f = ((D.t || {}).company || {}).financials || {};
  if (!f.available) return '';
  const V = periodView(f, period), a = V.vals, per = V.per, bs = f.balance_sheet || {}, m = f.margins || {};
  const rows = [['Revenue', 'revenue'], ['Gross profit', 'gross_profit'], ['Operating income', 'operating_income'], ['EBITDA', 'ebitda'], ['Net income', 'net_income'], ['Free cash flow', 'free_cash_flow'], ['Diluted EPS (GAAP)', 'diluted_eps']];
  const card = (k, label, slot, fmt) => {
    const v = a[k] || [], cur = v[0], prev = v[V.back];
    if (!v.length && V.q) return html`<div class="fin-card"><p class="t-label">${label}</p><p class="fin-card-v t-muted">Yearly only</p><p class="t-muted">The quarterly statements Optic reads carry no ${label.toLowerCase()}.</p></div>`;
    const ch = isNum(cur) && isNum(prev) && prev > 0 ? ((cur - prev) / Math.abs(prev)) * 100 : null;
    return html`<div class="fin-card"><p class="t-label">${label}, ${V.label(0)}</p><p class="fin-card-v">${fmt(cur)}${isNum(ch) ? html` <span class="${dir(ch)}">${signed(ch, 1)}</span>` : ''}</p>${isNum(ch) ? html`<p class="t-muted fin-card-d">${V.against}</p>` : ''}<div class="chart-slot" data-chart="${slot}"></div></div>`;
  };
  return html`<section class="section" id="fin-statements" aria-labelledby="st-h"><div class="section-head"><div><h2 class="t-h2" id="st-h">Statements</h2><p class="section-sub">${clean(f.source || "The company's statements as Yahoo Finance carries them.")} ${V.q ? 'The latest quarters, each against the same quarter a year before.' : 'The latest fiscal years, each against the year before.'}</p></div>${ask(sym, 'Ask Milo about the financials', `What do ${sym}'s financial statements say about the business's health?`)}</div>
    ${(f.quarterly_periods || []).length ? seg(period, [['year', 'Fiscal years'], ['quarter', 'Quarters']]) : ''}
    <div class="chart-grid fin-cards">${card('revenue', 'Revenue', 'rev', usd)}${card('net_income', 'Net income', 'ni', usd)}${card('free_cash_flow', 'Free cash flow', 'fcf', usd)}${card('diluted_eps', 'Diluted EPS', 'eps', (x) => num(x))}</div>
    <div class="tscroll"><table class="t fin-table"><thead><tr><th scope="col">${V.q ? 'Quarter' : 'Fiscal year'}</th>${per.map((p, i) => html`<th scope="col">${V.label(i)}<small class="t-muted fin-end">to ${shortDate(p)} ${String(p).slice(2, 4)}</small></th>`)}</tr></thead>
      <tbody>${rows.filter(([, k]) => (a[k] || []).some(isNum)).map(([l, k]) => html`<tr><th scope="row">${l}</th>${per.map((p, i) => html`<td>${k === 'diluted_eps' ? num((a[k] || [])[i]) : usd((a[k] || [])[i])}</td>`)}</tr>`)}</tbody></table></div>
    <p class="asof">${clean(f.eps_basis || '')} Earnings uses analysts' basis for EPS, usually adjusted, so the two can differ.</p>
    <h3>Balance sheet and margins</h3>${kv([['Cash', usd(bs.cash)], ['Debt', usd(bs.total_debt)], ['Net cash or debt', usd(bs.net_cash)], ['Debt to equity', num(bs.debt_to_equity, 2)], ['Gross margin', pct(m.gross_pct)], ['Operating margin', pct(m.operating_pct)], ['EBITDA margin', pct(m.ebitda_pct)], ['Net margin', pct(m.net_pct)]], 4)}
    <ul class="plain">${(f.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul></section>`;
}
function statementCharts() {
  const f = ((D.t || {}).company || {}).financials || {};
  if (!f.available) return {};
  const V = periodView(f, period), a = V.vals, n = V.per.length;
  const idx = [...Array(n).keys()].reverse();     // oldest first, left to right
  const by = V.q ? 'by quarter' : 'by fiscal year';
  const bars = (k, label, fmt) => ((a[k] || []).some(isNum) ? (w) => signedBars(idx.map((i) => ({ x: V.label(i), v: (a[k] || [])[i], label: `${V.label(i)}: ${fmt((a[k] || [])[i])}` })), { w, h: 120, label, fmt }) : null);
  const out = { rev: bars('revenue', `Revenue ${by}`, usd), ni: bars('net_income', `Net income ${by}`, usd), fcf: bars('free_cash_flow', `Free cash flow ${by}`, usd), eps: bars('diluted_eps', `Diluted EPS ${by}`, (v) => num(v)) };
  Object.keys(out).forEach((k) => { if (!out[k]) delete out[k]; });
  return out;
}

function record(which) {
  const c = (D.t || {}).company || {}, eh = which === 'earnings' ? c.earnings_history || {} : {}, si = which === 'short' ? c.short_interest || {} : {};
  return html`${eh.available ? html`<section class="section" id="fin-earnings" aria-labelledby="er-h"><h2 class="t-h2" id="er-h">Earnings track record</h2>
      <div class="tscroll"><table class="t"><thead><tr><th>Report</th><th>Estimate</th><th>Reported</th><th>Surprise</th></tr></thead><tbody>${(eh.quarters || []).map((q) => html`<tr><td>${fullDate(q.date)}</td><td>${num(q.eps_estimate)}</td><td>${num(q.eps_reported)}</td><td class="${dir(q.surprise_pct)}">${signed(q.surprise_pct, 1)}</td></tr>`)}</tbody></table></div>
      ${(eh.upcoming || [])[0] ? html`<p>Next report ${fullDate(eh.upcoming[0].date)}, estimate ${num(eh.upcoming[0].eps_estimate)}.</p>` : ''}<ul class="plain">${(eh.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul></section>` : ''}
    ${si.available ? html`<section class="section" id="fin-short" aria-labelledby="si-h"><h2 class="t-h2" id="si-h">Short interest</h2>
      ${kv([['Share of float', isNum(si.percent_of_float) ? pct(si.percent_of_float * 100, 2) : 'Not reported'], ['Days to cover', isNum(si.days_to_cover) ? num(si.days_to_cover, 1) : 'Not reported'], ['Since the last report', isNum(si.change_vs_prior_pct) ? signed(si.change_vs_prior_pct, 1) : 'Not reported'], ['Shares short', isNum(si.shares_short) ? compact(si.shares_short) : 'Not reported'], ['Prior', isNum(si.shares_short_prior) ? compact(si.shares_short_prior) : 'Not reported'], ['Float', isNum(si.float_shares) ? compact(si.float_shares) : 'Not reported']], 3)}
      <p>${isNum(si.percent_of_float) && si.squeeze_potential ? `Squeeze potential: ${si.squeeze_potential}. ` : 'No squeeze reading without the share of float. '}${(si.notes || []).map(clean).join(' ')}</p><p class="asof">Settlement ${fullDate(si.settlement_date)}. ${clean(si.caveat || '')}</p></section>` : ''}`;
}

function ownership(sym) {
  const ow = ((D.t || {}).company || {}).ownership || {};
  if (!ow.available) return '';
  const i6 = ow.insider_6m || {};
  return html`<section class="section" id="fin-ownership" aria-labelledby="ow-h"><div class="section-head"><h2 class="t-h2" id="ow-h">Insider and institutional activity</h2>${ask(sym, 'Ask Milo about insiders', `What does recent insider and institutional activity in ${sym} suggest?`)}</div>
    ${kv([['Insider signal, 6 months', capFirst(ow.insider_signal || '')], ['Insider net shares', compact(i6.net_shares)], ['Purchases', `${num(i6.purchase_count, 0)} (${compact(i6.purchase_shares)} shares)`], ['Sales', `${num(i6.sale_count, 0)} (${compact(i6.sale_shares)} shares)`], ['Held by institutions', isNum(ow.institutional_pct_held) ? pct(ow.institutional_pct_held * 100) : 'Not reported'], ['Held by insiders', isNum(ow.insider_pct_held) ? pct(ow.insider_pct_held * 100, 2) : 'Not reported']], 3)}
    <p>${ow.holders_adding} of the ${ow.holders_counted || (ow.top_holders || []).length} largest holders raised their stake and ${ow.holders_trimming} cut it by more than ${num(ow.holder_change_threshold_pct || 2, 0)}% at their last 13F filing; the rest changed by less. ${(ow.top_holders || []).length > 6 ? `The bars show the ${6} largest.` : ''}</p>
    ${raw(hbars((ow.top_holders || []).filter((h) => isNum(h.pct_held)).slice(0, 6).map((h) => ({ label: h.holder, v: h.pct_held * 100, note: `${compact(h.shares)} shares, ${isNum(h.pct_change) ? `${signed(h.pct_change * 100, 1)} at` : 'change not reported, filed'} ${fullDate(h.date_reported)}` }))))}
    <details class="more-inline"><summary>Recent insider transactions</summary><div class="tscroll"><table class="t"><thead><tr><th>Date</th><th>Insider</th><th>Role</th><th>Action</th><th>Shares</th><th>Value</th></tr></thead><tbody>${(ow.recent_transactions || []).slice(0, 20).map((t) => html`<tr><td>${fullDate(t.date)}</td><td>${t.insider}</td><td>${t.position || ''}</td><td>${capFirst(t.action || '')}</td><td>${compact(t.shares)}</td><td>${usd(t.value)}</td></tr>`)}</tbody></table></div>${(ow.recent_transactions || []).length > 20 ? html`<p class="asof">The latest 20 of ${(ow.recent_transactions || []).length} filings from the last two years. The Chart marks every purchase and sale among them, and the <a class="textlink" href="#/insiders">Insiders page</a> reads filings straight from EDGAR.</p>` : ''}</details>
    <ul class="plain">${(ow.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul><p class="asof">${clean(ow.caveat || '')}</p></section>`;
}

function filings() {
  const fl = (D.t || {}).filings || {};
  if (!fl.available) return '';
  return html`<section class="section" id="fin-filings" aria-labelledby="fl-h"><h2 class="t-h2" id="fl-h">Recent SEC filings</h2>
    <ul class="plain">${(fl.filings || []).slice(0, 10).map((f) => html`<li><a href="${f.url}" target="_blank" rel="noopener">${f.form}</a> ${clean(f.what)}, filed ${fullDate(f.filed)}</li>`)}</ul>
    <p class="asof">${clean(fl.method || '')}</p></section>`;
}

function extras() {
  const x = D.x;
  if (x === undefined) return html`<section class="section">${skeleton('lines', 3, 'Loading corporate actions')}</section>`;
  if (!x) return '';
  const a = x.actions || {}, sv = x.short_volume || {}, rl = x.relative || {};
  return html`<section class="section" id="fin-actions" aria-labelledby="ca-h"><h2 class="t-h2" id="ca-h">Corporate actions and flow</h2>
    ${a.pays_dividend ? html`<h3>Dividends</h3>${kv([['Payments on record', a.payment_count], ['Years of growth', a.growth_streak_years], ['Last cut', a.last_cut_year || 'None on record'], ['Latest', (a.dividends || []).length ? `$${num(a.dividends[a.dividends.length - 1].amount, 3)} on ${fullDate(a.dividends[a.dividends.length - 1].date)}` : 'n/a']], 4)}
      ${(a.annual || []).length ? html`<div class="tscroll"><table class="t"><thead><tr><th>Year</th><th>Total a share</th></tr></thead><tbody>${a.annual.slice(-8).map((y) => html`<tr><td>${y.year}</td><td>$${num(y.total, 3)}</td></tr>`)}</tbody></table></div>` : ''}` : html`<p>No dividend on record.</p>`}
    ${(a.splits || []).length ? html`<h3>Splits</h3><ul class="plain">${a.splits.map((s) => html`<li>${fullDate(s.date)}: ${splitWords(s.ratio)}</li>`)}</ul>` : ''}
    ${a.note ? html`<p class="asof">${clean(a.note)}</p>` : ''}
    ${(sv.rows || []).length ? html`<h3>Off-exchange short volume</h3>${kv([['Latest session', pct(sv.latest_pct)], [`Average, ${sv.days} sessions`, pct(sv.average_pct)]], 2)}<div class="chart-slot" data-chart="sv"></div><p class="asof">${clean(sv.caveat || '')}</p>` : ''}
    ${rl.excess ? html`<h3>Against ${rl.benchmark || 'the index'}</h3>${kv(Object.entries(rl.excess).map(([k, v]) => [k.replace('d', ' sessions'), signed(v)]), 5)}<p class="asof">${clean(rl.note || '')}</p>` : ''}
  </section>`;
}
function extraCharts() {
  const sv = ((D.x || {}).short_volume || {}).rows || [];
  const pts = sv.slice().reverse().map((r) => ({ d: r.date, c: r.short_pct }));
  return pts.length > 2 ? { sv: (w) => lineChart(pts, { w, h: 150, dp: 1, label: 'Off-exchange short volume, share of the day', pad: { t: 12, r: 46, b: 24, l: 0 } }) } : {};
}

function congress() {
  const c = D.cg;
  if (c === undefined) return '';
  if (!c || !c.available) return '';
  return html`<section class="section" id="fin-congress" aria-labelledby="cg-h"><h2 class="t-h2" id="cg-h">Congressional disclosures</h2>
    <p>${c.count} trades by ${c.members} members of the House: ${c.buys} buys and ${c.sells} sales, worth ${money(c.amount_low, 0)} to ${money(c.amount_high, 0)} in the bands filed. Filed a median ${c.lag_median} days after the trade.</p>
    <div class="tscroll"><table class="t"><thead><tr><th>Traded</th><th>Member</th><th>Action</th><th>Amount</th><th>Filed after</th></tr></thead>
      <tbody>${(c.trades || []).slice(0, 15).map((t) => html`<tr><td>${t.traded_iso ? fullDate(t.traded_iso) : t.traded}</td><td>${t.member} <small class="t-muted">${t.district || ''}</small></td><td>${capFirst(t.transaction || '')}</td><td>${money(t.amount_low, 0)} to ${money(t.amount_high, 0)}</td><td>${isNum(t.disclosure_lag_days) ? `${t.disclosure_lag_days} days` : ''}</td></tr>`)}</tbody></table></div>
    <p class="asof">${clean(c.caveat || '')} Source: House Clerk disclosures${c.complete ? '' : ', partly read'}.</p></section>`;
}

function segments() {
  const s = D.sg;
  if (s === undefined) return html`<section class="section">${skeleton('lines', 3, 'Reading segment filings')}</section>`;
  if (!s || !s.available) return s && s.reason ? html`<section class="section"><h2 class="t-h2">Segments and geography</h2><p>${clean(s.reason)}</p></section>` : '';
  const fy = (((D.t || {}).company || {}).financials || {}).fiscal_year_end;
  const years = period === 'year' && (s.tables || []).some((t) => ((t.annual || {}).ends || []).length);
  const table = (t) => {
    // newest first, as the statements read (the filings parse oldest first)
    const ends = years ? (t.annual.ends || []).slice().reverse() : (s.quarters || []).slice().reverse();
    const rows = years ? (t.annual.rows || []).map((r) => ({ member: r.member, values: r.values.slice().reverse(), derived: [] }))
      : t.rows.map((r) => ({ member: r.member, values: r.values.slice().reverse(), derived: (r.derived || []).slice().reverse() }));
    const keep = ends.map((_, i) => rows.some((r) => isNum(r.values[i])));
    const derivedCol = ends.map((_, i) => rows.some((r) => r.derived[i]));
    const name = (e) => (fy ? fiscalLabel(e, fy, years) : null) || `${shortDate(e)} ${String(e).slice(2, 4)}`;
    return html`<h3>${t.metric_label}, ${t.axis_label.toLowerCase()}</h3><div class="tscroll"><table class="t fin-table"><thead><tr><th scope="col">${t.axis_label}</th>${ends.map((e, i) => (keep[i] ? html`<th scope="col">${name(e)}<small class="t-muted fin-end">${derivedCol[i] ? 'year less three quarters' : `to ${shortDate(e)} ${String(e).slice(2, 4)}`}</small></th>` : ''))}</tr></thead>
      <tbody>${rows.map((r) => html`<tr><th scope="row">${clean(r.member)}</th>${r.values.map((v, i) => (keep[i] ? html`<td>${usd(v)}</td>` : ''))}</tr>`)}</tbody></table></div>`;
  };
  return html`<section class="section" id="fin-segments" aria-labelledby="sg-h"><h2 class="t-h2" id="sg-h">Segments and geography</h2>
    ${seg(years ? 'year' : 'quarter', [['year', 'Fiscal years'], ['quarter', 'Quarters']])}
    ${(s.tables || []).map(table)}
    ${!years && s.q4_derived ? html`<p class="asof">A 10-K reports the year, not its fourth quarter, so a fourth quarter here is the year less the three quarters filed before it, and its column says so.</p>` : ''}
    <p class="asof">Based on ${s.filings_read} of the ${s.filings_listed} most recent filings${s.filings_unread ? '; the rest are still being read' : ''}. ${clean(s.method || '')} ${clean(s.blind_spot || '')}</p></section>`;
}

function paint() {
  if (!live) return;
  const sym = D.sym, y = window.scrollY;
  let body;
  if (D.na) body = notApplicable(sym, D.na);
  else if (D.tErr) body = failed('The financial statements', D.tErr, { retry: 'ticker' });
  else if (!D.t) body = skeleton('lines', 6, 'Loading the statements');
  else body = html`${readings()}${jumpList()}${statements(sym)}${segments()}${record('earnings')}${ownership(sym)}${record('short')}${extras()}${filings()}${congress()}`;
  draw(mainEl, html`${header(sym, D, 'financials')}${tabs(sym, 'financials', { fund: isFund(D) })}<div class="fin">${body}</div>`);
  mountCharts(mainEl, Object.assign({}, statementCharts(), extraCharts()));
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

function notApplicable(sym, kind) {
  const name = (D.quote || {}).name || sym;
  return html`<section class="section na" aria-labelledby="na-h"><h2 class="t-h2" id="na-h">Financials do not apply to ${sym}</h2>
    <p>${name} is ${kind === 'fund' ? 'a fund: it holds other companies\' shares and has no income statement, balance sheet or cash flow of its own' : kind === 'index' ? 'an index: a calculated level, with no business behind it' : `a ${kindWord(kind)}, with no company statements behind it`}.</p>
    <p>${kind === 'fund' ? 'Its long-term record, drawdowns and its holdings\' valuation are on Investing; what it is and how it trades are on Overview.' : 'Its price history and setups are on Overview and Chart.'}</p>
    <div class="cluster">${kind === 'fund' ? html`<a class="btn" href="#/${sym}/investing">Open Investing</a>` : ''}<a class="btn" href="#/${sym}">Open Overview</a></div></section>`;
}

async function loadSegments(sym, round = 0) {
  try {
    const s = await api.get(`/api/segments/${encodeURIComponent(sym)}`, { ttl: 0, force: round > 0, timeout: 60000 });
    if (D.sym !== sym) return;
    D.sg = s; paint();
    // the server reads a few filings per call; ask again while it is still reading
    if (s && s.filings_unread > 0 && s.fetched_now > 0 && round < 5 && live) setTimeout(() => loadSegments(sym, round + 1), 400);
  } catch (e) { if (D.sym === sym && round === 0) { D.sg = null; paint(); } }
}

export async function render(main, route) {
  live = true; mainEl = main;
  const sym = route.symbol, enc = encodeURIComponent(sym);
  D = { sym };
  store.pushRecent(sym);
  document.title = `${sym} Financials, Optic`;
  provideContext(() => ({ view: 'financials', ticker: sym, quote: D.quote, company: (D.t || {}).company, filings: (D.t || {}).filings, extras: D.x }));
  if (!main.dataset.finWired) {
    main.dataset.finWired = '1';
    const jump = (id) => { const sec = document.getElementById(id); if (!sec) return; sec.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' }); const h = sec.querySelector('h2'); if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); } };
    main.addEventListener('click', (e) => {
      const b = e.target.closest('[data-fin-jump]'); if (b) { jump(b.dataset.finJump); return; }
      const p = e.target.closest('[data-fin-period]');
      if (p) { period = p.dataset.finPeriod; try { localStorage.setItem(PERIOD_KEY, period); } catch (err) { /* private mode */ } const at = p.closest('section'); const id = at && at.id; paint(); const again = id && document.querySelector(`#${id} [data-fin-period="${period}"]`); if (again) again.focus(); }
    });
    main.addEventListener('change', (e) => { const sl = e.target.closest('[data-fin-jumpsel]'); if (sl && sl.value) { jump(sl.value); sl.value = ''; } });
  }
  paint();
  const c = await core(sym).catch(() => ({}));
  if (D.sym !== sym) return;
  Object.assign(D, { quote: c.quote, session: c.session, quoteError: c.quoteError });
  // A direct link to a fund's or an index's Financials says why the view does not apply, and where the
  // useful figures are, rather than bouncing to Overview with no word (owner, 2026-10-19).
  const kind = kindOf(sym, D);
  if (!can(kind).financials) { D.na = kind; paint(); return; }
  paint();
  const step = (p, ok, bad) => p.then((d) => { if (D.sym === sym) ok(d); }, (e) => { if (D.sym === sym) bad(e); }).finally(() => { if (D.sym === sym) paint(); });
  step(api.get(`/api/ticker/${enc}?max_expiries=4&macro=true`, { ttl: 120000, timeout: 60000 }), (d) => { D.t = d; }, (e) => { D.tErr = e; });
  step(api.get(`/api/extras/${enc}?benchmark=SPY`, { ttl: 600000, timeout: 30000 }), (d) => { D.x = d; }, () => { D.x = null; });
  step(api.get(`/api/congress?ticker=${enc}&limit=40`, { ttl: 600000, timeout: 30000 }), (d) => { D.cg = d; }, () => { D.cg = null; });
  loadSegments(sym);
}
export function dispose() { live = false; }
export const retry = { ticker: (m, r) => render(m, r) };
void empty;
