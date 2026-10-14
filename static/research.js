/* The research framework on the Overview: four questions, answered apart.
 *
 * "Is it a strong business", "is the price attractive", "is there a trade" and
 * "what about earnings" have different evidence and different answers, and a
 * reader shown one score for all four cannot tell which the answer turns on.
 * Every grade here comes from /api/framework (app/research/), which does all of
 * the arithmetic and applies the stated rules; this file only shows it. Each
 * card leads with the answer in a word or a letter, then one sentence, then the
 * evidence on request.
 *
 * Loaded after app.js, whose helpers (esc, getJSON, STATE) it uses. Exposes
 * window.OpticFramework for renderOverviewView: the host markup and the loader.
 * The server computes the same assessment for Milo per question, so nothing
 * here is sent with the chat.
 */
(function () {
  'use strict';

  const FW = { data: {}, at: {}, loading: {}, errors: {} };
  const TTL_MS = 10 * 60 * 1000;
  const has = (v) => v !== null && v !== undefined && !(typeof v === 'number' && Number.isNaN(v));
  const money = (v) => (has(v) ? '$' + Number(v).toFixed(2) : 'n/a');
  const pct = (v, d = 1) => (has(v) ? `${Number(v).toFixed(d)}%` : 'n/a');

  function hostHTML() {
    return `<section class="ov-sec rf" id="ov-framework" aria-labelledby="rf-h">
      <h2 class="ov-q" id="rf-h">Four questions, answered separately</h2>
      <div class="rf-body"><p class="ov-meta">Grading the business, the price, the setup and the earnings…</p></div>
    </section>`;
  }

  function list(items) {
    const rows = (items || []).filter(Boolean);
    return rows.length ? `<ul class="rf-list">${rows.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>` : '';
  }

  function tile(id, label, value, sub, more) {
    return `<div class="rf-tile" data-rf="${id}">
      <p class="osc-label">${esc(label)}</p>
      <p class="rf-value">${esc(value)}</p>
      <p class="rf-sub">${esc(sub || '')}</p>
      ${more ? `<details class="rf-more"><summary>Why</summary><div class="rf-more-body">${more}</div></details>` : ''}
    </div>`;
  }

  function componentRows(cs) {
    return (cs || []).map((c) => {
      const grade = c.status === 'scored' ? (c.grade || (has(c.score) ? Number(c.score).toFixed(1) : ''))
        : c.status === 'not_applicable' ? 'n/a' : 'no data';
      const says = c.status === 'scored' ? c.headline : c.reason;
      return `<tr><th scope="row">${esc(c.label)}</th><td class="rf-g">${esc(grade)}</td><td>${esc(says || '')}</td></tr>`;
    }).join('');
  }

  function businessTile(lt) {
    if (!lt || !lt.available) {
      const why = ((lt || {}).conviction || {}).why || 'The filings could not be read.';
      return tile('business', 'Is it a strong business?', 'Insufficient Data', why, '');
    }
    const q = lt.quality || {};
    const conv = lt.conviction || {};
    const value = q.status === 'scored' ? `Quality ${q.grade}` : 'Insufficient Data';
    const sub = q.status === 'scored' ? `Long-term conviction: ${conv.label}. ${conv.why || ''}` : (q.reason || '');
    const more = `<table class="rf-table"><tbody>${componentRows(q.components)}</tbody></table>
      ${(lt.loss_paths || []).length ? `<p class="ov-h3">Two ways this could lose money over three years</p>
        ${list((lt.loss_paths || []).map((l) => `${l.risk}: ${l.text}`))}` : ''}
      ${(lt.accumulation || {}).offered ? `<p class="ov-h3">Levels to reassess at</p>
        ${list(lt.accumulation.zones.map((z) => `${money(z.price)}: ${z.basis} (${pct(z.distance_pct)})`))}
        <p class="ov-fine">${esc(lt.accumulation.condition)}</p>` : ''}
      <p class="ov-fine">${esc(lt.policy_note || '')} ${esc(lt.separation_note || '')}</p>`;
    return tile('business', 'Is it a strong business?', value, sub, more);
  }

  function priceTile(lt) {
    const v = (lt || {}).valuation || {};
    if (!lt || !lt.available || !v.status) return tile('price', 'Is the price attractive?', 'Insufficient Data',
      'Valuation needs the company\'s filings.', '');
    const lead = (v.components || []).find((c) => c.status === 'scored');
    const sub = v.status === 'scored' ? (lead ? lead.headline : v.summary) : (v.reason || '');
    const chart = lt.chart || {};
    const more = `<table class="rf-table"><tbody>${componentRows(v.components)}</tbody></table>
      ${chart.text ? `<p class="ov-h3">The chart, as context</p><p class="rf-p">${esc(chart.text)}</p>` : ''}
      ${chart.volume ? `<p class="ov-fine">${esc(chart.volume.text)}</p>` : ''}
      <p class="ov-fine">Graded on its own, separately from the business: 4 of 4 is cheapest. A strong business
        can be an expensive stock.</p>`;
    return tile('price', 'Is the price attractive?', v.status === 'scored' ? v.label : 'Insufficient Data', sub, more);
  }

  function tradeTile(sw) {
    if (!sw) return tile('trade', 'Is there a trade?', 'Insufficient Data', 'No swing assessment.', '');
    const plan = sw.plan;
    const objections = (sw.objections || []).slice().sort((a, b) => b.severity - a.severity);
    let more = objections.length ? `<p class="ov-h3">Reasons to skip it, most damaging first</p>
      ${list(objections.map((o) => o.text))}` : '<p class="rf-p">No specific objection was found in the data.</p>';
    if (plan) {
      const inv = plan.invalidation || {};
      const sens = plan.sensitivity || {};
      more += `<table class="rf-table"><tbody>
        <tr><th scope="row">Setup</th><td colspan="2">${esc(plan.kind)} (${esc(plan.side)})</td></tr>
        <tr><th scope="row">Entry zone</th><td colspan="2">${money((plan.entry_zone || [])[0])} to ${money((plan.entry_zone || [])[1])}</td></tr>
        <tr><th scope="row">Confirmation</th><td colspan="2">${esc(plan.confirmation)}</td></tr>
        <tr><th scope="row">Invalidation</th><td colspan="2">${money(inv.price)}: ${esc(inv.structure || '')}. ${esc(inv.note || '')}</td></tr>
        <tr><th scope="row">Targets</th><td colspan="2">${(plan.targets || []).map(money).join(', ')} (${esc(plan.target_basis || '')})</td></tr>
        <tr><th scope="row">Reward to risk</th><td colspan="2">${has(plan.reward_to_risk) ? Number(plan.reward_to_risk).toFixed(2) : 'n/a'}
          = ${esc(plan.rr_formula || '')}; ${has(sens.low) ? `${Number(sens.low).toFixed(2)} to ${Number(sens.high).toFixed(2)} across fills and costs` : ''}</td></tr>
        <tr><th scope="row">Holding</th><td colspan="2">${esc((plan.holding || {}).basis || '')}</td></tr>
        <tr><th scope="row">Earnings</th><td colspan="2">${esc((plan.earnings || {}).text || '')}</td></tr>
      </tbody></table>
      <p class="ov-fine">${esc(plan.reassess || '')}</p>`;
      if (plan.sizing_example && plan.sizing_example.available) {
        const s = plan.sizing_example;
        more += `<p class="ov-fine">${esc(s.label)} ${s.shares} shares risk about $${Math.round(s.planned_loss)} at the stop. ${esc(s.gap_note || '')}</p>`;
      }
    } else if (sw.reassess_when) {
      more += `<p class="ov-h3">What would make it worth another look</p><p class="rf-p">${esc(sw.reassess_when)}</p>`;
    }
    more += `<p class="ov-fine">${esc(sw.framework_note || '')}</p>`;
    const value = sw.grade === 'S' || sw.grade === 'A' || sw.grade === 'B' ? `Grade ${sw.grade}` : sw.grade;
    return tile('trade', 'Is there a trade?', value, sw.why, more);
  }

  function earningsTile(er) {
    if (!er) return tile('earnings', 'What about earnings?', 'Insufficient Data', 'No earnings data.', '');
    const pre = er.pre;
    const post = er.post;
    if (pre && pre.available) {
      const rel = pre.release || {};
      const p = pre.predictions || {};
      const conf = (pre.view || {}).confidence || {};
      const row = (k, label) => (p[k] ? `<tr><th scope="row">${label}</th><td class="rf-g">${esc(p[k].lean)}</td>
        <td>Confidence: ${esc(conf[k] || p[k].confidence)}. ${esc((p[k].evidence || []).map((x) => x.text).join(' '))}</td></tr>` : '');
      const opt = pre.options || {};
      const more = `<table class="rf-table"><tbody>${row('results', 'Results')}${row('guidance', 'Guidance')}${row('reaction', 'Stock reaction')}</tbody></table>
        <p class="ov-h3">The bar it has to clear</p><p class="rf-p">${esc((pre.hurdle || {}).text || '')}</p>
        ${list(((pre.hurdle || {}).points || []).map((x) => x.text))}
        ${opt.available ? `<p class="ov-h3">What options are priced for</p>
          <p class="rf-p">${pct(opt.event_move_pct || opt.expiry_move_pct)} either way${opt.range ? ` (${money(opt.range.low)} to ${money(opt.range.high)})` : ''}.
          ${esc(opt.event_isolated ? (opt.event_move_method || '') : (opt.event_note || ''))}</p>` : ''}
        <p class="ov-h3">Cases</p>${list([`Base: ${((pre.view || {}).cases || {}).base || ''}`,
          `Bull: ${((pre.view || {}).cases || {}).bull || ''}`, `Bear: ${((pre.view || {}).cases || {}).bear || ''}`])}
        <p class="ov-h3">What would prove it wrong</p>${list((pre.view || {}).invalidators)}
        <p class="ov-fine">${esc((pre.view || {}).thesis_vs_trade || '')} ${esc((pre.view || {}).probabilities_note || '')}
          Not in the data: ${esc((pre.not_available || []).join(', '))}.</p>`;
      const when = `${rel.date}${rel.timing && rel.timing !== 'unknown' ? ', ' + rel.timing.replace('_', ' ') : ''}`
        + (rel.confirmed ? '' : ' (estimated)');
      return tile('earnings', 'What about earnings?', `Reports ${when}`, (pre.view || {}).headline, more);
    }
    if (post && post.available) {
      const q = post.quality || {};
      const a = post.headline_audit || {};
      const more = `<table class="rf-table"><tbody>
        <tr><th scope="row">EPS</th><td class="rf-g">${esc((a.eps || {}).state || '')}</td><td>${has((a.eps || {}).actual) ? Number(a.eps.actual).toFixed(2) : 'n/a'} against ${has((a.eps || {}).consensus) ? Number(a.eps.consensus).toFixed(2) : 'n/a'} (${esc((a.eps || {}).basis || '')})</td></tr>
        <tr><th scope="row">Revenue</th><td class="rf-g">${esc((a.revenue || {}).state || '')}</td><td>${esc((a.revenue || {}).reason || '')}</td></tr>
        <tr><th scope="row">Guidance</th><td class="rf-g">n/a</td><td>${esc((a.guidance || {}).reason || '')}</td></tr>
      </tbody></table>
      ${(a.eps || {}).resolution ? `<p class="ov-fine">${esc(a.eps.resolution)}</p>` : ''}
      ${a.basis_warning ? `<p class="ov-fine">${esc(a.basis_warning)}</p>` : ''}
      <p class="ov-h3">The reaction</p><p class="rf-p">${esc((post.reaction || {}).text || '')} ${esc((post.reaction || {}).caveat || '')}</p>
      ${list((post.positives || []).map((t) => 'Positive: ' + t))}${list((post.weaknesses || []).map((t) => 'Weakness: ' + t))}
      <p class="ov-fine">Red flags: ${esc((post.red_flags || []).join(' '))} ${esc(post.separation_note || '')}</p>
      ${(post.forecast_review || {}).available ? `<p class="ov-fine">Saved forecast from ${esc(post.forecast_review.saved_at)} reviewed separately for results, guidance and reaction.</p>` : ''}`;
      return tile('earnings', 'What about earnings?', q.grade ? `Report quality ${q.grade}` : 'Report not graded',
        `Reported ${post.release.date}. ${(post.reaction || {}).text || ''}`, more);
    }
    const reason = (pre || post || {}).reason || er.reason || 'No earnings view.';
    return tile('earnings', 'What about earnings?', 'Insufficient Data', reason, '');
  }

  function render(out) {
    if (!out || out.available === false) {
      return `<p class="ov-meta">The research framework could not grade this symbol: ${esc((out || {}).reason || 'no data')}.</p>`;
    }
    const comb = out.combined || {};
    const gaps = ((out.data || {}).gaps || []);
    return `<div class="rf-grid">
        ${businessTile(out.long_term)}${priceTile(out.long_term)}${tradeTile(out.swing)}${earningsTile(out.earnings)}
      </div>
      ${comb.verdict ? `<p class="rf-verdict">${esc(comb.verdict)}</p>` : ''}
      <p class="ov-fine">The Optic Score above summarises trend and signals. These four are graded separately, each by
        its own stated rules (method ${esc(out.method_version || '')}, policy ${esc((out.policy || {}).version || '')}),
        and none has been shown to predict returns. "Insufficient Data" means evidence is missing, not that the answer is
        bad.${(out.freshness || {}).text ? ' ' + esc(out.freshness.text) : ''}${gaps.length ? ' Not loaded: ' + esc(gaps.join('; ')) + '.' : ''}</p>`;
  }

  function paint(sym) {
    const host = document.querySelector('#ov-framework .rf-body');
    if (!host || STATE.ticker !== sym) return;
    if (FW.errors[sym]) {
      host.innerHTML = `<p class="ov-meta">The research framework is not available right now: ${esc(FW.errors[sym])}.</p>`;
      return;
    }
    if (FW.data[sym]) host.innerHTML = render(FW.data[sym]);
  }

  async function load(sym) {
    sym = (sym || STATE.ticker || '').toUpperCase();
    if (!sym) return;
    if (FW.data[sym] && Date.now() - FW.at[sym] < TTL_MS) { paint(sym); return; }
    if (FW.loading[sym]) return;
    FW.loading[sym] = true;
    delete FW.errors[sym];
    try {
      FW.data[sym] = await getJSON(`/api/framework/${encodeURIComponent(sym)}?mode=combined`);
      FW.at[sym] = Date.now();
    } catch (err) {
      FW.errors[sym] = err.message;
    } finally {
      FW.loading[sym] = false;
    }
    paint(sym);
  }

  window.OpticFramework = { hostHTML, load, render, data: FW.data };
}());
