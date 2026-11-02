// What a reader typed, turned into a listing and the page it opens (Phase 03, 2026-10-29). The palette, Home's
// search box, the Dossier start page and Home's linked-panel box all use this, so the same text opens the same thing
// from each: before, Home and the Dossier start had their own code, opened an index as a company Dossier, and Home did
// nothing at all when it found no match (R-A14-1 to 3).
//
// The rule, from the palette's (ui/palette.js): an exact symbol wins; else a name people use ("google", "spx") or a
// company whose name starts with the word typed; else nothing, and the caller says so or offers the search.
import * as api from './api.js';
import { hrefFor } from '../nav.js';
import { canon } from './store.js';

// An index, rate, currency, future or crypto has an instrument page, not a company Dossier (the search audit,
// 2026-10-20: ^TNX opened as a dossier).
const INSTRUMENT_KINDS = new Set(['index', 'rate', 'fx', 'commodity', 'future', 'crypto']);
export const isInstrument = (sym, kind) => (kind ? INSTRUMENT_KINDS.has(kind) : /^\^|=|-USD$|\.NYB$/.test(String(sym || '')));
export const openHref = (sym, kind) => (isInstrument(sym, kind) ? `#/instrument/${encodeURIComponent(sym)}` : hrefFor('overview', sym));
export const looksLikeTicker = (t) => /^[A-Za-z][A-Za-z.-]{0,5}$/.test(String(t).trim());
export const tickerShaped = (t) => /^[A-Za-z0-9.^=-]{1,12}$/.test(String(t).trim());
// What a real symbol looks like, for opening one as typed when the directory cannot be asked: 1 to 5 letters with an
// optional share class (BRK.B, BRK-B), an index (^GSPC), a future (ES=F) or a crypto pair (BTC-USD). "nvidia" is not
// one, so with search down it opens the search rather than a Dossier for NVIDIA (Phase 03 scenario S12).
export const symbolShaped = (t) => /^(\^[A-Za-z0-9]{1,6}|[A-Za-z]{1,5}([.-][A-Za-z]{1,2})?|[A-Za-z0-9]{1,5}=[A-Za-z]|[A-Za-z]{2,5}-USD)$/.test(String(t).trim());
export const startsWord = (name, q) => String(name || '').toLowerCase().split(/[\s,.]+/).some((w) => w.startsWith(String(q).toLowerCase()));

/** The directory's answer for `q`, never cached when the directory could not be read (R-PAL-6: an outage's answer
 *  outlived the outage by five minutes). Resolves to {results, failed, stale, reason}. */
export async function search(q, limit = 12) {
  try {
    const r = await api.get(`/api/search?q=${encodeURIComponent(q)}&limit=${limit}`, { ttl: 300000, timeout: 8000, keep: (d) => !(d && d.available === false) });
    return { results: (r && r.results) || [], failed: !!(r && r.available === false), stale: !!(r && r.stale), reason: (r && r.reason) || '' };
  } catch (e) { return { results: [], failed: true, stale: false, reason: '' }; }
}

/** The listing a typed text names, or null. `results` is the directory's answer for exactly that text. */
export function pick(q, results) {
  const t = String(q || '').trim();
  if (!t || !results || !results.length) return null;
  const up = canon(t);
  const exact = results.find((r) => canon(r.symbol) === up);
  if (exact) return exact;
  const first = results[0];
  if (first.match === 'alias') return first;
  if (['name', 'word'].includes(first.match) && startsWord(first.name, t)) return first;
  return null;
}

/** Resolve typed text: {hit: {symbol, name, kind, href}} | {none: true, failed, results}. A ticker-shaped text the
 *  directory could not be asked about opens as typed, said so in `note`. */
export async function resolve(text) {
  const q = String(text || '').trim();
  if (!q) return { none: true, empty: true, failed: false, results: [] };
  const { results, failed } = await search(q, 8);
  const hit = pick(q, results);
  if (hit) {
    const kind = hit.kind || (hit.etf ? 'etf' : 'stock');
    const symbol = String(hit.symbol).toUpperCase();
    return { hit: { symbol, name: hit.name || '', kind, href: openHref(symbol, kind) } };
  }
  if (failed && symbolShaped(q)) {
    const symbol = canon(q);
    return { hit: { symbol, name: '', kind: '', href: openHref(symbol), note: 'Search is unavailable; opened as typed.' } };
  }
  return { none: true, failed, results };
}

/** A navigation that a slow answer must not make after the reader has moved on (R-A14-2): take a ticket before the
 *  await, and `go` only goes while the address and the ticket are still the ones it was taken on. */
let tickets = 0;
export function ticket() {
  const at = location.hash, mine = (tickets += 1);
  return { stillHere: () => location.hash === at && mine === tickets, go: (href) => { if (location.hash === at && mine === tickets) location.hash = href; } };
}
