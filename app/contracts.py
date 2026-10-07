"""Federal contract awards, from USAspending.

**The source.** api.usaspending.gov, the government's own system of record for
federal awards, fed by FPDS. Free, no key, no vendor in the path -- the same
terms as the House Clerk's filings behind app/analytics/congress.py.

**What it can and cannot serve, measured rather than assumed.** A market-wide
window of recent awards answers in about 0.6s and is the access pattern this
module is built on. A per-recipient search by NAME times out: every attempt at
`recipient_search_text: ["Lockheed Martin"]` returned 504 after 60s, at every
window width tried. By UEI the same query answers in under a second, so a
company lookup here is always two calls -- resolve the recipient, then ask for
its awards by identifier.

Field choice is a cost decision too. `Recipient UEI` is 0.6s, `Place of
Performance` 0.6s, `recipient_id` 0.6s -- but `NAICS` measured 54.7s, `Last
Modified Date` 58s, and `Total Outlays` 502'd outright. The field list below is
the cheap set and should not be extended without timing the addition.

**The matching rule, and why it is strict.** Recipient names are free text and
the search is a keyword search. Asked for "Apple" it ranks MAYER BROS. APPLE
PRODUCTS INC. above anything Apple Inc. has ever been awarded, and asked for
Northrop it will happily return a plumbing contractor with Northrop in its
name. Putting a juice company's federal contracts under AAPL is the same class
of failure as drawing one company's bars under another's name, which this
codebase has a written rule about.

So a match is accepted only when the recipient's name, stripped of corporate
suffixes, EQUALS the company's legal name stripped the same way. Anything less
certain reports no match, which is the correct answer for most listed
companies: the overwhelming majority of federal contractors are private, and a
page that invented a link would be wrong far more often than it was useful.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

log = logging.getLogger("uvicorn.error")

BASE = "https://api.usaspending.gov/api/v2"
AWARD_SEARCH = BASE + "/search/spending_by_award/"
RECIPIENT_SEARCH = BASE + "/recipient/"

# Contract award types only: A/B/C/D are the definitive contract families.
# Grants, loans and direct payments are a different question and would put
# university research money next to a defence award under one heading.
CONTRACT_TYPES = ["A", "B", "C", "D"]

# The cheap fields. See the module docstring before adding to this.
# `Base Obligation Date` is the day the award was signed, which is what a list
# of new awards is ordered by: `Start Date` is when the work begins and can be
# months away, so a list dated by it put a December start at the top of
# September's awards. Timed 2026-10-07: 0.57s market-wide and 0.64s by UEI,
# against 0.74s without it.
FIELDS = [
    "Award ID", "Recipient Name", "Awarding Agency", "Awarding Sub Agency",
    "Award Amount", "Start Date", "End Date", "Description",
    "Contract Award Type", "Place of Performance State Code",
    "Base Obligation Date",
]

TIMEOUT = 25.0
# Long, because the answer moves on the scale of days and the call is slow and
# occasionally refuses. A reader who reloads should not re-ask a federal API.
TTL = 3600.0

_LOCK = threading.RLock()
_CACHE: Dict[str, Dict[str, Any]] = {}


# Corporate suffixes, dropped from both sides before names are compared.
#
# "Lockheed Martin Corporation" and "LOCKHEED MARTIN CORP" are the same company
# written two ways, and neither the filer nor the exchange is consistent about
# which. Stripping them is what makes an EQUALITY test usable; without it the
# test is so strict it matches nothing and the feature silently never works.
SUFFIXES = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LLC",
    "LP", "LLP", "PLC", "LTD", "LIMITED", "HOLDINGS", "HOLDING", "GROUP",
    "THE", "AND", "NV", "SA", "AG", "CLASS", "COM", "TRUST", "PARTNERS",
}


def normalise(name: Any) -> str:
    """A company name reduced to the part that identifies it."""
    cleaned = re.sub(r"[^A-Z0-9 ]", " ", str(name or "").upper())
    return " ".join(w for w in cleaned.split() if w and w not in SUFFIXES)


def _post(url: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One call, or None. Never raises.

    Every caller here has a panel to draw either way, and this API refuses
    often enough -- 504s under load, 502s on an expensive field -- that an
    exception would be the common case rather than the exceptional one.
    """
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 # Named, because this is a public government API and an
                 # anonymous client is the one that gets rate-limited first.
                 "User-Agent": "optic-terminal (theopticterminal.com)"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.load(resp)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        log.info("usaspending %s unavailable: %s", url.rsplit("/", 2)[-2], exc)
        return None


def _cached(key: str, build):
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and (time.time() - hit["at"]) < TTL:
            return hit["data"]
    out = build()
    # A failure is cached too, briefly, by storing it with a past timestamp --
    # so a federal API that is down does not get one call per page view, but
    # does get retried well before the hour a success would hold for.
    with _LOCK:
        _CACHE[key] = {"at": time.time() if out.get("available") else time.time() - TTL + 120,
                       "data": out}
    return out


def _award_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    """One award, in this app's own vocabulary."""
    return {
        "award_id": raw.get("Award ID"),
        "recipient": raw.get("Recipient Name"),
        "agency": raw.get("Awarding Agency"),
        "sub_agency": raw.get("Awarding Sub Agency"),
        "amount": raw.get("Award Amount"),
        "awarded": raw.get("Base Obligation Date"),
        "start": raw.get("Start Date"),
        "end": raw.get("End Date"),
        "description": (raw.get("Description") or "").strip() or None,
        "kind": raw.get("Contract Award Type"),
        "state": raw.get("Place of Performance State Code"),
        # The award's own page on USAspending, so a reader can check it.
        "url": ("https://www.usaspending.gov/award/"
                + str(raw.get("generated_internal_id") or "")) if raw.get("generated_internal_id") else None,
    }


def _newest_first(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The largest awards, listed by the day each was signed, newest first.

    The API is asked for the largest, because a list of the most recent would
    be a page of $30k purchase orders. Shown in date order, because a reader
    scans awards as a timeline, and largest-first dated them 23, 26, 11, 25
    and 22 September down the page. ISO dates sort as strings; an award with
    no date goes last.
    """
    return sorted(rows, key=lambda r: str(r.get("awarded") or r.get("start") or ""),
                  reverse=True)


CAVEAT = ("Obligated amounts on prime contract awards, as reported to FPDS. An "
          "award is what the government committed, not what has been paid, and "
          "the figure covers the whole contract rather than a year of it. "
          "Subcontracts are not here: a defence prime's award does not show the "
          "suppliers under it.")


def recent(limit: int = 12, days: int = 30) -> Dict[str, Any]:
    """The largest federal contract awards in the last `days`, market-wide.

    No recipient filter, which is the access pattern this API serves well:
    measured at 0.6s against the 504s a name filter produces. This is the
    default view because most federal contractors are private companies, so a
    page that only worked for a matched ticker would be blank most of the time
    and would imply there was nothing to see.
    """
    def build() -> Dict[str, Any]:
        today = time.strftime("%Y-%m-%d")
        start = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))
        got = _post(AWARD_SEARCH, {
            "filters": {
                "award_type_codes": CONTRACT_TYPES,
                # new_awards_only, or a long-running contract's routine
                # modification reappears every time it is touched and the list
                # becomes a log of paperwork rather than of awards.
                "time_period": [{"start_date": start, "end_date": today,
                                 "date_type": "new_awards_only"}],
            },
            "fields": FIELDS, "sort": "Award Amount", "order": "desc",
            "limit": max(1, min(limit, 50)), "page": 1,
        })
        if not got:
            return {"available": False,
                    "reason": "USAspending did not answer just now.",
                    "source": "https://www.usaspending.gov/"}
        rows = _newest_first([_award_row(r) for r in (got.get("results") or [])])
        return {"available": True, "awards": rows, "days": days,
                "scope": "market", "caveat": CAVEAT,
                "source": "https://www.usaspending.gov/"}

    return _cached("recent:%d:%d" % (limit, days), build)


def _resolve(legal_name: str) -> Optional[Dict[str, Any]]:
    """The recipient this company files as, or None if it is not certain.

    Two rules, and the second is the one that matters. Prefer a PARENT record,
    because a company's awards are spread across its subsidiaries and the
    parent is the roll-up. And accept nothing whose normalised name is not
    EQUAL to the company's -- see the module docstring for what a keyword
    search returns for "Apple".
    """
    want = normalise(legal_name)
    if not want or len(want) < 3:
        return None
    got = _post(RECIPIENT_SEARCH, {"keyword": want, "award_type": "contracts",
                                   "limit": 10, "page": 1,
                                   "order": "desc", "sort": "amount"})
    if not got:
        return None
    exact = [r for r in (got.get("results") or []) if normalise(r.get("name")) == want]
    if not exact:
        return None
    parents = [r for r in exact if r.get("recipient_level") == "P"]
    return (parents or exact)[0]


def for_company(legal_name: str, ticker: str = "", limit: int = 12) -> Dict[str, Any]:
    """What one listed company has been awarded, or an honest absence.

    Three outcomes and they are different things, so they are reported
    differently: a confident match with awards, a confident match with none,
    and no confident match at all. Collapsing the last two into "no contracts"
    would tell a reader that Apple has no federal business when what actually
    happened is that this module declined to guess which recipient it is.
    """
    def build() -> Dict[str, Any]:
        who = _resolve(legal_name)
        if not who:
            return {"available": True, "matched": False, "scope": "company",
                    "ticker": ticker.upper(), "awards": [],
                    "reason": ("No federal contractor files under this company's "
                               "name. Most listed companies do not, and the "
                               "match has to be exact: a keyword search would "
                               "return a different firm with a similar name."),
                    "caveat": CAVEAT, "source": "https://www.usaspending.gov/"}
        # By UEI. See the module docstring: by name this call times out.
        got = _post(AWARD_SEARCH, {
            "filters": {"recipient_search_text": [who["uei"]],
                        "award_type_codes": CONTRACT_TYPES},
            "fields": FIELDS, "sort": "Award Amount", "order": "desc",
            "limit": max(1, min(limit, 50)), "page": 1,
        })
        if got is None:
            return {"available": False, "scope": "company", "ticker": ticker.upper(),
                    "reason": "USAspending matched the company but did not return its awards.",
                    "recipient": who.get("name"), "caveat": CAVEAT,
                    "source": "https://www.usaspending.gov/"}
        return {
            "available": True, "matched": True, "scope": "company",
            "ticker": ticker.upper(),
            "recipient": who.get("name"),
            "uei": who.get("uei"),
            "level": who.get("recipient_level"),
            # The number the recipient search ranks on, which is the last
            # twelve months of contract obligations: with award_type
            # "contracts" the endpoint reads its `last_12_contracts` column
            # (usaspending-api recipient/v2/lookups.py). It was called the
            # lifetime total and printed "in all", which put Lockheed Martin's
            # $46.7B "in all" above a single $48.1B award of its own from 1993.
            "amount_12m": who.get("amount"),
            "awards": _newest_first([_award_row(r) for r in (got.get("results") or [])]),
            "caveat": CAVEAT,
            "source": "https://www.usaspending.gov/",
        }

    return _cached("company:%s:%d" % (normalise(legal_name), limit), build)
