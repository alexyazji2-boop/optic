// What a symbol is and what Optic can say about it: one policy for every Dossier page, its tabs and
// its copy (owner, 2026-10-19: SPY's Overview asked company questions and printed an SEC 404, and its
// Financials tab showed on Chart but not on the other views because each page decided for itself).
//
// The kind comes from the session profile (`is_fund`, `is_company`, `kind`), then the quote's
// `quote_type`. Once any page learns it, it is remembered for the visit, so a page painted before its
// own data arrives already shows the right tabs.
const KNOWN = new Map();
const FUND = ['ETF', 'MUTUALFUND'];
const listeners = new Set();

export function learn(sym, { session, quote } = {}) {
  const k = kindFrom(session, quote);
  if (!sym || k === 'unknown' || KNOWN.get(sym) === k) return;
  KNOWN.set(sym, k);
  listeners.forEach((fn) => { try { fn(sym, k); } catch (e) { /* a listener's fault is its own */ } });
}
export const onLearn = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };

function kindFrom(session, quote) {
  const prof = (session || {}).profile || {};
  if (prof.is_fund) return 'fund';
  if (prof.is_company) return 'company';
  const t = String(prof.kind || (quote || {}).quote_type || '').toUpperCase();
  if (FUND.includes(t)) return 'fund';
  if (t === 'EQUITY') return 'company';
  if (t === 'INDEX') return 'index';
  if (t === 'CRYPTOCURRENCY') return 'crypto';
  return 'unknown';
}

/** company | fund | index | crypto | unknown */
export function kindOf(sym, data) {
  const k = data ? kindFrom(data.session, data.quote) : 'unknown';
  if (k !== 'unknown') return k;
  if (KNOWN.has(sym)) return KNOWN.get(sym);
  if (/^\^/.test(sym || '')) return 'index';
  if (/-USD$/.test(sym || '')) return 'crypto';
  return 'unknown';
}

// What each kind has. Unknown is treated as a company until the profile says otherwise, which is the
// common case and the one with the most to show; the tabs correct themselves when the kind is learnt.
export function can(kind) {
  const company = kind === 'company' || kind === 'unknown';
  return { financials: company, fundamentals: company, valuation: company, earnings: company, fundProfile: kind === 'fund' };
}

export const kindWord = (kind) => ({ company: 'company', fund: 'fund', index: 'index', crypto: 'cryptocurrency' })[kind] || 'symbol';
