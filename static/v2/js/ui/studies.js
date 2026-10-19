// The chart studies the classic Charting tab draws beside the averages and bands (C11), for the v2 price
// chart (ui/pricechart.js). The maths is the classic app's, ported line for line from static/app.js so the two
// draw the same thing: smaSeries, rsiSeries and adxSeries for TSO, maTrendSeries, volumeByPrice, weekMonday
// for the stages, and trendSegments for the auto trend lines. tests/test_v2_studies.py runs each against the
// classic function on the same bars.
//
// What the server computes stays on the server: Keltner, Donchian, the regression channel and anchored VWAP
// come from /api/indicators, the Weinstein stage of each week from /api/stage, the trend lines from
// /api/trendlines, the accumulation zones from /api/longterm and supply and demand from the ticker payload.
// Bars are {t (epoch ms), o, h, l, c, v}.

const fin = (v) => v !== null && v !== undefined && Number.isFinite(v);

/* ---------- the classic series helpers ---------- */
export function smaSeries(values, period) {
  const out = new Array(values.length).fill(null);
  let sum = 0, count = 0;
  for (let i = 0; i < values.length; i += 1) {
    const v = values[i];
    if (!fin(v)) { sum = 0; count = 0; continue; }
    sum += v; count += 1;
    if (count > period) { sum -= values[i - period]; count = period; }
    if (count === period) out[i] = sum / period;
  }
  return out;
}
/** Wilder's RSI, the smoothing the standard uses. */
export function rsiSeries(closes, period = 14) {
  const out = new Array(closes.length).fill(null);
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i < closes.length; i += 1) {
    const change = closes[i] - closes[i - 1], gain = Math.max(change, 0), loss = Math.max(-change, 0);
    if (i <= period) {
      avgGain += gain / period; avgLoss += loss / period;
      if (i === period) out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
      continue;
    }
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return out;
}
/** Wilder's ADX: how strong a trend is, whichever way it runs, 0 to 100. */
export function adxSeries(high, low, close, period = 14) {
  const n = close.length, out = new Array(n).fill(null);
  let tr = 0, plus = 0, minus = 0, dxSum = 0, dxCount = 0, adx = null;
  for (let i = 1; i < n; i += 1) {
    const h = high[i], l = low[i], pc = close[i - 1];
    if (![h, l, pc, high[i - 1], low[i - 1]].every(fin)) continue;
    const up = h - high[i - 1], down = low[i - 1] - l;
    const trI = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc));
    const pI = up > down && up > 0 ? up : 0, mI = down > up && down > 0 ? down : 0;
    if (i <= period) { tr += trI; plus += pI; minus += mI; if (i < period) continue; } else { tr = tr - tr / period + trI; plus = plus - plus / period + pI; minus = minus - minus / period + mI; }
    const pdi = tr ? 100 * plus / tr : 0, mdi = tr ? 100 * minus / tr : 0;
    const dx = pdi + mdi ? 100 * Math.abs(pdi - mdi) / (pdi + mdi) : 0;
    if (adx === null) { dxSum += dx; dxCount += 1; if (dxCount === period) { adx = dxSum / period; out[i] = adx; } } else { adx = (adx * (period - 1) + dx) / period; out[i] = adx; }
  }
  return out;
}

/* ---------- Trend Strength Oscillator ---------- */
/* TrendSpider's, as its published script defines it: ADX rescaled so 25 (where a trend starts to count) is 0
 * and 100 is 100, plus RSI centred on 50, smoothed by a 5-bar simple average. Above +50 a strong trend has run
 * up far and fast, below -50 down: "overextended", in the script's words. */
export const TSO_LEVEL = 50;
export function tsoSeries(high, low, close, adxPeriod = 14, rsiPeriod = 14, smooth = 5) {
  const adx = adxSeries(high, low, close, adxPeriod), rsi = rsiSeries(close, rsiPeriod);
  return smaSeries(close.map((_, i) => (adx[i] === null || rsi[i] === null ? null : (adx[i] - 25) / 75 * 100 + (rsi[i] - 50))), smooth);
}

/* ---------- MA Trend Identifier ---------- */
/* Each bar against five simple averages: 1 when its open and close are both above all five, -1 when both are
 * below all five, 0 in between, null before the slowest average exists. */
export const MA_TREND_PERIODS = [10, 20, 50, 100, 200];
export function maTrendSeries(open, close, periods = MA_TREND_PERIODS) {
  const mas = periods.map((p) => smaSeries(close, p));
  return close.map((c, i) => {
    const o = open[i];
    if (!fin(c)) return null;
    const vals = mas.map((m) => m[i]);
    if (vals.some((v) => v === null)) return null;
    const lo = Math.min(c, fin(o) ? o : c), hi = Math.max(c, fin(o) ? o : c);
    if (lo > Math.max(...vals)) return 1;
    if (hi < Math.min(...vals)) return -1;
    return 0;
  });
}

/* ---------- volume by price ---------- */
/* The closes of the bars in view in 40 price buckets, each holding the volume traded at that close; the point
 * of control is the bucket with the most. */
export const VBP_BUCKETS = 40;
export function volumeByPrice(close, volume) {
  const closes = close.filter(fin);
  if (closes.length < 10 || !volume.length) return null;
  const lo = Math.min(...closes), hi = Math.max(...closes);
  if (!(hi > lo)) return null;
  const step = (hi - lo) / VBP_BUCKETS, buckets = new Array(VBP_BUCKETS).fill(0);
  close.forEach((c, i) => { const v = volume[i]; if (!fin(c) || !fin(v)) return; buckets[Math.min(VBP_BUCKETS - 1, Math.max(0, Math.floor((c - lo) / step)))] += v; });
  const peak = Math.max(...buckets);
  return buckets.map((vol, i) => ({ price: lo + (i + 0.5) * step, volume: vol, poc: vol === peak && peak > 0, lo: lo + i * step, hi: lo + (i + 1) * step })).filter((b) => b.volume > 0);
}

/* ---------- session dividers ---------- */
/* Where each trading day starts on intraday bars (a New York date change), or none when they would come every
 * few bars: one per four bars is the floor, below which a fence adds noise rather than orientation. */
const NY = typeof Intl !== 'undefined' ? new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }) : null;
export const nyDate = (t) => (NY ? NY.format(new Date(t)) : new Date(t).toISOString().slice(0, 10));
export function sessionStarts(bars) {
  const out = [];
  let prev = null;
  bars.forEach((b, i) => { const k = nyDate(b.t); if (prev !== null && k !== prev) out.push(i); prev = k; });
  return out.length <= Math.max(2, Math.floor(bars.length / 4)) ? out : [];
}

/* ---------- Weinstein stages ---------- */
/** The Monday of a date's week, as YYYY-MM-DD (the classic weekMonday). */
export function weekMonday(iso) {
  const d = new Date(String(iso).slice(0, 10) + 'T00:00:00Z');
  if (Number.isNaN(d.getTime())) return null;
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
  return d.toISOString().slice(0, 10);
}
const priorMonday = (monday) => { const d = new Date(monday + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() - 7); return d.toISOString().slice(0, 10); };
/**
 * Each bar's stage (1 to 4, 0 for none yet) from /api/stage's weekly history ([monday, stage] pairs). A week's
 * stage is decided by its Friday close, so a daily or intraday bar takes the stage of the last completed week,
 * the reading that stood when it printed; a weekly bar keeps its own week's, since its close is the input.
 */
export function stageOfBars(bars, history, { weekly = false, intraday = false } = {}) {
  const byWeek = new Map(history || []);
  return bars.map((b) => {
    const day = intraday ? nyDate(b.t) : new Date(b.t).toISOString().slice(0, 10), m = weekMonday(day);
    return (m && byWeek.get(weekly ? m : priorMonday(m))) || 0;
  });
}

/* ---------- lines the server computed, and the auto trend lines ---------- */
/** Server lines ({dates, lines: [{name, values}]}) laid on the chart's bars by time; a bar with no value is null. */
export function alignLines(dates, lines, bars) {
  const at = new Map();
  (dates || []).forEach((d, i) => at.set(Date.parse(String(d).length === 10 ? `${d}T00:00:00Z` : d), i));
  return (lines || []).map((ln) => ({ name: ln.name, values: bars.map((b) => { const i = at.get(b.t); const v = i === undefined ? null : (ln.values || [])[i]; return fin(v) ? v : null; }) }));
}
/**
 * The classic trendSegments for daily or weekly bars: each line from the chart bar at or after its anchor to
 * the last bar, its price read off the line at both ends (the anchor's own price is right only when the
 * anchor is on screen). Past the server's last bar it counts on, a bar a bar.
 */
export function trendSegments(tl, keys, { weekly = false } = {}) {
  if (!tl || !tl.available || !keys.length) return [];
  const src = tl.dates || [], last = src.length - 1;
  const inChart = new Map(keys.map((d, i) => [d, i])), inSrc = new Map(src.map((d, i) => [d, i]));
  const srcAt = (ci) => {
    const d = keys[ci];
    if (inSrc.has(d)) return inSrc.get(d);
    if (d > src[last]) { const lc = inChart.has(src[last]) ? inChart.get(src[last]) : null; return lc === null ? last : last + (ci - lc); }
    for (let k = 0; k <= last; k += 1) if (src[k] >= d) return k;
    return last;
  };
  const nearest = (anchor) => { const want = weekly ? (weekMonday(anchor) || anchor) : anchor; if (inChart.has(want)) return inChart.get(want); for (let i = 0; i < keys.length; i += 1) if (keys[i] >= want) return i; return null; };
  return (tl.lines || []).map((l) => {
    const d1 = src[l.start_index];
    if (!d1 || !src[l.end_index]) return null;
    const span = Math.max(1, l.end_index - l.start_index);
    const lineAt = (si) => Math.round((l.start_price + (l.price_now - l.start_price) * (si - l.start_index) / span) * 100) / 100;
    const x1 = nearest(d1), x2 = keys.length - 1;
    if (x1 === null || x1 >= x2) return null;
    const holding = !l.broken, up = l.kind === 'support' ? holding : !holding;
    return { i1: x1, p1: lineAt(srcAt(x1)), i2: x2, p2: lineAt(srcAt(x2)), up, broken: !!l.broken, kind: l.kind, label: `${l.kind === 'support' ? 'Support' : 'Resistance'}, ${l.touches} touches${l.broken ? ', broken' : ''}` };
  }).filter(Boolean);
}
