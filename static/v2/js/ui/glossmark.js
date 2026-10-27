// Glossary terms marked where they appear (Classic parity B9.1; Classic app.js gloss, glossHeaders and dedupeGlossTerms).
// A word the glossary defines becomes the same control term() makes by hand (ui/term.js): a tap, Enter or Space opens
// its definition with "Explain this with Milo", a hover or keyboard focus shows it as a tip, Escape, a second tap or a
// tap elsewhere closes it. Once per section: the first mention is marked and the rest are left plain. A column header
// that is exactly a label Classic defines (Drawdown, 5Y CAGR, Implied vol) is explained as a whole.
//
// Eligible text only (owner's acceptance safeguards, 2026-10-21): never inside a link, a button, a field, editable
// text, code, a chart (its labels and tips), a heading that already holds a term, the Dossier header, the tabs and
// strips, a menu, or Milo's answers (the Milo panel is never touched). The reader's level decides: Professional
// marks nothing, as Classic's "off"; every other level marks. Applied again after every redraw, by one observer on
// the page, so a refresh keeps the marks.
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
  '.term', '.term-pop', '.term-tip', '.chart-wrap', '.chart-slot', '.chart-tip', '.milo-panel', '.milo-log', '.tick', '.seg', '.chips', '.tabs', '.tabset',
  '.menu', '.ta-list', '.dhead', '.dstick', '.legal-area', '.sr', '.mstrip', '.cs-strip', '.op-groups', '.sec-list', '.toast'].join(', ');
// a fold or a tab panel is a section of its own, so a mention hidden in a closed "How this works" never takes the mark
// from the one in view
const SCOPE = 'details, [role="tabpanel"], .view, section.section, [data-ws-panel], .drawer, .page-view';

const LEVEL_KEY = 'optic.knowledge.v1';
/** Whether this reader's level marks terms: every level but Professional (Classic's explain "off"). */
export function marking(level) { return String(level || '') !== 'professional'; }
const level = () => { try { return localStorage.getItem(LEVEL_KEY) || ''; } catch (e) { return ''; } };

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
      after.replaceWith(termButton(k, hit[1])); n += 1;
      node = rest;
    }
  });
  return n;
}

/** Take the automatic marks off again (the reader moved to Professional); terms placed by hand stay. */
export function unmark(root) {
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
  window.addEventListener('storage', (e) => { if (e.key === LEVEL_KEY) run(); });
}
