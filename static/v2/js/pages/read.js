// Markets, Read. The day's Read (the market, the calendar, the wires), the
// Optic Desk edition, and the rest of the day's material one tab away.
//
// Paid pieces never load on their own. The Read itself, the weekly update and
// the catalyst read are asked for with `cached=true`, which serves only what is
// already written; the server's own loop keeps the Read current. Writing a
// missing piece is a labelled button, because it spends a model call.
import { $, html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, clean, capFirst, ago, shortDate, fullDate, isNum } from '../core/format.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { tabset } from '../ui/tabset.js';
import { toast } from '../ui/toast.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { groupTabs } from './tabs.js';

let D = {}, live = true, mainEl = null, tabState = 0, cal = { impact: 'all', range: 'week' }, cat = { status: 'relevant', category: '', sector: '', theme: '', q: '' };
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
    <h2 class="t-display-m" id="dk-h">${clean(e.headline || '')}</h2>
    ${e.summary ? html`<p class="lede-line">${clean(e.summary)}</p>` : ''}
    ${(e.sections || []).map((s) => html`<div class="desk-sec"><h3>${clean(s.title || capFirst(s.id || ''))}</h3>
      ${(s.items || s.claims || []).map((c) => html`<p>${clean(c.text || c)}${cites(c.cites)}</p>`)}</div>`)}
    <details class="more-inline"><summary>How this edition was made</summary><p>${clean(((e.outline || {}).limits || []).join(' '))}</p><p class="asof">Written by ${e.written_by || e.voice || 'the desk'}; gathered ${ago(e.gathered_at)}.</p></details>
  </section>`;
}

/* ---------------- the Read ---------------- */
function readHero() {
  const b = D.brief;
  if (D.briefErr) return failed("Today's Read", D.briefErr, { retry: 'brief' });
  if (!b) return skeleton('lines', 6, "Loading today's Read");
  if (b.missing) return empty("Today's Read has not been built yet", `${clean(b.reason || '')} The current app builds it on request.`, html`<a class="btn" href="/#/read">Open Read in the current app ${icon('out')}</a>`);
  const s = b.summary || {}, w = b.wires || {};
  const idx = ((b.overview || {}).groups || {}).indices || [];
  return html`${idx.length ? html`<div class="mstrip" style="--n:${idx.length}" role="group" aria-label="Indices">${idx.map((r) => html`<a class="mcell" href="#/${r.symbol}"><span class="k">${r.symbol} ${r.name}</span><span class="v">${num(r.last)}</span><span class="d ${r.day >= 0 ? 'up' : 'down'}">${signed(r.day)}</span></a>`)}</div>
      <p class="asof">Fund prices, not index levels.</p>` : ''}
    <section class="section read-hero" aria-labelledby="rd-h">
      <div class="section-head"><div><p class="t-label">Optic's Read, ${fullDate(b.day)}</p><h2 class="t-display-m" id="rd-h">${clean(s.headline || 'The Read')}</h2>
        <p class="section-sub">Updated ${ago(b.built_at)}${b.previous_day ? '. This is the previous day\'s Read while today\'s is built' : b.stale ? '. A newer one is due on the server\'s next pass' : ''}.${w.window_hours ? ` Covering the ${w.window_hours} hours since the previous session closed${w.window_hours >= 48 ? ', the whole weekend' : ''}.` : ''}</p></div>
        ${ask('Ask Milo about the Read', 'What matters most in today\'s Read, and what period does it cover?')}</div>
      <div class="read-prose">${(s.paragraphs || []).map((p) => (String(p).startsWith('## ') ? html`<h3>${clean(p.slice(3))}</h3>` : html`<p>${clean(p)}</p>`))}</div>
      <p class="asof">${s.written_at ? `Written ${ago(s.written_at)}. ` : ''}${clean(s.method || '')} ${clean((b.overview || {}).note || '')}</p>
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
      <div class="tscroll"><table class="t"><thead><tr><th>Market</th><th>Day</th><th>5 days</th><th>20 days</th><th>With the S&amp;P</th></tr></thead><tbody>${(s.rows || []).map((r) => html`<tr><td><a href="#/instrument/${encodeURIComponent(r.symbol)}">${r.label}</a> <small class="t-muted">${r.region || ''}</small></td><td class="${r.chg_1d >= 0 ? 'up' : 'down'}">${signed(r.chg_1d)}</td><td>${signed(r.chg_5d)}</td><td>${signed(r.chg_20d)}</td><td>${num(r.corr_spx, 2)} <small class="t-muted">${r.corr_spx >= g.corr_threshold ? 'linked' : 'loose'}</small></td></tr>`)}</tbody></table></div>`)}
    ${(g.crosses || []).length ? html`<h3>What carries it into US hours</h3><ul class="plain">${g.crosses.map((c) => html`<li><b>${c.label}</b> ${signed(c.chg_1d)}: ${clean(c.note)}. ${clean(c.corr_read)}.</li>`)}</ul>` : ''}
    <p class="asof">${g.linked_count} of ${g.market_count} markets move with the S&amp;P (correlation at or above ${num(g.corr_threshold, 2)} over ${g.corr_window} sessions). Moving together is not one causing the other. ${clean(g.method || '')}</p>`;
}

function priority() {
  const p = D.priority;
  if (p === undefined) return skeleton('lines', 4, "Loading today's priority");
  if (!p || !p.available) return empty('Nothing on the board right now', '');
  return html`${p.columns.map((c) => html`<h3>${c.name} <span class="t-muted">${c.total ?? (c.rows || []).length}</span></h3><p class="t-muted">${clean(c.blurb || '')}</p>
    ${(c.rows || []).length ? html`<ul class="plain">${c.rows.slice(0, 8).map((r) => html`<li>${r.ticker ? html`<a href="#/${r.ticker}"><b>${r.ticker}</b></a> ` : ''}<b>${clean(r.title)}</b> <span class="t-muted">${[r.when, r.time, r.impact ? `${r.impact} impact` : ''].filter(Boolean).join(', ')}</span>. ${clean(r.why || '')}</li>`)}</ul>` : html`<p class="quiet">Nothing here today.</p>`}`)}
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
    ${(c.reaction || {}).available ? html`<h3>How markets took it</h3><div class="chips">${c.reaction.assets.map((a) => html`<span class="pill">${a.name} <b class="${a.change_pct >= 0 ? 'up' : 'down'}">${signed(a.change_pct)}</b></span>`)}</div><p class="asof">${clean(c.reaction.basis || '')}</p>` : ''}
    <h3>Optic's read of it</h3>
    ${rd.available ? html`<p><b>${clean(rd.headline || '')}</b></p>${(rd.paragraphs || []).map((p) => html`<p>${clean(p)}</p>`)}<p class="asof">${clean(rd.disclaimer || '')}</p>`
    : D.catWriting ? skeleton('lines', 3, 'Writing the read') : html`<p class="t-muted">Not written yet.</p><button type="button" class="btn btn-sm" data-v2-catread>Write the read</button><p class="asof">Writing it uses a paid model; once written it is kept for an hour and shared with every reader.</p>`}
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
    <p class="asof">${c.stored_total} stored. ${(c.scan || {}).last_ok_at ? `Last scanned ${ago(c.scan.last_ok_at)}.` : 'Not scanned yet.'} ${clean(c.method || '')}</p>
    <button type="button" class="btn btn-sm" data-v2-cat-refresh ${D.catRefreshing ? 'disabled' : ''}>${D.catRefreshing ? 'Scanning…' : 'Scan for new catalysts'}</button>
    <p class="asof">A scan reads the news for new catalysts. Anyone may run one every 15 minutes; when the server reads with a model, a scan uses a paid call.</p>`;
}

function weekly() {
  const w = D.weekly;
  if (w === undefined) return skeleton('lines', 4, "Loading this week's update");
  if (!w) return empty('The weekly update did not load', '');
  if (!w.available) {
    return html`<p>${clean(w.reason || 'Not written yet.')}</p>${w.not_written ? (D.weeklyWriting ? skeleton('lines', 3, 'Writing this week\'s update, about a minute') : html`<button type="button" class="btn btn-sm" data-v2-weekly-write>Write this week's update</button><p class="asof">Writing it uses a paid model (a long piece, about a minute). It is written once a week and shared with every reader.</p>`) : ''}`;
  }
  const e = (w.facts || {}).earnings;
  return html`<p class="t-label">Weekly market analysis</p><h3 class="t-h2">${clean(w.headline)}</h3>${w.subhead ? html`<p class="lede-line">${clean(w.subhead)}</p>` : ''}
    ${(w.paragraphs || []).map((p) => html`<p>${clean(p)}</p>`)}
    ${e && (e.days || []).length ? html`<h3>Reporting this week, from the watchlist</h3><ul class="plain">${e.days.map((d) => html`<li><b>${d.day}</b>: ${(d.symbols || []).join(', ')}</li>`)}</ul>` : ''}
    <p class="asof">${clean(w.method || '')} ${clean(w.disclaimer || '')}</p>`;
}

function sentiment() {
  const s = D.sent;
  if (s === undefined) return skeleton('lines', 3, 'Loading Fear and Greed');
  if (!s || !s.available) return empty('Fear and Greed is not available', '');
  const h = s.history || {};
  return html`<div class="figure"><p class="t-display-m">${num(s.score, 0)} <small class="t-muted">of 100</small></p><p class="delta"><span><b>${s.label}</b></span>${['prev_close', 'week', 'month'].map((k) => (h[k] ? html`<span class="t-muted">${k === 'prev_close' ? 'Last close' : k === 'week' ? 'A week ago' : 'A month ago'} ${num(h[k].score, 0)} (${signed(h[k].change, 1, '')})</span>` : ''))}</p></div>
    <div class="tscroll"><table class="t"><thead><tr><th>Input</th><th>Weight</th><th>Score</th><th>Reading</th></tr></thead><tbody>${(s.components || []).map((c) => html`<tr><td>${c.label}<br><small class="t-muted">${clean(c.question || '')}</small></td><td>${num(c.weight_pct, 0)}%</td><td>${num(c.score, 0)} <small class="t-muted">${c.label_text}</small></td><td style="text-align:left">${clean(c.reading || '')} <small class="t-muted">${clean(c.detail || '')}</small></td></tr>`)}</tbody></table></div>
    <p class="asof">${s.inputs_used} of ${s.inputs_total} inputs. ${clean(s.method || '')} ${clean(s.caveat || '')}</p>
    ${ask('Ask Milo what goes into this', 'What goes into Optic\'s Fear and Greed reading, and how should I use it?')}`;
}

function regime() {
  const r = (D.brief || {}).index_regime;
  if (!r || !r.available) return empty('No regime reading', '');
  const comps = Object.entries(r.components || {});
  return html`<div class="figure"><p class="t-display-m">${signed(r.score, 1, '')}</p><p class="delta"><span><b>${capFirst(r.stance || r.regime)}</b></span><span class="t-muted">${clean(r.plain || '')}</span></p></div>
    <p>${clean(r.effect || '')}</p>
    <div class="tscroll"><table class="t"><thead><tr><th>Input</th><th>Weight</th><th>Reading</th><th>How it is scaled</th></tr></thead><tbody>${comps.map(([k, v]) => html`<tr><td>${capFirst(k)}</td><td>${num((r.weights || {})[k], 0)}%</td><td>${signed(v, 1, '')}</td><td style="text-align:left"><small>${clean((r.scales || {})[k] || '')}</small></td></tr>`)}</tbody></table></div>
    <p>${isNum(r.agreement_pct) ? `${num(r.agreement_pct, 0)}% of the inputs point the same way.` : ''} ${(r.conflicts || []).map(clean).join(' ')}</p>
    <p class="asof">Positive at +12, negative at −12. ${clean(r.scale_note || '')} ${clean(r.method || '')}</p>`;
}

function calendar() {
  const c = (D.brief || {}).calendar;
  if (!c) return empty('No calendar', '');
  const ev = c.events || [];
  const cats = [...new Set(ev.map((e) => e.category).filter(Boolean))];
  const inRange = (e) => (cal.range === 'today' ? e.days_away === 0 : cal.range === 'week' ? e.days_away <= 6 : true);
  const inImpact = (e) => (cal.impact === 'all' ? true : cal.impact === 'high' ? e.impact === 'high' : e.category === cal.impact);
  const shown = ev.filter((e) => inRange(e) && inImpact(e));
  const groups = [...new Set(shown.map((e) => e.when_label))];
  return html`<div class="chips" role="group" aria-label="Which releases"><button type="button" class="chip" data-v2-cal-impact="all" aria-pressed="${cal.impact === 'all'}">All</button><button type="button" class="chip" data-v2-cal-impact="high" aria-pressed="${cal.impact === 'high'}">High impact</button>${cats.map((k) => html`<button type="button" class="chip" data-v2-cal-impact="${k}" aria-pressed="${cal.impact === k}">${capFirst(k)} <span class="t-muted">${ev.filter((e) => e.category === k).length}</span></button>`)}</div>
    <div class="seg" role="group" aria-label="When" style="margin-top:10px">${[['today', 'Today'], ['week', 'This week'], ['all', `Next ${c.horizon_days} days`]].map(([k, l]) => html`<button type="button" data-v2-cal-range="${k}" aria-pressed="${cal.range === k}">${l}</button>`)}</div>
    ${shown.length ? groups.map((g) => html`<h3>${g}</h3><ul class="plain">${shown.filter((e) => e.when_label === g).map((e) => html`<li><b>${e.time_label || 'All day'}</b> ${/^https?:/.test(e.source_url || '') ? html`<a href="${e.source_url}" target="_blank" rel="noopener">${clean(e.title)}</a>` : clean(e.title)} <span class="pill">${e.impact} impact</span> <span class="t-muted">${e.agency_short || ''}${e.confidence !== 'published' ? `, date ${e.confidence}` : ''}</span><br><span class="t-muted">${clean(e.why || '')}</span>${(e.readings || {}).available ? html`<br><small>Previous ${e.readings.previous}${e.readings.unit || ''}${e.readings.is_upcoming ? ', actual pending' : `, actual ${e.readings.actual}${e.readings.unit || ''}`}</small>` : ''}</li>`)}</ul>`)
    : html`<p class="quiet">${ev.length ? `Nothing in this window matches that filter. ${ev.length} releases scheduled overall.` : `Nothing scheduled in the next ${c.horizon_days} days.`}</p>`}
    <p class="asof">${(c.degraded || []).length ? `Not available right now: ${c.degraded.join(', ')}. ` : ''}Dates the agencies have published, plus recurring and estimated ones marked as such.</p>`;
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
    <p><a class="textlink" href="/#/insiders">Insider filings are on Insiders ${icon('arrow')}</a></p>`;
}

const TABS = [
  ['Overnight, worldwide', overnight], ["Today's priority", priority], ['Market catalyst', catalystMode], ['Catalyst library', library],
  ['Weekly analysis', weekly], ['Fear and Greed', sentiment], ['Market regime', regime], ['On the calendar', calendar], ['Headlines', headlines], ['Official releases and sources', releases],
];

function paint() {
  if (!live) return;
  const y = window.scrollY;
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">Read</h1>${groupTabs('market', 'brief')}</header>
    ${desk()}${readHero()}
    <section class="section" aria-label="More from today"><h2 class="t-h2">More from today</h2><div id="rd-more"></div></section>`);
  paintMore();
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}
function paintMore() {
  const h = $('#rd-more', mainEl); if (!h) return;
  const ts = tabset(TABS.map(([label, fn]) => ({ label, render: () => fn() })), { label: 'More from today', selected: tabState });
  draw(h, ts.html); ts.wire(h, (i) => { tabState = i; });
}

async function loadCats() {
  const q = new URLSearchParams({ limit: 30, status: cat.status });
  ['category', 'sector', 'theme', 'q'].forEach((k) => { if (cat[k]) q.set(k, cat[k]); });
  try { D.cats = await api.get(`/api/catalysts?${q}`, { ttl: 60000 }); } catch (e) { D.cats = null; }
  if (live) paintMore();
}

export async function render(main) {
  live = true; mainEl = main; tabState = 0;
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
