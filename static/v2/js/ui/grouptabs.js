// Grouped secondary tabs (owner's brief, 2026-10-19, item 13). A row of ten or twelve tabs ran off the
// screen; these put the views in a few named groups, and a group's own views in a row of chips under it.
// The groups are a tab list (arrow keys, Home and End move between them); the chips are pressed buttons.
// The selected view renders lazily, as in ui/tabset.js.
import { html, render, $ } from '../core/dom.js';

let seq = 0;

/** groups: [{label, items: [{label, render: () => tpl, mount?: (el) => void}]}]; state: {g, s: {}} kept by the page */
export function groupedTabs(groups, { label, state }) {
  const id = 'gt' + (++seq);
  const st = state || { g: 0, s: {} };
  if (!groups[st.g]) st.g = 0;
  const sub = () => Math.min(st.s[st.g] || 0, groups[st.g].items.length - 1);
  const frame = () => {
    const g = groups[st.g], j = sub();
    return html`<div class="gtabs" role="tablist" aria-label="${label}" style="--n:${groups.length}">${groups.map((x, i) => html`<button type="button" role="tab" id="${id}-t${i}" aria-controls="${id}-p" aria-selected="${i === st.g}" tabindex="${i === st.g ? 0 : -1}" data-gt="${i}">${x.label}</button>`)}</div>
      <div class="gpanel" id="${id}-p" role="tabpanel" aria-labelledby="${id}-t${st.g}">
        ${g.items.length > 1 ? html`<div class="gsub" role="group" aria-label="${g.label}">${g.items.map((it, k) => html`<button type="button" class="chip" aria-pressed="${k === j}" data-gs="${k}">${it.label}</button>`)}</div>` : ''}
        <div class="gbody"></div></div>`;
  };
  return {
    id,
    html: html`<div class="gtabs-wrap" data-v2-gtabs="${id}"></div>`,
    wire(root, onChange) {
      const box = $(`[data-v2-gtabs="${id}"]`, root);
      if (!box) return;
      const paint = (focus) => {
        render(box, frame());
        const it = groups[st.g].items[sub()];
        const b = $('.gbody', box);
        render(b, it.render());
        if (it.mount) it.mount(b);
        if (focus) { const f = $(focus, box); if (f) f.focus(); }
        if (onChange) onChange(st);
      };
      box.addEventListener('click', (e) => {
        const t = e.target.closest('[data-gt]'), c = e.target.closest('[data-gs]');
        if (t) { st.g = Number(t.dataset.gt); paint(); }
        else if (c) { st.s[st.g] = Number(c.dataset.gs); paint(`[data-gs="${c.dataset.gs}"]`); }
      });
      box.addEventListener('keydown', (e) => {
        const t = e.target.closest('[data-gt]');
        if (!t) return;
        const i = Number(t.dataset.gt), n = groups.length;
        const to = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i - 1 + n) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1;
        if (to >= 0) { e.preventDefault(); st.g = to; paint(`[data-gt="${to}"]`); }
      });
      paint();
    },
  };
}
