// Saved research, at #/research: the library (Handoff 5 of the owner's handover pack, 2026-11-03). What the reader
// saved from a Dossier, Compare, Milo or a research sheet, newest first, by kind and by search, a page at a time, each
// opening where it was saved: a company on its Dossier, a comparison in Compare, a sheet on today's figures, a Milo
// conversation in Milo's panel with the sources it had. Questions kept to ask again (Classic parity B4d) are listed with
// them. The library is the account's; a guest has this browser's questions, as before. Nothing here calls a model.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num } from '../core/format.js';
import * as lib from '../core/library.js';
import { skeleton, empty } from '../ui/states.js';
import { openMilo, openSaved, provideContext } from '../ui/milo.js';
import { renameSheet } from '../ui/library.js';
import { toast } from '../ui/toast.js';
import { icon } from '../ui/icons.js';
import { go } from '../core/router.js';
import { listSaved, forget } from '../core/research.js';

// the library's own loading ends like Home's panels (Handoff 4): 10 s to "Couldn't load", then 5, 15 and 45 s retries
export const WAIT = 10000, BACKOFF = [5000, 15000, 45000];
let L = null, live = true, mainEl = null, seq = 0, wired = null, lateT = 0, autoT = 0, typeT = 0, armed = null;
const fresh = () => ({ kind: '', search: '', items: [], next: null, counts: null, total: 0, limit: null, err: null, loading: false, late: false, tries: 0, more: false, guest: null });

// Classic's four ways in, word for word (RESEARCH_ROUTES); each goes where it says, none sends anything
const ROUTES = [
  { q: 'What do the named screens find today?', href: '#/scan', note: 'Named screens over the ranked universe. Each states what it did not search.' },
  { q: 'How do two or three names stack up?', href: '#/compare', note: 'Scored across three horizons separately, so a name can lead one and trail another.' },
  { q: 'What is going on with one company?', milo: '', note: 'Search a ticker to open the full read, or ask in plain language.' },
  { q: 'I need sources and citations.', milo: 'deep', note: 'Deep research runs live web sources and cites them. Slower, and rate limited.' },
];
function start() {
  return html`<section class="section" aria-labelledby="sv-start"><h2 class="t-h2" id="sv-start">Start an investigation</h2>
    <ul class="sv-routes">${ROUTES.map((r, i) => html`<li>${r.href ? html`<a class="sv-route" href="${r.href}"><b>${r.q}</b><span>${r.note}</span></a>`
      : html`<button type="button" class="sv-route" data-sv-route="${i}"><b>${r.q}</b><span>${r.note}</span></button>`}</li>`)}</ul></section>`;
}

/* ---------------- one item ---------------- */
const OPEN = { company: 'Open Dossier', comparison: 'Open comparison', conversation: 'Open in Milo', sheet: 'Open sheet', screen: 'Open and run', question: 'Ask again' };
const priced = (s) => (s && s.price && s.price.price !== undefined && s.price.price !== null ? ` at $${num(s.price.price)}` : '');
function goneLine(it) {
  const gone = it.gone || [];
  if (!gone.length) return '';
  const s = it.summary || {}, names = s.names || {};
  if (it.kind === 'comparison') {
    const left = (it.tickers || []).filter((t) => !gone.includes(t));
    return html`<p class="lib-gone">${gone.join(', ')} ${gone.length === 1 ? 'is' : 'are'} no longer available. ${left.length >= 2 ? `It opens with ${left.join(', ')}.` : left.length ? `It opens with ${left[0]} alone, to compare with another.` : ''}</p>`;
  }
  const t = gone[0];
  return html`<p class="lib-gone">${t} is no longer available. ${names[t] && names[t] !== t ? `${names[t]}, ` : ''}saved ${lib.dayText(it.created_at)}${priced(s)}.</p>`;
}
function item(it, i) {
  const s = it.summary || {}, names = s.names || {}, gone = it.gone || [];
  const deadEnd = (it.kind === 'company' || it.kind === 'sheet') && gone.length;
  const when = `Saved ${lib.dayText(it.created_at)}${it.updated_at && lib.dayText(it.updated_at) !== lib.dayText(it.created_at) ? `, updated ${lib.dayText(it.updated_at)}` : ''}`;
  // what it is about: the question, or the companies by name (said once: without their names the tickers line below is enough)
  const named = (it.tickers || []).some((t) => names[t] && names[t] !== t);
  // a screen (Handoff 8): the request as the reader wrote it, or its filters in plain English
  const about = it.kind === 'question' ? it.question : it.kind === 'screen' ? (s.text ? `“${s.text}”` : (s.said || []).join('; ')) : it.kind === 'conversation' ? (s.question ? `Asked: ${s.question}` : '') : named ? (it.tickers || []).map((t) => (names[t] && names[t] !== t ? `${t} ${names[t]}` : t)).join(', ') : '';
  const isArmed = armed === it.id;
  return html`<li class="lib-item" data-lib-item="${it.id}">
    <div class="lib-text"><p class="lib-kind t-label">${lib.WORD[it.kind] || 'Saved'}</p>
      <h3 class="lib-name">${it.name || about}</h3>
      ${about && about !== it.name ? html`<p class="lib-about">${about}</p>` : ''}
      <p class="lib-meta">${(it.tickers || []).length ? html`<span class="lib-ticks">${it.tickers.join(', ')}</span>` : ''}<span>${when}</span>${it.kind === 'conversation' && s.answers ? html`<span>${s.answers} answer${s.answers === 1 ? '' : 's'}</span>` : ''}</p>
      ${goneLine(it)}</div>
    <div class="lib-acts">${deadEnd ? html`<button type="button" class="btn btn-sm" disabled title="The ticker is no longer available">${OPEN[it.kind]}</button>` : html`<button type="button" class="btn btn-sm" data-lib-open="${i}">${OPEN[it.kind] || 'Open'}</button>`}
      ${it.kind === 'question' ? '' : html`<button type="button" class="btn btn-sm btn-quiet" data-lib-rename="${i}" aria-label="Rename ${it.name}">Rename</button>`}
      ${isArmed ? html`<button type="button" class="btn btn-sm btn-danger" data-lib-del="${i}">Yes, delete</button><button type="button" class="btn btn-sm btn-quiet" data-lib-keep>Keep</button>`
        : html`<button type="button" class="btn btn-sm btn-quiet" data-lib-del="${i}" aria-label="Delete ${it.name || 'this item'}">Delete</button>`}</div>
  </li>`;
}

/* ---------------- the page ---------------- */
function filters() {
  const c = L.counts || {};
  const all = [['', 'All', L.total], ...lib.KINDS.map((k) => [k, lib.PLURAL[k], c[k] || 0])].filter(([k, , n]) => !k || n || L.kind === k);
  return html`<div class="lib-tools"><div class="seg lib-kinds" role="group" aria-label="Kind of saved research">${all.map(([k, label, n]) => html`<button type="button" data-lib-kind="${k}" aria-pressed="${L.kind === k}">${label}${n ? html` <span class="lib-n">${n}</span>` : ''}</button>`)}</div>
    <label class="field lib-search"><span class="sr">Search saved research</span>${icon('search')}<input type="search" data-lib-search value="${L.search}" placeholder="Search names, tickers and questions" autocomplete="off" spellcheck="false"></label></div>`;
}
function body() {
  if (L.err && !L.items.length) {
    const why = L.err.kind === 'late' ? `It has not answered in ${WAIT / 1000} seconds. It appears here if it arrives.` : api.explain(L.err, 'Saved research');
    return html`<div class="state err lib-retry" role="alert"><p class="t-h3">Couldn't load your saved research.</p><p>${why}${autoT ? ' Optic asks again by itself.' : L.tries >= BACKOFF.length && L.err.kind !== 'late' ? ' Optic has stopped asking by itself.' : ''}</p><button type="button" class="btn btn-sm" data-lib-retry>Retry</button></div>`;
  }
  if (L.loading && !L.items.length) return skeleton('rows', 4, 'Loading saved research');
  if (!L.items.length) {
    if (L.search || L.kind) return empty('Nothing matches', L.search ? `Nothing saved matches “${L.search}”${L.kind ? ` among ${lib.PLURAL[L.kind].toLowerCase()}` : ''}.` : `No ${lib.PLURAL[L.kind].toLowerCase()} saved yet.`);
    return empty('Nothing saved yet', 'Press Save on a company\'s Dossier, on a comparison in Compare, on a research sheet, on a screen in Scan, or in Milo\'s panel to keep a conversation with its sources. Each keeps its tickers and the date, and opens where you saved it.',
      html`<a class="btn btn-sm" href="#/dossier">Open a Dossier</a>`);
  }
  return html`<ul class="lib-list">${L.items.map(item)}</ul>
    ${L.next ? html`<button type="button" class="btn btn-sm lib-more" data-lib-more ${L.more ? 'disabled' : ''}>${L.more ? 'Loading more…' : 'Show more'}</button>` : ''}
    <p class="asof">${L.total} saved${L.limit ? ` of the ${L.limit} this plan keeps` : ''}, kept with your account and on every device you sign in on. What you saved is research as it stood then, not advice.</p>`;
}
function guestBody() {
  const g = L.guest;
  if (!g) return skeleton('rows', 3, 'Loading saved questions');
  const items = g.items || [];
  return html`<p class="lib-guest">Saved research is kept with an account: companies, comparisons, research sheets, and Milo conversations with their sources. <a class="textlink" href="#/signin">Sign in or create a free account</a> to keep them on every device.</p>
    ${items.length ? html`<h3 class="t-h3">Questions kept in this browser</h3><ul class="sv-list">${items.map((x, i) => html`<li class="sv-item"><p class="sv-q">${x.question}</p>
      <p class="sv-meta">${x.symbol ? html`<a class="textlink" href="#/${encodeURIComponent(x.symbol)}">${x.symbol}</a>` : html`<span>The market</span>`}${x.at ? html`<span>Saved ${lib.dayText(x.at)}</span>` : ''}</p>
      <div class="sv-acts"><button type="button" class="btn btn-sm" data-sv-ask="${i}">Ask again</button><button type="button" class="btn btn-sm btn-quiet" data-sv-forget="${i}" aria-label="Forget: ${x.question.slice(0, 80)}">Forget</button></div></li>`)}</ul>
      <p class="asof">Kept in this browser, up to 40. Asking again puts the question in Milo's box; nothing is sent until you press Send.</p>` : ''}`;
}
function paint() {
  if (!live || !mainEl) return;
  const signed = store.signedIn();
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">Saved research</h1>
      <p class="section-sub">What you saved from a Dossier, Compare, a research sheet or Milo, to come back to.</p></header>
    <section class="section" aria-labelledby="lib-h"><h2 class="t-h2 sr" id="lib-h">Your saved research</h2>
      ${signed ? html`${filters()}<div id="lib-body" aria-live="polite">${body()}</div>` : guestBody()}</section>
    ${start()}`);
}
// the list alone, so the search box keeps its focus and what was typed
function paintBody() {
  if (!live || !mainEl) return;
  const b = mainEl.querySelector('#lib-body'), f = mainEl.querySelector('.lib-tools');
  if (!b || !f) { paint(); return; }
  draw(b, body());
  const kinds = mainEl.querySelector('.lib-kinds'); if (kinds) { const tmp = document.createElement('div'); draw(tmp, filters()); const k2 = tmp.querySelector('.lib-kinds'); if (k2) kinds.replaceWith(k2); }
}

async function load({ more = false } = {}) {
  if (!store.signedIn()) { try { L.guest = await listSaved(); } catch (e) { L.guest = { items: [] }; } paint(); return; }
  const my = ++seq; clearTimeout(lateT); clearTimeout(autoT); autoT = 0;
  if (more) L.more = true; else { L.loading = true; L.err = null; }
  paintBody();
  if (!more) lateT = setTimeout(() => { if (live && my === seq && L.loading && !L.items.length) { L.err = { kind: 'late' }; paintBody(); } }, WAIT);
  try {
    const r = await lib.list({ kind: L.kind, search: L.search, cursor: more ? L.next : '' });
    if (my !== seq) return;
    L.items = more ? [...L.items, ...(r.items || [])] : (r.items || []);
    L.next = r.next || null; L.counts = r.counts || {}; L.total = r.total || 0; L.limit = r.limit || null; L.err = null; L.tries = 0;
  } catch (e) {
    if (my !== seq) return;
    if (more) toast(`More did not load: ${api.explain(e, 'The list')}`, { kind: 'bad' });
    else {
      L.err = e;
      // asked again by itself 5, 15 and 45 seconds later, then only on Retry
      if (L.tries < BACKOFF.length) { const n = L.tries++; autoT = setTimeout(() => { autoT = 0; if (live && L.err) load(); }, BACKOFF[n]); }
    }
  } finally {
    if (my === seq) { clearTimeout(lateT); L.loading = false; L.more = false; paintBody(); }
  }
}

async function open(it, b) {
  if (it.kind === 'question') { openMilo({ question: it.question, opener: b, symbol: (it.tickers || [])[0] || '', about: 'Saved research' }); return; }
  if (it.kind === 'conversation') {
    // the saved copy is read now, not with the list: a conversation and its sources can be long
    b.disabled = true;
    try { const r = await lib.get(it.id); await openSaved(r.item, { opener: b }); }
    catch (e) { toast(`It did not open: ${api.explain(e, 'The conversation')}`, { kind: 'bad' }); }
    finally { b.disabled = false; }
    return;
  }
  const to = lib.routeOf(it); if (to) go(to);
}
function onClick(e) {
  const t = (q) => e.target.closest(q);
  let b;
  if ((b = t('[data-lib-kind]'))) { L.kind = b.dataset.libKind; L.next = null; armed = null; load(); return; }
  if ((b = t('[data-lib-retry]'))) { L.tries = 0; load(); return; }
  if ((b = t('[data-lib-more]'))) { load({ more: true }); return; }
  if ((b = t('[data-lib-open]'))) { const it = L.items[Number(b.dataset.libOpen)]; if (it) open(it, b); return; }
  if ((b = t('[data-lib-rename]'))) { const it = L.items[Number(b.dataset.libRename)]; if (it) renameSheet(it, b); return; }
  if ((b = t('[data-lib-keep]'))) { armed = null; paintBody(); return; }
  if ((b = t('[data-lib-del]'))) {
    const it = L.items[Number(b.dataset.libDel)]; if (!it) return;
    // two presses: the first asks, the second deletes everywhere (there is one copy, the account's)
    if (armed !== it.id) { armed = it.id; paintBody(); const y = mainEl.querySelector(`[data-lib-item="${CSS.escape(it.id)}"] [data-lib-del]`); if (y) y.focus(); return; }
    armed = null;
    // the delete tells every Save button and this list (core/library.js), which reloads itself
    lib.remove(it).then(() => toast(`Deleted “${it.name || 'it'}” from Saved research.`),
      (e2) => { paintBody(); toast(`It was not deleted: ${api.explain(e2, 'Deleting')}`, { kind: 'bad' }); });
    return;
  }
  if ((b = t('[data-sv-ask]'))) { const x = ((L.guest || {}).items || [])[Number(b.dataset.svAsk)]; if (x) openMilo({ question: x.question, opener: b, symbol: x.symbol || '', about: 'Saved research' }); return; }
  if ((b = t('[data-sv-route]'))) { const r = ROUTES[Number(b.dataset.svRoute)]; openMilo({ opener: b, about: 'Saved research' }).then(() => { if (r.milo === 'deep') { const d = document.querySelector('[data-v2-milo-deep]'); if (d) d.focus(); } }); return; }
  if ((b = t('[data-sv-forget]'))) {
    const x = ((L.guest || {}).items || [])[Number(b.dataset.svForget)]; if (!x) return;
    forget(x).then((undo) => { load(); toast('Forgotten.', undo ? { action: 'Undo', run: () => Promise.resolve(undo()).then(load) } : {}); },
      (e2) => toast(`It was not forgotten: ${e2.message || 'try again'}.`, { kind: 'bad' }));
  }
}
function onInput(e) {
  if (!e.target.matches('[data-lib-search]')) return;
  clearTimeout(typeT);
  typeT = setTimeout(() => { const v = e.target.value.trim(); if (v === L.search) return; L.search = v; L.next = null; armed = null; load(); }, 250);
}
// a save, a rename or a delete anywhere (a Dossier's Save, the rename sheet) shows here at once
const onLibrary = () => { if (live && mainEl && store.signedIn()) load(); };

export async function render(main, route) {
  live = true; mainEl = main; L = fresh(); armed = null;
  const p = (route && route.params) || {};
  if (lib.KINDS.includes(p.kind)) L.kind = p.kind;
  document.title = 'Saved research, Optic';
  provideContext(() => ({ view: 'saved', saved_research: (L.items || []).slice(0, 20).map((x) => ({ kind: x.kind, name: x.name, tickers: x.tickers, saved: x.created_at })) }));
  if (wired !== main) { main.addEventListener('click', onClick); main.addEventListener('input', onInput); wired = main; }
  window.removeEventListener('v2:library', onLibrary); window.addEventListener('v2:library', onLibrary);
  paint(); load();
}
export function dispose() { live = false; clearTimeout(lateT); clearTimeout(autoT); clearTimeout(typeT); window.removeEventListener('v2:library', onLibrary); }
export const _test = { item, routeOf: lib.routeOf, state: () => L, load };
