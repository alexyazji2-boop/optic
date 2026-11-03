// Glossary terms marked where they appear (Classic parity B9.1; Classic app.js gloss, glossHeaders and dedupeGlossTerms).
// A word the glossary defines becomes the same control term() makes by hand (ui/term.js): a tap, Enter or Space opens
// its definition with "Explain this with Milo", a hover or keyboard focus shows it as a tip, Escape, a second tap or a
// tap elsewhere closes it. Once per section: the first mention is marked and the rest are left plain. A column header
// that is exactly a label Classic defines (Drawdown, 5Y CAGR, Implied vol) is explained as a whole.
//
// Eligible text only (owner's acceptance safeguards, 2026-10-21): never inside a link, a button, a field, editable
// text, code, a chart (its labels and tips), a heading that already holds a term, the Dossier header, the tabs and
// strips, a menu, or Milo's answers (the Milo panel is never touched). The reader's knowledge level decides (Phase 05,
// core/prefs.js explainPolicy): Expert marks nothing, as Classic's "off"; New to Markets marks the term and shows its
// short definition with it, from the same glossary ("inline"); the levels between mark it to explain itself. Applied
// again after every redraw, by one observer on the page, so a refresh keeps the marks; a level change re-marks it.
import * as prefs from '../core/prefs.js';
import { GLOSSARY, LABEL_DEFS, TH_HINTS } from '../core/glossary.js';
// The marks' press, hover and Escape handlers are term.js's, registered when it loads. Only pages that make a term by
// hand imported it, so on a first visit to Macro, Read, Scan or Compare every marked word was a button that did
// nothing (investor audit, 2026-10-27). Loaded here, wherever a word can be marked.
import './term.js';

// words whose everyday sense is the common one on these pages ("the model on screen"); still available by hand
const AUTO_SKIP = new Set(['screen', 'universe', 'surprise', 'support']);   // "likely to support estimates" is not a price level
const KEYS = Object.keys(GLOSSARY).filter((k) => !AUTO_SKIP.has(k)).sort((a, b) => b.length - a.length);
export const TERM_RE = new RegExp(`\\b(${KEYS.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\b`, 'i');
const SKIP = ['a', 'button', 'input', 'textarea', 'select', 'option', 'label', 'summary', 'code', 'pre', 'kbd', 'samp', 'svg', 'canvas', 'script', 'style', 'nav', 'h1',
  '[contenteditable]', '[role="tab"]', '[role="button"]', '[role="option"]', '[role="dialog"]', '[aria-hidden="true"]', '[data-no-gloss]',
  '.term', '.term-pop', '.term-tip', '.lvl', '.chart-wrap', '.chart-slot', '.chart-tip', '.milo-panel', '.milo-log', '.tick', '.seg', '.chips', '.tabs', '.tabset',
  '.menu', '.ta-list', '.dhead', '.dstick', '.legal-area', '.sr', '.mstrip', '.cs-strip', '.op-groups', '.sec-list', '.toast',
  // a definition shown inline is not marked again: "gamma (how fast ... (its delta (how much ...)) changes" (Phase 12)
  '.term-inline'].join(', ');
// a fold or a tab panel is a section of its own, so a mention hidden in a closed "How this works" never takes the mark
// from the one in view
const SCOPE = 'details, [role="tabpanel"], .view, section.section, [data-ws-panel], .drawer, .page-view';
// a tile's label ("Implied move through Nov 4") keeps its mark without a definition inside it (Phase 12)
const NO_INLINE = 'table, dl, .kv, .rd .k';

const LEVEL_KEY = 'optic.knowledge.v1';
/** Whether this reader's level marks terms: every level but Expert (Classic's explain "off"; an old "professional" too). */
export function marking(level) { return prefs.explainPolicy(level) !== 'off'; }
const level = () => prefs.knowledge();
// the glossary's own first sentence, short enough to sit inside the reader's sentence ("dollar volume (share price
// multiplied by shares traded)"); a longer one is left to the mark, which still opens the whole definition
const PROPER = new Set(['Optic', 'Yahoo', 'Nasdaq', 'Treasury', 'Federal', 'Fed', 'Dow', 'Russell', 'Weinstein', 'Black', 'Bollinger', 'Fibonacci', 'Donchian', 'Wilder']);
export function gloss(key) {
  const d = String(GLOSSARY[key] || ''); if (!d) return '';
  let first = d.split('. ')[0].replace(/\.$/, '').trim();
  if (!first || first.length > 140) return '';
  // a parenthesis inside the definition becomes commas, so the reader's sentence never holds two levels of them
  first = first.replace(/\s*\(([^()]*)\)/g, ', $1,').replace(/,\s*,/g, ',').replace(/,\s*$/, '');
  const w = first.split(/\s/)[0];
  // an acronym's expansion keeps its capitals ("Earnings Per Share", not "earnings Per Share")
  const expansion = /^(?:[A-Z][a-z]+\s?){2,6}$/.test(first);
  if (!expansion && /^[A-Z][a-z]*$/.test(w) && !PROPER.has(w)) first = first[0].toLowerCase() + first.slice(1);   // "A" too: "(a 20-day average ...)"
  return first;
}

// A definition sits after a whole noun phrase, never inside one: at New to Markets the Desk read "No consensus (the
// average of what analysts forecast) estimates" (Phase 12, 2026-11-02). It goes in when the term ends its phrase:
// punctuation, the end of the text, a number, or a small joining word next ("P/E of 30", "consensus is"). Before
// another word of the same phrase ("consensus estimates", "gamma exposure") the mark alone explains it.
const JOINS = new Set(('is are was were be been being has have had do does did of in on at for to and or but nor that which who whose '
  + 'with from by as than then the a an its it this these those so if when while because about into over under after before between '
  + 'against during without within through per vs versus can could will would should may might must not no').split(' '));
/** Whether the text right after a term lets its definition follow it without splitting a phrase. */
export function endsPhrase(rest) {
  const r = String(rest || '');
  if (!r.trim()) return true;
  if (/^[-'\u2019]/.test(r)) return false;                 // "consensus-based", "Apple's"
  const m = /^\s+([A-Za-z][A-Za-z'\u2019-]*)/.exec(r);
  return m ? JOINS.has(m[1].toLowerCase()) : true;
}

const keyOf = (word) => String(word).toLowerCase();
function seenIn(scope) {
  const seen = new Set();
  scope.querySelectorAll('[data-v2-term]').forEach((t) => seen.add(t.dataset.v2Term));
  return seen;
}
function termButton(key, text) {
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'term'; b.dataset.v2Term = key; b.dataset.v2Auto = '';
  b.setAttribute('aria-expanded', 'false'); b.setAttribute('aria-haspopup', 'dialog'); b.textContent = text;
  return b;
}
/** Whether a text node may be marked: not inside anything the safeguards keep plain. */
export function eligible(node) {
  const el = node.parentElement; if (!el) return false;
  if (el.closest(SKIP)) return false;
  const h = el.closest('h2, h3, h4'); if (h && h.querySelector('[data-v2-term]')) return false;
  return true;
}

/** Mark the terms under a root: whole-label column headers, then the first mention of each term in each section. */
export function mark(root) {
  if (!root) return 0;
  if (!marking(level())) { unmark(root); return 0; }
  const inline = prefs.explainPolicy(level()) === 'inline';
  let n = 0;
  root.querySelectorAll('th').forEach((th) => {
    if (th.querySelector('[data-v2-term], button, a, input')) return;
    const k = th.textContent.trim().toLowerCase().replace(/\s+/g, ' ');
    if (!k || !(LABEL_DEFS[k] || TH_HINTS[k])) return;
    const b = termButton(`head:${k}`, th.textContent.trim()); th.textContent = ''; th.appendChild(b); n += 1;
  });
  const seen = new Map();   // scope -> keys already marked in it
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: (t) => (t.nodeValue && t.nodeValue.trim().length > 1 && TERM_RE.test(t.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT) });
  const nodes = []; for (let t = walker.nextNode(); t; t = walker.nextNode()) nodes.push(t);
  nodes.forEach((t) => {
    if (!t.isConnected || !eligible(t)) return;
    const scope = t.parentElement.closest(SCOPE) || root;
    if (!seen.has(scope)) seen.set(scope, seenIn(scope));
    const keys = seen.get(scope);
    let node = t;
    for (let guard = 0; guard < 6 && node; guard += 1) {
      const text = node.nodeValue, re = new RegExp(TERM_RE.source, 'gi');
      let m, hit = null;
      while ((m = re.exec(text))) { if (!keys.has(keyOf(m[1]))) { hit = m; break; } }
      if (!hit) break;
      const k = keyOf(hit[1]); keys.add(k);
      const after = node.splitText(hit.index), rest = after.splitText(hit[1].length);
      const btn = termButton(k, hit[1]); after.replaceWith(btn); n += 1;
      // a definition joins prose only: a table cell or a figure's label keeps the mark, and its row its shape
      // (directive 05 section 4: the level is not forced into data tables)
      // nor inside a parenthesis the page already opened: "(free cash flow (cash from operations ...) to the firm)"
      const head = text.slice(0, hit.index), insideParens = (head.match(/\(/g) || []).length > (head.match(/\)/g) || []).length;
      const def = inline && !insideParens && !btn.closest(NO_INLINE) && endsPhrase(rest.nodeValue) ? gloss(k) : '';
      if (def) { const sp = document.createElement('span'); sp.className = 'term-inline'; sp.dataset.v2TermInline = ''; sp.textContent = ` (${def})`; btn.after(sp); }
      node = rest;
    }
  });
  return n;
}

/** Take the automatic marks off again (the reader moved to Expert, or to another level), with any definition shown
 *  beside them; terms placed by hand stay. */
export function unmark(root) {
  root.querySelectorAll('[data-v2-term-inline]').forEach((sp) => sp.remove());
  root.querySelectorAll('[data-v2-term][data-v2-auto]').forEach((b) => b.replaceWith(document.createTextNode(b.textContent)));
}

let mo = null;
/** Keep the page marked: now, and after every redraw under it. */
export function watch(root) {
  if (!root || typeof MutationObserver === 'undefined') return;
  if (mo) mo.disconnect();
  let queued = false;
  const run = () => { queued = false; mo.disconnect(); try { mark(root); } finally { mo.observe(root, { childList: true, subtree: true, characterData: true }); } };
  mo = new MutationObserver(() => { if (!queued) { queued = true; requestAnimationFrame(run); } });
  run();
  // a level change marks the page again from scratch: New to Markets adds definitions, Expert takes the marks off
  const relevel = () => { mo.disconnect(); try { unmark(root); mark(root); } finally { mo.observe(root, { childList: true, subtree: true, characterData: true }); } };
  window.addEventListener('storage', (e) => { if (e.key === LEVEL_KEY) relevel(); });
  prefs.onChange((what) => { if (what === 'knowledge' || what === 'knowledge-synced') relevel(); });
}
