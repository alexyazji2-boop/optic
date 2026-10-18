// One toast at a time, announced politely. An action (Undo) keeps it up longer.
import { announce } from '../core/dom.js';

let el, timer;
export function toast(msg, { action, run, kind } = {}) {
  if (!el) {
    el = document.createElement('div');
    el.className = 'toast';
    document.body.appendChild(el);
  }
  clearTimeout(timer);
  el.textContent = msg;
  el.dataset.kind = kind || '';
  if (action && run) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'toast-act'; b.textContent = action;
    b.addEventListener('click', () => { hide(); run(); });
    el.append(' ', b);
  }
  el.classList.add('show');
  announce(msg);
  timer = setTimeout(hide, action ? 10000 : 5000);
}
function hide() { if (el) el.classList.remove('show'); }
