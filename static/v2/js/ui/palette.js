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
import { getFlags } from './shell.js';
import { openMilo } from './milo.js';

// The classic labels and search words, so nothing becomes unfindable by the word it was found by.
export const PLACES = [
  { view: 'home', label: 'Home', terms: 'home start' },
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
  { view: 'chart', label: 'Chart', symbol: true, terms: 'chart charting drawings indicators advanced' },
  { view: 'swing', label: 'Options', symbol: true, terms: 'options option chain greeks gamma flow swing setup calls puts strategies levels' },
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

let root, input, list, untrap, opener, timer, seq = 0, items = [], sel = 0, catalogue = null, research = null, ctxSym = null;
const allowed = (p) => (!p.owner || !!(store.state.me && store.state.me.admin)) && (!p.feature || !!getFlags()[p.feature]);
const symFor = () => ctxSym || store.recent()[0] || null;
const placeHref = (p) => (p.symbol ? (symFor() ? hrefFor(p.view, symFor()) : '#/') : hrefFor(p.view));
const go = (href) => () => { if (href.startsWith('/')) location.href = href; else location.hash = href; };
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
function symbolRows(sym, detail, exact) {
  const out = [{ group: 'Open', lead: '◎', label: sym, detail, tag: exact ? '' : 'enter', run: go(`#/${sym}`) }];
  [['Chart', 'Charting workspace', `#/${sym}/chart`], ['News', 'Headlines for this symbol', `#/${sym}/news`], ['Earnings', 'History, estimates and the read', `#/${sym}/earnings`], ['Investing', 'Valuation and the decade view', `#/${sym}/investing`], ['Compare', 'Put it beside other names', `#/compare?t=${sym}`]]
    .forEach(([label, d, href]) => out.push({ group: sym, lead: '→', label, detail: d, run: go(href) }));
  savedFor(sym).forEach((q) => out.push({ group: sym, lead: '✧', label: q.slice(0, 60), detail: 'Saved research', run: () => openMilo({ question: q, opener }) }));
  return out;
}

async function build(q, early) {
  const rows = [];
  const places = PLACES.filter(allowed);
  if (!q) {
    store.recent().slice(0, 5).forEach((s) => rows.push({ group: 'Recent', lead: '◎', label: s, detail: 'Open again', run: go(`#/${s}`) }));
    QUICK.forEach((a) => rows.push({ group: 'Actions', lead: '✦', label: a.label, detail: a.detail, run: a.run }));
    places.slice(0, 6).forEach((p) => rows.push({ group: 'Go to', lead: '→', label: p.label, run: go(placeHref(p)) }));
    return rows;
  }
  const upper = q.toUpperCase(), lower = q.toLowerCase(), isTicker = looksLikeTicker(q), isQuestion = looksLikeQuestion(q);
  const matched = places.filter((p) => p.label.toLowerCase().includes(lower) || p.terms.includes(lower));
  const exact = exactPlace(q, matched);
  const placeRow = (p) => ({ group: 'Go to', lead: '→', label: p.label, detail: p.symbol && symFor() ? symFor() : '', tag: p === exact ? 'enter' : '', run: go(placeHref(p)) });
  if (exact) rows.push(placeRow(exact));
  const from = rows.length;
  if (isTicker) rows.push(...symbolRows(upper, 'Analyse this symbol', !!exact));
  const to = rows.length;
  matched.forEach((p) => { if (p !== exact) rows.push(placeRow(p)); });
  const ask = (isQuestion || (!isTicker && q.length > 2)) ? { group: 'Ask Milo', lead: '✧', label: q, detail: ctxSym ? `With ${ctxSym} and this page in context` : 'Milo answers with this page in context', tag: isQuestion && !exact ? 'enter' : '', run: () => openMilo({ question: q, opener }) } : null;
  if (ask) { if (isQuestion && !exact) rows.unshift(ask); else rows.push(ask); }
  if (early) early(rows.slice());
  const my = seq;
  let results = [];
  try { const r = await api.get(`/api/search?q=${encodeURIComponent(q)}&limit=7`, { ttl: 300000, timeout: 8000 }); results = (r && r.results) || []; } catch (e) { results = []; }
  if (my !== seq) return null;
  if (isTicker && results.length && !results.some((r) => String(r.symbol || '').toUpperCase() === upper)) {
    const top = results[0]; rows.splice(from + (ask && isQuestion && !exact ? 1 : 0), to - from, ...symbolRows(String(top.symbol).toUpperCase(), top.name || 'Analyse this symbol', !!exact)); results = results.slice(1);
  }
  const insertAt = rows.findIndex((r) => r.group === 'Ask Milo' && !isQuestion);
  const symRows = results.filter((r) => !(isTicker && r.symbol === upper)).map((r) => ({ group: 'Symbols', lead: r.etf ? 'ETF' : '◎', label: r.symbol, detail: r.name, run: go(`#/${r.symbol}`) }));
  if (insertAt >= 0) rows.splice(insertAt, 0, ...symRows); else rows.push(...symRows);
  if (looksLikeScreen(q)) {
    if (!catalogue) { try { catalogue = await api.get('/api/scanners', { ttl: 600000 }); } catch (e) { catalogue = { scans: [] }; } }
    if (my !== seq) return null;
    const found = screenMatches(q, catalogue.scans), sector = sectorMentioned(q), caveat = sector ? `Does not filter by ${sector}: these run over the whole ranked universe. ` : '';
    if (found.length) rows.forEach((r) => { if (r.group === 'Ask Milo') r.tag = ''; });
    [...found].reverse().forEach((s, i) => rows.unshift({ group: 'Screen', lead: '≡', label: s.name, detail: caveat + String(s.looks_for || '').slice(0, 120), tag: i === found.length - 1 && !exact ? 'enter' : '', run: go(`#/scan?id=${encodeURIComponent(s.id)}`) }));
    if (sector && found.length) rows.push({ group: 'Screen', lead: '→', label: 'Sector board', detail: `For ${sector} specifically. Macro groups the whole market by sector and drills into one.`, run: go('#/macro') });
  }
  return rows;
}

function ensure() {
  if (root) return;
  root = document.createElement('div');
  root.className = 'palette'; root.hidden = true;
  root.innerHTML = `<div class="palette-scrim"></div><div class="palette-panel" role="dialog" aria-modal="true" aria-label="Search or ask Optic">
    <input type="search" role="combobox" aria-expanded="true" aria-controls="pal-list" aria-autocomplete="list" placeholder="Search stocks, ETFs, pages, or ask Milo" autocomplete="off" spellcheck="false">
    <div class="palette-list" id="pal-list" role="listbox" aria-label="Results"></div>
    <p class="palette-foot" aria-hidden="true"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>↵</kbd> open</span><span><kbd>esc</kbd> close</span></p></div>`;
  document.body.appendChild(root);
  input = $('input', root); list = $('.palette-list', root);
  root.addEventListener('click', (e) => { if (e.target.classList.contains('palette-scrim')) close(); const it = e.target.closest('.palette-item'); if (it) choose(Number(it.dataset.v2Idx)); });
  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => paint(input.value.trim()), 120); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1); } else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
    else if (e.key === 'Enter') { e.preventDefault(); clearTimeout(timer); const q = input.value.trim(); if (q && q !== lastPainted) paint(q).then(() => choose(sel)); else choose(sel); }
  });
}
let lastPainted = '';
async function paint(q) {
  const my = ++seq; lastPainted = q;
  const out = await build(q, (early) => { if (my === seq) draw(early); });
  if (out && my === seq) draw(out);
}
function draw(out) {
  items = out; sel = Math.max(0, out.findIndex((r) => r.tag === 'enter'));
  let last = null;
  render(list, out.length ? out.map((it, i) => { const head = it.group !== last ? html`<p class="palette-group" role="presentation">${it.group}</p>` : ''; last = it.group;
    return html`${head}<button type="button" class="palette-item" role="option" id="pal-${i}" data-v2-idx="${i}" aria-selected="${i === sel}"><span class="pal-lead" aria-hidden="true">${it.lead}</span><span class="pal-main">${it.group === 'Open' || it.group === 'Symbols' || it.group === 'Recent' ? html`<b class="tick">${it.label}</b>` : it.label}</span>${it.detail ? html`<small>${it.detail}</small>` : ''}${it.tag ? html`<kbd class="pal-tag">${it.tag}</kbd>` : ''}</button>`; })
    : html`<p class="quiet">Nothing matches. Try a ticker such as AAPL, or ask a question.</p>`);
  input.setAttribute('aria-activedescendant', out.length ? `pal-${sel}` : '');
  const b = $(`#pal-${sel}`, list); if (b) b.scrollIntoView({ block: 'nearest' });
}
function move(d) {
  if (!items.length) return;
  sel = (sel + d + items.length) % items.length;
  $$('.palette-item', list).forEach((b, i) => b.setAttribute('aria-selected', String(i === sel)));
  input.setAttribute('aria-activedescendant', `pal-${sel}`);
  const b = $(`#pal-${sel}`, list); if (b) b.scrollIntoView({ block: 'nearest' });
}
function choose(i) { const it = items[i]; if (!it) return; close({ silent: true }); it.run(); }

/** Open the palette; seed it with text when a field handed it over. */
export function open(from, { seed = '', symbol = null } = {}) {
  ensure();
  opener = from || document.activeElement; ctxSym = symbol;
  root.hidden = false; input.value = seed;
  paint(seed.trim());
  untrap = trapFocus($('.palette-panel', root), () => close());
  input.focus();
  // the account's saved research arrives after the first paint: paint again
  // when it does, so a symbol's saved questions show without another keystroke
  if (store.signedIn() && research === null) {
    api.get('/api/saved-research?limit=200', { ttl: 60000 }).then((r) => { research = (r && r.research) || []; }, () => { research = []; })
      .then(() => { if (isOpen() && research.length) paint(input.value.trim()); });
  }
}
export function close({ silent } = {}) {
  if (!root || root.hidden) return;
  root.hidden = true; if (untrap) untrap();
  if (!silent && opener && document.contains(opener)) opener.focus();
}
export const isOpen = () => !!root && !root.hidden;
export function forgetResearch() { research = null; }
