// One contextual Milo prompt per screen (2026-11-09, the owner's ask: "keep Milo easy to reach from both screens ...
// one contextual prompt on each screen"). Home asks about the reader's own day; a company's Overview asks why that
// company is moving. Pressed, it opens Milo through the same openMilo path every Ask Milo button uses, with the
// screen's figures attached, and asks at once. Milo needs an account: signed out, the question is kept in this tab
// (sessionStorage, never sent anywhere), the reader goes to sign in, and Milo asks it when they land back here.
import { html } from '../core/dom.js';
import * as store from '../core/store.js';
import * as prefs from '../core/prefs.js';
import { go } from '../core/router.js';
import { openMilo } from './milo.js';
import { icon } from './icons.js';
import { whenSettled } from '../core/device.js';

const KEY = 'optic.milo.ask.v1';
const KEEP_MS = 30 * 60 * 1000;   // a question kept longer than half an hour is not asked unannounced

/** Home's question, from what the reader has: holdings, else followed names, else the market. */
export function homeQuestion({ holdings = 0, followed = 0 } = {}) {
  if (holdings > 0) return 'Why did my holdings move today?';
  if (followed > 0) return 'Why did the names I follow move today?';
  return 'Why did the market move today?';
}
/** The Overview's question: the company's name when it is known, else its ticker (an ETF, an index, a name the
 *  feeds cannot give). The name is shortened the way people say it: "Apple Inc." reads as Apple. */
export function companyQuestion(sym, name) {
  return `Why is ${shortName(name) || String(sym || '').toUpperCase()} moving today?`;
}
export function shortName(name) {
  const n = String(name || '').trim();
  if (!n) return '';
  const cut = n.replace(/,?\s+(Inc\.?|Incorporated|Corp\.?|Corporation|Co\.?|Company|Ltd\.?|Limited|plc|PLC|N\.V\.|S\.A\.|AG|SE|Holdings?|Group|Class [A-C])\s*$/i, '').replace(/,\s*$/, '');
  // twice, for "Alphabet Inc. Class A"
  return cut.replace(/,?\s+(Inc\.?|Corp\.?|Corporation|Ltd\.?|plc|Holdings?)\s*$/i, '').trim() || n;
}

/** The prompt bar. `ask` is {question, about, symbol, figures: {name, figures: [[label, value]]}, screen}. */
export function miloPrompt(ask, { label = 'Ask Milo' } = {}) {
  return html`<section class="mp" aria-label="Ask Milo about this screen" data-v2-mp="${ask.screen}">
    <span class="mp-head" aria-hidden="true">${icon('milo')}</span>
    <p class="mp-q"><span class="mp-k">${label}:</span> <span class="mp-text" data-v2-mp-text>${ask.question}</span></p>
    <button type="button" class="btn btn-milo btn-sm mp-go" data-v2-mp-ask>${store.signedIn() ? 'Ask' : 'Sign in to ask'}</button>
  </section>`;
}

function keep(ask) {
  try { sessionStorage.setItem(KEY, JSON.stringify({ ...ask, at: Date.now() })); } catch (e) { /* private mode: asked again after sign-in by hand */ }
}
function take(screen, symbol) {
  let v = null;
  try { v = JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (e) { v = null; }
  if (!v || v.screen !== screen || (symbol || null) !== (v.symbol || null)) return null;
  try { sessionStorage.removeItem(KEY); } catch (e) { /* nothing kept */ }
  return Date.now() - Number(v.at || 0) < KEEP_MS ? v : null;
}

/** Ask now. `getAsk` is read at the press, so the figures are what the screen shows then. */
export function press(getAsk, opener) {
  const ask = getAsk();
  if (!ask) return;
  if (!store.signedIn()) {
    keep(ask);
    go(`#/signin?next=${encodeURIComponent(location.hash || '#/')}`);
    return;
  }
  openMilo({ question: ask.question, opener, about: ask.about, symbol: ask.symbol || '', figures: ask.figures || null, send: true });
}

/** After a sign-in that began at this screen's prompt: Milo opens and asks the kept question. Called by the page
 *  once it has drawn. The level the reader has now goes with it (core/prefs.js, sent with every question). */
export function resume(screen, symbol) {
  if (!store.signedIn()) return false;
  // not while the browser may still reload into the account's own things (core/device.js whenSettled): the question
  // stays kept until then, so it is asked on the page that stays, once, and its answer is not lost to the reload
  let now = false;
  whenSettled(() => { now = true; });
  if (!now) { whenSettled(() => resume(screen, symbol)); return false; }
  const ask = take(screen, symbol);
  if (!ask) return false;
  setTimeout(() => openMilo({ question: ask.question, about: ask.about, symbol: ask.symbol || '', figures: ask.figures || null, send: true }), 0);
  return true;
}

export const _test = { KEY, take, keep, level: () => prefs.level() };
