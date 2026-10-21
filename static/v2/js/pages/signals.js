// Signal history, on Alerts (Classic parity B5, 2026-10-21): each swing-setup alert of the reader's that fired, as
// it was recorded at the time, and what the stock did after (Classic app.js:8183-8580). Signed in, the server keeps
// it (app/signal_history.py) and filters it. A guest's lives in this browser under Classic's key and format,
// optic.signals.v1 {signals: [<=200], events: {key: [...]}}, so either app reads the other's: the record is kept
// exactly as the server built it for the check, and what followed is asked of /api/signals/followup, which stores
// nothing. An observation is the stock's close, never an option's price or a trade's result, and a horizon with
// nothing observed says so rather than showing a number. No model is called.
import { html } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, signed, clean, capFirst } from '../core/format.js';
import { skeleton, failed, empty, how } from '../ui/states.js';
import { icon } from '../ui/icons.js';

export const SIGNALS_KEY = 'optic.signals.v1';
export const SIGNALS_MAX = 200;          // a browser's storage is small; two hundred is years of an active reader's alerts
export const FOLLOWUP_MAX = 60;          // the follow-up endpoint's own cap
export const HORIZONS = [1, 5, 10, 20];
export const STATUS_LABELS = { unresolved: 'Open', invalidated: 'Invalidated', expired: 'Expired' };

/* ---------------- this browser's store, Classic's format ---------------- */
export function readLocal() {
  try {
    const raw = JSON.parse(localStorage.getItem(SIGNALS_KEY) || 'null');
    if (raw && Array.isArray(raw.signals) && raw.events && typeof raw.events === 'object') return raw;
  } catch (e) { /* unreadable: an empty history rather than a broken view */ }
  return { signals: [], events: {} };
}
function writeLocal(st) { try { localStorage.setItem(SIGNALS_KEY, JSON.stringify(st)); return true; } catch (e) { return false; } }

/** A guest's record, kept exactly as the server built it and never edited. The same trigger seen again is the same
 *  record, so it is not stored twice; past 200, the oldest triggers go, with what followed them. */
export function keepSignal(rec, now = new Date().toISOString()) {
  if (!rec || !rec.signal_key || !holds(store.state.user)) return false;
  const st = readLocal();
  if (st.signals.some((x) => x && x.signal_key === rec.signal_key)) return false;
  st.signals.push(Object.assign({}, rec, { recorded_at: now, origin: 'alert check on the page' }));
  if (st.signals.length > SIGNALS_MAX) {
    st.signals.sort((a, b) => String((b || {}).trigger_at).localeCompare(String((a || {}).trigger_at)));
    st.signals.slice(SIGNALS_MAX).forEach((x) => { if (x) delete st.events[x.signal_key]; });
    st.signals = st.signals.slice(0, SIGNALS_MAX);
  }
  return writeLocal(st);
}

/** What followed, appended once each as the server does it: one status per signal and one observation per horizon,
 *  stamped with when this browser first saw it. A later reply that differs does not replace what was recorded. */
export function addEvents(st, key, events, now = new Date().toISOString()) {
  const have = st.events[key] || [];
  (events || []).forEach((e) => {
    if (!e || typeof e !== 'object') return;
    if (e.kind === 'status' && have.some((h) => h.kind === 'status')) return;
    if (have.some((h) => h.kind === e.kind && h.label === e.label)) return;
    have.push(Object.assign({}, e, { observed_at: now }));
  });
  st.events[key] = have;
  return st;
}
export function statusOf(events) {
  const v = (events || []).find((e) => e.kind === 'status' && (e.label === 'invalidated' || e.label === 'expired'));
  return v ? v.label : 'unresolved';
}
export const horizonLabel = (h) => `after ${h} candle${h === 1 ? '' : 's'}`;

/** A guest's horizons: what this browser recorded, else what the last follow-up said about the candle (not
 *  printed yet, or printed and missing). Before any follow-up has answered, unknown. */
export function localHorizons(key, events, told = {}) {
  const said = told[key] || [];
  return HORIZONS.map((h) => {
    const e = (events || []).find((x) => x.kind === 'observation' && x.label === horizonLabel(h));
    if (e) return { horizon: h, state: 'observed', data_as_of: e.data_as_of, price: e.price, change_pct: e.change_pct, observed_at: e.observed_at };
    const t = said.find((x) => x.horizon === h);
    return { horizon: h, state: t && t.state !== 'observed' ? t.state : 'unknown' };
  });
}
export function localRows(st = readLocal(), told = {}) {
  return st.signals.filter((s) => s && s.signal_key).map((s) => {
    const events = (st.events[s.signal_key] || []).slice().sort((a, b) => String(a.data_as_of).localeCompare(String(b.data_as_of)));
    return Object.assign({}, s, { events, status: statusOf(events), horizons: localHorizons(s.signal_key, events, told) });
  }).sort((a, b) => String(b.trigger_at).localeCompare(String(a.trigger_at)));
}
/** The signals still waiting on something, newest first, as the follow-up endpoint takes them. */
export function followupBody(st = readLocal()) {
  return st.signals.filter((s) => s && s.signal_key && (st.events[s.signal_key] || []).length < 1 + HORIZONS.length)
    .sort((a, b) => String(b.trigger_at).localeCompare(String(a.trigger_at))).slice(0, FOLLOWUP_MAX)
    .map((s) => ({ signal_key: s.signal_key, symbol: s.symbol, direction: s.direction, trigger_at: s.trigger_at, trigger_price: s.trigger_price,
      invalidation: s.invalidation, params: { signal_ttl: (s.params || {}).signal_ttl } }));
}
/** A follow-up's reply, kept: read again rather than reused, since a check may have kept a new record meanwhile. */
export function keepFollowup(reply, now) {
  const fresh = readLocal();
  Object.keys((reply && reply.events) || {}).forEach((key) => { if (fresh.signals.some((s) => s && s.signal_key === key)) addEvents(fresh, key, reply.events[key], now); });
  writeLocal(fresh);
}
export function optionsOf(rows, labels = {}) {
  const strategies = {};
  rows.forEach((s) => { strategies[s.strategy] = s.strategy_label || labels[s.strategy] || s.strategy; });
  return { symbols: [...new Set(rows.map((s) => s.symbol))].sort(), strategies: Object.keys(strategies).sort().map((id) => ({ id, label: strategies[id] })) };
}
export const filtersDefault = (f) => f.status === 'all' && f.direction === 'all' && !f.symbol && !f.strategy;
/** The account's rows come filtered by the server (so an old row a long history would hide is still found);
 *  this browser's are filtered here. */
export function rowsShown(data, f) {
  const rows = (data && data.signals) || [];
  if (data && data.where === 'account') return rows;
  return rows.filter((s) => (f.status === 'all' || s.status === f.status) && (f.direction === 'all' || s.direction === f.direction)
    && (!f.symbol || s.symbol === f.symbol) && (!f.strategy || s.strategy === f.strategy));
}
export function query(f) {
  const q = [];
  if (f.status !== 'all') q.push(`status=${encodeURIComponent(f.status)}`);
  if (f.direction !== 'all') q.push(`direction=${encodeURIComponent(f.direction)}`);
  if (f.symbol) q.push(`symbol=${encodeURIComponent(f.symbol)}`);
  if (f.strategy) q.push(`strategy=${encodeURIComponent(f.strategy)}`);
  return '/api/signals' + (q.length ? `?${q.join('&')}` : '');
}

/* ---------------- loading ---------------- */
// One state for the page's life; Alerts resets it on each visit (fresh()).
// labels: each setup's name by its rule id, from Alerts' condition list, for a record that predates its stored label
export const SG = { labels: {}, data: null, error: null, loading: false, options: null, open: {}, followed: null, followedAt: null, followError: null, basis: '',
  f: { status: 'all', direction: 'all', symbol: '', strategy: '' } };
export function fresh() {
  Object.assign(SG, { data: null, error: null, loading: false, options: null, open: {}, followed: null, followedAt: null, followError: null, basis: '' });
  SG.f = { status: 'all', direction: 'all', symbol: '', strategy: '' };
}
let seq = 0;
export async function load() {
  const my = ++seq; SG.loading = true;
  try {
    if (store.signedIn()) {
      const r = await api.get(query(SG.f), { ttl: 0, force: true });
      if (my !== seq) return;
      SG.data = { signals: (r && r.signals) || [], basis: (r && r.basis) || '', where: 'account' };
      if (filtersDefault(SG.f) || !SG.options) SG.options = optionsOf(SG.data.signals, SG.labels);
    } else {
      // once a visit: the candles it reads move once a day
      if (!SG.followedAt) {
        SG.followedAt = new Date().toISOString();
        const todo = followupBody();
        if (todo.length) {
          try {
            const reply = await api.post('/api/signals/followup', { signals: todo });
            keepFollowup(reply);
            SG.followed = reply.horizons || {}; SG.basis = reply.basis || ''; SG.followError = null;
          } catch (e) { SG.followError = e; }
        }
      }
      if (my !== seq) return;
      const rows = localRows(readLocal(), SG.followed || {});
      SG.data = { signals: rows, basis: SG.basis, where: 'browser' };
      SG.options = optionsOf(rows, SG.labels);
    }
    SG.error = null;
  } catch (e) { if (my !== seq) return; SG.error = e; }
  SG.loading = false;
}

/* ---------------- words ---------------- */
/** A date as a date, a moment in Eastern time: a record is read against the exchange's clock, not the reader's. */
export function when(iso) {
  if (!iso) return 'not recorded';
  const s = String(iso), day = s.length === 10;
  const d = new Date(day ? `${s}T12:00:00Z` : s);
  if (Number.isNaN(d.getTime())) return s;
  return day ? d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
    : d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' });
}
/** When the trigger candle closed: the time alone when that was the candle's own day, as it always is for a daily candle. */
export function closedAt(s) {
  if (!s.trigger_completed_at) return '';
  const d = new Date(s.trigger_completed_at);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-CA', { timeZone: 'America/New_York' }) === String(s.trigger_at).slice(0, 10)
    ? d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' }) : when(s.trigger_completed_at);
}
const price = (v) => (v === null || v === undefined || v === '' || Number.isNaN(Number(v)) ? 'not recorded' : num(v, 2));
const tone = (v) => (Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : '');
const HORIZON_WHY = { pending: 'That candle has not closed yet.', missing: 'Its candle has passed and no close was observed: the feed had none, or the follow-up has not run since.', unknown: 'Not checked yet.' };

function horizonCell(h) {
  const k = html`<span class="sg-hk">+${h.horizon}</span>`;
  if (h.state === 'observed' && h.change_pct !== null && h.change_pct !== undefined) {
    return html`<span class="sg-hc">${k} <b class="${tone(h.change_pct)}">${signed(h.change_pct, 1)}</b><span class="sr">, close ${num(h.price, 2)} on ${when(h.data_as_of)}</span></span>`;
  }
  return html`<span class="sg-hc is-${h.state}">${k} <span class="t-muted">${h.state === 'pending' ? 'not yet' : 'unknown'}</span><span class="sr">: ${HORIZON_WHY[h.state] || HORIZON_WHY.unknown}</span></span>`;
}
function eventItem(e) {
  const at = html`<span class="sg-when">${when(e.data_as_of)}</span>`, seen = html`<span class="t-muted">Observed ${when(e.observed_at)}.</span>`;
  if (e.kind === 'status') return html`<li>${at} <b>${STATUS_LABELS[e.label] || e.label}.</b> ${clean(e.detail || '')} ${seen}</li>`;
  const rebased = e.detail && e.detail.indexOf('re-based') >= 0 ? html` <span class="t-muted">${clean(e.detail)}</span>` : '';
  return html`<li>${at} ${capFirst(e.label || '')}: close ${price(e.price)}, <b class="${tone(e.change_pct)}">${signed(e.change_pct, 2)}</b> from the trigger close.${rebased} ${seen}</li>`;
}
const pairs = (list) => html`<dl class="sg-dl">${list.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
const mark = (p) => (p === true ? 'Met' : p === false ? 'Not met' : 'No reading');

function detail(s) {
  const cond = s.conditions || {}, checks = cond.checks || [], events = s.events || [];
  const readings = Object.entries(s.indicators || {}).filter(([, v]) => v !== null && v !== undefined);
  const params = Object.entries(s.params || {}).filter(([, v]) => v !== null && v !== undefined);
  const waiting = (s.horizons || []).some((h) => h.state !== 'observed');
  return html`<div class="sg-body">
    ${s.explanation ? html`<p>${clean(s.explanation)}</p>` : ''}
    <div class="sg-cols">
      <div><h4 class="t-label">The record, as it fired</h4>${pairs([
        ['Trigger candle', `${capFirst(when(s.trigger_at))}${closedAt(s) ? `, closed ${closedAt(s)}` : ''}`],
        ['Data read through', capFirst(when(s.data_as_of))],
        ['Timeframe', capFirst(s.timeframe || 'daily')],
        ['Trigger price', capFirst(price(s.trigger_price))],
        ['Trigger level', s.trigger_level === null || s.trigger_level === undefined ? 'None for this rule' : capFirst(price(s.trigger_level))],
        ['Invalidation', capFirst(price(s.invalidation))],
        ['Target', s.target === null || s.target === undefined ? 'None: this rule sets no target' : capFirst(price(s.target))],
        ['Recorded', `${capFirst(when(s.recorded_at))}${s.origin ? `, by the ${s.origin}` : ''}`],
      ])}</div>
      <div><h4 class="t-label">What followed</h4>${events.length ? html`<ol class="sg-tl">${events.map(eventItem)}</ol>`
        : html`<p class="t-muted">Nothing observed yet. The first observation is the close one completed candle after the trigger.</p>`}
        ${waiting ? html`<p class="asof">Not yet: that candle has not closed. Unknown: its candle has passed and no close was observed (the feed had none, or the follow-up has not run since), or it has not been checked.</p>` : ''}</div>
    </div>
    ${checks.length ? html`<h4 class="t-label">${cond.met ?? ''} of ${cond.of ?? ''} conditions met when it fired</h4>
      <div class="tscroll"><table class="t sg-checks"><thead><tr><th class="l">Group</th><th class="l">Rule</th><th class="l">When it fired</th><th>Reading</th></tr></thead>
      <tbody>${checks.map((c) => html`<tr class="${c.required ? '' : 'is-info'}"><td class="l">${clean(c.group || '')}</td><td class="l">${clean(c.rule || '')}${c.required ? '' : html` <span class="t-muted">(filter off, not counted)</span>`}</td><td class="l">${mark(c.passed)}</td><td>${c.value === null || c.value === undefined ? '' : String(c.value)}</td></tr>`)}</tbody></table></div>
      ${cond.note ? html`<p class="asof">${clean(cond.note)}</p>` : ''}` : ''}
    ${readings.length || params.length || (s.assumptions || []).length || s.rule_version || s.source ? html`<details class="more-inline how"><summary>Readings, parameters and assumptions</summary><div class="how-body">
      ${readings.length ? html`<h4 class="t-label">Readings when it fired</h4>${pairs(readings.map(([k, v]) => [capFirst(k.replace(/_/g, ' ')), String(v)]))}` : ''}
      ${params.length ? html`<h4 class="t-label">Parameters</h4>${pairs(params.map(([k, v]) => [capFirst(k.replace(/_/g, ' ')), String(v)]))}` : ''}
      ${(s.assumptions || []).length ? html`<h4 class="t-label">Assumptions</h4><ul class="plain">${s.assumptions.map((a) => html`<li>${clean(a)}</li>`)}</ul>` : ''}
      ${pairs([['Rule version', s.rule_version ? html`<code>${s.rule_version}</code>` : 'Not recorded'], ['Source', s.source ? clean(s.source) : 'Not recorded']])}
    </div></details>` : ''}
  </div>`;
}
function row(s) {
  const status = STATUS_LABELS[s.status] ? s.status : 'unresolved', bull = s.direction === 'bull', key = s.signal_key || s.id;
  return html`<li class="sg-row"><details data-sg-key="${key}" ${SG.open[key] ? 'open' : ''}>
    <summary class="sg-sum"><span class="sg-when">${when(s.trigger_at)}</span>
      <span class="sg-title"><b class="tick">${s.symbol}</b> ${s.strategy_label || SG.labels[s.strategy] || s.strategy}</span>
      <span class="sg-side ${bull ? 'up' : 'down'}">${bull ? 'Bullish' : 'Bearish'}</span>
      <span class="sg-state is-${status}">${STATUS_LABELS[status]}</span>
      <span class="sg-hz" role="group" aria-label="The stock's close after 1, 5, 10 and 20 completed candles">${(s.horizons || []).map((h) => html`${horizonCell(h)} `)}</span>
      <span class="sg-chev" aria-hidden="true">${icon('chev')}</span></summary>
    ${detail(s)}</details></li>`;
}
const sel = (attr, label, value, opts) => html`<label class="select sg-filter"><span class="t-label">${label}</span><select ${attr}>${opts.map(([v, l]) => html`<option value="${v}" ${String(v) === String(value) ? 'selected' : ''}>${l}</option>`)}</select></label>`;

/** The section's body: filters, the records, and the method folded. */
export function block() {
  if (SG.error) return failed('Signal history', SG.error, { retry: 'signals' });
  if (!SG.data) return skeleton('rows', 2, 'Loading signal history');
  const rows = rowsShown(SG.data, SG.f), o = SG.options || { symbols: [], strategies: [] }, any = o.symbols.length > 0 || rows.length > 0;
  const filters = any ? html`<div class="sg-filters" role="group" aria-label="Filter signal history">
      ${sel('data-sg-status', 'Status', SG.f.status, [['all', 'All'], ['unresolved', 'Open'], ['invalidated', 'Invalidated'], ['expired', 'Expired']])}
      ${sel('data-sg-dir', 'Side', SG.f.direction, [['all', 'Both'], ['bull', 'Bullish'], ['bear', 'Bearish']])}
      ${o.symbols.length > 1 ? sel('data-sg-symbol', 'Symbol', SG.f.symbol, [['', 'All'], ...o.symbols.map((x) => [x, x])]) : ''}
      ${o.strategies.length > 1 ? sel('data-sg-strategy', 'Setup', SG.f.strategy, [['', 'All'], ...o.strategies.map((x) => [x.id, x.label])]) : ''}</div>` : '';
  const body = rows.length ? html`<ul class="sg-list">${rows.map(row)}</ul>`
    : any ? empty('No signal matches these filters', '', html`<button type="button" class="btn btn-sm" data-sg-reset>Show all</button>`)
      : empty('No signals yet', 'One is recorded when a swing-setup alert of yours fires on a completed candle.', html`<button type="button" class="btn btn-sm" data-v2-al-new="" data-kind="swing_setup">Set a swing setup alert</button>`);
  return html`${filters}
    ${SG.loading && SG.data ? html`<p class="asof" role="status">Updating…</p>` : ''}
    ${SG.followError && SG.data.where === 'browser' ? html`<p class="asof">What followed could not be checked just now (${api.explain(SG.followError, 'The follow-up')}), so horizons not already recorded show as unknown.</p>` : ''}
    ${body}
    ${rows.length >= 200 && SG.data.where === 'account' ? html`<p class="asof">Showing the newest 200 that match.</p>` : ''}
    ${rows.length && SG.data.basis ? how(html`<p>${clean(SG.data.basis)}</p>`) : ''}`;
}
export const whereLine = () => (store.signedIn() ? 'Kept in your account, recorded whether or not this page was open.'
  : 'Kept in this browser while you are signed out, so it holds only the triggers this page saw.');
