// Long pages (Classic parity B3, 2026-10-21): fold any section, a sticky "Jump to a section" strip where a page has
// six or more, Expand all and Collapse all, a Panels chooser, and the knowledge level folding the specialist
// sections. Classic's makePanelsCollapsible, buildSectionIndex and the panel chooser (app.js:50058-50914).
//
// - What persists is Classic's, in its keys and formats: optic.panels.open {"view|title": true or false} for a
//   section the reader opened or folded, optic.panels.hidden.v1 {"view|title": true} for one they took off. A
//   section nobody has touched follows its default: open, unless it is above the reader's level.
// - A page calls sections(pageView, view, opts) once as it renders; opts.open lists the headings open by default,
//   as Classic's PANELS_OPEN_BY_DEFAULT did (the rest start folded). An observer applies it again after every
//   redraw, so a refresh never resets what the reader folded, hid or jumped to (owner's amendment 6).
// - A folded section is its heading line alone. The heading's button says what it does, and the heading itself is a
//   large target.
// - The strip lights the section on screen, and a jump opens a folded section before scrolling to it: smooth for a
//   short hop, instant for a long one or with reduced motion, focus on its heading. Sticky under the header on a
//   desktop; it scrolls away on a phone, as the header does (B1.8).
import { icon } from './icons.js';
import { knowledge, onChange as onPrefs } from '../core/prefs.js';

const OPEN_KEY = 'optic.panels.open', HIDDEN_KEY = 'optic.panels.hidden.v1';
const RUNG = { simple: 0, literate: 1, advanced: 2, professional: 3, adaptive: 1 };
const LEVEL_WORD = { 2: 'Advanced', 3: 'Professional' };

const read = (k) => { try { const v = JSON.parse(localStorage.getItem(k) || '{}'); return v && typeof v === 'object' ? v : {}; } catch (e) { return {}; } };
const write = (k, fn) => { try { const all = read(k); fn(all); localStorage.setItem(k, JSON.stringify(all)); } catch (e) { /* private mode: it works, it just forgets */ } };
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 48);

/** Classic's identity for a section: its view and its heading, lower case, spaces collapsed, 48 characters. */
export const panelId = (view, title) => `${view}|${String(title).toLowerCase().replace(/\s+/g, ' ').trim().slice(0, 48)}`;
/** The rung a section opens at: the highest of the page's `levels` ({heading words: rung}) its heading contains. */
export function levelOf(levels, title) {
  const t = String(title).toLowerCase();
  return Object.entries(levels || {}).reduce((n, [k, v]) => (t.includes(k) ? Math.max(n, v) : n), 0);
}
/** Open or folded: what the reader chose for it, else open when it is at or under their rung. */
export const startsOpen = (saved, id, rung, level, dflt = true) => (Object.prototype.hasOwnProperty.call(saved, id) ? !!saved[id] : rung <= level && dflt);
/** Whether a section nobody has touched starts open by the page's own list (Classic's PANELS_OPEN_BY_DEFAULT): with no
 *  list, every section; with one, those whose heading holds one of its words. */
export const openByDefault = (open, title) => (!open ? true : open.some((k) => String(title).toLowerCase().includes(k)));
/** The current section: the last shown one whose top has reached the bottom of the sticky header (`stack`). */
export function currentOf(tops, stack) { let k = -1; tops.forEach((t, i) => { if (t <= stack + 12) k = i; }); return Math.max(0, k); }

const CONF = new WeakMap();   // page view -> {view, opts, mo}
function headText(h) {
  const c = h.cloneNode(true);
  c.querySelectorAll('.sec-fold, .sec-tag, .sr').forEach((x) => x.remove());
  return c.textContent.replace(/\s+/g, ' ').trim();
}
function find(root) {
  return [...root.querySelectorAll('section.section')].filter((s) => !(s.parentElement && s.parentElement.closest('section.section')) && !s.closest('.dstick, .legal-area') && s.dataset.fixed !== '1')
    .map((s) => ({ s, h: s.querySelector(':scope > h2, :scope > .section-head h2') })).filter((x) => x.h);
}
const rung = () => (RUNG[knowledge()] !== undefined ? RUNG[knowledge()] : 1);

function apply(root) {
  const c = CONF.get(root); if (!c || !root.isConnected) return;
  const { view, opts } = c, saved = read(OPEN_KEY), hidden = read(HIDDEN_KEY), level = rung(), norm = opts.norm || ((t) => t);
  const list = find(root).map(({ s, h }) => {
    if (!s.dataset.secTitle) s.dataset.secTitle = norm(headText(h));
    const title = s.dataset.secTitle, id = panelId(view, title), min = levelOf(opts.levels, title);
    if (!s.id) s.id = `sec-${slug(title)}`;
    if (s.dataset.secKey !== id) s.dataset.secKey = id;
    const off = !!hidden[id], open = startsOpen(saved, id, min, level, openByDefault(opts.open, title));
    if (s.hidden !== off) s.hidden = off;
    s.classList.toggle('is-folded', !open);
    let b = h.querySelector('.sec-fold');
    if (!b) {
      if (LEVEL_WORD[min]) h.insertAdjacentHTML('beforeend', ` <span class="sec-tag">${LEVEL_WORD[min]}</span>`);
      // first in the heading and floated right, so a long heading wraps beside it rather than pushing it to a line of its own
      h.insertAdjacentHTML('afterbegin', `<button type="button" class="sec-fold" data-sec-fold aria-expanded="${open}" aria-label="${open ? 'Fold' : 'Open'} ${esc(title)}">${icon('down').s}</button>`);
      h.classList.add('sec-head');
    } else if (b.getAttribute('aria-expanded') !== String(open)) { b.setAttribute('aria-expanded', String(open)); b.setAttribute('aria-label', `${open ? 'Fold' : 'Open'} ${title}`); }
    return { s, h, title, id, off, open };
  });
  bar(root, list, opts);
}

// A jump chip's own words where the heading is longer than a chip holds. Chips cut at 28 characters, and the VC audit
// of 2026-10-26 found seven reading "What options price for the…" and the like. The heading, the section's id and its
// saved fold state are the full title, untouched; only the chip is shorter, and its title attribute keeps the heading.
const CHIP = {
  'Four questions, answered separately': 'Four questions',
  'Long-term trend score, from price history': 'Long-term trend score',
  'The multiple against its own history': 'Against its own history',
  'Fair-value model, discounted cash flow': 'Fair-value model',
  'Valuation and accumulation levels': 'Valuation and accumulation',
  'The business behind the reports': 'Business behind the reports',
  'What options price for the report': 'What options price',
};
export const chipLabel = (t) => CHIP[t] || (t.length > 28 ? `${t.slice(0, 27).trimEnd()}…` : t);

function bar(root, list, opts) {
  const shown = list.filter((x) => !x.off), strip = opts.strip !== false && shown.length >= (opts.min || 6), bulk = list.length >= 4;
  let nav = root.querySelector(':scope > .sec-index');
  if (!strip && !bulk) { if (nav) nav.remove(); return; }
  const sig = JSON.stringify([strip, list.map((x) => [x.s.id, x.title, x.off])]);
  if (!nav || nav.dataset.sig !== sig) {
    const open = nav ? !!nav.querySelector('details.sec-panels[open]') : false;
    const html = `${strip ? `<div class="sec-list">${shown.map((x) => `<button type="button" class="sec-chip" data-sec-jump="${esc(x.s.id)}" title="${esc(x.title)}">${esc(chipLabel(x.title))}</button>`).join('')}</div>` : ''}
      <div class="sec-bulk"><button type="button" class="btn btn-sm btn-quiet" data-sec-bulk="open">Expand all</button><button type="button" class="btn btn-sm btn-quiet" data-sec-bulk="close">Collapse all</button>
      <details class="menu sec-panels"><summary class="btn btn-sm btn-quiet">Panels${list.some((x) => x.off) ? ` <span class="ch-count">${list.filter((x) => x.off).length} off</span>` : ''}</summary><div class="menu-body menu-end">
        <p class="menu-help">Which sections this page shows. Kept in this browser.</p>
        ${list.map((x) => `<label class="check"><input type="checkbox" data-sec-show="${esc(x.id)}" ${x.off ? '' : 'checked'}> <span>${esc(x.title)}</span></label>`).join('')}
        <button type="button" class="btn btn-sm" data-sec-showall ${list.some((x) => x.off) ? '' : 'disabled'}>Show every section</button></div></details></div>`;
    if (!nav) {
      nav = document.createElement(strip ? 'nav' : 'div');
      const after = root.querySelector(':scope > .dstick') || root.querySelector(':scope > header');
      if (after) after.after(nav); else root.prepend(nav);
    } else if ((nav.tagName === 'NAV') !== strip) {
      const n2 = document.createElement(strip ? 'nav' : 'div'); nav.replaceWith(n2); nav = n2;
    }
    nav.className = `sec-index${strip ? '' : ' sec-only-bulk'}`;
    if (strip) nav.setAttribute('aria-label', 'Jump to a section'); else { nav.setAttribute('role', 'group'); nav.setAttribute('aria-label', 'Sections of this page'); }
    nav.innerHTML = html; nav.dataset.sig = sig;
    if (open) { const d = nav.querySelector('details.sec-panels'); if (d) d.open = true; }
  }
  const any = shown.some((x) => !x.open), all = shown.some((x) => x.open);
  const o = nav.querySelector('[data-sec-bulk="open"]'), cl = nav.querySelector('[data-sec-bulk="close"]');
  if (o && o.disabled !== !any) o.disabled = !any;
  if (cl && cl.disabled !== !all) cl.disabled = !all;
  current(root);
}

/* ---------------- what the reader does ---------------- */
const resized = () => { try { window.dispatchEvent(new Event('resize')); } catch (e) { /* charts redraw at the next resize */ } };   // a chart drawn while folded measured no width
function setOpen(root, s, open) {
  const id = s.dataset.secKey; if (!id) return;
  write(OPEN_KEY, (all) => { all[id] = open; });
  apply(root);
  if (open) resized();
}
const reduced = () => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; } };
/** Open a section if it is folded (or taken off), then bring it under the sticky header, its heading focused. */
export function openSection(root, id, { scroll = true } = {}) {
  const s = root.querySelector(`#${CSS.escape(id)}`); if (!s) return false;
  if (s.hidden && s.dataset.secKey) { write(HIDDEN_KEY, (all) => { delete all[s.dataset.secKey]; }); apply(root); }
  if (s.classList.contains('is-folded')) setOpen(root, s, true);
  if (!scroll) return true;
  const far = Math.abs(s.getBoundingClientRect().top) > window.innerHeight * 1.5;
  s.scrollIntoView({ block: 'start', behavior: far || reduced() ? 'auto' : 'smooth' });
  const h = s.querySelector(':scope > h2, :scope > .section-head h2');
  if (h) { if (!h.hasAttribute('tabindex')) h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
  return true;
}
/** Open a section by its id from outside its page (Home's What changed opens Options at Swing setups): the
 *  nearest host that sections() was set up on. */
export function openSectionById(id, opts) {
  const s = document.getElementById(id);
  for (let el = s && s.parentElement; el; el = el.parentElement) if (CONF.has(el)) return openSection(el, id, opts);
  return false;
}
function onClick(e) {
  const root = e.currentTarget, t = (q) => e.target.closest(q);
  let b;
  if ((b = t('[data-sec-jump]'))) { openSection(root, b.dataset.secJump); return; }
  if ((b = t('[data-sec-bulk]'))) {
    const open = b.dataset.secBulk === 'open';
    write(OPEN_KEY, (all) => { find(root).forEach(({ s }) => { if (!s.hidden && s.dataset.secKey) all[s.dataset.secKey] = open; }); });
    apply(root); if (open) resized(); return;
  }
  if (t('[data-sec-showall]')) { const v = CONF.get(root).view; write(HIDDEN_KEY, (all) => { Object.keys(all).forEach((k) => { if (k.startsWith(`${v}|`)) delete all[k]; }); }); apply(root); resized(); return; }
  // the heading is the control too, except where it holds a control of its own (a term, a link)
  const h = t('h2.sec-head');
  if (h && (t('[data-sec-fold]') || !t('a, button, input, select, summary, [role="button"]'))) {
    const s = h.closest('section.section'); if (s) setOpen(root, s, s.classList.contains('is-folded'));
  }
}
function onChange(e) {
  const x = e.target.closest && e.target.closest('[data-sec-show]'); if (!x) return;
  const root = e.currentTarget, id = x.dataset.secShow, on = x.checked;
  write(HIDDEN_KEY, (all) => { if (on) delete all[id]; else all[id] = true; });
  apply(root); if (on) resized();
  const again = root.querySelector(`[data-sec-show="${CSS.escape(id)}"]`); if (again) again.focus({ preventScroll: true });
}

/* ---------------- the section on screen ---------------- */
const px = (name) => parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name)) || 0;
function current(root) {
  const nav = root.querySelector(':scope > .sec-index:not(.sec-only-bulk)'); if (!nav) return;
  const list = find(root).filter(({ s }) => !s.hidden), stack = px('--topbar-h') + px('--dstick-h') + px('--secidx-h');
  const k = currentOf(list.map(({ s }) => s.getBoundingClientRect().top), stack), id = list[k] && list[k].s.id;
  const strip = nav.querySelector('.sec-list');
  nav.querySelectorAll('[data-sec-jump]').forEach((b) => {
    const on = b.dataset.secJump === id;
    if (on !== (b.getAttribute('aria-current') === 'location')) { if (on) b.setAttribute('aria-current', 'location'); else b.removeAttribute('aria-current'); }
    // the lit chip stays in view in the strip, without moving the page
    if (on && strip && (b.offsetLeft < strip.scrollLeft || b.offsetLeft + b.offsetWidth > strip.scrollLeft + strip.clientWidth)) strip.scrollLeft = Math.max(0, b.offsetLeft - 40);
  });
}
let active = null, raf = 0;
const onScroll = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; if (active && active.isConnected) current(active); }); };
let ro = null;
function measure(root) {
  const nav = root.querySelector(':scope > .sec-index:not(.sec-only-bulk)');
  if (ro && nav && nav.dataset.ro !== '1') { nav.dataset.ro = '1'; ro.observe(nav); }   // a strip made after the first paint
  const h = nav && getComputedStyle(nav).position === 'sticky' ? nav.offsetHeight : 0;
  document.documentElement.style.setProperty('--secidx-h', `${h}px`);
}

/**
 * Make a page's sections foldable, and give it the strip when it has `min` (6) or more. `view` is Classic's name for
 * the page (overview, long, earnings, financials, swing), so what the reader chose there carries over. Options:
 * `levels` {heading words: rung} for the specialist sections, `strip: false` where the page has its own index,
 * `norm(title)` to take a changing part (a company's name, a fiscal year) out of a heading's identity.
 */
export function sections(root, view, opts = {}) {
  const had = CONF.get(root);
  if (had && had.mo) had.mo.disconnect();
  const conf = { view, opts };
  CONF.set(root, conf);
  if (!had) {
    root.addEventListener('click', onClick);
    root.addEventListener('change', onChange);
  }
  active = root;
  window.removeEventListener('scroll', onScroll); window.addEventListener('scroll', onScroll, { passive: true });
  let pending = 0;
  conf.mo = new MutationObserver(() => {
    if (!root.isConnected) { conf.mo.disconnect(); if (active === root) { active = null; document.documentElement.style.setProperty('--secidx-h', '0px'); } return; }
    // applied in the observer itself, which runs before the browser paints, so a repaint never shows a folded
    // section open for a frame; its own changes come back once and change nothing the second time
    apply(root);
    if (!pending) pending = requestAnimationFrame(() => { pending = 0; measure(root); });
  });
  conf.mo.observe(root, { childList: true, subtree: true });
  if (ro) ro.disconnect();
  ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => measure(root)) : null;
  apply(root); measure(root);
  // the knowledge level changed elsewhere (the Milo panel's selector, Settings): sections nobody chose for follow it
  window.removeEventListener('storage', onStorage); window.addEventListener('storage', onStorage);
}
// the level set in this tab (the Milo panel's selector, Settings): the same
onPrefs((what) => { if (what === 'knowledge' && active && active.isConnected) apply(active); });
function onStorage(e) { if (active && active.isConnected && (e.key === OPEN_KEY || e.key === HIDDEN_KEY || e.key === 'optic.knowledge.v1')) apply(active); }
