"""The Optic Desk, read for one portfolio.

The canonical market edition is written once for everyone (`app/desk`), and
this never regenerates it or calls a model: it reads the stored edition's own
evidence rows and says which of them touch what the reader holds, and why.
That keeps the cost of a personalised section at zero and every line traceable
to the same sources the edition cites.

A row is relevant when:
- it is about a symbol the reader holds (a company's shares, its earnings, or
  an index fund the reader owns directly, such as QQQ);
- it is a sector fund's move and the reader holds stocks Yahoo classifies in
  that sector (the SPDR map the research framework already uses);
- it is a headline that names a company the reader holds
  (`catalyst_rules.named_companies`, the same matcher the catalyst library
  uses: names and $TICKER mentions, not substrings).
Scheduled macro releases in the next three days are listed apart, as
market-wide: they touch everything and nothing in particular.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

VERSION = "desk-portfolio-2026-10-15.1"
SECTOR_ETF = {
    "Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV", "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP", "Energy": "XLE", "Industrials": "XLI", "Basic Materials": "XLB",
    "Real Estate": "XLRE", "Utilities": "XLU", "Communication Services": "XLC",
}
MACRO_DAYS = 3


def _cited_in(edition: Dict[str, Any]) -> Dict[str, List[str]]:
    """Evidence id -> titles of the sections that cite it."""
    out: Dict[str, List[str]] = {}

    def walk(node: Any, title: str) -> None:
        if isinstance(node, dict):
            for c in node.get("cites") or []:
                out.setdefault(str(c), [])
                if title and title not in out[str(c)]:
                    out[str(c)].append(title)
            ev = node.get("evidence")
            if isinstance(ev, str):
                out.setdefault(ev, [])
                if title and title not in out[ev]:
                    out[ev].append(title)
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v, title)
        elif isinstance(node, list):
            for v in node:
                walk(v, title)

    for s in edition.get("sections") or []:
        walk(s, s.get("title") or ("Opening" if s.get("id") == "opening" else s.get("id") or ""))
    for c in edition.get("headline_cites") or []:
        out.setdefault(str(c), []).append("Headline")
    return out


def build(served: Dict[str, Any], holdings: Iterable[Dict[str, Any]],
          sector_of: Optional[Callable[[str], Optional[str]]] = None,
          named_in: Optional[Callable[[str], List[str]]] = None,
          today: Optional[date] = None) -> Dict[str, Any]:
    """`served` is `desk.edition.served(...)`; holdings are the overview's."""
    if not served or served.get("available") is not True:
        return {"available": False, "version": VERSION,
                "reason": (served or {}).get("reason") or "No Optic Desk edition has been published yet."}
    ed = served.get("edition") or {}
    today = today or date.today()
    held: Dict[str, float] = {}
    sectors: Dict[str, List[str]] = {}
    for h in holdings or []:
        sym = str(h.get("symbol") or "").upper()
        if not sym:
            continue
        held[sym] = held.get(sym, 0.0) + float(h.get("weight_pct") or 0.0)
        sec = h.get("sector")
        if sec is None and sector_of and h.get("kind") == "equity":
            try:
                sec = sector_of(sym)
            except Exception:                                   # noqa: BLE001
                sec = None
        if sec and h.get("kind") == "equity":
            sectors.setdefault(sec, []).append(sym)
    etf_sector = {etf: sec for sec, etf in SECTOR_ETF.items() if sec in sectors}
    cited = _cited_in(ed)

    items: List[Dict[str, Any]] = []
    macro: List[Dict[str, Any]] = []
    for ev in ed.get("evidence") or []:
        kind, sym = ev.get("kind"), str(ev.get("symbol") or "").upper()
        why, names = None, []
        if sym and sym in held:
            why = "You hold {} ({:.1f}% of your portfolio).".format(sym, held[sym])
            names = [sym]
        elif kind == "sector" and sym in etf_sector:
            sec = etf_sector[sym]
            names = sorted(sectors[sec])
            why = "{} is the {} sector fund; you hold {} in that sector.".format(sym, sec, ", ".join(names))
        elif kind in ("news", "policy") and named_in:
            try:
                named = [s for s in named_in("{} {}".format(ev.get("label") or "", ev.get("text") or "")) if s in held]
            except Exception:                                   # noqa: BLE001
                named = []
            if named:
                names = named
                why = "Names {}, which you hold.".format(", ".join(named))
        elif kind == "calendar":
            at = str(ev.get("event_at") or "")[:10]
            try:
                days = (date.fromisoformat(at) - today).days
            except ValueError:
                days = None
            if days is not None and 0 <= days <= MACRO_DAYS:
                macro.append({"evidence_id": ev.get("id"), "label": ev.get("label"), "event_at": ev.get("event_at"),
                              "text": ev.get("text"), "source": ev.get("source"), "url": ev.get("url")})
            continue
        if not why:
            continue
        items.append({
            "evidence_id": ev.get("id"), "kind": kind, "symbols": names, "label": ev.get("label"),
            "value": ev.get("value"), "unit": ev.get("unit"), "text": ev.get("text"), "source": ev.get("source"),
            "url": ev.get("url"), "published_at": ev.get("published_at"), "event_at": ev.get("event_at"),
            "why": why, "cited_in": cited.get(str(ev.get("id")), []),
            "weight_pct": round(sum(held.get(n, 0.0) for n in names), 2),
        })
    items.sort(key=lambda i: (0 if i["cited_in"] else 1, -i["weight_pct"]))
    return {
        "available": True, "version": VERSION,
        "edition": {"key": ed.get("key"), "date": ed.get("date"), "slot_label": ed.get("slot_label"),
                    "headline": ed.get("headline"), "generated_at": ed.get("generated_at"),
                    "is_today": bool(served.get("is_today")), "written_by": ed.get("written_by"),
                    "test_edition": bool(ed.get("test_edition"))},
        "items": items, "market_wide": macro,
        "link": "#/read",
        "limitations": [
            "Drawn only from the evidence this edition cited or outlined, not from everything published "
            "that day. A story about something you hold that the edition did not use is not here.",
            "Sector matches use Yahoo's sector for each stock you hold; funds are not looked through here.",
            "Nothing here was written for you by a model: these are the edition's own sources, matched to "
            "your holdings.",
        ],
    }
