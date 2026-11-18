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

// The control is a setting, so it sits in the second tier (visual hierarchy review, 2026-11-10, change 3, F3): it was
// drawn at the heading's tier (a 14px question, three 44px buttons and a 13px sentence, level with Home's greeting and
// beside the company page's Milo bar), and its pressed state was a fill of 1.37:1 against its own track. Now: 14px
// labels on 36px buttons, the question a 13px label on the same line, a gold bar under the pressed level, and the
// one-sentence preview (directive 05) as the control's title and a line shown for a few seconds after a change. The
// sentence stays in the page as the group's description, so a screen reader still hears it.
const SAID_MS = 4000;
let saidUntil = 0, saidTimer = 0;
const said = () => Date.now() < saidUntil;

/** The control. `id` keeps its element ids unique on the page. */
export function levelControl({ id = 'lc' } = {}) {
  const now = prefs.level();
  return html`<div class="lc${said() ? ' is-said' : ''}" data-v2-lc>
    <p class="lc-q" id="${id}-q"><span class="lc-qt">How should Optic speak to you?</span> <span class="lc-i" title="It changes the words and how much each screen shows. Never a figure, a caveat or a disclosure.">${icon('help')}</span></p>
    <div class="lc-seg" role="group" aria-labelledby="${id}-q" aria-describedby="${id}-says" title="${SAYS[now] || ''}">${prefs.LEVEL_IDS.map((lv) => html`<button type="button" class="lc-b" data-v2-level="${lv}" aria-pressed="${lv === now}">${NAMES[lv]}</button>`)}</div>
    <p class="lc-says" id="${id}-says">${SAYS[now] || ''}</p>
  </div>`;
}
/** The preview line shows for a few seconds after the reader changes the level, on every control on the page. */
function sayFor() {
  saidUntil = Date.now() + SAID_MS;
  document.querySelectorAll('[data-v2-lc]').forEach((box) => box.classList.add('is-said'));
  clearTimeout(saidTimer);
  saidTimer = setTimeout(() => document.querySelectorAll('[data-v2-lc]').forEach((box) => box.classList.remove('is-said')), SAID_MS);
}

/** Every control on the page shows the reader's level (after a change here, in another tab or at sign-in). */
export function syncControls(root = typeof document !== 'undefined' ? document : null) {
  if (!root) return;
  const now = prefs.level();
  root.querySelectorAll('[data-v2-lc]').forEach((box) => {
    box.querySelectorAll('[data-v2-level]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v2Level === now)));
    const says = box.querySelector('.lc-says'); if (says) says.textContent = SAYS[now] || '';
    const seg = box.querySelector('.lc-seg'); if (seg) seg.title = SAYS[now] || '';
  });
}

if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('click', (e) => {
    const b = e.target.closest && e.target.closest('[data-v2-level]'); if (!b) return;
    const lv = b.dataset.v2Level;
    if (lv === prefs.level()) return;
    // The page repaints itself from prefs.onChange, synchronously inside chooseLevel, so focus goes back to the
    // pressed button here, in the same task. It was put back in the next animation frame, unconditionally: under load
    // that frame ran after the reader had already moved on and pressed Show more, and took focus back from the panel
    // Show more had opened (the keyboard journey failed once in three suite runs, gauntlet D2, 2026-11-10). The frame
    // is kept only as a fallback for a page that repaints later, and only takes focus that the repaint dropped.
    if (chooseLevel(lv)) {
      syncControls(); sayFor();
      announce(`Optic now speaks at ${NAMES[lv]}. The screen shows ${lv === 'advanced' ? 'every panel' : 'the panels for that level'}.`);
      const back = () => { const again = document.querySelector(`[data-v2-lc] [data-v2-level="${lv}"]`); if (again && document.activeElement !== again) again.focus({ preventScroll: true }); };
      const dropped = () => !document.activeElement || document.activeElement === document.body || !document.activeElement.isConnected;
      if (dropped() || !b.isConnected) back();
      requestAnimationFrame(() => { if (dropped()) back(); });
    }
  });
  prefs.onChange((what) => { if (what === 'knowledge' || what === 'knowledge-synced') syncControls(); });
}
