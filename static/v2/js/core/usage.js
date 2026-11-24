// The owner's three signals, from the page's side (2026-11-09, app/usage.py): a stock opened from Home and the first
// visit of a day. The third, a question to Milo, is recorded by the server when the question is asked.
//
// A signed-out reader is counted by a random id this browser makes once and keeps (optic.visitor.v1), so a return
// within a week can be counted without an account. It names no one, carries nothing about the reader, and is sent
// only to Optic's own server; clearing the browser's data clears it. A signed-in reader is counted by their account.
import * as api from './api.js';
import * as prefs from './prefs.js';

const KEY = 'optic.visitor.v1';
let memo = null;
/** This browser's visitor id ("v-" and 32 hex digits), made on first use. In private mode it lasts the visit. */
export function visitorId() {
  if (memo) return memo;
  try { const v = localStorage.getItem(KEY); if (/^v-[0-9a-f]{32}$/.test(v || '')) { memo = v; return memo; } } catch (e) { /* private mode */ }
  const b = new Uint8Array(16);
  try { crypto.getRandomValues(b); } catch (e) { for (let i = 0; i < 16; i += 1) b[i] = Math.floor(Math.random() * 256); }
  memo = `v-${[...b].map((x) => x.toString(16).padStart(2, '0')).join('')}`;
  try { localStorage.setItem(KEY, memo); } catch (e) { /* private mode: this visit only */ }
  return memo;
}

/** Send one event; never in the reader's way (a failure is dropped, nothing is retried or shown). */
export function track(event, { symbol = null, screen = null } = {}) {
  const body = { event, visitor: visitorId(), level: prefs.level() };
  if (symbol) body.symbol = String(symbol).toUpperCase();
  if (screen) body.screen = screen;
  return api.post('/api/usage', body, { timeout: 8000 }).catch(() => null);
}
