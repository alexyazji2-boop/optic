// Saved research (Classic parity B4d, 2026-10-21): questions the reader keeps to ask again. Classic's two stores and
// their formats, so what was saved in either app shows in both (app.js:31034-31245, 45850):
// - signed in, the account's: /api/saved-research rows {id, title, symbol, content, research_type: 'pulse', created_at}
// - a guest, this browser's: optic.research.v1, [{question, ticker, at}], newest first, 40 at most.
// Nothing here calls a model; asking again only drafts the question into Milo's box.
import * as api from './api.js';
import * as store from './store.js';
import { holds } from './device.js';

export const RESEARCH_KEY = 'optic.research.v1';
export const LOCAL_MAX = 40;

const local = () => { try { const v = JSON.parse(localStorage.getItem(RESEARCH_KEY) || '[]'); return Array.isArray(v) ? v : []; } catch (e) { return []; } };
/** One shape for both stores: {id, question, symbol, at, where: 'account' | 'browser'}. Old and partial records
 *  are read as they are (a missing ticker, a missing date). */
export function normalise(r, where) {
  if (!r || typeof r !== 'object') return null;
  const question = String(r.question || r.content || r.title || '').trim();
  if (!question) return null;
  const symbol = String(r.ticker || r.symbol || '').toUpperCase() || null;
  return { id: r.id || null, question, symbol, at: r.at || r.created_at || null, where };
}
/** Whether a question is one already kept (the same words, case and spacing aside). */
export const sameQuestion = (a, b) => String(a || '').replace(/\s+/g, ' ').trim().toLowerCase() === String(b || '').replace(/\s+/g, ' ').trim().toLowerCase();

/** What is saved: the account's when signed in, else this browser's (not another account's things). */
export async function listSaved() {
  if (store.signedIn()) {
    const r = await api.get('/api/saved-research?limit=200', { ttl: 0, force: true });
    return { items: ((r && r.research) || []).map((x) => normalise(x, 'account')).filter(Boolean), limit: r && r.limit, where: 'account' };
  }
  if (!holds(store.state.user)) return { items: [], where: 'browser' };
  return { items: local().map((x) => normalise(x, 'browser')).filter(Boolean), where: 'browser' };
}

/** Keep a question. Resolves to {ok, already, where, text}: text is what to tell the reader. */
export async function saveQuestion({ question, symbol = null }) {
  const q = String(question || '').trim();
  if (!q) return { ok: false, text: 'There is nothing to save.' };
  const sym = symbol ? String(symbol).toUpperCase() : null;
  if (store.signedIn()) {
    try {
      const have = await listSaved();
      if (have.items.some((x) => sameQuestion(x.question, q))) return { ok: true, already: true, where: 'account', text: 'That question is already in Saved research.' };
      await api.post('/api/saved-research', { title: q.slice(0, 200), symbol: sym, content: q, research_type: 'pulse' });
      api.invalidate('/api/saved-research');
      return { ok: true, where: 'account', text: 'Saved to Saved research.' };
    } catch (e) { return { ok: false, text: api.explain(e, 'Saving') }; }
  }
  if (!holds(store.state.user)) return { ok: false, text: 'It was not saved: this browser holds another account\'s things.' };
  const all = local();
  if (all.some((r) => sameQuestion(r.question, q))) return { ok: true, already: true, where: 'browser', text: 'That question is already in Saved research.' };
  all.unshift({ question: q, ticker: sym, at: new Date().toISOString() });
  try { localStorage.setItem(RESEARCH_KEY, JSON.stringify(all.slice(0, LOCAL_MAX))); } catch (e) { return { ok: false, text: 'This browser refused to save it.' }; }
  return { ok: true, where: 'browser', text: 'Saved in this browser. An account keeps it on every device.' };
}

/** Forget one; resolves to a function that puts it back (for Undo), or null when it could not be forgotten. */
export async function forget(item) {
  if (item.where === 'account') {
    await api.del(`/api/saved-research/${encodeURIComponent(item.id)}`);
    api.invalidate('/api/saved-research');
    return () => saveQuestion({ question: item.question, symbol: item.symbol });
  }
  const all = local(), k = all.findIndex((r) => sameQuestion(r.question, item.question));
  if (k < 0) return null;
  const [gone] = all.splice(k, 1);
  localStorage.setItem(RESEARCH_KEY, JSON.stringify(all));
  return () => { const now = local(); now.splice(Math.min(k, now.length), 0, gone); localStorage.setItem(RESEARCH_KEY, JSON.stringify(now.slice(0, LOCAL_MAX))); };
}
