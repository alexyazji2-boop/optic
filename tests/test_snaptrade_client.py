"""The SnapTrade adapter against a fake HTTP session.

Not a contract test: SnapTrade has not been called. These pin the parts that
are Optic's to get right whatever SnapTrade answers: the signature recipe as
documented, the query carrying user credentials, mapping positions/all into
Optic's shapes (options with their multiplier and per-share cost), turning
HTTP failures into the typed errors the UI depends on, never leaking the user
secret into an error, and verifying webhooks.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from app.brokerage import snaptrade
from app.brokerage.providers import AuthExpired, ProviderError, ProviderOutage, WebhookRejected


class Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.content = json.dumps(body).encode() if body is not None else b""

    def json(self):
        return self._body


class FakeHTTP:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def request(self, method, url, json=None, headers=None, timeout=None):
        u = urlparse(url)
        self.calls.append({"method": method, "path": u.path, "query": u.query, "body": json,
                           "headers": headers})
        status, body = self.routes.get((method, u.path), (404, {"code": "404"}))
        return Resp(status, body)


def client(routes):
    http = FakeHTTP(routes)
    return snaptrade.SnapTradeProvider("cid", "ckey", session=http), http


def test_signature_follows_the_documented_recipe():
    p, http = client({("GET", "/authorizations"): (200, [])})
    p.list_connections("u1", "s1")
    call = http.calls[0]
    q = parse_qs(call["query"])
    assert q["clientId"] == ["cid"] and q["userId"] == ["u1"] and q["userSecret"] == ["s1"] and q["timestamp"]
    msg = json.dumps({"content": None, "path": "/authorizations", "query": call["query"]},
                     separators=(",", ":"), sort_keys=True)
    want = base64.b64encode(hmac.new(b"ckey", msg.encode(), hashlib.sha256).digest()).decode()
    assert call["headers"]["Signature"] == want


def test_portal_asks_for_read_only_and_passes_reconnect():
    p, http = client({("POST", "/snapTrade/login"): (200, {"redirectURI": "https://app.snaptrade.com/x"})})
    assert p.portal_url("u", "s", "https://optic/cb", reconnect="auth-1") == "https://app.snaptrade.com/x"
    body = http.calls[0]["body"]
    assert body["connectionType"] == "read" and body["reconnect"] == "auth-1"
    assert body["customRedirect"] == "https://optic/cb"


def test_positions_all_maps_stocks_and_options():
    p, _ = client({
        ("GET", "/accounts/a1/positions/all"): (200, {"results": [
            {"instrument": {"kind": "stock", "symbol": "AAPL", "description": "Apple"}, "units": "10",
             "price": "227.5", "cost_basis": "150", "currency": "USD"},
            {"instrument": {"kind": "option", "symbol": "AAPL  261218C00250000", "option_type": "CALL",
                            "strike_price": "250", "expiration_date": "2026-12-18", "multiplier": "100",
                            "underlying": {"symbol": "AAPL"}},
             "units": "-2", "price": "6.4", "cost_basis": "4.1", "currency": {"code": "USD"}},
            {"instrument": {"kind": "future", "symbol": "ESZ6"}, "units": "1", "price": "6000"},
        ], "data_freshness": {"as_of": "2026-10-12T13:00:00Z"}}),
        ("GET", "/accounts/a1/balances"): (200, [{"currency": {"code": "USD"}, "cash": "100.5",
                                                   "buying_power": "200"}]),
    })
    h = p.holdings("u", "s", "a1")
    assert [x.symbol for x in h.positions] == ["AAPL", "ESZ6"]
    assert h.positions[0].kind == "equity" and h.positions[0].quantity == 10
    assert h.positions[1].kind == "other"            # a future: listed, not valued
    o = h.options[0]
    assert (o.underlying, o.option_type, o.strike, o.contracts, o.multiplier, o.avg_cost) == \
        ("AAPL", "call", 250.0, -2.0, 100.0, 4.1)
    assert h.cash[0].amount == 100.5 and h.problems == []


def test_partial_when_balances_fail():
    p, _ = client({("GET", "/accounts/a1/positions/all"): (200, {"results": []}),
                   ("GET", "/accounts/a1/balances"): (400, {"code": "x"})})
    assert p.holdings("u", "s", "a1").problems == ["balances"]


@pytest.mark.parametrize("status,body,err", [
    (402, {"code": "x"}, AuthExpired),
    (400, {"code": "1076"}, AuthExpired),
    (429, {}, ProviderOutage),
    (503, {}, ProviderOutage),
    (401, {}, ProviderError),
])
def test_http_failures_become_typed_errors(status, body, err):
    p, _ = client({("GET", "/accounts/all"): (status, body)})
    with pytest.raises(err):
        p.list_accounts("u", "s")


def test_user_secret_never_appears_in_an_error():
    p, _ = client({("GET", "/accounts/all"): (500, {"detail": "userSecret=TOPSECRET"})})
    with pytest.raises(ProviderError) as e:
        p.list_accounts("u", "TOPSECRET")
    assert "TOPSECRET" not in str(e.value)


def test_accounts_all_maps_fields_and_skips_non_investment():
    p, _ = client({("GET", "/accounts/all"): (200, [
        {"id": "a1", "brokerage_authorization": "c1", "name": "Roth", "number": "12345678",
         "institution_name": "Schwab", "kind": "investment",
         "balance": {"total": {"amount": "1000", "currency": "USD"}},
         "sync_status": {"holdings": {"last_successful_sync": "2026-10-12T01:00:00Z",
                                      "initial_sync_completed": True}}},
        {"id": "b1", "kind": "deposit"},
    ])})
    a = p.list_accounts("u", "s")
    assert len(a) == 1 and a[0].number_mask == "..5678" and a[0].total_value == 1000.0
    assert a[0].connection_id == "c1" and a[0].broker_as_of.startswith("2026-10-12")


def test_remove_connection_uses_current_path():
    p, http = client({("DELETE", "/connection/c1"): (204, None)})
    p.remove_connection("u", "s", "c1")
    assert http.calls[0]["path"] == "/connection/c1"


def _webhook(body, key="ckey"):
    sig = base64.b64encode(hmac.new(key.encode(), json.dumps(body, separators=(",", ":"), sort_keys=True)
                                    .encode(), hashlib.sha256).digest()).decode()
    return {"signature": sig}, json.dumps(body, indent=2).encode()


def test_webhook_verification():
    p, _ = client({})
    now = datetime.now(timezone.utc).isoformat()
    body = {"eventType": "CONNECTION_BROKEN", "userId": "u", "eventTimestamp": now, "webhookId": "w1"}
    headers, raw = _webhook(body)
    assert p.verify_webhook(headers, raw)["eventType"] == "CONNECTION_BROKEN"
    bad_headers, _ = _webhook(body, key="wrong")
    with pytest.raises(WebhookRejected):
        p.verify_webhook(bad_headers, raw)
    old = dict(body, eventTimestamp=datetime.fromtimestamp(time.time() - 900, timezone.utc).isoformat())
    h2, raw2 = _webhook(old)
    with pytest.raises(WebhookRejected):
        p.verify_webhook(h2, raw2)
