// The reader's unread alert count, for the top bar's bell and the phone bar's Watchlist tab (the classic app's
// paintWatchHitBadge). Only the reader's own watches, so only signed in: a guest's watches live in the browser
// and are checked while the Alerts page is open. Every two minutes through the trading day, ten outside it,
// paused while the tab is hidden (core/poll.js); Alerts asks again as soon as it marks anything seen.
import * as api from './api.js';
import { poll } from './poll.js';
import { state } from './store.js';

let loop = null, sink = () => {};
export function startUnread(onCount) {
  sink = onCount;
  if (loop) loop.stop();
  loop = poll(async (current) => {
    if (!state.user) { sink(0); return; }
    const r = await api.get('/api/watches/hits?limit=1', { ttl: 0, force: true });
    if (current()) sink((r && r.unseen) || 0);
  }, { every: 120000, closed: 600000 });
  loop.now();
}
export function refreshUnread() { if (loop) loop.now(); }
