// The frame every Dossier tab shares: the company header (symbol, name,
// price, data state, Watch / Alert / Ask Milo) and the tab strip, which is
// the only place the Dossier's pages are listed. Each tab module renders its
// own body under it and loads the core quote through core(), which the API
// cache shares across tabs so switching tabs does not refetch.
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, dir, clean, capFirst, isNum } from '../core/format.js';
import { watchButton, tickerMenu } from '../ui/company.js';
import { icon } from '../ui/icons.js';
import { button as miloButton } from '../ui/milo.js';
import { GROUPS, pageOf } from '../nav.js';
import { tabSelect, tabLinks } from './tabs.js';
import { learn, kindOf, can, onLearn } from '../core/instrument.js';
import { etStamp, etDay, sessionWord, tradeTime, sessionFreshness } from '../core/marketTime.js';
import { poll } from '../core/poll.js';
import { term } from '../ui/term.js';
import { logoHTML } from '../ui/symbols.js';
import { advancedOn } from '../core/prefs.js';

// The price's session and time in words: the close it is, or the trade time when the session is open, and any
// extended print with the moment it was struck (core/marketTime.js).
// The quote's own market state, for when the session read has not answered.
const QUOTE_PHASE = { REGULAR: 'regular', PRE: 'pre', PREPRE: 'pre', POST: 'after', POSTPOST: 'after', CLOSED: 'closed' };
export function stateLine(D) {
  const q = D.quote || {}, sess = (D.session || {}).session || {}, s = (D.session || {}).prices || {};
  const ext = s.extended && isNum(s.extended.price) ? s.extended : null;
  const phase = s.phase || sess.phase || QUOTE_PHASE[String(q.market_state || '').toUpperCase()] || null;
  let base;
  if (phase === 'regular' || sess.is_regular) base = `Regular session. ${sessionFreshness(q).text}.`;
  // In real Safari a cold server answered the session read after the client's 20 s limit, and the header
  // said "Closed" at 9:58 AM on a trading day (2026-10-19). Not knowing the session, it claims none.
  else if (!phase) base = `${sessionFreshness(q).text}.`;
  else base = `${sessionWord(s.phase_label || sess.label || phase)}. Price is the close of ${etDay((sess.last_close || {}).date) || 'the last session'}.`;
  return { base, ext };
}
/**
 * The same, short, for the one-line header: what the price is and when (editorial pass, 2026-10-19). During the
 * session it is a delayed trade with its time, never "the close"; outside it, the close of the named day; and an
 * extended-hours print is said apart, with the moment it was struck.
 */
export function priceWhen(D) {
  const q = D.quote || {}, sess = (D.session || {}).session || {}, s = (D.session || {}).prices || {};
  const phase = s.phase || sess.phase || QUOTE_PHASE[String(q.market_state || '').toUpperCase()] || null;
  if (phase === 'regular' || sess.is_regular || !phase) return sessionFreshness(q).text;
  const day = etDay((sess.last_close || {}).date);
  return day ? `Close of ${day}` : 'Last close';
}

/**
 * Two quotes for one ticker (the 20-second /api/quote and the ticker snapshot's, cached two minutes) merged so the
 * later trade wins and the other only fills gaps. Whichever answered last used to win, so the header price could
 * step back to an older snapshot (editorial pass, 2026-10-19).
 */
export function fresher(a, b) {
  if (!a) return b || null; if (!b) return a;
  const ta = Date.parse(tradeTime(a) || '') || 0, tb = Date.parse(tradeTime(b) || '') || 0;
  return tb >= ta ? Object.assign({}, a, b) : Object.assign({}, b, a);
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

/** Keep a Dossier tab's header price current: every 20 s through the trading day, every 5 minutes outside it,
 *  paused while the tab is hidden (core/poll.js). Only the price lines are swapped, so an open menu, focus and
 *  everything below the header are untouched, and nothing is repainted when nothing changed. The price says
 *  how fresh it is from the quote's own time (priceWhen), never from how often this asks. Stop it in dispose(). */
export function livePrice(root, sym, getD, view, opts) {
  const enc = encodeURIComponent(sym);
  const key = (D) => JSON.stringify([D.quote && D.quote.price, D.quote && D.quote.change_pct, tradeTime(D.quote), D.quote && D.quote.delayed_minutes, D.quote ? sessionFreshness(D.quote).word : '',
    ((D.session || {}).prices || {}).extended]);
  // the Chart tab asks every 15 s (`every`) and takes each new quote for its last bar and the tab's title (`onQuote`)
  const { every = 20000, onQuote = null } = opts || {};
  return poll(async (current) => {
    const [q, s] = await Promise.allSettled([api.get(`/api/quote/${enc}`, { ttl: 0, force: true, timeout: 15000 }), api.get(`/api/session/${enc}`, { ttl: 60000 })]);
    const D = getD();
    if (!current() || !D || D.sym !== sym) return;
    const was = key(D), pxWas = D.quote && D.quote.price;
    if (q.status === 'fulfilled' && q.value && q.value.available !== false) D.quote = fresher(D.quote, q.value.quote || q.value);
    if (s.status === 'fulfilled' && s.value) D.session = s.value;
    if (onQuote) onQuote(D);
    if (key(D) === was) return;
    const h = root.querySelector('.dhead'); if (!h) return;
    const tmp = document.createElement('div'); draw(tmp, header(sym, D, view, opts));
    ['.dh-price', '.dh-state'].forEach((sel) => { const a = h.querySelector(sel), b = tmp.querySelector(sel); if (a && b && a.innerHTML !== b.innerHTML) a.innerHTML = b.innerHTML; });
    // a price that moved holds its direction's colour for a moment (motion proposal, 2026-10-24); the figure is the record
    const px = D.quote && D.quote.price, el = h.querySelector('.dh-px, .dh-price .t-display');
    if (el && isNum(px) && isNum(pxWas) && px !== pxWas) { el.classList.add(px > pxWas ? 'is-tick-up' : 'is-tick-dn'); setTimeout(() => el.classList.remove('is-tick-up', 'is-tick-dn'), 1200); }
  }, { every });
}

// The ticker's actions, grouped at the right of its header (owner, 2026-10-19). Alert and Compare are
// quieter than Watch, and sit under ⋯ on a phone. The Milo button names the ticker, so it reads as a
// question about this company and not as the top bar's general "Ask Milo".
function actions(sym, label, sm) {
  const s = sm ? 'btn-sm' : '';
  return html`<div class="acts" role="group" aria-label="${sym} actions">
    <span class="acts-2"><a class="btn btn-quiet ${s}" href="#/alerts?symbol=${sym}">Alert</a><a class="btn btn-quiet ${s}" href="#/compare?t=${sym}">Compare</a><a class="btn btn-quiet ${s}" href="#/${encodeURIComponent(sym)}/sheet" title="A printable research sheet">Export</a></span>
    ${watchButton(sym, { compact: sm })}${miloButton(`Ask about ${sym}`, { ask: `What is the case for ${sym} right now?`, context: `${sym} Dossier, ${label}`, symbol: sym, cls: `${s} acts-milo` })}
    <details class="menu acts-more"><summary class="btn btn-quiet ${s}" aria-label="More actions for ${sym}">${icon('more')}</summary><div class="menu-body menu-end">${tickerMenu(sym)}</div></details>
  </div>`;
}

/* "Show advanced analysis", Classic's one control for how much of the specialist research shows open (owner's
 * screenshots, 2026-10-25), at the end of the tab row as in Classic. It is the reader's knowledge level read as a
 * switch, on Classic's keys (core/prefs.js), so this switch, Settings' and Classic's never disagree. Only where it
 * changes something: the Overview. */
export function advSwitch() {
  const on = advancedOn();
  return html`<button type="button" class="adv-switch" role="switch" aria-checked="${on}" data-v2-adv-toggle title="Opens Advanced research and the full case for and against on this page, and has Milo answer at the Advanced level"><span class="adv-track" aria-hidden="true"><span class="adv-knob"></span></span><span class="adv-label">Show advanced analysis</span></button>`;
}
/* The Weinstein stage, on the Overview alone as in Classic: its reading in Classic's words ("Stage 3 · Topping",
 * "breakdown") as a label that opens what it means for this symbol, and Explain, which drafts the question for Milo. */
function stageLine(sym, st) {
  if (!st) return '';
  return html`<p class="dh-stage stage-${st.stage}">${term(`stage:${sym}`, html`<i class="stage-dot" aria-hidden="true"></i>${st.main}${st.tag ? html` <span class="dh-stage-tag">${st.tag}</span>` : ''}`)}
    ${miloButton('Explain', { ask: st.ask(sym), context: `${sym} Dossier, Overview: Weinstein stage`, symbol: sym, cls: 'btn-sm dh-explain' })}</p>`;
}

export function header(sym, D, view = 'overview', { compact = false, bar = true, stage = null } = {}) {
  const q = D.quote || {};
  const s = (D.session && D.session.prices) || {};
  const name = q.name || (D.session && D.session.name) || '';
  const ext = s.extended && isNum(s.extended.price) ? s.extended : null;
  const label = (pageOf(view) || {}).label || 'Overview';
  const st = typeof stage === 'function' ? stage() : stage;   // a function for livePrice's redraws, which pass these options on
  // One line, so the research gets the screen: the Chart page's header (owner, 2026-10-18 second review), on every
  // dossier tab since the design standard of 2026-10-19. The tall header below is kept for a caller that asks.
  if (bar) {
    return html`<header class="dhead bar${st ? ' is-wide' : ''}">${raw(logoHTML(sym, { lazy: false }))}
      <h1 class="name"><b class="tick">${sym}</b>${name && name !== sym ? html`<span>${name}</span>` : ''}<span class="sr">, ${label}</span></h1>
      <p class="dh-price">${isNum(q.price) ? html`<span class="dh-px">${num(q.price)}</span>` : D.quoteError ? '' : html`<span class="sk dh-sk dh-sk-sm" role="status" aria-label="Loading the price"></span>`}
        <span class="dh-chg ${dir(q.change_pct)}">${isNum(q.change_pct) ? html`${signed(q.change, 2, '')} (${signed(q.change_pct)})` : ''}</span>
        ${isNum(q.price) ? html`<span class="dh-ext">${priceWhen(D)}</span>` : ''}${ext ? html`<span class="dh-ext">${capFirst(ext.kind)} ${num(ext.price)} <span class="${dir(ext.change_pct)}">${signed(ext.change_pct)}</span>${ext.as_of ? ` at ${etStamp(ext.as_of)}` : ''}</span>` : ''}</p>
      ${stageLine(sym, st)}${actions(sym, label, true)}
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
