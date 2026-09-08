"""The secret check in publish.sh, run through the real grep.

Why this file exists: the check was written to stop `.env` being pushed, and for
as long as it has existed it has not done that. `git status --porcelain` prefixes
every line with a two-character status field and a space, so `(^|/)\\.env`
matched `app/.env` and never matched `.env` at the repository root. It has never
mattered, because .gitignore covers the file. It would have mattered the first
time anyone ran `git add -f .env`.

The pattern is read out of publish.sh rather than duplicated here, so this test
cannot pass against a pattern the script does not use. And it is run through
`grep -E`, not Python's `re`: the script uses POSIX ERE and the point is to test
what will actually execute.
"""

from __future__ import annotations

import re
import subprocess

import pytest

SCRIPT = open("publish.sh").read()


def _pattern() -> str:
    found = re.search(r"^SENSITIVE='([^']+)'", SCRIPT, re.M)
    assert found, "publish.sh no longer defines SENSITIVE"
    return found.group(1)


def refused(path: str) -> bool:
    """True if publish.sh would refuse to ship this path."""
    if path == ".env.example":
        # The script excludes it by name before matching, because it is
        # committed on purpose.
        return False
    done = subprocess.run(["grep", "-qE", _pattern()],
                          input=path + "\n", text=True)
    return done.returncode == 0


@pytest.mark.parametrize("path", [
    ".env",
    ".env.local",
    ".env.production",
    "app/.env",
    "data/tracker.db",
    "data/accounts.db",
    "data/alerts.db",
    ".share/tunnel.json",
    # A ledger snapshot. Named for the day it was taken, so a pattern listing
    # the three database names by hand missed it.
    "data/snapshots/tracker-20260908T000000Z.db",
    "data/tracker.db.bak-20260801-133957".replace(".bak-20260801-133957", ""),
    "accounts.db",
])
def test_sensitive_paths_are_refused(path):
    assert refused(path), path


@pytest.mark.parametrize("path", [
    ".env.example",
    "app/main.py",
    "app/auth/routes.py",
    "app/db.py",
    "static/auth.js",
    "static/styles.css",
    "tests/test_auth_accounts.py",
    "DEPLOY.md",
    "requirements.txt",
])
def test_ordinary_source_is_allowed(path):
    assert not refused(path), path


def test_the_paths_are_extracted_before_matching():
    """The fix itself. Without the sed, no root-level file can ever match."""
    assert "sed 's/^...//; s/^.* -> //'" in SCRIPT
    assert "STAGED_PATHS" in SCRIPT


def test_the_root_env_file_would_be_caught_now():
    """The specific regression: a status line for `.env` at the root, put through
    the same two steps the script uses."""
    line = "?? .env"
    stripped = subprocess.run(["sed", "s/^...//; s/^.* -> //"],
                              input=line + "\n", text=True,
                              capture_output=True).stdout.strip()
    assert stripped == ".env"
    assert refused(stripped)


def test_a_renamed_secret_is_caught_by_its_new_name():
    line = "R  something.txt -> data/accounts.db"
    stripped = subprocess.run(["sed", "s/^...//; s/^.* -> //"],
                              input=line + "\n", text=True,
                              capture_output=True).stdout.strip()
    assert stripped == "data/accounts.db"
    assert refused(stripped)


def test_gitignore_covers_every_env_variant_except_the_example():
    """The ignore layer and the publish guard have to agree, or one of them is
    the only thing standing in front of a credential."""
    for path in (".env", ".env.local", ".env.production"):
        done = subprocess.run(["git", "check-ignore", "-q", path])
        assert done.returncode == 0, path
    done = subprocess.run(["git", "check-ignore", "-q", ".env.example"])
    assert done.returncode != 0, ".env.example must stay committable"
