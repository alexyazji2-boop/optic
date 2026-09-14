"""Knowledge modes: how much financial fluency Optic should assume.

**One control, three axes.** The same setting moves the language Pulse writes
in, how many panels a view renders, and whether a term is explained where it
appears. Those were three separate things before this module and none of them
used the same vocabulary:

* `uiMode` was Pro / Simple and switched *panels* only.
* `PERSONAS` held six lenses, one of which ("Straight to it") was not a lens at
  all but a register control, so picking it fought whatever `uiMode` said.
* The glossary explained terms on hover regardless of whether the reader needed
  it, which is the right default for nobody in particular.

A lens and a level are different questions. "Whose judgement do I want" is a
lens; "how much do I already know" is a level, and the level is the one that
should decide how everything is worded. So the registers moved here and the
lenses stayed where they were.

**The data never changes, only its presentation.** A mode may hide a panel and
may simplify a sentence. It must not round a number, drop a caveat, or withhold
a figure that was measured: every panel remains reachable, and the levels are
about what is shown *first*. A mode that changed the arithmetic would be a way
of getting a friendlier answer by claiming to be a beginner.

**Levels, not tiers of customer.** The labels say what the reader gets, never
what the product thinks of them: "Simple" describes the explanation, where
"Beginner" would describe the person. Nothing in the interface calls anybody a
novice, and nothing is locked.

**Adaptive is about the answer, not the layout.** It lets Pulse judge the depth
of a reply from the question asked, which is a thing a question can support. It
does not guess at panel density, because a reader who has not asked anything yet
has given nothing to infer from, so it renders at Financially Literate and says
so rather than picking silently.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# The density ladder. A panel carries the lowest level at which it appears, so
# the comparison is one integer and a new mode does not mean re-tagging panels.
LEVEL_SIMPLE = 0
LEVEL_LITERATE = 1
LEVEL_ADVANCED = 2
LEVEL_PROFESSIONAL = 3

# What "explain a term where it appears" does per mode.
#   inline     the definition is shown, not hidden behind a hover
#   on_demand  the term is marked and explains itself when asked
#   off        no marks; the reader knows the vocabulary
EXPLAIN_INLINE = "inline"
EXPLAIN_ON_DEMAND = "on_demand"
EXPLAIN_OFF = "off"

DEFAULT_MODE = "literate"

MODES: Dict[str, Dict[str, Any]] = {
    "simple": {
        "label": "Simple",
        "glyph": "\U0001F331",
        "tagline": "Explain it simply.",
        "blurb": "New to investing. Plain words, and every term explained where "
                 "it appears.",
        "level": LEVEL_SIMPLE,
        "explain": EXPLAIN_INLINE,
        "prompt": (
            "Write for somebody new to investing. Short sentences and everyday "
            "words. Where a term is unavoidable, define it in the same breath "
            "you use it: \"the price-to-earnings ratio (what you pay for each "
            "dollar the company earns)\". Use a comparison to something outside "
            "markets where one genuinely fits, and skip it where it does not. "
            "After each point, answer the question they have not asked: why "
            "does this matter to somebody holding this stock. "
            "Every factual constraint above still applies without exception. "
            "Cite the same CONTEXT figures, keep every caveat about delayed "
            "data and inferred flow, and never state a number you do not have. "
            "Simple means the words are plain, not that the facts are softer: "
            "if the honest answer is that the signals disagree and there is no "
            "edge here, say exactly that in plain words rather than reaching "
            "for something more comfortable."
        ),
    },
    "literate": {
        "label": "Financially Literate",
        "glyph": "\U0001F4CA",
        "tagline": "Give me the important context.",
        "blurb": "Assumes the basics: stocks, earnings, percentages, why rates "
                 "matter. Explains the rest.",
        "level": LEVEL_LITERATE,
        "explain": EXPLAIN_ON_DEMAND,
        "prompt": (
            "Assume the reader follows markets and knows the basics: what a "
            "stock is, how earnings work, what a percentage move means, roughly "
            "why interest rates matter. Do not explain those. Use ordinary "
            "financial vocabulary and gloss the specialist end of it in a "
            "clause as you go, which is what the base instructions already ask "
            "for. Assume no professional training: implied volatility, dealer "
            "gamma and factor exposure each need a few words the first time "
            "they appear in an answer."
        ),
    },
    "advanced": {
        "label": "Advanced",
        "glyph": "\U0001F4C8",
        "tagline": "Give me the full analysis.",
        "blurb": "Comfortable with valuation, technicals and macro. Skip the "
                 "definitions.",
        "level": LEVEL_ADVANCED,
        "explain": EXPLAIN_ON_DEMAND,
        "prompt": (
            "Assume the reader is fluent: valuation multiples, technical "
            "indicators, the rate and dollar relationships, how positioning "
            "feeds back into price. Do not define standard terms, and do not "
            "prefix an explanation with what it is about to explain. Spend the "
            "words you save on the reasoning instead: which readings disagree "
            "with each other, what the base rate is, and what would have to "
            "happen for the read to be wrong."
        ),
    },
    "professional": {
        "label": "Professional",
        "glyph": "\U0001F52C",
        "tagline": "Give me the terminal view.",
        "blurb": "Maximum density. Raw readings, market structure, no "
                 "explanation.",
        "level": LEVEL_PROFESSIONAL,
        "explain": EXPLAIN_OFF,
        "prompt": (
            "Terminal register. Lead with the readings and let them carry the "
            "argument: levels, greeks, positioning, the distribution a number "
            "sits in. No definitions and no scene-setting. Where a figure is a "
            "proxy or an assumption, label it in a word rather than a sentence, "
            "and keep it labelled: density is not a reason to drop the "
            "distinction between what was measured and what was inferred, which "
            "is the one thing this register could quietly lose."
        ),
    },
    "adaptive": {
        "label": "Adaptive",
        "glyph": "\U0001F9E0",
        "tagline": "Judge it from what I ask.",
        "blurb": "Optic reads the depth from your question. Panels render at "
                 "Financially Literate.",
        "level": LEVEL_LITERATE,
        "explain": EXPLAIN_ON_DEMAND,
        "prompt": (
            "Judge the depth from the question itself. \"What is a P/E\" and "
            "\"is the 31x forward multiple supported by the revenue trajectory\" "
            "come from readers who need different answers, and the wording of "
            "the question is real evidence about which one is asking. Match the "
            "vocabulary the reader used rather than the vocabulary you would "
            "pick, and where the question carries no signal either way, answer "
            "as you would for somebody who follows markets and has no "
            "professional training. Never explain a term the reader has just "
            "used correctly."
        ),
    },
}

# The order the selector shows. Not dict order: the ladder is the point, and
# Adaptive sits at the end because it is a choice not to choose a rung.
ORDER = ["simple", "literate", "advanced", "professional", "adaptive"]


def normalise(mode: Optional[str]) -> str:
    """A known mode id, or the default.

    Never raises and never trusts the input. The value arrives from
    localStorage, which the reader can edit, and from a query string, which
    anybody can. An unknown mode has to render *something*, and the something is
    the recommended default rather than an error page.
    """
    key = str(mode or "").strip().lower()
    return key if key in MODES else DEFAULT_MODE


def level(mode: Optional[str]) -> int:
    return MODES[normalise(mode)]["level"]


def explain_policy(mode: Optional[str]) -> str:
    return MODES[normalise(mode)]["explain"]


def prompt_for(mode: Optional[str]) -> str:
    """The register fragment for Pulse's system prompt."""
    return MODES[normalise(mode)]["prompt"]


def catalogue() -> Dict[str, Any]:
    """What the selector renders, and what each mode changes.

    `changes` is published rather than described in the UI's own copy so the
    promise and the behaviour come from one place. A selector that claimed to
    change density while the density table disagreed would be the kind of split
    nothing reports.
    """
    return {
        "modes": [
            {
                "id": key,
                "label": MODES[key]["label"],
                "glyph": MODES[key]["glyph"],
                "tagline": MODES[key]["tagline"],
                "blurb": MODES[key]["blurb"],
                "level": MODES[key]["level"],
                "explain": MODES[key]["explain"],
            }
            for key in ORDER
        ],
        "default": DEFAULT_MODE,
        "changes": [
            "The words Optic writes in, and how much it explains as it goes.",
            "How many panels a view opens with. Every panel stays reachable.",
            "Whether a term is defined where it appears or when you ask.",
        ],
        "never_changes": [
            "The figures. A mode never rounds a number, drops a caveat, or "
            "withholds something that was measured.",
        ],
    }


def resolve_for_answer(mode: Optional[str], question: str) -> str:
    """Which register to write an answer in.

    Adaptive is the only mode that reads the question, and it is deliberately a
    coarse read: a question containing "what is" or "explain" from somebody who
    has not used a specialist term is asking to be taught, and a question that
    uses the vocabulary correctly is not.

    Kept crude on purpose. A confident classifier that is wrong a quarter of the
    time is worse than a blunt rule a reader can predict, and Pulse gets the
    question itself as well, so the model sees whatever this misses.
    """
    key = normalise(mode)
    if key != "adaptive":
        return key
    text = (question or "").strip().lower()
    if not text:
        return DEFAULT_MODE
    teaching = ("what is", "what are", "what does", "explain", "how does",
                "why does", "in simple terms", "eli5", "beginner")
    if any(text.startswith(p) or (" " + p) in text for p in teaching):
        # Asking to be taught is not the same as being a beginner, so this
        # lands on Simple for the wording of one answer and changes nothing
        # about the reader's chosen mode.
        return "simple"
    fluent = ("gamma", "vanna", "charm", "skew", "basis", "term structure",
              "factor", "duration", "carry", "iv rank", "delta-hedg",
              "forward multiple", "free cash flow yield")
    if any(term in text for term in fluent):
        return "advanced"
    return DEFAULT_MODE
