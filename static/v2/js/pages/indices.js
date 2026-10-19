// Markets, Indices. What the major indices say together, the index funds'
// trend board (with an Index Read on request), the long-run regime of each
// index, and growth against the broad market. From /api/indices and
// /api/indices/board; no model call unless the reader asks for a read.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, clean, capFirst, isNum } from '../core/format.js';
import { lineChart, mountCharts } from '../ui/chart.js';
import { skeleton, failed } from '../ui/states.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { sectionHead } from './tabs.js';
import { sectorBoard, sectorReadBlock, loadSectorRead } from './market-shared.js';

let D = {}, live = true, mainEl = null;

function readings(x) {
  const ix = x.indices || [];
  if (!ix.length) return '';
  const above = ix.filter((i) => i.above_200w_sma).length;
  const v = ix.map((i) => i.vs_40w_sma).filter(isNum), spread = v.length ? Math.max(...v) - Math.min(...v) : null;
  const worst = ix.reduce((a, i) => (i.current_drawdown_pct < a.current_drawdown_pct ? i : a), ix[0]);
  const g = (x.growth_vs_market || {}).chg_3m_pct;
  const rows = [
    ['Secular trend', `${above} of ${ix.length} above their 200-week average`, above >= ix.length / 2 ? 'up' : 'down'],
    ['Dispersion', isNum(spread) ? `${spread >= 6 ? 'Wide' : spread >= 3 ? 'Moderate' : 'Narrow'}: ${num(spread, 1)} points between the strongest and weakest against their 40-week averages` : 'n/a', ''],
    ['Furthest from a high', `${worst.name}, ${signed(worst.current_drawdown_pct)}`, worst.current_drawdown_pct <= -20 ? 'down' : ''],
    ['Style', isNum(g) ? (g > 2 ? `Growth ahead, ${signed(g)} over 3 months` : g < -2 ? `The broad market ahead, ${signed(g)} for growth over 3 months` : 'Growth and the broad market together') : 'n/a', ''],
  ];
  return html`<section class="section" aria-labelledby="iw-h"><h2 class="t-h2" id="iw-h">What the indices say</h2><dl class="reads-dl">${rows.map(([k, v, c]) => html`<div><dt>${k}</dt><dd class="${c}">${v}</dd></div>`)}</dl></section>`;
}

function regime(x) {
  return html`<section class="section" aria-labelledby="ir-h"><div class="section-head"><div><h2 class="t-h2" id="ir-h">Index regime</h2><p class="section-sub">${clean(x.regime_summary || '')}</p></div>${miloButton('Ask Milo about the indices', { ask: 'What do the major indices say about the market cycle right now?', context: 'Markets, Indices' })}</div>
    <div class="tscroll"><table class="t"><thead><tr><th>Index</th><th>Last</th><th>1 year</th><th>3 years a year</th><th>5 years a year</th><th>10 years a year</th><th>Against 40-week</th><th>Against 200-week</th><th>Weekly RSI</th><th>From the high</th><th>Phase</th></tr></thead>
      <tbody>${(x.indices || []).map((i) => html`<tr><td><a href="#/instrument/${encodeURIComponent(i.symbol)}">${i.name}</a><br><small class="t-muted">${clean(i.note || '')}</small></td><td>${num(i.last, 0)}</td><td>${signed(i.return_1y_pct)}</td><td>${signed(i.cagr_3y_pct)}</td><td>${signed(i.cagr_5y_pct)}</td><td>${signed(i.cagr_10y_pct)}</td><td>${signed(i.vs_40w_sma)}</td><td>${signed(i.vs_200w_sma)}</td><td>${num(i.weekly_rsi, 0)}</td><td>${signed(i.current_drawdown_pct)}</td><td style="text-align:left">${capFirst(i.phase || '')}</td></tr>`)}</tbody></table></div></section>
    ${(x.growth_vs_market || {}).series ? html`<section class="section" aria-labelledby="gv-h"><h2 class="t-h2" id="gv-h">Growth against the broad market (QQQ / SPY)</h2>
      <dl class="kv" style="--kv:2"><div><dt>Ratio</dt><dd>${num(x.growth_vs_market.qqq_spy_ratio, 3)}</dd></div><div><dt>3 months</dt><dd>${signed(x.growth_vs_market.chg_3m_pct)}</dd></div></dl>
      <p>${clean(x.growth_vs_market.note || '')}</p><div class="chart-slot" data-chart="gvm"></div></section>` : ''}`;
}

function paint() {
  if (!live) return;
  const y = window.scrollY;
  draw(mainEl, html`<header class="page-head">${sectionHead('market', 'indices')}</header>
    ${D.err ? failed('The index picture', D.err, { retry: 'indices' }) : !D.x ? skeleton('lines', 5, 'Loading ten years per index') : readings(D.x)}
    <section class="section" aria-labelledby="mf-h"><h2 class="t-h2" id="mf-h">Major index funds</h2>${sectorBoard(D.board, 'Index Read')}${sectorReadBlock(D.sread)}</section>
    ${D.x ? regime(D.x) : ''}`);
  const g = (D.x || {}).growth_vs_market;
  if (g && g.series) mountCharts(mainEl, { gvm: (w) => lineChart(g.dates.map((d, i) => ({ d: String(d).slice(0, 10), c: g.series[i] })), { w, h: 190, dp: 3, label: 'QQQ against SPY', monthStep: 3 }) });
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

export async function render(main) {
  live = true; mainEl = main; D = {};
  document.title = 'Indices, Optic';
  provideContext(() => ({ view: 'indices', indices: D.x }));
  paint();
  main.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-v2-sread]');
    if (b) { D.sread = { loading: b.dataset.v2Sread }; paint(); D.sread = await loadSectorRead(b.dataset.v2Sread); paint(); return; }
    if (e.target.closest('[data-v2-sread-close]')) { D.sread = null; paint(); }
  });
  api.get('/api/indices/board', { ttl: 120000 }).then((d) => { D.board = d; }, () => { D.board = null; }).finally(() => { if (live) paint(); });
  try { D.x = await api.get('/api/indices', { ttl: 600000, timeout: 60000 }); } catch (e) { D.err = e; }
  if (live) paint();
}
export function dispose() { live = false; }
export const retry = { indices: (m, r) => render(m, r) };
