// Hash routes, using the classic app's addresses so a link means the same page
// in both: #/ Home, #/AAPL Overview, #/AAPL/options a Dossier tab, #/watchlist,
// #/alerts, and the other section slugs. #/signin is v2's own.
import { GROUPS, SETTINGS } from '../nav.js';

const SLUG_VIEW = {};
GROUPS.forEach((g) => { if (!g.symbol) g.pages.forEach((p) => { if (p.slug) SLUG_VIEW[p.slug] = p.view; }); });
SLUG_VIEW[SETTINGS.slug] = SETTINGS.view;
SLUG_VIEW.signin = 'signin';
SLUG_VIEW.terms = 'terms';       // the drafts in pages/legalpages.js (owner's checklist, 2026-10-19)
SLUG_VIEW.privacy = 'privacy';
SLUG_VIEW.instrument = 'instrument';
SLUG_VIEW.workspace = 'home';   // the workspace is Home (owner, 2026-10-18); old #/workspace links land there
SLUG_VIEW.dossier = 'dossierstart';   // Dossier with no company open (pages/dossierstart.js)
SLUG_VIEW.earnings = 'earningsweek';
SLUG_VIEW.research = 'saved';   // Saved research (Classic parity B4d): the account sheet, the palette and Milo link here   // the classic app's #/earnings, the week's reports (a ticker's own Earnings tab is #/SYM/earnings)
const TAB_VIEW = {};
GROUPS.find((g) => g.id === 'security').pages.forEach((p) => { TAB_VIEW[p.slug || ''] = p.view; });
const BROKERAGE_SECTIONS = ['overview', 'holdings', 'performance', 'events', 'connections'];

export function parse(hash = location.hash) {
  const raw = String(hash || '').replace(/^#\/?/, '');
  const [path, query = ''] = raw.split('?');
  // a hand-typed or truncated address ("#/%") must not stop the app from rendering
  const parts = path.split('/').filter(Boolean).map((s) => { try { return decodeURIComponent(s); } catch (e) { return s; } });
  const params = {};
  query.split('&').filter(Boolean).forEach((kv) => {
    const [k, v = ''] = kv.split('=');
    try { params[decodeURIComponent(k)] = decodeURIComponent(v.replace(/\+/g, ' ')); } catch (e) { /* a malformed pair is skipped */ }
  });
  if (!parts.length) return { view: 'home', params };
  const head = parts[0].toLowerCase();
  if (head === 'brokerage') return { view: 'brokerage', section: BROKERAGE_SECTIONS.includes(parts[1]) ? parts[1] : null, params };
  if (head === 'instrument') return { view: 'instrument', symbol: (parts[1] || '').toUpperCase(), params };
  if (SLUG_VIEW[head]) return { view: SLUG_VIEW[head], params };
  const symbol = parts[0].toUpperCase();
  if (!/^[A-Z0-9.^=-]{1,12}$/.test(symbol)) return { view: 'notfound', params };
  const tab = (parts[1] || '').toLowerCase();
  return { view: TAB_VIEW[tab] || 'overview', symbol, params };
}

const listeners = new Set();
export function onRoute(fn) { listeners.add(fn); }
export function go(hash) {
  if (location.hash === hash || (hash === '#/' && !location.hash)) { listeners.forEach((fn) => fn(parse(hash))); return; }
  location.hash = hash;
}
export function start() {
  window.addEventListener('hashchange', () => { const r = parse(); listeners.forEach((fn) => fn(r)); });
  const r = parse(); listeners.forEach((fn) => fn(r));
}
