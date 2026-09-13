/* Optic Terminal — accounts, in the browser.
 *
 * Loaded before app.js and exposes one global, `window.OpticAuth`. Everything
 * here is plain DOM: this project has no framework and no build step, and the
 * sign-in screen was not going to be the thing that introduced one.
 *
 * Three ideas run through the file.
 *
 * **One state read.** `/api/auth/me` answers with everything needed to render
 * either state — the user, which sign-in methods exist, the plan, which
 * providers this deployment has configured, and the CSRF value. It is fetched
 * once, cached, and pushed to subscribers. Four endpoints would mean four round
 * trips before the first paint.
 *
 * **Three states, never two.** `loading`, `guest`, `user`. Collapsing the first
 * two is what makes an app flash a signed-out header at somebody who is signed
 * in, and it is the single most common tell of a bolted-on auth layer. The
 * account button renders nothing until the answer arrives.
 *
 * **Authentication interrupts, it does not redirect.** `OpticAuth.require()`
 * takes the thing you were about to do, opens the modal, and runs it afterwards.
 * Nobody researching NVDA is sent to a dashboard to log in and then left there.
 *
 * The session token is an HttpOnly cookie and is never touched by this file. The
 * only thing read from a cookie here is the CSRF value, which exists to be read.
 */

(function () {
  'use strict';

  /* ------------------------------------------------------------------ utils */

  function esc(str) {
    return String(str === null || str === undefined ? '' : str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function csrfCookie() {
    var match = document.cookie.match(/(?:^|;\s*)optic_csrf=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  /* Every request carries cookies and, on anything that changes state, the CSRF
   * header. Errors arrive as `{detail: "..."}` and are re-thrown as an Error
   * whose message is that sentence, so a caller can put it straight on screen.
   * A 500 has no `detail` worth showing, so it gets a generic line: the server
   * deliberately does not send stack traces to browsers. */
  async function api(path, options) {
    var opts = options || {};
    var headers = { Accept: 'application/json' };
    var method = (opts.method || 'GET').toUpperCase();
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
    if (method !== 'GET' && method !== 'HEAD') {
      var token = csrfCookie();
      if (token) headers['X-Optic-CSRF'] = token;
    }
    var res;
    try {
      res = await fetch(path, {
        method: method,
        headers: headers,
        credentials: 'same-origin',
        cache: 'no-store',
        body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      });
    } catch (err) {
      throw new Error('The connection dropped. Check your network and try again.');
    }
    var data = null;
    try { data = await res.json(); } catch (err) { data = null; }
    if (!res.ok) {
      var detail = data && data.detail;
      if (Array.isArray(detail)) detail = detail.map(function (d) { return d.msg; }).join(' ');
      var error = new Error(detail || (res.status >= 500
        ? 'Something went wrong on the server. Try again in a moment.'
        : 'That did not work (HTTP ' + res.status + ').'));
      error.status = res.status;
      throw error;
    }
    return data;
  }

  /* ------------------------------------------------------------------- state */

  var STATE = {
    status: 'loading',        // loading | guest | user
    admin: false,             // owns this deployment: see app/auth/admin.py
    user: null,
    methods: null,
    preferences: null,
    subscription: null,
    providers: null,
    mail: null,
    policy: [],
    sessionId: null,
  };

  var listeners = [];
  var loaded = null;

  function notify() {
    listeners.forEach(function (fn) {
      try { fn(STATE); } catch (err) { /* one bad subscriber is not the others' problem */ }
    });
    renderAccountButton();
  }

  function absorb(payload) {
    STATE.status = payload && payload.authenticated ? 'user' : 'guest';
    // Server-computed, never inferred from the email on the client. A browser
    // that set this itself would gain nothing — every admin path is re-checked
    // server-side — but it would make the UI claim a privilege the API refuses,
    // which is worse than showing nothing.
    STATE.admin = !!(payload && payload.admin);
    STATE.user = (payload && payload.user) || null;
    STATE.methods = (payload && payload.methods) || null;
    STATE.preferences = (payload && payload.preferences) || null;
    STATE.subscription = (payload && payload.subscription) || null;
    STATE.providers = (payload && payload.providers) || STATE.providers;
    STATE.mail = (payload && payload.mail) || STATE.mail;
    STATE.policy = (payload && payload.password_policy) || STATE.policy;
    STATE.sessionId = (payload && payload.session_id) || null;
    notify();
    return STATE;
  }

  async function load(force) {
    if (loaded && !force) return loaded;
    loaded = api('/api/auth/me').then(absorb).catch(function (err) {
      // A failed state read must not leave the app in `loading` forever. Guest
      // is the safe answer: it shows the open terminal, which is what a visitor
      // gets anyway.
      STATE.status = 'guest';
      notify();
      return STATE;
    });
    return loaded;
  }

  async function refresh() {
    loaded = null;
    return load(true);
  }

  /* -------------------------------------------------------------- passkeys */

  function b64urlToBytes(value) {
    var normalised = String(value || '').replace(/-/g, '+').replace(/_/g, '/');
    while (normalised.length % 4) normalised += '=';
    var raw = atob(normalised);
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
    return bytes;
  }

  function bytesToB64url(buffer) {
    var bytes = new Uint8Array(buffer);
    var out = '';
    for (var i = 0; i < bytes.length; i += 1) out += String.fromCharCode(bytes[i]);
    return btoa(out).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function passkeysSupported() {
    return !!(window.PublicKeyCredential && navigator.credentials
      && navigator.credentials.create && window.isSecureContext);
  }

  /* Whether this device can verify you with a fingerprint or a face.
   *
   * A passkey already IS Face ID or Touch ID — WebAuthn with a platform
   * authenticator uses the device biometric, and that has worked here since
   * passkeys went in. What was missing was saying so: the button read "Sign in
   * with a passkey", a word most people have never met, next to two buttons
   * that said Google and Apple.
   *
   * isUserVerifyingPlatformAuthenticatorAvailable is the only honest way to
   * ask. It answers "this device has a built-in authenticator that will verify
   * the person", which is exactly the claim the label needs to make. A security
   * key or a phone-by-QR still works either way; this only decides the wording.
   *
   * Async, cached, and never awaited by a render: the answer arrives after the
   * first paint, so the label starts neutral and is upgraded in place. A modal
   * that waited on it would flash empty.
   */
  var platformAuth = null;          // null = not asked yet, then true/false

  function askPlatformAuthenticator() {
    if (platformAuth !== null) return Promise.resolve(platformAuth);
    if (!passkeysSupported()
        || !window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable) {
      platformAuth = false;
      return Promise.resolve(false);
    }
    return window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
      .then(function (ok) { platformAuth = !!ok; return platformAuth; })
      .catch(function () { platformAuth = false; return false; });
  }

  /* What to call it, without claiming a sensor we cannot see.
   *
   * There is no API that distinguishes Face ID from Touch ID, or a Windows
   * Hello camera from its fingerprint reader. So the platform family is named
   * from the user agent and BOTH of that family's sensors are named, which is
   * Apple's own convention when an app cannot tell either. Where the platform
   * is not one of the three, the wording stays generic rather than guessing.
   *
   * Getting this wrong costs a slightly odd label and nothing else — the
   * browser still offers whatever the device actually has. */
  function biometricName() {
    var ua = (navigator.userAgent || '');
    if (/iPhone|iPad|iPod|Macintosh|Mac OS X/i.test(ua)) return 'Face ID or Touch ID';
    if (/Android/i.test(ua)) return 'your fingerprint or face';
    if (/Windows/i.test(ua)) return 'Windows Hello';
    return 'your fingerprint or face';
  }

  /** The sign-in button's label: biometric where there is one, passkey where not. */
  function passkeyButtonLabel() {
    return platformAuth ? ('Sign in with ' + biometricName()) : 'Sign in with a passkey';
  }

  /* A passkey ceremony that the person cancelled is not an error worth showing.
   * NotAllowedError covers both "pressed escape" and "timed out", and neither
   * deserves a red banner. AbortError is our own conditional-UI teardown. */
  function passkeyCancelled(err) {
    return err && (err.name === 'NotAllowedError' || err.name === 'AbortError');
  }

  /* Has a passkey ever been created in this browser?
   *
   * The one fact that makes NotAllowedError interpretable. The spec collapses
   * three different situations into that single error on purpose, so that the
   * site cannot learn whether a credential exists: the person dismissed the
   * dialog, it timed out, or there is no passkey for this site on this device.
   *
   * Silence is right for the first two and wrong for the third — pressing "Sign
   * in with Face ID" having never made one did nothing at all and said nothing,
   * which is a dead control. Reproduced against the live site: the ceremony
   * rejects with NotAllowedError and the handler returns.
   *
   * So rather than guessing at intent from timing, this records the one thing
   * actually known. Local to the browser, because that is the scope of the
   * question; a false negative only costs an extra sentence of guidance. */
  var MADE_KEY = 'optic.auth.passkeyMade';

  function passkeyMadeHere() {
    try { return localStorage.getItem(MADE_KEY) === '1'; } catch (e) { return false; }
  }

  function rememberPasskeyMade() {
    try { localStorage.setItem(MADE_KEY, '1'); } catch (e) { /* private mode */ }
  }

  /* What to say when the ceremony ends with nothing.
   *
   * Returns null where silence is right. A red banner every time somebody
   * presses Escape is the reason this was swallowed in the first place, so the
   * guidance is only offered where it is the likely explanation, and it covers
   * the dismissal case too rather than accusing the reader of not having a
   * passkey. */
  function passkeyNothingHappened(err) {
    if (!err || err.name === 'AbortError') return null;
    if (err.name !== 'NotAllowedError') return null;
    if (passkeyMadeHere()) return null;
    return 'No passkey was offered on this device. If you have not set one up '
      + 'yet, sign in with your email and password once, then add ' + biometricName()
      + ' from Settings.';
  }

  function passkeyMessage(err) {
    if (!err) return 'That passkey attempt did not complete.';
    if (err.name === 'InvalidStateError') {
      return 'This device already has a passkey for Optic Terminal.';
    }
    if (err.name === 'OperationError'
        || /already pending/i.test(err.message || '')) {
      // Should now be unreachable from the button, which releases the autofill
      // request first. Kept because a browser extension or a second tab can
      // hold the slot, and "A request is already pending" alone tells a reader
      // nothing they can act on.
      return 'Another sign-in prompt is already open. Close it, or reload this '
        + 'page, and try again.';
    }
    if (err.name === 'SecurityError') {
      // The RP id has to match the site's domain. Getting it wrong fails in the
      // browser before any request is sent, so there is nothing in the server
      // log to find.
      return 'This browser refused the passkey for this domain. If you are running '
        + 'Optic locally, open it at http://localhost rather than 127.0.0.1.';
    }
    return err.message || 'That passkey attempt did not complete.';
  }

  /* Ask for the sensor on this device first.
   *
   * WebAuthn L3 `hints` is a preference, not a restriction: a phone and a USB
   * key stay reachable, they just stop being the first thing offered. Without
   * it, a Mac with no local passkey yet opens straight onto "Use a phone or
   * tablet" and "USB security key" under a button that says Touch ID, which is
   * what a reader reported. An unknown hint is ignored, so this is safe on
   * browsers that predate it.
   *
   * It matters most on the *create* side. Registering is where the local
   * credential either comes into existence or does not, and a dialog that
   * leads with the phone is how somebody ends up with a passkey that Touch ID
   * can never satisfy. Once one exists here, signing in finds it. */
  function preferThisDevice(publicKey) {
    publicKey.hints = ['client-device'];
    return publicKey;
  }

  async function createPasskey(name) {
    if (!passkeysSupported()) {
      throw new Error('This browser does not support passkeys.');
    }
    var got = await api('/api/auth/passkeys/register/options', { method: 'POST' });
    var options = got.options;
    var publicKey = {
      rp: options.rp,
      user: {
        id: b64urlToBytes(options.user.id),
        name: options.user.name,
        displayName: options.user.displayName,
      },
      challenge: b64urlToBytes(options.challenge),
      pubKeyCredParams: options.pubKeyCredParams,
      timeout: options.timeout,
      attestation: options.attestation,
      authenticatorSelection: options.authenticatorSelection,
      excludeCredentials: (options.excludeCredentials || []).map(function (item) {
        return { id: b64urlToBytes(item.id), type: item.type, transports: item.transports };
      }),
    };
    var credential = await navigator.credentials.create({
      publicKey: preferThisDevice(publicKey),
    });
    if (!credential) throw new Error('That passkey attempt did not complete.');
    var response = {
      id: credential.id,
      rawId: bytesToB64url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: bytesToB64url(credential.response.clientDataJSON),
        attestationObject: bytesToB64url(credential.response.attestationObject),
        transports: credential.response.getTransports
          ? credential.response.getTransports() : [],
      },
      clientExtensionResults: credential.getClientExtensionResults
        ? credential.getClientExtensionResults() : {},
    };
    rememberPasskeyMade();
    var saved = await api('/api/auth/passkeys/register/verify', {
      method: 'POST',
      body: { credential: response, name: name || '' },
    });
    await refresh();
    return saved;
  }

  async function signInWithPasskey(mediation, signal) {
    if (!passkeysSupported()) {
      throw new Error('This browser does not support passkeys.');
    }
    var got = await api('/api/auth/passkeys/login/options', { method: 'POST' });
    var options = got.options;
    var publicKey = {
      challenge: b64urlToBytes(options.challenge),
      timeout: options.timeout,
      rpId: options.rpId,
      userVerification: options.userVerification,
      allowCredentials: (options.allowCredentials || []).map(function (item) {
        return { id: b64urlToBytes(item.id), type: item.type, transports: item.transports };
      }),
    };
    var request = { publicKey: preferThisDevice(publicKey) };
    if (mediation) request.mediation = mediation;
    if (signal) request.signal = signal;
    var credential = await navigator.credentials.get(request);
    if (!credential) throw new Error('That passkey attempt did not complete.');
    var assertion = {
      id: credential.id,
      rawId: bytesToB64url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: bytesToB64url(credential.response.clientDataJSON),
        authenticatorData: bytesToB64url(credential.response.authenticatorData),
        signature: bytesToB64url(credential.response.signature),
        userHandle: credential.response.userHandle
          ? bytesToB64url(credential.response.userHandle) : null,
      },
      clientExtensionResults: credential.getClientExtensionResults
        ? credential.getClientExtensionResults() : {},
    };
    var signed = await api('/api/auth/passkeys/login/verify', {
      method: 'POST', body: { credential: assertion },
    });
    await refresh();
    return signed;
  }

  /* ---------------------------------------------------------------- toasts */

  function toast(message, kind) {
    var host = document.getElementById('auth-toasts');
    if (!host) {
      host = document.createElement('div');
      host.id = 'auth-toasts';
      host.className = 'auth-toasts';
      host.setAttribute('role', 'status');
      host.setAttribute('aria-live', 'polite');
      document.body.appendChild(host);
    }
    var note = document.createElement('div');
    note.className = 'auth-toast' + (kind ? ' ' + kind : '');
    note.textContent = message;
    host.appendChild(note);
    // Long enough to read two lines, and dismissible by clicking it.
    var timer = setTimeout(function () { drop(); }, 7000);
    function drop() {
      clearTimeout(timer);
      note.classList.add('gone');
      setTimeout(function () { if (note.parentNode) note.parentNode.removeChild(note); }, 200);
    }
    note.addEventListener('click', drop);
    return drop;
  }

  /* ----------------------------------------------------------------- modal */

  var modal = null;
  var lastFocus = null;
  var pending = null;          // what to run once somebody is signed in
  var mode = 'signin';
  var resetToken = '';
  var conditionalAbort = null;
  // One explicit ceremony at a time. See stopConditionalPasskey for why a
  // second overlapping request is not merely wasteful but fails outright.
  var passkeyBusy = false;

  function providerAvailable(name) {
    var providers = STATE.providers || {};
    return !!(providers[name] && providers[name].available);
  }

  function providerRow(reason) {
    var buttons = [];
    if (providerAvailable('apple')) {
      buttons.push('<button type="button" class="auth-provider apple" data-provider="apple">'
        + '<svg viewBox="0 0 16 16" aria-hidden="true" class="auth-glyph">'
        + '<path fill="currentColor" d="M11.2 8.5c0-1.4.8-2.3 1.5-2.8-.6-.9-1.6-1.3-2.4-1.3-.9 0-1.6.5-2.1.5s-1.1-.5-1.9-.5C4.7 4.4 3 5.7 3 8.4c0 1.7.6 3.4 1.4 4.5.6.8 1.1 1.4 1.9 1.4.7 0 1-.4 1.9-.4.9 0 1.1.4 1.9.4.8 0 1.3-.7 1.9-1.5.4-.6.6-1.1.8-1.7-1.3-.5-1.6-1.7-1.6-2.6zM9.9 3.4c.4-.5.7-1.2.6-1.9-.7 0-1.4.4-1.9 1-.4.5-.7 1.2-.6 1.9.7.1 1.4-.4 1.9-1z"/>'
        + '</svg>Continue with Apple</button>');
    }
    if (providerAvailable('google')) {
      buttons.push('<button type="button" class="auth-provider google" data-provider="google">'
        + '<svg viewBox="0 0 18 18" aria-hidden="true" class="auth-glyph">'
        + '<path fill="#4285F4" d="M17.6 9.2c0-.6-.1-1.2-.2-1.8H9v3.4h4.8a4.1 4.1 0 0 1-1.8 2.7v2.2h2.9c1.7-1.6 2.7-3.9 2.7-6.5z"/>'
        + '<path fill="#34A853" d="M9 18c2.4 0 4.5-.8 6-2.2l-2.9-2.2c-.8.5-1.8.9-3.1.9-2.4 0-4.4-1.6-5.1-3.8H.9v2.3A9 9 0 0 0 9 18z"/>'
        + '<path fill="#FBBC05" d="M3.9 10.7a5.4 5.4 0 0 1 0-3.4V5H.9a9 9 0 0 0 0 8l3-2.3z"/>'
        + '<path fill="#EA4335" d="M9 3.6c1.3 0 2.5.5 3.4 1.3l2.6-2.6A9 9 0 0 0 .9 5l3 2.3C4.6 5.2 6.6 3.6 9 3.6z"/>'
        + '</svg>Continue with Google</button>');
    }
    if (passkeysSupported() && providerAvailable('passkey')) {
      buttons.push('<button type="button" class="auth-provider passkey" data-passkey-signin'
        + ' title="Uses the passkey saved on this device. A security key or your'
        + ' phone works too.">'
        + '<svg viewBox="0 0 24 24" aria-hidden="true" class="auth-glyph">'
        + '<circle cx="9" cy="8" r="3.4" fill="none" stroke="currentColor" stroke-width="1.8"/>'
        + '<path d="M3.4 20c0-3.1 2.5-5.2 5.6-5.2 1 0 2 .2 2.8.6" fill="none" '
        + 'stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'
        + '<path d="M17 12.4v3.2m0 2.2v2.6m-1.6-1.3H17" fill="none" stroke="currentColor" '
        + 'stroke-width="1.8" stroke-linecap="round"/>'
        + '<circle cx="17" cy="10.4" r="2.4" fill="none" stroke="currentColor" stroke-width="1.8"/>'
        + '</svg><span data-passkey-label>' + esc(passkeyButtonLabel())
        + '</span></button>');
    }
    if (!buttons.length) return '';
    /* Say where a passkey comes from, before the dialog does not offer one.
     *
     * A reader pressed "Sign in with Touch ID" on a laptop and got Chrome's
     * "Use a phone or tablet / USB security key" list, because there was no
     * passkey for this site on that Mac. Nothing was broken: the spec gives a
     * site no way to ask whether a credential exists, deliberately, so the
     * button cannot know before it opens the dialog. What it can do is not let
     * that dialog be the first mention of how one gets made.
     *
     * Only where none has been made in this browser, and phrased as a
     * condition rather than a claim: a passkey synced from an iPhone will show
     * up here without ever having been created on this machine, so "you do not
     * have one" would be wrong for exactly the people it would annoy most. */
    var hint = (passkeysSupported() && providerAvailable('passkey')
                && !passkeyMadeHere())
      ? '<p class="auth-note auth-passkey-hint">First time on this device? Sign in '
        + 'with your email, then add ' + esc(biometricName()) + ' from Settings.</p>'
      : '';
    return '<div class="auth-providers">' + buttons.join('') + '</div>' + hint
      + '<div class="auth-or"><span>or</span></div>';
  }

  function policyList() {
    var rules = STATE.policy && STATE.policy.length ? STATE.policy
      : ['At least 10 characters', 'Not a commonly used password',
        'Not your name or email address'];
    return '<ul class="auth-policy">' + rules.map(function (rule) {
      return '<li>' + esc(rule) + '</li>';
    }).join('') + '</ul>';
  }

  function passwordField(id, label, autocomplete) {
    return '<label class="auth-field auth-pw">'
      + '<span>' + esc(label) + '</span>'
      + '<span class="auth-pw-wrap">'
      + '<input type="password" id="' + id + '" name="' + id + '" autocomplete="'
      + autocomplete + '" required>'
      + '<button type="button" class="auth-peek" data-peek="' + id + '" '
      + 'aria-label="Show password" title="Show password">Show</button>'
      + '</span></label>';
  }

  function body() {
    if (mode === 'signup') {
      return '<h2 id="auth-title">Create your Optic Terminal account</h2>'
        + '<p class="auth-sub">Free. It exists so a watchlist and your saved research '
        + 'follow you between devices. The terminal itself stays open either way.</p>'
        + providerRow()
        + '<form class="auth-form" data-form="signup" novalidate>'
        + '<div class="auth-row2">'
        + '<label class="auth-field"><span>First name</span>'
        + '<input type="text" name="first_name" autocomplete="given-name" required></label>'
        + '<label class="auth-field"><span>Last name</span>'
        + '<input type="text" name="last_name" autocomplete="family-name"></label>'
        + '</div>'
        + '<label class="auth-field"><span>Email</span>'
        + '<input type="email" name="email" autocomplete="email" required '
        + 'spellcheck="false"></label>'
        + passwordField('auth-new-password', 'Password', 'new-password')
        + policyList()
        + passwordField('auth-confirm-password', 'Confirm password', 'new-password')
        + '<div class="auth-error" data-error hidden></div>'
        + '<button type="submit" class="btn primary auth-submit">Create account</button>'
        + '</form>'
        + '<p class="auth-alt">Already have an account? '
        + '<button type="button" data-mode="signin">Sign in</button></p>';
    }

    if (mode === 'forgot') {
      return '<h2 id="auth-title">Reset your password</h2>'
        + '<p class="auth-sub">Enter the address on the account. If it has a password, '
        + 'a reset link goes to that inbox and works once, for 15 minutes.</p>'
        + '<form class="auth-form" data-form="forgot" novalidate>'
        + '<label class="auth-field"><span>Email</span>'
        + '<input type="email" name="email" autocomplete="email" required '
        + 'spellcheck="false"></label>'
        + '<div class="auth-error" data-error hidden></div>'
        + '<div class="auth-note" data-note hidden></div>'
        + '<button type="submit" class="btn primary auth-submit">Send reset link</button>'
        + '</form>'
        + '<p class="auth-alt"><button type="button" data-mode="signin">'
        + 'Back to sign in</button></p>';
    }

    if (mode === 'reset') {
      return '<h2 id="auth-title">Choose a new password</h2>'
        + '<p class="auth-sub">Every signed-in device is signed out when this is done.</p>'
        + '<form class="auth-form" data-form="reset" novalidate>'
        + passwordField('auth-reset-password', 'New password', 'new-password')
        + policyList()
        + passwordField('auth-reset-confirm', 'Confirm password', 'new-password')
        + '<div class="auth-error" data-error hidden></div>'
        + '<button type="submit" class="btn primary auth-submit">Set password '
        + 'and sign in</button>'
        + '</form>';
    }

    // signin
    var reason = pending && pending.reason
      ? '<p class="auth-reason">' + esc(pending.reason) + '</p>' : '';
    return '<h2 id="auth-title">Welcome back to Optic Terminal</h2>'
      + reason
      + providerRow()
      + '<form class="auth-form" data-form="signin" novalidate>'
      + '<label class="auth-field"><span>Email</span>'
      // `username webauthn` is what lets a browser offer a saved passkey from
      // the email field itself. Harmless where it is not supported.
      + '<input type="email" name="email" autocomplete="username webauthn" required '
      + 'spellcheck="false"></label>'
      + passwordField('auth-password', 'Password', 'current-password')
      + '<div class="auth-error" data-error hidden></div>'
      + '<button type="submit" class="btn primary auth-submit">Sign in</button>'
      + '<button type="button" class="auth-link" data-mode="forgot">'
      + 'Forgot password?</button>'
      + '</form>'
      + '<p class="auth-alt">Do not have an account? '
      + '<button type="button" data-mode="signup">Create one</button></p>';
  }

  function paint() {
    if (!modal) return;
    modal.querySelector('.auth-body').innerHTML = body();
    var first = modal.querySelector('input:not([type=hidden])');
    if (first) first.focus();
    armConditionalPasskey();
    /* Upgrade the passkey label once the device has answered.
     *
     * The check is async and paint is not, so the button renders with the
     * neutral wording and swaps to "Face ID or Touch ID" a frame later.
     * Swapping the label rather than repainting the row, because a repaint
     * would take focus off the field the person is typing in and tear down the
     * conditional-UI request armed two lines above. */
    askPlatformAuthenticator().then(function () {
      if (!modal) return;
      var label = modal.querySelector('[data-passkey-label]');
      if (label) label.textContent = passkeyButtonLabel();
    });
  }

  function open(next, options) {
    var opts = options || {};
    mode = next || 'signin';
    pending = opts.pending || pending;
    if (opts.reason && !pending) pending = { reason: opts.reason };
    if (opts.token) resetToken = opts.token;

    if (modal) { paint(); return; }
    lastFocus = document.activeElement;
    modal = document.createElement('div');
    modal.className = 'auth-modal';
    modal.innerHTML = '<div class="auth-backdrop" data-close></div>'
      + '<div class="auth-card" role="dialog" aria-modal="true" '
      + 'aria-labelledby="auth-title">'
      + '<button type="button" class="auth-close" data-close '
      + 'aria-label="Close">&times;</button>'
      + '<div class="auth-body"></div>'
      + '<p class="auth-legal">Optic Terminal is a research tool. Nothing here is '
      + 'financial advice.</p>'
      + '</div>';
    document.body.appendChild(modal);
    document.body.classList.add('auth-open');
    paint();

    modal.addEventListener('click', onModalClick);
    modal.addEventListener('submit', onModalSubmit);
    document.addEventListener('keydown', onModalKey, true);
  }

  function close(silent) {
    if (!modal) return;
    stopConditionalPasskey();
    passkeyBusy = false;
    document.removeEventListener('keydown', onModalKey, true);
    modal.parentNode.removeChild(modal);
    modal = null;
    document.body.classList.remove('auth-open');
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    lastFocus = null;
    if (!silent) pending = null;
  }

  function onModalKey(evt) {
    if (!modal) return;
    if (evt.key === 'Escape') { evt.stopPropagation(); close(); return; }
    if (evt.key !== 'Tab') return;
    // Focus stays inside the dialog. Without this, tab walks into the page
    // behind it and a keyboard user is stuck outside a modal they cannot see.
    var focusable = modal.querySelectorAll(
      'button:not([disabled]), input:not([disabled]), a[href], select, textarea');
    if (!focusable.length) return;
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (evt.shiftKey && document.activeElement === first) {
      evt.preventDefault(); last.focus();
    } else if (!evt.shiftKey && document.activeElement === last) {
      evt.preventDefault(); first.focus();
    }
  }

  function showError(form, message) {
    var box = form.querySelector('[data-error]');
    if (!box) { toast(message, 'bad'); return; }
    box.textContent = message;
    // A real error can follow a note with no clearError between them.
    box.classList.remove('auth-note');
    box.classList.add('auth-error');
    box.hidden = false;
  }

  /* Guidance, in the same slot as an error but not dressed as one.
   *
   * Reuses the error box, because that is where a reader is already looking
   * after pressing the button, and swaps it to the .auth-note styling this
   * stylesheet already defines — quiet, bordered, no red. "You may not have a
   * passkey yet" is an instruction, not a failure. */
  function showNote(form, message) {
    var box = form.querySelector('[data-error]');
    if (!box) { toast(message); return; }
    box.textContent = message;
    box.classList.remove('auth-error');
    box.classList.add('auth-note');
    box.hidden = false;
  }

  function clearError(form) {
    var box = form.querySelector('[data-error]');
    // Restored to the error styling as well: left as a note, the next genuine
    // failure renders quiet and reads as advice.
    if (box) {
      box.hidden = true;
      box.textContent = '';
      box.classList.remove('auth-note');
      box.classList.add('auth-error');
    }
  }

  function busy(form, on, label) {
    var button = form.querySelector('.auth-submit');
    if (!button) return;
    if (on) {
      button.dataset.idle = button.textContent;
      button.textContent = label || 'Working...';
      button.disabled = true;
    } else {
      button.textContent = button.dataset.idle || button.textContent;
      button.disabled = false;
    }
  }

  async function finish(payload) {
    absorb({
      authenticated: true,
      user: payload.user,
      methods: payload.methods || STATE.methods,
      providers: STATE.providers,
      mail: STATE.mail,
      password_policy: STATE.policy,
    });
    await refresh();
    var resume = pending;
    close(true);
    pending = null;
    if (resume && typeof resume.run === 'function') {
      try { await resume.run(STATE); } catch (err) { toast(err.message, 'bad'); }
    }
    maybeOfferPasskey();
  }

  function onModalClick(evt) {
    var target = evt.target;
    if (!target || !target.closest) return;

    if (target.closest('[data-close]')) { close(); return; }

    var switcher = target.closest('[data-mode]');
    if (switcher) { open(switcher.getAttribute('data-mode'), { pending: pending }); return; }

    var peek = target.closest('[data-peek]');
    if (peek) {
      var input = document.getElementById(peek.getAttribute('data-peek'));
      if (input) {
        var showing = input.type === 'text';
        input.type = showing ? 'password' : 'text';
        peek.textContent = showing ? 'Show' : 'Hide';
        peek.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
      }
      return;
    }

    var provider = target.closest('[data-provider]');
    if (provider) {
      var name = provider.getAttribute('data-provider');
      // A full-page redirect, not a popup: a popup is blocked as often as it
      // works, and Apple will not render inside one.
      var query = '?next=' + encodeURIComponent(location.pathname + location.search);
      location.href = '/api/auth/' + name + '/start' + query;
      return;
    }

    if (target.closest('[data-passkey-signin]')) {
      // A second press while the first dialog is open is another pending
      // request and the same OperationError.
      if (passkeyBusy) return;
      passkeyBusy = true;
      var form = modal.querySelector('.auth-form');
      if (form) clearError(form);
      stopConditionalPasskey().then(function () {
        return signInWithPasskey();
      }).then(function (payload) {
        passkeyBusy = false;
        finish(payload);
      }).catch(function (err) {
        passkeyBusy = false;
        // Put the autofill shortcut back: the person may have dismissed the
        // dialog and gone to type their email instead.
        armConditionalPasskey();
        if (passkeyCancelled(err)) {
          /* An explicit press that produced nothing needs an explanation, where
           * the autofill route stays silent: one is a question the reader asked
           * out loud, the other is a shortcut that simply was not taken. */
          var hint = passkeyNothingHappened(err);
          if (hint) {
            if (form) showNote(form, hint); else toast(hint);
          }
          return;
        }
        if (form) showError(form, passkeyMessage(err));
        else toast(passkeyMessage(err), 'bad');
      });
    }
  }

  async function onModalSubmit(evt) {
    var form = evt.target;
    if (!form || form.tagName !== 'FORM') return;
    evt.preventDefault();
    clearError(form);
    var kind = form.getAttribute('data-form');
    var data = {};
    Array.prototype.forEach.call(form.elements, function (field) {
      if (field.name) data[field.name] = field.value;
    });

    try {
      if (kind === 'signin') {
        busy(form, true, 'Signing in...');
        var signed = await api('/api/auth/login', {
          method: 'POST',
          body: { email: data.email, password: data['auth-password'] },
        });
        await finish(signed);
        toast('Signed in as ' + signed.user.email);
        return;
      }

      if (kind === 'signup') {
        busy(form, true, 'Creating account...');
        var made = await api('/api/auth/register', {
          method: 'POST',
          body: {
            first_name: data.first_name,
            last_name: data.last_name,
            email: data.email,
            password: data['auth-new-password'],
            confirm_password: data['auth-confirm-password'],
          },
        });
        await finish(made);
        if (made.verification_sent) {
          toast('Account created. Check ' + made.user.email + ' to confirm the address.');
        } else if (made.mail && !made.mail.available) {
          // Honest rather than reassuring: no mail is configured, so no message
          // was sent, and saying "check your inbox" would be a lie.
          toast('Account created. Email is not configured on this deployment, so no '
            + 'verification message was sent.', 'warn');
        } else {
          toast('Account created, but the verification email could not be sent. '
            + 'You can request another from Settings.', 'warn');
        }
        return;
      }

      if (kind === 'forgot') {
        busy(form, true, 'Sending...');
        var asked = await api('/api/auth/forgot-password', {
          method: 'POST', body: { email: data.email },
        });
        var note = form.querySelector('[data-note]');
        var message = asked.message;
        if (asked.mail && !asked.mail.available) {
          message += ' Email is not configured on this deployment, so the link is in '
            + 'the server log rather than an inbox.';
        }
        if (note) { note.textContent = message; note.hidden = false; }
        busy(form, false);
        return;
      }

      if (kind === 'reset') {
        busy(form, true, 'Setting password...');
        var done = await api('/api/auth/reset-password', {
          method: 'POST',
          body: {
            token: resetToken,
            password: data['auth-reset-password'],
            confirm_password: data['auth-reset-confirm'],
          },
        });
        resetToken = '';
        await finish(done);
        toast('Password changed, and you are signed in.');
        return;
      }
    } catch (err) {
      busy(form, false);
      showError(form, err.message);
    }
  }

  /* Release the WebAuthn slot before asking for it again.
   *
   * A browser allows exactly one navigator.credentials.get() at a time, and
   * paint() arms a conditional-mediation request on every render of the sign-in
   * modal. So pressing "Sign in with Face ID" started a second call while the
   * autofill call was still outstanding, and the browser rejected it with
   * `OperationError: A request is already pending.` — reproduced on the live
   * site and on localhost. The button did nothing useful, every time, on a page
   * where a passkey would otherwise have worked.
   *
   * The abort existed but only ran in close(), so the collision was guaranteed
   * for anyone who pressed the button rather than using the autofill dropdown.
   *
   * Awaits a macrotask after aborting: abort() is synchronous but the browser
   * releases the slot on its own turn, and retrying in the same tick fails the
   * same way. */
  function stopConditionalPasskey() {
    if (!conditionalAbort) return Promise.resolve();
    try { conditionalAbort.abort(); } catch (e) { /* already settled */ }
    conditionalAbort = null;
    return new Promise(function (done) { setTimeout(done, 0); });
  }

  /* Conditional mediation: the browser offers a saved passkey from inside the
   * email field, with no button pressed. Entirely optional, and every failure
   * here is swallowed — it is a shortcut, and a broken shortcut must not break
   * the form it sits on. */
  async function armConditionalPasskey() {
    if (!modal || mode !== 'signin' || !passkeysSupported()) return;
    if (!window.PublicKeyCredential.isConditionalMediationAvailable) return;
    try {
      var ok = await window.PublicKeyCredential.isConditionalMediationAvailable();
      if (!ok || !modal) return;
      if (conditionalAbort) conditionalAbort.abort();
      conditionalAbort = new AbortController();
      var payload = await signInWithPasskey('conditional', conditionalAbort.signal);
      conditionalAbort = null;
      await finish(payload);
      toast('Signed in with your passkey.');
    } catch (err) {
      conditionalAbort = null;
    }
  }

  /* -------------------------------------------------- passkey promotion */

  var PROMPTED_KEY = 'optic.auth.passkeyOffered';

  function maybeOfferPasskey() {
    if (STATE.status !== 'user' || !STATE.methods) return;
    if (STATE.methods.passkeys > 0 || !passkeysSupported()) return;
    try {
      if (localStorage.getItem(PROMPTED_KEY)) return;
      localStorage.setItem(PROMPTED_KEY, new Date().toISOString());
    } catch (err) { return; }        // private mode: do not nag every load

    var host = document.createElement('div');
    host.className = 'auth-promo';
    host.innerHTML = '<div class="auth-promo-copy">'
      + '<strong>Make sign-in faster</strong>'
      + '<span>Set up a passkey and use ' + esc(biometricName()) + ' or your device PIN '
      + 'next time. No password to type or lose.</span></div>'
      + '<div class="auth-promo-act">'
      + '<button type="button" class="btn primary" data-promo-add>Set up passkey</button>'
      + '<button type="button" class="btn" data-promo-later>Maybe later</button></div>';
    document.body.appendChild(host);

    host.addEventListener('click', function (evt) {
      if (evt.target.closest('[data-promo-later]')) { host.remove(); return; }
      if (!evt.target.closest('[data-promo-add]')) return;
      var button = evt.target.closest('[data-promo-add]');
      button.disabled = true;
      button.textContent = 'Waiting for your device...';
      createPasskey('').then(function () {
        host.remove();
        toast('Passkey saved. Next time, no password.');
      }).catch(function (err) {
        button.disabled = false;
        button.textContent = 'Set up passkey';
        if (!passkeyCancelled(err)) toast(passkeyMessage(err), 'bad');
      });
    });
  }

  /* -------------------------------------------------------- account button */

  var menuOpen = false;

  function initials(user) {
    var first = (user.first_name || '').trim();
    var last = (user.last_name || '').trim();
    if (first || last) {
      return ((first[0] || '') + (last[0] || '')).toUpperCase();
    }
    return (user.email || '?').slice(0, 1).toUpperCase();
  }

  function renderAccountButton() {
    var host = document.getElementById('account-slot');
    if (!host) return;

    if (STATE.status === 'loading') {
      // Nothing, on purpose. Rendering "Sign in" here and swapping it a moment
      // later is the flash this three-state model exists to avoid.
      host.innerHTML = '<span class="acct-wait" aria-hidden="true"></span>';
      return;
    }

    if (STATE.status === 'guest') {
      host.innerHTML = '<button type="button" class="btn acct-signin" data-auth-open="signin">'
        + 'Sign in</button>';
      return;
    }

    var user = STATE.user || {};
    var avatar = user.avatar_url
      ? '<img class="acct-face" src="' + esc(user.avatar_url) + '" alt="">'
      : '<span class="acct-face">' + esc(initials(user)) + '</span>';
    host.innerHTML = '<button type="button" class="acct-btn" id="account-btn" '
      + 'aria-haspopup="true" aria-expanded="' + (menuOpen ? 'true' : 'false') + '" '
      + 'aria-label="Account menu for ' + esc(user.email) + '">'
      + avatar + '</button>';
    if (menuOpen) renderMenu(host);
  }

  function renderMenu(host) {
    var user = STATE.user || {};
    var plan = (STATE.subscription || {}).label || 'Free';
    var unverified = user.email_verified === false;
    var menu = document.createElement('div');
    menu.className = 'acct-menu';
    menu.setAttribute('role', 'menu');
    menu.innerHTML = '<div class="acct-head">'
      + '<span class="acct-name">' + esc(user.name || user.email) + '</span>'
      + '<span class="acct-mail">' + esc(user.email) + '</span>'
      + '<span class="acct-plan">' + esc(plan) + ' plan</span>'
      // Shown because the privilege is silent otherwise: the owner's only
      // evidence would be that a write stopped asking for a token, which is
      // indistinguishable from the token being cached. Rendered from STATE.admin
      // and therefore from the server's answer, so it appears exactly when the
      // API would actually allow it.
      + (STATE.admin ? '<span class="acct-admin">Owner</span>' : '')
      + '</div>'
      + (unverified ? '<div class="acct-warn">Email not confirmed. '
        + '<button type="button" data-acct-resend>Resend the link</button></div>' : '')
      + '<div class="acct-items">'
      + '<button type="button" role="menuitem" data-acct-go="watchlist">Watchlists</button>'
      + '<button type="button" role="menuitem" data-acct-go="brief">Saved research</button>'
      + '<button type="button" role="menuitem" data-acct-go="settings">Settings</button>'
      + '</div>'
      + '<button type="button" class="acct-out" role="menuitem" data-acct-signout>'
      + 'Sign out</button>';
    host.appendChild(menu);
  }

  function closeMenu() {
    if (!menuOpen) return;
    menuOpen = false;
    renderAccountButton();
  }

  document.addEventListener('click', function (evt) {
    var target = evt.target;
    if (!target || !target.closest) return;

    var opener = target.closest('[data-auth-open]');
    if (opener) {
      open(opener.getAttribute('data-auth-open'));
      return;
    }

    if (target.closest('#account-btn')) {
      menuOpen = !menuOpen;
      renderAccountButton();
      return;
    }

    if (target.closest('[data-acct-signout]')) {
      closeMenu();
      signOut();
      return;
    }

    var goto = target.closest('[data-acct-go]');
    if (goto) {
      closeMenu();
      var view = goto.getAttribute('data-acct-go');
      if (window.OpticAuth.onNavigate) window.OpticAuth.onNavigate(view);
      return;
    }

    if (target.closest('[data-acct-resend]')) {
      api('/api/auth/resend-verification', { method: 'POST' }).then(function (reply) {
        closeMenu();
        if (reply.already_verified) toast('That address is already confirmed.');
        else if (reply.sent) toast('A new confirmation link is on its way.');
        else toast('Email is not configured on this deployment, so the link went to '
          + 'the server log.', 'warn');
      }).catch(function (err) { toast(err.message, 'bad'); });
      return;
    }

    if (menuOpen && !target.closest('.acct-menu')) closeMenu();
  });

  document.addEventListener('keydown', function (evt) {
    if (evt.key === 'Escape' && menuOpen) closeMenu();
  });

  async function signOut() {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch (err) { /* going anyway */ }
    absorb({ authenticated: false, providers: STATE.providers, mail: STATE.mail,
      password_policy: STATE.policy });
    toast('Signed out. The terminal stays open.');
    if (window.OpticAuth.onSignOut) window.OpticAuth.onSignOut();
  }

  /* -------------------------------------------------------- the ask moment */

  /* The conversion point from the brief: somebody is researching NVDA, presses
   * Save, and the modal opens over the work rather than replacing it. Signed in
   * already, `run` happens immediately and no modal appears at all. */
  async function require(reason, run) {
    await load();
    if (STATE.status === 'user') {
      return run ? run(STATE) : STATE;
    }
    open('signup', { pending: { reason: reason, run: run } });
    return null;
  }

  /* ------------------------------------------------- links from an email */

  var OAUTH_ERRORS = {
    state: 'That sign-in attempt expired before it finished. Start again.',
    provider: 'The sign-in could not be completed. Try again in a moment.',
    config: 'That sign-in method is not configured on this deployment yet.',
    taken: 'That account is already connected to another Optic Terminal account.',
    needs_link: 'An Optic Terminal account already uses that email address. Sign in the '
      + 'way you did before, then connect this method under Settings, Security. That '
      + 'keeps one account instead of two.',
    no_email: 'No email address was shared, so there is nothing to attach an account to. '
      + 'Try again and choose to share your address, or create an account with an email '
      + 'and password.',
    inactive: 'That account is not active.',
    denied: 'That sign-in was cancelled.',
  };

  function scrubUrl(keys) {
    if (!window.history || !history.replaceState) return;
    var url = new URL(location.href);
    keys.forEach(function (key) { url.searchParams.delete(key); });
    history.replaceState({}, '', url.pathname + (url.search || '') + url.hash);
  }

  async function handleUrl() {
    var params = new URLSearchParams(location.search);

    var verify = params.get('verify');
    if (verify) {
      scrubUrl(['verify']);
      try {
        await api('/api/auth/verify-email', { method: 'POST', body: { token: verify } });
        await refresh();
        toast('Email address confirmed.');
      } catch (err) {
        toast(err.message, 'bad');
      }
      return;
    }

    var reset = params.get('reset');
    if (reset) {
      scrubUrl(['reset']);
      var check = null;
      try {
        check = await api('/api/auth/reset/check?token=' + encodeURIComponent(reset));
      } catch (err) { check = { valid: false, reason: err.message }; }
      if (check && check.valid) open('reset', { token: reset });
      else toast((check && check.reason) || 'That reset link is no longer valid.', 'bad');
      return;
    }

    if (params.get('auth') === 'ok') {
      scrubUrl(['auth', 'provider', 'next']);
      await refresh();
      if (STATE.user) toast('Signed in as ' + STATE.user.email);
      maybeOfferPasskey();
      var next = params.get('next');
      if (next && next.charAt(0) === '/' && next.charAt(1) !== '/') {
        history.replaceState({}, '', next);
      }
      return;
    }

    var failed = params.get('auth_error');
    if (failed) {
      var who = params.get('provider') || '';
      scrubUrl(['auth_error', 'provider', 'next']);
      var message = OAUTH_ERRORS[failed] || OAUTH_ERRORS.provider;
      if (who && (failed === 'taken' || failed === 'needs_link' || failed === 'config'
        || failed === 'no_email')) {
        message = message.replace('That account', 'That ' + label(who) + ' account')
          .replace('this method', label(who))
          .replace('No email address', label(who) + ' shared no email address');
      }
      toast(message, 'bad');
      if (failed === 'needs_link') open('signin');
    }
  }

  function label(provider) {
    if (provider === 'google') return 'Google';
    if (provider === 'apple') return 'Apple';
    if (provider === 'email') return 'Email';
    return provider.charAt(0).toUpperCase() + provider.slice(1);
  }

  /* ------------------------------------------------------------------ boot */

  window.OpticAuth = {
    state: function () { return STATE; },
    load: load,
    refresh: refresh,
    api: api,
    on: function (fn) { listeners.push(fn); if (STATE.status !== 'loading') fn(STATE); },
    open: open,
    close: close,
    require: require,
    signOut: signOut,
    toast: toast,
    createPasskey: createPasskey,
    signInWithPasskey: signInWithPasskey,
    passkeysSupported: passkeysSupported,
    // Exported so the Settings page can label its own passkey button the same
    // way, and so a test can assert the wording without a browser.
    biometricName: biometricName,
    platformAuthenticator: askPlatformAuthenticator,
    passkeyMessage: passkeyMessage,
    passkeyCancelled: passkeyCancelled,
    providerLabel: label,
    // Exposed so app.js's own postJSON can send the header on the four
    // write-guarded endpoints. Exported rather than re-read in app.js because
    // the cookie *name* would then live in two files, and the one that was not
    // updated would fail silently as a missing header.
    csrf: csrfCookie,
    esc: esc,
    onNavigate: null,          // set by app.js
    onSignOut: null,           // set by app.js
  };

  function boot() {
    renderAccountButton();
    load().then(handleUrl);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
}());
