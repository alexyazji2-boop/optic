// In-page tabs for a group's pages. With the rail listing groups only, these
// are the single place a group's pages are listed (owner's point 1).
import { html } from '../core/dom.js';
import { GROUPS, hrefFor } from '../nav.js';
import { icon } from '../ui/icons.js';

export function groupTabs(groupId, current, symbol) {
  const g = GROUPS.find((x) => x.id === groupId);
  if (!g || g.pages.length < 2) return '';
  return html`<nav class="tabs" aria-label="${g.label}">${g.pages.map((p) => html`<a href="${hrefFor(p.view, symbol)}" ${p.view === current ? html`aria-current="page"` : ''}>${p.label}${p.v2 ? '' : html`<span class="legacy-mark" aria-hidden="true">${icon('out')}</span><span class="sr">, opens in the current app</span>`}</a>`)}</nav>`;
}
