// Watchlist. The reader's named lists, from the account when signed in and from
// this browser when not (store.js). Sorts, filters and in-list search work
// as in the classic app; every row opens the company beside the list.
// List management (new, rename, delete, reorder) happens inline: no browser
// prompts, and nothing that needs dragging.
//
// The rows come from one batched pull (/api/watchlist: price, change, volume
// against its average, what changed, the signal). The next earnings date and
// the reader's alerts are asked after the rows paint, because each is slower
// or separate: earnings is one provider call per company.
import { $, html, render as draw, raw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, signed, dir, clean, shortDate } from '../core/format.js';
import { spark } from '../ui/chart.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { openCompany, alertsBySymbol } from '../ui/company.js';
import { toast } from '../ui/toast.js';
import { provideContext, button as miloButton } from '../ui/milo.js';
import { groupTabs } from './tabs.js';

const SIGNAL_RANK = { bullish: 3, neutral: 2, bearish: 1, unknown: 0 };
const has = (v) => typeof v === 'number' && Number.isFinite(v);
// A numeric sort puts a row without the figure last, whichever way it runs, and rows that tie keep
// their place on the list, so the order never depends on the browser (the audit, 2026-10-20).
const by = (key, desc = true) => (a, b) => (has(a[key]) ? (has(b[key]) ? (desc ? b[key] - a[key] : a[key] - b[key]) : -1) : (has(b[key]) ? 1 : 0));
const absBy = (key) => (a, b) => (has(a[key]) ? (has(b[key]) ? Math.abs(b[key]) - Math.abs(a[key]) : -1) : (has(b[key]) ? 1 : 0));
export const SORTS = [
  { id: 'movers', label: 'Biggest movers', cmp: absBy('change_pct') },
  { id: 'gainers', label: 'Gainers', cmp: by('change_pct') },
  { id: 'losers', label: 'Losers', cmp: by('change_pct', false) },
  { id: 'changed', label: 'Something changed', cmp: (a, b) => (b.changed ? 1 : 0) - (a.changed ? 1 : 0) || absBy('change_pct')(a, b) },
  { id: 'volume', label: 'Volume against average', cmp: by('volume_ratio') },
  { id: 'earnings', label: 'Next earnings', cmp: by('earn_days', false) },
  { id: 'signal', label: 'Optic signal', cmp: (a, b) => (SIGNAL_RANK[b.signal] || 0) - (SIGNAL_RANK[a.signal] || 0) || absBy('change_pct')(a, b) },
  { id: 'alpha', label: 'A-Z', cmp: (a, b) => a.symbol.localeCompare(b.symbol), all: true },
  { id: 'custom', label: 'My order', cmp: null, all: true },
];
const FILTERS = [
  { id: 'all', label: 'All', keep: () => true },
  { id: 'bullish', label: 'Bullish', keep: (r) => r.signal === 'bullish' },
  { id: 'bearish', label: 'Bearish', keep: (r) => r.signal === 'bearish' },
  { id: 'movers', label: 'Moved 2%+', keep: (r) => has(r.change_pct) && Math.abs(r.change_pct) >= 2 },
];
const SIGNAL = { bullish: 'Bullish', bearish: 'Bearish', neutral: 'Neutral', unknown: 'No signal' };
const SORT_KEY = 'optic.v2.watchlist.sort.v1';   // a display choice, not personal data

/** The rows in the order a sort asks, rows without data last except under A-Z and My order. */
export function sortRows(rows, sortId) {
  const spec = SORTS.find((x) => x.id === sortId) || SORTS[3];
  if (!spec.cmp) return rows.slice();
  const place = new Map(rows.map((r, i) => [r.symbol, i]));
  const tie = (a, b) => place.get(a.symbol) - place.get(b.symbol);
  return rows.slice().sort((x, y) => {
    if (!spec.all && x.available !== y.available) return x.available ? -1 : 1;
    if (!spec.all && !x.available) return tie(x, y);
    return spec.cmp(x, y) || tie(x, y);
  });
}

const readSort = () => { try { const v = localStorage.getItem(SORT_KEY); return SORTS.some((x) => x.id === v) ? v : 'changed'; } catch (e) { return 'changed'; } };
const fresh = () => ({ sort: readSort(), filter: 'all', q: '', rows: null, err: null, editing: null, confirmDelete: false, method: '', earn: {}, alerts: {}, undo: null });
let S = fresh();
let live = true;
let seq = 0;

async function fetchRows(symbols) {
  const chunks = [];
  for (let i = 0; i < symbols.length; i += 40) chunks.push(symbols.slice(i, i + 40));
  const res = await Promise.all(chunks.map((c) => api.get(`/api/watchlist?symbols=${c.map(encodeURIComponent).join(',')}`, { ttl: 60000, timeout: 30000 })));
  S.method = (res[0] || {}).method || '';
  const got = new Map(res.flatMap((r) => r.rows || []).map((r) => [r.symbol, r]));
  return symbols.map((s) => got.get(s) || { symbol: s, available: false, reason: 'No data returned for this symbol.' });
}

async function loadExtras(main, symbols) {
  const my = seq;
  const want = symbols.slice(0, 40);
  want.forEach((s) => { if (!S.earn[s]) S.earn[s] = { loading: true }; });
  const earn = api.get(`/api/watchlist/earnings?symbols=${want.map(encodeURIComponent).join(',')}`, { ttl: 3600000, timeout: 45000 })
    .then((r) => { Object.assign(S.earn, (r && r.dates) || {}); }, () => { want.forEach((s) => { if (S.earn[s] && S.earn[s].loading) S.earn[s] = { failed: true }; }); });
  const watches = alertsBySymbol().then((m) => { if (m) S.alerts = m; });
  await Promise.all([earn, watches]);
  if (my !== seq || !live) return;
  paintRows(main);
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
  const big = ok.filter((r) => has(r.change_pct)).sort(absBy('change_pct'))[0];
  const changed = ok.filter((r) => r.changed).length;
  const bull = ok.filter((r) => r.signal === 'bullish').length, bear = ok.filter((r) => r.signal === 'bearish').length;
  const asOf = ok.map((r) => r.as_of).filter(Boolean).sort().pop();
  return html`<dl class="kv wl-pulse"><div><dt>Today</dt><dd>${up} up, ${down} down</dd></div>
    <div><dt>Biggest move</dt><dd>${big ? html`<span class="tick">${big.symbol}</span> <span class="${dir(big.change_pct)}">${signed(big.change_pct)}</span>` : html`<span class="t-muted">Not reported</span>`}</dd></div>
    <div><dt>Something changed</dt><dd>${changed} of ${ok.length}</dd></div>
    <div><dt>Signals</dt><dd>${bull} bullish, ${bear} bearish</dd></div></dl>
    ${asOf ? html`<p class="asof">Daily bars to the session of ${shortDate(asOf)}${ok.some((r) => r.volume_partial) ? ', which is still trading: its volume is so far today' : ''}.</p>` : ''}`;
}

const cellMissing = (t = 'n/a') => html`<span class="t-muted">${t}</span>`;
function earnCell(r) {
  const e = S.earn[r.symbol];
  if (!e || e.loading) return cellMissing('…');
  if (e.failed) return cellMissing('Not loaded');
  return e.date ? html`${shortDate(e.date)}<small class="t-muted"> ${e.days === 0 ? 'today' : `${e.days}d`}</small>` : cellMissing('None set');
}
function alertCell(r) {
  const a = S.alerts[r.symbol];
  if (!a || (!a.n && !a.fired)) return '';
  return html`<span class="wl-alert ${a.fired ? 'is-fired' : ''}">${icon('bell')}${a.fired ? `${a.fired} fired today` : `${a.n} alert${a.n === 1 ? '' : 's'}`}</span>`;
}

function rowsBlock() {
  const a = store.activeList();
  if (!a) return '';
  if (!a.symbols.length) return empty('Nothing on this list yet', 'Add a ticker above, or press Watch on any company.');
  if (!S.rows && !S.err) return skeleton('rows', Math.min(6, a.symbols.length), 'Loading the list');
  // the feed failing hides no names: each row keeps its symbol and its controls, said as unpriced
  const base = S.rows || a.symbols.map((s) => ({ symbol: s, available: false, reason: 'Price not loaded.' }));
  const withExtras = base.map((r) => Object.assign({}, r, { earn_days: (S.earn[r.symbol] || {}).days }));
  const flt = FILTERS.find((x) => x.id === S.filter) || FILTERS[0];
  const q = S.q.trim().toUpperCase();
  let rows = withExtras.filter((r) => (!r.available ? S.filter === 'all' : flt.keep(r)) && (!q || r.symbol.includes(q)));
  rows = sortRows(rows, S.sort);
  const custom = S.sort === 'custom' && S.filter === 'all' && !q;
  const banner = html`${S.err ? html`<div class="stale" role="status">Prices did not load: ${api.explain(S.err, 'This list')} <button type="button" class="textlink" data-v2-retry="watchlist">Try again</button></div>` : ''}
    ${S.undo ? html`<p class="wl-undo" role="status">${S.undo.text} <button type="button" class="btn btn-sm" data-v2-wl-undo>Undo</button></p>` : ''}`;
  if (!rows.length) {
    return html`${banner}${q ? empty(`No name matches “${S.q.trim()}”`, '', html`<button type="button" class="btn btn-sm" data-v2-wl-clear>Clear the search</button>`)
      : empty(`None of your ${base.length} names matches ${flt.label.toLowerCase()}`, '', html`<button type="button" class="btn btn-sm" data-v2-wl-filter="all">Show all</button>`)}`;
  }
  return html`${banner}<div class="wl-rows ${custom ? 'is-custom' : ''}">
    <div class="wl-head" aria-hidden="true"><span>Symbol</span><span class="num">Price</span><span class="num">Today</span><span class="spark-cell">30 sessions</span><span class="num wl-vol">Volume</span><span class="wl-earn">Earnings</span><span>What changed</span><span>Signal</span></div>
    <div role="list">
    ${rows.map((r, i) => html`<div class="wl-row" role="listitem">
      ${r.available ? html`<button type="button" class="row-main" data-v2-company="${r.symbol}" aria-haspopup="dialog" aria-label="${r.symbol}, ${has(r.price) ? num(r.price) : 'no price'}, ${has(r.change_pct) ? signed(r.change_pct) : 'no change figure'} today${r.changed ? `, ${clean(r.changed.text)}` : ''}${r.signal ? `, ${SIGNAL[r.signal] || 'no signal'}` : ''}. Open the detail">
        <span class="who"><b class="tick">${r.symbol}</b>${alertCell(r)}</span><span class="num wl-price">${has(r.price) ? num(r.price) : cellMissing()}</span><span class="num wl-chg ${dir(r.change_pct)}">${has(r.change_pct) ? signed(r.change_pct) : cellMissing()}</span>
        <span class="spark-cell">${raw(spark(r.spark))}</span>
        <span class="num wl-vol">${has(r.volume_ratio) ? html`${num(r.volume_ratio, 1)}×${r.volume_partial ? html`<small class="t-muted"> so far</small>` : ''}` : cellMissing()}</span>
        <span class="wl-earn">${earnCell(r)}</span>
        <span class="note">${r.changed ? clean(r.changed.text) : html`<span class="t-muted">Nothing new</span>`}</span><span class="sig sig-${r.signal}">${SIGNAL[r.signal] || 'No signal'}</span></button>`
    : html`<div class="row-main is-off"><span class="who"><b class="tick">${r.symbol}</b></span><span class="note t-muted" style="grid-column: 2 / -1">${clean(r.reason || 'No data right now.')}</span></div>`}
      ${custom ? html`<span class="order"><button type="button" class="icon-btn" data-v2-sym-move="-1" data-v2-sym="${r.symbol}" aria-label="Move ${r.symbol} up" ${i === 0 ? 'disabled' : ''}>${icon('up')}</button><button type="button" class="icon-btn" data-v2-sym-move="1" data-v2-sym="${r.symbol}" aria-label="Move ${r.symbol} down" ${i === rows.length - 1 ? 'disabled' : ''}>${icon('down')}</button></span>` : ''}
      <button type="button" class="icon-btn" data-v2-unwatch="${r.symbol}" aria-label="Remove ${r.symbol} from ${a.name}">${icon('close')}</button>
    </div>`)}</div></div>
    <p class="asof">${clean(S.method)} Volume is the last session's against its 20-session average. Earnings dates are the companies' published or expected dates, from Yahoo Finance.</p>`;
}

function controls() {
  const a = store.activeList();
  if (!a || !a.symbols.length) return '';
  return html`<div class="wl-controls">
    <label class="field field-sm">${icon('search')}<span class="sr">Find in this list</span><input type="search" data-v2-wl-q value="${S.q}" placeholder="Find in this list" autocomplete="off"></label>
    <div class="seg" role="group" aria-label="Show">${FILTERS.map((f) => html`<button type="button" data-v2-wl-filter="${f.id}" aria-pressed="${S.filter === f.id}">${f.label}</button>`)}</div>
    <label class="select"><span class="t-label">Sort</span><select data-v2-wl-sort>${SORTS.map((x) => html`<option value="${x.id}" ${S.sort === x.id ? 'selected' : ''}>${x.label}</option>`)}</select></label>
    ${S.sort !== 'custom' ? html`<button type="button" class="btn btn-sm" data-v2-wl-reorder>Reorder</button>` : ''}
  </div>`;
}

function savedNote() {
  if (store.signedIn()) return html`<p class="asof">On your account: saved as you change it, and the same on any device you sign in on.</p>`;
  return html`<p class="asof">Only in this browser. <a href="#/signin">Sign in</a> and Optic offers to bring these lists into your account, as lists. An account already used on this browser keeps its own lists, and these wait here until you sign out.</p>`;
}

// what to focus after a paint: the same control on the same row, or the next row after a removal
let focusNext = null;
function paint(main) {
  const a = store.activeList();
  const lists = store.state.lists || [];
  const f = document.activeElement;
  const kept = focusNext || (f && main.contains(f) ? keyOf(f) : null);
  focusNext = null;
  draw($('#wl-body', main), html`
    ${store.state.listsError ? failed('Your watchlists', store.state.listsError, { retry: 'lists' }) : ''}
    ${!lists.length ? empty('You are not following anything yet', 'Add a ticker below to start your watchlist.') : listsBar()}
    <form class="add-form" data-v2-add>
      <label class="field">${icon('plus')}<span class="sr">Add a ticker${a ? ` to ${a.name}` : ''}</span><input name="sym" data-v2-wl-add placeholder="Add a ticker, such as MSFT" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="12" enterkeyhint="done" required></label>
      <button type="submit" class="btn btn-primary">Add</button></form>
    ${savedNote()}
    ${S.rows ? pulse(S.rows) : ''}${controls()}<div id="wl-rows">${rowsBlock()}</div>`);
  if (kept) refocus(main, kept);
}
/** Redraw the rows alone (the earnings and alerts arriving, a search keystroke), keeping focus where it was. */
function paintRows(main) {
  const box = $('#wl-rows', main); if (!box) return;
  const f = document.activeElement;
  const kept = f && box.contains(f) ? keyOf(f) : null;
  draw(box, rowsBlock());
  if (kept) refocus(main, kept);
}
function keyOf(el) {
  const sym = el.dataset && (el.dataset.v2Sym || el.dataset.v2Company || el.dataset.v2Unwatch);
  const act = ['v2SymMove', 'v2Company', 'v2Unwatch', 'v2WlAdd', 'v2WlQ', 'v2WlSort', 'v2WlFilter', 'v2List', 'v2ListMove', 'v2WlReorder', 'v2WlUndo'].find((k) => el.dataset && k in el.dataset);
  return act ? { act, sym, val: el.dataset[act] } : null;
}
function refocus(main, k) {
  const attr = 'data-' + k.act.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase());
  let el = null;
  if (k.act === 'v2SymMove') el = $(`[data-v2-sym-move="${k.val}"][data-v2-sym="${CSS.escape(k.sym)}"]`, main) || $(`[data-v2-sym="${CSS.escape(k.sym)}"]`, main);
  else if (k.sym) el = $(`[${attr}="${CSS.escape(k.sym)}"]`, main);
  else el = $(k.val !== undefined && k.val !== '' ? `[${attr}="${CSS.escape(k.val)}"]` : `[${attr}]`, main);
  if (el && el.disabled) el = el.parentElement && $('button:not([disabled])', el.parentElement);
  if (el) { el.focus({ preventScroll: true }); if (el.tagName === 'INPUT' && el.type === 'search') el.setSelectionRange(el.value.length, el.value.length); }
}

async function loadRows(main) {
  const my = ++seq;
  const a = store.activeList();
  S.err = null;
  if (!a || !a.symbols.length) { S.rows = []; paint(main); return; }
  if (!S.rows || S.rows.length !== a.symbols.length || S.rows.some((r, i) => r.symbol !== a.symbols[i])) {
    const known = new Map((S.rows || []).map((r) => [r.symbol, r]));
    // a removal or a reorder shows at once from the rows already here; only a new name waits for its figures
    if (a.symbols.every((s) => known.has(s))) S.rows = a.symbols.map((s) => known.get(s));
    else S.rows = null;
    paint(main);
  }
  try {
    const rows = await fetchRows(a.symbols);
    if (my !== seq || !live) return;
    S.rows = rows; S.err = null;
  } catch (e) { if (my !== seq) return; S.err = e; S.rows = null; }
  paint(main);
  loadExtras(main, a.symbols);
}

export async function render(main) {
  live = true;
  S = fresh();
  provideContext(() => ({ view: 'watchlist', watchlist: { name: (store.activeList() || {}).name, rows: S.rows, earnings: S.earn } }));
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

const say = (e, what) => (e && e.message && (e.kind === 'bad' || e.kind === 'limit' || e.status === 0 || e.status === 409) ? e.message : api.explain(e, what));
function offerUndo(main, text, run) {
  S.undo = { text, run };
  toast(text, { action: 'Undo', run: () => doUndo(main) });
  clearTimeout(offerUndo.t); offerUndo.t = setTimeout(() => { if (S.undo && S.undo.text === text) { S.undo = null; if (live) paintRows(main); } }, 15000);
}
async function doUndo(main) {
  const u = S.undo; if (!u) return;
  S.undo = null;
  try { await u.run(); } catch (e) { toast(`Undo did not go through: ${say(e, 'The change')}`, { kind: 'bad' }); }
  if (live) paint(main);
}

function wire(main) {
  main.addEventListener('submit', async (e) => {
    const add = e.target.closest('[data-v2-add]');
    if (add) {
      e.preventDefault();
      const input = $('input', add);
      const typed = String(input.value || '').trim();
      const sym = store.canon(typed);
      if (!/^[A-Z0-9.^=-]{1,12}$/.test(sym)) { toast('That does not look like a ticker. Try letters such as MSFT.'); return; }
      const a = store.activeList();
      if (a && a.symbols.includes(sym)) { toast(`${sym} is already on ${a.name}.`); input.select(); return; }
      input.value = '';
      focusNext = { act: 'v2WlAdd' };
      try {
        await store.follow(sym);
        const l = store.activeList(), id = l && l.id;
        offerUndo(main, `${sym} added to ${(l || {}).name || 'your watchlist'}.`, () => store.unfollow(sym, id));
      } catch (err) {
        // the form may have been redrawn while the change was put back: the box that is there now gets the text
        const cur = $('[data-v2-wl-add]', main) || input; cur.value = typed; cur.focus({ preventScroll: true });
        toast(say(err, 'Adding it'), { kind: 'bad' });
      }
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
      } catch (err) { toast(say(err, 'That'), { kind: 'bad' }); }
    }
  });
  main.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && e.target.closest('[data-v2-list-form]')) { e.preventDefault(); S.editing = null; paint(main); const r = $('[data-v2-list-rename]', main) || $('[data-v2-list-new]', main); if (r) r.focus(); }
  });
  main.addEventListener('input', (e) => {
    if (e.target.matches('[data-v2-wl-q]')) { S.q = e.target.value; paintRows(main); }
  });
  main.addEventListener('change', (e) => {
    if (e.target.matches('[data-v2-wl-sort]')) { S.sort = e.target.value; try { localStorage.setItem(SORT_KEY, S.sort); } catch (err) { /* private */ } paint(main); }
  });
  main.addEventListener('click', async (e) => {
    const t = (sel) => e.target.closest(sel);
    let b;
    if ((b = t('[data-v2-list]'))) { store.setActive(b.dataset.v2List); S.rows = null; S.q = ''; S.undo = null; return; }
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
      try { await store.deleteList(a.id); toast(`Deleted ${a.name}.`); } catch (err) { toast(say(err, 'Deleting it'), { kind: 'bad' }); }
      S.confirmDelete = false; S.rows = null; return;
    }
    if ((b = t('[data-v2-list-move]'))) { try { await store.moveList(store.state.activeId, Number(b.dataset.v2ListMove)); } catch (err) { toast(say(err, 'Moving it'), { kind: 'bad' }); } return; }
    if ((b = t('[data-v2-wl-filter]'))) { S.filter = b.dataset.v2WlFilter; paint(main); return; }
    if (t('[data-v2-wl-clear]')) { S.q = ''; paint(main); return; }
    if (t('[data-v2-wl-reorder]')) { S.sort = 'custom'; S.filter = 'all'; S.q = ''; try { localStorage.setItem(SORT_KEY, 'custom'); } catch (err) { /* private */ } paint(main); const m = $('[data-v2-sym-move]:not([disabled])', main); if (m) m.focus(); return; }
    if (t('[data-v2-wl-undo]')) { await doUndo(main); return; }
    if ((b = t('[data-v2-sym-move]'))) {
      // the same button on the same name keeps focus, so a name can be walked up or down a list by key
      focusNext = { act: 'v2SymMove', sym: b.dataset.v2Sym, val: b.dataset.v2SymMove };
      try { await store.moveSymbol(b.dataset.v2Sym, Number(b.dataset.v2SymMove)); } catch (err) { focusNext = null; toast(say(err, 'Moving it'), { kind: 'bad' }); }
      return;
    }
    if ((b = t('[data-v2-unwatch]'))) {
      const sym = b.dataset.v2Unwatch, a = store.activeList(), id = a.id, at = a.symbols.indexOf(sym);
      const next = a.symbols[at + 1] || a.symbols[at - 1];
      focusNext = next ? { act: 'v2Unwatch', sym: next } : { act: 'v2WlAdd' };
      try { await store.unfollow(sym, id); offerUndo(main, `${sym} removed from ${a.name}.`, () => store.follow(sym, id, { at })); }
      catch (err) { focusNext = null; toast(say(err, 'Removing it'), { kind: 'bad' }); }
      return;
    }
    if ((b = t('[data-v2-company]'))) {
      const r = (S.rows || []).find((x) => x.symbol === b.dataset.v2Company);
      if (r) openCompany(r, b, { context: (store.activeList() || {}).name || 'Watchlist', earnings: S.earn[r.symbol] || null, alerts: S.alerts[r.symbol] || null });
    }
  });
}
