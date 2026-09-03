"""Economic series as charts, from FRED.

`app/fred.py` already fetches FRED and uses it to answer "what did that release
say" beside a calendar entry. This is the other half: the *history*, plotted, so
you can see whether a print is a break in trend or one more month of the same.

**Why FRED and not a vendor.** Every series here is CSV at a stable URL with no
API key. The data is the statistical agency's own, redistributed by the St. Louis
Fed, so it is a primary source at one remove rather than somebody's
interpretation of it.

**Levels versus changes, stated per series.** This is the one place an economic
chart routinely misleads. CPI as a level is a smooth line that always rises and
tells you nothing; CPI as a month-over-month change is the number people argue
about. The unemployment rate is the opposite — the level is the point and the
change is noise. So each series declares which form to plot rather than applying
one rule to all of them, and the label says which you are looking at.

**No forecasts.** FRED publishes what was released. Consensus estimates are
surveyed and licensed, so there is no expectations column here and there will not
be one from this source.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from ..fred import SERIES_MAP, observations

# Grouped the way a macro reader thinks, and ordered within each group by how
# often the number actually moves markets.
GROUPS: List[Dict[str, Any]] = [
    {"id": "inflation", "label": "Inflation",
     "series": ["CPIAUCSL", "PCEPILFE", "PPIFIS", "T10YIE"]},
    {"id": "labour", "label": "Labour",
     "series": ["PAYEMS", "UNRATE", "ICSA", "JTSJOL", "AHETPI"]},
    {"id": "growth", "label": "Growth and activity",
     "series": ["GDPC1", "INDPRO", "RSAFS", "UMCSENT", "HOUST"]},
    {"id": "rates", "label": "Rates and policy",
     "series": ["DFF", "DGS2", "DGS10", "T10Y2Y", "MORTGAGE30US"]},
    {"id": "credit", "label": "Credit and money",
     "series": ["BAMLH0A0HYM2", "M2SL", "WALCL", "DRTSCILM"]},
]

# What each series is, how to read it, and — the part that matters — whether to
# plot the level or the change.
SERIES: Dict[str, Dict[str, Any]] = {
    "CPIAUCSL": {"label": "CPI, all items", "form": "yoy", "unit": "%",
                 "note": "Headline inflation. Plotted year over year, which is the "
                         "figure quoted in the news; the level is a line that only "
                         "ever rises and says nothing."},
    "PCEPILFE": {"label": "Core PCE", "form": "yoy", "unit": "%",
                 "note": "The Fed's actual target measure, and not the one the "
                         "headlines lead with. Excludes food and energy."},
    "PPIFIS": {"label": "PPI, final demand", "form": "yoy", "unit": "%",
               "note": "Producer prices. Sometimes leads CPI, often does not. The "
                       "pass-through is weaker than it is usually claimed to be."},
    "T10YIE": {"label": "10-year breakeven", "form": "level", "unit": "%",
               "note": "What the bond market expects inflation to average over ten "
                       "years. A market price, not a survey, so it moves daily."},
    "PAYEMS": {"label": "Nonfarm payrolls", "form": "diff", "unit": "k",
               "note": "Change in jobs on the month. The level is meaningless here; "
                       "the monthly change is the release."},
    "UNRATE": {"label": "Unemployment rate", "form": "level", "unit": "%",
               "note": "The level is the point. Read it with the participation "
                       "rate. Unemployment can fall because people stopped looking."},
    "ICSA": {"label": "Initial jobless claims", "form": "level", "unit": "k",
             "note": "Weekly, so it is the highest-frequency labour reading there "
                     "is. Noisy week to week; the four-week trend is the signal."},
    "JTSJOL": {"label": "Job openings", "form": "level", "unit": "m",
               "note": "Vacancies. Openings per unemployed person is the ratio the "
                       "Fed has cited most often."},
    "AHETPI": {"label": "Average hourly earnings", "form": "yoy", "unit": "%",
               "note": "Wage growth. The link from wages to inflation is real but "
                       "much looser than it is usually presented."},
    "GDPC1": {"label": "Real GDP", "form": "qoq_ann", "unit": "%",
              "note": "Quarterly, annualised. Backward-looking by a quarter, so it "
                      "confirms rather than warns."},
    "INDPRO": {"label": "Industrial production", "form": "yoy", "unit": "%",
               "note": "Factory, mining and utility output. A small share of GDP "
                       "and a large share of its cyclicality."},
    "RSAFS": {"label": "Retail sales", "form": "yoy", "unit": "%",
              "note": "Nominal, so in a high-inflation period it can rise while "
                      "real volumes fall."},
    "UMCSENT": {"label": "Consumer sentiment", "form": "level", "unit": "",
                "note": "A survey. Has been a poor predictor of actual spending "
                        "for some years. People report gloom and keep buying."},
    "HOUST": {"label": "Housing starts", "form": "level", "unit": "k",
              "note": "Rate-sensitive and early. One of the few series that turns "
                      "before the cycle does."},
    "DFF": {"label": "Fed funds rate", "form": "level", "unit": "%",
            "note": "The policy rate itself, daily effective."},
    "DGS2": {"label": "2-year Treasury", "form": "level", "unit": "%",
             "note": "The market's view of policy over two years. Moves before the "
                     "Fed does."},
    "DGS10": {"label": "10-year Treasury", "form": "level", "unit": "%",
              "note": "The discount rate underneath most valuation. Equity "
                      "multiples argue with this number more than with any other."},
    "T10Y2Y": {"label": "10y minus 2y spread", "form": "level", "unit": "%",
               "note": "The classic curve. Below zero is inversion, which has "
                       "preceded recessions with long and inconsistent lags. The "
                       "signal is real, the timing is not."},
    "MORTGAGE30US": {"label": "30-year mortgage", "form": "level", "unit": "%",
                     "note": "Where policy meets the household."},
    "BAMLH0A0HYM2": {"label": "High-yield spread", "form": "level", "unit": "%",
                     "note": "What junk borrowers pay over Treasuries. The cleanest "
                             "single measure of financial stress on this list. It "
                             "widens before equities fall."},
    "M2SL": {"label": "M2 money supply", "form": "yoy", "unit": "%",
             "note": "Plotted year over year. The level rises forever; the growth "
                     "rate going negative in 2022 was the first time since the 1930s."},
    "WALCL": {"label": "Fed balance sheet", "form": "level", "unit": "$",
              "note": "Total assets. Falling is quantitative tightening."},
    "DRTSCILM": {"label": "Banks tightening standards", "form": "level", "unit": "%",
                 "note": "Net share of banks tightening lending standards, from the "
                         "senior loan officer survey. Quarterly and slow, but it is "
                         "credit supply rather than credit price."},
}

FORM_LABEL = {
    "level": "level",
    "yoy": "year over year",
    "diff": "change on the period",
    "qoq_ann": "quarterly, annualised",
}


def _f(v: Any, digits: int = 2) -> Optional[float]:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


def _transform(rows: List[Any], form: str, unit: str) -> List[Dict[str, Any]]:
    """Apply the series' declared form. See the module docstring for why this is
    per-series rather than one rule."""
    out: List[Dict[str, Any]] = []
    values = [(d, v) for d, v in rows if v is not None]
    if not values:
        return out

    if form == "level":
        for d, v in values:
            scaled = v / 1000.0 if unit == "$" else v
            out.append({"date": d, "value": _f(scaled, 2)})
        return out

    if form == "diff":
        for i in range(1, len(values)):
            out.append({"date": values[i][0],
                        "value": _f(values[i][1] - values[i - 1][1], 0)})
        return out

    if form == "yoy":
        # Step back by the series' own frequency rather than assuming monthly:
        # a weekly series compared to "12 rows ago" would be a quarter, not a year.
        step = _periods_per_year(values)
        for i in range(step, len(values)):
            base = values[i - step][1]
            if not base:
                continue
            out.append({"date": values[i][0],
                        "value": _f((values[i][1] / base - 1) * 100, 2)})
        return out

    if form == "qoq_ann":
        for i in range(1, len(values)):
            base = values[i - 1][1]
            if not base:
                continue
            out.append({"date": values[i][0],
                        "value": _f(((values[i][1] / base) ** 4 - 1) * 100, 2)})
        return out

    return out


def _periods_per_year(values: List[Any]) -> int:
    """Infer the frequency from the dates, so a year-over-year change really is
    a year for weekly, monthly and quarterly series alike."""
    if len(values) < 3:
        return 12
    from datetime import date as _date
    try:
        d1 = _date.fromisoformat(values[-1][0])
        d0 = _date.fromisoformat(values[-2][0])
    except (ValueError, TypeError):
        return 12
    gap = abs((d1 - d0).days)
    if gap <= 3:
        return 252
    if gap <= 10:
        return 52
    if gap <= 45:
        return 12
    return 4


def series(code: str, years: int = 12) -> Dict[str, Any]:
    """One series, transformed and ready to plot."""
    spec = SERIES.get(code)
    if not spec:
        return {"code": code, "error": "unknown series"}
    rows = observations(code)
    if not rows:
        return {"code": code, "label": spec["label"],
                "error": "FRED returned nothing for this series"}

    points = _transform(rows, spec["form"], spec["unit"])
    if years:
        cut = _periods_per_year([(d, v) for d, v in rows if v is not None]) * years
        points = points[-cut:] if cut < len(points) else points
    if not points:
        return {"code": code, "label": spec["label"],
                "error": "not enough history to apply this transform"}

    vals = [p["value"] for p in points if p["value"] is not None]
    latest = points[-1]
    prev = points[-2] if len(points) > 1 else None
    return {
        "code": code,
        "label": spec["label"],
        "unit": spec["unit"],
        "form": spec["form"],
        "form_label": FORM_LABEL.get(spec["form"], spec["form"]),
        "note": spec["note"],
        "dates": [p["date"] for p in points],
        "values": [p["value"] for p in points],
        "latest": latest,
        "previous": prev,
        "change": _f((latest["value"] - prev["value"]), 2) if prev else None,
        "min": _f(min(vals), 2) if vals else None,
        "max": _f(max(vals), 2) if vals else None,
        "average": _f(float(np.mean(vals)), 2) if vals else None,
        "points": len(points),
        "source": "FRED (St. Louis Fed), no API key required",
    }


def catalogue() -> Dict[str, Any]:
    """The list, grouped, without fetching anything."""
    return {
        "groups": [
            {"id": g["id"], "label": g["label"],
             "series": [{"code": c, "label": SERIES[c]["label"],
                         "form_label": FORM_LABEL.get(SERIES[c]["form"], ""),
                         "unit": SERIES[c]["unit"]}
                        for c in g["series"] if c in SERIES]}
            for g in GROUPS
        ],
        "count": len(SERIES),
        "note": ("Every series is plotted in the form that is actually read. CPI "
                 "year over year, payrolls as the monthly change, unemployment as "
                 "a level. Applying one rule to all of them is how an economic "
                 "chart ends up technically correct and useless."),
    }
