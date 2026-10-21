// Questions worth asking on Home (Classic parity B8.5; Classic app.js marketQuestions and MARKET_QUESTION_POOL,
// its questions word for word). What happened today first: the day's biggest move against its own typical day, the
// session when it is shut, the day's top story, a release due today or tomorrow, any other move past its typical
// range in a market not already asked about. A pool fills the rest, rotated by the market day over the pool's fixed
// length, so a reading going quiet for an hour does not reshuffle it. Each question that names a number names a real
// one from /api/home; one that the payload does not support is left out. Nothing is written for it and nothing is
// spent: a press only drafts the question into Milo.

// ATR measures the high-to-low range, wider than the close-to-close move it is compared with (app/analytics/macro.py)
export const RANGE_PER_SIGMA = 1.6;
const inst = (d, group, label) => ((((d || {}).macro || {}).groups || {})[group] || []).find((r) => r.label === label) || null;
const has = (v) => v !== null && v !== undefined && Number.isFinite(Number(v));

/** The day's moves across the macro instruments, each against its own typical day, one row per market. */
export function rankedMoves(data) {
  const groups = (((data || {}).macro || {}).groups) || {};
  const rows = [];
  Object.entries(groups).forEach(([group, list]) => (list || []).forEach((i) => {
    if (!has(i.chg_1d)) return;
    const atr = Number(i.atr_pct) || 0;
    rows.push(Object.assign({}, i, { group, rel: atr ? Math.abs(i.chg_1d) / (atr / RANGE_PER_SIGMA) : 0 }));
  }));
  rows.sort((a, b) => b.rel - a.rel);
  const seen = new Set();   // the S&P 500 and its futures are one market quoted twice
  return rows.filter((r) => { const fam = String(r.label || r.symbol || '').replace(/\s+futures$/i, '').toLowerCase(); if (seen.has(fam)) return false; seen.add(fam); return true; });
}

export function marketDayKey(data) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String((((data || {}).session) || {}).now_et || ''));
  return m ? Math.floor(Date.UTC(+m[1], +m[2] - 1, +m[3]) / 864e5) : null;
}

export const POOL = [
  { id: 'vix', covers: 'volatility', make: (d) => { const v = inst(d, 'volatility', 'VIX'); return v && has(v.last) ? `VIX is at ${Number(v.last).toFixed(1)}. Is the market underpricing risk?` : null; } },
  { id: 'regime', make: (d) => { const r = (d.macro || {}).regime; return r ? `The regime reads ${r}. What would change it?` : null; } },
  { id: 'ratio', make: (d) => {
    const rs = ((d.macro || {}).ratios || []).filter((r) => r.name && has(r.chg_20d)); if (!rs.length) return null;
    const top = rs.reduce((a, b) => (Math.abs(b.chg_20d) > Math.abs(a.chg_20d) ? b : a));
    const reads = String(top.reads || '').split(/[;.]/)[0].trim().toLowerCase();
    return `${top.name} is ${top.chg_20d >= 0 ? 'up' : 'down'} ${Math.abs(top.chg_20d).toFixed(1)}% over twenty days${reads ? `, which reads as ${reads}` : ''}. Does that hold up?`;
  } },
  { id: 'breadth', make: (d) => {
    const c = ((d.indices || {}).counts) || {}, total = ['uptrend', 'downtrend', 'neutral'].reduce((n, k) => n + (Number(c[k]) || 0), 0);
    return total ? `${Number(c.uptrend) || 0} of ${total} index groups are in an uptrend and ${Number(c.downtrend) || 0} in a downtrend. Is this broadening or narrowing?` : null;
  } },
  { id: 'curve', covers: 'rates', make: (d) => { const c = (d.macro || {}).curve_3m10y; if (!has(c)) return null; return `The 3m/10y spread is ${c >= 0 ? '+' : ''}${Number(c).toFixed(2)} and ${c < 0 ? 'inverted' : 'positive'}. What is the curve saying about growth from here?`; } },
  { id: 'credit', covers: 'credit', make: (d) => { const h = inst(d, 'credit', 'HYG'); return h && has(h.chg_20d) ? `High yield is ${h.chg_20d >= 0 ? 'up' : 'down'} ${Math.abs(h.chg_20d).toFixed(1)}% over twenty days. Is credit agreeing with equities?` : null; } },
  { id: 'commodity', covers: 'commodities', make: (d) => {
    const ok = ((((d.macro || {}).groups) || {}).commodities || []).filter((r) => has(r.chg_20d)); if (!ok.length) return null;
    const top = ok.reduce((a, b) => (Math.abs(b.chg_20d) > Math.abs(a.chg_20d) ? b : a));
    return `${top.label} is ${top.chg_20d >= 0 ? 'up' : 'down'} ${Math.abs(top.chg_20d).toFixed(1)}% over twenty days. Is that demand or supply?`;
  } },
  { id: 'dollar', covers: 'fx', make: (d) => { const x = inst(d, 'fx', 'DXY') || inst(d, 'fx', 'Dollar'); return x && has(x.chg_20d) ? `The dollar is ${Math.abs(x.chg_20d).toFixed(1)}% ${x.chg_20d >= 0 ? 'stronger' : 'weaker'} over twenty days. Who does that hurt?` : null; } },
  // standing, on purpose: the question a reader asks on a day when nothing has moved enough to name
  { id: 'fed', covers: 'fed', make: () => 'What is the market expecting from the Fed?' },
];

const FED_WORDS = /\b(fed|fomc|powell|rate cut|rate hike|rates on hold)\b/i;
export function sessionQuestion(data) {
  const s = (data || {}).session || {};
  if (s.holiday) return `The market is closed for ${s.holiday}. What should I watch for the reopen?`;
  if (s.phase === 'overnight' || s.phase === 'closed') return 'Single stocks are not trading. What are the futures telling me?';
  return null;
}
const MOVE_ASKS = {
  equity: (m, dir, x) => `Why is the ${m.label} ${dir} ${x}% today?`,
  futures: (m, dir, x) => `${m.label} are ${dir} ${x}%. What are they pricing in?`,
  volatility: (m, dir, x) => (dir === 'up' ? `${m.label} is up ${x}% today. What is the market bracing for?` : `${m.label} is down ${x}% today. Is the market getting complacent?`),
  rates: (m, dir, x) => `The ${m.label} yield is ${dir} ${x}% today. What is moving rates?`,
  fx: (m, dir, x) => `Why is ${m.label} ${dir} ${x}% today?`,
  commodities: (m, dir, x) => `${m.label} is ${dir} ${x}% today. Is that supply or demand?`,
  credit: (m, dir, x) => `${m.label} is ${dir} ${x}% today. Is credit agreeing with stocks?`,
  crypto: (m, dir, x) => `Why is ${m.label} ${dir} ${x}% today?`,
};
export function moveQuestion(m) {
  if (!m || !m.label || !has(m.chg_1d)) return null;
  return (MOVE_ASKS[m.group] || MOVE_ASKS.fx)(m, m.chg_1d >= 0 ? 'up' : 'down', Math.abs(m.chg_1d).toFixed(1));
}
export function storyQuestion(data) {
  const top = (((data || {}).read || {}).stories || []).find((st) => st && st.title && String(st.title).trim().length <= 110);
  return top ? `${String(top.title).trim().replace(/[\s.!?:;,]+$/, '')}: what does that mean for markets?` : null;
}
const RELEASE_NAMES = { Jobs: 'The jobs report', CPI: 'CPI', PPI: 'PPI', FOMC: 'The Fed decision', JOLTS: 'JOLTS', ECI: 'The employment cost index', 'FOMC minutes': 'The Fed minutes' };
export function catalystQuestion(data) {
  const c = (((data || {}).morning_desk) || {}).catalyst;
  if (!c || !c.title || !(Number(c.importance) >= 5)) return null;
  const name = RELEASE_NAMES[c.short] || c.title, fed = c.short === 'FOMC', at = c.time_label ? ` at ${c.time_label}` : '';
  const due = Date.parse(c.at || ''), now = Date.parse((((data || {}).session) || {}).now_et || ''), out = Number.isFinite(due) && Number.isFinite(now) && now >= due;
  if (c.short === 'FOMC minutes') {   // minutes have no number to come in hot or cool
    if (c.days_away === 1) return `${name} are out tomorrow${at}. What could they change about the next decision?`;
    if (c.days_away !== 0) return null;
    return out ? `${name} came out today. What did they change about the next decision?` : `${name} are out today${at}. What could they change about the next decision?`;
  }
  if (c.days_away === 1) return fed ? `${name} is tomorrow${at}. What is priced in?` : `${name} is out tomorrow${at}. What would a hot or a cool number do?`;
  if (c.days_away !== 0) return null;
  if (out) return `${name} came out today. What did it change?`;
  return fed ? `${name} is today${at}. What is priced in?` : `${name} is out today${at}. What would surprise the market?`;
}

/** Up to five questions for the day, from /api/home. */
export function marketQuestions(data, n = 5) {
  if (!data) return [];
  const moves = rankedMoves(data), qs = [], asked = new Set();
  const add = (q, kind) => { if (!q || qs.includes(q)) return; qs.push(q); if (kind) asked.add(kind); };
  if (moves[0]) add(moveQuestion(moves[0]), moves[0].group);
  const shut = sessionQuestion(data); if (shut) add(shut, 'session');
  const story = storyQuestion(data); add(story, story && FED_WORDS.test(story) ? 'fed' : 'story');
  const release = catalystQuestion(data); add(release, release && FED_WORDS.test(release) ? 'fed' : 'release');
  // a move worth its own question is one past its instrument's whole average range: about one day in ten
  moves.slice(1).filter((m) => m.rel >= RANGE_PER_SIGMA && !asked.has(m.group)).slice(0, 2).forEach((m) => add(moveQuestion(m), m.group));
  const day = marketDayKey(data), off = day === null ? 0 : ((day % POOL.length) + POOL.length) % POOL.length;
  for (let i = 0; i < POOL.length; i += 1) {
    const e = POOL[(off + i) % POOL.length];
    if (e.covers && asked.has(e.covers)) continue;
    let q = null; try { q = e.make(data); } catch (err) { q = null; }   // one bad entry must not empty the panel
    if (q && !qs.includes(q)) qs.push(q);
  }
  return qs.slice(0, n);
}
