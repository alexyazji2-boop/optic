"""Optic's Positions — a public paper-trading ledger.

The terminal takes its own simulated trades so its recommendations carry a
visible track record instead of only ever being forward-looking claims. One
shared ledger, identical for every visitor: this is the *system's* record, not a
per-user portfolio, so it needs no accounts.

Two instrument types, because the Swing tab produces both kinds of idea:

* **Shares** — unambiguous P&L, and a stop-loss means exactly what it says.
* **Option contracts** — matches the strike recommendations the terminal
  actually makes. Marked by looking the same contract up in the live chain each
  time; Black-Scholes is only a fallback when the contract has gone illiquid or
  stopped being quoted.

Everything here is simulated. Fills assume the mid price, which is optimistic on
a wide spread, and no commission or slippage is modelled. The ledger records
those assumptions alongside every trade rather than presenting the numbers as
what a real account would have made.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from . import legal, universe
from .analytics import screen
from .analytics.greeks import bs_price, implied_vol

# --------------------------------------------------------------- configuration

# Notional account the ledger trades. Not real money; it exists to make position
# sizing meaningful and P&L comparable across trades.
START_EQUITY = float(os.environ.get("TRACKER_EQUITY", "100000"))

# Fraction of equity risked per trade. 1% is the textbook figure and keeps a
# losing streak survivable — 20 consecutive losers costs about 18% of capital.
RISK_PER_TRADE = float(os.environ.get("TRACKER_RISK_PCT", "1.0")) / 100.0

# A single option position can't risk more than this share of equity even if the
# stop maths says otherwise: long premium can go to zero, so "risk" is the whole
# ticket and sizing off a stop distance would understate it.
MAX_OPTION_RISK = 0.02

# Ceiling for letting a single contract through when even one costs more than the
# budget above. Without this the ledger would only ever hold cheap options — a
# deep-ITM put on a $300 stock runs $3,000 a contract — and the record would
# quietly stop matching the recommendations the terminal actually made.
OPTION_SINGLE_CONTRACT_CAP = 0.05

# Composite score a setup must clear before the ledger will take it. Deliberately
# above the "leaning" band — the tracker should trade conviction, not noise.
MIN_COMPOSITE = 30.0

# Hard time stop. An idea that hasn't worked in this many calendar days is closed
# so the ledger reflects decisions rather than accumulating forgotten positions.
MAX_HOLD_DAYS = 45

# One position per ticker at a time, so the record can't be gamed by stacking.
#
# The universe the scan draws from. "nasdaq" is every NASDAQ-listed common stock
# from NASDAQ's own directory — about 3,000 names — put through a cheap price and
# volume screen before anything expensive runs. "watchlist" is the ten-name list
# below, kept for quick local testing.
DEFAULT_UNIVERSE = os.environ.get("TRACKER_UNIVERSE", "nasdaq")
DEFAULT_WATCHLIST = ["SPY", "QQQ", "NVDA", "AAPL", "MSFT", "AMD", "TSLA", "GOOGL", "META", "AMZN"]

# How many of the screen's top-ranked names get the full analysis. At roughly four
# seconds each this is the main cost of a scan, so it's a direct trade of scan
# time against how deep into the ranking the tracker is willing to look.
SHORTLIST_SIZE = int(os.environ.get("TRACKER_SHORTLIST", "30"))

# Portfolio caps. With ten tickers these never bound; over the whole exchange a
# single scan can find thirty qualifying setups, and taking all of them at 1%
# each would put a third of the account at risk in an afternoon — on names that
# are mostly the same momentum bet under different tickers.
MAX_OPEN_POSITIONS = int(os.environ.get("TRACKER_MAX_POSITIONS", "20"))
MAX_PORTFOLIO_RISK = float(os.environ.get("TRACKER_MAX_PORTFOLIO_RISK_PCT", "15")) / 100.0

# Cap per scan as well as in aggregate, so the book fills over days instead of in
# one pass — which also keeps the entries spread across different market days
# rather than all sharing one afternoon's conditions.
MAX_NEW_PER_SCAN = int(os.environ.get("TRACKER_MAX_NEW_PER_SCAN", "6"))

# The ledger file. Defaults inside TRACKER_DATA_DIR so it lands on the same
# mounted disk as the symbol directory and the screener cache — those two already
# honoured that variable, and the ledger only agreed with them by accident of the
# container's layout. TRACKER_DB still overrides for a one-off path.

# --------------------------------------------------------------------- books
#
# Three books running the same scan against different rules. That is the whole
# design: they see identical candidates, so comparing them says what a risk
# tolerance costs and earns rather than comparing three different signals.
#
# They differ in the four things that actually change a risk/reward profile —
# how selective the entry bar is, how much is risked per trade, which
# instruments are allowed, and how volatile a name may be. Nothing here changes
# the analysis; a setup is a setup, and these decide what to do about it.
#
# Options are the lever that matters most. A defined-risk option position can
# lose its whole premium, which is why the conservative book will not hold them
# at all and the aggressive book prefers them.
#
# `max_notional_pct` is per-book for a reason that only showed up once the books
# were compared on a real candidate. Sizing is stop-based, so a tight stop asks
# for a very large position, and a single 25% cap used to bind on every book at
# once — all three took the same size on NVIDIA, and the aggressive book actually
# risked LESS than the balanced one because it had less equity. The cap itself is
# right (a tight stop must not produce a position bigger than the account) but one
# constant across books with a fourfold spread in risk appetite erases the only
# thing they were built to show.
BOOKS: Dict[str, Dict[str, Any]] = {
    "conservative": {
        "id": "conservative",
        "label": "Conservative",
        "tagline": "Low risk, low reward",
        "blurb": ("Shares only, and only the setups that clear a high bar. Half the "
                  "risk per trade, a smaller book, and no option premium that can "
                  "expire worthless."),
        "risk_per_trade": 0.005,
        "min_composite": 55.0,
        "allow_options": False,
        "prefer_options": False,
        "max_atr_pct": 5.0,
        "max_positions": 8,
        "max_portfolio_risk": 0.06,
        "max_new_per_scan": 3,
        "max_notional_pct": 0.12,
    },
    "balanced": {
        "id": "balanced",
        "label": "Balanced",
        "tagline": "Medium risk, medium reward",
        "blurb": ("Shares and options, at the textbook 1% of equity per trade. The "
                  "middle book, and the one the terminal's existing record belongs "
                  "to."),
        "risk_per_trade": 0.010,
        "min_composite": 30.0,
        "allow_options": True,
        "prefer_options": False,
        "max_atr_pct": 8.0,
        "max_positions": 20,
        "max_portfolio_risk": 0.15,
        "max_new_per_scan": 6,
        "max_notional_pct": 0.25,
    },
    "aggressive": {
        "id": "aggressive",
        "label": "Aggressive",
        "tagline": "High risk, high reward",
        "blurb": ("Options preferred and twice the risk per trade, with more "
                  "volatile names allowed through. The book most likely to post the "
                  "best month and the worst one."),
        "risk_per_trade": 0.020,
        "min_composite": 30.0,
        "allow_options": True,
        "prefer_options": True,
        "max_atr_pct": 12.0,
        "max_positions": 25,
        "max_portfolio_risk": 0.25,
        "max_new_per_scan": 8,
        "max_notional_pct": 0.4,
    },
}

BOOK_IDS = list(BOOKS)
DEFAULT_BOOK = "balanced"


def book_config(book: Optional[str]) -> Dict[str, Any]:
    """Config for a book id, falling back to the balanced defaults."""
    return BOOKS.get((book or "").lower(), BOOKS[DEFAULT_BOOK])

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
DB_PATH = os.environ.get("TRACKER_DB", os.path.join(_DATA_DIR, "tracker.db"))

_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------- market session
#
# The ledger has to know whether the tape is live. Two things go wrong otherwise,
# and both quietly fabricate history rather than erroring:
#
#   * Entries taken while the market is shut fill at a stale last price, with a
#     stop and target derived from it — an entry nobody could have got.
#   * Exit checks compare against the *session's* high and low, which for a
#     position opened during that same session includes hours that happened
#     before the entry. A stop could "trigger" off a low set that morning.

_ET = ZoneInfo("America/New_York")

# Regular US equity session. Pre- and post-market are deliberately excluded: the
# quotes are thin, the options chains barely trade, and a simulated fill there is
# the least believable kind.
SESSION_OPEN_MINUTES = 9 * 60 + 30
SESSION_CLOSE_MINUTES = 16 * 60


def market_open_et(when: Optional[datetime] = None) -> bool:
    """True during the regular session. Ignores market holidays — yfinance simply
    returns the prior close on those, so a scan finds nothing new and the guard
    below keeps it from trading on it."""
    now = (when or datetime.now(timezone.utc)).astimezone(_ET)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return SESSION_OPEN_MINUTES <= minutes < SESSION_CLOSE_MINUTES


def _session_date_et(iso: Optional[str]) -> Optional[str]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).astimezone(_ET).date().isoformat()
    except (TypeError, ValueError):
        return None


def _entered_this_session(pos: Dict[str, Any]) -> bool:
    today = datetime.now(timezone.utc).astimezone(_ET).date().isoformat()
    return _session_date_et(pos.get("entry_at")) == today


def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        if value is None:
            return None
        out = float(value)
        if not np.isfinite(out):
            return None
        return round(out, digits)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------- storage


SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker        TEXT NOT NULL,
    instrument    TEXT NOT NULL,          -- 'shares' | 'option'
    direction     TEXT NOT NULL,          -- 'long' | 'short'
    option_type   TEXT,                   -- 'call' | 'put' (options only)
    strike        REAL,
    expiry        TEXT,
    qty           REAL NOT NULL,          -- shares, or contracts
    entry_price   REAL NOT NULL,          -- share price, or premium per share
    entry_spot    REAL NOT NULL,
    entry_at      TEXT NOT NULL,
    stop          REAL,
    target        REAL,
    risk_dollars  REAL,
    composite     REAL,
    thesis        TEXT,
    status        TEXT NOT NULL,          -- 'open' | 'closed'
    mark_price    REAL,
    mark_spot     REAL,
    marked_at     TEXT,
    mark_source   TEXT,                   -- how the mark was obtained
    exit_price    REAL,
    exit_spot     REAL,
    exit_at       TEXT,
    exit_reason   TEXT,
    pnl           REAL,
    pnl_pct       REAL,
    book          TEXT NOT NULL DEFAULT 'balanced'
);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE TABLE IF NOT EXISTS scans (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at     TEXT NOT NULL,
    trigger    TEXT NOT NULL,             -- 'manual' | 'scheduled'
    considered INTEGER,
    opened     INTEGER,
    closed     INTEGER,
    notes      TEXT,
    funnel     TEXT,                         -- JSON: universe, screen counts, shortlist
    book       TEXT NOT NULL DEFAULT 'balanced'
);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    # WAL so a read during a scan doesn't block; the ledger is read far more
    # often than it's written.
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _LOCK, _connect() as conn:
        conn.executescript(SCHEMA)
        # Additive migration: a ledger written by an older build is missing this
        # column, and dropping the table would throw away the track record —
        # which is the one thing here that can't be regenerated.
        have = {r[1] for r in conn.execute("PRAGMA table_info(positions)")}
        if "mark_source" not in have:
            conn.execute("ALTER TABLE positions ADD COLUMN mark_source TEXT")
        # Existing trades predate the three books and belong to the balanced one:
        # they were taken under its rules — 1% risk, shares and options, a
        # composite floor of 30 — so backfilling them anywhere else would put a
        # record under a rule set that never produced it.
        if "book" not in have:
            conn.execute(
                "ALTER TABLE positions ADD COLUMN book TEXT NOT NULL DEFAULT 'balanced'")
            conn.execute("UPDATE positions SET book='balanced' WHERE book IS NULL")
        have_scans = {r[1] for r in conn.execute("PRAGMA table_info(scans)")}
        if "funnel" not in have_scans:
            conn.execute("ALTER TABLE scans ADD COLUMN funnel TEXT")
        if "book" not in have_scans:
            conn.execute(
                "ALTER TABLE scans ADD COLUMN book TEXT NOT NULL DEFAULT 'balanced'")
        # Only now that the column is guaranteed to exist.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_book ON positions(book, status)")


def _rows(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with _LOCK, _connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ------------------------------------------------------------------- sizing


def size_shares(entry: float, stop: float, equity: float,
                book: Optional[str] = None) -> Dict[str, Any]:
    """Shares sized so a stop-out costs exactly the risk budget.

    This is the whole point of a stop-based size: the position is large when the
    stop is tight and small when it's wide, so every trade risks the same amount
    regardless of how volatile the name is.
    """
    risk_dollars = equity * book_config(book)['risk_per_trade']
    per_share = abs(entry - stop)
    if per_share <= 0:
        return {"qty": 0, "risk_dollars": 0.0, "reason": "stop is at the entry price"}
    qty = int(risk_dollars / per_share)
    if qty < 1:
        return {"qty": 0, "risk_dollars": 0.0,
                "reason": "stop distance is wider than the risk budget allows for one share"}
    notional = qty * entry
    # Concentration cap, per book. Sizing purely off a very tight stop can
    # otherwise ask for a position larger than the account. Per book rather than
    # one constant: a single 25% bound on all three made them take identical sizes
    # on exactly the tight-stop names most likely to trigger, which is where the
    # difference between them was supposed to show up.
    cap_pct = book_config(book).get("max_notional_pct", 0.25)
    if notional > equity * cap_pct:
        qty = int(equity * cap_pct / entry)
        if qty < 1:
            return {"qty": 0, "risk_dollars": 0.0, "reason": "share price too high for a capped position"}
    return {
        "qty": qty,
        "risk_dollars": _f(qty * per_share, 2),
        "notional": _f(qty * entry, 2),
        # Whether the concentration cap decided the size rather than the risk
        # budget. Without this a position that risks a third of its allowance
        # looks like a sizing bug instead of a cap doing its job.
        "capped": bool(qty * entry >= equity * cap_pct - entry),
        "reason": None,
    }


def size_option(premium: float, equity: float,
                book: Optional[str] = None) -> Dict[str, Any]:
    """Contracts sized on premium at risk, not on a stop distance.

    A long option's realistic worst case is the whole premium, so that's what
    gets budgeted. Using a stop-based size here would claim a smaller risk than
    the position actually carries — a gap through the stop overnight leaves no
    opportunity to honour it.
    """
    if premium <= 0:
        return {"qty": 0, "risk_dollars": 0.0, "reason": "no premium quoted"}
    cfg = book_config(book)
    budget = equity * min(cfg['risk_per_trade'] * 2, MAX_OPTION_RISK)
    per_contract = premium * 100.0
    qty = int(budget / per_contract)
    note = None
    if qty < 1:
        # An expensive contract — a deep-ITM put on a $300 stock can cost $3,000 —
        # would otherwise be skipped every time, and the ledger would end up
        # holding only cheap options while quietly never taking the recommendation
        # it actually made. One contract is allowed through, up to a hard ceiling,
        # with the oversized risk recorded rather than hidden.
        if per_contract <= equity * OPTION_SINGLE_CONTRACT_CAP:
            return {
                "qty": 1,
                "risk_dollars": _f(per_contract, 2),
                "notional": _f(per_contract, 2),
                "reason": None,
                "note": "one contract costs {:.1f}% of equity, above the usual {:.1f}% budget . "
                        "Taken as a single contract so the ledger doesn't silently skip "
                        "expensive recommendations".format(
                            per_contract / equity * 100.0, budget / equity * 100.0),
            }
        return {"qty": 0, "risk_dollars": 0.0,
                "reason": "one contract costs {:.1f}% of equity, past the {:.0f}% ceiling".format(
                    per_contract / equity * 100.0, OPTION_SINGLE_CONTRACT_CAP * 100.0)}
    return {
        "qty": qty,
        "risk_dollars": _f(qty * per_contract, 2),
        "notional": _f(qty * per_contract, 2),
        "reason": None,
        "note": note,
    }


# --------------------------------------------------------------- option marks


def _find_contract(chain: pd.DataFrame, strike: float, expiry: str,
                   is_call: bool) -> Optional[Dict[str, Any]]:
    if chain is None or chain.empty:
        return None
    match = chain[
        (chain["expiry"] == expiry)
        & (chain["is_call"] == is_call)
        & (np.isclose(chain["strike"].astype(float), float(strike)))
    ]
    if match.empty:
        return None
    row = match.iloc[0]
    mid = row.get("mid")
    try:
        mid = float(mid)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(mid) or mid <= 0:
        return None
    return {"mid": mid, "iv": _f(row.get("iv"))}


def mark_option(provider, pos: Dict[str, Any], spot: float, rate: float) -> Dict[str, Any]:
    """Current value of an option position.

    Preference order matters: the live chain is what the position could actually
    be closed at, so it wins. Black-Scholes is a model estimate and only used
    when the contract has no usable quote — flagged so the ledger never presents
    a modelled mark as a real one.
    """
    expiry = pos["expiry"]
    is_call = pos["option_type"] == "call"
    dte = (pd.Timestamp(expiry) - pd.Timestamp.today().normalize()).days

    if dte < 0:
        # Expired: worth only whatever it's in the money by.
        intrinsic = max(0.0, (spot - pos["strike"]) if is_call else (pos["strike"] - spot))
        return {"price": _f(intrinsic, 4), "source": "Expired (intrinsic value)", "dte": dte}

    try:
        chain = provider.options_chain(pos["ticker"], [expiry])
        found = _find_contract(chain, pos["strike"], expiry, is_call)
        if found:
            return {"price": _f(found["mid"], 4), "source": "Live chain mid", "dte": dte,
                    "iv": found.get("iv")}
    except Exception:
        pass

    # Fallback: reprice with the entry's implied vol. Vol almost certainly moved,
    # so this is an estimate — labelled as one.
    tau = max(dte, 1) / 365.0
    entry_dte = max((pd.Timestamp(expiry) - pd.Timestamp(pos["entry_at"][:10])).days, 1)
    iv = implied_vol(pos["entry_price"], pos["entry_spot"], pos["strike"],
                     entry_dte / 365.0, rate=rate, is_call=is_call)
    if not iv or not np.isfinite(iv):
        iv = 0.4
    modelled = bs_price(spot, pos["strike"], tau, iv, rate=rate, is_call=is_call)
    return {"price": _f(modelled, 4), "source": "Modelled (no live quote)", "dte": dte,
            "iv": _f(iv)}


# ------------------------------------------------------------------ lifecycle


def _pnl(pos: Dict[str, Any], price: float) -> Dict[str, Any]:
    multiplier = 100.0 if pos["instrument"] == "option" else 1.0
    sign = 1.0 if pos["direction"] == "long" else -1.0
    gross = (price - pos["entry_price"]) * pos["qty"] * multiplier * sign
    cost = pos["entry_price"] * pos["qty"] * multiplier
    return {"pnl": _f(gross, 2), "pnl_pct": _f(gross / cost * 100.0, 2) if cost else None}


def open_position(entry: Dict[str, Any]) -> int:
    cols = ("ticker", "instrument", "direction", "option_type", "strike", "expiry", "qty",
            "entry_price", "entry_spot", "entry_at", "stop", "target", "risk_dollars",
            "composite", "thesis", "status", "mark_price", "mark_spot", "marked_at",
            "mark_source", "pnl", "pnl_pct", "book")
    # A brand-new position is flat, not unknown. Writing 0 rather than NULL keeps
    # the ledger's P&L column readable before the first marking pass runs.
    entry = dict(entry, pnl=0.0, pnl_pct=0.0,
                 book=(entry.get('book') or DEFAULT_BOOK))
    values = tuple(entry.get(c) for c in cols)
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO positions ({}) VALUES ({})".format(
                ",".join(cols), ",".join("?" * len(cols))),
            values,
        )
        return int(cur.lastrowid)


def close_position(pos_id: int, price: float, spot: float, reason: str,
                   pos: Dict[str, Any]) -> None:
    result = _pnl(pos, price)
    with _LOCK, _connect() as conn:
        conn.execute(
            "UPDATE positions SET status='closed', exit_price=?, exit_spot=?, exit_at=?,"
            " exit_reason=?, pnl=?, pnl_pct=?, mark_price=?, marked_at=? WHERE id=?",
            (_f(price, 4), _f(spot, 4), _now(), reason, result["pnl"], result["pnl_pct"],
             _f(price, 4), _now(), pos_id),
        )


def _exit_check(pos: Dict[str, Any], price: float, spot: float,
                bar_high: Optional[float], bar_low: Optional[float]) -> Optional[str]:
    """Whether this position should close, and why.

    Stops and targets are checked against the day's high and low rather than the
    last price: a level touched intraday would otherwise be missed entirely if
    price closed back inside it, which would flatter the record.
    """
    held = (datetime.now(timezone.utc) - datetime.fromisoformat(pos["entry_at"])).days

    if pos["instrument"] == "option":
        dte = (pd.Timestamp(pos["expiry"]) - pd.Timestamp.today().normalize()).days
        if dte <= 0:
            return "Expiry reached"
        # Premium-based exits: an option's stop has to be on its own price, since
        # the underlying can sit still while theta drains the position.
        if pos["entry_price"] and price <= pos["entry_price"] * 0.5:
            return "Premium stop (-50%)"
        if pos["entry_price"] and price >= pos["entry_price"] * 2.0:
            return "Premium target (+100%)"
        # The underlying invalidating the thesis closes it too. Note this cannot
        # use `direction`: for an option that field means *long premium*, which is
        # true of a put as well, while the thesis direction is the contract type.
        # Reading direction here closed every put the instant it was opened.
        bullish = pos["option_type"] == "call"
        if pos["stop"] and ((bullish and spot <= pos["stop"])
                            or (not bullish and spot >= pos["stop"])):
            return "Underlying broke the stop level"
        if held >= MAX_HOLD_DAYS:
            return "Time stop ({} days)".format(MAX_HOLD_DAYS)
        return None

    # Shares only from here: `direction` is unambiguous for them.
    long = pos["direction"] == "long"
    low = bar_low if bar_low is not None else price
    high = bar_high if bar_high is not None else price
    if pos["stop"] is not None:
        if (long and low <= pos["stop"]) or (not long and high >= pos["stop"]):
            return "Stop hit"
    if pos["target"] is not None:
        if (long and high >= pos["target"]) or (not long and low <= pos["target"]):
            return "Target hit"
    if held >= MAX_HOLD_DAYS:
        return "Time stop ({} days)".format(MAX_HOLD_DAYS)
    return None


def mark_open_positions(provider, rate: float = 0.0) -> Dict[str, int]:
    """Refresh every open position and close any that hit an exit."""
    open_rows = _rows("SELECT * FROM positions WHERE status='open'")
    closed = 0
    closed_positions: List[Dict[str, Any]] = []
    for pos in open_rows:
        try:
            quote = provider.quote(pos["ticker"])
            spot = quote.get("price")
            if not spot:
                continue
            bar_high, bar_low = quote.get("day_high"), quote.get("day_low")

            if pos["instrument"] == "option":
                mark = mark_option(provider, pos, spot, rate)
                price = mark["price"]
                source = mark["source"]
            else:
                price = spot
                source = "Last quote"

            if price is None:
                continue

            # The session's extremes are only evidence for an exit if the whole
            # session came after the entry. For a position opened today, a low set
            # this morning predates it, and using it would invent a stop-out.
            if _entered_this_session(pos):
                bar_high = bar_low = None

            reason = _exit_check(pos, price, spot, bar_high, bar_low)
            if reason:
                # Exit at the stop or target rather than the mark: that's the
                # price the order would have filled at. Otherwise a day that
                # traded through a level and came back would credit a better
                # exit than the plan allowed. For a stop the fill is the *worse*
                # of the level and the current price, because a gap opens below
                # a long's stop and the order fills there, not at the level.
                fill = price
                long_pos = pos["direction"] == "long"
                if pos["instrument"] == "shares" and reason == "Stop hit":
                    fill = min(pos["stop"], price) if long_pos else max(pos["stop"], price)
                elif pos["instrument"] == "shares" and reason == "Target hit":
                    fill = pos["target"]
                close_position(pos["id"], fill, spot, reason, pos)
                closed += 1
                # Same reason as the opens: an alert has to name the position and
                # why it exited, and a count cannot.
                closed_positions.append({
                    "id": pos["id"], "ticker": pos["ticker"],
                    "instrument": pos["instrument"], "direction": pos["direction"],
                    "entry_price": pos["entry_price"], "exit_price": fill,
                    "exit_reason": reason, "book": pos.get("book"),
                    "exit_at": _now(),
                })
                continue

            result = _pnl(pos, price)
            with _LOCK, _connect() as conn:
                conn.execute(
                    "UPDATE positions SET mark_price=?, mark_spot=?, marked_at=?, pnl=?,"
                    " pnl_pct=?, mark_source=? WHERE id=?",
                    (_f(price, 4), _f(spot, 4), _now(), result["pnl"], result["pnl_pct"],
                     source, pos["id"]),
                )
        except Exception:
            # One bad ticker must not abort the whole marking pass.
            continue
    return {"marked": len(open_rows), "closed": closed,
            "closed_positions": closed_positions}


# ---------------------------------------------------------------------- scan


def _pick_stop(snapshot: Dict[str, Any], spot: float, long: bool) -> Optional[float]:
    """Stop below the nearest real support (or above resistance for a short),
    falling back to 2x ATR when no level is close enough to be useful."""
    levels = (snapshot.get("technicals") or {}).get("support_resistance") or []
    if long:
        below = [lv for lv in levels if lv.get("price") and lv["price"] < spot * 0.995]
        if below:
            best = max(below, key=lambda lv: lv["price"])
            return round(best["price"] * 0.99, 2)  # just under the level
    else:
        above = [lv for lv in levels if lv.get("price") and lv["price"] > spot * 1.005]
        if above:
            best = min(above, key=lambda lv: lv["price"])
            return round(best["price"] * 1.01, 2)

    atr_val = ((snapshot.get("technicals") or {}).get("volatility") or {}).get("atr14")
    if atr_val:
        return round(spot - 2 * atr_val, 2) if long else round(spot + 2 * atr_val, 2)
    return None


def consider_ticker(snapshot: Dict[str, Any], equity: float,
                    book: Optional[str] = None) -> tuple[List[Dict[str, Any]], List[str]]:
    """Turn one ticker's snapshot into zero, one or two candidate entries, plus
    notes on anything it declined and why.

    Zero is the common case and the correct one: the ledger's job is to be
    selective, and a scan that opens something every time it runs is not a
    strategy. The notes matter as much as the trades — a leg dropped on sizing
    would otherwise look like the strategy simply never trades that instrument.

    `book` selects which set of rules to apply. It was missing from this signature
    while the body already used it and the scan loop already passed it, so every
    call raised TypeError and the scan reported "opened 0" instead of failing
    loudly. That silence is the reason it survived: the honest outcome of a
    selective strategy and a crashing one look identical in the ledger.
    """
    verdict = snapshot.get("verdict") or {}
    composite = verdict.get("composite_score")
    ticker = snapshot.get("ticker")
    spot = (snapshot.get("quote") or {}).get("price")
    notes: List[str] = []
    if composite is None or spot is None:
        return [], ["{}: no verdict or no price".format(ticker)]
    cfg = book_config(book)
    if abs(composite) < cfg["min_composite"]:
        return [], []

    # Volatility gate, per book. The conservative book will not hold a name whose
    # ordinary daily range can take out its own stop; the aggressive one will.
    atr_pct = _f(((snapshot.get("technicals") or {}).get("volatility") or {}).get("atr_pct"))
    if atr_pct is not None and atr_pct > cfg["max_atr_pct"]:
        return [], ["{}: daily range {:.1f}% exceeds the {} book's {:.0f}% limit".format(
            ticker, atr_pct, cfg["label"].lower(), cfg["max_atr_pct"])]

    long = composite > 0
    stop = _pick_stop(snapshot, spot, long)
    if stop is None:
        return [], ["{}: score {:+.0f} cleared the bar but no stop level could be "
                    "derived".format(ticker, composite)]

    candidates: List[Dict[str, Any]] = []
    risk_per_share = abs(spot - stop)
    # 2:1 reward-to-risk target. Fixed rather than fitted: a target derived from
    # the same indicators that triggered the entry would flatter the record.
    target = round(spot + 2 * risk_per_share, 2) if long else round(spot - 2 * risk_per_share, 2)

    # A short's target cannot sit at or below zero, and a stop wide enough to put
    # it there means the 2:1 reward-to-risk this book is built on is simply not
    # available on that name. Found live: LMB was recorded short at $42.60 with a
    # stop at $71.41 — a 68% stop — giving a target of -$15.02. The position could
    # only ever have exited at the stop or the time stop, while the ledger still
    # counted it as a 2R setup and reported the risk as if a 2R reward were on the
    # other side of it. Declining is the honest answer: the trade the rules
    # describe does not exist here.
    if not long and target <= 0:
        return [], ["{}: the stop sits {:.0f}% above the entry, so a 2:1 target lands at "
                    "{:.2f}. Below zero and unreachable. No short taken.".format(
                        ticker, 100 * risk_per_share / spot, target)]

    share_size = size_shares(spot, stop, equity, book)
    if share_size["qty"] <= 0:
        notes.append("{}: no share leg: {}".format(ticker, share_size["reason"]))
    else:
        candidates.append({
            "ticker": ticker, "instrument": "shares",
            "book": cfg["id"],
            "direction": "long" if long else "short",
            "option_type": None, "strike": None, "expiry": None,
            "qty": share_size["qty"], "entry_price": _f(spot, 4), "entry_spot": _f(spot, 4),
            "entry_at": _now(), "stop": stop, "target": target,
            "risk_dollars": share_size["risk_dollars"], "composite": _f(composite, 1),
            "thesis": verdict.get("summary") or "", "status": "open",
            "mark_price": _f(spot, 4), "mark_spot": _f(spot, 4), "marked_at": _now(),
            "mark_source": "Entry price",
        })

    if not cfg["allow_options"]:
        # Not a failure to report per ticker — it is the book's whole definition,
        # and repeating it on every name would bury the real notes.
        return candidates, notes

    # The option leg follows the terminal's own strike recommendation, so the
    # ledger tracks the advice actually given rather than a generic ATM contract.
    plan = snapshot.get("entry_plan") or {}
    pick = (plan.get("recommended") or {}) if plan.get("actionable") else {}
    if not pick.get("strike") or not pick.get("expiry") or not pick.get("entry_mid"):
        notes.append("{}: no option leg. The entry plan had no quotable contract".format(ticker))
    else:
        opt_size = size_option(float(pick["entry_mid"]), equity, book)
        if opt_size["qty"] <= 0:
            notes.append("{}: no option leg: {}".format(ticker, opt_size["reason"]))
        else:
            if opt_size.get("note"):
                notes.append("{}: {}".format(ticker, opt_size["note"]))
            candidates.append({
                "ticker": ticker, "instrument": "option", "direction": "long",
                "book": cfg["id"],
                "option_type": "call" if long else "put",
                "strike": _f(pick["strike"], 4), "expiry": pick["expiry"],
                "qty": opt_size["qty"], "entry_price": _f(pick["entry_mid"], 4),
                "entry_spot": _f(spot, 4), "entry_at": _now(),
                "stop": stop, "target": target,
                "risk_dollars": opt_size["risk_dollars"], "composite": _f(composite, 1),
                "thesis": verdict.get("summary") or "", "status": "open",
                "mark_price": _f(pick["entry_mid"], 4), "mark_spot": _f(spot, 4),
                "marked_at": _now(), "mark_source": "Entry price (chain mid)",
            })
    return candidates, notes


def _money(value: Optional[float]) -> str:
    return "${:,.0f}".format(value or 0.0)


def _feed_state() -> Dict[str, Any]:
    """Whether the upstream price feed is currently rate-limiting.

    Read through the yfinance module rather than off the provider, because the
    throttle is a property of the shared upstream session — it applies even when
    a paid provider is configured for quotes, since the screen and fundamentals
    still go through yfinance.
    """
    try:
        from .providers.yf import throttle_state
        return throttle_state()
    except Exception:
        return {"throttled": False}


def _feed_throttled() -> bool:
    return bool(_feed_state().get("throttled"))


# Longest the scan will ever sit waiting for a rate limit to clear. Bounded so a
# persistently throttled feed makes the scan short, not endless.
MAX_COOLOFF_SECONDS = float(os.environ.get("TRACKER_MAX_COOLOFF", "90"))

# Abandon the shortlist after this many names come back unusable. A feed this
# throttled won't recover within one scan, and every further name costs a full
# cool-off to learn the same thing.
MAX_THROTTLED_SKIPS = int(os.environ.get("TRACKER_MAX_THROTTLED_SKIPS", "5"))


def _cool_off(reason: str) -> bool:
    """Wait out an active rate limit. True if the feed came back."""
    deadline = time.time() + MAX_COOLOFF_SECONDS
    while time.time() < deadline:
        state = _feed_state()
        if not state.get("throttled"):
            return True
        remaining = min(float(state.get("seconds_remaining") or 5.0), deadline - time.time())
        _set_progress(stage="{} ({}s)".format(reason, int(max(remaining, 0))))
        time.sleep(min(max(remaining, 1.0), 10.0))
    return not _feed_throttled()


def equity_for(book: Optional[str] = None) -> float:
    """Starting capital plus that book's own realised P&L.

    Each book gets its own pool. Sharing one would make the aggressive book's
    losses shrink the conservative book's position sizes, which would turn three
    independent records into one entangled one and make the comparison
    meaningless.

    Realised only, deliberately: marking open positions into equity would let
    position sizing drift with unrealised swings.
    """
    if book:
        rows = _rows(
            "SELECT pnl FROM positions WHERE status='closed' AND book=?", (book,))
    else:
        rows = _rows("SELECT pnl FROM positions WHERE status='closed'")
    realised = sum(r["pnl"] or 0.0 for r in rows)
    return START_EQUITY + realised


def open_risk(book: Optional[str] = None) -> float:
    """Total dollars at risk across open positions, optionally for one book."""
    if book:
        rows = _rows(
            "SELECT risk_dollars FROM positions WHERE status='open' AND book=?", (book,))
    else:
        rows = _rows("SELECT risk_dollars FROM positions WHERE status='open'")
    return float(sum(r["risk_dollars"] or 0.0 for r in rows))


def _capacity(equity: float, book: Optional[str] = None) -> Dict[str, Any]:
    """How much room the book has left, and why.

    This exists because the universe got big. Scanning ten megacaps, caps were
    academic; scanning ~3,000 NASDAQ listings, a single scan can easily find
    thirty qualifying setups, and taking all of them at 1% each would put a third
    of the account at risk in one afternoon on names that are mostly the same
    momentum bet wearing different tickers.
    """
    cfg = book_config(book)
    rows = _rows("SELECT id FROM positions WHERE status='open' AND book=?", (cfg["id"],))
    risk = open_risk(cfg["id"])
    return {
        "book": cfg["id"],
        "open_positions": len(rows),
        "position_slots_left": max(cfg["max_positions"] - len(rows), 0),
        "open_risk": _f(risk, 2),
        "open_risk_pct": _f(risk / equity * 100.0, 2) if equity else None,
        "risk_budget_left": _f(max(equity * cfg["max_portfolio_risk"] - risk, 0.0), 2),
    }


# --------------------------------------------------------------- scan progress
#
# A NASDAQ-wide scan takes minutes, not seconds, so the request that starts it
# can't be the one that returns the result. Progress is published here for the
# tab to poll.

_PROGRESS: Dict[str, Any] = {"running": False}


def progress() -> Dict[str, Any]:
    with _LOCK:
        return dict(_PROGRESS)


def _set_progress(**fields: Any) -> None:
    with _LOCK:
        _PROGRESS.update(fields)


def mark_scan_queued(trigger: str) -> None:
    """Flag a scan as running before its thread starts, so the request that kicked
    it off can honestly report that something is happening."""
    _set_progress(running=True, stage="starting", done=0, total=0,
                  started_at=_now(), trigger=trigger, note=None)


def resolve_universe(name: Optional[str]) -> Dict[str, Any]:
    """Symbols for a named universe, with a note on where they came from."""
    key = (name or DEFAULT_UNIVERSE).lower()
    if key == "watchlist":
        return {"symbols": list(DEFAULT_WATCHLIST), "count": len(DEFAULT_WATCHLIST),
                "name": "watchlist", "source": universe.UNIVERSES["watchlist"]}
    resolved = universe.nasdaq_symbols()
    return {**resolved, "name": "nasdaq"}


def run_scan(snapshot_fn: Callable[[str], Dict[str, Any]], provider,
             watchlist: Optional[List[str]] = None, trigger: str = "manual",
             rate: float = 0.0, universe_name: Optional[str] = None,
             shortlist_size: int = SHORTLIST_SIZE,
             allow_entries: Optional[bool] = None) -> Dict[str, Any]:
    """Mark open positions, screen the universe, then analyse the shortlist.

    Three stages, because the analysis that produces a verdict costs about four
    seconds a symbol and the universe is the whole exchange. An explicit ticker
    list skips the screen entirely — that's the manual "look at these" path.
    """
    init_db()
    started = _now()
    _set_progress(running=True, stage="marking open positions", done=0, total=0,
                  started_at=started, trigger=trigger, note=None)
    try:
        marks = mark_open_positions(provider, rate)
        held = {r["ticker"] for r in _rows("SELECT ticker FROM positions WHERE status='open'")}
        equity = summary()["equity"]

        # Marking a closed market is harmless — it just re-reads the last close.
        # Opening a position is not: the fill would be a stale price nobody could
        # have traded, with a stop and target measured from it.
        if allow_entries is None:
            allow_entries = market_open_et()
        if not allow_entries:
            note = ("Market is closed. Positions were re-marked at the last close, but no new "
                    "entries were taken. A fill at a stale price isn't a trade anyone could "
                    "have got.")
            with _LOCK, _connect() as conn:
                conn.execute(
                    "INSERT INTO scans (ran_at, trigger, considered, opened, closed, notes,"
                    " funnel) VALUES (?,?,?,?,?,?,?)",
                    (started, trigger, 0, 0, marks["closed"], json.dumps([note]),
                     json.dumps({"market_open": False, "skipped": True})),
                )
            return {"considered": 0, "opened": 0, "closed": marks["closed"],
                    "marked": marks["marked"], "notes": [note],
                    "funnel": {"market_open": False, "skipped": True}}

        screened: Optional[Dict[str, Any]] = None
        if watchlist:
            candidates_in = [t for t in watchlist if t not in held]
            universe_info = {"name": "explicit list", "count": len(watchlist),
                             "source": "symbols supplied with the request"}
        else:
            universe_info = resolve_universe(universe_name)
            _set_progress(stage="screening {} symbols".format(universe_info["count"]),
                          total=universe_info["count"])
            screened = screen.run(
                provider, universe_info["symbols"], top_n=shortlist_size, exclude=held,
                progress=lambda done, total: _set_progress(done=done, total=total),
            )
            candidates_in = [m["symbol"] for m in screened["shortlist"]]

        # Let the feed recover before the expensive stage. The screen just pulled
        # a year of bars for ~3,000 symbols, which reliably earns a rate limit;
        # walking straight into the options chains means the throttle lands on the
        # part of the scan that can't tolerate it, and most of the shortlist gets
        # skipped. Waiting here costs a minute and saves the whole stage.
        if screened is not None and _feed_throttled():
            _cool_off("letting the data feed recover after the screen")

        _set_progress(stage="analysing shortlist", done=0, total=len(candidates_in))

        opened, considered, notes = 0, 0, []
        # `opened` is also the loop's stop condition against MAX_NEW_PER_SCAN, and
        # it counts the default book only. Widening it to all three would cut every
        # scan short by roughly a factor of three, so the tally for REPORTING is
        # kept separately — the scans table was recording four when sixteen
        # positions had been opened, understating the ledger's activity by exactly
        # the factor the three-book split introduced.
        opened_by_book: Dict[str, int] = {}
        opened_positions: List[Dict[str, Any]] = []
        capped = None
        throttled_skips = 0
        for index, ticker in enumerate(candidates_in):
            cap = _capacity(equity)
            if cap["position_slots_left"] <= 0:
                capped = "book full at {} open positions".format(MAX_OPEN_POSITIONS)
                break
            if cap["risk_budget_left"] <= 0:
                capped = "portfolio risk budget of {:.0f}% is used up".format(
                    MAX_PORTFOLIO_RISK * 100)
                break
            if opened >= MAX_NEW_PER_SCAN:
                capped = "hit the {}-position limit for a single scan".format(MAX_NEW_PER_SCAN)
                break

            considered += 1
            _set_progress(done=index + 1, note=ticker)
            try:
                snapshot = snapshot_fn(ticker)
            except Exception as exc:
                notes.append("{}: snapshot failed ({})".format(ticker, exc))
                continue

            # Refuse to trade on a throttled feed. This matters more than it
            # looks: a rate-limited options fetch comes back as an empty chain,
            # so the entry plan reports "no options chain available" and the
            # ledger would open a shares-only position — silently converting an
            # option recommendation into a different trade, and recording that as
            # what the terminal advised. Better to skip the name entirely.
            if not (snapshot.get("expiries") or {}).get("available") and _feed_throttled():
                # One retry after the limit clears. Skipping outright meant most of
                # a shortlist could be lost to a throttle the screen itself caused.
                _cool_off("waiting out a rate limit before retrying " + ticker)
                try:
                    snapshot = snapshot_fn(ticker)
                except Exception as exc:
                    notes.append("{}: snapshot failed on retry ({})".format(ticker, exc))
                    continue
            if not (snapshot.get("expiries") or {}).get("available") and _feed_throttled():
                notes.append("{}: skipped. The data feed is still rate-limiting, so the "
                             "options chain came back empty and any trade here would "
                             "misrepresent what the terminal actually recommended".format(ticker))
                throttled_skips += 1
                # Give up rather than grinding through the rest. Once the feed is
                # this unhappy, each remaining name costs a cool-off and still
                # comes back unusable — a scan that takes forty minutes to skip
                # everything is worse than a short one that says why it stopped.
                if throttled_skips >= MAX_THROTTLED_SKIPS:
                    capped = ("the data feed rate-limited {} names in a row, so the scan "
                              "stopped rather than trade on partial data".format(throttled_skips))
                    break
                continue

            # Every book sees the same candidate. That is the design: identical
            # opportunities under different rules, so comparing the three says
            # what a risk tolerance costs rather than comparing three signals.
            for book_id in BOOK_IDS:
                cfg = book_config(book_id)
                book_equity = equity_for(book_id)
                found, why = consider_ticker(snapshot, book_equity, book_id)
                if book_id == DEFAULT_BOOK:
                    notes.extend(why)
                for candidate in found:
                    room = _capacity(book_equity, book_id)["risk_budget_left"] or 0.0
                    cost = candidate.get("risk_dollars") or 0.0
                    slots = _capacity(book_equity, book_id)["position_slots_left"]
                    if slots <= 0 or cost > room:
                        continue
                    open_position(candidate)
                    opened_by_book[book_id] = opened_by_book.get(book_id, 0) + 1
                    # Kept, not just counted. The alert layer needs to say WHICH
                    # position opened and on what terms; a count cannot.
                    opened_positions.append(dict(candidate))
                    if book_id == DEFAULT_BOOK:
                        opened += 1
                        notes.append("Opened {} {} on {}".format(
                            candidate["instrument"], candidate["direction"], ticker))
                    else:
                        notes.append("[{}] opened {} {} on {}".format(
                            cfg["label"].lower(), candidate["instrument"],
                            candidate["direction"], ticker))

        if capped:
            notes.append("Stopped early: {}. Remaining shortlist untouched.".format(capped))
        if throttled_skips:
            notes.append("{} name(s) skipped because the data feed was rate-limiting. Nothing "
                         "was traded on incomplete data.".format(throttled_skips))

        funnel = {
            "universe": universe_info.get("name"),
            "universe_size": universe_info.get("count"),
            "universe_source": universe_info.get("source"),
            "screen": {k: v for k, v in (screened or {}).items() if k != "shortlist"},
            "shortlist": [
                {"symbol": m["symbol"], "score": m["score"], "price": m["price"],
                 "dollar_volume": m["dollar_volume"], "roc20": m["roc20"],
                 "analysed": m["symbol"] in candidates_in[:considered]}
                for m in (screened or {}).get("shortlist", [])
            ],
            "capped": capped,
            "throttled_skips": throttled_skips,
            "feed": _feed_state(),
        }

        with _LOCK, _connect() as conn:
            conn.execute(
                "INSERT INTO scans (ran_at, trigger, considered, opened, closed, notes, funnel)"
                " VALUES (?,?,?,?,?,?,?)",
                (started, trigger, considered, sum(opened_by_book.values()),
                 marks["closed"],
                 json.dumps(notes[:60]), json.dumps(funnel)),
            )
        return {"considered": considered,
                "opened": sum(opened_by_book.values()),
                "opened_by_book": opened_by_book,
                "opened_positions": opened_positions,
                "closed_positions": marks.get("closed_positions") or [],
                "closed": marks["closed"],
                "ran_at": started,
                "marked": marks["marked"], "notes": notes, "funnel": funnel}
    finally:
        _set_progress(running=False, stage=None, note=None,
                      finished_at=_now())


# -------------------------------------------------------------------- summary


def seconds_since_last_scan() -> Optional[float]:
    """Age of the most recent scan, so a restart doesn't restart the schedule."""
    init_db()
    rows = _rows("SELECT ran_at FROM scans ORDER BY ran_at DESC LIMIT 1")
    if not rows:
        return None
    try:
        then = datetime.fromisoformat(rows[0]["ran_at"])
    except (TypeError, ValueError):
        return None
    return max((datetime.now(timezone.utc) - then).total_seconds(), 0.0)


def summary(book: Optional[str] = None) -> Dict[str, Any]:
    init_db()
    # Filtered only if a start floor is configured, so the headline figures always
    # reconcile with the months shown in the table.
    closed = _rows(
        "SELECT * FROM positions WHERE status='closed' AND book=? ORDER BY exit_at DESC",
        (book,)) if book else _rows(
        "SELECT * FROM positions WHERE status='closed' ORDER BY exit_at DESC")
    if LEDGER_START:
        closed = [r for r in closed
                  if (_month_key(r.get("exit_at")) or LEDGER_START) >= LEDGER_START]
    open_rows = _rows(
        "SELECT * FROM positions WHERE status='open' AND book=? ORDER BY entry_at DESC",
        (book,)) if book else _rows(
        "SELECT * FROM positions WHERE status='open' ORDER BY entry_at DESC")

    realised = sum(r["pnl"] or 0.0 for r in closed)
    unrealised = sum(r["pnl"] or 0.0 for r in open_rows)
    wins = [r for r in closed if (r["pnl"] or 0) > 0]
    losses = [r for r in closed if (r["pnl"] or 0) < 0]

    avg_win = float(np.mean([r["pnl"] for r in wins])) if wins else None
    avg_loss = float(np.mean([r["pnl"] for r in losses])) if losses else None

    return {
        "start_equity": _f(START_EQUITY, 2),
        # Equity counts realised P&L only. Marking open positions into equity
        # would make position sizing drift with unrealised swings.
        "equity": _f(START_EQUITY + realised, 2),
        "book": book or "all",
        "realised_pnl": _f(realised, 2),
        "unrealised_pnl": _f(unrealised, 2),
        "total_pnl": _f(realised + unrealised, 2),
        "return_pct": _f((realised + unrealised) / START_EQUITY * 100.0, 2),
        "open_count": len(open_rows),
        "closed_count": len(closed),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate_pct": _f(len(wins) / len(closed) * 100.0, 1) if closed else None,
        "avg_win": _f(avg_win, 2),
        "avg_loss": _f(avg_loss, 2),
        # Expectancy per trade is the number that actually matters: a 40% win
        # rate is fine if winners are three times the size of losers.
        "expectancy": _f(float(np.mean([r["pnl"] for r in closed])), 2) if closed else None,
        "profit_factor": _f(
            sum(r["pnl"] for r in wins) / abs(sum(r["pnl"] for r in losses)), 2
        ) if wins and losses and sum(r["pnl"] for r in losses) else None,
    }


# ------------------------------------------------------------------- monthly
#
# A single all-time number can't answer the question people actually have of a
# track record: is it consistent, or was it one good fortnight? Splitting by month
# also lines the record up against the market it was trading in — a flat month in
# a falling tape means something different from a flat month in a rally.
#
# Realised P&L is attributed to the month a trade *closed*, which is the month the
# money was actually made or lost. A position opened in August and closed in
# October belongs to October's result and appears in August's "opened" count.

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]

# Optional floor on the published record. Unset by default: the ledger shows every
# month it actually has, because deciding on the reader's behalf which of their own
# history counts is not this module's call. Set TRACKER_LEDGER_START to "YYYY-MM"
# to hide months before a chosen start.
LEDGER_START = os.environ.get("TRACKER_LEDGER_START", "")


def _month_key(iso: Optional[str]) -> Optional[str]:
    """'2026-08' in Eastern Time — the market's own calendar, so a trade closed at
    5pm ET on the 31st doesn't land in the next month for a UTC reader."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).astimezone(_ET).strftime("%Y-%m")
    except (TypeError, ValueError):
        return None


def _month_label(key: str) -> str:
    try:
        year, month = key.split("-")
        return "{} {}".format(MONTH_NAMES[int(month) - 1], year)
    except (ValueError, IndexError):
        return key


def _month_span() -> List[str]:
    """Every month from the ledger's first activity to now, gaps included.

    An empty month is a real observation — "took nothing in September" is part of
    a consistency record — so the range is filled rather than derived only from
    months that happen to contain trades.
    """
    rows = _rows("SELECT MIN(entry_at) AS first FROM positions")
    first = (rows[0]["first"] if rows else None) or _now()
    start = _month_key(first) or _month_key(_now())
    if LEDGER_START:
        start = max(start, LEDGER_START)
    now_key = _month_key(_now())
    if start > now_key:                # floor set in the future
        start = now_key
    keys: List[str] = []
    year, month = int(start[:4]), int(start[5:7])
    while True:
        key = "{:04d}-{:02d}".format(year, month)
        keys.append(key)
        if key >= now_key:
            break
        month += 1
        if month > 12:
            month, year = 1, year + 1
        if len(keys) > 600:            # guard against a corrupt timestamp
            break
    return keys


def _stats(closed: List[Dict[str, Any]], base_equity: float) -> Dict[str, Any]:
    """The same measures as the all-time summary, over an arbitrary slice."""
    realised = sum(r["pnl"] or 0.0 for r in closed)
    wins = [r for r in closed if (r["pnl"] or 0) > 0]
    losses = [r for r in closed if (r["pnl"] or 0) < 0]
    gross_loss = abs(sum(r["pnl"] for r in losses)) if losses else 0.0
    return {
        "closed_count": len(closed),
        "win_count": len(wins),
        "loss_count": len(losses),
        "realised_pnl": _f(realised, 2),
        "win_rate_pct": _f(len(wins) / len(closed) * 100.0, 1) if closed else None,
        "expectancy": _f(realised / len(closed), 2) if closed else None,
        "avg_win": _f(float(np.mean([r["pnl"] for r in wins])), 2) if wins else None,
        "avg_loss": _f(float(np.mean([r["pnl"] for r in losses])), 2) if losses else None,
        "profit_factor": _f(sum(r["pnl"] for r in wins) / gross_loss, 2)
        if wins and gross_loss else None,
        # Return measured against equity at the start of the slice, so a month's
        # percentage isn't distorted by everything earned before it.
        "start_equity": _f(base_equity, 2),
        "end_equity": _f(base_equity + realised, 2),
        "return_pct": _f(realised / base_equity * 100.0, 2) if base_equity else None,
    }


def monthly_breakdown() -> List[Dict[str, Any]]:
    """Per-month results, oldest first, with running equity carried across."""
    closed = _rows("SELECT * FROM positions WHERE status='closed'")
    opened = _rows("SELECT entry_at FROM positions")

    by_close: Dict[str, List[Dict[str, Any]]] = {}
    for row in closed:
        key = _month_key(row.get("exit_at"))
        if key:
            by_close.setdefault(key, []).append(row)

    opened_counts: Dict[str, int] = {}
    for row in opened:
        key = _month_key(row.get("entry_at"))
        if key:
            opened_counts[key] = opened_counts.get(key, 0) + 1

    out: List[Dict[str, Any]] = []
    equity = START_EQUITY
    for key in _month_span():
        rows = by_close.get(key, [])
        stats = _stats(rows, equity)
        equity = (stats["end_equity"] if stats["end_equity"] is not None else equity)
        out.append({
            "key": key,
            "label": _month_label(key),
            "opened_count": opened_counts.get(key, 0),
            **stats,
        })
    return out


def month_detail(key: str) -> Dict[str, Any]:
    """Trades that closed in a month, and positions opened in it."""
    closed = [r for r in _rows("SELECT * FROM positions WHERE status='closed' ORDER BY exit_at DESC")
              if _month_key(r.get("exit_at")) == key]
    opened = [r for r in _rows("SELECT * FROM positions ORDER BY entry_at DESC")
              if _month_key(r.get("entry_at")) == key]
    still_open = [r for r in opened if r["status"] == "open"]
    return {
        "key": key,
        "label": _month_label(key),
        "closed": closed,
        "opened": opened,
        "still_open": still_open,
        "is_current": key == _month_key(_now()),
    }


def state(limit: int = 60, month: Optional[str] = None,
          book: Optional[str] = None) -> Dict[str, Any]:
    init_db()
    scans = _rows("SELECT * FROM scans ORDER BY ran_at DESC LIMIT 12")
    for scan in scans:
        try:
            scan["notes"] = json.loads(scan["notes"] or "[]")
        except (TypeError, ValueError):
            scan["notes"] = []
        try:
            scan["funnel"] = json.loads(scan["funnel"] or "null")
        except (TypeError, ValueError):
            scan["funnel"] = None
    months = monthly_breakdown()
    keys = [m["key"] for m in months]
    # Default to the current month, which is what someone opening the tab wants.
    selected = month if month in keys else (keys[-1] if keys else None)

    return {
        "summary": summary(book),
        "months": months,
        "selected_month": selected,
        "month": month_detail(selected) if selected else None,
        "progress": progress(),
        "feed": _feed_state(),
        "market_open": market_open_et(),
        "capacity": _capacity(equity_for(book), book),
        "book": book or DEFAULT_BOOK,
        # Every book, with its own equity and record, so the tab can offer a
        # selector and a comparison without three round trips.
        "books": [
            {**book_config(b),
             "equity": _f(equity_for(b), 2),
             "summary": summary(b),
             "capacity": _capacity(equity_for(b), b)}
            for b in BOOK_IDS
        ],
        "open": _rows(
            "SELECT * FROM positions WHERE status='open' AND book=? ORDER BY entry_at DESC",
            (book or DEFAULT_BOOK,)),
        "closed": _rows(
            "SELECT * FROM positions WHERE status='closed' AND book=? "
            "ORDER BY exit_at DESC LIMIT ?",
            (book or DEFAULT_BOOK, limit),
        ),
        "scans": scans,
        "config": {
            "universe": DEFAULT_UNIVERSE,
            "universe_note": universe.UNIVERSES.get(DEFAULT_UNIVERSE, ""),
            "shortlist_size": SHORTLIST_SIZE,
            "screen_gates": {
                "min_price": screen.MIN_PRICE,
                "min_dollar_volume": screen.MIN_DOLLAR_VOLUME,
                "max_atr_pct": screen.MAX_ATR_PCT,
                "max_abs_1m_move_pct": screen.MAX_ABS_ROC20,
            },
            "max_open_positions": MAX_OPEN_POSITIONS,
            "max_portfolio_risk_pct": _f(MAX_PORTFOLIO_RISK * 100, 1),
            "max_new_per_scan": MAX_NEW_PER_SCAN,
            "watchlist": DEFAULT_WATCHLIST,
            "risk_per_trade_pct": _f(RISK_PER_TRADE * 100, 2),
            "min_composite": MIN_COMPOSITE,
            "max_hold_days": MAX_HOLD_DAYS,
            "max_option_risk_pct": _f(MAX_OPTION_RISK * 100, 1),
            "option_single_contract_cap_pct": _f(OPTION_SINGLE_CONTRACT_CAP * 100, 1),
        },
        "disclaimer": legal.SHORT,
        "disclaimer_area": legal.SIMULATED,
        "caveats": [
            "Simulated trades. Fills assume the mid price, which is optimistic on a wide "
            "spread, and no commission or slippage is charged.",
            "One signal can open both a share and an option position on the same ticker. That "
            "is deliberate. It shows how the same idea performed in each instrument, but it "
            "means the two lines are the same bet, not two independent ones.",
            "Share stops and targets are checked against the day's high and low, so a level "
            "touched intraday counts even if price closed back inside it.",
            "Options are marked from the live chain where a quote exists; when one doesn't, "
            "the mark is a Black-Scholes estimate and is labelled as such on the position.",
            "Equity for sizing counts realised P&L only, so open positions don't inflate the "
            "size of the next trade.",
            "When a single recommended contract costs more than the option budget, one contract "
            "is still taken (up to {:.0f}% of equity) rather than skipping the trade. Otherwise "
            "the ledger would only ever hold cheap options and would stop matching the "
            "recommendations it actually made. But it does mean a few positions carry more risk "
            "than the stated budget. The scan notes say which ones.".format(
                OPTION_SINGLE_CONTRACT_CAP * 100),
            "The screen that picks which names get analysed uses price and volume only. No "
            "options positioning, no news, no fundamentals. It decides what gets a closer look, "
            "not whether a trade is good. Anything it ranks first can still be rejected by the "
            "full analysis, and often is.",
            "Names trading under ${:,.0f} a day are excluded, which removes most of the "
            "exchange. Those are real listings, but a simulated fill in one wouldn't survive "
            "contact with its actual spread.".format(screen.MIN_DOLLAR_VOLUME),
            "Screening thousands of symbols on a free data feed earns a temporary rate limit, and "
            "a rate-limited options request comes back looking identical to a stock with no "
            "options at all. Rather than open a shares-only position and record it as what was "
            "recommended, Optic waits for the limit to clear and then skips the name if it "
            "hasn't. A throttled scan therefore takes fewer positions, not wrong ones.",
        ],
    }
