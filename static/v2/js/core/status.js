// The always-there bits of the shell: the market session in the top bar
// (refreshed each minute), the feed and Milo line in the footer (the classic
// footer chip), and a notice while the browser is offline.
import { html, render, $ } from './dom.js';
import * as api from './api.js';
import * as prefs from './prefs.js';

async function session() {
  const el = $('#session-chip'); if (!el) return;
  try {
    const s = await api.get('/api/session', { ttl: 50000, timeout: 10000 });
    const next = s.next && s.next.starts_at ? `${s.next.label} at ${prefs.clock(s.next.starts_at)}` : '';
    render(el, html`<i class="ses-dot p-${s.phase}" aria-hidden="true"></i><span class="sc-label">${s.label}</span>${next ? html`<span class="sc-next">, ${next}</span>` : ''}`);
    el.title = [s.description, s.early_close_note].filter(Boolean).join(' ');
  } catch (e) { render(el, ''); }
}
async function health() {
  const el = $('#app-status'); if (!el) return;
  try {
    const h = await api.get('/api/health', { ttl: 300000, timeout: 10000 });
    const feed = h.realtime_chain ? 'Option chains real-time; other quotes may be delayed.' : 'Quotes from Yahoo Finance, delayed about 15 minutes.';
    const milo = (h.assistant || {}).enabled ? 'Milo is answering.' : 'Milo is switched off in this build.';
    render(el, `${feed} ${milo}`);
  } catch (e) { render(el, ''); }
}
function offline() {
  let bar = $('#offline-bar');
  if (navigator.onLine !== false) { if (bar) bar.remove(); return; }
  if (bar) return;
  bar = document.createElement('div'); bar.id = 'offline-bar'; bar.className = 'offline-bar'; bar.setAttribute('role', 'status');
  bar.textContent = 'You are offline. What is on screen stays; new figures load when you are back.';
  document.body.appendChild(bar);
}
export function watchStatus() {
  session(); health(); offline();
  setInterval(() => { if (!document.hidden) session(); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) session(); });
  window.addEventListener('online', offline); window.addEventListener('offline', offline);
  prefs.onChange((w) => { if (w === 'timezone') session(); });
}
