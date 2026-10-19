// In-page tabs for a group's pages. With the rail listing groups only, these
// are the single place a group's pages are listed (owner's point 1).
import { html } from '../core/dom.js';
import { GROUPS, hrefFor } from '../nav.js';
import { icon } from '../ui/icons.js';

// On a phone a row of tabs was clipped at the screen's edge with nothing to say more were there (owner,
// 2026-10-19: "an obvious overflow control or view selector instead of clipped labels"). Every tab list
// carries a selector that names the view the reader is on; CSS shows it instead of the row under 640 px.
// app.js navigates on its change.
export function tabSelect(label, pages, current, symbol) {
  const cur = pages.find((p) => p.view === current);
  return html`<label class="tabsel"><span class="tabsel-k">${label}</span><select data-v2-tabsel aria-label="${label} view">${pages.map((p) => html`<option value="${hrefFor(p.view, symbol)}" ${p.view === current ? 'selected' : ''}>${p.label}${p.v2 ? '' : ' (current app)'}</option>`)}${cur ? '' : html`<option value="" selected disabled>Choose a view</option>`}</select></label>`;
}

export function tabLinks(pages, current, symbol) {
  return pages.map((p) => html`<a href="${hrefFor(p.view, symbol)}" ${p.view === current ? html`aria-current="page"` : ''}>${p.label}${p.v2 ? '' : html`<span class="legacy-mark" aria-hidden="true">${icon('out')}</span><span class="sr">, opens in the current app</span>`}</a>`);
}

export function groupTabs(groupId, current, symbol) {
  const g = GROUPS.find((x) => x.id === groupId);
  if (!g || g.pages.length < 2) return '';
  return html`<nav class="tabs" aria-label="${g.label}">${tabSelect(g.label, g.pages, current, symbol)}${tabLinks(g.pages, current, symbol)}</nav>`;
}

// A destination's heading is the name the reader chose in the rail or the phone bar, and its tabs name
// the view within it (owner's brief, item 11: Markets opened on a page headed "Read", Discover on one
// headed "Explore").
export function sectionHead(groupId, current, symbol) {
  const g = GROUPS.find((x) => x.id === groupId);
  const p = g && g.pages.find((x) => x.view === current);
  return html`<h1 class="t-display-m">${g ? g.label : ''}${p && g.pages.length > 1 ? html`<span class="sr">, ${p.label}</span>` : ''}</h1>${groupTabs(groupId, current, symbol)}`;
}
