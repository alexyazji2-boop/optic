// Optic v2: boot, routing and the app-wide controls. device.js is imported
// first so a pending account switch is finished before any store is read.
import { keepDeviceSession, bringGuestThings, keepGuestThingsOut, switchedSaid } from './core/device.js';
import { $, html, render, announce } from './core/dom.js';
import * as api from './core/api.js';
import * as store from './core/store.js';
import * as router from './core/router.js';
import * as prefs from './core/prefs.js';
import * as shell from './ui/shell.js';
import * as palette from './ui/palette.js';
import * as drawer from './ui/drawer.js';
import { openMilo } from './ui/milo.js';
import { toggleWatch } from './ui/company.js';
import { toast } from './ui/toast.js';
import { hrefFor } from './nav.js';
import * as home from './pages/home.js';
import * as dossier from './pages/dossier.js';
import * as options from './pages/options.js';
import * as investing from './pages/investing.js';
import * as earnings from './pages/earnings.js';
import * as financials from './pages/financials.js';
import * as news from './pages/news.js';
import * as chartPage from './pages/chart.js';
import * as readPage from './pages/read.js';
import * as macroPage from './pages/macro.js';
import * as indicesPage from './pages/indices.js';
import * as instrumentPage from './pages/instrument.js';
import * as explorePage from './pages/explore.js';
import * as scanPage from './pages/scan.js';
import * as insidersPage from './pages/insiders.js';
import * as analystsPage from './pages/analysts.js';
import * as settingsPage from './pages/settings.js';
import * as comparePage from './pages/compare.js';
import * as trackerPage from './pages/tracker.js';
import * as paperPage from './pages/paper.js';
import * as retirementPage from './pages/retirement.js';
import * as brokeragePage from './pages/brokerage.js';
import * as reportsPage from './pages/reports.js';
import * as watchlist from './pages/watchlist.js';
import * as alerts from './pages/alerts.js';
import * as signin from './pages/signin.js';
import * as bridge from './pages/bridge.js';

const PAGES = { home, overview: dossier, swing: options, long: investing, earnings, financials, news, chart: chartPage, brief: readPage, market: macroPage, indices: indicesPage, instrument: instrumentPage, explore: explorePage, scan: scanPage, insiders: insidersPage, analysts: analystsPage, settings: settingsPage, compare: comparePage, tracker: trackerPage, paper: paperPage, roth: retirementPage, brokerage: brokeragePage, reports: reportsPage, usage: reportsPage, accounts: reportsPage, watchlist, alerts, signin };
let current = null;   // { page, view, route }

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

function show(route) {
  if (current && current.page.dispose) current.page.dispose();
  drawer.close({ silent: true, route: true });
  palette.close({ silent: true });
  if (route.view === 'signin' && store.signedIn()) { router.go('#/'); return; }
  const page = PAGES[route.view] || bridge;
  const main = $('#main');
  const view = document.createElement('div');
  view.className = 'page-view';
  main.replaceChildren(view);
  current = { page, view, route };
  shell.paint(route);
  shell.setMiloContext(route.symbol ? `${route.symbol} Dossier, Overview` : 'this page', route.symbol || '', '');
  window.scrollTo(0, 0);
  Promise.resolve(page.render(view, route, app)).catch((e) => {
    console.error(e);
    render(view, html`<div class="state err" role="alert"><p class="t-h3">This page did not load</p><p>${e.message || 'An error stopped it.'}</p><a class="btn" href="${hrefFor(route.view, route.symbol)}">Try again</a></div>`);
  });
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
    <nav class="more-list" aria-label="Account"><a class="rail-row" href="#/watchlist">Watchlists</a><a class="rail-row" href="#/settings">Settings</a><a class="rail-row" href="/#/read">Saved research, in the current app</a></nav>
    <button type="button" class="btn" data-v2-signout>Sign out</button>`;
}

function wireGlobal() {
  document.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s);
    let b;
    if ((b = t('[data-v2-open-palette]'))) { e.preventDefault(); palette.open(b); return; }
    if ((b = t('[data-v2-milo]'))) {
      openMilo({ question: b.dataset.v2Milo || '', contextLabel: b.dataset.v2MiloCtx || 'this page', symbol: b.dataset.v2MiloSym || '', opener: b });
      return;
    }
    if ((b = t('[data-v2-watch]'))) { e.preventDefault(); await toggleWatch(b.dataset.v2Watch); return; }
    if ((b = t('[data-v2-account]'))) { drawer.open({ kicker: 'Account', title: store.state.user ? (store.state.user.first_name || 'Your account') : 'Not signed in', body: accountBody(), opener: b }); return; }
    if ((b = t('[data-v2-more]'))) { drawer.open({ kicker: 'Sections', title: 'More', body: shell.moreBody(), opener: b }); return; }
    if (t('[data-v2-signout]')) { drawer.close({ silent: true }); await store.signOut(); await app.settleAuth({ said: 'out', next: '#/' }); return; }
    if ((b = t('[data-v2-guest]'))) {
      drawer.close({ silent: true, force: true });
      if (b.dataset.v2Guest === 'keep') { keepGuestThingsOut(); return; }
      bringGuestThings();
      // the guest's symbols join the account's lists, as the classic app does on load
      let syms = [];
      try { const raw = JSON.parse(localStorage.getItem('optic.watchlists.v1') || 'null'); syms = raw && Array.isArray(raw.lists) ? raw.lists.flatMap((l) => l.symbols || []) : JSON.parse(localStorage.getItem('optic.chart.watch.v1') || '[]'); } catch (err) { syms = []; }
      if (syms.length) { try { await api.post('/api/watchlists/adopt', { symbols: [...new Set(syms)] }); toast(`Brought ${new Set(syms).size} names into your account.`); } catch (err) { toast(api.explain(err, 'Bringing them across'), { kind: 'bad' }); } }
      await afterAuth();
      if (current) show(current.route);
      return;
    }
    if ((b = t('[data-v2-retry]')) && current) {
      const fn = current.page.retry && current.page.retry[b.dataset.v2Retry];
      if (fn) fn(current.view, current.route); else show(current.route);
    }
  });
  document.addEventListener('keydown', (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || '') || (e.target && e.target.isContentEditable);
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); if (palette.isOpen()) palette.close(); else palette.open(); }
    else if (e.key === '/' && !typing && !drawer.isOpen()) { e.preventDefault(); palette.open(); }
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
  prefs.applyTheme(); prefs.applyScale();
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => prefs.applyTheme());
  // another tab (or the classic app in one) changed a setting
  window.addEventListener('storage', (e) => { if (/^optic\.(theme|ui\.scale\.v1)$/.test(e.key || '')) { prefs.applyTheme(); prefs.applyScale(); } });
  shell.mount($('#app'));
  wireGlobal();
  await store.loadMe();
  const r = await deviceCheck();
  if (r === 'reload') return;
  if (store.state.auth === 'unknown') toast('Optic could not check your sign-in. Showing this browser\'s lists for now.');
  await afterAuth();
  router.onRoute(show);
  router.start();
  const said = switchedSaid();
  if (said === 'in') toast('Signed in. This browser now shows your account\'s things.');
  if (said === 'out') toast('Signed out. Your account\'s things are put away on this browser.');
}

boot();
