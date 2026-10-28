// Dossier, Export: a printable research sheet for one company (roadmap stage 4, 2026-10-22). Opened from the
// Dossier's ⋯ menu at #/SYM/sheet, printed or saved as a PDF from the browser's own print dialog.
//
// One page where the facts fit and an intentional second page where they do not, never smaller type. Each
// figure is tagged as Reported (from the company's filings or the exchange), Estimate (analysts' consensus,
// option prices) or Optic (a rule or model applied to those). Missing data is said. Everything comes from the
// same free endpoints the Dossier reads; no model is called and no private holding is included.
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, money, compact, clean, fullDate, shortDate, isNum, plural } from '../core/format.js';
import { lineChart } from '../ui/chart.js';
import { skeleton, failed } from '../ui/states.js';
import { etStamp } from '../core/marketTime.js';

let D = {}, live = true, mainEl = null;
const TAG = { reported: 'Reported', estimate: 'Estimate', optic: 'Optic' };
const tag = (k) => html`<span class="sh-tag sh-${k}">${TAG[k]}</span>`;
const na = (v, f = (x) => x) => (isNum(v) ? f(v) : html`<span class="sh-na">Not reported</span>`);
const usd = (v) => (isNum(v) ? `$${compact(Math.abs(v))}` : null);
const one = (t) => firstSentences(clean(t || ''), 1);
// a full stop ends a sentence only before a space or the end: split at every one, "$217.94 ... at $187.99. The
// line ..." came back as "99." and the sheet printed "Trading above the 200-day average. 99 ." (investor audit, 2026-10-27)
export const firstSentences = (t, n = 2) => (String(t || '').match(/(?:[^.!?]|[.!?](?!\s|$))+[.!?]+(?:\s+|$)/g) || [String(t || '')]).slice(0, n).join('').trim();

/** The sheet's rows from the payloads, so what it says can be checked without a browser. */
export function sheetFacts(d) {
  const t = d.ticker || {}, q = { ...(t.quote || {}), ...(d.quote || {}) }, c = t.company || {}, f = c.financials || {};
  const a = f.annual || {}, per = f.annual_periods || [], g = f.growth || {}, m = f.margins || {}, bs = f.balance_sheet || {};
  const fvd = d.fairValue || {}, fv = fvd.fair_value || {}, st = fvd.stars || {}, e = d.earnings || {}, nr = e.next_report || {}, pr = e.pricing || {};
  const eh = c.earnings_history || {}, gex = t.gex || {}, im = e.implied || {}, te = t.technicals || {}, ma = te.moving_averages || {};
  const lt = (d.longterm || {}).holding || {}, rk = lt.risk || {}, dd = lt.drawdown || {};
  const levels = (te.support_resistance || []).slice().sort((x, y) => Math.abs(x.distance_pct) - Math.abs(y.distance_pct)).slice(0, 4);
  return {
    identity: { sym: d.sym, name: q.name || (d.session || {}).name || d.sym, price: q.price, change_pct: q.change_pct, currency: q.currency || 'USD',
      exchange: q.exchange || (d.session || {}).exchange || null, session: (((d.session || {}).session) || {}).label || null, observed: q.as_of || q.market_time || null },
    business: { summary: firstSentences(clean(((d.session || {}).profile || {}).summary || '').replace(/^The Company\b/, q.name || d.sym)), industry: ((d.session || {}).profile || {}).industry, sector: ((d.session || {}).profile || {}).sector, market_cap: q.market_cap },
    financials: f.available ? { period: per[0] || null, fiscal: (f.annual_fiscal || [])[0] || null, revenue: (a.revenue || [])[0], net_income: (a.net_income || [])[0],
      fcf: (a.free_cash_flow || [])[0], revenue_yoy: g.revenue_yoy_pct, income_yoy: g.net_income_yoy_pct, op_margin: m.operating_pct, net_margin: m.net_pct,
      net_cash: bs.net_cash, cash: bs.cash, liquid: bs.cash_and_short_term, debt: bs.total_debt } : null,
    valuation: { available: !!(fv.available && st.available), low: fv.low, mid: fv.mid, high: fv.high, stars: st.stars, word: st.word, basis: fv.basis, reason: st.reason || fv.reason,
      pe: q.trailing_pe, fwd_pe: q.forward_pe },
    earnings: { date: nr.date || null, days: nr.days_away, confirmed: nr.confirmed, timing: nr.timing, eps: nr.eps_consensus, eps_low: nr.eps_low, eps_high: nr.eps_high,
      revenue: nr.revenue_consensus_label, beats: eh.beat_count, sample: eh.sample_size, event_avg: pr.event_day_avg_pct },
    chart: { sma200: ma.sma200 && (ma.sma200.value ?? ma.sma200), high52: q.fifty_two_high, low52: q.fifty_two_low, levels },
    options: gex.error || !gex.regime ? null : { regime: (gex.regime || {}).state, call_wall: ((gex.levels || {}).call_wall || {}).strike, put_wall: ((gex.levels || {}).put_wall || {}).strike,
      implied: im.available ? { pct: im.implied_move_pct, expiry: im.expiry } : null, assumption: gex.assumption },
    evidence: { bull: ((t.cases || {}).bull || []).slice(0, 3), bear: ((t.cases || {}).bear || []).slice(0, 3) },
    risks: { vol: rk.annualised_vol_pct, max_dd: dd.max_drawdown_pct, dd_date: dd.max_drawdown_date, now_dd: dd.current_drawdown_pct, event_move: im.available ? im.implied_move_pct : null, report: nr.date || null },
  };
}

function series() {
  const ps = ((D.ticker || {}).technicals || {}).price_series || {};
  return (ps.dates || []).map((x, i) => ({ d: String(x).slice(0, 10), c: Number((ps.close || [])[i]) })).filter((p) => p.d && isNum(p.c)).slice(-253);
}

function page1(F) {
  const id = F.identity, b = F.business, fi = F.financials, v = F.valuation, e = F.earnings;
  return html`<section class="sh-page">
    <header class="sh-head"><div><p class="sh-kicker">Research sheet</p><h1>${id.name} <span class="sh-sym">${id.sym}</span></h1>
        <p class="sh-meta">${[id.exchange, id.currency].filter(Boolean).join(', ')}${b.industry ? `. ${[b.industry, b.sector].filter(Boolean).join(', ')}` : ''}</p></div>
      <div class="sh-px"><b>${isNum(id.price) ? money(id.price) : 'No price'}</b>${isNum(id.change_pct) ? html` <span>${signed(id.change_pct)}</span>` : ''}
        <p>${id.observed ? `Quote at ${etStamp(id.observed)}, delayed about 15 minutes` : 'Quote time not reported'}${id.session ? `. ${id.session}` : ''}</p></div></header>
    <h2>The business ${tag('reported')}</h2><p>${b.summary || html`<span class="sh-na">No description reported.</span>`}${isNum(b.market_cap) ? ` Market value ${usd(b.market_cap)}.` : ''}</p>
    <h2>Key financials ${tag('reported')}</h2>
    ${fi ? html`<p class="sh-sub">${fi.fiscal || 'Latest fiscal year'}${fi.period ? `, the year to ${fullDate(fi.period)}` : ''}</p>
      <table class="sh-t"><tbody>
        <tr><th>Revenue</th><td>${na(fi.revenue, usd)}</td><td>${na(fi.revenue_yoy, (x) => `${signed(x)} on the year before`)}</td></tr>
        <tr><th>Net income</th><td>${na(fi.net_income, usd)}</td><td>${na(fi.income_yoy, (x) => `${signed(x)} on the year before`)}</td></tr>
        <tr><th>Free cash flow</th><td>${na(fi.fcf, usd)}</td><td>${isNum(fi.fcf) && fi.revenue ? `${num((fi.fcf / fi.revenue) * 100, 1)}% of revenue` : ''}</td></tr>
        <tr><th>Margins</th><td>${na(fi.op_margin, (x) => `${num(x, 1)}% operating`)}</td><td>${na(fi.net_margin, (x) => `${num(x, 1)}% net`)}</td></tr>
        <tr><th>${isNum(fi.net_cash) && fi.net_cash < 0 ? 'Net debt' : 'Net cash'}</th><td>${na(isNum(fi.net_cash) ? Math.abs(fi.net_cash) : null, usd)}</td><td>${isNum(fi.liquid) ? `cash and short-term investments ${usd(fi.liquid)}, debt ${usd(fi.debt) || 'n/a'}` : isNum(fi.cash) ? `cash ${usd(fi.cash)}, debt ${usd(fi.debt) || 'n/a'}` : ''}</td></tr>
      </tbody></table>` : html`<p class="sh-na">No annual statements in the feed for ${id.sym}.</p>`}
    <h2>Valuation ${tag('optic')}</h2>
    ${v.available ? html`<p><b>${clean(v.word || '')}.</b> The usual range from its own five-year P/E is ${money(v.low, 0)} to ${money(v.high, 0)} (middle ${money(v.mid, 0)}); the price is ${money(id.price)}. ${v.stars} of 5 stars, where more stars means cheaper against its own past.</p>
      <p class="sh-sub">${clean(v.basis || '')} A reading against its own history, not an intrinsic value or a forecast.</p>`
      : html`<p class="sh-na">${clean(v.reason || 'No valuation range for this company.')}</p>`}
    <p class="sh-sub">P/E ${na(v.pe, (x) => `${num(x, 1)} trailing`)} ${tag('reported')}, ${na(v.fwd_pe, (x) => `${num(x, 1)} forward`)} ${tag('estimate')}</p>
    <h2>Earnings ${tag('estimate')}</h2>
    ${e.date ? html`<p><b>Next report ${fullDate(e.date)}</b>${isNum(e.days) ? `, ${plural(e.days, 'day')} away` : ''}, ${e.confirmed ? 'date confirmed' : 'date not confirmed'}${e.timing === 'after_close' ? ', after the close' : e.timing === 'before_open' ? ', before the open' : ''}.
      ${isNum(e.eps) ? `Analysts expect EPS of ${money(e.eps)}${isNum(e.eps_low) && isNum(e.eps_high) ? ` (range ${money(e.eps_low)} to ${money(e.eps_high)})` : ''}${e.revenue ? ` on revenue of about ${e.revenue}` : ''}.` : 'No consensus in the feed.'}</p>` : html`<p class="sh-na">No report date in the feed.</p>`}
    ${isNum(e.sample) && e.sample ? html`<p class="sh-sub">Beat the estimate in ${e.beats} of the last ${e.sample} quarters ${tag('reported')}${isNum(e.event_avg) ? `; the session after a report has moved ±${num(e.event_avg, 2)}% on average` : ''}. A beat does not mean the price rises.</p>` : ''}
    <h2>Price, past year ${tag('reported')}</h2><div class="sh-chart" data-sheet-chart></div>
  </section>`;
}

function page2(F) {
  const ch = F.chart, o = F.options, ev = F.evidence, r = F.risks, id = F.identity;
  return html`<section class="sh-page sh-cont"><p class="sh-kicker">${id.sym} research sheet, continued</p>
    <h2>Chart structure ${tag('optic')}</h2>
    <p>52-week range ${na(ch.low52, money)} to ${na(ch.high52, money)}${isNum(ch.sma200) ? `; the 200-day average is ${money(ch.sma200)}, the price ${id.price >= ch.sma200 ? 'above' : 'below'} it` : ''}.</p>
    ${ch.levels.length ? html`<table class="sh-t"><thead><tr><th>Level</th><th>Role</th><th>Away</th><th>Touches</th></tr></thead><tbody>${ch.levels.map((l) => html`<tr><td>${money(l.price)}</td><td>${l.role}</td><td>${signed(l.distance_pct, 1)}</td><td>${l.touches}</td></tr>`)}</tbody></table>
      <p class="sh-sub">Levels where daily prices turned before, from confirmed swing points. They describe the past chart; they are not orders or predictions.</p>` : html`<p class="sh-na">No levels found.</p>`}
    <h2>Options positioning ${tag('estimate')}</h2>
    ${o ? html`<p>${o.implied ? `Options price a move of ±${num(o.implied.pct)}% through ${shortDate(o.implied.expiry)}. ` : ''}Modelled dealer gamma is ${o.regime || 'not read'}${o.call_wall ? `, with the largest call and put concentrations at ${num(o.call_wall, 0)} and ${num(o.put_wall, 0)}` : ''}.</p>
      <p class="sh-sub">${one(o.assumption || 'Dealer gamma assumes which side of each trade dealers hold.')} Estimated from open interest, not reported positions.</p>` : html`<p class="sh-na">No usable option chain when this was generated.</p>`}
    <h2>Evidence for and against ${tag('optic')}</h2>
    <div class="sh-two"><div><h3>Supporting</h3>${ev.bull.length ? html`<ul>${ev.bull.map((x) => html`<li><b>${clean(x.claim)}.</b> ${one(x.detail)}</li>`)}</ul>` : html`<p class="sh-na">None found by the rules.</p>`}</div>
      <div><h3>Conflicting</h3>${ev.bear.length ? html`<ul>${ev.bear.map((x) => html`<li><b>${clean(x.claim)}.</b> ${one(x.detail)}</li>`)}</ul>` : html`<p class="sh-na">None found by the rules.</p>`}</div></div>
    <h2>Principal risks</h2>
    <ul class="sh-risk">
      <li>${isNum(r.vol) ? `Volatility of about ${num(r.vol, 0)}% a year` : 'Volatility not measured'}${isNum(r.max_dd) ? `; its largest fall in the history measured was ${signed(r.max_dd, 0)}${r.dd_date ? ` (to ${fullDate(r.dd_date)})` : ''}` : ''}. ${tag('reported')}</li>
      ${r.report ? html`<li>The ${fullDate(r.report)} report${isNum(r.event_move) ? `, with options pricing ±${num(r.event_move)}% through the next expiry` : ''}. ${tag('estimate')}</li>` : ''}
      ${F.valuation.available && F.valuation.stars <= 2 ? html`<li>The price is ${F.valuation.stars === 1 ? 'above' : 'in the upper half of'} its usual valuation range, so results have less room to disappoint. ${tag('optic')}</li>` : ''}
      <li>Delayed and free data: figures can be revised or wrong, and nothing here is a recommendation.</li></ul>
    <h2>Sources</h2>
    <p class="sh-sub">Quotes, fundamentals, estimates and option chains from Yahoo Finance (delayed); filings from SEC EDGAR; ranges, levels, gamma estimates and the evidence lists from Optic's published rules. Generated ${new Date().toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' })}. Not financial advice. For research and education only.</p>
  </section>`;
}

function paint() {
  if (!live) return;
  const sym = D.sym;
  if (D.err && !D.ticker) { draw(mainEl, failed(`${sym}'s research sheet`, D.err, { retry: 'sheet' })); return; }
  const ready = D.ticker && D.fairValue !== undefined && D.earnings !== undefined;
  draw(mainEl, html`<div class="sh-actions"><a class="btn btn-quiet btn-sm" href="#/${encodeURIComponent(sym)}">Back to the Dossier</a>
      <button type="button" class="btn btn-primary btn-sm" data-sheet-print ${ready ? '' : 'disabled'}>Print or save as PDF</button>
      <span class="t-muted">${ready ? 'Two pages, Letter or A4. Private holdings are never included.' : 'Gathering the figures…'}</span></div>
    ${ready ? html`<article class="sheet" aria-label="${sym} research sheet">${page1(sheetFacts(D))}${page2(sheetFacts(D))}</article>` : skeleton('lines', 8, 'Gathering the figures for the sheet')}`);
  const slot = mainEl.querySelector('[data-sheet-chart]'), pts = series();
  if (slot && pts.length > 20) slot.innerHTML = lineChart(pts, { w: 680, h: 140, area: true, label: `${sym} closing price, past year`, pad: { t: 10, r: 48, b: 22, l: 0 }, measure: false }).html;
}

export async function render(main, route) {
  live = true; mainEl = main; const sym = route.symbol; D = { sym };
  document.title = `${sym} research sheet, Optic`;
  paint();
  const enc = encodeURIComponent(sym), step = (p, k) => p.then((d) => { D[k] = d; }, (e) => { if (k === 'ticker') D.err = e; else D[k] = D[k] || {}; }).finally(paint);
  step(api.get(`/api/ticker/${enc}?max_expiries=4&macro=true`, { ttl: 120000, timeout: 60000 }), 'ticker');
  step(api.get(`/api/session/${enc}`, { ttl: 60000 }), 'session');
  step(api.get(`/api/quote/${enc}`, { ttl: 20000, timeout: 15000 }).then((d) => d.quote || d), 'quote');
  step(api.get(`/api/fair-value/${enc}`, { ttl: 600000, timeout: 45000 }), 'fairValue');
  step(api.get(`/api/earnings/${enc}`, { ttl: 600000, timeout: 45000 }), 'earnings');
  step(api.get(`/api/longterm/${enc}?indices=false`, { ttl: 600000, timeout: 45000 }), 'longterm');
  main.addEventListener('click', (e) => { if (e.target.closest('[data-sheet-print]')) window.print(); });
}
export function dispose() { live = false; }
export const retry = { sheet: (main, route) => render(main, route) };
