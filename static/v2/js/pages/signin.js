// Sign in, create an account, forgot password and reset password, against
// the same /api/auth routes as the classic app (static/auth.js): email and
// password, passkeys, and Google or Apple where the deployment has them.
// Reset links (/?reset=…) arrive through core/authlinks.js, which checks the
// token and opens this page in reset mode; the token is held in memory only,
// never put in the address.
import { $, html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { state as store } from '../core/store.js';
import * as passkey from '../core/passkey.js';
import { toast } from '../ui/toast.js';

let mode = 'in', resetToken = '', note = '';
export function startReset(token) { resetToken = token; mode = 'reset'; }

const providers = () => ((store.me || {}).providers) || {};
const policy = () => { const p = (store.me || {}).password_policy; return Array.isArray(p) ? p : p && (p.text || p.summary) ? [p.text || p.summary] : []; };
const policyList = () => (policy().length ? html`<ul class="plain asof si-policy" aria-label="Password rules">${policy().map((x) => html`<li>${x}</li>`)}</ul>` : '');

function providerRow() {
  const pv = providers(), next = encodeURIComponent(`/v2/${location.hash || '#/'}`);
  const pk = passkey.supported() && (pv.passkey || {}).available !== false;
  const items = [
    pk ? html`<button type="button" class="btn si-alt" data-v2-pk-signin>Sign in with a passkey</button>` : '',
    (pv.google || {}).available ? html`<a class="btn si-alt" href="/api/auth/google/start?next=${next}">Continue with Google</a>` : '',
    (pv.apple || {}).available ? html`<a class="btn si-alt" href="/api/auth/apple/start?next=${next}">Continue with Apple</a>` : '',
  ].filter(Boolean);
  if (!items.length) return '';
  return html`<div class="stack si-providers">${items}</div><p class="si-or"><span>or with email</span></p>`;
}

function form() {
  if (mode === 'forgot') {
    return html`<section class="signin" aria-labelledby="si-h"><h1 class="t-display-m" id="si-h">Reset your password</h1>
      <p class="t-muted">Enter the address on the account. If it has a password, a reset link goes to that inbox and works once, for 15 minutes.</p>
      <form class="stack" data-v2-auth="forgot" novalidate><label class="field"><span class="sr">Email</span><input name="email" type="email" autocomplete="email" placeholder="Email" required spellcheck="false"></label>
        <p class="form-error" role="alert" id="si-err"></p>${note ? html`<p class="stale" role="status">${note}</p>` : ''}
        <button type="submit" class="btn btn-primary">Send reset link</button></form>
      <p><button type="button" class="textlink" data-v2-auth-mode="in">Back to sign in</button></p></section>`;
  }
  if (mode === 'reset') {
    return html`<section class="signin" aria-labelledby="si-h"><h1 class="t-display-m" id="si-h">Choose a new password</h1>
      <p class="t-muted">Every signed-in device is signed out when this is done.</p>
      ${resetToken ? html`<form class="stack" data-v2-auth="reset" novalidate>
        <label class="field"><span class="sr">New password</span><input name="password" type="password" autocomplete="new-password" placeholder="New password" required></label>${policyList()}
        <label class="field"><span class="sr">Confirm password</span><input name="confirm" type="password" autocomplete="new-password" placeholder="Confirm password" required></label>
        <p class="form-error" role="alert" id="si-err"></p><button type="submit" class="btn btn-primary">Set password and sign in</button></form>`
        : html`<p>This page opens from the link in a reset email. <button type="button" class="textlink" data-v2-auth-mode="forgot">Send a new link</button></p>`}</section>`;
  }
  const up = mode === 'up';
  return html`<section class="signin" aria-labelledby="si-h">
    <h1 class="t-display-m" id="si-h">${up ? 'Create your account' : 'Sign in to Optic'}</h1>
    <p class="t-muted">${up ? 'Free. Keeps your watchlists and alerts on every device, and opens Milo.' : 'Your watchlists, watches and Milo questions are kept on your account.'}</p>
    ${providerRow()}
    <form class="stack" data-v2-auth="${up ? 'up' : 'in'}" novalidate>
      ${up ? html`<div class="cluster"><label class="field fl"><span class="sr">First name</span><input name="first_name" autocomplete="given-name" placeholder="First name" required></label>
        <label class="field fl"><span class="sr">Last name</span><input name="last_name" autocomplete="family-name" placeholder="Last name"></label></div>` : ''}
      <label class="field"><span class="sr">Email</span><input name="email" type="email" autocomplete="${up ? 'email' : 'username webauthn'}" placeholder="Email" required spellcheck="false"></label>
      <label class="field"><span class="sr">Password</span><input name="password" type="password" autocomplete="${up ? 'new-password' : 'current-password'}" placeholder="Password" required></label>
      ${up ? policyList() : ''}
      ${up ? html`<label class="field"><span class="sr">Confirm password</span><input name="confirm" type="password" autocomplete="new-password" placeholder="Confirm password" required></label>` : ''}
      <label class="check"><input type="checkbox" name="remember" checked> <span>Keep me signed in on this device</span></label>
      <p class="form-error" role="alert" id="si-err"></p>
      <button type="submit" class="btn btn-primary">${up ? 'Create account' : 'Sign in'}</button>
    </form>
    ${up ? html`<p class="t-muted si-agree">By creating an account, with email or with Google or Apple, you agree to the <a class="textlink" href="#/terms">Terms of use</a> and the <a class="textlink" href="#/privacy">Privacy policy</a>.</p>` : html`<p><button type="button" class="textlink" data-v2-auth-mode="forgot">Forgot your password?</button></p>`}
    <p>${up ? html`Have an account? <button type="button" class="textlink" data-v2-auth-mode="in">Sign in</button>` : html`New to Optic? <button type="button" class="textlink" data-v2-auth-mode="up">Create an account</button>`}</p>
  </section>`;
}

const fail = (x, what) => (x.kind === 'limit' ? 'Too many attempts. Wait a minute and try again.' : (x.message && x.message !== 'Request failed' ? x.message : api.explain(x, what)));

export async function render(main, route, app) {
  const p = route.params || {};
  if (p.mode === 'up') mode = 'up'; else if (p.mode === 'forgot') mode = 'forgot'; else if (p.mode === 'reset') mode = 'reset'; else if (mode === 'reset' && !resetToken) mode = 'in';
  note = '';
  const paint = () => { draw(main, form()); const first = $('input', main); if (first && !matchMedia('(pointer: coarse)').matches) first.focus(); };
  paint();
  document.title = `${mode === 'up' ? 'Create an account' : mode === 'forgot' || mode === 'reset' ? 'Reset your password' : 'Sign in'}, Optic`;
  // the destination goes in the address first: settling the account may reload the page
  const done = (said) => { const next = p.next || '#/'; try { history.replaceState(history.state, '', `${location.pathname}${location.search}${next}`); } catch (e) { /* sandboxed */ } api.invalidate('/api/'); return app.settleAuth({ said, next }); };
  main.addEventListener('click', async (e) => {
    const m = e.target.closest('[data-v2-auth-mode]');
    if (m) { mode = m.dataset.v2AuthMode; note = ''; paint(); return; }
    if (e.target.closest('[data-v2-pk-signin]')) {
      const b = e.target.closest('[data-v2-pk-signin]'); b.disabled = true; b.textContent = 'Waiting for your device...';
      const remember = !!(($('input[name=remember]', main) || {}).checked);
      try { await passkey.signIn({ remember }); await done('in'); }
      catch (x) { b.disabled = false; b.textContent = 'Sign in with a passkey'; if (!(x && (x.name === 'NotAllowedError' || x.name === 'AbortError'))) { const err = $('#si-err', main); if (err) err.textContent = fail(x, 'The passkey'); } }
    }
  });
  main.addEventListener('submit', async (e) => {
    const f = e.target.closest('[data-v2-auth]'); if (!f) return;
    e.preventDefault();
    const err = $('#si-err', main); if (err) err.textContent = '';
    const fd = new FormData(f), kind = f.dataset.v2Auth, btn = $('button[type=submit]', f); btn.disabled = true;
    try {
      if (kind === 'in') { await api.post('/api/auth/login', { email: fd.get('email'), password: fd.get('password'), remember: !!fd.get('remember') }); await done('in'); return; }
      if (kind === 'up') {
        if (fd.get('password') !== fd.get('confirm')) throw new api.ApiError('bad', 400, 'Those passwords do not match.');
        const r = await api.post('/api/auth/register', { email: fd.get('email'), first_name: fd.get('first_name'), last_name: fd.get('last_name'), password: fd.get('password'), confirm_password: fd.get('confirm'), remember: !!fd.get('remember') });
        await done('in');
        toast(r && r.mail && r.mail.available === false ? 'Account created. Email is not switched on yet, so no confirmation message was sent.' : r && r.verification_sent === false ? 'Account created, but the confirmation email could not be sent. You can request another from Settings.' : 'Account created. A confirmation link is on its way to your inbox.');
        return;
      }
      if (kind === 'forgot') {
        const r = await api.post('/api/auth/forgot-password', { email: fd.get('email') });
        note = r && r.mail && r.mail.available === false ? 'Email is not switched on yet, so a reset link cannot be sent. Devices already signed in stay signed in.' : (r && r.message) || 'If that address has an account with a password, a reset link is on its way.';
        paint(); return;
      }
      if (kind === 'reset') {
        if (fd.get('password') !== fd.get('confirm')) throw new api.ApiError('bad', 400, 'Those passwords do not match.');
        await api.post('/api/auth/reset-password', { token: resetToken, password: fd.get('password'), confirm_password: fd.get('confirm') });
        resetToken = ''; mode = 'in';
        await done('');
        toast('Password changed, and you are signed in.');
      }
    } catch (x) {
      if (err) err.textContent = fail(x, kind === 'up' ? 'Creating the account' : kind === 'forgot' ? 'The reset link' : kind === 'reset' ? 'The new password' : 'Sign in');
      btn.disabled = false;
      const bad = $('input[name=password]', f) || $('input', f); if (bad) bad.focus();
    }
  });
}
export function dispose() {}
