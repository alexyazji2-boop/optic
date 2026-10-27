// Markets, Read. The day's Read (the market, the calendar, the wires), the
// Optic Desk edition, and the rest of the day's material one tab away.
//
// Paid pieces never load on their own. The Read itself, the weekly update and
// the catalyst read are asked for with `cached=true`, which serves only what is
// already written; the server's own loop keeps the Read current. Writing a
// missing piece is a labelled button, because it spends a model call.
import { $, html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, clean, bolded, capFirst, ago, shortDate, fullDate, isNum, dir } from '../core/format.js';
import { skeleton, empty, failed, how, generated } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { groupedTabs } from '../ui/grouptabs.js';
import { toast } from '../ui/toast.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { sectionHead } from './tabs.js';
import { etDay } from '../core/marketTime.js';
import * as TR from '../core/track.js';
import { scoreLine, toneBand } from '../ui/score.js';

let D = {}, live = true, mainEl = null, tabState = { g: 0, s: {} }, cal = { impact: 'all', range: 'week' }, cat = { status: 'relevant', category: '', sector: '', theme: '', q: '' };
const ask = (label, q) => miloButton(label, { ask: q, context: 'Markets, Read' });
const kv = (rows, n = 3) => html`<dl class="kv" style="--kv:${n}">${rows.filter(Boolean).map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
const etTime = (iso) => { try { return new Date(iso).toLocaleString('en-US', { weekday: 'short', hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' }) + ' ET'; } catch (e) { return ''; } };

/* ---------------- the Desk edition ---------------- */
function desk() {
  const d = D.desk;
  if (!d || !d.available) return '';
  const e = d.edition || {};
  const ev = new Map((e.evidence || []).map((x) => [x.id, x]));
  const cites = (ids) => (ids || []).map((id) => ev.get(id)).filter(Boolean).map((x) => html` <a class="cite" href="${x.url}" target="_blank" rel="noopener" title="${x.label || ''}">${x.source || 'source'}</a>`);
  return html`<section class="section desk" aria-labelledby="dk-h"><p class="t-label">Optic Desk, ${e.slot_label || ''}${e.test_edition ? ', a test edition' : ''}</p>
    <h2 class="t-display-m" id="dk-h">${clean(e.headline || '')}</h2>${generated(e, { at: e.written_at || e.gathered_at })}
    ${e.summary ? html`<p class="lede-line">${clean(e.summary)}</p>` : ''}
    ${(e.sections || []).map((s) => html`<div class="desk-sec"><h3>${clean(s.title || capFirst(s.id || ''))}</h3>
      ${(s.items || s.claims || []).map((c) => html`<p>${clean(c.text || c)}${cites(c.cites)}</p>`)}</div>`)}
    <details class="more-inline"><summary>How this edition was made</summary><p>${clean(((e.outline || {}).limits || []).join(' '))}</p><p class="asof">Written by ${e.written_by || e.voice || 'the desk'}; gathered ${ago(e.gathered_at)}.</p></details>
  </section>`;
}

/* ---------------- the Read ---------------- */
// Building the Read on request (Classic parity B8.7). Classic built it whenever its tab opened with no edition ready;
// here it is built only when the reader presses, and says what it costs first: the server writes the edition's text
// with one model call, kept and shared by every reader, so a second press does not write it again.
const BUILD_COST = 'Building it gathers the day\'s moves, the calendar and the wires, and an AI model writes the summary: one model call for this edition, shared by every reader. It can take half a minute.';
function buildControl(label, quiet) {
  if (D.building) return html`<p class="asof" role="status">Building today's Read. It appears here when it is done.</p>`;
  return html`${D.buildNote ? html`<p class="asof" role="status">${D.buildNote}</p>` : ''}<button type="button" class="${quiet ? 'textlink' : 'btn'}" data-v2-read-build>${label}</button>${quiet ? html`<span class="asof"> One model call for this edition, shared by every reader.</span>` : ''}`;
}
const pause = (ms) => new Promise((r) => setTimeout(r, ms));
async function buildRead() {
  if (D.building) return;
  const was = D.brief && !D.brief.missing ? `${D.brief.day}|${D.brief.built_at}` : '';
  D.building = true; D.buildNote = ''; paint();
  try {
    let r = await api.get('/api/brief', { ttl: 0, force: true, timeout: 120000 });
    // an aged Read comes back at once while a newer one is built behind it: asked again until it lands, about two minutes
    for (let i = 0; r && r.refreshing && i < 15 && live; i += 1) {
      await pause(8000);
      const c = await api.get('/api/brief?cached=true', { ttl: 0, force: true, timeout: 30000 });
      if (c && !c.missing && !c.previous_day && `${c.day}|${c.built_at}` !== was) { r = c; break; }
    }
    if (r && !r.missing) { D.brief = r; D.briefErr = null; }
    if (r && (r.refreshing || r.missing) && live) D.buildNote = 'It is still being built. It appears here when you come back, or press again in a minute.';
  } catch (err) { toast(api.explain(err, "Today's Read"), { kind: 'bad' }); }
  D.building = false; if (live) { paint(); const f = mainEl.querySelector('#rd-h') || mainEl.querySelector('[data-v2-read-build]'); if (f) { if (!f.hasAttribute('tabindex')) f.setAttribute('tabindex', '-1'); f.focus({ preventScroll: true }); } }
}
function readHero() {
  const b = D.brief;
  if (D.briefErr) return failed("Today's Read", D.briefErr, { retry: 'brief' });
  if (!b) return skeleton('lines', 6, "Loading today's Read");
  if (b.missing) return empty("Today's Read is not ready yet", `${clean(b.reason || '')} ${BUILD_COST}`, buildControl("Build today's Read"));
  const s = b.summary || {}, w = b.wires || {};
  const idx = ((b.overview || {}).groups || {}).indices || [];
  return html`${idx.length ? html`<div class="mstrip" style="--n:${idx.length}" role="group" aria-label="Indices">${idx.map((r) => html`<a class="mcell" href="#/${r.symbol}"><span class="k">${r.symbol} ${r.name}</span><span class="v">${num(r.last)}</span><span class="d ${dir(r.day)}">${signed(r.day)}</span></a>`)}</div>
      <p class="asof">Fund prices, not index levels.</p>` : ''}
    <section class="section read-hero" aria-labelledby="rd-h">
      <div class="section-head"><div><p class="t-label">Optic's Read, ${fullDate(b.day)}</p><h2 class="t-display-m" id="rd-h">${clean(s.headline || 'The Read')}</h2>
        <p class="section-sub">Prices and headlines updated ${ago(b.built_at)}${b.previous_day ? '. Showing the previous day\'s Read until today\'s is ready' : b.stale ? '. A newer edition is due shortly' : ''}.${w.window_hours ? ` Covering the ${w.window_hours} hours since the previous session closed${w.window_hours >= 48 ? ', the whole weekend' : ''}.` : ''}</p>
        ${b.previous_day || b.stale ? html`<div class="read-build">${buildControl(b.previous_day ? "Build today's Read now" : 'Update it now', true)}</div>` : ''}</div>
        ${ask('Ask Milo about the Read', 'What matters most in today\'s Read, and what period does it cover?')}</div>
      <div class="read-prose">${(s.paragraphs || []).map((p) => (String(p).startsWith('## ') ? html`<h3>${raw(bolded(p.slice(3)))}</h3>` : html`<p>${raw(bolded(p))}</p>`))}</div>
      <!-- two clocks, said apart (design review, 2026-10-19): the data refresh above and when this text was written -->
      ${generated(s, { at: s.written_at })}${s.covers_words ? html`<p class="asof">The text covers the session of ${s.covers_words}.</p>` : ''}${s.written_at && Date.parse(b.built_at) - Date.parse(s.written_at) > 1800000 ? html`<p class="asof">The text was written from the figures at that time; the prices above are newer.</p>` : ''}
      ${((s.figure_check || {}).unmatched || []).length ? html`<p class="stale">Optic could not match ${s.figure_check.unmatched.length === 1 ? 'one figure' : `${s.figure_check.unmatched.length} figures`} in this text to the data it was written from: ${s.figure_check.unmatched.map((u) => `${u.figure} (${clean(u.why)})`).join('; ')}. The figures in the panels are computed, not written by the model.</p>` : ''}
      ${s.method || (b.overview || {}).note ? html`<details class="more-inline"><summary>How the Read is made</summary><p class="asof">${clean(s.method || '')} ${clean((b.overview || {}).note || '')}</p></details>` : ''}
      <form class="read-search" role="search" data-v2-read-search><label class="field">${icon('search')}<span class="sr">Search the headlines</span><input name="q" placeholder="Search the headlines" autocomplete="off" value="${D.q || ''}"></label></form>
      <div id="read-results" aria-live="polite">${searchResults()}</div>
    </section>`;
}
function searchResults() {
  const r = D.search;
  if (!r) return '';
  if (r === 'loading') return html`<p class="t-muted" role="status">Searching…</p>`;
  if (r.error) return html`<p class="form-error">Could not search. ${api.explain(r.error, 'The search')}</p>`;
  if (!(r.results || []).length) return html`<p class="quiet">No headline matches “${D.q}” in the ${r.searched} stories currently loaded.</p>`;
  return html`<p class="asof">${r.matched} match${r.matched === 1 ? '' : 'es'} in ${r.searched} stories across ${r.sources} sources.</p><ul class="nw-list">${r.results.map(headline)}</ul>`;
}
const headline = (h) => html`<li class="nw"><a class="nw-title" href="${h.url}" target="_blank" rel="noopener">${clean(h.title)}</a><p class="t-muted">${h.source}${h.source_detail ? `, ${h.source_detail}` : ''}, ${ago(h.published)}${h.access === 'paid' ? ', subscription' : ''}</p>${h.summary ? html`<p>${clean(h.summary).slice(0, 240)}</p>` : ''}</li>`;

/* ---------------- tabs ---------------- */
function overnight() {
  if (D.briefErr) return html`<p class="quiet">The overnight reading comes with today's Read, which did not load. Try again above.</p>`;
  if (D.brief === undefined) return skeleton('lines', 3, 'Loading the overnight reading');
  const g = (D.brief || {}).global_overnight;
  if (!g || !g.available) return empty('No overnight reading', clean((g || {}).reason || ''));
  return html`${(g.sessions || []).map((s) => html`<h3>${clean(s.label)}</h3><p class="t-muted">${s.advancing} up, ${s.declining} down, average move ${num(s.avg_move_pct, 2)}%.</p>
      <div class="tscroll"><table class="t"><thead><tr><th>Market</th><th>Day</th><th>5 days</th><th>20 days</th><th>With the S&amp;P</th></tr></thead><tbody>${(s.rows || []).map((r) => html`<tr><td><a href="#/instrument/${encodeURIComponent(r.symbol)}">${r.label}</a> <small class="t-muted">${r.region || ''}</small></td><td class="${dir(r.chg_1d)}">${signed(r.chg_1d)}</td><td>${signed(r.chg_5d)}</td><td>${signed(r.chg_20d)}</td><td>${num(r.corr_spx, 2)} <small class="t-muted">${r.corr_spx >= g.corr_threshold ? 'linked' : 'loose'}</small></td></tr>`)}</tbody></table></div>`)}
    ${(g.crosses || []).length ? html`<h3>What carries it into US hours</h3><ul class="plain">${g.crosses.map((c) => html`<li><b>${c.label}</b> ${signed(c.chg_1d)}: ${clean(c.note)}. ${clean(c.corr_read)}.</li>`)}</ul>` : ''}
    <p class="asof">${g.linked_count} of ${g.market_count} markets move with the S&amp;P (correlation at or above ${num(g.corr_threshold, 2)} over ${g.corr_window} sessions). Moving together is not one causing the other. ${clean(g.method || '')}</p>`;
}

function priority() {
  const p = D.priority;
  if (p === undefined) return skeleton('lines', 4, "Loading today's priority");
  if (!p || !p.available) return empty('Nothing on the board right now', '');
  return html`${p.columns.map((c) => html`<h3>${c.name} <span class="t-muted">${c.total ?? (c.rows || []).length}</span></h3><p class="t-muted">${clean(c.blurb || '')}</p>
    ${(c.rows || []).length ? html`<ul class="plain">${c.rows.slice(0, 8).map((r) => html`<li>${r.ticker ? html`<a class="tk-link" href="#/${r.ticker}"><b>${r.ticker}</b></a> ` : ''}<b>${clean(r.title)}</b> <span class="t-muted">${[r.when, r.time, r.impact ? `${r.impact} impact` : ''].filter(Boolean).join(', ')}</span>. ${clean(r.why || '')}</li>`)}</ul>` : html`<p class="quiet">Nothing here today.</p>`}`)}
    <p class="asof">${clean(p.method || '')}</p>`;
}

function catalystMode() {
  const c = D.catmode;
  if (c === undefined) return skeleton('lines', 3, 'Checking for a release moving the market');
  if (!c || !c.available) return empty('No release is driving the market', clean((c || {}).reason || 'Nothing major has been released in the last 72 hours.'));
  const r = c.release || {}, rd = c.read || {};
  return html`<h3>${clean(r.title)}</h3><p class="t-muted">${r.source}${r.source_detail ? `, ${r.source_detail}` : ''}. Released ${(r.age || {}).at_et || ''}, ${(r.age || {}).label || ''}.</p>
    ${r.summary ? html`<p>${clean(r.summary)}</p>` : ''}${r.why_it_matters ? html`<p>${clean(r.why_it_matters)}</p>` : ''}
    <p><b>Consensus against actual:</b> not shown. ${clean((c.consensus || {}).reason || '')}</p>
    ${(c.reaction || {}).available ? html`<h3>How markets took it</h3><ul class="plain cal-react">${c.reaction.assets.map((a) => html`<li>${a.name} <b class="${dir(a.change_pct)}">${signed(a.change_pct)}</b></li>`)}</ul><p class="asof">${clean(c.reaction.basis || '')}</p>` : ''}
    <h3>Optic's read of it</h3>
    ${rd.available ? html`<p><b>${clean(rd.headline || '')}</b></p>${(rd.paragraphs || []).map((p) => html`<p>${raw(bolded(p))}</p>`)}${generated(rd, { at: rd.written_at || rd.generated_at })}<p class="asof">${clean(rd.disclaimer || '')}</p>`
    : D.catWriting ? skeleton('lines', 3, 'Writing the read') : html`<p class="t-muted">Not written yet.</p><button type="button" class="btn btn-sm" data-v2-catread>Write the read</button><p class="asof">Written by an AI model when someone asks, then kept for an hour and shared with every reader.</p>`}
    <p class="asof">${clean(c.method || '')}</p>`;
}

function library() {
  const c = D.cats;
  if (c === undefined) return skeleton('lines', 3, 'Loading the catalyst library');
  if (!c || !c.available) return empty('The catalyst library is not available', clean((c || {}).reason || ''));
  const f = c.facets || {};
  const sel = (key, label, opts) => html`<label class="select"><span class="t-label">${label}</span><select data-v2-cat="${key}"><option value="">All</option>${opts.map((o) => html`<option value="${o}" ${cat[key] === o ? 'selected' : ''}>${capFirst(o)}</option>`)}</select></label>`;
  return html`<form class="op-filters" data-v2-cat-form><label class="field field-sm"><span class="sr">Search catalysts</span><input name="q" value="${cat.q}" placeholder="Search catalysts"></label><button type="submit" class="btn btn-sm">Search</button>
      <label class="select"><span class="t-label">Status</span><select data-v2-cat="status">${[['relevant', 'Relevant now'], ['archived', 'Archived'], ['all', 'All']].map(([v, l]) => html`<option value="${v}" ${cat.status === v ? 'selected' : ''}>${l}</option>`)}</select></label>
      ${sel('category', 'Category', f.categories || [])}${sel('sector', 'Sector', f.sectors || [])}${sel('theme', 'Theme', f.themes || [])}</form>
    ${(c.catalysts || []).length ? c.catalysts.map((k) => html`<details class="cat-card"><summary><span class="t-label">${[k.horizon, k.category, k.event_date ? shortDate(k.event_date) : ''].filter(Boolean).join(', ')}</span><b>${clean(k.title)}</b><span class="t-muted">${clean(k.summary || '')}</span></summary>
        ${(k.companies || []).length ? html`<div class="tscroll"><table class="t"><thead><tr><th>Company</th><th>How directly</th><th>Strength</th><th>Why</th></tr></thead><tbody>${k.companies.map((co) => html`<tr><td><a href="#/${co.ticker}">${co.ticker}</a> ${co.name || ''}</td><td>${co.directness || ''}</td><td>${co.strength || ''}</td><td>${clean(co.why || '')}</td></tr>`)}</tbody></table></div>` : ''}
        ${/^https?:/.test(k.source_url || '') ? html`<p><a class="textlink" href="${k.source_url}" target="_blank" rel="noopener">${k.source_name || 'Source'} ${icon('out')}</a></p>` : ''}</details>`)
      : html`<p class="quiet">${c.stored_total ? 'Nothing matches these filters.' : 'No catalysts stored yet.'}</p>`}
    <p class="asof">${c.stored_total} catalysts on record. ${(c.scan || {}).last_ok_at ? `Last scanned ${ago(c.scan.last_ok_at)}.` : 'Not scanned yet.'} ${clean(c.method || '')}</p>
    <button type="button" class="btn btn-sm" data-v2-cat-refresh ${D.catRefreshing ? 'disabled' : ''}>${D.catRefreshing ? 'Scanning…' : 'Scan for new catalysts'}</button>
    <p class="asof">A scan checks the news for new catalysts. One can run every 15 minutes.</p>`;
}

function weekly() {
  const w = D.weekly;
  if (w === undefined) return skeleton('lines', 4, "Loading this week's update");
  if (!w) return empty('The weekly update did not load', '');
  if (!w.available) {
    return html`<p>${clean(w.reason || 'Not written yet.')}</p>${w.not_written ? (D.weeklyWriting ? skeleton('lines', 3, 'Writing this week\'s update, about a minute') : html`<button type="button" class="btn btn-sm" data-v2-weekly-write>Write this week's update</button><p class="asof">Written by an AI model when someone asks, in about a minute, then kept for the week and shared with every reader.</p>`) : ''}`;
  }
  const e = (w.facts || {}).earnings;
  return html`<p class="t-label">Weekly market analysis</p><h3 class="t-h2">${clean(w.headline)}</h3>${w.subhead ? html`<p class="lede-line">${clean(w.subhead)}</p>` : ''}
    ${(w.paragraphs || []).map((p) => html`<p>${raw(bolded(p))}</p>`)}${generated(w, { at: w.written_at || w.generated_at })}
    ${e && (e.days || []).length ? html`<h3>Reporting this week, from the watchlist</h3><ul class="plain">${e.days.map((d) => html`<li><b>${d.day}</b>: ${(d.symbols || []).join(', ')}</li>`)}</ul>` : ''}
    <p class="asof">${clean(w.method || '')} ${clean(w.disclaimer || '')}</p>`;
}

function sentiment() {
  const s = D.sent;
  if (s === undefined) return skeleton('lines', 3, 'Loading Fear and Greed');
  if (!s || !s.available) return empty('Fear and Greed is not available', '');
  const h = s.history || {};
  return html`<div class="figure"><p class="t-display-m ${toneBand(s.label)}">${num(s.score, 0)} <small class="t-muted">of 100</small></p>${scoreLine(s.score, { tone: toneBand(s.label) })}<p class="delta"><span><b class="${toneBand(s.label)}">${s.label}</b></span>${['prev_close', 'week', 'month'].map((k) => (h[k] ? html`<span class="t-muted">${k === 'prev_close' ? 'Last close' : k === 'week' ? 'A week ago' : 'A month ago'} ${num(h[k].score, 0)} (${signed(h[k].change, 1, '')})</span>` : ''))}</p></div>
    <div class="tscroll"><table class="t"><thead><tr><th>Input</th><th>Weight</th><th>Score</th><th>Reading</th></tr></thead><tbody>${(s.components || []).map((c) => html`<tr><td>${c.label}<br><small class="t-muted">${clean(c.question || '')}</small></td><td>${num(c.weight_pct, 0)}%</td><td><span class="${toneBand(c.label_text)}">${num(c.score, 0)}</span> <small class="t-muted">${c.label_text}</small>${scoreLine(c.score, { tone: toneBand(c.label_text) })}</td><td style="text-align:left">${clean(c.reading || '')} <small class="t-muted">${clean(c.detail || '')}</small></td></tr>`)}</tbody></table></div>
    <p class="asof">${s.inputs_used} of ${s.inputs_total} inputs. ${clean(s.method || '')} ${clean(s.caveat || '')}</p>
    ${ask('Ask Milo what goes into this', 'What goes into Optic\'s Fear and Greed reading, and how should I use it?')}`;
}

function regime() {
  const r = (D.brief || {}).index_regime;
  if (!r || !r.available) return empty('No regime reading', '');
  const comps = Object.entries(r.components || {});
  return html`<div class="figure"><p class="t-display-m">${signed(r.score, 1, '')}</p><p class="delta"><span><b>${capFirst(r.stance || r.regime)}</b></span><span class="t-muted">${clean(r.plain || '')}</span></p></div>
    <p>${clean(r.effect || '')}</p>${TR.historySlot('regime')}
    <div class="tscroll"><table class="t"><thead><tr><th>Input</th><th>Weight</th><th>Reading</th><th>How it is scaled</th></tr></thead><tbody>${comps.map(([k, v]) => html`<tr><td>${capFirst(k)}</td><td>${num((r.weights || {})[k], 0)}%</td><td>${signed(v, 1, '')}</td><td style="text-align:left"><small>${clean((r.scales || {})[k] || '')}</small></td></tr>`)}</tbody></table></div>
    <p>${isNum(r.agreement_pct) ? `${num(r.agreement_pct, 0)}% of the inputs point the same way.` : ''} ${(r.conflicts || []).map(clean).join(' ')}</p>
    ${how(html`<p>Positive at +12, negative at −12. ${clean(r.scale_note || '')} ${clean(r.method || '')}</p>`)}`;
}

// The calendar (backlog task 9, 2026-10-20). Each day's macro releases and the week's company reports
// together, in time order; a release already out today says so; each date says whether the agency
// published it, it recurs on a rule, or it is estimated; a previous reading names the period it is for.
const ET_DAY = (() => { try { return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }); } catch (e) { return null; } })();
const dayOf = (iso) => { try { return ET_DAY ? ET_DAY.format(new Date(iso)) : String(iso).slice(0, 10); } catch (e) { return String(iso || '').slice(0, 10); } };
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
/** The period a reading is for, from its observation date: "September 2026", or "Q2 2026" for a quarterly series. */
export function periodOf(asOf, label) {
  const m = /^(\d{4})-(\d{2})/.exec(String(asOf || ''));
  if (!m) return '';
  const y = m[1], mo = Number(m[2]);
  return /quarter/i.test(label || '') ? `Q${Math.floor((mo - 1) / 3) + 1} ${y}` : `${MONTHS[mo - 1]} ${y}`;
}
const DATE_WORD = { published: (e) => `Date published by ${e.agency_short || e.agency || 'the agency'}`, recurring: () => 'Recurring date, set by rule', estimated: () => 'Estimated date, not yet published' };
const IMPACT_WORD = { high: 'High impact', medium: 'Medium impact', low: 'Low impact' };
/** One timeline: macro events, then the week's company reports from Today's priority, each with an ET day. */
export function calendarItems(c, pr, now = new Date()) {
  const today = dayOf(now), tomorrow = dayOf(new Date(now.getTime() + 86400000));
  const days = (d) => Math.round((Date.parse(`${d}T12:00:00Z`) - Date.parse(`${today}T12:00:00Z`)) / 86400000);
  // days and "released" from the clock now, not the Read's build: a Read built yesterday called today's
  // releases "tomorrow", and one built at 8 AM still called a 8:30 release due at noon
  const ev = (c.events || []).map((e) => { const day = e.at ? dayOf(e.at) : ''; return { ...e, kind: 'macro', day, days_away: day ? days(day) : e.days_away, released: !!(e.released || (e.at && !e.all_day && Date.parse(e.at) <= now.getTime())) }; });
  const col = ((pr || {}).columns || []).find((x) => x.id === 'earnings');
  // a report earlier in the week is out, said in the past tense by the ET day (pitch audit, 2026-10-22: Tuesday's
  // and Wednesday's reports were still listed as "reports" on Thursday); today's too once its figures are in, the
  // same test Home's rows use (priority row `result`, not pending)
  const reports = ((col || {}).rows || []).filter((r) => r.ticker && r.date).map((r) => { const day = String(r.date).slice(0, 10), away = days(day), out = away < 0 || !!(r.result && !r.result.pending); return { kind: 'report', day, days_away: away, released: out, title: out ? `${r.ticker} reported` : away === 0 ? `${r.ticker} reports today` : `${r.ticker} reports`, ticker: r.ticker, impact: r.impact, category: 'earnings', why: r.why }; });
  return { today, tomorrow, items: [...ev, ...reports].sort((a, b) => (a.day < b.day ? -1 : a.day > b.day ? 1 : (a.kind === 'report') - (b.kind === 'report') || String(a.at || '').localeCompare(String(b.at || '')))) };
}
function calItem(e) {
  if (e.kind === 'report') return html`<li class="cal-i ${e.released ? 'is-out' : ''}"><p class="cal-top"><b>${e.released ? 'Reported' : 'Company report'}</b> <a class="textlink" href="#/${e.ticker}/earnings">${e.title}</a> <span class="cal-imp">${IMPACT_WORD[e.impact] || ''}</span></p><p class="t-muted">${clean(e.why || '')}</p></li>`;
  const r = e.readings || {};
  const when = e.all_day ? 'All day' : e.time_label || '';
  const status = e.released ? `Released${when ? ` ${when}` : ''}` : when ? `Due ${when}` : 'Due';
  // the period is the previous figure's own (previous_as_of): once a release is out, `as_of` is the new print's, and a
  // Read built before the server said so names no period rather than the wrong one. A release still due by the clock
  // shows no released figure: a Read built at 7 AM on jobs day called September's payrolls November's (2026-10-20).
  const pAsOf = r.previous_as_of || (r.is_upcoming ? r.as_of : '');
  const prev = r.available && isNum(r.previous) ? `Previous reading${pAsOf ? `, for ${periodOf(pAsOf, r.series_label)}` : ''}: ${r.previous}${r.unit || ''}${r.series_label ? ` (${r.series_label.toLowerCase()})` : ''}.` : '';
  const actual = r.available && e.released ? (isNum(r.actual) ? ` Released: ${r.actual}${r.unit || ''}.` : ' The released figure has not reached the data feed yet.') : '';
  return html`<li class="cal-i ${e.released ? 'is-out' : ''}"><p class="cal-top"><b>${status}</b> ${/^https?:/.test(e.source_url || '') ? html`<a class="textlink" href="${e.source_url}" target="_blank" rel="noopener">${clean(e.title)}</a>` : clean(e.title)} <span class="cal-imp">${IMPACT_WORD[e.impact] || ''}</span></p>
    <p class="t-muted cal-meta">${(DATE_WORD[e.confidence] || (() => ''))(e)}${e.category ? `. ${capFirst(e.category)}` : ''}.</p>
    ${e.why ? html`<p class="cal-why">${clean(e.why)}</p>` : ''}
    ${prev || actual ? html`<p class="cal-read">${prev}${actual}</p>` : ''}
    ${e.previous && /^https?:/.test(e.previous.url || '') ? html`<p class="cal-read">Last release: <a class="textlink" href="${e.previous.url}" target="_blank" rel="noopener">${clean(e.previous.headline || 'the release')}</a></p>` : ''}</li>`;
}
function calendar() {
  const c = (D.brief || {}).calendar;
  if (D.briefErr) return html`<p class="quiet">The calendar comes with today's Read, which did not load. Try again above.</p>`;
  if (D.brief === undefined) return skeleton('lines', 4, 'Loading the calendar');
  if (!c) return empty('No calendar', 'The Read for today has no calendar yet.');
  const { today, tomorrow, items } = calendarItems(c, D.priority);
  const cats = [...new Set(items.map((e) => e.category).filter(Boolean))];
  const inRange = (e) => (cal.range === 'today' ? e.days_away === 0 : cal.range === 'week' ? e.days_away <= 6 : true);
  const inImpact = (e) => (cal.impact === 'all' ? true : cal.impact === 'high' ? e.impact === 'high' : e.category === cal.impact);
  const shown = items.filter((e) => e.days_away >= 0 && inRange(e) && inImpact(e));
  const days = [...new Set(shown.map((e) => e.day))];
  const name = (d) => (d === today ? `Today, ${etDay(d)}` : d === tomorrow ? `Tomorrow, ${etDay(d)}` : etDay(d));
  const noted = items.some((e) => (e.readings || {}).forecast_note);
  const reportsIn = !!((((D.priority || {}).columns || []).find((x) => x.id === 'earnings') || {}).rows || []).length;
  return html`<div class="chips" role="group" aria-label="Which releases"><button type="button" class="chip" data-v2-cal-impact="all" aria-pressed="${cal.impact === 'all'}">All</button><button type="button" class="chip" data-v2-cal-impact="high" aria-pressed="${cal.impact === 'high'}">High impact</button>${cats.map((k) => html`<button type="button" class="chip" data-v2-cal-impact="${k}" aria-pressed="${cal.impact === k}">${k === 'earnings' ? 'Company reports' : capFirst(k)} <span class="t-muted">${items.filter((e) => e.category === k).length}</span></button>`)}</div>
    <div class="seg" role="group" aria-label="When" style="margin-top:10px">${[['today', 'Today'], ['week', 'This week'], ['all', `Next ${c.horizon_days} days`]].map(([k, l]) => html`<button type="button" data-v2-cal-range="${k}" aria-pressed="${cal.range === k}">${l}</button>`)}</div>
    ${shown.length ? days.map((d) => { const xs = shown.filter((e) => e.day === d); return html`<h3 class="cal-day">${name(d)} <span class="t-muted">${xs.length}</span></h3><ul class="plain cal-list">${xs.map(calItem)}</ul>`; })
    : html`<p class="quiet">${items.length ? `Nothing in this window matches that filter. ${items.length} events scheduled overall.` : `Nothing scheduled in the next ${c.horizon_days} days.`}</p>`}
    <p class="asof">${(c.degraded || []).length ? `Not available right now: ${c.degraded.join(', ')}. ` : ''}Dates the agencies have published, plus recurring and estimated ones, each marked. Times are Eastern.${reportsIn ? " Company reports are this week's widely followed names, from Today's priority." : D.priority === undefined ? ' Company reports load with Today\'s priority.' : ''}${noted ? ' No consensus forecasts: they are surveyed and licensed, and the free sources publish what was released, not what was expected.' : ''}</p>`;
}

function headlines() {
  const w = (D.brief || {}).wires || {};
  return html`${w.lead ? html`<h3>Leading now</h3><ul class="nw-list">${headline(w.lead)}</ul>` : ''}
    ${(w.desks || []).map((d) => html`<h3>${d.label} <span class="t-muted">${(d.entries || []).length}</span></h3><ul class="nw-list">${(d.entries || []).slice(0, 8).map(headline)}</ul>`)}
    <p class="asof">${clean(w.window_note || '')}</p>`;
}
function releases() {
  const m = (D.brief || {}).macro || {}, b = D.brief || {};
  return html`${(m.entries || []).length ? html`<ul class="nw-list">${m.entries.map(headline)}</ul>` : html`<p class="quiet">Nothing published recently.</p>`}
    <h3>Where this comes from</h3><p>${clean(b.attribution || '')}</p>
    <ul class="plain">${[...(m.sources || []), ...((b.wires || {}).sources || [])].map((s) => html`<li>${s.name}${s.detail ? `, ${s.detail}` : ''}: ${s.error ? html`<span class="down">unreachable</span>` : `${s.count} items`}${s.access === 'paid' ? ', subscription' : ''}</li>`)}</ul>
    ${(b.degraded_sources || []).length ? html`<p class="stale">Not available on this refresh: ${b.degraded_sources.join(', ')}.</p>` : ''}
    <p><a class="textlink" href="#/insiders">Insider filings are on Insiders ${icon('arrow')}</a></p>`;
}

const TABS = [
  ['Overnight, worldwide', overnight], ["Today's priority", priority], ['Market catalyst', catalystMode], ['Catalyst library', library],
  ['Weekly analysis', weekly], ['Fear and Greed', sentiment], ['Market regime', regime], ['On the calendar', calendar], ['Headlines', headlines], ['Official releases and sources', releases],
];

function paint() {
  if (!live) return;
  const y = window.scrollY;
  draw(mainEl, html`<header class="page-head">${sectionHead('market', 'brief')}</header>
    ${readHero()}${desk()}
    <section class="section" aria-labelledby="rd-more-h"><h2 class="t-h2" id="rd-more-h">More from today</h2><div id="rd-more"></div></section>`);
  paintMore();
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}
// The ten views in three groups (item 13); every view and its name is kept.
const RGROUPS = [
  ['Today', ["Today's priority", 'Overnight, worldwide', 'Headlines', 'Official releases and sources']],
  ['Catalysts and calendar', ['On the calendar', 'Market catalyst', 'Catalyst library']],
  ['Sentiment and regime', ['Fear and Greed', 'Market regime', 'Weekly analysis']],
];
function paintMore() {
  const h = $('#rd-more', mainEl); if (!h) return;
  const item = (name) => { const [label, fn] = TABS.find((x) => x[0] === name); return { label, render: () => fn() }; };
  const ts = groupedTabs(RGROUPS.map(([label, names]) => ({ label, items: names.map(item) })), { label: 'More from today', state: tabState });
  draw(h, ts.html); ts.wire(h);
}

async function loadCats() {
  const q = new URLSearchParams({ limit: 30, status: cat.status });
  ['category', 'sector', 'theme', 'q'].forEach((k) => { if (cat[k]) q.set(k, cat[k]); });
  try { D.cats = await api.get(`/api/catalysts?${q}`, { ttl: 60000 }); } catch (e) { D.cats = null; }
  if (live) paintMore();
}

export async function render(main) {
  live = true; mainEl = main; tabState = { g: 0, s: {} };
  D = {};
  document.title = 'Read, Optic';
  provideContext(() => ({ view: 'brief', read: D.brief ? { day: D.brief.day, summary: D.brief.summary, overview: D.brief.overview, calendar: D.brief.calendar } : null, sentiment: D.sent }));
  paint(); wire(main);
  const step = (p, ok, bad, repaintAll) => p.then(ok, bad).finally(() => { if (live) (repaintAll ? paint() : paintMore()); });
  step(api.get('/api/brief?cached=true', { ttl: 60000, timeout: 30000 }), (d) => { D.brief = d; }, (e) => { D.briefErr = e; }, true);
  step(api.get('/api/desk/edition', { ttl: 300000 }), (d) => { D.desk = d; }, () => { D.desk = null; }, true);
  step(api.get('/api/priority', { ttl: 300000, timeout: 90000 }), (d) => { D.priority = d; }, () => { D.priority = null; });
  step(api.get('/api/catalyst-mode?cached=true', { ttl: 600000, timeout: 45000 }), (d) => { D.catmode = d; }, () => { D.catmode = null; });
  step(api.get('/api/weekly?cached=true', { ttl: 600000, timeout: 30000 }), (d) => { D.weekly = d; }, () => { D.weekly = null; });
  step(api.get('/api/sentiment', { ttl: 600000, timeout: 30000 }), (d) => { D.sent = d; }, () => { D.sent = null; });
  loadCats();
}
export function dispose() { live = false; }
export const retry = { brief: (m, r) => { api.invalidate('/api/brief'); render(m, r); } };

function wire(main) {
  let t;
  main.addEventListener('input', (e) => {
    if (!e.target.closest('[data-v2-read-search]')) return;
    clearTimeout(t); D.q = e.target.value.trim();
    t = setTimeout(runSearch, 220);
  });
  main.addEventListener('keydown', (e) => { if (e.key === 'Escape' && e.target.closest('[data-v2-read-search]')) { e.target.value = ''; D.q = ''; D.search = null; const r = $('#read-results', main); if (r) draw(r, ''); } });
  main.addEventListener('submit', (e) => {
    if (e.target.closest('[data-v2-read-search]')) { e.preventDefault(); clearTimeout(t); runSearch(); return; }
    const f = e.target.closest('[data-v2-cat-form]'); if (f) { e.preventDefault(); cat.q = f.q.value.trim(); loadCats(); }
  });
  main.addEventListener('change', (e) => { const s = e.target.closest('[data-v2-cat]'); if (s) { cat[s.dataset.v2Cat] = s.value; loadCats(); } });
  main.addEventListener('click', async (e) => {
    const b = (s) => e.target.closest(s);
    let x;
    if (b('[data-v2-read-build]')) { buildRead(); return; }
    if ((x = b('[data-v2-cal-impact]'))) { cal.impact = x.dataset.v2CalImpact; paintMore(); return; }
    if ((x = b('[data-v2-cal-range]'))) { cal.range = x.dataset.v2CalRange; paintMore(); return; }
    if (b('[data-v2-catread]')) {
      D.catWriting = true; paintMore();
      try { D.catmode = await api.get('/api/catalyst-mode', { ttl: 0, force: true, timeout: 90000 }); } catch (err) { toast(api.explain(err, 'The read'), { kind: 'bad' }); }
      D.catWriting = false; paintMore(); return;
    }
    if (b('[data-v2-weekly-write]')) {
      D.weeklyWriting = true; paintMore();
      try { D.weekly = await api.get('/api/weekly', { ttl: 0, force: true, timeout: 150000 }); } catch (err) { toast(api.explain(err, 'The weekly update'), { kind: 'bad' }); }
      D.weeklyWriting = false; paintMore(); return;
    }
    if (b('[data-v2-cat-refresh]')) {
      D.catRefreshing = true; paintMore();
      try { const r = await api.post('/api/catalysts/refresh', {}, { timeout: 120000 }); toast(clean((r && (r.message || r.reason)) || 'Scan finished.')); api.invalidate('/api/catalysts'); await loadCats(); }
      catch (err) { toast(err.message && err.kind !== 'server' ? err.message : api.explain(err, 'The scan'), { kind: 'bad' }); }
      D.catRefreshing = false; paintMore();
    }
  });
}
async function runSearch() {
  const r = $('#read-results', mainEl);
  if (!D.q) { D.search = null; if (r) draw(r, ''); return; }
  const my = (D.sseq = (D.sseq || 0) + 1);
  D.search = 'loading'; if (r) draw(r, searchResults());
  try { const res = await api.get(`/api/brief/search?q=${encodeURIComponent(D.q)}&limit=40`, { ttl: 60000 }); if (my !== D.sseq) return; D.search = res; }
  catch (err) { if (my !== D.sseq) return; D.search = { error: err }; }
  const r2 = $('#read-results', mainEl); if (r2) draw(r2, searchResults());
}
