"""One person, one Optic account, however many ways they sign in.

This is the module the whole provider story turns on, so the rules are written
out rather than left implicit in a chain of ifs.

**The identity is the provider's subject id, never the email address.** Google's
`sub` and Apple's `sub` are stable for the lifetime of the account; the email is
not. People change their Gmail address, Apple hands out a different private-relay
address to every app, and an address can be reassigned by a corporate admin to a
different human being. Keying on email would mean the second person inherits the
first person's account.

**Four outcomes, and why each exists.**

* `signed_in` — this provider identity is already attached to an Optic account.
  The only question was which one.
* `created` — nothing matched, so this is a new person.
* `linked` — the provider proved control of an address that an existing verified
  Optic account also proved control of. Both sides verified means both sides
  demonstrated access to the same mailbox, so this is the same person and the
  identity is attached to the existing account. This is the case that stops one
  person accumulating three accounts because they clicked a different button.
* `needs_link` — an account exists with that address, but one side of it is
  unverified. **Not linked, and not duplicated.** The reader is asked to sign in
  with what they already have and connect the provider from Settings.

**Why `needs_link` is not just "link it anyway".** If an Optic account was made
with an unverified email, anyone could have typed that address. Auto-linking a
Google identity to it would hand the Google account's owner an account somebody
else created and may already have data in. And in reverse: a provider that has
not verified an address has not established that its holder owns the mailbox, so
treating it as proof would let a provider account with an attacker-chosen email
claim any Optic account with that address. The brief's rule, and the right one,
is that ambiguity means authenticate into the existing account first.

**Private relay is never a match key.** An Apple private-relay address is unique
per app, so it cannot collide with an address a person typed into this site. It
is stored and used for delivery, and skipped when looking for an account to link.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from . import store

log = logging.getLogger("optic.linking")

PROVIDER_LABELS = {"google": "Google", "apple": "Apple", "email": "Email"}


def label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, provider.title())


def resolve(profile: Dict[str, Any],
            link_user_id: Optional[str] = None) -> Dict[str, Any]:
    """Turn a verified provider profile into an outcome.

    `link_user_id` is set when an already-signed-in reader is connecting a
    provider from Settings. That is the one path where the answer to "whose
    account is this" comes from the session rather than from a match, and it is
    also the secure linking flow `needs_link` sends people to.
    """
    provider = profile["provider"]
    subject = profile["subject"]
    email = profile.get("email")
    provider_verified = bool(profile.get("email_verified"))
    relay = bool(profile.get("private_relay"))

    existing = store.get_identity(provider, subject)

    # ------------------------------------------------ connecting to this session
    if link_user_id:
        if existing and existing["user_id"] != link_user_id:
            # Someone else's. Moving it would sign that person out of their own
            # account permanently, so it is refused with a message that says
            # which account is in the way without naming it.
            return {"outcome": "taken", "provider": provider,
                    "reason": "That {} account is already connected to another Optic "
                              "Terminal account.".format(label(provider))}
        if existing:
            store.touch_identity(existing["id"], email)
            return {"outcome": "signed_in", "user": store.get_user(link_user_id),
                    "provider": provider}
        store.add_identity(link_user_id, provider, subject, email)
        return {"outcome": "linked", "user": store.get_user(link_user_id),
                "provider": provider}

    # ---------------------------------------------------------- already attached
    if existing:
        user = store.get_user(existing["user_id"])
        if not user or not user.get("is_active"):
            return {"outcome": "inactive", "provider": provider,
                    "reason": "That account is not active."}
        store.touch_identity(existing["id"], email)
        return {"outcome": "signed_in", "user": user, "provider": provider}

    # ------------------------------------------------------------- no email at all
    #
    # Apple can return a sign-in with no address when the reader declined to
    # share one and there is no first-authorization payload to read it from.
    # There is nothing to create an account around: `users.email` is the only
    # handle the product has for a person, and inventing a placeholder mailbox
    # would produce an account that can never receive a reset link.
    if not email:
        return {"outcome": "no_email", "provider": provider,
                "reason": "{} did not share an email address, so there is nothing to "
                          "attach an account to. Sign in again and choose to share "
                          "your address, or create an account with an email and "
                          "password.".format(label(provider))}

    # ----------------------------------------------------- an account with this address
    match = store.get_user_by_email(email)
    if match:
        both_verified = provider_verified and bool(match.get("email_verified"))
        if both_verified and not relay:
            store.add_identity(match["id"], provider, subject, email)
            log.info("linked %s identity to existing verified account", provider)
            return {"outcome": "linked", "user": match, "provider": provider}
        return {
            "outcome": "needs_link", "provider": provider, "email": email,
            "reason": "An Optic Terminal account already uses that email address. Sign "
                      "in the way you did before, then connect {} under Settings, "
                      "Security. That keeps one account instead of "
                      "two.".format(label(provider)),
        }

    # ----------------------------------------------------------------- new person
    user = store.create_user(
        email=email,
        first_name=profile.get("first_name") or "",
        last_name=profile.get("last_name") or "",
        # Trusting the provider's flag rather than sending our own verification
        # email: Google and Apple both confirm the address before issuing a
        # token, and asking again would be asking someone to prove something
        # they just proved.
        email_verified=provider_verified,
        avatar_url=profile.get("avatar_url"),
    )
    store.add_identity(user["id"], provider, subject, email)
    return {"outcome": "created", "user": user, "provider": provider}
