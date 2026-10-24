// The classic app's draw-on (static/charts.js animateChart), for v2's line and area charts: each line traces
// itself in from the left and the area under it fades in behind, once, as the chart is first drawn on a page.
// Not on a redraw, a refresh or a resize: a chart that redraws itself while it is being read is worse than one
// that never moves. Never set off by scrolling (the owner's checklist, 2026-10-19: no scroll animations), so a
// chart below the fold has drawn by the time it is reached. None with reduced motion.
import { reducedMotion as reduced } from '../core/dom.js';

// Timed by tokens (2026-10-24 motion proposal): --m-reveal for the trace (it was 620 ms, which could hold a redraw back),
// the area a little after, and --m-stagger between lines, at most four apart. It never holds data: any redraw, input or
// new data finishes it on the spot (finish(), and the first press, key or wheel on the chart).
const tok = (name, fallback) => { const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name)); return Number.isFinite(v) ? v : fallback; };
const EASE = 'cubic-bezier(0.33, 1, 0.68, 1)';
export function drawOn(svg, { lines = '', fades = '' } = {}) {
  const none = { busy: () => false, finish() {}, carry() {} };
  if (!svg || !svg.isConnected || reduced() || typeof svg.animate !== 'function') return none;
  const DRAW_MS = tok('--m-reveal', 400), STAGGER_MS = tok('--m-stagger', 24);
  const ds = [...svg.querySelectorAll(lines || ':not(*)')].map((el, i) => {
    let len = 0; try { len = el.getTotalLength(); } catch (e) { len = 0; }
    return len && Number.isFinite(len) ? { el, len, delay: Math.min(i, 3) * STAGGER_MS } : null;
  }).filter(Boolean);
  if (!ds.length) return none;
  const t0 = performance.now(), until = t0 + DRAW_MS + Math.min(ds.length - 1, 3) * STAGGER_MS + 40;
  let anims = [];
  // `at`: how far in it already is, for the same lines drawn again (carry)
  const start = (at) => {
    svg.querySelectorAll(lines || ':not(*)').forEach((el, i) => {
      let len = 0; try { len = el.getTotalLength(); } catch (e) { len = 0; }
      if (!len || !Number.isFinite(len)) return;
      el.style.strokeDasharray = `${len}`;
      const a = el.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: DRAW_MS, delay: Math.min(i, 3) * STAGGER_MS, easing: EASE, fill: 'backwards' });
      a.currentTime = at;
      a.finished.then(() => { el.style.strokeDasharray = ''; }).catch(() => {});
      anims.push(a);
    });
    // an empty last keyframe ends at the element's own opacity (an area drawn at 0.2 stays at 0.2)
    svg.querySelectorAll(fades || ':not(*)').forEach((el) => {
      const a = el.animate([{ opacity: 0 }, {}], { duration: Math.round(DRAW_MS / 2), delay: 80, easing: 'ease-out', fill: 'backwards' });
      a.currentTime = at; anims.push(a);
    });
  };
  start(0);
  let done = false;
  const finish = () => {
    if (done) return; done = true;
    anims.forEach((a) => { try { a.finish(); } catch (e) { /* already gone with its element */ } });
    ['pointerdown', 'keydown', 'wheel'].forEach((ev) => svg.removeEventListener(ev, finish));
  };
  ['pointerdown', 'keydown', 'wheel'].forEach((ev) => svg.addEventListener(ev, finish, { passive: true }));
  // the chart drew itself again with the same lines (a settling redraw, the crosshair): the trace goes on from where
  // it was on the new elements rather than restart or vanish
  const carry = () => { if (done) return; anims.forEach((a) => { try { a.cancel(); } catch (e) { /* gone */ } }); anims = []; start(performance.now() - t0); };
  return { busy: () => !done && performance.now() < until, finish, carry };
}
