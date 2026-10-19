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
// The notice shows only while the browser says it is offline and the server has not answered in the last
// 30 s: the browser's flag alone was wrong in iOS Safari (2026-10-19).
function offline() {
  let bar = $('#offline-bar');
  if (navigator.onLine !== false || Date.now() - api.lastReached() < 30000) { if (bar) bar.remove(); return; }
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
  window.addEventListener('optic:reached', offline);
  setInterval(offline, 30000);   // a server that stops answering while the browser says offline brings it back
  prefs.onChange((w) => { if (w === 'timezone') session(); });
}
