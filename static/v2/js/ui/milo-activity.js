// What Milo is doing, said in his own states, from the server's own events.
//
// The panel used to show one grey line of status text ("Thinking it through...") and a sliding bar. The states
// below give the same information as the mascot already in the panel doing the matching thing, with the line
// underneath. Nothing here invents a step: every state change comes from an event app/ai.py actually sends
// (stream_chat), so a question answered with no lookup shows Thinking then Writing and never Researching.
//
//   thinking     the question has gone and the model has it: `status thinking`, or a round starting with
//                nothing fetched yet (`status writing`, which the server sends as each model round begins)
//   researching  the server says it is fetching: a tool's own words ("Checking NVDA's options data"), a web
//                search, or the server gathering the page's figures; `retrieved` names what came back
//   analyzing    a model round started AFTER at least one lookup returned and before any text: the model is
//                working on what it got. Without a lookup this state never appears
//   writing      the first `delta`. Text is arriving and the answer itself has the reader's attention
//   complete     `done`
//   error        an `error` event, or the stream ending with no text
//   cancelled    the reader pressed Stop
//
// A tool call can happen after text has started (the model asks for one more figure mid-answer), so writing ->
// researching is allowed and honest; it is the same loop, going round again.
//
// The view is in two sizes, as the owner's reference sheet has it: an expanded card while there is no text yet
// and the panel is wide enough, and the compact line everywhere else. Both draw the same mascot
// (components/scout.js), so the character is the one rendered for the app, never a drawing of him.
import { esc } from '../core/format.js';

/** Server status strings that mean the model itself is working, not a lookup. */
const MODEL_STEPS = new Set(['thinking', 'writing']);
/** Server status strings for a web search (components/scout.js looks around for these). */
export const SEARCH_STEPS = new Set(['searching the web', 'searching', 'reading results', 'reading and weighing sources']);
/** A status that is a problem report rather than a step: it must not move the state. */
const NOT_A_STEP = /^some files were not sent/i;

// title: the heading the reader sees. line: what it says when the server has given no words of its own.
// scout: the mascot state (components/scout.js POSE), prop: the drawing beside him.
export const ACTIVITY = {
  thinking: { title: 'Thinking', line: 'Understanding your question', scout: 'thinking', prop: 'bubble' },
  researching: { title: 'Researching', line: 'Looking through Optic’s data', scout: 'researching', prop: null },
  analyzing: { title: 'Analyzing', line: 'Connecting what came back', scout: 'analyzing', prop: null },
  writing: { title: 'Writing', line: 'Putting it together', scout: 'writing', prop: null },
  complete: { title: 'Answer ready', line: 'Here’s what I found', scout: 'idle', prop: 'done' },
  error: { title: 'No answer', line: 'Milo could not finish this one', scout: 'error', prop: null },
  cancelled: { title: 'Stopped', line: 'Stopped by you', scout: 'idle', prop: null },
  idle: { title: '', line: '', scout: 'idle', prop: null },
};

/** The record the panel keeps for one answer. `said` is the server's own words for the step it is on. */
export const begin = (deep = false) => ({ state: 'thinking', said: '', fetched: [], text: false, deep: !!deep });

/**
 * The next record after one event. Pure: same record in, same record out, no DOM, no clock.
 * `kind` is submitted | status | retrieved | delta | done | error | cancelled.
 */
export function on(a, kind, payload) {
  if (!a) return a;
  const put = (state, said) => (a.state === state && (said === undefined || said === a.said) ? a
    : { ...a, state, said: said === undefined ? a.said : said });
  if (kind === 'status') {
    const raw = String((payload && payload.state) || '');
    if (!raw || NOT_A_STEP.test(raw)) return a;
    if (SEARCH_STEPS.has(raw)) return put('researching', raw);
    if (!MODEL_STEPS.has(raw)) return put('researching', raw);     // a tool's own words, or `gathering`
    // The model itself. Before any text: Analyzing once something has actually been fetched for this answer,
    // Thinking otherwise. After text has started, a new round is still the answer being written.
    if (a.text) return put('writing', '');
    return put(a.fetched.length ? 'analyzing' : 'thinking', '');
  }
  if (kind === 'retrieved') {
    const items = (Array.isArray(payload) ? payload : []).filter((r) => r && r.ok !== false)
      .map((r) => String(r.label || (r.symbols || []).join(', ') || '')).filter(Boolean);
    const fetched = [...new Set(items)];
    if (fetched.length === a.fetched.length && fetched.every((x, i) => x === a.fetched[i])) return a;
    return { ...a, fetched, state: a.text ? a.state : 'researching' };
  }
  if (kind === 'delta') return a.text && a.state === 'writing' ? a : { ...a, state: 'writing', said: '', text: true };
  if (kind === 'done') return put('complete', '');
  if (kind === 'error') return put('error', '');
  if (kind === 'cancelled') return put('cancelled', '');
  return a;
}

/** The heading and line for a record: the server's own words win over the state's default. */
export function words(a, stepWords) {
  const spec = ACTIVITY[a.state] || ACTIVITY.idle;
  const said = a.said && stepWords ? stepWords(a.said) : a.said;
  return { title: spec.title, line: said || spec.line, scout: spec.scout, prop: spec.prop };
}

/* ---------------- the two drawings beside him ----------------
 * The thing Milo works with in Researching, Analyzing and Writing is rendered in the frame itself: he is at
 * the desk with the laptop, holding the tablet, writing in the notebook (static/scout, FRAMES in
 * optic-brand/scout/render_scout.py). What has no pose of its own is a thought bubble while he reads the
 * question and the sparkles when the answer lands, and those two are drawn here in Optic's line work, in the
 * brand gold, with their motion declared in CSS (components.css) so Reduce motion stops it in one place.
 * aria-hidden: the heading and the line carry the meaning. */
const PROPS = {
  // A thought bubble with the logo's own chart line drawing itself inside it.
  bubble: `<svg viewBox="0 0 48 40" class="prop prop-bubble" aria-hidden="true" focusable="false">
    <circle cx="7" cy="34" r="2.4"/><circle cx="13" cy="28" r="3.4"/>
    <rect x="17" y="3" width="29" height="22" rx="7"/>
    <path class="draw" d="M23 18.5l4.6-5.2 3.2 2.6 4.6-7 3.4 3.1"/></svg>`,
  // Three sparkles, once.
  done: `<svg viewBox="0 0 40 40" class="prop prop-done" aria-hidden="true" focusable="false">
    <path class="s1" d="M10 8l1.6 4.4L16 14l-4.4 1.6L10 20l-1.6-4.4L4 14l4.4-1.6z"/>
    <path class="s2" d="M29 16l1.2 3.3L33.5 20l-3.3 1.2L29 24l-1.2-3.3L24.5 20l3.3-1.2z"/>
    <path class="s3" d="M19 28l.9 2.4 2.4.9-2.4.9-.9 2.4-.9-2.4-2.4-.9 2.4-.9z"/></svg>`,
};

const scout = (size) => (window.OpticScout ? window.OpticScout.html({ size }) : '');

/** The ticks under Analyzing: what actually came back, at most three, newest last. Nothing is listed that a
 *  lookup did not return, so the list is provenance, not decoration. */
const rowsFor = (a) => (a.state === 'analyzing' ? a.fetched.slice(-3) : []);
function checklist(a) {
  const rows = rowsFor(a);
  return rows.length ? `<ul class="milo-doing-got">${rows.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>` : '';
}

/**
 * Keep `host` showing `a`, without tearing the figure down when only the words change: a state change used to
 * replace the whole view, which restarted the mascot's own blink timer, reloaded his sprite and re-ran the
 * card's fade, so the card flashed empty between states (browser check, 2026-11-03). The view is rebuilt only
 * when it appears, goes, or changes size. True when it was rebuilt, so the caller can start the figure.
 */
export function syncActivity(host, a, opts = {}) {
  if (!host) return false;
  const live = a && a.state !== 'idle' ? a : null;
  let box = host.querySelector('.milo-doing');
  if (!live) { if (box) box.remove(); return false; }
  const expanded = !!opts.expanded;
  if (box && box.classList.contains('is-expanded') !== expanded) { box.remove(); box = null; }
  if (!box) { host.insertAdjacentHTML('afterbegin', activityHTML(live, opts)); return true; }
  const w = words(live, opts.stepWords), spec = ACTIVITY[live.state] || ACTIVITY.idle;
  if (box.dataset.doing !== live.state) box.dataset.doing = live.state;
  if (box.dataset.scout !== w.scout) box.dataset.scout = w.scout;
  const title = box.querySelector('b'), line = box.querySelector('.milo-doing-line');
  if (title && title.textContent !== w.title) title.textContent = w.title;
  if (line && line.textContent !== w.line) line.textContent = w.line;
  const propHost = box.querySelector('.milo-doing-prop'), prop = spec.prop && PROPS[spec.prop] ? spec.prop : '';
  if (propHost && propHost.dataset.prop !== prop) { propHost.innerHTML = prop ? PROPS[prop] : ''; propHost.dataset.prop = prop; }
  const rows = rowsFor(live), got = box.querySelector('.milo-doing-got');
  const wanted = rows.join('\u0000');
  if ((got ? got.dataset.rows : '') !== wanted) {
    if (!rows.length) { if (got) got.remove(); } else {
      const say = box.querySelector('.milo-doing-say');
      const ul = got || say.insertBefore(document.createElement('ul'), box.querySelector('.milo-doing-dots'));
      ul.className = 'milo-doing-got';
      ul.innerHTML = rows.map((r) => `<li>${esc(r)}</li>`).join('');
      ul.dataset.rows = wanted;
    }
  }
  return false;
}

/**
 * The activity, drawn. `expanded` gives the card with the whole figure; otherwise the inline line with his bust.
 * `stepWords` turns the server's own status string into the reader's words (the panel owns that vocabulary).
 */
export function activityHTML(a, { expanded = false, stepWords = null } = {}) {
  // complete is drawn only when the panel asks for it by name (the moment an answer lands); it is never part
  // of the running states, so a finished answer carries no activity of its own.
  if (!a || a.state === 'idle') return '';
  const w = words(a, stepWords);
  const spec = ACTIVITY[a.state] || ACTIVITY.idle;
  const name = spec.prop && PROPS[spec.prop] ? spec.prop : '';
  const prop = `<span class="milo-doing-prop" data-prop="${name}">${name ? PROPS[name] : ''}</span>`;
  // role=status, not an aria-live region of its own per state: the heading and line are read as one.
  return `<div class="milo-doing${expanded ? ' is-expanded' : ''}" data-doing="${a.state}" data-scout="${w.scout}" role="status">
    <span class="milo-doing-fig">${scout(expanded ? 'full' : 'compact')}${prop}</span>
    <span class="milo-doing-say"><b>${esc(w.title)}</b><span class="milo-doing-line">${esc(w.line)}</span>${checklist(a)}
      <span class="milo-doing-dots" aria-hidden="true"><i></i><i></i><i></i></span></span></div>`;
}
