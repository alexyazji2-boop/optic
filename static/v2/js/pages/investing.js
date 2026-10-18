// Dossier, Investing. The long-term picture: the trend score and what it is
// built from, return and risk, the weekly structure, drawdown, the multiple
// against its own history, fair value and stars, the discounted cash flow
// summary, valuation scenarios, and accumulation levels.
//
// Data: /api/longterm (trend score, returns, weekly bars), /api/pe-history,
// /api/fair-value, /api/valuation (DCF), /api/valuation-inputs. None calls a
// model. The trend score is labelled as in the Overview, beside the
// business-and-price case, so the two long-term readings never blur.
import { $, html, render as draw, raw } from '../core/dom.js';
import { CLASSIC } from '../core/classic.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, signed, money, compact, clean, capFirst, shortDate, fullDate, isNum, score100 } from '../core/format.js';
import { lineChart, meter, mountCharts } from '../ui/chart.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { core, header, tabs, isFund } from './dossier-frame.js';
import * as VS from './valuation-scenarios.js';

const RANGES = { '1Y': 52, '3Y': 156, '5Y': 260, '10Y': 520, All: Infinity };
let D = {}, live = true, mainEl = null;

function setting(k, d) { try { return localStorage.getItem(k) || d; } catch (e) { return d; } }
function setSetting(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private */ } }

const sma = (vals, n) => vals.map((_, i) => (i + 1 < n ? null : vals.slice(i + 1 - n, i + 1).reduce((a, b) => a + b, 0) / n));
function monthly(dates, closes) {
  const out = []; dates.forEach((d, i) => { const m = d.slice(0, 7); if (out.length && out[out.length - 1].m === m) out[out.length - 1] = { m, d, c: closes[i] }; else out.push({ m, d, c: closes[i] }); });
  return out;
}
const kv = (rows, n = 3) => html`<dl class="kv" style="--kv:${n}">${rows.filter(Boolean).map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
const ask = (sym, label, q) => miloButton(label, { ask: q, context: `${sym} Dossier, Investing`, symbol: sym });
const pct = (v, dp = 1) => (isNum(v) ? `${num(v, dp)}%` : 'n/a');

/* ---------------- sections ---------------- */
function trend(sym) {
  const h = (D.lt || {}).holding;
  if (D.ltErr) return failed('The long-term model', D.ltErr, { retry: 'lt' });
  if (!h) return skeleton('lines', 4, 'Loading the long-term model');
  const sc = h.conviction_scale || {};
  const s = score100(h.conviction_score, sc.min_possible, sc.max_possible);
  const st = ((D.fv || {}).stars) || {}, vh = h.valuation_history || {};
  const conv = (((D.fw || {}).long_term) || {}).conviction || {};
  const clash = s !== null && s >= 60 && ((st.available && st.stars <= 2) || (vh.available && vh.percentile >= 80));
  return html`<section class="section" aria-labelledby="lt-h">
    <div class="section-head"><div><h2 class="t-h2" id="lt-h">Long-term trend score, from price history</h2><p class="section-sub">How the stock has behaved over years. It does not say whether the price is low.</p></div>${ask(sym, 'Ask Milo about this score', `What is ${sym}'s long-term trend score built from, and what does it leave out?`)}</div>
    <div class="figure"><p class="t-display-m">${s === null ? 'n/a' : num(s, 0)} <small class="t-muted">of 100</small></p><p class="delta"><span>${capFirst(h.conviction || '')} conviction</span><span class="t-muted">${capFirst((h.long_trend || {}).phase || '')}</span></p></div>
    <p><b>The model's rule:</b> ${clean(h.plan || '')}</p>
    ${clash ? html`<p class="reconcile"><b>Read it beside the price.</b> The score is built from trend and the five-year record${st.available ? `, while the price earns ${st.stars} of 5 stars against its own usual valuation` : ''}${vh.available ? ` and the P/E sits at the ${num(vh.percentile, 0)}th percentile of its own history` : ''}.${conv.label ? ` The business-and-price case on the Overview reads ${conv.label}.` : ''}</p>` : ''}
    ${(h.data_quality || {}).warnings && h.data_quality.warnings.length ? h.data_quality.warnings.map((w) => html`<p class="stale">${clean(w)}</p>`) : ''}
    <div class="tscroll"><table class="t"><thead><tr><th>Factor</th><th>Type</th><th>Points</th><th>Why</th></tr></thead>
      <tbody>${(h.conviction_factors || []).map((f) => html`<tr><td>${f.label}</td><td>${f.kind}</td><td>${signed(f.points, 0, '')}</td><td style="text-align:left">${clean(f.detail)}</td></tr>`)}
      <tr><td><b>Total</b></td><td></td><td><b>${signed(h.conviction_score, 0, '')}</b></td><td style="text-align:left" class="t-muted">On a scale of ${sc.min_possible} to ${sc.max_possible}; ${num(s, 0)} of 100 when mapped.</td></tr></tbody></table></div>
  </section>`;
}

function returnsRisk() {
  const h = (D.lt || {}).holding; if (!h) return '';
  const hz = h.horizons || {}, r = h.risk || {};
  return html`<section class="section" aria-labelledby="rr-h"><h2 class="t-h2" id="rr-h">Return and risk</h2>
    ${kv([['1 year', html`<span class="${hz.return_1y_pct >= 0 ? 'up' : 'down'}">${signed(hz.return_1y_pct)}</span>`], ['3 years, a year', signed(hz.cagr_3y_pct)], ['5 years, a year', signed(hz.cagr_5y_pct)], ['Against the S&P 500, 5 years', html`${signed(h.excess_cagr_5y_pct)} a year <span class="t-muted">(index ${signed(h.benchmark_cagr_5y_pct)})</span>`]], 4)}
    ${kv([['Volatility, a year', pct(r.annualised_vol_pct)], ['Downside volatility', pct(r.downside_vol_pct)], ['Return per unit of risk', num(r.sharpe_proxy, 2)], ['Downside-adjusted', num(r.sortino_proxy, 2)], ['Beta to the S&P 500', num(r.beta_vs_spy, 2)], ['Correlation', num(r.correlation_vs_spy, 2)], ['Best day', signed(r.best_day_pct)], ['Worst day', signed(r.worst_day_pct)], ['Up days', pct(r.pct_positive_days)]], 3)}
  </section>`;
}

function weekly(sym) {
  const h = (D.lt || {}).holding; if (!h) return '';
  const lt = h.long_trend || {};
  const range = setting('optic.lt.range', '5Y'), iv = setting('optic.lt.interval', 'weekly');
  return html`<section class="section" aria-labelledby="ws-h"><div class="section-head"><div><h2 class="t-h2" id="ws-h">Weekly structure</h2><p class="section-sub">${clean(lt.guidance || '')}</p></div>
      <div class="cluster"><div class="seg" role="group" aria-label="Interval">${[['weekly', 'Weekly'], ['monthly', 'Monthly']].map(([k, l]) => html`<button type="button" data-v2-lt-iv="${k}" aria-pressed="${iv === k}">${l}</button>`)}</div>
      <div class="seg" role="group" aria-label="Range">${Object.keys(RANGES).map((k) => html`<button type="button" data-v2-lt-range="${k}" aria-pressed="${range === k}">${k}</button>`)}</div></div></div>
    <div class="chart-slot" data-chart="weekly">${skeleton('chart')}</div>
    <p class="legend-line"><span><i></i>Close</span><span><i class="o1"></i>40-${iv === 'monthly' ? 'month' : 'week'} average</span><span><i class="o2"></i>200-${iv === 'monthly' ? 'month' : 'week'} average</span></p>
    ${kv([['Against the 40-week average', signed(lt.vs_40w_sma)], ['Against the 200-week average', signed(lt.vs_200w_sma)], ['Weekly RSI', html`${num(lt.weekly_rsi, 1)} <span class="t-muted">40-week slope ${signed(lt.slope_40w_pct_3m)} over 3 months</span>`]], 3)}
  </section>`;
}
function weeklyMaker() {
  const h = (D.lt || {}).holding; if (!h) return {};
  const range = setting('optic.lt.range', '5Y'), iv = setting('optic.lt.interval', 'weekly');
  let dates, closes;
  if (range === 'All' && D.allWeeks) { dates = D.allWeeks.dates; closes = D.allWeeks.close; }
  else { const s = (h.long_trend || {}).series || {}; dates = s.dates || []; closes = s.close || []; }
  let pts = dates.map((d, i) => ({ d: String(d).slice(0, 10), c: Number(closes[i]) })).filter((p) => isNum(p.c));
  if (iv === 'monthly') pts = monthly(pts.map((p) => p.d), pts.map((p) => p.c)).map((m) => ({ d: m.d, c: m.c }));
  const all = pts.map((p) => p.c), s40 = sma(all, 40), s200 = sma(all, 200);
  const keep = range === 'All' ? pts.length : Math.min(pts.length, iv === 'monthly' ? Math.ceil(RANGES[range] / 4.33) : RANGES[range]);
  const sl = pts.slice(-keep);
  return { weekly: (w) => lineChart(sl, { w, h: Math.round(Math.max(220, Math.min(320, w * 0.32))), area: true, label: `${D.sym} ${iv} closes`, overlays: [{ values: s40.slice(-keep), cls: 'o1' }, { values: s200.slice(-keep), cls: 'o2' }], monthStep: keep > 150 ? 12 : 3, pad: { t: 16, r: 52, b: 24, l: 0 } }) };
}

function drawdown() {
  const h = (D.lt || {}).holding; if (!h || !h.drawdown) return '';
  const dd = h.drawdown;
  return html`<section class="section" aria-labelledby="dd-h"><h2 class="t-h2" id="dd-h">Drawdown, daily</h2>
    ${kv([['From the high now', signed(dd.current_drawdown_pct)], ['Largest drawdown', html`${signed(dd.max_drawdown_pct)} <span class="t-muted">${fullDate(dd.max_drawdown_date)}</span>`], ['All-time high', html`${num(dd.all_time_high)} <span class="t-muted">${fullDate(dd.ath_date)}</span>`]], 3)}
    <div class="chart-slot" data-chart="dd"></div></section>`;
}
function ddMaker() {
  const dd = (((D.lt || {}).holding) || {}).drawdown; if (!dd) return {};
  const pts = (dd.dates || []).map((d, i) => ({ d: String(d).slice(0, 10), c: Number(dd.series[i]) })).filter((p) => isNum(p.c));
  return { dd: (w) => lineChart(pts, { w, h: 170, area: false, dp: 1, label: 'Drawdown from the running high, percent', pad: { t: 12, r: 52, b: 24, l: 0 } }) };
}

function multiple(sym) {
  const pe = D.pe, h = (D.lt || {}).holding || {}, vh = h.valuation_history || {}, rm = h.revenue_multiple || {};
  if (pe === undefined) return html`<section class="section">${skeleton('lines', 3, 'Loading the multiple history')}</section>`;
  return html`<section class="section" aria-labelledby="pe-h"><div class="section-head"><div><h2 class="t-h2" id="pe-h">The multiple against its own history</h2><p class="section-sub">${pe && pe.available ? `${num(pe.weeks / 52, 0)} years of weekly trailing P/E from the company's filings.` : 'No P/E history for this company.'}</p></div>${ask(sym, 'Ask Milo about the multiple', `Is ${sym}'s P/E high against its own history, and why might that be?`)}</div>
    ${pe && pe.available ? html`${kv([['Trailing P/E now', html`${num(pe.pe_current, 1)} <span class="t-muted">${num(pe.pe_percentile, 0)}th percentile</span>`], ['Its own median, 5 years', html`${num(pe.pe_median, 1)} <span class="t-muted">quartiles ${num((pe.pe_bands || {})[25], 1)} to ${num((pe.pe_bands || {})[75], 1)}</span>`], ['Cross-check with the quote feed', (pe.anchor || {}).available ? `${num(pe.anchor.provider, 1)} (${pe.anchor.agrees ? 'agrees' : 'differs'})` : 'n/a']], 3)}
      <div class="chart-slot" data-chart="pe"></div><p class="legend-line"><span><i></i>Trailing P/E</span><span><i class="o1"></i>Median</span><span><i class="o3"></i>25th and 75th percentile</span></p>
      ${(pe.revenue_growth || []).length ? html`<details class="more-inline"><summary>Revenue growth, last 8 quarters</summary><div class="tscroll"><table class="t"><thead><tr><th>Quarter</th><th>Revenue</th><th>Growth, year on year</th></tr></thead><tbody>${pe.revenue_growth.slice(-8).map((r) => html`<tr><td>${r.label}</td><td>${compact(r.revenue)}</td><td>${signed(r.growth_pct)}</td></tr>`)}</tbody></table></div></details>` : ''}
      <p class="asof">${clean(pe.method || '')}</p>` : ''}
    ${vh.available ? html`<h3>Fiscal years</h3><p>${capFirst(clean(vh.read || ''))}: ${num(vh.current_pe, 1)} times earnings against a median of ${num(vh.median_pe, 1)} over ${vh.usable_years} years (${signed(vh.premium_to_median_pct, 0)}).</p>
      <div class="tscroll"><table class="t"><thead><tr><th>Fiscal year</th><th>EPS</th><th>Average price</th><th>P/E</th></tr></thead><tbody>${(vh.years || []).map((y) => html`<tr><td>${shortDate(y.period)} ${String(y.period).slice(0, 4)}</td><td>${num(y.eps)}</td><td>${num(y.avg_price)}</td><td>${num(y.pe, 1)}</td></tr>`)}</tbody></table></div>` : ''}
    ${rm.available ? html`<details class="more-inline"><summary>Revenue and the multiple, by fiscal year</summary><div class="tscroll"><table class="t"><thead><tr><th>Year</th><th>Revenue</th><th>P/E</th></tr></thead><tbody>${rm.years.map((y) => html`<tr><td>${y.label}</td><td>${compact(y.revenue)}</td><td>${num(y.pe, 1)}</td></tr>`)}</tbody></table></div><p class="asof">${clean(rm.method || '')}</p></details>` : ''}
  </section>`;
}
function peMaker() {
  const pe = D.pe; if (!pe || !pe.available) return {};
  const pts = (pe.pe_series || []).map((r) => ({ d: r.date, c: r.pe })).filter((p) => isNum(p.c));
  const b = pe.pe_bands || {};
  const flat = (v) => pts.map(() => v);
  return { pe: (w) => lineChart(pts, { w, h: 220, dp: 1, label: 'Trailing P/E, weekly', overlays: [{ values: flat(b[50]), cls: 'o1' }, { values: flat(b[25]), cls: 'o3' }, { values: flat(b[75]), cls: 'o3' }], monthStep: 12, pad: { t: 14, r: 52, b: 24, l: 0 } }) };
}

function fairValue(sym) {
  const d = D.fv;
  if (d === undefined) return html`<section class="section">${skeleton('lines', 3, 'Loading fair value')}</section>`;
  if (!d) return '';
  const fv = d.fair_value || {}, st = d.stars || {}, an = d.analysts || {}, dv = d.dividend || {}, ms = d.morningstar || {};
  const price = (D.quote || {}).price || fv.price;
  return html`<section class="section" aria-labelledby="fv-h"><div class="section-head"><div><h2 class="t-h2" id="fv-h">Fair value and stars</h2><p class="section-sub">${clean(st.note || '')}</p></div>${ask(sym, 'Ask Milo about fair value', `How should I read ${sym}'s fair value range and star rating?`)}</div>
    ${st.available ? html`<p class="stars">${raw(`<svg class="star-row" viewBox="0 0 120 22" aria-hidden="true">${[0, 1, 2, 3, 4].map((i) => `<path class="${i < st.stars ? 'on' : 'off'}" transform="translate(${i * 24} 0)" d="M11 1.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L11 16.4 5.1 19.5l1.2-6.5L1.5 8.4l6.6-.9z"/>`).join('')}</svg>`)}<span class="sr">${st.stars} of 5 stars.</span> <b>${clean(st.word)}</b></p><p class="asof">${clean(st.rule)}</p>` : html`<p><b>No star rating.</b> ${clean(st.reason || '')}</p>`}
    ${fv.available ? html`${!fv.wide ? raw(meter({ lo: fv.low, mid: fv.mid, hi: fv.high, price, w: 420, showMid: true })) : ''}
      ${kv([['Fair value range', `${num(fv.low)} to ${num(fv.high)}`], ['Middle', num(fv.mid)], ['Price now', html`${num(price)} <span class="t-muted">${isNum(fv.gap_to_mid_pct) ? signed(fv.gap_to_mid_pct, 1) + ' against the middle' : ''}</span>`]], 3)}
      ${fv.wide ? html`<p class="stale">${clean(fv.wide_note)}</p>` : ''}<p class="asof">${clean(fv.basis || '')}</p>
      <details class="more-inline"><summary>What this range cannot say</summary><ul class="plain">${(fv.limits || []).map((l) => html`<li>${clean(l)}</li>`)}</ul></details>` : html`<p>${clean(fv.reason || 'No fair value estimate for this company.')}</p>`}
    ${isNum(an.target_mean) ? html`<h3>What analysts say</h3>${kv([['Average target', html`${num(an.target_mean)} <span class="t-muted">${signed(an.upside_pct, 1)}</span>`], ['Range of targets', `${num(an.target_low)} to ${num(an.target_high)}`], ['Ratings', isNum(an.buys) ? `${an.buys} buy, ${an.holds} hold, ${an.sells} sell` : `${num(an.buy_share_pct, 0)}% buy`]], 3)}${an.note ? html`<p class="asof">${clean(an.note)}</p>` : ''}` : ''}
    ${dv.available ? html`<h3>Dividend score: ${dv.score} of 100, ${dv.band}</h3><div class="tscroll"><table class="t"><thead><tr><th>Part</th><th>Value</th><th>Points</th><th>Why</th></tr></thead><tbody>${(dv.parts || []).map((p) => html`<tr><td>${p.label}</td><td>${clean(p.value)}</td><td>${num(p.points, 0)}</td><td style="text-align:left">${clean(p.why)}</td></tr>`)}</tbody></table></div><p class="asof">${clean(dv.method || '')}</p>` : ''}
    ${ms.available ? html`<h3>Morningstar</h3><p>${ms.stars} stars, ${clean(ms.risk_word || ms.risk || '')}. ${clean(ms.note || '')}</p>` : ''}
  </section>`;
}

function dcf(sym) {
  const v = D.val;
  if (v === undefined) return html`<section class="section">${skeleton('lines', 3, 'Loading the cash flow model')}</section>`;
  if (!v || !v.available) return '';
  const d = v.dcf || {}, sc = v.scenarios || {}, rv = v.reverse || {}, tor = (v.tornado || []).slice(0, 4);
  const price = (v.market || {}).price;
  return html`<section class="section" aria-labelledby="dcf-h"><div class="section-head"><div><h2 class="t-h2" id="dcf-h">Fair-value model, discounted cash flow</h2><p class="section-sub">${clean((((v.classification || {}).models || {}).dcf || {}).name || '')}. ${clean((((v.classification || {}).models || {}).dcf || {}).why || '')}</p></div>
      <a class="btn" href="${CLASSIC}#/${sym}/investing">Edit the model in the current app</a></div>
    ${kv([['Base case, a share', html`${money(d.per_share)} <span class="t-muted">${signed((d.upside || 0) * 100, 0)} against ${num(price)}</span>`], ['Discount rate', pct((d.discount_rate || 0) * 100, 2)], ['Share of value after the forecast', pct((d.terminal_share || 0) * 100, 0)]], 3)}
    <div class="tscroll"><table class="t"><thead><tr><th>Case</th><th>A share</th><th>Against the price</th><th>What it assumes</th></tr></thead>
      <tbody>${['bear', 'base', 'bull'].filter((k) => sc[k]).map((k) => html`<tr><td>${capFirst(k)}</td><td>${money(sc[k].per_share)}</td><td>${signed((sc[k].upside || 0) * 100, 0)}</td><td style="text-align:left">${clean((v.scenario_text || {})[k] || '')}</td></tr>`)}</tbody></table></div>
    ${(rv.solves || []).length ? html`<h3>What today's price implies</h3><ul class="plain">${rv.solves.map((s) => html`<li>${clean(s.text)} <span class="t-muted">Holding ${clean(s.held)}.</span></li>`)}</ul>` : ''}
    ${tor.length ? html`<h3>What moves the value most</h3><div class="tscroll"><table class="t"><thead><tr><th>Input</th><th>Lower</th><th>Higher</th><th>Swing</th></tr></thead><tbody>${tor.map((t) => html`<tr><td>${t.label}</td><td>${money(t.value_low)}</td><td>${money(t.value_high)}</td><td>${money(t.swing)}</td></tr>`)}</tbody></table></div>` : ''}
    ${(v.warnings || []).map((w) => html`<p class="stale">${clean(w.text || w)}</p>`)}
    <p class="asof">Model output from the company's filings, with stated defaults. The full workspace (assumptions, sensitivity tables, statements, other methods, peers, saved models) opens in the current app.</p>
  </section>`;
}

function scenarios(sym) {
  if (D.vin === undefined) return html`<section class="section">${skeleton('lines', 3, 'Loading valuation inputs')}</section>`;
  if (!D.vin || !D.vin.available) return '';
  return html`<section class="section" aria-labelledby="vs-h"><div class="section-head"><div><h2 class="t-h2" id="vs-h">Valuation scenarios</h2></div>${ask(sym, 'Ask Milo about these scenarios', `Do my ${sym} bear, base and bull assumptions look reasonable against its history?`)}</div>
    ${VS.view(sym, D.vin, D.vsBody, D.vsStatus)}</section>`;
}

function accumulation() {
  const h = (D.lt || {}).holding; if (!h) return '';
  const z = h.accumulation_zones || [], va = h.valuation || {};
  return html`<section class="section" aria-labelledby="ac-h"><h2 class="t-h2" id="ac-h">Valuation and accumulation levels</h2>
    ${kv([['Forward P/E', num(va.forward_pe, 1)], ['Trailing P/E', num(va.trailing_pe, 1)], ['Price to book', num(va.price_to_book, 1)], ['Dividend yield', isNum(va.dividend_yield) ? pct(va.dividend_yield * 100, 2) : 'n/a'], ['Analysts\' average target', num(((h.fundamentals || {}).analyst_target))]], 3)}
    <ul class="plain">${(va.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul><p class="asof">${clean(va.caveat || '')}</p>
    ${z.length ? html`<div class="tscroll"><table class="t"><thead><tr><th>Level</th><th>Price</th><th>Distance</th><th>Role</th></tr></thead><tbody>${z.map((l) => html`<tr><td>${l.label}${l.is_golden ? ' (golden zone)' : ''}</td><td>${num(l.price)}</td><td>${signed(l.distance_pct)}</td><td>${capFirst(l.kind)}</td></tr>`)}</tbody></table></div>
      <p class="asof">Levels where long-term buyers have historically stepped in, from the weekly chart. Not targets and not advice.</p>` : ''}
    <p class="asof">${clean(h.disclaimer || '')}</p></section>`;
}

/* ---------------- page ---------------- */
function paint() {
  if (!live) return;
  const sym = D.sym;
  const keep = document.activeElement && mainEl.contains(document.activeElement) ? document.activeElement : null;
  const keepKey = keep && (keep.name || Object.entries(keep.dataset || {}).map((e) => e.join('=')).join('&'));
  const y = window.scrollY;
  draw(mainEl, html`${header(sym, D, 'long')}${tabs(sym, 'long', { fund: isFund(D) })}
    ${trend(sym)}${returnsRisk()}${weekly(sym)}${drawdown()}${multiple(sym)}${fairValue(sym)}${dcf(sym)}${scenarios(sym)}${accumulation()}`);
  mountCharts(mainEl, Object.assign({}, weeklyMaker(), ddMaker(), peMaker()));
  if (keepKey) {
    const el = keep.name ? mainEl.querySelector(`[name="${CSS.escape(keep.name)}"]`) : null;
    const el2 = el || [...mainEl.querySelectorAll('button')].find((b) => Object.entries(b.dataset).map((e) => e.join('=')).join('&') === keepKey);
    if (el2) el2.focus({ preventScroll: true });
  }
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

export async function render(main, route) {
  live = true; mainEl = main;
  const sym = route.symbol, enc = encodeURIComponent(sym);
  D = { sym };
  store.pushRecent(sym);
  document.title = `${sym} Investing, Optic`;
  provideContext(() => ({ view: 'long', ticker: sym, quote: D.quote, long_term: D.lt, fair_value: D.fv, valuation: D.val ? { dcf: (D.val.dcf || {}).per_share, scenarios: D.val.scenarios, reverse: D.val.reverse } : null, scenarios: D.vsBody }));
  paint(); wire(main);
  const step = (p, ok, bad) => p.then((d) => { if (D.sym === sym) ok(d); }, (e) => { if (D.sym === sym) bad(e); }).finally(() => { if (D.sym === sym) paint(); });
  step(core(sym), (c) => { D.quote = c.quote; D.session = c.session; D.quoteError = c.quoteError; }, () => {});
  step(api.get(`/api/longterm/${enc}?indices=false`, { ttl: 600000, timeout: 60000 }), (d) => { D.lt = d; }, (e) => { D.ltErr = e; });
  step(api.get(`/api/pe-history/${enc}?years=10`, { ttl: 3600000, timeout: 45000 }), (d) => { D.pe = d; }, () => { D.pe = null; });
  step(api.get(`/api/fair-value/${enc}`, { ttl: 600000, timeout: 30000 }), (d) => { D.fv = d; }, () => { D.fv = null; });
  step(api.get(`/api/valuation/${enc}`, { ttl: 600000, timeout: 45000 }), (d) => { D.val = d; }, () => { D.val = null; });
  step(api.get(`/api/valuation-inputs/${enc}`, { ttl: 600000, timeout: 30000 }), (d) => { D.vin = d; }, () => { D.vin = null; });
  step(api.get(`/api/framework/${enc}?mode=combined`, { ttl: 300000, timeout: 60000 }), (d) => { D.fw = d; }, () => {});
  step(VS.load(sym), (b) => { D.vsBody = b || null; }, () => {});
  if (setting('optic.lt.range', '5Y') === 'All') loadAll();
}
async function loadAll() {
  if (D.allWeeks) return;
  try { D.allWeeks = await api.get(`/api/weekly-bars/${encodeURIComponent(D.sym)}?span=max`, { ttl: 3600000, timeout: 45000 }); } catch (e) { toast('The full weekly history did not load.'); }
  paint();
}
export function dispose() { live = false; }
export const retry = { lt: (m, r) => { api.invalidate('/api/longterm'); render(m, r); } };

function wire(main) {
  main.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s);
    let b;
    if ((b = t('[data-v2-lt-range]'))) { setSetting('optic.lt.range', b.dataset.v2LtRange); if (b.dataset.v2LtRange === 'All') loadAll(); paint(); return; }
    if ((b = t('[data-v2-lt-iv]'))) { setSetting('optic.lt.interval', b.dataset.v2LtIv); paint(); return; }
    if (t('[data-v2-vs-fill]')) {
      // the classic app's valuationFillFromHistory: one decimal, and the exit
      // P/E from the company's own median multiple when there is one
      const f = $('[data-v2-vs]', main); const hist = (D.vin || {}).history || {};
      const vh = (((D.lt || {}).holding || {}).valuation_history) || {};
      const filled = [];
      const put = (k, v) => { if (!Number.isFinite(v)) return; f[`base.${k}`].value = String(Math.round(v * 10) / 10); filled.push(`base.${k}`); };
      put('growth', (hist.revenue_growth || {}).value); put('margin', (hist.margin || {}).value); put('share_change', (hist.share_change || {}).value);
      if (vh.available && vh.median_pe > 0) put('pe', vh.median_pe);
      const body = VS.readForm(f, D.vsBody);
      body.from_history = [...new Set([...body.from_history, ...filled])];
      D.vsBody = body;
      D.vsStatus = filled.includes('base.pe') ? 'Base case filled from history, exit P/E from its median multiple. Save to keep it.' : 'Base case filled from history. Add an exit P/E, then save.'; paint();
    }
  });
  main.addEventListener('input', (e) => {
    const f = e.target.closest('[data-v2-vs]'); if (!f) return;
    clearTimeout(D.vsT);
    D.vsT = setTimeout(() => {
      D.vsBody = VS.readForm(f, D.vsBody); D.vsStatus = 'Not saved yet.';
      // only the results change while typing, so the caret stays where it is
      const start = VS.startOf(D.vin, D.vsBody);
      VS.CASES.forEach(([c]) => { const o = f.querySelector(`[data-v2-vs-out="${c}"]`); if (o) draw(o, VS.caseOut(start, D.vsBody[c], D.vsBody.shared)); });
      const st = f.querySelector('.vs-status'); if (st) st.textContent = D.vsStatus;
    }, 350);
  });
  main.addEventListener('submit', async (e) => {
    const f = e.target.closest('[data-v2-vs]'); if (!f) return;
    e.preventDefault();
    const body = VS.readForm(f, D.vsBody);
    if (Object.keys(VS.errors(body)).length) { D.vsStatus = 'Not saved: fix the boxes marked first.'; paint(); return; }
    D.vsBody = body; D.vsStatus = await VS.save(D.sym, body); paint();
    toast(D.vsStatus);
  });
}
