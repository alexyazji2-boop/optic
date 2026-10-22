"""Milo's research integration (backlog task 12, 2026-10-20): an answer says what it was about, an earlier
answer is flagged when the page now open is another symbol's, and the Options context says when its quotes were
read and why figures are missing.

Driven in headless Chrome against the STAND-IN model (milo_standin.py) at 390 and 1440 px
(~/Optic/work/v2-backlog/milo_check.py, 10 checks each) and through a five-case evaluation set
(~/Optic/work/v2-backlog/milo_eval.py: factual grounding, numerical consistency, missing data, contradictory
sources, cross-ticker context). Those runs verify what Optic sends the model; the answers are simulated and
were not graded, so nothing here is evidence of answer quality.
"""
from tests.test_frontend_v2_stage0 import V2

MILO = (V2 / "js/ui/milo.js").read_text()
OPT = (V2 / "js/pages/options.js").read_text()


def test_each_answer_says_what_it_was_about():
    about = MILO[MILO.index("export function aboutLine"):MILO.index("function sourceLists")]
    # behaviour in tests/test_pitch_audit_2026_10_22.py (page context and answer concerns told apart)
    assert "About ${join(about)}" in about and "asked from ${where}" in about and "attached as context" in about
    assert "!about.includes(now.symbol)" in about and "Not about ${now.symbol}, the page now open." in about
    assert "${aboutLine(info)}" in MILO.split("function msgHTML")[1].split("function sourceLists")[0]


def test_a_route_change_redraws_the_open_panel_but_not_a_stream():
    reset = MILO[MILO.index("export function resetContext"):MILO.index("const pageLabel")]
    assert "paintLog(false)" in reset and "!S.live" in reset


def test_options_tells_milo_when_its_quotes_were_read_and_why_figures_are_missing():
    ctx = OPT[OPT.index("options_research: R.data ?"):OPT.index("position: B.analysis")]
    assert "quotes_read_at: R.data.fetched_at" in ctx and "quotes_unusable: noQuotes()" in ctx
