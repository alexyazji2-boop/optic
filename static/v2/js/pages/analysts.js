// Discover, Analysts. What each firm did to its rating and price target:
// across the covered names (/api/analysts/latest, the server's own feed) or
// for one symbol (/api/analysts/{T}). Filter by action, rating and window.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, clean, ago } from '../core/format.js';
import { skeleton, failed } from '../ui/states.js';
import { table, nextSort } from '../ui/table.js';
import { provideContext } from '../ui/milo.js';
import { sectionHead } from './tabs.js';

const SHOWS = [['', 'All'], ['upgrades', 'Upgrades'], ['downgrades', 'Downgrades'], ['initiations', 'Initiations'], ['raised', 'Target raised'], ['lowered', 'Target lowered']];
const RATINGS = [['', 'Any'], ['buy', 'Buy'], ['hold', 'Hold'], ['sell', 'Sell']];
let Q = { show: '', rating: '', days: 7, ticker: '' }, D = {}, live = true, mainEl = null, seq = 0, sort = { key: 'at', dir: 'desc' };

const COLS = [
  { key: 'at', label: 'Date', sort: (r) => Date.parse(r.at), cell: (r) => html`${new Date(r.at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}<br><small class="t-muted">${ago(r.at)}</small>` },
  { key: 'ticker', label: 'Symbol', cell: (r) => html`<a href="#/${r.ticker}">${r.ticker}</a>` },
  { key: 'firm', label: 'Analyst', cell: (r) => r.firm },
  { key: 'prior_target', label: 'Prior target', num: true, hideOnPhone: true, cell: (r) => (r.action === 'init' ? 'New' : r.prior_target ? num(r.prior_target) : 'Not given') },
  { key: 'target', label: 'Target', num: true, cell: (r) => html`${r.target ? num(r.target) : 'Not given'}${r.target_action === 'Raises' ? html` <span class="up">↑</span>` : r.target_action === 'Lowers' ? html` <span class="down">↓</span>` : ''}` },
  { key: 'action_label', label: 'Action', cell: (r) => html`<span class="${r.action === 'up' ? 'up' : r.action === 'down' ? 'down' : ''}">${r.action_label || r.action}</span>` },
  { key: 'rating', label: 'Rating', cell: (r) => html`<span class="rt rt-${r.rating_class || ''}" title="${r.prior_rating && r.prior_rating !== r.rating ? `From ${r.prior_rating}` : ''}">${r.rating || ''}</span>` },
];

function body() {
  const d = D.d;
  if (D.err) return failed('The analyst actions', D.err, { retry: 'analysts' });
  if (!d) return skeleton('rows', 6, 'Loading analyst actions');
  const rows = d.rows || [];
  const lead = Q.ticker ? (rows.length ? `${d.count ?? rows.length} actions on ${Q.ticker}.` : `Nothing on ${Q.ticker} matching. A longer window, or All under Show, may find more.`)
    : d.covered === 0 ? 'Analyst actions are loading for the first time. They appear here when they finish.'
      : rows.length ? `${d.count} actions in the last ${Q.days} days across ${d.covered} names, newest first.${d.count > rows.length ? ` Showing the newest ${rows.length}.` : ''}` : `Nothing matching in the last ${Q.days} days, across ${d.covered} names.`;
  // how old the list is, and what its dates are: when the firm's action was recorded, not when it was read
  const age = d.read_at || d.generated_at;
  return html`<p class="section-sub">${lead}</p>
    ${table(rows, COLS, { id: 'an', sort, caption: 'Analyst actions' })}<p class="asof">${age ? `Read ${ago(age)}. ` : ''}Each date is when Yahoo Finance recorded the firm's action, usually the day it was announced. ${clean(d.method || '')}</p>`;
}

function paint() {
  if (!live) return;
  const days = Q.ticker ? [[1, 'Day'], [7, '7 days'], [30, '30 days'], [365, 'Year']] : [[1, 'Day'], [7, '7 days'], [30, '30 days']];
  draw(mainEl, html`<header class="page-head">${sectionHead('discover', 'analysts')}</header>
    <section class="section first" aria-labelledby="an-h"><h2 class="t-h2" id="an-h">Analyst actions${Q.ticker ? `: ${Q.ticker}` : ''}</h2>
      <form class="op-filters" data-v2-an-form role="search"><label class="field field-sm"><span class="sr">Symbol</span><input name="t" value="${Q.ticker}" placeholder="Symbol, such as NVDA" maxlength="12" autocomplete="off"></label><button type="submit" class="btn btn-sm">Search</button>${Q.ticker ? html`<button type="button" class="btn btn-sm" data-v2-an-clear>All names</button>` : ''}</form>
      <div class="cluster an-filters">
        <div class="seg" role="group" aria-label="Show">${SHOWS.map(([v, l]) => html`<button type="button" data-v2-an-show="${v}" aria-pressed="${Q.show === v}">${l}</button>`)}</div>
        <div class="seg" role="group" aria-label="Rating">${RATINGS.map(([v, l]) => html`<button type="button" data-v2-an-rating="${v}" aria-pressed="${Q.rating === v}">${l}</button>`)}</div>
        <div class="seg" role="group" aria-label="Window">${days.map(([v, l]) => html`<button type="button" data-v2-an-days="${v}" aria-pressed="${Q.days === v}">${l}</button>`)}</div></div>
      ${body()}</section>`);
}

async function load() {
  const my = ++seq; D.d = null; D.err = null; paint();
  const q = new URLSearchParams({ days: Q.days }); if (Q.show) q.set('show', Q.show); if (Q.rating) q.set('rating', Q.rating);
  try {
    const d = Q.ticker ? await api.get(`/api/analysts/${encodeURIComponent(Q.ticker)}?limit=200&${q}`, { ttl: 300000, timeout: 30000 }) : await api.get(`/api/analysts/latest?${q}`, { ttl: 120000 });
    if (my !== seq || !live) return; D.d = d;
  } catch (e) { if (my !== seq) return; D.err = e; }
  paint();
}

export async function render(main) {
  live = true; mainEl = main; D = {};
  document.title = 'Analysts, Optic';
  provideContext(() => ({ view: 'analysts', analysts: D.d ? { query: Q, rows: (D.d.rows || []).slice(0, 30) } : null }));
  main.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-an-show]'))) { Q.show = b.dataset.v2AnShow; load(); return; }
    if ((b = t('[data-v2-an-rating]'))) { Q.rating = b.dataset.v2AnRating; load(); return; }
    if ((b = t('[data-v2-an-days]'))) { Q.days = Number(b.dataset.v2AnDays); load(); return; }
    if (t('[data-v2-an-clear]')) { Q.ticker = ''; if (Q.days === 365) Q.days = 30; load(); return; }
    if ((b = t('[data-v2-sort]'))) { const [, k] = b.dataset.v2Sort.split(':'); sort = nextSort(sort, k, COLS); paint(); const again = mainEl.querySelector(`[data-v2-sort="an:${k}"]`); if (again) again.focus(); }
  });
  main.addEventListener('submit', (e) => { const f = e.target.closest('[data-v2-an-form]'); if (!f) return; e.preventDefault(); Q.ticker = String(f.t.value || '').trim().toUpperCase(); load(); });
  load();
}
export function dispose() { live = false; }
export const retry = { analysts: () => load() };
