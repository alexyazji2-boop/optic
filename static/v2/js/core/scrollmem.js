// Back, forward and refresh return the reader to where they were on a page.
// Pages render after the address changes, so the browser's own restoration
// lands on a page that is still short. Each history entry gets a key in
// history.state, its scroll position is kept under that key for the tab's
// session, and on arrival the position is put back once the page is tall
// enough, unless the reader scrolls, taps or types first.
const KEY = 'optic.v2.scroll.v1';
const STOP = ['wheel', 'touchstart', 'keydown', 'pointerdown'];
let mem = {}, n = 0, restoring = false, cancel = null, timer = null;
try { mem = JSON.parse(sessionStorage.getItem(KEY) || '{}') || {}; } catch (e) { mem = {}; }

const id = () => (history.state && history.state.v2k) || null;
function tag() {
  if (!id()) {
    try { history.replaceState(Object.assign({}, history.state || {}, { v2k: `${Date.now().toString(36)}${(n++).toString(36)}` }), ''); } catch (e) { /* a sandboxed frame */ }
  }
  return id();
}
function save() {
  const k = id();
  if (!k || restoring) return;
  mem[k] = Math.round(window.scrollY);
  const keys = Object.keys(mem);
  if (keys.length > 80) keys.slice(0, keys.length - 80).forEach((x) => { delete mem[x]; });
  try { sessionStorage.setItem(KEY, JSON.stringify(mem)); } catch (e) { /* private mode */ }
}

export function start() {
  try { history.scrollRestoration = 'manual'; } catch (e) { /* older browsers */ }
  window.addEventListener('scroll', () => { clearTimeout(timer); timer = setTimeout(save, 120); }, { passive: true });
  window.addEventListener('pagehide', save);
}

/** On every route: a new entry starts at the top; a revisited one goes back to where it was left. */
export function arrive() {
  if (cancel) cancel();
  const k = tag(), y = mem[k] || 0;
  if (!y) { window.scrollTo(0, 0); return; }
  restoring = true;
  const t0 = performance.now();
  let raf = 0;
  const stop = () => { restoring = false; cancelAnimationFrame(raf); STOP.forEach((e) => window.removeEventListener(e, stop, true)); cancel = null; };
  STOP.forEach((e) => window.addEventListener(e, stop, true));
  cancel = stop;
  const step = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    window.scrollTo(0, Math.max(0, Math.min(y, max)));
    if (max >= y || performance.now() - t0 > 5000) { stop(); return; }
    raf = requestAnimationFrame(step);
  };
  step();
}
