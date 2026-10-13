"""Client contracts from the strategy pass (2026-10-12).

Read as text, the house pattern for wiring (CLAUDE.md): every silent client
failure here has been a wiring failure. Behaviour was checked in a browser;
these stop the wiring from being undone.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")


def body(name: str) -> str:
    start = APP.index("function " + name + "(")
    nxt = re.search(r"\n(?:async )?function |\nconst [A-Z_]+ = ", APP[start + 10:])
    return APP[start:start + 10 + (nxt.start() if nxt else 4000)]


def test_milo_sees_what_the_overview_shows():
    payload = body("chatContextPayload")
    for key in ("cases", "why", "whats_next", "pulse", "next_earnings_date", "sector_confirm",
                "earnings_momentum"):
        assert "ctx.%s = s.%s" % (key, key) in payload, key
    assert "STATE.ovLongData" in payload, "the Overview's long-term payload reaches Milo"


def test_the_overview_keeps_long_term_data_without_prefilling_the_investing_tab():
    loader = body("loadOverviewLongScore")
    assert "STATE.ovLongData" in loader
    assert "STATE.long = data" not in loader, (
        "a pre-filled STATE.long sends Investing down its cached path and skips the P/E history")


def test_the_timeframe_is_sent_and_kept_as_a_setting():
    assert "horizon: miloHorizon" in APP
    assert "const MILO_HORIZON_KEY = 'optic.milo.horizon.v1'" in APP
    assert "data-hz-pick" in body("miloHorizonHTML")
    assert "localStorage.setItem(MILO_HORIZON_KEY" in body("setMiloHorizon")
    assert "miloHorizonHTML()" in body("renderPersonaPicker")


def test_an_answer_says_when_the_question_set_the_timeframe():
    assert "event === 'assumed'" in APP
    assert "Your setting is unchanged." in APP


def test_the_price_is_its_own_takeaway_beside_the_business():
    take = body("ovTakeawaysHTML")
    assert "The price you pay" in take and "ovValuationRead()" in take
    val = body("ovValuationRead")
    assert "valuation_history" in val and "usable_years >= 3" in val
    assert "A strong business can still be an expensive stock." in val
    assert "ovValuationRead()" in body("ovFactors")


def test_a_high_long_term_score_is_reconciled_with_a_stretched_price():
    assert "It does not say the price is low" in body("ovScoreHTML")


def test_the_thesis_check_is_rules_over_page_data_and_never_advice():
    html = body("thesisCheckHTML")
    assert "not by an AI model, and not a recommendation" in html
    assert "Whether a change breaks your case is your call" in html
    ids = re.findall(r"\{ id: '([a-z]+)', label:", APP[APP.index("const THESIS_CHECKS"):])
    assert {"trend", "growth", "profit", "beats", "value", "sector", "level"} <= set(ids)
    assert "${thesisCheckHTML(d)}" in body("renderOverviewView")
    # The old free-text panel on Options stays hidden, as the reader asked.
    assert "const THESIS_PANEL_HIDDEN = true;" in APP


def test_the_thesis_check_uses_the_existing_synced_store():
    save = body("thesisSave")
    assert "...(extra || {})" in save
    assert "{ check: { v: 1, items } }" in APP
    assert "openPulseWithText(text)" in APP[APP.index("data-tc-ask"):]


def test_the_ask_milo_button_is_charcoal_with_a_thin_gold_edge_and_no_disc():
    rule = CSS[CSS.index(".btn.milo-btn {"):]
    rule = rule[:rule.index("}")]
    assert "var(--milo-btn-bg)" in rule and "1px solid var(--asset-brand)" in rule
    assert "--milo-btn-bg: #1c1917;" in CSS
    badge = CSS[CSS.index(".scout-badge {"):]
    badge = badge[:badge.index("}")]
    assert "background: transparent;" in badge


def test_every_source_key_milo_is_told_about_becomes_a_chip():
    """The prompt lists the CONTEXT keys Milo may tag; a key missing from
    PULSE_SOURCES is silently dropped, so a correct citation vanished. The
    Overview's blocks were sent from 2026-10-12 and had no chip."""
    from app import ai
    flat = " ".join(ai.FORMAT_PROMPT.split())
    listed = flat[flat.index("The keys are "):flat.index("Tag the key the figure")]
    keys = set(re.findall(r"\b([a-z]+(?:_[a-z]+)*)\b", listed.replace("The keys are", "").replace(" and ", " ")))
    block = APP[APP.index("const PULSE_SOURCES = {"):APP.index("const PULSE_SRC_RE")]
    chips = set(re.findall(r"^\s+([a-z_]+): \[", block, re.M))
    assert keys - {"the", "keys", "are"} <= chips, sorted(keys - chips)
