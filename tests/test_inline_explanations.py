"""How a term explains itself, and who decides.

Until this, every glossary term was a hover tooltip for everybody. That is the
right default for nobody in particular and wrong at both ends of the ladder: a
reader on Simple cannot discover a hover, cannot perform one on a touchscreen,
and is the person most likely to need the definition, while a reader on
Professional knows what IV rank is and was getting 94 dotted underlines
decorating a page they can already read.

The knowledge mode already published an `explain` policy and nothing read it,
so the feature promised an education layer it did not deliver. Now:

    inline     marked, and the definition opens in place on a click
    on_demand  marked, and explains itself on hover or focus   (the old one)
    off        plain text, no marks

Measured on AMD's Options tab, hover terms then inline terms:

    Simple          0   128
    Literate       96     0
    Advanced       96     0
    Professional    0     0
"""

import re

APP_JS = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def strip_comments(js):
    """The rationale here names the policies, so a raw read cannot tell an
    explanation from an implementation."""
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP_JS)


def body_of(name):
    start = CODE.index("function %s(" % name)
    return CODE[start:].split("\nfunction ", 1)[0]


# --------------------------------------------------------------- the policy

def test_the_three_policies_are_all_handled():
    fn = body_of("glossTerm")
    assert "'off'" in fn and "'inline'" in fn
    # on_demand is the fall-through, which is what keeps the old behaviour the
    # behaviour nobody had to opt into.
    assert "dfn" in fn


def test_off_returns_plain_text_with_no_mark():
    """Professional was getting 94 dotted underlines on terms it does not need
    defined. A mark that never pays off is decoration."""
    fn = body_of("glossTerm")
    assert re.search(r"if \(policy === 'off' \|\| !def\) return text;", fn)


def test_inline_renders_a_control_not_a_dfn():
    """It does something when activated, and a thing that responds to a click
    has to be a button or the keyboard and a screen reader never find out."""
    fn = body_of("glossTerm")
    assert "<button type=\"button\"" in fn
    assert "aria-expanded=\"false\"" in fn
    assert "data-gloss-open" in fn


def test_the_policy_is_read_at_render_time():
    """A mode change re-renders the view, so this needs no invalidation of its
    own, which is only true if it is not cached anywhere."""
    fn = body_of("explainPolicy")
    assert "OpticKnowledge.explain()" in fn
    assert "on_demand" in fn, "there has to be a pre-catalogue default"


# ------------------------------------------------ every emitter goes through it

def test_there_is_one_emitter_of_the_term_markup():
    """Three call sites built this markup by hand and so ignored the reader's
    mode entirely: measured at 13 terms still hover-only on Simple and 13 still
    marked on Professional, where both should have been zero. A table header, a
    fear-and-greed component and a regime row."""
    emitters = len(re.findall(r'class="gloss-term', CODE))
    assert emitters == 2, "expected only glossTerm's own two branches"


def test_both_entry_points_defer_to_it():
    """`gloss` spots terms inside prose and `hg` looks up a whole heading. They
    are different lookups and must not be different policies."""
    assert "glossTerm(match, def, policy)" in body_of("gloss")
    assert "glossTerm(esc(title), def, explainPolicy())" in body_of("hg")


def test_gloss_short_circuits_when_marks_are_off():
    """No point running a 94-term regex over every string to throw the result
    away. This is the hot path: gloss is called 132 times per view."""
    fn = body_of("gloss")
    assert fn.index("=== 'off'") < fn.index("escaped.replace")


# ---------------------------------------------------------- opening one inline

def test_the_definition_opens_and_closes():
    handler = CODE[CODE.index("closest('[data-gloss-open]')"):]
    handler = handler[:handler.index("\n});")]
    assert "aria-expanded" in handler
    assert "next.remove()" in handler, "a second click has to close it"
    assert "insertAdjacentElement('afterend'" in handler


def test_the_definition_is_inserted_as_text_not_markup():
    """The definitions are prose from a table in this file. The day one of them
    contains an ampersand is not the day to discover it was being parsed."""
    handler = CODE[CODE.index("closest('[data-gloss-open]')"):]
    handler = handler[:handler.index("\n});")]
    assert "textContent" in handler
    assert "innerHTML" not in handler


def test_the_handler_is_delegated():
    """These are rendered into every panel on every repaint, so a bind-once
    loop would only ever reach the ones that existed at load. Same trap the nav
    dropdowns and the second tab row both hit."""
    assert "document.addEventListener('click'" in CODE
    handler_at = CODE.index("closest('[data-gloss-open]')")
    assert "document.addEventListener('click'" in CODE[:handler_at]


def test_hover_does_not_also_fire_for_the_inline_variant():
    """Two ways to read one definition is one too many, and the tooltip would
    cover the text it is explaining while the inline copy sat underneath."""
    fn = CODE[CODE.index("function initGlossaryTooltips()"):]
    fn = fn[:fn.index("\nfunction ")]
    assert "hasAttribute('data-gloss-open')" in fn


# ------------------------------------------------------------------ the repaint

def test_a_level_change_rerenders_rather_than_reloads():
    """This was a bug before it was a comment. `loadView(view, false)` returns
    early from every loader's cache guard when the payload is already in STATE,
    which is right for navigation and wrong here: the data has not changed, the
    markup has. Measured: switching rung left 95 hover-only terms in place at
    all four levels because renderSwing never ran again."""
    fn = body_of("applyKnowledgeLevel")
    assert "rerenderActiveView()" in fn
    assert "loadView(STATE.view, false)" not in fn


def test_the_fallback_does_not_duplicate_the_dispatch_list():
    """rerenderActiveView handles eight views. A second copy of that list here,
    which is a guess about the other, is how a view comes to silently not
    repaint, so it reports whether it rendered instead."""
    fn = body_of("applyKnowledgeLevel")
    assert "if (rerenderActiveView()) return;" in fn
    rerender = CODE[CODE.index("const rerenderActiveView = () => {"):]
    rerender = rerender[:rerender.index("\n};")]
    # The *end* of the dispatch chain specifically. The first version checked
    # only that the words appeared somewhere, and the early returns for home
    # and settings satisfied that while the chain's own fall-through was
    # deleted: an unhandled view would have reported success and never
    # repainted.
    chain = rerender[rerender.index("if (STATE.view === 'swing')"):]
    assert "else return false;" in chain
    assert chain.rstrip().endswith("return true;")


def test_the_first_paint_corrects_itself_only_when_it_has_to():
    """The policy comes from the catalogue, so it is unknown on the first paint.
    A reader on the default sees no difference; one on Simple or Professional
    would get a single paint of the default's glosses."""
    assert "const assumed = explainPolicy();" in CODE
    assert "if (explainPolicy() !== assumed) applyKnowledgeLevel();" in CODE


# ------------------------------------------------------------------------- CSS

def test_the_inline_definition_is_a_block_not_a_floating_panel():
    """The point of this mode is that the explanation stays put and can be read
    next to its subject, which a tooltip cannot do: it covers the thing it is
    explaining and vanishes on the way to reading it."""
    rule = CSS[CSS.index(".gloss-inline {"):]
    rule = rule[:rule.index("}")]
    assert "display: block" in rule
    assert "position: absolute" not in rule and "position: fixed" not in rule


def test_the_clickable_term_looks_clickable_and_focusable():
    rule = CSS[CSS.index(".gloss-term.is-inline {"):]
    rule = rule[:rule.index("}")]
    assert "cursor" in rule
    assert ".gloss-term.is-inline:focus-visible" in CSS
