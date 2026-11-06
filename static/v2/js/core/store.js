// Shared state for v2: who is signed in, their watchlists, recent symbols.
//
// Watchlists have two stores, chosen by who is here, exactly as in the classic
// app: an account's lists live on the server (/api/watchlists); a guest's live
// in this browser under the classic keys, so a guest moving between the two
// frontends keeps one list. A personal key is read only while this browser
// holds it for the person on screen (device.js), which is what keeps one
// person's list off another person's page.
import * as api from './api.js';
import * as symbols from './symbolcheck.js';
import { holds } from './device.js';
import * as prefs from './prefs.js';

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
  if (state.user) pullLevel(state.me);
  return state;
}

/* ---------------- the knowledge level on the account (post-demo Phase 05) ---------------- */
// One value. A guest's lives in this browser (core/prefs.js, Classic's key). A signed-in reader's lives on the
// account (/api/auth/preferences, user_preferences.knowledge_level): at sign-in an account that has a level wins and
// is written here; an account that never chose takes this browser's, if the reader chose one here. A change while
// signed in is sent (ui/levelslider.js); if it cannot be, this browser keeps it and the slider says so. The failed
// save is remembered with the account and the version of its preferences this browser last saw (`updated_at`,
// compared, never a clock): at the next load this browser's level goes up only if nothing has changed the account
// since; if something has, the account's newer level wins. Classic follows the same rule
// (static/components/knowledge.js), under the same key.
const PENDING_KEY = 'optic.knowledge.pending.v1';
let acctAt = null;   // the version of the account's preferences this page last saw
function pending() { try { return JSON.parse(localStorage.getItem(PENDING_KEY) || 'null'); } catch (e) { return null; } }
function setPending(v) { try { if (v) localStorage.setItem(PENDING_KEY, JSON.stringify(v)); else localStorage.removeItem(PENDING_KEY); } catch (e) { /* private mode */ } }
async function pullLevel(me) {
  try {
    // the session's answer carries the account's preferences; they are asked for only when it does not
    const r = me && me.preferences ? me : await api.get('/api/auth/preferences', { force: true, timeout: 10000 });
    const p = (r && r.preferences) || {}, lv = p.knowledge_level || null, was = pending();
    acctAt = p.updated_at || null;
    // the unsaved level itself, not the browser's current one: another account may have used this browser since
    if (was && was.user === state.user.id && (was.base || null) === acctAt) { if (was.level) prefs.setKnowledge(was.level, { quiet: true }); await pushLevel(); }
    else if (lv) { setPending(null); prefs.setKnowledge(lv, { quiet: true }); }
    else if (prefs.knowledgeChosen()) await pushLevel();
  } catch (e) { /* the browser's level stands; the next change or load sends it */ }
}
/** Send this browser's level to the account. {ok, local} when there is no account to send it to. */
export async function pushLevel() {
  if (!state.user) return { ok: true, local: true };
  const user = state.user.id;
  try {
    const r = await api.patch('/api/auth/preferences', { knowledge_level: prefs.knowledge() }, { timeout: 10000 });
    acctAt = ((r || {}).preferences || {}).updated_at || acctAt; setPending(null);
    return { ok: true };
  } catch (e) {
    const was = pending(); setPending({ user, base: was && was.user === user ? was.base : acctAt, level: prefs.knowledge() });
    return { ok: false, error: e };
  }
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
// The market's default symbol: Home's company panels show it, and a place that needs a company opens it, until the
// reader chooses another (Phase 03, 2026-10-29). Precedence, everywhere a page needs one: the address's symbol, the
// company opened on this visit (openedNow, for the palette and the Dossier link), the reader's saved choice where a
// page keeps one (Home's linked panels), then this. Never the Recent list or the watchlist on their own.
export const DEFAULT_SYMBOL = 'SPY';
export function recent() {
  const r = readJSON(RECENT_KEY, []);
  return Array.isArray(r) ? r.map((x) => String(typeof x === 'string' ? x : x && x.symbol || '').toUpperCase()).filter(Boolean).slice(0, 8) : [];
}
// The company opened on this visit, kept in memory only. The sidebar's Dossier link and an empty Compare start from
// it, never from the Recent list: that list outlives the visit (the classic app shares it and signing in brings
// back the person's own), so following it opened a company the reader had not asked for today.
let opened = null;
export const openedNow = () => opened;
export function pushRecent(sym) {
  if (!sym) return;
  if (!/^\^|=|-USD$/.test(sym)) opened = sym;
  const raw = readJSON(RECENT_KEY, []);
  const list = Array.isArray(raw) ? raw : [];
  // keep whatever shape the classic app stored; it stores plain symbols
  const next = [sym, ...list.filter((x) => String(typeof x === 'string' ? x : x && x.symbol).toUpperCase() !== sym)].slice(0, 8);
  writeJSON(RECENT_KEY, next);
}

/** Take one symbol off the Recent list: one that turned out not to exist (the classic forgetSymbol). */
export function forgetRecent(sym) {
  const raw = readJSON(RECENT_KEY, []);
  if (!Array.isArray(raw)) return;
  writeJSON(RECENT_KEY, raw.filter((x) => String(typeof x === 'string' ? x : x && x.symbol).toUpperCase() !== String(sym).toUpperCase()));
}
/** Forget the symbols opened in this browser (the search's Recent list; the classic app reads the same key). */
export function clearRecent() { writeJSON(RECENT_KEY, []); }

/* ---------------- watchlists ---------------- */
// One company is one entry: a US share class is kept dashed (BRK-B), the form every price
// source uses, however it was typed (BRK.B, brk b). Only A and B: VOD.L is London.
export function canon(sym) {
  const s = String(sym || '').trim().toUpperCase();
  const m = /^([A-Z]{1,5})[./ ]([AB])$/.exec(s);
  return m ? `${m[1]}-${m[2]}` : s;
}
const uniq = (syms) => [...new Set(syms.map(canon).filter(Boolean))];
const SAVE_REFUSED = 'This browser would not save the change (private browsing, or its storage is full), so nothing was changed.';
const newId = () => 'wl' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

function guestLists() {
  const raw = readJSON(WATCHLISTS_KEY, null);
  if (raw && Array.isArray(raw.lists) && raw.lists.length) {
    const lists = raw.lists.map((l) => ({
      id: String(l.id || newId()), name: String(l.name || 'Watchlist').slice(0, 60),
      symbols: uniq(Array.isArray(l.symbols) ? l.symbols : []),
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
    return { lists: [{ id, name: 'Watchlist', symbols: uniq(flat) }], activeId: id, stored: true };
  }
  return { lists: [], activeId: null, stored: false };
}

/** False when the browser refused the write: the caller puts the list back and says so. */
function saveGuest(lists, activeId) {
  const ok = writeJSON(WATCHLISTS_KEY, { lists, activeId });
  const active = lists.find((l) => l.id === activeId);
  // the active list is mirrored into the flat key every classic reader uses
  writeJSON(WATCH_KEY, active ? active.symbols : []);
  return ok;
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
  state.lists = (lists || []).map((w) => ({ id: w.id, name: w.name, symbols: uniq(w.symbols || []) }));
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
export const isFollowed = (sym) => (state.lists || []).some((l) => l.symbols.includes(canon(sym)));
export const listsWith = (sym) => (state.lists || []).filter((l) => l.symbols.includes(canon(sym)));
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
  else saveGuest(state.lists, id);   // which list is open is a convenience: a refused write is not worth an error
  emit('lists');
}

// Every write is optimistic: the page changes at once, and a refusal puts it
// back and throws so the caller can say why. A browser that will not store a
// guest's change is a refusal too. When the answer never came (a timeout, a
// dropped connection) the server may have applied it, so the lists are read
// again from the account instead of being guessed back.
async function mutate(apply, remote) {
  const before = JSON.stringify({ lists: state.lists, activeId: state.activeId });
  const restore = () => { const b = JSON.parse(before); state.lists = b.lists; state.activeId = b.activeId; emit('lists'); };
  apply();
  emit('lists');
  if (!signedIn()) {
    if (!saveGuest(state.lists, state.activeId)) { restore(); throw new api.ApiError('bad', 0, SAVE_REFUSED); }
    return;
  }
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
    if (e && e.status === 0 && (e.kind === 'timeout' || e.kind === 'server' || e.kind === 'offline')) {
      await loadLists({ force: true }).catch(() => {});
      if (!state.listsError) throw new api.ApiError(e.kind, 0, 'Optic could not confirm that change. The list now shows what your account holds.');
    }
    restore();
    throw e;
  }
}

/** Add a symbol to a list (the open one by default). `at` puts it back where it was, for Undo. */
export async function follow(sym, listId, { at } = {}) {
  sym = canon(sym);
  if (!sym) return;
  // only a symbol that names something (Handoff 3): "MARKETS" was saved from the Dossier a bad link drew for it. One
  // the check could not be made for is not added either, and the reader is told to try again.
  const known = await symbols.check(sym);
  if (!symbols.admissible(known)) throw new api.ApiError('bad', 0, symbols.refusal(known));
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
    if (!saveGuest(state.lists, id)) { state.lists = []; state.activeId = null; emit('lists'); throw new api.ApiError('bad', 0, SAVE_REFUSED); }
    emit('lists');
    return;
  }
  const id = listId || state.activeId;
  const list = state.lists.find((l) => l.id === id);
  if (!list || list.symbols.includes(sym)) return;
  const next = list.symbols.slice();
  next.splice(Number.isInteger(at) && at >= 0 ? Math.min(at, next.length) : next.length, 0, sym);
  const atEnd = next[next.length - 1] === sym;
  return mutate(() => { list.symbols = next; }, async () => {
    const r = await api.post(`/api/watchlists/${encodeURIComponent(id)}/items`, { symbol: sym });
    return atEnd ? r : api.put(`/api/watchlists/${encodeURIComponent(id)}/order`, { symbols: next });
  });
}

export async function unfollow(sym, listId) {
  sym = canon(sym);
  const id = listId || state.activeId;
  const list = (state.lists || []).find((l) => l.id === id);
  if (!list) return;
  return mutate(() => { list.symbols = list.symbols.filter((s) => s !== sym); },
    () => api.del(`/api/watchlists/${encodeURIComponent(id)}/items/${encodeURIComponent(sym)}`));
}

/** Remove a symbol from every list (the Watch/Watching toggle on a company). */
export async function unfollowEverywhere(sym) {
  sym = canon(sym);
  const where = (state.lists || []).filter((l) => l.symbols.includes(sym)).map((l) => ({ id: l.id, name: l.name, at: l.symbols.indexOf(sym) }));
  for (const w of where) await unfollow(sym, w.id); // eslint-disable-line no-await-in-loop
  return where;   // the lists it left and its place on each, so Undo can put it back exactly
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
  if ((state.lists || []).some((l) => l.name.toLowerCase() === name.toLowerCase())) throw new api.ApiError('bad', 409, 'You already have a list with that name.');
  const id = newId();
  const was = { lists: state.lists, activeId: state.activeId };
  state.lists = [...(state.lists || []), { id, name, symbols: [] }];
  state.activeId = id;
  if (!saveGuest(state.lists, id)) { state.lists = was.lists; state.activeId = was.activeId; emit('lists'); throw new api.ApiError('bad', 0, SAVE_REFUSED); }
  emit('lists');
}

export async function renameList(id, name) {
  name = String(name || '').trim().slice(0, 60);
  const list = (state.lists || []).find((l) => l.id === id);
  if (!list || !name || name === list.name) return;
  if (!signedIn() && state.lists.some((l) => l !== list && l.name.toLowerCase() === name.toLowerCase())) throw new api.ApiError('bad', 409, 'You already have a list with that name.');
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
