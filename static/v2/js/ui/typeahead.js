// Ticker suggestions under a symbol box (Classic parity B8.10; Classic app.js attachTypeahead): Optic's own search
// (/api/search) as the reader types, the typed text in bold in each symbol and name, arrow keys to move, Enter to
// take the highlighted one, Escape to close. Enter with nothing highlighted takes the one company whose name the
// reader typed ("apple" is AAPL), never a symbol typed as itself (F, AI, ^GSPC, BRK-B). Classic's logos came from two
// outside services keyed by the symbol, so every symbol typed went to them; v2 shows no outside logos anywhere, and
// these rows carry the symbol, the name and whether it is a fund.
//
// Delegated from the page's root, so a page that redraws its boxes keeps it: one list at a time, under the box that
// has focus, and gone when focus leaves it. A box opts in with data-v2-ta.
import * as api from '../core/api.js';
import { esc } from '../core/format.js';

export const DEBOUNCE_MS = 160;

/** Which suggestion an Enter with nothing highlighted means, or -1 for "the typed text": only a company name, and
 *  only once the list answered for exactly what is in the box. */
export function typedNamePick(items, listedFor, typed) {
  const q = String(typed || '').trim();
  if (!q || !items || !items.length || q !== listedFor) return -1;
  if (/[\^=.\-]/.test(q)) return -1;
  const upper = q.toUpperCase();
  if (items.some((r) => String(r.symbol || '').toUpperCase() === upper)) return -1;
  const lower = q.toLowerCase();
  return items.findIndex((r) => String(r.name || '').toLowerCase().includes(lower));
}
/** The text with the first match of the query in bold, escaped. */
export function marked(text, query) {
  const t = String(text || ''), q = String(query || '').trim();
  const at = q ? t.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (at < 0) return esc(t);
  return `${esc(t.slice(0, at))}<b>${esc(t.slice(at, at + q.length))}</b>${esc(t.slice(at + q.length))}`;
}

let uid = 0;
export function wire(root, onChoose) {
  const S = { input: null, list: null, items: [], active: -1, timer: null, listedFor: '', seq: 0 };
  const close = () => {
    clearTimeout(S.timer);
    if (S.list) S.list.remove();
    if (S.input) { S.input.setAttribute('aria-expanded', 'false'); S.input.removeAttribute('aria-activedescendant'); }
    S.list = null; S.items = []; S.active = -1;
  };
  const paint = () => {
    const input = S.input; if (!input || !input.isConnected) { close(); return; }
    if (!S.items.length) { close(); return; }
    if (!S.list || !S.list.isConnected) {
      S.list = document.createElement('ul');
      S.list.className = 'ta-list'; S.list.id = input.getAttribute('aria-controls') || `ta-${(uid += 1)}`; S.list.setAttribute('role', 'listbox');
      S.list.setAttribute('aria-label', 'Suggestions');
      const host = input.closest('[data-v2-ta-host]') || input.parentElement;
      host.classList.add('ta-host'); host.appendChild(S.list);
      input.setAttribute('aria-controls', S.list.id);
    }
    S.list.innerHTML = S.items.map((r, i) => `<li role="option" id="${S.list.id}-${i}" aria-selected="${i === S.active}" class="${i === S.active ? 'on' : ''}" data-ta-i="${i}">
      <span class="ta-sym">${marked(r.symbol, S.listedFor)}</span><span class="ta-name">${marked(r.name, S.listedFor)}</span>${r.etf ? '<span class="ta-tag">Fund</span>' : ''}</li>`).join('');
    input.setAttribute('aria-expanded', 'true');
    // kept on screen: a box at the right of a phone row opens its list leftward as far as it needs
    S.list.style.left = ''; const lr = S.list.getBoundingClientRect(), vw = document.documentElement.clientWidth, hl = S.list.parentElement.getBoundingClientRect().left;
    if (lr.right > vw - 12) S.list.style.left = `${Math.max(12 - hl, vw - 12 - lr.width - hl)}px`;
    if (S.active >= 0) { input.setAttribute('aria-activedescendant', `${S.list.id}-${S.active}`); const on = S.list.querySelector('.on'); if (on) on.scrollIntoView({ block: 'nearest' }); }
    else input.removeAttribute('aria-activedescendant');
  };
  const choose = (i) => {
    const pick = S.items[i], input = S.input; if (!pick || !input) return;
    input.value = pick.symbol; close();
    onChoose(pick, input);
  };
  root.addEventListener('input', (e) => {
    const input = e.target.closest && e.target.closest('[data-v2-ta]'); if (!input) return;
    if (S.input !== input) { close(); S.input = input; input.setAttribute('role', 'combobox'); input.setAttribute('aria-autocomplete', 'list'); }
    const q = input.value.trim(); clearTimeout(S.timer);
    if (!q) { close(); return; }
    const my = (S.seq += 1);
    S.timer = setTimeout(async () => {
      try {
        const r = await api.get(`/api/search?q=${encodeURIComponent(q)}&limit=10`, { ttl: 60000, timeout: 8000 });
        if (my !== S.seq || S.input !== input || input.value.trim() !== q || document.activeElement !== input) return;   // a later keystroke, or focus moved on
        S.items = ((r && r.results) || []).slice(0, 10); S.active = -1; S.listedFor = q; paint();
      } catch (err) { if (my === S.seq) close(); }   // suggestions are optional; the box still takes what is typed
    }, DEBOUNCE_MS);
  });
  root.addEventListener('keydown', (e) => {
    const input = e.target.closest && e.target.closest('[data-v2-ta]'); if (!input || input !== S.input) return;
    const n = S.items.length;
    if (e.key === 'ArrowDown' && n) { e.preventDefault(); S.active = (S.active + 1) % n; paint(); return; }
    if (e.key === 'ArrowUp' && n) { e.preventDefault(); S.active = (S.active - 1 + n) % n; paint(); return; }
    if (e.key === 'Escape' && S.list) { e.preventDefault(); e.stopPropagation(); close(); return; }
    if (e.key === 'Enter') {
      const i = S.active >= 0 ? S.active : typedNamePick(S.items, S.listedFor, input.value);
      if (i >= 0) { e.preventDefault(); choose(i); } else close();   // otherwise the form takes what was typed
    }
  });
  root.addEventListener('mousedown', (e) => {
    const li = e.target.closest && e.target.closest('.ta-list [data-ta-i]'); if (!li) return;
    e.preventDefault();   // keep focus in the box
    choose(Number(li.dataset.taI));
  });
  root.addEventListener('focusout', (e) => { if (e.target === S.input) setTimeout(() => { if (document.activeElement !== S.input) close(); }, 120); });
  return { close };
}
