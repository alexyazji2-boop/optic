// Track record (Classic parity B6c, 2026-10-21; Classic app.js:6526-6615 and the validation branch's historyText):
// whether Optic's reads have predicted anything. Two records, said side by side:
// - forward: Optic keeps each read as it stood (app/signal_archive.py) and /api/validation tests it against a baseline
//   once there are enough readings; until then each says it is untested, with the count so far;
// - history: what the rules free history can replay did from the 1990s to 2026, from the pre-registered validation
//   program (docs/validation/PROTOCOL.md on the validation branch), as /api/validation's `history`.
// A slot says "not yet tested" before the request answers, so a page never implies an edge meanwhile. Free; no model.
import { html, toString } from './dom.js';
import * as api from './api.js';
import { num, esc, shortDate } from './format.js';

const TTL = 30 * 60 * 1000;
let BODY = null, AT = 0, PENDING = null;
export const DEFAULT = {
  composite: 'not yet shown to predict returns.',
  regime: 'not yet shown that moves are calmer after a positive reading.',
  walls: 'not yet shown that price stalls at the walls.',
  setups: 'not yet shown to beat the market.',
};
export const NEED = { composite: '200 readings over 20 trading days', regime: '100 readings in each regime', walls: '50 touches of a wall', setups: '50 observed setups at each horizon' };
const sg = (v, d) => (Number.isFinite(v) ? `${v > 0 ? '+' : ''}${num(v, d)}` : 'n/a');
const many = (k, one, more) => `${num(k || 0, 0)} ${k === 1 ? one : more}`;

/** The forward record for one claim, in Classic's words. */
export function forwardText(name, body = BODY) {
  const c = ((body || {}).claims || {})[name];
  if (!c) return `not yet tested${DEFAULT[name] ? `: ${DEFAULT[name]}` : '.'}`;
  const n = c.counts || {};
  if (c.status !== 'tested' || !c.result) {
    const so = {
      composite: `${many(n.observations, 'reading', 'readings')} over ${many(n.days, 'day', 'days')}`,
      regime: `${num(n.positive || 0, 0)} positive and ${num(n.negative || 0, 0)} negative ${(n.positive || 0) + (n.negative || 0) === 1 ? 'reading' : 'readings'}`,
      walls: n.touches ? many(n.touches, 'touch', 'touches') : `${many(n.reads_with_walls, 'reading', 'readings')} with a wall`,
      setups: many(n.observations, 'observed setup', 'observed setups'),
    }[name] || '';
    return `not yet tested. ${c.since ? `Optic began keeping this read on ${shortDate(c.since)} ${String(c.since).slice(0, 4)}` : 'Optic keeps this read from today'}; a fair test needs ${NEED[name] || 'more readings'}, so far ${so}. Until then, treat it as a description, not a prediction.`;
  }
  const r = c.result;
  if (name === 'composite') return `rank correlation with the next ${r.horizon_days} days' return ${sg(r.mean_rank_correlation, 3)}, against ${r.momentum_rank_correlation === null || r.momentum_rank_correlation === undefined ? 'no momentum reading' : `${sg(r.momentum_rank_correlation, 3)} for 20-day momentum alone`}; shuffled scores did as well ${num(r.shuffled_as_good_pct, 0)}% of the time (${num(n.observations, 0)} readings, ${num(n.days, 0)} days).${r.shuffled_as_good_pct > 5 ? ' Not distinguishable from chance.' : ''}`;
  if (name === 'regime') { const h = (r.by_horizon || {})['5d'] || {}; return `over 5 days, moves after positive readings averaged ${num(h.positive_mean_move_vs_implied, 2)} times the move IV implied, after negative ${num(h.negative_mean_move_vs_implied, 2)} times (${num(h.n_positive, 0)} and ${num(h.n_negative, 0)} readings${Number.isFinite(h.difference_t) ? `, t ${num(h.difference_t, 1)}` : ''}).`; }
  if (name === 'walls') return `price closed back on the near side the first day it reached a wall ${num(r.wall_hold_pct, 0)}% of the time, against ${num(r.placebo_hold_pct, 0)}% for the strikes beside it (${num(n.touches, 0)} touches, within ${r.horizon_days} days).`;
  const h = (r.by_horizon || {})['10 candles'] || {};
  return `after 10 candles, ${num(h.beat_spy_pct, 0)}% of setups beat SPY in their direction, by ${sg(h.mean_excess_pct, 2)}% on average (${num(h.n, 0)} setups).`;
}
/** What history says about one rule, or '' when the program has nothing on it. */
export function historyLine(key, body = BODY) {
  const r = ((((body || {}).history) || {}).rules || {})[key];
  return r ? `${r.line} Sample: ${r.sample}.` : '';
}
/** A claim's whole sentence: the forward record and what history adds (the branch's trackRecordText). */
export function trackText(name, body = BODY) {
  const fwd = forwardText(name, body), hist = (body || {}).history;
  if (name === 'setups') { const h = historyLine('setups', body); return { fwd, hist: h ? ['Replayed on history:', h] : null }; }
  if (name === 'composite') { const h = historyLine('trend_score', body); return { fwd, hist: h ? ['Its chart input, replayed on history:', h] : null }; }
  if ((name === 'regime' || name === 'walls') && hist) return { fwd, hist: ['', 'No history of open interest exists, so this forward record is its only test.'] };
  return { fwd, hist: null };
}

/* ---------------- slots ---------------- */
const fwdHTML = (name) => { const t = trackText(name); return html`<b>Track record:</b> ${t.fwd}${t.hist ? html` ${t.hist[0] ? html`<b>${t.hist[0]}</b> ` : ''}${t.hist[1]}` : ''}`; };
/** A forward-record slot; its words are current from the record already loaded, and refresh when it lands. */
export function slot(name) { load(); return html`<p class="asof tr-line" data-track="${name}">${fwdHTML(name)}</p>`; }
/** A history-only slot, hidden until the program has something on this rule. */
export function historySlot(key) {
  load();
  const h = historyLine(key);
  return html`<p class="asof tr-line" data-history="${key}" ${h ? '' : 'hidden'}>${h ? html`<b>Replayed on history:</b> ${h}` : ''}</p>`;
}
function paintSlots() {
  if (typeof document === 'undefined') return;
  document.querySelectorAll('[data-track]').forEach((el) => { el.innerHTML = toString(fwdHTML(el.dataset.track)); });
  document.querySelectorAll('[data-history]').forEach((el) => { const h = historyLine(el.dataset.history); el.innerHTML = h ? `<b>Replayed on history:</b> ${esc(h)}` : ''; el.hidden = !h; });
}
export function load() {
  if (BODY && Date.now() - AT < TTL) return Promise.resolve(BODY);
  if (PENDING) return PENDING;
  PENDING = api.get('/api/validation', { ttl: TTL, timeout: 60000 }).then((b) => { BODY = b; AT = Date.now(); }, () => { /* untested is the honest reading without an answer */ })
    .finally(() => { PENDING = null; paintSlots(); });
  return PENDING;
}
export const loaded = () => BODY;
/** What Milo is told: each claim's status, counts and result, and history's verdict per rule (Classic's
 *  trackRecordContext as the validation branch extended it). */
export function context(body = BODY) {
  const claims = (body || {}).claims, out = claims ? {} : { status: 'not yet tested', note: 'Optic has not shown that its composite score, gamma regime, walls or setups predict returns.' };
  Object.entries(claims || {}).forEach(([k, c]) => { out[k] = { claim: c.claim, status: c.status, since: c.since, counts: c.counts, needed: c.needed, result: c.result }; });
  const hist = (body || {}).history;
  if (hist && hist.rules) {
    out.history = { method: hist.method, scale: hist.scale, untestable: hist.untestable, rules: {} };
    Object.entries(hist.rules).forEach(([k, r]) => { out.history.rules[k] = { rule: r.what, result: r.line, sample: r.sample, counts: r.counts }; });
  }
  return out;
}
