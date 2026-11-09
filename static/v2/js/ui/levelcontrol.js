// "How should Optic speak to you?": the one level control on Home and a company's Overview (2026-11-09, the owner's
// layout of that day). Three buttons, Beginner, Intermediate and Advanced, each a real button whose pressed state is
// announced. It replaces, on those two screens, the knowledge slider, the View setting (Simple or Advanced) and "Show
// advanced analysis" (decision card B): one control, so the words and what the screen shows can never disagree.
//
// The level changes the words and which panels appear, never a figure, a caveat or a disclosure (app/knowledge.py).
// It is the same one value Settings and Milo set (core/prefs.js), saved to a signed-in reader's account.
import { html, announce } from '../core/dom.js';
import * as prefs from '../core/prefs.js';
import { chooseLevel } from './levelslider.js';
import { icon } from './icons.js';

export const NAMES = { beginner: 'Beginner', intermediate: 'Intermediate', advanced: 'Advanced' };
// What each level means on these two screens, one sentence, said under the control
const SAYS = {
  beginner: 'Plain words and the essentials; the rest is under Show more.',
  intermediate: 'Adds the market detail and the bull and bear case.',
  advanced: 'Everything, in denser words.',
};

/** The control. `id` keeps its element ids unique on the page. */
export function levelControl({ id = 'lc' } = {}) {
  const now = prefs.level();
  return html`<div class="lc" data-v2-lc>
    <p class="lc-q" id="${id}-q">How should Optic speak to you? <span class="lc-i" title="It changes the words and how much each screen shows. Never a figure, a caveat or a disclosure.">${icon('help')}</span></p>
    <div class="lc-seg" role="group" aria-labelledby="${id}-q" aria-describedby="${id}-says">${prefs.LEVEL_IDS.map((lv) => html`<button type="button" class="lc-b" data-v2-level="${lv}" aria-pressed="${lv === now}">${NAMES[lv]}</button>`)}</div>
    <p class="lc-says" id="${id}-says">${SAYS[now] || ''}</p>
  </div>`;
}

/** Every control on the page shows the reader's level (after a change here, in another tab or at sign-in). */
export function syncControls(root = typeof document !== 'undefined' ? document : null) {
  if (!root) return;
  const now = prefs.level();
  root.querySelectorAll('[data-v2-lc]').forEach((box) => {
    box.querySelectorAll('[data-v2-level]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v2Level === now)));
    const says = box.querySelector('.lc-says'); if (says) says.textContent = SAYS[now] || '';
  });
}

if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('click', (e) => {
    const b = e.target.closest && e.target.closest('[data-v2-level]'); if (!b) return;
    const lv = b.dataset.v2Level;
    if (lv === prefs.level()) return;
    // the page repaints itself from prefs.onChange; focus goes back to the pressed button once it has
    if (chooseLevel(lv)) {
      syncControls();
      announce(`Optic now speaks at ${NAMES[lv]}. The screen shows ${lv === 'advanced' ? 'every panel' : 'the panels for that level'}.`);
      requestAnimationFrame(() => { const again = document.querySelector(`[data-v2-lc] [data-v2-level="${lv}"]`); if (again && document.activeElement !== again) again.focus({ preventScroll: true }); });
    }
  });
  prefs.onChange((what) => { if (what === 'knowledge' || what === 'knowledge-synced') syncControls(); });
}
