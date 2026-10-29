// The four states every block can be in besides "loaded": loading, empty,
// stale and failed. One look for each across the app, so a reader learns them
// once. Copy says what happened and what to do, never sorry.
import { html, raw } from '../core/dom.js';
import { explain } from '../core/api.js';
import { ago, shortDate } from '../core/format.js';
import * as prefs from '../core/prefs.js';

export const skeleton = (kind = 'lines', n = 3, label = 'Loading') => html`<div class="sk-wrap" role="status" aria-label="${label}">
  ${kind === 'chart' ? html`<div class="sk sk-chart"></div>` : ''}
  ${kind === 'rows' ? Array.from({ length: n }, () => html`<div class="sk sk-row"></div>`) : ''}
  ${kind === 'lines' ? Array.from({ length: n }, (_, i) => html`<div class="sk sk-line" style="width:${[92, 78, 64, 85, 70][i % 5]}%"></div>`) : ''}
</div>`;

/**
 * A section's method, folded (design standard, 2026-10-19): the finding stays on screen and the formulas,
 * conventions and caveats are one press away, under the same words everywhere.
 */
/* Supporting detail one press away (directive 04's second layer): a fold that Simple starts closed and Advanced starts
 * open (density, D-019), which keeps the reader's own open or close for the visit, through the page's redraws. Its
 * heading and one line stay in view outside it, so the reader knows what is inside. */
const FOLDS = new Map();
export const simpleFold = (id, summary, ...body) => html`<details class="more-inline sfold" data-v2-sfold="${id}" ${(FOLDS.has(id) ? FOLDS.get(id) : prefs.density() === 'advanced') ? raw('open') : ''}><summary>${summary}</summary>${body}</details>`;
// recorded on the press (capture, before the fold toggles), so a fold drawn open under Advanced is not taken as a choice
if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('click', (e) => { const s = e.target.closest && e.target.closest('details[data-v2-sfold] > summary'); if (s) FOLDS.set(s.parentElement.dataset.v2Sfold, !s.parentElement.open); }, true);
}
export const how = (...parts) => html`<details class="more-inline how"><summary>How this works</summary><div class="how-body">${parts}</div></details>`;
/**
 * Where prose came from (editorial pass, 2026-10-19): an AI model's interpretation of the figures, or fixed rules
 * over them. Said beside the text, in the same words everywhere, so a reader can tell generated reading from the
 * source data and the deterministic calculations around it. Nothing is said when the payload does not say.
 */
export const generated = (x, { at } = {}) => {
  const by = x && x.written_by, mech = x && x.voice === 'mechanical';
  if (!by && !mech) return '';
  const when = at ? `, ${ago(at)}` : '';
  return html`<p class="gen-note">${mech ? `Compiled by fixed rules from the figures${when}; no model wrote it.` : `Written by an AI model from the figures${when}. It interprets them and can be wrong; the figures are the record.`}</p>`;
};
export const empty = (title, body, action) => html`<div class="state" role="note"><p class="t-h3">${title}</p>${body ? html`<p>${body}</p>` : ''}${action || ''}</div>`;

export const failed = (what, err, { retry } = {}) => html`<div class="state err" role="alert">
  <p class="t-h3">${what} did not load</p><p>${detail(err, what)}</p>
  ${retry ? html`<button type="button" class="btn btn-sm" data-v2-retry="${retry}">Try again</button>` : ''}</div>`;

function detail(err, what) {
  if (err && (err.kind === 'server' || err.kind === 'bad') && err.message && err.message !== 'Request failed') {
    return `${err.message.replace(/\.$/, '')}. It shows here as soon as the source answers.`;
  }
  return explain(err, what);
}

/** When figures are from, in the reader's zone and named: "as of 10:05 AM EDT", "as of Oct 28, 4:00 PM EDT", or
 *  "through Oct 28" for a daily close (a bare date read as a moment lands on the evening before). */
export function whenText(at) {
  if (!at) return '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(at))) return `through ${shortDate(at)}`;
  const t = new Date(at); if (!Number.isFinite(t.getTime())) return '';
  const z = prefs.zone(), day = (d) => d.toLocaleDateString('en-US', { timeZone: z, year: 'numeric', month: 'short', day: 'numeric' });
  const date = day(new Date()) === day(t) ? '' : `${t.toLocaleDateString('en-US', { timeZone: z, month: 'short', day: 'numeric' })}, `;
  return `as of ${date}${t.toLocaleTimeString('en-US', { timeZone: z, hour: 'numeric', minute: '2-digit' })} ${prefs.zoneAbbrev(z, t)}`;
}
/** The one line saying when a page's figures are from (registry B X-10: Macro, Indices, Explore, Instrument and
 *  Compare said none, though each payload carries its time): "Prices as of 10:05 AM EDT. From delayed quotes." */
export function asOfLine(at, { what = 'Figures', note = '' } = {}) {
  const when = whenText(at);
  if (!when && !note) return '';
  return html`<p class="asof">${when ? `${what} ${when}.` : ''}${when && note ? ' ' : ''}${note}</p>`;
}

/** A line for data that is older than it looks: closed market, delayed feed, failed source. */
export function staleLine({ text, at, degraded } = {}) {
  const bits = [];
  if (text) bits.push(text);
  if (at) bits.push(`Updated ${ago(at)}.`);
  if (degraded && degraded.length) bits.push(`Not available right now: ${degraded.join(', ')}.`);
  return bits.length ? html`<p class="stale" role="status">${bits.join(' ')}</p>` : '';
}
