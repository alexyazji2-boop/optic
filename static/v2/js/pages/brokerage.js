// Brokerage: the reader's own linked accounts, read-only. Before a link it is
// sign-in, plan and consent; after, five sections at their own addresses
// (#/brokerage/<section>): Overview, Holdings & Exposure, Performance,
// Events & Research and Connections. Every figure says which kind
// it is: broker-reported, market data, or Optic's calculation.
//
// Against the same /api/brokerage routes as static/brokerage.js. What can cost
// money: "Write it up" (one Milo message, labelled), "Sync now" (a provider
// refresh, limited per plan per day), Connect (creates a provider connection)
// and the billing buttons (Stripe). Nothing here can trade; the server has no
// route that could.
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { num, clean, capFirst, ago, isNum, billingOff } from '../core/format.js';
import * as RP from '../core/reports.js';
import { stamp } from '../core/prefs.js';
import { skeleton } from '../ui/states.js';
import { lineChart, mountCharts } from '../ui/chart.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { scenariosSection } from '../ui/scenarios.js';

export const SECTIONS = [
  { id: 'overview', label: 'Overview', ask: 'What deserves my attention in my linked portfolio this week?' },
  { id: 'holdings', label: 'Holdings & Exposure', ask: 'Where am I concentrated, counting what my ETFs hold?' },
  { id: 'performance', label: 'Performance', ask: 'How has my portfolio done against the S&P 500, and how much of the change was my own deposits and withdrawals?' },
  { id: 'events', label: 'Events & Research', ask: 'Which earnings and events affect me in the next two weeks?' },
  { id: 'connections', label: 'Connections', ask: 'What can Optic see in my linked accounts, and what can it not?' },
];
const SECTION_KEY = 'optic.brokerage.section.v1', SCOPE_KEY = 'optic.brokerage.scope.v1';
const PERIODS = [['1m', '1M'], ['3m', '3M'], ['ytd', 'YTD'], ['1y', '1Y'], ['all', 'All']];
const BENCHMARKS = [['SPY', 'S&P 500 (SPY)'], ['VTI', 'US total market (VTI)'], ['QQQ', 'Nasdaq 100 (QQQ)'], ['ACWI', 'World stocks (ACWI)'], ['AGG', 'US bonds (AGG)']];
const ENDPOINT = { overview: 'overview', holdings: 'holdings', performance: 'performance', events: 'events' };
const ASKS = ['Where is my portfolio concentrated?', 'Which upcoming earnings affect my holdings?', 'Explain my exposure in plain English.', 'What changed since my last sync?', 'Why did my portfolio move today?', 'What risks deserve more research?'];
const FLASH = {
  linked: ['good', 'Connected. Your accounts are synced below.'], abandoned: ['', 'Connection cancelled. Nothing was linked.'],
  expired: ['bad', 'That connection link expired or belonged to another sign-in. Start again with Connect.'],
  unsupported: ['bad', 'That broker or account type is not supported by the provider yet. Nothing was linked.'],
  error: ['bad', 'The provider could not finish the connection. Nothing was linked; try again in a few minutes.'],
  limit: ['bad', 'That connection would go over your plan\'s limit, so it was removed straight away.'],
  notreadonly: ['bad', 'That connection allowed trading, so Optic removed it. Connect again and choose read-only access.'],
  nothing: ['', 'No new connection came back from the provider. If you finished signing in, wait a minute and press Connect again.'],
};
const STATUS = { active: ['on', 'Connected'], partial: ['warn', 'Partial sync'], pending: ['warn', 'First sync running'], expired: ['off', 'Needs reconnecting'], outage: ['warn', 'Provider not responding'], error: ['off', 'Sync failed'], unsupported: ['off', 'Not supported'], paused: ['off', 'Paused: plan ended'], closed: ['off', 'Closed'] };
const THESIS_FIELDS = [['why', 'bull', 'Why I own it'], ['horizon', 'horizon', 'Horizon'], ['assumptions', 'assumptions', 'What I am assuming'], ['reassess_if', 'invalidation', 'What would make me reassess'], ['risks', 'bear', 'Risks I accept'], ['catalysts', 'catalysts', 'What I am watching for']];
const SAFE = (url) => typeof url === 'string' && (url.startsWith('/api/brokerage/sandbox/') || /^https:\/\/([a-z0-9-]+\.)*(snaptrade\.com|stripe\.com)\//i.test(url));

/* ---------------- formatting (the classic bk* helpers) ---------------- */
export function money(v, ccy = 'USD') {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return 'Not supplied';
  const code = String(ccy || 'USD').toUpperCase();
  try { return Number(v).toLocaleString('en-US', { style: 'currency', currency: code, minimumFractionDigits: 2, maximumFractionDigits: 2 }).replace(/^-/, '−'); } catch (e) { return `${Number(v).toFixed(2)} ${code}`; }
}
const signedMoney = (v, ccy) => (v === null || v === undefined ? 'Not supplied' : html`<span class="${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${v > 0 ? '+' : ''}${money(v, ccy)}</span>`);
export const qty = (v) => (v === null || v === undefined ? 'Not supplied' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 4 }));
export const pct = (v, d = 1, signed = false) => (v === null || v === undefined || !Number.isFinite(Number(v)) ? 'n/a' : `${signed && Number(v) > 0 ? '+' : ''}${Number(v).toFixed(d)}%`.replace(/^-/, '−'));
const sPct = (v, d = 2) => (v === null || v === undefined || !Number.isFinite(Number(v)) ? html`<span class="t-muted">n/a</span>` : html`<span class="${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${pct(v, d, true)}</span>`);
const day = (iso) => { if (!iso) return 'n/a'; const d = new Date(String(iso).length === 10 ? `${iso}T12:00:00` : iso); return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }); };
const when = (iso) => (!iso ? 'never' : `${ago(iso)} (${new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })})`);
const SRC = { broker: 'Broker-reported', market: 'Market data', optic: 'Optic calculation' };
const src = (k) => html`<span class="bk-src bk-src-${k}">${SRC[k]}</span>`;
const limits = (list, open) => ((list || []).filter(Boolean).length ? html`<details class="more-inline bk-limits" ${open ? 'open' : ''}><summary>What this cannot tell you</summary><ul class="plain">${list.filter(Boolean).map((l) => html`<li>${clean(l)}</li>`)}</ul></details>` : '');
function bars(rows, max = 8) {
  const shown = (rows || []).filter((r) => r.share_pct !== null && r.share_pct !== undefined && r.value > 0).slice(0, max);
  if (!shown.length) return html`<p class="t-muted">Nothing to show.</p>`;
  return html`<ul class="bk-bars">${shown.map((r) => html`<li><span class="bk-bar-l">${r.label}</span><span class="bk-bar-t" aria-hidden="true"><span class="bk-bar-f" style="width:${Math.max(1, Math.min(100, r.share_pct))}%"></span></span><span class="bk-bar-v">${Number(r.share_pct).toFixed(1)}%</span></li>`)}</ul>`;
}
const shareRows = (rows) => (rows || []).map((r) => ({ label: r.label || r.key || r.name || 'Unclassified', value: Number(r.value_usd || r.value || 0), share_pct: r.share_pct === undefined ? r.weight_pct : r.share_pct }));
const tag = (tone, text) => html`<span class="set-tag ${tone === 'on' ? 'on' : tone === 'warn' ? 'warn' : 'off'}">${text}</span>`;

/* ---------------- state ---------------- */
let S = { status: null }, live = true, mainEl = null, refreshT = null, appRef = null;
const W = { data: {}, key: {}, extra: {}, loading: {}, error: {}, scopeKey: null, period: '1y', bench: 'SPY', sectors: 'look',
  thesisEdit: null, thesisArmed: null, alertDraft: null };
const stored = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } };
const keep = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } };
const accounts = () => { const out = []; ((S.status || {}).connections || []).forEach((c) => (c.accounts || []).forEach((a) => out.push({ institution: c.institution, ...a }))); return out; };
const scopeIds = () => { const ids = stored(SCOPE_KEY, []), own = new Set(accounts().map((a) => a.id)); return Array.isArray(ids) ? ids.filter((i) => own.has(i)) : []; };
const query = (extra = {}) => { const q = new URLSearchParams(extra); const ids = scopeIds(); if (ids.length) q.set('accounts', ids.join(',')); const s = q.toString(); return s ? `?${s}` : ''; };
const wantKey = (sec) => `${scopeIds().join(',')}|${sec === 'performance' ? `${W.period}:${W.bench}` : ''}`;
const linked = () => ((S.status || {}).connections || []).length > 0;

/* ---------------- before a link ---------------- */
function permissions(st, open) {
  return html`<details class="section bk-perms" ${open ? 'open' : ''}><summary><h2 class="t-h2">What Optic can and cannot see</h2></summary>
    <ul class="plain">${(st.permissions || []).map((t) => html`<li>${t}</li>`)}</ul>
    ${st.provider ? html`<p class="asof">Provider: ${st.provider}${st.mode === 'sandbox' ? ' (sandbox: test data only)' : ''}.</p>` : ''}</details>`;
}
function upgrade(ent) {
  const b = S.billing || {}, paid = (S.status || {}).paid_limits || {};
  if (b.available === false) return html`<section class="section first"><h2 class="t-h2">Link your brokerage</h2><p>Linking is part of the paid plan. ${billingOff(b.reason, !!(store.state.me && store.state.me.admin))}</p></section>`;
  const syncs = paid.brokerage_manual_syncs_per_day || 1;
  return html`<section class="section first"><h2 class="t-h2">Link your brokerage with Pro</h2>
    <p>Connect up to ${paid.brokerage_connections || 3} brokerages read-only, see every account in one portfolio, and ask Milo about your actual holdings: concentration, upcoming earnings, what changed since the last sync.</p>
    <ul class="plain"><li>Read-only through SnapTrade's hosted sign-in. Optic never sees your brokerage password.</li><li>Daily sync, plus ${syncs} manual sync${syncs === 1 ? '' : 's'} a day.</li><li>Up to ${paid.ai_calls_per_day || 15} Milo messages a day and ${paid.ai_calls_per_month || 100} in any 30 days.</li></ul>
    <div class="cluster"><button type="button" class="btn btn-primary" data-v2-bill="checkout">Upgrade${b.price_label ? ` for ${b.price_label}` : ''}</button><span class="t-muted">You are on ${ent.plan_label || 'Free'}. Cancel any time from Settings.</span></div></section>`;
}
function consent(c) {
  if (c.accepted) return html`<p class="asof" title="${c.version ? `Terms version ${c.version}` : ''}">You agreed to the linking terms on ${new Date(c.accepted_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}.</p>`;
  const link = (url, text) => html`<a href="${url}" target="_blank" rel="noopener">${text}</a>`;
  const optic = [c.terms_url && link(c.terms_url, 'Terms'), c.privacy_url && link(c.privacy_url, 'Privacy Policy')].filter(Boolean);
  const docs = [optic.length ? html`Optic's ${optic.length === 2 ? html`${optic[0]} and ${optic[1]}` : optic[0]}` : '', c.provider_terms_url ? html`SnapTrade's ${link(c.provider_terms_url, 'End User Terms')}` : ''].filter(Boolean);
  const st = S.status || {}, unpub = [!c.terms_url && 'Terms', !c.privacy_url && 'Privacy Policy'].filter(Boolean);
  const note = st.mode === 'sandbox' && (unpub.length || !c.provider_terms_url) ? ' (Sandbox: the documents are not published yet.)' : st.owner_only && unpub.length ? ` (Owner only: Optic's ${unpub.join(' and ')} ${unpub[0] === 'Terms' ? 'are' : 'is'} not published yet.)` : '';
  return html`<label class="check bk-consent"><input type="checkbox" data-v2-bk-consent ${S.agreed ? 'checked' : ''}> <span>${docs.length ? html`I agree to ${docs.length === 2 ? html`${docs[0]} and to ${docs[1]}` : docs[0]}. ` : ''}I understand Optic gets read-only access and that holdings I ask Milo about are sent to Anthropic to answer.<i>${note}</i></span></label>`;
}
function acctState(a) {
  const s = a.sync_state;
  if (s === 'ok') return a.broker_as_of ? `Broker data as of ${new Date(a.broker_as_of).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}` : 'Synced';
  if (s === 'partial') return a.sync_note || 'Partial: some data did not arrive';
  if (s === 'stale') return 'Provider did not respond; showing the last good data';
  if (s === 'failed') return 'Last sync failed; showing the last good data';
  if (s === 'missing') return 'No longer reported by the broker; left out';
  if (s === 'pending') return a.sync_note || 'Waiting for first data';
  return '';
}
function connCard(c) {
  const [tone, label] = STATUS[c.status] || ['off', capFirst(c.status || 'unknown')];
  const ent = (S.status || {}).entitlement || {}, armed = S.armed === c.id;
  const reconnect = ['expired', 'closed', 'error'].includes(c.status) && ent.can_link, canSync = ent.can_link && !['expired', 'closed', 'paused', 'unsupported'].includes(c.status);
  return html`<div class="bk-conn"><div class="split"><p><b>${c.institution || 'Brokerage'}</b> ${tag(tone, label)}</p>
      <div class="cluster">${canSync ? html`<button type="button" class="btn btn-sm" data-v2-bk-sync="${c.id}" ${S.syncing === c.id ? 'disabled' : ''}>${S.syncing === c.id ? 'Syncing...' : 'Sync now'}</button>` : ''}
        ${reconnect ? html`<button type="button" class="btn btn-sm btn-primary" data-v2-bk-reconnect="${c.id}">Reconnect</button>` : ''}
        ${armed ? html`<button type="button" class="btn btn-sm btn-danger" data-v2-bk-disconnect="${c.id}" data-v2-confirm="1">Disconnect and delete</button><button type="button" class="btn btn-sm" data-v2-bk-disarm>Keep</button>` : html`<button type="button" class="btn btn-sm" data-v2-bk-disconnect="${c.id}">Disconnect</button>`}</div></div>
    <p class="asof">Last successful sync: ${when(c.last_sync_at)}${c.status_reason ? `. ${c.status_reason}` : ''}${armed ? '. Disconnecting removes it at the provider and deletes Optic\'s copy of its data now.' : ''}</p>
    <ul class="bk-accts">${(c.accounts || []).map((a) => (S.renaming === a.id ? html`<li class="bk-renaming"><label class="field field-sm"><span class="sr">Name for ${a.broker_name || a.name || 'Account'} ${a.number_mask || ''}</span><input maxlength="40" value="${a.nickname || ''}" placeholder="${a.broker_name || a.name || 'Account'}" autocomplete="off" data-v2-bk-rename-input="${a.id}"></label>
        <span class="cluster"><button type="button" class="btn btn-sm btn-primary" data-v2-bk-rename-save="${a.id}">Save</button><button type="button" class="btn btn-sm" data-v2-bk-rename-cancel>Cancel</button></span>
        <p class="asof">${a.number_mask || ''}${a.account_type ? `, ${a.account_type}` : ''}. Leave it blank to use the broker's name, ${a.broker_name || a.name || 'Account'}.</p></li>`
      : html`<li><label class="check"><input type="checkbox" data-v2-bk-select="${a.id}" ${a.selected ? 'checked' : ''}> <span><b>${a.name || 'Account'}</b> ${a.number_mask || ''}${a.account_type ? `, ${a.account_type}` : ''}${a.currency ? `, ${a.currency}` : ''}</span></label>
        <span class="bk-acct-side"><span class="t-muted">${acctState(a)}</span><button type="button" class="btn btn-sm" data-v2-bk-rename="${a.id}" aria-label="Rename ${a.name || 'Account'} ${a.number_mask || ''}">Rename</button></span></li>`))}</ul></div>`;
}
function connections() {
  const st = S.status || {}, ent = st.entitlement || {}, conns = st.connections || [], active = conns.filter((c) => c.status !== 'disconnected');
  const canAdd = ent.can_link && active.length < (ent.max_connections || 0), needAgree = st.consent && !st.consent.accepted && !S.agreed;
  return html`${st.paused_at ? html`<section class="section"><h2 class="t-h2">Syncing is paused</h2><p>Your paid plan ended, so these accounts stopped updating on ${new Date(st.paused_at).toLocaleDateString()}. What you see is the last sync. ${st.provider_closed_at ? 'The connection has been closed at the provider; reconnect after upgrading to resume.' : 'Resubscribe within 7 days to resume where you left off. After 7 days the connection is closed at the provider, and after 30 days Optic deletes its copy.'} You can disconnect or delete everything now on any plan.</p><button type="button" class="btn" data-v2-bill="checkout">Resume with Pro</button></section>` : ''}
    <section class="section ${linked() ? '' : 'first'}" aria-labelledby="bc-h"><div class="section-head"><h2 class="t-h2" id="bc-h">Connections</h2>${canAdd ? html`<button type="button" class="btn btn-primary" data-v2-bk-connect ${needAgree ? 'disabled aria-disabled="true"' : ''}>Connect a brokerage</button>` : ''}</div>
      ${ent.can_link && canAdd ? consent(st.consent || {}) : ''}
      <p class="section-sub">${ent.can_link ? `Your plan links up to ${ent.max_connections} connection${ent.max_connections === 1 ? '' : 's'} and ${ent.max_accounts} accounts. Accounts sync on their own once a day; Sync now is limited to ${ent.manual_syncs_per_day} a day.` : 'Linking and syncing are part of the paid plan. Your stored data stays until you delete it or the retention period ends.'}</p>
      ${conns.length ? conns.map(connCard) : html`<p class="quiet">Nothing linked yet. Connect a brokerage to see your holdings here.</p>`}
      ${conns.length ? '' : html`<p class="asof">After you finish at the provider, it returns you to Brokerage in the classic app.</p>`}</section>
    ${permissions(st, !conns.length)}
    ${conns.length ? html`<section class="section set-danger" aria-labelledby="bd-h"><h2 class="t-h2" id="bd-h">Delete all brokerage data</h2><p>Disconnects every brokerage at the provider and deletes everything Optic stored about them, including the encryption key, so backups cannot be read either. Your Optic account stays.</p>
      ${S.armed === 'all' ? html`<div class="cluster"><button type="button" class="btn btn-danger" data-v2-bk-delete="confirm">Yes, delete all brokerage data</button><button type="button" class="btn" data-v2-bk-disarm>Keep it</button></div>` : html`<button type="button" class="btn btn-danger" data-v2-bk-delete>Delete all brokerage data</button>`}</section>` : ''}`;
}

/* ---------------- workspace frame ---------------- */
// the newest price may be a pre-market or after-hours print (the server picks the latest; owner, 2026-10-20)
const EXT_QUOTES = { pre: 'Pre-market quotes', post: 'After-hours quotes' }, EXT_WORD = { pre: 'pre-market ', post: 'after-hours ' };
function freshness() {
  const o = W.data.overview || W.data.holdings || {}, f = o.freshness || {}, b = f.broker || {}, m = f.market || {};
  const out = [];
  if (b.oldest_broker_as_of) out.push(html`<span class="pill">Broker data as of ${day(b.oldest_broker_as_of)} ${new Date(b.oldest_broker_as_of).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}</span>`);
  else if (b.newest_sync) out.push(html`<span class="pill">Synced ${ago(b.newest_sync)}</span>`);
  if (m.quotes_newest) out.push(html`<span class="pill">${EXT_QUOTES[m.extended] || 'Quotes'} ${ago(m.quotes_newest)}${m.delayed_minutes ? ` (delayed ${Math.round(m.delayed_minutes)} min)` : ''}</span>`);
  return out;
}
function frame(sec) {
  const def = SECTIONS.find((s) => s.id === sec) || SECTIONS[0], accts = accounts(), ids = scopeIds();
  return html`<div class="bk-head"><label class="select"><span class="t-label">Accounts</span><select data-v2-bk-scope><option value="" ${ids.length ? '' : 'selected'}>All counted accounts (${accts.filter((a) => a.selected).length})</option>${accts.map((a) => html`<option value="${a.id}" ${ids.length === 1 && ids[0] === a.id ? 'selected' : ''}>${a.name || 'Account'} ${a.number_mask || ''}${a.selected ? '' : ' (not counted)'}</option>`)}</select></label>
      <div class="bk-fresh">${freshness()}</div>${miloButton('Ask Milo', { ask: def.ask, context: `Brokerage: ${def.label}` })}</div>
    <div class="bk-tabs" role="tablist" aria-label="Brokerage sections">${SECTIONS.map((s) => html`<button type="button" role="tab" id="bkt-${s.id}" aria-selected="${s.id === sec}" aria-controls="bk-panel" tabindex="${s.id === sec ? '0' : '-1'}" data-v2-bk-tab="${s.id}">${s.label}</button>`)}</div>
    <div id="bk-panel" role="tabpanel" aria-labelledby="bkt-${sec}" tabindex="-1">${safe(sec)}</div>`;
}
function safe(sec) {
  try { return sectionHTML(sec); } catch (e) { console.error('brokerage section', sec, e); return html`<p class="stale">This section could not be drawn. Reload the page; if it persists, report it from Settings, Report a problem.</p>`; }
}
function sectionHTML(sec) {
  if (sec === 'connections') return connections();
  if (W.error[sec]) return html`<div class="state err" role="alert"><p class="t-h3">${(SECTIONS.find((s) => s.id === sec) || {}).label} did not load</p><p>${W.error[sec]}</p><button type="button" class="btn btn-sm" data-v2-bk-retry>Try again</button></div>`;
  const d = W.data[sec];
  if (!d) return skeleton('rows', 5, `Loading ${(SECTIONS.find((s) => s.id === sec) || {}).label}`);
  if (sec === 'overview') return overview(d);
  if (sec === 'holdings') return holdings(d);
  if (sec === 'performance') return performance(d);
  if (sec === 'events') return events(d);
  return '';
}

/* ---------------- overview ---------------- */
const tile = (k, v, n) => html`<div class="bk-tile"><p class="t-label">${k}</p><p class="bk-v">${v}</p><p class="kv-note">${n}</p></div>`;
function overview(d) {
  const tot = d.totals || {}, comb = tot.combined_usd, byc = tot.by_currency || {};
  const totalText = comb ? `${money(comb.value, 'USD')}${comb.approximate ? ' (approx.)' : ''}` : Object.entries(byc).map(([c, b]) => money(b.total, c)).join(' + ') || 'Not supplied';
  const today = d.today || {}, since = d.since_sync || {}, perf = d.performance || {}, pl = perf.unrealized_pl_by_currency || {}, now = d.value_now || {}, bw = ((d.freshness || {}).broker || {}).oldest_broker_as_of;
  const nScope = ((d.scope || {}).scope || []).length;
  return html`<div class="bk-tiles">
      ${now.available ? tile('Value now', money(now.value, 'USD'), html`${src('market')} Your broker's quantities at Optic's delayed ${EXT_WORD[now.extended] || ''}prices, ${ago(now.quotes_newest) || 'just now'}. The broker's own total is ${totalText}${bw ? ` (${ago(bw)})` : ''}${(now.kept_at_broker || []).length ? `; ${now.kept_at_broker.join(', ')} kept at the broker's price` : ''}. Cash and options as last reported.`)
        : tile('Total value', totalText, html`${src('broker')} Securities, options at the broker's last price, and cash.`)}
      ${tile('Today', today.available ? html`${signedMoney(today.total, 'USD')} ${sPct(today.total_pct)}` : html`<span class="t-muted">No quotes</span>`, html`${src('market')} ${today.available ? `Quantity x price change since the previous close${{ pre: ', at pre-market prices', post: ', including after-hours trading' }[((d.freshness || {}).market || {}).extended] || ''}, quotes ${ago(today.quotes_newest)}. Covers ${money(today.covered_value_at_prev_close, 'USD')}.` : 'Optic could not price your holdings just now.'}`)}
      ${tile('Since your last sync', since.available ? (Object.entries(since.value_change_by_currency || {}).map(([c, v]) => signedMoney(v, c)) || '0') : html`<span class="t-muted">After the next sync</span>`, html`${src('optic')} ${since.available ? html`Price effect ${Object.entries(since.price_effect_by_currency || {}).length ? Object.entries(since.price_effect_by_currency).map(([c, v]) => signedMoney(v, c)) : 'none'}; the rest is trades, deposits or new positions.` : clean(since.reason || '')}`)}
      ${tile('Unrealised gain', Object.keys(pl).length ? Object.entries(pl).map(([c, v]) => signedMoney(v, c)) : html`<span class="t-muted">Not supplied</span>`, html`${src('optic')} Market value minus the broker's average cost, on ${isNum(perf.basis_coverage_pct) ? `${perf.basis_coverage_pct}% of value with a cost basis` : 'the holdings the broker gave a cost for'}. Not a return.`)}</div>
    <div class="grid2"><section class="section" aria-labelledby="bo-h"><h2 class="t-h2" id="bo-h">What you own</h2>
        <p class="section-sub">${d.holdings_count || 0} holdings${d.options_count ? ` and ${d.options_count} option position${d.options_count === 1 ? '' : 's'}` : ''} in ${nScope} account${nScope === 1 ? '' : 's'}. Largest, as a share of long value:</p>
        ${bars((d.top_holdings || []).map((h) => ({ label: h.symbol || h.description, value: h.value_usd || h.market_value || 0, share_pct: h.weight_pct })), 5)}
        <h3>By kind</h3>${bars((d.allocation || {}).by_kind || [], 6)}
        <button type="button" class="btn btn-sm" data-v2-bk-go="holdings">Holdings & Exposure</button></section>
      <section class="section" aria-labelledby="ba-h"><h2 class="t-h2" id="ba-h">Deserves attention</h2>
        ${(d.observations || []).length ? html`<ul class="plain">${d.observations.map((o) => html`<li>${clean(o.text)} <small class="t-muted">${o.source || ''}</small> ${o.section && o.section !== 'overview' ? html`<button type="button" class="textlink" data-v2-bk-go="${o.section}">Open</button>` : ''}</li>`)}</ul>` : html`<p class="t-muted">Nothing stands out: no concentration over your thresholds, no reports this week, every account synced.</p>`}
        ${d.alerts_unseen ? html`<p>${d.alerts_unseen} unread alert${d.alerts_unseen === 1 ? '' : 's'}. <button type="button" class="textlink" data-v2-bk-go="events">Read alerts</button></p>` : ''}
        <h3>Coming up</h3>${eventRows((d.upcoming || []).slice(0, 6), true)}</section></div>
    ${briefing()}
    <section class="section" aria-labelledby="bq-h"><h2 class="t-h2" id="bq-h">Ask about your portfolio</h2>
      <div class="chips">${ASKS.map((q) => html`<button type="button" class="chip" data-v2-milo="${q}" data-v2-milo-ctx="Your linked portfolio">${q}</button>`)}</div>
      <p class="asof">Milo reads only your own linked accounts, read-only, and describes rather than advises. Each question uses one Milo message when you send it.</p></section>
    ${limits(d.notes)}`;
}
function briefing() {
  const b = W.extra.briefing;
  if (!b) return html`<section class="section"><h2 class="t-h2">Briefing</h2><p class="t-muted" role="status">Measuring what moved...</p></section>`;
  if (b.error) return html`<section class="section"><h2 class="t-h2">Briefing</h2><p>${b.error}</p></section>`;
  const rows = ((b.today || {}).rows || []).slice(0, 5), w = b.written, earlier = b.written_earlier;
  return html`<section class="section" aria-labelledby="bb-h"><h2 class="t-h2" id="bb-h">Briefing</h2>
    <div class="grid2"><div><h3>Measured: what moved today ${src('market')}</h3>
        ${rows.length ? html`<div class="tscroll"><table class="t"><thead><tr><th scope="col">Holding</th><th scope="col">Today</th><th scope="col">Contribution</th></tr></thead><tbody>${rows.map((r) => html`<tr><td>${r.symbol}</td><td>${sPct(r.change_pct)}</td><td>${signedMoney(r.contribution, 'USD')}</td></tr>`)}</tbody></table></div>` : html`<p class="t-muted">No quotes to measure with just now.</p>`}</div>
      <div><h3>Possibly related: headlines published around the move</h3>
        ${(b.drivers || []).length ? b.drivers.map((x) => html`<div class="bk-driver"><p><b>${x.symbol}</b> ${sPct(x.change_pct)}</p>${(x.headlines || []).length ? html`<ul class="plain">${x.headlines.map((h) => html`<li><a href="${h.url || '#'}" target="_blank" rel="noopener">${h.title || ''}</a> <small class="t-muted">${h.publisher || ''} ${h.published ? ago(h.published) : ''}</small></li>`)}</ul>` : ''}${x.note ? html`<p class="asof">${clean(x.note)}</p>` : ''}</div>`) : html`<p class="t-muted">No large movers to look for headlines about.</p>`}
        <p class="asof">Matched by when they were published. That is not evidence that they caused the move.</p></div></div>
    ${w ? html`<div class="bk-written"><p><b>${w.headline}</b></p>${['what_changed', 'drivers', 'ahead', 'attention'].map((k) => (w[k] ? html`<p>${clean(w[k])}</p>` : ''))}<p class="asof">Written by Milo from the measured figures on this page, ${ago(w.written_at)}.</p></div>`
      : html`<p class="cluster">${earlier ? html`<span class="t-muted">An earlier write-up (${ago(earlier.written_at)}) was from different figures.</span>` : ''}<button type="button" class="btn btn-milo" data-v2-bk-write ${S.writing ? 'disabled' : ''}>${S.writing ? 'Writing...' : 'Write it up'}</button><span class="t-muted">Uses one Milo message. The same figures are kept and not charged again.</span></p>`}</section>`;
}

/* ---------------- holdings & exposure ---------------- */
function holdings(d) {
  const others = [];
  if ((d.cash || []).length || (d.cash_equivalents || []).length) others.push(html`<section class="section"><h2 class="t-h2">Cash</h2>${(d.cash || []).map((c) => html`<p>${c.currency} ${money(c.amount, c.currency)}</p>`)}${(d.cash_equivalents || []).length ? html`<p class="asof">Includes ${d.cash_equivalents.map((c) => c.symbol || c.description).join(', ')}, counted once as cash because your broker's cash balance already includes ${d.cash_equivalents.length === 1 ? 'it' : 'them'}.</p>` : ''}</section>`);
  if ((d.unsupported || []).length) others.push(html`<section class="section"><h2 class="t-h2">Not counted</h2><ul class="plain">${d.unsupported.map((u) => html`<li><b>${u.symbol || u.description}</b> ${u.account || ''}: ${clean(u.reason || '')}</li>`)}</ul></section>`);
  return html`<section class="section first" aria-labelledby="bh-h"><h2 class="t-h2" id="bh-h">Holdings</h2>
      <p class="section-sub">${src('broker')} quantity, price and cost from your broker at its last sync; ${src('market')} Optic's quote beside it; ${src('optic')} weights and unrealised gain.</p>
      <div class="tscroll"><table class="t bk-hold"><thead><tr><th scope="col">Holding</th><th scope="col">Accounts</th><th scope="col">Qty</th><th scope="col">Broker price</th><th scope="col">Quote now</th><th scope="col">Value</th><th scope="col">Weight</th><th scope="col">Cost basis</th><th scope="col">Unrealised</th></tr></thead>
        <tbody>${(d.holdings || []).length ? d.holdings.map((h) => { const q = (d.quotes || {})[String(h.symbol || '').toUpperCase()] || {};
          return html`<tr><td>${h.symbol ? html`<a href="#/${h.symbol}"><b>${h.symbol}</b></a>` : ''} <small class="t-muted">${h.description || ''}${h.sector ? `, ${h.sector}${h.industry ? `, ${h.industry}` : ''}` : ''}</small></td><td>${(h.accounts || []).join(', ')}</td><td>${qty(h.quantity)}</td><td>${money(h.price, h.currency)}</td>
            <td>${isNum(q.price) ? html`${money(q.price, 'USD')} ${sPct(q.change_pct)}` : html`<span class="t-muted">n/a</span>`}</td><td>${money(h.market_value, h.currency)}</td><td>${pct(h.weight_pct)}</td><td>${h.cost_basis === null ? html`<span class="t-muted">Not supplied</span>` : money(h.cost_basis, h.currency)}</td>
            <td>${h.unrealized_pl === null || h.unrealized_pl === undefined ? html`<span class="t-muted">Not supplied</span>` : html`${signedMoney(h.unrealized_pl, h.currency)} ${sPct(h.unrealized_pct, 1)}`}</td></tr>`; }) : html`<tr><td colspan="9">No holdings in these accounts.</td></tr>`}</tbody></table></div>
      ${(d.price_checks || []).length ? html`<p class="asof">The broker's price and Optic's quote differ by 2% or more for ${d.price_checks.map((c) => c.symbol).join(', ')}; the broker's is from its last sync.</p>` : ''}</section>
    ${exposure(d.exposure, d)}${scorecard(W.extra.scorecard)}${(d.options || []).length ? optionsRisk(W.extra.options) : ''}${(d.holdings || []).length || (d.options || []).length ? scenariosSection(W.extra.scenarios, { id: 'bsn-h' }) : ''}
    ${others.length ? html`<div class="grid2">${others}</div>` : ''}${limits(d.notes)}`;
}
function exposure(e, d) {
  if (!e) return '';
  const sec = e.sectors || {}, look = W.sectors === 'look' && (sec.look_through || []).length;
  const comp = e.companies || {}, status = { looked_through: 'looked through', no_source: 'no holdings source', leveraged: 'leveraged or inverse: not looked through' };
  const block = (title, part, note) => { const rows = (part && part.rows) || []; return rows.length ? html`<div><h3>${title}</h3>${bars(shareRows(rows), 8)}<p class="asof">${note || part.basis || ''}</p></div>` : ''; };
  return html`<section class="section" aria-labelledby="be-h"><h2 class="t-h2" id="be-h">Exposure</h2>
    <p class="section-sub">${src('optic')} Where your money sits, counting what your funds hold where Optic has their holdings. Look-through moves fund value onto the companies inside; it never adds to your total.</p>
    ${(comp.flags || []).length ? html`<ul class="plain">${comp.flags.slice(0, 4).map((f) => html`<li>${clean(f)}</li>`)}</ul>` : ''}
    <div class="grid2"><div><div class="split"><h3>Sectors</h3><div class="seg" role="group" aria-label="Sector view"><button type="button" data-v2-bk-sectors="look" aria-pressed="${W.sectors === 'look'}">With look-through</button><button type="button" data-v2-bk-sectors="direct" aria-pressed="${W.sectors === 'direct'}">Direct only</button></div></div>
        ${bars(shareRows(look ? sec.look_through : (sec.direct_only || ((d.allocation || {}).by_sector || []))), 10)}
        <p class="asof">${look ? `Look-through covers ${pct(sec.coverage_pct)} of value${sec.unclassified_value ? `; ${money(sec.unclassified_value, 'USD')} has no sector from Yahoo` : ''}.` : 'Stocks held directly; each fund is one line.'}</p></div>
      <div>${block('Asset class', e.asset_class)}${block('Issuer country', e.issuer_country, 'Where the companies are organised or based, not where they earn their revenue.')}${block('Pricing currency', e.currency, 'The currency each security is priced in, not its underlying economic currency exposure.')}</div></div>
    ${(comp.rows || []).length ? html`<h3>Companies, directly and through funds</h3><div class="tscroll"><table class="t"><thead><tr><th scope="col">Company</th><th scope="col">Direct</th><th scope="col">Through funds</th><th scope="col">Total</th><th scope="col">Share</th></tr></thead>
      <tbody>${comp.rows.slice(0, 12).map((c) => html`<tr><td><b>${c.ticker || ''}</b> <small class="t-muted">${c.name && c.name !== c.ticker ? c.name : ''}</small></td><td>${money(c.direct_usd || 0, 'USD')}</td><td class="bk-left">${(c.via_funds || []).length ? c.via_funds.map((v) => `${v.symbol || ''} ${money(v.value_usd, 'USD')}`).join(', ') : html`<span class="t-muted">none</span>`}</td><td>${money(c.total_usd || 0, 'USD')}</td><td>${pct(c.share_pct)}</td></tr>`)}</tbody></table></div><p class="asof">${clean(comp.no_double_counting || '')}</p>` : ''}
    ${(e.etfs || []).length ? html`<h3>Funds</h3><ul class="plain">${e.etfs.map((f) => html`<li><b>${f.symbol}</b> ${pct(f.share_pct)} of your portfolio: ${f.status === 'looked_through' ? `holdings as of ${day(f.report_date)} from ${f.source || 'SEC Form N-PORT'}, ${pct(f.coverage_pct)} of the fund itemised${f.stale ? ' (an older copy: SEC could not be reached)' : ''}` : clean(f.reason || status[f.status] || 'not looked through')}${f.leveraged || f.inverse ? html` ${tag('warn', 'Leveraged or inverse')}` : ''}</li>`)}</ul>` : ''}
    ${limits(e.limitations)}</section>`;
}
function scorecard(s) {
  if (!s) return html`<section class="section"><h2 class="t-h2">Optic scorecard</h2><p class="t-muted" role="status">Calculating the five assessments...</p></section>`;
  if (s.error) return html`<section class="section"><h2 class="t-h2">Optic scorecard</h2><p>${s.error}</p></section>`;
  const txt = (v) => (typeof v === 'string' ? v : Array.isArray(v) ? v.join(', ') : JSON.stringify(v));
  return html`<section class="section" aria-labelledby="bs-h"><h2 class="t-h2" id="bs-h">Optic scorecard</h2>
    <p class="section-sub">${src('optic')} Five separate assessments of the portfolio as it stands, each with what it is built from and what it could not assess. There is no overall score.</p>
    <div class="bk-scores">${(s.assessments || []).length ? s.assessments.map((a) => { const scored = isNum(a.score);
      const drivers = (a.drivers || []).slice(0, 5).map((x) => (typeof x === 'string' ? x : `${x.symbol || x.label || ''}${isNum(x.weight_pct) ? ` ${Number(x.weight_pct).toFixed(1)}%` : ''}${x.pulls ? ` (pulls ${x.pulls})` : ''}`)).join(', ');
      const missing = (a.not_assessed || []).slice(0, 8).map((x) => (typeof x === 'string' ? x : `${x.symbol || ''}: ${x.reason || x.why || ''}`)).join('; ');
      return html`<div class="bk-score"><div class="split"><p class="t-label">${a.label}</p>${scored ? html`<b class="bk-score-n">${Math.round(a.score)}</b>` : tag('off', 'Not scored')}</div><p class="bk-level">${a.level || ''}</p>
        ${scored ? html`<span class="bk-bar-t" aria-hidden="true"><span class="bk-bar-f" style="width:${Math.max(2, Math.min(100, a.score))}%"></span></span>` : ''}<p>${clean(a.summary || '')}</p>
        <p class="asof">Coverage ${pct(a.coverage_pct, 0)} of value.${drivers ? ` Driven by ${drivers}.` : ''}</p>${missing ? html`<p class="asof">Not assessed: ${missing}.</p>` : ''}
        <details class="more-inline"><summary>Inputs and method</summary><p>${clean(a.method || '')}</p>${a.weights ? html`<p>Weights: ${txt(a.weights)}</p>` : ''}${a.inputs ? html`<p>Inputs: ${txt(a.inputs)}</p>` : ''}<p class="asof">${a.version || s.version || ''}</p></details></div>`; }) : html`<p>No assessments could be made.</p>`}</div>
    <p class="asof">${clean(s.disclaimer || 'These describe the portfolio today. They are not forecasts of return and not validated probabilities.')}</p></section>`;
}
function optionsRisk(o) {
  if (!o) return html`<section class="section"><h2 class="t-h2">Options risk</h2><p class="t-muted" role="status">Calculating Greeks...</p></section>`;
  if (o.error || o.available === false) return html`<section class="section"><h2 class="t-h2">Options risk</h2><p>${clean(o.error || o.reason || '')}</p></section>`;
  return html`<section class="section" aria-labelledby="bx-h"><h2 class="t-h2" id="bx-h">Options risk</h2>
    <p class="section-sub">${src('optic')} Greeks from implied volatility solved from your broker's option price and Optic's underlying quote. Delta is in share-equivalents (positive gains when the underlying rises); theta and vega are in dollars.</p>
    <div class="tscroll"><table class="t"><thead><tr><th scope="col">Contract</th><th scope="col">Contracts</th><th scope="col">IV</th><th scope="col">Delta (sh)</th><th scope="col">Theta / day</th><th scope="col">Vega / pt</th><th scope="col">Notes</th></tr></thead>
      <tbody>${(o.positions || []).map((p) => html`<tr><td>${p.underlying || ''} ${p.strike || ''} ${p.option_type || p.type || ''} ${p.expiry || ''}</td><td>${p.contracts}</td><td>${isNum(p.iv) ? pct(100 * p.iv, 1) : 'n/a'}</td><td>${isNum(p.delta_shares) ? Number(p.delta_shares).toFixed(1) : 'n/a'}</td><td>${isNum(p.theta_per_day) ? signedMoney(p.theta_per_day, p.currency || 'USD') : 'n/a'}</td><td>${isNum(p.vega_per_vol_point) ? money(p.vega_per_vol_point, p.currency || 'USD') : 'n/a'}</td>
        <td class="bk-left">${[p.greeks_available === false ? (p.greeks_reason || 'No Greeks for this contract.') : '', (p.notes || []).join(' ')].filter(Boolean).join(' ')}</td></tr>`)}</tbody></table></div>
    ${(o.by_underlying || []).length ? html`<h3>By underlying</h3><ul class="plain">${o.by_underlying.map((u) => html`<li><b>${u.underlying}</b>: ${(u.legs_without_greeks || []).length && !u.complete ? `${u.stock_shares || 0} shares held; ${u.legs_without_greeks.length} option leg${u.legs_without_greeks.length === 1 ? '' : 's'} without Greeks, so no net delta is shown` : html`net ${Number(u.net_delta_shares || 0).toFixed(1)} share-equivalents (${u.stock_shares || 0} shares held)${isNum(u.theta_per_day) ? html`, theta ${signedMoney(u.theta_per_day, u.currency || 'USD')} a day` : ''}`}</li>`)}</ul>` : ''}
    ${(o.considerations || []).length ? html`<h3>Assignment and settlement</h3><ul class="plain">${o.considerations.map((c) => html`<li>${clean(typeof c === 'string' ? c : (c.text || c.note || ''))}</li>`)}</ul>` : ''}${limits(o.limitations)}</section>`;
}

/* ---------------- performance ---------------- */
// the periods whose start is more than four days before the first value Optic holds (a long weekend is not a gap)
export function shortPeriods(period) {
  const hs = period && period.history_start, st = (period && period.starts) || {};
  if (!hs) return [];
  return PERIODS.map(([k]) => k).filter((k) => k !== 'all' && st[k] && (Date.parse(hs) - Date.parse(st[k])) / 864e5 > 4);
}
const listWords = (xs) => (xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`);
function performance(d) {
  const r = d.returns || {}, twr = r.twr || {}, mwr = r.mwr || {}, bench = r.benchmark || {}, period = d.period || {}, ccy = d.currency || 'USD';
  const words = { provider_estimate: 'SnapTrade\'s estimated daily balances', collected: 'snapshots Optic collected at each sync', mixed: 'SnapTrade\'s estimates, then Optic\'s own snapshots', none: 'no value history yet' }[(d.sources || {}).values] || (d.sources || {}).values || 'unknown';
  const flows = d.flows || {}, inc = d.income || {}, att = d.attribution || {}, enough = isNum(twr.pct);
  const needsAddon = (d.data_status || []).some((s) => s.balance_history === 'unavailable');
  // a period that reaches back past the first value Optic holds measures the same days as All: it waits, said so,
  // rather than offering buttons that all show one number (owner, 2026-10-20: "these percentages remain a constant")
  const short = shortPeriods(period), shown = short.includes(W.period) ? 'all' : W.period;
  return html`<section class="section first" aria-labelledby="bp-h"><h2 class="t-h2" id="bp-h">Performance</h2>
      <div class="cluster"><div class="seg" role="group" aria-label="Period">${PERIODS.map(([k, l]) => html`<button type="button" data-v2-bk-period="${k}" aria-pressed="${shown === k}" ${short.includes(k) ? html`disabled title="Needs history back to ${day(period.starts[k])}"` : ''}>${l}</button>`)}</div>
        <label class="select"><span class="t-label">Benchmark</span><select data-v2-bk-bench>${BENCHMARKS.map(([k, l]) => html`<option value="${k}" ${W.bench === k ? 'selected' : ''}>${l}</option>`)}</select></label></div>
      ${short.length ? html`<p class="bk-short">Optic has values for these accounts from ${day(period.history_start)}, so ${listWords(short.map((k) => PERIODS.find((x) => x[0] === k)[1]))} would measure the same days as All. ${short.length > 1 ? 'They open' : 'It opens'} as the history grows: Optic records a value at each sync.</p>` : ''}
      ${enough ? html`<div class="bk-tiles">${tile('Time-weighted return', sPct(twr.pct), html`${src('optic')} The investments' own result, with deposits and withdrawals taken out.${twr.annualized ? ` Annualised ${pct(twr.annualized_pct, 2, true)}.` : ' Not annualised: under a year.'}`)}
          ${tile('Money-weighted return', sPct(mwr.period_pct), html`${src('optic')} Your own result, weighted by when you added or took out money.${twr.annualized && isNum(mwr.irr_annualized_pct) ? ` Annualised ${pct(mwr.irr_annualized_pct, 2, true)}.` : ''}`)}
          ${tile(`Benchmark (${bench.symbol || W.bench})`, sPct(bench.twr_pct), html`${src('market')} Total return with dividends reinvested, over the same dates.`)}${tile('Difference', sPct(r.excess_pct), html`${src('optic')} Your time-weighted return minus the benchmark's.`)}</div>
        ${period.measured_start ? html`<p class="asof">Measured ${day(period.measured_start)} to ${day(period.measured_end)} (${period.days || ''} days) from ${words}.</p>` : ''}
        <h3>Cumulative return, yours and the benchmark's</h3><p class="legend-line cmp-legend"><span><i class="c1"></i>Your time-weighted return</span><span><i class="c2"></i>${bench.symbol || W.bench} total return</span></p><div class="chart-slot" data-chart="cum"></div>
        <h3>Value and money put in ${src('broker')}</h3><p class="legend-line cmp-legend"><span><i class="c1"></i>Value</span><span><i class="c0"></i>Starting value plus net deposits</span></p><div class="chart-slot" data-chart="val"></div>
        <p class="asof">The value line includes your own deposits and withdrawals, so it is not a return and is not compared with the benchmark.</p>`
        : html`<p>${clean((d.limitations || [])[0] || 'There is not enough history yet to measure a return.')}</p>`}</section>
    <div class="grid2"><section class="section"><h2 class="t-h2">Money in and out</h2><p class="section-sub">${src('broker')} From your broker's transaction history.</p>
        <dl class="reads-dl"><div><dt>Deposits</dt><dd>${money(flows.deposits, ccy)}</dd></div><div><dt>Withdrawals</dt><dd>${money(flows.withdrawals, ccy)}</dd></div><div><dt>Net</dt><dd>${signedMoney(flows.net_external, ccy)}</dd></div></dl>
        ${(flows.internal_transfers || {}).matched ? html`<p class="asof">${flows.internal_transfers.matched} transfer${flows.internal_transfers.matched === 1 ? '' : 's'} between your linked accounts (${money(flows.internal_transfers.total, ccy)}) left out: they move money between your own accounts, not in or out.</p>` : ''}
        ${(flows.unvalued || []).length ? html`<p class="asof">${flows.unvalued.length} transfer${flows.unvalued.length === 1 ? '' : 's'} of securities had no value from the broker; returns are not measured across ${flows.unvalued.length === 1 ? 'it' : 'them'}.</p>` : ''}</section>
      <section class="section"><h2 class="t-h2">Income and costs</h2><dl class="reads-dl"><div><dt>Dividends</dt><dd>${signedMoney(inc.dividends, ccy)}</dd></div><div><dt>Interest</dt><dd>${signedMoney(inc.interest, ccy)}</dd></div>
        <div><dt>Fees paid</dt><dd>${money(inc.fees === null || inc.fees === undefined ? null : Math.abs(Number(inc.fees)), ccy)}</dd></div><div><dt>Taxes withheld</dt><dd>${money(inc.taxes === null || inc.taxes === undefined ? null : Math.abs(Number(inc.taxes)), ccy)}</dd></div></dl></section></div>
    <section class="section"><h2 class="t-h2">What drove it</h2>
      ${att.available ? html`<p class="section-sub">${src('optic')} Price effect on each position held through each pair of days Optic has a snapshot for, ${day((att.window || {}).start)} to ${day((att.window || {}).end)}.</p>
        <div class="tscroll"><table class="t"><thead><tr><th scope="col">Holding</th><th scope="col">Contribution</th><th scope="col">Of average capital</th></tr></thead><tbody>${(att.positions || []).slice(0, 10).map((x) => html`<tr><td>${x.label || x.symbol || x.key || ''}</td><td>${signedMoney(x.contribution, x.currency || ccy)}</td><td>${sPct(x.contribution_pct)}</td></tr>`)}</tbody></table></div>
        <p class="asof">Contributions ${signedMoney(att.sum_contributions, ccy)}, money in or out ${signedMoney(att.flows, ccy)}, everything else ${signedMoney(att.remainder, ccy)}: together the change of ${signedMoney(att.total_change, ccy)}. ${clean(att.remainder_note || '')}</p>`
        : html`<p>${clean(att.reason || 'Contributions need at least two of Optic\'s daily snapshots in the period. One is taken at every sync.')}</p>`}</section>
    <section class="section"><h2 class="t-h2">History this rests on</h2>
      ${(d.data_status || []).length ? html`<ul class="plain">${d.data_status.map((s) => html`<li><b>${s.account}</b>: transactions ${s.transactions}${s.first_transaction ? ` from ${day(s.first_transaction)}` : ''}; balance history ${s.balance_history}</li>`)}</ul>` : ''}
      ${needsAddon ? html`<p class="asof">SnapTrade's balance-history add-on is off for these accounts. Switching it on in the SnapTrade dashboard (free) gives up to a year of estimated daily values; until then Optic measures from the snapshots it collects itself.</p>` : ''}
      ${limits(d.limitations, false)}<details class="more-inline"><summary>How these are calculated</summary>${Object.entries(d.definitions || {}).map(([k, v]) => html`<p><b>${k.replace(/_/g, ' ')}</b>: ${clean(typeof v === 'string' ? v : JSON.stringify(v))}</p>`)}<p class="asof">${d.version || ''}</p></details></section>`;
}
function perfCharts(d) {
  const ser = (d.series || []).filter((p) => isNum(p.cum_twr_pct)), out = {};
  if (ser.length >= 2) {
    // the two charts follow each other's crosshair by date (ui/chart.js sync), each in its own unit
    out.cum = (w) => lineChart(ser.map((p) => ({ d: p.date, c: p.cum_twr_pct })), { sync: 'bk-perf', measure: 'points', msUnit: ' pts', w, h: 220, dp: 1, label: 'Your time-weighted return, %', overlays: [{ values: ser.map((p) => (isNum(p.cum_benchmark_pct) ? p.cum_benchmark_pct : NaN)), cls: 'c2' }, { values: ser.map(() => 0), cls: 'c0' }],
      summary: `Cumulative time-weighted return ${pct(ser[ser.length - 1].cum_twr_pct, 1, true)} against the benchmark's ${pct(ser[ser.length - 1].cum_benchmark_pct, 1, true)}, ${day(ser[0].date)} to ${day(ser[ser.length - 1].date)}.` });
  }
  const vals = (d.series || []).filter((p) => isNum(p.value));
  if (vals.length > 1) {
    let cum = 0; const net = vals.map((p) => { cum += Number(p.net_flow || 0); return cum; }); const base = Number(vals[0].value) - net[0];
    out.val = (w) => lineChart(vals.map((p) => ({ d: p.date, c: Number(p.value) })), { sync: 'bk-perf', w, h: 180, dp: 0, label: 'Account value', overlays: [{ values: net.map((n) => base + n), cls: 'c0' }] });
  }
  return out;
}

/* ---------------- events & research ---------------- */
function eventRows(list, compact) {
  if (!list || !list.length) return html`<p class="t-muted">Nothing scheduled in the window for what you hold.</p>`;
  const kind = { earnings: 'Earnings', ex_dividend: 'Ex-dividend', option_expiry: 'Option expiry' };
  return html`<ul class="bk-events">${list.map((e) => html`<li><span class="bk-when">${day(e.date)}<small class="t-muted">${e.days_away === 0 ? 'today' : `in ${e.days_away} day${e.days_away === 1 ? '' : 's'}`}</small></span>
    <span><b>${e.symbol}</b> ${kind[e.kind] || e.kind} ${e.kind === 'earnings' ? tag(e.confirmed ? 'on' : 'warn', e.confirmed ? 'Confirmed' : 'Estimated') : ''} ${RP.habitLine(e) ? html`<small class="t-muted">${RP.habitLine(e)}</small>` : ''} ${e.weight_pct ? html`<small class="t-muted">${pct(e.weight_pct)} of portfolio</small>` : ''} ${!compact && e.note ? html`<small class="t-muted">${clean(e.note)}</small>` : ''}</span>
    ${!compact && e.links ? html`<span class="cluster">${e.links.earnings ? html`<a class="btn btn-sm" href="${v2href(e.links.earnings)}">Earnings analysis</a>` : ''}${e.links.overview ? html`<a class="btn btn-sm" href="${v2href(e.links.overview)}">Dossier</a>` : ''}${e.links.options ? html`<a class="btn btn-sm" href="${v2href(e.links.options)}">Options</a>` : ''}</span>` : ''}</li>`)}</ul>`;
}
// the server writes classic addresses ("#/AAPL/earnings"); they are the same in v2
const v2href = (h) => String(h || '').replace(/^\/?#/, '#');
function events(d) {
  const cal = d.calendar || {}, sum = cal.summary || {}, desk = d.desk || {};
  return html`<section class="section first" aria-labelledby="bv-h"><h2 class="t-h2" id="bv-h">Your calendar</h2>
      <p class="section-sub">${src('market')} Earnings, ex-dividend dates and option expiries for what you hold, next ${cal.window_days || 45} days. Reporting in the next two weeks: ${pct(sum.earnings_next_14d_pct)} of your portfolio (${pct(sum.earnings_confirmed_next_14d_pct)} on confirmed dates).</p>
      ${eventRows(cal.events || [], false)}${limits(cal.limitations)}</section>
    ${theses(d.theses || {})}
    <section class="section" aria-labelledby="bk-desk"><h2 class="t-h2" id="bk-desk">Optic Desk, for your portfolio</h2>
      ${desk.available ? html`<p class="section-sub">From the ${desk.edition.slot_label || ''} edition of ${day(desk.edition.date)}${desk.edition.is_today ? '' : ' (not today\'s)'}: "${desk.edition.headline || ''}". These are the edition's own sources that touch what you hold; nothing was rewritten for you.</p>
        ${(desk.items || []).length ? html`<ul class="plain">${desk.items.map((i) => html`<li><b>${i.label || ''}</b>${isNum(i.value) || i.value ? html` <small class="t-muted">${String(i.value)}${i.unit || ''}</small>` : ''}<br><small class="t-muted">${clean(i.why || '')}${(i.cited_in || []).length ? ` Cited in: ${i.cited_in.join(', ')}.` : ''} ${i.source || ''}</small>${i.url ? html` <a href="${i.url}" target="_blank" rel="noopener">Source</a>` : ''}</li>`)}</ul>` : html`<p class="t-muted">Nothing in this edition touches what you hold.</p>`}
        ${(desk.market_wide || []).length ? html`<h3>Market-wide, next three days</h3><ul class="plain">${desk.market_wide.map((m) => html`<li>${m.label} <small class="t-muted">${day(m.event_at)}</small></li>`)}</ul>` : ''}
        <a class="btn btn-sm" href="#/read">Read the full edition</a>${limits(desk.limitations)}` : html`<p>${clean(desk.reason || 'No edition is available.')}</p>`}</section>
    ${alertsBlock(d.alerts || {}, d.alert_settings || {}, d.alert_choices || {})}`;
}
function theses(th) {
  const list = th.theses || [], missing = th.held_without_thesis || [];
  const form = (t) => html`<form class="bk-thesis stack" data-v2-bk-thesis-form="${t.symbol}"><h3>${t.symbol}</h3>
    ${THESIS_FIELDS.map(([k, , label]) => html`<label class="field"><span class="t-label">${label}</span>${k === 'horizon' ? html`<input name="${k}" maxlength="200" value="${t[k] || ''}" placeholder="For example: 3 to 5 years">` : html`<textarea name="${k}" rows="2" maxlength="8000">${t[k] || ''}</textarea>`}</label>`)}
    <div class="cluster"><button type="submit" class="btn btn-primary">Save thesis</button><button type="button" class="btn" data-v2-bk-thesis-cancel>Cancel</button></div></form>`;
  return html`<section class="section" aria-labelledby="bt-h"><h2 class="t-h2" id="bt-h">Your theses</h2>
    <p class="section-sub">Why you own each position, in your own words, and what has happened since. Shared with the Dossier's thesis for the same symbol.</p>
    ${list.length ? list.map((t) => (W.thesisEdit === t.symbol ? form(t) : html`<div class="bk-thesis"><div class="split"><h3>${t.symbol} ${t.held ? html`<small class="t-muted">${pct(t.weight_pct)} of portfolio</small>` : tag('off', 'Not held')}</h3>
        <span class="cluster"><button type="button" class="btn btn-sm" data-v2-bk-thesis-edit="${t.symbol}">Edit</button>${W.thesisArmed === t.symbol ? html`<button type="button" class="btn btn-sm btn-danger" data-v2-bk-thesis-del="${t.symbol}" data-v2-confirm="1">Delete thesis</button>` : html`<button type="button" class="btn btn-sm" data-v2-bk-thesis-del="${t.symbol}">Delete</button>`}</span></div>
      <dl class="reads-dl">${THESIS_FIELDS.filter(([k]) => t[k]).map(([k, , label]) => html`<div><dt>${label}</dt><dd>${t[k]}</dd></div>`)}</dl>
      <p class="asof">Saved ${t.saved_at ? ago(t.saved_at) : 'n/a'}. Your words; Milo can comment on them but never changes them.</p>
      <h4>Since you saved it</h4>${(t.developments || []).length ? html`<ul class="plain">${t.developments.map((x) => html`<li>${x.source_url ? html`<a href="${x.source_url}" target="_blank" rel="noopener">${x.title || ''}</a>` : x.title || ''} <small class="t-muted">${x.event_date || ''} ${x.source_name || x.basis || ''}</small></li>`)}</ul>` : html`<p class="t-muted">Nothing new found in headlines, filings or the calendar.</p>`}
      ${miloButton('Ask Milo about this thesis', { ask: `How does what has happened since I saved my ${t.symbol} thesis bear on it? My thesis: ${(t.why || '').slice(0, 300)}${t.reassess_if ? ` I said I would reassess if: ${t.reassess_if.slice(0, 200)}` : ''}`, context: `Brokerage: ${t.symbol} thesis`, symbol: t.symbol })}</div>`)) : html`<p class="t-muted">No theses yet.</p>`}
    ${W.thesisEdit && !list.some((t) => t.symbol === W.thesisEdit) ? form({ symbol: W.thesisEdit }) : missing.length ? html`<p class="cluster"><span>Write down why you own it:</span>${missing.slice(0, 12).map((s) => html`<button type="button" class="btn btn-sm" data-v2-bk-thesis-edit="${s}">${s}</button>`)}</p>` : ''}</section>`;
}
function alertsBlock(a, s, choices) {
  const draft = W.alertDraft || JSON.parse(JSON.stringify(s || {}));
  const sel = (path, label) => { const [k, f] = path.split('.'); return html`<label class="select select-inline"><span class="sr">${label}</span><select data-v2-bk-alert="${path}">${(choices[path] || []).map((v) => html`<option value="${v}" ${(draft[k] || {})[f] === v ? 'selected' : ''}>${v}</option>`)}</select></label>`; };
  const on = (k, label, extra) => html`<div class="bk-alert-row"><label class="check"><input type="checkbox" data-v2-bk-alert="${k}.on" ${(draft[k] || {}).on ? 'checked' : ''}> <span>${label}</span></label>${extra || ''}</div>`;
  return html`<section class="section" aria-labelledby="bl-h"><h2 class="t-h2" id="bl-h">Alerts</h2><p class="section-sub">In Optic only, unless you turn on email below. Each situation is raised once, not on every visit.</p>
    ${(a.alerts || []).length ? html`<ul class="plain bk-alerts">${a.alerts.slice(0, 15).map((x) => html`<li class="${x.seen ? '' : 'is-unseen'}"><b>${x.title}</b> <small class="t-muted">${ago(x.created_at)}${x.seen ? '' : ', unread'}</small><br><span class="t-muted">${clean(x.body || '')}</span>${x.link ? html` <a href="${v2href(x.link)}">Open</a>` : ''}</li>`)}</ul>` : html`<p class="t-muted">No alerts yet.</p>`}
    <div class="cluster"><button type="button" class="btn btn-sm" data-v2-bk-alerts="check">Check now</button>${a.unseen ? html`<button type="button" class="btn btn-sm" data-v2-bk-alerts="seen">Mark all read</button>` : ''}</div>
    <details class="more-inline"><summary>Alert settings</summary><div class="stack bk-alert-set">
      ${on('earnings', 'A holding reports within', html`${sel('earnings.days', 'Days before earnings')} <span>days</span>`)}
      ${on('concentration', 'One holding passes', html`${sel('concentration.single_pct', 'Single holding share')} <span>% or one sector passes</span> ${sel('concentration.sector_pct', 'Sector share')} <span>%</span>`)}
      ${on('drift', 'A holding\'s weight moves', html`${sel('drift.pp', 'Weight change in points')} <span>points in about a month</span>`)}
      ${on('exposure', 'A sector\'s share moves', html`${sel('exposure.pp', 'Sector change in points')} <span>points in about a month</span>`)}
      ${on('thesis', 'Something new about a name with a thesis')}${on('connection', 'A connection needs attention')}
      <label class="check"><input type="checkbox" data-v2-bk-alert="email" ${draft.email ? 'checked' : ''}> <span>Also email me a count of new alerts (nothing about holdings is put in the email)</span></label>
      <div><button type="button" class="btn btn-primary btn-sm" data-v2-bk-alerts="save">Save alert settings</button></div></div></details></section>`;
}

/* ---------------- page ---------------- */
function body() {
  const st = S.status;
  if (S.err) return html`<div class="state err" role="alert"><p class="t-h3">Brokerage did not load</p><p>${S.err}</p><button type="button" class="btn btn-sm" data-v2-bk-reload>Try again</button></div>`;
  if (!st) return skeleton('rows', 4, 'Loading your brokerage');
  if (!st.available) return html`<section class="section first"><p>${clean(st.reason || 'Brokerage linking is not available right now.')}</p></section>`;
  if (!st.signed_in) return html`<section class="section first"><h2 class="t-h2">Link your brokerage</h2><p>See your real holdings in Optic and ask Milo about them. Read-only: Optic cannot trade or move money. Sign in first; linking is part of the paid plan.</p><a class="btn btn-primary" href="#/signin">Sign in</a></section>${permissions(st, true)}`;
  const ent = st.entitlement || {};
  if (!ent.can_link && !linked()) return html`${upgrade(ent)}${permissions(st, true)}`;
  if (!linked()) return connections();
  return frame(S.section);
}
function paint(focusSel) {
  if (!live) return;
  const y = window.scrollY, a = document.activeElement;
  const keepSel = focusSel || (a && mainEl.contains(a) ? (a.id ? `#${a.id}` : [...a.attributes].filter((x) => x.name.startsWith('data-v2-')).map((x) => `[${x.name}="${CSS.escape(x.value)}"]`).join('') || null) : null);
  const fl = S.flash ? FLASH[S.flash] : null; // kept until the reader moves to another section
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">Brokerage</h1>${linked() ? html`<p class="section-sub">Your own linked accounts, read-only. Optic cannot place, cancel or move anything.</p>` : ''}</header>
    ${fl ? html`<p class="bk-flash ${fl[0]}" role="status">${fl[1]}</p>` : ''}${body()}`);
  if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
  if (keepSel) { try { const el = mainEl.querySelector(keepSel); if (el) el.focus({ preventScroll: true }); } catch (e) { /* a selector the page no longer has */ } }
  if (linked() && S.section === 'performance' && W.data.performance) mountCharts(mainEl, perfCharts(W.data.performance));
  if (linked() && S.section === 'overview') scheduleRefresh();
}

async function loadStatus() {
  try {
    S.status = await api.get('/api/brokerage/status', { force: true });
    S.err = null;
    const ent = (S.status || {}).entitlement;
    if (ent && !ent.can_link) S.billing = await api.get('/api/billing/status', { force: true }).catch(() => null);
  } catch (e) { S.err = api.explain(e, 'Brokerage status'); S.status = null; }
}
async function loadSection(force) {
  const sec = S.section, scope = scopeIds().join(',');
  if (W.scopeKey !== scope) Object.assign(W, { data: {}, key: {}, extra: {}, error: {}, loading: {}, scopeKey: scope });
  if (force) { delete W.data[sec]; W.extra = {}; }
  if (!ENDPOINT[sec]) return;
  const want = wantKey(sec);
  if (W.data[sec] && W.key[sec] === want) { if (sec === 'holdings') loadExtras(); if (sec === 'overview') loadBriefing(); return; }
  if (W.loading[sec] === want) return;
  W.loading[sec] = want; W.error[sec] = null;
  const params = sec === 'performance' ? { period: W.period, benchmark: W.bench } : {};
  try {
    const d = await api.get(`/api/brokerage/workspace/${ENDPOINT[sec]}${query(params)}`, { force: true, timeout: 60000 });
    if (W.loading[sec] !== want || wantKey(sec) !== want) return;
    W.data[sec] = d; W.key[sec] = want;
  } catch (e) { if (W.loading[sec] !== want) return; W.error[sec] = e.message && e.kind !== 'server' ? e.message : api.explain(e, 'That section'); }
  W.loading[sec] = null;
  if (live && S.section === sec) paint();
  if (sec === 'overview' && W.data.overview) loadBriefing();
  if (sec === 'holdings' && W.data.holdings) loadExtras();
}
async function loadBriefing() {
  const scope = W.scopeKey;
  if (W.extra.briefing || W.loading.briefing === scope) return;
  W.loading.briefing = scope;
  let r; try { r = await api.get(`/api/brokerage/workspace/briefing${query()}`, { force: true, timeout: 60000 }); } catch (e) { r = { error: api.explain(e, 'The briefing') }; }
  if (W.scopeKey !== scope) return;
  W.loading.briefing = null; W.extra.briefing = r;
  if (live && S.section === 'overview') paint();
}
async function loadExtras() {
  const scope = W.scopeKey, want = [['scorecard', 'scorecard']];
  if ((W.data.holdings || {}).options && W.data.holdings.options.length) want.push(['options', 'options']);
  if (((W.data.holdings || {}).holdings || []).length || ((W.data.holdings || {}).options || []).length) want.push(['scenarios', 'scenarios']);
  await Promise.all(want.map(async ([k, path]) => {
    if (W.extra[k] || W.loading[k] === scope) return;
    W.loading[k] = scope;
    let r; try { r = await api.get(`/api/brokerage/workspace/${path}${query()}`, { force: true, timeout: 60000 }); } catch (e) { r = { error: api.explain(e, 'This') }; }
    if (W.scopeKey !== scope) return;
    W.loading[k] = null; W.extra[k] = r;
    if (live && S.section === 'holdings') paint();
  }));
}
// The Overview's prices refresh every minute while the regular session is open and the tab is visible.
// 4:00 am to 8:00 pm Eastern, weekdays: pre-market, the session and after hours, whose prints Brokerage now prices
function tapeLive() { const p = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric', minute: 'numeric', hour12: false }).formatToParts(new Date()); const g = (t) => (p.find((x) => x.type === t) || {}).value; const m = Number(g('hour')) * 60 + Number(g('minute')); return !['Sat', 'Sun'].includes(g('weekday')) && m >= 240 && m < 1200; }
function scheduleRefresh() { clearTimeout(refreshT); if (!tapeLive()) return; refreshT = setTimeout(refreshOverview, 60000); }
async function refreshOverview() {
  if (!live || S.section !== 'overview') return;
  if (document.hidden) { scheduleRefresh(); return; }
  const want = wantKey('overview');
  try { const d = await api.get(`/api/brokerage/workspace/overview${query()}`, { force: true }); if (live && S.section === 'overview' && wantKey('overview') === want) { W.data.overview = d; W.key.overview = want; paint(); } } catch (e) { scheduleRefresh(); }
}
const onVisible = () => { if (!document.hidden && live && S.section === 'overview' && linked()) refreshOverview(); };

function setSection(id, push) {
  if (push) S.flash = null;
  const ids = SECTIONS.map((s) => s.id);
  const next = ids.includes(id) ? id : 'overview';
  S.section = next; keep(SECTION_KEY, next);
  const want = `#/brokerage/${next}`;
  if (location.hash !== want) { try { history[push ? 'pushState' : 'replaceState'](null, '', want); } catch (e) { /* a sandboxed frame */ } }
}
async function loadAll(force) {
  await loadStatus();
  paint();
  if (linked()) await loadSection(force);
}

async function act(fn, ok, bad) { try { const r = await fn(); if (ok) toast(typeof ok === 'function' ? ok(r) : ok); return r || {}; } catch (e) { toast(e.message && e.kind !== 'server' ? e.message : bad || api.explain(e, 'That'), { kind: 'bad' }); return null; } }

export async function render(main, route, app) {
  live = true; mainEl = main; appRef = app;
  document.title = 'Brokerage, Optic';
  const q = new URLSearchParams(location.search), code = q.get('brokerage');
  if (code && FLASH[code]) { S.flash = code; q.delete('brokerage'); history.replaceState(null, '', `${location.pathname}${q.toString() ? `?${q}` : ''}${location.hash}`); }
  setSection(route.section || (S.flash ? 'connections' : stored(SECTION_KEY, 'overview')), false);
  provideContext(() => ({ view: 'brokerage', brokerage_scope: scopeIds(), focus_label: `Brokerage: ${(SECTIONS.find((s) => s.id === S.section) || {}).label}` }));
  document.addEventListener('visibilitychange', onVisible);
  wire(main);
  paint();
  await loadAll(false);
}
export function dispose() { live = false; S.flash = null; clearTimeout(refreshT); document.removeEventListener('visibilitychange', onVisible); }
export function onAuth() { if (live) { W.scopeKey = null; loadAll(true); } }

function wire(main) {
  main.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-bk-tab]')) || (b = t('[data-v2-bk-go]'))) { setSection(b.dataset.v2BkTab || b.dataset.v2BkGo, true); paint(b.dataset.v2BkTab ? `#bkt-${S.section}` : '#bk-panel'); loadSection(false); return; }
    if (t('[data-v2-bk-reload]')) { S.err = null; S.status = null; paint(); loadAll(true); return; }
    if (t('[data-v2-bk-retry]')) { W.error[S.section] = null; paint(); loadSection(true); return; }
    if ((b = t('[data-v2-bk-sectors]'))) { W.sectors = b.dataset.v2BkSectors; paint(); return; }
    if ((b = t('[data-v2-bk-period]'))) { W.period = b.dataset.v2BkPeriod; delete W.data.performance; paint(); loadSection(false); return; }
    if (t('[data-v2-bk-write]')) {
      S.writing = true; paint();
      const r = await act(() => api.post('/api/brokerage/workspace/briefing/written', { accounts: scopeIds() }, { timeout: 90000 }), null, 'The briefing could not be written.');
      S.writing = false; if (r && W.extra.briefing) W.extra.briefing.written = r.written; paint(); return;
    }
    if ((b = t('[data-v2-bill]'))) {
      b.disabled = true;
      const r = await act(() => api.post(`/api/billing/${b.dataset.v2Bill === 'portal' ? 'portal' : 'checkout'}`, {}), null, 'Billing is not available right now.');
      b.disabled = false; if (r && SAFE(r.url)) location.assign(r.url); else if (r) toast('Billing is not available right now.', { kind: 'bad' });
      return;
    }
    if ((b = t('[data-v2-bk-connect]')) || (b = t('[data-v2-bk-reconnect]'))) {
      b.disabled = true;
      const reqBody = b.dataset.v2BkReconnect ? { reconnect: b.dataset.v2BkReconnect } : {}, c = (S.status || {}).consent || {};
      if (!c.accepted && S.agreed) reqBody.consent_version = c.version;
      // fetched at the click: the provider's link expires in five minutes
      const r = await act(() => api.post('/api/brokerage/connect', reqBody), null, 'Could not start the connection.');
      b.disabled = false;
      if (r && SAFE(r.url)) { location.assign(r.url); return; }
      if (r) toast('The connection link did not point at the provider, so Optic did not follow it.', { kind: 'bad' });
      return;
    }
    if ((b = t('[data-v2-bk-sync]'))) {
      S.syncing = b.dataset.v2BkSync; paint();
      const words = { requested: 'Refresh requested. Your broker\'s data usually arrives within a few minutes; this page updates when it does.', ok: 'Synced.', partial: 'Synced, but some data did not arrive.', expired: 'Your broker needs you to reconnect.', outage: 'The provider did not respond. Showing the last good data.', busy: 'A sync is already running.', paused: 'Syncing is paused because the plan ended.', unsupported: 'This account is not supported.', error: 'The sync failed.' };
      const r = await act(() => api.post(`/api/brokerage/connections/${encodeURIComponent(S.syncing)}/sync`, {}, { timeout: 90000 }), (x) => x.message || words[x.result] || 'Done.', 'Sync failed.');
      void r; S.syncing = null; W.scopeKey = null; loadAll(true); return;
    }
    if ((b = t('[data-v2-bk-disconnect]'))) {
      if (!b.dataset.v2Confirm) { S.armed = b.dataset.v2BkDisconnect; paint(`[data-v2-bk-disconnect="${CSS.escape(S.armed)}"]`); return; }
      await act(() => api.post(`/api/brokerage/connections/${encodeURIComponent(b.dataset.v2BkDisconnect)}/disconnect`, {}), (x) => (x.provider_removal_queued ? 'Disconnected and deleted from Optic. The provider did not answer, so Optic will keep asking it to remove the connection.' : 'Disconnected. Optic\'s copy of that data is deleted.'), 'Could not disconnect.');
      S.armed = null; W.scopeKey = null; loadAll(true); return;
    }
    if ((b = t('[data-v2-bk-delete]'))) {
      if (b.dataset.v2BkDelete !== 'confirm') { S.armed = 'all'; paint('[data-v2-bk-delete="confirm"]'); return; }
      await act(() => api.post('/api/brokerage/delete-data', {}), 'All brokerage data deleted.', 'Could not delete.');
      S.armed = null; W.scopeKey = null; loadAll(true); return;
    }
    if (t('[data-v2-bk-disarm]')) { S.armed = null; paint(); return; }
    if ((b = t('[data-v2-bk-rename]'))) { S.renaming = b.dataset.v2BkRename; paint('[data-v2-bk-rename-input]'); const f = mainEl.querySelector('[data-v2-bk-rename-input]'); if (f) f.select(); return; }
    if (t('[data-v2-bk-rename-cancel]')) { S.renaming = null; paint(); return; }
    if ((b = t('[data-v2-bk-rename-save]'))) { saveRename(b.dataset.v2BkRenameSave); return; }
    if ((b = t('[data-v2-bk-thesis-edit]'))) { W.thesisEdit = b.dataset.v2BkThesisEdit; W.thesisArmed = null; paint('[data-v2-bk-thesis-form] textarea'); return; }
    if (t('[data-v2-bk-thesis-cancel]')) { W.thesisEdit = null; paint(); return; }
    if ((b = t('[data-v2-bk-thesis-del]'))) {
      const sym = b.dataset.v2BkThesisDel;
      if (!b.dataset.v2Confirm) { W.thesisArmed = sym; paint(`[data-v2-bk-thesis-del="${CSS.escape(sym)}"]`); return; }
      await act(() => api.del(`/api/theses/${encodeURIComponent(sym)}`).then((r) => { store.forgetLocalCopy('optic.thesis.v1', sym); return r; }), 'Thesis deleted.', 'Could not delete that thesis.');
      W.thesisArmed = null; delete W.data.events; paint(); loadSection(false); return;
    }
    if ((b = t('[data-v2-bk-alerts]'))) {
      const k = b.dataset.v2BkAlerts;
      if (k === 'check') { const r = await act(() => api.post('/api/brokerage/workspace/alerts/refresh', {}), (x) => `${x.new || 0} new alert${x.new === 1 ? '' : 's'}.`, 'Alerts could not be checked.'); if (r && W.data.events) W.data.events.alerts = r; paint(); return; }
      if (k === 'seen') { await act(() => api.post('/api/brokerage/workspace/alerts/seen', {})); if (W.data.events && W.data.events.alerts) { (W.data.events.alerts.alerts || []).forEach((x) => { x.seen = true; }); W.data.events.alerts.unseen = 0; } paint(); return; }
      if (k === 'save') { const r = await act(() => api.put('/api/brokerage/workspace/alerts/settings', W.alertDraft || {}), 'Alert settings saved.', 'Those settings were not saved.'); if (r && W.data.events) { W.data.events.alert_settings = r.settings; W.alertDraft = null; } paint(); }
    }
  });
  main.addEventListener('keydown', (e) => {
    const tab = e.target.closest('[data-v2-bk-tab]');
    if (tab) {
      const ids = SECTIONS.map((s) => s.id), at = ids.indexOf(tab.dataset.v2BkTab);
      const next = e.key === 'ArrowRight' ? ids[(at + 1) % ids.length] : e.key === 'ArrowLeft' ? ids[(at - 1 + ids.length) % ids.length] : e.key === 'Home' ? ids[0] : e.key === 'End' ? ids[ids.length - 1] : null;
      if (next) { e.preventDefault(); setSection(next, true); paint(`#bkt-${next}`); loadSection(false); }
      return;
    }
    const f = e.target.closest('[data-v2-bk-rename-input]');
    if (f) { if (e.key === 'Enter') { e.preventDefault(); saveRename(f.dataset.v2BkRenameInput); } else if (e.key === 'Escape') { e.stopPropagation(); S.renaming = null; paint(); } }
  });
  main.addEventListener('change', async (e) => {
    const t = e.target;
    if (t.matches('[data-v2-bk-consent]')) { S.agreed = t.checked; const btn = mainEl.querySelector('[data-v2-bk-connect]'); if (btn) { btn.disabled = !t.checked; btn.setAttribute('aria-disabled', String(!t.checked)); } return; }
    if (t.matches('[data-v2-bk-select]')) {
      t.disabled = true;
      const r = await act(() => api.patch(`/api/brokerage/accounts/${encodeURIComponent(t.dataset.v2BkSelect)}`, { selected: t.checked }), null, 'Could not change that.');
      if (!r) { t.checked = !t.checked; t.disabled = false; return; }
      W.scopeKey = null; loadAll(true); return;
    }
    if (t.matches('[data-v2-bk-scope]')) { keep(SCOPE_KEY, t.value ? [t.value] : []); W.scopeKey = null; paint('[data-v2-bk-scope]'); loadSection(false); return; }
    if (t.matches('[data-v2-bk-bench]')) { W.bench = t.value; delete W.data.performance; paint('[data-v2-bk-bench]'); loadSection(false); return; }
    if (t.matches('[data-v2-bk-alert]')) {
      W.alertDraft = W.alertDraft || JSON.parse(JSON.stringify((W.data.events || {}).alert_settings || {}));
      const path = t.dataset.v2BkAlert; if (path === 'email') { W.alertDraft.email = t.checked; return; }
      const [k, f] = path.split('.'); W.alertDraft[k] = W.alertDraft[k] || {}; W.alertDraft[k][f] = f === 'on' ? t.checked : Number(t.value);
    }
  });
  main.addEventListener('submit', async (e) => {
    const f = e.target.closest('[data-v2-bk-thesis-form]'); if (!f) return;
    e.preventDefault();
    const bodyOut = {}; THESIS_FIELDS.forEach(([k, apiKey]) => { bodyOut[apiKey] = ((f.elements[k] || {}).value || '').trim(); });
    const r = await act(() => api.put(`/api/theses/${encodeURIComponent(f.dataset.v2BkThesisForm)}`, bodyOut), 'Thesis saved.', 'Could not save that thesis.');
    if (r) { W.thesisEdit = null; delete W.data.events; paint(); loadSection(false); }
  });
}
async function saveRename(id) {
  const field = mainEl.querySelector('[data-v2-bk-rename-input]');
  const r = await act(() => api.patch(`/api/brokerage/accounts/${encodeURIComponent(id)}`, { nickname: field ? field.value : '' }), null, 'Could not rename that.');
  if (r) { S.renaming = null; loadAll(true); }
}
export const retry = { scenarios: () => { delete W.extra.scenarios; paint(); loadExtras(); } };
void store; void raw; void stamp; void num;
