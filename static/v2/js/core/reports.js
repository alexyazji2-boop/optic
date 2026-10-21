// How every page words a company's next report (owner, 2026-10-21: "trace that provenance and correct
// unsupported certainty"). The session of a report that has not happened is never stated: the time Yahoo lists
// on an upcoming row is a placeholder (it put Apple's and NVIDIA's next reports "before the open"; both report
// after the close). What is known is the company's habit from the reports it has made (`usual_timing`), said as
// a habit, and whether Yahoo Finance marks the date as confirmed (`confirmed_basis` 'yahoo_flag'); a date
// confirmed only by the feed listing one date rather than a window is called listed, not confirmed.
export const SESSION_WORD = { before_open: 'before the open', after_close: 'after the close' };

/** "date confirmed by Yahoo Finance", "date listed by Yahoo Finance", "date not confirmed". */
export function dateStatus(nr) {
  if (!nr || !nr.date) return '';
  if (!nr.confirmed) return 'date not confirmed';
  return nr.confirmed_basis === 'yahoo_flag' ? 'date confirmed by Yahoo Finance' : 'date listed by Yahoo Finance';
}

/** "Its last 4 reports came after the close." or '' when the company is not consistent or the record is short. */
export function habitLine(nr, who = 'Its') {
  const u = nr && nr.usual_timing;
  return u && SESSION_WORD[u.timing] && u.count >= 3 ? `${who} last ${u.count} reports came ${SESSION_WORD[u.timing]}.` : '';
}
