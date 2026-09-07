"""Outside-world feed layer: polite HTTP, RSS *and* Atom parsing, cached.

Everything the daily brief knows that isn't computed from price data arrives
through here. Three rules shape the whole module.

**Primary sources wherever one exists.** Company news comes from SEC EDGAR — the
8-K filing itself, with its item codes — rather than an article about the filing.
Macro comes from the Federal Reserve, the BLS and the BEA. That is both better
data and a cleaner copyright position: a filing is a public record, and an item
code is a fact rather than someone's prose.

**Headline, source and link only.** Nothing in this module stores or forwards
article bodies. `summary` is deliberately capped hard and exists so a card isn't
a bare headline; anything longer belongs to the publisher, and the link is how a
reader gets it. See app/legal.py for how that's surfaced.

**One dead feed must never break the brief.** Sources go down, rename their
paths, and rate-limit. Every fetch is individually wrapped, failures are recorded
rather than raised, and the brief renders with whatever legs are standing.
Saying which ones aren't.

Parsing is stdlib ElementTree rather than feedparser, to avoid a dependency for
what is two element names. Both dialects are handled because the sources are
mixed in practice: BBC and CNN are RSS `<item>`, the BLS is Atom `<entry>`, and
assuming RSS silently yields zero rows on half the set.
"""

from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
CACHE_PATH = os.path.join(_DATA_DIR, "feed_cache.json")

# The SEC requires automated callers to identify themselves with a contact
# address, and enforces it: measured against sec.gov, a User-Agent containing an
# email returns 200 from /Archives while one without returns 403. The full-text
# search endpoint is laxer and answers either way, which is a good way to ship
# something that works until the day it needs a document.
#
# No address is hard-coded, because this repository is public. Set FEED_CONTACT in
# .env (gitignored) to an address you're willing to be contacted on.
CONTACT = os.environ.get("FEED_CONTACT", "").strip()
USER_AGENT = f"OpticTerminal/1.0 ({CONTACT})" if CONTACT else "OpticTerminal/1.0"
# Whether we can expect /Archives to answer. Surfaced in the brief's status so a
# missing contact shows up as configuration rather than as a broken section.
CONTACT_OK = "@" in CONTACT

TIMEOUT_SECONDS = float(os.environ.get("FEED_TIMEOUT", "12"))
# Feeds are polled per-server, not per-visitor. Fifteen minutes is far inside
# every source's tolerance while still being fresh enough for a daily brief.
CACHE_TTL_SECONDS = int(os.environ.get("FEED_CACHE_MINUTES", "15")) * 60
# Successive requests to the same host, so a rebuild doesn't arrive as a burst.
POLITE_GAP_SECONDS = float(os.environ.get("FEED_POLITE_GAP", "0.6"))

_ATOM = "{http://www.w3.org/2005/Atom}"

_LOCK = threading.RLock()
_MEM: Dict[str, Dict[str, Any]] = {}
_LAST_HIT: Dict[str, float] = {}

# ---------------------------------------------------------------- source table

# `kind` selects the section a source feeds; `weight` breaks ties when a section
# has more entries than it can show, so the wire services don't crowd out the
# central bank.
SOURCES: List[Dict[str, Any]] = [
    # -- macro: statistical agencies and the central bank, all primary ---------
    {"id": "fed-monetary", "name": "Federal Reserve", "detail": "Monetary policy",
     "kind": "macro", "weight": 10,
     "url": "https://www.federalreserve.gov/feeds/press_monetary.xml"},
    {"id": "fed-press", "name": "Federal Reserve", "detail": "All press releases",
     "kind": "macro", "weight": 7,
     "url": "https://www.federalreserve.gov/feeds/press_all.xml"},
    {"id": "bls-cpi", "name": "Bureau of Labor Statistics", "detail": "Consumer prices",
     "kind": "macro", "weight": 9,
     "url": "https://www.bls.gov/feed/cpi.rss"},
    {"id": "bls-empsit", "name": "Bureau of Labor Statistics", "detail": "Employment",
     "kind": "macro", "weight": 9,
     "url": "https://www.bls.gov/feed/empsit.rss"},
    {"id": "bls-ppi", "name": "Bureau of Labor Statistics", "detail": "Producer prices",
     "kind": "macro", "weight": 8,
     "url": "https://www.bls.gov/feed/ppi.rss"},
    {"id": "bea", "name": "Bureau of Economic Analysis", "detail": "GDP and income",
     "kind": "macro", "weight": 8,
     "url": "https://apps.bea.gov/rss/rss.xml"},
    {"id": "sec-press", "name": "SEC", "detail": "Press releases",
     "kind": "macro", "weight": 6,
     "url": "https://www.sec.gov/news/pressreleases.rss"},

    # Added after probing, not on reputation. Every one of these was fetched
       # and parsed with this module's own code before it went in; the twelve
       # candidates that failed are listed under REJECTED_SOURCES below with the
       # reason, so nobody re-adds them on the strength of the name.
    # A speech is frequently the policy news, and the press-release feed does
    # not carry them: the decision arrives in a statement, the reasoning and the
    # next move arrive in a speech two days later.
    {"id": "fed-speeches", "name": "Federal Reserve", "detail": "Speeches",
     "kind": "macro", "weight": 9,
     "url": "https://www.federalreserve.gov/feeds/speeches.xml"},
    # Retail sales, durable goods, housing starts, trade balance. All of these
    # were being read second-hand off a wire; Census publishes them itself.
    {"id": "census-eco", "name": "Census Bureau", "detail": "Economic indicators",
     "kind": "macro", "weight": 8,
     "url": "https://www.census.gov/economic-indicators/indicator.xml"},
    # The other side of the Atlantic sets the dollar as much as the Fed does.
    {"id": "ecb-press", "name": "European Central Bank", "detail": "Press",
     "kind": "macro", "weight": 7,
     "url": "https://www.ecb.europa.eu/rss/press.html"},
    # Primary energy data. OilPrice is commentary on this.
    {"id": "eia-today", "name": "EIA", "detail": "Today in energy",
     "kind": "macro", "weight": 7,
     "url": "https://www.eia.gov/rss/todayinenergy.xml"},
    # Research rather than news, and the reason it is here: it is the Fed's own
    # staff arguing about the data in public, months before it reaches a speech.
    {"id": "nyfed-research", "name": "New York Fed", "detail": "Liberty Street Economics",
     "kind": "macro", "weight": 6,
     "url": "https://libertystreeteconomics.newyorkfed.org/feed/"},
    {"id": "cbo", "name": "Congressional Budget Office", "detail": "Publications",
     "kind": "macro", "weight": 5,
     "url": "https://www.cbo.gov/publications/all/rss.xml"},

    # -- wires, grouped into desks by `sector` ---------------------------------
    #
    # CNN is deliberately absent. Its public RSS feeds are abandoned: measured on
    # 2026-08-04, the newest item in edition_world was 2.9 years old, and
    # money_news_international and edition_technology were both ~9.5 years old.
    # They were in this table and cost four HTTP requests a cycle to contribute
    # nothing — every item fell outside the freshness window, which is the only
    # reason no reader ever saw a 2017 headline presented as today's news.
    # Reinstate only against a fresh-dates check, not on the strength of the brand.
    {"id": "cnbc-top", "name": "CNBC", "detail": "Top news",
     "kind": "wire", "sector": "markets", "weight": 9,
     "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
    {"id": "cnbc-markets", "name": "CNBC", "detail": "Markets",
     "kind": "wire", "sector": "markets", "weight": 9,
     "url": "https://www.cnbc.com/id/15839069/device/rss/rss.html"},
    {"id": "mw-top", "name": "MarketWatch", "detail": "Top stories",
     "kind": "wire", "sector": "markets", "weight": 8,
     "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories"},
    {"id": "bbc-business", "name": "BBC News", "detail": "Business",
     "kind": "wire", "sector": "markets", "weight": 7,
     "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},

    # Energy and commodities. Oil is the shortest path from a geopolitical event to
    # an inflation print to a Fed expectation, so it belongs on a terminal that
    # already scores a macro regime — and the desk grid was an odd number, leaving
    # World alone in a two-column row with a dead cell beside it.
    {"id": "cnbc-energy", "name": "CNBC", "detail": "Energy",
     "kind": "wire", "sector": "energy", "weight": 8,
     "url": "https://www.cnbc.com/id/19836768/device/rss/rss.html"},
    {"id": "oilprice", "name": "OilPrice", "detail": "Oil, gas and metals",
     "kind": "wire", "sector": "energy", "weight": 7,
     "url": "https://oilprice.com/rss/main"},

    # Two sources on this desk, not one: with a 36-hour window a single economy
    # feed left the section showing one story next to four full ones, which reads
    # as a broken desk rather than a quiet one.
    {"id": "cnbc-economy", "name": "CNBC", "detail": "Economy",
     "kind": "wire", "sector": "economy", "weight": 8,
     "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"id": "cnbc-finance", "name": "CNBC", "detail": "Finance",
     "kind": "wire", "sector": "economy", "weight": 7,
     "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html"},

    {"id": "cnbc-tech", "name": "CNBC", "detail": "Technology",
     "kind": "wire", "sector": "tech", "weight": 8,
     "url": "https://www.cnbc.com/id/19854910/device/rss/rss.html"},
    {"id": "bbc-tech", "name": "BBC News", "detail": "Technology",
     "kind": "wire", "sector": "tech", "weight": 8,
     "url": "https://feeds.bbci.co.uk/news/technology/rss.xml"},

    {"id": "bbc-politics", "name": "BBC News", "detail": "Politics",
     "kind": "wire", "sector": "politics", "weight": 7,
     "url": "https://feeds.bbci.co.uk/news/politics/rss.xml"},
    {"id": "cnbc-politics", "name": "CNBC", "detail": "Politics",
     "kind": "wire", "sector": "politics", "weight": 7,
     "url": "https://www.cnbc.com/id/10000113/device/rss/rss.html"},

    # Regulatory. The desk the brief had no equivalent of, and the one whose
       # items most often ARE the move in a single name.
       #
       # An FDA approval or complete response letter is the entire thesis for a
       # biotech; an FTC second request is the entire thesis for a merger arb. A
       # wire will report both, hours later and with the document paraphrased.
    {"id": "fda-press", "name": "FDA", "detail": "Press announcements",
     "kind": "wire", "sector": "regulatory", "weight": 9,
     "url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml"},
    {"id": "fda-drugs", "name": "FDA", "detail": "Drug approvals and safety",
     "kind": "wire", "sector": "regulatory", "weight": 8,
     "url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/drugs/rss.xml"},
    {"id": "ftc-competition", "name": "FTC", "detail": "Competition enforcement",
     "kind": "wire", "sector": "regulatory", "weight": 7,
     "url": "https://www.ftc.gov/feeds/press-release-competition.xml"},
    {"id": "cftc", "name": "CFTC", "detail": "Derivatives enforcement",
     "kind": "wire", "sector": "regulatory", "weight": 5,
     "url": "https://www.cftc.gov/RSS/RSSGP/rssgp.xml"},

    # Analysis and opinion, kept in its own desk and clearly labelled.
       #
       # The brief was entirely reported news, which answers "what happened" and
       # never "what does anyone think it means". Op-eds and long-form analysis
       # are the other half of reading a market, and mixing them into the wire
       # desks would have blurred the one distinction that matters about them:
       # these are arguments, not events. Headline and link only, as everywhere
       # else in this module — the argument belongs to whoever wrote it.
    {"id": "economist-fin", "name": "The Economist", "detail": "Finance and economics",
     "kind": "wire", "sector": "analysis", "weight": 8,
     "url": "https://www.economist.com/finance-and-economics/rss.xml"},
    {"id": "ft-home", "name": "Financial Times", "detail": "Top stories",
     "kind": "wire", "sector": "analysis", "weight": 8,
     "url": "https://www.ft.com/rss/home"},
    # Healthcare and pharma reporting at a depth the general wires do not reach,
    # which matters because a third of the S&P's single-name volatility is a
    # clinical readout or a label change.
    {"id": "statnews", "name": "STAT", "detail": "Health and pharma",
     "kind": "wire", "sector": "analysis", "weight": 7,
     "url": "https://www.statnews.com/feed/"},

    # WSJ markets alongside CNBC and MarketWatch on the existing desk.
    {"id": "wsj-markets", "name": "WSJ", "detail": "Markets",
     "kind": "wire", "sector": "markets", "weight": 9,
     "url": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain"},

    {"id": "bbc-world", "name": "BBC News", "detail": "World",
     "kind": "wire", "sector": "world", "weight": 9,
     "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"id": "bbc-scienv", "name": "BBC News", "detail": "Science and environment",
     "kind": "wire", "sector": "world", "weight": 5,
     "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"},
]

# The desks, in the order they appear on the page. Kept here rather than in the
# frontend so a new source can only ever land in a section that exists.
SECTOR_ORDER = ["markets", "regulatory", "analysis", "energy", "economy",
                "tech", "politics", "world"]
SECTOR_LABELS = {
    "markets": "Markets",
    "regulatory": "Regulators & Agencies",
    "analysis": "Analysis & Opinion",
    "energy": "Energy & Commodities",
    "economy": "Economy",
    "tech": "Technology",
    "politics": "Politics",
    "world": "World",
}

# Candidates that were probed and did NOT make it, with the measured reason.
#
# Kept as a record for the same reason the CNN note above is kept: without it,
# every one of these is a plausible-sounding suggestion that costs another round
# of HTTP requests to rediscover. Re-add only against a fresh probe, never on
# the strength of the name. Measured 2026-09-07 with this module's own fetcher.
REJECTED_SOURCES: Dict[str, str] = {
    "https://www.federalreserve.gov/feeds/testimony.xml":
        "live but slow: newest item 55 days old, so it would never clear the "
        "brief's freshness window. Testimony is episodic, not a feed.",
    "https://home.treasury.gov/rss/press.xml": "404",
    "https://www.bankofengland.co.uk/rss/news":
        "50 rows, newest 11 days old. Outside the window.",
    "https://www.justice.gov/feeds/opa/justice-news.xml": "404",
    "https://feeds.reuters.com/reuters/businessNews":
        "DNS does not resolve. Reuters withdrew public RSS.",
    "https://rsshub.app/apnews/topics/business": "403",
    "https://feeds.content.dowjones.io/public/rss/RSSBarronsTopStories": "404",
    "https://www.piie.com/rss/research-and-analysis": "404",
    "https://www.brookings.edu/topic/economics/feed/":
        "returns a body that is not well-formed XML",
    "https://cepr.org/voxeu/rss.xml": "403",
    "https://www.imf.org/en/Blogs/rss": "403",
    "https://www.bis.org/doclist/all_rss.rss": "404",
    "https://feeds.content.dowjones.io/public/rss/RSSOpinion":
        "live, fresh, and briefly shipped on the Analysis desk before being "
        "removed. It is WSJ's general op-ed page, not a markets one: on the "
        "day it went in it took all six desk slots with a piece on a "
        "daughter's last first day of school, two on court packing and foreign "
        "university donations, and a readers' letters column. Capping it to "
        "half a desk limited the damage without fixing the source. There is no "
        "finance-only WSJ opinion feed to point at instead.",
    "https://seekingalpha.com/market_currents.xml":
        "live and fresh, deliberately excluded. It is the one candidate with no "
        "editorial accountability behind it, and this module's first rule is "
        "primary sources.",
}

SOURCE_BY_ID = {s["id"]: s for s in SOURCES}


# ------------------------------------------------------------------- utilities

def _clean(text: Optional[str]) -> str:
    """Strip tags and collapse whitespace. Feed descriptions carry HTML."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " "))
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    """RSS uses RFC 2822, Atom uses ISO 8601, and neither is guaranteed."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed is not None:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    text = raw.replace("Z", "+00:00")
    # Python 3.9's fromisoformat is strict about fractional seconds and offsets.
    for candidate in (text, text[:19], text[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _fetch(url: str, accept: str, user_agent: Optional[str] = None) -> bytes:
    """One HTTP GET, throttled per host.

    `user_agent` overrides the module default, and one caller genuinely needs it.
    Measured: FRED hangs until timeout on a request carrying our contact
    User-Agent (40s, no response) and answers in 0.2s with urllib's default.
    SEC is the mirror image — it returns 403 WITHOUT a contact address. So the
    header cannot be one global value; it belongs to the host.
    """
    host = urlparse(url).netloc or url
    with _LOCK:
        last = _LAST_HIT.get(host, 0.0)
        wait = POLITE_GAP_SECONDS - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    headers = {"Accept": accept,
        # Some CDNs serve a cached stub to callers that don't ask for fresh.
        "Cache-Control": "no-cache"}
    # An explicit empty string means "send no User-Agent header at all", which is
    # what FRED wants; None means use the module default.
    if user_agent is None:
        headers["User-Agent"] = USER_AGENT
    elif user_agent:
        headers["User-Agent"] = user_agent
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read()
    finally:
        with _LOCK:
            _LAST_HIT[host] = time.time()


# ------------------------------------------------------------------ disk cache

def cached_json(key: str) -> Any:
    """Any cached copy for this key, however old, or None.

    For sources that fail hard and change slowly. SEC rate-limits aggressively.
    A burst of requests earns a 403 for a while — and eighteen years of filed
    quarterly results do not go stale in a day. Serving the last good copy is
    strictly better than dropping the feature, provided the caller says so.
    """
    hit = _MEM.get(key) or _load_disk().get(key)
    return (hit or {}).get("json")


def fetch_json(url: str, ttl_seconds: float, key: Optional[str] = None) -> Any:
    """Cached JSON GET, sharing the polite fetch and the disk cache.

    Its own TTL rather than the module's feed TTL, because these are different
    kinds of resource: EDGAR's ticker directory changes when a company lists, and
    caching that for fifteen minutes would be pointless traffic against an agency
    that asks callers to be considerate. Raises on failure — the caller decides
    whether a missing block is fatal, which for a per-ticker panel it is not.
    """
    cache_key = key or ("json:" + url)
    now = time.time()
    with _LOCK:
        hit = _MEM.get(cache_key)
    if hit is None:
        hit = _load_disk().get(cache_key)
    if hit and (now - float(hit.get("at", 0))) < ttl_seconds and hit.get("json") is not None:
        return hit["json"]

    body = _fetch(url, "application/json, text/json, */*")
    parsed = json.loads(body.decode("utf-8", "replace"))
    _store(cache_key, {"at": now, "json": parsed, "error": None})
    return parsed


def fetch_text(url: str, ttl_seconds: float, key: Optional[str] = None,
               user_agent: Optional[str] = None) -> str:
    """Cached plain-text GET, sharing the polite fetch and the disk cache.

    Separate from fetch_json because FRED serves CSV: parsing it as JSON would
    fail, and asking each caller to decode bytes would spread the encoding
    decision around the codebase.
    """
    cache_key = key or ("text:" + url)
    now = time.time()
    with _LOCK:
        hit = _MEM.get(cache_key)
    if hit is None:
        hit = _load_disk().get(cache_key)
    if hit and (now - float(hit.get("at", 0))) < ttl_seconds and hit.get("text") is not None:
        return hit["text"]

    body = _fetch(url, "text/csv, text/plain, */*", user_agent=user_agent)
    text = body.decode("utf-8", "replace")
    _store(cache_key, {"at": now, "text": text, "error": None})
    return text


def _load_disk() -> Dict[str, Any]:
    try:
        with open(CACHE_PATH) as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_disk(payload: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        tmp = CACHE_PATH + ".tmp"
        with open(tmp, "w") as handle:
            json.dump(payload, handle)
        os.replace(tmp, CACHE_PATH)
    except OSError:
        # A read-only or missing data dir must not take the brief down; the
        # in-memory cache still does its job for the life of the process.
        pass


def _cached(key: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        entry = _MEM.get(key)
    if entry is None:
        disk = _load_disk().get(key)
        if isinstance(disk, dict):
            entry = disk
            with _LOCK:
                _MEM[key] = disk
    if not entry:
        return None
    if time.time() - float(entry.get("at", 0)) > CACHE_TTL_SECONDS:
        return None
    return entry


def _store(key: str, entry: Dict[str, Any]) -> None:
    with _LOCK:
        _MEM[key] = entry
    disk = _load_disk()
    disk[key] = entry
    # Keep the file from growing without bound if source ids ever change.
    if len(disk) > 60:
        for stale in sorted(disk, key=lambda k: disk[k].get("at", 0))[:len(disk) - 60]:
            disk.pop(stale, None)
    _save_disk(disk)


# ---------------------------------------------------------------- feed parsing

def parse_feed(body: bytes) -> List[Dict[str, Any]]:
    """Rows out of an RSS or Atom document. Unknown dialects yield nothing."""
    root = ET.fromstring(body)
    rows: List[Dict[str, Any]] = []

    for item in root.findall(".//item"):          # RSS 2.0
        link = item.findtext("link") or ""
        if not link:
            guid = item.findtext("guid") or ""
            link = guid if guid.startswith("http") else ""
        rows.append({
            "title": _clean(item.findtext("title")),
            "url": link.strip(),
            "summary": _clean(item.findtext("description"))[:280],
            "published": _parse_date(item.findtext("pubDate")
                                     or item.findtext("{http://purl.org/dc/elements/1.1/}date")),
        })

    for entry in root.findall(f".//{_ATOM}entry"):  # Atom
        link = ""
        for node in entry.findall(f"{_ATOM}link"):
            rel = node.get("rel") or "alternate"
            if rel == "alternate" and node.get("href"):
                link = node.get("href", "")
                break
        if not link:
            first = entry.find(f"{_ATOM}link")
            link = (first.get("href") or "") if first is not None else ""
        rows.append({
            "title": _clean(entry.findtext(f"{_ATOM}title")),
            "url": link.strip(),
            "summary": _clean(entry.findtext(f"{_ATOM}summary")
                              or entry.findtext(f"{_ATOM}content"))[:280],
            "published": _parse_date(entry.findtext(f"{_ATOM}updated")
                                     or entry.findtext(f"{_ATOM}published")),
        })

    return [r for r in rows if r["title"]]


def load_source(source: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    """One source's entries, cached. Never raises: failure is a returned field."""
    key = f"src:{source['id']}"
    if not force:
        hit = _cached(key)
        if hit is not None:
            return {**hit, "cached": True}

    started = time.time()
    try:
        body = _fetch(source["url"], "application/rss+xml, application/atom+xml, text/xml, */*")
        rows = parse_feed(body)
        entries = [{
            "title": r["title"], "url": r["url"], "summary": r["summary"],
            "published": r["published"].astimezone(timezone.utc).isoformat() if r["published"] else None,
            "source": source["name"], "source_detail": source.get("detail", ""),
            "source_id": source["id"],
        } for r in rows]
        entry = {"at": time.time(), "entries": entries, "error": None,
                 "ms": int((time.time() - started) * 1000)}
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout,
            ET.ParseError, ValueError, OSError) as exc:
        # Keep the previous good payload if there is one, even if it's stale — a
        # source that just started 404ing is better represented by yesterday's
        # headlines plus a warning than by a blank section.
        stale = _MEM.get(key) or _load_disk().get(key) or {}
        entry = {"at": stale.get("at", 0), "entries": stale.get("entries", []),
                 "error": f"{type(exc).__name__}: {str(exc)[:120]}",
                 "ms": int((time.time() - started) * 1000)}
        with _LOCK:
            _MEM[key] = entry
        return {**entry, "cached": False, "stale": bool(stale.get("entries"))}

    _store(key, entry)
    return {**entry, "cached": False}


def load_kind(kind: str, force: bool = False, sector: Optional[str] = None
              ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Every entry for a section, newest first, plus a per-source status list.

    `sector` narrows a kind to one desk. Sources are cached per source, so asking
    for five sectors separately costs the same fetches as asking for all of them.
    """
    entries: List[Dict[str, Any]] = []
    status: List[Dict[str, Any]] = []
    for source in SOURCES:
        if source["kind"] != kind:
            continue
        if sector is not None and source.get("sector") != sector:
            continue
        result = load_source(source, force=force)
        weight = source.get("weight", 5)
        for row in result.get("entries", []):
            entries.append({**row, "weight": weight, "sector": source.get("sector")})
        status.append({
            "id": source["id"], "name": source["name"], "detail": source.get("detail", ""),
            "count": len(result.get("entries", [])), "error": result.get("error"),
            "stale": bool(result.get("stale")), "cached": bool(result.get("cached")),
        })
    entries.sort(key=lambda r: (r.get("published") or "", r.get("weight", 0)), reverse=True)
    return entries, status


# Evergreen index pages that arrive in a news feed.
#
# The FDA's drug feed republishes its own navigation alongside actual
# announcements: "What's New Related to Drugs", "Newly Added Guidance
# Documents", "Oncology Approval Notifications". Each is a standing page with a
# fresh timestamp, so it clears every freshness check and reads on the page as
# though something happened. On the day the regulatory desk was added, three of
# its six items were these — half a desk of table of contents.
#
# Matched on the title rather than the URL because the same page is reachable at
# several paths. Deliberately a short, specific list: a generic "looks like an
# index" heuristic would eventually eat a real announcement.
EVERGREEN_TITLES = (
    "what's new related to drugs",
    "newly added guidance documents",
    "approval notifications",
    "drug safety-related labeling changes",
    "drug shortages",
    "recalls, market withdrawals",
    "press announcements",
)


def is_evergreen(entry: Dict[str, Any]) -> bool:
    """True for a standing page republished with a fresh date."""
    title = (entry.get("title") or "").strip().lower()
    if not title:
        return False
    return any(marker in title for marker in EVERGREEN_TITLES)


def within_hours(entries: List[Dict[str, Any]], hours: int) -> List[Dict[str, Any]]:
    """Entries published inside a window. Undated entries are kept — a release
    with no timestamp is more likely a parsing gap than something ancient."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for row in entries:
        # Dropped here rather than in the parser: an evergreen page is valid
        # feed content, it is just not news, and this is the gate every desk
        # already passes through.
        if is_evergreen(row):
            continue
        stamp = _parse_date(row.get("published"))
        if stamp is None or stamp >= cutoff:
            out.append(row)
    return out


def dedupe(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Same story from two feeds — BBC World and BBC Business overlap daily."""
    seen = set()
    out = []
    for row in entries:
        key = re.sub(r"[^a-z0-9]+", "", (row.get("title") or "").lower())[:70]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


# --------------------------------------------------------------- SEC filings

"""8-K item codes.

This table is why company news in the brief comes from EDGAR rather than a wire.
An item code is the filer's own statement of what the filing is about. The
company saying "this is a results release" or "this is a merger agreement". So
categorising on it involves no guesswork about someone's headline.

`weight` orders the section. 9.01 is deliberately weightless: it is the exhibit
index, present on two thirds of all filings, and a filing carrying only 9.01 is
paperwork rather than news.
"""
ITEM_LABELS: Dict[str, Tuple[str, int]] = {
    "1.01": ("Material agreement", 8),
    "1.02": ("Agreement terminated", 7),
    "1.03": ("Bankruptcy or receivership", 10),
    "1.05": ("Cybersecurity incident", 9),
    "2.01": ("Acquisition or disposal completed", 9),
    "2.02": ("Earnings / results", 9),
    "2.03": ("New debt obligation", 5),
    "2.04": ("Obligation accelerated", 8),
    "2.05": ("Restructuring costs", 6),
    "2.06": ("Material impairment", 8),
    "3.01": ("Delisting notice", 8),
    "3.02": ("Unregistered share sale", 5),
    "3.03": ("Shareholder rights modified", 5),
    "4.01": ("Auditor change", 7),
    "4.02": ("Financials not to be relied on", 10),
    "5.01": ("Change of control", 9),
    "5.02": ("Management change", 6),
    "5.03": ("Charter or bylaw amendment", 3),
    "5.07": ("Shareholder vote", 3),
    "7.01": ("Guidance / Reg FD disclosure", 7),
    "8.01": ("Other announcement", 4),
    "9.01": ("Exhibits", 0),
}

# Which headline group a filing belongs to, for the themed rows the brief shows.
ITEM_GROUPS: Dict[str, str] = {
    "2.02": "earnings",
    "7.01": "guidance",
    "1.01": "deals", "1.02": "deals", "2.01": "deals", "5.01": "deals",
    "5.02": "management",
    "1.03": "distress", "2.04": "distress", "2.06": "distress",
    "3.01": "distress", "4.02": "distress",
}

EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
# 60 was sized when this section pulled one form. Twelve forms need more room
# before the per-form share is large enough to be worth reading — at 60 the
# lightest forms were down to a floor of two rows each.
FILINGS_LIMIT = int(os.environ.get("BRIEF_FILINGS_LIMIT", "96"))

_TICKER_RE = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,6})\)\s*\(CIK")


# The filing types the brief pulls, and what each one is.
#
# This was `forms=8-K` and nothing else, which is material events only — a
# terminal that could tell you a company had announced something and never that
# an activist had taken 6% of it, that a shelf had been priced into the float,
# or what the annual report actually said.
#
# `SCHEDULE 13D` is spelled out for a reason worth recording: EDGAR full-text
# search does not recognise `SC 13D`, the name the form is universally called
# and the one the filing index itself uses. Queried that way it returns zero
# hits and looks like a quiet week. `SCHEDULE 13D` returns 79 in seven days.
# The same trap applies to `SC 13D/A` — amendments come back under the spelled
# form, so they arrive with the parent rather than needing their own query.
#
# Weight orders the section when several land the same day. An activist stake
# outranks a proxy statement; a priced offering outranks a shelf registration
# that may never be drawn on.
FILING_FORMS: List[Dict[str, Any]] = [
    {"form": "SCHEDULE 13D", "label": "Activist stake (13D)", "weight": 10,
     "note": "A holder above 5% declaring intent to influence. Filed within 5 days."},
    {"form": "8-K", "label": "Material event (8-K)", "weight": 9, "items": True,
     "note": "The catch-all for anything material between quarterly reports."},
    {"form": "SC 14D9", "label": "Tender offer response", "weight": 9,
     "note": "The board's answer to a tender offer. Recommends for or against."},
    {"form": "425", "label": "Merger communication", "weight": 8,
     "note": "A written communication about a proposed business combination."},
    {"form": "424B5", "label": "Offering priced", "weight": 8,
     "note": "A takedown off a shelf, priced. This is dilution with a number on it."},
    {"form": "10-Q", "label": "Quarterly report", "weight": 7,
     "note": "The quarter's financials, with management's discussion."},
    {"form": "10-K", "label": "Annual report", "weight": 7,
     "note": "The full year, including the risk factors in the company's own words."},
    {"form": "DEF 14A", "label": "Proxy statement", "weight": 6,
     "note": "Pay, the board, and what shareholders are being asked to vote on."},
    {"form": "S-1", "label": "Registration (S-1)", "weight": 6,
     "note": "New securities registered. For an IPO this is the prospectus."},
    {"form": "S-3", "label": "Shelf registration", "weight": 5,
     "note": "Capacity to issue later. Not dilution yet, but permission for it."},
    {"form": "6-K", "label": "Foreign material event", "weight": 5,
     "note": "The 8-K equivalent for a foreign private issuer."},
    {"form": "20-F", "label": "Foreign annual report", "weight": 5,
     "note": "The 10-K equivalent for a foreign private issuer."},
]

FILING_FORM_BY_NAME = {f["form"]: f for f in FILING_FORMS}


def _filing_row(hit: Dict[str, Any],
                spec: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    src = hit.get("_source") or {}
    names = src.get("display_names") or []
    if not names:
        return None
    raw = names[0]
    ticker_match = _TICKER_RE.search(raw)
    company = re.sub(r"\s*\((?:[A-Z][A-Z0-9.\-]{0,6}|CIK \d+)\)\s*", " ", raw)
    company = re.sub(r"\s+", " ", company).strip(" ,")

    spec = spec or FILING_FORM_BY_NAME["8-K"]
    # Item codes exist on 8-K and 6-K only. For every other form the form ITSELF
    # is the news — a 13D is interesting because it is a 13D — so requiring an
    # item code would have discarded every one of them.
    if spec.get("items"):
        codes = [c for c in (src.get("items") or []) if c in ITEM_LABELS]
        # Filings whose only item is the exhibit index carry no news.
        meaningful = [c for c in codes if ITEM_LABELS[c][1] > 0]
        if not meaningful:
            return None
    else:
        meaningful = []

    cik = (src.get("ciks") or [""])[0].lstrip("0")
    adsh = src.get("adsh") or ""
    url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{adsh}-index.htm"
           if cik and adsh else "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent")

    groups = sorted({ITEM_GROUPS[c] for c in meaningful if c in ITEM_GROUPS})
    return {
        "company": company, "ticker": ticker_match.group(1) if ticker_match else None,
        "cik": cik, "accession": adsh,
        "form": spec["form"],
        "form_label": spec["label"],
        "form_note": spec.get("note", ""),
        "items": meaningful,
        "labels": [ITEM_LABELS[c][0] for c in meaningful],
        "groups": groups,
        # An item code is a finer read than the form when there is one, so it
        # wins; otherwise the form's own weight orders the row.
        "weight": (max(ITEM_LABELS[c][1] for c in meaningful)
                   if meaningful else spec["weight"]),
        "filed": src.get("file_date"),
        "url": url,
        "source": "SEC EDGAR", "source_detail": spec["label"],
    }


def load_filings(days: int = 1, force: bool = False) -> Dict[str, Any]:
    """Recent 8-K filings across every filer, categorised by item code.

    Full-text search is used rather than the `getcurrent` feed because only this
    endpoint returns the item codes, and the codes are the entire point — without
    them a filing is an untyped link and the section can't be organised at all.
    """
    key = f"filings:{days}"
    if not force:
        hit = _cached(key)
        if hit is not None:
            return {**hit, "cached": True}

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=max(0, days))
    started = time.time()

    # One request per form. Comma-separating them was tried and EDGAR's
    # full-text endpoint answers a multi-form `forms=` with zero hits rather
    # than an error, which is the worst of both — it looks like a quiet day.
    rows: List[Dict[str, Any]] = []
    total = 0
    per_form: Dict[str, Any] = {}
    failures: List[str] = []
    for spec in FILING_FORMS:
        quoted = spec["form"].replace(" ", "%20")
        url = (f"{EDGAR_SEARCH}?q=&forms={quoted}&dateRange=custom"
               f"&startdt={start.isoformat()}&enddt={today.isoformat()}")
        try:
            payload = json.loads(_fetch(url, "application/json"))
            hits = (payload.get("hits") or {}).get("hits") or []
            got = ((payload.get("hits") or {}).get("total") or {}).get("value") or 0
            built = [r for r in (_filing_row(h, spec) for h in hits) if r]
            rows.extend(built)
            total += got
            per_form[spec["form"]] = {"in_window": got, "shown": len(built)}
        except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout,
                ValueError, KeyError, OSError) as exc:
            # One form failing must not lose the other eleven — the same rule
            # the wire sources have carried from the start.
            per_form[spec["form"]] = {"in_window": None, "shown": 0,
                                      "error": f"{type(exc).__name__}"}
            failures.append(spec["form"])

    if not rows and failures:
        # Everything failed. Serve whatever is on disk and say it is stale,
        # rather than presenting an empty section as a quiet day.
        stale = _MEM.get(key) or _load_disk().get(key) or {}
        entry = {"at": stale.get("at", 0), "filings": stale.get("filings", []),
                 "matched": stale.get("matched", 0),
                 "total_in_window": stale.get("total_in_window"),
                 "per_form": stale.get("per_form", per_form),
                 "failed_forms": failures,
                 "error": "every form query failed: " + ", ".join(failures),
                 "ms": int((time.time() - started) * 1000)}
        with _LOCK:
            _MEM[key] = entry
        return {**entry, "cached": False, "stale": bool(stale.get("filings"))}

    # Every form that had news gets into the shown set.
     #
     # Sorting the merged list by date and truncating to 60 was the first
     # version and it silently undid most of the work: 369 filings came back
     # across eleven form types, the newest day was 334 8-Ks and 191 6-Ks, and
     # the 60 that survived were 8-K, 13D, 425 and 424B5 only. Every 10-K,
     # 10-Q, proxy and registration was fetched, parsed and then discarded by
     # the truncation — the section looked exactly as it had before the forms
     # were added.
     #
     # So the budget is allocated per form before the merge. Each form keeps up
     # to its share, the forms that filed nothing release theirs, and one busy
     # form can no longer crowd out the rest. Within a form it is still newest
     # first, then weight, which is what a reader scanning a section wants.
     #
    by_form: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_form.setdefault(r["form"], []).append(r)
    for group in by_form.values():
        group.sort(key=lambda r: (r.get("filed") or "", r.get("weight", 0)), reverse=True)

    # Share by weight, not evenly.
    #
    # An equal split was the second version and it over-corrected: 8-K is 334 of
    # the 698 filings in the window and the material-event form a reader scans
    # first, and it was getting the same five slots as a shelf registration.
    # Weighting the share keeps every form present while letting the important
    # ones be present in proportion. The floor of two is what guarantees the
    # long tail still appears at all.
    present = [f for f in FILING_FORMS if by_form.get(f["form"])]
    shown: List[Dict[str, Any]] = []
    if present:
        total_weight = sum(f["weight"] for f in present) or 1
        for spec in present:
            share = max(2, round(FILINGS_LIMIT * spec["weight"] / total_weight))
            shown.extend(by_form[spec["form"]][:share])
        # Any budget left by a thin form goes to the heaviest rows still unseen,
        # so a quiet day does not produce a short section.
        if len(shown) < FILINGS_LIMIT:
            seen = {id(r) for r in shown}
            spare = [r for r in rows if id(r) not in seen]
            spare.sort(key=lambda r: (r.get("weight", 0), r.get("filed") or ""),
                       reverse=True)
            shown.extend(spare[:FILINGS_LIMIT - len(shown)])

    shown.sort(key=lambda r: (r.get("filed") or "", r.get("weight", 0)), reverse=True)
    entry = {"at": time.time(), "filings": shown[:FILINGS_LIMIT],
             "matched": len(rows), "total_in_window": total,
             "per_form": per_form,
             "failed_forms": failures,
             # Named so the reader can see the section is a selection rather
             # than everything EDGAR received.
             "forms_queried": [f["form"] for f in FILING_FORMS],
             "error": None if not failures else (
                 "%d of %d form queries failed: %s"
                 % (len(failures), len(FILING_FORMS), ", ".join(failures))),
             "ms": int((time.time() - started) * 1000)}

    _store(key, entry)
    return {**entry, "cached": False}


# ------------------------------------------------------------------ wire search

def search(query: str, limit: int = 40, hours: Optional[int] = None,
           force: bool = False) -> Dict[str, Any]:
    """Search every wire and macro headline currently cached.

    Deliberately a local search, not a web search. It looks only at what the
    brief has already pulled — roughly the last few days across the sources in
    SOURCES — so a reader searching "Hormuz" gets the stories the page is built
    from and can see for themselves where each came from. There is no honest way
    to promise more than that without a paid news API, so the response reports
    the corpus it searched and the frontend says so.
    """
    terms = [t for t in re.split(r"\s+", (query or "").strip().lower()) if t]
    if not terms:
        return {"query": "", "results": [], "searched": 0, "sources": 0, "terms": []}

    rows: List[Dict[str, Any]] = []
    source_ids = set()
    for kind in ("wire", "macro"):
        entries, _status = load_kind(kind, force=force)
        for row in entries:
            rows.append({**row, "kind": kind})
            source_ids.add(row.get("source_id"))
    rows = dedupe(rows)
    if hours:
        rows = within_hours(rows, hours)

    scored = []
    for row in rows:
        title = (row.get("title") or "").lower()
        blurb = (row.get("summary") or "").lower()
        # Every term must appear somewhere, so a two-word query narrows rather
        # than widens. Title hits outrank summary hits.
        if not all(t in title or t in blurb for t in terms):
            continue
        score = sum(3 if t in title else 1 for t in terms)
        if title.startswith(terms[0]):
            score += 2
        scored.append((score, row.get("published") or "", row))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return {
        "query": query,
        "terms": terms,
        "results": [r for _s, _p, r in scored[:limit]],
        "matched": len(scored),
        "searched": len(rows),
        "sources": len(source_ids),
    }


# ---------------------------------------------------------- release calendars

def parse_ics(text: str) -> List[Dict[str, Any]]:
    """Minimal iCalendar reader: SUMMARY and DTSTART out of each VEVENT.

    stdlib again rather than a dependency. RFC 5545 folds long lines by starting
    the continuation with a space or tab, so unfolding has to happen before any
    line is read as a field — without it a long SUMMARY silently truncates.
    """
    text = re.sub(r"\r?\n[ \t]", "", text or "")
    out: List[Dict[str, Any]] = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        summary = None
        start = None
        all_day = False
        for line in block.splitlines():
            if line.startswith("END:VEVENT"):
                break
            field = line.split(":", 1)
            if len(field) != 2:
                continue
            name, value = field[0], field[1].strip()
            if name.startswith("SUMMARY"):
                # Escaped commas and semicolons per the spec.
                summary = value.replace("\\,", ",").replace("\\;", ";").strip()
            elif name.startswith("DTSTART"):
                match = re.match(r"(\d{8})(?:T(\d{6}))?", value)
                if not match:
                    continue
                stamp = datetime.strptime(match.group(1), "%Y%m%d")
                if match.group(2):
                    stamp = stamp.replace(hour=int(match.group(2)[0:2]),
                                          minute=int(match.group(2)[2:4]))
                else:
                    all_day = True
                start = stamp
        if summary and start:
            out.append({"summary": summary, "start": start, "all_day": all_day})
    return out


def load_ics(key: str, url: str, force: bool = False) -> Dict[str, Any]:
    """Fetch and parse an iCalendar feed, cached like any other source."""
    cache_key = f"ics:{key}"
    if not force:
        hit = _cached(cache_key)
        if hit is not None:
            return {**hit, "cached": True}

    started = time.time()
    try:
        body = _fetch(url, "text/calendar, text/plain, */*")
        events = [{"summary": e["summary"],
                   "start": e["start"].isoformat(),
                   "all_day": e["all_day"]}
                  for e in parse_ics(body.decode("utf-8", "replace"))]
        entry = {"at": time.time(), "events": events, "error": None,
                 "ms": int((time.time() - started) * 1000)}
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout,
            ValueError, OSError) as exc:
        stale = _MEM.get(cache_key) or _load_disk().get(cache_key) or {}
        entry = {"at": stale.get("at", 0), "events": stale.get("events", []),
                 "error": f"{type(exc).__name__}: {str(exc)[:120]}",
                 "ms": int((time.time() - started) * 1000)}
        with _LOCK:
            _MEM[cache_key] = entry
        return {**entry, "cached": False, "stale": bool(stale.get("events"))}

    _store(cache_key, entry)
    return {**entry, "cached": False}


def load_html(key: str, url: str, force: bool = False) -> Dict[str, Any]:
    """Fetch a page as text, cached. For schedules with no machine-readable form."""
    cache_key = f"html:{key}"
    if not force:
        hit = _cached(cache_key)
        if hit is not None:
            return {**hit, "cached": True}
    started = time.time()
    try:
        body = _fetch(url, "text/html, */*")
        entry = {"at": time.time(), "text": body.decode("utf-8", "replace"),
                 "error": None, "ms": int((time.time() - started) * 1000)}
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout,
            ValueError, OSError) as exc:
        stale = _MEM.get(cache_key) or _load_disk().get(cache_key) or {}
        entry = {"at": stale.get("at", 0), "text": stale.get("text", ""),
                 "error": f"{type(exc).__name__}: {str(exc)[:120]}",
                 "ms": int((time.time() - started) * 1000)}
        with _LOCK:
            _MEM[cache_key] = entry
        return {**entry, "cached": False, "stale": bool(stale.get("text"))}
    _store(cache_key, entry)
    return {**entry, "cached": False}
