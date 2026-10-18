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
import { html, render, $, raw } from '../core/dom.js';
import * as drawer from './drawer.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import * as prefs from '../core/prefs.js';
import * as router from '../core/router.js';
import { holds } from '../core/device.js';
import { esc, compact } from '../core/format.js';
import { GROUPS, SETTINGS } from '../nav.js';
import { renderAnswer, streamingTail, sourcesAsText, STUDIES, SECTIONS as ACT_SECTIONS } from '../core/milo-text.js';
import { lineChart, mountCharts } from './chart.js';
import { CLASSIC } from '../core/classic.js';
import { miloNotice } from '../core/legal.js';

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
/** Pages register what Milo may see from them, as they render. */
export function provideContext(fn) { provider = typeof fn === 'function' ? fn : null; }
/** Called by the app on every navigation, before the new page renders. */
export function resetContext(r) { provider = null; route = r || { view: 'home' }; asked = null; }
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
  return { ...ctx, focus };
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
const S = { conv: blankConv(), items: [], busy: false, abort: null, scope: 'auto', showHistory: false, allowance: null, personas: null, modes: null, draft: '', live: null, mounted: null, symbolAtAsk: null };
// items: what the log shows this session: {kind:'msg', i} for conv.messages[i], or {kind:'note', text}; meta per message index
const meta = new Map();
const persona = () => { try { return localStorage.getItem(PERSONA_KEY) || 'neutral'; } catch (e) { return 'neutral'; } };
const horizon = () => { try { return localStorage.getItem(HORIZON_KEY) || 'auto'; } catch (e) { return 'auto'; } };
const setPref = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } };

export function button(label, { ask, context, symbol, cls = '' } = {}) {
  return html`<button type="button" class="btn btn-milo ${cls}" data-v2-milo="${ask || ''}" data-v2-milo-ctx="${context || ''}" data-v2-milo-sym="${symbol || ''}">${label}</button>`;
}

/* ---------------- allowance and blocking ---------------- */
function blocked() {
  const r = S.allowance;
  if (!r) return null;
  const ai = r.ai || {}, a = r.allowance || {};
  if (ai.enabled === false) return { kind: 'off', text: 'Milo is switched off on this deployment, so it cannot answer questions. Every other part of Optic works without it.' };
  if (a.requires_account && !store.signedIn()) return { kind: 'signin', text: 'Milo needs a free account. Sign in or create one to ask.' };
  if (Number.isFinite(a.allowed) && a.allowed > 0 && a.left === 0) return { kind: 'spent', text: `You have used today's ${a.allowed} questions.${a.next_at ? ` The next one is available ${new Date(a.next_at).toLocaleString('en-US', { weekday: 'short', hour: 'numeric', minute: '2-digit' })}.` : ''}` };
  return null;
}
function allowanceLine() {
  const a = (S.allowance || {}).allowance || {};
  if (blocked()) return '';
  return Number.isFinite(a.left) && Number.isFinite(a.allowed) && a.allowed > 0 ? `${a.left} of ${a.allowed} questions left today.` : '';
}
async function loadAllowance() { try { S.allowance = await api.get('/api/ai-allowance', { force: true, timeout: 10000 }); } catch (e) { /* the panel still opens */ } paintChrome(); }
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
  if (m.role === 'user') return html`<div class="milo-msg milo-you"><p class="milo-who">You</p><div class="milo-bubble">${m.content}</div></div>`;
  const shown = String(m.content || '').replace(/\n\n\[(Stopped by the reader|Cut off): incomplete\]$/, '');
  const { html: body, ups } = renderAnswer(shown, info.symbol || null);
  return html`<div class="milo-msg milo-bot" data-v2-milo-i="${it.i}"><p class="milo-who">Milo</p>
    ${info.assumed ? html`<p class="milo-assumed">${info.assumed}</p>` : ''}
    <div class="milo-bubble">${raw(body)}</div>
    ${info.ended || /\[(Stopped by the reader|Cut off): incomplete\]$/.test(m.content || '') ? html`<p class="milo-ended" role="note">${(info.ended || (/Stopped by the reader/.test(m.content) ? 'stopped' : 'cut')) === 'stopped' ? 'Stopped by you. This answer is incomplete.' : 'The connection ended before Milo finished. This answer is incomplete.'}</p>` : ''}
    ${ups.length ? html`<div class="chips milo-ups">${ups.map((q) => html`<button type="button" class="chip" data-v2-milo-follow="${q}">${q}</button>`)}</div>` : ''}
    ${sourceLists(info)}
    <div class="cluster milo-acts"><button type="button" class="textlink" data-v2-milo-copy="${it.i}">Copy</button>${info.question ? html`<button type="button" class="textlink" data-v2-milo-again="${it.i}">Ask again</button>` : ''}</div></div>`;
}
function sourceLists(info) {
  const cites = info.citations || [], read = info.read || [], got = info.retrieved || [];
  return html`${cites.length ? html`<div class="milo-sources"><p class="t-label">Sources</p>${cites.map((c) => (/^https?:\/\//i.test(c.url || '') ? html`<a href="${c.url}" target="_blank" rel="noopener">${c.title || c.url}</a>` : html`<span>${c.title || ''}</span>`))}</div>` : ''}
    ${read.length ? html`<details class="more-inline milo-read"><summary>Sources Milo read (${read.length})</summary><ul class="plain">${read.map((r) => html`<li>${/^https?:\/\//i.test(r.url || '') ? html`<a href="${r.url}" target="_blank" rel="noopener">${r.source}</a>` : r.source} <small class="t-muted">${[r.what, r.period].filter(Boolean).join(', ')}</small></li>`)}</ul></details>` : ''}
    ${got.length ? html`<details class="more-inline milo-read"><summary>Data Milo retrieved (${got.length})</summary><ul class="plain">${got.map((r) => html`<li>${r.label || ''} <small class="t-muted">${[r.source, r.as_of ? `as of ${prefs.clock(r.as_of)}` : '', r.ok === false ? 'could not be retrieved' : ''].filter(Boolean).join(', ')}</small></li>`)}</ul></details>` : ''}`;
}
function historyHTML() {
  const list = loadHistory();
  return html`<div class="milo-history"><div class="split"><p class="t-label">${list.length} saved conversation${list.length === 1 ? '' : 's'}</p><button type="button" class="btn btn-sm" data-v2-milo-new>New conversation</button></div>
    ${list.length ? html`<ul class="plain">${list.map((c) => html`<li class="${c.id === S.conv.id ? 'is-now' : ''}"><button type="button" class="milo-hist-open" data-v2-milo-open="${c.id}"><span>${c.title}</span><small class="t-muted">${prefs.dayTime(c.at)}, ${(c.messages || []).length} messages${c.ticker ? `, ${c.ticker}` : ''}</small></button><button type="button" class="icon-btn" data-v2-milo-del="${c.id}" aria-label="Delete ${c.title}">×</button></li>`)}</ul>` : html`<p class="t-muted">Nothing saved yet.</p>`}
    <p class="asof">Stored in this browser only and never uploaded, shared with the classic app. Each account's are kept apart here, and signing out puts yours away until you sign in again. The last ${MAX_CONVERSATIONS} conversations are kept.</p></div>`;
}
function settingsHTML() {
  const p = S.personas || {}, ps = p.personas || [], hz = ((p.horizons || {}).horizons) || [], ms = (S.modes || {}).modes || [];
  return html`<details class="more-inline milo-settings"><summary>Answer settings</summary><div class="milo-set-grid">
      <label class="select"><span class="t-label">Level</span><select data-v2-milo-mode>${ms.map((m) => html`<option value="${m.id}" ${prefs.knowledge() === m.id ? 'selected' : ''}>${m.label}</option>`)}</select></label>
      <label class="select"><span class="t-label">Analyst</span><select data-v2-milo-persona>${ps.map((x) => html`<option value="${x.id}" ${persona() === x.id ? 'selected' : ''}>${x.label}</option>`)}</select></label>
      <label class="select"><span class="t-label">Timeframe</span><select data-v2-milo-horizon>${hz.map((x) => html`<option value="${x.id}" ${horizon() === x.id ? 'selected' : ''}>${x.label}</option>`)}</select></label></div>
    <p class="asof">The same settings as the classic panel. They change how Milo explains and what it weighs, never the figures.</p></details>`;
}
function chromeHTML() {
  const b = blocked();
  return html`<div class="milo-top"><label class="select milo-scope"><span class="t-label">Milo sees</span><select data-v2-milo-scope>${Object.entries(SCOPES).map(([k, v]) => html`<option value="${k}" ${S.scope === k ? 'selected' : ''}>${k === 'auto' ? contextLabel('auto') : v}</option>`)}</select></label>
      <div class="cluster"><button type="button" class="btn btn-sm" data-v2-milo-history aria-expanded="${S.showHistory}">History</button><button type="button" class="btn btn-sm" data-v2-milo-new>New</button></div></div>
    <p class="asof milo-delay">${(S.health && S.health.realtime_chain) ? 'Option chains are real-time; other prices may be delayed.' : 'Prices are delayed up to 15 minutes.'}</p>${miloNotice()}
    ${S.showHistory ? historyHTML() : ''}${settingsHTML()}
    ${b ? html`<div class="state milo-block" role="status"><p>${b.text}</p>${b.kind === 'signin' ? html`<a class="btn btn-primary btn-sm" href="#/signin">Sign in</a>` : ''}</div>` : ''}`;
}
function logHTML() {
  if (!S.items.length) return html`<p class="t-muted milo-empty">Ask about ${contextLabel()}, or anything else in the market. Follow-up questions keep the conversation going.</p>`;
  return html`${S.items.map(msgHTML)}`;
}
function paintChrome() { const h = host(); if (!h) return; draw($('.milo-chrome', h), chromeHTML()); paintForm(); }
function paintLog(stick = true) {
  const h = host(); if (!h) return;
  const log = $('.milo-log', h), pinned = !log || log.scrollHeight - log.scrollTop - log.clientHeight < 60;
  draw(log, logHTML());
  mountAnswerCharts(log);
  if (stick && pinned) log.scrollTop = log.scrollHeight;
}
function paintForm() {
  const h = host(); if (!h) return;
  const b = blocked(), send = $('[data-v2-milo-send]', h), stop = $('[data-v2-milo-stop]', h), ta = $('#milo-q', h);
  if (send) { send.disabled = S.busy || !!b; send.hidden = S.busy; }
  if (stop) stop.hidden = !S.busy;
  if (ta) { ta.disabled = !!b && b.kind !== 'spent'; ta.setAttribute('aria-describedby', 'milo-allow'); }
  const al = $('#milo-allow', h); if (al) al.textContent = S.busy ? '' : allowanceLine();
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
    mountAnswerCharts(node);
    const log = $('.milo-log', h); if (log && log.scrollHeight - log.scrollTop - log.clientHeight < 120) log.scrollTop = log.scrollHeight;
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
  return `The server did not answer${status ? ` (HTTP ${status})` : ''}. This is usually a restart or a deploy: wait a moment and send it again.`;
}
export async function send(text) {
  text = String(text || '').trim();
  if (!text || S.busy || blocked()) return;
  const h = host(), ta = h && $('#milo-q', h);
  const context = buildContext(S.scope, S.conv.lastTicker);
  const focusTicker = context.focus.ticker;
  if (context.focus.previous_ticker) S.items.push({ kind: 'note', text: `Now looking at ${focusTicker} (was ${context.focus.previous_ticker}). Milo is told the earlier answers were about ${context.focus.previous_ticker}.` });
  S.conv.messages.push({ role: 'user', content: text }); S.items.push({ kind: 'msg', i: S.conv.messages.length - 1 });
  if (focusTicker) S.conv.lastTicker = focusTicker;
  const ai = S.conv.messages.length; // index the answer will take
  S.conv.messages.push({ role: 'assistant', content: '' }); S.items.push({ kind: 'msg', i: ai });
  meta.set(ai, { question: text, symbol: focusTicker || route.symbol || null, context });
  S.busy = true; S.live = { i: ai, text: '', status: 'Reading what is on your screen', symbol: focusTicker || route.symbol || null };
  if (ta) ta.value = ''; S.draft = '';
  paintLog(); paintForm(); paintLive();
  const ctl = new AbortController(); S.abort = ctl;
  let finished = false, ended = '', failed = null;
  try {
    const res = await fetch('/api/chat', {
      method: 'POST', credentials: 'same-origin', signal: ctl.signal,
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', 'X-Optic-CSRF': (document.cookie.match(/(?:^|; )optic_csrf=([^;]*)/) || [])[1] || '' },
      body: JSON.stringify({ messages: S.conv.messages.slice(0, ai).map((m) => ({ role: m.role, content: m.content })), context, web: false, attachments: [], persona: persona(), mode: prefs.knowledge(), horizon: horizon() }),
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
          if (ev === 'delta') { S.live.text += p.text || ''; S.live.status = ''; S.conv.messages[ai].content = S.live.text; paintLive(); }
          else if (ev === 'status') { const w = STEP_WORDS[String(p.state || '')] || String(p.state || '').replace(/^./, (x) => x.toUpperCase()); S.live.status = w; paintLive(); }
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
    S.conv.messages.splice(ai - 1, 2); S.items = S.items.filter((it) => !(it.kind === 'msg' && it.i >= ai - 1)); meta.delete(ai);
    S.items.push({ kind: 'note', text: failed.text });
    S.draft = text; const box = host() && $('#milo-q', host()); if (box && !box.value.trim()) box.value = text;
    if (failed.signin) loadAllowance();
  } else if (!reply && ended === 'stopped') {
    S.conv.messages.splice(ai - 1, 2); S.items = S.items.filter((it) => !(it.kind === 'msg' && it.i >= ai - 1)); meta.delete(ai);
    S.items.push({ kind: 'note', text: 'Stopped before Milo answered.' });
  } else {
    if (failed) S.items.push({ kind: 'note', text: failed.text });
    if (ended) { meta.get(ai).ended = ended; S.conv.messages[ai].content = `${reply}\n\n[${ended === 'stopped' ? 'Stopped by the reader' : 'Cut off'}: incomplete]`; }
    persist();
  }
  paintLog(); paintForm(); loadAllowance();
}
export function stop() { if (S.abort) S.abort.abort(); }

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
    if (!spec) { say(`${STUDIES[a.id][0]} is on the classic chart for now.`, false); const r = $('.milo-act-result', card); if (r) r.insertAdjacentHTML('beforeend', ` <a href="${CLASSIC}#/${encodeURIComponent(sym)}/chart">Open it there</a>`); return; }
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
    if (store.signedIn()) {
      try { await api.post('/api/saved-research', { title: a.question.slice(0, 200), symbol: sym, content: a.question, research_type: 'pulse' }); say('Saved to Research.', true); } catch (e) { say(api.explain(e, 'Saving'), false); }
      return;
    }
    if (!holds(store.state.user)) { say('It was not saved.', false); return; }
    try { const all = JSON.parse(localStorage.getItem(RESEARCH_KEY) || '[]'); if (all.some((r) => String(r.question || '').trim().toLowerCase() === a.question.toLowerCase())) { say('That question is already in Research.', true); return; } all.unshift({ question: a.question, ticker: sym, at: new Date().toISOString() }); localStorage.setItem(RESEARCH_KEY, JSON.stringify(all.slice(0, 40))); say('Saved to Research in this browser.', true); } catch (e) { say('It was not saved.', false); }
    return;
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
export async function openMilo({ question = '', opener, send: sendNow = false, about, symbol } = {}) {
  if (question) S.draft = question;
  // every opening says where it came from; one with no block is the whole page
  asked = about || symbol ? { about: about || null, symbol: symbol ? String(symbol).toUpperCase() : null } : null;
  let vvOff = null;
  drawer.open({
    kicker: 'Ask Milo', title: 'Milo', opener,
    body: html`<div class="milo"><div class="milo-chrome">${chromeHTML()}</div>
      <div class="milo-log" role="log" aria-live="polite" aria-label="Conversation with Milo">${logHTML()}</div>
      <form class="milo-form" data-v2-milo-form><label class="sr" for="milo-q">Your question</label>
        <textarea id="milo-q" rows="3" maxlength="4000" placeholder="Ask Milo">${S.draft}</textarea>
        <div class="cluster"><button type="submit" class="btn btn-primary" data-v2-milo-send>Send</button><button type="button" class="btn" data-v2-milo-stop hidden>Stop</button><p class="asof" id="milo-allow"></p></div></form></div>`,
    mount: (b) => {
      S.mounted = $('.milo', b) || b;
      const panel = S.mounted.closest('.drawer-panel'); if (panel) panel.classList.add('milo-panel');
      // the phone keyboard: keep the composer above it
      const vv = window.visualViewport;
      if (vv && panel) { const fit = () => { panel.style.setProperty('--vvh', `${Math.round(vv.height)}px`); }; fit(); vv.addEventListener('resize', fit); vvOff = () => vv.removeEventListener('resize', fit); }
      wire(S.mounted);
      paintLog(); paintForm();
      const ta = $('#milo-q', S.mounted);
      if (ta && !matchMedia('(pointer: coarse)').matches) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }
      loadAllowance(); loadChoices();
      api.get('/api/health', { ttl: 60000 }).then((hh) => { S.health = hh; paintChrome(); }, () => {});
      if (sendNow && S.draft) send(S.draft);
    },
    closed: () => { if (vvOff) vvOff(); const ta = S.mounted && $('#milo-q', S.mounted); if (ta) S.draft = ta.value; S.mounted = null; },
  });
}
function wire(root) {
  root.addEventListener('submit', (e) => { if (e.target.closest('[data-v2-milo-form]')) { e.preventDefault(); send($('#milo-q', root).value); } });
  root.addEventListener('keydown', (e) => { if (e.target.id === 'milo-q' && e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(e.target.value); } });
  root.addEventListener('input', (e) => { if (e.target.id === 'milo-q') S.draft = e.target.value; });
  root.addEventListener('change', (e) => {
    const t = e.target;
    if (t.matches('[data-v2-milo-scope]')) { S.scope = t.value; return; }
    if (t.matches('[data-v2-milo-persona]')) { setPref(PERSONA_KEY, t.value); return; }
    if (t.matches('[data-v2-milo-horizon]')) { setPref(HORIZON_KEY, t.value); return; }
    if (t.matches('[data-v2-milo-mode]')) prefs.setKnowledge(t.value);
  });
  root.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s); let b;
    if (t('[data-v2-milo-stop]')) { stop(); return; }
    if (t('[data-v2-milo-history]')) { S.showHistory = !S.showHistory; paintChrome(); const hb = $('[data-v2-milo-history]', root); if (hb) hb.focus(); return; }
    if (t('[data-v2-milo-new]')) { if (S.busy) return; S.conv = blankConv(); S.items = []; meta.clear(); S.showHistory = false; paintChrome(); paintLog(); const ta = $('#milo-q', root); if (ta) ta.focus(); return; }
    if ((b = t('[data-v2-milo-open]'))) {
      if (S.busy) return;
      const c = loadHistory().find((x) => x.id === b.dataset.v2MiloOpen); if (!c) return;
      S.conv = { id: c.id, messages: (c.messages || []).map((m) => ({ role: m.role, content: m.content })), lastTicker: c.ticker || null };
      meta.clear(); S.items = S.conv.messages.map((m, i) => ({ kind: 'msg', i }));
      S.conv.messages.forEach((m, i) => { if (m.role === 'assistant') meta.set(i, { question: (S.conv.messages[i - 1] || {}).content || '', symbol: c.ticker || null }); });
      S.showHistory = false; paintChrome(); paintLog(); const ta = $('#milo-q', root); if (ta) ta.focus(); return;
    }
    if ((b = t('[data-v2-milo-del]'))) { const id = b.dataset.v2MiloDel; saveHistory(loadHistory().filter((c) => c.id !== id)); if (S.conv.id === id && !S.busy) { S.conv = blankConv(); S.items = []; meta.clear(); paintLog(); } paintChrome(); return; }
    if ((b = t('[data-v2-milo-follow]'))) { const ta = $('#milo-q', root); if (ta) { ta.value = b.dataset.v2MiloFollow; S.draft = ta.value; ta.focus(); } return; }
    if ((b = t('[data-v2-milo-again]'))) { const q = (meta.get(Number(b.dataset.v2MiloAgain)) || {}).question; const ta = $('#milo-q', root); if (q && ta) { ta.value = q; S.draft = q; ta.focus(); } return; }
    if ((b = t('[data-v2-milo-copy]'))) {
      const m = S.conv.messages[Number(b.dataset.v2MiloCopy)] || {}; const txt = sourcesAsText(String(m.content || '').split(/\n(?:→|->) /)[0]);
      try { await navigator.clipboard.writeText(txt); b.textContent = 'Copied'; setTimeout(() => { b.textContent = 'Copy'; }, 1500); } catch (err) { b.textContent = 'Copy failed'; }
      return;
    }
    if (t('[data-v2-milo-srclist]')) { const msg = e.target.closest('.milo-msg'); const d = msg && $('.milo-read', msg); if (d) { msg.querySelectorAll('.milo-read').forEach((x) => { x.open = true; }); d.scrollIntoView({ block: 'nearest' }); } return; }
    if (t('[data-v2-milo-act-skip]')) { const card = e.target.closest('.milo-act'); const r = $('.milo-act-result', card); if (r) r.textContent = 'Left as it was.'; card.querySelectorAll('button').forEach((x) => { x.disabled = true; }); return; }
    if (t('[data-v2-milo-act-go]')) {
      const card = e.target.closest('.milo-act'), msg = e.target.closest('[data-v2-milo-i]');
      let a = null; try { a = JSON.parse(card.dataset.v2MiloAct); } catch (err) { return; }
      runAction(a, card, msg ? Number(msg.dataset.v2MiloI) : -1);
    }
  });
}
void compact; void ACT_SECTIONS;
