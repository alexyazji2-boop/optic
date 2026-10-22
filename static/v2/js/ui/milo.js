// Milo, the assistant. A conversation, not a single question: every exchange
// is sent with the ones before it, kept in the classic app's own history key
// (optic.pulse.history.v1, a personal key, so it is the same list in both
// apps), and can be reopened, continued or deleted.
//
// What Milo is told about the page is built when the reader presses Send, from
// the route on screen at that moment. Pages register a context provider as
// they render; the app clears it on every navigation (resetContext), so a page
// that registers nothing sends nothing, and a Dossier page's data is dropped if
// it names a different symbol from the one on screen. The label the reader
// sees is built the same way, so it always names the page actually open.
//
// Nothing is sent until the reader presses Send. Every entry point drafts.
import { html, render, $, raw, announce } from '../core/dom.js';
import { makeDrawer } from './drawer.js';
import { saveQuestion } from '../core/research.js';
import { toast } from './toast.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import * as prefs from '../core/prefs.js';
import * as router from '../core/router.js';
import { holds } from '../core/device.js';
import { esc, compact } from '../core/format.js';
import { GROUPS, SETTINGS } from '../nav.js';
import { renderAnswer, streamingTail, sourcesAsText, STUDIES, SECTIONS as ACT_SECTIONS } from '../core/milo-text.js';
import { lineChart, mountCharts } from './chart.js';
import * as FF from './finfigs.js';
import { CLASSIC } from '../core/classic.js';
import { miloNotice } from '../core/legal.js';
import { icon } from './icons.js';

const HISTORY_KEY = 'optic.pulse.history.v1', PERSONA_KEY = 'optic.pulse.persona.v1', HORIZON_KEY = 'optic.milo.horizon.v1', RESEARCH_KEY = 'optic.research.v1';
const MAX_CONVERSATIONS = 30, MAX_MESSAGES = 60, MAX_CHARS = 12000;
const DOSSIER = new Set(['overview', 'chart', 'swing', 'long', 'earnings', 'financials', 'news']);
const STEP_WORDS = { thinking: 'Thinking it through', 'searching the web': 'Searching the web', searching: 'Searching live sources', 'reading results': 'Reading what it found' };
const SCOPES = { auto: 'This page', market: 'Market only', none: 'No page context' };

/* ---------------- context ---------------- */
let provider = null, route = { view: 'home' };
// The block an Ask Milo button sits in ("Brokerage: VOO thesis"), and the
// symbol it is about when the page itself has none: the classic app's
// per-panel ask chips said where a question came from. Cleared on navigation.
let asked = null;
/**
 * The figures of the panel an Ask Milo button sits in, as the reader sees them (Classic parity B4a.3): its heading,
 * its value tiles (dt and dd), its finding line, and the first rows of its first table. Only what is on screen
 * (not a folded section's insides, not a closed fold), capped, so Milo answers about the numbers the reader is
 * looking at. Read at the press, so a panel that refreshed sends what it shows now.
 */
export function panelFigures(el) {
  const box = el && el.closest && el.closest('section.section, .answer, .ws-panel, .op-sec, .chw, article.card');
  if (!box) return null;
  const shown = (n) => n && n.getClientRects().length > 0 && !n.closest('details:not([open]) > :not(summary)');
  const text = (n, max = 160) => { if (!n) return ''; const c = n.cloneNode(true); c.querySelectorAll('button, .sec-fold, .sec-tag, .sr, svg, script, style').forEach((x) => x.remove()); return c.textContent.replace(/\s+/g, ' ').trim().slice(0, max); };
  const h = [...box.querySelectorAll('h2, h3')].find(shown);
  const figures = [...box.querySelectorAll('dt')].filter(shown).slice(0, 30).map((dt) => [text(dt, 80), text(dt.nextElementSibling, 120)]).filter(([k, v]) => k && v);
  const notes = [...box.querySelectorAll('.section-sub, .lead, .answer-lead, .t-lead, .finding')].filter(shown).slice(0, 2).map((n) => text(n, 300)).filter(Boolean);
  const tb = [...box.querySelectorAll('table')].find(shown);
  const table = tb ? { head: [...tb.querySelectorAll('thead th')].map((x) => text(x, 40)), rows: [...tb.querySelectorAll('tbody tr')].filter(shown).slice(0, 8).map((tr) => [...tr.children].map((x) => text(x, 60))) } : null;
  const out = { name: text(h, 100) || null, figures, notes };
  if (table && table.rows.length) out.table = table;
  return figures.length || notes.length || out.table ? out : null;
}
/** Pages register what Milo may see from them, as they render. */
export function provideContext(fn) { provider = typeof fn === 'function' ? fn : null; }
/** Called by the app on every navigation, before the new page renders. */
export function resetContext(r) {
  provider = null; route = r || { view: 'home' }; asked = null;
  if (drawer.isOpen() && !drawer.isDocked()) drawer.close({ silent: true });
  // an open panel redraws its answers' "About" lines against the page now open (not while one streams)
  if (typeof paintLog === 'function' && host() && !S.live) { try { paintLog(false); paintChrome(); } catch (e) { /* drawn on next open */ } }
}
const pageLabel = (r) => {
  if (r.view === 'settings') return SETTINGS.label;
  if (r.view === 'instrument') return `${r.symbol || 'Instrument'}`;
  for (const g of GROUPS) { const p = g.pages.find((x) => x.view === r.view); if (p) return g.symbol ? p.label : (g.pages.length > 1 ? `${g.label}, ${p.label}` : p.label); }
  return 'this page';
};
/** What the reader is told Milo will see: the page actually open, never a stale string. */
export function contextLabel(scope = S.scope) {
  if (scope !== 'auto') return SCOPES[scope];
  const r = route, base = pageLabel(r);
  if (asked && asked.about) return asked.about;
  const extra = (provider && safeCall(provider).focus_label) || '';
  if (extra) return extra;
  return DOSSIER.has(r.view) && r.symbol ? `${r.symbol} Dossier, ${base}` : base;
}
const safeCall = (fn) => { try { return fn() || {}; } catch (e) { console.error(e); return {}; } };
/** The context sent with a question, checked against the route on screen. */
export function buildContext(scope, prevTicker, now = new Date()) {
  const panel = scope === 'auto' && asked && asked.panel ? asked.panel : null;
  const r = route, ctx = scope === 'auto' && provider ? { ...safeCall(provider) } : {};
  // a Dossier page's data must be about the symbol on screen; anything naming another is dropped
  if (DOSSIER.has(r.view) && r.symbol) {
    Object.keys(ctx).forEach((k) => { const v = ctx[k]; const own = v && typeof v === 'object' && !Array.isArray(v) ? (v.symbol || v.ticker) : null; if (own && typeof own === 'string' && own.toUpperCase() !== r.symbol) delete ctx[k]; });
    if (ctx.ticker && ctx.ticker !== r.symbol) ctx.ticker = r.symbol;
  }
  const own = DOSSIER.has(r.view) || r.view === 'instrument' ? r.symbol || null : null;
  // a block about one symbol on a page about none (a Brokerage thesis) names it; it never overrides the page's own
  const ticker = scope === 'auto' ? own || (asked && asked.symbol) || null : null;
  const focus = { scope, view: r.view, view_label: contextLabel(scope), ticker, captured_at: now.toISOString() };
  if (scope === 'auto' && asked && asked.about) focus.asked_from = asked.about;
  if (r.view === 'chart' && scope === 'auto' && ctx.chart) focus.chart = { range: ctx.chart.range, interval: ctx.chart.interval };
  if (prevTicker && ticker && prevTicker !== ticker) focus.previous_ticker = prevTicker;
  delete ctx.focus_label; delete ctx.focus;
  if (scope === 'none') return { focus };
  if (scope === 'market') { const out = { focus }; ['macro', 'sectors', 'indices', 'read'].forEach((k) => { if (ctx[k]) out[k] = ctx[k]; }); return out; }
  return panel ? { ...ctx, panel, focus } : { ...ctx, focus };
}

/* ---------------- history (the classic format) ---------------- */
const newId = () => `c${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
export function loadHistory() { if (!holds(store.state.user)) return []; try { const v = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); return Array.isArray(v) ? v : []; } catch (e) { return []; } }
function saveHistory(list) {
  if (!holds(store.state.user)) return false;
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(list)); return true; } catch (e) {
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, Math.max(1, Math.floor(list.length / 2))))); return true; } catch (e2) { return false; }
  }
}
export const titleOf = (messages) => { const first = (messages || []).find((m) => m.role === 'user'); return (first && String(first.content || '').replace(/\s+/g, ' ').trim().slice(0, 70)) || 'Empty conversation'; };
function persist() {
  if (!S.conv.messages.length) return;
  const messages = S.conv.messages.slice(-MAX_MESSAGES).map((m) => ({ role: m.role, content: String(m.content || '').slice(0, MAX_CHARS) }));
  const list = loadHistory().filter((c) => c.id !== S.conv.id);
  list.unshift({ id: S.conv.id, at: new Date().toISOString(), title: titleOf(messages), ticker: route.symbol || null, messages });
  saveHistory(list.slice(0, MAX_CONVERSATIONS));
}

/* ---------------- state ---------------- */
const blankConv = () => ({ id: newId(), messages: [], lastTicker: null });
const S = { files: [], web: false, deepHint: false, conv: blankConv(), items: [], busy: false, abort: null, scope: 'auto', showHistory: false, showSettings: false, showInfo: false, allowance: null, personas: null, modes: null, draft: '', live: null, mounted: null, panel: null, toEnd: false, symbolAtAsk: null };
// items: what the log shows this session: {kind:'msg', i} for conv.messages[i], or {kind:'note', text}; meta per message index
const meta = new Map();
/* ---------------- attachments (Classic parity B4b; Classic's app.js:46216-46345) ----------------
 * An image or a PDF goes with the next question: PNG, JPEG, GIF, WebP or PDF, up to 4 files of 5 MB each, by the
 * button or by dropping them on the panel. Checked here (type, size, count and the file's own first bytes) and
 * again on the server (app/ai.py attachment_blocks), which says what it turned away. Retention: a file is held in
 * this tab's memory until it is sent or removed, never written to the conversation history (only its name is shown,
 * and only in this tab), sent once with its question to Optic's server, which writes nothing to disk and passes it
 * to the model provider in that request (docs/frontend-v2/CLASSIC-PARITY.md, B4b). */
export const ATTACH_TYPES = { 'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/gif': 'GIF', 'image/webp': 'WebP', 'application/pdf': 'PDF' };
export const ATTACH_MAX_BYTES = 5 * 1024 * 1024, ATTACH_MAX_FILES = 4;
const MAGIC = { 'image/png': ['\x89PNG\r\n\x1a\n'], 'image/jpeg': ['\xff\xd8\xff'], 'image/gif': ['GIF87a', 'GIF89a'], 'application/pdf': ['%PDF-'] };
/** Whether a file's first bytes (a binary string) are the type it claims, as the server checks. */
export function bytesMatch(type, head) {
  if (type === 'image/webp') return head.slice(0, 4) === 'RIFF' && head.slice(8, 12) === 'WEBP';
  return (MAGIC[type] || []).some((m) => head.startsWith(m));
}
/** Why a file cannot go, or '' when it can: its type, its size, the count already attached. */
export function attachProblem({ type, size }, count) {
  if (count >= ATTACH_MAX_FILES) return `only ${ATTACH_MAX_FILES} files can go with one question`;
  if (!ATTACH_TYPES[type]) return 'not a PNG, JPEG, GIF, WebP or PDF';
  if (size > ATTACH_MAX_BYTES) return `larger than the ${ATTACH_MAX_BYTES / 1048576} MB limit`;
  if (!size) return 'the file is empty';
  return '';
}
export const fmtSize = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${Math.round(n / 1024)} KB` : `${n} bytes`);
const persona = () => { try { return localStorage.getItem(PERSONA_KEY) || 'neutral'; } catch (e) { return 'neutral'; } };
const horizon = () => { try { return localStorage.getItem(HORIZON_KEY) || 'auto'; } catch (e) { return 'auto'; } };
const setPref = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } };

/* ---------------- the mascot ---------------- */
// Scout, the classic panel's mascot (components/scout.js, loaded before the app as on the classic page:
// window.OpticScout). He moves on Milo's own events, as he does there, never on a loop of his own: the panel
// opening (one wave, not again within 20 s), typing (a curious tilt, let go 2.5 s after the last key), a question
// sent (an acknowledging wave, then thinking), a search the server reports (a look around), the first words of
// the answer (stillness), the end (a small nod), a failure or a cut-off answer (a concerned face), a stop (a look).
// The welcome figure is a button with the classic guide menu. Since the 2026-10-20 redesign the small figure
// beside "Milo" in the panel's header is the one that reacts to an answer (the brief: a small reserved place by
// the title, the large one only above a new conversation's question). Without the script the panel reads the
// same, without him.
const OS = () => window.OpticScout || null;
const SEARCHING = new Set(['searching the web', 'searching', 'reading and weighing sources']);
const CAN_ASK = 'Ask me anything: about the company or the page you have open, about the market as a whole, or about how Optic works something out. I read Optic\'s own figures for what is on your screen, and look up more of Optic\'s data when a question needs it.';
// the classic panel's starters, word for word; the ones about a symbol only when one is on screen
const EXAMPLES = [
  ['ticker', 'Walk me through the composite score on {T}. Which inputs are carrying it, and where do they disagree?'],
  ['ticker', 'What is the strongest argument AGAINST the current setup on {T}?'],
  ['ticker', 'Give me the bull and bear case for {T} over the next quarter, from the numbers on screen.'],
  ['ticker', 'Is {T}’s seasonality real, or is the sample too small to say?'],
  ['ticker', 'What does the dealer gamma profile imply if {T} breaks its nearest level?'],
  ['ticker', 'How has {T} actually traded after its last eight earnings reports?'],
  [null, 'What is the macro regime saying right now, and which sectors is it favouring?'],
  [null, 'Which currency pairs are worth watching this week, and why?'],
  [null, 'Explain how this terminal computes dealer gamma, and what assumption it is making.'],
  [null, 'Summarise what happened in the market since the last close.'],
  [null, 'How is the paper-trading ledger actually doing, and is the sample big enough to mean anything?'],
  [null, 'Which chart patterns has this terminal measured as actually working, and at what hit rate?'],
];
export const examples = (sym) => EXAMPLES.filter(([need]) => !need || sym).map(([, q]) => q.replace(/\{T\}/g, sym || ''));
// i: the answer whose bust moves, and the state it is in; via: a gesture still to play into that state
const SC = { i: null, state: 'idle', via: null, menu: false, canAsk: false, examples: false, presses: 0, lastWave: 0, quiet: null };
const figure = (size, label = '') => (OS() ? raw(OS().html({ size, label: label ? esc(label) : '' })) : '');
const welcomeEl = (h) => $('.milo-hello .scout', h);
// the figure that reacts to an answer: the small one in the header, beside the title
const headEl = () => (S.panel && document.contains(S.panel) ? $('.milo-id .scout', S.panel) : null);
const replyEl = (h, i) => (i === null || i === undefined ? null : headEl());
/** After the log is drawn: start the welcome figure, and put the moving bust back in its state. */
function scoutAfterPaint() {
  const O = OS(), h = host(); if (!O || !h) return;
  const btn = $('.milo-hello .scout-btn', h); if (btn) { btn.setAttribute('aria-expanded', String(SC.menu)); O.attach(welcomeEl(h), { slot: 'welcome' }); }
  const el = replyEl(h, SC.i); if (!el) return;
  const c = O.attach(el, { slot: 'reply' }), via = SC.via; SC.via = null;
  if (c) c.set(SC.state, via || undefined);
}
function scoutTo(i, state, via) { SC.i = i; SC.state = state; SC.via = via || null; scoutAfterPaint(); }
// typing: the welcome figure, or once a conversation has started the header's figure, unless it is busy with an answer
function scoutListen(v) {
  const O = OS(), h = host(); if (!O || !h) return;
  let el = welcomeEl(h);
  if (!el && !S.busy) el = headEl();
  const c = el && O.attach(el, el.closest('.milo-hello') ? { slot: 'welcome' } : { slot: 'reply' }); if (!c) return;
  clearTimeout(SC.quiet);
  if (!String(v || '').trim()) { if (c.state === 'listening') c.set('idle'); return; }
  if (c.state === 'idle') c.set('listening');
  SC.quiet = setTimeout(() => { if (c.state === 'listening') c.set('idle'); }, 2500);
}
function setMenu(open, refocus) {
  const h = host(); SC.menu = open;
  const menu = h && $('#milo-scout-menu', h), btn = h && $('.milo-hello .scout-btn', h);
  if (menu) menu.hidden = !open;
  if (btn) { btn.setAttribute('aria-expanded', String(open)); if (!open && refocus) btn.focus(); }
  if (open && menu) { const f = $('.scout-mi', menu); if (f) f.focus({ preventScroll: true }); menu.scrollIntoView({ block: 'nearest' }); }
}
// a press: a short wave or, every other time, a curious tilt, and the menu
function scoutPress(btn) {
  if (SC.menu) { setMenu(false, true); return; }
  const c = OS() && OS().attach($('.scout', btn), { slot: 'welcome' }); if (c) c.gesture(SC.presses++ % 2 ? 'curious' : 'wave');
  setMenu(true);
}
// the menu's two actions show the sentence or the examples in the opening; neither sends anything
function scoutAct(act) {
  SC.menu = false;
  if (act === 'ask') SC.canAsk = !SC.canAsk; else SC.examples = !SC.examples;
  paintLog(false);
  const h = host(); if (!h) return;
  const btn = $('.milo-hello .scout-btn', h); if (btn) btn.focus({ preventScroll: true });
  const c = OS() && OS().attach(welcomeEl(h), { slot: 'welcome' });
  if (act === 'examples' && SC.examples) { const ex = $('.milo-examples', h); if (ex) ex.scrollIntoView({ block: 'nearest' }); if (c) c.gesture('point'); } else if (act === 'ask' && SC.canAsk && c) c.gesture('curious');
}
function menuHTML() {
  const m = OS() ? OS().motion() : 'full';
  const radio = (v, l) => html`<button type="button" role="menuitemradio" class="scout-mi" aria-checked="${m === v ? 'true' : 'false'}" data-v2-scout-motion="${v}">${l}</button>`;
  return html`<div class="scout-menu" id="milo-scout-menu" role="menu" aria-label="Milo guide" ${SC.menu ? '' : 'hidden'}>
    <button type="button" role="menuitem" class="scout-mi" data-v2-scout-act="ask">${SC.canAsk ? 'Hide what I can ask' : 'What can I ask?'}</button>
    <button type="button" role="menuitem" class="scout-mi" data-v2-scout-act="examples">${SC.examples ? 'Hide example questions' : 'Show example questions'}</button>
    <div class="scout-menu-sep" role="separator"></div><p class="scout-menu-lab" aria-hidden="true">Animation</p>
    ${radio('full', 'Full')}${radio('subtle', 'Subtle')}${radio('still', 'Still')}</div>`;
}
// Up to three questions for the page open, each sent as it reads when pressed: the redesign's starters "must
// send meaningful requests" (owner, 2026-10-20). Questions taken from the classic examples keep its words; the
// full classic list stays in the guide menu (Show example questions), where a question is drafted, not sent.
const STARTERS = {
  overview: ['What matters most for {T} right now, from the figures on this page?', 'Give me the bull and bear case for {T} over the next quarter, from the numbers on screen.', 'What is the strongest argument AGAINST the current setup on {T}?'],
  chart: ['What is this {T} chart saying about the trend and the nearest levels?', 'What would change the outlook on this chart?', 'How does {T} compare with its closest competitor?'],
  swing: ["What are {T}'s options pricing for the next move?", 'What does the dealer gamma profile imply if {T} breaks its nearest level?', 'Which expiry carries the most risk around the next report?'],
  long: ['Is {T} cheap or expensive against its own history?', 'Give me the bull and bear case for {T} over the next quarter, from the numbers on screen.', "What would have to be true for {T}'s valuation to make sense?"],
  earnings: ['How has {T} actually traded after its last eight earnings reports?', "What are options pricing for {T}'s next report?", "What changed in {T}'s last report?"],
  financials: ["How have {T}'s revenue and margins changed over the last year?", "Is {T}'s cash flow keeping up with its earnings?", 'How much debt does {T} carry against its cash?'],
  news: ['What do the latest headlines mean for {T}?', 'Which of these stories could move {T} the most?', 'What has changed for {T} this week?'],
  instrument: ['What matters most for {T} right now?', 'What is the strongest argument AGAINST the current setup on {T}?', 'How has {T} traded over the last three months?'],
  compare: ['How do these names compare on the figures on screen?', 'Which of these looks strongest, and on what measure?', 'Where do these names disagree most?'],
  market: ['Summarise what happened in the market since the last close.', 'What is the macro regime saying right now, and which sectors is it favouring?', 'Explain how this terminal computes dealer gamma, and what assumption it is making.'],
};
const onSymbol = (r = route) => ((DOSSIER.has(r.view) || r.view === 'instrument') && r.symbol ? r.symbol : null);
/** The opening's starter questions for the page open and what Milo is set to receive. */
export function starters(r = route, scope = S.scope) {
  const sym = onSymbol(r);
  const key = scope !== 'auto' ? 'market' : sym ? (STARTERS[r.view] ? r.view : 'instrument') : (STARTERS[r.view] && !STARTERS[r.view].some((q) => q.includes('{T}')) ? r.view : 'market');
  return STARTERS[key].slice(0, 3).map((q) => q.replace(/\{T\}/g, sym || ''));
}
// "NVDA / Chart": the instrument and the view, for the context selector
export function contextShort(scope = S.scope, r = route) {
  if (scope !== 'auto') return SCOPES[scope];
  if (asked && asked.about) return asked.about;
  const sym = onSymbol(r), page = r.view === 'instrument' ? '' : pageLabel(r);
  return sym ? (page && page !== sym ? `${sym} / ${page}` : sym) : page;
}
const PAGE_WORDS = { chart: 'this {T} chart', swing: "{T}'s options", long: "{T}'s valuation", earnings: "{T}'s earnings", financials: "{T}'s financials", news: "{T}'s news" };
function welcomeLine() {
  const bk = blocked(); if (bk && bk.kind !== 'spent') return bk.kind === 'signin' ? 'Sign in above to ask. The pages themselves need no account.' : bk.text;
  if (S.scope === 'none') return 'Milo will see your question only, not this page.';
  if (S.scope === 'market') return "Milo will see the market's state, not this page.";
  const sym = onSymbol();
  if (sym) return `Ask about ${(PAGE_WORDS[route.view] || '{T}').replace('{T}', sym)}, or start with a question.`;
  return `Ask about the ${pageLabel(route)} page, or anything in the market.`;
}
function openingHTML() {
  const fig = figure('full', 'Milo guide: what to ask, examples and animation');
  const sym = onSymbol();
  // the owner's ask: Milo says hello first, from under Scout, then the question
  return html`<div class="milo-opening"><div class="milo-hello">${fig}${fig ? menuHTML() : ''}</div>
    <p class="milo-hi">Hey, I'm Milo!</p>
    <h3 class="milo-hello-h">What would you like to understand?</h3>
    <p class="milo-hello-say">${welcomeLine()}</p>
    ${SC.canAsk ? html`<p class="milo-can-ask" role="note">${CAN_ASK}</p>` : ''}
    ${blocked() ? '' : html`<ul class="milo-starters" aria-label="Questions to start with">${starters().map((q) => html`<li><button type="button" class="milo-start" data-v2-milo-start="${q}"><span>${q}</span>${icon('arrow')}</button></li>`)}</ul>`}
    ${SC.examples ? html`<div class="milo-examples" role="group" aria-label="Example questions"><p class="t-label">Example questions: pressing one puts it in the box</p>${examples(sym).map((q) => html`<button type="button" class="milo-ex" data-v2-milo-follow="${q}">${q}</button>`)}</div>` : ''}</div>`;
}

export function button(label, { ask, context, symbol, cls = '' } = {}) {
  return html`<button type="button" class="btn btn-milo ${cls}" data-v2-milo="${ask || ''}" data-v2-milo-ctx="${context || ''}" data-v2-milo-sym="${symbol || ''}" ${AVAIL === 'off' ? html`aria-describedby="milo-off-desc"` : ''}>${icon('milo')}${label}</button>`;
}

/* ---------------- whether Milo can answer here ---------------- */
// Every Ask Milo button looked ready on a deployment with no model behind it; the drawer said so only
// after a press (owner's brief, 2026-10-19, item 17). The status is read once on load (a free status
// request, not a model call): when Milo is off, every Milo button is marked so and described, and still
// opens the drawer, which says why and what works without it.
let AVAIL = null;   // 'off' | 'on' | null while unknown
export const miloOff = () => AVAIL === 'off';
export async function checkAvailability() {
  try {
    const r = await api.get('/api/ai-allowance', { ttl: 60000, timeout: 10000 });
    if (!S.allowance) S.allowance = r;
    AVAIL = r && r.ai && r.ai.enabled === false ? 'off' : 'on';
  } catch (e) { AVAIL = null; }
  markButtons();
  // buttons drawn later (a page, a panel's menu) are marked as they appear
  if (AVAIL === 'off' && !observer) {
    let queued = false;
    observer = new MutationObserver(() => { if (queued) return; queued = true; setTimeout(() => { queued = false; if (AVAIL === 'off') markButtons(); }, 50); });
    observer.observe(document.body, { childList: true, subtree: true });
  }
}
let observer = null;
export function markButtons() {
  document.documentElement.dataset.milo = AVAIL || '';
  let note = document.getElementById('milo-off-desc');
  if (AVAIL === 'off' && !note) {
    note = document.createElement('p'); note.id = 'milo-off-desc'; note.hidden = true;
    note.textContent = 'Milo is switched off right now. The button opens Milo, which says why; everything else in Optic works without it.';
    document.body.appendChild(note);
  }
  document.querySelectorAll('[data-v2-milo]').forEach((b) => {
    if (AVAIL === 'off') { if (b.getAttribute('aria-describedby') !== 'milo-off-desc') { b.setAttribute('aria-describedby', 'milo-off-desc'); b.title = 'Milo is switched off right now'; } } else { b.removeAttribute('aria-describedby'); if (b.title === 'Milo is switched off right now') b.removeAttribute('title'); }
  });
}

/* ---------------- allowance and blocking ---------------- */
function blocked() {
  const r = S.allowance;
  if (!r) return null;
  const ai = r.ai || {}, a = r.allowance || {};
  if (ai.enabled === false) return { kind: 'off', text: 'Milo is switched off right now, so it cannot answer questions. Everything else in Optic works without it.' };
  if (a.requires_account && !store.signedIn()) return { kind: 'signin', text: 'Asking Milo needs a free account.', perDay: a.signed_in_allowance };
  if (Number.isFinite(a.allowed) && a.allowed > 0 && a.left === 0) return { kind: 'spent', text: `You have used today's ${a.allowed} questions.${a.next_at ? ` The next one is available ${new Date(a.next_at).toLocaleString('en-US', { weekday: 'short', hour: 'numeric', minute: '2-digit' })}.` : ''}` };
  return null;
}
function allowanceLine() {
  const a = (S.allowance || {}).allowance || {};
  if (blocked()) return '';
  return Number.isFinite(a.left) && Number.isFinite(a.allowed) && a.allowed > 0 ? `${a.left} of ${a.allowed} questions left today.` : '';
}
async function loadAllowance() {
  try { S.allowance = await api.get('/api/ai-allowance', { force: true, timeout: 10000 }); const was = AVAIL; AVAIL = (S.allowance.ai || {}).enabled === false ? 'off' : 'on'; if (was !== AVAIL) markButtons(); } catch (e) { /* the panel still opens */ }
  paintChrome();
}
async function loadChoices() {
  if (!S.personas) { try { S.personas = await api.get('/api/personas', { ttl: 3600000 }); } catch (e) { S.personas = { personas: [{ id: 'neutral', label: 'Neutral analyst' }], horizons: { horizons: [{ id: 'auto', label: 'Auto' }] } }; } }
  if (!S.modes) { try { S.modes = await api.get('/api/knowledge/modes', { ttl: 3600000 }); } catch (e) { S.modes = { modes: [] }; } }
  paintChrome();
}

/* ---------------- drawing ---------------- */
const host = () => S.mounted && document.contains(S.mounted) ? S.mounted : null;
function msgHTML(it) {
  if (it.kind === 'note') return html`<p class="milo-note" role="note">${it.text}</p>`;
  const m = S.conv.messages[it.i] || {}, info = meta.get(it.i) || {};
  // a question worth keeping can be saved, to ask again from Saved research (Classic's msg-save, B4d)
  const savable = String(m.content || '').trim().length > 12;
  if (m.role === 'user') return html`<div class="milo-msg milo-you"><p class="sr">You asked</p><div class="milo-bubble">${m.content}</div>${info.files ? html`<p class="milo-sent-files">${icon('clip')}<span>${info.files.join(', ')}</span></p>` : ''}${savable ? html`<p class="milo-you-acts"><button type="button" class="milo-save" data-v2-milo-save="${it.i}" ${info.saved ? html`disabled` : ''} title="Keep this question in Saved research, to ask again">${info.saved ? 'Saved' : 'Save'}</button></p>` : ''}</div>`;
  const shown = String(m.content || '').replace(/\n\n\[(Stopped by the reader|Cut off): incomplete\]$/, '');
  const { html: body, ups } = renderAnswer(shown, info.symbol || null);
  const live = S.live && S.live.i === it.i;
  // an answer sits on the panel's own surface: its name, what it was about, the text; sources and actions after it
  return html`<article class="milo-msg milo-bot" data-v2-milo-i="${it.i}" aria-label="Milo's answer"><p class="milo-who">Milo</p>
    ${aboutLine(info)}
    ${info.assumed ? html`<p class="milo-assumed">${info.assumed}</p>` : ''}
    ${info.deep ? html`<p class="milo-assumed">Deep research: read from live web sources.</p>` : info.web ? html`<p class="milo-assumed">Web search was on for this answer.</p>` : ''}
    ${info.notSent && info.notSent.length ? html`<p class="milo-not-sent" role="note"><b>Not sent with this question:</b> ${info.notSent.join('; ')}.</p>` : ''}
    <div class="milo-bubble">${raw(body)}</div>
    ${info.ended || /\[(Stopped by the reader|Cut off): incomplete\]$/.test(m.content || '') ? html`<p class="milo-ended" role="note">${(info.ended || (/Stopped by the reader/.test(m.content) ? 'stopped' : 'cut')) === 'stopped' ? 'Stopped by you. This answer is incomplete.' : 'The connection ended before Milo finished. This answer is incomplete.'}</p>` : ''}
    ${live ? '' : html`${ups.length ? html`<div class="milo-ups" role="group" aria-label="Follow-up questions">${ups.map((q) => html`<button type="button" class="milo-up" data-v2-milo-follow="${q}">${q}</button>`)}</div>` : ''}
      <div class="milo-foot">${sourceLists(info)}<div class="milo-acts"><button type="button" class="milo-act-btn" data-v2-milo-copy="${it.i}">${icon('copy')}<span>Copy</span></button>${info.question ? html`<button type="button" class="milo-act-btn" data-v2-milo-again="${it.i}" title="Put the question back in the box">${icon('retry')}<span>Ask again</span></button>` : ''}</div></div>
      <p class="milo-gen">Generated by an AI model from Optic's data. It can be wrong; check the figures against the sources.</p>`}</article>`;
}
// What an answer was about and when it was asked, from the context sent with its question, so an answer about
// AAPL never reads as the answer to a question on the MSFT page the reader has moved to.
export function aboutLine(info, now = route) {
  const f = ((info || {}).context || {}).focus || {};
  const sym = (info || {}).symbol || f.ticker || null, where = f.view_label || '';
  if (!sym && !where) return '';
  const other = sym && now && now.symbol && now.symbol !== sym;
  return html`<p class="milo-about ${other ? 'is-other' : ''}">${sym ? `About ${sym}` : `From ${where}`}${sym && where && where !== sym ? `, asked from ${where}` : ''}${f.captured_at ? `, ${prefs.clock(f.captured_at)}` : ''}${other ? html`. <b>Not about ${now.symbol}, the page now open.</b>` : ''}</p>`;
}
// Every source behind an answer, one fold away: what it cited, what it read, the data it looked up
function sourceLists(info) {
  const cites = info.citations || [], read = info.read || [], got = info.retrieved || [];
  const n = cites.length + read.length + got.length;
  if (!n) return html`<span class="milo-src-none"></span>`;
  return html`<details class="milo-src-all"><summary>Sources (${n})</summary><div class="milo-src-body">
    ${cites.length ? html`<div class="milo-sources"><p class="t-label">Cited</p>${cites.map((c) => (/^https?:\/\//i.test(c.url || '') ? html`<a href="${c.url}" target="_blank" rel="noopener">${c.title || c.url}</a>` : html`<span>${c.title || ''}</span>`))}</div>` : ''}
    ${read.length ? html`<div class="milo-read"><p class="t-label">Sources Milo read (${read.length})</p><ul class="plain">${read.map((r) => html`<li>${/^https?:\/\//i.test(r.url || '') ? html`<a href="${r.url}" target="_blank" rel="noopener">${r.source}</a>` : r.source} <small class="t-muted">${[r.what, r.period].filter(Boolean).join(', ')}</small></li>`)}</ul></div>` : ''}
    ${got.length ? html`<div class="milo-read"><p class="t-label">Data Milo retrieved (${got.length})</p><ul class="plain">${got.map((r) => html`<li>${r.label || ''} <small class="t-muted">${[r.source, r.as_of ? `as of ${prefs.clock(r.as_of)}` : '', r.ok === false ? 'could not be retrieved' : ''].filter(Boolean).join(', ')}</small></li>`)}</ul></div>` : ''}</div></details>`;
}
// History takes the conversation's place while it is open; the composer and its draft stay as they are
function historyHTML() {
  const list = loadHistory();
  return html`<section class="milo-history" id="milo-history" aria-labelledby="milo-hist-h"><div class="milo-hist-head"><h3 id="milo-hist-h">${list.length} saved conversation${list.length === 1 ? '' : 's'}</h3><button type="button" class="btn btn-sm" data-v2-milo-history-close>Back to the conversation</button></div>
    ${list.length ? html`<ul class="plain">${list.map((c) => html`<li class="${c.id === S.conv.id ? 'is-now' : ''}"><button type="button" class="milo-hist-open" data-v2-milo-open="${c.id}" ${c.id === S.conv.id ? html`aria-current="true"` : ''}><span>${c.title}</span><small class="t-muted">${prefs.dayTime(c.at)}, ${(c.messages || []).length} messages${c.ticker ? `, ${c.ticker}` : ''}${c.id === S.conv.id ? ', open now' : ''}</small></button><button type="button" class="icon-btn" data-v2-milo-del="${c.id}" aria-label="Delete ${c.title}" title="Delete">${icon('trash')}</button></li>`)}</ul>` : html`<p class="t-muted">Nothing saved yet.</p>`}
    <p class="asof">Saved in this browser only, never uploaded, and kept apart for each account. The last ${MAX_CONVERSATIONS} conversations are kept.</p></section>`;
}
// The answer settings since the 2026-10-20 redesign (owner's brief, from an approved sketch): the Optic Persona under
// the context bar; the Level and the Timeframe in Response settings, every option kept, each control's own line under
// it. The classic keys and their values are unchanged.
//
// The persona is a menu, like the context bar's (owner, 2026-10-22: "the personalities are very cluttered, fix it",
// choosing the menu over keeping the five on show): one line naming the persona in use; pressed, it lists the five,
// each with what it does, the chosen one ticked. As a row of five (2026-10-20) its names did not fit the panel.
const HZ_SHORT = { auto: 'Auto', day: 'Day', swing: 'Swing', long: 'Long term' };
const curPersona = () => { const ps = (S.personas || {}).personas || []; return ps.find((x) => x.id === persona()) || ps[0] || { id: 'neutral', label: 'Neutral analyst', blurb: '' }; };
function personaHTML() {
  const ps = (S.personas || {}).personas || [], cur = curPersona();
  if (!ps.length) return html`<div class="milo-persona is-loading" aria-hidden="true"></div>`;
  // inside the menu, a radio group: the arrows move the choice; the chosen one is marked by its check
  return html`<div class="milo-persona"><p class="t-label milo-pp-lab" id="milo-pp-lab">Optic Persona</p>
    <details class="menu milo-pp-pick"><summary class="milo-ctx-btn milo-pp-btn" title="How Milo approaches your questions"><span class="sr">Optic Persona: </span><span class="milo-ctx-now">${cur.label}</span>${icon('chev')}</summary>
      <div class="menu-body milo-pp-menu" role="radiogroup" aria-labelledby="milo-pp-lab">${ps.map((x) => html`<button type="button" role="radio" class="milo-ctx-opt milo-pp-opt" aria-checked="${x.id === cur.id ? 'true' : 'false'}" tabindex="${x.id === cur.id ? '0' : '-1'}" data-v2-milo-pp="${x.id}">${x.id === cur.id ? icon('check') : html`<span class="milo-ctx-gap"></span>`}<span><b>${x.label}</b>${x.blurb ? html`<small>${x.blurb}</small>` : ''}</span></button>`)}</div></details></div>`;
}
function settingsHTML() {
  if (!S.showSettings) return '';
  const pp = S.personas || {}, hz = ((pp.horizons || {}).horizons) || [], ms = (S.modes || {}).modes || [];
  const h = hz.find((x) => x.id === horizon()) || hz[0] || null, mode = ms.find((m) => m.id === prefs.knowledge()) || null;
  const list = (rows, head) => (rows && rows.length ? html`<p class="t-label">${head}</p><ul class="plain">${rows.map((r) => html`<li>${r}</li>`)}</ul>` : '');
  // the classic order: the level first, then the timeframe
  return html`<div class="milo-sheet-scrim" data-v2-milo-settings-done aria-hidden="true"></div>
    <div class="milo-settings" id="milo-settings" role="dialog" aria-modal="false" aria-labelledby="milo-set-h">
    <div class="milo-set-head"><h3 id="milo-set-h" tabindex="-1">Response settings</h3><button type="button" class="icon-btn" data-v2-milo-settings-done aria-label="Close Response settings" title="Close">${icon('close')}</button></div>
    ${ms.length ? html`<label class="select milo-level"><span class="t-label">Level</span><select data-v2-milo-mode>${ms.map((m) => html`<option value="${m.id}" ${prefs.knowledge() === m.id ? 'selected' : ''}>${m.label}</option>`)}</select></label>
      ${mode && mode.blurb ? html`<p class="milo-lens-blurb">${mode.blurb}</p>` : ''}` : ''}
    ${hz.length ? html`<div class="milo-hz" role="group" aria-labelledby="milo-hz-lab"><span class="t-label" id="milo-hz-lab">Timeframe</span>
      <div class="seg">${hz.map((x) => html`<button type="button" aria-pressed="${h && x.id === h.id ? 'true' : 'false'}" data-v2-milo-hz="${x.id}" title="${x.blurb || ''}">${HZ_SHORT[x.id] || x.label}</button>`)}</div></div>
    ${h && h.blurb ? html`<p class="milo-lens-blurb">${h.blurb}</p>` : ''}` : ''}
    ${(pp.changes || []).length || (pp.never_changes || []).length ? html`<details class="more-inline milo-pp-foot"><summary>What a persona changes</summary>${list(pp.changes, 'Changes')}${list(pp.never_changes, 'Never changes')}</details>` : ''}
    <p class="asof">A change applies to your next question. Answers already given stay as they were.</p></div>`;
}
// What Milo receives (the page, the market only, or nothing), the data's freshness and the disclosure
const freshness = () => ((S.health && S.health.realtime_chain) ? 'Option chains are real-time; other prices may be delayed.' : 'Prices are delayed up to 15 minutes.');
function attachedLine() {
  if (S.scope === 'none') return 'No page context attached';
  if (S.scope === 'market') return 'The market only attached';
  return `${contextLabel('auto')} attached${asked && asked.panel && asked.panel.figures && asked.panel.figures.length ? `, with its ${asked.panel.figures.length} figures` : ''}`;
}
const placeholder = () => { const sym = S.scope === 'auto' ? onSymbol() : null; return sym ? `Ask about ${sym}` : 'Ask Milo'; };
/* The example question for the page open: Classic put it in the placeholder and Tab drafted it (app.js:44053, 49845).
 * Here a visible "Use this example" button drafts it, so Tab keeps moving focus (owner's amendment 7). Its words
 * are Classic's. */
const EXAMPLE_FOR = { brokerage: 'Where am I concentrated?', paper: 'How concentrated am I?', tracker: 'How concentrated am I?', watchlist: 'What changed this week?', scan: 'What do they have in common?' };
export function exampleAsk(r = route, scope = S.scope) {
  const sym = scope === 'auto' ? onSymbol(r) : null;
  if (sym) return `What would change the picture for ${sym}?`;
  return (scope === 'auto' && EXAMPLE_FOR[r.view]) || 'What is moving the market today?';
}
/* Follow-ups above the box once a symbol's options read is on screen, word for word Classic's (app.js:44016); quiet
 * buttons, not chips (owner's amendment 3), and each only drafts, never sends. */
export const OPTIONS_FOLLOWUPS = ['Why did the ranker pick that strike over a cheaper OTM one?', 'What does the gamma profile imply for a swing long here?', 'Is the flow confirming or fighting the chart?', 'Walk me through the entry zone and what invalidates it.', 'Does the short interest or insider activity change the read?', 'How does the earnings record affect holding through the print?'];
function suggestHTML(empty) {
  if (!empty || S.busy || blocked() || !(S.conv.messages || []).length) return '';
  const follow = route.view === 'swing' && onSymbol() && S.scope === 'auto' ? OPTIONS_FOLLOWUPS : [];
  const eg = exampleAsk();
  return html`${follow.length ? html`<div class="milo-suggest" role="group" aria-label="Follow-up questions">${follow.map((q) => html`<button type="button" class="btn btn-quiet btn-sm" data-v2-milo-follow="${q}">${q}</button>`)}</div>` : ''}
    <p class="milo-eg"><span><span class="t-muted">For example:</span> ${eg}</span><button type="button" class="btn btn-quiet btn-sm" data-v2-milo-follow="${eg}">Use this example</button></p>`;
}
/* ---------------- web search, Deep research and the modes (Classic parity B4c; Classic's app.js:44066, 46425) -------
 * Both cost money and run only when the reader presses Send or Deep research, each saying so on the control. Web
 * search is off until the reader turns it on for this panel (Classic had it on: v2's Milo looks Optic's own data
 * up with its tools, so the web is the reader's choice, never the default spend), and it is not remembered. The
 * modes are Classic's, word for word: each only writes a question into the box. */
export function researchModes(r = route) {
  const t = onSymbol(r);
  if (t && r.view !== 'chart') return [
    { id: 'quick', label: 'Quick read', text: `In three sentences: what matters for ${t} right now, and what would change that view?` },
    { id: 'catalyst', label: 'Catalysts', text: `What are the next catalysts for ${t} (earnings, macro releases, company events)? How has it reacted to similar events before, and what looks priced in?` },
    { id: 'thesis', label: 'Thesis check', text: `Test the thesis on ${t}: give the strongest bull case and the strongest bear case from the loaded data, and the evidence that would prove each one wrong.` },
    { id: 'risk', label: 'Risk review', text: `If I held ${t}, what are the main risks over the next month: event risk, volatility, positioning, and how it moves with the market?` },
    { id: 'deep', label: 'Deep research', deep: true, text: `Deep research on ${t}: what has changed in the last two weeks, with sources, and does it change the thesis?` },
  ];
  if (t) return [
    { id: 'chart', label: 'Read this chart', text: `Read the ${t} chart: the trend, the levels that matter, and what the most recent bars say about momentum.` },
    { id: 'levels', label: 'Key levels', text: `Which support and resistance levels on ${t} matter most, and what happens on a break of each?` },
    { id: 'catalyst', label: 'Catalysts', text: `What upcoming events could move ${t} through those levels?` },
  ];
  if (r.view === 'brokerage') return [
    { id: 'attention', label: 'What needs attention', text: 'What deserves my attention in my linked portfolio this week: concentration, upcoming events and anything that changed?' },
    { id: 'moved', label: 'Why it moved', text: 'Why did my portfolio move today? Separate what you measured from headlines that only match the timing.' },
    { id: 'earnings', label: 'My earnings', text: 'Which earnings affect me this week, and how much of my portfolio do they cover?' },
    { id: 'exposure', label: 'Exposure', text: 'How exposed am I to technology, counting what my ETFs hold, and how complete is that look-through?' },
    { id: 'research', label: 'Research next', text: 'Which of my holdings or risks deserve more research, and why?' },
  ];
  if (r.view === 'tracker' || r.view === 'paper' || r.view === 'watchlist') {
    const what = r.view === 'watchlist' ? 'my watchlist' : 'these positions';
    return [
      { id: 'risk', label: 'Portfolio risk', text: `Review the risk in ${what}: concentration, shared sector and factor exposure, and anything that would hit several names at once.` },
      { id: 'events', label: 'Event risk', text: `Which earnings, dividends or macro releases in the next two weeks affect ${what}, and which matter most?` },
      { id: 'review', label: 'What needs review', text: `Which names in ${what} have changed the most since last week, and which deserve a closer look?` },
    ];
  }
  if (r.view === 'scan') return [
    { id: 'screen', label: 'Explain these results', text: 'What do the names on this screen have in common, and which stand out from the rest?' },
    { id: 'pick', label: 'Compare the leaders', text: 'Compare the top few names here on momentum, valuation and event risk. Which are worth a closer look?' },
  ];
  return [
    { id: 'quick', label: 'Market read', text: 'What is driving the market today, and what would change the picture this week?' },
    { id: 'catalyst', label: 'This week’s catalysts', text: 'Which economic releases and earnings this week matter most, and what outcome is the market positioned for?' },
    { id: 'deep', label: 'Deep research', deep: true, text: 'Give me a sourced brief on the market right now: direction, drivers, notable movers, and what traders are watching.' },
  ];
}
const MARKET_BRIEF = 'Give me a live sourced brief on the overall market right now: index direction, what is driving it, notable movers, and the macro releases or events traders are positioned around.';
function toolsHTML() {
  if (blocked() && (blocked() || {}).kind !== 'spent') return '';
  const sym = onSymbol(), busy = S.busy;
  return html`<div class="milo-tools" role="group" aria-label="How Milo answers">
    <details class="menu milo-modes"><summary class="btn btn-sm btn-quiet" ${busy ? html`aria-disabled="true"` : ''}>Modes${icon('down')}</summary><div class="menu-body" role="group" aria-label="Research modes">
      <p class="menu-help">Each writes a question into the box. Nothing is sent until you press Send.</p>
      ${researchModes().map((m) => html`<button type="button" class="milo-mode" data-v2-milo-mode="${m.id}" data-v2-milo-follow="${m.text}" ${m.deep ? html`data-deep="1"` : ''}><b>${m.label}</b><span>${m.text}</span></button>`)}</div></details>
    <button type="button" class="btn btn-sm btn-quiet milo-web" data-v2-milo-web aria-pressed="${S.web ? 'true' : 'false'}" ${busy ? 'disabled' : ''} title="Milo also searches the web for your next questions. Each search adds to what a question costs. Off again when this panel closes.">${icon(S.web ? 'check' : 'search')}<span>Search the web</span></button>
    <button type="button" class="btn btn-sm btn-quiet milo-deep ${S.deepHint ? 'is-suggested' : ''}" data-v2-milo-deep ${busy ? 'disabled' : ''} title="Researches the question in the box${sym ? `, or ${sym}` : ', or the market'}, with live web sources. Uses one Milo question and several web searches.">Deep research</button>
  </div>`;
}
function paintTools() { const h = host(); if (!h) return; const slot = $('[data-v2-milo-tools]', h); if (!slot) return; const open = slot.querySelector('details.milo-modes[open]'); draw(slot, toolsHTML()); if (open) { const d = slot.querySelector('details.milo-modes'); if (d) d.open = true; } }
function filesHTML() {
  if (!S.files.length) return '';
  return html`<ul class="milo-files" aria-label="Files to send with your question">${S.files.map((f, i) => html`<li class="milo-file ${f.error ? 'is-bad' : ''}">
      ${f.thumb ? html`<img data-v2-milo-thumb="${i}" alt="">` : html`<span class="milo-file-kind" aria-hidden="true">${ATTACH_TYPES[f.type] || 'File'}</span>`}
      <span class="milo-file-meta"><span class="milo-file-name">${f.name}</span><span class="milo-file-size">${f.error ? `Not sent: ${f.error}` : fmtSize(f.size)}</span></span>
      <button type="button" class="icon-btn" data-v2-milo-unattach="${i}" aria-label="Remove ${f.name}" title="Remove">${icon('close')}</button></li>`)}</ul>
    <p class="milo-files-note">Sent with your next question to Milo's model provider. Optic does not keep them.</p>`;
}
function paintFiles() {
  const h = host(); if (!h) return; draw($('[data-v2-milo-files]', h), filesHTML());
  // the reader's own image, from its own file: set here, as the template turns every data: address into "#"
  h.querySelectorAll('[data-v2-milo-thumb]').forEach((im) => { const f = S.files[Number(im.dataset.v2MiloThumb)]; if (f && f.thumb) im.src = f.thumb; }); const b = $('[data-v2-milo-attach]', h); if (b) b.disabled = S.busy || S.files.filter((f) => !f.error).length >= ATTACH_MAX_FILES; }
const readFile = (file) => new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(String(r.result || '')); r.onerror = () => bad(new Error('unreadable')); r.readAsDataURL(file); });
async function addFiles(list) {
  for (const file of [...(list || [])]) {
    const good = S.files.filter((f) => !f.error).length;
    const f = { name: String(file.name || 'attachment').slice(0, 120), type: file.type || '', size: file.size || 0, data: null, thumb: null, error: attachProblem({ type: file.type || '', size: file.size || 0 }, good) };
    if (!f.error) {
      try {
        const url = await readFile(file), data = url.slice(url.indexOf(',') + 1);
        const head = atob(data.slice(0, 16));
        if (!bytesMatch(f.type, head)) f.error = `not a ${ATTACH_TYPES[f.type]} file, whatever its name says`;
        else { f.data = data; if (f.type.startsWith('image/')) f.thumb = url; }
      } catch (e) { f.error = 'the file could not be read'; }
    }
    S.files.push(f);
  }
  paintFiles();
  const bad = S.files.filter((f) => f.error);
  if (bad.length) announce(`${bad.length === 1 ? `${bad[0].name} cannot be sent: ${bad[0].error}` : `${bad.length} files cannot be sent`}.`);
}
function paintSuggest() {
  const h = host(); if (!h) return;
  const slot = $('[data-v2-milo-suggest]', h), ta = $('#milo-q', h); if (!slot) return;
  draw(slot, suggestHTML(!ta || !ta.value.trim()));
}
function ctxHTML() {
  const opts = [['auto', `This page: ${contextLabel('auto')}`, 'The figures on the page you have open.'], ['market', SCOPES.market, "The market's state: indices, sectors and the macro read. No company."], ['none', SCOPES.none, 'Your question and this conversation only.']];
  return html`<div class="milo-ctx"><div class="milo-ctx-l">
      <details class="menu milo-ctx-pick"><summary class="milo-ctx-btn" title="What Milo receives with your question"><span class="sr">What Milo receives: </span><span class="milo-ctx-now">${contextShort()}</span>${icon('chev')}</summary>
        <div class="menu-body milo-ctx-menu" role="group" aria-label="What Milo receives">${opts.map(([k, l, d]) => html`<button type="button" class="milo-ctx-opt" aria-pressed="${S.scope === k ? 'true' : 'false'}" data-v2-milo-scope="${k}">${S.scope === k ? icon('check') : html`<span class="milo-ctx-gap"></span>`}<span><b>${l}</b><small>${d}</small></span></button>`)}</div></details>
      <p class="milo-ctx-meta"><span>${freshness()} Not financial advice.</span><button type="button" class="milo-info-btn" data-v2-milo-info aria-expanded="${S.showInfo ? 'true' : 'false'}" aria-controls="milo-info" aria-label="About Milo's data and its limits" title="About Milo's data and its limits">${icon('info')}</button></p></div>
    <button type="button" class="btn btn-quiet btn-sm milo-set-btn" data-v2-milo-settings aria-expanded="${S.showSettings ? 'true' : 'false'}" aria-controls="milo-settings" title="Response settings: Level and Timeframe">${icon('sliders')}<span class="milo-set-l">Response settings</span></button>
    ${settingsHTML()}</div>
    ${S.showInfo ? html`<div class="milo-info" id="milo-info"><p>${freshness()} Milo reads Optic's own figures for the page you have open, and looks up more of Optic's data when a question needs it.</p>${miloNotice()}${allowanceLine() ? html`<p>${allowanceLine()}</p>` : ''}</div>` : ''}`;
}
// The page open is another symbol's than the conversation's: said before a question is sent, not after
function movedHTML() {
  const now = onSymbol();
  if (!S.items.length || S.scope !== 'auto' || !S.conv.lastTicker || !now || now === S.conv.lastTicker) return '';
  return html`<p class="milo-moved" role="note">This conversation is about ${S.conv.lastTicker}. Your next question will be about ${now}, and Milo is told the change. <button type="button" class="textlink" data-v2-milo-new>Start a new conversation</button></p>`;
}
// What the reader can do here, said first when they cannot ask (beginner brief item 10): Milo being on is the
// service; whether this reader may ask is their access. A guest sees that an account is needed, the way to one,
// what it unlocks and what works without it, before any setting.
function accessHTML(b) {
  if (!b) return '';
  if (b.kind === 'signin') return html`<div class="milo-guest" role="status"><p><b>${b.text}</b> Milo is available. A free account lets you ask it${isFinite(b.perDay) && b.perDay > 0 ? ` ${b.perDay} questions a day` : ''} about any company or page, and keeps your watchlists on every device.</p>
    <div class="cluster"><a class="btn btn-primary btn-sm" href="#/signin">Sign in or create an account</a></div>
    <p class="milo-guest-sub">Without an account you can search companies, read every page, follow companies in this browser, and tap an underlined term for its meaning.</p></div>`;
  return html`<div class="state milo-block" role="status"><p>${b.text}</p></div>`;
}
function chromeHTML() {
  const b = blocked();
  return html`${accessHTML(b)}${ctxHTML()}${movedHTML()}${personaHTML()}`;
}
function logHTML() {
  if (S.showHistory) return historyHTML();
  if (!S.items.length) return openingHTML();
  return html`${S.items.map(msgHTML)}`;
}
function paintChrome() { const h = host(); if (!h) return; draw($('.milo-chrome', h), chromeHTML()); paintHead(); paintForm(); }
// the header's buttons (outside the panel's body): whether history is open, and no new conversation mid-answer
function paintHead() {
  const hb = S.panel && $('.drawer-head [data-v2-milo-history]', S.panel), nb = S.panel && $('.drawer-head [data-v2-milo-new]', S.panel);
  if (hb) { hb.setAttribute('aria-expanded', String(!!S.showHistory)); hb.classList.toggle('is-on', !!S.showHistory); }
  if (nb) { nb.disabled = S.busy; nb.title = S.busy ? 'New conversation (stop the answer first)' : 'New conversation'; }
}
function paintLog(stick = true) {
  const h = host(); if (!h) return;
  const log = $('.milo-log', h), pinned = !log || log.scrollHeight - log.scrollTop - log.clientHeight < 60;
  draw(log, logHTML());
  mountAnswerCharts(log); mountAnswerFigures(log);
  // the reader's own question always comes into view; new output follows only a reader already at the end
  if (S.toEnd || (stick && pinned)) log.scrollTop = log.scrollHeight;
  if (S.showHistory || !S.items.length) log.scrollTop = 0;
  S.toEnd = false;
  scoutAfterPaint(); syncLatest();
}
// "Latest": back to the end of the conversation, offered only when the reader has scrolled away from it
function syncLatest() {
  const h = host(); if (!h) return;
  const log = $('.milo-log', h), b = $('[data-v2-milo-latest]', h); if (!log || !b) return;
  b.hidden = !(S.items.length && !S.showHistory && log.scrollHeight - log.scrollTop - log.clientHeight > 160);
}
function grow(ta) {
  if (!ta) return;
  ta.style.height = 'auto';
  const max = parseFloat(getComputedStyle(ta).maxHeight) || 160;
  ta.style.height = `${Math.min(ta.scrollHeight + 2, max)}px`;
  ta.style.overflowY = ta.scrollHeight + 2 > max ? 'auto' : 'hidden';
}
function paintForm() {
  const h = host(); if (!h) return;
  const b = blocked(), send = $('[data-v2-milo-send]', h), stop = $('[data-v2-milo-stop]', h), ta = $('#milo-q', h);
  const hadFocus = document.activeElement;
  if (send) { send.disabled = S.busy || !!b; send.hidden = S.busy; }
  if (stop) stop.hidden = !S.busy;
  // the send control turns into Stop while Milo answers; focus follows it rather than falling to the page
  if (S.busy && hadFocus === send && stop) stop.focus({ preventScroll: true });
  if (!S.busy && hadFocus === stop && ta) ta.focus({ preventScroll: true });
  if (ta) { ta.disabled = !!b && b.kind !== 'spent'; ta.placeholder = placeholder(); }
  // no conversation form that cannot be used: hidden while asking needs an account or Milo is off
  const fm = $('.milo-form', h); if (fm) fm.hidden = !!b && b.kind !== 'spent';
  const at = $('#milo-attached span', h); if (at) at.textContent = attachedLine();
  const f = $('.milo-form', h); if (f) f.dataset.state = !S.busy ? 'idle' : S.live && S.live.text ? 'streaming' : 'sending';
  const al = $('#milo-allow', h); if (al) al.textContent = !S.busy ? allowanceLine() : S.live && S.live.text ? 'Milo is answering' : 'Sending';
  paintHead();
  paintSuggest();
  paintFiles();
  paintTools();
}
const draw = (el, tpl) => { if (el) render(el, tpl); };

// the answer still streaming: settled paragraphs drawn, the tail as plain text
let liveFrame = null;
function paintLive() {
  if (liveFrame) return;
  liveFrame = requestAnimationFrame(() => {
    liveFrame = null;
    const h = host(), L = S.live; if (!h || !L) return;
    const node = $(`[data-v2-milo-i="${L.i}"] .milo-bubble`, h); if (!node) { paintLog(); return; }
    const text = L.text, cut = text.lastIndexOf('\n\n');
    const settled = cut > 0 ? renderAnswer(text.slice(0, cut), L.symbol).html : '';
    node.innerHTML = `${settled}<p class="milo-tail">${esc(streamingTail(cut > 0 ? text.slice(cut + 2) : text))}</p>${L.status ? `<p class="milo-status" role="status">${esc(L.status)}…</p>` : ''}`;
    mountAnswerCharts(node); mountAnswerFigures(node);
    const log = $('.milo-log', h); if (log && log.scrollHeight - log.scrollTop - log.clientHeight < 120) log.scrollTop = log.scrollHeight;
    syncLatest(); paintForm();
  });
}

/* ---------------- figures inside answers: Optic's own data, never the model's numbers ---------------- */
function mountAnswerFigures(root) {
  root.querySelectorAll('[data-v2-milo-fig]:not([data-mounted])').forEach((fig) => {
    fig.dataset.mounted = '1';
    const kind = fig.dataset.v2MiloFig, sym = fig.dataset.sym;
    FF.build(kind, sym).then((f) => {
      if (!document.contains(fig)) return;
      fig.removeAttribute('aria-busy');
      if (f.missing) { render(fig, html`<p class="milo-fig-none" role="note">No figure: ${f.missing}</p>`); return; }
      render(fig, html`<figcaption><p class="milo-fig-h">${f.title}</p><p class="fv-take">${f.take}</p>${f.keyHTML || ''}<p class="fv-unit">${f.unit}. From ${f.source}; drawn by Optic, not by Milo.</p></figcaption>
        ${f.html ? raw(f.html) : html`<div class="chart-slot" data-chart="fig"></div>`}${f.table}`);
      if (f.chart) mountCharts(fig, { fig: f.chart });
    });
  });
}
/* ---------------- charts inside answers ---------------- */
const chartCache = new Map();
function mountAnswerCharts(root) {
  root.querySelectorAll('[data-v2-milo-chart]:not([data-mounted])').forEach((fig) => {
    fig.dataset.mounted = '1';
    const sym = fig.dataset.v2MiloChart, span = fig.dataset.span, key = `${sym} ${span}`, plot = $('.milo-chart-plot', fig);
    if (!chartCache.has(key)) chartCache.set(key, api.get(`/api/take-chart/${encodeURIComponent(sym)}?span=${encodeURIComponent(span)}`, { ttl: 600000, timeout: 30000 }).catch(() => null));
    chartCache.get(key).then((tc) => {
      if (!document.contains(plot)) return;
      const c = tc && tc.available ? tc.chart : null;
      if (!c || !(c.close || []).length) { plot.innerHTML = `<p class="t-muted">No price history for ${esc(sym)}.</p>`; return; }
      const levels = [...(tc.supports || []).slice(0, 2), ...(tc.resistances || []).slice(0, 1)].map((l) => l.price).filter(Number.isFinite);
      plot.innerHTML = '<div class="chart-slot" data-chart="take"></div>';
      mountCharts(plot, { take: (w) => lineChart(c.dates.map((d, i) => ({ d, c: c.close[i] })), { w, h: 220, label: `${sym} daily closes`, overlays: levels.map((v) => ({ values: c.dates.map(() => v), cls: 'c0' })), summary: `${sym} daily closes over ${tc.span_words || span}, through ${tc.as_of || ''}${levels.length ? `, with support and resistance at ${levels.map((v) => v.toFixed(2)).join(', ')}` : ''}.` }) });
      const cap = $('figcaption', fig); if (cap) cap.textContent = `${sym}, daily closes over ${tc.span_words || span}, through ${tc.as_of || ''}. Dashed: support and resistance, where price turned before. Source: Yahoo Finance.`;
    });
  });
}

/* ---------------- sending ---------------- */
function offlineOr(status) {
  if (navigator.onLine === false) return 'You appear to be offline. The question is still in the box: send it again once you are back on.';
  return `Milo did not respond${status ? ` (HTTP ${status})` : ''}. Wait a moment and send it again; your question is still in the box.`;
}
export async function send(text, { deep = false } = {}) {
  text = String(text || '').trim();
  const sym0 = onSymbol();
  // Deep research may run on an empty box: on the symbol open, or the market (Classic's runResearch)
  if (deep && !text) text = sym0 ? `Deep research: ${sym0}` : 'Deep research: the market';
  if (!text || S.busy || blocked()) return;
  S.deepHint = false;
  const h = host(), ta = h && $('#milo-q', h);
  const context = buildContext(S.scope, S.conv.lastTicker);
  const focusTicker = context.focus.ticker;
  if (context.focus.previous_ticker) S.items.push({ kind: 'note', text: `Now asking about ${focusTicker}. The earlier answers were about ${context.focus.previous_ticker}, and Milo is told so.` });
  S.conv.messages.push({ role: 'user', content: text }); S.items.push({ kind: 'msg', i: S.conv.messages.length - 1 });
  const going = S.files.filter((f) => f.data && !f.error), attachments = going.map((f) => ({ name: f.name, media_type: f.type, data: f.data }));
  if (going.length) meta.set(S.conv.messages.length - 1, { files: going.map((f) => f.name) });
  S.files = [];
  if (focusTicker) S.conv.lastTicker = focusTicker;
  const ai = S.conv.messages.length; // index the answer will take
  S.conv.messages.push({ role: 'assistant', content: '' }); S.items.push({ kind: 'msg', i: ai });
  meta.set(ai, { question: text, symbol: focusTicker || route.symbol || null, context, deep, web: !deep && !!S.web });
  S.busy = true; S.live = { i: ai, text: '', status: 'Reading what is on your screen', symbol: focusTicker || route.symbol || null };
  if (ta) { ta.value = ''; grow(ta); } S.draft = ''; S.showHistory = false; S.showSettings = false; S.toEnd = true;
  paintChrome(); paintLog(); paintForm(); paintLive();
  scoutTo(ai, 'thinking', 'ack');
  const ctl = new AbortController(); S.abort = ctl;
  let finished = false, ended = '', failed = null;
  try {
    const askedText = /^Deep research: /.test(text) && deep ? null : text;
    const res = await fetch(deep ? '/api/research' : '/api/chat', {
      method: 'POST', credentials: 'same-origin', signal: ctl.signal,
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', 'X-Optic-CSRF': (document.cookie.match(/(?:^|; )optic_csrf=([^;]*)/) || [])[1] || '' },
      body: JSON.stringify(deep
        ? { ticker: focusTicker || sym0 || null, question: askedText || (focusTicker || sym0 ? null : MARKET_BRIEF), context }
        : { messages: S.conv.messages.slice(0, ai).map((m) => ({ role: m.role, content: m.content })), context, web: !!S.web, attachments, persona: persona(), mode: prefs.knowledge(), horizon: horizon() }),
    });
    if (!res.ok || !res.body) {
      let d = null; try { d = await res.json(); } catch (e) { /* not json */ }
      const msg = (d && (d.detail || d.message)) || '';
      failed = res.status === 401 ? { signin: true, text: typeof msg === 'string' && msg ? msg : 'Milo needs a free account. Sign in to ask.' }
        : res.status === 429 ? { text: typeof msg === 'string' && msg ? msg : 'No questions left for now.' }
          : { text: (typeof msg === 'string' && msg) || (res.status >= 502 && res.status <= 530 ? offlineOr(res.status) : `Milo did not answer (HTTP ${res.status}).`) };
    } else {
      const reader = res.body.getReader(), dec = new TextDecoder(); let buf = '';
      for (;;) {
        let step;
        try { step = await reader.read(); } catch (e) { ended = ctl.signal.aborted ? 'stopped' : 'cut'; break; } // eslint-disable-line no-await-in-loop
        if (step.done) break;
        buf += dec.decode(step.value, { stream: true });
        const chunks = buf.split('\n\n'); buf = chunks.pop();
        for (const c of chunks) {
          let ev = 'message', data = '';
          c.split('\n').forEach((line) => { if (line.startsWith('event: ')) ev = line.slice(7).trim(); else if (line.startsWith('data: ')) data += line.slice(6); });
          if (!data) continue;
          let p; try { p = JSON.parse(data); } catch (e) { continue; }
          if (ev === 'delta') { S.live.text += p.text || ''; S.live.status = ''; S.conv.messages[ai].content = S.live.text; paintLive(); if (SC.i === ai && SC.state !== 'streaming') scoutTo(ai, 'streaming'); }
          else if (ev === 'status') { const w = STEP_WORDS[String(p.state || '')] || String(p.state || '').replace(/^./, (x) => x.toUpperCase()); S.live.status = w; paintLive(); if (SC.i === ai && SC.state !== 'streaming') scoutTo(ai, SEARCHING.has(String(p.state || '')) ? 'searching' : 'thinking'); }
          else if (ev === 'attachments') { const m = meta.get(ai); if (m && Array.isArray(p.problems)) m.notSent = p.problems.map(String).slice(0, 5); }
          else if (ev === 'assumed') { const hz = (((S.personas || {}).horizons || {}).horizons || []).find((x) => x.id === p.horizon); if (hz && p.horizon_source === 'question' && p.horizon !== horizon()) meta.get(ai).assumed = `Answered for a ${hz.label.toLowerCase()} timeframe, from your question. Your setting is unchanged.`; }
          else if (ev === 'error') { finished = true; failed = { text: p.message || 'Milo could not answer.' }; }
          else if (ev === 'done') { finished = true; Object.assign(meta.get(ai), { citations: p.sources || p.citations || [], read: Array.isArray(p.read) ? p.read : [], retrieved: Array.isArray(p.retrieved) ? p.retrieved : [] }); }
        }
      }
      if (!finished && !ended && !failed) ended = ctl.signal.aborted ? 'stopped' : 'cut';
    }
  } catch (e) {
    if (ctl.signal.aborted) ended = 'stopped';
    else failed = { text: offlineOr('') };
  }
  const reply = S.live ? S.live.text : '';
  S.live = null; S.busy = false; S.abort = null;
  if (failed && !reply) {
    // nothing came back: take the exchange out, and give the question back
    S.conv.messages.splice(ai - 1, 2); S.items = S.items.filter((it) => !(it.kind === 'msg' && it.i >= ai - 1)); meta.delete(ai); meta.delete(ai - 1);
    S.items.push({ kind: 'note', text: failed.text });
    if (going.length && !S.files.length) S.files = going;   // and the files with it
    S.draft = text; const box = host() && $('#milo-q', host()); if (box && !box.value.trim()) { box.value = text; grow(box); }
    if (failed.signin) loadAllowance();
    SC.i = null;
  } else if (!reply && ended === 'stopped') {
    S.conv.messages.splice(ai - 1, 2); S.items = S.items.filter((it) => !(it.kind === 'msg' && it.i >= ai - 1)); meta.delete(ai);
    S.items.push({ kind: 'note', text: 'Stopped before Milo answered.' });
    SC.i = null;
  } else {
    if (failed || ended === 'cut') Object.assign(SC, { i: ai, state: 'error', via: null });
    else if (ended === 'stopped') Object.assign(SC, { i: ai, state: 'idle', via: 'look' });
    else Object.assign(SC, { i: ai, state: 'idle', via: reply.trim() ? 'nod' : null });
    if (failed) S.items.push({ kind: 'note', text: failed.text });
    if (ended) { meta.get(ai).ended = ended; S.conv.messages[ai].content = `${reply}\n\n[${ended === 'stopped' ? 'Stopped by the reader' : 'Cut off'}: incomplete]`; }
    persist();
  }
  paintLog(); paintForm(); loadAllowance();
  // the state, for a screen reader: the log reads the answer itself
  announce(failed ? 'Milo could not answer. Your question is back in the box.' : ended === 'stopped' ? 'Stopped. The answer is incomplete.' : ended === 'cut' ? 'The answer was cut off.' : 'Milo has answered.');
}
export function stop() { if (S.abort) S.abort.abort(); }

/* ---------------- the fair-value model's proposal card (Classic parity B7d; Classic valuation.js miloCardPress) ----------------
 * Milo proposes a change; the card runs Optic's engine to show the effect before anything changes, and Apply changes
 * only the reader's working assumptions on screen, never a saved model, with Undo after. The open model registers its
 * preview, apply and undo here (pages/dcf.js), so this module does not import the page. */
let VALUATION = null;
export function registerValuation(v) { VALUATION = v; }
export function unregisterValuation(v) { if (VALUATION === v) VALUATION = null; }
async function valuationPress(btn) {
  const card = btn.closest('.milo-val'); if (!card) return;
  let a = null; try { a = JSON.parse(card.dataset.v2MiloVal); } catch (e) { return; }
  const out = $('.milo-act-result', card), say = (text, ok) => { if (out) { out.textContent = text; out.className = `milo-act-result${ok === false ? ' down' : ''}`; } };
  const msg = btn.closest('[data-v2-milo-i]'), asked = ((msg && meta.get(Number(msg.dataset.v2MiloI))) || {}).symbol || null;
  if (!VALUATION || !VALUATION.ready()) { say(`Open ${asked ? `${asked}'s` : 'the company\'s'} Investing tab first: the card works on the fair-value model on screen.`, false); return; }
  if (asked && VALUATION.sym() !== asked) { say(`This was proposed for ${asked}'s model, and ${VALUATION.sym()}'s is on screen. Open ${asked}'s Investing tab to try it.`, false); return; }
  if (btn.hasAttribute('data-v2-milo-val-undo')) {
    let prev = null; try { prev = JSON.parse(card.dataset.prev || 'null'); } catch (e) { prev = null; }
    btn.disabled = true; await VALUATION.undo(prev); say('Put back as it was.'); btn.remove();
    const ap = $('[data-v2-milo-val-apply]', card); if (ap) { ap.textContent = 'Apply to my working model'; ap.disabled = false; ap.focus(); }
    return;
  }
  if (btn.hasAttribute('data-v2-milo-val-preview')) {
    say('Running the model…');
    try { const r = await VALUATION.preview(a.changes); say(r.text, r.ok); const ap = $('[data-v2-milo-val-apply]', card); if (ap) ap.disabled = !r.ok; }
    catch (err) { say(`It did not run: ${err.message || 'try again'}.`, false); }
    return;
  }
  if (btn.hasAttribute('data-v2-milo-val-apply')) {
    btn.disabled = true;
    try {
      card.dataset.prev = JSON.stringify(await VALUATION.apply(a.changes));
      say('Applied to your working assumptions. Saved models are unchanged.'); btn.textContent = 'Applied';   // a dimmed gold still reads as pressable
      if (!$('[data-v2-milo-val-undo]', card)) btn.insertAdjacentHTML('afterend', '<button type="button" class="btn btn-sm" data-v2-milo-val-undo>Undo</button>');
      const u = $('[data-v2-milo-val-undo]', card); if (u) u.focus();
    } catch (err) { btn.disabled = false; say(`It was not applied: ${err.message || 'try again'}.`, false); }
  }
}

/* ---------------- actions in answers ---------------- */
const chartRange = { '1m': '1M', '3m': '3M', '6m': '6M', '1y': '1Y', all: 'All' };
function levelGrounded(price, ctx) {
  const out = []; const LEVELISH = /(level|support|resistance|pivot|sma|ema|fib|retrace|poc|vah|val|wall|flip|high|low|close|price|target|stop|entry|r1|r2|r3|s1|s2|s3)/i;
  const walk = (v, key, d) => { if (d > 6 || v === null || v === undefined) return; if (typeof v === 'number') { if (LEVELISH.test(key) && v > 0) out.push(v); return; } if (Array.isArray(v)) { v.slice(0, 60).forEach((x) => walk(x, key, d + 1)); return; } if (typeof v === 'object') Object.keys(v).forEach((k) => walk(v[k], k, d + 1)); };
  walk(ctx || {}, '', 0);
  return out.some((v) => Math.abs(v - price) / price <= 0.0025);
}
async function runAction(a, card, i) {
  const sym = route.symbol || (meta.get(i) || {}).symbol || null;
  const say = (text, ok) => { const r = $('.milo-act-result', card); if (r) { r.textContent = text; r.className = `milo-act-result ${ok ? 'up' : 'down'}`; } if (ok) card.querySelectorAll('button').forEach((b) => { b.disabled = true; }); };
  const slug = { overview: '', chart: '/chart', options: '/options', investing: '/investing', earnings: '/earnings', financials: '/financials', news: '/news' };
  if (a.kind === 'open') { router.go(`#/${a.sym}${slug[a.section]}`); return; }
  if (a.kind === 'compare') { router.go(`#/compare?t=${a.syms.join(',')}`); return; }
  if (a.kind === 'valuation') { if (!sym) { say('Open a company first; the model needs a symbol.', false); return; } router.go(`#/${sym}/investing`); return; }
  if (a.kind === 'screen') { router.go(`#/scan?q=${encodeURIComponent(a.words)}`); return; }
  if (a.kind === 'chart' || a.kind === 'indicator') {
    if (!sym) { say('Load a ticker first; the chart needs a symbol.', false); return; }
    if (a.kind === 'chart') { router.go(`#/${sym}/chart?interval=${a.interval}&range=${chartRange[a.range]}`); return; }
    const spec = STUDIES[a.id][1];
    if (!spec) { say(`${STUDIES[a.id][0]} is on the classic chart.`, false); const r = $('.milo-act-result', card); if (r) r.insertAdjacentHTML('beforeend', ` <a href="${CLASSIC}#/${encodeURIComponent(sym)}/chart">Open it there</a>`); return; }
    router.go(`#/${sym}/chart?show=${encodeURIComponent(spec)}`); return;
  }
  if (a.kind === 'watch') {
    const named = a.list ? (store.state.lists || []).find((l) => l.name.toLowerCase() === a.list.toLowerCase()) : null;
    const target = named || store.activeList();
    if (target && target.symbols.includes(a.sym)) { say(`${a.sym} is already on ${target.name}.`, true); return; }
    try { await store.follow(a.sym, target ? target.id : undefined); } catch (e) { say(e.message && e.kind === 'limit' ? e.message : api.explain(e, 'The change'), false); return; }
    say(`Added ${a.sym} to ${target ? target.name : 'your watchlist'}.${a.list && !named ? ` There is no list called "${a.list}", so it went on your current list.` : ''}`, true); return;
  }
  if (a.kind === 'save') {
    const r = await saveQuestion({ question: a.question, symbol: sym });
    say(r.text, r.ok); return;
  }
  if (a.kind === 'level') {
    if (route.view !== 'chart' || !route.symbol) { say('Open the chart first; a level is drawn on the chart on screen.', false); return; }
    if (!levelGrounded(a.price, (meta.get(i) || {}).context)) { say(`${a.price.toFixed(2)} is not one of the levels Optic computed for this chart, so it was not drawn.`, false); return; }
    if (!holds(store.state.user)) { say('It was not drawn.', false); return; }
    try {
      const all = JSON.parse(localStorage.getItem('optic.chart.drawings.v2') || '{}'), list = Array.isArray(all[route.symbol]) ? all[route.symbol] : [];
      if (list.some((x) => x.origin === 'milo' && x.kind === 'hline' && Math.abs(x.points[0].p - a.price) / a.price < 0.0005)) { say(`That level is already on the ${route.symbol} chart.`, true); return; }
      list.push({ id: `d${Date.now().toString(36)}`, kind: 'hline', points: [{ t: Date.parse(new Date().toISOString().slice(0, 10)), p: a.price }], color: 'accent', width: 1.6, origin: 'milo', text: a.note });
      all[route.symbol] = list; localStorage.setItem('optic.chart.drawings.v2', JSON.stringify(all));
      router.go(`#/${route.symbol}/chart`);
    } catch (e) { say('It was not drawn.', false); }
  }
}

/* ---------------- the panel ---------------- */
// A drawer of its own (ui/drawer.js makeDrawer), so another one (an answer's evidence, the account sheet) opens over
// it rather than in its place.
const drawer = makeDrawer({ cls: 'drawer-milo', titleId: 'milo-title' });
export const isOpen = () => drawer.isOpen();
export const isDocked = () => drawer.isDocked();
/* Docked beside the page, as in Classic (styles.css:6973), only while the research beside it keeps its usable width
 * (owner's amendment 8, 2026-10-21): CONTENT_MIN, measured. Every desktop page was laid out at narrower and narrower
 * content widths with the window at 1600 (~/Optic/work/classic-parity/b4a_widths.py): the Dossier tabs, Chart,
 * Options, Financials, Investing, Home, Macro, Brokerage, Compare and Scan held down to 640; the Watchlist's rows
 * needed their narrower columns, which the page now takes from the docked width too (the eff-* classes). 760 keeps
 * a margin over that and is the plan's starting point. Below it, and on a phone, Milo opens over the page as before.
 * The panel narrows to fit (never under W_MIN) before it gives up docking. */
export const CONTENT_MIN = 760;
/** The docked width for a window `vw` wide with a rail `rail` wide, the reader's chosen width `want`: 0 when Milo
 *  must open over the page instead. */
export function dockFit(vw, rail, want, phone = false) {
  if (phone) return 0;
  const w = Math.min(want, vw - rail - CONTENT_MIN);
  return w >= W_MIN ? Math.round(w) : 0;
}
const railW = () => { const r = document.querySelector('.shell > .rail'); return r && getComputedStyle(r).display !== 'none' ? r.getBoundingClientRect().width : 0; };
const isPhoneNow = () => matchMedia('(max-width: 860px)').matches;
let laid = '';
/** Beside the page or over it, at the width that fits: on opening, on a resize, when the grip moves or the rail folds. */
function layout(chosen = storedWidth() || W_DEFAULT) {
  const root = document.documentElement, open = drawer.isOpen() && S.panel;
  const w = open ? dockFit(window.innerWidth, railW(), chosen, isPhoneNow()) : 0;
  if (open) drawer.setDocked(!!w);
  if (w) {
    const eff = window.innerWidth - w;   // the width the page lays out against: a window this wide without Milo
    root.classList.add('milo-docked'); root.style.setProperty('--milo-dock-w', `${w}px`); S.panel.style.setProperty('--milo-w', `${w}px`);
    root.classList.toggle('eff-1240', eff <= 1240); root.classList.toggle('eff-1100', eff <= 1100);
  } else {
    root.classList.remove('milo-docked', 'eff-1240', 'eff-1100'); root.style.removeProperty('--milo-dock-w');
  }
  // the page changed width without the window doing so: charts that redraw on a resize are told
  const sig = `${w}|${open ? 1 : 0}`;
  if (sig !== laid) { laid = sig; resizedPage(); }
  return w;
}
let relaying = false;
function resizedPage() { if (relaying) return; relaying = true; try { window.dispatchEvent(new Event('resize')); } finally { relaying = false; } }
// the rail folding or unfolding changes the room beside Milo
if (typeof MutationObserver !== 'undefined') {
  const watchRail = () => { const sh = document.querySelector('.shell'); if (!sh) { setTimeout(watchRail, 500); return; } new MutationObserver(() => { if (drawer.isOpen()) layout(); }).observe(sh, { attributes: true, attributeFilter: ['class'] }); };
  if (typeof document !== 'undefined') setTimeout(watchRail, 0);
}

export async function openMilo({ question = '', opener, send: sendNow = false, about, symbol, figures = null } = {}) {
  if (question) S.draft = question;
  // every opening says where it came from, with the figures of the panel it was asked from; one with no block is the
  // whole page
  asked = about || symbol || figures ? { about: about || (figures && figures.name) || null, symbol: symbol ? String(symbol).toUpperCase() : null, panel: figures || null } : null;
  // already open beside the page: the new question goes into the box, nothing is redrawn and the conversation stays
  if (drawer.isOpen() && host()) {
    const ta = $('#milo-q', host());
    if (ta && question) { ta.value = question; grow(ta); }
    paintChrome();
    if (ta) { ta.focus({ preventScroll: true }); ta.setSelectionRange(ta.value.length, ta.value.length); }
    if (sendNow && S.draft) send(S.draft);
    return;
  }
  S.showSettings = false; S.showInfo = false;
  let vvOff = null, gripOff = null;
  drawer.open({
    title: 'Milo', opener, dock: dockFit(window.innerWidth, railW(), storedWidth() || W_DEFAULT, isPhoneNow()) > 0,
    // the redesign's compact header: Milo beside his name, and history, a new conversation and close as icons
    head: html`<div class="milo-id">${figure('compact')}<div><h2 id="milo-title" tabindex="-1">Milo</h2><p class="milo-sub">Research assistant</p></div></div>`,
    actions: html`<button type="button" class="icon-btn" data-v2-milo-history aria-expanded="false" aria-controls="milo-history" aria-label="Conversation history" title="Conversation history">${icon('history')}</button>
      <button type="button" class="icon-btn" data-v2-milo-new aria-label="New conversation" title="New conversation">${icon('compose')}</button>`,
    body: html`<div class="milo"><div class="milo-chrome">${chromeHTML()}</div>
      <div class="milo-log-wrap"><div class="milo-log" role="log" aria-live="polite" aria-label="Conversation with Milo">${logHTML()}</div>
        <button type="button" class="milo-latest" data-v2-milo-latest hidden>${icon('arrowDown')}<span>Latest</span></button></div>
      <form class="milo-form" data-v2-milo-form data-state="idle"><div class="milo-suggest-slot" data-v2-milo-suggest></div><div data-v2-milo-tools>${toolsHTML()}</div><div data-v2-milo-files>${filesHTML()}</div><div class="milo-compose">
        <button type="button" class="milo-attach" data-v2-milo-attach aria-label="Attach an image or PDF" title="Attach an image or PDF: PNG, JPEG, GIF, WebP or PDF, up to 4 files of 5 MB each. You can also drop them here.">${icon('clip')}</button>
        <input type="file" hidden multiple accept="${Object.keys(ATTACH_TYPES).join(',')}" data-v2-milo-file tabindex="-1"><label class="sr" for="milo-q">Your question to Milo</label>
        <textarea id="milo-q" rows="1" maxlength="4000" placeholder="${placeholder()}" aria-describedby="milo-attached milo-allow">${S.draft}</textarea>
        <button type="submit" class="milo-send" data-v2-milo-send aria-label="Send" title="Send (Enter). Shift and Enter for a new line">${icon('send')}</button>
        <button type="button" class="milo-stop" data-v2-milo-stop aria-label="Stop the answer" title="Stop the answer" hidden>${icon('stop')}</button></div>
        <div class="milo-form-foot"><p class="milo-attached" id="milo-attached">${icon('link')}<span>${attachedLine()}</span></p><p class="milo-allow" id="milo-allow" aria-live="polite"></p></div></form></div>`,
    mount: (b) => {
      S.mounted = $('.milo', b) || b;
      const panel = S.mounted.closest('.drawer-panel'); S.panel = panel;
      if (panel) { panel.classList.add('milo-panel'); gripOff = resizable(panel); layout(); }
      // the phone keyboard: the panel is the part of the screen the keyboard leaves, so the composer stays above it
      const vv = window.visualViewport;
      if (vv && panel) {
        const fit = () => { panel.style.setProperty('--vvh', `${Math.round(vv.height)}px`); panel.style.setProperty('--vvt', `${Math.round(vv.offsetTop)}px`); };
        fit(); vv.addEventListener('resize', fit); vv.addEventListener('scroll', fit);
        vvOff = () => { vv.removeEventListener('resize', fit); vv.removeEventListener('scroll', fit); };
      }
      wire(S.mounted);
      const head = panel && $('.drawer-head', panel); if (head) wireHead(head);
      paintLog(); paintForm();
      const w = OS() && welcomeEl(S.mounted);
      if (w && Date.now() - SC.lastWave > 20000) { const c = OS().attach(w, { slot: 'welcome' }); if (c) { SC.lastWave = Date.now(); c.gesture('wave'); } }
      const ta = $('#milo-q', S.mounted); grow(ta);
      if (ta && !matchMedia('(pointer: coarse)').matches) { requestAnimationFrame(() => { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }); }
      loadAllowance(); loadChoices();
      api.get('/api/health', { ttl: 60000 }).then((hh) => { S.health = hh; paintChrome(); }, () => {});
      if (sendNow && S.draft) send(S.draft);
    },
    closed: () => { if (vvOff) vvOff(); if (gripOff) { gripOff(); gripOff = null; } S.panel = null; S.web = false; S.deepHint = false; layout(); const ta = S.mounted && $('#milo-q', S.mounted); if (ta) S.draft = ta.value; SC.menu = false; S.showSettings = false; S.mounted = null; S.panel = null; },
  });
}
// Milo's panel is as wide as the reader drags it, as in the classic app: a grip on its left edge, the arrow
// keys on the grip, a double click for the default. The classic key and its rules: a width is saved only once
// chosen, never on opening; the page keeps at least 240 px (owner, 2026-10-20).
const W_KEY = 'optic.chat.width.v2', W_OLD = 'optic.chat.width.v1', W_OLD_DEFAULT = 382, W_MIN = 320, W_DEFAULT = 560, PAGE_MIN = 240;
const wMax = () => Math.max(W_MIN, drawer.isDocked() ? window.innerWidth - railW() - CONTENT_MIN : window.innerWidth - PAGE_MIN);
function storedWidth() {
  try {
    const n = parseInt(localStorage.getItem(W_KEY) || '', 10); if (Number.isFinite(n) && n >= W_MIN) return n;
    const o = parseInt(localStorage.getItem(W_OLD) || '', 10); if (Number.isFinite(o) && o >= W_MIN && o !== W_OLD_DEFAULT) return o;
  } catch (e) { /* private mode */ }
  return null;
}
function resizable(panel) {
  const grip = document.createElement('div');
  grip.className = 'milo-grip'; grip.tabIndex = 0;
  grip.setAttribute('role', 'separator'); grip.setAttribute('aria-orientation', 'vertical');
  grip.setAttribute('aria-label', "Milo's width. Drag, or use the arrow keys; double-click for the default.");
  panel.appendChild(grip);
  let w = W_DEFAULT;
  const apply = (px, save) => {
    w = Math.round(Math.min(Math.max(px, W_MIN), wMax()));
    panel.style.setProperty('--milo-w', `${w}px`);
    if (drawer.isDocked()) { document.documentElement.style.setProperty('--milo-dock-w', `${w}px`); layout(w); }
    grip.setAttribute('aria-valuenow', String(w)); grip.setAttribute('aria-valuemin', String(W_MIN)); grip.setAttribute('aria-valuemax', String(wMax()));
    if (save) { try { localStorage.setItem(W_KEY, String(w)); } catch (e) { /* private mode */ } }
  };
  apply(storedWidth() || W_DEFAULT, false);
  let dragging = false;
  grip.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    dragging = true; grip.classList.add('is-dragging');
    try { grip.setPointerCapture(e.pointerId); } catch (err) { /* a pointer the browser no longer tracks */ }
    e.preventDefault();
  });
  grip.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    if (e.pointerType === 'mouse' && e.buttons === 0) { end(); return; }
    apply(window.innerWidth - e.clientX, false);
  });
  const end = () => { if (!dragging) return; dragging = false; grip.classList.remove('is-dragging'); apply(w, true); };
  grip.addEventListener('pointerup', end); grip.addEventListener('pointercancel', end); grip.addEventListener('lostpointercapture', end);
  grip.addEventListener('keydown', (e) => {
    const step = e.shiftKey ? 96 : 24;
    if (e.key === 'ArrowLeft') apply(w + step, true);
    else if (e.key === 'ArrowRight') apply(w - step, true);
    else if (e.key === 'Home') apply(W_MIN, true);
    else if (e.key === 'End') apply(wMax(), true);
    else return;
    e.preventDefault();
  });
  grip.addEventListener('dblclick', () => { try { localStorage.removeItem(W_KEY); } catch (e) { /* private mode */ } apply(W_DEFAULT, false); });
  // a narrower window re-clamps the panel, without overwriting the width the reader chose
  const onResize = () => { if (relaying) return; const w2 = layout(); apply(w2 || storedWidth() || W_DEFAULT, false); };
  window.addEventListener('resize', onResize);
  return () => { window.removeEventListener('resize', onResize); grip.remove(); panel.style.removeProperty('--milo-w'); panel.classList.remove('milo-panel'); };
}

// History and a new conversation, from the header's icons or the moved-symbol note; neither touches the draft
function toggleHistory(open = !S.showHistory) {
  S.showHistory = open; S.showSettings = false;
  paintChrome(); paintLog(false);
  const h = host(); if (open && h) { const hd = $('#milo-hist-h', h); if (hd) { hd.setAttribute('tabindex', '-1'); hd.focus({ preventScroll: true }); } }
  else { const hb = S.panel && $('.drawer-head [data-v2-milo-history]', S.panel); if (hb) hb.focus({ preventScroll: true }); }
}
function newConversation() {
  if (S.busy) return;
  S.conv = blankConv(); S.items = []; meta.clear(); SC.i = null; S.showHistory = false;
  paintChrome(); paintLog();
  const ta = host() && $('#milo-q', host()); if (ta) ta.focus();
  announce('New conversation');
}
function wireHead(head) {
  head.addEventListener('click', (e) => {
    if (e.target.closest('[data-v2-milo-history]')) toggleHistory();
    else if (e.target.closest('[data-v2-milo-new]')) newConversation();
  });
}
function setSettings(open, refocus = true) {
  S.showSettings = open; paintChrome();
  const h = host(); if (!h) return;
  if (open) { const hd = $('#milo-set-h', h); if (hd) hd.focus({ preventScroll: true }); }
  else if (refocus) { const b = $('[data-v2-milo-settings]', h); if (b) b.focus({ preventScroll: true }); }
}

function wire(root) {
  root.addEventListener('submit', (e) => { if (e.target.closest('[data-v2-milo-form]')) { e.preventDefault(); send($('#milo-q', root).value); } });
  root.addEventListener('keydown', (e) => { if (e.target.id === 'milo-q' && e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(e.target.value); } });
  // Escape closes what is open inside the panel first (a menu, then Response settings, focus back to its button),
  // and only then the panel: the drawer's own Escape would otherwise shut everything at once
  root.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const menu = e.target.closest && e.target.closest('details.menu[open]');
    if (menu) { e.preventDefault(); e.stopPropagation(); menu.open = false; const sm = menu.querySelector('summary'); if (sm) sm.focus(); return; }
    if (S.showSettings) { e.preventDefault(); e.stopPropagation(); setSettings(false); }
  });
  // the personas are a radio group: the arrows, Home and End move the choice
  root.addEventListener('keydown', (e) => {
    const b = e.target.closest && e.target.closest('.milo-pp-opt'); if (!b) return;
    const all = [...root.querySelectorAll('.milo-pp-opt')], k = all.indexOf(b);
    const to = { ArrowRight: k + 1, ArrowDown: k + 1, ArrowLeft: k - 1, ArrowUp: k - 1, Home: 0, End: all.length - 1 }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    const next = all[(to + all.length) % all.length]; if (next) pickPersona(next.dataset.v2MiloPp, root);
  });
  // inside the guide menu, Escape closes the menu and not the panel; the arrows, Home and End move through it
  root.addEventListener('keydown', (e) => {
    const menu = e.target.closest && e.target.closest('#milo-scout-menu'); if (!menu) return;
    const items = [...menu.querySelectorAll('.scout-mi')], i = items.indexOf(document.activeElement);
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); setMenu(false, true); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
    else if (e.key === 'Home') { e.preventDefault(); items[0].focus(); }
    else if (e.key === 'End') { e.preventDefault(); items[items.length - 1].focus(); }
    else if (e.key === 'Tab') setMenu(false);
  });
  // attachments: the button, the file picker, a tile's remove, and files dropped on the panel
  root.addEventListener('change', (e) => { const inp = e.target.closest && e.target.closest('[data-v2-milo-file]'); if (inp) { addFiles(inp.files).then(() => { inp.value = ''; const b = $('[data-v2-milo-attach]', root); if (b && !b.disabled) b.focus(); }); } });
  root.addEventListener('dragover', (e) => { if (!e.dataTransfer || ![...(e.dataTransfer.types || [])].includes('Files') || blocked()) return; e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; root.classList.add('is-drop'); });
  root.addEventListener('dragleave', (e) => { if (!root.contains(e.relatedTarget)) root.classList.remove('is-drop'); });
  root.addEventListener('drop', (e) => { if (!e.dataTransfer || !e.dataTransfer.files || !e.dataTransfer.files.length) return; e.preventDefault(); root.classList.remove('is-drop'); if (!blocked()) addFiles(e.dataTransfer.files); });
  root.addEventListener('input', (e) => { if (e.target.id === 'milo-q') { const was = !S.draft.trim(), now = !e.target.value.trim(); S.draft = e.target.value; grow(e.target); scoutListen(e.target.value); if (was !== now) paintSuggest(); } });
  root.addEventListener('scroll', (e) => { if (e.target.classList && e.target.classList.contains('milo-log')) syncLatest(); }, true);
  root.addEventListener('change', (e) => {
    const t = e.target;
    if (t.matches('[data-v2-milo-mode]')) { prefs.setKnowledge(t.value); paintChrome(); const sel = $('[data-v2-milo-mode]', root); if (sel) sel.focus(); }
  });
  root.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s); let b;
    if (S.showSettings && !t('.milo-settings') && !t('[data-v2-milo-settings]')) { setSettings(false, false); if (t('[data-v2-milo-settings-done]')) return; }
    if ((b = t('.scout-btn'))) { scoutPress(b); return; }
    if ((b = t('[data-v2-scout-act]'))) { scoutAct(b.dataset.v2ScoutAct); return; }
    if ((b = t('[data-v2-scout-motion]'))) {
      const v = b.dataset.v2ScoutMotion; if (OS()) OS().setMotion(v);
      root.querySelectorAll('[data-v2-scout-motion]').forEach((x) => x.setAttribute('aria-checked', String(x.dataset.v2ScoutMotion === v)));
      setMenu(false, true); return;
    }
    if (SC.menu && !t('#milo-scout-menu')) setMenu(false);
    if (t('[data-v2-milo-settings]')) { setSettings(!S.showSettings); return; }
    if (t('[data-v2-milo-settings-done]')) { setSettings(false); return; }
    if (t('[data-v2-milo-info]')) { S.showInfo = !S.showInfo; paintChrome(); const ib = $('[data-v2-milo-info]', root); if (ib) ib.focus(); return; }
    if ((b = t('[data-v2-milo-scope]'))) {
      S.scope = b.dataset.v2MiloScope;
      const d = b.closest('details'); if (d) d.open = false;
      paintChrome(); if (!S.items.length) paintLog(false);
      const sm = $('.milo-ctx-pick > .milo-ctx-btn', root); if (sm) sm.focus(); return;
    }
    if ((b = t('[data-v2-milo-pp]'))) { pickPersona(b.dataset.v2MiloPp, root, true); return; }
    if ((b = t('[data-v2-milo-hz]'))) { setPref(HORIZON_KEY, b.dataset.v2MiloHz); paintChrome(); const hb = $(`[data-v2-milo-hz="${b.dataset.v2MiloHz}"]`, root); if (hb) hb.focus(); return; }
    if ((b = t('[data-v2-milo-start]'))) { send(b.dataset.v2MiloStart); return; }
    if (t('[data-v2-milo-latest]')) { const log = $('.milo-log', root); if (log) log.scrollTo({ top: log.scrollHeight, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); return; }
    if (t('[data-v2-milo-stop]')) { stop(); return; }
    if (t('[data-v2-milo-history-close]')) { toggleHistory(false); return; }
    if (t('[data-v2-milo-history]')) { toggleHistory(); return; }
    if (t('[data-v2-milo-new]')) { newConversation(); return; }
    if ((b = t('[data-v2-milo-open]'))) {
      if (S.busy) return;
      const c = loadHistory().find((x) => x.id === b.dataset.v2MiloOpen); if (!c) return;
      S.conv = { id: c.id, messages: (c.messages || []).map((m) => ({ role: m.role, content: m.content })), lastTicker: c.ticker || null };
      meta.clear(); SC.i = null; S.items = S.conv.messages.map((m, i) => ({ kind: 'msg', i }));
      S.conv.messages.forEach((m, i) => { if (m.role === 'assistant') meta.set(i, { question: (S.conv.messages[i - 1] || {}).content || '', symbol: c.ticker || null }); });
      S.showHistory = false; S.toEnd = true; paintChrome(); paintLog(); const ta = $('#milo-q', root); if (ta) ta.focus(); return;
    }
    if ((b = t('[data-v2-milo-del]'))) { const id = b.dataset.v2MiloDel; saveHistory(loadHistory().filter((c) => c.id !== id)); if (S.conv.id === id && !S.busy) { S.conv = blankConv(); S.items = []; meta.clear(); } paintChrome(); paintLog(false); const hd = $('#milo-hist-h', root); if (hd) { hd.setAttribute('tabindex', '-1'); hd.focus({ preventScroll: true }); } return; }
    if ((b = t('[data-v2-milo-save]'))) {
      const i = Number(b.dataset.v2MiloSave), q = (S.conv.messages[i] || {}).content, ans = meta.get(i + 1) || {};
      b.disabled = true;
      saveQuestion({ question: q, symbol: ans.symbol || route.symbol || null }).then((r) => {
        if (r.ok) meta.set(i, Object.assign({}, meta.get(i), { saved: true })); else b.disabled = false;
        paintLog(false);
        const guestSave = r.ok && !r.already && r.where === 'browser';
        toast(r.text, guestSave ? { action: 'Create a free account', run: () => { location.hash = '#/signin'; } } : r.ok ? { action: 'Open Saved research', run: () => { location.hash = '#/research'; } } : { kind: 'bad' });
      });
      return;
    }
    if (t('[data-v2-milo-web]')) { S.web = !S.web; paintTools(); const w = $('[data-v2-milo-web]', root); if (w) w.focus(); announce(S.web ? 'Milo will also search the web. Searches add to the cost.' : 'Web search off.'); return; }
    if (t('[data-v2-milo-deep]')) { const ta = $('#milo-q', root); send(ta ? ta.value : '', { deep: true }); return; }
    if ((b = t('[data-v2-milo-mode]'))) { const d = b.closest('details'); if (d) d.open = false; S.deepHint = b.dataset.deep === '1'; }
    if (t('[data-v2-milo-attach]')) { const inp = $('[data-v2-milo-file]', root); if (inp) inp.click(); return; }
    if ((b = t('[data-v2-milo-unattach]'))) { const i = Number(b.dataset.v2MiloUnattach), gone = S.files[i]; S.files.splice(i, 1); paintFiles(); const nb = $('[data-v2-milo-unattach]', root) || $('[data-v2-milo-attach]', root); if (nb) nb.focus(); if (gone) announce(`${gone.name} removed.`); return; }
    if ((b = t('[data-v2-milo-follow]'))) { const ta = $('#milo-q', root); if (ta) { ta.value = b.dataset.v2MiloFollow; S.draft = ta.value; grow(ta); ta.focus(); scoutListen(ta.value); paintSuggest(); paintTools(); } return; }
    if ((b = t('[data-v2-milo-again]'))) { const q = (meta.get(Number(b.dataset.v2MiloAgain)) || {}).question; const ta = $('#milo-q', root); if (q && ta) { ta.value = q; S.draft = q; grow(ta); ta.focus(); } return; }
    if ((b = t('[data-v2-milo-copy]'))) {
      const m = S.conv.messages[Number(b.dataset.v2MiloCopy)] || {}; const txt = sourcesAsText(String(m.content || '').split(/\n(?:→|->) /)[0]);
      const lab = $('span', b) || b;
      try { await navigator.clipboard.writeText(txt); lab.textContent = 'Copied'; setTimeout(() => { lab.textContent = 'Copy'; }, 1500); } catch (err) { lab.textContent = 'Copy failed'; }
      return;
    }
    if (t('[data-v2-milo-srclist]')) { const msg = e.target.closest('.milo-msg'); const d = msg && $('.milo-src-all', msg); if (d) { d.open = true; d.scrollIntoView({ block: 'nearest' }); } return; }
    if (t('[data-v2-milo-act-skip]')) { const card = e.target.closest('.milo-act'); const r = $('.milo-act-result', card); if (r) r.textContent = 'Left as it was.'; card.querySelectorAll('button').forEach((x) => { x.disabled = true; }); return; }
    const vb = t('[data-v2-milo-val-preview], [data-v2-milo-val-apply], [data-v2-milo-val-undo]');
    if (vb) { valuationPress(vb); return; }
    if (t('[data-v2-milo-act-go]')) {
      const card = e.target.closest('.milo-act'), msg = e.target.closest('[data-v2-milo-i]');
      let a = null; try { a = JSON.parse(card.dataset.v2MiloAct); } catch (err) { return; }
      runAction(a, card, msg ? Number(msg.dataset.v2MiloI) : -1);
    }
  });
}
// a persona applies from the next question on; the answers already given are not touched
function pickPersona(id, root, close = false) {
  setPref(PERSONA_KEY, id); paintChrome();
  // a press closes the menu and goes back to its button; the arrows keep the menu open on the new choice (the redraw
  // cannot reopen it itself: its button now names another persona)
  const menu = $('.milo-pp-pick', root);
  if (close && menu) { menu.open = false; const sm = $('.milo-pp-btn', root); if (sm) sm.focus(); }
  else { if (menu) menu.open = true; const nb = $(`[data-v2-milo-pp="${id}"]`, root); if (nb) nb.focus(); }
  const cur = curPersona(); announce(`${cur.label}. Applies from your next question.`);
}
void compact; void ACT_SECTIONS;
