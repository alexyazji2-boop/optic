// Portfolio scenarios (roadmap stage 6, 2026-10-22): what today's positions would be worth if something happened,
// drawn the same way for an Optic Portfolio book (/api/portfolio-scenarios) and a linked brokerage
// (/api/brokerage/workspace/scenarios). One engine, app/analytics/scenarios.py, revalues every position in full;
// this only lays it out. It leads with the answer (a 10% fall, together and by beta), keeps the exposures apart
// (premium at risk, notional, delta-adjusted, concentration, correlation, the options' convexity), and says what
// it could not price. Every figure is hypothetical and is never shown beside recorded performance.
import { html } from '../core/dom.js';
import { num, money, signedMoney, signed, clean, dir, isNum, plural } from '../core/format.js';
import { failed, how } from './states.js';

const pctOf = (v, base) => (isNum(v) && base ? signed((100 * v) / Math.abs(base), 1) : 'n/a');
const cell = (v) => html`<td class="n ${dir(v)}">${isNum(v) ? signedMoney(v, 0) : 'n/a'}</td>`;

function rowsOf(g) {
  if (g.id !== 'earnings') return g.rows.map((r) => ({ ...r }));
  return g.rows.flatMap((r) => (r.unavailable ? [{ label: r.label, unavailable: r.unavailable }]
    : [{ ...r.up, label: `${r.label}: up ${num(r.move_pct, 1)}%` }, { ...r.down, label: `${r.label}: down ${num(r.move_pct, 1)}%` }]));
}

function table(sc, hasOptions) {
  const cols = hasOptions ? 6 : 4;
  return html`<div class="tscroll"><table class="t sc-t"><thead><tr><th scope="col">If</th><th scope="col">Change in value</th><th scope="col">Of today's value</th><th scope="col">Hardest hit</th>${hasOptions ? html`<th scope="col">Options alone</th><th scope="col">Delta alone says</th>` : ''}</tr></thead>
    <tbody>${sc.groups.map((g) => html`<tr class="sc-g"><th scope="colgroup" colspan="${cols}">${g.title}</th></tr>
      ${rowsOf(g).map((r) => (r.unavailable ? html`<tr><th scope="row">${clean(r.label)}</th><td colspan="${cols - 1}" class="t-muted">${clean(r.unavailable)}</td></tr>`
          : html`<tr><th scope="row">${clean(r.label)}${(r.left_out || []).length ? html` <small class="t-muted">without ${r.left_out.join(', ')}</small>` : ''}</th>${cell(r.pnl)}<td class="n ${dir(r.pnl)}">${pctOf(r.pnl, sc.gross_value)}</td>
          <td>${(r.worst || []).length ? r.worst.map((w) => `${w.symbol} ${signedMoney(w.pnl, 0)}`).join(', ') : html`<span class="t-muted">none lose</span>`}</td>
          ${hasOptions ? html`${cell(r.option_pnl)}<td class="n t-muted">${isNum(r.delta_estimate) ? signedMoney(r.delta_estimate, 0) : ''}</td>` : ''}</tr>`))}`)}</tbody></table></div>`;
}

function lead(sc) {
  const find = (gid, id) => ((sc.groups.find((g) => g.id === gid) || { rows: [] }).rows.find((r) => r.id === id));
  const all = find('together', 'all-10'), spx = find('market', 'spx-10');
  if (!all) return '';
  return html`<p class="sc-lead">If every holding fell 10% together, these positions would be worth about <b class="${dir(all.pnl)}">${money(Math.abs(all.pnl), 0)} ${all.pnl < 0 ? 'less' : 'more'}</b> (${pctOf(all.pnl, sc.gross_value)})${spx && isNum(spx.pnl) ? html`; a 10% fall in the S&P 500, through each holding's beta, comes to <b class="${dir(spx.pnl)}">${signedMoney(spx.pnl, 0)}</b>` : ''}.</p>`;
}

function exposures(e, sc) {
  const c = e.concentration || {}, nl = e.nonlinear || {};
  const kv = (t, v, note) => html`<div><dt>${t}</dt><dd>${v}</dd>${note ? html`<dd class="note">${note}</dd>` : ''}</div>`;
  const opts = isNum(e.premium_at_risk) || isNum(e.short_premium) || isNum(nl.vega_per_point);
  return html`<dl class="kv sc-kv">
      ${kv('Delta-adjusted, net', money(e.delta_adjusted_net, 0), `gross ${money(e.delta_adjusted_gross, 0)}: what it moves like`)}
      ${kv('Notional, gross', money(e.gross_notional, 0), `net ${money(e.net_notional, 0)}: what it controls`)}
      ${opts ? kv('Premium at risk', money(e.premium_at_risk || 0, 0), 'the most the long options can lose') : ''}
      ${opts && e.short_premium ? kv('Premium taken in', money(e.short_premium, 0), (e.uncovered_short_calls || []).length ? html`<span class="down">uncovered calls on ${e.uncovered_short_calls.map((u) => u.symbol).join(', ')}: the loss has no ceiling</span>` : 'short options; they can lose more than this') : ''}
      ${kv('Largest name', c.largest ? `${c.largest} ${num(c.largest_pct, 0)}%` : 'n/a', `top three ${num(c.top3_pct, 0)}%; like ${num(c.effective_names, 1)} equal positions`)}
    </dl>
    ${(e.correlated || []).length ? html`<p><b>Moving together.</b> ${e.correlated.map((g) => `${g.names.join(', ')} (${num(g.share_pct, 0)}% of the delta-adjusted exposure, average correlation ${num(g.avg_correlation, 2)})`).join('; ')}. <span class="t-muted">${clean(e.correlated_note)}</span></p>`
      : html`<p class="asof">No two holdings moved together closely (a correlation of 0.70 or more) over the last quarter. That describes calm markets; in a selloff correlations rise, so read the rows where every holding moves together.</p>`}
    ${(c.sectors || []).length ? html`<p class="asof">By sector, delta-adjusted: ${c.sectors.slice(0, 5).map((s) => `${s.sector} ${num(s.share_pct, 0)}%`).join(', ')}.</p>` : ''}
    ${isNum(nl.vega_per_point) ? html`<p class="asof">The options' nonlinear risk: ${signedMoney(nl.gamma_1pct, 0)} from gamma alone on a 1% move either way, ${signedMoney(nl.vega_per_point, 0)} per point of implied volatility, ${signedMoney(nl.theta_per_day, 0)} a day with nothing else changing. The gap between the last two columns of the table is what delta alone misses.</p>` : ''}`;
}

function coverage(sc) {
  const c = sc.coverage || {}, m = sc.marks || {};
  return html`<p class="asof">${c.priced} of ${plural(c.positions, 'position')} revalued, ${num(c.value_covered_pct, 0)}% of the value${(c.multiplier_assumed || []).length ? `; a standard contract size assumed for ${c.multiplier_assumed.length === 1 ? 'one option' : `${c.multiplier_assumed.length} options`}, the source did not say` : ''}. ${clean(m.note || '')}</p>
    ${(c.unpriced || []).length ? html`<p class="asof"><b>Left out of every figure:</b> ${c.unpriced.map((u) => `${u.label} (${clean(u.reason || '').replace(/\.$/, '')})`).join('; ')}.</p>` : ''}
    ${(c.stale || []).length ? html`<p class="asof"><b>Prices from different times:</b> ${c.stale.map((s) => clean(s.reason)).join(' ')}</p>` : ''}`;
}

/** The scenarios section. `sc` undefined while loading; {error} on failure. */
export function scenariosSection(sc, { retry = 'scenarios', id = 'sc-h' } = {}) {
  const head = html`<h2 class="t-h2" id="${id}">What could happen to these positions</h2>`;
  if (sc === undefined) return html`<section class="section" aria-labelledby="${id}">${head}<p class="t-muted" role="status">Revaluing every position under each scenario…</p></section>`;
  if (sc && typeof sc.error === 'string') return html`<section class="section" aria-labelledby="${id}">${head}<div class="state err" role="alert"><p class="t-h3">The scenarios did not load</p><p>${sc.error}</p><button type="button" class="btn btn-sm" data-v2-retry="${retry}">Try again</button></div></section>`;
  if (!sc || sc.error) return html`<section class="section" aria-labelledby="${id}">${head}${failed('The scenarios', (sc || {}).error, { retry })}</section>`;
  if (!sc.available) return html`<section class="section" aria-labelledby="${id}">${head}<p>${clean(sc.reason || 'Unavailable.')}</p>${((sc.coverage || {}).unpriced || []).length ? coverage({ coverage: { priced: 0, positions: sc.coverage.unpriced.length, ...sc.coverage }, marks: {} }) : ''}</section>`;
  const hasOptions = sc.groups.some((g) => g.id === 'volatility');
  return html`<section class="section" aria-labelledby="${id}">${head}
    <p class="section-sub">${clean(sc.hypothetical)}</p>
    ${lead(sc)}${exposures(sc.exposure || {}, sc)}${table(sc, hasOptions)}${coverage(sc)}
    ${how(html`${sc.groups.map((g) => html`<p><b>${g.title}.</b> ${clean(g.note)}</p>`)}<p>${clean((sc.exposure || {}).correlated_note || '')}</p><p>${clean(sc.method)}</p><p>${clean((sc.exposure || {}).basis || '')}</p>
      ${((sc.groups.find((g) => g.id === 'market') || {}).betas || []).length ? html`<p>Betas to SPY over the last year: ${sc.groups.find((g) => g.id === 'market').betas.map((b) => `${b.symbol} ${isNum(b.beta) ? num(b.beta, 2) : 'n/a'}`).join(', ')}.</p>` : ''}
      <p class="asof">${sc.source ? `${clean(sc.source)}. ` : ''}${sc.version}.</p>`)}</section>`;
}
