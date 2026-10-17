"""The 1h chart on clock hours: 12:00 to 1:00, not the feed's 12:30 to 1:30.

The feed's hour bars start at the open, so every one sat half an hour off the
clock axis. The rung is built from half-hour bars instead, which start on the
clock; these pin how two halves become an hour and where they must not."""
import pandas as pd

from app import main as M

TZ = "America/New_York"


def halves(day="2026-10-15", start="09:30", end="15:30", attrs=None, nan=None):
    idx = pd.date_range(f"{day} {start}", f"{day} {end}", freq="30min", tz=TZ)
    n = len(idx)
    f = pd.DataFrame({"Open": [100.0 + i for i in range(n)],
                      "High": [101.0 + i for i in range(n)],
                      "Low": [99.0 + i for i in range(n)],
                      "Close": [100.5 + i for i in range(n)],
                      "Volume": [1000 * (i + 1) for i in range(n)]}, index=idx)
    if nan:
        f.loc[pd.Timestamp(nan[0], tz=TZ), nan[1]] = float("nan")
    f.attrs.update(attrs or {})
    return f


def hhmm(frame):
    return [s.strftime("%H:%M") for s in frame.index]


def test_a_session_reads_on_the_clock_with_the_first_half_hour_alone():
    h = M.clock_hours(halves())
    assert hhmm(h) == ["09:30", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]


def test_an_hour_is_its_two_halves_open_high_low_close_and_volume():
    f, h = halves(), M.clock_hours(halves())
    a, b = f.loc[pd.Timestamp("2026-10-15 12:00", tz=TZ)], f.loc[pd.Timestamp("2026-10-15 12:30", tz=TZ)]
    bar = h.loc[pd.Timestamp("2026-10-15 12:00", tz=TZ)]
    assert bar["Open"] == a["Open"] and bar["Close"] == b["Close"]
    assert bar["High"] == max(a["High"], b["High"]) and bar["Low"] == min(a["Low"], b["Low"])
    assert bar["Volume"] == a["Volume"] + b["Volume"]


def test_pre_market_never_joins_the_opening_bar():
    f = halves(start="04:00", end="19:30", attrs={"has_prepost": True, "regular_minutes": (570, 960)})
    h = M.clock_hours(f)
    assert "09:00" in hhmm(h) and "09:30" in hhmm(h) and "16:00" in hhmm(h)
    nine = h.loc[pd.Timestamp("2026-10-15 09:00", tz=TZ)]
    assert nine["Volume"] == f.loc[pd.Timestamp("2026-10-15 09:00", tz=TZ), "Volume"]


def test_a_missing_value_in_either_half_is_missing_from_the_hour():
    h = M.clock_hours(halves(nan=("2026-10-15 12:30", "High")))
    assert pd.isna(h.loc[pd.Timestamp("2026-10-15 12:00", tz=TZ), "High"])
    assert not pd.isna(h.loc[pd.Timestamp("2026-10-15 13:00", tz=TZ), "High"])


def test_a_round_the_clock_market_is_already_on_the_hour():
    f = halves(start="00:00", end="23:30")
    assert hhmm(M.clock_hours(f)) == ["{:02d}:00".format(i) for i in range(24)]


class Feed:
    def __init__(self):
        self.calls = []

    def intraday_history(self, symbol, period="5d", interval="1m", prepost=False):
        self.calls.append((period, interval))
        if interval == "30m":
            return pd.concat([halves("2026-10-14"), halves("2026-10-15")])
        idx = pd.date_range("2026-10-13 09:30", periods=7, freq="60min", tz=TZ).append(
            pd.date_range("2026-10-14 09:30", periods=7, freq="60min", tz=TZ))
        return pd.DataFrame({"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10}, index=idx)


def test_the_1h_rung_asks_for_half_hours_and_other_rungs_are_untouched(monkeypatch):
    feed = Feed()
    monkeypatch.setattr(M, "YF_PROVIDER", feed)
    h = M.intraday_bars("NVDA", M.intraday_spec("60", "1mo"))
    assert feed.calls == [("1mo", "30m")]
    assert "12:30" not in hhmm(h)
    feed.calls.clear()
    M.intraday_bars("NVDA", M.intraday_spec("30"))
    assert feed.calls == [("1mo", "30m")]


def test_a_window_past_sixty_days_keeps_the_feeds_hours_only_before_the_half_hours(monkeypatch):
    feed = Feed()
    monkeypatch.setattr(M, "YF_PROVIDER", feed)
    h = M.intraday_bars("NVDA", M.intraday_spec("60", "1y"))
    assert feed.calls == [("60d", "30m"), ("1y", "60m")]
    days = sorted({s.date().isoformat() for s in h.index})
    assert days == ["2026-10-13", "2026-10-14", "2026-10-15"]
    assert hhmm(h[h.index.date == pd.Timestamp("2026-10-13").date()])[1] == "10:30"
    assert hhmm(h[h.index.date == pd.Timestamp("2026-10-14").date()])[1] == "10:00"
    assert h.index.is_monotonic_increasing
