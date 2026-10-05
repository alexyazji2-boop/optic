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
/* Chart typography.
 *
 * Everything drawn on a chart used to be 10px, with weight left unset on the
 * labels that most needed it: a Fibonacci level rendered "23.6 (321.19)" at
 * 10px, weight 400, opacity 0.9, in a colour measuring 5.42:1 against the
 * surface. That is legible in the sense of passing a contrast check at normal
 * size and illegible in the sense that a reader has to lean in, which is what
 * was reported.
 *
 * So the sizes are named and raised, and the labels a reader actually reads --
 * axis ticks, level labels, event markers -- take a weight. Weight buys more
 * legibility per pixel than size at this scale, because the failure is stroke
 * thinness rather than glyph height.
 *
 * `tick` stays a step below `label`: the axis is orientation and the labels are
 * content, and flattening them would leave the plot with no hierarchy at all.
 */
const CF = {
  micro: 10.5,   // session dividers, the densest annotation on the plot
  tick: 11.5,    // axis ticks
  label: 12,     // level labels, event markers, band labels
  tag: 12.5,     // the value tags at the end of each series
  title: 12,     // axis titles
};
const CW = {
  tick: 500,
  label: 600,
  tag: 700,
};

/* The width a stage name is measured at: 10.5px semibold, about 6px a
 * character, estimated rather than measured because the node is not in the
 * document yet (the session captions do the same). */
const STAGE_NAME_CHAR = 6;

// Text for the tooltip, which is HTML: a stage's name comes from the server.
function escapeText(v) {
  return String(v).replace(/[&<>"']/g, (ch) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

const C = {
  ink: '#f5f1ec', ink2: '#c2c6cb', muted: '#9fa3a8',
  grid: '#2c2c2a', baseline: '#383835', surface: '#121010',
  s1: '#3987e5', s2: '#d95926', s3: '#199e70', s4: '#c98500',
  s5: '#d55181', s6: '#5fa617', s7: '#9085e9', s8: '#e66767',
  pos: '#0ca30c', neg: '#d95656',
  good: '#0ca30c', warn: '#fab219', serious: '#ec835a', critical: '#d03b3b',
  // Weinstein stages. --stage-1..4 in styles.css says why these four; the
  // values here are the dark theme's, for the moment before syncChartTheme.
  stage1: '#98d292', stage2: '#0ca30c', stage3: '#fab219', stage4: '#d95656',

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

  /* Optic's gold, the colour of the primary buttons, and the default colour of
   * the one line a chart is about. It was --s1's blue until the owner asked for
   * every chart in the brand colour. --brand follows --btn-primary, so this is
   * #d4b144 on the dark plane and #9a6b00 in the light theme.
   *
   * It sits 22.6 apart from --s4's amber in the dark theme (CIE76), and --warn
   * is 2.7 from it in the light one: the same colour. So the lines drawn
   * beside it by default -- RSI and MACD signals, a second rank window, the
   * contributions line -- moved off amber to --s7's violet (111 and 116), and
   * the gamma flip line to a neutral. Blue stays in the categorical slots,
   * where its job is telling eleven sectors apart, not being the chart. */
  brand: '#d4b144',

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

  /* The moving averages and the EMA clouds, dark values; the light ones are
   * in styles.css. Kept off the categorical slots because four of those sat
   * on the chart's own colours (see OVERLAY_DEFS in app.js). */
  ma1: '#648fd8', ma2: '#bd9efa', ma3: '#c461c9',
  ma4: '#f4c1f6', ma5: '#6b6ff5', ma6: '#a855f7',
  cloudUp: '#648fd8', cloudDown: '#c461c9',
};

// Which CSS custom property backs each slot.
const C_VARS = {
  ink: '--ink', ink2: '--ink-2', muted: '--ink-muted',
  grid: '--grid', baseline: '--baseline', surface: '--surface',
  s1: '--s1', s2: '--s2', s3: '--s3', s4: '--s4',
  s5: '--s5', s6: '--s6', s7: '--s7', s8: '--s8',
  pos: '--pos', neg: '--neg', mid: '--mid',
  good: '--good', warn: '--warn', serious: '--serious', critical: '--critical',
  stage1: '--stage-1', stage2: '--stage-2', stage3: '--stage-3', stage4: '--stage-4',
  accent: '--accent', brand: '--brand',
  refSR: '--ref-sr', refFib: '--ref-fib', refSession: '--ref-session',
  ma1: '--ma-1', ma2: '--ma-2', ma3: '--ma-3', ma4: '--ma-4', ma5: '--ma-5', ma6: '--ma-6',
  cloudUp: '--cloud-up', cloudDown: '--cloud-down',
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

/* The smallest and largest of a list, read in a loop.
 *
 * `Math.min(...list)` passes every value as an argument, and engines cap
 * arguments by stack: Chrome 152 threw "Maximum call stack size exceeded"
 * between 100,000 and 125,000 of them. The price chart pools every series it
 * draws before asking, and on the All range that is IBM's 16,296 sessions in
 * each of ten lines, 162,960 values, so the chart would not have drawn. */
function extentOf(list) {
  let lo = Infinity;
  let hi = -Infinity;
  for (let i = 0; i < list.length; i += 1) {
    if (list[i] < lo) lo = list[i];
    if (list[i] > hi) hi = list[i];
  }
  return [lo, hi];
}

/* The page's ink or its surface, whichever reads better on a fill.
 *
 * For the insider badges, filled in the trade's colour in either theme. The
 * surface (near black) is the one on the dark theme's red and green, about
 * 4.9:1 and 5.5:1; on the light theme's green the surface (near white) was
 * 2.8:1 and its ink is 6.6:1. A colour this cannot read gets the ink. */
function inkOn(fill) {
  const lum = (hex) => {
    const m6 = /^#([0-9a-f]{6})$/i.exec(String(hex || '').trim());
    if (!m6) return null;
    const v = parseInt(m6[1], 16);
    return [v >> 16, (v >> 8) & 255, v & 255].reduce((sum, c, k) => {
      const x = c / 255;
      const lin = x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
      return sum + lin * [0.2126, 0.7152, 0.0722][k];
    }, 0);
  };
  const ratio = (a, b) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  const f = lum(fill), ink = lum(C.ink), surface = lum(C.surface);
  if (f === null || ink === null || surface === null) return C.ink;
  return ratio(f, surface) >= ratio(f, ink) ? C.surface : C.ink;
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
function chartAnimationOn() { return animateNextChart; }

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

/* Draw-ons in progress, as the promises of their animations.
 *
 * So a redraw that only updates a chart can wait for a sweep to finish rather
 * than cut it off. The stage reading is the case that needed it: it lands a
 * moment after the payload, and the redraw it causes replaced the price chart,
 * RSI and MACD with finished copies part-way through their sweep, so on the
 * Charting tab the panes were seen to appear fully drawn. */
const runningDraws = new Set();

function trackDraw(anim) {
  const done = anim.finished.catch(() => {});
  runningDraws.add(done);
  done.then(() => runningDraws.delete(done));
}

/** Run `fn` once no draw-on is in progress: at once if none is. */
function afterDrawsSettle(fn) {
  if (!runningDraws.size) { fn(); return; }
  Promise.all([...runningDraws]).then(() => afterDrawsSettle(fn));
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
      trackDraw(anim);
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
      trackDraw(anim);
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

/** A bar's label as a reader would write it.
 *
 * The tooltip printed the label raw, so hovering an intraday bar returned
 * "2026-09-04T14:00:00-04:00" as its heading -- a machine timestamp over two
 * lines of human-readable numbers.
 *
 * Formatted from the string's OWN parts rather than through a Date, and that
 * is the part worth keeping. `new Date("...-04:00")` converts to whatever zone
 * the browser is in, so the same bar reads 2:00 pm in New York and 7:00 pm in
 * London -- for a bar whose identity IS its market time. Reading the digits
 * out of the string shows the time the exchange stamped, wherever it is
 * hovered from. `parseBarDate` above converts on purpose, because an axis is
 * placing ticks rather than naming a moment.
 *
 * Daily bars carry no time, so they get the year instead; intraday bars drop
 * it, because a year on every hover is noise when the axis already says it.
 */
function barLabelText(label) {
  const raw = String(label == null ? '' : label);
  const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/);
  if (!m) return raw;
  const [, y, mo, d, hh, mm] = m;
  // Noon, so a day name cannot be dragged across a boundary by a local offset.
  const named = new Date(Number(y), Number(mo) - 1, Number(d), 12);
  if (isNaN(named.getTime())) return raw;
  const day = named.toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
  });
  if (hh === undefined) return `${day}, ${y}`;
  const h24 = Number(hh);
  const suffix = h24 >= 12 ? 'pm' : 'am';
  const h12 = h24 % 12 || 12;
  return `${day} \u00b7 ${h12}:${mm} ${suffix}`;
}

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
 * see build(). The first tick has no predecessor; on a year axis it names its
 * year, and on a month, week or day axis its month. It used to name the year
 * there too, so a 3-month chart in Pulse read "2026, Sep, Oct", where the one
 * label left of the turn said the year and not which month the line starts in.
 * A year the axis crosses is still named where it turns, and the hover names
 * every bar's year.
 */
function tickLabel(d, unitId, prev) {
  const newYear = !prev || prev.getFullYear() !== d.getFullYear();
  const newMonth = newYear || !prev || prev.getMonth() !== d.getMonth();
  if (unitId === 'year') return String(d.getFullYear());
  if (unitId === 'month') return newYear && prev ? String(d.getFullYear()) : MONTH_SHORT[d.getMonth()];
  if (unitId === 'week' || unitId === 'day') {
    /* The leftmost tick names the month, not the year.
     *
     * `newYear` is true for the first tick because it has no predecessor. A
     * 1-month axis came back "2026, 17, 24, 31", where the one label that
     * should have told you the month told you the year instead. Months now
     * start the same way (above). */
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
    return { grain: 'day', key: (d) => d.toISOString().slice(0, 10) };
  }
  if (step < 5) {
    // Daily bars. Months give ~1 per 21 bars: 6 on a six-month chart, 12 on a
    // year. Weeks would give 26 and 52, which is the fence again. Years over
    // a long span, as on weekly bars: the All range draws every session since
    // the listing, and months there are 333 lines on NVDA's 27 years.
    const years = (last - first) / 86400000 / 365;
    if (years > 3) {
      return { grain: 'year', key: (d) => String(d.getUTCFullYear()) };
    }
    return { grain: 'month', key: (d) => d.toISOString().slice(0, 7) };
  }
  if (step < 45) {
    // Weekly bars: quarters on a short span, years on a long one.
    const years = (last - first) / 86400000 / 365;
    if (years > 3) {
      return { grain: 'year', key: (d) => String(d.getUTCFullYear()) };
    }
    return { grain: 'quarter',
      key: (d) => d.getUTCFullYear() + 'Q' + Math.floor(d.getUTCMonth() / 3) };
  }
  return { grain: 'year', key: (d) => String(d.getUTCFullYear()) };
}

/* Where the period dividers fall: a bar index per boundary, or none.
 *
 * Shared by the price chart and the RSI and MACD panes under it, so a boundary
 * is drawn at one x down the whole stack. Collected before anything is drawn,
 * so the count is checked first: the old code decided per line and capped
 * mid-loop, which is how it ended up drawing a fence and then stopping. */
function dividerMarks(labels, n) {
  const spec = periodDividers(labels, n);
  if (!spec) return [];
  const marks = [];
  let prev = null;
  for (let i = 0; i < n; i += 1) {
    const raw = String(labels[i] || '');
    const d = new Date(raw.length <= 10 ? raw + 'T00:00:00Z' : raw);
    if (Number.isNaN(d.getTime())) continue;
    const k = spec.key(d);
    if (prev === null) { prev = k; continue; }
    if (k === prev) continue;
    prev = k;
    marks.push(i);
  }
  /* Draw nothing rather than a fence.
   *
   * If the chosen granularity still produces a line every few bars the
   * feature is not adding orientation, it is adding noise, so it stands down
   * instead of capping. One line per four bars is the floor. */
  return marks.length <= Math.max(2, Math.floor(n / 4)) ? marks : [];
}

/* The dividers, as asked for with a reference chart: "this is how the session
 * dividers should look like". A dashed line the full height of the plot and
 * nothing else. They were a sparse dotted line over the price area alone,
 * each with its own caption at the foot, and the captions said again what the
 * date axis under the chart already says: the axis names the boundaries.
 *
 * Dashes of 4 on 4, a pattern no other line on these charts uses: fine dots
 * are the ratio levels and 6 on 4 the structural ones. */
function drawDividers(layer, marks, X, top, bottom) {
  marks.forEach((i) => {
    const x = X(i);
    layer.appendChild(s('line', {
      x1: x, y1: top, x2: x, y2: bottom,
      stroke: C.refSession, 'stroke-width': 1,
      'stroke-dasharray': '4 4',
      opacity: 0.55,
    }));
  });
}

function lineChart(opts) {
  const {
    series = [], labels = [], height = 220, refLines = [],
    yFormat = (v) => fmt(v, 2), valueFormat = null, zeroLine = false,
    markerLast = true, width = 720,
    // {open, high, low, close} arrays. Drawn as OHLC candles under the series.
    // Folded into this chart rather than a separate function so candles inherit
    // the axis, date labels, reference-line placement and hover layer.
    candles = null,
    /* The directional pair for the price mark and the volume strip.
     *
     * Defaulted to the slots each already used rather than to one shared pair,
     * because they were never the same pair: candles have always been s3/s8 and
     * volume pos/neg. Passing a default of `C.pos` here would have quietly
     * restyled every candle in the app on the way to making them configurable.
     *
     * Read at call time, not captured at module scope: `syncChartTheme()`
     * rewrites C when the OS theme flips, and a default frozen at import would
     * keep drawing the old theme's colours. */
    candleUp = null, candleDown = null, volUp = null, volDown = null,
    /* Per-bar colours for the candles, over the up and down pair: the Weinstein
     * stage of each bar's week, today. A null entry keeps that bar's direction
     * colour. A line takes the same thing from its series' own `tints`, so the
     * two chart styles are coloured by one array. */
    candleTints = null,
    /* The Weinstein stage of each bar's week: `stageBand` its colour, and
     * `stageNames` what to call it ("Stage 4 · Declining"). The candles and
     * the line are drawn in it through `candleTints` and a series' `tints`;
     * these name each run along the foot of the price and in the readout. */
    stageBand = null,
    stageNames = null,
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
    /* The bars outside the regular session, one boolean per bar, shaded: the
     * pre- and post-market stretches of a chart drawn with extended hours, so
     * the thin-book prints read apart from the session's own. */
    offHours = null,
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
    // Vertical event markers: {index, color, label, detail, value}. A dashed
    // line down the plot, an optional short label at the top, an optional dot
    // on the price, and `detail` as the hover text. Used for the point where
    // two series cross and for earnings report dates — anything that is a
    // moment rather than a direction, which is what separates these from
    // `events` below.
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
    /* The caller pans this chart on a plain drag, and the measurement takes a
     * press held still for a moment first, or shift.
     *
     * Asked for both ways: "the drag feature to see percent change is not
     * working", and then "dragging left and right on the chart with a left
     * click does not move the chart". One button, two gestures, told apart
     * the way a phone tells a scroll from a press: move within HOLD_MS and it
     * is a pan, hold still and it is a measurement. A chart that cannot pan
     * at the moment, its whole history on screen, measures on a plain drag,
     * which the caller says by leaving `data-pan-armed` off its host. */
    panDrag = false,
    /* Called with a marker's events when one is clicked, a press and release
     * that did not move or hold; the hover readout for its bar ends with
     * `eventHint`. Asked for as "whenever i click in the insider trades, take
     * me to a sub-tab of the insider buys/sells for that specific stock". */
    onEventClick = null,
    eventHint = '',
    /* How far the price scale is stretched, and what to call as it is dragged.
     * `yZoom` divides the range the data asks for about its middle: 2 shows
     * half of it, so moves look larger, and 0.5 twice it. With `onYZoom` the
     * axis gutter is a handle: up stretches, down squeezes, a double press
     * asks for 1. Asked for as "be able to zoom in/out of this tab by
     * dragging the price up or down". */
    yZoom = 1,
    onYZoom = null,
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
    const [dLo, dHi] = extentOf(all);
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
    [lo, hi] = extentOf(all);
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

  /* Room for the insider markers on their side of the price. Insiders sell
   * into strength, so their sales sit at the top of the range, where there
   * was nowhere above for a triangle and its badge: the badge went beside the
   * triangle, or off the plot. The range grows by what a marker and badge
   * need and no more, only where one is near an edge, and not on a plot too
   * short to spare it. A sell is measured from the high it stands over on a
   * candle chart, a buy from the low. */
  if (!yDomain && events && events.length && priceH > 0) {
    const need = (EVENT_OFF + EVENT_H + 4 + 17 + 2) / priceH;
    if (need < 0.35) {
      const closesAt = (candles && candles.close) || (series[0] && series[0].values) || [];
      const priced = (kind) => events.filter((e) => e.kind === kind && Number.isFinite(e.index))
        .map((e) => {
          const wick = candles && (kind === 'buy' ? candles.low : candles.high);
          const v = wick && wick[e.index] !== null && isFinite(wick[e.index])
            ? wick[e.index] : closesAt[e.index];
          return v === null || v === undefined || !isFinite(v) ? null : v;
        }).filter((v) => v !== null);
      const sells = priced('sell');
      const buys = priced('buy');
      // Twice, because each widening moves the other end's share of the range.
      for (let pass = 0; pass < 2; pass += 1) {
        if (sells.length) hi = Math.max(hi, (extentOf(sells)[1] - need * lo) / (1 - need));
        if (buys.length) lo = Math.min(lo, (extentOf(buys)[0] - need * hi) / (1 - need));
      }
    }
  }

  // The scale as dragged, about the middle of the range it would have had.
  const yZoomed = !yDomain && isFinite(yZoom) && yZoom > 0 && yZoom !== 1;
  if (yZoomed) {
    const mid = (lo + hi) / 2;
    const half = (hi - lo) / 2 / yZoom;
    lo = mid - half;
    hi = mid + half;
  }

  const X = (i) => m.l + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const Y = (v) => m.t + priceH - ((v - lo) / (hi - lo)) * priceH;

  const root = svgRoot(W, H);

  /* Stretched past its range, the price is cut at the plot's edges, where it
   * would otherwise be drawn over the dates, the volume and the header. Each
   * layer of the price area takes the clip rather than one group holding them
   * all, so the order they are drawn in is the order it was. */
  let clipRef = null;
  if (yZoomed && yZoom > 1) {
    lineChart.clips = (lineChart.clips || 0) + 1;
    const id = 'plot-clip-' + lineChart.clips;
    const defs = s('defs', {});
    const clip = s('clipPath', { id });
    clip.appendChild(s('rect', { x: m.l - 1, y: m.t, width: plotW + 2, height: priceH }));
    defs.appendChild(clip);
    root.appendChild(defs);
    clipRef = `url(#${id})`;
  }
  const clipped = (el) => {
    if (clipRef && el && el.setAttribute) el.setAttribute('clip-path', clipRef);
    return el;
  };

  // Captured once per chart so a flag flipped mid-render can't half-animate it.
  const animating = animateNextChart && !reducedMotion();
  const seriesDelay = makeStagger();
  // Scale gridline count with available height — a fixed 4 ticks leaves a tall
  // chart with a sparse, hard-to-read axis. ~65px per tick keeps labels legible.
  const ticks = niceTicks(lo, hi, Math.max(3, Math.min(8, Math.round(priceH / 65))));

  /* Each run of a stage, for its name along the foot (below).
   *
   * Stages have been drawn three ways here. As the reference chart draws them,
   * every candle in the colour of its week's stage, which NKE in stage 4 had
   * reported as "why are all candles [red], even in uptrends like these?".
   * Then as a four-pixel band along the foot, asked about as "does stages no
   * longer work on the chart?", and then as a faint tint behind each run. And
   * now as the reference again, at the reader's word: "keep the candles as is
   * with the color change as per the reference screenshot, and so the same
   * feature with the lines". So the candles and the line take the colour
   * (candleTints, a series' tints), and Stages off gives every bar its own
   * direction back. What is drawn from these runs is each one's name, which
   * is what lets a red rally be read as stage 4 rather than as a fall. */
  const stageRuns = [];
  if (Array.isArray(stageBand) && stageBand.length) {
    const half = n > 1 ? plotW / (n - 1) / 2 : plotW / 2;
    let start = 0;
    for (let i = 1; i <= n; i += 1) {
      if (i < n && stageBand[i] === stageBand[start]) continue;
      if (stageBand[start]) {
        const x0 = Math.max(m.l, X(start) - half);
        const x1 = Math.min(m.l + plotW, X(i - 1) + half);
        stageRuns.push({ x0, width: Math.max(1, x1 - x0), color: stageBand[start],
          name: Array.isArray(stageNames) ? stageNames[start] : null });
      }
      start = i;
    }
  }
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
    root.appendChild(clipped(vpLayer));
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
      x: m.l + plotW + 6, y: Y(t) + 3.5, fill: C.ink2, 'font-size': CF.tick, 'font-weight': CW.tick,
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
  // for that day is part of the answer. `volLit` is the one lit, so a move
  // relights two bars rather than every bar: on the All range that was 16,296
  // of them on IBM's chart, about 40ms a move.
  const volBars = [];
  let volLit = -1;
  const lightVol = (i) => {
    if (i === volLit) return;
    if (volBars[volLit]) volBars[volLit].setAttribute('opacity', 0.42);
    if (volBars[i]) volBars[i].setAttribute('opacity', 0.95);
    volLit = i;
  };
  if (volRows) {
    const volTop = m.t + priceH + volGap;
    const volMax = Math.max(extentOf(volRows.map((v) => (v === null || !isFinite(v) ? 0 : v)))[1], 1);
    const volLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.5 : null });
    root.appendChild(volLayer);

    const closes = (candles && candles.close) || (series[0] && series[0].values) || [];
    const barW = Math.max(1, (plotW / Math.max(n, 1)) - 1.5);
    const drawBar = (i, v, x, w) => {
      const h = Math.max(1, (v / volMax) * volH);
      // Direction from the close-to-close change, falling back to neutral on the
      // first bar where there is no prior close to compare against.
      const prev = closes[i - 1];
      const cur = closes[i];
      const up = (prev === null || prev === undefined || cur === null || cur === undefined)
        ? null : cur >= prev;
      const bar = s('rect', {
        x, y: volTop + volH - h, width: w, height: h,
        fill: up === null ? C.muted
          : (up ? (volUp || C.pos) : (volDown || C.neg)),
        opacity: 0.42, rx: Math.min(1.5, w / 2),
      });
      volLayer.appendChild(bar);
      return bar;
    };
    /* One bar a pixel column where there are more than three bars to a pixel:
     * the tallest of them, in its own direction, lit by any bar in it. Every
     * session since the listing is that, 16,296 bars across about 1,200 pixels
     * on IBM's All, and drawn one a bar they were 16,296 overlapping 1px rects
     * that doubled the cost of every frame for no mark a reader could see. */
    if (n > plotW * 3) {
      const cols = new Map();
      volRows.forEach((v, i) => {
        if (v === null || !isFinite(v) || v <= 0) return;
        const c = Math.floor(X(i));
        const held = cols.get(c);
        if (!held) {
          cols.set(c, { i, v, bars: [i] });
        } else {
          held.bars.push(i);
          if (v > held.v) { held.v = v; held.i = i; }
        }
      });
      cols.forEach((col, c) => {
        const bar = drawBar(col.i, col.v, c, 1);
        col.bars.forEach((i) => { volBars[i] = bar; });
      });
    } else {
      volRows.forEach((v, i) => {
        if (v === null || !isFinite(v) || v <= 0) return;
        volBars[i] = drawBar(i, v, X(i) - barW / 2, barW);
      });
    }
    // One quiet label so the strip is identifiable without a legend entry.
    volLayer.appendChild(s('text', {
      x: m.l + 2, y: volTop + 9, fill: C.ink2, 'font-size': CF.tick,
      'font-weight': CW.tick,
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
    root.appendChild(clipped(cloudLayer));
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
  root.appendChild(clipped(levelLayer));

  // Extended hours, under everything: a band for each run of bars outside the
  // regular session, reaching halfway to the bars either side of it.
  if (Array.isArray(offHours) && offHours.length === n && n > 1) {
    const half = plotW / (n - 1) / 2;
    const shade = s('g', { class: 'off-hours' });
    for (let i = 0; i < n; i += 1) {
      if (!offHours[i]) continue;
      let j = i;
      while (j + 1 < n && offHours[j + 1]) j += 1;
      const x0 = Math.max(m.l, X(i) - half);
      const x1 = Math.min(m.l + plotW, X(j) + half);
      shade.appendChild(s('rect', {
        x: x0, y: m.t, width: Math.max(0, x1 - x0), height: priceH,
        fill: C.ink2, opacity: 0.07,
      }));
      i = j;
    }
    levelLayer.appendChild(shade);
  }

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
        x: m.l + 6, y: yTop + 11, fill: b.color || C.ink2, 'font-size': CF.tick,
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
   * Behind the price line and the drawings, in front of the grid: it is
   * orientation, not data. Through the volume strip as well as the price, and
   * the panes under the chart draw the same marks (see dividerMarks), so one
   * boundary is one line down the whole stack. */
  if (sessions && n > 1) drawDividers(levelLayer, dividerMarks(labels, n), X, m.t, m.t + plotH);

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
        fill: sg.color || C.ink2, 'font-size': CF.tick, 'font-weight': 600,
      }, sg.label));
    }
  });

  vMarkers.forEach((mk) => {
    if (!(mk.index >= 0 && mk.index < n)) return;
    const cx = X(mk.index);
    /* One group per marker, carrying a <title>.
     *
     * `detail` was accepted by callers and rendered by nothing, which is the
     * same defect the events layer had: a marker labelled "E" is a date and
     * nothing else, and the caller had already built the sentence saying which
     * quarter it was, whether it beat and what the tape did next.
     *
     * A native <title> rather than the chart's own tooltip, for the reason
     * given on the events layer: no listener, survives every redraw, and works
     * on a target a few pixels wide where a scrub binding would compete with
     * the crosshair underneath. */
    const mark = s('g', mk.detail ? { style: 'cursor:help' } : {});
    levelLayer.appendChild(mark);
    mark.appendChild(s('line', {
      x1: cx, y1: m.t, x2: cx, y2: m.t + priceH, stroke: mk.color || C.ink2,
      'stroke-width': 1.4, 'stroke-dasharray': '6 4', opacity: 0.75,
    }));
    if (mk.detail) {
      // A dashed 1.4px line is not a hover target. This widens it without
      // widening what is drawn.
      mark.appendChild(s('rect', {
        x: cx - 5, y: m.t, width: 10, height: priceH, fill: 'transparent',
      }));
      mark.appendChild(s('title', {}, mk.detail));
    }
    if (mk.label) {
      // Flip the anchor near the right edge so the text stays inside the plot.
      const nearRight = cx > m.l + plotW * 0.62;
      mark.appendChild(s('text', {
        x: nearRight ? cx - 6 : cx + 6, y: m.t + 11, fill: mk.color || C.ink2,
        'font-size': CF.tick, 'font-weight': 600,
        'text-anchor': nearRight ? 'end' : 'start',
      }, mk.label));
    }
    if (isFinite(mk.value)) {
      mark.appendChild(s('circle', {
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
    // Stretched, a level off the scale has no line on the plot to label.
    .filter((r) => r.label && (!yZoomed || (r.value >= lo && r.value <= hi)))
    .map((r) => ({ text: r.label, color: readable(r.color), lineY: Y(r.value) }))
    .sort((a, b) => a.lineY - b.lineY);

  let prevY = -Infinity;
  labeled.forEach((r) => {
    r.y = Math.min(Math.max(r.lineY - 4, prevY + LABEL_GAP), m.t + priceH - 2);
    prevY = r.y;
  });

  /* Each run's name, along the foot of the price area in the stage's colour
   * with a halo of the plane. The price domain is padded 8% below its lowest
   * bar, so the names sit under the data rather than on it, and a name is
   * drawn only where its run can hold it: the full name first, then "Stage 4"
   * alone, then nothing. A run a few bars wide still shows its colour in its
   * bars, and the tooltip names it. See the runs above. */
  if (stageRuns.length) {
    const y = m.t + priceH - 4;
    const nameLayer = s('g', { class: 'stage-names', 'aria-hidden': 'true' });
    root.appendChild(nameLayer);
    stageRuns.forEach((r) => {
      if (!r.name) return;
      const name = String(r.name);
      const fits = [name, name.split(' \u00b7 ')[0]]
        .find((t) => t.length * STAGE_NAME_CHAR + 10 <= r.width);
      if (!fits) return;
      const x0 = r.x0 + 5;
      nameLayer.appendChild(s('text', {
        x: x0, y: y - 4, fill: r.color, 'font-size': CF.micro, 'font-weight': 600,
        stroke: C.surface, 'stroke-width': 3, 'paint-order': 'stroke',
        'stroke-linejoin': 'round',
      }, fits));
    });
  }

  if (candles) {
    const o = candles.open || [], h = candles.high || [],
      l = candles.low || [], c = candles.close || [];
    // Leave a gap between bars so individual candles stay distinguishable; on a
    // dense series this floors at a 1px body, which reads as a bar chart and is
    // the honest rendering at that density.
    const slot = n > 1 ? plotW / (n - 1) : plotW;
    const body = Math.max(1, Math.min(11, slot * 0.62));
    const drawCandle = (x, oo, hh, ll, cc, i) => {
      const up = cc >= oo;
      const colour = (candleTints && candleTints[i])
        || (up ? (candleUp || C.s3) : (candleDown || C.s8));
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
    };
    /* One candle a pixel column past three bars to a pixel, as the volume
     * strip draws: the column's first open, its high and low, and its last
     * close, tinted as its last bar is. That is the candle of those sessions
     * taken together, and the All range is 16,296 of them on IBM's chart in
     * about 1,200 pixels, two elements apiece one a bar. */
    const pooled = n > plotW * 3;
    let col = null;
    const flush = () => { if (col) drawCandle(col.cx + 0.5, col.o, col.h, col.l, col.c, col.last); };
    for (let i = 0; i < n; i += 1) {
      const oo = o[i], hh = h[i], ll = l[i], cc = c[i];
      if ([oo, hh, ll, cc].some((v) => v === null || v === undefined || !isFinite(v))) continue;
      if (!pooled) { drawCandle(X(i), oo, hh, ll, cc, i); continue; }
      const cx = Math.floor(X(i));
      if (col && col.cx === cx) {
        col.h = Math.max(col.h, hh); col.l = Math.min(col.l, ll); col.c = cc; col.last = i;
      } else {
        flush();
        col = { cx, o: oo, h: hh, l: ll, c: cc, last: i };
      }
    }
    flush();
  }

  // Where the series start among the root's children, for the clip below.
  const seriesFrom = root.children.length;
  series.forEach((se, si) => {
    if (se.hidden) return;  // present for hover/tooltip only, not drawn
    const pts = [];
    // Which bar each point is, for a tinted line: a gap in the values means
    // point k is not bar k.
    const at = [];
    se.values.forEach((v, i) => {
      if (v === null || !isFinite(v)) return;
      pts.push(`${X(i).toFixed(2)},${Y(v).toFixed(2)}`);
      at.push(i);
    });
    if (!pts.length) return;
    /* A tinted line is drawn in runs, one per colour.
     *
     * The segment into a point takes that point's colour, because it is the move
     * into that bar: the line changes colour at the bar whose week changed stage
     * rather than one bar early. Each run starts on the last point of the run
     * before it, so the line is unbroken. The fill under it is split the same
     * way, which shades each stretch in its stage.
     *
     * A fade rather than the sweep. Every run would sweep from its own start at
     * once, which reads as the line assembling itself in pieces. */
    if (Array.isArray(se.tints)) {
      const tint = (k) => se.tints[at[k]] || se.color;
      const runs = [];
      for (let k = 1; k < pts.length; k += 1) {
        const c = tint(k);
        const prev = runs[runs.length - 1];
        if (prev && prev.color === c) prev.to = k;
        else runs.push({ color: c, from: k - 1, to: k });
      }
      const base = Y(Math.max(lo, 0));
      runs.forEach((run) => {
        const part = pts.slice(run.from, run.to + 1);
        if (se.fill) {
          root.appendChild(s('path', {
            d: `M${part[0].split(',')[0]},${base} L${part.join(' L')} L${
              part[part.length - 1].split(',')[0]},${base} Z`,
            fill: run.color, opacity: se.fillOpacity || 0.1, stroke: 'none',
            'data-fade': animating ? DRAW_MS * 0.55 : null,
          }));
        }
        root.appendChild(s('polyline', {
          points: part.join(' '), fill: 'none', stroke: run.color,
          'stroke-width': se.width || 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round',
          'stroke-dasharray': se.dash || null, opacity: se.opacity || 1,
          'data-fade': animating ? DRAW_MS * 0.55 : null,
        }));
      });
    } else {
      if (se.fill) {
        const base = Y(Math.max(lo, 0));
        root.appendChild(s('path', {
          d: `M${pts[0].split(',')[0]},${base} L${pts.join(' L')} L${pts[pts.length - 1].split(',')[0]},${base} Z`,
          fill: se.color, opacity: se.fillOpacity || 0.1, stroke: 'none',
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
    }

    if (markerLast && se.marker !== false) {
      const lastIdx = se.values.reduce((acc, v, i) => (v !== null && isFinite(v) ? i : acc), -1);
      // The end of a tinted line is in its last bar's colour, not the base one.
      const endColor = (se.tints && se.tints[lastIdx]) || se.color;
      if (lastIdx >= 0) {
        // A halo behind the leading point of the primary series while the
        // session is live. One series only: every line pulsing is noise, and the
        // reader is being told "the newest point is still forming", which is a
        // fact about the bar rather than about any particular average.
        /* Asked to "make the chart blink more visible, pop out more", with a
         * screenshot where it could barely be found: a 4px dot breathing by
         * 14%, and one 1.5px outline of a halo starting at 55% opacity, on a
         * line of the same colour against a near-black plot. Two filled
         * ripples now, half a beat apart so one is always spreading, reaching
         * four times the dot; and the dot is larger, glows in the line's
         * colour and swells with the beat. See .live-halo in styles.css. */
        if (liveNextChart && si === 0) {
          ['live-halo', 'live-halo live-halo-late'].forEach((cls) => {
            const halo = s('circle', {
              cx: X(lastIdx), cy: Y(se.values[lastIdx]), r: 5,
              fill: endColor, 'fill-opacity': 0.28, stroke: endColor, 'stroke-width': 2,
              class: cls,
              'data-fade': animating ? DRAW_MS * 0.8 : null,
            });
            root.appendChild(halo);
            liveMarks.push(halo);
          });
        }
        // 2px surface ring keeps the end dot legible where lines cross.
        const live = liveNextChart && si === 0;
        const endDot = s('circle', {
          cx: X(lastIdx), cy: Y(se.values[lastIdx]), r: live ? 5 : 4,
          fill: endColor, stroke: C.surface, 'stroke-width': 2,
          // `color` so the glow can be currentColor: the line's own colour,
          // tinted bar and all, without a second copy of it in the CSS.
          color: live ? endColor : null,
          class: live ? 'live-dot' : null,
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
  if (clipRef) Array.from(root.children).slice(seriesFrom).forEach(clipped);
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
        /* The price is tagged once, by the price tag above. In candle mode its
         * series is hidden and skipped anyway; in line mode it is drawn, and
         * took a second tag of its own: measured on SPY weekly, two pills
         * reading 769.64 stacked 17px apart beside the last close, the lower
         * one pushed down by the collision pass below. */
        if (priceTag && se === priceSeries) return null;
        const li = se.values.reduce((acc, v, i) => (v !== null && isFinite(v) ? i : acc), -1);
        if (li < 0) return null;
        return { si, color: (se.tints && se.tints[li]) || se.color,
          value: se.values[li], y: Y(se.values[li]) };
      })
      .filter(Boolean);
    // Into the same list, so one collision pass positions everything and the
    // price cannot be pushed off the axis or drawn over.
    if (priceTag) tags.push(priceTag);
    // Stretched, a value off the scale is tagged at the edge it left by.
    if (yZoomed) tags.forEach((t) => { t.y = Math.min(Math.max(t.y, m.t + 8), m.t + priceH - 8); });
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
        'font-size': t.isPrice ? CF.tag : CF.label,
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

  /* Dated events pinned to the price line: insider transactions, in practice.
   *
   * A triangle off the price on the day, pointing the way the trade went, on a
   * stem from a dot where the trade sits on the price. Buys and sells are the
   * same shape flipped rather than two different glyphs: the direction IS the
   * information, and a reader should not have to learn a legend to see it.
   * Above a candle's high for a sell and below its low for a buy, so it never
   * sits on the wick it is annotating.
   *
   * Asked to be "more visible on the chart". The triangles were 10px, their
   * stems a hairline at half strength and their labels coloured text on a dark
   * box, three at most, and red marks on a green area fill were easy to miss.
   * Now the triangle is 14px and ringed in the surface colour, which cuts it
   * out of whatever is behind it, and its label is a solid badge in the
   * trade's colour.
   *
   * Trades closer than a marker's width, the same way, are one marker: the
   * largest stands on its own bar, the others are dots on theirs, and the badge
   * gives their count and total. Overlapping triangles read as one mark under
   * the label of only the biggest.
   *
   * As many badges as fit, largest first, where one would not cover another
   * badge or a marker, up to one for every 150px of plot; three, whatever the
   * width, was the old rule. Every trade is also named in the crosshair readout
   * for its bar. That is where a reader can get at who traded: the hover layer
   * covers the whole plot, so the <title> on a marker, kept for a screen
   * reader, never showed under a mouse.
   *
   * Colours are read here, not held in a constant: one taken at load kept the
   * dark theme's red and green on the light theme. */
  const eventsAt = new Map();
  // Where each marker and badge was drawn, and the trades it stands for, so a
  // press on one can be told apart from a press on the plot (onEventClick).
  const eventHits = [];
  if (events && events.length) {
    const evLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.9 : null });
    root.appendChild(clipped(evLayer));
    const closes = (candles && candles.close) || (series[0] && series[0].values) || [];
    const standOn = (e) => {
      const buy = e.kind === 'buy';
      const wick = candles && (buy ? candles.low : candles.high);
      const v = wick && isFinite(wick[e.index]) && wick[e.index] !== null ? wick[e.index] : closes[e.index];
      return v === null || v === undefined || !isFinite(v) ? null : v;
    };
    // Largest first, so a large trade claims its place and a smaller one near
    // it joins the nearest marker going its way.
    const marks = [];
    events
      .filter((e) => Number.isFinite(e.index) && e.index >= 0 && e.index < n && standOn(e) !== null)
      .sort((a, b) => (b.value || 0) - (a.value || 0))
      .forEach((e) => {
        if (!eventsAt.has(e.index)) eventsAt.set(e.index, []);
        eventsAt.get(e.index).push(e);
        const at = { e, buy: e.kind === 'buy', x: X(e.index), y: Y(standOn(e)) };
        let near = null;
        marks.forEach((mk) => {
          const gap = Math.abs(mk.x - at.x);
          if (mk.buy === at.buy && gap < EVENT_GAP && (!near || gap < Math.abs(near.x - at.x))) near = mk;
        });
        if (near) near.items.push(at);
        else marks.push({ buy: at.buy, x: at.x, y: at.y, items: [at] });
      });

    const occupied = [];
    marks.forEach((mk) => {
      const colour = mk.buy ? C.s3 : C.neg;
      const away = mk.buy ? 1 : -1;               // below the price for a buy
      // A sell at the top of the range is let down a pixel or two rather than
      // drawn off the plot, never closer than 3px to the price.
      const drop = mk.buy ? 0 : Math.min(EVENT_OFF - 3,
        Math.max(0, 1 - (mk.y - EVENT_OFF - EVENT_H)));
      const tip = mk.y + away * EVENT_OFF + drop;
      const base = mk.y + away * (EVENT_OFF + EVENT_H) + drop;
      const total = mk.items.reduce((sum, it) => sum + (it.e.value || 0), 0);
      const many = mk.items.length > 1;
      const word = mk.buy ? 'buys' : 'sells';
      Object.assign(mk, {
        colour, base, total,
        text: many ? `${mk.items.length} ${word}${total ? ` · $${fmtCompact(total)}` : ''}`
          : mk.items[0].e.label,
      });
      const mark = s('g', {});
      // The other trades it stands for, each a dot on its own bar.
      mk.items.slice(1).forEach((it) => {
        mark.appendChild(s('circle', {
          cx: it.x, cy: it.y, r: 2.5, fill: colour, stroke: C.surface, 'stroke-width': 1,
        }));
      });
      mark.appendChild(s('line', {
        x1: mk.x, y1: mk.y, x2: mk.x, y2: tip, stroke: colour, 'stroke-width': 1.5, opacity: 0.85,
      }));
      mark.appendChild(s('circle', {
        cx: mk.x, cy: mk.y, r: 3.5, fill: colour, stroke: C.surface, 'stroke-width': 1.5,
      }));
      // The shape flips through tip and base rather than through two path
      // strings: for a buy the tip sits above the base, an upward triangle.
      mark.appendChild(s('path', {
        d: `M ${mk.x} ${tip} L ${mk.x - EVENT_W / 2} ${base} L ${mk.x + EVENT_W / 2} ${base} Z`,
        fill: colour, stroke: C.surface, 'stroke-width': 1.5, 'stroke-linejoin': 'round',
      }));
      const detail = mk.items.map((it) => it.e.detail || it.e.label).filter(Boolean);
      if (detail.length) {
        mark.appendChild(s('title', {}, (many ? [`${mk.items.length} insider ${word}`] : [])
          .concat(detail).join('\n')));
      }
      evLayer.appendChild(mark);
      mk.box = { x: mk.x - EVENT_W / 2 - 1, y: Math.min(mk.y, base) - 4,
        w: EVENT_W + 2, h: Math.abs(base - mk.y) + 8 };
      occupied.push(mk.box);
      mk.events = mk.items.map((it) => it.e);
      // On the scale, or stretched off it by onYZoom and clipped: then it has
      // no badge and nothing to click.
      mk.onScale = mk.y >= m.t && mk.y <= m.t + priceH;
      if (mk.onScale) eventHits.push({ ...mk.box, events: mk.events });
    });

    const cap = Math.max(2, Math.min(8, Math.floor(plotW / 150)));
    // Inside the price plot, off the volume strip, and clear of every badge
    // and marker but its own.
    const clear = (r, own) => r.y >= m.t && r.y + r.h <= m.t + priceH && r.x >= m.l
      && r.x + r.w <= m.l + plotW
      && !occupied.some((o) => o !== own && r.x < o.x + o.w + 3 && o.x < r.x + r.w + 3
        && r.y < o.y + o.h + 3 && o.y < r.y + r.h + 3);
    let badges = 0;
    [...marks].sort((a, b) => b.total - a.total).forEach((mk) => {
      if (badges >= cap || !mk.text || !mk.onScale) return;
      const w = mk.text.length * 6 + 14;
      const h = 17;
      const left = Math.min(Math.max(m.l + 2, mk.x - w / 2), m.l + plotW - w - 2);
      // Past the triangle, on its side of the price. Where that runs off the
      // plot or onto another marker, the other side of the price, then beside
      // the triangle: a sell at the top of a short chart has no room above.
      const past = { x: left, y: mk.buy ? mk.base + 4 : mk.base - 4 - h, w, h };
      const facing = { x: left, y: mk.buy ? mk.y - 8 - h : mk.y + 8, w, h };
      const mid = (mk.y + mk.base) / 2 - h / 2;
      const right = { x: mk.x + EVENT_W / 2 + 4, y: mid, w, h };
      const leftward = { x: mk.x - EVENT_W / 2 - 4 - w, y: mid, w, h };
      const at = [past, facing, right, leftward].find((r) => clear(r, mk.box));
      if (!at) return;
      occupied.push(at);
      eventHits.push({ ...at, events: mk.events });
      badges += 1;
      evLayer.appendChild(s('rect', {
        x: at.x, y: at.y, width: w, height: h, rx: h / 2, fill: mk.colour,
      }));
      evLayer.appendChild(s('text', {
        x: at.x + w / 2, y: at.y + 12.5, fill: inkOn(mk.colour), 'font-size': CF.label,
        'font-weight': CW.tag, 'text-anchor': 'middle',
      }, mk.text));
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
      x: x + 5, y: r.y, fill: r.color, 'font-size': CF.label,
      'font-weight': CW.label, opacity: 1,
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
          x: X(t.i), y: H - 6, fill: C.ink2, 'font-size': CF.tick, 'font-weight': CW.tick,
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
          x: X(i), y: H - 6, fill: C.ink2, 'font-size': CF.tick, 'font-weight': CW.tick,
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
    root.appendChild(clipped(d));
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
    y: m.t + 12, 'font-size': CF.label, 'font-weight': 600, 'text-anchor': 'middle',
  });
  [measureBand, measureA, measureB, measureDotA, measureDotB, measureLabel]
    .forEach((el) => measureGroup.appendChild(el));
  root.appendChild(measureGroup);

  // The series the measurement reads. The first one that isn't hidden — for a
  // candle chart that's the close, which is the right thing to measure.
  const measured = series.find((se) => !se.hidden && (se.values || []).some(
    (v) => v !== null && v !== undefined && isFinite(v))) || series[0];

  /* Hiding the readout and ending the gesture are two things.
   *
   * They were one: a move that landed on the bar the drag started on cleared
   * the anchor as well as the readout, so the rest of the drag measured
   * nothing. A hand starts a drag with a pixel or two, which is almost always
   * the same bar, so a drag across the chart usually died on its first move,
   * and read as the measurement not working at all. Tests that moved in one
   * long jump never saw it. */
  const hideMeasure = () => measureGroup.setAttribute('opacity', 0);
  const clearMeasure = () => {
    hideMeasure();
    measureAnchor = null;
    delete root.dataset.measuring;
  };

  /* The anchor alone, while the pointer is still on its bar: where the
   * measurement will be taken from, and that it has begun. */
  function markAnchor(i) {
    const v = measured && measured.values[i];
    if (v === null || v === undefined || !isFinite(v)) { hideMeasure(); return; }
    const x = X(i);
    measureBand.setAttribute('x', x);
    measureBand.setAttribute('width', 0);
    [measureA, measureB].forEach((l) => {
      l.setAttribute('x1', x); l.setAttribute('x2', x); l.setAttribute('stroke', C.ink2);
    });
    [measureDotA, measureDotB].forEach((d) => {
      d.setAttribute('cx', x); d.setAttribute('cy', Y(v)); d.setAttribute('fill', C.ink2);
    });
    measureLabel.setAttribute('fill', C.ink2);
    measureLabel.textContent = `${labels[i] || `#${i + 1}`}   drag to measure`;
    measureLabel.setAttribute('x', Math.min(Math.max(x, m.l + 90), m.l + plotW - 90));
    measureGroup.setAttribute('opacity', 1);
  }

  function drawMeasure(i, j) {
    if (!measured) { hideMeasure(); return; }
    // Back on its own bar: a mouse drag keeps its anchor and shows it; two
    // fingers on one bar have nothing to show.
    if (i === j) { if (measureAnchor !== null) markAnchor(i); else hideMeasure(); return; }
    const [lo, hi] = i < j ? [i, j] : [j, i];
    const va = measured.values[lo];
    const vb = measured.values[hi];
    if (va === null || vb === null || !isFinite(va) || !isFinite(vb)) { hideMeasure(); return; }

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
  function beginMeasure(at) {
    measureAnchor = at;
    // Read by the pan handler, which stands aside for as long as it is set.
    root.dataset.measuring = '1';
    window.addEventListener('mousemove', onDragMove);
    window.addEventListener('mouseup', endDrag);
  }

  /* A press on a chart that pans: moved more than HOLD_SLOP within HOLD_MS it
   * is the pan's, held still that long it is a measurement. The pan handler
   * waits out the same slop before it moves anything, so a hold never nudges
   * the chart under the anchor it is about to measure from. */
  const HOLD_MS = 300;
  const HOLD_SLOP = 4;
  let holdTimer = 0;
  let holdX = 0;
  const onHoldMove = (evt) => {
    if (Math.abs(evt.clientX - holdX) > HOLD_SLOP) cancelHold();
  };
  function cancelHold() {
    clearTimeout(holdTimer);
    holdTimer = 0;
    window.removeEventListener('mousemove', onHoldMove);
    window.removeEventListener('mouseup', cancelHold);
  }

  overlay.addEventListener('mousedown', (evt) => {
    if (evt.button !== 0) return;
    evt.preventDefault();            // no text-selection drag over the chart
    const at = indexFromClientX(evt.clientX);
    const armed = root.closest ? root.closest('[data-pan-armed]') : null;
    // Shift, a chart that does not pan, or one with nothing to pan right now:
    // measure from the press.
    if (!panDrag || evt.shiftKey || !armed) { beginMeasure(at); return; }
    holdX = evt.clientX;
    window.addEventListener('mousemove', onHoldMove);
    window.addEventListener('mouseup', cancelHold);
    holdTimer = setTimeout(() => {
      cancelHold();
      beginMeasure(at);
      markAnchor(at);
    }, HOLD_MS);
  });

  /* A click on an insider marker, for onEventClick: a press and release no
   * further apart than HOLD_SLOP and sooner than HOLD_MS, which no pan, hold
   * or measurement is. The overlay sits over the markers, so it is asked where
   * the press landed rather than each marker carrying a listener the overlay
   * would never let reach it. */
  const eventAt = (clientX, clientY) => {
    if (!eventHits.length) return null;
    const box = root.getBoundingClientRect();
    if (!box.width || !box.height) return null;
    // The SVG is scaled to its box and centred in it (xMidYMid meet).
    const k = Math.min(box.width / W, box.height / H);
    const px = (clientX - box.left - (box.width - W * k) / 2) / k;
    const py = (clientY - box.top - (box.height - H * k) / 2) / k;
    // The last drawn is on top, and answers first.
    for (let j = eventHits.length - 1; j >= 0; j -= 1) {
      const r = eventHits[j];
      if (px >= r.x - 2 && px <= r.x + r.w + 2 && py >= r.y - 2 && py <= r.y + r.h + 2) return r;
    }
    return null;
  };
  if (onEventClick) {
    let pressed = null;
    overlay.addEventListener('pointerdown', (evt) => {
      pressed = { x: evt.clientX, y: evt.clientY, t: Date.now() };
    });
    overlay.addEventListener('click', (evt) => {
      const p = pressed;
      pressed = null;
      if (!p || Math.abs(evt.clientX - p.x) > HOLD_SLOP || Math.abs(evt.clientY - p.y) > HOLD_SLOP
          || Date.now() - p.t > HOLD_MS) return;
      const hit = eventAt(evt.clientX, evt.clientY);
      if (hit) onEventClick(hit.events, evt);
    });
  }

  bindScrub(overlay, (evt) => {
    const box = root.getBoundingClientRect();
    const scale = W / box.width;
    const localX = (evt.clientX - box.left) * scale;
    let i = Math.round(((localX - m.l) / plotW) * (n - 1));
    i = Math.max(0, Math.min(n - 1, i));
    cross.setAttribute('x1', X(i));
    cross.setAttribute('x2', X(i));
    cross.setAttribute('opacity', 0.45);
    // A hand over a marker that opens something, the crosshair elsewhere.
    if (onEventClick) {
      overlay.style.cursor = eventAt(evt.clientX, evt.clientY) ? 'pointer' : 'crosshair';
    }
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
      // A tinted line is a different colour at every stage, and a swatch in
      // the base colour would name a line that is not on the chart.
      const hue = (se.tints && se.tints[i]) || se.color;
      dots[k].setAttribute('cx', X(i));
      dots[k].setAttribute('cy', Y(v));
      dots[k].setAttribute('fill', hue);
      dots[k].setAttribute('opacity', 1);
      rows.push([
        `<span style="color:${hue}">■</span> ${se.name}`,
        (valueFormat || yFormat)(v),
      ]);
    });
    // The stage of the bar's week, by name: the one place a run too narrow
    // for its name on the strip is still called something.
    if (Array.isArray(stageNames) && stageNames[i] && Array.isArray(stageBand) && stageBand[i]) {
      rows.push([`<span style="color:${stageBand[i]}">■</span> Stage`,
        escapeText(String(stageNames[i]).replace(/^Stage /, ''))]);
    }
    // Volume for the same bar. Shown in full rather than abbreviated: the point
    // of hovering a bar is to read the actual figure, and "144.3M" is what the
    // axis already told you.
    if (volRows) {
      const vv = volRows[i];
      if (vv !== null && vv !== undefined && isFinite(vv)) {
        rows.push(['Volume', Math.round(vv).toLocaleString()]);
      }
      lightVol(i);
    }
    // The insider trades on this bar, who and how much, largest first. See
    // the events layer: this is the one place the details can be read.
    const traded = eventsAt.get(i) || [];
    traded.slice(0, 4).forEach((e) => {
      const buy = e.kind === 'buy';
      rows.push([
        `<span style="color:${buy ? C.s3 : C.neg}">${buy ? '▲' : '▼'}</span> ${
          escapeText(e.who || (buy ? 'Insider buy' : 'Insider sell'))}`,
        escapeText(e.label || (buy ? 'Buy' : 'Sell')),
      ]);
    });
    if (traded.length > 4) rows.push(['', `${traded.length - 4} more insider trades`]);
    if (traded.length && eventHint) rows.push([`<span class="t-hint">${escapeText(eventHint)}</span>`, '']);
    showTip(tipRows(barLabelText(labels[i]) || `#${i + 1}`, rows), evt);
    // Tell the caller which bar is under the cursor, so a header or legend can
    // track it. Index only: this function knows nothing about what the caller
    // wants to display, and passing the bar would mean guessing.
    if (onHover) onHover(i);
  }, () => {
    hideTip();
    cross.setAttribute('opacity', 0);
    dots.forEach((d) => d.setAttribute('opacity', 0));
    lightVol(-1);
    // null means "cursor gone" — distinct from bar 0, which is a real bar.
    if (onHover) onHover(null);
  });
  root.appendChild(overlay);

  /* The price scale as a handle, for onYZoom. Up stretches the prices, down
   * squeezes them, a double press puts back the range the bars ask for. A
   * strip of its own over the axis gutter and above the overlay, so a press
   * there is neither a pan nor a measurement (the page's pan handler stands
   * aside for `data-price-scale`). The window carries the drag, as it does a
   * pan's: every step of it redraws this chart, and this strip with it. */
  if (onYZoom) {
    const grip = s('rect', {
      x: m.l + plotW, y: m.t, width: Math.max(0, W - m.l - plotW), height: priceH,
      fill: 'transparent', style: 'cursor:ns-resize;touch-action:none',
      'data-price-scale': '1',
    });
    // Neither gesture is visible on the axis, so it says what they are.
    grip.appendChild(s('title', {}, 'Drag up or down to stretch the price scale. '
      + 'Double-click to fit it to the bars on screen.'));
    grip.addEventListener('pointerdown', (evt) => {
      if (evt.button !== 0) return;
      evt.preventDefault();
      hideTip();
      const startY = evt.clientY;
      const from = yZoom;
      const move = (e) => onYZoom(from * Math.exp((startY - e.clientY) / Y_ZOOM_PX));
      const end = () => {
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', end);
        window.removeEventListener('pointercancel', end);
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', end);
      window.addEventListener('pointercancel', end);
    });
    grip.addEventListener('dblclick', (evt) => {
      evt.preventDefault();
      onYZoom(1);
    });
    root.appendChild(grip);
  }

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
    // The same inverse without the rounding, and without clamping to the bars.
    // A drawing placed between two candles, or dragged past the last one, has
    // to keep the position it was given: rounding to a whole bar is snapping,
    // and snapping is the reader's choice rather than this function's.
    indexAtExact: (px) => (n <= 1 ? 0 : ((px - m.l) / plotW) * (n - 1)),
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
      x: m.l - 8, y: Y(i) + 3.5, fill: C.ink2, 'font-size': CF.tick, 'text-anchor': 'end',
      'font-variant-numeric': 'tabular-nums',
    }, r.label));

    root.appendChild(s('text', {
      x: v >= 0 ? m.l + plotW + 6 : m.l + plotW + 6,
      y: Y(i) + 3.5, fill: C.muted, 'font-size': CF.tick, 'font-variant-numeric': 'tabular-nums',
    }, format(v)));
  });

  if (markerRow !== null && markerRow !== undefined && rows.length > 1) {
    const y = m.t + Math.max(0, Math.min(rows.length, markerRow)) * (plotH / rows.length);
    root.appendChild(s('line', {
      x1: m.l - 4, y1: y, x2: m.l + plotW, y2: y,
      stroke: C.warn, 'stroke-width': 1, 'stroke-dasharray': '4 3',
    }));
    root.appendChild(s('text', {
      x: m.l - 8, y: y - 3, fill: C.warn, 'font-size': CF.tick, 'text-anchor': 'end',
    }, markerLabel));
  }

  if (axisLabel) {
    root.appendChild(s('text', {
      x: mid, y: H - 5, fill: C.muted, 'font-size': CF.tick, 'text-anchor': 'middle',
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
function sparkline(values, width = 96, height = 26, color = C.brand) {
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
/* The insider markers' geometry: a triangle 14px wide whose tip stands 10px
 * off the price. Two closer than EVENT_GAP would overlap, and are drawn as one.
 * Their colours are C.s3 and C.neg, read when drawn: green and red, NOT C.pos,
 * which is blue and the same hex as C.s1. */
const EVENT_W = 14;
const EVENT_H = 12;
const EVENT_OFF = 10;
const EVENT_GAP = EVENT_W + 2;

// Pixels of drag on the price scale that stretch it by a factor of e, about
// 2.7: a full-height drag on a 400px plot is about 12 times.
const Y_ZOOM_PX = 160;

const MACD_HIST_POS = C.s3;
const MACD_HIST_NEG = C.neg;

function macdChart(macd, signal, hist, labels, width = 720, opts = {}) {
  // Taller than the old 150px. The panel's job is to show which side of the
  // signal line MACD is on, and at 118px of plot height two series a couple of
  // points apart were a single thick stroke.
  /* 210 unless the caller asks for less. The default is the Options panel's:
     at 118px of plot height two series a couple of points apart were a single
     thick stroke. The charting workspace's pane asks for less because it is one
     of a stack under a price chart rather than a panel of its own. */
  const W = width, H = opts.height || 210;
  /* b leaves room for the date row. r is the caller's when it is stacked under
     a chart with value tags, whose gutter is 74: at 58 this plot ran 16px
     further right than the price above it, so its bars and dividers did not
     line up with the price's. */
  const m = { t: 10, r: opts.marginRight || 58, b: 22, l: 8 };
  const plotW = W - m.l - m.r, plotH = H - m.t - m.b;
  const all = [...macd, ...signal, ...hist].filter((v) => v !== null && isFinite(v));
  if (!all.length) return document.createTextNode('');
  let [lo, hi] = extentOf(all);
  lo = Math.min(lo, 0); hi = Math.max(hi, 0);
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
    gridLayer.appendChild(s('text', { x: m.l + plotW + 6, y: Y(t) + 3.5, fill: C.ink2, 'font-size': CF.tick, 'font-weight': CW.tick }, fmt(t, 2)));
  });
  gridLayer.appendChild(s('line', { x1: m.l, y1: Y(0), x2: m.l + plotW, y2: Y(0), stroke: C.baseline, 'stroke-width': 1 }));
  // The price chart's dividers, carried down through this pane.
  if (opts.sessions && n > 1) drawDividers(gridLayer, dividerMarks(labels, n), X, m.t, m.t + plotH);

  // The histogram is data, so it arrives with the lines rather than with the
  // frame — one fade for the whole set, not 126 individually animated columns.
  const histLayer = s('g', { 'data-fade': animating ? DRAW_MS * 0.55 : null });
  root.appendChild(histLayer);
  const bw = Math.max(1.5, (plotW / n) - 2); // 2px surface gap between columns
  const histBar = (v, x, w) => {
    const y0 = Y(0), y1 = Y(v);
    const h = Math.abs(y1 - y0);
    histLayer.appendChild(s('rect', {
      x, y: Math.min(y0, y1), width: w, height: Math.max(h, 1),
      // Green above zero rather than the MACD line's blue. The bars and the line
      // are different quantities and must not share a hue; green/red also matches
      // the sign convention the histogram is already encoding.
      fill: v >= 0 ? MACD_HIST_POS : MACD_HIST_NEG, opacity: 0.5,
      rx: Math.min(2, w / 2),
    }));
  };
  if (n > plotW * 3) {
    /* One a pixel column past three bars to a pixel, as the price chart's
     * volume strip does: the column's highest bar above zero and its lowest
     * below, the outline its bars drawn one by one made. The All range is
     * 16,296 of them on IBM's pane, in about 1,200 pixels. */
    const cols = new Map();
    hist.forEach((v, i) => {
      if (v === null || !isFinite(v)) return;
      const c = Math.floor(X(i));
      const held = cols.get(c) || { up: null, down: null };
      if (v >= 0) held.up = held.up === null ? v : Math.max(held.up, v);
      else held.down = held.down === null ? v : Math.min(held.down, v);
      cols.set(c, held);
    });
    cols.forEach((col, c) => {
      if (col.up !== null) histBar(col.up, c, 1);
      if (col.down !== null) histBar(col.down, c, 1);
    });
  } else {
    hist.forEach((v, i) => {
      if (v === null || !isFinite(v)) return;
      histBar(v, X(i) - bw / 2, bw);
    });
  }

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
      x: nearRight ? cx - 6 : cx + 6, y: m.t + 11, fill: tone, 'font-size': CF.tick,
      'font-weight': 600, 'text-anchor': nearRight ? 'end' : 'start',
    }, `${xover.bullish ? 'Bullish' : 'Bearish'} cross${
      xover.barsAgo
        ? ` · ${xover.barsAgo} ${opts.unit || 'bar'}${xover.barsAgo === 1 ? '' : 's'} ago`
        : ' · latest bar'}`));
  }

  [[macd, C.brand, 'MACD'], [signal, C.s7, 'Signal']].forEach(([vals, color]) => {
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
    /* The same calendar ticks as lineChart, so this pane's axis reads like the
     * RSI pane above it. It printed three raw labels, which was tolerable as
     * "2026-06-12" and not once the pane drew minute bars: it wrote
     * "2026-09-21T09:30:00-04:00" under the chart. The three marks stay as the
     * fallback for labels that are not dates. */
    const ticks = timeTicks(labels, X, 46);
    if (ticks.length) {
      ticks.forEach((t) => {
        axisLayer.appendChild(s('text', {
          x: X(t.i), y: H - 5, fill: C.muted, 'font-size': CF.tick, 'text-anchor': 'middle',
        }, t.text));
      });
    } else {
      const marks = [0, Math.floor((labels.length - 1) / 2), labels.length - 1];
      marks.forEach((i, k) => {
        axisLayer.appendChild(s('text', {
          x: X(i), y: H - 5, fill: C.muted, 'font-size': CF.tick,
          'text-anchor': k === 0 ? 'start' : k === 2 ? 'end' : 'middle',
        }, labels[i]));
      });
    }
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
    showTip(tipRows(barLabelText(labels[i]), [
      [`<span style="color:${C.brand}">■</span> MACD`, fmt(macd[i], 3)],
      [`<span style="color:${C.s7}">■</span> Signal`, fmt(signal[i], 3)],
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
      'text-anchor': q.anchor, fill: q.fill, 'font-size': CF.label,
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
      fill: C.muted, 'font-size': CF.tick }, fmt(t, 0)));
    root.appendChild(s('text', { x: m.l - 8, y: Y(t) + 3, 'text-anchor': 'end',
      fill: C.muted, 'font-size': CF.tick }, fmt(t, 0)));
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
      fill: colour, 'font-size': CF.label, 'font-weight': 600,
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
      fill: C.muted, 'font-size': CF.tick },
    fmt(t, Math.abs(t) < 10 ? 1 : 0) + (opts.xUnit === '%' ? '%' : '')));
  });
  niceTicks(y0, y1, 5).forEach((t) => {
    root.appendChild(s('line', { x1: m.l, x2: m.l + plotW, y1: Y(t), y2: Y(t),
      stroke: C.grid, 'stroke-width': 1, opacity: 0.5 }));
    root.appendChild(s('text', { x: m.l - 8, y: Y(t) + 3, 'text-anchor': 'end',
      fill: C.muted, 'font-size': CF.tick },
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
      'text-anchor': 'middle', fill: C.muted, 'font-size': CF.label }, opts.xLabel));
  }
  if (opts.yLabel) {
    root.appendChild(s('text', {
      x: 12, y: m.t + plotH / 2, 'text-anchor': 'middle', fill: C.muted,
      'font-size': CF.label, transform: `rotate(-90 12 ${m.t + plotH / 2})`,
    }, opts.yLabel));
  }

  // Biggest first, so a small bubble is never hidden underneath a large one.
  [...usable].sort((a, b) => (Math.abs(b.size) || 0) - (Math.abs(a.size) || 0))
    .forEach((p) => {
      const cx = X(p.x); const cy = Y(p.y); const r = R(p.size);
      const dot = s('circle', {
        cx, cy, r, fill: p.color || C.brand, 'fill-opacity': 0.75,
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
          'font-size': CF.tick, 'font-weight': 600, 'pointer-events': 'none',
        }, p.label));
      }
    });

  return root;
}
