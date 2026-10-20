// Pieces about one company used on several pages: the Watch toggle, the
// watchlist row, and the company drawer that opens from a row (master-detail:
// the list stays put, the detail opens beside it).
import { html, raw } from '../core/dom.js';
import { num, signed, dir, money, clean, capFirst } from '../core/format.js';
import { spark } from './chart.js';
import { icon } from './icons.js';
import * as drawer from './drawer.js';
import * as store from '../core/store.js';
import { toast } from './toast.js';
import { explain } from '../core/api.js';
import { button as miloButton } from './milo.js';

export function watchButton(sym, { compact = false } = {}) {
  const on = store.isFollowed(sym);
  return html`<button type="button" class="btn ${compact ? 'btn-sm' : ''}" data-v2-watch="${sym}" aria-pressed="${on}">${on ? 'Watching' : 'Watch'}</button>`;
}

/** Follow or unfollow from any Watch button; says what happened, with Undo. */
export async function toggleWatch(sym) {
  const was = store.isFollowed(sym);
  try {
    if (was) {
      const lists = (store.state.lists || []).filter((l) => l.symbols.includes(sym)).map((l) => l.id);
      await store.unfollowEverywhere(sym);
      toast(`${sym} removed from your watchlist.`, { action: 'Undo', run: () => lists.forEach((id) => store.follow(sym, id).catch(() => {})) });
    } else {
      await store.follow(sym);
      const l = store.activeList();
      toast(`${sym} added to ${l ? l.name : 'your watchlist'}.`, { action: 'Undo', run: () => store.unfollowEverywhere(sym).catch(() => {}) });
    }
  } catch (e) {
    toast(e.message && e.kind === 'limit' ? e.message : explain(e, 'The change'), { kind: 'bad' });
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

/** The company drawer: the row's facts, why, and where to go next. */
export function openCompany(r, opener, { context = 'Home' } = {}) {
  const sym = r.symbol;
  drawer.open({
    kicker: context === 'Home' ? 'From your watchlist' : context,
    title: sym,
    opener,
    body: html`<div class="figure"><p class="t-label">Last price</p><p class="t-display-m">${money(r.price)}</p>
        <p class="delta"><span class="${dir(r.change_pct)}">${signed(r.change_pct)} today</span><span class="${dir(r.change_5d_pct)}">${signed(r.change_5d_pct)} over 5 days</span><span class="${dir(r.change_20d_pct)}">${signed(r.change_20d_pct)} over 20</span></p></div>
      <dl class="kv">
        <div><dt>What changed</dt><dd class="note">${r.changed ? html`${clean(r.changed.text)}. ${capFirst(clean(r.changed.why || ''))}.` : 'No change worth noting since the last close.'}</dd></div>
        <div><dt>Signal</dt><dd class="note">${signalWord[r.signal] || 'No signal'}${r.signal_why ? html`: ${clean(r.signal_why)}` : ''}</dd></div>
      </dl>
      <div class="cluster"><a class="btn btn-primary" href="#/${sym}">Open the Dossier</a>${watchButton(sym)}</div>
      ${miloButton(`Ask Milo about ${sym}`, { ask: `What should I know about ${sym} right now?`, context: `${sym}, from your watchlist`, symbol: sym })}
      <p class="asof">Computed from daily closes by fixed thresholds, not written by a model. Each change names the number that triggered it.</p>`,
  });
}
