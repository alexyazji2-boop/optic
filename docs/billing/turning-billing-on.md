# Turning billing on

Optic's billing is off until four variables are set on the platform (Railway: the `optic` service's Variables).
With none of them set, no reader sees anything about plans or prices; the owner's Settings page names the
variables still missing. Names only here: the values live in Railway's variables and your Stripe account, never in
this repository.

## What you need first

- A Stripe account in your company's name, with its bank account connected.
- One Product in Stripe (for example "Optic Pro") with one recurring Price. Its price id starts with `price_`.
- A webhook endpoint in Stripe pointing at `https://<your domain>/api/billing/webhook`, sending
  `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated` and
  `customer.subscription.deleted`. Stripe shows its signing secret once; it starts with `whsec_`.

## The variables

| Name | What it holds | Required |
| --- | --- | --- |
| `STRIPE_SECRET_KEY` | your Stripe secret key (a restricted key is better); test mode first | yes |
| `STRIPE_PRICE_ID` | the Price id above | yes |
| `STRIPE_WEBHOOK_SECRET` | the webhook's signing secret | yes |
| `BILLING_LIVE_APPROVED` | `true` only when you switch to live keys; a live key without it is refused | for live only |
| `BILLING_PRICE_LABEL` | the words on the Upgrade button, if you want your own; otherwise Optic reads the amount and interval from the Stripe price | no |

## Order

1. Set the three required variables with test-mode values. Railway redeploys the service.
2. Open Settings signed in as a reader: the Plan row now offers Upgrade with the price Stripe holds.
3. Subscribe with Stripe's test card, and check the plan turns to Pro only after the webhook arrives.
4. When the test run is right, replace the three with live values and set `BILLING_LIVE_APPROVED=true`.

To switch billing off again, remove `STRIPE_SECRET_KEY`. Readers see no plans; existing Pro rows stay as they are.
