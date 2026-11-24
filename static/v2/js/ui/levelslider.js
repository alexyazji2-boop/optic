// The knowledge level as a three-position slider (2026-11-09; five positions from post-demo Phase 05 until then):
// Beginner, Intermediate, Advanced, the owner's names. Home and a company's Overview use the segmented control in
// ui/levelcontrol.js instead; this slider stays in Settings and Milo's Response settings, on the same one value. The level chosen is named beside the slider, and a short illustration shows
// how Optic would explain one fact at that level. A native range input, so arrows, Home and End, Page Up and Down,
// touch and screen readers all work as they do elsewhere; aria-valuetext names the level, not the number.
//
// One component for every place the level is set: Home's first-visit card, Settings and Milo's Response settings. The
// labels, blurbs and illustrations are the server's (/api/knowledge/modes, app/knowledge.py); this file holds none.
// Moving the slider previews a level; letting go (or each key press) sets it, through core/prefs.js, which keeps the
// one value and core/store.js sends it to a signed-in reader's account.
import { html } from '../core/dom.js';
import * as api from '../core/api.js';
import * as prefs from '../core/prefs.js';
import * as store from '../core/store.js';
import { toast } from './toast.js';

let CAT = null, pending = null;
/** The server's catalogue of levels, fetched once; every slider on the page is filled in when it lands. */
export function catalogue() {
  if (CAT) return Promise.resolve(CAT);
  if (!pending) {
    pending = api.get('/api/knowledge/modes', { ttl: 3600000 })
      .then((d) => { CAT = d && Array.isArray(d.modes) ? d : null; sync(); return CAT; }, () => { pending = null; return null; });
  }
  return pending;
}
// the catalogue's entries for the three levels the reader chooses from, in order (app/knowledge.py THREE)
const three = () => { const ms = (CAT && CAT.modes) || []; return prefs.LEVEL_IDS.map((id) => ms.find((m) => m.id === id)).filter(Boolean); };
const modeAt = (i) => three()[i] || null;
const LAST = prefs.LEVEL_IDS.length - 1;
/** A level's name from the catalogue, or '' until it has landed. */
export const levelLabel = (id) => ((((CAT || {}).modes) || []).find((m) => m.id === id) || {}).label || '';
const valueText = (m, i) => (m ? `${m.label}, level ${i + 1} of ${LAST + 1}` : `Level ${i + 1} of ${LAST + 1}`);

/** The slider. `id` makes its element ids unique on the page; `compact` leaves out the level's one-line description. */
export function levelSlider({ id = 'lvl', label = 'How Optic explains things', compact = false } = {}) {
  if (!CAT) catalogue();
  const i = prefs.levelIndex(), m = modeAt(i), first = modeAt(0), last = modeAt(LAST);
  return html`<div class="lvl ${compact ? 'lvl-compact' : ''}" data-v2-lvl>
    <label class="lvl-label" for="${id}-in">${label}</label>
    <div class="lvl-row">
      <div class="lvl-track"><input id="${id}-in" class="lvl-in" type="range" min="1" max="${LAST + 1}" step="1" value="${i + 1}"
        aria-valuetext="${valueText(m, i)}" aria-describedby="${id}-prev" data-v2-lvl-in>
        <div class="lvl-ticks" aria-hidden="true">${prefs.LEVEL_IDS.map(() => html`<i></i>`)}</div>
        <div class="lvl-ends" aria-hidden="true"><span data-v2-lvl-first>${first ? first.label : ''}</span><span data-v2-lvl-last>${last ? last.label : ''}</span></div></div>
      <output class="lvl-now" for="${id}-in" data-v2-lvl-now>${m ? m.label : ''}</output>
    </div>
    ${compact ? '' : html`<p class="lvl-blurb" data-v2-lvl-blurb>${m ? m.blurb : ''}</p>`}
    <p class="lvl-prev" id="${id}-prev"><span class="t-label">Illustration</span> <span data-v2-lvl-prev>${m ? m.preview : ''}</span></p>
  </div>`;
}

/** Show a position's level in one slider's text (while it is dragged, or after the level changed elsewhere). */
function show(box, i) {
  const m = modeAt(i), set = (sel, text) => { const el = box.querySelector(sel); if (el) el.textContent = text; };
  if (!m) return;
  set('[data-v2-lvl-now]', m.label); set('[data-v2-lvl-blurb]', m.blurb); set('[data-v2-lvl-prev]', m.preview);
  set('[data-v2-lvl-first]', (modeAt(0) || {}).label || ''); set('[data-v2-lvl-last]', (modeAt(LAST) || {}).label || '');
  const input = box.querySelector('[data-v2-lvl-in]'); if (input) input.setAttribute('aria-valuetext', valueText(m, i));
}
/** Every slider on the page shows the reader's level: after the catalogue lands, and after the level changes. */
export function sync(root = typeof document !== 'undefined' ? document : null) {
  if (!root) return;
  const i = prefs.levelIndex();
  root.querySelectorAll('[data-v2-lvl]').forEach((box) => {
    const input = box.querySelector('[data-v2-lvl-in]');
    if (input && input !== document.activeElement) input.value = String(i + 1);
    show(box, input && input === document.activeElement ? Number(input.value) - 1 : i);
  });
}

/** Set the reader's level from any control: this browser at once, and a signed-in reader's account. True when it
 *  changed. One path for the slider and the level control (ui/levelcontrol.js), so both save it the same way. */
export function chooseLevel(id) {
  if (!id || !prefs.setKnowledge(id)) return false;
  if (store.signedIn()) {
    // a signed-in reader's level is the account's; if it cannot be saved there, this browser keeps it and says so
    store.pushLevel().then((r) => { if (!r.ok) toast('Kept in this browser. Your account did not save it; Optic will try again on your next visit.', { kind: 'bad' }); });
  }
  return true;
}

if (typeof document !== 'undefined' && document.addEventListener) {
  // dragging previews, letting go sets; a key press fires both, so each step is set as it is reached
  document.addEventListener('input', (e) => {
    const input = e.target.closest && e.target.closest('[data-v2-lvl-in]'); if (!input) return;
    show(input.closest('[data-v2-lvl]'), Number(input.value) - 1);
  });
  document.addEventListener('change', (e) => {
    const input = e.target.closest && e.target.closest('[data-v2-lvl-in]'); if (!input) return;
    chooseLevel(prefs.LEVEL_IDS[Number(input.value) - 1]);
  });
  prefs.onChange((what) => { if (what === 'knowledge' || what === 'knowledge-synced') sync(); });
  // another tab moved it: the stored value is newer than this page's
  window.addEventListener('storage', (e) => { if (e.key === 'optic.knowledge.v1') sync(); });
}
