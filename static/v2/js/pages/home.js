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
import { num, signed, dir, money, signedMoney, clean, ago, shortDate, fullDate, isNum } from '../core/format.js';
import { lineChart, spark, mountCharts } from '../ui/chart.js';
import { skeleton, empty, failed, staleLine, how } from '../ui/states.js';
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
export const STARTERS = ['AAPL', 'NVDA', 'MSFT', 'SPY'];
// each starter with the name a newcomer knows it by; SPY is a fund, said so (beginner brief item 2)
export const STARTER_NAMES = { AAPL: 'Apple', NVDA: 'NVIDIA', MSFT: 'Microsoft', SPY: 'S&P 500 fund' };
export const STARTER_ABOUT = { SPY: 'SPY is a fund that holds the 500 companies of the S&P 500, so it moves with the US market as a whole.' };

let timer = null;
let live = true;
let ctx = {};

const etTime = (iso) => { const t = iso ? Date.parse(iso) : NaN; if (!Number.isFinite(t)) return 'time not reported'; return new Date(t).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' }) + ' ET'; };
export const etDate = (iso) => { try { return new Date(iso || Date.now()).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'America/New_York' }); } catch (e) { return ''; } };
export function hello() {
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
    <div class="lens"><p class="lens-k"><span>S&amp;P 500, the past three months</span><b>Gold band: the next session's range, as options price it</b></p>
      <div class="chart-slot" data-chart="spx">${series ? '' : skeleton('chart')}</div></div>
    <div class="copy">
      <p class="kicker" id="scene-h">The S&amp;P 500, next session</p>
      <p class="big">±${num(em.implied_pct, 2)}%</p>
      <p class="big-cap">About ${num(em.implied_points, 0)} points either way from ${num(em.spot, 0)}: the VIX's 30-day implied volatility as one day's move, an approximation.</p>
      ${real && isNum(em.ratio) ? html`<p class="second"><b>${num(em.ratio, 2)}×</b><span>the index's typical day over the last 14 sessions (±${num(em.realized_pct, 2)}%).</span></p>` : ''}
      ${how(html`<p>The one-day figure is the VIX (${num(em.vix, 1)}) divided by 16, the square root of about 256 trading days, as a percentage of the index level. The VIX measures the volatility S&amp;P 500 options price over the next 30 days, so this is a daily equivalent of that, not the price of a one-day option.${real ? ` The typical day is the 14-day average true range (${num(em.atr_pct, 2)}%) divided by 1.6, which puts a range on the same footing as a one-standard-deviation move. The ratio is ±${num(em.implied_pct, 2)}% divided by ±${num(em.realized_pct, 2)}%.` : ''}</p>`)}
      <p class="claim">${clean(em.reading || '')}</p>
      <div class="acts"><a class="btn btn-light" href="#/macro">See the macro picture</a><a class="btn" href="#/explore">What moved most</a>${miloButton('Ask Milo about today', { ask: 'What matters for the market in the next session?', context: 'Home, the market today' })}</div>
    </div>
    <p class="src">Source: Yahoo Finance index and VIX quotes, ${etTime(data.generated_at)}. ${clean((data.session || {}).label || '')}.</p>
  </section>`;
}

/* ---------------- portfolio (linked brokerage) ---------------- */
export function portfolio(ov, perf) {
  const vn = ov.value_now;
  const v = isNum(vn) ? vn : (vn && isNum(vn.value) ? vn.value : (ov.totals || {}).value);
  const today = ov.today || {};
  const series = ((perf || {}).series || []).filter((p) => isNum(p.value)).map((p) => ({ d: String(p.date).slice(0, 10), c: Number(p.value) }));
  // Under a week of values is not a three-month chart: the connection sends no past balances, so Optic's own
  // snapshots began on the day of the first sync, and two equal ones drew a flat line read as "my portfolio has not
  // moved" (owner, 2026-10-23). Until there is a week, the panel says how much history there is and what changed.
  const per = (perf || {}).period || {}, days = new Set(series.map((p) => p.d)).size;
  const short = series.length > 0 && (days < 7 || (isNum(per.covered_days) && per.covered_days < 7));
  const noBackfill = ((perf || {}).data_status || []).some((x) => x.balance_history === 'unavailable');
  ctx.portfolio = short ? [] : series;
  const twr = (((perf || {}).returns || {}).twr || {}).pct;
  const from = per.measured_start || (series[0] || {}).d, to = per.measured_end || (series[series.length - 1] || {}).d;
  const rows = (today.rows || []).slice().sort((x, y) => Math.abs(y.contribution || 0) - Math.abs(x.contribution || 0));
  const sync = ((ov.freshness || {}).broker || {}).newest_sync;
  const brokerTotal = ((ov.totals || {}).combined_usd || {}).value;
  const src = ((perf || {}).sources || {});
  const srcWords = { provider_estimate: "your data provider's estimated daily balances", collected: 'snapshots Optic collected at each sync', mixed: "the provider's estimates, then Optic's own snapshots", none: 'no value history yet' }[src.values] || src.values || '';
  const switches = (src.switches || []).map((x) => shortDate(x.date));
  return html`<section class="figure hero pf" aria-labelledby="pf-h"><div class="pf-main">
    <p class="t-label" id="pf-h">Your portfolio, value now${ov.holdings_count ? html`<span class="pill">${ov.holdings_count} holdings</span>` : ''}</p>
    <p class="t-display">${money(v)}</p>
    <p class="delta">${isNum(today.total) ? html`<span class="${dir(today.total)}">${signedMoney(today.total)} (${signed(today.total_pct)}) on the day</span>` : ''}${isNum(brokerTotal) && Math.abs(brokerTotal - v) > 1 ? html`<span class="t-muted">Your broker's own total: ${money(brokerTotal)}${sync ? `, ${ago(sync)}` : ''}</span>` : ''}</p>
    ${short ? html`<p class="pf-chart-k">Optic has ${days === 1 ? 'one day' : `${days} days`} of value history for these accounts, since ${fullDate(series[0].d)}.${noBackfill ? " Your broker's connection does not send past balances, so" : ''} Optic records the value your broker reports at each sync; the three-month chart appears once there is a week of them.</p>
      ${series.length > 1 ? html`<p class="pf-twr">${isNum(twr) ? html`<b class="${dir(twr)}">${signed(twr)}</b> from ${fullDate(from)} to ${fullDate(to)}` : 'No return yet'}, time-weighted, from your broker's reported values (${money(series[0].c)} on ${shortDate(series[0].d)}, ${money(series[series.length - 1].c)} on ${shortDate(series[series.length - 1].d)}). The value now above is at Optic's current quotes.</p>` : ''}`
    : series.length > 1 ? html`<p class="pf-chart-k">Account value as your broker reported it, three months. It includes your own deposits and withdrawals, so it is not a return.${switches.length ? ` The source changes on ${switches.join(', ')}, marked on the chart; the step there is not a gain or loss.` : ''}</p><div class="chart-slot" data-chart="portfolio"></div>` : html`<p class="asof">The value chart fills in as daily snapshots accumulate.</p>`}
    ${isNum(twr) && !short ? html`<p class="pf-twr"><b>${signed(twr)}</b> from ${fullDate(from)} to ${fullDate(to)}, time-weighted, measured from ${srcWords}.${switches.length ? ' A change of source inside the period moves this figure, so read it with the chart.' : ''}</p>` : ''}
    </div><div class="pf-side">${rows.length ? html`<div class="pf-rows" role="table" aria-label="Holdings, by their effect on the day">
      <div class="pf-row pf-head" role="row"><span role="columnheader">Holding</span><span role="columnheader" class="num">Price</span><span role="columnheader" class="num">Day</span><span role="columnheader" class="num">Effect</span></div>
      ${rows.slice(0, 6).map((r) => html`<a class="pf-row" role="row" href="#/${r.symbol}"><span role="cell"><b class="tick">${r.symbol}</b> <small class="t-muted">${num(r.quantity, 0)} shares</small></span><span role="cell" class="num">${num(r.price)}</span><span role="cell" class="num ${dir(r.change_pct)}">${signed(r.change_pct)}</span><span role="cell" class="num ${dir(r.contribution)}">${signedMoney(r.contribution, 0)}</span></a>`)}</div>` : ''}
    <p class="asof">${clean((vn && vn.basis) || '')}${sync ? ` Last sync ${ago(sync)}.` : ''}</p>
    <div class="cluster"><a class="textlink" href="#/brokerage/holdings">All holdings ${icon('arrow')}</a><a class="textlink" href="#/brokerage/performance">Performance ${icon('arrow')}</a></div></div>
  </section>`;
}

/* ---------------- what matters today ---------------- */
// What the reader opened here is kept by each item's own key, not its place on the page, so a refresh of the board
// (every ten minutes, or when a figure comes in) repaints it with the same rows, groups and note still open.
const EV_OPEN = new Set(), EV_MORE = new Set();
let csOpen = null;
const evId = (k) => { let h = 5381; for (let i = 0; i < k.length; i += 1) h = ((h * 33) ^ k.charCodeAt(i)) >>> 0; return `ev-${h.toString(36)}`; };
const evKey = (r) => [r.kind, r.ticker || '', r.date || r.when || '', r.kind === 'earnings' ? '' : (r.short || r.title || '')].join('|');
function bucket(r) {
  const d = Number(r.days_away);
  if (r.kind === 'sector') return 'Now';
  if (d === 0 || r.when === 'Today') return 'Today';
  // A report from earlier in the week is out, with its result: under "Through
  // the next 5 days" it read as one still to come.
  if (Number.isFinite(d) && d < 0) return 'Earlier this week';
  return 'This week';
}
/* What a release or a report that is out printed, ahead of what the report
 * is. The agency's own headline backs a release's figure when it is that day's. */
function resultBody(res) {
  if (!res) return '';
  if (res.pending) return html`<p class="ev-result is-pending">${clean(res.text || '')}</p>`;
  if (res.detail) return reportBody(res);
  return html`<p class="ev-result">${clean(res.text || '')}${res.headline ? html` <span class="ev-src">${clean(res.headline_source || 'Agency')}: \u201c${clean(res.headline)}\u201d${res.headline_url ? html` <a class="textlink" href="${res.headline_url}" target="_blank" rel="noopener">Release</a>` : ''}</span>` : ''}${res.source ? html` <small class="t-muted">${clean(res.source)}.</small>` : ''}</p>`;
}
/* A company's released result, read past its EPS line (owner, 2026-10-26): revenue against its estimate, the
 * two together, growth on a year earlier, the record and the reaction, each only where Optic has the figure.
 * What it does not have is named, and why is one press away (app/earnings_result.py says where each comes from). */
function reportBody(res) {
  const d = res.detail, rev = d.revenue || {}, g = d.growth || {};
  const pct = (x) => `${num(Math.abs(x), 1)}%`;
  const revText = rev.available ? (rev.estimate
    ? `${rev.reported_label} against ${rev.estimate_label} expected${rev.verdict ? `: ${rev.verdict}${rev.verdict === 'in line' ? '' : ` by ${pct(rev.surprise_pct)}`}` : ''}.`
    : `${rev.reported_label} reported, with no estimate to set it against.`) : '';
  const facts = [
    d.combined ? ['Together', d.combined.text] : null,
    revText ? ['Revenue', revText] : null,
    g.revenue_text || g.eps_text ? ['Year on year', [g.revenue_text, g.eps_text].filter(Boolean).join(' ')] : null,
    d.record && d.record.available ? ['Record', d.record.text] : null,
    d.reaction && d.reaction.available ? ['Reaction', d.reaction.text] : null,
  ].filter(Boolean);
  const missing = (d.missing || []).map((m) => { const i = String(m).indexOf(':'); return i > 0 ? [m.slice(0, i), m.slice(i + 1).trim()] : [m, '']; });
  return html`<p class="ev-result">${d.fiscal ? `${clean(d.fiscal)}: ` : ''}${clean(res.text || '')}</p>
    ${facts.length ? html`<dl class="ev-facts">${facts.map(([k, v]) => html`<div><dt>${k}</dt><dd>${clean(v)}</dd></div>`)}</dl>` : ''}
    ${missing.length ? html`<details class="ev-missing"><summary>${icon('chev')}Not in Optic's data yet: ${missing.map(([k]) => k.charAt(0).toLowerCase() + k.slice(1)).join('; ')}</summary><ul class="plain">${missing.map(([k, v]) => html`<li><b>${clean(k)}</b>${v ? `: ${clean(v)}` : ''}</li>`)}</ul></details>` : ''}
    <p><small class="t-muted">${clean(d.sources || res.source || '')}</small></p>`;
}
const shortResult = (r) => (r.result && !r.result.pending ? r.result.short || '' : '');

/* The week as days (Classic's catalyst strip, app.js catalystStripHTML; parity B8.2). Only what the feed dates is
 * placed, by the row's date or else its days away, and only on the days the feed looks at; anything it cannot
 * place stays in the list below. Two a day, the larger first; the rest of a day opens under the strip. */
const CATALYST_SHOWN = 2;
const DAY = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const etToday = () => { try { return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()); } catch (e) { return ''; } };
export function catalystDays(p, todayIso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(todayIso || etToday()));
  const base = m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) : null;
  if (base === null) return { days: [], placed: 0 };
  const cols = {}; ((p || {}).columns || []).forEach((c) => { cols[c.id] = c; });
  const horizon = Math.max(1, Math.min(7, Number.isFinite(p.horizon_days) ? p.horizon_days : 5));   // inclusive, as the feed's own
  const days = [];
  for (let k = 0; k <= horizon; k += 1) {
    const d = new Date(base + k * 864e5);
    if (d.getUTCDay() === 0 || d.getUTCDay() === 6) continue;   // no session
    const iso = d.toISOString().slice(0, 10);
    days.push({ k, iso, name: k === 0 ? 'Today' : `${DAY[d.getUTCDay()]} ${d.getUTCDate()}`, items: [], closed: ((p || {}).closed_days || {})[iso] || null });
  }
  const place = (row, kind) => {
    const on = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(row.date || ''));
    const k = on ? Math.round((Date.UTC(+on[1], +on[2] - 1, +on[3]) - base) / 864e5) : (Number.isFinite(row.days_away) ? row.days_away : null);
    const day = days.find((x) => x.k === k); if (!day) return;
    const res = shortResult(row);
    // a report by its ticker (the cell is headed with its day); a release that is out says what it printed, or
    // Out while its figures are on their way
    // a report says before the open or after the close where a source Optic trusts does (row.time), and under
    // its result once it is out; nothing where none does
    day.items.push({ kind, key: evKey(row), title: row.short || (kind === 'earnings' && row.ticker) || row.title, time: res || (row.released ? 'Out' : row.time || ''), sess: res && kind === 'earnings' ? row.time || '' : '', result: !!res, impact: row.impact, row });
  };
  ((cols.events || {}).rows || []).forEach((r) => place(r, 'event'));
  ((cols.earnings || {}).rows || []).forEach((r) => place(r, 'earnings'));
  const RANK = { high: 0, medium: 1, low: 2 };
  days.forEach((x) => x.items.sort((a, b) => (RANK[a.impact] ?? 3) - (RANK[b.impact] ?? 3)));
  return { days, placed: days.reduce((n, x) => n + x.items.length, 0) };
}
function csNote(days) {
  if (!csOpen) return html`<div class="cs-note" id="cs-note" hidden></div>`;
  const [kind, what] = [csOpen.slice(0, 4), csOpen.slice(5)];
  if (kind === 'more') {
    const day = days.find((x) => x.iso === what); if (!day) return html`<div class="cs-note" id="cs-note" hidden></div>`;
    return html`<div class="cs-note" id="cs-note"><p class="cs-note-h">${day.name}, the rest</p><ul class="plain">${day.items.slice(CATALYST_SHOWN).map((it) => html`<li><b>${clean(it.row.title || it.title)}</b>${it.time && (it.result || it.kind !== 'earnings') ? html` <span class="t-muted">${it.time}</span>` : ''}${it.impact === 'high' ? html` <span class="t-muted">High impact</span>` : ''}</li>`)}</ul></div>`;
  }
  const it = days.flatMap((x) => x.items).find((x) => x.key === what);
  if (!it) return html`<div class="cs-note" id="cs-note" hidden></div>`;
  const r = it.row, title = String(r.title || it.title);
  let when = String(r.when || r.time || '').trim();
  if (when && title.toLowerCase().includes(when.toLowerCase())) when = '';   // "PEP reports Thursday" already says when
  return html`<div class="cs-note" id="cs-note"><p class="cs-note-h">${clean(title)}${when ? html` <span class="t-muted">${when}${r.time && when !== r.time ? `, ${r.time}` : ''}</span>` : ''}</p>
    ${resultBody(r.result)}${r.why ? html`<p class="${r.result ? 'ev-why' : ''}">${clean(r.why)}</p>` : ''}
    ${r.ticker ? html`<p><a class="textlink" href="#/${r.ticker}">Open ${r.ticker} ${icon('arrow')}</a></p>` : ''}</div>`;
}
export function catalystStrip(p, todayIso) {
  const { days, placed } = catalystDays(p, todayIso);
  if (!placed) return '';
  if (csOpen && !days.some((x) => (csOpen === `more:${x.iso}`) || x.items.some((it) => `item:${it.key}` === csOpen))) csOpen = null;   // gone from the board
  const item = (it) => {
    const inner = html`<span class="cs-what">${clean(it.title)}</span>${it.time ? html`<span class="cs-time${it.result ? ' is-result' : ''}">${it.time}</span>` : ''}${it.sess ? html`<span class="cs-time">${it.sess}</span>` : ''}${it.impact === 'high' ? html`<span class="sr"> (high impact)</span>` : ''}`;
    const cls = `cs-item is-${it.kind}${it.impact === 'high' ? ' is-high' : ''}`;
    if (!String(it.row.why || '').trim() && !it.row.result && !it.row.ticker) return html`<li class="${cls}">${inner}</li>`;
    const open = csOpen === `item:${it.key}`;
    return html`<li class="${cls}"><button type="button" class="cs-btn" data-v2-cs="item:${it.key}" aria-expanded="${open}" aria-controls="cs-note">${inner}</button></li>`;
  };
  const anyHigh = days.some((x) => x.items.slice(0, CATALYST_SHOWN).some((it) => it.impact === 'high'));
  const anyEarn = days.some((x) => x.items.slice(0, CATALYST_SHOWN).some((it) => it.kind === 'earnings'));
  return html`<div class="cs-strip" role="list" aria-label="${placed} scheduled ${placed === 1 ? 'item' : 'items'} by day">${days.map((x) => {
      const rest = x.items.length - CATALYST_SHOWN;
      if (x.closed && !x.items.length) return html`<div class="cs-day is-closed" role="listitem"><p class="cs-date">${x.name}</p><p class="cs-none">Market closed: ${clean(x.closed)}</p></div>`;
      return html`<div class="cs-day${x.k === 0 ? ' is-today' : ''}" role="listitem"><p class="cs-date">${x.name}</p>
        ${x.items.length ? html`<ul class="cs-items">${x.items.slice(0, CATALYST_SHOWN).map(item)}${rest > 0 ? html`<li><button type="button" class="cs-btn cs-more" data-v2-cs="more:${x.iso}" aria-expanded="${csOpen === `more:${x.iso}`}" aria-controls="cs-note">${rest} more</button></li>` : ''}</ul>`
          : html`<p class="cs-none">Nothing tracked</p>`}</div>`;
    })}</div>
    ${anyHigh || anyEarn ? html`<p class="cs-key">${anyHigh ? html`<span class="cs-key-i is-high">High impact</span>` : ''}${anyEarn ? html`<span class="cs-key-i is-earnings">Company report</span>` : ''}</p>` : ''}
    ${csNote(days)}`;
}
export function eventsBlock(pr, followed, filter) {
  const cols = (pr.columns || []);
  const rows = [];
  cols.forEach((c) => (c.rows || []).forEach((r) => rows.push(Object.assign({ col: c.id }, r))));
  const mine = rows.filter((r) => r.ticker && followed.includes(r.ticker));
  const shown = filter === 'mine' ? mine : rows.filter((r) => r.col !== 'movers');
  if (!rows.length) return empty('Nothing scheduled that moves the market', 'No major releases, earnings or sector moves in the next few days.');
  const byDate = (a, b) => String(a.date || '').localeCompare(String(b.date || '')) || (a.impact === 'high' ? -1 : 0);
  // What is out reads newest first; what is coming, soonest first.
  const newest = (a, b) => String(b.date || '').localeCompare(String(a.date || '')) || (a.impact === 'high' ? -1 : 0);
  const groups = ['Now', 'Today', 'This week', 'Earlier this week'].map((b) => [b, shown.filter((r) => bucket(r) === b).sort(b === 'Earlier this week' ? newest : byDate)]).filter(([, l]) => l.length);
  const item = (r) => {
    const key = evKey(r), id = evId(key), open = EV_OPEN.has(key), res = shortResult(r);
    const title = clean(r.title), when = r.when && title.toLowerCase().includes(String(r.when).toLowerCase()) ? '' : r.when;
    const meta = [when, res || r.kind === 'earnings' ? '' : r.time, r.impact ? `${r.impact} impact` : '', r.ticker && followed.includes(r.ticker) ? 'on your list' : ''].filter(Boolean).join(', ');
    return html`<div class="ev">
        <button type="button" class="ev-head" aria-expanded="${open}" aria-controls="${id}" data-v2-ev="${key}">
          <span class="who">${r.kind === 'sector' ? 'Sector' : r.ticker || r.short || ''}</span>
          <span class="what">${title}<small>${meta.charAt(0).toUpperCase() + meta.slice(1)}</small></span>
          <span class="ch">${res ? html`<span class="ev-res">${res}</span>` : ''}</span>${icon('chev')}</button>
        <div class="ev-body" id="${id}" ${open ? '' : raw('hidden')}>${resultBody(r.result)}${r.why ? html`<p class="${r.result ? 'ev-why' : ''}">${clean(r.why)}</p>` : ''}${r.ticker ? html`<div class="cluster"><a class="textlink" href="#/${r.ticker}">Open ${r.ticker} ${icon('arrow')}</a></div>` : ''}</div></div>`;
  };
  return html`${filter === 'mine' ? '' : catalystStrip(pr)}
    <div class="chips" role="group" aria-label="Show">
      <button type="button" class="chip" data-v2-evfilter="all" aria-pressed="${filter !== 'mine'}">Everything</button>
      <button type="button" class="chip" data-v2-evfilter="mine" aria-pressed="${filter === 'mine'}">Your names <span class="t-muted">${mine.length}</span></button></div>
    ${groups.length ? groups.map(([b, list]) => { const more = EV_MORE.has(b); return html`<p class="group-h"><b>${b}</b>${b === 'Now' ? 'Sector moves' : b === 'Today' ? 'Releases and reports' : b === 'Earlier this week' ? 'Reported, with results' : `Through the next ${pr.horizon_days || 5} days`}</p>
      ${list.slice(0, 3).map(item)}
      ${list.length > 3 ? html`<div id="evmore-${b.replace(/\s/g, '')}" ${more ? '' : raw('hidden')}>${list.slice(3).map(item)}</div>
        <button type="button" class="textlink ev-more" aria-expanded="${more}" aria-controls="evmore-${b.replace(/\s/g, '')}" data-v2-evmore="${list.length - 3}" data-v2-evgroup="${b}">${more ? 'Show fewer' : `Show ${list.length - 3} more`}</button>` : ''}`; })
      : html`<p class="quiet">None of your names has an event in the next ${pr.horizon_days || 5} days.</p>`}
    <p class="asof">Updated ${ago(pr.generated_at)}.</p>
    <details class="method" data-v2-fold="pr-method"><summary>How this is sorted and timed</summary><p>${clean(pr.method || '')}</p>${pr.earnings_method ? html`<p>${clean(pr.earnings_method)}</p>` : ''}</details>`;
}
/** A press inside what matters today, from Home's workspace or this page; true when it was one. Toggles in place
 *  and records it, so a later repaint draws it the same way. */
export function evPress(t, scope) {
  let b = t.closest('[data-v2-ev]');
  if (b) {
    const open = b.getAttribute('aria-expanded') === 'true', key = b.dataset.v2Ev;
    if (open) EV_OPEN.delete(key); else EV_OPEN.add(key);
    b.setAttribute('aria-expanded', String(!open)); const body = document.getElementById(b.getAttribute('aria-controls')); if (body) body.hidden = open; return true;
  }
  b = t.closest('[data-v2-evmore]');
  if (b) {
    const open = b.getAttribute('aria-expanded') === 'true', g = b.dataset.v2Evgroup;
    if (open) EV_MORE.delete(g); else EV_MORE.add(g);
    const box = document.getElementById(b.getAttribute('aria-controls')); if (box) box.hidden = open;
    b.setAttribute('aria-expanded', String(!open)); b.textContent = open ? `Show ${b.dataset.v2Evmore} more` : 'Show fewer'; return true;
  }
  b = t.closest('[data-v2-cs]');
  if (b) {
    const key = b.dataset.v2Cs; csOpen = csOpen === key ? null : key;
    return { repaint: true, focus: key };
  }
  void scope; return false;
}

/* ---------------- the Desk ---------------- */
// Classic's Desk (app.js morningDesk; parity B8.1): the edition when one is kept, the bottom line first, then the
// lead; the rest of it (the branches, the note, today's reports) one press away, and what it does not tell you
// folded with its count. Which voice wrote it is said, and when the written one is not showing, why.
const voiceWords = (md) => (md.voice !== 'mechanical' ? `Written for today by an AI model${md.written_by ? ` (${md.written_by})` : ''} from the day's figures and nothing else.` : 'Compiled by fixed rules from the day\'s figures; no model wrote it.');
// why the written version is not the one showing, said at the Desk's foot (Classic's deskVoiceReason)
function voiceWhy(md) {
  if (md.voice !== 'mechanical') return '';
  if (md.voice_reason === 'moved') return `The written version${md.written_at ? ` from ${etTime(md.written_at)}` : ''} is not shown, because the market has moved since it was written and its figures no longer match.${md.rewriting ? ' A new one is being written against today\'s figures.' : ''}`;
  if (md.voice_reason === 'unwritten') return 'Today\'s written version could not be produced.';
  return '';
}
export function deskBody(md) {
  const lead = (md.lead || []).map(clean), ed = md.edition;
  const scen = md.scenarios || [], cal = md.calendar || [], limits = md.limits || [];
  const rest = lead.length > 1 || scen.length || md.note || cal.length;
  return html`<p class="ws-sub">${md.date ? `For ${shortDate(md.date)}. ` : ''}${voiceWords(md)}</p>
    ${ed && ed.headline ? html`<div class="desk-ed"><p class="t-label">${ed.is_today ? 'Today\'s edition' : `Latest edition, ${shortDate(ed.date)}`}${ed.slot_label ? `, ${ed.slot_label}` : ''}${ed.test_edition ? ', a test edition' : ''}</p>
      <p class="desk-ed-h">${clean(ed.headline)}</p>${ed.summary ? html`<p>${clean(ed.summary)}</p>` : ''}<p><a class="textlink" href="#/read">The full edition ${icon('arrow')}</a></p></div>` : ''}
    ${md.overall ? html`<p class="desk-bottom"><b>Bottom line.</b> ${clean(md.overall)}</p>` : ''}
    ${lead.length ? html`<p>${lead[0]}</p>` : ''}
    ${rest ? html`<details class="more desk-more" data-v2-fold="desk-more"><summary>The whole desk ${icon('chev')}</summary><div class="inner">
      ${lead.slice(1).map((l) => html`<p>${l}</p>`)}
      ${scen.length ? html`<h3 class="t-h3">What could happen next</h3><dl class="desk-branches">${scen.map((x) => html`<div><dt>${clean(x.label)}</dt><dd>${clean(x.text)}</dd></div>`)}</dl>` : ''}
      ${md.note ? html`<p><b>Note.</b> ${clean(md.note)}</p>` : ''}
      ${cal.length ? html`<h3 class="t-h3">Today's reports</h3><ul class="plain desk-cal">${cal.map((r) => html`<li><p><b>${clean(r.title)}</b>${[r.time, r.impact ? `${r.impact} impact` : ''].filter(Boolean).length ? html` <span class="t-muted">${[r.time, r.impact ? `${r.impact} impact` : ''].filter(Boolean).join(', ')}</span>` : ''}</p>${r.detail ? html`<p class="t-muted">${clean(r.detail)}</p>` : ''}</li>`)}</ul>` : ''}
    </div></details>` : ''}
    ${limits.length ? html`<details class="more-inline desk-limits" data-v2-fold="desk-limits"><summary>What this does not tell you (${limits.length})</summary><ul>${limits.map((l) => html`<li>${clean(l)}</li>`)}</ul></details>` : ''}
    ${voiceWhy(md) ? html`<p class="asof desk-why">${voiceWhy(md)}</p>` : ''}`;
}
export function desk(md) {
  if (!md || !md.available) return '';
  return html`<section class="section" aria-labelledby="desk-h">
    <div class="section-head"><div><h2 class="t-h2" id="desk-h">${md.title || 'Optic Desk'}</h2></div>
      ${miloButton('Ask Milo about the Desk', { ask: 'Walk me through today\'s Desk.', context: 'Home, Optic Desk' })}</div>
    ${deskBody(md)}
  </section>`;
}

/* ---------------- what changed since yesterday ---------------- */
// The briefing for the reader's own names (app/briefing.py; Classic app.js dailyChangesHTML, parity B8.3): the latest
// completed session against the one before, item by item, each with why it may matter and where it shows. The
// sentences are the server's, from fixed rules; no model writes them. Four, and the rest one press away.
export const CHANGES_SHOWN = 4;
const CHANGE_LINK = { chart: ['chart', 'Chart'], swing: ['options', 'Options'], earnings: ['earnings', 'Earnings'], financials: ['financials', 'Financials'], long: ['investing', 'Investing'] };
/** Holdings where the page already keeps them, symbols only: open paper positions, the retirement planner's
 *  holdings box (Classic's two), and a linked brokerage's holdings when Home has them. Quantities stay here. */
export function briefingHoldings(brokerageRows) {
  const out = [];
  try { (((JSON.parse(localStorage.getItem('optic.paper.v1') || 'null')) || {}).open || []).forEach((x) => { if (x && x.ticker) out.push(String(x.ticker).toUpperCase()); }); } catch (e) { /* none, or unreadable */ }
  try {
    const r = JSON.parse(localStorage.getItem('optic.roth.inputs') || 'null') || {};
    String(r.holdings || '').split(/[\n,]/).forEach((line) => { const m = /^\s*([A-Za-z][A-Za-z0-9.\-]{0,9})\b/.exec(line); if (m) out.push(m[1].toUpperCase()); });
  } catch (e) { /* none, or unreadable */ }
  (brokerageRows || []).forEach((x) => { if (x && x.symbol) out.push(String(x.symbol).toUpperCase()); });
  return [...new Set(out)].slice(0, 40);
}
function changeRow(it, repeatWhy) {
  const sym = String(it.symbol || ''), link = it.link || {}, [route, label] = CHANGE_LINK[link.view] || ['chart', 'Chart'];
  const head = String(it.headline || '').indexOf(`${sym} `) === 0 ? it.headline.slice(sym.length + 1) : String(it.headline || '');
  return html`<li class="dc-item"><div class="dc-line"><b class="tick">${sym}</b>${it.holding ? html`<span class="t-muted dc-held">Held</span>` : ''}<span class="dc-head">${clean(head.charAt(0).toUpperCase() + head.slice(1))}</span>
      <button type="button" class="btn btn-sm btn-quiet dc-open" data-v2-dc="${sym}" data-v2-dc-view="${route}" data-v2-dc-panel="${link.panel || ''}">${link.panel || label} ${icon('arrow')}</button></div>
    ${it.detail ? html`<p class="dc-detail">${clean(it.detail)}</p>` : ''}${it.why && !repeatWhy ? html`<p class="t-muted dc-why">${clean(it.why)}</p>` : ''}</li>`;
}
export function changesBlock(d, all) {
  if (!d) return skeleton('rows', 3, 'Comparing your names');
  const per = d.period || {};
  if (!d.available) return html`<p class="ws-note">${clean(d.reason || 'Nothing to compare yet.')}</p>`;
  const items = d.items || [], shown = all ? items : items.slice(0, CHANGES_SHOWN), names = d.names || [];
  const quiet = names.filter((n) => n.state === 'unchanged'), lost = names.filter((n) => n.state === 'stale' || n.state === 'missing'), unread = d.unread || [];
  // a kind of change says what it means once; four setups triggering said the same sentence four times
  const seen = new Set();
  const rows = shown.map((it) => { const why = String(it.why || '').trim(), rep = !!why && seen.has(why); if (why) seen.add(why); return changeRow(it, rep); });
  // "unchanged" covers only the checks that ran, so the ones that could not are named beside it
  const by = {}; quiet.forEach((n) => (n.not_checked || []).forEach((w) => { (by[w] = by[w] || []).push(n.symbol); }));
  const notChecked = Object.keys(by).map((w) => `${w} for ${by[w].join(', ')}`);
  return html`${per.label ? html`<p class="ws-sub">${clean(per.label)}.${(per.notes || []).length ? ` ${clean(per.notes.join(' '))}` : ''}</p>` : ''}
    <p class="dc-summary">${clean(d.summary || '')}</p>
    ${rows.length ? html`<ul class="dc-list">${rows}</ul>` : ''}
    ${items.length > CHANGES_SHOWN ? html`<button type="button" class="textlink" data-v2-dc-all aria-expanded="${!!all}">${all ? 'Show fewer' : `All ${items.length} changes`}</button>` : ''}
    ${quiet.length ? html`<p class="dc-quiet"><b>No meaningful change:</b> ${quiet.map((n, i) => html`${i ? ', ' : ''}${n.symbol} <span class="${dir(n.change_pct)}">${isNum(n.change_pct) ? signed(n.change_pct, 1) : 'n/a'}</span>`)}.</p>` : ''}
    ${notChecked.length ? html`<p class="t-muted">Not checked: ${notChecked.join('; ')}.</p>` : ''}
    ${lost.map((n) => html`<p class="dc-stale"><b>${n.symbol}</b>: ${clean(n.summary || '')}</p>`)}
    ${unread.length ? html`<p class="t-muted">Earnings dates and filings are being read for the first time for ${unread.length === names.length ? 'these names' : unread.join(', ')}. They compare from the next session; until then those checks are not counted.</p>` : ''}
    ${d.method ? html`<details class="more-inline" data-v2-fold="dc-method"><summary>How this is compared</summary><p>${clean(d.method)}</p></details>` : ''}`;
}

/* ---------------- index and sector trends ---------------- */
// The board Macro and Indices draw, on Home (Classic app.js homeTrendsInner, parity B8.4): SPY, QQQ, IWM and the
// eleven SPDR sectors against the prior completed session's high and low. The state's words are v2's own, as on
// Macro's board, so one row never reads two ways; the distance and the action are the server's sentences.
const TREND_WORD = { uptrend: 'Uptrend', downtrend: 'Downtrend', neutral: 'Neutral' };
const TREND_DIR = { uptrend: 'up', downtrend: 'down', neutral: 'flat' };
/** Which range and which print each card compares, said once above them (Classic's trendBasisLine). */
export function trendBasis(basis, today = new Date()) {
  const s = basis || null;
  if (!s || !s.levels_label) return '';
  const dayOf = (d) => d.toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
  const at = (iso) => { const t = Date.parse(iso || ''); if (!Number.isFinite(t)) return ''; const d = new Date(t); const clock = etTime(iso); return dayOf(d) === dayOf(today) ? clock : `${d.toLocaleDateString('en-US', { weekday: 'short', timeZone: 'America/New_York' })} ${clock}`; };
  const kinds = s.price_kinds || {}, total = Object.values(kinds).reduce((n, v) => n + (Number(v) || 0), 0);
  let price;
  if (s.price_kind === 'last close') price = 'the last close, as nothing has printed since it. A close sits inside its own session\'s range, so those cards read neutral';
  else {
    const to = at(s.price_as_of), from = at(s.price_as_of_from), span = Date.parse(s.price_as_of) - Date.parse(s.price_as_of_from);
    const when = !to ? (s.price_kind === 'regular session' ? ', from today\'s daily bar' : '') : (from && from !== to && span > 5 * 60 * 1000 ? `, struck between ${from} and ${to}` : `, as of ${to}`);
    price = `${s.price_kind}${when}`;
  }
  const parts = [`Levels: ${s.levels_label}.`, `Price: ${price}.`];
  const closes = s.price_kind === 'last close' ? 0 : (Number(kinds['last close']) || 0);
  if (closes) parts.push(`${closes} of ${total} have not traded since that close, so they show it and read neutral.`);
  if (total - (Number(kinds[s.price_kind]) || 0) - closes > 0) parts.push('A card priced from another session says which.');
  const late = (s.delayed || []).map((x) => `${x.symbol} ${x.minutes} minutes`);
  if (late.length) parts.push(`Delayed by the feed: ${late.join(', ')}.`);
  return parts.join(' ');
}
function trendCell(r, mainKind) {
  if (!r) return '';
  if (!r.available) return html`<li class="tr-cell is-missing"><p class="tr-top"><b class="tick">${r.symbol}</b></p><p class="tr-name">${r.name || ''}</p><p class="t-muted">${clean(r.reason || 'Unavailable')}</p></li>`;
  const d = TREND_DIR[r.trend] || 'flat', kind = r.price_kind && r.price_kind !== mainKind ? r.price_kind : '';
  return html`<li class="tr-cell is-${d}"><a href="#/${r.symbol}" class="tr-link">
    <span class="tr-top"><b class="tick">${r.symbol}</b><span class="tr-price">${num(r.price)}</span></span>
    <span class="tr-name">${r.name || ''}</span>
    <span class="tr-state">${TREND_WORD[r.trend] || clean(r.trend || '')}</span>
    ${kind ? html`<span class="t-muted">Price: ${kind}${r.price_venue ? `, on ${r.price_venue}` : ''}</span>` : ''}
    <span class="tr-vs ${d === 'flat' ? '' : d}">${clean(r.vs_level_text || '')}</span>
    <span class="tr-act">${clean((r.action || {}).text || r.summary || '')}</span></a></li>`;
}
export function trendsBlock(d) {
  if (!d) return skeleton('rows', 3, 'Loading the board');
  if (!d.available) return html`<p class="ws-note">The trend board is unavailable right now${d.reason ? ` (${clean(d.reason)})` : ''}.</p>`;
  const main = (d.basis || {}).price_kind, line = trendBasis(d.basis);
  const group = (name, rows) => (rows && rows.length ? html`<h3 class="t-label tr-group">${name}</h3><ul class="tr-grid">${rows.map((r) => trendCell(r, main))}</ul>` : '');
  return html`${line ? html`<p class="ws-sub">${line}</p>` : ''}${group('Indices', d.indices)}${group('Sectors', d.sectors)}
    <p><a class="textlink" href="#/market">The full sector board ${icon('arrow')}</a></p>
    ${d.method ? html`<details class="more-inline" data-v2-fold="tr-method"><summary>How the levels are set</summary><p>${clean(d.method)}</p></details>` : ''}`;
}

/* ---------------- movers ---------------- */
function movers(m) {
  const rows = (m && (m.rows || m.results || m.movers)) || [];
  if (m && m.building) return empty('The one-month ranking is still loading', clean(m.reason || 'It appears here when it finishes.'));
  if (!rows.length) return empty('No one-month movers yet', clean((m && m.reason) || 'They appear once the ranking has run.'));
  return html`<ol class="movers">${rows.slice(0, 6).map((r) => html`<li><a href="#/${r.symbol || r.ticker}"><b class="tick">${r.symbol || r.ticker}</b><span class="${dir(r.roc20 ?? r.change_pct)}">${signed(r.roc20 ?? r.change_pct, 1)}</span></a></li>`)}</ol>
    <p class="asof">The 20-session change, ranked by size either way.</p>`;
}

/* ---------------- new user ---------------- */
export function welcome(data) {
  const spx = inst(data, 'equity', 'S&P 500');
  return html`<section class="welcome" aria-labelledby="wel-h">
    <div class="copy">
      <p class="kicker">Stock and options research</p>
      <h1 id="wel-h">See what moves a stock, and why.</h1>
      <p>Prices, options, financials and filings for US stocks and funds, each figure with its source.</p>
      <form class="wel-form" role="search" data-v2-search-form>
        <label class="field">${icon('search')}<span class="sr">Company or ticker</span><input name="q" placeholder="Try AAPL or Nvidia" data-v2-ta="submit" autocomplete="off" spellcheck="false"></label>
        <button type="submit" class="btn btn-light">Open</button>
      </form>
    </div>
    <figure class="art">${raw(art(ctx.sceneSeries || []))}
      ${spx && isNum(spx.chg_120d) ? html`<figcaption class="art-cap"><span>S&amp;P 500</span><b class="${dir(spx.chg_120d)}">${signed(spx.chg_120d, 1)}</b>over six months</figcaption>` : ''}</figure>
  </section>`;
}

export function starters(rows) {
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

export function modes(list) {
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
        <p class="section-sub">${store.signedIn() ? 'They go into your account\'s watchlist.' : 'Kept in this browser. Sign in to keep them on your account.'}</p></div></div>
        <div id="hm-starters">${skeleton('rows', 2)}</div></section>
      <section class="section" id="hm-modes" hidden aria-labelledby="md-h"><div class="section-head"><div><h2 class="t-h2" id="md-h">How should Optic speak to you?</h2><p class="section-sub">Change it any time in Settings.</p></div></div><div id="hm-modes-in"></div></section>
      <section class="section" aria-labelledby="pa-h"><h2 class="sr" id="pa-h">Ways to start</h2><div class="paths">
        <div class="path"><p class="t-h3">Look up a company</p><p>Every Dossier answers four questions first: the business, the price, the trade and what is next.</p><button type="button" class="textlink" data-v2-open-palette>Search ${icon('arrow')}</button></div>
        <div class="path"><p class="t-h3">Read today's market</p><p>The day's read, the macro regime and the index cycles.</p><a class="textlink" href="#/read">Open Read ${icon('arrow')}</a></div>
        <div class="path"><p class="t-h3">${store.signedIn() ? 'Set alerts' : 'Keep it on an account'}</p><p>${store.signedIn() ? 'Optic checks your alerts about every 30 minutes on market days and keeps what fired.' : 'A free account keeps your watchlists and alerts on any device.'}</p>${store.signedIn() ? html`<a class="textlink" href="#/alerts">Alerts ${icon('arrow')}</a>` : html`<a class="textlink" href="#/signin">Sign in or create one ${icon('arrow')}</a>`}</div>
      </div></section>`
    : html`<div id="hm-hero"></div><div id="hm-scene">${skeleton('chart', 1, 'Loading the market')}</div>
      <section class="section" aria-labelledby="wl-h"><div class="section-head"><div><h2 class="t-h2" id="wl-h">${list ? list.name : 'Your watchlist'}</h2><p class="section-sub">Price, today's move and the last 30 sessions. Choose a row for what changed.</p></div>
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
  const slow = setTimeout(() => { if ($('.sk-wrap', host)) host.insertAdjacentHTML('beforeend', '<p class="asof" role="status">Still loading the calendar and this week\'s earnings. It can take up to a minute.</p>'); }, 8000);
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

// Home's blocks are drawn inside the research workspace (pages/workspace.js);
// these let it hand over the illustration's series and read the portfolio's.
export const setScene = (series) => { ctx.sceneSeries = series || []; };
export const portfolioSeries = () => ctx.portfolio || [];
export { wireForms };

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
    const ev = evPress(e.target);
    if (ev) {
      if (ev.repaint && ctx.priority) { draw($('#hm-priority', main), eventsBlock(ctx.priority, store.allSymbols(), ctx.evFilter)); const again = $(`[data-v2-cs="${ev.focus}"]`, main); if (again) again.focus(); }
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
