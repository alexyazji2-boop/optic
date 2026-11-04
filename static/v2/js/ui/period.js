// The period line a statement or segment block carries under its title (Handoff 2): its badges (the period type, the
// accounting basis), the period in plain words with its end date, the filing it was read from, and what the reader
// must also know (a 53-week year, a change of year end). Badges are words in squared tags, never colour alone, and the
// line wraps under the title on a phone.
import { html } from '../core/dom.js';
import { fullDate } from '../core/format.js';
import * as PER from '../core/periods.js';

export const badge = (text, means = '') => html`<span class="pbadge" title="${means}">${text}</span>`;
export const typeBadge = (type) => badge(PER.BADGE[type] || type, PER.BADGE_MEANS[type] || '');
export const basisBadge = (basis) => (basis ? badge(basis, PER.BASIS_MEANS[basis] || '') : '');
/** A non-GAAP mark beside one line's name ("Free cash flow"), where the rest of the block is GAAP. */
export const nonGaap = () => badge('Non-GAAP', PER.BASIS_MEANS['Non-GAAP']);

/** "10-K filed Nov 3, 2026", linked to the filing on EDGAR. */
export function filingLink(f, lead = 'From the') {
  if (!f || !f.form) return '';
  const what = `${f.form}${f.filed ? ` filed ${fullDate(String(f.filed).slice(0, 10))}` : ''}`;
  return f.url ? html`<span class="period-filing">${lead} <a class="period-link" href="${f.url}" target="_blank" rel="noopener">${what}</a></span>` : html`<span class="period-filing">${lead} ${what}</span>`;
}

/**
 * The line itself. `type` is the period type ("annual", "quarter", "ttm"), `basis` the accounting basis badge,
 * `what` the period in words, `filing` the filing, `notes` what must be said beside it.
 */
export function periodLine({ type, basis = null, what, filing = null, notes = [], extra = '', id = '' }) {
  const bad = !what || what === PER.UNAVAILABLE;
  return html`<div class="period-line${bad ? ' is-unavailable' : ''}"${id ? html` id="${id}"` : ''}><span class="pbadges">${type ? typeBadge(type) : ''}${basisBadge(basis)}${extra}</span><span class="period-what">${what || PER.UNAVAILABLE}</span>${filingLink(filing)}</div>${(notes || []).map((n) => html`<p class="period-note">${n}</p>`)}`;
}
