// Scores in green and red, with a line filled to the score (owner, 2026-10-21: "use the green/red color scheme
// wherever applicable, such as optic score ... include a line filled percentage based on the score like how classic
// used to show"). Classic's rules, one per kind of score:
// - a 0 to 100 score where 50 is no edge (the Optic Score, the composite, the long-term conviction): green from 55,
//   red to 45, grey between (Classic's ovScoreTile);
// - a signed score (the market score, from -100 to +100): green above zero, red below, filled out from a middle line
//   (Classic's pulseBar);
// - a score with named bands (the dividend score, the sentiment gauge): the band's own side.
// The figure beside the line says the value and the words say the reading, so colour never carries it alone; the
// line itself is hidden from a screen reader.
import { html } from '../core/dom.js';
import { isNum } from '../core/format.js';

/** A 0 to 100 score's side: up from 55, down to 45, flat between; nothing when there is no score. */
export const tone100 = (n, hi = 55, lo = 45) => (!isNum(n) ? '' : Number(n) >= hi ? 'up' : Number(n) <= lo ? 'down' : 'flat');
/** A signed score's side. */
export const toneSign = (n) => (!isNum(n) ? '' : Number(n) > 0 ? 'up' : Number(n) < 0 ? 'down' : 'flat');
/** A banded reading's side, by the words of its band (Classic: strong or solid up, weak down; greed up, fear down). */
export function toneBand(words) {
  const w = String(words || '').toLowerCase();
  if (/greed|strong|solid|risk-on/.test(w)) return 'up';
  if (/fear|weak|risk-off/.test(w)) return 'down';
  return w ? 'flat' : '';
}

/** The line under a score: filled from the left to its share of the scale. */
export function scoreLine(n, { max = 100, tone } = {}) {
  if (!isNum(n)) return html`<span class="sline is-none" aria-hidden="true"></span>`;
  const t = tone || tone100(n), pct = Math.max(0, Math.min(100, (Number(n) / max) * 100));
  return html`<span class="sline is-${t || 'flat'}" aria-hidden="true"><i style="width:${pct.toFixed(1)}%"></i></span>`;
}
/** The line under a signed score: from a middle line, leftward below zero and rightward above. */
export function signedLine(n, { max = 100, tone } = {}) {
  if (!isNum(n)) return html`<span class="sline is-none" aria-hidden="true"></span>`;
  const v = Math.max(-max, Math.min(max, Number(n))), f = (Math.abs(v) / max) * 100, t = tone || toneSign(v);
  return html`<span class="sline sline-signed is-${t || 'flat'}" aria-hidden="true"><span class="sl-half sl-neg"><i style="width:${v < 0 ? f.toFixed(1) : 0}%"></i></span><b class="sl-mid"></b><span class="sl-half"><i style="width:${v > 0 ? f.toFixed(1) : 0}%"></i></span></span>`;
}
