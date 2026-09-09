"""Who owns this deployment.

One boolean, `is_admin`, read from the environment and never from a row.

**Not a column on `users`, and not a roles table.** In order of how much it
matters:

* There is no escalation path through the database. A restored backup, a stray
  UPDATE, an injection that reaches `users` — none of them can mint an
  administrator, because the answer is not kept there. Changing who owns the
  deployment means changing a variable on the host, which is a different
  credential from anything the application itself can write.
* It is how privilege already works here. `OPTIC_WRITE_TOKEN` gates the four
  endpoints that change the ledger, and it is configuration. This is the same
  decision made the same way, so there is one place to look.
* This repository is public, so the address cannot live in the source anyway.

**A configured address is not enough; the account must have proved it holds the
mailbox.** Anyone may type any address into the signup form, so without the
`email_verified` condition this would be privilege escalation by registration:
the first stranger to sign up with the owner's address would *be* the owner.
That condition is the whole gate, and it is why this module is a short policy
function rather than one `in` test.

**There is exactly one privilege level and it is not a hierarchy.** The brief
rules out a role system, and the product has no second kind of privileged person
to model. This answers "does this account own the deployment", nothing else. It
grants no ability to read another person's watchlist, saved research or watches:
those stay scoped to their owner by `user_id`, and admin is not a key to them.
What it removes is the friction of proving ownership to your own server.

Unset, every one of these functions answers no and the app behaves exactly as it
did before the variable existed.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

ENV_NAME = "ADMIN_EMAILS"


def emails() -> frozenset:
    """The configured addresses, lower-cased and stripped.

    Read on each call rather than captured into a module constant at import.
    Nothing here is a hot path — four write endpoints and `/api/auth/me` — so
    the cost is one `split` on a short string. What it buys is that the value
    is not frozen at first import: a test can set the variable, and a host can
    change the owner by editing it, without either depending on import order.

    Lower-cased because `users.email` is stored `COLLATE NOCASE`: the account
    row treats `Alex@x.com` and `alex@x.com` as one mailbox, and a comparison
    here that did not would disagree with the uniqueness constraint that made
    them one account in the first place."""
    raw = os.environ.get(ENV_NAME, "")
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def configured() -> bool:
    """Whether this deployment names an owner at all."""
    return bool(emails())


def is_admin(user: Optional[Dict[str, Any]]) -> bool:
    """Both conditions, and the second is the one doing the work.

    Takes a user dict rather than an id so it cannot be called with something
    the caller has not already authenticated. `is_active` is not re-checked:
    `deps.session_and_user` refuses to resolve a deactivated account at all, so
    a user reaching here came through that gate, and `public_user()` does not
    carry the column to check anyway."""
    if not user:
        return False
    if not user.get("email_verified"):
        return False
    address = (user.get("email") or "").strip().lower()
    return bool(address) and address in emails()


def status(user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Diagnostics, deliberately without the addresses in it.

    `count` and not the list: this shape is safe to hand to a signed-in reader,
    and an endpoint that echoed the configured addresses would turn a private
    setting into a way to harvest the owner's email from a public site."""
    return {
        "configured": configured(),
        "count": len(emails()),
        "admin": is_admin(user),
    }
