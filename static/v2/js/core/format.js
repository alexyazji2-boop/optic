// Number, money, percent and date formatting for v2. Pure functions, no DOM.
// House rules: a minus sign is U+2212, changes always carry a sign, and no em
// dashes reach the screen (clean() swaps any that arrive in server copy).

const MINUS = '−';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const isNum = (v) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));

export function num(v, dp = 2) {
  if (!isNum(v)) return 'n/a';
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp }).replace('-', MINUS);
}

export function signed(v, dp = 2, unit = '%') {
  if (!isNum(v)) return 'n/a';
  const n = Number(v);
  const s = n > 0 ? '+' : n < 0 ? MINUS : '';
  return s + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp }) + unit;
}

export function money(v, dp = 2) {
  if (!isNum(v)) return 'n/a';
  const n = Number(v);
  return (n < 0 ? MINUS : '') + '$' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
}

export function signedMoney(v, dp = 2) {
  if (!isNum(v)) return 'n/a';
  const n = Number(v);
  return (n > 0 ? '+' : n < 0 ? MINUS : '') + '$' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
}

export function compact(v) {
  if (!isNum(v)) return 'n/a';
  const n = Number(v), a = Math.abs(n);
  const out = a >= 1e12 ? num(n / 1e12, 2) + 'T' : a >= 1e9 ? num(n / 1e9, 1) + 'B' : a >= 1e6 ? num(n / 1e6, 1) + 'M' : a >= 1e3 ? num(n / 1e3, 1) + 'K' : num(n, 0);
  return out;
}

export const dir = (v) => (!isNum(v) ? 'flat' : Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : 'flat');

function parts(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  return { y, m, d, dow: new Date(Date.UTC(y, m - 1, d)).getUTCDay() };
}
export const shortDate = (iso) => { if (!iso) return ''; const p = parts(iso); return `${MONTHS[p.m - 1]} ${p.d}`; };
export const longDate = (iso) => { if (!iso) return ''; const p = parts(iso); return `${DAYS[p.dow]} ${MONTHS[p.m - 1]} ${p.d}`; };
export const fullDate = (iso) => { if (!iso) return ''; const p = parts(iso); return `${MONTHS[p.m - 1]} ${p.d}, ${p.y}`; };
export const monthName = (m) => MONTHS[m - 1];

// "4 minutes ago", "2 hours ago", "Fri 4:00 PM": used for freshness labels.
export function ago(iso, now = Date.now()) {
  if (!iso) return '';
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return '';
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 90) return 'just now';
  const m = Math.round(s / 60);
  if (m < 60) return `${m} minutes ago`;
  const h = Math.round(m / 60);
  if (h < 36) return `${h} hour${h === 1 ? '' : 's'} ago`;
  const d = Math.round(h / 24);
  return `${d} days ago`;
}

// Provider exceptions never reach a reader (owner, 2026-10-19: "SEC XBRL unavailable: HTTP Error 404:
// Not Found" on SPY's Overview). Each fragment becomes a plain sentence; the original is kept for
// diagnostics in window.__opticDiag (read it from the console).
const RAW = [
  [/SEC XBRL unavailable:?\s*HTTP Error 404:?\s*Not Found\.?/gi, 'The SEC has no company figures for this symbol.'],
  [/SEC XBRL unavailable:?[^.]*\.?/gi, 'The SEC company figures did not load just now.'],
  [/HTTP Error (\d{3}):?\s*[A-Za-z ]*\.?/g, (m, c) => (c === '404' ? 'The source has nothing for this symbol.' : c === '429' ? 'The source is limiting requests; try again shortly.' : 'The source did not answer just now.')],
  [/<urlopen error[^>]*>\.?/gi, 'The source could not be reached.'],
  [/\b(?:HTTPSConnectionPool|ConnectionError|ReadTimeout|TimeoutError|JSONDecodeError|KeyError|TypeError|ValueError|AttributeError|Traceback)\b[^.]*\.?/g, 'The source did not answer in a usable form.'],
];
function plain(t) {
  let out = t;
  for (const [re, to] of RAW) out = out.replace(re, to);
  if (out !== t) { try { (window.__opticDiag = window.__opticDiag || []).push(t); } catch (e) { /* no window in tests */ } }
  return out;
}

export function clean(s) {
  return plain(String(s == null ? '' : s)).replace(/\s*—\s*/g, ': ').replace(/–/g, ' to ');
}

/**
 * Written prose as HTML: escaped, then the model's **bold** kept as bold (the Read's figures arrive so marked) and
 * nothing else interpreted. The markers printed as they were on the Read (design review, 2026-10-19).
 */
export function bolded(s) {
  return esc(clean(s)).replace(/\*\*([^*\n]+?)\*\*/g, '<b>$1</b>').replace(/\*\*/g, '');
}

export function capFirst(s) {
  const t = String(s == null ? '' : s);
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// The legacy app's 0 to 100 mapping for scores on a model's own scale
// (static/app.js score100). Kept identical so both frontends show the same number.
export function score100(score, min, max) {
  if (!isNum(score)) return null;
  const lo = isNum(min) && min < 0 ? min : -100;
  const hi = isNum(max) && max > 0 ? max : 100;
  const s = Math.max(lo, Math.min(hi, Number(score)));
  return s >= 0 ? 50 + 50 * s / hi : 50 - 50 * s / lo;
}

// The server's reason when billing is off names the settings it needs ("set STRIPE_SECRET_KEY, ..."): an
// operator's note. A reader is told plainly; the owner also sees the setup detail (2026-10-19).
export function billingOff(reason, owner) {
  const plain = 'Plans are not on sale yet. Every account is on Free.';
  if (!reason) return plain;
  return /[A-Z]{3,}_[A-Z_]{3,}/.test(reason) ? (owner ? `${plain} ${clean(reason)}` : plain) : clean(reason);
}
