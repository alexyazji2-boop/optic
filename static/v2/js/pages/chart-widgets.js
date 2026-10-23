// Dossier, Chart: the side widgets, carried over from the classic app's dock and widget rail (static/app.js,
// WS_WIDGETS and wsWidgetBody). Eighteen panels, each opened from the rail beside the plot with the classic
// name, order and mark. Nothing is open to start, and the open ones are remembered with the chart's view
// (optic.v2.chart.v1, `dock`). On a wide screen any number stack between the plot and the rail, in the
// rail's order; on a phone one shows at a time, under the chart.
//
// Data. Most read the /api/ticker payload the page has already loaded, so opening them asks for nothing.
// Alerts, Season, the analysts' latest actions, Stop check, Pairs, Backtest and Trading ask their own
// endpoints, and only once their panel is open. None of them calls a model. Notes, Checklist, Stop check,
// Backtest and Pairs keep what the reader types in the classic keys, so it shows in both apps; the first
// three are personal keys (core/device.js) and are read and written only while this browser holds the
// signed-in reader's things.
//
// Fields are the payload's real ones. Classic's Reports widget read financials.revenue_growth_pct and
// gross_margin_pct, which the financials block does not carry (it has growth and margins), its Options
// widget read greeks.atm_greeks as one object (it is a list, one per expiry), and its Insiders widget read
// short_interest.short_percent_float (the field is percent_of_float). Here each reads what is sent.
import { html, raw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, signed, money, compact, isNum, clean, capFirst, shortDate, fullDate, ago, dir } from '../core/format.js';
import { GLOSSARY } from '../core/glossary.js';
import { skeleton, failed } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { button as miloButton } from '../ui/milo.js';
import { toast } from '../ui/toast.js';

/* The classic marks, drawn to the rail's recipe: a 24-unit box, no fill, a 1.8 stroke, round caps. */
export const WIDGETS = [
  { id: 'watchlist', label: 'Watch', icon: '<path d="M2.6 12C6 6.8 8.9 4.6 12 4.6s6 2.2 9.4 7.4c-3.4 5.2-6.3 7.4-9.4 7.4S6 17.2 2.6 12Z"/><circle cx="12" cy="12" r="2.6"/>' },
  { id: 'alerts', label: 'Alerts', icon: '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2H4.5Z"/><path d="M10 21h4"/>' },
  { id: 'news', label: 'News', icon: '<rect x="3.5" y="5" width="13" height="14" rx="1.5"/><path d="M16.5 9h3a1 1 0 0 1 1 1v7.5a1.5 1.5 0 0 1-3 0V9"/><path d="M6.5 9h7M6.5 12.5h7M6.5 16h4"/>' },
  { id: 'analysts', label: 'Analysts', icon: '<circle cx="12" cy="12" r="7.5"/><circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3"/>' },
  { id: 'seasonality', label: 'Season', icon: '<rect x="3.5" y="5" width="17" height="15" rx="1.5"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>' },
  { id: 'notes', label: 'Notes', icon: '<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17Z"/><path d="m14.5 7.5 3 3"/>' },
  { id: 'insiders', label: 'Insiders', icon: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20a7 7 0 0 1 14 0"/>' },
  { id: 'reports', label: 'Reports', icon: '<path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7Z"/><path d="M14 3v4h4"/><path d="M9.5 17v-3M12 17v-5M14.5 17v-2"/>' },
  { id: 'checklist', label: 'Checklist', icon: '<path d="m4 7 2 2 3.5-3.5"/><path d="M12.5 7.5H20"/><path d="m4 15 2 2 3.5-3.5"/><path d="M12.5 15.5H20"/>' },
  { id: 'stopcheck', label: 'Stop check', short: 'Stop', icon: '<path d="M3.5 9h17"/><path d="M3.5 14.5h17" stroke-dasharray="2.5 2"/><path d="m12 4.5 0 3M12 16v3.5"/>' },
  { id: 'options', label: 'Options', icon: '<path d="M3.5 15.5h7.5l9.5-9.5"/><path d="M3.5 19.5h17"/>' },
  { id: 'levels', label: 'Key levels', short: 'Levels', icon: '<path d="M3.5 6.5h17M3.5 17.5h17"/><path d="m4.5 14 4-3.5 3 2.5 4-5 4 2.5"/>' },
  { id: 'stats', label: 'Stats', icon: '<path d="M9 6.5h11M9 12h11M9 17.5h11"/><path d="M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01" stroke-width="2.6"/>' },
  { id: 'patterns', label: 'Patterns', icon: '<path d="M7 3.5v3M7 15.5v5"/><rect x="5" y="6.5" width="4" height="9" rx="0.8"/><path d="M17 5v4M17 16v3.5"/><rect x="15" y="9" width="4" height="7" rx="0.8"/>' },
  { id: 'pairs', label: 'Pairs', icon: '<path d="M3.5 9c3 0 4.5 3 8.5 3s5.5-5 8.5-5"/><path d="M3.5 15c3 0 4.5-3 8.5-3s5.5 5 8.5 5"/>' },
  { id: 'backtest', label: 'Backtest', icon: '<path d="M3.5 19.5h17"/><path d="M4.5 16.5 9 12l3 2.5 3.5-5 4 2.5"/><circle cx="19.5" cy="12" r="1.2"/>' },
  { id: 'trading', label: 'Trading', icon: '<path d="M4 8.5h15l-3.5-3.5"/><path d="M20 15.5H5l3.5 3.5"/>' },
  { id: 'learn', label: 'Learn', icon: '<path d="M2.8 9.5 12 5l9.2 4.5L12 14Z"/><path d="M7 11.8v4.4c0 1.4 2.2 2.6 5 2.6s5-1.2 5-2.6v-4.4"/><path d="M21.2 9.5v5"/>' },
];
export const IDS = WIDGETS.map((w) => w.id);
const byId = (id) => WIDGETS.find((w) => w.id === id);
/** The widgets that read only the ticker payload, redrawn when it arrives. */
export const FROM_TICKER = ['news', 'analysts', 'insiders', 'reports', 'stopcheck', 'options', 'levels', 'stats', 'patterns'];
const mark = (w) => raw(`<svg viewBox="0 0 24 24" aria-hidden="true" class="chw-ic">${w.icon}</svg>`);

/* A pre-trade checklist with the classic app's fixed questions: an editable one becomes a list of the
 * questions you already like the answers to. Ticked per symbol. */
export const CHECKS = [
  'Do I know what invalidates this?',
  'Is the stop at a level, not a round number?',
  'Is this sized so the stop costs 1% or less?',
  'Am I early, or chasing?',
  'Does the higher timeframe agree?',
  'Is earnings inside my holding period?',
  'Would I take the other side at this price?',
];

/* ---------------- what the reader keeps, in the classic keys ---------------- */
const KEY = { notes: 'optic.chart.notes.v1', checks: 'optic.chart.checks.v1', stop: 'optic.chart.stopcheck.v1', bt: 'optic.chart.backtest.v1', pairs: 'optic.chart.pairs.v1' };
const PERSONAL = new Set([KEY.notes, KEY.checks, KEY.stop]);
const held = () => holds(store.state.user);
function readKey(k) {
  if (PERSONAL.has(k) && !held()) return {};
  try { const v = JSON.parse(localStorage.getItem(k) || 'null'); return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; } catch (e) { return {}; }
}
function writeKey(k, v) {
  if (PERSONAL.has(k) && !held()) { toast('Not saved: this browser is holding another account\'s things.'); return false; }
  try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { toast('This browser refused to save it.'); return false; }
}
const pick = (o, keys) => Object.fromEntries(keys.filter((k) => k in o).map((k) => [k, o[k]]));

/* ---------------- state ---------------- */
let C = null;                 // the page: sym(), t(), tErr(), phase(), repaint(id), chart(), overlayOn(k), overlay(k, on)
let S = {};                   // this symbol's answers, replaced by reset()
const G = { cat: undefined, catErr: null, alerts: undefined, alertsErr: null, tracker: undefined, trackerErr: null, learn: '' };   // the same whatever the symbol
let BT = {}, SC = {}, PR = {};

export function bind(page) { C = page; }
export function reset() {
  S = {};
  BT = Object.assign({ strategy: 'macd_turn_below_zero', timeframe: '1d', years: 5, params: {}, show: true }, pick(readKey(KEY.bt), ['strategy', 'timeframe', 'years', 'params', 'show']));
  if (!BT.params || typeof BT.params !== 'object') BT.params = {};
  SC = Object.assign({ entry: {}, stop: {}, buffer: 0.25, account: '', riskPct: 1, show: true }, pick(readKey(KEY.stop), ['entry', 'stop', 'buffer', 'account', 'riskPct', 'show']));
  PR = Object.assign({ peer: {} }, pick(readKey(KEY.pairs), ['peer']));
}
reset();

/** One request into a box; its answer is drawn only while the reader is still on the symbol it was for. */
function fetchInto(box, key, url, opts, id) {
  if (box[key] !== undefined || box[key + 'Busy']) return;
  box[key + 'Busy'] = true; box[key + 'Err'] = null;
  api.get(url, opts).then((r) => { box[key] = r; }, (e) => { box[key] = null; box[key + 'Err'] = e; })
    .finally(() => { box[key + 'Busy'] = false; if (C && (box === G || box === S)) C.repaint(id); });
}

/** Start whatever an open widget needs. Safe to call again: each request is made once. */
export function need(id) {
  if (!C) return;
  const enc = encodeURIComponent(C.sym());
  if (id === 'watchlist' && store.state.lists === null) store.loadLists().catch(() => {}).finally(() => C.repaint('watchlist'));
  if (id === 'alerts') fetchInto(G, 'alerts', '/api/alerts?limit=20', { ttl: 60000, timeout: 30000 }, 'alerts');
  if (id === 'analysts') fetchInto(S, 'acts', `/api/analysts/${enc}?limit=6`, { ttl: 600000, timeout: 30000 }, 'analysts');
  if (id === 'seasonality') fetchInto(S, 'seas', `/api/seasonality/${enc}`, { ttl: 3600000, timeout: 45000 }, 'seasonality');
  if (id === 'trading') fetchInto(G, 'tracker', '/api/tracker?book=balanced', { ttl: 60000, timeout: 45000 }, 'trading');
  if (id === 'stopcheck') runStop();
  if (id === 'pairs') { fetchInto(S, 'peers', `/api/pairs/${enc}/peers`, { ttl: 3600000, timeout: 45000 }, 'pairs'); runPair(); }
  if (id === 'backtest') runBacktest();
}
/** "Try again" on a widget that failed. */
export function retry(id) {
  if (id === 'alerts') G.alerts = undefined;
  if (id === 'trading') G.tracker = undefined;
  if (id === 'analysts') S.acts = undefined;
  if (id === 'seasonality') S.seas = undefined;
  if (id === 'pairs') { S.peers = undefined; S.prKey = null; }
  if (id === 'stopcheck') S.scKey = null;
  if (id === 'backtest') { if (G.catErr) G.cat = undefined; S.btKey = null; }
  if (id === 'watchlist') store.loadLists({ force: true }).catch(() => {}).finally(() => C.repaint('watchlist'));
  C.repaint(id); need(id);
}

/* ---------------- small pieces ---------------- */
const none = (t) => html`<p class="chw-none">${t}</p>`;
const fine = (t) => html`<p class="chw-fine">${t}</p>`;
const more = (href, t) => html`<a class="textlink chw-more" href="${href}">${t}</a>`;
const kv = (rows) => html`<dl class="chw-rows">${rows.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
const tone = (v) => (dir(v) === 'flat' ? '' : dir(v));
const pct0 = (v) => (isNum(v) ? `${num(v, 0)}%` : 'n/a');
/** The ticker payload, or what to show while it is not here. */
function payload() {
  const t = C.t();
  if (t) return { t };
  const e = C.tErr();
  return { wait: e ? failed('This symbol\'s figures', e, { retry: 'ticker' }) : skeleton('lines', 3, 'Loading') };
}
/** Exact counts under a million, compact above: 2,605 shares and 2,900 are different facts. */
const shares = (n, sign = false) => { const v = Number(n || 0), s = Math.abs(v) >= 1e6 ? compact(v) : num(v, 0); return sign && v > 0 ? `+${s}` : s; };
const dollars = (v) => (isNum(v) ? `${Number(v) < 0 ? '−' : ''}$${compact(Math.abs(Number(v)))}` : 'n/a');
const tile = (val, cls, lab, sub) => html`<div class="chw-tile"><b class="${cls}">${val}</b><span>${lab}</span>${sub ? html`<small>${sub}</small>` : ''}</div>`;

/* ---------------- the widgets ---------------- */
const BODY = {
  watchlist() {
    const sym = C.sym(), lists = store.state.lists;
    if (lists === null) return store.state.listsError ? failed('Your watchlist', store.state.listsError, { retry: 'w-watchlist' }) : skeleton('rows', 3, 'Loading your watchlist');
    const L = store.activeList(), syms = L ? L.symbols : [], name = L ? L.name : 'your watchlist';
    return html`${lists.length > 1 ? html`<label class="select chw-sel"><span class="sr">Watchlist</span><select data-chw-list>${lists.map((l) => html`<option value="${l.id}" ${l.id === store.state.activeId ? 'selected' : ''}>${l.name}</option>`)}</select></label>` : ''}
      ${syms.length ? html`<ul class="chw-list chw-watch">${syms.map((s) => html`<li><a class="tick" href="#/${encodeURIComponent(s)}/chart" ${s === sym ? raw('aria-current="page"') : ''}>${s}</a><button type="button" class="ch-tool chw-x" data-chw-unwatch="${s}" aria-label="Remove ${s} from ${name}" title="Remove ${s}">${icon('close')}</button></li>`)}</ul>` : none(`Nothing in ${name} yet.`)}
      <form class="chw-add" data-chw-watchform><label class="field field-sm"><span class="sr">Add a symbol to ${name}</span><input name="s" placeholder="Add ticker" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="12"></label><button type="submit" class="btn btn-sm">Add</button></form>
      ${sym && !syms.includes(sym) ? html`<button type="button" class="btn btn-sm chw-wide" data-chw-watchadd="${sym}">Add ${sym}</button>` : ''}
      ${fine(store.signedIn() ? 'The lists on your account, the same as the Watchlist page.' : 'Kept in this browser until you sign in.')}`;
  },

  alerts() {
    if (G.alertsErr) return failed('The alerts', G.alertsErr, { retry: 'w-alerts' });
    if (!G.alerts) return skeleton('rows', 3, 'Loading alerts');
    const rows = (G.alerts.alerts || []).slice(0, 12);
    return html`${rows.length ? html`<ul class="chw-list chw-alerts">${rows.map((x) => html`<li class="${x.seen ? '' : 'unseen'}"><p class="chw-line"><b>${clean(x.kind_label || x.kind || '')}</b>${x.ticker ? html` <a class="tick" href="#/${encodeURIComponent(x.ticker)}/chart">${x.ticker}</a>` : ''} <small class="t-muted">${ago(x.created_at)}</small></p><p>${clean(x.title || '')}</p>${x.body ? html`<small class="t-muted">${clean(x.body)}</small>` : ''}</li>`)}</ul>`
      : none('Nothing has fired from the scheduled scan yet. Optic\'s own scans record setups, signal changes and unusual activity here when they find them.')}
      ${fine('Shared by every reader of Optic.')}
      ${more('#/alerts', 'Your watches and every alert')}`;
  },

  news() {
    const p = payload(); if (p.wait) return p.wait;
    const sym = C.sym(), n = p.t.news || {}, arts = (n.articles || []).slice(0, 7);
    if (!arts.length) return html`${none('No recent coverage.')}${more(`#/${sym}/news`, `News for ${sym}`)}`;
    const head = [n.overall_tone ? capFirst(n.overall_tone) : '', n.article_count ? `${num(n.article_count, 0)} stories` : '', n.held && n.held.fetched_at ? `fetched ${ago(n.held.fetched_at)}, the feed is empty now` : ''].filter(Boolean).join(', ');
    return html`${head ? fine(`${head}.`) : ''}<ul class="chw-list chw-news">${arts.map((a) => html`<li><a href="${a.url || a.link || '#'}" target="_blank" rel="noopener">${clean(a.title || '')}</a><small class="t-muted">${clean(a.publisher || a.source || '')}${a.published ? `, ${ago(a.published)}` : ''}</small></li>`)}</ul>
      ${more(`#/${sym}/news`, `All news for ${sym}`)}`;
  },

  analysts() {
    const p = payload(); if (p.wait) return p.wait;
    const t = p.t, q = t.quote || {}, rows = [];
    if (isNum(q.analyst_target)) rows.push(['Mean target', money(q.analyst_target)]);
    if (q.recommendation) rows.push(['Consensus', capFirst(String(q.recommendation).replace(/_/g, ' '))]);   // "strong_buy" is a machine token
    if (isNum(q.forward_pe)) rows.push(['Forward P/E', num(q.forward_pe, 1)]);
    if (isNum(q.peg_ratio)) rows.push(['PEG', num(q.peg_ratio, 2)]);
    if (isNum(q.revenue_growth)) rows.push(['Revenue growth', signed(q.revenue_growth * 100, 1)]);
    const em = t.earnings_momentum || {};
    if (em.revision_direction && em.revision_direction !== 'unknown') rows.push(['EPS estimate revisions', capFirst(em.revision_direction)]);   // "Revisions: Flat" beside the price target read as the target's   // "unknown" is no revision history
    if (!rows.length) {
      const fund = ['ETF', 'MUTUALFUND'].includes(String(q.quote_type || '').toUpperCase());
      return none(fund ? 'A fund has no earnings, so it has no analyst estimates or price target of its own. Its holdings do.' : 'No analyst data for this symbol.');
    }
    const a = S.acts;
    const latest = S.actsErr ? fine('The latest actions did not load.') : a === undefined ? skeleton('lines', 2, 'Loading the latest actions')
      : a && a.available !== false && (a.rows || []).length ? html`<h4 class="chw-sub">Latest actions</h4><ul class="chw-list">${a.rows.slice(0, 6).map((r) => html`<li><p class="chw-line"><b>${clean(r.firm || '')}</b> <span class="${r.action === 'up' ? 'up' : r.action === 'down' ? 'down' : ''}">${clean(r.action_label || r.action || '')}</span></p><small class="t-muted">${clean(r.rating || 'No rating')}${isNum(r.target) ? `, target ${num(r.target)}${isNum(r.prior_target) && r.prior_target !== r.target ? ` from ${num(r.prior_target)}` : ''}` : ''}, ${shortDate(r.at)}</small></li>`)}</ul>` : '';
    return html`${kv(rows)}
      ${isNum(q.analyst_target) && isNum(q.price) && Number(q.price) ? fine(`${signed(((q.analyst_target - q.price) / q.price) * 100, 1)} to the mean target. A target is a forecast, and the record of them as a group is poor. Read it as sentiment, not as a level.`) : ''}
      ${latest}${more('#/analysts', 'Analyst actions across the market')}`;
  },

  /* A compact month grid: a losing month is drawn below the line, and only a month that clears the
   * significance test takes the up or down colour (at n=15 most do not). */
  seasonality() {
    if (S.seasErr) return failed('Seasonality', S.seasErr, { retry: 'w-seasonality' });
    const sn = S.seas;
    if (sn === undefined) return skeleton('lines', 3, 'Loading seasonality');
    if (sn && sn.error) return none(clean(sn.error));
    const rows = ((sn || {}).monthly || {}).rows || [];
    if (!rows.length) return none('Not enough history.');
    const sym = C.sym(), val = (r) => (r.raw || {}).mean, max = Math.max(...rows.map((r) => Math.abs(val(r) || 0)), 0.01);
    const said = (r) => (r.raw || {}).verdict || 'no verdict';   // the server's own word: significant, unproven, noise or too few
    const read = (r) => `${r.label || r.short}: mean ${signed(val(r), 2)} over ${num((r.raw || {}).n, 0)} years, up in ${num((r.raw || {}).hit_rate, 0)}% of them, ${said(r)}`;
    return html`<div class="chw-seas" role="img" aria-label="${`Mean move by calendar month over ${num(sn.years, 0)} years. ${rows.map(read).join('. ')}.`}">${rows.map((r) => {
      const v = val(r) || 0, h = Math.max(Math.round((Math.abs(v) / max) * 26), 2), shade = said(r) === 'significant' ? (v >= 0 ? 'up' : 'down') : 'faint';
      return html`<div class="chw-scol" title="${read(r)}"><span class="chw-shit">${num((r.raw || {}).hit_rate, 0)}</span><span class="chw-shalf">${v >= 0 ? html`<i class="${shade}" style="height:${h}px"></i>` : ''}</span><span class="chw-shalf dn">${v < 0 ? html`<i class="${shade}" style="height:${h}px"></i>` : ''}</span><span class="chw-slab">${(r.short || '').slice(0, 1)}</span></div>`;
    })}</div>
      ${fine(`Each bar is the month's mean move, above the line for a gain and below for a loss; the figure over it is how often the month was up. ${num(sn.years, 0)} years. Only a month that clears the significance test is coloured: at n=${num(((rows[0] || {}).raw || {}).n, 0)} per month most come back noise.`)}
      <details class="chw-details"><summary>Exact figures</summary><div class="tscroll"><table class="t chw-table"><thead><tr><th>Month</th><th class="num">Mean</th><th class="num">Up</th><th>Reads as</th></tr></thead>
        <tbody>${rows.map((r) => html`<tr><td>${r.short || r.label}</td><td class="num">${signed(val(r), 2)}</td><td class="num">${pct0((r.raw || {}).hit_rate)}</td><td>${said(r)}</td></tr>`)}</tbody></table></div></details>
      ${more(`#/${sym}/options`, 'The full table, with the medians and the baseline, on the Options tab')}`;
  },

  notes() {
    const sym = C.sym(), ok = held(), text = ok ? (readKey(KEY.notes)[sym] || '') : '';
    return html`<label class="sr" for="chw-note-in">Notes on ${sym}</label><textarea id="chw-note-in" class="chw-note" data-chw-note="${sym}" rows="6" placeholder="Why are you looking at ${sym}? What would change your mind?" ${ok ? '' : 'disabled'}>${text}</textarea>
      ${fine(ok ? `Saved for ${sym} on this device. The one thing on the page the terminal cannot work out for you.` : 'Notes are not kept while this browser is holding another account\'s things.')}`;
  },

  insiders() {
    const p = payload(); if (p.wait) return p.wait;
    const c = p.t.company || {}, own = c.ownership || {}, six = own.insider_6m || {}, si = c.short_interest || {}, tx = (own.recent_transactions || []).slice(0, 6), rows = [];
    if (own.insider_signal) rows.push(['6-month signal', capFirst(own.insider_signal)]);
    if (isNum(six.net_shares)) rows.push(['Net shares', shares(six.net_shares, true)]);
    if (six.purchase_count) rows.push(['Buys', num(six.purchase_count, 0)]);
    if (six.sale_count) rows.push(['Sells', num(six.sale_count, 0)]);
    if (si.available !== false && isNum(si.percent_of_float)) rows.push(['Short float', `${num(si.percent_of_float * 100, 2)}%`]);   // a fraction of the float
    if (si.available !== false && isNum(si.days_to_cover)) rows.push(['Days to cover', num(si.days_to_cover, 1)]);
    if (!rows.length && !tx.length) return none('No ownership data.');
    // Direction comes from `action`: `shares` is a magnitude. `other` (exercises, grants, gifts) is no direction at all.
    const row = (x) => {
      const a = String(x.action || '').toLowerCase(), cls = a === 'purchase' ? 'up' : a === 'sale' ? 'down' : '';
      const amt = [isNum(x.shares) ? `${shares(x.shares)} shares` : '', isNum(x.value) && x.value ? `$${compact(x.value)}` : ''].filter(Boolean).join(', ');
      return html`<li title="${[x.insider, x.position, x.detail].filter(Boolean).join('. ')}"><p class="chw-line"><b class="${cls}">${a === 'purchase' ? 'Bought' : a === 'sale' ? 'Sold' : 'Other'}</b> ${clean(x.insider || '')}</p><small class="t-muted">${amt}${amt ? ', ' : ''}${shortDate(x.date)}${x.position ? `, ${clean(x.position)}` : ''}</small></li>`;
    };
    return html`${rows.length ? kv(rows) : ''}
      ${tx.length ? html`<ul class="chw-list chw-ins">${tx.map(row)}</ul>${fine('Shares and value as filed. An exercise or conversion is neither a purchase nor a sale, so it is left uncoloured.')}` : ''}
      ${spanLine(p.t)}
      ${more('#/insiders', 'Insider filings and House trades')}`;
  },

  reports() {
    const p = payload(); if (p.wait) return p.wait;
    const t = p.t, c = t.company || {}, fin = c.financials || {}, g = fin.growth || {}, m = fin.margins || {}, eh = c.earnings_history || {}, q = t.quote || {}, sym = C.sym(), rows = [];
    if (isNum(g.revenue_yoy_pct)) rows.push(['Revenue growth, year on year', signed(g.revenue_yoy_pct, 1)]);
    if (isNum(m.gross_pct)) rows.push(['Gross margin', `${num(m.gross_pct, 1)}%`]);
    if (isNum(q.trailing_pe) && q.trailing_pe > 0) rows.push(['P/E (trailing)', num(q.trailing_pe, 1)]);
    if (isNum(q.forward_pe) && q.forward_pe > 0) rows.push(['P/E (forward)', num(q.forward_pe, 1)]);
    if (isNum(eh.beat_rate_pct)) rows.push(['EPS beat rate', `${num(eh.beat_rate_pct, 0)}%${eh.sample_size ? ` of ${num(eh.sample_size, 0)} quarters` : ''}`]);
    const f = ((t.filings || {}).filings || []).slice(0, 5);
    if (!rows.length && !f.length) return none('No filings or financials.');
    return html`${rows.length ? kv(rows) : ''}
      ${f.length ? html`<h4 class="chw-sub">Latest filings</h4><ul class="chw-list">${f.map((x) => html`<li><a href="${x.url || '#'}" target="_blank" rel="noopener"><b>${x.form || ''}</b> ${clean(x.what || '')}</a><small class="t-muted">Filed ${fullDate(x.filed || x.date)}</small></li>`)}</ul>` : ''}
      ${more(`#/${sym}/financials`, `Financials for ${sym}`)}`;
  },

  checklist() {
    const sym = C.sym(), ok = held(), on = new Set(ok ? (readKey(KEY.checks)[sym] || []) : []);
    return html`<ul class="chw-checks">${CHECKS.map((q, i) => html`<li><label class="check"><input type="checkbox" data-chw-check="${i}" ${on.has(i) ? 'checked' : ''} ${ok ? '' : 'disabled'}> <span>${q}</span></label></li>`)}</ul>
      <p class="chw-fine" data-chw-checkn>${checkCount(on.size, sym)}</p>`;
  },

  stopcheck() {
    if (!C.t() && !C.tErr()) return skeleton('lines', 3, 'Loading');
    const { entry, stop, fromPlan } = scInputs(), v = (x) => (isNum(x) ? String(Math.round(x * 100) / 100) : '');
    const controls = html`<div class="chw-fields">
      <label class="chw-field"><span>Entry</span><input type="number" step="0.01" min="0" inputmode="decimal" data-chw-sc="entry" value="${v(entry)}"></label>
      <label class="chw-field"><span>Stop</span><input type="number" step="0.01" min="0" inputmode="decimal" data-chw-sc="stop" value="${v(stop)}" placeholder="Your stop"></label>
      <label class="chw-field"><span>Buffer past the level</span><select data-chw-sc="buffer">${[[0.1, '0.1 ATR'], [0.25, '0.25 ATR'], [0.5, '0.5 ATR']].map(([x, l]) => html`<option value="${x}" ${Number(SC.buffer) === x ? 'selected' : ''}>${l}</option>`)}</select></label>
      <label class="chw-field"><span>Account (optional)</span><input type="number" step="100" min="0" inputmode="numeric" data-chw-sc="account" value="${SC.account || ''}" placeholder="For sizing"></label></div>
      ${fromPlan ? fine('Stop from the entry plan (1.5 ATR from the price). Type your own to check it.') : ''}`;
    if (!(stop > 0)) return html`${controls}${none('Enter a stop to check it against round numbers.')}`;
    if (S.scErr) return html`${controls}${failed('The stop check', S.scErr, { retry: 'w-stopcheck' })}`;
    const r = S.sc;
    if (r === undefined) return html`${controls}${skeleton('lines', 3, 'Checking the stop')}`;
    if (!r) return controls;
    if (r.available === false) return html`${controls}${none(clean(r.reason || 'No result.'))}`;
    const sized = Number(SC.account) > 0, moved = !!r.moved;
    // How far the stop sits beyond the level, away from the price; negative is between the price and the level.
    const past = r.round_level ? (r.side === 'long' ? r.round_level.price - r.stop : r.stop - r.round_level.price) / r.atr : null;
    const rows = [
      ['Stop', num(r.stop), num(r.adjusted_stop)],
      ['Past the round number', past === null ? 'None within the buffer' : Math.abs(past) < 0.005 ? 'On it' : past < 0 ? `Inside it by ${num(-past, 2)} ATR` : `${num(past, 2)} ATR`, `${num(r.past_level_atr, 2)} ATR`],
      ['Crosses that went further', pct0(r.swept_share_pct_before), pct0(r.swept_share_pct)],
      ['Risk a share', num(r.risk_per_share), num(r.risk_per_share_adjusted)],
      sized ? [`Shares at ${num(r.risk_pct, 0)}% risk`, num(r.shares_for_risk, 0), num(r.shares_for_risk_adjusted, 0)] : null,
    ].filter(Boolean);
    const ev = r.evidence || {}, way = r.side === 'long' ? 'down' : 'up', fall = r.side === 'long' ? 'fall' : 'rise';
    return html`${controls}<p class="chw-verdict">${clean(r.text || '')}</p>
      <div class="tscroll"><table class="t chw-table"><thead><tr><th></th><th class="num">Yours</th>${moved ? html`<th class="num">Buffered</th>` : ''}</tr></thead>
        <tbody>${rows.map(([k, a, b]) => html`<tr><td>${k}</td><td class="num">${a}</td>${moved ? html`<td class="num">${b}</td>` : ''}</tr>`)}</tbody></table></div>
      ${fine(`ATR ${num(r.atr, 2)} (14-day${r.atr_as_of ? `, to ${shortDate(r.atr_as_of)}` : ''}). Round numbers every $${num(r.step, r.step < 1 ? 1 : 0)} at this price. "Crosses that went further": of the times a ${fall} crossed a round number in the study, the share that went past where this stop sits.`)}
      <label class="check chw-show"><input type="checkbox" data-chw-scshow ${SC.show ? 'checked' : ''}> <span>Show on the chart</span></label>
      <details class="chw-details"><summary>What this rests on</summary>
        ${fine(`${clean(ev.sample || '')}: how far a ${fall} through a level went before a five-minute close back, for round numbers and for arbitrary prices at the same spacing.`)}
        <div class="tscroll"><table class="t chw-table"><thead><tr><th>Past by more than</th><th class="num">Round</th><th class="num">Other</th></tr></thead><tbody>${(ev.buffers_atr || []).map((b, k) => html`<tr><td>${num(b, 2)} ATR</td><td class="num">${pct0((ev['round_' + way] || [])[k])}</td><td class="num">${pct0((ev['control_' + way] || [])[k])}</td></tr>`)}</tbody></table></div>
        ${fine('Round numbers draw a little more overshoot on the way down, and none to speak of on the way up. The bigger finding holds at any level: most crosses came back within the session, so a stop sitting right at a level is the one a sweep takes. The post\'s research is on currencies (Osler, New York Fed, 2003); this is the check on stocks.')}
        ${r.method ? fine(clean(r.method)) : ''}
        ${(r.caveats || []).length ? html`<ul class="chw-fine">${r.caveats.map((x) => html`<li>${clean(x)}</li>`)}</ul>` : ''}
      </details>`;
  },

  options() {
    const p = payload(); if (p.wait) return p.wait;
    const t = p.t, g = t.gex || {}, sym = C.sym(), spot = isNum(g.spot) ? Number(g.spot) : Number((t.quote || {}).price), rows = [];
    if (!g.error) {
      if ((g.regime || {}).state) rows.push(['Gamma regime', capFirst(g.regime.state)]);   // regime is {state, note}
      if (isNum((g.totals || {}).net_gex)) rows.push(['Net GEX', dollars(g.totals.net_gex)]);
      // gex.levels is a dict of named levels, not a list
      [['call_wall', 'Call wall'], ['put_wall', 'Put wall'], ['gamma_pin', 'Gamma pin'], ['max_oi_strike', 'Most open interest']].forEach(([k, label]) => {
        const l = (g.levels || {})[k]; if (!l || !isNum(l.strike)) return;
        const d = isNum(l.distance_pct) ? l.distance_pct : spot ? ((l.strike - spot) / spot) * 100 : null;
        rows.push([label, `${num(l.strike)}${isNum(d) ? ` (${signed(d, 1)})` : ''}`]);
      });
    }
    const atm = ((t.greeks || {}).atm_greeks || []).find((x) => x && x.call && isNum(x.call.iv));
    if (atm) rows.push([`ATM IV, ${num(atm.dte, 0)} days`, `${num(atm.call.iv * 100, 1)}%`]);
    if (!rows.length) return html`${none('No option chain for this symbol.')}${more(`#/${sym}/options`, `Options for ${sym}`)}`;
    const note = String((g.regime || {}).note || ''), cut = note.indexOf('. ');
    return html`${kv(rows)}${note ? fine(clean(cut > 0 ? note.slice(0, cut + 1) : note)) : ''}${more(`#/${sym}/options`, `Options for ${sym}`)}`;
  },

  levels() {
    const p = payload(); if (p.wait) return p.wait;
    const te = p.t.technicals || {}, lv = (te.support_resistance || []).slice(0, 9), spot = Number(te.spot);
    if (!lv.length) return none('No levels found.');
    return html`<div class="tscroll"><table class="t chw-table"><thead><tr><th class="num">Level</th><th>Role</th><th class="num">Away</th><th class="num">Strength</th></tr></thead>
      <tbody>${lv.map((l) => html`<tr><td class="num">${num(l.price)}</td><td class="${l.role === 'resistance' ? 'down' : 'up'}">${capFirst(l.role || '')}</td><td class="num">${signed(isNum(l.distance_pct) ? l.distance_pct : spot ? ((l.price - spot) / spot) * 100 : null, 1)}</td><td class="num">${num(l.strength, 0)}</td></tr>`)}</tbody></table></div>
      <label class="check chw-show"><input type="checkbox" data-chw-sr ${C.overlayOn('sr') ? 'checked' : ''}> <span>Show on the chart</span></label>`;
  },

  stats() {
    const p = payload(); if (p.wait) return p.wait;
    const q = p.t.quote || {}, ph = C.phase();
    // "today" only while it is: before the open and overnight the day's figures are the last session's
    const day = ph === 'regular' || ph === 'after' ? 'today' : ph ? 'last session' : 'latest session';
    const rows = [['Open price', q.open, money], [`High ${day}`, q.day_high, money], [`Low ${day}`, q.day_low, money], ['Volume', q.volume, compact], ['Average volume', q.avg_volume, compact], ['52-week high', q.fifty_two_high, money], ['52-week low', q.fifty_two_low, money]]
      .filter(([, v]) => isNum(v)).map(([k, v, f]) => [k, f(v)]);
    return rows.length ? kv(rows) : none('The feed has no statistics for this symbol.');
  },

  patterns() {
    const p = payload(); if (p.wait) return p.wait;
    const pat = p.t.patterns || {}, chart = (pat.chart_patterns || []).slice(0, 4), candles = (pat.candles || []).slice(0, 4);
    if (pat.available === false || (!chart.length && !candles.length)) return none('Nothing detected.');
    return html`${chart.length ? html`<h4 class="chw-sub">Chart patterns</h4><ul class="chw-list">${chart.map((x) => html`<li><p class="chw-line"><b>${x.name || ''}</b> <small class="t-muted">${x.confirmed ? `confirmed ${shortDate(x.confirmed_on)}` : 'not confirmed'}</small></p><small class="t-muted">${x.start_date ? `${fullDate(x.start_date)} to ${fullDate(x.end_date)}. ` : ''}${x.conventional ? `Read as ${clean(x.conventional)}.` : ''}</small></li>`)}</ul>` : ''}
      ${candles.length ? html`<h4 class="chw-sub">Candles</h4><ul class="chw-list">${candles.map((c) => html`<li><p class="chw-line"><b>${c.name || ''}</b> <small class="t-muted">${shortDate(c.date)}${c.direction ? `, ${c.direction}` : ''}</small></p>${c.conventional ? html`<small class="t-muted">${capFirst(clean(c.conventional))}.</small>` : ''}</li>`)}</ul>` : ''}
      ${fine('Directions shown are the conventional reading of each pattern, not a measurement.')}`;
  },

  /* Two related stocks' spread: how stretched it is now, and whether trading it back has worked on years
   * the pair was not fitted to (app/analytics/pairs.py). */
  pairs() {
    const sym = C.sym(), b = PR.peer[sym] || '', pe = S.peers;
    const sugg = pe && pe.available ? (pe.peers || []).slice(0, 6) : [];
    const controls = html`<form class="chw-add chw-pairform" data-chw-pairform><label class="chw-field"><span>Pair ${sym} with</span><input name="b" value="${b}" placeholder="Symbol" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="12"></label><button type="submit" class="btn btn-sm">Test</button></form>
      ${sugg.length ? html`<div class="chw-sugg"><span class="chw-fine">Moved most alike:</span> ${sugg.map((x) => html`<button type="button" class="chip" data-chw-pick="${x.symbol}" aria-pressed="${x.symbol === b}" title="${x.name || x.symbol}: correlation ${num(x.corr, 2)}">${x.symbol}</button>`)}</div>` : ''}`;
    if (!b) return html`${controls}${none('Pick a second stock: one with the same products, customers or market.')}`;
    if (S.prErr) return html`${controls}${failed('The pairs test', S.prErr, { retry: 'w-pairs' })}`;
    const r = S.pr;
    if (r === undefined || S.prKey !== `${sym}/${b}`) return html`${controls}${skeleton('lines', 4, 'Testing the pair')}`;
    if (!r) return controls;
    if (r.available === false) return html`${controls}${none(clean(r.reason || 'No result.'))}`;
    const now = r.now || {}, wf = r.walk_forward || {}, al = wf.all || {}, ct = wf.coint_only || {}, lvl = now.coint_level, pa = r.params || {};
    const book = (bk, lab) => tile(signed(bk.total_return_pct, 0), tone(bk.total_return_pct), lab, `${num(bk.trades || 0, 0)} trades${isNum(bk.win_rate_pct) ? `, ${num(bk.win_rate_pct, 0)}% won` : ''}${isNum(bk.beats_random_pct) ? `, beat ${num(bk.beats_random_pct, 0)}% of random` : ''}`);
    return html`${controls}<p class="chw-line"><b>${sym} / ${b}</b> <span class="t-muted">spread ${isNum(now.z) ? `${now.z > 0 ? '+' : now.z < 0 ? '−' : ''}${num(Math.abs(now.z), 1)}σ` : 'n/a'}</span></p>
      <p class="chw-verdict">${clean(now.stance || '')}</p>
      ${zSvg(r.z_history, pa.entry_z || 2)}
      ${fine(`Spread in standard deviations over the last year, with lines at ±${num(pa.entry_z || 2, 1)}, where the rule enters.`)}
      ${kv([['A pair?', lvl ? `Cointegrated at ${num(lvl * 100, 0)}% over the last year` : 'Not cointegrated over the last year (no evidence the gap comes back)'],
        ['Hedge', now.beta > 0 ? `${num(now.beta, 2)} of ${b} for each 1 of ${sym}` : `None: the ratio is ${num(now.beta, 2)}, the two moved apart`],
        ['Half-life', isNum(now.half_life) ? `${num(now.half_life, 0)} sessions for a gap to halve` : 'n/a'],
        ['Correlation', `${num(now.corr, 2)} (daily returns)`]])}
      <h4 class="chw-sub">Out of sample, ${num(wf.years_traded || 0, 0)} years</h4>
      <div class="chw-tiles">${book(al, 'Every window')}${book(ct, 'Only when it tested as a pair')}</div>
      <p class="chw-verdict">${clean(r.verdict || '')}</p>
      ${fine(`Tested as a pair in ${num(wf.coint_share_pct || 0, 0)}% of formation years${isNum(wf.stayed_coint_pct) ? `, and still did in the next half-year ${num(wf.stayed_coint_pct, 0)}% of the time` : ''}.`)}
      ${miloButton('Ask Milo about this pair', { ask: `Explain the pairs test of ${sym} and ${b}: the spread is ${now.z} standard deviations from its average, ${lvl ? `cointegrated at ${lvl * 100}%` : 'not cointegrated'} over the last year; out of sample, every window ${al.trades} trades ${signed(al.total_return_pct, 0)}, only when cointegrated ${ct.trades} trades ${signed(ct.total_return_pct, 0)}. Is this a real pair, and what would make me trust the trade?`, context: `${sym} Chart, Pairs`, symbol: sym, cls: 'btn-sm' })}
      <details class="chw-details"><summary>How this is tested</summary>
        ${fine(`${clean(r.method || '')} Enter at |z| ${num(pa.entry_z, 1)}, exit at ${num(pa.exit_z, 1)}, stop at ${num(pa.stop_z, 1)}, give up after three half-lives.`)}
        ${(r.caveats || []).length ? html`<ul class="chw-fine">${r.caveats.map((x) => html`<li>${clean(x)}</li>`)}</ul>` : ''}
      </details>`;
  },

  /* One strategy's record on this symbol, always beside buy and hold over the same window and random
   * entries with the same exposure (app/analytics/backtest.py). */
  backtest() {
    const sym = C.sym();
    if (G.catErr) return failed('The strategies', G.catErr, { retry: 'w-backtest' });
    if (!G.cat) return skeleton('lines', 3, 'Loading the strategies');
    const s = btStrategy(), all = G.cat.timeframes || {}, tfs = btTimeframes(s).filter((k) => all[k]);
    const periods = BT.timeframe === '1d' ? [[1, '1 year'], [2, '2 years'], [5, '5 years'], [10, '10 years'], [0, 'All history']]
      : BT.timeframe === '5m' ? [[0, 'Last 60 sessions']] : [[1, '1 year'], [2, '2 years'], [0, 'All available (about 3 years)']];
    const controls = html`<div class="chw-fields">
      <label class="chw-field chw-wide"><span>Strategy</span><select data-chw-bt="strategy">${(G.cat.strategies || []).map((x) => html`<option value="${x.id}" ${x.id === BT.strategy ? 'selected' : ''}>${x.label}</option>`)}</select></label>
      <label class="chw-field"><span>Bars</span><select data-chw-bt="timeframe">${tfs.map((k) => html`<option value="${k}" ${k === BT.timeframe ? 'selected' : ''}>${all[k].label}</option>`)}</select></label>
      <label class="chw-field"><span>Period</span><select data-chw-bt="years">${periods.map(([v, l]) => html`<option value="${v}" ${Number(BT.years || 0) === v ? 'selected' : ''}>${l}</option>`)}</select></label></div>
      ${s ? html`${fine(clean(s.summary || ''))}<details class="chw-details"><summary>Rules</summary><div class="chw-fields">${btParams(s)}</div><button type="button" class="btn btn-sm" data-chw-btrun>Run again</button></details>` : ''}`;
    if (S.btErr) return html`${controls}${failed('The backtest', S.btErr, { retry: 'w-backtest' })}`;
    const r = S.bt;
    if (r === undefined) return html`${controls}${skeleton('lines', 4, 'Testing')}`;
    if (!r) return controls;
    if (r.available === false) return html`${controls}${none(clean(r.reason || 'No result.'))}`;
    const st = r.stats || {}, bm = r.benchmark || {}, w = r.window || {}, session = r.engine === 'session', intraday = (w.timeframe || '1d') !== '1d', pb = bm.plain_break || null;
    const span = session ? `in ${num(w.sessions || 0, 0)} sessions` : `over ${num(w.years || 0, 1)} years`;
    const ci = st.win_rate_ci95 || [];
    return html`${controls}<p class="chw-line"><b>${r.ticker}</b> <span class="t-muted">${num(st.trades || 0, 0)} trades ${span}, ${clean(w.timeframe_label || '')}</span></p>
      <div class="chw-tiles">
        ${tile(signed(st.total_return_pct, 0), tone(st.total_return_pct), 'Return', `Buy and hold ${signed(bm.buy_hold_return_pct, 0)}`)}
        ${tile(pct0(st.win_rate_pct), '', 'Win rate', isNum(ci[0]) ? `95% range ${num(ci[0], 0)} to ${num(ci[1], 0)}%` : '')}
        ${tile(isNum(st.reward_risk) ? num(st.reward_risk, 2) : 'n/a', '', 'Reward / risk', `Average win ${signed(st.avg_win_pct, 1)}, loss ${signed(st.avg_loss_pct, 1)}`)}
        ${tile(signed(st.max_drawdown_pct, 0), 'down', 'Max drawdown', `Buy and hold ${signed(bm.buy_hold_max_drawdown_pct, 0)}`)}
      </div>
      <p class="chw-verdict">${clean(r.verdict || '')}</p>
      ${isNum(bm.beats_random_pct) ? fine(`Beat ${num(bm.beats_random_pct, 0)}% of ${num(bm.random_runs, 0)} ${session ? 'books with the same trades entered at random times on the same days' : 'random-entry books with the same number of trades and holding periods'} (median ${signed(bm.random_median_pct, session ? 1 : 0)}).`) : ''}
      ${pb ? fine(`The plain break, entering on the first close outside the range with the same exits: ${num(pb.trades || 0, 0)} trades, ${signed(pb.total_return_pct, 1)}${isNum(pb.win_rate_pct) ? `, ${num(pb.win_rate_pct, 0)}% winners` : ''}.`) : ''}
      ${curveSvg(r.equity)}
      <p class="chw-key"><span><i class="st"></i>Strategy</span><span><i class="bh"></i>Buy and hold</span><span>Growth of $1, log scale, ${shortDate(w.from)} ${String(w.from || '').slice(0, 4)} to ${shortDate(w.to)} ${String(w.to || '').slice(0, 4)}</span></p>
      <label class="check chw-show"><input type="checkbox" data-chw-btshow ${BT.show ? 'checked' : ''}> <span>Show trades on the chart</span></label>
      ${(r.trades || []).length || r.open_trade ? html`<div class="tscroll"><table class="t chw-table"><thead><tr><th>${session ? 'In' : 'Bought'}</th><th>${session ? 'Out' : 'Sold'}</th><th class="num">Return</th></tr></thead><tbody>
        ${r.open_trade ? html`<tr><td>${when(r.open_trade.entry_date, intraday)}</td><td>Open</td><td class="num ${tone(r.open_trade.unrealised_pct)}">${signed(r.open_trade.unrealised_pct, 1)}</td></tr>` : ''}
        ${(r.trades || []).slice(-6).reverse().map((x) => html`<tr title="${x.exit_reason || ''}"><td>${x.side === 'short' ? 'Short ' : ''}${when(x.entry_date, intraday)}</td><td>${session ? String(x.exit_date).slice(11, 16) : when(x.exit_date, intraday)}</td><td class="num ${tone(x.return_pct)}">${signed(x.return_pct, 1)}</td></tr>`)}
      </tbody></table></div>` : ''}
      ${miloButton('Ask Milo about this test', { ask: `Explain this backtest of ${s ? s.label : 'the strategy'} on ${r.ticker} (${w.timeframe_label}, ${w.from} to ${w.to}): ${st.trades} trades ${span}, ${signed(st.total_return_pct, 0)} against buy and hold ${signed(bm.buy_hold_return_pct, 0)}, win rate ${num(st.win_rate_pct || 0, 0)}%, max drawdown ${signed(st.max_drawdown_pct, 0)}, beat ${num(bm.beats_random_pct || 0, 0)}% of random-entry books. Is the rule adding anything, and what would make the result more convincing?`, context: `${sym} Chart, Backtest`, symbol: sym, cls: 'btn-sm' })}
      <details class="chw-details"><summary>How this is tested</summary>
        ${fine(`${clean(r.fill || '')} ${session ? `${capFirst(r.sides || 'long and short')}, one trade a session` : 'Long only'}, fully invested, returns compounded, ${num(r.cost_bps || 0, 0)} basis points a side for costs. ${clean(w.timeframe_note || '')} ${clean(bm.random_method || '')}`)}
        ${(r.caveats || []).length ? html`<ul class="chw-fine">${r.caveats.map((x) => html`<li>${clean(x)}</li>`)}</ul>` : ''}
      </details>`;
  },

  trading() {
    if (G.trackerErr) return failed('Optic Portfolio', G.trackerErr, { retry: 'w-trading' });
    const tr = G.tracker;
    if (!tr) return skeleton('lines', 3, 'Loading Optic Portfolio');
    const sym = C.sym(), s = tr.summary || {}, mine = (tr.open || []).filter((x) => x.ticker === sym);
    return html`${kv([['Equity', money(s.equity, 0)], ['Open', num(s.open_count, 0)], ['Return', html`<span class="${tone(s.return_pct)}">${signed(s.return_pct, 2)}</span>`]])}
      ${fine(mine.length ? `Holding ${sym}: ${mine.map((x) => `${num(x.qty, 0)} ${x.instrument === 'option' ? 'contracts' : 'shares'} at ${num(x.entry_price)}`).join('; ')}.` : `No position in ${sym}.`)}
      ${fine(`The ${clean(s.book || 'balanced')} book of Optic Portfolio: Optic's own paper trades, made by its rule sets, the same for everyone and never real money.`)}
      ${more('#/portfolio', 'Open Optic Portfolio')}`;
  },

  learn() {
    const terms = Object.keys(GLOSSARY).sort(), word = GLOSSARY[G.learn] ? G.learn : terms[0];
    return html`<label class="select chw-sel"><span class="sr">Term</span><select data-chw-learn>${terms.map((x) => html`<option value="${x}" ${x === word ? 'selected' : ''}>${termName(x)}</option>`)}</select></label>
      <p class="chw-def" data-chw-def aria-live="polite">${GLOSSARY[word]}</p>
      ${fine(`${terms.length} terms.`)}`;
  },
};
// The glossary's keys are lower case for matching; a term is shown as it is written ("ATM", "Forward P/E").
const ACRONYM = new Set(['0dte', 'atm', 'atr', 'cagr', 'dte', 'ebitda', 'ema', 'eps', 'gex', 'itm', 'iv', 'macd', 'oi', 'otm', 'p/e', 'p&l', 'r1', 'r2', 'rsi', 'rvol', 's1', 's2', 'sma', 'vwap']);
export const termName = (t) => capFirst(String(t).split(' ').map((w) => (ACRONYM.has(w) ? w.toUpperCase() : w === 'yoy' ? 'YoY' : w)).join(' '));
// What the arrows on the chart stand for, and how far back they go, under a switch for them.
function spanLine(t) {
  const sp = insiderSpan(t);
  if (!sp.n) return '';
  return html`<label class="check chw-show"><input type="checkbox" data-chw-ins ${C.overlayOn('ins') ? 'checked' : ''}> <span>Show on the chart</span></label>
    ${fine(sp.marked ? `The chart marks the ${[sp.buys ? `${sp.buys} purchase${sp.buys === 1 ? '' : 's'}` : '', sp.sells ? `${sp.sells} sale${sp.sells === 1 ? '' : 's'}` : ''].filter(Boolean).join(' and ')} among the ${sp.n} filings Optic has from the last two years, ${fullDate(sp.from)} to ${fullDate(sp.to)}: a green arrow under the bar for a purchase, a red one over it for a sale. Point at or tap one to see the trade.` : `None of the ${sp.n} filings Optic has from the last two years is a purchase or a sale, so the chart has nothing to mark.`)}`;
}
const checkCount = (n, sym) => `${n} of ${CHECKS.length} for ${sym}. Fixed questions on purpose. A checklist you can edit becomes a list of the questions you already like the answers to.`;

/* ---------------- stop check ---------------- */
// Entry and stop are per symbol; the stop starts from the entry plan's when there is one, since that is
// the stop this app already proposes.
function scInputs() {
  const sym = C.sym(), t = C.t() || {}, q = t.quote || {};
  const entry = Number(SC.entry[sym]) > 0 ? Number(SC.entry[sym]) : isNum(q.price) ? Number(q.price) : null;
  const plan = ((t.entry_plan || {}).risk || {}).underlying_stop, typed = Number(SC.stop[sym]) > 0;
  const stop = typed ? Number(SC.stop[sym]) : isNum(plan) ? Number(plan) : null;
  return { entry, stop, fromPlan: !typed && stop !== null };
}
function runStop() {
  if (!C.t()) return;
  const sym = C.sym(), { entry, stop } = scInputs();
  if (!(stop > 0)) { S.sc = null; S.scKey = null; return; }
  const qs = new URLSearchParams({ stop: String(stop), buffer: String(SC.buffer) });
  if (entry > 0) qs.set('entry', String(entry));
  if (Number(SC.account) > 0) { qs.set('account', String(SC.account)); qs.set('risk_pct', String(SC.riskPct || 1)); }
  const key = qs.toString(), box = S;
  if (box.scKey === key) return;
  box.scKey = key; box.sc = undefined; box.scErr = null;
  api.get(`/api/stop-check/${encodeURIComponent(sym)}?${key}`, { ttl: 300000, timeout: 45000 })
    .then((r) => { if (box.scKey === key) box.sc = r; }, (e) => { if (box.scKey === key) { box.sc = null; box.scErr = e; } })
    .finally(() => { if (S === box && box.scKey === key) { C.repaint('stopcheck'); C.chart(); } });
}

/* ---------------- pairs ---------------- */
function runPair() {
  const sym = C.sym(), b = PR.peer[sym];
  if (!b) return;
  const key = `${sym}/${b}`, box = S;
  if (box.prKey === key) return;
  box.prKey = key; box.pr = undefined; box.prErr = null;
  api.get(`/api/pairs/${encodeURIComponent(sym)}?b=${encodeURIComponent(b)}`, { ttl: 600000, timeout: 60000 })
    .then((r) => { if (box.prKey === key) box.pr = r; }, (e) => { if (box.prKey === key) { box.pr = null; box.prErr = e; } })
    .finally(() => { if (S === box && box.prKey === key) C.repaint('pairs'); });
}
function setPeer(v) {
  const sym = C.sym(), b = String(v || '').toUpperCase().trim().replace(/[^A-Z0-9.^=-]/g, '');
  if (b === sym) { toast(`Pick a symbol other than ${sym}.`); return; }
  if (b) PR.peer[sym] = b; else delete PR.peer[sym];
  writeKey(KEY.pairs, { peer: PR.peer });
  C.repaint('pairs'); runPair();
}
// The spread's z-score over the formation year, with the entry lines.
function zSvg(rows, entry) {
  if (!rows || rows.length < 2) return '';
  const W = 268, H = 80, pad = 4, vals = rows.map((r) => r.z), top = Math.max(entry + 0.5, ...vals.map(Math.abs));
  const x = (i) => pad + (i / (rows.length - 1)) * (W - 2 * pad), y = (v) => H / 2 - (v / top) * (H / 2 - pad);
  const line = (v, cls) => `<line x1="${pad}" x2="${W - pad}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" class="${cls}"/>`;
  return raw(`<svg class="chw-spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="Spread z-score over the last year, now ${num(vals[vals.length - 1], 1)}">${line(0, 'zero')}${line(entry, 'band')}${line(-entry, 'band')}<path d="${rows.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(r.z).toFixed(1)}`).join('')}" class="st"/></svg>`);
}

/* ---------------- backtest ---------------- */
const btStrategy = () => ((G.cat || {}).strategies || []).find((s) => s.id === BT.strategy) || null;
// Each rule says which bars it runs on: switching rule moves the bar size to one the new rule takes.
const btTimeframes = (s) => (s && Array.isArray(s.timeframes) && s.timeframes.length ? s.timeframes : ['1d', '4h', '1h']);
function btFix() { const tfs = btTimeframes(btStrategy()); if (!tfs.includes(BT.timeframe)) BT.timeframe = tfs[0]; }
const btSave = () => writeKey(KEY.bt, { strategy: BT.strategy, timeframe: BT.timeframe, years: BT.years, params: BT.params, show: BT.show });
function runBacktest(force) {
  const box = S;
  if (G.cat === undefined) {
    if (!G.catBusy) {
      G.catBusy = true; G.catErr = null;
      api.get('/api/backtest/strategies', { ttl: 3600000, timeout: 30000 }).then((r) => { G.cat = r; if (!btStrategy() && (r.strategies || []).length) BT.strategy = r.strategies[0].id; }, (e) => { G.catErr = e; G.cat = null; })
        .finally(() => { G.catBusy = false; if (S === box) { C.repaint('backtest'); if (G.cat) runBacktest(); } });
    }
    return;
  }
  if (!G.cat) return;
  btFix();
  const sym = C.sym(), key = JSON.stringify([sym, BT.strategy, BT.timeframe, BT.years, BT.params[BT.strategy] || {}]);
  if (!force && box.btKey === key) return;
  box.btKey = key; box.bt = undefined; box.btErr = null;
  const qs = new URLSearchParams({ strategy: BT.strategy, timeframe: BT.timeframe });
  if (BT.years) qs.set('years', String(BT.years));
  Object.entries(BT.params[BT.strategy] || {}).forEach(([k, v]) => qs.set(k, String(v)));
  C.repaint('backtest');
  api.get(`/api/backtest/${encodeURIComponent(sym)}?${qs}`, { ttl: force ? 0 : 600000, force: !!force, timeout: 90000 })
    .then((r) => { if (box.btKey === key) box.bt = r; }, (e) => { if (box.btKey === key) { box.bt = null; box.btErr = e; } })
    .finally(() => { if (S === box && box.btKey === key) { C.repaint('backtest'); C.chart(); } });
}
function btParams(s) {
  const cur = BT.params[s.id] || {};
  return (s.params || []).map((p) => {
    const v = cur[p.id] !== undefined ? cur[p.id] : p.default;
    if (p.kind === 'bool') return html`<label class="check chw-wide"><input type="checkbox" data-chw-btp="${p.id}" ${v ? 'checked' : ''}> <span>${p.label}</span></label>`;
    const float = p.kind === 'float';
    return html`<label class="chw-field"><span>${p.label}</span><input type="number" data-chw-btp="${p.id}" value="${v}" min="${p.min}" max="${p.max}" step="${float ? (p.step || 0.1) : 1}" inputmode="${float ? 'decimal' : 'numeric'}"></label>`;
  });
}
// A trade's time as the table shows it: the date for daily bars, the date and time for intraday ones.
const when = (stamp, intraday) => { const s = String(stamp || ''); return intraday ? `${shortDate(s)} ${s.slice(11, 16)}` : fullDate(s); };
// The equity curve against buy and hold, on a log scale so a tenfold move and a doubling read as what they are.
function curveSvg(rows) {
  if (!rows || rows.length < 2) return '';
  const W = 268, H = 92, pad = 4, vals = rows.flatMap((r) => [r.strategy, r.buy_hold]).filter((v) => v > 0);
  const lo = Math.log(Math.min(...vals)), hi = Math.log(Math.max(...vals));
  const y = (v) => H - pad - ((Math.log(v) - lo) / ((hi - lo) || 1)) * (H - 2 * pad), x = (i) => pad + (i / (rows.length - 1)) * (W - 2 * pad);
  const path = (k) => rows.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(r[k] > 0 ? r[k] : 1).toFixed(1)}`).join('');
  return raw(`<svg class="chw-spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="Growth of 1 dollar: the strategy against buy and hold, log scale"><line x1="${pad}" x2="${W - pad}" y1="${y(1).toFixed(1)}" y2="${y(1).toFixed(1)}" class="zero"/><path d="${path('buy_hold')}" class="bh"/><path d="${path('strategy')}" class="st"/></svg>`);
}

/* ---------------- what the open widgets draw on the price ---------------- */
/**
 * A trade's stamp ('2024-05-01', or '2024-05-01 10:25' in New York time) to the time of the bar it falls on:
 * the same minute on an intraday chart, its day's first bar for a daily trade there, its day on a daily
 * chart and its week on a weekly one. Null when no bar in the series holds it.
 */
const NY = typeof Intl !== 'undefined' ? new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) : null;
export function barKey(t, intraday) {
  if (!intraday || !NY) return new Date(t).toISOString().slice(0, 10);
  const p = {}; NY.formatToParts(new Date(t)).forEach((x) => { p[x.type] = x.value; });
  return `${p.year}-${p.month}-${p.day} ${p.hour === '24' ? '00' : p.hour}:${p.minute}`;
}
export function barTime(bars, keys, stamp, { intraday = false, weekly = false, within = 0 } = {}) {
  const s = String(stamp || '').replace('T', ' ').slice(0, 16);
  if (!s || !bars.length) return null;
  if (intraday && s.length === 10) { const i = keys.findIndex((k) => k.slice(0, 10) === s); return i < 0 ? null : bars[i].t; }
  const want = intraday ? s : s.slice(0, 10);
  let lo = 0, hi = keys.length - 1, at = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (keys[m] <= want) { at = m; lo = m + 1; } else hi = m - 1; }
  if (at < 0) return null;
  if (weekly) return Date.parse(want.slice(0, 10)) - Date.parse(keys[at].slice(0, 10)) < 7 * 86400000 ? bars[at].t : null;
  if (keys[at].slice(0, 10) === want.slice(0, 10)) return bars[at].t;
  return within && !intraday && Date.parse(want.slice(0, 10)) - Date.parse(keys[at].slice(0, 10)) <= within * 86400000 ? bars[at].t : null;
}
/**
 * The insider trades the chart marks, from the ticker payload's filings of the last two years (company.ownership.
 * recent_transactions). Only purchases and sales: "other" is option exercises, grants and gifts, which are
 * pay rather than a view on the price, as the classic chart's insider marks have it. Each carries the words
 * for its hover box; the date is the trade's own, not its bar's (a weekly bar holds five days).
 */
export function insiderMarks(t) {
  return (((((t || {}).company || {}).ownership || {}).recent_transactions) || []).map((x) => {
    const a = String(x.action || '').toLowerCase(), side = a === 'purchase' ? 'buy' : a === 'sale' ? 'sell' : null, date = String(x.date || '').slice(0, 10);
    if (!side || !/^\d{4}-\d\d-\d\d$/.test(date)) return null;
    const amount = [isNum(x.shares) ? `${shares(x.shares)} shares` : '', isNum(x.value) && Number(x.value) ? `$${compact(x.value)}` : ''].filter(Boolean).join(', ');
    return { at: date, side, date: fullDate(date), value: Number(x.value) || 0, who: clean(x.insider || 'An insider'), role: clean(x.position || ''), amount, note: clean(x.detail || '') };
  }).filter(Boolean);
}
/** What the Insiders panel says the chart covers: the filings in the payload, and their span. */
function insiderSpan(t) {
  const tx = ((((t || {}).company || {}).ownership || {}).recent_transactions) || [], dates = tx.map((x) => String(x.date || '').slice(0, 10)).filter(Boolean).sort();
  const m = insiderMarks(t);
  return { n: tx.length, from: dates[0], to: dates[dates.length - 1], marked: m.length, buys: m.filter((x) => x.side === 'buy').length, sells: m.filter((x) => x.side === 'sell').length };
}

/** The backtest's fills as markers and the stop check's lines, for the widgets that are showing. */
export function onChart(shown) {
  const marks = [], lines = [];
  if (!C) return { marks, lines };
  const bt = S.bt;
  if (shown.includes('backtest') && BT.show && bt && bt.available === true && bt.ticker === C.sym()) {
    (bt.trades || []).forEach((x) => {
      const short = x.side === 'short';
      marks.push({ at: x.entry_date, kind: short ? 'S' : 'B', tone: short ? 'neg' : 'pos', label: `${short ? 'Sold short' : 'Bought'} ${x.entry_date} at ${num(x.entry_price)}: ${x.entry_reason || ''}` });
      marks.push({ at: x.exit_date, kind: short ? 'B' : 'S', tone: x.return_pct >= 0 ? 'pos' : 'neg', label: `${short ? 'Bought back' : 'Sold'} ${x.exit_date} at ${num(x.exit_price)}, ${signed(x.return_pct, 1)} after ${x.bars} candles: ${x.exit_reason || ''}` });
    });
    if (bt.open_trade) marks.push({ at: bt.open_trade.entry_date, kind: 'B', tone: 'pos', label: `Bought ${bt.open_trade.entry_date}, still held: ${bt.open_trade.entry_reason || ''}` });
  }
  const r = S.sc;
  if (shown.includes('stopcheck') && SC.show && r && r.available === true) {
    // three lines a dollar or two apart: the stop labelled over its line, the buffered stop (further from the
    // price) under it for a long and over it for a short, the round number at the right, or not at all when the stop is on it
    const long = r.side !== 'short', on = r.round_level && Math.abs(r.round_level.price - r.stop) < 0.005;
    lines.push({ price: r.stop, cls: 'stop', label: on ? `Stop ${num(r.stop)}, on the round number` : `Stop ${num(r.stop)}`, below: !long });
    if (r.moved) lines.push({ price: r.adjusted_stop, cls: 'stopb', label: `Buffered ${num(r.adjusted_stop)}`, below: long });
    if (r.round_level && !on) lines.push({ price: r.round_level.price, cls: 'round', label: `Round ${num(r.round_level.price, 0)}`, end: true });
  }
  return { marks, lines };
}

/** What Milo is told about the open widgets: their names, and the figures of the three that compute. */
export function context(shown) {
  if (!C || !shown.length) return undefined;
  const out = { open: shown.map((id) => byId(id).label) };
  const bt = S.bt, sc = S.sc, pr = S.pr;
  if (shown.includes('backtest') && bt && bt.available === true) out.backtest = { strategy: (btStrategy() || {}).label, window: bt.window, stats: pick(bt.stats || {}, ['trades', 'total_return_pct', 'win_rate_pct', 'max_drawdown_pct', 'reward_risk']), buy_hold_return_pct: (bt.benchmark || {}).buy_hold_return_pct, beats_random_pct: (bt.benchmark || {}).beats_random_pct, verdict: bt.verdict };
  if (shown.includes('stopcheck') && sc && sc.available === true) out.stop_check = pick(sc, ['side', 'entry', 'stop', 'adjusted_stop', 'moved', 'atr', 'risk_per_share', 'text']);
  if (shown.includes('pairs') && pr && pr.available === true) out.pairs = { a: pr.a, b: pr.b, now: pr.now, verdict: pr.verdict };
  return out;
}

/* ---------------- the rail and the panels ---------------- */
export function rail(shown, horizontal) {
  const first = Math.max(0, IDS.findIndex((id) => shown.includes(id)));
  return html`<div class="chw-rail" role="toolbar" aria-label="Widgets" aria-orientation="${horizontal ? 'horizontal' : 'vertical'}">${WIDGETS.map((w, i) => html`<button type="button" class="chw-btn" data-chw="${w.id}" aria-pressed="${shown.includes(w.id)}" aria-label="${w.label}" title="${w.label}" tabindex="${i === first ? '0' : '-1'}">${mark(w)}<span class="chw-lab">${w.short || w.label}</span></button>`)}</div>`;
}
export function panel(id) {
  const w = byId(id);
  if (!w) return '';
  return html`<section class="chw" id="chw-${id}" data-chw-panel="${id}" aria-labelledby="chw-${id}-h"><header class="chw-head"><h3 class="chw-t" id="chw-${id}-h">${mark(w)}<span>${w.label}</span></h3><button type="button" class="ch-tool chw-close" data-chw-close="${id}" aria-label="Close ${w.label}" title="Close">${icon('close')}</button></header><div class="chw-body" id="chw-${id}-b">${body(id)}</div></section>`;
}
/** One widget's contents. A fault in one is kept to that one, not the column. */
export function body(id) {
  try { return BODY[id] ? BODY[id]() : ''; } catch (e) { console.error(e); return none('This panel could not be drawn from the figures that arrived.'); }
}
export const label = (id) => (byId(id) || {}).label || id;

/** Save a note still being typed (before a redraw, a symbol change or leaving the page). */
export function flush(root = document) {
  const el = root.querySelector && root.querySelector('[data-chw-note]');
  if (el && !el.disabled) saveNote(el);
}
function saveNote(el) {
  const sym = el.dataset.chwNote, all = readKey(KEY.notes), text = el.value;
  if ((all[sym] || '') === text) return;
  if (text.trim()) all[sym] = text; else delete all[sym];
  writeKey(KEY.notes, all);
}

/* ---------------- events (from the page's own listeners; true when handled) ---------------- */
export function onClick(e) {
  const t = (s) => e.target.closest(s);
  let b;
  if ((b = t('[data-chw-unwatch]'))) {
    const s = b.dataset.chwUnwatch, id = store.state.activeId, L = store.activeList();
    store.unfollow(s, id).then(() => toast(`${s} removed from ${L ? L.name : 'your watchlist'}.`, { action: 'Undo', run: () => store.follow(s, id).catch(() => {}) }), (err) => toast(api.explain(err, 'The change'), { kind: 'bad' }));
    return true;
  }
  if ((b = t('[data-chw-watchadd]'))) { follow(b.dataset.chwWatchadd); return true; }
  if (t('[data-chw-btrun]')) { runBacktest(true); return true; }
  if ((b = t('[data-chw-pick]'))) { setPeer(b.dataset.chwPick); return true; }
  return false;
}
function follow(s) {
  const L = store.activeList();
  store.follow(s, store.state.activeId).then(() => toast(`${s} added to ${(store.activeList() || L || {}).name || 'your watchlist'}.`), (err) => toast(err && err.kind === 'limit' && err.message ? err.message : api.explain(err, 'The change'), { kind: 'bad' }));
}
export function onChange(e) {
  const el = e.target, sym = C.sym();
  if (el.matches('[data-chw-note]')) { saveNote(el); return true; }
  if (el.matches('[data-chw-list]')) { store.setActive(el.value); return true; }
  if (el.matches('[data-chw-check]')) {
    const all = readKey(KEY.checks), on = new Set(all[sym] || []), i = Number(el.dataset.chwCheck);
    if (el.checked) on.add(i); else on.delete(i);
    all[sym] = [...on];
    if (!writeKey(KEY.checks, all)) { el.checked = !el.checked; return true; }
    const n = el.closest('.chw-body').querySelector('[data-chw-checkn]'); if (n) n.textContent = checkCount(on.size, sym);
    return true;
  }
  if (el.matches('[data-chw-sc]')) {
    const k = el.dataset.chwSc;
    if (k === 'entry' || k === 'stop') SC[k][sym] = el.value === '' ? '' : Number(el.value);
    else if (k === 'buffer') SC.buffer = Number(el.value);
    else if (k === 'account') SC.account = el.value === '' ? '' : Number(el.value);
    writeKey(KEY.stop, pick(SC, ['entry', 'stop', 'buffer', 'account', 'riskPct', 'show']));
    runStop(); C.repaint('stopcheck'); C.chart();
    return true;
  }
  if (el.matches('[data-chw-scshow]')) { SC.show = el.checked; writeKey(KEY.stop, pick(SC, ['entry', 'stop', 'buffer', 'account', 'riskPct', 'show'])); C.chart(); return true; }
  if (el.matches('[data-chw-bt]')) {
    const k = el.dataset.chwBt;
    BT[k] = k === 'years' ? Number(el.value) : el.value;
    if (k === 'strategy') btFix();
    if (k === 'timeframe' && BT.timeframe !== '1d' && (BT.years || 0) > 2) BT.years = 0;
    btSave(); runBacktest(); C.chart();
    return true;
  }
  if (el.matches('[data-chw-btp]')) {
    const cur = BT.params[BT.strategy] = BT.params[BT.strategy] || {};
    cur[el.dataset.chwBtp] = el.type === 'checkbox' ? el.checked : el.value;
    btSave();
    return true;
  }
  if (el.matches('[data-chw-btshow]')) { BT.show = el.checked; btSave(); C.chart(); return true; }
  if (el.matches('[data-chw-sr]')) { C.overlay('sr', el.checked); return true; }
  if (el.matches('[data-chw-ins]')) { C.overlay('ins', el.checked); return true; }
  if (el.matches('[data-chw-learn]')) { G.learn = el.value; const d = el.closest('.chw-body').querySelector('[data-chw-def]'); if (d) d.textContent = GLOSSARY[el.value] || ''; return true; }
  return false;
}
export function onSubmit(e) {
  const f = e.target;
  if (f.matches('[data-chw-watchform]')) {
    e.preventDefault();
    const s = String(f.s.value || '').toUpperCase().trim().replace(/[^A-Z0-9.^=-]/g, '');
    if (s) { follow(s); f.s.value = ''; }
    return true;
  }
  if (f.matches('[data-chw-pairform]')) { e.preventDefault(); setPeer(f.b.value); return true; }
  return false;
}
