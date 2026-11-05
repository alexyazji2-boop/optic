// The saved research library (Handoff 5 of the owner's handover pack, 2026-11-03): what the reader chose to keep, on
// their account, at /api/library (app/library.py). A company, a comparison and a research sheet are kept by reference
// and reopen on the live page; a Milo conversation is kept as it was, with each answer's sources and the times they
// were read, so reopening it never changes what it cited. Nothing is saved without the reader pressing Save.
import * as api from './api.js';
import * as store from './store.js';
import * as prefs from './prefs.js';

export const KINDS = ['company', 'comparison', 'conversation', 'sheet', 'investigation', 'question'];
export const WORD = { company: 'Company', comparison: 'Comparison', conversation: 'Milo conversation', sheet: 'Research sheet', investigation: 'Investigation', question: 'Question' };
export const PLURAL = { company: 'Companies', comparison: 'Comparisons', conversation: 'Milo conversations', sheet: 'Research sheets', investigation: 'Investigations', question: 'Questions' };

/** A calendar date in the reader's zone: "Nov 4, 2026". */
export function dayText(at, zone = prefs.zone()) {
  const t = new Date(at); if (!Number.isFinite(t.getTime())) return '';
  try { return t.toLocaleDateString('en-US', { timeZone: zone, month: 'short', day: 'numeric', year: 'numeric' }); } catch (e) { return t.toISOString().slice(0, 10); }
}
/** The name a save takes unless the reader gives one: the ticker(s) and the date, as the handoff asks. */
export function defaultName(kind, tickers = [], at = Date.now()) {
  const date = dayText(at);
  if (!tickers.length) return `${kind === 'conversation' ? 'Milo conversation' : 'Saved research'}, ${date}`;
  return `${tickers.join(' vs ')}, ${date}`;
}
/** What makes two saves the same thing, as the server keys them (app/library.py item_key). */
export function keyOf(kind, tickers = [], ref = {}) {
  if ((kind === 'company' || kind === 'sheet') && tickers[0]) return `${kind}:${tickers[0]}`;
  if (kind === 'comparison' && tickers.length) return `comparison:${[...tickers].sort().join(',')}`;
  if (kind === 'conversation' && ref && ref.conversation) return `conversation:${ref.conversation}`;
  return null;
}
/** Where an item reopens, with the tickers that are still there: its page's address, or null for a Milo conversation
 *  (which opens in Milo's panel) and a question (asked again). */
export function routeOf(item) {
  const live = (item.tickers || []).filter((t) => !(item.gone || []).includes(t)), e = encodeURIComponent;
  if (item.kind === 'company') return live[0] ? `#/${e(live[0])}${(item.ref || {}).tab ? `/${item.ref.tab}` : ''}` : null;
  if (item.kind === 'sheet') return live[0] ? `#/${e(live[0])}/sheet` : null;
  // an investigation reopens on its own page, drafts included, even for a ticker no longer listed: it is a record
  if (item.kind === 'investigation') return (item.tickers || [])[0] ? `#/${e(item.tickers[0])}/investigate?saved=${e(item.id)}` : null;
  if (item.kind === 'comparison') {
    const gone = (item.gone || []).filter((t) => (item.tickers || []).includes(t));
    return `#/compare?t=${live.map(e).join(',')}${gone.length ? `&gone=${gone.map(e).join(',')}` : ''}`;
  }
  return null;
}

/* ---------------- the account's library ---------------- */
const q = (o) => Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
export const list = ({ kind = '', search = '', cursor = '', limit = 30 } = {}) => api.get(`/api/library?${q({ kind, q: search, cursor, limit })}`, { ttl: 0, force: true, timeout: 20000 });
export const get = (id) => api.get(`/api/library/${encodeURIComponent(id)}`, { ttl: 0, force: true, timeout: 20000 });

// What each key is saved as, for the Save buttons: {id, name, created_at} or null; filled as buttons ask
const SAVED = new Map();
const tell = (key, item) => { if (key) SAVED.set(key, item || null); try { window.dispatchEvent(new CustomEvent('v2:library', { detail: { key, item: item || null } })); } catch (e) { /* no window in tests */ } };
/** Whether something is saved, and as what. One request per key a visit; a save or a delete here updates it. */
export async function savedAs(key) {
  if (!key || !store.signedIn()) return null;
  if (SAVED.has(key)) return SAVED.get(key);
  const r = await api.get(`/api/library?${q({ key, limit: 1 })}`, { ttl: 60000, timeout: 15000 });
  const it = ((r && r.items) || [])[0] || null;
  SAVED.set(key, it);
  return it;
}
export const known = (key) => (SAVED.has(key) ? SAVED.get(key) : undefined);

/** Save one thing: {kind, tickers, ref, name, summary, conversation}. `onDuplicate` is how a second save of the same
 *  thing is settled: unset, the server answers 409 with the saved one (ApiError body.detail.duplicate); "update" gives
 *  the saved one this save's contents and time; "copy" keeps another under its own name. */
export async function save(spec, { onDuplicate } = {}) {
  const body = Object.assign({}, spec, onDuplicate ? { on_duplicate: onDuplicate } : {});
  const r = await api.post('/api/library', body, { timeout: 20000 });
  api.invalidate('/api/library');
  tell(r.item && r.item.ref && spec.kind ? keyOf(spec.kind, r.item.tickers, r.item.ref) : null, r.item);
  return r;
}
/** The saved one a 409 named, or null for any other failure. */
export const duplicateOf = (e) => (e && e.status === 409 && e.body && e.body.detail && e.body.detail.duplicate) || null;
export async function rename(item, name) {
  const r = await api.patch(`/api/library/${encodeURIComponent(item.id)}`, { name }, { timeout: 15000 });
  api.invalidate('/api/library');
  tell(keyOf(item.kind, item.tickers, item.ref), r.item);
  return r.item;
}
/** Delete everywhere: the account holds the one copy, and every Save button showing it is told. */
export async function remove(item) {
  await api.del(`/api/library/${encodeURIComponent(item.id)}`, { timeout: 15000 });
  api.invalidate('/api/library');
  tell(keyOf(item.kind, item.tickers, item.ref), null);
}
