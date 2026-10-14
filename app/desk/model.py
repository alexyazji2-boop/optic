"""The evidence record, and the story clustering that keeps syndication honest.

An edition may say only what an `Evidence` row supports, and every row says
where it came from and which of three different times it carries:

  published_at  when the source made it public (a story, a filing, a release)
  event_at      when the thing itself happened (a session's close, a decision)
  period        what a figure describes ("2026-09" for September's CPI, "FQ3
                2026" for a company's fiscal quarter, "1d" for a day's change)

A September inflation figure published on 15 October is not "today's
inflation", and the edition can only get that right if the record keeps the
three apart.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

KINDS = ("index", "sector", "breadth", "macro", "rates", "fx", "commodity", "credit",
         "volatility", "calendar", "earnings", "company", "filing", "news", "options",
         "policy")


@dataclass
class Evidence:
    id: str                         # stable within an edition: "M3", "N12"
    kind: str                       # one of KINDS
    label: str                      # "10-year Treasury yield"
    value: Optional[float] = None   # the figure, in `unit`
    unit: str = ""                  # "%", "pp", "bp", "$", "$bn", "x", "index", "k"
    period: str = ""                # what the figure describes
    published_at: Optional[str] = None
    event_at: Optional[str] = None
    as_of: Optional[str] = None     # when Optic read it
    source: str = ""                # "FRED (St. Louis Fed): DGS10"
    url: Optional[str] = None
    method: str = ""                # how a derived figure was computed
    compare: Optional[Dict[str, Any]] = None   # {"base": "a week earlier", "value": 4.41, "change": 0.17, "change_unit": "pp"}
    symbol: Optional[str] = None
    text: str = ""                  # a headline or a one-line description
    detail: Dict[str, Any] = field(default_factory=dict)
    sources_in_cluster: int = 1     # distinct outlets carrying the same story
    stale: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, "", {}, [])}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------- syndication

# Words that carry no identity: two headlines about the same event differ in
# these and agree in the rest.
_STOP = set("""a an the and or but of to in on for at by with from as is are was were be
been it its this that these those after before over under into about amid says said
say report reports reported new news update live stock stocks shares market markets
us u.s. week today why how what will could may might""".split())


_UNIT = {"billion": "bn", "bln": "bn", "b": "bn", "million": "mn", "mln": "mn", "m": "mn",
         "trillion": "tn", "percent": "%", "pct": "%"}


def _stem(w: str) -> str:
    """Crude, on purpose: "violations" and "violated", "fined" and "fine"."""
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ied", "ed", "es", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def _tokens(title: str) -> set:
    text = (title or "").lower().replace("’", "'")
    # "$1.2bn", "$1.21 billion" and "1.2 billion" are one figure: the number
    # rounded to one decimal, its unit normalised.
    text = re.sub(r"\$?(\d+(?:\.\d+)?)\s*(billion|bln|bn|b|million|mln|mn|m|trillion|tn)\b",
                  lambda m: "{:.1f}{}".format(float(m.group(1)), _UNIT.get(m.group(2), m.group(2))), text)
    words = re.findall(r"[a-z0-9%.]+", text)
    out = set()
    for w in words:
        w = w.strip(".")
        if not w or w in _STOP or len(w) < 2:
            continue
        out.add(w if re.match(r"^[0-9.]+[a-z%]*$", w) else _stem(w))
    return out


def canonical_url(url: Optional[str]) -> str:
    """A link without its tracking and its scheme, for matching."""
    if not url:
        return ""
    u = re.sub(r"^https?://(www\.)?", "", url.strip().lower())
    u = re.sub(r"[?#].*$", "", u)
    return u.rstrip("/")


def similar(a: str, b: str) -> float:
    """How far two headlines share their content words: the overlap
    coefficient (shared words over the shorter headline's), so a short
    headline and a long re-titling of it still match."""
    ta, tb = _tokens(a), _tokens(b)
    if len(ta) < 3 or len(tb) < 3:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


# Two headlines are the same story when they share most of the shorter one's
# content words AND at least four of them. Measured on the live wires
# (2026-10-13, 276 stories in 36 hours; the pairs are in
# tests/test_desk_edition.py): the same event across outlets scored 0.56 to
# 0.86 sharing five or more words; a five-word headline ("What could Trump's
# energy ceasefire mean for Ukraine?") scored 0.6 against three different
# stories on three shared words, which the second condition refuses. Between
# 0.4 and 0.5 sat both re-titlings of one event and different pieces on one
# theme, so those stay apart: an unmerged duplicate overstates coverage by
# one, a wrongly merged story drops one from the edition.
SAME_STORY = 0.55
SAME_STORY_MIN_SHARED = 4


def same_story(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if len(ta) < 3 or len(tb) < 3:
        return False
    shared = len(ta & tb)
    return shared >= SAME_STORY_MIN_SHARED and shared / min(len(ta), len(tb)) >= SAME_STORY


def cluster(stories: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group the same story carried by several outlets.

    Each cluster keeps its earliest publication as the representative (the
    original rather than the re-post), the list of distinct outlets, and how
    many there are. A story on five sites is one report: `outlets` says how
    widely it was carried, and nothing downstream may treat the count as
    independent confirmation, because syndicated copies are the same reporting.
    """
    clusters: List[Dict[str, Any]] = []
    for s in stories:
        title = s.get("title") or ""
        url = canonical_url(s.get("url"))
        home = None
        for c in clusters:
            if url and url in c["_urls"]:
                home = c
                break
            if same_story(title, c["title"]):
                home = c
                break
        outlet = s.get("source") or s.get("source_id") or ""
        if home is None:
            clusters.append({**s, "_urls": {url} if url else set(), "outlets": [outlet] if outlet else [],
                             "copies": 1, "sectors": [s["sector"]] if s.get("sector") else []})
            continue
        home["copies"] += 1
        if s.get("sector") and s["sector"] not in home["sectors"]:
            home["sectors"].append(s["sector"])
        if url:
            home["_urls"].add(url)
        if outlet and outlet not in home["outlets"]:
            home["outlets"].append(outlet)
        # The earliest copy represents the story: it is the likeliest original.
        if (s.get("published") or "9999") < (home.get("published") or "9999"):
            keep = {k: home[k] for k in ("_urls", "outlets", "copies", "sectors")}
            home.clear()
            home.update({**s, **keep})
    for c in clusters:
        c.pop("_urls", None)
    return clusters
