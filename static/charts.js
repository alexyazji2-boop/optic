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
};

// Which CSS custom property backs each slot.
const C_VARS = {
  ink: '--ink', ink2: '--ink-2', muted: '--ink-muted',
  grid: '--grid', baseline: '--baseline', surface: '--surface',
  s1: '--s1', s2: '--s2', s3: '--s3', s4: '--s4',
  s5: '--s5', s6: '--s6', s7: '--s7', s8: '--s8',
  pos: '--pos', neg: '--neg', mid: '--mid',
  good: '--good', warn: '--warn', serious: '--serious', critical: '--critical',
  refSR: '--ref-sr', refFib: '--ref-fib',
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
  const pad = 14;
  const rect = tip.getBoundingClientRect();
  let x = evt.clientX + pad;
  let y = evt.clientY + pad;
  if (x + rect.width > window.innerWidth - 8) x = evt.clientX - rect.width - pad;
  if (y + rect.height > window.innerHeight - 8) y = evt.clientY - rect.height - pad;
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
}

function hideTip() { TIP().classList.remove('on'); }

function tipRows(title, rows) {
  return `<div class="t-title">${title}</div>` + rows
    .map(([k, v]) => `<div class="t-row"><span>${k}</span><span>${v}</span></div>`)
    .join('');
}

/* ------------------------------------------------------------- line charts */

/**
 * Multi-series line chart with an optional set of horizontal reference lines
 * (used for Fibonacci levels and gamma walls). Single y-scale only — two
 * measures of different magnitude get two charts, never two axes.
 */
function lineChart(opts) {
  const {
    series = [], labels = [], height = 220, refLines = [],
    yFormat = (v) => fmt(v, 2), valueFormat = null, zeroLine = false,
    markerLast = true, width = 720,
    // {open, high, low, close} arrays. Drawn as OHLC candles under the series.
    // Folded into this chart rather than a separate function so candles inherit
    // the axis, date labels, reference-line placement and hover layer.
    candles = null,
    // 'expand' (default) grows the y-axis to include every reference line.
    // 'clip' sizes the axis from the price data alone and drops lines that fall
    // outside it — a chart with levels 25% away otherwise compresses the actual
    // price action into a thin band in the middle.
    refLineFit = 'expand',
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
  } = opts;

  const W = width;
  const H = height;
  const m = { t: 12, r: 58, b: 22, l: 8 };
  const plotW = W - m.l - m.r;
  const plotH = H - m.t - m.b;

  const all = [];
  series.forEach((se) => se.values.forEach((v) => { if (v !== null && isFinite(v)) all.push(v); }));
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
  const X = (i) => m.l + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const Y = (v) => m.t + plotH - ((v - lo) / (hi - lo)) * plotH;

  const root = svgRoot(W, H);
  // Scale gridline count with available height — a fixed 4 ticks leaves a tall
  // chart with a sparse, hard-to-read axis. ~65px per tick keeps labels legible.
  const ticks = niceTicks(lo, hi, Math.max(3, Math.min(8, Math.round(plotH / 65))));

  let lastTickLabel = null;
  ticks.forEach((t) => {
    root.appendChild(s('line', {
      x1: m.l, y1: Y(t), x2: m.l + plotW, y2: Y(t), stroke: C.grid,
      'stroke-width': 1, opacity: 0.55,
    }));
    // A fine step plus a coarse yFormat can round neighbouring ticks to the same
    // string; draw the gridline but skip the repeated label.
    const text = yFormat(t);
    if (text === lastTickLabel) return;
    lastTickLabel = text;
    root.appendChild(s('text', {
      x: m.l + plotW + 6, y: Y(t) + 3.5, fill: C.muted, 'font-size': 10.5,
      'font-variant-numeric': 'tabular-nums',
    }, text));
  });

  if (zeroLine && lo < 0 && hi > 0) {
    root.appendChild(s('line', {
      x1: m.l, y1: Y(0), x2: m.l + plotW, y2: Y(0), stroke: C.baseline, 'stroke-width': 1,
    }));
  }

  // Reference lines sit under the data: they are context, not a series. Once the
  // scale is fixed, anything outside it is dropped rather than clamped to the
  // edge, where it would read as a real level sitting at the chart boundary.
  const visibleRefs = refLines.filter(
    (r) => isFinite(r.value) && (refLineFit !== 'clip' || (r.value >= lo && r.value <= hi)),
  );
  visibleRefs.forEach((r) => {
    root.appendChild(s('line', {
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

  vMarkers.forEach((mk) => {
    if (!(mk.index >= 0 && mk.index < n)) return;
    const cx = X(mk.index);
    root.appendChild(s('line', {
      x1: cx, y1: m.t, x2: cx, y2: m.t + plotH, stroke: mk.color || C.ink2,
      'stroke-width': 1.4, 'stroke-dasharray': '6 4', opacity: 0.75,
    }));
    if (mk.label) {
      // Flip the anchor near the right edge so the text stays inside the plot.
      const nearRight = cx > m.l + plotW * 0.62;
      root.appendChild(s('text', {
        x: nearRight ? cx - 6 : cx + 6, y: m.t + 11, fill: mk.color || C.ink2,
        'font-size': 10.5, 'font-weight': 600,
        'text-anchor': nearRight ? 'end' : 'start',
      }, mk.label));
    }
    if (isFinite(mk.value)) {
      root.appendChild(s('circle', {
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
    r.y = Math.min(Math.max(r.lineY - 4, prevY + LABEL_GAP), m.t + plotH - 2);
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
      root.appendChild(s('line', {
        x1: x, y1: Y(hh), x2: x, y2: Y(ll), stroke: colour, 'stroke-width': 1,
      }));
      // A doji (open === close) has zero height, which would render nothing —
      // floor it at 1px so flat bars are still visible.
      const top = Y(Math.max(oo, cc));
      const height = Math.max(1, Math.abs(Y(oo) - Y(cc)));
      // Both directions filled. Hollow-up is a real convention on some platforms,
      // but mixing it with filled-down makes the two look like different kinds of
      // mark rather than the same mark in two colours.
      root.appendChild(s('rect', {
        x: x - body / 2, y: top, width: body, height,
        fill: colour, stroke: colour, 'stroke-width': 1,
      }));
    }
  }

  series.forEach((se) => {
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
      }));
    }
    root.appendChild(s('polyline', {
      points: pts.join(' '), fill: 'none', stroke: se.color,
      'stroke-width': se.width || 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round',
      'stroke-dasharray': se.dash || null, opacity: se.opacity || 1,
    }));

    if (markerLast && se.marker !== false) {
      const lastIdx = se.values.reduce((acc, v, i) => (v !== null && isFinite(v) ? i : acc), -1);
      if (lastIdx >= 0) {
        // 2px surface ring keeps the end dot legible where lines cross.
        root.appendChild(s('circle', {
          cx: X(lastIdx), cy: Y(se.values[lastIdx]), r: 4,
          fill: se.color, stroke: C.surface, 'stroke-width': 2,
        }));
      }
    }
  });

  /* Labels go on last, above the series: underneath, price and moving-average
   * lines ran straight through the text. Each sits on an opaque pill so it stays
   * readable wherever it lands, and takes its line's color so you can tell at a
   * glance which level it belongs to. */
  labeled.forEach((r) => {
    const w = r.text.length * 5.5 + 10;
    // Anchored to the right edge of the plot: the left is where the series
    // begins, and tags stacked there sat directly on top of the price.
    const x = m.l + plotW - w - 2;
    root.appendChild(s('rect', {
      x, y: r.y - 9.5, width: w, height: 13, rx: 3,
      fill: C.surface, opacity: 0.86,
    }));
    root.appendChild(s('text', {
      x: x + 5, y: r.y, fill: r.color, 'font-size': 10, opacity: 0.9,
      'font-variant-numeric': 'tabular-nums',
    }, r.text));
  });

  if (labels.length) {
    const marks = [0, Math.floor((labels.length - 1) / 2), labels.length - 1];
    marks.forEach((i, k) => {
      root.appendChild(s('text', {
        x: X(i), y: H - 6, fill: C.muted, 'font-size': 10,
        'text-anchor': k === 0 ? 'start' : k === 2 ? 'end' : 'middle',
      }, labels[i]));
    });
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

  const overlay = s('rect', {
    x: m.l, y: m.t, width: plotW, height: plotH, fill: 'transparent',
    style: 'cursor:crosshair',
  });
  overlay.addEventListener('mousemove', (evt) => {
    const box = root.getBoundingClientRect();
    const scale = W / box.width;
    const localX = (evt.clientX - box.left) * scale;
    let i = Math.round(((localX - m.l) / plotW) * (n - 1));
    i = Math.max(0, Math.min(n - 1, i));
    cross.setAttribute('x1', X(i));
    cross.setAttribute('x2', X(i));
    cross.setAttribute('opacity', 0.45);
    const rows = [];
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
    showTip(tipRows(labels[i] || `#${i + 1}`, rows), evt);
  });
  overlay.addEventListener('mouseleave', () => {
    hideTip();
    cross.setAttribute('opacity', 0);
    dots.forEach((d) => d.setAttribute('opacity', 0));
  });
  root.appendChild(overlay);

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
    bar.addEventListener('mousemove', (evt) => showTip(
      tipRows(r.label, (r.detail || [['Value', format(v)]])), evt,
    ));
    bar.addEventListener('mouseleave', hideTip);
    root.appendChild(bar);

    root.appendChild(s('text', {
      x: m.l - 8, y: Y(i) + 3.5, fill: C.ink2, 'font-size': 10.5, 'text-anchor': 'end',
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
      x: m.l - 8, y: y - 3, fill: C.warn, 'font-size': 9.5, 'text-anchor': 'end',
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
  niceTicks(lo, hi, 3).forEach((t) => {
    root.appendChild(s('line', { x1: m.l, y1: Y(t), x2: m.l + plotW, y2: Y(t), stroke: C.grid, 'stroke-width': 1 }));
    root.appendChild(s('text', { x: m.l + plotW + 6, y: Y(t) + 3.5, fill: C.muted, 'font-size': 10 }, fmt(t, 2)));
  });
  root.appendChild(s('line', { x1: m.l, y1: Y(0), x2: m.l + plotW, y2: Y(0), stroke: C.baseline, 'stroke-width': 1 }));

  const bw = Math.max(1.5, (plotW / n) - 2); // 2px surface gap between columns
  hist.forEach((v, i) => {
    if (v === null || !isFinite(v)) return;
    const y0 = Y(0), y1 = Y(v);
    const h = Math.abs(y1 - y0);
    root.appendChild(s('rect', {
      x: X(i) - bw / 2, y: Math.min(y0, y1), width: bw, height: Math.max(h, 1),
      fill: v >= 0 ? C.pos : C.neg, opacity: 0.55, rx: Math.min(2, bw / 2),
    }));
  });

  /* Mark the last crossover. This is the one event the panel exists to show, and
   * finding it by eye on overlapping lines is exactly what it shouldn't require. */
  const xover = opts.cross;
  if (xover && xover.index >= 0 && xover.index < n) {
    const cx = X(xover.index);
    const tone = xover.bullish ? C.good : C.critical;
    root.appendChild(s('line', {
      x1: cx, y1: m.t, x2: cx, y2: m.t + plotH, stroke: tone,
      'stroke-width': 1.4, 'stroke-dasharray': '6 4', opacity: 0.75,
    }));
    // A dot at the intersection itself, so the eye lands on the level too.
    if (isFinite(macd[xover.index])) {
      root.appendChild(s('circle', {
        cx, cy: Y(macd[xover.index]), r: 3.4, fill: tone,
        stroke: C.surface, 'stroke-width': 1.5,
      }));
    }
    // Label placed inside whichever half has room.
    const nearRight = cx > m.l + plotW * 0.62;
    root.appendChild(s('text', {
      x: nearRight ? cx - 6 : cx + 6, y: m.t + 11, fill: tone, 'font-size': 10.5,
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
      }));
    }
  });

  if (labels && labels.length) {
    const marks = [0, Math.floor((labels.length - 1) / 2), labels.length - 1];
    marks.forEach((i, k) => {
      root.appendChild(s('text', {
        x: X(i), y: H - 5, fill: C.muted, 'font-size': 10,
        'text-anchor': k === 0 ? 'start' : k === 2 ? 'end' : 'middle',
      }, labels[i]));
    });
  }

  const cross = s('line', { y1: m.t, y2: m.t + plotH, stroke: C.ink2, 'stroke-width': 1, opacity: 0 });
  root.appendChild(cross);
  const overlay = s('rect', { x: m.l, y: m.t, width: plotW, height: plotH, fill: 'transparent', style: 'cursor:crosshair' });
  overlay.addEventListener('mousemove', (evt) => {
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
  });
  overlay.addEventListener('mouseleave', () => { hideTip(); cross.setAttribute('opacity', 0); });
  root.appendChild(overlay);
  return root;
}
