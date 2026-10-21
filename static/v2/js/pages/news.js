// Dossier, News. Headlines for one company, scored and tagged by fixed rules
// (no model): the overall tone, a timeline in two lanes (about the company,
// market context), the catalyst types found, which filter the list, and the
// headlines by tier. From the shared /api/ticker snapshot's news block.
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { signed, num, clean, capFirst, esc, isNum } from '../core/format.js';
import { skeleton, empty, failed, how } from '../ui/states.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { core, header, tabs, isFund, livePrice } from './dossier-frame.js';
let lp = null;   // the header's price refresh (dossier-frame livePrice), stopped in dispose()

let D = {}, live = true, mainEl = null, filter = null;
const TIER_W = { breaking: 3, major: 3, notable: 2, background: 1 };
const toneShape = (t) => (/bullish/.test(t || '') ? 'up' : /bearish/.test(t || '') ? 'down' : 'flat');

function timeline(articles) {
  const now = Date.now();
  const pts = articles.map((a) => ({ a, t: Date.parse(a.published) })).filter((p) => Number.isFinite(p.t));
  if (pts.length < 2) return '';
  const t0 = Math.min(...pts.map((p) => p.t)), t1 = now;
  const W = 900, H = 150, l = 120, r = 20;
  const X = (t) => l + ((t - t0) / ((t1 - t0) || 1)) * (W - l - r);
  const lanes = [['About the company', 50], ['Market context', 110]];
  const marks = pts.map(({ a, t }, i) => {
    const y = a.about_company === false ? 110 : 50, x = X(t), s = 4 + 2.5 * (TIER_W[a.tier] || 1), shape = toneShape(a.tone);
    const label = `${clean(a.title)}. ${a.publisher}, ${a.age_words || ''}. ${capFirst(a.tier || '')}, ${(a.keywords || []).length ? a.tone : 'not scored'}.`;
    const g = shape === 'up' ? `<path d="M${x} ${y - s}L${x + s} ${y + s * 0.8}L${x - s} ${y + s * 0.8}Z"/>` : shape === 'down' ? `<path d="M${x} ${y + s}L${x + s} ${y - s * 0.8}L${x - s} ${y - s * 0.8}Z"/>` : `<circle cx="${x}" cy="${y}" r="${s * 0.8}"/>`;
    return `<g class="tl-m tl-${shape}">${g}<title>${esc(label)}</title></g>`;
  }).join('');
  const ticks = [0, 0.5, 1].map((f) => { const t = t0 + f * (t1 - t0); return `<text class="ax" x="${X(t).toFixed(1)}" y="${H - 6}" text-anchor="middle">${esc(new Date(t).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }))}</text>`; }).join('');
  const about = pts.filter((p) => p.a.about_company !== false).length;
  // a picture of the list below, which carries every link
  return `<svg class="timeline" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(`Timeline of ${pts.length} headlines, ${about} about the company and ${pts.length - about} on the market, from ${new Date(t0).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} to now. The same headlines are listed below.`)}">${lanes.map(([n, y]) => `<line class="lane" x1="${l}" x2="${W - r}" y1="${y}" y2="${y}"/><text class="lane-t" x="0" y="${y + 4}">${esc(n)}</text>`).join('')}${marks}${ticks}</svg>`;
}

function row(a) {
  // A tone is shown only when a scored term supports it; the terms are its evidence (owner, 2026-10-19).
  const terms = (a.keywords || []).map((k) => `${k.slice(1)} (${k[0] === '+' ? 'positive' : 'negative'})`);
  return html`<li class="nw"><div class="nw-top"><span class="pill" title="${a.tier_why || ''}">${capFirst(a.tier || '')}</span>${terms.length ? html`<span class="nw-tone ${toneShape(a.tone)}" title="Scored on: ${terms.join(', ')}">${capFirst(a.tone || 'mixed') === 'Neutral' ? 'Mixed' : capFirst(a.tone)}</span>` : html`<span class="nw-tone flat" title="No word in Optic's list of scored terms appears in this headline">Not scored</span>`}</div>
    <a class="nw-title" href="${a.url}" target="_blank" rel="noopener">${clean(a.title)}</a>
    <p class="t-muted">${a.publisher}, ${a.age_words || ''}</p>
    ${a.summary ? html`<p>${clean(a.summary).slice(0, 220)}${a.summary.length > 220 ? '…' : ''}</p>` : ''}
    ${(a.catalysts || []).length ? html`<p class="nw-tags">${a.catalysts.map((c) => html`<span class="flag">${c.type}</span>`)}</p>` : ''}</li>`;
}

function body(sym) {
  const n = (D.t || {}).news || {};
  const arts = n.articles || [];
  if (!arts.length) return empty('No headlines for this company right now', clean(n.reason || 'No recent headlines name it.'));
  const shown = filter ? arts.filter((a) => (a.catalysts || []).some((c) => c.type === filter)) : arts;
  const about = shown.filter((a) => a.about_company !== false), ctx = shown.filter((a) => a.about_company === false);
  const tc = n.tier_counts || {};
  return html`<section class="section" aria-labelledby="nt-h"><div class="section-head"><div><h2 class="t-h2" id="nt-h">News and catalysts</h2>
      <p class="section-sub"><span class="nw-tone ${toneShape(n.overall_tone)}">${capFirst(n.overall_tone || 'neutral')}</span> overall, net ${signed(n.net_sentiment, 2, '')} across ${n.article_count} headlines.</p>${how(html`<p>The net tone adds up each headline's score. Beyond ±0.5 it leans one way, beyond ±2 it is strong.</p>`)}</div>
      ${miloButton('Ask Milo about the news', { ask: `Which recent ${sym} headlines matter for the stock, and why?`, context: `${sym} Dossier, News`, symbol: sym })}</div>
    ${n.earnings_warning ? html`<p class="stale">${clean(n.earnings_warning)}</p>` : ''}${(n.held || {}).note ? html`<p class="stale">${clean(n.held.note)}</p>` : ''}
    <div class="chart-wrap tl-wrap">${raw(timeline(arts))}</div>
    <p class="legend-line"><span>▲ bullish</span><span>▼ bearish</span><span>● neither</span><span>Larger marks are breaking or major headlines.</span></p>
    ${(n.catalyst_summary || []).length ? html`<h3>Catalyst types found</h3><div class="chips" role="group" aria-label="Show headlines by catalyst">${n.catalyst_summary.map((c) => html`<button type="button" class="chip" data-v2-cat="${c.type}" aria-pressed="${filter === c.type}">${capFirst(c.type)} <span class="t-muted">${c.mentions}, ${c.lean}</span></button>`)}${filter ? html`<button type="button" class="textlink" data-v2-cat="">Show all</button>` : ''}</div>` : ''}
    <h3>About ${sym} <span class="t-muted">${about.length}</span></h3>${about.length ? html`<ul class="nw-list">${about.map(row)}</ul>` : html`<p class="quiet">None ${filter ? 'with this catalyst' : ''}.</p>`}
    ${ctx.length ? html`<h3>Market context <span class="t-muted">${ctx.length}</span></h3><ul class="nw-list">${ctx.map(row)}</ul>` : ''}
    <p class="asof">${(n.dropped || {}).total ? `Left out: ${n.dropped.filler || 0} filler and ${n.dropped.off_topic || 0} off-topic headlines.` : ''}</p>
    <details class="more-inline"><summary>How these are ranked</summary><ul class="plain">${(n.tiers || []).map((t) => html`<li><b>${t.label}</b> (${tc[t.id] || 0}): ${clean(t.rule)}</li>`)}</ul>
      <p>Matched on ${(n.matched_on || []).join(', ')}. A catalyst type has no direction of its own; its lean is the average tone of its headlines. These rules cannot read sarcasm, judge a source or know what the market already priced.</p><p class="asof">${clean(n.method || '')}</p></details>
  </section>`;
}

function paint() {
  if (!live) return;
  const sym = D.sym;
  draw(mainEl, html`<div class="dstick">${header(sym, D, 'news')}${tabs(sym, 'news', { fund: isFund(D) })}</div>${D.err ? failed('The headlines', D.err, { retry: 'news' }) : !D.t ? skeleton('rows', 5, 'Loading headlines') : body(sym)}`);
}

export async function render(main, route) {
  live = true; mainEl = main; filter = null;
  const sym = route.symbol;
  D = { sym };
  store.pushRecent(sym);
  document.title = `${sym} News, Optic`;
  if (lp) lp.stop();
  lp = livePrice(main, route.symbol, () => D, 'news', undefined);
  provideContext(() => ({ view: 'news', ticker: sym, news: (D.t || {}).news }));
  paint();
  main.addEventListener('click', (e) => {
    const c = e.target.closest('[data-v2-cat]');
    if (!c) return;
    filter = c.dataset.v2Cat || null; paint();
    const again = mainEl.querySelector(`[data-v2-cat="${filter || ''}"]`) || mainEl.querySelector('[data-v2-cat]'); if (again) again.focus();
  });
  core(sym).then((c) => { if (D.sym !== sym) return; D.quote = c.quote; D.session = c.session; D.quoteError = c.quoteError; paint(); });
  try { D.t = await api.get(`/api/ticker/${encodeURIComponent(sym)}?max_expiries=4&macro=true`, { ttl: 120000, timeout: 60000 }); }
  catch (e) { D.err = e; }
  if (D.sym === sym) paint();
}
export function dispose() { if (lp) { lp.stop(); lp = null; } live = false; }
export const retry = { news: (m, r) => render(m, r) };
void num; void isNum;
