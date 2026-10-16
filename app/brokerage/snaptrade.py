"""SnapTrade, the chosen aggregator, behind the provider interface.

Written against SnapTrade's public OpenAPI spec and docs as read on 2026-10-12
(`~/Optic/work/brokerage-launch/research/VERIFIED-2026-10-12.md`). **It has not
been run against SnapTrade.** Their free tier connects real brokerage accounts
only, and connecting one needs the owner's approval. The first contract test is
on the launch checklist: one signed call to `GET /snapTrade/partners` settles
the one open question below.

Things that matter here, each from that reading:

* Root paths on `https://api.snaptrade.com`. The `/api/v1` prefix still works but
  answers with a Deprecation header dated 2026-06-12.
* Every call is signed: query `clientId` and `timestamp`, header `Signature` =
  base64(HMAC-SHA256(consumerKey, canonical JSON of {content, path, query})).
  `query` is the raw query string exactly as sent. **Open question:** the
  signatures doc says to sign the `/api/v1` path; the current official SDK
  signs the root path it actually calls. This signs the path it sends, like the
  SDK. If the contract test returns 401, set `SNAPTRADE_SIGN_PREFIX=/api/v1`.
* `positions/all` returns stocks, ETFs and options together, with a required
  `multiplier` on option instruments and option `cost_basis` per share. The
  combined `holdings` endpoint returns 410 for customers who signed up after
  2026-05-11, so it is not used.
* Removing a connection is `DELETE /connection/{id}`; `GET /accounts` is
  deprecated in favour of `GET /accounts/all`.
* The portal link expires in five minutes, which is why Optic fetches it at the
  moment the reader presses Connect rather than rendering it into the page.
* Rate limit: 250 requests a minute per client id. The launch guide also asks
  for no more than four background holdings pulls per user per day.

**The user secret never leaves this module in an error.** SnapTrade puts
`userSecret` in the query string, and `requests` exception text can include the
URL. Every error raised from here is rebuilt from the status code alone.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import requests

from .providers import (Account, AuthExpired, Cash, Connection, Holdings, NotFoundAtProvider, OptionPosition,
                        Position, Provider, ProviderError, ProviderOutage, UnsupportedBroker, WebhookRejected)

BASE_URL = "https://api.snaptrade.com"
TIMEOUT = 20
# SnapTrade retries a failed delivery after 30 minutes with backoff, up to
# three times. A five-minute window (their docs' sample) rejected every retry,
# so USER_DELETED or CONNECTION_BROKEN missed once was missed for good (review
# H1). Replays are harmless: every event only prompts a re-read, and the
# webhookId is de-duplicated.
WEBHOOK_MAX_AGE = 24 * 3600

KIND_MAP = {"stock": "equity", "adr": "equity", "etf": "etf", "mutualfund": "fund", "cef": "fund",
            "bond": "bond", "crypto": "crypto"}


def canonical(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


def sign(consumer_key: str, path: str, query: str, content: Any) -> str:
    message = canonical({"content": content if content not in ({},) else None,
                         "path": path, "query": query})
    digest = hmac.new(consumer_key.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _mask(number: Any) -> str:
    digits = str(number or "")
    return ".." + digits[-4:] if len(digits) >= 4 else ("..." if digits else "")


class SnapTradeProvider(Provider):
    name = "snaptrade"
    label = "SnapTrade"

    def __init__(self, client_id: str, consumer_key: str, base_url: str = BASE_URL,
                 sign_prefix: str = "", session: Optional[requests.Session] = None) -> None:
        self.client_id = client_id
        self.consumer_key = consumer_key
        self.base_url = base_url.rstrip("/")
        self.sign_prefix = sign_prefix
        self.http = session or requests.Session()
        self.mode = "production" if (os.environ.get("SNAPTRADE_ENV") or "").lower() == "production" \
            else "development"

    @classmethod
    def from_env(cls) -> "SnapTradeProvider":
        return cls(os.environ["SNAPTRADE_CLIENT_ID"], os.environ["SNAPTRADE_CONSUMER_KEY"],
                   os.environ.get("SNAPTRADE_BASE_URL", BASE_URL),
                   os.environ.get("SNAPTRADE_SIGN_PREFIX", ""))

    # ------------------------------------------------------------ transport

    def _call(self, method: str, path: str, user: Optional[Dict[str, str]] = None,
              params: Optional[Dict[str, str]] = None, body: Any = None) -> Any:
        query_items = [("clientId", self.client_id), ("timestamp", str(int(time.time())))]
        if user:
            query_items += [("userId", user["user_id"]), ("userSecret", user["secret"])]
        query_items += list((params or {}).items())
        query = urllib.parse.urlencode(query_items)
        signature = sign(self.consumer_key, self.sign_prefix + path, query, body)
        try:
            resp = self.http.request(method, "{}{}?{}".format(self.base_url, path, query),
                                     json=body if body is not None else None,
                                     headers={"Signature": signature, "Accept": "application/json"},
                                     timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderOutage("SnapTrade did not answer ({})".format(type(exc).__name__)) from None
        if resp.status_code in (200, 201, 202, 204):
            if not resp.content:
                return None
            try:
                return resp.json()
            except ValueError:
                raise ProviderError("SnapTrade returned something that was not JSON") from None
        said = self._error_said(resp, (user or {}).get("secret"), self.consumer_key, self.client_id)
        if resp.status_code in (429,) or resp.status_code >= 500:
            raise ProviderOutage("SnapTrade returned {}".format(resp.status_code))
        # Expiry is read from `authorizations[].disabled`, which is documented,
        # not guessed from status codes. 402 is documented for a refresh on a
        # disabled connection but can also mean Optic's own SnapTrade plan, so
        # it is a provider-side error, never "sign in again" for every reader.
        if resp.status_code == 402:
            raise ProviderError("SnapTrade refused the request (402): refresh or plan not available")
        if resp.status_code == 401:
            # SnapTrade's code tells a wrong client id (1083) from a consumer key
            # that does not match it (1076), which is all the owner can act on.
            raise ProviderError("SnapTrade rejected Optic's credentials (401{})"
                                .format(", " + said if said else ""))
        if resp.status_code == 404:
            raise NotFoundAtProvider("SnapTrade could not find that resource (404)")
        raise ProviderError("SnapTrade returned {}{}".format(resp.status_code,
                                                             " ({})".format(said) if said else ""))

    @staticmethod
    def _error_said(resp: requests.Response, *secrets: Optional[str]) -> str:
        """SnapTrade's own code and sentence, as "1076: Unable to verify
        signature sent". It goes to the log and the owner, so every credential
        is cut out of it, the client id included: 1083 echoes whatever was sent
        as the client id, and on the first live connect (2026-10-15) that was
        the consumer key, pasted into the wrong variable."""
        try:
            body = resp.json()
        except ValueError:
            return ""
        if not isinstance(body, dict):
            return ""
        detail = " ".join(str(body.get("detail") or "").split())
        for secret in secrets:
            if secret:
                detail = detail.replace(secret, "[redacted]")
        return ": ".join(p for p in (str(body.get("code") or ""), detail[:160]) if p)

    @staticmethod
    def _u(puid: str, secret: str) -> Dict[str, str]:
        return {"user_id": puid, "secret": secret}

    # ---------------------------------------------------------------- users

    def register_user(self) -> Dict[str, str]:
        # A random id, not Optic's user id: the aggregator does not need to be
        # able to correlate its users with Optic's.
        puid = "optic-" + base64.urlsafe_b64encode(os.urandom(12)).decode().rstrip("=")
        made = self._call("POST", "/snapTrade/registerUser", body={"userId": puid}) or {}
        if not made.get("userSecret"):
            raise ProviderError("SnapTrade did not return a user secret")
        return {"user_id": made.get("userId") or puid, "secret": made["userSecret"]}

    def delete_user(self, provider_user_id: str) -> None:
        self._call("DELETE", "/snapTrade/deleteUser", params={"userId": provider_user_id})

    def portal_url(self, provider_user_id, secret, redirect_url, reconnect=None) -> str:
        body: Dict[str, Any] = {"connectionType": "read", "customRedirect": redirect_url,
                                "immediateRedirect": True, "connectionPortalVersion": "v4"}
        if reconnect:
            body["reconnect"] = reconnect
        out = self._call("POST", "/snapTrade/login", user=self._u(provider_user_id, secret), body=body) or {}
        url = out.get("redirectURI") if isinstance(out, dict) else None
        if not url:
            raise ProviderError("SnapTrade did not return a portal link")
        return url

    # ---------------------------------------------------------- connections

    def list_connections(self, provider_user_id, secret) -> List[Connection]:
        out = []
        for a in self._call("GET", "/authorizations", user=self._u(provider_user_id, secret)) or []:
            broker = a.get("brokerage") or {}
            out.append(Connection(id=str(a.get("id")),
                                  institution=broker.get("display_name") or broker.get("name") or a.get("name")
                                  or "Brokerage",
                                  disabled=bool(a.get("disabled")),
                                  disabled_reason="The broker needs you to sign in again."
                                  if a.get("disabled") else None,
                                  read_only=(str(a.get("type")).lower() == "read") if a.get("type") else None))
        return out

    def remove_connection(self, provider_user_id, secret, connection_id) -> None:
        self._call("DELETE", "/connection/{}".format(urllib.parse.quote(connection_id, safe="")),
                   user=self._u(provider_user_id, secret))

    def refresh_connection(self, provider_user_id, secret, connection_id) -> None:
        """A paid call on the Daily plan ($0.05 each, pricing page 2026-09-23).
        Only ever made from a reader's metered "Sync now"."""
        self._call("POST", "/authorizations/{}/refresh".format(urllib.parse.quote(connection_id, safe="")),
                   user=self._u(provider_user_id, secret))

    # ------------------------------------------------------------- accounts

    def list_accounts(self, provider_user_id, secret) -> List[Account]:
        raw = self._call("GET", "/accounts/all", user=self._u(provider_user_id, secret)) or []
        if isinstance(raw, dict):
            raw = raw.get("results") or raw.get("accounts") or []
        out = []
        for a in raw:
            if a.get("kind") and a.get("kind") != "investment":
                continue
            total = ((a.get("balance") or {}).get("total") or {})
            sync = ((a.get("sync_status") or {}).get("holdings") or {})
            out.append(Account(
                id=str(a.get("id")),
                connection_id=str(a.get("brokerage_authorization") or a.get("connection_id") or ""),
                name=a.get("name") or "Account", number_mask=_mask(a.get("number")),
                institution=a.get("institution_name") or "", account_type=(a.get("meta") or {}).get("type")
                or a.get("raw_type"), currency=total.get("currency") or None,
                total_value=_num(total.get("amount")),
                broker_as_of=sync.get("last_successful_sync"),
                initial_sync_done=sync.get("initial_sync_completed") is not False))
        return out

    def holdings(self, provider_user_id, secret, account_id) -> Holdings:
        user = self._u(provider_user_id, secret)
        aid = urllib.parse.quote(account_id, safe="")
        h = Holdings()
        try:
            got = self._call("GET", "/accounts/{}/positions/all".format(aid), user=user) or {}
            for r in (got.get("results") if isinstance(got, dict) else got) or []:
                inst = r.get("instrument") or {}
                kind = str(inst.get("kind") or "other").lower()
                if kind == "option":
                    h.options.append(OptionPosition(
                        underlying=(inst.get("underlying") or {}).get("symbol")
                        if isinstance(inst.get("underlying"), dict) else inst.get("underlying"),
                        occ=inst.get("symbol"), option_type=str(inst.get("option_type") or "").lower() or None,
                        strike=_num(inst.get("strike_price")), expiry=inst.get("expiration_date"),
                        contracts=_num(r.get("units")), price=_num(r.get("price")),
                        avg_cost=_num(r.get("cost_basis")), currency=_ccy(r.get("currency")),
                        multiplier=_num(inst.get("multiplier")),
                        mini=(_num(inst.get("multiplier")) or 100) == 10))
                    continue
                if r.get("cash_equivalent"):
                    kind = "fund"
                h.positions.append(Position(
                    symbol=inst.get("symbol"), description=inst.get("description") or inst.get("symbol") or "",
                    kind=KIND_MAP.get(kind, "other"), currency=_ccy(r.get("currency")),
                    quantity=_num(r.get("units")), price=_num(r.get("price")),
                    avg_cost=_num(r.get("cost_basis")), raw_type=kind))
        except (AuthExpired, ProviderOutage):
            raise
        except ProviderError:
            h.problems.append("positions")
        try:
            for b in self._call("GET", "/accounts/{}/balances".format(aid), user=user) or []:
                h.cash.append(Cash(currency=_ccy(b.get("currency")) or "USD", amount=_num(b.get("cash")),
                                   buying_power=_num(b.get("buying_power"))))
        except (AuthExpired, ProviderOutage):
            raise
        except ProviderError:
            h.problems.append("balances")
        if h.problems == ["positions", "balances"]:
            raise UnsupportedBroker("Neither holdings nor balances are available for this account.")
        return h

    # ------------------------------------------------------------- webhooks

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        """Signature over the re-serialised parsed body (sorted keys, no
        spaces), keyed with the consumer key, per SnapTrade's webhook doc. The
        doc's own example rejects events older than five minutes; so does this."""
        given = headers.get("signature") or headers.get("Signature") or ""
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise WebhookRejected("body is not JSON") from None
        expected = base64.b64encode(hmac.new(self.consumer_key.encode(), canonical(parsed).encode(),
                                             hashlib.sha256).digest()).decode()
        if not given or not hmac.compare_digest(given, expected):
            raise WebhookRejected("signature does not match")
        stamp = parsed.get("eventTimestamp")
        try:
            from datetime import datetime
            at = datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            raise WebhookRejected("no usable eventTimestamp") from None
        if abs(time.time() - at) > WEBHOOK_MAX_AGE:
            raise WebhookRejected("event is too old to accept")
        return parsed


def _ccy(v: Any) -> Optional[str]:
    if isinstance(v, dict):
        return (v.get("code") or None)
    return str(v).upper() if v else None
