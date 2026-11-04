// Fiscal periods as the company's own filings name and date them (Handoff 2: fiscal-period labels).
//
// The server describes each period (app/figures/periods.py describe()): its type and badge, its exact start and end,
// the company's own short name for it ("FY25", "Q3 FY26"; "2025" and "Q3 2025" for a calendar year), a plain label
// ("Fiscal year ended Sep 27, 2025") and the filing that reported it. A period no filing reports is dated only
// ("Year to Mar 31, 2026, as Yahoo Finance dates it"), and one with no date says "Period labels unavailable".
// Nothing here works a fiscal-year name out of a date: that guess named Home Depot's fiscal 2025 "FY26".
import { fullDate } from './format.js';

export const UNAVAILABLE = 'Period labels unavailable';
export const BADGE = { annual: 'Annual', quarter: 'Quarter', ttm: 'TTM', balance: 'Balance sheet', transition: 'Transition period' };
// What each badge means, for its title and the "How these periods are named" fold.
export const BADGE_MEANS = {
  annual: 'One fiscal year: the company\'s own reporting year, which need not end in December',
  quarter: 'One fiscal quarter of the company\'s year',
  ttm: 'Trailing twelve months: the last four reported quarters added together',
  balance: 'Measured on one balance-sheet date, not over a period',
  transition: 'The months between two fiscal year ends, when the company moved its year end',
};
export const BASIS_MEANS = {
  GAAP: 'US generally accepted accounting principles, the rules the company files its statements under',
  IFRS: 'International Financial Reporting Standards, the rules the company files its statements under',
  'Non-GAAP': 'Not defined by accounting rules: worked out from the filed lines, or adjusted by the company or the provider',
  "Analysts' basis": "The basis analysts' estimates use, usually the company's adjusted (non-GAAP) figure",
  'Basis not stated': 'The source does not say which accounting rules its figures follow',
};
const isoDay = (s) => /^\d{4}-\d{2}-\d{2}/.test(String(s || ''));
const day = (s) => String(s).slice(0, 10);
const lower = (s) => (s ? s[0].toLowerCase() + s.slice(1) : s);

/** A period known only by its source's date: no name, and said to be that source's dating. */
export function bare(end, type = 'annual') {
  if (!isoDay(end)) return { type, badge: BADGE[type], available: false, label: UNAVAILABLE, short: null, end: null };
  return { type, badge: BADGE[type], available: true, end: day(end), short: null, filing: null, dated_by: 'provider',
    label: `${type === 'quarter' ? 'Quarter' : 'Year'} to ${fullDate(day(end))}` };
}

/** The statements' column periods from the snapshot (/api/ticker figures.periods.statements), aligned with the
 * provider's columns; a column the server did not describe is dated by the provider alone. */
export function statementPeriods(t, which = 'annual') {
  const f = ((t || {}).company || {}).financials || {};
  const q = which === 'quarterly' || which === 'quarter';
  const per = q ? f.quarterly_periods || [] : f.annual_periods || [];
  const got = ((((t || {}).figures || {}).periods || {}).statements || {})[q ? 'quarterly' : 'annual'] || [];
  // matched by date, not position: a description is used only for the column it describes (within ten days, the
  // provider's month end against the filing's own day)
  const near = (a, b) => isoDay(a) && isoDay(b) && Math.abs(Date.parse(day(a)) - Date.parse(day(b))) <= 10 * 864e5;
  return per.map((p) => got.find((d) => d && d.label && (near(d.provider_end, p) || near(d.end, p))) || bare(p, q ? 'quarter' : 'annual'));
}
/** The company's calendar from the snapshot: how its year is set, and any change of year end. */
export const calendarOf = (t) => (((t || {}).figures || {}).periods || {}).calendar || null;
/** The accounting basis the statements are filed under, when the filings say ("GAAP", "IFRS"). */
export const basisOf = (t) => ((((t || {}).figures || {}).periods || {}).statements || {}).basis || null;

/** The short name for a column or a tick: the company's own ("FY25"), else the period's end date. */
export const short = (d) => (!d || !d.available ? UNAVAILABLE : d.short || fullDate(d.end));
/** The end date: "Sep 27, 2025"; "about Sep 26, 2026" for a period not yet filed in a 52- or 53-week year, whose end
 * the filings have not given yet (the server's _next()). */
export const endText = (d) => (d && d.end ? `${d.projected && /\babout\b/.test(d.label || '') ? 'about ' : ''}${fullDate(d.end)}` : '');
/** A column's or tick's whole label, for a tip or a screen reader: "FY25, fiscal year ended Sep 27, 2025". */
export const label = (d) => (!d || !d.available ? UNAVAILABLE : d.short ? `${d.short}, ${lower(d.label)}` : d.label);
/** A period inside a sentence, with its date: "FY25 (to Sep 27, 2025)", "the year to Sep 30, 2025". */
export const inText = (d) => (!d || !d.available ? 'a period Optic could not date' : d.short ? `${d.short} (to ${endText(d)}${d.projected ? ', not yet filed' : ''})` : `the ${lower(d.label).replace(/, as .* dates it$/, '')}`);
/** A balance-sheet date inside a sentence: "FY25 (Sep 27, 2025)". */
export const atText = (d) => (!d || !d.available ? 'a date Optic could not establish' : d.short ? `${d.short} (${endText(d)})` : endText(d));
/** A period in words for a sentence that names it once: "the fiscal year ended Sep 27, 2025 (FY25)". */
export const inWords = (d) => (!d || !d.available ? 'a period Optic could not date' : `the ${lower(d.label).replace(/, as .* dates it$/, '')}${d.short ? ` (${d.short})` : ''}`);
/** A chart's group for one period: the name, its end date under it, and its whole label in the tip. */
export const tick = (d) => (d && d.short ? { x: d.short, sub: endText(d), title: label(d) } : { x: d && d.available ? endText(d) : UNAVAILABLE, title: label(d) });

/** A run of periods for a block's label: "Fiscal years ended Sep 24, 2022 to Sep 27, 2025 (FY22 to FY25)". */
export function range(ds) {
  const xs = (ds || []).filter(Boolean);
  if (!xs.length || xs.some((d) => !d.available)) return UNAVAILABLE;
  const s = xs.slice().sort((a, b) => (a.end < b.end ? -1 : 1)), a = s[0], b = s[s.length - 1];
  if (s.length === 1) return label(a);
  // named when every period's name is the company's own: from its filing, or its place in its calendar (not yet filed)
  const q = a.type === 'quarter', named = s.every((d) => d.short && d.dated_by !== 'provider' && d.dated_by !== 'source');
  if (named) return `${q ? 'Quarters' : 'Fiscal years'} ended ${endText(a)} to ${endText(b)} (${a.short} to ${b.short})`;
  const prov = s.some((d) => d.dated_by === 'provider');
  return `${q ? 'Quarters' : 'Years'} ending ${endText(a)} to ${endText(b)}${prov ? ', as the provider dates them' : ''}`;
}

/** What a block covering these periods must also say: a 53-week year or 14-week quarter, and a change of year end. */
export function notes(ds, cal = null) {
  const xs = (ds || []).filter((d) => d && d.available);
  const out = xs.filter((d) => d.weeks === 53 || d.weeks === 14).map((d) => `${d.short ? `${d.short} (to ${endText(d)})` : `The ${d.type === 'quarter' ? 'quarter' : 'year'} to ${endText(d)}`} had ${d.weeks} weeks, one more than the ${d.type === 'quarter' ? 'quarters' : 'years'} beside it, which flatters its comparison.`);
  xs.filter((d) => d.type === 'transition').forEach((d) => out.push(`${d.label}: ${lower(d.note || 'not a full fiscal year')}`));
  xs.filter((d) => d.projected).forEach((d) => out.push(`${d.short} (to ${endText(d)}) is not filed yet. ${d.note || ''}`.trim()));
  const ends = xs.map((d) => d.end).sort();
  if (ends.length && cal && cal.available) {
    (cal.changes || []).forEach((c) => {
      const lo = ends[0], hi = ends[ends.length - 1];
      const inside = (c.before && c.before >= lo && c.before < hi) || (c.after && c.after > lo && c.after <= hi);
      if (inside && c.note) out.push(c.note);
    });
  }
  if (xs.some((d) => d.dated_by === 'provider') && !(cal && cal.available)) out.push('Fiscal-year names come from the company\'s SEC filings, which Optic could not read for this company, so each period is named by the date the provider gives it.');
  return [...new Set(out)];
}

/** The filing that reported the newest of these periods, when one did. */
export function latestFiling(ds) {
  const xs = (ds || []).filter((d) => d && d.available && d.filing && d.filing.url).sort((a, b) => (a.end < b.end ? 1 : -1));
  return xs.length ? xs[0].filing : null;
}

/** A segment table's period, from the segments payload's own calendar (/api/segments periods), else its date alone. */
export const segmentPeriod = (sg, end, years) => ((((sg || {}).periods || {})[years ? 'year' : 'quarter'] || {})[end]) || bare(end, years ? 'annual' : 'quarter');
/** The consolidated total a segment table's period should add up to, from the same filings (/api/segments reported). */
export function segmentTotal(t, i, years) {
  const r = (((t || {}).reported || {})[years ? 'year' : 'quarter'] || [])[i];
  return r && typeof r.value === 'number' && Number.isFinite(r.value) ? r : null;
}
/** What a reconciliation line says it was checked against, or why it was not. */
export const reconOf = (t, r) => (r ? { form: r.form, derived: r.derived } : { why: (t && t.reported_why) || "Not reconciled: the filings carry no consolidated figure for this period, so the parts are not checked against the company's total." });
/** Every breakdown in a segments payload: the quarterly tables, then those filed only in the 10-K. */
export const segmentTables = (sg) => [...((sg || {}).tables || []), ...((sg || {}).annual_only_tables || [])];
