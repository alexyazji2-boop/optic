// Pieces shared by Macro and Indices: the trend board for sector or index
// funds, and the written Sector Read, which is a paid model call and so only
// ever runs on the reader's press.
import { html, raw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, clean, bolded, capFirst, isNum } from '../core/format.js';
import { skeleton, empty, generated } from '../ui/states.js';

export function sectorBoard(board, readLabel) {
  if (board === undefined) return skeleton('rows', 4, 'Loading the board');
  if (!board || !board.available) return empty('The board is not available', clean((board || {}).reason || ''));
  const c = board.counts || {};
  // counts only when the board sent them: missing ones printed "0 in uptrends"
  return html`${['uptrend', 'downtrend', 'neutral'].every((k) => isNum(c[k])) ? html`<p>${c.uptrend} in uptrends, ${c.downtrend} in downtrends, ${c.neutral} inside their prior range${board.benchmark ? `, each against ${board.benchmark}` : ''}.</p>` : ''}
    <div class="tscroll"><table class="t"><thead><tr><th>Fund</th><th>Price</th><th>Trend</th><th>Bullish above</th><th>Bearish below</th><th>Rotation</th><th><span class="sr">Read</span></th></tr></thead>
      <tbody>${board.rows.filter((r) => r.available).map((r) => html`<tr><td><a href="#/${r.symbol}">${r.symbol}</a> ${r.name}<br><small class="t-muted">${clean((r.action || {}).text || r.summary || '')}</small></td>
        <td>${num(r.price)} <small class="t-muted">${r.price_kind || ''}</small></td><td>${capFirst(r.trend)}${r.changed ? html` <small class="t-muted">changed</small>` : ''}</td>
        <td>${num(r.bull_above)} <small class="t-muted">${signed(r.to_break_pct)}</small></td><td>${num(r.bear_below)} <small class="t-muted">${signed(r.to_breakdown_pct)}</small></td>
        <td>${(r.rotation || {}).label || ''}</td><td><button type="button" class="btn btn-sm" data-v2-sread="${r.symbol}" aria-label="${readLabel} for ${r.symbol}">${readLabel}</button></td></tr>`)}</tbody></table></div>
    <p class="asof">Levels from the prior session's range. ${/^[aeiou]/i.test(readLabel) ? 'An' : 'A'} ${readLabel} is written by an AI model when you ask for it, and kept for an hour.</p>`;
}

export function sectorReadBlock(sread) {
  if (!sread) return '';
  if (sread.loading) return html`<div class="sread" role="status">${sread.loading}. Reading the board…${skeleton('lines', 3)}</div>`;
  if (sread.error) return html`<div class="state err" role="alert"><p class="t-h3">The read did not load</p><p>${api.explain(sread.error, 'The read')}</p></div>`;
  if (!sread.available) return html`<div class="state"><p class="t-h3">${clean(sread.summary || 'No read')}</p><p>${clean(sread.reason || '')}</p><button type="button" class="btn btn-sm" data-v2-sread-close>Close</button></div>`;
  return html`<div class="sread"><p class="t-label">${sread.symbol || ''}, ${capFirst(sread.stance || '')}</p><h3 class="t-h3">${clean(sread.headline || '')}</h3>${(sread.paragraphs || []).map((p) => html`<p>${raw(bolded(p))}</p>`)}${generated(sread, { at: sread.written_at || sread.generated_at })}
    <p class="asof">${clean(sread.method || '')} ${clean(sread.disclaimer || '')}</p><button type="button" class="btn btn-sm" data-v2-sread-close>Close</button></div>`;
}

export async function loadSectorRead(sym) {
  try { const r = await api.get(`/api/sectors/${encodeURIComponent(sym)}/read`, { ttl: 3600000, timeout: 90000 }); return Object.assign({ symbol: sym }, r); }
  catch (e) { return { error: e }; }
}
