// Discover, Insiders. Who is trading what, and who the government is paying,
// from three public filing regimes: House members' trades (/api/congress),
// company insiders' Form 4s (/api/insiders/latest) and federal contract
// awards (/api/contracts). A record of what was filed, not a signal; nothing
// is ranked by how profitable it looked.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, money, compact, clean, capFirst, fullDate, shortDate, isNum, plural } from '../core/format.js';
import { closeCell, CLOSE_NOTE } from '../core/congress.js';
import { skeleton, failed } from '../ui/states.js';
import { mountCharts } from '../ui/chart.js';
import { icon } from '../ui/icons.js';
import { provideContext } from '../ui/milo.js';
import { sectionHead } from './tabs.js';

const OWNER = { SP: 'Spouse', JT: 'Joint', DC: 'Child' };
// The three filing regimes are three views of one page (owner's brief, item 14), each with its count, what
// period it covers, and whether it is complete. The symbol box filters all three.
const VIEWS = [['house', 'House trades'], ['insiders', 'Insider filings'], ['contracts', 'Federal contracts']];
const SIDES = [['', 'All'], ['buy', 'Buys'], ['sell', 'Sales'], ['other', 'Other']];
const SINCE = [[0, 'Any time'], [30, '30 days'], [90, '90 days'], [365, 'A year']];
let D = {}, Q = { ticker: '', days: 30, show: 'trades', view: 'house', side: '', member: '', since: 0 }, live = true, mainEl = null, seq = { c: 0, i: 0, k: 0 };
const dayAgo = (n) => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);
const span = (dates) => { const d = dates.filter(Boolean).sort(); return d.length ? (d[0] === d[d.length - 1] ? shortDate(d[0]) : `${shortDate(d[0])} to ${shortDate(d[d.length - 1])}`) : ''; };
// What a view covers and whether it is all of it: said above the rows, not after them.
const cover = (text, partial) => html`<p class="ins-cover ${partial ? 'is-partial' : ''}" role="status">${partial ? html`<b>Partial.</b> ` : ''}${text}</p>`;

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
  const filtered = Q.side || Q.member || Q.since;
  const coverage = cover(`${c.complete ? `Every House periodic transaction report filed this year is read (${num(c.filings_known, 0)}).` : `${num(c.filings_parsed, 0)} of ${num(c.filings_known, 0)} House reports filed this year are read so far; the rest are read in batches, so counts can rise.`}${c.latest_filed ? ` Latest disclosure filed ${fullDate(c.latest_filed)}.` : ''}`, !c.complete);
  const filters = html`<form class="op-filters ins-filters" data-v2-ins-hform>
      <div class="seg" role="group" aria-label="Transaction">${SIDES.map(([v, l]) => html`<button type="button" data-v2-ins-side="${v}" aria-pressed="${Q.side === v}">${l}</button>`)}</div>
      <label class="select"><span class="t-label">Traded within</span><select data-v2-ins-since>${SINCE.map(([v, l]) => html`<option value="${v}" ${Q.since === v ? 'selected' : ''}>${l}</option>`)}</select></label>
      <label class="field field-sm"><span class="sr">Member</span><input name="m" value="${Q.member}" placeholder="Member's name" maxlength="80" autocomplete="off"></label><button type="submit" class="btn btn-sm">Filter</button>
      ${filtered ? html`<button type="button" class="textlink" data-v2-ins-hclear>Clear filters</button>` : ''}</form>`;
  if (!trades.length) return html`${coverage}${filters}<p>${Q.ticker || filtered ? html`<b>No House trades match${Q.ticker ? ` in ${Q.ticker}` : ''}.</b> An absence of a disclosure, not evidence that nothing was traded.${Q.ticker ? " The company's own insiders file separately, under Insider filings." : ''}` : 'No House filings have been read yet.'}</p>`;
  const top = c.top_tickers || [], tmax = Math.max(...top.map((t) => t.count), 1);
  return html`${coverage}${filters}
    <div class="ins-grid"><div><h3>Disclosed trades per day</h3><p class="t-muted">${num(c.count, 0)} disclosures${filtered ? ' matching' : ''}: ${num(c.buys, 0)} buys, ${num(c.sells, 0)} sales, ${num(c.other, 0)} other, from ${num(c.members, 0)} members in ${num(c.symbols, 0)} symbols.</p>
      <div class="seg" role="group" aria-label="Chart window">${[14, 30, 90].map((d) => html`<button type="button" data-v2-ins-days="${d}" aria-pressed="${Q.days === d}">${d} days</button>`)}</div>
      ${activityChart(c)}<p class="asof">Filed a median ${plural(c.lag_median, 'day')} after the trade (longest ${c.lag_max}).${c.dates_suspect ? ` ${c.dates_suspect} trade dates look mistyped and are shown as filed.` : ''}</p></div>
    <div><h3>Most disclosed</h3><p class="t-muted">By how often a symbol appears, not by money.</p><ul class="top-list">${top.map((t) => html`<li><button type="button" class="textlink" data-v2-ins-pick="${t.ticker}">${t.ticker}</button><span class="t-muted">${t.count} filings, ${t.buys} buys, ${t.sells} sales, ${t.members} members</span><span class="tl-bar" style="--w:${(t.count / tmax) * 100}%"></span></li>`)}</ul></div></div>
    <h3>The filings <span class="t-muted">newest ${trades.length} of ${num(c.count, 0)}, traded ${span(trades.filter((t) => !t.date_suspect).map((t) => t.traded_iso))}</span></h3>
    <div class="tscroll"><table class="t"><thead><tr><th>Member</th><th>Owner</th><th>Symbol</th><th>Transaction</th><th>Amount</th><th>Traded</th>${Q.ticker ? html`<th>Close that day</th>` : ''}<th>Filed</th><th><span class="sr">Filing</span></th></tr></thead>
      <tbody>${trades.map((t) => html`<tr><td>${t.member}<br><small class="t-muted">${t.district || ''}</small></td><td>${OWNER[t.owner] || 'Self'}</td><td>${t.ticker ? html`<button type="button" class="textlink" data-v2-ins-pick="${t.ticker}">${t.ticker}</button>` : ''}</td>
        <td class="${t.side === 'buy' ? 'up' : t.side === 'sell' ? 'down' : ''}">${capFirst(t.transaction || '')}${t.description ? html`<br><small class="t-muted">${clean(t.description)}</small>` : ''}</td>
        <td>${money(t.amount_low, 0)} to ${money(t.amount_high, 0)}</td><td>${t.traded_iso ? fullDate(t.traded_iso) : t.traded}${t.date_suspect ? html` <small class="t-muted">as filed</small>` : ''}</td>${Q.ticker ? html`<td>${closeCell(t)}</td>` : ''}
        <td>${t.filed ? fullDate(t.filed) : ''}${isNum(t.disclosure_lag_days) ? html`<br><small class="${t.disclosure_lag_days > 45 ? 'down' : 't-muted'}">${plural(t.disclosure_lag_days, 'day')} after the trade${t.disclosure_lag_days > 45 ? ', past the 45-day limit' : ''}</small>` : ''}</td><td>${/^https?:/.test(t.source_url || '') ? html`<a href="${t.source_url}" target="_blank" rel="noopener">Filing</a>` : ''}</td></tr>`)}</tbody></table></div>
    <p class="asof">${clean(c.caveat || '')}${Q.ticker ? ` ${CLOSE_NOTE}` : ''} Source: House Clerk.</p>`;
}

function filings() {
  const f = D.i;
  if (D.iErr) return failed('Insider filings', D.iErr, { retry: 'insiders' });
  if (!f) return skeleton('rows', 4, 'Reading the latest Form 4s');
  if (!f.available) return html`<p>${clean(f.reason || 'EDGAR did not answer.')}</p>`;
  const rows = f.rows || [];
  const edgar = (r) => (/^https?:/.test(r.index_url || '') ? html`<a class="textlink" href="${r.index_url}" target="_blank" rel="noopener">Form ${r.form || '4'}${r.amendment ? ', amendment' : ''}</a>` : `Form ${r.form || '4'}`);
  const pair = (r) => (r.may_amend ? html`<br><small class="t-muted">May amend the filing of ${shortDate(String(r.may_amend.filed_at || '').slice(0, 10))}, the same trade listed below</small>` : r.may_be_amended_by ? html`<br><small class="t-muted">A Form 4/A filed ${shortDate(String(r.may_be_amended_by.filed_at || '').slice(0, 10))} may amend this</small>` : '');
  return html`<div class="cluster"><div class="seg" role="group" aria-label="Show">${[['trades', 'Buys and sells'], ['buys', 'Buys only'], ['all', 'Everything filed']].map(([k, l]) => html`<button type="button" data-v2-ins-show="${k}" aria-pressed="${Q.show === k}">${l}</button>`)}</div><button type="button" class="btn btn-sm" data-v2-ins-refresh>Refresh</button></div>
    ${cover(`${Q.ticker ? `${Q.ticker} only: that company's own Form 4 history. ` : 'The newest Form 4s filed with the SEC, newest filing first. '}${num(f.matched, 0)} transactions matching from ${num(f.filings_read, 0)} filings read${f.filings_unread ? `; ${num(f.filings_unread, 0)} are still to read and are added as they are` : ''}.${rows.length ? ` Showing the newest ${rows.length}${rows.length < f.matched ? ` of ${num(f.matched, 0)}` : ''}, filed ${span(rows.map((r) => String(r.filed_at || '').slice(0, 10)))}.` : ''}${f.amendments ? ` ${f.amendments} ${f.amendments === 1 ? 'is' : 'are'} from amended filings (Form 4/A), shown beside what they may correct, not merged.` : ''}`, f.filings_unread > 0)}
    ${f.note ? html`<p class="stale">${clean(f.note)}</p>` : ''}
    ${rows.length ? html`<div class="tscroll"><table class="t ins-t"><thead><tr><th scope="col">Symbol</th><th scope="col">Insider</th><th scope="col">Transaction</th><th scope="col" class="ins-wide">Shares</th><th scope="col" class="ins-wide">Price</th><th scope="col" class="ins-wide">Value</th><th scope="col">Traded</th><th scope="col">Filed</th><th scope="col" class="ins-wide">Filing</th></tr></thead>
      <tbody>${rows.map((r, n) => html`<tr class="${r.amendment ? 'is-amend' : ''}"><td>${r.ticker ? html`<a href="#/${r.ticker}">${r.ticker}</a>` : html`<span class="t-muted">no ticker</span>`}<br><small class="t-muted">${r.issuer || ''}</small><button type="button" class="icon-btn ins-rowbtn" data-v2-ins-row="${n}" aria-expanded="false" aria-controls="ins-rd-${n}" aria-label="Details of this filing">${icon('chev')}</button></td>
        <td>${r.insider}<br><small class="t-muted">${(r.roles || []).join(', ')}</small></td><td class="${r.is_purchase ? 'up' : r.code === 'S' ? 'down' : ''}" title="${r.code_note || ''}">${r.code_label || r.code}${r.amendment ? html`<br><small class="t-muted">amended filing</small>` : ''}</td>
        <td class="ins-wide">${compact(r.shares)}</td><td class="ins-wide">${isNum(r.price) ? money(r.price) : ''}</td><td class="ins-wide">${isNum(r.value) ? `$${compact(r.value)}` : ''}</td><td>${r.date ? fullDate(String(r.date).slice(0, 10)) : ''}</td><td>${new Date(r.filed_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' })} ET${pair(r)}</td><td class="ins-wide">${edgar(r)}</td></tr>
        <tr class="ins-detail" id="ins-rd-${n}" hidden><td colspan="9"><dl class="kv"><div><dt>Shares</dt><dd>${compact(r.shares)}</dd></div><div><dt>Price</dt><dd>${isNum(r.price) ? money(r.price) : 'Not given'}</dd></div><div><dt>Value</dt><dd>${isNum(r.value) ? `$${compact(r.value)}` : 'Not given'}</dd></div><div><dt>Filing</dt><dd>${edgar(r)}</dd></div></dl>${r.code_note ? html`<p class="t-muted">${clean(r.code_note)}</p>` : ''}<p class="t-muted">Accession ${r.accession || ''}</p></td></tr>`)}</tbody></table></div>`
    : html`<p class="quiet">${Q.show === 'buys' ? 'No open-market purchases in what has been read.' : 'Nothing matching in what has been read.'}</p>`}
    <p class="asof">${clean(f.blind_spot || '')} ${clean(f.method || '')}</p>`;
}

function contracts() {
  const k = D.k;
  if (D.kErr) return failed('Federal contracts', D.kErr, { retry: 'contracts' });
  if (!k) return skeleton('rows', 3, 'Reading USAspending');
  if (!k.available && k.reason) return html`<p>${clean(k.reason)}</p>`;
  const aw = k.awards || [];
  return html`${cover(`${k.scope === 'company' && k.matched ? `Awarded to ${k.recipient}, $${compact(k.amount_12m)} over the last 12 months.` : k.scope === 'company' ? clean(k.reason || 'No exact recipient match for this company.') : `The largest new awards in the last ${k.days} days, newest first.`}${aw.length ? ` Showing ${aw.length}, awarded ${span(aw.map((a) => a.awarded))}.` : ''}`, false)}
    ${(k.awards || []).length ? html`<div class="tscroll"><table class="t"><thead><tr><th>Awarded</th><th>Recipient</th><th>Agency</th><th>Amount</th><th><span class="sr">Award</span></th></tr></thead>
      <tbody>${k.awards.map((a) => html`<tr><td>${fullDate(a.awarded)}${a.start && a.start > a.awarded ? html`<br><small class="t-muted">work from ${shortDate(a.start)}</small>` : ''}</td><td>${a.recipient}<br><small class="t-muted">${clean(a.description || '')}${a.state ? `, ${a.state}` : ''}</small></td><td>${a.agency}${a.sub_agency && a.sub_agency !== a.agency ? html`<br><small class="t-muted">${a.sub_agency}</small>` : ''}</td><td>$${compact(a.amount)}</td><td>${/^https?:/.test(a.url || '') ? html`<a href="${a.url}" target="_blank" rel="noopener">Award</a>` : ''}</td></tr>`)}</tbody></table></div>` : ''}
    <p class="asof">${clean(k.caveat || '')} <a href="https://www.usaspending.gov/" target="_blank" rel="noopener">USAspending ${icon('out')}</a></p>`;
}

// A view's count once it has loaded: what it holds after the filters, not the whole archive.
function count(v) {
  const x = v === 'house' ? D.c : v === 'insiders' ? D.i : D.k;
  const err = v === 'house' ? D.cErr : v === 'insiders' ? D.iErr : D.kErr;
  if (err) return 'Failed';
  if (!x) return 'Loading';
  if (v === 'house') return `${num(x.count || 0, 0)}${x.complete ? '' : '+'}`;
  if (v === 'insiders') return x.available === false ? 'Unavailable' : `${num(x.matched || 0, 0)}${x.filings_unread ? '+' : ''}`;
  return x.available === false && x.reason ? 'None' : String((x.awards || []).length);
}

function paint() {
  if (!live) return;
  const y = window.scrollY;
  draw(mainEl, html`<header class="page-head">${sectionHead('discover', 'insiders')}
      <p class="section-sub">Who is trading what, and who the government is paying, from three filing regimes that all have to be public. A record of what was filed, not a signal: nothing here is ranked by how profitable it looked.</p></header>
    <form class="op-filters" data-v2-ins-form role="search" style="margin-top:18px"><label class="field field-sm"><span class="sr">Symbol</span><input name="t" value="${Q.ticker}" placeholder="NVDA, or blank for everything" maxlength="10" autocomplete="off"></label><button type="submit" class="btn btn-sm">Show filings</button>${Q.ticker ? html`<button type="button" class="btn btn-sm" data-v2-ins-reset>Clear</button>` : ''}</form>
    <div class="gtabs ins-views" role="tablist" aria-label="Filings" style="--n:3">${VIEWS.map(([v, l]) => html`<button type="button" role="tab" id="iv-${v}" aria-controls="iv-panel" aria-selected="${Q.view === v}" tabindex="${Q.view === v ? 0 : -1}" data-v2-ins-view="${v}">${l}<span class="iv-n">${count(v)}</span></button>`)}</div>
    <section class="section first" id="iv-panel" role="tabpanel" aria-labelledby="iv-${Q.view}">
      ${Q.view === 'house' ? html`<h2 class="t-h2">House trades${Q.ticker ? ` in ${Q.ticker}` : ''}</h2>${house()}` : Q.view === 'insiders' ? html`<h2 class="t-h2">Insider filings${Q.ticker ? ` in ${Q.ticker}` : ''}</h2>${filings()}` : html`<h2 class="t-h2">Federal contracts${Q.ticker ? ` for ${Q.ticker}` : ''}</h2>${contracts()}`}</section>`);
  if (Q.view === 'house' && D.c && (D.c.activity || []).length) mountCharts(mainEl, { cg: activitySvg(D.c) });
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

async function loadC() { const my = ++seq.c; D.c = null; D.cErr = null; paint(); const q = new URLSearchParams({ limit: 60, activity_days: Q.days }); if (Q.ticker) q.set('ticker', Q.ticker); if (Q.side) q.set('side', Q.side); if (Q.member) q.set('member', Q.member); if (Q.since) q.set('since', dayAgo(Q.since)); try { const d = await api.get(`/api/congress?${q}`, { ttl: 300000 }); if (my === seq.c) D.c = d; } catch (e) { if (my === seq.c) D.cErr = e; } if (live) paint(); }
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
  const v = (route.params || {}).view; if (VIEWS.some(([x]) => x === v)) Q.view = v;
  document.title = 'Insiders, Optic';
  provideContext(() => ({ view: 'insiders', insiders: { ticker: Q.ticker, house: D.c ? { count: D.c.count, top: D.c.top_tickers } : null } }));
  main.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-ins-pick]'))) { Q.ticker = Q.ticker === b.dataset.v2InsPick ? '' : b.dataset.v2InsPick; loadAll(); return; }
    if ((b = t('[data-v2-ins-view]'))) { Q.view = b.dataset.v2InsView; paint(); const again = mainEl.querySelector(`[data-v2-ins-view="${Q.view}"]`); if (again) again.focus(); return; }
    if ((b = t('[data-v2-ins-side]'))) { Q.side = b.dataset.v2InsSide; loadC(); return; }
    if (t('[data-v2-ins-hclear]')) { Q.side = ''; Q.member = ''; Q.since = 0; loadC(); return; }
    if ((b = t('[data-v2-ins-days]'))) { Q.days = Number(b.dataset.v2InsDays); loadC(); return; }
    if ((b = t('[data-v2-ins-show]'))) { Q.show = b.dataset.v2InsShow; loadI(); return; }
    if (t('[data-v2-ins-refresh]')) { loadI(true); return; }
    if ((b = t('[data-v2-ins-row]'))) { const r = document.getElementById(b.getAttribute('aria-controls')); const open = b.getAttribute('aria-expanded') !== 'true'; if (r) r.hidden = !open; b.setAttribute('aria-expanded', String(open)); return; }
    if (t('[data-v2-ins-reset]')) { Q.ticker = ''; loadAll(); }
  });
  main.addEventListener('submit', (e) => {
    const h = e.target.closest('[data-v2-ins-hform]');
    if (h) { e.preventDefault(); Q.member = String(h.m.value || '').trim(); loadC(); return; }
    const f = e.target.closest('[data-v2-ins-form]'); if (!f) return; e.preventDefault(); Q.ticker = String(f.t.value || '').trim().toUpperCase(); loadAll();
  });
  main.addEventListener('change', (e) => { const s = e.target.closest('[data-v2-ins-since]'); if (s) { Q.since = Number(s.value) || 0; loadC(); } });
  main.addEventListener('keydown', (e) => {
    const tab = e.target.closest('[data-v2-ins-view]'); if (!tab) return;
    const i = VIEWS.findIndex(([v]) => v === tab.dataset.v2InsView), n = VIEWS.length;
    const to = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i - 1 + n) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1;
    if (to < 0) return; e.preventDefault(); Q.view = VIEWS[to][0]; paint(); const again = mainEl.querySelector(`[data-v2-ins-view="${Q.view}"]`); if (again) again.focus();
  });
  loadAll();
}
export function dispose() { live = false; }
export const retry = { congress: () => loadC(), insiders: () => loadI(), contracts: () => loadK() };
void signed;
