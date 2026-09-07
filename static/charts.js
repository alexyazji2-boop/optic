/* SVG chart primitives.
   No chart library: every mark is built here so the specs (2px lines, 4px
   rounded data-ends anchored to the baseline, 2px surface gaps and rings,
   hairline recessive grid, hover layer on everything with a plot) are applied
   uniformly rather than fought with a framework's defaults. */

const NS = 'http://www.w3.org/2000/svg';
const TIP = () => document.getElementById('tooltip');

/* Chart colours live in CSS, not here.
 *
 * SVG is built in JavaScript, so these never saw a CSS variable — which meant the
 * charts would have kept drawing white text and dark fills on a light page no
 * matter what the stylesheet said. The object below is now a cache that
 * `syncChartTheme()` refills from the computed custom properties, with these
 * values as the fallback for a stylesheet that hasn't loaded yet. */
const C = {
  ink: '#ffffff', ink2: '#c3c2b7', muted: '#898781',
  grid: '#2c2c2a', baseline: '#383835', surface: '#1a1a19',
  s1: '#3987e5', s2: '#d95926', s3: '#199e70', s4: '#c98500',
  s5: '#d55181', s6: '#008300', s7: '#9085e9', s8: '#e66767',
  pos: '#3987e5', neg: '#e66767',
  good: '#0ca30c', warn: '#fab219', serious: '#ec835a', critical: '#d03b3b',

  /* The default colour for a chart drawing.
   *
   * This slot was missing, and every new drawing is created with
   * color: 'accent'. So `C[dr.color] || C.accent` resolved to undefined, the
   * attribute helper skips undefined rather than writing the string
   * "undefined", and the line was appended with no stroke at all: present in
   * the DOM, hit-testable, selectable, draggable, and completely invisible.
   * "2 drawings" in the status bar with an empty chart is exactly what that
   * looks like from the outside. */
  accent: '#00c805',

  /* Reference-line colours, held apart from the eight categorical slots.
   *
   * Levels are annotation, not data: they mark where something happened rather
   * than tracing a value over time, so they're chosen for luminance against the
   * dark plane instead of for categorical separation. That matters here because
   * all eight series slots were already spoken for — support/resistance had been
   * given the dark green #008300, which at 34% opacity was almost invisible and
   * sat right next to the teal 50-week average. Gold and a light violet are the
   * two hues nothing else on a price chart uses. */
  refSR: '#eb17bd',
  refFib: '#c3c2b7',

  /* Session and period dividers.
   *
   * Its own hue, because the old implementation drew them in C.baseline — the
   * exact colour of the axis line — so a time boundary was indistinguishable
   * from chart furniture. Cyan is the one family nothing else on a price chart
   * uses: 7.87:1 on the plane and at least 81 points of RGB separation from
   * every series slot, the two reference hues, the grid and the baseline. */
  refSession: '#5ab7d1',
};

// Which CSS custom property backs each slot.
const C_VARS = {
  ink: '--ink', ink2: '--ink-2', muted: '--ink-muted',
  grid: '--grid', baseline: '--baseline', surface: '--surface',
  s1: '--s1', s2: '--s2', s3: '--s3', s4: '--s4',
  s5: '--s5', s6: '--s6', s7: '--s7', s8: '--s8',
  pos: '--pos', neg: '--neg', mid: '--mid',
  good: '--good', warn: '--warn', serious: '--serious', critical: '--critical',
  accent: '--accent',
  refSR: '--ref-sr', refFib: '--ref-fib', refSession: '--ref-session',
};

/** Pull the live theme into C. Called at boot and whenever the OS theme flips. */
function syncChartTheme() {
  if (typeof getComputedStyle !== 'function') return;
  const cs = getComputedStyle(document.documentElement);
  Object.entries(C_VARS).forEach(([slot, prop]) => {
    const value = cs.getPropertyValue(prop).trim();
    if (value) C[slot] = value;
  });
}

/* ------------------------------------------------------------- formatting */

/* Never render a negative zero.
 *
 * A composite of -0.04 rounded to whole numbers came out as "-0", which is not a
 * number anyone can read — it looks like a typo or a broken sign. Anything that
 * rounds to zero at the requested precision is zero, and should say so. Fixed
 * here rather than at one call site because every figure in the app goes through
 * these two functions. */
function stripNegativeZero(text) {
  return /^-0(?:[.,]0+)?$/.test(text) ? text.slice(1) : text;
}

function fmt(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return stripNegativeZero(Number(v).toLocaleString('en-US', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  }));
}

function fmtCompact(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  const abs = Math.abs(v);
  if (abs >= 1e12) return (v / 1e12).toFixed(digits) + 'T';
  if (abs >= 1e9) return (v / 1e9).toFixed(digits) + 'B';
  if (abs >= 1e6) return (v / 1e6).toFixed(digits) + 'M';
  if (abs >= 1e3) return (v / 1e3).toFixed(digits) + 'K';
  return fmt(v, abs < 10 ? 2 : 0);
}

function fmtPct(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  // Same rule, plus the sign prefix has to follow the rounded value: -0.004 at two
  // decimals is 0.00%, so it takes the '+' rather than keeping a stray minus.
  const rounded = stripNegativeZero(Number(v).toFixed(digits));
  return (Number(rounded) >= 0 ? '+' : '') + rounded + '%';
}

function signClass(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'flat';
  return v > 0 ? 'up' : v < 0 ? 'down' : 'flat';
}

/* --------------------------------------------------------------- svg utils */

function s(tag, attrs = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined) continue;
    node.setAttribute(k, String(v));
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

function svgRoot(width, height) {
  const root = s('svg', {
    class: 'chart', viewBox: `0 0 ${width} ${height}`,
    width: '100%', height, preserveAspectRatio: 'xMidYMid meet',
    role: 'img',
  });
  return root;
}

function niceTicks(min, max, count = 4) {
  if (!(isFinite(min) && isFinite(max)) || min === max) return [min];
  const span = max - min;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  // The 2.5 rung matters: without it, a normalized step of 2-3 rounds up to 5,
  // which on a ~150-wide price range collapses a 6-tick request down to 3.
  const step = (norm >= 5 ? 10 : norm >= 3 ? 5 : norm >= 2 ? 2.5 : norm >= 1 ? 2 : 1) * mag;
  const out = [];
  for (let t = Math.ceil(min / step) * step; t <= max + step * 0.001; t += step) out.push(t);
  return out;
}

function showTip(html, evt) {
  const tip = TIP();
  tip.innerHTML = html;
  tip.classList.add('on');
  const rect = tip.getBoundingClientRect();
  const edge = 8;
  const touch = evt.pointerType && evt.pointerType !== 'mouse';

  // A finger covers roughly 40px of screen. Placing the readout below the point
  // the way a cursor tooltip does puts it directly under the hand holding the
  // phone, so on touch it goes above the contact point and further away.
  const pad = touch ? 26 : 14;
  let x = evt.clientX + (touch ? -rect.width / 2 : pad);
  let y = touch ? evt.clientY - rect.height - pad : evt.clientY + pad;

  if (!touch && x + rect.width > window.innerWidth - edge) {
    x = evt.clientX - rect.width - pad;
  }
  if (!touch && y + rect.height > window.innerHeight - edge) {
    y = evt.clientY - rect.height - pad;
  }
  // Clamp both axes unconditionally. The old code only flipped, which still let
  // the box run off the top or bottom on a short viewport — at phone height the
  // readout was partly off-screen.
  x = Math.max(edge, Math.min(x, window.innerWidth - rect.width - edge));
  y = Math.max(edge, Math.min(y, window.innerHeight - rect.height - edge));

  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
}

function hideTip() { TIP().classList.remove('on'); }

/* Bind chart scrubbing for mouse *and* touch.
 *
 * The charts only listened for mousemove, so on a phone they had no readout at
 * all — the tooltip is the only way to get an exact value off a line, and it was
 * desktop-only. Pointer events unify the three input types: for a mouse
 * `pointermove` fires on hover exactly as before, and for touch it fires while a
 * finger is down, which is the scrubbing gesture people already expect from a
 * price chart.
 *
 * `touch-action: pan-y` is the important part. Without it the browser either
 * treats the drag as a page scroll (so the chart never sees it) or, with
 * `none`, swallows vertical scrolling so the page traps the finger inside the
 * chart. `pan-y` gives the axis away and keeps the other: drag sideways to
 * scrub, drag up and down to scroll past.
 */
function bindScrub(el, onMove, onEnd) {
  el.style.touchAction = 'pan-y';
  el.addEventListener('pointermove', (evt) => {
    // A touch that isn't pressed is a stray hover event from a hybrid device.
    if (evt.pointerType !== 'mouse' && evt.pressure === 0 && evt.buttons === 0) return;
    onMove(evt);
  });
  el.addEventListener('pointerdown', (evt) => {
    // Report immediately on tap rather than waiting for the first movement.
    onMove(evt);
    if (el.setPointerCapture && evt.pointerType !== 'mouse') {
      // Keeps events coming if the finger strays outside the plot mid-drag.
      try { el.setPointerCapture(evt.pointerId); } catch (e) { /* not critical */ }
    }
  });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach((type) => {
    el.addEventListener(type, (evt) => {
      // A mouse leaving means "stop"; a mouse button release does not.
      if (type === 'pointerup' && evt.pointerType === 'mouse') return;
      onEnd();
    });
  });
}

function tipRows(title, rows) {
  return `<div class="t-title">${title}</div>` + rows
    .map(([k, v]) => `<div class="t-row"><span>${k}</span><span>${v}</span></div>`)
    .join('');
}

/* --------------------------------------------------------- draw-on animation
 *
 * The line sweeps in from the left and the axis, levels and markers fade in
 * behind it. Done with stroke-dashoffset: a polyline's dash pattern set to its
 * own length, offset by that length, is invisible; animating the offset to zero
 * reveals it end to end. That traces the actual path rather than wiping a
 * rectangle across it, so it follows the data.
 *
 * Two things it deliberately does NOT do.
 *
 * It doesn't animate on a silent refresh. The swing view re-renders every 20
 * seconds while the market is open, and a chart that redraws itself on a timer
 * while you're reading it is worse than one that never animates at all — so the
 * flag is set by the loaders and only for a foreground load.
 *
 * It doesn't animate on resize, for the same reason: dragging a window edge
 * would otherwise replay it on every frame.
 */
let animateNextChart = false;

function setChartAnimation(on) { animateNextChart = on; }

/* Whether the next chart's leading point should pulse.
 *
 * Set from the market clock, not from "a fetch happened": a dot that blinks
 * while the market is shut is telling the reader something untrue. The pulse
 * means "this point is still moving", which is only the case in a live session.
 */
let liveNextChart = false;

function setChartLive(on) { liveNextChart = on; }

const reducedMotion = () => window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const DRAW_MS = 620;
const FADE_MS = 300;

/* The primary line leads; each subsequent series follows 70ms behind, which
 * reads as one gesture rather than several lines racing. Each chart gets its own
 * counter, so a MACD panel doesn't inherit the price chart's ordering. */
const DRAW_STAGGER_MS = 70;
function makeStagger() {
  let order = 0;
  return () => (order++) * DRAW_STAGGER_MS;
}

/* One observer for every waiting chart. The Map is keyed by the SVG root so the
 * callback can be recovered from entry.target, and entries are deleted as they
 * fire so nothing accumulates across view switches. */
const deferredDraws = new Map();
let drawObserver = null;

/* Forget charts whose DOM has been swapped out. A detached node can never
 * intersect anything, so its entry would sit in the Map holding a reference to a
 * dead SVG tree. Called on every queue and every pending check. */
function pruneDeferredDraws() {
  deferredDraws.forEach((pending, root) => {
    if (root.isConnected) return;
    if (drawObserver) drawObserver.unobserve(root);
    deferredDraws.delete(root);
  });
}

/* There is deliberately no timeout here.
 *
 * The first version gave a waiting chart 15 seconds and then revealed it
 * undrawn, as insurance against IntersectionObserver never firing. That
 * insurance was the bug: a reader who takes longer than 15 seconds to scroll
 * down — which is most readers, on a page this long — arrived to find every
 * chart already revealed and the animation silently cancelled. Instrumenting the
 * page showed exactly that, six charts queued and then flushed at ~26s with the
 * viewport still at the top.
 *
 * Waiting indefinitely is safe because a pre-hidden chart is by definition
 * off-screen, so nobody is looking at the thing being withheld. Whatever makes
 * it visible later — scrolling, a window resize, revealing the tab it sits in —
 * fires the observer, and the absent-API case falls through to drawing at once.
 */
function releaseWhenVisible(root, start) {
  const rect = root.getBoundingClientRect();
  const vh = window.innerHeight || document.documentElement.clientHeight || 0;
  // Already on screen: draw now.
  if (rect.top < vh * 0.92 && rect.bottom > 0) { start(); return; }
  if (typeof IntersectionObserver !== 'function') { start(); return; }

  if (!drawObserver) {
    drawObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const pending = deferredDraws.get(entry.target);
        drawObserver.unobserve(entry.target);
        deferredDraws.delete(entry.target);
        if (pending) pending.start();
      });
    // A fifth of the chart has to be on screen, and the bottom edge is pulled in
    // so the draw doesn't start while only the top pixel row is peeking up.
    }, { threshold: 0.2, rootMargin: '0px 0px -10% 0px' });
  }

  pruneDeferredDraws();
  deferredDraws.set(root, { start });
  drawObserver.observe(root);
}

/* Is any chart still waiting to be scrolled to?
 *
 * The silent refresh needs this. It rebuilds the view every 20 seconds with
 * animation off, which was quietly cancelling the whole feature: a chart that
 * had been deferred until it scrolled into view got replaced by a plain one
 * before the reader ever got down the page, so the draw only ever appeared if
 * you happened to scroll within the first twenty seconds. If something is still
 * pending, the replacement keeps its tags and waits its turn too.
 *
 * Detached roots are dropped first — a chart whose DOM was swapped out can never
 * intersect anything. This runs before the new render, while the outgoing chart
 * is still connected, so a genuinely-pending draw survives the swap.
 */
function hasPendingDraws() {
  pruneDeferredDraws();
  return deferredDraws.size > 0;
}

/** Kick off the animation. Must run after the SVG is in the document —
 *  getTotalLength() returns 0 on a detached node.
 *
 *  Uses element.animate() rather than a CSS transition. The transition version
 *  silently did nothing: it depends on the browser painting the start value
 *  before the end value is assigned, and no amount of requestAnimationFrame
 *  nesting made that reliable — the computed stroke-dashoffset never left zero.
 *  The Web Animations API states both keyframes explicitly, so there is no
 *  paint-timing race to lose. It also tidies up after itself, which is what the
 *  setTimeout cleanup was for.
 *
 *  Charts below the fold wait until they are scrolled to.
 *
 *  Without that they were animating on schedule and nobody ever saw it: the
 *  price chart on the swing view sits several panels down, so the whole 620ms
 *  sweep finished while the reader was still at the top of the page and the
 *  chart was fully drawn by the time it came into view. Deferring is also just
 *  better behaviour — every chart on a long page introduces itself as you reach
 *  it, instead of all nineteen animating at once into an empty viewport.
 */
function animateChart(root) {
  if (!root || !root.querySelectorAll) return;
  const lines = root.querySelectorAll('[data-draw]');
  const fades = root.querySelectorAll('[data-fade]');
  if (!lines.length && !fades.length) return;
  // Older Safari lacks element.animate on SVG; the chart is fully drawn either
  // way, so the fallback is simply no animation.
  if (typeof root.animate !== 'function') return;

  // Measure now, while the node is attached and laid out — by the time a
  // deferred chart is scrolled to, this is all still valid, and doing it here
  // keeps the hidden state and the animation working from identical numbers.
  const draws = [];
  lines.forEach((el) => {
    let len = 0;
    try { len = el.getTotalLength(); } catch (e) { len = 0; }
    if (!len || !isFinite(len)) return;
    draws.push({ el, len, delay: Number(el.getAttribute('data-draw')) || 0 });
  });
  const fadeIns = [...fades].map((el) => ({
    el, delay: Number(el.getAttribute('data-fade')) || 0,
  }));
  if (!draws.length && !fadeIns.length) return;

  // Pre-hide, so a deferred chart isn't sitting there fully drawn and then
  // blanking itself the moment it scrolls into view.
  const hide = () => {
    draws.forEach(({ el, len }) => {
      el.style.strokeDasharray = `${len}`;
      el.style.strokeDashoffset = `${len}`;
    });
    fadeIns.forEach(({ el }) => { el.style.opacity = '0'; });
  };
  const start = () => {
    draws.forEach(({ el, len, delay }) => {
      // dasharray has to be set for dashoffset to mean anything; the inline
      // offset is cleared on finish or the element would snap back to hidden.
      el.style.strokeDasharray = `${len}`;
      el.style.strokeDashoffset = `${len}`;
      const anim = el.animate(
        [{ strokeDashoffset: len }, { strokeDashoffset: 0 }],
        { duration: DRAW_MS, delay, easing: 'cubic-bezier(0.33, 1, 0.68, 1)', fill: 'backwards' },
      );
      anim.finished.then(() => {
        el.style.strokeDasharray = '';
        el.style.strokeDashoffset = '';
      }).catch(() => {});
    });

    fadeIns.forEach(({ el, delay }) => {
      el.style.opacity = '0';
      // The second keyframe is deliberately empty rather than `{ opacity: 1 }`.
      // An empty keyframe resolves to the element's own value, which matters for
      // anything not naturally opaque: the area fill sits at 0.1, so fading it to
      // 1 drove it to a solid block and then snapped it back to 0.1 on finish — a
      // visible flash right as the line completed.
      const anim = el.animate([{ opacity: 0 }, {}],
        { duration: FADE_MS, delay, easing: 'ease-out', fill: 'backwards' });
      anim.finished.then(() => { el.style.opacity = ''; }).catch(() => {});
    });
  };

  hide();
  releaseWhenVisible(root, start);
}

/* ------------------------------------------------------------- line charts */

/**
 * Multi-series line chart with an optional set of horizontal reference lines
 * (used for Fibonacci levels and gamma walls). Single y-scale only — two
 * measures of different magnitude get two charts, never two axes.
 */
/* ------------------------------------------------------------- time axis
 *
 * Ticks chosen by calendar boundary, not by fraction of the width.
 *
 * The axis before this was three labels — first bar, middle bar, last bar —
 * carrying full ISO dates. On a six-month chart that is "2026-03-09",
 * "2026-06-05", "2026-09-04" and nothing between them, so a reader could see
 * that a move happened and not say when. Every reference platform ticks the
 * calendar instead: a mark where the month turns, or the week, or the day,
 * whichever is coarse enough to fit.
 *
 * Fraction-based ticks cannot do that. A mark at 25% of the width lands on
 * whatever bar happens to be there, so the labels read 14 Aug, 3 Sep, 22 Sep —
 * evenly spaced and meaningless. Boundary ticks land on the dates a reader
 * already thinks in.
 *
 * The granularity is picked by measuring: take the finest unit whose boundaries
 * still leave `minGap` pixels between labels. That way a 5-day chart ticks
 * hours, a 6-month chart ticks months, and a 10-year chart ticks years, with no
 * per-range configuration to keep in step with CHART_RANGES.
 */
const TIME_UNITS = [
  { id: 'hour', of: (d) => d.getHours() + d.getDate() * 24 },
  { id: 'day', of: (d) => d.getDate() + d.getMonth() * 32 },
  { id: 'week', of: (d) => {
    // Monday-anchored week index. getDay() is 0 on Sunday, so shift it.
    const t = new Date(d.getTime());
    t.setDate(t.getDate() - ((t.getDay() + 6) % 7));
    return Math.floor(t.getTime() / 86400000);
  } },
  { id: 'month', of: (d) => d.getMonth() + d.getFullYear() * 12 },
  { id: 'year', of: (d) => d.getFullYear() },
];

const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function parseBarDate(label) {
  if (!label) return null;
  const raw = String(label);
  // Daily labels are bare dates. Parsing "2026-03-09" as ISO makes it UTC
  // midnight, which in a negative offset is the evening of the 8th — so the
  // month boundary lands one bar early and December reads as November. The
  // T00:00:00 suffix keeps it local, which is what the axis is describing.
  const iso = /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw + 'T00:00:00' : raw;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d;
}

/** Tick indices and their labels, at the finest calendar unit that fits.
 *
 * Two rules do the work, and both were learned by getting it wrong.
 *
 * **A unit finer than the bars is not a unit.** On daily bars the hour of every
 * bar is 00, so "the hour changed" is true at every single bar. Combined with
 * striding that unit always fitted — it just kept every Nth bar — and the axis
 * came back reading "10 Mar, 27 Mar, 16 Apr, 5 May", thirteen trading days
 * apart. Evenly spaced marks on arbitrary bars is precisely the fraction-based
 * axis this replaced, wearing calendar labels.
 *
 * **Stride is the outer loop, not the inner one.** Searching unit-first finds
 * week-every-third before month-every-first, and a tick on every third week is
 * a worse label than a tick on every month even though both fit. Trying stride
 * 1 across all units before stride 2 means the axis lands on the coarsest
 * structure available at full density, which is what a reader is looking for.
 */
function timeTicks(labels, X, minGap) {
  const dates = labels.map(parseBarDate);
  const present = dates.filter(Boolean).length;
  if (!present) return [];

  // Boundary indices per unit, computed once.
  const perUnit = TIME_UNITS.map((unit) => {
    const marks = [];
    let prev = null;
    for (let i = 0; i < dates.length; i += 1) {
      const d = dates[i];
      if (!d) continue;
      const key = unit.of(d);
      // The first bar is only a tick if it is genuinely a boundary; a label
      // hard against the left edge tells a reader nothing they cannot see.
      if (prev !== null && key !== prev) marks.push(i);
      prev = key;
    }
    return { unit, marks };
  }).filter(({ marks }) => (
    // Finer than the data: every bar is a boundary, so this unit carries no
    // structure. 0.9 rather than 1.0 because a market week has holidays in it
    // and a stray equal pair should not rescue an otherwise meaningless unit.
    marks.length >= 2 && marks.length < present * 0.9
  ));

  const fits = (kept) => {
    for (let k = 1; k < kept.length; k += 1) {
      if (X(kept[k]) - X(kept[k - 1]) < minGap) return false;
    }
    return true;
  };
  /* Labels are built against the previous KEPT tick, not the previous bar.
   *
   * The year is meant to replace the month wherever the year turns, so a run
   * reads "Oct, Dec, 2026, Apr". Comparing each tick to dates[i - 1] made that
   * test true only on the exact bar the year changed — and with a stride of 2
   * that bar is usually one of the marks thrown away. The result was a 2-year
   * axis reading "Oct, Dec, Feb, Apr, Jun, Aug, Oct, Dec, Feb, Apr, Jun, Aug",
   * with nothing anywhere to say which October was which. */
  const build = ({ unit, marks }, stride) => {
    const kept = marks.filter((_, k) => k % stride === 0);
    return kept.map((i, k) => ({
      i,
      text: tickLabel(dates[i], unit.id, k > 0 ? dates[kept[k - 1]] : null),
    }));
  };

  // A two-label fit is accepted only if nothing denser exists anywhere, so a
  // 2-year chart prefers eight quarter marks over two year marks.
  let sparse = null;
  for (let stride = 1; stride <= 8; stride += 1) {
    for (let u = 0; u < perUnit.length; u += 1) {
      const kept = perUnit[u].marks.filter((_, k) => k % stride === 0);
      if (kept.length < 2 || !fits(kept)) continue;
      if (kept.length >= 3) return build(perUnit[u], stride);
      if (!sparse) sparse = build(perUnit[u], stride);
    }
  }
  if (sparse) return sparse;

  /* Last resort. A window that crosses no boundary at all — a two-bar chart —
   * still has a first and last date worth naming, and they are what tell a
   * reader which period this is. Formatted through the same vocabulary so they
   * do not appear as raw ISO next to an axis that reads "Aug" everywhere else.
   */
  const ends = [0, dates.length - 1].filter((i) => dates[i]);
  if (ends.length === 2 && X(ends[1]) - X(ends[0]) >= minGap) {
    return ends.map((i) => ({
      i,
      text: `${dates[i].getDate()} ${MONTH_SHORT[dates[i].getMonth()]}`,
    }));
  }
  return [];
}

/* The label for one tick.
 *
 * Coarser than the unit being ticked wherever the coarser unit also turned, so
 * a run of "Aug, Sep, Oct, Nov, Dec, Jan" says which January it is without
 * repeating the year on all six. Same idea as the reference axis reading
 * "25. Jul ... 4. Sep" and then "2027" when it crosses.
 *
 * `prev` is the previous tick that survived striding, not the previous bar —
 * see build(). The first tick has no predecessor and is treated as a fresh
 * year, so a chart always names its era once at the left.
 */
function tickLabel(d, unitId, prev) {
  const newYear = !prev || prev.getFullYear() !== d.getFullYear();
  const newMonth = newYear || !prev || prev.getMonth() !== d.getMonth();
  if (unitId === 'year') return String(d.getFullYear());
  if (unitId === 'month') return newYear ? String(d.getFullYear()) : MONTH_SHORT[d.getMonth()];
  if (unitId === 'week' || unitId === 'day') {
    /* The leftmost tick names the month, not the year.
     *
     * `newYear` is true for the first tick because it has no predecessor, which
     * is right when the ticks are months — a 6-month axis reading "2026, May,
     * Jun" is correct. It is over-specified when the ticks are days: a 1-month
     * axis came back "2026, 17, 24, 31", where the one label that should have
     * told you the month told you the year instead. */
    if (newYear) return prev ? String(d.getFullYear()) : MONTH_SHORT[d.getMonth()];
    return newMonth ? MONTH_SHORT[d.getMonth()] : String(d.getDate());
  }
  // Hours, on an intraday chart. A new day gets the date instead of 00:00,
  // which is the only tick where the time is not the useful part.
  if (newMonth || (prev && prev.getDate() !== d.getDate())) {
    return `${d.getDate()} ${MONTH_SHORT[d.getMonth()]}`;
  }
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/* Which time boundary is worth drawing a line at, and how to label it.
 *
 * Read off the spacing of the bars rather than told by the caller. The old
 * version always divided on the calendar day, which is correct intraday and
 * absurd on a daily chart where every bar is a new day — and the guard against
 * that capped the line count at a third of the bars rather than bailing, so a
 * six-month daily chart got 42 dashed verticals.
 *
 * The rule is that a divider should appear often enough to orient you and
 * rarely enough to read as punctuation: roughly between 2 and 24 of them. So
 * the granularity steps up with the bar interval.
 */
function periodDividers(labels, n) {
  const at = (i) => {
    const raw = String(labels[i] || '');
    const d = new Date(raw.length <= 10 ? raw + 'T00:00:00Z' : raw);
    return Number.isNaN(d.getTime()) ? null : d;
  };
  const first = at(0);
  const last = at(n - 1);
  if (!first || !last || n < 4) return null;

  // Median gap in days, which is robust to the weekend holes a mean is not.
  const gaps = [];
  for (let i = 1; i < n; i += 1) {
    const a = at(i - 1);
    const b = at(i);
    if (a && b) gaps.push((b - a) / 86400000);
  }
  if (!gaps.length) return null;
  gaps.sort((x, y) => x - y);
  const step = gaps[Math.floor(gaps.length / 2)];

  /* Granularity, and the key that changes at each boundary.
   *
   * `key` returns a string that is constant within a period, so a boundary is
   * simply "the key changed" — the same test at every granularity. */
  if (step < 0.9) {
    return { grain: 'day', key: (d) => d.toISOString().slice(0, 10),
      label: (d) => d.toUTCString().slice(0, 11).trim() };
  }
  if (step < 5) {
    // Daily bars. Months give ~1 per 21 bars: 6 on a six-month chart, 12 on a
    // year. Weeks would give 26 and 52, which is the fence again.
    return { grain: 'month', key: (d) => d.toISOString().slice(0, 7),
      label: (d) => MONTHS[d.getUTCMonth()] + (d.getUTCMonth() === 0
        ? " '" + String(d.getUTCFullYear()).slice(2) : '') };
  }
  if (step < 45) {
    // Weekly bars: quarters on a short span, years on a long one.
    const years = (last - first) / 86400000 / 365;
    if (years > 3) {
      return { grain: 'year', key: (d) => String(d.getUTCFullYear()),
        label: (d) => String(d.getUTCFullYear()) };
    }
    return { grain: 'quarter',
      key: (d) => d.getUTCFullYear() + 'Q' + Math.floor(d.getUTCMonth() / 3),
      label: (d) => 'Q' + (Math.floor(d.getUTCMonth() / 3) + 1) };
  }
  return { grain: 'year', key: (d) => String(d.getUTCFullYear()),
    label: (d) => String(d.getUTCFullYear()) };
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function lineChart(opts) {
  const {
    series = [], labels = [], height = 220, refLines = [],
    yFormat = (v) => fmt(v, 2), valueFormat = null, zeroLine = false,
    markerLast = true, width = 720,
    // {open, high, low, close} arrays. Drawn as OHLC candles under the series.
    // Folded into this chart rather than a separate function so candles inherit
    // the axis, date labels, reference-line placement and hover layer.
    candles = null,
    // Sloped lines in (bar index, price) space — trend lines, channels, and any
    // drawing anchored to two points. refLines cannot express these: they are
    // horizontal by construction, which is right for a level and wrong for a
    // trend. Each is {x1, y1, x2, y2, color, width, dash, label, extend}.
    segments = [],
    // Called with the index of the bar under the cursor, and with null when the
    // cursor leaves. Lets a caller keep its own readout in step with the
    // crosshair — the header on the Charting tab tracks it — without this
    // function needing to know what is being displayed.
    onHover = null,
    /* Period dividers: a labelled vertical line at each time boundary.
     *
     * Pass the label array (or a parallel array of timestamps) and the renderer
     * works out which boundary is worth drawing from the spacing of the bars
     * themselves — day on an intraday series, month on a daily one, year on a
     * weekly one. See periodDividers.
     *
     * It used to divide on the calendar day whatever the timeframe, which on a
     * daily chart is every single bar. Its own comment said "bailing out is
     * better than painting a picket fence" and then the guard capped the count
     * at a third of the bars instead of bailing: 126 daily bars produced 42
     * dashed verticals across the plot. */
    sessions = null,
    // Daily volume, drawn as a band of bars beneath the price plot. Its own
    // scale, its own strip: sharing the price axis would either flatten the bars
    // to nothing or crush the price into the top third. Bars are tinted by the
    // day's direction so a high-volume down day is visually distinct from a
    // high-volume up day, which is the whole reason to look at volume.
    volume = null,
    // Share of the chart height given to the volume strip.
    volumeShare = 0.18,
    // Volume by price: [{price, volume}] buckets drawn as horizontal bars against
    // the right edge, sharing the PRICE axis. This is the one overlay that
    // genuinely belongs on the price scale — it answers "how much traded here",
    // and the answer is only meaningful next to the level it refers to.
    volumeProfile = null,
    // Share of the plot width the profile may occupy. Kept small: it is context
    // behind the price, not a second chart competing with it.
    profileShare = 0.16,
    // Dated events to pin on the price line: [{date|index, kind, label, detail}].
    // kind is 'buy' or 'sell'. Used for insider transactions, where the date and
    // the direction are the whole point and the price at that date is the anchor.
    events = null,
    // 'expand' (default) grows the y-axis to include every reference line.
    // 'clip' sizes the axis from the price data alone and drops lines that fall
    // outside it — a chart with levels 25% away otherwise compresses the actual
    // price action into a thin band in the middle.
    refLineFit = 'expand',
    // 'right' (default) or 'left'. The labels are pills drawn inside the plot, so
    // the side matters: on a multi-year chart the recent action is bunched at the
    // right edge and right-aligned labels cover exactly the bars a reader is
    // looking at. Left is emptier there.
    refLabelSide = 'right',
    // How far past the price range a clipped reference line may still pull the
    // axis, as a fraction of the data span. A strict clip dropped the swing high
    // that sits 3% above a stock trading at its highs — which is precisely the
    // only resistance such a chart has. Near misses are worth a little axis;
    // levels a quarter of the way off the screen are not.
    refLineSlack = 0.16,
    // Force the y-axis instead of deriving it from the data. RSI is bounded 0-100,
    // and auto-scaling it to whatever range the line happened to occupy put the
    // overbought band at the very top edge and left the oversold band floating in
    // empty space — so the one thing the chart is for, how close to a band price
    // is, could not be judged.
    yDomain = null,
    // Vertical event markers, given as {index, color, label}. Used for the point
    // where two series cross.
    vMarkers = [],
    // Price bands: [{top, bottom, color, label}]. Drawn as filled rectangles
    // spanning the plot, beneath the data. Used for supply and demand zones,
    // which are genuinely areas rather than lines — the unfilled orders that
    // define one sit across the range that formed it, so collapsing a zone to a
    // single price would misrepresent what it is.
    bands = [],
    /* Filled ribbons between two per-bar series, tinted by which one is on top:
     * [{fast, slow, upColor, downColor, opacity, name}].
     *
     * A band is horizontal and fixed; a cloud follows the data and changes
     * colour where the two series cross. That difference is the whole point of
     * the shape — the question an EMA cloud answers is "which side of this pair
     * is price on, and for how long", and a reader gets that from the colour of
     * a filled area at a glance in a way that two lines close together never
     * gives them.
     *
     * The fill is split into runs of constant sign rather than drawn as one
     * polygon, because one polygon can only have one colour. Each run is closed
     * at the exact interpolated crossing point, so consecutive runs share an
     * edge and the ribbon has no gap or overlap where it flips.
     */
    clouds = [],
    // Draw each series' latest value as a coloured pill on the price axis.
    //
    // The single biggest readability gap against a platform chart: with four
    // lines on one plot, knowing that the 50-day sits at 215.08 meant either
    // hovering for a tooltip or matching a legend colour against a number in a
    // tile below the chart. The value belongs at the end of the line it describes.
    //
    // Off by default so the panels that are deliberately spare — sparklines,
    // the breadth strip — do not grow a gutter they have no use for.
    valueTags = false,
    /* The caller owns the plain drag, so measuring moves to shift-drag here.
     *
     * Only one gesture can have an unmodified left-drag. On the Charting tab it
     * is panning, because that is what a reader reaches for on a chart they can
     * zoom, and the measurement has two other ways in: shift-drag, and the ruler
     * in the tool rail, which leaves a drawing that stays put. The Swing chart
     * has no zoom and no pan, so it leaves this off and keeps the plain drag. */
    panDrag = false,
  } = opts;

  const W = width;
  const H = height;
  // r was 58, sized for a bare tick label. The value tags below sit in this
  // gutter, so it has to hold "1,234.56" plus the pill padding — otherwise the
  // tag overhangs the viewBox and gets clipped.
  const m = { t: 12, r: valueTags ? 74 : 58, b: 22, l: 8 };

  /* The pulsing last-price marker, kept so it can be raised above the value
   * tags at the end.
   *
   * SVG paints in document order and the tags are appended after the series, so
   * the tag's background rect and its leader line landed on top of the dot. The
   * hit stack under the marker read rect, line, circle.live-dot: it was being
   * drawn and then covered, which is indistinguishable from missing. */
  const liveMarks = [];
  const plotW = W - m.l - m.r;
  const plotH = H - m.t - m.b;

  const all = [];
  series.forEach((se) => se.values.forEach((v) => { if (v !== null && isFinite(v)) all.push(v); }));
  /* Cloud edges count towards the range, like any other data.
   *
   * The normal way to read an EMA cloud is with the lines themselves switched
   * off, so the values bounding it are in no series and would not otherwise
   * reach the axis. On a stock that has run hard away from its slow average
   * that silently clipped the bottom edge of the ribbon at the plot floor,
   * which reads as a cloud that stops rather than one that is off screen. */
  clouds.forEach((cl) => {
    (cl.fast || []).forEach((v) => { if (v !== null && isFinite(v)) all.push(v); });
    (cl.slow || []).forEach((v) => { if (v !== null && isFinite(v)) all.push(v); });
  });
  if (refLineFit !== 'clip') {
    refLines.forEach((r) => { if (isFinite(r.value)) all.push(r.value); });
  } else if (all.length) {
    // Let a level just outside the data range in, measured against the span the
    // data itself occupies.
    const dLo = Math.min(...all);
    const dHi = Math.max(...all);
    const slack = (dHi - dLo) * refLineSlack;
    refLines.forEach((r) => {
      if (isFinite(r.value) && r.value >= dLo - slack && r.value <= dHi + slack) all.push(r.value);
    });
  }
  // Bands, after the reference-line chain rather than inside it. Slotting this
  // between the `if` and its `else if` orphaned the else and took the whole file
  // out — every chart global went undefined at once.
  //
  // Under 'clip' a band is not offered to the domain at all: a zone 30% away
  // would compress the price action into a ribbon, and the panel already reports
  // zones that are out of reach separately.
  if (refLineFit !== 'clip') {
    bands.forEach((b) => {
      if (isFinite(b.top) && isFinite(b.bottom)) all.push(b.top, b.bottom);
    });
  }
  // Wicks reach beyond the closes, so the range has to include them or the
  // extremes clip at the plot edge.
  if (candles) {
    (candles.high || []).forEach((v) => { if (v !== null && isFinite(v)) all.push(v); });
    (candles.low || []).forEach((v) => { if (v !== null && isFinite(v)) all.push(v); });
  }
  if (zeroLine) all.push(0);
  if (!all.length) return document.createTextNode('');

  let lo;
  let hi;
  if (yDomain) {
    [lo, hi] = yDomain;
  } else {
    lo = Math.min(...all);
    hi = Math.max(...all);
    const padY = (hi - lo) * 0.08 || Math.abs(hi) * 0.08 || 1;
    lo -= padY; hi += padY;
  }

  const n = Math.max(...series.map((se) => se.values.length), (candles && (candles.close || []).length) || 0, 1);

  // Volume takes a strip off the bottom and the price plot shrinks to fit. This
  // has to happen before Y() is defined: scaling price over the full plot height
  // and then drawing bars into the bottom of it overlaps the two.
  const volRows = (volume && volume.length) ? volume : null;
  const volH = volRows ? Math.round(plotH * volumeShare) : 0;
  const volGap = volRows ? 6 : 0;
  const priceH = plotH - volH - volGap;

  const X = (i) => m.l + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const Y = (v) => m.t + priceH - ((v - lo) / (hi - lo)) * priceH;

  const root = svgRoot(W, H);

  // Captured once per chart so a flag flipped mid-render can't half-animate it.
  const animating = animateNextChart && !reducedMotion();
  const seriesDelay = makeStagger();
  // Scale gridline count with available height — a fixed 4 ticks leaves a tall
  // chart with a sparse, hard-to-read axis. ~65px per tick keeps labels legible.
  const ticks = niceTicks(lo, hi, Math.max(3, Math.min(8, Math.round(priceH / 65))));

  let lastTickLabel = null;
  const gridLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.45 : null });
  root.appendChild(gridLayer);

  /* Volume by price.
   *
   * Horizontal bars against the right edge on the PRICE axis, so each bar sits
   * level with the prices it describes. Drawn immediately after the grid and
   * before anything else, because it is background: the price line should read
   * over the profile, never the reverse.
   *
   * Deliberately low contrast and capped at a fraction of the width. A profile
   * drawn boldly competes with the line it is meant to contextualise, and the
   * useful signal is the SHAPE — where the fat nodes and the thin gaps are —
   * not any individual bar's exact length.
   */
  if (volumeProfile && volumeProfile.length) {
    const vpLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.4 : null });
    root.appendChild(vpLayer);
    const maxVol = Math.max(...volumeProfile.map((b) => b.volume || 0), 1);
    const maxW = plotW * profileShare;
    const sorted = volumeProfile.map((b) => b.price).filter(isFinite).sort((a, b) => a - b);
    const gaps = sorted.slice(1).map((v, i) => v - sorted[i]).filter((d) => d > 0);
    const step = gaps.length ? Math.min(...gaps) : (hi - lo) / 20;
    const barH = Math.max(1, Math.abs(Y(lo) - Y(lo + step)) - 1);
    volumeProfile.forEach((b) => {
      const v = b.volume || 0;
      if (v <= 0 || !isFinite(b.price) || b.price < lo || b.price > hi) return;
      const w = Math.max(1, (v / maxVol) * maxW);
      vpLayer.appendChild(s('rect', {
        x: m.l + plotW - w, y: Y(b.price) - barH / 2, width: w, height: barH,
        // The point-of-control bucket is the one worth finding at a glance.
        fill: b.poc ? C.s4 : C.ink2, opacity: b.poc ? 0.34 : 0.16,
      }));
    });
  }
  ticks.forEach((t) => {
    gridLayer.appendChild(s('line', {
      x1: m.l, y1: Y(t), x2: m.l + plotW, y2: Y(t), stroke: C.grid,
      'stroke-width': 1, opacity: 0.55,
    }));
    // A fine step plus a coarse yFormat can round neighbouring ticks to the same
    // string; draw the gridline but skip the repeated label.
    const text = yFormat(t);
    if (text === lastTickLabel) return;
    lastTickLabel = text;
    gridLayer.appendChild(s('text', {
      x: m.l + plotW + 6, y: Y(t) + 3.5, fill: C.muted, 'font-size': 10,
      'font-variant-numeric': 'tabular-nums',
    }, text));
  });

  if (zeroLine && lo < 0 && hi > 0) {
    gridLayer.appendChild(s('line', {
      x1: m.l, y1: Y(0), x2: m.l + plotW, y2: Y(0), stroke: C.baseline, 'stroke-width': 1,
    }));
  }

  /* Volume strip.
   *
   * Own scale, own band beneath the price. Tinted by the day's direction, because
   * the reason to look at volume at all is to tell a heavy up day from a heavy
   * down day — a single-colour strip answers "how much" but not "which way", and
   * "which way" is the half that matters.
   */
  // Indexed by bar so the crosshair can light the one under the cursor. A
  // reader scrubbing the price line is asking about that day, and the volume
  // for that day is part of the answer.
  const volBars = [];
  if (volRows) {
    const volTop = m.t + priceH + volGap;
    const volMax = Math.max(...volRows.map((v) => (v === null || !isFinite(v) ? 0 : v)), 1);
    const volLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.5 : null });
    root.appendChild(volLayer);

    const closes = (candles && candles.close) || (series[0] && series[0].values) || [];
    const barW = Math.max(1, (plotW / Math.max(n, 1)) - 1.5);
    volRows.forEach((v, i) => {
      if (v === null || !isFinite(v) || v <= 0) return;
      const h = Math.max(1, (v / volMax) * volH);
      // Direction from the close-to-close change, falling back to neutral on the
      // first bar where there is no prior close to compare against.
      const prev = closes[i - 1];
      const cur = closes[i];
      const up = (prev === null || prev === undefined || cur === null || cur === undefined)
        ? null : cur >= prev;
      const bar = s('rect', {
        x: X(i) - barW / 2, y: volTop + volH - h, width: barW, height: h,
        fill: up === null ? C.muted : (up ? C.pos : C.neg),
        opacity: 0.42, rx: Math.min(1.5, barW / 2),
      });
      volBars[i] = bar;
      volLayer.appendChild(bar);
    });
    // One quiet label so the strip is identifiable without a legend entry.
    volLayer.appendChild(s('text', {
      x: m.l + 2, y: volTop + 9, fill: C.muted, 'font-size': 10,
    }, 'Volume'));
  }

  /* Clouds, under the levels and under the data.
   *
   * Order matters both ways here. Above the volume strip, because a cloud is
   * price-axis information and the strip is not. Below the reference lines and
   * bands, because those are annotation and have to stay readable across a
   * filled area. Below the series themselves, because the EMA lines that bound
   * a cloud are drawn from the same numbers — a fill painted over them would
   * mute exactly the two lines it is describing.
   */
  if (clouds.length) {
    const cloudLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.7 : null });
    root.appendChild(cloudLayer);
    clouds.forEach((cl) => {
      const fastVals = cl.fast || [];
      const slowVals = cl.slow || [];
      const upColor = cl.upColor || C.pos;
      const downColor = cl.downColor || C.neg;
      const opacity = cl.opacity == null ? 0.16 : cl.opacity;
      // A bar counts only when both sides have a number. The fast average is
      // defined earlier in the history than the slow one, so the leading bars of
      // any pair have one side present and the other null; filling from a null
      // would anchor the ribbon at the bottom of the axis.
      const ok = (i) => Number.isFinite(fastVals[i]) && Number.isFinite(slowVals[i]);
      const diff = (i) => fastVals[i] - slowVals[i];
      // A forced yDomain does not have to contain the cloud, and a polygon has
      // no clip of its own — an unclamped edge would paint over the axis labels
      // and out through the bottom of the chart.
      const Yc = (v) => Math.max(m.t, Math.min(m.t + priceH, Y(v)));

      // Points are collected as [x, yFast, ySlow] so a run can be closed by
      // walking the same list backwards along the slow edge.
      let run = [];
      let runSign = 0;
      const flush = () => {
        if (run.length < 2) { run = []; return; }
        const fwd = run.map((pt) => `${pt[0]},${pt[1]}`).join(' ');
        const back = run.slice().reverse().map((pt) => `${pt[0]},${pt[2]}`).join(' ');
        cloudLayer.appendChild(s('polygon', {
          points: `${fwd} ${back}`,
          fill: runSign >= 0 ? upColor : downColor,
          opacity,
        }));
        run = [];
      };

      for (let i = 0; i < n; i += 1) {
        if (!ok(i)) { flush(); runSign = 0; continue; }
        const d = diff(i);
        // Zero continues whatever run is open rather than starting a third
        // state: two averages printing the same value is a touch, not a regime.
        const sign = d > 0 ? 1 : (d < 0 ? -1 : runSign || 1);
        if (run.length && sign !== runSign) {
          /* The crossing sits between this bar and the previous one, not on
           * either of them. Interpolating it and using that point to close the
           * old run and open the new one is what makes the colour change land
           * on the cross instead of up to a full bar late. */
          const prev = i - 1;
          const dPrev = diff(prev);
          const span = dPrev - d;
          const t = span === 0 ? 0.5 : Math.max(0, Math.min(1, dPrev / span));
          const xC = X(prev) + t * (X(i) - X(prev));
          const vC = fastVals[prev] + t * (fastVals[i] - fastVals[prev]);
          const yC = Yc(vC);
          run.push([xC, yC, yC]);
          flush();
          run.push([xC, yC, yC]);
        }
        runSign = sign;
        run.push([X(i), Yc(fastVals[i]), Yc(slowVals[i])]);
      }
      flush();
    });
  }

  // Levels arrive last: they annotate the price, so they should appear once the
  // price is there to annotate. Created here, ahead of the series, so everything
  // in it still renders *underneath* the data.
  const levelLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.8 : null });
  root.appendChild(levelLayer);

  // Bands first, so a reference line crossing a zone stays visible on top of it.
  // Clipped to the plot rather than dropped when partly outside: half a zone at
  // the edge of the axis is still information about where it is.
  /* Bands: a filled price range with its edges marked.
   *
   * Used for three families that are all genuinely ranges rather than lines —
   * Fibonacci intervals, support and resistance shelves, and supply/demand zones.
   * Drawing any of them as a single hairline claimed a precision the underlying
   * method does not have: an S/R level is a cluster with an ATR-scaled tolerance,
   * and the interesting Fibonacci fact is which pair price sits between.
   *
   * Labels are placed top-down with a minimum spacing, because seven Fibonacci
   * bands on a six-month chart put their captions within a few pixels of each
   * other and the overlap made all of them unreadable.
   */
  let lastLabelY = -Infinity;
  bands.forEach((b) => {
    if (!isFinite(b.top) || !isFinite(b.bottom)) return;
    if (b.bottom > hi || b.top < lo) return;          // entirely off the axis
    const yTop = Y(Math.min(b.top, hi));
    const yBot = Y(Math.max(b.bottom, lo));
    const height = Math.max(1.5, yBot - yTop);
    levelLayer.appendChild(s('rect', {
      x: m.l, y: yTop, width: plotW, height,
      fill: b.color || C.ink2, opacity: b.opacity == null ? 0.13 : b.opacity,
    }));
    if (b.edge !== false) {
      // The edges are the prices that actually matter; at 7% fill a thin band is
      // otherwise impossible to locate.
      const edgeOp = b.edgeOpacity == null ? 0.55 : b.edgeOpacity;
      [yTop, yTop + height].forEach((yy) => {
        levelLayer.appendChild(s('line', {
          x1: m.l, y1: yy, x2: m.l + plotW, y2: yy,
          stroke: b.color || C.ink2, 'stroke-width': 1, opacity: edgeOp,
        }));
      });
    }
    if (b.label && yTop - lastLabelY > 12) {
      lastLabelY = yTop;
      levelLayer.appendChild(s('text', {
        x: m.l + 6, y: yTop + 11, fill: b.color || C.ink2, 'font-size': 10,
        'font-weight': 600, opacity: 0.95,
      }, b.label));
    }
  });

  // Reference lines sit under the data: they are context, not a series. Once the
  // scale is fixed, anything outside it is dropped rather than clamped to the
  // edge, where it would read as a real level sitting at the chart boundary.
  const visibleRefs = refLines.filter(
    (r) => isFinite(r.value) && (refLineFit !== 'clip' || (r.value >= lo && r.value <= hi)),
  );
  visibleRefs.forEach((r) => {
    levelLayer.appendChild(s('line', {
      x1: m.l, y1: Y(r.value), x2: m.l + plotW, y2: Y(r.value),
      stroke: r.color || C.baseline,
      // Thicker and brighter than before. The old 1px at 34% opacity disappeared
      // against the area fill; these still read as annotation rather than data
      // because they're dashed and perfectly horizontal, not because they're dim.
      'stroke-width': r.emphasis ? 2 : 1.5,
      // Two dash patterns, so the level families stay apart even where their
      // colours sit close: long dashes for structure, fine dots for ratios.
      'stroke-dasharray': r.dash === false ? null : (r.pattern || '6 4'),
      // 0.3 was effectively invisible on a dark plane; the subordinate ratios need
      // to read as present-but-secondary, not as a rendering artefact.
      opacity: r.emphasis ? 0.95 : (r.dim ? 0.5 : 0.75),
    }));
  });

  /* Session dividers.
   *
   * Drawn from the labels rather than from a separate array: the label already
   * carries the timestamp, and taking the date part of it is what "a new session
   * started here" means. Behind the price line and the drawings, in front of the
   * grid — it is orientation, not data.
   */
  if (sessions && n > 1) {
    const spec = periodDividers(labels, n);
    const toDate = (i) => {
      const raw = String(labels[i] || '');
      const d = new Date(raw.length <= 10 ? raw + 'T00:00:00Z' : raw);
      return Number.isNaN(d.getTime()) ? null : d;
    };
    if (spec) {
      // Collected first, then drawn, so the count can be checked BEFORE
      // anything is painted. The old code decided per line and capped mid-loop,
      // which is how it ended up drawing a fence and then stopping.
      const marks = [];
      let prev = null;
      for (let i = 0; i < n; i += 1) {
        const d = toDate(i);
        if (!d) continue;
        const k = spec.key(d);
        if (prev === null) { prev = k; continue; }
        if (k === prev) continue;
        prev = k;
        marks.push({ i, label: spec.label(d) });
      }
      /* Draw nothing rather than a fence.
       *
       * If the chosen granularity still produces a line every few bars the
       * feature is not adding orientation, it is adding noise — so it stands
       * down instead of capping. One line per four bars is the floor. */
      if (marks.length && marks.length <= Math.max(2, Math.floor(n / 4))) {
        marks.forEach((mk) => {
          const x = X(mk.i);
          levelLayer.appendChild(s('line', {
            x1: x, y1: m.t, x2: x, y2: m.t + priceH,
            stroke: C.refSession, 'stroke-width': 1,
            // A long dash, distinct from the fine dots the ratio levels use and
            // the medium dashes the structural levels use. Three dash patterns,
            // three families.
            'stroke-dasharray': '2 6',
            opacity: 0.7,
          }));
          /* The label is what makes it a divider rather than a line.
           *
           * Sat at the top of the plot, on the right of its own line, so a
           * reader can tell WHICH boundary they are looking at — "Sep" or
           * "2024" — instead of only that one exists. */
          levelLayer.appendChild(s('text', {
            x: x + 3, y: m.t + 9, fill: C.refSession, 'font-size': 9,
            'font-weight': 600, opacity: 0.85,
          }, mk.label));
        });
      }
    }
  }

  /* Sloped segments.
   *
   * Clipped to the plot rather than to the data range: a trend line's whole
   * point is where it projects to, and cutting it at the last bar removes the
   * part you were looking for. `extend` carries it to the right edge.
   */
  segments.forEach((sg) => {
    if (![sg.x1, sg.y1, sg.x2, sg.y2].every((v) => isFinite(v))) return;
    const i1 = Math.max(0, Math.min(n - 1, sg.x1));
    const i2 = Math.max(0, Math.min(n - 1, sg.x2));
    const px1 = X(i1);
    const px2 = X(i2);
    // Recompute the endpoint prices after clamping, so a clipped line keeps its
    // slope instead of being sheared toward the clamped x.
    const t = (i) => (sg.x2 === sg.x1 ? 0 : (i - sg.x1) / (sg.x2 - sg.x1));
    const py1 = Y(sg.y1 + (sg.y2 - sg.y1) * t(i1));
    const py2 = Y(sg.y1 + (sg.y2 - sg.y1) * t(i2));
    levelLayer.appendChild(s('line', {
      x1: px1, y1: py1, x2: px2, y2: py2,
      stroke: sg.color || C.ink2,
      'stroke-width': sg.width || 1.6,
      'stroke-dasharray': sg.dash || null,
      'stroke-linecap': 'round',
      opacity: sg.opacity === undefined ? 0.9 : sg.opacity,
    }));
    if (sg.label) {
      // At the right end, where the line is heading — which is the end a reader
      // is asking about.
      const atRight = px2 >= px1;
      levelLayer.appendChild(s('text', {
        x: (atRight ? px2 : px1) - (atRight ? 4 : -4),
        y: (atRight ? py2 : py1) - 5,
        'text-anchor': atRight ? 'end' : 'start',
        fill: sg.color || C.ink2, 'font-size': 10, 'font-weight': 600,
      }, sg.label));
    }
  });

  vMarkers.forEach((mk) => {
    if (!(mk.index >= 0 && mk.index < n)) return;
    const cx = X(mk.index);
    levelLayer.appendChild(s('line', {
      x1: cx, y1: m.t, x2: cx, y2: m.t + priceH, stroke: mk.color || C.ink2,
      'stroke-width': 1.4, 'stroke-dasharray': '6 4', opacity: 0.75,
    }));
    if (mk.label) {
      // Flip the anchor near the right edge so the text stays inside the plot.
      const nearRight = cx > m.l + plotW * 0.62;
      levelLayer.appendChild(s('text', {
        x: nearRight ? cx - 6 : cx + 6, y: m.t + 11, fill: mk.color || C.ink2,
        'font-size': 10, 'font-weight': 600,
        'text-anchor': nearRight ? 'end' : 'start',
      }, mk.label));
    }
    if (isFinite(mk.value)) {
      levelLayer.appendChild(s('circle', {
        cx, cy: Y(mk.value), r: 3.4, fill: mk.color || C.ink2,
        stroke: C.surface, 'stroke-width': 1.5,
      }));
    }
  });

  /* Reference-line labels are placed in *pixel* space, not price space.
   *
   * A price-percentage gap rule can't know how tall the chart is, so clustered
   * levels still printed on top of each other. Here the real y positions are
   * known: sort them, then push each label down until it clears the one above
   * by LABEL_GAP. A nudge of a few pixels keeps the label visually attached to
   * its own line while guaranteeing the text stays readable.
   */
  const LABEL_GAP = 13;
  // A line drawn in a structural grey is deliberately faint, but text in that
  // grey is unreadable — those labels fall back to the muted ink instead.
  const readable = (color) => (!color || color === C.baseline || color === C.grid ? C.ink2 : color);
  const labeled = visibleRefs
    .filter((r) => r.label)
    .map((r) => ({ text: r.label, color: readable(r.color), lineY: Y(r.value) }))
    .sort((a, b) => a.lineY - b.lineY);

  let prevY = -Infinity;
  labeled.forEach((r) => {
    r.y = Math.min(Math.max(r.lineY - 4, prevY + LABEL_GAP), m.t + priceH - 2);
    prevY = r.y;
  });

  if (candles) {
    const o = candles.open || [], h = candles.high || [],
      l = candles.low || [], c = candles.close || [];
    // Leave a gap between bars so individual candles stay distinguishable; on a
    // dense series this floors at a 1px body, which reads as a bar chart and is
    // the honest rendering at that density.
    const slot = n > 1 ? plotW / (n - 1) : plotW;
    const body = Math.max(1, Math.min(11, slot * 0.62));
    for (let i = 0; i < n; i += 1) {
      const oo = o[i], hh = h[i], ll = l[i], cc = c[i];
      if ([oo, hh, ll, cc].some((v) => v === null || v === undefined || !isFinite(v))) continue;
      const up = cc >= oo;
      const colour = up ? C.s3 : C.s8;
      const x = X(i);
      levelLayer.appendChild(s('line', {
        x1: x, y1: Y(hh), x2: x, y2: Y(ll), stroke: colour, 'stroke-width': 1,
      }));
      // A doji (open === close) has zero height, which would render nothing —
      // floor it at 1px so flat bars are still visible.
      const top = Y(Math.max(oo, cc));
      const height = Math.max(1, Math.abs(Y(oo) - Y(cc)));
      // Both directions filled. Hollow-up is a real convention on some platforms,
      // but mixing it with filled-down makes the two look like different kinds of
      // mark rather than the same mark in two colours.
      levelLayer.appendChild(s('rect', {
        x: x - body / 2, y: top, width: body, height,
        fill: colour, stroke: colour, 'stroke-width': 1,
      }));
    }
  }

  series.forEach((se, si) => {
    if (se.hidden) return;  // present for hover/tooltip only, not drawn
    const pts = [];
    se.values.forEach((v, i) => {
      if (v === null || !isFinite(v)) return;
      pts.push(`${X(i).toFixed(2)},${Y(v).toFixed(2)}`);
    });
    if (!pts.length) return;
    if (se.fill) {
      const base = Y(Math.max(lo, 0));
      root.appendChild(s('path', {
        d: `M${pts[0].split(',')[0]},${base} L${pts.join(' L')} L${pts[pts.length - 1].split(',')[0]},${base} Z`,
        fill: se.color, opacity: 0.1, stroke: 'none',
        // Fades rather than sweeps: an area clipped to a growing width reads as a
        // curtain, and it would race the line it sits under.
        'data-fade': animating ? DRAW_MS * 0.55 : null,
      }));
    }
    root.appendChild(s('polyline', {
      points: pts.join(' '), fill: 'none', stroke: se.color,
      'stroke-width': se.width || 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round',
      'stroke-dasharray': se.dash || null, opacity: se.opacity || 1,
      // Already-dashed series are skipped — animating dashoffset on them would
      // fight the pattern that carries their meaning.
      'data-draw': animating && !se.dash ? seriesDelay(se) : null,
    }));

    if (markerLast && se.marker !== false) {
      const lastIdx = se.values.reduce((acc, v, i) => (v !== null && isFinite(v) ? i : acc), -1);
      if (lastIdx >= 0) {
        // A halo behind the leading point of the primary series while the
        // session is live. One series only: every line pulsing is noise, and the
        // reader is being told "the newest point is still forming", which is a
        // fact about the bar rather than about any particular average.
        if (liveNextChart && si === 0) {
          const halo = s('circle', {
            cx: X(lastIdx), cy: Y(se.values[lastIdx]), r: 4,
            fill: 'none', stroke: se.color, 'stroke-width': 1.5,
            class: 'live-halo',
            'data-fade': animating ? DRAW_MS * 0.8 : null,
          });
          root.appendChild(halo);
          liveMarks.push(halo);
        }
        // 2px surface ring keeps the end dot legible where lines cross.
        const endDot = s('circle', {
          cx: X(lastIdx), cy: Y(se.values[lastIdx]), r: 4,
          fill: se.color, stroke: C.surface, 'stroke-width': 2,
          class: liveNextChart && si === 0 ? 'live-dot' : null,
          // Lands as the line reaches it, rather than sitting at the far right
          // waiting for a line that hasn't arrived yet.
          'data-fade': animating ? DRAW_MS * 0.8 : null,
        });
        root.appendChild(endDot);
        if (liveNextChart && si === 0) liveMarks.push(endDot);
      }
    }
  });

  /* Labels go on last, above the series: underneath, price and moving-average
   * lines ran straight through the text. Each sits on an opaque pill so it stays
   * readable wherever it lands, and takes its line's color so you can tell at a
   * glance which level it belongs to.
   *
   * Grouped with the axis labels so the whole textual frame — level tags and
   * dates — resolves after the line is drawn. Reading numbers off an axis while
   * the series is still moving is the one part of this that looked unfinished. */
  const annotLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.85 : null });
  root.appendChild(annotLayer);

  /* Latest value per series, as a pill on the price axis in the line's colour.
   *
   * Two things this has to get right or it makes the chart worse, not better.
   *
   * Collisions. Four averages converging in a range put four tags on top of each
   * other. Tags are laid out from the top down and pushed apart to a minimum
   * spacing, so they stay in the same vertical order as the lines they belong to
   * and stay individually readable. A tag pushed off its own line is still
   * unambiguous — it keeps the line's colour, and no two share one.
   *
   * The tick labels underneath. A tag landing on a gridline number renders two
   * numbers on top of each other, so any tick within a tag's band is suppressed.
   * The tag carries strictly more information than the tick it hides. */
  /* The last price, tagged on the axis and ruled across the plot.
   *
   * The most conspicuous thing missing against a reference chart, and the
   * reason it was missing is specific: in candle mode the close series is kept
   * for the crosshair but marked `hidden`, and the tag loop skips hidden
   * series. So every overlay got a price tag on the axis and the price itself
   * did not — the one number a reader looks for first.
   *
   * The rule matters as much as the tag. A tag alone says what the price is; a
   * line across says where it sits relative to everything drawn on the chart,
   * which is the question being asked when someone glances at a level.
   *
   * Drawn before the overlay tags so those stack on top of it, and in the
   * directional colour rather than a series hue: this is not another line on
   * the chart, it is the price the chart is about.
   */
  if (valueTags) {
    let priceTag = null;
    const priceSeries = series.find((se) => (se.values || []).some(
      (v) => v !== null && isFinite(v),
    ));
    if (priceSeries) {
      const li = priceSeries.values.reduce(
        (acc, v, i) => (v !== null && isFinite(v) ? i : acc), -1,
      );
      if (li >= 0) {
        const last = priceSeries.values[li];
        // Direction over the visible window, so the tag agrees with the change
        // the header reports for the same range rather than with the last bar.
        const first = priceSeries.values.find((v) => v !== null && isFinite(v));
        const tone = (isFinite(first) && last < first) ? C.neg : C.pos;
        // The rule goes down now, under the data where it belongs. The TAG is
        // deferred into the stack below: rendered here it landed on top of the
        // fast average's tag, which sits within a couple of dollars of the
        // price by construction — so on the one chart where a price tag matters
        // most, the two numbers were drawn over each other.
        levelLayer.appendChild(s('line', {
          x1: m.l, y1: Y(last), x2: m.l + plotW, y2: Y(last),
          stroke: tone, 'stroke-width': 1,
          'stroke-dasharray': '3 3', opacity: 0.5,
        }));
        priceTag = { si: -1, color: tone, value: last, y: Y(last), isPrice: true };
      }
    }

    const tags = series
      .map((se, si) => {
        if (se.tag === false || se.hidden) return null;
        const li = se.values.reduce((acc, v, i) => (v !== null && isFinite(v) ? i : acc), -1);
        if (li < 0) return null;
        return { si, color: se.color, value: se.values[li], y: Y(se.values[li]) };
      })
      .filter(Boolean);
    // Into the same list, so one collision pass positions everything and the
    // price cannot be pushed off the axis or drawn over.
    if (priceTag) tags.push(priceTag);
    tags.sort((a, b) => a.y - b.y);

    const TAG_H = 15;
    const GAP = 1.5;
    // Top-down pass, then a bottom-up correction so a stack that hits the floor
    // does not push its last tag out of the plot entirely.
    let cursor = m.t - Infinity;
    tags.forEach((t) => {
      t.ty = Math.max(t.y, cursor + TAG_H + GAP);
      cursor = t.ty;
    });
    const floor = m.t + plotH;
    if (tags.length && tags[tags.length - 1].ty > floor) {
      let up = floor;
      for (let i = tags.length - 1; i >= 0; i -= 1) {
        tags[i].ty = Math.min(tags[i].ty, up);
        up = tags[i].ty - TAG_H - GAP;
      }
    }

    const fmtTag = valueFormat || yFormat;
    tags.forEach((t) => {
      const text = fmtTag(t.value);
      // The price reads a shade larger and fully opaque. It is the number a
      // reader looks for first and it should not be one of six identical pills.
      const h = t.isPrice ? TAG_H + 2 : TAG_H;
      const w = Math.max(30, text.length * (t.isPrice ? 6.4 : 6.1) + (t.isPrice ? 10 : 9));
      const x = m.l + plotW + 3;
      annotLayer.appendChild(s('rect', {
        x, y: t.ty - h / 2, width: w, height: h, rx: 3,
        fill: t.color, opacity: t.isPrice ? 1 : 0.92,
      }));
      annotLayer.appendChild(s('text', {
        x: x + w / 2, y: t.ty + (t.isPrice ? 4 : 3.7), fill: C.surface,
        'font-size': t.isPrice ? 10.5 : 10,
        'font-weight': t.isPrice ? 700 : 600, 'text-anchor': 'middle',
        'font-variant-numeric': 'tabular-nums',
      }, text));
      // A 2px stub back to the plot edge, so a tag that had to be nudged still
      // reads as belonging to a line rather than floating in the gutter.
      annotLayer.appendChild(s('line', {
        x1: m.l + plotW, y1: t.y, x2: x, y2: t.ty,
        stroke: t.color, 'stroke-width': 1, opacity: 0.5,
      }));
    });

    // Hide any tick label a tag now covers.
    gridLayer.querySelectorAll('text').forEach((el) => {
      const ty = parseFloat(el.getAttribute('y'));
      if (tags.some((t) => Math.abs(ty - t.ty) < TAG_H)) el.setAttribute('opacity', '0');
    });

    /* Raise the pulsing marker above the tag that was covering it.
     *
     * The tag sits 3px right of the plot edge and draws a leader line back to
     * the price, and that line runs straight over the last point, which is
     * exactly where the live dot is. appendChild on an existing child moves it,
     * so this re-stacks rather than duplicating.
     *
     * Only when valueTags is on: with no tags there is nothing above it, and
     * moving it would put the marker over the crosshair instead. */
    liveMarks.forEach((el) => root.appendChild(el));
  }

  /* Dated events pinned to the price line — insider transactions, in practice.
   *
   * A triangle at the price on the day, pointing the way the trade went, with a
   * stem down to the axis so the date is findable. Buys and sells are the same
   * shape flipped rather than two different glyphs: the direction IS the
   * information, and a reader should not have to learn a legend to see it.
   *
   * Labels are only drawn for the largest few. Ten insider prints on a
   * three-month chart, each labelled, is a wall of text over the price, so size
   * decides who gets named.
   *
   * Every marker carries a <title> regardless, which is what makes the
   * unlabelled ones readable. This comment used to claim the hover tooltip
   * carried them and nothing did: insiderEvents built a detail string with the
   * insider's name and position, and no code ever rendered it. An unlabelled
   * triangle was therefore mute, which is indistinguishable from decoration.
   *
   * A native <title> rather than the chart's own tooltip: it needs no listener,
   * survives every redraw, and works on a marker only a few pixels wide, where
   * a scrub binding competes with the crosshair underneath it.
   */
  if (events && events.length) {
    const evLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.9 : null });
    root.appendChild(evLayer);
    const closes = (candles && candles.close) || (series[0] && series[0].values) || [];
    // Label the three biggest by value; the rest are marks only.
    const ranked = [...events]
      .filter((e) => Number.isFinite(e.index) && e.index >= 0 && e.index < n)
      .sort((a, b) => (b.value || 0) - (a.value || 0));
    const named = new Set(ranked.slice(0, 3).map((e) => e.index));

    ranked.forEach((e) => {
      const price = closes[e.index];
      if (price === null || price === undefined || !isFinite(price)) return;
      const x = X(e.index);
      const y = Y(price);
      const buy = e.kind === 'buy';
      const colour = buy ? EVENT_BUY : EVENT_SELL;
      // Below the price for a buy, above for a sell, so the marker never sits on
      // the line it is annotating.
      const tip = buy ? y + 9 : y - 9;
      const base = buy ? y + 20 : y - 20;
      // One group per event so the triangle, its stem and the title move
      // together, and so the hover target is the whole marker rather than five
      // pixels of a path.
      const mark = s('g', { style: 'cursor:help' });
      // The shape flips through tip/base rather than through two path strings:
      // for a buy, tip sits below base, which turns the same three points into
      // an upward triangle.
      mark.appendChild(s('path', {
        d: `M ${x} ${tip} L ${x - 5} ${base} L ${x + 5} ${base} Z`,
        fill: colour, opacity: 0.92,
      }));
      mark.appendChild(s('line', {
        x1: x, y1: y, x2: x, y2: tip, stroke: colour, 'stroke-width': 1, opacity: 0.5,
      }));
      // A wider invisible target: a 10px triangle is a hard thing to hit.
      mark.appendChild(s('rect', {
        x: x - 8, y: Math.min(y, base) - 4, width: 16,
        height: Math.abs(base - y) + 8, fill: 'transparent',
      }));
      if (e.detail || e.label) {
        mark.appendChild(s('title', {}, e.detail || e.label));
      }
      evLayer.appendChild(mark);
      if (named.has(e.index) && e.label) {
        const w = e.label.length * 5.4 + 10;
        const lx = Math.min(Math.max(m.l + 2, x - w / 2), m.l + plotW - w - 2);
        const ly = buy ? base + 13 : base - 5;
        evLayer.appendChild(s('rect', {
          x: lx, y: ly - 9.5, width: w, height: 13, rx: 3,
          fill: C.surface, opacity: 0.88,
        }));
        evLayer.appendChild(s('text', {
          x: lx + 5, y: ly, fill: colour, 'font-size': 10,
        }, e.label));
      }
    });
  }

  labeled.forEach((r) => {
    const w = r.text.length * 5.5 + 10;
    // Which edge to hug. Right by default: on a chart showing months, the left is
    // where the series begins and tags stacked there sat on top of the price.
    // On a multi-year chart the opposite is true — the newest bars crowd the right
    // edge, so the labels covered exactly the part being read.
    const x = refLabelSide === 'left' ? m.l + 2 : m.l + plotW - w - 2;
    annotLayer.appendChild(s('rect', {
      x, y: r.y - 9.5, width: w, height: 13, rx: 3,
      fill: C.surface, opacity: 0.86,
    }));
    annotLayer.appendChild(s('text', {
      x: x + 5, y: r.y, fill: r.color, 'font-size': 10, opacity: 0.9,
      'font-variant-numeric': 'tabular-nums',
    }, r.text));
  });

  /* The date axis, and its gridlines.
   *
   * The gridlines matter as much as the labels: a tick at the bottom edge tells
   * you where a month began, a line through the plot tells you which bars are
   * inside it. The reference draws both, and reading a candle's date off three
   * labels 200px apart was guesswork without them.
   *
   * 46px minimum gap is measured, not chosen: the widest label the axis emits
   * is a year, "2026", at about 26px in this face at 10px, and 20px of air is
   * the point at which two labels stop reading as one string.
   */
  if (labels.length) {
    const ticks = timeTicks(labels, X, 46);
    if (ticks.length) {
      ticks.forEach((t) => {
        // Into the grid layer, so a date line sits under the price with the
        // price gridlines rather than over it with the annotations.
        gridLayer.appendChild(s('line', {
          x1: X(t.i), y1: m.t, x2: X(t.i), y2: m.t + plotH,
          stroke: C.grid, 'stroke-width': 1, opacity: 0.55,
        }));
        annotLayer.appendChild(s('text', {
          x: X(t.i), y: H - 6, fill: C.muted, 'font-size': 10,
          'text-anchor': 'middle',
        }, t.text));
      });
    } else {
      /* Nothing parsed as a date — a categorical x-axis, which several panels
       * in this app legitimately have (strike, sector, factor name). The old
       * three-mark behaviour is exactly right for those, so it stays as the
       * fallback rather than leaving them with no axis at all. */
      const marks = [0, Math.floor((labels.length - 1) / 2), labels.length - 1];
      marks.forEach((i, k) => {
        annotLayer.appendChild(s('text', {
          x: X(i), y: H - 6, fill: C.muted, 'font-size': 10,
          'text-anchor': k === 0 ? 'start' : k === 2 ? 'end' : 'middle',
        }, labels[i]));
      });
    }
  }

  // ------------------------------------------------------- hover layer
  const cross = s('line', {
    y1: m.t, y2: m.t + plotH, stroke: C.ink2, 'stroke-width': 1, opacity: 0,
  });
  root.appendChild(cross);
  const dots = series.map((se) => {
    const d = s('circle', { r: 4, fill: se.color, stroke: C.surface, 'stroke-width': 2, opacity: 0 });
    root.appendChild(d);
    return d;
  });

  /* ------------------------------------------------- range measurement
   *
   * Drag across the plot (or put two fingers on it) to measure between two
   * points, the way the Stocks app does: two markers, a shaded span, and the
   * change from the first to the second in both dollars and percent.
   *
   * Worth having because a chart answers "what happened" but not "how much" —
   * eyeballing a move off a y-axis is exactly the sort of estimate that turns
   * into a wrong number in someone's head. This reads it off the data.
   *
   * Drawn as its own group appended before the hover layer so the crosshair and
   * dots stay on top of the shading.
   */
  const measureGroup = s('g', { opacity: 0, 'pointer-events': 'none' });
  /* 0.14, not 0.08.
   *
   * At 0.08 against the plot background the shaded span was essentially
   * invisible: the two edge markers read, but the region between them did not,
   * so the gesture looked like two loose lines rather than one measured range.
   * Still light enough to read the price line straight through it, which is the
   * constraint that kept it low in the first place. */
  const measureBand = s('rect', { y: m.t, height: plotH, fill: C.ink2, opacity: 0.14 });
  const measureA = s('line', { y1: m.t, y2: m.t + plotH, stroke: C.ink2, 'stroke-width': 1.2, opacity: 0.75 });
  const measureB = s('line', { y1: m.t, y2: m.t + plotH, stroke: C.ink2, 'stroke-width': 1.2, opacity: 0.75 });
  const measureDotA = s('circle', { r: 4.5, stroke: C.surface, 'stroke-width': 2 });
  const measureDotB = s('circle', { r: 4.5, stroke: C.surface, 'stroke-width': 2 });
  const measureLabel = s('text', {
    y: m.t + 12, 'font-size': 11, 'font-weight': 600, 'text-anchor': 'middle',
  });
  [measureBand, measureA, measureB, measureDotA, measureDotB, measureLabel]
    .forEach((el) => measureGroup.appendChild(el));
  root.appendChild(measureGroup);

  // The series the measurement reads. The first one that isn't hidden — for a
  // candle chart that's the close, which is the right thing to measure.
  const measured = series.find((se) => !se.hidden && (se.values || []).some(
    (v) => v !== null && v !== undefined && isFinite(v))) || series[0];

  const clearMeasure = () => {
    measureGroup.setAttribute('opacity', 0);
    measureAnchor = null;
  };

  function drawMeasure(i, j) {
    if (!measured || i === j) { clearMeasure(); return; }
    const [lo, hi] = i < j ? [i, j] : [j, i];
    const va = measured.values[lo];
    const vb = measured.values[hi];
    if (va === null || vb === null || !isFinite(va) || !isFinite(vb)) { clearMeasure(); return; }

    const xa = X(lo);
    const xb = X(hi);
    measureBand.setAttribute('x', xa);
    measureBand.setAttribute('width', Math.max(xb - xa, 1));
    measureA.setAttribute('x1', xa); measureA.setAttribute('x2', xa);
    measureB.setAttribute('x1', xb); measureB.setAttribute('x2', xb);
    measureDotA.setAttribute('cx', xa); measureDotA.setAttribute('cy', Y(va));
    measureDotB.setAttribute('cx', xb); measureDotB.setAttribute('cy', Y(vb));

    const delta = vb - va;
    const pct = va ? (delta / Math.abs(va)) * 100 : null;
    // Direction colours the readout and both markers, so which way it went is
    // legible without reading the sign.
    const tone = delta > 0 ? C.good : delta < 0 ? C.critical : C.ink2;
    [measureDotA, measureDotB].forEach((d) => d.setAttribute('fill', tone));
    [measureA, measureB].forEach((l) => l.setAttribute('stroke', tone));
    measureLabel.setAttribute('fill', tone);

    const from = labels[lo] || `#${lo + 1}`;
    const to = labels[hi] || `#${hi + 1}`;
    const sign = delta > 0 ? '+' : '';
    measureLabel.textContent = `${from} → ${to}   ${sign}${(valueFormat || yFormat)(delta)}`
      + (pct === null ? '' : `   ${sign}${pct.toFixed(2)}%`);
    // Keep the readout inside the plot at both extremes.
    const mid = Math.min(Math.max((xa + xb) / 2, m.l + 90), m.l + plotW - 90);
    measureLabel.setAttribute('x', mid);
    measureGroup.setAttribute('opacity', 1);
  }

  let measureAnchor = null;      // index where the drag or first finger landed

  const indexFromClientX = (clientX) => {
    const box = root.getBoundingClientRect();
    const scale = W / box.width;
    const localX = (clientX - box.left) * scale;
    return Math.max(0, Math.min(n - 1, Math.round(((localX - m.l) / plotW) * (n - 1))));
  };

  // Covers the whole chart, not just the plot rectangle.
  //
  // It used to be inset to the plot, which left three dead zones a gesture could
  // land in and appear broken: the 58px axis gutter on the right, the date strip
  // along the bottom, and the top margin. Nine percent of the width and a strip
  // at each edge where nothing happened. x is clamped to a valid bar index
  // anyway, so extending the target costs nothing and removes the guesswork
  // about where the chart is "live".
  const overlay = s('rect', {
    x: 0, y: 0, width: W, height: H, fill: 'transparent',
    style: 'cursor:crosshair',
  });

  // Two fingers measures directly, one endpoint per finger. Handled before the
  // scrub binding so a pinch never reaches the single-point crosshair, and
  // preventDefault is scoped to the two-finger case so one finger still scrolls.
  overlay.addEventListener('touchmove', (evt) => {
    if (evt.touches.length < 2) return;
    evt.preventDefault();
    hideTip();
    drawMeasure(indexFromClientX(evt.touches[0].clientX),
                indexFromClientX(evt.touches[1].clientX));
  }, { passive: false });
  ['touchend', 'touchcancel'].forEach((type) => {
    overlay.addEventListener(type, (evt) => {
      // Lifting one of two fingers ends the measurement rather than leaving it
      // pinned to wherever the fingers happened to be.
      if (evt.touches.length < 2) clearMeasure();
    });
  });

  // Mouse drag: press sets the anchor, movement extends, release clears. The
  // measurement lives only as long as the gesture — leaving it on screen meant a
  // stale span sat over the chart until it was dismissed, which reads as part of
  // the drawing rather than as something you did.
  //
  // Both move and release are tracked on `window` for the duration of the drag,
  // not on the chart. Listening on the element meant the measurement froze the
  // instant the cursor drifted above or below the plot band — which happens
  // constantly, because dragging sideways across a chart is not a straight line.
  // The gesture now continues wherever the mouse goes and ends wherever it is
  // released, which is what every other drag on a computer does.
  const onDragMove = (evt) => {
    if (measureAnchor === null) return;
    if (evt.buttons !== 1) { endDrag(); return; }   // button released off-window
    drawMeasure(measureAnchor, indexFromClientX(evt.clientX));
  };
  function endDrag() {
    window.removeEventListener('mousemove', onDragMove);
    window.removeEventListener('mouseup', endDrag);
    clearMeasure();
  }
  overlay.addEventListener('mousedown', (evt) => {
    if (evt.button !== 0) return;
    /* On a pannable chart this needs shift; everywhere else a plain drag does it.
     *
     * Returning without preventDefault matters as much as not measuring: the
     * pan handler is delegated on the document, so the event still reaches it,
     * and swallowing the default here would break the gesture it is deferring
     * to. */
    if (panDrag && !evt.shiftKey) return;
    evt.preventDefault();            // no text-selection drag over the chart
    measureAnchor = indexFromClientX(evt.clientX);
    window.addEventListener('mousemove', onDragMove);
    window.addEventListener('mouseup', endDrag);
  });

  bindScrub(overlay, (evt) => {
    const box = root.getBoundingClientRect();
    const scale = W / box.width;
    const localX = (evt.clientX - box.left) * scale;
    let i = Math.round(((localX - m.l) / plotW) * (n - 1));
    i = Math.max(0, Math.min(n - 1, i));
    cross.setAttribute('x1', X(i));
    cross.setAttribute('x2', X(i));
    cross.setAttribute('opacity', 0.45);
    const rows = [];
    // Open, high and low first, when the caller supplied candles. The series
    // loop below only sees closing values, so on a candle chart the readout
    // named a single price for a bar that has four — and the range is usually
    // the thing being hovered for.
    if (candles && candles.open) {
      const o = candles.open[i], h = candles.high[i], l = candles.low[i];
      if ([o, h, l].every((v) => v !== null && v !== undefined && isFinite(v))) {
        rows.push(['Open', yFormat(o)]);
        rows.push(['High', yFormat(h)]);
        rows.push(['Low', yFormat(l)]);
      }
    }
    series.forEach((se, k) => {
      const v = se.values[i];
      if (v === null || v === undefined || !isFinite(v)) { dots[k].setAttribute('opacity', 0); return; }
      dots[k].setAttribute('cx', X(i));
      dots[k].setAttribute('cy', Y(v));
      dots[k].setAttribute('opacity', 1);
      rows.push([
        `<span style="color:${se.color}">■</span> ${se.name}`,
        (valueFormat || yFormat)(v),
      ]);
    });
    // Volume for the same bar. Shown in full rather than abbreviated: the point
    // of hovering a bar is to read the actual figure, and "144.3M" is what the
    // axis already told you.
    if (volRows) {
      const vv = volRows[i];
      if (vv !== null && vv !== undefined && isFinite(vv)) {
        rows.push(['Volume', Math.round(vv).toLocaleString()]);
      }
      volBars.forEach((b, k) => {
        if (!b) return;
        b.setAttribute('opacity', k === i ? 0.95 : 0.42);
      });
    }
    showTip(tipRows(labels[i] || `#${i + 1}`, rows), evt);
    // Tell the caller which bar is under the cursor, so a header or legend can
    // track it. Index only: this function knows nothing about what the caller
    // wants to display, and passing the bar would mean guessing.
    if (onHover) onHover(i);
  }, () => {
    hideTip();
    cross.setAttribute('opacity', 0);
    dots.forEach((d) => d.setAttribute('opacity', 0));
    volBars.forEach((b) => b && b.setAttribute('opacity', 0.42));
    // null means "cursor gone" — distinct from bar 0, which is a real bar.
    if (onHover) onHover(null);
  });
  root.appendChild(overlay);

  /* The coordinate frame, hung on the node.
   *
   * A drawing layer has to convert between screen pixels and (bar index, price),
   * and only this function knows the margins, the plot size and the price domain
   * it settled on. Recomputing them outside would mean duplicating the whole
   * domain-fitting chain — including the reference-line slack and the band
   * inclusion rules — and any drift would put every drawing slightly wrong.
   *
   * Exposed as a property rather than a return value so nothing that already
   * calls lineChart has to change.
   */
  root.chartFrame = {
    width, height, margin: m, plotW, priceH,
    lo, hi, bars: n, labels,
    // Pixel from data, and data from pixel. Kept as closures over the same
    // scales the chart drew with, so they cannot disagree with what is on screen.
    xOf: (i) => X(i),
    yOf: (v) => Y(v),
    indexAt: (px) => (n <= 1 ? 0
      : Math.round(((px - m.l) / plotW) * (n - 1))),
    priceAt: (py) => hi - ((py - m.t) / priceH) * (hi - lo),
  };

  return root;
}

function legend(items, boxed = false) {
  const div = document.createElement('div');
  div.className = 'legend';
  items.forEach((it) => {
    const key = document.createElement('span');
    key.className = 'key';
    const sw = document.createElement('span');
    sw.className = 'swatch' + (boxed ? ' box' : '');
    sw.style.background = it.color;
    if (it.dash) sw.style.background = `repeating-linear-gradient(90deg, ${it.color} 0 3px, transparent 3px 6px)`;
    /* Two-tone swatch, for something that is drawn in one of two colours
     * depending on its own state — an EMA cloud is the case this exists for.
     * A single-colour key would name the ribbon after only half of what it
     * does, and two legend rows for one overlay is worse than one honest key.
     * Hard stops, not a blend: the two states are discrete. */
    if (it.split) sw.style.background = `linear-gradient(90deg, ${it.color} 0 50%, ${it.split} 50% 100%)`;
    key.appendChild(sw);
    key.appendChild(document.createTextNode(it.name));
    div.appendChild(key);
  });
  return div;
}

/* -------------------------------------------------- horizontal bar charts */

/**
 * Diverging horizontal bars around a zero axis. Used for GEX by strike and
 * net premium by strike, where the sign is the whole point.
 */
function divergingBars(opts) {
  const {
    rows = [], height = null, posColor = C.pos, negColor = C.neg,
    format = (v) => fmtCompact(v), rowHeight = 20, markerRow = null,
    markerLabel = 'spot', axisLabel = '', width = 720,
  } = opts;

  if (!rows.length) return document.createTextNode('');

  const W = width;
  const barH = Math.min(16, rowHeight - 6);
  const H = height || rows.length * rowHeight + 30;
  const m = { t: 8, r: 74, b: 20, l: 58 };
  const plotW = W - m.l - m.r;
  const plotH = H - m.t - m.b;

  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.value || 0)), 1);
  const mid = m.l + plotW / 2;
  const X = (v) => mid + (v / maxAbs) * (plotW / 2);
  const Y = (i) => m.t + (i + 0.5) * (plotH / rows.length);

  const root = svgRoot(W, H);

  root.appendChild(s('line', {
    x1: mid, y1: m.t, x2: mid, y2: m.t + plotH, stroke: C.baseline, 'stroke-width': 1,
  }));

  rows.forEach((r, i) => {
    const v = r.value || 0;
    const y = Y(i) - barH / 2;
    const w = Math.abs(X(v) - mid);
    const x = v >= 0 ? mid : mid - w;
    const color = v >= 0 ? posColor : negColor;

    // 4px rounded data-end, square against the zero baseline.
    const rx = Math.min(4, w);
    const path = v >= 0
      ? `M${mid},${y} H${mid + Math.max(w - rx, 0)} q${rx},0 ${rx},${rx} v${barH - 2 * rx} q0,${rx} -${rx},${rx} H${mid} Z`
      : `M${mid},${y} H${x + rx} q-${rx},0 -${rx},${rx} v${barH - 2 * rx} q0,${rx} ${rx},${rx} H${mid} Z`;
    const bar = s('path', { d: w < 1 ? `M${mid},${y} h1 v${barH} h-1 Z` : path, fill: color });
    bindScrub(bar, (evt) => showTip(
      tipRows(r.label, (r.detail || [['Value', format(v)]])), evt,
    ), hideTip);
    root.appendChild(bar);

    root.appendChild(s('text', {
      x: m.l - 8, y: Y(i) + 3.5, fill: C.ink2, 'font-size': 10, 'text-anchor': 'end',
      'font-variant-numeric': 'tabular-nums',
    }, r.label));

    root.appendChild(s('text', {
      x: v >= 0 ? m.l + plotW + 6 : m.l + plotW + 6,
      y: Y(i) + 3.5, fill: C.muted, 'font-size': 10, 'font-variant-numeric': 'tabular-nums',
    }, format(v)));
  });

  if (markerRow !== null && markerRow !== undefined && rows.length > 1) {
    const y = m.t + Math.max(0, Math.min(rows.length, markerRow)) * (plotH / rows.length);
    root.appendChild(s('line', {
      x1: m.l - 4, y1: y, x2: m.l + plotW, y2: y,
      stroke: C.warn, 'stroke-width': 1, 'stroke-dasharray': '4 3',
    }));
    root.appendChild(s('text', {
      x: m.l - 8, y: y - 3, fill: C.warn, 'font-size': 10, 'text-anchor': 'end',
    }, markerLabel));
  }

  if (axisLabel) {
    root.appendChild(s('text', {
      x: mid, y: H - 5, fill: C.muted, 'font-size': 10, 'text-anchor': 'middle',
    }, axisLabel));
  }

  return root;
}

/** Inline mini bar for table cells: one measure, diverging around zero. */
function inlineBar(value, maxAbs, width = 76, height = 9) {
  const root = svgRoot(width, height);
  root.setAttribute('width', width);
  root.setAttribute('height', height);
  root.style.width = width + 'px';
  const mid = width / 2;
  root.appendChild(s('line', { x1: mid, y1: 0, x2: mid, y2: height, stroke: C.baseline, 'stroke-width': 1 }));
  if (value !== null && isFinite(value) && maxAbs > 0) {
    const w = Math.max(1.5, (Math.abs(value) / maxAbs) * (width / 2 - 1));
    root.appendChild(s('rect', {
      x: value >= 0 ? mid : mid - w, y: 1, width: w, height: height - 2, rx: 2,
      fill: value >= 0 ? C.pos : C.neg,
    }));
  }
  return root;
}

/** Sparkline: one series, no legend, no axis — the number beside it carries the value. */
function sparkline(values, width = 96, height = 26, color = C.s1) {
  const clean = (values || []).filter((v) => v !== null && isFinite(v));
  if (clean.length < 2) return document.createTextNode('');
  const lo = Math.min(...clean), hi = Math.max(...clean);
  const span = hi - lo || 1;
  const root = svgRoot(width, height);
  root.setAttribute('width', width);
  root.setAttribute('height', height);
  root.style.width = width + 'px';
  const pts = clean.map((v, i) => {
    const x = (i / (clean.length - 1)) * (width - 4) + 2;
    const y = height - 3 - ((v - lo) / span) * (height - 6);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  root.appendChild(s('polyline', {
    points: pts.join(' '), fill: 'none', stroke: color, 'stroke-width': 1.5,
    'stroke-linejoin': 'round', 'stroke-linecap': 'round',
  }));
  const last = pts[pts.length - 1].split(',');
  root.appendChild(s('circle', {
    cx: last[0], cy: last[1], r: 2.5, fill: color, stroke: C.surface, 'stroke-width': 1.5,
  }));
  return root;
}

/**
 * MACD panel: histogram columns plus the MACD and signal lines. One unit,
 * one scale — the histogram is the difference of the two lines, so they share
 * an axis legitimately.
 */
/* Histogram colours, deliberately not the MACD line's.
 *
 * These were C.pos and C.neg, and C.pos is the same hex as C.s1 — so the bars
 * and the MACD line rendered identically and the legend carried two matching
 * blue swatches. Green above zero and red below also states the sign the bars
 * already encode, which the blue never did. */
// Buy/sell green and red, NOT C.pos — which is blue and the same hex as C.s1.
const EVENT_BUY = C.s3;
const EVENT_SELL = C.neg;

const MACD_HIST_POS = C.s3;
const MACD_HIST_NEG = C.neg;

function macdChart(macd, signal, hist, labels, width = 720, opts = {}) {
  // Taller than the old 150px. The panel's job is to show which side of the
  // signal line MACD is on, and at 118px of plot height two series a couple of
  // points apart were a single thick stroke.
  const W = width, H = 210;
  const m = { t: 10, r: 58, b: 22, l: 8 };  // b leaves room for the date row
  const plotW = W - m.l - m.r, plotH = H - m.t - m.b;
  const all = [...macd, ...signal, ...hist].filter((v) => v !== null && isFinite(v));
  if (!all.length) return document.createTextNode('');
  let lo = Math.min(...all, 0), hi = Math.max(...all, 0);
  const pad = (hi - lo) * 0.1 || 1;
  lo -= pad; hi += pad;
  const n = macd.length;
  const X = (i) => m.l + (i / (n - 1)) * plotW;
  const Y = (v) => m.t + plotH - ((v - lo) / (hi - lo)) * plotH;

  const root = svgRoot(W, H);
  // Same draw-on treatment as the price chart, and for the same reason: the two
  // panels sit one above the other, so if only one of them animated the pair
  // would look broken rather than restrained.
  const animating = animateNextChart && !reducedMotion();
  const seriesDelay = makeStagger();

  const gridLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.45 : null });
  root.appendChild(gridLayer);
  niceTicks(lo, hi, 3).forEach((t) => {
    gridLayer.appendChild(s('line', { x1: m.l, y1: Y(t), x2: m.l + plotW, y2: Y(t), stroke: C.grid, 'stroke-width': 1 }));
    gridLayer.appendChild(s('text', { x: m.l + plotW + 6, y: Y(t) + 3.5, fill: C.muted, 'font-size': 10 }, fmt(t, 2)));
  });
  gridLayer.appendChild(s('line', { x1: m.l, y1: Y(0), x2: m.l + plotW, y2: Y(0), stroke: C.baseline, 'stroke-width': 1 }));

  // The histogram is data, so it arrives with the lines rather than with the
  // frame — one fade for the whole set, not 126 individually animated columns.
  const histLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.55 : null });
  root.appendChild(histLayer);
  const bw = Math.max(1.5, (plotW / n) - 2); // 2px surface gap between columns
  hist.forEach((v, i) => {
    if (v === null || !isFinite(v)) return;
    const y0 = Y(0), y1 = Y(v);
    const h = Math.abs(y1 - y0);
    histLayer.appendChild(s('rect', {
      x: X(i) - bw / 2, y: Math.min(y0, y1), width: bw, height: Math.max(h, 1),
      // Green above zero rather than the MACD line's blue. The bars and the line
      // are different quantities and must not share a hue; green/red also matches
      // the sign convention the histogram is already encoding.
      fill: v >= 0 ? MACD_HIST_POS : MACD_HIST_NEG, opacity: 0.5,
      rx: Math.min(2, bw / 2),
    }));
  });

  /* Mark the last crossover. This is the one event the panel exists to show, and
   * finding it by eye on overlapping lines is exactly what it shouldn't require. */
  const xover = opts.cross;
  if (xover && xover.index >= 0 && xover.index < n) {
    const cx = X(xover.index);
    const tone = xover.bullish ? C.good : C.critical;
    // The cross is the panel's conclusion, so it lands after the lines that
    // justify it — the same ordering the price chart gives its levels.
    const xoverLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.8 : null });
    root.appendChild(xoverLayer);
    xoverLayer.appendChild(s('line', {
      x1: cx, y1: m.t, x2: cx, y2: m.t + plotH, stroke: tone,
      'stroke-width': 1.4, 'stroke-dasharray': '6 4', opacity: 0.75,
    }));
    // A dot at the intersection itself, so the eye lands on the level too.
    if (isFinite(macd[xover.index])) {
      xoverLayer.appendChild(s('circle', {
        cx, cy: Y(macd[xover.index]), r: 3.4, fill: tone,
        stroke: C.surface, 'stroke-width': 1.5,
      }));
    }
    // Label placed inside whichever half has room.
    const nearRight = cx > m.l + plotW * 0.62;
    xoverLayer.appendChild(s('text', {
      x: nearRight ? cx - 6 : cx + 6, y: m.t + 11, fill: tone, 'font-size': 10,
      'font-weight': 600, 'text-anchor': nearRight ? 'end' : 'start',
    }, `${xover.bullish ? 'Bullish' : 'Bearish'} cross${
      xover.barsAgo
        ? ` · ${xover.barsAgo} ${opts.unit || 'bar'}${xover.barsAgo === 1 ? '' : 's'} ago`
        : ' · latest bar'}`));
  }

  [[macd, C.s1, 'MACD'], [signal, C.s4, 'Signal']].forEach(([vals, color]) => {
    const pts = vals.map((v, i) => (v === null || !isFinite(v) ? null : `${X(i).toFixed(1)},${Y(v).toFixed(1)}`))
      .filter(Boolean);
    if (pts.length) {
      root.appendChild(s('polyline', {
        points: pts.join(' '), fill: 'none', stroke: color, 'stroke-width': 2,
        'stroke-linejoin': 'round', 'stroke-linecap': 'round',
        // MACD sweeps first, the signal line chases it 70ms behind — which is
        // the relationship the panel is there to show.
        'data-draw': animating ? seriesDelay() : null,
      }));
    }
  });

  if (labels && labels.length) {
    const axisLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.85 : null });
    root.appendChild(axisLayer);
    const marks = [0, Math.floor((labels.length - 1) / 2), labels.length - 1];
    marks.forEach((i, k) => {
      axisLayer.appendChild(s('text', {
        x: X(i), y: H - 5, fill: C.muted, 'font-size': 10,
        'text-anchor': k === 0 ? 'start' : k === 2 ? 'end' : 'middle',
      }, labels[i]));
    });
  }

  const cross = s('line', { y1: m.t, y2: m.t + plotH, stroke: C.ink2, 'stroke-width': 1, opacity: 0 });
  root.appendChild(cross);
  const overlay = s('rect', { x: m.l, y: m.t, width: plotW, height: plotH, fill: 'transparent', style: 'cursor:crosshair' });
  bindScrub(overlay, (evt) => {
    const box = root.getBoundingClientRect();
    const scale = W / box.width;
    let i = Math.round((((evt.clientX - box.left) * scale) - m.l) / plotW * (n - 1));
    i = Math.max(0, Math.min(n - 1, i));
    cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('opacity', 0.45);
    showTip(tipRows(labels[i] || '', [
      [`<span style="color:${C.s1}">■</span> MACD`, fmt(macd[i], 3)],
      [`<span style="color:${C.s4}">■</span> Signal`, fmt(signal[i], 3)],
      ['Histogram', fmt(hist[i], 3)],
    ]), evt);
  }, () => { hideTip(); cross.setAttribute('opacity', 0); });
  root.appendChild(overlay);
  return root;
}

/* ------------------------------------------------------ relative rotation
 *
 * Sectors plotted on relative strength against relative momentum, both centred
 * on 100, with a tail behind each showing where it came from.
 *
 * Two decisions worth stating. The axes are drawn on a *shared, symmetric*
 * range around 100 rather than each fitted to its own data: an asymmetric fit
 * moves the crossing point off-centre, and the whole chart is a statement about
 * which side of 100 things are on. And the tail is drawn as a fading polyline
 * rather than a series of equal dots, so direction is readable without a legend
 * — the bright end is now.
 */
function rotationChart(sectors, opts = {}) {
  const width = opts.width || 720;
  const height = opts.height || 520;
  const m = { l: 44, r: 16, t: 16, b: 34 };
  const plotW = width - m.l - m.r;
  const plotH = height - m.t - m.b;

  // One symmetric range for both axes, so 100 sits dead centre and a point's
  // distance from the middle means the same horizontally as vertically.
  let reach = 0;
  sectors.forEach((sec) => (sec.path || []).forEach((p) => {
    reach = Math.max(reach, Math.abs((p.strength ?? 100) - 100),
      Math.abs((p.momentum ?? 100) - 100));
  }));
  reach = Math.max(reach * 1.15, 1.2);
  const lo = 100 - reach, hi = 100 + reach;

  const X = (v) => m.l + ((v - lo) / (hi - lo)) * plotW;
  const Y = (v) => m.t + plotH - ((v - lo) / (hi - lo)) * plotH;

  const root = svgRoot(width, height);
  root.setAttribute('aria-label', 'Sector relative rotation');

  const cx = X(100), cy = Y(100);

  // Quadrant washes. Very low alpha — they are there to name the regions, not
  // to compete with the data drawn on top of them.
  const quads = [
    { x: cx, y: m.t, w: m.l + plotW - cx, h: cy - m.t, fill: C.good, label: 'Leading', anchor: 'end' },
    { x: m.l, y: m.t, w: cx - m.l, h: cy - m.t, fill: C.s1, label: 'Improving', anchor: 'start' },
    { x: m.l, y: cy, w: cx - m.l, h: m.t + plotH - cy, fill: C.critical, label: 'Lagging', anchor: 'start' },
    { x: cx, y: cy, w: m.l + plotW - cx, h: m.t + plotH - cy, fill: C.warn, label: 'Weakening', anchor: 'end' },
  ];
  quads.forEach((q) => {
    if (q.w <= 0 || q.h <= 0) return;
    root.appendChild(s('rect', { x: q.x, y: q.y, width: q.w, height: q.h,
      fill: q.fill, opacity: 0.07 }));
    root.appendChild(s('text', {
      x: q.anchor === 'end' ? q.x + q.w - 8 : q.x + 8,
      y: q.y + (q.label === 'Leading' || q.label === 'Improving' ? 18 : q.h - 8),
      'text-anchor': q.anchor, fill: q.fill, 'font-size': 11,
      'font-weight': 600, opacity: 0.75,
    }, q.label));
  });

  // Grid, then the two centre lines on top of it.
  niceTicks(lo, hi, 5).forEach((t) => {
    if (t <= lo || t >= hi) return;
    root.appendChild(s('line', { x1: X(t), x2: X(t), y1: m.t, y2: m.t + plotH,
      stroke: C.grid, 'stroke-width': 1, opacity: 0.5 }));
    root.appendChild(s('line', { x1: m.l, x2: m.l + plotW, y1: Y(t), y2: Y(t),
      stroke: C.grid, 'stroke-width': 1, opacity: 0.5 }));
    root.appendChild(s('text', { x: X(t), y: m.t + plotH + 16, 'text-anchor': 'middle',
      fill: C.muted, 'font-size': 10 }, fmt(t, 0)));
    root.appendChild(s('text', { x: m.l - 8, y: Y(t) + 3, 'text-anchor': 'end',
      fill: C.muted, 'font-size': 10 }, fmt(t, 0)));
  });
  root.appendChild(s('line', { x1: cx, x2: cx, y1: m.t, y2: m.t + plotH,
    stroke: C.baseline, 'stroke-width': 1.5 }));
  root.appendChild(s('line', { x1: m.l, x2: m.l + plotW, y1: cy, y2: cy,
    stroke: C.baseline, 'stroke-width': 1.5 }));

  const SLOTS = [C.s1, C.s2, C.s3, C.s4, C.s5, C.s6, C.s7, C.s8, C.good, C.warn, C.refSR];

  sectors.forEach((sec, i) => {
    const colour = SLOTS[i % SLOTS.length];
    const path = (sec.path || []).filter(
      (p) => Number.isFinite(p.strength) && Number.isFinite(p.momentum));
    if (!path.length) return;

    // The tail as a curve, not a dogleg.
    //
    // Rotation is a continuous motion and straight segments between weekly
    // samples draw it as a series of sharp turns the sector never made — with
    // eleven of them overlapping, the chart read as a tangle of zigzags rather
    // than as eleven arcs. A Catmull-Rom spline passes exactly through every
    // measured point (it interpolates rather than approximates, so no reading is
    // moved) and rounds only the path between them, which is the part that was
    // invented by the straight line anyway.
    //
    // Drawn one bezier per segment rather than as a single path, so opacity can
    // still ramp along the tail: the bright end is now. A single path would need
    // a gradient per sector, and a linear gradient cannot follow a curve.
    const pts = path.map((p) => [X(p.strength), Y(p.momentum)]);
    for (let k = 0; k < pts.length - 1; k += 1) {
      const p0 = pts[k - 1] || pts[k];
      const p1 = pts[k];
      const p2 = pts[k + 1];
      const p3 = pts[k + 2] || p2;
      // Catmull-Rom to cubic bezier. The sixth is the standard tension; higher
      // overshoots on a tight reversal, which on this chart would draw a sector
      // crossing a quadrant boundary it never crossed.
      const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
      const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      root.appendChild(s('path', {
        d: `M${p1[0].toFixed(1)},${p1[1].toFixed(1)}`
          + ` C${c1[0].toFixed(1)},${c1[1].toFixed(1)}`
          + ` ${c2[0].toFixed(1)},${c2[1].toFixed(1)}`
          + ` ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`,
        fill: 'none', stroke: colour, 'stroke-width': 1.8,
        'stroke-linecap': 'round',
        opacity: 0.16 + 0.64 * ((k + 1) / (pts.length - 1 || 1)),
      }));
    }
    path.slice(0, -1).forEach((p, k) => {
      root.appendChild(s('circle', { cx: X(p.strength), cy: Y(p.momentum), r: 2,
        fill: colour, opacity: 0.2 + 0.5 * (k / (path.length - 1 || 1)) }));
    });

    const last = path[path.length - 1];
    const dot = s('circle', { cx: X(last.strength), cy: Y(last.momentum), r: 5.5,
      fill: colour, stroke: C.surface, 'stroke-width': 1.5 });
    root.appendChild(dot);
    root.appendChild(s('text', {
      x: X(last.strength) + 9, y: Y(last.momentum) + 4,
      fill: colour, 'font-size': 11, 'font-weight': 600,
    }, sec.symbol));

    // The hit area is deliberately larger than the dot: eleven labelled points
    // on a 720px square are close together, and a 5px target is a miss.
    const hit = s('circle', { cx: X(last.strength), cy: Y(last.momentum), r: 14,
      fill: 'transparent', style: 'cursor:pointer' });
    hit.addEventListener('mouseenter', (evt) => showTip(tipRows(
      `${sec.symbol} · ${sec.name}`, [
        ['Quadrant', sec.quadrant],
        ['Relative strength', fmt(last.strength, 2)],
        ['Relative momentum', fmt(last.momentum, 2)],
        ['Change on the week', `${fmt(sec.d_strength, 2)} strength, ${fmt(sec.d_momentum, 2)} momentum`],
        ['Tail', `${path.length} weeks to ${last.date}`],
      ]), evt));
    hit.addEventListener('mouseleave', hideTip);
    root.appendChild(hit);
  });

  return root;
}

/* --------------------------------------------------------- bubble chart
 *
 * Two measures against each other with size as a third. The shape a treemap
 * cannot make: a treemap shows weight and a scatter shows relationship, and
 * "are we paying more for less growth" is a relationship.
 *
 * Bubble AREA is proportional to the size measure, not its radius. Scaling the
 * radius linearly is the classic error and it exaggerates the largest item by
 * its square — a company twice the size looks four times as big.
 */
function bubbleChart(points, opts = {}) {
  const width = opts.width || 720;
  const height = opts.height || 420;
  const m = { l: 58, r: 18, t: 16, b: 44 };
  const plotW = width - m.l - m.r;
  const plotH = height - m.t - m.b;

  const usable = (points || []).filter(
    (p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  const root = svgRoot(width, height);
  if (!usable.length) return root;

  const xs = usable.map((p) => p.x);
  const ys = usable.map((p) => p.y);
  const pad = (lo, hi) => {
    const span = hi - lo || Math.abs(hi) || 1;
    return [lo - span * 0.12, hi + span * 0.12];
  };
  const [x0, x1] = pad(Math.min(...xs), Math.max(...xs));
  const [y0, y1] = pad(Math.min(...ys), Math.max(...ys));
  const X = (v) => m.l + ((v - x0) / (x1 - x0)) * plotW;
  const Y = (v) => m.t + plotH - ((v - y0) / (y1 - y0)) * plotH;

  const sizes = usable.map((p) => Math.abs(p.size) || 0);
  const maxSize = Math.max(...sizes, 1);
  // Area proportional to the measure, so radius goes as the square root.
  const R = (v) => 5 + Math.sqrt((Math.abs(v) || 0) / maxSize) * 22;

  // Grid and axes.
  niceTicks(x0, x1, 5).forEach((t) => {
    root.appendChild(s('line', { x1: X(t), x2: X(t), y1: m.t, y2: m.t + plotH,
      stroke: C.grid, 'stroke-width': 1, opacity: 0.5 }));
    root.appendChild(s('text', { x: X(t), y: m.t + plotH + 16, 'text-anchor': 'middle',
      fill: C.muted, 'font-size': 10 },
    fmt(t, Math.abs(t) < 10 ? 1 : 0) + (opts.xUnit === '%' ? '%' : '')));
  });
  niceTicks(y0, y1, 5).forEach((t) => {
    root.appendChild(s('line', { x1: m.l, x2: m.l + plotW, y1: Y(t), y2: Y(t),
      stroke: C.grid, 'stroke-width': 1, opacity: 0.5 }));
    root.appendChild(s('text', { x: m.l - 8, y: Y(t) + 3, 'text-anchor': 'end',
      fill: C.muted, 'font-size': 10 },
    fmt(t, Math.abs(t) < 10 ? 1 : 0) + (opts.yUnit === '%' ? '%' : '')));
  });
  // Zero lines, where zero is inside the range — a scatter of percentages needs
  // to show which side of nothing each point is on.
  if (x0 < 0 && x1 > 0) {
    root.appendChild(s('line', { x1: X(0), x2: X(0), y1: m.t, y2: m.t + plotH,
      stroke: C.baseline, 'stroke-width': 1.5 }));
  }
  if (y0 < 0 && y1 > 0) {
    root.appendChild(s('line', { x1: m.l, x2: m.l + plotW, y1: Y(0), y2: Y(0),
      stroke: C.baseline, 'stroke-width': 1.5 }));
  }

  if (opts.xLabel) {
    root.appendChild(s('text', { x: m.l + plotW / 2, y: height - 6,
      'text-anchor': 'middle', fill: C.muted, 'font-size': 11 }, opts.xLabel));
  }
  if (opts.yLabel) {
    root.appendChild(s('text', {
      x: 12, y: m.t + plotH / 2, 'text-anchor': 'middle', fill: C.muted,
      'font-size': 11, transform: `rotate(-90 12 ${m.t + plotH / 2})`,
    }, opts.yLabel));
  }

  // Biggest first, so a small bubble is never hidden underneath a large one.
  [...usable].sort((a, b) => (Math.abs(b.size) || 0) - (Math.abs(a.size) || 0))
    .forEach((p) => {
      const cx = X(p.x); const cy = Y(p.y); const r = R(p.size);
      const dot = s('circle', {
        cx, cy, r, fill: p.color || C.s1, 'fill-opacity': 0.75,
        stroke: C.surface, 'stroke-width': 1.5, style: 'cursor:pointer',
      });
      dot.addEventListener('mouseenter', (evt) => showTip(tipRows(
        `${p.label}${p.name ? ' · ' + p.name : ''}`, [
          [opts.xLabel || 'x', fmt(p.x, 2) + (opts.xUnit === '%' ? '%' : '')],
          [opts.yLabel || 'y', fmt(p.y, 2) + (opts.yUnit === '%' ? '%' : '')],
          ['Size', fmtCompact(p.size, 1)],
        ]), evt));
      dot.addEventListener('mouseleave', hideTip);
      root.appendChild(dot);
      if (r >= 9) {
        root.appendChild(s('text', {
          x: cx, y: cy + 3.5, 'text-anchor': 'middle', fill: C.ink,
          'font-size': 10, 'font-weight': 600, 'pointer-events': 'none',
        }, p.label));
      }
    });

  return root;
}
