// Optic v2: boot, routing and the app-wide controls. device.js is imported
// first so a pending account switch is finished before any store is read.
import { keepDeviceSession, bringGuestThings, keepGuestThingsOut, switchedSaid } from './core/device.js';
import { CLASSIC } from './core/classic.js';
import { $, html, render, announce } from './core/dom.js';
import * as api from './core/api.js';
import * as store from './core/store.js';
import * as router from './core/router.js';
import * as scrollmem from './core/scrollmem.js';
import * as prefs from './core/prefs.js';
import * as shell from './ui/shell.js';
import * as palette from './ui/palette.js';
import * as drawer from './ui/drawer.js';
import { openShortcuts } from './ui/shortcuts.js';
import * as motion from './ui/motion.js';
import { openMilo, resetContext, checkAvailability, markButtons } from './ui/milo.js';
import { toggleWatch } from './ui/company.js';
import { linkHome } from './core/homelink.js';
import { toast } from './ui/toast.js';
import { hrefFor } from './nav.js';
import * as settingsPage from './pages/settings.js';
import * as signin from './pages/signin.js';
import { startReset } from './pages/signin.js';
import { handleAuthLinks } from './core/authlinks.js';
import { areaNotice } from './core/legal.js';
import { watchBuild, isClosed } from './core/build.js';
import { watchStatus } from './core/status.js';
import { openReport } from './pages/settings.js';
import * as bridge from './pages/bridge.js';
import { watchTables } from './ui/align.js';
import { startUnread } from './core/unread.js';
import { startStrips } from './ui/strips.js';

// Home is the research workspace (Market Overview by default); pages/home.js supplies its blocks
// Each page's module is fetched the first time it is opened, not with the shell: a first visit on a phone
// downloaded all 78 modules (444 KB compressed) whatever the page (backlog task 14, 2026-10-20). The import map
// in index.html gives import() the same versioned URLs as a static import, so a module is never loaded twice.
// A page's modules beyond the shell (index.html's v2-graph), asked for side by side before its import() runs.
const GRAPH = (() => { try { return JSON.parse((document.getElementById('v2-graph') || {}).textContent || '{}'); } catch (e) { return {}; } })();
function preloadGraph(name) {
  (GRAPH[name] || []).forEach((url) => {
    if (document.querySelector(`link[rel="modulepreload"][href="${url}"]`)) return;
    const l = document.createElement('link'); l.rel = 'modulepreload'; l.href = url; document.head.appendChild(l);
  });
}
const lazy = (load, name) => { let p = null; return () => (p || (p = (preloadGraph(name), load()).catch((e) => { p = null; throw e; }))); };
const P = {
  workspace: lazy(() => import('./pages/workspace.js'), 'workspace'), dossier: lazy(() => import('./pages/dossier.js'), 'dossier'), options: lazy(() => import('./pages/options.js'), 'options'),
  investing: lazy(() => import('./pages/investing.js'), 'investing'), earnings: lazy(() => import('./pages/earnings.js'), 'earnings'), financials: lazy(() => import('./pages/financials.js'), 'financials'),
  news: lazy(() => import('./pages/news.js'), 'news'), chart: lazy(() => import('./pages/chart.js'), 'chart'), read: lazy(() => import('./pages/read.js'), 'read'),
  macro: lazy(() => import('./pages/macro.js'), 'macro'), indices: lazy(() => import('./pages/indices.js'), 'indices'), instrument: lazy(() => import('./pages/instrument.js'), 'instrument'),
  explore: lazy(() => import('./pages/explore.js'), 'explore'), scan: lazy(() => import('./pages/scan.js'), 'scan'), insiders: lazy(() => import('./pages/insiders.js'), 'insiders'),
  analysts: lazy(() => import('./pages/analysts.js'), 'analysts'), compare: lazy(() => import('./pages/compare.js'), 'compare'), tracker: lazy(() => import('./pages/tracker.js'), 'tracker'),
  paper: lazy(() => import('./pages/paper.js'), 'paper'), retirement: lazy(() => import('./pages/retirement.js'), 'retirement'), brokerage: lazy(() => import('./pages/brokerage.js'), 'brokerage'),
  reports: lazy(() => import('./pages/reports.js'), 'reports'), watchlist: lazy(() => import('./pages/watchlist.js'), 'watchlist'), alerts: lazy(() => import('./pages/alerts.js'), 'alerts'),
  legal: lazy(() => import('./pages/legalpages.js'), 'legalpages'), earningsweek: lazy(() => import('./pages/earningsweek.js'), 'earningsweek'),
  dossierstart: lazy(() => import('./pages/dossierstart.js'), 'dossierstart'),
  sheet: lazy(() => import('./pages/sheet.js'), 'sheet'),
};
const PAGES = { home: P.workspace, overview: P.dossier, swing: P.options, long: P.investing, earnings: P.earnings, financials: P.financials, news: P.news, chart: P.chart, brief: P.read, market: P.macro, indices: P.indices, instrument: P.instrument, explore: P.explore, scan: P.scan, insiders: P.insiders, analysts: P.analysts, settings: () => settingsPage, compare: P.compare, tracker: P.tracker, paper: P.paper, roth: P.retirement, brokerage: P.brokerage, reports: P.reports, usage: P.reports, accounts: P.reports, metrics: P.reports, watchlist: P.watchlist, alerts: P.alerts, signin: () => signin, terms: P.legal, privacy: P.legal, earningsweek: P.earningsweek, dossierstart: P.dossierstart, sheet: P.sheet };
// The pages a reader most often opens next, fetched (not run) once the first page has settled and the
// connection is not marked as costly: a later move to them does not wait on the network.
function warmNext() {
  const c = navigator.connection || {};
  if (c.saveData || /2g/.test(c.effectiveType || '')) return;
  ['dossier', 'chart', 'options', 'watchlist', 'workspace', 'compare'].forEach((n) => {
    preloadGraph(n);
    const url = ((JSON.parse((document.querySelector('script[type="importmap"]') || {}).textContent || '{}').imports) || {})[`/v2/js/pages/${n}.js`];
    if (url && !document.querySelector(`link[rel="modulepreload"][href="${url}"]`)) { const l = document.createElement('link'); l.rel = 'modulepreload'; l.href = url; document.head.appendChild(l); }
  });
}
let warmed = false;
// four seconds after the first page has drawn, in idle time
const warmLater = () => { if (warmed) return; warmed = true; setTimeout(() => { const run = () => warmNext(); if (window.requestIdleCallback) requestIdleCallback(run, { timeout: 4000 }); else run(); }, 4000); };
let SHOW = 0;
let current = null;   // { page, view, route }
let noticeWatch = null;

const app = {
  /** After sign in or out: settle whose browser this is, then reload state. */
  async settleAuth({ said = '', next } = {}) {
    await store.loadMe();
    const r = await deviceCheck();
    if (r === 'reload') return;
    await afterAuth();
    if (said === 'in' && store.state.user) toast(`Signed in as ${store.state.user.email}.`);
    if (said === 'out') toast('Signed out.');
    if (next) router.go(next);
  },
};

async function deviceCheck() {
  return keepDeviceSession(store.state.user, (ask) => {
    drawer.open({
      kicker: 'Welcome back', title: 'Keep what you made on this browser?', keep: true,
      body: html`<p>This browser has ${ask.things.join(', ')} from before you signed in.</p>
        <div class="cluster"><button type="button" class="btn btn-primary" data-v2-guest="bring">Bring them into my account</button>
        <button type="button" class="btn" data-v2-guest="keep">Leave them for the next guest</button></div>`,
    });
  });
}

async function afterAuth() {
  const me = store.state.me || {};
  shell.setFlags({ admin: !!me.admin, brokerage: false });
  await store.loadLists();
  if (store.signedIn()) {
    api.get('/api/brokerage/status', { ttl: 60000 }).then((st) => {
      if (st && st.available) { shell.setFlags({ brokerage: true }); if (current) shell.paint(current.route); }
    }).catch(() => {});
  }
  if (current) shell.paint(current.route);
  if (current && current.page.onAuth) current.page.onAuth(current.view);
}

// The thin line under the top bar while the page has a section still loading (ui/motion.js watchLoading)
let LINE = null;
function pageLine() {
  if (!LINE) { LINE = document.createElement('div'); LINE.className = 'page-line'; LINE.setAttribute('aria-hidden', 'true'); document.body.appendChild(LINE); }
  return LINE;
}
/** Run `fn` once `sel` is in `view`: at the next frame if the page drew at once, or when it does, within a second. */
function whenDrawn(view, sel, fn) {
  requestAnimationFrame(() => {
    if (view.querySelector(sel)) { fn(); return; }
    const mo = new MutationObserver(() => { if (view.querySelector(sel)) { mo.disconnect(); requestAnimationFrame(fn); } });
    mo.observe(view, { childList: true, subtree: true });
    setTimeout(() => mo.disconnect(), 1000);
  });
}

async function show(route) {
  // v2 closed to this reader since the page loaded: the move lands on the classic app instead
  if (isClosed()) { location.href = `${CLASSIC}${location.hash}`; return; }
  if (route.view === 'signin' && store.signedIn() && (route.params || {}).mode !== 'reset') { router.go('#/'); return; }
  // the page's module: at once once fetched; on a first visit, fetched now (a later route wins a race)
  const my = ++SHOW, load = PAGES[route.view];
  let page = bridge;
  if (load) {
    try { page = await load(); }
    catch (e) {
      if (my !== SHOW) return;
      const v = $('#main'); render(v, html`<div class="page-view"><div class="state err" role="alert"><p class="t-h3">This page did not load</p><p>Its code could not be fetched. Check the connection and try again.</p><a class="btn" href="${hrefFor(route.view, route.symbol)}">Try again</a></div></div>`);
      return;
    }
    if (my !== SHOW) return;
  }
  if (current && current.page.dispose) current.page.dispose();
  drawer.close({ silent: true, route: true });
  palette.close({ silent: true });
  const main = $('#main');
  // between two pages of one strip only: the same page drawn again (Try again, a sign-in) gets no entrance
  const again = current && current.route.view === route.view && current.route.symbol === route.symbol && current.route.section === route.section;
  const tabsWere = again ? null : motion.tabsBefore(main.querySelector('.page-view'));
  const view = document.createElement('div');
  view.className = 'page-view';
  main.replaceChildren(view);
  motion.watchLoading(view, pageLine());
  // The page's own notice (not advice, hypothetical performance), where Classic puts it: below the
  // answer, above the evidence, i.e. after the page's first section. Pages repaint themselves, so an
  // observer puts it back after every paint; no page can drop it.
  if (noticeWatch) noticeWatch.disconnect();
  const notice = areaNotice(route.view);
  if (notice) {
    const place = () => {
      if (view.querySelector(':scope .legal-area')) return;
      const holder = document.createElement('div'); render(holder, notice);
      const first = view.querySelector(':scope > section.section, :scope > .section');
      const anchor = first ? first.nextSibling : null;
      if (first) view.insertBefore(holder.firstElementChild, anchor); else if (view.firstElementChild) view.appendChild(holder.firstElementChild);
    };
    noticeWatch = new MutationObserver(place); noticeWatch.observe(view, { childList: true });
  }
  current = { page, view, route };
  shell.paint(route);
  // Milo forgets the last page before this one renders (it registers its own context as it renders)
  resetContext(route);
  scrollmem.arrive();
  const rendered = Promise.resolve(page.render(view, route, app));
  // once the first page has drawn, the likeliest next pages are fetched in quiet time
  rendered.then(warmLater, () => {});
  rendered.catch((e) => {
    console.error(e);
    render(view, html`<div class="state err" role="alert"><p class="t-h3">This page did not load</p><p>${e.message || 'An error stopped it.'}</p><a class="btn" href="${hrefFor(route.view, route.symbol)}">Try again</a></div>`);
  });
  // a tab strip's bar slides (if the press has not moved it already) and the content fades in, once drawn (ui/motion.js)
  if (tabsWere) whenDrawn(view, 'nav.tabs', () => motion.tabsAfter(view, tabsWere));
  // Focus the page's heading so a screen reader hears where it landed.
  requestAnimationFrame(() => {
    const h = drawer.isOpen() ? null : view.querySelector('h1');
    if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
    announce(document.title.replace(', Optic', ''));
  });
  if (route.view === 'home') document.title = 'Optic';
}

function accountBody() {
  const u = store.state.user;
  if (!u) {
    return html`<p>Signed out. Watchlists and watches are kept in this browser.</p><a class="btn btn-primary" href="#/signin">Sign in or create an account</a>`;
  }
  const plan = store.plan();
  return html`<dl class="kv"><div><dt>Name</dt><dd>${u.name || `${u.first_name || ''} ${u.last_name || ''}`}</dd></div><div><dt>Email</dt><dd>${u.email}</dd></div>
      <div><dt>Plan</dt><dd>${plan.label || 'Free'}${(store.state.me || {}).admin ? ', owner' : ''}</dd></div></dl>
    ${u.email_verified ? '' : html`<p class="stale">Your email is not verified yet. The link is in your inbox.</p>`}
    <nav class="more-list" aria-label="Account"><a class="rail-row" href="#/watchlist">Watchlists</a><a class="rail-row" href="#/settings">Settings</a><a class="rail-row" href="${CLASSIC}#/scan">Saved research, in the classic app</a></nav>
    <button type="button" class="btn" data-v2-signout>Sign out</button>`;
}

// Copy a ticker, or the price as the page shows it with the words that say when it is from ("347.73, Close of Fri Oct
// 23"), never a figure the page is not showing. The menu it came from closes; the toast says what was copied.
async function copyFrom(b) {
  const sym = b.dataset.v2Copy || b.dataset.v2CopyPrice;
  let text = sym;
  if (b.dataset.v2CopyPrice) {
    const box = document.querySelector(b.dataset.v2CopyFrom || '.dhead .dh-price');
    const px = box && (box.querySelector('.dh-px, .t-display') || {}).textContent;
    if (!px) { toast(`No price for ${sym} on screen yet.`); return; }
    const chg = ((box.querySelector('.dh-chg') || {}).textContent || '').trim(), when = ((box.querySelector('.dh-ext') || {}).textContent || '').trim();
    text = `${sym} ${px.trim()}${chg ? ` ${chg}` : ''}${when ? `, ${when}` : ''}`;
  }
  const menu = b.closest('details.menu'); if (menu) { menu.open = false; const s = menu.querySelector('summary'); if (s) s.focus(); }
  try { await navigator.clipboard.writeText(text); toast(`Copied: ${text}`); } catch (e) { toast('The browser did not allow copying. Select the text on the page instead.'); }
}

function wireGlobal() {
  document.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s);
    let b;
    // a tab answers its press at once; the address change that follows loads the page (ui/motion.js tabPressed)
    if ((b = t('nav.tabs a[href^="#"]')) && !e.defaultPrevented && e.button === 0 && !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)) motion.tabPressed(b);
    if ((b = t('[data-v2-report-open]'))) { openReport(b, current ? document.title.replace(', Optic', '') : 'Optic'); return; }
    if ((b = t('[data-v2-rail-collapse]'))) { const on = !shell.railTight(); shell.setRailTight(on); b.setAttribute('aria-pressed', String(on)); return; }
    if (t('[data-v2-use-classic]')) { e.preventDefault(); document.cookie = 'optic_ui=classic; path=/; max-age=31536000; samesite=lax'; location.href = `${CLASSIC}${location.hash}`; return; }
    if ((b = t('[data-v2-legal-more]'))) { const full = $('#legal-full'); const open = full.hidden; full.hidden = !open; b.setAttribute('aria-expanded', String(open)); b.textContent = open ? 'Hide the full disclaimer' : 'Full disclaimer'; return; }
    if ((b = t('[data-v2-shortcuts]'))) { openShortcuts(b); return; }
    if ((b = t('[data-v2-copy]')) || (b = t('[data-v2-copy-price]'))) { copyFrom(b); return; }
    if ((b = t('[data-v2-open-palette]'))) { e.preventDefault(); palette.open(b, { symbol: current && current.route.symbol }); return; }
    if ((b = t('[data-v2-milo]'))) {
      openMilo({ question: b.dataset.v2Milo || '', opener: b, about: b.dataset.v2MiloCtx || '', symbol: b.dataset.v2MiloSym || '' });
      return;
    }
    if ((b = t('[data-v2-watch]'))) { e.preventDefault(); await toggleWatch(b.dataset.v2Watch); return; }
    if ((b = t('[data-v2-homelink]'))) {
      const sym = b.dataset.v2Homelink, onHome = current && current.route.view === 'home';
      drawer.close({ silent: true });
      if (linkHome(sym)) { toast(`Home's linked panels now follow ${sym}.`); if (!onHome) router.go('#/'); }
      return;
    }
    if ((b = t('[data-v2-account]'))) { drawer.open({ kicker: 'Account', title: store.state.user ? (store.state.user.first_name || 'Your account') : 'Not signed in', body: accountBody(), opener: b }); return; }
    if ((b = t('[data-v2-more]'))) { drawer.open({ kicker: 'Sections', title: 'More', body: shell.moreBody(), opener: b }); return; }
    if (t('[data-v2-signout]')) { drawer.close({ silent: true }); await store.signOut(); await app.settleAuth({ said: 'out', next: '#/' }); return; }
    if ((b = t('[data-v2-guest]'))) {
      drawer.close({ silent: true, force: true });
      if (b.dataset.v2Guest === 'keep') { keepGuestThingsOut(); return; }
      bringGuestThings();
      // the guest's lists join the account as lists: a name the account has merges into it, a new
      // name becomes a list while the plan has room, the rest go into the first list (account.py)
      let lists = [];
      try { const raw = JSON.parse(localStorage.getItem('optic.watchlists.v1') || 'null'); lists = raw && Array.isArray(raw.lists) ? raw.lists.filter((l) => (l.symbols || []).length).map((l) => ({ name: l.name, symbols: l.symbols })) : [{ name: 'Watchlist', symbols: JSON.parse(localStorage.getItem('optic.chart.watch.v1') || '[]') }].filter((l) => l.symbols.length); } catch (err) { lists = []; }
      if (lists.length) {
        try {
          const r = await api.post('/api/watchlists/adopt', { lists });
          const made = (r && r.created) || [], merged = (r && r.merged) || [];
          toast(`Brought ${r && r.added || 0} name${(r && r.added) === 1 ? '' : 's'} into your account${made.length ? `, as ${made.length} new list${made.length === 1 ? '' : 's'}` : ''}.${merged.length ? ` The plan's list limit put ${merged.map((m) => m.name).join(', ')} into ${merged[0].into}.` : ''}`);
        } catch (err) { toast(`${api.explain(err, 'Bringing your lists across')} They are still in this browser; sign out and in again to retry.`, { kind: 'bad' }); }
      }
      // theses and valuation scenarios too, as the classic app's adoptLocalTheses
      // and valuationAccountLoad do; the server never overwrites one the account has
      await adoptKeyed('optic.thesis.v1', '/api/theses/adopt', 'theses', (n) => `Brought ${n} thesis${n === 1 ? '' : 'es'} into your account.`);
      await adoptKeyed('optic.valuation.v1', '/api/valuations/adopt', 'valuations', (n) => `Brought scenarios for ${n} name${n === 1 ? '' : 's'} into your account.`);
      await afterAuth();
      if (current) show(current.route);
      return;
    }
    if ((b = t('[data-v2-retry]')) && current) {
      const fn = current.page.retry && current.page.retry[b.dataset.v2Retry];
      if (fn) fn(current.view, current.route); else show(current.route);
    }
  });
  // an open ⋯ or Indicators menu closes on a click elsewhere, or on Escape (focus returns to its button)
  document.addEventListener('click', (e) => {
    document.querySelectorAll('details.menu[open]').forEach((d) => { if (!d.contains(e.target)) d.open = false; });
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const d = e.target.closest && e.target.closest('details.menu[open]');
    if (d) { d.open = false; const s = d.querySelector('summary'); if (s) s.focus(); }
  });
  // the phone's view selector in a tab list (pages/tabs.js)
  document.addEventListener('change', (e) => {
    const sel = e.target.closest && e.target.closest('select[data-v2-tabsel]');
    if (!sel || !sel.value) return;
    if (sel.value.startsWith('#')) location.hash = sel.value.slice(1); else location.href = sel.value;
  });
  document.addEventListener('keydown', (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || '') || (e.target && e.target.isContentEditable);
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); if (palette.isOpen()) palette.close(); else { const f = document.activeElement; const seed = f && f.matches && f.matches('input[type=search], input[type=text]:not([name=password])') && !f.closest('.palette') ? f.value : ''; palette.open(null, { seed, symbol: current && current.route.symbol }); } }
    else if (e.key === '/' && !typing && !drawer.isOpen()) { e.preventDefault(); palette.open(null, { symbol: current && current.route.symbol }); }
    else if (e.key === '?' && !typing && !e.metaKey && !e.ctrlKey && !drawer.isOpen() && !palette.isOpen()) { e.preventDefault(); openShortcuts(document.activeElement); }
  });
  store.subscribe((what) => {
    if (what !== 'lists') return;
    // every Watch button on screen follows the list
    document.querySelectorAll('.btn[data-v2-watch]').forEach((b) => {
      const on = store.isFollowed(b.dataset.v2Watch);
      b.setAttribute('aria-pressed', String(on)); b.textContent = on ? 'Watching' : 'Watch';
    });
    if (current && current.page.onLists) current.page.onLists(current.view);
  });
}

async function boot() {
  prefs.applyTheme(); prefs.applyScale(); prefs.applyMotion();
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => prefs.applyTheme());
  // another tab (or the classic app in one) changed a setting
  window.addEventListener('storage', (e) => { if (/^optic\.(theme|ui\.scale\.v1|v2\.motion\.v1)$/.test(e.key || '')) { prefs.applyTheme(); prefs.applyScale(); prefs.applyMotion(); } });
  shell.mount($('#app'));
  watchTables($('#app'));   // every shared table aligned by what its columns hold (ui/align.js)
  wireGlobal();
  watchBuild();
  watchStatus();
  await store.loadMe();
  const r = await deviceCheck();
  if (r === 'reload') return;
  // links from email and sign-in providers (?verify, ?reset, ?auth, ?auth_error), read once,
  // after the account is settled so a reload cannot swallow them
  const link = await handleAuthLinks().catch(() => null);
  if (link && link.refresh) await store.loadMe();
  if (store.state.auth === 'unknown') toast('Optic could not check your sign-in. Showing this browser\'s lists for now.');
  await afterAuth();
  checkAvailability();
  startUnread(shell.setUnread);
  startStrips();   // sideways strips: edge arrows, the wheel and a mouse drag (Classic parity B3)   // the bell and the phone bar's Watchlist count (signed in only)
  scrollmem.start();
  router.onRoute(show);
  if (link && link.reset) { startReset(link.reset); history.replaceState(history.state, '', `${location.pathname}${location.search}#/signin?mode=reset`); }
  else if (link && link.signin && !store.signedIn()) history.replaceState(history.state, '', `${location.pathname}${location.search}#/signin`);
  else if (link && link.signedIn && link.hash) history.replaceState(history.state, '', `${location.pathname}${location.search}${link.hash}`);
  router.start();
  if (link && link.signedIn && store.state.user) toast(`Signed in as ${store.state.user.email}.`);
  const said = switchedSaid();
  if (said === 'in') toast('Signed in. This browser now shows your account\'s things.');
  if (said === 'out') toast('Signed out. Your account\'s things are put away on this browser.');
}

boot();

async function adoptKeyed(key, url, field, said) {
  let local = null;
  try { local = JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) { local = null; }
  if (!local || typeof local !== 'object' || !Object.keys(local).length) return;
  try { const out = await api.post(url, { [field]: local }); const n = ((out || {}).adopted || []).length; if (n) toast(said(n)); }
  catch (e) { /* the browser copies are untouched; the classic app tries again on its next load */ }
}
