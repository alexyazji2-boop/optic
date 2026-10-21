// Markets, Macro. The macro regime and what it is made of, the S&P's expected
// move, then breadth, the yield curve, rotation, economic data, stock maps,
// currencies, the cross-asset dashboard and ratios, correlation and dispersion,
// the sector board, sector strength, themes and pair trades, one tab each.
//
// /api/market is about 40 symbols and slow cold; everything else loads beside
// it. The only paid piece is a Sector Read, written on request.
import { $, html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, compact, clean, capFirst, shortDate, isNum, esc, dir } from '../core/format.js';
import { lineChart, spark, mountCharts } from '../ui/chart.js';
import { skeleton, empty, failed, how } from '../ui/states.js';
import { groupedTabs } from '../ui/grouptabs.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { sectionHead } from './tabs.js';
import { sectorBoard, sectorReadBlock, loadSectorRead } from './market-shared.js';
import { poll } from '../core/poll.js';

let D = {}, live = true, mainEl = null, tabState = { g: 0, s: {} }, refresh = null;
const kv = (rows, n = 3) => html`<dl class="kv" style="--kv:${n}">${rows.filter(Boolean).map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
const ask = (label, q) => miloButton(label, { ask: q, context: 'Markets, Macro' });
const pct = (v, dp = 1) => (isNum(v) ? `${num(v, dp)}%` : 'n/a');
const instLink = (sym, label) => html`<a href="#/instrument/${encodeURIComponent(sym)}">${label}</a>`;

function plain(m) {
  const s = m.sectors || {}, b = s.breadth || {}, evc = b.equal_vs_cap || {}, rg = (m.macro || {}).regime || '';
  return html`<ul class="desk-lead">
    <li>The market leans ${/off/.test(rg) ? 'cautious (risk-off)' : /on/.test(rg) ? 'confident (risk-on)' : 'neither way'}: ${clean((m.macro || {}).stance || '')}</li>
    <li>${isNum(b.pct_sectors_above_200sma) ? `${num(b.pct_sectors_above_200sma, 0)}% of the 11 sector funds are above their 200-day average` : ''}${isNum(evc.chg_3m_pct) ? `${isNum(b.pct_sectors_above_200sma) ? '; ' : ''}the equal-weight S&P 500 is ${evc.chg_3m_pct >= 0 ? 'keeping up with' : 'falling behind'} the cap-weighted index (${signed(evc.chg_3m_pct)} over 3 months).` : '.'}</li>
    ${s.rotation_note ? html`<li>${clean(s.rotation_note)}</li>` : ''}</ul>`;
}

function regimeBlock(m) {
  const x = m.macro || {}, inst = x.instruments || {};
  const facs = (x.factors || []).slice().sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  const peak = Math.max(...facs.map((f) => Math.abs(f.contribution)), 1);
  return html`<section class="section" aria-labelledby="mr-h"><div class="section-head"><div><p class="t-label">Macro regime</p><h2 class="t-display-m" id="mr-h">${capFirst(x.regime || '')}</h2></div>${ask('Ask Milo about the regime', 'What is driving the macro regime right now, and what would change it?')}</div>
    ${kv([['Risk score', html`<b>${signed(x.risk_score, 1, '')}</b>`], ['3-month to 10-year curve', html`<span class="${x.curve_3m10y < 0 ? 'down' : ''}">${signed(x.curve_3m10y, 2, ' pts')}</span>`], ['VIX', num((inst['^VIX'] || {}).last, 2)]], 3)}
    <p>${clean(x.stance || '')}</p><ul class="plain">${(x.notes || []).map((n) => html`<li>${clean(n)}</li>`)}</ul>
    <details class="more-inline"><summary>How the score is built, ${facs.length} terms</summary><ul class="factor-bars">${facs.map((f) => html`<li><span class="fb-l">${f.factor} <small class="t-muted">${clean(f.rule || '')}</small></span><span class="fb-track"><span class="fb-bar ${f.contribution >= 0 ? 'pos' : 'neg'}" style="width:${(Math.abs(f.contribution) / peak) * 50}%"></span></span><span class="fb-v">${signed(f.contribution, 1, '')}</span></li>`)}</ul>
    <p class="asof">${facs.length} terms add to ${signed(x.risk_score, 1, '')}.${x.score_unattributed ? ` ${signed(x.score_unattributed, 1, '')} is not attributed to a term.` : ''}</p></details>
    ${expected(x.expected_move)}</section>`;
}
function expected(em) {
  if (!em || !isNum(em.implied_pct)) return '';
  return html`<h3>Expected S&amp;P move, from the VIX</h3><p>${clean(em.reading || '')}</p>
    ${kv([['Options price', html`±${num(em.implied_pct, 2)}% a day <small class="t-muted">±${num(em.implied_points, 0)} points, from the VIX</small>`], ['The S&P moves', html`${num(em.atr_pct, 2)}% a day <small class="t-muted">${num(em.atr14, 0)} points, average over 14 sessions</small>`], ['On one footing', isNum(em.ratio) ? html`${num(em.ratio, 1)}× <small class="t-muted">priced against delivered</small>` : 'n/a']], 3)}
    ${how(html`<p>Options price: the VIX (${num(em.vix, 1)}) divided by 16, as a share of the index. The S&amp;P moves: the 14-session average true range. On one footing: ±${num(em.implied_pct, 2)}% priced against ±${num(em.realized_pct, 2)}%, the average range divided by 1.6 so a range compares with a one-standard-deviation move.</p>`)}`;
}

/* ---------------- tabs ---------------- */
function breadth() {
  const s = (D.m || {}).sectors || {}, b = s.breadth || {}, evc = b.equal_vs_cap || {}, sp = s.suggested_pair;
  return html`${kv([['Sectors above the 200-day', pct(b.pct_sectors_above_200sma, 0)], ['Sectors above the 50-day', pct(b.pct_sectors_above_50sma, 0)]], 2)}<p>${clean(b.note || '')}</p>
    ${s.rotation_note ? html`<p><b>Rotation.</b> ${clean(s.rotation_note)}</p>` : ''}${sp ? html`<p><b>Strongest against weakest right now:</b> long ${sp.long}, short ${sp.short}. ${clean(sp.note || '')}</p>` : ''}
    ${evc.note ? html`<h3>Equal weight against cap weight (RSP / SPY)</h3>${kv([['3 months', signed(evc.chg_3m_pct)], ['1 year', signed(evc.chg_1y_pct)]], 2)}<p>${clean(evc.note)}</p><div class="chart-slot" data-chart="rsp"></div>` : ''}`;
}
function curve() {
  const inst = ((D.m || {}).macro || {}).instruments || {};
  const keys = [['^IRX', '3 month'], ['^FVX', '5 year'], ['^TNX', '10 year']];
  const now = keys.map(([k]) => (inst[k] || {}).last), ago = keys.map(([k]) => (inst[k] || {}).close_20d_ago);
  const s = now[0], l = now[2];
  return html`<p><b>${isNum(s) && isNum(l) ? (l > s ? `The curve slopes up: the 10-year yields ${num(l - s, 2)} points more than the 3-month.` : `The curve is inverted: the 3-month yields ${num(s - l, 2)} points more than the 10-year.`) : ''}</b></p>
    <div class="tscroll"><table class="t"><thead><tr><th>Maturity</th><th>Now</th><th>20 sessions ago</th><th>Change</th></tr></thead><tbody>${keys.map(([k, lab], i) => html`<tr><td>${instLink(k, lab)}</td><td>${num(now[i], 2)}%</td><td>${num(ago[i], 2)}%</td><td>${isNum(now[i]) && isNum(ago[i]) ? signed(now[i] - ago[i], 2, ' pts') : 'n/a'}</td></tr>`)}</tbody></table></div><p class="asof">Source: Yahoo Finance Treasury yield indices.</p>`;
}
function rotation() {
  const r = D.rot;
  if (r === undefined) return skeleton('lines', 3);
  if (!r || r.error) return empty('Rotation is not available', clean((r || {}).error || ''));
  return html`<p>${Object.entries(r.counts || {}).map(([k, v]) => `${v} ${k}`).join(', ')}. Weekly, against ${r.benchmark}, as of ${shortDate(r.as_of)}.</p>
    <div class="chart-slot" data-chart="rrg"></div>
    ${(r.crossed || []).length ? html`<p><b>Crossed a boundary this week:</b> ${r.crossed.map((c) => `${c.name} (${c.from} to ${c.to})`).join(', ')}.</p>` : ''}
    <div class="tscroll"><table class="t"><thead><tr><th>Sector</th><th>Quadrant</th><th>Strength</th><th>Momentum</th><th>Change in strength</th></tr></thead><tbody>${r.sectors.map((s) => html`<tr><td><a href="#/${s.symbol}">${s.symbol}</a> ${s.name}</td><td>${capFirst(s.quadrant)}${s.previous_quadrant !== s.quadrant ? html` <small class="t-muted">from ${s.previous_quadrant}</small>` : ''}</td><td>${num(s.strength, 1)}</td><td>${num(s.momentum, 1)}</td><td>${signed(s.d_strength, 2, '')}</td></tr>`)}</tbody></table></div>
    ${how(html`<p>Strength is the sector against ${r.benchmark}, normalised so 100 is in line; momentum is the change in that strength. Leading: both above 100. Improving: momentum above, strength below. Weakening: the reverse. Lagging: both below.</p>`)}`;
}
// The rotation map (Classic's charts.js:3641, focusMark 3777): each sector's path over the last weeks to its dot.
// A sector reads on hover, on focus (each is a stop for Tab) and on a tap: its path stands out and a box says its
// quadrant, where it came from, its strength and momentum. Escape, a tap elsewhere or leaving puts it away.
// one listener for the page, not one a redraw: a tap outside the open map's box puts it away
let rrOpen = null;   // {wrap, hide}
document.addEventListener('pointerdown', (e) => { if (rrOpen && !rrOpen.wrap.contains(e.target)) rrOpen.hide(); }, true);
const rrWords = (s) => `${s.symbol}${s.name ? ` ${s.name}` : ''}: ${s.quadrant}${s.previous_quadrant && s.previous_quadrant !== s.quadrant ? `, from ${s.previous_quadrant}` : ''}; strength ${num(s.strength, 1)}, momentum ${num(s.momentum, 1)}, change in strength ${signed(s.d_strength, 2, '')}`;
function rrgChart(r) {
  return (w) => {
    const W = Math.max(300, w), H = Math.min(420, Math.round(W * 0.7)), p = 30;
    const all = r.sectors.flatMap((s) => [...(s.path || []).map((q) => [q.strength ?? q[0], q.momentum ?? q[1]]), [s.strength, s.momentum]]);
    const ext = Math.max(2, ...all.map(([a, b]) => Math.max(Math.abs(a - 100), Math.abs(b - 100)))) * 1.1;
    const X = (v) => p + ((v - (100 - ext)) / (2 * ext)) * (W - 2 * p), Y = (v) => H - p - ((v - (100 - ext)) / (2 * ext)) * (H - 2 * p);
    const cx = X(100), cy = Y(100);
    const rect = (x, y, ww, hh, cls) => `<rect class="rq ${cls}" x="${x}" y="${y}" width="${ww}" height="${hh}"/>`;
    const lab = (x, y, t, end) => `<text class="rq-t" x="${x}" y="${y}"${end ? ' text-anchor="end"' : ''}>${t}</text>`;
    let o = rect(cx, p, W - p - cx, cy - p, 'lead') + rect(p, p, cx - p, cy - p, 'imp') + rect(p, cy, cx - p, H - p - cy, 'lag') + rect(cx, cy, W - p - cx, H - p - cy, 'weak')
      + lab(W - p - 6, p + 14, 'Leading', true) + lab(p + 6, p + 14, 'Improving') + lab(p + 6, H - p - 6, 'Lagging') + lab(W - p - 6, H - p - 6, 'Weakening', true);
    // each label takes the first of four places round its dot that no label already drawn covers (on a phone XLY
    // and XLP, XLB and XLF were printed over each other)
    const taken = [], boxes = (x, y, wd, end) => ({ x0: end ? x - wd : x, x1: end ? x : x + wd, y0: y - 11, y1: y + 2 });
    const hits = (a) => taken.some((b) => a.x0 < b.x1 + 2 && a.x1 > b.x0 - 2 && a.y0 < b.y1 + 1 && a.y1 > b.y0 - 1);
    const spot = (cx2, cy2, sym) => {
      const wd = sym.length * 7.4 + 2;
      const tries = [[cx2 + 6, cy2 - 6, false], [cx2 - 6, cy2 - 6, true], [cx2 + 6, cy2 + 15, false], [cx2 - 6, cy2 + 15, true]];
      const pick = tries.find(([x, y, end]) => !hits(boxes(x, y, wd, end))) || tries[0];
      taken.push(boxes(pick[0], pick[1], wd, pick[2])); return pick;
    };
    r.sectors.forEach((s, k) => {
      const pts = [...(s.path || []).map((z) => [z.strength ?? z[0], z.momentum ?? z[1]]), [s.strength, s.momentum]], x = X(s.strength).toFixed(1), y = Y(s.momentum).toFixed(1);
      const [lx, ly, end] = spot(X(s.strength), Y(s.momentum), String(s.symbol));
      o += `<g class="rr-s" data-rr="${k}" tabindex="0" role="img" aria-label="${esc(rrWords(s))}"><path class="rr-tail" d="${pts.map(([a, b], i) => `${i ? 'L' : 'M'}${X(a).toFixed(1)} ${Y(b).toFixed(1)}`).join('')}"/><circle class="rr-hit" cx="${x}" cy="${y}" r="14"/><circle class="rr-dot" cx="${x}" cy="${y}" r="4"/><text class="rr-t" x="${lx.toFixed(1)}" y="${ly.toFixed(1)}"${end ? ' text-anchor="end"' : ''}>${esc(s.symbol)}</text></g>`;
    });
    const svg = `<svg class="rrg" viewBox="0 0 ${W} ${H}" role="group" aria-label="Sector rotation map. Each sector is a stop: hover, focus or tap one to read it.">${o}</svg>`;
    return {
      html: `<div class="rr-wrap">${svg}<div class="rr-tip" role="status" hidden></div></div>`,
      wire(el) {
        const wrap = el.querySelector('.rr-wrap'), tip = wrap.querySelector('.rr-tip');
        let on = null;
        const hide = () => { if (on) on.classList.remove('is-on'); on = null; tip.hidden = true; if (rrOpen && rrOpen.wrap === wrap) rrOpen = null; };
        const show = (g) => {
          if (on && on !== g) on.classList.remove('is-on');
          on = g; g.classList.add('is-on'); rrOpen = { wrap, hide };
          const s = r.sectors[Number(g.dataset.rr)];
          tip.innerHTML = `<b>${esc(s.symbol)}</b> ${esc(s.name || '')}<em>${esc(capFirst(s.quadrant))}${s.previous_quadrant && s.previous_quadrant !== s.quadrant ? `, from ${esc(s.previous_quadrant)}` : ''}</em><span>Strength ${num(s.strength, 1)}, momentum ${num(s.momentum, 1)}</span><span>Change in strength ${signed(s.d_strength, 2, '')}</span>`;
          tip.hidden = false;
          const d = g.querySelector('.rr-dot').getBoundingClientRect(), b = wrap.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
          let left = d.left - b.left + 14; if (left + tw > b.width - 4) left = Math.max(4, d.left - b.left - tw - 10);
          tip.style.left = `${Math.round(left)}px`; tip.style.top = `${Math.round(Math.max(4, Math.min(b.height - th - 4, d.top - b.top - th / 2)))}px`;
        };
        wrap.addEventListener('pointerover', (e) => { const g = e.target.closest('.rr-s'); if (g && e.pointerType === 'mouse') show(g); });
        wrap.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse' && !wrap.contains(document.activeElement)) hide(); });
        wrap.addEventListener('pointerdown', (e) => { if (e.pointerType === 'mouse') return; const g = e.target.closest('.rr-s'); if (g) { if (g === on) hide(); else show(g); } else hide(); });
        wrap.addEventListener('focusin', (e) => { const g = e.target.closest('.rr-s'); if (g) show(g); });
        wrap.addEventListener('focusout', (e) => { if (!wrap.contains(e.relatedTarget)) hide(); });
        wrap.addEventListener('keydown', (e) => { if (e.key === 'Escape' && on) { hide(); e.stopPropagation(); } });
      },
    };
  };
}
function econ() {
  const cat = D.econCat, s = D.econ;
  if (cat === undefined) return skeleton('lines', 3);
  return html`<div class="chips econ-pills" role="group" aria-label="Series">${((cat || {}).groups || []).flatMap((g) => g.series.map((x) => html`<button type="button" class="chip" data-v2-econ="${x.code}" aria-pressed="${D.econCode === x.code}">${x.label}</button>`))}</div>
    ${!s ? skeleton('chart') : s.error ? empty('This series did not load', clean(s.error)) : html`<h3>${s.label}, ${s.form_label}</h3>
      ${kv([['Latest', html`${num(s.latest.value, 2)}${s.unit === '%' ? '%' : ''} <small class="t-muted">${shortDate(s.latest.date)} ${String(s.latest.date).slice(0, 4)}</small>`], ['Previous', `${num((s.previous || {}).value, 2)}${s.unit === '%' ? '%' : ''}`], ['Change', signed(s.change, 2, s.unit === '%' ? ' pts' : '')], ['12-year average', html`${num(s.average, 2)} <small class="t-muted">${num(s.min, 2)} to ${num(s.max, 2)}</small>`]], 4)}
      <div class="chart-slot" data-chart="econ"></div><p class="asof">${clean(s.note || '')} Source: ${s.source}.</p>`}`;
}
function stockmap() {
  const s = D.map;
  if (s === undefined) return skeleton('chart');
  if (!s || !s.template) return empty('Stock maps are not available', '');
  const ms = s.measures || {}, col = s.template.color, size = s.template.size;
  return html`<div class="chips" role="group" aria-label="Map">${(s.templates || []).map((t) => html`<button type="button" class="chip" data-v2-map="${t.id}" aria-pressed="${t.id === s.template.id}">${t.label}</button>`)}</div>
    <p><b>${clean(s.template.question || '')}</b> Size: ${(ms[size] || {}).label || size}; colour: ${(ms[col] || {}).label || col}.</p>
    ${s.sector ? html`<button type="button" class="textlink" data-v2-map-back>All sectors</button>` : ''}
    <div class="chart-slot" data-chart="map"></div>
    ${!s.sector && (s.drillable || []).length ? html`<div class="chips chips-scroll" role="group" aria-label="Open a sector"><span class="t-label">Open a sector</span>${(s.layout || []).filter((c) => s.drillable.includes(c.symbol)).map((c) => html`<button type="button" class="chip" data-v2-map-sector="${c.symbol}">${c.name || c.symbol}</button>`)}</div>` : ''}
    <details class="more-inline"><summary>The full table</summary><div class="tscroll"><table class="t"><thead><tr><th>Name</th>${Object.keys(ms).map((k) => html`<th>${ms[k].label}</th>`)}</tr></thead><tbody>${(s.rows || []).map((r) => html`<tr><td>${r.symbol} ${r.name || ''}</td>${Object.keys(ms).map((k) => html`<td>${ms[k].unit === '%' ? signed((r.values || r)[k]) : ms[k].unit === '$' ? compact((r.values || r)[k]) : num((r.values || r)[k], 2)}</td>`)}</tr>`)}</tbody></table></div></details>
    ${(s.dropped || []).length ? html`<p class="asof">Left out for missing data: ${s.dropped.map((d) => d.symbol || d).join(', ')}.</p>` : ''}${s.holdings_caveat ? html`<p class="asof">${clean(s.holdings_caveat)}</p>` : ''}`;
}
function mapChart(s) {
  return (w) => {
    const W = Math.max(300, w), lay = s.layout || [];
    if (!lay.length) return '<p class="quiet">This map is drawn as bubbles in the classic app.</p>';
    // the server lays tiles out in percent of the canvas
    const k = Math.max(...lay.map((c) => c.x + c.w)) > 1.5 ? 100 : 1;
    const H = Math.round(W * (W < 600 ? 1.1 : 0.55)), col = s.template.color, dom = s.colour_domain || { min: -5, max: 5 };
    const tone = (v) => { if (!isNum(v)) return 'var(--c-sunk)'; const m = Math.max(Math.abs(dom.min || 0), Math.abs(dom.max || 0)) || 1; const t = Math.max(-1, Math.min(1, v / m)); return t >= 0 ? `color-mix(in srgb, var(--c-pos) ${Math.round(15 + 55 * t)}%, var(--c-plane))` : `color-mix(in srgb, var(--c-neg) ${Math.round(15 + 55 * -t)}%, var(--c-plane))`; };
    const cells = lay.map((c) => { const v = (c.values || {})[col]; const x = (c.x / k) * W, y = (c.y / k) * H, ww = (c.w / k) * W, hh = (c.h / k) * H; const drill = (s.drillable || []).includes(c.symbol) && ww >= 24 && hh >= 24;
      return `<g class="tile" ${drill ? `data-v2-map-sector="${c.symbol}" role="button" tabindex="0"` : ''} aria-label="${esc(c.name || c.symbol)}: ${signed(v)}"><rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${Math.max(0, ww - 2).toFixed(1)}" height="${Math.max(0, hh - 2).toFixed(1)}" rx="3" style="fill:${tone(v)}"/>${ww > 60 && hh > 30 ? `<text x="${(x + 8).toFixed(1)}" y="${(y + 20).toFixed(1)}" class="tile-t">${c.symbol}</text><text x="${(x + 8).toFixed(1)}" y="${(y + 38).toFixed(1)}" class="tile-v">${signed(v)}</text>` : ''}<title>${esc(c.name || c.symbol)}: ${signed(v)}</title></g>`; }).join('');
    return `<svg class="smap" viewBox="0 0 ${W} ${H}" role="group" aria-label="Stock map">${cells}</svg>`;
  };
}
function forex() {
  const f = D.fx;
  if (f === undefined) return skeleton('lines', 3);
  if (!f) return empty('Currencies did not load', '');
  return html`<form class="op-filters" data-v2-fx><label class="field field-sm"><span class="sr">Find a currency</span><input name="q" value="${f.query || ''}" placeholder="Find a currency, such as yen"></label><button class="btn btn-sm" type="submit">Find</button></form>
    ${(f.groups || []).map((g) => html`<h3>${g}</h3><div class="tscroll"><table class="t"><thead><tr><th>Pair</th><th>Last</th><th>Day</th><th>20 days</th><th>Against the 200-day</th><th>Reading</th></tr></thead><tbody>${f.pairs.filter((p) => p.group === g).map((p) => html`<tr><td>${instLink(p.symbol, p.label)}<br><small class="t-muted">Up means ${clean(p.up_means)}</small></td><td>${num((p.snapshot || {}).last, 4)}</td><td>${signed((p.snapshot || {}).chg_1d)}</td><td>${signed((p.snapshot || {}).chg_20d)}</td><td>${signed((p.snapshot || {}).vs_sma200)}</td><td style="text-align:left">${clean(p.reading || '')} <small class="t-muted">${clean(p.driver || '')}</small></td></tr>`)}</tbody></table></div>`)}
    <details class="more-inline"><summary>The five drivers</summary><ul class="plain">${Object.entries(f.drivers || {}).map(([k, v]) => html`<li><b>${capFirst(k)}.</b> ${clean(v)}</li>`)}</ul></details><p class="asof">${f.count} of ${f.total} pairs.</p>`;
}
function crossAsset() {
  const g = ((D.m || {}).macro || {}).groups || {};
  return html`${['volatility', 'rates', 'fx', 'commodities', 'credit', 'crypto'].filter((k) => (g[k] || []).length).map((k) => html`<h3>${capFirst(k === 'fx' ? 'currencies' : k)}</h3><div class="tscroll"><table class="t"><thead><tr><th>Instrument</th><th>Last</th><th>Day</th><th>5 days</th><th>20 days</th><th>Against the 200-day</th><th>RSI</th><th>90 sessions</th></tr></thead>
    <tbody>${g[k].filter((r) => !r.error).map((r) => html`<tr><td>${instLink(r.symbol, r.label)}${r.note ? html`<br><small class="t-muted">${clean(r.note)}</small>` : ''}</td><td>${num(r.last, r.last < 10 ? 3 : 2)}</td><td class="${dir(r.chg_1d)}">${signed(r.chg_1d)}</td><td>${signed(r.chg_5d)}</td><td>${signed(r.chg_20d)}</td><td>${signed(r.vs_sma200)}</td><td>${num(r.rsi, 0)}</td><td>${raw(spark(r.series || []))}</td></tr>`)}</tbody></table></div>`)}`;
}
function ratios() {
  const r = ((D.m || {}).macro || {}).ratios || [];
  return html`<div class="tscroll"><table class="t"><thead><tr><th>Ratio</th><th>Reading</th><th>5 days</th><th>20 days</th><th>60 days</th><th>Trend</th></tr></thead><tbody>${r.map((x) => html`<tr><td><b>${x.name}</b><br><small class="t-muted">${clean(x.reads || '')}</small></td><td>${capFirst(x.signal || '')}${x.signal_note ? html`<br><small>${clean(x.signal_note)}</small>` : ''}</td><td>${signed(x.chg_5d)}</td><td>${signed(x.chg_20d)}</td><td>${signed(x.chg_60d)}</td><td>${raw(spark(x.series || []))}</td></tr>`)}</tbody></table></div>`;
}
function corrDisp() {
  const c = D.ic, d = D.disp;
  return html`<h3>Implied correlation</h3>${c === undefined ? skeleton('lines', 2) : !c || !c.available ? html`<p class="quiet">${clean((c || {}).reason || 'Not available right now.')}</p>` : html`
      ${kv([['Implied correlation', html`${num(c.implied_correlation, 2)} <small class="t-muted">${c.band}</small>`], [`${c.index} implied volatility`, pct(c.index_iv_pct)], ['Weighted component volatility', pct(c.weighted_component_iv_pct)]], 3)}
      <p>${clean(c.plain || '')}</p><p class="asof">${clean(c.dispersion_note || '')} ${clean((c.expiries || {}).note || '')}</p>
      <details class="more-inline"><summary>Components (${c.components_used})</summary><ul class="plain">${(c.components || []).map((x) => html`<li>${x.symbol}: IV ${pct(x.iv_pct)}, weight ${pct(x.weight_pct)}</li>`)}</ul></details><p class="asof">${clean(c.method || '')}</p>`}
    <h3>Dispersion</h3>${d === undefined ? skeleton('lines', 2) : !d || !d.available ? html`<p class="quiet">Not available right now.</p>` : html`
      ${kv([['VIXEQ (average stock)', num(d.vixeq, 1)], ['VIX (index)', num(d.vix, 1)], ['The gap', html`${num(d.gap, 1)} <small class="t-muted">${isNum(d.gap_percentile) ? `${num(d.gap_percentile, 0)}th percentile` : 'history building'}</small>`]], 3)}
      <p>${clean(d.text || '')}</p>${d.evidence ? html`<p class="t-muted">${clean(d.evidence.finding || '')} ${clean(d.evidence.sample || '')}</p>` : ''}<p class="asof">${clean(d.method || '')} As of ${shortDate(d.as_of)}.</p>`}
    ${ask('Ask Milo about implied correlation', 'What is implied correlation telling me about the market right now?')}`;
}
function strength() {
  const s = (D.m || {}).sectors || {};
  return html`<div class="tscroll"><table class="t"><thead><tr><th>Sector</th><th>Day</th><th>1 month</th><th>3 months</th><th>6 months</th><th>RSI</th><th>Against the 50-day</th><th>Against the 200-day</th></tr></thead>
    <tbody>${(s.sectors || []).map((r) => html`<tr><td><a href="#/${r.symbol}">${r.symbol}</a> ${r.name}</td><td class="${dir(r.chg_1d)}">${signed(r.chg_1d)}</td><td>${signed(r.chg_20d)}</td><td>${signed(r.chg_60d)}</td><td>${signed(r.chg_120d)}</td><td>${num(r.rsi, 0)}</td><td>${signed(r.vs_sma50)}</td><td>${signed(r.vs_sma200)}</td></tr>`)}</tbody></table></div>
    <p class="asof">Leaders: ${(s.leaders || []).map((x) => x.name).join(', ')}. Laggards: ${(s.laggards || []).map((x) => x.name).join(', ')}.</p>`;
}
function themes() {
  const s = (D.m || {}).sectors || {};
  const tbl = (rows) => html`<div class="tscroll"><table class="t"><thead><tr><th>Name</th><th>Day</th><th>1 month</th><th>3 months</th><th>Against the 200-day</th></tr></thead><tbody>${rows.map((r) => html`<tr><td><a href="#/${r.symbol}">${r.symbol}</a> ${r.name}${r.breakout_reasons ? html`<br><small class="t-muted">${r.breakout_reasons.map(clean).join('; ')}</small>` : ''}</td><td>${signed(r.chg_1d)}</td><td>${signed(r.chg_20d)}</td><td>${signed(r.chg_60d)}</td><td>${signed(r.vs_sma200)}</td></tr>`)}</tbody></table></div>`;
  return html`<h3>Themes and sub-industries</h3>${tbl(s.themes || [])}
    <h3>Breakout candidates</h3>${(s.breakout_candidates || []).length ? tbl(s.breakout_candidates) : html`<p class="quiet">No sector is set up for a breakout right now.</p>`}
    <h3>Niche industries</h3>${tbl(s.niche || [])}
    <h3>Ratio pair trades</h3><div class="tscroll"><table class="t"><thead><tr><th>Pair</th><th>Ratio</th><th>z-score, 60 days</th><th>5 days</th><th>20 days</th><th>Setup</th></tr></thead><tbody>${(s.pairs || []).map((p) => html`<tr><td><b>${p.pair}</b><br><small class="t-muted">${clean(p.thesis || '')}</small></td><td>${num(p.ratio, 3)}</td><td class="${Math.abs(p.zscore_60d) >= 2 ? 'z-stretched' : ''}">${signed(p.zscore_60d, 1, '')}</td><td>${signed(p.chg_5d)}</td><td>${signed(p.chg_20d)}</td><td style="text-align:left">${clean(p.setup || '')}</td></tr>`)}</tbody></table></div>
    <p class="asof">A z-score beyond ±2 is stretched against the last 60 sessions; it is not a call.</p>`;
}

// The twelve views in four groups (item 13); every view and its name is kept.
const TABS = [
  ['Breadth', breadth, () => { const evc = ((((D.m || {}).sectors || {}).breadth || {}).equal_vs_cap) || {}; return evc.series ? { rsp: (w) => lineChart((evc.dates || []).map((d, i) => ({ d: String(d).slice(0, 10), c: evc.series[i] })), { w, h: 190, dp: 3, label: 'RSP against SPY' }) } : {}; }],
  ['Yield curve', curve], ['Rotation', rotation, () => (D.rot && D.rot.sectors ? { rrg: rrgChart(D.rot) } : {})],
  ['Economic data', econ, () => (D.econ && D.econ.values ? { econ: (w) => lineChart(D.econ.dates.map((d, i) => ({ d, c: D.econ.values[i] })), { w, h: 240, dp: 2, label: D.econ.label, monthStep: 12, measure: D.econ.unit === '%' ? 'points' : 'change', msUnit: D.econ.unit === '%' ? ' pts' : '' }) } : {})],
  ['Stock maps', stockmap, () => (D.map && D.map.template ? { map: mapChart(D.map) } : {})],
  ['Currencies', forex], ['Cross-asset', crossAsset], ['Ratios', ratios], ['Correlation and dispersion', corrDisp],
  ['Sector board', () => html`${sectorBoard(D.board, 'Sector Read')}${sectorReadBlock(D.sread)}`], ['Sector strength', strength], ['Themes and pairs', themes],
];

const MGROUPS = [
  ['Breadth and sectors', ['Breadth', 'Sector board', 'Sector strength', 'Rotation', 'Themes and pairs']],
  ['Rates and the economy', ['Yield curve', 'Economic data']],
  ['Cross-asset', ['Cross-asset', 'Currencies', 'Ratios', 'Correlation and dispersion']],
  ['Stock maps', ['Stock maps']],
];
function paintMore() {
  const h = $('#mc-more', mainEl); if (!h) return;
  const item = (name) => { const [label, fn, charts] = TABS.find((x) => x[0] === name); return { label, render: () => fn(), mount: (p) => { if (charts) mountCharts(p, charts()); } }; };
  const ts = groupedTabs(MGROUPS.map(([label, names]) => ({ label, items: names.map(item) })), { label: 'Macro in depth', state: tabState });
  draw(h, ts.html); ts.wire(h);
}
function paint() {
  if (!live) return;
  const y = window.scrollY;
  draw(mainEl, html`<header class="page-head">${sectionHead('market', 'market')}</header>
    ${D.err ? failed('The macro picture', D.err, { retry: 'market' }) : !D.m ? html`${skeleton('lines', 5, 'Loading about 40 instruments')}<p class="asof" role="status">Loading about 40 instruments. This can take up to 30 seconds.</p>`
    : html`<section class="section" aria-label="The market today"><h2 class="t-h2">The market today, in brief</h2>${plain(D.m)}</section>${regimeBlock(D.m)}`}
    <section class="section" aria-labelledby="mc-more-h"><h2 class="t-h2" id="mc-more-h">In depth</h2><div id="mc-more"></div></section>`);
  paintMore();
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

async function loadMarket(quiet) {
  try { D.m = await api.get('/api/market', { ttl: quiet ? 0 : 60000, force: !!quiet, timeout: 90000 }); D.err = null; } catch (e) { if (!quiet) D.err = e; }
  if (live) paint();
}
export async function render(main) {
  live = true; mainEl = main; tabState = { g: 0, s: {} };
  D = { econCode: 'CPIAUCSL' };
  document.title = 'Macro, Optic';
  provideContext(() => ({ view: 'market', macro: (D.m || {}).macro, sectors: (D.m || {}).sectors, dispersion: D.disp ? Object.assign({}, D.disp, { history: undefined }) : null }));
  paint(); wire(main);
  loadMarket();
  const side = (p, set) => p.then(set, () => set(null)).finally(() => { if (live) paintMore(); });
  side(api.get('/api/rotation?tail=8', { ttl: 600000 }), (d) => { D.rot = d; });
  side(api.get('/api/econ', { ttl: 3600000 }), (d) => { D.econCat = d; });
  side(api.get('/api/econ/CPIAUCSL?years=12', { ttl: 3600000 }), (d) => { D.econ = d; });
  side(api.get('/api/stockmap', { ttl: 600000 }), (d) => { D.map = d; });
  side(api.get('/api/forex', { ttl: 600000 }), (d) => { D.fx = d; });
  side(api.get('/api/implied-correlation', { ttl: 600000, timeout: 60000 }), (d) => { D.ic = d; });
  side(api.get('/api/dispersion', { ttl: 600000 }), (d) => { D.disp = d; });
  side(api.get('/api/sectors/board', { ttl: 120000 }), (d) => { D.board = d; });
  if (refresh) refresh.stop();
  // the boards every minute through the trading day, quietly; paused while hidden, caught up on return (core/poll.js)
  refresh = poll(async (current) => { if (live && current() && D.m && ['pre', 'regular', 'after'].includes((D.m.session || {}).phase)) loadMarket(true); }, { every: 60000, closed: 600000 });
}
export function dispose() { live = false; if (refresh) { refresh.stop(); refresh = null; } }
export const retry = { market: () => loadMarket() };

function wire(main) {
  main.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s);
    let b;
    if ((b = t('[data-v2-econ]'))) { D.econCode = b.dataset.v2Econ; D.econ = null; paintMore(); try { D.econ = await api.get(`/api/econ/${encodeURIComponent(D.econCode)}?years=12`, { ttl: 3600000 }); } catch (err) { D.econ = { error: err.message }; } paintMore(); return; }
    if ((b = t('[data-v2-map]'))) { D.map = undefined; paintMore(); try { D.map = await api.get(`/api/stockmap?template=${encodeURIComponent(b.dataset.v2Map)}`, { ttl: 600000 }); } catch (err) { D.map = null; } paintMore(); return; }
    if ((b = t('[data-v2-map-sector]'))) { const tpl = (D.map.template || {}).id; D.map = undefined; paintMore(); try { D.map = await api.get(`/api/stockmap?template=${encodeURIComponent(tpl)}&sector=${encodeURIComponent(b.dataset.v2MapSector)}`, { ttl: 600000 }); } catch (err) { D.map = null; } paintMore(); return; }
    if (t('[data-v2-map-back]')) { const tpl = (D.map.template || {}).id; D.map = undefined; paintMore(); try { D.map = await api.get(`/api/stockmap?template=${encodeURIComponent(tpl)}`, { ttl: 600000 }); } catch (err) { D.map = null; } paintMore(); return; }
    if ((b = t('[data-v2-sread]'))) { D.sread = { loading: b.dataset.v2Sread }; paintMore(); D.sread = await loadSectorRead(b.dataset.v2Sread); paintMore(); return; }
    if (t('[data-v2-sread-close]')) { D.sread = null; paintMore(); }
  });
  main.addEventListener('keydown', (e) => { const g = e.target.closest('[data-v2-map-sector]'); if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); g.dispatchEvent(new MouseEvent('click', { bubbles: true })); } });
  main.addEventListener('submit', async (e) => { const f = e.target.closest('[data-v2-fx]'); if (!f) return; e.preventDefault(); D.fx = undefined; paintMore(); try { D.fx = await api.get(`/api/forex?q=${encodeURIComponent(f.q.value.trim())}`, { ttl: 600000 }); } catch (err) { D.fx = null; } paintMore(); });
}
