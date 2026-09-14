"""The homepage story slot: what is moving markets, not who published it.

"What matters now" opened with a written headline and a ranked list of
cross-asset moves, and nothing at all saying what had happened. A reader could
see the ten-year was up and had nowhere to go to find out why. The homepage
carried no news.

The daily brief already holds the wire, and `_home_read` already loads it from
the store without building it, so the slot costs a re-ranking of a list in
memory rather than any fetch.

What took a second pass was the ranking. The brief orders its desks by a
per-source `weight`, which is a judgement about outlets rather than about
stories, and measured on the live wire it led with "Novo CEO tells CNBC why
drugmaker is rebranding" while "Ten-year Treasury yield hits 5% for first time
since 2023" sat further down, because CNBC outweighs Econbrowser. For a slot
whose whole job is what is moving markets, the catalyst has to beat the
masthead, so this reuses the tiering the headline panel uses.

Measured live after the change, three stories:

    BREAKING  Warsh's credibility is on the line this week ...   30 minutes ago
    BREAKING  Ten-year Treasury yield hits 5% for first time ... 1 hour ago
    BREAKING  Stocks Decline, 10-Year Treasury Yield Touches 5%  2 hours ago

and the rebranding story off the list. Rendered height 210px for the block,
84/63/63 per story, badge inline with the headline, no horizontal overflow.
"""

import re

from app import main as main_mod
from app import news

APP_JS = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
MAIN_PY = open("app/main.py", encoding="utf-8").read()


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP_JS)


def body_of(name, src=None):
    s = src if src is not None else CODE
    start = s.index("function %s(" % name)
    return s[start:].split("\nfunction ", 1)[0]


def py_body(name):
    """One Python function, bounded at the next top-level def or decorator.

    Bounded because the unbounded version sliced to the end of the file, so
    `"limit=3" in fn` matched a different call in main.py entirely and a
    mutation raising this slot's limit to 12 passed. Every assertion about a
    Python function body here goes through this.
    """
    start = MAIN_PY.index("def %s(" % name)
    rest = MAIN_PY[start:]
    ends = [i for i in (rest.find("\ndef "), rest.find("\n@app"),
                        rest.find("\nclass ")) if i > 0]
    return rest[:min(ends)] if ends else rest


# ------------------------------------------------------------- the ranking

def test_the_wire_is_ranked_by_catalyst_not_by_source_weight():
    """The measured failure. A rebranding must not outrank a benchmark yield
    through a round number because of which outlet carried it."""
    entries = [
        {"title": "Novo CEO tells CNBC why drugmaker is rebranding",
         "summary": "", "published": "2026-09-14T17:40:00+00:00", "weight": 9},
        {"title": "Ten-year Treasury yield hits 5% for first time since 2023",
         "summary": "", "published": "2026-09-14T17:00:00+00:00", "weight": 3},
    ]
    ranked = news.rank_wire(entries, limit=2)
    assert "Treasury" in ranked[0]["title"], [r["title"] for r in ranked]


def test_a_benchmark_yield_is_a_macro_event():
    """It was not. The macro pattern had `fed`, `cpi`, `inflation` and `fomc`
    and no bond terms at all, so "Stocks Decline, 10-Year Treasury Yield
    Touches 5%" was rated medium and ranked below the rebranding."""
    for headline in ("Ten-year Treasury yield hits 5%",
                     "10-Year Treasury Yield Touches 5% Amid Oil Surge",
                     "yield curve inverts again",
                     "November jobs report comes in hot",
                     "nonfarm payrolls beat"):
        types = [c["type"] for c in news.classify(headline)["catalysts"]]
        assert "macro event" in types, (headline, types)


def test_the_ranking_is_the_same_rule_the_headline_panel_uses():
    """One rule, two surfaces. If the taxonomy is wrong it should be wrong in
    one place, not in two that disagree."""
    src = open("app/news.py", encoding="utf-8").read()
    fn = src[src.index("def rank_wire("):]
    assert "tier_for(" in fn
    assert "TIER_ORDER.index" in fn
    assert "_importance_rank" in fn


def test_the_wire_ranking_does_not_apply_the_company_relevance_split():
    """That test asks whether an item names one particular company, and this
    feed is not about one. Everything on it is market context, which is what
    the slot is for."""
    fn = open("app/news.py", encoding="utf-8").read()
    fn = fn[fn.index("def rank_wire("):]
    assert "mentions_company" not in fn
    assert "about_company" not in fn


def test_ranking_an_empty_wire_returns_nothing_rather_than_raising():
    assert news.rank_wire([], limit=3) == []
    assert news.rank_wire(None, limit=3) == []


def test_the_ranking_does_not_mutate_the_brief_entries():
    """`rank_wire` copies each row. The brief is cached and served to other
    surfaces, so writing tier fields into it in place would leak this slot's
    annotations into every other reader of the same dict."""
    entry = {"title": "Fed holds rates", "summary": "",
             "published": "2026-09-14T17:00:00+00:00"}
    news.rank_wire([entry], limit=1)
    assert set(entry) == {"title", "summary", "published"}, entry


# ------------------------------------------------------------- the payload

def test_the_story_desks_exclude_agency_notices():
    """`regulatory` is an FDA and agency notice feed. Measured, its top four
    entries were "FDA Rare Disease Innovation Hub" and three guidance agendas,
    which are not what is moving markets today."""
    assert "regulatory" not in main_mod._STORY_DESKS
    assert "markets" in main_mod._STORY_DESKS
    assert "economy" in main_mod._STORY_DESKS


def test_the_slot_never_triggers_a_brief_build():
    """`_home_read` reads the brief store without building it, because
    `brief_mod.state()` would generate today's brief on a miss: a minute of
    feed fetches and several model calls, on the landing page. The story slot
    is handed the dict that is already loaded and must not reach for more."""
    fn = py_body("_home_stories")
    assert "brief_mod.state" not in fn
    assert "_load" not in fn
    assert "rank_wire" in fn


def test_the_payload_carries_the_reason_for_each_tier():
    fn = py_body("_home_stories")
    for field in ("title", "url", "source", "tier", "tier_why", "age_words"):
        assert '"%s"' % field in fn, field


def test_a_missing_wire_is_an_absent_slot_not_an_error():
    """Every leg of /api/home reports its own absence. A landing page that 500s
    because one feed is down is worse than one that shows less."""
    assert main_mod._home_stories({}) == []
    assert main_mod._home_stories({"wires": {}}) == []
    assert main_mod._home_stories({"wires": {"desks": []}}) == []


# -------------------------------------------------------------- the render

def test_the_stories_render_above_the_instrument_list():
    """The order is the point: the headline says what happened, the stories say
    what happened, then the numbers show it."""
    fn = body_of("whatMattersNow")
    assert "homeStories(data)" in fn
    assert fn.index("homeStories(data)") < fn.index("cc-moves")


def test_no_stories_renders_nothing_at_all():
    """Not an empty list with a border, which reads as a panel that failed."""
    fn = body_of("homeStories")
    assert "if (!stories.length) return '';" in fn


def test_the_story_slot_is_three_lines_not_paragraphs():
    """The measured defect on this page has always been height. The brief's own
    summary paragraphs are one click away on the Read tab; what belongs here is
    the link, not the essay."""
    fn = py_body("_home_stories")
    assert "limit=3" in fn
    render = body_of("homeStories")
    assert "paragraphs" not in render


def test_the_story_is_not_a_flex_row():
    """It was, and it cost 121px per story. The block lives in a 401px grid
    cell, so `flex: 1 1 260px` on the link made the title a full-width flex
    item and pushed the tier badge onto a line of its own. Inline, the badge
    sits at the head of the paragraph like a newspaper kicker."""
    block = CSS[CSS.index(".cc-stories li {"):CSS.index("a.cc-story-t {")]
    assert "display: flex" not in block
    assert "display: inline-flex" not in block


def test_the_tier_label_is_derived_not_hardcoded():
    """The home payload does not carry the tier catalogue, so the label is
    capitalised from the id. A new tier then needs nothing here, and a renamed
    one leaves no stale string behind."""
    fn = body_of("homeTierLabel")
    assert "toUpperCase()" in fn
    for label in (t["label"] for t in news.TIERS):
        assert label not in fn, label


def test_the_story_link_is_safe_and_external():
    fn = body_of("homeStories")
    assert 'target="_blank"' in fn
    assert "noopener" in fn and "noreferrer" in fn and "nofollow" in fn
    # Every interpolation of feed-supplied text is escaped. This is third-party
    # prose from an RSS feed, so it is the least trusted string on the page.
    for field in ("s.url", "s.title", "s.source", "s.age_words", "s.tier"):
        assert "esc(%s" % field in fn, field


def test_the_story_hover_transitions_like_every_other_link():
    """House rule: every hover state transitions paint-level properties only.
    A first version underlined with no transition, so it snapped while the rest
    of the app eased, and tests/test_ui_refactor.py caught it."""
    block = CSS[CSS.index("a.cc-story-t {"):]
    block = block[:block.index("}", block.index("focus-visible"))]
    assert "transition: color var(--dur-ui) var(--ease-ui)" in block
