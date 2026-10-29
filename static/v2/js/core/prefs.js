// Device preferences, shared with the classic app through its own keys, so a
// choice made in either Settings holds in both: theme (optic.theme), text
// size (optic.ui.scale.v1), time zone (optic.timezone), density (optic.mode.v1)
// and the knowledge level (optic.knowledge.v1, five levels since Phase 05). The
// level is also kept on a signed-in reader's account (core/store.js syncs it);
// the rest are device settings that stay put on sign-in.

const THEME_KEY = 'optic.theme', SCALE_KEY = 'optic.ui.scale.v1', TZ_KEY = 'optic.timezone';
const KNOW_KEY = 'optic.knowledge.v1', ASKED_KEY = 'optic.knowledge.asked.v1';
// The five levels in slider order (post-demo Phase 05, app/knowledge.py). Their labels, blurbs and previews are the
// server's (/api/knowledge/modes); only the ids and their order are here, and the ids before Phase 05 map on read.
export const LEVEL_IDS = ['new', 'beginner', 'intermediate', 'advanced', 'expert'];
const LEVELS = { new: 0, beginner: 1, intermediate: 2, advanced: 3, expert: 4 };
const LEGACY = { simple: 'new', literate: 'intermediate', professional: 'expert', adaptive: 'intermediate' };
const DEFAULT_MODE = 'intermediate';

// The classic list, word for word (static/app.js TIMEZONES).
export const TIMEZONES = [
  { id: 'auto', label: 'My device’s time zone' },
  { id: 'America/New_York', label: 'New York. Eastern (market time)' },
  { id: 'America/Chicago', label: 'Chicago: Central' },
  { id: 'America/Denver', label: 'Denver: Mountain' },
  { id: 'America/Los_Angeles', label: 'Los Angeles. Pacific' },
  { id: 'America/Toronto', label: 'Toronto' },
  { id: 'America/Sao_Paulo', label: 'São Paulo' },
  { id: 'Europe/London', label: 'London' },
  { id: 'Europe/Paris', label: 'Paris / Berlin / Madrid' },
  { id: 'Europe/Istanbul', label: 'Istanbul' },
  { id: 'Asia/Dubai', label: 'Dubai' },
  { id: 'Asia/Kolkata', label: 'Mumbai' },
  { id: 'Asia/Singapore', label: 'Singapore' },
  { id: 'Asia/Hong_Kong', label: 'Hong Kong' },
  { id: 'Asia/Tokyo', label: 'Tokyo' },
  { id: 'Australia/Sydney', label: 'Sydney' },
  { id: 'UTC', label: 'UTC' },
];
// v2's type is set at the classic "Default" size (the original plus 15%), so
// Compact and Large are that size scaled to the classic 1 and 1.3.
export const SCALES = { compact: 1 / 1.15, default: 1, large: 1.3 / 1.15 };

const get = (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } };
const put = (k, v) => { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { /* private mode */ } };
const subs = new Set();
export function onChange(fn) { subs.add(fn); return () => subs.delete(fn); }
const emit = (what) => subs.forEach((fn) => { try { fn(what); } catch (e) { console.error(e); } });

/* ---------------- theme ---------------- */
// v2 is dark unless the reader chooses Light, or chooses to match the system
// (VISUAL-SPEC-DARK.md, X1). The key is shared with the classic app, which
// reads 'light', 'dark' and 'system' the same way; only an absent key differs
// (dark here, follow-the-OS there).
export function theme() { const t = get(THEME_KEY); return t === 'light' || t === 'system' ? t : 'dark'; }
export function applyTheme() {
  const t = theme(), root = document.documentElement;
  const light = t === 'light' || (t === 'system' && matchMedia('(prefers-color-scheme: light)').matches);
  root.setAttribute('data-theme', light ? 'ivory' : 'charcoal');
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', light ? '#f6f2e9' : '#0b0b0a');
}
export function setTheme(t) { put(THEME_KEY, t === 'light' || t === 'system' ? t : 'dark'); applyTheme(); emit('theme'); }
try { matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => { if (theme() === 'system') applyTheme(); }); } catch (e) { /* no matchMedia in tests */ }

/* ---------------- motion ---------------- */
// v2's own setting (2026-10-24; Classic has none): 'system' follows the operating system's reduced-motion setting,
// 'reduce' asks for the same stillness whatever the system says. It sets html[data-motion], which the CSS and
// core/dom.js reducedMotion() read, and Scout goes still with it unless the reader chose his motion themselves.
const MOTION_KEY = 'optic.v2.motion.v1';
export function motion() { return get(MOTION_KEY) === 'reduce' ? 'reduce' : 'system'; }
export function applyMotion() {
  if (motion() === 'reduce') document.documentElement.setAttribute('data-motion', 'reduce');
  else document.documentElement.removeAttribute('data-motion');
  try { if (window.OpticScout) window.OpticScout.setMotion(null); } catch (e) { /* Scout not loaded yet: he reads it when he is */ }
}
export function setMotion(m) { put(MOTION_KEY, m === 'reduce' ? 'reduce' : null); applyMotion(); emit('motion'); }

/* ---------------- text size ---------------- */
export function scale() { const s = get(SCALE_KEY); return SCALES[s] ? s : 'default'; }
export function applyScale() {
  const s = scale();
  if (s === 'default') document.documentElement.style.removeProperty('zoom');
  else document.documentElement.style.zoom = String(SCALES[s]);
}
export function setScale(s) { put(SCALE_KEY, SCALES[s] && s !== 'default' ? s : null); applyScale(); emit('scale'); }

/* ---------------- time zone ---------------- */
export function timezone() { const z = get(TZ_KEY); return z && TIMEZONES.some((x) => x.id === z) ? z : 'auto'; }
export function zone() {
  const z = timezone();
  if (z !== 'auto') return z;
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (e) { return 'UTC'; }
}
export function setTimezone(z) { put(TZ_KEY, TIMEZONES.some((x) => x.id === z) ? z : 'auto'); emit('timezone'); }
export function zoneAbbrev(z = zone(), at = new Date()) {
  try { return new Intl.DateTimeFormat('en-US', { timeZone: z, timeZoneName: 'short' }).formatToParts(at).find((p) => p.type === 'timeZoneName').value; } catch (e) { return z; }
}
/** "Aug 14, 2026, 11:00 AM" in the reader's zone. */
export function stamp(iso, z = zone()) {
  if (!iso) return '';
  const d = new Date(iso); if (Number.isNaN(d.getTime())) return '';
  try { return d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: z }); } catch (e) { return d.toISOString(); }
}
/** "Oct 16, 9:57 pm" in the reader's zone, for dense lists. */
export function dayTime(iso, z = zone()) {
  if (!iso) return '';
  const d = new Date(iso); if (Number.isNaN(d.getTime())) return '';
  try { return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: z })}, ${d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: z }).replace(':00 ', ' ').toLowerCase()}`; } catch (e) { return d.toISOString(); }
}
/** A clock time in a zone, the classic way: "9:30 am", "4 pm". */
export function clock(iso, z = zone()) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: z }).replace(':00 ', ' ').toLowerCase(); } catch (e) { return ''; }
}

/* ---------------- the knowledge level (how things are explained) ---------------- */
// One value for the reader, on Classic's key: Milo's answers, deep research, the written briefing and how a page's
// terms explain themselves all read it (D-026). It changes words, never figures (app/knowledge.py INVARIANT).
const levelOf = (id) => { const k = String(id || ''); return k in LEVELS ? k : LEGACY[k] || null; };
export function knowledge() {
  const k = get(KNOW_KEY), id = levelOf(k);
  if (id && id !== k) put(KNOW_KEY, id);   // an id from before Phase 05, rewritten once so both apps read the same
  return id || DEFAULT_MODE;
}
/** The level's position on the slider, 0 (New to Markets) to 4 (Expert). */
export const levelIndex = (id = knowledge()) => LEVELS[levelOf(id) || DEFAULT_MODE];
/** Whether the reader has chosen a level (or answered the question by keeping the default). */
export const knowledgeChosen = () => get(ASKED_KEY) === '1';
/** Set the level (the slider, wherever it is). `quiet` is for the account's value arriving at sign-in, which is
 *  written here without being sent back. */
export function setKnowledge(id, { quiet = false } = {}) {
  const lv = levelOf(id); if (!lv) return false;
  const changed = lv !== knowledge();
  put(KNOW_KEY, lv); put(ASKED_KEY, '1');
  if (changed) emit(quiet ? 'knowledge-synced' : 'knowledge');
  return changed;
}
/** How a page's own terms explain themselves at this level, as Classic's catalogue says: the definition shown with the
 *  term (New to Markets), the term marked to explain itself (Beginner to Advanced), or left plain (Expert). */
export const explainPolicy = (id = knowledge()) => (levelOf(id) === 'new' ? 'inline' : levelOf(id) === 'expert' ? 'off' : 'on_demand');

/* ---------------- density (what a page shows) ---------------- */
// Simple or Advanced, one state of its own (post-demo overhaul, Phase 04, D-019). Simple leads with each page's main
// finding and folds the specialist research; Advanced opens it, and Home shows every panel of its layout. It used to
// be the knowledge level read as a switch, so "Show advanced analysis" on a Dossier also changed how Milo and every
// page explained things (BUG-002). Kept on Classic's own key for it, optic.mode.v1, with Classic's values ('simple',
// 'pro'); Classic now derives its density from its knowledge ladder and does not read the key.
const DENSITY_KEY = 'optic.mode.v1';
export function density() {
  const d = get(DENSITY_KEY);
  if (d === 'pro') return 'advanced';
  if (d === 'simple') return 'simple';
  // never set: taken once from the knowledge level, so a reader who had turned on "Show advanced analysis" (which
  // wrote the knowledge level) still sees the advanced sections, then kept apart from it
  const from = levelIndex() >= LEVELS.advanced ? 'advanced' : 'simple';
  put(DENSITY_KEY, from === 'advanced' ? 'pro' : 'simple');
  return from;
}
export function setDensity(d) {
  const v = d === 'advanced' ? 'pro' : 'simple';
  if (get(DENSITY_KEY) === v) return;
  put(DENSITY_KEY, v); emit('density');
}
export function advancedOn() { return density() === 'advanced'; }
/** "Show advanced analysis": density only. */
export function setAdvanced(on) { setDensity(on ? 'advanced' : 'simple'); }
