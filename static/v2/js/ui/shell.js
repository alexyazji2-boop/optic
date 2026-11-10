// The frame around every page: the labelled rail (destinations only; a
// group's pages are its page tabs, never listed twice), the top bar
// (search, Ask Milo, account) and the phone bar. Pages render into #main.
import { html, render, $, $$ } from '../core/dom.js';
import { icon, brandMark } from './icons.js';
import { footer as legalFooter } from '../core/legal.js';
import { GROUPS, SETTINGS, MOBILE_TABS, visibleGroups, hrefFor, groupOf, RESEARCH, LISTS, RAIL_MORE, researchHref } from '../nav.js';
import { state as store, openedNow } from '../core/store.js';

let flags = { admin: false, brokerage: false };
export function setFlags(f) { flags = Object.assign(flags, f); }
export const getFlags = () => ({ ...flags });
// Collapsed to icons, remembered under the classic key (optic.rail.tight.v2: '1' or '0').
const RAIL_KEY = 'optic.rail.tight.v2';
export function railTight() { try { return localStorage.getItem(RAIL_KEY) === '1'; } catch (e) { return false; } }
export function setRailTight(on) { try { localStorage.setItem(RAIL_KEY, on ? '1' : '0'); } catch (e) { /* private mode */ } const sh = $('.shell'); if (sh) sh.classList.toggle('is-tight', on); }

// The page last open in each section on this visit (the classic app's NAV_LAST, kept in memory as it was): a
// section's button returns to it, so leaving Markets on Macro and coming back is Macro, not Markets' first page.
const NAV_LAST = {};
// the company the rail and the phone bar point at, as last painted: More's Research entries follow it, so they match
// the bar's Research tab on a company's page (the visit's recents alone lagged behind the quote, and More said the
// company search while the bar said the company; round two's live run, 2026-11-10)
let PAINTED_SYM = null;
function groupHref(g, symbol) {
  const page = g.pages.find((p) => p.view === NAV_LAST[g.id]) || g.pages[0];
  // with no company open, Dossier's own start page rather than the search (owner, 2026-10-21)
  if (g.symbol) return symbol ? (page === g.pages[0] ? `#/${encodeURIComponent(symbol)}` : hrefFor(page.view, symbol)) : '#/dossier';
  return hrefFor(page.view, symbol);
}
// What each page is for, in the More sheet (the classic app's SUB_TITLES, said plainly)
const WHAT = {
  compare: 'Two to four tickers side by side', brief: 'The day in markets, macro and the world', market: 'Macro conditions and sector rotation',
  indices: 'The major indexes over the long run', explore: 'Sectors, themes and what is moving', scan: 'Named screens across the ranked list',
  insiders: 'Company insiders and House members\' trades', analysts: 'Rating and price-target changes, newest first',
  tracker: "Optic's own demonstration portfolio", paper: 'Practice trades you enter yourself', roth: 'A rules-based allocation to compare yours against',
  brokerage: 'Your linked accounts, read-only', watchlist: 'The names you follow', alerts: 'What fired on your alerts, and why', saved: 'The research you saved',
  reports: 'What readers reported as broken', usage: 'What the model has cost', accounts: 'Everyone who signed up', metrics: 'Sign-ups, actives, retention and Milo', settings: 'Your account and preferences',
};
/* ---------------- unread alerts: the bell on the top bar, the count on the phone bar's Lists (it opens the Watchlist, where Alerts is a tab) */
let unread = 0;
export function setUnread(n) { unread = Math.max(0, Number(n) || 0); paintUnread(); }
function paintUnread() {
  const words = unread ? `${unread} unread alert${unread === 1 ? '' : 's'}` : '';
  const bell = $('[data-v2-bell]');
  if (bell) {
    bell.hidden = !unread;
    bell.setAttribute('aria-label', unread ? `Alerts, ${words}` : 'Alerts');
    const c = bell.querySelector('.bell-n'); if (c) c.textContent = unread > 9 ? '9+' : String(unread);
  }
  $$('.tabbar [data-v2-tab="lists"]').forEach((t) => {
    let dot = t.querySelector('.tab-n');
    if (!unread) { if (dot) dot.remove(); t.removeAttribute('aria-label'); return; }
    if (!dot) { dot = document.createElement('span'); dot.className = 'tab-n'; dot.setAttribute('aria-hidden', 'true'); t.appendChild(dot); }
    dot.textContent = unread > 9 ? '9+' : String(unread);
    t.setAttribute('aria-label', `Lists. ${words}`);   // starts with the visible word (WCAG 2.5.3); Lists opens the Watchlist, where Alerts is a tab
  });
}
const groupIsV2 = (g) => g.pages.some((p) => p.v2);

// The top bar's and a Dossier header's heights, published for the sticky header (.dstick sits under the top bar)
// and for the page's scroll padding, so a jump to a section lands below both rather than under them.
function trackHeights() {
  if (typeof ResizeObserver !== 'function') return;
  const root = document.documentElement, bar = $('.topbar'), main = $('#main');
  const set = (k, el) => root.style.setProperty(k, `${el ? Math.round(el.getBoundingClientRect().height) : 0}px`);
  let stick = null;
  const ro = new ResizeObserver(() => { set('--topbar-h', bar); set('--dstick-h', stick && stick.isConnected ? stick : null); });
  if (bar) ro.observe(bar);
  // the header is the page view's own child (#main > .page-view > .dstick), drawn as the page paints: watched through
  // the subtree, as `:scope > .dstick` on #main never matched and the height stayed 0 (found by B3, 2026-10-21)
  const find = () => { const s2 = main && main.querySelector(':scope > .page-view > .dstick'); if (s2 === stick) return; if (stick) ro.unobserve(stick); stick = s2; if (stick) ro.observe(stick); else set('--dstick-h', null); };
  if (main) new MutationObserver(find).observe(main, { childList: true, subtree: true });
}
export function mount(app) {
  render(app, html`<a class="skip" href="#main">Skip to content</a>
  <div class="shell ${railTight() ? 'is-tight' : ''}">
    <div class="rail"></div>
    <div class="stage">
      <header class="topbar">
        <a class="brand-sm" href="#/" aria-label="Optic Terminal, Home">${brandMark()}</a>
        <button type="button" class="search-btn" data-v2-open-palette aria-label="Search companies, tickers and pages, or ask Milo">${icon('search')}<span class="sb-long">Search or ask</span><span class="sb-short" aria-hidden="true">Search</span><kbd>⌘K</kbd></button>
        <span class="spacer"></span><span class="session-chip" id="session-chip" role="status" aria-live="off"></span>
        <a class="icon-btn topbar-bell" href="#/alerts" data-v2-bell hidden aria-label="Alerts">${icon('bell')}<span class="bell-n" aria-hidden="true"></span></a>
        <button type="button" class="btn btn-milo btn-sm topbar-milo" data-v2-milo="" data-v2-milo-ctx="" data-v2-milo-sym="" aria-label="Ask Milo"><span class="scout-badge" aria-hidden="true"><span class="scout-badge-fig"></span></span><span class="tm-label" aria-hidden="true">Ask Milo</span></button>
        <button type="button" class="account-btn" data-v2-account aria-haspopup="dialog">Sign in</button>
      </header>
      <main id="main" class="page" tabindex="-1"></main>
      <footer class="legal" id="legal-footer"><p class="app-status"><span id="app-status"></span><button type="button" class="textlink" data-v2-report-open>Report a problem</button></p>${legalFooter()}</footer>
    </div>
  </div>
  <nav class="tabbar" aria-label="Sections"></nav>`);
  trackHeights();
}

/** Paint the rail and phone bar for the current route. */
export function paint(route) {
  const g = route.view === 'settings' ? null : groupOf(route.view);
  if (g && g.pages.some((p) => p.view === route.view)) NAV_LAST[g.id] = route.view;
  // an instrument page (^TNX) has no Dossier: the Dossier link stays on the company opened on this visit; with none,
  // it opens the search, where the Recent list is offered rather than followed
  const sym = (route.view !== 'instrument' && route.symbol) || openedNow() || null;
  PAINTED_SYM = sym;
  const groups = visibleGroups(flags);
  const has = (id) => groups.some((x) => x.id === id);
  const byId = (id) => GROUPS.find((x) => x.id === id);
  const cur = (on) => (on ? html`aria-current="page"` : '');
  const row = (href, ic, label, on, cls = 'rail-row') => html`<a class="${cls}" href="${href}" ${cur(on)}>${icon(ic)}<span>${label}</span></a>`;
  const gid = g ? g.id : null, view = route.view;
  // The owner's rail of 2026-11-09 (nav.js RESEARCH and LISTS), item for item, over today's routes
  const inResearch = gid === 'security' || view === 'dossierstart' || view === 'insiders';
  const research = RESEARCH.map((e) => row(researchHref(e, sym), e.icon, e.label,
    e.filter ? view === 'insiders' : (gid === 'security' && (view === e.view || (e.view === 'overview' && !['financials', 'chart', 'swing'].includes(view)))), 'rail-row rail-sub'));
  const more = RAIL_MORE.filter((m) => (m.group ? has(m.group) : true)).map((m) => row(m.group ? groupHref(byId(m.group), sym) : hrefFor(m.view), m.icon, m.label,
    m.group ? gid === m.group : view === m.view, 'rail-row rail-sub'));
  render($('.rail'), html`<a class="brand" href="#/" aria-label="Optic Terminal, Home">${brandMark()}<span class="brand-word" aria-hidden="true">OPTIC <span>TERMINAL</span></span></a>
    <nav class="rail-nav" aria-label="Sections">
      ${row('#/', 'home', 'Home', view === 'home')}
      <div class="rail-group ${inResearch ? 'is-in' : ''}" role="group" aria-labelledby="rail-research">
        <p class="rail-row rail-head" id="rail-research">${icon('research')}<span>Research</span></p>
        ${research}
      </div>
      ${row(groupHref(byId('market'), sym), 'markets', 'Markets', gid === 'market')}
      ${row(groupHref(byId('discover'), sym), 'discover', 'Discover', gid === 'discover' && view !== 'scan')}
      ${row(groupHref(byId('portfolio'), sym), 'positions', 'Portfolio', gid === 'portfolio')}
      <div class="rail-lists" role="group" aria-labelledby="rail-lists-h">
        <p class="rail-sec rail-lists-h"><span id="rail-lists-h">Lists</span><a class="rail-plus" href="#/watchlist" aria-label="Your lists: open or make one">${icon('plus')}</a></p>
        ${LISTS.map((l) => row(l.href, l.icon, l.label, l.views.includes(view), 'rail-row rail-sub'))}
      </div>
      <div class="rail-more" role="group" aria-labelledby="rail-more-h"><p class="rail-sec" id="rail-more-h">More</p>${more}</div>
    </nav>
    <div class="rail-foot"><a class="rail-row" href="${hrefFor('settings')}" ${route.view === 'settings' ? html`aria-current="page"` : ''}>${icon(SETTINGS.icon)}<span>${SETTINGS.label}</span></a><button type="button" class="rail-row" data-v2-rail-collapse aria-pressed="${railTight()}" aria-label="Collapse">${icon('chev')}<span>Collapse</span></button></div>`);

  // The phone bar: the rail's sections by the rail's names, each to the address the rail's entry opens (nav.js MOBILE_TABS)
  const tabOn = {
    home: view === 'home', security: inResearch && view !== 'insiders', market: gid === 'market',
    discover: gid === 'discover' && view !== 'scan', portfolio: gid === 'portfolio', lists: LISTS.some((l) => l.views.includes(view)),
  };
  const tabHref = { home: '#/', security: researchHref(RESEARCH[0], sym), market: groupHref(byId('market'), sym), discover: groupHref(byId('discover'), sym), portfolio: groupHref(byId('portfolio'), sym), lists: LISTS[0].href };
  render($('.tabbar'), MOBILE_TABS.map((t) => {
    if (t.more) {
      const inMore = view !== 'home' && !Object.values(tabOn).some(Boolean);
      return html`<button type="button" data-v2-more ${inMore ? html`aria-current="page"` : ''}>${icon(t.icon)}<span>${t.label}</span></button>`;
    }
    const key = t.lists ? 'lists' : t.group;
    return html`<a href="${tabHref[key]}" data-v2-tab="${key}" ${tabOn[key] ? html`aria-current="page"` : ''}>${icon(t.icon)}<span>${t.label}</span></a>`;
  }));
  paintUnread();
  paintAccount();
}

export function moreBody() {
  const sym = PAINTED_SYM || openedNow() || null;
  const groups = visibleGroups(flags), has = (id) => groups.some((x) => x.id === id), byId = (id) => GROUPS.find((x) => x.id === id);
  // What the phone bar does not hold, in the rail's sections and by the rail's names: Research's and Lists' entries,
  // the rail's More (Compare, Brokerage, Alerts, the owner's Reports), Settings; Sign in for a guest, whose top bar
  // keeps its width for search (the classic app's More sheet)
  const row = (href, ic, label, what, out) => html`<a class="more-row" href="${href}">${icon(ic)}<span class="more-lab">${label}${what ? html`<small>${what}</small>` : ''}</span>${out ? html`<span class="legacy">${icon('out')}<span class="sr">, opens in the classic app</span></span>` : ''}</a>`;
  const group = (label, rows) => html`<div class="more-group"><p class="more-glab">${label}</p>${rows}</div>`;
  const research = RESEARCH.map((e) => row(researchHref(e, sym), e.icon, e.label, sym ? '' : 'Opens the company search first', false));
  const lists = LISTS.map((l) => row(l.href, l.icon, l.label, WHAT[l.views[0]], false));
  const more = RAIL_MORE.filter((m) => (m.group ? has(m.group) : true)).map((m) => {
    const g = m.group ? byId(m.group) : null;
    return row(g ? groupHref(g, sym) : hrefFor(m.view), m.icon, m.label, WHAT[g ? g.pages[0].view : m.view], g ? !groupIsV2(g) : false);
  });
  return html`<nav class="more-list" aria-label="More sections">${group('Research', research)}${group('Lists', lists)}${group('More', more)}
    <div class="more-group">${row(hrefFor('settings'), 'settings', SETTINGS.label, WHAT.settings, !SETTINGS.v2)}${store.user ? '' : row('#/signin', 'user', 'Sign in', 'A free account, for Milo and a saved watchlist', false)}</div></nav>`;
}

export function paintAccount() {
  const b = $('[data-v2-account]');
  if (!b) return;
  const u = store.user;
  if (store.auth === 'loading') { b.textContent = ''; b.setAttribute('aria-label', 'Account'); return; }
  if (u) {
    const ini = ((u.first_name || u.email || '?')[0] + ((u.last_name || '')[0] || '')).toUpperCase();
    b.textContent = ini.slice(0, 2);
    b.classList.add('avatar');
    b.setAttribute('aria-label', `Account: ${u.name || u.email}`);
  } else {
    b.textContent = 'Sign in';
    b.classList.remove('avatar');
    b.removeAttribute('aria-label');
  }
}

