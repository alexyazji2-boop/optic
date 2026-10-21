// A reader's alerts (watches), where they are kept: the account's at /api/watches when signed in, this browser's
// optic.watches.v1 otherwise, in the classic app's format so either app reads the other's (app.js:7553-7630).
// Shared by Alerts and by the pages that set an alert in one press, such as a swing setup's (Classic parity B5).
import * as api from './api.js';
import * as store from './store.js';
import { holds } from './device.js';

export const LOCAL_KEY = 'optic.watches.v1';
export const LOCAL_MAX = 40;

/** This browser's alerts, without the deleted ones (nothing, when the browser holds another account's things). */
export function localDefs() {
  if (!holds(store.state.user)) return [];
  try { const r = JSON.parse(localStorage.getItem(LOCAL_KEY) || '[]'); return Array.isArray(r) ? r.filter((w) => w && !w.deleted_at) : []; } catch (e) { return []; }
}
export function saveLocal(list) {
  if (!holds(store.state.user)) return false;
  try { localStorage.setItem(LOCAL_KEY, JSON.stringify(list.slice(0, LOCAL_MAX))); return true; } catch (e) { return false; }
}
const sameAlert = (a, b) => JSON.stringify({ symbol: a.symbol, kind: a.kind, params: a.params || {} }) === JSON.stringify({ symbol: b.symbol, kind: b.kind, params: b.params || {} });

/** Set one alert; resolves to the alert, or throws with what to tell the reader. The same rules as the form on
 *  Alerts: one of each per symbol, 40 at most. */
export async function addAlert({ symbol, kind, params = {} }) {
  const sym = store.canon(symbol || '');
  if (store.signedIn()) {
    const r = await api.post('/api/watches', { symbol: sym, kind, params });
    api.invalidate('/api/watches');
    return r && r.watch;
  }
  if (!holds(store.state.user)) throw new Error('This browser holds another account\'s things, so the alert was not set here.');
  const defs = localDefs(), def = { symbol: sym, kind, params };
  if (defs.some((d) => sameAlert(d, def))) throw new Error(`You already have that alert on ${sym}.`);
  if (defs.length >= LOCAL_MAX) throw new Error('That is 40 alerts, which is the limit. Delete one to add another.');
  const made = { id: 'local-' + Math.random().toString(36).slice(2, 11), symbol: sym, kind, params, active: true, created_at: new Date().toISOString(),
    ref_price: null, ref_at: null, last_state: null, last_met_at: null, last_evidence: null };
  if (!saveLocal([...defs, made])) throw new Error('This browser would not save the alert (private browsing, or its storage is full).');
  return made;
}
