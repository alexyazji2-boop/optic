"""Currency pairs, and what each one is actually telling you.

A quote screen full of pairs is close to useless on its own: EUR/USD at 1.1583
means nothing without knowing that a *rising* EUR/USD is a weaker dollar, that
the pair is mostly a rates-differential trade, and that it is the single largest
weight in the dollar index. So every pair here carries three things a number
cannot:

* **What it is** — the two economies, and which way round the quote is written.
* **What moves it** — rate differentials, terms of trade, carry, or risk appetite.
  These are genuinely different mechanisms and they respond to different news.
* **What a move means for equities**, where there is a defensible link. Several
  pairs have none, and those say so rather than inventing one.

**On direction.** Every pair is quoted base/quote, so the price is "how many
units of the quote currency buys one unit of the base". Rising EUR/USD is euro
strength *and* dollar weakness; rising USD/JPY is dollar strength and yen
weakness. Getting this backwards is the most common way to misread an FX screen,
so `up_means` spells it out per pair instead of leaving it to be inferred.

**What this does not do.** It does not forecast. The commentary describes the
mechanism and the current reading; nothing here says which way a pair goes next.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .series_stats import _f, snapshot

BENCHMARK = "DX-Y.NYB"

# Grouped the way a macro desk thinks about them, not alphabetically.
#
# `driver` is the mechanism, and it is the field that earns this module: two
# pairs can move the same percentage for completely unrelated reasons, and the
# reason is what decides whether it matters to anything else on the screen.
PAIRS: List[Dict[str, Any]] = [
    # ---- the majors -----------------------------------------------------
    {
        "symbol": "EURUSD=X", "label": "EUR/USD", "group": "Majors",
        "base": "Euro", "quote": "US dollar",
        "up_means": "euro stronger, dollar weaker",
        "driver": "rate differential",
        "what": "The most traded pair in the world and the largest weight in the "
                "dollar index at roughly 58%, so the dollar index and this pair "
                "are close to the same trade with the sign flipped.",
        "moves_on": "The gap between what the Fed and the ECB are expected to do. "
                    "Widening US yields relative to Bund yields pulls capital "
                    "into dollars and the pair down.",
        "equities": "A falling pair is a rising dollar, which mechanically trims "
                    "the reported earnings of US multinationals — roughly 40% of "
                    "S&P 500 revenue is earned abroad — and tightens conditions "
                    "for anyone funding in dollars offshore.",
    },
    {
        "symbol": "USDJPY=X", "label": "USD/JPY", "group": "Majors",
        "base": "US dollar", "quote": "Japanese yen",
        "up_means": "dollar stronger, yen weaker",
        "driver": "carry",
        "what": "The market's main carry trade: borrow in yen at near-zero, hold "
                "something yielding more. That makes the pair a leverage gauge as "
                "much as a currency.",
        "moves_on": "US 10-year yields, and any hint the Bank of Japan will let "
                    "its own yields rise. Also Ministry of Finance intervention, "
                    "which is announced by the move rather than beforehand.",
        "equities": "The important asymmetry: a grinding rise is benign, but a "
                    "sharp FALL unwinds the carry trade, and carry unwinds force "
                    "selling of whatever the borrowed yen was funding. August "
                    "2024 is the reference — a yen rally and a global equity "
                    "drawdown in the same week.",
    },
    {
        "symbol": "GBPUSD=X", "label": "GBP/USD", "group": "Majors",
        "base": "British pound", "quote": "US dollar",
        "up_means": "pound stronger, dollar weaker",
        "driver": "rate differential",
        "what": "Sterling against the dollar, historically called cable after the "
                "transatlantic telegraph the rate was quoted over.",
        "moves_on": "UK inflation prints and Bank of England expectations against "
                    "the Fed. Sterling also carries a fiscal-credibility premium "
                    "that most majors do not — gilt yields and the pound can move "
                    "the same way, which for a developed market is a warning.",
        "equities": "Little direct read across to US equities. Matters for UK "
                    "large caps, where a weaker pound flatters the FTSE 100 "
                    "because most of its revenue is earned in other currencies.",
    },
    {
        "symbol": "USDCHF=X", "label": "USD/CHF", "group": "Majors",
        "base": "US dollar", "quote": "Swiss franc",
        "up_means": "dollar stronger, franc weaker",
        "driver": "risk appetite",
        "what": "The franc is the developed world's other haven, alongside the "
                "yen and the dollar itself.",
        "moves_on": "Risk aversion, which bids the franc and pushes this pair "
                    "down, and Swiss National Bank discomfort with a strong franc.",
        "equities": "A falling pair — franc strength — often accompanies a "
                    "risk-off equity tape. It reads as confirmation rather than "
                    "as a cause.",
    },
    # ---- commodity currencies -------------------------------------------
    {
        "symbol": "AUDUSD=X", "label": "AUD/USD", "group": "Commodity",
        "base": "Australian dollar", "quote": "US dollar",
        "up_means": "Aussie stronger, dollar weaker",
        "driver": "terms of trade",
        "what": "The cleanest liquid proxy for Chinese industrial demand: "
                "Australia sells iron ore and coal, and China is the buyer.",
        "moves_on": "Iron ore, Chinese credit and property data, and the Reserve "
                    "Bank of Australia. It is also a classic risk barometer, so it "
                    "falls in a global risk-off regardless of the commodity.",
        "equities": "Rising alongside copper is a genuine growth signal. Rising "
                    "while copper falls is usually just dollar weakness wearing a "
                    "growth costume — which is exactly the case worth catching.",
    },
    {
        "symbol": "USDCAD=X", "label": "USD/CAD", "group": "Commodity",
        "base": "US dollar", "quote": "Canadian dollar",
        "up_means": "dollar stronger, loonie weaker",
        "driver": "terms of trade",
        "what": "Two closely integrated economies, so the pair is quieter than "
                "most and mostly expresses oil and the rate gap.",
        "moves_on": "WTI crude — Canada is a net exporter, so higher oil pushes "
                    "this pair DOWN — plus the Bank of Canada against the Fed, and "
                    "tariff news, which for Canada is idiosyncratic risk.",
        "equities": "Thin read across on its own. Useful as a cross-check on an "
                    "oil move: crude up with this pair not falling suggests the "
                    "oil move is supply-driven rather than demand-driven.",
    },
    {
        "symbol": "NZDUSD=X", "label": "NZD/USD", "group": "Commodity",
        "base": "New Zealand dollar", "quote": "US dollar",
        "up_means": "kiwi stronger, dollar weaker",
        "driver": "terms of trade",
        "what": "Smaller and less liquid than the Aussie, and it mostly follows "
                "it. Dairy rather than metals.",
        "moves_on": "Chinese demand, dairy auctions, and the RBNZ. Its lower "
                    "liquidity means it overshoots in a risk-off.",
        "equities": "Read the Aussie instead unless AUD/NZD is the point. The two "
                    "diverging is a story about New Zealand, not about the world.",
    },
    # ---- crosses --------------------------------------------------------
    {
        "symbol": "EURJPY=X", "label": "EUR/JPY", "group": "Crosses",
        "base": "Euro", "quote": "Japanese yen",
        "up_means": "euro stronger, yen weaker",
        "driver": "risk appetite",
        "what": "A cross with no dollar in it, which is what makes it useful: it "
                "strips out the dollar and leaves the risk signal.",
        "moves_on": "Global risk appetite. The euro is funded and the yen is a "
                    "haven, so the pair rises when money is being put to work.",
        "equities": "One of the better FX confirmations of an equity move, "
                    "precisely because the dollar is not in it. Equities up with "
                    "this pair down is a divergence worth taking seriously.",
    },
    {
        "symbol": "GBPJPY=X", "label": "GBP/JPY", "group": "Crosses",
        "base": "British pound", "quote": "Japanese yen",
        "up_means": "pound stronger, yen weaker",
        "driver": "risk appetite",
        "what": "The same risk trade as EUR/JPY with more leverage in it — wide "
                "ranges, and a long-standing nickname among traders for the size "
                "of its moves.",
        "moves_on": "Risk appetite, amplified. It exaggerates whatever EUR/JPY is "
                    "doing.",
        "equities": "A volatility gauge more than an indicator. Sharp falls here "
                    "tend to lead carry unwinds elsewhere.",
    },
    {
        "symbol": "EURGBP=X", "label": "EUR/GBP", "group": "Crosses",
        "base": "Euro", "quote": "British pound",
        "up_means": "euro stronger, pound weaker",
        "driver": "rate differential",
        "what": "Two neighbouring economies. A tight range most of the time, "
                "which is what makes a breakout meaningful.",
        "moves_on": "The ECB against the Bank of England, and UK-specific fiscal "
                    "or political news.",
        "equities": "No useful read across to US equities. Included because it "
                    "isolates sterling from the dollar.",
    },
    {
        "symbol": "AUDJPY=X", "label": "AUD/JPY", "group": "Crosses",
        "base": "Australian dollar", "quote": "Japanese yen",
        "up_means": "Aussie stronger, yen weaker",
        "driver": "risk appetite",
        "what": "High-yielder against the funding currency — the textbook carry "
                "pair, and historically one of the tightest FX correlations to "
                "global equities.",
        "moves_on": "Risk appetite and the rate gap together. Both legs push the "
                    "same way in a risk-off, which is why it moves so far.",
        "equities": "The FX pair that tracks equity beta most closely. Treat a "
                    "sustained divergence between this and the S&P as a question "
                    "about the equity move, not about the pair.",
    },
    # ---- emerging / other ------------------------------------------------
    {
        "symbol": "USDCNY=X", "label": "USD/CNY", "group": "Emerging",
        "base": "US dollar", "quote": "Chinese yuan",
        "up_means": "dollar stronger, yuan weaker",
        "driver": "policy",
        "what": "Managed, not floating. The People's Bank of China sets a daily "
                "fix and the rate trades in a band around it, so this is a policy "
                "signal rather than a market price.",
        "moves_on": "The PBoC's own decisions. A deliberate weakening is usually "
                    "a growth-support measure and is read as such.",
        "equities": "A sharp managed devaluation has twice been a global risk "
                    "event (2015 and 2016). Otherwise the level matters less than "
                    "the fact of a change.",
    },
    {
        "symbol": "USDMXN=X", "label": "USD/MXN", "group": "Emerging",
        "base": "US dollar", "quote": "Mexican peso",
        "up_means": "dollar stronger, peso weaker",
        "driver": "carry",
        "what": "A high-carry emerging currency with deep enough liquidity to be "
                "used as a proxy for emerging-market risk appetite generally.",
        "moves_on": "The carry — Mexican rates are high — plus US trade policy "
                    "and nearshoring flows. Tariff news moves this first.",
        "equities": "A spike here is emerging-market risk aversion, and it "
                    "usually leads rather than follows.",
    },
    {
        "symbol": "USDINR=X", "label": "USD/INR", "group": "Emerging",
        "base": "US dollar", "quote": "Indian rupee",
        "up_means": "dollar stronger, rupee weaker",
        "driver": "policy",
        "what": "Heavily managed by the Reserve Bank of India, which smooths the "
                "rate. The result is a long, slow drift with occasional steps.",
        "moves_on": "Oil, because India imports most of what it burns, plus RBI "
                    "intervention and foreign portfolio flows.",
        "equities": "Little direct read across. Relevant to Indian equity "
                    "exposure held in dollars, where the currency drift is a "
                    "persistent drag on returns.",
    },
    {
        "symbol": "DX-Y.NYB", "label": "Dollar index (DXY)", "group": "Index",
        "base": "US dollar", "quote": "basket",
        "up_means": "dollar stronger against a basket",
        "driver": "rate differential",
        "what": "Not a pair. A trade-weighted basket that is roughly 58% euro, "
                "14% yen and 12% sterling — which means it is mostly EUR/USD "
                "upside down, and it says almost nothing about Asia or emerging "
                "markets despite being read as 'the dollar'.",
        "moves_on": "Whatever moves EUR/USD, plus the Fed against everyone else.",
        "equities": "The single most useful FX number on an equity screen. A "
                    "rising dollar tightens global financial conditions, trims "
                    "multinational earnings and historically pressures commodities "
                    "and emerging markets together.",
    },
]

PAIR_BY_SYMBOL = {p["symbol"]: p for p in PAIRS}
DRIVERS = {
    "rate differential": "Moves on the expected gap between two central banks. "
                         "Watch rate decisions, inflation prints and the 2-year "
                         "yield spread.",
    "carry": "Moves on the incentive to borrow the low-yielding side and hold the "
             "high-yielding one. Trends quietly for months, then unwinds fast — "
             "the unwinds are what matter.",
    "terms of trade": "Moves on what the country sells. A commodity currency is "
                      "a bet on its export, so read it alongside that commodity.",
    "risk appetite": "Moves on whether money is being put to work or pulled back. "
                     "These are the pairs worth checking against an equity move.",
    "policy": "Managed rather than floating. The level is a decision, so a change "
              "is a signal about intent rather than a market price.",
}


def _reading(pair: Dict[str, Any], snap: Dict[str, Any]) -> str:
    """One sentence on the current state, in the pair's own direction language."""
    chg = snap.get("chg_20d")
    if chg is None:
        return "No recent history to read."
    strong = pair["up_means"].split(",")[0].strip()
    weak = pair["up_means"].split(",")[-1].strip()
    if abs(chg) < 1.0:
        return "Broadly flat over the last month — neither side has the upper hand."
    direction = strong if chg > 0 else weak
    return ("Up {:.1f}% over the last month, so {}.".format(chg, direction)
            if chg > 0
            else "Down {:.1f}% over the last month, so {}.".format(abs(chg), direction))


def build(provider, query: str = "") -> Dict[str, Any]:
    """Every pair, with its snapshot and its explanation.

    `query` filters on the label, either currency name, the group or the driver —
    so "yen", "carry" and "commodity" all work, which is how someone actually
    looks for a pair.
    """
    q = (query or "").strip().lower()
    wanted = PAIRS
    if q:
        def matches(p: Dict[str, Any]) -> bool:
            hay = " ".join([p["label"], p["base"], p["quote"], p["group"],
                            p["driver"], p["symbol"]]).lower()
            return q in hay
        wanted = [p for p in PAIRS if matches(p)]

    if not wanted:
        return {"query": query, "pairs": [], "groups": [], "drivers": DRIVERS,
                "reason": "Nothing matched. Try a currency, a group, or a driver."}

    frames = provider.batch_history([p["symbol"] for p in wanted],
                                    period="1y", interval="1d")
    rows: List[Dict[str, Any]] = []
    for p in wanted:
        df = frames.get(p["symbol"])
        snap = snapshot(df) if df is not None and not df.empty else {}
        row = dict(p)
        row["snapshot"] = snap
        row["reading"] = _reading(p, snap)
        row["driver_note"] = DRIVERS.get(p["driver"], "")
        rows.append(row)

    groups: List[str] = []
    for r in rows:
        if r["group"] not in groups:
            groups.append(r["group"])

    return {"query": query, "pairs": rows, "groups": groups, "drivers": DRIVERS,
            "count": len(rows), "total": len(PAIRS)}
