// Alerts. Three kinds, kept apart because they answer to different people:
//   your alerts     conditions you set on a symbol (watches: /api/watches, or this browser's optic.watches.v1)
//   Optic's book    trade ideas and closes from the paper book Optic keeps for its scans (/api/alerts), the same for everyone
//   your portfolio  situations in a linked brokerage account, kept on Brokerage
//
// An alert fires when its condition changes from not met to met (analytics/watches.py fires), once,
// and again only after it has stopped being met. Every check is kept on the alert: what it read,
// when, and why it could not, so the page can say what an alert is doing and why it fired.
import { $, html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, clean, ago, shortDate, signed, plural } from '../core/format.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { toast } from '../ui/toast.js';
import * as drawer from '../ui/drawer.js';
import { icon } from '../ui/icons.js';
import { getFlags } from '../ui/shell.js';
import { provideContext } from '../ui/milo.js';
import { hrefFor } from '../nav.js';
import { sectionHead } from './tabs.js';
import { refreshUnread } from '../core/unread.js';

const LOCAL_KEY = 'optic.watches.v1';
let S = {};
let live = true;

// What a check leaves behind, exactly as the classic app's checkWatchSymbol
// does, so either app's next check knows what is news: signed in, the server
// records it (/api/watches/seen, which also keeps a hit when it is news);
// signed out, the watch keeps its state and when it last fired, and a
// swing-setup alert that fired is kept in the browser's signal history
// (optic.signals.v1, as keepLocalSignal).
const SIGNALS_KEY = 'optic.signals.v1', SIGNALS_MAX = 200;
function keepSignal(rec) {
  if (!rec || !rec.signal_key || !holds(store.state.user)) return;
  let st = { signals: [], events: {} };
  try { const raw = JSON.parse(localStorage.getItem(SIGNALS_KEY) || 'null'); if (raw && Array.isArray(raw.signals) && raw.events && typeof raw.events === 'object') st = raw; } catch (e) { /* unreadable: start again */ }
  if (st.signals.some((x) => x.signal_key === rec.signal_key)) return;
  st.signals.push(Object.assign({}, rec, { recorded_at: new Date().toISOString(), origin: 'alert check on the page' }));
  if (st.signals.length > SIGNALS_MAX) {
    st.signals.sort((a, b) => String(b.trigger_at).localeCompare(String(a.trigger_at)));
    st.signals.slice(SIGNALS_MAX).forEach((x) => { delete st.events[x.signal_key]; });
    st.signals = st.signals.slice(0, SIGNALS_MAX);
  }
  try { localStorage.setItem(SIGNALS_KEY, JSON.stringify(st)); } catch (e) { /* private */ }
}

// The same rule as the server (analytics/watches.py fires): a crossing needs a state to change from.
const CROSSINGS = new Set(['price_above', 'price_below', 'rsi_above', 'rsi_below', 'macd_cross', 'breakout', 'signal_flip', 'analyst_revisions', 'insider_activity']);
export function fires(kind, prev, cur, met) {
  if (!met || cur == null) return false;
  if (CROSSINGS.has(kind) && prev == null) return false;
  return prev !== cur;
}
export function refState(kind, level, ref) {
  if (!Number.isFinite(ref) || !Number.isFinite(level)) return null;
  if (kind === 'price_above') return ref > level ? 'above' : 'not above';
  if (kind === 'price_below') return ref < level ? 'below' : 'not below';
  return null;
}

async function record(results) {
  if (store.signedIn()) {
    try {
      const r = await api.post('/api/watches/seen', { results });
      const [w, h] = await Promise.all([api.get('/api/watches', { ttl: 0, force: true }), api.get('/api/watches/hits?limit=60', { ttl: 0, force: true })]);
      S.watches = w.watches || S.watches; S.hits = h.hits || S.hits;
      return (r && r.fired) || 0;
    } catch (e) { return 0; /* the check itself worked; recording is best effort */ }
  }
  results.filter((x) => x.met && x.signal_record).forEach((x) => keepSignal(x.signal_record));
  const by = new Map(results.map((x) => [x.id, x]));
  let fired = 0;
  saveLocal(localDefs().map((d) => {
    const h = by.get(d.id);
    if (!h) return d;
    const prev = d.last_state != null ? d.last_state : refState(d.kind, Number((d.params || {}).level), Number(d.ref_price));
    const news = d.active !== false && fires(d.kind, prev, h.state, h.met);
    if (news) fired += 1;
    return Object.assign(d, { last_state: h.state != null ? h.state : d.last_state, last_checked_at: new Date().toISOString(), last_error: !h.met && h.reason ? h.reason : null },
      news ? { last_met_at: new Date().toISOString(), last_evidence: { evidence: h.evidence, state: h.state, observed: h.observed || null, from: prev } } : {});
  }));
  S.watches = localDefs();
  return fired;
}

function localDefs() {
  if (!holds(store.state.user)) return [];
  try { const r = JSON.parse(localStorage.getItem(LOCAL_KEY) || '[]'); return Array.isArray(r) ? r.filter((w) => !w.deleted_at) : []; } catch (e) { return []; }
}
function saveLocal(list) {
  if (!holds(store.state.user)) return false;
  try { localStorage.setItem(LOCAL_KEY, JSON.stringify(list.slice(0, 40))); return true; } catch (e) { return false; }
}

/* ---------------- words ---------------- */
const cat = () => S.catalogue || [];
const cond = (k) => cat().find((c) => c.id === k) || null;
const kindLabel = (k) => (cond(k) || {}).label || k;
const FAMILY = { price_above: 'price', price_below: 'price', move_pct: 'price', rsi_above: 'technical', rsi_below: 'technical', macd_cross: 'technical', breakout: 'technical',
  signal_flip: 'research', analyst_revisions: 'research', earnings_near: 'research', insider_activity: 'research', short_interest: 'research', swing_setup: 'research', unusual_options: 'options' };
const FAMILIES = [['all', 'All'], ['price', 'Price'], ['technical', 'Technical'], ['research', 'Research signals'], ['options', 'Options activity']];
function paramText(w) {
  const c = cond(w.kind);
  const p = c && c.param; if (!p) return '';
  const v = (w.params || {})[p.key];
  if (v === undefined || v === null || v === '') return '';
  if (p.choices) return ((p.choices.find((x) => x.value === v) || {}).label || v);
  return p.kind === 'percent' ? `${num(v, 1)}%` : p.kind === 'price' ? `$${num(v)}` : p.kind === 'days' ? `${plural(v, 'day')}` : String(v);
}
const sentence = (w) => `${kindLabel(w.kind)} ${paramText(w)}`.trim();
const etTime = (iso) => { try { return new Date(iso).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' ET'; } catch (e) { return ''; } };
const today = (iso) => { try { const f = (d) => new Date(d).toLocaleDateString('en-CA', { timeZone: 'America/New_York' }); return f(iso) === f(Date.now()); } catch (e) { return false; } };

function stateWords(w) {
  const s = String(w.last_state || ''), lv = paramText(w);
  if (/^(above|not above|below|not below)$/.test(s)) return `${s} ${lv}`;
  if (s.startsWith('moved:')) return 'moved past it today';
  if (s.startsWith('quiet:')) return 'not past it today';
  if (s.startsWith('near:')) return `reports ${shortDate(s.slice(5))}`;
  if (s.startsWith('far:')) return `next report ${shortDate(s.slice(4))}`;
  if (s.startsWith('filing:')) return `latest filing ${shortDate(s.split(':')[1])}`;
  if (s === 'none') return 'nothing to report';
  if (s.startsWith('changed:') || s.startsWith('steady:')) return `report of ${shortDate(s.split(':')[1])}`;
  if (s === 'inside') return 'inside its levels';
  if (s === 'broken') return 'past every mapped level';
  return s.length < 30 ? s : 'read';
}
/** What an alert is doing now, in one line. */
function statusLine(w) {
  if (w.active === false) return html`<span class="w-paused">Paused${w.paused_at ? ` since ${shortDate(w.paused_at)}` : ''}.</span> Not checked until you resume it.`;
  const parts = [];
  if (w.last_met_at && today(w.last_met_at)) parts.push(html`<b>Fired today</b>, ${etTime(w.last_met_at)}. `);
  else if (w.last_met_at) parts.push(html`Last fired ${ago(w.last_met_at)}. `);
  if (w.last_error) parts.push(html`<span class="down">Could not check: ${clean(w.last_error)}</span>`);
  else if (w.last_checked_at && w.last_state) parts.push(html`Checked ${ago(w.last_checked_at)}: ${stateWords(w)}.`);
  else if (w.ref_price) parts.push(html`Set when ${w.symbol} was $${num(w.ref_price)}${w.ref_at ? `, ${shortDate(w.ref_at)}` : ''}. ${w.last_checked_at ? `Checked ${ago(w.last_checked_at)}.` : 'Not checked yet.'}`);
  else if (w.last_checked_at) parts.push(html`Checked ${ago(w.last_checked_at)}.`);
  else parts.push(html`Not checked yet. Its first check arms it; it fires on the change after that.`);
  return parts;
}

/** The alert a hit came from, without repeating its symbol: "Price rises above $308.65". */
function hitWhat(h) {
  const live = (S.watches || []).find((w) => w.id === h.watch_id);
  if (live) return sentence(live);
  const text = clean(h.condition || h.title || '');
  const bare = text.startsWith(h.symbol) ? text.slice(h.symbol.length).replace(/^[:\s]+/, '') : text;
  return bare.charAt(0).toUpperCase() + bare.slice(1);
}
/** Why a hit fired: what was read, against what, when, and from where. */
function whyFired(h) {
  const o = h.observed || {};
  const bits = [];
  if (o.from && o.to && o.from !== o.to && !/^(moved|quiet|hit|none|near|far|changed|steady|filing):/.test(String(o.to))) bits.push(`It read ${o.from}, then ${o.to}.`);
  if (Number.isFinite(o.price)) bits.push(`Last trade $${num(o.price)}${o.quote_time ? ` at ${etTime(o.quote_time)}` : ''}${Number.isFinite(o.level) && /price/.test(h.kind) ? `, against $${num(o.level)}` : ''}.`);
  if (Number.isFinite(o.value) && /rsi/.test(h.kind)) bits.push(`RSI ${num(o.value, 1)} against ${num(o.level, 0)}.`);
  if (Number.isFinite(o.value) && h.kind === 'move_pct') bits.push(`${signed(o.value)} on the day against ${num(o.level, 1)}%.`);
  if (Number.isFinite(o.ref_price)) bits.push(`Set when it was $${num(o.ref_price)}.`);
  if (o.delay && Number.isFinite(o.price)) bits.push(o.delay);
  return bits.join(' ');
}

/* ---------------- sections ---------------- */
function scheduleLine() {
  if (!store.signedIn()) return 'In this browser. Checked only while this page is open, when you press Check now. Sign in to have Optic check them for you and keep what fired.';
  return 'On your account. Optic checks them on market days about every 30 minutes from 9:30 to 4:00 ET and once after the close, skipping exchange holidays. Prices are about 15 minutes behind the exchange. What fires is shown here; Optic does not send email or push notifications.';
}

function watchesBlock() {
  if (S.watchErr) return failed('Your alerts', S.watchErr, { retry: 'watches' });
  const ws = S.watches;
  if (!ws) return skeleton('rows', 2, 'Loading your alerts');
  const undo = S.undo ? html`<p class="wl-undo" role="status">${S.undo.text} <button type="button" class="btn btn-sm" data-v2-al-undo>Undo</button></p>` : '';
  if (!ws.length) return html`${undo}${empty('No alerts yet', 'A price level, a day\'s move, an RSI line, a change in Optic\'s stance or an earnings date.')}`;
  const bySym = {};
  ws.forEach((w) => { (bySym[w.symbol] = bySym[w.symbol] || []).push(w); });
  return html`${undo}
    ${Object.entries(bySym).map(([sym, list]) => {
    const ck = (S.checks || {})[sym];
    return html`<div class="watch-group"><div class="watch-sym"><a href="${hrefFor('overview', sym)}" class="tick">${sym}</a>
      <button type="button" class="btn btn-sm" data-v2-check="${sym}" ${ck && ck.loading ? 'disabled' : ''}>${ck && ck.loading ? 'Checking…' : 'Check now'}</button>
      <button type="button" class="btn btn-sm btn-quiet" data-v2-al-new="${sym}" aria-label="Add an alert on ${sym}">${icon('plus')} Add</button>
      ${ck && ck.at ? html`<span class="asof">Checked ${ago(ck.at)}${ck.price ? `, last $${num(ck.price)}` : ''}${ck.fired ? `, ${ck.fired} fired` : ''}</span>` : ''}</div>
      <ul class="watch-list">${list.map((w) => {
        const res = ck && ck.results ? ck.results.find((r) => r.id === w.id) : null;
        return html`<li class="${w.active === false ? 'is-paused' : ''}"><div class="w-main"><span class="w-what">${sentence(w)}</span>
          <span class="w-state">${res ? html`<b class="${res.met ? 'up' : ''}">${res.met ? 'Met now' : 'Not met now'}</b> ${clean(res.evidence || res.reason || '')}` : statusLine(w)}</span></div>
          <div class="w-acts">
            ${cond(w.kind) && cond(w.kind).param ? html`<button type="button" class="btn btn-sm btn-quiet" data-v2-al-edit="${w.id}" aria-label="Change ${sentence(w)} on ${sym}">Edit</button>` : ''}
            <button type="button" class="btn btn-sm btn-quiet" data-v2-al-pause="${w.id}" aria-label="${w.active === false ? 'Resume' : 'Pause'} ${sentence(w)} on ${sym}">${w.active === false ? 'Resume' : 'Pause'}</button>
            <button type="button" class="btn btn-sm btn-quiet" data-v2-al-del="${w.id}" aria-label="Delete ${sentence(w)} on ${sym}">Delete</button>
          </div></li>`;
      })}</ul></div>`;
  })}`;
}

function hitsBlock() {
  if (!store.signedIn()) {
    return html`<div class="state"><p class="t-h3">A history needs an account</p><p>Signed in, Optic checks your alerts on its own schedule and keeps each one that fires here, with what it read. In this browser, each alert shows when it last fired at your own check.</p><a class="btn btn-primary" href="#/signin">Sign in or create an account</a></div>`;
  }
  if (S.hitsErr) return failed('What fired', S.hitsErr, { retry: 'hits' });
  if (!S.hits) return skeleton('rows', 2, 'Loading what fired');
  const fam = S.fam || 'all';
  const shown = S.hits.filter((h) => (fam === 'all' || (FAMILY[h.kind] || 'research') === fam) && (!S.unseenOnly || !h.seen));
  const counts = {}; S.hits.forEach((h) => { const k = FAMILY[h.kind] || 'research'; counts[k] = (counts[k] || 0) + 1; });
  const unseen = S.hits.filter((h) => !h.seen).length;
  return html`${S.hits.length ? html`<div class="al-filters"><div class="chips chips-scroll" role="group" aria-label="Show">${FAMILIES.filter(([k]) => k === 'all' || counts[k]).map(([k, l]) => html`<button type="button" class="chip" data-v2-al-fam="${k}" aria-pressed="${fam === k}">${l} <span class="t-muted">${k === 'all' ? S.hits.length : counts[k]}</span></button>`)}</div>
      <label class="check"><input type="checkbox" data-v2-al-unseen ${S.unseenOnly ? 'checked' : ''}> <span>New only (${unseen})</span></label></div>` : ''}
    ${!S.hits.length ? empty('Nothing has fired yet', 'When an alert fires it is kept here, with what Optic read and when.')
    : !shown.length ? empty('Nothing in this view', '', html`<button type="button" class="btn btn-sm" data-v2-al-fam="all">Show everything</button>`)
    : html`<ul class="hit-list">${shown.map((h) => html`<li class="${h.seen ? '' : 'is-new'}">
        <p class="hit-head"><a href="${hrefFor('overview', h.symbol)}"><b class="tick">${h.symbol}</b></a> ${hitWhat(h)}${h.seen ? '' : html` <span class="hit-new">New</span>`}</p>
        <p>${clean(h.body || '')}</p>${whyFired(h) ? html`<p class="hit-why">${whyFired(h)}</p>` : ''}
        <small class="t-muted">${etTime(h.created_at)}, ${h.origin === 'page check' ? 'found by your check on this page' : 'found by Optic\'s scheduled check'}</small></li>`)}</ul>`}
    ${unseen ? html`<button type="button" class="btn btn-sm" data-v2-hits-seen>Mark all as seen</button>` : ''}`;
}

function ledger() {
  if (S.alertsErr) return failed('Optic\'s book', S.alertsErr, { retry: 'alerts' });
  if (!S.alerts) return skeleton('rows', 3, 'Loading Optic\'s book');
  const a = S.alerts.alerts || [], kinds = S.alerts.kinds || {};
  if (!a.length) return empty('Nothing from the book yet', 'A new paper trade idea or a closed position appears here when Optic\'s scheduled scan records one.');
  return html`<ul class="hit-list">${a.slice(0, 20).map((x) => html`<li><p class="hit-head"><a href="${x.ticker ? hrefFor('overview', x.ticker) : '#/'}"><b class="tick">${x.ticker || ''}</b></a> ${clean(x.title)}</p><p>${clean(x.body || '')}</p><small class="t-muted">${clean((kinds[x.kind] || {}).label || x.kind || '')}, ${etTime(x.created_at)}</small></li>`)}</ul>`;
}

function paint(main) {
  const bk = !!getFlags().brokerage;
  const f = document.activeElement, keep = f && main.contains(f) ? [...f.attributes].map((a) => a.name).find((n) => n.startsWith('data-v2-al-') || n === 'data-v2-check') : null, kv = keep ? f.getAttribute(keep) : null;
  draw($('#al-body', main), html`
    <section class="section first" aria-labelledby="h-w"><div class="section-head"><div><h2 class="t-h2" id="h-w">Your alerts</h2><p class="section-sub">${scheduleLine()}</p></div>
      <button type="button" class="btn btn-primary" data-v2-al-new="">New alert</button></div>${watchesBlock()}</section>
    <section class="section" aria-labelledby="h-hits"><div class="section-head"><div><h2 class="t-h2" id="h-hits">What fired</h2><p class="section-sub">One entry per crossing: an alert fires again only after its condition has stopped being met.</p></div></div>${hitsBlock()}</section>
    <section class="section" aria-labelledby="h-l"><div class="section-head"><div><h2 class="t-h2" id="h-l">From Optic's paper book</h2><p class="section-sub">Trade ideas and closed positions from the paper book Optic keeps for its scans. The same for every reader: not your trades, and not your alerts.</p></div></div>${ledger()}</section>
    ${bk ? html`<p class="asof">Alerts about your linked brokerage holdings (earnings, concentration, drift) are on <a class="textlink" href="#/brokerage/overview">Brokerage</a>.</p>` : ''}`);
  if (keep) { const el = $(`[${keep}="${CSS.escape(kv || '')}"]`, main); if (el) el.focus({ preventScroll: true }); }
}

/* ---------------- the form, a sheet on a phone ---------------- */
const GROUPS = [['Price', 'price'], ['Technical', 'technical'], ['Research signals', 'research'], ['Options activity', 'options']];
function formBody(f) {
  const c = cond(f.kind) || cat()[0];
  if (!c) return S.catErr ? failed('The list of conditions', S.catErr, { retry: 'catalogue' }) : skeleton('lines', 2, 'Loading the conditions');
  const p = c.param;
  return html`<form class="stack al-form" data-v2-al-form="${f.id || 'new'}" novalidate>
    <label class="field"><span class="sr">Symbol</span><input name="symbol" value="${f.symbol || ''}" placeholder="Symbol, such as AAPL" maxlength="12" required autocomplete="off" autocapitalize="characters" spellcheck="false" enterkeyhint="next" ${f.id ? 'readonly' : ''}></label>
    <label class="select"><span class="t-label">When</span><select name="kind" data-v2-al-kind ${f.id ? 'disabled' : ''}>${GROUPS.map(([g, fam]) => html`<optgroup label="${g}">${cat().filter((x) => (FAMILY[x.id] || 'research') === fam).map((x) => html`<option value="${x.id}" ${x.id === c.id ? 'selected' : ''}>${x.label}</option>`)}</optgroup>`)}</select></label>
    ${p ? (p.choices ? html`<label class="select"><span class="t-label">${p.label}</span><select name="param" data-v2-al-param>${p.choices.map((ch) => html`<option value="${ch.value}" ${String(ch.value) === String(f.param ?? p.default) ? 'selected' : ''}>${ch.label}</option>`)}</select></label>`
    : html`<label class="field"><span class="t-label">${p.label}</span><input name="param" data-v2-al-param inputmode="decimal" enterkeyhint="done" value="${f.param ?? p.default ?? ''}" placeholder="${p.label}" required></label>`) : ''}
    <div class="al-summary" aria-live="polite">${summary(f, c)}</div>
    <p class="form-error" role="alert">${f.error || ''}</p>
    <div class="cluster"><button type="submit" class="btn btn-primary">${f.id ? 'Save changes' : 'Create alert'}</button><button type="button" class="btn" data-v2-close>Cancel</button></div>
    <div class="al-mine-box">${mineBlock(f)}</div>
    <p class="asof">${clean(c.why || '')}</p></form>`;
}
function mineBlock(f) {
  const mine = (S.watches || []).filter((w) => w.symbol === f.symbol && w.id !== f.id);
  return mine.length ? html`<div class="al-mine"><p class="t-label">Your other alerts on ${f.symbol}</p><ul class="plain">${mine.map((w) => html`<li>${sentence(w)}${w.active === false ? html` <span class="t-muted">paused</span>` : ''}</li>`)}</ul></div>` : '';
}
const numOf = (raw) => { const s = String(raw ?? '').replace(/[$,%\s]/g, ''); return s === '' ? NaN : Number(s); };
function summary(f, c) {
  const p = c.param, sym = f.symbol || 'the symbol';
  const v = p && !p.choices ? numOf(f.param ?? p.default) : null;
  const q = f.quote;
  const now = q && Number.isFinite(q.price) ? `Now $${num(q.price)}${q.market_time ? ` at ${etTime(q.market_time)}` : ''}` : (q && q.failed ? 'The current price did not load' : f.symbol ? 'Looking up the current price' : '');
  let what;
  if (c.id === 'price_above' && Number.isFinite(v)) what = `Fires when ${sym}'s last trade moves from at or under $${num(v)} to above it.${q && Number.isFinite(q.price) ? ` ${now}, ${q.price > v ? 'already above: it fires after it falls back under and crosses again' : `${num(((v - q.price) / q.price) * 100, 1)}% below`}.` : ''}`;
  else if (c.id === 'price_below' && Number.isFinite(v)) what = `Fires when ${sym}'s last trade moves from at or over $${num(v)} to below it.${q && Number.isFinite(q.price) ? ` ${now}, ${q.price < v ? 'already below: it fires after it rises back over and crosses again' : `${num(((q.price - v) / q.price) * 100, 1)}% above`}.` : ''}`;
  else if (c.id === 'move_pct' && Number.isFinite(v)) what = `Fires once on a session when ${sym} is up or down more than ${num(v, 1)}% on the day.${now ? ` ${now}.` : ''}`;
  else if (/^price_/.test(c.id)) what = `Enter the level for ${sym}.${q && Number.isFinite(q.price) ? ` ${now}.` : ''}`;
  else {
    const pv = p ? (p.choices ? ((p.choices.find((x) => String(x.value) === String(f.param ?? p.default)) || {}).label || '') : (Number.isFinite(v) ? `${num(v, p.kind === 'percent' ? 1 : p.kind === 'days' ? 0 : 2)}${p.kind === 'percent' ? '%' : p.kind === 'days' ? ' days' : ''}` : '')) : '';
    what = `${sym}: ${c.label.toLowerCase()}${pv ? ` ${pv}` : ''}. ${CROSSINGS.has(c.id) ? 'Its first check arms it; it fires when that changes, and again only after it has changed back.' : 'It fires once for each new occurrence.'}${now ? ` ${now}.` : ''}`;
  }
  const when = store.signedIn() ? 'Checked on market days about every 30 minutes, 9:30 to 4:00 ET, and once after the close.' : 'Checked only while the Alerts page is open, when you press Check now.';
  return html`<p><b>${what}</b></p><p class="t-muted">${when} Prices are about 15 minutes behind the exchange. Shown in Optic only: no email or push.</p>`;
}

async function quoteFor(f) {
  const sym = store.canon(f.symbol || '');
  if (!/^[A-Z0-9.^=-]{1,12}$/.test(sym)) { f.quote = null; return; }
  try { const r = await api.get(`/api/quote/${encodeURIComponent(sym)}`, { ttl: 20000, timeout: 12000 }); const q = (r && (r.quote || r)) || {}; f.quote = Number.isFinite(Number(q.price)) && r.available !== false ? { price: Number(q.price), market_time: q.market_time || q.as_of } : { failed: true }; }
  catch (e) { f.quote = { failed: true }; }
}

function openForm(main, f, opener) {
  S.form = f;
  drawer.open({ kicker: f.id ? 'Change an alert' : 'New alert', title: f.symbol ? `${f.symbol}${f.id ? '' : ': a new alert'}` : 'A new alert', body: formBody(f), opener, form: true, closed: () => { S.form = null; } });
  if (f.symbol) quoteFor(f).then(() => { const b = drawer.body(); if (b && S.form === f) draw(b, formBody(f)); });
}
function readForm(form, f) {
  f.symbol = store.canon(form.symbol.value || '');
  if (!f.id) f.kind = form.kind.value;
  f.param = form.param ? form.param.value : undefined;
}

async function submit(main, form) {
  const f = S.form; if (!f) return;
  readForm(form, f);
  const c = cond(f.kind);
  const fail = (msg) => { f.error = msg; const e = $('.form-error', form); if (e) e.textContent = msg; };
  if (!/^[A-Z0-9.^=-]{1,12}$/.test(f.symbol)) return fail('Enter a ticker, such as AAPL.');
  const params = {};
  if (c && c.param) {
    const raw = f.param ?? c.param.default;
    if (c.param.choices) params[c.param.key] = raw;
    else {
      const n = numOf(raw);
      const rsi = /^rsi_/.test(c.id);
      const bad = !Number.isFinite(n) || n <= 0 || ((c.param.kind === 'percent' || rsi) && n >= 100) || (c.param.kind === 'days' && n > 365);
      if (bad) return fail(`${c.param.label} needs ${rsi ? 'a number between 0 and 100' : c.param.kind === 'percent' ? 'a percentage between 0 and 100' : c.param.kind === 'days' ? 'a number of days from 1 to 365' : 'a number above zero'}.`);
      params[c.param.key] = c.param.kind === 'days' ? Math.round(n) : n;
    }
  }
  const ref = f.quote && Number.isFinite(f.quote.price) && /^price_/.test(f.kind) ? f.quote.price : undefined;
  try {
    if (store.signedIn()) {
      if (f.id) await api.patch(`/api/watches/${encodeURIComponent(f.id)}`, { params, ref_price: ref });
      else await api.post('/api/watches', { symbol: f.symbol, kind: f.kind, params, ref_price: ref });
      S.watches = (await api.get('/api/watches', { ttl: 0, force: true })).watches || S.watches;
    } else {
      const defs = localDefs();
      const key = JSON.stringify({ symbol: f.symbol, kind: f.kind, params });
      if (defs.some((d) => d.id !== f.id && JSON.stringify({ symbol: d.symbol, kind: d.kind, params: d.params }) === key)) return fail(`You already have that alert on ${f.symbol}.`);
      let next;
      if (f.id) next = defs.map((d) => (d.id === f.id ? Object.assign(d, { params, ref_price: ref ?? null, last_state: null, updated_at: new Date().toISOString() }) : d));
      else {
        if (defs.length >= 40) return fail('That is 40 alerts, which is the limit. Delete one to add another.');
        next = [...defs, { id: 'local-' + Math.random().toString(36).slice(2, 11), symbol: f.symbol, kind: f.kind, params, active: true, created_at: new Date().toISOString(), ref_price: ref ?? null, ref_at: ref ? new Date().toISOString() : null, last_state: null, last_met_at: null, last_evidence: null }];
      }
      if (!saveLocal(next)) return fail('This browser would not save the alert (private browsing, or its storage is full).');
      S.watches = localDefs();
    }
    drawer.close({ silent: true });
    toast(f.id ? `Changed: ${f.symbol}, ${sentence({ kind: f.kind, params })}.` : `Alert set: ${f.symbol}, ${sentence({ kind: f.kind, params })}.`);
    paint(main);
    const row = (f.id && $(`[data-v2-al-edit="${CSS.escape(String(f.id))}"]`, main)) || $(`[data-v2-check="${CSS.escape(f.symbol)}"]`, main);
    if (row) row.focus();
  } catch (err) { fail(err.message && err.kind !== 'server' ? err.message : api.explain(err, 'The alert')); }
}

/* ---------------- loading ---------------- */
async function loadAll(main) {
  const signed = store.signedIn();
  const jobs = [
    api.get('/api/watches/catalogue', { ttl: 3600000 }).then((r) => { S.catalogue = r.conditions || []; S.schedule = r.schedule; }, (e) => { S.catErr = e; }),
    api.get('/api/alerts?limit=40', { ttl: 60000 }).then((r) => { S.alerts = r; }, (e) => { S.alertsErr = e; }),
  ];
  if (signed) {
    jobs.push(api.get('/api/watches', { ttl: 0, force: true }).then((r) => { S.watches = r.watches || []; }, (e) => { S.watchErr = e; }));
    jobs.push(api.get('/api/watches/hits?limit=60', { ttl: 0, force: true }).then((r) => { S.hits = r.hits || []; }, (e) => { S.hitsErr = e; }));
  } else S.watches = localDefs();
  await Promise.all(jobs.map((j) => j.finally(() => { if (live) paint(main); })));
}

export async function render(main, route) {
  live = true;
  (S.stops || []).forEach((s) => s());
  S = { checks: {}, fam: 'all', unseenOnly: false, undo: null, stops: [] };
  provideContext(() => ({ view: 'alerts', alerts: (S.watches || []).map((w) => ({ symbol: w.symbol, condition: sentence(w), active: w.active !== false, last_met_at: w.last_met_at })) }));
  document.title = 'Alerts, Optic';
  draw(main, html`<header class="page-head">${sectionHead('follow', 'alerts')}</header><div id="al-body"></div>`);
  paint(main);
  wire(main);
  await loadAll(main);
  // arriving from a company's Alert action: the form opens for that symbol, beside its existing alerts
  const sym = store.canon((route.params || {}).symbol || '');
  if (sym && live && cat().length) openForm(main, { symbol: sym, kind: 'price_above' }, null);
}
export function dispose() { live = false; (S.stops || []).forEach((s) => s()); S.stops = []; }
export const retry = {
  hits: (m) => { S.hitsErr = null; loadAll(m); }, catalogue: (m) => { S.catErr = null; loadAll(m); },
  watches: (m) => { S.watchErr = null; loadAll(m); }, alerts: (m) => { S.alertsErr = null; loadAll(m); },
};

async function setActive(main, w, on) {
  const was = w.active, wasAt = w.paused_at;
  w.active = on; w.paused_at = on ? null : new Date().toISOString();
  if (store.signedIn()) {
    try { const r = await api.patch(`/api/watches/${encodeURIComponent(w.id)}`, { active: on }); Object.assign(w, r.watch || {}); }
    catch (err) { w.active = was; w.paused_at = wasAt; paint(main); toast(api.explain(err, 'The change'), { kind: 'bad' }); return; }
  } else if (!saveLocal(localDefs().map((d) => (d.id === w.id ? Object.assign(d, { active: on, paused_at: w.paused_at, last_state: on ? null : d.last_state }) : d)))) {
    w.active = was; w.paused_at = wasAt; paint(main); toast('This browser would not save the change.', { kind: 'bad' }); return;
  } else if (on) w.last_state = null;
  toast(on ? `Resumed: ${w.symbol}, ${sentence(w)}. It starts again from its next check.` : `Paused: ${w.symbol}, ${sentence(w)}.`);
  paint(main);
  const b = $(`[data-v2-al-pause="${CSS.escape(String(w.id))}"]`, main); if (b) b.focus();
}

async function remove(main, w) {
  const all = localDefs();
  try {
    if (store.signedIn()) await api.del(`/api/watches/${encodeURIComponent(w.id)}`);
    else if (!saveLocal(all.filter((x) => String(x.id) !== String(w.id)))) throw new api.ApiError('bad', 0, 'This browser would not save the change.');
  } catch (err) { toast(err.message && err.kind === 'bad' ? err.message : api.explain(err, 'The delete'), { kind: 'bad' }); return; }
  const at = S.watches.indexOf(w);
  S.watches = S.watches.filter((x) => x !== w);
  const undo = async () => {
    S.undo = null;
    try {
      if (store.signedIn()) { await api.post(`/api/watches/${encodeURIComponent(w.id)}/restore`, {}); S.watches = (await api.get('/api/watches', { ttl: 0, force: true })).watches || S.watches; }
      else { const now = localDefs(); now.splice(Math.max(0, at), 0, Object.assign(w, { last_state: null })); saveLocal(now); S.watches = localDefs(); }
      toast(`Restored: ${w.symbol}, ${sentence(w)}.`);
    } catch (err) { toast(`Undo did not go through: ${api.explain(err, 'The change')}`, { kind: 'bad' }); }
    if (live) paint(main);
  };
  S.undo = { text: `Deleted: ${w.symbol}, ${sentence(w)}.${store.signedIn() ? ' What it fired stays in the history.' : ''}`, run: undo };
  toast(S.undo.text, { action: 'Undo', run: () => { if (S.undo) S.undo.run(); } });
  paint(main);
  const next = $('[data-v2-al-undo]', main) || $('[data-v2-al-new]', main); if (next) next.focus();
}

function wire(main) {
  // the form lives in the drawer, outside the page: its events are caught on the document while this page is open
  const onDoc = (type, fn) => { document.addEventListener(type, fn); S.stops.push(() => document.removeEventListener(type, fn)); };
  onDoc('submit', (e) => { const form = e.target.closest('[data-v2-al-form]'); if (!form || !live) return; e.preventDefault(); submit(main, form); });
  onDoc('change', (e) => {
    const form = e.target.closest('[data-v2-al-form]'); if (!form || !S.form || !live) return;
    readForm(form, S.form);
    if (e.target.matches('[data-v2-al-kind]')) { S.form.param = undefined; draw(drawer.body(), formBody(S.form)); const k = $('[data-v2-al-kind]', drawer.body()); if (k) k.focus(); return; }
    if (e.target.name === 'symbol') {
      // a new symbol updates the summary, the title and its other alerts; what else was typed stays
      const f = S.form, b = drawer.body(), c = cond(f.kind);
      f.quote = null;
      const sumBox = $('.al-summary', b), mineBox = $('.al-mine-box', b), title = document.getElementById('drawer-title');
      if (sumBox && c) draw(sumBox, summary(f, c)); if (mineBox) draw(mineBox, mineBlock(f)); if (title && f.symbol) title.textContent = `${f.symbol}: a new alert`;
      quoteFor(f).then(() => { const box = S.form === f && drawer.body() && $('.al-summary', drawer.body()); if (box && c) draw(box, summary(f, cond(f.kind) || c)); });
    }
  });
  onDoc('input', (e) => {
    const form = e.target.closest('[data-v2-al-form]'); if (!form || !S.form || !live || !e.target.matches('[data-v2-al-param]')) return;
    readForm(form, S.form); S.form.error = '';
    const box = $('.al-summary', form), c = cond(S.form.kind); if (box && c) draw(box, summary(S.form, c));
  });
  main.addEventListener('click', async (e) => {
    const t = (sel) => e.target.closest(sel);
    let b;
    if ((b = t('[data-v2-al-new]'))) { openForm(main, { symbol: b.dataset.v2AlNew || '', kind: 'price_above' }, b); return; }
    if ((b = t('[data-v2-al-edit]'))) {
      const w = (S.watches || []).find((x) => String(x.id) === b.dataset.v2AlEdit); if (!w) return;
      const c = cond(w.kind); openForm(main, { id: w.id, symbol: w.symbol, kind: w.kind, param: c && c.param ? (w.params || {})[c.param.key] : undefined }, b); return;
    }
    if ((b = t('[data-v2-al-pause]'))) { const w = (S.watches || []).find((x) => String(x.id) === b.dataset.v2AlPause); if (w) await setActive(main, w, w.active === false); return; }
    if ((b = t('[data-v2-al-del]'))) { const w = (S.watches || []).find((x) => String(x.id) === b.dataset.v2AlDel); if (w) await remove(main, w); return; }
    if (t('[data-v2-al-undo]')) { if (S.undo) await S.undo.run(); return; }
    if ((b = t('[data-v2-al-fam]'))) { S.fam = b.dataset.v2AlFam; paint(main); return; }
    if ((b = t('[data-v2-check]'))) {
      const sym = b.dataset.v2Check;
      const defs = S.watches.filter((w) => w.symbol === sym && w.active !== false);
      if (!defs.length) { toast(`Every alert on ${sym} is paused.`); return; }
      S.checks[sym] = { loading: true }; paint(main);
      try {
        const r = await api.post('/api/watches/check', { ticker: sym, watches: defs.map((w) => ({ id: w.id, kind: w.kind, params: w.params })) }, { timeout: 60000 });
        const fired = await record(r.results || []);
        S.checks[sym] = { at: r.checked_at || new Date().toISOString(), results: r.results || [], price: r.price, fired };
      } catch (err) { S.checks[sym] = null; toast(api.explain(err, 'The check'), { kind: 'bad' }); }
      paint(main);
      const again = $(`[data-v2-check="${sym}"]`, main); if (again) again.focus();
      return;
    }
    if (t('[data-v2-hits-seen]')) {
      try { await api.post('/api/watches/hits/seen', {}); S.hits = S.hits.map((h) => Object.assign(h, { seen: true })); paint(main); refreshUnread(); }
      catch (err) { toast(api.explain(err, 'That'), { kind: 'bad' }); }
    }
  });
  main.addEventListener('change', (e) => {
    if (e.target.matches('[data-v2-al-unseen]')) { S.unseenOnly = e.target.checked; paint(main); const c = $('[data-v2-al-unseen]', main); if (c) c.focus(); }
  });
}
