// The figure registry (owner's Handoff 1, 2026-11-03; app/figures on the server): what each financial figure is,
// fetched once per session, and the helpers every page prints one with. A page never formats one of these figures
// itself. It prints the server's `text`, so the Dossier, Compare and Milo cannot round, date or define the same
// figure differently: on 2026-11-03 AAPL's net debt read $62.7B in one Financials caption and $44.0B beside it.
import * as api from './api.js';

const TTL = 3600000;
let REG = null, pending = null, failedAt = 0;

// Whether the definitions could be read, on the root element: while they cannot, every figure on the page carries
// "definition unavailable" beside it (components.css), rather than a figure that silently explains nothing
const flag = (failed) => { try { if (failed) document.documentElement.dataset.figRegistry = 'failed'; else delete document.documentElement.dataset.figRegistry; } catch (e) { /* no document */ } };
/** The registry, fetched once per session; resolves to null when it could not be read (the panel says so). */
export function registry() {
  if (REG) return Promise.resolve(REG);
  if (!pending) {
    pending = api.get('/api/figures/registry', { ttl: TTL, timeout: 15000 })
      .then((r) => { REG = r && r.figures ? r : null; pending = null; flag(!REG); return REG; })
      .catch(() => { pending = null; failedAt = Date.now(); flag(true); return null; });
  }
  return pending;
}
/** The registry if it has arrived, without waiting. */
export const loaded = () => REG;
export const lastFailure = () => failedAt;
/** One entry's definition data, or null when the registry has no such figure. */
export const entry = (id) => (REG && REG.figures && REG.figures[id]) || null;

/** One figure's value from a payload that carries the registry block (`/api/ticker`, `/api/figures/{T}`). */
export function of(payload, id) {
  const block = payload && payload.figures;
  const figs = block && block.figures;
  return (figs && figs[id]) || null;
}
export const ok = (fv) => !!(fv && fv.status === 'ok' && fv.value !== null && fv.value !== undefined);
/** The figure's value for a page's own arithmetic or comparisons (never for printing: print `fv.text`). */
export const value = (fv) => (ok(fv) ? Number(fv.value) : null);
/** The period a figure covers, as a page labels it: "12 months to Sep 26, 2026". */
export const period = (fv) => ((fv && fv.period) || {}).label || '';

// The registry's figures for Milo's page context, and the page's own copies of them taken out of the quote and the
// statements it also sends, so the model has one number for each, with its period and source (Handoff 1).
export function forMilo(block) {
  const figs = (block && block.figures) || {};
  const out = {};
  Object.keys(figs).forEach((id) => {
    const fv = figs[id] || {}, per = fv.period || {}, src = fv.source || {};
    out[id] = { name: fv.name, text: fv.text, status: fv.status, period: per.label ? `${per.label}${per.fiscal ? ` (${per.fiscal})` : ''}` : null, source: src.name || null, filing: src.url || null };
    if (fv.why) out[id].why = fv.why;
  });
  return Object.keys(out).length ? out : null;
}
export function quoteForMilo(q) {
  if (!q || typeof q !== 'object') return q;
  const out = { ...q };
  delete out.forward_pe; delete out.profit_margin;
  return out;
}
// The statements without the provider's guessed fiscal names ("FY26" for Home Depot's fiscal 2025), with each column's
// period as the filings name and date it instead (Handoff 2), when the page has the registry's block.
export function companyForMilo(c, block = null) {
  const fin = c && c.financials;
  if (!fin || typeof fin !== 'object') return c;
  const margins = { ...(fin.margins || {}) }, bs = { ...(fin.balance_sheet || {}) };
  delete margins.net_pct; delete bs.net_cash;
  const out = { ...fin, margins, balance_sheet: bs };
  delete out.annual_fiscal; delete out.quarterly_fiscal; delete out.fiscal_year_end;
  const st = ((block || {}).periods || {}).statements;
  if (st) {
    const words = (d) => (d && d.label ? `${d.short ? `${d.short}, ` : ''}${d.label}` : 'Period labels unavailable');
    out.annual_period_labels = (st.annual || []).map(words);
    out.quarterly_period_labels = (st.quarterly || []).map(words);
    if (st.basis) out.accounting_basis = st.basis;
  }
  return { ...c, financials: out };
}
