// One way to say when a price is from (owner, 2026-10-19: AAPL's header showed an overnight print while
// Earnings showed a different after-hours one, and nothing said which was which or when each was struck).
// A price names its session and the New York time it was struck; when Optic fetched it is a separate fact.
const ET = 'America/New_York';
const fmt = (o) => { try { return new Intl.DateTimeFormat('en-US', Object.assign({ timeZone: ET }, o)); } catch (e) { return null; } };
const DAY = fmt({ year: 'numeric', month: '2-digit', day: '2-digit' });
const WD = fmt({ weekday: 'short' });
const MD = fmt({ month: 'short', day: 'numeric' });
const HM = fmt({ hour: 'numeric', minute: '2-digit' });

export const SESSION_WORD = { regular: 'Regular session', pre: 'Pre-market', 'pre-market': 'Pre-market', premarket: 'Pre-market', after: 'After hours', 'after hours': 'After hours', 'after-hours': 'After hours', post: 'After hours', overnight: 'Overnight', closed: 'Closed' };
export const sessionWord = (k) => SESSION_WORD[String(k || '').toLowerCase()] || (k ? String(k).charAt(0).toUpperCase() + String(k).slice(1) : '');

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
