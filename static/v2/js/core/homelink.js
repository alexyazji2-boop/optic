// "Show on Home" from anywhere: Home's linked panels follow one ticker (pages/workspace.js).
// When Home is open it takes the ticker itself (it listens for v2:homelink and keeps the
// event); otherwise the ticker is written into the saved workspace for Home's next visit.
const KEY = 'optic.v2.workspace.v1';

export function linkHome(sym) {
  sym = String(sym || '').trim().toUpperCase();
  if (!/^[A-Z0-9.^=-]{1,12}$/.test(sym)) return false;
  const ev = new CustomEvent('v2:homelink', { detail: sym, cancelable: true });
  if (!window.dispatchEvent(ev)) return true;
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || 'null');
    localStorage.setItem(KEY, JSON.stringify(Object.assign(v && typeof v === 'object' ? v : {}, { link: sym })));
    return true;
  } catch (e) { return false; }
}
