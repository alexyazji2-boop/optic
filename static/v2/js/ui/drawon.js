// The classic app's draw-on (static/charts.js animateChart), for v2's line and area charts: each line traces
// itself in from the left and the area under it fades in behind, once, as the chart is first drawn on a page.
// Not on a redraw, a refresh or a resize: a chart that redraws itself while it is being read is worse than one
// that never moves. Never set off by scrolling (the owner's checklist, 2026-10-19: no scroll animations), so a
// chart below the fold has drawn by the time it is reached. None with reduced motion.
const DRAW_MS = 620, FADE_MS = 300, STAGGER_MS = 70;
const EASE = 'cubic-bezier(0.33, 1, 0.68, 1)';
const reduced = () => !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

/** Draw `svg`'s lines (`lines`, a selector) in and fade its areas (`fades`) in, now. Returns a handle whose
 * `busy()` is true until the draw has finished, so a caller can hold a redraw rather than cut the line off. */
export function drawOn(svg, { lines = '', fades = '' } = {}) {
  const none = { busy: () => false };
  if (!svg || !svg.isConnected || reduced() || typeof svg.animate !== 'function') return none;
  const ds = [...svg.querySelectorAll(lines || ':not(*)')].map((el, i) => {
    let len = 0; try { len = el.getTotalLength(); } catch (e) { len = 0; }
    return len && Number.isFinite(len) ? { el, len, delay: i * STAGGER_MS } : null;
  }).filter(Boolean);
  if (!ds.length) return none;
  const until = performance.now() + DRAW_MS + ds[ds.length - 1].delay + 40;
  ds.forEach(({ el, len, delay }) => {
    el.style.strokeDasharray = `${len}`;
    const a = el.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: DRAW_MS, delay, easing: EASE, fill: 'backwards' });
    a.finished.then(() => { el.style.strokeDasharray = ''; }).catch(() => {});
  });
  // an empty last keyframe ends at the element's own opacity (an area drawn at 0.2 stays at 0.2)
  svg.querySelectorAll(fades || ':not(*)').forEach((el) => {
    el.animate([{ opacity: 0 }, {}], { duration: FADE_MS, delay: 120, easing: 'ease-out', fill: 'backwards' });
  });
  return { busy: () => performance.now() < until };
}
