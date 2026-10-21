// Sideways strips (Classic parity B3.2 and B3.7, 2026-10-21): the rows that scroll sideways with their scrollbar
// hidden (the Dossier tabs, Home's market strip on a phone, the section index, the tool rails) say when there is
// more, and a mouse can reach it.
//
// - An arrow at an edge, shown only while there is more that way. It scrolls the strip most of its width, so a
//   reader without a wheel or a trackpad can reach the far end. Classic used fades; a fade is a gradient, which the
//   design standard keeps for the rail's divider and the loading shimmer, so here it is a button (DESIGN-STANDARD.md).
// - A vertical wheel over the strip scrolls it sideways, only while it can still move that way and only for a
//   gesture that started on it (Classic's app.js:50755): at an end, or for a page scroll passing over, the page
//   scrolls.
// - A mouse can drag it (Classic's app.js:50790); a drag of more than a few pixels does not click what it ends on.
//   A finger scrolls it natively.
//
// The arrows are children of the strip, sticky at its edges with a negative margin, so they take no room and need
// no wrapper; a page that redraws a strip loses them, and one observer puts them back.
import { icon } from './icons.js';

export const STRIPS = '.tabs, .tabset, .mstrip, .drail, .bk-tabs, .chw-rail, .ch-draw, .ws-presets, .chips-scroll, .sec-list, .cs-strip, .palette-filters';
const LATCH_MS = 200;
let lastWheel = { at: -1e9, el: null };

function edges(el) {
  if (el.dataset.strip === '1' && el.querySelector(':scope > .strip-edge')) return;
  el.dataset.strip = '1';
  const mk = (side) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = `strip-edge strip-${side}`; b.tabIndex = -1; b.hidden = true;
    b.setAttribute('aria-hidden', 'true');   // a pointer's convenience: the keyboard reaches each item by Tab, and the strip follows focus
    b.title = side === 'start' ? 'Scroll back' : 'Scroll on';
    b.innerHTML = icon(side === 'start' ? 'chevL' : 'chev').s;
    b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); el.scrollBy({ left: (side === 'start' ? -1 : 1) * Math.max(120, el.clientWidth * 0.8), behavior: reduced() ? 'auto' : 'smooth' }); });
    return b;
  };
  el.prepend(mk('start')); el.append(mk('end'));
  paintBg(el);
  sync(el);
}
// The arrows sit over the strip's ends, so they take the colour of whatever is behind the strip (the page, a panel,
// a sheet): the first ancestor with a background of its own.
function paintBg(el) {
  let n = el, bg = '';
  while (n && n.nodeType === 1) { const c = getComputedStyle(n).backgroundColor; if (c && c !== 'transparent' && !/rgba\([^)]*,\s*0\)$/.test(c)) { bg = c; break; } n = n.parentElement; }
  el.style.setProperty('--strip-bg', bg || 'var(--c-plane)');
  // a sticky arrow stops at the strip's padding: it reaches over it, so nothing scrolled shows beside it
  const cs = getComputedStyle(el);
  el.style.setProperty('--strip-pl', cs.paddingLeft); el.style.setProperty('--strip-pr', cs.paddingRight);
}
const reduced = () => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; } };
/** Which arrows a strip shows: there is more before it, after it, or both. */
export function moreWays(scrollLeft, clientWidth, scrollWidth) {
  const max = scrollWidth - clientWidth;
  return { start: max > 1 && scrollLeft > 1, end: max > 1 && scrollLeft < max - 1 };
}
function sync(el) {
  const w = moreWays(el.scrollLeft, el.clientWidth, el.scrollWidth);
  const a = el.querySelector(':scope > .strip-start'), b = el.querySelector(':scope > .strip-end');
  if (a && a.hidden === w.start) a.hidden = !w.start;
  if (b && b.hidden === w.end) b.hidden = !w.end;
}

// one listener of each kind for the whole document, delegating to the strip under the event
function stripOf(t) { return t && t.closest ? t.closest('[data-strip="1"]') : null; }
function onScroll(e) { const el = e.target; if (el && el.dataset && el.dataset.strip === '1') sync(el); }
function onWheel(e) {
  const now = e.timeStamp > 0 ? e.timeStamp : performance.now(), el = stripOf(e.target);
  const fresh = now - lastWheel.at >= LATCH_MS || lastWheel.el === el;
  lastWheel = { at: now, el: fresh ? el : lastWheel.el };
  if (!el || !fresh || e.ctrlKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;   // sideways strokes scroll it natively
  const max = el.scrollWidth - el.clientWidth, d = e.deltaMode === 1 ? e.deltaY * 33 : e.deltaY;
  if (max <= 1 || !d) return;
  const next = Math.max(0, Math.min(max, el.scrollLeft + d));
  if (next === el.scrollLeft) return;   // at the end that way: the page's
  e.preventDefault();
  el.scrollLeft = next;
}
let drag = null;
function onDown(e) {
  if (e.pointerType !== 'mouse' || e.button !== 0) return;
  const el = stripOf(e.target); if (!el || el.scrollWidth - el.clientWidth <= 1 || e.target.closest('.strip-edge')) return;
  drag = { el, x: e.clientX, left: el.scrollLeft, moved: false };
}
function onMove(e) {
  if (!drag) return;
  if (e.buttons === 0) { drag = null; return; }
  const dx = e.clientX - drag.x;
  if (!drag.moved && Math.abs(dx) < 6) return;
  drag.moved = true; drag.el.classList.add('is-dragging');
  drag.el.scrollLeft = drag.left - dx;
}
function onUp() {
  if (!drag) return;
  const d = drag; drag = null; d.el.classList.remove('is-dragging');
  // a drag ends on an item: that is not a click on it
  if (d.moved) { const stop = (ev) => { ev.preventDefault(); ev.stopPropagation(); }; d.el.addEventListener('click', stop, { capture: true, once: true }); setTimeout(() => d.el.removeEventListener('click', stop, { capture: true }), 0); }
}

let armed = false, ro = null, raf = 0;
function scan(root) {
  root.querySelectorAll(STRIPS).forEach((el) => { edges(el); if (ro && !el.dataset.stripObs) { el.dataset.stripObs = '1'; ro.observe(el); } });
}
/** Watch the document: every strip, now and later, gets its arrows, its wheel and its drag. Called once at boot. */
export function startStrips(root = document.body) {
  if (armed) return; armed = true;
  ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver((es) => es.forEach((x) => sync(x.target))) : null;
  document.addEventListener('scroll', onScroll, { capture: true, passive: true });
  document.addEventListener('wheel', onWheel, { passive: false });
  document.addEventListener('pointerdown', onDown);
  document.addEventListener('pointermove', onMove);
  document.addEventListener('pointerup', onUp); document.addEventListener('pointercancel', onUp);
  // a strip's own contents change (a redraw, a tab added): its width does too
  // a theme change repaints the surfaces behind the strips
  new MutationObserver(() => requestAnimationFrame(() => root.querySelectorAll('[data-strip="1"]').forEach(paintBg))).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class', 'style'] });
  new MutationObserver(() => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; scan(root); root.querySelectorAll('[data-strip="1"]').forEach(sync); }); }).observe(root, { childList: true, subtree: true });
  scan(root);
}
