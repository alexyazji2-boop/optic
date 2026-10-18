// A page that has not moved yet. It keeps the group's tabs, says plainly that
// this page is still in the current app, and opens it there at the same
// address. Every classic page stays reachable from the new frontend this way.
import { html, render } from '../core/dom.js';
import { CLASSIC } from '../core/classic.js';
import { groupOf, pageOf, hrefFor, SETTINGS } from '../nav.js';
import { icon } from '../ui/icons.js';
import { groupTabs } from './tabs.js';

export function render_(main, route) {
  const g = route.view === 'settings' ? null : groupOf(route.view);
  const p = route.view === 'settings' ? SETTINGS : pageOf(route.view);
  const label = p ? p.label : 'This page';
  let href = p ? hrefFor(p.view, route.symbol) : CLASSIC;
  if (route.view === 'brokerage' && route.section) href = `${CLASSIC}#/brokerage/${route.section}`;
  if (route.view === 'instrument') href = `${CLASSIC}#/instrument/${encodeURIComponent(route.symbol || '')}`;
  if (route.view === 'notfound') {
    render(main, html`<div class="state"><p class="t-h3">That address is not a page</p><p>Check the ticker, or search for the company.</p><button type="button" class="btn" data-v2-open-palette>Search</button></div>`);
    return;
  }
  render(main, html`<header class="page-head">${g && g.symbol && route.symbol ? html`<p class="name"><b class="tick">${route.symbol}</b></p>` : ''}
      <h1 class="t-display-m">${label}</h1>${g ? groupTabs(g.id, p.view, route.symbol) : ''}</header>
    <div class="state bridge"><p class="t-h3">${label} is still in the current app</p>
      <p>This page has not moved to the new design yet. It works as before at the same address.</p>
      <a class="btn btn-primary" href="${href}">Open ${label} ${icon('out')}</a></div>`);
  document.title = `${label}, Optic`;
}
export { render_ as render };
export function dispose() {}
