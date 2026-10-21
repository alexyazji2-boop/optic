// House disclosures, shared by Financials and Insiders. A filing reports a dollar band, never a price, so the
// "Close that day" column is the market's close on the trade date (the server adds it for one symbol's trades),
// and the note says that is what it is.
import { html } from './dom.js';
import { money, shortDate, isNum } from './format.js';

export const closeCell = (t) => (isNum(t.close) ? html`${money(t.close, 2)}${t.close_date && t.close_date !== t.traded_iso ? html`<br><small class="t-muted">close ${shortDate(t.close_date)}</small>` : ''}` : 'Not available');
export const CLOSE_NOTE = "Close that day is the stock's closing price on the trade date (the last session before it on a weekend or holiday), from Yahoo Finance and adjusted for any later split: filings give no price, so the member's own price may differ.";
