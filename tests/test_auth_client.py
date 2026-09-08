"""Client-side contracts, asserted by reading `static/auth.js` and `static/app.js`.

There is no JS test runner in this project and this file is not pretending to be
one. It exists because every silent client failure in this codebase has been a
*wiring* failure rather than a logic one: a handler that was never attached, a
key that no longer matches, a script tag that was not added. Those are visible
in the text. Behaviour was verified in a real browser, including a full passkey
ceremony against Chrome's authenticator.

See `tests/test_ui_refactor.py` for the same pattern applied to the interface.
"""

from __future__ import annotations

import re

import pytest

AUTH_JS = open("static/auth.js").read()
APP_JS = open("static/app.js").read()
INDEX = open("static/index.html").read()
CSS = open("static/styles.css").read()


# --------------------------------------------------------------------- wiring


def test_auth_js_is_loaded_before_app_js():
    """app.js reads `window.OpticAuth` while it evaluates, so the order is not
    cosmetic. Reversed, the account-aware stores silently fall back to
    localStorage for the whole session."""
    assert 'src="auth.js' in INDEX
    assert INDEX.index('src="auth.js') < INDEX.index('src="app.js')


def test_the_topbar_has_a_slot_for_the_account_control():
    assert 'id="account-slot"' in INDEX
    assert "getElementById('account-slot')" in AUTH_JS


def test_auth_js_is_in_the_asset_cache_key():
    """The ?v= query is derived from asset mtimes in app/main.py. A file missing
    from that list ships new HTML paired with a stale copy of itself, which
    presents as a feature that silently does not work."""
    main = open("app/main.py").read()
    assert 'for name in ("app.js", "auth.js", "charts.js", "styles.css")' in main


# -------------------------------------------------------------------- session


def test_no_token_is_ever_put_in_localstorage():
    """The session is an HttpOnly cookie. A token in localStorage is readable by
    any script on the page, which is the whole reason the cookie is HttpOnly."""
    for key in ("optic.session", "optic.token", "sessionToken", "authToken",
                "access_token", "bearer"):
        assert key not in AUTH_JS, key
    # The only cookie this file reads is the CSRF value, which exists to be read.
    # Matched to end of line rather than to the next semicolon: the cookie is
    # read through a regex literal that contains one.
    reads = re.findall(r"document\.cookie.*", AUTH_JS)
    assert len(reads) == 1, reads
    assert "optic_csrf" in reads[0], reads[0]
    # Nothing writes a cookie from JavaScript. Every cookie this app sets comes
    # from a Set-Cookie header, which is the only way to get HttpOnly.
    assert "document.cookie =" not in AUTH_JS
    assert "document.cookie=" not in AUTH_JS


def test_every_request_sends_cookies_and_state_changes_send_the_csrf_header():
    assert "credentials: 'same-origin'" in AUTH_JS
    assert "'X-Optic-CSRF'" in AUTH_JS
    # And only on the verbs that change something: a GET does not need it, and
    # adding it there would mean a preflight on every read.
    assert "if (method !== 'GET' && method !== 'HEAD')" in AUTH_JS


def test_the_state_machine_has_three_states_not_two():
    """Collapsing `loading` into `guest` is what makes an app flash a signed-out
    header at somebody who is signed in."""
    assert "status: 'loading'" in AUTH_JS
    assert "if (STATE.status === 'loading')" in AUTH_JS
    assert "renderAccountButton" in AUTH_JS


def test_one_state_read_serves_the_whole_first_paint():
    """Four endpoints would be four round trips before anything renders."""
    calls = re.findall(r"api\('(/api/auth/[a-z-]+)'\)", AUTH_JS)
    assert calls.count("/api/auth/me") == 1
    for field in ("providers", "methods", "preferences", "subscription",
                  "password_policy"):
        assert field in AUTH_JS, field


# ------------------------------------------------------------------ passkeys


def test_the_passkey_ceremony_converts_every_binary_field():
    """A field left as base64 text where the API wants an ArrayBuffer fails in
    the browser with a TypeError and never reaches the server."""
    for field in ("challenge", "user.id", "rawId", "clientDataJSON",
                  "attestationObject", "authenticatorData", "signature"):
        assert field.split(".")[-1] in AUTH_JS, field
    assert "b64urlToBytes(options.challenge)" in AUTH_JS
    assert "b64urlToBytes(options.user.id)" in AUTH_JS
    assert "bytesToB64url(credential.rawId)" in AUTH_JS
    # excludeCredentials and allowCredentials are lists of buffers, not strings.
    assert AUTH_JS.count("id: b64urlToBytes(item.id)") == 2


def test_a_cancelled_passkey_is_not_reported_as_an_error():
    """NotAllowedError is "pressed escape" and "timed out". Neither is a fault
    and neither deserves a red banner."""
    assert "err.name === 'NotAllowedError'" in AUTH_JS
    assert "passkeyCancelled" in AUTH_JS
    assert "if (passkeyCancelled(err)) return;" in AUTH_JS


def test_the_rp_id_failure_names_the_localhost_trap():
    """A wrong RP id is rejected by the browser before any request is sent, so
    there is nothing in the server log to find. The message has to carry it."""
    assert "err.name === 'SecurityError'" in AUTH_JS
    assert "127.0.0.1" in AUTH_JS


def test_passkeys_are_hidden_where_they_cannot_work():
    assert "window.isSecureContext" in AUTH_JS
    assert "passkeysSupported()" in AUTH_JS


# ------------------------------------------------------------------ providers


def test_an_unconfigured_provider_shows_no_button():
    """A dead button reads as a broken site. The server says which providers it
    has credentials for, and the row is built from that."""
    assert "function providerAvailable(name)" in AUTH_JS
    assert "providerAvailable('apple')" in AUTH_JS
    assert "providerAvailable('google')" in AUTH_JS


def test_provider_sign_in_is_a_full_page_redirect():
    """A popup is blocked as often as it works, and Apple refuses to render in
    one."""
    assert "location.href = '/api/auth/' + name + '/start'" in AUTH_JS
    assert "window.open" not in AUTH_JS


def test_callback_outcomes_arrive_as_codes_and_are_mapped_client_side():
    """A server-generated sentence echoed through a query string is a reflection
    this app does not need to own."""
    assert "OAUTH_ERRORS" in AUTH_JS
    for code in ("state", "provider", "config", "taken", "needs_link", "no_email",
                 "inactive", "denied"):
        assert code + ":" in AUTH_JS, code


def test_emailed_links_are_handled_by_the_page_not_by_a_get_endpoint():
    """A GET that consumed the token would be spent by any mail client that
    prefetches links, and several do."""
    assert "params.get('verify')" in AUTH_JS
    assert "params.get('reset')" in AUTH_JS
    assert "api('/api/auth/verify-email', { method: 'POST'" in AUTH_JS
    # And the token is removed from the address bar either way.
    assert "scrubUrl(['verify'])" in AUTH_JS
    assert "scrubUrl(['reset'])" in AUTH_JS


def test_the_next_parameter_is_relative_only():
    """An absolute URL here would make sign-in an open redirect."""
    assert "next.charAt(0) === '/' && next.charAt(1) !== '/'" in AUTH_JS


# ------------------------------------------------------- accessibility of the dialog


def test_the_dialog_is_a_dialog_and_traps_focus():
    assert 'role="dialog"' in AUTH_JS
    assert 'aria-modal="true"' in AUTH_JS
    assert 'aria-labelledby="auth-title"' in AUTH_JS
    assert "evt.key === 'Escape'" in AUTH_JS
    assert "evt.key !== 'Tab'" in AUTH_JS
    # Focus goes back where it came from, or a keyboard user is left nowhere.
    assert "lastFocus.focus()" in AUTH_JS


def test_password_fields_carry_the_right_autocomplete_tokens():
    """Wrong tokens make a password manager save the new password over the old
    one, or offer the account password in a "new password" field."""
    assert "'current-password'" in AUTH_JS
    assert "'new-password'" in AUTH_JS
    # `username webauthn` is what lets the browser offer a passkey from the
    # email field itself.
    assert "username webauthn" in AUTH_JS


def test_the_provider_buttons_meet_the_pointer_target_size():
    """WCAG 2.5.8 asks for 24x24; 44px is the comfortable touch figure and these
    are the first thing on the screen on a phone."""
    block = CSS[CSS.index(".auth-provider {"):]
    assert "min-height: 44px" in block[:400]


# ---------------------------------------------------------- the app.js bridge


def test_the_stores_stay_synchronous():
    """`watchList()` and `savedResearch()` are called from render paths all over
    app.js. Making either async would mean rewriting every caller, so the
    account's copy is loaded once into ACCOUNT and read from there."""
    assert "function watchList() {" in APP_JS
    assert "function savedResearch() {" in APP_JS
    assert "async function watchList" not in APP_JS
    assert "async function savedResearch" not in APP_JS
    assert "if (ACCOUNT.watchlist) return ACCOUNT.watchlist.slice();" in APP_JS
    assert "if (ACCOUNT.research) return ACCOUNT.research;" in APP_JS


def test_a_guest_still_gets_the_local_stores():
    """Accounts are additive. Nothing that worked without one may stop working."""
    assert "function localWatchList()" in APP_JS
    assert "function localSavedResearch()" in APP_JS
    assert "return localWatchList();" in APP_JS
    assert "return localSavedResearch();" in APP_JS


def test_signing_out_does_not_leave_the_account_copy_behind():
    assert "ACCOUNT.watchlist = null;" in APP_JS
    assert "window.OpticAuth.onSignOut" in APP_JS


def test_a_failed_account_load_falls_back_rather_than_emptying_the_page():
    """A watchlist that vanishes because one request failed is worse than a
    watchlist that is briefly the local one."""
    block = APP_JS[APP_JS.index("async function accountLoad()"):]
    block = block[:block.index("async function loadAllowance")]
    assert "catch (err)" in block
    assert "ACCOUNT.watchlist = null;" in block


def test_saving_as_a_guest_saves_first_and_offers_second():
    """The conversion moment, without taking anything away: the question is
    already in this browser before the offer appears."""
    block = APP_JS[APP_JS.index("function saveResearch(entry)"):]
    block = block[:block.index("function dropResearch")]
    assert "localStorage.setItem(RESEARCH_KEY" in block
    assert block.index("localStorage.setItem(RESEARCH_KEY") < block.index("offerAccountForResearch")
    assert "researchOfferShown" in APP_JS         # once a session, not once a click


def test_the_settings_page_no_longer_claims_nothing_is_stored_on_the_server():
    """It was true before accounts existed. Leaving it would be a false claim on
    the one page that is about what is stored where."""
    assert "'Stored on the server', signedIn()" in APP_JS
    assert "Your account: name, email, watchlists" in APP_JS


def test_the_allowance_is_stated_before_the_click_not_after():
    """A 429 arriving mid-answer reads as the assistant being broken. The same
    fact in advance reads as a limit."""
    assert "renderAllowanceNote" in APP_JS
    assert "/api/ai-allowance" in APP_JS
    assert "loadAllowance();" in APP_JS
    assert "Create a free account" in APP_JS


def test_provider_linking_from_settings_uses_the_session_not_a_query_parameter():
    assert "'/start?link=1&next='" in APP_JS


def test_a_hidden_form_that_sets_display_also_resets_it_when_hidden():
    """An author `display` beats the UA stylesheet's `[hidden] { display: none }`
    whatever the specificity, so the password form rendered open on every visit
    to Settings until this pair existed."""
    assert ".set-pw[hidden] { display: none; }" in CSS


@pytest.mark.parametrize("selector", [
    ".account-slot", ".acct-btn", ".acct-face", ".acct-menu", ".auth-modal",
    ".auth-card", ".auth-provider", ".auth-field", ".auth-error", ".auth-toast",
    ".auth-promo", ".set-row", ".set-tag", ".set-guest", ".chat-allow",
    ".auth-toast-act", ".set-pw", ".set-h3",
])
def test_every_class_the_scripts_emit_has_a_rule(selector):
    """The other direction from the dead-class sweep: a class with no rule is an
    unstyled element, which on a dark page is often invisible rather than ugly."""
    assert selector + " " in CSS or selector + "," in CSS or selector + "{" in CSS \
        or selector + " {" in CSS, selector


def test_no_hex_colours_were_introduced_in_the_accounts_stylesheet():
    """Tokens only, per the design system. The one exception is the Google mark,
    whose four brand colours are part of the logo and are not Optic's to
    re-theme."""
    block = CSS[CSS.index("   Accounts"):]
    hexes = set(re.findall(r"#[0-9a-fA-F]{3,8}\b", block))
    assert not hexes, hexes
    brand = set(re.findall(r"#[0-9a-fA-F]{6}", AUTH_JS))
    assert brand == {"#4285F4", "#34A853", "#FBBC05", "#EA4335"}, brand
