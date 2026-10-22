// Positions, Optic Portfolio: the terminal's own paper-traded record. Three
// books (conservative, balanced, aggressive) run the same scan under three
// rule sets, shared by everyone, never real money. From /api/tracker and
// /api/portfolio-risk; "Run a scan now" and "Refresh marks" are the server's
// own cooldown-guarded actions. No model call anywhere on the page.
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, signed, money, compact, clean, capFirst, shortDate, isNum } from '../core/format.js';
import { stamp, advancedOn } from '../core/prefs.js';
import { skeleton, failed } from '../ui/states.js';
import { signedBars, hbars } from '../ui/bars.js';
import { mountCharts } from '../ui/chart.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { sectionHead } from './tabs.js';

let book = 'balanced', month = null, D = {}, live = true, mainEl = null, poll = null, scanning = false, notice = null;
const $0 = (v) => (isNum(v) ? money(v, 0) : 'n/a');
const tone = (v) => (!isNum(v) ? '' : v > 0 ? 'up' : v < 0 ? 'down' : '');
const tile = (k, v, note, cls = '') => html`<div><dt>${k}</dt><dd class="${cls}">${v}</dd>${note ? html`<p class="kv-note">${note}</p>` : ''}</div>`;

/** Days a position has been held, the classic way: whole days, never negative. */
export function heldDays(from, to, now = Date.now()) {
  if (!from) return null;
  const a = new Date(from).getTime(), b = to ? new Date(to).getTime() : now;
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  return Math.max(Math.round((b - a) / 86400000), 0);
}
/** Where the stock sits between stop and target (static/app.js positionTravel). */
export function travel(p) {
  const n = (v) => (v === null || v === undefined || !Number.isFinite(Number(v)) ? null : Number(v));
  const stop = n(p.stop), target = n(p.target);
  const now = n(p.mark_spot) === null ? n(p.mark_price) : n(p.mark_spot);
  const entry = n(p.entry_spot) === null ? n(p.entry_price) : n(p.entry_spot);
  if (stop === null || target === null || now === null) return null;
  if (target <= 0) return { stop, target, now, unreachable: true };
  const span = target - stop; if (!span) return null;
  const frac = (v) => Math.max(0, Math.min(1, (v - stop) / span));
  return { stop, target, now, entry, at: frac(now), from: entry === null ? null : frac(entry), ahead: entry === null ? null : (now - entry) / span >= 0 };
}
export function travelRead(t) {
  const span = t.target - t.stop, r = span ? (t.now - t.stop) / span : null;
  if (r === null) return '';
  if (r >= 1) return 'At or past the target';
  if (r <= 0) return 'At or past the stop';
  if (t.from === null) return `${Math.round(r * 100)}% of the way from stop to target`;
  if (r >= t.from) { const room = 1 - t.from; return room > 0 ? `${Math.round(((r - t.from) / room) * 100)}% of the way from entry to target` : 'At the target'; }
  return t.from > 0 ? `${Math.round(((t.from - r) / t.from) * 100)}% of the way from entry to the stop` : 'At the stop';
}
const markNote = (s) => (/^modelled/i.test(s || '') ? ', estimated' : /^entry price/i.test(s || '') ? ', not yet marked' : /^expired/i.test(s || '') ? ', at expiry' : '');
const modelled = (p) => /^modelled/i.test(String(p.mark_source || ''));

function label(p) {
  const sym = html`<a href="#/${p.ticker}">${p.ticker}</a>`;
  if (p.instrument !== 'option') return html`${sym} shares`;
  return html`${sym} $${num(p.strike, 0)} ${p.option_type || ''}<br><small class="t-muted">expires ${p.expiry ? shortDate(p.expiry) : ''}</small>`;
}
function side(p) {
  if (p.instrument !== 'option') { const l = p.direction === 'long'; return html`${l ? 'Bullish' : 'Bearish'}<br><small class="t-muted">${l ? 'Owns the shares' : 'Sold short'}</small>`; }
  const put = p.option_type === 'put';
  return html`${put ? 'Bearish' : 'Bullish'}<br><small class="t-muted">Owns the ${put ? 'put' : 'call'}</small>`;
}
function size(p) {
  return p.instrument === 'option' ? html`${num(p.qty, 0)} contract${p.qty === 1 ? '' : 's'}<br><small class="t-muted">${$0(p.qty * p.entry_price * 100)} premium</small>`
    : html`${num(p.qty, 0)} shares<br><small class="t-muted">${$0(p.qty * p.entry_price)} notional</small>`;
}
function gauge(p) {
  const t = travel(p);
  if (!t) return html`<span class="t-muted">n/a</span>`;
  if (t.unreachable) return html`<div class="pos-gauge"><div class="pos-ends"><span>stop ${num(t.stop)}</span><span>now ${num(t.now)}</span></div><p class="pos-read">No reachable target. Stop or time stop only.</p></div>`;
  const cls = t.ahead === null ? '' : t.ahead ? 'up' : 'down', at = t.at * 100, from = t.from === null ? at : t.from * 100, a = Math.min(at, from), b = Math.max(at, from);
  return html`<div class="pos-gauge"><div class="pos-ends"><span>stop ${num(t.stop)}</span><span>target ${num(t.target)}</span></div>
    <div class="pos-track" role="img" aria-label="${travelRead(t)}"><span class="pos-fill ${cls}" style="left:${a.toFixed(1)}%;width:${(b - a).toFixed(1)}%"></span>${t.from === null ? '' : html`<i class="pos-entry" style="left:${from.toFixed(1)}%" title="opened with the stock at ${num(t.entry)}"></i>`}<i class="pos-now ${cls}" style="left:${at.toFixed(1)}%" title="the stock is at ${num(t.now)} now"></i></div>
    <p class="pos-read">${travelRead(t)}${p.instrument === 'option' && t.entry !== null ? html`<br>on the stock: ${num(t.now)}, opened at ${num(t.entry)}` : ''}</p></div>`;
}
const pnlCell = (p) => html`<b class="${tone(p.pnl)}">${$0(p.pnl)}</b><br><small class="t-muted">${signed(p.pnl_pct, 1)}</small>`;

/* ---------------- sections ---------------- */
// "High risk, high reward" read as a promise: higher risk means wider swings both ways, never a better return
const RISK_WORDS = { conservative: 'Smaller risk per trade', balanced: 'Middle risk per trade', aggressive: 'Higher risk: bigger gains and bigger losses' };
function books(d) {
  const bs = d.books || [];
  if (bs.length < 2) return '';
  const dated = bs.filter((b) => b.since).map((b) => b.since).sort();
  return html`<section class="section first" aria-labelledby="bk-h"><div class="section-head"><div><h2 class="t-h2" id="bk-h">Three simulated accounts</h2>
      <p class="section-sub">Each account, which traders call a book, runs the same scan under its own rules. Identical candidates, so comparing them says what a risk tolerance costs and earns rather than comparing three different signals. Each book has its own $100,000 and its own record.</p></div>
      ${miloButton('Ask Milo what differs', { ask: 'Explain the three books. What actually differs between conservative, balanced and aggressive, and what does comparing them tell me that one book alone would not?', context: 'Optic Portfolio' })}</div>
    <div class="book-cards" role="group" aria-label="Choose a book">${bs.map((b) => { const su = b.summary || {}, traded = (su.open_count || 0) + (su.closed_count || 0) > 0, val = isNum(su.start_equity) ? su.start_equity + (su.total_pnl || 0) : b.equity;
      return html`<button type="button" class="book-card" data-v2-book="${b.id}" aria-pressed="${b.id === (d.book || book)}">
        <span class="bk-top"><b>${b.label}</b><span class="pill">${RISK_WORDS[b.id] || b.tagline}</span></span>
        <span class="bk-figs"><span><i>Value</i>$${compact(val)}</span>${traded ? html`<span><i>Return</i><b class="${tone(su.return_pct)}">${signed(su.return_pct, 2)}</b></span><span><i>Open</i>${num(su.open_count, 0)}</span><span><i>Closed</i>${num(su.closed_count, 0)}</span>` : html`<span><i>Record</i>No trades yet</span>`}</span>
        ${b.since ? html`<span class="bk-since">Record from ${b.since}</span>` : ''}
        <span class="bk-rules">${num(b.risk_per_trade * 100, 1)}% per trade, score bar ${num(b.min_composite, 0)}, ${b.allow_options ? (b.prefer_options ? 'options preferred' : 'shares and options') : 'shares only'}, max daily range ${num(b.max_atr_pct, 0)}%</span>
        <span class="bk-blurb">${b.blurb}</span></button>`; })}</div>
    ${dated.length > 1 && dated[0] !== dated[dated.length - 1] ? html`<p class="asof">Their records do not begin on the same day, so the returns above are only like for like from ${dated[dated.length - 1]} onward. Before that a scan could fill one book's risk budget and stop before the others were offered the same candidate, which is fixed but not retrospective.</p>` : ''}
    <p class="asof">They differ in the four things that actually change a risk profile: how selective the entry bar is, how much is risked per trade, which instruments are allowed, and how volatile a name may be. Nothing changes the analysis. A setup is a setup, and these decide what to do about it.</p></section>`;
}

function ledger(d) {
  const s = d.summary || {}, cfg = d.config || {}, cap = d.capacity || {}, prog = d.progress || {}, run = scanning || !!prog.running;
  const name = ((d.books || []).find((b) => b.id === (d.book || book)) || {}).label || '';
  const hint = cfg.universe === 'curated' ? html`Universe: <b>${(cfg.universe_symbols || []).length} large names and index funds</b>, leveraged ones included, listed under How these positions are taken. A scan screens all of them on price and volume, then puts the top ${cfg.shortlist_size} through the full analysis. It also runs on its own every few hours while the server is up.`
    : cfg.universe === 'nasdaq' ? html`Universe: <b>every NASDAQ-listed common stock</b>, about 3,000 names. A scan screens all of them on price and volume, then puts the top ${cfg.shortlist_size} through the full analysis, so it takes a few minutes.`
      : `Watchlist: ${(cfg.watchlist || []).join(', ')}. A scan puts all of them through the full analysis.`;
  return html`<section class="section" aria-labelledby="op-h"><h2 class="t-h2" id="op-h">Optic Portfolio${name ? html` <span class="pill">${name}</span>` : ''}</h2>
    <p class="section-sub">Three simulated ledgers, one per rule set, trading Optic's own signals. Every reader sees the same books.${name ? ` You are looking at the ${name.toLowerCase()} book; the cards above switch between them.` : ''} Each trades both instruments the Options tab produces: the shares, and the exact contract it recommended.</p>
    ${run ? '' : html`<details class="more-inline tk-ops"><summary>Run the shared scan or refresh prices</summary>
      <p class="asof">These act on the demonstration portfolio every reader sees. Anyone may run a scan once every half hour; it also runs on its own every few hours. Refreshing prices only re-marks the open positions.</p>
      <div class="cluster tk-bar"><button type="button" class="btn" data-v2-tk="scan">Run a scan now</button><button type="button" class="btn" data-v2-tk="mark">Refresh marks</button></div>
      <p class="asof">${hint}</p></details>`}
    ${notice ? html`<div class="state" role="status"><p>${notice}</p></div>` : ''}
    ${d.market_open ? '' : html`<p class="stale"><b>The market is closed.</b> Open positions are still re-marked at the closing price, but no new entries are taken while the tape is shut. A fill at a stale price isn't a trade anyone could have got. Scanning resumes at the next open (9:30am ET, weekdays).</p>`}
    ${run ? html`<div class="tk-progress" role="status"><p><b>${prog.stage || 'Working'}</b>${prog.note ? ` ${prog.note}` : ''}${prog.total ? ` ${prog.done} of ${prog.total}` : ''}${prog.trigger === 'scheduled' ? ' (scheduled)' : ''}</p>${prog.total ? html`<div class="build-bar"><span style="width:${Math.min(100, Math.round((prog.done / prog.total) * 100))}%"></span></div>` : ''}</div>` : ''}
    ${(d.feed || {}).throttled ? html`<p class="stale"><b>The price feed is rate-limiting right now.</b> A scan during a block takes fewer positions, not wrong ones: a blocked options request looks like a stock with no options, so Optic skips those names rather than recording a shares-only trade. Clears in about ${num(d.feed.seconds_remaining, 0)}s.</p>` : ''}
    <dl class="kv" style="--kv:4">${tile('Account value', $0(s.start_equity + s.total_pnl), `started at ${$0(s.start_equity)}`, tone(s.total_pnl))}${tile('Realised P&L', $0(s.realised_pnl), `${s.closed_count || 0} closed ${s.closed_count === 1 ? 'trade' : 'trades'}`, tone(s.realised_pnl))}
      ${tile('Unrealised P&L', $0(s.unrealised_pnl), `${s.open_count || 0} open now`, tone(s.unrealised_pnl))}${tile('Total return', signed(s.return_pct, 2), 'realised plus open marks', tone(s.return_pct))}</dl>
    <details class="more-inline" ${advancedOn() ? 'open' : ''}><summary>How the book limits its risk</summary>
      <dl class="kv" style="--kv:5">${tile('Position slots', `${cap.open_positions || 0} / ${cfg.max_open_positions || 'n/a'}`, `${cap.position_slots_left || 0} left`)}${tile('Risk deployed', $0(cap.open_risk), `${num(cap.open_risk_pct, 1)}% of a ${num(cfg.max_portfolio_risk_pct, 0)}% budget`)}
        ${tile('Risk budget left', $0(cap.risk_budget_left), 'before the book stops adding')}${tile('Sizing base', $0(s.equity), 'closed trades only, so an open run-up cannot raise the next bet')}${tile('New per scan', num(cfg.max_new_per_scan, 0), 'so the book fills over days')}</dl>
      <p class="asof">The caps exist because one scan can find many qualifying setups at once. Without them it could put a third of the account at risk in an afternoon, on names that are often the same bet under different tickers: TQQQ, QQQ and NVIDIA move together.</p></details></section>`;
}

function openPositions(open) {
  if (!open.length) return '';
  const scored = open.filter((p) => isNum(p.pnl)), up = scored.filter((p) => p.pnl > 0).length, down = scored.filter((p) => p.pnl < 0).length;
  const best = scored.reduce((m, p) => (p.pnl > m.pnl ? p : m), scored[0] || {}), worst = scored.reduce((m, p) => (p.pnl < m.pnl ? p : m), scored[0] || {});
  const nm = (p) => `${p.ticker}${p.instrument === 'option' ? ' (option)' : ''}`;
  const total = scored.reduce((a, p) => a + p.pnl, 0), top = scored.reduce((m, p) => (Math.abs(p.pnl) > Math.abs(m.pnl) ? p : m), scored[0] || {});
  return html`<section class="section" aria-labelledby="oo-h"><h2 class="t-h2" id="oo-h">Open positions</h2>
    <p class="section-sub">The ${open.length === 1 ? 'one trade' : `${open.length} trades`} the ledger is holding right now. Each will end at one of two prices decided when it opened: a <b>stop</b>, which cuts the loss if the trade is wrong, or a <b>target</b>, which takes the gain if it is right. The bar shows how far the stock has travelled between the two: the tick is where the trade opened, the dot is where the stock is now.</p>
    ${scored.length ? html`<p class="lead-line"><b>${up} of ${scored.length} are up</b>${down ? `, ${down} ${down === 1 ? 'is' : 'are'} down` : ''}.${best !== worst ? ` Best is ${nm(best)} at ${$0(best.pnl)}; worst is ${nm(worst)} at ${$0(worst.pnl)}.` : ''} None of it is real money: no order is ever sent to a broker.</p>` : ''}
    ${scored.length >= 2 ? html`<h3>${total >= 0 ? 'Up' : 'Down'} ${$0(Math.abs(total))} across ${scored.length} open trades; ${nm(top)} is the largest at ${$0(top.pnl)}</h3><div class="chart-slot" data-chart="open"></div><p class="asof">Unrealised profit or loss at the latest mark, in dollars. Nothing is settled until a trade closes.${open.some(modelled) ? ' Some option marks are estimated by a model; the table says which.' : ''}</p>` : ''}
    <div class="tscroll"><table class="t tk-t"><thead><tr><th scope="col">Position</th><th scope="col">Betting on</th><th scope="col">Size</th><th scope="col">Paid</th><th scope="col">Where it stands</th><th scope="col">Up or down</th><th scope="col">If stopped</th><th scope="col">Signal score</th><th scope="col">Held</th></tr></thead>
      <tbody>${open.map((p) => html`<tr><td>${label(p)}</td><td>${side(p)}</td><td>${size(p)}</td><td>${num(p.entry_price)}<br><small class="t-muted">now ${num(p.mark_price)}${markNote(p.mark_source)}</small></td><td>${gauge(p)}</td><td>${pnlCell(p)}</td><td>${$0(p.risk_dollars)}</td><td>${isNum(p.composite) ? num(Math.abs(p.composite), 0) : 'n/a'}</td><td>${heldDays(p.entry_at) === null ? 'n/a' : `${heldDays(p.entry_at)}d`}</td></tr>`)}</tbody></table></div>
    <p class="asof">Stop and target are prices on the underlying stock for both instruments, which is why an option row can be losing while its bar moves the right way: time decay can drain the premium while the stock sits still. An option also carries its own exits on the premium, at −50% and +100%. Options are re-priced from the live chain; with no usable quote the mark falls back to a Black-Scholes estimate, marked "estimated".</p>
    ${open.some((p) => isNum(p.target) && p.target <= 0) ? html`<p class="asof">A row reading <i>no reachable target</i> is a short whose stop put its 2:1 target below zero, so it can only end at its stop or its time stop. The scanner now declines these; the ones on the book are left in place rather than quietly deleted.</p>` : ''}</section>`;
}

function months(d) {
  const ms = d.months || [], mo = d.month || {}, st = ms.find((m) => m.key === (d.selected_month || mo.key)) || {};
  const last = ms.length ? ms[ms.length - 1].key : null, arch = d.archive || [];
  const done = ms.slice(0, -1).filter((m) => isNum(m.realised_pnl)), gains = done.filter((m) => m.realised_pnl > 0).length;
  return html`<section class="section" aria-labelledby="mm-h"><h2 class="t-h2" id="mm-h">Month by month</h2>
    <p class="section-sub">Results split by the month a trade <i>closed</i>, the month the money was actually made or lost. A position opened in one month and closed in the next counts toward the month it closed in, and appears in the earlier month's opened count.</p>
    <div class="cluster">${ms.length ? html`<label class="select"><span class="sr">Month to show</span><select data-v2-tk-month>${ms.slice().reverse().map((m) => html`<option value="${m.key}" ${m.key === d.selected_month ? 'selected' : ''}>${m.label}${m.key === last ? ' (current)' : ''}</option>`)}</select></label>` : ''}
      <p class="t-muted">Showing <b>${mo.label || 'n/a'}</b>${mo.is_current ? '. Still in progress, so these figures are not final.' : '.'} The record runs from ${ms.length ? ms[0].label : 'this month'} and includes every trade ${arch.length ? `taken since it restarted on ${String(arch[arch.length - 1].archived_at || '').slice(0, 10)}, nothing excluded. The earlier record is kept, under Earlier records.` : 'the ledger has taken, nothing excluded.'}</p></div>
    <dl class="kv" style="--kv:4">${tile('Closed this month', num(st.closed_count, 0), `${num(st.opened_count, 0)} position${st.opened_count === 1 ? '' : 's'} opened`)}${tile('Realised P&L', $0(st.realised_pnl), `from ${num(st.closed_count, 0)} closed`, tone(st.realised_pnl))}
      ${tile('Return', signed(st.return_pct, 2), `on ${$0(st.start_equity)} at the start`, tone(st.return_pct))}${tile('Expectancy', $0(st.expectancy), 'average result per closed trade', tone(st.expectancy))}</dl>
    ${(mo.closed || []).length ? html`<h3>Closed in this month</h3><div class="tscroll"><table class="t"><thead><tr><th scope="col">Position</th><th scope="col">Side</th><th scope="col">Entry</th><th scope="col">Exit</th><th scope="col">P&L</th><th scope="col">Why it closed</th><th scope="col">Closed</th></tr></thead>
      <tbody>${mo.closed.map((p) => html`<tr><td>${label(p)}</td><td>${side(p)}</td><td>${num(p.entry_price)}</td><td>${num(p.exit_price)}</td><td>${pnlCell(p)}</td><td>${capFirst(p.exit_reason || '') || 'n/a'}</td><td>${p.exit_at ? shortDate(p.exit_at) : 'n/a'}</td></tr>`)}</tbody></table></div>`
      : html`<p class="quiet">No trades closed in ${mo.label || 'this month'}.${mo.is_current ? ' Positions opened this month are still running.' : ''}</p>`}
    ${(mo.still_open || []).length ? html`<h3>Opened in this month and still held</h3><div class="tscroll"><table class="t"><thead><tr><th scope="col">Position</th><th scope="col">Side</th><th scope="col">Size</th><th scope="col">Entry</th><th scope="col">Mark</th><th scope="col">P&L</th><th scope="col">Held</th></tr></thead>
      <tbody>${mo.still_open.map((p) => html`<tr><td>${label(p)}</td><td>${side(p)}</td><td>${size(p)}</td><td>${num(p.entry_price)}</td><td>${num(p.mark_price)}</td><td>${pnlCell(p)}</td><td>${heldDays(p.entry_at) === null ? 'n/a' : `${heldDays(p.entry_at)}d`}</td></tr>`)}</tbody></table></div><p class="asof">Unrealised. These carry into whichever month they eventually close in.</p>` : ''}
    ${ms.length > 1 ? html`<h3>Consistency${done.length ? html`: ${gains} of ${done.length} finished month${done.length === 1 ? '' : 's'} closed with a gain` : ''}</h3><div class="chart-slot" data-chart="months"></div>
      <p class="asof">Realised profit or loss by the month trades closed in, in dollars. The latest month is still in progress.</p>
      <div class="tscroll"><table class="t"><thead><tr><th scope="col">Month</th><th scope="col">Opened</th><th scope="col">Closed</th><th scope="col">Realised</th><th scope="col">Return</th><th scope="col">Win rate</th><th scope="col">Expectancy</th><th scope="col">Profit factor</th><th scope="col">Equity after</th></tr></thead>
        <tbody>${ms.slice().reverse().map((m) => html`<tr class="${m.key === d.selected_month ? 'is-now' : ''}"><td>${m.label}${m.key === last ? html` <small class="t-muted">in progress</small>` : ''}</td><td>${num(m.opened_count, 0)}</td><td>${num(m.closed_count, 0)}</td><td class="${tone(m.realised_pnl)}"><b>${$0(m.realised_pnl)}</b></td><td class="${tone(m.return_pct)}">${signed(m.return_pct, 2)}</td><td>${isNum(m.win_rate_pct) ? `${num(m.win_rate_pct, 0)}%` : 'n/a'}</td><td class="${tone(m.expectancy)}">${$0(m.expectancy)}</td><td>${num(m.profit_factor, 2)}</td><td>${$0(m.end_equity)}</td></tr>`)}</tbody></table></div>
      <p class="asof">Equity after carries forward, so each month's return is measured against what the account was worth when that month began rather than against the original stake. A month with no closed trades is still a row. Taking nothing is a decision, and hiding it would flatter the record.</p>`
      : html`<p class="asof">One month of record so far. A consistency table needs several months before it says anything. Treat a single month, good or bad, as noise.</p>`}</section>`;
}

function funnel(d) {
  const f = (d.scans || []).map((x) => x.funnel).find((x) => x && x.screen && x.screen.universe_size);
  if (!f) return '';
  const sc = f.screen || {}, g = (d.config || {}).screen_gates || {}, list = f.shortlist || [];
  const steps = [['Listed', sc.universe_size, f.universe === 'curated' ? 'names on the list' : f.universe === 'nasdaq' ? 'NASDAQ common stocks' : 'symbols'], ['Had usable data', sc.with_data, 'a year of daily bars'], ['Passed liquidity', sc.passed, `over $${compact(g.min_dollar_volume)} a day`], ['Analysed', list.filter((m) => m.analysed).length, 'full swing composite']];
  return html`<section class="section" aria-labelledby="fn-h"><h2 class="t-h2" id="fn-h">How the shortlist was chosen</h2><p class="section-sub">${clean(f.universe_source || '')}</p>
    <ol class="funnel-steps">${steps.map(([l, v, n]) => html`<li><b>${num(v, 0)}</b><span>${l}</span><small class="t-muted">${n}</small></li>`)}</ol>
    <p class="asof">Dropped along the way: ${num(sc.dropped_illiquid, 0)} too thinly traded, ${num(sc.dropped_short_history, 0)} without a year of history, ${num(sc.dropped_too_volatile, 0)} moving more than ${num(g.max_atr_pct, 0)}% a day, ${num(sc.dropped_already_moved, 0)} already up or down more than ${num(g.max_abs_1m_move_pct, 0)}% in a month.${sc.already_held ? ` ${sc.already_held} ranked well but are already held.` : ''}</p>
    ${sc.failed_batches ? html`<p class="stale">${sc.failed_batches} batch(es) of symbols never returned data, even after a retry, almost always the free feed's rate limit. Those names weren't screened.</p>` : ''}
    ${f.throttled_skips ? html`<p class="stale">${f.throttled_skips} shortlisted name(s) were skipped because the feed was still rate-limiting when their options chain was requested. They weren't traded on partial data.</p>` : ''}
    <h3>Screen ranking</h3><p class="t-muted">Top ${list.length} by absolute score. Greyed rows ranked high enough but weren't reached: the scan stopped when a cap bound.</p>
    <div class="tscroll"><table class="t"><thead><tr><th scope="col">#</th><th scope="col">Symbol</th><th scope="col">Screen score</th><th scope="col">Price</th><th scope="col">$ volume/day</th><th scope="col">1-month</th><th scope="col">Reached</th></tr></thead>
      <tbody>${list.map((m, i) => html`<tr class="${m.analysed ? '' : 'is-dim'}"><td class="t-muted">${i + 1}</td><td><a href="#/${m.symbol}">${m.symbol}</a></td><td class="${tone(m.score)}">${m.score > 0 ? '+' : ''}${num(m.score, 0)}</td><td>${num(m.price)}</td><td>$${compact(m.dollar_volume)}</td><td class="${tone(m.roc20)}">${signed(m.roc20, 1)}</td><td class="t-muted">${m.analysed ? 'Analysed' : 'Not reached'}</td></tr>`)}</tbody></table></div>
    ${f.capped ? html`<p class="stale">Stopped early: ${clean(f.capped)}.</p>` : ''}<p class="asof">${clean(sc.caveat || '')}</p></section>`;
}

function record(s) {
  if (!s.closed_count) return '';
  return html`<section class="section" aria-labelledby="tr-h"><h2 class="t-h2" id="tr-h">Track record</h2>
    <dl class="kv" style="--kv:4">${tile('Expectancy', $0(s.expectancy), 'average result per closed trade', tone(s.expectancy))}${tile('Win rate', isNum(s.win_rate_pct) ? `${num(s.win_rate_pct, 0)}%` : 'n/a', `${s.win_count} of ${s.closed_count}`)}${tile('Average win', $0(s.avg_win), s.win_count ? `across ${s.win_count}` : 'none yet', 'up')}${tile('Average loss', $0(s.avg_loss), s.loss_count ? `across ${s.loss_count}` : 'none yet', 'down')}
      ${tile('Profit factor', num(s.profit_factor, 2), 'gross wins ÷ gross losses')}${tile('Closed trades', num(s.closed_count, 0), 'the only results that are final')}${tile('Winners', num(s.win_count, 0), '', 'up')}${tile('Losers', num(s.loss_count, 0), '', 'down')}</dl>
    <p class="asof">A sample this small says almost nothing yet. Win rate on its own is the least useful number here. Expectancy, the average result per trade, is what decides whether there is an edge. Treat anything under about fifty closed trades as noise.</p>
    <p class="asof"><b>How fills are modelled.</b> ${clean((D.d || {}).execution_note || '')}</p></section>`;
}

function risk(d) {
  if (!(d.open || []).length) return '';
  const r = D.risk;
  if (r === undefined) return html`<section class="section"><h2 class="t-h2">Book-level risk</h2><p class="section-sub">Measuring how these positions move together, from three months of returns…</p></section>`;
  if (!r || r.error) return html`<section class="section"><h2 class="t-h2">Book-level risk</h2>${failed('Book-level risk', (r || {}).error, { retry: 'risk' })}</section>`;
  if (!r.available) return html`<section class="section"><h2 class="t-h2">Book-level risk</h2><p>${clean(r.reason || 'Unavailable.')}</p></section>`;
  const dr = r.diversification_ratio, drc = dr === null ? '' : dr < 1.15 ? 'down' : dr >= 1.5 ? 'up' : '';
  const pos = (r.positions || []).slice().sort((a, b) => Math.abs(b.weight_pct) - Math.abs(a.weight_pct));
  const sectors = (r.sectors || []).filter((x) => isNum(x.weight_pct)).sort((a, b) => b.weight_pct - a.weight_pct);
  return html`<section class="section" aria-labelledby="br-h"><div class="section-head"><div><h2 class="t-h2" id="br-h">Book-level risk</h2>
      <p class="section-sub">${num(r.names, 0)} names, ${money(r.gross_exposure, 0)} gross${(r.options || []).length ? ', options at their delta exposure' : ''}. The ledger above reports each trade on its own; this asks whether they are separate bets.</p></div>
      ${miloButton('Ask Milo about gross exposure', { ask: 'What is gross exposure, and how should I read the diversification ratio and effective positions for this book?', context: 'Optic Portfolio, book-level risk' })}</div>
    <dl class="kv" style="--kv:4">${tile('Diversification ratio', dr === null ? 'n/a' : num(dr, 2), '1.0 means nothing is cancelling', drc)}${tile('Book volatility', isNum(r.portfolio_vol_pct) ? `${num(r.portfolio_vol_pct, 0)}%` : 'n/a', `vs ${num(r.weighted_avg_vol_pct, 0)}% average of the parts`)}
      ${tile('Effective positions', isNum(r.effective_positions) ? num(r.effective_positions, 1) : 'n/a', `of ${num(r.names, 0)} held`)}${tile('Largest / top 3', `${num(r.largest_weight_pct, 0)}% / ${num(r.top3_weight_pct, 0)}%`, 'of gross exposure')}</dl>
    <p class="${r.concentrated ? 'stale' : ''}"><b>${r.concentrated ? 'This is one bet.' : 'Correlation read.'}</b> ${clean(r.verdict || '')}</p>
    ${r.sector_warning ? html`<p class="stale"><b>Shared exposure.</b> ${clean(r.sector_warning)}</p>` : ''}
    <div class="grid2"><div><h3>Where the money and the risk sit</h3>
      <div class="tscroll"><table class="t"><thead><tr><th scope="col">Name</th><th scope="col">Sector</th><th scope="col" class="n">Exposure</th><th scope="col" class="n">Risk</th></tr></thead>
        <tbody>${pos.map((p) => html`<tr><td><a href="#/${p.symbol}">${p.symbol}</a></td><td class="t-muted">${p.sector || ''}</td><td class="n">${num(p.weight_pct, 1)}%</td><td class="n ${isNum(p.risk_contribution_pct) && p.risk_contribution_pct - Math.abs(p.weight_pct) >= 5 ? 'down' : ''}">${isNum(p.risk_contribution_pct) ? `${num(p.risk_contribution_pct, 1)}%` : 'n/a'}</td></tr>`)}</tbody></table></div>
      <p class="asof">Each name's share of the book's exposure beside its share of the book's swings, from ${num(r.window_sessions, 0)} sessions of daily returns. ${clean(r.exposure_basis || '')}</p>
      ${(r.options || []).length ? html`<p class="asof">${clean(r.option_note || '')} Long options' premium at risk ${money(r.option_premium_at_risk, 0)}; notional ${money(r.option_notional, 0)}.</p>` : ''}</div>
      <div><h3>Most correlated pairs</h3><div class="tscroll"><table class="t"><thead><tr><th scope="col">Pair</th><th scope="col" class="n">${num(r.window_sessions, 0)}-day correlation</th></tr></thead>
        <tbody>${(r.top_pairs || []).slice(0, 6).length ? r.top_pairs.slice(0, 6).map((p) => html`<tr><td>${p.a} / ${p.b}</td><td class="n ${Math.abs(p.correlation) >= 0.7 ? 'down' : ''}">${p.correlation > 0 ? '+' : ''}${num(p.correlation, 2)}</td></tr>`) : html`<tr><td colspan="2">Not enough overlapping history.</td></tr>`}</tbody></table></div>
        <p class="asof">From −1, moving opposite, to +1, moving together. At 0.7 or more two names behave much like one.</p>
        <h3>Sector exposure</h3>${sectors.some((x) => !/^(unclassified|unknown|n\/a|)$/i.test(String(x.sector || '').trim())) ? raw(hbars(sectors.map((x) => ({ label: x.sector, v: x.weight_pct })))) : html`<p class="t-muted">The data provider gives no sector for these names.</p>`}</div></div>
    <p><b>Summed stop risk ${money(r.summed_stop_risk, 0)}.</b> ${clean(r.summed_risk_note || '')}</p><p class="asof">${clean(r.method || '')}</p></section>`;
}

function rest(d) {
  const closed = d.closed || [], s = d.summary || {}, cfg = d.config || {}, arch = d.archive || [], bk = (d.books || []).find((b) => b.id === (d.book || book)) || {};
  const kvl = (rows) => html`<dl class="reads-dl">${rows.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>`;
  return html`${closed.length ? html`<section class="section" aria-labelledby="ct-h"><h2 class="t-h2" id="ct-h">Closed trades</h2>
      <p class="section-sub">Most recent first. The exit reason is the honest part of the record. A table full of time stops means the signals were early, not unlucky.</p>
      <div class="tscroll"><table class="t"><thead><tr><th scope="col">Position</th><th scope="col">Side</th><th scope="col">Size</th><th scope="col">Entry</th><th scope="col">Exit</th><th scope="col">P&L</th><th scope="col">Why it closed</th><th scope="col">Held</th><th scope="col">Closed</th></tr></thead>
        <tbody>${closed.map((p) => html`<tr><td>${label(p)}</td><td>${side(p)}</td><td>${size(p)}</td><td>${num(p.entry_price)}</td><td>${num(p.exit_price)}</td><td>${pnlCell(p)}</td><td>${capFirst(p.exit_reason || '') || 'n/a'}</td><td>${heldDays(p.entry_at, p.exit_at) === null ? 'n/a' : `${heldDays(p.entry_at, p.exit_at)}d`}</td><td>${p.exit_at ? shortDate(p.exit_at) : 'n/a'}</td></tr>`)}</tbody></table></div></section>` : ''}
    ${arch.length ? html`<section class="section" aria-labelledby="er-h"><h2 class="t-h2" id="er-h">Earlier records</h2><p class="section-sub">Set aside when the record restarted, and kept rather than deleted. None of their positions are in the figures above.</p>
      ${arch.map((r) => html`<h3>${r.label}</h3><p class="t-muted">${r.trades ? `${r.from || ''} to ` : ''}${String(r.archived_at || '').slice(0, 10)}, ${num(r.trades, 0)} trade${r.trades === 1 ? '' : 's'}. ${clean(r.reason || '')}</p>
        ${(r.books || []).length ? html`<div class="tscroll"><table class="t narrow"><thead><tr><th scope="col">Book</th><th scope="col" class="n">Trades</th><th scope="col" class="n">Result</th></tr></thead><tbody>${r.books.map((b) => html`<tr><td>${capFirst(b.id)}</td><td class="n">${num(b.trades, 0)}</td><td class="n ${tone(b.pnl)}">${$0(b.pnl)}${isNum(b.return_pct) ? ` (${signed(b.return_pct, 2)})` : ''}</td></tr>`)}</tbody></table></div>` : ''}`)}</section>` : ''}
    <section class="section" aria-labelledby="hw-h"><h2 class="t-h2" id="hw-h">How these positions are taken</h2>
      <p class="section-sub">Fixed rules, set in advance and applied identically to every ticker. Written down here so the record can't be improved after the fact by changing its mind.</p>
      <div class="grid2"><div><h3>Position sizing</h3>${kvl([['Account', `${$0(s.start_equity)} notional`], ['Risk per share trade', `${num(cfg.risk_per_trade_pct, 1)}% of equity`], ['Max risk per option trade', `${num(cfg.max_option_risk_pct, 1)}% of equity`], ['Single-contract exception', `up to ${num(cfg.option_single_contract_cap_pct, 0)}% of equity`], ['Share position cap', `${num((bk.max_notional_pct || 0.25) * 100, 0)}% of equity in notional`], ['Open positions', `at most ${num(cfg.max_open_positions, 0)}`], ['Total risk deployed', `at most ${num(cfg.max_portfolio_risk_pct, 0)}% of equity`], ['New positions per scan', `at most ${num(cfg.max_new_per_scan, 0)}`]])}
          <p class="asof">Shares are sized so that being stopped out costs exactly the risk budget. A wide stop therefore buys fewer shares, not more risk. Options are sized on the whole premium, because a long option can genuinely go to zero and a stop cannot prevent it.</p></div>
        <div><h3>Entries and exits</h3>${kvl([['Universe', cfg.universe === 'nasdaq' ? 'every NASDAQ common stock (about 3,000)' : cfg.universe === 'curated' ? `${(cfg.universe_symbols || []).length} large names and index funds, below` : 'fixed watchlist'], ['Screened down to', `${num(cfg.shortlist_size, 0)} names per scan`], ['Takes a trade when', `composite score ≥ ${num(cfg.min_composite, 0)} (either direction), at the scan's price`], ['Does not wait for', "the Options tab's pullback or breakout triggers, their confirmations, or its event warnings"], ['Stop', 'Just beyond the nearest real support or resistance level, or twice the average daily range if none is close'], ['Target', 'twice the risk distance. Fixed, not fitted'], ['Option exits', '−50% / +100% premium, underlying stop, or expiry'], ['Time stop', `${num(cfg.max_hold_days, 0)} days`], ['Per ticker', 'one idea at a time'], ['Trades only', 'during the regular session, 9:30 to 4:00 ET']])}</div></div>
      ${cfg.universe === 'curated' && (cfg.universe_symbols || []).length ? html`<p class="asof">The list: ${cfg.universe_symbols.join(', ')}. Fixed, so the record cannot drift toward whatever happened to work.</p>` : ''}
      <div class="state" role="note"><p class="t-h3">What these numbers are not</p><ul class="plain">${(d.caveats || []).map((c) => html`<li>${clean(c)}</li>`)}</ul></div>
      ${d.disclaimer_area ? html`<p class="asof">${clean(d.disclaimer_area)}</p>` : ''}</section>
    ${(d.scans || []).length ? html`<section class="section" aria-labelledby="sh-h"><h2 class="t-h2" id="sh-h">Scan history</h2>
      <div class="tscroll"><table class="t"><thead><tr><th scope="col">Ran</th><th scope="col">Trigger</th><th scope="col">Considered</th><th scope="col">Opened</th><th scope="col">Closed</th></tr></thead>
        <tbody>${d.scans.map((x) => html`<tr><td>${stamp(x.ran_at)}</td><td>${capFirst(x.trigger || '')}</td><td>${num(x.considered, 0)}</td><td>${num(x.opened, 0)}</td><td>${num(x.closed, 0)}</td></tr>
          <tr class="sh-notes"><td colspan="5">${capFirst((x.notes || []).join('. ')) || 'Nothing cleared the bar'}${(x.funnel || {}).screen && x.funnel.screen.ranking_reused ? html`<br>Screen ranking reused from ${num(x.funnel.screen.ranking_age_minutes, 0)} minutes earlier. Daily bars don't change intraday, and re-downloading the exchange is what earns a rate limit.` : ''}</td></tr>`)}</tbody></table></div></section>` : ''}`;
}

/* ---------------- page ---------------- */
function paint() {
  if (!live) return;
  const d = D.d, y = window.scrollY;
  // a background repaint (risk, a scan poll) must not take focus away from the reader
  const a = document.activeElement, fid = a && mainEl.contains(a) ? a.id || (a.dataset && Object.keys(a.dataset).length ? a.outerHTML.match(/data-v2-[a-z-]+="[^"]*"/)?.[0] : '') : '';
  const empty = d && !(d.open || []).length && !(d.closed || []).length;
  // whose portfolio this is, before any figure (beginner brief item 9): Optic's own simulated record, the same for
  // every reader, with pretend money; the reader's own practice portfolio and real accounts are elsewhere
  draw(mainEl, html`<header class="page-head">${sectionHead('portfolio', 'tracker')}
      <div class="whose" role="note"><p><b>This is Optic's demonstration portfolio, not yours.</b> Three simulated accounts trade Optic's own signals with pretend money, the same for every reader. No money is real and no order reaches a broker.</p>
        <p>Your own practice portfolio is the <a class="textlink" href="#/paper">Paper Desk</a>.${store.signedIn() ? html` Accounts you link are under <a class="textlink" href="#/brokerage">Brokerage</a>, read only.` : ''}</p></div></header>
    ${D.err ? failed("Optic's position ledger", D.err, { retry: 'load' }) : !d ? skeleton('rows', 6, "Loading Optic's own position ledger") : html`
      ${books(d)}${ledger(d)}${openPositions(d.open || [])}${months(d)}${funnel(d)}
      ${empty ? html`<section class="section"><h2 class="t-h2">No trades yet</h2><p>The ledger is empty. It only opens a position when a name's composite score clears ${num((d.config || {}).min_composite, 0)}, and most scans find nothing. Open "Run the shared scan" above to run one, or wait for the scheduled one.</p></section>` : ''}
      ${record(d.summary || {})}${risk(d)}${rest(d)}`}`);
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
  if (fid) { const el = fid.startsWith('data-') ? mainEl.querySelector(`[${fid}]`) : mainEl.querySelector(`#${fid}`); if (el) { if (!el.hasAttribute('tabindex') && /^H\d$/.test(el.tagName)) el.setAttribute('tabindex', '-1'); el.focus({ preventScroll: true }); } }
  if (!d) return;
  const scored = (d.open || []).filter((p) => isNum(p.pnl)).sort((a, b) => b.pnl - a.pnl);
  mountCharts(mainEl, {
    open: scored.length >= 2 ? (w) => signedBars(scored.map((p) => ({ x: `${p.ticker}${p.instrument === 'option' ? ' opt' : ''}`, v: p.pnl })), { w, h: 200, label: 'Unrealised profit or loss of each open trade', fmt: (v) => money(v, 0) }) : null,
    months: (d.months || []).length > 1 ? (w) => signedBars(d.months.map((m) => ({ x: m.label, v: Number(m.realised_pnl) || 0 })), { w, h: 170, label: 'Realised profit or loss by month', fmt: (v) => money(v, 0) }) : null,
  });
}

async function load(quiet) {
  if (!quiet) { D.d = null; D.err = null; D.risk = undefined; paint(); }
  const q = new URLSearchParams({ book }); if (month) q.set('month', month);
  try {
    const d = await api.get(`/api/tracker?${q}`, { force: true, timeout: 45000 });
    if (!live) return;
    D.d = d; D.err = null; scanning = !!(d.progress || {}).running;
  } catch (e) { if (!quiet) D.err = e; }
  paint();
  clearTimeout(poll);
  if (live && D.d && (D.d.progress || {}).running) poll = setTimeout(() => load(true), 4000);
  if (D.d && (D.d.open || []).length && D.risk === undefined) loadRisk();
}
async function loadRisk() {
  try { D.risk = await api.get(`/api/portfolio-risk?book=${encodeURIComponent(book)}`, { ttl: 120000, timeout: 60000 }); }
  catch (e) { D.risk = { error: e }; }
  paint();
}
async function action(kind) {
  notice = null; if (kind === 'scan') scanning = true; paint();
  try {
    await api.post(`/api/tracker/${kind}`, {}, { timeout: kind === 'mark' ? 60000 : 20000 });
    if (kind === 'mark') toast('Marks refreshed.');
  } catch (e) {
    scanning = false;
    notice = e.status === 429 || e.status === 409 ? clean(e.message) : api.explain(e, kind === 'scan' ? 'The scan' : 'The mark');
  }
  D.risk = undefined; load(true);
}

export async function render(main) {
  live = true; mainEl = main; D = {}; notice = null;
  document.title = 'Optic Portfolio, Optic';
  provideContext(() => ({ view: 'tracker', tracker: D.d ? { book, summary: D.d.summary, open: (D.d.open || []).slice(0, 20).map((p) => ({ ticker: p.ticker, instrument: p.instrument, direction: p.direction, pnl: p.pnl, stop: p.stop, target: p.target })), caveats: D.d.caveats } : null }));
  main.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-book]'))) { if (b.dataset.v2Book === book) return; book = b.dataset.v2Book; month = null; load().then(() => { const h = mainEl.querySelector('#op-h'); if (h) { h.setAttribute('tabindex', '-1'); h.focus(); } }); return; }
    if ((b = t('[data-v2-tk]'))) action(b.dataset.v2Tk);
  });
  main.addEventListener('change', (e) => { if (e.target.matches('[data-v2-tk-month]')) { month = e.target.value; load(true); } });
  load();
}
export function dispose() { live = false; clearTimeout(poll); }
export const retry = { load: () => load(), risk: () => { D.risk = undefined; loadRisk(); } };
