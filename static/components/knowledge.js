/* Knowledge modes: the client half.
 *
 * First file under static/components/, and the pattern it sets is the one
 * charts.js already uses: a classic script loaded before app.js, exposing what
 * app.js consumes. Not an ES module, deliberately. app.js would have to become
 * one to import from here, its 609 top-level functions would stop being global,
 * and tests/test_js_parses.py loads it under JavaScriptCore with script
 * semantics — that harness is the only thing in the project that catches a
 * deleted function with live call sites, and it exists because `maLabel` was
 * removed twice while twelve places still called it. Module syntax is not worth
 * that.
 *
 * WHAT LIVES HERE. The reader's level, the selector that changes it, and the
 * two questions the rest of the app asks: how dense should this view be, and
 * should a term explain itself where it appears. The vocabulary, the prompt
 * registers and the level numbers are the server's (app/knowledge.py) and are
 * fetched; this file holds no copy of them except the one noted below.
 */

(function (global) {
  'use strict';

  var STORE_KEY = 'optic.knowledge.v1';
  var DEFAULT_MODE = 'literate';

  /* The one thing duplicated from the server, and why.
   *
   * Panels are rendered on the first paint, before any fetch has answered, and
   * the density decision needs an integer at that moment. Five integers is the
   * smallest thing that can be copied to avoid rendering the whole app at the
   * wrong level for one frame and then reflowing it.
   *
   * Labels, blurbs and registers are NOT here: they arrive from
   * /api/knowledge/modes and there is exactly one copy of them.
   * tests/test_knowledge_modes.py asserts this table agrees with the server's,
   * because two records of one fact drift and the symptom would be panels at a
   * density the selector does not claim. */
  var LEVELS = {
    simple: 0,
    literate: 1,
    advanced: 2,
    professional: 3,
    adaptive: 1        // the answer adapts; the layout does not guess
  };

  var catalogue = null;          // filled from the server, once
  var listeners = [];

  function read() {
    try {
      var saved = localStorage.getItem(STORE_KEY);
      if (saved && Object.prototype.hasOwnProperty.call(LEVELS, saved)) return saved;
    } catch (e) { /* private mode */ }
    return DEFAULT_MODE;
  }

  function mode() { return read(); }

  function level() {
    var value = LEVELS[read()];
    return typeof value === 'number' ? value : LEVELS[DEFAULT_MODE];
  }

  /** Does a term explain itself where it appears, on request, or not at all? */
  function explain() {
    var found = catalogue && catalogue.modes
      ? catalogue.modes.filter(function (m) { return m.id === read(); })[0]
      : null;
    // Before the catalogue lands, the honest default is the one the default
    // mode uses: marked and explains itself when asked.
    return found ? found.explain : 'on_demand';
  }

  function set(id) {
    if (!Object.prototype.hasOwnProperty.call(LEVELS, id)) return;
    if (id === read()) return;
    try { localStorage.setItem(STORE_KEY, id); } catch (e) { /* private mode */ }
    listeners.forEach(function (fn) {
      // One listener throwing must not stop the others: a mode change that
      // half-applied would leave the page at two densities at once.
      try { fn(id); } catch (e) { /* keep going */ }
    });
  }

  function onChange(fn) { if (typeof fn === 'function') listeners.push(fn); }

  function modes() {
    return (catalogue && catalogue.modes) || [];
  }

  function current() {
    var found = modes().filter(function (m) { return m.id === read(); })[0];
    return found || { id: read(), label: '', glyph: '', blurb: '' };
  }

  async function load() {
    if (catalogue) return catalogue;
    try {
      var res = await fetch('/api/knowledge/modes', { headers: { Accept: 'application/json' } });
      if (res.ok) catalogue = await res.json();
    } catch (e) { /* the selector falls back to the current label alone */ }
    return catalogue;
  }

  /* The selector.
   *
   * Compact by construction: a button showing the current level, and a menu
   * only while open. The brief this was built from is explicit that the control
   * must be reachable from Ask Optic rather than buried in Settings, and just
   * as explicit that it must never dominate the interface, so it renders as one
   * chip and never as a row of five.
   *
   * `data-km-*` rather than `data-mode-*`: `data-set-mode` already belongs to
   * the Pro/Simple detail toggle in Settings, and a `data-*` attribute is a
   * crowded namespace in this app. A collision there does not error, it just
   * lets the wrong handler match first and swallow the click. */
  function selectorHTML(opts) {
    var o = opts || {};
    var now = current();
    var open = !!o.open;
    return '<div class="km" data-km-root>'
      + '<button type="button" class="km-btn" data-km-toggle'
      + ' aria-haspopup="true" aria-expanded="' + (open ? 'true' : 'false') + '"'
      + ' title="How much financial detail Optic assumes">'
      + (o.compact ? '' : '<span class="km-eyebrow">Optic mode</span>')
      /* No fallback label. Hardcoding "Financially Literate" here would be a
         second copy of a string the server owns, and the two would drift the
         day one of them is reworded. Until the catalogue lands the chip shows
         its eyebrow and caret alone for one round trip, which is honest about
         not knowing yet rather than confidently naming the wrong rung. */
      + '<span class="km-now">' + (now.glyph ? now.glyph + ' ' : '')
      + escapeHTML(now.label) + '</span>'
      + '<i class="km-caret" aria-hidden="true"></i>'
      + '</button>'
      + (open ? menuHTML() : '')
      + '</div>';
  }

  function menuHTML() {
    var here = read();
    var list = modes();
    if (!list.length) return '';
    return '<div class="km-menu" role="menu">'
      + list.map(function (m) {
        var on = m.id === here;
        return '<button type="button" class="km-opt' + (on ? ' on' : '') + '"'
          + ' role="menuitemradio" aria-checked="' + on + '"'
          + ' data-km-pick="' + m.id + '">'
          + '<span class="km-opt-head">'
          + '<span class="km-opt-glyph" aria-hidden="true">' + m.glyph + '</span>'
          + '<span class="km-opt-label">' + escapeHTML(m.label) + '</span>'
          + '</span>'
          + '<span class="km-opt-blurb">' + escapeHTML(m.blurb) + '</span>'
          + '</button>';
      }).join('')
      /* What it changes, and what it cannot. Both come from the server so the
         menu's promise and the behaviour have one source. A control that
         claimed to change the figures would be the one claim that matters. */
      + '<div class="km-foot">'
      + '<p class="km-foot-h">Changes</p><ul>'
      + ((catalogue && catalogue.changes) || []).map(function (c) {
        return '<li>' + escapeHTML(c) + '</li>';
      }).join('')
      + '</ul><p class="km-foot-h">Never changes</p><ul>'
      + ((catalogue && catalogue.never_changes) || []).map(function (c) {
        return '<li>' + escapeHTML(c) + '</li>';
      }).join('')
      + '</ul></div>'
      + '</div>';
  }

  function escapeHTML(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  global.OpticKnowledge = {
    mode: mode,
    level: level,
    explain: explain,
    set: set,
    onChange: onChange,
    load: load,
    modes: modes,
    current: current,
    selectorHTML: selectorHTML,
    menuHTML: menuHTML,
    LEVELS: LEVELS,
    DEFAULT_MODE: DEFAULT_MODE,
    STORE_KEY: STORE_KEY
  };
}(typeof window !== 'undefined' ? window : this));
