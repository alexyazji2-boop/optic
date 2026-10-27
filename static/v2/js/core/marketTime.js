// One way to say when a price is from (owner, 2026-10-19: AAPL's header showed an overnight print while
// Earnings showed a different after-hours one, and nothing said which was which or when each was struck).
// A price names its session and the New York time it was struck; when Optic fetched it is a separate fact.
import { num, isNum, capFirst } from './format.js';

const ET = 'America/New_York';
const fmt = (o) => { try { return new Intl.DateTimeFormat('en-US', Object.assign({ timeZone: ET }, o)); } catch (e) { return null; } };
const DAY = fmt({ year: 'numeric', month: '2-digit', day: '2-digit' });
const WD = fmt({ weekday: 'short' });
const MD = fmt({ month: 'short', day: 'numeric' });
const HM = fmt({ hour: 'numeric', minute: '2-digit' });

export const SESSION_WORD = { regular: 'Regular session', pre: 'Pre-market', 'pre-market': 'Pre-market', premarket: 'Pre-market', after: 'After hours', 'after hours': 'After hours', 'after-hours': 'After hours', post: 'After hours', overnight: 'Overnight', closed: 'Closed' };
export const sessionWord = (k) => SESSION_WORD[String(k || '').toLowerCase()] || (k ? String(k).charAt(0).toUpperCase() + String(k).slice(1) : '');

const ISO_DAY = (() => { try { return new Intl.DateTimeFormat('en-CA', { timeZone: ET, year: 'numeric', month: '2-digit', day: '2-digit' }); } catch (e) { return null; } })();
/** New York's calendar date ("2026-10-26"), the one every market countdown counts from: a viewer in another timezone,
 * or a browser past midnight UTC, is still on New York's trading day (Brokerage called Tuesday "today" at 10 PM ET on
 * Monday 2026-10-26, while the header said Monday). */
export const marketDate = (t = Date.now()) => (ISO_DAY ? ISO_DAY.format(new Date(t)) : new Date(t).toISOString().slice(0, 10));
/** Whole days from New York's today to a calendar date ("2026-11-17"); null when it is not one. */
export function daysUntil(iso, t = Date.now()) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || '')), n = /^(\d{4})-(\d{2})-(\d{2})/.exec(marketDate(t));
  if (!m || !n) return null;
  return Math.round((Date.UTC(+m[1], +m[2] - 1, +m[3]) - Date.UTC(+n[1], +n[2] - 1, +n[3])) / 86400000);
}
/** "12:28 AM ET" today in New York, "Fri 7:59 PM ET" on another day. */
export function etStamp(iso) {
  if (!iso || !HM) return '';
  const t = new Date(iso); if (Number.isNaN(t.getTime())) return '';
  const today = DAY.format(new Date()) === DAY.format(t);
  return `${today ? '' : `${WD.format(t)} `}${HM.format(t)} ET`;
}
/** "Fri Oct 16" for a date or a moment. A bare date is read as that calendar day, not UTC midnight. */
export function etDay(iso) {
  if (!iso) return '';
  const t = /^\d{4}-\d{2}-\d{2}$/.test(String(iso)) ? new Date(`${iso}T12:00:00Z`) : new Date(iso);
  if (Number.isNaN(t.getTime()) || !MD) return '';
  return `${WD.format(t)} ${MD.format(t)}`;
}
/** An extended-hours print: "Overnight 344.96, at 12:28 AM ET". */
export const printWhen = (kind, at) => `${sessionWord(kind)}${at ? `, struck ${etStamp(at)}` : ''}`;

/** The trade's own moment: `trade_time` (an ISO instant, from 2026-10-21), else the older `market_time`. */
export const tradeTime = (q) => (q && (q.trade_time || q.market_time)) || null;
/**
 * How fresh a session price is, in words, from the feed and nothing else (owner's safeguard, 2026-10-21): "Live" only
 * when the feed states no delay for the exchange and the trade is under two minutes old; a delay the feed states, by
 * its number; without one, the site's standing "about 15 minutes". Refreshing often never earns "Live".
 */
export function sessionFreshness(q, now = Date.now()) {
  const t = tradeTime(q), at = t ? Date.parse(t) : NaN, delay = q && isNum(q.delayed_minutes) ? Number(q.delayed_minutes) : null;
  const last = t ? `last trade ${etStamp(t)}` : '';
  if (delay === 0 && Number.isFinite(at) && now - at >= -60000 && now - at <= 120000) return { word: 'live', text: `Live, ${last}` };
  if (delay === 0) return { word: 'quiet', text: last ? capFirst(last) : 'No delay stated by the feed' };
  const lead = delay !== null ? `Delayed ${num(delay, 0)} minutes` : 'Delayed about 15 minutes';
  return { word: 'delayed', text: last ? `${lead}, ${last}` : lead };
}
