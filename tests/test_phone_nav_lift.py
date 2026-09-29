"""A phone's section menu opens where nothing can clip it.

Reported from an iPhone as "the dropdown menu on the phone does not work". On
a phone the section strip is a sideways scroller (135-179 at 375x812) inside
a fixed bar that clips, and the open menu is position: fixed below both, from
193.6. Chrome draws a fixed box outside its scroller, which is why the menus
opened in Chrome's phone emulation; Safari on iOS clips it to the scroller,
which leaves nothing of this one to see. The open menu now moves to a layer
on <body> and back when it closes.

Checked in Chrome at 375x812: tap opens, a second tap closes, an outside tap
closes, a page navigates, Enter opens and focuses a page, Tab walks the
pages and off the end, Shift+Tab and Escape come back to the button, and a
rotation to 740x360 closes it. At desktop width nothing moves. Not checked in
Safari itself: this Mac has no full Xcode, so no iOS Simulator.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _raw_fn(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     RAW, re.M | re.S).group()


def _js(prelude, names, scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    query = re.search(r"^const NAV_ROW_QUERY = [^\n]*$", RAW, re.M).group()
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n" + query + "\n"
           + prelude + "\n" + "\n".join(_raw_fn(n) for n in names)
           + "\n(function () {\n" + scenario + "\n})(); print('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


# A few DOM calls, just enough for these functions: elements know their
# parent, children, class list and whether they are attached to the document.
DOM = r"""
function El(tag, cls) { this.tagName = tag; this.className = cls || ''; this.children = []; this.parent = null; this.attrs = {}; this.id = '';
  var self = this;
  this.classList = { contains: function (c) { return (' ' + self.className + ' ').indexOf(' ' + c + ' ') >= 0; },
                     remove: function (c) { self.className = self.className.split(' ').filter(function (x) { return x !== c; }).join(' '); },
                     add: function (c) { if (!this.contains(c)) self.className += ' ' + c; } }; }
El.prototype.appendChild = function (c) { if (c.parent) c.parent.children.splice(c.parent.children.indexOf(c), 1); c.parent = this; this.children.push(c); return c; };
El.prototype.remove = function () { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } };
El.prototype.setAttribute = function (k, v) { this.attrs[k] = v; };
El.prototype.getAttribute = function (k) { return this.attrs[k]; };
El.prototype.focus = function () { focused = this; };
El.prototype.matches = function (sel) {
  var self = this;
  return sel.split(',').some(function (one) {
    one = one.trim();
    var m = one.match(/^(\w+)?((?:\.[\w-]+)*)(\[[\w-]+\])?$/);
    if (!m) throw new Error('stub cannot match ' + one);
    if (m[1] && m[1] !== self.tagName) return false;
    var classes = (m[2] || '').split('.').filter(Boolean);
    if (!classes.every(function (c) { return self.classList.contains(c); })) return false;
    if (m[3] && !(m[3].slice(1, -1) in self.attrs)) return false;
    return true;
  });
};
El.prototype.querySelectorAll = function (sel) {
  var out = [];
  (function walk(e) { e.children.forEach(function (c) { if (c.matches(sel)) out.push(c); walk(c); }); })(this);
  return out;
};
El.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };
Object.defineProperty(El.prototype, 'isConnected', { get: function () { var e = this; while (e.parent) e = e.parent; return e === body; } });
var body = new El('body');
var focused = null;
var phone = true;
var document = {
  body: body,
  createElement: function (t) { return new El(t); },
  getElementById: function (id) { return body.children.filter(function (c) { return c.id === id; })[0] || null; },
  querySelectorAll: function (sel) { return body.querySelectorAll(sel); },
};
function matchMedia(q) { assert(q === NAV_ROW_QUERY, 'asked ' + q); return { matches: phone }; }
var strip = body.appendChild(new El('nav', 'tabs tabs-group'));
var item = strip.appendChild(new El('div', 'nav-item open'));
var btn = item.appendChild(new El('button', 'nav-top'));
btn.attrs['data-group'] = 'security';
btn.attrs['aria-expanded'] = 'true';
var menu = item.appendChild(new El('div', 'nav-menu'));
var first = menu.appendChild(new El('button', 'nav-page'));
var current = menu.appendChild(new El('button', 'nav-page current'));
"""

FNS = ["navRailIsRow", "liftNavMenu", "returnNavMenus", "closeNavMenus",
       "focusNavPage", "closeLiftedNavMenu"]


def test_the_open_menu_moves_to_body_and_comes_back():
    _js(DOM, FNS, """
      var lifted = liftNavMenu(item);
      var layer = document.getElementById('nav-lift');
      assert(lifted === menu, 'liftNavMenu did not hand back the menu');
      assert(layer && menu.parent === layer && layer.parent === body, 'the menu stayed in the strip');
      assert(/\\btabs\\b/.test(layer.className), 'the layer is not a nav.tabs, so its pages lose their handler');
      returnNavMenus();
      assert(menu.parent === item, 'the menu did not go home');
      assert(!document.getElementById('nav-lift'), 'an empty layer was left on <body>');
    """)


def test_a_menu_whose_strip_was_rebuilt_is_dropped_not_stranded():
    _js(DOM, FNS, """
      liftNavMenu(item);
      strip.remove();                          // paintNav replaced the strip
      returnNavMenus();
      assert(!menu.parent, 'an orphan menu left on the page');
      assert(!document.getElementById('nav-lift'), 'the layer outlived it');
    """)


def test_nothing_moves_where_the_rail_is_a_column():
    _js(DOM, FNS, """
      phone = false;
      assert(liftNavMenu(item) === null, 'reported a lift that did not happen');
      assert(menu.parent === item && !document.getElementById('nav-lift'), 'moved on a desktop');
    """)


def test_the_keyboard_goes_into_the_menu_and_comes_back_to_its_button():
    _js(DOM, FNS, """
      liftNavMenu(item);
      focusNavPage(menu);
      assert(focused === current, 'focus went to the first page, not the one you are on');
      current.className = 'nav-page';
      focusNavPage(menu);
      assert(focused === first, 'with no current page, focus should take the first');
      closeLiftedNavMenu(menu);
      assert(menu.parent === item && !document.getElementById('nav-lift'), 'not closed');
      assert(!item.classList.contains('open') && btn.attrs['aria-expanded'] === 'false', 'still marked open');
      assert(focused === btn, 'focus did not come back to the section button');
    """)


def test_the_wiring_that_uses_them():
    tap = RAW[RAW.index("if (item && navMenusOpenOnTap()) {"):][:520]
    assert "const lifted = liftNavMenu(item);" in tap
    assert "if (lifted && evt.detail === 0) focusNavPage(lifted);" in tap
    close = _raw_fn("closeNavMenus")
    assert close.index("returnNavMenus();") < close.index("classList.remove('open')")
    paint = _raw_fn("paintNav")
    assert paint.index("returnNavMenus();") < paint.index("nav.innerHTML =")
    assert "evt.target.closest('#nav-lift')) return;" in RAW
    keys = RAW[RAW.index("document.addEventListener('keydown', (evt) => {\n  const lifted"):][:1100]
    assert "if (lifted) closeLiftedNavMenu(lifted);" in keys
    assert "const edge = evt.shiftKey ? pages[0] : pages[pages.length - 1];" in keys
    assert "if (evt.shiftKey) evt.preventDefault();" in keys
    assert "navRow.addEventListener('change', closeNavMenus)" in RAW


def test_the_lifted_menu_is_placed_and_shown_on_a_phone():
    phone = CSS[CSS.index("@media (max-width: 559px) {"):]
    lifted = re.search(r"\.nav-lift \.nav-menu \{([^}]*)\}", phone).group(1)
    for decl in ("position: fixed", "visibility: visible", "opacity: 1",
                 "left: var(--space-3)", "right: var(--space-3)"):
        assert decl in lifted
    assert "nav.tabs.nav-lift { display: contents; }" in phone
