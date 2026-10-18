// Watchlist. The reader's named lists, from the account when signed in and from
// this browser when not (store.js). Sorts, filters and in-list search work
// exactly as in the classic app; every row opens the company beside the list.
// List management (new, rename, delete, reorder) happens inline: no browser
// prompts.
import { $, html, render as draw, raw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, signed, dir, clean } from '../core/format.js';
import { spark } from '../ui/chart.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { openCompany } from '../ui/company.js';
import { toast } from '../ui/toast.js';
import { provideContext, button as miloButton } from '../ui/milo.js';
import { groupTabs } from './tabs.js';

const SIGNAL_RANK = { bullish: 3, neutral: 2, bearish: 1, unknown: 0 };
const SORTS = [
  { id: 'movers', label: 'Biggest movers', cmp: (a, b) => Math.abs(b.change_pct || 0) - Math.abs(a.change_pct || 0) },
  { id: 'gainers', label: 'Gainers', cmp: (a, b) => (b.change_pct || 0) - (a.change_pct || 0) },
  { id: 'losers', label: 'Losers', cmp: (a, b) => (a.change_pct || 0) - (b.change_pct || 0) },
  { id: 'changed', label: 'Something changed', cmp: (a, b) => (b.changed ? 1 : 0) - (a.changed ? 1 : 0) || Math.abs(b.change_pct || 0) - Math.abs(a.change_pct || 0) },
  { id: 'signal', label: 'Optic signal', cmp: (a, b) => SIGNAL_RANK[b.signal] - SIGNAL_RANK[a.signal] || Math.abs(b.change_pct || 0) - Math.abs(a.change_pct || 0) },
  { id: 'alpha', label: 'A-Z', cmp: (a, b) => a.symbol.localeCompare(b.symbol) },
  { id: 'custom', label: 'My order', cmp: null },
];
const FILTERS = [
  { id: 'all', label: 'All', keep: () => true },
  { id: 'bullish', label: 'Bullish', keep: (r) => r.signal === 'bullish' },
  { id: 'bearish', label: 'Bearish', keep: (r) => r.signal === 'bearish' },
  { id: 'movers', label: 'Moved 2%+', keep: (r) => Math.abs(r.change_pct || 0) >= 2 },
];
const SIGNAL = { bullish: 'Bullish', bearish: 'Bearish', neutral: 'Neutral', unknown: 'No signal' };

let S = { sort: 'changed', filter: 'all', q: '', rows: null, err: null, editing: null, confirmDelete: false, method: '' };
let live = true;
let seq = 0;

async function fetchRows(symbols) {
  const chunks = [];
  for (let i = 0; i < symbols.length; i += 40) chunks.push(symbols.slice(i, i + 40));
  const res = await Promise.all(chunks.map((c) => api.get(`/api/watchlist?symbols=${c.map(encodeURIComponent).join(',')}`, { ttl: 60000, timeout: 30000 })));
  S.method = (res[0] || {}).method || '';
  const by = new Map(res.flatMap((r) => r.rows || []).map((r) => [r.symbol, r]));
  return symbols.map((s) => by.get(s) || { symbol: s, available: false, reason: 'No data returned for this symbol.' });
}

function listsBar() {
  const lists = store.state.lists || [];
  const a = store.activeList();
  const cap = store.listCap();
  if (S.editing === 'new' || S.editing === 'rename') {
    return html`<form class="list-form" data-v2-list-form="${S.editing}">
      <label class="field"><span class="sr">${S.editing === 'new' ? 'Name for the new list' : 'New name for this list'}</span><input name="name" maxlength="60" value="${S.editing === 'rename' && a ? a.name : ''}" placeholder="${S.editing === 'new' ? 'Name the list' : ''}" required></label>
      <button type="submit" class="btn btn-primary btn-sm">${S.editing === 'new' ? 'Create list' : 'Rename'}</button>
      <button type="button" class="btn btn-sm" data-v2-list-cancel>Cancel</button></form>`;
  }
  return html`<div class="lists-bar">
    <div class="chips" role="group" aria-label="Your lists">${lists.map((l) => html`<button type="button" class="chip" data-v2-list="${l.id}" aria-pressed="${!!a && l.id === a.id}">${l.name} <span class="t-muted">${l.symbols.length}</span></button>`)}
      <button type="button" class="chip" data-v2-list-new ${lists.length >= cap.n ? html`aria-disabled="true"` : ''}>${icon('plus')} New list</button></div>
    ${a ? html`<div class="cluster list-acts">
      <button type="button" class="textlink" data-v2-list-rename>Rename</button>
      ${lists.length > 1 ? (S.confirmDelete
    ? html`<span class="confirm" role="alert">Delete “${a.name}” and its ${a.symbols.length} names? <button type="button" class="btn btn-sm" data-v2-list-delete="yes">Delete</button><button type="button" class="btn btn-sm" data-v2-list-delete="no">Keep it</button></span>`
    : html`<button type="button" class="textlink" data-v2-list-delete="ask">Delete</button>`) : ''}
      ${lists.length > 1 ? html`<button type="button" class="icon-btn" data-v2-list-move="-1" aria-label="Move ${a.name} earlier">${icon('up')}</button><button type="button" class="icon-btn" data-v2-list-move="1" aria-label="Move ${a.name} later">${icon('down')}</button>` : ''}
    </div>` : ''}
  </div>`;
}

function pulse(rows) {
  const ok = rows.filter((r) => r.available);
  if (!ok.length) return '';
  const up = ok.filter((r) => r.change_pct > 0).length, down = ok.filter((r) => r.change_pct < 0).length;
  const big = ok.slice().sort((a, b) => Math.abs(b.change_pct || 0) - Math.abs(a.change_pct || 0))[0];
  const changed = ok.filter((r) => r.changed).length;
  const bull = ok.filter((r) => r.signal === 'bullish').length, bear = ok.filter((r) => r.signal === 'bearish').length;
  return html`<dl class="kv wl-pulse"><div><dt>Today</dt><dd>${up} up, ${down} down</dd></div>
    <div><dt>Biggest move</dt><dd><span class="tick">${big.symbol}</span> <span class="${dir(big.change_pct)}">${signed(big.change_pct)}</span></dd></div>
    <div><dt>Something changed</dt><dd>${changed} of ${ok.length}</dd></div>
    <div><dt>Signals</dt><dd>${bull} bullish, ${bear} bearish</dd></div></dl>`;
}

function rowsBlock() {
  const a = store.activeList();
  if (!a) return '';
  if (!a.symbols.length) return empty('Nothing on this list yet', 'Add a ticker above, or press Watch on any company.');
  if (S.err) return failed('This list', S.err, { retry: 'watchlist' });
  if (!S.rows) return skeleton('rows', Math.min(6, a.symbols.length), 'Loading the list');
  const spec = SORTS.find((x) => x.id === S.sort) || SORTS[3];
  const flt = FILTERS.find((x) => x.id === S.filter) || FILTERS[0];
  const q = S.q.trim().toUpperCase();
  let rows = S.rows.filter((r) => (!r.available ? S.filter === 'all' : flt.keep(r)) && (!q || r.symbol.includes(q)));
  if (spec.cmp) rows = rows.slice().sort((x, y) => (x.available && y.available ? spec.cmp(x, y) : x.available ? -1 : 1));
  const custom = !spec.cmp && S.filter === 'all' && !q;
  if (!rows.length) {
    return q ? empty(`No name matches “${S.q.trim()}”`, '', html`<button type="button" class="btn btn-sm" data-v2-wl-clear>Clear the search</button>`)
      : empty(`None of your ${S.rows.length} names matches ${flt.label.toLowerCase()}`, '', html`<button type="button" class="btn btn-sm" data-v2-wl-filter="all">Show all</button>`);
  }
  return html`<div class="wl-rows ${custom ? 'is-custom' : ''}">
    <div class="wl-head" aria-hidden="true"><span>Symbol</span><span class="num">Price</span><span class="num">Today</span><span class="spark-cell">30 sessions</span><span>What changed</span><span>Signal</span></div>
    <div role="list">
    ${rows.map((r, i) => html`<div class="wl-row" role="listitem">
      ${r.available ? html`<button type="button" class="row-main" data-v2-company="${r.symbol}" aria-expanded="false" aria-label="${r.symbol}, ${num(r.price)}, ${signed(r.change_pct)} today. Open the detail">
        <span class="who"><b class="tick">${r.symbol}</b></span><span class="num">${num(r.price)}</span><span class="num ${dir(r.change_pct)}">${signed(r.change_pct)}</span>
        <span class="spark-cell">${raw(spark(r.spark))}</span><span class="note">${r.changed ? clean(r.changed.text) : html`<span class="t-muted">Nothing new</span>`}</span><span class="sig sig-${r.signal}">${SIGNAL[r.signal] || 'No signal'}</span></button>`
    : html`<div class="row-main is-off"><span class="who"><b class="tick">${r.symbol}</b></span><span class="note t-muted" style="grid-column: 2 / -1">${clean(r.reason || 'No data right now.')}</span></div>`}
      ${custom ? html`<span class="order"><button type="button" class="icon-btn" data-v2-sym-move="-1" data-v2-sym="${r.symbol}" aria-label="Move ${r.symbol} up" ${i === 0 ? 'disabled' : ''}>${icon('up')}</button><button type="button" class="icon-btn" data-v2-sym-move="1" data-v2-sym="${r.symbol}" aria-label="Move ${r.symbol} down" ${i === rows.length - 1 ? 'disabled' : ''}>${icon('down')}</button></span>` : ''}
      <button type="button" class="icon-btn" data-v2-unwatch="${r.symbol}" aria-label="Remove ${r.symbol} from ${a.name}">${icon('close')}</button>
    </div>`)}</div></div>
    <p class="asof">${clean(S.method)}</p>`;
}

function controls() {
  const a = store.activeList();
  if (!a || !a.symbols.length) return '';
  return html`<div class="wl-controls">
    <label class="field field-sm">${icon('search')}<span class="sr">Find in this list</span><input type="search" data-v2-wl-q value="${S.q}" placeholder="Find in this list" autocomplete="off"></label>
    <div class="seg" role="group" aria-label="Show">${FILTERS.map((f) => html`<button type="button" data-v2-wl-filter="${f.id}" aria-pressed="${S.filter === f.id}">${f.label}</button>`)}</div>
    <label class="select"><span class="t-label">Sort</span><select data-v2-wl-sort>${SORTS.map((x) => html`<option value="${x.id}" ${S.sort === x.id ? 'selected' : ''}>${x.label}</option>`)}</select></label>
  </div>`;
}

function paint(main) {
  const a = store.activeList();
  const lists = store.state.lists || [];
  const f = document.activeElement;
  const keep = f && main.contains(f) ? [...Object.entries(f.dataset || {})][0] : null;
  draw($('#wl-body', main), html`
    ${store.state.listsError ? failed('Your watchlists', store.state.listsError, { retry: 'lists' }) : ''}
    ${!lists.length ? empty('You are not following anything yet', 'Add a ticker to start a list. Home and alerts fill in around what you follow.') : listsBar()}
    <form class="add-form" data-v2-add>
      <label class="field">${icon('plus')}<span class="sr">Add a ticker${a ? ` to ${a.name}` : ''}</span><input name="sym" placeholder="Add a ticker, such as MSFT" autocomplete="off" spellcheck="false" maxlength="12" required></label>
      <button type="submit" class="btn btn-primary">Add</button></form>
    ${!store.signedIn() ? html`<p class="asof">Kept in this browser. <a href="#/signin">Sign in</a> to keep your lists on your account.</p>` : ''}
    ${S.rows ? pulse(S.rows) : ''}${controls()}<div id="wl-rows">${rowsBlock()}</div>`);
  if (keep) {
    const [k, v] = keep;
    const attr = 'data-' + k.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase());
    const el = $(`[${attr}="${CSS.escape(v)}"]`, main);
    if (el) { el.focus(); if (el.tagName === 'INPUT' && el.type === 'search') { el.setSelectionRange(el.value.length, el.value.length); } }
  }
}

async function loadRows(main) {
  const my = ++seq;
  const a = store.activeList();
  S.err = null;
  if (!a || !a.symbols.length) { S.rows = []; paint(main); return; }
  if (!S.rows || S.rows.length !== a.symbols.length || S.rows.some((r, i) => r.symbol !== a.symbols[i])) {
    const known = new Map((S.rows || []).map((r) => [r.symbol, r]));
    if (a.symbols.every((s) => known.has(s))) S.rows = a.symbols.map((s) => known.get(s));
    else { S.rows = null; paint(main); }
  }
  try {
    const rows = await fetchRows(a.symbols);
    if (my !== seq || !live) return;
    S.rows = rows; S.err = null;
  } catch (e) { if (my !== seq) return; S.err = e; S.rows = null; }
  paint(main);
}

export async function render(main) {
  live = true;
  S = { sort: 'changed', filter: 'all', q: '', rows: null, err: null, editing: null, confirmDelete: false, method: '' };
  provideContext(() => ({ view: 'watchlist', watchlist: { name: (store.activeList() || {}).name, rows: S.rows } }));
  document.title = 'Watchlist, Optic';
  render_(main);
  wire(main);
  loadRows(main);
}
function render_(main) {
  draw(main, html`<header class="page-head"><div class="split"><h1 class="t-display-m">Watchlist</h1>${miloButton('Ask Milo about this list', { ask: 'Which names on my watchlist need attention, and why?', context: 'Watchlist' })}</div>${groupTabs('follow', 'watchlist')}</header>
    <div id="wl-body"></div>`);
  paint(main);
}

export function dispose() { live = false; }
export function onLists(main) { S.confirmDelete = false; loadRows(main); }
export const retry = { watchlist: (main) => loadRows(main), lists: async (main) => { await store.loadLists({ force: true }); loadRows(main); } };

function wire(main) {
  main.addEventListener('submit', async (e) => {
    const add = e.target.closest('[data-v2-add]');
    if (add) {
      e.preventDefault();
      const input = $('input', add);
      const sym = String(input.value || '').trim().toUpperCase();
      if (!/^[A-Z0-9.^=-]{1,12}$/.test(sym)) { toast('That does not look like a ticker. Try letters such as MSFT.'); return; }
      const a = store.activeList();
      if (a && a.symbols.includes(sym)) { toast(`${sym} is already on ${a.name}.`); return; }
      input.value = '';
      try { await store.follow(sym); toast(`${sym} added to ${(store.activeList() || {}).name || 'your watchlist'}.`, { action: 'Undo', run: () => store.unfollow(sym).catch(() => {}) }); }
      catch (err) { toast(err.message || 'Could not add it.', { kind: 'bad' }); }
      return;
    }
    const lf = e.target.closest('[data-v2-list-form]');
    if (lf) {
      e.preventDefault();
      const name = String(new FormData(lf).get('name') || '').trim();
      try {
        if (lf.dataset.v2ListForm === 'new') { await store.createList(name); toast(`Created ${name}.`); }
        else { await store.renameList(store.state.activeId, name); toast(`Renamed to ${name}.`); }
        S.editing = null; paint(main);
      } catch (err) { toast(err.message || 'That did not work.', { kind: 'bad' }); }
    }
  });
  main.addEventListener('input', (e) => {
    if (e.target.matches('[data-v2-wl-q]')) { S.q = e.target.value; draw($('#wl-rows', main), rowsBlock()); }
  });
  main.addEventListener('change', (e) => {
    if (e.target.matches('[data-v2-wl-sort]')) { S.sort = e.target.value; draw($('#wl-rows', main), rowsBlock()); }
  });
  main.addEventListener('click', async (e) => {
    const t = (sel) => e.target.closest(sel);
    let b;
    if ((b = t('[data-v2-list]'))) { store.setActive(b.dataset.v2List); S.rows = null; S.q = ''; return; }
    if ((b = t('[data-v2-list-new]'))) {
      if (b.getAttribute('aria-disabled') === 'true') { const c = store.listCap(); toast(c.plan ? `The ${c.plan} plan keeps ${c.n} watchlists. Rename or delete one to make room.` : 'Twelve lists is the limit. Rename or delete one.'); return; }
      S.editing = 'new'; paint(main); const i = $('[data-v2-list-form] input', main); if (i) i.focus(); return;
    }
    if (t('[data-v2-list-rename]')) { S.editing = 'rename'; paint(main); const i = $('[data-v2-list-form] input', main); if (i) { i.focus(); i.select(); } return; }
    if (t('[data-v2-list-cancel]')) { S.editing = null; paint(main); const r = $('[data-v2-list-rename]', main); if (r) r.focus(); return; }
    if ((b = t('[data-v2-list-delete]'))) {
      const v = b.dataset.v2ListDelete;
      if (v === 'ask') { S.confirmDelete = true; paint(main); const y = $('[data-v2-list-delete="no"]', main); if (y) y.focus(); return; }
      if (v === 'no') { S.confirmDelete = false; paint(main); return; }
      const a = store.activeList();
      try { await store.deleteList(a.id); toast(`Deleted ${a.name}.`); } catch (err) { toast(err.message || 'Could not delete it.', { kind: 'bad' }); }
      S.confirmDelete = false; S.rows = null; return;
    }
    if ((b = t('[data-v2-list-move]'))) { try { await store.moveList(store.state.activeId, Number(b.dataset.v2ListMove)); } catch (err) { toast(err.message, { kind: 'bad' }); } return; }
    if ((b = t('[data-v2-wl-filter]'))) { S.filter = b.dataset.v2WlFilter; paint(main); return; }
    if (t('[data-v2-wl-clear]')) { S.q = ''; paint(main); return; }
    if ((b = t('[data-v2-sym-move]'))) {
      try { await store.moveSymbol(b.dataset.v2Sym, Number(b.dataset.v2SymMove)); } catch (err) { toast(err.message, { kind: 'bad' }); }
      return;
    }
    if ((b = t('[data-v2-unwatch]'))) {
      const sym = b.dataset.v2Unwatch, a = store.activeList();
      try { await store.unfollow(sym); toast(`${sym} removed from ${a.name}.`, { action: 'Undo', run: () => store.follow(sym, a.id).catch(() => {}) }); }
      catch (err) { toast(err.message || 'Could not remove it.', { kind: 'bad' }); }
      return;
    }
    if ((b = t('[data-v2-company]'))) {
      const r = (S.rows || []).find((x) => x.symbol === b.dataset.v2Company);
      if (r) openCompany(r, b, { context: (store.activeList() || {}).name || 'Watchlist' });
    }
  });
}
