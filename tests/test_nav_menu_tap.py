"""Opening a section menu with a finger.

Reported from a phone: pressing Dossier showed no dropdown. Reproduced at 375px.
The menu opened on `:hover` and `:focus-within`, and a phone has neither. Safari
does not focus a `<button>` when you tap it, so `:focus-within` never matched,
and the same tap ran `switchView`, which replaces `nav.innerHTML` and destroys
the element any transient hover was sitting on. The seven pages never appeared,
and with no ticker loaded the tap landed on "No ticker loaded" with no facet
strip either, so it cost a page and returned nothing.

Two of these run the real functions under JavaScriptCore rather than reading
them, which is worth the setup here: the whole defect was a capability check
that did not exist, and a grep for one cannot tell a working check from a
plausible-looking one. `static/app.js` stops evaluating part-way under the
stubs, but function declarations hoist, so the two helpers are callable even
though the module-level code below them never ran.

The CSS test is structural rather than a grep: it finds the `@media (hover:
hover)` block by counting braces and asks which rules are inside it. "The file
contains `@media (hover: hover)`" would pass with the hover rules still sitting
outside it, which is the bug.
"""

import os
import re
import shutil
import subprocess

import pytest

JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")

APP_JS = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def _jsc():
    return JSC if os.path.exists(JSC) else shutil.which("jsc")


def strip_comments(js):
    """Drop `/* ... */` and `// ...` so a contract cannot match its own rationale.

    Every mis-written test in this project's history matched an explanatory
    comment sitting next to the code instead of the code, and this file is about
    a region with a twenty-line comment above it.
    """
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


def group_button_branch():
    """The body of the delegated handler's `data-group` branch, comments gone."""
    start = APP_JS.index("const groupBtn = evt.target.closest(")
    end = APP_JS.index("const secBtn = evt.target.closest(", start)
    return strip_comments(APP_JS[start:end])


def css_rule(head):
    """The declarations inside a rule, found by its opening line."""
    start = CSS.index(head) + len(head)
    return CSS[start:CSS.index("}", start)]


def media_block(query):
    """The text inside `@media <query> { ... }`, matched by counting braces."""
    head = "@media %s {" % query
    start = CSS.index(head) + len(head)
    depth = 1
    i = start
    while depth:
        if CSS[i] == "{":
            depth += 1
        elif CSS[i] == "}":
            depth -= 1
        i += 1
    return CSS[start:i - 1]


# ------------------------------------------------------------- run the code

@pytest.fixture(scope="module")
def ran():
    exe = _jsc()
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = r"""
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) { }

      // What does it ask the device, and does the answer decide anything?
      var asked = [];
      window.matchMedia = function (q) { asked.push(q); return { matches: true }; };
      var whenTrue = navMenusOpenOnTap();
      window.matchMedia = function (q) { asked.push(q); return { matches: false }; };
      var whenFalse = navMenusOpenOnTap();
      print('ASKED:' + asked.join('|'));
      print('FOLLOWS_DEVICE:' + whenTrue + ',' + whenFalse);

      // Every open menu closes, and every one of them says so.
      function fakeItem() {
        var open = true;
        var btn = { attrs: {},
                    setAttribute: function (k, v) { this.attrs[k] = v; } };
        return {
          btn: btn,
          isOpen: function () { return open; },
          classList: {
            remove: function (n) { if (n === 'open') open = false; },
            contains: function (n) { return n === 'open' && open; }
          },
          querySelector: function (sel) { return sel === 'button[data-group]' ? btn : null; }
        };
      }
      var a = fakeItem(), b = fakeItem();
      var selectorUsed = '';
      document.querySelectorAll = function (sel) {
        selectorUsed = sel;
        return sel === '.nav-item.open' ? [a, b] : [];
      };
      closeNavMenus();
      print('SELECTOR:' + selectorUsed);
      print('STILL_OPEN:' + a.isOpen() + ',' + b.isOpen());
      print('ARIA:' + a.btn.attrs['aria-expanded'] + ',' + b.btn.attrs['aria-expanded']);

      // A menu with no button must not throw on the way out.
      var lone = fakeItem();
      lone.querySelector = function () { return null; };
      document.querySelectorAll = function (sel) {
        return sel === '.nav-item.open' ? [lone] : [];
      };
      var threw = '';
      try { closeNavMenus(); } catch (e) { threw = String(e); }
      print('BUTTONLESS:' + (threw || 'ok') + ':' + lone.isOpen());
    """
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                          timeout=120)
    return proc.stdout + proc.stderr


def line(ran, key):
    assert key in ran, ran[-900:]
    return ran.split(key)[1].split("\n")[0].strip()


def test_the_tap_path_asks_the_device_whether_it_has_hover(ran):
    """`(hover: none)` and not a width. A 370px-wide desktop window still has a
    mouse, and an iPad in landscape is 1024px wide and still has none, so a
    breakpoint gets both of them wrong."""
    asked = line(ran, "ASKED:")
    assert asked == "(hover: none)|(hover: none)", asked
    assert "max-width" not in asked


def test_the_answer_actually_decides_it(ran):
    """A check whose result is ignored looks identical in a grep."""
    assert line(ran, "FOLLOWS_DEVICE:") == "true,false"


def test_closing_clears_every_open_menu(ran):
    """Plural on purpose. Tapping a second section closes the first, and that
    path runs through here rather than through a per-item handler."""
    assert line(ran, "SELECTOR:") == ".nav-item.open"
    assert line(ran, "STILL_OPEN:") == "false,false"


def test_closing_also_retracts_the_aria_state(ran):
    """The button carries aria-haspopup, so a screen reader is told a menu
    exists. Leaving aria-expanded on true after closing tells it the menu is
    still open, which is worse than never having set it."""
    assert line(ran, "ARIA:") == "false,false"


def test_closing_survives_a_menu_with_no_button(ran):
    """`querySelector` returning null is the ordinary shape of a DOM read, and
    an unguarded setAttribute on it would throw part-way through the loop,
    leaving the menus after it open."""
    assert line(ran, "BUTTONLESS:") == "ok:false"


# ------------------------------------------------------- the click it changes

def test_the_group_button_checks_for_tap_before_it_navigates():
    """Order is the whole fix. The check has to happen before switchView, not
    after: switchView repaints the strip, so a menu opened after it is opened on
    an element that has already been replaced."""
    branch = group_button_branch()
    assert "navMenusOpenOnTap()" in branch
    assert branch.index("navMenusOpenOnTap()") < branch.index("switchView(")


def test_the_tap_path_returns_instead_of_falling_through():
    """Without the return it would open the menu and then navigate, which is the
    original bug with a menu briefly drawn over the page it left."""
    branch = group_button_branch()
    opened = branch.index("classList.add('open')")
    navigated = branch.index("switchView(")
    assert "return;" in branch[opened:navigated]


def test_a_single_page_section_still_navigates_on_tap():
    """Home, Compare, Explore, Scan and Optic's Positions have one page each, so
    paintNav gives them a plain button with no .nav-item wrapper and no menu.
    Requiring the wrapper is what keeps them navigating."""
    branch = group_button_branch()
    assert "groupBtn.closest('.nav-item')" in branch
    assert re.search(r"if \(item && navMenusOpenOnTap\(\)\)", branch)


def test_choosing_a_page_closes_the_menu_by_both_routes():
    """Two things hold a menu open and choosing a page has to release both.
    `blur()` drops the focus that :focus-within reads, and closeNavMenus drops
    the class the tap sets. paintNav rebuilds the strip and would clear the class
    on its own, but only when the view changes, and tapping the page you are
    already on is the case where it does not."""
    start = APP_JS.index("const viewBtn = evt.target.closest(")
    tail = strip_comments(APP_JS[start:start + 900])
    assert "viewBtn.blur()" in tail
    assert "closeNavMenus()" in tail


def test_something_outside_the_strip_closes_it():
    """A menu that can only be closed by the control that opened it is a trap on
    a touchscreen, where there is no pointer to move away."""
    js = strip_comments(APP_JS)
    assert re.search(r"closest\('\.nav-item'\)\) return;\s*closeNavMenus\(\)", js)


def test_escape_closes_it():
    js = strip_comments(APP_JS)
    assert re.search(r"key === 'Escape'\) closeNavMenus\(\)", js)


def test_the_menu_button_starts_out_saying_it_is_closed():
    """aria-expanded is set on the tap path, so it has to exist in the markup
    paintNav writes or the first state a screen reader sees is no state at
    all."""
    assert 'aria-haspopup="true" aria-expanded="false"' in APP_JS


# --------------------------------------------------------------------- CSS

def test_hover_opening_is_scoped_to_devices_that_have_hover():
    """Unscoped, :hover fires on a touchscreen too: a tap sets it and it sticks
    until you tap elsewhere. Combined with the tap that navigated, the menu
    appeared over the page it had just taken you to."""
    block = media_block("(hover: hover)")
    assert ".nav-item:hover .nav-menu" in block
    outside = CSS.replace(block, "")
    assert ".nav-item:hover .nav-menu" not in outside
    assert ".nav-item:hover .nav-caret" not in outside


def test_the_pointer_bridge_is_scoped_with_it():
    """The 6px strip under each section exists so the menu does not close as the
    mouse crosses the gap. On a phone it is six pixels of whatever is underneath
    that cannot be tapped, for no benefit at all."""
    block = media_block("(hover: hover)")
    assert ".nav-item::after" in block
    assert ".nav-item::after" not in CSS.replace(block, "")


def test_the_tapped_open_rule_is_not_scoped_to_anything():
    """The class is set by JavaScript that has already decided the device, so a
    media query on the rule would be a second opinion that can disagree with the
    first."""
    block = media_block("(hover: hover)")
    assert ".nav-item.open .nav-menu" in CSS
    assert ".nav-item.open .nav-menu" not in block


def test_the_keyboard_route_is_not_scoped_either():
    """:focus-within is how this opens without a pointer of any kind, and it has
    to keep working on both sorts of device."""
    block = media_block("(hover: hover)")
    assert ".nav-item:focus-within .nav-menu" in CSS
    assert ".nav-item:focus-within .nav-menu" not in block


def test_a_tall_menu_fits_the_window_it_opens_in():
    """Seven pages do not fit a phone held sideways, and there is no scrolling
    out of the overflow: the window itself does not scroll (the app scrolls
    `main`, which is overflow: clip) and on a phone the menu is position: fixed,
    which the page cannot reach into either. Measured at 740x360 before the cap:
    the menu ran to y=433 in a 360px viewport and elementFromPoint at Long-Term's
    coordinates returned page content. After: it ends at 340, scrolls inside
    itself, and the same point returns the button.

    This was always true for a hover device in a short window. Opening on tap is
    what made it likely to be met."""
    rule = css_rule(".nav-menu {\n  position: absolute;")
    assert "max-height:" in rule
    assert "overflow-y: auto" in rule


def test_the_height_cap_is_measured_from_the_bar_rather_than_guessed():
    """The strip is one, two or three rows depending on width, which is the whole
    reason --topbar-h is published by a ResizeObserver. A constant here would be
    wrong at two of those three heights."""
    rule = css_rule(".nav-menu {\n  position: absolute;")
    cap = [ln for ln in rule.splitlines() if "max-height:" in ln][0]
    assert "var(--topbar-h" in cap, cap
