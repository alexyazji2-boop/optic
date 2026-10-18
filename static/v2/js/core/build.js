// A page left open across a deploy keeps running the code it loaded. The
// server stamps v2's page with its build (meta optic-build); this checks
// /api/build when the tab comes back into view and every ten minutes, and
// offers a reload when v2 has changed. It never reloads by itself: a reader
// may be mid-way through a form or a Milo answer.
//
// The same check carries a rollback: when v2 is closed to this reader
// (OPTIC_V2_ACCESS=owner), or "/" has gone back to the classic app and this
// tab was opened at "/", the bar offers the classic app at the same address.
// Both apps read the same account and browser keys, so nothing is left behind.
import { html, render } from './dom.js';
import { CLASSIC } from './classic.js';

const mine = () => { const m = document.querySelector('meta[name="optic-build"]'); return m ? m.content : null; };
let shown = false, last = 0;
async function check() {
  const have = mine(); if (!have || shown || Date.now() - last < 60000) return;
  last = Date.now();
  try {
    const r = await fetch('/api/build', { credentials: 'same-origin', cache: 'no-store' });
    const d = await r.json();
    if (d && (d.v2_open === false || (d.ui === 'classic' && !location.pathname.startsWith('/v2')))) offer('classic');
    else if (d && d.v2 && d.v2 !== have) offer();
  } catch (e) { /* offline: try again later */ }
}
function offer(kind) {
  shown = true;
  const bar = document.createElement('div');
  bar.className = 'build-new'; bar.setAttribute('role', 'status');
  render(bar, kind === 'classic'
    ? html`<p>Optic has moved this page back to the classic app. Your lists, settings and Milo history are there too.</p><button type="button" class="btn btn-sm btn-primary" data-v2-build-classic>Open the classic app</button><button type="button" class="btn btn-sm" data-v2-build-later>Later</button>`
    : html`<p>A new version of Optic is ready.</p><button type="button" class="btn btn-sm btn-primary" data-v2-build-reload>Reload</button><button type="button" class="btn btn-sm" data-v2-build-later>Later</button>`);
  bar.addEventListener('click', (e) => {
    if (e.target.closest('[data-v2-build-reload]')) location.reload();
    if (e.target.closest('[data-v2-build-classic]')) location.href = `${CLASSIC}${location.hash}`;
    if (e.target.closest('[data-v2-build-later]')) bar.remove();
  });
  document.body.appendChild(bar);
}
export function watchBuild() {
  document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
  setInterval(() => { if (!document.hidden) check(); }, 10 * 60 * 1000);
}
export const _test = { check, offer, reset: () => { last = 0; shown = false; document.querySelectorAll('.build-new').forEach((b) => b.remove()); } };
