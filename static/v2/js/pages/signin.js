// Sign in and create an account, against the same /api/auth routes as the
// classic app. Passkeys, Google, Apple and password reset stay in the classic
// sign-in for now, linked from here.
import { $, html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { state as store } from '../core/store.js';

let mode = 'in';

function form() {
  const policy = ((store.me || {}).password_policy || {}).text || ((store.me || {}).password_policy || {}).summary || '';
  return html`<section class="signin" aria-labelledby="si-h">
    <h1 class="t-display-m" id="si-h">${mode === 'in' ? 'Sign in to Optic' : 'Create your account'}</h1>
    <p class="t-muted">${mode === 'in' ? 'Your watchlists, watches and Milo questions are kept on your account.' : 'Free. Keeps your watchlists and alerts on every device, and opens Milo.'}</p>
    <form class="stack" data-v2-auth novalidate>
      ${mode === 'up' ? html`<div class="cluster"><label class="field fl"><span class="sr">First name</span><input name="first_name" autocomplete="given-name" placeholder="First name" required></label>
        <label class="field fl"><span class="sr">Last name</span><input name="last_name" autocomplete="family-name" placeholder="Last name"></label></div>` : ''}
      <label class="field"><span class="sr">Email</span><input name="email" type="email" autocomplete="email" placeholder="Email" required></label>
      <label class="field"><span class="sr">Password</span><input name="password" type="password" autocomplete="${mode === 'in' ? 'current-password' : 'new-password'}" placeholder="Password" required></label>
      ${mode === 'up' && policy ? html`<p class="asof">${policy}</p>` : ''}
      ${mode === 'in' ? html`<label class="check"><input type="checkbox" name="remember" checked> <span>Keep me signed in on this device</span></label>` : ''}
      <p class="form-error" role="alert" id="si-err"></p>
      <button type="submit" class="btn btn-primary">${mode === 'in' ? 'Sign in' : 'Create account'}</button>
    </form>
    <p>${mode === 'in' ? html`New to Optic? <button type="button" class="textlink" data-v2-auth-mode="up">Create an account</button>` : html`Have an account? <button type="button" class="textlink" data-v2-auth-mode="in">Sign in</button>`}</p>
    <p class="asof">Passkeys, Google, Apple and password reset are in the <a href="/">current app's sign-in</a> for now.</p>
  </section>`;
}

export async function render(main, route, app) {
  draw(main, form());
  document.title = 'Sign in, Optic';
  const first = $('input', main); if (first) first.focus();
  main.addEventListener('click', (e) => {
    const m = e.target.closest('[data-v2-auth-mode]');
    if (m) { mode = m.dataset.v2AuthMode; draw(main, form()); const i = $('input', main); if (i) i.focus(); }
  });
  main.addEventListener('submit', async (e) => {
    const f = e.target.closest('[data-v2-auth]'); if (!f) return;
    e.preventDefault();
    const err = $('#si-err', main); err.textContent = '';
    const fd = new FormData(f);
    const btn = $('button[type=submit]', f); btn.disabled = true;
    try {
      if (mode === 'in') await api.post('/api/auth/login', { email: fd.get('email'), password: fd.get('password'), remember: !!fd.get('remember') });
      else await api.post('/api/auth/register', { email: fd.get('email'), first_name: fd.get('first_name'), last_name: fd.get('last_name'), password: fd.get('password'), confirm_password: fd.get('password') });
      api.invalidate('/api/');
      await app.settleAuth({ said: 'in', next: (route.params || {}).next || '#/' });
    } catch (x) {
      err.textContent = x.kind === 'limit' ? 'Too many attempts. Wait a minute and try again.' : (x.message && x.message !== 'Request failed' ? x.message : api.explain(x, 'Sign in'));
      btn.disabled = false;
      const bad = $('input[name=password]', f); if (bad) bad.focus();
    }
  });
}
export function dispose() {}
