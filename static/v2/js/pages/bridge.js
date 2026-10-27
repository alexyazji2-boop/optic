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
    // a heading and a title of its own: with neither, a screen reader landed on nothing and the tab kept the
    // previous page's name (investor audit, 2026-10-27)
    render(main, html`<header class="page-head"><h1 class="t-display-m">Page not found</h1></header>
      <div class="state"><p class="t-h3">That address is not a page</p><p>Check the ticker, or search for the company.</p>
      <div class="cluster"><button type="button" class="btn btn-primary" data-v2-open-palette>Search</button><a class="btn" href="#/">Go to Home</a></div></div>`);
    document.title = 'Page not found, Optic';
    return;
  }
  render(main, html`<header class="page-head">${g && g.symbol && route.symbol ? html`<p class="name"><b class="tick">${route.symbol}</b></p>` : ''}
      <h1 class="t-display-m">${label}</h1>${g ? groupTabs(g.id, p.view, route.symbol) : ''}</header>
    <div class="state bridge"><p class="t-h3">${label} is in the classic app</p>
      <p>It opens there, with the same account and data.</p>
      <a class="btn btn-primary" href="${href}">Open ${label} ${icon('out')}</a></div>`);
  document.title = `${label}, Optic`;
}
export { render_ as render };
export function dispose() {}
