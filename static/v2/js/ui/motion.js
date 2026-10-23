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

export const reduced = () => !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
const ms = (name, fallback) => { const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name)); return Number.isFinite(v) ? v : fallback; };
const EASE_OUT = 'cubic-bezier(0.23, 1, 0.32, 1)';

/* ---------------- the page line ---------------- */
const SHOW_AFTER = 220;   // a section that loads faster than this never flashes a line
let watched = null, showT = null;

/** Keep `bar` (the shell's line under the top bar) shown while `root` has a skeleton still waiting. */
export function watchLoading(root, bar) {
  if (!root || !bar) return;
  if (watched) watched.disconnect();
  const busy = () => !!root.querySelector('.sk-wrap, [aria-busy="true"]');
  const sync = () => {
    if (busy()) {
      if (!bar.classList.contains('is-on') && !showT) showT = setTimeout(() => { showT = null; if (busy()) bar.classList.add('is-on'); }, SHOW_AFTER);
    } else { clearTimeout(showT); showT = null; bar.classList.remove('is-on'); }
  };
  watched = new MutationObserver(sync);
  watched.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ['aria-busy'] });
  sync();
}

/* ---------------- Dossier tabs ---------------- */
/** Before a route leaves: where the selected tab's bar is, and which symbol's tabs they are. */
export function tabsBefore(view) {
  const nav = view && view.querySelector('nav.tabs[data-v2-dtabs]');
  const cur = nav && nav.querySelector('a[aria-current="page"]');
  // offsets inside the strip, which scrolls sideways on a phone (the bar is placed in the strip's own coordinates)
  return cur && cur.offsetWidth ? { sym: nav.dataset.v2Dtabs, left: cur.offsetLeft, width: cur.offsetWidth } : null;
}

/** After the new page's first paint: slide the bar from where it was and fade the content under the header in. */
export function tabsAfter(view, before) {
  if (!before || reduced()) return;
  const nav = view.querySelector('nav.tabs[data-v2-dtabs]');
  if (!nav || nav.dataset.v2Dtabs !== before.sym) return;
  const cur = nav.querySelector('a[aria-current="page"]');
  if (!cur) return;
  const r = { width: cur.offsetWidth }, left = cur.offsetLeft;
  if (r.width && Math.abs(left - before.left) > 1 && cur.animate) {
    // the anchor's own bar is drawn by a pseudo-element that follows it; the moving one is a copy of it
    const ink = document.createElement('span');
    ink.className = 'tab-ink'; ink.setAttribute('aria-hidden', 'true');
    ink.style.width = `${r.width}px`; ink.style.left = `${left}px`;
    nav.appendChild(ink); nav.classList.add('is-moving');
    const a = ink.animate([{ transform: `translateX(${before.left - left}px) scaleX(${before.width / r.width})` }, { transform: 'none' }],
      { duration: ms('--m-panel', 200), easing: EASE_OUT });
    const done = () => { ink.remove(); nav.classList.remove('is-moving'); };
    a.finished.then(done, done);
  }
  // the content under the header, not the header: the name and price stay put (no full-page fade)
  let el = (nav.closest('.dstick') || nav).nextElementSibling;
  const parts = [];
  while (el && parts.length < 8) { parts.push(el); el = el.nextElementSibling; }
  parts.forEach((p) => { if (p.animate) p.animate([{ opacity: 0 }, { opacity: 1 }], { duration: ms('--m-content', 150), easing: 'ease-out' }); });
}
