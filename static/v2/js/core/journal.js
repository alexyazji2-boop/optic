// The trade journal (roadmap stage 3, 2026-10-22): what a practice trade was planned to be, kept apart from
// what happened, and a review of the record. Pure functions over the Paper Desk's own trade objects
// (optic.paper.v1), so the journal is the book, not a second store that could disagree with it.
//
// Three rules, from the brief:
// - The plan is frozen when the trade opens. Editing it later appends a revision; the original stays readable.
// - Evidence is counted by source family, because two momentum oscillators are one piece of evidence, not two.
//   A count of independent families is a description of the case, not a probability.
// - Every statistic says how many trades it rests on, and which records were missing what it needed.

export const SETUPS = [
  ['pullback', 'Pullback in a trend'], ['breakout', 'Breakout'], ['earnings', 'Earnings reaction'],
  ['reversal', 'Reversal'], ['range', 'Range trade'], ['other', 'Other'],
];
// Families of evidence that move together. Indicators inside one family are read off the same prices (or the
// same option chain) and so are not independent confirmations of each other.
export const FAMILIES = {
  trend: { label: 'Price trend', examples: 'moving averages, higher highs, trend lines' },
  momentum: { label: 'Momentum', examples: 'RSI, MACD, stochastics: all read from the same closes' },
  volume: { label: 'Volume', examples: 'volume against its average, accumulation' },
  levels: { label: 'Levels', examples: 'support, resistance, Fibonacci' },
  options: { label: 'Options positioning', examples: 'dealer gamma, the flow proxy, skew: all read from one chain' },
  fundamentals: { label: 'Business and valuation', examples: 'results, margins, valuation against history' },
  catalyst: { label: 'News or a scheduled event', examples: 'a report, a filing, a product date' },
  market: { label: 'The market', examples: 'the regime, the sector, the index' },
};
const clip = (s, n) => String(s || '').slice(0, n);
const num = (v) => (v === null || v === undefined || String(v).trim() === '' || !Number.isFinite(Number(v)) ? null : Number(v));

/** The plan as it stood when the trade opened. Nothing in it is changed afterwards. */
export function freezePlan(f, at = new Date().toISOString()) {
  const evidence = (f.evidence || []).filter((e) => e && String(e.text || '').trim())
    .slice(0, 12).map((e) => ({ text: clip(e.text, 160), family: FAMILIES[e.family] ? e.family : 'trend' }));
  return {
    at, thesis: clip(f.thesis, 600), setup: SETUPS.some(([k]) => k === f.setup) ? f.setup : 'other',
    evidence, against: (f.against || []).map((x) => clip(x, 160)).filter(Boolean).slice(0, 8),
    catalyst: clip(f.catalyst, 120) || null, catalyst_date: /^\d{4}-\d{2}-\d{2}$/.test(f.catalyst_date || '') ? f.catalyst_date : null,
    hold_through_catalyst: !!f.hold_through_catalyst,
    trigger: clip(f.trigger, 200) || null, invalidation: clip(f.invalidation, 200) || null,
    hold_days: num(f.hold_days), stop: num(f.stop), target: num(f.target), risk: num(f.risk),
    source: f.source ? clip(f.source, 80) : null,
  };
}

/** A later change to the plan, kept beside it: the original is never overwritten. */
export function revise(trade, changes, at = new Date().toISOString()) {
  const plan = trade.plan || {};
  const revs = (trade.revisions || []).slice();
  Object.entries(changes || {}).forEach(([k, v]) => {
    const now = currentPlan(trade)[k];
    if (JSON.stringify(now) !== JSON.stringify(v)) revs.push({ at, field: k, from: now === undefined ? null : now, to: v });
  });
  return { ...trade, plan, revisions: revs };
}
/** The plan with its revisions applied, for display beside the original. */
export function currentPlan(trade) {
  const out = { ...(trade.plan || {}) };
  (trade.revisions || []).forEach((r) => { out[r.field] = r.to; });
  return out;
}

/** How many independent kinds of evidence the case rests on, and where it repeats itself. */
export function independence(evidence) {
  const by = {};
  (evidence || []).forEach((e) => { (by[e.family] = by[e.family] || []).push(e.text); });
  const families = Object.keys(by);
  const repeated = families.filter((f) => by[f].length > 1).map((f) => ({ family: f, label: FAMILIES[f].label, n: by[f].length }));
  return {
    items: (evidence || []).length, families: families.length, repeated,
    note: !(evidence || []).length ? 'No supporting evidence recorded.'
      : `${families.length} independent ${families.length === 1 ? 'kind' : 'kinds'} of evidence from ${(evidence || []).length} ${(evidence || []).length === 1 ? 'item' : 'items'}`
        + (repeated.length ? `; ${repeated.map((r) => `${r.n} ${r.label.toLowerCase()} readings count once`).join(', ')}` : '')
        + '. A count of agreeing evidence is not a probability.',
  };
}

const daysBetween = (a, b) => (Date.parse(b) - Date.parse(a)) / 86400000;
const holdBucket = (d) => (d === null ? 'unknown' : d <= 5 ? 'up to 5 days' : d <= 20 ? '6 to 20 days' : d <= 60 ? '21 to 60 days' : 'over 60 days');

function stats(rows) {
  const n = rows.length, wins = rows.filter((t) => t.pnl > 0), losses = rows.filter((t) => t.pnl < 0);
  const sum = (xs, k) => xs.reduce((a, t) => a + (Number(t[k]) || 0), 0);
  const withR = rows.filter((t) => Number.isFinite(t.r));
  return {
    n, wins: wins.length, losses: losses.length, win_rate: n ? wins.length / n : null,
    avg_win: wins.length ? sum(wins, 'pnl') / wins.length : null, avg_loss: losses.length ? sum(losses, 'pnl') / losses.length : null,
    expectancy: n ? sum(rows, 'pnl') / n : null, expectancy_r: withR.length ? sum(withR, 'r') / withR.length : null, n_r: withR.length,
  };
}

/** The review of closed trades. `closed` is the Paper Desk's closed list, newest first. */
export function review(closed) {
  const rows = (closed || []).filter((t) => Number.isFinite(Number(t.pnl))).map((t) => ({ ...t, pnl: Number(t.pnl) }));
  const planned = rows.filter((t) => t.plan);
  const missing = {
    no_plan: rows.length - planned.length,
    no_setup: planned.filter((t) => !t.plan.setup || t.plan.setup === 'other').length,
    no_hold: planned.filter((t) => !Number.isFinite(t.plan.hold_days)).length,
    no_adherence: rows.filter((t) => !t.adherence || Object.values(t.adherence).every((v) => !v)).length,
    no_reflection: rows.filter((t) => !String(t.reflection || '').trim()).length,
  };
  const group = (key) => {
    const g = {};
    rows.forEach((t) => { const k = key(t); (g[k] = g[k] || []).push(t); });
    return Object.entries(g).map(([k, xs]) => ({ key: k, ...stats(xs) })).sort((a, b) => b.n - a.n);
  };
  const setupLabel = (k) => (SETUPS.find(([x]) => x === k) || [k, 'Not recorded'])[1];
  const held = (t) => (t.entry_at && t.closed_at ? daysBetween(t.entry_at, t.closed_at) : null);
  // the realised curve in close order, oldest first; drawdown from its running peak
  const chrono = rows.slice().sort((a, b) => Date.parse(a.closed_at || 0) - Date.parse(b.closed_at || 0));
  let eq = 0, peak = 0, dd = 0;
  chrono.forEach((t) => { eq += t.pnl; peak = Math.max(peak, eq); dd = Math.min(dd, eq - peak); });
  const adherenceOf = (t) => { const a = t.adherence || {}; const vals = Object.values(a).filter((v) => v === 'yes' || v === 'no'); return !vals.length ? 'not recorded' : vals.every((v) => v === 'yes') ? 'followed the plan' : 'departed from it'; };
  const throughOf = (t) => (!t.plan || !t.plan.catalyst_date ? 'no catalyst recorded'
    : t.closed_at && t.closed_at.slice(0, 10) >= t.plan.catalyst_date && (t.entry_at || '').slice(0, 10) <= t.plan.catalyst_date ? 'held through its catalyst' : 'out before or after its catalyst');
  return {
    all: stats(rows),
    by_setup: group((t) => (t.plan && t.plan.setup) || 'unrecorded').map((x) => ({ ...x, label: x.key === 'unrecorded' ? 'Not recorded' : setupLabel(x.key) })),
    by_hold: group((t) => holdBucket(held(t))).map((x) => ({ ...x, label: x.key })),
    by_catalyst: group(throughOf).map((x) => ({ ...x, label: x.key })),
    by_adherence: group(adherenceOf).map((x) => ({ ...x, label: x.key })),
    max_drawdown: chrono.length >= 2 ? dd : null,
    missing, small: rows.length < 30,
    note: rows.length < 30 ? `${rows.length} closed ${rows.length === 1 ? 'trade' : 'trades'}: too few to say whether any of these differences is more than chance.` : null,
  };
}

/** What Milo is given to review: the recorded plan and outcome only, with the rule it must keep. */
export function forMilo(closed, limit = 20) {
  return {
    rule: 'Review only what is recorded here. Do not invent trades, prices, motives or explanations; where a field is empty, say it was not recorded.',
    trades: (closed || []).slice(0, limit).map((t) => ({
      ticker: t.ticker, direction: t.direction, instrument: t.instrument, entry_price: t.entry_price, exit_price: t.exit_price,
      pnl: t.pnl, r: t.r, opened: t.entry_at, closed: t.closed_at, plan: t.plan || null, revisions: t.revisions || [],
      exit_note: t.exit_note || null, adherence: t.adherence || null, reflection: t.reflection || null,
    })),
  };
}
