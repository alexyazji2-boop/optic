// Links that arrive from email and sign-in providers, read once at boot and
// removed from the address, as static/auth.js handleUrl does:
//   ?verify=<token>      confirm the email address
//   ?reset=<token>       check it, then open the reset form (token kept in memory)
//   ?auth=ok&next=…      back from Google or Apple, signed in
//   ?auth_error=<code>   back from them, not signed in, with the reason
import * as api from './api.js';
import { toast } from '../ui/toast.js';

export const OAUTH_ERRORS = {
  state: 'That sign-in attempt expired before it finished. Start again.',
  provider: 'The sign-in could not be completed. Try again in a moment.',
  config: 'That sign-in method is not set up yet. Sign in with your email and password instead.',
  taken: 'That account is already connected to another Optic Terminal account.',
  needs_link: 'An Optic Terminal account already uses that email address. Sign in the way you did before, then connect this method under Settings, Security. That keeps one account instead of two.',
  no_email: 'No email address was shared, so there is nothing to attach an account to. Try again and choose to share your address, or create an account with an email and password.',
  inactive: 'That account is not active.',
  denied: 'That sign-in was cancelled.',
};
const label = (p) => ({ google: 'Google', apple: 'Apple', email: 'Email' }[p] || (p ? p[0].toUpperCase() + p.slice(1) : ''));
/** The reason words for an error code, naming the provider where the classic app does. */
export function oauthMessage(code, provider) {
  let m = OAUTH_ERRORS[code] || OAUTH_ERRORS.provider;
  if (provider && ['taken', 'needs_link', 'config', 'no_email'].includes(code)) {
    m = m.replace('That account', `That ${label(provider)} account`).replace('this method', label(provider)).replace('No email address', `${label(provider)} shared no email address`);
  }
  return m;
}
function scrub(keys) {
  const url = new URL(location.href);
  keys.forEach((k) => url.searchParams.delete(k));
  history.replaceState(history.state, '', url.pathname + (url.search || '') + url.hash);
}
/** Returns what the app should do next: { reset: token } | { signedIn: true, hash } | { signin: true } | null. */
export async function handleAuthLinks() {
  const p = new URLSearchParams(location.search);
  const verify = p.get('verify');
  if (verify) {
    scrub(['verify']);
    try { await api.post('/api/auth/verify-email', { token: verify }); toast('Email address confirmed.'); return { refresh: true }; }
    catch (e) { toast(e.message && e.message !== 'Request failed' ? e.message : 'That confirmation link is no longer valid.', { kind: 'bad' }); return null; }
  }
  const reset = p.get('reset');
  if (reset) {
    scrub(['reset']);
    let check = null;
    try { check = await api.get(`/api/auth/reset/check?token=${encodeURIComponent(reset)}`, { force: true }); } catch (e) { check = { valid: false, reason: e.message }; }
    if (check && check.valid) return { reset };
    toast((check && check.reason) || 'That reset link is no longer valid.', { kind: 'bad' });
    return null;
  }
  if (p.get('auth') === 'ok') {
    const next = p.get('next') || '';
    scrub(['auth', 'provider', 'next']);
    // next is a same-site path the server only passes when it starts with one slash; the hash is the page
    const hash = next.startsWith('/') && !next.startsWith('//') && next.includes('#') ? next.slice(next.indexOf('#')) : '';
    return { signedIn: true, hash };
  }
  const failed = p.get('auth_error');
  if (failed) {
    const who = p.get('provider') || '';
    scrub(['auth_error', 'provider', 'next']);
    toast(oauthMessage(failed, who), { kind: 'bad' });
    return failed === 'needs_link' ? { signin: true } : null;
  }
  return null;
}
