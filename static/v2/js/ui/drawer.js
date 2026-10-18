// The inspector: one drawer for every object (an answer's evidence, an event,
// Milo). A modal dialog: focus moves to its title, Tab stays inside, Escape or
// the close button shuts it, and focus goes back to what opened it. On phones
// it rises as a sheet.
import { $, html, render, trapFocus, announce } from '../core/dom.js';
import { icon } from './icons.js';

let root, panel, from, untrap, onClose, sticky = false;

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
export function open({ kicker = '', title, body, opener, mount, closed, keep = false }) {
  ensure();
  if (!root.hidden) close({ silent: true, force: true });
  sticky = keep;
  from = opener || document.activeElement;
  onClose = closed;
  render(panel, html`<header class="drawer-head"><div><p class="drawer-kicker">${kicker}</p><h2 id="drawer-title" tabindex="-1">${title}</h2></div>
    <button type="button" class="icon-btn" data-v2-close aria-label="Close">${icon('close')}</button></header>
    <div class="drawer-body">${body}</div>`);
  root.hidden = false;
  document.body.classList.add('drawer-open');
  if (from && from.setAttribute && from.hasAttribute('aria-expanded')) from.setAttribute('aria-expanded', 'true');
  requestAnimationFrame(() => { root.classList.add('is-open'); $('#drawer-title', panel).focus(); });
  untrap = trapFocus(panel, () => close());
  if (mount) mount($('.drawer-body', panel));
  announce(`${title} opened`);
}

export function close({ silent, route, force } = {}) {
  if (!root || root.hidden) return;
  if (sticky && route && !force) return;
  sticky = false;
  root.classList.remove('is-open');
  root.hidden = true;
  document.body.classList.remove('drawer-open');
  if (untrap) untrap();
  if (from && from.setAttribute && from.hasAttribute('aria-expanded')) from.setAttribute('aria-expanded', 'false');
  if (onClose) onClose();
  if (!silent && from && document.contains(from)) from.focus();
  from = null;
}

export const isOpen = () => !!root && !root.hidden;
export const body = () => root && $('.drawer-body', panel);
