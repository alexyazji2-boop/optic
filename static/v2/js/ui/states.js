// The four states every block can be in besides "loaded": loading, empty,
// stale and failed. One look for each across the app, so a reader learns them
// once. Copy says what happened and what to do, never sorry.
import { html } from '../core/dom.js';
import { explain } from '../core/api.js';
import { ago } from '../core/format.js';

export const skeleton = (kind = 'lines', n = 3, label = 'Loading') => html`<div class="sk-wrap" role="status" aria-label="${label}">
  ${kind === 'chart' ? html`<div class="sk sk-chart"></div>` : ''}
  ${kind === 'rows' ? Array.from({ length: n }, () => html`<div class="sk sk-row"></div>`) : ''}
  ${kind === 'lines' ? Array.from({ length: n }, (_, i) => html`<div class="sk sk-line" style="width:${[92, 78, 64, 85, 70][i % 5]}%"></div>`) : ''}
</div>`;

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

/** A line for data that is older than it looks: closed market, delayed feed, failed source. */
export function staleLine({ text, at, degraded } = {}) {
  const bits = [];
  if (text) bits.push(text);
  if (at) bits.push(`Updated ${ago(at)}.`);
  if (degraded && degraded.length) bits.push(`Not available right now: ${degraded.join(', ')}.`);
  return bits.length ? html`<p class="stale" role="status">${bits.join(' ')}</p>` : '';
}
