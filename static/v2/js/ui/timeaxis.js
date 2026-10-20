// Where a moment sits on a chart's bars, and back. A drawing keeps its points as {t, p}; drawn on
// another bar size it has to land on the same day and the same moment, not on the nearest bar:
//   - a daily point (a date, stored at midnight or noon UTC as the classic app stores them) on daily bars
//     is its own date's bar; on intraday bars it is the first bar of that trading day;
//   - an intraday point on daily or weekly bars is its New York trading date's bar;
//   - between bars it is interpolated, and before the first or after the last bar it is extrapolated by
//     the bars' own spacing (trading days, not calendar days, on daily bars), so a trend line keeps its
//     slope whatever window is loaded instead of being clamped to the edge.
// The classic chart's wsTimeAxis does the same (static/app.js); the 2026-10-20 chart audit found v2
// snapping to the nearest bar, which put a Tuesday point on Wednesday and changed slopes with the window.
const DAY = 86400000;
const nyDate = (t) => { try { return new Date(t).toLocaleDateString('en-CA', { timeZone: 'America/New_York' }); } catch (e) { return new Date(t).toISOString().slice(0, 10); } };
const utcDate = (t) => new Date(t).toISOString().slice(0, 10);
/** A point that names a date rather than a moment: midnight or noon UTC exactly. */
export const isDateStamp = (t) => { const r = ((t % DAY) + DAY) % DAY; return r === 0 || r === DAY / 2; };

export function makeAxis(bars, intraday) {
  const N = bars.length, ts = bars.map((b) => b.t);
  const gaps = []; for (let i = 1; i < N; i += 1) { const g = ts[i] - ts[i - 1]; if (g > 0) gaps.push(g); }
  gaps.sort((a, b) => a - b);
  const step = gaps.length ? gaps[Math.floor(gaps.length / 2)] : DAY;
  // past the ends, a daily chart counts trading days: five for every seven calendar days
  const per = !intraday && step >= DAY * 0.9 && step <= DAY * 1.1 ? (5 / 7) : 1;
  const keys = intraday ? ts.map(nyDate) : ts.map(utcDate);
  const firstOf = (key) => { let lo = 0, hi = N; while (lo < hi) { const m = (lo + hi) >> 1; if (keys[m] < key) lo = m + 1; else hi = m; } return lo; };
  const floorOf = (t) => { let lo = 0, hi = N - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (ts[m] <= t) lo = m; else hi = m - 1; } return lo; };
  function byTime(t) {
    if (!N) return 0;
    if (t <= ts[0]) return (t - ts[0]) / step * per;
    if (t >= ts[N - 1]) return N - 1 + (t - ts[N - 1]) / step * per;
    const i = floorOf(t), span = ts[i + 1] - ts[i];
    return i + (span > 0 ? (t - ts[i]) / span : 0);
  }
  /** The fractional bar index of a moment. */
  function f(t) {
    if (!N || !Number.isFinite(t)) return 0;
    if (!intraday) {
      const key = isDateStamp(t) ? utcDate(t) : nyDate(t);
      const i = firstOf(key);
      if (i < N && keys[i] === key) return i;
      return byTime(Date.parse(`${key}T00:00:00Z`));
    }
    if (isDateStamp(t)) {
      const key = utcDate(t), i = firstOf(key);
      if (i < N && keys[i] === key) return i;
    }
    return byTime(t);
  }
  /** The moment at a fractional bar index (the inverse of f, for moving a drawing by bars). */
  function t(fi) {
    if (!N) return 0;
    if (fi <= 0) return ts[0] + fi / per * step;
    if (fi >= N - 1) return ts[N - 1] + (fi - (N - 1)) / per * step;
    const i = Math.floor(fi), frac = fi - i;
    return frac ? ts[i] + frac * (ts[i + 1] - ts[i]) : ts[i];
  }
  /** The bar a dated event belongs to, or -1 when it falls outside the bars (a report still to come). */
  function bar(tm) { const x = f(tm); return x < -0.5 || x > N - 0.5 ? -1 : Math.round(x); }
  return { f, t, bar, step, N };
}
