// Dossier, with no company open (owner, 2026-10-21: "pressing dossier redirects me to the search bar, fix this
// issue"). The sidebar's Dossier opened the search whenever no company had been opened on this visit; it still does not
// reopen an old one by itself (store.js: following the Recent list opened a company the reader had not asked for
// today), so it lands here instead: a search box on the page, the companies opened recently, the reader's watchlist
// and a few well-known names, each one press from its Dossier. The box suggests as the reader types, with logos, as
// every symbol box does (ui/typeahead.js); choosing one opens it.
import { html, raw, render as draw } from '../core/dom.js';
import * as store from '../core/store.js';
import * as api from '../core/api.js';
import { icon } from '../ui/icons.js';
import { provideContext } from '../ui/milo.js';
import * as palette from '../ui/palette.js';
import { logoHTML } from '../ui/symbols.js';

const KNOWN = [['AAPL', 'Apple'], ['NVDA', 'NVIDIA'], ['MSFT', 'Microsoft'], ['SPY', 'S&P 500 fund']];
const isListing = (s) => !/^\^|=|-USD$/.test(s);
let mainEl = null;

function group(title, list) {
  if (!list.length) return '';
  return html`<section class="section" aria-label="${title}"><h2 class="t-h3">${title}</h2>
    <ul class="ds-list">${list.map(([sym, name]) => html`<li><a class="ds-row" href="#/${encodeURIComponent(sym)}">${raw(logoHTML(sym))}<b class="tick">${sym}</b>${name ? html`<span class="t-muted">${name}</span>` : ''}${icon('arrow')}</a></li>`)}</ul></section>`;
}

export async function render(main) {
  mainEl = main;
  document.title = 'Dossier, Optic';
  provideContext(() => ({ view: 'dossierstart' }));
  const recent = store.recent().filter(isListing).slice(0, 6);
  const list = store.activeList();
  const watch = ((list && list.symbols) || []).filter((s) => isListing(s) && !recent.includes(s)).slice(0, 8);
  const known = KNOWN.filter(([s]) => !recent.includes(s) && !watch.includes(s));
  draw(main, html`<header class="page-head"><h1 class="t-h2">Dossier</h1>
      <p class="section-sub">Everything Optic has on one company or fund: the business, the price, the options and what comes next. Choose one to open it.</p></header>
    <section class="section first" aria-label="Find a company"><form class="ds-search" role="search" data-v2-ds-form>
      <label class="field">${icon('search')}<span class="sr">Company, fund or ticker</span><input name="q" placeholder="Search a company, fund or ticker" autocomplete="off" spellcheck="false" data-v2-ta="submit"></label>
      <button type="submit" class="btn btn-primary">Open</button></form></section>
    ${group('Opened recently', recent.map((s) => [s, '']))}
    ${group(list ? list.name : 'Your watchlist', watch.map((s) => [s, '']))}
    ${group('Well-known names', known)}`);
  main.addEventListener('submit', async (e) => {
    const f = e.target.closest('[data-v2-ds-form]'); if (!f) return;
    e.preventDefault();
    const q = String(f.q.value || '').trim();
    if (!q) { f.q.focus(); return; }
    // a listed symbol opens its Dossier; anything else (a company's name) goes to the search with it, to choose from
    const tickerish = /^[A-Za-z0-9.^=-]{1,12}$/.test(q);
    let hit = null, failed = false;
    try { const r = await api.get(`/api/search?q=${encodeURIComponent(q)}&limit=5`, { ttl: 300000, timeout: 8000 }); hit = ((r && r.results) || []).find((x) => String(x.symbol).toUpperCase() === q.toUpperCase()) || null; } catch (err) { failed = true; }
    if (hit || (failed && tickerish)) location.hash = `#/${encodeURIComponent(q.toUpperCase())}`;
    else palette.open(f.q, { seed: q });
  });
  const input = main.querySelector('[data-v2-ds-form] input'); if (input && !matchMedia('(pointer: coarse)').matches) input.focus({ preventScroll: true });
}
export function dispose() { mainEl = null; }
void mainEl;
