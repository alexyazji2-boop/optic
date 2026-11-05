// Dossier, Investigate this company (owner's Handoff 10, 2026-11-03): a fixed, visible checklist of six steps, each
// one Milo answer grounded in figures Optic has already read (app/investigation.py), then one summary the reader can
// edit and keep in Saved research. Reached from the Dossier's ⋯ menu and the Overview at #/SYM/investigate; a kept one
// reopens at #/SYM/investigate?saved=<id>.
//
// - Before anything runs: the steps, which the reader can skip or reorder, what each reads, the most it can cost
//   against their Milo allowance and the longest it can take. Start is the confirmation.
// - Steps run one at a time, each as it is reached. Stop, Skip, Retry and Re-run are the reader's; nothing retries
//   itself. A failed step leaves the others as they are.
// - Each step shows Optic's verified figures as Optic's own table, Milo's text with each figure cited, and, apart, what
//   could not be verified: a sentence whose figure matched none of the step's facts is moved there, never left in.
// - On a phone the steps are a progress list with the current one open.
import { html, raw, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import * as prefs from '../core/prefs.js';
import * as store from '../core/store.js';
import { clean, fullDate } from '../core/format.js';
import { icon } from '../ui/icons.js';
import { skeleton, failed } from '../ui/states.js';
import { openMilo, provideContext } from '../ui/milo.js';

export const STATE_WORDS = { pending: 'Waiting', running: 'Running', done: 'Done', skipped: 'Skipped', failed: 'Failed',
  stopped: 'Stopped' };
const STEP_TIMEOUT_MS = 135000;    // the server stops a step at 120 s; this waits a little longer for its answer
let S = {}, live = true, mainEl = null;
const wide = () => { try { return matchMedia('(min-width: 641px)').matches; } catch (e) { return true; } };
const enc = (s) => encodeURIComponent(s);

/* ---------------- what the page says before anything runs ---------------- */

/** Whether the investigation can start with `k` steps, and if not, why, in the reader's words. */
export function canStart(plan, k) {
  if (!plan) return { ok: false, why: 'The plan has not loaded.' };
  if (!(plan.ai || {}).enabled) return { ok: false, why: 'Milo cannot answer here right now, and each step is a Milo answer.' };
  const u = plan.usage || {};
  if (u.requires_account || !plan.signed_in) return { ok: false, why: 'Milo needs a free account. Sign in to run an investigation.', signin: true };
  if (k < 1) return { ok: false, why: 'Choose at least one step.' };
  if (u.enforced && typeof u.left === 'number' && u.left < k) {
    return { ok: false, why: `You have ${u.left} assistant message${u.left === 1 ? '' : 's'} left, and these steps need up to ${k}. Skip steps to fit, or come back when the allowance resets.` };
  }
  return { ok: true, why: '' };
}

/** The usage line: the most it can cost, and what is left. */
export function usageLine(plan, k) {
  const u = (plan || {}).usage || {};
  const most = `Uses up to ${k} assistant message${k === 1 ? '' : 's'}, one for each step that asks Milo.`;
  if (!u.enforced) return `${most} This account's Milo use is not counted against an allowance.`;
  if (typeof u.left !== 'number') return most;
  return `${most} You have ${u.left} left${u.plan ? ` on the ${u.plan} plan` : ''}.`;
}

function planView(sym) {
  const p = S.plan, k = S.order.filter((id) => !S.skip.has(id)).length, gate = canStart(p, k);
  const title = (id) => (p.steps.find((s) => s.id === id) || {}).title || id;
  return html`<section class="section gi-plan" aria-labelledby="gi-plan-h">
    <h2 class="t-h2" id="gi-plan-h">The checklist</h2>
    <p class="section-sub">Six fixed steps. Each asks Milo one question, answered only from figures Optic has already read, each with its source. Choose the steps and their order, then start.</p>
    <ol class="gi-plan-list">${S.order.map((id, i) => {
      const st = p.steps.find((s) => s.id === id) || {}, on = !S.skip.has(id);
      return html`<li class="gi-plan-item ${on ? '' : 'is-off'}">
        <label class="gi-check"><input type="checkbox" data-gi-include="${id}" ${on ? raw('checked') : ''}><span><b>${i + 1}. ${st.title}</b><small>${st.reads}</small></span></label>
        <span class="gi-move"><button type="button" class="icon-btn" data-gi-up="${id}" aria-label="Move ${st.title} up" ${i === 0 ? raw('disabled') : ''}>${icon('up')}</button><button type="button" class="icon-btn" data-gi-down="${id}" aria-label="Move ${st.title} down" ${i === S.order.length - 1 ? raw('disabled') : ''}>${icon('down')}</button></span>
      </li>`;
    })}</ol>
    <div class="gi-before" role="group" aria-labelledby="gi-before-h">
      <h3 class="t-h3" id="gi-before-h">Before you start</h3>
      <dl class="gi-kv">
        <div><dt>Steps</dt><dd>${k} of ${p.max_steps}${k < p.max_steps ? `, skipping ${S.order.filter((id) => S.skip.has(id)).map(title).join(', ')}` : ''}</dd></div>
        <div><dt>Milo usage</dt><dd>${usageLine(p, k)} ${clean((p.usage || {}).note || '')}</dd></div>
        <div><dt>Time</dt><dd>${clean(p.time_note || '')}</dd></div>
        <div><dt>Kept</dt><dd>${clean(p.keeps || '')}</dd></div>
      </dl>
      ${gate.ok ? '' : html`<p class="stale" role="status">${gate.why}${gate.signin ? html` <a class="textlink" href="#/signin">Sign in</a>` : ''}</p>`}
      ${S.startErr ? html`<p class="stale" role="alert">${clean(S.startErr.message || 'It did not start.')}</p>` : ''}
      <button type="button" class="btn btn-primary" data-gi-start ${gate.ok && !S.starting ? '' : raw('disabled')}>${S.starting ? 'Starting' : `Start investigation${k ? `, up to ${k} message${k === 1 ? '' : 's'}` : ''}`}</button>
    </div>
    <p class="asof disclaimer">${clean(p.disclaimer || '')}</p>
  </section>`;
}

/* ---------------- one step ---------------- */

/** Milo's text with each cited fact a button to its row. */
export function prose(text, step) {
  return String(text || '').split(/\n\s*\n/).filter((x) => x.trim()).map((para) => html`<p>${para.split(/(\[F\d+\])/).map((bit) => {
    const m = bit.match(/^\[(F\d+)\]$/);
    return m ? html`<button type="button" class="gi-cite" data-gi-fact="${step}-${m[1]}" aria-label="Fact ${m[1].slice(1)}, in the table below">${m[1]}</button>` : bit;
  })}</p>`);
}

const factDate = (iso) => (/^\d{4}-\d{2}-\d{2}/.test(String(iso || '')) ? fullDate(iso) : '');

function factsTable(res) {
  const facts = res.facts || [], texts = facts.filter((f) => f.kind === 'text'), figs = facts.filter((f) => f.kind !== 'text');
  return html`${texts.map((f) => html`<div class="gi-textfact" id="gi-${res.step}-${f.id}" tabindex="-1"><p class="t-label"><span class="gi-fid">${f.id}</span> ${f.label}</p><p>${clean(f.text)}</p><p class="asof">${clean([f.period, f.source].filter(Boolean).join('. '))}. Source ${f.source_n}.</p></div>`)}
    ${figs.length ? html`<div class="tscroll"><table class="t gi-facts"><caption class="sr">Figures Optic verified for ${res.title}</caption>
      <thead><tr><th scope="col">Figure</th><th scope="col" class="num">Value</th><th scope="col">Period</th><th scope="col">As of</th><th scope="col">Source</th></tr></thead>
      <tbody>${figs.map((f) => html`<tr id="gi-${res.step}-${f.id}" tabindex="-1"><th scope="row"><span class="gi-fid">${f.id}</span> ${f.label}${f.definition || f.formula ? html`<details class="gi-def"><summary>Definition</summary>${f.definition ? html`<p>${clean(f.definition)}</p>` : ''}${f.formula ? html`<p>Formula: ${clean(f.formula)}</p>` : ''}</details>` : ''}</th>
        <td class="num">${clean(f.text)}</td><td>${clean(f.period || '')}</td><td>${factDate(f.as_of) || 'Not dated'}</td><td>Source ${f.source_n}</td></tr>`)}</tbody></table></div>` : ''}`;
}

/** What could not be verified, in its own list: data the sources did not have, and Milo's sentences whose figures
 *  matched no fact (moved out of the answer, so they are never shown as verified). */
export function unverifiedList(items) {
  if (!(items || []).length) return html`<p class="t-muted">Nothing: every figure in this answer is one of the facts above.</p>`;
  return html`<ul class="gi-unv-list">${items.map((u) => html`<li>${u.kind === 'unmatched'
    ? html`Milo wrote “${clean(u.text)}” Optic found no source for ${u.figures.join(', ')}, so it was taken out of the answer.`
    : clean(u.text)}</li>`)}</ul>`;
}

export function sourceList(sources, cls = 'gi-sources') {
  return html`<ol class="${cls}">${(sources || []).map((s) => html`<li value="${s.n}">${s.url ? html`<a class="textlink" href="${s.url}" target="_blank" rel="noopener">${clean(s.name)}<span class="sr"> (opens in a new tab)</span></a>` : clean(s.name)}</li>`)}</ol>`;
}

export function stepBody(res) {
  if (!res || res.state === 'pending') return html`<p class="t-muted">Waiting for its turn.</p>`;
  if (res.state === 'skipped') return html`<p class="t-muted">Skipped. It is not in the summary, which says so.</p>`;
  if (res.state === 'running') return skeleton('lines', 3, `Reading Optic's figures for ${res.title || 'this step'}, then asking Milo`);
  if (res.state === 'stopped') return html`<p class="t-muted">Stopped before Milo answered. Run it again when you want it.</p>`;
  if (res.state === 'failed') return html`<p class="stale" role="status">${clean(res.why || 'This step did not finish.')} The other steps are unaffected.</p>`;
  return html`${res.no_data ? html`<p class="gi-nodata"><b>Not reported.</b> Optic has none of this step's figures for this company, so Milo was not asked and nothing was estimated.</p>` : html`<div class="gi-prose">${prose(res.text, res.step)}</div>`}
    ${res.removed ? html`<p class="asof">${res.removed} sentence${res.removed === 1 ? '' : 's'} that read as advice ${res.removed === 1 ? 'was' : 'were'} removed, as from every Milo answer.</p>` : ''}
    ${(res.facts || []).length ? html`<h3 class="t-h3 gi-sub">Verified figures</h3>${factsTable(res)}` : ''}
    <h3 class="t-h3 gi-sub">Could not verify</h3>${unverifiedList(res.unverified)}
    ${(res.sources || []).length ? html`<h3 class="t-h3 gi-sub">Sources</h3>${sourceList(res.sources)}` : ''}`;
}

const stateOf = (id) => {
  const inv = S.inv || {};
  if (S.current === id) return 'running';
  const r = (inv.steps || {})[id];
  if (r && r.state) return r.state;
  return (inv.skipped || []).includes(id) ? 'skipped' : 'pending';
};
const left = () => (S.inv ? S.inv.order.filter((id) => !(S.inv.skipped || []).includes(id) && !['done'].includes(stateOf(id))) : []);
const runnable = () => left().filter((id) => stateOf(id) === 'pending' || stateOf(id) === 'stopped');

function stepItem(id, i) {
  const inv = S.inv, res = (inv.steps || {})[id] || {}, st = stateOf(id), title = (S.plan.steps.find((s) => s.id === id) || {}).title || id;
  const open = S.open.has(id) ? S.open.get(id) : (wide() ? st !== 'pending' && st !== 'skipped' : id === S.focusStep);
  const busy = !!S.current;
  const acts = [];
  if (st === 'pending') acts.push(html`<button type="button" class="btn btn-sm btn-quiet" data-gi-skip="${id}">Skip<span class="sr"> ${title}</span></button>`);
  if (st === 'skipped') acts.push(html`<button type="button" class="btn btn-sm btn-quiet" data-gi-include-step="${id}">Include<span class="sr"> ${title}</span></button>`);
  if ((st === 'failed' || st === 'stopped') && !busy) acts.push(html`<button type="button" class="btn btn-sm" data-gi-retry="${id}">Retry<span class="sr"> ${title}</span></button>`);
  if (st === 'done' && !busy) acts.push(html`<button type="button" class="btn btn-sm btn-quiet" data-gi-retry="${id}">Run again<span class="sr"> ${title}</span></button>`);
  return html`<li class="gi-step" data-gi-step="${id}" data-state="${st}">
    <div class="gi-step-head">
      <span class="gi-state gi-state-${st}">${icon(st === 'done' ? 'check' : st === 'failed' ? 'flag' : st === 'running' ? 'history' : 'minus')}<span>${STATE_WORDS[st]}${st === 'done' && res.no_data ? ', not reported' : ''}</span></span>
      <h2 class="t-h3 gi-step-t" id="gi-h-${id}">${i + 1}. ${title}</h2>
      <span class="gi-step-acts">${acts}<button type="button" class="btn btn-sm btn-quiet gi-toggle" data-gi-toggle="${id}" aria-expanded="${open}" aria-controls="gi-b-${id}">${open ? 'Hide' : 'Show'}<span class="sr"> ${title}</span></button></span>
    </div>
    <div class="gi-step-body" id="gi-b-${id}" role="region" aria-labelledby="gi-h-${id}" ${open ? '' : raw('hidden')}>${stepBody(st === 'running' ? { state: 'running', title } : st === 'skipped' ? { state: 'skipped' } : st === 'pending' ? { state: 'pending' } : res)}</div>
  </li>`;
}

/* ---------------- the summary ---------------- */

/** Where an investigation stands, in words: complete, or partial and why. */
export function statusLine(inv) {
  const order = inv.order || [], steps = inv.steps || {}, skipped = order.filter((id) => (inv.skipped || []).includes(id));
  const done = order.filter((id) => (steps[id] || {}).state === 'done'), failedIds = order.filter((id) => (steps[id] || {}).state === 'failed');
  const notRun = order.filter((id) => !skipped.includes(id) && !done.includes(id) && !failedIds.includes(id));
  const name = (id) => TITLES[id] || id;
  if (!skipped.length && !failedIds.length && !notRun.length) return { partial: false, text: `Complete: all ${order.length} steps.` };
  const bits = [`Partial: ${done.length} of ${order.length} steps done.`];
  if (skipped.length) bits.push(`Skipped: ${skipped.map(name).join(', ')}.`);
  if (failedIds.length) bits.push(`Failed: ${failedIds.map(name).join(', ')}.`);
  if (notRun.length) bits.push(`Not run: ${notRun.map(name).join(', ')}.`);
  bits.push('The summary covers the steps done, and nothing is filled in for the others.');
  return { partial: true, text: bits.join(' ') };
}
const TITLES = { business: 'What the company does', health: 'Financial health', segments: 'Segments and company KPIs', peers: 'Peers', events: 'Recent events', risks: 'Risks and questions to check' };

/** Every step's sources once, numbered for the summary, with the steps that used each. */
export function combinedSources(inv) {
  const out = [];
  (inv.order || []).forEach((id) => {
    const r = (inv.steps || {})[id];
    if (!r || r.state !== 'done') return;
    (r.sources || []).forEach((s) => {
      let found = out.find((x) => x.name === s.name && (x.url || null) === (s.url || null));
      if (!found) { found = { n: out.length + 1, name: s.name, url: s.url || null, steps: [] }; out.push(found); }
      if (!found.steps.includes(TITLES[id])) found.steps.push(TITLES[id]);
    });
  });
  return out;
}

export function summaryHTML(inv, { editing = false, drafts = {}, notes = null } = {}) {
  const st = statusLine(inv), done = (inv.order || []).filter((id) => ((inv.steps || {})[id] || {}).state === 'done');
  const edits = inv.edits || {}, srcs = combinedSources(inv);
  const unv = done.map((id) => [id, ((inv.steps || {})[id] || {}).unverified || []]).filter(([, xs]) => xs.length);
  return html`<section class="section gi-summary" aria-labelledby="gi-sum-h">
    <h2 class="t-h2" id="gi-sum-h">Summary</h2>
    <p class="gi-status ${st.partial ? 'is-partial' : ''}">${st.partial ? html`<b>Partial.</b> ${st.text.replace(/^Partial: /, '')}` : st.text}</p>
    ${done.map((id) => {
      const r = inv.steps[id], text = edits[id] || r.text;
      return html`<div class="gi-sum-step"><h3 class="t-h3">${TITLES[id]}${edits[id] ? html` <small class="t-muted">Edited by you</small>` : ''}</h3>
        ${editing ? html`<label class="field gi-edit"><span class="sr">${TITLES[id]}, your words</span><textarea rows="5" data-gi-edit="${id}">${drafts[id] !== undefined ? drafts[id] : (text || '')}</textarea></label>`
          : r.no_data && !edits[id] ? html`<p class="t-muted">Not reported: Optic has none of this step's figures.</p>` : html`<div class="gi-prose">${prose(text, id)}</div>`}</div>`;
    })}
    ${editing ? html`<label class="field gi-edit"><span>Your notes</span><textarea rows="4" data-gi-notes>${notes !== null ? notes : inv.notes || ''}</textarea></label>`
      : inv.notes ? html`<div class="gi-sum-step"><h3 class="t-h3">Your notes</h3><p>${clean(inv.notes)}</p></div>` : ''}
    <div class="gi-sum-unv"><h3 class="t-h3">Could not verify</h3>
      ${unv.length ? unv.map(([id, xs]) => html`<p class="t-label">${TITLES[id]}</p>${unverifiedList(xs)}`) : html`<p class="t-muted">Nothing: every figure in the summary is one of the steps' verified figures.</p>`}</div>
    <div><h3 class="t-h3">Sources</h3>${srcs.length ? html`<ol class="gi-sources">${srcs.map((s) => html`<li value="${s.n}">${s.url ? html`<a class="textlink" href="${s.url}" target="_blank" rel="noopener">${clean(s.name)}<span class="sr"> (opens in a new tab)</span></a>` : clean(s.name)} <small class="t-muted">${s.steps.join(', ')}</small></li>`)}</ol>` : html`<p class="t-muted">No step used a source.</p>`}</div>
    <p class="asof disclaimer">Research, not investment advice. Nothing here recommends buying, selling or holding anything; check the figures and their sources before relying on them. Each figure's period and as-of date are in its step above.</p>
  </section>`;
}

function summaryActions(sym) {
  const inv = S.inv, saved = inv.status === 'saved', lead = runnable().length || S.current ? 'btn' : 'btn btn-primary';
  return html`<div class="gi-sum-acts">
    ${S.editing ? html`<button type="button" class="${lead}" data-gi-save-edits ${S.saving ? raw('disabled') : ''}>Save changes</button><button type="button" class="btn btn-quiet" data-gi-cancel-edits>Cancel</button>`
      : html`${saved ? '' : html`<button type="button" class="${lead}" data-gi-keep ${S.itemId && !S.saving ? '' : raw('disabled')}>Save to library</button>`}
        ${S.itemId ? html`<button type="button" class="btn" data-gi-edit-start>Edit summary</button>` : ''}
        <button type="button" class="btn" data-gi-follow>${icon('milo')}<span>Ask a follow-up</span></button>`}
    ${saved && !S.editing ? html`<p class="gi-saved" role="status">Saved to <a class="textlink" href="#/research?kind=investigation">Saved research</a> as “${inv.name}”.</p>` : ''}
    ${S.itemId ? '' : html`<p class="stale">${clean(S.keepNote || 'This investigation is not kept: leaving this page loses it.')}</p>`}
    ${S.saveErr ? html`<p class="stale" role="alert">${clean(S.saveErr.message || 'It was not saved.')}</p>` : ''}
  </div>`;
}

/* ---------------- the page ---------------- */

function runView(sym) {
  const inv = S.inv, done = inv.order.filter((id) => stateOf(id) === 'done').length, planned = inv.order.filter((id) => !(inv.skipped || []).includes(id)).length;
  const cur = S.current ? inv.order.indexOf(S.current) + 1 : 0;
  const words = S.current ? `Step ${cur} of ${inv.order.length}: ${TITLES[S.current]}, asking Milo.` : runnable().length ? `${done} of ${planned} steps done.${S.stopped ? ' Stopped.' : ''}` : `${done} of ${planned} steps done.`;
  return html`<section class="section gi-run" aria-labelledby="gi-run-h">
    <div class="section-head"><div><h2 class="t-h2" id="gi-run-h">Steps</h2>
      <p class="gi-progress" role="status" aria-live="polite">${words}</p></div>
      <div class="gi-run-acts">${S.current ? html`<button type="button" class="btn" data-gi-stop>Stop</button>`
        : runnable().length ? html`<button type="button" class="btn btn-primary" data-gi-continue>Continue, up to ${runnable().length} message${runnable().length === 1 ? '' : 's'}</button>` : ''}
        <button type="button" class="btn btn-quiet" data-gi-new ${S.current ? raw('disabled') : ''}>Start a new investigation</button></div></div>
    ${S.limitErr ? html`<p class="stale" role="alert">${clean(S.limitErr.message || 'Milo cannot answer more today.')} The steps done are kept; continue when the allowance allows.</p>` : ''}
    <div class="gi-meter" aria-hidden="true"><span style="width:${planned ? Math.round((done / planned) * 100) : 0}%"></span></div>
    <ol class="gi-steps">${inv.order.map((id, i) => stepItem(id, i))}</ol>
  </section>
  ${inv.order.some((id) => stateOf(id) === 'done') ? html`${summaryHTML(inv, { editing: S.editing, drafts: S.drafts, notes: S.notesDraft })}${summaryActions(sym)}` : ''}`;
}

function paint() {
  if (!live || !mainEl) return;
  const sym = S.sym;
  const was = document.activeElement, keyAttr = was && mainEl.contains(was) ? [...was.attributes].map((a) => a.name).find((n) => n.startsWith('data-gi-')) : null;
  const keyVal = keyAttr ? was.getAttribute(keyAttr) : null;
  const name = S.name && S.name !== sym ? `, ${S.name}` : '';
  let body;
  if (S.loadErr) body = failed('This investigation', S.loadErr, { retry: 'investigate' });
  else if (!S.plan || (S.savedId && !S.inv)) body = skeleton('rows', 6, 'Loading the investigation');
  else if (!S.inv) body = planView(sym);
  else body = runView(sym);
  draw(mainEl, html`<div class="gi-page"><header class="page-head gi-head"><a class="btn btn-quiet btn-sm" href="#/${enc(sym)}">${icon('chevL')}<span>Back to the ${sym} Dossier</span></a>
      <h1 class="t-display-m">Investigate ${sym}<span class="gi-name">${name}</span></h1>
      ${S.inv ? html`<p class="t-muted">${S.inv.name || ''}${S.itemId ? (S.inv.status === 'saved' ? ', saved' : ', kept as a draft in Saved research') : ''}</p>` : ''}</header>${body}</div>`);
  if (keyAttr) {
    const el = [...mainEl.querySelectorAll(`[${keyAttr}]`)].find((x) => x.getAttribute(keyAttr) === keyVal) || mainEl.querySelector(`[${keyAttr}]`);
    if (el && !el.disabled) el.focus({ preventScroll: true });
  }
}

/* ---------------- running ---------------- */

async function runStep(id) {
  const ctrl = typeof AbortController === 'function' ? new AbortController() : null;
  S.ctrl = ctrl; S.current = id; S.focusStep = id; S.limitErr = null; paint();
  try {
    const r = await api.post(`/api/investigate/${enc(S.sym)}/step`, { step: id, item_id: S.itemId || undefined, level: S.inv.level,
      order: S.inv.order, earlier: S.itemId ? undefined : earlierOf(id) }, { timeout: STEP_TIMEOUT_MS, signal: ctrl ? ctrl.signal : undefined });
    S.inv.steps[id] = r.result;
  } catch (e) {
    if (e.kind === 'cancelled') S.inv.steps[id] = { step: id, state: 'stopped' };
    else if (e.kind === 'limit' || e.kind === 'auth') { S.limitErr = e; delete S.inv.steps[id]; S.stopped = true; }
    else S.inv.steps[id] = { step: id, title: TITLES[id], state: 'failed', why: e.kind === 'timeout' ? 'Milo took too long to answer this step.' : `This step did not finish: ${e.message || 'no answer'}.` };
  }
  S.ctrl = null; S.current = null; paint();
}

/** For a run that is not kept: what the earlier steps could not verify, sent with the risk step. */
function earlierOf(id) {
  const order = S.inv.order;
  return order.slice(0, order.indexOf(id)).flatMap((x) => (((S.inv.steps || {})[x] || {}).unverified || []).map((u) => u.text)).slice(0, 20);
}

async function run() {
  if (S.current) return;
  S.stopped = false;
  for (const id of S.inv.order) {
    if (!live || S.stopped) break;
    const st = stateOf(id);
    if (st !== 'pending' && st !== 'stopped') continue;
    await runStep(id);
  }
  // the last finished step is the one open on a phone, so the reader sees where it ended
  S.focusStep = S.inv.order.filter((x) => stateOf(x) === 'done').pop() || S.focusStep;
  paint();
}

async function patch(body) {
  if (!S.itemId) return null;
  try { const r = await api.patch(`/api/investigate/item/${enc(S.itemId)}`, body, { timeout: 20000 }); if (r && r.investigation) { const steps = S.inv.steps; S.inv = Object.assign(r.investigation, { steps: Object.assign({}, r.investigation.steps, steps) }); } return r; }
  catch (e) { S.saveErr = e; return null; }
}

async function start() {
  S.starting = true; S.startErr = null; paint();
  try {
    const r = await api.post(`/api/investigate/${enc(S.sym)}`, { order: S.order, skip: [...S.skip], level: prefs.knowledge() }, { timeout: 20000 });
    S.inv = Object.assign({ steps: {} }, r.investigation); S.itemId = r.item_id; S.keepNote = r.note;
    // the address now reopens this one, without a redraw
    if (S.itemId) { try { history.replaceState(null, '', `#/${enc(S.sym)}/investigate?saved=${enc(S.itemId)}`); } catch (e) { /* tests */ } }
  } catch (e) { S.startErr = e; }
  S.starting = false; paint();
  if (S.inv) run();
}

function wire(main) {
  if (main.dataset.giWired) return;
  main.dataset.giWired = '1';
  main.addEventListener('change', (e) => {
    const c = e.target.closest('[data-gi-include]');
    if (c) { if (c.checked) S.skip.delete(c.dataset.giInclude); else S.skip.add(c.dataset.giInclude); paint(); }
  });
  main.addEventListener('input', (e) => {
    const t = e.target.closest('[data-gi-edit]'); if (t) { S.drafts[t.dataset.giEdit] = t.value; return; }
    if (e.target.closest('[data-gi-notes]')) S.notesDraft = e.target.value;
  });
  main.addEventListener('click', async (e) => {
    const t = (s) => e.target.closest(s); let b;
    if ((b = t('[data-gi-up]')) || (b = t('[data-gi-down]'))) {
      const id = b.dataset.giUp || b.dataset.giDown, i = S.order.indexOf(id), j = b.dataset.giUp ? i - 1 : i + 1;
      if (j >= 0 && j < S.order.length) { [S.order[i], S.order[j]] = [S.order[j], S.order[i]]; paint(); }
      return;
    }
    if (t('[data-gi-start]')) { start(); return; }
    if (t('[data-gi-stop]')) { S.stopped = true; if (S.ctrl) S.ctrl.abort(); patch({ stopped: true }); return; }
    if (t('[data-gi-continue]')) { run(); return; }
    if ((b = t('[data-gi-retry]'))) { if (!S.current) { const id = b.dataset.giRetry; delete S.inv.steps[id]; await runStep(id); } return; }
    if ((b = t('[data-gi-skip]'))) { const id = b.dataset.giSkip; S.inv.skipped = [...new Set([...(S.inv.skipped || []), id])]; paint(); patch({ skip: S.inv.skipped }); return; }
    if ((b = t('[data-gi-include-step]'))) { const id = b.dataset.giIncludeStep; S.inv.skipped = (S.inv.skipped || []).filter((x) => x !== id); paint(); patch({ skip: S.inv.skipped }); return; }
    if ((b = t('[data-gi-toggle]'))) { const id = b.dataset.giToggle; const open = b.getAttribute('aria-expanded') !== 'true'; S.open.set(id, open); paint(); return; }
    if ((b = t('[data-gi-fact]'))) { const row = document.getElementById(`gi-${b.dataset.giFact}`); if (row) { row.scrollIntoView({ block: 'center' }); row.focus({ preventScroll: true }); } return; }
    if (t('[data-gi-new]')) { S.inv = null; S.itemId = null; S.savedId = null; S.open = new Map(); S.editing = false; try { history.replaceState(null, '', `#/${enc(S.sym)}/investigate`); } catch (err) { /* tests */ } paint(); return; }
    if (t('[data-gi-keep]')) { S.saving = true; S.saveErr = null; paint(); await patch({ status: 'saved', name: S.inv.name }); S.saving = false; paint(); return; }
    if (t('[data-gi-edit-start]')) { S.editing = true; S.drafts = {}; S.notesDraft = null; paint(); const f = mainEl.querySelector('[data-gi-edit]'); if (f) f.focus(); return; }
    if (t('[data-gi-cancel-edits]')) { S.editing = false; paint(); return; }
    if (t('[data-gi-save-edits]')) {
      S.saving = true; paint();
      const body = { edits: S.drafts }; if (S.notesDraft !== null) body.notes = S.notesDraft;
      await patch(body); S.saving = false; S.editing = false; paint(); return;
    }
    if ((b = t('[data-gi-follow]'))) { openMilo({ opener: b, symbol: S.sym, about: `Investigation of ${S.sym}` }); }
  });
}

/** What Milo is given for a follow-up asked from this page: the steps as written (as the reader edited them), their
 *  verified figures and what could not be verified. Read when the reader sends, never before. */
export function contextOf(inv) {
  if (!inv) return null;
  const steps = (inv.order || []).filter((id) => ((inv.steps || {})[id] || {}).state === 'done').map((id) => {
    const r = inv.steps[id];
    return { step: TITLES[id], text: ((inv.edits || {})[id] || r.text || '').replace(/\s*\[F\d+\]/g, ''),
      figures: (r.facts || []).slice(0, 12).map((f) => ({ label: f.label, value: f.text, period: f.period, as_of: f.as_of, source: f.source })),
      could_not_verify: (r.unverified || []).map((u) => u.text).slice(0, 8) };
  });
  return { name: inv.name, status: statusLine(inv).text, steps, notes: inv.notes || '' };
}

// Not kept (Saved research full): the tab warns before it closes on finished steps, as the page says above them
const guard = (e) => { if (live && S.inv && !S.itemId && Object.values(S.inv.steps || {}).some((r) => r && r.state === 'done')) { e.preventDefault(); e.returnValue = ''; } };

export async function render(main, route) {
  live = true; mainEl = main;
  try { window.removeEventListener('beforeunload', guard); window.addEventListener('beforeunload', guard); } catch (e) { /* tests */ }
  const sym = route.symbol, savedId = (route.params || {}).saved || null;
  S = { sym, savedId, plan: null, order: [], skip: new Set(), inv: null, itemId: null, open: new Map(), drafts: {}, notesDraft: null,
    editing: false, current: null, stopped: false };
  document.title = `Investigate ${sym}, Optic`;
  provideContext(() => ({ view: 'investigate', ticker: sym, investigation: contextOf(S.inv) }));
  wire(main);
  paint();
  api.get(`/api/quote/${enc(sym)}`, { ttl: 20000, timeout: 15000 }).then((d) => { if (S.sym === sym) { S.name = ((d || {}).quote || d || {}).name || null; paint(); } }, () => {});
  try {
    S.plan = await api.get(`/api/investigate/${enc(sym)}/plan`, { ttl: 0, force: true, timeout: 20000 });
    S.order = S.plan.steps.map((s) => s.id);
    if (savedId && !store.signedIn()) S.loadErr = new api.ApiError('auth', 401, 'Sign in to open a kept investigation');
    if (savedId && store.signedIn()) {
      const r = await api.get(`/api/investigate/item/${enc(savedId)}`, { ttl: 0, force: true, timeout: 20000 });
      S.inv = Object.assign({ steps: {} }, r.investigation); S.itemId = savedId;
      S.focusStep = S.inv.order.filter((x) => stateOf(x) === 'done').pop() || S.inv.order[0];
    }
  } catch (e) { if (S.sym === sym) S.loadErr = e; }
  if (S.sym === sym) paint();
}

/** Leaving with a step running: it is stopped, as Stop would. A kept one is in Saved research to come back to. */
export function dispose() {
  live = false;
  if (S.ctrl) S.ctrl.abort();
  try { window.removeEventListener('beforeunload', guard); } catch (e) { /* tests */ }
}
export const retry = { investigate: (main, route) => render(main, route) };
export const _test = { state: () => S, set: (o) => { S = Object.assign(S || {}, o); }, stepItem, runView, planView };
