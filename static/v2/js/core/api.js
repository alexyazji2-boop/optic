// The v2 API client. One place for: timeouts, the CSRF header on writes,
// a small in-memory cache with stale-while-revalidate, and errors classified
// so every screen can say plainly what went wrong.
//
// Freshness: responses carry their own "as of" (generated_at, freshness,
// data_source, degraded). asOf() pulls a consistent label out of them.

const CSRF_COOKIE = 'optic_csrf';
const CSRF_HEADER = 'X-Optic-CSRF';

export class ApiError extends Error {
  constructor(kind, status, message, body) {
    super(message);
    this.kind = kind;      // 'offline' | 'timeout' | 'auth' | 'forbidden' | 'notfound' | 'limit' | 'server' | 'bad'
    this.status = status;
    this.body = body;
  }
}

function cookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : '';
}

function classify(status) {
  if (status === 401) return 'auth';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'notfound';
  if (status === 409 || status === 422 || status === 400) return 'bad';
  if (status === 429) return 'limit';
  return 'server';
}

async function request(method, path, { body, timeout = 20000, signal } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort('timeout'), timeout);
  if (signal) signal.addEventListener('abort', () => ctrl.abort('cancelled'), { once: true });
  const headers = { Accept: 'application/json' };
  if (method !== 'GET') headers['Content-Type'] = 'application/json';
  // on reads too: the owner's pages check it on GET, as the classic app sends it
  const t = cookie(CSRF_COOKIE);
  if (t) headers[CSRF_HEADER] = t;
  let res;
  try {
    res = await fetch(path, { method, headers, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body), signal: ctrl.signal });
  } catch (e) {
    clearTimeout(timer);
    if (ctrl.signal.aborted && ctrl.signal.reason === 'timeout') throw new ApiError('timeout', 0, 'The server took too long to answer.');
    if (ctrl.signal.aborted) throw new ApiError('cancelled', 0, 'Cancelled.');
    throw new ApiError(navigator.onLine === false ? 'offline' : 'server', 0, navigator.onLine === false ? 'You appear to be offline.' : 'Could not reach Optic.');
  }
  clearTimeout(timer);
  // v2 closed to this reader (owner-only preview or emergency shutdown): core/build.js offers the classic app
  if (res.headers.get('X-Optic-V2') === 'closed') { try { window.dispatchEvent(new CustomEvent('optic:v2-closed')); } catch (e) { /* no window in tests */ } }
  let data = null;
  const text = await res.text();
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
  if (!res.ok) {
    const msg = (data && (data.detail || data.error || data.message)) || res.statusText || 'Request failed';
    throw new ApiError(classify(res.status), res.status, typeof msg === 'string' ? msg : 'Request failed', data);
  }
  return data;
}

// cache: path -> { at, data, promise }
const cache = new Map();

/**
 * GET with caching. ttl: how long a response counts as fresh (ms).
 * onUpdate(data): called again if a stale cached copy was returned first and a
 * fresh one arrives later.
 */
export async function get(path, { ttl = 60000, force = false, onUpdate, timeout } = {}) {
  const hit = cache.get(path);
  const now = Date.now();
  if (hit && hit.data !== undefined && !force) {
    if (now - hit.at < ttl) return hit.data;
    // stale: return it now, refresh in the background
    if (!hit.promise) {
      hit.promise = request('GET', path, { timeout }).then((d) => { cache.set(path, { at: Date.now(), data: d }); if (onUpdate) onUpdate(d); return d; })
        .catch(() => { hit.promise = null; });
    }
    return hit.data;
  }
  if (hit && hit.promise && !force) return hit.promise;
  // An answer that says it is still being built is never cached: the next ask goes to the server.
  const p = request('GET', path, { timeout }).then((d) => { if (d && d.building) cache.delete(path); else cache.set(path, { at: Date.now(), data: d }); return d; })
    .catch((e) => { cache.delete(path); throw e; });
  cache.set(path, { at: 0, data: undefined, promise: p });
  return p;
}

export const post = (path, body, opts) => request('POST', path, { ...opts, body });
export const put = (path, body, opts) => request('PUT', path, { ...opts, body });
export const patch = (path, body, opts) => request('PATCH', path, { ...opts, body });
export const del = (path, opts) => request('DELETE', path, opts);

export function invalidate(prefix) {
  [...cache.keys()].forEach((k) => { if (k.startsWith(prefix)) cache.delete(k); });
}

/** Run requests in parallel; each settles to {ok, data} or {ok:false, error}. */
export async function settle(map) {
  const keys = Object.keys(map);
  const out = await Promise.all(keys.map((k) => Promise.resolve(map[k]).then((data) => ({ ok: true, data }), (error) => ({ ok: false, error }))));
  return Object.fromEntries(keys.map((k, i) => [k, out[i]]));
}

/** A readable sentence for an ApiError, for state cards. */
export function explain(err, what = 'This') {
  if (!err) return '';
  switch (err.kind) {
    case 'offline': return `${what} needs a connection. Optic will try again when you are back online.`;
    case 'timeout': return `${what} took too long to load. The data provider may be slow right now.`;
    case 'auth': return `Sign in to see ${what.toLowerCase()}.`;
    case 'forbidden': return `${what} is not available on this account.`;
    case 'notfound': return `${what} was not found.`;
    case 'limit': return 'Too many requests in a short time. Wait a moment and try again.';
    default: return `${what} did not load. ${err.message && err.message !== 'Request failed' ? err.message + '.' : 'The server answered with an error.'}`;
  }
}

/** Pull an "as of" from any payload shape the backend uses. */
export function asOf(d) {
  if (!d || typeof d !== 'object') return null;
  const f = d.freshness || {};
  return {
    at: d.generated_at || d.as_of || f.market_time || null,
    text: f.text || null,
    label: f.session_label || (d.session && d.session.label) || null,
    degraded: !!d.degraded,
    source: d.data_source || null,
    caveat: d.data_caveat || null,
  };
}
