// Whether a symbol names something Optic can show a page for (Handoff 3), asked of the server (/api/symbol-check,
// app/symbol_check.py) before a Dossier draws, before a symbol is saved to a watchlist and before Compare takes it.
// "MARKETS" opened as a company, with its tabs, a Watch button and Milo set to it (authenticated audit, 2026-11-03).
//
// A listed symbol is remembered on this device for a day and a missing one in memory for five minutes (a symbol can
// list tomorrow), so a Dossier the reader opens again does not wait on the check. A check that cannot be made is never
// kept and never read as "not found".
import * as api from './api.js';

export const OK = new Set(['listed', 'instrument', 'traded']);
// The pages about one symbol, drawn only once the symbol is known to name something (app.js show): any address shaped
// like a ticker opened a Dossier, and #/markets drew one for a "MARKETS" (audit, 2026-11-03)
export const SYMBOL_VIEWS = new Set(['overview', 'chart', 'swing', 'long', 'earnings', 'financials', 'news', 'sheet', 'instrument']);
/** The symbol a route asks about, for the check: a Dossier tab's or an instrument's, or the text of an address that is
 *  not a page at all; null for every other page. */
export const askedSymbol = (route) => (route.view === 'notfound' ? (route.attempted == null ? null : route.attempted)
  : route.symbol != null && SYMBOL_VIEWS.has(route.view) ? route.symbol : null);
export const REFUSED = new Set(['unknown', 'not_trading', 'invalid']);
const KEY = 'optic.v2.symbols.known.v1';
const DAY = 86400000, MISS = 300000;
const mem = new Map();

// the same spelling rule as store.canon and the server's: BRK.B, BRK/B and brk b are BRK-B
export function canon(sym) {
  const s = String(sym == null ? '' : sym).replace(/\s+/g, ' ').trim().toUpperCase();
  const m = /^([A-Z]{1,5})[./ ]([AB])$/.exec(s);
  return m ? `${m[1]}-${m[2]}` : s;
}
const readKept = () => { try { const v = JSON.parse(localStorage.getItem(KEY) || '{}'); return v && typeof v === 'object' ? v : {}; } catch (e) { return {}; } };
function keep(sym, r) {
  mem.set(sym, { at: Date.now(), r });
  if (!OK.has(r.status)) return;
  try {
    const all = readKept(), now = Date.now();
    all[sym] = { at: now, status: r.status, name: r.name || null, kind: r.kind || null };
    // a few hundred symbols at most, the oldest dropped first
    const keys = Object.keys(all).filter((k) => now - all[k].at < DAY).sort((a, b) => all[b].at - all[a].at).slice(0, 400);
    localStorage.setItem(KEY, JSON.stringify(Object.fromEntries(keys.map((k) => [k, all[k]]))));
  } catch (e) { /* private mode: kept in memory for this visit */ }
}

/** A kept answer for this symbol, or null: a known one for a day, a missing one for five minutes. */
export function cached(raw) {
  const sym = canon(raw);
  const m = mem.get(sym);
  if (m && Date.now() - m.at < (OK.has(m.r.status) ? DAY : MISS)) return m.r;
  const k = readKept()[sym];
  if (k && Date.now() - k.at < DAY) return { status: k.status, symbol: sym, query: sym, name: k.name, kind: k.kind };
  return null;
}
export const admissible = (r) => !!r && OK.has(r.status);

/** The server's answer for a symbol: {status, symbol, query, name, kind, suggestions, last_trade, reason}. A failure
 * or a timeout is {status: 'unavailable'}: "could not check", which no caller reads as a not-found. */
export async function check(raw, { from = '', timeout = 8000 } = {}) {
  const hit = cached(raw);
  if (hit) return hit;
  const sym = canon(raw);
  try {
    const r = await api.get(`/api/symbol-check?q=${encodeURIComponent(String(raw == null ? '' : raw))}&from=${encodeURIComponent(String(from || '').slice(0, 200))}`, { ttl: 0, timeout });
    if (r && r.status) { if (r.status !== 'unavailable' && sym) keep(sym, r); return r; }
  } catch (e) {
    return { status: 'unavailable', symbol: sym || null, query: String(raw == null ? '' : raw), reason: e && e.kind === 'timeout' ? 'The check took too long.' : 'The check did not answer.' };
  }
  return { status: 'unavailable', symbol: sym || null, query: String(raw == null ? '' : raw), reason: 'The check did not answer.' };
}

/** Why a symbol was not taken, said to the reader by a watchlist ("added") or Compare ("compared"). */
export function refusal(r, done = 'added') {
  const q = (r && (r.query || r.symbol)) || 'that';
  if (!r || r.status === 'unavailable') return `Optic could not check ${q} right now, so it was not ${done}. Try again in a moment.`;
  if (r.status === 'not_trading') return `${q} no longer trades, so it was not ${done}.`;
  return `No company found for '${q}', so it was not ${done}.`;
}

/** Drop what this browser kept, for a check that must ask again (tests, and a reader's Retry). */
export function forget(raw) { const sym = canon(raw); mem.delete(sym); try { const all = readKept(); delete all[sym]; localStorage.setItem(KEY, JSON.stringify(all)); } catch (e) { /* nothing kept */ } }
