// Dossier, Overview: the company's events in one list (owner's Handoff 9, 2026-11-03, the Company Event Timeline).
// News, earnings, insider and congressional trades, analyst actions and SEC filings from /api/timeline (app/timeline.py),
// newest first, 50 at a time. One node for the visit, kept through the Overview's redraws as its data arrives (as
// pages/thesis.js keeps its own), so the period, the filter, an opened entry and the pages read stay as they are. It
// asks for nothing until the Dossier's own figures (/api/ticker) have arrived or failed, so the first load is the same
// as before, and most of what it reads is then in the server's cache.
//
// - Every entry says what its date is ("Transaction date", "Disclosed", "Published"), shown in the reader's time zone
//   when the source gives a time, and as the source dates it when it does not.
// - Every entry names its source and links it, and its details link the Dossier section it comes from.
// - A source that did not answer is said above the list, with what did arrive below it: never a silent gap.
// - The kind of an entry is a word beside its icon, never a colour alone.
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as prefs from '../core/prefs.js';
import { clean, fullDate } from '../core/format.js';
import { icon } from './icons.js';
import { how, skeleton, whenText } from './states.js';

export const TYPES = [['news', 'News', 'news'], ['earnings', 'Earnings', 'earnings'], ['insiders', 'Insiders', 'insider'],
  ['congress', 'Congress', 'congress'], ['analysts', 'Analysts', 'analyst'], ['filings', 'Filings', 'filing']];
const ICON = Object.fromEntries(TYPES.map(([id, , ic]) => [id, ic]));
export const PERIODS = [[30, '30 days'], [90, '90 days'], [365, '1 year']];
export const PER = 50;

const TL = { sym: null, node: null, days: 90, kind: 'all', data: null, items: [], page: 0, err: null, moreErr: null,
  loading: false, more: false, started: false, open: new Set(), seq: 0, focusId: null };

/** Where an entry's kind lives in Optic, for "the full Dossier section" each entry links back to. */
export function sectionLink(type, sym) {
  const s = encodeURIComponent(sym);
  return {
    news: { href: `#/${s}/news`, label: `All of ${sym}'s headlines on the News tab` },
    earnings: { href: `#/${s}/earnings`, label: `${sym}'s Earnings tab` },
    insiders: { href: `#/${s}/financials?section=fin-ownership`, label: 'Insider activity on the Financials tab' },
    congress: { href: `#/insiders?symbol=${s}&view=house`, label: `House trades in ${sym} on the Insiders page` },
    analysts: { href: `#/analysts?symbol=${s}`, label: `Analyst actions on ${sym} on the Analysts page` },
    filings: { href: `#/${s}/financials?section=fin-filings`, label: 'SEC filings on the Financials tab' },
  }[type] || null;
}

/** The words of an entry's source link: where it goes, not "click here". */
export function sourceText(e) {
  if (e.type === 'news') return 'Read the story';
  if (e.type === 'earnings') return 'Yahoo Finance earnings calendar';
  if (e.type === 'analysts') return "Yahoo Finance's analysis page";
  if (e.type === 'congress') return 'The filing (PDF)';
  if (e.type === 'insiders') return /SEC EDGAR/.test(e.source || '') ? 'The Form 4 filing on EDGAR' : "The company's Form 4 filings on EDGAR";
  return 'The filing on EDGAR';
}

/** The day and, when the source gives one, the time in the reader's zone with its name. A dated record with no time
 *  is printed as the source dates it, never moved by a time zone. */
export function whenOf(e) {
  if (e.at) {
    const t = new Date(e.at);
    if (Number.isFinite(t.getTime())) {
      const z = prefs.zone();
      return { iso: e.at,
        day: t.toLocaleDateString('en-US', { timeZone: z, month: 'short', day: 'numeric', year: 'numeric' }),
        time: `${t.toLocaleTimeString('en-US', { timeZone: z, hour: 'numeric', minute: '2-digit' })} ${prefs.zoneAbbrev(z, t)}` };
    }
  }
  return { iso: e.date, day: fullDate(e.date), time: '' };
}

const domId = (id) => `tl-d-${String(id).replace(/[^a-zA-Z0-9_-]/g, '-')}`;

export function entryHTML(e, sym, datesOf = {}) {
  const w = whenOf(e), open = TL.open.has(e.id), did = domId(e.id), link = sectionLink(e.type, sym);
  return html`<li class="tl-e" data-tl-type="${e.type}" data-tl-id="${e.id}" tabindex="-1">
    <div class="tl-when"><time datetime="${w.iso}">${w.day}</time>${w.time ? html`<span class="tl-time">${w.time}</span>` : ''}<span class="tl-dk">${e.date_label}${e.when_note ? `, ${e.when_note}` : ''}</span></div>
    <div class="tl-main">
      <p class="tl-kind">${icon(ICON[e.type] || 'flag')}<span>${e.type_label}</span></p>
      <p class="tl-title">${clean(e.title)}</p>
      ${e.summary ? html`<p class="tl-sum">${clean(e.summary)}</p>` : ''}
      ${e.delay_note ? html`<p class="tl-delay">${clean(e.delay_note)}</p>` : ''}
      <p class="tl-src">Source: ${clean(e.source)}${e.source_url ? html`. <a class="textlink" href="${e.source_url}" target="_blank" rel="noopener">${sourceText(e)}<span class="sr"> (opens in a new tab)</span></a>` : ''}</p>
      <button type="button" class="btn btn-quiet btn-sm tl-more" data-tl-open="${e.id}" aria-expanded="${open}" aria-controls="${did}">${open ? 'Hide details' : 'Details'}<span class="sr">: ${clean(e.title)}</span></button>
      <div class="tl-detail" id="${did}" ${open ? '' : raw('hidden')}>
        ${(e.detail || []).length ? html`<dl class="tl-dl">${e.detail.map((d) => html`<div><dt>${clean(d.label)}</dt><dd>${clean(d.value)}</dd></div>`)}</dl>` : ''}
        ${datesOf[e.type] ? html`<p class="tl-note">The date: ${clean(datesOf[e.type])}</p>` : ''}
        ${link ? html`<p><a class="textlink" href="${link.href}">${link.label}</a></p>` : ''}
      </div>
    </div></li>`;
}

function controls(d) {
  const types = (d && d.types) || [];
  const all = types.reduce((n, t) => n + (t.count || 0), 0);
  const chip = (id, label, ic, count, state) => html`<button type="button" class="chip tl-chip" data-tl-kind="${id}" aria-pressed="${TL.kind === id}">${ic ? icon(ic) : ''}<span>${label}</span> <span class="t-muted">${state === 'failed' ? 'unavailable' : count}</span></button>`;
  return html`<div class="tl-controls">
    <div class="seg" role="group" aria-label="Period">${PERIODS.map(([n, l]) => html`<button type="button" data-tl-days="${n}" aria-pressed="${TL.days === n}">${l}</button>`)}</div>
    <div class="chips tl-chips" role="group" aria-label="Show events of one kind">${chip('all', 'All', '', all, '')}${types.map((t) => chip(t.id, t.label, ICON[t.id], t.count, t.state))}</div>
  </div>`;
}

function emptyFor(d) {
  const t = (d.types || []).find((x) => x.id === TL.kind);
  if (!t) {
    const why = (d.types || []).filter((x) => x.reach).map((x) => `${x.label}: ${x.reach}`);
    return html`<div class="state" role="note"><p class="t-h3">No events for this company in this period</p>${why.length ? html`<p>${clean(why.join(' '))}</p>` : ''}</div>`;
  }
  if (t.state === 'failed') return html`<div class="state err" role="note"><p class="t-h3">${t.label}: temporarily unavailable</p><p>${clean(t.failed)} The other kinds of event are still here: choose All to see them.</p></div>`;
  return html`<div class="state" role="note"><p class="t-h3">${clean(t.empty)}</p>${t.absent || t.reach ? html`<p>${clean(t.absent || t.reach)}</p>` : ''}</div>`;
}

export function sectionHTML(sym) {
  const d = TL.data;
  const head = html`<div class="section-head"><div><h2 class="t-h2" id="tl-h">Company events</h2>
    <p class="section-sub">News, earnings, insider and congressional trades, analyst actions and SEC filings for ${sym}, newest first.</p>
    ${d ? how(html`<p>Six sources the Dossier already reads, put in one list. No new feed and no model: each entry is what its source says, credited to it, and its date says what it is.</p>
      <ul class="plain">${(d.types || []).map((t) => html`<li><b>${t.label}</b>. ${clean(t.dates)} From ${clean(t.source)}.</li>`)}</ul>
      <p>Nothing is merged across sources. The same event reported by two sources is two entries, each labelled; two entries are one only when they are the same source's same story or filing.</p>
      <p>An insider's or a member of Congress's trade is the record of a trade they disclosed. It is not a recommendation or a signal, and Optic draws no conclusion from it. Not investment advice.</p>`) : ''}</div></div>`;
  if (!TL.started || (TL.loading && !d)) return html`${head}${skeleton('rows', 4, 'Loading company events')}`;
  if (TL.err && !d) {
    return html`${head}<div class="state err" role="alert"><p class="t-h3">Company events did not load</p><p>${clean(String(TL.err.message || 'The server did not answer.').replace(/\.?$/, '.'))} The rest of the page is unaffected.</p><button type="button" class="btn btn-sm" data-tl-retry>Try again</button></div>`;
  }
  const failed = (d.types || []).filter((t) => t.state === 'failed');
  const reach = (d.types || []).filter((t) => (TL.kind === 'all' || t.id === TL.kind) && t.state !== 'failed' && (t.reach || t.partial || t.absent));
  const left = Math.max(0, (d.total || 0) - TL.items.length);
  return html`${head}${controls(d)}
    ${failed.length ? html`<div class="tl-failed stale" role="status"><p>Not every source answered. ${failed.map((t) => `${clean(t.label)}: ${clean(t.failed)}`).join(' ')} The entries below are from the other ${d.answered} sources.</p><button type="button" class="btn btn-sm" data-tl-retry>Try again</button></div>` : ''}
    ${reach.length ? html`<ul class="tl-reach">${reach.map((t) => html`<li><b>${t.label}</b>: ${clean([t.partial, t.absent, t.reach].filter(Boolean).join(' '))}</li>`)}</ul>` : ''}
    <div class="tl-list-wrap" aria-busy="${TL.loading ? 'true' : 'false'}">${!d.total ? emptyFor(d) : html`<ol class="tl-list" aria-label="${TL.kind === 'all' ? 'Company events' : `${(TYPES.find((x) => x[0] === TL.kind) || [])[1] || ''} events`}, newest first">${TL.items.map((e) => entryHTML(e, sym, Object.fromEntries((d.types || []).map((t) => [t.id, t.dates]))))}</ol>`}</div>
    ${d.total ? html`<p class="tl-count">Showing ${TL.items.length} of ${d.total}.${left ? html` <button type="button" class="btn btn-sm" data-tl-more ${TL.more ? raw('disabled') : ''}>${TL.more ? 'Loading' : `Show ${Math.min(PER, left)} older`}</button>` : ''}</p>` : ''}
    ${TL.moreErr ? html`<p class="stale" role="status">The next ${PER} did not load: ${clean(String(TL.moreErr.message || 'no answer'))}.</p>` : ''}
    <p class="asof">Events ${whenText(d.built_at)}, for ${fullDate(d.since)} to ${fullDate(d.today)}. Times are in your time zone; an entry with no time is dated as its source dates it.</p>`;
}

function focusKey(el) {
  if (!el || !TL.node || !TL.node.contains(el)) return null;
  for (const a of ['data-tl-days', 'data-tl-kind', 'data-tl-open', 'data-tl-more', 'data-tl-retry']) if (el.hasAttribute(a)) return [a, el.getAttribute(a)];
  return null;
}

function paint() {
  const n = TL.node; if (!n) return;
  const box = n.querySelector('.tl-box'); if (!box) return;
  const key = focusKey(document.activeElement);
  const howOpen = !!box.querySelector('details.how[open]');
  draw(box, sectionHTML(TL.sym));
  if (howOpen) { const h = box.querySelector('details.how'); if (h) h.open = true; }
  if (TL.focusId) {
    const li = [...box.querySelectorAll('[data-tl-id]')].find((x) => x.getAttribute('data-tl-id') === TL.focusId);
    TL.focusId = null;
    if (li) { li.focus({ preventScroll: false }); return; }
  }
  if (key) {
    const el = [...box.querySelectorAll(`[${key[0]}]`)].find((x) => x.getAttribute(key[0]) === key[1]) || box.querySelector(`[${key[0]}]`);
    if (el) el.focus({ preventScroll: true });
  }
}

async function load({ append = false, fresh = false } = {}) {
  const my = ++TL.seq, sym = TL.sym, page = append ? TL.page + 1 : 1;
  if (append) { TL.more = true; TL.moreErr = null; } else { TL.loading = true; TL.err = null; }
  paint();
  const q = new URLSearchParams({ days: String(TL.days), type: TL.kind, page: String(page), per: String(PER) });
  if (fresh) q.set('fresh', '1');
  try {
    const d = await api.get(`/api/timeline/${encodeURIComponent(sym)}?${q}`, { ttl: 120000, timeout: 45000, force: fresh });
    if (my !== TL.seq || TL.sym !== sym) return;
    TL.data = d; TL.page = d.page || page;
    TL.items = append ? TL.items.concat(d.events || []) : (d.events || []);
    if (append && (d.events || []).length) TL.focusId = d.events[0].id;
  } catch (e) {
    if (my !== TL.seq || TL.sym !== sym) return;
    if (append) TL.moreErr = e; else { TL.err = e; TL.data = null; TL.items = []; }
  }
  TL.loading = false; TL.more = false;
  paint();
}

/** Start reading, once per visit: the Overview calls it when its own figures have arrived or failed. */
export function startTimeline(sym) {
  if (!TL.node || TL.sym !== sym || TL.started) return;
  TL.started = true;
  load();
}

function wire(n) {
  n.addEventListener('click', (ev) => {
    const t = (s) => ev.target.closest(s); let b;
    if ((b = t('[data-tl-days]'))) { const v = Number(b.dataset.tlDays); if (v !== TL.days) { TL.days = v; TL.open.clear(); load(); } return; }
    if ((b = t('[data-tl-kind]'))) { const v = b.dataset.tlKind; if (v !== TL.kind) { TL.kind = v; load(); } return; }
    if ((b = t('[data-tl-open]'))) {
      const id = b.dataset.tlOpen, open = !TL.open.has(id), panel = document.getElementById(b.getAttribute('aria-controls'));
      if (open) TL.open.add(id); else TL.open.delete(id);
      b.setAttribute('aria-expanded', String(open));
      if (b.firstChild) b.firstChild.textContent = open ? 'Hide details' : 'Details';
      if (panel) panel.hidden = !open;
      return;
    }
    if (t('[data-tl-more]')) { if (!TL.more) load({ append: true }); return; }
    if (t('[data-tl-retry]')) { load({ fresh: true }); }
  });
}

/** The section in the Overview's `[data-tl-slot]`, one node for the visit: drawn once, moved into each redraw. */
export function mountTimeline(main, sym) {
  const slot = main.querySelector('[data-tl-slot]');
  if (TL.sym !== sym || !TL.node) {
    Object.assign(TL, { sym, days: 90, kind: 'all', data: null, items: [], page: 0, err: null, moreErr: null,
      loading: false, more: false, started: false, open: new Set(), focusId: null });
    TL.seq += 1;
    const n = document.createElement('section');
    n.className = 'section tl'; n.id = 'ov-events'; n.setAttribute('aria-labelledby', 'tl-h');
    n.innerHTML = '<div class="tl-box"></div>';
    TL.node = n; wire(n); paint();
  }
  if (!slot) { if (TL.node.isConnected) TL.node.remove(); return; }
  if (slot !== TL.node) slot.replaceWith(TL.node);
}

/** Leaving the page: the next visit starts again. */
export function disposeTimeline() {
  TL.seq += 1;
  Object.assign(TL, { sym: null, node: null, data: null, items: [], started: false, open: new Set() });
}

export const _test = { state: TL, sectionHTML, entryHTML, whenOf, sectionLink, sourceText, load };
