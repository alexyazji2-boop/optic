/* A DOM that remembers what it was given, for rendering a chart under
 * JavaScriptCore and reading back what it drew.
 *
 * browser_stubs.js is the other shim here, and it records nothing: it exists
 * so app.js can be *evaluated*. This one keeps every element in NODES with its
 * tag, attributes and children, which is what a test needs to say "the band
 * was drawn in two runs" or "this candle was filled green". Only what
 * charts.js's lineChart reaches is here. Used by tests/test_stage_band.py.
 */
var NODES = [];
function mk(tag) {
  var n = { tag: tag, attrs: {}, children: [], style: {}, dataset: {}, textContent: '',
    setAttribute: function (k, v) { this.attrs[k] = String(v); },
    getAttribute: function (k) { return this.attrs[k] === undefined ? null : this.attrs[k]; },
    removeAttribute: function (k) { delete this.attrs[k]; },
    appendChild: function (c) { this.children.push(c); c.parentNode = this; return c; },
    insertBefore: function (c) { this.children.unshift(c); c.parentNode = this; return c; },
    removeChild: function () {}, remove: function () {},
    addEventListener: function () {}, removeEventListener: function () {},
    querySelector: function () { return null; }, querySelectorAll: function () { return []; },
    getBoundingClientRect: function () { return { width: 900, height: 400, left: 0, top: 0 }; },
    getBBox: function () { return { width: 30, height: 10, x: 0, y: 0 }; },
    getComputedTextLength: function () { return 30; },
    classList: { add: function () {}, remove: function () {}, contains: function () { return false; }, toggle: function () {} } };
  NODES.push(n); return n;
}
var document = { createElementNS: function (ns, tag) { return mk(tag); }, createElement: mk,
  createTextNode: function (t) { return { tag: '#text', textContent: t }; },
  documentElement: mk('html'), body: mk('body'), head: mk('head'),
  addEventListener: function () {}, querySelector: function () { return null; },
  querySelectorAll: function () { return []; }, getElementById: function () { return null; } };
var window = this;
window.document = document;
window.getComputedStyle = function () { return { getPropertyValue: function () { return ''; } }; };
window.requestAnimationFrame = function () {}; window.cancelAnimationFrame = function () {};
window.matchMedia = function () { return { matches: false, addEventListener: function () {}, addListener: function () {} }; };
window.addEventListener = function () {};
var localStorage = { getItem: function () { return null; }, setItem: function () {} };
function setTimeout(f) { return 0; } function clearTimeout() {}
