// Positions, Paper Desk: the reader's own book, entered by hand and priced by
// the terminal. Kept in this browser under the classic key (optic.paper.v1,
// a personal key: it follows the person on this browser, not the server).
// Marks come from POST /api/paper/mark, the option chain for the ticket from
// /api/chain/{SYM}, and Optic's read from /api/ticker/{SYM}, recorded on the
// trade at the moment it opens. No model call.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, compact, clean, shortDate, isNum, dir, plural } from '../core/format.js';
import { signedBars } from '../ui/bars.js';
import { mountCharts } from '../ui/chart.js';
import { provideContext } from '../ui/milo.js';
import { sectionHead } from './tabs.js';
import { etStamp } from '../core/marketTime.js';
import * as J from '../core/journal.js';
import * as RP from './paper-replay.js';
import { hrefFor } from '../nav.js';
import { button as miloButton } from '../ui/milo.js';

// A plan handed over from research (the contract picker): read once, then removed, so a reload does not refill it
export const DRAFT_KEY = 'optic.v2.paper.draft.v1';
const KEY = 'optic.paper.v1', MAX = 50, KEEP_CLOSED = 200, R_SHOWN = 30, EXPIRY_DAYS = 7, CONCENTRATED = 0.4;

/* ---------------- the classic arithmetic ---------------- */
const mult = (p) => (p.instrument === 'option' ? 100 : 1);
export const cost = (p) => p.entry_price * p.qty * mult(p);
export function risk(p) { if (!p.stop) return null; return Math.abs(p.entry_price - p.stop) * p.qty * mult(p); }
export function rOf(p, pnl) { const r = risk(p); if (!r || pnl === null || pnl === undefined) return null; return pnl / r; }
export const rText = (r) => (r === null || r === undefined || !Number.isFinite(r) ? 'n/a' : `${r >= 0 ? '+' : ''}${num(r, 2)}R`);
export function agrees(read, direction) {
  if (!read || !read.stance) return null;
  if (read.stance === 'bullish') return direction === 'long';
  if (read.stance === 'bearish') return direction === 'short';
  return null;
}
const etToday = (t = Date.now()) => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(t);
/** Portfolio health from the book and its marks (static/app.js paperHealth). */
export function health(open, marks, today = etToday()) {
  if (!open.length) return null;
  const bySym = {}; let long = 0, short = 0, pnl = 0, marked = 0; const review = [];
  open.forEach((p) => {
    const c = Math.abs(cost(p)) || 0;
    bySym[p.ticker] = (bySym[p.ticker] || 0) + c;
    if (p.direction === 'short') short += c; else long += c;
    const m = marks[p.id] || {};
    if (isNum(m.pnl)) { pnl += m.pnl; marked += 1; }
    const why = [], r = rOf(p, m.pnl);
    if (r !== null && r <= -0.75) why.push(`${rText(r)}, within a quarter of its stop`);
    if (p.instrument === 'option' && p.expiry && today) {
      const days = Math.round((Date.parse(`${String(p.expiry).slice(0, 10)}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86400000);
      if (days < 0) why.push('expired and still open'); else if (days === 0) why.push('expires today'); else if (days <= EXPIRY_DAYS) why.push(`expires in ${days} day${days === 1 ? '' : 's'}`);
    }
    if (why.length) review.push({ p, why: why.join('; ') });
  });
  const total = long + short, ranked = Object.entries(bySym).sort((a, b) => b[1] - a[1]), top = ranked[0];
  return { total, long, short, pnl, marked, ranked, top, topShare: total ? top[1] / total : 0, top3: total ? ranked.slice(0, 3).reduce((a, x) => a + x[1], 0) / total : 0, review };
}

/* ---------------- state ---------------- */
let book = { open: [], closed: [] }, ticket = blankTicket(), chain = null, chainFor = '', chainState = 'idle', chainErr = '';
let markedAt = null, marks = {}, marking = false, markFailed = false, armed = false, note = '', reads = {}, live = true, mainEl = null, health0 = null, fromDraft = '';
function blankTicket() { return { ticker: '', instrument: 'shares', direction: 'long', qty: '', entry: '', stop: '', target: '', thesis: '', expiry: '', strike: '', optionType: 'call',
  // the journal's plan (core/journal.js): frozen on the trade when it opens
  setup: 'other', evidence: [{ text: '', family: 'trend' }, { text: '', family: 'momentum' }], against: '', catalyst: '', catalyst_date: '', hold_through: false, trigger: '', invalidation: '', hold_days: '', entry_note: '', source: '' }; }
/** A draft from research becomes the ticket, without re-typing it. */
export function ticketFromDraft(d, base = blankTicket()) {
  if (!d || !d.ticker) return base;
  return { ...base, ticker: String(d.ticker).toUpperCase(), instrument: d.instrument === 'option' ? 'option' : 'shares', direction: d.direction === 'short' ? 'short' : 'long',
    optionType: d.option_type === 'put' ? 'put' : 'call', expiry: d.expiry || '', strike: d.strike != null ? String(d.strike) : '', qty: d.qty ? String(d.qty) : '',
    entry: d.entry ? String(d.entry) : '', stop: d.stop ? String(d.stop) : '', target: d.target ? String(d.target) : '', thesis: d.thesis || '',
    hold_days: d.hold_days ? String(d.hold_days) : '', catalyst: d.catalyst || '', catalyst_date: d.catalyst_date || '', hold_through: !!d.hold_through,
    invalidation: d.invalidation || '', trigger: d.trigger || '', setup: d.setup || 'other', source: d.source || '' };
}
function loadBook() {
  book = { open: [], closed: [] };
  if (!holds(store.state.user)) return;
  try { const raw = JSON.parse(localStorage.getItem(KEY) || 'null'); if (raw && Array.isArray(raw.open) && Array.isArray(raw.closed)) book = raw; } catch (e) { /* a corrupt blob reads as an empty book */ }
}
function save() { if (!holds(store.state.user)) return; try { localStorage.setItem(KEY, JSON.stringify(book)); } catch (e) { /* private mode: the book lasts as long as the tab */ } }
const pid = () => `p${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
const sym = () => (ticket.ticker || '').toUpperCase().trim();
const readFor = (s) => reads[s] || null;
const money2 = (v) => `${v >= 0 ? '+' : '−'}$${compact(Math.abs(v))}`;
const posLabel = (p) => (p.instrument !== 'option' ? `${p.qty} ${p.ticker}` : `${p.qty} ${p.ticker} ${num(p.strike)} ${p.option_type} ${String(p.expiry).slice(5)}`);
function picked() {
  const c = chain && chain.ticker === sym() ? chain : null;
  return c && ticket.expiry && ticket.strike ? c.rows.find((r) => r.expiry === ticket.expiry && String(r.strike) === String(ticket.strike) && r.is_call === (ticket.optionType === 'call')) : null;
}

/* ---------------- sections ---------------- */
function healthBlock() {
  const h = health(book.open, marks);
  if (!h) return '';
  const names = h.ranked.length, conc = h.topShare >= CONCENTRATED && names > 1;
  const lean = !h.total ? 'flat' : h.short === 0 ? 'all long' : h.long === 0 ? 'all short' : h.long >= h.short ? `net long, ${Math.round((h.long / h.total) * 100)}% of exposure` : `net short, ${Math.round((h.short / h.total) * 100)}% of exposure`;
  const modelledN = book.open.filter((p) => /^modelled/i.test(String((marks[p.id] || {}).mark_source || ''))).length;
  const realtime = !!(health0 && health0.realtime_chain);
  const isShort = (s) => { const mine = book.open.filter((p) => p.ticker === s); return mine.length > 0 && mine.every((p) => p.direction === 'short'); };
  const parts = h.ranked.slice(0, 6).map(([s, v], i) => ({ name: `${s}${isShort(s) ? ' short' : ''}`, share: v / (h.total || 1), cls: `s${i + 1}` }));
  const rest = h.ranked.slice(6); if (rest.length) parts.push({ name: `${rest.length} other${rest.length === 1 ? '' : 's'}`, share: rest.reduce((a, [, v]) => a + v, 0) / (h.total || 1), cls: 's0' });
  return html`<section class="section first" aria-labelledby="ph-h"><div class="section-head"><h2 class="t-h2" id="ph-h">Portfolio health</h2>
      <span class="pill">${h.marked < book.open.length ? `${book.open.length - h.marked} of ${book.open.length} not marked` : `${realtime ? 'Marked from live quotes' : 'Marked from delayed quotes'}${markedAt ? ` at ${etStamp(markedAt)}` : ''}${modelledN ? `; ${modelledN} option${modelledN === 1 ? '' : 's'} estimated by a model` : ''}`}</span></div>
    <p class="lead-line">${names === 1 ? `One name, ${h.top[0]}, is the whole book.` : conc ? `${h.top[0]} is ${Math.round(h.topShare * 100)}% of the book, which is concentrated.` : `Spread across ${names} names; the largest, ${h.top[0]}, is ${Math.round(h.topShare * 100)}%.`} It is ${lean}. ${h.review.length ? `${h.review.length} position${h.review.length === 1 ? ' needs' : 's need'} a look.` : 'Nothing is near its stop or its expiry.'}</p>
    <dl class="kv" style="--kv:3"><div><dt>Exposure</dt><dd>$${compact(h.total)}</dd><p class="kv-note">at cost, ${book.open.length} position${book.open.length === 1 ? '' : 's'}</p></div>
      <div><dt>Open P&L</dt><dd class="${h.marked ? (h.pnl >= 0 ? 'up' : 'down') : ''}">${h.marked ? money2(h.pnl) : 'n/a'}</dd><p class="kv-note">${!h.marked ? 'waiting on marks' : modelledN ? `a quote, not a result; ${modelledN} of it a model's estimate` : 'a quote, not a result'}</p></div>
      <div><dt>Largest name</dt><dd>${Math.round(h.topShare * 100)}%</dd><p class="kv-note">${h.top[0]}${names > 3 ? `, top three ${Math.round(h.top3 * 100)}%` : ''}</p></div></dl>
    <div class="ph-bar" role="img" aria-label="Exposure at cost: ${parts.map((x) => `${x.name} ${Math.round(x.share * 100)}%`).join(', ')}">${parts.map((x) => html`<span class="ph-seg ${x.cls}" style="flex-grow:${x.share.toFixed(4)}"></span>`)}</div>
    <ul class="ph-legend" aria-hidden="true">${parts.map((x) => html`<li><i class="${x.cls}"></i>${x.name} ${Math.round(x.share * 100)}%</li>`)}</ul>
    ${h.review.length ? html`<h3>Needs review</h3><ul class="plain">${h.review.map((x) => html`<li><b>${posLabel(x.p)}</b> <span class="t-muted">${x.why}</span></li>`)}</ul>` : ''}
    <p class="asof">Computed from this book alone. It does not see sectors, upcoming earnings or how these names move together, and it does not know about anything you hold elsewhere.</p></section>`;
}

/* ---------------- the journal's plan (roadmap stage 3) ---------------- */
function planFold() {
  const t = ticket, ind = J.independence(t.evidence.filter((e) => e.text.trim()));
  return html`<details class="pt-plan more-inline" ${fromDraft || t.trigger || t.catalyst ? 'open' : ''}><summary>The plan</summary><p class="asof">Kept with the trade as it was when you opened it; a later change is recorded beside it.</p>
    <div class="pt-row"><label class="select pt-f"><span class="t-label">Setup</span><select name="setup" data-v2-pt-plan>${J.SETUPS.map(([k, l]) => html`<option value="${k}" ${t.setup === k ? 'selected' : ''}>${l}</option>`)}</select></label>
      <label class="pt-f"><span class="t-label">Planned hold, days</span><span class="field"><input name="hold_days" type="number" min="1" step="1" inputmode="numeric" value="${t.hold_days}" data-v2-pt-plan></span></label></div>
    <fieldset class="pt-ev"><legend class="t-label">What supports it</legend>
      ${t.evidence.map((e, i) => html`<div class="pt-row"><label class="select pt-f"><span class="sr">Kind of evidence ${i + 1}</span><select data-v2-pt-ev-fam="${i}">${Object.entries(J.FAMILIES).map(([k, f]) => html`<option value="${k}" ${e.family === k ? 'selected' : ''}>${f.label}</option>`)}</select></label>
        <label class="pt-f pt-grow"><span class="sr">Evidence ${i + 1}</span><span class="field"><input data-v2-pt-ev-text="${i}" maxlength="160" value="${e.text}" placeholder="${i ? 'RSI back above 50' : 'Held the 50-day average'}"></span></label></div>`)}
      ${t.evidence.length < 6 ? html`<button type="button" class="textlink" data-v2-pt-ev-add>Add evidence</button>` : ''}
      <p class="asof">${ind.note}</p></fieldset>
    <label class="pt-f"><span class="t-label">What argues against it</span><span class="field"><input name="against" maxlength="320" value="${t.against}" data-v2-pt-plan placeholder="Below its 200-day; sector lagging"></span></label>
    <div class="pt-row"><label class="pt-f pt-grow"><span class="t-label">Catalyst</span><span class="field"><input name="catalyst" maxlength="120" value="${t.catalyst}" data-v2-pt-plan placeholder="Earnings"></span></label>
      <label class="pt-f"><span class="t-label">Its date</span><span class="field"><input name="catalyst_date" type="date" value="${t.catalyst_date}" data-v2-pt-plan></span></label></div>
    <label class="check"><input type="checkbox" name="hold_through" ${t.hold_through ? 'checked' : ''} data-v2-pt-plan> <span>I mean to hold through it</span></label>
    <label class="pt-f"><span class="t-label">Entry trigger, if it is conditional</span><span class="field"><input name="trigger" maxlength="200" value="${t.trigger}" data-v2-pt-plan placeholder="A daily close above 352"></span></label>
    <label class="pt-f"><span class="t-label">What would make it wrong</span><span class="field"><input name="invalidation" maxlength="200" value="${t.invalidation}" data-v2-pt-plan placeholder="A close below the 50-day"></span></label>
    <label class="pt-f"><span class="t-label">What you saw when you entered</span><span class="field"><input name="entry_note" maxlength="200" value="${t.entry_note}" data-v2-pt-plan placeholder="Opened strong, volume above average"></span></label>
  </details>`;
}
const PLAN_KEYS = ['setup', 'hold_days', 'against', 'catalyst', 'catalyst_date', 'trigger', 'invalidation', 'entry_note'];
function planOf(t, entry, qty, m) {
  const stop = Number(t.stop), risk = stop > 0 ? Math.abs(entry - stop) * qty * m : null;
  return J.freezePlan({ thesis: t.thesis, setup: t.setup, evidence: t.evidence, against: String(t.against || '').split(/;|\n/).map((x) => x.trim()),
    catalyst: t.catalyst, catalyst_date: t.catalyst_date, hold_through_catalyst: t.hold_through, trigger: t.trigger, invalidation: t.invalidation,
    hold_days: t.hold_days, stop, target: Number(t.target) || null, risk, source: t.source });
}

function ticketForm() {
  const t = ticket, isOpt = t.instrument === 'option', s = sym();
  const c = chain && chain.ticker === s ? chain : null;
  const expiries = c ? [...new Set(c.rows.map((r) => r.expiry))] : [];
  const strikes = c && t.expiry ? [...new Set(c.rows.filter((r) => r.expiry === t.expiry && r.is_call === (t.optionType === 'call')).map((r) => r.strike))].sort((a, b) => a - b) : [];
  const pk = picked(), read = readFor(s), ag = agrees(read, t.direction);
  const prompt = !t.ticker ? 'Type a symbol above' : chainState === 'failed' ? `Could not read ${s}'s chain` : chainState === 'empty' ? `${s} has no listed options` : `Reading ${s}'s chain…`;
  return html`<section class="section ${book.open.length ? '' : 'first'}" aria-labelledby="pt-h"><h2 class="t-h2" id="pt-h">Open a trade</h2>
    <form class="pt-form" data-v2-pt-form novalidate>
      <div class="pt-row"><div class="pt-f pt-sym"><label class="t-label" for="pt-ticker">Symbol</label><span class="field"><input id="pt-ticker" name="ticker" value="${t.ticker}" placeholder="NVDA" maxlength="12" spellcheck="false" autocomplete="off" autocapitalize="characters"></span></div>
        <div class="pt-f"><span class="t-label" id="pt-dir">Direction</span><div class="seg" role="group" aria-labelledby="pt-dir"><button type="button" data-v2-pt-dir="long" aria-pressed="${t.direction === 'long'}">Long</button><button type="button" data-v2-pt-dir="short" aria-pressed="${t.direction === 'short'}">Short</button></div></div>
        <div class="pt-f"><span class="t-label" id="pt-inst">Instrument</span><div class="seg" role="group" aria-labelledby="pt-inst"><button type="button" data-v2-pt-inst="shares" aria-pressed="${!isOpt}">Shares</button><button type="button" data-v2-pt-inst="option" aria-pressed="${isOpt}">Option</button></div></div></div>
      ${isOpt ? html`<div class="pt-row"><div class="pt-f"><span class="t-label" id="pt-ot">Call or put</span><div class="seg" role="group" aria-labelledby="pt-ot"><button type="button" data-v2-pt-ot="call" aria-pressed="${t.optionType === 'call'}">Call</button><button type="button" data-v2-pt-ot="put" aria-pressed="${t.optionType === 'put'}">Put</button></div></div>
          <label class="select pt-f"><span class="t-label">Expiry</span><select name="expiry" data-v2-pt-expiry ${expiries.length ? '' : 'disabled'}>${expiries.length ? '' : html`<option value="">${prompt}</option>`}${expiries.length && !t.expiry ? html`<option value="">Pick an expiry</option>` : ''}${expiries.map((e) => html`<option value="${e}" ${t.expiry === e ? 'selected' : ''}>${e}</option>`)}</select></label>
          <label class="select pt-f"><span class="t-label">Strike</span><select name="strike" data-v2-pt-strike ${strikes.length ? '' : 'disabled'}>${strikes.length ? (t.strike ? '' : html`<option value="">Pick a strike</option>`) : html`<option value="">${expiries.length ? 'Pick an expiry' : 'n/a'}</option>`}${strikes.map((k) => html`<option value="${k}" ${String(t.strike) === String(k) ? 'selected' : ''}>${num(k)}</option>`)}</select></label></div>
        ${chainState === 'failed' ? html`<p class="stale">Could not read the options chain for ${s}${chainErr ? ` (${chainErr})` : ''}. <button type="button" class="textlink" data-v2-pt-chain>Try again</button></p>` : ''}
        ${pk ? html`<p class="pt-quote">${pk.contract}, mid <b>$${num(pk.mid)}</b> (bid ${num(pk.bid)} / ask ${num(pk.ask)}), ${plural(num(pk.dte, 0), 'day')}, delta ${num(pk.delta)}${isNum(pk.spread_pct) ? `, spread ${num(pk.spread_pct, 1)}%` : ''}${pk.spread_pct > 10 ? html`<span class="down">, which is wide, so a real fill would be worse.</span>` : ''}</p>` : ''}` : ''}
      <div class="pt-row pt-nums"><label class="pt-f"><span class="t-label">${isOpt ? 'Contracts' : 'Shares'}</span><span class="field"><input name="qty" type="number" min="0" step="any" inputmode="decimal" value="${t.qty}" placeholder="100"></span></label>
        <label class="pt-f"><span class="t-label">Entry ${isOpt ? 'premium' : 'price'}</span><span class="field"><input name="entry" type="number" min="0" step="any" inputmode="decimal" value="${t.entry}" placeholder="${pk ? num(pk.mid) : 'Last price'}"></span></label>
        <label class="pt-f"><span class="t-label">Stop</span><span class="field"><input name="stop" type="number" min="0" step="any" inputmode="decimal" value="${t.stop}" aria-required="true"></span></label>
        <label class="pt-f"><span class="t-label">Target <span class="t-muted">(optional)</span></span><span class="field"><input name="target" type="number" min="0" step="any" inputmode="decimal" value="${t.target}"></span></label></div>
      <label class="pt-f"><span class="t-label">Why, and what would prove you wrong</span><span class="field"><input name="thesis" maxlength="600" value="${t.thesis}" placeholder="Held the 200-day and volume came in"></span></label>
      ${planFold()}
      ${s ? (read ? html`<p class="pt-read">Optic reads ${s} as <b class="${read.stance === 'bullish' ? 'up' : read.stance === 'bearish' ? 'down' : ''}">${read.stance}</b>${read.conviction ? `, ${read.conviction} conviction` : ''}. ${ag === null ? 'Neither with nor against you.' : ag ? 'That agrees with this trade.' : 'That is against this trade.'} <span class="t-muted">Recorded on the trade, and scored separately below.</span></p>`
        : html`<p class="pt-read">Optic has no read on ${s} loaded. <button type="button" class="textlink" data-v2-pt-read="${s}">Load it</button> and this trade will record what the terminal thought at the moment you opened it.</p>`) : ''}
      <div aria-live="polite" data-v2-pt-preview>${preview()}</div>
      <div class="cluster"><button type="submit" class="btn btn-primary">Open the trade</button><button type="button" class="btn" data-v2-pt-clear>Clear</button></div>
      ${note ? html`<p class="pt-note" role="status">${note}${markFailed ? html` <button type="button" class="textlink" data-v2-pt-remark>Price it again</button>` : ''}</p>` : ''}</form></section>`;
}
function preview() {
  const t = ticket, qty = Number(t.qty), entry = Number(t.entry), stop = Number(t.stop), target = Number(t.target), m = t.instrument === 'option' ? 100 : 1;
  if (!(qty > 0) || !(entry > 0)) return '';
  const r = stop > 0 ? Math.abs(entry - stop) * qty * m : null, reward = target > 0 ? Math.abs(target - entry) * qty * m : null;
  const wrong = stop > 0 && ((t.direction === 'long' && stop >= entry) || (t.direction === 'short' && stop <= entry));
  return html`<p class="pt-preview"><span><span class="t-muted">Costs</span> $${compact(entry * qty * m)}</span><span><span class="t-muted">Risks</span> ${r === null ? html`<span class="down">no stop set</span>` : `$${compact(r)}`}</span>${reward !== null && r ? html`<span><span class="t-muted">Reward:risk</span> ${num(reward / r, 2)} to 1</span>` : ''}${wrong ? html`<span class="down">Stop is on the wrong side of entry for a ${t.direction}.</span>` : ''}</p>`;
}

/** An open trade's plan can change; each change is a dated revision beside the original (core/journal.js revise). */
function planEditRow(tr) {
  const cur = J.currentPlan(tr);
  if (!tr.plan) return '';
  const f = (k, label, type = 'text') => html`<label class="pt-f"><span class="t-label">${label}</span><span class="field"><input data-v2-pt-rev="${tr.id}" name="${k}" type="${type}" value="${cur[k] ?? ''}" maxlength="200"></span></label>`;
  return html`<details class="pt-rev" data-rev-id="o-${tr.id}"><summary>Plan for ${posLabel(tr)} <span class="t-muted">${(tr.revisions || []).length ? `changed ${plural(tr.revisions.length, 'time')}` : 'as opened'}</span></summary>
    <div class="pt-row">${f('target', 'Target', 'number')}${f('hold_days', 'Planned hold, days', 'number')}</div>${f('invalidation', 'What would make it wrong')}
    <p class="asof">Opened ${shortDate(tr.plan.at)} with: ${tr.plan.invalidation || 'no invalidation written'}${tr.plan.target ? `, target ${num(tr.plan.target)}` : ''}${isNum(tr.plan.hold_days) ? `, ${plural(tr.plan.hold_days, 'day')}` : ''}. A change here is kept beside that, never over it.</p></details>`;
}

function openTable() {
  const o = book.open;
  return html`<section class="section" aria-labelledby="po-h"><h2 class="t-h2" id="po-h">Open, ${o.length}</h2>
    ${o.length ? html`<div class="tscroll"><table class="t"><thead><tr><th scope="col">Position</th><th scope="col">Entry</th><th scope="col">Mark</th><th scope="col">Marked from</th><th scope="col">P&L</th><th scope="col">R</th><th scope="col">Optic then</th><th scope="col"><span class="sr">Close</span></th></tr></thead>
      <tbody>${o.map((p) => { const m = marks[p.id] || {}, pnl = m.pnl, r = rOf(p, pnl), cls = !isNum(pnl) ? '' : pnl >= 0 ? 'up' : 'down', ag = agrees(p.read, p.direction);
        return html`<tr><td>${posLabel(p)} <span class="pill ${p.direction === 'long' ? 'up' : 'down'}">${p.direction}</span></td><td>${num(p.entry_price)}</td><td>${isNum(m.mark_price) ? num(m.mark_price) : 'n/a'}</td>
          <td class="pt-src">${m.mark_source ? m.mark_source : html`<span class="t-muted">${m.reason || (marking ? 'pricing…' : 'not marked')}</span>`}</td><td class="${cls}">${isNum(pnl) ? money2(pnl) : 'n/a'}</td><td class="${cls}">${rText(r)}</td>
          <td>${p.read ? html`<span class="${ag === null ? 't-muted' : ag ? 'up' : 'down'}" title="${p.read.summary || ''}">${p.read.stance}${ag === null ? '' : ag ? ', with' : ', against'}</span>` : html`<span class="t-muted">n/a</span>`}</td>
          <td><button type="button" class="btn btn-sm" data-v2-pt-close="${p.id}" ${isNum(m.mark_price) ? '' : 'disabled'} title="Close at the current mark" aria-label="Close ${posLabel(p)} at the current mark">Close</button></td></tr>`; })}</tbody></table></div>
      <p class="asof">${markedAt ? `Marks taken ${etStamp(markedAt)}; a mark is a quote, delayed about 15 minutes in session and the last close outside it. ` : ''}Closing takes the current mark: the last trade for shares, the chain's mid for an option, or a model's estimate when the contract has no quote. A real fill would be at the bid or the ask.</p>`
      : html`<p class="quiet">No open positions. The ticket above opens one.</p>`}${o.length ? html`<div class="pt-revs">${o.map(planEditRow)}</div>` : ''}</section>`;
}

/** One closed trade's plan beside what happened, its adherence and the reflection: kept on the trade. */
function reviewRow(tr) {
  const p = tr.plan, a = tr.adherence || {}, days = tr.entry_at && tr.closed_at ? Math.max(0, Math.round((Date.parse(tr.closed_at) - Date.parse(tr.entry_at)) / 86400000)) : null;
  const sel = (k, q) => html`<label class="select pt-f"><span class="t-label">${q}</span><select data-v2-pt-adh="${tr.id}" data-k="${k}">${[['', 'Not recorded'], ['yes', 'Yes'], ['no', 'No']].map(([v, l]) => html`<option value="${v}" ${(a[k] || '') === v ? 'selected' : ''}>${l}</option>`)}</select></label>`;
  return html`<details class="pt-rev" data-rev-id="c-${tr.id}"><summary>${posLabel(tr)} <span class="t-muted">${p ? (J.SETUPS.find(([k]) => k === p.setup) || ['', ''])[1] : 'no plan recorded'}</span></summary>
    ${p ? html`<dl class="kv" style="--kv:3"><div><dt>Planned</dt><dd>${isNum(p.hold_days) ? plural(p.hold_days, 'day') : 'no hold set'}</dd><p class="kv-note">risk ${isNum(p.risk) ? `$${compact(p.risk)}` : 'not set'}, stop ${num(p.stop)}${p.target ? `, target ${num(p.target)}` : ''}</p></div>
      <div><dt>Actual</dt><dd class="${dir(tr.pnl)}">${money2(tr.pnl)}</dd><p class="kv-note">${isNum(days) ? `held ${plural(days, 'day')}` : ''}, ${rText(tr.r)}, out at ${num(tr.exit_price)}</p></div>
      <div><dt>Evidence</dt><dd>${J.independence(p.evidence).families}</dd><p class="kv-note">independent ${J.independence(p.evidence).families === 1 ? 'kind' : 'kinds'} recorded</p></div></dl>
      ${p.thesis ? html`<p><b>Thesis then.</b> ${p.thesis}</p>` : ''}${p.trigger ? html`<p><b>Trigger.</b> ${p.trigger}</p>` : ''}${p.invalidation ? html`<p><b>Wrong if.</b> ${p.invalidation}</p>` : ''}
      ${p.catalyst ? html`<p><b>Catalyst.</b> ${p.catalyst}${p.catalyst_date ? `, ${shortDate(p.catalyst_date)}` : ''}${p.hold_through_catalyst ? ', planned to hold through it' : ''}</p>` : ''}
      ${(tr.revisions || []).length ? html`<p class="asof">Plan changed ${plural(tr.revisions.length, 'time')} after opening: ${tr.revisions.map((r) => `${r.field} from ${r.from === null ? 'blank' : r.from} to ${r.to}`).join('; ')}. The record above is the original.</p>` : ''}` : html`<p class="t-muted">Opened before the journal existed, or without a plan.</p>`}
    <div class="pt-row">${sel('entry', 'Entered as planned?')}${sel('exit', 'Exited as planned?')}${sel('size', 'Sized to the planned risk?')}</div>
    <label class="pt-f"><span class="t-label">Reflection</span><span class="field"><input data-v2-pt-refl="${tr.id}" maxlength="400" value="${tr.reflection || ''}" placeholder="What you would do the same, or differently"></span></label>
    <p class="asof">Saved in this browser with the trade.</p></details>`;
}

/** The journal's review of the closed record (core/journal.js review), each figure with its count. */
function journalBlock() {
  const rv = J.review(book.closed);
  if (!rv.all.n) return '';
  const row = (x) => html`<tr><th scope="row">${x.label}</th><td>${x.n}</td><td>${isNum(x.win_rate) ? `${Math.round(x.win_rate * 100)}%` : 'n/a'}</td><td class="${dir(x.expectancy)}">${isNum(x.expectancy) ? money2(x.expectancy) : 'n/a'}</td><td>${x.n_r ? rText(x.expectancy_r) : 'n/a'}</td></tr>`;
  const table = (title, rows) => html`<h3>${title}</h3><div class="tscroll"><table class="t"><thead><tr><th scope="col">Group</th><th scope="col">Trades</th><th scope="col">Won</th><th scope="col">Average result</th><th scope="col">Average R</th></tr></thead><tbody>${rows.map(row)}</tbody></table></div>`;
  const m = rv.missing, gaps = [m.no_plan ? `${m.no_plan} without a plan` : '', m.no_adherence ? `${m.no_adherence} without adherence answers` : '', m.no_reflection ? `${m.no_reflection} without a reflection` : ''].filter(Boolean);
  return html`<section class="section" aria-labelledby="pj-h"><div class="section-head"><div><h2 class="t-h2" id="pj-h">Journal review</h2><p class="section-sub">${rv.note || `From ${rv.all.n} closed trades.`}</p></div>
      ${miloButton('Ask Milo to review my process', { ask: 'Review the process in my recorded paper trades: where did I follow my plans, where did I depart from them, and what do the outcomes and my reflections suggest? Use only what is recorded.', context: 'Paper Desk, journal review' })}</div>
    <dl class="kv" style="--kv:4"><div><dt>Average win</dt><dd class="up">${isNum(rv.all.avg_win) ? money2(rv.all.avg_win) : 'n/a'}</dd><p class="kv-note">${rv.all.wins} won</p></div><div><dt>Average loss</dt><dd class="down">${isNum(rv.all.avg_loss) ? money2(rv.all.avg_loss) : 'n/a'}</dd><p class="kv-note">${rv.all.losses} lost</p></div>
      <div><dt>Expectancy</dt><dd class="${dir(rv.all.expectancy)}">${money2(rv.all.expectancy)}</dd><p class="kv-note">average per trade${rv.all.n_r ? `, ${rText(rv.all.expectancy_r)}` : ''}</p></div>
      <div><dt>Worst run</dt><dd class="down">${isNum(rv.max_drawdown) ? money2(rv.max_drawdown) : 'n/a'}</dd><p class="kv-note">largest fall in realised results, peak to trough</p></div></dl>
    ${table('By setup', rv.by_setup)}${table('By time held', rv.by_hold)}${table('Catalysts', rv.by_catalyst)}${table('Following the plan', rv.by_adherence)}
    <p class="asof">${gaps.length ? `Missing records: ${gaps.join(', ')}. ` : ''}Grouped by what was recorded at the time. Kept in this browser; nothing here reaches Optic Portfolio, whose shared record is separate.</p>
    <div class="pt-revs">${book.closed.slice(0, 30).map(reviewRow)}</div></section>`;
}

function recordBlock() {
  const done = book.closed;
  if (!done.length) return html`<section class="section"><h2 class="t-h2">Record</h2><p class="quiet">Nothing closed yet. Every number here is realised: an open position's profit is a quote, not a result.</p></section>`;
  const wins = done.filter((t) => t.pnl > 0), total = done.reduce((a, t) => a + t.pnl, 0), withR = done.filter((t) => isNum(t.r)), avgR = withR.length ? withR.reduce((a, t) => a + t.r, 0) / withR.length : null;
  const sided = (want) => { const rows = done.filter((t) => agrees(t.read, t.direction) === want && isNum(t.r)); return rows.length ? { n: rows.length, avg: rows.reduce((a, t) => a + t.r, 0) / rows.length } : null; };
  const w = sided(true), a = sided(false);
  return html`<section class="section" aria-labelledby="pr-h"><h2 class="t-h2" id="pr-h">Record</h2>
    <p class="section-sub">${done.length} closed, ${wins.length} up, ${Math.round((wins.length / done.length) * 100)}% win rate</p>
    <dl class="kv" style="--kv:2"><div><dt>Realised</dt><dd class="${dir(total)}">${money2(total)}</dd><p class="kv-note">all ${done.length} closed${done.length > 50 ? ', the table shows the newest 50' : ''}</p></div><div><dt>Average</dt><dd class="${dir(avgR)}">${rText(avgR)}</dd><p class="kv-note">per trade, in multiples of what it risked</p></div></dl>
    ${withR.length >= 2 ? html`<h3>${withR.filter((t) => t.r > 0).length} of ${withR.length} trades with a stop made more than they risked to lose${withR.length > R_SHOWN ? `; the latest ${R_SHOWN} drawn` : ''}</h3><div class="chart-slot" data-chart="r"></div><p class="asof">Each closed trade in multiples of what its stop said it could lose, oldest first. Kept in this browser only.</p>` : ''}
    ${w || a ? html`<h3>With the terminal, and against it</h3><dl class="kv" style="--kv:2">${w ? html`<div><dt>Traded with Optic's read</dt><dd class="${dir(w.avg)}">${rText(w.avg)}</dd><p class="kv-note">${w.n} trade${w.n === 1 ? '' : 's'}</p></div>` : ''}${a ? html`<div><dt>Traded against it</dt><dd class="${dir(a.avg)}">${rText(a.avg)}</dd><p class="kv-note">${a.n} trade${a.n === 1 ? '' : 's'}</p></div>` : ''}</dl>
      <p class="asof">The read is the one Optic held when the trade was opened, not today's. Trades where it was neutral are in neither column: a neutral read was not an opinion to disagree with. Two or three trades is not a finding about anything.</p>` : ''}</section>
    <section class="section" aria-labelledby="pc-h"><h2 class="t-h2" id="pc-h">Closed</h2>
      <div class="tscroll"><table class="t"><thead><tr><th scope="col">Position</th><th scope="col">Entry</th><th scope="col">Exit</th><th scope="col">P&L</th><th scope="col">R</th><th scope="col">Optic then</th><th scope="col">Closed</th></tr></thead>
        <tbody>${done.slice(0, 50).map((t) => { const cls = dir(t.pnl), ag = agrees(t.read, t.direction);
          return html`<tr><td>${posLabel(t)} <span class="pill ${t.direction === 'long' ? 'up' : 'down'}">${t.direction}</span></td><td>${num(t.entry_price)}</td><td>${num(t.exit_price)}</td><td class="${cls}">${money2(t.pnl)}</td><td class="${cls}">${rText(t.r)}</td><td>${t.read ? html`<span class="${ag === null ? 't-muted' : ag ? 'up' : 'down'}">${t.read.stance}</span>` : html`<span class="t-muted">n/a</span>`}</td><td>${shortDate(String(t.closed_at).slice(0, 10))}</td></tr>`; })}</tbody></table></div>
      ${done.length > 50 ? html`<p class="asof">The newest 50 of ${done.length}.</p>` : ''}
      ${armed ? html`<div class="cluster" role="group" aria-label="Confirm clearing the book"><button type="button" class="btn btn-danger" data-v2-pt-reset="do">Delete ${book.open.length} open and ${done.length} closed</button><button type="button" class="btn" data-v2-pt-reset="keep">Keep them</button><span class="t-muted">Optic Portfolio is not touched.</span></div>`
        : html`<button type="button" class="btn btn-sm" data-v2-pt-reset="arm">Clear the book</button>`}</section>`;
}

/* ---------------- page ---------------- */
// a replay open sits at the top of the desk; closed, its library sits at the foot (roadmap stage 7)
let replaying = null;
const replayHost = html`<section class="section" id="pt-replay" aria-labelledby="rp-h"></section>`;
function routeReplay(id) {
  const want = id ? `#/paper?replay=${encodeURIComponent(id)}` : '#/paper';
  if (location.hash !== want) { try { history.replaceState(history.state, '', `${location.pathname}${location.search}${want}`); } catch (e) { /* a sandboxed frame */ } }
  const moved = !!replaying !== !!id; replaying = id;
  if (moved) { paint(); const h = mainEl.querySelector('#pt-replay'); if (h && id) h.scrollIntoView({ block: 'start' }); }
}
function paint() {
  if (!live) return;
  const a = document.activeElement, keep = a && mainEl.contains(a) ? (a.name ? `[name="${a.name}"]` : a.id ? `#${a.id}` : null) : null, caret = a && 'selectionStart' in a ? a.selectionStart : null;
  // a review or plan the reader has open stays open through a redraw: answering one question closed it
  const openRevs = [...mainEl.querySelectorAll('details[data-rev-id][open]')].map((d) => d.dataset.revId), planOpen = !!mainEl.querySelector('details.pt-plan[open]');
  draw(mainEl, html`<header class="page-head">${sectionHead('portfolio', 'paper')}
      <p class="section-sub">Practice trades you enter yourself, priced by Optic. They are saved in this browser only${store.signedIn() ? ', under your account, and hidden when you sign out' : ''}. Nothing reaches a broker or Optic Portfolio.</p></header>
    ${replaying ? replayHost : ''}${healthBlock()}${fromDraft ? html`<p class="pt-note" role="status">${fromDraft}</p>` : ''}${ticketForm()}${openTable()}${recordBlock()}${journalBlock()}${replaying ? '' : replayHost}`);
  RP.mount(mainEl.querySelector('#pt-replay'), { replay: replaying, onRoute: routeReplay });
  openRevs.forEach((id) => { const d = mainEl.querySelector(`details[data-rev-id="${id}"]`); if (d) d.open = true; });
  if (planOpen) { const d = mainEl.querySelector('details.pt-plan'); if (d) d.open = true; }
  if (keep) { const el = mainEl.querySelector(keep); if (el) { el.focus({ preventScroll: true }); if (caret !== null && 'setSelectionRange' in el) { try { el.setSelectionRange(caret, caret); } catch (e) { /* number inputs */ } } } }
  const rs = book.closed.filter((t) => isNum(t.r)).slice(0, R_SHOWN).reverse();
  mountCharts(mainEl, { r: rs.length >= 2 ? (w) => signedBars(rs.map((t, i) => ({ x: `${t.ticker} ${i + 1}`, label: t.ticker, v: t.r })), { w, h: 150, label: 'Each closed trade in multiples of what it risked', fmt: rText, xfmt: (x) => String(x).split(' ')[0] }) : null });
}

async function mark() {
  if (marking || !book.open.length) return;
  marking = true; markFailed = false; paint();
  try { const out = await api.post('/api/paper/mark', { positions: book.open }, { timeout: 60000 }); marks = {}; markedAt = out.marked_at || new Date().toISOString(); (out.marks || []).forEach((m) => { marks[m.id] = m; }); }
  catch (e) { markFailed = true; note = `Could not price the book just now (${api.explain(e, 'The pricing')}).`; }
  marking = false; paint();
}
async function loadChain(s) {
  if (!s || (chainFor === s && (chainState === 'loading' || chainState === 'ready'))) return;
  chainFor = s; chainState = 'loading'; chainErr = ''; paint();
  try { const d = await api.get(`/api/chain/${encodeURIComponent(s)}?max_expiries=6`, { ttl: 120000, timeout: 45000 }); if (chainFor !== s) return; chain = { ticker: s, spot: d.spot, rows: d.rows || [] }; chainState = chain.rows.length ? 'ready' : 'empty'; }
  catch (e) { if (chainFor !== s) return; chainState = 'failed'; chainErr = api.explain(e, 'The chain'); }
  paint();
}
async function loadRead(s) {
  note = `Reading ${s}…`; paint();
  try { const d = await api.get(`/api/ticker/${encodeURIComponent(s)}?max_expiries=4&macro=true`, { ttl: 120000, timeout: 60000 }); const v = (d && d.verdict) || {}; if (v.stance) reads[s] = { stance: v.stance, conviction: v.conviction, score: v.composite_score, summary: v.summary }; note = v.stance ? '' : `Optic has no read on ${s} right now.`; }
  catch (e) { note = `Could not read ${s} (${api.explain(e, 'The read')}).`; }
  paint();
}
function openTrade() {
  const t = ticket, s = sym(), qty = Number(t.qty), isOpt = t.instrument === 'option', c = chain && chain.ticker === s ? chain : null, pk = picked();
  const entry = Number(t.entry) || (isOpt ? pk && pk.mid : c && c.spot) || 0, stop = Number(t.stop);
  if (!s) return 'Which symbol?';
  if (book.open.length >= MAX) return `This book holds ${MAX} open positions. Close one first.`;
  if (isOpt && !pk) return 'Pick an expiry and a strike from the chain.';
  if (!(qty > 0)) return isOpt ? 'How many contracts?' : 'How many shares?';
  if (!(entry > 0)) return 'What price did you get in at?';
  if (!(stop > 0)) return 'A stop is required. Everything here is reported in multiples of what a trade risked, and a trade with no stop has no denominator.';
  if ((t.direction === 'long' && stop >= entry) || (t.direction === 'short' && stop <= entry)) return `A ${t.direction} stops out ${t.direction === 'long' ? 'below' : 'above'} entry. That stop is on the wrong side and would close the trade immediately.`;
  const read = readFor(s);
  book.open.unshift({ id: pid(), ticker: s, instrument: t.instrument, direction: t.direction, option_type: isOpt ? t.optionType : null, strike: isOpt ? Number(t.strike) : null, expiry: isOpt ? t.expiry : null,
    qty, entry_price: entry, entry_spot: (c && c.spot) || entry, entry_at: new Date().toISOString(), stop, target: Number(t.target) || null, thesis: (t.thesis || '').slice(0, 600),
    plan: planOf(t, entry, qty, isOpt ? 100 : 1), entry_note: (t.entry_note || '').slice(0, 200) || null, revisions: [],
    read: read ? { stance: read.stance, conviction: read.conviction, score: read.score, summary: read.summary } : null });
  save(); ticket = blankTicket(); fromDraft = '';
  note = `Opened ${t.direction} ${qty} ${s}.`;
  return null;
}
function close(id) {
  const i = book.open.findIndex((p) => p.id === id); if (i < 0) return;
  const p = book.open[i], m = marks[id] || {}; if (!isNum(m.mark_price)) return;
  book.open.splice(i, 1);
  book.closed.unshift(Object.assign({}, p, { exit_price: m.mark_price, exit_source: m.mark_source, pnl: m.pnl, r: rOf(p, m.pnl), closed_at: new Date().toISOString() }));
  book.closed = book.closed.slice(0, KEEP_CLOSED); delete marks[id]; save();
  note = `Closed ${p.ticker} at ${num(m.mark_price)}.`; paint();
  const h = mainEl.querySelector('#po-h'); if (h) { h.setAttribute('tabindex', '-1'); h.focus(); }
}

export async function render(main, route) {
  live = true; mainEl = main; armed = false; note = ''; marks = {};
  replaying = ((route || {}).params || {}).replay || null;
  document.title = 'Paper Desk, Optic';
  loadBook();
  fromDraft = '';
  try { const d = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null'); if (d && d.ticker) { ticket = ticketFromDraft(d); fromDraft = `Filled from ${d.source || 'your research'}: check the price and the plan, then open it.`; } localStorage.removeItem(DRAFT_KEY); } catch (e) { /* no draft */ }
  provideContext(() => ({ view: 'paper', reader_holdings: book.open.slice(0, 30).map((p) => ({ ticker: p.ticker, instrument: p.instrument, direction: p.direction, qty: p.qty, entry_price: p.entry_price, stop: p.stop, pnl: (marks[p.id] || {}).pnl })), journal: J.forMilo(book.closed) }));
  if (fromDraft && ticket.instrument === 'option' && ticket.ticker) loadChain(ticket.ticker);
  api.get('/api/health', { ttl: 60000 }).then((h) => { health0 = h; paint(); }, () => {});
  main.addEventListener('input', (e) => {
    const ev = e.target.dataset.v2PtEvText;
    if (ev !== undefined) { ticket.evidence[Number(ev)].text = e.target.value; return; }
    const rf = e.target.dataset.v2PtRefl;
    if (rf) { const tr = book.closed.find((x) => x.id === rf); if (tr) { tr.reflection = e.target.value.slice(0, 400); save(); } return; }
    const f = e.target.closest('[data-v2-pt-form]'); if (!f || !e.target.name || e.target.tagName === 'SELECT') return;
    ticket[e.target.name] = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    if (e.target.name === 'ticker') return;
    const pv = mainEl.querySelector('[data-v2-pt-preview]'); if (pv) draw(pv, preview());
  });
  main.addEventListener('change', (e) => {
    const t = e.target;
    if (t.dataset.v2PtRev) {
      const i = book.open.findIndex((x) => x.id === t.dataset.v2PtRev); if (i < 0) return;
      const v = t.type === 'number' ? (t.value === '' ? null : Number(t.value)) : t.value.slice(0, 200);
      book.open[i] = J.revise(book.open[i], { [t.name]: v }); save(); paint(); return;
    }
    if (t.dataset.v2PtEvFam !== undefined) { ticket.evidence[Number(t.dataset.v2PtEvFam)].family = t.value; paint(); return; }
    if (t.dataset.v2PtAdh) { const tr = book.closed.find((x) => x.id === t.dataset.v2PtAdh); if (tr) { tr.adherence = { ...(tr.adherence || {}), [t.dataset.k]: t.value || null }; save(); paint(); } return; }
    if (t.matches('[data-v2-pt-plan]')) { ticket[t.name] = t.type === 'checkbox' ? t.checked : t.value; if (t.tagName === 'SELECT' || t.type === 'checkbox') paint(); return; }
    if (t.name === 'ticker') { ticket.ticker = t.value.toUpperCase().trim(); ticket.expiry = ''; ticket.strike = ''; if (ticket.instrument === 'option') loadChain(sym()); else paint(); return; }
    if (t.matches('[data-v2-pt-expiry]')) { ticket.expiry = t.value; ticket.strike = ''; paint(); return; }
    if (t.matches('[data-v2-pt-strike]')) { ticket.strike = t.value; paint(); }
  });
  main.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-pt-dir]'))) { ticket.direction = b.dataset.v2PtDir; paint(); return; }
    if ((b = t('[data-v2-pt-inst]'))) { ticket.instrument = b.dataset.v2PtInst; if (ticket.instrument === 'option' && sym()) loadChain(sym()); else paint(); return; }
    if ((b = t('[data-v2-pt-ot]'))) { ticket.optionType = b.dataset.v2PtOt; ticket.strike = ''; paint(); return; }
    if (t('[data-v2-pt-chain]')) { chainFor = ''; loadChain(sym()); return; }
    if ((b = t('[data-v2-pt-read]'))) { loadRead(b.dataset.v2PtRead); return; }
    if (t('[data-v2-pt-ev-add]')) { ticket.evidence.push({ text: '', family: 'volume' }); paint(); return; }
    if (t('[data-v2-pt-clear]')) { ticket = Object.assign(blankTicket(), { ticker: ticket.ticker, instrument: ticket.instrument, direction: ticket.direction }); fromDraft = ''; note = ''; paint(); return; }
    if (t('[data-v2-pt-remark]')) { note = ''; mark(); return; }
    if ((b = t('[data-v2-pt-close]'))) { close(b.dataset.v2PtClose); return; }
    if ((b = t('[data-v2-pt-reset]'))) {
      const k = b.dataset.v2PtReset;
      if (k === 'arm') { armed = true; paint(); const d = mainEl.querySelector('[data-v2-pt-reset="keep"]'); if (d) d.focus(); return; }
      if (k === 'keep') { armed = false; paint(); return; }
      book = { open: [], closed: [] }; marks = {}; armed = false; save(); note = 'Book cleared. Nothing was touched in Optic Portfolio.'; paint();
    }
  });
  main.addEventListener('submit', (e) => {
    if (!e.target.closest('[data-v2-pt-form]')) return;
    e.preventDefault();
    const f = e.target; ['qty', 'entry', 'stop', 'target', 'thesis', ...PLAN_KEYS].forEach((k) => { if (f[k]) ticket[k] = f[k].value; }); ticket.ticker = f.ticker.value.toUpperCase().trim();
    if (f.hold_through) ticket.hold_through = f.hold_through.checked;
    const err = openTrade();
    if (err) { note = err; markFailed = false; paint(); return; }
    paint(); mark();
  });
  paint(); mark();
}
export function dispose() { live = false; RP.dispose(); }
export const retry = RP.retry;
export function onAuth() { if (live) { loadBook(); marks = {}; paint(); mark(); } }
