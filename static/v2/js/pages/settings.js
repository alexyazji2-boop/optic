// Settings: the account (profile, security, plan, deletion), then this
// browser's preferences (theme, text size, how much to show, time zone), what
// is stored where, and Report a problem. Against the same /api/auth, /api/billing
// and /api/feedback routes as the classic page, and the same device keys
// (core/prefs.js), so a choice made here holds in both apps.
//
// The classic page used browser confirm and prompt dialogs in four places; here each
// is an inline step on the row itself.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import * as prefs from '../core/prefs.js';
import * as passkey from '../core/passkey.js';
import { handDeviceSessionToGuest } from '../core/device.js';
import { clean, billingOff } from '../core/format.js';
import { skeleton } from '../ui/states.js';
import * as drawer from '../ui/drawer.js';
import { toast } from '../ui/toast.js';

let D = {}, live = true, mainEl = null, appRef = null, ui = {};
const me = () => store.state.me || {};
const user = () => store.state.user || {};
const SAFE = /^https:\/\/([a-z0-9-]+\.)*(stripe\.com|snaptrade\.com)\//i;
const GUEST_STORED = 'Theme, time zone, chart preferences, your watchlists and watches, saved research, theses, Milo chats, drawings, notes, Paper Desk trades and any Retirement holdings you entered';
const short = (iso) => (iso ? prefs.stamp(iso) : '');

const row = (title, note, act, tag) => html`<div class="set-row"><div class="set-row-main"><p class="set-row-title">${title}${tag || ''}</p>${note ? html`<p class="set-row-note">${note}</p>` : ''}</div><div class="set-row-act">${act || ''}</div></div>`;
const tag = (on, text) => html` <span class="set-tag ${on ? 'on' : 'off'}">${text}</span>`;
// written out per control, so the dead-controls test can see who reads each attribute
const seg = (label, items, cur, attr) => html`<div class="seg" role="group" aria-label="${label}">${items.map(([v, l]) => (attr === 'theme'
  ? html`<button type="button" data-v2-theme="${v}" aria-pressed="${cur === v}">${l}</button>`
  : html`<button type="button" data-v2-scale="${v}" aria-pressed="${cur === v}">${l}</button>`))}</div>`;

/* ---------------- account ---------------- */
function account() {
  const a = store.state.auth;
  if (a === 'loading') return html`<section class="section first"><h2 class="t-h2">Account</h2><p class="t-muted">Checking...</p></section>`;
  if (a === 'unknown') return html`<section class="section first"><h2 class="t-h2">Account</h2><p>Your sign-in could not be checked just now. Nothing on this device has changed, and it is tried again on its own.</p><button type="button" class="btn btn-sm" data-v2-set-recheck>Try now</button></section>`;
  if (a !== 'user') {
    return html`<section class="section first" aria-labelledby="sa-h"><h2 class="t-h2" id="sa-h">Account</h2>
      <p class="section-sub">Optic works without one. An account keeps your watchlist and your saved research on the server instead of in this browser, so they follow you to another device and survive clearing site data.</p>
      <p><b>Right now everything is stored in this browser.</b> ${GUEST_STORED}. Nothing about you is on the server.</p>
      <div class="cluster"><a class="btn btn-primary" href="#/signin?mode=up">Create an account</a><a class="btn" href="#/signin">Sign in</a></div></section>`;
  }
  const u = user(), m = me(), plan = m.subscription || {}, lim = plan.limits || {};
  return html`<section class="section first" aria-labelledby="sp-h"><h2 class="t-h2" id="sp-h">Profile</h2>
      <div class="set-who"><span class="set-face" aria-hidden="true">${u.avatar_url ? html`<img src="${u.avatar_url}" alt="">` : ((u.first_name || u.email || '?')[0] || '?').toUpperCase()}</span><div><b>${u.name || u.email}</b><br><span class="t-muted">${u.email}</span></div></div>
      <form class="set-row" data-v2-set-profile><div class="set-row-main"><p class="set-row-title">Name</p><p class="set-row-note">Used to address you, nothing else.</p></div>
        <div class="set-row-act set-name"><label class="field field-sm"><span class="sr">First name</span><input name="first_name" value="${u.first_name || ''}" placeholder="First" autocomplete="given-name"></label>
          <label class="field field-sm"><span class="sr">Last name</span><input name="last_name" value="${u.last_name || ''}" placeholder="Last" autocomplete="family-name"></label><button type="submit" class="btn btn-sm">Save</button></div></form>
      ${row('Email address', `${u.email}${u.email_verified ? '' : (m.mail || {}).available === false ? '. Email is not switched on yet, so the confirmation link goes to the server log rather than an inbox.' : '. Check your inbox for the confirmation link.'}`,
        u.email_verified ? '' : html`<button type="button" class="btn btn-sm" data-v2-set-resend>Resend link</button>`, tag(u.email_verified, u.email_verified ? 'Confirmed' : 'Not confirmed'))}
    </section>
    <section class="section" aria-labelledby="ss-h"><h2 class="t-h2" id="ss-h">Security</h2>
      <p class="section-sub">Keep more than one way in. If a device is lost, another method is how you get back to this account, and Optic will not let you remove the last one.</p>
      ${security()}</section>
    <section class="section" aria-labelledby="pl-h"><h2 class="t-h2" id="pl-h">Plan</h2>
      ${row(plan.label || 'Free', html`${lim.watchlists !== undefined ? `${lim.watchlists} watchlists, ${lim.saved_research} saved items, ${lim.ai_calls_per_day} assistant messages a day${lim.ai_calls_per_month ? ` (${lim.ai_calls_per_month} in any 30 days)` : ''}.` : ''}${plan.cancel_at_period_end && plan.current_period_end ? ` Ends on ${prefs.stamp(plan.current_period_end).split(',').slice(0, 2).join(',')}; it will not renew.` : ''}`, billing(), tag(true, plan.status || 'active'))}
      ${D.flash ? html`<p class="stale" role="status">${D.flash}</p>` : ''}
      ${D.brokerage ? row('Linked brokerages', 'Read-only connections, what they can see, and how to disconnect or delete the data.', html`<a class="btn btn-sm" href="#/brokerage/connections">Manage</a>`) : ''}</section>
    <section class="section set-danger" aria-labelledby="dl-h"><h2 class="t-h2" id="dl-h">Delete account</h2>
      <p>Removes the account and everything kept on it: watchlists, watches, saved research, theses, valuation scenarios, signal history, preferences, connected sign-in methods and every session. It cannot be undone. Problem reports you sent are kept with the address they came from, so a reply can still reach you, and the shared paper-trading ledger is not affected because it was never yours.</p>
      <p>A paid plan is cancelled at the same moment, and any linked brokerage is disconnected at the provider with Optic's copy of its data deleted.</p>
      ${ui.deleting ? html`<form class="stack set-del" data-v2-set-delete><p><b>This cannot be undone.</b></p>
          <label class="field"><span class="t-label">Type ${u.email} to confirm</span><input name="confirm_email" type="email" required autocomplete="off"></label>
          ${(m.methods || {}).password ? html`<label class="field"><span class="t-label">Your password</span><input name="password" type="password" required autocomplete="current-password"></label>` : ''}
          <p class="form-error" role="alert">${ui.delErr || ''}</p>
          <div class="cluster"><button type="submit" class="btn btn-danger">Delete the account</button><button type="button" class="btn" data-v2-set-del-cancel>Cancel</button></div></form>`
        : html`<button type="button" class="btn btn-danger" data-v2-set-del>Delete this account</button>`}</section>`;
}

function billing() {
  const b = D.billing;
  if (b === undefined) return html`<span class="t-muted">Checking plans...</span>`;
  if (!b || !b.available) return html`<span class="set-row-note">${billingOff((b || {}).reason, !!(store.state.me && store.state.me.admin))}</span>`;
  const pro = ((b.subscription || me().subscription || {}).plan || '') === 'pro';
  const test = b.mode === 'test' ? tag(false, 'Test mode') : '';
  if (pro) return b.can_manage ? html`<button type="button" class="btn btn-sm" data-v2-billing="portal">Manage billing</button>${test}` : html`<span class="set-row-note">Pro, granted by the operator.</span>`;
  return html`<button type="button" class="btn btn-sm btn-primary" data-v2-billing="checkout">Upgrade to Pro, ${b.price_label || ''}</button>${b.can_manage ? html`<button type="button" class="btn btn-sm" data-v2-billing="portal">Billing history</button>` : ''}${test}`;
}

function security() {
  const s = D.sec;
  if (s === undefined) return skeleton('lines', 3, 'Loading your sign-in methods');
  if (s && s.error) return html`<p class="stale">Could not load your sign-in methods: ${api.explain(s.error, 'The list')}</p>`;
  const ids = s.identities || {}, methods = ids.methods || me().methods || {}, only = (methods.count || 0) <= 1;
  const lastTitle = 'This is the only way into this account. Add another method before removing it.';
  const pw = !!methods.password, provs = me().providers || {}, connected = (ids.identities || []);
  const keys = ids.passkeys || [];
  const remove = (what, label) => (ui.arm === what
    ? html`<button type="button" class="btn btn-sm btn-danger" data-v2-sec-do="${what}">${label}</button><button type="button" class="btn btn-sm" data-v2-sec-disarm>Keep</button>`
    : html`<button type="button" class="btn btn-sm" data-v2-sec-arm="${what}" ${only ? html`disabled title="${lastTitle}"` : ''}>${what.startsWith('passkey:') ? 'Remove' : what === 'provider:email' ? 'Remove' : 'Disconnect'}</button>`);
  return html`<h3>Password</h3>
    ${row('Email and password', pw ? 'Changing it signs out every other device.' : 'This account signs in without one. You can add a password if you want a fallback.',
      html`<button type="button" class="btn btn-sm" data-v2-pw-toggle aria-expanded="${!!ui.pw}">${pw ? 'Change' : 'Add a password'}</button>${pw ? remove('provider:email', 'Remove the password') : ''}`, tag(pw, pw ? 'Set' : 'Not set'))}
    ${ui.pw ? html`<form class="stack set-pw" data-v2-pw-form>${pw ? html`<label class="field"><span class="t-label">Current password</span><input name="current_password" type="password" autocomplete="current-password" required></label>` : ''}
        <label class="field"><span class="t-label">New password</span><input name="new_password" type="password" autocomplete="new-password" required></label>
        <label class="field"><span class="t-label">Confirm new password</span><input name="confirm_password" type="password" autocomplete="new-password" required></label>
        ${(me().password_policy || []).length ? html`<p class="asof">${[].concat(me().password_policy).map((x) => (typeof x === 'string' ? x : x.text || '')).join(' ')}</p>` : ''}
        <p class="form-error" role="alert">${ui.pwErr || ''}</p><div class="cluster"><button type="submit" class="btn btn-primary btn-sm">Save password</button><button type="button" class="btn btn-sm" data-v2-pw-toggle>Cancel</button></div></form>` : ''}
    <h3>Passkeys <span class="t-muted">${keys.length}</span></h3><p class="set-row-note">Face ID, Touch ID, Windows Hello or a security key: sign in with the device instead of a password.</p>
    ${keys.length ? keys.map((k) => row(k.name || 'Passkey', `Added ${short(k.created_at)}. ${k.last_used_at ? `Last used ${short(k.last_used_at)}.` : 'Not used yet.'}`,
      ui.rename === k.id ? html`<form class="cluster" data-v2-pk-rename="${k.id}"><label class="field field-sm"><span class="sr">New name for this passkey</span><input name="name" value="${k.name || ''}" maxlength="60" required></label><button type="submit" class="btn btn-sm">Save</button><button type="button" class="btn btn-sm" data-v2-pk-rename-cancel>Cancel</button></form>`
        : html`<button type="button" class="btn btn-sm" data-v2-pk-rename-open="${k.id}">Rename</button>${remove(`passkey:${k.id}`, 'Remove the passkey')}`, tag(!!k.backed_up, k.backed_up ? 'Synced' : 'This device'))) : html`<p class="t-muted">None yet.</p>`}
    ${ui.arm && ui.arm.startsWith('passkey:') ? html`<p class="stale">The device it lives on will no longer sign you in.</p>` : ''}
    <button type="button" class="btn btn-sm" data-v2-pk-add ${passkey.supported() ? '' : html`disabled title="This browser does not support passkeys."`}>${ui.pkBusy ? 'Waiting for your device...' : 'Add a passkey'}</button>
    <h3>Connected accounts</h3>
    ${['google', 'apple'].map((p) => { const c = connected.find((x) => x.provider === p), av = (provs[p] || {}).available, name = p === 'google' ? 'Google' : 'Apple';
      return row(name, c ? `${c.email || ''} Connected ${short(c.connected_at)}.` : av ? `Sign in with ${name} as well as, or instead of, a password.` : clean((provs[p] || {}).reason || ''),
        c ? remove(`provider:${p}`, `Disconnect ${name}`) : av ? html`<a class="btn btn-sm" href="/api/auth/${p}/start?link=1&next=${encodeURIComponent(location.pathname)}">Connect</a>` : '',
        tag(!!c, c ? 'Connected' : av ? 'Not connected' : 'Unavailable')); })}
    <h3>Active sessions</h3>
    ${(s.sessions || []).length ? (ui.allSess ? s.sessions : s.sessions.slice(0, 5)).map((x) => row(x.label || 'A browser', `Last used ${short(x.last_used_at)}${x.ip_address ? ` from ${x.ip_address}` : ''}. Signed in ${short(x.created_at)}.`,
      html`<button type="button" class="btn btn-sm" data-v2-sess="${x.id}" data-v2-sess-here="${x.current ? '1' : ''}">${x.current ? 'Sign out' : 'Revoke'}</button>`, x.current ? tag(true, 'This device') : '')) : html`<p class="t-muted">None.</p>`}
    ${(s.sessions || []).length > 5 ? html`<button type="button" class="textlink" data-v2-sess-all aria-expanded="${!!ui.allSess}">${ui.allSess ? 'Show the five most recent' : `Show all ${s.sessions.length} sessions`}</button>` : ''}
    ${ui.arm === 'everywhere' ? html`<div class="cluster"><button type="button" class="btn btn-sm btn-danger" data-v2-sec-do="everywhere">Sign out everywhere, including here</button><button type="button" class="btn btn-sm" data-v2-sec-disarm>Keep</button></div>`
      : html`<button type="button" class="btn btn-sm" data-v2-sec-arm="everywhere">Sign out of all devices</button>`}`;
}

/* ---------------- preferences ---------------- */
function preferences() {
  const tz = prefs.timezone(), z = prefs.zone(), onMarket = z === 'America/New_York';
  const now = new Date();
  // one row a phase; overnight's two halves (8 pm to midnight, midnight to 4 am) join into one
  const segs = [];
  ((D.session || {}).segments || []).forEach((g) => {
    const had = segs.find((x) => x.phase === g.phase);
    if (had) Object.assign(had, { start_at: g.start_at, active: had.active || g.active });
    else segs.push({ ...g });
  });
  return html`<section class="section" aria-labelledby="ap-h"><h2 class="t-h2" id="ap-h">Appearance</h2>
      <p class="section-sub">Both themes are hand-picked rather than one flipped into the other, so contrast and colour-vision separation hold either way.</p>
      ${row('Theme', 'Dark is the default. "Follow system" tracks your operating system setting and changes with it.', seg('Theme', [['dark', 'Dark'], ['light', 'Light'], ['system', 'Follow system']], prefs.theme(), 'theme'))}</section>
    <section class="section" aria-labelledby="ts-h"><h2 class="t-h2" id="ts-h">Text size</h2>
      <p class="section-sub">Scales the whole interface, type and spacing together, so the proportions stay as they are and only the size changes.</p>
      ${row('Size', 'Default is 15% larger than the terminal shipped with. Compact is that original density, for a small screen or a reader who wants more on it at once.', seg('Text size', [['compact', 'Compact'], ['default', 'Default'], ['large', 'Large']], prefs.scale(), 'scale'))}</section>
    <section class="section" aria-labelledby="hm-h"><h2 class="t-h2" id="hm-h">How much to show</h2>
      <p class="section-sub">Off, every page leads with plain-language summaries and the specialist panels start folded, one press from open. On, those panels start open with their full terminology and methodology. Every panel is on the page either way.</p>
      ${row('Advanced analysis', 'The same setting as Optic Mode in the Milo panel: on is Advanced or Professional, off is Simple, Financially Literate or Adaptive. Turning it off returns you to the level you had chosen.',
        html`<label class="switch"><input type="checkbox" role="switch" data-v2-adv ${prefs.advancedOn() ? 'checked' : ''}> <span>Show advanced analysis</span></label>`)}</section>
    <section class="section" aria-labelledby="tz-h"><h2 class="t-h2" id="tz-h">Time zone</h2>
      <p class="section-sub"><b>US market hours are defined in Eastern Time and don't move.</b> This setting only changes the clock they're displayed against, so you can see when the open and close land where you are.</p>
      ${row('Show times in', `Currently ${z} (${prefs.zoneAbbrev(z)})${onMarket ? '. The same as market time, so nothing is converted.' : '.'}`,
        html`<label class="select"><span class="sr">Show times in</span><select data-v2-tz>${prefs.TIMEZONES.map((x) => html`<option value="${x.id}" ${x.id === tz ? 'selected' : ''}>${x.label}, ${prefs.clock(now.toISOString(), x.id === 'auto' ? undefined : x.id)}</option>`)}</select></label>`)}
      ${segs.length ? html`<h3>Market hours</h3><div class="tscroll"><table class="t narrow"><thead><tr><th scope="col">Session</th><th scope="col">Eastern (market)</th>${onMarket ? '' : html`<th scope="col">Your zone (${prefs.zoneAbbrev(z)})</th>`}</tr></thead>
        <tbody>${segs.map((g) => html`<tr class="${g.active ? 'is-now' : ''}"><td><span class="ses-dot p-${g.phase}" aria-hidden="true"></span>${g.label}${g.active ? html` <b>now</b>` : ''}</td><td>${prefs.clock(g.start_at, 'America/New_York')} to ${prefs.clock(g.end_at, 'America/New_York')} ET</td>${onMarket ? '' : html`<td>${prefs.clock(g.start_at, z)} to ${prefs.clock(g.end_at, z)}</td>`}</tr>`)}</tbody></table></div>
        <p class="asof">Overnight straddles midnight, so its two halves share one row. Daylight saving shifts these by an hour on different dates in different countries; the conversion follows each zone's own calendar rather than assuming a fixed offset.</p>`
        : D.session === undefined ? skeleton('lines', 2, 'Loading market hours') : html`<p class="t-muted">Market hours could not be read just now.</p>`}</section>`;
}

function about() {
  const h = D.health, signed = store.signedIn();
  const feed = (p) => ({ yfinance: 'Yahoo Finance', yahoo: 'Yahoo Finance', tradier: 'Tradier' }[String(p || 'yfinance').toLowerCase()] || p);
  const rows = [
    ['Data source', h && h.realtime_chain ? `Real-time option chains via ${feed(h.provider)}; other quotes may be delayed` : 'Yahoo Finance. Quotes delayed roughly 15 minutes'],
    ['Assistant', !h ? 'Checking…' : (h.assistant || {}).enabled ? 'Milo is configured and answering' : 'Milo is switched off in this build'],
    ['Optic Portfolio', 'One shared simulated ledger, no real money'],
    ['Stored on this device', signed ? 'Theme, time zone, chart preferences, recent symbols, Milo chats, drawings, notes, Paper Desk trades and Retirement holdings' : GUEST_STORED],
    ['Stored on the server', signed ? 'Your account: name, email, watchlists, watches, saved research, theses, valuation scenarios, signal history, preferences and sessions' : 'Nothing about you'],
  ];
  return html`<section class="section" aria-labelledby="ab-h"><h2 class="t-h2" id="ab-h">About this build</h2>
      <dl class="reads-dl">${rows.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl>
      <p class="asof">${signed ? 'Appearance and chart preferences live in this browser. Your watchlist and saved research live on your account, so clearing site data does not lose them. Recent symbols, Milo chats, drawings and notes stay in this browser, kept apart for each account, and signing out puts yours away until you sign in here again.' : 'Settings live in this browser only. Clearing site data resets them.'}</p></section>
    <section class="section" aria-labelledby="rp-h"><h2 class="t-h2" id="rp-h">Report a problem</h2>
      <p class="section-sub">Found something wrong, confusing, or missing? Tell us and it gets looked at. The build, the page you were on and your window size are attached, so you only need to say what happened.</p>
      <button type="button" class="btn" data-v2-report>Report a problem</button>
      <p class="asof">Goes to the person who maintains the terminal, with your account's address so they can write back.</p></section>`;
}

/* ---------------- Report a problem ---------------- */
export function openReport(opener, from = 'Settings') {
  if (!store.signedIn()) {
    drawer.open({ kicker: 'Report a problem', title: 'Sign in to report a problem', opener, body: html`<p>Sign in to report a problem, so we can write back to you.</p><a class="btn btn-primary" href="#/signin">Sign in</a>` });
    return;
  }
  drawer.open({ kicker: 'Report a problem', title: 'What went wrong?', opener, keep: true, body: html`<form class="stack" data-v2-report-form>
      <label class="field"><span class="sr">What went wrong?</span><textarea name="message" rows="7" maxlength="2000" required placeholder="What you did, what you expected, what happened instead."></textarea></label>
      <p class="asof" data-v2-report-left></p><p class="form-error" role="alert" data-v2-report-err></p>
      <div class="cluster"><button type="submit" class="btn btn-primary">Send</button><button type="button" class="btn" data-v2-report-cancel>Cancel</button></div>
      <p class="asof">Sent from ${user().email}.</p></form>` });
  const f = document.querySelector('[data-v2-report-form]'); if (!f) return;
  const ta = f.message; ta.focus();
  const send = async () => {
    const text = ta.value.trim(); if (!text) return;
    const ctx = `Build v2 | Page ${location.hash || '#/'} | From ${from} | Window ${innerWidth}x${innerHeight}`;
    try { const r = await api.post('/api/feedback', { message: `${text}\n\n${ctx}`, page: location.hash || '#/' }); drawer.close({ force: true }); toast(r && r.emailed === false ? 'Saved. It is on the server and will be passed on.' : 'Sent. Thank you.'); }
    catch (e) { if (e.status === 401) { drawer.close({ force: true }); openReport(opener, from); return; } f.querySelector('[data-v2-report-err]').textContent = `That did not send. ${api.explain(e, 'The report')}`; }
  };
  ta.addEventListener('input', () => { const left = 2000 - ta.value.length; f.querySelector('[data-v2-report-left]').textContent = left <= 300 ? `${left} left` : ''; });
  ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send(); } });
  f.addEventListener('submit', (e) => { e.preventDefault(); send(); });
  f.querySelector('[data-v2-report-cancel]').addEventListener('click', () => drawer.close({ force: true }));
}

/* ---------------- page ---------------- */
function paint() {
  if (!live) return;
  const y = window.scrollY;
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">Settings</h1></header>${account()}${preferences()}${about()}`);
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
}

async function loadSecurity() {
  if (!store.signedIn()) return;
  try { const [identities, sessions] = await Promise.all([api.get('/api/auth/identities', { force: true }), api.get('/api/auth/sessions', { force: true })]); D.sec = { identities, sessions: sessions.sessions || [] }; }
  catch (e) { D.sec = { error: e }; }
  paint();
}
function loadAll() {
  D.sec = undefined; D.billing = undefined;
  paint();
  if (store.signedIn()) {
    loadSecurity();
    api.get('/api/billing/status', { force: true }).then((b) => { D.billing = b; }, () => { D.billing = null; }).finally(paint);
    api.get('/api/brokerage/status', { ttl: 60000 }).then((b) => { D.brokerage = !!(b && b.available); paint(); }, () => {});
  }
  api.get('/api/session', { ttl: 60000 }).then((s) => { D.session = s; }, () => { D.session = null; }).finally(paint);
  api.get('/api/health', { ttl: 60000 }).then((h) => { D.health = h; }, () => { D.health = null; }).finally(paint);
}

export async function render(main, route, app) {
  live = true; mainEl = main; appRef = app; D = {}; ui = {};
  document.title = 'Settings, Optic';
  // the classic billing return lands with ?billing=; say what happened, then drop it
  const q = new URLSearchParams(location.search), bill = q.get('billing') || (route.params || {}).billing;
  if (bill) {
    D.flash = bill === 'success' ? 'Thanks. Your plan updates as soon as the payment provider confirms it, usually within a minute.' : 'Checkout cancelled. Nothing was charged.';
    q.delete('billing'); history.replaceState(null, '', `${location.pathname}${q.toString() ? `?${q}` : ''}#/settings`);
  }
  wire(main);
  loadAll();
}
export function dispose() { live = false; }
export function onAuth() { if (live) loadAll(); }

async function act(fn, ok) { try { const r = await fn(); if (ok) toast(typeof ok === 'function' ? ok(r) : ok); return r; } catch (e) { toast(api.explain(e, 'The change'), { kind: 'bad' }); return null; } }

function wire(main) {
  main.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-theme]'))) { prefs.setTheme(b.dataset.v2Theme); paint(); return; }
    if ((b = t('[data-v2-scale]'))) { prefs.setScale(b.dataset.v2Scale); paint(); const again = mainEl.querySelector(`[data-v2-scale="${b.dataset.v2Scale}"]`); if (again) again.focus(); return; }
    if (t('[data-v2-report]')) { openReport(t('[data-v2-report]')); return; }
    if (t('[data-v2-set-recheck]')) { await store.loadMe(); if (appRef) appRef.settleAuth(); return; }
    if (t('[data-v2-set-resend]')) { await act(() => api.post('/api/auth/resend-verification', {}), (r) => (r && r.already_verified ? 'This address is already confirmed.' : r && r.mail && r.mail.available === false ? 'Email is not configured here, so the link went to the server log.' : 'A new confirmation link is on its way.')); return; }
    if ((b = t('[data-v2-billing]'))) {
      const r = await act(() => api.post(`/api/billing/${b.dataset.v2Billing === 'portal' ? 'portal' : 'checkout'}`, {}));
      if (r && r.url && SAFE.test(r.url)) location.href = r.url; else if (r) toast('Billing is not available right now.', { kind: 'bad' });
      return;
    }
    if (t('[data-v2-set-del]')) { ui.deleting = true; ui.delErr = ''; paint(); const i = mainEl.querySelector('[data-v2-set-delete] input'); if (i) i.focus(); return; }
    if (t('[data-v2-set-del-cancel]')) { ui.deleting = false; paint(); const back = mainEl.querySelector('[data-v2-set-del]'); if (back) back.focus(); return; }
    if (t('[data-v2-pw-toggle]')) { ui.pw = !ui.pw; ui.pwErr = ''; paint(); const i = mainEl.querySelector('[data-v2-pw-form] input'); if (i) i.focus(); return; }
    if ((b = t('[data-v2-sec-arm]'))) { ui.arm = b.dataset.v2SecArm; paint(); const d = mainEl.querySelector('[data-v2-sec-do]'); if (d) d.focus(); return; }
    if (t('[data-v2-sec-disarm]')) { ui.arm = null; paint(); return; }
    if ((b = t('[data-v2-sec-do]'))) {
      const what = b.dataset.v2SecDo; ui.arm = null;
      if (what === 'everywhere') { const r = await act(() => api.post('/api/auth/logout-all', {}), 'Signed out on every device.'); if (r && appRef) appRef.settleAuth({ next: '#/' }); return; }
      if (what.startsWith('passkey:')) await act(() => api.del(`/api/auth/passkeys/${encodeURIComponent(what.slice(8))}`), 'Passkey removed.');
      else if (what.startsWith('provider:')) await act(() => api.del(`/api/auth/identities/${what.slice(9)}`), what === 'provider:email' ? 'Password removed.' : 'Disconnected.');
      await store.loadMe(); loadSecurity(); return;
    }
    if ((b = t('[data-v2-pk-rename-open]'))) { ui.rename = b.dataset.v2PkRenameOpen; paint(); const i = mainEl.querySelector('[data-v2-pk-rename] input'); if (i) i.select(); return; }
    if (t('[data-v2-pk-rename-cancel]')) { ui.rename = null; paint(); return; }
    if (t('[data-v2-pk-add]')) {
      ui.pkBusy = true; paint();
      try { const r = await passkey.create(''); toast(`Saved "${(r && (r.passkey || {}).name) || 'passkey'}".`); await store.loadMe(); }
      catch (err) { if (!(err && err.name === 'NotAllowedError')) toast(err.message && !(err instanceof api.ApiError) ? err.message : api.explain(err, 'The passkey'), { kind: 'bad' }); }
      ui.pkBusy = false; loadSecurity(); return;
    }
    if (t('[data-v2-sess-all]')) { ui.allSess = !ui.allSess; paint(); return; }
    if ((b = t('[data-v2-sess]'))) {
      const here = b.dataset.v2SessHere === '1';
      const r = await act(() => api.del(`/api/auth/sessions/${encodeURIComponent(b.dataset.v2Sess)}`), here ? null : 'Session revoked.');
      if (r !== null && here && appRef) { appRef.settleAuth({ said: 'out', next: '#/' }); return; }
      loadSecurity();
    }
  });
  main.addEventListener('change', (e) => {
    const t = e.target;
    if (t.matches('[data-v2-tz]')) { prefs.setTimezone(t.value); paint(); const s = mainEl.querySelector('[data-v2-tz]'); if (s) s.focus(); return; }
    if (t.matches('[data-v2-adv]')) { prefs.setAdvanced(t.checked); toast(t.checked ? 'Advanced analysis on.' : 'Advanced analysis off.'); }
  });
  main.addEventListener('submit', async (e) => {
    const f = e.target; e.preventDefault();
    if (f.matches('[data-v2-set-profile]')) {
      const r = await act(() => api.patch('/api/auth/profile', { first_name: f.first_name.value.trim(), last_name: f.last_name.value.trim() }), 'Profile saved.');
      if (r) { await store.loadMe(); paint(); }
      return;
    }
    if (f.matches('[data-v2-pw-form]')) {
      try {
        const r = await api.post('/api/auth/change-password', { current_password: f.current_password ? f.current_password.value : '', new_password: f.new_password.value, confirm_password: f.confirm_password.value });
        ui.pw = false; toast(r && r.other_sessions_ended !== undefined ? `Password changed. ${r.other_sessions_ended} other session${r.other_sessions_ended === 1 ? '' : 's'} signed out.` : 'Password changed.'); await store.loadMe(); loadSecurity();
      } catch (err) { ui.pwErr = err.message && err.kind === 'bad' ? err.message : api.explain(err, 'The password'); paint(); }
      return;
    }
    if (f.matches('[data-v2-pk-rename]')) {
      const id = f.dataset.v2PkRename; ui.rename = null;
      await act(() => api.patch(`/api/auth/passkeys/${encodeURIComponent(id)}`, { name: f.name.value.trim() }), 'Passkey renamed.'); loadSecurity(); return;
    }
    if (f.matches('[data-v2-set-delete]')) {
      try {
        await api.post('/api/auth/delete-account', { confirm_email: f.confirm_email.value.trim(), password: f.password ? f.password.value : '' });
        handDeviceSessionToGuest(); toast('Account deleted. The terminal stays open.');
        if (appRef) appRef.settleAuth({ next: '#/' });
      } catch (err) { ui.delErr = err.message && err.kind === 'bad' ? err.message : api.explain(err, 'Deleting the account'); paint(); }
    }
  });
}
