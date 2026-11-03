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
  idle: { title: 'Ready', line: '', scout: 'idle' },
  thinking: { title: 'Thinking', line: 'Understanding your question', scout: 'thinking' },
  researching: { title: 'Researching', line: 'Looking through Optic\u2019s data', scout: 'researching' },
  analyzing: { title: 'Analyzing', line: 'Connecting what came back', scout: 'analyzing' },
  writing: { title: 'Writing', line: 'Putting the answer together', scout: 'writing' },
  complete: { title: 'Answer ready', line: '', scout: 'idle' },
  error: { title: 'Couldn\u2019t finish', line: '', scout: 'error' },
  cancelled: { title: 'Stopped', line: '', scout: 'idle' },
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

/* ---------------- the companion ----------------
 * One region at the top of the panel, outside the scrolling log, that holds Milo for the whole conversation:
 * before a question, while he works, while the answer streams, and after it lands. He used to be drawn
 * inside the log, which meant he was built when the answer began and taken away when it finished, and the
 * reader lost him exactly when they most wanted to know what was happening.
 *
 * Nothing here draws him: the figure is the render (components/scout.js) and the poses carry what he is
 * doing, so there are no icons beside him to crowd a header. The region is built once and patched in place,
 * so his blink timer, his sprite and his gestures all survive every status change and every chunk of text.
 */
const scout = (size, label) => (window.OpticScout ? window.OpticScout.html({ size, label: label || '' }) : '');

/** The companion, built once per panel. `id` names the heading the drawer focuses when it opens. */
export function companionHTML({ size = 'full', id = 'milo-title', label = '' } = {}) {
  return `<div class="milo-co" data-doing="idle" data-scout="idle">
    <span class="milo-co-stage">${scout(size, label)}</span>
    <span class="milo-co-say">
      <h2 class="milo-co-name" id="${id}" tabindex="-1">Milo</h2>
      <span class="milo-co-status" role="status"><b>Ready</b><i></i></span>
    </span>
  </div>`;
}

/**
 * Keep the companion showing `a`. Patches text and data attributes in place and never removes the region:
 * the figure element has to outlive the answer, or his motion restarts every time anything changes.
 * `stepWords` turns the server's own status string into the reader's words. Returns the pose to hold.
 */
export function syncCompanion(root, a, opts = {}) {
  if (!root) return null;
  const live = a && ACTIVITY[a.state] ? a : { state: 'idle', said: '' };
  const spec = ACTIVITY[live.state] || ACTIVITY.idle;
  const said = live.said && opts.stepWords ? opts.stepWords(live.said) : live.said;
  if (root.dataset.doing !== live.state) root.dataset.doing = live.state;
  if (root.dataset.scout !== spec.scout) root.dataset.scout = spec.scout;
  const name = root.querySelector('.milo-co-status > b');
  const detail = root.querySelector('.milo-co-status > i');
  // The state is the status. The server's own words for the step go under it when it sends them, and
  // nowhere at all when it does not, so the line is never filled with something invented.
  if (name && name.textContent !== spec.title) name.textContent = spec.title;
  const under = said || spec.line || '';
  if (detail && detail.textContent !== under) detail.textContent = under;
  return spec.scout;
}
