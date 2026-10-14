/* Fair-value model workspace (Investing tab).
 *
 * "Complex analysis, presented simply": a sourced, deterministic DCF that the
 * reader can read in one sentence and interrogate as far as they like. Every
 * figure here comes from the server (/api/valuation, app/valuation/), which
 * does all of the arithmetic; this file only shows it, collects the reader's
 * edits and sends them back to be recomputed. Nothing is calculated here
 * except formatting, so the page and the engine cannot disagree.
 *
 * Layout: the summary sentence and the numbers that frame it, then what moves
 * the value, the scenario range, what today's price implies, and the
 * sensitivity tables. Assumptions, the forecast, the bridge, the linked
 * statements, other methods, sources and formulas sit in sections that open on
 * request.
 *
 * Loaded after app.js, whose helpers (esc, fmt, fmtCompact, usdCompact,
 * getJSON, signedIn, loadingHTML, STATE, draftPulse) it uses. Exposes
 * window.OpticValuation for app.js's hooks: the host markup, the loader, the
 * Milo context and Milo's proposal cards.
 */
(function () {
  'use strict';

  const VAL = {
    data: {},        // symbol -> last server answer for the working assumptions
    defaults: {},    // symbol -> server answer for the defaults (for the "default" column)
    edits: {},       // symbol -> { drivers: {...}, wacc: {...} } the reader's working changes
    loading: {},     // symbol -> true while the first load is in flight
    errors: {},      // symbol -> message from the last failed run
    seq: 0,
    timer: null,
    open: {},        // section key -> true when the reader opened it
    tab: 'wacc_growth',
    saved: {},       // symbol -> list of saved models (account or browser)
    status: {},      // symbol -> save status line
    comps: {},       // symbol -> comps answer
    sotp: {},        // symbol -> sum-of-the-parts answer
    replays: {},     // model id -> replay answer
  };
  const STORE_KEY = 'optic.dcf.v1';
  const MAX_LOCAL_MODELS = 40;

  /* ------------------------------------------------------------ storage */

  function readStore() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      const parsed = raw ? JSON.parse(raw) : null;
      if (parsed && typeof parsed === 'object') return { edits: parsed.edits || {}, models: parsed.models || [] };
    } catch (e) { /* private mode or a bad copy: start empty */ }
    return { edits: {}, models: [] };
  }

  function writeStore(next) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(next)); } catch (e) { /* full or blocked */ }
  }

  function rememberEdits(sym) {
    const s = readStore();
    const e = VAL.edits[sym];
    if (e && (Object.keys(e.drivers || {}).length || Object.keys(e.wacc || {}).length)) s.edits[sym] = e;
    else delete s.edits[sym];
    writeStore(s);
  }

  /* ------------------------------------------------------------ formatting
   *
   * A model value is an estimate, so the headline rounds it: two significant
   * figures ("about $440"). Tables keep more digits because they compare cases
   * with each other, not with reality. */

  const has = (v) => v !== null && v !== undefined && !Number.isNaN(v);
  const pct = (x, d = 1) => (has(x) ? `${(x * 100).toFixed(d)}%` : '—');
  const signedPct = (x, d = 0) => (has(x) ? `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(d)}%` : '—');
  const pts = (x, d = 1) => (has(x) ? `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(d)} pts` : '—');

  function money(v, ccy) {
    if (!has(v)) return '—';
    const sym = (!ccy || ccy === 'USD') ? '$' : '';
    const abs = Math.abs(v);
    const body = abs >= 100 ? fmt(abs, 0) : abs >= 10 ? fmt(abs, 1) : fmt(abs, 2);
    return `${v < 0 ? '−' : ''}${sym}${body}${sym ? '' : ` ${ccy}`}`;
  }

  function about(v) {
    if (!has(v)) return '—';
    if (v <= 0) return 'nothing per share';
    const digits = Math.max(0, 2 - Math.floor(Math.log10(Math.abs(v))) - 1);
    const rounded = Number(v.toPrecision(2));
    return `about $${fmt(rounded, Math.min(2, digits))}`;
  }

  function bigMoney(v) { return has(v) ? usdCompact(v, 1) : '—'; }

  /* When the price is from. The quote's own trade time when the feed gives
   * one; otherwise only when it was fetched, and said that way, because a
   * quote fetched at midnight is the last close, not a midnight trade. */
  function priceWhen(m) {
    if (m && m.market_time) return `last trade ${when(m.market_time)}`;
    return m && m.as_of ? `quote fetched ${when(m.as_of)}` : 'time not given';
  }

  function when(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric',
      minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' });
  }

  function day(iso) {
    if (!iso) return '';
    const d = new Date(String(iso).slice(0, 10) + 'T12:00:00Z');
    return Number.isNaN(d.getTime()) ? String(iso)
      : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  }

  const KIND_LABEL = {
    reported: 'Reported', history: 'From history', external_estimate: 'Analyst estimate',
    market: 'Market', assumption: 'Assumption', derived: 'Derived', not_reported: 'Not reported',
    included_elsewhere: 'Included in debt', external: 'Quote feed',
  };
  function kindChip(kind) {
    if (!kind) return '';
    return `<span class="dcf-kind dcf-kind-${esc(kind)}">${esc(KIND_LABEL[kind] || kind)}</span>`;
  }

  /* ------------------------------------------------------------ the form's fields
   *
   * Every editable assumption: where it lives in the request, how it is shown
   * (percent or plain), and which default rationale explains it. */

  const FIELDS = [
    { group: 'Growth', key: 'growth.y1', label: 'Revenue growth, first year', unit: '%', why: 'growth.y1' },
    { group: 'Growth', key: 'growth.y2', label: 'Revenue growth, second year', unit: '%', why: 'growth.y2', blank: 'fades from year 1' },
    { group: 'Growth', key: 'terminal.growth', label: 'Growth after the forecast, forever', unit: '%', why: 'terminal.growth' },
    { group: 'Growth', key: 'horizon', label: 'Forecast years', unit: 'yrs', step: 1 },
    { group: 'Profitability', key: 'margin.start', label: 'Operating margin, first year', unit: '%', why: 'margin.start' },
    { group: 'Profitability', key: 'margin.target', label: 'Operating margin it settles at', unit: '%', why: 'margin.target' },
    { group: 'Profitability', key: 'margin.years', label: 'Years to get there', unit: 'yrs', step: 1 },
    { group: 'Reinvestment', key: 'capex_pct.start', label: 'Capex, first year (share of revenue)', unit: '%', why: 'capex.start' },
    { group: 'Reinvestment', key: 'capex_pct.target', label: 'Capex it settles at', unit: '%', why: 'capex.target' },
    { group: 'Reinvestment', key: 'capex_pct.years', label: 'Years to get there', unit: 'yrs', step: 1 },
    { group: 'Reinvestment', key: 'dep_rate', label: 'Depreciation (share of last year’s net PP&E)', unit: '%', why: 'dep_rate' },
    { group: 'Reinvestment', key: 'nwc_pct', label: 'Working capital (share of revenue)', unit: '%', why: 'nwc_pct' },
    { group: 'Reinvestment', key: 'terminal.ronic', label: 'Return on new capital after the forecast', unit: '%', why: 'terminal.ronic' },
    { group: 'Taxes', key: 'tax.start', label: 'Tax rate on operating profit, first year', unit: '%', why: 'tax.start' },
    { group: 'Taxes', key: 'tax.terminal', label: 'Long-run tax rate', unit: '%', why: 'tax.terminal' },
    { group: 'Discount rate', key: 'wacc.risk_free', label: 'Risk-free rate (10-year Treasury)', unit: '%', wacc: true },
    { group: 'Discount rate', key: 'wacc.beta_raw', label: 'Beta (raw, before adjustment)', unit: 'x', wacc: true, step: 0.01 },
    { group: 'Discount rate', key: 'wacc.erp', label: 'Equity risk premium', unit: '%', wacc: true },
    { group: 'Discount rate', key: 'wacc.extra_premium', label: 'Extra premium (size, country, your own)', unit: '%', wacc: true },
    { group: 'Discount rate', key: 'wacc.pre_tax_cost_debt', label: 'Pre-tax cost of debt', unit: '%', wacc: true },
    { group: 'Discount rate', key: 'wacc.marginal_tax', label: 'Tax rate for the interest shield', unit: '%', wacc: true },
    { group: 'Discount rate', key: 'wacc.debt_weight', label: 'Debt weight (blank: today’s market weights)', unit: '%', wacc: true, blank: 'market weights' },
    { group: 'Discount rate', key: 'wacc.override', label: 'Or set the discount rate directly', unit: '%', wacc: true, blank: 'built from the parts above' },
    { group: 'Cross-check', key: 'exit_multiple', label: 'Exit EV/EBITDA (cross-check only)', unit: 'x', why: 'exit_multiple', step: 0.1 },
  ];
  const GROUPS = ['Growth', 'Profitability', 'Reinvestment', 'Taxes', 'Discount rate', 'Cross-check'];

  function getPath(obj, key) {
    return key.split('.').reduce((o, k) => (o && typeof o === 'object' ? o[k] : undefined), obj);
  }

  function fieldValue(d, f, which) {
    const a = which === 'default' ? d.defaults : d.assumptions;
    if (!a) return null;
    if (f.wacc) return getPath(a.wacc, f.key.slice(5));
    return getPath(a.drivers, f.key);
  }

  function shown(f, v) {
    if (!has(v)) return '';
    if (f.unit === '%') return String(Number((v * 100).toFixed(3)));
    return String(Number(Number(v).toFixed(3)));
  }

  function editsFor(sym) {
    if (!VAL.edits[sym]) VAL.edits[sym] = readStore().edits[sym] || { drivers: {}, wacc: {} };
    const e = VAL.edits[sym];
    e.drivers = e.drivers || {};
    e.wacc = e.wacc || {};
    return e;
  }

  function setEdit(sym, f, raw) {
    const e = editsFor(sym);
    const text = String(raw).trim();
    let value;
    if (text === '') value = f.blank ? null : undefined;
    else {
      const n = Number(text.replace(/[,%x×]/g, ''));
      if (!Number.isFinite(n)) return `${f.label} needs a number.`;
      value = f.unit === '%' ? n / 100 : n;
    }
    if (f.wacc) {
      const k = f.key.slice(5);
      if (value === undefined) delete e.wacc[k]; else e.wacc[k] = value;
    } else {
      const [head, tail] = f.key.split('.');
      if (tail) {
        e.drivers[head] = e.drivers[head] || {};
        if (value === undefined) delete e.drivers[head][tail]; else e.drivers[head][tail] = value;
        if (!Object.keys(e.drivers[head]).length) delete e.drivers[head];
      } else if (value === undefined) delete e.drivers[head];
      else e.drivers[head] = value;
    }
    return null;
  }

  /* ------------------------------------------------------------ loading */

  function hostHTML() {
    const sym = STATE.ticker;
    // Always the panel, loading or not: it has to exist when the tab renders
    // so Optic's panel folding wraps it, and load() always follows.
    if (!sym) return '';
    if (!VAL.data[sym]) return shell(sym, loadingHTML('the fair-value model'));
    return render(sym);
  }

  /* The panel's heading and one inner box. Optic folds a panel by moving
   * everything after its h2 into a body it controls, so repaints replace the
   * inner box only and leave that machinery alone. */
  function shell(sym, inner) {
    return `<div class="panel dcf-panel" id="dcf-panel">
      <h2>Fair-value model <span class="th-plain">· discounted cash flow</span></h2><div id="dcf-inner">${inner}</div></div>`;
  }

  function innerHTML(sym) {
    const d = VAL.data[sym];
    if (!d) return VAL.loading[sym] ? loadingHTML('the fair-value model') : '';
    return renderInner(sym, d);
  }

  async function load(force) {
    const sym = STATE.ticker;
    if (!sym) return;
    if (VAL.data[sym] && !force) { paint(sym); return; }
    VAL.loading[sym] = true;
    paint(sym);
    const e = editsFor(sym);
    const edited = Object.keys(e.drivers).length || Object.keys(e.wacc).length;
    try {
      const fresh = await getJSON(`/api/valuation/${encodeURIComponent(sym)}${force ? '?refresh=true' : ''}`);
      VAL.defaults[sym] = fresh;
      VAL.data[sym] = fresh;
      if (edited && fresh.available && fresh.dcf && fresh.dcf.available) await runNow(sym);
    } catch (err) {
      VAL.data[sym] = { available: false, reason: err.message };
    }
    VAL.loading[sym] = false;
    if (STATE.ticker !== sym) return;
    paint(sym);
    loadSaved(sym);
  }

  function paint(sym) {
    const host = document.getElementById('dcf-host');
    if (!host || STATE.ticker !== sym || STATE.view !== 'long') return;
    const active = document.activeElement;
    const focusKey = active && active.getAttribute && active.getAttribute('data-dcf-field');
    const caret = focusKey && typeof active.selectionStart === 'number' ? active.selectionStart : null;
    const inner = document.getElementById('dcf-inner');
    if (inner && host.contains(inner)) inner.innerHTML = innerHTML(sym);
    else host.innerHTML = hostHTML();
    if (focusKey) {
      const again = host.querySelector(`[data-dcf-field="${focusKey}"]`);
      if (again) {
        again.focus();
        if (caret !== null) { try { again.setSelectionRange(caret, caret); } catch (e) { /* number inputs */ } }
      }
    }
  }

  /* Only the results are repainted while the reader types, so the box they
   * are typing in keeps its caret. */
  function paintResults(sym) {
    const out = document.getElementById('dcf-results');
    const d = VAL.data[sym];
    if (!out || !d || STATE.ticker !== sym) { paint(sym); return; }
    out.innerHTML = renderResults(sym, d);
    const form = document.getElementById('dcf-form-status');
    if (form) form.innerHTML = formStatus(sym, d);
    document.querySelectorAll('[data-dcf-field]').forEach((el) => {
      const f = FIELDS.find((x) => x.key === el.getAttribute('data-dcf-field'));
      if (!f) return;
      const changed = (d.assumptions && d.assumptions.changed || []).includes(f.key);
      const row = el.closest('.dcf-field');
      if (row) row.classList.toggle('is-edited', changed);
    });
  }

  function schedule(sym) {
    clearTimeout(VAL.timer);
    VAL.timer = setTimeout(() => { runNow(sym).then(() => paintResults(sym)); }, 350);
  }

  async function runNow(sym, extra) {
    const seq = ++VAL.seq;
    const e = extra || editsFor(sym);
    try {
      const res = await fetch(`/api/valuation/${encodeURIComponent(sym)}/run`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
        body: JSON.stringify({ drivers: e.drivers, wacc: e.wacc }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      if (extra) return body;
      if (seq !== VAL.seq) return null;
      VAL.data[sym] = body;
      VAL.errors[sym] = '';
      rememberEdits(sym);
      return body;
    } catch (err) {
      if (extra) throw err;
      if (seq === VAL.seq) VAL.errors[sym] = err.message;
      return null;
    }
  }

  /* ------------------------------------------------------------ render */

  function render(sym) {
    return shell(sym, renderInner(sym, VAL.data[sym]));
  }

  function renderInner(sym, d) {
    if (!d.available) {
      return `<p class="caveat">${esc(d.reason || 'A model cannot be built for this symbol.')}</p>`;
    }
    return `
      <div id="dcf-results">${renderResults(sym, d)}</div>
      ${renderForm(sym, d)}
      ${renderSaved(sym)}
      <p class="caveat dcf-foot">Model ${esc(d.model_version)} · filings retrieved ${esc(day((d.inputs_digest || {}).filings_retrieved))}
        · balance sheet ${esc(day((d.inputs_digest || {}).balance_date))} · ${esc(priceWhen(d.market || {}))}.
        A model-implied value under stated assumptions. It is not a price target, a forecast Optic stands behind,
        or a signal to buy or sell.</p>`;
  }

  function lede(d) {
    const dcf = d.dcf || {};
    const m = d.market || {};
    const name = esc(d.name || d.ticker);
    const sc = d.scenarios || {};
    const cls = d.classification || {};
    const fitsDcf = ((cls.models || {}).dcf || {}).fit;
    if (!dcf.available && d.defaults && (fitsDcf === 'primary' || fitsDcf === 'supporting' || fitsDcf === 'limited')) {
      return dcf.invalid
        ? `<p class="dcf-lede">These assumptions have no meaningful answer: ${esc(dcf.reason || '')}
          Change them below, or reset to the defaults.</p>`
        : `<p class="dcf-lede">The model could not run yet: ${esc(dcf.reason || '')}
          ${dcf.needs_input ? 'Open the assumptions below and enter it; nothing is filled in with a guess.' : ''}</p>`;
    }
    if (!dcf.available) {
      const alt = d.residual_income && d.residual_income.available ? d.residual_income
        : d.reit && d.reit.available ? null : null;
      let text = `A cash-flow-to-the-firm model does not suit ${name}: ${esc((cls.models && cls.models.dcf && cls.models.dcf.why) || dcf.reason || '')}`;
      if (alt) {
        text += ` Valuing the equity directly with residual income, this model estimates ${name} at <strong>${about(alt.per_share)}</strong> a share.
          The stock last traded at ${money(m.price, m.currency)} (${esc(priceWhen(m))}).`;
      } else if (d.reit && d.reit.available) {
        const r = d.reit; const o = r.own_history;
        text += ` On funds from operations, the REIT yardstick, it earned ${money(r.ffo_per_share)} a share last year and trades at
          <strong>${fmt(r.price_to_ffo, 1)}× FFO</strong> (${money(m.price, m.currency)}, ${esc(priceWhen(m))}).${o
  ? ` At the multiples it traded on over the last ${(r.years || []).filter((y) => y.p_ffo).length} fiscal years, today's FFO would be worth ${money(o.per_share_low)} to ${money(o.per_share_high)},
          about ${money(o.per_share_mid)} at the median. That compares the REIT with its own past, not with what its properties are worth.` : ''}`;
      }
      return `<p class="dcf-lede">${text}</p>`;
    }
    const v = dcf.per_share;
    const rng = has((sc.bear || {}).per_share) && has((sc.bull || {}).per_share)
      ? ` Its bear and bull cases span ${money(sc.bear.per_share)} to ${money(sc.bull.per_share)}.` : '';
    let vs = '';
    if (has(m.price) && has(v) && v > 0) {
      const gap = m.price / v - 1;
      vs = ` The stock last traded at <strong>${money(m.price, m.currency)}</strong> (${esc(priceWhen(m))}), ${
        Math.abs(gap) < 0.05 ? 'close to that estimate' : `${pct(Math.abs(gap), 0)} ${gap > 0 ? 'above' : 'below'} it`}.`;
    } else if (has(v) && v <= 0) {
      vs = ` Under these assumptions the debts and other claims are worth more than the operations, so the model
        leaves nothing for shareholders. That says more about the assumptions than about the stock, which trades at ${money(m.price, m.currency)}.`;
    }
    return `<p class="dcf-lede">Under these assumptions, this model estimates ${name} is worth
      <strong>${about(v)}</strong> a share.${rng}${vs}</p>`;
  }

  function confidenceNote(d) {
    const c = d.classification || {};
    if (!c.confidence || c.confidence === 'normal') return '';
    const reasons = (c.confidence_reasons || []).map(esc).join(' ');
    return `<p class="callout ${c.confidence === 'low' ? 'bad' : 'info'}"><strong>${c.confidence === 'low' ? 'Low' : 'Limited'} confidence.</strong>
      ${esc(c.label || '')}: ${esc(((c.models || {})[c.primary] || {}).why || '')} ${reasons}</p>`;
  }

  function checksHTML(d) {
    const checks = ((d.dcf || {}).checks || []).filter((c) => c.level !== 'info');
    const warns = (d.warnings || []);
    if (!checks.length && !warns.length) return '';
    return `<div class="dcf-checks">${checks.map((c) => `<p class="callout ${c.level === 'error' ? 'bad' : 'info'}">
      <strong>${c.level === 'error' ? 'Not meaningful' : 'Check'}:</strong> ${esc(c.text)}</p>`).join('')}
      ${warns.map((w) => `<p class="callout info"><strong>Data:</strong> ${esc(w)}</p>`).join('')}</div>`;
  }

  function renderResults(sym, d) {
    const dcf = d.dcf || {};
    const m = d.market || {};
    const err = VAL.errors[sym] ? `<p class="callout bad" role="alert">${esc(VAL.errors[sym])} The figures below are from the last assumptions that worked.</p>` : '';
    const tvShare = dcf.terminal_share;
    const tiles = dcf.available ? `<div class="grid c4 dcf-tiles">
      ${tile('Model value, base case', money(dcf.per_share), `${money((d.scenarios || {}).bear && d.scenarios.bear.per_share)} bear · ${money((d.scenarios || {}).bull && d.scenarios.bull.per_share)} bull`)}
      ${tile('Market price', money(m.price, m.currency), esc(priceWhen(m)))}
      ${tile('Upside to the base value', signedPct(dcf.upside), 'Base value ÷ price − 1: how far the price would move to reach it', '')}
      ${tile('Margin of safety', has(dcf.margin_of_safety) && dcf.margin_of_safety > 0 ? pct(dcf.margin_of_safety, 0) : 'None',
    has(dcf.margin_of_safety) && dcf.margin_of_safety > 0 ? '1 − price ÷ value: the cushion below the estimate'
      : 'The price is at or above the estimate, so there is no cushion')}
    </div>
    <p class="dcf-tv">${tvShare > 1
    ? `<strong>All of the value, and more, comes after year ${esc(String(dcf.rows.length))}:</strong> the forecast years consume cash (their present value is ${bigMoney(dcf.pv_forecast)}).`
    : `<strong>${pct(tvShare, 0)} of enterprise value</strong> comes from the years after the ${esc(String(dcf.rows.length))}-year forecast (the terminal value).`}
      ${tvShare > 0.75 ? ' The result depends mostly on the long-run assumptions.' : ''}</p>` : '';
    const ri = d.residual_income;
    const noDcf = !dcf.available && (rangeRows(d).length || (ri && ri.available)) ? `
      <section class="dcf-sec" aria-labelledby="dcf-h-range"><h3 id="dcf-h-range">The methods that fit, side by side</h3>${rangeHTML(d)}</section>
      ${ri && ri.available && ri.sensitivity ? `<section class="dcf-sec" aria-labelledby="dcf-h-sens"><h3 id="dcf-h-sens">Sensitivity</h3>
        ${heatTable(ri.sensitivity, (m.price), () => pct)}</section>` : ''}` : '';
    if (!dcf.available && VAL.open.methods === undefined) VAL.open.methods = true;
    return `${err}${lede(d)}${confidenceNote(d)}${tiles}${checksHTML(d)}${noDcf}
      ${dcf.available ? `
      <div class="dcf-grid">
        <section class="dcf-sec" aria-labelledby="dcf-h-drivers">
          <h3 id="dcf-h-drivers">What moves the value most</h3>
          ${tornadoHTML(d)}
        </section>
        <section class="dcf-sec" aria-labelledby="dcf-h-range">
          <h3 id="dcf-h-range">Scenarios and other methods, side by side</h3>
          ${rangeHTML(d)}
        </section>
      </div>
      <section class="dcf-sec" aria-labelledby="dcf-h-rev">
        <h3 id="dcf-h-rev">What today's price implies</h3>
        ${reverseHTML(d)}
      </section>
      <section class="dcf-sec" aria-labelledby="dcf-h-sens">
        <h3 id="dcf-h-sens">Sensitivity</h3>
        ${sensitivityHTML(d)}
      </section>
      ${scenarioTable(d)}
      ${detailsSec('forecast', 'The forecast, year by year', forecastHTML(d))}
      ${detailsSec('wacc', 'How the discount rate is built', waccHTML(d))}
      ${detailsSec('bridge', 'From enterprise value to a value per share', bridgeHTML(d))}
      ${detailsSec('statements', 'Linked income statement, balance sheet and cash flow', statementsHTML(d))}` : ''}
      ${detailsSec('methods', 'Other valuation methods and when each fits', methodsHTML(sym, d))}
      ${detailsSec('sources', 'Reported history and sources', sourcesHTML(d))}
      ${detailsSec('formulas', 'Formulas and conventions', formulasHTML())}
      ${miloAsks(d)}`;
  }

  function tile(label, value, note) {
    return `<div class="tile"><span class="label">${esc(label)}</span><span class="value">${value}</span>
      ${note ? `<span class="note">${note}</span>` : ''}</div>`;
  }

  function detailsSec(key, title, body) {
    return `<details class="dcf-more" data-dcf-sec="${key}"${VAL.open[key] ? ' open' : ''}>
      <summary>${esc(title)}</summary><div class="dcf-more-body">${body}</div></details>`;
  }

  /* ------------------------------------------------------------ charts */

  /* Tornado: each assumption moved down and up by a stated step, one at a
   * time, centred on the base value. The two sides are told apart by which
   * step produced them (down step / up step), with the value printed at each
   * end, so colour is never the only cue. */
  function tornadoHTML(d) {
    const bars = (d.tornado || []).slice(0, 6);
    if (!bars.length) return '<p class="caveat">No sensitivities could be run.</p>';
    const center = d.dcf.per_share;
    const lo = Math.min(center, ...bars.map((b) => Math.min(b.value_low, b.value_high)));
    const hi = Math.max(center, ...bars.map((b) => Math.max(b.value_low, b.value_high)));
    const span = (hi - lo) || 1;
    const x = (v) => ((v - lo) / span) * 100;
    // Every step is in percentage points; a decimal only where the step has one.
    const step = (b, s) => pts(s, Math.abs(Math.round(s * 1000) % 10) ? 1 : 0);
    const rows = bars.map((b) => {
      const seg = (v, cls, s) => {
        const a = x(Math.min(v, center)); const w = Math.abs(x(v) - x(center));
        return `<span class="dcf-tbar ${cls}" style="left:${a}%;width:${Math.max(w, 0.4)}%"
          title="${esc(`${b.label} ${step(b, s)}: ${money(v)} a share`)}"></span>`;
      };
      return `<li class="dcf-trow">
        <span class="dcf-tlabel">${esc(b.label)}</span>
        <span class="dcf-ttrack">
          ${seg(b.value_low, 'is-down', b.step_low)}${seg(b.value_high, 'is-up', b.step_high)}
          <span class="dcf-tcenter" style="left:${x(center)}%"></span>
        </span>
        <span class="dcf-tvals">${[[b.step_low, b.value_low], [b.step_high, b.value_high]]
    .sort((p, q) => p[1] - q[1]).map(([st, v]) => `<span>${esc(step(b, st))}: ${money(v)}</span>`).join('')}</span>
      </li>`;
    }).join('');
    return `<p class="dcf-note">Each bar moves one assumption by the step shown, holding the rest. Longest first.</p>
      <div class="dcf-legend"><span class="dcf-key is-down"></span>step down <span class="dcf-key is-up"></span>step up
        <span class="dcf-key is-center"></span>base ${money(center)}</div>
      <ul class="dcf-tornado" aria-label="Value per share when each assumption moves">${rows}</ul>`;
  }

  /* One row per method, on one axis, with the market price as a reference
   * line. Rows are never combined: each answers a different question. */
  function rangeHTML(d) {
    const m = d.market || {};
    const rows = rangeRows(d);
    if (!rows.length) return '<p class="caveat">Nothing to compare yet.</p>';
    return rangeChart(rows, m);
  }

  function rangeRows(d) {
    const sc = d.scenarios || {};
    const rows = [];
    if (has((sc.base || {}).per_share)) {
      rows.push({ label: 'DCF, bear to bull', lo: sc.bear && sc.bear.per_share, mid: sc.base.per_share,
        hi: sc.bull && sc.bull.per_share, fit: 'primary' });
    }
    const one = (key, label) => {
      const x = d[key];
      if (x && x.available && has(x.per_share)) rows.push({ label, mid: x.per_share, fit: (x.fit || {}).fit });
    };
    one('fcfe', 'Equity DCF (FCFE)');
    one('ddm', 'Dividend discount');
    one('residual_income', 'Residual income');
    if (d.reit && d.reit.available && d.reit.own_history) {
      const o = d.reit.own_history;
      rows.push({ label: 'P/FFO, its own history', lo: o.per_share_low, mid: o.per_share_mid, hi: o.per_share_high, fit: 'primary' });
    }
    const comps = VAL.comps[d.ticker];
    if (comps && comps.available) {
      (comps.implied || []).filter((c) => c.implied && c.key !== 'pb' && !c.wide).forEach((c) => rows.push({
        label: `Peers' ${c.label}`, lo: c.implied.low.per_share, mid: c.implied.mid.per_share,
        hi: c.implied.high.per_share, fit: 'supporting' }));
    }
    const sp = VAL.sotp[d.ticker];
    if (sp && sp.available && has(sp.per_share)) rows.push({ label: 'Sum of the parts', mid: sp.per_share, fit: 'supporting' });
    return rows;
  }

  function rangeChart(rows, m) {
    const vals = rows.flatMap((r) => [r.lo, r.mid, r.hi]).filter(has).concat(has(m.price) ? [m.price] : []);
    let lo = Math.min(0, ...vals); let hi = Math.max(...vals);
    const pad = (hi - lo) * 0.06; lo -= lo < 0 ? pad : 0; hi += pad;
    const x = (v) => ((v - lo) / ((hi - lo) || 1)) * 100;
    const fitWord = { primary: 'fits', supporting: 'supporting', limited: 'limited fit' };
    return `<p class="dcf-note">Model values per share, each on its own assumptions. They are not averaged.</p>
      <ul class="dcf-range" aria-label="Value per share by method">
      ${rows.map((r) => `<li class="dcf-rrow">
        <span class="dcf-rlabel">${esc(r.label)} <span class="dcf-fit">${esc(fitWord[r.fit] || '')}</span></span>
        <span class="dcf-rtrack">
          ${has(r.lo) && has(r.hi) ? `<span class="dcf-rbar" style="left:${x(Math.min(r.lo, r.hi))}%;width:${Math.abs(x(r.hi) - x(r.lo))}%"
            title="${esc(`${r.label}: ${money(r.lo)} to ${money(r.hi)}`)}"></span>` : ''}
          <span class="dcf-rdot" style="left:${x(r.mid)}%" title="${esc(`${r.label}: ${money(r.mid)}`)}"></span>
          ${has(m.price) ? `<span class="dcf-rprice" style="left:${x(m.price)}%"></span>` : ''}
        </span>
        <span class="dcf-rval">${has(r.lo) ? `${money(r.lo)} – ` : ''}<strong>${money(r.mid)}</strong>${has(r.hi) ? ` – ${money(r.hi)}` : ''}</span>
      </li>`).join('')}
      </ul>
      ${has(m.price) ? `<div class="dcf-legend"><span class="dcf-key is-price"></span>price ${money(m.price, m.currency)}
        <span class="dcf-key is-dot"></span>central value <span class="dcf-key is-bar"></span>range</div>` : ''}`;
  }

  function reverseHTML(d) {
    const r = d.reverse || {};
    if (!(r.solves || []).length) return `<p class="caveat">${esc(r.reason || 'Not available.')}</p>`;
    return `<p class="dcf-note">Many combinations can explain one price. Each line moves a single assumption until the
      model value equals the price and holds everything else at the current settings.</p>
      <ul class="dcf-rev">${r.solves.map((s) => `<li><strong>${esc(s.label)}.</strong> ${esc(s.text)}
        ${s.held ? `<span class="muted">Held fixed: ${esc(s.held)}.</span>` : ''}</li>`).join('')}</ul>`;
  }

  /* Heat table: each cell is a full model run. Shading says how far the cell
   * sits above or below today's price (two hues, neutral near the price); the
   * number is always printed, so the shading is never the only cue. */
  function sensitivityHTML(d) {
    const s = d.sensitivity || {};
    const tabs = [['wacc_growth', 'Discount rate × long-run growth'], ['margin_growth', 'Margin × growth'],
      ['capex_wacc', 'Capex × discount rate']].filter(([k]) => s[k]);
    if (!tabs.length) return '';
    const t = s[VAL.tab] ? VAL.tab : tabs[0][0];
    const g = s[t];
    const price = (d.market || {}).price;
    const fmtAxis = (k, v) => (t === 'margin_growth' && k === 'col' ? pts(v, 0) : pct(v, 1));
    const shade = (v) => {
      if (!has(v) || !has(price)) return '';
      const r = Math.max(-1, Math.min(1, (v / price - 1) / 0.5));
      const a = Math.round(Math.abs(r) * 100) / 100;
      return a < 0.06 ? '' : `style="--dcf-heat:${a}" data-side="${r > 0 ? 'above' : 'below'}"`;
    };
    return `<div class="dcf-tabs" role="tablist">${tabs.map(([k, label]) => `<button type="button" role="tab"
        aria-selected="${k === t}" class="dcf-tab${k === t ? ' is-on' : ''}" data-dcf-tab="${k}">${esc(label)}</button>`).join('')}</div>
      <div class="dcf-heat-wrap"><table class="data dcf-heat">
        <caption class="sr-only">${esc(g.row_label)} down, ${esc(g.col_label)} across, value per share</caption>
        <thead><tr><th scope="col">${esc(g.row_label)} ↓ / ${esc(g.col_label)} →</th>
          ${g.cols.map((c, j) => `<th scope="col"${j === 2 ? ' class="is-base"' : ''}>${esc(fmtAxis('col', c))}</th>`).join('')}</tr></thead>
        <tbody>${g.rows.map((r, i) => `<tr><th scope="row"${i === 2 ? ' class="is-base"' : ''}>${esc(fmtAxis('row', r))}</th>
          ${g.values[i].map((v, j) => `<td class="${i === 2 && j === 2 ? 'is-centre' : ''}" ${shade(v)}
            title="${has(v) ? esc(`${money(v)} a share`) : 'Not meaningful: growth at or above the discount rate'}">${has(v) ? money(v) : '—'}</td>`).join('')}</tr>`).join('')}
        </tbody></table></div>
      <p class="caveat">Outlined: the current assumptions. Shaded by how far each value sits from today's price of
        ${money(price)}: <span class="dcf-swatch" data-side="above"></span> above,
        <span class="dcf-swatch" data-side="below"></span> below. A dash means growth would reach the discount rate.</p>`;
  }

  function heatTable(g, price) {
    const shade = (v) => {
      if (!has(v) || !has(price)) return '';
      const r = Math.max(-1, Math.min(1, (v / price - 1) / 0.5));
      const a = Math.round(Math.abs(r) * 100) / 100;
      return a < 0.06 ? '' : `style="--dcf-heat:${a}" data-side="${r > 0 ? 'above' : 'below'}"`;
    };
    return `<div class="dcf-heat-wrap"><table class="data dcf-heat">
      <caption class="sr-only">${esc(g.row_label)} down, ${esc(g.col_label)} across, value per share</caption>
      <thead><tr><th scope="col">${esc(g.row_label)} ↓ / ${esc(g.col_label)} →</th>
        ${g.cols.map((c, j) => `<th scope="col"${j === 2 ? ' class="is-base"' : ''}>${esc(pct(c, 1))}</th>`).join('')}</tr></thead>
      <tbody>${g.rows.map((r, i) => `<tr><th scope="row"${i === 2 ? ' class="is-base"' : ''}>${esc(pct(r, 1))}</th>
        ${g.values[i].map((v, j) => `<td class="${i === 2 && j === 2 ? 'is-centre' : ''}" ${shade(v)}>${has(v) ? money(v) : '—'}</td>`).join('')}</tr>`).join('')}
      </tbody></table></div>
      <p class="caveat">Outlined: the current assumptions. Shaded by distance from today's price of ${money(price)}:
        <span class="dcf-swatch" data-side="above"></span> above, <span class="dcf-swatch" data-side="below"></span> below.</p>`;
  }

  function scenarioTable(d) {
    const sc = d.scenarios || {};
    if (!sc.base) return '';
    const cases = ['bear', 'base', 'bull'];
    const row = (label, fn) => `<tr><th scope="row">${esc(label)}</th>${cases.map((c) => `<td>${sc[c] ? fn(sc[c]) : '—'}</td>`).join('')}</tr>`;
    const dr = (c) => c.drivers || {};
    return `<section class="dcf-sec" aria-labelledby="dcf-h-sc"><h3 id="dcf-h-sc">Bear, base and bull</h3>
      <p class="dcf-note">The cases move growth, margins, capex and the long run together, by the same amount in each
        direction, so the base case is not quietly the optimistic end of the range.</p>
      <table class="data dcf-sc"><thead><tr><th></th><th scope="col">Bear</th><th scope="col">Base</th><th scope="col">Bull</th></tr></thead>
      <tbody>
        ${row('Value per share', (c) => `<strong>${money(c.per_share)}</strong>`)}
        ${row('Versus price', (c) => signedPct(c.upside))}
        ${row('Revenue growth, first year', (c) => pct(dr(c).growth && dr(c).growth.y1))}
        ${row('Operating margin it settles at', (c) => pct(dr(c).margin && dr(c).margin.target))}
        ${row('Capex it settles at', (c) => pct(dr(c).capex_pct && dr(c).capex_pct.target))}
        ${row('Growth after the forecast', (c) => pct(dr(c).terminal && dr(c).terminal.growth))}
        ${row('Return on new capital, long run', (c) => pct(dr(c).terminal && dr(c).terminal.ronic))}
        ${row('Terminal value share', (c) => pct(c.terminal_share, 0))}
      </tbody></table>
      <ul class="dcf-notes">${cases.map((c) => `<li><strong>${c[0].toUpperCase() + c.slice(1)}:</strong> ${esc((d.scenario_text || {})[c] || '')}</li>`).join('')}</ul>
      ${(d.what_ifs || []).length ? `<h4>Single changes people ask about</h4><ul class="dcf-notes">${d.what_ifs.map((w) => `<li>${esc(w.label)}:
        <strong>${money(w.per_share)}</strong> (${signedPct(w.change, 1)} against the base value).</li>`).join('')}</ul>` : ''}
    </section>`;
  }

  function forecastHTML(d) {
    const dcf = d.dcf;
    const r = dcf.rows;
    const tv = dcf.terminal;
    const line = (label, fn, cls) => `<tr${cls ? ` class="${cls}"` : ''}><th scope="row">${esc(label)}</th>${r.map((y) => `<td>${fn(y)}</td>`).join('')}</tr>`;
    return `<p class="dcf-note">Fiscal years ending ${esc(day(r[0].fiscal_year_end))} onward. ${dcf.timing.stub_fraction < 0.999
      ? `The first year counts ${pct(dcf.timing.stub_fraction, 0)} of its cash flow: the balance sheet is from ${esc(day(d.inputs.balance_date))}, so only the part after it is new.` : ''}
      Discounting: ${dcf.timing.convention === 'mid_year' ? 'mid-year (each year’s cash arrives at its middle)' : 'end of year'}, at ${pct(dcf.discount_rate, 2)}.
      D&A ${dcf.da_method === 'ppe' ? 'follows net PP&E (depreciation rate × last year’s PP&E)' : 'is a share of revenue'}.</p>
      ${trailingNote(d)}
      <div class="dcf-scroll"><table class="data dcf-fc">
        <thead><tr><th scope="col">Year</th>${r.map((y) => `<th scope="col">${esc(String(y.fiscal_year_end).slice(0, 4))}</th>`).join('')}</tr></thead>
        <tbody>
          ${line('Revenue', (y) => bigMoney(y.revenue))}
          ${line('Growth', (y) => pct(y.revenue_growth))}
          ${line('Operating margin', (y) => pct(y.ebit_margin))}
          ${line('EBIT', (y) => bigMoney(y.ebit))}
          ${line('Taxes on EBIT', (y) => bigMoney(-y.taxes))}
          ${line('NOPAT', (y) => bigMoney(y.nopat))}
          ${line('+ D&A', (y) => bigMoney(y.da))}
          ${line('− Capex', (y) => bigMoney(-y.capex))}
          ${line('− Change in working capital', (y) => bigMoney(-y.change_nwc))}
          ${line('Free cash flow to the firm', (y) => `<strong>${bigMoney(y.fcff)}</strong>`, 'is-total')}
          ${line('Share of year counted', (y) => pct(y.counted_fraction, 0))}
          ${line('Discount factor', (y) => fmt(y.discount_factor, 3))}
          ${line('Present value', (y) => bigMoney(y.pv))}
          ${line('Return on invested capital', (y) => pct(y.roic))}
        </tbody></table></div>
      <p><strong>Terminal value</strong> (${tv.method === 'value_driver' ? 'value driver' : 'growing last cash flow'}):
        ${tv.method === 'value_driver'
    ? `NOPAT next year ${bigMoney(tv.nopat_next)} × (1 − ${pct(tv.growth)} ÷ ${pct(tv.ronic)}) = ${bigMoney(tv.fcff_next)}, reinvesting ${pct(tv.reinvestment_rate, 0)} of profit to grow ${pct(tv.growth)} a year`
    : `${bigMoney(tv.fcff_next)} next year${has(tv.implied_ronic) ? `, which implies a ${pct(tv.implied_ronic, 0)} return on new capital` : ''}`},
        ÷ (${pct(tv.rate, 2)} − ${pct(tv.growth)}) = ${bigMoney(tv.value)}, worth ${bigMoney(tv.pv)} today.
        That is ${has(tv.implied_exit_ev_ebitda) ? `${fmt(tv.implied_exit_ev_ebitda, 1)}× the last year’s EBITDA` : 'not a positive multiple of EBITDA'}.</p>
      ${dcf.exit_check ? `<p><strong>Exit-multiple cross-check:</strong> at ${fmt(dcf.exit_check.multiple, 1)}× EBITDA (today's
        market multiple), the value would be ${money(dcf.exit_check.per_share)} a share${has(dcf.exit_check.implied_growth)
    ? `, which a perpetuity reaches only with ${pct(dcf.exit_check.implied_growth)} growth forever` : ''}. Using the market's own
        multiple is circular, which is why it is a check and not the answer.</p>` : ''}`;
  }

  /* The latest four quarters beside the base year, so a reader can see how
   * the first forecast year is tracking. Built from reported figures only:
   * fiscal year + this year to date - the same months a year earlier. */
  function trailingNote(d) {
    const t = (d.inputs || {}).trailing || {};
    if (!t.available) return t.reason ? `<p class="dcf-note">Trailing year: ${esc(t.reason)}</p>` : '';
    const v = t.values || {};
    const g1 = (((d.assumptions || {}).drivers || {}).growth || {}).y1;
    return `<p class="dcf-note"><strong>Trailing twelve months to ${esc(day(t.period_end))}:</strong> revenue ${bigMoney((v.revenue || {}).value)}
      (${signedPct(t.revenue_change_vs_fy0, 1)} on the fiscal year to ${esc(day(t.fy0_end))}), operating margin ${pct(t.ebit_margin)}.
      The forecast starts from the fiscal year and assumes ${pct(g1)} growth in the first year, so the two can be compared directly.
      Built as the fiscal year + this year to date − the same months a year earlier, each from the filings.</p>`;
  }

  function waccHTML(d) {
    const w = d.dcf.wacc;
    const p = (d.assumptions || {}).wacc || {};
    const rf = (d.inputs || {}).risk_free || {};
    if (w.override) return `<p>The discount rate is set directly at ${pct(w.wacc, 2)}.</p>`;
    const rating = p.rating || {};
    return `<table class="data narrow"><tbody>
      <tr><th scope="row">Risk-free rate ${kindChip('market')}</th><td>${pct(w.risk_free, 2)}</td><td>${esc(rf.source || '')}${rf.as_of ? `, ${esc(day(rf.as_of))}` : ''}</td></tr>
      <tr><th scope="row">Beta ${kindChip('market')}</th><td>${fmt(w.beta, 2)}</td><td>Raw ${fmt(w.beta_raw, 2)}: ${esc((((d.inputs || {}).quote || {}).beta_meta || {}).source || 'the quote feed')} (a regression on past returns, so an estimate), ${p.beta_adjust === 'raw' ? 'used as is' : 'adjusted toward 1 (Blume: 0.67 × raw + 0.33), since measured betas drift toward the market’s over time'}.</td></tr>
      <tr><th scope="row">Equity risk premium ${kindChip('assumption')}</th><td>${pct(w.erp, 2)}</td><td>Damodaran's implied premium for the S&amp;P 500, January 2026. An estimate, not an observable fact.</td></tr>
      ${w.extra_premium ? `<tr><th scope="row">Extra premium</th><td>${pct(w.extra_premium, 2)}</td><td>Yours.</td></tr>` : ''}
      <tr class="is-total"><th scope="row">Cost of equity</th><td>${pct(w.cost_equity, 2)}</td><td>Risk-free + beta × premium (CAPM).</td></tr>
      <tr><th scope="row">Pre-tax cost of debt ${kindChip(p.kd_source === 'filing_implied' ? 'derived' : 'assumption')}</th><td>${pct(w.pre_tax_cost_debt, 2)}</td><td>${p.kd_source === 'filing_implied'
    ? `Interest expense ÷ debt from the filings (${pct(p.implied_cost_debt, 2)}): with operating losses, an interest-coverage rating is undefined.`
    : `Risk-free + a ${pct(rating.spread, 2)} spread for a synthetic ${esc(rating.rating || '')} rating${has(rating.coverage) ? ` (operating income covers interest ${fmt(rating.coverage, 1)}×)` : ''}. Damodaran's table, January 2026.${has(p.implied_cost_debt) ? ` The filings' interest ÷ debt is ${pct(p.implied_cost_debt, 2)}, which reflects older coupons.` : ''}`}</td></tr>
      <tr><th scope="row">After-tax cost of debt</th><td>${pct(w.after_tax_cost_debt, 2)}</td><td>× (1 − ${pct(w.tax_rate, 0)}).</td></tr>
      <tr><th scope="row">Weights</th><td>${pct(w.weight_equity, 1)} / ${pct(w.weight_debt, 1)}</td><td>${has(w.equity_market_value)
    ? `Equity at market value (${bigMoney(w.equity_market_value)}), debt and finance leases at book (${bigMoney(w.debt_book_value)}). Gross debt, because cash is counted separately in the bridge.` : 'Your debt weight.'}</td></tr>
      <tr class="is-total"><th scope="row">Discount rate (WACC)</th><td><strong>${pct(w.wacc, 2)}</strong></td><td>Equity weight × cost of equity + debt weight × after-tax cost of debt.</td></tr>
    </tbody></table>`;
  }

  function factLink(f) {
    if (!f) return '';
    const bits = [];
    if (f.tag) bits.push(esc(f.tag));
    if (f.form) bits.push(esc(f.form));
    if (f.end) bits.push(esc(day(f.end)));
    const label = bits.join(' · ');
    const note = f.note || f.reason || f.rule || '';
    return `${f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener">${label || 'filing'}</a>` : label}
      ${f.restated ? ' <span class="dcf-kind">restated</span>' : ''}${note ? `<span class="muted"> ${esc(note)}</span>` : ''}`;
  }

  function bridgeHTML(d) {
    const br = d.dcf.bridge;
    const facts = (d.inputs || {}).bridge || {};
    const sh = (d.inputs || {}).shares || {};
    const op = (d.inputs || {}).operating_lease;
    return `<div class="dcf-scroll"><table class="data dcf-bridge"><tbody>
      ${br.lines.map((l) => `<tr class="${l.key === 'enterprise_value' ? 'is-total' : ''}${l.included === false && l.value !== null ? ' is-off' : ''}">
        <th scope="row">${l.key === 'enterprise_value' ? '' : l.sign > 0 ? '+ ' : '− '}${esc(l.label)}</th>
        <td>${l.value === null ? 'not reported' : bigMoney(l.value)}</td>
        <td>${l.key === 'enterprise_value' ? 'Present value of the forecast and the terminal value' : factLink(facts[l.key])}
          ${l.key !== 'enterprise_value' && l.value !== null ? `<label class="dcf-inc"><input type="checkbox" data-dcf-bridge="${esc(l.key)}"${l.included === false ? '' : ' checked'}> count it</label>` : ''}</td></tr>`).join('')}
      <tr class="is-total"><th scope="row">Equity value</th><td>${bigMoney(d.dcf.equity_value)}</td><td></td></tr>
      <tr><th scope="row">÷ Diluted shares</th><td>${fmtCompact(d.dcf.shares, 2)}</td><td>${esc(sh.method || '')}. ${esc(sh.note || '')}</td></tr>
      <tr class="is-total"><th scope="row">Value per share</th><td><strong>${money(d.dcf.per_share)}</strong></td><td></td></tr>
    </tbody></table></div>
    <ul class="dcf-notes">
      <li><strong>Operating leases</strong>${op && has(op.value) ? ` (${bigMoney(op.value)})` : ''} are not subtracted: their cost is already inside EBIT. Subtracting the liability as well would charge them twice.</li>
      <li><strong>Stock-based compensation</strong> is left in EBIT as an expense and not added back. Awards already granted are in the diluted share count; future grants are paid for through that expense.</li>
      <li><strong>Cash</strong> is all treated as surplus; a business that needs some cash to operate is worth slightly less than this.</li>
      <li>Investments, preferred stock and non-controlling interests are at book value; a listed stake's market value can differ a lot.</li>
    </ul>`;
  }

  function statementsHTML(d) {
    const ts = d.three_statement || {};
    if (!ts.available) return `<p class="caveat">${esc(ts.reason || 'Not available.')}</p>`;
    const y = ts.years;
    const line = (label, k, cls) => `<tr${cls ? ` class="${cls}"` : ''}><th scope="row">${esc(label)}</th>${y.map((r) => `<td>${bigMoney(r[k])}</td>`).join('')}</tr>`;
    const head = `<tr><th></th>${y.map((r) => `<th scope="col">Year ${r.year}</th>`).join('')}</tr>`;
    return `<p class="callout ${ts.balances ? 'info' : 'bad'}"><strong>${esc(ts.label)}.</strong> ${ts.balances
      ? 'Assets equal liabilities plus equity in every year (largest gap ' + bigMoney(ts.max_imbalance) + ').'
      : 'The balance sheet does not balance: ' + bigMoney(ts.max_imbalance) + '. Treat these statements as unreliable.'}
      ${ts.reconciles_with_dcf ? 'Free cash flow from these statements equals the DCF’s every year.' : esc(ts.reconcile_note || '')}</p>
      <div class="dcf-scroll"><table class="data dcf-fc"><thead>${head}</thead><tbody>
        <tr class="dcf-sub"><th colspan="${y.length + 1}">Income statement</th></tr>
        ${line('Revenue', 'revenue')}${line('EBIT', 'ebit')}${line('Interest expense', 'interest_expense')}
        ${line('Interest income', 'interest_income')}${line('Taxes', 'taxes')}${line('Net income', 'net_income', 'is-total')}
        <tr class="dcf-sub"><th colspan="${y.length + 1}">Cash flow</th></tr>
        ${line('Operating cash flow', 'cfo')}${line('Capex', 'cfi')}${line('Dividends', 'dividends')}
        ${line('Buybacks', 'buybacks')}${line('Net borrowing', 'net_borrowing')}${line('Change in cash', 'change_cash', 'is-total')}
        <tr class="dcf-sub"><th colspan="${y.length + 1}">Balance sheet</th></tr>
        ${line('Cash', 'cash')}${line('Net PP&E', 'ppe')}${line('Total assets', 'total_assets', 'is-total')}
        ${line('Debt', 'debt')}${line('Total liabilities', 'total_liabilities')}${line('Equity', 'equity', 'is-total')}
        ${line('Assets − liabilities − equity', 'balance_check')}
      </tbody></table></div>
      <ul class="dcf-notes">${(ts.notes || []).map((n) => `<li>${esc(n)}</li>`).join('')}
        <li>Starting balance sheet ${esc(day(ts.start.date))}: other assets and other liabilities are what remains of the reported totals, so the start balances by construction${has(ts.start.unexplained_equity) && Math.abs(ts.start.unexplained_equity) > 1 ? `; reported equity differs from assets less liabilities by ${bigMoney(ts.start.unexplained_equity)} (temporary or mezzanine equity)` : ''}.</li></ul>`;
  }

  function methodsHTML(sym, d) {
    const c = d.classification || {};
    const fits = c.models || {};
    const order = ['dcf', 'fcfe', 'ddm', 'residual_income', 'reit_ffo', 'comps', 'sotp', 'reverse_dcf'];
    const word = { primary: 'Fits', supporting: 'Supporting', limited: 'Limited', not_applicable: 'Does not apply' };
    const extra = {
      fcfe: () => d.fcfe && d.fcfe.available ? `${money(d.fcfe.per_share)} a share at a ${pct(d.fcfe.cost_equity, 2)} cost of equity. ${esc((d.fcfe.notes || []).join(' '))}` : (d.fcfe ? esc(d.fcfe.reason || '') : ''),
      ddm: () => d.ddm && d.ddm.available ? `${money(d.ddm.per_share)} a share: dividends of ${money(d.ddm.dps0)} growing ${pct(d.ddm.growth_high)} for five years, then ${pct(d.ddm.growth_terminal)}, at ${pct(d.ddm.cost_equity, 2)}. ${esc(d.ddm.growth_note || '')}` : (d.ddm ? esc(d.ddm.reason || '') : ''),
      residual_income: () => {
        const r = d.residual_income;
        if (!r) return '';
        if (!r.available) return esc(r.reason || '');
        return `${money(r.per_share)} a share: book value ${money(r.book_value_0)} plus the value of a ${pct(r.roe_start)} return on equity
          against a ${pct(r.cost_equity, 2)} cost, fading to ${pct(r.roe_terminal)}. Today's price is ${fmt(r.price_to_book, 2)}× book, which in
          perpetuity needs a ${pct(r.implied_roe)} return on equity. ${esc((r.notes || []).join(' '))}
          ${(r.flags || []).map((f) => `<strong>Check:</strong> ${esc(f)}`).join(' ')}`;
      },
      reit_ffo: () => {
        const r = d.reit;
        if (!r) return '';
        if (!r.available) return esc(r.reason || '');
        return `FFO ${money(r.ffo_per_share)} a share; the price is ${fmt(r.price_to_ffo, 1)}× FFO, and dividends take ${pct(r.ffo_payout, 0)} of FFO.
          ${r.own_history ? `At the multiples of the last few years (${fmt(r.own_history.low, 1)}× to ${fmt(r.own_history.high, 1)}×, median ${fmt(r.own_history.median, 1)}×), today's FFO is worth ${money(r.own_history.per_share_low)} to ${money(r.own_history.per_share_high)}. ${esc(r.own_history.note)}` : ''}
          ${esc(r.affo_reason || '')}`;
      },
      comps: () => compsHTML(sym),
      sotp: () => sotpHTML(sym),
    };
    return `<p class="dcf-note">${esc(c.label || '')}. Which methods suit this business, and why. Values from different
      methods answer different questions, so they are shown side by side and never averaged.</p>
      <ul class="dcf-methods">${order.filter((k) => fits[k]).map((k) => `<li class="dcf-m-${esc(fits[k].fit)}">
        <strong>${esc(fits[k].name)}</strong> <span class="dcf-fit">${esc(word[fits[k].fit] || '')}</span>
        <div>${esc(fits[k].why)}</div>${extra[k] ? `<div class="dcf-m-out">${extra[k]()}</div>` : ''}</li>`).join('')}</ul>`;
  }

  function compsHTML(sym) {
    const c = VAL.comps[sym];
    const ask = `<button type="button" class="btn" data-dcf-comps>${c && c.available ? 'Compare again' : 'Compare with peers'}</button>
      <span class="muted">Peers (optional, comma-separated):
      <input type="text" class="dcf-peers" id="dcf-peers" placeholder="e.g. ORCL, ADBE, CRM" aria-label="Peer tickers"
        value="${esc(c && c.peer_source === 'reader' ? (c.peers || []).map((p) => p.symbol).join(', ') : '')}"></span>`;
    if (!c) return `${ask}<p class="muted">Without a list, the largest companies in the same industry within 25× of its size, the eight closest.</p>`;
    if (c.loading) return loadingHTML('peer multiples');
    if (!c.available) return `${ask}<p>${esc(c.reason || 'No peers.')}</p>`;
    const mult = (v) => (has(v) && v > 0 ? `${fmt(v, 1)}×` : '—');
    return `${ask}
      <p class="muted">${esc(c.note)} Source: ${esc(c.source)}. Peers: ${esc(c.peer_source === 'reader' ? 'yours' : c.peer_source === 'industry_and_sector'
  ? 'the industry’s largest within the size band, with the sector’s largest added because the industry has too few of this size'
  : 'the industry’s largest within the size band')}.</p>
      ${(c.flags || []).length ? `<p class="callout info"><strong>Peers disagree widely.</strong> ${c.flags.map(esc).join(' ')} Read these values as a range, not an answer, or enter peers you consider comparable above.</p>` : ''}
      <div class="dcf-scroll"><table class="data"><thead><tr><th>Multiple</th><th>${esc(sym)}</th><th>Peers: 25th / median / 75th</th><th>Implied per share</th></tr></thead><tbody>
      ${c.implied.map((i) => `<tr><th scope="row">${esc(i.label)}</th><td>${mult(i.own_multiple)}</td>
        <td>${i.implied ? `${mult(i.implied.low.multiple)} / ${mult(i.implied.mid.multiple)} / ${mult(i.implied.high.multiple)}` : '—'}
          <span class="muted">${esc(String(i.peers_with_value))} peers${(i.outliers || []).length ? `; set aside as outliers: ${esc(i.outliers.join(', '))}` : ''}</span></td>
        <td>${i.implied ? `${money(i.implied.low.per_share)} – <strong>${money(i.implied.mid.per_share)}</strong> – ${money(i.implied.high.per_share)}` : esc(i.reason || '')}
          ${i.note ? `<span class="muted">${esc(i.note)}</span>` : ''}</td></tr>`).join('')}
      </tbody></table></div>
      <div class="dcf-scroll"><table class="data"><thead><tr><th>Peer</th><th>Market value</th><th>EV / EBITDA</th><th>EV / revenue</th><th>P / E</th><th>P / B</th></tr></thead><tbody>
      ${c.peers.map((p) => `<tr><th scope="row">${esc(p.symbol)} <span class="muted">${esc(p.name || '')}${p.origin === 'sector' ? ' · sector peer' : ''}</span></th><td>${bigMoney(p.market_cap)}</td>
        <td>${mult(p.ev_ebitda)}</td><td>${mult(p.ev_revenue)}</td><td>${mult(p.pe)}</td><td>${mult(p.pb)}</td></tr>`).join('')}
      ${(c.excluded || []).map((p) => `<tr class="is-off"><th scope="row">${esc(p.symbol)}</th><td colspan="5" class="muted">Not used: ${esc(p.why)}</td></tr>`).join('')}
      </tbody></table></div>`;
  }

  function sotpHTML(sym) {
    const r = VAL.sotp[sym];
    if (!r) return `<button type="button" class="btn" data-dcf-sotp>Value the segments</button>
      <span class="muted">Reads segment operating income from the last four quarterly filings.</span>`;
    if (r.loading) return loadingHTML('segment filings');
    if (!r.available) return esc(r.reason || 'Not available.');
    const per = r.period || {};
    const rec = r.reconciles === true ? `The parts add up to the company's operating income for the same year (${bigMoney(r.company_ebit_fy0)}).`
      : r.reconciles === false ? `The parts add up to ${bigMoney(r.segments_ttm_total)} against operating income of ${bigMoney(r.company_ebit_fy0)}, so a line is missing or counted twice; treat the result with care.` : '';
    return `<p class="muted">${esc(r.note)} ${esc(r.period_note || '')} ${rec}
      ${per.kind === 'trailing_four_quarters' && r.q4_derived ? 'A fourth quarter is derived as the year less the first three.' : ''}</p>
      <table class="data narrow dcf-sotp"><thead><tr><th>${esc(r.axis_label || 'Segment')}</th><th>Operating income, ${per.kind === 'fiscal_year' ? `fiscal year to ${esc(day(per.end))}` : 'last 4 quarters'}</th><th>EV / EBIT</th><th>Value</th></tr></thead><tbody>
      ${r.segments.map((g) => `<tr><th scope="row">${esc(g.name)}</th><td>${bigMoney(g.operating_income)}</td>
        <td>${has(g.operating_income) ? `<input type="text" inputmode="decimal" class="dcf-ovin" data-dcf-sotp-m="${esc(g.name)}" value="${has(g.multiple) ? fmt(g.multiple, 1) : ''}" aria-label="${esc(`EV/EBIT for ${g.name}`)}">×` : esc(g.note || '')}</td>
        <td>${bigMoney(g.value)}</td></tr>`).join('')}
      <tr><th scope="row">Corporate and eliminations</th><td>${bigMoney(r.unallocated)}</td>
        <td><input type="text" inputmode="decimal" class="dcf-ovin" data-dcf-sotp-u value="${fmt(r.unallocated_value && r.unallocated ? r.unallocated_value / r.unallocated : r.dcf_implied_ev_ebit, 1)}" aria-label="EV/EBIT for unallocated costs">×</td>
        <td>${bigMoney(r.unallocated_value)}</td></tr>
      <tr class="is-total"><th scope="row">Enterprise value</th><td>${bigMoney(r.segments_ttm_total)}</td><td></td><td>${bigMoney(r.enterprise_value)}</td></tr>
      <tr class="is-total"><th scope="row">Value per share (same bridge as the DCF)</th><td></td><td></td><td><strong>${money(r.per_share)}</strong></td></tr>
      </tbody></table>
      <p class="muted">Multiples start at the DCF's implied ${fmt(r.dcf_implied_ev_ebit, 1)}× EV/EBIT, which reproduces the whole; change the segments you think are worth more or less.
        <button type="button" class="btn" data-dcf-sotp-run>Recalculate</button></p>`;
  }

  async function loadSotp(sym, withInputs) {
    const body = {};
    if (withInputs) {
      body.multiples = {};
      document.querySelectorAll('[data-dcf-sotp-m]').forEach((el) => { body.multiples[el.getAttribute('data-dcf-sotp-m')] = el.value.trim(); });
      const u = document.querySelector('[data-dcf-sotp-u]');
      if (u) body.unallocated_multiple = u.value.trim();
    }
    VAL.sotp[sym] = withInputs ? VAL.sotp[sym] : { loading: true };
    VAL.open.methods = true;
    paintResults(sym);
    try {
      VAL.sotp[sym] = await send('POST', `/api/valuation/${encodeURIComponent(sym)}/sotp`, body);
    } catch (err) {
      VAL.sotp[sym] = { available: false, reason: err.message };
    }
    paintResults(sym);
  }

  function sourcesHTML(d) {
    const h = (d.inputs || {}).history || [];
    if (!h.length) return '';
    const rows = [['Revenue', 'revenue'], ['Operating income', 'operating_income'], ['Pre-tax income', 'pretax_income'],
      ['Income tax', 'income_tax'], ['Net income', 'net_income'], ['D&A', 'da'], ['Capex', 'capex'],
      ['Operating cash flow', 'cfo'], ['Stock compensation', 'sbc'], ['Interest expense', 'interest_expense'],
      ['Dividends paid', 'dividends_paid'], ['Buybacks', 'buybacks']];
    const ratios = [['Revenue growth', 'revenue_growth'], ['Operating margin', 'ebit_margin'], ['Effective tax rate', 'effective_tax_rate'],
      ['Capex / revenue', 'capex_pct'], ['Working capital / revenue', 'nwc_pct'], ['Return on invested capital', 'roic'],
      ['FCFF (rebuilt)', 'fcff', 'money'], ['Operating cash flow − capex', 'fcf_simple', 'money'],
      ['Tagged restructuring and impairment', 'unusual_items', 'money'], ['Operating margin excluding them', 'ebit_margin_normalized'],
      ['Acquisitions / revenue', 'acquisitions_pct']];
    const cell = (f) => (f && has(f.value) ? `<td title="${esc([f.tag, f.form, f.filed && `filed ${f.filed}`].filter(Boolean).join(' · '))}">${f.url
      ? `<a href="${esc(f.url)}" target="_blank" rel="noopener">${bigMoney(f.value)}</a>` : bigMoney(f.value)}${f.restated ? '*' : ''}</td>` : '<td class="muted">not reported</td>');
    return `<p class="dcf-note">Fiscal years from the company's 10-K filings (SEC EDGAR, US-GAAP XBRL). Each figure links to its filing;
      hover for the tag. * restated in a later filing (the latest figure is used). Filings retrieved ${esc(when((d.inputs || {}).retrieved))}.</p>
      <div class="dcf-scroll"><table class="data dcf-fc"><thead><tr><th></th>${h.map((y) => `<th scope="col">FY ${esc(y.fy_end.slice(0, 4))}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(([label, k]) => `<tr><th scope="row">${esc(label)}</th>${h.map((y) => cell(y.facts[k])).join('')}</tr>`).join('')}
        <tr class="dcf-sub"><th colspan="${h.length + 1}">Derived (reported figures, same periods)</th></tr>
        ${ratios.map(([label, k, kind]) => `<tr><th scope="row">${esc(label)}</th>${h.map((y) => `<td>${kind === 'money' ? bigMoney(y.derived[k]) : pct(y.derived[k])}</td>`).join('')}</tr>`).join('')}
      </tbody></table></div>
      <p class="caveat">Restructuring and impairment are only what the filings tag under standard names; a charge tagged
        with the company's own label is not caught, so the normalised margin is a partial adjustment and never the default.</p>
      <p class="caveat">${esc((d.inputs || {}).source_note || '')} Rebuilt FCFF uses the reported working-capital change, which can swing with one-off items; the forecast holds working capital at a steady share of revenue instead.</p>`;
  }

  function formulasHTML() {
    return `<ul class="dcf-notes dcf-formulas">
      <li><strong>Free cash flow to the firm</strong> = EBIT × (1 − tax rate) + D&amp;A − capex − change in operating working capital.</li>
      <li><strong>Operating working capital</strong> = (current assets − cash − short-term investments) − (current liabilities − current debt − current lease liabilities).</li>
      <li><strong>Taxes</strong> apply to EBIT; a loss carries forward and shelters later profit. Interest's tax saving sits in the discount rate instead.</li>
      <li><strong>D&amp;A</strong> = depreciation rate × last year's net PP&amp;E; PP&amp;E grows by capex less D&amp;A.</li>
      <li><strong>Discounting</strong>: factor = (1 + WACC)<sup>−t</sup>, t in fiscal years from the valuation date; mid-year puts each flow at its year's middle. The first year counts only the part after the balance sheet.</li>
      <li><strong>Terminal value</strong> = NOPAT<sub>N+1</sub> × (1 − g ÷ RONIC) ÷ (WACC − g), valued at the end of year N (half a year sooner under mid-year). Growth at or above WACC is refused.</li>
      <li><strong>Equity</strong> = enterprise value + cash + investments − debt − finance leases − preferred − non-controlling interests − unfunded pensions. <strong>Per share</strong> = equity ÷ diluted shares.</li>
      <li><strong>WACC</strong> = E/V × (r<sub>f</sub> + β × ERP) + D/V × r<sub>d</sub> × (1 − t).</li>
      <li><strong>Upside</strong> = value ÷ price − 1. <strong>Margin of safety</strong> = 1 − price ÷ value.</li>
      <li><strong>Residual income</strong>: value = book + Σ (ROE − r<sub>e</sub>) × opening book, discounted; justified P/B = (ROE − g) ÷ (r<sub>e</sub> − g).</li>
      <li><strong>Dividend discount</strong>: two stages, dividends discounted at the cost of equity, a growing perpetuity after five years.</li>
      <li>Full notes: app/valuation/METHODS.md in the source.</li></ul>`;
  }

  function miloAsks(d) {
    const name = d.ticker;
    const dcfOk = (d.dcf || {}).available;
    const ri = d.residual_income;
    const qs = !dcfOk ? [
      `Why doesn't a DCF suit ${name}?`,
      ri && ri.available ? `What return on equity does ${name}'s price imply?` : `Which method fits ${name} best, and why?`,
      ri && ri.available ? `Is ${name}'s return on equity sustainable?` : `What does ${name}'s price imply?`,
      `Which assumptions matter most in ${name}'s valuation?`,
    ] : [
      `Why is ${name}'s model value ${(d.dcf || {}).upside < 0 ? 'below' : 'above'} the market price?`,
      `Which assumptions matter most in ${name}'s valuation?`,
      `What happens to ${name}'s value if capital spending stays elevated?`,
      `How much of ${name}'s value comes from the terminal period?`,
      `What growth would justify ${name}'s price today?`,
      `Is a DCF appropriate for ${name}?`,
    ];
    return `<div class="dcf-ask"><span class="muted">Ask Milo about this model:</span>
      ${qs.map((q) => `<button type="button" class="chip" data-ask-text="${esc(q)}">${esc(q)}</button>`).join('')}</div>`;
  }

  /* ------------------------------------------------------------ the form */

  function formStatus(sym, d) {
    const changed = (d.assumptions || {}).changed || [];
    return changed.length
      ? `${changed.length} assumption${changed.length === 1 ? '' : 's'} changed from the defaults. <button type="button" class="auth-link" data-dcf-reset>Reset to defaults</button>`
      : 'All assumptions are at their defaults.';
  }

  function renderForm(sym, d) {
    if (!d.defaults) return '';
    const why = {};
    (d.defaults.rationale || []).forEach((r) => { why[r.key] = r; });
    const changed = new Set((d.assumptions || {}).changed || []);
    const e = editsFor(sym);
    const field = (f) => {
      const cur = fieldValue(d, f, 'current');
      const def = fieldValue(d, f, 'default');
      const w = f.why ? why[f.why] : null;
      const raw = f.wacc ? e.wacc[f.key.slice(5)] : getPath(e.drivers, f.key);
      const typed = raw === undefined ? '' : shown(f, raw);
      return `<label class="dcf-field${changed.has(f.key) ? ' is-edited' : ''}">
        <span class="dcf-flabel">${esc(f.label)} ${w ? kindChip(w.kind) : f.wacc ? '' : ''}</span>
        <span class="dcf-finput"><input type="text" inputmode="decimal" data-dcf-field="${esc(f.key)}" value="${esc(typed)}"
          placeholder="${esc(has(cur) ? shown(f, cur) : (f.blank || ''))}" aria-describedby="dcf-why-${esc(f.key.replace(/\./g, '-'))}">
          <span class="dcf-unit">${esc(f.unit === 'x' ? '×' : f.unit)}</span></span>
        <span class="dcf-fwhy" id="dcf-why-${esc(f.key.replace(/\./g, '-'))}">Default ${esc(has(def) ? shown(f, def) + (f.unit === '%' ? '%' : f.unit === 'x' ? '×' : '') : (f.blank || 'none'))}.
          ${w ? esc(w.why) : ''}</span>
      </label>`;
    };
    const drv = (d.assumptions || {}).drivers || {};
    const openForm = VAL.open.form || ((d.dcf || {}).needs_input && VAL.open.form !== false);
    return `<details class="dcf-more dcf-form" data-dcf-sec="form"${openForm ? ' open' : ''}>
      <summary>Assumptions: see why each was chosen, and change any of them</summary>
      <div class="dcf-more-body">
        <p class="dcf-note">Leave a box empty to use the default shown in grey. Values recalculate as you type. Your changes are
          kept in this browser until you save a model or reset.</p>
        <p class="dcf-status" id="dcf-form-status" role="status">${formStatus(sym, d)}</p>
        ${GROUPS.map((g) => `<fieldset class="dcf-group"><legend>${esc(g)}</legend>${FIELDS.filter((f) => f.group === g).map(field).join('')}</fieldset>`).join('')}
        <fieldset class="dcf-group"><legend>Method</legend>
          <label class="dcf-field"><span class="dcf-flabel">Discounting</span>
            <select data-dcf-select="convention"><option value="mid_year"${drv.convention !== 'end_year' ? ' selected' : ''}>Mid-year (cash arrives through the year)</option>
            <option value="end_year"${drv.convention === 'end_year' ? ' selected' : ''}>End of year</option></select></label>
          <label class="dcf-field"><span class="dcf-flabel">Terminal value</span>
            <select data-dcf-select="terminal.method"><option value="value_driver"${(drv.terminal || {}).method !== 'fcf_growth' ? ' selected' : ''}>Value driver: growth costs reinvestment</option>
            <option value="fcf_growth"${(drv.terminal || {}).method === 'fcf_growth' ? ' selected' : ''}>Grow the last year's cash flow</option></select></label>
          <label class="dcf-field"><span class="dcf-flabel">Beta</span>
            <select data-dcf-select="wacc.beta_adjust"><option value="blume"${((d.assumptions || {}).wacc || {}).beta_adjust !== 'raw' ? ' selected' : ''}>Adjusted toward 1 (Blume)</option>
            <option value="raw"${((d.assumptions || {}).wacc || {}).beta_adjust === 'raw' ? ' selected' : ''}>Raw, as measured</option></select></label>
        </fieldset>
        ${overridesHTML(sym, d)}
        <div class="dcf-save-row">
          <input type="text" id="dcf-save-name" class="dcf-save-name" maxlength="80" placeholder="Name this model (optional)" aria-label="Model name">
          <button type="button" class="btn primary" data-dcf-save>Save a snapshot</button>
          <span class="dcf-status" role="status">${esc(VAL.status[sym] || '')}</span>
        </div>
        <p class="caveat">A snapshot keeps the reported figures, your assumptions and the result together, so it can be rerun
          exactly later. Saving again makes a new snapshot; an earlier one is never changed.
          ${signedIn() ? 'Saved to your account.' : 'Signed out, so snapshots are kept in this browser.'}</p>
      </div></details>`;
  }

  const OVERRIDE_ROWS = [['revenue_growth', 'Revenue growth'], ['ebit_margin', 'Operating margin'], ['capex_pct', 'Capex / revenue']];

  function overridesHTML(sym, d) {
    const rows = ((d.dcf || {}).rows) || [];
    if (!rows.length) return '';
    const ov = ((editsFor(sym).drivers || {}).overrides) || {};
    const key = { revenue_growth: 'revenue_growth', ebit_margin: 'ebit_margin', capex_pct: 'capex_pct' };
    return `<details class="dcf-more" data-dcf-sec="overrides"${VAL.open.overrides ? ' open' : ''}><summary>Set individual years</summary>
      <div class="dcf-more-body dcf-scroll"><table class="data dcf-ov"><thead><tr><th></th>${rows.map((r) => `<th scope="col">${esc(String(r.fiscal_year_end).slice(0, 4))}</th>`).join('')}</tr></thead>
      <tbody>${OVERRIDE_ROWS.map(([k, label]) => `<tr><th scope="row">${esc(label)} %</th>${rows.map((r) => {
    const typed = (ov[k] || {})[String(r.year)];
    return `<td><input type="text" inputmode="decimal" class="dcf-ovin" data-dcf-ov="${k}" data-year="${r.year}"
      value="${has(typed) ? esc(String(Number((typed * 100).toFixed(3)))) : ''}" placeholder="${esc((r[key[k]] * 100).toFixed(1))}"
      aria-label="${esc(`${label}, ${String(r.fiscal_year_end).slice(0, 4)}`)}"></td>`;
  }).join('')}</tr>`).join('')}</tbody></table>
      <p class="caveat">A year you type here wins over the path the drivers above draw. Empty boxes follow the drivers.</p></div></details>`;
  }

  /* ------------------------------------------------------------ saved models */

  async function loadSaved(sym) {
    if (signedIn()) {
      try {
        const body = await getJSON(`/api/valuation-models?symbol=${encodeURIComponent(sym)}`);
        VAL.saved[sym] = { where: 'account', models: body.models || [] };
      } catch (err) {
        VAL.saved[sym] = { where: 'account', models: [], error: err.message };
      }
    } else {
      VAL.saved[sym] = { where: 'browser', models: readStore().models.filter((m) => m.symbol === sym) };
    }
    const host = document.getElementById('dcf-saved');
    if (host && STATE.ticker === sym) host.outerHTML = renderSaved(sym);
  }

  function renderSaved(sym) {
    const s = VAL.saved[sym];
    if (!s || !s.models.length) return `<div id="dcf-saved">${s && s.error ? `<p class="caveat">Saved models could not be loaded (${esc(s.error)}).</p>` : ''}</div>`;
    return `<div id="dcf-saved"><details class="dcf-more" data-dcf-sec="saved"${VAL.open.saved ? ' open' : ''}>
      <summary>Saved models for ${esc(sym)} (${s.models.length})</summary><div class="dcf-more-body">
      <table class="data"><thead><tr><th>Saved</th><th>Name</th><th>Value then</th><th>Inputs as of</th><th>Changed</th><th></th></tr></thead><tbody>
      ${s.models.map((m) => {
    const rp = VAL.replays[m.id];
    return `<tr><td>${esc(when(m.created_at))}</td><td>${esc(m.name || '—')}</td>
        <td>${money((m.result || {}).per_share)}</td>
        <td>${esc(day((m.inputs || {}).balance_date))} balance sheet, price ${money((m.inputs || {}).price)}</td>
        <td>${(m.changed || []).length ? esc(m.changed.join(', ')) : 'defaults'}</td>
        <td><button type="button" class="auth-link" data-dcf-replay="${esc(m.id)}">Rerun exactly</button>
          <button type="button" class="auth-link" data-dcf-use="${esc(m.id)}">Use these assumptions</button>
          <button type="button" class="auth-link" data-dcf-del="${esc(m.id)}">Delete</button>
          ${rp ? `<div class="muted">${rp.error ? esc(rp.error) : `${money(rp.per_share)} ${rp.matches ? '✓ the same as when saved' : '(differs from the saved result)'}${rp.version_changed ? `; the engine has moved from ${esc(rp.saved_version)} to ${esc(rp.engine_version)}` : ''}`}</div>` : ''}</td></tr>`;
  }).join('')}</tbody></table>
      <p class="caveat">"Rerun exactly" uses the reported figures stored with the snapshot. "Use these assumptions" applies them to today's figures.</p>
      </div></details></div>`;
  }

  function snapshot(sym, name) {
    const d = VAL.data[sym];
    return { symbol: sym, name, base: d.base, assumptions: d.assumptions, model_version: d.model_version,
      inputs: d.inputs_digest, result: { per_share: d.dcf.per_share, wacc: d.dcf.wacc.wacc,
        terminal_share: d.dcf.terminal_share, bear: ((d.scenarios || {}).bear || {}).per_share,
        bull: ((d.scenarios || {}).bull || {}).per_share } };
  }

  async function send(method, url, body) {
    const headers = { 'Content-Type': 'application/json' };
    const csrf = window.OpticAuth ? window.OpticAuth.csrf() : '';
    if (csrf) headers['X-Optic-CSRF'] = csrf;
    const res = await fetch(url, { method, headers, credentials: 'same-origin', body: body ? JSON.stringify(body) : undefined });
    const parsed = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(parsed.detail || `HTTP ${res.status}`);
    return parsed;
  }

  async function save(sym) {
    const d = VAL.data[sym];
    if (!d || !d.dcf || !d.dcf.available) { VAL.status[sym] = 'Nothing to save: the model has no result.'; paint(sym); return; }
    const name = ((document.getElementById('dcf-save-name') || {}).value || '').trim();
    const snap = snapshot(sym, name);
    try {
      if (signedIn()) {
        await send('POST', '/api/valuation-models', snap);
      } else {
        const s = readStore();
        s.models.unshift({ ...snap, id: `local-${Date.now()}`, created_at: new Date().toISOString(),
          changed: (snap.assumptions || {}).changed || [], snapshot: snap });
        s.models = s.models.slice(0, MAX_LOCAL_MODELS);
        writeStore(s);
      }
      VAL.status[sym] = `Saved ${new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}.`;
    } catch (err) {
      VAL.status[sym] = `Not saved: ${err.message}`;
    }
    VAL.open.saved = true;
    await loadSaved(sym);
    paint(sym);
  }

  async function modelById(sym, id) {
    if (String(id).startsWith('local-')) return readStore().models.find((m) => m.id === id) || null;
    try { return await getJSON(`/api/valuation-models/${encodeURIComponent(id)}`); } catch (e) { return null; }
  }

  async function replay(sym, id) {
    const m = await modelById(sym, id);
    if (!m) { VAL.replays[id] = { error: 'That model could not be read.' }; paint(sym); return; }
    try {
      VAL.replays[id] = m.replay || await send('POST', '/api/valuation-models/replay', m.snapshot);
    } catch (err) {
      VAL.replays[id] = { error: err.message };
    }
    paint(sym);
  }

  async function useModel(sym, id) {
    const m = await modelById(sym, id);
    if (!m || !m.snapshot) return;
    const a = m.snapshot.assumptions || {};
    VAL.edits[sym] = { drivers: JSON.parse(JSON.stringify(a.drivers || {})), wacc: JSON.parse(JSON.stringify(a.wacc || {})) };
    delete VAL.edits[sym].drivers._deltas;
    await runNow(sym);
    paint(sym);
  }

  async function del(sym, id) {
    if (!window.confirm('Delete this saved model? This cannot be undone.')) return;
    try {
      if (String(id).startsWith('local-')) {
        const s = readStore();
        s.models = s.models.filter((m) => m.id !== id);
        writeStore(s);
      } else {
        await send('DELETE', `/api/valuation-models/${encodeURIComponent(id)}`);
      }
    } catch (err) {
      VAL.status[sym] = `Not deleted: ${err.message}`;
    }
    await loadSaved(sym);
    paint(sym);
  }

  async function loadComps(sym) {
    const peers = ((document.getElementById('dcf-peers') || {}).value || '').trim();
    VAL.comps[sym] = { loading: true };
    VAL.open.methods = true;
    paintResults(sym);
    try {
      VAL.comps[sym] = await getJSON(`/api/valuation/${encodeURIComponent(sym)}/comps${peers ? `?peers=${encodeURIComponent(peers)}` : ''}`);
    } catch (err) {
      VAL.comps[sym] = { available: false, reason: err.message };
    }
    paintResults(sym);
  }

  /* ------------------------------------------------------------ events */

  document.addEventListener('input', (evt) => {
    const t = evt.target;
    if (!t || !t.matches) return;
    const sym = STATE.ticker;
    if (t.matches('[data-dcf-field]')) {
      const f = FIELDS.find((x) => x.key === t.getAttribute('data-dcf-field'));
      if (!f) return;
      const msg = setEdit(sym, f, t.value);
      t.setAttribute('aria-invalid', msg ? 'true' : 'false');
      if (msg) { VAL.errors[sym] = msg; return; }
      schedule(sym);
    } else if (t.matches('[data-dcf-ov]')) {
      const e = editsFor(sym);
      const k = t.getAttribute('data-dcf-ov');
      const y = t.getAttribute('data-year');
      e.drivers.overrides = e.drivers.overrides || {};
      e.drivers.overrides[k] = e.drivers.overrides[k] || {};
      const n = Number(String(t.value).replace(/[,%]/g, ''));
      if (String(t.value).trim() === '') delete e.drivers.overrides[k][y];
      else if (Number.isFinite(n)) e.drivers.overrides[k][y] = n / 100;
      else return;
      schedule(sym);
    }
  });

  document.addEventListener('change', (evt) => {
    const t = evt.target;
    if (!t || !t.matches) return;
    const sym = STATE.ticker;
    if (t.matches('[data-dcf-select]')) {
      const key = t.getAttribute('data-dcf-select');
      const e = editsFor(sym);
      if (key === 'wacc.beta_adjust') e.wacc.beta_adjust = t.value;
      else if (key === 'convention') e.drivers.convention = t.value;
      else if (key === 'terminal.method') { e.drivers.terminal = e.drivers.terminal || {}; e.drivers.terminal.method = t.value; }
      runNow(sym).then(() => paint(sym));
    } else if (t.matches('[data-dcf-bridge]')) {
      const e = editsFor(sym);
      e.drivers.bridge_include = e.drivers.bridge_include || {};
      e.drivers.bridge_include[t.getAttribute('data-dcf-bridge')] = t.checked;
      runNow(sym).then(() => paintResults(sym));
    }
  });

  document.addEventListener('toggle', (evt) => {
    const t = evt.target;
    if (t && t.matches && t.matches('details[data-dcf-sec]')) VAL.open[t.getAttribute('data-dcf-sec')] = t.open;
  }, true);

  document.addEventListener('click', (evt) => {
    const t = evt.target && evt.target.closest ? evt.target : null;
    if (!t) return;
    const sym = STATE.ticker;
    const tab = t.closest('[data-dcf-tab]');
    if (tab) { VAL.tab = tab.getAttribute('data-dcf-tab'); paintResults(sym); return; }
    if (t.closest('[data-dcf-reset]')) {
      VAL.edits[sym] = { drivers: {}, wacc: {} };
      rememberEdits(sym);
      VAL.data[sym] = VAL.defaults[sym] || VAL.data[sym];
      VAL.errors[sym] = '';
      paint(sym);
      return;
    }
    if (t.closest('[data-dcf-save]')) { save(sym); return; }
    if (t.closest('[data-dcf-comps]')) { loadComps(sym); return; }
    if (t.closest('[data-dcf-sotp]')) { loadSotp(sym, false); return; }
    if (t.closest('[data-dcf-sotp-run]')) { loadSotp(sym, true); return; }
    const rp = t.closest('[data-dcf-replay]');
    if (rp) { replay(sym, rp.getAttribute('data-dcf-replay')); return; }
    const use = t.closest('[data-dcf-use]');
    if (use) { useModel(sym, use.getAttribute('data-dcf-use')); return; }
    const dl = t.closest('[data-dcf-del]');
    if (dl) { del(sym, dl.getAttribute('data-dcf-del')); return; }
    const pv = t.closest('[data-milo-val-preview], [data-milo-val-apply], [data-milo-val-undo]');
    if (pv) miloCardPress(pv);
  });

  /* ------------------------------------------------------------ Milo
   *
   * The context Milo is given about the model on screen: inputs with their
   * kinds and sources, the result, what moves it, what the price implies, and
   * the checks. Compact, because the whole context is capped. Numbers only
   * from the server's answer; nothing is recomputed. */

  function context(sym) {
    const d = VAL.data[sym];
    if (!d || !d.available) return d && d.reason ? { ticker: sym, available: false, reason: d.reason } : null;
    const dcf = d.dcf || {};
    const r4 = (x) => (has(x) ? Math.round(x * 10000) / 10000 : x);
    const r2 = (x) => (has(x) ? Math.round(x * 100) / 100 : x);
    const why = {};
    ((d.defaults || {}).rationale || []).forEach((r) => { why[r.key] = r; });
    const changed = new Set((d.assumptions || {}).changed || []);
    const assumptions = FIELDS.map((f) => {
      const v = fieldValue(d, f, 'current');
      const def = fieldValue(d, f, 'default');
      const w = f.why ? why[f.why] : null;
      return { key: f.key, label: f.label, value: f.unit === '%' ? r4(v) : r2(v), default: f.unit === '%' ? r4(def) : r2(def),
        unit: f.unit === '%' ? 'fraction' : f.unit, kind: w ? w.kind : (f.wacc ? 'assumption' : null),
        why: w ? w.why : null, edited_by_reader: changed.has(f.key) };
    }).filter((a) => has(a.value) || has(a.default));
    const out = {
      what: 'Optic fair-value model on the Investing tab. Deterministic: computed by Optic’s engine, not by Milo.',
      model_version: d.model_version, ticker: d.ticker, name: d.name,
      price: (d.market || {}).price, price_as_of: (d.market || {}).as_of,
      inputs_as_of: d.inputs_digest,
      classification: { type: (d.classification || {}).label, confidence: (d.classification || {}).confidence,
        reasons: (d.classification || {}).confidence_reasons,
        models: Object.fromEntries(Object.entries((d.classification || {}).models || {}).map(([k, v]) => [k, { fit: v.fit, why: v.why }])) },
      assumptions,
      warnings: d.warnings,
    };
    if (dcf.available) {
      const w = dcf.wacc || {};
      out.base_case = { value_per_share: r2(dcf.per_share), enterprise_value: dcf.enterprise_value, equity_value: dcf.equity_value,
        upside_vs_price: r4(dcf.upside), margin_of_safety: r4(dcf.margin_of_safety),
        terminal_value_share_of_ev: r4(dcf.terminal_share), pv_forecast_years: dcf.pv_forecast, pv_terminal: (dcf.terminal || {}).pv,
        terminal: { method: (dcf.terminal || {}).method, growth: r4((dcf.terminal || {}).growth), ronic: r4((dcf.terminal || {}).ronic),
          implied_exit_ev_ebitda: r2((dcf.terminal || {}).implied_exit_ev_ebitda) },
        exit_multiple_check: dcf.exit_check ? { multiple: r2(dcf.exit_check.multiple), value_per_share: r2(dcf.exit_check.per_share),
          implied_perpetual_growth: r4(dcf.exit_check.implied_growth) } : null,
        discount_rate: { wacc: r4(w.wacc), cost_equity: r4(w.cost_equity), risk_free: r4(w.risk_free), beta: r2(w.beta),
          beta_raw: r2(w.beta_raw), erp: r4(w.erp), pre_tax_cost_debt: r4(w.pre_tax_cost_debt), weight_debt: r4(w.weight_debt) },
        checks: dcf.checks };
      const rows = dcf.rows || [];
      out.forecast = rows.filter((x, i) => i < 3 || i === rows.length - 1).map((y) => ({ fiscal_year_end: y.fiscal_year_end,
        revenue: y.revenue, growth: r4(y.revenue_growth), ebit_margin: r4(y.ebit_margin), capex: y.capex, da: y.da,
        fcff: y.fcff, roic: r4(y.roic) }));
      out.bridge = (dcf.bridge || {}).lines;
      out.shares = { diluted: dcf.shares, method: ((d.inputs || {}).shares || {}).method };
      out.scenarios = Object.fromEntries(Object.entries(d.scenarios || {}).map(([k, v]) => [k, { value_per_share: r2(v.per_share),
        upside_vs_price: r4(v.upside), deltas_from_base: v.deltas, growth_y1: r4(((v.drivers || {}).growth || {}).y1),
        margin_target: r4(((v.drivers || {}).margin || {}).target), capex_target: r4(((v.drivers || {}).capex_pct || {}).target) }]));
      out.most_sensitive = (d.tornado || []).slice(0, 6).map((b) => ({ assumption: b.label, step_down: b.step_low,
        value_down: r2(b.value_low), step_up: b.step_high, value_up: r2(b.value_high) }));
      out.what_ifs = (d.what_ifs || []).map((x) => ({ change: x.label, value_per_share: r2(x.per_share), vs_base: r4(x.change) }));
      out.reverse_dcf = ((d.reverse || {}).solves || []).map((s) => ({ solved_for: s.label, value: r4(s.value), text: s.text, held_fixed: s.held }));
    } else {
      out.dcf_not_run = dcf.reason;
    }
    ['fcfe', 'ddm', 'residual_income'].forEach((k) => {
      const m = d[k];
      if (m) out[k] = m.available ? { value_per_share: r2(m.per_share), fit: (m.fit || {}).fit } : { available: false, reason: m.reason };
    });
    if (d.reit) out.reit = d.reit.available ? { ffo_per_share: r2(d.reit.ffo_per_share), price_to_ffo: r2(d.reit.price_to_ffo),
      ffo_payout: r4(d.reit.ffo_payout), own_history: d.reit.own_history } : { available: false, reason: d.reit.reason };
    if (d.residual_income && d.residual_income.available) {
      out.residual_income.implied_roe = r4(d.residual_income.implied_roe);
      out.residual_income.roe_start = r4(d.residual_income.roe_start);
      out.residual_income.price_to_book = r2(d.residual_income.price_to_book);
    }
    const tt = (d.inputs || {}).trailing || {};
    if (tt.available) {
      out.trailing_twelve_months = { period_end: tt.period_end, revenue: ((tt.values || {}).revenue || {}).value,
        revenue_change_vs_fiscal_year: r4(tt.revenue_change_vs_fy0), operating_margin: r4(tt.ebit_margin),
        how: 'fiscal year + this year to date - same months a year earlier, from the filings' };
    }
    out.history = ((d.inputs || {}).history || []).slice(0, 3).map((y) => ({ fiscal_year_end: y.fy_end,
      revenue_growth: r4(y.derived.revenue_growth), operating_margin: r4(y.derived.ebit_margin),
      operating_margin_excluding_tagged_charges: r4(y.derived.ebit_margin_normalized),
      capex_share: r4(y.derived.capex_pct), roic: r4(y.derived.roic), acquisitions_share: r4(y.derived.acquisitions_pct) }));
    out.sources = 'Statements: SEC EDGAR XBRL (us-gaap), fiscal years ' + ((d.inputs || {}).fy_ends || []).slice(0, 3).join(', ')
      + '; balance sheet ' + ((d.inputs || {}).balance_date || '') + '. Price and beta: Yahoo Finance quote. Risk-free: FRED DGS10. ERP and credit spreads: Damodaran, January 2026.';
    return out;
  }

  /* Milo proposes a change as [[action valuation KEY=VALUE ... "why"]]. The
   * card shows the change and its effect, computed by the engine, before
   * anything is applied, and applying it touches only the working
   * assumptions on screen, never a saved snapshot. */
  const PROPOSABLE = new Set(FIELDS.map((f) => f.key));

  function parseAction(args) {
    const sym = STATE.ticker;
    const changes = [];
    const words = [];
    (args || []).forEach((a) => {
      const m = /^([a-z_]+(?:\.[a-z_0-9]+)?)=(-?[0-9.]+)(%|x)?$/i.exec(String(a));
      if (m) changes.push({ key: m[1], value: Number(m[2]), unit: m[3] || '' });
      else words.push(a);
    });
    if (!VAL.data[sym] || !VAL.data[sym].available) return { bad: 'there is no valuation model open to change' };
    if (!changes.length) return { bad: 'the proposal named no assumption to change' };
    const clean = [];
    for (const c of changes) {
      const f = FIELDS.find((x) => x.key === c.key);
      if (!f || !PROPOSABLE.has(c.key)) return { bad: `the model has no "${c.key}" assumption` };
      if (!Number.isFinite(c.value)) return { bad: `${c.key} is not a number` };
      const value = f.unit === '%' ? (c.unit === '%' || Math.abs(c.value) > 1.5 ? c.value / 100 : c.value) : c.value;
      clean.push({ key: c.key, label: f.label, value, unit: f.unit });
    }
    const why = words.join(' ').trim().slice(0, 240);
    if (why.length < 4) return { bad: 'a proposed change needs its reason' };
    return { kind: 'valuation', sym, changes: clean, why,
      label: `Try on the ${sym} model: ${clean.map((c) => `${c.label} ${c.unit === '%' ? pct(c.value) : fmt(c.value, 2)}`).join(', ')}` };
  }

  function actionCard(a) {
    return `<div class="milo-act milo-val" data-milo-val="${esc(JSON.stringify(a))}">
      <div class="milo-act-what">${esc(a.label)}</div>
      <div class="milo-act-sub">Milo's reason: ${esc(a.why)}. Nothing changes until you press Apply, and saved models are never changed.</div>
      <div class="milo-val-out" aria-live="polite"></div>
      <div class="milo-act-btns">
        <button type="button" class="btn" data-milo-val-preview>Show the effect</button>
        <button type="button" class="btn primary" data-milo-val-apply disabled>Apply to my working model</button>
      </div></div>`;
  }

  async function miloCardPress(btn) {
    const card = btn.closest('.milo-val');
    if (!card) return;
    let a;
    try { a = JSON.parse(card.dataset.miloVal); } catch (e) { return; }
    const out = card.querySelector('.milo-val-out');
    const sym = a.sym;
    const cur = VAL.data[sym];
    if (!cur || !cur.dcf || !cur.dcf.available) { out.textContent = 'Open the Investing tab for this company first.'; return; }
    const proposed = JSON.parse(JSON.stringify(editsFor(sym)));
    a.changes.forEach((c) => {
      const f = FIELDS.find((x) => x.key === c.key);
      if (f.wacc) proposed.wacc[c.key.slice(5)] = c.value;
      else {
        const [head, tail] = c.key.split('.');
        if (tail) { proposed.drivers[head] = proposed.drivers[head] || {}; proposed.drivers[head][tail] = c.value; }
        else proposed.drivers[head] = c.value;
      }
    });
    if (btn.hasAttribute('data-milo-val-undo')) {
      const prev = card.dataset.prev ? JSON.parse(card.dataset.prev) : { drivers: {}, wacc: {} };
      VAL.edits[sym] = prev;
      await runNow(sym);
      paint(sym);
      out.textContent = 'Put back as it was.';
      btn.remove();
      return;
    }
    if (btn.hasAttribute('data-milo-val-preview')) {
      out.textContent = 'Running the model…';
      try {
        const res = await runNow(sym, proposed);
        const before = cur.dcf.per_share; const after = res.dcf && res.dcf.available ? res.dcf.per_share : null;
        out.innerHTML = after === null ? `The model cannot run with this change: ${esc((res.dcf || {}).reason || '')}`
          : `Base value ${money(before)} → <strong>${money(after)}</strong> (${signedPct(after / before - 1, 1)}); terminal share
            ${pct(cur.dcf.terminal_share, 0)} → ${pct(res.dcf.terminal_share, 0)}. Computed by Optic's engine.`;
        card.querySelector('[data-milo-val-apply]').disabled = after === null;
      } catch (err) { out.textContent = `It did not run: ${err.message}`; }
      return;
    }
    if (btn.hasAttribute('data-milo-val-apply')) {
      card.dataset.prev = JSON.stringify(editsFor(sym));
      VAL.edits[sym] = proposed;
      await runNow(sym);
      paint(sym);
      out.innerHTML = `Applied to your working assumptions. Saved models are unchanged.`;
      btn.disabled = true;
      btn.insertAdjacentHTML('afterend', '<button type="button" class="btn" data-milo-val-undo>Undo</button>');
    }
  }

  window.OpticValuation = { hostHTML, load, context, parseAction, actionCard, _state: VAL, _lede: lede };
}());
