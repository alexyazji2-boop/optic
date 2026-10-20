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
import { num, compact, clean, shortDate, isNum, dir } from '../core/format.js';
import { signedBars } from '../ui/bars.js';
import { mountCharts } from '../ui/chart.js';
import { provideContext } from '../ui/milo.js';
import { sectionHead } from './tabs.js';

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
let marks = {}, marking = false, markFailed = false, armed = false, note = '', reads = {}, live = true, mainEl = null, health0 = null;
function blankTicket() { return { ticker: '', instrument: 'shares', direction: 'long', qty: '', entry: '', stop: '', target: '', thesis: '', expiry: '', strike: '', optionType: 'call' }; }
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
      <span class="pill">${h.marked < book.open.length ? `${book.open.length - h.marked} of ${book.open.length} not marked` : `${realtime ? 'Marked from live quotes' : 'Marked from delayed quotes'}${modelledN ? `; ${modelledN} option${modelledN === 1 ? '' : 's'} estimated by a model` : ''}`}</span></div>
    <p class="lead-line">${names === 1 ? `One name, ${h.top[0]}, is the whole book.` : conc ? `${h.top[0]} is ${Math.round(h.topShare * 100)}% of the book, which is concentrated.` : `Spread across ${names} names; the largest, ${h.top[0]}, is ${Math.round(h.topShare * 100)}%.`} It is ${lean}. ${h.review.length ? `${h.review.length} position${h.review.length === 1 ? ' needs' : 's need'} a look.` : 'Nothing is near its stop or its expiry.'}</p>
    <dl class="kv" style="--kv:3"><div><dt>Exposure</dt><dd>$${compact(h.total)}</dd><p class="kv-note">at cost, ${book.open.length} position${book.open.length === 1 ? '' : 's'}</p></div>
      <div><dt>Open P&L</dt><dd class="${h.marked ? (h.pnl >= 0 ? 'up' : 'down') : ''}">${h.marked ? money2(h.pnl) : 'n/a'}</dd><p class="kv-note">${!h.marked ? 'waiting on marks' : modelledN ? `a quote, not a result; ${modelledN} of it a model's estimate` : 'a quote, not a result'}</p></div>
      <div><dt>Largest name</dt><dd>${Math.round(h.topShare * 100)}%</dd><p class="kv-note">${h.top[0]}${names > 3 ? `, top three ${Math.round(h.top3 * 100)}%` : ''}</p></div></dl>
    <div class="ph-bar" role="img" aria-label="Exposure at cost: ${parts.map((x) => `${x.name} ${Math.round(x.share * 100)}%`).join(', ')}">${parts.map((x) => html`<span class="ph-seg ${x.cls}" style="flex-grow:${x.share.toFixed(4)}"></span>`)}</div>
    <ul class="ph-legend" aria-hidden="true">${parts.map((x) => html`<li><i class="${x.cls}"></i>${x.name} ${Math.round(x.share * 100)}%</li>`)}</ul>
    ${h.review.length ? html`<h3>Needs review</h3><ul class="plain">${h.review.map((x) => html`<li><b>${posLabel(x.p)}</b> <span class="t-muted">${x.why}</span></li>`)}</ul>` : ''}
    <p class="asof">Computed from this book alone. It does not see sectors, upcoming earnings or how these names move together, and it does not know about anything you hold elsewhere.</p></section>`;
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
      <div class="pt-grid"><label class="field"><span class="t-label">Symbol</span><input id="pt-ticker" name="ticker" value="${t.ticker}" placeholder="NVDA" maxlength="12" spellcheck="false" autocomplete="off" autocapitalize="characters"></label>
        <div><span class="t-label" id="pt-dir">Direction</span><div class="seg" role="group" aria-labelledby="pt-dir"><button type="button" data-v2-pt-dir="long" aria-pressed="${t.direction === 'long'}">Long</button><button type="button" data-v2-pt-dir="short" aria-pressed="${t.direction === 'short'}">Short</button></div></div>
        <div><span class="t-label" id="pt-inst">Instrument</span><div class="seg" role="group" aria-labelledby="pt-inst"><button type="button" data-v2-pt-inst="shares" aria-pressed="${!isOpt}">Shares</button><button type="button" data-v2-pt-inst="option" aria-pressed="${isOpt}">Option</button></div></div></div>
      ${isOpt ? html`<div class="pt-grid"><div><span class="t-label" id="pt-ot">Call or put</span><div class="seg" role="group" aria-labelledby="pt-ot"><button type="button" data-v2-pt-ot="call" aria-pressed="${t.optionType === 'call'}">Call</button><button type="button" data-v2-pt-ot="put" aria-pressed="${t.optionType === 'put'}">Put</button></div></div>
          <label class="select"><span class="t-label">Expiry</span><select name="expiry" data-v2-pt-expiry ${expiries.length ? '' : 'disabled'}>${expiries.length ? '' : html`<option value="">${prompt}</option>`}${expiries.length && !t.expiry ? html`<option value="">Pick an expiry</option>` : ''}${expiries.map((e) => html`<option value="${e}" ${t.expiry === e ? 'selected' : ''}>${e}</option>`)}</select></label>
          <label class="select"><span class="t-label">Strike</span><select name="strike" data-v2-pt-strike ${strikes.length ? '' : 'disabled'}>${strikes.length ? (t.strike ? '' : html`<option value="">Pick a strike</option>`) : html`<option value="">${expiries.length ? 'Pick an expiry' : 'n/a'}</option>`}${strikes.map((k) => html`<option value="${k}" ${String(t.strike) === String(k) ? 'selected' : ''}>${num(k)}</option>`)}</select></label></div>
        ${chainState === 'failed' ? html`<p class="stale">Could not read the options chain for ${s}${chainErr ? ` (${chainErr})` : ''}. <button type="button" class="textlink" data-v2-pt-chain>Try again</button></p>` : ''}
        ${pk ? html`<p class="pt-quote">${pk.contract}, mid <b>$${num(pk.mid)}</b> (bid ${num(pk.bid)} / ask ${num(pk.ask)}), ${num(pk.dte, 0)} days, delta ${num(pk.delta)}${isNum(pk.spread_pct) ? `, spread ${num(pk.spread_pct, 1)}%` : ''}${pk.spread_pct > 10 ? html`<span class="down">, which is wide, so a real fill would be worse.</span>` : ''}</p>` : ''}` : ''}
      <div class="pt-grid pt-nums"><label class="field"><span class="t-label">${isOpt ? 'Contracts' : 'Shares'}</span><input name="qty" type="number" min="0" step="any" inputmode="decimal" value="${t.qty}" placeholder="100"></label>
        <label class="field"><span class="t-label">Entry ${isOpt ? 'premium' : 'price'}</span><input name="entry" type="number" min="0" step="any" inputmode="decimal" value="${t.entry}" placeholder="${pk ? num(pk.mid) : 'market'}"></label>
        <label class="field"><span class="t-label">Stop</span><input name="stop" type="number" min="0" step="any" inputmode="decimal" value="${t.stop}" placeholder="required"></label>
        <label class="field"><span class="t-label">Target</span><input name="target" type="number" min="0" step="any" inputmode="decimal" value="${t.target}" placeholder="optional"></label></div>
      <label class="field"><span class="t-label">Why, and what would prove you wrong</span><input name="thesis" maxlength="200" value="${t.thesis}" placeholder="Held the 200-day and volume came in"></label>
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

function openTable() {
  const o = book.open;
  return html`<section class="section" aria-labelledby="po-h"><h2 class="t-h2" id="po-h">Open, ${o.length}</h2>
    ${o.length ? html`<div class="tscroll"><table class="t"><thead><tr><th scope="col">Position</th><th scope="col">Entry</th><th scope="col">Mark</th><th scope="col">Marked from</th><th scope="col">P&L</th><th scope="col">R</th><th scope="col">Optic then</th><th scope="col"><span class="sr">Close</span></th></tr></thead>
      <tbody>${o.map((p) => { const m = marks[p.id] || {}, pnl = m.pnl, r = rOf(p, pnl), cls = !isNum(pnl) ? '' : pnl >= 0 ? 'up' : 'down', ag = agrees(p.read, p.direction);
        return html`<tr><td>${posLabel(p)} <span class="pill ${p.direction === 'long' ? 'up' : 'down'}">${p.direction}</span></td><td>${num(p.entry_price)}</td><td>${isNum(m.mark_price) ? num(m.mark_price) : 'n/a'}</td>
          <td class="pt-src">${m.mark_source ? m.mark_source : html`<span class="t-muted">${m.reason || (marking ? 'pricing…' : 'not marked')}</span>`}</td><td class="${cls}">${isNum(pnl) ? money2(pnl) : 'n/a'}</td><td class="${cls}">${rText(r)}</td>
          <td>${p.read ? html`<span class="${ag === null ? 't-muted' : ag ? 'up' : 'down'}" title="${p.read.summary || ''}">${p.read.stance}${ag === null ? '' : ag ? ', with' : ', against'}</span>` : html`<span class="t-muted">n/a</span>`}</td>
          <td><button type="button" class="btn btn-sm" data-v2-pt-close="${p.id}" ${isNum(m.mark_price) ? '' : 'disabled'} title="Close at the current mark" aria-label="Close ${posLabel(p)} at the current mark">Close</button></td></tr>`; })}</tbody></table></div>
      <p class="asof">Closing takes the current mark: the last trade for shares, the chain's mid for an option, or a model's estimate when the contract has no quote. A real fill would be at the bid or the ask.</p>`
      : html`<p class="quiet">No open positions. The ticket above opens one.</p>`}</section>`;
}

function recordBlock() {
  const done = book.closed;
  if (!done.length) return html`<section class="section"><h2 class="t-h2">Record</h2><p class="quiet">Nothing closed yet. Every number here is realised: an open position's profit is a quote, not a result.</p></section>`;
  const wins = done.filter((t) => t.pnl > 0), total = done.reduce((a, t) => a + t.pnl, 0), withR = done.filter((t) => isNum(t.r)), avgR = withR.length ? withR.reduce((a, t) => a + t.r, 0) / withR.length : null;
  const sided = (want) => { const rows = done.filter((t) => agrees(t.read, t.direction) === want && isNum(t.r)); return rows.length ? { n: rows.length, avg: rows.reduce((a, t) => a + t.r, 0) / rows.length } : null; };
  const w = sided(true), a = sided(false);
  return html`<section class="section" aria-labelledby="pr-h"><h2 class="t-h2" id="pr-h">Record</h2>
    <p class="section-sub">${done.length} closed, ${wins.length} up, ${Math.round((wins.length / done.length) * 100)}% win rate</p>
    <dl class="kv" style="--kv:2"><div><dt>Realised</dt><dd class="${dir(total)}">${money2(total)}</dd></div><div><dt>Average</dt><dd class="${dir(avgR)}">${rText(avgR)}</dd><p class="kv-note">per trade, in multiples of what it risked</p></div></dl>
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
function paint() {
  if (!live) return;
  const a = document.activeElement, keep = a && mainEl.contains(a) ? (a.name ? `[name="${a.name}"]` : a.id ? `#${a.id}` : null) : null, caret = a && 'selectionStart' in a ? a.selectionStart : null;
  draw(mainEl, html`<header class="page-head">${sectionHead('portfolio', 'paper')}
      <p class="section-sub">Your own book, entered by hand and priced by the terminal. It lives in this browser${store.signedIn() ? ', kept apart for your account and put away when you sign out' : ''}: no server copy, and no connection to Optic Portfolio.</p></header>
    ${healthBlock()}${ticketForm()}${openTable()}${recordBlock()}`);
  if (keep) { const el = mainEl.querySelector(keep); if (el) { el.focus({ preventScroll: true }); if (caret !== null && 'setSelectionRange' in el) { try { el.setSelectionRange(caret, caret); } catch (e) { /* number inputs */ } } } }
  const rs = book.closed.filter((t) => isNum(t.r)).slice(0, R_SHOWN).reverse();
  mountCharts(mainEl, { r: rs.length >= 2 ? (w) => signedBars(rs.map((t, i) => ({ x: `${t.ticker} ${i + 1}`, label: t.ticker, v: t.r })), { w, h: 150, label: 'Each closed trade in multiples of what it risked', fmt: rText, xfmt: (x) => String(x).split(' ')[0] }) : null });
}

async function mark() {
  if (marking || !book.open.length) return;
  marking = true; markFailed = false; paint();
  try { const out = await api.post('/api/paper/mark', { positions: book.open }, { timeout: 60000 }); marks = {}; (out.marks || []).forEach((m) => { marks[m.id] = m; }); }
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
    qty, entry_price: entry, entry_spot: (c && c.spot) || entry, entry_at: new Date().toISOString(), stop, target: Number(t.target) || null, thesis: (t.thesis || '').slice(0, 200),
    read: read ? { stance: read.stance, conviction: read.conviction, score: read.score, summary: read.summary } : null });
  save(); ticket = Object.assign({}, ticket, { qty: '', entry: '', stop: '', target: '', thesis: '' });
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

export async function render(main) {
  live = true; mainEl = main; armed = false; note = ''; marks = {};
  document.title = 'Paper Desk, Optic';
  loadBook();
  provideContext(() => ({ view: 'paper', reader_holdings: book.open.slice(0, 30).map((p) => ({ ticker: p.ticker, instrument: p.instrument, direction: p.direction, qty: p.qty, entry_price: p.entry_price, stop: p.stop, pnl: (marks[p.id] || {}).pnl })) }));
  api.get('/api/health', { ttl: 60000 }).then((h) => { health0 = h; paint(); }, () => {});
  main.addEventListener('input', (e) => {
    const f = e.target.closest('[data-v2-pt-form]'); if (!f || !e.target.name || e.target.tagName === 'SELECT') return;
    ticket[e.target.name] = e.target.value;
    if (e.target.name === 'ticker') return;
    const pv = mainEl.querySelector('[data-v2-pt-preview]'); if (pv) draw(pv, preview());
  });
  main.addEventListener('change', (e) => {
    const t = e.target;
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
    if (t('[data-v2-pt-clear]')) { ticket = Object.assign({}, ticket, { qty: '', entry: '', stop: '', target: '', thesis: '' }); note = ''; paint(); return; }
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
    const f = e.target; ['qty', 'entry', 'stop', 'target', 'thesis'].forEach((k) => { ticket[k] = f[k].value; }); ticket.ticker = f.ticker.value.toUpperCase().trim();
    const err = openTrade();
    if (err) { note = err; markFailed = false; paint(); return; }
    paint(); mark();
  });
  paint(); mark();
}
export function dispose() { live = false; }
export function onAuth() { if (live) { loadBook(); marks = {}; paint(); mark(); } }
