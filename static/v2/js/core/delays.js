// How delayed each price is, said one way on every page (Handoff 4 of the owner's handover pack, 2026-11-03). The audit
// found 15 minutes on the Dossier and in Milo and 20 on Brokerage: each surface wrote its own sentence. Each quote
// states its exchange's delay and its trade's own time, so its label is computed from those, in the reader's
// timezone; the numbers about the feed as a whole come from the server's one record of them (app/delays.py, served
// at /api/delays). A label redraws itself in place when the timezone, the clock or that record changes (relabel).
import * as api from './api.js';
import * as prefs from './prefs.js';
import { html } from './dom.js';
import { isNum, num, capFirst } from './format.js';

// When /api/delays cannot be read: the longest delay any exchange in the feed states, and a note that the delay
// information is missing. Never "Live". The numbers equal app/delays.py's (tests/test_honest_loading.py holds them so).
export const FALLBACK = Object.freeze({ longest_minutes: 20, usual_minutes: 15, stale_after_minutes: 30, chain_minutes: 15, exchanges: {}, unavailable: true });
// Until the record answers: the same numbers, without the note (nothing has failed yet)
const PENDING = Object.freeze(Object.assign({}, FALLBACK, { unavailable: false }));
const MIN = 60000;
let CONF = null, asking = null, failedAt = 0;

/** The delay record in force: the server's, the fallback after a failure, or the fallback's numbers until it answers. */
export const config = () => CONF || PENDING;

/** Ask for the record; once it answers it is kept. A failure keeps the fallback, with its note, and is asked again
 * at the next page shown a minute or more later (app.js show), so an outage costs one request a minute at most. */
export function load() {
  if (CONF && !CONF.unavailable) return Promise.resolve(CONF);
  if (asking) return asking;
  if (failedAt && Date.now() - failedAt < MIN) return Promise.resolve(config());
  asking = api.get('/api/delays', { ttl: 6 * 3600000, timeout: 8000 })
    .then((d) => { if (!d || !isNum(d.longest_minutes)) throw new Error('no record'); CONF = d; failedAt = 0; })
    .catch(() => { CONF = FALLBACK; failedAt = Date.now(); })
    .then(() => { asking = null; relabel(); return CONF; });
  return asking;
}

/* ---------------- the words ---------------- */
const PHASES = { REGULAR: 'regular', PRE: 'pre', PREPRE: 'pre', POST: 'after', POSTPOST: 'after', CLOSED: 'closed' };
const SESSION = { pre: 'Pre-market', after: 'After hours', post: 'After hours', overnight: 'Overnight' };
/** The trade's own moment in milliseconds (`trade_time`, else an ISO `market_time`), or null. */
export const tradeAt = (q) => { const t = q && (q.trade_time || q.market_time); const ms = t ? Date.parse(t) : NaN; return Number.isFinite(ms) ? ms : null; };

/** "1:34 PM EST" today in the reader's zone, "Nov 3, 3:59 PM EST" on another day. The abbreviation is the zone's own
 * at that moment (Intl), so a time either side of a clock change says EDT or EST as it was; no offset is worked here. */
export function clockText(at, { now = Date.now(), zone = prefs.zone() } = {}) {
  const t = new Date(at); if (!Number.isFinite(t.getTime())) return '';
  try {
    const day = (d) => d.toLocaleDateString('en-US', { timeZone: zone, year: 'numeric', month: 'short', day: 'numeric' });
    const date = day(new Date(now)) === day(t) ? '' : `${t.toLocaleDateString('en-US', { timeZone: zone, month: 'short', day: 'numeric' })}, `;
    return `${date}${t.toLocaleTimeString('en-US', { timeZone: zone, hour: 'numeric', minute: '2-digit' })} ${prefs.zoneAbbrev(zone, t)}`;
  } catch (e) { return t.toISOString(); }
}
/** A session's date ("2026-11-03") as "Tue Nov 3": a calendar day, so no timezone moves it. */
export function closeDay(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || '')); if (!m) return '';
  try { return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], 12)).toLocaleDateString('en-US', { timeZone: 'UTC', weekday: 'short', month: 'short', day: 'numeric' }).replace(',', ''); } catch (e) { return m[0]; }
}

/**
 * One price's label, from its own stated delay and trade time:
 * - in the regular session, "Delayed 15 min · as of 1:34 PM EST" (a delay other than the usual one names its
 *   exchange: "Delayed 20 min (NYSE)"); "Delayed up to 20 min" when the quote states none; "Live" only when it states no
 *   delay and the trade is under two minutes old (the owner's safeguard, 2026-10-21), else "As of 1:34 PM EST";
 * - "Stale · as of ..." when the trade is older than its delay plus the tolerance, so an old price is never shown as
 *   current;
 * - outside the session, "Market closed · last close Tue Nov 3", or the extended session by name, with "regular session
 *   only" when the data holds no print of its own for it.
 * Without the delay record, "Delayed up to 20 min · ... · delay info unavailable", never "Live".
 * q: { delayed_minutes, trade_time | market_time, exchange, market_state, session ('pre' or 'post' for a print of that session) }
 * ctx: { phase ('regular', 'pre', 'after', 'overnight', 'closed', 'holiday'), lastClose ('2026-11-03'), extended, now, zone }
 * Returns { state ('live', 'delayed', 'asof', 'stale', 'closed', 'extended'), text, delay (stated minutes or null) }.
 */
export function quoteLabel(q, ctx = {}) {
  const c = config(), now = isNum(ctx.now) ? Number(ctx.now) : Date.now(), zone = ctx.zone || prefs.zone();
  q = q || {};
  const phase = ctx.phase || PHASES[String(q.market_state || '').toUpperCase()] || null;
  // a price that is itself an extended-hours print (Brokerage reprices with the latest one) is that session's, at its time
  if (SESSION[q.session]) {
    const at = tradeAt(q);
    return { state: 'extended', text: `${SESSION[q.session]} print · ${at !== null ? `as of ${clockText(at, { now, zone })}` : 'time not reported'}`, delay: null };
  }
  if (phase && phase !== 'regular') {
    const day = closeDay(ctx.lastClose), close = day ? `last close ${day}` : 'last close';
    if (!SESSION[phase]) return { state: 'closed', text: `Market closed · ${close}`, delay: null };
    return { state: 'extended', text: `${SESSION[phase]} · ${ctx.extended ? '' : 'regular session only · '}${close}`, delay: null };
  }
  const at = tradeAt(q), when = at !== null ? `as of ${clockText(at, { now, zone })}` : 'trade time not reported';
  const stated = !c.unavailable && isNum(q.delayed_minutes) ? Number(q.delayed_minutes) : null;
  const note = c.unavailable ? ' · delay info unavailable' : '';
  if (phase === 'regular' && at !== null && now - at > ((stated === null ? c.longest_minutes : stated) + c.stale_after_minutes) * MIN) {
    return { state: 'stale', text: `Stale · ${when}${note}`, delay: stated };
  }
  if (stated === 0) {
    if (at !== null && now - at >= -MIN && now - at <= 2 * MIN) return { state: 'live', text: `Live · ${when}`, delay: 0 };
    return { state: 'asof', text: capFirst(when), delay: 0 };
  }
  const where = stated !== null && stated !== c.usual_minutes && (c.exchanges || {})[q.exchange] ? ` (${c.exchanges[q.exchange]})` : '';
  const lead = stated === null ? `Delayed up to ${num(c.longest_minutes, 0)} min` : `Delayed ${num(stated, 0)} min${where}`;
  return { state: 'delayed', text: `${lead} · ${when}${note}`, delay: stated };
}

/**
 * Several prices under one label (a panel's footer, a table's caption): the range of their stated delays and the time
 * of the oldest current trade, so no price shown is older than the label says; stale ones are counted apart.
 * "Delayed 0 to 20 min by exchange · as of 1:31 PM EST", "Live · as of 1:46 PM EST", "Market closed · last close Tue Nov 3".
 */
export function listLabel(quotes, ctx = {}) {
  const c = config(), now = isNum(ctx.now) ? Number(ctx.now) : Date.now(), zone = ctx.zone || prefs.zone();
  const all = (quotes || []).filter((q) => q && typeof q === 'object');
  if (!all.length) return null;
  const ls = all.map((q) => ({ q, l: quoteLabel(q, Object.assign({}, ctx, { now, zone })) }));
  const out = ls.find((x) => x.l.state === 'closed' || x.l.state === 'extended');
  if (out && (ctx.phase || ls.every((x) => x.l.state === out.l.state))) return out.l;
  const stale = ls.filter((x) => x.l.state === 'stale'), cur = ls.filter((x) => x.l.state !== 'stale' && x.l.state !== 'closed' && x.l.state !== 'extended');
  const oldest = (xs) => { const ts = xs.map((x) => tradeAt(x.q)).filter((t) => t !== null); return ts.length ? Math.min(...ts) : null; };
  const note = c.unavailable ? ' · delay info unavailable' : '';
  if (!cur.length) { const t = oldest(stale); return { state: 'stale', text: `Stale · ${t !== null ? `as of ${clockText(t, { now, zone })}` : 'trade times not reported'}${note}`, delay: null }; }
  const t = oldest(cur), when = t !== null ? `as of ${clockText(t, { now, zone })}` : 'trade times not reported';
  const known = cur.map((x) => x.l.delay).filter((d) => d !== null), unknown = cur.length - known.length;
  const lo = known.length ? Math.min(...known) : null, hi = unknown ? c.longest_minutes : (known.length ? Math.max(...known) : null);
  // one price, or several from one exchange, reads exactly as each one's own label does
  if (cur.length === 1 && !stale.length) return cur[0].l;
  const tail = `${stale.length ? ` · ${stale.length} stale` : ''}${note}`;
  const names = [...new Set(cur.map((x) => (c.exchanges || {})[x.q.exchange] || ''))];
  let state = 'delayed', lead;
  if (c.unavailable || !known.length) lead = `Delayed up to ${num(c.longest_minutes, 0)} min`;
  else if (lo === hi && hi === 0) { const live = cur.every((x) => x.l.state === 'live'); state = live ? 'live' : 'asof'; lead = live ? 'Live' : ''; }
  else if (lo === hi) lead = `Delayed ${num(hi, 0)} min${hi !== c.usual_minutes && names.length === 1 && names[0] ? ` (${names[0]})` : ''}`;
  else lead = `Delayed ${num(lo, 0)} to ${num(hi, 0)} min by exchange`;
  return { state, text: lead ? `${lead} · ${when}${tail}` : `${capFirst(when)}${tail}`, delay: [lo, hi] };
}

/** The quotes a payload's delay range stands for, when it carries the range and not the quotes (Brokerage's freshness:
 *  `delay_range`, `delay_unstated`, `quotes_oldest`): the two ends at the oldest quote's time, and one stating no delay. */
export function rangeQuotes(m) {
  m = m || {};
  const r = Array.isArray(m.delay_range) ? m.delay_range : null, at = m.quotes_oldest || null;
  const out = r ? [{ delayed_minutes: r[0], trade_time: at }, { delayed_minutes: r[1], trade_time: at }] : [];
  if (m.delay_unstated || !out.length) out.push({ trade_time: at });
  return out;
}
/** A short label for prices a panel holds without their own delays or times (daily bars, a chain): the session by name
 *  outside it; in it, the longest delay the feed states, or the chain's. */
export function generalLabel(ctx = {}, { chain = false } = {}) {
  const c = config(), phase = ctx.phase || null;
  if (phase && phase !== 'regular') return quoteLabel({}, ctx);
  const note = c.unavailable ? ' · delay info unavailable' : '';
  if (chain) return { state: 'delayed', text: `Chain ${chainWords().replace(/ minutes$/, ' min')}${note}`, delay: null };
  return { state: 'delayed', text: `Delayed up to ${num(c.longest_minutes, 0)} min${note}`, delay: null };
}

/** The sentence about quotes in general (the footer's status line, Settings, Milo's panel, the alerts page). */
export function quotesSentence() {
  const c = config();
  if (c.unavailable) return `Quotes are delayed up to ${num(c.longest_minutes, 0)} minutes during the session, by exchange (delay info unavailable).`;
  return c.footer || `Quotes are delayed up to ${num(c.longest_minutes, 0)} minutes during the session, by exchange; each price states its own delay and the time of its trade.`;
}
/** "up to 20 minutes", for a clause about quotes in general. */
export const upTo = () => `up to ${num(config().longest_minutes, 0)} minutes`;
/** Option chains, their own feed: "delayed about 15 minutes", or real-time from a configured provider. */
export function chainWords(realtime = false) {
  const o = (config().sources || {}).options;
  if (realtime || (o && o.minutes === 0)) return `real-time${o && o.provider ? ` from ${o.provider}` : ''}`;
  return `delayed about ${num(o && isNum(o.minutes) ? o.minutes : config().chain_minutes, 0)} minutes`;
}

/* ---------------- labels that keep themselves current ---------------- */
const KEEP = ['delayed_minutes', 'trade_time', 'market_time', 'exchange', 'market_state', 'session'];
const slim = (q) => { const o = {}; KEEP.forEach((k) => { if (q && q[k] !== null && q[k] !== undefined) o[k] = q[k]; }); return o; };
const ctxOf = (ctx) => ({ phase: (ctx && ctx.phase) || null, lastClose: (ctx && ctx.lastClose) || null, extended: !!(ctx && ctx.extended) });

/** A price's label as an element that relabel() redraws in place. */
export function label(q, ctx = {}, cls = '') {
  const l = quoteLabel(q, ctx);
  return html`<span class="qlabel is-${l.state}${cls ? ` ${cls}` : ''}" data-qlabel="${JSON.stringify({ q: slim(q), c: ctxOf(ctx) })}">${l.text}</span>`;
}
/** Several prices' label, the same way; '' when there are none. */
export function listTag(quotes, ctx = {}, cls = '') {
  const l = listLabel(quotes, ctx); if (!l) return '';
  return html`<span class="qlabel is-${l.state}${cls ? ` ${cls}` : ''}" data-qlist="${JSON.stringify({ q: (quotes || []).filter(Boolean).map(slim), c: ctxOf(ctx) })}">${l.text}</span>`;
}
/** A moment ("as of 7:59 AM EST", an extended-hours print's) that relabel() keeps in the reader's zone. */
export function atTag(iso, prefix = 'as of ') {
  const t = Date.parse(iso || ''); if (!Number.isFinite(t)) return '';
  return html`<span class="qat" data-qat="${new Date(t).toISOString()}" data-qat-prefix="${prefix}">${prefix}${clockText(t)}</span>`;
}

/** Redraw every label on the page from its own data: a timezone chosen in Settings, a device that moved zones, a
 *  minute passing (Live ages into "As of", an old price into Stale) or the delay record arriving. */
export function relabel(root) {
  root = root || (typeof document !== 'undefined' ? document : null);
  if (!root || !root.querySelectorAll) return;
  const put = (el, l) => { if (!l) return; if (el.textContent !== l.text) el.textContent = l.text; el.className = el.className.replace(/\bis-[a-z]+\b/, `is-${l.state}`); };
  root.querySelectorAll('[data-qlabel]').forEach((el) => { try { const d = JSON.parse(el.dataset.qlabel); put(el, quoteLabel(d.q, d.c)); } catch (e) { /* a label that will not read keeps its words */ } });
  root.querySelectorAll('[data-qlist]').forEach((el) => { try { const d = JSON.parse(el.dataset.qlist); put(el, listLabel(d.q, d.c)); } catch (e) { /* as above */ } });
  root.querySelectorAll('[data-qat]').forEach((el) => { const t = Date.parse(el.dataset.qat), x = `${el.dataset.qatPrefix || ''}${clockText(t)}`; if (Number.isFinite(t) && el.textContent !== x) el.textContent = x; });
}

let watching = false;
/** Keep the labels current for the life of the page (app.js boot). Each redraw reads the zone afresh, so a device that
 *  changed zones on "My device's time zone" relabels at the next tick or when the tab is shown again. */
export function watch() {
  if (watching || typeof document === 'undefined') return;
  watching = true;
  prefs.onChange((what) => { if (what === 'timezone') relabel(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) relabel(); });
  setInterval(() => { if (!document.hidden) relabel(); }, 30000);
}
