// Show more, per panel (2026-11-09). On Home and a company's Overview the level decides which panels appear; a panel
// the level leaves out, or trims, is never gone: it is listed with one Show more, which opens that panel only and
// leaves the level as it is. What was opened stays open until the reader presses its Show less, the level changes or
// the reader leaves the screen. Show less closes that one panel only: with Show more alone, the only way to put a panel
// back was to change the level and back, which closed everything else that was open as well (round-one corrections,
// 2026-11-10).
import { html, reducedMotion } from '../core/dom.js';

/** A screen's set of panels opened past its level. Cleared when the level changes; one panel leaves it by Show less. */
export function expansions() {
  const open = new Set();
  return { has: (id) => open.has(id), add: (id) => open.add(id), remove: (id) => open.delete(id), clear: () => open.clear(), list: () => [...open] };
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

/** One Show less button, on a panel Show more opened: it closes that panel only, the panel goes back to the list above
 *  and focus goes back to its Show more. The same small plain button as Show more, so the pair reads as one control
 *  and neither competes with the screen's one gold action. */
export function lessButton(id, title, { label = 'Show less' } = {}) {
  return html`<button type="button" class="btn btn-sm" data-v2-show-less="${id}" aria-expanded="true" aria-label="${label}: ${title}">${label}</button>`;
}

/** Bring what Show more opened into view, then focus it. `target` is scrolled to (a panel or its heading); `focus`,
 *  if given, takes focus instead (Home focuses the panel's body under the heading it scrolls to).
 *  Focus with preventScroll: false (and, on the Overview, the swap keeping its place) jumped the page in one frame: on
 *  AAPL at Beginner, 1440 x 900, Show more on the advanced analysis moved it 1,335 px between two frames (gauntlet, 2026-11-10; "the browser jumped"). So the page
 *  scrolls smoothly (at once under Reduce motion, the system's or Settings'), the heading stopping under the sticky
 *  stack by html's scroll-padding-top (components.css), and focus moves without a second scroll. Already in view
 *  below the stack, nothing moves. */
export function revealOpened(target, focus = target) {
  if (!target) return;
  const pad = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0;
  const r = target.getBoundingClientRect();
  if (r.top < pad || r.top > window.innerHeight - 48) target.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' });
  if (focus) focus.focus({ preventScroll: true });
}
