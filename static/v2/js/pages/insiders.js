// Discover, Insiders. Who is trading what, and who the government is paying,
// from three public filing regimes: House members' trades (/api/congress),
// company insiders' Form 4s (/api/insiders/latest) and federal contract
// awards (/api/contracts). A record of what was filed, not a signal; nothing
// is ranked by how profitable it looked.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, money, compact, clean, capFirst, fullDate, shortDate, isNum } from '../core/format.js';
import { skeleton, failed } from '../ui/states.js';
import { mountCharts } from '../ui/chart.js';
import { icon } from '../ui/icons.js';
import { provideContext } from '../ui/milo.js';
import { groupTabs } from './tabs.js';

const OWNER = { SP: 'Spouse', JT: 'Joint', DC: 'Child' };
let D = {}, Q = { ticker: '', days: 30, show: 'trades' }, live = true, mainEl = null, seq = { c: 0, i: 0, k: 0 };

function activityChart(c) {
  const act = c.activity || [];
  if (!act.length || !act.some((a) => a.buys + a.sells + a.other)) return html`<p class="quiet">Nothing to chart in this window.</p>`;
  return html`<div class="chart-slot" data-chart="cg"></div>
    <p class="legend-line"><span><i class="lb"></i>Buys</span><span><i class="lo"></i>Other</span><span><i class="ls"></i>Sales</span></p>`;
}
// Drawn at the slot's own width, so the date ticks stay 12px on a phone.
function activitySvg(c) {
  return (w) => {
    const act = c.activity || [];
    const W = w, H = 150, l = 4, r = 4, b = 22, max = Math.max(...act.map((a) => a.buys + a.sells + a.other)) || 1, bw = (W - l - r) / act.length;
    const peak = act.reduce((p, a) => (a.buys + a.sells + a.other > p.buys + p.sells + p.other ? a : p), act[0]);
    const bars = act.map((a, i) => { const x = l + i * bw; let y = H - b; const seg = (v, cls) => { const h = (v / max) * (H - b - 8); y -= h; return v ? `<rect class="${cls}" x="${(x + 1).toFixed(1)}" y="${y.toFixed(1)}" width="${Math.max(1, bw - 2).toFixed(1)}" height="${h.toFixed(1)}"><title>${a.date}: ${a.buys} buys, ${a.sells} sales, ${a.other} other</title></rect>` : ''; }; return seg(a.buys, 'cb') + seg(a.other, 'co') + seg(a.sells, 'cs'); }).join('');
    const sum = `Disclosed trades per day over ${act.length} days; tallest bar ${peak.buys + peak.sells + peak.other} on ${peak.date}.`;
    return `<svg class="cg-chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${sum}">${bars}<text class="ax" x="${l}" y="${H - 6}">${shortDate(act[0].date)}</text><text class="ax" x="${W - r}" y="${H - 6}" text-anchor="end">${shortDate(act[act.length - 1].date)}</text></svg>`;
  };
}

function house() {
  const c = D.c;
  if (D.cErr) return failed('House trades', D.cErr, { retry: 'congress' });
  if (!c) return skeleton('rows', 4, "Reading the Clerk's filings");
  const trades = c.trades || [];
  if (!trades.length) return html`<p>${Q.ticker ? html`<b>No House trades in ${Q.ticker}.</b> An absence of a disclosure, not evidence that nothing was traded. The company's own insiders file separately, below.` : 'No House filings have been read yet.'}</p>`;
  const top = c.top_tickers || [], tmax = Math.max(...top.map((t) => t.count), 1);
  return html`<div class="ins-grid"><div><h3>Disclosed trades per day</h3><p class="t-muted">${c.count} disclosures, ${c.buys} buys, ${c.sells} sales, ${c.other} other, ${c.members} members, ${c.symbols} symbols.</p>
      <div class="seg" role="group" aria-label="Window">${[14, 30, 90].map((d) => html`<button type="button" data-v2-ins-days="${d}" aria-pressed="${Q.days === d}">${d} days</button>`)}</div>
      ${activityChart(c)}<p class="asof">Filed a median ${c.lag_median} days after the trade (longest ${c.lag_max}).${c.dates_suspect ? ` ${c.dates_suspect} trade dates look mistyped and are shown as filed.` : ''}</p></div>
    <div><h3>Most disclosed</h3><p class="t-muted">By how often a symbol appears, not by money.</p><ul class="top-list">${top.map((t) => html`<li><button type="button" class="textlink" data-v2-ins-pick="${t.ticker}">${t.ticker}</button><span class="t-muted">${t.count} filings, ${t.buys} buys, ${t.sells} sales, ${t.members} members</span><span class="tl-bar" style="--w:${(t.count / tmax) * 100}%"></span></li>`)}</ul></div></div>
    <h3>The filings <span class="t-muted">newest ${trades.length} of ${c.count}</span></h3>
    <div class="tscroll"><table class="t"><thead><tr><th>Member</th><th>Owner</th><th>Symbol</th><th>Transaction</th><th>Amount</th><th>Traded</th><th>Filed after</th><th><span class="sr">Filing</span></th></tr></thead>
      <tbody>${trades.map((t) => html`<tr><td>${t.member}<br><small class="t-muted">${t.district || ''}</small></td><td>${OWNER[t.owner] || 'Self'}</td><td>${t.ticker ? html`<button type="button" class="textlink" data-v2-ins-pick="${t.ticker}">${t.ticker}</button>` : ''}</td>
        <td class="${t.side === 'buy' ? 'up' : t.side === 'sell' ? 'down' : ''}">${capFirst(t.transaction || '')}${t.description ? html`<br><small class="t-muted">${clean(t.description)}</small>` : ''}</td>
        <td>${money(t.amount_low, 0)} to ${money(t.amount_high, 0)}</td><td>${t.traded_iso ? fullDate(t.traded_iso) : t.traded}${t.date_suspect ? html` <small class="t-muted">as filed</small>` : ''}</td>
        <td class="${t.disclosure_lag_days > 45 ? 'down' : ''}">${isNum(t.disclosure_lag_days) ? `${t.disclosure_lag_days} days` : ''}</td><td>${/^https?:/.test(t.source_url || '') ? html`<a href="${t.source_url}" target="_blank" rel="noopener">Filing</a>` : ''}</td></tr>`)}</tbody></table></div>
    <p class="asof">${clean(c.caveat || '')} ${c.complete ? 'The whole year is read.' : `Read so far: ${c.filings_parsed} of ${c.filings_known} known filings this year.`} Latest disclosure ${fullDate(c.latest_filed)}. Source: House Clerk.</p>`;
}

function filings() {
  const f = D.i;
  if (D.iErr) return failed('Insider filings', D.iErr, { retry: 'insiders' });
  if (!f) return skeleton('rows', 4, 'Reading the latest Form 4s');
  if (!f.available) return html`<p>${clean(f.reason || 'EDGAR did not answer.')}</p>`;
  const rows = f.rows || [];
  return html`<div class="cluster"><div class="seg" role="group" aria-label="Show">${[['trades', 'Buys and sells'], ['buys', 'Buys only'], ['all', 'Everything filed']].map(([k, l]) => html`<button type="button" data-v2-ins-show="${k}" aria-pressed="${Q.show === k}">${l}</button>`)}</div><button type="button" class="btn btn-sm" data-v2-ins-refresh>Refresh</button></div>
    ${f.note ? html`<p class="stale">${clean(f.note)}</p>` : ''}
    <p class="t-muted">${Q.ticker ? `${Q.ticker} only: that company's own Form 4 history. ` : ''}${f.matched} matching from ${f.filings_read} filings read${f.filings_unread ? `, ${f.filings_unread} still to read` : ''}.</p>
    ${rows.length ? html`<div class="tscroll"><table class="t"><thead><tr><th>Filed</th><th>Symbol</th><th>Insider</th><th>Transaction</th><th>Shares</th><th>Price</th><th>Value</th><th>Trade date</th></tr></thead>
      <tbody>${rows.map((r) => html`<tr><td>${new Date(r.filed_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</td><td>${r.ticker ? html`<a href="#/${r.ticker}">${r.ticker}</a>` : html`<span class="t-muted">no ticker</span>`}<br><small class="t-muted">${r.issuer || ''}</small></td>
        <td>${r.insider}<br><small class="t-muted">${(r.roles || []).join(', ')}</small></td><td class="${r.is_purchase ? 'up' : r.code === 'S' ? 'down' : ''}" title="${r.code_note || ''}">${r.code_label || r.code}</td>
        <td>${compact(r.shares)}</td><td>${isNum(r.price) ? money(r.price) : ''}</td><td>${isNum(r.value) ? `$${compact(r.value)}` : ''}</td><td>${r.date ? fullDate(String(r.date).slice(0, 10)) : ''}</td></tr>`)}</tbody></table></div>`
    : html`<p class="quiet">${Q.show === 'buys' ? 'No open-market purchases in what has been read.' : 'Nothing matching in what has been read.'}</p>`}
    <p class="asof">${clean(f.blind_spot || '')} ${clean(f.method || '')}</p>`;
}

function contracts() {
  const k = D.k;
  if (D.kErr) return failed('Federal contracts', D.kErr, { retry: 'contracts' });
  if (!k) return skeleton('rows', 3, 'Reading USAspending');
  if (!k.available && k.reason) return html`<p>${clean(k.reason)}</p>`;
  return html`<p class="t-muted">${k.scope === 'company' && k.matched ? `Awarded to ${k.recipient}, $${compact(k.amount_12m)} over the last 12 months.` : k.scope === 'company' ? clean(k.reason || 'No exact recipient match for this company.') : `The largest new awards in the last ${k.days} days, newest first.`}</p>
    ${(k.awards || []).length ? html`<div class="tscroll"><table class="t"><thead><tr><th>Awarded</th><th>Recipient</th><th>Agency</th><th>Amount</th><th><span class="sr">Award</span></th></tr></thead>
      <tbody>${k.awards.map((a) => html`<tr><td>${fullDate(a.awarded)}${a.start && a.start > a.awarded ? html`<br><small class="t-muted">work from ${shortDate(a.start)}</small>` : ''}</td><td>${a.recipient}<br><small class="t-muted">${clean(a.description || '')}${a.state ? `, ${a.state}` : ''}</small></td><td>${a.agency}${a.sub_agency && a.sub_agency !== a.agency ? html`<br><small class="t-muted">${a.sub_agency}</small>` : ''}</td><td>$${compact(a.amount)}</td><td>${/^https?:/.test(a.url || '') ? html`<a href="${a.url}" target="_blank" rel="noopener">Award</a>` : ''}</td></tr>`)}</tbody></table></div>` : ''}
    <p class="asof">${clean(k.caveat || '')} <a href="https://www.usaspending.gov/" target="_blank" rel="noopener">USAspending ${icon('out')}</a></p>`;
}

function paint() {
  if (!live) return;
  const y = window.scrollY;
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">Insiders</h1>${groupTabs('discover', 'insiders')}
      <p class="section-sub">Who is trading what, and who the government is paying, from three filing regimes that all have to be public. A record of what was filed, not a signal: nothing here is ranked by how profitable it looked.</p></header>
    <form class="op-filters" data-v2-ins-form role="search" style="margin-top:18px"><label class="field field-sm"><span class="sr">Symbol</span><input name="t" value="${Q.ticker}" placeholder="NVDA, or blank for everything" maxlength="10" autocomplete="off"></label><button type="submit" class="btn btn-sm">Show filings</button>${Q.ticker ? html`<button type="button" class="btn btn-sm" data-v2-ins-reset>Clear</button>` : ''}</form>
    <section class="section first" aria-labelledby="ih-h"><h2 class="t-h2" id="ih-h">House trades${Q.ticker ? ` in ${Q.ticker}` : ''}</h2>${house()}</section>
    <section class="section" aria-labelledby="if-h"><h2 class="t-h2" id="if-h">Insider filings</h2>${filings()}</section>
    <section class="section" aria-labelledby="fc-h"><h2 class="t-h2" id="fc-h">Federal contracts</h2>${contracts()}</section>`);
  if (D.c && (D.c.activity || []).length) mountCharts(mainEl, { cg: activitySvg(D.c) });
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

async function loadC() { const my = ++seq.c; D.c = null; D.cErr = null; paint(); const q = new URLSearchParams({ limit: 60, activity_days: Q.days }); if (Q.ticker) q.set('ticker', Q.ticker); try { const d = await api.get(`/api/congress?${q}`, { ttl: 300000 }); if (my === seq.c) D.c = d; } catch (e) { if (my === seq.c) D.cErr = e; } if (live) paint(); }
async function loadI(force, round = 0) {
  const my = round ? seq.i : ++seq.i; if (!round) { D.i = null; D.iErr = null; paint(); }
  const q = new URLSearchParams({ limit: 40, show: Q.show }); if (Q.ticker) q.set('ticker', Q.ticker); if (force) q.set('force', 'true');
  try { const d = await api.get(`/api/insiders/latest?${q}`, { ttl: force || round ? 0 : 120000, force: force || round > 0, timeout: 60000 }); if (my !== seq.i) return; D.i = d;
    // one company: keep reading its history while filings remain, as the classic page does
    if (Q.ticker && d.filings_unread > 0 && round < 9 && live) setTimeout(() => loadI(false, round + 1), 600);
  } catch (e) { if (my === seq.i && !round) D.iErr = e; }
  if (live) paint();
}
async function loadK() { const my = ++seq.k; D.k = null; D.kErr = null; paint(); const q = new URLSearchParams({ limit: 12 }); if (Q.ticker) q.set('ticker', Q.ticker); try { const d = await api.get(`/api/contracts?${q}`, { ttl: 600000, timeout: 30000 }); if (my === seq.k) D.k = d; } catch (e) { if (my === seq.k) D.kErr = e; } if (live) paint(); }
const loadAll = () => { loadC(); loadI(); loadK(); };

export async function render(main, route) {
  live = true; mainEl = main; D = {};
  Q.ticker = String((route.params || {}).symbol || '').toUpperCase();
  document.title = 'Insiders, Optic';
  provideContext(() => ({ view: 'insiders', insiders: { ticker: Q.ticker, house: D.c ? { count: D.c.count, top: D.c.top_tickers } : null } }));
  main.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-ins-pick]'))) { Q.ticker = Q.ticker === b.dataset.v2InsPick ? '' : b.dataset.v2InsPick; loadAll(); return; }
    if ((b = t('[data-v2-ins-days]'))) { Q.days = Number(b.dataset.v2InsDays); loadC(); return; }
    if ((b = t('[data-v2-ins-show]'))) { Q.show = b.dataset.v2InsShow; loadI(); return; }
    if (t('[data-v2-ins-refresh]')) { loadI(true); return; }
    if (t('[data-v2-ins-reset]')) { Q.ticker = ''; loadAll(); }
  });
  main.addEventListener('submit', (e) => { const f = e.target.closest('[data-v2-ins-form]'); if (!f) return; e.preventDefault(); Q.ticker = String(f.t.value || '').trim().toUpperCase(); loadAll(); });
  loadAll();
}
export function dispose() { live = false; }
export const retry = { congress: () => loadC(), insiders: () => loadI(), contracts: () => loadK() };
void num; void signed;
