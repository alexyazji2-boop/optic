// How Milo's answers are drawn, as pure functions so they can be tested: the
// classic panel's mdLite, source chips ([[src key]]), inline charts
// ([[chart SYM span]]), action cards ([[action kind args]]) and follow-up
// questions (lines starting "→" at the end). Ported from static/app.js
// (mdLite, PULSE_SOURCES, PULSE_SRC_RE, PULSE_CHART_RE, MILO_ACTION_RE,
// miloParseAction, splitFollowUps); the tags and their meaning are the
// server's contract, so they must stay the same.
import { esc } from './format.js';

export const SRC_RE = /\s?\[\[src ([a-z_]{2,20})\]\]/g;
export const CHART_RE = /\[\[chart ([A-Z0-9.^=-]{1,12}) (1m|3m|6m|1y|2y|5y)\]\]/g;
export const ACTION_RE = /\[\[action ([a-z]+)((?: [^\]\n]*)?)\]\]/g;
// a figure drawn from Optic's own data (ui/finfigs.js): the tag names it, the terminal fills it (2026-10-20)
export const FIG_RE = /\[\[figure (revenue|margins|cashflow|segments|eps|reactions) ([A-Z0-9.^=-]{1,12})\]\]/g;
const CHART_WORDS = { '1m': 'month', '3m': '3 months', '6m': '6 months', '1y': 'year', '2y': '2 years', '5y': '5 years' };

// key -> [label, where it lives]. Where: a v2 view, or 'sources' for the list under the answer.
export const SOURCES = {
  quote: ['Quote', 'overview'], digest: ['Digest', 'overview'], verdict: ["Optic's read", 'overview'], company: ['Company', 'overview'],
  chart: ['Chart', 'chart'], backtest: ['Backtest', 'chart'], stop_check: ['Stop check', 'chart'], pairs: ['Pairs', 'chart'],
  technicals: ['Technicals', 'swing'], gex: ['Dealer gamma', 'swing'], greeks: ['Greeks', 'swing'], flow: ['Options flow', 'swing'],
  entry_plan: ['Entry plan', 'swing'], naked_ideas: ['Options ideas', 'swing'], strategy_ideas: ['Options ideas', 'swing'],
  long_term: ['Investing', 'long'], valuation: ['Fair-value model', 'long'], framework: ['Research framework', 'overview'],
  earnings: ['Earnings', 'earnings'], news: ['News', 'news'], macro: ['Macro', 'market'], sectors: ['Sectors', 'market'],
  indices: ['Indices', 'indices'], read: ['The Read', 'brief'], compare: ['Compare', 'compare'], tracker: ['Positions', 'tracker'],
  cases: ['Bull and bear case', 'overview'], why: ['What moved it', 'overview'], whats_next: ['Coming up', 'overview'],
  pulse: ["Optic's read", 'overview'], sector_confirm: ['Sector', 'overview'], next_earnings_date: ['Earnings', 'earnings'],
  earnings_momentum: ['Earnings', 'earnings'], portfolio_summary: ['Paper book', 'paper'], reader_holdings: ['Paper book', 'paper'],
  reader_watchlist: ['Watchlist', 'watchlist'], market: ['The Read', 'brief'], vol_surface: ['Options pricing', 'swing'],
  iv_rank: ['IV rank', 'swing'], iv_hv: ['Implied against realised', 'swing'], iv_cheapness: ['Cheap or dear', 'swing'],
  straddle_calibration: ['Straddle record', 'swing'], dispersion: ['Dispersion', 'market'], options_research: ['Options research', 'swing'],
  desk_edition: ['Optic Desk', 'brief'], desk_section: ['Optic Desk', 'brief'], research: ['Sources Milo read', 'sources'],
  retrieved: ['Data Milo retrieved', 'sources'], chart_levels: ['Levels', 'chart'], track_record: ['Track record', 'swing'],
  brokerage_portfolio: ['Your brokerage', 'brokerage'],
};
const SYMBOL_VIEWS = { overview: '', chart: 'chart', swing: 'options', long: 'investing', earnings: 'earnings', news: 'news' };
const PLAIN_VIEWS = { market: '#/macro', brief: '#/read', indices: '#/indices', compare: '#/compare', tracker: '#/portfolio', paper: '#/paper', watchlist: '#/watchlist', brokerage: '#/brokerage' };

/** Where a source chip goes in v2, for the symbol on screen; null when it needs one and there is none. */
export function sourceHref(view, symbol) {
  if (view in SYMBOL_VIEWS) return symbol ? `#/${encodeURIComponent(symbol)}${SYMBOL_VIEWS[view] ? `/${SYMBOL_VIEWS[view]}` : ''}` : null;
  return PLAIN_VIEWS[view] || null;
}

/** The classic mdLite: escape first, then a small, safe subset of markdown. Links must be http(s). */
export function mdLite(text) {
  let out = esc(text);
  out = out.replace(/```([\s\S]*?)```/g, (m, code) => `<pre class="milo-code">${code}</pre>`);
  out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  out = out.replace(/^#{2,3} (.*)$/gm, '<strong class="milo-h">$1</strong>');
  out = out.replace(/^\s*[-*] (.*)$/gm, '<span class="milo-li">$1</span>');
  // numbered steps keep their numbers (2026-10-20: the redesign renders lists, tables and code as written)
  out = out.replace(/^\s*(\d{1,2})[.)] (.*)$/gm, '<span class="milo-li milo-oli"><span class="milo-n">$1.</span> $2</span>');
  out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // tables: lines that start and end with "|", the second a separator row ("|---|:---:|"); figures right-aligned
  out = out.replace(/(^|\n)((?:[ \t]*\|[^\n]*\|[ \t]*(?:\n|$)){2,})/g, (m, lead, block) => {
    const rows = block.trim().split('\n').map((l) => l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim()));
    if (rows.length < 2 || !rows[1].every((c) => /^:?-{2,}:?$/.test(c))) return m;
    const fig = (c) => /^[−+\-]?[$€£]?\d[\d,.]*(?:%|x|bn|m|k|B|M|K)?$/.test(c);
    return `${lead}\n\n<div class="milo-tbl"><table><thead><tr>${rows[0].map((c) => `<th>${c}</th>`).join('')}</tr></thead><tbody>${rows.slice(2).map((r) => `<tr>${r.map((c) => `<td${fig(c) ? ' class="n"' : ''}>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>\n\n`;
  });
  // paragraphs: blank lines separate; single newlines are line breaks
  return out.split(/\n{2,}/).filter((p) => p.trim()).map((p) => (/^\s*<(pre|div class="milo-tbl")/.test(p) ? p.trim() : `<p>${p.replace(/^\n+|\n+$/g, '').replace(/\n/g, '<br>')}</p>`)).join('');
}

/** Trailing "→ question" lines become follow-up buttons (at most four). */
export function splitFollowUps(text) {
  const lines = String(text || '').split('\n'); const ups = []; let end = lines.length;
  while (end > 0) {
    const line = lines[end - 1].trim();
    if (!line) { end -= 1; continue; }
    const hit = line.match(/^(?:→|->)\s+(\S.*)$/);
    if (!hit) break;
    ups.unshift(hit[1].trim()); end -= 1;
  }
  if (!ups.length) return { body: String(text || ''), ups };
  return { body: lines.slice(0, end).join('\n').replace(/\s+$/, ''), ups: ups.slice(0, 4) };
}

/** [[src key]] tags as chips, at most one of each label per paragraph; unknown keys vanish. */
export function sourcesIn(htmlText, symbol) {
  return htmlText.split(/(<\/p>)/).map((para) => {
    const seen = new Set();
    return para.replace(SRC_RE, (m, key) => {
      const s = SOURCES[key];
      if (!s || seen.has(s[0])) return '';
      seen.add(s[0]);
      if (s[1] === 'sources') return ` <button type="button" class="milo-src" data-v2-milo-srclist>${esc(s[0])}</button>`;
      const href = sourceHref(s[1], symbol);
      return href ? ` <a class="milo-src" href="${href}" title="From ${esc(s[0])}. Open it">${esc(s[0])}</a>` : ` <span class="milo-src" title="From ${esc(s[0])}">${esc(s[0])}</span>`;
    });
  }).join('');
}
/** The same tags as plain words, for Copy. */
export function sourcesAsText(text) {
  return String(text || '').split(/(\n\s*\n)/).map((para) => {
    const seen = new Set();
    return para.replace(SRC_RE, (m, key) => { const s = SOURCES[key]; if (!s || seen.has(s[0])) return ''; seen.add(s[0]); return ` (${s[0]})`; });
  }).join('').replace(CHART_RE, '').replace(ACTION_RE, '').replace(FIG_RE, '');
}

/* ---------------- actions ---------------- */
const SYMBOL = /^[A-Z][A-Z0-9.\-]{0,9}$/;
export const SECTIONS = { overview: 'Overview', chart: 'Chart', options: 'Options', investing: 'Investing', earnings: 'Earnings', financials: 'Financials', news: 'News' };
const RANGES = ['1m', '3m', '6m', '1y', 'all'], INTERVALS = ['daily', 'weekly'];
// The classic study ids, and what each is on v2's chart (or null: the Classic chart has it).
export const STUDIES = { sma20: ['SMA 20', 'ov:ma'], sma50: ['SMA 50', 'ov:ma'], sma200: ['SMA 200', 'ov:ma'], ema9: ['EMA 9', 'ov:ema'], ema21: ['EMA 21', 'ov:ema'], ema50: ['EMA 50', 'ov:ema'],
  vol: ['Volume', 'pane:volume'], rsi: ['RSI pane', 'pane:rsi'], macd: ['MACD pane', 'pane:macd'], stages: ['Weinstein stages', null], matrend: ['MA Trend Identifier', null], tso: ['Trend Strength Oscillator pane', null] , msb: ['Market structure breaks', 'ov:msb'] };
export function actionArgs(rawArgs) {
  const text = String(rawArgs || '').replace(/&quot;|[“”]/g, '"').replace(/&#39;|[‘’]/g, "'").trim();
  const out = []; const re = /"([^"]{0,200})"|(\S+)/g; let m;
  while ((m = re.exec(text))) out.push(m[1] !== undefined ? m[1] : m[2]);
  return out;
}
export function parseAction(kind, args) {
  const sym = (v) => String(v || '').toUpperCase().replace(/^\$/, '');
  if (kind === 'open') { const t = sym(args[0]), section = String(args[1] || 'overview').toLowerCase(); if (!SYMBOL.test(t)) return { bad: 'that is not a ticker Optic can open' }; if (!SECTIONS[section]) return { bad: `Optic has no "${section}" section` }; return { kind, sym: t, section, label: `Open ${t}, ${SECTIONS[section]}` }; }
  if (kind === 'compare') { const list = [...new Set(args.map(sym).filter((t) => SYMBOL.test(t)))]; if (list.length < 2 || list.length > 4) return { bad: 'Compare takes two to four tickers' }; return { kind, syms: list, label: `Compare ${list.join(', ')}` }; }
  if (kind === 'watch') { const t = sym(args[0]); if (!SYMBOL.test(t)) return { bad: 'that is not a ticker Optic can watch' }; const list = String(args[1] || '').trim().slice(0, 60); return { kind, sym: t, list, label: list ? `Add ${t} to “${list}”` : `Add ${t} to a watchlist` }; }
  if (kind === 'chart') { const range = String(args[0] || '').toLowerCase(), interval = String(args[1] || 'daily').toLowerCase(); if (!RANGES.includes(range)) return { bad: `the chart has no ${range || 'such'} range` }; if (!INTERVALS.includes(interval)) return { bad: `the chart has no ${interval} interval here` }; return { kind, range, interval, label: `Chart: ${range.toUpperCase()}, ${interval}` }; }
  if (kind === 'indicator') { const id = String(args[0] || '').toLowerCase(); if (!STUDIES[id]) return { bad: `Optic has no "${id}" study` }; return { kind, id, label: `Show ${STUDIES[id][0]}` }; }
  if (kind === 'screen') { const words = String(args.join(' ') || '').trim().slice(0, 300); if (words.length < 3) return { bad: 'there were no criteria to screen on' }; return { kind, words, label: `Find stocks: “${words}”` }; }
  if (kind === 'save') { const q = String(args.join(' ') || '').trim().slice(0, 500); if (q.length < 8) return { bad: 'there was no question to save' }; return { kind, question: q, label: 'Save this question to Research' }; }
  if (kind === 'valuation') return { kind, label: 'Open the valuation model', args };
  if (kind === 'level') { const price = Number(String(args[0] || '').replace(/[$,]/g, '')); const note = String(args[1] || 'Level').trim().slice(0, 40); if (!(price > 0) || !Number.isFinite(price)) return { bad: 'that is not a price' }; return { kind, price, note, label: `Mark ${price.toFixed(2)} on the chart (${note})` }; }
  return { bad: `Optic cannot "${kind}" from here` };
}
const PERSISTS = new Set(['watch', 'save', 'level']);
function actionCard(a) {
  if (a.bad) return `<div class="milo-act milo-act-off" role="note">Not available: ${esc(a.bad)}.</div>`;
  const persists = PERSISTS.has(a.kind);
  const sub = a.kind === 'watch' ? 'Changes your watchlist. Nothing changes until you confirm.' : a.kind === 'save' ? 'Keeps the question in Research. Nothing is saved until you confirm.'
    : a.kind === 'level' ? 'Draws a dashed level labelled Milo on your chart. You can remove it.' : a.kind === 'screen' ? 'Opens Scan with these words. Words the free reader cannot read use one Milo question when you run it.' : 'Opens it in Optic. Nothing is saved.';
  return `<div class="milo-act" data-v2-milo-act="${esc(JSON.stringify(a))}"><p class="milo-act-what">${esc(a.label)}</p><p class="milo-act-sub">${esc(sub)}</p>
    <div class="cluster"><button type="button" class="btn btn-sm${persists ? ' btn-primary' : ''}" data-v2-milo-act-go>${persists ? 'Confirm' : 'Go'}</button>${persists ? '<button type="button" class="btn btn-sm" data-v2-milo-act-skip>Not now</button>' : ''}</div>
    <p class="milo-act-result" role="status" aria-live="polite"></p></div>`;
}
function actionsIn(htmlText) { let n = 0; return htmlText.replace(ACTION_RE, (m, kind, rest) => { n += 1; return n > 2 ? '' : actionCard(parseAction(kind, actionArgs(rest))); }); }
function chartsIn(htmlText) {
  return htmlText.replace(CHART_RE, (m, sym, span) => `<figure class="milo-chart" data-v2-milo-chart="${sym}" data-span="${span}"><div class="milo-chart-plot"></div><figcaption class="asof">${sym}, daily closes over the last ${CHART_WORDS[span]}</figcaption></figure>`);
}
// at most two figures an answer, each a placeholder the panel fills from Optic's data
function figuresIn(htmlText) { let n = 0; return htmlText.replace(FIG_RE, (m, kind, sym) => { n += 1; return n > 2 ? '' : `<figure class="milo-fig" data-v2-milo-fig="${kind}" data-sym="${sym}" aria-busy="true"><p class="asof">Drawing ${esc(sym)}'s figures from Optic's data</p></figure>`; }); }
/** A full answer: body markdown with tags drawn, plus its follow-up questions. */
export function renderAnswer(text, symbol) {
  const { body, ups } = splitFollowUps(text);
  // a tag alone in its paragraph becomes the block itself, not a block inside a <p>
  const md = mdLite(body).replace(/<p>\s*(\[\[(?:chart|action|figure) [^\]]*\]\])\s*<\/p>/g, '$1');
  return { html: sourcesIn(actionsIn(figuresIn(chartsIn(md))), symbol), ups };
}
/** Text still arriving: drop any tag, complete or half-written, so nothing raw flashes. */
export function streamingTail(text) { return String(text || '').replace(/\s?\[\[[^\]\n]*\]\]/g, '').replace(/\s?\[\[?[^\]\n]*$/, ''); }
