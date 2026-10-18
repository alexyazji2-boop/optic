// The frame around every page: the labelled, expandable rail, the top bar
// (search, Ask Milo, account) and the phone bar. Pages render into #main.
import { html, render, $, $$ } from '../core/dom.js';
import { icon, brandMark } from './icons.js';
import { footer as legalFooter } from '../core/legal.js';
import { GROUPS, SECTIONS, SETTINGS, MOBILE_TABS, visibleGroups, hrefFor, groupOf } from '../nav.js';
import { state as store, recent } from '../core/store.js';

let flags = { admin: false, brokerage: false };
export function setFlags(f) { flags = Object.assign(flags, f); }
export const getFlags = () => ({ ...flags });
// Collapsed to icons, remembered under the classic key (optic.rail.tight.v2: '1' or '0').
const RAIL_KEY = 'optic.rail.tight.v2';
export function railTight() { try { return localStorage.getItem(RAIL_KEY) === '1'; } catch (e) { return false; } }
export function setRailTight(on) { try { localStorage.setItem(RAIL_KEY, on ? '1' : '0'); } catch (e) { /* private mode */ } const sh = $('.shell'); if (sh) sh.classList.toggle('is-tight', on); }

// Groups opened in the rail (VISUAL-SPEC-DARK.md, X2): the group on screen is
// always open; others stay as the reader left them.
const OPEN_KEY = 'optic.v2.rail.open.v1';
const openGroups = () => { try { const v = JSON.parse(localStorage.getItem(OPEN_KEY) || '[]'); return new Set(Array.isArray(v) ? v : []); } catch (e) { return new Set(); } };
export function toggleGroup(id, btn) {
  const open = openGroups(); const on = !open.has(id);
  if (on) open.add(id); else open.delete(id);
  try { localStorage.setItem(OPEN_KEY, JSON.stringify([...open])); } catch (e) { /* private mode */ }
  if (btn) { btn.setAttribute('aria-expanded', String(on)); const sub = document.getElementById(btn.getAttribute('aria-controls')); if (sub) sub.hidden = !on; }
}

function groupHref(g, symbol) {
  const first = g.pages[0];
  if (g.symbol) return symbol ? `#/${symbol}` : null;
  return hrefFor(first.view, symbol);
}
const groupIsV2 = (g) => g.pages.some((p) => p.v2);

export function mount(app) {
  render(app, html`<a class="skip" href="#main">Skip to content</a>
  <div class="shell ${railTight() ? 'is-tight' : ''}">
    <div class="rail"></div>
    <div class="stage">
      <header class="topbar">
        <a class="brand-sm" href="#/" aria-label="Optic Terminal, Home">${brandMark()}</a>
        <button type="button" class="search-btn" data-v2-open-palette aria-label="Search companies, tickers and pages, or ask Milo">${icon('search')}<span class="sb-long">Search or ask</span><span class="sb-short" aria-hidden="true">Search</span><kbd>⌘K</kbd></button>
        <span class="spacer"></span><span class="session-chip" id="session-chip" role="status" aria-live="off"></span>
        <a class="btn btn-sm topbar-ws" href="#/workspace">Workspace</a>
        <button type="button" class="btn btn-milo btn-sm topbar-milo" data-v2-milo="" data-v2-milo-ctx="" data-v2-milo-sym="" aria-label="Ask Milo">${icon('milo')}<span class="tm-label" aria-hidden="true">Ask Milo</span></button>
        <button type="button" class="account-btn" data-v2-account aria-haspopup="dialog">Sign in</button>
      </header>
      <main id="main" class="page" tabindex="-1"></main>
      <footer class="legal" id="legal-footer"><p class="app-status"><span id="app-status"></span><button type="button" class="textlink" data-v2-report-open>Report a problem</button></p>${legalFooter()}</footer>
    </div>
  </div>
  <nav class="tabbar" aria-label="Sections"></nav>`);
}

/** Paint the rail and phone bar for the current route. */
export function paint(route) {
  const g = route.view === 'settings' ? null : groupOf(route.view);
  const sym = route.symbol || recent()[0] || null;
  const groups = visibleGroups(flags);
  const opened = openGroups();
  let lastSec = '';
  const rows = [];
  groups.forEach((gr) => {
    const sec = SECTIONS[gr.id];
    if (sec !== lastSec) { rows.push(html`<p class="rail-sec">${sec}</p>`); lastSec = sec; }
    const href = groupHref(gr, sym);
    const cur = g && g.id === gr.id ? 'page' : null;
    const out = !groupIsV2(gr);
    const inner = html`${icon(gr.icon)}<span>${gr.label}</span>${out ? html`<span class="legacy" aria-hidden="true">${icon('out')}</span>` : ''}`;
    const name = out ? `${gr.label}, opens in the current app` : gr.label;
    const main = href
      ? html`<a class="rail-row" href="${href}" aria-label="${name}" ${cur ? html`aria-current="${g && g.pages.length > 1 ? 'true' : 'page'}"` : ''}>${inner}</a>`
      : html`<button type="button" class="rail-row" data-v2-open-palette aria-label="${name}, search for a company" ${cur ? html`aria-current="true"` : ''}>${inner}</button>`;
    // a group with several pages opens to list them, by the same names as its page tabs
    const subs = gr.pages.length > 1 && (!gr.symbol || sym) ? gr.pages : null;
    if (!subs) { rows.push(main); return; }
    const open = !!cur || opened.has(gr.id), id = `rail-sub-${gr.id}`;
    rows.push(html`<div class="rail-item">${main}<button type="button" class="rail-disc" data-v2-rail-disc="${gr.id}" aria-expanded="${open}" aria-controls="${id}" aria-label="${gr.label} pages">${icon('chev')}</button></div>
      <ul class="rail-sub" id="${id}" ${open ? '' : 'hidden'}>${subs.map((p) => html`<li><a class="rail-subrow" href="${hrefFor(p.view, sym)}" ${route.view === p.view ? html`aria-current="page"` : ''}>${p.label}${p.v2 ? '' : html`<span class="sr">, opens in the current app</span>`}</a></li>`)}</ul>`);
  });
  render($('.rail'), html`<a class="brand" href="#/" aria-label="Optic Terminal, Home">${brandMark()}<span class="brand-word" aria-hidden="true">OPTIC <span>TERMINAL</span></span></a>
    <nav class="rail-nav" aria-label="Sections">${rows}</nav>
    <div class="rail-foot"><a class="rail-row" href="${hrefFor('settings')}" ${SETTINGS.v2 ? '' : html`aria-label="${SETTINGS.label}, opens in the current app"`} ${route.view === 'settings' ? html`aria-current="page"` : ''}>${icon(SETTINGS.icon)}<span>${SETTINGS.label}</span>${SETTINGS.v2 ? '' : html`<span class="legacy" aria-hidden="true">${icon('out')}</span>`}</a><button type="button" class="rail-row" data-v2-rail-collapse aria-pressed="${railTight()}" aria-label="Collapse">${icon('chev')}<span>Collapse</span></button></div>`);

  render($('.tabbar'), MOBILE_TABS.map((t) => {
    if (t.more) {
      const inMore = g && !MOBILE_TABS.some((m) => m.group === g.id);
      return html`<button type="button" data-v2-more ${inMore ? html`aria-current="page"` : ''}>${icon(t.icon)}<span>${t.label}</span></button>`;
    }
    const gr = GROUPS.find((x) => x.id === t.group);
    const href = groupHref(gr, sym);
    const cur = g && g.id === t.group ? html`aria-current="page"` : '';
    return href ? html`<a href="${href}" ${cur}>${icon(t.icon)}<span>${t.label}</span></a>`
      : html`<button type="button" data-v2-open-palette ${cur}>${icon(t.icon)}<span>${t.label}</span></button>`;
  }));
  paintAccount();
}

export function moreBody() {
  const shown = new Set(MOBILE_TABS.filter((t) => t.group).map((t) => t.group));
  const sym = recent()[0] || null;
  return html`<nav class="more-list" aria-label="More sections">${visibleGroups(flags).filter((g) => !shown.has(g.id)).map((g) => {
    const href = groupHref(g, sym);
    return html`<a class="rail-row" href="${href}">${icon(g.icon)}<span>${g.label}</span>${groupIsV2(g) ? '' : html`<span class="legacy">${icon('out')}<span class="sr">, opens in the current app</span></span>`}</a>`;
  })}<a class="rail-row" href="${hrefFor('settings')}">${icon('settings')}<span>${SETTINGS.label}</span>${SETTINGS.v2 ? '' : html`<span class="legacy">${icon('out')}<span class="sr">, opens in the current app</span></span>`}</a></nav>`;
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

