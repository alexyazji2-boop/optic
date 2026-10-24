// Keyboard shortcuts, one list (motion proposal Phase 2, 2026-10-24): "?" anywhere outside a field, the palette's
// "Keyboard shortcuts" row, and Settings. Every key listed here is one the code already handles; the list is read
// from no other place, so a key added elsewhere must be added here too (tests/test_v2_phase2.py checks the pairs).
import { html } from '../core/dom.js';
import * as drawer from './drawer.js';

const MAC = /Mac|iPhone|iPad/.test((typeof navigator !== 'undefined' && (navigator.platform || navigator.userAgent)) || '');
const MOD = MAC ? '⌘' : 'Ctrl';

export const GROUPS = [
  ['Anywhere', [
    [[MOD, 'K'], 'Search, open a company or a page, or ask Milo'],
    [['/'], 'Search, the same box'],
    [['?'], 'This list'],
    [['Esc'], 'Close a menu, the search box or a panel'],
  ]],
  ['In the search box', [
    [['↑', '↓'], 'Move between results'],
    [['Enter'], 'Open the marked result'],
    [['>'], 'Typed first: pages and actions only, no company search'],
  ]],
  ['On a chart (click it first)', [
    [['←', '→'], 'Read the bar before or after'],
    [['Shift', '←', '→'], 'Move along the history'],
    [['↑', '↓'], 'Stretch or squeeze the price scale'],
    [['+', '−'], 'Zoom in or out'],
    [['Home', 'End'], 'The first or last bar in view'],
    [['M'], 'Measure from the bar being read'],
    [['Delete'], 'Remove the selected drawing'],
    [[MOD, 'Z'], 'Undo a drawing; with Shift, redo'],
  ]],
  ['Milo', [
    [['Enter'], 'Send'],
    [['Shift', 'Enter'], 'A new line'],
  ]],
  ['Watchlist', [
    [['↑', '↓'], 'Move between rows'],
    [['Enter'], 'Open the company beside the list'],
  ]],
];

const keys = (ks) => ks.map((k, i) => html`${i ? html`<span class="kbd-plus" aria-hidden="true"> </span>` : ''}<kbd>${k}</kbd>`);

export function openShortcuts(opener) {
  drawer.open({
    kicker: 'Keyboard', title: 'Keyboard shortcuts', opener,
    body: html`<div class="shortcuts">${GROUPS.map(([name, rows]) => html`<section><h3 class="t-label">${name}</h3>
      <dl class="sc-list">${rows.map(([ks, what]) => html`<div><dt>${keys(ks)}</dt><dd>${what}</dd></div>`)}</dl></section>`)}
      <p class="asof">Keys are ignored while you type in a field, so a slash or a question mark in a search or a question stays text.</p></div>`,
  });
}
