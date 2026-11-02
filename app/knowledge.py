"""Knowledge levels: how much financial fluency Optic assumes when it explains.

**Five levels, one preference (post-demo overhaul, Phase 05, 2026-10-29).** The
owner's directive names them: New to Markets, Beginner, Intermediate, Advanced
and Expert, five positions on one slider. The reader's choice is one value:
`optic.knowledge.v1` in the browser, and `user_preferences.knowledge_level` for a
signed-in reader (app/auth/store.py). Both apps and every page read that value.

**The level changes the words, never the facts.** It decides vocabulary, how
much is explained, and how dense an answer is. It must not change a figure, a
calculation, a source, a caveat, a disclosure, whether missing data is said, or
whether the advice policy applies (app/ai_policy.py). Every style instruction
below ends with the same INVARIANT, appended in one place (`prompt_for`), so no
level can be written without it. A level that changed the arithmetic would be a
way of getting a friendlier answer by claiming to be a beginner.

**One copy of the styles.** This module is the only place the five styles are
written. Milo, deep research and the written portfolio briefing take their
level block from `prompt_for`; no service keeps its own five prompts
(directive 05, section 5).

**What changed in Phase 05.** The ladder had five modes, Simple, Financially
Literate, Advanced, Professional and Adaptive, and the labels were chosen to
describe the explanation rather than the reader. The owner's directive asks for
the five names above, so they replace those labels (DECISIONS D-026). Adaptive,
which judged depth from each question, is not one of the five positions; a
stored "adaptive" reads as Intermediate, where its layout already sat, and the
reader's chosen level is now always the one used (D-027). Old ids keep working
through LEGACY, because they are stored in readers' browsers and sent by any
page loaded before this change.

**Density is not here.** What a page shows is the separate Simple or Advanced
setting (static/v2/js/core/prefs.js `density`, D-019). The `level` integers below
are Classic's panel ladder only, kept so Classic's layouts do not move.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Classic's panel ladder (static/components/knowledge.js reads these through the
# catalogue and keeps a copy for its first paint). A panel carries the lowest
# rung it appears at. New to Markets and Beginner share the first rung, so the
# two levels that replace "Simple" render Classic exactly as Simple did.
LEVEL_SIMPLE = 0
LEVEL_LITERATE = 1
LEVEL_ADVANCED = 2
LEVEL_PROFESSIONAL = 3

# What "explain a term where it appears" does per level, for rule-written text:
#   inline     the definition is shown with the term, not behind a press
#   on_demand  the term is marked and explains itself when pressed
#   off        no marks; the reader knows the vocabulary
EXPLAIN_INLINE = "inline"
EXPLAIN_ON_DEMAND = "on_demand"
EXPLAIN_OFF = "off"

DEFAULT_MODE = "intermediate"

# Ids before Phase 05, as stored in browsers and sent by pages loaded before it.
LEGACY = {
    "simple": "new",
    "literate": "intermediate",
    "professional": "expert",
    "adaptive": "intermediate",
}

# Appended to every level's instruction, so no level is ever written without it.
INVARIANT = (
    "Whatever this level asks of the wording, it changes only the words, how much "
    "is explained and how densely; nothing else. Every figure, calculation and "
    "date is the same at every level and comes from the CONTEXT as given. Every "
    "source is named the same way. Every caveat, every risk, every note that data "
    "is delayed, estimated or inferred, and every statement that something is "
    "missing or unknown stays in, in words this reader can follow. The advice "
    "policy in these instructions applies unchanged. A simpler level never makes the facts "
    "softer, and a denser one never drops a caveat."
)

# The one fact every level's preview explains, so the slider shows the same
# thing said five ways. An illustration, labelled as one where it is shown.
PREVIEW_FACT = "A company whose shares trade at 30 times its earnings over the past year."

MODES: Dict[str, Dict[str, Any]] = {
    "new": {
        "label": "New to Markets",
        "position": 1,
        "glyph": "\U0001F331",
        "tagline": "Explain it in everyday words.",
        "blurb": "Everyday English. Every financial term is explained where it appears.",
        "level": LEVEL_SIMPLE,
        "explain": EXPLAIN_INLINE,
        "preview": ("People are paying $30 for every $1 of profit the company made last year. "
                    "That figure, called the price-to-earnings ratio, is high next to many "
                    "companies, which usually means buyers expect the profits to grow."),
        "prompt": (
            "Write for somebody new to markets. Use basic everyday English and short "
            "sentences. Define every financial term in the same breath you use it: "
            "\"the price-to-earnings ratio (what you pay for each dollar the company "
            "earns)\". Use a comparison to something outside markets where one "
            "genuinely fits, and skip it where it does not. After each point, answer "
            "the question they have not asked: why does this matter to somebody "
            "holding this stock. Cite the same CONTEXT figures, keep every caveat "
            "about delayed data and inferred flow, and never state a number you do "
            "not have. Plain words, not softer facts: if the honest answer is that "
            "the signals disagree and there is no edge here, say exactly that in "
            "plain words rather than reaching for something more comfortable."
        ),
    },
    "beginner": {
        "label": "Beginner",
        "position": 2,
        "glyph": "\U0001F33F",
        "tagline": "Explain it simply.",
        "blurb": "Simple explanations that introduce the essential terms as they come up.",
        "level": LEVEL_SIMPLE,
        "explain": EXPLAIN_ON_DEMAND,
        "preview": ("The shares trade at 30 times last year's earnings, a price-to-earnings "
                    "ratio (P/E) of 30. A high P/E means buyers expect earnings to grow."),
        "prompt": (
            "Write for a beginner: somebody who knows what a stock and a percentage "
            "move are, and not much more. Use simple explanations and introduce the "
            "essential terms rather than avoiding them: use the standard name "
            "(earnings per share, the price-to-earnings ratio, volatility) and explain "
            "it in a few words the first time it appears. Use only the terms the "
            "answer needs, one idea to a sentence, and say why each point matters."
        ),
    },
    "intermediate": {
        "label": "Intermediate",
        "position": 3,
        "glyph": "\U0001F4CA",
        "tagline": "Give me the important context.",
        "blurb": "Ordinary financial terms, with context for the specialist ones.",
        "level": LEVEL_LITERATE,
        "explain": EXPLAIN_ON_DEMAND,
        "preview": ("At 30 times trailing earnings the stock is priced for growth: the "
                    "multiple holds only if earnings keep rising."),
        "prompt": (
            "Assume the reader follows markets and knows the basics: what a stock "
            "is, how earnings work, what a percentage move means, roughly why "
            "interest rates matter. Do not explain those. Use balanced financial "
            "vocabulary and gloss the specialist end of it in a clause as you go, "
            "which is what the base instructions already ask for. Assume no "
            "professional training: implied volatility, dealer gamma and factor "
            "exposure each need a few words the first time they appear in an answer."
        ),
    },
    "advanced": {
        "label": "Advanced",
        "position": 4,
        "glyph": "\U0001F4C8",
        "tagline": "Give me the full analysis.",
        "blurb": "Professional language and deeper reasoning. Standard terms are not defined.",
        "level": LEVEL_ADVANCED,
        "explain": EXPLAIN_ON_DEMAND,
        "preview": ("30x trailing EPS is a premium multiple. It needs sustained earnings "
                    "growth, and a miss would compress it."),
        "prompt": (
            "Assume the reader is fluent: valuation multiples, technical indicators, "
            "the rate and dollar relationships, how positioning feeds back into "
            "price. Use professional technical language. Do not define standard "
            "terms, and do not prefix an explanation with what it is about to "
            "explain. Spend the words you save on deeper analytical reasoning "
            "instead: which readings disagree with each other, what the base rate "
            "is, and what would have to happen for the read to be wrong."
        ),
    },
    "expert": {
        "label": "Expert",
        "position": 5,
        "glyph": "\U0001F52C",
        "tagline": "Give me the terminal view.",
        "blurb": "Concise research language and advanced metrics. No definitions.",
        "level": LEVEL_PROFESSIONAL,
        "explain": EXPLAIN_OFF,
        "preview": "30x TTM P/E: a premium multiple, sensitive to EPS revisions.",
        "prompt": (
            "Terminal register: concise, precise financial research language, with "
            "advanced metrics where they are relevant. Lead with the readings and "
            "let them carry the argument: levels, greeks, positioning, the "
            "distribution a number sits in. No definitions and no scene-setting. "
            "Where a figure is a proxy or an assumption, label it in a word rather "
            "than a sentence, and keep it labelled: density is not a reason to drop "
            "the distinction between what was measured and what was inferred, "
            "which is the one thing this register could quietly lose."
        ),
    },
}

# Slider order, New to Markets to Expert.
ORDER = ["new", "beginner", "intermediate", "advanced", "expert"]


def normalise(mode: Optional[str]) -> str:
    """A known level id, or the default.

    Never raises and never trusts the input. The value arrives from
    localStorage, which the reader can edit, from a query string, which anybody
    can, and from pages loaded before Phase 05, which send the old ids."""
    key = str(mode or "").strip().lower()
    key = LEGACY.get(key, key)
    return key if key in MODES else DEFAULT_MODE


def known(mode: Optional[str]) -> bool:
    """Whether a value names a level (an old id counts), for storing it."""
    key = str(mode or "").strip().lower()
    return LEGACY.get(key, key) in MODES


def level(mode: Optional[str]) -> int:
    return MODES[normalise(mode)]["level"]


def label(mode: Optional[str]) -> str:
    return MODES[normalise(mode)]["label"]


def explain_policy(mode: Optional[str]) -> str:
    return MODES[normalise(mode)]["explain"]


def prompt_for(mode: Optional[str]) -> str:
    """The level's instruction block for a model's system prompt: its style, then the invariant."""
    return MODES[normalise(mode)]["prompt"] + "\n\n" + INVARIANT


def catalogue() -> Dict[str, Any]:
    """What the slider renders, and what a level changes and cannot change.

    Published rather than written into each page, so the promise and the
    behaviour come from one place."""
    return {
        "modes": [
            {
                "id": key,
                "label": MODES[key]["label"],
                "position": MODES[key]["position"],
                "glyph": MODES[key]["glyph"],
                "tagline": MODES[key]["tagline"],
                "blurb": MODES[key]["blurb"],
                "level": MODES[key]["level"],
                "explain": MODES[key]["explain"],
                "preview": MODES[key]["preview"],
            }
            for key in ORDER
        ],
        "default": DEFAULT_MODE,
        "legacy": dict(LEGACY),
        "preview_fact": PREVIEW_FACT,
        "changes": [
            "The words Optic and Milo use, and how much they explain as they go.",
            "Whether a term is defined where it appears, marked to explain itself, or left plain.",
        ],
        "never_changes": [
            "The figures, the calculations and the sources. A level never rounds a number, "
            "drops a caveat or a disclosure, hides that something is missing, or changes "
            "what the advice policy declines.",
        ],
    }


def resolve_for_answer(mode: Optional[str], question: str = "") -> str:
    """Which level to write an answer at: the reader's own, always.

    Adaptive used to read the question and pick a level per answer. It is not
    one of the five positions (D-027), so the reader's chosen level is the one
    used, and `question` is no longer read. The name is kept for its callers."""
    return normalise(mode)
