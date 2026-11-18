// What the reader is looking at on a long page (Pass 2, 2026-11-17): the element marked data-v2-metric that the reader
// last pressed or focused, or else the one nearest the top of the screen. Milo is told its name, so "explain this
// chart" on Financials means the chart in view, not the page. Names only, never values.
//
// The press is kept by name, not by element, and it holds until the reader scrolls on their own (gauntlet, Pass 2
// round one): opening Milo from the top bar narrows the page and moves the pressed chart, and a page that redraws as
// its figures arrive replaces the element, so a press held as an element on screen was lost, and Milo was told the
// chart that slid under the header instead. A wheel, a swipe or a scrolling key ends the press; after that the chart
// nearest the top answers, as before.
const nameOf = (el) => (el.dataset.v2Metric || ((el.querySelector('h3, h2') || {}).textContent || '')).replace(/\s+/g, ' ').trim();
const SCROLL_KEYS = new Set(['PageDown', 'PageUp', 'ArrowDown', 'ArrowUp', 'Home', 'End', ' ', 'Spacebar']);

/** The metric's name: its data-v2-metric value, or else its own heading. Start watching `root`; `get()` answers the metric in view as {metric, el} or null; `stop()` ends it. */
export function watchInView(root) {
  let touched = null;   // { name, el } of the last press or focus inside root
  let moved = false;    // the reader has scrolled on their own since that press
  const mark = (e) => { const el = e.target && e.target.closest && e.target.closest('[data-v2-metric]'); if (el && root.contains(el)) { touched = { name: nameOf(el), el }; moved = false; } };
  const scrolled = () => { if (touched) moved = true; };
  const key = (e) => { const t = e.target; if (SCROLL_KEYS.has(e.key) && !(t && t.closest && t.closest('input, textarea, select, [contenteditable="true"], [role="slider"]'))) scrolled(); };
  root.addEventListener('click', mark, true);
  root.addEventListener('focusin', mark, true);
  window.addEventListener('wheel', scrolled, { passive: true, capture: true });
  window.addEventListener('touchmove', scrolled, { passive: true, capture: true });
  window.addEventListener('keydown', key, true);
  const onScreen = (el) => { const r = el.getBoundingClientRect(); return r.bottom > 80 && r.top < (window.innerHeight || 800) - 80; };
  const marked = () => [...root.querySelectorAll('[data-v2-metric]')].filter((e) => e.offsetParent !== null);
  // the pressed one, or the one drawn in its place when the page redrew
  const pressed = () => {
    if (!touched) return null;
    if (touched.el.isConnected && touched.el.offsetParent !== null) return touched.el;
    const again = marked().find((e) => nameOf(e) === touched.name);
    if (again) touched.el = again;
    return again || null;
  };
  return {
    get() {
      const p = pressed();
      if (p && (!moved || onScreen(p))) return { metric: touched.name, el: p };
      const els = marked().filter(onScreen);
      if (!els.length) return null;
      // the one whose top is nearest the top of the screen, below the sticky header
      els.sort((a, b) => Math.abs(a.getBoundingClientRect().top - 96) - Math.abs(b.getBoundingClientRect().top - 96));
      return { metric: nameOf(els[0]), el: els[0] };
    },
    stop() {
      root.removeEventListener('click', mark, true); root.removeEventListener('focusin', mark, true);
      window.removeEventListener('wheel', scrolled, { capture: true }); window.removeEventListener('touchmove', scrolled, { capture: true });
      window.removeEventListener('keydown', key, true);
    },
  };
}
