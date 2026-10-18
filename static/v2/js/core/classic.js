// Where the classic app lives. Every v2 link to a page or tool that is still
// classic-only goes through this, so the switch-over (classic moving to
// /classic) changes one line. The server's index route sets it on the page as
// data-classic on every v2 page; /classic always serves the classic app.
const fromPage = typeof document !== 'undefined' && document.documentElement && document.documentElement.dataset.classic;
export const CLASSIC = fromPage || '/classic';
/** A classic address for a hash route: classicHref('#/AAPL/chart'). */
export const classicHref = (hash = '#/') => `${CLASSIC}${String(hash).startsWith('#') ? hash : `#/${hash}`}`;
