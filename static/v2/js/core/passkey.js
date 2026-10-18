// Registering a passkey from Settings, as the classic auth.js does: options
// from the server, the browser's own prompt, then the server verifies.
import * as api from './api.js';

const fromB64 = (v) => { let s = String(v || '').replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '='; const raw = atob(s); const b = new Uint8Array(raw.length); for (let i = 0; i < raw.length; i += 1) b[i] = raw.charCodeAt(i); return b; };
const toB64 = (buf) => { const b = new Uint8Array(buf); let out = ''; for (let i = 0; i < b.length; i += 1) out += String.fromCharCode(b[i]); return btoa(out).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); };

export const supported = () => !!(window.PublicKeyCredential && navigator.credentials && navigator.credentials.create && window.isSecureContext);

export async function create(name = '') {
  if (!supported()) throw new Error('This browser does not support passkeys.');
  const { options: o } = await api.post('/api/auth/passkeys/register/options', {});
  const publicKey = {
    rp: o.rp, user: { id: fromB64(o.user.id), name: o.user.name, displayName: o.user.displayName },
    challenge: fromB64(o.challenge), pubKeyCredParams: o.pubKeyCredParams, timeout: o.timeout, attestation: o.attestation,
    authenticatorSelection: o.authenticatorSelection,
    excludeCredentials: (o.excludeCredentials || []).map((x) => ({ id: fromB64(x.id), type: x.type, transports: x.transports })),
    hints: ['client-device'],
  };
  const c = await navigator.credentials.create({ publicKey });
  if (!c) throw new Error('That passkey attempt did not complete.');
  try { localStorage.setItem('optic.auth.passkeyMade', '1'); } catch (e) { /* private mode */ }
  return api.post('/api/auth/passkeys/register/verify', {
    credential: {
      id: c.id, rawId: toB64(c.rawId), type: c.type,
      response: { clientDataJSON: toB64(c.response.clientDataJSON), attestationObject: toB64(c.response.attestationObject), transports: c.response.getTransports ? c.response.getTransports() : [] },
      clientExtensionResults: c.getClientExtensionResults ? c.getClientExtensionResults() : {},
    },
    name,
  });
}
