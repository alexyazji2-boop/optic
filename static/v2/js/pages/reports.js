// Reports, the owner's four pages: Problem Reports (/api/feedback), Claude
// usage (/api/ai/usage), Accounts (/api/admin/accounts) and Metrics
// (/api/admin/metrics, counted in app/metrics.py). Owner only: the
// group shows only when /api/auth/me says admin, each page checks again before
// and after it fetches, and the server enforces it on every request. Nothing
// here calls a model.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { clean, shortDate, fullDate } from '../core/format.js';
import { stamp, dayTime } from '../core/prefs.js';
import { skeleton, failed, how } from '../ui/states.js';
import { toast } from '../ui/toast.js';
import { groupTabs } from './tabs.js';

const TITLES = { reports: 'Problem Reports', usage: 'Claude usage', accounts: 'Accounts', metrics: 'Metrics' };
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

/* ---------------- Metrics ---------------- */
const pct = (v) => (v === null || v === undefined ? '' : `${Math.round(Number(v))}%`);
function metrics() {
  const d = D.d, a = d.accounts || {}, weeks = d.weeks || [], cohorts = (d.retention || {}).cohorts || [];
  const q = d.questions || {}, kinds = q.by_kind || [], calls = d.model_calls || {}, since = d.tracking_since;
  const left = d.owners_left_out ? ` Your own account${d.owners_left_out === 1 ? ' is' : 's are'} left out of every count.` : '';
  const lead = a.total ? `${count(a.total)} account${a.total === 1 ? '' : 's'}: ${count(a.active_7_days)} used Optic in the last 7 days and ${count(a.active_30_days)} in the last 30.${left}`
    : `Nobody but you has made an account yet.${left}`;
  const wk = (w) => `${shortDate(w.week_start)}${w.partial ? ', so far' : ''}`;
  const active = (w) => (w.active_accounts === null || w.active_accounts === undefined ? html`<span class="t-muted">Not recorded</span>`
    : html`${count(w.active_accounts)}${w.active_from ? html` <small class="t-muted">from ${shortDate(w.active_from)}</small>` : ''}`);
  const shown = weeks.slice().reverse(), recent = cohorts.slice().reverse();
  const anyQ = kinds.some((k) => k.all);
  return html`<p class="section-sub">${lead}</p>
    <dl class="kv mt-kv"><div><dt>Accounts</dt><dd>${count(a.total)}</dd></div><div><dt>Active, 7 days</dt><dd>${count(a.active_7_days)}</dd></div><div><dt>Active, 30 days</dt><dd>${count(a.active_30_days)}</dd></div><div><dt>Verified email</dt><dd>${count(a.verified)}</dd></div></dl>

    <h2 class="t-h2 mt-h">Sign-ups and weekly active accounts</h2>
    <p class="asof">Weeks start on Monday (UTC). An active account opened Optic while signed in that week.${since ? ` Weekly actives are recorded from ${fullDate(since)}; earlier weeks were not kept.` : ''}</p>
    <div class="tscroll"><table class="t mt-t"><caption class="sr">Sign-ups and active accounts by week, newest first</caption><thead><tr><th scope="col">Week of</th><th scope="col" class="n">Sign-ups</th><th scope="col" class="n">Verified</th><th scope="col" class="n">Active accounts</th></tr></thead>
      <tbody>${shown.map((w) => html`<tr><th scope="row">${wk(w)}</th><td class="n">${count(w.signups)}</td><td class="n">${count(w.verified)}</td><td class="n">${active(w)}</td></tr>`)}</tbody></table></div>

    <h2 class="t-h2 mt-h">Came back after four weeks</h2>
    <p class="asof">For each sign-up week: of the accounts at least ${count((d.retention || {}).days || 28)} days old, how many used Optic again ${count((d.retention || {}).days || 28)} days or more after signing up.</p>
    <div class="tscroll"><table class="t mt-t"><caption class="sr">Four-week retention by sign-up week, newest first</caption><thead><tr><th scope="col">Week of</th><th scope="col" class="n">Sign-ups</th><th scope="col" class="n">Old enough</th><th scope="col" class="n">Came back</th></tr></thead>
      <tbody>${recent.map((c) => html`<tr><th scope="row">${shortDate(c.week_start)}</th><td class="n">${count(c.signups)}</td><td class="n">${count(c.measurable)}</td><td class="n">${c.measurable ? html`${count(c.retained)} <small class="t-muted mt-new">(${pct(c.retained_pct)})</small>` : c.signups ? html`<span class="t-muted mt-new">Too new</span>` : ''}</td></tr>`)}</tbody></table></div>

    <h2 class="t-h2 mt-h">Questions to Milo</h2>
    <p class="asof">One per question sent, wherever it was asked${since ? `, counted from ${fullDate(since)}` : ''}. In the last 7 days, ${count(q.askers_7_days)} account${q.askers_7_days === 1 ? '' : 's'} asked, and guests asked ${count(q.guest_questions_7_days)}.${q.owner_questions_left_out ? ` Your own ${q.owner_questions_left_out === 1 ? 'question is' : `${count(q.owner_questions_left_out)} questions are`} left out.` : ''}</p>
    ${anyQ ? html`<div class="tscroll"><table class="t mt-t"><caption class="sr">Questions to Milo by where they were asked</caption><thead><tr><th scope="col">Asked through</th><th scope="col" class="n">7 days</th><th scope="col" class="n">30 days</th><th scope="col" class="n">Since counting began</th></tr></thead>
      <tbody>${kinds.map((k) => html`<tr><th scope="row">${k.label}</th><td class="n">${count(k.last_7_days)}</td><td class="n">${count(k.last_30_days)}</td><td class="n">${count(k.all)}</td></tr>`)}</tbody></table></div>` : html`<p>No questions counted yet.</p>`}

    ${calls.available === false ? html`<p class="asof">${clean(calls.reason || 'The usage ledger could not be read.')}</p>` : (calls.features || []).length ? html`<h3 class="t-h3 mt-h3">Model calls by feature</h3>
      <p class="asof">Calls to Claude, not questions: one Milo answer can take several, and the Read and the desk write on a schedule. These include your own use. Costs are on Claude usage.</p>
      <div class="tscroll"><table class="t mt-t"><caption class="sr">Model calls by feature</caption><thead><tr><th scope="col">Feature</th><th scope="col" class="n">7 days</th><th scope="col" class="n">30 days</th></tr></thead>
        <tbody>${calls.features.map((f) => html`<tr><th scope="row">${f.label}</th><td class="n">${count(f.last_7_days)}</td><td class="n">${count(f.last_30_days)}</td></tr>`)}</tbody></table></div>` : ''}

    <h2 class="t-h2 mt-h">Plans</h2>
    <div class="tscroll"><table class="t mt-t"><caption class="sr">Accounts by plan</caption><thead><tr><th scope="col">Plan</th><th scope="col" class="n">Accounts</th></tr></thead>
      <tbody>${(d.plans || []).map((p) => html`<tr><th scope="row">${p.label}</th><td class="n">${count(p.accounts)}</td></tr>`)}</tbody></table></div>
    ${how(html`<p>Everything here is counted from Optic's own database. Nothing is sent to an analytics service, and nothing records which pages were viewed or what was asked.</p>
      <p>An account counts as active on a day it loaded Optic while signed in, or signed in. Visitors who never sign in are not counted, except as guest questions to Milo.</p>
      <p>The plan is the one Optic's limits read: a lapsed subscription counts as Free.</p>`)}
    <p class="asof">Counted ${stamp(d.generated_at)}.</p>`;
}

/* ---------------- page ---------------- */
function paint() {
  if (!live) return;
  const what = { reports: 'The reports', usage: 'The usage ledger', accounts: 'The accounts', metrics: 'The metrics' }[view];
  const body = !isOwner() ? notOwner() : D.err ? errorBlock(D.err, what) : !D.d ? skeleton('rows', 5, 'Loading')
    : view === 'reports' ? reports() : view === 'usage' ? usage() : view === 'metrics' ? metrics() : accounts();
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
    else if (view === 'metrics') d = await api.get('/api/admin/metrics', { force: true });
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
