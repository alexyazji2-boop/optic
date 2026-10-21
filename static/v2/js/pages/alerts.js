// Alerts. Three kinds, kept apart because they answer to different people:
//   your alerts     conditions you set on a symbol (watches: /api/watches, or this browser's optic.watches.v1),
//                   and the signal history of the swing-setup ones that fired (pages/signals.js)
//   Optic's book    trade ideas and closes from the paper book Optic keeps for its scans (/api/alerts), the same for
//                   everyone, grouped by urgency as Classic does (Classic parity B5); its read state is the owner's
//   your portfolio  situations in a linked brokerage account, kept on Brokerage
//
// An alert fires when its condition changes from not met to met (analytics/watches.py fires), once,
// and again only after it has stopped being met. Every check is kept on the alert: what it read,
// when, and why it could not, so the page can say what an alert is doing and why it fired.
import { $, html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, clean, ago, shortDate, signed, plural, capFirst } from '../core/format.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { toast } from '../ui/toast.js';
import * as drawer from '../ui/drawer.js';
import { icon } from '../ui/icons.js';
import { getFlags } from '../ui/shell.js';
import { provideContext } from '../ui/milo.js';
import { hrefFor } from '../nav.js';
import { sectionHead } from './tabs.js';
import { refreshUnread } from '../core/unread.js';
import { localDefs, saveLocal } from '../core/watches.js';
import * as SIG from './signals.js';

let S = {};
let live = true;

// What a check leaves behind, exactly as the classic app's checkWatchSymbol
// does, so either app's next check knows what is news: signed in, the server
// records it (/api/watches/seen, which also keeps a hit when it is news, and the
// signal history of a swing-setup alert); signed out, the watch keeps its state
// and when it last fired, and a swing-setup alert that fired is kept in the
// browser's signal history (optic.signals.v1, as keepLocalSignal: SIG.keepSignal).

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
  results.filter((x) => x.met && x.signal_record).forEach((x) => SIG.keepSignal(x.signal_record));
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

/* ---------------- Optic's book: the scheduled scan's alerts ----------------
 * One inbox for the deployment, so its read state and clearing are the owner's (both routes are behind the write
 * guard): a reader sees every alert, without marks that would only be the owner's. Grouped by urgency, in the order
 * it should be read (Classic's ALERT_URGENCY), time ordering each group. "Why this fired" is the rule's class (the
 * kind's own why, published by /api/alerts) and the numbers it fired on (the alert's payload): neither is written
 * by a model, so they can be checked rather than believed. */
export const URGENCY = [['high', 'Needs attention'], ['normal', 'Worth knowing'], ['low', 'For the record']];
const isOwner = () => !!(store.state.me && store.state.me.admin);
const PAYLOAD_SKIP = new Set(['id', 'ticker', 'symbol', 'book', 'entry_at', 'exit_at', 'created_at', 'ran_at', 'dedupe_key']);
/** An alert's payload as readings: scalars only, eight at most, label-cased, numbers to two places. */
export function readings(payload) {
  return Object.entries(payload || {}).filter(([k, v]) => !PAYLOAD_SKIP.has(k) && (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean') && v !== '' && v !== null)
    .slice(0, 8).map(([k, v]) => [capFirst(k.replace(/_/g, ' ')), typeof v === 'number' ? num(v, 2) : String(v)]);
}
/** Which alerts show: the kind chosen, unread only when asked, then grouped by urgency (empty groups dropped). */
export function bookGroups(all, kind = 'all', unreadOnly = false) {
  const rows = (all || []).filter((x) => (kind === 'all' || x.kind === kind) && (!unreadOnly || !x.seen));
  return URGENCY.map(([id, label]) => ({ id, label, rows: rows.filter((x) => (x.urgency || 'normal') === id) })).filter((g) => g.rows.length);
}
/** Whether email delivers the book, for the owner only: what it is set to do, then what it last did. */
export function deliveryNote(d, owner) {
  if (!d || !owner) return '';
  if (d.enabled) {
    const last = d.last_attempt, at = last && last.at ? etTime(last.at) : '';
    const rec = !last ? 'No email has been attempted since this server started.'
      : last.sent ? `The last email went out ${at}, carrying ${last.sent} alert${last.sent === 1 ? '' : 's'}.`
        : last.reason ? `The last attempt, ${at}, sent nothing: ${clean(last.reason)}` : '';
    const n = d.undelivered_recent, waiting = n ? ` ${n} alert${n === 1 ? '' : 's'} from the last day ${n === 1 ? 'has' : 'have'} not been emailed yet.` : '';
    return html`<p class="asof al-mail"><b>Set up to email you.</b> Each scan's new alerts go out as one email, and stay here as well. ${rec}${waiting}</p>`;
  }
  const bl = d.blockers || [];
  if (!bl.length) return '';
  return html`<details class="more-inline al-mail"><summary>These stay in this inbox: nothing here is emailed yet</summary><div class="how-body"><p>Shown to you only, as the owner. What email delivery still needs:</p><ul class="plain">${bl.map((b) => html`<li>${clean(b)}</li>`)}</ul></div></details>`;
}
function bookRow(x, kinds, owner) {
  const meta = kinds[x.kind] || {}, rd = readings(x.payload), open = S.bookOpen.has(x.id), fresh = owner && !x.seen;
  const can = !!(meta.why || rd.length);
  return html`<li class="${fresh ? 'is-new' : ''}">
    <p class="hit-head">${x.ticker ? html`<a href="${hrefFor('overview', x.ticker)}"><b class="tick">${x.ticker}</b></a> ` : ''}${clean(x.title)}${fresh ? html` <span class="hit-new">Unread</span>` : ''}</p>
    ${x.body ? html`<p>${clean(x.body)}</p>` : ''}
    <div class="al-tags"><small class="t-muted">${clean(x.kind_label || meta.label || x.kind || '')}, ${etTime(x.created_at)}</small>
      ${can ? html`<button type="button" class="btn btn-sm btn-quiet" data-v2-book-why="${x.id}" aria-expanded="${open}" aria-controls="bk-why-${x.id}">${open ? 'Hide why' : 'Why this fired'}</button>` : ''}
      ${fresh ? html`<button type="button" class="btn btn-sm btn-quiet" data-v2-book-seen="${x.id}" aria-label="Mark read: ${clean(x.title).slice(0, 80)}">Mark read</button>` : ''}</div>
    ${open ? html`<div class="al-explain" id="bk-why-${x.id}">${meta.why ? html`<p>${clean(meta.why)}</p>` : ''}${rd.length ? html`<dl class="sg-dl">${rd.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>` : ''}</div>` : ''}</li>`;
}
function ledger() {
  if (S.alertsErr) return failed('Optic\'s book', S.alertsErr, { retry: 'alerts' });
  if (!S.alerts) return skeleton('rows', 3, 'Loading Optic\'s book');
  const all = S.alerts.alerts || [], kinds = S.alerts.kinds || {}, owner = isOwner();
  const note = deliveryNote(S.alerts.delivery, owner);
  if (!all.length) return html`${note}${empty('Nothing from the book yet', 'A new paper trade idea, a closed position, a confirmed pattern or a risk cap appears here when Optic\'s scheduled scan records one. An empty list means nothing crossed a threshold, which is the common case.')}`;
  const counts = {}; all.forEach((x) => { counts[x.kind] = (counts[x.kind] || 0) + 1; });
  const kindIds = Object.keys(counts), kind = counts[S.bookKind] ? S.bookKind : 'all';
  const unread = all.filter((x) => !x.seen).length;
  const groups = bookGroups(all, kind, owner && S.bookUnread);
  const confirm = S.confirmClear ? html`<div class="al-confirm" role="group" aria-label="Clear the inbox"><p>Remove all ${all.length} alert${all.length === 1 ? '' : 's'} from the inbox? This clears them for every reader and cannot be undone.</p>
      <div class="cluster"><button type="button" class="btn btn-sm" data-v2-book-clear-yes>Clear all</button><button type="button" class="btn btn-sm btn-quiet" data-v2-book-clear-no>Keep them</button></div></div>` : '';
  return html`${note}
    ${kindIds.length > 1 || owner ? html`<div class="al-filters">${kindIds.length > 1 ? html`<div class="chips chips-scroll" role="group" aria-label="Show">${[['all', 'All'], ...kindIds.map((k) => [k, (kinds[k] || {}).label || k])].map(([k, l]) => html`<button type="button" class="chip" data-v2-book-kind="${k}" aria-pressed="${kind === k}">${l} <span class="t-muted">${k === 'all' ? all.length : counts[k]}</span></button>`)}</div>` : ''}
      ${owner ? html`<label class="check"><input type="checkbox" data-v2-book-unread ${S.bookUnread ? 'checked' : ''}> <span>Unread only (${unread})</span></label>` : ''}</div>` : ''}
    ${groups.length ? groups.map((g) => html`<div class="al-group"><h3 class="t-h3">${g.label} <span class="t-muted">${g.rows.length}</span></h3><ul class="hit-list">${g.rows.map((x) => bookRow(x, kinds, owner))}</ul></div>`)
      : empty(`None of these ${all.length} alerts matches this view`, '', html`<button type="button" class="btn btn-sm" data-v2-book-kind="all" data-v2-book-all>Show all</button>`)}
    ${owner ? html`<div class="cluster al-owner">${unread ? html`<button type="button" class="btn btn-sm" data-v2-book-seen-all>Mark all read</button>` : ''}<button type="button" class="btn btn-sm btn-quiet" data-v2-book-clear ${S.confirmClear ? 'disabled' : ''}>Clear all</button></div>${confirm}` : ''}`;
}
const bookSub = () => {
  const n = S.alerts && S.alerts.unseen, owner = isOwner();
  return html`Not yours: these fire on the paper book Optic keeps for its scans and on the ranked universe, the same for every reader. Each names the rule that tripped it and the readings it tripped on.${owner && n ? html` <b>${n} unread.</b>` : ''}`;
};

function paint(main) {
  const bk = !!getFlags().brokerage;
  const f = document.activeElement, keep = f && main.contains(f) ? [...f.attributes].map((a) => a.name).find((n) => n.startsWith('data-v2-al-') || n.startsWith('data-v2-book-') || n.startsWith('data-sg-') || n === 'data-v2-check') : null, kv = keep ? f.getAttribute(keep) : null;
  draw($('#al-body', main), html`
    <section class="section first" aria-labelledby="h-w"><div class="section-head"><div><h2 class="t-h2" id="h-w">Your alerts</h2><p class="section-sub">${scheduleLine()}</p></div>
      <button type="button" class="btn btn-primary" data-v2-al-new="">New alert</button></div>${watchesBlock()}</section>
    <section class="section" aria-labelledby="h-hits"><div class="section-head"><div><h2 class="t-h2" id="h-hits">What fired</h2><p class="section-sub">One entry per crossing: an alert fires again only after its condition has stopped being met.</p></div></div>${hitsBlock()}</section>
    <section class="section" aria-labelledby="h-sg"><div class="section-head"><div><h2 class="t-h2" id="h-sg">Signal history</h2><p class="section-sub">Every swing-setup alert of yours that fired, recorded when it fired and never edited. What the stock did next is added beside it as each completed candle prints. ${SIG.whereLine()}</p></div></div><div id="al-sg">${SIG.block()}</div></section>
    <section class="section" aria-labelledby="h-l"><div class="section-head"><div><h2 class="t-h2" id="h-l">From Optic's paper book</h2><p class="section-sub">${bookSub()}</p></div></div>${ledger()}</section>
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
    <label class="field"><span class="sr">Symbol</span><input name="symbol" value="${f.symbol || ''}" data-v2-ta="submit" placeholder="Symbol, such as AAPL" maxlength="12" required autocomplete="off" autocapitalize="characters" spellcheck="false" enterkeyhint="next" ${f.id ? 'readonly' : ''}></label>
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
  if (!f.id && await api.knownSymbol(f.symbol) === false) return fail(`No quote came back for ${f.symbol}. Check the symbol before setting an alert on it.`);
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
function loadBook(force) {
  return api.get('/api/alerts?limit=50', { ttl: force ? 0 : 60000, force: !!force }).then((r) => { S.alerts = r; S.alertsErr = null; }, (e) => { S.alertsErr = e; });
}
/** Signal history alone, repainted in its own box so the rest of the page (a form, a filter, focus) is left alone. */
async function reloadSignals(main) {
  const box = () => $('#al-sg', main);
  const p = SIG.load();
  if (box()) draw(box(), SIG.block());
  await p;
  if (live && box()) draw(box(), SIG.block());
}
async function loadAll(main) {
  const signed = store.signedIn();
  const jobs = [
    api.get('/api/watches/catalogue', { ttl: 3600000 }).then((r) => {
      S.catalogue = r.conditions || []; S.schedule = r.schedule;
      const ss = S.catalogue.find((c) => c.id === 'swing_setup'), ch = (ss && ss.param && ss.param.choices) || [];
      SIG.SG.labels = Object.fromEntries(ch.filter((x) => x.value !== 'any').map((x) => [x.value, x.label]));
      if (SIG.SG.data && SIG.SG.data.where === 'browser') SIG.SG.options = SIG.optionsOf(SIG.SG.data.signals, SIG.SG.labels);
    }, (e) => { S.catErr = e; }),
    loadBook(),
    SIG.load(),
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
  S = { checks: {}, fam: 'all', unseenOnly: false, undo: null, stops: [], bookOpen: new Set(), bookKind: 'all', bookUnread: false, confirmClear: false };
  SIG.fresh();
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
  signals: (m) => { SIG.SG.error = null; reloadSignals(m); },
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
    if ((b = t('[data-v2-al-new]'))) { openForm(main, { symbol: b.dataset.v2AlNew || '', kind: (cond(b.dataset.kind) && b.dataset.kind) || 'price_above' }, b); return; }
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
        if ((r.results || []).some((x) => x.met && x.signal_record)) { SIG.SG.followedAt = null; SIG.load().then(() => { if (live) paint(main); }); }
      } catch (err) { S.checks[sym] = null; toast(api.explain(err, 'The check'), { kind: 'bad' }); }
      paint(main);
      const again = $(`[data-v2-check="${sym}"]`, main); if (again) again.focus();
      return;
    }
    if ((b = t('[data-v2-book-kind]'))) { S.bookKind = b.dataset.v2BookKind; if (b.hasAttribute('data-v2-book-all')) S.bookUnread = false; paint(main); return; }
    if ((b = t('[data-v2-book-why]'))) { const id = Number(b.dataset.v2BookWhy); if (S.bookOpen.has(id)) S.bookOpen.delete(id); else S.bookOpen.add(id); paint(main); return; }
    if ((b = t('[data-v2-book-seen]')) || t('[data-v2-book-seen-all]')) {
      const ids = b ? [Number(b.dataset.v2BookSeen)] : null;
      try {
        const r = await api.post('/api/alerts/seen', ids ? { ids } : {});
        if (r && r.shared === false) { toast(clean(r.detail || 'Nothing was marked.')); return; }
        (S.alerts.alerts || []).forEach((x) => { if (!ids || ids.includes(x.id)) x.seen = 1; });
        S.alerts.unseen = Math.max(0, (S.alerts.unseen || 0) - ((r && r.marked) || 0));
        paint(main);
        const next = $('[data-v2-book-seen]', main) || $('[data-v2-book-clear]', main); if (next) next.focus();
      } catch (err) { toast(api.explain(err, 'That'), { kind: 'bad' }); }
      return;
    }
    if (t('[data-v2-book-clear]')) { S.confirmClear = true; paint(main); const y = $('[data-v2-book-clear-yes]', main); if (y) y.focus(); return; }
    if (t('[data-v2-book-clear-no]')) { S.confirmClear = false; paint(main); const c = $('[data-v2-book-clear]', main); if (c) c.focus(); return; }
    if (t('[data-v2-book-clear-yes]')) {
      try { const r = await api.post('/api/alerts/clear', {}); S.confirmClear = false; S.bookOpen.clear(); toast(`Cleared ${(r && r.removed) || 0} alert${(r && r.removed) === 1 ? '' : 's'} from the inbox.`); await loadBook(true); }
      catch (err) { toast(api.explain(err, 'Clearing'), { kind: 'bad' }); }
      if (live) { paint(main); const h = $('#h-l', main); if (h) { h.tabIndex = -1; h.focus(); } }
      return;
    }
    if (t('[data-sg-reset]')) { SIG.SG.f = { status: 'all', direction: 'all', symbol: '', strategy: '' }; await reloadSignals(main); const f = $('[data-sg-status]', main); if (f) f.focus(); return; }
    if (t('[data-v2-hits-seen]')) {
      try { await api.post('/api/watches/hits/seen', {}); S.hits = S.hits.map((h) => Object.assign(h, { seen: true })); paint(main); refreshUnread(); }
      catch (err) { toast(api.explain(err, 'That'), { kind: 'bad' }); }
    }
  });
  main.addEventListener('change', (e) => {
    if (e.target.matches('[data-v2-al-unseen]')) { S.unseenOnly = e.target.checked; paint(main); const c = $('[data-v2-al-unseen]', main); if (c) c.focus(); return; }
    if (e.target.matches('[data-v2-book-unread]')) { S.bookUnread = e.target.checked; paint(main); const c = $('[data-v2-book-unread]', main); if (c) c.focus(); return; }
    const k = { 'data-sg-status': 'status', 'data-sg-dir': 'direction', 'data-sg-symbol': 'symbol', 'data-sg-strategy': 'strategy' };
    const attr = Object.keys(k).find((a) => e.target.hasAttribute(a));
    if (attr) { SIG.SG.f[k[attr]] = e.target.value; reloadSignals(main).then(() => { const c = $(`[${attr}]`, main); if (c) c.focus(); }); }
  });
  // an open record stays open across repaints; toggle does not bubble, so this listens in the capture phase
  main.addEventListener('toggle', (e) => { const d = e.target; if (d && d.matches && d.matches('details[data-sg-key]')) SIG.SG.open[d.getAttribute('data-sg-key')] = d.open; }, true);
}
