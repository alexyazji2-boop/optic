"""Guided Investigation (owner's Handoff 10, 2026-11-03): "Investigate this company" on a Dossier runs a fixed,
visible checklist of six steps, one grounded Milo answer each, and keeps their findings as one summary in the
reader's library (Handoff 5).

**What each step reads**, all of it already Optic's (no new feed, no new model):
1. What the company does: its description from its latest annual report on EDGAR (analytics/business.py), else
   Yahoo Finance's profile, said as such; its industry; its revenue by segment for the latest fiscal year.
2. Financial health: the figure registry's figures only (app/figures, Handoff 1), with the inputs each is worked out
   from. The registry has no revenue-growth figure, so the step says so rather than computing one.
3. Segments and company KPIs: revenue and operating income by segment, product and geography, from the filings
   (analytics/segments.py). Operating KPIs are not tagged in filings, which the step says.
4. Peers: the valuation workspace's comparables (valuation/service.py `comps`): the peer universe and its rule, each
   multiple's peer median and quartiles, how many peers had one, read from Yahoo Finance today.
5. Recent events: the Company events timeline (app/timeline.py, Handoff 9), its newest entries of each kind.
6. Risks and questions to check: what the earlier steps observed, as reported facts, and what they could not verify.

**Verified and could not verify, kept apart.** A step's facts are numbered and sent to the model with their period,
as-of date and source; the page shows them as Optic's own table, never as the model's. The model's text is then read
for numbers. A sentence holding a number that matches none of the step's facts is taken out of the answer and listed
under "Could not verify", beside what the step's sources did not have. The model never adds to the verified list.
The advice policy (ai_policy) is applied to every answer, as to every Milo answer.

**No hidden loop.** At most six steps, run one at a time in the reader's order. Each is one model call, charged to
the reader's Milo allowance like a question (main.py `_spend_guard`), and the allowance is shown before the start. A
step with none of its data makes no call and costs nothing. A failed step is retried only when the reader asks.

**Kept as a draft as it runs.** Signed in, an investigation is kept in the library as each step finishes, marked a
draft, so leaving the page or a failure loses nothing; "Save to library" marks it saved under the reader's name for
it. The summary's text is the reader's to edit; the facts and their sources are not.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from . import ai, ai_policy, db, knowledge, timeline as timeline_mod
from .analytics import business as business_mod, segments as segments_mod
from .figures import REGISTRY as FIGURES, definition as figure_definition
from .session import ET

log = logging.getLogger(__name__)

STEPS: Tuple[Dict[str, str], ...] = (
    {"id": "business", "title": "What the company does",
     "reads": "Its description from its latest annual report, its industry and its revenue by segment.",
     "ask": "What does this company do, and where does its revenue come from?",
     "write": "Say what the company does and where its revenue comes from, segment by segment."},
    {"id": "health", "title": "Financial health",
     "reads": "The figure registry's figures: margins, cash flow and net debt, with the filings each comes from.",
     "ask": "How healthy are the company's finances?",
     "write": ("Describe its profitability, cash generation and debt from the figures, comparing the fiscal year with "
               "the last twelve months where both are given. Describe direction in words; compute nothing.")},
    {"id": "segments", "title": "Segments and company KPIs",
     "reads": "Revenue and operating income by segment, product and geography, from the company's filings.",
     "ask": "How do the company's segments compare, and which operating figures does it report?",
     "write": "Compare the segments, products and regions on the figures given, and say which KPIs are not available."},
    {"id": "peers", "title": "Peers",
     "reads": "The valuation comparables: who the peers are and why, and each multiple's peer median and quartiles.",
     "ask": "How is the company valued against its peers?",
     "write": ("Say who the peers are and by what rule, then where the company's multiples sit against the peers' "
               "median and quartiles. A multiple describes the price, not whether it is right.")},
    {"id": "events", "title": "Recent events",
     "reads": "The Company events timeline: news, earnings, insider and congressional trades, analyst actions, "
              "filings.",
     "ask": "What has happened at the company recently?",
     "write": "Summarise the recent events in date order, each with what its date is."},
    {"id": "risks", "title": "Risks and questions to check",
     "reads": "What the earlier steps observed, and what they could not verify.",
     "ask": "What risks do the figures show, and what should be checked next?",
     "write": ("Name the risks the facts show, each as an observed fact with its source, never as a prediction. Then "
               "list three to five questions the reader could check next, including what could not be verified.")},
)
STEP_IDS = tuple(s["id"] for s in STEPS)
TITLES = {s["id"]: s["title"] for s in STEPS}
MAX_STEPS = len(STEPS)
STEP_TIMEOUT = 120.0          # seconds one step's answer may take before it is stopped
STEP_MAX_TOKENS = 3000
FACTS_MAX = 40
EARLIER_MAX = 20
DISCLAIMER = ("Research, not investment advice. Nothing here recommends buying, selling or holding anything; check the "
              "figures and their sources before relying on them.")
INVESTIGATION_PROMPT = """This is one step of a Guided Investigation the reader started: a fixed checklist of steps \
about one company, each answered from the facts Optic sends with it.

Rules for this answer, which override any general guidance about length or tools:
- Use only the numbers in FACTS. Cite each fact you use by its id in square brackets, like [F2], right after it.
- Do not compute new numbers: no growth rates, totals, differences or ratios of your own. Describe direction in words.
- For anything listed under NOT AVAILABLE, say plainly that it is not available. Never estimate it.
- Two to four short paragraphs of plain prose. No headings, no tables, no lists unless the step asks for questions.
- Describe; do not advise. No recommendation, price target, prediction or timing of any trade."""


# ------------------------------------------------------------------------------------------------ facts

def _day_words(iso: Any) -> str:
    try:
        d = datetime.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso or "")
    return "{} {}, {}".format(d.strftime("%b"), d.day, d.year)


def _money(v: Any) -> Optional[str]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    a = abs(x)
    for cut, word in ((1e12, "trillion"), (1e9, "billion"), (1e6, "million")):
        if a >= cut:
            return "{}${:,.1f} {}".format("-" if x < 0 else "", a / cut, word)
    return "{}${:,.0f}".format("-" if x < 0 else "", a)


class Facts:
    """A step's numbered facts and what its sources did not have."""

    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []
        self.missing: List[Dict[str, str]] = []

    def add(self, label: str, text: str, *, period: str = "", as_of: Optional[str] = None, source: str,
            url: Optional[str] = None, definition: str = "", formula: str = "", figure: Optional[str] = None,
            value: Optional[float] = None, kind: str = "figure") -> None:
        if len(self.items) >= FACTS_MAX or not text:
            return
        self.items.append({"id": "F{}".format(len(self.items) + 1), "label": label, "text": text, "period": period,
                           "as_of": as_of, "source": source, "url": url, "definition": definition,
                           "formula": formula, "figure": figure, "value": value, "kind": kind})

    def lack(self, label: str, why: str) -> None:
        if not any(m["label"] == label for m in self.missing):
            self.missing.append({"label": label, "why": why})

    def out(self) -> Dict[str, Any]:
        return {"facts": self.items, "missing": self.missing}


def _segments_table(seg: Dict[str, Any], axis: str, metric: str) -> Optional[Dict[str, Any]]:
    for t in seg.get("tables") or []:
        if t.get("axis") == axis and t.get("metric") == metric:
            return t
    return None


def _latest_year(table: Dict[str, Any]) -> Tuple[Optional[str], List[Tuple[str, float]]]:
    """The last fiscal year every listed member has a value for, and those values, largest first."""
    annual = table.get("annual") or {}
    ends = annual.get("ends") or []
    for k in range(len(ends) - 1, -1, -1):
        vals = [(r["member"], (r.get("values") or [None] * len(ends))[k]) for r in annual.get("rows") or []]
        got = [(m, float(v)) for m, v in vals if isinstance(v, (int, float))]
        if got:
            return ends[k], sorted(got, key=lambda x: -x[1])
    return None, []


SEG_SOURCE = "SEC EDGAR, the company's 10-K and 10-Q filings (XBRL segment tables)"
SHARE_FORMULA = "The segment's revenue divided by the total of the segments' revenue for the same fiscal year, times 100."


def _segment_facts(f: Facts, seg: Dict[str, Any], sym: str, *, metrics: Iterable[str] = ("revenue",),
                   axes: Iterable[str] = ("segment",), shares: bool = True, limit: int = 8) -> None:
    for axis in axes:
        for metric in metrics:
            t = _segments_table(seg, axis, metric)
            if not t:
                continue
            end, rows = _latest_year(t)
            if not end:
                continue
            total = sum(v for _, v in rows if v > 0)
            period = "Fiscal year ended {}".format(_day_words(end))
            for member, value in rows[:limit]:
                f.add("{}, {} ({})".format(t.get("metric_label") or metric, member, (t.get("axis_label") or axis).lower()),
                      _money(value) or "", period=period, as_of=end, source=SEG_SOURCE, value=value,
                      definition="{} attributed to {} in the company's segment note.".format(
                          t.get("metric_label") or metric, member),
                      formula="As reported.", kind="segment")
                if shares and metric == "revenue" and total > 0 and value > 0:
                    pct = value / total * 100.0
                    f.add("{}'s share of segment revenue".format(member), "{:.1f}%".format(pct), period=period,
                          as_of=end, source=SEG_SOURCE + "; worked out by Optic", value=round(pct, 1),
                          definition="How much of the segments' combined revenue this one brought in.",
                          formula=SHARE_FORMULA, kind="share")


def business_facts(sym: str, yf: Any, seg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    f = Facts()
    try:
        prof = yf.profile(sym) or {}
    except Exception:                                                     # noqa: BLE001
        prof = {}
    filing = business_mod.latest(sym) if prof.get("is_company") else None
    text = (filing or {}).get("text") or prof.get("summary") or ""
    if text:
        text = re.sub(r"\s+", " ", text).strip()
        cut = text[:1500].rsplit(". ", 1)[0] + "." if len(text) > 1500 else text
        if filing:
            f.add("Business description", cut, period="From the annual report for {}".format(
                filing.get("period") or "its latest fiscal year"), as_of=filing.get("filed"),
                source="SEC EDGAR, {} filed {}".format(filing.get("form_name") or filing.get("form") or "annual report",
                                                     _day_words(filing.get("filed"))),
                url=filing.get("url"), definition="The company's own description of its business.", kind="text")
        else:
            f.add("Business description", cut, period="Undated", source="Yahoo Finance company profile (undated)",
                  definition="The provider's description of the business; it carries no date.", kind="text")
    else:
        f.lack("Business description", "Neither EDGAR nor Yahoo Finance gave a description for {}.".format(sym))
    if prof.get("industry") or prof.get("sector"):
        f.add("Industry", ", ".join(x for x in (prof.get("industry"), prof.get("sector")) if x),
              period="Not dated by the provider", source="Yahoo Finance company profile",
              definition="The provider's industry and sector classification.", kind="label")
    if prof.get("employees"):
        f.add("Employees", "{:,}".format(int(prof["employees"])), period="Not dated by the provider",
              source="Yahoo Finance company profile", definition="Full-time employees as the provider lists them.",
              value=float(prof["employees"]), kind="count")
    if seg and seg.get("available"):
        before = len(f.items)
        _segment_facts(f, seg, sym, limit=6)
        if len(f.items) == before:
            f.lack("Revenue by segment", "The filings read so far carry no segment revenue for a full fiscal year.")
    else:
        f.lack("Revenue by segment", (seg or {}).get("reason") or "The segment tables could not be read just now.")
    return f.out()


def health_facts(sym: str, figures_block: Dict[str, Any], level: str) -> Dict[str, Any]:
    """The registry's figures and nothing else (Handoff 10: step 2 introduces no figure outside the registry)."""
    f = Facts()
    figs = (figures_block or {}).get("figures") or {}
    seen_inputs = set()
    for fid in ("net_margin_fy", "net_margin_ttm", "operating_cash_flow_fy", "operating_cash_flow_ttm",
                "free_cash_flow_fy", "free_cash_flow_ttm", "net_debt", "net_debt_with_leases", "forward_pe"):
        fig = figs.get(fid) or {}
        entry = FIGURES.get(fid) or {}
        if fig.get("status") != "ok":
            f.lack(fig.get("name") or entry.get("name") or fid,
                   "{}{}".format(fig.get("text") or "Not available", ": " + fig["why"] if fig.get("why") else "."))
            continue
        src = fig.get("source") or {}
        where = src.get("provider") or "Source not given"
        if src.get("form"):
            where += ", {}{}".format(src["form"], " filed {}".format(_day_words(src["filed"])) if src.get("filed") else "")
        period = (fig.get("period") or {}).get("label") or ""
        f.add(fig.get("name") or entry.get("name") or fid, fig.get("text") or "", period=period, as_of=fig.get("as_of"),
              source=where, url=src.get("url"), definition=figure_definition(fid, level),
              formula=entry.get("formula") or "", figure=fid, value=fig.get("value"))
        for inp in fig.get("inputs") or []:
            if inp.get("value") is None:
                continue
            ident = (inp.get("name"), inp.get("start"), inp.get("end"), inp.get("value"))
            if ident in seen_inputs:
                continue
            seen_inputs.add(ident)
            span = ("{} to {}".format(_day_words(inp["start"]), _day_words(inp["end"])) if inp.get("start")
                    else "On {}".format(_day_words(inp["end"])) if inp.get("end") else period)
            f.add("{} (an input to {})".format(inp.get("name"), fig.get("name") or fid), inp.get("text") or "",
                  period=span, as_of=inp.get("end"),
                  source="SEC EDGAR{}".format(", " + inp["form"] if inp.get("form") else "") if inp.get("form") or inp.get("url")
                  else where, url=inp.get("url"), definition="As the filing reports it, the line {}.".format(
                      inp.get("line") or "named in the registry"), formula="As reported.", kind="input")
    f.lack("Revenue and profit growth",
           "The figure registry has no growth figure, so none is stated; each figure's fiscal year and twelve months "
           "are given where both exist.")
    return f.out()


def segments_facts(sym: str, seg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    f = Facts()
    if not seg or not seg.get("available"):
        f.lack("Segments", (seg or {}).get("reason") or "The segment tables could not be read just now.")
    else:
        _segment_facts(f, seg, sym, metrics=("revenue", "operating_income"), axes=("segment", "product", "geography"),
                       limit=6)
        if not f.items:
            f.lack("Segments", "The filings read so far carry no segment figures for a full fiscal year.")
        if seg.get("filings_unread"):
            f.lack("Older segment figures", "{} filings are not read yet.".format(seg.get("filings_unread")))
    f.lack("Company KPIs", ((seg or {}).get("kpi_note") or "Operating metrics are not tagged in the filings, so Optic "
                            "has no source for them.").split(". ")[0].rstrip(".") + ".")
    return f.out()


PEER_RULE = {"industry": "the largest companies in its Yahoo Finance industry within 25 times its market value either "
                         "way, the eight closest in size",
             "industry_and_sector": "the largest companies in its Yahoo Finance industry within 25 times its market "
                                    "value, with the sector's largest added to reach five",
             "reader": "the peers the reader chose"}


def peer_facts(sym: str, comps: Optional[Dict[str, Any]], today: str) -> Dict[str, Any]:
    f = Facts()
    if not comps or not comps.get("available"):
        f.lack("Peers", (comps or {}).get("reason") or "The peer comparison could not be read just now.")
        return f.out()
    peers = comps.get("peers") or []
    names = ", ".join("{} ({})".format(p.get("name") or p.get("symbol"), p.get("symbol")) for p in peers)
    f.add("Peer universe", "{} companies: {}".format(len(peers), names),
          period="Read {}".format(_day_words(today)), as_of=today, source="Yahoo Finance industry and market values",
          definition="Rule: {}.".format(PEER_RULE.get(comps.get("peer_source"), "the valuation workspace's rule")),
          value=float(len(peers)), kind="universe")
    for row in comps.get("implied") or []:
        label = row.get("label") or row.get("key")
        own = row.get("own_multiple")
        if own is not None:
            f.add("{}'s {}".format(sym, label), "{:.1f}x".format(own), period="Trailing twelve months", as_of=today,
                  source=comps.get("source") or "Yahoo Finance", value=round(float(own), 1),
                  definition="The company's own multiple as the quote feed gives it.", formula=label + ".")
        imp = row.get("implied") or {}
        if imp.get("mid"):
            text = "median {:.1f}x, 25th percentile {:.1f}x, 75th percentile {:.1f}x, over {} peers".format(
                imp["mid"]["multiple"], imp["low"]["multiple"], imp["high"]["multiple"], row.get("peers_with_value"))
            f.add("Peers' {}".format(label), text, period="Trailing twelve months", as_of=today,
                  source=comps.get("source") or "Yahoo Finance", value=round(float(imp["mid"]["multiple"]), 1),
                  definition="The peers with a positive figure; {}.".format(
                      "outliers set aside: " + ", ".join(row["outliers"]) if row.get("outliers") else "no outliers"),
                  formula="The median and quartiles of the peers' multiples.", kind="peers")
        else:
            f.lack("Peers' {}".format(label), row.get("reason") or "Not enough peers have this figure.")
        if row.get("wide"):
            f.add("{}: how far the peers disagree".format(label),
                  "75th percentile {:.1f} times the 25th".format(row.get("spread") or 0), as_of=today,
                  source="Worked out by Optic from the peers' multiples", value=round(float(row.get("spread") or 0), 1),
                  definition="Above 2, the comparison says more about which peers were chosen than about the company.",
                  formula="75th percentile multiple divided by the 25th.", kind="spread")
    return f.out()


def event_facts(sym: str, built: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    f = Facts()
    if not built:
        f.lack("Recent events", "The Company events timeline could not be read just now.")
        return f.out()
    sources = built.get("sources") or {}
    for kind, state in sources.items():
        if state.get("state") == "failed":
            f.lack("{} (events)".format(timeline_mod.NOUNS.get(kind, kind)), state.get("failed") or "Did not answer.")
    events = built.get("events") or []
    take = {"earnings": 3, "news": 3, "analysts": 3, "insiders": 3, "congress": 2, "filings": 3}
    used: Dict[str, int] = {}
    for e in events:
        k = e["type"]
        if used.get(k, 0) >= take.get(k, 0):
            continue
        used[k] = used.get(k, 0) + 1
        when = "{} {}".format(e["date_label"], _day_words(e["date"]))
        words = e["title"] + (". " + e["summary"] if e.get("summary") else "")
        f.add("{}, {}".format(e["type_label"], when), words, period=when, as_of=e["date"], source=e["source"],
              url=e.get("source_url"), definition=(e.get("delay_note") or timeline_mod.DATES.get(k, "")),
              kind="event")
    since = built.get("since")
    if not events:
        # counts of nothing are not events: with no entry at all there is nothing to summarise, and Milo is not asked
        f.lack("Recent events", "None of the timeline's sources reported an event for {} since {}.".format(
            sym, _day_words(since)) if since else "The timeline has no events for {}.".format(sym))
        for kind, state in sources.items():
            if state.get("reach"):
                f.lack("{}: coverage".format(timeline_mod.NOUNS.get(kind, kind)), state["reach"])
        return f.out()
    count = lambda pred: sum(1 for e in events if pred(e))                       # noqa: E731
    sales = count(lambda e: e["type"] == "insiders" and e["title"].startswith("Sale of"))
    buys = count(lambda e: e["type"] == "insiders" and e["title"].startswith("Purchase of"))
    if sources.get("insiders", {}).get("state") != "failed":
        f.add("Insider open-market sales and purchases since {}".format(_day_words(since)),
              "{} sales, {} purchases".format(sales, buys), period="{} to {}".format(_day_words(since),
                                                                               _day_words(built.get("today"))),
              as_of=built.get("today"), source="Form 4 filings, as the Company events timeline lists them",
              definition="Form 4 transactions described as a sale or a purchase; awards and other kinds are not counted.",
              formula="A count of the timeline's entries.", value=float(sales), kind="count")
    downs = count(lambda e: e["type"] == "analysts" and " downgraded " in e["title"])
    ups = count(lambda e: e["type"] == "analysts" and " upgraded " in e["title"])
    if sources.get("analysts", {}).get("state") != "failed":
        f.add("Analyst upgrades and downgrades since {}".format(_day_words(since)),
              "{} upgrades, {} downgrades".format(ups, downs), as_of=built.get("today"),
              period="{} to {}".format(_day_words(since), _day_words(built.get("today"))),
              source="Yahoo Finance's record of analyst actions, as the timeline lists it",
              definition="Rating changes only; reiterations and target changes are not counted.",
              formula="A count of the timeline's entries.", value=float(downs), kind="count")
    for kind, state in sources.items():
        if state.get("reach"):
            f.lack("{}: coverage".format(timeline_mod.NOUNS.get(kind, kind)), state["reach"])
    return f.out()


def risk_facts(sym: str, figures_block: Dict[str, Any], seg: Optional[Dict[str, Any]],
               built: Optional[Dict[str, Any]], comps: Optional[Dict[str, Any]], today: str,
               earlier: List[str], level: str) -> Dict[str, Any]:
    """The observed facts that bear on risk, gathered again from the same sources as the earlier steps."""
    f = Facts()
    health = health_facts(sym, figures_block, level)
    for item in health["facts"]:
        if item.get("figure") in ("net_debt", "free_cash_flow_ttm", "net_margin_ttm"):
            f.items.append(dict(item, id="F{}".format(len(f.items) + 1)))
    if seg and seg.get("available"):
        t = _segments_table(seg, "segment", "revenue")
        if t:
            end, rows = _latest_year(t)
            total = sum(v for _, v in rows if v > 0)
            if end and rows and total > 0:
                top, value = rows[0]
                f.add("Largest segment's share of segment revenue", "{}: {:.1f}%".format(top, value / total * 100.0),
                      period="Fiscal year ended {}".format(_day_words(end)), as_of=end,
                      source=SEG_SOURCE + "; worked out by Optic", value=round(value / total * 100.0, 1),
                      definition="How much of the segments' combined revenue the largest one brought in.",
                      formula=SHARE_FORMULA, kind="share")
    events = event_facts(sym, built)
    for item in events["facts"]:
        if item["kind"] == "count" or item["label"].startswith("Earnings"):
            f.items.append(dict(item, id="F{}".format(len(f.items) + 1)))
    if comps and comps.get("available"):
        for row in comps.get("implied") or []:
            if row.get("wide"):
                f.add("{}: how far the peers disagree".format(row.get("label")),
                      "75th percentile {:.1f} times the 25th".format(row.get("spread") or 0), as_of=today,
                      source="Worked out by Optic from the peers' multiples", value=round(float(row.get("spread") or 0), 1),
                      definition="Above 2, the comparison says more about which peers were chosen than about the company.",
                      formula="75th percentile multiple divided by the 25th.", kind="spread")
    for m in health["missing"] + events["missing"]:
        f.lack(m["label"], m["why"])
    out = f.out()
    out["earlier"] = [re.sub(r"\s+", " ", str(x)).strip()[:300] for x in (earlier or []) if str(x).strip()][:EARLIER_MAX]
    return out


# ------------------------------------------------------------------------------------------------ checking an answer

_NUM = re.compile(r"(?<![\w.])(\$)?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?"
                  r"(%|percent\b|x\b|times\b|trillion\b|billion\b|million\b|thousand\b|bn\b|[BMKT]\b)?", re.I)
_MONTH = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?"
                    r"(?:,\s*\d{4})?", re.I)
_LABELS = re.compile(r"\b(?:Q[1-4]|FY|H[12])\s?'?\d{2,4}\b|\b(?:19|20)\d{2}\b|\[F\d+\]|\bF\d+\b", re.I)
_SCALE = {"trillion": 1e12, "t": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "m": 1e6,
          "thousand": 1e3, "k": 1e3}


def _numbers(text: str) -> List[Tuple[str, float, str]]:
    """The figures in a text: (as written, value, unit), with dates, years, fiscal labels and citations left out."""
    clean = _LABELS.sub(" ", _MONTH.sub(" ", text))
    out = []
    for m in _NUM.finditer(clean):
        cur, raw, unit = m.group(1), m.group(2), (m.group(3) or "").lower()
        value = float(raw.replace(",", ""))
        if not cur and not unit and value <= 12 and "." not in raw:
            continue    # a count or an ordinal ("three segments", "the last 4 reports") is not a figure
        kind = ("percent" if unit in ("%", "percent") else "multiple" if unit in ("x", "times")
                else "money" if cur or unit in _SCALE else "plain")
        scaled = value * _SCALE.get(unit, 1.0)
        out.append((m.group(0).strip(), scaled, kind))
    return out


def _decimals(written: str) -> int:
    m = re.search(r"\.(\d+)", written)
    return len(m.group(1)) if m else 0


def _matches(written: str, value: float, kind: str, facts: List[Dict[str, Any]]) -> bool:
    """Whether a figure in the answer is one of the facts, as written or rounded from it."""
    places = _decimals(written)
    for fact in facts:
        for w2, v2, k2 in _numbers(" ".join(str(fact.get(k) or "") for k in ("text", "label", "period"))):
            if kind != "plain" and k2 != "plain" and kind != k2:
                continue
            if kind == "money" or k2 == "money":
                # money as written ("$416 billion") against the fact's ("$416.2 billion"): the same scale and rounding
                scale = 1e12 if abs(v2) >= 1e12 else 1e9 if abs(v2) >= 1e9 else 1e6 if abs(v2) >= 1e6 else 1.0
                if round(v2 / scale, places) == round(value / scale, places):
                    return True
                continue
            if round(v2, places) == round(value, places):
                return True
    return False


_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")


def check(text: str, facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Split an answer into what stays (every figure in it is one of the facts) and the sentences holding a figure
    that matches none, which are moved to "Could not verify". Citations of facts that do not exist are dropped."""
    ids = {f["id"] for f in facts}
    text = re.sub(r"\s*\[(F\d+)\]", lambda m: m.group(0) if m.group(1) in ids else "", text or "")
    kept_paras, moved = [], []
    for para in re.split(r"\n\s*\n", text.strip()):
        keep = []
        for sentence in _SENTENCE.split(para.strip()):
            if not sentence.strip():
                continue
            bad = [w for w, v, k in _numbers(sentence) if not _matches(w, v, k, facts)]
            if bad:
                moved.append({"text": re.sub(r"\s*\[F\d+\]", "", sentence).strip(), "figures": bad})
            else:
                keep.append(sentence.strip())
        if keep:
            kept_paras.append(" ".join(keep))
    cited = sorted({m for m in re.findall(r"\[(F\d+)\]", "\n\n".join(kept_paras))}, key=lambda x: int(x[1:]))
    return {"text": "\n\n".join(kept_paras), "unverified": moved, "cited": cited}


def sources_of(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The step's numbered sources: each distinct source once, in the order its facts come."""
    out: List[Dict[str, Any]] = []
    for fact in facts:
        key = (fact.get("source"), fact.get("url"))
        found = next((s for s in out if (s["name"], s.get("url")) == key), None)
        if not found:
            found = {"n": len(out) + 1, "name": fact.get("source"), "url": fact.get("url")}
            out.append(found)
        fact["source_n"] = found["n"]
    return out


# ------------------------------------------------------------------------------------------------ one step

def prompt_for(step: Dict[str, str], n: int, total: int, sym: str, name: str, today: str,
               gathered: Dict[str, Any]) -> str:
    lines = ["INVESTIGATION STEP {} of {}: {}".format(n, total, step["title"]),
             "Company: {}{}".format(sym, " ({})".format(name) if name and name != sym else ""),
             "Today: {} (New York)".format(_day_words(today)),
             "The step's question: {}".format(step["ask"]), "",
             "FACTS. Optic verified each of these; its value, period, as-of date and source are fixed:"]
    for fact in gathered.get("facts") or []:
        bits = [x for x in (fact.get("period"), "as of {}".format(_day_words(fact["as_of"])) if fact.get("as_of") else "",
                            fact.get("source")) if x]
        lines.append("[{}] {}: {} ({})".format(fact["id"], fact["label"], fact["text"], "; ".join(bits)))
    if not gathered.get("facts"):
        lines.append("(none)")
    lines += ["", "NOT AVAILABLE. Say plainly that these are not available; never estimate them:"]
    lines += ["- {}: {}".format(m["label"], m["why"]) for m in gathered.get("missing") or []] or ["(nothing)"]
    if gathered.get("earlier"):
        lines += ["", "EARLIER STEPS COULD NOT VERIFY. Turn these into questions to check, not into facts:"]
        lines += ["- {}".format(x) for x in gathered["earlier"]]
    lines += ["", "WRITE: {}".format(step["write"])]
    return "\n".join(lines)


def _sync_client() -> Any:
    """The writers' client, as ai._ask's other callers make theirs: synchronous, retried, within the step's limit."""
    from anthropic import Anthropic
    return Anthropic(max_retries=3, timeout=STEP_TIMEOUT)


def answer(prompt: str, level: str) -> Dict[str, Any]:
    """One model call for one step, through ai._ask (one of the app's three policy points): Milo's model and prompt,
    the advice policy in the system prompt and applied to the reply, the call kept in the cost ledger as
    "investigation". No tools. Raises when the model does not answer; the caller holds it to the step's time limit."""
    msg = ai._ask(_sync_client(), "investigation", model=ai.PULSE_MODEL, max_tokens=STEP_MAX_TOKENS,
                  system=[{"type": "text", "text": ai.SYSTEM_PROMPT + ai.FORMAT_PROMPT + "\n\n" + ai_policy.POLICY_TEXT,
                           "cache_control": {"type": "ephemeral"}},
                          {"type": "text", "text": knowledge.prompt_for(level)},
                          {"type": "text", "text": INVESTIGATION_PROMPT}],
                  messages=[{"role": "user", "content": prompt}])
    if getattr(msg, "stop_reason", None) == "refusal":
        raise RuntimeError("The answer was declined by the model's safety checks.")
    text = "".join(getattr(b, "text", "") or "" for b in getattr(msg, "content", None) or []
                   if getattr(b, "type", "") == "text")
    usage = getattr(msg, "usage", None)
    return {"text": text.strip(), "removed": ai.last_removed(),
            "usage": {"input": getattr(usage, "input_tokens", None), "output": getattr(usage, "output_tokens", None)}}


def result(step_id: str, gathered: Dict[str, Any], said: Optional[Dict[str, Any]], *, took: float,
           no_data: bool = False) -> Dict[str, Any]:
    """A finished step as the page draws it and the library keeps it."""
    facts = gathered.get("facts") or []
    sources = sources_of(facts)
    checked = check((said or {}).get("text") or "", facts) if said else {"text": "", "unverified": [], "cited": []}
    unverified = [{"text": "{}: {}".format(m["label"], m["why"]), "kind": "not_available"}
                  for m in gathered.get("missing") or []]
    unverified += [{"text": u["text"], "figures": u["figures"], "kind": "unmatched"} for u in checked["unverified"]]
    return {"step": step_id, "title": TITLES[step_id], "state": "done", "no_data": no_data,
            "text": checked["text"], "facts": facts, "sources": sources, "unverified": unverified,
            "earlier": gathered.get("earlier") or [],
            "removed": (said or {}).get("removed", 0), "usage": (said or {}).get("usage"),
            "at": datetime.now(timezone.utc).isoformat(), "took_ms": int(took * 1000), "disclaimer": DISCLAIMER}


def failed(step_id: str, why: str) -> Dict[str, Any]:
    return {"step": step_id, "title": TITLES[step_id], "state": "failed", "why": why,
            "at": datetime.now(timezone.utc).isoformat()}


# ------------------------------------------------------------------------------------------------ keeping it

KIND = "investigation"


def _now_name(sym: str, now: Optional[datetime] = None) -> str:
    day = (now or datetime.now(timezone.utc)).astimezone(ET)
    return "Investigation of {}, {} {}, {}".format(sym, day.strftime("%b"), day.day, day.year)


def status_of(inv: Dict[str, Any]) -> Dict[str, Any]:
    """Where an investigation stands: its steps' counts, whether it is partial, and the library's summary of it."""
    order = inv.get("order") or []
    skipped = [s for s in order if s in (inv.get("skipped") or [])]
    steps = inv.get("steps") or {}
    done = [s for s in order if (steps.get(s) or {}).get("state") == "done"]
    failed_ = [s for s in order if (steps.get(s) or {}).get("state") == "failed"]
    planned = [s for s in order if s not in skipped]
    left = [s for s in planned if s not in done]
    partial = bool(skipped or failed_ or (left and inv.get("stopped")))
    return {"status": inv.get("status") or "draft", "done": len(done), "planned": len(planned), "steps": len(order),
            "skipped": skipped, "failed": failed_, "left": left, "partial": partial,
            "complete": not left and not skipped}


def summary_text(inv: Dict[str, Any]) -> str:
    """The investigation as one plain text, for the library's search and a copy: each step's findings, as edited."""
    lines = [inv.get("name") or "Investigation of {}".format(inv.get("ticker"))]
    steps = inv.get("steps") or {}
    edits = inv.get("edits") or {}
    for sid in inv.get("order") or []:
        st = steps.get(sid) or {}
        if st.get("state") != "done":
            continue
        lines += ["", TITLES.get(sid, sid), re.sub(r"\s*\[F\d+\]", "", edits.get(sid) or st.get("text") or "") or
                  "Not reported: Optic has none of this step's figures."]
    if inv.get("notes"):
        lines += ["", "Notes", inv["notes"]]
    return "\n".join(lines)[:20000]


def new(sym: str, order: List[str], skipped: List[str], level: str) -> Dict[str, Any]:
    return {"id": uuid.uuid4().hex[:16], "ticker": sym, "order": order, "skipped": skipped, "level": level,
            "status": "draft", "steps": {}, "edits": {}, "notes": "", "name": _now_name(sym),
            "started_at": datetime.now(timezone.utc).isoformat()}


def store_new(user_id: str, inv: Dict[str, Any], limit: int) -> Optional[str]:
    """Kept in the library as a draft. None when the plan's library is full: the page then says it is not kept."""
    count = db.row("SELECT COUNT(*) AS n FROM saved_research WHERE user_id = ?", (user_id,))
    if int((count or {}).get("n") or 0) >= limit:
        return None
    rid = db.new_id()
    now = db.utcnow()
    db.execute("INSERT INTO saved_research (id, user_id, title, symbol, content, research_type, created_at, updated_at, "
               "tickers, ref, summary, payload, item_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (rid, user_id, inv["name"], inv["ticker"], summary_text(inv), KIND, now, now, json.dumps([inv["ticker"]]),
                json.dumps({"investigation": inv["id"]}), json.dumps(status_of(inv)), json.dumps(inv),
                "{}:{}".format(KIND, inv["id"])))
    return rid


def load(user_id: str, item_id: str) -> Optional[Dict[str, Any]]:
    row = db.row("SELECT * FROM saved_research WHERE id = ? AND user_id = ? AND research_type = ?",
                 (item_id, user_id, KIND))
    if not row:
        return None
    try:
        inv = json.loads(row.get("payload") or "{}")
    except ValueError:
        return None
    inv["name"] = row.get("title") or inv.get("name")
    inv["item_id"] = row["id"]
    inv["saved_at"] = row.get("updated_at")
    return inv


def store(user_id: str, item_id: str, inv: Dict[str, Any]) -> None:
    payload = json.dumps({k: v for k, v in inv.items() if k not in ("item_id", "saved_at")})
    if len(payload) > 400000:
        raise ValueError("This investigation is too large to keep.")
    db.execute("UPDATE saved_research SET title = ?, content = ?, summary = ?, payload = ?, updated_at = ? "
               "WHERE id = ? AND user_id = ? AND research_type = ?",
               (inv.get("name") or _now_name(inv["ticker"]), summary_text(inv), json.dumps(status_of(inv)), payload,
                db.utcnow(), item_id, user_id, KIND))


def plan(allowance: Dict[str, Any], signed_in: bool) -> Dict[str, Any]:
    """What a reader is shown before anything runs: the steps, the most it can cost, the longest it can take."""
    left, enforced = allowance.get("left"), allowance.get("enforced", True)
    return {
        "steps": [{"id": s["id"], "title": s["title"], "reads": s["reads"]} for s in STEPS],
        "max_steps": MAX_STEPS, "step_timeout_s": int(STEP_TIMEOUT),
        "time_note": ("Steps run one at a time. Each is one Milo answer, and a step that has not finished after {} "
                      "minutes stops and can be retried, so {} steps take at most {} minutes.".format(
                          int(STEP_TIMEOUT // 60), MAX_STEPS, int(STEP_TIMEOUT // 60) * MAX_STEPS)),
        "usage": {"per_step": 1, "most": MAX_STEPS, "left": left if enforced is not False else None,
                  "allowed": allowance.get("allowed"), "enforced": enforced is not False,
                  "scope": allowance.get("scope"), "plan": allowance.get("plan_label") or allowance.get("plan"),
                  "requires_account": bool(allowance.get("requires_account")),
                  "note": ("Each step that asks Milo counts as one assistant message from your allowance, as a "
                           "question does, even if it fails. A step with none of its data asks nothing.")},
        "keeps": ("As each step finishes, the investigation is kept as a draft in Saved research, so leaving this page "
                  "loses nothing. Save to library marks it saved, under a name you can change in Saved research." if signed_in else
                  "Signed out, nothing is kept: leaving this page loses the investigation."),
        "disclaimer": DISCLAIMER,
    }
