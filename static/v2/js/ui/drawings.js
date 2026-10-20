// The geometry of the chart's drawings (C10), in bar-index and price space, for ui/pricechart.js to draw. Ported
// from the classic app's wsRenderDrawings (static/app.js) so a drawing made in one app reads the same in the
// other: the stored form is the classic one, {kind, points: [{t, p}]}, in optic.chart.drawings.v2.
//   channel: two parallel lines, the base through the first two points and a copy through the third;
//   fibext: levels projected from the third point by multiples of the first move;
//   pitchfork: Andrews, a handle from the first pivot to the middle of the other two and three tines;
//   arrow: a line with a head;  ruler: the move between two points;  rr: entry, stop and target;
//   position: entry, stop and a third point setting the risk budget, $100 for each dollar from the entry.

/** How many points each tool needs (the classic TOOL_POINTS). */
export const TOOL_POINTS = { trend: 2, ray: 2, hline: 1, vline: 1, channel: 3, rect: 2, fibdraw: 2, fibext: 3, pitchfork: 3, arrow: 2, text: 1, ruler: 2, rr: 3, position: 3 };
export const FIB_EXT = [0, 0.618, 1, 1.272, 1.618, 2, 2.618];
/** The classic snap radius: within 7 px of a bar's open, high, low or close, a point goes to it. */
export const SNAP_PX = 7;

/** Two parallel lines from the first point's bar to `last`: the base through a and b, its copy through c. */
export function channel(a, b, c, last) {
  const slope = b.i === a.i ? 0 : (b.p - a.p) / (b.i - a.i), at = (i, q) => q.p + slope * (i - q.i);
  return [a, c].map((q) => ({ i1: a.i, p1: at(a.i, q), i2: last, p2: at(last, q) }));
}
/** The extension's levels: from c by multiples of the a-to-b move. */
export function fibExt(a, b, c) {
  const span = b.p - a.p;
  return FIB_EXT.map((r) => ({ r, price: c.p + span * r }));
}
/** The handle (a to the middle of b and c) and the three tines (through the middle, b and c) to `last`. */
export function pitchfork(a, b, c, last) {
  const mid = { i: (b.i + c.i) / 2, p: (b.p + c.p) / 2 }, slope = mid.i === a.i ? 0 : (mid.p - a.p) / (mid.i - a.i);
  return { handle: { i1: a.i, p1: a.p, i2: mid.i, p2: mid.p }, tines: [mid, b, c].map((q) => ({ i1: q.i, p1: q.p, i2: last, p2: q.p + slope * (last - q.i) })) };
}
/** Risk and reward in price, and the reward as a multiple of the risk (null with no risk). */
export function riskReward(entry, stop, target) {
  const risk = Math.abs(entry.p - stop.p), reward = Math.abs(target.p - entry.p);
  return { risk, reward, r: risk ? reward / risk : null };
}
/** Shares for the budget: the third point's distance from the entry is the budget at $100 a dollar. */
export function positionSize(entry, stop, budgetPt) {
  const perShare = Math.abs(entry.p - stop.p), budget = Math.abs(budgetPt.p - entry.p) * 100;
  return { perShare, budget, shares: perShare ? Math.floor(budget / perShare) : 0 };
}
/** The move between two points: in price, in percent of the first, and in bars. */
export function measure(a, b) {
  return { change: b.p - a.p, pct: a.p ? ((b.p - a.p) / a.p) * 100 : 0, bars: Math.round(Math.abs(b.i - a.i)) };
}
/**
 * A price snapped to the bar's open, high, low or close when one is within SNAP_PX on screen: {price, field},
 * field null when none was close enough and the price is the pointer's own.
 */
export function snap(bar, price, yOf, px = SNAP_PX) {
  let best = null, bestPx = Infinity;
  [['H', bar.h], ['L', bar.l], ['C', bar.c], ['O', bar.o]].forEach(([field, v]) => {
    if (!Number.isFinite(v)) return;
    const d = Math.abs(yOf(v) - yOf(price));
    if (d < bestPx) { bestPx = d; best = { price: v, field }; }
  });
  return best && bestPx <= px ? best : { price, field: null };
}
/** A drawing moved by `di` bars and `dp` in price; points stay on bars, held at the ends of the series. */
/** A drawing moved by `di` bars and `dp` in price. Positions go through the chart's time axis (ui/timeaxis.js), so
 * a point keeps its place between bars and past the ends instead of snapping to the nearest bar. */
export function moved(points, di, dp, axis) {
  return points.map((q) => ({ t: Math.round(axis.t(axis.f(q.t) + di)), p: +(q.p + dp).toFixed(4) }));
}
/** The distance from a point to a segment, for picking a drawing under the pointer. */
export function segDist(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1, t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / ((dx * dx + dy * dy) || 1)));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}
