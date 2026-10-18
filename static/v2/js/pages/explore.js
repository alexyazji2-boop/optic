// Discover, Explore. A reading of what is worth a look, the screens by the
// question each asks, the sectors against the S&P by their own week, and the
// cross-asset moves ranked against each instrument's own typical day. From
// /api/scanners, /api/scanners/groups, /api/sectors/board and /api/home.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, clean, isNum } from '../core/format.js';
import { skeleton, empty } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { groupTabs } from './tabs.js';

const RANGE_PER_SIGMA = 1.6;
let D = {}, live = true, mainEl = null;

/** The classic ranking: each move against its own typical day (ATR ÷ 1.6). */
export function rankedMoves(home) {
  const groups = ((home || {}).macro || {}).groups || {};
  const rows = [];
  Object.entries(groups).forEach(([group, list]) => (list || []).forEach((i) => {
    if (!isNum(i.chg_1d)) return;
    const typical = isNum(i.atr_pct) && i.atr_pct > 0 ? i.atr_pct / RANGE_PER_SIGMA : null;
    rows.push({ group, label: i.label, symbol: i.symbol, chg: i.chg_1d, rel: typical ? Math.abs(i.chg_1d) / typical : null });
  }));
  // an index and its future are one reading
  const seen = new Set();
  return rows.sort((a, b) => (b.rel || 0) - (a.rel || 0)).filter((r) => { const k = r.label.replace(/ futures$/, ''); if (seen.has(k)) return false; seen.add(k); return true; });
}

function readings() {
  const sc = D.scans || {}, mv = rankedMoves(D.home), sb = D.board || {};
  const rows = [];
  if (sc.ready) rows.push(['What is screenable', `${sc.considered} names`, `${sc.considered} of the ${sc.universe_size}-symbol universe clear the price and volume filters.`]);
  if (mv.length) { const t = mv[0]; rows.push(t.rel !== null && t.rel < 1 ? ['A quiet tape', `${t.label} ${signed(t.chg)}`, 'Even the biggest move is inside its own typical day.'] : ['Biggest move', `${t.label} ${signed(t.chg)}`, isNum(t.rel) ? `${num(t.rel, 1)} times its own typical day.` : '']); }
  const sec = (sb.rows || []).filter((r) => r.available && isNum(r.rel_week_pct));
  if (sec.length) { const a = sec.filter((r) => r.rel_week_pct > 0).length, sh = a / sec.length; rows.push(['Sector breadth', `${a} of ${sec.length} ahead of ${sb.benchmark || 'SPY'}`, sh >= 0.6 ? 'Broad: most sectors beat the index this week.' : sh <= 0.4 ? 'Carried by the heaviest sectors.' : 'Split.']); }
  if (!rows.length) return '';
  return html`<section class="section" aria-labelledby="ex-r"><h2 class="t-h2" id="ex-r">What is worth a look</h2><p class="section-sub">A reading of the three sections below, not a fourth thing to read.</p>
    <dl class="reads-dl">${rows.map(([k, v, n]) => html`<div><dt>${k}</dt><dd><b>${v}</b> <span class="t-muted">${n}</span></dd></div>`)}</dl></section>`;
}

function screens() {
  const sc = D.scans, gr = D.groups;
  if (sc === undefined) return html`<section class="section">${skeleton('rows', 3, 'Loading the screens')}</section>`;
  const groups = (gr && gr.groups) || (sc && sc.scans ? [{ id: 'all', name: 'Screens', scans: sc.scans }] : []);
  return html`<section class="section" aria-labelledby="ex-s"><div class="section-head"><div><h2 class="t-h2" id="ex-s">Screens</h2><p class="section-sub">${sc && sc.ready ? `Each screen asks one question of those ${sc.considered} names and opens its ranked results on Scan.` : sc && (sc.scans || []).length ? 'The universe ranking is still building in the background. The screens open, and fill once it lands.' : 'The scanner catalogue is unavailable right now.'}</p></div></div>
    <div class="scan-groups">${groups.map((g) => html`<div class="sg"><h3>${g.name}</h3>${g.blurb ? html`<p class="t-muted">${clean(g.blurb)}</p>` : ''}<ul class="plain">${(g.scans || []).map((s) => html`<li><a href="#/scan?id=${encodeURIComponent(s.id)}"><b>${s.name}</b></a><br><small class="t-muted">${clean(s.looks_for || '')}</small></li>`)}</ul></div>`)}</div>
    ${gr && gr.note ? html`<p class="asof">${clean(gr.note)}</p>` : ''}</section>`;
}

function sectors() {
  const b = D.board;
  if (b === undefined) return '';
  const rows = ((b || {}).rows || []).filter((r) => r.available);
  if (!rows.length) return '';
  return html`<section class="section" aria-labelledby="ex-c"><h2 class="t-h2" id="ex-c">Sectors</h2><p class="section-sub">Every sector against ${b.benchmark || 'SPY'}, by its own week. Rotation is where money moved, not where it is.</p>
    <div class="tscroll"><table class="t"><thead><tr><th>Sector</th><th>Week</th><th>Month</th><th>Read</th></tr></thead><tbody>${rows.map((r) => html`<tr><td><a href="#/${r.symbol}">${r.symbol}</a> ${r.name}</td><td class="${r.rel_week_pct >= 0 ? 'up' : 'down'}">${signed(r.rel_week_pct)}</td><td class="${r.rel_month_pct >= 0 ? 'up' : 'down'}">${signed(r.rel_month_pct)}</td><td title="${(r.rotation || {}).note || ''}">${(r.rotation || {}).label || ''}</td></tr>`)}</tbody></table></div>
    <p><a class="textlink" href="#/macro">The sector board and rotation are on Macro ${icon('arrow')}</a></p></section>`;
}

function crossAsset() {
  const mv = rankedMoves(D.home);
  if (!mv.length) return '';
  return html`<section class="section" aria-labelledby="ex-x"><div class="section-head"><div><h2 class="t-h2" id="ex-x">Cross-asset</h2><p class="section-sub">Every instrument's move against its own typical day, biggest first. A 1.0× move is an ordinary day for that instrument.</p></div>
      ${miloButton('Ask Milo about the biggest move', { ask: `Why is ${mv[0].label} moving ${signed(mv[0].chg)} today, and does it matter for stocks?`, context: 'Discover, Explore' })}</div>
    <ul class="xa">${mv.map((r) => html`<li><a href="#/instrument/${encodeURIComponent(r.symbol)}"><span>${r.label}</span><b class="${r.chg >= 0 ? 'up' : 'down'}">${signed(r.chg)}</b><small class="t-muted">${isNum(r.rel) ? `${num(r.rel, 1)}×` : ''}</small></a></li>`)}</ul></section>`;
}

function paint() {
  if (!live) return;
  const missing = [D.scans === null && 'the screen catalogue', D.board === null && 'the sector board', D.home === null && 'the cross-asset instruments'].filter(Boolean);
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">Explore</h1>${groupTabs('discover', 'explore')}</header>
    ${missing.length === 3 ? '' : html`${readings()}${screens()}${sectors()}${crossAsset()}`}
    ${missing.length === 3 ? html`<div class="state err" role="alert"><p class="t-h3">Explore did not load</p><p>None of its sources answered: ${missing.join(', ')}.</p><button type="button" class="btn btn-sm" data-v2-retry="explore">Try again</button></div>`
      : missing.length ? html`<p class="stale">Unavailable right now: ${missing.join(', ')}. Everything else on this page still works.</p>` : ''}`);
}

export async function render(main) {
  live = true; mainEl = main; D = {};
  document.title = 'Explore, Optic';
  provideContext(() => ({ view: 'explore', macro: (D.home || {}).macro }));
  paint();
  const step = (p, set) => p.then(set, () => set(null)).finally(() => { if (live) paint(); });
  step(api.get('/api/scanners', { ttl: 120000 }), (d) => { D.scans = d; });
  step(api.get('/api/scanners/groups', { ttl: 600000 }), (d) => { D.groups = d; });
  step(api.get('/api/sectors/board', { ttl: 120000 }), (d) => { D.board = d; });
  step(api.get('/api/home', { ttl: 20000, timeout: 30000 }), (d) => { D.home = d; });
}
export function dispose() { live = false; }
export const retry = { explore: (m) => render(m) };
void empty;
