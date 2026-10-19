// Terms of use and the privacy policy (owner's checklist, 2026-10-19).
//
// DRAFTS. Written from what Optic's code verifiably does (the evidence, file by file, is in
// docs/frontend-v2/LEGAL-DRAFTS.md), not reviewed by the owner or a lawyer, and not in force. While
// IN_FORCE is false every page says so at the top, and no screen asks a reader to agree to them. What the
// code cannot say (the operator's legal name, contact address, governing law, refunds) is a highlighted
// field to fill in.
import { html, render as draw } from '../core/dom.js';

export const IN_FORCE = false;
const DRAFT_OF = 'October 19, 2026';

const fill = (t) => html`<span class="legal-fill">[${t}]</span>`;
const p = (...parts) => html`<p>${parts}</p>`;
const ul = (...items) => html`<ul>${items.map((i) => html`<li>${i}</li>`)}</ul>`;

const PRIVACY = [
  ['Who this covers', [
    p('This page says what Optic Terminal (theopticterminal.com) collects, where it is kept, who else receives it and how to remove it. It describes what the software does today. ', fill('operator\'s legal name'), ' runs Optic and is responsible for this information.'),
  ]],
  ['What you give when you create an account', [
    ul(
      'Your email address, first name, an optional last name and a password. The password is stored only as an Argon2id hash, so Optic cannot read it.',
      'If you sign in with Google: an identifier from Google, the email address and name on that account, the address of its picture and whether Google has verified the email. With Apple: an identifier, the email address Apple shares and, the first time, your name.',
      'If you add a passkey: its public key and identifiers, the name you give it, and when it was made and last used. The private key stays on your device.',
      'Your choices of time zone, default market and the page Optic opens on.',
    ),
  ]],
  ['What Optic keeps while you use it', [
    ul(
      'Each signed-in session: when it started and was last used, your browser\'s description of itself (its user agent) and the IP address it connected from. Settings, Security lists them and signs any of them out. Sign-in, password reset and email confirmation links are stored only as one-way hashes.',
      'What you save to your account: watchlists, saved research, watches and the alerts they raise, theses, valuation scenarios and saved models, signal history, and portfolio alert settings.',
      'A count of the Milo questions you ask, kept under a hashed identifier, so your plan\'s daily allowance can be applied.',
      'Problem reports you send: your message, the page you were on, your browser\'s description and your email address, so a reply can reach you.',
    ),
    p('Kept only in your browser, never on Optic\'s servers: your Milo conversations, paper trades, chart drawings and notes, recent searches, and display settings such as the theme and layouts. They are kept separately for each account on that browser, and clearing the site\'s data in your browser removes them.'),
  ]],
  ['Cookies and tracking', [
    p('Optic sets two cookies of its own. ', html`<b>optic_session</b>`, ' keeps you signed in: for 30 days of use if you choose "Keep me signed in", otherwise until you close the browser and at most a day unused. ', html`<b>optic_csrf</b>`, ' stops other sites acting as you. There are no advertising or analytics cookies and no tracking scripts.'),
    p('The page\'s fonts are loaded from jsDelivr, a public content network, which receives your IP address as part of that request, as any web server would.'),
  ]],
  ['Milo, the assistant', [
    p('Milo\'s answers are written by Anthropic\'s Claude models. When you send Milo a question, Optic sends Anthropic your question, the conversation so far, a summary of the page you are on and any file you attach. Your name and email address are not sent.'),
    p('Holdings from a linked brokerage are sent only when your question is about your portfolio or you ask from the Brokerage page. Web search is used only when you turn it on. Nothing is sent to Anthropic unless you send a question or ask Optic to write something up for you. Anthropic handles this data under its own terms: ', fill('link to Anthropic\'s commercial terms and data policy'), '.'),
    p('Optic also records the size and model of each call, without who made it, to keep track of cost.'),
  ]],
  ['Linking a brokerage (Pro)', [
    ul(
      'Linking goes through SnapTrade and is read-only: Optic cannot place trades or move money. SnapTrade knows you by a random identifier, not by your Optic account.',
      'Optic stores your connected accounts (with masked account numbers), holdings, balances, transactions and their history, encrypted with a key that belongs to your account alone.',
      'Snapshots of your holdings are kept so changes can be shown: the newest 30, plus one a day for 400 days.',
      'You can disconnect at any time. If your plan lapses, syncing stops; SnapTrade\'s copy is removed after 7 days and Optic\'s after 30.',
    ),
  ]],
  ['Payments', [
    p('When paid plans are on sale, payments are handled by Stripe. Optic gives Stripe your account identifier and, the first time, your email address; you give your card details to Stripe directly. Optic keeps only your plan, its status, Stripe\'s customer and subscription identifiers and the renewal date. Optic never sees your card number.'),
  ]],
  ['Email', [
    p('Optic emails you to confirm your address, reset your password and deliver the alerts you set, through ', fill('email provider'), '.'),
  ]],
  ['Market data sources', [
    p('Prices, filings and economic figures come from Yahoo Finance, the SEC, FRED, the Bureau of Labor Statistics and other public sources. Optic asks them for tickers and data series, never for anything about you.'),
  ]],
  ['Where it is kept, and for how long', [
    p('Optic runs on Railway, in ', fill('region'), ', where the data above is stored.'),
    ul(
      'Expired sessions and links are deleted within the hour; counts used to limit sign-in attempts within a day; the monthly Milo count within 31 days.',
      'Records of model calls, which do not say who made them: 92 days.',
      html`Server logs: ${fill('retention period')}.`,
      'Everything else saved to your account: until you delete it or the account.',
    ),
  ]],
  ['Deleting your account', [
    p('Settings, Delete account, removes your account and everything saved to it. It cancels any subscription and deletes linked brokerage data, including SnapTrade\'s copy. Problem reports you sent are kept, with your email address, so they can still be answered. ', fill('decide whether these are removed too'), ' There is no download of your data yet.'),
  ]],
  ['Your choices and rights', [
    p('You can correct your name in Settings, sign out any session, disconnect a brokerage, and delete your account at any time. ', fill('rights under the laws that apply to you, and how to exercise them, with counsel'), '.'),
    p('Optic is not meant for anyone under ', fill('minimum age'), '.'),
  ]],
  ['Contact and changes', [
    p('Questions about your data: ', fill('contact email address'), '. If this policy changes, the date at the top changes and a notice appears in Optic.'),
  ]],
];

const TERMS = [
  ['What Optic is', [
    p('Optic Terminal is an independent research tool for stocks and options, run by ', fill('operator\'s legal name'), '. It is not financial, investment, tax or legal advice, and nothing in it is a recommendation, solicitation or offer to buy or sell any security, option or other instrument. The operator is not a broker-dealer or a registered investment adviser.'),
  ]],
  ['Your account', [
    p('Give accurate details, keep your sign-in to yourself and tell us if you think someone else has used it. You are responsible for what is done with your account. An account is for one person.'),
  ]],
  ['Plans and payment', [
    p('Free and paid plans differ in their limits, which Settings shows. When the paid plan is on sale, its price is shown before you pay, it is billed monthly through Stripe until you cancel, and you cancel from the billing page in Settings; it then runs to the end of the period you paid for. Refunds: ', fill('refund policy'), '. Prices may change, with notice before your next renewal.'),
  ]],
  ['Using Optic fairly', [
    ul(
      'Do not scrape Optic, download its data in bulk, or use automated tools to get around its limits.',
      'Do not try to reach other readers\' data or test Optic\'s security without permission.',
      'Do not resell or republish Optic\'s data or analysis. Market data belongs to its providers and is shown to you for your own use.',
      'Do not use Optic for anything unlawful.',
    ),
  ]],
  ['The data and Milo', [
    p('Figures come from third parties and may be delayed, incomplete or wrong. Models state their assumptions but are not guaranteed. Milo\'s answers are written by an AI model from Optic\'s data and can be wrong or incomplete. Check anything you intend to act on against primary sources, and consult a licensed professional before making an investment decision.'),
  ]],
  ['Linking a brokerage', [
    p('Linking is read-only, through SnapTrade, whose own terms also apply: ', fill('link to SnapTrade\'s terms'), '. Optic cannot trade or move money for you. Your relationship with your broker stays between you and your broker.'),
  ]],
  ['Your content', [
    p('What you save in Optic, such as watchlists, notes and theses, stays yours. You let Optic store and process it only to run the service for you.'),
  ]],
  ['Availability and changes', [
    p('Optic may change, add or remove features, and may be unavailable at times. If a change takes away something you pay for, you will be told first.'),
  ]],
  ['No warranty, and limits of liability', [
    p('Optic is provided as it is, without warranties. Trading involves substantial risk of loss; options can expire worthless and short positions can lose more than was invested. The operator is not liable for losses arising from your use of Optic, ', fill('the extent of this limit and any cap, with counsel'), '.'),
  ]],
  ['Ending', [
    p('You can delete your account at any time from Settings. Accounts that break these terms may be suspended or closed.'),
  ]],
  ['Changes, law and contact', [
    p('If these terms change, the date at the top changes and a notice appears in Optic before the new terms apply. They are governed by the laws of ', fill('jurisdiction'), '. Contact: ', fill('contact email address'), '.'),
  ]],
];

const DOCS = {
  terms: { title: 'Terms of use', sections: TERMS },
  privacy: { title: 'Privacy', sections: PRIVACY },
};

let live = false;
export async function render(main, route) {
  live = true;
  const doc = DOCS[route.view] || DOCS.terms;
  document.title = `${doc.title}, Optic`;
  if (!live) return;
  draw(main, html`<header class="page-head"><h1 class="t-display-m">${doc.title}</h1>
      <p class="section-sub">Draft of ${DRAFT_OF}. ${route.view === 'privacy' ? html`See also the <a class="textlink" href="#/terms">Terms of use</a>.` : html`See also <a class="textlink" href="#/privacy">Privacy</a>.`}</p></header>
    ${IN_FORCE ? '' : html`<p class="legal-draft" role="note"><b>Draft for review, not yet in force.</b> Written from what Optic's software does today. The highlighted fields need the operator's details, and the whole text needs the owner's approval and a lawyer's review before it applies to anyone.</p>`}
    <article class="legal-doc">${doc.sections.map(([h, body]) => html`<h2>${h}</h2>${body}`)}</article>`);
}
export function dispose() { live = false; }
