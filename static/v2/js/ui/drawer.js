// The inspector: one drawer for every object (an answer's evidence, an event,
// Milo). A modal dialog: focus moves to its title, Tab stays inside, Escape or
// the close button shuts it, and focus goes back to what opened it. On phones
// it rises as a sheet.
//
// makeDrawer() makes another, with a root of its own: Milo's (ui/milo.js), which can also be docked beside the
// page (Classic parity B4a, 2026-10-21). Docked, it is not a dialog: no scrim, no focus trap, the page beside it
// stays usable, it stays open across pages, and Escape inside it still closes it. The default instance below is
// the inspector every other caller uses, unchanged.
import { $, html, render, trapFocus, announce } from '../core/dom.js';
import { icon } from './icons.js';

export function makeDrawer({ cls = '', titleId = 'drawer-title' } = {}) {
  let root, panel, from, untrap, onClose, sticky = false, vvOff = null, docked = false, offEsc = null, titleText = '';
  let shown = false, hideT = 0, leaving = null;

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
    root.className = `drawer ${cls}`.trim(); root.hidden = true;
    root.innerHTML = `<div class="drawer-scrim"></div><section class="drawer-panel" role="dialog" aria-modal="true" aria-labelledby="${titleId}"></section>`;
    document.body.appendChild(root);
    panel = $('.drawer-panel', root);
    root.addEventListener('click', (e) => {
      if (e.target.closest('[data-v2-close]') || e.target.classList.contains('drawer-scrim')) close();
    });
  }
  // modal or docked: the trap, the dialog's role and the page's dimming follow it
  function setModal(modal) {
    if (untrap) { untrap(); untrap = null; }
    if (offEsc) { offEsc(); offEsc = null; }
    if (modal) {
      panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true');
      untrap = trapFocus(panel, () => close());
      document.body.classList.add('drawer-open');
    } else {
      panel.setAttribute('role', 'complementary'); panel.removeAttribute('aria-modal');
      const onKey = (e) => { if (e.key === 'Escape' && !e.defaultPrevented) { e.preventDefault(); close(); } };
      panel.addEventListener('keydown', onKey); offEsc = () => panel.removeEventListener('keydown', onKey);
      document.body.classList.remove('drawer-open');
    }
  }

  // sticky: a question that must survive navigation (the guest's things).
  // form: a sheet with fields in it. On a phone it shrinks to the part of the screen the keyboard
  // leaves (visualViewport), so the field being typed in and the button under it stay in view.
  // head and actions: a panel's own header (it must hold the #drawer-title heading) and buttons before Close
  // (Milo's compact header, 2026-10-20); every other drawer keeps the kicker and title. A second drawer's title has an
  // id of its own (`titleId`), so two open at once never share one.
  // dock: open beside the page instead of over it (see setDocked).
  function open({ kicker = '', title, body, opener, mount, closed, keep = false, form = false, head = null, actions = null, dock = false }) {
    ensure();
    if (shown) close({ silent: true, force: true, now: true });
    if (leaving) { clearTimeout(hideT); leaving(); }   // opened again while the last one was still leaving: finish it first
    panel.classList.toggle('is-form', !!form);
    const vv = window.visualViewport;
    if (form && vv) { const fit = () => panel.style.setProperty('--vvh', `${Math.round(vv.height)}px`); fit(); vv.addEventListener('resize', fit); vvOff = () => { vv.removeEventListener('resize', fit); panel.style.removeProperty('--vvh'); vvOff = null; }; }
    sticky = keep;
    from = opener || document.activeElement;
    onClose = closed;
    titleText = title;
    const shut = html`<button type="button" class="icon-btn" data-v2-close aria-label="Close" ${actions ? html`title="Close"` : ''}>${icon('close')}</button>`;
    render(panel, html`<header class="drawer-head">${head || html`<div><p class="drawer-kicker">${kicker}</p><h2 id="${titleId}" tabindex="-1">${title}</h2></div>`}
      ${actions ? html`<div class="drawer-acts">${actions}${shut}</div>` : shut}</header>
      <div class="drawer-body">${body}</div>`);
    root.hidden = false; shown = true;
    docked = !!dock; root.classList.toggle('is-docked', docked);
    if (from && from.setAttribute && from.hasAttribute('aria-expanded')) from.setAttribute('aria-expanded', 'true');
    requestAnimationFrame(() => { root.classList.add('is-open'); const h = $(`#${titleId}`, panel); if (h) h.focus(); });
    setModal(!docked);
    if (mount) mount($('.drawer-body', panel));
    announce(`${title} opened`);
  }

  // The drawer closes at once (isOpen, focus, the page behind it), and its panel then plays the exit before it leaves
  // the page, inert so nothing in it can be reached. Hiding it in the same moment skipped the exit transition: the
  // panel was gone in the next painted frame (motion check 2026-10-24). What the panel's owner set up on it is taken
  // down once it has left (`closed`, the keyboard's height): Milo's teardown, run at once, dropped its full-screen
  // layout for the generic sheet's in the first frame of the exit. `now` is for open() replacing one drawer with another.
  function close({ silent, route, force, now } = {}) {
    if (!root || !shown) return;
    if ((sticky || docked) && route && !force) return;   // a docked panel stays open from page to page
    sticky = false; shown = false;
    root.classList.remove('is-open', 'is-docked');
    docked = false;
    document.body.classList.remove('drawer-open');
    if (untrap) { untrap(); untrap = null; }
    if (offEsc) { offEsc(); offEsc = null; }
    if (from && from.setAttribute && from.hasAttribute('aria-expanded')) from.setAttribute('aria-expanded', 'false');
    if (!silent && from && document.contains(from)) from.focus();
    from = null;
    const done = onClose, vv = vvOff;
    onClose = null; vvOff = null;
    leaving = () => { leaving = null; root.hidden = true; root.inert = false; if (vv) vv(); if (done) done(); };
    const ms = now ? 0 : exitMs();
    if (ms > 0) { root.inert = true; hideT = setTimeout(leaving, ms + 20); } else leaving();
  }

  /** Beside the page or over it, while open (a window resized across the line): the trap and the role follow. */
  function setDocked(on) {
    if (!root || !shown || docked === !!on) return;
    docked = !!on; root.classList.toggle('is-docked', docked);
    setModal(!docked);
    announce(docked ? `${titleText} is beside the page` : `${titleText} is over the page`);
  }

  return {
    open, close, setDocked,
    isOpen: () => !!root && shown,
    isDocked: () => !!root && shown && docked,
    body: () => root && $('.drawer-body', panel),
    panel: () => panel,
  };
}

// the inspector every page uses
const main = makeDrawer();
export const open = main.open;
export const close = main.close;
export const isOpen = main.isOpen;
export const body = main.body;
