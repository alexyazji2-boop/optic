// Terms of use and the privacy policy, in force from October 19, 2026 (owner's go-ahead: "draft the legal pages
// and publish"). Written from what Optic's code verifiably does (the evidence, file by file, is in
// docs/frontend-v2/LEGAL-DRAFTS.md) and from the owner's answers: the operator, the contact address, Massachusetts
// law, a minimum age of 13. Not reviewed by a lawyer: the owner was told so, and LAUNCH-REQUIREMENTS.md L1 keeps
// that review open. A change here changes EFFECTIVE, and a significant one is announced before it applies.
import { html, render as draw } from '../core/dom.js';

export const IN_FORCE = true;
export const EFFECTIVE = 'October 19, 2026';
export const OPERATOR = 'Optic Terminal';
export const CONTACT = 'theopticterminal@gmail.com';

const p = (...parts) => html`<p>${parts}</p>`;
const ul = (...items) => html`<ul>${items.map((i) => html`<li>${i}</li>`)}</ul>`;
const out = (href, label) => html`<a class="textlink" href="${href}" target="_blank" rel="noopener">${label}</a>`;
const mail = html`<a class="textlink" href="mailto:${CONTACT}">${CONTACT}</a>`;

const PRIVACY = [
  ['Who this covers', [
    p(`This policy says what ${OPERATOR} ("Optic", "we", "us"), which runs theopticterminal.com, collects about you, where it is kept, who else receives it and how to remove it. It describes what the software does today. ${OPERATOR} is responsible for this information.`),
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
      'The days you use Optic while signed in, and when and from which part of Optic you ask Milo a question (not what you asked), recorded against your account so the operator can count active readers and questions.',
      'Problem reports you send: your message, the page you were on, your browser\'s description and your email address, so a reply can reach you.',
    ),
    p('Kept only in your browser, never on Optic\'s servers: your Milo conversations, paper trades, chart drawings and notes, recent searches, and display settings such as the theme and layouts. They are kept separately for each account on that browser, and clearing the site\'s data in your browser removes them.'),
  ]],
  ['How we use it', [
    p('To run the account you asked for and the features you use; to keep Optic secure, including limiting repeated sign-in attempts and signing out sessions; to apply your plan\'s limits; and to answer you when you write to us. A linked brokerage is used only to show you your own accounts, and only because you agreed to it when you linked it. We do not sell your personal information, and we do not use it or share it for advertising.'),
  ]],
  ['Cookies and tracking', [
    p('Optic sets three cookies of its own. ', html`<b>optic_session</b>`, ' keeps you signed in: for 30 days of use if you choose "Keep me signed in", otherwise until you close the browser and at most a day unused. ', html`<b>optic_csrf</b>`, ' stops other sites acting as you. ', html`<b>optic_ui</b>`, ' remembers, for a year, whether you chose the new design or the classic app. Optic sets no advertising or analytics cookies and adds no tracking scripts of its own.'),
    p('The page\'s fonts are loaded from jsDelivr, a public content network, which receives your IP address as part of that request, as any web server would.'),
    // Seen on the live site on 2026-10-26: Cloudflare's automatic Web Analytics adds this script to HTML it serves to
    // browsers (not in Optic's source). The owner may switch it off in Cloudflare instead; then this paragraph goes.
    p('The site is served through Cloudflare, which adds its Web Analytics script to the pages it serves, loaded from static.cloudflareinsights.com. It sends Cloudflare information about each page visit. Cloudflare describes what it collects in its own privacy policy.'),
    p('In the classic app, company logos are loaded from Google, unavatar.io, favicone.com, Parqet and Financial Modeling Prep, which receive your IP address and the company being shown in the same way.'),
  ]],
  ['Milo, the assistant', [
    p('Milo\'s answers are written by Anthropic\'s Claude models. When you send Milo a question, Optic sends Anthropic your question, the conversation so far, a summary of the page you are on and any file you attach. Your name and email address are not sent.'),
    p('Holdings from a linked brokerage are sent only when your question is about your portfolio or you ask from the Brokerage page. Web search is used only when you turn it on. Nothing is sent to Anthropic unless you send a question or ask Optic to write something up for you. Anthropic handles this data under its own ', out('https://www.anthropic.com/legal/commercial-terms', 'commercial terms'), ' and ', out('https://www.anthropic.com/legal/privacy', 'privacy policy'), '.'),
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
    p('Optic emails you to confirm your address, reset your password and deliver the alerts you set. Email delivery is not switched on yet: until it is, nothing is emailed, and confirmation and reset links cannot reach you. The server log records that a message was attempted, with your address shortened (for example r***@example.com) and without the link. When a delivery service is switched on, this page will name it before it is used.'),
  ]],
  ['Market data sources', [
    p('Prices, filings and economic figures come from Yahoo Finance, the SEC, FRED, the Bureau of Labor Statistics and other public sources. Optic asks them for tickers and data series, never for anything about you.'),
  ]],
  ['Where it is kept, and for how long', [
    p('Optic runs on Railway, in its Amsterdam, Netherlands region, where the data above is stored. Optic is operated from the United States, and some of the services named here (Anthropic, Stripe, SnapTrade, Google and Apple) process data in the United States or Canada.'),
    ul(
      'Expired sessions and links are deleted within the hour; counts used to limit sign-in attempts within a day; the monthly Milo count within 31 days.',
      'Records of model calls, which do not say who made them: 92 days.',
      'The record of the days you used Optic while signed in and of when you asked Milo questions: 400 days.',
      'Daily copies of the accounts database, kept for 7 days to recover from a fault. A deleted account is gone from them within 7 days. They hold no brokerage encryption keys, so linked brokerage data in them cannot be read.',
      'Server logs, which record each request (the IP address it came from, what it asked for and when): kept by Railway for up to 90 days, then deleted.',
      'Everything else saved to your account: until you delete it or the account.',
    ),
  ]],
  ['Deleting your account', [
    p('Settings, Delete account, removes your account and everything saved to it. It cancels any subscription and deletes linked brokerage data, including SnapTrade\'s copy. Problem reports you sent are kept for the problem they describe, without your email address or your account. The daily recovery copies described above keep the account for up to 7 days more.'),
  ]],
  ['Your choices and rights', [
    p('You can correct your name in Settings, sign out any session, disconnect a brokerage, and delete your account at any time. You can also write to us at ', mail, ' to ask for a copy of the information we hold about you, or to have it corrected or deleted. We answer within 30 days.'),
    p('Depending on where you live, for example in the European Union, the United Kingdom or California, you may have further rights, such as to object to some uses of your information or to complain to your local data protection authority. Write to us and we will help you use them.'),
    p('Optic is not meant for children under 13, and we do not knowingly collect their information. If you believe a child under 13 has an account, write to us and we will delete it.'),
  ]],
  ['Contact and changes', [
    p('Questions about your data: ', mail, '. When this policy changes, the date at the top changes; for a significant change, we tell you in Optic or by email before it applies.'),
  ]],
];

const TERMS = [
  ['Agreeing to these terms', [
    p(`These terms are an agreement between you and ${OPERATOR} ("Optic", "we", "us"), which runs theopticterminal.com. By creating an account or using Optic, you agree to them and to the `, html`<a class="textlink" href="#/privacy">Privacy policy</a>`, '. If you do not agree, do not use Optic.'),
  ]],
  ['What Optic is', [
    p('Optic Terminal is an independent research tool for stocks and options. It is not financial, investment, tax or legal advice, and nothing in it is a recommendation, solicitation or offer to buy or sell any security, option or other instrument. Optic is not a broker-dealer or a registered investment adviser.'),
  ]],
  ['Who can use it', [
    p('You must be at least 13 to use Optic. If you are under 18, or under the age of majority where you live, you may use it only with a parent\'s or guardian\'s agreement. Linking a brokerage and buying a paid plan are for adults only.'),
  ]],
  ['Your account', [
    p('Give accurate details, keep your sign-in to yourself and tell us if you think someone else has used it. You are responsible for what is done with your account. An account is for one person.'),
  ]],
  ['Plans and payment', [
    p('Free and paid plans differ in their limits, which Settings shows. When the paid plan is on sale, its price is shown before you pay, it is billed monthly through Stripe until you cancel, and you cancel from the billing page in Settings; it then runs to the end of the period you paid for. Payments are not refunded for part of a period. If you were charged in error, write to us and we will refund the charge. Nothing here limits a refund the law gives you. Prices may change, with notice before your next renewal.'),
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
    p('Linking is read-only, through SnapTrade, whose own ', out('https://snaptrade.com/terms-and-conditions', 'terms and conditions'), ' also apply. Optic cannot trade or move money for you. Your relationship with your broker stays between you and your broker.'),
  ]],
  ['Your content', [
    p('What you save in Optic, such as watchlists, notes and theses, stays yours. You let Optic store and process it only to run the service for you.'),
  ]],
  ['Availability and changes', [
    p('Optic may change, add or remove features, and may be unavailable at times. If a change takes away something you pay for, you will be told first.'),
  ]],
  ['No warranty', [
    p('Optic is provided as it is and as available, without warranties of any kind, including that it is accurate, complete, uninterrupted or fit for a particular purpose. Trading involves substantial risk of loss; options can expire worthless and short positions can lose more than was invested.'),
  ]],
  ['Limits of liability', [
    p('To the extent the law allows, Optic is not liable for indirect, incidental, special or consequential losses, or for lost profits or trading losses, arising from your use of Optic or from relying on its data or Milo\'s answers. Optic\'s total liability for any claim about the service is limited to the greater of the amount you paid Optic in the 12 months before the claim and US$100. Some places do not allow some of these limits; there they apply as far as the law allows.'),
  ]],
  ['Ending', [
    p('You can delete your account at any time from Settings. Accounts that break these terms may be suspended or closed.'),
  ]],
  ['Law and disputes', [
    p('These terms are governed by the laws of the Commonwealth of Massachusetts, United States, without regard to its rules on conflicts of law. Disputes about them or about Optic will be heard in the state or federal courts located in Massachusetts, except where the law where you live gives you the right to bring a claim at home.'),
  ]],
  ['General', [
    p('These terms and the Privacy policy are the whole agreement between you and Optic about the service. If part of them cannot be enforced, the rest still applies. Not enforcing a term is not a waiver of it.'),
  ]],
  ['Changes and contact', [
    p('When these terms change, the date at the top changes; for a significant change, we tell you in Optic or by email before the new terms apply. Using Optic after they apply means you accept them. Contact: ', mail, '.'),
  ]],
];

const DOCS = {
  terms: { title: 'Terms of use', sections: TERMS },
  privacy: { title: 'Privacy policy', sections: PRIVACY },
};

let live = false;
export async function render(main, route) {
  live = true;
  const doc = DOCS[route.view] || DOCS.terms;
  document.title = `${doc.title}, Optic`;
  if (!live) return;
  draw(main, html`<header class="page-head"><h1 class="t-display-m">${doc.title}</h1>
      <p class="section-sub">Effective ${EFFECTIVE}. ${route.view === 'privacy' ? html`See also the <a class="textlink" href="#/terms">Terms of use</a>.` : html`See also the <a class="textlink" href="#/privacy">Privacy policy</a>.`}</p></header>
    <article class="legal-doc">${doc.sections.map(([h, body]) => html`<h2>${h}</h2>${body}`)}</article>`);
}
export function dispose() { live = false; }
