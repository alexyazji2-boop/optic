// Scan, Nightly shortlist (roadmap stage 5, 2026-10-22): the setups that changed on the last completed session
// across Optic's documented universe, from GET /api/shortlist (app/shortlist.py). No quota: an empty list is an
// answer. Each entry says its trigger and state, what supports and conflicts with it, its catalysts, how fresh
// its data is and why it was included; the forward record of past lists sits under it, failures included.
import { html } from '../core/dom.js';
import { num, signed, clean, shortDate, fullDate, isNum, capFirst, plural } from '../core/format.js';
import { empty, failed, how, skeleton } from '../ui/states.js';
import { hrefFor } from '../nav.js';

const STATE = { triggered: 'Triggered', armed: 'Armed, waiting', watching: 'Watching', invalidated: 'Invalidated', expired: 'Expired' };

function item(it, d) {
  const up = it.direction === 'bull';
  const level = !isNum(it.trigger_level) ? '' : it.state === 'armed' ? `Trigger at ${num(it.trigger_level)}. ` : `It closed through ${num(it.trigger_level)}. `;
  const stale = it.data_as_of && it.data_as_of !== d.as_of;
  return html`<li class="sl-i">
    <div class="sl-h"><a class="tick" href="${hrefFor('chart', it.symbol)}">${it.symbol}</a><span class="${up ? 'up' : 'down'}">${up ? 'Rising setup' : 'Falling setup'}</span>
      <b>${it.setup}</b><span class="chip-tag">${STATE[it.state] || capFirst(it.state)}${it.state_at ? `, ${shortDate(it.state_at)}` : ''}</span></div>
    <p>${clean(it.why_included)} ${level}${isNum(it.invalidation) ? `A close ${up ? 'below' : 'above'} ${num(it.invalidation)} invalidates it` : 'No invalidation level'}${isNum(it.close) ? `; the last close was ${num(it.close)}` : ''}.</p>
    <div class="sl-two"><div><p class="t-label">Supports it</p><ul class="plain">${(it.supporting || []).map((x) => html`<li>${clean(x)}</li>`)}</ul></div>
      <div><p class="t-label">Conflicts with it</p>${(it.conflicting || []).length ? html`<ul class="plain">${it.conflicting.map((x) => html`<li>${clean(x)}</li>`)}</ul>` : html`<p class="t-muted">Nothing in the rule's checks or the calendar.</p>`}</div></div>
    ${(it.catalysts || []).length ? html`<p class="sl-cat"><b>Catalysts.</b> ${it.catalysts.map((c) => clean(c.text)).join(' ')}</p>` : ''}
    <p class="asof">${it.conditions && isNum(it.conditions.met) ? `${it.conditions.met} of ${it.conditions.of} conditions met. ` : ''}${isNum(it.volume_ratio) ? `Volume ${num(it.volume_ratio, 2)}× its 20-session average.` : ''}${stale ? html` <b>Older data: through the ${fullDate(it.data_as_of)} close.</b>` : ''}</p></li>`;
}

function record(r) {
  if (!r) return '';
  if (!r.outcomes_recorded) return html`<p class="asof">Forward record: ${plural(r.entries_listed || 0, 'entry', 'entries')} listed since ${r.since ? fullDate(r.since) : 'the first list'}; outcomes are recorded ten sessions after each list, so none are in yet.</p>`;
  return html`<h3>The forward record</h3>
    <dl class="kv sl-kv"><div><dt>Outcomes recorded</dt><dd>${r.outcomes_recorded}</dd><dd class="kv-note">of ${r.entries_listed} listed since ${fullDate(r.since)}</dd></div>
      <div><dt>Moved its way after 10 sessions</dt><dd>${r.positive} of ${r.outcomes_recorded}</dd><dd class="kv-note">average ${signed(r.avg_move_pct, 2)} from the list's close</dd></div>
      <div><dt>Closed through the invalidation</dt><dd>${r.invalidated}</dd><dd class="kv-note">within 10 sessions</dd></div></dl>
    <div class="tscroll"><table class="t"><thead><tr><th scope="col">Name</th><th scope="col">Setup</th><th scope="col">Then</th><th scope="col">Invalidated</th><th scope="col">Move its way, 10 sessions</th></tr></thead>
      <tbody>${(r.recent || []).map((o) => html`<tr><th scope="row">${o.symbol} <small class="t-muted">${o.direction === 'bull' ? 'rising' : 'falling'}</small></th><td>${o.setup}</td><td>${o.state_then}${o.state_then === 'armed' ? (o.triggered ? ', then triggered' : ', never triggered') : ''}</td><td>${o.invalidated_on ? shortDate(o.invalidated_on) : 'No'}</td><td class="${o.move_pct > 0 ? 'up' : o.move_pct < 0 ? 'down' : ''}">${signed(o.move_pct, 2)}</td></tr>`)}</tbody></table></div>
    <p class="asof">${clean(r.note)}${r.pending ? ` ${r.pending} more still inside their ten sessions.` : ''}</p>`;
}

/** The shortlist section's body for Scan's third mode. */
export function shortlistBody(S) {
  const d = S.shortlist;
  if (d === undefined) return skeleton('rows', 5, 'Reading the latest shortlist');
  if (d && d.error) return failed('The shortlist', d.error, { retry: 'shortlist' });
  if (!d || d.available === false) return empty('No shortlist yet', clean((d && d.reason) || 'The first one is built after the next completed session.'));
  const items = d.items || [];
  const method = how(html`<ul class="plain">${(d.rules || []).map((x) => html`<li>${clean(x)}</li>`)}</ul><p>Selection rules ${d.version}. ${d.evaluated} of ${d.universe_size} names evaluated${(d.failed || []).length ? `; no data for ${d.failed.join(', ')}` : ''}. ${d.forming_excluded ? 'A candle still forming was left out. ' : ''}Built ${new Date(d.built_at).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}.</p>
    <p>Conditions are counted once per kind, so two readings of the same prices are not two confirmations; a count of conditions met is not a probability.</p>
    <p>What it cannot see: anything outside these ${d.universe_size} names, intraday moves after the close, and news after the build. A setup here is a rule's reading of the chart, not a recommendation or a forecast.</p>`);
  return html`<p class="section-sub">Setups that changed on the ${fullDate(d.as_of)} close, across Optic Portfolio's ${d.universe_size} curated names. ${clean(((items[0] || {}).horizon) || '')}</p>
    ${items.length ? html`<ol class="sl-list">${items.map((it) => item(it, d))}</ol>${(d.also_qualified || []).length ? html`<p class="asof">Also qualified, not shown: ${d.also_qualified.join(', ')}.</p>` : ''}`
      : empty('Nothing qualified on that close', clean(d.empty_note || 'An empty list is a normal answer.'))}
    ${method}${record(d.record)}`;
}
