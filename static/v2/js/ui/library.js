// The Save control (Handoff 5 of the owner's handover pack): one press keeps what is on screen in Saved research, under
// the ticker(s) and the date, and the name can be changed after. A page says what it would save with provide(); the
// press reads it then, so a summary is the page's figures at that moment. A second save of the same thing asks
// whether to update the saved one or keep a copy under another name; nothing is duplicated silently. A failed save
// says so beside the button, with Retry, and the button is never shown as saved. Pressing a Saved button shows the
// saved item: its name, Rename, Update and Delete.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import * as lib from '../core/library.js';
import * as drawer from './drawer.js';
import { toast } from './toast.js';
import { icon } from './icons.js';
import { go } from '../core/router.js';

const SPECS = new Map(), RETRY = new WeakMap();
/** What a page would save under `id` (read at the press): {kind, tickers, ref, summary, conversation}. */
export function provide(id, fn) { SPECS.set(id, fn); }

/** A Save button for `id`. `key` is what it would be saved as (core/library.js keyOf), for the Saved state.
 *  `iconOnly` is Milo's header, whose buttons are icons with their names spoken. */
export function saveButton(id, key, { cls = 'btn-sm', label = 'Save', iconOnly = false } = {}) {
  const k = key || '', it = k ? lib.known(k) : undefined, on = !!it;
  if (k && it === undefined && store.signedIn()) setTimeout(() => refresh(k), 0);
  const title = on ? `Saved as “${it.name}”` : `${label} to Saved research`;
  const btn = iconOnly
    ? html`<button type="button" class="icon-btn lib-save-btn" data-v2-save="${id}" data-v2-save-key="${k}" data-v2-save-label="${label}" aria-pressed="${on}" aria-label="${title}" title="${title}">${icon('bookmark')}</button>`
    : html`<button type="button" class="btn ${cls} lib-save-btn" data-v2-save="${id}" data-v2-save-key="${k}" data-v2-save-label="${label}" aria-pressed="${on}" title="${title}">${icon('bookmark')}<span class="lib-save-t">${on ? 'Saved' : label}</span></button>`;
  return html`<span class="lib-save">${btn}<span class="lib-err" role="alert" hidden></span></span>`;
}

/* ---------------- the buttons' state ---------------- */
function paintKey(key, item) {
  if (typeof document === 'undefined' || !key) return;
  document.querySelectorAll(`[data-v2-save-key="${CSS.escape(key)}"]`).forEach((b) => {
    const on = !!item, label = b.dataset.v2SaveLabel || 'Save', title = on ? `Saved as “${item.name}”` : `${label} to Saved research`;
    b.setAttribute('aria-pressed', String(on)); b.title = title;
    if (b.classList.contains('icon-btn')) b.setAttribute('aria-label', title);
    const t = b.querySelector('.lib-save-t'); if (t) t.textContent = on ? 'Saved' : label;
  });
}
/** Ask whether `key` is saved, and draw every button for it to match. */
export function refresh(key) { lib.savedAs(key).then((it) => paintKey(key, it), () => { /* the button stays "Save"; a press says if saving fails */ }); }

function setBusy(b, on) { if (!b) return; b.disabled = !!on; b.setAttribute('aria-busy', String(!!on)); }
// Why a save failed, short enough to sit beside the button: the server's own sentence when it sent one (the plan's
// limit, a size), else what kind of failure it was
function why(e) {
  const said = e && e.message && e.message !== 'Request failed' && !/^Could not reach Optic|^The server took too long/.test(e.message) ? e.message : '';
  if (e && e.kind === 'offline') return 'you appear to be offline';
  if (e && e.kind === 'timeout') return 'the server took too long to answer';
  if (e && e.kind === 'auth') return 'your session has ended; sign in again';
  if (e && e.kind === 'limit') return 'too many requests just now; wait a moment';
  return said || 'the server answered with an error';
}
function setErr(b, e, retry) {
  const box = b && b.closest('.lib-save') && b.closest('.lib-save').querySelector('.lib-err'); if (!box) return;
  if (!e) { box.hidden = true; draw(box, ''); RETRY.delete(b); return; }
  RETRY.set(b, retry);
  draw(box, html`Not saved: ${why(e).replace(/\.$/, '')}. <button type="button" class="textlink" data-v2-save-retry>Retry</button>`);
  box.hidden = false;
}

/* ---------------- a press ---------------- */
async function press(b) {
  if (!store.signedIn()) { toast('Saved research is kept with an account.', { action: 'Sign in', run: () => go('#/signin') }); return; }
  const fn = SPECS.get(b.dataset.v2Save), spec = fn ? fn() : null;
  if (!spec) { toast('There is nothing to save here yet.'); return; }
  if (spec.blocked) { toast(spec.blocked); return; }   // the page's own reason it cannot be saved yet (Milo mid-answer)
  const key = b.dataset.v2SaveKey || lib.keyOf(spec.kind, spec.tickers, spec.ref);
  const have = key ? lib.known(key) : null;
  if (have) { manage(have, spec, b); return; }
  await attempt(b, spec, {});
}
async function attempt(b, spec, opts) {
  const body = Object.assign({}, spec, { name: spec.name || lib.defaultName(spec.kind, spec.tickers || []) });
  setBusy(b, true); setErr(b, null);
  try {
    const r = await lib.save(body, opts);
    drawer.close({ silent: true });
    toast(r.updated ? `Updated “${r.item.name}” in Saved research.` : `Saved to Saved research as “${r.item.name}”.`, { action: 'Rename', run: () => renameSheet(r.item, b) });
  } catch (e) {
    const dup = lib.duplicateOf(e);
    if (dup) duplicateSheet(dup, body, b);
    else setErr(b, e, () => attempt(b, spec, opts));
  } finally { setBusy(b, false); }
}

/* ---------------- the sheets: rename, already saved, saved ---------------- */
const nameField = (id, value) => html`<div class="lib-field"><label class="t-label" for="${id}">Name</label><span class="field"><input id="${id}" type="text" maxlength="120" required value="${value}" autocomplete="off"></span></div>`;
const savedWhen = (it) => `saved ${lib.dayText(it.created_at)}${it.updated_at && lib.dayText(it.updated_at) !== lib.dayText(it.created_at) ? `, updated ${lib.dayText(it.updated_at)}` : ''}`;
const what = (it) => (it.kind === 'conversation' ? 'This conversation' : it.kind === 'comparison' ? `This comparison of ${(it.tickers || []).join(', ')}` : `${(it.tickers || [])[0] || 'This'}${it.kind === 'sheet' ? "'s research sheet" : ''}`);

export function renameSheet(item, opener) {
  drawer.open({ kicker: 'Saved research', title: 'Rename', opener, form: true,
    body: html`<form class="lib-form" data-lib-rename>${nameField('lib-name', item.name)}<p class="lib-form-err" role="alert" hidden></p>
      <div class="cluster"><button type="submit" class="btn btn-primary">Rename</button><button type="button" class="btn" data-v2-close>Cancel</button></div></form>`,
    mount: (body) => {
      const f = body.querySelector('[data-lib-rename]'), input = f.querySelector('input'); input.select();
      f.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = input.value.replace(/\s+/g, ' ').trim(), err = f.querySelector('.lib-form-err');
        if (!name) { err.textContent = 'A name cannot be empty.'; err.hidden = false; input.focus(); return; }
        try { const it = await lib.rename(item, name); drawer.close(); toast(`Renamed to “${it.name}”.`); } catch (e2) { err.textContent = `Not renamed: ${api.explain(e2, 'Renaming')}`; err.hidden = false; }
      });
    } });
}

function duplicateSheet(dup, body, b) {
  const copy = `${body.name || dup.name} (copy)`.slice(0, 120);
  drawer.open({ kicker: 'Saved research', title: 'Already saved', opener: b, form: true,
    body: html`<p>${what(dup)} is already in Saved research as <b>“${dup.name}”</b>, ${savedWhen(dup)}.</p>
      <div class="cluster"><button type="button" class="btn btn-primary" data-lib-update>Update the saved one</button><button type="button" class="btn" data-v2-close>Cancel</button></div>
      <p class="asof">Updating keeps its name and gives it what is on screen now, with today's date.</p>
      <form class="lib-form" data-lib-copy><p class="t-label">Or keep both</p>${nameField('lib-copy-name', copy)}<button type="submit" class="btn">Save a copy</button></form>`,
    mount: (el) => {
      el.querySelector('[data-lib-update]').addEventListener('click', () => attempt(b, body, { onDuplicate: 'update' }));
      el.querySelector('[data-lib-copy]').addEventListener('submit', (e) => {
        e.preventDefault();
        const name = el.querySelector('#lib-copy-name').value.replace(/\s+/g, ' ').trim();
        if (name) attempt(b, Object.assign({}, body, { name }), { onDuplicate: 'copy' });
      });
    } });
}

function manage(item, spec, b) {
  drawer.open({ kicker: 'Saved research', title: 'Saved', opener: b,
    body: html`<p>${what(item)} is in Saved research as <b>“${item.name}”</b>, ${savedWhen(item)}.</p>
      <div class="cluster"><button type="button" class="btn" data-lib-rename-open>Rename</button><button type="button" class="btn" data-lib-update>Update with what is on screen</button><a class="btn btn-quiet" href="#/research">Open Saved research</a></div>
      <div class="lib-del"><button type="button" class="btn btn-danger" data-lib-delete>Delete from Saved research</button></div>`,
    mount: (el) => {
      el.querySelector('[data-lib-rename-open]').addEventListener('click', () => renameSheet(item, b));
      el.querySelector('[data-lib-update]').addEventListener('click', () => attempt(b, Object.assign({}, spec, { name: item.name }), { onDuplicate: 'update' }));
      const del = el.querySelector('[data-lib-delete]');
      del.addEventListener('click', async () => {
        // two presses: the first asks, the second deletes (there is no copy to bring back)
        if (del.dataset.armed !== '1') { del.dataset.armed = '1'; del.textContent = `Yes, delete “${item.name}”`; return; }
        try { await lib.remove(item); drawer.close(); toast(`Deleted “${item.name}” from Saved research.`); }
        catch (e) { del.dataset.armed = ''; del.textContent = 'Delete from Saved research'; toast(`It was not deleted: ${api.explain(e, 'Deleting')}`, { kind: 'bad' }); }
      });
    } });
}

/* ---------------- wiring, once ---------------- */
if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('click', (e) => {
    const t = e.target && e.target.closest ? e.target : null; if (!t) return;
    const b = t.closest('[data-v2-save]'); if (b) { e.preventDefault(); press(b); return; }
    const r = t.closest('[data-v2-save-retry]');
    if (r) { const btn = r.closest('.lib-save') && r.closest('.lib-save').querySelector('[data-v2-save]'); const again = btn && RETRY.get(btn); if (again) again(); }
  });
  try { window.addEventListener('v2:library', (e) => paintKey((e.detail || {}).key, (e.detail || {}).item)); } catch (e) { /* no window in tests */ }
}
export const _test = { press, attempt, paintKey, SPECS };
