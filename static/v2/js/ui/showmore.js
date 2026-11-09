// Show more, per panel (2026-11-09). On Home and a company's Overview the level decides which panels appear; a panel
// the level leaves out, or trims, is never gone: it is listed with one Show more, which opens that panel only and
// leaves the level as it is. What was opened stays open until the level changes or the reader leaves the screen.
import { html } from '../core/dom.js';

/** A screen's set of panels opened past its level. Cleared when the level changes. */
export function expansions() {
  const open = new Set();
  return { has: (id) => open.has(id), add: (id) => open.add(id), clear: () => open.clear(), list: () => [...open] };
}

/** The panels the level leaves out, each with Show more. `items` is [{id, title, blurb}]. */
export function moreList(items, { heading = 'More on this screen', sub = 'Each opens on its own; your level stays as it is.', screen = '' } = {}) {
  if (!items.length) return '';
  return html`<section class="sm" aria-labelledby="sm-h-${screen}" data-v2-sm="${screen}">
    <h2 class="sm-h" id="sm-h-${screen}">${heading}</h2><p class="sm-sub">${sub}</p>
    <ul class="sm-list">${items.map((x) => html`<li class="sm-stub" data-v2-sm-stub="${x.id}"><h3>${x.title}</h3>${x.blurb ? html`<p>${x.blurb}</p>` : ''}
      ${moreButton(x.id, x.title)}</li>`)}</ul>
  </section>`;
}

/** One Show more button: for a stub above, or inside a panel the level trims. */
export function moreButton(id, title, { label = 'Show more' } = {}) {
  return html`<button type="button" class="btn btn-sm" data-v2-show-more="${id}" aria-expanded="false" aria-label="${label}: ${title}">${label}</button>`;
}
