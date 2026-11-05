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
// The Milo Context Bar (Handoff 6): what Milo is researching, from the same context, at the top of the panel:
// "Researching AAPL · Daily · RSI 14, MACD 12, 26, 9 · Chart", with Change (the menu: what it holds, a focus on
// Compare, what Milo receives) and Remove (one press: general questions, no ticker). It follows the page as it
// changes (contextChanged, from the chart), and each answer says what it was for, kept with the conversation.
//
// Nothing is sent until the reader presses Send, and every entry point elsewhere in the terminal drafts. The panel's
// three opening starters and Deep research are the exceptions, by the owner's decision: a starter sends as it reads
// ("must send meaningful requests", 2026-10-20), and Deep research is itself the ask (BUG-049).
import { html, render, $, raw, announce, reducedMotion } from '../core/dom.js';
import { makeDrawer } from './drawer.js';
import { saveQuestion } from '../core/research.js';
import { saveButton, provide as provideSave, refresh as refreshSaved } from './library.js';
import { keyOf, known as knownSaved, dayText } from '../core/library.js';
import { toast } from './toast.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import * as prefs from '../core/prefs.js';
import * as router from '../core/router.js';
import { holds } from '../core/device.js';
import { esc, compact } from '../core/format.js';
import { GROUPS, SETTINGS } from '../nav.js';
import { renderAnswer, splitFollowUps, streamingHTML, settledEnd, FOLLOW_AT, sourcesAsText, STUDIES, SECTIONS as ACT_SECTIONS } from '../core/milo-text.js';
import { lineChart, mountCharts } from './chart.js';
import * as FF from './finfigs.js';
import { CLASSIC } from '../core/classic.js';
import { miloNotice } from '../core/legal.js';
import { icon } from './icons.js';
import { levelSlider } from './levelslider.js';
import { begin as actBegin, on as actOn, activityHTML, syncActivity } from './milo-activity.js';
import { researchOf, researchLine, researchWords, researchRows, removedSince, usedLine, keepUsed } from './milo-context.js';

const HISTORY_KEY = 'optic.pulse.history.v1', PERSONA_KEY = 'optic.pulse.persona.v1', HORIZON_KEY = 'optic.milo.horizon.v1', RESEARCH_KEY = 'optic.research.v1';
const MAX_CONVERSATIONS = 30, MAX_MESSAGES = 60, MAX_CHARS = 12000, MAX_Q = 4000;
const DOSSIER = new Set(['overview', 'chart', 'swing', 'long', 'earnings', 'financials', 'news', 'investigate']);
// a source's time as a reader says it: "2026-10-22T20:11:00+00:00" printed raw under every headline (audit 2026-10-22)
// a moment with its day when it is not today's, in the reader's zone: a saved conversation reopened later says which day
// each figure was read, not only the hour (Saved research, Handoff 5)
const sameDay = (iso) => { try { const z = prefs.zone(), f = (d) => d.toLocaleDateString('en-US', { timeZone: z }); return f(new Date(iso)) === f(new Date()); } catch (e) { return true; } };
const seenAt = (iso) => (sameDay(iso) ? prefs.clock(iso) : prefs.dayTime(iso));
const readWhen = (v) => { const t = /^\d{4}-\d{2}-\d{2}T/.test(String(v || '')) ? new Date(v) : null; return t && !Number.isNaN(t.getTime()) ? `published ${t.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' })} ET` : (v || ''); };
// The states an answer shows, each tied to something that happened (audit and motion session, 2026-10-22). No
// fake progress, no percentages, no research claims without an event behind them:
//   submitted   the question has left ("Sending your question"), the activity line runs
//   preparing   the server accepted it and assembled the page's context, before any model event
//   retrieving  a status event from the server: a tool it is running ("Checking NVDA's options data"), a web search
//   streaming   text is arriving; the status line gives way to the words
//   complete    the done event: the line goes, sources and actions appear
//   stopped     the reader pressed Stop: "Stopped by you. This answer is incomplete."
//   failed      an error event or no answer: the reason, and the question back in the box
export const MILO_STATES = { submitted: 'Sending your question', preparing: 'Preparing the answer' };
// No word from the server for this long (no event, no bytes) and the answer says so, with Stop beside it: a silent
// stream looked frozen (motion proposal, 2026-10-24). It goes the moment anything arrives. It claims nothing more.
const QUIET_MS = 30000;
export const QUIET_TEXT = 'No reply from the server for 30 seconds. You can keep waiting or stop the answer.';
const STEP_WORDS = { thinking: 'Thinking it through', 'searching the web': 'Searching the web', searching: 'Searching live sources', 'reading results': 'Reading what it found',
  // the server's own steps (post-demo Phase 07): it has the question and is gathering the page's figures; a round of the
  // model has started, so what the reader waits for now is the model, not the tool whose line was showing
  writing: 'Working out the answer' };
const stepWords = (state, sym) => (state === 'gathering' ? (sym ? `Reading ${sym}'s figures` : 'Reading the figures for your question')
  : STEP_WORDS[state] || String(state || '').replace(/^./, (x) => x.toUpperCase()));
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
export function provideContext(fn) { provider = typeof fn === 'function' ? fn : null; contextChanged(); }
/** Called by the app on every navigation, before the new page renders. */
export function resetContext(r) {
  provider = null; route = r || { view: 'home' }; asked = null; S.dropped.clear(); S.pick = null;
  if (drawer.isOpen() && !drawer.isDocked()) drawer.close({ silent: true });
  // an open panel redraws its answers' "About" lines against the page now open (not while one streams)
  if (typeof paintLog === 'function' && host() && !S.live) { try { paintLog(false); paintChrome(); } catch (e) { /* drawn on next open */ } }
}
const pageLabel = (r) => {
  if (r.view === 'settings') return SETTINGS.label;
  if (r.view === 'instrument') return `${r.symbol || 'Instrument'}`;
  if (r.view === 'investigate') return 'Investigation';
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
// A page whose context could not be read sends none: general mode, said so, never a guessed ticker (Handoff 6)
const unreadable = (r, now) => ({ focus: { scope: 'none', unavailable: true, view: r.view, view_label: 'Page context unavailable', ticker: null, section: null, captured_at: now.toISOString() } });
/** The context sent with a question, checked against the route on screen. */
export function buildContext(scope, prevTicker, now = new Date()) {
  const panel = scope === 'auto' && asked && asked.panel ? asked.panel : null;
  const r = route;
  let ctx = {};
  if (scope === 'auto' && provider) { try { ctx = { ...(provider() || {}) }; } catch (e) { console.error(e); return unreadable(r, now); } }
  // a Dossier page's data must be about the symbol on screen; anything naming another is dropped
  if (DOSSIER.has(r.view) && r.symbol) {
    Object.keys(ctx).forEach((k) => { const v = ctx[k]; const own = v && typeof v === 'object' && !Array.isArray(v) ? (v.symbol || v.ticker) : null; if (own && typeof own === 'string' && own.toUpperCase() !== r.symbol) delete ctx[k]; });
    if (ctx.ticker && ctx.ticker !== r.symbol) ctx.ticker = r.symbol;
  }
  // the parts the reader took out before sending (the attached list in the context menu)
  if (scope === 'auto') S.dropped.forEach((k) => { delete ctx[k]; });
  const own = DOSSIER.has(r.view) || r.view === 'instrument' ? r.symbol || null : null;
  // a block about one symbol on a page about none (a Brokerage thesis) names it; it never overrides the page's own
  const ticker = scope === 'auto' ? own || (asked && asked.symbol) || null : null;
  // the Dossier tab, if any: its key is always there, so the server knows the panel describes the research
  const focus = { scope, view: r.view, view_label: contextLabel(scope), ticker, section: own && DOSSIER.has(r.view) ? pageLabel(r) : null, captured_at: now.toISOString() };
  if (scope === 'auto' && asked && asked.about) focus.asked_from = asked.about;
  // the chart's identity, never its bars: the size and range, the dates in view, the indicators with their settings
  if (r.view === 'chart' && scope === 'auto' && ctx.chart) {
    const c = ctx.chart;
    focus.chart = { range: c.range, interval: c.interval, visible_from: c.visible_from || null, visible_to: c.visible_to || null, indicators: (c.indicators || []).map((x) => ({ id: x.id, label: x.label, settings: x.settings })), compared: (c.compared || []).slice(0, 3) };
  }
  // Compare: the names compared, and the one the reader picked, or none; never one chosen for the reader
  const cmpNames = scope === 'auto' && r.view === 'compare' && ctx.compare && Array.isArray(ctx.compare.tickers) ? ctx.compare.tickers.slice(0, 4) : [];
  if (cmpNames.length >= 2) { focus.compare = { tickers: cmpNames, focus: cmpNames.includes(S.pick) ? S.pick : null }; if (!own) focus.ticker = focus.compare.focus; }
  if (prevTicker && focus.ticker && prevTicker !== focus.ticker) focus.previous_ticker = prevTicker;
  delete ctx.focus_label; delete ctx.focus;
  if (scope === 'none') return { focus };
  if (scope === 'market') { const out = { focus }; ['macro', 'sectors', 'indices', 'read'].forEach((k) => { if (ctx[k]) out[k] = ctx[k]; }); return out; }
  // the panel an Ask Milo button sat in (B4a.3) is one of the attached parts, so it can be taken out like the rest
  return panel && !S.dropped.has('panel') ? { ...ctx, panel, focus } : { ...ctx, focus };
}

/** A page whose context changed without a navigation (the chart's bar size, an indicator on or off) says so here:
 *  the bar follows at once. One paint a frame, and only the panel's controls, never the conversation. */
let ctxFrame = null;
export function contextChanged() {
  if (ctxFrame || !host()) return;
  ctxFrame = requestAnimationFrame(() => { ctxFrame = null; if (host()) paintChrome(); });
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
  // the advice-policy notes go with their answer, so a reopened conversation still says what was declined or removed
  const from = Math.max(0, S.conv.messages.length - MAX_MESSAGES);
  const messages = S.conv.messages.slice(-MAX_MESSAGES).map((m, k) => { const inf = meta.get(from + k) || {}, o = { role: m.role, content: String(m.content || '').slice(0, MAX_CHARS) };
    if (inf.policyLine) o.policy = String(inf.policyLine).slice(0, 400); if (inf.amended) o.amended = String(inf.amended).slice(0, 400); if (inf.level) o.level = String(inf.level).slice(0, 20);
    // what the answer was for (ticker, timeframe, indicators, tab), so a reopened answer still says it (Handoff 6)
    if (inf.used) o.context = keepUsed({ ...inf.used, at: ((inf.context || {}).focus || {}).captured_at }); return o; });
  const list = loadHistory().filter((c) => c.id !== S.conv.id);
  list.unshift({ id: S.conv.id, at: new Date().toISOString(), title: titleOf(messages), ticker: route.symbol || null, messages });
  saveHistory(list.slice(0, MAX_CONVERSATIONS));
}

/* ---------------- state ---------------- */
const blankConv = () => ({ id: newId(), messages: [], lastTicker: null, lastChart: null });
const S = { files: [], web: false, deepHint: false, conv: blankConv(), items: [], busy: false, abort: null, scope: 'auto', pick: null, showHistory: false, showSettings: false, showInfo: false, allowance: null, personas: null, modes: null, draft: '', live: null, mounted: null, panel: null, toEnd: false, symbolAtAsk: null, dropped: new Set(), report: null, follow: true, view: null, lastTop: null, cutPaste: 0 };
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
// The header is his name alone: the owner asked for the figure out of it (2026-11-03). What he is doing is
// said by the activity figure in the answer itself (ui/milo-activity.js), which is where a reader is looking,
// so nothing is lost by it. These two stay because they are what puts a figure back there if it returns, and
// every caller already handles finding none.
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
  // the owner's ask: Milo says hello first, then the question. The bubble sits beside his head, its tail
  // pointing at him (owner, 2026-10-22: "have the text next to his head"; it had been under his feet)
  return html`<div class="milo-opening"><div class="milo-hello">${fig}<p class="milo-hi">Hey, I'm Milo!</p>${fig ? menuHTML() : ''}</div>
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
  if (m.role === 'user') return html`<div class="milo-msg milo-you${S.fresh === it.i ? ' is-new' : ''}"><p class="sr">You asked</p><div class="milo-bubble">${m.content}</div>${info.files ? html`<p class="milo-sent-files">${icon('clip')}<span>${info.files.join(', ')}</span></p>` : ''}${savable ? html`<p class="milo-you-acts"><button type="button" class="milo-save" data-v2-milo-save="${it.i}" ${info.saved ? html`disabled` : ''} title="Keep this question in Saved research, to ask again">${info.saved ? 'Saved' : 'Save'}</button></p>` : ''}</div>`;
  const shown = String(m.content || '').replace(/\n\n\[(Stopped by the reader|Cut off): incomplete\]$/, '');
  const live = S.live && S.live.i === it.i;
  // an answer still arriving, when the whole log is drawn (the panel opened again mid-answer): as the live drawing has
  // it, so no half-written tag shows for the frame before paintLive takes it over
  const { html: body, ups } = live ? { html: streamingHTML(shown, info.symbol || null), ups: [] } : renderAnswer(shown, info.symbol || null);
  // an answer sits on the panel's own surface: its name, what it was about, the text; sources and actions after it
  return html`<article class="milo-msg milo-bot" data-v2-milo-i="${it.i}" aria-label="Milo's answer"><p class="milo-who">Milo</p>
    ${aboutLine(info)}
    ${info.assumed ? html`<p class="milo-assumed">${info.assumed}</p>` : ''}
    ${levelNote(info, live)}
    ${info.deep ? html`<p class="milo-assumed">Deep research: read from live web sources.</p>` : info.web ? html`<p class="milo-assumed">Web search was on for this answer.</p>` : ''}
    ${info.notSent && info.notSent.length ? html`<p class="milo-not-sent" role="note"><b>Not sent with this question:</b> ${info.notSent.join('; ')}.</p>` : ''}
    ${info.policyLine ? html`<p class="milo-policy" role="note">${info.policyLine}</p>` : ''}
    <div class="milo-bubble">${raw(body)}</div>
    ${info.amended ? html`<p class="milo-amended" role="note">${info.amended}</p>` : ''}
    ${live ? html`<span class="activity" role="progressbar" aria-label="Milo is working on this answer"></span>` : ''}
    ${info.ended || /\[(Stopped by the reader|Cut off): incomplete\]$/.test(m.content || '') ? html`<p class="milo-ended" role="note">${(info.ended || (/Stopped by the reader/.test(m.content) ? 'stopped' : 'cut')) === 'stopped' ? 'Stopped by you. This answer is incomplete.' : 'The connection ended before Milo finished. This answer is incomplete.'}</p>` : ''}
    ${live ? '' : html`${ups.length ? html`<div class="milo-ups" role="group" aria-label="Follow-up questions">${ups.map((q) => html`<button type="button" class="milo-up" data-v2-milo-follow="${q}">${q}</button>`)}</div>` : ''}
      <div class="milo-foot">${sourceLists(info)}<div class="milo-acts"><button type="button" class="milo-act-btn" data-v2-milo-copy="${it.i}">${icon('copy')}<span>Copy</span></button>${info.question ? html`<button type="button" class="milo-act-btn" data-v2-milo-again="${it.i}" title="Put the question back in the box">${icon('retry')}<span>Ask again</span></button>` : ''}<button type="button" class="milo-act-btn" data-v2-milo-report="${it.i}" aria-expanded="${S.report && S.report.i === it.i ? 'true' : 'false'}" title="Tell Optic this answer has a wrong figure or a mistake">${icon('flag')}<span>Report a problem</span></button></div></div>
      ${S.report && S.report.i === it.i && S.report.conv === S.conv.id ? reportHTML(it.i) : ''}
      <p class="milo-gen">Generated by an AI model from Optic's data. It can be wrong; check the figures against the sources.</p>`}</article>`;
}
// A problem with one answer, sent to the operator's problem reports (/api/feedback) with the question and the answer
// attached, so a wrong figure can be traced. It goes to a person; nothing here trains or changes the model.
function reportHTML(i) {
  const r = S.report;
  if (r.sent) return html`<p class="milo-report-done" role="status">Report sent. It goes to the people who run Optic, with this question and answer attached.</p>`;
  return html`<form class="milo-report" data-v2-milo-report-form="${i}"><label for="milo-rep-${i}">What is wrong with this answer?</label>
    <textarea id="milo-rep-${i}" rows="3" maxlength="600" placeholder="For example: the P/E it gives is not the one on the Overview">${r.text || ''}</textarea>
    ${r.err ? html`<p class="milo-report-err" role="alert">${r.err}</p>` : ''}
    <p class="asof">Sent to the people who run Optic with the question and the first part of the answer. It does not train or change Milo.</p>
    <div class="cluster"><button type="submit" class="btn btn-sm" ${r.busy ? 'disabled' : ''}>${r.busy ? 'Sending...' : 'Send report'}</button><button type="button" class="btn btn-quiet btn-sm" data-v2-milo-report-cancel>Cancel</button></div></form>`;
}
async function sendReport(i, text) {
  const q = String((S.conv.messages[i - 1] || {}).content || ''), a = String((S.conv.messages[i] || {}).content || '');
  const head = `${text.trim().slice(0, 600)}\n\nMilo answer report\nQuestion: ${q.slice(0, 300)}\nAnswer: `;
  // the conversation it was written in, taken now: read after the request, a report sent before New conversation
  // showed its outcome under the new one's answer at the same place (BUG-185, Phase 11)
  const conv = S.conv.id;
  S.report = { conv, i, text, busy: true }; paintLog(false);
  try {
    await api.post('/api/feedback', { message: head + a.slice(0, Math.max(200, 1990 - head.length)), page: `Milo, ${contextLabel('auto')}`.slice(0, 200) });
    S.report = { conv, i, sent: true };
  } catch (e) { S.report = { conv, i, text, err: api.explain(e, 'The report') }; }
  paintLog(false);
}
/** The instruments an answer's data concerns: what the server loaded for the question and what Milo looked up,
 * apart from the page it was asked from. */
export function concerns(info) {
  const out = [], add = (s) => { if (s && !out.includes(s)) out.push(s); };
  const nm = (info || {}).named;
  // what the question named, the page's own symbol included (sent with the answer since 2026-10-22), and what the
  // server loaded for it. What Milo looked up besides is "also looked up", not the subject: a BRK-A question that
  // fetched SPY for the market read "About SPY ... Not about BRK-A" (audit 2026-10-22).
  if (nm && typeof nm === 'object') {
    (nm.symbols || []).forEach(add); ((info || {}).loaded || []).forEach((r) => (r.symbols || []).forEach(add));
    if (!out.length && !(nm.unknown || []).length) ((info || {}).retrieved || []).filter((r) => r && r.ok !== false).forEach((r) => (r.symbols || []).forEach(add));
    return out;
  }
  // an answer saved before then: what the question loaded, then what Milo looked up
  ((info || {}).loaded || []).forEach((r) => (r.symbols || []).forEach(add));
  ((info || {}).retrieved || []).filter((r) => r && r.ok !== false).forEach((r) => (r.symbols || []).forEach(add));
  return out;
}
/** Symbols Milo looked up that the question was not about. */
const alsoLooked = (info, about) => [...new Set(((info || {}).retrieved || []).filter((r) => r && r.ok !== false).flatMap((r) => r.symbols || []))].filter((s) => s && !about.includes(s));
/** Symbols the answer concerns for which no data came back. */
const dataless = (info, syms) => syms.filter((s) => ![...((info || {}).loaded || []), ...((info || {}).retrieved || [])].some((r) => r && r.ok !== false && (r.symbols || []).includes(s)));
// What an answer was about and when it was asked. The page attached as context and the instruments the answer's
// data concerns are said apart: an NVDA answer asked from AAPL's Investing page read "About AAPL" (pitch audit,
// 2026-10-22). Before the data is known (while it streams), the page is all there is to say.
export function aboutLine(info, now = route) {
  const used = (info || {}).used;
  if (used && (used.ticker || used.general || used.unavailable || used.compare)) return forLine(info, used, now);
  const f = ((info || {}).context || {}).focus || {};
  const page = (info || {}).symbol || f.ticker || null, where = f.view_label || '';
  const data = concerns(info), unknown = (((info || {}).named || {}).unknown || []);
  const about = data.length ? data : unknown.length ? [] : page ? [page] : [];
  if (!about.length && !where && !unknown.length) return '';
  const also = (info || {}).named ? alsoLooked(info, about) : [];
  const join = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}` : xs[0]);
  const ctx = page && !about.includes(page) ? `${where && where !== page ? where : `${page}'s page`} attached as context` : (where && (!page || where !== page) ? `asked from ${where}` : '');
  const other = about.length && now && now.symbol && !about.includes(now.symbol);
  const none = data.length ? dataless(info, data).filter((x) => x !== page) : [];   // the page's own data is attached
  return html`<p class="milo-about ${other || unknown.length ? 'is-other' : ''}">${about.length ? `About ${join(about)}` : unknown.length ? `About ${join(unknown)}, a symbol Optic has no data for` : `From ${where}`}${none.length ? ` (no ${join(none)} data came back)` : ''}${also.length ? `; also looked up ${join(also)}` : ''}${ctx ? `; ${ctx}` : ''}${f.captured_at ? `, ${seenAt(f.captured_at)}` : ''}${other ? html`. <b>Not about ${now.symbol}, the page now open.</b>` : ''}</p>`;
}
// The figure registry's figures a lookup returned (Handoff 1): each as Milo retrieved it, opening the same definition
// the Dossier opens (ui/figure.js reads the value from the button, so the panel shows what this answer was given)
function figureList(figs) {
  const list = (Array.isArray(figs) ? figs : []).filter((x) => x && x.figure_id);
  if (!list.length) return '';
  const own = (x) => JSON.stringify({ name: x.name, text: x.text, status: x.status, why: x.why || null, period: { label: x.period || '' }, source: { name: x.source || '', url: x.filing || null }, as_of: x.as_of || null });
  return html`<ul class="plain milo-figs">${list.map((x) => html`<li>${x.name || ''}${x.symbol ? `, ${x.symbol}` : ''}: <button type="button" class="fig" data-v2-fig="${x.figure_id}" data-v2-fig-sym="${x.symbol || ''}" data-v2-fig-value="${own(x)}" aria-haspopup="dialog" aria-expanded="false" aria-label="${x.name || 'Figure'}: ${x.text || ''}. Show how it is defined">${x.text || ''}</button>${x.period ? html` <small class="t-muted">${x.period}</small>` : ''}</li>`)}</ul>`;
}
// What an answer was for (Handoff 6), in the context bar's words: "For AAPL · Daily · RSI 14 · Chart, 3:41 pm". When
// the question named another company, that is what it is about and the page was only its context; a general answer
// says it had no ticker, and one whose page context could not be read says that, as a note.
function forLine(info, used, now) {
  const f = ((info || {}).context || {}).focus || {}, t = used.ticker, at = f.captured_at || used.at;
  const data = concerns(info), unknown = (((info || {}).named || {}).unknown || []);
  const join = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}` : xs[0]);
  let head = usedLine(used), about = t ? [t] : data;
  if (used.general || used.unavailable) head += data.length ? `; about ${join(data)}` : unknown.length ? `; about ${join(unknown)}, a symbol Optic has no data for` : '';
  else if (t && data.length && !data.includes(t)) { about = data; head = `About ${join(data)}; ${researchLine(used)} attached as context`; }
  else if (t) { const also = (info || {}).named ? alsoLooked(info, [t, ...data]) : []; if (also.length) head += `; also looked up ${join(also)}`; }
  const other = about.length && now && now.symbol && !about.includes(now.symbol);
  return html`<p class="milo-about milo-for ${other || used.unavailable ? 'is-other' : ''}" ${used.unavailable ? html`role="note"` : ''}>${head}${at ? `, ${prefs.clock(at)}` : ''}${other ? html`. <b>Not about ${now.symbol}, the page now open.</b>` : ''}</p>`;
}
// The line above one answer drawn again in place (its `context` event came after the answer was first drawn)
function paintAbout(i) {
  const h = host(), box = h && $(`[data-v2-milo-i="${i}"]`, h); if (!box) return;
  const tmp = document.createElement('div'); render(tmp, aboutLine(meta.get(i) || {}));
  const was = $('.milo-about', box), now = tmp.firstElementChild;
  if (was && now) was.replaceWith(now); else if (was) was.remove(); else if (now) { const who = $('.milo-who', box); if (who) who.after(now); }
}
// Every source behind an answer, one fold away: what it cited, what it read, the data it looked up
export function sourceLists(info) {
  const cites = info.citations || [], read = info.read || [], got = info.retrieved || [], loaded = info.loaded || [];
  const n = cites.length + read.length + got.length + loaded.length;
  if (!n) return html`<span class="milo-src-none"></span>`;
  return html`<details class="milo-src-all"><summary>Sources (${n})</summary><div class="milo-src-body">
    ${cites.length ? html`<div class="milo-sources"><p class="t-label">Cited</p>${cites.map((c) => (/^https?:\/\//i.test(c.url || '') ? html`<a href="${c.url}" target="_blank" rel="noopener">${c.title || c.url}</a>` : html`<span>${c.title || ''}</span>`))}</div>` : ''}
    ${read.length ? html`<div class="milo-read"><p class="t-label">Sources Milo read (${read.length})</p><ul class="plain">${read.map((r) => html`<li>${r.symbol ? html`<b>${r.symbol}</b> ` : ''}${/^https?:\/\//i.test(r.url || '') ? html`<a href="${r.url}" target="_blank" rel="noopener">${r.source}</a>` : r.source} <small class="t-muted">${[r.what, readWhen(r.period), r.kind === 'headline' ? 'the headline only, not the article' : ''].filter(Boolean).join(', ')}</small></li>`)}</ul></div>` : ''}
    ${got.length ? html`<div class="milo-read"><p class="t-label">Data Milo retrieved (${got.length})</p><ul class="plain">${got.map((r) => html`<li>${r.label || ''} <small class="t-muted">${[r.source, r.as_of ? `observed ${seenAt(r.as_of)}` : '', r.retrieved_at ? `retrieved ${seenAt(r.retrieved_at)}` : '', r.ok === false ? 'could not be retrieved' : ''].filter(Boolean).join(', ')}</small>${figureList(r.figures)}</li>`)}</ul></div>` : ''}
    ${loaded.length ? html`<div class="milo-read"><p class="t-label">Loaded because the question named them (${loaded.length})</p><ul class="plain">${loaded.map((r) => html`<li>${r.label || ''} <small class="t-muted">${[r.source, r.as_of ? `quote observed ${seenAt(r.as_of)}` : ''].filter(Boolean).join(', ')}</small></li>`)}</ul></div>` : ''}</div></details>`;
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
  const h = hz.find((x) => x.id === horizon()) || hz[0] || null;
  const list = (rows, head) => (rows && rows.length ? html`<p class="t-label">${head}</p><ul class="plain">${rows.map((r) => html`<li>${r}</li>`)}</ul>` : '');
  // the classic order: the level first, then the timeframe
  return html`<div class="milo-sheet-scrim" data-v2-milo-settings-done aria-hidden="true"></div>
    <div class="milo-settings" id="milo-settings" role="dialog" aria-modal="false" aria-labelledby="milo-set-h">
    <div class="milo-set-head"><h3 id="milo-set-h" tabindex="-1">Response settings</h3><button type="button" class="icon-btn" data-v2-milo-settings-done aria-label="Close Response settings" title="Close">${icon('close')}</button></div>
    ${ms.length ? html`<div class="milo-level">${levelSlider({ id: 'milo-lvl', label: 'Level', compact: true })}</div>` : ''}
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
// What the page's context holds, by name, so the reader sees what goes with the question and can take a part out
// (motion proposal, 2026-10-24). Read from the same buildContext() that Send uses; nothing here is a summary of it.
// the Chart page's bar sizes as its menu names them: '60' is 1h, 'daily' 1D
const barWord = (k) => { const n = Number(k); return Number.isFinite(n) && n > 0 ? (n >= 60 ? `${n / 60}h` : `${n}m`) : ({ daily: '1D', weekly: '1W' }[k] || String(k || '')); };
const partName = (k) => String(k).replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/^./, (x) => x.toUpperCase());
function attachedParts(built, bar = false) {
  if (S.scope !== 'auto') return '';
  const ctx = built || buildContext('auto'), f = ctx.focus || {};
  if (f.unavailable) return '';
  // `view` only names the page, which the focus already says
  const parts = Object.keys(ctx).filter((k) => k !== 'focus' && k !== 'view' && ctx[k] !== null && ctx[k] !== undefined && ctx[k] !== '');
  const dropped = [...S.dropped];
  if (!parts.length && !dropped.length) return html`<p class="milo-parts-none">This page sends no figures of its own: only which page it is${f.ticker ? ` and ${f.ticker}` : ''}.</p>`;
  // with the context bar above it, the ticker and the chart are said there already
  return html`<details class="more-inline milo-parts" ${S.partsOpen ? 'open' : ''}><summary>What is attached: ${parts.length} part${parts.length === 1 ? '' : 's'}${!bar && f.ticker ? `, ${f.ticker}` : ''}${!bar && f.chart ? `, ${barWord(f.chart.interval)} bars${f.chart.range ? `, ${f.chart.range}` : ''}` : ''}</summary>
    <ul class="milo-parts-l">${parts.map((k) => html`<li><span>${partName(k)}</span><button type="button" class="textlink" data-v2-milo-drop="${k}" aria-label="Remove ${partName(k)} from what Milo receives">Remove</button></li>`)}
      ${dropped.map((k) => html`<li class="is-off"><span>${partName(k)}, removed</span><button type="button" class="textlink" data-v2-milo-undrop="${k}">Put back</button></li>`)}</ul>
    <p class="asof">Read from the page when you press Send. Removed parts stay out until you change page.</p></details>`;
}
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
export const OPTIONS_FOLLOWUPS = ['Why does the model score that strike above a cheaper out-of-the-money one?', 'What does the gamma profile say about how the price may move here?', 'Is the flow confirming or fighting the chart?', "Walk me through the model's trigger zone and what breaks the setup.", 'Does the short interest or insider activity change the read?', 'How has the stock moved after past earnings reports?'];
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
// The Milo Context Bar (Handoff 6). With a ticker (or Compare's names) in the page's context: "Researching", the
// ticker and timeframe (all a phone shows), then the indicators and the Dossier tab, as the summary of the menu that
// changes it (Change), and Remove beside it, one press to general questions. Without one, the picker as before.
function researchMenu(rf, built) {
  const rows = researchRows(rf), layers = ((built.chart || {}).layers || []).filter(Boolean);
  const cur = rf.compare ? rf.compare.focus : undefined;
  return html`<div class="milo-rs-detail"><p class="menu-help milo-rs-h">Milo is researching</p>
      ${rows.length ? html`<dl class="milo-rs-dl">${rows.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}${layers.length ? html`<div><dt>Also on the chart</dt><dd>${layers.join('; ')}</dd></div>` : ''}</dl>` : ''}
      ${rf.compare ? html`<div class="milo-rs-focus" role="group" aria-labelledby="milo-rs-fh"><p class="t-label" id="milo-rs-fh">Which name Milo answers about</p>
        ${[null, ...rf.compare.tickers].map((t) => html`<button type="button" class="milo-ctx-opt" aria-pressed="${cur === t ? 'true' : 'false'}" data-v2-milo-pick="${t || ''}">${cur === t ? icon('check') : html`<span class="milo-ctx-gap"></span>`}<span><b>${t || 'The comparison as a whole'}</b><small>${t ? `Milo answers about ${t}, against the others.` : 'No single name: Milo answers about all of them, and asks which one when a question needs one.'}</small></span></button>`)}</div>` : ''}
      <p class="menu-help">Read from the page when you press Send. Milo only reads it: it never changes your chart, watchlists or alerts.</p></div>`;
}
function barHTML(rf, menu) {
  const short = researchLine(rf, { short: true }), full = researchLine(rf);
  const rest = rf.ticker && full.startsWith(short) ? full.slice(short.length) : '';
  const what = rf.ticker || `the comparison of ${rf.compare.tickers.join(', ')}`;
  return html`<div class="milo-rs" role="group" aria-label="What Milo is researching"><span class="milo-rs-lab" aria-hidden="true">Researching</span>
      <details class="menu milo-ctx-pick milo-rs-pick"><summary class="milo-ctx-btn milo-rs-btn" title="${`Researching ${full}. Change what Milo receives`}"><span class="sr">Researching ${researchWords(rf)}. Change: </span><span class="milo-ctx-now milo-rs-now" aria-hidden="true">${rest ? html`<b>${short}</b><span class="milo-rs-rest">${rest}</span>` : html`<b>${rf.ticker ? short : full}</b>`}</span><span class="milo-rs-chg" aria-hidden="true">Change</span>${icon('chev')}</summary>${menu}</details>
      <button type="button" class="icon-btn milo-rs-x" data-v2-milo-scope="none" aria-label="${`Remove ${what} from what Milo receives`}" title="Remove: Milo answers in general, about no company">${icon('close')}</button></div>`;
}
function ctxHTML() {
  const opts = [['auto', `This page: ${contextLabel('auto')}`, 'The figures on the page you have open.'], ['market', SCOPES.market, "The market's state: indices, sectors and the macro read. No company."], ['none', SCOPES.none, 'Your question and this conversation only.']];
  const built = S.scope === 'auto' ? buildContext('auto') : null, rf = built ? researchOf(built.focus) : null;
  const bar = !!(rf && (rf.ticker || rf.compare));
  const menu = html`<div class="menu-body milo-ctx-menu" role="group" aria-label="What Milo receives">${bar ? researchMenu(rf, built) : ''}${opts.map(([k, l, d]) => html`<button type="button" class="milo-ctx-opt" aria-pressed="${S.scope === k ? 'true' : 'false'}" data-v2-milo-scope="${k}">${S.scope === k ? icon('check') : html`<span class="milo-ctx-gap"></span>`}<span><b>${l}</b><small>${d}</small></span></button>`)}</div>`;
  // after Remove, one press puts the page's ticker back (the choice holds across pages until it is changed)
  const back = S.scope === 'none' && onSymbol() ? html`<button type="button" class="textlink milo-rs-back" data-v2-milo-scope="auto">Use ${onSymbol()}</button>` : '';
  return html`<div class="milo-ctx ${bar ? 'has-rs' : ''}"><div class="milo-ctx-l">
      ${bar ? barHTML(rf, menu) : (() => { const pick = html`<details class="menu milo-ctx-pick"><summary class="milo-ctx-btn" title="What Milo receives with your question"><span class="sr">What Milo receives: </span><span class="milo-ctx-now">${built && built.focus.unavailable ? 'Page context unavailable' : contextShort()}</span>${icon('chev')}</summary>${menu}</details>`; return back ? html`<div class="milo-rs is-general">${pick}${back}</div>` : pick; })()}
      ${built && built.focus.unavailable ? html`<p class="milo-rs-err" role="status">This page's context could not be read. Milo will answer in general, about no company, until it can be.</p>` : ''}
      ${attachedParts(built, bar)}
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
// The header's buttons (outside the panel's body): whether history is open, and neither history nor a new conversation
// mid-answer. The answer being written belongs to the conversation on screen, so while Milo answers nothing else can
// take its place. Both buttons stay where a keyboard or a screen reader finds them (aria-disabled, not disabled) and a
// press says why (post-demo Phase 07).
function paintHead() {
  const hb = S.panel && $('.drawer-head [data-v2-milo-history]', S.panel), nb = S.panel && $('.drawer-head [data-v2-milo-new]', S.panel);
  if (hb) { hb.setAttribute('aria-expanded', String(!!S.showHistory)); hb.classList.toggle('is-on', !!S.showHistory); hb.setAttribute('aria-disabled', String(!!S.busy)); hb.title = S.busy ? 'Conversation history (stop the answer first)' : 'Conversation history'; }
  if (nb) { nb.setAttribute('aria-disabled', String(!!S.busy)); nb.title = S.busy ? 'New conversation (stop the answer first)' : 'New conversation'; }
  // Save follows the conversation on screen: its key is the conversation's own id, and it is asked about once it has
  // an answer (a blank conversation has nothing saved)
  const sb = S.panel && $('.drawer-head [data-v2-save="conversation"]', S.panel);
  if (sb) {
    const key = keyOf('conversation', [], { conversation: S.conv.id }), answered = S.conv.messages.some((m) => m.role === 'assistant' && String(m.content || '').trim());
    if (sb.dataset.v2SaveKey !== key) { sb.dataset.v2SaveKey = key; sb.setAttribute('aria-pressed', 'false'); sb.title = 'Save conversation to Saved research'; sb.setAttribute('aria-label', sb.title); }
    sb.setAttribute('aria-disabled', String(!answered || !!S.busy));
    if (answered && !S.busy && knownSaved(key) === undefined && store.signedIn()) refreshSaved(key);
  }
}
// What Save conversation keeps (Saved research, Handoff 5): each message, and each answer's sources with the times
// they were read and the page it was asked from, as they are now. The cited figures are the copy's own: reopening it
// never re-reads them.
/** The saved form of a conversation, from its messages and each answer's facts (meta). Pure, so it can be tested. */
export function conversationSpec(conv, facts, savedFrom = '') {
  const msgs = (conv && conv.messages) || [];
  if (!msgs.some((m) => m.role === 'assistant' && String(m.content || '').trim())) return { blocked: 'Ask Milo something first: a conversation is saved with its answers.' };
  const syms = [];
  msgs.forEach((m, i) => { const sym = (facts.get(i) || {}).symbol; if (m.role === 'assistant' && sym && !syms.includes(sym)) syms.push(sym); });
  if (!syms.length && conv.lastTicker) syms.push(conv.lastTicker);
  const messages = msgs.map((m, i) => {
    const inf = facts.get(i) || {}, o = { role: m.role, content: String(m.content || '') };
    if (inf.policyLine) o.policy = inf.policyLine; if (inf.amended) o.amended = inf.amended; if (inf.level) o.level = inf.level;
    if (m.role === 'assistant') {
      o.sources = { citations: inf.citations || [], read: inf.read || [], retrieved: inf.retrieved || [], loaded: inf.loaded || [] };
      const f = (inf.context || {}).focus; if (f) o.focus = { view_label: f.view_label || '', ticker: f.ticker || inf.symbol || '', captured_at: f.captured_at || '' };
    }
    return o;
  });
  const first = (msgs.find((m) => m.role === 'user') || {}).content || '';
  return { kind: 'conversation', tickers: syms.slice(0, 4), ref: { conversation: conv.id },
    summary: { question: String(first).slice(0, 300), answers: msgs.filter((m) => m.role === 'assistant').length },
    conversation: { messages, saved_from: savedFrom } };
}
provideSave('conversation', () => (S.busy ? { blocked: 'Milo is still answering. Save the conversation once the answer is finished.' } : conversationSpec(S.conv, meta, contextLabel('auto'))));
/** A saved conversation as Milo's state: its messages, a log that first says when it was saved and that its figures
 *  are as of then, and each answer's facts as saved (its sources, when each was read, the page it was asked from).
 *  Pure, so it can be tested; openSaved puts it on screen. */
export function restoreSaved(item, newConvId = newId) {
  const conv = item.conversation || {}, msgs = (conv.messages || []).filter((m) => m && (m.role === 'user' || m.role === 'assistant'));
  const ticker = (item.tickers || []).find((x) => !(item.gone || []).includes(x)) || null;
  const out = { id: (item.ref || {}).conversation || newConvId(), messages: msgs.map((m) => ({ role: m.role, content: m.content })), lastTicker: ticker };
  const at = item.updated_at || item.created_at, gone = item.gone || [];
  const note = `Saved on ${dayText(at)} at ${prefs.clock(at)} ${prefs.zoneAbbrev(prefs.zone(), new Date(at))}; figures as of then. Each answer keeps the sources it had and when they were read.${gone.length ? ` ${gone.join(', ')} ${gone.length === 1 ? 'is' : 'are'} no longer available.` : ''}`;
  const facts = new Map();
  msgs.forEach((m, i) => {
    if (m.role !== 'assistant') return;
    const src = m.sources || {}, f = m.focus || {};
    facts.set(i, { question: (msgs[i - 1] || {}).content || '', symbol: f.ticker || ticker, policyLine: m.policy || '', amended: m.amended || '', level: m.level || '',
      citations: src.citations || [], read: src.read || [], retrieved: src.retrieved || [], loaded: src.loaded || [],
      context: { focus: { scope: 'auto', view_label: f.view_label || '', ticker: f.ticker || ticker, captured_at: f.captured_at || '' } } });
  });
  return { conv: out, items: [{ kind: 'note', text: note }, ...out.messages.map((m, i) => ({ kind: 'msg', i }))], facts, ticker };
}
/**
 * A saved conversation reopened (Saved research, Handoff 5), with the sources each answer had, as saved. Milo's
 * context is its ticker, so a follow-up is about the same company; nothing is sent until the reader asks.
 */
export async function openSaved(item, { opener } = {}) {
  const r = restoreSaved(item);
  await openMilo({ opener, symbol: r.ticker || undefined, about: `Saved: ${item.name}` });
  if (S.busy) { toast(WAIT_HISTORY); return; }
  S.conv = r.conv; S.report = null; meta.clear(); SC.i = null;
  r.facts.forEach((v, k) => meta.set(k, v));
  S.items = r.items;
  S.showHistory = false; S.toEnd = false; S.follow = true; S.view = null; paintChrome(); paintLog();
}
const WAIT_HISTORY = 'Milo is still answering. Stop the answer first, then open your history.';
const WAIT_NEW = 'Milo is still answering. Stop the answer first, then start a new conversation.';
function paintLog(stick = true) {
  const h = host(); if (!h) return;
  const log = $('.milo-log', h);
  draw(log, logHTML());
  S.fresh = null;   // the question just sent enters once, not on every repaint
  mountAnswerCharts(log); mountAnswerFigures(log);
  // the reader's own question always comes into view; new output follows only a reader following the end
  if (S.toEnd || (stick && S.follow)) log.scrollTop = log.scrollHeight;
  if (S.showHistory || !S.items.length) log.scrollTop = 0;
  S.toEnd = false;
  scoutAfterPaint(); syncLatest();
}
// Whether new output follows (post-demo Phase 07). A reader at the end of the conversation is followed; one who has
// moved up is left where they are, however near the end, so the answer arriving never pulls the view back down. Optic
// only ever scrolls to the end, so a view that moved up was moved by the reader; the browser pulling it in when the
// content gets shorter leaves it at the end, which is still following. Within 60 px of the end is the end again.
// Measured against where the view was before a frame's changes, not after: a chart or a paragraph taller than the
// old allowance (120 px) used to leave a following reader behind.
function noteScroll(l) {
  if (S.showHistory || !S.items.length) return;
  const d = l.scrollHeight - l.scrollTop - l.clientHeight, was = S.lastTop === null ? l.scrollTop : S.lastTop;
  if (l.scrollTop < was - 1 && d > 4) S.follow = false;
  else if (d < 60) S.follow = true;
  S.lastTop = l.scrollTop; S.view = { top: l.scrollTop, end: S.follow };
}
// a chart or a figure is drawn once its data comes, after its answer: a reader following the end stays at it
function keepEnd() { const h = host(), log = h && $('.milo-log', h); if (log && S.follow && !S.showHistory && S.items.length) log.scrollTop = log.scrollHeight; }
// Back where the reader was, when the panel opens again or history gives the conversation back: following the end, or
// at the place they had scrolled up to
function restoreView() {
  const h = host(), log = h && $('.milo-log', h); if (!log || S.showHistory || !S.items.length) return;
  const v = S.view; S.lastTop = null;
  S.follow = !v || v.end;
  log.scrollTop = S.follow ? log.scrollHeight : v.top;
  syncLatest();
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
// The box holds a question of up to MAX_Q characters and cuts anything longer, as typed or pasted: when it is full it
// says so, and how much of a paste was left out (post-demo Phase 07; the cut was silent)
function paintLimit(ta) {
  const n = host() && $('#milo-limit', host()); if (!n || !ta) return;
  const full = ta.value.length >= MAX_Q, max = MAX_Q.toLocaleString('en-US');
  if (!full) S.cutPaste = 0;
  const text = !full ? '' : S.cutPaste ? `A question can be up to ${max} characters, so the last ${S.cutPaste.toLocaleString('en-US')} characters of what you pasted were left out.` : `That is ${max} characters, the most a question can hold.`;
  n.hidden = !full; if (n.textContent !== text) n.textContent = text;
}
function paintForm() {
  const h = host(); if (!h) return;
  const b = blocked(), send = $('[data-v2-milo-send]', h), stop = $('[data-v2-milo-stop]', h), ta = $('#milo-q', h);
  paintLimit(ta);
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

// The answer still streaming (post-demo Phase 07). Paragraphs that are finished are drawn once and appended, and only
// the paragraph still arriving is drawn again each frame, so a finished paragraph, a chart or a figure inside it, and
// text the reader has selected are never torn down and drawn again. Answer markdown is drawn paragraph by paragraph
// (core/milo-text.js mdLite), and settledEnd only ends the finished part where drawing it in pieces gives what drawing
// the whole answer gives, so the answer reads the same while it arrives, when it ends and when it is drawn again from
// history. The arriving paragraph is drawn as markdown too (streamingHTML). At most one paint a frame, however many
// events arrived in it.
// The card is for the wait before any text: it has room for the figure and it is the only thing in the bubble.
// Once words are arriving they take the space back and he goes to the inline line beside them (the owner's
// reference sheet, and its note: he shrinks rather than disappears). Measured on the panel, not on the bubble,
// which is the panel less its padding and the answer's own indent (403px inside a 444px panel, measured
// 2026-11-03) and would have put the threshold on a number with no meaning. A phone never gets the card: there
// the panel is the whole screen and the answer has to come first.
const CARD_MIN = 400;
// How long "Answer ready" stays before the row goes. Long enough to read three words, short enough not to sit
// under a finished answer: the follow-ups below it are already live while it shows.
const DONE_MS = 1600;
const expandedNow = (L, width) => !L.text && !isPhoneNow() && (width || 0) >= CARD_MIN;
// What sits under the activity: the quiet notice, and the lookups so far where the card is not already listing
// them. One string, as before; the activity above it is patched in place rather than redrawn (syncActivity).
function liveLinesHTML(L, expanded) {
  const got = (L.got || []).filter((r) => r && r.ok !== false).map((r) => r.label || (r.symbols || []).join(', ')).filter(Boolean);
  return `${L.quiet ? `<p class="milo-quiet" role="status">${esc(QUIET_TEXT)}</p>` : ''}${got.length && !expanded ? `<p class="milo-sofar">Looked up so far: ${esc([...new Set(got)].join('; '))}. Every source is listed when the answer is complete.</p>` : ''}`;
}
/** The figure inside the activity, in its own slot: the header bust keeps the gestures the end of an answer plays
 *  on it, and starting this one never stops that one. */
function scoutInActivity(root) {
  const O = OS(), box = root && root.querySelector('.milo-doing'); if (!O || !box) return;
  const el = box.querySelector('.scout'); if (!el) return;
  const c = O.attach(el, { slot: 'activity' }); if (!c) return;
  // The answer landed: the small wave he already has, played once into the resting pose. It is the gesture
  // the owner's sheet asks for in state 5, and it is his own frames, not a new drawing of him.
  if (box.dataset.doing === 'complete') { c.set('idle', 'ack'); return; }
  c.set(box.dataset.scout || 'thinking');
}
let liveFrame = null;
function paintLive() {
  if (liveFrame) return;
  liveFrame = requestAnimationFrame(() => {
    liveFrame = null;
    const h = host(), L = S.live; if (!h || !L || S.showHistory) return;
    const node = $(`[data-v2-milo-i="${L.i}"] .milo-bubble`, h); if (!node) { paintLog(); return; }
    if (node.dataset.v2Live !== String(L.i)) {
      // first paint into this bubble (or the log was redrawn): its parts, and the finished paragraphs so far, once
      node.dataset.v2Live = String(L.i); L.cut = 0; L.seen = {};
      node.innerHTML = '<div class="milo-settled"></div><div class="milo-tail"></div><div class="milo-live-lines"></div>';
    }
    const text = L.text, followAt = text.search(FOLLOW_AT), end = settledEnd(text, followAt);
    if (end > L.cut) {
      const settled = $('.milo-settled', node);
      settled.insertAdjacentHTML('beforeend', renderAnswer(text.slice(L.cut, end), L.symbol, L.seen).html);
      L.cut = end;
      mountAnswerCharts(settled); mountAnswerFigures(settled);
    }
    const tail = $('.milo-tail', node), th = streamingHTML(text.slice(L.cut, followAt >= 0 ? Math.max(L.cut, followAt) : text.length), L.symbol);
    if (tail.v2Html !== th) { tail.innerHTML = th; tail.v2Html = th; }
    const panel = S.panel && document.contains(S.panel) ? S.panel : h;
    const lines = $('.milo-live-lines', node), expanded = expandedNow(L, panel.getBoundingClientRect().width);
    let rest = $('.milo-live-rest', lines);
    if (!rest) { lines.insertAdjacentHTML('beforeend', '<div class="milo-live-rest"></div>'); rest = $('.milo-live-rest', lines); }
    syncActivity(lines, L.act, { expanded, stepWords: (raw) => stepWords(raw, L.symbol) });
    // every paint, not only when it was rebuilt: the figure stays, and this is what moves him to the new pose.
    // attach gives the figure already there, and set on the pose he is in is not news, so this costs nothing.
    scoutInActivity(lines);
    const lh = liveLinesHTML(L, expanded);
    if (rest.dataset.html !== lh) { rest.innerHTML = lh; rest.dataset.html = lh; }
    const log = $('.milo-log', h); if (log && S.follow) log.scrollTop = log.scrollHeight;
    syncLatest();
    // the form changes twice in an answer (sending, then streaming), not every frame
    const fs = L.text ? 'streaming' : 'sending'; if (L.formState !== fs) { L.formState = fs; paintForm(); }
  });
}
/** The answer just finished, drawn in its final form in place: the finished paragraphs already on screen stay (with
 *  any chart in them), the last one is added, and only what sits around the text (follow-ups, sources, actions, the
 *  incomplete note) is drawn new. The rest of the conversation is not touched. False when it cannot be done in place
 *  (the text was amended, or the bubble is not the live one), and the caller draws the log instead. */
function paintFinished(i, live, ok) {
  const h = host(); if (!h || !live || live.amended) return false;
  const el = $(`[data-v2-milo-i="${i}"]`, h), it = S.items.find((x) => x.kind === 'msg' && x.i === i);
  const old = el && $('.milo-bubble', el);
  if (!el || !it || !old || old.dataset.v2Live !== String(i) || S.items[S.items.length - 1] !== it) return false;
  const shown = String((S.conv.messages[i] || {}).content || '').replace(/\n\n\[(Stopped by the reader|Cut off): incomplete\]$/, '');
  const { body } = splitFollowUps(shown);
  const settled = $('.milo-settled', old);
  if (body.length > live.cut) settled.insertAdjacentHTML('beforeend', renderAnswer(body.slice(live.cut), live.symbol, live.seen || {}).html);
  settled.replaceWith(...settled.childNodes);
  const tailNode = $('.milo-tail', old); if (tailNode) tailNode.remove();
  // State 5 of the owner's sheet: the answer is complete, and he says so for a moment in the place he was already
  // standing. Nothing waits on it: the answer, its sources, its follow-ups and its actions are drawn in this same
  // frame, and the row he was in is removed a moment later, which is the one move it was going to make anyway.
  const linesNode = $('.milo-live-lines', old);
  if (linesNode && ok && live.act) {
    const done = activityHTML({ ...live.act, state: 'complete', said: '' }, { expanded: false });
    if (done) {
      linesNode.innerHTML = done; delete linesNode.dataset.html; scoutInActivity(linesNode);
      setTimeout(() => { if (linesNode.isConnected) linesNode.remove(); }, DONE_MS);
    } else linesNode.remove();
  } else if (linesNode) linesNode.remove();
  delete old.dataset.v2Live;
  const tmp = document.createElement('div'); render(tmp, msgHTML(it));
  const fresh = tmp.firstElementChild, nb = fresh && $('.milo-bubble', fresh);
  if (!fresh || !nb) return false;
  nb.replaceWith(old);
  el.replaceWith(fresh);
  mountAnswerCharts(fresh); mountAnswerFigures(fresh);
  return true;
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
      keepEnd();
    });
  });
}
/* ---------------- charts inside answers ---------------- */
const chartCache = new Map();
function mountAnswerCharts(root) {
  root.querySelectorAll('[data-v2-milo-chart]:not([data-mounted])').forEach((fig) => {
    fig.dataset.mounted = '1';
    const sym = fig.dataset.v2MiloChart, span = fig.dataset.span, key = `${sym} ${span}`, plot = $('.milo-chart-plot', fig);
    // re-asked after ten minutes, and a failure is not kept (Phase 09 cache audit, B04)
    const hit = chartCache.get(key);
    if (!hit || Date.now() - hit.at > 600000) {
      chartCache.set(key, { at: Date.now(), p: api.get(`/api/take-chart/${encodeURIComponent(sym)}?span=${encodeURIComponent(span)}`, { ttl: 600000, timeout: 30000 }).catch(() => { chartCache.delete(key); return null; }) });
    }
    chartCache.get(key).p.then((tc) => {
      if (!document.contains(plot)) return;
      const c = tc && tc.available ? tc.chart : null;
      if (!c || !(c.close || []).length) { plot.innerHTML = `<p class="t-muted">No price history for ${esc(sym)}.</p>`; keepEnd(); return; }
      const levels = [...(tc.supports || []).slice(0, 2), ...(tc.resistances || []).slice(0, 1)].map((l) => l.price).filter(Number.isFinite);
      plot.innerHTML = '<div class="chart-slot" data-chart="take"></div>';
      mountCharts(plot, { take: (w) => lineChart(c.dates.map((d, i) => ({ d, c: c.close[i] })), { w, h: 220, label: `${sym} daily closes`, overlays: levels.map((v) => ({ values: c.dates.map(() => v), cls: 'c0' })), summary: `${sym} daily closes over ${tc.span_words || span}, through ${tc.as_of || ''}${levels.length ? `, with support and resistance at ${levels.map((v) => v.toFixed(2)).join(', ')}` : ''}.` }) });
      const cap = $('figcaption', fig); if (cap) cap.textContent = `${sym}, daily closes over ${tc.span_words || span}, through ${tc.as_of || ''}. Dashed: support and resistance, where price turned before. Source: Yahoo Finance.`;
      keepEnd();
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
  // with the page's context removed, Deep research is about the market too: no company is taken from the page
  const sym0 = S.scope === 'auto' ? onSymbol() : null;
  // Deep research may run on an empty box: on the symbol open, or the market (Classic's runResearch)
  if (deep && !text) text = sym0 ? `Deep research: ${sym0}` : 'Deep research: the market';
  if (!text || S.busy || blocked()) return;
  S.deepHint = false;
  const h = host(), ta = h && $('#milo-q', h);
  // a context that cannot be built or sent goes as none: general mode, said so, never a guessed ticker (Handoff 6)
  let context;
  try { context = buildContext(S.scope, S.conv.lastTicker); JSON.stringify(context); } catch (e) { console.error(e); context = unreadable(route, new Date()); }
  const focusTicker = context.focus.ticker;
  if (context.focus.previous_ticker) S.items.push({ kind: 'note', text: `Now asking about ${focusTicker}. The earlier answers were about ${context.focus.previous_ticker}, and Milo is told so.` });
  // an indicator taken off the chart since the last question: Milo is told, in case an earlier answer leaned on it
  const gone = removedSince(S.conv.lastChart, context.focus);
  if (gone.length) { context.focus.indicators_removed = gone; S.items.push({ kind: 'note', text: `${gone.map((x) => x.label).join(' and ')} ${gone.length === 1 ? 'is' : 'are'} no longer on the chart. Milo is told, in case an earlier answer used ${gone.length === 1 ? 'it' : 'them'}.` }); }
  if (context.focus.chart && focusTicker) S.conv.lastChart = { ticker: focusTicker, indicators: context.focus.chart.indicators.map((x) => ({ id: x.id, label: x.label })) };
  else if (S.conv.lastChart && focusTicker && S.conv.lastChart.ticker !== focusTicker) S.conv.lastChart = null;
  S.conv.messages.push({ role: 'user', content: text }); S.items.push({ kind: 'msg', i: S.conv.messages.length - 1 }); S.fresh = S.conv.messages.length - 1;
  const going = S.files.filter((f) => f.data && !f.error), attachments = going.map((f) => ({ name: f.name, media_type: f.type, data: f.data }));
  if (going.length) meta.set(S.conv.messages.length - 1, { files: going.map((f) => f.name) });
  S.files = [];
  if (focusTicker) S.conv.lastTicker = focusTicker;
  const ai = S.conv.messages.length; // index the answer will take
  S.conv.messages.push({ role: 'assistant', content: '' }); S.items.push({ kind: 'msg', i: ai });
  // a general question is about no company, whatever page it was asked on: its answer is not labelled with the page's
  const answerSym = S.scope === 'auto' && !context.focus.unavailable ? focusTicker || route.symbol || null : focusTicker || null;
  // what the answer is for, as sent; the server's own account (its `context` event) replaces it when it comes
  meta.set(ai, { question: text, symbol: answerSym, context, used: researchOf(context.focus), deep, web: !deep && !!S.web, level: prefs.knowledge() });
  S.busy = true; S.live = { i: ai, text: '', status: MILO_STATES.submitted, symbol: answerSym, lastAt: performance.now(), quiet: false,
    // what he is doing, from the server's own events (ui/milo-activity.js); the line above is still the words
    act: actBegin(deep) };
  if (ta) { ta.value = ''; grow(ta); } S.draft = ''; S.showHistory = false; S.showSettings = false; S.toEnd = true; S.follow = true;
  paintChrome(); paintLog(); paintForm(); paintLive();
  scoutTo(ai, 'thinking', 'ack');
  const ctl = new AbortController(); S.abort = ctl; S.sentAt = performance.now();
  let finished = false, ended = '', failed = null;
  const heard = () => { if (!S.live) return; S.live.lastAt = performance.now(); if (S.live.quiet) { S.live.quiet = false; paintLive(); } };
  const quietT = setInterval(() => { if (S.live && !S.live.quiet && performance.now() - S.live.lastAt > QUIET_MS) { S.live.quiet = true; paintLive(); } }, 2000);
  try {
    const askedText = /^Deep research: /.test(text) && deep ? null : text;
    const res = await fetch(deep ? '/api/research' : '/api/chat', {
      method: 'POST', credentials: 'same-origin', signal: ctl.signal,
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', 'X-Optic-CSRF': (document.cookie.match(/(?:^|; )optic_csrf=([^;]*)/) || [])[1] || '' },
      body: JSON.stringify(deep
        ? { ticker: focusTicker || sym0 || null, question: askedText || (focusTicker || sym0 ? null : MARKET_BRIEF), context, mode: prefs.knowledge() }
        : { messages: S.conv.messages.slice(0, ai).map((m) => ({ role: m.role, content: m.content })), context, web: !!S.web, attachments, persona: persona(), mode: prefs.knowledge(), horizon: horizon() }),
    });
    // the server has the question (and says its own first step at once)
    heard();
    // the chat route says its own first step at once ("gathering"); deep research has none, so the panel says this one
    if (deep && res.ok && S.live && !S.live.text) { S.live.status = MILO_STATES.preparing; paintLive(); }
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
        buf += dec.decode(step.value, { stream: true }); heard();
        const chunks = buf.split('\n\n'); buf = chunks.pop();
        for (const c of chunks) {
          let ev = 'message', data = '';
          c.split('\n').forEach((line) => { if (line.startsWith('event: ')) ev = line.slice(7).trim(); else if (line.startsWith('data: ')) data += line.slice(6); });
          if (!data) continue;
          let p; try { p = JSON.parse(data); } catch (e) { continue; }
          if (ev === 'delta') { S.live.text += p.text || ''; S.live.status = ''; S.live.act = actOn(S.live.act, 'delta'); S.conv.messages[ai].content = S.live.text; paintLive(); if (SC.i === ai && SC.state !== 'streaming') scoutTo(ai, 'streaming'); }
          else if (ev === 'status') { const w = stepWords(String(p.state || ''), S.live.symbol); S.live.status = w; S.live.act = actOn(S.live.act, 'status', p); paintLive(); if (SC.i === ai && SC.state !== 'streaming') scoutTo(ai, SEARCHING.has(String(p.state || '')) ? 'searching' : 'thinking'); }
          // what the server used for this answer (Handoff 6): the line above it says so, and it is kept with it
          else if (ev === 'context') { const m = meta.get(ai); if (m && p && typeof p === 'object') { m.used = p; paintAbout(ai); } }
          else if (ev === 'attachments') { const m = meta.get(ai); if (m && Array.isArray(p.problems)) m.notSent = [...(m.notSent || []), ...p.problems.map(String)].slice(0, 6); }   // files the model refused, and the reader's own blocks left out (BUG-071)
          else if (ev === 'assumed') { const hz = (((S.personas || {}).horizons || {}).horizons || []).find((x) => x.id === p.horizon); if (hz && p.horizon_source === 'question' && p.horizon !== horizon()) meta.get(ai).assumed = `Answered for a ${hz.label.toLowerCase()} timeframe, from your question. Your setting is unchanged.`; }
          else if (ev === 'retrieved') { S.live.got = Array.isArray(p.items) ? p.items : []; S.live.act = actOn(S.live.act, 'retrieved', p.items); paintLive(); }
          // the advice policy (app/ai_policy.py): the server's own line for a question that asked for a personal decision,
          // and, after the stream, the answer with any sentence that read as personal advice taken out, said in a note
          else if (ev === 'notice') { if (p.kind === 'policy' && p.text) { meta.get(ai).policyLine = String(p.text); paintLive(); } }
          else if (ev === 'amend') { if (typeof p.text === 'string') { S.live.text = p.text; S.live.amended = true; S.conv.messages[ai].content = p.text; meta.get(ai).amended = String(p.note || 'Milo removed a sentence that read as personal investment advice.'); paintLive(); } }
          else if (ev === 'error') { finished = true; failed = { text: p.message || 'Milo could not answer.' }; }
          else if (ev === 'done') { finished = true; Object.assign(meta.get(ai), { citations: p.sources || p.citations || [], read: Array.isArray(p.read) ? p.read : [], retrieved: Array.isArray(p.retrieved) ? p.retrieved : [], loaded: Array.isArray(p.loaded) ? p.loaded : [], named: p.named && typeof p.named === 'object' ? p.named : null }); }
        }
      }
      if (!finished && !ended && !failed) ended = ctl.signal.aborted ? 'stopped' : 'cut';
    }
  } catch (e) {
    if (ctl.signal.aborted) ended = 'stopped';
    else failed = { text: offlineOr('') };
  }
  clearInterval(quietT);
  const reply = S.live ? S.live.text : '', liveWas = S.live;
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
    // part of an answer, then a failure: kept, and marked as cut off rather than saved as if it were complete (BUG-051)
    if (failed && !ended) ended = 'cut';
    if (ended) { meta.get(ai).ended = ended; S.conv.messages[ai].content = `${reply}\n\n[${ended === 'stopped' ? 'Stopped by the reader' : 'Cut off'}: incomplete]`; }
    persist();
  }
  // the finished answer in place when it can be, so the rest of the conversation is not drawn again; a reader at the end
  // of the conversation stays at it
  const lg = host() && $('.milo-log', host());
  if (paintFinished(ai, liveWas, !failed && !ended && !!reply.trim())) { if (S.follow) lg.scrollTop = lg.scrollHeight; scoutAfterPaint(); syncLatest(); } else paintLog();
  paintForm(); loadAllowance();
  // the state, for a screen reader: the log reads the answer itself
  announce(failed ? 'Milo could not answer. Your question is back in the box.' : ended === 'stopped' ? 'Stopped. The answer is incomplete.' : ended === 'cut' ? 'The answer was cut off.' : 'Milo has answered.');
}
// Send turns into Stop in the same place, so a double-click on Send, or Enter on the button just pressed, stopped
// the answer it had started ("Stopped before Milo answered": audit 2026-10-22). Stop listens from 600 ms after Send.
export function stop() { if (S.abort && performance.now() - (S.sentAt || 0) > 600) S.abort.abort(); }

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
  // the card says it may use a Milo message, so pressing it is the go-ahead the Scan page checks for (scan.js, SCAN_GO)
  if (a.kind === 'screen') { try { sessionStorage.setItem('optic.scan.go.v1', String(a.words || '').trim().slice(0, 300)); } catch (e) { /* private mode */ } router.go(`#/scan?q=${encodeURIComponent(a.words)}`); return; }
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
  let vvOff = null, gripOff = null, sizeOff = null;
  drawer.open({
    title: 'Milo', opener, dock: dockFit(window.innerWidth, railW(), storedWidth() || W_DEFAULT, isPhoneNow()) > 0,
    // the redesign's compact header: Milo beside his name, and history, a new conversation and close as icons
    head: html`<div class="milo-id"><div><h2 id="milo-title" tabindex="-1">Milo</h2><p class="milo-sub">Research assistant</p></div></div>`,
    actions: html`${saveButton('conversation', keyOf('conversation', [], { conversation: S.conv.id }), { iconOnly: true, label: 'Save conversation' })}<button type="button" class="icon-btn" data-v2-milo-history aria-expanded="false" aria-controls="milo-history" aria-label="Conversation history" title="Conversation history">${icon('history')}</button>
      <button type="button" class="icon-btn" data-v2-milo-new aria-label="New conversation" title="New conversation">${icon('compose')}</button>`,
    body: html`<div class="milo"><div class="milo-chrome">${chromeHTML()}</div>
      <div class="milo-log-wrap"><div class="milo-log" role="log" aria-live="polite" aria-label="Conversation with Milo">${logHTML()}</div>
        <button type="button" class="milo-latest" data-v2-milo-latest hidden>${icon('arrowDown')}<span>Latest</span></button></div>
      <form class="milo-form" data-v2-milo-form data-state="idle"><div class="milo-suggest-slot" data-v2-milo-suggest></div><div data-v2-milo-tools>${toolsHTML()}</div><div data-v2-milo-files>${filesHTML()}</div><div class="milo-compose">
        <button type="button" class="milo-attach" data-v2-milo-attach aria-label="Attach an image or PDF" title="Attach an image or PDF: PNG, JPEG, GIF, WebP or PDF, up to 4 files of 5 MB each. You can also drop them here.">${icon('clip')}</button>
        <input type="file" hidden multiple accept="${Object.keys(ATTACH_TYPES).join(',')}" data-v2-milo-file tabindex="-1"><label class="sr" for="milo-q">Your question to Milo</label>
        <textarea id="milo-q" rows="1" maxlength="${MAX_Q}" placeholder="${placeholder()}" aria-describedby="milo-attached milo-allow milo-limit">${S.draft}</textarea>
        <button type="submit" class="milo-send" data-v2-milo-send aria-label="Send" title="Send (Enter). Shift and Enter for a new line">${icon('send')}</button>
        <button type="button" class="milo-stop" data-v2-milo-stop aria-label="Stop the answer" title="Stop the answer" hidden>${icon('stop')}</button></div>
        <p class="milo-limit" id="milo-limit" role="status" hidden></p>
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
      paintLog(); restoreView(); paintForm();
      // the log gets shorter when the composer grows under it (suggestions, files, a line of text) or a phone's keyboard
      // opens: a reader following the end stays at it, where before the view was left up to 56 px short
      const lg = $('.milo-log', S.mounted);
      if (lg && typeof ResizeObserver === 'function') { const ro = new ResizeObserver(() => keepEnd()); ro.observe(lg); sizeOff = () => ro.disconnect(); }
      const w = OS() && welcomeEl(S.mounted);
      if (w && Date.now() - SC.lastWave > 20000) { const c = OS().attach(w, { slot: 'welcome' }); if (c) { SC.lastWave = Date.now(); c.gesture('wave'); } }
      const ta = $('#milo-q', S.mounted); grow(ta);
      if (ta && !matchMedia('(pointer: coarse)').matches) { requestAnimationFrame(() => { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }); }
      loadAllowance(); loadChoices();
      api.get('/api/health', { ttl: 60000 }).then((hh) => { S.health = hh; paintChrome(); }, () => {});
      if (sendNow && S.draft) send(S.draft);
    },
    closed: () => { if (vvOff) vvOff(); if (sizeOff) { sizeOff(); sizeOff = null; } if (gripOff) { gripOff(); gripOff = null; } S.panel = null; S.web = false; S.deepHint = false; layout(); const ta = S.mounted && $('#milo-q', S.mounted); if (ta) S.draft = ta.value; SC.menu = false; S.showSettings = false; S.mounted = null; S.panel = null; },
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
    // a narrow panel (beside the page it is about 440 px) gives the context bar's words the room "Change" took
    panel.classList.toggle('milo-narrow', w < 500);
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
  return () => { window.removeEventListener('resize', onResize); grip.remove(); panel.style.removeProperty('--milo-w'); panel.classList.remove('milo-panel', 'milo-narrow'); };
}

// History and a new conversation, from the header's icons or the moved-symbol note; neither touches the draft
function toggleHistory(open = !S.showHistory) {
  if (open && S.busy) { toast(WAIT_HISTORY); return; }
  S.showHistory = open; S.showSettings = false;
  paintChrome(); paintLog(false);
  if (!open) restoreView();
  const h = host(); if (open && h) { const hd = $('#milo-hist-h', h); if (hd) { hd.setAttribute('tabindex', '-1'); hd.focus({ preventScroll: true }); } }
  else { const hb = S.panel && $('.drawer-head [data-v2-milo-history]', S.panel); if (hb) hb.focus({ preventScroll: true }); }
}
function newConversation() {
  if (S.busy) { toast(WAIT_NEW); return; }
  S.conv = blankConv(); S.items = []; meta.clear(); SC.i = null; S.showHistory = false; S.follow = true; S.view = null; S.report = null;   // a report form belongs to its own conversation (BUG-051)
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

// An answer keeps the level it was written for (Phase 05, directive 05 section 6). When the reader has moved since, it
// says so and offers to ask again at the new level: drafted into the box, sent only when the reader presses Send, and
// the answer itself is never rewritten.
const levelLabel = (id) => ((((S.modes || {}).modes) || []).find((m) => m.id === id) || {}).label || '';
function levelNote(info, live) {
  if (live || !info || !info.level || info.deep) return '';
  const now = prefs.knowledge(), was = levelLabel(info.level), is = levelLabel(now);
  if (info.level === now || !was || !is) return '';
  const q = String(info.question || '').replace(/\s+/g, ' ').trim().slice(0, 90);
  return html`<p class="milo-assumed milo-level-was">Explained for ${was}. Your level is now ${is}. <button type="button" class="textlink" data-v2-milo-follow="${q ? `Explain your answer to "${q}" again, for the ${is} level.` : `Explain that again, for the ${is} level.`}">Ask again for ${is}</button></p>`;
}

// the level moved while a conversation is open: say where the change starts, and leave what was written alone.
// Registered once, here: wire() runs on every open of the panel.
prefs.onChange((what) => {
  if ((what !== 'knowledge' && what !== 'knowledge-synced') || !S.conv.messages.length) return;
  const is = levelLabel(prefs.knowledge());
  if (!is) return;
  S.items.push({ kind: 'note', text: `From here on Milo explains for ${is}. Earlier answers stay as they were written.` });
  if (S.mounted && S.mounted.isConnected) paintLog();
});

function wire(root) {
  root.addEventListener('submit', (e) => {
    if (e.target.closest('[data-v2-milo-form]')) { e.preventDefault(); const ta = $('#milo-q', root); if (!ta.value.trim()) { ta.focus(); return; } send(ta.value); return; }
    const rf = e.target.closest('[data-v2-milo-report-form]');
    if (rf) {
      e.preventDefault();
      const i = Number(rf.dataset.v2MiloReportForm), text = ($('textarea', rf) || {}).value || '';
      if (!text.trim()) { S.report = { conv: S.conv.id, i, text, err: 'Say what is wrong first, in a few words.' }; paintLog(false); const ta = $('.milo-report textarea', root); if (ta) ta.focus(); return; }
      sendReport(i, text);
    }
  });
  // the attached list stays open or shut as the reader left it when the chrome redraws (toggle does not bubble)
  root.addEventListener('toggle', (e) => { if (e.target.classList && e.target.classList.contains('milo-parts')) S.partsOpen = e.target.open; }, true);
  // a report being written survives the log redrawing under it
  root.addEventListener('input', (e) => { if (S.report && e.target.matches && e.target.matches('.milo-report textarea')) S.report.text = e.target.value; });
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
  root.addEventListener('input', (e) => { if (e.target.id === 'milo-q') { const was = !S.draft.trim(), now = !e.target.value.trim(); S.draft = e.target.value; grow(e.target); scoutListen(e.target.value); paintLimit(e.target); if (was !== now) paintSuggest(); } });
  // a pasted image is attached, as a dropped one is; pasted text past the limit is measured, to say how much was cut
  root.addEventListener('paste', (e) => {
    const ta = e.target; if (ta.id !== 'milo-q' || !e.clipboardData) return;
    const files = [...(e.clipboardData.files || [])], text = e.clipboardData.getData('text/plain') || '';
    if (files.length && !text) { e.preventDefault(); if (!blocked()) addFiles(files); return; }
    const room = MAX_Q - (ta.value.length - Math.abs((ta.selectionEnd || 0) - (ta.selectionStart || 0)));
    S.cutPaste = text.length > room ? text.length - Math.max(0, room) : 0;
  });
  root.addEventListener('scroll', (e) => { if (e.target.classList && e.target.classList.contains('milo-log')) { noteScroll(e.target); syncLatest(); } }, true);
  // a wheel turned up is a reader going back to read, before the view has even moved
  root.addEventListener('wheel', (e) => { const l = e.deltaY < 0 && e.target.closest && e.target.closest('.milo-log'); if (l && l.scrollTop > 0) S.follow = false; }, { passive: true });
  root.addEventListener('change', (e) => {
    const t = e.target;
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
      const sm = $('.milo-ctx-pick > .milo-ctx-btn', root); if (sm) sm.focus();
      announce(S.scope === 'none' ? 'Page context removed. Milo answers in general, about no company.' : S.scope === 'market' ? 'Milo will see the market only.' : `Milo will see ${contextLabel('auto')}.`);
      return;
    }
    if ((b = t('[data-v2-milo-pick]'))) {
      S.pick = b.dataset.v2MiloPick || null;
      const d = b.closest('details'); if (d) d.open = false;
      paintChrome(); if (!S.items.length) paintLog(false);
      const sm = $('.milo-ctx-pick > .milo-ctx-btn', root); if (sm) sm.focus();
      announce(S.pick ? `Milo will answer about ${S.pick}.` : 'Milo will answer about the comparison as a whole.');
      return;
    }
    if ((b = t('[data-v2-milo-pp]'))) { pickPersona(b.dataset.v2MiloPp, root, true); return; }
    if ((b = t('[data-v2-milo-hz]'))) { setPref(HORIZON_KEY, b.dataset.v2MiloHz); paintChrome(); const hb = $(`[data-v2-milo-hz="${b.dataset.v2MiloHz}"]`, root); if (hb) hb.focus(); return; }
    if ((b = t('[data-v2-milo-start]'))) { send(b.dataset.v2MiloStart); return; }
    if (t('[data-v2-milo-latest]')) { const log = $('.milo-log', root); S.follow = true; if (log) log.scrollTo({ top: log.scrollHeight, behavior: reducedMotion() ? 'auto' : 'smooth' }); return; }
    if (t('[data-v2-milo-stop]')) { stop(); return; }
    if (t('[data-v2-milo-history-close]')) { toggleHistory(false); return; }
    if (t('[data-v2-milo-history]')) { toggleHistory(); return; }
    if (t('[data-v2-milo-new]')) { newConversation(); return; }
    if ((b = t('[data-v2-milo-open]'))) {
      if (S.busy) return;
      const c = loadHistory().find((x) => x.id === b.dataset.v2MiloOpen); if (!c) return;
      S.conv = { id: c.id, messages: (c.messages || []).map((m) => ({ role: m.role, content: m.content })), lastTicker: c.ticker || null, lastChart: null }; S.report = null;
      meta.clear(); SC.i = null; S.items = S.conv.messages.map((m, i) => ({ kind: 'msg', i }));
      S.conv.messages.forEach((m, i) => { if (m.role === 'assistant') { const saved = (c.messages || [])[i] || {}; meta.set(i, { question: (S.conv.messages[i - 1] || {}).content || '', symbol: c.ticker || null, policyLine: saved.policy || '', amended: saved.amended || '', used: keepUsed(saved.context), level: saved.level || '' }); } });
      S.showHistory = false; S.toEnd = true; S.follow = true; S.view = null; paintChrome(); paintLog(); const ta = $('#milo-q', root); if (ta) ta.focus(); return;
    }
    if ((b = t('[data-v2-milo-del]'))) { const id = b.dataset.v2MiloDel; if (S.busy && id === S.conv.id) { toast(WAIT_HISTORY); return; } saveHistory(loadHistory().filter((c) => c.id !== id)); if (S.conv.id === id && !S.busy) { S.conv = blankConv(); S.items = []; meta.clear(); } paintChrome(); paintLog(false); const hd = $('#milo-hist-h', root); if (hd) { hd.setAttribute('tabindex', '-1'); hd.focus({ preventScroll: true }); } return; }
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
    if ((b = t('[data-v2-milo-report]'))) {
      const i = Number(b.dataset.v2MiloReport);
      S.report = S.report && S.report.i === i && S.report.conv === S.conv.id ? null : { conv: S.conv.id, i, text: '' }; paintLog(false);
      const form = S.report && $(`[data-v2-milo-report-form="${i}"]`, root);
      if (form) { form.scrollIntoView({ block: 'nearest' }); $('textarea', form).focus({ preventScroll: true }); }
      return;
    }
    if (t('[data-v2-milo-report-cancel]')) { const i = S.report && S.report.i; S.report = null; paintLog(false); const rb = $(`[data-v2-milo-report="${i}"]`, root); if (rb) rb.focus(); return; }
    if ((b = t('[data-v2-milo-drop]')) || (b = t('[data-v2-milo-undrop]'))) {
      const k = b.dataset.v2MiloDrop || b.dataset.v2MiloUndrop;
      if (b.dataset.v2MiloDrop) S.dropped.add(k); else S.dropped.delete(k);
      S.partsOpen = true; paintChrome();
      const again = $('.milo-parts summary', root); if (again) again.focus();
      return;
    }
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
// for the tests (tests/test_milo_context_bar.py): the bar as drawn, and the panel's state
export const _test = { ctxHTML: () => ctxHTML(), state: S };
