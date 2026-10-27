// Table alignment by content (editorial pass, 2026-10-19). table.t right-aligned every column but the first, so
// text columns (an insider's name, a role, a setup's direction) sat right-aligned, and a numeric first column (a
// strike, a support price) sat left. Each column is now read: mostly figures, right; otherwise left. Cells that
// say n/a or are empty do not vote. A column a page marks itself (class "l" or "n") is left as marked.
export const FIG = /^[−+\-±~≈$€£]?\s*[\d][\d,]*(\.\d+)?\s*(%|×|x|[KMBT]|pp|pts?|bp|bps|vol pts?|days?|d|shares)?(\s*\(?[−+\-±]?[\d.,]+%?\)?)?(\s+(to|and|\/)\s+[−+\-$]?[\d.,]+%?)?\s*$/i;
const MISSING = /^(n\/a|not reported|none|\u2014|-)?$/i;

export function alignTable(t) {
  const rows = [...t.querySelectorAll('tr')];
  const width = Math.max(0, ...rows.map((r) => r.children.length));
  for (let c = 0; c < width; c += 1) {
    const cells = rows.map((r) => r.children[c]).filter(Boolean);
    if (cells.some((x) => x.classList.contains('l') || x.classList.contains('n'))) continue;
    const body = cells.filter((x) => x.tagName === 'TD').map((x) => x.textContent.replace(/\s+/g, ' ').trim()).filter((v) => !MISSING.test(v));
    if (!body.length) continue;
    // years and fiscal labels are names for a row, not figures to compare
    if (body.every((v) => /^(FY\s?)?(19|20)\d\d$/i.test(v))) { cells.forEach((x) => x.classList.add('l')); continue; }
    const figs = body.filter((v) => FIG.test(v.split(' (')[0]) || FIG.test(v)).length;
    const cls = figs / body.length >= 0.6 ? 'n' : 'l';
    cells.forEach((x) => x.classList.add(cls));
  }
  t.dataset.aligned = '1';
}

/** Align every shared table under root now, and any drawn later. */
/** Mark a table's sideways scroller when the table is wider than it, so the scroller can say so (components.css). */
export function markWide(root) {
  // only a box that scrolls: Compare's phone table lets its box overflow visibly, and "scroll sideways" would be wrong
  root.querySelectorAll('.tscroll').forEach((sc) => { const wide = /(auto|scroll)/.test(getComputedStyle(sc).overflowX) && sc.scrollWidth > sc.clientWidth + 4; if (wide !== sc.hasAttribute('data-wide')) sc.toggleAttribute('data-wide', wide); });
}

export function watchTables(root) {
  const run = () => { root.querySelectorAll('table.t:not([data-aligned])').forEach(alignTable); markWide(root); };
  run();
  let queued = false;
  new MutationObserver(() => { if (queued) return; queued = true; setTimeout(() => { queued = false; run(); }, 0); }).observe(root, { childList: true, subtree: true });
  let rz = 0;
  window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => markWide(root), 150); });
}
