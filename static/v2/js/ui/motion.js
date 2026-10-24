// Shared motion and loading (audit and motion session, 2026-10-22). One place for the few things that move, so
// pages do not each invent durations. The values are tokens in css/tokens.css (--m-press, --m-content, --m-panel,
// --m-exit, --ease-out, --ease-drawer); this module only decides when they run.
//
// What moves, and why each earns it:
// - The page line: a thin gold line under the top bar while the page still has a section waiting on data (a
//   skeleton on screen). It is tied to what the reader sees, not to the network: cached content shows no line,
//   a section that fails replaces its skeleton and the line stops, and nothing invents progress.
// - Dossier tabs: the gold bar slides from the tab that was selected to the new one, and the content under the
//   header fades in (opacity only). Only between tabs of one symbol: a new symbol keeps its own loading layout,
//   so old figures never sit under a new name. No full-page fades.
// - Milo: its states are listed in ui/milo.js (MILO_STATES); the same line marks an answer in progress.
// Nothing here runs with reduced motion: the tab bar and content appear at once, and the line stands still.

import { reducedMotion as reduced } from '../core/dom.js';
export { reduced };
const ms = (name, fallback) => { const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name)); return Number.isFinite(v) ? v : fallback; };
const EASE_OUT = 'cubic-bezier(0.23, 1, 0.32, 1)';

/* ---------------- the page line ---------------- */
const SHOW_AFTER = 220;   // a section that loads faster than this never flashes a line
let watched = null, showT = null;

/** Keep `bar` (the shell's line under the top bar) shown while `root` has a skeleton still waiting. */
export function watchLoading(root, bar) {
  if (!root || !bar) return;
  if (watched) watched.disconnect();
  // on screen only: Home hides its portfolio panel for a reader with no linked brokerage and leaves the panel's
  // skeleton inside it, which held the line on for good (audit regression, 2026-10-22)
  const busy = () => [...root.querySelectorAll('.sk-wrap, [aria-busy="true"]')].some((el) => el.getClientRects().length > 0);
  const sync = () => {
    if (busy()) {
      if (!bar.classList.contains('is-on') && !showT) showT = setTimeout(() => { showT = null; if (busy()) bar.classList.add('is-on'); }, SHOW_AFTER);
    } else { clearTimeout(showT); showT = null; bar.classList.remove('is-on'); }
  };
  watched = new MutationObserver(sync);
  watched.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ['aria-busy'] });
  sync();
}

/* ---------------- tabs ---------------- */
// Every page's tab strip (the Dossier's and a section's, pages/tabs.js), between pages of one strip: the same symbol's
// Dossier or the same section. The selected tab and its bar move on the press itself, before the next page's code has
// loaded (motion check 2026-10-24: a first visit showed nothing for up to 300 ms); the content under the header fades
// once it is drawn, on a phone too, where the strip is a menu and there is no bar to move.
const stripOf = (view) => view && (view.querySelector('nav.tabs[data-v2-dtabs]') || view.querySelector('nav.tabs'));
const keyOf = (nav) => (nav.dataset.v2Dtabs ? `d:${nav.dataset.v2Dtabs}` : `g:${nav.getAttribute('aria-label') || ''}`);

/** Slide a copy of the bar from {left, width} (offsets in the strip) to `cur`. */
function slide(nav, cur, from) {
  const width = cur.offsetWidth, left = cur.offsetLeft;
  if (!width || !from || from.left === null || Math.abs(left - from.left) <= 1 || !cur.animate) return;
  nav.querySelectorAll(':scope > .tab-ink').forEach((x) => x.remove());
  // the anchor's own bar is drawn by its border; the moving one is a copy of it
  const ink = document.createElement('span');
  ink.className = 'tab-ink'; ink.setAttribute('aria-hidden', 'true');
  ink.style.width = `${width}px`; ink.style.left = `${left}px`;
  nav.appendChild(ink); nav.classList.add('is-moving');
  const a = ink.animate([{ transform: `translateX(${from.left - left}px) scaleX(${from.width / width})` }, { transform: 'none' }],
    { duration: ms('--m-panel', 200), easing: EASE_OUT });
  const done = () => { ink.remove(); if (!nav.querySelector(':scope > .tab-ink')) nav.classList.remove('is-moving'); };
  a.finished.then(done, done);
}

/** Before a route leaves: which strip is on screen and where its selected tab's bar is (null left on a phone). */
export function tabsBefore(view) {
  const nav = stripOf(view);
  if (!nav) return null;
  const cur = nav.querySelector('a[aria-current="page"]'), vis = !!(cur && cur.offsetWidth);
  // offsets inside the strip, which scrolls sideways on a phone (the bar is placed in the strip's own coordinates)
  return { key: keyOf(nav), left: vis ? cur.offsetLeft : null, width: vis ? cur.offsetWidth : null };
}

/** After the new page's first paint: slide the bar if it has not moved already, and fade the content under the header. */
export function tabsAfter(view, before) {
  if (!before || reduced()) return;
  const nav = stripOf(view);
  if (!nav || keyOf(nav) !== before.key) return;
  const cur = nav.querySelector('a[aria-current="page"]');
  if (cur) slide(nav, cur, before);
  // the content under the header, not the header: the name and price stay put (no full-page fade)
  let el = (nav.closest('.dstick') || nav).nextElementSibling;
  const parts = [];
  while (el && parts.length < 8) { parts.push(el); el = el.nextElementSibling; }
  parts.forEach((p) => { if (p.animate) p.animate([{ opacity: 0 }, { opacity: 1 }], { duration: ms('--m-content', 150), easing: 'ease-out' }); });
}

/** A press on a tab: it is the selected one from this frame, whatever the next page still has to load. */
export function tabPressed(a) {
  const nav = a && a.closest('nav.tabs');
  if (!nav || a.getAttribute('aria-current') === 'page') return;
  const was = nav.querySelector('a[aria-current="page"]');
  const from = was && was.offsetWidth ? { left: was.offsetLeft, width: was.offsetWidth } : null;
  if (was) was.removeAttribute('aria-current');
  a.setAttribute('aria-current', 'page');
  if (!reduced()) slide(nav, a, from);
}
