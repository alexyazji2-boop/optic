// An in-page tab set for "the rest, one step away": a row of tabs over one
// panel. Arrow keys move between tabs (roving tabindex), Home and End jump,
// and the panel is labelled by its tab. Panels render lazily on selection.
import { html, render, $, $$ } from '../core/dom.js';

let seq = 0;

/** items: [{id, label, render: () => tpl, mount?: (panel) => void}] */
export function tabset(items, { label, selected = 0 } = {}) {
  const id = 'ts' + (++seq);
  return {
    id,
    html: html`<div class="tabset-wrap" data-v2-tabset="${id}">
      <div class="tabset" role="tablist" aria-label="${label || 'More'}">${items.map((it, i) => html`<button type="button" role="tab" id="${id}-t${i}" aria-controls="${id}-p" aria-selected="${i === selected}" tabindex="${i === selected ? 0 : -1}">${it.label}</button>`)}</div>
      <div class="tabpanel" id="${id}-p" role="tabpanel" aria-labelledby="${id}-t${selected}" tabindex="0"></div></div>`,
    wire(root, onSelect) {
      const box = $(`[data-v2-tabset="${id}"]`, root);
      if (!box) return;
      const tabs = $$('[role=tab]', box), panel = $('.tabpanel', box);
      const sel = (i, focus) => {
        tabs.forEach((t, j) => { t.setAttribute('aria-selected', String(i === j)); t.tabIndex = i === j ? 0 : -1; });
        panel.setAttribute('aria-labelledby', `${id}-t${i}`);
        render(panel, items[i].render());
        if (items[i].mount) items[i].mount(panel);
        if (focus) tabs[i].focus();
        if (onSelect) onSelect(i);
      };
      tabs.forEach((t, i) => {
        t.addEventListener('click', () => sel(i));
        t.addEventListener('keydown', (e) => {
          const n = tabs.length;
          const to = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i - 1 + n) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1;
          if (to >= 0) { e.preventDefault(); sel(to, true); }
        });
      });
      sel(selected);
    },
  };
}
