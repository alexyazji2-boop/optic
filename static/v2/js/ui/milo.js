// Contextual Milo. Every entry point says what Milo will see ("AAPL Dossier,
// Overview") and opens with a question already drafted, which the reader can
// change before sending. Talks to the real /api/chat stream; when the server
// refuses (signed out, allowance used, no assistant configured) the panel says
// exactly that and what to do.
import { html, render, $, raw } from '../core/dom.js';
import * as drawer from './drawer.js';
import * as api from '../core/api.js';
import { signedIn } from '../core/store.js';
import { esc } from '../core/format.js';

let ctxProvider = () => ({});
/** Pages register what Milo may see from them. */
export function provideContext(fn) { ctxProvider = fn || (() => ({})); }

export function button(label, { ask, context, symbol, cls = '' } = {}) {
  return html`<button type="button" class="btn btn-milo ${cls}" data-v2-milo="${ask || ''}" data-v2-milo-ctx="${context || ''}" data-v2-milo-sym="${symbol || ''}">${label}</button>`;
}

function paragraphs(text) {
  return raw(String(text).split(/\n{2,}/).map((p) => `<p>${esc(p).replace(/\n/g, '<br>')}</p>`).join(''));
}

export async function openMilo({ question = '', contextLabel = '', symbol = '', opener } = {}) {
  drawer.open({
    kicker: 'Ask Milo', title: symbol ? `About ${symbol}` : 'Ask Milo', opener,
    body: html`<div class="milo">
      <p class="milo-ctx">Milo will see <b>${contextLabel || 'this page'}</b>, with prices delayed up to 15 minutes.</p>
      <div class="milo-answer" aria-live="polite"></div>
      <form class="milo-form">
        <label class="sr" for="milo-q">Your question</label>
        <textarea id="milo-q" rows="3">${question}</textarea>
        <button type="submit" class="btn btn-primary">Send</button>
      </form>
      <p class="milo-allow asof"></p>
    </div>`,
    mount: (b) => {
      const form = $('.milo-form', b), out = $('.milo-answer', b), ta = $('#milo-q', b), allow = $('.milo-allow', b);
      api.get('/api/ai-allowance', { ttl: 0, force: true }).then((r) => {
        const a = (r && r.allowance) || {};
        if (a.requires_account && !signedIn()) allow.textContent = 'Milo needs a free account. Sign in to ask.';
        else if (a.enforced && Number.isFinite(a.left)) allow.textContent = `${a.left} of ${a.allowed} questions left today.`;
      }).catch(() => {});
      ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
      form.addEventListener('submit', (e) => { e.preventDefault(); send(ta.value.trim(), { out, form, symbol, contextLabel }); });
    },
  });
}

async function send(q, { out, form, symbol, contextLabel }) {
  if (!q) return;
  const btn = $('button[type=submit]', form);
  btn.disabled = true;
  render(out, html`<p class="t-muted" role="status">Milo is reading ${contextLabel || 'the page'}…</p>`);
  const ctx = Object.assign({}, ctxProvider() || {});
  ctx.focus = { scope: 'auto', view: ctx.view || 'v2', view_label: contextLabel || 'Optic', ticker: symbol || null, captured_at: new Date().toISOString() };
  let text = '';
  try {
    const res = await fetch('/api/chat', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ messages: [{ role: 'user', content: q }], context: ctx, persona: 'neutral' }),
    });
    if (!res.ok) {
      let d = null; try { d = await res.json(); } catch (e) { /* not json */ }
      const msg = (d && (d.detail || d.message)) || res.statusText;
      if (res.status === 401) {
        render(out, html`<div class="state"><p class="t-h3">Milo needs a free account</p><p>${typeof msg === 'string' ? msg : ''}</p><a class="btn btn-primary" href="#/signin">Sign in</a></div>`);
      } else if (res.status === 429) {
        render(out, html`<div class="state"><p class="t-h3">No questions left for now</p><p>${typeof msg === 'string' ? msg : 'The allowance resets tomorrow.'}</p></div>`);
      } else {
        render(out, html`<div class="state err"><p class="t-h3">Milo did not answer</p><p>${typeof msg === 'string' ? msg : 'The server answered with an error.'}</p></div>`);
      }
      return;
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read(); // eslint-disable-line no-await-in-loop
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const chunks = buf.split('\n\n');
      buf = chunks.pop();
      for (const c of chunks) {
        const ev = (/^event: (.*)$/m.exec(c) || [])[1];
        const dataLine = (/^data: (.*)$/m.exec(c) || [])[1];
        let data = {}; try { data = JSON.parse(dataLine || '{}'); } catch (e) { data = {}; }
        if (ev === 'delta' && data.text) { text += data.text; render(out, paragraphs(text)); }
        else if (ev === 'status' && !text) render(out, html`<p class="t-muted" role="status">${data.label || data.state || 'Working'}…</p>`);
        else if (ev === 'error') render(out, html`<div class="state err"><p class="t-h3">Milo could not answer</p><p>${data.message || 'The assistant returned an error.'}</p></div>`);
      }
    }
    if (!text && !$('.state', out)) render(out, html`<p class="t-muted">Milo returned no text.</p>`);
  } catch (e) {
    render(out, html`<div class="state err"><p class="t-h3">Milo could not be reached</p><p>Check your connection and try again.</p></div>`);
  } finally {
    btn.disabled = false;
  }
}
