// Line icons, 24px grid, stroked with currentColor. Decorative unless a label
// is passed, because every icon in v2 sits beside visible text.
import { raw } from '../core/dom.js';

const P = {
  home: '<path d="M4 11 12 4l8 7v9h-5v-6H9v6H4z"/>',
  dossier: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 12h7M9 16h5"/>',
  compare: '<path d="M8 4v16M16 4v16M4 8h8M12 16h8"/>',
  markets: '<path d="M3 18l5-6 4 3 7-9"/><path d="M15 6h4v4"/>',
  discover: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  positions: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  brokerage: '<path d="M3 10 12 4l9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/>',
  watchlist: '<path d="M2.6 12C5.6 6.6 8.6 4.6 12 4.6s6.4 2 9.4 7.4c-3 5.4-6 7.4-9.4 7.4S5.6 17.4 2.6 12Z"/><circle cx="12" cy="12" r="2.8"/>',
  reports: '<path d="M5 3h10l4 4v14H5z"/><path d="M9 13h6M9 17h4M9 9h2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
  more: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.7 9.4a2.4 2.4 0 0 1 4.6 1c0 1.6-2.3 2-2.3 3.6"/><path d="M12 17.2v.1"/>',
  grip: '<circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  chev: '<path d="m9 6 6 6-6 6"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  out: '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
  up: '<path d="m6 15 6-6 6 6"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  bell: '<path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  milo: '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 10h8M8 13h5"/>',
  // the chart's tools (pages/chart.js): each button carries its name, so these stay decorative
  minus: '<path d="M5 12h14"/>',
  // Milo's panel (2026-10-20 redesign): history, a new conversation, response settings, attached context, the
  // data note, send and stop, the chosen persona, copy, ask again, back to the latest answer
  history: '<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4.5v4h4"/><path d="M12 8v4.2l2.8 1.8"/>',
  compose: '<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="M12 8.5v7M8.5 12h7"/>',
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1"/><path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.8v.1"/>',
  send: '<path d="M12 19V5.5M6.5 11 12 5.5l5.5 5.5"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="1.5"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/>',
  retry: '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v4.2h-4.2"/>',
  arrowDown: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  // Fit is the whole range between two edges; the four corners are full screen, as in the classic chart
  fit: '<path d="M4 5v14M20 5v14M8 12h8M10.5 9.5 8 12l2.5 2.5M13.5 9.5 16 12l-2.5 2.5"/>',
  expand: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  shrink: '<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/>',
  palette: '<path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.2 0 1.9-.8 1.9-1.8 0-1.2-1.1-1.6-1.1-2.8 0-1 .8-1.8 1.9-1.8h2.4a3.4 3.4 0 0 0 3.4-3.4c0-4-3.8-7.2-8.5-7.2Z"/><circle cx="7.6" cy="11.2" r="1.1"/><circle cx="10.4" cy="7.4" r="1.1"/><circle cx="15" cy="7.6" r="1.1"/>',
  candles: '<path d="M7 3.5v3.5M7 17v3.5M17 6v4M17 18v2.5"/><rect x="5" y="7" width="4" height="10" rx="1"/><rect x="15" y="10" width="4" height="8" rx="1"/>',
  lineChart: '<path d="M3 17l5-6 4 3 8-9"/>',
  area: '<path d="M3 17l5-6 4 3 8-9v15H3z"/>',
  lineChart: '<path d="M3 17l5-6 4 3 8-9"/>',   // the Line style (it had no icon of its own and drew an empty button)
  cursor: '<path d="M6 3.5l12 8.8-5.4 1.3 2.9 6.4-2.3 1-2.9-6.4L6 18.4z"/>',
  hline: '<path d="M3 12h18"/><circle cx="7" cy="12" r="1.8"/>',
  vline: '<path d="M12 3v18"/><circle cx="12" cy="8" r="1.8"/>',
  trend: '<path d="M5 19 19 5"/><circle cx="5" cy="19" r="1.8"/><circle cx="19" cy="5" r="1.8"/>',
  ray: '<path d="M5 19 20 4"/><circle cx="5" cy="19" r="1.8"/><path d="M15 4h5v5"/>',
  rect: '<rect x="4" y="6" width="16" height="12" rx="1.5"/>',
  fib: '<path d="M3 5h18M3 10h18M3 14h18M3 19h18"/><path d="M6 5v14" stroke-dasharray="2 2"/>',
  text: '<path d="M5 7V4.5h14V7M12 4.5V20M9 20h6"/>',
  undo: '<path d="M9 5 4 10l5 5"/><path d="M4 10h10a5.5 5.5 0 0 1 0 11h-3"/>',
  trash: '<path d="M4 7h16M9 7V4.5h6V7M6 7l1 13h10l1-13"/>',
  clear: '<path d="M4 7h16M9 7V4.5h6V7M6 7l1 13h10l1-13M10 11l4 5M14 11l-4 5"/>',
  layers: '<path d="m12 4 9 5-9 5-9-5z"/><path d="m3 14 9 5 9-5"/>',
  pencil: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
  // the drawing tools the classic app adds (C10), its own marks
  channel: '<path d="M3.5 14.5 17 4.5M7 19.5 20.5 9.5"/>',
  fibext: '<path d="M4 19.5h9M4 14.5h9M4 9.5h16M4 4.5h16"/><path d="M17 19.5V12"/><path d="m14.5 14.5 2.5-2.5 2.5 2.5"/>',
  pitchfork: '<path d="M3.5 20.5 9.5 14.5"/><path d="M9.5 14.5 20 7M9.5 14.5H20M9.5 14.5 20 21"/>',
  arrowdraw: '<path d="M5 19 18.5 5.5"/><path d="M11 5.5h7.5V13"/>',
  ruler: '<path d="M4 12h16"/><path d="m7 9-3 3 3 3M17 9l3 3-3 3"/>',
  rr: '<rect x="5" y="3.5" width="14" height="17" rx="1"/><path d="M5 11h14"/>',
  position: '<rect x="5" y="3.5" width="14" height="17" rx="1.5"/><path d="M8 7.5h8"/><path d="M8.5 12h.01M12 12h.01M15.5 12h.01M8.5 16h.01M12 16h.01M15.5 16h.01" stroke-width="2.4"/>',
  magnet: '<path d="M6 3v9a6 6 0 0 0 12 0V3M6 7.5h3.75M14.25 7.5H18"/>',
  redo: '<path d="M15 5l5 5-5 5"/><path d="M20 10H10a5.5 5.5 0 0 0 0 11h3"/>',
};

export function icon(name, label = '') {
  const a = label ? `role="img" aria-label="${label}"` : 'aria-hidden="true"';
  return raw(`<svg viewBox="0 0 24 24" ${a} class="ic ic-${name}">${P[name] || ''}</svg>`);
}

// The Optic mark, from static/index.html (the brand's eye and line).
export const brandMark = () => raw(`<svg viewBox="0 0 32 32" aria-hidden="true">
  <path d="M2.6 16C6.3 8.9 10.9 5.4 16 5.4S25.7 8.9 29.4 16C25.7 23.1 21.1 26.6 16 26.6S6.3 23.1 2.6 16Z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" opacity="0.7"/>
  <path d="M7.4 20.2 11.4 15.6 14.6 17.8 18.6 11.6 21.6 14 23.9 11.4" fill="none" stroke="var(--c-gold-light)" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="23.9" cy="11.4" r="1.5" fill="var(--c-gold-light)"/></svg>`);
