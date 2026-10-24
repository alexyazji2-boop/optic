// The inspector: one drawer for every object (an answer's evidence, an event,
// Milo). A modal dialog: focus moves to its title, Tab stays inside, Escape or
// the close button shuts it, and focus goes back to what opened it. On phones
// it rises as a sheet.
import { $, html, render, trapFocus, announce } from '../core/dom.js';
import { icon } from './icons.js';

let root, panel, from, untrap, onClose, sticky = false, vvOff = null, shown = false, hideT = 0, leaving = null;

// How long the drawer takes to leave: its longest transition as computed, so the CSS stays the one place that says
// (--m-exit, and 0 under reduced motion, where the drawer goes at once).
function exitMs() {
  const longest = (el) => {
    const s = getComputedStyle(el), d = s.transitionDuration.split(','), w = s.transitionDelay.split(',');
    return Math.max(0, ...d.map((x, i) => (parseFloat(x) + parseFloat(w[i % w.length] || '0')) * 1000));
  };
  return Math.max(longest(panel), longest($('.drawer-scrim', root)));
}

function ensure() {
  if (root) return;
  root = document.createElement('div');
  root.className = 'drawer'; root.hidden = true;
  root.innerHTML = '<div class="drawer-scrim"></div><section class="drawer-panel" role="dialog" aria-modal="true" aria-labelledby="drawer-title"></section>';
  document.body.appendChild(root);
  panel = $('.drawer-panel', root);
  root.addEventListener('click', (e) => {
    if (e.target.closest('[data-v2-close]') || e.target.classList.contains('drawer-scrim')) close();
  });
}

// sticky: a question that must survive navigation (the guest's things).
// form: a sheet with fields in it. On a phone it shrinks to the part of the screen the keyboard
// leaves (visualViewport), so the field being typed in and the button under it stay in view.
// head and actions: a panel's own header (it must hold the #drawer-title heading) and buttons before Close
// (Milo's compact header, 2026-10-20); every other drawer keeps the kicker and title.
export function open({ kicker = '', title, body, opener, mount, closed, keep = false, form = false, head = null, actions = null }) {
  ensure();
  if (shown) close({ silent: true, force: true, now: true });
  if (leaving) { clearTimeout(hideT); leaving(); }   // opened again while the last one was still leaving: finish it first
  panel.classList.toggle('is-form', !!form);
  const vv = window.visualViewport;
  if (form && vv) { const fit = () => panel.style.setProperty('--vvh', `${Math.round(vv.height)}px`); fit(); vv.addEventListener('resize', fit); vvOff = () => { vv.removeEventListener('resize', fit); panel.style.removeProperty('--vvh'); vvOff = null; }; }
  sticky = keep;
  from = opener || document.activeElement;
  onClose = closed;
  const shut = html`<button type="button" class="icon-btn" data-v2-close aria-label="Close" ${actions ? html`title="Close"` : ''}>${icon('close')}</button>`;
  render(panel, html`<header class="drawer-head">${head || html`<div><p class="drawer-kicker">${kicker}</p><h2 id="drawer-title" tabindex="-1">${title}</h2></div>`}
    ${actions ? html`<div class="drawer-acts">${actions}${shut}</div>` : shut}</header>
    <div class="drawer-body">${body}</div>`);
  root.hidden = false; shown = true;
  document.body.classList.add('drawer-open');
  if (from && from.setAttribute && from.hasAttribute('aria-expanded')) from.setAttribute('aria-expanded', 'true');
  requestAnimationFrame(() => { root.classList.add('is-open'); $('#drawer-title', panel).focus(); });
  untrap = trapFocus(panel, () => close());
  if (mount) mount($('.drawer-body', panel));
  announce(`${title} opened`);
}

// The drawer closes at once (isOpen, focus, the page behind it), and its panel then plays the exit before it leaves
// the page, inert so nothing in it can be reached. Hiding it in the same moment skipped the exit transition: the
// panel was gone in the next painted frame (motion check 2026-10-24). What the panel's owner set up on it is taken
// down once it has left (`closed`, the keyboard's height): Milo's teardown, run at once, dropped its full-screen
// layout for the generic sheet's in the first frame of the exit. `now` is for open() replacing one drawer with another.
export function close({ silent, route, force, now } = {}) {
  if (!root || !shown) return;
  if (sticky && route && !force) return;
  sticky = false; shown = false;
  root.classList.remove('is-open');
  document.body.classList.remove('drawer-open');
  if (untrap) untrap();
  if (from && from.setAttribute && from.hasAttribute('aria-expanded')) from.setAttribute('aria-expanded', 'false');
  if (!silent && from && document.contains(from)) from.focus();
  from = null;
  const done = onClose, vv = vvOff;
  onClose = null; vvOff = null;
  leaving = () => { leaving = null; root.hidden = true; root.inert = false; if (vv) vv(); if (done) done(); };
  const ms = now ? 0 : exitMs();
  if (ms > 0) { root.inert = true; hideT = setTimeout(leaving, ms + 20); } else leaving();
}

export const isOpen = () => !!root && shown;
export const body = () => root && $('.drawer-body', panel);
