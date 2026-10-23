// The figures behind Optic's financial charts and the sentences under them (owner's brief, 2026-10-20: "Pair each
// visualization with a short, factual takeaway supported by its displayed data"). Every change, sum and difference
// a takeaway states is computed here from the same figures its chart draws, so a sentence can never say what its
// chart does not show. Pure: no DOM, no fetching, so each rule is tested on its own.
import { num, compact } from './format.js';

export const isFig = (v) => typeof v === 'number' && Number.isFinite(v);
const MINUS = '−';
/** A dollar figure, compact: $416.2B, −$12.7B. */
export const usd = (v) => (isFig(v) ? `${v < 0 ? MINUS : ''}$${compact(Math.abs(v))}` : 'n/a');
/** A figure in the currency the statements are kept in: dollars as $, any other by its code (TSM files in New
 * Taiwan dollars: "TWD 3.81T", never "$3.81T"). */
export const moneyIn = (ccy) => (!ccy || ccy === 'USD' ? usd : (v) => (isFig(v) ? `${v < 0 ? MINUS : ''}${ccy} ${compact(Math.abs(v))}` : 'n/a'));
export const pctText = (v, dp = 1) => (isFig(v) ? `${num(v, dp)}%` : 'n/a');

/** A percentage change, or null where one would mislead: a missing figure, or a base at or below zero (a loss
 * that turns into a profit is not "+300%"). */
export function pctChange(cur, prev) {
  if (!isFig(cur) || !isFig(prev) || prev <= 0) return null;
  return ((cur - prev) / prev) * 100;
}
/** The change in a percentage, in percentage points (a margin from 31.5% to 32.0% is up 0.5 points, not 1.6%). */
export const ppChange = (cur, prev) => (isFig(cur) && isFig(prev) ? cur - prev : null);
/** a over b, as a percentage; null without both or with b at zero */
export const share = (a, b) => (isFig(a) && isFig(b) && b !== 0 ? (a / b) * 100 : null);
export const marginSeries = (numer, denom) => (denom || []).map((d, i) => share((numer || [])[i], d));

const moved = (ch, up = 'rose', down = 'fell') => (ch >= 0 ? up : down);
const flat = (ch, dp = 1) => Math.abs(Number(ch.toFixed(dp))) === 0;

/** "Revenue rose 6.4% to $416.2B in FY25, from $391.0B in FY24." values newest first; `back` is the comparison
 * (1: the period before; 4 in quarters: the same quarter a year before), `against` names it. */
export function growthLine(name, vals, labels, back = 1, against = '', usd = moneyIn('USD')) {
  const cur = (vals || [])[0], prev = (vals || [])[back];
  if (!isFig(cur)) return '';
  const ch = pctChange(cur, prev), then = `${labels[back] || ''}${against ? `, ${against}` : ''}`;
  if (ch === null) return isFig(prev) ? `${name} was ${usd(cur)} in ${labels[0]}, against ${usd(prev)} in ${then}.` : `${name} was ${usd(cur)} in ${labels[0]}.`;
  if (flat(ch)) return `${name} was ${usd(cur)} in ${labels[0]}, unchanged from ${then}.`;
  return `${name} ${moved(ch)} ${num(Math.abs(ch), 1)}% to ${usd(cur)} in ${labels[0]}, from ${usd(prev)} in ${then}.`;
}

/** Revenue and net income in one sentence, against the same comparison period. */
export function profitLine(rev, ni, labels, back = 1, against = '', usd = moneyIn('USD')) {
  const r = growthLine('Revenue', rev, labels, back, against, usd);
  if (!r) return '';
  const n0 = (ni || [])[0], ch = pctChange(n0, (ni || [])[back]);
  if (!isFig(n0)) return r;
  if (n0 < 0) return `${r} The company lost ${usd(Math.abs(n0))} in the period.`;
  return `${r} Net income ${ch === null ? `was ${usd(n0)}` : flat(ch) ? `was ${usd(n0)}, unchanged` : `${moved(ch)} ${num(Math.abs(ch), 1)}% to ${usd(n0)}`}.`;
}

/** "Operating margin was 32.0% in FY25, up 0.5 percentage points from 31.5% in FY24." */
export function marginLine(name, vals, labels, back = 1) {
  const cur = (vals || [])[0], prev = (vals || [])[back], ch = ppChange(cur, prev);
  if (!isFig(cur)) return '';
  if (ch === null) return `${name} was ${pctText(cur)} in ${labels[0]}.`;
  if (flat(ch)) return `${name} was ${pctText(cur)} in ${labels[0]}, unchanged from ${labels[back]}.`;
  return `${name} was ${pctText(cur)} in ${labels[0]}, ${ch > 0 ? 'up' : 'down'} ${num(Math.abs(ch), 1)} percentage ${Math.abs(Number(ch.toFixed(1))) === 1 ? 'point' : 'points'} from ${pctText(prev)} in ${labels[back]}.`;
}

/** Operating cash flow less capital spending against the statement's free cash flow: whether the three agree, to
 * half a percent of operating cash flow (or a million dollars). A bridge is drawn only when they do. */
export function bridges(ocf, capex, fcf) {
  if (![ocf, capex, fcf].every(isFig)) return false;
  return Math.abs(ocf + capex - fcf) <= Math.max(1e6, Math.abs(ocf) * 0.005);
}
export function cashFlowLine(ocf, capex, fcf, labels, usd = moneyIn('USD')) {
  const o = (ocf || [])[0], c = (capex || [])[0], f = (fcf || [])[0];
  if (!isFig(f)) return '';
  const ch = pctChange(f, (fcf || [])[1]);
  const how = bridges(o, c, f) ? `: ${usd(o)} from operations less ${usd(Math.abs(c))} of capital spending` : isFig(o) && isFig(c) ? `. Operating cash flow less capital spending gives ${usd(o + c)}, which is not the statement's figure, so no bridge is drawn` : '';
  const vs = ch === null ? '' : flat(ch) ? `, unchanged from ${labels[1]}` : `, ${ch > 0 ? 'up' : 'down'} ${num(Math.abs(ch), 1)}% from ${usd(fcf[1])} in ${labels[1]}`;
  return `Free cash flow was ${usd(f)} in ${labels[0]}${how}${vs}.`;
}

/** Cash less debt, and whether it matches the net figure reported beside them. */
export function netCash(cash, debt, reported = null) {
  if (!isFig(cash) || !isFig(debt)) return null;
  const net = cash - debt;
  return { net, matches: !isFig(reported) || Math.abs(net - reported) <= Math.max(1e6, Math.abs(net) * 0.001) };
}
export function netCashLine(cash, debt, labels, usd = moneyIn('USD')) {
  const c = (cash || [])[0], d = (debt || [])[0], n = netCash(c, d);
  if (!n) return '';
  const first = (debt || []).length - 1;
  const trend = first > 0 && isFig(debt[first]) && isFig(d) && pctChange(d, debt[first]) !== null && !flat(pctChange(d, debt[first]))
    ? ` Debt ${moved(pctChange(d, debt[first]))} from ${usd(debt[first])} at the end of ${labels[first]}.` : '';
  return `${n.net < 0 ? 'Net debt' : 'Net cash'} of ${usd(Math.abs(n.net))} at the end of ${labels[0]}: ${usd(c)} of cash and equivalents against ${usd(d)} of debt.${trend}`;
}

/** EPS and the share count beside it, each with its own change and no claim that one caused the other. */
export function perShareLine(eps, shares, labels, back = 1, against = '') {
  const e0 = (eps || [])[0], s0 = (shares || [])[0];
  if (!isFig(e0)) return '';
  const ce = pctChange(e0, (eps || [])[back]), cs = pctChange(s0, (shares || [])[back]);
  const then = `${labels[back] || ''}${against ? `, ${against}` : ''}`;
  const a = `Diluted EPS was ${num(e0, 2)} in ${labels[0]}${ce === null ? '' : flat(ce) ? `, unchanged from ${then}` : `, ${ce > 0 ? 'up' : 'down'} ${num(Math.abs(ce), 1)}% from ${num(eps[back], 2)} in ${then}`}.`;
  // with the EPS change left out (a base at or below zero), "the same span" named no span (CRCL, audit 2026-10-22)
  return cs === null ? a : `${a} ${ce === null ? `From ${then} to ${labels[0]}` : 'Over the same span'} the diluted share count ${flat(cs) ? `was unchanged at ${compact(s0)}` : `${cs > 0 ? 'rose' : 'fell'} ${num(Math.abs(cs), 1)}%, to ${compact(s0)}`}.`;
}

/** The parts of a total for one period, as filed: rows with no figure dropped; an aggregate line (Apple files
 * "Product", the sum of iPhone, Mac, iPad and Wearables, beside them) left out when removing it brings the parts to
 * the reported total, so nothing is counted twice; never scaled to 100. `canShare`: every part at or above zero. */
export function composition(members, values, total = null) {
  let rows = (members || []).map((m, i) => ({ label: m, v: (values || [])[i] })).filter((r) => isFig(r.v));
  let sum = rows.reduce((a, r) => a + r.v, 0);
  const dropped = [];
  if (isFig(total) && total > 0 && sum > total * 1.02) {
    const hit = rows.find((r) => Math.abs(sum - r.v - total) <= total * 0.01);
    if (hit) { dropped.push(hit.label); rows = rows.filter((r) => r !== hit); sum -= hit.v; }
  }
  rows.sort((a, b) => b.v - a.v);
  const gap = isFig(total) ? total - sum : null;
  return { rows, dropped, sum, total: isFig(total) ? total : null, gap, reconciles: isFig(total) && total !== 0 && Math.abs(gap) <= Math.abs(total) * 0.01, canShare: rows.length > 0 && rows.every((r) => r.v >= 0) };
}
export function compositionLine(c, metric, label, usd = moneyIn('USD')) {
  if (!c.rows.length) return '';
  const top = c.rows[0], base = c.reconciles ? c.total : c.sum;
  const sh = c.canShare ? share(top.v, base) : null;
  const lead = `${top.label} was the largest${sh === null ? `, at ${usd(top.v)}` : `, ${usd(top.v)} or ${num(sh, 0)}% of ${metric.toLowerCase()}`} in ${label}.`;
  const recon = c.total === null ? `The parts add to ${usd(c.sum)}.` : c.reconciles ? `The parts add to the ${usd(c.total)} reported.` : `The parts add to ${usd(c.sum)}, against ${usd(c.total)} reported; the ${usd(Math.abs(c.gap))} difference is not assigned to a part in the filing.`;
  return `${lead} ${recon}`;
}

/** An earnings surprise, read the same way every quarter: the dollar difference always; a percentage only when
 * the estimate is at least ten cents (a percentage of almost nothing misleads); in line when it rounds to nothing. */
export function surprise(est, act, pct = null) {
  if (!isFig(est) || !isFig(act)) return { cls: 'missing', diff: null, pct: null, small: false };
  const diff = act - est, small = Math.abs(est) < 0.1;
  const p = small ? null : isFig(pct) ? pct : (diff / Math.abs(est)) * 100;
  const inLine = Math.abs(diff) < 0.005 || (p !== null && Math.abs(Number(p.toFixed(1))) === 0);
  return { cls: inLine ? 'in line' : diff > 0 ? 'beat' : 'miss', diff, pct: inLine ? 0 : p, small };
}
export const CLASS_WORD = { beat: 'Beat', miss: 'Miss', 'in line': 'In line', missing: 'No estimate' };

/** Reaction-session moves against a one-session implied move: the comparison the two windows allow. */
export function reactionVsImplied(moves, implied) {
  const ms = (moves || []).filter(isFig);
  if (!ms.length) return null;
  const avg = ms.reduce((a, m) => a + Math.abs(m), 0) / ms.length;
  return { n: ms.length, avg, over: isFig(implied) ? ms.filter((m) => Math.abs(m) > implied).length : null, largest: ms.reduce((a, m) => (Math.abs(m) > Math.abs(a) ? m : a), 0) };
}

/** The three ways a figure can be absent, said the same way everywhere (beginner brief item 13): not out yet, not
 * a figure this item has, or one Optic does not have. Never a blank, never a zero. */
export const MISSING = { pending: 'Not released yet', na: 'Not applicable', unavailable: 'Not available' };
