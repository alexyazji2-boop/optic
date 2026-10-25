"""What "conviction" means in v2's Optic's read (owner, 2026-10-25).

The "Read more" fold said "Conviction is agreement between the inputs, not a probability." It is not: in
`swing.verdict()` conviction is only a band of the composite's size (10, 30 and 50 points from zero, capped at moderate
while a scheduled event is pending), and agreement is a separate figure, `signal_agreement_pct`. Five inputs all at +12
agree fully and read low. Neither has been shown to predict returns.

So v2 now says which distance from 50 the word names, on the Optic Score's 0 to 100, and gives agreement its own
sentence; the meta row's chip carries the distance too. The owner asked for v2 only: Classic keeps its wording, and the
last test here holds it unchanged.

Every case runs end to end: `swing.verdict()` builds the verdict, `pulse.pulse()` the panel payload, and v2's own
functions render it in JavaScriptCore.
"""
import json
import re

import pytest

from app.analytics import pulse as pulse_mod
from app.analytics import swing
from tests.test_frontend_v2_stage0 import V2, _run

OVR = (V2 / "js/pages/overview-research.js").read_text()
APP = (V2.parent / "app.js").read_text()
NOW = "Date.parse('2026-10-25T16:00:00Z')"


def payload(trend, *, gamma_flow=None, pending=False):
    """A ticker payload whose composite is `trend` (one input, so the weights renormalise to it alone)."""
    v = swing.verdict({"trend_score": trend}, {}, {"flow_score": gamma_flow} if gamma_flow is not None else {}, {}, 100.0)
    if pending:
        # verdict() reads a pending event from headlines; the cap is the rule under test, so it is applied the way
        # verdict applies it rather than by inventing a headline the keyword rules happen to match.
        v["pending_catalyst"] = {"pending": True, "kinds": ["regulatory"], "count": 1}
        if v["conviction"] == "high":
            v["conviction"] = "moderate"
    p = pulse_mod.pulse({"verdict": v})
    return {"verdict": v, "pulse": p, "digest": {}}


CASES = {
    "slight": payload(17),          # 58.5 on 0 to 100, printed 59
    "none": payload(-2),
    "edge_none": payload(9.9),      # 4.95 from 50: still none
    "edge_low": payload(10),
    "moderate": payload(-34),
    "high": payload(62),
    "held": payload(62, pending=True),
    "pending_low": payload(14, pending=True),
    "agree": payload(24, gamma_flow=24),
}


@pytest.fixture(scope="module")
def reads(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("conv"), f"""
      const R = await import('{(V2 / "js/pages/overview-research.js").as_posix()}');
      const T = {json.dumps(CASES)}, now = {NOW};
      const s = (x) => (x && x.s) || String(x || '');
      const strip = (h) => h.replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/\\s+/g, ' ').replace(/ ([:.,])/g, '$1').trim();
      const o = {{}};
      for (const k of Object.keys(T)) {{
        const more = s(R.readMore(T[k].pulse)), hero = s(R.opticRead({{ t: T[k], now }}));
        const paras = more.split('<p').slice(1).map((c) => strip(c.replace(/^[^>]*>/, '')));
        o[k] = {{ conv: paras.find((x) => /conviction/i.test(x)) || '', meta: strip(hero.split('class="pl-meta">')[1].split('</div>')[0]),
                 chip: R.convictionChip(T[k].pulse), score: R.shortScore(T[k], now).n, text: strip(more) }};
      }}
      o.nocomp = s(R.readMore({{ ...T.high.pulse, composite_score: null }}));
      o.nocomp = {{ conv: strip(o.nocomp), chip: R.convictionChip({{ ...T.high.pulse, composite_score: null }}) }};
      print(JSON.stringify(o));
    """)


def test_it_no_longer_calls_conviction_agreement(reads):
    assert "agreement between the inputs" not in OVR
    for k, r in reads.items():
        assert "agreement between" not in r["conv"].lower(), k


def test_conviction_is_said_as_the_distance_from_50_the_optic_score_card_shows(reads):
    r = reads["slight"]
    assert r["conv"].startswith("Low conviction: the short-term score is 59 of 100, 9 points from its neutral 50."), r["conv"]
    assert "Conviction only sorts that distance into bands: under 5 points none, 5 to 15 low, 15 to 25 moderate, 25 or more high." in r["conv"]
    assert "It is not a probability, and it has not been shown to predict returns." in r["conv"]
    # Same reading as the Optic Score card above it: 58.5 prints as 59 there too.
    assert r["score"] == 58.5
    assert reads["none"]["conv"].startswith("No conviction: the short-term score is 49 of 100, 1 point from its neutral 50.")


def test_the_bands_in_the_copy_are_the_bands_verdict_applies(reads):
    """Parsed from the sentence and checked against swing.verdict() on both sides of every cut, both signs."""
    m = re.search(r"under (\d+) points none, \1 to (\d+) low, \2 to (\d+) moderate, \3 or more high", OVR)
    assert m, "the band sentence"
    cuts = [int(x) for x in m.groups()]
    for comp in (0, 9.9, 10, 20, 29.9, 30, 40, 49.9, 50, 80, 100):
        for sign in (1, -1):
            c = sign * comp
            words = "none" if abs(c) / 2 < cuts[0] else "low" if abs(c) / 2 < cuts[1] else "moderate" if abs(c) / 2 < cuts[2] else "high"
            assert swing.verdict({"trend_score": c}, {}, {}, {}, 100.0)["conviction"] == words, c
    # 9.9 sits 4.95 from 50 and prints as 5, as the card prints 54.95 as 55: whole points, the card's rounding.
    assert reads["edge_none"]["chip"] == "no conviction, 5 points from 50"
    assert reads["edge_low"]["chip"] == "low conviction, 5 points from 50"
    assert reads["moderate"]["chip"] == "moderate conviction, 17 points from 50"
    assert reads["high"]["chip"] == "high conviction, 31 points from 50"


def test_agreement_is_its_own_figure(reads):
    r = reads["agree"]
    assert r["meta"].startswith("low conviction, 12 points from 50"), r["meta"]
    assert "100% of inputs agree" in r["meta"]
    assert "Agreement is a separate figure: 100% of the inputs with a clear lean point the same way and 2 of 4 had data." in r["conv"], r["conv"]
    assert "The two can differ: inputs that all lean slightly one way agree fully and still sit near 50." in r["conv"]


def test_a_pending_event_holds_it_below_high_and_says_so(reads):
    r = reads["held"]
    assert r["chip"] == "moderate conviction, 31 points from 50"
    assert "It is held short of high while a scheduled event is still ahead" in r["conv"]
    # On a low read the hold changed nothing, and saying it would suggest the event is why the read is low
    # (INTC, live, 2026-10-25). The pending line above the fold still states the rule.
    low = reads["pending_low"]
    assert low["chip"] == "low conviction, 7 points from 50" and "held short of high" not in low["conv"], low["conv"]


def test_without_a_composite_it_still_says_what_the_word_measures(reads):
    r = reads["nocomp"]
    assert "High conviction. Conviction only sorts how far the short-term score sits from its neutral 50 into bands:" in r["conv"]
    assert r["chip"] == "high conviction"


def test_the_meta_row_carries_the_distance(reads):
    assert "${convictionChip(p)}" in OVR
    for k in ("slight", "none", "moderate", "high", "held"):
        assert reads[k]["meta"].startswith(reads[k]["chip"]), k
    assert "1 point from 50" in reads["none"]["chip"] and "1 points" not in reads["none"]["chip"]


def test_no_em_dash_in_what_it_says(reads):
    for k, r in reads.items():
        assert "—" not in json.dumps(r, ensure_ascii=False), k


def test_classic_is_kept_as_it_is():
    """The owner asked for v2 only, so Classic's panel keeps its own wording."""
    assert "Conviction is agreement between the inputs, not a probability." in APP
    assert "function pulseConvictionChip(" not in APP and "function pulseFromNeutral(" not in APP
