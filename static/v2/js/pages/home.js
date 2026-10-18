// Home. Two states from one page:
//   new:       nothing followed and no linked portfolio. A welcome with search
//              first, a short illustration, names to follow and today's market.
//   returning: the reader's portfolio (when a brokerage is linked) or the
//              market's expected move, then their watchlist, what matters
//              today, the Desk, and what moved most this month.
// Each block loads on its own and shows its own loading, empty, stale and
// failed state, so a slow source never holds the rest of the page.
import { $, $$, html, render as draw, raw } from '../core/dom.js';
import { CLASSIC } from '../core/classic.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, signed, dir, money, signedMoney, clean, ago, shortDate, isNum } from '../core/format.js';
import { lineChart, spark, mountCharts } from '../ui/chart.js';
import { skeleton, empty, failed, staleLine } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { row as watchRow, openCompany } from '../ui/company.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { art } from '../ui/art.js';
import { go } from '../core/router.js';

const STRIP = [
  { group: 'equity', label: 'S&P 500', overnight: { group: 'futures', label: 'S&P 500 futures' } },
  { group: 'equity', label: 'Nasdaq 100', overnight: { group: 'futures', label: 'Nasdaq 100 futures' } },
  { group: 'equity', label: 'Russell 2000', overnight: { group: 'futures', label: 'Russell 2000 futures' } },
  { group: 'volatility', label: 'VIX' },
  { group: 'rates', label: 'US 10Y' },
  { group: 'commodities', label: 'WTI Crude' },
  { group: 'commodities', label: 'Gold' },
  { group: 'crypto', label: 'Bitcoin' },
];
const STARTERS = ['AAPL', 'NVDA', 'MSFT', 'SPY'];
const STARTER_NAMES = { AAPL: 'Apple', NVDA: 'NVIDIA', MSFT: 'Microsoft', SPY: 'S&P 500 ETF' };

let timer = null;
let live = true;
let ctx = {};

const etTime = (iso) => { try { return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' }) + ' ET'; } catch (e) { return ''; } };
const etDate = (iso) => { try { return new Date(iso || Date.now()).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'America/New_York' }); } catch (e) { return ''; } };
function hello() {
  const h = new Date().getHours();
  const part = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  const u = store.state.user;
  return u && u.first_name ? `${part}, ${u.first_name}` : part;
}

/* ---------------- market strip ---------------- */
function inst(data, group, label) { return ((((data || {}).macro || {}).groups || {})[group] || []).find((r) => r.label === label) || null; }
function moveLabel(i) {
  const chg = i.chg_1d;
  if (!isNum(chg)) return null;
  if (i.group === 'rates' && isNum(i.last) && chg > -100) {
    const bp = Math.round((i.last - i.last / (1 + chg / 100)) * 100);
    return `${bp > 0 ? '+' : bp < 0 ? '−' : ''}${Math.abs(bp)} bp`;
  }
  return signed(chg);
}
function strip(data) {
  const overnight = (data.session || {}).phase === 'overnight';
  const cells = STRIP.map((r) => (overnight && r.overnight ? r.overnight : r)).map(({ group, label }) => {
    const i = inst(data, group, label);
    if (!i || !isNum(i.last)) return '';
    const dp = i.last < 20 ? 2 : i.last > 1000 ? 0 : 2;
    return html`<a class="mcell" href="#/instrument/${encodeURIComponent(i.symbol)}"><span class="k">${label}</span><span class="v">${num(i.last, dp)}</span><span class="d ${dir(i.chg_1d)}">${moveLabel(i) || ''}</span></a>`;
  });
  const regular = (data.session || {}).phase === 'regular';
  return html`<div class="mstrip" role="group" aria-label="Market snapshot">${cells}</div>
    <p class="asof">As of ${etTime(data.generated_at)}. ${regular ? '' : 'Futures and crypto trade now; the rest are at the last close.'}</p>`;
}

/* ---------------- the statement panel: the market's expected move ---------------- */
function scene(data, series) {
  const em = (data.macro || {}).expected_move || {};
  if (!isNum(em.implied_pct) || !isNum(em.spot)) return '';
  const hi = em.spot + em.implied_points, lo = em.spot - em.implied_points;
  const real = isNum(em.realized_pct) && em.realized_pct > 0;
  ctx.scene = { series, cone: { lo, hi } };
  return html`<section class="scene" aria-labelledby="scene-h">
    <div class="lens"><p class="lens-k"><span>S&amp;P 500, the past three months</span><b>Gold: one session, as options price it</b></p>
      <div class="chart-slot" data-chart="spx">${series ? '' : skeleton('chart')}</div></div>
    <div class="copy">
      <p class="kicker" id="scene-h">The S&amp;P 500, next session</p>
      <p class="big">±${num(em.implied_pct, 2)}%</p>
      <p class="big-cap">The one-day move options price, from the VIX: about ${num(em.implied_points, 0)} points either way from ${num(em.spot, 0)} (VIX ${num(em.vix, 1)} ÷ 16).</p>
      ${real && isNum(em.ratio) ? html`<p class="second"><b>${num(em.ratio, 1)}×</b><span>= ±${num(em.implied_pct, 2)}% priced ÷ ±${num(em.realized_pct, 2)}%, the index's own recent day (its 14-day average range, ${num(em.atr_pct, 2)}%, ÷ 1.6).</span></p>` : ''}
      <p class="claim">${clean(em.reading || '')}</p>
      <div class="acts"><a class="btn btn-light" href="#/macro">See the macro picture</a><a class="btn" href="#/explore">What moved most</a>${miloButton('Ask Milo about today', { ask: 'What matters for the market in the next session?', context: 'Home, the market today' })}</div>
    </div>
    <p class="src">Source: Yahoo Finance index and VIX quotes, ${etTime(data.generated_at)}. ${clean((data.session || {}).label || '')}.</p>
  </section>`;
}

/* ---------------- portfolio (linked brokerage) ---------------- */
function portfolio(ov, perf) {
  const vn = ov.value_now;
  const v = isNum(vn) ? vn : (vn && isNum(vn.value) ? vn.value : (ov.totals || {}).value);
  const today = ov.today || {};
  const series = ((perf || {}).series || []).filter((p) => isNum(p.value)).map((p) => ({ d: String(p.date).slice(0, 10), c: Number(p.value) }));
  ctx.portfolio = series;
  const twr = (((perf || {}).returns || {}).twr || {}).pct;
  const rows = (today.rows || []).slice().sort((x, y) => Math.abs(y.contribution || 0) - Math.abs(x.contribution || 0));
  const sync = ((ov.freshness || {}).broker || {}).newest_sync;
  const brokerTotal = ((ov.totals || {}).combined_usd || {}).value;
  const src = ((perf || {}).sources || {});
  const srcWords = { provider_estimate: "your data provider's estimated daily balances", collected: 'snapshots Optic collected at each sync', mixed: "the provider's estimates, then Optic's own snapshots", none: 'no value history yet' }[src.values] || src.values || '';
  const switches = (src.switches || []).map((x) => shortDate(x.date));
  return html`<section class="figure hero" aria-labelledby="pf-h">
    <p class="t-label" id="pf-h">Your portfolio, value now${ov.holdings_count ? html`<span class="pill">${ov.holdings_count} holdings</span>` : ''}</p>
    <p class="t-display">${money(v)}</p>
    <p class="delta">${isNum(today.total) ? html`<span class="${dir(today.total)}">${signedMoney(today.total)} (${signed(today.total_pct)}) on the day</span>` : ''}${isNum(brokerTotal) && Math.abs(brokerTotal - v) > 1 ? html`<span class="t-muted">Your broker's own total: ${money(brokerTotal)}${sync ? `, ${ago(sync)}` : ''}</span>` : ''}</p>
    ${series.length > 1 ? html`<p class="pf-chart-k">Account value as your broker reported it, three months. It includes your own deposits and withdrawals, so it is not a return.${switches.length ? ` The source changes on ${switches.join(', ')}.` : ''}</p><div class="chart-slot" data-chart="portfolio"></div>` : html`<p class="asof">The value chart fills in as daily snapshots accumulate.</p>`}
    ${isNum(twr) ? html`<p class="pf-twr"><b>${signed(twr)}</b> time-weighted over the period, measured from ${srcWords}.${switches.length ? ' A change of source inside the period moves this figure, so read it with the chart.' : ''}</p>` : ''}
    ${rows.length ? html`<div class="pf-rows" role="table" aria-label="Holdings, by their effect on the day">
      <div class="pf-row pf-head" role="row"><span role="columnheader">Holding</span><span role="columnheader" class="num">Price</span><span role="columnheader" class="num">Day</span><span role="columnheader" class="num">Effect</span></div>
      ${rows.slice(0, 6).map((r) => html`<a class="pf-row" role="row" href="#/${r.symbol}"><span role="cell"><b class="tick">${r.symbol}</b> <small class="t-muted">${num(r.quantity, 0)} shares</small></span><span role="cell" class="num">${num(r.price)}</span><span role="cell" class="num ${dir(r.change_pct)}">${signed(r.change_pct)}</span><span role="cell" class="num ${dir(r.contribution)}">${signedMoney(r.contribution, 0)}</span></a>`)}</div>` : ''}
    <p class="asof">${clean((vn && vn.basis) || '')}${sync ? ` Last sync ${ago(sync)}.` : ''}</p>
    <div class="cluster"><a class="textlink" href="#/brokerage/holdings">All holdings ${icon('arrow')}</a><a class="textlink" href="#/brokerage/performance">Performance ${icon('arrow')}</a></div>
  </section>`;
}

/* ---------------- what matters today ---------------- */
function bucket(r) {
  const d = Number(r.days_away);
  if (r.kind === 'sector') return 'Now';
  if (d === 0 || r.when === 'Today') return 'Today';
  return 'This week';
}
function eventsBlock(pr, followed, filter) {
  const cols = (pr.columns || []);
  const rows = [];
  cols.forEach((c) => (c.rows || []).forEach((r) => rows.push(Object.assign({ col: c.id }, r))));
  const mine = rows.filter((r) => r.ticker && followed.includes(r.ticker));
  const shown = filter === 'mine' ? mine : rows.filter((r) => r.col !== 'movers');
  if (!rows.length) return empty('Nothing scheduled that moves the market', 'No major releases, earnings or sector moves in the next few days.');
  const byDate = (a, b) => String(a.date || '').localeCompare(String(b.date || '')) || (a.impact === 'high' ? -1 : 0);
  const groups = ['Now', 'Today', 'This week'].map((b) => [b, shown.filter((r) => bucket(r) === b).sort(byDate)]).filter(([, l]) => l.length);
  let n = 0;
  const item = (r) => { n += 1; const id = `ev-${n}`; return html`<div class="ev">
        <button type="button" class="ev-head" aria-expanded="false" aria-controls="${id}" data-v2-ev>
          <span class="who">${r.kind === 'sector' ? 'Sector' : r.ticker || r.short || ''}</span>
          <span class="what">${clean(r.title)}<small>${[r.when, r.time, r.impact ? `${r.impact} impact` : ''].filter(Boolean).join(', ')}</small></span>
          <span class="ch">${r.ticker && followed.includes(r.ticker) ? html`<span class="pill">On your list</span>` : ''}</span>${icon('chev')}</button>
        <div class="ev-body" id="${id}" hidden><p>${clean(r.why || '')}</p>${r.ticker ? html`<div class="cluster"><a class="textlink" href="#/${r.ticker}">Open ${r.ticker} ${icon('arrow')}</a></div>` : ''}</div></div>`; };
  return html`<div class="chips" role="group" aria-label="Show">
      <button type="button" class="chip" data-v2-evfilter="all" aria-pressed="${filter !== 'mine'}">Everything</button>
      <button type="button" class="chip" data-v2-evfilter="mine" aria-pressed="${filter === 'mine'}">Your names <span class="t-muted">${mine.length}</span></button></div>
    ${groups.length ? groups.map(([b, list], gi) => html`<p class="group-h"><b>${b}</b>${b === 'Now' ? 'Sector moves' : b === 'Today' ? 'Releases and reports' : `Through the next ${pr.horizon_days || 5} days`}</p>
      ${list.slice(0, 3).map(item)}
      ${list.length > 3 ? html`<div id="evmore-${gi}" hidden>${list.slice(3).map(item)}</div>
        <button type="button" class="textlink ev-more" aria-expanded="false" aria-controls="evmore-${gi}" data-v2-evmore="${list.length - 3}">Show ${list.length - 3} more</button>` : ''}`)
      : html`<p class="quiet">None of your names has an event in the next ${pr.horizon_days || 5} days.</p>`}
    <p class="asof">Updated ${ago(pr.generated_at)}.</p>
    <details class="method"><summary>How this is sorted</summary><p>${clean(pr.method || '')}</p></details>`;
}

/* ---------------- the Desk ---------------- */
function desk(md) {
  if (!md || !md.available) return '';
  const lead = (md.lead || []).map(clean);
  return html`<section class="section" aria-labelledby="desk-h">
    <div class="section-head"><div><h2 class="t-h2" id="desk-h">${md.title || 'Optic Desk'}</h2><p class="section-sub">${md.voice === 'mechanical' ? 'Written from the numbers by fixed rules today.' : 'The day\'s edition.'} ${md.date ? `For ${shortDate(md.date)}.` : ''}</p></div>
      ${miloButton('Ask Milo about the Desk', { ask: 'Walk me through today\'s Desk.', context: 'Home, Optic Desk' })}</div>
    <ul class="desk-lead">${lead.map((l) => html`<li>${l}</li>`)}</ul>
    ${md.overall ? html`<details class="more"><summary>The full read ${icon('chev')}</summary><div class="inner"><p>${clean(md.overall)}</p>${md.note ? html`<p class="t-muted">${clean(md.note)}</p>` : ''}</div></details>` : ''}
  </section>`;
}

/* ---------------- movers ---------------- */
function movers(m) {
  const rows = (m && (m.rows || m.results || m.movers)) || [];
  if (m && m.building) return empty('The ranking is still being built', clean(m.reason || 'It runs in the background and appears here when it finishes.'));
  if (!rows.length) return empty('Nothing to rank right now', clean((m && m.reason) || 'The month\'s movers appear once the background ranking has run.'));
  return html`<ol class="movers">${rows.slice(0, 6).map((r) => html`<li><a href="#/${r.symbol || r.ticker}"><b class="tick">${r.symbol || r.ticker}</b><span class="${dir(r.roc20 ?? r.change_pct)}">${signed(r.roc20 ?? r.change_pct, 1)}</span></a></li>`)}</ol>
    <p class="asof">The 20-session change, ranked by size either way.</p>`;
}

/* ---------------- new user ---------------- */
function welcome(data) {
  const spx = inst(data, 'equity', 'S&P 500');
  return html`<section class="welcome" aria-labelledby="wel-h">
    <div class="copy">
      <p class="kicker">Stock and options research</p>
      <h1 id="wel-h">See what moves a stock, and why.</h1>
      <p>Prices, options and filings for any US company, read in plain words, with the evidence one step away.</p>
      <form class="wel-form" role="search" data-v2-search-form>
        <label class="field">${icon('search')}<span class="sr">Company or ticker</span><input name="q" placeholder="Try AAPL or Nvidia" autocomplete="off" spellcheck="false"></label>
        <button type="submit" class="btn btn-light">Open</button>
      </form>
    </div>
    <figure class="art">${raw(art(ctx.sceneSeries || []))}
      ${spx && isNum(spx.chg_120d) ? html`<figcaption class="art-cap"><span>S&amp;P 500</span><b class="${dir(spx.chg_120d)}">${signed(spx.chg_120d, 1)}</b>over six months</figcaption>` : ''}</figure>
  </section>`;
}

function starters(rows) {
  return html`<div class="starters">${STARTERS.map((s) => {
    const r = (rows || []).find((x) => x.symbol === s) || { symbol: s };
    const on = store.isFollowed(s);
    return html`<button type="button" class="starter" data-v2-watch="${s}" aria-pressed="${on}">
      <span class="st-top"><b class="tick">${s}</b><span class="${dir(r.change_pct)}">${isNum(r.change_pct) ? signed(r.change_pct) : ''}</span></span>
      <span class="t-muted">${STARTER_NAMES[s]}${isNum(r.price) ? html`, ${num(r.price)}` : ''}</span>
      ${raw(spark(r.spark, `${s}, last 30 sessions`))}
      <span class="follow">${on ? 'Following' : 'Follow'}</span></button>`;
  })}</div>
  ${store.allSymbols().length ? html`<div class="cluster st-done"><button type="button" class="btn btn-primary" data-v2-home-ready>See your Home</button><span class="t-muted">Following ${store.allSymbols().join(', ')}.</span></div>` : ''}`;
}

function modes(list) {
  let cur = null; try { cur = localStorage.getItem('optic.knowledge.v1'); } catch (e) { /* private */ }
  return html`<div class="modes" role="radiogroup" aria-label="How should Optic speak to you?">${list.map((m) => html`<button type="button" class="mode" role="radio" aria-checked="${cur === m.id}" data-v2-mode="${m.id}"><b>${m.label}</b><span>${clean(m.tagline || m.blurb || '')}</span></button>`)}</div>
    <button type="button" class="textlink" data-v2-mode="">Skip for now</button>`;
}

/* ---------------- page ---------------- */
export async function render(main) {
  live = true; ctx = {};
  clearInterval(timer);
  provideContext(() => ({ view: 'home', macro: ctx.home && ctx.home.macro, read: ctx.home && ctx.home.read }));
  const followed = store.allSymbols();
  const isNew = !followed.length && !ctx.linked;
  render_(main, isNew);
  wire(main);
  loadHome(main, isNew);
  if (isNew) loadStarters(main);
  else { loadWatch(main); loadPriority(main); loadMovers(main); }
  if (store.signedIn()) loadBrokerage(main);
  // Refresh the market while the page is open and visible.
  timer = setInterval(() => { if (live && document.visibilityState === 'visible') loadHome(main, isNew, { quiet: true }); }, 60000);
}

export function dispose() { live = false; clearInterval(timer); }

function render_(main, isNew) {
  const list = store.activeList();
  draw(main, html`
    <header class="home-head"><h1 class="t-h2">${hello()}</h1><p class="t-muted" id="home-date">${etDate()}</p></header>
    <div id="hm-strip">${skeleton('lines', 2, 'Loading the market')}</div>
    ${isNew ? html`<div id="hm-welcome">${skeleton('chart', 1, 'Loading')}</div>
      <section class="section" aria-labelledby="st-h"><div class="section-head"><div><h2 class="t-h2" id="st-h">Follow a few names to start</h2>
        <p class="section-sub">${store.signedIn() ? 'They go into your account\'s watchlist.' : 'Kept in this browser. Sign in to keep them on your account.'} Home fills in around what you follow.</p></div></div>
        <div id="hm-starters">${skeleton('rows', 2)}</div></section>
      <section class="section" id="hm-modes" hidden aria-labelledby="md-h"><div class="section-head"><div><h2 class="t-h2" id="md-h">How should Optic speak to you?</h2><p class="section-sub">Change it any time in Settings.</p></div></div><div id="hm-modes-in"></div></section>
      <section class="section" aria-labelledby="pa-h"><h2 class="sr" id="pa-h">Ways to start</h2><div class="paths">
        <div class="path"><p class="t-h3">Look up a company</p><p>Every Dossier answers four questions first: the business, the price, the trade and what is next.</p><button type="button" class="textlink" data-v2-open-palette>Search ${icon('arrow')}</button></div>
        <div class="path"><p class="t-h3">Read today's market</p><p>The day's read, the macro regime and the index cycles.</p><a class="textlink" href="#/read">Open Read ${icon('arrow')}</a></div>
        <div class="path"><p class="t-h3">${store.signedIn() ? 'Set alerts' : 'Keep it on an account'}</p><p>${store.signedIn() ? 'Watches check your conditions every 30 minutes and record what fired.' : 'A free account keeps your watchlists and alerts on any device.'}</p>${store.signedIn() ? html`<a class="textlink" href="#/alerts">Alerts ${icon('arrow')}</a>` : html`<a class="textlink" href="#/signin">Sign in or create one ${icon('arrow')}</a>`}</div>
      </div></section>`
    : html`<div id="hm-hero"></div><div id="hm-scene">${skeleton('chart', 1, 'Loading the market')}</div>
      <section class="section" aria-labelledby="wl-h"><div class="section-head"><div><h2 class="t-h2" id="wl-h">${list ? list.name : 'Your watchlist'}</h2><p class="section-sub">Price, today's move, 30 sessions and what changed. Choose a row for the detail.</p></div>
        <a class="textlink" href="#/watchlist">All of it ${icon('arrow')}</a></div><div id="hm-watch">${skeleton('rows', 4)}</div></section>
      <section class="section" aria-labelledby="pr-h"><div class="section-head"><div><h2 class="t-h2" id="pr-h">What matters today</h2><p class="section-sub">The calendar, this week's earnings and the sector board, sorted by when they land.</p></div></div>
        <div id="hm-priority">${skeleton('lines', 4, 'Loading what matters today')}</div></section>
      <div id="hm-desk"></div>
      <section class="section" aria-labelledby="mv-h"><div class="section-head"><div><h2 class="t-h2" id="mv-h">Moved most this month</h2></div><a class="textlink" href="#/scan">All scans ${icon('out')}</a></div><div id="hm-movers">${skeleton('lines', 2)}</div></section>
      <div id="hm-alerts"></div>`}
  `);
}

async function loadHome(main, isNew, { quiet } = {}) {
  let data;
  try {
    data = await api.get('/api/home', { ttl: 20000, force: !!quiet, timeout: 30000 });
  } catch (e) {
    if (quiet) return;
    draw($('#hm-strip', main), failed('The market summary', e, { retry: 'home' }));
    const sc = $(isNew ? '#hm-welcome' : '#hm-scene', main);
    if (sc) draw(sc, isNew ? welcome({}) : '');
    if (isNew) wireForms(main);
    return;
  }
  if (!live) return;
  ctx.home = data;
  const d = $('#home-date', main);
  if (d) d.textContent = `${etDate((data.session || {}).now_et)}. ${clean((data.session || {}).label || '')}.`;
  draw($('#hm-strip', main), html`${strip(data)}${(data.degraded || []).length ? staleLine({ degraded: data.degraded }) : ''}`);
  if (quiet && ctx.drawn) return;
  // the index's own dated closes for the panel and the illustration
  let series = null;
  try {
    const r = await api.get('/api/instrument?symbol=%5EGSPC&range=6mo', { ttl: 300000, timeout: 15000 });
    series = (r.dates || []).map((dd, i) => ({ d: String(dd).slice(0, 10), c: Number(r.close[i]) })).filter((p) => isNum(p.c));
  } catch (e) { series = null; }
  if (!live) return;
  ctx.drawn = true;
  if (isNew) {
    ctx.sceneSeries = series || [];
    draw($('#hm-welcome', main), welcome(data));
    wireForms(main);
    loadModes(main);
  } else {
    const sc = $('#hm-scene', main);
    draw(sc, scene(data, series && series.slice(-63)));
    const s3 = series ? series.slice(-63) : null;
    if (s3 && s3.length > 2) {
      mountCharts(sc, { spx: (w) => lineChart(s3, { w, h: Math.round(Math.max(200, Math.min(300, w * 0.5))), label: 'S&P 500 closing level', dp: 0, future: 1, cone: ctx.scene.cone, pad: { t: 22, r: 50, b: 24, l: 0 } }) });
    } else if (sc.querySelector('.chart-slot')) draw(sc.querySelector('.chart-slot'), html`<p class="asof">The index history did not load. The figures beside it are current.</p>`);
    draw($('#hm-desk', main), desk(data.morning_desk));
    const al = (data.alerts || []).slice(0, 4);
    draw($('#hm-alerts', main), al.length ? html`<section class="section" aria-labelledby="al-h"><div class="section-head"><h2 class="t-h2" id="al-h">Latest scan alerts</h2><a class="textlink" href="#/alerts">Alerts ${icon('arrow')}</a></div>
      <ul class="plain-list">${al.map((a) => html`<li><a href="#/${a.ticker || ''}"><b class="tick">${a.ticker || ''}</b> ${clean(a.title)}</a><small class="t-muted">${ago(a.created_at)}</small></li>`)}</ul></section>` : '');
  }
}

async function loadWatch(main) {
  const host = $('#hm-watch', main);
  const list = store.activeList();
  const syms = (list ? list.symbols : store.allSymbols()).slice(0, 8);
  if (!syms.length) { draw(host, empty('This list is empty', 'Add names on the Watchlist page, or press Watch on any company.', html`<a class="btn btn-sm" href="#/watchlist">Open Watchlist</a>`)); return; }
  try {
    const r = await api.get(`/api/watchlist?symbols=${syms.join(',')}`, { ttl: 60000, timeout: 30000 });
    if (!live) return;
    ctx.watch = r;
    const rows = (r.rows || []);
    const more = (list ? list.symbols.length : 0) - syms.length;
    draw(host, html`<div class="rows" role="list">${rows.map((x) => watchRow(x))}</div>${more > 0 ? html`<p class="quiet"><a class="textlink" href="#/watchlist">${more} more on this list ${icon('arrow')}</a></p>` : ''}`);
  } catch (e) { draw(host, failed('Your watchlist', e, { retry: 'watch' })); }
}

async function loadPriority(main) {
  const host = $('#hm-priority', main);
  const slow = setTimeout(() => { if ($('.sk-wrap', host)) host.insertAdjacentHTML('beforeend', '<p class="asof" role="status">Still gathering the calendar and this week\'s earnings. This can take a minute after a restart.</p>'); }, 8000);
  try {
    const pr = await api.get('/api/priority', { ttl: 300000, timeout: 90000 });
    if (!live) return;
    ctx.priority = pr; ctx.evFilter = ctx.evFilter || 'all';
    if (!pr || pr.available === false) draw(host, empty('Nothing to sort yet', clean((pr && pr.reason) || 'The calendar did not return anything.')));
    else draw(host, eventsBlock(pr, store.allSymbols(), ctx.evFilter));
  } catch (e) { draw(host, failed('What matters today', e, { retry: 'priority' })); }
  finally { clearTimeout(slow); }
}

async function loadMovers(main) {
  const host = $('#hm-movers', main);
  try { const m = await api.get('/api/scanners/movers?limit=6', { ttl: 120000 }); if (live) draw(host, movers(m)); }
  catch (e) { draw(host, failed('This month\'s movers', e, { retry: 'movers' })); }
}

async function loadStarters(main) {
  const host = $('#hm-starters', main);
  try {
    const r = await api.get(`/api/watchlist?symbols=${STARTERS.join(',')}`, { ttl: 60000, timeout: 30000 });
    if (!live) return;
    ctx.starters = r.rows; draw(host, starters(r.rows));
  } catch (e) { ctx.starters = []; draw(host, starters([])); }
}

async function loadModes(main) {
  let asked = null; try { asked = localStorage.getItem('optic.knowledge.asked.v1'); } catch (e) { /* private */ }
  if (asked) return;
  try {
    const r = await api.get('/api/knowledge/modes', { ttl: 3600000 });
    if (!live || !(r.modes || []).length) return;
    const sec = $('#hm-modes', main); sec.hidden = false;
    draw($('#hm-modes-in', main), modes(r.modes));
  } catch (e) { /* the question can wait for the next visit */ }
}

async function loadBrokerage(main) {
  try {
    const st = await api.get('/api/brokerage/status', { ttl: 60000 });
    const linked = st && st.available && (st.connections || []).some((c) => c.status !== 'disconnected');
    if (!linked || !live) return;
    ctx.linked = true;
    const [ov, perf] = await Promise.all([api.get('/api/brokerage/workspace/overview', { ttl: 60000 }), api.get('/api/brokerage/workspace/performance?period=3m', { ttl: 300000 }).catch(() => null)]);
    if (!live) return;
    let hero = $('#hm-hero', main);
    if (!hero) { // a new-user page that turns out to have a portfolio: draw the returning page
      draw(main, ''); render_(main, false); wire(main);
      loadHome(main, false); loadWatch(main); loadPriority(main); loadMovers(main);
      hero = $('#hm-hero', main);
    }
    draw(hero, portfolio(ov, perf));
    if (ctx.portfolio && ctx.portfolio.length > 1) mountCharts(hero, { portfolio: (w) => lineChart(ctx.portfolio, { w, h: Math.round(Math.max(200, Math.min(300, w * 0.3))), area: true, label: 'Portfolio value', dp: 0 }) });
  } catch (e) { /* no portfolio block: the rest of Home is complete without it */ }
}

function wireForms(main) {
  $$('[data-v2-search-form]', main).forEach((f) => f.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = String(new FormData(f).get('q') || '').trim();
    if (!q) return;
    const typed = /^[A-Za-z0-9.^=-]{1,12}$/.test(q) ? q.toUpperCase() : null;
    let sym = typed;
    try {
      const r = await api.get(`/api/search?q=${encodeURIComponent(q)}&limit=5`, { ttl: 300000, timeout: 8000 });
      const res = r.results || [];
      // an exact ticker wins; otherwise the best match for the words typed
      if (!(typed && res.some((x) => x.symbol === typed)) && res[0]) sym = res[0].symbol;
    } catch (err) { /* fall back to what was typed */ }
    if (sym) location.hash = `#/${sym}`;
  }));
}

function wire(main) {
  main.addEventListener('click', (e) => {
    const evb = e.target.closest('[data-v2-ev]');
    if (evb) {
      const open = evb.getAttribute('aria-expanded') === 'true';
      evb.setAttribute('aria-expanded', String(!open));
      const body = document.getElementById(evb.getAttribute('aria-controls'));
      if (body) body.hidden = open;
      return;
    }
    const more = e.target.closest('[data-v2-evmore]');
    if (more) {
      const open = more.getAttribute('aria-expanded') === 'true';
      const box = document.getElementById(more.getAttribute('aria-controls'));
      if (box) box.hidden = open;
      more.setAttribute('aria-expanded', String(!open));
      more.textContent = open ? `Show ${more.dataset.v2Evmore} more` : 'Show fewer';
      return;
    }
    const f = e.target.closest('[data-v2-evfilter]');
    if (f && ctx.priority) {
      ctx.evFilter = f.dataset.v2Evfilter;
      draw($('#hm-priority', main), eventsBlock(ctx.priority, store.allSymbols(), ctx.evFilter));
      const again = $(`[data-v2-evfilter="${ctx.evFilter}"]`, main); if (again) again.focus();
      return;
    }
    const c = e.target.closest('[data-v2-company]');
    if (c && ctx.watch) {
      const r = (ctx.watch.rows || []).find((x) => x.symbol === c.dataset.v2Company);
      if (r) openCompany(r, c);
      return;
    }
    if (e.target.closest('[data-v2-home-ready]')) { go('#/'); return; }
    const m = e.target.closest('[data-v2-mode]');
    if (m) {
      try {
        if (m.dataset.v2Mode) localStorage.setItem('optic.knowledge.v1', m.dataset.v2Mode);
        localStorage.setItem('optic.knowledge.asked.v1', '1');
      } catch (err) { /* private mode */ }
      $$('[data-v2-mode]', main).forEach((b) => b.setAttribute('aria-checked', String(b === m && !!m.dataset.v2Mode)));
      const sec = $('#hm-modes', main);
      if (sec) setTimeout(() => { sec.hidden = true; }, m.dataset.v2Mode ? 600 : 0);
    }
  });
}

/** Called by the app when the watchlist changes (a Follow on this page). */
export function onLists(main) {
  const sc = $('#hm-starters', main);
  if (sc && ctx.starters) {
    const focused = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.v2Watch : null;
    draw(sc, starters(ctx.starters));
    if (focused) { const b = $(`[data-v2-watch="${focused}"]`, sc); if (b) b.focus(); }
  }
}

export const retry = { home: (main) => loadHome(main, !store.allSymbols().length), watch: loadWatch, priority: loadPriority, movers: loadMovers };
