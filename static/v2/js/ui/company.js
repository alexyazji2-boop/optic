// One More menu for a ticker (motion proposal Phase 2, 2026-10-24), the same wherever it opens: set an alert, compare,
// the printable sheet, show it on Home, and copy the ticker or the price as it is on screen with its time. The first
// three are buttons of their own on a wide header, so there they sit in the menu only on a phone (.menu-phone).
// `price` is a selector for the figure to copy, read from the page so what is copied is what the reader sees.
export function tickerMenu(sym, { price = '.dhead .dh-price', sheet = true } = {}) {
  const e = encodeURIComponent(sym);
  return html`<a class="menu-phone" href="#/alerts?symbol=${e}">Set an alert</a><a class="menu-phone" href="#/compare?t=${e}">Compare</a>${sheet ? html`<a class="menu-phone" href="#/${e}/sheet">Export research sheet</a>` : ''}
    <button type="button" data-v2-homelink="${sym}">Show on Home</button>
    <button type="button" data-v2-copy="${sym}">Copy ticker</button>
    ${price ? html`<button type="button" data-v2-copy-price="${sym}" data-v2-copy-from="${price}">Copy price and time</button>` : ''}`;
}

// Pieces about one company used on several pages: the Watch toggle, the
// watchlist row, and the company drawer that opens from a row (master-detail:
// the list stays put, the detail opens beside it).
import { html, raw } from '../core/dom.js';
import { num, signed, dir, money, clean, capFirst, shortDate } from '../core/format.js';
import { spark } from './chart.js';
import { icon } from './icons.js';
import * as drawer from './drawer.js';
import * as store from '../core/store.js';
import { toast } from './toast.js';
import { explain, get as apiGet } from '../core/api.js';
import { holds } from '../core/device.js';
import { render as draw } from '../core/dom.js';
import { button as miloButton } from './milo.js';
import { hrefFor } from '../nav.js';
import { linkHome } from '../core/homelink.js';

const names = (ls) => (ls.length < 3 ? ls.map((l) => l.name).join(' and ') : `${ls.length} lists`);
export function watchButton(sym, { compact = false } = {}) {
  const on = store.listsWith(sym);
  // Watching names where: the toggle takes the symbol off every list it is on, and says so
  return html`<button type="button" class="btn ${compact ? 'btn-sm' : ''}" data-v2-watch="${sym}" aria-pressed="${on.length > 0}" title="${on.length ? `On ${names(on)}. Press to take it off.` : 'Add to the open watchlist'}">${on.length ? 'Watching' : 'Watch'}${on.length ? html`<span class="sr"> on ${names(on)}</span>` : ''}</button>`;
}

const undoFailed = (e) => toast(`Undo did not go through: ${explain(e, 'The change')}`, { kind: 'bad' });

/** Follow or unfollow from any Watch button; says what happened and where, with Undo. */
export async function toggleWatch(sym) {
  sym = store.canon(sym);
  const was = store.listsWith(sym);
  try {
    if (was.length) {
      const where = await store.unfollowEverywhere(sym);
      toast(`${sym} taken off ${names(was)}.`, { action: 'Undo', run: async () => { try { for (const w of where) await store.follow(sym, w.id, { at: w.at }); } catch (e) { undoFailed(e); } } });   // eslint-disable-line no-await-in-loop
    } else {
      await store.follow(sym);
      const l = store.activeList(), id = l && l.id;
      toast(`${sym} added to ${l ? l.name : 'your watchlist'}.`, { action: 'Undo', run: () => store.unfollow(sym, id).catch(undoFailed) });
    }
  } catch (e) {
    toast(e.message && (e.kind === 'limit' || e.kind === 'bad' || e.status === 0) ? e.message : explain(e, 'The change'), { kind: 'bad' });
  }
}

const signalWord = { bullish: 'Bullish', bearish: 'Bearish', neutral: 'Neutral', unknown: 'No signal' };

/** One watchlist row from /api/watchlist. */
export function row(r, { names = {}, expanded = false } = {}) {
  if (!r.available) {
    return html`<div class="row row-off" role="listitem"><span class="who"><b class="tick">${r.symbol}</b><small>${clean(r.reason || 'No data for this symbol right now.')}</small></span></div>`;
  }
  const name = names[r.symbol] || '';
  return html`<button type="button" class="row" data-v2-company="${r.symbol}" aria-expanded="${expanded}" role="listitem">
    <span class="who"><b class="tick">${r.symbol}</b>${name ? html`<small>${name}</small>` : ''}</span>
    <span class="num c2">${num(r.price)}</span>
    <span class="num c3 ${dir(r.change_pct)}">${signed(r.change_pct)}<span class="sr"> today</span></span>
    <span class="spark-cell">${raw(spark(r.spark, `${r.symbol}, last 30 sessions`))}</span>
    <span class="note c4">${r.changed ? clean(r.changed.text) : html`<span class="t-muted">No change worth noting</span>`}</span>
    <span class="sig sig-${r.signal}">${signalWord[r.signal] || 'No signal'}</span>
    ${icon('chev')}
  </button>`;
}

/** Volume against its 20-session average, said as a part day while the session runs. */
export function volumeLine(r) {
  if (!r || !Number.isFinite(r.volume_ratio)) return '';
  return r.volume_partial ? `${num(r.volume_ratio, 1)}× its average so far today` : `${num(r.volume_ratio, 1)}× its 20-session average`;
}
/** The next report, as a date and a distance; '' when none is known yet. */
export function earningsLine(e) {
  if (!e || e.loading) return '';
  if (!e.date) return 'No date published';
  return `${shortDate(e.date)}, ${e.days === 0 ? 'today' : e.days === 1 ? 'tomorrow' : `in ${e.days} days`}`;
}

const etDay = (d) => { try { return new Date(d).toLocaleDateString('en-CA', { timeZone: 'America/New_York' }); } catch (e) { return ''; } };
/** The reader's alerts per symbol: how many are on, and how many fired today (ET). The account's
 * when signed in, this browser's otherwise (optic.watches.v1, the classic key). null when unreadable. */
export async function alertsBySymbol() {
  let list;
  if (store.signedIn()) { try { list = ((await apiGet('/api/watches', { ttl: 30000 })) || {}).watches || []; } catch (e) { return null; } }
  else { list = []; if (holds(store.state.user)) { try { const v = JSON.parse(localStorage.getItem('optic.watches.v1') || '[]'); list = Array.isArray(v) ? v : []; } catch (e) { list = []; } } }
  const today = etDay(Date.now()), out = {};
  list.forEach((w) => { const s = store.canon(w.symbol); const o = out[s] || (out[s] = { n: 0, fired: 0 }); if (w.active !== false && w.active !== 0) o.n += 1; if (w.last_met_at && etDay(w.last_met_at) === today) o.fired += 1; });
  return out;
}
const earnDd = (earnings) => (earnings && !earnings.loading ? (earnings.failed ? html`<span class="t-muted">Did not load</span>` : earningsLine(earnings)) : html`<span class="t-muted">Looking it up</span>`);
const alertDd = (sym, alerts) => (alerts && alerts.n ? html`${alerts.n} set${alerts.fired ? html`, <b>${alerts.fired} fired today</b>` : ''}.<br><a class="textlink" href="#/alerts?symbol=${encodeURIComponent(sym)}">See ${alerts.n === 1 ? 'it' : 'them'}</a>` : html`None set.<br><a class="textlink" href="#/alerts?symbol=${encodeURIComponent(sym)}">Set one</a>`);

/** The company drawer: the row's facts, why, and where to go next. */
export function openCompany(r, opener, { context = 'Home', earnings = null, alerts = null } = {}) {
  const sym = r.symbol;
  const on = store.listsWith(sym);
  drawer.open({
    kicker: context === 'Home' ? 'From your watchlist' : context,
    title: sym,
    opener,
    body: html`<div class="figure"><p class="t-label">Last price</p><p class="t-display-m">${money(r.price)}</p>
        <p class="delta"><span class="${dir(r.change_pct)}">${signed(r.change_pct)} today</span><span class="${dir(r.change_5d_pct)}">${signed(r.change_5d_pct)} over 5 days</span><span class="${dir(r.change_20d_pct)}">${signed(r.change_20d_pct)} over 20</span></p></div>
      <dl class="kv">
        <div><dt>What changed</dt><dd class="note">${r.changed ? html`${clean(r.changed.text)}. ${capFirst(clean(r.changed.why || ''))}.` : 'No change worth noting since the last close.'}</dd></div>
        <div><dt>Signal</dt><dd class="note">${signalWord[r.signal] || 'No signal'}${r.signal_why ? html`: ${clean(r.signal_why)}` : ''}</dd></div>
        <div><dt>Volume</dt><dd>${volumeLine(r) || html`<span class="t-muted">Not reported</span>`}${r.as_of ? html`<br><small class="t-muted">Session of ${shortDate(r.as_of)}</small>` : ''}</dd></div>
        <div><dt>Next earnings</dt><dd id="co-earn">${earnDd(earnings)}</dd></div>
        <div><dt>Alerts</dt><dd id="co-alerts">${alerts ? alertDd(sym, alerts) : html`<span class="t-muted">Looking them up</span>`}</dd></div>
        <div><dt>Lists</dt><dd>${on.length ? names(on) : html`<span class="t-muted">Not on a list</span>`}</dd></div>
      </dl>
      <div class="cluster"><a class="btn btn-primary" href="${hrefFor('overview', sym)}">Open the Dossier</a>${watchButton(sym)}</div>
      <div class="cluster co-go" role="group" aria-label="Open ${sym} in">${[['Chart', 'chart'], ['Options', 'swing'], ['Earnings', 'earnings']].map(([l, v]) => html`<a class="btn btn-sm" href="${hrefFor(v, sym)}">${l}</a>`)}
        <details class="menu co-more"><summary class="btn btn-sm" aria-label="More actions for ${sym}">More ${icon('chev')}</summary><div class="menu-body">${tickerMenu(sym, { price: null })}</div></details></div>
      ${miloButton(`Ask Milo about ${sym}`, { ask: `What should I know about ${sym} right now?`, context: `${sym}, from your watchlist`, symbol: sym })}
      <p class="asof">From daily bars and the companies' published calendars, by fixed rules: nothing here is written by a model. Each change names the number that triggered it.</p>`,
  });
  const put = (id, v) => { const el = document.getElementById(id); if (el) draw(el, v); };
  if (!earnings || earnings.loading) apiGet(`/api/watchlist/earnings?symbols=${encodeURIComponent(sym)}`, { ttl: 3600000, timeout: 30000 }).then((d) => put('co-earn', earnDd(((d && d.dates) || {})[sym] || { date: null })), () => put('co-earn', earnDd({ failed: true })));
  if (!alerts) alertsBySymbol().then((m) => put('co-alerts', m ? alertDd(sym, m[sym] || { n: 0 }) : html`<span class="t-muted">Did not load</span>`));
}
