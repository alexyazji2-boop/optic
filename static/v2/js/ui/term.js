// A term explained where it is used (owner's beginner brief, 2026-10-20, item 11): the word itself is the control,
// underlined with dots, so there is no help icon after every word. A tap, a click, Enter or Space opens a short
// definition beside it, with an illustration where one helps, labelled as one; Escape, the close button or a tap
// elsewhere shuts it and focus goes back to the word, so the reader's place and task are kept. Definitions come
// from the classic glossary (core/glossary.js, word for word) and, for the few beginner terms it lacks, from BASICS.
import { html, raw } from '../core/dom.js';
import { esc } from '../core/format.js';
import { GLOSSARY } from '../core/glossary.js';

// beginner terms the classic glossary does not carry; each a sentence or two, and an example where it helps
const BASICS = {
  ticker: { def: 'The short code a stock trades under on an exchange. Apple is AAPL; NVIDIA is NVDA. You can search Optic by a company\'s name or its ticker.' },
  watchlist: { def: 'Your list of companies to follow. Adding a company only saves it here so you can find it again; it does not buy shares or spend money.' },
  'earnings report': { def: 'A company\'s results for its latest quarter: how much it sold, how much profit it kept, and often what it expects next. US companies report four times a year.' },
  volume: { def: 'How many shares changed hands in a period. High volume means many people traded; it says nothing on its own about whether the price will rise or fall.' },
  volatility: { def: 'How much a price tends to move, up or down. High volatility means larger swings in either direction; it is not the same as risk of loss, and not a direction.' },
  valuation: { def: 'What the market price implies about a business, measured against its earnings, sales or cash flow. A company can be excellent and still expensive.' },
  'market capitalization': { def: 'The value the market puts on all of a company\'s shares: the share price times the number of shares.', ex: 'A company with 1 billion shares at $50 has a market capitalization of $50 billion.' },
  'earnings per share': { def: 'A company\'s profit for a period divided by its number of shares.', ex: 'A company that earns $10 million with 5 million shares has earnings per share of $2.00.' },
  'yield': { def: 'For a bond or a Treasury: the yearly return its price implies, as a percentage. When a bond\'s price falls its yield rises, and the reverse; a rising yield is neither good nor bad on its own.' },
  'realized return': { def: 'The gain or loss on a position that has been closed. It is locked in.' },
  'unrealized return': { def: 'The gain or loss on a position still held, at today\'s price. It changes with the price until the position is closed.' },
};
// glossary keys a page may use by another name
const ALIAS = { eps: 'earnings per share', 'market cap': 'market capitalization', 'realised return': 'realized return', 'unrealised return': 'unrealized return', bps: 'basis points' };
const EXAMPLE = {
  'basis points': 'A yield that rises from 4.25% to 4.50% has risen 25 basis points.',
  'p/e': 'A share at $100 with earnings per share of $5 has a P/E of 20.',
  'implied move': 'A ±5% implied move on a $200 stock prices a range of about $190 to $210 for the period, not a forecast of either.',
};

/** The definition of a term (and an illustration, if it has one), or null when Optic has none. */
export function define(key) {
  const k = String(key || '').toLowerCase(), a = ALIAS[k] || k;
  const b = BASICS[a] || BASICS[k];
  if (b) return { def: b.def, ex: b.ex || EXAMPLE[a] || null };
  const g = GLOSSARY[a] || GLOSSARY[k];
  return g ? { def: g, ex: EXAMPLE[a] || EXAMPLE[k] || null } : null;
}

let seq = 0;
/** The term as a control that explains itself; plain text when there is no definition for it. */
export function term(key, shown) {
  const d = define(key), label = shown || key;
  if (!d) return html`${label}`;
  return html`<button type="button" class="term" data-v2-term="${String(key).toLowerCase()}" aria-expanded="false" aria-haspopup="dialog">${label}</button>`;
}

let pop = null, from = null;
function close(refocus = true) {
  if (!pop) return;
  pop.remove(); pop = null;
  if (from) { from.setAttribute('aria-expanded', 'false'); if (refocus && document.contains(from)) from.focus({ preventScroll: true }); }
  from = null;
}
function open(btn) {
  const same = from === btn;
  close(false);
  if (same) return;
  const d = define(btn.dataset.v2Term); if (!d) return;
  const id = `term-pop-${++seq}`;
  pop = document.createElement('div');
  pop.className = 'term-pop'; pop.id = id; pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', btn.textContent.trim());
  pop.innerHTML = `<p class="term-pop-h">${esc(btn.textContent.trim())}</p><p>${esc(d.def)}</p>${d.ex ? `<p class="term-pop-ex"><span>Illustration:</span> ${esc(d.ex)}</p>` : ''}<button type="button" class="term-pop-x" aria-label="Close the explanation">Close</button>`;
  document.body.appendChild(pop);
  from = btn; btn.setAttribute('aria-expanded', 'true'); btn.setAttribute('aria-controls', id);
  // beside the word, inside the screen: under it when there is room, over it when not
  const r = btn.getBoundingClientRect(), w = Math.min(320, window.innerWidth - 24), h = pop.offsetHeight;
  const left = Math.min(Math.max(12, r.left + r.width / 2 - w / 2), window.innerWidth - w - 12);
  const below = r.bottom + 8 + h <= window.innerHeight - 12;
  pop.style.width = `${w}px`; pop.style.left = `${left + window.scrollX}px`;
  pop.style.top = `${(below ? r.bottom + 8 : Math.max(12, r.top - 8 - h)) + window.scrollY}px`;
  pop.querySelector('.term-pop-x').focus({ preventScroll: true });
}
if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('click', (e) => {
    const b = e.target.closest && e.target.closest('[data-v2-term]');
    if (b) { e.preventDefault(); open(b); return; }
    if (pop && e.target.closest && e.target.closest('.term-pop-x')) { close(); return; }
    if (pop && !(e.target.closest && e.target.closest('.term-pop'))) close(false);
  });
  // Escape shuts the explanation and nothing else (a drawer under it stays open)
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && pop) { e.preventDefault(); e.stopPropagation(); close(); } }, true);
  window.addEventListener('hashchange', () => close(false));
}
export { raw };
