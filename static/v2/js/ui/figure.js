// A financial figure printed from the figure registry (owner's Handoff 1, 2026-11-03), and the panel that defines it.
//
// fig(fv) prints the server's own text for the figure as a control, underlined with dots like a term (ui/term.js),
// so there is no info icon after every number. A press, Enter or Space opens what the figure is: its plain-English
// definition at the reader's knowledge level, the period it covers and its basis as text badges, the formula, the
// inputs with the filing each came from, the as-of date, the source, any restatement, and what it cannot tell you.
// Beside the number on a wide screen; on a phone it rises from the bottom as a sheet with the page still in view
// above it, never a modal over it. Escape, Close or a press elsewhere shuts it and focus returns to the figure.
//
// The panel is built from two things: the registry's definition (fetched once per session, core/figures.js) and
// the value object the page printed, kept here by symbol and id as it is printed. A figure whose definition cannot
// be loaded opens a panel that says so, with a retry; it is never shown as if it had none.
import { html } from '../core/dom.js';
import { esc, fullDate } from '../core/format.js';
import * as prefs from '../core/prefs.js';
import * as F from '../core/figures.js';
import * as PER from '../core/periods.js';
import * as api from '../core/api.js';
import { icon } from './icons.js';

const SEEN = new Map();
const keyOf = (sym, id) => `${String(sym || '').toUpperCase()}|${id}`;
/** Remember a figure's value object for its panel (a page that prints the text another way still registers it). */
export function remember(fv, sym = '') { if (fv && fv.id) SEEN.set(keyOf(sym, fv.id), fv); }

/** The figure's text as the control that opens its definition. `label` names it for a screen reader when the
 *  visible label is elsewhere (a table's row heading). A missing figure prints "Not reported", never a blank. */
export function fig(fv, { sym = '', label = '', cls = '' } = {}) {
  if (!fv || !fv.id) return html`<span class="fig-missing">Not reported</span>`;
  remember(fv, sym);
  const name = label || fv.name || '';
  return html`<button type="button" class="fig ${fv.status === 'ok' ? '' : 'is-missing'} ${cls}" data-v2-fig="${fv.id}" data-v2-fig-sym="${String(sym || '').toUpperCase()}" aria-haspopup="dialog" aria-expanded="false" aria-label="${name}: ${fv.text}. Show how it is defined">${fv.text}</button>`;
}

/** A figure's label as the same control, for a row heading: it opens the definition its value opens. */
export function figName(fv, text = '', { sym = '' } = {}) {
  if (!fv || !fv.id) return html`${text}`;
  remember(fv, sym);
  return html`<button type="button" class="fig fig-name" data-v2-fig="${fv.id}" data-v2-fig-sym="${String(sym || '').toUpperCase()}" aria-haspopup="dialog" aria-expanded="false">${text || fv.name}</button>`;
}

// ---------------------------------------------------------------- the panel
let pop = null, from = null, seq = 0;
// the period badges every statement and segment block uses (core/periods.js, Handoff 2); the server sends its own
const BADGE = { annual: 'Annual', quarter: 'Quarter', ttm: 'TTM', balance: 'Balance sheet', forward: 'Forward estimate' };
const level = () => { try { return prefs.knowledge(); } catch (e) { return 'intermediate'; } };
const dateText = (iso) => (iso && /^\d{4}-\d{2}-\d{2}/.test(String(iso)) ? fullDate(String(iso).slice(0, 10)) : '');

function close(refocus = true) {
  if (!pop) return;
  pop.remove(); pop = null;
  if (from) { from.setAttribute('aria-expanded', 'false'); if (refocus && document.contains(from)) from.focus({ preventScroll: true }); }
  from = null;
}

function inputsHTML(fv) {
  const ins = (fv.inputs || []).filter((x) => x && x.name);
  if (!ins.length) return '';
  return `<div class="fig-sec"><p class="fig-k">Inputs</p><ul class="fig-ins">${ins.map((x) => {
    const where = [x.line ? `line ${x.line}` : '', x.end ? dateText(x.end) : '', x.form ? `${x.form}${x.filed ? `, filed ${dateText(x.filed)}` : ''}` : ''].filter(Boolean).join(', ');
    const re = x.restated ? ` Restated${x.restated.on ? ` in a filing on ${dateText(x.restated.on)}` : ''}.` : '';
    return `<li><span class="fig-in-n">${esc(x.name)}</span> <b>${esc(x.text || 'Not reported')}</b>${where ? `<small>${esc(where)}${x.url ? ` <a href="${esc(x.url)}" target="_blank" rel="noopener">filing</a>` : ''}</small>` : ''}${x.note || re ? `<small>${esc(`${x.note || ''}${re}`.trim())}</small>` : ''}</li>`;
  }).join('')}</ul></div>`;
}

function body(e, fv, sym) {
  const per = fv.period || {}, src = fv.source || {};
  const defs = (e && e.definitions) || {};
  const def = defs[level()] || defs[(F.loaded() || {}).default_level] || defs.intermediate || '';
  const kind = per.type || (e && e.period);
  const again = fv.status === 'unavailable' && sym && !fv.retrieved_by_milo ? ` <button type="button" class="btn btn-sm fig-refetch">${icon('retry').s}Retry</button>` : '';
  const status = fv.status && fv.status !== 'ok' ? `<p class="fig-why"><b>${esc(fv.text)}.</b> ${esc(fv.why || '')}${again}</p>` : '';
  const stop = (x) => (x && !/[.!?]$/.test(x) ? `${x}.` : x);
  const periodLine = [stop(per.fiscal && per.label ? `${per.label} (${per.fiscal})` : per.label), per.quarters_text, per.detail, per.fiscal_year ? `Fiscal year the estimate covers: ${per.fiscal_year.toLowerCase()}.` : '', per.note].filter(Boolean).join(' ');
  const asOf = fv.as_of && /^\d{4}-\d{2}-\d{2}T/.test(String(fv.as_of)) ? `As of ${prefs.clock(fv.as_of)}` : fv.as_of ? `As of ${dateText(fv.as_of)}` : '';
  const source = [src.name, src.form ? `${src.form}${src.filed ? ` filed ${dateText(src.filed)}` : ''}` : '', src.note].filter(Boolean).join('. ');
  const restated = fv.restated
    ? `Restated${fv.restated.on ? ` in a filing on ${dateText(fv.restated.on)}` : ' in a later filing'}${fv.restated.prior_text ? `; the earlier filing gave ${fv.restated.prior_text}` : '; the earlier value is not available'}.`
    : fv.restatement === 'unavailable' ? 'Restatement history unavailable from this source.' : fv.restatement === 'checked' ? 'Not restated in any later filing.' : '';
  const retrieved = fv.retrieved_by_milo ? '<p class="fig-note">The value as Milo retrieved it for this answer. The Dossier shows the current one.</p>' : '';
  return `<p class="fig-h">${esc(fv.name || (e && e.name) || 'Figure')}${sym ? ` <span class="fig-sym">${esc(sym)}</span>` : ''}</p>
    <p class="fig-v">${esc(fv.text || '')}${fv.note ? ` <small>${esc(fv.note)}</small>` : ''}</p>
    <p class="fig-badges">${kind ? `<span class="fig-badge" title="${esc(PER.BADGE_MEANS[kind] || '')}">${esc(per.badge || BADGE[kind] || kind)}</span>` : ''}${e && e.basis ? `<span class="fig-badge">${esc(e.basis)}</span>` : ''}${fv.currency && fv.unit === 'money' ? `<span class="fig-badge">${esc(fv.currency)}</span>` : ''}</p>
    ${status}${retrieved}
    ${def ? `<p class="fig-def">${esc(def)}</p>` : '<p class="fig-def is-missing">Definition unavailable.</p>'}
    ${periodLine ? `<div class="fig-sec"><p class="fig-k">Period</p><p>${esc(periodLine)}</p></div>` : ''}
    ${e ? `<div class="fig-sec"><p class="fig-k">Formula</p><p>${esc(e.formula)}</p><p class="fig-sym-line">${esc(e.symbols)}</p></div>` : ''}
    ${inputsHTML(fv)}
    <div class="fig-sec"><p class="fig-k">Source</p><p>${esc(source || 'Source not stated.')}${src.url ? ` <a href="${esc(src.url)}" target="_blank" rel="noopener">Open the filing</a>` : ''}</p>${asOf ? `<p class="fig-meta">${esc(asOf)}</p>` : ''}${restated ? `<p class="fig-meta">${esc(restated)}</p>` : ''}</div>
    ${e && e.limits ? `<div class="fig-sec"><p class="fig-k">What it cannot tell you</p><p>${esc(e.limits)}</p></div>` : ''}`;
}

function paint(btn, fv, sym) {
  const e = F.entry(fv.id);
  const missing = !F.loaded();
  const ask = `Explain ${fv.name || 'this figure'} (${fv.text})${sym ? ` for ${sym}` : ''}: what it measures, how it is calculated, the period it covers, and what it cannot tell me.`;
  pop.innerHTML = `${missing ? `<p class="fig-why">The definition could not be loaded just now. <button type="button" class="btn btn-sm fig-retry">${icon('retry').s}Retry</button></p>` : ''}${body(e, fv, sym)}
    <div class="term-pop-acts"><button type="button" class="btn btn-sm btn-milo term-pop-milo" data-v2-milo="${esc(ask)}" data-v2-milo-ctx="${esc(String(document.title || '').replace(/, Optic$/, ''))}" ${sym ? `data-v2-milo-sym="${esc(sym)}"` : ''}>${icon('milo').s}Explain this with Milo</button><button type="button" class="term-pop-x fig-x" aria-label="Close the definition">Close</button></div>`;
  if (!pop.classList.contains('is-sheet')) place(btn);
}

// Under the figure, else over it, else inside the screen over it: the panel is taller than the term's popover, and
// placed only under or over it, it opened 250px below the bottom of a 609px pane with the figure mid-screen.
function place(btn) {
  // the page's width without its scrollbar: innerWidth counts it, and the panel ran 3px past the page's edge
  const r = btn.getBoundingClientRect(), vw = document.documentElement.clientWidth || window.innerWidth, vh = window.innerHeight, w = Math.min(380, vw - 24);
  pop.style.width = `${w}px`; pop.style.maxHeight = `${Math.max(160, Math.min(640, vh - 24))}px`;
  const h = pop.offsetHeight, left = Math.min(Math.max(12, r.left + r.width / 2 - w / 2), vw - w - 12);
  const top = r.bottom + 8 + h <= vh - 12 ? r.bottom + 8 : r.top - 8 - h >= 12 ? r.top - 8 - h : Math.max(12, vh - 12 - h);
  pop.style.left = `${left + window.scrollX}px`; pop.style.top = `${top + window.scrollY}px`;
}

function valueFor(btn) {
  const sym = btn.dataset.v2FigSym || '', id = btn.dataset.v2Fig;
  // a Milo source carries its figure in the button, as Milo retrieved it: that, not the page's newer copy
  try { const own = btn.dataset.v2FigValue ? JSON.parse(btn.dataset.v2FigValue) : null; if (own) return { ...own, id, retrieved_by_milo: true }; } catch (e) { /* falls through */ }
  const seen = SEEN.get(keyOf(sym, id));
  if (seen) return seen;
  return { id, name: (F.entry(id) || {}).name, text: btn.textContent.trim(), status: 'ok' };
}

// The company's figures asked for again, for a figure the server could not work out the first time: the panel shows
// the new value, and says so when it is still unavailable; nothing stale is put in its place.
async function refetch(btn) {
  if (!btn) return;
  const sym = btn.dataset.v2FigSym || '', id = btn.dataset.v2Fig;
  try {
    const block = await api.get(`/api/figures/${encodeURIComponent(sym)}`, { force: true, timeout: 30000 });
    const fv = ((block || {}).figures || {})[id];
    if (fv) remember(fv, sym);
  } catch (e) { /* still unavailable: the panel says so again */ }
  if (pop && from === btn) paint(btn, valueFor(btn), sym);
}

async function open(btn) {
  const same = from === btn;
  close(false);
  if (same) return;
  const fv = valueFor(btn), sym = btn.dataset.v2FigSym || '';
  const id = `fig-pop-${++seq}`;
  pop = document.createElement('div');
  pop.className = 'term-pop fig-pop'; pop.id = id; pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', `${fv.name || 'Figure'}: how it is defined`);
  if (window.matchMedia && window.matchMedia('(max-width: 559px)').matches) pop.classList.add('is-sheet');
  document.body.appendChild(pop);
  from = btn; btn.setAttribute('aria-expanded', 'true'); btn.setAttribute('aria-controls', id);
  paint(btn, fv, sym);
  pop.querySelector('.fig-x').focus({ preventScroll: true });
  if (!F.loaded()) {
    const mine = pop;
    await F.registry();
    if (pop === mine && F.loaded()) { paint(btn, fv, sym); pop.querySelector('.fig-x').focus({ preventScroll: true }); }
  }
}

if (typeof document !== 'undefined' && document.addEventListener) {
  F.registry();
  document.addEventListener('click', (e) => {
    const t = e.target;
    if (!t || !t.closest) return;
    if (pop && t.closest('.fig-pop [data-v2-milo]')) { setTimeout(() => close(false), 0); return; }   // drafted into Milo
    if (pop && t.closest('.fig-retry')) { e.preventDefault(); const b = from; F.registry().then(() => { if (pop && b) paint(b, valueFor(b), b.dataset.v2FigSym || ''); }); return; }
    if (pop && t.closest('.fig-refetch')) { e.preventDefault(); refetch(from); return; }
    const b = t.closest('[data-v2-fig]');
    if (b) { e.preventDefault(); open(b); return; }
    if (pop && t.closest('.fig-x')) { close(); return; }
    if (pop && !t.closest('.fig-pop')) close(false);
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && pop) { e.preventDefault(); e.stopPropagation(); close(); } }, true);
  window.addEventListener('hashchange', () => close(false));
}
