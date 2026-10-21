// Earnings this week, at #/earnings (the classic app's address for the same page). Who reports, by day, among
// the widely followed names the server checks (/api/earnings-week), with the analysts' EPS and revenue
// consensus, and the reader's own followed names marked. Grouped by day only: the feed publishes a date and no
// session, so a "before the open" column would be invented (the API's own session_note says so).
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, compact, clean, ago, isNum } from '../core/format.js';
import { skeleton, failed, how } from '../ui/states.js';
import { provideContext } from '../ui/milo.js';

let offset = 0, D = null, err = null, live = true, mainEl = null, seq = 0;

function row(r) {
  const mine = store.isFollowed(r.ticker);
  const eps = isNum(r.eps_consensus) ? html`EPS <b>${num(r.eps_consensus)}</b>` : html`<span class="t-muted">No EPS estimate</span>`;
  const rev = isNum(r.revenue_consensus) ? html`, revenue <b>$${compact(r.revenue_consensus)}</b>` : '';
  return html`<li class="ew-row"><a class="ew-name" href="#/${encodeURIComponent(r.ticker)}/earnings"><b class="ew-tick">${r.ticker}</b> <span>${r.name || ''}</span></a>
    <span class="ew-est">${eps}${rev}</span>
    <span class="ew-meta">${r.major ? html`<span>Index-moving</span>` : ''}${mine ? html`<span>You follow it</span>` : ''}${r.confirmed === false ? html`<span class="ew-unconf">Date not confirmed</span>` : ''}</span></li>`;
}

function body() {
  if (err) return failed('The earnings calendar', err, { retry: 'week' });
  if (!D) return skeleton('rows', 6, 'Loading the week');
  if (D.available === false) return html`<p>${clean(D.reason || 'The earnings calendar is not available right now.')}</p>`;
  const days = D.days || [];
  const scanned = Number(D.universe || D.checked) || 0;
  return html`<p class="section-sub">${D.week_label}: <b>${num(D.total, 0)}</b> reporting${scanned ? ` among the ${num(scanned, 0)} widely followed names Optic checks` : ''}${D.majors ? `, ${num(D.majors, 0)} of them index-moving` : ''}. Open one for its earnings analysis.</p>
    <div class="ew-days">${days.map((d) => html`<section class="ew-day${d.is_today ? ' is-today' : ''}${d.is_past ? ' is-past' : ''}" aria-labelledby="ew-${d.date}">
      <h2 class="ew-dh" id="ew-${d.date}">${d.day} ${d.day_number}${d.is_today ? html` <span class="ew-today">Today</span>` : ''}<span class="ew-count">${d.count ? `${d.count} reporting` : 'None'}</span></h2>
      ${(d.rows || []).length ? html`<ul class="ew-list">${d.rows.map(row)}</ul>` : html`<p class="t-muted ew-none">Nothing scheduled among the names checked.</p>`}</section>`)}</div>
    <p class="asof">${D.generated_at ? `Calendar read ${ago(D.generated_at)}. ` : ''}Dates and consensus from Yahoo Finance.${D.failed ? ` ${D.failed} companies could not be read.` : ''}</p>
    ${how(html`<p>${clean(D.session_note || '')}</p><p>${clean(D.method || '')}</p>`)}`;
}

function paint() {
  if (!live || !mainEl) return;
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">Earnings this week</h1>
      <div class="seg" role="group" aria-label="Week">${[[-1, 'Last week'], [0, 'This week'], [1, 'Next week']].map(([k, l]) => html`<button type="button" data-v2-ew="${k}" aria-pressed="${offset === k}">${l}</button>`)}</div></header>
    <div aria-live="polite" aria-busy="${D ? 'false' : 'true'}">${body()}</div>`);
}

async function load() {
  const my = ++seq; D = null; err = null; paint();
  try {
    const d = await api.get(`/api/earnings-week?offset=${offset}`, { ttl: 600000, timeout: 90000 });
    if (!live || my !== seq) return;
    D = d;
  } catch (e) { if (!live || my !== seq) return; err = e; }
  paint();
}

export async function render(main, route) {
  live = true; mainEl = main;
  const o = Number((route && route.params && route.params.week) || 0);
  offset = [-1, 0, 1].includes(o) ? o : 0;
  document.title = 'Earnings this week, Optic';
  provideContext(() => ({ view: 'earningsweek', earnings_week: D && D.available !== false ? { week: D.week_label, days: (D.days || []).map((d) => ({ day: d.date, tickers: (d.rows || []).map((r) => r.ticker) })) } : null }));
  main.addEventListener('click', (e) => {
    const b = e.target.closest('[data-v2-ew]'); if (!b) return;
    offset = Number(b.dataset.v2Ew);
    try { history.replaceState(null, '', offset ? `#/earnings?week=${offset}` : '#/earnings'); } catch (x) { /* a sandboxed frame */ }
    load();
  });
  load();
}
export function dispose() { live = false; }
export const retry = { week: () => load() };
