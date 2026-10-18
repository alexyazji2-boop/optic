// A sortable table for lists of companies or filings. Headers are buttons that
// set aria-sort; the caller keeps the sort state and repaints, so a sort
// survives a data refresh. Cells render through each column's own function.
import { html } from '../core/dom.js';
import { icon } from './icons.js';

/**
 * cols: [{key, label, num?: bool, sort?: (row) => value, cell: (row) => tpl, hideOnPhone?: bool}]
 * opts: {id, sort: {key, dir: 'asc'|'desc'}, caption, rowAttrs?: (row) => tpl, empty?: tpl}
 */
export function sortRows(rows, cols, sort) {
  const c = cols.find((x) => x.key === (sort || {}).key);
  if (!c) return rows;
  const val = c.sort || ((r) => r[c.key]);
  const dir = sort.dir === 'asc' ? 1 : -1;
  return rows.slice().sort((a, b) => {
    const x = val(a), y = val(b);
    const xn = x === null || x === undefined || x === '' || Number.isNaN(x), yn = y === null || y === undefined || y === '' || Number.isNaN(y);
    if (xn || yn) return xn && yn ? 0 : xn ? 1 : -1; // blanks last either way
    return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))) * dir;
  });
}

export function table(rows, cols, opts = {}) {
  const sort = opts.sort || {};
  const sorted = sortRows(rows, cols, sort);
  return html`<div class="tscroll"><table class="t st" id="${opts.id || ''}">${opts.caption ? html`<caption class="sr">${opts.caption}</caption>` : ''}
    <thead><tr>${cols.map((c) => {
      const on = sort.key === c.key;
      return html`<th scope="col" class="${c.num ? 'n' : ''} ${c.hideOnPhone ? 'ph-hide' : ''}" aria-sort="${on ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}">${c.sortable === false ? c.label
        : html`<button type="button" class="th-sort" data-v2-sort="${opts.id || 't'}:${c.key}">${c.label}${on ? icon(sort.dir === 'asc' ? 'up' : 'down') : ''}</button>`}</th>`;
    })}</tr></thead>
    <tbody>${sorted.length ? sorted.map((r) => html`<tr ${opts.rowAttrs ? opts.rowAttrs(r) : ''}>${cols.map((c) => html`<td class="${c.num ? 'n' : ''} ${c.hideOnPhone ? 'ph-hide' : ''}">${c.cell(r)}</td>`)}</tr>`)
      : html`<tr><td colspan="${cols.length}" class="quiet">${opts.empty || 'Nothing to show.'}</td></tr>`}</tbody></table></div>`;
}

/** Toggle helper for a click on a header: returns the next sort state. */
export function nextSort(sort, key, cols) {
  if (sort && sort.key === key) return { key, dir: sort.dir === 'asc' ? 'desc' : 'asc' };
  const c = cols.find((x) => x.key === key);
  return { key, dir: c && c.num ? 'desc' : 'asc' };
}
