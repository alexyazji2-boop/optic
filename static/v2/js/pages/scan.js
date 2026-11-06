// Discover, Scan. Three ways to find stocks over the same ranked universe:
//   Find stocks: a request in plain words, read as filters the reader reviews before anything runs (Handoff 8, the
//     Describe-It screener: POST /api/screener/read, then POST /api/screener). A fixed parser reads it for free;
//     only words it cannot read go to Milo, which uses one Milo question from the reader's allowance, and never on
//     load. A phrase nothing can screen for is named, never replaced. The result says the exact filters, the
//     universe, the data's dates and sources and its fingerprint, and the screen can be saved and run again.
//   Named scans: thirteen questions already computed (/api/scanners/{id}).
//   Build a screen: the reader's own bounds (POST /api/screener).
// "Does the score work?" replays the score on history (/api/evaluate) when
// asked. Recent requests and the built screen are kept in the classic keys.
import { $, html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, signed, compact, clean, capFirst, dir } from '../core/format.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { watchButton } from '../ui/company.js';
import { hrefFor } from '../nav.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { shortlistBody } from './scan-shortlist.js';
import * as lib from '../core/library.js';
import { provide as provideSave, saveButton } from '../ui/library.js';
import { sectionHead } from './tabs.js';

const RECENT_KEY = 'optic.scan.recent.v1', SCREEN_KEY = 'optic.screener.v1';
const EXAMPLES = ['Strong stocks on the 200-day average right now', 'Near 52-week highs on heavy volume', 'Pullbacks in strong uptrends', 'Under $20 and up 20% in the last 3 months', '10% pull back after 20% rally', '2% or more above prev close'];
let S = {}, live = true, mainEl = null, poll = null;
// What was already asked and screened this visit. Coming back from a result's Dossier shows the same
// answer instead of asking again: a request in words can use a Milo question, and a screen is the
// whole ranked universe (the brief: no expensive scan re-run by an incidental change).
const ASKED = new Map(), SCREENED = new Map();
// Set by Milo's "Find stocks" card when it is pressed (ui/milo.js), read once here: the press is what allows the spend.
const SCAN_GO = 'optic.scan.go.v1';
function pressedInMilo(q) {
  try { const go = sessionStorage.getItem(SCAN_GO); sessionStorage.removeItem(SCAN_GO); return go === q; } catch (e) { return false; }
}
const specKey = (sp) => JSON.stringify({ f: sp.filters, s: sp.states, o: sp.sort, d: sp.direction });
/** The address says which scan, screen or request is on screen, so Back from a result returns to it. */
function remember(q) {
  const want = `#/scan${q ? `?${q}` : ''}`;
  if (location.hash !== want) { try { history.replaceState(history.state, '', `${location.pathname}${location.search}${want}`); } catch (e) { /* a sandboxed frame */ } }
}

const readKey = (k, d) => { if (!holds(store.state.user)) return d; try { const v = JSON.parse(localStorage.getItem(k) || 'null'); return v == null ? d : v; } catch (e) { return d; } };
const writeKey = (k, v) => { if (!holds(store.state.user)) return; try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private */ } };
const blankSpec = () => ({ filters: [], states: [], sort: 'score', direction: 'desc', limit: 50 });

export function scanCell(kind, v) {
  if (v === null || v === undefined) return 'n/a';
  if (kind === 'text') return clean(String(v));
  if (kind === 'pct') return html`<span class="${dir(v)}">${signed(v, 1)}</span>`;
  if (kind === 'pct_plain') return `${num(v, 2)}%`;
  if (kind === 'mult') return `${num(v, 2)}×`;
  if (kind === 'ratio') return `${num(v * 100, 0)}%`;
  if (kind === 'score') return html`<span class="${dir(v)}">${num(v, 0)}</span>`;
  if (kind === 'usd') return `$${compact(v)}`;
  return num(v, 2);
}
/* A bar in the ranked column, and only where the rows spread enough to tell apart (Classic's fillScanBars and
 * inlineBar; parity B9.4): the top momentum scores run 74 to 82, and the same bar 25 times says nothing, while dollar
 * volume or the month's movers have a shape worth seeing. One-sided for a measure that only runs up, from zero either
 * way for a signed one; a share against its whole, a percentile against 100. The figure beside it says the value. */
const ONE_SIDED = new Set(['usd', 'mult', 'ratio', 'pct_plain', 'num']);
export function rankBars(res) {
  const cols = (res || {}).columns || [], rk = res && res.ranked_by && cols.some((c) => c.key === res.ranked_by.key) ? res.ranked_by : null;
  if (!rk) return null;
  const vals = (res.rows || []).map((r) => Number(r[rk.key])).filter(Number.isFinite), abs = vals.map(Math.abs);
  const top = abs.length ? Math.max(...abs) : 0;
  if (!(abs.length >= 3 && top > 0 && (top - Math.min(...abs)) / top >= 0.35)) return null;
  const kind = (cols.find((c) => c.key === rk.key) || {}).kind;
  const max = kind === 'ratio' ? 1 : kind === 'num' && Math.max(...vals) <= 100 ? 100 : top;
  return { key: rk.key, oneSided: ONE_SIDED.has(kind), max };
}
export function cellBar(v, b, w = 52, h = 8) {
  if (!b || v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) || !(b.max > 0)) return '';   // a missing value is no bar, not a zero one
  const x = Number(v), f = Math.min(1, Math.abs(x) / b.max);
  if (b.oneSided) return `<svg class="sc-bar" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><rect class="one" x="0" y="1" width="${Math.max(1.5, f * (w - 1)).toFixed(1)}" height="${h - 2}" rx="2"/></svg>`;
  const mid = w / 2, bw = Math.max(1.5, f * (mid - 1));
  return `<svg class="sc-bar" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><line x1="${mid}" x2="${mid}" y1="0" y2="${h}"/><rect class="${x >= 0 ? 'pos' : 'neg'}" x="${(x >= 0 ? mid : mid - bw).toFixed(1)}" y="1" width="${bw.toFixed(1)}" height="${h - 2}" rx="2"/></svg>`;
}
export function screenCell(c, v) {
  if (v === null || v === undefined) return 'n/a';
  if (c.unit === '$' && Math.abs(v) >= 1e6) return `$${compact(v)}`;
  const n = num(v, c.decimals ?? 2);
  return c.unit === '%' ? `${n}%` : c.unit === 'x' ? `${n}×` : c.unit === '$' ? `$${n}` : n;
}
const buildBar = (b) => (b && b.total ? html`<div class="build-bar" role="progressbar" aria-valuemin="0" aria-valuemax="${b.total}" aria-valuenow="${b.done}" aria-label="Building the ranking"><span style="width:${Math.round((b.done / b.total) * 100)}%"></span></div><p class="asof">${b.done} of ${b.total} symbols screened.</p>` : '');

/** A result row's next steps: its chart, and following it. */
const rowActs = (sym) => html`<td class="sc-acts"><a class="icon-btn" href="${hrefFor('chart', sym)}" aria-label="${sym} chart" title="Chart">${icon('markets')}</a>${watchButton(sym, { compact: true })}</td>`;
/** Comparing the names a result leads with, in one step. */
const compareTop = (rows) => (rows || []).length >= 2 ? html`<p class="cluster scan-next"><a class="btn btn-sm" href="#/compare?t=${encodeURIComponent(rows.slice(0, 4).map((r) => r.symbol).join(','))}">Compare the first ${Math.min(4, rows.length)}</a></p>` : '';
function screenTable(res, emptyText) {
  const cols = res.columns || [];
  if (!(res.rows || []).length) return html`<p class="quiet">${emptyText}</p>`;
  return html`<div class="tscroll"><table class="t sc-t"><thead><tr><th scope="col">Symbol</th>${cols.map((c) => html`<th scope="col">${c.label}</th>`)}<th scope="col"><span class="sr">Next</span></th></tr></thead><tbody>${res.rows.map((r) => html`<tr><th scope="row"><a href="${hrefFor('overview', r.symbol)}">${r.symbol}</a></th>${cols.map((c) => html`<td>${screenCell(c, r[c.id])}</td>`)}${rowActs(r.symbol)}</tr>`)}</tbody></table></div>${compareTop(res.rows)}`;
}

/* ---------------- Find stocks: describe, review, run (Handoff 8) ---------------- */
const wideScreen = () => { try { return matchMedia('(min-width: 641px)').matches; } catch (e) { return true; } };
const PAGE = 25;
const specOf = (pr) => ({ filters: (pr.filters || []).map(({ field, min, max, min_exclusive, max_exclusive, min_peer, max_peer }) => Object.fromEntries(Object.entries({ field, min, max, min_exclusive, max_exclusive, min_peer, max_peer }).filter(([, v]) => v !== undefined && v !== null && v !== false))), states: (pr.states || []).map((x) => x.id || x), sort: pr.sort || 'score', direction: pr.direction || 'desc' });
const fieldOf = (id) => ((S.fields || {}).fields || []).find((f) => f.id === id) || {};
function amount(fd, v) { const n = num(v, fd.decimals ?? 2).replace(/\.0+$|(\.\d*?)0+$/, '$1'); return fd.unit === '$' ? `$${n}` : fd.unit === '%' ? `${n}%` : fd.unit === 'x' ? `${n}×` : n; }
/** One filter in plain English, as the server's screener.plain says it, so an edit reads the same as the reading. */
export function plainOf(f, fd = fieldOf(f.field), periods = (S.fields || {}).period_words || {}) {
  const label = fd.label || f.field; let said;
  if (f.min_peer || f.max_peer) said = `${label} ${f.min_peer ? 'above' : 'below'} the universe's ${f.min_peer || f.max_peer}`;
  else if (f.min != null && f.max != null) said = `${label} between ${amount(fd, f.min)} and ${amount(fd, f.max)}`;
  else if (f.min != null) said = `${label} ${f.min_exclusive ? 'above' : 'at least'} ${amount(fd, f.min)}`;
  else if (f.max != null) said = `${label} ${f.max_exclusive ? 'below' : 'at most'} ${amount(fd, f.max)}`;
  else said = `${label}: no bound yet`;
  return periods[f.field] ? `${said} (${periods[f.field]})` : said;
}
function ask() {
  const recent = readKey(RECENT_KEY, []);
  return html`<section class="section first" aria-labelledby="fs-h"><h2 class="t-h2" id="fs-h">Find stocks</h2>
    <form class="ask-form" data-v2-ask><label class="sr" for="sc-ask">Describe the stocks you want</label><textarea id="sc-ask" name="text" maxlength="300" rows="2" placeholder="Positive revenue growth and below-average debt ratios">${S.askText || ''}</textarea>
      <div class="cluster"><button type="submit" class="btn btn-primary" ${S.reading ? 'disabled' : ''}>${S.reading ? 'Reading…' : 'Read my request'}</button>${miloButton(S.run && S.run.rows ? 'Ask Milo about the results' : 'Ask Milo to help phrase it', { ask: S.run && S.run.rows ? `I screened for "${S.askText}". ${S.run.matched} of ${S.run.considered} ranked names matched: ${(S.run.rows || []).slice(0, 15).map((x) => x.symbol).join(', ')}. Which fit best, and what would make each stop fitting?` : 'Help me turn my idea into a stock screen.', context: 'Discover, Scan' })}</div></form>
    <p class="asof">Fixed rules read most requests at no cost; words they cannot read use one Milo question, once. Nothing runs until you have seen the filters and pressed Run.</p>
    <details class="sc-ex" ${wideScreen() ? 'open' : ''}><summary>Examples <span class="t-muted">${EXAMPLES.length}</span></summary>
      <div class="chips chips-scroll" role="group" aria-label="Examples">${EXAMPLES.map((e) => html`<button type="button" class="chip" data-v2-ask-ex="${e}">${e}</button>`)}</div></details>
    ${recent.length ? html`<p class="t-label" style="margin-top:12px">Your recent requests <button type="button" class="textlink" data-v2-ask-clear>Clear</button></p><div class="chips chips-scroll">${recent.map((e) => html`<button type="button" class="chip" data-v2-ask-ex="${e}">${e}</button>`)}</div>` : ''}
    <div aria-live="polite">${S.propErr ? html`<div class="state err" role="alert"><p class="t-h3">The request was not read</p><p>${api.explain(S.propErr, 'Reading the request')}</p></div>` : S.prop ? html`${review()}${resultView()}` : ''}</div>
  </section>`;
}
/** The filters as read, before anything runs: each in plain English, each editable or removable. */
function review() {
  const pr = S.prop, n = pr.filters.length + pr.states.length, fields = (S.fields || {}).fields || [];
  const used = new Set(pr.filters.map((x) => x.field));
  return html`<div class="ds-review" aria-labelledby="ds-rh"><h3 id="ds-rh">${n ? 'The filters, before anything runs' : 'Nothing to screen on yet'}</h3>
    <p class="asof">${pr.read_by === 'saved' ? 'A saved screen, as you saved it.' : pr.read_by === 'pulse' ? 'Read by Milo (one question, kept so it is never paid for twice).' : 'Read by Optic\'s fixed rules, at no cost.'}${pr.note ? ` ${clean(pr.note)}` : ''}</p>
    ${(pr.unmapped || []).map((u) => html`<p class="ds-unmapped" role="note">Couldn't map “${u}” to a filter, so it was left out. Nothing was put in its place.</p>`)}
    ${n ? html`<ul class="ds-filters">${pr.filters.map((f, i) => { const fd = fieldOf(f.field), peer = f.min_peer || f.max_peer; return html`<li class="ds-f">
        <p class="ds-said">${plainOf(f, fd)}</p>
        <div class="ds-edit">${peer ? html`<label class="select"><span class="sr">How ${fd.label || f.field} is compared</span><select data-ds-peer="${i}"><option value="median" ${peer === 'median' ? 'selected' : ''}>Against the universe's median</option><option value="mean" ${peer === 'mean' ? 'selected' : ''}>Against the universe's mean</option><option value="value">Against a number</option></select></label>`
          : html`<label class="field field-xs"><span class="sr">${fd.label || f.field}, from</span><input data-ds-min="${i}" inputmode="decimal" placeholder="min" value="${f.min ?? ''}"></label><span>to</span><label class="field field-xs"><span class="sr">${fd.label || f.field}, to</span><input data-ds-max="${i}" inputmode="decimal" placeholder="max" value="${f.max ?? ''}"></label><span class="t-muted">${fd.unit === 'x' ? '×' : fd.unit || ''}</span>`}
          <button type="button" class="icon-btn" data-ds-del="${i}" aria-label="${`Remove the ${fd.label || f.field} filter`}" title="Remove">${icon('close')}</button></div></li>`; })}
      ${pr.states.map((st, k) => html`<li class="ds-f"><p class="ds-said">${st.label}</p><div class="ds-edit"><button type="button" class="icon-btn" data-ds-sdel="${k}" aria-label="${`Remove “${st.label}”`}" title="Remove">${icon('close')}</button></div></li>`)}</ul>`
      : html`<p>Nothing in that could be read as a filter. Build one yourself, or describe it another way.</p>`}
    <div class="cluster">${n ? html`<button type="button" class="btn btn-primary" data-ds-run ${S.running ? 'disabled' : ''}>${S.running ? 'Screening…' : 'Run screen'}</button>` : ''}
      ${fields.length && pr.filters.length < 8 ? html`<label class="select"><span class="sr">Add a filter</span><select data-ds-add><option value="">Add a filter…</option>${fields.filter((f) => !used.has(f.id)).map((f) => html`<option value="${f.id}">${f.label}</option>`)}</select></label>` : ''}
      <button type="button" class="btn btn-quiet btn-sm" data-ds-build>Open in Build a screen</button></div></div>`;
}
const fmtDay = (d) => { const t = d ? new Date(`${d}T12:00:00Z`) : null; return t && Number.isFinite(t.getTime()) ? t.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }) : ''; };
/** What the screen ran on, said once above its list: the filters, the universe, the dates, the sources, the fingerprint. */
function pinned(r) {
  const fund = (r.as_of || {}).fundamentals, p = (fund || {}).periods || {};
  const used = new Set((r.filters || []).map((f) => f.field));
  const asOf = [r.as_of && r.as_of.bars_through ? `Daily bars through ${fmtDay(r.as_of.bars_through)}` : `Ranking built ${num(r.ranking_age_hours, 1)} hours ago`];
  if (fund && used.has('revenue_growth')) asOf.push(`revenue growth: fiscal years that fall mostly in ${p.revenue_year}, against those in ${p.revenue_prior}`);
  if (fund && used.has('debt_ratio')) asOf.push(`debt ratio: balance sheets at ${fmtDay(p.balance_end)}, or the nearest quarter-end each company reports`);
  const unmeasured = (r.funnel || []).filter((x) => x.unmeasured && fieldOf(x.field).family === 'fundamental');
  return html`<dl class="ds-pin">
      <div><dt>Filters</dt><dd><ul class="plain">${(r.filters_said || []).map((x) => html`<li>${x}</li>`)}</ul></dd></div>
      <div><dt>Universe</dt><dd>NASDAQ-listed stocks: ${r.prefiltered ?? r.considered} of ${r.universe} pass the price and liquidity gates (at least $${num((r.gates || {}).min_price, 0)}, and $${compact((r.gates || {}).min_dollar_volume)} a day).</dd></div>
      <div><dt>As of</dt><dd>${capFirst(asOf.join('; '))}.${r.stale ? ' The ranking is stale.' : ''}</dd></div>
      ${(r.peers || []).length ? html`<div><dt>Compared with</dt><dd>${r.peers.map((x) => (x.value === null ? `${x.label}: no stock in the universe reports it, so nothing passes` : `${x.label} ${x.side === 'max' ? 'below' : 'above'} ${x.value}%, the ${x.basis} of the ${x.of} stocks in the universe that report it`)).join('; ')}.</dd></div>` : ''}
      <div><dt>Sources</dt><dd>Prices: ${r.sources.price}.${r.sources.fundamental ? ` Revenue and balance sheets: ${r.sources.fundamental}.` : ''}</dd></div>
      <div><dt>Screen</dt><dd>${r.fingerprint}: the same filters on the same data give the same list.</dd></div></dl>
    ${unmeasured.map((x) => html`<p class="ds-note">${x.unmeasured} stocks in the universe have no ${x.label.toLowerCase()} in SEC's US-GAAP filings (most file in IFRS or are funds), so this filter cannot pass them.</p>`)}
    ${(r.considered || 0) < 30 ? html`<p class="stale">A small universe: only ${r.considered} stocks were screened.</p>` : ''}`;
}
function resultView() {
  const r = S.run;
  if (!r) return '';
  if (r.error) return failed('The screen', r.error, { retry: 'describe' });
  if (r.available === false) return html`<div class="state" role="status"><p>${clean(r.reason || '')}</p>${buildBar(r.building)}${r.building ? html`<button type="button" class="btn btn-sm" data-ds-stop>Stop waiting</button>` : r.retry ? html`<button type="button" class="btn btn-sm" data-ds-run>Try again</button>` : ''}</div>`;
  const shown = (r.rows || []).slice(0, S.shown || PAGE), b = r.binding;
  return html`<section class="ds-result" aria-labelledby="ds-mh">
    ${S.runKey && S.runKey !== lib.screenKey(specOf(S.prop)) ? html`<p class="stale">These matches are for the filters as they were when you ran the screen. Run it again for the ones above.</p>` : ''}
    <div class="section-head"><h3 id="ds-mh">${r.matched} of ${r.considered} match</h3><div class="cluster">${saveButton('screen', `screen:${lib.screenKey(specOf(S.prop))}`, { label: 'Save screen' })}</div></div>
    ${pinned(r)}
    <p class="ds-disc">Screening is not investment advice: being on a list is not a recommendation. Check the figures before acting on them.</p>
    ${r.matched ? html`${screenTable(Object.assign({}, r, { rows: shown }), '')}
      ${(r.rows || []).length > shown.length ? html`<p class="cluster"><button type="button" class="btn btn-sm" data-ds-more>Show ${Math.min(PAGE, r.rows.length - shown.length)} more</button><span class="t-muted">${shown.length} of ${r.rows.length} shown</span></p>` : ''}
      ${r.matched > (r.rows || []).length ? html`<p class="asof">These are the first ${(r.rows || []).length} of ${r.matched}, in the order shown. Narrow the filters to see the rest.</p>` : ''}`
      : html`<div class="state" role="status"><p><b>Nothing matched.</b>${b ? ` The filter that left nothing: ${b.said} (${b.reached} stocks reached it).` : ''}</p>
        ${b && b.suggest ? html`<p>Loosen it to “${b.suggest_said}”? That would let ${b.keeps} of those ${b.reached} through this filter. <button type="button" class="btn btn-sm" data-ds-loosen>Use this bound</button></p><p class="asof">It changes the filter above; nothing runs until you press Run.</p>` : b && b.why ? html`<p class="t-muted">${capFirst(b.why)}.</p>` : ''}</div>`}
  </section>`;
}
/* ---------------- named scans ---------------- */
function named() {
  const g = (S.groups || {}).groups || [], sc = S.scans || {};
  const active = g.find((x) => (x.scans || []).some((s) => s.id === S.scanId)) || g[0];
  const r = S.result;
  return html`<p class="section-sub">${sc.considered ? `${sc.considered} of ${sc.universe_size} symbols pass the price and volume filters. Each scan below is already computed over them.` : 'The ranking is still loading. Each scan fills when it finishes; this page checks every 5 seconds.'}</p>
    <div class="chips" role="group" aria-label="Scan groups">${g.map((x) => html`<button type="button" class="chip" data-v2-scan-group="${x.id}" aria-pressed="${active && active.id === x.id}">${x.name} <span class="t-muted">${x.count}</span></button>`)}</div>
    ${active ? html`<p class="t-muted">${clean(active.blurb || '')}</p><div class="seg scan-tabs" role="group" aria-label="Scans">${active.scans.map((s) => html`<button type="button" data-v2-scan="${s.id}" aria-pressed="${S.scanId === s.id}" title="${s.looks_for || ''}">${s.name}</button>`)}</div>` : ''}
    <div class="scan-result">${!r ? skeleton('rows', 6, 'Running the scan') : r.error ? failed('This scan', r.error, { retry: 'scan' }) : r.available === false ? html`<p>${clean(r.reason || 'This scan is unavailable.')}</p>${buildBar(r.building)}` : html`
      <p>${clean(r.looks_for || '')}</p>${r.stale ? html`<p class="stale">The ranking is ${num(r.age_hours, 0)} hours old, so these results describe an earlier session.</p>` : ''}
      <p class="asof">${r.matched} matched, showing the first ${r.shown}. Ranking ${num(r.age_hours, 1)} hours old.</p>
      ${(r.rows || []).length ? html`<p class="asof">Ranked by ${((r.columns || []).find((c) => c.key === (r.ranked_by || {}).key) || {}).label || 'score'}, ${(r.ranked_by || {}).order === 'asc' ? 'lowest' : 'highest'} first.</p><div class="tscroll"><table class="t sc-t"><thead><tr><th scope="col">Symbol</th><th scope="col">Price</th>${(r.columns || []).map((c) => html`<th scope="col" aria-sort="${(r.ranked_by || {}).key === c.key ? ((r.ranked_by || {}).order === 'asc' ? 'ascending' : 'descending') : 'none'}">${c.label}${(r.ranked_by || {}).key === c.key ? ((r.ranked_by || {}).order === 'asc' ? ' ▲' : ' ▼') : ''}</th>`)}<th scope="col"><span class="sr">Next</span></th></tr></thead>
        <tbody>${((bars) => r.rows.map((x) => html`<tr><th scope="row"><a href="${hrefFor('overview', x.symbol)}">${x.symbol}</a></th><td>${num(x.price)}</td>${(r.columns || []).map((c) => html`<td${bars && c.key === bars.key ? html` class="sc-barred"` : ''}>${bars && c.key === bars.key ? raw(cellBar(x[c.key], bars)) : ''}${scanCell(c.kind, x[c.key])}</td>`)}${rowActs(x.symbol)}</tr>`))(rankBars(r))}</tbody></table></div>${compareTop(r.rows)}${readings(r)}`
      : html`<p class="quiet">No symbols match this scan right now: it ran over ${r.considered || 'the'} ranked names and none clears its conditions. That is a result, not a failure.</p>`}
      ${r.blind_spot ? html`<p class="stale">What this scan cannot see: ${clean(r.blind_spot)}</p>` : ''}<p class="asof">${clean(r.method || '')}</p>`}</div>
    ${(S.groups || {}).note ? html`<p class="asof">${clean(S.groups.note)}</p>` : ''}`;
}
function readings(r) {
  const rows = r.rows || [];
  const up = rows.filter((x) => (x.roc20 || 0) > 0).length, vol = rows.filter((x) => (x.volume_expansion || 0) >= 1.5).length;
  const roc = rows.map((x) => x.roc20).filter((v) => typeof v === 'number');
  return html`<h3>What this screen returned</h3><ul class="plain">${roc.length ? html`<li>${up} of ${rows.length} are up over 20 sessions (${signed(Math.min(...roc), 1)} to ${signed(Math.max(...roc), 1)}).</li>` : ''}${rows.some((x) => 'volume_expansion' in x) ? html`<li>${vol} trade at least 1.5 times their usual volume.</li>` : ''}${r.matched > r.shown ? html`<li>These are the first ${r.shown} of ${r.matched}.</li>` : ''}</ul>`;
}

/* ---------------- build a screen ---------------- */
function builder() {
  const f = S.fields, sp = S.spec;
  if (f === undefined) return skeleton('lines', 3, 'Loading the filters');
  if (!f) return empty('Could not load the filter list', '');
  const used = new Set(sp.filters.map((x) => x.field));
  const max = f.max_filters || 8;
  const res = S.screen;
  const active = sp.filters.filter((x) => x.min != null || x.max != null).length + sp.states.length;
  return html`<p class="section-sub">Filter the ranked universe with up to ${max} conditions. Leave the minimum or maximum empty for a one-sided bound.</p>
    <form class="screen-form" data-v2-screen>
      <p class="flt-count" aria-live="polite"><b>${active ? `${active} condition${active === 1 ? '' : 's'} on` : 'No conditions on'}</b>${active || sp.filters.length ? html` <button type="button" class="textlink" data-v2-flt-reset>Reset all</button>` : ''}</p>
      ${sp.filters.length ? sp.filters.map((x, i) => { const fd = f.fields.find((y) => y.id === x.field) || {}; return html`<div class="flt"><label class="select"><span class="sr">Field</span><select data-v2-flt-field="${i}">${f.fields.map((y) => html`<option value="${y.id}" ${y.id === x.field ? 'selected' : ''}>${y.label}</option>`)}</select></label>
        <label class="field field-xs"><span class="sr">Minimum</span><input data-v2-flt-min="${i}" inputmode="decimal" placeholder="min" value="${x.min ?? ''}"></label><span>to</span>
        <label class="field field-xs"><span class="sr">Maximum</span><input data-v2-flt-max="${i}" inputmode="decimal" placeholder="max" value="${x.max ?? ''}"></label><span class="t-muted">${fd.unit === 'x' ? '×' : fd.unit || ''}</span>
        <button type="button" class="icon-btn" data-v2-flt-del="${i}" aria-label="Remove the ${fd.label || ''} filter">${icon('close')}</button><small class="t-muted flt-help">${clean(fd.help || '')}</small></div>`; })
      : html`<p class="quiet">No filters yet. Add one, or run it as it is to rank the whole liquid universe by trend score.</p>`}
      <div class="cluster"><button type="button" class="btn btn-sm" data-v2-flt-add ${sp.filters.length >= max ? 'disabled' : ''}>Add filter</button></div>
      <fieldset class="states"><legend class="t-label">Also require</legend>${f.states.map((s) => html`<label class="check"><input type="checkbox" data-v2-state="${s.id}" ${sp.states.includes(s.id) ? 'checked' : ''}> <span>${s.label}</span></label>`)}</fieldset>
      <div class="cluster"><label class="select"><span class="t-label">Sort by</span><select data-v2-screen-sort>${f.fields.map((y) => html`<option value="${y.id}" ${sp.sort === y.id ? 'selected' : ''}>${y.label}</option>`)}</select></label>
        <label class="select"><span class="t-label">Direction</span><select data-v2-screen-dir><option value="desc" ${sp.direction === 'desc' ? 'selected' : ''}>Highest first</option><option value="asc" ${sp.direction === 'asc' ? 'selected' : ''}>Lowest first</option></select></label>
        <button type="submit" class="btn btn-primary" ${S.screening ? 'disabled' : ''}>${S.screening ? 'Screening…' : 'Run screen'}</button></div>
      <p class="asof">What this screen cannot see: ${clean(f.blind_spot || '')}</p></form>
    <div aria-live="polite">${!res ? '' : res.error ? failed('The screen', res.error) : res.available === false ? html`<p>${clean(res.reason || '')}</p>${buildBar(res.building)}` : html`
      ${res.spec_key && res.spec_key !== specKey(sp) ? html`<p class="stale">These matches are for the conditions as they were when you ran the screen. Run it again for the ones above.</p>` : ''}
      <h3>Matches</h3><p class="asof">${res.matched} of ${res.considered} ranked names, from a ${res.universe}-symbol universe, showing the first ${(res.rows || []).length}. Ranking ${num(res.ranking_age_hours, 1)} hours old.${res.stale ? ' The ranking is stale.' : ''} The universe drops anything under $${num((res.gates || {}).min_price, 0)} or under $${compact((res.gates || {}).min_dollar_volume)} a day.</p>
      ${(res.funnel || []).length ? html`<p class="funnel">${res.funnel.map((x) => html`<span>${x.label}: ${x.before} → ${x.after}</span>`)}</p>` : ''}
      ${(res.ignored || []).length ? html`<p class="stale">Not applied: ${res.ignored.map((x) => `${x.label || x.field} (${x.reason})`).join(', ')}.</p>` : ''}
      ${screenTable(res, 'Nothing clears every condition. That is a result rather than a failure: the funnel says which bound emptied it.')}`}</div>`;
}

/* ---------------- evaluation ---------------- */
function evaluation() {
  const e = S.evalD;
  return html`<section class="section" aria-labelledby="ev-h"><div class="section-head"><div><h2 class="t-h2" id="ev-h">Does the score work?</h2><p class="section-sub">Whether higher-scored names went on to do better, replayed on past data.</p></div>${miloButton('Ask Milo about this test', { ask: 'How should I read the test of whether Optic\'s score works?', context: 'Discover, Scan' })}</div>
    ${e === undefined ? html`<button type="button" class="btn btn-sm" data-v2-eval>Run the test</button><p class="asof">The first run takes longer: it replays the score over 220 names.</p>` : e === 'loading' ? skeleton('lines', 4, 'Replaying the score') : !e || !e.available ? html`<p>${clean((e || {}).reason || 'The test did not run.')}</p>` : html`
      <p class="${(e.comparison || []).some((c) => c.beats_single_factor) ? '' : 'stale'}"><b>Result.</b> ${clean(e.verdict || '')}</p>
      <div class="tscroll"><table class="t"><thead><tr><th>Horizon</th><th>Composite</th><th>Random</th><th>3-month return alone</th><th>Against one factor</th></tr></thead><tbody>${(e.comparison || []).map((c) => html`<tr><td>${c.horizon_sessions} sessions</td><td>${num(c.composite_ic, 3)}</td><td>${num(c.random_ic, 3)}</td><td>${num(c.single_factor_ic, 3)}</td><td>${c.beats_single_factor ? 'Beats it' : 'Loses'}</td></tr>`)}</tbody></table></div>
      <p class="asof">${clean(e.control_note || '')}</p>
      ${(e.horizons || []).map((h) => html`<details class="more-inline"><summary>${h.horizon_sessions} sessions, by score bucket</summary><div class="tscroll"><table class="t"><thead><tr><th>Bucket</th><th>n</th><th>Mean excess</th><th>Hit rate</th><th>95% interval</th></tr></thead><tbody>${(h.buckets || []).map((b) => html`<tr><td>${b.bucket}</td><td>${b.n}</td><td>${signed(b.mean_pct, 2)}</td><td>${num(b.hit_rate_pct, 0)}%</td><td>${Array.isArray(b.ci95_pct) ? `${signed(b.ci95_pct[0], 2)} to ${signed(b.ci95_pct[1], 2)}` : ''}</td></tr>`)}</tbody></table></div></details>`)}
      <p>${clean(e.interpretation || '')}</p>${(e.biases || []).length ? html`<h3>What this cannot fix</h3><ul class="plain">${e.biases.map((b) => html`<li>${clean(b)}</li>`)}</ul>` : ''}`}</section>`;
}

/* ---------------- page ---------------- */
function paint() {
  if (!live) return;
  const y = window.scrollY;
  draw(mainEl, html`<header class="page-head">${sectionHead('discover', 'scan')}</header>
    ${ask()}
    <section class="section" aria-labelledby="sc-h"><div class="section-head"><h2 class="t-h2" id="sc-h">${S.mode === 'build' ? 'Build a screen' : S.mode === 'shortlist' ? 'Nightly shortlist' : 'Scanners'}</h2>
      <div class="seg sc-modes" role="group" aria-label="Mode"><button type="button" data-v2-scan-mode="named" aria-pressed="${S.mode === 'named'}">Named scans</button><button type="button" data-v2-scan-mode="shortlist" aria-pressed="${S.mode === 'shortlist'}">Shortlist</button><button type="button" data-v2-scan-mode="build" aria-pressed="${S.mode === 'build'}">Build a screen</button></div></div>
      ${S.mode === 'build' ? builder() : S.mode === 'shortlist' ? shortlistBody(S) : S.scans === undefined ? skeleton('rows', 4, 'Loading the scanner catalogue') : S.scansErr ? failed('The scanner catalogue', S.scansErr, { retry: 'catalogue' }) : named()}</section>
    ${evaluation()}`);
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

async function runScan(id, quiet) {
  // a saved screen keeps the address, so a reload or Back reopens it rather than the named scan under it
  S.scanId = id; if (!S.savedId) remember(`id=${encodeURIComponent(id)}`); if (!quiet) { S.result = null; paint(); }
  try { const r = await api.get(`/api/scanners/${encodeURIComponent(id)}?limit=25`, { ttl: quiet ? 0 : 60000, force: !!quiet }); if (S.scanId !== id || !live) return; S.result = r; }
  catch (e) { if (S.scanId === id) S.result = { error: e }; }
  paint(); whenBuilt(S.result && S.result.building, () => runScan(id, true));
}
function whenBuilt(building, again) { clearTimeout(poll); if (building && live) poll = setTimeout(again, 5000); }
async function runScreen(again) {
  if (S.screening && !again) return;   // one screen at a time
  const bad = S.spec.filters.some((x) => Number.isNaN(x.min) || Number.isNaN(x.max));
  if (bad) { toast('One of the bounds is not a number, so the screen did not run.'); return; }
  S.screening = true; paint();
  const key = specKey(S.spec);
  try { S.screen = Object.assign(await api.post('/api/screener', S.spec, { timeout: 60000 }), { spec_key: key }); if (!S.screen.building && S.screen.available !== false) SCREENED.set(key, S.screen); } catch (e) { S.screen = { error: e }; }
  S.screening = false; remember('mode=build'); paint(); whenBuilt(S.screen && S.screen.building, () => runScreen(true));
}
async function readRequest(text) {
  text = String(text || '').trim();
  if (S.reading) return;   // one request at a time: a second click does not ask twice
  // nothing typed: the box is focused and the reader told what goes in it (investor audit, 2026-10-27)
  if (!text) { const box = document.getElementById('sc-ask'); if (box) box.focus(); toast('Describe the stocks you want first, in a few words.'); return; }
  S.askText = text; S.reading = true; S.propErr = null; S.run = null; S.savedId = null; paint();
  try {
    if (S.fields === undefined) await loadFields(true);
    const r = await api.post('/api/screener/read', { text }, { timeout: 60000 });
    S.prop = { text: r.text, read_by: r.read_by, note: r.note, unmapped: r.unmapped || [], filters: r.filters || [], states: r.states || [], sort: r.sort, direction: r.direction };
    ASKED.set(text, S.prop);
    writeKey(RECENT_KEY, [text, ...readKey(RECENT_KEY, []).filter((x) => x.toLowerCase() !== text.toLowerCase())].slice(0, 6));
  } catch (e) { S.propErr = e; S.prop = null; }
  S.reading = false; remember(`q=${encodeURIComponent(text)}`); paint();
  const h = mainEl && mainEl.querySelector('#ds-rh'); if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: false }); }
}
async function runDescribed(again) {
  if (!S.prop || (S.running && !again)) return;
  const sp = specOf(S.prop);
  if (sp.filters.some((x) => Number.isNaN(x.min) || Number.isNaN(x.max))) { toast('One of the bounds is not a number, so the screen did not run.'); return; }
  S.running = true; if (!again) { S.run = null; S.shown = PAGE; } paint();
  try { S.run = await api.post('/api/screener', Object.assign({}, sp, { limit: 200, text: S.prop.text || '' }), { timeout: 90000 }); S.runKey = lib.screenKey(sp); }
  catch (e) { S.run = { error: e }; }
  S.running = false; paint();
  // still being built (the ranking, or SEC's figures for the universe): asked again every 5 seconds, until Stop waiting
  whenBuilt(S.run && S.run.building && !S.stopped, () => runDescribed(true));
  if (!again) { const h = mainEl && mainEl.querySelector('#ds-mh'); if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: false }); } }
}
// a saved screen (Saved research, Handoff 8): its filters as saved, run at once (a screen costs nothing to run)
async function openSaved(id) {
  try {
    const r = await lib.get(id), sc = (r.item || {}).screen;
    if (!sc) throw new Error('This saved item is not a screen.');
    S.savedId = id;
    if (S.fields === undefined) await loadFields(true);
    S.askText = sc.text || ''; S.prop = { text: sc.text || '', read_by: 'saved', unmapped: [], filters: sc.filters || [], states: (sc.states || []).map((k) => ({ id: k, label: ((S.fields || {}).states || []).find((x) => x.id === k)?.label || k })), sort: sc.sort, direction: sc.direction };
    paint(); runDescribed();
  } catch (e) { S.propErr = e; paint(); }
}

export async function render(main, route) {
  live = true; mainEl = main;
  const prm = route.params || {};
  S = { mode: prm.mode === 'build' ? 'build' : prm.mode === 'shortlist' ? 'shortlist' : 'named', scanId: prm.id || 'momentum', spec: Object.assign(blankSpec(), readKey(SCREEN_KEY, {})) };
  if (S.mode === 'build') { loadFields(); const kept = SCREENED.get(specKey(S.spec)); if (kept) S.screen = kept; }
  document.title = 'Scan, Optic';
  provideContext(() => ({ view: 'scan', scan: S.result && S.result.rows ? { id: S.scanId, name: S.result.name, rows: S.result.rows.slice(0, 15) } : null }));
  paint(); wire(main);
  if (S.mode === 'shortlist') loadShortlist();
  // #/scan?q=… from Milo's "Find stocks" card, which said it may use a question, runs that request, once; back on
  // this page from a result, the answer already given is shown again. Any other link with ?q= (a shared one) puts the
  // words in the box and waits for the press, so opening a link never spends a reader's Milo message (Phase 02).
  const q = String(prm.q || '').trim().slice(0, 300);
  if (prm.saved) openSaved(String(prm.saved));
  else if (q && ASKED.has(q)) { S.askText = q; S.prop = ASKED.get(q); paint(); } else if (q && pressedInMilo(q)) readRequest(q); else if (q) { S.askText = q; paint(); }
  // what Save keeps for a screen: the request in words and the filters exactly as confirmed (Handoff 8)
  provideSave('screen', () => (S.prop ? { kind: 'screen', tickers: [], screen: Object.assign(specOf(S.prop), { text: S.prop.text || '' }), summary: { text: S.prop.text || '', said: [...S.prop.filters.map((f) => plainOf(f)), ...S.prop.states.map((x) => x.label)] }, name: `${S.prop.text ? `${S.prop.text.slice(0, 60)}` : 'Screen'}, ${lib.dayText(Date.now())}` } : { blocked: 'Read a request first: there is no screen to save yet.' }));
  try { [S.scans, S.groups] = await Promise.all([api.get('/api/scanners', { ttl: 120000 }), api.get('/api/scanners/groups', { ttl: 600000 }).catch(() => null)]); if (!S.groups && S.scans) S.groups = { groups: [{ id: 'all', name: 'Screens', count: S.scans.scans.length, scans: S.scans.scans }] }; }
  catch (e) { S.scansErr = e; S.scans = null; }
  paint();
  if (S.scans && S.mode === 'named') runScan(S.scanId);
}
export function dispose() { live = false; clearTimeout(poll); }
export const retry = { scan: () => runScan(S.scanId), catalogue: (m, r) => render(m, r), shortlist: () => loadShortlist(), describe: () => runDescribed() };
async function loadShortlist() {
  S.shortlist = undefined; paint(); remember('mode=shortlist');
  try { S.shortlist = await api.get('/api/shortlist', { ttl: 300000, timeout: 120000 }); } catch (e) { S.shortlist = { error: e }; }
  paint();
}

function saveSpec() {
  writeKey(SCREEN_KEY, S.spec);
  // the count of conditions on follows each keystroke, not only the next redraw
  const b = mainEl && $('.flt-count b', mainEl);
  if (b) { const n = S.spec.filters.filter((x) => x.min != null || x.max != null).length + S.spec.states.length; b.textContent = n ? `${n} condition${n === 1 ? '' : 's'} on` : 'No conditions on'; }
}
function wire(main) {
  // once per page view: Try again draws into the same view, and wiring it again doubled every press (BUG-037)
  if (main.__v2Wired) return;
  main.__v2Wired = true;
  main.addEventListener('submit', (e) => {
    if (e.target.closest('[data-v2-ask]')) { e.preventDefault(); readRequest(e.target.text.value); return; }
    if (e.target.closest('[data-v2-screen]')) { e.preventDefault(); runScreen(); }
  });
  main.addEventListener('keydown', (e) => { if (e.target.id === 'sc-ask' && e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); readRequest(e.target.value); } });
  main.addEventListener('input', (e) => {
    const t = e.target; let i;
    const val = (v) => { const s = String(v).trim().replace(/,/g, ''); if (!s) return null; const n = Number(s); return Number.isFinite(n) ? n : NaN; };
    if ((i = t.dataset.v2FltMin) !== undefined) { S.spec.filters[i].min = val(t.value); t.closest('.field').classList.toggle('bad', Number.isNaN(S.spec.filters[i].min)); saveSpec(); }
    else if ((i = t.dataset.v2FltMax) !== undefined) { S.spec.filters[i].max = val(t.value); t.closest('.field').classList.toggle('bad', Number.isNaN(S.spec.filters[i].max)); saveSpec(); }
    else if (t.id === 'sc-ask') S.askText = t.value;
    else if ((i = t.dataset.dsMin) !== undefined || (i = t.dataset.dsMax) !== undefined) {
      const f = S.prop.filters[i], side = t.dataset.dsMin !== undefined ? 'min' : 'max';
      f[side] = val(t.value); delete f[`${side}_exclusive`];   // a bound the reader typed is "at least" or "at most"
      t.closest('.field').classList.toggle('bad', Number.isNaN(f[side]));
      const said = t.closest('.ds-f') && t.closest('.ds-f').querySelector('.ds-said'); if (said) said.textContent = plainOf(f);
    }
  });
  main.addEventListener('change', (e) => {
    const t = e.target;
    if (t.dataset.v2FltField !== undefined) { const f = S.spec.filters[t.dataset.v2FltField]; f.field = t.value; f.min = null; f.max = null; saveSpec(); paint(); return; }
    if (t.dataset.dsPeer !== undefined) {
      const f = S.prop.filters[t.dataset.dsPeer], side = f.min_peer ? 'min' : 'max';
      if (t.value === 'value') { delete f.min_peer; delete f.max_peer; f[side] = null; } else f[`${side}_peer`] = t.value;
      paint(); return;
    }
    if (t.dataset.dsAdd !== undefined && t.value) { S.prop.filters.push({ field: t.value, min: null, max: null }); paint(); const ins = mainEl.querySelectorAll('[data-ds-min]'); if (ins.length) ins[ins.length - 1].focus(); return; }
    if (t.dataset.v2State !== undefined) { const id = t.dataset.v2State; S.spec.states = t.checked ? [...new Set([...S.spec.states, id])] : S.spec.states.filter((x) => x !== id); saveSpec(); return; }
    if (t.matches('[data-v2-screen-sort]')) { S.spec.sort = t.value; saveSpec(); return; }
    if (t.matches('[data-v2-screen-dir]')) { S.spec.direction = t.value; saveSpec(); }
  });
  main.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-ask-ex]'))) { readRequest(b.dataset.v2AskEx); return; }
    if (t('[data-ds-run]')) { S.stopped = false; runDescribed(); return; }
    if (t('[data-ds-stop]')) { S.stopped = true; clearTimeout(poll); S.run = null; S.running = false; paint(); toast('Stopped waiting. Nothing was screened; press Run to try again.'); return; }
    if (t('[data-ds-more]')) { S.shown = (S.shown || PAGE) + PAGE; paint(); return; }
    if ((b = t('[data-ds-del]'))) { S.prop.filters.splice(Number(b.dataset.dsDel), 1); paint(); return; }
    if ((b = t('[data-ds-sdel]'))) { S.prop.states.splice(Number(b.dataset.dsSdel), 1); paint(); return; }
    if (t('[data-ds-loosen]')) {
      const s2 = S.run && S.run.binding && S.run.binding.suggest; if (!s2) return;
      const f = S.prop.filters.find((x) => x.field === s2.field);
      if (f) { delete f.min_peer; delete f.max_peer; delete f.min_exclusive; delete f.max_exclusive; f.min = s2.min; f.max = s2.max; }
      paint(); const r2 = mainEl.querySelector('[data-ds-run]'); if (r2) r2.focus(); toast('The filter is loosened above. Press Run to screen again.'); return;
    }
    if (t('[data-ds-build]')) { S.spec = Object.assign(blankSpec(), S.prop ? specOf(S.prop) : {}); saveSpec(); S.mode = 'build'; if (S.fields === undefined) loadFields(); paint(); const sec = mainEl.querySelector('#sc-h'); if (sec) sec.scrollIntoView({ block: 'start' }); return; }
    if (t('[data-v2-ask-clear]')) { writeKey(RECENT_KEY, null); paint(); return; }
    if ((b = t('[data-v2-scan-mode]'))) {
      S.mode = b.dataset.v2ScanMode;
      if (S.mode === 'build') { if (S.fields === undefined) loadFields(); remember('mode=build'); } else if (S.mode === 'shortlist') { if (S.shortlist === undefined || (S.shortlist && S.shortlist.error)) { loadShortlist(); return; } remember('mode=shortlist'); } else { remember(`id=${encodeURIComponent(S.scanId)}`); if (!S.result) runScan(S.scanId); }
      paint(); return;
    }
    if ((b = t('[data-v2-scan-group]'))) { const g = S.groups.groups.find((x) => x.id === b.dataset.v2ScanGroup); if (g && g.scans[0]) runScan(g.scans[0].id); return; }
    if ((b = t('[data-v2-scan]'))) { runScan(b.dataset.v2Scan); return; }
    if (t('[data-v2-flt-add]')) { const used = new Set(S.spec.filters.map((x) => x.field)); const f = (S.fields.fields || []).find((x) => !used.has(x.id)); if (f) { S.spec.filters.push({ field: f.id, min: null, max: null }); saveSpec(); paint(); } return; }
    if ((b = t('[data-v2-flt-del]'))) { S.spec.filters.splice(Number(b.dataset.v2FltDel), 1); saveSpec(); paint(); return; }
    if (t('[data-v2-flt-reset]')) { S.spec = blankSpec(); saveSpec(); paint(); const a = $('[data-v2-flt-add]', main); if (a) a.focus(); return; }
    if (t('[data-v2-eval]')) { S.evalD = 'loading'; paint(); try { S.evalD = await api.get('/api/evaluate', { ttl: 3600000, timeout: 180000 }); } catch (err) { S.evalD = { available: false, reason: api.explain(err, 'The test') }; } paint(); }
  });
}
async function loadFields(quiet) { try { S.fields = await api.get('/api/screener/fields', { ttl: 3600000 }); } catch (e) { S.fields = null; } if (!quiet) paint(); }
void capFirst;
