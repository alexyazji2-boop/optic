// Dossier, Financials (rebuilt 2026-10-19, owner's brief item 15). A summary first (the latest fiscal
// year's key figures and what the statements say), then a jump list of the sections, the statements as
// four chart cards and a table whose first column stays put, segments, the earnings record, ownership,
// short interest, corporate actions, filings and congressional disclosures. Statements come with the shared
// /api/ticker snapshot (company); the rest from /api/extras, /api/congress and
// /api/segments. Funds have no Financials page, as in the classic app.
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, signed, dir, money, compact, clean, capFirst, fullDate, shortDate, isNum, plural } from '../core/format.js';
import { lineChart, mountCharts } from '../ui/chart.js';
import { signedBars, hbars, groupedBars, periodLines, bridgeBars, stackedBars } from '../ui/bars.js';
import * as FV from '../core/finviz.js';
import { closeCell, CLOSE_NOTE } from '../core/congress.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { core, header, tabs, isFund, livePrice } from './dossier-frame.js';
import { kindOf, can, kindWord } from '../core/instrument.js';
import { icon } from '../ui/icons.js';
let lp = null;   // the header's price refresh (dossier-frame livePrice), stopped in dispose()

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
// Statement figures in the currency the company files in (TSM's are New Taiwan dollars: "$3.81T" was its
// revenue in TWD, 2026-10-20); set from the snapshot's financial_currency on every paint
let usd = FV.moneyIn('USD'), ccy = 'USD';
const CCY_WORDS = { USD: 'US dollars', TWD: 'New Taiwan dollars', EUR: 'euros', JPY: 'yen', GBP: 'pounds', CNY: 'yuan', HKD: 'Hong Kong dollars', KRW: 'won', INR: 'rupees', CAD: 'Canadian dollars', CHF: 'Swiss francs', DKK: 'Danish kroner', BRL: 'reais', AUD: 'Australian dollars', SEK: 'Swedish kronor', ILS: 'shekels', MXN: 'pesos', ZAR: 'rand' };
const ccyWords = () => CCY_WORDS[ccy] || ccy;
// a key for a figure's series: the swatch carries the colour, the name carries the meaning
const key = (items) => html`<p class="legend-line fv-key">${items.map(([cls, name, hollow]) => html`<span><i class="sw ${cls}${hollow ? ' hollow' : ''}"></i>${name}</span>`)}</p>`;

// The six-month insider reading in words: open-market purchases and sales only (awards and exercises are not
// decisions to trade), and what it leaves out.
export function insiderLine(ow) {
  const i6 = ow.insider_6m || {}, open = i6.basis === 'open_market';
  if (open && !i6.purchase_count && !i6.sale_count) return `No open-market purchases or sales by insiders in six months${i6.other_count ? `; ${i6.other_count} awards, grants and exercises, which are not trades` : ''}.`;
  const dirn = (i6.net_shares || 0) > 0 ? 'Net buying' : (i6.net_shares || 0) < 0 ? 'Net selling' : 'Even';
  return `${dirn} on the open market over six months: ${num(i6.purchase_count, 0)} ${i6.purchase_count === 1 ? 'purchase' : 'purchases'} and ${num(i6.sale_count, 0)} ${i6.sale_count === 1 ? 'sale' : 'sales'}, net ${signed(i6.net_shares, 0, '')} shares.${open && i6.other_count ? ` ${i6.other_count} awards, grants and exercises not counted.` : ''}${open ? '' : ' As Yahoo Finance tallies them, awards included.'}`;
}
function readings() {
  const c = (D.t || {}).company || {}, f = c.financials || {}, m = f.margins || {}, g = f.growth || {}, eh = c.earnings_history || {}, si = c.short_interest || {}, ow = c.ownership || {};
  const items = [];
  if (f.available) items.push(['Margins', `Gross ${pct(m.gross_pct)}, operating ${pct(m.operating_pct)}, net ${pct(m.net_pct)}.`]);
  if (f.available) items.push(['Growth', `Revenue ${signed(g.revenue_yoy_pct)} and net income ${signed(g.net_income_yoy_pct)} in the last fiscal year${isNum(g.net_income_yoy_pct) && isNum(g.revenue_yoy_pct) && g.net_income_yoy_pct - g.revenue_yoy_pct > 2 ? ': net income outpaced revenue, so the net margin widened' : isNum(g.net_income_yoy_pct) && isNum(g.revenue_yoy_pct) && g.revenue_yoy_pct - g.net_income_yoy_pct > 2 ? ': revenue outpaced net income, so the net margin narrowed' : ''}.`]);
  if (eh.available && eh.sample_size) items.push(['Against estimates', `Beat in ${eh.beat_count} of ${eh.sample_size} quarters${eh.in_line_count ? `, in line in ${eh.in_line_count}` : ''}, by ${signed(eh.avg_surprise_pct, 1)} on average.`]);
  // only what was reported: a missing share of float is not 0%, and no squeeze reading is drawn without it
  if (si.available) { const parts = [isNum(si.percent_of_float) ? `${pct(si.percent_of_float * 100)} of float` : 'Share of float not reported', isNum(si.days_to_cover) ? `${num(si.days_to_cover, 1)} days to cover` : '', isNum(si.change_vs_prior_pct) ? `${signed(si.change_vs_prior_pct, 1)} since the last report` : ''].filter(Boolean); items.push(['Short interest', `${parts.join(', ')}.${isNum(si.percent_of_float) && si.squeeze_potential ? ` Squeeze potential ${si.squeeze_potential}.` : ''}`]); }
  if (ow.available) items.push(['Insiders', insiderLine(ow)]);
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
    ${/* folded on a phone, so the period control and the charts come sooner (pitch audit, 2026-10-22); the figures above are the finding */ ''}
    ${items.length ? html`<details class="fin-say" ${wideScreen() ? 'open' : ''}><summary><h3>What the figures say</h3>${icon('chev')}</summary><dl class="reads-dl">${items.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl></details>` : ''}</section>`;
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
const wideScreen = () => { try { return matchMedia('(min-width: 641px)').matches; } catch (e) { return true; } };
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
// The comparison a period is read against: a year against the year before; a quarter against the same quarter a
// year before when five quarters are on hand, otherwise the quarter before, and the sentence says which.
function compare(V) {
  if (!V.q) return { back: 1, against: '' };
  return V.per.length > 4 ? { back: 4, against: 'the same quarter a year before' } : { back: 1, against: 'the quarter before' };
}
function statements(sym) {
  const f = ((D.t || {}).company || {}).financials || {};
  if (!f.available) return '';
  const V = periodView(f, period), a = V.vals, per = V.per, bs = f.balance_sheet || {}, m = f.margins || {};
  const Y = periodView(f, 'year'), ya = Y.vals, ylab = Y.per.map((_, i) => Y.label(i));
  const labels = per.map((_, i) => V.label(i)), C = compare(V);
  const opm = FV.marginSeries(a.operating_income, a.revenue), gpm = FV.marginSeries(a.gross_profit, a.revenue), npm = FV.marginSeries(a.net_income, a.revenue);
  const qoq = V.q && C.back === 4 && per.length > 1 ? FV.growthLine('Against the quarter before, revenue', a.revenue, labels, 1, '', usd).replace('Against the quarter before, revenue was', 'Against the quarter before, revenue was') : '';
  const bh = f.balance_history || {}, hasBal = (bh.cash || []).some(isNum) && (bh.total_debt || []).some(isNum);
  const hasCf = (ya.operating_cash_flow || []).some(isNum) || (ya.free_cash_flow || []).some(isNum);
  const latestBridge = FV.bridges((ya.operating_cash_flow || [])[0], (ya.capital_expenditure || [])[0], (ya.free_cash_flow || [])[0]);
  const shares = a.diluted_shares || [];
  const unit = V.q ? 'Quarters' : 'Fiscal years';
  const rows = [['Revenue', 'revenue'], ['Gross profit', 'gross_profit'], ['Operating income', 'operating_income'], ['EBITDA', 'ebitda'], ['Net income', 'net_income'], ['Operating cash flow', 'operating_cash_flow'], ['Capital expenditure', 'capital_expenditure'], ['Free cash flow', 'free_cash_flow'], ['Diluted EPS (GAAP)', 'diluted_eps'], ['Diluted shares', 'diluted_shares']];
  const cell = (k, v) => (k === 'diluted_eps' ? num(v) : k === 'diluted_shares' ? compact(v) : usd(v));
  return html`<section class="section" id="fin-statements" aria-labelledby="st-h"><div class="section-head"><div><h2 class="t-h2" id="st-h">Statements</h2><p class="section-sub">${clean(f.source || "The company's statements as Yahoo Finance carries them.")} In ${ccyWords()}${ccy !== 'USD' ? ', as the company files; the share price is in US dollars' : ''}.</p></div>
      ${(f.quarterly_periods || []).length ? seg(period, [['year', 'Fiscal years'], ['quarter', 'Quarters']]) : ''}</div>
    <div class="fv-grid">
      <figure class="fv"><figcaption><h3>Revenue and profit</h3><p class="fv-take">${FV.profitLine(a.revenue, a.net_income, labels, C.back, C.against, usd)}</p>${qoq ? html`<p class="fv-take fv-sub">${qoq}</p>` : ''}
        ${key([['s1', 'Revenue'], ['s2', 'Operating income'], ['s3', 'Net income']])}<p class="fv-unit">${unit}, ${ccyWords()}</p></figcaption><div class="chart-slot" data-chart="profit"></div></figure>
      <figure class="fv"><figcaption><h3>Margins</h3><p class="fv-take">${FV.marginLine('Operating margin', opm, labels, C.back)}</p>
        ${key([['s1', 'Gross margin'], ['s2', 'Operating margin'], ['s3', 'Net margin']])}<p class="fv-unit">${unit}, percent of revenue</p></figcaption><div class="chart-slot" data-chart="margins"></div></figure>
      ${hasCf ? html`<figure class="fv"><figcaption><h3>Cash flow</h3><p class="fv-take">${FV.cashFlowLine(ya.operating_cash_flow, ya.capital_expenditure, ya.free_cash_flow, ylab, usd)}</p>
        ${key([['s1', 'Operating cash flow'], ['s2', 'Capital spending, shown as cash out'], ['s3', 'Free cash flow']])}<p class="fv-unit">Fiscal years, ${ccyWords()}${V.q ? '. The statements Optic reads carry no quarterly cash flow' : ''}</p></figcaption>
        <div class="chart-slot" data-chart="cashflow"></div>${latestBridge ? html`<p class="t-label fv-bridge-h">${ylab[0]}: from operating cash flow to free cash flow</p><div class="chart-slot" data-chart="bridge"></div>` : ''}</figure>` : ''}
      ${hasBal ? html`<figure class="fv"><figcaption><h3>Cash and debt</h3><p class="fv-take">${FV.netCashLine(bh.cash, bh.total_debt, ylab, usd)}</p>
        ${key([['s1', 'Cash and equivalents'], ['s2', 'Total debt']])}<p class="fv-unit">At each fiscal year end, ${ccyWords()}</p></figcaption><div class="chart-slot" data-chart="balance"></div></figure>` : ''}
      ${(a.diluted_eps || []).some(isNum) ? html`<figure class="fv fv-wide"><figcaption><h3>Per share</h3><p class="fv-take">${FV.perShareLine(a.diluted_eps, shares, labels, C.back, C.against)}</p>
        <p class="fv-unit">${unit}. Diluted EPS (GAAP) in ${ccyWords()} a share; the share count is the weighted diluted average each EPS divides by.</p></figcaption>
        <div class="fv-pair"><div><p class="t-label">Diluted EPS</p><div class="chart-slot" data-chart="eps"></div></div>${shares.some(isNum) ? html`<div><p class="t-label">Diluted shares</p><div class="chart-slot" data-chart="shares"></div></div>` : ''}</div></figure>` : ''}
    </div>
    <details class="more-inline fv-data"><summary>View data</summary>
      <div class="tscroll"><table class="t fin-table"><thead><tr><th scope="col">${V.q ? 'Quarter' : 'Fiscal year'}</th>${per.map((pe, i) => html`<th scope="col">${V.label(i)}<small class="t-muted fin-end">to ${shortDate(pe)} ${String(pe).slice(2, 4)}</small></th>`)}</tr></thead>
        <tbody>${rows.filter(([, k]) => (a[k] || []).some(isNum)).map(([l, k]) => html`<tr><th scope="row">${l}</th>${per.map((pe, i) => html`<td>${cell(k, (a[k] || [])[i])}</td>`)}</tr>`)}
          ${!V.q && hasBal ? html`<tr><th scope="row">Cash and equivalents</th>${per.map((pe, i) => html`<td>${usd((bh.cash || [])[i])}</td>`)}</tr><tr><th scope="row">Total debt</th>${per.map((pe, i) => html`<td>${usd((bh.total_debt || [])[i])}</td>`)}</tr>` : ''}</tbody></table></div>
      <p class="asof">${clean(f.eps_basis || '')} Earnings uses analysts' basis for EPS, usually adjusted, so the two can differ. Margins are each line over revenue in the same period. ${V.q ? 'Cash flow and the balance sheet are yearly only here.' : ''}</p>
      <h3>Balance sheet and margins, latest</h3>${kv([['Cash', usd(bs.cash)], ['Debt', usd(bs.total_debt)], [isNum(bs.net_cash) && bs.net_cash < 0 ? 'Net debt' : 'Net cash', usd(isNum(bs.net_cash) ? Math.abs(bs.net_cash) : null)], ['Debt to equity', num(bs.debt_to_equity, 2)], ['Gross margin', pct(m.gross_pct)], ['Operating margin', pct(m.operating_pct)], ['EBITDA margin', pct(m.ebitda_pct)], ['Net margin', pct(m.net_pct)]], 4)}
      <ul class="plain">${(f.notes || []).map((n) => html`<li>${clean(ccy === 'USD' ? n : n.replace(/\$/g, `${ccy} `))}</li>`)}</ul></details></section>`;
}
function statementCharts() {
  const f = ((D.t || {}).company || {}).financials || {};
  if (!f.available) return {};
  const V = periodView(f, period), a = V.vals, n = V.per.length;
  const Y = periodView(f, 'year'), ya = Y.vals, yn = Y.per.length;
  const old = (len) => [...Array(len).keys()].reverse();     // oldest first, left to right
  const G = old(n).map((i) => ({ x: V.label(i) })), GY = old(yn).map((i) => ({ x: Y.label(i) }));
  const col = (vals, len = n) => old(len).map((i) => (vals || [])[i]);
  const out = {};
  out.profit = (w) => groupedBars(G, [{ name: 'Revenue', cls: 's1', values: col(a.revenue) }, { name: 'Operating income', cls: 's2', values: col(a.operating_income) }, { name: 'Net income', cls: 's3', values: col(a.net_income) }], { w, h: 220, label: `Revenue, operating income and net income, ${V.q ? 'by quarter' : 'by fiscal year'}`, fmt: usd });
  out.margins = (w) => periodLines(G, [{ name: 'Gross margin', cls: 's1', values: col(FV.marginSeries(a.gross_profit, a.revenue)) }, { name: 'Operating margin', cls: 's2', values: col(FV.marginSeries(a.operating_income, a.revenue)) }, { name: 'Net margin', cls: 's3', values: col(FV.marginSeries(a.net_income, a.revenue)) }], { w, h: 200, label: 'Gross, operating and net margin, percent of revenue', fmt: (v) => `${num(v, 1)}%`, axisFmt: (v) => `${num(v, 0)}%` });
  if ((ya.operating_cash_flow || []).some(isNum) || (ya.free_cash_flow || []).some(isNum)) {
    out.cashflow = (w) => groupedBars(GY, [{ name: 'Operating cash flow', cls: 's1', values: col(ya.operating_cash_flow, yn) }, { name: 'Capital spending', cls: 's2', values: col(ya.capital_expenditure, yn) }, { name: 'Free cash flow', cls: 's3', values: col(ya.free_cash_flow, yn) }], { w, h: 220, label: 'Operating cash flow, capital spending and free cash flow by fiscal year', fmt: usd });
    const o = (ya.operating_cash_flow || [])[0], c = (ya.capital_expenditure || [])[0], fc = (ya.free_cash_flow || [])[0];
    if (FV.bridges(o, c, fc)) out.bridge = (w) => bridgeBars([{ x: 'Operating cash flow', v: o, kind: 'total', cls: 's1' }, { x: 'Capital spending', v: c, kind: 'step' }, { x: 'Free cash flow', v: fc, kind: 'total', cls: 's3' }], { w: Math.min(w, 460), h: 180, fmt: usd, label: `${Y.label(0)}: operating cash flow less capital spending is free cash flow` });
  }
  const bh = f.balance_history || {};
  if ((bh.cash || []).some(isNum)) out.balance = (w) => groupedBars(GY, [{ name: 'Cash and equivalents', cls: 's1', values: col(bh.cash, yn) }, { name: 'Total debt', cls: 's2', values: col(bh.total_debt, yn) }], { w, h: 200, label: 'Cash and debt at each fiscal year end', fmt: usd, note: (i) => { const k = yn - 1 - i, nc = FV.netCash((bh.cash || [])[k], (bh.total_debt || [])[k]); return nc ? `${nc.net < 0 ? 'Net debt' : 'Net cash'} ${usd(Math.abs(nc.net))}` : ''; } });
  if ((a.diluted_eps || []).some(isNum)) out.eps = (w) => groupedBars(G, [{ name: 'Diluted EPS', cls: 's1', values: col(a.diluted_eps) }], { w, h: 170, label: `Diluted EPS ${V.q ? 'by quarter' : 'by fiscal year'}`, fmt: (v) => num(v, 2), axisFmt: (v) => num(v, Math.abs(v) < 1 && v !== 0 ? 2 : 1) });
  if ((a.diluted_shares || []).some(isNum)) out.shares = (w) => periodLines(G, [{ name: 'Diluted shares', cls: 's2', values: col(a.diluted_shares) }], { w, h: 170, zero: false, label: `Diluted share count ${V.q ? 'by quarter' : 'by fiscal year'}`, fmt: (v) => compact(v), axisFmt: (v) => compact(v) });
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
    <p>${insiderLine(ow)}</p>
    ${kv([['Open-market purchases, 6 months', `${num(i6.purchase_count, 0)} (${compact(i6.purchase_shares)} shares)`], ['Open-market sales, 6 months', `${num(i6.sale_count, 0)} (${compact(i6.sale_shares)} shares)`], ['Net shares', signed(i6.net_shares, 0, '')], ['Held by institutions', isNum(ow.institutional_pct_held) ? pct(ow.institutional_pct_held * 100) : 'Not reported'], ['Held by insiders', isNum(ow.insider_pct_held) ? pct(ow.insider_pct_held * 100, 2) : 'Not reported']], 3)}
    <p>${ow.holders_adding} of the ${ow.holders_counted || (ow.top_holders || []).length} largest holders raised their stake and ${ow.holders_trimming} cut it by more than ${num(ow.holder_change_threshold_pct || 2, 0)}% at their last 13F filing; the rest changed by less. ${(ow.top_holders || []).length > 6 ? `The bars show the ${6} largest.` : ''}</p>
    ${raw(hbars((ow.top_holders || []).filter((h) => isNum(h.pct_held)).slice(0, 6).map((h) => ({ label: h.holder, v: h.pct_held * 100, note: `${compact(h.shares)} shares, ${isNum(h.pct_change) ? `${signed(h.pct_change * 100, 1)} at` : 'change not reported, filed'} ${fullDate(h.date_reported)}` }))))}
    <details class="more-inline"><summary>Recent insider transactions</summary><p class="asof">Each row's date is when the trade happened; this feed does not carry when it was filed. The <a class="textlink" href="#/insiders?symbol=${sym}&view=insiders">Insiders page</a> lists ${sym}'s Form 4s with their filing times and links.</p><div class="tscroll"><table class="t"><thead><tr><th>Traded</th><th>Insider</th><th>Role</th><th>Action</th><th>Shares</th><th>Value</th></tr></thead><tbody>${(ow.recent_transactions || []).slice(0, 20).map((t) => html`<tr><td>${fullDate(t.date)}</td><td>${t.insider}</td><td>${t.position || ''}</td><td>${capFirst(t.action || '')}</td><td>${compact(t.shares)}</td><td>${usd(t.value)}</td></tr>`)}</tbody></table></div>${(ow.recent_transactions || []).length > 20 ? html`<p class="asof">The latest 20 of ${(ow.recent_transactions || []).length} filings from the last two years. The Chart marks every purchase and sale among them, and the <a class="textlink" href="#/insiders">Insiders page</a> reads filings straight from EDGAR.</p>` : ''}</details>
    <ul class="plain">${(ow.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul>
    <p class="asof">${clean(ow.insider_method || '')}${(ow.yahoo_tally_6m || {}).acquired_count ? ` Yahoo Finance's own tally, every acquisition and disposal counted: ${num(ow.yahoo_tally_6m.acquired_count, 0)} acquired and ${num(ow.yahoo_tally_6m.disposed_count, 0)} disposed.` : ''} ${clean(ow.caveat || '')}</p></section>`;
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
  return pts.length > 2 ? { sv: (w) => lineChart(pts, { measure: 'points', msUnit: ' pts', w, h: 150, dp: 1, label: 'Off-exchange short volume, share of the day', pad: { t: 12, r: 46, b: 24, l: 0 } }) } : {};
}

function congress() {
  const c = D.cg;
  if (c === undefined) return '';
  if (!c || !c.available) return '';
  return html`<section class="section" id="fin-congress" aria-labelledby="cg-h"><h2 class="t-h2" id="cg-h">Congressional disclosures</h2>
    <p>${c.count} trades by ${c.members} members of the House: ${c.buys} buys and ${c.sells} sales, worth ${money(c.amount_low, 0)} to ${money(c.amount_high, 0)} in the bands filed. Filed a median ${plural(c.lag_median, 'day')} after the trade.</p>
    <div class="tscroll"><table class="t"><thead><tr><th>Traded</th><th>Member</th><th>Action</th><th>Amount</th><th>Close that day</th><th>Filed after</th></tr></thead>
      <tbody>${(c.trades || []).slice(0, 15).map((t) => html`<tr><td>${t.traded_iso ? fullDate(t.traded_iso) : t.traded}</td><td>${t.member} <small class="t-muted">${t.district || ''}</small></td><td>${capFirst(t.transaction || '')}</td><td>${money(t.amount_low, 0)} to ${money(t.amount_high, 0)}</td><td>${closeCell(t)}</td><td>${isNum(t.disclosure_lag_days) ? `${plural(t.disclosure_lag_days, 'day')}` : ''}</td></tr>`)}</tbody></table></div>
    <p class="asof">${clean(c.caveat || '')} ${CLOSE_NOTE} Source: House Clerk disclosures${c.complete ? '' : ', partly read'}.</p></section>`;
}

// The reported total a segment table should add up to, on the same period end (within 15 days): revenue or
// operating income from the statements; null for anything else, and then no reconciliation is claimed.
function reportedTotal(metric, end, years) {
  const f = ((D.t || {}).company || {}).financials || {};
  const per = years ? f.annual_periods || [] : f.quarterly_periods || [], vals = (years ? f.annual || {} : f.quarterly || {})[metric];
  if (!vals || !end) return null;
  const day = (x) => Date.parse(String(x).slice(0, 10));
  const k = per.findIndex((p) => Math.abs(day(p) - day(end)) <= 15 * 86400000);
  return k >= 0 && isNum(vals[k]) ? vals[k] : null;
}
const SEG_CLS = ['s1', 's2', 's3'];
function segments() {
  const s = D.sg;
  if (s === undefined) return html`<section class="section">${skeleton('lines', 3, 'Reading segment filings')}</section>`;
  if (!s || !s.available) return s && s.reason ? html`<section class="section"><h2 class="t-h2">Segments and geography</h2><p>${clean(s.reason)}</p></section>` : '';
  const fy = (((D.t || {}).company || {}).financials || {}).fiscal_year_end;
  const years = period === 'year' && (s.tables || []).some((t) => ((t.annual || {}).ends || []).length);
  const name = (e) => (fy ? fiscalLabel(e, fy, years) : null) || `${shortDate(e)} ${String(e).slice(2, 4)}`;
  const susd = FV.moneyIn('USD');   // segment figures come from the 10-Q and 10-K filings, in US dollars
  const view = (t) => {
    const ends = years ? (t.annual.ends || []) : (s.quarters || []);   // oldest first, as the filings parse
    const rows = years ? (t.annual.rows || []) : (t.rows || []);
    const latest = ends.map((_, i) => rows.some((r) => isNum(r.values[i]))).lastIndexOf(true);
    const total = latest >= 0 ? reportedTotal(t.metric, ends[latest], years) : null;
    const comp = latest >= 0 ? FV.composition(rows.map((r) => clean(r.member)), rows.map((r) => r.values[latest]), total) : null;
    return { ends, rows, latest, comp };
  };
  const table = (t) => {
    // newest first, as the statements read
    const ends = years ? (t.annual.ends || []).slice().reverse() : (s.quarters || []).slice().reverse();
    const rows = years ? (t.annual.rows || []).map((r) => ({ member: r.member, values: r.values.slice().reverse(), derived: [] }))
      : t.rows.map((r) => ({ member: r.member, values: r.values.slice().reverse(), derived: (r.derived || []).slice().reverse() }));
    const keep = ends.map((_, i) => rows.some((r) => isNum(r.values[i])));
    const derivedCol = ends.map((_, i) => rows.some((r) => r.derived[i]));
    return html`<div class="tscroll"><table class="t fin-table"><thead><tr><th scope="col">${t.axis_label}</th>${ends.map((e, i) => (keep[i] ? html`<th scope="col">${name(e)}<small class="t-muted fin-end">${derivedCol[i] ? 'year less three quarters' : `to ${shortDate(e)} ${String(e).slice(2, 4)}`}</small></th>` : ''))}</tr></thead>
      <tbody>${rows.map((r) => html`<tr><th scope="row">${clean(r.member)}</th>${r.values.map((v, i) => (keep[i] ? html`<td>${susd(v)}</td>` : ''))}</tr>`)}</tbody></table></div>`;
  };
  const figure = (t, k) => {
    const v = view(t), c = v.comp;
    if (!c || !c.rows.length) return html`<figure class="fv"><figcaption><h3>${t.metric_label}, ${t.axis_label.toLowerCase()}</h3><p class="t-muted">No figures for the latest period in the filings read.</p></figcaption></figure>`;
    const label = name(v.ends[v.latest]), base = c.reconciles ? c.total : c.sum;
    const pos = c.rows.filter((r) => r.v >= 0), neg = c.rows.filter((r) => r.v < 0);
    return html`<figure class="fv"><figcaption><h3>${t.metric_label}, ${t.axis_label.toLowerCase()}</h3><p class="fv-take">${FV.compositionLine(c, t.metric_label, label, susd)}</p>
        <p class="fv-unit">${label}, US dollars, as filed${c.dropped.length ? html`. ${c.dropped.join(', ')} is a total of other lines here, so it is left out rather than counted twice` : ''}</p></figcaption>
      ${raw(hbars(pos.map((r) => ({ label: r.label, v: r.v, text: c.canShare && base > 0 ? `${susd(r.v)}, ${num((r.v / base) * 100, 0)}%` : susd(r.v) })), { fmt: (x) => susd(x) }))}
      ${neg.length ? html`<p class="fv-unit">${neg.map((r) => `${r.label}: ${susd(r.v)}`).join('; ')}. Costs or income the filing does not assign to a segment.</p>` : ''}
      ${years && c.canShare && v.ends.length > 1 ? html`<p class="t-label fv-bridge-h">Over the fiscal years</p>${key([...c.rows.slice(0, 3).map((r, i) => [SEG_CLS[i], r.label]), ...(c.rows.length > 3 ? [['s0', 'Other']] : [])])}<div class="chart-slot" data-chart="segmix${k}"></div>` : ''}</figure>`;
  };
  return html`<section class="section" id="fin-segments" aria-labelledby="sg-h"><div class="section-head"><div><h2 class="t-h2" id="sg-h">Segments and geography</h2><p class="section-sub">Where the money comes from, as the company reports it in its filings.</p></div>
    ${seg(years ? 'year' : 'quarter', [['year', 'Fiscal years'], ['quarter', 'Quarters']])}</div>
    <div class="fv-grid">${(s.tables || []).map((t, k) => figure(t, k))}</div>
    <details class="more-inline fv-data"><summary>View data</summary>${(s.tables || []).map((t) => html`<h3>${t.metric_label}, ${t.axis_label.toLowerCase()}</h3>${table(t)}`)}
      ${!years && s.q4_derived ? html`<p class="asof">A 10-K reports the year, not its fourth quarter, so a fourth quarter here is the year less the three quarters filed before it, and its column says so.</p>` : ''}
      <p class="asof">Based on ${s.filings_read} of the ${s.filings_listed} most recent filings${s.filings_unread ? '; the rest are still being read' : ''}. ${clean(s.method || '')} ${clean(s.blind_spot || '')}</p></details></section>`;
}
// composition over the fiscal years: the largest parts of the latest year stacked, the rest folded into Other, the
// aggregate line (if any) left out of every year; for parts at or above zero only
function segmentCharts() {
  const s = D.sg; if (!s || !s.available || period !== 'year') return {};
  const fy = (((D.t || {}).company || {}).financials || {}).fiscal_year_end;
  const susd = FV.moneyIn('USD'), out = {};
  (s.tables || []).forEach((t, k) => {
    const ends = (t.annual || {}).ends || [], rows = (t.annual || {}).rows || [];
    if (ends.length < 2) return;
    const latest = ends.map((_, i) => rows.some((r) => isNum(r.values[i]))).lastIndexOf(true); if (latest < 0) return;
    const c = FV.composition(rows.map((r) => clean(r.member)), rows.map((r) => r.values[latest]), reportedTotal(t.metric, ends[latest], true));
    if (!c.canShare) return;
    const use = rows.filter((r) => !c.dropped.includes(clean(r.member)));
    if (use.some((r) => r.values.some((x) => isNum(x) && x < 0))) return;
    const order = c.rows.map((r) => r.label), top = order.slice(0, 3), rest = order.slice(3);
    const vals = (m) => (use.find((r) => clean(r.member) === m) || { values: [] }).values;
    const parts = top.map((m, i) => ({ name: m, cls: SEG_CLS[i], values: ends.map((_, e) => vals(m)[e]) }));
    if (rest.length) parts.push({ name: 'Other', cls: 's0', values: ends.map((_, e) => rest.reduce((a, m) => (isNum(vals(m)[e]) ? (a || 0) + vals(m)[e] : a), null)) });
    const G = ends.map((e) => ({ x: (fy ? fiscalLabel(e, fy, true) : null) || String(e).slice(0, 4) }));
    out[`segmix${k}`] = (w) => stackedBars(G, parts, { w, h: 200, fmt: susd, label: `${t.metric_label} ${t.axis_label.toLowerCase()} by fiscal year` });
  });
  return out;
}

function paint() {
  if (!live) return;
  const sym = D.sym, y = window.scrollY;
  ccy = (((D.t || {}).quote || {}).financial_currency || (D.quote || {}).financial_currency || 'USD').toUpperCase();
  usd = FV.moneyIn(ccy);
  let body;
  if (D.na) body = notApplicable(sym, D.na);
  else if (D.tErr) body = failed('The financial statements', D.tErr, { retry: 'ticker' });
  else if (!D.t) body = skeleton('lines', 6, 'Loading the statements');
  else body = html`${readings()}${jumpList()}${statements(sym)}${segments()}${record('earnings')}${ownership(sym)}${record('short')}${extras()}${filings()}${congress()}`;
  draw(mainEl, html`<div class="dstick">${header(sym, D, 'financials')}${tabs(sym, 'financials', { fund: isFund(D) })}</div><div class="fin">${body}</div>`);
  mountCharts(mainEl, Object.assign({}, statementCharts(), segmentCharts(), extraCharts()));
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
  if (lp) lp.stop();
  lp = livePrice(main, route.symbol, () => D, 'financials', undefined);
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
export function dispose() { if (lp) { lp.stop(); lp = null; } live = false; }
export const retry = { ticker: (m, r) => render(m, r) };
void empty;
