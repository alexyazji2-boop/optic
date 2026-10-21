// Saved research, at #/research (Classic parity B4d, 2026-10-21): the questions the reader kept, to ask again, and
// Classic's "Start an investigation" (app.js:31034). The account's list when signed in, this browser's otherwise
// (core/research.js). Asking again opens Milo with the question in the box: nothing is sent until the reader
// presses Send.
import { html, render as draw } from '../core/dom.js';
import * as store from '../core/store.js';
import { shortDate } from '../core/format.js';
import { skeleton, failed, empty } from '../ui/states.js';
import { openMilo, provideContext } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { listSaved, forget } from '../core/research.js';

let D = null, err = null, live = true, mainEl = null, seq = 0, wired = null;

// Classic's four ways in, word for word (RESEARCH_ROUTES); each goes where it says, none sends anything
const ROUTES = [
  { q: 'Which names look strongest right now?', href: '#/scan', note: 'Named screens over the ranked universe. Each states what it did not search.' },
  { q: 'How do two or three names stack up?', href: '#/compare', note: 'Scored across three horizons separately, so a name can lead one and trail another.' },
  { q: 'What is going on with one company?', milo: '', note: 'Search a ticker to open the full read, or ask in plain language.' },
  { q: 'I need sources and citations.', milo: 'deep', note: 'Deep research runs live web sources and cites them. Slower, and rate limited.' },
];

function start() {
  return html`<section class="section" aria-labelledby="sv-start"><h2 class="t-h2" id="sv-start">Start an investigation</h2>
    <ul class="sv-routes">${ROUTES.map((r, i) => html`<li>${r.href ? html`<a class="sv-route" href="${r.href}"><b>${r.q}</b><span>${r.note}</span></a>`
      : html`<button type="button" class="sv-route" data-sv-route="${i}"><b>${r.q}</b><span>${r.note}</span></button>`}</li>`)}</ul></section>`;
}
function list() {
  if (err) return failed('Saved research', err, { retry: 'saved' });
  if (!D) return skeleton('rows', 4, 'Loading saved research');
  const items = D.items || [];
  const where = D.where === 'account' ? `Kept with your account${D.limit ? `, up to ${D.limit}` : ''}.` : 'Kept in this browser, up to 40. An account keeps them on every device.';
  if (!items.length) return html`${empty('Nothing saved yet', 'Press Save under a question you asked Milo, and it is kept here to ask again.')}<p class="asof">${where}</p>`;
  return html`<ul class="sv-list">${items.map((x, i) => html`<li class="sv-item">
      <p class="sv-q">${x.question}</p>
      <p class="sv-meta">${x.symbol ? html`<a class="textlink" href="#/${encodeURIComponent(x.symbol)}">${x.symbol}</a>` : html`<span>The market</span>`}${x.at ? html`<span>Saved ${shortDate(String(x.at).slice(0, 10))}</span>` : ''}</p>
      <div class="sv-acts"><button type="button" class="btn btn-sm" data-sv-ask="${i}">Ask again</button><button type="button" class="btn btn-sm btn-quiet" data-sv-forget="${i}" aria-label="Forget: ${x.question.slice(0, 80)}">Forget</button></div></li>`)}</ul>
    <p class="asof">${where} Asking again puts the question in Milo's box; nothing is sent until you press Send.</p>`;
}
function paint() {
  if (!live || !mainEl) return;
  draw(mainEl, html`<header class="page-head"><h1 class="t-display-m">Saved research</h1>
      <p class="section-sub">Questions you kept to ask again${store.signedIn() ? '' : html`. <a class="textlink" href="#/signin">Sign in</a> to keep them on every device`}.</p></header>
    <section class="section" aria-labelledby="sv-list-h"><h2 class="t-h2" id="sv-list-h">Your questions</h2><div id="sv-body">${list()}</div></section>
    ${start()}`);
}
async function load() {
  const my = ++seq; err = null;
  try { const r = await listSaved(); if (my !== seq) return; D = r; } catch (e) { if (my !== seq) return; err = e; }
  paint();
}
function onClick(e) {
  const t = (q) => e.target.closest(q);
  let b;
  if ((b = t('[data-sv-ask]'))) { const x = D.items[Number(b.dataset.svAsk)]; if (x) openMilo({ question: x.question, opener: b, symbol: x.symbol || '', about: 'Saved research' }); return; }
  if ((b = t('[data-sv-route]'))) { const r = ROUTES[Number(b.dataset.svRoute)]; openMilo({ opener: b, about: 'Saved research' }).then(() => { if (r.milo === 'deep') { const d = document.querySelector('[data-v2-milo-deep]'); if (d) d.focus(); } }); return; }
  if ((b = t('[data-sv-forget]'))) {
    const x = D.items[Number(b.dataset.svForget)]; if (!x) return;
    forget(x).then((undo) => {
      load();
      toast('Forgotten.', undo ? { action: 'Undo', run: () => Promise.resolve(undo()).then(load) } : {});
    }, (e2) => toast(`It was not forgotten: ${e2.message || 'try again'}.`, { kind: 'bad' }));
  }
}
export async function render(main) {
  live = true; mainEl = main; D = null;
  document.title = 'Saved research, Optic';
  provideContext(() => ({ view: 'saved', saved_research: (D && D.items || []).slice(0, 20).map((x) => ({ question: x.question, symbol: x.symbol })) }));
  if (wired !== main) { main.addEventListener('click', onClick); wired = main; }
  paint(); load();
}
export function dispose() { live = false; }
export const retry = { saved: () => load() };
