// Whose things this browser is holding. A port of the device-session logic in
// static/app.js (keepDeviceSession and its helpers), with the same keys and
// the same shelf format, so the classic app and v2 agree about who a browser
// is for. tests/test_device_session.py checks PERSONAL_KEYS here matches the
// classic list.
//
// The rule: personal keys belong to whoever SESSION_HOLDER_KEY names. When a
// different person settles (sign in, sign out, another account), their things
// go on a shelf and the newcomer's come back, through a reload so no page ever
// shows one person's data under another's name.

export const SESSION_HOLDER_KEY = 'optic.session.holder.v1';
export const SESSION_SHELF_PREFIX = 'optic.session.shelf.';
export const SESSION_NEXT_KEY = 'optic.session.next';
export const SESSION_GUEST = 'guest';

export const PERSONAL_KEYS = [
  'optic.brokerage.scope.v1',
  'optic.recent.v1',
  'optic.scan.recent.v1',
  'optic.pulse.history.v1',
  'optic.research.v1',
  'optic.chart.watch.v1',
  'optic.watchlists.v1',
  'optic.watchlist.account.v1',
  'optic.watches.v1',
  'optic.screener.v1',
  'optic.signals.v1',
  'optic.thesis.v1',
  'optic.valuation.v1',
  'optic.dcf.v1',
  'optic.chart.drawings.v1',
  'optic.chart.drawings.v2',
  'optic.chart.notes.v1',
  'optic.chart.checks.v1',
  'optic.chart.stopcheck.v1',
  'optic.paper.v1',
  'optic.roth.inputs',
  'optic.snapshots.v1',
  'optic.entry.budget.v1',
  'optic.v2.picker.v1',
  'optic.writeToken',
  'optic.auth.passkeyOffered',
];

const GUEST_THING_LABELS = {
  'optic.recent.v1': 'recent searches',
  'optic.chart.watch.v1': 'a watchlist',
  'optic.watchlists.v1': 'a watchlist',
  'optic.watches.v1': 'watches',
  'optic.thesis.v1': 'theses',
  'optic.research.v1': 'saved research',
  'optic.valuation.v1': 'valuation scenarios',
  'optic.signals.v1': 'signal history',
  'optic.screener.v1': 'a screen',
  'optic.paper.v1': 'paper trades',
  'optic.chart.drawings.v2': 'chart drawings',
  'optic.chart.notes.v1': 'chart notes',
  'optic.pulse.history.v1': 'Milo conversations',
};
const GUEST_THING_CONTENT = {
  'optic.screener.v1': (v) => !!(v && ((v.filters || []).length || (v.states || []).length)),
};

let holderSeen = null;
let seen = null;
let ending = false;
let stuck = false;
let said = '';
let askPending = null;

const shelfKey = (who) => SESSION_SHELF_PREFIX + who;

function readShelf(who) {
  try {
    const raw = JSON.parse(localStorage.getItem(shelfKey(who)) || 'null');
    return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : null;
  } catch (e) { return null; }
}

export function swapDeviceSession(from, to) {
  const leaving = readShelf(from) || {};
  PERSONAL_KEYS.forEach((key) => {
    const value = localStorage.getItem(key);
    if (value !== null) leaving[key] = value;
  });
  localStorage.setItem(shelfKey(from), JSON.stringify(leaving));
  PERSONAL_KEYS.forEach((key) => localStorage.removeItem(key));
  localStorage.setItem(SESSION_HOLDER_KEY, to);
  const coming = readShelf(to) || {};
  let whole = true;
  Object.keys(coming).forEach((key) => {
    if (PERSONAL_KEYS.indexOf(key) === -1 || typeof coming[key] !== 'string') return;
    try { localStorage.setItem(key, coming[key]); } catch (e) { whole = false; }
  });
  if (whole) localStorage.removeItem(shelfKey(to));
}

function storedHasContent(raw) {
  let value;
  try { value = JSON.parse(raw); } catch (e) { return !!raw; }
  const full = (x) => (Array.isArray(x) ? x.some(full)
    : (x && typeof x === 'object') ? Object.values(x).some(full)
      : (x !== null && x !== undefined && x !== '' && x !== false));
  return full(value);
}

export function guestThingsHere() {
  const found = [];
  Object.keys(GUEST_THING_LABELS).forEach((key) => {
    let raw = null;
    try { raw = localStorage.getItem(key); } catch (e) { raw = null; }
    if (raw === null) return;
    let has;
    if (GUEST_THING_CONTENT[key]) {
      try { has = GUEST_THING_CONTENT[key](JSON.parse(raw)); } catch (e) { has = false; }
    } else has = storedHasContent(raw);
    const label = GUEST_THING_LABELS[key];
    if (has && found.indexOf(label) < 0) found.push(label);
  });
  return found;
}

/** The guest's things become the account's: they stay where they are. */
export function bringGuestThings() {
  const ask = askPending;
  if (!ask) return false;
  askPending = null;
  try { localStorage.setItem(SESSION_HOLDER_KEY, ask.who); holderSeen = ask.who; } catch (e) { /* refused */ }
  return true;
}

/** Somebody else's: shelved for the next guest; the account starts clean. */
export function keepGuestThingsOut() {
  const ask = askPending;
  if (!ask) return false;
  askPending = null;
  try { localStorage.setItem(SESSION_HOLDER_KEY, SESSION_GUEST); } catch (e) { return false; }
  holderSeen = SESSION_GUEST;
  try {
    sessionStorage.setItem(SESSION_NEXT_KEY, JSON.stringify({ to: ask.who, said: 'in' }));
  } catch (e) {
    try { swapDeviceSession(SESSION_GUEST, ask.who); } catch (err) { return false; }
  }
  ending = true;
  location.reload();
  return true;
}

/**
 * Called with every settled auth state. Returns 'reload' when the page is
 * about to reload into a new session, 'ask' when a guest's things are waiting
 * for an answer (onAsk is called with {who, things}), or 'ok'.
 */
export function keepDeviceSession(user, onAsk) {
  const who = user && user.id ? String(user.id) : SESSION_GUEST;
  const before = seen;
  seen = who;
  if (ending) return 'reload';
  let holder;
  try { holder = localStorage.getItem(SESSION_HOLDER_KEY); } catch (e) { return 'ok'; }
  if (holder === who) { holderSeen = holder; return 'ok'; }
  if (holder === null || (holder === SESSION_GUEST && !readShelf(who))) {
    const things = who === SESSION_GUEST ? [] : guestThingsHere();
    if (things.length) {
      if (!askPending) { askPending = { who, holder, things }; if (onAsk) onAsk(askPending); }
      return 'ask';
    }
    try { localStorage.setItem(SESSION_HOLDER_KEY, who); holderSeen = who; } catch (e) { /* refused */ }
    return 'ok';
  }
  if (stuck) return 'ok';
  const word = before === null || before === who ? '' : (who === SESSION_GUEST ? 'out' : 'in');
  try {
    sessionStorage.setItem(SESSION_NEXT_KEY, JSON.stringify({ to: who, said: word }));
  } catch (e) {
    try { swapDeviceSession(holder, who); } catch (err) { return 'ok'; }
  }
  ending = true;
  location.reload();
  return 'reload';
}

/** For a deleted account: the person carries on as a guest with what is here. */
export function handDeviceSessionToGuest() {
  try { localStorage.setItem(SESSION_HOLDER_KEY, SESSION_GUEST); holderSeen = SESSION_GUEST; } catch (e) { /* refused */ }
}

/** True while personal keys may be read and written for this person. */
export function holds(user) {
  const who = user && user.id ? String(user.id) : SESSION_GUEST;
  let holder = null;
  try { holder = localStorage.getItem(SESSION_HOLDER_KEY); } catch (e) { return false; }
  return holder === who || (holder === null && who === SESSION_GUEST);
}

/** What the last reload switched to, to say once ('in', 'out' or ''). */
export const switchedSaid = () => said;
export const isEnding = () => ending;

// Runs as the module loads, before any store is read.
(function beginDeviceSession() {
  let next = null;
  try {
    next = JSON.parse(sessionStorage.getItem(SESSION_NEXT_KEY) || 'null');
    sessionStorage.removeItem(SESSION_NEXT_KEY);
  } catch (e) { next = null; }
  try { holderSeen = localStorage.getItem(SESSION_HOLDER_KEY); } catch (e) { return; }
  if (!next || typeof next.to !== 'string' || !next.to) return;
  try {
    if (holderSeen !== null && holderSeen !== next.to) swapDeviceSession(holderSeen, next.to);
    holderSeen = localStorage.getItem(SESSION_HOLDER_KEY);
  } catch (e) { /* checked below */ }
  if (holderSeen !== next.to) { stuck = true; return; }
  said = next.said === 'in' || next.said === 'out' ? next.said : '';
}());

// Another tab switched who this browser is for: start again here too.
window.addEventListener('storage', (evt) => {
  if (evt.key !== SESSION_HOLDER_KEY || evt.newValue === null || ending) return;
  if (holderSeen === null) { holderSeen = evt.newValue; return; }
  if (evt.newValue === holderSeen) return;
  ending = true;
  location.reload();
});
