// Alerts: what fired for the reader, the watches that decide it, and Optic's
// own scheduled-scan ledger. Signed in, watches live on the account and the
// server checks them every 30 minutes; signed out, they live in this browser
// (the classic key) and are checked only while the page is open, which the
// page says.
import { $, html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { clean, ago, num } from '../core/format.js';
import { skeleton, empty, failed } from '../ui/states.js';
import { toast } from '../ui/toast.js';
import { provideContext } from '../ui/milo.js';
import { groupTabs } from './tabs.js';

const LOCAL_KEY = 'optic.watches.v1';
let S = {};
let live = true;

function localDefs() {
  if (!holds(store.state.user)) return [];
  try { const r = JSON.parse(localStorage.getItem(LOCAL_KEY) || '[]'); return Array.isArray(r) ? r : []; } catch (e) { return []; }
}
function saveLocal(list) {
  if (!holds(store.state.user)) return;
  try { localStorage.setItem(LOCAL_KEY, JSON.stringify(list.slice(0, 40))); } catch (e) { /* quota */ }
}

const kindLabel = (k) => ((S.catalogue || []).find((c) => c.id === k) || {}).label || k;
function paramText(w) {
  const c = (S.catalogue || []).find((x) => x.id === w.kind);
  const p = c && c.param; if (!p) return '';
  const v = (w.params || {})[p.key];
  if (v === undefined || v === null || v === '') return '';
  if (p.choices) return ((p.choices.find((x) => x.value === v) || {}).label || v);
  return p.kind === 'percent' ? `${num(v, 1)}%` : p.kind === 'price' ? `$${num(v)}` : p.kind === 'days' ? `${v} days` : String(v);
}

function hitsBlock() {
  if (!store.signedIn()) {
    return html`<div class="state"><p class="t-h3">Alerts that wait for you need an account</p><p>Signed in, Optic checks your watches every 30 minutes and keeps what fired here, even while you are away. Signed out, watches are checked only while this page is open.</p><a class="btn btn-primary" href="#/signin">Sign in or create an account</a></div>`;
  }
  if (S.hitsErr) return failed('What fired', S.hitsErr, { retry: 'hits' });
  if (!S.hits) return skeleton('rows', 2);
  if (!S.hits.length) return empty('Nothing has fired yet', 'When a watch is met, it is recorded here with the number that met it.');
  return html`<ul class="hit-list">${S.hits.map((h) => html`<li class="${h.seen ? '' : 'is-new'}"><a href="#/${h.symbol}"><b class="tick">${h.symbol}</b> ${clean(h.title)}</a><p>${clean(h.body || '')}</p><small class="t-muted">${ago(h.created_at)}${h.seen ? '' : ', new'}</small></li>`)}</ul>
    ${S.hits.some((h) => !h.seen) ? html`<button type="button" class="btn btn-sm" data-v2-hits-seen>Mark all as seen</button>` : ''}`;
}

function builder() {
  const cat = S.catalogue || [];
  const c = cat.find((x) => x.id === S.kind) || cat[0];
  if (!c) return S.catErr ? failed('The list of conditions', S.catErr, { retry: 'catalogue' }) : skeleton('lines', 2);
  const p = c.param;
  return html`<form class="watch-form" data-v2-watch-form>
    <label class="field"><span class="sr">Symbol</span><input name="symbol" value="${S.draftSym || ''}" placeholder="Symbol, such as AAPL" maxlength="12" required autocomplete="off" spellcheck="false"></label>
    <label class="select"><span class="t-label">When</span><select name="kind" data-v2-watch-kind>${cat.map((x) => html`<option value="${x.id}" ${x.id === c.id ? 'selected' : ''}>${x.label}</option>`)}</select></label>
    ${p ? (p.choices ? html`<label class="select"><span class="t-label">${p.label}</span><select name="param">${p.choices.map((ch) => html`<option value="${ch.value}" ${ch.value === p.default ? 'selected' : ''}>${ch.label}</option>`)}</select></label>`
    : html`<label class="field field-sm"><span class="sr">${p.label}</span><input name="param" inputmode="decimal" value="${p.default ?? ''}" placeholder="${p.label}" required></label>`) : ''}
    <button type="submit" class="btn btn-primary">Add watch</button>
    <p class="asof watch-why">${clean(c.why || '')}</p></form>`;
}

function watchesBlock() {
  if (S.watchErr) return failed('Your watches', S.watchErr, { retry: 'watches' });
  const ws = S.watches;
  if (!ws) return skeleton('rows', 2);
  if (!ws.length) return empty('No watches yet', 'Add one above: a price level, a move, a signal change or an earnings date.');
  const bySym = {};
  ws.forEach((w) => { (bySym[w.symbol] = bySym[w.symbol] || []).push(w); });
  return html`${Object.entries(bySym).map(([sym, list]) => {
    const ck = (S.checks || {})[sym];
    return html`<div class="watch-group"><div class="watch-sym"><a href="#/${sym}" class="tick">${sym}</a>
      <button type="button" class="btn btn-sm" data-v2-check="${sym}" ${ck && ck.loading ? 'disabled' : ''}>${ck && ck.loading ? 'Checking…' : 'Check now'}</button>
      ${ck && ck.at ? html`<span class="asof">Checked ${ago(ck.at)}${ck.price ? `, price ${num(ck.price)}` : ''}</span>` : ''}</div>
      <ul class="watch-list">${list.map((w) => {
        const res = ck && ck.results ? ck.results.find((r) => r.id === w.id) : null;
        return html`<li><span class="w-what">${kindLabel(w.kind)} ${paramText(w)}</span>
          <span class="w-state">${res ? html`<b class="${res.met ? 'up' : ''}">${res.met ? 'Met' : 'Not met'}</b> ${clean(res.evidence || res.text || res.detail || '')}` : w.last_met_at ? html`Last met ${ago(w.last_met_at)}` : html`<span class="t-muted">Not met yet</span>`}</span>
          <label class="switch"><input type="checkbox" data-v2-watch-active="${w.id}" ${w.active !== false ? 'checked' : ''}><span>On</span></label>
          <button type="button" class="textlink" data-v2-watch-del="${w.id}" aria-label="Delete the watch ${kindLabel(w.kind)} ${paramText(w)} on ${sym}">Delete</button></li>`;
      })}</ul></div>`;
  })}`;
}

function ledger() {
  if (S.alertsErr) return failed('The scan ledger', S.alertsErr, { retry: 'alerts' });
  if (!S.alerts) return skeleton('rows', 3);
  const a = S.alerts.alerts || [];
  if (!a.length) return empty('Nothing has fired from the scheduled scan', 'Optic\'s own scans record setups, signal changes and unusual activity here when they find them.');
  return html`<ul class="hit-list">${a.slice(0, 20).map((x) => html`<li><a href="#/${x.ticker || ''}"><b class="tick">${x.ticker || ''}</b> ${clean(x.title)}</a><p>${clean(x.body || '')}</p><small class="t-muted">${clean(x.kind || '')}, ${ago(x.created_at)}</small></li>`)}</ul>
    <p class="asof">The same for everyone using this deployment. Marking read and clearing are for the owner, in the current app.</p>`;
}

function paint(main) {
  draw($('#al-body', main), html`
    <section class="section first" aria-labelledby="h-hits"><div class="section-head"><h2 class="t-h2" id="h-hits">What fired while you were away</h2></div>${hitsBlock()}</section>
    <section class="section" aria-labelledby="h-w"><div class="section-head"><div><h2 class="t-h2" id="h-w">Your watches</h2><p class="section-sub">${store.signedIn() ? 'On your account. Checked every 30 minutes.' : 'In this browser. Checked only while this page is open, when you press Check now.'}</p></div></div>
      ${builder()}${watchesBlock()}</section>
    <section class="section" aria-labelledby="h-l"><div class="section-head"><h2 class="t-h2" id="h-l">From the scheduled scan</h2></div>${ledger()}</section>`);
}

async function loadAll(main) {
  const signed = store.signedIn();
  const jobs = [
    api.get('/api/watches/catalogue', { ttl: 3600000 }).then((r) => { S.catalogue = r.conditions || []; S.kind = S.kind || (S.catalogue[0] || {}).id; }, (e) => { S.catErr = e; }),
    api.get('/api/alerts?limit=40', { ttl: 60000 }).then((r) => { S.alerts = r; }, (e) => { S.alertsErr = e; }),
  ];
  if (signed) {
    jobs.push(api.get('/api/watches', { ttl: 0, force: true }).then((r) => { S.watches = r.watches || []; }, (e) => { S.watchErr = e; }));
    jobs.push(api.get('/api/watches/hits?limit=30', { ttl: 0, force: true }).then((r) => { S.hits = r.hits || []; }, (e) => { S.hitsErr = e; }));
  } else S.watches = localDefs();
  await Promise.all(jobs.map((j) => j.finally(() => { if (live) paint(main); })));
}

export async function render(main, route) {
  live = true;
  S = { checks: {}, draftSym: (route.params || {}).symbol || '' };
  provideContext(() => ({ view: 'alerts' }));
  document.title = 'Alerts, Optic';
  draw(main, html`<header class="page-head"><h1 class="t-display-m">Alerts</h1>${groupTabs('follow', 'alerts')}</header><div id="al-body"></div>`);
  paint(main);
  wire(main);
  await loadAll(main);
  if (S.draftSym) { const i = $('[data-v2-watch-form] input[name=symbol]', main); if (i) i.focus(); }
}
export function dispose() { live = false; }
export const retry = {
  hits: (m) => { S.hitsErr = null; loadAll(m); }, catalogue: (m) => { S.catErr = null; loadAll(m); },
  watches: (m) => { S.watchErr = null; loadAll(m); }, alerts: (m) => { S.alertsErr = null; loadAll(m); },
};

function wire(main) {
  main.addEventListener('change', async (e) => {
    if (e.target.matches('[data-v2-watch-kind]')) {
      const f = e.target.form; S.draftSym = f.symbol.value; S.kind = e.target.value; paint(main);
      const k = $('[data-v2-watch-kind]', main); if (k) k.focus();
      return;
    }
    const act = e.target.closest('[data-v2-watch-active]');
    if (act) {
      const id = act.dataset.v2WatchActive, on = act.checked;
      const w = S.watches.find((x) => String(x.id) === id); if (!w) return;
      w.active = on;
      if (store.signedIn()) {
        try { await api.patch(`/api/watches/${encodeURIComponent(id)}`, { active: on }); }
        catch (err) { w.active = !on; act.checked = !on; toast(api.explain(err, 'The change'), { kind: 'bad' }); }
      } else saveLocal(S.watches);
    }
  });
  main.addEventListener('submit', async (e) => {
    const f = e.target.closest('[data-v2-watch-form]');
    if (!f) return;
    e.preventDefault();
    const sym = String(f.symbol.value || '').trim().toUpperCase();
    const kind = f.kind.value;
    const c = (S.catalogue || []).find((x) => x.id === kind);
    if (!/^[A-Z0-9.^=-]{1,12}$/.test(sym)) { toast('Enter a ticker, such as AAPL.'); return; }
    const params = {};
    if (c && c.param) {
      const raw = f.param ? f.param.value : c.param.default;
      if (c.param.choices) params[c.param.key] = raw;
      else {
        const n = Number(String(raw).replace(/[$,%\s]/g, ''));
        if (!Number.isFinite(n) || n <= 0) { toast(`${c.param.label} needs a positive number.`); return; }
        params[c.param.key] = n;
      }
    }
    try {
      if (store.signedIn()) {
        const r = await api.post('/api/watches', { symbol: sym, kind, params });
        S.watches = [...S.watches, r.watch];
      } else {
        const defs = localDefs();
        const key = JSON.stringify({ symbol: sym, kind, params });
        if (defs.some((d) => JSON.stringify({ symbol: d.symbol, kind: d.kind, params: d.params }) === key)) { toast(`You are already watching that on ${sym}.`); return; }
        if (defs.length >= 40) { toast('That is 40 watches, which is the limit. Delete one to add another.'); return; }
        const def = { id: 'local-' + Math.random().toString(36).slice(2, 11), symbol: sym, kind, params, active: true, created_at: new Date().toISOString(), last_met_at: null, last_evidence: null };
        saveLocal([...defs, def]); S.watches = localDefs();
      }
      S.draftSym = '';
      toast(`Watching ${sym}: ${kindLabel(kind)} ${paramText({ kind, params })}.`);
      paint(main);
    } catch (err) { toast(err.message && err.kind !== 'server' ? err.message : api.explain(err, 'The watch'), { kind: 'bad' }); }
  });
  main.addEventListener('click', async (e) => {
    const del = e.target.closest('[data-v2-watch-del]');
    if (del) {
      const id = del.dataset.v2WatchDel; const w = S.watches.find((x) => String(x.id) === id);
      try {
        if (store.signedIn()) await api.del(`/api/watches/${encodeURIComponent(id)}`);
        else saveLocal(localDefs().filter((x) => String(x.id) !== id));
        S.watches = S.watches.filter((x) => String(x.id) !== id);
        toast(`Deleted the watch on ${w ? w.symbol : 'that symbol'}.`); paint(main);
      } catch (err) { toast(api.explain(err, 'The delete'), { kind: 'bad' }); }
      return;
    }
    const ck = e.target.closest('[data-v2-check]');
    if (ck) {
      const sym = ck.dataset.v2Check;
      const defs = S.watches.filter((w) => w.symbol === sym && w.active !== false);
      if (!defs.length) { toast(`No watch on ${sym} is switched on.`); return; }
      S.checks[sym] = { loading: true }; paint(main);
      try {
        const r = await api.post('/api/watches/check', { ticker: sym, watches: defs.map((w) => ({ id: w.id, kind: w.kind, params: w.params })) }, { timeout: 60000 });
        S.checks[sym] = { at: r.checked_at || new Date().toISOString(), results: r.results || [], price: r.price };
        if (!store.signedIn()) {
          const met = new Set((r.results || []).filter((x) => x.met).map((x) => x.id));
          if (met.size) { saveLocal(localDefs().map((d) => (met.has(d.id) ? Object.assign(d, { last_met_at: new Date().toISOString() }) : d))); S.watches = localDefs(); }
        }
      } catch (err) { S.checks[sym] = null; toast(api.explain(err, 'The check'), { kind: 'bad' }); }
      paint(main);
      const again = $(`[data-v2-check="${sym}"]`, main); if (again) again.focus();
      return;
    }
    if (e.target.closest('[data-v2-hits-seen]')) {
      try { await api.post('/api/watches/hits/seen', {}); S.hits = S.hits.map((h) => Object.assign(h, { seen: true })); paint(main); }
      catch (err) { toast(api.explain(err, 'That'), { kind: 'bad' }); }
    }
  });
}
