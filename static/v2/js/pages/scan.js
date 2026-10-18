// Discover, Scan. Three ways to find stocks over the same ranked universe:
//   Find stocks: a request in plain words (POST /api/screener/ask). A fixed
//     parser reads it for free; only words it cannot read go to Milo, which
//     uses one Milo question from the reader's allowance, and never on load.
//   Named scans: thirteen questions already computed (/api/scanners/{id}).
//   Build a screen: the reader's own bounds (POST /api/screener).
// "Does the score work?" replays the score on history (/api/evaluate) when
// asked. Recent requests and the built screen are kept in the classic keys.
import { $, html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, signed, compact, clean, capFirst } from '../core/format.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { groupTabs } from './tabs.js';

const RECENT_KEY = 'optic.scan.recent.v1', SCREEN_KEY = 'optic.screener.v1';
const EXAMPLES = ['Strong stocks on the 200-day average right now', 'Near 52-week highs on heavy volume', 'Pullbacks in strong uptrends', 'Under $20 and up 20% in the last 3 months', '10% pull back after 20% rally', '2% or more above prev close'];
let S = {}, live = true, mainEl = null, poll = null;

const readKey = (k, d) => { if (!holds(store.state.user)) return d; try { const v = JSON.parse(localStorage.getItem(k) || 'null'); return v == null ? d : v; } catch (e) { return d; } };
const writeKey = (k, v) => { if (!holds(store.state.user)) return; try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private */ } };
const blankSpec = () => ({ filters: [], states: [], sort: 'score', direction: 'desc', limit: 50 });

export function scanCell(kind, v) {
  if (v === null || v === undefined) return 'n/a';
  if (kind === 'text') return clean(String(v));
  if (kind === 'pct') return html`<span class="${v >= 0 ? 'up' : 'down'}">${signed(v, 1)}</span>`;
  if (kind === 'pct_plain') return `${num(v, 2)}%`;
  if (kind === 'mult') return `${num(v, 2)}×`;
  if (kind === 'ratio') return `${num(v * 100, 0)}%`;
  if (kind === 'score') return html`<span class="${v >= 0 ? 'up' : 'down'}">${num(v, 0)}</span>`;
  if (kind === 'usd') return `$${compact(v)}`;
  return num(v, 2);
}
export function screenCell(c, v) {
  if (v === null || v === undefined) return 'n/a';
  if (c.unit === '$' && Math.abs(v) >= 1e6) return `$${compact(v)}`;
  const n = num(v, c.decimals ?? 2);
  return c.unit === '%' ? `${n}%` : c.unit === 'x' ? `${n}×` : c.unit === '$' ? `$${n}` : n;
}
const buildBar = (b) => (b && b.total ? html`<div class="build-bar" role="progressbar" aria-valuemin="0" aria-valuemax="${b.total}" aria-valuenow="${b.done}" aria-label="Building the ranking"><span style="width:${Math.round((b.done / b.total) * 100)}%"></span></div><p class="asof">${b.done} of ${b.total} symbols screened.</p>` : '');

function screenTable(res, emptyText) {
  const cols = res.columns || [];
  if (!(res.rows || []).length) return html`<p class="quiet">${emptyText}</p>`;
  return html`<div class="tscroll"><table class="t"><thead><tr><th>Symbol</th>${cols.map((c) => html`<th>${c.label}</th>`)}</tr></thead><tbody>${res.rows.map((r) => html`<tr><td><a href="#/${r.symbol}">${r.symbol}</a></td>${cols.map((c) => html`<td>${screenCell(c, r[c.id])}</td>`)}</tr>`)}</tbody></table></div>`;
}

/* ---------------- Find stocks ---------------- */
function ask() {
  const r = S.ask, recent = readKey(RECENT_KEY, []);
  return html`<section class="section first" aria-labelledby="fs-h"><h2 class="t-h2" id="fs-h">Find stocks</h2>
    <form class="ask-form" data-v2-ask><label class="sr" for="sc-ask">Describe the stocks you want</label><textarea id="sc-ask" name="text" maxlength="300" rows="2" placeholder="Strong stocks on the 200-day average right now">${S.askText || ''}</textarea>
      <div class="cluster"><button type="submit" class="btn btn-primary" ${S.asking ? 'disabled' : ''}>${S.asking ? 'Screening…' : 'Find symbols now'}</button>${miloButton(S.ask && S.ask.result ? 'Ask Milo about the results' : 'Ask Milo to help phrase it', { ask: S.ask && S.ask.result ? `I asked for "${S.askText}". ${S.ask.result.matched} of ${S.ask.result.considered} ranked names matched: ${(S.ask.result.rows || []).slice(0, 15).map((x) => x.symbol).join(', ')}. Which fit best, and what would make each stop fitting?` : 'Help me turn my idea into a stock screen.', context: 'Discover, Scan' })}</div></form>
    <p class="asof">A fixed reader handles most requests for free. Words it cannot read are passed to Milo, which uses one Milo question from your allowance; the same words are never charged twice.</p>
    <div class="chips chips-scroll" role="group" aria-label="Examples">${EXAMPLES.map((e) => html`<button type="button" class="chip" data-v2-ask-ex="${e}">${e}</button>`)}</div>
    ${recent.length ? html`<p class="t-label" style="margin-top:12px">Your recent requests <button type="button" class="textlink" data-v2-ask-clear>Clear</button></p><div class="chips chips-scroll">${recent.map((e) => html`<button type="button" class="chip" data-v2-ask-ex="${e}">${e}</button>`)}</div>` : ''}
    <div aria-live="polite">${r ? (r.error ? html`<div class="state err" role="alert"><p class="t-h3">The request did not run</p><p>${api.explain(r.error, 'The screen')}</p></div>` : html`
      <p class="t-label" style="margin-top:16px">Read by ${r.read_by === 'pulse' ? 'Milo' : 'the screener'}</p>
      ${(r.understood || []).length ? html`<div class="chips">${r.understood.map((u) => html`<span class="pill">${clean(u)}</span>`)}</div>` : html`<p>Nothing in that could be read as a screen.</p>`}
      ${(r.unsupported || []).length || (r.unread || []).length ? html`<p class="t-muted">The screen cannot ask about: ${[...(r.unsupported || []), ...(r.unread || []).map((w) => `not read: ${w}`)].join(', ')}.</p>` : ''}
      ${r.note ? html`<p class="stale">${clean(r.note)}</p>` : ''}
      ${r.spec ? html`<button type="button" class="btn btn-sm" data-v2-ask-edit>Edit as filters</button>` : ''}
      ${r.result ? (r.result.available === false ? html`<p>${clean(r.result.reason || '')}</p>${buildBar(r.result.building)}` : html`<p class="asof">${r.result.matched} of ${r.result.considered} ranked names match, showing the first ${(r.result.rows || []).length}. Ranking ${num(r.result.ranking_age_hours, 1)} hours old.</p>${screenTable(r.result, 'Nothing matches every part of that request.')}`) : ''}`) : ''}</div>
  </section>`;
}

/* ---------------- named scans ---------------- */
function named() {
  const g = (S.groups || {}).groups || [], sc = S.scans || {};
  const active = g.find((x) => (x.scans || []).some((s) => s.id === S.scanId)) || g[0];
  const r = S.result;
  return html`<p class="section-sub">${sc.considered ? `Named scans over the ${sc.considered} names that cleared the screen's gates, out of a ${sc.universe_size}-symbol universe. Pick a question; the answer is already computed.` : 'The universe ranking is still building. Each scan fills once it lands; this page checks every 5 seconds.'}</p>
    <div class="chips" role="group" aria-label="Scan groups">${g.map((x) => html`<button type="button" class="chip" data-v2-scan-group="${x.id}" aria-pressed="${active && active.id === x.id}">${x.name} <span class="t-muted">${x.count}</span></button>`)}</div>
    ${active ? html`<p class="t-muted">${clean(active.blurb || '')}</p><div class="seg scan-tabs" role="group" aria-label="Scans">${active.scans.map((s) => html`<button type="button" data-v2-scan="${s.id}" aria-pressed="${S.scanId === s.id}" title="${s.looks_for || ''}">${s.name}</button>`)}</div>` : ''}
    <div class="scan-result">${!r ? skeleton('rows', 6, 'Running the scan') : r.error ? failed('This scan', r.error, { retry: 'scan' }) : r.available === false ? html`<p>${clean(r.reason || 'This scan is unavailable.')}</p>${buildBar(r.building)}` : html`
      <p>${clean(r.looks_for || '')}</p>${r.stale ? html`<p class="stale">The ranking is ${num(r.age_hours, 0)} hours old, so these are yesterday's positions. A scan is a claim about now.</p>` : ''}
      <p class="asof">${r.matched} matched, showing the first ${r.shown}. Ranking ${num(r.age_hours, 1)} hours old.</p>
      ${(r.rows || []).length ? html`<div class="tscroll"><table class="t"><thead><tr><th>Symbol</th><th>Price</th>${(r.columns || []).map((c) => html`<th aria-sort="${(r.ranked_by || {}).key === c.key ? ((r.ranked_by || {}).order === 'asc' ? 'ascending' : 'descending') : 'none'}">${c.label}${(r.ranked_by || {}).key === c.key ? ((r.ranked_by || {}).order === 'asc' ? ' ▲' : ' ▼') : ''}</th>`)}</tr></thead>
        <tbody>${r.rows.map((x) => html`<tr><td><a href="#/${x.symbol}">${x.symbol}</a></td><td>${num(x.price)}</td>${(r.columns || []).map((c) => html`<td>${scanCell(c.kind, x[c.key])}</td>`)}</tr>`)}</tbody></table></div>${readings(r)}`
      : html`<p class="quiet">Nothing currently matches this scan. That is a result, not a failure: these conditions are meant to be selective.</p>`}
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
  return html`<p class="section-sub">Your own conditions over the same ranked universe the named scans use. Add up to ${max} bounds; leave either side of a bound empty to make it one-sided.</p>
    <form class="screen-form" data-v2-screen>
      ${sp.filters.length ? sp.filters.map((x, i) => { const fd = f.fields.find((y) => y.id === x.field) || {}; return html`<div class="flt"><label class="select"><span class="sr">Field</span><select data-v2-flt-field="${i}">${f.fields.map((y) => html`<option value="${y.id}" ${y.id === x.field ? 'selected' : ''}>${y.label}</option>`)}</select></label>
        <label class="field field-xs"><span class="sr">Minimum</span><input data-v2-flt-min="${i}" inputmode="decimal" placeholder="min" value="${x.min ?? ''}"></label><span>to</span>
        <label class="field field-xs"><span class="sr">Maximum</span><input data-v2-flt-max="${i}" inputmode="decimal" placeholder="max" value="${x.max ?? ''}"></label><span class="t-muted">${fd.unit === 'x' ? '×' : fd.unit || ''}</span>
        <button type="button" class="icon-btn" data-v2-flt-del="${i}" aria-label="Remove the ${fd.label || ''} filter">×</button><small class="t-muted flt-help">${clean(fd.help || '')}</small></div>`; })
      : html`<p class="quiet">No filters yet. Add one, or run it as it is to rank the whole liquid universe by trend score.</p>`}
      <div class="cluster"><button type="button" class="btn btn-sm" data-v2-flt-add ${sp.filters.length >= max ? 'disabled' : ''}>Add filter</button>${sp.filters.length ? html`<button type="button" class="textlink" data-v2-flt-clear>Clear all</button>` : ''}</div>
      <fieldset class="states"><legend class="t-label">Also require</legend>${f.states.map((s) => html`<label class="check"><input type="checkbox" data-v2-state="${s.id}" ${sp.states.includes(s.id) ? 'checked' : ''}> <span>${s.label}</span></label>`)}</fieldset>
      <div class="cluster"><label class="select"><span class="t-label">Sort by</span><select data-v2-screen-sort>${f.fields.map((y) => html`<option value="${y.id}" ${sp.sort === y.id ? 'selected' : ''}>${y.label}</option>`)}</select></label>
        <label class="select"><span class="t-label">Direction</span><select data-v2-screen-dir><option value="desc" ${sp.direction === 'desc' ? 'selected' : ''}>Highest first</option><option value="asc" ${sp.direction === 'asc' ? 'selected' : ''}>Lowest first</option></select></label>
        <button type="submit" class="btn btn-primary" ${S.screening ? 'disabled' : ''}>${S.screening ? 'Screening…' : 'Run screen'}</button></div>
      <p class="asof">What this screen cannot see: ${clean(f.blind_spot || '')}</p></form>
    <div aria-live="polite">${!res ? '' : res.error ? failed('The screen', res.error) : res.available === false ? html`<p>${clean(res.reason || '')}</p>${buildBar(res.building)}` : html`
      <h3>Matches</h3><p class="asof">${res.matched} of ${res.considered} ranked names, from a ${res.universe}-symbol universe, showing the first ${(res.rows || []).length}. Ranking ${num(res.ranking_age_hours, 1)} hours old.${res.stale ? ' The ranking is stale.' : ''} The universe drops anything under $${num((res.gates || {}).min_price, 0)} or under $${compact((res.gates || {}).min_dollar_volume)} a day.</p>
      ${(res.funnel || []).length ? html`<p class="funnel">${res.funnel.map((x) => html`<span>${x.label}: ${x.before} → ${x.after}</span>`)}</p>` : ''}
      ${(res.ignored || []).length ? html`<p class="stale">Not applied: ${res.ignored.map((x) => `${x.label || x.field} (${x.reason})`).join(', ')}.</p>` : ''}
      ${screenTable(res, 'Nothing clears every condition. That is a result rather than a failure: the funnel says which bound emptied it.')}`}</div>`;
}

/* ---------------- evaluation ---------------- */
function evaluation() {
  const e = S.evalD;
  return html`<section class="section" aria-labelledby="ev-h"><div class="section-head"><div><h2 class="t-h2" id="ev-h">Does the score work?</h2><p class="section-sub">The ranking's score replayed on history against what followed.</p></div>${miloButton('Ask Milo about this test', { ask: 'How should I read the test of whether Optic\'s score works?', context: 'Discover, Scan' })}</div>
    ${e === undefined ? html`<button type="button" class="btn btn-sm" data-v2-eval>Run the test</button><p class="asof">Free, but slow the first time: it replays the score over 220 names.</p>` : e === 'loading' ? skeleton('lines', 4, 'Replaying the score') : !e || !e.available ? html`<p>${clean((e || {}).reason || 'The test did not run.')}</p>` : html`
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
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">Scan</h1>${groupTabs('discover', 'scan')}</header>
    ${ask()}
    <section class="section" aria-labelledby="sc-h"><div class="section-head"><h2 class="t-h2" id="sc-h">${S.mode === 'build' ? 'Build a screen' : 'Scanners'}</h2>
      <div class="seg" role="group" aria-label="Mode"><button type="button" data-v2-scan-mode="named" aria-pressed="${S.mode !== 'build'}">Named scans</button><button type="button" data-v2-scan-mode="build" aria-pressed="${S.mode === 'build'}">Build a screen</button></div></div>
      ${S.mode === 'build' ? builder() : S.scans === undefined ? skeleton('rows', 4, 'Loading the scanner catalogue') : S.scansErr ? failed('The scanner catalogue', S.scansErr, { retry: 'catalogue' }) : named()}</section>
    ${evaluation()}`);
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

async function runScan(id, quiet) {
  S.scanId = id; if (!quiet) { S.result = null; paint(); }
  try { const r = await api.get(`/api/scanners/${encodeURIComponent(id)}?limit=25`, { ttl: quiet ? 0 : 60000, force: !!quiet }); if (S.scanId !== id || !live) return; S.result = r; }
  catch (e) { if (S.scanId === id) S.result = { error: e }; }
  paint(); whenBuilt(S.result && S.result.building, () => runScan(id, true));
}
function whenBuilt(building, again) { clearTimeout(poll); if (building && live) poll = setTimeout(again, 5000); }
async function runScreen() {
  const bad = S.spec.filters.some((x) => Number.isNaN(x.min) || Number.isNaN(x.max));
  if (bad) { toast('One of the bounds is not a number, so the screen did not run.'); return; }
  S.screening = true; paint();
  try { S.screen = await api.post('/api/screener', S.spec, { timeout: 60000 }); } catch (e) { S.screen = { error: e }; }
  S.screening = false; paint(); whenBuilt(S.screen && S.screen.building, runScreen);
}
async function runAsk(text) {
  text = String(text || '').trim(); if (!text) return;
  S.askText = text; S.asking = true; S.ask = null; paint();
  try {
    S.ask = await api.post('/api/screener/ask', { text }, { timeout: 60000 });
    const rec = [text, ...readKey(RECENT_KEY, []).filter((x) => x.toLowerCase() !== text.toLowerCase())].slice(0, 6);
    writeKey(RECENT_KEY, rec);
  } catch (e) { S.ask = { error: e }; }
  S.asking = false; paint();
}

export async function render(main, route) {
  live = true; mainEl = main;
  S = { mode: 'named', scanId: (route.params || {}).id || 'momentum', spec: Object.assign(blankSpec(), readKey(SCREEN_KEY, {})) };
  document.title = 'Scan, Optic';
  provideContext(() => ({ view: 'scan', scan: S.result && S.result.rows ? { id: S.scanId, name: S.result.name, rows: S.result.rows.slice(0, 15) } : null }));
  paint(); wire(main);
  try { [S.scans, S.groups] = await Promise.all([api.get('/api/scanners', { ttl: 120000 }), api.get('/api/scanners/groups', { ttl: 600000 }).catch(() => null)]); if (!S.groups && S.scans) S.groups = { groups: [{ id: 'all', name: 'Screens', count: S.scans.scans.length, scans: S.scans.scans }] }; }
  catch (e) { S.scansErr = e; S.scans = null; }
  paint();
  if (S.scans) runScan(S.scanId);
}
export function dispose() { live = false; clearTimeout(poll); }
export const retry = { scan: () => runScan(S.scanId), catalogue: (m, r) => render(m, r) };

function saveSpec() { writeKey(SCREEN_KEY, S.spec); }
function wire(main) {
  main.addEventListener('submit', (e) => {
    if (e.target.closest('[data-v2-ask]')) { e.preventDefault(); runAsk(e.target.text.value); return; }
    if (e.target.closest('[data-v2-screen]')) { e.preventDefault(); runScreen(); }
  });
  main.addEventListener('keydown', (e) => { if (e.target.id === 'sc-ask' && e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runAsk(e.target.value); } });
  main.addEventListener('input', (e) => {
    const t = e.target; let i;
    const val = (v) => { const s = String(v).trim().replace(/,/g, ''); if (!s) return null; const n = Number(s); return Number.isFinite(n) ? n : NaN; };
    if ((i = t.dataset.v2FltMin) !== undefined) { S.spec.filters[i].min = val(t.value); t.closest('.field').classList.toggle('bad', Number.isNaN(S.spec.filters[i].min)); saveSpec(); }
    else if ((i = t.dataset.v2FltMax) !== undefined) { S.spec.filters[i].max = val(t.value); t.closest('.field').classList.toggle('bad', Number.isNaN(S.spec.filters[i].max)); saveSpec(); }
    else if (t.id === 'sc-ask') S.askText = t.value;
  });
  main.addEventListener('change', (e) => {
    const t = e.target;
    if (t.dataset.v2FltField !== undefined) { const f = S.spec.filters[t.dataset.v2FltField]; f.field = t.value; f.min = null; f.max = null; saveSpec(); paint(); return; }
    if (t.dataset.v2State !== undefined) { const id = t.dataset.v2State; S.spec.states = t.checked ? [...new Set([...S.spec.states, id])] : S.spec.states.filter((x) => x !== id); saveSpec(); return; }
    if (t.matches('[data-v2-screen-sort]')) { S.spec.sort = t.value; saveSpec(); return; }
    if (t.matches('[data-v2-screen-dir]')) { S.spec.direction = t.value; saveSpec(); }
  });
  main.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-ask-ex]'))) { runAsk(b.dataset.v2AskEx); return; }
    if (t('[data-v2-ask-clear]')) { writeKey(RECENT_KEY, null); paint(); return; }
    if (t('[data-v2-ask-edit]')) { const sp = S.ask.spec; S.spec = Object.assign(blankSpec(), sp); saveSpec(); S.screen = S.ask.result; S.mode = 'build'; if (S.fields === undefined) loadFields(); paint(); return; }
    if ((b = t('[data-v2-scan-mode]'))) { S.mode = b.dataset.v2ScanMode; if (S.mode === 'build' && S.fields === undefined) loadFields(); paint(); return; }
    if ((b = t('[data-v2-scan-group]'))) { const g = S.groups.groups.find((x) => x.id === b.dataset.v2ScanGroup); if (g && g.scans[0]) runScan(g.scans[0].id); return; }
    if ((b = t('[data-v2-scan]'))) { runScan(b.dataset.v2Scan); return; }
    if (t('[data-v2-flt-add]')) { const used = new Set(S.spec.filters.map((x) => x.field)); const f = (S.fields.fields || []).find((x) => !used.has(x.id)); if (f) { S.spec.filters.push({ field: f.id, min: null, max: null }); saveSpec(); paint(); } return; }
    if ((b = t('[data-v2-flt-del]'))) { S.spec.filters.splice(Number(b.dataset.v2FltDel), 1); saveSpec(); paint(); return; }
    if (t('[data-v2-flt-clear]')) { S.spec.filters = []; saveSpec(); paint(); return; }
    if (t('[data-v2-eval]')) { S.evalD = 'loading'; paint(); try { S.evalD = await api.get('/api/evaluate', { ttl: 3600000, timeout: 180000 }); } catch (err) { S.evalD = { available: false, reason: api.explain(err, 'The test') }; } paint(); }
  });
}
async function loadFields() { try { S.fields = await api.get('/api/screener/fields', { ttl: 3600000 }); } catch (e) { S.fields = null; } paint(); }
void capFirst; void $;
