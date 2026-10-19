// The frame every Dossier tab shares: the company header (symbol, name,
// price, data state, Watch / Alert / Ask Milo) and the tab strip, which is
// the only place the Dossier's pages are listed. Each tab module renders its
// own body under it and loads the core quote through core(), which the API
// cache shares across tabs so switching tabs does not refetch.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, dir, clean, capFirst, isNum } from '../core/format.js';
import { watchButton } from '../ui/company.js';
import { button as miloButton } from '../ui/milo.js';
import { GROUPS, pageOf } from '../nav.js';
import { tabSelect, tabLinks } from './tabs.js';
import { learn, kindOf, can, onLearn } from '../core/instrument.js';
import { etStamp, etDay, sessionWord } from '../core/marketTime.js';

// The price's session and time in words: the close it is, or the trade time when the session is open, and any
// extended print with the moment it was struck (core/marketTime.js).
function stateLine(D) {
  const q = D.quote || {}, sess = (D.session || {}).session || {}, s = (D.session || {}).prices || {};
  const ext = s.extended && isNum(s.extended.price) ? s.extended : null;
  const base = s.phase === 'regular' || sess.is_regular
    ? `Regular session, delayed about 15 minutes${q.market_time ? `; last trade ${etStamp(q.market_time)}` : ''}.`
    : `${sessionWord(s.phase_label || sess.label || '') || 'Closed'}. Price is the close of ${etDay((sess.last_close || {}).date) || 'the last session'}.`;
  return { base, ext };
}

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
  learn(sym, out);
  return out;
}

// The ticker's actions, grouped at the right of its header (owner, 2026-10-19). Alert and Compare are
// quieter than Watch, and sit under ⋯ on a phone. The Milo button names the ticker, so it reads as a
// question about this company and not as the top bar's general "Ask Milo".
function actions(sym, label, sm) {
  const s = sm ? 'btn-sm' : '';
  return html`<div class="acts" role="group" aria-label="${sym} actions">
    <span class="acts-2"><a class="btn btn-quiet ${s}" href="#/alerts?symbol=${sym}">Alert</a><a class="btn btn-quiet ${s}" href="#/compare?t=${sym}">Compare</a></span>
    ${watchButton(sym, { compact: sm })}${miloButton(`Ask about ${sym}`, { ask: `What is the case for ${sym} right now?`, context: `${sym} Dossier, ${label}`, symbol: sym, cls: `${s} acts-milo` })}
    <details class="menu acts-more"><summary class="btn btn-quiet ${s}" aria-label="More actions for ${sym}">⋯</summary><div class="menu-body menu-end"><a href="#/alerts?symbol=${sym}">Alert</a><a href="#/compare?t=${sym}">Compare</a></div></details>
  </div>`;
}

export function header(sym, D, view = 'overview', { compact = false, bar = false } = {}) {
  const q = D.quote || {};
  const s = (D.session && D.session.prices) || {};
  const name = q.name || (D.session && D.session.name) || '';
  const ext = s.extended && isNum(s.extended.price) ? s.extended : null;
  const label = (pageOf(view) || {}).label || 'Overview';
  // The Chart page's header is one line, so the plot gets the screen (owner, 2026-10-18 second review).
  if (bar) {
    return html`<header class="dhead bar">
      <h1 class="name"><b class="tick">${sym}</b>${name && name !== sym ? html`<span>${name}</span>` : ''}<span class="sr">, ${label}</span></h1>
      <p class="dh-price">${isNum(q.price) ? html`<span class="dh-px">${num(q.price)}</span>` : D.quoteError ? '' : html`<span class="sk dh-sk dh-sk-sm" role="status" aria-label="Loading the price"></span>`}
        <span class="dh-chg ${dir(q.change_pct)}">${isNum(q.change_pct) ? html`${signed(q.change, 2, '')} (${signed(q.change_pct)})` : ''}</span>
        ${ext ? html`<span class="dh-ext">${capFirst(ext.kind)} ${num(ext.price)} <span class="${dir(ext.change_pct)}">${signed(ext.change_pct)}</span>${ext.as_of ? `, ${etStamp(ext.as_of)}` : ''}</span>` : s.phase_label ? html`<span class="dh-ext">Close of ${etDay(((D.session || {}).session || {}).last_close && D.session.session.last_close.date) || 'the last session'}</span>` : ''}</p>
      ${actions(sym, label, true)}
    </header>`;
  }
  return html`<header class="dhead ${compact ? 'compact' : ''}">
    <div class="dh-id">
      <h1 class="name"><b class="tick">${sym}</b>${name && name !== sym ? html`<span>${name}</span>` : ''}${q.sector ? html`<span class="t-muted dh-sector">${q.sector}</span>` : ''}<span class="sr">, ${label}</span></h1>
      <p class="dh-price">${isNum(q.price) ? html`<span class="t-display">${num(q.price)}</span>` : D.quoteError ? '' : html`<span class="sk dh-sk" role="status" aria-label="Loading the price"></span>`}
        <span class="dh-chg ${dir(q.change_pct)}">${isNum(q.change_pct) ? html`${signed(q.change, 2, '')} (${signed(q.change_pct)})` : ''}</span></p>
      <p class="dh-state">${stateLine(D).base}${ext ? html` ${capFirst(ext.kind)} ${num(ext.price)}, <span class="${dir(ext.change_pct)}">${signed(ext.change_pct)}</span>${ext.as_of ? `, struck ${etStamp(ext.as_of)}` : ''}.` : ''}</p>
    </div>
    ${actions(sym, label, false)}
  </header>`;
}

// One tab list for every view, from the instrument policy (core/instrument.js): a fund has no Financials,
// whichever view it is opened from. `fund` from a caller is still honoured.
const eligible = (sym, fund) => { const k = fund ? 'fund' : kindOf(sym); return GROUPS.find((x) => x.id === 'security').pages.filter((p) => p.view !== 'financials' || can(k).financials); };
export function tabs(sym, current, { fund = false } = {}) {
  const pages = eligible(sym, fund);
  return html`<nav class="tabs" aria-label="${sym} Dossier" data-v2-dtabs="${sym}" data-v2-dcur="${current}">${tabSelect(`${sym} Dossier`, pages, current, sym)}${tabLinks(pages, current, sym)}</nav>`;
}

export const isFund = (D) => kindOf(D.sym, D) === 'fund';

// When a symbol's kind is learnt after its tabs were drawn, every tab strip for it is redrawn in place.
onLearn((sym) => {
  document.querySelectorAll(`nav[data-v2-dtabs="${CSS.escape(sym)}"]`).forEach((n) => {
    const tmp = document.createElement('div');
    draw(tmp, tabs(sym, n.dataset.v2Dcur));
    if (tmp.firstElementChild) n.replaceWith(tmp.firstElementChild);
  });
});
