// One refresh loop per page, under the owner's rules (2026-10-21): a refresh never resets what the reader is
// doing (scroll, filters, folds, chart position, drafts: each page repaints quietly and only what changed), never
// overlaps itself, drops a response that is no longer the current one, pauses while the tab is hidden and catches
// up once on return, and slows outside the trading day. The classic app refreshed every 20 s in session.
//
//   const p = poll(async (current) => { const d = await api.get(...); if (!current()) return; ...apply quietly... },
//                  { every: 20000, closed: 300000 });
//   p.stop();          // in the page's dispose()
//   p.now();           // run once now (after an action), within the same rules
//
// `current()` is false once a newer run has started or the loop was stopped: the page applies nothing then.

/** Minutes since midnight in New York, and whether the day is a weekday. */
function etClock(now = new Date()) {
  try {
    const p = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric', minute: 'numeric', hour12: false }).formatToParts(now);
    const g = (t) => (p.find((x) => x.type === t) || {}).value;
    return { minutes: (Number(g('hour')) % 24) * 60 + Number(g('minute')), weekday: !['Sat', 'Sun'].includes(g('weekday')) };
  } catch (e) { return { minutes: now.getHours() * 60 + now.getMinutes(), weekday: ![0, 6].includes(now.getDay()) }; }
}

/** The trading day, pre-market through after hours (4:00 to 20:00 New York, weekdays). A holiday is not known
 *  here, so it is treated as a trading day: the cost is a few cheap, cached requests, never a stale claim, because
 *  pages say how fresh their figures are from the figures' own times, not from this. */
export function inTradingDay(now = new Date()) {
  const c = etClock(now);
  return c.weekday && c.minutes >= 240 && c.minutes < 1200;
}

export function poll(run, { every = 20000, closed = 300000, inSession = inTradingDay } = {}) {
  let timer = null, seq = 0, busy = false, stopped = false, owed = false;
  const delay = () => (inSession() ? every : closed);
  const schedule = () => { clearTimeout(timer); if (!stopped) timer = setTimeout(tick, delay()); };
  async function tick() {
    if (stopped) return;
    if (document.hidden) { owed = true; return; }          // no timer while hidden; one catch-up on return
    if (busy) { schedule(); return; }                      // never two at once
    busy = true; const my = ++seq;
    try { await run(() => !stopped && my === seq); } catch (e) { /* a failed refresh keeps what is on screen */ }
    busy = false;
    schedule();
  }
  const onVisible = () => { if (!document.hidden && owed && !stopped) { owed = false; tick(); } };
  document.addEventListener('visibilitychange', onVisible);
  schedule();
  return {
    stop() { stopped = true; clearTimeout(timer); document.removeEventListener('visibilitychange', onVisible); },
    now() { if (!stopped) { clearTimeout(timer); tick(); } },
  };
}
