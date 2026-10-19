// Home, as the research workspace (owner, 2026-10-18): panels on a 12-column
// grid, chosen by a layout (Market Overview by default), moved, resized,
// hidden, locked and reset by the reader, and kept in this browser
// (optic.v2.workspace.v1, a setting, not personal data). Panels marked
// `linked` follow one shared ticker; the rest are about the market. Home's
// own blocks (the welcome, What matters today, the Desk, the portfolio) come
// from pages/home.js unchanged. Every panel reads Optic's existing data
// sources and says how fresh they are; none invents a figure, a grade or a
// probability. On a phone the essential panels are open and the rest folded,
// loading only when opened. VISUAL-SPEC-DARK.md and WORKSPACE.md.
import { $, $$, html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, signed, money, compact, dir, isNum, ago, clean, shortDate } from '../core/format.js';
import { etDay } from '../core/marketTime.js';
import { skeleton, failed } from '../ui/states.js';
import { lineChart, spark, mountCharts, meter } from '../ui/chart.js';
import { provideContext } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { icon } from '../ui/icons.js';
import { go } from '../core/router.js';
import { hello, etDate, portfolio, eventsBlock, welcome, starters, modes, STARTERS, setScene, portfolioSeries, wireForms } from './home.js';

const KEY = 'optic.v2.workspace.v1';
const VERSION = 3;   // 3: default heights per panel type (2026-10-18, second review); the link, the lock and My Desk carry over
const SPANS = [3, 4, 6, 8, 12];
const HEIGHTS = ['s', 'm', 'l'];
const HEIGHT_WORDS = { s: 'compact', m: 'standard', l: 'tall' };

/* ---------------- presets: [panel, span, height] ---------------- */
export const PRESETS = {
  // Each row pairs a panel that sizes to its content with a list that fills the rest of the row's height,
  // so no panel stands half empty beside a cramped one (LIST below; VISUAL-SPEC-DARK.md section 4).
  market: { label: 'Market Overview', panels: [['indices', 12, 'm'], ['portfolio', 12, 'm'], ['quote', 8, 'm'], ['watch', 4, 's'], ['priority', 8, 'm'], ['cnews', 4, 's'], ['contracts', 12, 'l'], ['regime', 8, 'm'], ['expected', 4, 'm'], ['sectors', 6, 'm'], ['calendar', 6, 's'], ['desk', 6, 'm'], ['earnings', 6, 's'], ['movers', 4, 's'], ['news', 4, 's'], ['alerts', 4, 's'], ['economy', 12, 'l']] },
  options: { label: 'Options Research', panels: [['watch', 4, 's'], ['quote', 8, 'm'], ['contracts', 12, 'l'], ['expected', 4, 'm'], ['earnings', 8, 's'], ['cnews', 6, 's'], ['movers', 6, 's']] },
  longterm: { label: 'Long-Term Investing', panels: [['portfolio', 12, 'm'], ['quote', 8, 'm'], ['watch', 4, 's'], ['value', 6, 'm'], ['sectors', 6, 'm'], ['regime', 8, 'm'], ['cnews', 4, 's'], ['economy', 12, 'l']] },
  mine: { label: 'My Desk', panels: null },     // the reader's own; starts as a copy of Market Overview
};

// Open on a phone without asking: what a reader checks first. The rest fold to
// their title and one line, and load only when opened.
const ESSENTIAL = { market: ['indices', 'portfolio', 'quote', 'watch', 'priority'], options: ['watch', 'quote', 'contracts'], longterm: ['portfolio', 'watch', 'quote', 'value'], mine: ['indices', 'portfolio', 'priority', 'watch', 'quote'] };
const PHONE = '(max-width: 860px)';
const isPhone = () => { try { return matchMedia(PHONE).matches; } catch (e) { return false; } };
const folded = (id) => isPhone() && ((S.fold[S.preset] || {})[id] ?? !(ESSENTIAL[S.preset] || []).includes(id));

// How fresh each panel's figures are, from the server's own caches
// (providers/yf.py TTLs, fred.py, the route docstrings), not a guess.
const FRESH = {
  indices: 'Quotes delayed about 15 minutes; refreshed every minute while the market is open.',
  portfolio: 'Valued at Optic\'s delayed prices, refreshed every minute in session; quantities as of the last broker sync.',
  priority: 'Rebuilt at most every 10 minutes.',
  watch: 'Quotes delayed about 15 minutes; refreshed every minute while the market is open.',
  quote: 'Quote delayed about 15 minutes; daily closes re-read at most every 5 minutes.',
  cnews: 'Headlines re-read at most every 10 minutes.',
  contracts: 'Chain delayed about 15 minutes; re-read at most once a minute.',
  regime: 'From delayed quotes and daily closes; refreshed every minute while the market is open.',
  expected: 'From the delayed VIX and index; refreshed every minute while the market is open.',
  sectors: 'Fund prices delayed about 15 minutes; refreshed every minute while the market is open.',
  calendar: 'Schedule from the last built Read (built every 20 minutes); actual and prior from FRED, re-read at most every 6 hours.',
  desk: 'Written before the open and after the close; this is the latest edition.',
  earnings: 'Rebuilt at most once an hour; report dates move on the scale of days.',
  movers: 'From Optic\'s nightly universe scan.',
  news: 'From the last built Read, built every 20 minutes.',
  alerts: 'From the scheduled scan.',
  economy: 'FRED series change on release days; Optic re-reads them at most every 6 hours.',
  value: 'Earnings data re-read at most every 6 hours; price delayed about 15 minutes.',
};
// The footer's one line: a short source and a status in a word or two. The full source, FRESH and
// any calculation note are in the panel's "About this panel" explanation (owner, 2026-10-18).
const SRC = { indices: 'Yahoo Finance', portfolio: 'Your brokerage', priority: 'Optic', watch: 'Yahoo Finance', quote: 'Yahoo Finance', cnews: 'Publisher feeds',
  contracts: 'Yahoo Finance chain', regime: 'Optic rules', expected: 'Yahoo Finance', sectors: 'Yahoo Finance', calendar: 'Agency schedules', desk: 'Optic Desk',
  earnings: 'Yahoo Finance', movers: 'Optic scan', news: 'Wire feeds', alerts: 'Optic scan', economy: 'FRED', value: 'Yahoo Finance, SEC' };
const QUOTED = new Set(['indices', 'portfolio', 'watch', 'quote', 'contracts', 'regime', 'expected', 'sectors', 'value']);
const CADENCE = { priority: 'Every 10 min', cnews: 'Every 10 min', calendar: 'Every 20 min', news: 'Every 20 min', desk: 'Latest edition', earnings: 'Hourly', movers: 'Nightly scan', alerts: 'Scheduled scan', economy: 'Every 6 h' };
// How often each cadence panel's source is rebuilt; data older than three of these says its age instead.
const CADENCE_MS = { priority: 6e5, cnews: 6e5, calendar: 12e5, news: 12e5, earnings: 36e5, economy: 216e5 };
const marketOpen = () => !!(((DATA.indices || {}).session) || {}).is_regular;
// Quoted panels say which prices they hold: delayed in session, otherwise the close they are from
// (the footer's "Updated" time is when Optic fetched them, not when they traded).
const lastClose = () => ((((DATA.indices || {}).session) || {}).last_close || {}).date;
const statusOf = (id) => (QUOTED.has(id) ? (marketOpen() ? 'Delayed 15 min' : (lastClose() ? `${etDay(lastClose()).replace(/^\w+ /, '')} close` : 'Last close')) : (CADENCE[id] || ''));
// Lists and tables take a default height for their kind and fill the rest of their row; the other
// panels size to their content.
const LIST = new Set(['watch', 'cnews', 'contracts', 'calendar', 'earnings', 'movers', 'news', 'alerts']);
// Chart heights by the panel's height choice, desktop and phone.
const CH = { portfolio: { s: 150, m: 200, l: 280, phone: 150 }, quote: { s: 170, m: 230, l: 340, phone: 170 }, economy: { s: 160, m: 220, l: 300, phone: 150 } };
const portfolioMarks = () => ((((DATA.portfolio || {}).perf || {}).sources || {}).switches || []).map((x) => ({ d: String(x.date).slice(0, 10), label: 'Source changes', detail: 'estimated balances before, Optic\'s own snapshots after; the step is not a gain or loss' }));
const chartH = (id) => { const c = CH[id], x = (S.layouts[S.preset] || []).find((y) => y.id === id); return isPhone() ? c.phone : c[(x && x.h) || 'm']; };

// What a folded panel says in its one line on a phone.
const BLURB = {
  indices: 'The main indices, volatility, yields, oil, gold and bitcoin.', portfolio: 'Your linked accounts\' value and the day\'s move.', priority: 'Releases, reports and sector moves, by when they land.',
  watch: 'Your open list with the day\'s move.', quote: 'The linked ticker\'s price and chart.', cnews: 'Headlines about the linked ticker.', contracts: 'Option contracts for the linked ticker at one expiry.',
  regime: 'The regime score with its factors, and the sentiment gauge.', expected: 'What index options price for one day.', sectors: 'The 11 sector funds by their move.',
  calendar: 'Scheduled U.S. releases this week.', desk: 'The day\'s Optic Desk edition.', earnings: 'Who reports this week and next.', movers: 'The largest one-month moves.',
  news: 'The day\'s wire headlines.', alerts: 'The scheduled scan\'s latest alerts.', economy: 'U.S. indicators with their history.', value: 'The linked ticker against its own valuation history.',
};

/* ---------------- state, persisted ---------------- */
let S = null;
function defaults(preset) { const p = PRESETS[preset].panels || PRESETS.market.panels; return p.map(([id, span, h]) => ({ id, span, h, hidden: false })); }
function load() {
  let v = null;
  try { v = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { v = null; }
  const ok = v && v.v === VERSION && PRESETS[v.preset];
  S = ok ? v : { v: VERSION, preset: 'market', layouts: {}, locked: false, link: '', fold: {} };
  if (!ok && v && v.v === 2) Object.assign(S, { link: v.link || '', locked: !!v.locked, layouts: v.layouts && Array.isArray(v.layouts.mine) ? { mine: v.layouts.mine } : {}, preset: v.preset === 'mine' ? 'mine' : 'market' });
  S.fold = S.fold || {};
  Object.keys(PRESETS).forEach((p) => { if (!Array.isArray(S.layouts[p])) S.layouts[p] = defaults(p); });
  // a panel a later version adds appears hidden in older saved layouts, never lost
  Object.keys(PRESETS).forEach((p) => { const have = new Set(S.layouts[p].map((x) => x.id)); Object.keys(PANELS).forEach((id) => { if (!have.has(id)) S.layouts[p].push({ id, span: PANELS[id].span || 6, h: 'm', hidden: true }); }); S.layouts[p] = S.layouts[p].filter((x) => PANELS[x.id]); });
  if (!S.link) S.link = (((store.activeList() || {}).symbols || [])[0] || store.recent()[0] || 'SPY');
}
function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* private mode: the layout lasts this visit */ } }
const layout = () => S.layouts[S.preset];

/* ---------------- shared data ---------------- */
const get = (u, o = {}) => api.get(u, Object.assign({ ttl: 30000, timeout: 30000 }, o));
const enc = encodeURIComponent;
const pct = (v, dp = 2) => (isNum(v) ? signed(v, dp) : 'n/a');
// The contract table's columns. Sorting is the reader's choice; Optic ranks nothing (contracts.py).
const LIQ = { good: 3, fair: 2, poor: 1, not_tradable: 0 };   // analytics/liquidity.py grades
const CONTRACT_COLS = [
  // sec: hidden in a phone's row, shown when the row opens (or with All columns)
  { key: 'strike', label: 'Strike', num: true, v: (r) => r.strike, cell: (r) => num(r.strike) },
  { key: 'mid', label: 'Mid', num: true, sec: true, v: (r) => r.mid, cell: (r) => num(r.mid) },
  { key: 'cost', label: 'Cost', num: true, v: (r) => r.mid * 100, cell: (r) => money(r.mid * 100, 0) },
  { key: 'spread', label: 'Spread', num: true, sec: true, v: (r) => r.spread_pct, cell: (r) => `${num(r.spread_pct, 1)}%` },
  { key: 'delta', label: 'Delta', num: true, v: (r) => r.delta, cell: (r) => num(r.delta, 2) },
  { key: 'iv', label: 'IV', num: true, sec: true, v: (r) => r.iv_pct, cell: (r) => `${num(r.iv_pct, 1)}%` },
  { key: 'oi', label: 'Open int.', num: true, sec: true, v: (r) => r.open_interest, cell: (r) => compact(r.open_interest) },
  { key: 'vol', label: 'Volume', num: true, sec: true, v: (r) => r.volume, cell: (r) => compact(r.volume) },
  { key: 'liq', label: 'Liquidity', v: (r) => LIQ[String((r.liquidity || {}).grade || '').toLowerCase()], cell: (r) => (r.liquidity || {}).label || '' },
];
// An indicator in its own unit. /api/econ passes FRED's raw scale for levels, which differs by
// series: claims in persons, payrolls, openings and starts in thousands, the Fed's balance
// sheet already in billions (econ.py divides it). [multiplier to the shown unit, suffix]
const ECON_SCALE = { ICSA: [1 / 1000, 'K'], PAYEMS: [1, 'K'], HOUST: [1, 'K'], JTSJOL: [1 / 1000, 'M'], WALCL: [1, 'B'] };
const econVal = (v, unit, code) => {
  if (!isNum(v)) return 'n/a';
  if (unit === '%') return `${num(v, 2)}%`;
  const [k, suf] = ECON_SCALE[code] || [1, ''];
  const x = v * k;
  return `${unit === '$' ? '$' : ''}${num(x, Math.abs(x) >= 100 ? 0 : Math.abs(x) >= 10 ? 1 : 2)}${suf}`;
};
const econChg = (v, unit, code) => (isNum(v) ? `${v > 0 ? '+' : v < 0 ? '−' : ''}${unit === '%' ? `${num(Math.abs(v), 2)} pp` : econVal(Math.abs(v), unit, code)}` : '');
const asof = (iso) => {
  if (!iso) return '';
  // a bare date (a daily close) has no time to show, and read as a moment it lands on the evening before
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(iso))) return `Through ${shortDate(iso)}`;
  const t = new Date(iso), today = new Date().toDateString() === t.toDateString();
  return `Updated ${today ? '' : `${t.toLocaleDateString([], { month: 'short', day: 'numeric' })}, `}${t.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
};

/* ---------------- the panels ---------------- */
const STRIP = [['equity', 'S&P 500'], ['equity', 'Nasdaq 100'], ['equity', 'Russell 2000'], ['volatility', 'VIX'], ['rates', 'US 10Y'], ['commodities', 'WTI Crude'], ['commodities', 'Gold'], ['crypto', 'Bitcoin']];
const inst = (d, g, l) => ((((d || {}).macro || {}).groups || {})[g] || []).find((r) => r.label === l) || null;
function moveText(i) {
  if (!isNum(i.chg_1d)) return '';
  if (i.group === 'rates' && isNum(i.last)) { const bp = Math.round((i.last - i.last / (1 + i.chg_1d / 100)) * 100); return `${bp > 0 ? '+' : bp < 0 ? '−' : ''}${Math.abs(bp)} bp`; }
  return signed(i.chg_1d);
}
const tickBtn = (sym, label) => html`<button type="button" class="ws-tick" data-ws-pick="${sym}" aria-pressed="${S.link === sym}">${label || sym}</button>`;

export const PANELS = {
  portfolio: {
    title: 'Your portfolio', span: 12, optional: true,
    how: 'Your linked brokerage accounts at Optic\'s delayed prices, the day\'s move, and the holdings that moved the total most. The chart is the account value your broker reported, which includes your own deposits and withdrawals, so it is not a return.',
    load: async () => {
      const st = await get('/api/brokerage/status', { ttl: 60000 }).catch(() => null);
      const linked = st && st.available && (st.connections || []).some((c) => c.status !== 'disconnected');
      if (!linked) return { absent: true };
      const [ov, perf] = await Promise.all([get('/api/brokerage/workspace/overview', { ttl: 60000 }), get('/api/brokerage/workspace/performance?period=3m', { ttl: 300000 }).catch(() => null)]);
      return { ov, perf };
    },
    body: (d) => portfolio(d.ov, d.perf),
    charts: () => ({ portfolio: (w) => { const s2 = portfolioSeries(); return s2.length > 1 ? lineChart(s2, { w, h: chartH('portfolio'), area: true, label: 'Portfolio value', dp: 0, marks: portfolioMarks() }) : ''; } }),
    foot: () => ({ source: 'Your linked brokerage, read-only' }),
    milo: 'What moved my portfolio today, and is anything concentrated?',
  },
  priority: {
    title: 'What matters today', span: 8, state: { filter: 'all' },
    how: 'The calendar, this week\'s earnings and the sector board, sorted by when they land: now, today, this week. Choose an item for why it matters. Your names shows only events for companies you follow.',
    load: () => get('/api/priority?quick=true', { ttl: 300000, timeout: 90000 }),
    body: (d, P) => (!d || d.available === false ? html`<p class="ws-note">${clean((d && d.reason) || 'The calendar did not return anything.')}</p>` : eventsBlock(d, store.allSymbols(), P.filter)),
    foot: (d) => ({ source: 'Agency calendars, company report dates and the sector board, via Optic', at: (d || {}).generated_at }),
    milo: 'Of what is coming up this week, what matters most for the market and for my names?',
  },
  desk: {
    title: 'Optic Desk', span: 6,
    how: 'The day\'s edition: the lead lines first, the full read one step away. On a day with no written edition it is built from the numbers by fixed rules, and says so.',
    load: () => get('/api/home'),
    body: (d) => {
      const md = (d || {}).morning_desk;
      if (!md || !md.available) return html`<p class="ws-note">${clean((md && md.reason) || 'No Desk edition is available right now.')}</p>`;
      return html`<p class="ws-sub">${md.voice === 'mechanical' ? 'Written from the numbers by fixed rules today.' : 'The day\'s edition.'} ${md.date ? `For ${shortDate(md.date)}.` : ''}</p>
        <ul class="desk-lead">${(md.lead || []).map((l) => html`<li>${clean(l)}</li>`)}</ul>
        ${md.overall ? html`<details class="more"><summary>The full read ${icon('chev')}</summary><div class="inner"><p>${clean(md.overall)}</p>${md.note ? html`<p class="t-muted">${clean(md.note)}</p>` : ''}</div></details>` : ''}`;
    },
    foot: (d) => ({ source: 'Optic Desk', at: (d || {}).generated_at }),
    milo: 'Walk me through today\'s Desk.',
  },
  alerts: {
    title: 'Latest scan alerts', span: 4,
    how: 'What Optic\'s scheduled scan flagged most recently. Choose one to open the company; the full list and your own watches are in Alerts.',
    load: () => get('/api/home'),
    body: (d) => {
      const al = ((d || {}).alerts || []).slice(0, 6);
      if (!al.length) return html`<p class="ws-note">The scheduled scan has not flagged anything recently.</p>`;
      return html`<ul class="ws-news">${al.map((a) => html`<li><a href="#/${a.ticker || ''}"><b class="tick">${a.ticker || ''}</b> ${clean(a.title)}</a><span class="ws-rule">${ago(a.created_at)}</span></li>`)}</ul><p><a class="textlink" href="#/alerts">Alerts ${icon('arrow')}</a></p>`;
    },
    foot: () => ({ source: 'Optic scheduled scan' }),
    milo: 'Explain the latest scan alerts.',
  },
  indices: {
    title: 'Indices', span: 12,
    how: 'The day\'s move for the main U.S. indices, volatility, the 10-year yield, oil, gold and bitcoin. Yields move in basis points (0.01 percentage points). Outside the regular session most of these are at the last close; futures and crypto keep trading.',
    load: () => get('/api/home'),
    body: (d) => {
      const cells = STRIP.map(([g, l]) => inst(d, g, l)).filter((i) => i && isNum(i.last));
      if (!cells.length) return html`<p class="ws-note">No index readings came back from the feed.</p>`;
      return html`<div class="ws-strip">${cells.map((i) => html`<a class="ws-cell" href="#/instrument/${enc(i.symbol)}"><span class="k">${i.label}</span><span class="v">${num(i.last, i.last < 20 ? 2 : i.last > 1000 ? 0 : 2)}</span><span class="d ${dir(i.chg_1d)}">${moveText(i)}</span></a>`)}</div>`;
    },
    foot: (d) => ({ source: 'Yahoo Finance via Optic', at: d.generated_at, note: ((d.session || {}).is_regular ? '' : 'Outside the regular session, equities are at the last close; futures and crypto keep trading.'), stale: (d.degraded || []).length ? 'Some missing' : '', staleWhy: (d.degraded || []).length ? `Not available: ${d.degraded.join(', ')}.` : '' }),
    milo: 'What do today\'s index, volatility, yield and commodity moves say together?',
  },
  regime: {
    title: 'Sentiment and regime', span: 6,
    how: 'Two separate reads. The regime score adds up named rules (VIX level and change, trend, credit, the curve): each factor shows how much it moved the score. The sentiment gauge averages several market inputs into 0 to 100, where low is fear. When they disagree, the factors say why.',
    load: async () => { const [h, s] = await Promise.all([get('/api/home'), get('/api/sentiment', { ttl: 120000 }).catch((e) => ({ available: false, reason: api.explain(e, 'Sentiment') }))]); return { h, s }; },
    body: ({ h, s }) => {
      const m = (h || {}).macro || {};
      const factors = (m.factors || []).slice().sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 5);
      return html`<div class="ws-two">
        <div><p class="ws-k">Regime</p><p class="ws-big">${capitalize(m.regime || 'n/a')}</p><p class="ws-sub">Score ${num(m.risk_score, 1)} on −100 to +100</p>
          <table class="ws-t"><caption class="sr">Regime factors, largest first</caption><thead><tr><th scope="col">Factor</th><th scope="col" class="n">Reading</th><th scope="col" class="n">Effect</th></tr></thead>
          <tbody>${factors.map((f) => html`<tr><td>${f.factor}<span class="ws-rule ws-clip" title="${f.rule || ''}">${f.rule || ''}</span></td><td class="n">${num(f.value, 2)}</td><td class="n ${dir(f.contribution)}">${f.contribution > 0 ? '+' : ''}${num(f.contribution, 1)}</td></tr>`)}</tbody></table></div>
        <div><p class="ws-k">Sentiment</p>${s && s.available !== false ? html`<p class="ws-big">${num(s.score, 0)} <span class="ws-word">${s.label}</span></p><p class="ws-sub">0 is extreme fear, 100 extreme greed</p>
          <ul class="ws-bars">${(s.components || []).map((c) => html`<li><span>${c.label}</span><span class="ws-gauge" aria-hidden="true"><i style="width:${Math.max(2, Math.min(100, c.score || 0))}%"></i></span><b>${num(c.score, 0)}</b></li>`)}</ul>`
          : html`<p class="ws-note">${(s && s.reason) || 'The sentiment gauge is not available right now.'}</p>`}</div></div>`;
    },
    foot: ({ h, s }) => ({ source: 'Optic regime rules; Optic sentiment gauge', at: (s && s.generated_at) || (h || {}).generated_at }),
    milo: 'Where do the regime factors and the sentiment components agree or conflict right now?',
  },
  expected: {
    title: 'Expected move', span: 6,
    how: 'What S&P 500 options price for one day, from the VIX (annualised volatility divided by the square root of 252), next to how far the index has actually been moving (14-day average true range). A ratio above 1 means protection costs more than recent movement.',
    load: () => get('/api/home'),
    body: (d) => {
      const em = ((d || {}).macro || {}).expected_move || {};
      if (!isNum(em.implied_pct)) return html`<p class="ws-note">The expected move needs the VIX and the S&P 500 level; one of them did not come back.</p>`;
      return html`<dl class="ws-kv"><div><dt>Priced for one day</dt><dd>±${num(em.implied_pct)}%<small>±${num(em.implied_points, 0)} points on ${num(em.spot, 0)}</small></dd></div>
        <div><dt>Recently delivered</dt><dd>${num(em.atr_pct)}%<small>14-day average true range</small></dd></div>
        <div><dt>Priced against delivered</dt><dd>${num(em.ratio, 2)}×<small>VIX ${num(em.vix)}</small></dd></div></dl>
        <p class="ws-read">${clean(em.reading || '')}</p>`;
    },
    foot: (d) => ({ source: 'VIX and S&P 500 from Yahoo Finance; Optic arithmetic', at: d.generated_at }),
    milo: 'Is the market\'s one-day expected move rich or cheap against what the index has been doing, and what would change that?',
  },
  sectors: {
    title: 'Sector heatmap', span: 6, state: { period: 'chg_1d' },
    how: 'The 11 sector funds, coloured by their move over the chosen period: green rose, red fell, and the stronger the colour the larger the move. Choose a tile to link its fund to the linked panels. The colour never carries meaning alone: every tile shows its figure.',
    load: () => get('/api/market', { ttl: 60000 }),
    body: (d, P) => {
      const rows = (((d || {}).sectors || {}).sectors || []).filter((r) => isNum(r[P.period]));
      if (!rows.length) return html`<p class="ws-note">No sector readings came back from the feed.</p>`;
      const max = Math.max(...rows.map((r) => Math.abs(r[P.period]))) || 1;
      return html`<div class="seg ws-seg" role="group" aria-label="Period">${[['chg_1d', '1 day'], ['chg_5d', '1 week'], ['chg_20d', '1 month']].map(([k, l]) => html`<button type="button" data-ws-set="sectors:period:${k}" aria-pressed="${P.period === k}">${l}</button>`)}</div>
        <div class="ws-heat">${rows.sort((a, b) => b[P.period] - a[P.period]).map((r) => { const v = r[P.period], a = Math.round(10 + 45 * Math.abs(v) / max);
          return html`<button type="button" class="ws-heat-t" data-ws-pick="${r.symbol}" aria-pressed="${S.link === r.symbol}" style="--mix:${a}%" data-dir="${dir(v)}"><span>${r.label || r.name}</span><b>${r.symbol}</b><span class="${dir(v)}">${signed(v)}</span></button>`; })}</div>`;
    },
    foot: (d) => ({ source: 'Sector SPDR funds, Yahoo Finance', at: (d || {}).generated_at }),
    milo: 'Which sectors are leading and lagging, and is it broad rotation or a few names?',
  },
  calendar: {
    title: 'Economic calendar', span: 6, state: { imp: 'all' },
    how: 'Scheduled U.S. releases and market events for the coming days, with the time in New York and how much each usually matters. Released shows once a figure is out.',
    load: () => get('/api/brief?cached=true', { ttl: 120000 }),
    body: (d, P) => {
      if (!d || d.missing) return html`<p class="ws-note">${(d && d.reason) || 'The day\'s Read, which carries the calendar, has not been built yet.'}</p>`;
      let ev = ((d.calendar || {}).events || []);
      if (P.imp === 'high') ev = ev.filter((e) => e.impact === 'high' || e.impact === 'medium');
      if (!ev.length) return html`${impSeg(P)}<p class="ws-note">Nothing scheduled${P.imp === 'high' ? ' at medium or high impact' : ''} in the window.</p>`;
      const withFig = ev.some((e) => (e.readings || {}).available);
      const fig = (r, k) => (r.available && isNum(r[k]) ? `${num(r[k], 2)}${r.unit || ''}` : '');
      let day = '';
      return html`${impSeg(P)}<table class="ws-t"><caption class="sr">Economic calendar</caption><thead><tr><th scope="col">Time (ET)</th><th scope="col">Release</th><th scope="col">Impact</th>${withFig ? html`<th scope="col" class="n">Actual</th><th scope="col" class="n">Prior</th>` : ''}</tr></thead><tbody>
        ${ev.map((e) => { const head = e.when_label !== day ? (day = e.when_label, html`<tr class="ws-day"><th scope="rowgroup" colspan="${withFig ? 5 : 3}">${e.when_label}</th></tr>`) : ''; const r = e.readings || {};
          return html`${head}<tr><td class="ws-time">${e.all_day ? 'All day' : e.time_label || ''}</td><td>${e.title}${e.released ? html` <span class="ws-flag">Released</span>` : ''}<span class="ws-rule">${e.agency_short || e.agency || ''}</span></td><td><span class="ws-imp" data-imp="${e.impact}">${capitalize(e.impact || 'low')}</span></td>${withFig ? html`<td class="n">${r.available ? (r.is_upcoming || !isNum(r.actual) ? html`<span class="ws-rule">pending</span>` : fig(r, 'actual')) : ''}</td><td class="n">${fig(r, 'previous')}</td>` : ''}</tr>`; })}</tbody></table>`;
    },
    foot: (d) => ({ source: 'Agency schedules (BLS, BEA, Fed, Census), via Optic\'s Read', at: (d || {}).built_at, note: (d || {}).stale ? 'From the last built Read.' : '', gap: 'Actual and prior come from FRED where Optic maps the release to a series. Consensus forecasts are licensed and not in Optic.' }),
    milo: 'Which scheduled releases this week matter most for stocks, and why?',
  },
  earnings: {
    title: 'Earnings this week', span: 8, state: { offset: 0, im: {} },
    how: 'Who reports, by day, with the analysts\' EPS and revenue consensus. The implied move is what the company\'s options price through the report; it is fetched on request because each one reads a full option chain. Choose a ticker to link it.',
    load: (link, P) => get(`/api/earnings-week?offset=${P.offset}&quick=true`, { ttl: 600000, timeout: 90000 }),
    body: (d, P) => {
      const tabs = html`<div class="seg ws-seg" role="group" aria-label="Week">${[[0, 'This week'], [1, 'Next week']].map(([k, l]) => html`<button type="button" data-ws-set="earnings:offset:${k}" aria-pressed="${P.offset === k}">${l}</button>`)}</div>`;
      if (!d || d.available === false) return html`${tabs}<p class="ws-note">${(d && d.reason) || 'The earnings calendar is not available right now.'}</p>`;
      const rows = (d.days || []).flatMap((day) => (day.rows || []).map((r) => Object.assign({ day: `${day.short} ${day.day_number}`, past: day.is_past }, r)));
      if (!rows.length) return html`${tabs}<p class="ws-note">No reports found for ${d.week_label || 'this week'} among the ${d.checked || ''} companies checked.</p>`;
      // the week is Monday to Friday of the calendar week, so on a weekend "this week" has already reported
      const done = P.offset === 0 && rows.every((r) => r.past);
      return html`${tabs}${done ? html`<p class="ws-note">Every report in ${d.week_label || 'this week'} is out. The coming week is under Next week.</p>` : ''}<table class="ws-t"><caption class="sr">Earnings, ${d.week_label}</caption><thead><tr><th scope="col">Day</th><th scope="col">Company</th><th scope="col" class="n">EPS est.</th><th scope="col" class="n ws-sec">Revenue est.</th><th scope="col" class="n">Implied move</th></tr></thead><tbody>
        ${rows.map((r) => { const im = P.im[r.ticker];
          return html`<tr class="${r.past ? 'ws-past' : ''}"><td class="ws-time">${r.day}</td><td>${tickBtn(r.ticker)} <span class="ws-name">${r.name || ''}</span>${r.confirmed ? '' : html` <span class="ws-flag">Unconfirmed</span>`}</td><td class="n">${isNum(r.eps_consensus) ? num(r.eps_consensus) : ''}</td><td class="n ws-sec">${isNum(r.revenue_consensus) ? compact(r.revenue_consensus) : ''}</td>
            <td class="n">${r.past ? html`<span class="ws-rule">Reported</span>` : im === undefined ? html`<button type="button" class="textlink" data-ws-im="${r.ticker}" aria-label="Load the implied move for ${r.ticker}">Load</button>` : im === 'loading' ? 'Reading the chain...' : im && isNum(im.pct) ? html`±${num(im.pct)}%<span class="ws-rule">to ${shortDate(im.expiry)}</span>` : html`<span class="ws-rule">${(im && im.reason) || 'Not available'}</span>`}</td></tr>`; })}</tbody></table>`;
    },
    foot: (d) => ({ source: 'Company calendars and consensus via Yahoo Finance', at: (d || {}).generated_at, note: d && d.checked ? `${d.checked} companies checked${d.failed ? `, ${d.failed} could not be read` : ''}.` : '' }),
    milo: 'Which of this week\'s earnings reports matter most, and what do their options price?',
  },
  movers: {
    title: 'Moved most this month', span: 4,
    how: 'The liquid U.S. stocks with the largest one-month moves, from Optic\'s nightly universe scan. Volume against normal shows whether the move came with participation.',
    load: () => get('/api/scanners/movers', { ttl: 300000 }),
    body: (d) => {
      if (!d || d.available === false) return html`<p class="ws-note">${(d && (d.reason || (d.building && `Building the universe ranking: ${d.building.done} of ${d.building.total}.`))) || 'The movers scan is not available right now.'}</p>`;
      return html`<table class="ws-t"><caption class="sr">Moved most this month</caption><thead><tr><th scope="col">Ticker</th><th scope="col" class="n">1 month</th><th scope="col" class="n ws-sec">Volume</th></tr></thead><tbody>
        ${(d.rows || []).slice(0, 12).map((r) => html`<tr><td>${tickBtn(r.symbol)}</td><td class="n ${dir(r.roc20)}">${pct(r.roc20, 1)}</td><td class="n ws-sec">${isNum(r.volume_expansion) ? `${num(r.volume_expansion, 2)}×` : ''}</td></tr>`)}</tbody></table>`;
    },
    foot: (d) => ({ source: 'Optic universe scan', status: d && isNum(d.age_hours) ? `Scan ${num(d.age_hours, 0)} h old` : '', note: d && isNum(d.age_hours) ? `Scan is ${num(d.age_hours, 0)} hours old${d.stale ? ', older than usual' : ''}.` : '', stale: d && d.stale ? 'Stale scan' : '' }),
    milo: 'What do this month\'s biggest movers have in common?',
  },
  watch: {
    title: 'Watchlist', span: 4,
    how: 'Your open watchlist, with the day\'s move and what changed. Choose a ticker to link it to the chart, news and options panels.',
    load: async () => { const syms = (store.activeList() || {}).symbols || []; if (!syms.length) return { empty: true }; return get(`/api/watchlist?symbols=${enc(syms.slice(0, 30).join(','))}`, { ttl: 30000 }); },
    body: (d) => {
      if (d.empty) return html`<p class="ws-note">Your open watchlist is empty. Follow a company from its Dossier, or <a href="#/watchlist">open Watchlist</a>.</p>`;
      return html`<table class="ws-t"><caption class="sr">Watchlist</caption><thead><tr><th scope="col">Ticker</th><th scope="col" class="n">Price</th><th scope="col" class="n">Day</th><th scope="col" class="ws-sec">Changed</th></tr></thead><tbody>
        ${(d.rows || []).map((r) => html`<tr><td>${tickBtn(r.symbol)}</td><td class="n">${r.available === false ? '' : num(r.price)}</td><td class="n ${dir(r.change_pct)}">${r.available === false ? 'n/a' : pct(r.change_pct)}</td><td class="ws-rule ws-sec">${((r.changed || {}).text) || ''}</td></tr>`)}</tbody></table>`;
    },
    foot: () => ({ source: 'Your open list; prices from Yahoo Finance' }),
    milo: 'Summarise what changed across my watchlist today.',
  },
  quote: {
    title: 'Quote and chart', span: 8, linked: true, state: { span: '6m' },
    how: 'The linked ticker\'s price and daily closes, with the nearest support and resistance Optic computes from swing points. Change the linked ticker from any list, or type one in the bar above.',
    load: async (link, P) => { const [q, c] = await Promise.all([get(`/api/quote/${enc(link)}`, { ttl: 20000 }), get(`/api/take-chart/${enc(link)}?span=${P.span}`, { ttl: 600000 })]); return { q, c }; },
    body: ({ q, c }, P, link) => {
      const qq = (q || {}).quote || {};
      if (!q || q.available === false || !isNum(qq.price)) return html`<p class="ws-note">No quote for ${link}. Check the ticker.</p>`;
      return html`<div class="ws-quote"><div><a class="ws-sym" href="#/${enc(link)}">${link}</a> <span class="ws-name">${qq.name || ''}</span></div><div class="ws-px">${num(qq.price)} <span class="${dir(qq.change_pct)}">${signed(qq.change, 2, '')} (${signed(qq.change_pct)})</span></div></div>
        <div class="seg ws-seg" role="group" aria-label="Range">${['3m', '6m', '1y'].map((k) => html`<button type="button" data-ws-set="quote:span:${k}" aria-pressed="${P.span === k}">${k.toUpperCase()}</button>`)}</div>
        ${(c && c.available && ((c.chart || {}).close || []).length > 1) ? html`<div class="chart-slot" data-chart="ws-quote"></div>` : html`<p class="ws-note">No price history for ${link}.</p>`}`;
    },
    charts: ({ c }) => ({ 'ws-quote': (w) => {
      const ch = (c || {}).chart || {}; const dates = ch.dates || [];
      const levels = [...(c.supports || []).slice(0, 2), ...(c.resistances || []).slice(0, 1)].map((l) => l.price).filter(Number.isFinite);
      return lineChart(dates.map((d, i) => ({ d, c: ch.close[i] })), { w, h: chartH('quote'), label: `${c.ticker} daily closes`, overlays: levels.map((v) => ({ values: dates.map(() => v), cls: 'c0' })), summary: `${c.ticker} daily closes over ${c.span_words || ''}; dashed lines are support and resistance.` });
    } }),
    foot: ({ q, c }) => ({ source: 'Yahoo Finance; levels by Optic', at: (c || {}).as_of }),
    milo: (link) => `Read the ${link} chart on my Home: trend, levels and what would change the picture.`,
  },
  cnews: {
    title: 'Company news', span: 6, linked: true,
    how: 'Headlines about the linked ticker, newest first, with their publisher and age. Optic sorts headlines that are about the company from ones that only mention it.',
    load: (link) => get(`/api/news/${enc(link)}`, { ttl: 300000 }),
    body: (d, P, link) => {
      const arts = ((d || {}).articles || []).slice(0, 12);
      if (!arts.length) return html`<p class="ws-note">No recent headlines for ${link}.</p>`;
      return html`${d.earnings_warning ? html`<p class="ws-callout">${clean(d.earnings_warning)}</p>` : ''}<ul class="ws-news">${arts.map((a) => html`<li><a href="${a.url}" target="_blank" rel="noopener noreferrer">${a.title}</a><span class="ws-rule">${a.publisher || ''}${isNum(a.age_hours) ? `, ${a.age_hours < 1 ? 'under an hour' : `${num(a.age_hours, 0)} h`} ago` : ''}</span></li>`)}</ul>`;
    },
    foot: () => ({ source: 'Yahoo Finance and publisher feeds' }),
    milo: (link) => `What in the recent ${link} news actually matters for the stock?`,
  },
  news: {
    title: 'Market news', span: 6,
    how: 'The day\'s wire headlines Optic collected for its Read, with the publisher. Nothing here is written by a model.',
    load: () => get('/api/brief?cached=true', { ttl: 120000 }),
    body: (d) => {
      const w = (d || {}).wires || {}, seen = new Set();
      const items = [w.lead, ...(w.desks || []).flatMap((k) => k.entries || [])].filter((x) => x && x.title && !seen.has(x.url) && seen.add(x.url))
        .sort((a, b) => String(b.published || '').localeCompare(String(a.published || ''))).slice(0, 14);
      if (!items.length) return html`<p class="ws-note">No wire headlines in the last built Read.</p>`;
      return html`<ul class="ws-news">${items.map((a) => html`<li><a href="${a.url}" target="_blank" rel="noopener noreferrer">${a.title}</a><span class="ws-rule">${a.source || ''}${a.published ? `, ${ago(a.published)}` : ''}${(a.tone_terms || []).length ? `, ${a.tone_label === 'positive' ? 'leans positive' : a.tone_label === 'negative' ? 'leans negative' : 'mixed'}` : ''}</span></li>`)}</ul>`;
    },
    foot: (d) => ({ source: 'Public wire feeds via Optic\'s Read', at: (d || {}).built_at }),
    milo: 'What are the market-moving headlines today?',
  },
  economy: {
    title: 'Economy', span: 12, state: { group: 'all', code: null },
    how: 'U.S. indicators from FRED with their latest reading, the change from the one before, and their history. Inflation series are shown year over year, as quoted in the news. Choose an indicator to see its chart and what it measures.',
    load: async (link, P) => {
      const g = await get('/api/econ', { ttl: 3600000 });
      const series = (g.groups || []).flatMap((gr) => gr.series.map((x) => Object.assign({ group: gr.id, groupLabel: gr.label }, x)));
      const got = await Promise.all(series.map((x) => get(`/api/econ/${enc(x.code)}`, { ttl: 3600000, timeout: 30000 }).then((d) => Object.assign({}, x, { d }), () => Object.assign({}, x, { d: null }))));
      if (!P.code && got.length) P.code = got[0].code;
      return { groups: g.groups || [], series: got };
    },
    body: ({ groups, series }, P) => {
      const list = series.filter((x) => P.group === 'all' || x.group === P.group);
      const sel = series.find((x) => x.code === P.code) || list[0];
      const d = (sel || {}).d || {};
      return html`<div class="seg ws-seg" role="group" aria-label="Indicator group">${[['all', 'All'], ...groups.map((g) => [g.id, g.label])].map(([k, l]) => html`<button type="button" data-ws-set="economy:group:${k}" aria-pressed="${P.group === k}">${l}</button>`)}</div>
        <div class="ws-econ"><ul class="ws-elist">${list.map((x) => { const v = (x.d || {}).latest || {};
          return html`<li><button type="button" data-ws-set="economy:code:${x.code}" aria-pressed="${sel && sel.code === x.code}"><span class="ws-ename">${x.label}</span><span class="ws-eval">${econVal(v.value, x.unit, x.code)}</span><span class="ws-rule">${v.date ? shortDate(v.date) : ''}${x.d && isNum(x.d.change) ? `, ${econChg(x.d.change, x.unit, x.code)}` : ''}</span>${raw(spark((x.d || {}).values ? x.d.values.slice(-36) : []))}</button></li>`; })}</ul>
        <div class="ws-edetail">${sel && sel.d ? html`<p class="ws-k">${sel.groupLabel}</p><p class="ws-big">${sel.label} <span class="ws-word">${econVal((d.latest || {}).value, sel.unit, sel.code)}</span></p><p class="ws-sub">${d.form_label || ''}; latest ${shortDate((d.latest || {}).date)}, previous ${econVal((d.previous || {}).value, sel.unit, sel.code)}; high ${econVal(d.max, sel.unit, sel.code)}, low ${econVal(d.min, sel.unit, sel.code)} over ${d.points} readings</p>
          <div class="chart-slot" data-chart="ws-econ"></div><p class="ws-read">${clean(d.note || '')}</p>` : html`<p class="ws-note">That series did not come back from FRED.</p>`}</div></div>`;
    },
    charts: ({ series }, P) => ({ 'ws-econ': (w) => { const s = series.find((x) => x.code === P.code) || series[0]; const d = (s || {}).d || {}; return lineChart((d.values || []).map((v, i) => ({ d: d.dates[i], c: v })), { w, h: chartH('economy'), years: (d.values || []).length > 36, label: `${s.label} history`, summary: `${s.label}, ${d.form_label || ''}, ${d.points} readings` }); } }),
    foot: () => ({ source: 'FRED, St. Louis Fed' }),
    milo: 'Which of these economic indicators matter most for stocks right now?',
  },
  contracts: {
    title: 'Contracts', span: 12, linked: true, state: { side: 'call', expiry: '', sort: { key: 'strike', dir: 'asc' } },
    how: 'Option contracts for the linked ticker at one expiry, nearest the money first: what each costs to own, the spread you pay to get in and out, delta (how much the option moves per $1 in the stock) and open interest. Sort by any column. Optic\'s liquidity label judges how tradeable a contract is, not whether the trade will work; there is no grade or pick.',
    load: (link, P) => get(`/api/options/${enc(link)}/research?side=${P.side}&delta_lo=0.15&delta_hi=0.85${P.expiry ? `&expiry=${P.expiry}` : ''}`, { ttl: 60000, timeout: 60000 }),
    body: (d, P, link) => {
      if (!d || !d.table) return html`<p class="ws-note">${(d && (d.reason || d.detail)) || `No option chain for ${link}.`}</p>`;
      // the 14 nearest the money (delta's size nearest 0.5; a put's delta is negative), then in the order the reader chose
      const atm = (r) => Math.abs(Math.abs(r.delta || 0) - 0.5);
      const near = (d.table.rows || []).slice().sort((a, b) => atm(a) - atm(b)).slice(0, 14);
      const col = CONTRACT_COLS.find((c) => c.key === P.sort.key) || CONTRACT_COLS[0];
      const rows = near.sort((a, b) => { const x = col.v(a), y = col.v(b); if (!isNum(x) || !isNum(y)) return isNum(x) ? -1 : isNum(y) ? 1 : 0; return (x - y) * (P.sort.dir === 'asc' ? 1 : -1); });
      const sm = d.summary || {};
      return html`<div class="ws-toolrow"><div class="seg ws-seg" role="group" aria-label="Side">${[['call', 'Calls'], ['put', 'Puts']].map(([k, l]) => html`<button type="button" data-ws-set="contracts:side:${k}" aria-pressed="${P.side === k}">${l}</button>`)}</div>
          <label class="ws-sel">Expiry <select data-ws-expiry>${(d.listed_expiries || []).slice(0, 14).map((e) => html`<option value="${e.expiry}" ${e.expiry === d.expiry ? 'selected' : ''}>${shortDate(e.expiry)} (${e.dte}d${e.monthly ? ', monthly' : ''})</option>`)}</select></label>
          <span class="ws-rule">ATM IV ${num(sm.atm_iv_pct, 1)}%, straddle prices ±${num(sm.straddle_move_pct, 1)}% to expiry</span></div>
        <table class="ws-t"><caption class="sr">${link} ${P.side}s, ${d.expiry}, sorted by ${col.label}</caption><thead><tr>${CONTRACT_COLS.map((c) => { const on = c.key === P.sort.key;
          return html`<th scope="col" class="${c.num ? 'n' : ''} ${c.sec ? 'ws-sec' : ''}" aria-sort="${on ? (P.sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}"><button type="button" class="th-sort" data-ws-sort="${c.key}">${c.label}${on ? icon(P.sort.dir === 'asc' ? 'up' : 'down') : ''}</button></th>`; })}<th scope="col" class="ws-rowcol"><span class="sr">Details</span></th></tr></thead><tbody>
          ${rows.map((r, i) => html`<tr>${CONTRACT_COLS.map((c) => html`<td class="${c.num ? 'n' : ''} ${c.sec ? 'ws-sec' : ''}">${c.cell(r)}</td>`)}<td class="ws-rowcol"><button type="button" class="ws-rowbtn" data-ws-row="ctr-${i}" aria-expanded="false" aria-controls="ctr-${i}" aria-label="Every figure for the ${num(r.strike)} ${P.side}">${icon('chev')}</button></td></tr>
            <tr class="ws-rowd" id="ctr-${i}" hidden><td colspan="${CONTRACT_COLS.length + 1}"><dl>${CONTRACT_COLS.filter((c) => c.sec).map((c) => html`<div><dt>${c.label}</dt><dd>${c.cell(r)}</dd></div>`)}</dl></td></tr>`)}</tbody></table>`;
    },
    foot: (d) => ({ source: 'Option chain from Yahoo Finance; greeks computed by Optic', at: (d || {}).fetched_at, note: 'Mid is between bid and ask; you usually pay more.' }),
    milo: (link) => `Compare the ${link} contracts on my Home for tradeability: spread, liquidity, delta and expiry fit.`,
  },
  value: {
    title: 'Fair value', span: 6, linked: true,
    how: 'An estimated fair value range for the linked ticker from its own earnings history: trailing earnings at the low, middle and high of its own five-year P/E range. It says where the price sits against that history, not where it is going.',
    load: (link) => get(`/api/fair-value/${enc(link)}`, { ttl: 600000 }),
    body: (d, P, link) => {
      const f = (d || {}).fair_value || {};
      if (!f.available) return html`<p class="ws-note">${clean(f.reason || `No fair value range for ${link}: it needs positive earnings and enough price history.`)}</p>`;
      return html`<div class="ws-meter">${raw(meter({ lo: f.low, mid: f.mid, hi: f.high, price: f.price, w: 320, showMid: true }))}</div><p class="ws-read">${link} trades at ${num(f.price)}, ${f.position}. ${clean(f.basis || '')}</p>`;
    },
    foot: (d) => ({ source: 'Optic fair-value method on Yahoo Finance and SEC data', at: (d || {}).generated_at }),
    milo: (link) => `How does ${link}'s price compare with its own valuation history, and what would justify the gap?`,
  },
};
const capitalize = (s) => (s ? String(s).charAt(0).toUpperCase() + String(s).slice(1) : s);
const impSeg = (P) => html`<div class="seg ws-seg" role="group" aria-label="Impact">${[['all', 'All'], ['high', 'Medium and high']].map(([k, l]) => html`<button type="button" data-ws-set="calendar:imp:${k}" aria-pressed="${P.imp === k}">${l}</button>`)}</div>`;

/* ---------------- rendering ---------------- */
let root = null, live = false, timer = null, lastScroll = 0, mq = null, mq2 = null;
// DLINK: the ticker a linked panel's data was fetched for. A panel never paints data for another ticker
// under the current link (owner, 2026-10-19: Quote and chart showed SPY's name and price under AAPL).
const DATA = {}, ERR = {}, PS = {}, AT = {}, RETRIED = {}, DLINK = {}, ERRLINK = {};
const ps = (id) => (PS[id] || (PS[id] = JSON.parse(JSON.stringify(PANELS[id].state || {}))));
const NEW = { starters: undefined, modes: undefined };
const isNew = () => !store.allSymbols().length && !(DATA.portfolio && !DATA.portfolio.absent);

function bar() {
  const hidden = layout().filter((x) => x.hidden && !(PANELS[x.id].optional && (DATA[x.id] || {}).absent));
  return html`<div class="ws-bar" role="toolbar" aria-label="Layout">
    <div class="ws-presets" role="tablist" aria-label="Layout">${Object.entries(PRESETS).map(([k, p]) => html`<button type="button" role="tab" aria-selected="${S.preset === k}" data-ws-preset="${k}">${p.label}</button>`)}</div>
    <form class="ws-linkform" data-ws-linkform><label for="ws-link">Linked ticker</label><input id="ws-link" name="link" value="${S.link}" autocomplete="off" spellcheck="false" maxlength="12" aria-describedby="ws-link-help"><button type="submit" class="btn btn-sm">Link</button><span id="ws-link-help" class="sr">Panels marked with the ticker follow it</span></form>
    <span class="spacer"></span>
    <div class="ws-tools">
      <details class="ws-add"><summary class="btn btn-sm">Add panel${hidden.length ? ` (${hidden.length})` : ''}</summary><div class="ws-menu-body">${hidden.length ? hidden.map((x) => html`<button type="button" data-ws-show="${x.id}">${PANELS[x.id].title}</button>`) : html`<p class="ws-rule">Every panel is showing.</p>`}</div></details>
      <button type="button" class="btn btn-sm" data-ws-lock aria-pressed="${!!S.locked}">${S.locked ? 'Unlock layout' : 'Lock layout'}</button>
      <button type="button" class="btn btn-sm" data-ws-reset>Reset</button>
      ${S.preset === 'mine' ? '' : html`<button type="button" class="btn btn-sm" data-ws-save>Save as My Desk</button>`}
    </div>
    <details class="ws-menu ws-toolmenu"><summary class="btn btn-sm">Layout options</summary><div class="ws-menu-body">
      ${hidden.map((x) => html`<button type="button" data-ws-show="${x.id}">Add ${PANELS[x.id].title}</button>`)}
      <button type="button" data-ws-reset>Reset this layout</button>
      ${S.preset === 'mine' ? '' : html`<button type="button" data-ws-save>Save as My Desk</button>`}</div></details>
  </div>
  <p class="ws-live sr" role="status" aria-live="polite" id="ws-live"></p>`;
}

function panelShell(x, i, n) {
  const p = PANELS[x.id], locked = !!S.locked, link = S.link, fold = folded(x.id), P = ps(x.id);
  const ask = typeof p.milo === 'function' ? p.milo(link) : p.milo;
  const hasTable = !!CONTRACT_COLS && ['watch', 'earnings', 'movers', 'contracts'].includes(x.id);
  return html`<section class="ws-panel ${P.allCols ? 'all-cols' : ''}" data-ws-panel="${x.id}" data-h="${x.h}" data-kind="${LIST.has(x.id) ? 'list' : 'fit'}" style="--span:${x.span}" aria-labelledby="wsh-${x.id}" ${p.optional && (DATA[x.id] || {}).absent ? 'hidden' : ''}>
    <header class="ws-head">
      ${locked ? '' : html`<button type="button" class="ws-grip" data-ws-grip="${x.id}" aria-label="Move ${p.title}: arrow keys move it earlier or later">⠿</button>`}
      <h2 class="ws-title" id="wsh-${x.id}"><span class="ws-tt">${p.title}</span><button type="button" class="ws-tbtn" data-ws-fold="${x.id}" aria-expanded="${!fold}" aria-controls="wsb-${x.id}"><span>${p.title}</span>${icon('chev')}</button></h2>
      ${p.linked ? html`<span class="ws-linkchip" title="Follows the linked ticker">${link}</span>` : ''}
      <span class="spacer"></span>
      <button type="button" class="ws-ibtn ws-howbtn" data-ws-how="${x.id}" aria-expanded="false" aria-controls="wsw-${x.id}" aria-label="About ${p.title}: how to read it, its source and how fresh it is" title="About this panel">?</button>
      <button type="button" class="btn btn-milo btn-sm ws-ask" data-v2-milo="${ask}" data-v2-milo-ctx="Home: ${p.title}" data-v2-milo-sym="${p.linked ? link : ''}" aria-label="Ask Milo about ${p.title}">${icon('milo')}<span class="ws-ask-t">Ask Milo</span></button>
      <details class="ws-menu"><summary class="ws-hbtn" aria-label="${p.title} options">⋯</summary><div class="ws-menu-body">
        <button type="button" class="ws-phone-only" data-ws-how="${x.id}" aria-controls="wsw-${x.id}">About this panel</button>
        <button type="button" class="ws-phone-only ws-menu-milo" data-v2-milo="${ask}" data-v2-milo-ctx="Home: ${p.title}" data-v2-milo-sym="${p.linked ? link : ''}">${icon('milo')}Ask Milo about this</button>
        ${locked ? html`<p class="ws-rule">The layout is locked.</p>` : html`
        <button type="button" data-ws-move="${x.id}:-1" ${i === 0 ? 'disabled' : ''}>Move earlier</button><button type="button" data-ws-move="${x.id}:1" ${i === n - 1 ? 'disabled' : ''}>Move later</button>
        <button type="button" class="ws-wide-only" data-ws-span="${x.id}:-1" ${x.span <= SPANS[0] ? 'disabled' : ''}>Narrower</button><button type="button" class="ws-wide-only" data-ws-span="${x.id}:1" ${x.span >= 12 ? 'disabled' : ''}>Wider</button>
        <button type="button" data-ws-h="${x.id}:-1" ${x.h === 's' ? 'disabled' : ''}>Shorter</button><button type="button" data-ws-h="${x.id}:1" ${x.h === 'l' ? 'disabled' : ''}>Taller</button>
        <button type="button" class="ws-wide-only" data-ws-full="${x.id}">${x.span === 12 ? 'Back to its width' : 'Full width'}</button>
        <button type="button" data-ws-hide="${x.id}">Hide panel</button>`}
        ${hasTable ? html`<button type="button" class="ws-phone-only" data-ws-cols="${x.id}">${P.allCols ? 'Fewer columns' : 'All columns'}</button>` : ''}
        <button type="button" data-ws-reload="${x.id}">Refresh</button></div></details>
    </header>
    <div class="ws-how" id="wsw-${x.id}" hidden><p>${p.how}</p><dl class="ws-srcd" id="wsd-${x.id}"></dl></div>
    <p class="ws-blurb" ${fold ? '' : 'hidden'}>${BLURB[x.id] || ''}</p>
    <div class="ws-body" id="wsb-${x.id}" tabindex="-1" ${fold ? 'hidden' : ''}>${skeleton(x.id === 'indices' ? 'lines' : 'rows', x.id === 'indices' ? 2 : 4, `Loading ${p.title}`)}</div>
    <footer class="ws-foot" id="wsf-${x.id}" ${fold ? 'hidden' : ''}></footer>
    ${locked ? '' : html`<span class="ws-resize" data-ws-resize="${x.id}" aria-hidden="true" title="Drag to resize"></span>`}
  </section>`;
}

// Home's first visit: the welcome, a few names to follow, and how Optic should speak (pages/home.js)
function newBand() {
  return html`<div class="ws-new" id="ws-new">
    <div id="ws-welcome">${DATA.indices ? welcome(DATA.indices) : skeleton('chart', 1, 'Loading')}</div>
    <section class="ws-panel ws-newpanel" aria-labelledby="st-h"><header class="ws-head"><h2 class="ws-title" id="st-h">Follow a few names to start</h2></header>
      <div class="ws-body"><p class="ws-sub">${store.signedIn() ? 'They go into your account\'s watchlist.' : 'Kept in this browser. Sign in to keep them on your account.'} Home fills in around what you follow.</p><div id="ws-starters">${NEW.starters ? starters(NEW.starters) : skeleton('rows', 2)}</div></div></section>
    ${NEW.modes && NEW.modes.length ? html`<section class="ws-panel ws-newpanel" id="ws-modes" aria-labelledby="md-h"><header class="ws-head"><h2 class="ws-title" id="md-h">How should Optic speak to you?</h2></header><div class="ws-body"><p class="ws-sub">Change it any time in Settings.</p>${modes(NEW.modes)}</div></section>` : ''}
  </div>`;
}

// A row the next panel cannot join ends early; its last panel widens to the end of the row so the
// grid has no hole (for example when Your portfolio is absent). The saved spans are unchanged.
function fillRows() {
  const grid = $('.ws-grid', root); if (!grid) return;
  const ps2 = $$('.ws-grid > .ws-panel', root).filter((x) => !x.hidden);
  ps2.forEach((x) => x.style.removeProperty('grid-column'));
  const wide = window.innerWidth > 1100; if (window.innerWidth <= 860) return;
  const eff = (x) => { const sp = Number(x.style.getPropertyValue('--span')) || 6; return wide ? sp : (sp >= 8 ? 12 : 6); };
  let used = 0, prev = null;
  ps2.forEach((x) => { const w = eff(x); if (used + w > 12) { if (prev && used < 12) prev.style.gridColumn = `span ${12 - used + eff(prev)}`; used = 0; } used += w; prev = x; });
  if (prev && used < 12) prev.style.gridColumn = `span ${12 - used + eff(prev)}`;
}

function paintAll() {
  const shown = layout().filter((x) => !x.hidden);
  const ses = ((DATA.indices || {}).session) || {};
  draw(root, html`<div class="ws-page">
    <header class="ws-pagehead"><div><h1 class="t-h2" tabindex="-1">${hello()}</h1><p class="ws-sub" id="ws-date">${etDate(ses.now_et)}${ses.label ? `. ${clean(ses.label)}.` : ''}</p></div>
      <p class="ws-sub ws-about">Connected to Optic's existing data sources. Each panel says where its figures come from and how fresh they are. Your layout is kept in this browser.</p></header>
    ${isNew() ? newBand() : ''}
    ${bar()}
    <div class="ws-grid ${S.locked ? 'is-locked' : ''}">${shown.length ? shown.map((x, i) => panelShell(x, i, shown.length)) : html`<p class="ws-note">Every panel is hidden. Use Add panel, or Reset.</p>`}</div></div>`);
  if (isNew()) { wireForms(root); loadNew(); }
  shown.forEach((x) => { if (DATA[x.id] !== undefined || ERR[x.id]) paintBody(x.id); if (!folded(x.id)) loadPanel(x.id, { quiet: DATA[x.id] !== undefined }); });
  fillRows();
  provideContext(miloContext);
}

async function loadNew() {
  if (NEW.starters === undefined) {
    NEW.starters = null;
    get(`/api/watchlist?symbols=${STARTERS.join(',')}`, { ttl: 60000 }).then((r) => { NEW.starters = r.rows || []; }, () => { NEW.starters = []; }).then(() => { const h = $('#ws-starters', root); if (h && live) draw(h, starters(NEW.starters)); });
  }
  if (NEW.modes === undefined) {
    NEW.modes = null;
    let asked = null; try { asked = localStorage.getItem('optic.knowledge.asked.v1'); } catch (e) { /* private */ }
    if (!asked) get('/api/knowledge/modes', { ttl: 3600000 }).then((r) => { NEW.modes = r.modes || []; if (live && isNew() && NEW.modes.length) paintAll(); }, () => {});
  }
  if (!NEW.scene) {
    NEW.scene = true;
    get('/api/instrument?symbol=%5EGSPC&range=6mo', { ttl: 300000, timeout: 15000 }).then((r) => {
      setScene((r.dates || []).map((dd, i) => ({ d: String(dd).slice(0, 10), c: Number(r.close[i]) })).filter((q) => isNum(q.c)));
      const w = $('#ws-welcome', root); if (w && live && DATA.indices) { draw(w, welcome(DATA.indices)); wireForms(root); }
    }, () => {});
  }
}

function paintBody(id) {
  const sec = $(`[data-ws-panel="${id}"]`, root), body = $(`#wsb-${id}`, root), foot = $(`#wsf-${id}`, root); if (!body) return;
  const p = PANELS[id], P = ps(id);
  if (p.optional && (DATA[id] || {}).absent) { if (!sec.hidden) { sec.hidden = true; fillRows(); } return; }
  if (sec && sec.hidden) { sec.hidden = false; fillRows(); }
  if (ERR[id]) {
    // a linked panel's 404 means the provider had nothing for this ticker just now, not that the panel is missing
    if (p.linked && ERR[id].kind === 'notfound') draw(body, html`<div class="state err" role="alert"><p class="t-h3">${p.title} did not load</p><p>The data provider returned nothing for ${ERRLINK[id] || S.link} just now. This is usually brief.</p></div>`);
    else draw(body, failed(p.title, ERR[id], {}));
    body.insertAdjacentHTML('beforeend', `<button type="button" class="btn btn-sm" data-ws-reload="${id}">Try again</button>`);
    draw(foot, ''); return;
  }
  const d = DATA[id]; if (d === undefined) return;
  if (p.linked && DLINK[id] !== S.link) { draw(body, skeleton('rows', 4, `Loading ${p.title} for ${S.link}`)); draw(foot, ''); return; }
  const forLink = p.linked ? DLINK[id] : S.link;
  draw(body, p.body(d, P, forLink));
  if (p.charts) mountCharts(body, p.charts(d, P, forLink));
  const f = p.foot ? p.foot(d, P) : {};
  const old = f.at && CADENCE_MS[id] && Date.now() - Date.parse(f.at) > 3 * CADENCE_MS[id] ? `Built ${ago(f.at)}` : '';
  const st = d && d.building ? 'Building' : d && d.served_stale ? 'Updating' : old ? '' : (f.status || statusOf(id));
  draw(foot, html`<span class="ws-src">${SRC[id] || f.source || ''}</span>${f.at ? html`<span>${asof(f.at)}</span>` : ''}${st ? html`<span class="ws-state">${st}</span>` : ''}${old ? html`<span class="ws-stale">${old}</span>` : ''}${f.stale ? html`<span class="ws-stale">${f.stale}</span>` : ''}`);
  const dl = $(`#wsd-${id}`, root);
  if (dl) draw(dl, html`<div><dt>Source</dt><dd>${f.source || SRC[id] || ''}</dd></div>${FRESH[id] ? html`<div><dt>How fresh</dt><dd class="ws-fresh">${FRESH[id]}</dd></div>` : ''}${f.note || f.staleWhy ? html`<div><dt>Note</dt><dd>${[f.note, f.staleWhy].filter(Boolean).join(' ')}</dd></div>` : ''}${f.gap ? html`<div><dt>Not in Optic</dt><dd>${f.gap}</dd></div>` : ''}`);
  if (id === 'indices') { const dt = $('#ws-date', root), ses = d.session || {}; if (dt) dt.textContent = `${etDate(ses.now_et)}${ses.label ? `. ${clean(ses.label)}.` : ''}`; }
}

async function loadPanel(id, { force = false, quiet = false } = {}) {
  const p = PANELS[id]; const P = ps(id);
  if (folded(id) && !force) return;
  const linkAt = S.link; delete ERR[id]; ERRLINK[id] = linkAt;
  if (force) { DATA[id] = undefined; const b = $(`#wsb-${id}`, root); if (b) draw(b, skeleton('rows', 4, `Loading ${p.title}`)); }
  try {
    const d = await p.load(S.link, P);
    if (!live || (p.linked && linkAt !== S.link)) return;   // the link moved on while this loaded
    const was = DATA[id], wasLink = DLINK[id];
    DATA[id] = d; AT[id] = Date.now(); DLINK[id] = linkAt;
    // a board the server is still building: ask again shortly, quietly, while this panel is on screen
    if (d && d.building) setTimeout(() => { if (live && DATA[id] === d && !folded(id)) loadPanel(id, { quiet: true }); }, 12000);
    // a quiet refresh that changed nothing repaints nothing, so a reader mid-scroll keeps their place
    if (quiet && was !== undefined && wasLink === linkAt && JSON.stringify(was) === JSON.stringify(d)) return;
  } catch (e) {
    if (!live || (p.linked && linkAt !== S.link)) return;   // an error for a ticker no longer linked
    if (quiet && DATA[id] !== undefined) return; ERR[id] = e; DATA[id] = undefined;
    // the provider sometimes has nothing for a ticker for a moment: one quiet retry before the reader has to
    if (p.linked && e.kind === 'notfound' && !RETRIED[id]) { RETRIED[id] = true; setTimeout(() => { if (live && ERR[id] === e) loadPanel(id, { force: true }); }, 5000); }
  }
  if (!ERR[id]) delete RETRIED[id];
  paintBody(id);
  if (id === 'portfolio' && isNew() !== !!$('#ws-new', root)) paintAll();   // a linked portfolio makes this a returning reader's Home
  if (id === 'indices' && isNew()) { const w = $('#ws-welcome', root); if (w && !w.querySelector('form')) { draw(w, welcome(DATA.indices)); wireForms(root); } }
}

/* ---------------- linking ---------------- */
function setLink(sym) {
  sym = String(sym || '').trim().toUpperCase().replace(/^\$/, '');
  if (!/^[A-Z0-9.^=-]{1,12}$/.test(sym) || sym === S.link) return;
  S.link = sym; save();
  try { store.pushRecent(sym); } catch (e) { /* recent is a convenience */ }
  $$('[data-ws-pick]', root).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.wsPick === sym)));
  $$('.ws-linkchip', root).forEach((c) => { c.textContent = sym; });
  const inp = $('#ws-link', root); if (inp) inp.value = sym;
  layout().filter((x) => !x.hidden && PANELS[x.id].linked).forEach((x) => {
    const a = $(`[data-ws-panel="${x.id}"] .ws-ask`, root), p = PANELS[x.id];
    if (a) { a.dataset.v2MiloSym = sym; if (typeof p.milo === 'function') a.dataset.v2Milo = p.milo(sym); }
    if (folded(x.id)) { DATA[x.id] = undefined; return; }   // a folded panel loads the new ticker when opened
    loadPanel(x.id, { force: true });
  });
  say(`Linked panels now follow ${sym}.`);
  provideContext(miloContext);
}
const say = (t) => { const l = $('#ws-live', root); if (l) l.textContent = t; };

/* ---------------- layout changes ---------------- */
function mutate(fn, msg) { fn(layout()); save(); paintAll(); if (msg) say(msg); }
function move(id, delta) {
  mutate((L) => {
    const shown = L.filter((x) => !x.hidden); const i = shown.findIndex((x) => x.id === id), j = i + delta;
    if (i < 0 || j < 0 || j >= shown.length) return;
    const a = L.indexOf(shown[i]), b = L.indexOf(shown[j]); [L[a], L[b]] = [L[b], L[a]];
  }, `${PANELS[id].title} moved ${delta < 0 ? 'earlier' : 'later'}.`);
  const g = $(`[data-ws-grip="${id}"]`, root) || $(`[data-ws-panel="${id}"] .ws-menu summary`, root); if (g) g.focus();
}
function resize(id, delta) {
  mutate((L) => { const x = L.find((y) => y.id === id); const i = SPANS.indexOf(SPANS.reduce((p, c) => (Math.abs(c - x.span) < Math.abs(p - x.span) ? c : p))); x.span = SPANS[Math.max(0, Math.min(SPANS.length - 1, i + delta))]; }, `${PANELS[id].title} is ${layout().find((y) => y.id === id).span} columns wide.`);
}
function setFold(id, on) {
  S.fold[S.preset] = Object.assign({}, S.fold[S.preset], { [id]: on }); save();
  const sec = $(`[data-ws-panel="${id}"]`, root); if (!sec) return;
  const b = $('[data-ws-fold]', sec); b.setAttribute('aria-expanded', String(!on));
  $('.ws-body', sec).hidden = on; $('.ws-foot', sec).hidden = on; $('.ws-blurb', sec).hidden = !on;
  if (!on) { if (DATA[id] === undefined && !ERR[id]) loadPanel(id, { force: true }); else paintBody(id); }
  say(`${PANELS[id].title} ${on ? 'folded' : 'open'}.`);
}

/* ---------------- milo ---------------- */
function miloContext() {
  const home = DATA.indices || DATA.expected || (DATA.regime || {}).h || null;
  const m = (home || {}).macro || {};
  const q = ((DATA.quote || {}).q || {}).quote || null;
  return {
    focus_label: `Home, ${PRESETS[S.preset].label}${S.link ? `, linked to ${S.link}` : ''}`,
    workspace: { layout: PRESETS[S.preset].label, linked_ticker: S.link, panels: layout().filter((x) => !x.hidden).map((x) => PANELS[x.id].title) },
    macro: m.regime ? { regime: m.regime, risk_score: m.risk_score, stance: m.stance, expected_move: m.expected_move } : undefined,
    sentiment: (DATA.regime || {}).s && DATA.regime.s.available !== false ? { score: DATA.regime.s.score, label: DATA.regime.s.label } : undefined,
    linked_quote: q && DLINK.quote === S.link ? { ticker: S.link, price: q.price, change_pct: q.change_pct } : undefined,
    read: home && home.read ? home.read : undefined,
  };
}

/* ---------------- events ---------------- */
function wire() {
  root.addEventListener('click', async (e) => {
    const t = (s2) => e.target.closest(s2); let b;
    if ((b = t('[data-ws-preset]'))) { if (b.dataset.wsPreset === 'mine' && !S.layouts.mine.some((x) => !x.hidden)) S.layouts.mine = JSON.parse(JSON.stringify(S.layouts.market)); S.preset = b.dataset.wsPreset; save(); paintAll(); say(`${PRESETS[S.preset].label} layout.`); return; }
    if ((b = t('[data-ws-pick]'))) { setLink(b.dataset.wsPick); return; }
    if ((b = t('[data-ws-fold]'))) { setFold(b.dataset.wsFold, b.getAttribute('aria-expanded') === 'true'); return; }
    const menu = e.target.closest('.ws-menu-body button'); if (menu) { const dd = menu.closest('details'); if (dd) dd.open = false; }
    if ((b = t('[data-ws-how]'))) { const id = b.dataset.wsHow, w = $(`#wsw-${id}`, root); const open = w.hidden; w.hidden = !open; $$(`[data-ws-how="${id}"]`, root).forEach((x) => x.setAttribute('aria-expanded', String(open))); if (open && menu) w.setAttribute('tabindex', '-1'), w.focus(); return; }
    if ((b = t('[data-ws-row]'))) { const r = document.getElementById(b.getAttribute('aria-controls')); const open = b.getAttribute('aria-expanded') !== 'true'; if (r) r.hidden = !open; b.setAttribute('aria-expanded', String(open)); return; }
    if ((b = t('[data-ws-sort]'))) { const P = ps('contracts'); P.sort = P.sort.key === b.dataset.wsSort ? { key: P.sort.key, dir: P.sort.dir === 'asc' ? 'desc' : 'asc' } : { key: b.dataset.wsSort, dir: 'asc' }; paintBody('contracts'); const again = $(`[data-ws-sort="${P.sort.key}"]`, root); if (again) again.focus(); say(`Contracts sorted by ${(CONTRACT_COLS.find((c) => c.key === P.sort.key) || {}).label}, ${P.sort.dir === 'asc' ? 'lowest' : 'highest'} first.`); return; }
    if ((b = t('[data-ws-cols]'))) { const id = b.dataset.wsCols, P = ps(id); P.allCols = !P.allCols; const sec = $(`[data-ws-panel="${id}"]`, root); sec.classList.toggle('all-cols', P.allCols); b.textContent = P.allCols ? 'Fewer columns' : 'All columns'; return; }
    if ((b = t('[data-ws-set]'))) {
      const [id, k, v] = b.dataset.wsSet.split(':'); const P = ps(id);
      P[k] = /^-?\d+$/.test(v) ? Number(v) : v;
      if (id === 'earnings' && k === 'offset') { DATA.earnings = undefined; loadPanel('earnings', { force: true }); return; }
      if ((id === 'quote' && k === 'span') || (id === 'contracts' && k === 'side')) { if (id === 'contracts') P.expiry = ''; loadPanel(id, { force: true }); return; }
      paintBody(id); return;
    }
    if ((b = t('[data-ws-im]'))) {
      const sym = b.dataset.wsIm, P = ps('earnings'); P.im[sym] = 'loading'; paintBody('earnings');
      try { const d = await get(`/api/earnings/${enc(sym)}`, { ttl: 600000, timeout: 60000 }); const im = d.implied || {}; P.im[sym] = im.available ? { pct: im.implied_move_pct, expiry: im.expiry } : { reason: clean(im.reason || 'No implied move') }; }
      catch (err) { P.im[sym] = { reason: api.explain(err, 'The chain') }; }
      paintBody('earnings'); return;
    }
    // Home's own blocks (pages/home.js): what matters today, the welcome
    if ((b = t('[data-v2-ev]'))) { const open = b.getAttribute('aria-expanded') === 'true'; b.setAttribute('aria-expanded', String(!open)); const body = document.getElementById(b.getAttribute('aria-controls')); if (body) body.hidden = open; return; }
    if ((b = t('[data-v2-evmore]'))) { const open = b.getAttribute('aria-expanded') === 'true'; const box = document.getElementById(b.getAttribute('aria-controls')); if (box) box.hidden = open; b.setAttribute('aria-expanded', String(!open)); b.textContent = open ? `Show ${b.dataset.v2Evmore} more` : 'Show fewer'; return; }
    if ((b = t('[data-v2-evfilter]'))) { ps('priority').filter = b.dataset.v2Evfilter; paintBody('priority'); const again = $(`[data-v2-evfilter="${ps('priority').filter}"]`, root); if (again) again.focus(); return; }
    if (t('[data-v2-home-ready]')) { paintAll(); window.scrollTo(0, 0); return; }
    if ((b = t('[data-v2-mode]'))) {
      try { if (b.dataset.v2Mode) localStorage.setItem('optic.knowledge.v1', b.dataset.v2Mode); localStorage.setItem('optic.knowledge.asked.v1', '1'); } catch (err) { /* private mode */ }
      $$('[data-v2-mode]', root).forEach((m) => m.setAttribute('aria-checked', String(m === b && !!b.dataset.v2Mode)));
      const sec = $('#ws-modes', root); NEW.modes = []; if (sec) setTimeout(() => { sec.hidden = true; }, b.dataset.v2Mode ? 600 : 0);
      return;
    }
    if ((b = t('[data-ws-move]'))) { const [id, d] = b.dataset.wsMove.split(':'); move(id, Number(d)); return; }
    if ((b = t('[data-ws-span]'))) { const [id, d] = b.dataset.wsSpan.split(':'); resize(id, Number(d)); return; }
    if ((b = t('[data-ws-h]'))) { const [id, d] = b.dataset.wsH.split(':'); mutate((L) => { const x = L.find((y) => y.id === id); x.h = HEIGHTS[Math.max(0, Math.min(2, HEIGHTS.indexOf(x.h) + Number(d)))]; }, `${PANELS[id].title} is ${HEIGHT_WORDS[layout().find((y) => y.id === id).h]} height.`); return; }
    if ((b = t('[data-ws-full]'))) { const id = b.dataset.wsFull; mutate((L) => { const x = L.find((y) => y.id === id); if (x.span === 12) x.span = x.was || PANELS[id].span || 6; else { x.was = x.span; x.span = 12; } }); return; }
    if ((b = t('[data-ws-hide]'))) { const id = b.dataset.wsHide; mutate((L) => { L.find((y) => y.id === id).hidden = true; }, `${PANELS[id].title} hidden. Add panel brings it back.`); return; }
    if ((b = t('[data-ws-show]'))) { const id = b.dataset.wsShow; mutate((L) => { const x = L.find((y) => y.id === id); x.hidden = false; L.splice(L.indexOf(x), 1); L.push(x); }, `${PANELS[id].title} added at the end.`); return; }
    if ((b = t('[data-ws-reload]'))) { loadPanel(b.dataset.wsReload, { force: true }); return; }
    if (t('[data-ws-lock]')) { S.locked = !S.locked; save(); paintAll(); say(S.locked ? 'Layout locked.' : 'Layout unlocked.'); return; }
    if (t('[data-ws-reset]')) { S.layouts[S.preset] = defaults(S.preset); S.fold[S.preset] = {}; save(); paintAll(); toast(`${PRESETS[S.preset].label} is back to its standard layout.`); return; }
    if (t('[data-ws-save]')) { S.layouts.mine = JSON.parse(JSON.stringify(layout())); S.fold.mine = Object.assign({}, S.fold[S.preset]); S.preset = 'mine'; save(); paintAll(); toast('Saved as My Desk.'); return; }
  });
  root.addEventListener('change', (e) => {
    if (e.target.matches('[data-ws-expiry]')) { ps('contracts').expiry = e.target.value; loadPanel('contracts', { force: true }); }
  });
  root.addEventListener('submit', (e) => { const f = e.target.closest('[data-ws-linkform]'); if (!f) return; e.preventDefault(); setLink(f.link.value); });
  // keyboard: arrows on a grip move its panel
  root.addEventListener('keydown', (e) => {
    const g = e.target.closest('[data-ws-grip]'); if (!g) return;
    const d = { ArrowUp: -1, ArrowLeft: -1, ArrowDown: 1, ArrowRight: 1 }[e.key]; if (!d) return;
    e.preventDefault(); move(g.dataset.wsGrip, d);
  });
  // pointer: drag a grip to reorder, drag the corner to resize
  root.addEventListener('pointerdown', (e) => {
    const g = e.target.closest('[data-ws-grip]'), r = e.target.closest('[data-ws-resize]');
    if ((!g && !r) || S.locked || e.button !== 0) return;
    e.preventDefault();
    const id = (g || r).dataset.wsGrip || (g || r).dataset.wsResize, el = $(`[data-ws-panel="${id}"]`, root), grid = $('.ws-grid', root);
    const col = grid.clientWidth / 12, startX = e.clientX, startSpan = layout().find((x) => x.id === id).span;
    el.classList.add('is-dragging');
    const onMove = (ev) => {
      if (r) { const span = Math.max(3, Math.min(12, Math.round(startSpan + (ev.clientX - startX) / col))); el.style.setProperty('--span', span); el.dataset.dragSpan = span; return; }
      const over = document.elementFromPoint(ev.clientX, ev.clientY); const tgt = over && over.closest('[data-ws-panel]');
      if (!tgt || tgt === el) return;
      const box = tgt.getBoundingClientRect(); const after = ev.clientX > box.left + box.width / 2 || ev.clientY > box.bottom - 12;
      grid.insertBefore(el, after ? tgt.nextSibling : tgt);
    };
    const onUp = () => {
      document.removeEventListener('pointermove', onMove); document.removeEventListener('pointerup', onUp);
      el.classList.remove('is-dragging');
      if (r) { const span = Number(el.dataset.dragSpan || startSpan); mutate((L) => { L.find((x) => x.id === id).span = span; }, `${PANELS[id].title} is ${span} columns wide.`); return; }
      const order = $$('[data-ws-panel]', grid).map((p) => p.dataset.wsPanel);
      mutate((L) => { const shown = order.map((pid) => L.find((x) => x.id === pid)).filter(Boolean); const rest = L.filter((x) => !shown.includes(x)); L.splice(0, L.length, ...shown, ...rest); }, `${PANELS[id].title} moved.`);
    };
    document.addEventListener('pointermove', onMove); document.addEventListener('pointerup', onUp);
  });
}

/* ---------------- page ---------------- */
const MARKET_PANELS = ['indices', 'regime', 'expected', 'sectors', 'watch', 'quote', 'contracts', 'portfolio'];
export async function render(main) {
  root = main; live = true; load();
  document.title = 'Home, Optic';
  wire(); paintAll();
  // coming back from research: the layout, the figures and the place on the page are as left
  if (lastScroll) requestAnimationFrame(() => window.scrollTo(0, lastScroll));
  try { mq = matchMedia(PHONE); mq.onchange = () => { if (live) paintAll(); }; } catch (e) { mq = null; }
  try { mq2 = matchMedia('(max-width: 1100px)'); mq2.onchange = () => { if (live) fillRows(); }; } catch (e) { mq2 = null; }
  clearInterval(timer);
  // refresh the market panels every minute while the regular session is open and the tab is visible
  timer = setInterval(() => {
    const open = (((DATA.indices || {}).session) || {}).is_regular;
    if (!live || document.hidden || !open) return;
    layout().filter((x) => !x.hidden && MARKET_PANELS.includes(x.id)).forEach((x) => loadPanel(x.id, { quiet: true }));
  }, 60000);
}
export function dispose() { lastScroll = window.scrollY; live = false; clearInterval(timer); if (mq) mq.onchange = null; if (mq2) mq2.onchange = null; }
export function onLists() {
  if (!live) return;
  if (!!$('#ws-new', root) !== isNew()) { paintAll(); return; }
  const h = $('#ws-starters', root); if (h && NEW.starters) draw(h, starters(NEW.starters));
  if (layout().some((x) => x.id === 'watch' && !x.hidden)) loadPanel('watch', { force: !folded('watch') });
}
export const _test = { PRESETS, PANELS, ESSENTIAL, FRESH, load: () => { load(); return S; }, defaults };
