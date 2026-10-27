"""The privacy policy says what loads on the page and what is kept.

On 26 October 2026 the policy said "no tracking scripts" while the live site,
served to a browser, carried Cloudflare's Web Analytics beacon, which
Cloudflare adds at its edge. Optic's own pages load no third-party script, and
this pins both halves: the policy names Cloudflare's, and no page in the
repository loads one Optic would have to name."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
LEGAL = (ROOT / "static/v2/js/pages/legalpages.js").read_text()


def test_the_policy_names_cloudflares_script_and_claims_none_of_its_own():
    assert "no tracking scripts." not in LEGAL
    assert "adds no tracking scripts of its own" in LEGAL
    assert "static.cloudflareinsights.com" in LEGAL


def test_optics_own_pages_load_no_third_party_script():
    srcs = []
    for page in list((ROOT / "static").glob("*.html")) + list((ROOT / "static/v2").glob("*.html")):
        srcs += re.findall(r"<script[^>]+src=[\"']([^\"']+)", page.read_text())
    assert srcs and all(not s.startswith(("http:", "https:", "//")) for s in srcs), srcs


def test_the_policy_describes_the_email_log_and_the_recovery_copies_as_they_now_work():
    assert "without the link" in LEGAL and "written to the server log instead" not in LEGAL
    assert "Daily copies of the accounts database, kept for 7 days" in LEGAL
