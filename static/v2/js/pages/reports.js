// Reports, the owner's three pages: Problem Reports (/api/feedback), Claude
// usage (/api/ai/usage) and Accounts (/api/admin/accounts). Owner only: the
// group shows only when /api/auth/me says admin, each page checks again before
// and after it fetches, and the server enforces it on every request. Nothing
// here calls a model.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { clean } from '../core/format.js';
import { stamp, dayTime } from '../core/prefs.js';
import { skeleton, failed } from '../ui/states.js';
import { toast } from '../ui/toast.js';
import { groupTabs } from './tabs.js';

const TITLES = { reports: 'Problem Reports', usage: 'Claude usage', accounts: 'Accounts' };
let view = 'reports', D = {}, live = true, mainEl = null, tab = 'open', armedAll = null, seq = 0;
const isOwner = () => !!(store.state.me && store.state.me.admin);
const count = (n) => Number(n || 0).toLocaleString('en-US');

function notOwner() {
  if (view === 'reports') {
    return store.signedIn()
      ? html`<p>These are for the owner of this site. This account is not the owner's, or its address has not been verified yet.</p>`
      : html`<p>These are for the owner of this site. Sign in with the owner's address to read them.</p><a class="btn btn-sm" href="#/signin">Sign in</a>`;
  }
  return html`<p>This is for the owner of this site. Sign in with the owner's address to read it.</p>${store.signedIn() ? '' : html`<a class="btn btn-sm" href="#/signin">Sign in</a>`}`;
}
const refused = (e) => e && (e.status === 401 || e.status === 403 || e.status === 503);
function errorBlock(e, what) {
  if (refused(e)) return html`<div class="state err" role="alert"><p class="t-h3">${view === 'reports' ? 'These are not yours to read' : 'This is not yours to read'}</p><p>${clean(e.message)}</p></div>`;
  return failed(what, e, { retry: 'load' });
}

/* ---------------- Problem Reports ---------------- */
function reports() {
  const d = D.d;
  const total = d ? d.total : 0, open = d ? d.open : 0, resolved = d ? d.resolved : 0;
  const rows = (d && d.reports) || [];
  const lead = tab === 'resolved'
    ? (!resolved ? 'Nothing resolved yet.' : rows.length < resolved ? `Showing the ${rows.length} most recently resolved of ${resolved}.` : '')
    : (!open && resolved ? 'Nothing open.' : !total ? 'No problem reports yet. When a reader uses Report a Problem, it lands here.' : rows.length < open ? `Showing the newest ${rows.length} of ${open}.` : '');
  return html`<div class="seg" role="group" aria-label="Which reports"><button type="button" data-v2-rp-tab="open" aria-pressed="${tab === 'open'}">Open ${open}</button><button type="button" data-v2-rp-tab="resolved" aria-pressed="${tab === 'resolved'}">Resolved ${resolved}</button></div>
    <div class="cluster rp-lead">${lead ? html`<p class="t-muted">${lead}</p>` : ''}${tab === 'open' && open ? html`<button type="button" class="btn btn-sm" data-v2-rp-all>${armedAll ? `Resolve all ${open}? Press again to confirm` : `Resolve all ${open}`}</button>` : ''}</div>
    ${d.delivery && d.delivery.available === false ? html`<p class="asof">Email delivery is off. ${clean(d.delivery.reason || 'Reports are stored here and not emailed.')}</p>` : ''}
    <ol class="rp-list">${rows.map((r) => html`<li class="rp ${r.resolved_at ? 'is-resolved' : ''}">
      <div class="split"><p class="t-label">Filed ${stamp(r.created_at)}, ${r.emailed ? 'emailed' : 'stored'}</p>
        <button type="button" class="btn btn-sm" data-v2-rp-resolve="${r.id}" data-v2-rp-to="${r.resolved_at ? '0' : '1'}">${r.resolved_at ? 'Reopen' : 'Mark resolved'}</button></div>
      <p class="rp-msg">${r.message}</p>
      <p class="t-muted">${r.reporter_email ? html`From <a href="mailto:${r.reporter_email}">${r.reporter_email}</a>` : 'No account: sent before reports needed one'}</p>
      <p class="asof">${[r.page ? `Page: ${r.page}` : '', r.reply_to ? `Reply to: ${r.reply_to}` : '', r.user_agent || ''].filter(Boolean).join('. ')}</p>
      ${r.resolved_at ? html`<p class="asof">Resolved ${stamp(r.resolved_at)}</p>` : ''}</li>`)}</ol>`;
}

/* ---------------- Claude usage ---------------- */
function usd(b) {
  if (!b) return 'n/a';
  const v = b.cost_usd;
  if (v === null || v === undefined) return 'no price';
  const s = v > 0 && v < 0.005 ? '<$0.01' : `$${v.toFixed(2)}`;
  return b.unpriced ? `${s} + unpriced` : s;
}
function usage() {
  const d = D.d;
  if (d.available === false) return html`<p>${clean(d.reason || 'The usage ledger could not be read.')}</p>`;
  const f = d.features || [], t = d.totals || {}, noKey = D.health && D.health.assistant && D.health.assistant.enabled === false;
  const lead = f.length ? `What the model has cost this deployment, by feature. Recorded since ${stamp(d.since)}.`
    : noKey ? 'No calls recorded. The assistant has no key, so nothing calls Claude and nothing is recorded until it has one.'
      : 'No calls recorded yet. Every call to Claude is recorded here from this deploy on.';
  const row = (label, x) => html`<td>${usd(x.today)}</td><td>${usd(x.week)}</td><td>${usd(x.month)}</td><td class="n">${count((x.month || {}).calls)}</td><td class="n">${count((x.month || {}).unused)}</td><td class="n">${count((x.month || {}).failed)}</td>`;
  return html`<p class="section-sub">${lead}</p>
    ${f.length ? html`<div class="tscroll"><table class="t usage-t"><caption class="sr">Cost by feature</caption><thead><tr><th scope="col">Feature</th><th scope="col">Today</th><th scope="col">7 days</th><th scope="col">30 days</th><th scope="col" class="n" title="Calls in the last 30 days">Calls</th><th scope="col" class="n" title="Answers written but thrown away, 30 days">Unused</th><th scope="col" class="n" title="Calls that failed, 30 days">Failed</th></tr></thead>
      <tbody>${f.map((x) => html`<tr><th scope="row">${x.label || x.feature}</th>${row(x.label, x)}</tr>`)}</tbody>
      <tfoot><tr><th scope="row">Total</th>${row('Total', t)}</tr></tfoot></table></div>` : ''}
    ${d.method ? html`<p class="asof">${clean(d.method)}</p>` : ''}
    ${(d.recent || []).length ? html`<h2 class="t-h2" style="margin-top:32px">Latest calls</h2><div class="tscroll"><table class="t"><thead><tr><th scope="col">When</th><th scope="col">Feature</th><th scope="col">Model</th><th scope="col" class="n">Input</th><th scope="col" class="n">Output</th><th scope="col" class="n">Cost</th><th scope="col">Result</th></tr></thead>
      <tbody>${d.recent.slice(0, 25).map((c) => html`<tr><td>${dayTime(c.at)}</td><td>${c.label || c.feature}</td><td>${c.model || ''}</td><td class="n">${count(c.input_tokens)}</td><td class="n">${count(c.output_tokens)}</td><td class="n">${c.cost_usd === null || c.cost_usd === undefined ? 'no price' : usd({ cost_usd: c.cost_usd })}</td>
        <td title="${c.note || ''}">${c.stop_reason === 'error' ? 'Failed' : c.used === false ? 'Thrown away' : 'Used'}</td></tr>`)}</tbody></table></div>` : ''}`;
}

/* ---------------- Accounts ---------------- */
function accounts() {
  const d = D.d, a = d.accounts || [];
  const lead = d.total ? `${d.total} account${d.total === 1 ? '' : 's'}. ${d.last_7_days} new in the last 7 days, ${d.last_30_days} in the last 30. ${d.verified} with a verified email.` : 'Nobody has made an account yet.';
  const when = (v, absent) => (v === undefined ? absent : v ? stamp(v) : 'Never');
  return html`<p class="section-sub">${lead}</p>
    ${a.length ? html`<div class="tscroll ac-scroll" tabindex="0" role="region" aria-label="Accounts table, scrolls sideways"><table class="t ac-t"><thead><tr><th scope="col">Person</th><th scope="col">Joined</th><th scope="col">Last active</th><th scope="col">Last sign-in</th><th scope="col">Signs in with</th><th scope="col">Status</th></tr></thead>
      <tbody>${a.map((x) => html`<tr><th scope="row"><b>${[x.first_name, x.last_name].filter(Boolean).join(' ') || '(no name)'}</b><br><small class="t-muted ac-mail">${x.email}</small></th>
        <td>${stamp(x.created_at)}</td><td>${when(x.last_active_at, 'Not recorded')}</td><td>${when(x.last_login_at, 'Never')}</td><td>${(x.methods || []).join(', ') || 'None'}</td>
        <td>${x.is_active === false ? 'Deactivated' : x.email_verified ? 'Verified' : 'Not verified'}</td></tr>`)}</tbody></table></div>` : ''}
    <p class="asof">Newest first. Last active is the last time the account used Optic; last sign-in is the last time it entered a password, passkey or provider. No passwords or tokens are shown or kept here.</p>`;
}

/* ---------------- page ---------------- */
function paint() {
  if (!live) return;
  const body = !isOwner() ? notOwner() : D.err ? errorBlock(D.err, view === 'reports' ? 'The reports' : view === 'usage' ? 'The usage ledger' : 'The accounts') : !D.d ? skeleton('rows', 5, 'Loading')
    : view === 'reports' ? reports() : view === 'usage' ? usage() : accounts();
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">${TITLES[view]}</h1>${isOwner() ? groupTabs('reports', view) : ''}</header>
    <section class="section first" aria-label="${TITLES[view]}">${body}</section>`);
}

async function load() {
  const my = ++seq; D.err = null;
  if (!isOwner()) { paint(); return; }
  if (!D.d) paint();
  try {
    let d;
    if (view === 'reports') d = await api.get(`/api/feedback?limit=50&status=${tab}`, { force: true, timeout: 20000 });
    else if (view === 'usage') { [d, D.health] = await Promise.all([api.get('/api/ai/usage', { force: true }), api.get('/api/health', { ttl: 60000 }).catch(() => null)]); }
    else d = await api.get('/api/admin/accounts', { force: true });
    if (my !== seq || !live || !isOwner()) return;
    D.d = d;
  } catch (e) { if (my !== seq) return; D.err = e; D.d = null; }
  paint();
}

export async function render(main, route) {
  live = true; mainEl = main; view = route.view; D = {}; armedAll = null;
  document.title = `${TITLES[view]}, Optic`;
  main.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-rp-tab]'))) { tab = b.dataset.v2RpTab; armedAll = null; D.d = null; load(); return; }
    if ((b = t('[data-v2-rp-resolve]'))) {
      b.disabled = true;
      try { await api.post(`/api/feedback/${encodeURIComponent(b.dataset.v2RpResolve)}/resolve`, { resolved: b.dataset.v2RpTo === '1' }); toast(b.dataset.v2RpTo === '1' ? 'Marked resolved.' : 'Reopened.'); }
      catch (err) { toast(`That did not go through: ${api.explain(err, 'The change')}`); }
      await load(); return;
    }
    if (t('[data-v2-rp-all]')) {
      if (!armedAll) { armedAll = setTimeout(() => { armedAll = null; paint(); }, 5000); paint(); const again = mainEl.querySelector('[data-v2-rp-all]'); if (again) again.focus(); return; }
      clearTimeout(armedAll); armedAll = null;
      try { const r = await api.post('/api/feedback/resolve-all', {}); toast(`Resolved ${r.resolved}.`); } catch (err) { toast(`That did not go through: ${api.explain(err, 'The change')}`); }
      load();
    }
  });
  load();
}
export function dispose() { live = false; clearTimeout(armedAll); }
export const retry = { load: () => load() };
// sign-in or sign-out redraws: the owner check runs again
export function onAuth() { D = {}; load(); }
