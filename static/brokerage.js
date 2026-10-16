/* ============================================================ BROKERAGE WORKSPACE
 *
 * The Brokerage destination's six sections, for a reader with something
 * linked (2026-10-15). Loaded after app.js, whose BROKERAGE block keeps the
 * states before a link (sign in, plan, consent), the connection cards and the
 * shared formatters (bkMoney, bkSigned, bkQty, bkWhen, bkBars, bkChangesHtml);
 * renderBrokerage() hands over here once a connection exists.
 *
 * Every figure says which kind it is, because the reader acts differently on
 * each: what the broker reported (with the account's sync time and the
 * broker's own "as of"), Optic's market data (with the quote's time), and
 * Optic's calculations (with a method and a version). Account sync time and
 * quote freshness are shown separately, never as one "updated".
 *
 * Sections are addresses (#/brokerage/<section>, app.js parseRoute/routeFor),
 * the last one opened is remembered, and the account the workspace is narrowed
 * to is kept per reader. Nothing here can trade: there is no control that
 * places, cancels or moves anything, and the server has no route that could.
 */

const BKW_SECTIONS = [
  { id: 'overview', label: 'Overview', ask: 'What deserves my attention in my linked portfolio this week?' },
  { id: 'holdings', label: 'Holdings & Exposure', ask: 'Where am I concentrated, counting what my ETFs hold?' },
  { id: 'performance', label: 'Performance', ask: 'How has my portfolio done against the S&P 500, and how much of the change was my own deposits and withdrawals?' },
  { id: 'events', label: 'Events & Research', ask: 'Which earnings and events affect me in the next two weeks?' },
  { id: 'scenarios', label: 'Scenarios', ask: 'If I added to my largest position, how would my concentration change?' },
  { id: 'connections', label: 'Connections', ask: 'What can Optic see in my linked accounts, and what can it not?' },
];
const BKW_SECTION_KEY = 'optic.brokerage.section.v1';
const BKW_SCOPE_KEY = 'optic.brokerage.scope.v1';
const BKW_PERIODS = [['1m', '1M'], ['3m', '3M'], ['ytd', 'YTD'], ['1y', '1Y'], ['all', 'All']];
const BKW_BENCHMARKS = [['SPY', 'S&P 500 (SPY)'], ['VTI', 'US total market (VTI)'], ['QQQ', 'Nasdaq 100 (QQQ)'],
  ['ACWI', 'World stocks (ACWI)'], ['AGG', 'US bonds (AGG)']];
const BKW = {
  data: {},        // section id -> payload, for the scope it was loaded with
  dataKey: {},     // section id -> the bkwWantKey its payload answers
  scopeKey: null,  // the scope string the cached data belongs to
  loading: {},
  error: {},
  extra: {},       // scorecard, options, briefing: loaded after their section
  period: '1y',
  bench: 'SPY',
  sectors: 'look',
  scenario: { rows: [{ symbol: '', action: 'buy', amount_type: 'dollars', amount: '' }], funding: 'cash' },
  thesisEdit: null,
  thesisArmed: null,
  alertDraft: null,
};

function bkwStored(key, fallback) {
  try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch (e) { return fallback; }
}
function bkwStore(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode: the session still works */ }
}

/** Set the open section. Called by the route (fromRoute) and by the tabs. */
function bkSetSection(id, fromRoute) {
  const ids = BKW_SECTIONS.map((s) => s.id);
  let next = ids.includes(id) ? id : null;
  if (!next) next = BROKER.flash ? 'connections' : bkwStored(BKW_SECTION_KEY, 'overview');
  if (!ids.includes(next)) next = 'overview';
  const changed = BROKER.section !== next;
  BROKER.section = next;
  bkwStore(BKW_SECTION_KEY, next);
  // A bare #/brokerage, or one written before this file loaded, is brought in
  // line with the section actually shown, in place (no new history entry).
  if (STATE.view === 'brokerage' && typeof routeFor === 'function' && history.replaceState) {
    const want = routeFor('brokerage');
    if (want && want !== location.hash && fromRoute) {
      try { history.replaceState(null, '', want); } catch (e) { /* a sandboxed frame */ }
    }
  }
  if (STATE.view === 'brokerage' && BROKER.status && (BROKER.status.connections || []).length) {
    if (changed) {
      bkWorkspaceRender(views.brokerage, bkFlashHtml());
      bkWorkspaceLoad(false);
    }
    if (!fromRoute && typeof routeRecord === 'function') routeRecord();
    if (typeof updateChatContext === 'function') updateChatContext();
  }
}

function bkwSection() {
  if (!BROKER.section) bkSetSection(null, true);
  return BROKER.section || 'overview';
}

function bkViewLabel() {
  const s = BKW_SECTIONS.find((x) => x.id === bkwSection());
  return `Brokerage: ${s ? s.label : 'Overview'}`;
}

/** The accounts the workspace is narrowed to, or [] for every counted one. */
function bkScopeIds() {
  const ids = bkwStored(BKW_SCOPE_KEY, []);
  const own = new Set(bkwAllAccounts().map((a) => a.id));
  return Array.isArray(ids) ? ids.filter((i) => own.has(i)) : [];
}

function bkwAllAccounts() {
  const out = [];
  ((BROKER.status && BROKER.status.connections) || []).forEach((c) => (c.accounts || []).forEach((a) => out.push(Object.assign({ institution: c.institution }, a))));
  return out;
}

function bkwQuery(extra) {
  const ids = bkScopeIds();
  const q = new URLSearchParams(extra || {});
  if (ids.length) q.set('accounts', ids.join(','));
  const s = q.toString();
  return s ? `?${s}` : '';
}

function bkwPct(v, d = 1, signed = false) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return 'n/a';
  const n = Number(v);
  return `${signed && n > 0 ? '+' : ''}${n.toFixed(d)}%`;
}

function bkwSignedPct(v, d = 2) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return '<span class="bk-na">n/a</span>';
  const n = Number(v);
  return `<span class="${n > 0 ? 'pos' : n < 0 ? 'neg' : ''}">${bkwPct(n, d, true)}</span>`;
}

function bkwDate(iso) {
  if (!iso) return 'n/a';
  const d = new Date(String(iso).length === 10 ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

/** A source tag: which of the three kinds of figure this is. */
function bkwSrc(kind) {
  const words = { broker: 'Broker-reported', market: 'Market data', optic: 'Optic calculation' };
  return `<span class="bkw-src bkw-src-${kind}">${words[kind] || kind}</span>`;
}

function bkwChip(state, text) {
  return `<span class="data-state is-${state}"><span class="dot" aria-hidden="true"></span>${esc(text)}</span>`;
}

function bkwAskButton(text, label) {
  return `<button type="button" class="btn milo-btn bkw-ask" data-ask-text="${esc(text)}"><span class="pulse-mark" aria-hidden="true"><span class="scout-badge"><span class="scout-badge-fig"></span></span></span>${esc(label || 'Ask Milo')}</button>`;
}

function bkwEmpty(title, body) {
  return `<div class="panel span2 bkw-empty"><h2>${hg(title)}</h2><p class="sub">${esc(body)}</p></div>`;
}

function bkwLimits(list, open) {
  const items = (list || []).filter(Boolean);
  if (!items.length) return '';
  return `<details class="bkw-limits"${open ? ' open' : ''}><summary>What this cannot tell you</summary><ul>${items.map((l) => `<li>${esc(l)}</li>`).join('')}</ul></details>`;
}

// ------------------------------------------------------------------- frame

function bkwFreshness() {
  const o = BKW.data.overview || BKW.data.holdings || {};
  const f = o.freshness || {};
  const b = f.broker || {};
  const m = f.market || {};
  const chips = [];
  if (b.oldest_broker_as_of) chips.push(bkwChip('cached', `Broker data as of ${bkwDate(b.oldest_broker_as_of)} ${new Date(b.oldest_broker_as_of).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`));
  else if (b.newest_sync) chips.push(bkwChip('cached', `Synced ${agoWords(b.newest_sync)}`));
  if (m.quotes_newest) {
    const delayed = m.delayed_minutes ? ` (delayed ${Math.round(m.delayed_minutes)} min)` : '';
    chips.push(bkwChip(m.delayed_minutes ? 'delayed' : 'live', `Quotes ${agoWords(m.quotes_newest)}${delayed}`));
  }
  return chips.join(' ');
}

function bkwScopeSelect() {
  const accts = bkwAllAccounts();
  const ids = bkScopeIds();
  const counted = accts.filter((a) => a.selected);
  const opts = [`<option value=""${ids.length ? '' : ' selected'}>All counted accounts (${counted.length})</option>`]
    .concat(accts.map((a) => `<option value="${esc(a.id)}"${ids.length === 1 && ids[0] === a.id ? ' selected' : ''}>${esc(a.name || 'Account')} ${esc(a.number_mask || '')}${a.selected ? '' : ' (not counted)'}</option>`));
  return `<label class="bkw-scope"><span class="eyebrow">Accounts</span><select data-bkw-scope aria-label="Accounts shown">${opts.join('')}</select></label>`;
}

function bkWorkspaceRender(host, flash) {
  if (!host) return;
  const sec = bkwSection();
  const def = BKW_SECTIONS.find((s) => s.id === sec) || BKW_SECTIONS[0];
  const tabs = BKW_SECTIONS.map((s) => `<button type="button" role="tab" class="sec-tab${s.id === sec ? ' on' : ''}" id="bkw-tab-${s.id}"
      aria-selected="${s.id === sec}" aria-controls="bkw-panel" tabindex="${s.id === sec ? 0 : -1}" data-bkw-tab="${s.id}">${esc(s.label)}</button>`).join('');
  host.innerHTML = `${flash || ''}
    <div class="bkw-head">
      ${bkwScopeSelect()}
      <div class="bkw-fresh" id="bkw-fresh">${bkwFreshness()}</div>
      ${bkwAskButton(def.ask)}
    </div>
    <nav class="sec-tabs bkw-tabs" role="tablist" aria-label="Brokerage sections">${tabs}</nav>
    <div id="bkw-panel" class="bkw-panel" role="tabpanel" aria-labelledby="bkw-tab-${sec}">${bkwSafeSection(sec)}</div>`;
  bkwAfterRender(sec);
}

function bkwSectionHTML(sec) {
  if (sec === 'connections') return bkConnectionsHTML();
  if (sec === 'scenarios') return bkwScenariosHTML();
  if (BKW.error[sec]) {
    return `<div class="panel span2"><p class="sub">${esc(BKW.error[sec])}</p><button type="button" class="btn" data-bkw-retry>Try again</button></div>`;
  }
  const d = BKW.data[sec];
  if (!d) return `<div class="panel span2 bkw-loading"><p class="sub">Loading ${esc((BKW_SECTIONS.find((s) => s.id === sec) || {}).label || sec)}...</p></div>`;
  if (sec === 'overview') return bkwOverviewHTML(d);
  if (sec === 'holdings') return bkwHoldingsHTML(d);
  if (sec === 'performance') return bkwPerformanceHTML(d);
  if (sec === 'events') return bkwEventsHTML(d);
  return '';
}

/* A renderer that throws must not leave the last state on screen: the first
 * local run showed "Working it out..." under a finished scenario because one
 * field had an unexpected shape. The section says so instead. */
function bkwSafeSection(sec) {
  try {
    return bkwSectionHTML(sec);
  } catch (e) {
    if (typeof console !== 'undefined') console.error('brokerage section', sec, e);
    return '<div class="panel span2"><p class="sub">This section could not be drawn. Reload the page; if it persists, report it with Report a Problem.</p></div>';
  }
}

function bkwPaintPanel() {
  const panel = document.getElementById('bkw-panel');
  if (!panel) return;
  const sec = bkwSection();
  panel.innerHTML = bkwSafeSection(sec);
  const fresh = document.getElementById('bkw-fresh');
  if (fresh) fresh.innerHTML = bkwFreshness();
  bkwAfterRender(sec);
}

function bkwAfterRender(sec) {
  if (sec === 'performance' && BKW.data.performance) bkwMountPerformance(BKW.data.performance);
  if (typeof revealPanels === 'function') revealPanels(views.brokerage);
}

/** Redraw from what is already loaded: a resize or a theme change. */
function bkWorkspaceRerender() {
  if (!document.getElementById('bkw-panel')) return false;
  bkwPaintPanel();
  return true;
}

const BKW_ENDPOINT = {
  overview: () => '/api/brokerage/workspace/overview',
  holdings: () => '/api/brokerage/workspace/holdings',
  performance: () => '/api/brokerage/workspace/performance',
  events: () => '/api/brokerage/workspace/events',
};

/* What a section's data must match to be shown: the account scope, and for
 * Performance the period and benchmark. A request answers for the key it was
 * sent with; one that comes back after the reader changed the account or the
 * period is dropped, not painted over the newer choice (2026-10-16: a load
 * started before switching to the Roth landed after it and showed both
 * accounts). */
function bkwWantKey(sec) {
  return `${bkScopeIds().join(',')}|${sec === 'performance' ? `${BKW.period}:${BKW.bench}` : ''}`;
}

async function bkWorkspaceLoad(force) {
  const sec = bkwSection();
  const scopeKey = bkScopeIds().join(',');
  if (BKW.scopeKey !== scopeKey) { BKW.data = {}; BKW.dataKey = {}; BKW.extra = {}; BKW.error = {}; BKW.loading = {}; BKW.scopeKey = scopeKey; }
  BKW.dataKey = BKW.dataKey || {};
  if (force) { delete BKW.data[sec]; BKW.extra = {}; }
  if (!BKW_ENDPOINT[sec]) return;
  const want = bkwWantKey(sec);
  if (BKW.data[sec] && BKW.dataKey[sec] === want) {
    if (sec === 'holdings') bkwLoadExtras();
    if (sec === 'overview') bkwLoadBriefing();
    return;
  }
  if (BKW.loading[sec] === want) return;
  BKW.loading[sec] = want;
  BKW.error[sec] = null;
  const params = sec === 'performance' ? { period: BKW.period, benchmark: BKW.bench } : {};
  const r = await brokerFetch('GET', BKW_ENDPOINT[sec]() + bkwQuery(params));
  if (BKW.loading[sec] !== want) return;          // superseded while in flight
  BKW.loading[sec] = null;
  if (bkwWantKey(sec) !== want) return;           // the reader has moved on
  if (r.ok) { BKW.data[sec] = r.data; BKW.dataKey[sec] = want; }
  else BKW.error[sec] = (r.data && r.data.detail) || 'That section could not be loaded.';
  if (STATE.view === 'brokerage' && bkwSection() === sec) bkwPaintPanel();
  if (sec === 'overview' && r.ok) bkwLoadBriefing();
  if (sec === 'holdings' && r.ok) bkwLoadExtras();
}

async function bkwLoadBriefing() {
  const scope = BKW.scopeKey;
  if (BKW.extra.briefing || BKW.loading.briefing === scope) return;
  BKW.loading.briefing = scope;
  const r = await brokerFetch('GET', '/api/brokerage/workspace/briefing' + bkwQuery());
  if (BKW.scopeKey !== scope) return;
  BKW.loading.briefing = null;
  BKW.extra.briefing = r.ok ? r.data : { error: (r.data && r.data.detail) || 'The briefing could not be built.' };
  if (bkwSection() === 'overview') bkwPaintPanel();
}

async function bkwLoadExtras() {
  const scope = BKW.scopeKey;
  const want = [['scorecard', '/api/brokerage/workspace/scorecard']];
  const h = BKW.data.holdings;
  if (h && (h.options || []).length) want.push(['options', '/api/brokerage/workspace/options']);
  await Promise.all(want.map(async ([key, url]) => {
    if (BKW.extra[key] || BKW.loading[key] === scope) return;
    BKW.loading[key] = scope;
    const r = await brokerFetch('GET', url + bkwQuery());
    if (BKW.scopeKey !== scope) return;
    BKW.loading[key] = null;
    BKW.extra[key] = r.ok ? r.data : { error: (r.data && r.data.detail) || 'Could not be calculated just now.' };
    if (bkwSection() === 'holdings') bkwPaintPanel();
  }));
}

// ------------------------------------------------------------------ overview

function bkwOverviewHTML(d) {
  const tot = d.totals || {};
  const comb = tot.combined_usd;
  const byc = tot.by_currency || {};
  const totalText = comb ? bkMoney(comb.value, 'USD') + (comb.approximate ? ' (approx.)' : '')
    : Object.entries(byc).map(([c, b]) => bkMoney(b.total, c)).join(' + ') || 'Not supplied';
  const today = d.today || {};
  const since = d.since_sync || {};
  const perf = d.performance || {};
  const pl = perf.unrealized_pl_by_currency || {};
  const tiles = [
    { k: 'Total value', v: esc(totalText), n: `${bkwSrc('broker')} Securities, options at the broker's last price, and cash.` },
    { k: 'Today', v: today.available ? `${bkSigned(today.total, 'USD')} ${bkwSignedPct(today.total_pct)}` : '<span class="bk-na">No quotes</span>',
      n: `${bkwSrc('market')} ${today.available ? `Quantity x price change since the previous close, quotes ${esc(agoWords(today.quotes_newest))}. Covers ${esc(bkMoney(today.covered_value_at_prev_close, 'USD'))}.` : 'Optic could not price your holdings just now.'}` },
    { k: 'Since your last sync', v: since.available ? Object.entries(since.value_change_by_currency || {}).map(([c, v]) => bkSigned(v, c)).join(' ') || '0' : '<span class="bk-na">After the next sync</span>',
      n: `${bkwSrc('optic')} ${since.available ? `Price effect ${Object.entries(since.price_effect_by_currency || {}).map(([c, v]) => bkSigned(v, c)).join(' ') || 'none'}; the rest is trades, deposits or new positions.` : esc(since.reason || '')}` },
    { k: 'Unrealised gain', v: Object.entries(pl).map(([c, v]) => bkSigned(v, c)).join(' ') || '<span class="bk-na">Not supplied</span>',
      n: `${bkwSrc('optic')} Market value minus the broker's average cost, on ${esc(String(perf.basis_coverage_pct ?? 'n/a'))}% of value with a cost basis. Not a return.` },
  ];
  const tilesHtml = `<div class="bk-tiles">${tiles.map((t) => `<div class="bk-tile"><span class="bk-k">${esc(t.k)}</span><span class="bk-v">${t.v}</span><span class="bk-n">${t.n}</span></div>`).join('')}</div>`;

  const top = (d.top_holdings || []).map((h) => ({ label: `${h.symbol || h.description}`, value: h.value_usd || h.market_value || 0, share_pct: h.weight_pct }));
  const own = `<div class="panel"><h2>${hg('What you own')}</h2>
      <p class="sub">${esc(String(d.holdings_count || 0))} holdings${d.options_count ? ` and ${d.options_count} option position${d.options_count === 1 ? '' : 's'}` : ''} in ${esc(String((d.scope && d.scope.scope || []).length))} account${(d.scope && d.scope.scope || []).length === 1 ? '' : 's'}. Largest, as a share of long value:</p>
      ${bkBars(top, 5)}
      <h3 class="bkw-h3">By kind</h3>${bkBars((d.allocation || {}).by_kind || [], 6)}
      <p class="set-row-note"><button type="button" class="btn sm" data-bkw-go="holdings">Holdings &amp; Exposure</button></p></div>`;

  const obs = (d.observations || []).map((o) => `<li><span>${esc(o.text)}</span> <span class="bkw-meta">${esc(o.source || '')}</span>
      ${o.section && o.section !== 'overview' ? `<button type="button" class="btn sm" data-bkw-go="${esc(o.section)}">Open</button>` : ''}</li>`).join('');
  const attention = `<div class="panel"><h2>${hg('Deserves attention')}</h2>
      ${obs ? `<ul class="bkw-list">${obs}</ul>` : '<p class="sub">Nothing stands out: no concentration over your thresholds, no reports this week, every account synced.</p>'}
      ${d.alerts_unseen ? `<p class="set-row-note">${d.alerts_unseen} unread alert${d.alerts_unseen === 1 ? '' : 's'}. <button type="button" class="btn sm" data-bkw-go="events">Read alerts</button></p>` : ''}
      <h3 class="bkw-h3">Coming up</h3>${bkwEventRows((d.upcoming || []).slice(0, 6), true)}</div>`;

  return `${tilesHtml}
    <div class="grid c2 bkw-grid">${own}${attention}</div>
    ${bkwBriefingHTML()}
    <div class="panel span2"><h2>${hg('Ask about your portfolio')}</h2>
      <div class="bk-asks">${BROKER_ASKS.concat(['Why did my portfolio move today?', 'What risks deserve more research?']).map((q) => `<button type="button" class="cc-q" data-ask-text="${esc(q)}">${esc(q)}</button>`).join('')}</div>
      <p class="set-row-note">Milo reads only your own linked accounts, read-only, and describes rather than advises.</p></div>
    ${bkwLimits(d.notes)}`;
}

function bkwBriefingHTML() {
  const b = BKW.extra.briefing;
  if (!b) return '<div class="panel span2"><h2>Briefing</h2><p class="sub">Measuring what moved...</p></div>';
  if (b.error) return `<div class="panel span2"><h2>Briefing</h2><p class="sub">${esc(b.error)}</p></div>`;
  const rows = ((b.today || {}).rows || []).slice(0, 5).map((r) => `<tr><td class="name">${esc(r.symbol)}</td><td class="num">${bkwSignedPct(r.change_pct)}</td><td class="num">${bkSigned(r.contribution, 'USD')}</td></tr>`).join('');
  const drivers = (b.drivers || []).map((x) => {
    const heads = (x.headlines || []).map((h) => `<li><a href="${esc(h.url || '#')}" target="_blank" rel="noopener">${esc(h.title || '')}</a> <span class="bkw-meta">${esc(h.publisher || '')} ${esc(h.published ? agoWords(h.published) : '')}</span></li>`).join('');
    return `<div class="bkw-driver"><b>${esc(x.symbol)}</b> ${bkwSignedPct(x.change_pct)}
      ${heads ? `<ul class="bkw-list">${heads}</ul>` : ''}${x.note ? `<p class="set-row-note">${esc(x.note)}</p>` : ''}</div>`;
  }).join('');
  const w = b.written;
  const earlier = b.written_earlier;
  const written = w ? `<div class="bkw-written"><p><b>${esc(w.headline)}</b></p>${['what_changed', 'drivers', 'ahead', 'attention'].map((k) => w[k] ? `<p>${esc(w[k])}</p>` : '').join('')}
      <p class="set-row-note">Written by Milo from the measured figures on this page, ${esc(agoWords(w.written_at))}.</p></div>`
    : `<p class="set-row-note">${earlier ? `An earlier write-up (${esc(agoWords(earlier.written_at))}) was from different figures. ` : ''}
      <button type="button" class="btn" data-bkw-write>Write it up</button> Uses one Milo message. The same figures are kept and not charged again.</p>`;
  return `<div class="panel span2"><h2>${hg('Briefing')}</h2>
    <div class="grid c2 bkw-grid"><div>
      <h3 class="bkw-h3">Measured: what moved today ${bkwSrc('market')}</h3>
      ${rows ? `<div class="ss-scroll"><table class="data bk-table"><thead><tr><th>Holding</th><th class="num">Today</th><th class="num">Contribution</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<p class="sub">No quotes to measure with just now.</p>'}
    </div><div>
      <h3 class="bkw-h3">Possibly related: headlines published around the move</h3>
      ${drivers || '<p class="sub">No large movers to look for headlines about.</p>'}
      <p class="set-row-note">Matched by when they were published. That is not evidence that they caused the move.</p>
    </div></div>
    ${written}</div>`;
}

// ------------------------------------------------------- holdings & exposure

function bkwHoldingsHTML(d) {
  const rows = (d.holdings || []).map((h) => {
    const q = (d.quotes || {})[String(h.symbol || '').toUpperCase()] || {};
    return `<tr>
      <td class="name"><b>${esc(h.symbol || '')}</b> <span class="bkw-meta">${esc(h.description || '')}</span></td>
      <td>${esc((h.accounts || []).join(', '))}</td>
      <td class="num">${esc(bkQty(h.quantity))}</td>
      <td class="num">${esc(bkMoney(h.price, h.currency))}</td>
      <td class="num">${q.price !== undefined && q.price !== null ? `${esc(bkMoney(q.price, 'USD'))} ${bkwSignedPct(q.change_pct)}` : '<span class="bk-na">n/a</span>'}</td>
      <td class="num">${esc(bkMoney(h.market_value, h.currency))}</td>
      <td class="num">${bkwPct(h.weight_pct)}</td>
      <td class="num">${h.cost_basis === null ? '<span class="bk-na">Not supplied</span>' : esc(bkMoney(h.cost_basis, h.currency))}</td>
      <td class="num">${h.unrealized_pl === null || h.unrealized_pl === undefined ? '<span class="bk-na">Not supplied</span>' : `${bkSigned(h.unrealized_pl, h.currency)} ${bkwSignedPct(h.unrealized_pct, 1)}`}</td>
    </tr>`;
  }).join('');
  const table = `<div class="panel span2"><h2>${hg('Holdings')}</h2>
    <p class="sub">${bkwSrc('broker')} quantity, price and cost from your broker at its last sync; ${bkwSrc('market')} Optic's quote beside it; ${bkwSrc('optic')} weights and unrealised gain.</p>
    <div class="ss-scroll"><table class="data bk-table"><thead><tr><th>Holding</th><th>Accounts</th><th class="num">Qty</th><th class="num">Broker price</th>
      <th class="num">Quote now</th><th class="num">Value</th><th class="num">Weight</th><th class="num">Cost basis</th><th class="num">Unrealised</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="9">No holdings in these accounts.</td></tr>'}</tbody></table></div>
    ${(d.price_checks || []).length ? `<p class="set-row-note">The broker's price and Optic's quote differ by 2% or more for ${esc(d.price_checks.map((c) => c.symbol).join(', '))}; the broker's is from its last sync.</p>` : ''}</div>`;
  const others = [];
  if ((d.cash || []).length || (d.cash_equivalents || []).length) {
    others.push(`<div class="panel"><h2>${hg('Cash')}</h2>${(d.cash || []).map((c) => `<p class="bkw-line">${esc(c.currency)} ${esc(bkMoney(c.amount, c.currency))}</p>`).join('')}
      ${(d.cash_equivalents || []).length ? `<p class="set-row-note">Includes ${esc(d.cash_equivalents.map((c) => c.symbol || c.description).join(', '))}, counted once as cash because your broker's cash balance already includes ${d.cash_equivalents.length === 1 ? 'it' : 'them'}.</p>` : ''}</div>`);
  }
  if ((d.unsupported || []).length) {
    others.push(`<div class="panel"><h2>${hg('Not counted')}</h2><ul class="bkw-list">${d.unsupported.map((u) => `<li><b>${esc(u.symbol || u.description)}</b> ${esc(u.account || '')}: ${esc(u.reason || '')}</li>`).join('')}</ul></div>`);
  }
  return `${table}
    ${bkwExposureHTML(d.exposure, d)}
    ${bkwScorecardHTML(BKW.extra.scorecard)}
    ${(d.options || []).length ? bkwOptionsHTML(BKW.extra.options, d.options) : ''}
    ${others.length ? `<div class="grid c2 bkw-grid">${others.join('')}</div>` : ''}
    ${bkwLimits(d.notes)}`;
}

function bkwShareRows(rows) {
  return (rows || []).map((r) => ({ label: r.label || r.key || r.name || 'Unclassified', value: Number(r.value_usd || r.value || 0), share_pct: r.share_pct === undefined ? r.weight_pct : r.share_pct }));
}

function bkwExposureHTML(e, d) {
  if (!e) return '';
  const sec = e.sectors || {};
  const look = BKW.sectors === 'look' && (sec.look_through || []).length;
  const sectorRows = bkwShareRows(look ? sec.look_through : (sec.direct_only || ((d.allocation || {}).by_sector || [])));
  const comp = e.companies || {};
  const companies = (comp.rows || []).slice(0, 12).map((c) => {
    const via = (c.via_funds || []).map((v) => `${esc(v.symbol || '')} ${esc(bkMoney(v.value_usd, 'USD'))}`).join(', ');
    return `<tr><td class="name"><b>${esc(c.ticker || '')}</b> <span class="bkw-meta">${esc(c.name && c.name !== c.ticker ? c.name : '')}</span></td>
      <td class="num">${esc(bkMoney(c.direct_usd || 0, 'USD'))}</td><td>${via || '<span class="bkw-meta">none</span>'}</td>
      <td class="num">${esc(bkMoney(c.total_usd || 0, 'USD'))}</td><td class="num">${bkwPct(c.share_pct)}</td></tr>`;
  }).join('');
  const status = { looked_through: 'looked through', no_source: 'no holdings source', leveraged: 'leveraged or inverse: not looked through' };
  const etfs = (e.etfs || []).map((f) => `<li><b>${esc(f.symbol)}</b> ${bkwPct(f.share_pct)} of your portfolio:
      ${f.status === 'looked_through' ? `holdings as of ${esc(bkwDate(f.report_date))} from ${esc(f.source || 'SEC Form N-PORT')}, ${bkwPct(f.coverage_pct)} of the fund itemised${f.stale ? ' (an older copy: SEC could not be reached)' : ''}`
    : esc(f.reason || status[f.status] || 'not looked through')}${f.leveraged || f.inverse ? ' <span class="set-tag warn">Leveraged or inverse</span>' : ''}</li>`).join('');
  const block = (title, part, note) => {
    const rows = (part && part.rows) || [];
    return rows.length ? `<div><h3 class="bkw-h3">${esc(title)}</h3>${bkBars(bkwShareRows(rows), 8)}<p class="set-row-note">${esc(note || part.basis || '')}</p></div>` : '';
  };
  return `<div class="panel span2"><h2>${hg('Exposure')}</h2>
    <p class="sub">${bkwSrc('optic')} Where your money sits, counting what your funds hold where Optic has their holdings. Look-through moves fund value onto the companies inside; it never adds to your total.</p>
    ${(comp.flags || []).length ? `<ul class="bkw-list">${comp.flags.slice(0, 4).map((f) => `<li>${esc(f)}</li>`).join('')}</ul>` : ''}
    <div class="grid c2 bkw-grid"><div>
      <div class="bkw-row"><h3 class="bkw-h3">Sectors</h3>
        <span class="seg" role="group" aria-label="Sector view"><button type="button" class="seg-opt${BKW.sectors === 'look' ? ' on' : ''}" data-bkw-sectors="look" aria-pressed="${BKW.sectors === 'look'}">With look-through</button><button type="button" class="seg-opt${BKW.sectors === 'direct' ? ' on' : ''}" data-bkw-sectors="direct" aria-pressed="${BKW.sectors === 'direct'}">Direct only</button></span></div>
      ${bkBars(sectorRows, 10)}
      <p class="set-row-note">${look ? `Look-through covers ${bkwPct(sec.coverage_pct)} of value${sec.unclassified_value ? `; ${esc(bkMoney(sec.unclassified_value, 'USD'))} has no sector from Yahoo` : ''}.` : 'Stocks held directly; each fund is one line.'}</p>
    </div><div>
      ${block('Asset class', e.asset_class)}
      ${block('Issuer country', e.issuer_country, 'Where the companies are organised or based, not where they earn their revenue.')}
      ${block('Pricing currency', e.currency, 'The currency each security is priced in, not its underlying economic currency exposure.')}
    </div></div>
    ${companies ? `<h3 class="bkw-h3">Companies, directly and through funds</h3>
      <div class="ss-scroll"><table class="data bk-table"><thead><tr><th>Company</th><th class="num">Direct</th><th>Through funds</th><th class="num">Total</th><th class="num">Share</th></tr></thead><tbody>${companies}</tbody></table></div>
      <p class="set-row-note">${esc(comp.no_double_counting || '')}</p>` : ''}
    ${etfs ? `<h3 class="bkw-h3">Funds</h3><ul class="bkw-list">${etfs}</ul>` : ''}
    ${bkwLimits(e.limitations)}</div>`;
}

function bkwScorecardHTML(s) {
  if (!s) return '<div class="panel span2"><h2>Optic scorecard</h2><p class="sub">Calculating the five assessments...</p></div>';
  if (s.error) return `<div class="panel span2"><h2>Optic scorecard</h2><p class="sub">${esc(s.error)}</p></div>`;
  const cards = (s.assessments || []).map((a) => {
    const drivers = (a.drivers || []).slice(0, 5).map((x) => esc(typeof x === 'string' ? x : `${x.symbol || x.label || ''}${x.weight_pct !== undefined && x.weight_pct !== null ? ` ${Number(x.weight_pct).toFixed(1)}%` : ''}${x.pulls ? ` (pulls ${x.pulls})` : ''}`)).join(', ');
    const missing = (a.not_assessed || []).slice(0, 8).map((x) => esc(typeof x === 'string' ? x : `${x.symbol || ''}: ${x.reason || x.why || ''}`)).join('; ');
    return `<div class="bkw-score">
      <div class="bkw-score-top"><span class="bk-k">${esc(a.label)}</span>${a.score === null || a.score === undefined ? '<span class="set-tag off">Not scored</span>' : `<span class="bkw-score-n">${Math.round(a.score)}</span>`}</div>
      <p class="bkw-level">${esc(a.level || '')}</p>
      ${a.score === null || a.score === undefined ? '' : `<span class="bk-bar-t" aria-hidden="true"><span class="bk-bar-f" style="width:${Math.max(2, Math.min(100, a.score))}%"></span></span>`}
      <p class="sub">${esc(a.summary || '')}</p>
      <p class="set-row-note">Coverage ${bkwPct(a.coverage_pct, 0)} of value.${drivers ? ` Driven by ${drivers}.` : ''}</p>
      ${missing ? `<p class="set-row-note">Not assessed: ${missing}.</p>` : ''}
      <details class="bkw-limits"><summary>Inputs and method</summary>
        <p>${esc(a.method || '')}</p>
        ${a.weights ? `<p>Weights: ${esc(typeof a.weights === 'string' ? a.weights : JSON.stringify(a.weights))}</p>` : ''}
        ${a.inputs ? `<p>Inputs: ${esc(typeof a.inputs === 'string' ? a.inputs : (Array.isArray(a.inputs) ? a.inputs.join(', ') : JSON.stringify(a.inputs)))}</p>` : ''}
        <p class="bkw-meta">${esc(a.version || s.version || '')}</p></details></div>`;
  }).join('');
  return `<div class="panel span2"><h2>${hg('Optic scorecard')}</h2>
    <p class="sub">${bkwSrc('optic')} Five separate assessments of the portfolio as it stands, each with what it is built from and what it could not assess. There is no overall score.</p>
    <div class="bkw-scores">${cards || '<p class="sub">No assessments could be made.</p>'}</div>
    <p class="set-row-note">${esc(s.disclaimer || 'These describe the portfolio today. They are not forecasts of return and not validated probabilities.')}</p></div>`;
}

function bkwOptionsHTML(o, raw) {
  if (!o) return '<div class="panel span2"><h2>Options risk</h2><p class="sub">Calculating Greeks...</p></div>';
  if (o.error || o.available === false) return `<div class="panel span2"><h2>Options risk</h2><p class="sub">${esc(o.error || o.reason || '')}</p></div>`;
  const pos = (o.positions || []).map((p) => `<tr><td class="name">${esc(p.underlying || '')} ${esc(String(p.strike || ''))} ${esc(p.option_type || p.type || '')} ${esc(p.expiry || '')}</td>
      <td class="num">${esc(String(p.contracts))}</td><td class="num">${p.iv === null || p.iv === undefined ? '<span class="bk-na">n/a</span>' : bkwPct(100 * p.iv, 1)}</td>
      <td class="num">${p.delta_shares === null || p.delta_shares === undefined ? 'n/a' : Number(p.delta_shares).toFixed(1)}</td>
      <td class="num">${p.theta_per_day === null || p.theta_per_day === undefined ? 'n/a' : bkSigned(p.theta_per_day, p.currency || 'USD')}</td>
      <td class="num">${p.vega_per_vol_point === null || p.vega_per_vol_point === undefined ? 'n/a' : esc(bkMoney(p.vega_per_vol_point, p.currency || 'USD'))}</td>
      <td>${esc([p.greeks_available === false ? (p.greeks_reason || 'No Greeks for this contract.') : '', (p.notes || []).join(' ')].filter(Boolean).join(' '))}</td></tr>`).join('');
  const under = (o.by_underlying || []).map((u) => `<li><b>${esc(u.underlying)}</b>: ${(u.legs_without_greeks || []).length && !u.complete
    ? `${esc(String(u.stock_shares || 0))} shares held; ${u.legs_without_greeks.length} option leg${u.legs_without_greeks.length === 1 ? '' : 's'} without Greeks, so no net delta is shown`
    : `net ${esc(Number(u.net_delta_shares || 0).toFixed(1))} share-equivalents (${esc(String(u.stock_shares || 0))} shares held)${u.theta_per_day === null || u.theta_per_day === undefined ? '' : `, theta ${bkSigned(u.theta_per_day, u.currency || 'USD')} a day`}`}</li>`).join('');
  const cons = (o.considerations || []).map((c) => `<li>${esc(typeof c === 'string' ? c : (c.text || c.note || ''))}</li>`).join('');
  return `<div class="panel span2"><h2>${hg('Options risk')}</h2>
    <p class="sub">${bkwSrc('optic')} Greeks from implied volatility solved from your broker's option price and Optic's underlying quote. Delta is in share-equivalents (positive gains when the underlying rises); theta and vega are in dollars.</p>
    <div class="ss-scroll"><table class="data bk-table"><thead><tr><th>Contract</th><th class="num">Contracts</th><th class="num">IV</th><th class="num">Delta (sh)</th><th class="num">Theta / day</th><th class="num">Vega / pt</th><th>Notes</th></tr></thead><tbody>${pos}</tbody></table></div>
    ${under ? `<h3 class="bkw-h3">By underlying</h3><ul class="bkw-list">${under}</ul>` : ''}
    ${cons ? `<h3 class="bkw-h3">Assignment and settlement</h3><ul class="bkw-list">${cons}</ul>` : ''}
    ${bkwLimits(o.limitations)}</div>`;
}

// ---------------------------------------------------------------- performance

function bkwPerformanceHTML(d) {
  const r = d.returns || {};
  const twr = r.twr || {};
  const mwr = r.mwr || {};
  const bench = r.benchmark || {};
  const period = d.period || {};
  const src = (d.sources || {}).values;
  const srcWords = { provider_estimate: 'SnapTrade\'s estimated daily balances', collected: 'snapshots Optic collected at each sync', mixed: 'SnapTrade\'s estimates, then Optic\'s own snapshots', none: 'no value history yet' }[src] || src || 'unknown';
  const controls = `<div class="bkw-row bkw-controls">
      <span class="seg" role="group" aria-label="Period">${BKW_PERIODS.map(([k, l]) => `<button type="button" class="seg-opt${BKW.period === k ? ' on' : ''}" data-bkw-period="${k}" aria-pressed="${BKW.period === k}">${l}</button>`).join('')}</span>
      <label class="bkw-inline">Benchmark <select data-bkw-bench>${BKW_BENCHMARKS.map(([k, l]) => `<option value="${k}"${BKW.bench === k ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select></label></div>`;
  const tile = (k, v, n) => `<div class="bk-tile"><span class="bk-k">${esc(k)}</span><span class="bk-v">${v}</span><span class="bk-n">${n}</span></div>`;
  const tiles = `<div class="bk-tiles">
    ${tile('Time-weighted return', bkwSignedPct(twr.pct), `${bkwSrc('optic')} The investments' own result, with deposits and withdrawals taken out.${twr.annualized ? ` Annualised ${bkwPct(twr.annualized_pct, 2, true)}.` : ' Not annualised: under a year.'}`)}
    ${tile('Money-weighted return', bkwSignedPct(mwr.period_pct), `${bkwSrc('optic')} Your own result, weighted by when you added or took out money.${mwr.irr_annualized_pct !== null && mwr.irr_annualized_pct !== undefined ? ` Annualised ${bkwPct(mwr.irr_annualized_pct, 2, true)}.` : ''}`)}
    ${tile(`Benchmark (${esc(bench.symbol || BKW.bench)})`, bkwSignedPct(bench.twr_pct), `${bkwSrc('market')} Total return with dividends reinvested, over the same dates.`)}
    ${tile('Difference', bkwSignedPct(r.excess_pct), `${bkwSrc('optic')} Your time-weighted return minus the benchmark's.`)}
  </div>`;
  const measured = period.measured_start ? `Measured ${esc(bkwDate(period.measured_start))} to ${esc(bkwDate(period.measured_end))} (${esc(String(period.days || ''))} days) from ${esc(srcWords)}.` : '';
  const flows = d.flows || {};
  const inc = d.income || {};
  const att = d.attribution || {};
  const attRows = (att.positions || []).slice(0, 10).map((x) => `<tr><td class="name">${esc(x.label || x.symbol || x.key || '')}</td><td class="num">${bkSigned(x.contribution, x.currency || d.currency || 'USD')}</td><td class="num">${bkwSignedPct(x.contribution_pct)}</td></tr>`).join('');
  const status = (d.data_status || []).map((s) => `<li><b>${esc(s.account)}</b>: transactions ${esc(s.transactions)}${s.first_transaction ? ` from ${esc(bkwDate(s.first_transaction))}` : ''}; balance history ${esc(s.balance_history)}</li>`).join('');
  const needsAddon = (d.data_status || []).some((s) => s.balance_history === 'unavailable');
  const enough = twr.pct !== null && twr.pct !== undefined;
  return `<div class="panel span2"><h2>${hg('Performance')}</h2>
    ${controls}
    ${enough ? `${tiles}<p class="set-row-note">${measured}</p>
      <h3 class="bkw-h3">Cumulative return, yours and the benchmark's</h3>
      <div class="bkw-chart" id="bkw-perf-chart" role="img" aria-label="Cumulative time-weighted return against the benchmark"></div>
      <h3 class="bkw-h3">Value and money put in ${bkwSrc('broker')}</h3>
      <div class="bkw-chart" id="bkw-perf-value" role="img" aria-label="Account value and cumulative net deposits"></div>
      <p class="set-row-note">The value line includes your own deposits and withdrawals, so it is not a return and is not compared with the benchmark.</p>`
    : `<p class="sub">${esc((d.limitations || [])[0] || 'There is not enough history yet to measure a return.')}</p>`}
  </div>
  <div class="grid c2 bkw-grid">
    <div class="panel"><h2>${hg('Money in and out')}</h2>
      <p class="sub">${bkwSrc('broker')} From your broker's transaction history.</p>
      <p class="bkw-line">Deposits ${esc(bkMoney(flows.deposits, d.currency || 'USD'))}</p>
      <p class="bkw-line">Withdrawals ${esc(bkMoney(flows.withdrawals, d.currency || 'USD'))}</p>
      <p class="bkw-line">Net ${bkSigned(flows.net_external, d.currency || 'USD')}</p>
      ${(flows.internal_transfers || {}).matched ? `<p class="set-row-note">${flows.internal_transfers.matched} transfer${flows.internal_transfers.matched === 1 ? '' : 's'} between your linked accounts (${esc(bkMoney(flows.internal_transfers.total, d.currency || 'USD'))}) left out: they move money between your own accounts, not in or out.</p>` : ''}
      ${(flows.unvalued || []).length ? `<p class="set-row-note">${flows.unvalued.length} transfer${flows.unvalued.length === 1 ? '' : 's'} of securities had no value from the broker; returns are not measured across ${flows.unvalued.length === 1 ? 'it' : 'them'}.</p>` : ''}
    </div>
    <div class="panel"><h2>${hg('Income and costs')}</h2>
      <p class="bkw-line">Dividends ${bkSigned(inc.dividends, d.currency || 'USD')}</p>
      <p class="bkw-line">Interest ${bkSigned(inc.interest, d.currency || 'USD')}</p>
      <p class="bkw-line">Fees paid ${esc(bkMoney(Math.abs(Number(inc.fees || 0)), d.currency || 'USD'))}</p>
      <p class="bkw-line">Taxes withheld ${esc(bkMoney(Math.abs(Number(inc.taxes || 0)), d.currency || 'USD'))}</p>
    </div>
  </div>
  <div class="panel span2"><h2>${hg('What drove it')}</h2>
    ${att.available ? `<p class="sub">${bkwSrc('optic')} Price effect on each position held through each pair of days Optic has a snapshot for, ${esc(bkwDate((att.window || {}).start))} to ${esc(bkwDate((att.window || {}).end))}.</p>
      <div class="ss-scroll"><table class="data bk-table"><thead><tr><th>Holding</th><th class="num">Contribution</th><th class="num">Of average capital</th></tr></thead><tbody>${attRows}</tbody></table></div>
      <p class="set-row-note">Contributions ${bkSigned(att.sum_contributions, d.currency || 'USD')}, money in or out ${bkSigned(att.flows, d.currency || 'USD')}, everything else ${bkSigned(att.remainder, d.currency || 'USD')}: together the change of ${bkSigned(att.total_change, d.currency || 'USD')}. ${esc(att.remainder_note || '')}</p>`
    : `<p class="sub">${esc(att.reason || 'Contributions need at least two of Optic\'s daily snapshots in the period. One is taken at every sync.')}</p>`}
  </div>
  <div class="panel span2"><h2>${hg('History this rests on')}</h2>
    ${status ? `<ul class="bkw-list">${status}</ul>` : ''}
    ${needsAddon ? '<p class="set-row-note">SnapTrade\'s balance-history add-on is off for these accounts. Switching it on in the SnapTrade dashboard (free) gives up to a year of estimated daily values; until then Optic measures from the snapshots it collects itself.</p>' : ''}
    ${bkwLimits(d.limitations, false)}
    <details class="bkw-limits"><summary>How these are calculated</summary>${Object.entries(d.definitions || {}).map(([k, v]) => `<p><b>${esc(k.replace(/_/g, ' '))}</b>: ${esc(typeof v === 'string' ? v : JSON.stringify(v))}</p>`).join('')}<p class="bkw-meta">${esc(d.version || '')}</p></details>
  </div>`;
}

function bkwMountPerformance(d) {
  if (typeof lineChart !== 'function' || typeof mount !== 'function') return;
  const series = (d.series || []).filter((p) => p.cum_twr_pct !== null && p.cum_twr_pct !== undefined);
  if (series.length < 2) return;
  const labels = series.map((p) => p.date);
  const lines = [{ name: 'Your time-weighted return', values: series.map((p) => p.cum_twr_pct), color: (typeof C !== 'undefined' && C.brand) || undefined }];
  if (series.some((p) => p.cum_benchmark_pct !== null && p.cum_benchmark_pct !== undefined)) {
    lines.push({ name: `${((d.returns || {}).benchmark || {}).symbol || BKW.bench} total return`, values: series.map((p) => (p.cum_benchmark_pct === undefined ? null : p.cum_benchmark_pct)), color: (typeof C !== 'undefined' && C.s7) || undefined });
  }
  mount('bkw-perf-chart', (w) => lineChart({ series: lines, labels, height: 220, width: w, zeroLine: true, yFormat: (v) => `${Number(v).toFixed(1)}%` }));
  const vals = (d.series || []).filter((p) => p.value !== null && p.value !== undefined);
  if (vals.length > 1) {
    let cum = 0;
    const net = vals.map((p) => { cum += Number(p.net_flow || 0); return cum; });
    const base = Number(vals[0].value) - net[0];
    mount('bkw-perf-value', (w) => lineChart({
      series: [{ name: 'Value', values: vals.map((p) => p.value), color: (typeof C !== 'undefined' && C.ink2) || undefined },
        { name: 'Starting value plus net deposits', values: net.map((n) => base + n), color: (typeof C !== 'undefined' && C.muted) || undefined }],
      labels: vals.map((p) => p.date), height: 180, width: w, yFormat: (v) => bkMoney(v, d.currency || 'USD'),
    }));
  }
}

// ---------------------------------------------------------- events & research

function bkwEventRows(list, compact) {
  if (!list || !list.length) return '<p class="sub">Nothing scheduled in the window for what you hold.</p>';
  const kind = { earnings: 'Earnings', ex_dividend: 'Ex-dividend', option_expiry: 'Option expiry' };
  return `<ul class="bkw-events">${list.map((e) => `<li>
      <span class="bkw-when">${esc(bkwDate(e.date))}<span class="bkw-meta">${e.days_away === 0 ? 'today' : `in ${e.days_away} day${e.days_away === 1 ? '' : 's'}`}</span></span>
      <span class="bkw-what"><b>${esc(e.symbol)}</b> ${esc(kind[e.kind] || e.kind)}
        ${e.kind === 'earnings' ? (e.confirmed ? '<span class="set-tag on">Confirmed</span>' : '<span class="set-tag warn">Estimated</span>') : ''}
        ${e.timing ? `<span class="bkw-meta">${e.timing === 'before_open' ? 'before the open' : 'after the close'}</span>` : ''}
        ${e.weight_pct ? `<span class="bkw-meta">${bkwPct(e.weight_pct)} of portfolio</span>` : ''}
        ${!compact && e.note ? `<span class="bkw-meta">${esc(e.note)}</span>` : ''}</span>
      ${!compact ? `<span class="bkw-links">${e.links && e.links.earnings ? `<a class="btn sm" href="${esc(e.links.earnings)}">Earnings analysis</a>` : ''}${e.links && e.links.overview ? `<a class="btn sm" href="${esc(e.links.overview)}">Dossier</a>` : ''}${e.links && e.links.options ? `<a class="btn sm" href="${esc(e.links.options)}">Options</a>` : ''}</span>` : ''}
    </li>`).join('')}</ul>`;
}

function bkwEventsHTML(d) {
  const cal = d.calendar || {};
  const sum = cal.summary || {};
  const desk = d.desk || {};
  const th = d.theses || {};
  const deskItems = (desk.items || []).map((i) => `<li><span><b>${esc(i.label || '')}</b>${i.value !== null && i.value !== undefined ? ` <span class="bkw-meta">${esc(String(i.value))}${i.unit ? esc(i.unit) : ''}</span>` : ''}</span>
      <span class="bkw-meta">${esc(i.why)}${(i.cited_in || []).length ? ` Cited in: ${esc(i.cited_in.join(', '))}.` : ''} ${esc(i.source || '')}</span>
      ${i.url ? `<a href="${esc(i.url)}" target="_blank" rel="noopener" class="bkw-meta">Source</a>` : ''}</li>`).join('');
  const deskHtml = `<div class="panel span2"><h2>${hg('Optic Desk, for your portfolio')}</h2>
    ${desk.available ? `<p class="sub">From the ${esc(desk.edition.slot_label || '')} edition of ${esc(bkwDate(desk.edition.date))}${desk.edition.is_today ? '' : ' (not today\'s)'}: "${esc(desk.edition.headline || '')}". These are the edition's own sources that touch what you hold; nothing was rewritten for you.</p>
      ${deskItems ? `<ul class="bkw-list">${deskItems}</ul>` : '<p class="sub">Nothing in this edition touches what you hold.</p>'}
      ${(desk.market_wide || []).length ? `<h3 class="bkw-h3">Market-wide, next three days</h3><ul class="bkw-list">${desk.market_wide.map((m) => `<li>${esc(m.label)} <span class="bkw-meta">${esc(bkwDate(m.event_at))}</span></li>`).join('')}</ul>` : ''}
      <p class="set-row-note"><a href="${esc(desk.link || '#/read')}" class="btn sm">Read the full edition</a></p>${bkwLimits(desk.limitations)}`
    : `<p class="sub">${esc(desk.reason || 'No edition is available.')}</p>`}</div>`;
  return `<div class="panel span2"><h2>${hg('Your calendar')}</h2>
      <p class="sub">${bkwSrc('market')} Earnings, ex-dividend dates and option expiries for what you hold, next ${esc(String(cal.window_days || 45))} days.
        Reporting in the next two weeks: ${bkwPct(sum.earnings_next_14d_pct)} of your portfolio (${bkwPct(sum.earnings_confirmed_next_14d_pct)} on confirmed dates).</p>
      ${bkwEventRows(cal.events || [], false)}
      ${bkwLimits(cal.limitations)}</div>
    ${bkwThesesHTML(th)}
    ${deskHtml}
    ${bkwAlertsHTML(d.alerts || {}, d.alert_settings || {}, d.alert_choices || {})}`;
}

const BKW_THESIS_FIELDS = [
  ['why', 'bull', 'Why I own it'], ['horizon', 'horizon', 'Horizon'], ['assumptions', 'assumptions', 'What I am assuming'],
  ['reassess_if', 'invalidation', 'What would make me reassess'], ['risks', 'bear', 'Risks I accept'], ['catalysts', 'catalysts', 'What I am watching for'],
];

function bkwThesesHTML(th) {
  const list = th.theses || [];
  const cards = list.map((t) => {
    if (BKW.thesisEdit === t.symbol) return bkwThesisForm(t);
    const devs = (t.developments || []).map((x) => `<li>${x.source_url ? `<a href="${esc(x.source_url)}" target="_blank" rel="noopener">${esc(x.title || '')}</a>` : esc(x.title || '')} <span class="bkw-meta">${esc(x.event_date || '')} ${esc(x.source_name || x.basis || '')}</span></li>`).join('');
    return `<div class="bkw-thesis">
      <div class="bkw-row"><h3 class="bkw-h3">${esc(t.symbol)} ${t.held ? `<span class="bkw-meta">${bkwPct(t.weight_pct)} of portfolio</span>` : '<span class="set-tag off">Not held</span>'}</h3>
        <span><button type="button" class="btn sm" data-bkw-thesis-edit="${esc(t.symbol)}">Edit</button>
        ${BKW.thesisArmed === t.symbol ? `<button type="button" class="btn sm bk-danger" data-bkw-thesis-del="${esc(t.symbol)}" data-confirm="1">Delete thesis</button>` : `<button type="button" class="btn sm" data-bkw-thesis-del="${esc(t.symbol)}">Delete</button>`}</span></div>
      ${BKW_THESIS_FIELDS.filter(([k]) => t[k]).map(([k, , label]) => `<p><span class="bk-k">${esc(label)}</span> ${esc(t[k])}</p>`).join('')}
      <p class="set-row-note">Saved ${esc(t.saved_at ? agoWords(t.saved_at) : 'n/a')}. Your words; Milo can comment on them but never changes them.</p>
      <h4 class="bkw-h4">Since you saved it</h4>
      ${devs ? `<ul class="bkw-list">${devs}</ul>` : '<p class="sub">Nothing new found in headlines, filings or the calendar.</p>'}
      ${bkwAskButton(`How does what has happened since I saved my ${t.symbol} thesis bear on it? My thesis: ${(t.why || '').slice(0, 300)}${t.reassess_if ? ` I said I would reassess if: ${t.reassess_if.slice(0, 200)}` : ''}`, 'Ask Milo about this thesis')}
    </div>`;
  }).join('');
  const missing = th.held_without_thesis || [];
  const adder = BKW.thesisEdit && !list.some((t) => t.symbol === BKW.thesisEdit) ? bkwThesisForm({ symbol: BKW.thesisEdit })
    : (missing.length ? `<p class="set-row-note">Write down why you own it: ${missing.slice(0, 12).map((s) => `<button type="button" class="btn sm" data-bkw-thesis-edit="${esc(s)}">${esc(s)}</button>`).join(' ')}</p>` : '');
  return `<div class="panel span2"><h2>${hg('Your theses')}</h2>
    <p class="sub">Why you own each position, in your own words, and what has happened since. Shared with the Dossier's thesis for the same symbol.</p>
    ${cards || '<p class="sub">No theses yet.</p>'}${adder}</div>`;
}

function bkwThesisForm(t) {
  return `<form class="bkw-thesis bkw-form" data-bkw-thesis-form="${esc(t.symbol)}">
    <h3 class="bkw-h3">${esc(t.symbol)}</h3>
    ${BKW_THESIS_FIELDS.map(([k, , label]) => `<label class="bkw-field"><span class="bk-k">${esc(label)}</span>
      ${k === 'horizon' ? `<input type="text" name="${k}" maxlength="200" value="${esc(t[k] || '')}" placeholder="For example: 3 to 5 years">`
    : `<textarea name="${k}" rows="2" maxlength="8000">${esc(t[k] || '')}</textarea>`}</label>`).join('')}
    <div class="set-row-act"><button type="submit" class="btn primary">Save thesis</button> <button type="button" class="btn" data-bkw-thesis-cancel>Cancel</button></div></form>`;
}

function bkwAlertsHTML(a, s, choices) {
  const list = (a.alerts || []).slice(0, 15).map((x) => `<li class="${x.seen ? '' : 'bkw-unseen'}"><span><b>${esc(x.title)}</b> <span class="bkw-meta">${esc(agoWords(x.created_at))}</span></span>
      <span class="bkw-meta">${esc(x.body || '')}</span>${x.link ? ` <a href="${esc(x.link)}" class="bkw-meta">Open</a>` : ''}</li>`).join('');
  const draft = BKW.alertDraft || JSON.parse(JSON.stringify(s));
  const sel = (path) => {
    const [k, f] = path.split('.');
    const opts = (choices[path] || []).map((v) => `<option value="${v}"${(draft[k] || {})[f] === v ? ' selected' : ''}>${v}</option>`).join('');
    return `<select data-bkw-alert="${path}" aria-label="${esc(path)}">${opts}</select>`;
  };
  const on = (k, label, extra) => `<label class="bkw-check"><input type="checkbox" data-bkw-alert="${k}.on"${(draft[k] || {}).on ? ' checked' : ''}> ${label}${extra ? ` ${extra}` : ''}</label>`;
  return `<div class="panel span2"><h2>${hg('Alerts')}</h2>
    <p class="sub">In Optic only, unless you turn on email below. Each situation is raised once, not on every visit.</p>
    ${list ? `<ul class="bkw-list">${list}</ul>` : '<p class="sub">No alerts yet.</p>'}
    <div class="set-row-act"><button type="button" class="btn" data-bkw-alerts-check>Check now</button>${a.unseen ? ' <button type="button" class="btn" data-bkw-alerts-seen>Mark all read</button>' : ''}</div>
    <details class="bkw-limits"><summary>Alert settings</summary>
      <div class="bkw-alert-set">
        ${on('earnings', 'A holding reports within', `${sel('earnings.days')} days`)}
        ${on('concentration', 'One holding passes', `${sel('concentration.single_pct')}% or one sector passes ${sel('concentration.sector_pct')}%`)}
        ${on('drift', 'A holding\'s weight moves', `${sel('drift.pp')} points in about a month`)}
        ${on('exposure', 'A sector\'s share moves', `${sel('exposure.pp')} points in about a month`)}
        ${on('thesis', 'Something new about a name with a thesis', '')}
        ${on('connection', 'A connection needs attention', '')}
        <label class="bkw-check"><input type="checkbox" data-bkw-alert="email"${draft.email ? ' checked' : ''}> Also email me a count of new alerts (nothing about holdings is put in the email)</label>
      </div>
      <div class="set-row-act"><button type="button" class="btn primary" data-bkw-alerts-save>Save alert settings</button></div>
    </details></div>`;
}

// ------------------------------------------------------------------ scenarios

function bkwScenariosHTML() {
  const sc = BKW.scenario;
  const held = ((BKW.data.overview || {}).top_holdings || []).map((h) => h.symbol).filter(Boolean);
  const rows = sc.rows.map((r, i) => `<div class="bkw-scen-row">
      <label class="bkw-field"><span class="bk-k">Symbol</span><input type="text" data-bkw-scen="${i}.symbol" value="${esc(r.symbol)}" maxlength="15" list="bkw-held" placeholder="NVDA" autocomplete="off"></label>
      <label class="bkw-field"><span class="bk-k">Change</span><select data-bkw-scen="${i}.action">${[['buy', 'Add'], ['sell', 'Reduce'], ['target_weight', 'Set weight to']].map(([k, l]) => `<option value="${k}"${r.action === k ? ' selected' : ''}>${l}</option>`).join('')}</select></label>
      <label class="bkw-field"><span class="bk-k">Amount</span><input type="number" step="any" min="0" data-bkw-scen="${i}.amount" value="${esc(String(r.amount))}"></label>
      <label class="bkw-field"><span class="bk-k">In</span><select data-bkw-scen="${i}.amount_type">${(r.action === 'target_weight' ? [['weight_pct', '% of portfolio']] : [['dollars', 'dollars'], ['shares', 'shares']]).map(([k, l]) => `<option value="${k}"${r.amount_type === k ? ' selected' : ''}>${l}</option>`).join('')}</select></label>
      <button type="button" class="btn sm" data-bkw-scen-del="${i}" aria-label="Remove this change">Remove</button></div>`).join('');
  return `<div class="panel span2"><h2>${hg('What-if lab')}</h2>
    <p class="sub">Try changes to your holdings and see what they would do to weights, concentration and historical risk. Nothing is traded: this is arithmetic on a copy.</p>
    <datalist id="bkw-held">${held.map((s) => `<option value="${esc(s)}">`).join('')}</datalist>
    ${rows}
    <div class="bkw-row bkw-controls"><button type="button" class="btn sm" data-bkw-scen-add>Add a change</button>
      <label class="bkw-inline">Paid for by <select data-bkw-scen-funding>${[['cash', 'cash in the accounts'], ['new_money', 'new money'], ['pro_rata', 'selling the rest evenly']].map(([k, l]) => `<option value="${k}"${sc.funding === k ? ' selected' : ''}>${l}</option>`).join('')}</select></label>
      <button type="button" class="btn primary" data-bkw-scen-run>Run</button></div>
    ${sc.error ? `<p class="sub">${esc(sc.error)}</p>` : ''}
    ${sc.running ? '<p class="sub">Working it out...</p>' : ''}
  </div>
  ${sc.result ? bkwScenarioResult(sc.result) : ''}`;
}

function bkwScenarioResult(r) {
  if (r.available === false) return `<div class="panel span2"><p class="sub">${esc(r.reason || 'The scenario could not be run.')}</p></div>`;
  const conc = r.concentration || {};
  const hist = r.history || {};
  const hb = hist.before || {};
  const ha = hist.after || {};
  const row = (label, b, a) => `<tr><td>${esc(label)}</td><td class="num">${b}</td><td class="num">${a}</td></tr>`;
  const money = (v) => esc(bkMoney(v, 'USD'));
  const num = (v) => (v === null || v === undefined ? 'n/a' : Number(v).toFixed(2));
  const histCell = (h, k, fmt) => (h.available ? fmt(h[k]) : '<span class="bk-na">n/a</span>');
  const weights = (r.weights || []).filter((w) => w.changed).slice(0, 15).map((w) => `<tr><td class="name">${esc(w.symbol)}</td><td class="num">${bkwPct(w.before_pct)}</td><td class="num">${bkwPct(w.after_pct)}</td><td class="num">${bkwSignedPct(w.change_pts, 1)}</td></tr>`).join('');
  const changes = (r.changes || []).filter((c) => c.status !== 'applied').map((c) => `<li><b>${esc(c.symbol)}</b>: ${esc(c.reason || c.status)}</li>`).join('');
  // look_through is a list when the fund holdings could be re-split after the
  // change, and {available: false, reason} when not; direct is always a list.
  const lt = (r.sectors || {}).look_through;
  const sectorList = Array.isArray(lt) ? lt : (((r.sectors || {}).direct) || []);
  const sectors = sectorList.filter((x) => Math.abs(x.change_pts || 0) >= 0.05)
    .map((x) => `<li>${esc(x.sector || x.label)} ${bkwPct(x.before_pct)} to ${bkwPct(x.after_pct)}</li>`).join('');
  const ltNote = lt && !Array.isArray(lt) && lt.reason ? `<p class="set-row-note">Sectors are shown for directly held stocks: ${esc(lt.reason)}</p>` : '';
  const stress = r.stress || {};
  return `<div class="panel span2"><h2>${hg('Before and after')}</h2>
    <p class="sub">${esc(r.funding_rule || '')}</p>
    <div class="ss-scroll"><table class="data bk-table"><thead><tr><th></th><th class="num">Now</th><th class="num">After</th></tr></thead><tbody>
      ${row('Total', money((r.total || {}).before), money((r.total || {}).after))}
      ${row('Cash', money((r.cash || {}).before), money((r.cash || {}).after))}
      ${row('Effective number of holdings', num((conc.before || {}).effective_holdings), num((conc.after || {}).effective_holdings))}
      ${row('Largest holding', bkwPct((conc.before || {}).top1_pct), bkwPct((conc.after || {}).top1_pct))}
      ${row('Largest five holdings', bkwPct((conc.before || {}).top5_pct), bkwPct((conc.after || {}).top5_pct))}
      ${row('Volatility over the past year (annualised)', histCell(hb, 'vol_pct', (v) => bkwPct(v)), histCell(ha, 'vol_pct', (v) => bkwPct(v)))}
      ${row('Beta to the S&P 500, past year', histCell(hb, 'beta', num), histCell(ha, 'beta', num))}
      ${row('Worst fall at these weights, past year', histCell(hb, 'max_drawdown_pct', (v) => bkwPct(v)), histCell(ha, 'max_drawdown_pct', (v) => bkwPct(v)))}
    </tbody></table></div>
    <p class="set-row-note">${esc(hist.label || '')}${hb.available ? '' : ` ${esc(hb.reason || '')}`}</p>
    ${weights ? `<h3 class="bkw-h3">Weights that change</h3><div class="ss-scroll"><table class="data bk-table"><thead><tr><th>Holding</th><th class="num">Now</th><th class="num">After</th><th class="num">Change</th></tr></thead><tbody>${weights}</tbody></table></div>` : ''}
    ${sectors ? `<h3 class="bkw-h3">Sectors that change</h3><ul class="bkw-list">${sectors}</ul>${ltNote}` : ''}
    ${stress.before ? `<p class="set-row-note">${esc(stress.label || '')}: ${bkwPct(stress.before.pct)} now, ${bkwPct((stress.after || {}).pct)} after.</p>` : ''}
    ${changes ? `<h3 class="bkw-h3">Not applied</h3><ul class="bkw-list">${changes}</ul>` : ''}
    ${(r.warnings || []).length ? `<ul class="bkw-list">${r.warnings.map((w) => `<li>${esc(w)}</li>`).join('')}</ul>` : ''}
    <details class="bkw-limits"><summary>Method</summary><p>${esc(r.method || '')}</p><p class="bkw-meta">${esc(r.version || '')}</p></details>
    ${bkwLimits(r.limitations)}</div>`;
}

async function bkwRunScenario() {
  const sc = BKW.scenario;
  const changes = sc.rows.filter((r) => String(r.symbol).trim() && String(r.amount).trim() !== '')
    .map((r) => ({ symbol: String(r.symbol).trim().toUpperCase(), action: r.action, amount_type: r.amount_type, amount: Number(r.amount) }));
  if (!changes.length) { sc.error = 'Add at least one change with a symbol and an amount.'; bkwPaintPanel(); return; }
  sc.error = null; sc.running = true; bkwPaintPanel();
  const r = await brokerFetch('POST', '/api/brokerage/workspace/scenario', { changes, funding: sc.funding, accounts: bkScopeIds() });
  sc.running = false;
  if (r.ok) sc.result = r.data;
  else sc.error = (r.data && r.data.detail) || 'The scenario could not be run.';
  bkwPaintPanel();
}

// ------------------------------------------------------------------- actions

function bkwToast(msg, tone) {
  if (window.OpticAuth && window.OpticAuth.toast) window.OpticAuth.toast(msg, tone);
}

async function bkwSaveThesis(form) {
  const sym = form.dataset.bkwThesisForm;
  const val = (k) => ((form.elements[k] || {}).value || '').trim();
  const body = {};
  BKW_THESIS_FIELDS.forEach(([k, apiKey]) => { body[apiKey] = val(k); });
  const r = await brokerFetch('PUT', `/api/theses/${encodeURIComponent(sym)}`, body);
  if (!r.ok) { bkwToast((r.data && r.data.detail) || 'Could not save that thesis.', 'bad'); return; }
  BKW.thesisEdit = null;
  delete BKW.data.events;
  bkwToast('Thesis saved.', 'good');
  bkWorkspaceLoad(false);
  bkwPaintPanel();
}

async function bkwClick(evt) {
  const host = views.brokerage;
  if (!host || !host.contains(evt.target)) return;
  const t = evt.target.closest('[data-bkw-tab], [data-bkw-go], [data-bkw-retry], [data-bkw-write], [data-bkw-sectors], [data-bkw-period], [data-bkw-scen-add], [data-bkw-scen-del], [data-bkw-scen-run], [data-bkw-thesis-edit], [data-bkw-thesis-cancel], [data-bkw-thesis-del], [data-bkw-alerts-check], [data-bkw-alerts-seen], [data-bkw-alerts-save]');
  if (!t) return;
  if (t.matches('[data-bkw-tab]')) { bkSetSection(t.dataset.bkwTab); return; }
  if (t.matches('[data-bkw-go]')) { bkSetSection(t.dataset.bkwGo); return; }
  if (t.matches('[data-bkw-retry]')) { BKW.error[bkwSection()] = null; bkWorkspaceLoad(true); bkwPaintPanel(); return; }
  if (t.matches('[data-bkw-sectors]')) { BKW.sectors = t.dataset.bkwSectors; bkwPaintPanel(); return; }
  if (t.matches('[data-bkw-period]')) { BKW.period = t.dataset.bkwPeriod; delete BKW.data.performance; bkwPaintPanel(); bkWorkspaceLoad(false); return; }
  if (t.matches('[data-bkw-write]')) {
    t.disabled = true;
    const r = await brokerFetch('POST', '/api/brokerage/workspace/briefing/written', { accounts: bkScopeIds() });
    t.disabled = false;
    if (!r.ok) { bkwToast((r.data && r.data.detail) || 'The briefing could not be written.', 'bad'); return; }
    if (BKW.extra.briefing) BKW.extra.briefing.written = r.data.written;
    bkwPaintPanel();
    return;
  }
  if (t.matches('[data-bkw-scen-add]')) {
    if (BKW.scenario.rows.length < 12) BKW.scenario.rows.push({ symbol: '', action: 'buy', amount_type: 'dollars', amount: '' });
    bkwPaintPanel(); return;
  }
  if (t.matches('[data-bkw-scen-del]')) {
    BKW.scenario.rows.splice(Number(t.dataset.bkwScenDel), 1);
    if (!BKW.scenario.rows.length) BKW.scenario.rows.push({ symbol: '', action: 'buy', amount_type: 'dollars', amount: '' });
    bkwPaintPanel(); return;
  }
  if (t.matches('[data-bkw-scen-run]')) { bkwRunScenario(); return; }
  if (t.matches('[data-bkw-thesis-edit]')) { BKW.thesisEdit = t.dataset.bkwThesisEdit; BKW.thesisArmed = null; bkwPaintPanel(); return; }
  if (t.matches('[data-bkw-thesis-cancel]')) { BKW.thesisEdit = null; bkwPaintPanel(); return; }
  if (t.matches('[data-bkw-thesis-del]')) {
    const sym = t.dataset.bkwThesisDel;
    if (!t.dataset.confirm) { BKW.thesisArmed = sym; bkwPaintPanel(); return; }
    const r = await brokerFetch('DELETE', `/api/theses/${encodeURIComponent(sym)}`);
    BKW.thesisArmed = null;
    if (!r.ok) bkwToast((r.data && r.data.detail) || 'Could not delete that thesis.', 'bad');
    delete BKW.data.events;
    bkWorkspaceLoad(false);
    bkwPaintPanel();
    return;
  }
  if (t.matches('[data-bkw-alerts-check]')) {
    t.disabled = true;
    const r = await brokerFetch('POST', '/api/brokerage/workspace/alerts/refresh', {});
    t.disabled = false;
    if (r.ok && BKW.data.events) BKW.data.events.alerts = r.data;
    bkwToast(r.ok ? `${r.data.new || 0} new alert${r.data.new === 1 ? '' : 's'}.` : 'Alerts could not be checked.', r.ok ? 'good' : 'bad');
    bkwPaintPanel(); return;
  }
  if (t.matches('[data-bkw-alerts-seen]')) {
    await brokerFetch('POST', '/api/brokerage/workspace/alerts/seen', {});
    if (BKW.data.events && BKW.data.events.alerts) {
      (BKW.data.events.alerts.alerts || []).forEach((x) => { x.seen = true; });
      BKW.data.events.alerts.unseen = 0;
    }
    bkwPaintPanel(); return;
  }
  if (t.matches('[data-bkw-alerts-save]')) {
    const r = await brokerFetch('PUT', '/api/brokerage/workspace/alerts/settings', BKW.alertDraft || {});
    if (!r.ok) { bkwToast((r.data && r.data.detail) || 'Those settings were not saved.', 'bad'); return; }
    if (BKW.data.events) BKW.data.events.alert_settings = r.data.settings;
    BKW.alertDraft = null;
    bkwToast('Alert settings saved.', 'good');
    bkwPaintPanel();
  }
}

function bkwChange(evt) {
  const host = views.brokerage;
  if (!host || !host.contains(evt.target)) return;
  const t = evt.target;
  if (t.matches('[data-bkw-scope]')) {
    bkwStore(BKW_SCOPE_KEY, t.value ? [t.value] : []);
    BKW.data = {}; BKW.extra = {}; BKW.error = {}; BKW.scenario.result = null;
    bkWorkspaceRender(host, bkFlashHtml());
    bkWorkspaceLoad(false);
    if (typeof updateChatContext === 'function') updateChatContext();
    return;
  }
  if (t.matches('[data-bkw-bench]')) { BKW.bench = t.value; delete BKW.data.performance; bkwPaintPanel(); bkWorkspaceLoad(false); return; }
  if (t.matches('[data-bkw-scen]')) {
    const [i, k] = t.dataset.bkwScen.split('.');
    const row = BKW.scenario.rows[Number(i)];
    if (!row) return;
    row[k] = t.value;
    if (k === 'action') { row.amount_type = t.value === 'target_weight' ? 'weight_pct' : 'dollars'; bkwPaintPanel(); }
    return;
  }
  if (t.matches('[data-bkw-scen-funding]')) { BKW.scenario.funding = t.value; return; }
  if (t.matches('[data-bkw-alert]')) {
    const base = (BKW.data.events && BKW.data.events.alert_settings) || {};
    BKW.alertDraft = BKW.alertDraft || JSON.parse(JSON.stringify(base));
    const path = t.dataset.bkwAlert;
    if (path === 'email') { BKW.alertDraft.email = t.checked; return; }
    const [k, f] = path.split('.');
    BKW.alertDraft[k] = BKW.alertDraft[k] || {};
    BKW.alertDraft[k][f] = f === 'on' ? t.checked : Number(t.value);
  }
}

function bkwInput(evt) {
  const t = evt.target;
  if (!t.matches || !t.matches('input[data-bkw-scen]')) return;
  const [i, k] = t.dataset.bkwScen.split('.');
  const row = BKW.scenario.rows[Number(i)];
  if (row) row[k] = t.value;
}

function bkwKeydown(evt) {
  const t = evt.target;
  if (!t.matches || !t.matches('[data-bkw-tab]')) return;
  const ids = BKW_SECTIONS.map((s) => s.id);
  const at = ids.indexOf(t.dataset.bkwTab);
  let next = null;
  if (evt.key === 'ArrowRight') next = ids[(at + 1) % ids.length];
  else if (evt.key === 'ArrowLeft') next = ids[(at - 1 + ids.length) % ids.length];
  else if (evt.key === 'Home') next = ids[0];
  else if (evt.key === 'End') next = ids[ids.length - 1];
  if (!next) return;
  evt.preventDefault();
  bkSetSection(next);
  const tab = document.getElementById(`bkw-tab-${next}`);
  if (tab) tab.focus();
}

function bkwSubmit(evt) {
  const form = evt.target.closest && evt.target.closest('[data-bkw-thesis-form]');
  if (!form) return;
  evt.preventDefault();
  bkwSaveThesis(form);
}

/* Settings' "Manage" names the section it opens; set before the view
 * switches, in the capture phase, so the workspace opens on Connections. */
function bkwCapture(evt) {
  const t = evt.target.closest && evt.target.closest('[data-bk-section]');
  if (t) bkSetSection(t.dataset.bkSection, true);
}

if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('click', bkwCapture, true);
  document.addEventListener('click', (evt) => { bkwClick(evt); });
  document.addEventListener('change', bkwChange);
  document.addEventListener('input', bkwInput);
  document.addEventListener('keydown', bkwKeydown);
  document.addEventListener('submit', bkwSubmit);
}
