// A symbol in a search result, laid out as TradingView lays one out (owner, 2026-10-21: "any search bar within optic
// should look like this, whether the user searches the name of a company, ETF or ticker. include the logo as well"):
// the company's logo, the symbol, the name, and on the right what kind of listing it is. The letters the reader typed
// are marked in gold in the symbol and the name (the owner's choice of colour); corners stay squared (the owner's
// choice: no pills). The exchange is not shown: Optic's search does not carry it, and a guessed one would be invented.
//
// Logos come from /api/logo/{symbol}, which Optic fetches and keeps, so the logo services never see the reader. Until
// one arrives, and where there is none (an index, a future, a pair, a symbol no service has), the symbol's initial
// stands in its place.
import { esc } from '../core/format.js';

export const KIND = { stock: 'stock', etf: 'fund etf', index: 'index', crypto: 'crypto', commodity: 'futures', future: 'futures', fx: 'currency', rate: 'rate' };
/** The filter a kind of listing falls under. */
export const filterOf = (kind) => (kind === 'commodity' || kind === 'future' ? 'futures' : kind === 'rate' ? 'index' : kind || 'stock');
export const FILTERS = [['all', 'All'], ['stock', 'Stocks'], ['etf', 'Funds'], ['index', 'Indices'], ['futures', 'Futures'], ['crypto', 'Crypto'], ['fx', 'Currencies']];
const LOGO_SYM = /^[A-Z][A-Z0-9.-]{0,9}$/;
// symbols whose logo answered with an error on this visit: a repaint draws the initial at once instead of asking
// again (an unlisted symbol's Overview asked four times, one 404 per redraw: investor audit, 2026-10-27)
const NO_LOGO = new Set();

/** The text with the first match of the query marked, escaped. */
export function marked(text, query) {
  const t = String(text || ''), q = String(query || '').trim();
  const at = q ? t.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (at < 0) return esc(t);
  return `${esc(t.slice(0, at))}<b>${esc(t.slice(at, at + q.length))}</b>${esc(t.slice(at + q.length))}`;
}
/** The logo, over the symbol's initial. `lazy: false` for one above the fold, such as the Dossier header's (on every
 *  tab since 2026-10-25, as Classic's header has it), which a repaint draws afresh and a lazy load could leave waiting. */
export function logoHTML(symbol, { lazy = true } = {}) {
  const sym = String(symbol || '').toUpperCase(), first = (sym.match(/[A-Z0-9]/) || [''])[0];
  return `<span class="sym-logo" aria-hidden="true" data-l="${esc(first)}">${LOGO_SYM.test(sym) && !NO_LOGO.has(sym) ? `<img src="/api/logo/${encodeURIComponent(sym)}" alt=""${lazy ? ' loading="lazy"' : ''} decoding="async">` : ''}</span>`;
}
/** One result: the logo, the symbol and the name with what was typed marked, and the kind of listing. */
export function rowHTML(r, query, { kind = true } = {}) {
  const k = r.kind || (r.etf ? 'etf' : 'stock');
  return `${logoHTML(r.symbol)}<span class="sym-sym">${marked(r.symbol, query)}</span><span class="sym-name">${marked(r.name || '', query)}</span>${kind && KIND[k] ? `<span class="sym-kind">${esc(KIND[k])}</span>` : ''}`;
}

// a logo that did not load leaves the initial showing (one listener for the page)
if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('error', (e) => {
    const t = e.target;
    if (!(t && t.tagName === 'IMG' && t.parentElement && t.parentElement.classList.contains('sym-logo'))) return;
    const m = /\/api\/logo\/([^/?#]+)/.exec(t.getAttribute('src') || ''); if (m) NO_LOGO.add(decodeURIComponent(m[1]).toUpperCase());
    t.remove();
  }, true);
  document.addEventListener('load', (e) => { const t = e.target; if (t && t.tagName === 'IMG' && t.parentElement && t.parentElement.classList.contains('sym-logo')) t.parentElement.classList.add('has-img'); }, true);
}
