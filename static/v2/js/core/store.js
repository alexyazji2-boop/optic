// Shared state for v2: who is signed in, their watchlists, recent symbols.
//
// Watchlists have two stores, chosen by who is here, exactly as in the classic
// app: an account's lists live on the server (/api/watchlists); a guest's live
// in this browser under the classic keys, so a guest moving between the two
// frontends keeps one list. A personal key is read only while this browser
// holds it for the person on screen (device.js), which is what keeps one
// person's list off another person's page.
import * as api from './api.js';
import { holds } from './device.js';

const WATCH_KEY = 'optic.chart.watch.v1';
const WATCHLISTS_KEY = 'optic.watchlists.v1';
const ACCOUNT_LIST_KEY = 'optic.watchlist.account.v1';
const RECENT_KEY = 'optic.recent.v1';
const GUEST_LIST_LIMIT = 12;

const subs = new Set();
export const state = {
  auth: 'loading',     // 'loading' | 'guest' | 'user' | 'unknown'
  me: null,            // /api/auth/me payload
  user: null,
  lists: null,         // [{id, name, symbols}]  null until loaded
  activeId: null,
  listsError: null,
  listLimit: null,
};

export function subscribe(fn) { subs.add(fn); return () => subs.delete(fn); }
function emit(what) { subs.forEach((fn) => { try { fn(what); } catch (e) { console.error(e); } }); }

const signedIn = () => state.auth === 'user';
export { signedIn };

function readJSON(key, fallback) {
  if (!holds(state.user)) return fallback;
  try { const v = JSON.parse(localStorage.getItem(key) || 'null'); return v == null ? fallback : v; } catch (e) { return fallback; }
}
function writeJSON(key, value) {
  if (!holds(state.user)) return false;
  try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch (e) { return false; }
}

/* ---------------- auth ---------------- */
export async function loadMe() {
  try {
    const me = await api.get('/api/auth/me', { force: true, timeout: 10000 });
    state.me = me;
    state.user = me && me.authenticated ? me.user : null;
    state.auth = state.user ? 'user' : 'guest';
  } catch (e) {
    // The server could not say. Treat as a guest for reading, but say so.
    state.me = null; state.user = null; state.auth = 'unknown';
  }
  emit('auth');
  return state;
}

export function plan() {
  const s = (state.me && state.me.subscription) || {};
  return { label: s.label || s.plan || null, limits: s.limits || {} };
}

export async function signIn(email, password, remember) {
  const r = await api.post('/api/auth/login', { email, password, remember: !!remember });
  api.invalidate('/api/');
  return r;
}
export async function signOut() {
  try { await api.post('/api/auth/logout', {}); } finally { api.invalidate('/api/'); }
}

/* ---------------- recent symbols ---------------- */
export function recent() {
  const r = readJSON(RECENT_KEY, []);
  return Array.isArray(r) ? r.map((x) => String(typeof x === 'string' ? x : x && x.symbol || '').toUpperCase()).filter(Boolean).slice(0, 8) : [];
}
export function pushRecent(sym) {
  if (!sym) return;
  const raw = readJSON(RECENT_KEY, []);
  const list = Array.isArray(raw) ? raw : [];
  // keep whatever shape the classic app stored; it stores plain symbols
  const next = [sym, ...list.filter((x) => String(typeof x === 'string' ? x : x && x.symbol).toUpperCase() !== sym)].slice(0, 8);
  writeJSON(RECENT_KEY, next);
}

/* ---------------- watchlists ---------------- */
const newId = () => 'wl' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

function guestLists() {
  const raw = readJSON(WATCHLISTS_KEY, null);
  if (raw && Array.isArray(raw.lists) && raw.lists.length) {
    const lists = raw.lists.map((l) => ({
      id: String(l.id || newId()), name: String(l.name || 'Watchlist').slice(0, 60),
      symbols: (Array.isArray(l.symbols) ? l.symbols : []).map((x) => String(x).toUpperCase()).filter(Boolean),
    }));
    const activeId = lists.some((l) => l.id === raw.activeId) ? raw.activeId : lists[0].id;
    return { lists, activeId, stored: true };
  }
  // Only the single flat list, or nothing at all. Unlike the classic app,
  // nothing stored means nothing followed: a new visitor gets the welcome
  // instead of four starter symbols they never chose.
  const flat = readJSON(WATCH_KEY, null);
  if (Array.isArray(flat)) {
    const id = newId();
    return { lists: [{ id, name: 'Watchlist', symbols: flat.map((s) => String(s).toUpperCase()).filter(Boolean) }], activeId: id, stored: true };
  }
  return { lists: [], activeId: null, stored: false };
}

function saveGuest(lists, activeId) {
  writeJSON(WATCHLISTS_KEY, { lists, activeId });
  const active = lists.find((l) => l.id === activeId);
  // the active list is mirrored into the flat key every classic reader uses
  writeJSON(WATCH_KEY, active ? active.symbols : []);
}

// Signed in, the classic app still keeps the open list in the flat key: its
// chart dock, feed and alert builder read only that. Kept current here too, so
// a change made in v2 shows there.
function mirrorActive() {
  if (!signedIn() || !holds(state.user)) return;
  const active = (state.lists || []).find((l) => l.id === state.activeId);
  if (active) writeJSON(WATCH_KEY, active.symbols);
}

function adoptServer(lists, preferId) {
  state.lists = (lists || []).map((w) => ({ id: w.id, name: w.name, symbols: (w.symbols || []).slice() }));
  // the classic app stores the id as a bare string, not JSON (watchListSwitch)
  let remembered = null; try { remembered = holds(state.user) ? localStorage.getItem(ACCOUNT_LIST_KEY) : null; } catch (e) { /* private */ }
  const want = [preferId, state.activeId, remembered].find((id) => id && state.lists.some((l) => l.id === id));
  state.activeId = want || (state.lists[0] && state.lists[0].id) || null;
  if (state.activeId && holds(state.user)) { try { localStorage.setItem(ACCOUNT_LIST_KEY, state.activeId); } catch (e) { /* private */ } }
  mirrorActive();
}

export async function loadLists({ force = false } = {}) {
  state.listsError = null;
  if (signedIn()) {
    try {
      const r = await api.get('/api/watchlists', { ttl: force ? 0 : 15000, force });
      state.listLimit = r && r.limit;
      adoptServer(r && r.watchlists);
    } catch (e) {
      state.listsError = e;
      if (state.lists === null) state.lists = [];
    }
  } else {
    const g = guestLists();
    state.lists = g.lists; state.activeId = g.activeId;
  }
  emit('lists');
  return state.lists;
}

export const activeList = () => (state.lists || []).find((l) => l.id === state.activeId) || null;
export const allSymbols = () => [...new Set((state.lists || []).flatMap((l) => l.symbols))];
export const isFollowed = (sym) => (state.lists || []).some((l) => l.symbols.includes(sym));
export function listCap() {
  if (signedIn()) {
    const n = Number(plan().limits.watchlists || state.listLimit);
    return { n: Number.isFinite(n) && n > 0 ? n : 3, plan: plan().label || 'Free' };
  }
  return { n: GUEST_LIST_LIMIT, plan: null };
}

export function setActive(id) {
  if (!(state.lists || []).some((l) => l.id === id)) return;
  state.activeId = id;
  if (signedIn()) { if (holds(state.user)) { try { localStorage.setItem(ACCOUNT_LIST_KEY, id); } catch (e) { /* private */ } } mirrorActive(); }
  else saveGuest(state.lists, id);
  emit('lists');
}

// Every write is optimistic: the page changes at once, and a refusal puts it
// back and throws so the caller can say why.
async function mutate(apply, remote) {
  const before = JSON.stringify({ lists: state.lists, activeId: state.activeId });
  apply();
  emit('lists');
  if (!signedIn()) { saveGuest(state.lists, state.activeId); return; }
  try {
    const r = await remote();
    if (r && Array.isArray(r.watchlists)) adoptServer(r.watchlists);
    else if (r && r.watchlist) {
      const i = state.lists.findIndex((l) => l.id === r.watchlist.id);
      const w = { id: r.watchlist.id, name: r.watchlist.name, symbols: r.watchlist.symbols || [] };
      if (i >= 0) state.lists[i] = w; else state.lists.push(w);
      mirrorActive();
    }
    api.invalidate('/api/watchlists');
    emit('lists');
  } catch (e) {
    const b = JSON.parse(before); state.lists = b.lists; state.activeId = b.activeId;
    emit('lists');
    throw e;
  }
}

export async function follow(sym, listId) {
  sym = String(sym || '').toUpperCase().trim();
  if (!sym) return;
  if (!state.lists || !state.lists.length) {
    // the first follow makes the first list
    if (signedIn()) {
      const r = await api.post('/api/watchlists/adopt', { symbols: [sym] });
      api.invalidate('/api/watchlists');
      await loadLists({ force: true });
      return r;
    }
    const id = newId();
    state.lists = [{ id, name: 'Watchlist', symbols: [sym] }]; state.activeId = id;
    saveGuest(state.lists, id); emit('lists');
    return;
  }
  const id = listId || state.activeId;
  const list = state.lists.find((l) => l.id === id);
  if (!list || list.symbols.includes(sym)) return;
  return mutate(() => { list.symbols = [...list.symbols, sym]; },
    () => api.post(`/api/watchlists/${encodeURIComponent(id)}/items`, { symbol: sym }));
}

export async function unfollow(sym, listId) {
  const id = listId || state.activeId;
  const list = (state.lists || []).find((l) => l.id === id);
  if (!list) return;
  return mutate(() => { list.symbols = list.symbols.filter((s) => s !== sym); },
    () => api.del(`/api/watchlists/${encodeURIComponent(id)}/items/${encodeURIComponent(sym)}`));
}

/** Remove a symbol from every list (the Watch/Watching toggle on a company). */
export async function unfollowEverywhere(sym) {
  const ids = (state.lists || []).filter((l) => l.symbols.includes(sym)).map((l) => l.id);
  for (const id of ids) await unfollow(sym, id); // eslint-disable-line no-await-in-loop
}

export async function moveSymbol(sym, delta, listId) {
  const id = listId || state.activeId;
  const list = (state.lists || []).find((l) => l.id === id);
  if (!list) return;
  const i = list.symbols.indexOf(sym), j = i + delta;
  if (i < 0 || j < 0 || j >= list.symbols.length) return;
  const next = list.symbols.slice(); next.splice(j, 0, next.splice(i, 1)[0]);
  return mutate(() => { list.symbols = next; },
    () => api.put(`/api/watchlists/${encodeURIComponent(id)}/order`, { symbols: next }));
}

export async function createList(name) {
  name = String(name || '').trim().slice(0, 60);
  if (!name) throw new api.ApiError('bad', 400, 'Give the list a name.');
  const cap = listCap();
  if ((state.lists || []).length >= cap.n) {
    throw new api.ApiError('limit', 0, cap.plan ? `The ${cap.plan} plan keeps ${cap.n} watchlists. Rename or delete one to make room.` : 'Twelve lists is the limit. Rename or delete one.');
  }
  if (signedIn()) {
    const r = await api.post('/api/watchlists', { name });
    api.invalidate('/api/watchlists');
    await loadLists({ force: true });
    if (r && r.watchlist) setActive(r.watchlist.id);
    return;
  }
  const id = newId();
  state.lists = [...(state.lists || []), { id, name, symbols: [] }];
  state.activeId = id;
  saveGuest(state.lists, id); emit('lists');
}

export async function renameList(id, name) {
  name = String(name || '').trim().slice(0, 60);
  const list = (state.lists || []).find((l) => l.id === id);
  if (!list || !name || name === list.name) return;
  return mutate(() => { list.name = name; }, () => api.patch(`/api/watchlists/${encodeURIComponent(id)}`, { name }));
}

export async function deleteList(id) {
  if ((state.lists || []).length < 2) throw new api.ApiError('bad', 400, 'Keep at least one list.');
  return mutate(() => {
    state.lists = state.lists.filter((l) => l.id !== id);
    if (state.activeId === id) state.activeId = state.lists[0].id;
  }, () => api.del(`/api/watchlists/${encodeURIComponent(id)}`));
}

export async function moveList(id, delta) {
  const i = (state.lists || []).findIndex((l) => l.id === id), j = i + delta;
  if (i < 0 || j < 0 || j >= state.lists.length) return;
  const next = state.lists.slice(); next.splice(j, 0, next.splice(i, 1)[0]);
  return mutate(() => { state.lists = next; }, () => api.put('/api/watchlists/order', { ids: next.map((l) => l.id) }));
}

/** Remove one symbol's entry from a keyed browser copy (optic.thesis.v1,
 *  optic.valuation.v1). The classic app keeps such a copy beside the account's
 *  and adopts it into the account on its next load, so a delete made here has
 *  to remove both, or the classic app quietly puts the thing back. */
export function forgetLocalCopy(key, sym) {
  if (!holds(state.user)) return;
  try {
    const all = JSON.parse(localStorage.getItem(key) || 'null');
    if (all && typeof all === 'object' && sym in all) { delete all[sym]; localStorage.setItem(key, JSON.stringify(all)); }
  } catch (e) { /* unreadable or private: nothing to remove */ }
}
