"""Currency pairs and their explanations.

The numbers here come from the shared snapshot helper, which is tested
elsewhere. What is worth testing is the part that is specific to FX and easy to
get silently wrong: the direction language. A pair is quoted base/quote, and
saying "up means the dollar is stronger" on a pair where the dollar is the base
is the exact error that makes an FX screen misleading rather than merely wrong.
"""

import pytest

from app.analytics import forex


def test_every_pair_declares_what_up_means():
    for p in forex.PAIRS:
        assert p["up_means"], p["label"]
        assert "," in p["up_means"] or "basket" in p["up_means"], (
            "%s: up_means should name both sides" % p["label"])


def test_direction_language_matches_the_quote_convention():
    """The check that matters.

    On USD/JPY the dollar is the BASE, so a rise is dollar strength. On EUR/USD
    the dollar is the QUOTE, so a rise is dollar weakness. Getting either
    backwards inverts the reading of the whole panel.
    """
    for p in forex.PAIRS:
        if p["group"] == "Index":
            continue
        says = p["up_means"].lower()
        base_is_usd = p["base"] == "US dollar"
        if base_is_usd:
            assert "dollar stronger" in says, (
                "%s quotes USD as the base, so up is dollar STRENGTH" % p["label"])
        elif p["quote"] == "US dollar":
            assert "dollar weaker" in says, (
                "%s quotes USD as the quote, so up is dollar WEAKNESS" % p["label"])


def test_every_pair_has_a_known_driver():
    for p in forex.PAIRS:
        assert p["driver"] in forex.DRIVERS, "%s: %s" % (p["label"], p["driver"])


def test_every_pair_explains_itself():
    """A quote with no explanation is the thing this module exists to replace."""
    for p in forex.PAIRS:
        for field in ("what", "moves_on", "equities"):
            assert p.get(field), "%s missing %s" % (p["label"], field)
            assert len(p[field]) > 40, "%s: %s is too thin to be useful" % (
                p["label"], field)


def test_pairs_with_no_equity_read_across_say_so():
    """Rather than inventing one. Two pairs are here to isolate a currency, not
    because they tell you anything about the S&P."""
    hedged = [p for p in forex.PAIRS
              if "little direct" in p["equities"].lower()
              or "no useful read" in p["equities"].lower()]
    assert hedged, "no pair admits to having no equity read across"


def test_symbols_are_unique():
    syms = [p["symbol"] for p in forex.PAIRS]
    assert len(syms) == len(set(syms))


# ------------------------------------------------------------------ search

class _Provider:
    def batch_history(self, tickers, period="1y", interval="1d"):
        return {}


def test_search_matches_a_currency_name():
    out = forex.build(_Provider(), "yen")
    labels = [p["label"] for p in out["pairs"]]
    assert "USD/JPY" in labels
    assert all("JPY" in l or "yen" in p["base"].lower() or "yen" in p["quote"].lower()
               for l, p in zip(labels, out["pairs"]))


def test_search_matches_a_driver():
    out = forex.build(_Provider(), "carry")
    assert out["pairs"]
    for p in out["pairs"]:
        assert p["driver"] == "carry"


def test_search_matches_a_group():
    out = forex.build(_Provider(), "commodity")
    assert out["pairs"]
    for p in out["pairs"]:
        assert p["group"] == "Commodity" or p["driver"] == "terms of trade"


def test_no_match_explains_itself_rather_than_returning_empty():
    out = forex.build(_Provider(), "zzzznotacurrency")
    assert out["pairs"] == []
    assert out.get("reason")


def test_an_empty_query_returns_everything():
    out = forex.build(_Provider(), "")
    assert len(out["pairs"]) == len(forex.PAIRS)
    assert out["count"] == out["total"]


def test_the_reading_is_direction_aware():
    """The generated sentence has to use the pair's own language, not a generic
    'up' — that is the whole point of carrying up_means per pair."""
    pair = forex.PAIR_BY_SYMBOL["USDJPY=X"]
    assert "dollar stronger" in forex._reading(pair, {"chg_20d": 3.2})
    assert "yen weaker" in forex._reading(pair, {"chg_20d": -3.2})
    eur = forex.PAIR_BY_SYMBOL["EURUSD=X"]
    assert "euro stronger" in forex._reading(eur, {"chg_20d": 4.0})
    assert "dollar weaker" in forex._reading(eur, {"chg_20d": -4.0})


def test_a_flat_month_is_reported_as_flat_not_as_a_direction():
    pair = forex.PAIR_BY_SYMBOL["EURUSD=X"]
    assert "flat" in forex._reading(pair, {"chg_20d": 0.3}).lower()


def test_missing_history_does_not_invent_a_reading():
    pair = forex.PAIR_BY_SYMBOL["EURUSD=X"]
    assert "No recent history" in forex._reading(pair, {})
