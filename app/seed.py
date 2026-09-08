"""A development account, for working on signed-in surfaces without signing up.

    .venv/bin/python -m app.seed

**Development only, enforced rather than documented.** It refuses to run when a
hosting platform is present, so it cannot create a known account on the live
site by accident. `--force` exists for a self-hosted box that is genuinely a
development environment; it has to be typed.

**No hardcoded password.** The password is generated per run and printed once.
A fixture password in source is a password on every deployment that ever ran the
seed, and it would be in the repository, which is the one place it must not be.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from typing import List

from . import db
from .account import ensure_default
from .auth import passwords as pw, store
from .runtime import is_hosted

DEMO_EMAIL = "demo@opticterminal.com"
DEMO_SYMBOLS: List[str] = ["NVDA", "AAPL", "TSLA", "SPY", "QQQ"]


def _password() -> str:
    """Four words and a number. Long enough to pass the policy, short enough to
    type from a terminal into a browser."""
    words = ["harbour", "lantern", "granite", "meadow", "cobalt", "thistle",
             "compass", "juniper", "quarry", "saffron", "tundra", "walnut"]
    picked = [secrets.choice(words) for _ in range(3)]
    return "-".join(picked) + "-" + str(secrets.randbelow(90) + 10)


def seed(force: bool = False, reset: bool = False) -> int:
    if is_hosted() and not force:
        print("Refusing to seed: this looks like a hosted environment "
              "(RAILWAY_ENVIRONMENT or similar is set).", file=sys.stderr)
        print("A seeded account with a printed password does not belong on a live "
              "site. Pass --force only if this really is a development box.",
              file=sys.stderr)
        return 2

    db.migrate()
    existing = store.get_user_by_email(DEMO_EMAIL)
    if existing and not reset:
        print("Development account already exists: {}".format(DEMO_EMAIL))
        print("Run with --reset to delete it and make a new one with a new password.")
        return 0
    if existing:
        store.delete_user(existing["id"])
        print("Deleted the previous development account and everything it owned.")

    password = _password()
    user = store.create_user(DEMO_EMAIL, "Demo", "Reader", email_verified=True)
    store.add_identity(user["id"], "email", DEMO_EMAIL, DEMO_EMAIL)
    store.set_password(user["id"], pw.hash_password(password), pw.ALGO)

    watchlist = ensure_default(user["id"])
    from .account import _put_symbols          # local: seeding is not a hot path
    _put_symbols(watchlist["id"], DEMO_SYMBOLS)
    store.set_preferences(user["id"], {"time_zone": "America/New_York",
                                       "default_landing": "watchlist"})

    print("")
    print("  Development account created (this environment only)")
    print("  ------------------------------------------------------")
    print("  email     {}".format(DEMO_EMAIL))
    print("  password  {}".format(password))
    print("")
    print("  Printed once and not stored anywhere. Run --reset for a new one.")
    print("  Watchlist seeded with: {}".format(", ".join(DEMO_SYMBOLS)))
    print("  Database: {}".format(db.DB_PATH))
    print("")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a development account.")
    parser.add_argument("--force", action="store_true",
                        help="seed even though a hosting platform was detected")
    parser.add_argument("--reset", action="store_true",
                        help="delete the existing development account first")
    args = parser.parse_args()
    raise SystemExit(seed(force=args.force, reset=args.reset))
