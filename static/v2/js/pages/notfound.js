// The page for an address that names no company (Handoff 3): "No company found for 'MARKETS'" at the address the
// reader opened, never a redirect to another symbol. It shows the listings closest to what was typed, a search box
// holding it, and Discover and Markets Read. Nothing on it is shaped like a Dossier: no header strip, no tabs, no chart
// or figures, and Milo is given no symbol. "MARKETS" used to open as a company, Watch button and all (authenticated
// audit, 2026-11-03).
//
// The answer comes from core/symbolcheck.js; app.js shows this page in place of any Dossier tab whose symbol it
// refuses, and with "Could not check this symbol right now" when the check cannot be made, which is not a not-found.
import { html, raw, render as draw } from '../core/dom.js';
import { fullDate } from '../core/format.js';
import { GROUPS, hrefFor } from '../nav.js';
import { icon } from '../ui/icons.js';
import { provideContext } from '../ui/milo.js';
import * as palette from '../ui/palette.js';
import { resolve, ticket, openHref } from '../core/resolve.js';
import { logoHTML } from '../ui/symbols.js';

const KIND = { stock: 'Stock', etf: 'ETF', fund: 'Fund', index: 'Index', crypto: 'Crypto', fx: 'Currency', future: 'Future', commodity: 'Future', rate: 'Rate' };

/** A section's name typed as a symbol ("#/markets"): the section it names, offered first. */
export function sectionFor(text) {
  const t = String(text || '').trim().toLowerCase();
  if (!t) return null;
  for (const g of GROUPS) {
    if (g.symbol || !g.pages.length) continue;
    if ([g.label, ...g.pages.map((p) => p.label)].some((w) => w.toLowerCase() === t)) {
      const p = g.pages[0];
      return { href: hrefFor(p.view), label: p.label === g.label ? p.label : `${g.label} ${p.label}` };
    }
  }
  return null;
}

/** What the page says for an answer, as text the tests read: its heading and the line under it. */
export function words(r, attempted) {
  const typed = String(attempted == null ? (r && r.query) || '' : attempted).replace(/[^\x20-\x7e]/g, '').trim().slice(0, 24);
  const q = typed || '';
  const st = (r && r.status) || 'unknown';
  if (st === 'unavailable') {
    return { q, h1: 'Could not check this symbol right now', line: `Optic's symbol directory and its price source did not answer, so it cannot say whether '${q}' names a company. Nothing is shown for it until it can. Try again in a moment.` };
  }
  if (st === 'invalid') {
    return q ? { q, h1: `No company found for '${q}'`, line: `'${q}' is not a symbol: a ticker is letters and digits, with . - ^ or = in a few. Check the address, or search by the company's name.` }
      : { q, h1: 'No company found', line: 'This address names no symbol. Search by a company\'s name or ticker.' };
  }
  if (st === 'not_trading') {
    return { q, h1: `No company found for '${q}'`, line: `${q} is not in today's directory of US-listed securities, and the last trade Optic can find for it was on ${fullDate(r.last_trade)}. A symbol that no longer trades has no Dossier here. It may have been delisted, merged or renamed; Optic's data does not say which.` };
  }
  return { q, h1: `No company found for '${q}'`, line: `Optic's symbol directory, every stock and fund listed in the US, has no '${q}', and no price source trades it. Check the spelling, or search by the company's name.` };
}

export function view(route) {
  const r = route.check || { status: 'invalid' }, typed = route.attempted == null ? r.query || '' : route.attempted;
  const w = words(r, typed), shownText = w.q;
  const sec = r.status !== 'unavailable' ? sectionFor(typed) : null;
  const sugs = (r.suggestions || []).filter((s) => s && s.symbol);
  const rows = [
    ...(sec ? [html`<li><a class="ds-row nf-row" href="${sec.href}">${icon('markets')}<b>${sec.label}</b><span class="t-muted">The section, not a ticker</span></a></li>`] : []),
    ...sugs.map((s) => html`<li><a class="ds-row nf-row" href="${openHref(s.symbol, s.kind)}">${raw(logoHTML(s.symbol))}<b class="tick">${s.symbol}</b><span class="t-muted">${s.name || ''}</span><span class="nf-kind">${KIND[s.kind] || 'Stock'}</span></a></li>`),
  ];
  return html`<header class="page-head"><h1 class="t-h2" id="nf-h">${w.h1}</h1><p class="section-sub">${w.line}</p></header>
    ${r.status === 'unavailable' ? html`<section class="section first" aria-label="Try again"><div class="cluster"><button type="button" class="btn btn-primary" data-v2-nf-retry>Try again</button></div></section>` : ''}
    <section class="section${r.status === 'unavailable' ? '' : ' first'}" aria-label="Find a company"><form class="ds-search" role="search" data-v2-nf-form>
      <label class="field">${icon('search')}<span class="sr">Company, fund or ticker</span><input name="q" value="${shownText}" placeholder="Search a company, fund or ticker" autocomplete="off" spellcheck="false" data-v2-ta="submit"></label>
      <button type="submit" class="btn btn-primary">Search</button></form></section>
    ${rows.length ? html`<section class="section" aria-labelledby="nf-near"><h2 class="t-h3" id="nf-near">Closest matches</h2><ul class="ds-list nf-list">${rows}</ul></section>`
      : r.status !== 'unavailable' && shownText ? html`<section class="section"><p class="t-muted">Nothing in the directory is close to '${shownText}'.</p></section>` : ''}
    <section class="section" aria-labelledby="nf-else"><h2 class="t-h3" id="nf-else">Or start from</h2><div class="cluster"><a class="btn" href="#/explore">Discover</a><a class="btn" href="#/read">Markets Read</a></div></section>`;
}

let mainEl = null, retryFn = null;
export async function render(main, route, app) {
  mainEl = main;
  retryFn = route.retry || null;
  const w = words(route.check || { status: 'invalid' }, route.attempted);
  document.title = `${w.h1}, Optic`;
  // Milo sees a page about no symbol: a question asked here is about the question alone
  provideContext(() => ({ view: 'notfound' }));
  draw(main, view(route));
  if (main.dataset.nfWired) return;
  main.dataset.nfWired = '1';
  main.addEventListener('submit', async (e) => {
    const f = e.target.closest('[data-v2-nf-form]'); if (!f) return;
    e.preventDefault();
    const q = String(f.q.value || '').trim();
    if (!q) { f.q.focus(); return; }
    // the one resolver for typed text (core/resolve.js), as the Dossier start page's box: a listing opens its page,
    // anything else goes to the search with the text
    const t = ticket(), r = await resolve(q);
    if (!t.stillHere()) return;
    if (r.hit) t.go(r.hit.href); else palette.open(f.q, { seed: q });
  });
  main.addEventListener('click', (e) => { if (e.target.closest('[data-v2-nf-retry]') && retryFn) retryFn(); });
  void app;
}
export function dispose() { mainEl = null; retryFn = null; }
void mainEl;
