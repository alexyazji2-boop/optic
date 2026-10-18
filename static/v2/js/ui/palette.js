// Search and go: ⌘K or the top bar. Symbols come from /api/search; places are
// the navigation's own pages; recent symbols come first when the box is empty.
// A listbox with arrow keys, Enter to open and Escape to close.
import { html, render, $, $$, trapFocus } from '../core/dom.js';
import * as api from '../core/api.js';
import { GROUPS, SETTINGS, hrefFor } from '../nav.js';
import { recent } from '../core/store.js';

let root, input, list, untrap, opener, timer, seq = 0, items = [], sel = 0;

function ensure() {
  if (root) return;
  root = document.createElement('div');
  root.className = 'palette'; root.hidden = true;
  root.innerHTML = `<div class="palette-scrim"></div><div class="palette-panel" role="dialog" aria-modal="true" aria-label="Search Optic">
    <input type="search" role="combobox" aria-expanded="true" aria-controls="pal-list" aria-autocomplete="list" placeholder="Search a company, ticker or page" autocomplete="off" spellcheck="false">
    <div class="palette-list" id="pal-list" role="listbox" aria-label="Results"></div></div>`;
  document.body.appendChild(root);
  input = $('input', root); list = $('.palette-list', root);
  root.addEventListener('click', (e) => {
    if (e.target.classList.contains('palette-scrim')) close();
    const it = e.target.closest('.palette-item');
    if (it) choose(Number(it.dataset.v2Idx));
  });
  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => paint(input.value.trim()), 120); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
    else if (e.key === 'Enter') { e.preventDefault(); choose(sel); }
  });
}

const places = () => [...GROUPS.filter((g) => !g.symbol && !g.owner && !g.feature).flatMap((g) => g.pages.map((p) => ({ kind: 'place', label: p.label, sub: g.label === p.label ? (p.v2 ? '' : 'Opens in the current app') : `${g.label}${p.v2 ? '' : ', opens in the current app'}`, href: hrefFor(p.view) }))),
  { kind: 'place', label: SETTINGS.label, sub: 'Opens in the current app', href: hrefFor('settings') }];

async function paint(q) {
  const my = ++seq;
  let out = [];
  if (!q) {
    out = recent().map((s) => ({ kind: 'symbol', label: s, sub: 'Recent', href: `#/${s}` }));
    out.push(...places().slice(0, 6));
  } else {
    const ql = q.toLowerCase();
    const pl = places().filter((p) => p.label.toLowerCase().includes(ql));
    out = pl;
    if (/^[A-Za-z0-9.^=-]{1,12}$/.test(q)) out.unshift({ kind: 'symbol', label: q.toUpperCase(), sub: 'Open this symbol', href: `#/${q.toUpperCase()}` });
    draw(out);
    try {
      const r = await api.get(`/api/search?q=${encodeURIComponent(q)}&limit=7`, { ttl: 300000, timeout: 8000 });
      if (my !== seq) return;
      const syms = ((r && r.results) || []).map((x) => ({ kind: 'symbol', label: x.symbol, sub: x.name || x.exchange || '', href: `#/${x.symbol}` }));
      const seen = new Set(syms.map((s) => s.label));
      out = [...syms, ...out.filter((o) => !(o.kind === 'symbol' && seen.has(o.label)))];
    } catch (e) { /* the places and the typed symbol still work */ }
  }
  if (my === seq) draw(out);
}

function draw(out) {
  items = out; sel = 0;
  render(list, out.length ? out.map((it, i) => html`<button type="button" class="palette-item" role="option" id="pal-${i}" data-v2-idx="${i}" aria-selected="${i === 0}"><span>${it.kind === 'symbol' ? html`<b class="tick">${it.label}</b>` : it.label}</span><small>${it.sub}</small></button>`)
    : html`<p class="quiet">Nothing matches. Try a ticker such as AAPL.</p>`);
  input.setAttribute('aria-activedescendant', out.length ? 'pal-0' : '');
}

function move(d) {
  if (!items.length) return;
  sel = (sel + d + items.length) % items.length;
  $$('.palette-item', list).forEach((b, i) => b.setAttribute('aria-selected', String(i === sel)));
  input.setAttribute('aria-activedescendant', 'pal-' + sel);
  const b = $(`#pal-${sel}`, list); if (b) b.scrollIntoView({ block: 'nearest' });
}

function choose(i) {
  const it = items[i]; if (!it) return;
  close({ silent: true });
  if (it.href.startsWith('/')) location.href = it.href; else location.hash = it.href;
}

export function open(from) {
  ensure();
  opener = from || document.activeElement;
  root.hidden = false; input.value = '';
  paint('');
  untrap = trapFocus($('.palette-panel', root), () => close());
  input.focus();
}
export function close({ silent } = {}) {
  if (!root || root.hidden) return;
  root.hidden = true; if (untrap) untrap();
  if (!silent && opener && document.contains(opener)) opener.focus();
}
export const isOpen = () => !!root && !root.hidden;
