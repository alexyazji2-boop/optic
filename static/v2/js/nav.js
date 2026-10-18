// The navigation model. Names are the classic app's, word for word
// (NAV_GROUPS, SUB_LABELS and MOBILE_TABS in static/app.js); renaming any of
// them needs the owner's yes.
//
// One place for each level: the rail lists the groups, and the pages inside a
// group appear only as tabs at the top of that group's pages. The classic rail
// showed Dossier's seven pages in a fly-out and again as tabs; here they are
// tabs only.
//
// `v2` marks a page rebuilt in this frontend. Everything else opens in the
// classic app at the same address, so every section stays reachable while the
// migration runs. docs/frontend-v2/COVERAGE.md tracks the same list.

export const SECTIONS = { home: 'Research', security: 'Research', analyse: 'Research', market: 'Research', discover: 'Research', portfolio: 'Tracking', brokerage: 'Tracking', follow: 'Tracking', reports: 'Owner' };

export const GROUPS = [
  { id: 'home', label: 'Home', icon: 'home', pages: [{ view: 'home', label: 'Home', slug: '', v2: true }] },
  { id: 'security', label: 'Dossier', icon: 'dossier', symbol: true, pages: [
    { view: 'overview', label: 'Overview', slug: '', v2: true },
    { view: 'chart', label: 'Chart', slug: 'chart', v2: true },
    { view: 'swing', label: 'Options', slug: 'options', v2: true },
    { view: 'long', label: 'Investing', slug: 'investing', v2: true },
    { view: 'earnings', label: 'Earnings', slug: 'earnings', v2: true },
    { view: 'financials', label: 'Financials', slug: 'financials', v2: true },
    { view: 'news', label: 'News', slug: 'news', v2: true },
  ] },
  { id: 'analyse', label: 'Compare', icon: 'compare', pages: [{ view: 'compare', label: 'Compare', slug: 'compare' }] },
  { id: 'market', label: 'Markets', icon: 'markets', pages: [
    { view: 'brief', label: 'Read', slug: 'read' },
    { view: 'market', label: 'Macro', slug: 'macro' },
    { view: 'indices', label: 'Indices', slug: 'indices' },
  ] },
  { id: 'discover', label: 'Discover', icon: 'discover', pages: [
    { view: 'explore', label: 'Explore', slug: 'explore' },
    { view: 'scan', label: 'Scan', slug: 'scan' },
    { view: 'insiders', label: 'Insiders', slug: 'insiders' },
    { view: 'analysts', label: 'Analysts', slug: 'analysts' },
  ] },
  { id: 'portfolio', label: 'Positions', icon: 'positions', pages: [
    { view: 'tracker', label: 'Optic Portfolio', slug: 'portfolio' },
    { view: 'paper', label: 'Paper Desk', slug: 'paper' },
    { view: 'roth', label: 'Retirement', slug: 'retirement' },
  ] },
  { id: 'brokerage', label: 'Brokerage', icon: 'brokerage', feature: 'brokerage', pages: [{ view: 'brokerage', label: 'Brokerage', slug: 'brokerage' }] },
  { id: 'follow', label: 'Watchlist', icon: 'watchlist', pages: [
    { view: 'watchlist', label: 'Watchlist', slug: 'watchlist', v2: true },
    { view: 'alerts', label: 'Alerts', slug: 'alerts', v2: true },
  ] },
  { id: 'reports', label: 'Reports', icon: 'reports', owner: true, pages: [
    { view: 'reports', label: 'Problem Reports', slug: 'reports' },
    { view: 'usage', label: 'Claude usage', slug: 'usage' },
    { view: 'accounts', label: 'Accounts', slug: 'accounts' },
  ] },
];

export const SETTINGS = { view: 'settings', label: 'Settings', slug: 'settings', icon: 'settings' };

// The phone bar, as in the classic app.
export const MOBILE_TABS = [
  { label: 'Home', group: 'home', icon: 'home' },
  { label: 'Dossier', group: 'security', icon: 'dossier' },
  { label: 'Markets', group: 'market', icon: 'markets' },
  { label: 'Discover', group: 'discover', icon: 'discover' },
  { label: 'More', more: true, icon: 'more' },
];

export const groupOf = (view) => GROUPS.find((g) => g.pages.some((p) => p.view === view)) || null;
export const pageOf = (view) => { for (const g of GROUPS) { const p = g.pages.find((x) => x.view === view); if (p) return p; } return view === 'settings' ? SETTINGS : null; };

/** The address of a page, in v2 if it has moved, otherwise in the classic app. */
export function hrefFor(view, symbol) {
  const g = groupOf(view);
  const p = pageOf(view);
  if (!p) return '#/';
  if (g && g.symbol) {
    if (!symbol) return p.v2 ? '#/' : '/#/';
    return (p.v2 ? '#/' : '/#/') + encodeURIComponent(symbol) + (p.slug ? '/' + p.slug : '');
  }
  return (p.v2 ? '#/' : '/#/') + p.slug;
}

export function visibleGroups({ admin, brokerage }) {
  return GROUPS.filter((g) => (!g.owner || admin) && (!g.feature || (g.feature === 'brokerage' && brokerage)));
}
