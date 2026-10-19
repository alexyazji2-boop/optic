// The legal text, word for word from static/app.js (LEGAL) and the classic
// footer in static/index.html, so both apps say the same thing. These strings
// are the operator's own markup (strong and em only), drawn with raw(); nothing
// from a server or a reader is ever put into them.
//
// Copying a notice is not the same as being ready to launch: what is still
// open (published Terms and Privacy, email delivery, billing) is listed in
// docs/frontend-v2/LAUNCH-REQUIREMENTS.md, not here.
import { html, raw } from './dom.js';

export const LEGAL = {
  full: [
    'Optic Terminal is an independent research tool. It is not financial, investment, tax or legal advice, and nothing in it is a recommendation, solicitation or offer to buy or sell any security, option or other instrument. It is provided for informational and educational purposes only.',
    'The operator is not a broker-dealer, not a registered investment adviser, and not licensed to give investment advice. No output here is personalised advice. If you link a brokerage account, Optic shows and describes those holdings read-only, but it does not know or assess your wider finances, tax position, time horizon, obligations or risk tolerance, and cannot take them into account.',
    'Every figure is generated from third-party data that may be delayed, incomplete or wrong, and from models whose assumptions are stated but not guaranteed. Verify anything you intend to act on against primary sources.',
    'Trading involves substantial risk of loss and is not suitable for everyone. Options carry additional risks and can expire worthless, losing the entire premium; short positions can lose more than the amount invested. Past performance does not predict future results. You may lose some or all of your capital.',
    'Consult a licensed financial professional before making any investment decision. The operator accepts no liability for any loss arising from use of this tool.',
  ],
  // Per-view notice, naming the specific way that view's output could be taken
  // for advice. Generic boilerplate gets skimmed; a specific sentence doesn't.
  areas: {
    pulse: '<strong>Not financial advice.</strong> Milo states which way the <em>data</em> leans and how strongly. That is a reading of numbers on this screen, not a recommendation for you: it does not know your horizon, capital or tax position, and even with a linked brokerage it describes your holdings rather than judging whether any of this suits you. It can be confidently wrong. The inputs are delayed, several are labelled proxies, and a lean is not a forecast.',
    swing: '<strong>Not a recommendation.</strong> The strikes, limit prices, stops and targets on this tab are model output, not advice to place any trade. Options can expire worthless and lose the entire premium.',
    long: '<strong>Not a recommendation.</strong> A conviction score summarises historical data. It says nothing about whether this holding suits your horizon, taxes or existing exposure.',
    roth: '<strong>Not retirement or tax advice.</strong> A rules-based illustration to compare against your own plan. It is not tailored to your income, tax situation, other accounts or goals, and contribution limits and eligibility change. Confirm current rules with the IRS and a licensed professional.',
    earnings: '<strong>Not a recommendation.</strong> Event pricing describes what the market is charging, not what you should do about it. Holding an option through a report can lose money even when the direction is right.',
    tracker: '<strong>Hypothetical performance.</strong> These positions were never placed with real money. Simulated results are prepared with the benefit of hindsight, assume fills at the mid price, and bear no commission, slippage, financing, borrow cost or tax. No real account would necessarily achieve results resembling these, and simulated performance does not indicate future results.',
    paper: '<strong>Hypothetical performance.</strong> Positions you enter here were never placed with real money. Marks assume you could trade at the last price or the chain mid, and bear no commission, slippage, financing, borrow cost, assignment risk or tax. A short position here cannot fail to borrow and an option here is never exercised early. No real account would necessarily achieve results resembling these.',
    market: '<strong>Not a recommendation.</strong> A regime read on the market as a whole, not a view on any individual security, and not advice to change your positioning.',
    indices: '<strong>Not a recommendation.</strong> Long-run index context, not advice to buy, sell or hold any index fund.',
    brief: '<strong>Not a recommendation.</strong> A summary of published news, not analysis of it, and not a view on any security mentioned. Headlines belong to their publishers and link to the original, and nothing here has been verified independently. Scheduled releases are calendar dates, not forecasts.',
  },
};
export const FOOTER_LINE = '<strong>Not financial advice.</strong> Optic Terminal is an independent research tool, not a broker-dealer or investment adviser. Data may be delayed or wrong, and trading involves substantial risk of loss.';
// v2's views, mapped to the classic ones the notices are written for
const AREA_FOR = { swing: 'swing', long: 'long', roth: 'roth', earnings: 'earnings', tracker: 'tracker', paper: 'paper', market: 'market', indices: 'indices', brief: 'brief' };
/** The notice for a page, or '' when it has none. */
export function areaNotice(view) {
  const t = LEGAL.areas[AREA_FOR[view]];
  return t ? html`<p class="legal-area">${raw(t)}</p>` : '';
}
export const miloNotice = () => html`<details class="legal-milo"><summary>${raw('<strong>Not financial advice.</strong>')} What Milo's reading is, and is not</summary><p>${raw(LEGAL.areas.pulse.replace('<strong>Not financial advice.</strong> ', ''))}</p></details>`;
export const footer = () => html`<p class="legal-line">${raw(FOOTER_LINE)} <button type="button" class="textlink" data-v2-legal-more aria-expanded="false" aria-controls="legal-full">Full disclaimer</button></p>
  <p class="legal-links"><a class="textlink" href="#/terms">Terms of use</a> <a class="textlink" href="#/privacy">Privacy</a></p>
  <p class="legal-switch"><a class="textlink" href="/classic" data-v2-use-classic>Use the classic app</a> <span>The same account and data; you can come back from its footer.</span></p>
  <div class="legal-full" id="legal-full" hidden>${LEGAL.full.map((p) => html`<p>${p}</p>`)}</div>`;
