// The frame every Dossier tab shares: the company header (symbol, name,
// price, data state, Watch / Alert / Ask Milo) and the tab strip, which is
// the only place the Dossier's pages are listed. Each tab module renders its
// own body under it and loads the core quote through core(), which the API
// cache shares across tabs so switching tabs does not refetch.
import { html } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, dir, clean, capFirst, isNum } from '../core/format.js';
import { icon } from '../ui/icons.js';
import { watchButton } from '../ui/company.js';
import { button as miloButton } from '../ui/milo.js';
import { GROUPS, hrefFor, pageOf } from '../nav.js';

/** Quote and session for the header. Resolves to {quote, session, quoteError}. */
export async function core(sym) {
  const enc = encodeURIComponent(sym);
  const [q, s] = await Promise.allSettled([
    api.get(`/api/quote/${enc}`, { ttl: 20000, timeout: 15000 }),
    api.get(`/api/session/${enc}`, { ttl: 60000 }),
  ]);
  const out = { quote: null, session: s.status === 'fulfilled' ? s.value : null, quoteError: null };
  if (q.status === 'fulfilled' && q.value && q.value.available !== false) out.quote = q.value.quote || q.value;
  else out.quoteError = q.status === 'rejected' ? q.reason : new api.ApiError('notfound', 404, `No quote for ${sym}`);
  return out;
}

export function header(sym, D, view = 'overview', { compact = false } = {}) {
  const q = D.quote || {};
  const s = (D.session && D.session.prices) || {};
  const name = q.name || (D.session && D.session.name) || '';
  const ext = s.extended && isNum(s.extended.price) ? s.extended : null;
  const label = (pageOf(view) || {}).label || 'Overview';
  return html`<header class="dhead ${compact ? 'compact' : ''}">
    <div class="dh-id">
      <h1 class="name"><b class="tick">${sym}</b>${name && name !== sym ? html`<span>${name}</span>` : ''}${q.sector ? html`<span class="t-muted dh-sector">${q.sector}</span>` : ''}<span class="sr">, ${label}</span></h1>
      <p class="dh-price">${isNum(q.price) ? html`<span class="t-display">${num(q.price)}</span>` : D.quoteError ? '' : html`<span class="sk dh-sk" role="status" aria-label="Loading the price"></span>`}
        <span class="dh-chg ${dir(q.change_pct)}">${isNum(q.change_pct) ? html`${signed(q.change, 2, '')} (${signed(q.change_pct)})` : ''}</span></p>
      <p class="dh-state">${s.phase_label ? html`${clean(s.phase_label)}. ` : ''}${s.regular_close_label && s.phase !== 'regular' ? `Price is the ${s.regular_close_label}.` : ''}${ext ? html` ${capFirst(ext.kind)} ${num(ext.price)}, <span class="${dir(ext.change_pct)}">${signed(ext.change_pct)}</span>.` : ''}</p>
    </div>
    <div class="cluster acts">${watchButton(sym)}<a class="btn" href="#/alerts?symbol=${sym}">Alert</a>${miloButton('Ask Milo', { ask: `What is the case for ${sym} right now?`, context: `${sym} Dossier, ${label}`, symbol: sym })}</div>
  </header>`;
}

export function tabs(sym, current, { fund = false } = {}) {
  const g = GROUPS.find((x) => x.id === 'security');
  // Funds have no Financials page, as in the classic app.
  const pages = g.pages.filter((p) => !(fund && p.view === 'financials'));
  return html`<nav class="tabs" aria-label="${sym} Dossier">${pages.map((p) => html`<a href="${hrefFor(p.view, sym)}" ${p.view === current ? html`aria-current="page"` : ''}>${p.label}${p.v2 ? '' : html`<span class="legacy-mark" aria-hidden="true">${icon('out')}</span><span class="sr">, opens in the current app</span>`}</a>`)}</nav>`;
}

export const isFund = (D) => !!(((D.session || {}).profile || {}).is_fund);
