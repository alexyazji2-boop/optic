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
    # The open paren matters. Named lists brought watchListSwitch, Create,
    # Rename, Delete and Move, all legitimately async, and a prefix match called
    # every one of them a violation of a rule about watchList() itself.
    assert "async function watchList(" not in APP_JS
    assert "async function savedResearch(" not in APP_JS
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


# ----------------------------------------------------------------- watches


def test_the_watch_builder_is_generated_from_the_server_catalogue():
    """Not hand-listed. The evaluator compares the stored parameter as a string,
    so a UI with its own vocabulary produces a watch that stores fine, evaluates
    fine and never fires. Three of them did."""
    assert "/api/watches/catalogue" in APP_JS
    assert "watchCondition(" in APP_JS
    assert "p.choices.map(" in APP_JS
    # Scoped to the watches section. These words appear elsewhere in app.js for
    # good reasons — the insider table renders `action`, the earnings panel
    # colours a revision direction — and a whole-file check flagged those. That
    # those panels use `action === 'purchase'` is itself the corroboration that
    # the evaluator reading `kind` was out of step with the rest of the app.
    block = APP_JS[APP_JS.index("const WATCHES_KEY"):
                   APP_JS.index("/** A short relative stamp")]
    for invented in ("'rising'", "'falling'", "'purchase'", "'leaning bullish'",
                     "'bearish'", "'sale'"):
        assert invented not in block, invented


def test_the_builder_draft_survives_a_condition_change():
    """Changing the condition re-renders the block, because the parameter
    field's kind changes with it. That re-render used to eat the symbol somebody
    had already typed."""
    assert "const watchDraft" in APP_JS
    assert "watchDraft.symbol || STATE.ticker" in APP_JS
    assert "data-watch-draft" in APP_JS


def test_newness_is_computed_two_ways_because_there_are_two_kinds_of_condition():
    """A level watch carries no `state`, so reading `state` for both put a level
    watch at "still met" on the very first trip it ever had."""
    block = APP_JS[APP_JS.index("async function checkWatchSymbol"):]
    block = block[:block.index("async function checkAllWatches")]
    assert "metBefore" in block
    assert "if (r.state) {" in block
    assert "r.first_seen = !was.metBefore;" in block


def test_watches_are_checked_one_symbol_at_a_time():
    """Each check is the full analysis payload, roughly twenty seconds of
    provider calls. Ten in parallel is three minutes and a rate limit."""
    block = APP_JS[APP_JS.index("async function checkAllWatches"):]
    block = block[:block.index("/* ------")]
    assert "await checkWatchSymbol(symbol);" in block
    assert "Promise.all" not in block


def test_the_alerts_view_says_a_watch_is_not_a_push_notification():
    """Nothing here can reach a phone, and an alert that silently misses the
    move it was created for is worse than no alert."""
    assert "Checked while Optic is open" in APP_JS
    # Matched without crossing the line break the source wraps at.
    assert "not pushed to you" in APP_JS
    assert "can send you a notification" in APP_JS


def test_your_watches_render_even_when_the_scan_feed_is_unreachable():
    """Two different endpoints with no dependency on each other. The scan feed
    failing is not a reason to hide the watches somebody set."""
    block = APP_JS[APP_JS.index("function renderAlerts()"):]
    block = block[:block.index("/* ==========")]
    assert block.count("renderWatchesBlock()") == 3


def test_the_builder_does_not_borrow_the_settings_row_control_class():
    """`.settings-select` carries `flex: 0 1 340px`, written for a row layout
    where 340px is a width. `.wd-param` is a column, so flex-basis became the
    main-axis size and every input rendered 340px tall."""
    block = APP_JS[APP_JS.index("function renderWatchesBlock()"):]
    block = block[:block.index("document.addEventListener('input'")]
    assert "settings-select" not in block
    assert ".wd-param input, .wd-param select {" in CSS
    assert "min-height: 38px" in CSS[CSS.index(".wd-param input, .wd-param select {"):][:400]


@pytest.mark.parametrize("selector", [
    ".wd-block", ".wd-new", ".wd-param", ".wd-row", ".wd-chip", ".wd-sym-head",
    ".wd-price", ".wd-list", ".wd-btn", ".wd-foot", ".wd-err", ".wd-why",
])
def test_every_watch_class_has_a_rule(selector):
    assert selector + " " in CSS or selector + "," in CSS or selector + "{" in CSS \
        or selector + " {" in CSS, selector


# ------------------------------------------- the rest of the product brief


def test_every_ask_pulse_topic_used_is_a_topic_defined():
    """The dead-control class, in both directions.

    `askPulse('bookrisk')`, `askPulse('instrument')` and `askPulse('relperf')`
    were all in the markup with no entry in PULSE_TOPICS, and `openPulseWith`
    returns early on an unknown topic — so three buttons rendered, took a click
    and did nothing. Nothing errors; the panel simply does not open, which is
    indistinguishable from a slow response.

    The other direction matters too: `indicators` was defined and attached to
    nothing, which is a prompt nobody could reach.
    """
    start = APP_JS.index("const PULSE_TOPICS = {")
    end = APP_JS.index("\n};", start)
    defined = set(re.findall(r"^\s{2}'?([a-zA-Z-]+)'?:", APP_JS[start:end], re.M))
    used = set(re.findall(r"askPulse\('([a-zA-Z-]+)'\)", APP_JS))
    assert defined, "no topics parsed, so this test is checking nothing"
    assert used - defined == set(), sorted(used - defined)
    assert defined - used == set(), sorted(defined - used)


def test_the_panels_the_product_brief_added_all_have_a_contextual_action():
    """Five panels shipped from the earlier brief with no Ask Pulse at all."""
    for topic in ("invalidate", "optionsactivity", "whatsnext", "setup", "whymoving"):
        assert "askPulse('{}')".format(topic) in APP_JS, topic


def test_the_invalidation_prompt_carries_the_thesis_that_was_written():
    """Four labelled fields, not one blob. Reading a `text` key the store does
    not have produced an empty string, and a prompt asking for a
    counter-argument to nothing gets a confident essay about nothing."""
    assert "{thesis}" in APP_JS
    block = APP_JS[APP_JS.index("function openPulseWith(topic)"):]
    block = block[:block.index("\n}")]
    for field in ("saved.bull", "saved.bear", "saved.catalysts", "saved.invalidation"):
        assert field in block, field
    assert "saved.text" not in block
    # And the empty case says so rather than sending an empty thesis.
    assert "I have not written one yet" in APP_JS


def test_the_price_head_is_the_first_thing_on_the_asset_page():
    block = APP_JS[APP_JS.index("  const html = `"):]
    block = block[:block.index("</div>`")]
    assert block.index("renderPriceHead") < block.index("renderOpticPulse")


def test_the_price_itself_is_not_coloured_by_direction():
    """A price painted red reads as "this number is wrong" rather than "it is
    down today", and it is the same number whichever way the day went."""
    assert ".px-chg.up, .px-chg-pct.up { color: var(--pos); }" in CSS
    block = CSS[CSS.index(".px-last {"):]
    block = block[:block.index("}")]
    assert "--pos" not in block and "--neg" not in block


def test_the_chart_is_second_on_a_phone_and_back_in_its_grid_on_a_desktop():
    """Both ids are static, in the markup. The first version generated one at
    runtime and looked it up to move the panel back, which does not survive the
    20-second repaint this view is on."""
    assert 'id="swing-chart-grid"' in APP_JS
    assert 'id="swing-chart-panel"' in APP_JS
    block = APP_JS[APP_JS.index("function orderAssetPageForPhone()"):]
    block = block[:block.index("\n}")]
    assert "head.insertAdjacentElement('afterend', panel)" in block
    assert "grid.insertBefore(panel, grid.firstChild)" in block
    assert "Math.random" not in block


def test_intraday_ranges_on_the_workspace_use_the_intraday_endpoint():
    """1D and 5D drew the full daily history. `sliceSeries` reads `spec.daily`,
    which is undefined on an intraday spec, so `Math.min(undefined, total)` is
    NaN and `arr.slice(NaN)` returns everything."""
    block = APP_JS[APP_JS.index("function wsSeries(d)"):]
    block = block[:block.index("/** Current window")]
    assert "isIntradayRange(chartRange)" in block
    assert "wsIntradayStub" in block
    assert "/api/intraday/" in APP_JS


def test_drawings_are_hidden_rather_than_replayed_onto_intraday_bars():
    """Drawings store a bar index. Index 120 on a daily series and on a
    five-minute series are different moments by a factor of about eighty."""
    block = APP_JS[APP_JS.index("function wsRenderDrawings()"):]
    block = block[:block.index("const NS =")]
    assert "isIntradayRange(chartRange)" in block
    assert "layer.innerHTML = ''" in block


def test_the_status_line_reports_the_interval_on_screen():
    """It said "daily" over five-minute bars, which is a false claim about what
    is being looked at."""
    assert "wsIntraday && wsIntraday.interval" in APP_JS
    assert APP_JS.count("wsIntraday && wsIntraday.interval") >= 3


def test_hidden_is_a_different_state_from_off():
    """Off forgets the overlay's settings; hidden keeps the row, the settings and
    the reading, and only stops the line being drawn."""
    assert "function seriesDrawn(id)" in APP_JS
    assert "function overlayHidden(id)" in APP_JS
    assert "function wsOverlayDrawn(id)" in APP_JS
    # The drawing filters use seriesDrawn; the legend still uses seriesShown.
    assert APP_JS.count("].filter(([id]) => seriesDrawn(id))") == 5
    assert "].filter(([id]) => seriesShown(id))" not in APP_JS
    # And the eye has a handler now.
    assert "data-ws-hide" in APP_JS
    assert "setOverlayHidden(id, !overlayHidden(id))" in APP_JS
    assert "data-ws-hide has no handler" not in APP_JS


def test_earnings_dates_are_vertical_markers_not_direction_triangles():
    """An earnings date has no direction, so the insider layer's triangle would
    be claiming one."""
    assert "function earningsMarkers(ps, earnings)" in APP_JS
    assert "vMarkers: earningsMarkersFor(ps, STATE.ticker)" in APP_JS
    assert "vMarkers: earningsMarkersFor(ps, STATE.chartSymbol)" in APP_JS
    # The bar lookup is shared, not copied. Its comment records a real bug.
    assert APP_JS.count("function barIndexForDate") == 1
    assert APP_JS.count("const mid = Math.ceil((lo + hi) / 2);") == 1


def test_vmarkers_render_the_detail_they_are_given():
    """`detail` was accepted by callers and rendered by nothing, so a marker
    labelled "E" was a date and nothing else."""
    charts = open("static/charts.js").read()
    block = charts[charts.index("vMarkers.forEach((mk) => {"):]
    block = block[:block.index("/* Reference-line labels")]
    assert "s('title', {}, mk.detail)" in block
    assert "fill: 'transparent'" in block          # a hover target for a 1.4px line


def test_the_compare_bars_use_the_same_threshold_as_the_take():
    """The bars exist to show the gap, and the wording about whether the gap is
    decisive must not disagree with the headline above it."""
    block = APP_JS[APP_JS.index("function renderCompareBars(c)"):]
    block = block[:block.index("function renderCompare(c)")]
    assert "gap >= 8" in block
    take = open("app/analytics/compare.py").read()
    assert "0.08" in take or "8" in take


def test_a_composite_score_bar_is_not_painted_with_the_directional_pair():
    """Every one of these is positive by construction, so green would claim a
    direction the number does not carry."""
    block = CSS[CSS.index(".cb-fill {"):]
    block = block[:block.index("}")]
    assert "--pos" not in block and "--neg" not in block


def test_the_watchlist_filter_is_scoped_to_the_view_with_the_controls():
    """A filter set on the Watchlist tab quietly emptying the home page's
    six-row summary would look like the home page was broken."""
    block = APP_JS[APP_JS.index("function watchlistFeedHTML(opts)"):]
    block = block[:block.index("/* ====")]
    # The compact branch must be the unfiltered set. Asserted as the branch
    # rather than as one literal expression, because the full branch also picks
    # up the in-list search and this was matching the whole line.
    assert re.search(r"o\.compact \? all : ", block), "the compact feed is being narrowed"
    assert "all.filter((r) => spec.keep(r))" in block
    # And an empty result names the filter rather than looking like data loss.
    assert "matches" in block and "Show all" in block


def test_the_watchlist_does_not_pretend_to_filter_by_sector():
    """The feed is one batched history call, which is the difference between a
    2-second panel and a 30-second one. Sector needs a per-symbol lookup."""
    assert "Sector is not a filter on this feed" in APP_JS
    ids = re.findall(r"\{ id: '([a-z]+)', label: '[^']*', keep:", APP_JS)
    assert "sector" not in ids, ids


def test_natural_language_screening_needs_both_a_verb_and_a_noun():
    """"find" alone matches "find me the NVDA earnings date"; "stocks" alone
    matches "why are stocks down", which is a question, not a request for a
    list."""
    block = APP_JS[APP_JS.index("function looksLikeScreen(text)"):]
    block = block[:block.index("\n}")]
    assert "SCREEN_INTENT.test(t) && SCREEN_NOUNS.test(t)" in block


def test_the_screen_matcher_scores_the_id_as_well_as_the_name():
    """"breaking out" reached "High-risk swings, upside" and not the screen
    literally called `breakout`, whose name is "At 52-week highs"."""
    block = APP_JS[APP_JS.index("function screenMatches(text, catalogue)"):]
    block = block[:block.index("\n}")]
    assert "String(s.id" in block
    assert "s.looks_for" in block


def test_the_sector_caveat_cannot_become_the_default_action():
    """It was its own row above the screens, which put it at paletteIndex 0 —
    and Enter runs paletteIndex 0. The honest note about what the screens cannot
    do became the default action."""
    block = APP_JS[APP_JS.index("if (looksLikeScreen(q)) {"):]
    block = block[:block.index("return rows;")]
    assert "const caveat = sector" in block
    assert "detail: caveat + String(s.looks_for" in block
    # Exactly one row may claim the enter hint.
    # Matched through the constant, not the literal. The group name is both a
    # label and a comparison key, so it lives in ASK_GROUP: renaming the label
    # alone would leave this branch reading a name nothing produces, and two
    # rows would both claim the return key without anything throwing.
    assert "if (r.group === ASK_GROUP) r.tag = ''" in block
    assert "const ASK_GROUP = 'Ask Pulse';" in APP_JS
