/* Just enough browser for JavaScriptCore to *evaluate* static/app.js.
 *
 * This is not a test environment and nothing here is meant to behave: every
 * stub exists so that module-level evaluation reaches the end of the file, and
 * a stub that returns null part-way through is fine. The point is the parse and
 * the function declarations, which hoist.
 *
 * Used by tests/test_js_parses.py. It exists because two separate edits in one
 * session deleted `maLabel` while twelve call sites still referenced it, and
 * nothing caught it: there is no JS runner here, Python cannot see a
 * ReferenceError, and the app kept rendering every panel that did not touch
 * that function.
 */
// Minimal DOM/browser stubs: app.js only needs these to reach the end of
// evaluation. Nothing here is called, so a stub that returns an object is enough.
var noop = function () { return undefined; };
function elem() {
  return { style: {}, dataset: {}, classList: { add: noop, remove: noop, contains: function () { return false; }, toggle: noop },
    appendChild: noop, removeChild: noop, remove: noop, setAttribute: noop, getAttribute: function () { return null; },
    addEventListener: noop, removeEventListener: noop, querySelector: function () { return null; },
    querySelectorAll: function () { return []; }, insertAdjacentHTML: noop, focus: noop, click: noop,
    getBoundingClientRect: function () { return { top: 0, left: 0, width: 0, height: 0, right: 0, bottom: 0, x: 0, y: 0 }; },
    innerHTML: '', textContent: '', value: '', checked: false, children: [], parentElement: null, closest: function () { return null; } };
}
var document = { documentElement: elem(), body: elem(), head: elem(),
  createElement: elem, createElementNS: elem, createTextNode: elem,
  getElementById: function () { return null; }, querySelector: function () { return null; },
  querySelectorAll: function () { return []; }, addEventListener: noop, removeEventListener: noop,
  cookie: '', readyState: 'complete', title: '', visibilityState: 'visible' };
var localStorage = { getItem: function () { return null; }, setItem: noop, removeItem: noop, clear: noop, key: noop, length: 0 };
var location = { href: 'http://localhost/', pathname: '/', search: '', hash: '', origin: 'http://localhost', reload: noop, replace: noop, assign: noop };
var navigator = { userAgent: 'jsc', language: 'en-US', clipboard: {}, credentials: {} };
var window = this;
window.document = document; window.localStorage = localStorage; window.location = location;
window.navigator = navigator; window.matchMedia = function () { return { matches: false, addEventListener: noop, addListener: noop }; };
window.addEventListener = noop; window.requestAnimationFrame = noop; window.cancelAnimationFrame = noop;
window.getComputedStyle = function () { return { getPropertyValue: function () { return ''; }, color: '', backgroundColor: '', position: 'static', lineHeight: '16px' }; };
window.ResizeObserver = function () { return { observe: noop, unobserve: noop, disconnect: noop }; };
window.IntersectionObserver = window.ResizeObserver;
window.fetch = function () { return { then: function () { return this; }, catch: function () { return this; } }; };
window.setTimeout = noop; window.setInterval = noop; window.clearTimeout = noop; window.clearInterval = noop;
var getComputedStyle = window.getComputedStyle;
var requestAnimationFrame = noop, cancelAnimationFrame = noop, ResizeObserver = window.ResizeObserver;
var IntersectionObserver = window.IntersectionObserver, matchMedia = window.matchMedia, fetch = window.fetch;
var setTimeout = noop, setInterval = noop, clearTimeout = noop, clearInterval = noop;
var alert = noop, prompt = function () { return null; }, confirm = function () { return false; };
var Response = function () {}, Event = function () {}, CustomEvent = function () {}, URLSearchParams = function () { return { get: noop, set: noop }; };
