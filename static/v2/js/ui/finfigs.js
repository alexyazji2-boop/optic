// The figures Milo can put in an answer (owner's data-visualization brief, 2026-10-20, item 4). Milo names one with
// a tag, [[figure KIND SYMBOL]]; the terminal draws it here from Optic's own figures, through the same components and
// the same takeaway rules as Financials and Earnings. Nothing a model wrote is plotted: a number in the answer's
// text is the model's, a number in the figure is Optic's, and the figure says where it came from. When the data is
// missing or does not fit, the figure says so instead of drawing anything.
import { html } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, compact, shortDate, fullDate, isNum } from '../core/format.js';
import * as FV from '../core/finviz.js';
import { groupedBars, periodLines, hbars } from './bars.js';

export const KINDS = ['revenue', 'margins', 'cashflow', 'segments', 'eps', 'reactions'];
const cache = new Map();
const get = (url) => { if (!cache.has(url)) cache.set(url, api.get(url, { ttl: 300000, timeout: 60000 }).catch((e) => ({ __error: e }))); return cache.get(url); };
const key = (items) => html`<p class="legend-line fv-key">${items.map(([cls, name, hollow]) => html`<span><i class="sw ${cls}${hollow ? ' hollow' : ''}"></i>${name}</span>`)}</p>`;
const table = (cols, rows) => html`<details class="more-inline milo-fig-data"><summary>View data</summary><div class="tscroll"><table class="t"><thead><tr>${cols.map((c) => html`<th scope="col">${c}</th>`)}</tr></thead><tbody>${rows.map((r) => html`<tr>${r.map((v, i) => (i ? html`<td>${v}</td>` : html`<th scope="row">${v}</th>`))}</tr>`)}</tbody></table></div></details>`;
const missing = (why) => ({ missing: why });

function statements(t, sym) {
  const f = ((t || {}).company || {}).financials || {};
  if (!f.available || !(f.annual_periods || []).length) return null;
  const ccy = ((t.quote || {}).financial_currency || 'USD').toUpperCase(), m = FV.moneyIn(ccy);
  const labels = (f.annual_periods || []).map((p, i) => (f.annual_fiscal || [])[i] || String(p).slice(0, 4));
  const n = labels.length, old = [...Array(n).keys()].reverse(), col = (v) => old.map((i) => (v || [])[i]);
  return { f, m, ccy, labels, G: old.map((i) => ({ x: labels[i] })), col, a: f.annual || {}, source: `${sym}'s annual statements as Yahoo Finance carries them, in ${ccy === 'USD' ? 'US dollars' : ccy}` };
}

/** The figure for one tag: its title, takeaway, unit line, source, chart makers and data table; or why there is none. */
export async function build(kind, sym) {
  const s = encodeURIComponent(sym);
  if (['revenue', 'margins', 'cashflow'].includes(kind)) {
    const t = await get(`/api/ticker/${s}?max_expiries=4&macro=true`);
    if (t.__error) return missing(`Optic could not load ${sym}'s statements just now.`);
    const S = statements(t, sym); if (!S) return missing(`Optic has no statements for ${sym}; funds and indices do not report them.`);
    const { a, labels, G, col, m, source } = S;
    if (kind === 'revenue') return { title: `${sym}: revenue and profit by fiscal year`, take: FV.profitLine(a.revenue, a.net_income, labels, 1, '', m), unit: 'Fiscal years', source,
      keyHTML: key([['s1', 'Revenue'], ['s2', 'Operating income'], ['s3', 'Net income']]),
      chart: (w) => groupedBars(G, [{ name: 'Revenue', cls: 's1', values: col(a.revenue) }, { name: 'Operating income', cls: 's2', values: col(a.operating_income) }, { name: 'Net income', cls: 's3', values: col(a.net_income) }], { w, h: 200, fmt: m, label: `${sym} revenue, operating income and net income by fiscal year` }),
      table: table(['Fiscal year', 'Revenue', 'Operating income', 'Net income'], labels.map((l, i) => [l, m((a.revenue || [])[i]), m((a.operating_income || [])[i]), m((a.net_income || [])[i])])) };
    if (kind === 'margins') {
      const gm = FV.marginSeries(a.gross_profit, a.revenue), om = FV.marginSeries(a.operating_income, a.revenue), nm = FV.marginSeries(a.net_income, a.revenue);
      return { title: `${sym}: margins by fiscal year`, take: FV.marginLine('Operating margin', om, labels, 1), unit: 'Fiscal years, percent of revenue', source,
        keyHTML: key([['s1', 'Gross margin'], ['s2', 'Operating margin'], ['s3', 'Net margin']]),
        chart: (w) => periodLines(G, [{ name: 'Gross margin', cls: 's1', values: col(gm) }, { name: 'Operating margin', cls: 's2', values: col(om) }, { name: 'Net margin', cls: 's3', values: col(nm) }], { w, h: 190, fmt: (v) => `${num(v, 1)}%`, axisFmt: (v) => `${num(v, 0)}%`, label: `${sym} margins by fiscal year` }),
        table: table(['Fiscal year', 'Gross margin', 'Operating margin', 'Net margin'], labels.map((l, i) => [l, FV.pctText(gm[i]), FV.pctText(om[i]), FV.pctText(nm[i])])) };
    }
    if (!(a.free_cash_flow || []).some(isNum)) return missing(`The statements Optic reads carry no cash flow for ${sym}.`);
    return { title: `${sym}: cash flow by fiscal year`, take: FV.cashFlowLine(a.operating_cash_flow, a.capital_expenditure, a.free_cash_flow, labels, m), unit: 'Fiscal years; capital spending shown as cash out', source,
      keyHTML: key([['s1', 'Operating cash flow'], ['s2', 'Capital spending'], ['s3', 'Free cash flow']]),
      chart: (w) => groupedBars(G, [{ name: 'Operating cash flow', cls: 's1', values: col(a.operating_cash_flow) }, { name: 'Capital spending', cls: 's2', values: col(a.capital_expenditure) }, { name: 'Free cash flow', cls: 's3', values: col(a.free_cash_flow) }], { w, h: 200, fmt: m, label: `${sym} cash flow by fiscal year` }),
      table: table(['Fiscal year', 'Operating cash flow', 'Capital spending', 'Free cash flow'], labels.map((l, i) => [l, m((a.operating_cash_flow || [])[i]), m((a.capital_expenditure || [])[i]), m((a.free_cash_flow || [])[i])])) };
  }
  if (kind === 'segments') {
    const [sg, t] = await Promise.all([get(`/api/segments/${s}`), get(`/api/ticker/${s}?max_expiries=4&macro=true`)]);
    if (sg.__error || !sg.available) return missing(sg.reason || `Optic has no segment figures for ${sym} from its filings.`);
    const tb = (sg.tables || []).filter((x) => x.metric === 'revenue' && ((x.annual || {}).ends || []).length).sort((x) => (x.axis === 'product' ? -1 : 1))[0];
    if (!tb) return missing(`${sym}'s filings Optic has read carry no yearly revenue by segment.`);
    const ends = tb.annual.ends, rows = tb.annual.rows, k = ends.map((_, i) => rows.some((r) => isNum(r.values[i]))).lastIndexOf(true);
    const S = statements(t.__error ? {} : t, sym), fiscal = S ? S.labels[(S.f.annual_periods || []).findIndex((p) => Math.abs(Date.parse(p) - Date.parse(ends[k])) <= 15 * 864e5)] : null;
    const total = S ? ((S.a.revenue || [])[(S.f.annual_periods || []).findIndex((p) => Math.abs(Date.parse(p) - Date.parse(ends[k])) <= 15 * 864e5)]) : null;
    const c = FV.composition(rows.map((r) => r.member), rows.map((r) => r.values[k]), isNum(total) ? total : null);
    if (!c.rows.length) return missing(`No segment figures for ${sym}'s latest year.`);
    const label = fiscal || String(ends[k]).slice(0, 4), base = c.reconciles ? c.total : c.sum, usd = FV.moneyIn('USD');
    return { title: `${sym}: revenue ${tb.axis_label.toLowerCase()}, ${label}`, take: FV.compositionLine(c, 'Revenue', label, usd), unit: `${label}, US dollars, as filed${c.dropped.length ? `; ${c.dropped.join(', ')} totals other lines, so it is left out` : ''}`, source: `${sym}'s 10-K and 10-Q filings`,
      html: hbars(c.rows.filter((r) => r.v >= 0).map((r) => ({ label: r.label, v: r.v, text: c.canShare && base > 0 ? `${usd(r.v)}, ${num((r.v / base) * 100, 0)}%` : usd(r.v) })), { fmt: usd }),
      table: table(['Segment', 'Revenue'], c.rows.map((r) => [r.label, usd(r.v)])) };
  }
  if (kind === 'eps' || kind === 'reactions') {
    const e = await get(`/api/earnings/${s}`);
    if (e.__error || e.not_applicable) return missing(e.reason || `Optic has no earnings record for ${sym}.`);
    const R = (((e.surprise || {}).rows) || []).map((r) => Object.assign({}, r, FV.surprise(r.eps_estimate, r.eps_reported, r.surprise_pct))).reverse();
    if (!R.length) return missing(`Optic has no earnings history for ${sym}.`);
    const G = R.map((r) => ({ x: r.fiscal || shortDate(r.date), sub: FV.CLASS_WORD[r.cls] })), last = R[R.length - 1];
    if (kind === 'eps') {
      const b = R.filter((r) => r.cls === 'beat').length, mi = R.filter((r) => r.cls === 'miss').length;
      return { title: `${sym}: EPS against the estimate, last ${R.length} quarters`, take: `${b} beats, ${mi} misses and ${R.length - b - mi} without a clear result. The latest, ${last.fiscal || fullDate(last.date)}, ${last.cls === 'missing' ? 'had no estimate' : `${last.cls === 'in line' ? 'was in line' : `${last.cls === 'beat' ? 'beat' : 'missed'} by $${num(Math.abs(last.diff))} a share`}`}.`,
        unit: "Dollars a share, analysts' basis; the estimate hollow", source: 'Yahoo Finance estimates and reported EPS',
        keyHTML: key([['s0', "Analysts' estimate", true], ['s1', 'Reported EPS']]),
        chart: (w) => groupedBars(G, [{ name: "Analysts' estimate", cls: 's0', hollow: true, values: R.map((r) => r.eps_estimate) }, { name: 'Reported EPS', cls: 's1', values: R.map((r) => r.eps_reported) }], { w, h: 210, fmt: (v) => `$${num(v, 2)}`, axisFmt: (v) => `$${num(v, 2)}`, valueLabels: 'none', label: `${sym} EPS estimate against reported` }),
        table: table(['Quarter', 'Estimate', 'Reported', 'Result'], R.slice().reverse().map((r) => [r.fiscal || fullDate(r.date), num(r.eps_estimate), num(r.eps_reported), FV.CLASS_WORD[r.cls]])) };
    }
    const mv = R.filter((r) => isNum(r.next_day_move_pct)), up = mv.filter((r) => r.next_day_move_pct > 0).length;
    return { title: `${sym}: the share price after each report`, take: `The price rose after ${up} of ${mv.length} reports and fell after ${mv.length - up}. A beat is not a rise: the reaction depends on what investors expected and the rest of the report.`,
      unit: `The move in the session that traded on each report; ${mv.length} reports`, source: 'Yahoo Finance prices and report dates',
      chart: (w) => groupedBars(G, [{ name: 'Price move', cls: 's2', values: R.map((r) => r.next_day_move_pct) }], { w, h: 210, fmt: (v) => signed(v), axisFmt: (v) => `${num(v, 0)}%`, valueLabels: 'all', label: `${sym} share price move after each report` }),
      table: table(['Quarter', 'Result', 'Move'], R.slice().reverse().map((r) => [r.fiscal || fullDate(r.date), FV.CLASS_WORD[r.cls], isNum(r.next_day_move_pct) ? signed(r.next_day_move_pct) : 'Not reported'])) };
  }
  return missing('Optic draws no such figure.');
}
export { compact };
