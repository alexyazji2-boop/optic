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

export function clean(s) {
  return String(s == null ? '' : s).replace(/\s*—\s*/g, ': ').replace(/–/g, ' to ');
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
