"""The owner's front-end checklist for Optic v2 (2026-10-19): no purple gradient, no vague hero text, no fake
reviews or metrics, no scroll animations, no pill-shaped buttons, no emoji icons, no em dashes, no "made
with AI" tag; a favicon, Terms and Privacy pages, a custom domain.

Read from the v2 source as text. The rendered pages were also swept at five sizes for em dashes and checked
in a browser for controls drawn as pills (a corner radius at least half their height).
"""
import re
from pathlib import Path

from tests.test_frontend_v2_stage0 import V2

ROOT = V2.parent.parent
JS = [p for p in (V2 / "js").rglob("*.js")]
CSS = {p.name: p.read_text() for p in (V2 / "css").glob("*.css")}
ALL_CSS = "\n".join(CSS.values())


def _rule(css, selector):
    i = css.index("\n" + selector + " {")
    return css[i:css.index("}", i)]


def test_no_purple_and_no_decorative_gradients():
    assert not re.search(r"purple|violet|indigo|#(8b5cf6|7c3aed|a855f7|9333ea|6d28d9|c084fc|a78bfa)", ALL_CSS, re.I)
    # the only gradients: the rail's divider line and the loading shimmer; the two gold glows went with the
    # design standard (2026-10-19: "no decorative gradients, glow effects")
    assert len(re.findall(r"(linear|radial)-gradient\(", ALL_CSS)) <= 2


def test_buttons_and_controls_are_not_pill_shaped():
    comp, pages = CSS["components.css"], CSS["pages.css"]
    for sel in (".btn", ".seg", ".seg button", ".chip", ".field", ".search-btn", ".account-btn"):
        rule = _rule(comp, sel)
        assert "var(--r-pill)" not in rule and "var(--r-ctl" in rule, sel
    for sel in (".select select", ".ws-presets", ".ws-presets button", ".toast-act"):
        rule = _rule(pages, sel)
        assert "var(--r-pill)" not in rule and "var(--r-ctl" in rule, sel
    assert "--r-ctl: var(--r-md);" in CSS["tokens.css"] and "--r-md: 8px;" in CSS["tokens.css"], "controls are 8px (design standard)"


def test_no_emoji_or_sparkle_icons():
    emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF⭐⭕]")
    for p in JS + [V2 / "index.html"]:
        found = emoji.findall(p.read_text())
        assert not found, (p.name, found[:3])


def test_no_em_dashes_in_what_a_reader_reads():
    for p in JS:
        for n, line in enumerate(p.read_text().splitlines(), 1):
            code = line.split("//")[0]
            if "—" in code and "replace(" not in code:
                raise AssertionError(f"{p.name}:{n} {line.strip()[:80]}")
    assert "—" not in (V2 / "index.html").read_text()


def test_no_made_with_ai_tag_reviews_metrics_or_tracking():
    text = "\n".join(p.read_text() for p in JS) + (V2 / "index.html").read_text()
    for pat in (r"made with (ai|claude)", r"built with (ai|claude)", r"powered by (ai|claude)", r"testimonial",
                r"trusted by", r"loved by", r"\d[\d,]*\+? (traders|users|investors|customers)\b"):
        assert not re.search(pat, text, re.I), pat
    head = (V2 / "index.html").read_text()
    for tracker in ("googletagmanager", "google-analytics", "plausible", "segment.com", "hotjar", "mixpanel"):
        assert tracker not in head, tracker


def test_no_scroll_driven_animation():
    js = "\n".join(p.read_text() for p in JS)
    assert "IntersectionObserver" not in js
    assert "prefers-reduced-motion: reduce" in ALL_CSS


def test_a_favicon_at_every_path_a_browser_asks_for():
    head = (V2 / "index.html").read_text()
    assert 'rel="icon" href="/icon.svg"' in head and 'rel="apple-touch-icon"' in head
    assert (ROOT / "static" / "favicon.ico").stat().st_size > 1000, "browsers and crawlers ask for /favicon.ico"


def test_terms_and_privacy_are_published_and_complete():
    """In force from 2026-10-19 (owner: "draft the legal pages and publish"), with the owner's details."""
    src = (V2 / "js/pages/legalpages.js").read_text()
    assert "export const IN_FORCE = true;" in src and "export const EFFECTIVE = 'October 19, 2026';" in src
    assert "legal-fill" not in src and "Draft for review" not in src, "no field left to fill, no draft banner"
    assert "export const OPERATOR = 'Optic Terminal';" in src and "export const CONTACT = 'theopticterminal@gmail.com';" in src
    assert "Commonwealth of Massachusetts" in src and "at least 13" in src and "children under 13" in src
    router = (V2 / "js/core/router.js").read_text()
    assert "SLUG_VIEW.terms = 'terms';" in router and "SLUG_VIEW.privacy = 'privacy';" in router
    app = (V2 / "js/app.js").read_text()
    assert "terms: legalPages, privacy: legalPages" in app
    legal = (V2 / "js/core/legal.js").read_text()
    assert 'href="#/terms"' in legal and 'href="#/privacy"' in legal, "every page's footer links both"
    for claim in ("Argon2id", "optic_session", "optic_csrf", "optic_ui", "read-only", "Anthropic", "never sees your card number",
                  "Amsterdam, Netherlands", "up to 90 days", "Email delivery is not switched on yet",
                  "without your email address or your account", "We do not sell your personal information"):
        assert claim in src, claim
    for url in ("https://www.anthropic.com/legal/commercial-terms", "https://www.anthropic.com/legal/privacy", "https://snaptrade.com/terms-and-conditions"):
        assert f"out('{url}'" in src, url
    # agreeing: both sign-up forms say so, and the classic footer links the two pages
    assert "you agree to the <a class=\"textlink\" href=\"#/terms\">Terms of use</a>" in (V2 / "js/pages/signin.js").read_text()
    classic_auth = (ROOT / "static/auth.js").read_text()
    assert '<a href="/v2/#/terms" target="_blank" rel="noopener">Terms of use</a>' in classic_auth
    assert '<a href="/v2/#/terms">Terms of use</a> <a href="/v2/#/privacy">Privacy policy</a>' in (ROOT / "static/index.html").read_text()
    assert (ROOT / "docs/frontend-v2/LEGAL-DRAFTS.md").exists()
