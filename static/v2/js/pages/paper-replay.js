// Paper Desk, Replay a past decision (roadmap stage 7, 2026-10-22). A past chart from GET /api/replays/{id},
// revealed one completed session at a time: the server sends the bars up to the replay's session and nothing
// after, and the chart (ui/pricechart.js, the Chart tab's) computes its averages and RSI from those bars alone.
// At the session the setups engine flagged, the replay stops for the reader's decision, which is kept in this
// browser (optic.v2.replay.v1) and set beside the rule's reading and what followed in the review.
// Controls: Next session, Next 5, Play/Pause, and Review once the decision is made; arrow keys and Space too.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, signed, clean, fullDate, isNum, dir } from '../core/format.js';
import { failed, skeleton } from '../ui/states.js';
import { createPriceChart } from '../ui/pricechart.js';

export const REPLAY_KEY = 'optic.v2.replay.v1';
const PLAY_MS = 900;
let R = { lib: undefined, id: null, at: null, d: null, err: null, loading: false, playing: false, form: null };
let host = null, chart = null, timer = null, onOpen = null;

const readAll = () => { if (!holds(store.state.user)) return {}; try { return JSON.parse(localStorage.getItem(REPLAY_KEY) || '{}') || {}; } catch (e) { return {}; } };
const writeAll = (v) => { if (!holds(store.state.user)) return; try { localStorage.setItem(REPLAY_KEY, JSON.stringify(v)); } catch (e) { /* private mode: kept for this visit */ } };
let memo = null;
const attempts = (id) => ((memo || (memo = readAll()))[id] || []);
function keep(id, attempt) { memo = memo || readAll(); memo[id] = [...(memo[id] || []), attempt].slice(-10); writeAll(memo); }
const current = () => { const a = attempts(R.id); const last = a[a.length - 1]; return last && !last.reviewed ? last : null; };

/** What the reader's plan did over the revealed sessions after the decision. Pure, so a test can drive it. */
export function planResult(plan, bars, fromIdx) {
  if (!plan || plan.choice !== 'take' || !isNum(plan.entry) || !isNum(plan.stop)) return null;
  const long = plan.side !== 'short', e = Number(plan.entry), st = Number(plan.stop), tg = isNum(plan.target) ? Number(plan.target) : null;
  const risk = Math.abs(e - st);
  if (!risk) return null;
  let exit = null, how = 'was still open at the end', ambiguous = false, best = 0, worst = 0;
  for (let i = fromIdx + 1; i < bars.length; i += 1) {
    const b = bars[i], hitStop = long ? b.l <= st : b.h >= st, hitTarget = tg !== null && (long ? b.h >= tg : b.l <= tg);
    best = Math.max(best, ((long ? b.h - e : e - b.l)) / risk); worst = Math.min(worst, ((long ? b.l - e : e - b.h)) / risk);
    if (hitStop || hitTarget) {
      // one daily bar cannot say which came first; the stop is assumed, the cautious reading
      ambiguous = hitStop && hitTarget;
      exit = hitStop ? st : tg; how = hitStop ? `was stopped out on ${fullDate(new Date(b.t).toISOString().slice(0, 10))}` : `reached the target on ${fullDate(new Date(b.t).toISOString().slice(0, 10))}`;
      break;
    }
  }
  const last = bars[bars.length - 1].c, out = exit === null ? last : exit;
  return { r: (long ? out - e : e - out) / risk, how, ambiguous, best, worst };
}

function lib() {
  if (R.lib === undefined) return skeleton('rows', 3, 'Loading the replays');
  if (R.lib && R.lib.error) return failed('The replays', R.lib.error, { retry: 'replays' });
  return html`<ul class="rp-lib">${(R.lib.replays || []).map((r) => { const n = attempts(r.id).filter((a) => a.reviewed).length;
    return html`<li><div><b>${r.title}</b><p>${clean(r.question)}</p>${n ? html`<p class="asof">Replayed ${n === 1 ? 'once' : `${n} times`}; your reasoning is kept.</p>` : ''}</div>
      <button type="button" class="btn btn-sm" data-v2-rp-open="${r.id}">${n ? 'Replay again' : 'Start'}</button></li>`; })}</ul>
    <p class="asof">${clean(R.lib.scope || '')}</p>`;
}

function reading(rd, d) {
  if (!rd) return html`<p class="t-muted">The rule has no reading for this setup on this session.</p>`;
  const state = { triggered: 'Triggered', armed: 'Armed, waiting for its trigger', watching: 'Watching', invalidated: 'Invalidated', expired: 'Expired', inactive: 'Not set up' }[rd.status] || rd.status;
  return html`<p><b>The rule, reading only what is on the chart:</b> ${rd.label}, ${rd.direction === 'bear' ? 'falling' : 'rising'}: ${state}${rd.status_at ? ` (${fullDate(rd.status_at)})` : ''}.
    ${isNum(rd.trigger_level) ? `Trigger ${num(rd.trigger_level)}. ` : ''}${isNum(rd.invalidation) ? `Invalidated by a close ${rd.direction === 'bear' ? 'above' : 'below'} ${num(rd.invalidation)}.` : ''}</p>
    ${d.phase === 'decision' && (rd.checks || []).length ? html`<ul class="plain rp-checks">${rd.checks.map((c) => html`<li class="${c.passed ? 'up' : 'down'}">${c.passed ? 'Holds' : 'Not yet'}: ${clean(c.rule)}</li>`)}</ul>` : ''}`;
}

function decisionForm(d) {
  const f = R.form || {}, last = d.bars[d.bars.length - 1], rd = d.reading || {}, bear = rd.direction === 'bear';
  return html`<form class="rp-form" data-v2-rp-form><fieldset><legend class="t-h3">Your decision, before you see the next session</legend>
    <div class="seg" role="group" aria-label="Decision"><button type="button" data-v2-rp-choice="take" aria-pressed="${f.choice === 'take'}">Take it</button><button type="button" data-v2-rp-choice="pass" aria-pressed="${f.choice === 'pass'}">Pass</button></div>
    ${f.choice === 'take' ? html`<div class="rp-row"><label class="field"><span class="t-label">Side</span><select name="side"><option value="long" ${!bear ? 'selected' : ''}>Long</option><option value="short" ${bear ? 'selected' : ''}>Short</option></select></label>
      <label class="field"><span class="t-label">Entry</span><input name="entry" type="number" step="any" inputmode="decimal" value="${f.entry ?? last.c}"></label>
      <label class="field"><span class="t-label">Stop</span><input name="stop" type="number" step="any" inputmode="decimal" value="${f.stop ?? (isNum(rd.invalidation) ? rd.invalidation : '')}"></label>
      <label class="field"><span class="t-label">Target <small>optional</small></span><input name="target" type="number" step="any" inputmode="decimal" value="${f.target ?? ''}"></label></div>` : ''}
    <label class="field"><span class="t-label">Why, in a sentence or two</span><textarea name="why" rows="3" maxlength="600" placeholder="What you see, and what would prove you wrong">${f.why || ''}</textarea></label>
    <button type="submit" class="btn btn-primary" ${f.choice ? '' : 'disabled'}>Keep my decision</button></fieldset></form>`;
}

function review(d) {
  const a = current() || attempts(R.id)[attempts(R.id).length - 1];
  const dIdx = d.bars.length - 1 - d.review, res = a ? planResult(a, d.bars, dIdx) : null, ro = d.rule_outcome || {}, rd = d.at_decision || {};
  return html`<div class="rp-review" tabindex="-1" id="rp-review"><h3 class="t-h3">Review</h3>
    <div class="grid2"><div><p class="t-label">Your decision</p>${!a ? html`<p class="t-muted">No decision was kept for this replay.</p>` : html`
      <p><b>${a.choice === 'take' ? `${a.side === 'short' ? 'Short' : 'Long'} at ${num(a.entry)}, stop ${num(a.stop)}${isNum(a.target) ? `, target ${num(a.target)}` : ''}` : 'You passed.'}</b></p>
      ${a.why ? html`<blockquote class="rp-why">${a.why}</blockquote>` : html`<p class="t-muted">No reasoning written.</p>`}
      ${res ? html`<p>Over the next ${d.review} sessions it ${res.how}: <b class="${dir(res.r)}">${signed(res.r, 2, 'R')}</b>, in multiples of what the stop risked. At its best ${signed(res.best, 2, 'R')}, at its worst ${signed(res.worst, 2, 'R')}.${res.ambiguous ? ' One session touched both the stop and the target; daily bars cannot say which came first, so the stop is assumed.' : ''}</p>` : ''}`}</div>
      <div><p class="t-label">The rule's own outcome</p><p>${rd.label || 'The setup'} was ${rd.status || 'n/a'} at the decision${ro.state_then === 'armed' ? (ro.triggered ? ' and triggered later' : ' and never triggered') : ''}. ${ro.invalidated_on ? `It closed through its invalidation on ${fullDate(ro.invalidated_on)}.` : 'It never closed through its invalidation.'} ${isNum(ro.move_pct) ? html`After ${d.review} sessions the price had moved <b class="${dir(ro.move_pct)}">${signed(ro.move_pct, 2)}</b> in the setup's direction (${rd.direction === 'bear' ? 'a fall counts as a gain' : 'a rise counts as a gain'}) from the decision close; best ${signed(ro.best_pct, 1)}, worst ${signed(ro.worst_pct, 1)}.` : ''}</p></div></div>
    <p class="asof">${clean(d.revision || '')} One replay is one outcome: a sound decision can lose and a poor one can win, so judge the reasoning against what was knowable at the decision, which is all the chart showed you then.</p>
    <div class="cluster"><button type="button" class="btn btn-sm" data-v2-rp-again>Replay it again</button><a class="btn btn-sm" href="#/${encodeURIComponent(d.symbol)}/chart">${d.symbol} on the chart today</a><button type="button" class="btn btn-sm" data-v2-rp-close>Back to the replays</button></div></div>`;
}

function kept(a) {
  return html`<p class="rp-kept"><b>Your decision, kept from ${fullDate(a.through)}:</b> ${a.choice === 'take' ? `${a.side === 'short' ? 'short' : 'long'} at ${num(a.entry)}, stop ${num(a.stop)}${isNum(a.target) ? `, target ${num(a.target)}` : ''}` : 'pass'}.${a.why ? html` <span class="t-muted">${a.why}</span>` : ''}</p>`;
}
function controls(d) {
  const decided = !!current() || d.at > 0, atDecision = d.at === 0 && !decided, end = d.at >= d.review;
  const where = d.at < 0 ? `${-d.at} session${d.at === -1 ? '' : 's'} before the decision` : d.at === 0 ? 'The decision session' : `${d.at} of ${d.review} sessions after it`;
  return html`<div class="rp-ctl" role="group" aria-label="Replay controls">
    <button type="button" class="btn btn-sm" data-v2-rp-play ${atDecision || end || R.loading ? 'disabled' : ''} aria-pressed="${R.playing}">${R.playing ? 'Pause' : 'Play'}</button>
    <button type="button" class="btn btn-sm" data-v2-rp-step="1" ${atDecision || end || R.loading ? 'disabled' : ''}>Next session</button>
    <button type="button" class="btn btn-sm" data-v2-rp-step="5" ${atDecision || end || R.loading ? 'disabled' : ''}>Next 5</button>
    ${decided && !end ? html`<button type="button" class="btn btn-sm" data-v2-rp-review>Go to the review</button>` : ''}
    <span class="rp-where" aria-live="polite">${where}, through ${fullDate(d.through)}</span></div>`;
}

function body() {
  if (!R.id) return html`<h2 class="t-h2" id="rp-h">Replay a past decision</h2><p class="section-sub">A real chart from the past, one session at a time, stopping where Optic's setup rule flagged something, so you can decide before you see what came next.</p>${lib()}`;
  const d = R.d;
  const head = html`<div class="section-head"><h2 class="t-h2" id="rp-h">${d ? d.title : 'Replay'}</h2><button type="button" class="btn btn-sm btn-quiet" data-v2-rp-close>Back to the replays</button></div>`;
  if (R.err) return html`${head}${failed('This replay', R.err, { retry: 'replay' })}`;
  if (!d) return html`${head}${skeleton('lines', 4, 'Loading the replay')}`;
  return html`${head}<p class="section-sub">${clean(d.question)}</p>
    <div class="rp-chart" id="rp-chart" aria-label="${d.symbol} daily candles through ${fullDate(d.through)}"></div>
    ${controls(d)}${reading(d.reading, d)}
    ${d.phase === 'decision' && !current() ? decisionForm(d) : ''}${d.phase !== 'review' && current() ? kept(current()) : ''}${d.phase === 'review' ? review(d) : ''}
    <p class="asof">${clean(d.scope)} ${clean(d.revised)}</p>`;
}

function mountChart() {
  const el = host && host.querySelector('#rp-chart'), d = R.d;
  if (!el || !d) return;
  const a = current() || (d.phase === 'review' ? attempts(R.id)[attempts(R.id).length - 1] : null), rd = d.reading || {};
  const lines = [];
  if (isNum(rd.trigger_level)) lines.push({ price: rd.trigger_level, cls: 'fib', label: `Trigger ${num(rd.trigger_level)}` });
  if (isNum(rd.invalidation)) lines.push({ price: rd.invalidation, cls: rd.direction === 'bear' ? 'res' : 'sup', label: `Invalidation ${num(rd.invalidation)}`, below: true });
  if (a && a.choice === 'take') { if (isNum(a.stop)) lines.push({ price: a.stop, cls: 'sup', label: `Your stop ${num(a.stop)}`, below: true }); if (isNum(a.target)) lines.push({ price: a.target, cls: 'res', label: `Your target ${num(a.target)}` }); }
  const dIdx = d.decision_date ? d.bars.length - 1 - d.at : -1;
  const events = dIdx >= 0 ? [{ t: d.bars[dIdx].t, kind: 'Decision', label: 'The session the rule flagged, where the replay asked for your decision' }] : [];
  const phone = window.innerWidth < 640;
  chart = createPriceChart(el, { bars: d.bars, style: 'candles', overlays: { ma: true }, panes: { volume: true, rsi: false, macd: false }, lines, events,
    window: Math.min(d.bars.length, (phone ? 50 : 90) + Math.max(0, d.at)), label: `${d.symbol} replay`, height: phone ? 300 : 400 });
}

function paint() {
  if (!host || !host.isConnected) return;
  draw(host, body());
  mountChart();
}
async function load(id, at) {
  R.loading = true; R.err = null; paint();
  try { const d = await api.get(`/api/replays/${encodeURIComponent(id)}?at=${at}`, { ttl: 3600000, timeout: 60000 }); if (R.id !== id) return; R.d = d; R.at = d.at; }
  catch (e) { if (R.id !== id) return; R.err = e; R.playing = false; }
  R.loading = false; paint();
  if (R.d && R.d.phase === 'review') { const el = host.querySelector('#rp-review'); if (el) el.focus({ preventScroll: false }); }
}
function stop() { R.playing = false; clearTimeout(timer); }
async function advance(n) {
  if (!R.d || R.loading) return;
  const decided = !!current() || R.at > 0;
  let to = R.at + n;
  if (R.at < 0 && to > 0 && !decided) to = 0;            // the decision is never skipped
  to = Math.min(to, R.d.review);
  if (to === R.at) { stop(); paint(); return; }
  await load(R.id, to);
  if (R.d && (R.d.phase === 'decision' && !current())) stop();
  if (R.d && R.d.at >= R.d.review) stop();
}
function tick() { if (!R.playing) return; advance(1).then(() => { if (R.playing) timer = setTimeout(tick, PLAY_MS); else paint(); }); }

export async function loadLibrary() {
  if (R.lib && !R.lib.error) return;
  try { R.lib = await api.get('/api/replays', { ttl: 600000 }); } catch (e) { R.lib = { error: e }; }
  paint();
}
export function open(id) { stop(); R.id = id; R.d = null; R.form = null; R.err = null; if (onOpen) onOpen(id); load(id, -20); }
export function close() { stop(); R.id = null; R.d = null; if (onOpen) onOpen(null); paint(); }
export const retry = { replays: () => { R.lib = undefined; paint(); loadLibrary(); }, replay: () => load(R.id, R.at ?? -20) };

/** Mount the section into `el` (the Paper Desk calls this after each of its own paints). */
export function mount(el, { replay, onRoute } = {}) {
  host = el; onOpen = onRoute || null; memo = null;
  if (replay && replay !== R.id) { stop(); R.id = replay; R.d = null; R.form = null; load(replay, -20); }
  else if (!replay && R.id) { stop(); R.id = null; R.d = null; }
  paint();
  if (R.lib === undefined) loadLibrary();
  if (el._wired) return;
  el._wired = true;
  el.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-v2-rp-open]'))) { open(b.dataset.v2RpOpen); return; }
    if (t('[data-v2-rp-close]')) { close(); return; }
    if ((b = t('[data-v2-rp-choice]'))) { R.form = { ...(R.form || {}), choice: b.dataset.v2RpChoice }; paint(); return; }
    if ((b = t('[data-v2-rp-step]'))) { stop(); advance(Number(b.dataset.v2RpStep)); return; }
    if (t('[data-v2-rp-play]')) { if (R.playing) { stop(); paint(); } else { R.playing = true; paint(); tick(); } return; }
    if (t('[data-v2-rp-review]')) { stop(); load(R.id, R.d.review); return; }
    if (t('[data-v2-rp-again]')) { const a = current(); if (a) { a.reviewed = true; writeAll(memo); } R.form = null; load(R.id, -20); }
  });
  el.addEventListener('input', (e) => { const f = e.target.closest('[data-v2-rp-form]'); if (f && e.target.name) R.form = { ...(R.form || {}), [e.target.name]: e.target.value }; });
  el.addEventListener('submit', (e) => {
    if (!e.target.closest('[data-v2-rp-form]')) return;
    e.preventDefault();
    const f = e.target, v = (k) => (f[k] && f[k].value !== '' ? Number(f[k].value) : null), form = R.form || {};
    if (form.choice === 'take' && (!isNum(v('entry')) || !isNum(v('stop')))) { R.form = { ...form, why: f.why.value }; paint(); return; }
    keep(R.id, { at: new Date().toISOString(), through: R.d.through, choice: form.choice, side: f.side ? f.side.value : null, entry: v('entry'), stop: v('stop'), target: v('target'), why: (f.why.value || '').trim().slice(0, 600), reviewed: false });
    R.form = null; paint();
    const nx = host.querySelector('[data-v2-rp-step="1"]'); if (nx) nx.focus();
  });
  el.addEventListener('keydown', (e) => {
    if (!R.d || e.target.closest('input, textarea, select')) return;
    if (e.key === 'ArrowRight' && !e.target.closest('.pc')) { e.preventDefault(); stop(); advance(1); }
    if (e.key === ' ' && e.target.closest('[data-v2-rp-play]') === null && e.target.tagName !== 'BUTTON') { e.preventDefault(); if (R.playing) stop(); else { R.playing = true; tick(); } paint(); }
  });
}
export function dispose() { stop(); if (chart && chart.destroy) chart.destroy(); chart = null; host = null; }
