"""The provider boundary: what Optic needs from a brokerage aggregator, and a
local sandbox that answers the same calls.

Everything above this file speaks Optic's own shapes (`Connection`, `Account`,
`Position`, `OptionPosition`, `Cash`), so the provider can be swapped or a second
one added (Plaid Investments was the runner-up) without touching sync, storage,
the portfolio maths or Milo. A provider module's whole job is to translate.

**Read-only by construction.** There is no order, trade or transfer method on
this interface, so no code path above it can place one. The real adapter also
asks the aggregator for a read-only connection (`connectionType=read`).

**Errors are typed** because each one means something different to a reader:
an expired authorisation is theirs to fix (reconnect), an outage is nobody's
(keep the last good data and say how old it is), an unsupported broker is a
fact about coverage. A bare exception would collapse all three into "sync
failed", which is the one message nobody can act on.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ProviderError(RuntimeError):
    """Something went wrong that is not one of the specific cases below."""


class AuthExpired(ProviderError):
    """The broker no longer accepts the aggregator's authorisation. Only the
    reader can fix it, by reconnecting through the hosted portal."""


class ProviderOutage(ProviderError):
    """The aggregator or the broker is down or rate-limiting us. Retry later;
    keep showing the last good data with its age."""


class RefreshUnavailable(ProviderError):
    """The provider will not refresh from the broker on demand: SnapTrade's
    402 (no paid refresh on the plan, or the connection is disabled), or its
    403 1141 on the Real-time plan, whose reads are already live (`live`).
    Either way the provider's data can still be read."""

    live = False


class UnsupportedBroker(ProviderError):
    """The broker, or this account type at the broker, is not available."""


class NotFoundAtProvider(ProviderError):
    """The user or connection is already gone at the provider. For a
    deletion that is success, not a failure to retry."""


class FeatureUnavailable(ProviderError):
    """The provider, or this plan of it, does not offer that data: SnapTrade's
    balance history is an add-on that answers 403 until it is switched on in
    the dashboard. Not a failure to retry, and not a reason to fail a sync."""


class WebhookRejected(ProviderError):
    """A webhook whose signature or freshness did not verify."""


@dataclass
class Connection:
    id: str
    institution: str
    disabled: bool = False
    disabled_reason: Optional[str] = None
    # True only when the provider says the connection is read-only. Optic
    # refuses anything else, even though it asks for read-only, because the
    # reader can change the type in the provider's portal.
    read_only: Optional[bool] = None


@dataclass
class Account:
    id: str
    connection_id: str
    name: str
    number_mask: str
    institution: str
    account_type: Optional[str]
    currency: Optional[str]
    # The broker's own total for the account, in its own currency, if it gave one.
    total_value: Optional[float] = None
    # When the provider last pulled this account from the broker successfully.
    broker_as_of: Optional[str] = None
    initial_sync_done: bool = True
    # The institution's own id for the account, where the provider passes it
    # on: the same account reached through a second connection has a new
    # provider id but the same one of these.
    institution_account_id: Optional[str] = None
    # The earliest transaction the provider knows of. Anything before it is
    # not missing data Optic can fetch: the broker did not hand it over.
    transactions_first_date: Optional[str] = None


@dataclass
class Position:
    symbol: Optional[str]
    description: str
    kind: str                      # equity | etf | fund | bond | crypto | other
    currency: Optional[str]
    quantity: Optional[float]
    price: Optional[float]         # broker's price per unit, in `currency`
    avg_cost: Optional[float]      # per unit; None when the broker did not supply it
    raw_type: Optional[str] = None
    # A money-market fund or similar that the broker also counts in the
    # account's cash balance (SnapTrade's `cash_equivalent`, whose Balance.cash
    # "includes" them): counted once, as cash.
    cash_equivalent: bool = False


@dataclass
class OptionPosition:
    underlying: Optional[str]
    occ: Optional[str]
    option_type: Optional[str]     # call | put
    strike: Optional[float]
    expiry: Optional[str]
    contracts: Optional[float]     # signed: negative is short
    price: Optional[float]         # per share, as premium is quoted
    avg_cost: Optional[float]      # per share (SnapTrade's positions/all convention, 2026-10)
    currency: Optional[str]
    mini: bool = False
    # Shares per contract, when the provider supplies it. SnapTrade's
    # positions/all does; Plaid and the retired SnapTrade endpoint did not, and
    # the portfolio maths assumes 100 (10 for a mini) and says so when absent.
    multiplier: Optional[float] = None


@dataclass
class Cash:
    currency: str
    amount: Optional[float]
    buying_power: Optional[float] = None


@dataclass
class Activity:
    """One transaction as the broker reported it. `amount` is signed from the
    account's side: positive for money in (a sale, a deposit, a dividend),
    negative for money out (a purchase, a withdrawal, a fee), in `currency`."""
    id: str
    type: str                      # BUY, SELL, DIVIDEND, CONTRIBUTION, WITHDRAWAL, TRANSFER, FEE, ...
    trade_date: Optional[str]      # YYYY-MM-DD
    settlement_date: Optional[str] = None
    symbol: Optional[str] = None
    option_occ: Optional[str] = None
    option_action: Optional[str] = None
    units: Optional[float] = None
    price: Optional[float] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    fee: Optional[float] = None
    fx_rate: Optional[float] = None
    description: str = ""
    group_ref: Optional[str] = None


@dataclass
class Holdings:
    """One account's data from one sync. `problems` names any part that failed,
    so a partial sync is stored as partial rather than as a smaller portfolio."""
    positions: List[Position] = field(default_factory=list)
    options: List[OptionPosition] = field(default_factory=list)
    cash: List[Cash] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)


class Provider:
    name = "base"
    mode = "development"          # sandbox | development | production
    label = "Provider"

    def register_user(self) -> Dict[str, str]:
        raise NotImplementedError

    def delete_user(self, provider_user_id: str) -> None:
        raise NotImplementedError

    def portal_url(self, provider_user_id: str, secret: str, redirect_url: str,
                   reconnect: Optional[str] = None) -> str:
        raise NotImplementedError

    def list_connections(self, provider_user_id: str, secret: str) -> List[Connection]:
        raise NotImplementedError

    def remove_connection(self, provider_user_id: str, secret: str, connection_id: str) -> None:
        raise NotImplementedError

    def list_accounts(self, provider_user_id: str, secret: str) -> List[Account]:
        raise NotImplementedError

    def holdings(self, provider_user_id: str, secret: str, account_id: str) -> Holdings:
        raise NotImplementedError

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        raise WebhookRejected("this provider does not send webhooks")

    def activities(self, provider_user_id: str, secret: str, account_id: str,
                   start_date: Optional[str] = None) -> List[Activity]:
        """Transactions from `start_date` (YYYY-MM-DD, inclusive) or from the
        first the provider knows, oldest first."""
        raise FeatureUnavailable("this provider does not supply transactions")

    def balance_history(self, provider_user_id: str, secret: str, account_id: str) -> Dict[str, Any]:
        """{"currency": str|None, "points": [(YYYY-MM-DD, total value)]}, oldest first."""
        raise FeatureUnavailable("this provider does not supply balance history")


# --------------------------------------------------------------------- sandbox
#
# SnapTrade has no synthetic sandbox: its free tier connects real brokerage
# accounts (up to five). The brief rules out connecting real accounts without
# approval, so development runs against this instead. It walks the same steps
# as the real flow, including a hosted-portal page that is clearly labelled as
# a sandbox and asks for no credentials, and its scenarios produce every state
# the UI has to handle.

SANDBOX_SCENARIOS = {
    "standard": "Two accounts (individual and Roth IRA), stocks, ETFs, one option, cash",
    "edge": "Canadian dollars, a mini option, crypto, missing cost basis, an unsupported asset",
    "partial": "Positions arrive but options and balances fail: a partial sync",
    "expired": "The authorisation expires after the first sync",
    "outage": "The provider is down for every sync after the first",
    "unsupported": "The broker is not supported: the connection cannot be made",
}


# Transactions for the sandbox's standard and edge accounts, chosen so the
# cash they leave matches the cash the holdings report (individual 2,400,
# Roth 300): a performance view built on them can be checked by hand. The
# 1,000 TRANSFER on 2026-05-01 leaves the individual account and arrives in
# the Roth, so across both linked accounts it is not money in or out.
# (id, type, trade date, symbol, units, price, amount, description, extra)
SANDBOX_ACTIVITIES: Dict[str, List[tuple]] = {
    "ind": [
        ("i01", "CONTRIBUTION", "2026-01-02", None, None, None, 26663.50, "Bank deposit", {}),
        ("i02", "BUY", "2026-01-05", "AAPL", 40, 150.10, -6004.00, "Bought 40 AAPL", {}),
        ("i03", "BUY", "2026-01-05", "MSFT", 15, 301.00, -4515.00, "Bought 15 MSFT", {}),
        ("i04", "BUY", "2026-01-06", "NVDA", 60, 48.25, -2895.00, "Bought 60 NVDA", {}),
        ("i05", "BUY", "2026-01-06", "VOO", 20, 380.00, -7600.00, "Bought 20 VOO", {}),
        ("i06", "BUY", "2026-01-07", None, 2, 4.10, -820.00, "Bought 2 AAPL Dec 18 2026 250 calls",
         {"option_occ": "AAPL  261218C00250000", "option_action": "BUY_TO_OPEN", "symbol_under": "AAPL"}),
        ("i07", "DIVIDEND", "2026-02-12", "AAPL", None, None, 10.40, "AAPL dividend", {}),
        ("i08", "FEE", "2026-03-02", None, None, None, -5.00, "Account maintenance fee", {}),
        ("i09", "DIVIDEND", "2026-03-27", "VOO", None, None, 32.10, "VOO dividend", {}),
        ("i10", "WITHDRAWAL", "2026-04-15", None, None, None, -1500.00, "Bank withdrawal", {}),
        ("i11", "TRANSFER", "2026-05-01", None, None, None, -1000.00, "Transfer to Roth IRA", {}),
        ("i12", "DIVIDEND", "2026-06-26", "VOO", None, None, 33.00, "VOO dividend", {}),
    ],
    "roth": [
        ("r01", "CONTRIBUTION", "2026-01-02", None, None, None, 14136.05, "Roth contribution", {}),
        ("r02", "BUY", "2026-01-08", "VOO", 30, 401.20, -12036.00, "Bought 30 VOO", {}),
        ("r03", "BUY", "2026-01-09", "SCHD", 50, 24.10, -1205.00, "Bought 50 SCHD", {}),
        ("r04", "BUY", "2026-01-09", "AAPL", 10, 172.00, -1720.00, "Bought 10 AAPL", {}),
        ("r05", "DIVIDEND", "2026-03-25", "SCHD", None, None, 13.50, "SCHD dividend", {}),
        ("r06", "DIVIDEND", "2026-03-27", "VOO", None, None, 48.15, "VOO dividend", {}),
        ("r07", "TRANSFER", "2026-05-01", None, None, None, 1000.00, "Transfer from Individual", {}),
        ("r08", "DIVIDEND", "2026-06-24", "SCHD", None, None, 13.80, "SCHD dividend", {}),
        ("r09", "DIVIDEND", "2026-06-26", "VOO", None, None, 49.50, "VOO dividend", {}),
    ],
    "tfsa": [
        ("t01", "CONTRIBUTION", "2026-02-02", None, None, None, 8000.00, "Deposit", {"currency": "CAD"}),
        ("t02", "BUY", "2026-02-03", "SHOP.TO", 25, 98.00, -2450.00, "Bought 25 SHOP", {"currency": "CAD"}),
        ("t03", "BUY", "2026-02-03", "XEQT.TO", 100, 30.00, -3000.00, "Bought 100 XEQT", {"currency": "CAD"}),
    ],
    "margin": [
        ("m01", "CONTRIBUTION", "2026-02-02", None, None, None, 10000.00, "Deposit", {}),
        ("m02", "SELL", "2026-02-10", "TSLA", -10, 240.00, 2400.00, "Sold short 10 TSLA", {}),
        ("m03", "INTEREST", "2026-03-31", None, None, None, -15.20, "Margin interest", {}),
        ("m04", "EXTERNAL_ASSET_TRANSFER_IN", "2026-04-02", None, 1, None, None,
         "Transfer in: Example Holdings LP", {}),
    ],
}

# Kinds of activity that move money across the account's boundary rather than
# within it. TRANSFER is here too: between two linked accounts it nets to
# nothing, which is for the performance maths to see, not the provider.
EXTERNAL_FLOW_TYPES = ("CONTRIBUTION", "WITHDRAWAL", "TRANSFER", "EXTERNAL_ASSET_TRANSFER_IN",
                       "EXTERNAL_ASSET_TRANSFER_OUT")


def _sandbox_activity(row: tuple) -> Activity:
    aid, kind, day, sym, units, price, amount, desc, extra = row
    return Activity(id=aid, type=kind, trade_date=day, settlement_date=day,
                    symbol=sym or extra.get("symbol_under"), option_occ=extra.get("option_occ"),
                    option_action=extra.get("option_action"), units=units, price=price, amount=amount,
                    currency=extra.get("currency", "USD"), fee=0.0 if kind in ("BUY", "SELL") else None,
                    description=desc)


def _p(symbol, kind, qty, price, avg, desc=None, ccy="USD", raw=None):
    return Position(symbol=symbol, description=desc or symbol or "", kind=kind, currency=ccy,
                    quantity=qty, price=price, avg_cost=avg, raw_type=raw)


class SandboxProvider(Provider):
    name = "sandbox"
    mode = "sandbox"
    label = "Optic sandbox brokerage"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, Dict[str, str]] = {}

    # The scenario is encoded in the connection id so a restart of the dev
    # server does not orphan connections the accounts database still holds.
    @staticmethod
    def _scenario(connection_id: str) -> str:
        parts = (connection_id or "").split("-")
        return parts[1] if len(parts) > 2 and parts[1] in SANDBOX_SCENARIOS else "standard"

    def _user(self, puid: str) -> Dict[str, Any]:
        return self._users.setdefault(puid, {"connections": {}, "syncs": {}})

    def register_user(self) -> Dict[str, str]:
        return {"user_id": "sbxu-" + secrets.token_hex(8), "secret": secrets.token_urlsafe(24)}

    def delete_user(self, provider_user_id: str) -> None:
        with self._lock:
            self._users.pop(provider_user_id, None)

    def portal_url(self, provider_user_id, secret, redirect_url, reconnect=None) -> str:
        session = secrets.token_urlsafe(16)
        with self._lock:
            self._sessions[session] = {"user": provider_user_id, "redirect": redirect_url,
                                       "reconnect": reconnect or ""}
        return "/api/brokerage/sandbox/portal?" + urllib.parse.urlencode({"session": session})

    def portal_session(self, session: str) -> Optional[Dict[str, str]]:
        with self._lock:
            return self._sessions.get(session)

    def authorize(self, session: str, scenario: str) -> str:
        """What the hosted portal does when the reader approves: creates (or
        repairs) a connection and returns where to send the browser next."""
        with self._lock:
            found = self._sessions.pop(session, None)
            if not found:
                raise ProviderError("That sandbox portal link has expired. Start again from Optic.")
            user = self._user(found["user"])
            if scenario == "unsupported":
                return _with_query(found["redirect"], status="ERROR", reason="UNSUPPORTED_BROKER")
            if found["reconnect"] and found["reconnect"] in user["connections"]:
                user["connections"][found["reconnect"]]["disabled"] = False
                user["syncs"][found["reconnect"]] = -1
                return _with_query(found["redirect"], status="SUCCESS")
            scenario = scenario if scenario in SANDBOX_SCENARIOS else "standard"
            cid = "sbx-{}-{}".format(scenario, secrets.token_hex(4))
            user["connections"][cid] = {"disabled": False}
            user["syncs"][cid] = -1
        return _with_query(found["redirect"], status="SUCCESS")

    def list_connections(self, provider_user_id, secret) -> List[Connection]:
        with self._lock:
            user = self._user(provider_user_id)
            return [Connection(id=cid, institution="Sandbox Brokerage ({})".format(self._scenario(cid)),
                               disabled=bool(c["disabled"]),
                               disabled_reason="Authorisation expired" if c["disabled"] else None,
                               read_only=c.get("type", "read") == "read")
                    for cid, c in user["connections"].items()]

    def remove_connection(self, provider_user_id, secret, connection_id) -> None:
        with self._lock:
            user = self._user(provider_user_id)
            user["connections"].pop(connection_id, None)

    @staticmethod
    def _broker_time() -> str:
        # A broker report six hours before the fetch, so the page has a
        # broker "as of" that differs from Optic's fetch time, as on a real
        # once-a-day plan.
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def list_accounts(self, provider_user_id, secret) -> List[Account]:
        # One sync calls this once, so this is where the sync count moves.
        # Moving it inside holdings() priced the second account one sync
        # later than the first, and the same ETF got two prices.
        with self._lock:
            user = self._user(provider_user_id)
            for cid in user["connections"]:
                user["syncs"][cid] = user["syncs"].get(cid, -1) + 1
        out: List[Account] = []
        for conn in self.list_connections(provider_user_id, secret):
            scenario = self._scenario(conn.id)
            tag = hashlib.sha1(conn.id.encode()).hexdigest()[:4]
            if scenario == "edge":
                out.append(Account(id=conn.id + ":tfsa", connection_id=conn.id, name="TFSA",
                                   number_mask="..{}".format(tag[:2] + "21"), institution=conn.institution,
                                   account_type="TFSA", currency="CAD", total_value=None, broker_as_of=self._broker_time()))
                out.append(Account(id=conn.id + ":margin", connection_id=conn.id, name="Margin",
                                   number_mask="..{}".format(tag[:2] + "88"), institution=conn.institution,
                                   account_type="Margin", currency="USD", total_value=None, broker_as_of=self._broker_time()))
            else:
                out.append(Account(id=conn.id + ":ind", connection_id=conn.id, name="Individual",
                                   number_mask="..{}".format(tag[:2] + "04"), institution=conn.institution,
                                   account_type="Individual", currency="USD",
                                   broker_as_of=self._broker_time()))
                if scenario == "standard":
                    out.append(Account(id=conn.id + ":roth", connection_id=conn.id, name="Roth IRA",
                                       number_mask="..{}".format(tag[:2] + "57"),
                                       institution=conn.institution, account_type="Roth IRA",
                                       currency="USD", broker_as_of=self._broker_time()))
        return out

    def holdings(self, provider_user_id, secret, account_id) -> Holdings:
        cid, _, which = account_id.rpartition(":")
        scenario = self._scenario(cid)
        with self._lock:
            user = self._user(provider_user_id)
            conn = user["connections"].get(cid)
            if conn is None:
                raise ProviderError("connection not found at the provider")
            n = max(0, user["syncs"].get(cid, 0))
            if conn["disabled"]:
                raise AuthExpired("The broker needs you to sign in again.")
            if scenario == "outage" and n >= 1:
                raise ProviderOutage("The provider is not responding.")
            if scenario == "expired" and n >= 1:
                conn["disabled"] = True
                raise AuthExpired("The broker needs you to sign in again.")
        # Prices drift a little on each sync, and the second sync trims NVDA and
        # opens AMD, so "what changed since my last sync" has something to say.
        drift = 1.0 + 0.012 * n
        h = Holdings()
        if which == "ind":
            nvda = 60 if n == 0 else 45
            h.positions = [
                _p("AAPL", "equity", 40, round(227.50 * drift, 2), 150.10, "Apple Inc.", raw="cs"),
                _p("MSFT", "equity", 15, round(418.20 * drift, 2), 301.00, "Microsoft Corp.", raw="cs"),
                _p("NVDA", "equity", nvda, round(132.40 * drift, 2), 48.25, "NVIDIA Corp.", raw="cs"),
                _p("VOO", "etf", 20, round(512.00 * drift, 2), 380.00, "Vanguard S&P 500 ETF", raw="et"),
            ]
            if n >= 1:
                h.positions.append(_p("AMD", "equity", 25, 158.30, 158.30, "Advanced Micro Devices", raw="cs"))
            h.options = [OptionPosition(underlying="AAPL", occ="AAPL  261218C00250000", option_type="call",
                                        strike=250.0, expiry="2026-12-18", contracts=2, price=6.40,
                                        avg_cost=4.10, currency="USD", multiplier=100)]
            h.cash = [Cash("USD", 2400.0 if n == 0 else 4386.0, None)]
        elif which == "roth":
            h.positions = [
                _p("VOO", "etf", 30, round(512.00 * drift, 2), 401.20, "Vanguard S&P 500 ETF", raw="et"),
                _p("SCHD", "etf", 50, round(27.80 * drift, 2), 24.10, "Schwab US Dividend Equity ETF", raw="et"),
                _p("AAPL", "equity", 10, round(227.50 * drift, 2), 172.00, "Apple Inc.", raw="cs"),
            ]
            h.cash = [Cash("USD", 300.0, None)]
        elif which == "tfsa":
            h.positions = [
                _p("SHOP.TO", "equity", 25, 152.40, 98.00, "Shopify Inc.", ccy="CAD", raw="cs"),
                _p("XEQT.TO", "etf", 100, 33.10, None, "iShares Core Equity ETF Portfolio", ccy="CAD", raw="et"),
            ]
            h.cash = [Cash("CAD", 1250.0, None)]
        elif which == "margin":
            h.positions = [
                _p("TSLA", "equity", -10, 251.00, 240.00, "Tesla Inc. (short)", raw="cs"),
                _p("BTC", "crypto", 0.05, 62000.0, None, "Bitcoin", raw="crypto"),
                _p(None, "other", 1, None, None, "Private placement: Example Holdings LP", raw="pp"),
            ]
            h.options = [OptionPosition(underlying="SPY", occ="SPY7  261120P00500000", option_type="put",
                                        strike=500.0, expiry="2026-11-20", contracts=-3, price=4.10,
                                        avg_cost=5.50, currency="USD", mini=True)]
            h.cash = [Cash("USD", -1500.0, 8200.0)]
        if scenario == "partial" and which == "ind":
            h.options = []
            h.cash = []
            h.problems = ["options", "balances"]
        return h


    def _live_connection(self, provider_user_id: str, cid: str) -> str:
        """The checks every read makes, in the order holdings() makes them."""
        scenario = self._scenario(cid)
        with self._lock:
            conn = self._user(provider_user_id)["connections"].get(cid)
            if conn is None:
                raise ProviderError("connection not found at the provider")
            n = max(0, self._user(provider_user_id)["syncs"].get(cid, 0))
            if conn["disabled"]:
                raise AuthExpired("The broker needs you to sign in again.")
            if scenario == "outage" and n >= 1:
                raise ProviderOutage("The provider is not responding.")
        return scenario

    def activities(self, provider_user_id, secret, account_id, start_date=None) -> List[Activity]:
        cid, _, which = account_id.rpartition(":")
        if self._live_connection(provider_user_id, cid) == "partial":
            raise ProviderError("transactions did not arrive for this account")
        out = [_sandbox_activity(r) for r in SANDBOX_ACTIVITIES.get(which, [])]
        return [a for a in out if not start_date or (a.trade_date or "") >= start_date]

    def balance_history(self, provider_user_id, secret, account_id) -> Dict[str, Any]:
        """Daily totals from the first deposit to yesterday: the money put in so
        far, grown along a gentle wave. Shaped like SnapTrade's estimate (one
        value a day, weekends included), not meant to match the holdings."""
        import math
        from datetime import date, timedelta
        cid, _, which = account_id.rpartition(":")
        if self._live_connection(provider_user_id, cid) == "edge":
            raise FeatureUnavailable("SnapTrade returned 403 (balance history is an add-on that is not enabled)")
        acts = [_sandbox_activity(r) for r in SANDBOX_ACTIVITIES.get(which, [])]
        flows = sorted((a.trade_date, a.amount or 0.0) for a in acts if a.type in EXTERNAL_FLOW_TYPES)
        if not flows:
            return {"currency": "USD", "points": []}
        start = date.fromisoformat(flows[0][0])
        end = date.today() - timedelta(days=1)
        points = []
        day = start
        while day <= end:
            base = sum(v for d, v in flows if d <= day.isoformat())
            k = (day - start).days
            points.append((day.isoformat(), round(base * (1 + 0.12 * k / 365 + 0.02 * math.sin(k / 9)), 2)))
            day += timedelta(days=1)
        return {"currency": "USD", "points": points}


def _with_query(url: str, **params: str) -> str:
    sep = "&" if "?" in url else "?"
    return url + sep + urllib.parse.urlencode(params)
