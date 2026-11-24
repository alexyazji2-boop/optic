"""Pass 2, item 9 (2026-11-17): billing switched on by the platform's variables, with nothing shown when unset.

The keys, the price id and the webhook secret were already read from the environment (app/billing.py). New: the
price on the Upgrade button comes from the Stripe price itself unless the owner sets BILLING_PRICE_LABEL (it was a
default "$20 a month" no variable set); a reader sees nothing about plans while billing is off, and the owner sees the
missing variables by name; docs/billing/turning-billing-on.md is the runbook, names only.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import billing
from tests.test_frontend_v2_stage0 import V2

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_a_real_key")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_test_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_not_real")
    monkeypatch.delenv("BILLING_PRICE_LABEL", raising=False)
    billing._PRICE.update({"id": None, "at": 0.0, "label": None})
    yield monkeypatch
    billing._PRICE.update({"id": None, "at": 0.0, "label": None})


def test_with_nothing_set_billing_is_off_and_says_nothing_of_a_price(monkeypatch):
    for n in ("STRIPE_SECRET_KEY", "STRIPE_PRICE_ID", "STRIPE_WEBHOOK_SECRET"):
        monkeypatch.delenv(n, raising=False)
    st = billing.status()
    assert st["available"] is False and "price_label" not in st


def test_the_button_names_the_price_stripe_holds_read_once_an_hour(keys):
    calls = []
    keys.setattr(billing, "_stripe", lambda m, p, **k: calls.append(p) or {"unit_amount": 1500, "currency": "usd", "recurring": {"interval": "month"}})
    assert billing.status()["price_label"] == "$15 a month"
    billing.status()
    assert calls == ["/prices/price_test_123"], "cached: one read"
    assert billing.price_label(now=billing._PRICE["at"] + billing.PRICE_TTL + 1) == "$15 a month" and len(calls) == 2


def test_the_owners_own_label_wins_and_an_unreadable_price_names_none(keys):
    keys.setenv("BILLING_PRICE_LABEL", "$9.99 a month, students")
    assert billing.status()["price_label"] == "$9.99 a month, students"
    keys.delenv("BILLING_PRICE_LABEL")

    def refuse(*a, **k):
        raise billing.HTTPException(status_code=502, detail="refused")
    keys.setattr(billing, "_stripe", refuse)
    assert billing.status()["price_label"] is None


def test_amounts_in_other_currencies_and_cents_read_plainly():
    assert billing._money(999, "usd") == "$9.99" and billing._money(2000, "eur") == "€20" and billing._money(500, "chf") == "5 CHF"


def test_settings_shows_a_reader_nothing_while_billing_is_off_and_never_a_blank_price():
    src = (V2 / "js" / "pages" / "settings.js").read_text()
    assert "store.state.me && store.state.me.admin ? html`<span class=\"set-row-note\">${billingOff((b || {}).reason, true)}</span>` : ''" in src
    assert "Upgrade to Pro${b.price_label ? `, ${b.price_label}` : ''}" in src


def test_the_runbook_names_every_variable_and_holds_no_value():
    doc = (ROOT / "docs" / "billing" / "turning-billing-on.md").read_text()
    for name in ("STRIPE_SECRET_KEY", "STRIPE_PRICE_ID", "STRIPE_WEBHOOK_SECRET", "BILLING_LIVE_APPROVED", "BILLING_PRICE_LABEL"):
        assert "`{}`".format(name) in doc
    assert "sk_live_" not in doc and "sk_test_" not in doc and "whsec_" in doc and "whsec_" not in doc.split("starts with `whsec_`")[1]
