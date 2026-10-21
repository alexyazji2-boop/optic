// The thesis check, on the Overview (Classic parity B6a, 2026-10-21; Classic app.js:6647-7215): the conditions a
// reader's idea depends on, picked from seven fixed rules, and what the page's data says about each one now and when
// it was written. Checked by fixed rules from the page's data, never by a model, and never a recommendation: "2 of
// your 3 conditions hold", not "sell".
//
// Stored as Classic stores it, so either app reads the other's (and Brokerage's thesis form edits the same record):
// - optic.thesis.v1 {SYM: {bull, bear, catalysts, invalidation, saved_at, snapshot: {stance, conviction, price, bias,
//   rsi, gamma, flow, earnings, check: {v: 1, items: [{id, level?, was, was_text}]}}}}, written on both paths as a
//   backing copy, so a failed save never loses what was typed;
// - signed in, the account's /api/theses (one record per symbol), which is authoritative once it has loaded.
// What the reader wrote elsewhere in the record (Brokerage's risks, what they watch for, what would make them
// reassess) is kept: a save here changes only the note and the conditions.
//
// The section is one node kept for the visit and put back after each of the Overview's redraws, so a half-typed
// note, the boxes ticked and the caret survive the data arriving (owner's amendment 6).
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, signed, money, shortDate, ago, clean } from '../core/format.js';
import { button as miloButton } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { icon } from '../ui/icons.js';

export const THESIS_KEY = 'optic.thesis.v1';
const AUTO = 'Would change my mind if any of these stop holding: ';

/* ---------------- what is read ---------------- */
const g = (o, ...ks) => ks.reduce((x, k) => (x && typeof x === 'object' ? x[k] : undefined), o);
const fin = (v) => typeof v === 'number' && Number.isFinite(v);

/** The readings kept beside the words when a thesis is written (Classic's THESIS_FIELDS), scalars only. */
export const SNAPSHOT_FIELDS = [
  ['stance', (d) => g(d, 'pulse', 'stance')], ['conviction', (d) => g(d, 'pulse', 'conviction')], ['price', (d) => g(d, 'quote', 'price')],
  ['bias', (d) => g(d, 'technicals', 'bias')], ['rsi', (d) => g(d, 'technicals', 'rsi', 'value')], ['gamma', (d) => g(d, 'gex', 'regime', 'state')],
  ['flow', (d) => g(d, 'flow', 'stance')], ['earnings', (d) => g(d, 'next_earnings_date')],
];
export function snapshot(d) {
  const out = {};
  SNAPSHOT_FIELDS.forEach(([k, get]) => { let v = null; try { v = get(d || {}); } catch (e) { v = null; } out[k] = v === undefined ? null : v; });
  return out;
}
/** The price-to-earnings against its own history (Classic's ovValuationRead), from /api/longterm. */
export function valuationRead(lt) {
  const vh = g(lt, 'holding', 'valuation_history');
  if (!vh || !vh.available || !(vh.usable_years >= 3)) return null;
  const cur = Number(vh.current_pe), med = Number(vh.median_pe);
  if (!Number.isFinite(cur) || !Number.isFinite(med) || cur <= 0 || med <= 0) return null;
  return { cur, med, prem: (cur / med - 1) * 100, years: vh.usable_years };
}

/** The seven conditions, Classic's wording and rules. `read` gives {ok, now} or null when the figure is missing. */
export const CHECKS = [
  { id: 'trend', label: 'The price stays above its 200-day average', read(d) {
    const ma = g(d, 'technicals', 'moving_averages', 'sma200') || {}, px = g(d, 'quote', 'price');
    if (!fin(ma.value) || !fin(px)) return null;
    return { ok: px >= ma.value, now: `${money(px)} against a 200-day average of ${money(ma.value)}` };
  } },
  { id: 'growth', label: 'Revenue keeps growing', read(d) {
    const q = g(d, 'quote', 'revenue_growth'), fy = g(d, 'company', 'financials', 'growth', 'revenue_yoy_pct');
    if (fin(q)) return { ok: q > 0, now: `${signed(q * 100, 1)} in the latest quarter against a year earlier` };
    if (fin(fy)) return { ok: fy > 0, now: `${signed(fy, 1)} in the latest fiscal year` };
    return null;
  } },
  { id: 'profit', label: 'It stays profitable', read(d) {
    const m = g(d, 'company', 'financials', 'margins', 'net_pct'), q = g(d, 'quote', 'profit_margin');
    const net = fin(m) ? m : fin(q) ? q * 100 : null;
    if (!fin(net)) return null;
    return { ok: net > 0, now: `net margin ${num(net, 1)}%` };
  } },
  { id: 'beats', label: 'It keeps meeting or beating earnings estimates', read(d) {
    const last = (g(d, 'company', 'earnings_history', 'quarters') || [])[0];
    if (!last || !fin(last.surprise_pct)) return null;
    return { ok: last.surprise_pct >= 0, now: `last report ${shortDate(last.date)}: ${signed(last.surprise_pct, 1)} against the estimate` };
  } },
  { id: 'value', label: 'The price stays within 20% of its usual price-to-earnings', read(d, level, lt) {
    const v = valuationRead(lt);
    if (!v) return null;
    return { ok: v.prem < 20, now: `${num(v.cur, 1)} times earnings, ${signed(v.prem, 0)} against its ${v.years}-year average` };
  } },
  { id: 'sector', label: 'It keeps up with its sector', read(d) {
    const sc = g(d, 'sector_confirm') || {};
    if (!sc.available || !sc.rs_vs_sector_label) return null;
    return { ok: !/lag/i.test(sc.rs_vs_sector_label), now: `${String(sc.rs_vs_sector_label).toLowerCase().replace(/\bits sector\b/, 'sector').replace(/\bsector\b/, 'its sector')} over ${num(sc.window_sessions || 21, 0)} sessions (${signed(sc.rs_vs_sector_pct, 1)} against it)` };
  } },
  { id: 'level', label: 'The price stays above a level I choose', param: true, read(d, level) {
    const px = g(d, 'quote', 'price');
    if (!fin(px) || !fin(level)) return null;
    return { ok: px >= level, now: `${money(px)} against your level of ${money(level)}` };
  } },
];
const def = (id) => CHECKS.find((c) => c.id === id) || null;
export const labelOf = (it) => { const c = def(it.id); return c ? c.label.replace('a level I choose', money(Number(it.level))) : String(it.id); };
export function readItem(d, lt, it) { const c = def(it && it.id); if (!c) return null; try { return c.read(d || {}, Number(it.level), lt); } catch (e) { return null; } }

/** A level as typed: "$1,200.50" is 1200.5; anything else is NaN. */
export const levelOf = (raw) => { const t = String(raw ?? '').replace(/[$,\s]/g, ''); return t === '' ? NaN : Number(t); };
/** The items to save, each with how it read when written. Null when nothing valid was chosen, or when the level
 *  condition is ticked without a level above zero (Classic dropped it silently and saved the rest). */
export function itemsFrom(d, lt, ids, level) {
  if ((ids || []).includes('level') && !(levelOf(level) > 0)) return null;
  const items = (ids || []).map((id) => {
    if (!def(id)) return null;
    const it = { id };
    if (id === 'level') it.level = levelOf(level);
    const r = readItem(d, lt, it);
    it.was = r ? r.ok : null; it.was_text = r ? r.now : null;
    return it;
  }).filter(Boolean);
  return items.length ? items : null;
}
/** How each saved condition reads now, against how it read when written. */
export function review(items, d, lt) {
  const rows = (items || []).map((it) => {
    const r = readItem(d, lt, it), state = !r ? 'unknown' : r.ok ? 'holds' : 'changed';
    const had = it.was === true || it.was === false;
    return { id: it.id, label: labelOf(it), state, now: r ? r.now : null, flipped: !!(r && had && r.ok !== it.was), was: it.was === true ? 'held' : it.was === false ? 'did not hold' : 'could not be checked' };
  });
  const known = rows.filter((r) => r.state !== 'unknown'), holding = rows.filter((r) => r.state === 'holds').length, flips = rows.filter((r) => r.flipped).length;
  const head = !known.length ? 'Optic could not check your conditions just now.'
    : holding === known.length ? (known.length === 1 ? 'Your condition holds.' : `All ${known.length} of your conditions hold.`) : `${holding} of your ${known.length} conditions hold.`;
  return { rows, head, flips, broken: holding < known.length };
}
/** The record to save: the note and the conditions, with the rest of what the reader wrote kept as it was. The
 *  conditions also go into `invalidation` as words (as Classic writes them) unless the reader wrote their own there. */
export function entryFor(prev, { note, items, d, now = new Date().toISOString() }) {
  const p = prev || {}, own = p.invalidation && !String(p.invalidation).startsWith(AUTO);
  const out = { bull: String(note || '').trim(), bear: p.bear || '', catalysts: p.catalysts || '',
    invalidation: own ? p.invalidation : `${AUTO}${items.map(labelOf).join('; ')}.`, saved_at: now,
    snapshot: Object.assign({}, snapshot(d), { check: { v: 1, items } }) };
  ['horizon', 'assumptions', 'created_at'].forEach((k) => { if (p[k]) out[k] = p[k]; });
  return out;
}
export const checkOf = (t) => (t && t.snapshot && t.snapshot.check && Array.isArray(t.snapshot.check.items) ? t : null);
/** Milo's question, Classic's words: drafted, never sent. */
export function stressText(sym, t) {
  const conds = t ? `${t.snapshot.check.items.map(labelOf).join('; ')}.` : '';
  return `Stress-test my thesis on ${sym}. My conditions: ${conds}${t && t.bull ? ` In my words: "${t.bull}"` : ''} Using the data on this page, what is the strongest evidence against it, which condition is closest to breaking, and what should I watch next? Treat these as my reasons, not as a recommendation.`;
}

/* ---------------- where it is kept ---------------- */
export function localAll() {
  try { const v = JSON.parse(localStorage.getItem(THESIS_KEY) || '{}'); return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; } catch (e) { return {}; }
}
function localWrite(fn) {
  if (!holds(store.state.user)) return false;
  try { const all = localAll(); fn(all); localStorage.setItem(THESIS_KEY, JSON.stringify(all)); return true; } catch (e) { return false; }
}

/* ---------------- the section ---------------- */
const TC = { sym: null, node: null, getD: null, editing: false, draft: null, account: null, accountErr: null, failed: new Set(), sig: '', undo: null, focus: null, sel: null };
const saved = () => { const all = store.signedIn() && TC.account ? TC.account : localAll(); return all[TC.sym] || null; };
function where(t) {
  if (!store.signedIn()) return 'Kept in this browser. Sign in and it follows you between them.';
  if (TC.failed.has(TC.sym)) return 'Saved in this browser. It could not reach your account, so it will sync next time you sign in.';
  if (!TC.account) return TC.accountErr ? 'Your account\'s copy did not load, so this is the copy in this browser.' : 'Loading from your account…';
  return t ? 'Saved to your account. It follows you between browsers.' : 'Saved to your account when you save it.';
}
const data = () => { const D = TC.getD ? TC.getD() : {}; return { d: D.ticker || null, lt: D.longterm || null, D }; };

function viewHTML(t) {
  const { d, lt } = data(), rv = review(t.snapshot.check.items, d, lt);
  const next = (g(d, 'company', 'earnings_history', 'upcoming') || [])[0];
  return html`<p class="tc-head${rv.broken ? ' is-changed' : ''}" role="status"><b>${d ? rv.head : 'Checking your conditions…'}</b>${d && rv.flips ? ` ${rv.flips === 1 ? 'One has' : `${rv.flips} have`} changed since you wrote it.` : ''}</p>
    <p class="asof">Written ${ago(t.saved_at)}. Checked against this page's data each time you open it.</p>
    <ul class="tc-list">${rv.rows.map((r) => html`<li class="tc-item is-${d ? r.state : 'unknown'}">
      <span class="tc-mark" aria-hidden="true">${!d || r.state === 'unknown' ? icon('help') : r.state === 'holds' ? icon('check') : icon('close')}</span>
      <span class="tc-body"><span class="tc-label">${r.label}</span>
        <span class="tc-now">${!d ? 'Waiting for this page\'s data.' : r.now ? `${r.state === 'holds' ? (r.flipped ? 'Holds now' : 'Still holds') : (r.flipped ? 'No longer holds' : 'Does not hold')}: ${r.now}.` : 'Optic could not check this just now: the figure it needs did not load.'}
        ${d && r.flipped ? html` <b class="tc-flip">Changed since you wrote this (it ${r.was} then).</b>` : ''}</span></span></li>`)}</ul>
    ${t.bull ? html`<blockquote class="tc-note">${t.bull}</blockquote>` : ''}
    ${next && next.date ? html`<p class="asof">Next real test: the earnings report on ${shortDate(next.date)}. Revenue, profit and the estimate conditions update when it is out.</p>` : ''}
    <div class="cluster tc-acts"><button type="button" class="btn btn-sm" data-tc-edit>Edit</button>
      ${miloButton('Ask Milo to stress-test it', { ask: stressText(TC.sym, t), context: `${TC.sym} thesis check`, symbol: TC.sym, cls: 'btn-sm' })}
      <button type="button" class="btn btn-sm btn-quiet" data-tc-delete>Delete</button></div>
    <p class="asof">These are your conditions and what the data says about them. Whether a change breaks your case is your call. ${where(t)}</p>`;
}
function optNow(c, d, lt) {
  if (c.param) return '';
  const r = d ? readItem(d, lt, { id: c.id }) : null;
  return !d ? 'Waiting for this page\'s data' : r ? `${r.ok ? 'Holds today' : 'Does not hold today'}: ${r.now}` : 'Not available for this symbol';
}
function formHTML(t) {
  const { d, lt } = data(), dr = TC.draft, px = g(d, 'quote', 'price');
  return html`<form class="tc-form stack" data-tc-form novalidate>
    <fieldset class="tc-opts"><legend class="t-label">Your conditions</legend>
    ${CHECKS.map((c) => { const r = c.param || !d ? true : readItem(d, lt, { id: c.id }); return html`<label class="tc-opt">
      <input type="checkbox" name="tc" value="${c.id}" ${dr.ids.includes(c.id) ? 'checked' : ''} ${!r ? 'disabled' : ''}>
      <span class="tc-opt-body"><span class="tc-label">${c.label}</span>
        ${c.param ? html`<span class="tc-level"><span aria-hidden="true">$</span><input type="text" inputmode="decimal" name="tc-level" value="${dr.level}" placeholder="${fin(px) ? num(px * 0.9, 2) : ''}" aria-label="Your level in dollars" autocomplete="off"></span>`
          : html`<span class="tc-now" data-tc-now="${c.id}">${optNow(c, d, lt)}</span>`}</span></label>`; })}</fieldset>
    <label class="tc-note-wrap"><span class="t-label">In your own words (optional)</span>
      <textarea name="tc-note" rows="2" maxlength="2000" placeholder="For example: services keep growing faster than hardware.">${dr.note}</textarea></label>
    <p class="form-error" role="alert">${dr.error || ''}</p>
    <div class="cluster"><button type="submit" class="btn btn-primary">${t ? 'Save changes' : 'Save my thesis check'}</button><button type="button" class="btn" data-tc-cancel>Cancel</button></div>
    <p class="asof">Checked by fixed rules from the data on this page, not by an AI model, and not a recommendation. ${where(t)}</p></form>`;
}
function bodyHTML() {
  const t = checkOf(saved());
  if (TC.editing) return formHTML(t);
  if (t) return viewHTML(t);
  return html`<p class="section-sub">Why are you interested in ${TC.sym}, and what would change your mind? Pick the conditions that matter to you and Optic checks them each time you come back.</p>
    ${TC.undo ? html`<p class="wl-undo" role="status">${TC.undo.text} <button type="button" class="btn btn-sm" data-tc-undo>Undo</button></p>` : ''}
    <div class="cluster"><button type="button" class="btn" data-tc-start>Start a thesis check</button></div>`;
}
function paintTC(focusSel) {
  const n = TC.node; if (!n) return;
  draw(n.querySelector('.tc-body-box'), bodyHTML());
  if (focusSel) { const f = n.querySelector(focusSel); if (f) f.focus({ preventScroll: true }); }
}
/** Data arrived: the reading lines change; a form being filled in is touched only where its readings are. */
function update() {
  const { d, lt } = data(), sig = `${!!d}|${!!(lt && lt.holding)}|${TC.account ? 1 : 0}|${TC.accountErr ? 1 : 0}`;
  if (sig === TC.sig) return; TC.sig = sig;
  if (!TC.editing) { paintTC(); return; }
  CHECKS.forEach((c) => {
    if (c.param) return;
    const s = TC.node.querySelector(`[data-tc-now="${c.id}"]`); if (s) s.textContent = optNow(c, d, lt);
    const box = TC.node.querySelector(`input[name="tc"][value="${c.id}"]`); if (box && d) { const ok = !!readItem(d, lt, { id: c.id }); box.disabled = !ok; if (!ok) box.checked = false; }
  });
}

function startEdit(t) {
  // the note is the record's own words (Brokerage's "Why I own it" is the same field), even before it has a check:
  // starting empty and saving wiped them (Classic does that)
  const items = t ? t.snapshot.check.items : [], lvl = (items.find((x) => x.id === 'level') || {}).level, rec = saved();
  TC.draft = { ids: items.map((x) => x.id), level: Number.isFinite(Number(lvl)) && lvl !== undefined ? String(lvl) : '', note: (rec && rec.bull) || '', error: '' };
  TC.editing = true; TC.undo = null;
  paintTC('input[name="tc"]:not([disabled])');
}
async function save(form) {
  const { d, lt } = data();
  const dr = TC.draft, items = d ? itemsFrom(d, lt, dr.ids, dr.level) : null;
  if (!d) { dr.error = 'This page\'s data has not loaded yet, so the conditions cannot be read. Try again in a moment.'; paintErr(form); return; }
  if (!items) { dr.error = dr.ids.includes('level') && !(levelOf(dr.level) > 0) ? 'Enter your level in dollars, above zero, or untick that condition.' : 'Pick at least one condition.'; paintErr(form); return; }
  const sym = TC.sym, prev = saved(), entry = entryFor(prev, { note: dr.note, items, d });
  localWrite((all) => { all[sym] = entry; });
  TC.editing = false; TC.failed.delete(sym);
  if (store.signedIn() && TC.account) TC.account[sym] = entry;
  paintTC('[data-tc-edit]');
  toast(prev ? 'Thesis check saved.' : 'Thesis check saved. Optic checks it each time you open this page.');
  if (!store.signedIn()) return;
  try {
    const body = { bull: entry.bull, bear: entry.bear, catalysts: entry.catalysts, invalidation: entry.invalidation, snapshot: entry.snapshot };
    const r = await api.put(`/api/theses/${encodeURIComponent(sym)}`, body);
    if (TC.account && r && r.thesis) TC.account[sym] = r.thesis;
  } catch (e) { TC.failed.add(sym); }
  if (TC.sym === sym && !TC.editing) paintTC();
}
function paintErr(form) { const e = form.querySelector('.form-error'); if (e) e.textContent = TC.draft.error; const f = form.querySelector('input[name="tc"]:not([disabled])'); if (f) f.focus(); }
async function remove() {
  const sym = TC.sym, prev = saved(); if (!prev) return;
  localWrite((all) => { delete all[sym]; });
  if (store.signedIn()) {
    try { await api.del(`/api/theses/${encodeURIComponent(sym)}`); } catch (e) { if (e.status !== 404) { toast(api.explain(e, 'The delete'), { kind: 'bad' }); localWrite((all) => { all[sym] = prev; }); return; } }
    if (TC.account) delete TC.account[sym];
  }
  TC.editing = false;
  TC.undo = { text: 'Thesis check deleted.', entry: prev };
  paintTC('[data-tc-undo]');
  toast('Thesis check deleted.', { action: 'Undo', run: () => restore() });
}
async function restore() {
  const u = TC.undo; if (!u) return;
  const sym = TC.sym, e = u.entry; TC.undo = null;
  localWrite((all) => { all[sym] = e; });
  if (store.signedIn()) {
    try { const r = await api.put(`/api/theses/${encodeURIComponent(sym)}`, { bull: e.bull || '', bear: e.bear || '', catalysts: e.catalysts || '', invalidation: e.invalidation || '', snapshot: e.snapshot || {} }); if (TC.account) TC.account[sym] = (r && r.thesis) || e; }
    catch (err) { TC.failed.add(sym); if (TC.account) TC.account[sym] = e; }
  }
  paintTC('[data-tc-edit]');
  toast('Thesis check restored.');
}

function wire(n) {
  n.addEventListener('click', (e) => {
    const t = (q) => e.target.closest(q);
    if (t('[data-tc-start]')) { startEdit(null); return; }
    if (t('[data-tc-edit]')) { startEdit(checkOf(saved())); return; }
    if (t('[data-tc-cancel]')) { const had = !!checkOf(saved()); TC.editing = false; TC.draft = null; paintTC(had ? '[data-tc-edit]' : '[data-tc-start]'); return; }
    if (t('[data-tc-delete]')) { remove(); return; }
    if (t('[data-tc-undo]')) restore();
  });
  // Chrome sends no blur when a redraw takes a focused field out of the page, so where focus was, and the caret,
  // are kept here and put back when the section returns
  const caret = (e) => { const x = e.target; if (x && 'selectionStart' in x && TC.focus === x) try { TC.sel = [x.selectionStart, x.selectionEnd]; } catch (err) { TC.sel = null; } };
  n.addEventListener('focusin', (e) => { TC.focus = e.target; TC.sel = null; caret(e); });
  n.addEventListener('focusout', () => setTimeout(() => { if (n.isConnected && !n.contains(document.activeElement)) { TC.focus = null; TC.sel = null; } }, 0));
  ['keyup', 'mouseup', 'select'].forEach((k) => n.addEventListener(k, caret));
  // the draft follows every keystroke, so a redraw puts back exactly what was there
  n.addEventListener('input', (e) => {
    caret(e);
    const f = e.target.closest('[data-tc-form]'); if (!f || !TC.draft) return;
    if (e.target.name === 'tc-note') TC.draft.note = e.target.value;
    if (e.target.name === 'tc-level') { TC.draft.level = e.target.value; const box = f.querySelector('input[name="tc"][value="level"]'); if (box && e.target.value.trim() && !box.checked) { box.checked = true; TC.draft.ids = [...new Set([...TC.draft.ids, 'level'])]; } }
  });
  n.addEventListener('change', (e) => {
    if (e.target.name !== 'tc' || !TC.draft) return;
    TC.draft.ids = [...n.querySelectorAll('input[name="tc"]:checked')].map((x) => x.value);
    TC.draft.error = '';
  });
  n.addEventListener('submit', (e) => { const f = e.target.closest('[data-tc-form]'); if (!f) return; e.preventDefault(); save(f); });
}

/** Called after each of the Overview's paints: put the section (one node for the visit) where the page left its
 *  slot, keeping focus and the caret if they were in it. */
export function mountThesis(main, sym, getD) {
  const slot = main.querySelector('[data-tc-slot]');
  if (TC.sym !== sym || !TC.node) {
    Object.assign(TC, { sym, getD, editing: false, draft: null, account: null, accountErr: null, sig: '', undo: null, focus: null, sel: null });
    const n = document.createElement('section');
    n.className = 'section tc'; n.id = 'ov-thesis'; n.setAttribute('aria-labelledby', 'tc-h');
    n.innerHTML = '<div class="section-head"><h2 class="t-h2" id="tc-h">Your thesis check</h2></div><div class="tc-body-box"></div>';
    TC.node = n; wire(n); paintTC();
    if (store.signedIn()) {
      api.get('/api/theses', { ttl: 0, force: true }).then((r) => { if (TC.sym === sym) { TC.account = (r && r.theses) || {}; update(); } },
        (e) => { if (TC.sym === sym) { TC.accountErr = e; update(); } });
    }
  }
  TC.getD = getD;
  if (!slot) { if (TC.node.isConnected) TC.node.remove(); return; }
  if (slot !== TC.node) {
    slot.replaceWith(TC.node);
    const a = document.activeElement, f = TC.focus;
    if (f && TC.node.contains(f) && (!a || a === document.body)) {
      f.focus({ preventScroll: true });
      if (TC.sel) try { f.setSelectionRange(TC.sel[0], TC.sel[1]); } catch (e) { /* not a text field */ }
    }
  }
  update();
}
/** Leaving the page: the next visit starts from what is saved. */
export function disposeThesis() { TC.sym = null; TC.node = null; TC.draft = null; TC.editing = false; }
export const thesisContext = () => { const t = checkOf(saved()); return t ? { conditions: t.snapshot.check.items.map(labelOf), note: t.bull || '', saved_at: t.saved_at } : null; };
void clean;
