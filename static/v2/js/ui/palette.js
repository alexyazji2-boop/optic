// Search or ask: ⌘K, "/", or the top bar. The classic palette's behaviour
// (static/app.js paletteBuild), on v2's addresses:
//   empty: recent symbols, quick actions, places
//   typed: an exact page name first (it beats a ticker guess, so "scan" opens
//   Scan), a symbol with its actions and saved research, other places, search
//   results, screens that match a request for a list of names, and an Ask
//   Milo row (first when it reads as a question). Asking drafts the question
//   in Milo; nothing is sent until the reader presses Send there.
import { html, render, $, $$, trapFocus } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { hrefFor } from '../nav.js';
import * as router from '../core/router.js';
import { getFlags } from './shell.js';
import { openMilo } from './milo.js';
// Row markers are the app's own line icons: the sparkle and arrow characters read as emoji (owner's checklist, 2026-10-19).
import { icon } from './icons.js';

// The classic labels and search words, so nothing becomes unfindable by the word it was found by.
export const PLACES = [
  { view: 'home', label: 'Home', terms: 'home start workspace dashboard layout panels market overview options research long-term investing my desk' },
  { view: 'brief', label: "Optic's Read", terms: 'read brief daily market news morning' },
  { view: 'market', label: 'Macro & sectors', terms: 'macro sectors rotation regime economy' },
  { view: 'indices', label: 'Indices', terms: 'indices index spy qqq cycle' },
  { view: 'explore', label: 'Explore', terms: 'explore discover browse trending ideas sectors what is happening' },
  { view: 'scan', label: 'Scan', terms: 'scan screener find candidates momentum breakout' },
  { view: 'paper', label: 'Paper Desk', terms: 'paper desk trades trading simulator practice manual position long short buy sell shares option call put book ticket mock virtual' },
  { view: 'analysts', label: 'Analyst actions', terms: 'analysts analyst ratings rating upgrades downgrades upgrade downgrade price targets target initiations estimates firms' },
  { view: 'insiders', label: 'Insiders', terms: 'insiders insider congress congressional politicians form 4 stock act disclosures pelosi senator representative buying selling' },
  { view: 'reports', label: 'Problem Reports', owner: true, terms: 'reports problem report feedback bug issue complaints readers inbox support' },
  { view: 'usage', label: 'Claude usage', owner: true, terms: 'usage credits spend cost bill billing anthropic claude tokens api model' },
  { view: 'accounts', label: 'Accounts', owner: true, terms: 'accounts users signups sign ups members people registered emails readers' },
  { view: 'watchlist', label: 'Watchlist', terms: 'watchlist watching follow list' },
  { view: 'alerts', label: 'Alerts', terms: 'alerts alarms notifications fired' },
  { view: 'compare', label: 'Compare', terms: 'compare versus vs side by side' },
  { view: 'overview', label: 'Dossier: Overview', symbol: true, terms: 'overview dossier ticker security summary company snapshot' },
  { view: 'chart', label: 'Chart', symbol: true, terms: 'chart charting drawings indicators advanced studies backtest back-test pairs stop' },
  { view: 'swing', label: 'Options', symbol: true, terms: 'options option chain greeks gamma gex flow swing setup calls puts strategies levels payoff builder spread' },
  { view: 'long', label: 'Investing', symbol: true, terms: 'investing long term valuation fair value dcf conviction drawdown hold' },
  { view: 'earnings', label: 'Earnings', symbol: true, terms: 'earnings report eps estimates surprise implied move guidance results' },
  { view: 'financials', label: 'Financials', symbol: true, terms: 'financials revenue margin cash ownership short interest statements' },
  { view: 'news', label: 'News', symbol: true, terms: 'news headlines catalysts sentiment company' },
  { view: 'tracker', label: 'Optic Portfolio', terms: 'positions ledger record paper trades book' },
  { view: 'roth', label: 'Retirement', terms: 'retirement roth ira allocation contribution funds long term planner pension' },
  { view: 'settings', label: 'Settings', terms: 'settings appearance theme timezone preferences' },
  { view: 'brokerage', label: 'Brokerage', feature: 'brokerage', terms: 'brokerage broker linked accounts connect schwab fidelity robinhood vanguard holdings my portfolio snaptrade' },
];
const QUESTION_WORDS = /^(what|why|how|when|where|which|who|is|are|does|do|should|can|will|find|show|explain|compare)\b/i;
export const looksLikeTicker = (t) => /^[A-Za-z][A-Za-z.-]{0,5}$/.test(String(t).trim());
// What a result is decides where it opens: an index, rate, currency, future or crypto has an
// instrument page, not a company dossier (the search audit, 2026-10-20: ^TNX opened as a dossier).
const INSTRUMENT_KINDS = new Set(['index', 'rate', 'fx', 'commodity', 'future', 'crypto']);
export const isInstrument = (sym, kind) => (kind ? INSTRUMENT_KINDS.has(kind) : /^\^|=|-USD$|\.NYB$/.test(String(sym || '')));
export const openHref = (sym, kind) => (isInstrument(sym, kind) ? `#/instrument/${encodeURIComponent(sym)}` : hrefFor('overview', sym));
// An index's options trade on its fund, so the chart-then-options path still works from ^GSPC.
const PROXY = { '^GSPC': 'SPY', '^NDX': 'QQQ', '^RUT': 'IWM', '^DJI': 'DIA', 'ES=F': 'SPY', 'NQ=F': 'QQQ', 'RTY=F': 'IWM' };
const KIND_WORD = { etf: 'fund', index: 'index', rate: 'rate', fx: 'currency', commodity: 'commodity', future: 'future', crypto: 'crypto' };
const startsWord = (name, q) => String(name || '').toLowerCase().split(/[\s,.]+/).some((w) => w.startsWith(q.toLowerCase()));
export function looksLikeQuestion(text) { const t = String(text).trim(); if (!t) return false; if (t.endsWith('?')) return true; if (QUESTION_WORDS.test(t) && t.split(/\s+/).length > 1) return true; return t.split(/\s+/).length >= 3; }
const SCREEN_INTENT = /\b(find|show|screen|scan|list|which|what)\b/i, SCREEN_NOUNS = /\b(stocks?|names?|tickers?|companies|equities|etfs?|setups?)\b/i;
export const looksLikeScreen = (t) => { t = String(t || '').trim(); return t.length >= 8 && SCREEN_INTENT.test(t) && SCREEN_NOUNS.test(t); };
const SECTOR_WORDS = ['technology', 'tech', 'semiconductor', 'semiconductors', 'semis', 'software', 'hardware', 'healthcare', 'health', 'biotech', 'biotechnology', 'pharma', 'pharmaceutical', 'financial', 'financials', 'bank', 'banks', 'banking', 'insurance', 'energy', 'oil', 'gas', 'utilities', 'utility', 'industrial', 'industrials', 'materials', 'mining', 'gold', 'consumer', 'retail', 'staples', 'discretionary', 'communication', 'media', 'telecom', 'real estate', 'reit', 'reits', 'transport', 'airlines', 'autos', 'defence', 'defense', 'aerospace'];
export const sectorMentioned = (text) => { const l = ` ${String(text || '').toLowerCase()} `; return SECTOR_WORDS.find((w) => l.includes(` ${w} `) || l.includes(` ${w}s `)) || null; };
const SCREEN_STOP = new Set(['find', 'show', 'me', 'the', 'a', 'an', 'with', 'and', 'or', 'for', 'of', 'in', 'on', 'that', 'are', 'is', 'to', 'stocks', 'stock', 'names', 'name', 'tickers', 'ticker', 'companies', 'which', 'what', 'list', 'screen', 'scan', 'best', 'good', 'some', 'any', 'right', 'now']);
export function screenMatches(text, scans) {
  const terms = String(text || '').toLowerCase().replace(/[^a-z0-9\s-]/g, ' ').split(/\s+/).filter((w) => w.length > 2 && !SCREEN_STOP.has(w));
  if (!terms.length || !(scans || []).length) return [];
  return scans.map((s) => {
    const name = String(s.name || '').toLowerCase(), id = String(s.id || '').toLowerCase().replace(/[-_]/g, ' '), body = String(s.looks_for || '').toLowerCase(); let score = 0;
    terms.forEach((w) => { const idHit = id.includes(w) || id.split(' ').some((part) => part.startsWith(w.slice(0, 5)) && w.length >= 5); if (name.includes(w) || idHit) score += 3; else if (body.includes(w)) score += 1; });
    return { s, score };
  }).filter((r) => r.score > 0).sort((a, b) => b.score - a.score).slice(0, 3).map((r) => r.s);
}
/** The place a typed word names exactly (its label, or one of its search words). */
export function exactPlace(q, places) { const l = String(q).trim().toLowerCase(); return places.find((p) => p.label.toLowerCase() === l || p.terms.split(/\s+/).indexOf(l) !== -1) || null; }

let root, input, list, note, untrap, opener, timer, seq = 0, items = [], sel = 0, catalogue = null, research = null, ctxSym = null, vvOff = null, scrollY0 = 0;
let moved = null, pending = null, pendingFor = null, settledFor = null, notice = '';
const allowed = (p) => (!p.owner || !!(store.state.me && store.state.me.admin)) && (!p.feature || !!getFlags()[p.feature]);
const symFor = () => ctxSym || store.recent().find((s) => !isInstrument(s)) || null;
const placeHref = (p) => (p.href ? p.href : p.symbol ? (symFor() ? hrefFor(p.view, symFor()) : '#/') : hrefFor(p.view));
// While the palette is open it has a history entry of its own, so Back on a phone closes it.
// Opening a result replaces that entry: Back from the result returns to the screen the search began
// on, with no empty step between. The current address re-renders instead of doing nothing.
const onEntry = () => !!(history.state && history.state.v2palette);
const go = (href) => () => {
  if (href.startsWith('/')) { location.href = href; return; }
  if (onEntry()) {
    if (href === location.hash) { history.back(); return; }
    location.replace(`${location.pathname}${location.search}${href}`);
    return;
  }
  router.go(href);
};
const QUICK = [
  { label: 'Market overview', detail: 'Macro, sectors and rotation', run: go('#/macro') },
  { label: "Today's read", detail: 'The written daily brief', run: go('#/read') },
  { label: 'Find movers', detail: 'Ranked on a one-month move', run: go('#/scan?id=movers') },
  { label: 'Find unusual volume', detail: 'Twenty-day volume against sixty', run: go('#/scan?id=volume') },
  { label: 'Momentum leaders', detail: 'Highest trend and momentum score', run: go('#/scan?id=momentum') },
  { label: 'Compare stocks', detail: 'Side by side on the same measures', run: go('#/compare') },
  { label: 'Charting', detail: 'Drawings, studies and intraday', run: () => go(symFor() ? `#/${symFor()}/chart` : '#/')() },
  { label: 'Ask Milo', detail: 'Put a question to the assistant', run: () => openMilo({ opener }) },
];

function savedFor(sym) {
  const list0 = store.signedIn() ? (research || []) : (() => { if (!holds(store.state.user)) return []; try { const v = JSON.parse(localStorage.getItem('optic.research.v1') || '[]'); return Array.isArray(v) ? v : []; } catch (e) { return []; } })();
  return list0.filter((r) => String(r.ticker || r.symbol || '').toUpperCase() === sym).slice(0, 3).map((r) => String(r.question || r.title || ''));
}
/** The Open row and the symbol's own places. `kind` is the search's (stock, etf, index, ...), or ''
 * for a symbol taken as typed; `enter` marks the row Enter opens. */
function symbolRows(sym, detail, { kind = '', enter = true, bare = false } = {}) {
  const word = KIND_WORD[kind];
  const what = [detail, word && kind !== 'etf' ? word : ''].filter(Boolean).join(', ');
  const out = [{ group: 'Open', lead: isInstrument(sym, kind || undefined) ? icon('markets') : icon('dossier'), label: sym, detail: what, tag: enter ? 'enter' : '', run: go(openHref(sym, kind || undefined)) }];
  if (bare) return out;   // nothing listed under that name: no Chart, Options and the rest to offer for it
  if (isInstrument(sym, kind || undefined)) {
    const proxy = PROXY[sym];
    if (proxy) out.push({ group: sym, lead: icon('arrow'), label: `Options on ${proxy}`, detail: `The fund that tracks it; ${sym} has no option chain here`, run: go(hrefFor('swing', proxy)) });
    return out;
  }
  const fund = kind === 'etf';
  [['Chart', 'Charting workspace', 'chart'], ['Options', 'The chain, positioning and the position builder', 'swing'], fund ? null : ['Earnings', 'History, estimates and the read', 'earnings'],
    ['News', 'Headlines for this symbol', 'news'], ['Investing', fund ? 'The decade view' : 'Valuation and the decade view', 'long']].filter(Boolean)
    .forEach(([label, d, view]) => out.push({ group: sym, lead: icon('arrow'), label, detail: d, run: go(hrefFor(view, sym)) }));
  out.push({ group: sym, lead: icon('arrow'), label: 'Compare', detail: 'Put it beside other names', run: go(`#/compare?t=${encodeURIComponent(sym)}`) });
  savedFor(sym).forEach((q) => out.push({ group: sym, lead: icon('milo'), label: q.slice(0, 60), detail: 'Saved research', run: () => openMilo({ question: q, opener }) }));
  return out;
}

async function build(q, early) {
  const rows = [];
  const places = PLACES.filter(allowed);
  notice = '';
  if (!q) {
    const rec = store.recent().slice(0, 5);
    rec.forEach((s) => rows.push({ group: 'Recent', lead: icon(isInstrument(s) ? 'chart' : 'dossier'), label: s, detail: 'Open again', run: go(openHref(s)) }));
    if (rec.length) rows.push({ group: 'Recent', lead: icon('close'), label: 'Clear recent symbols', detail: 'Forgets them in this browser', keep: true, run: () => store.clearRecent() });
    // companies first, by the names a newcomer knows, then a few actions; the full list of pages answers to typing
    POPULAR.filter(([s2]) => !rec.includes(s2)).slice(0, rec.length ? 2 : 4).forEach(([s2, name, d]) => rows.push({ group: 'Companies', lead: icon(s2 === 'SPY' ? 'markets' : 'dossier'), label: `${name} · ${s2}`, detail: d, run: go(openHref(s2)) }));
    QUICK.slice(0, 3).forEach((x) => rows.push({ group: 'Actions', lead: icon('arrow'), label: x.label, detail: x.detail, run: x.run }));
    places.slice(0, 4).forEach((p) => rows.push({ group: 'Go to', lead: icon('arrow'), label: p.label, run: go(placeHref(p)) }));
    return rows;
  }
  const upper = q.toUpperCase(), lower = q.toLowerCase(), isTicker = looksLikeTicker(q), isQuestion = looksLikeQuestion(q);
  const matched = places.filter((p) => p.label.toLowerCase().includes(lower) || p.terms.includes(lower));
  const exact = exactPlace(q, matched);
  const placeRow = (p) => ({ group: 'Go to', lead: icon('arrow'), label: p.label, detail: p.symbol && symFor() ? symFor() : '', tag: p === exact ? 'enter' : '', run: go(placeHref(p)) });
  // the quick actions answer to what they do ("movers", "unusual volume"), not only on an empty box
  const actions = lower.length >= 3 ? QUICK.filter((x) => `${x.label} ${x.detail}`.toLowerCase().split(/[\s,]+/).some((w) => w.startsWith(lower)) || x.label.toLowerCase().includes(lower)) : [];
  if (exact) rows.push(placeRow(exact));
  const from = rows.length;
  // until the search answers, a ticker-shaped word is offered as typed, without the Enter mark
  if (isTicker) rows.push(...symbolRows(upper, 'Looking it up', { enter: false }));
  const to = rows.length;
  matched.forEach((p) => { if (p !== exact) rows.push(placeRow(p)); });
  actions.forEach((x) => rows.push({ group: 'Actions', lead: icon('arrow'), label: x.label, detail: x.detail, run: x.run }));
  const ask = (isQuestion || (!isTicker && q.length > 2)) ? { group: 'Ask Milo', lead: icon('milo'), label: q, detail: ctxSym ? `With ${ctxSym} and this page in context` : 'Milo answers with this page in context', tag: isQuestion && !exact ? 'enter' : '', run: () => openMilo({ question: q, opener }) } : null;
  if (ask) { if (isQuestion && !exact) rows.unshift(ask); else rows.push(ask); }
  if (early) early(rows.slice());
  const my = seq;
  // A sentence is a question for Milo, not a name: the directory is not asked (over 40 characters it refuses).
  const lookUp = q.length <= 40 && !(isQuestion && q.split(/\s+/).length > 3);
  let results = [], failed = false;
  if (lookUp) {
    try { const r = await api.get(`/api/search?q=${encodeURIComponent(q)}&limit=8`, { ttl: 300000, timeout: 8000 }); results = (r && r.results) || []; failed = !!(r && r.available === false); } catch (e) { failed = true; }
  }
  if (my !== seq) return null;
  const at = from + (ask && isQuestion && !exact ? 1 : 0);
  const hit = results.find((r) => r.match === 'symbol');
  // A name is promoted to the Open row only when it is what was typed: a symbol, a name people use
  // ("google", "spx", "10 year"), or a company whose name starts with the word. "VIX" no longer opens VIXM.
  const first = results[0];
  const named = !hit && first && (first.match === 'alias' || (['name', 'word'].includes(first.match) && (first.kind || 'stock') === 'stock' && startsWord(first.name, q))) ? first : null;
  const top = hit || named;
  const others = top ? results.filter((r) => r !== top) : results;
  const placeTakes = !!exact || matched.length > 0 || actions.length > 0;
  // A page named exactly ("scan", "Compare") beats a ticker; a page that only lists the word among its
  // search terms does not beat the listed symbol itself ("SPY" opens SPY, not Indices).
  const byLabel = !!exact && exact.label.toLowerCase() === lower;
  if (hit && exact && !byLabel) rows.forEach((r) => { if (r.group === 'Go to' && r.label === exact.label) r.tag = ''; });
  if (top) {
    const enter = (!exact || (hit && !byLabel)) && !(isQuestion && ask);
    const swap = symbolRows(String(top.symbol).toUpperCase(), top.name || '', { kind: top.kind || (top.etf ? 'etf' : 'stock'), enter });
    if (isTicker) rows.splice(at, to - from, ...swap); else rows.splice(at, 0, ...swap);
  } else if (isTicker) {
    // nothing listed under that word: it can still be opened as typed (a foreign listing, a new issue),
    // said plainly, and a place or action that matched takes Enter instead
    const why = failed ? 'Search is unavailable; opens as typed' : results.length ? 'Not a listed symbol; opens as typed' : 'No listing found; opens as typed';
    rows.splice(at, to - from, ...symbolRows(upper, why, { enter: !placeTakes && !(isQuestion && ask), bare: !failed }));
    if (placeTakes && !exact) { const row = rows.find((r) => r.group === 'Go to' || r.group === 'Actions'); if (row) row.tag = 'enter'; }
  }
  if (failed) notice = 'Company search is not answering right now. Typed symbols still open, and pages and Milo work as usual.';
  else if (lookUp && !results.length && !isTicker && !matched.length && !actions.length) notice = `No company, fund or index matches "${q}".`;
  const insertAt = rows.findIndex((r) => r.group === 'Ask Milo' && !isQuestion);
  const symRows = others.map((r) => ({ group: 'Symbols', lead: isInstrument(r.symbol, r.kind) ? icon('markets') : r.etf ? 'ETF' : icon('dossier'), label: r.symbol, detail: [r.name, KIND_WORD[r.kind] && r.kind !== 'etf' ? KIND_WORD[r.kind] : ''].filter(Boolean).join(', '), run: go(openHref(r.symbol, r.kind)) }));
  if (insertAt >= 0) rows.splice(insertAt, 0, ...symRows); else rows.push(...symRows);
  if (looksLikeScreen(q)) {
    if (!catalogue) { try { catalogue = await api.get('/api/scanners', { ttl: 600000 }); } catch (e) { catalogue = { scans: [] }; } }
    if (my !== seq) return null;
    const found = screenMatches(q, catalogue.scans), sector = sectorMentioned(q), caveat = sector ? `Does not filter by ${sector}: these run over the whole ranked universe. ` : '';
    if (found.length) rows.forEach((r) => { r.tag = ''; });
    const screens = found.map((s, i) => ({ group: 'Screen', lead: icon('discover'), label: s.name, detail: caveat + String(s.looks_for || '').slice(0, 120), tag: i === 0 && !exact ? 'enter' : '', run: go(`#/scan?id=${encodeURIComponent(s.id)}`) }));
    if (sector && found.length) screens.push({ group: 'Screen', lead: icon('arrow'), label: 'Sector board', detail: `For ${sector} specifically. Macro groups the whole market by sector and drills into one.`, run: go('#/macro') });
    rows.unshift(...screens);
    if (exact) { const ex = rows.find((r) => r.group === 'Go to' && r.label === exact.label); if (ex) ex.tag = 'enter'; }
  }
  return rows;
}

const POPULAR = [['AAPL', 'Apple', 'iPhone, Mac and services'], ['NVDA', 'NVIDIA', 'Chips for AI and graphics'], ['MSFT', 'Microsoft', 'Software and cloud'], ['SPY', 'S&P 500 fund', 'A fund that tracks the S&P 500']];
function ensure() {
  if (root) return;
  root = document.createElement('div');
  root.className = 'palette'; root.hidden = true;
  root.innerHTML = `<div class="palette-scrim"></div><div class="palette-panel" role="dialog" aria-modal="true" aria-label="Search or ask Optic">
    <div class="palette-top"><input type="search" role="combobox" aria-expanded="true" aria-controls="pal-list" aria-autocomplete="list" aria-label="Search a company, fund, index or page, or ask Milo a question" placeholder="Search a company" autocomplete="off" autocapitalize="none" autocorrect="off" enterkeyhint="go" spellcheck="false">
      <button type="button" class="palette-x" data-pal-close>Cancel</button></div>
    <div class="palette-list" id="pal-list" role="listbox" aria-label="Results"></div>
    <p class="palette-note" role="status" aria-live="polite" hidden></p>
    <p class="palette-foot" aria-hidden="true"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>↵</kbd> open</span><span><kbd>esc</kbd> close</span></p></div>`;
  document.body.appendChild(root);
  input = $('input', root); list = $('.palette-list', root); note = $('.palette-note', root);
  // the scrim, Cancel or Escape close it and put the reader back where they were (beginner brief item 12: a phone
  // has no Escape key, and the menu showed no way out)
  root.addEventListener('click', (e) => { if (e.target.classList.contains('palette-scrim') || e.target.closest('[data-pal-close]')) { close(); return; } const it = e.target.closest('.palette-item'); if (it) choose(Number(it.dataset.v2Idx)); });
  input.addEventListener('input', () => { moved = null; clearTimeout(timer); timer = setTimeout(() => paint(input.value.trim()), 120); });
  input.addEventListener('keydown', (e) => {
    if (e.isComposing) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1); } else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
    else if (e.key === 'Home' && items.length) { e.preventDefault(); move(-sel); } else if (e.key === 'End' && items.length) { e.preventDefault(); move(items.length - 1 - sel); }
    else if (e.key === 'Enter') {
      e.preventDefault(); clearTimeout(timer);
      // Enter waits until the search has answered for exactly what is typed, so a fast Enter never opens a guess
      const q = input.value.trim();
      if (q === settledFor) choose(sel); else (q === pendingFor && pending ? pending : paint(q)).then(() => { if (input.value.trim() === q) choose(sel); });
    }
  });
  window.addEventListener('popstate', () => { if (isOpen() && !onEntry()) close({ fromHistory: true }); });
}
function paint(q) {
  const my = ++seq; settledFor = null; pendingFor = q;
  pending = build(q, (early) => { if (my === seq) draw(early); }).then((out) => { if (out && my === seq) { draw(out); settledFor = q; } });
  return pending;
}
function draw(out) {
  items = out;
  // once the reader has moved the selection, results arriving keep it on the same row
  const keep = moved ? out.findIndex((r) => `${r.group}|${r.label}` === moved) : -1;
  sel = keep >= 0 ? keep : Math.max(0, out.findIndex((r) => r.tag === 'enter'));
  if (note) { note.textContent = notice; note.hidden = !notice; }
  let last = null;
  render(list, out.length ? out.map((it, i) => { const head = it.group !== last ? html`<p class="palette-group" role="presentation">${it.group}</p>` : ''; last = it.group;
    return html`${head}<button type="button" class="palette-item" role="option" id="pal-${i}" data-v2-idx="${i}" aria-selected="${i === sel}"><span class="pal-lead" aria-hidden="true">${it.lead}</span><span class="pal-main">${it.group === 'Open' || it.group === 'Symbols' || it.group === 'Recent' ? html`<b class="tick">${it.label}</b>` : it.label}</span>${it.detail ? html`<small>${it.detail}</small>` : ''}${it.tag ? html`<kbd class="pal-tag">${it.tag}</kbd>` : ''}</button>`; })
    : html`<p class="quiet">${notice ? '' : 'Nothing matches. Try a ticker such as AAPL, or ask a question.'}</p>`);
  input.setAttribute('aria-activedescendant', out.length ? `pal-${sel}` : '');
  const b = $(`#pal-${sel}`, list); if (b) b.scrollIntoView({ block: 'nearest' });
}
function move(d) {
  if (!items.length) return;
  sel = (sel + d + items.length) % items.length;
  moved = `${items[sel].group}|${items[sel].label}`;
  $$('.palette-item', list).forEach((b, i) => b.setAttribute('aria-selected', String(i === sel)));
  input.setAttribute('aria-activedescendant', `pal-${sel}`);
  const b = $(`#pal-${sel}`, list); if (b) b.scrollIntoView({ block: 'nearest' });
}
function choose(i) {
  const it = items[i]; if (!it) return;
  if (it.keep) { it.run(); paint(input.value.trim()); input.focus({ preventScroll: true }); return; }   // an action on the list itself keeps it open
  close({ silent: true, leaving: true }); it.run();
  // an action that does not navigate (Ask Milo) leaves the palette's history step behind: drop it
  setTimeout(() => { if (onEntry() && !isOpen()) history.back(); }, 0);
}

/** Open the palette; seed it with text when a field handed it over. */
export function open(from, { seed = '', symbol = null } = {}) {
  ensure();
  opener = from || document.activeElement; ctxSym = symbol;
  scrollY0 = window.scrollY; moved = null; settledFor = null;
  if (!onEntry()) { try { history.pushState(Object.assign({}, history.state || {}, { v2palette: 1 }), ''); } catch (e) { /* a sandboxed frame */ } }
  root.hidden = false; input.value = seed;
  paint(seed.trim());
  untrap = trapFocus($('.palette-panel', root), () => close());
  // a phone's keyboard covers the bottom of the screen: the list fits the visible part (visualViewport) instead
  const vv = window.visualViewport;
  if (vv && !vvOff) { const fit = () => root.style.setProperty('--vvh', `${Math.round(vv.height)}px`); fit(); vv.addEventListener('resize', fit); vvOff = () => { vv.removeEventListener('resize', fit); vvOff = null; }; }
  input.focus({ preventScroll: true });
  // the account's saved research arrives after the first paint: paint again
  // when it does, so a symbol's saved questions show without another keystroke
  if (store.signedIn() && research === null) {
    api.get('/api/saved-research?limit=200', { ttl: 60000 }).then((r) => { research = (r && r.research) || []; }, () => { research = []; })
      .then(() => { if (isOpen() && research.length) paint(input.value.trim()); });
  }
}
export function close({ silent, leaving, fromHistory } = {}) {
  if (!root || root.hidden) return;
  root.hidden = true; if (untrap) untrap();
  if (vvOff) vvOff();
  // Escape, the scrim or a route change take the palette's history step away; Back already has
  if (!leaving && !fromHistory && onEntry()) history.back();
  // dismissing returns the reader to the screen and the place they left (iOS scrolls the page to the focused field)
  if (!silent) { if (opener && document.contains(opener)) opener.focus({ preventScroll: true }); if (Math.abs(window.scrollY - scrollY0) > 1) window.scrollTo(0, scrollY0); }
}
export const isOpen = () => !!root && !root.hidden;
export function forgetResearch() { research = null; }
