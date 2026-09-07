"""The daily brief: what happened, from primary sources, organised.

Four sections, in the order a reader wants them.

  overview  Computed, not reported. Index moves, the Mag 7 individually, and
            every sector and theme ETF — so "how did semiconductors do" has a
            number rather than a headline about it. This is the only section
            derived from price data we already fetch.
  macro     Federal Reserve, BLS, BEA, SEC. Statistical agencies and the central
            bank, first-hand.
  company   8-K filings, grouped by the filer's own item codes into earnings,
            guidance, deals, management and distress.
  world     General wires, for the geopolitical leg.

Three deliberate choices worth knowing before changing anything here.

**Nothing in this module scores or ranks a security.** The brief reports; the
Swing and Long-Term tabs judge. Mixing the two would turn a news page into an
unlabelled recommendation, and every catalyst tag here is descriptive.

**The day's snapshot is upserted, not written once.** Today's row is rebuilt as
the day goes on and stops changing when the date rolls over in Eastern time,
which is what makes the archive an archive rather than a cache with history.

**A section that failed says so.** `sources` carries per-feed status, and the
frontend shows a degraded section rather than an empty one — a brief that quietly
drops the Fed because a URL moved is worse than one that admits it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from . import ai, events, feeds, news
from .analytics import regime
from .analytics import global_markets
from .analytics.sectors import SECTORS, THEMES

ET = ZoneInfo("America/New_York")

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
DB_PATH = os.environ.get("BRIEF_DB", os.path.join(_DATA_DIR, "brief.db"))

# How long a built brief is served before it is rebuilt. The feed layer caches
# for 15 minutes independently, so this mostly governs how often the overview's
# prices are refreshed.
REBUILD_AFTER_SECONDS = int(os.environ.get("BRIEF_REBUILD_MINUTES", "20")) * 60

# Section sizes. Enough to be a brief, not a wire terminal.
MACRO_LIMIT = int(os.environ.get("BRIEF_MACRO_LIMIT", "12"))
WORLD_LIMIT = int(os.environ.get("BRIEF_WORLD_LIMIT", "14"))
# Per-desk story count. Small on purpose: five desks of six beats one list of
# thirty, which is the whole point of splitting them.
DESK_LIMIT = int(os.environ.get("BRIEF_DESK_LIMIT", "6"))

# How far back a headline can be and still count as today's news. Macro releases
# are sparse — a week without a Fed statement is normal — so that leg gets a
# longer window than the wires, which would otherwise fill with a week of noise.
MACRO_WINDOW_HOURS = int(os.environ.get("BRIEF_MACRO_HOURS", "96"))
# Below this many in-window releases, the section is topped up with older ones so
# a quiet macro week doesn't render as a dead feed. See _macro_section.
MACRO_FLOOR = int(os.environ.get("BRIEF_MACRO_FLOOR", "6"))
# Floor for the wire window, and the fallback if the session maths ever fails.
WORLD_WINDOW_HOURS = int(os.environ.get("BRIEF_WORLD_HOURS", "36"))
# The window never shrinks below this: on a quiet Tuesday morning the last close
# was 17 hours ago, and a 17-hour window renders a near-empty page.
WORLD_WINDOW_FLOOR_HOURS = 24
# And never grows past this, so a long holiday weekend does not surface a week of
# stale headlines as though they were new.
WORLD_WINDOW_CEILING_HOURS = 80


def wire_window_hours(now: Optional[datetime] = None) -> int:
    """Hours of wire coverage: everything since the previous session's close.

    A fixed 36-hour window is wrong in exactly the case a pre-open read matters
    most. Friday's 16:00 close to Monday's 09:00 open is 65 hours, so on a Monday
    morning a 36-hour window silently dropped all of Friday and most of Saturday.
    The weekend news a reader opens this page to catch up on.

    Measuring from the last close instead makes the window mean something: "what
    has happened since you could last trade". It is ~17-24 hours midweek and ~65
    over a weekend, clamped either side so a quiet night is not empty and a long
    holiday weekend does not present a week of headlines as new.
    """
    now = now or datetime.now(ET)
    # Walk back to the most recent weekday 16:00 ET that has already passed.
    close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    if close > now:
        close -= timedelta(days=1)
    while close.weekday() >= 5:                 # Saturday or Sunday
        close -= timedelta(days=1)
    hours = (now - close).total_seconds() / 3600.0
    return int(max(WORLD_WINDOW_FLOOR_HOURS,
                   min(WORLD_WINDOW_CEILING_HOURS, round(hours))))

log = logging.getLogger(__name__)

_LOCK = threading.RLock()
_MEM: Dict[str, Any] = {}

MAG7 = [
    {"symbol": "AAPL", "name": "Apple"},
    {"symbol": "MSFT", "name": "Microsoft"},
    {"symbol": "NVDA", "name": "Nvidia"},
    {"symbol": "GOOGL", "name": "Alphabet"},
    {"symbol": "AMZN", "name": "Amazon"},
    {"symbol": "META", "name": "Meta"},
    {"symbol": "TSLA", "name": "Tesla"},
]

INDICES = [
    {"symbol": "SPY", "name": "S&P 500"},
    {"symbol": "QQQ", "name": "Nasdaq 100"},
    {"symbol": "DIA", "name": "Dow 30"},
    {"symbol": "IWM", "name": "Russell 2000"},
    {"symbol": "^VIX", "name": "VIX"},
]

GROUP_LABELS = {
    "earnings": "Earnings and results",
    "guidance": "Guidance and disclosures",
    "deals": "Deals and control",
    "management": "Management changes",
    "distress": "Distress and warnings",
}
GROUP_ORDER = ["earnings", "guidance", "deals", "distress", "management"]


# --------------------------------------------------------------------- storage

SCHEMA = """
CREATE TABLE IF NOT EXISTS briefs (
  day         TEXT PRIMARY KEY,   -- Eastern-time calendar date, YYYY-MM-DD
  payload     TEXT NOT NULL,      -- the whole brief as JSON
  built_at    TEXT NOT NULL,      -- UTC ISO instant of the most recent rebuild
  builds      INTEGER NOT NULL DEFAULT 1
);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def _save(day: str, payload: Dict[str, Any]) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                """INSERT INTO briefs (day, payload, built_at, builds)
                   VALUES (?, ?, ?, 1)
                   ON CONFLICT(day) DO UPDATE SET
                     payload = excluded.payload,
                     built_at = excluded.built_at,
                     builds = briefs.builds + 1""",
                (day, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
            )
    except sqlite3.Error:
        # An unwritable data dir must not cost the reader today's brief; it only
        # costs the archive. The in-memory copy still serves this process.
        pass


def _load(day: str) -> Optional[Dict[str, Any]]:
    try:
        with _connect() as conn:
            row = conn.execute("SELECT payload FROM briefs WHERE day = ?", (day,)).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    try:
        return json.loads(row["payload"])
    except ValueError:
        return None


def archive() -> List[Dict[str, Any]]:
    """Days on record, newest first, for the date picker."""
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT day, built_at, builds FROM briefs ORDER BY day DESC LIMIT 120"
            ).fetchall()
    except sqlite3.Error:
        return []
    return [{"day": r["day"], "built_at": r["built_at"], "builds": r["builds"]} for r in rows]


# -------------------------------------------------------------------- sections

def _pct(frame, bars: int = 1) -> Optional[float]:
    """Percentage change over `bars` sessions from a close series."""
    try:
        closes = frame["Close"].dropna()
    except (KeyError, TypeError, AttributeError):
        return None
    if len(closes) <= bars:
        return None
    prev, last = float(closes.iloc[-1 - bars]), float(closes.iloc[-1])
    if prev == 0:
        return None
    return (last / prev - 1.0) * 100.0


def _overview(yf_provider) -> Dict[str, Any]:
    """Index, mega-cap and sector moves. Computed here, from bars, not reported."""
    universe = INDICES + MAG7 + SECTORS + THEMES
    symbols = [row["symbol"] for row in universe]
    error = None
    frames: Dict[str, Any] = {}
    try:
        frames = yf_provider.batch_history(symbols, period="3mo", interval="1d") or {}
    except Exception as exc:                     # noqa: BLE001 - provider-agnostic
        error = f"{type(exc).__name__}: {str(exc)[:120]}"

    def build(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        out = []
        for row in rows:
            frame = frames.get(row["symbol"])
            day = _pct(frame, 1) if frame is not None else None
            week = _pct(frame, 5) if frame is not None else None
            month = _pct(frame, 21) if frame is not None else None
            last = None
            if frame is not None:
                try:
                    last = float(frame["Close"].dropna().iloc[-1])
                except (KeyError, IndexError, TypeError, ValueError):
                    last = None
            out.append({**row, "last": last, "day": day, "week": week, "month": month})
        return out

    groups = {
        "indices": build(INDICES),
        "mag7": build(MAG7),
        "sectors": build(SECTORS),
        "themes": build(THEMES),
    }

    # Leaders and laggards across sectors and themes together — the "what was
    # actually affected today" line, ranked rather than asserted.
    movers = [r for r in groups["sectors"] + groups["themes"] if r["day"] is not None]
    movers.sort(key=lambda r: r["day"], reverse=True)

    breadth = None
    scored = [r for r in groups["sectors"] if r["day"] is not None]
    if scored:
        breadth = round(100.0 * sum(1 for r in scored if r["day"] > 0) / len(scored), 1)

    return {
        "groups": groups,
        "leaders": movers[:3],
        "laggards": movers[-3:][::-1] if len(movers) > 3 else [],
        "sector_breadth_pct": breadth,
        "error": error,
        "note": ("Percentage changes are close-to-close from daily bars, so during "
                 "an open session the latest bar is still forming."),
    }


# Which catalyst labels mean anything on a story that isn't about one company.
#
# The taxonomy in news.py was written for per-ticker headlines, and applied to a
# statistical release it invents things: "GDP (Advance Estimate), 2nd Quarter
# 2026" came out tagged *Product news* because the pattern for that category
# matches "announces". A wrong label is worse than no label — it reads as a
# classification someone stands behind. So the macro and world sections keep only
# the categories that describe events larger than a single filer.
NON_COMPANY_CATALYSTS = {"macro event", "policy / supply chain", "legal / regulatory"}


def _classify(entry: Dict[str, Any], allowed: Optional[set] = None) -> Dict[str, Any]:
    """Attach the existing catalyst tags and lexicon tone to a headline.

    Reuses app/news.py rather than a second taxonomy: the Swing tab already scores
    headlines this way, and two classifiers disagreeing about the same headline on
    two tabs is a bug waiting to be reported.
    """
    text = f"{entry.get('title', '')} {entry.get('summary', '')}"
    verdict = news.classify(text)
    tags = verdict["catalysts"]
    if allowed is not None:
        tags = [c for c in tags if c.get("type") in allowed]
    return {
        **entry,
        "catalysts": tags,
        "tone": verdict["tone"],
        # Sorting and colour only — the raw lexicon sum is not a number to show.
        "tone_label": ("positive" if verdict["tone"] >= 2
                       else "negative" if verdict["tone"] <= -2 else "neutral"),
    }


def _macro_section() -> Dict[str, Any]:
    """Official releases, newest first — with a floor on how empty it can look.

    Macro is sparse by nature: a normal four-day window contains no FOMC
    statement, no CPI print and no GDP revision, and the section measured two
    entries out of 143 available on a live run. An empty macro panel reads as a
    broken feed, when the truthful statement is "nothing new since the 15th".

    So the window still decides what counts as *new*, and below a floor the
    section is topped up with the most recent releases regardless of age. Each
    card carries its own date, and `backfilled` tells the frontend to say so.
    """
    entries, status = feeds.load_kind("macro")
    deduped = feeds.dedupe(entries)
    fresh = feeds.within_hours(deduped, MACRO_WINDOW_HOURS)
    recent_count = len(fresh)

    shown = list(fresh)
    if len(shown) < MACRO_FLOOR:
        seen = {e.get("url") or e.get("title") for e in shown}
        for row in deduped:                      # already newest-first
            if len(shown) >= MACRO_FLOOR:
                break
            if (row.get("url") or row.get("title")) not in seen:
                shown.append(row)

    return {
        "entries": [_classify(e, NON_COMPANY_CATALYSTS) for e in shown[:MACRO_LIMIT]],
        "available": len(deduped),
        "in_window": recent_count,
        "backfilled": max(0, len(shown) - recent_count),
        "sources": status,
        "window_hours": MACRO_WINDOW_HOURS,
    }


def _spread(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The desk's stories, with no single source taking the whole desk.

    Straight recency, which is what this was, hands a desk to whichever source
    publishes most often. Measured on the Analysis desk the day it was added:
    all six slots went to WSJ Opinion, whose feed is a general op-ed page — the
    six were a piece about a daughter's last first day of school, two on court
    packing and foreign donations, and a readers' letters column. The Economist's
    finance feed had 300 items in the window and reached the desk zero times,
    because every one of them was a few hours older.

    So a source may hold at most half a desk. Recency still decides the order
    and decides who fills the remainder; it just no longer decides everything.
    """
    if len(rows) <= DESK_LIMIT:
        return rows
    cap = max(1, DESK_LIMIT // 2)
    picked: List[Dict[str, Any]] = []
    used: Dict[str, int] = {}
    for row in rows:
        sid = row.get("source_id") or row.get("source") or ""
        if used.get(sid, 0) >= cap:
            continue
        picked.append(row)
        used[sid] = used.get(sid, 0) + 1
        if len(picked) >= DESK_LIMIT:
            return picked
    # A desk carried by one or two prolific sources would otherwise come back
    # short, which reads as a quiet desk rather than a capped one.
    if len(picked) < DESK_LIMIT:
        chosen = {id(r) for r in picked}
        picked.extend([r for r in rows if id(r) not in chosen][:DESK_LIMIT - len(picked)])
    return picked[:DESK_LIMIT]


def _desks() -> Dict[str, Any]:
    """The wires, split into desks.

    One fetch pass, then partitioned — `load_kind` caches per source, so asking
    for five sectors costs the same HTTP as asking for one. Each desk gets its
    own freshness window applied to the shared pool so a quiet politics day
    can't be padded with a week of business stories.

    The lead story is the newest item from the highest-weighted source across
    every desk. It is picked by recency and source weight, never by tone or by
    what a model thought was interesting.
    """
    entries, status = feeds.load_kind("wire")
    window = wire_window_hours()
    fresh = feeds.dedupe(feeds.within_hours(entries, window))

    # Pick the lead first, then keep it out of the desks.
    #
    # `dedupe` already removes the same story arriving from two sources, so no
    # headline appears on two desks. The lead was the exception: it is chosen from
    # the same pool and was left in place afterwards, so the top story rendered
    # twice — once as the lead, once a few inches below in whichever desk owns its
    # source. Measured on a live brief, the Spotify lead was also sitting in
    # Markets.
    lead_row = None
    if fresh:
        lead_row = max(fresh, key=lambda r: ((r.get("published") or ""), r.get("weight", 0)))
    lead_url = (lead_row or {}).get("url")
    lead_title = (lead_row or {}).get("title")

    def _is_lead(row: Dict[str, Any]) -> bool:
        # Match on url where there is one; a headline can be reworded between
        # feeds but the link is the story.
        if lead_url and row.get("url"):
            return row["url"] == lead_url
        return bool(lead_title) and row.get("title") == lead_title

    desks = []
    for sector in feeds.SECTOR_ORDER:
        rows = [e for e in fresh if e.get("sector") == sector and not _is_lead(e)]
        if not rows:
            continue
        desks.append({
            "id": sector,
            "label": feeds.SECTOR_LABELS.get(sector, sector.title()),
            "entries": [_classify(e, NON_COMPANY_CATALYSTS) for e in _spread(rows)],
            "available": len(rows),
        })

    lead = _classify(lead_row, NON_COMPANY_CATALYSTS) if lead_row else None

    return {
        "lead": lead,
        "desks": desks,
        "available": len(fresh),
        "sources": status,
        "window_hours": window,
        "window_note": ("Everything published since the previous session closed"
                        ", about {} hours.").format(window),
    }


def _move_verb(pct: float, up_words, down_words) -> str:
    size = abs(pct)
    words = up_words if pct >= 0 else down_words
    if size < 0.25:
        return "was little changed"
    if size < 0.75:
        return words[0]
    if size < 1.5:
        return words[1]
    if size < 3.0:
        return words[2]
    return words[3]


_UP = ("edged up", "rose", "climbed", "surged")
_DOWN = ("edged down", "fell", "dropped", "slumped")


def _pct_text(pct: Optional[float], digits: int = 1) -> str:
    if pct is None:
        return "n/a"
    return f"{pct:+.{digits}f}%".replace("+-", "-")


def _by_symbol(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {r["symbol"]: r for r in rows}


def _breadth_phrase(breadth: Optional[float]) -> str:
    """Deliberately without a leading "with": the caller decides the connective,
    which stopped the tape sentence reading "…, with the Nasdaq 100 …, with sector
    participation …"."""
    if breadth is None:
        return ""
    if breadth >= 90:
        return "every sector but one finished higher"
    if breadth >= 73:
        return "most sectors participated"
    if breadth >= 55:
        return "sector participation was slightly positive"
    if breadth >= 45:
        return "sectors split roughly evenly"
    if breadth >= 27:
        return "most sectors finished lower"
    return "almost every sector finished lower"


def _world_paragraph(wires: Dict[str, Any], window_hours: int) -> Optional[str]:
    """A geopolitical line for the mechanical read: what is on the world and
    politics desks, counted and attributed — never characterised.

    This exists because the mechanical narrative described price and nothing else.
    A pre-open read that covers eleven sector ETFs and omits that the world desk
    has six stories on it is answering a narrower question than the reader asked.

    Deliberately a pointer rather than a summary. Counting stories and naming
    their sources is something this function can do correctly. Deciding that an
    arson campaign in Thailand matters to the S&P is not, and a mechanical
    threshold dressed up as geopolitical analysis would be the worst output on the
    page. So it says what is there and where to read it.
    """
    desks = {d["id"]: d for d in (wires or {}).get("desks") or []}
    picks = []
    for key, label in (("world", "world"), ("politics", "politics")):
        entries = (desks.get(key) or {}).get("entries") or []
        if entries:
            picks.append((label, entries))
    if not picks:
        return None

    total = sum(len(e) for _, e in picks)
    lead = max((e for _, entries in picks for e in entries),
               key=lambda r: (r.get("published") or ""), default=None)
    where = " and ".join("{} ({})".format(label, len(entries)) for label, entries in picks)
    line = ("Since the last close (about {}h) the {} desk{} carrying {} "
            "stor{}.".format(window_hours, where,
                             "s are" if len(picks) > 1 else " is",
                             total, "ies" if total != 1 else "y"))
    if lead and lead.get("title"):
        line += (" Newest is \u201c{}\u201d from {}.".format(
            str(lead["title"]).strip()[:130], lead.get("source") or "the wire"))
    line += (" Headlines only. Nothing here reads across to a price, and this "
             "paragraph deliberately does not claim one does.")
    return line


def _narrative(overview: Dict[str, Any],
               wires: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    groups = overview.get("groups") or {}
    idx = _by_symbol(groups.get("indices") or [])
    mag7 = [r for r in (groups.get("mag7") or []) if r.get("day") is not None]
    sectors = [r for r in (groups.get("sectors") or []) if r.get("day") is not None]
    themes = [r for r in (groups.get("themes") or []) if r.get("day") is not None]
    breadth = overview.get("sector_breadth_pct")

    spy = idx.get("SPY") or {}
    qqq = idx.get("QQQ") or {}
    iwm = idx.get("IWM") or {}
    vix = idx.get("^VIX") or {}

    paragraphs: List[str] = []

    # ---- 1. the tape -------------------------------------------------------
    if spy.get("day") is not None:
        tape = f"The S&P 500 {_move_verb(spy['day'], _UP, _DOWN)} {_pct_text(spy['day'])}"
        if qqq.get("day") is not None:
            gap = qqq["day"] - spy["day"]
            if abs(gap) >= 0.4:
                tape += (f" and the Nasdaq 100 {_pct_text(qqq['day'])}, so large-cap technology "
                         f"{'led' if gap > 0 else 'lagged'} the broad market")
            else:
                tape += f", with the Nasdaq 100 close behind at {_pct_text(qqq['day'])}"
        tape += "."
        phrase = _breadth_phrase(breadth)
        if phrase:
            tape += f" Underneath, {phrase}"
            tape += f", {breadth:.0f}% of the eleven closed up." if breadth is not None else "."
        paragraphs.append(tape)

    # ---- 2. volatility and small caps, only when they say something --------
    extras = []
    if vix.get("day") is not None and vix.get("last") is not None:
        direction = "eased" if vix["day"] < 0 else "picked up"
        extras.append(f"Volatility {direction}: the VIX ended near {vix['last']:.1f} "
                      f"({_pct_text(vix['day'])})")
    if iwm.get("day") is not None and spy.get("day") is not None:
        gap = iwm["day"] - spy["day"]
        if abs(gap) >= 0.5:
            extras.append(f"small caps {'outpaced' if gap > 0 else 'trailed'} large ones, the "
                          f"Russell 2000 at {_pct_text(iwm['day'])} against {_pct_text(spy['day'])}")
    if extras:
        joined = "; ".join(extras)
        # Not .capitalize(): it lowercases everything after the first character,
        # which turned "the VIX" into "the vix".
        paragraphs.append(joined[0].upper() + joined[1:] + ".")

    # ---- 3. leadership, sectors and themes together -----------------------
    ranked = sorted(sectors + themes, key=lambda r: r["day"], reverse=True)
    if len(ranked) >= 4:
        top = ranked[:3]
        bottom = ranked[-3:][::-1]
        lead = ", ".join(f"{r['name']} ({_pct_text(r['day'])})" for r in top)
        lag = ", ".join(f"{r['name']} ({_pct_text(r['day'])})" for r in bottom)
        paragraphs.append(f"Leadership sat with {lead}. The weakest corners were {lag}.")

    # ---- 4. megacaps, named individually ----------------------------------
    if len(mag7) >= 3:
        ordered = sorted(mag7, key=lambda r: r["day"], reverse=True)
        best, worst = ordered[0], ordered[-1]
        spread = best["day"] - worst["day"]
        winners = [r for r in ordered if r["day"] > 0]
        line = (f"Among the megacaps, {best['name']} was strongest at {_pct_text(best['day'])} "
                f"and {worst['name']} weakest at {_pct_text(worst['day'])}")
        if spread >= 4:
            line += (f". A {spread:.1f} point spread, so the group moved on its own news "
                     f"rather than together")
        elif len(winners) in (0, len(ordered)):
            line += f", and all seven finished {'higher' if winners else 'lower'}"
        else:
            line += f", with {len(winners)} of {len(ordered)} higher"
        paragraphs.append(line + ".")

    world = _world_paragraph(wires or {}, (wires or {}).get("window_hours")
                             or WORLD_WINDOW_HOURS)
    if world:
        paragraphs.append(world)

    headline = _headline(spy.get("day"), breadth, mag7)
    return {
        "headline": headline,
        "paragraphs": paragraphs,
        "method": ("Composed mechanically from the same daily closes, with fixed "
                   "thresholds for each phrase. A description of what moved, not "
                   "a view on why it moved, and not written by a model. The wire "
                   "window runs from the previous session's close, so a Monday "
                   "read covers the whole weekend rather than a fixed 36 hours."),
    }


def _morning_read(overview: Dict[str, Any], macro: Dict[str, Any],
                  calendar: Dict[str, Any], wires: Dict[str, Any],
                  index_regime: Optional[Dict[str, Any]] = None,
                  global_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The morning note: written if the assistant is available, mechanical if not.

    Two implementations of the same slot, and the difference is honest rather than
    cosmetic. The mechanical version describes — fixed thresholds turn percentages
    into phrases, and it can never be wrong about what moved. The written version
    interprets: it can say a soft print plus cooling employment is a Fed story,
    which is the part a reader actually wants and which no threshold can produce.

    The written one is preferred, generated once per Eastern day as part of the
    cached brief, so it is one API call a day shared by everyone rather than one
    per page view. Whenever it is unavailable or comes back malformed, the
    mechanical narrative stands in — a drier note is much better than none, and
    much better than a fabricated one.
    """
    mechanical = _narrative(overview, wires)

    facts = {
        "index_regime": index_regime if index_regime is not None else regime.score(overview),
        "indices": (overview.get("groups") or {}).get("indices"),
        "sectors": (overview.get("groups") or {}).get("sectors"),
        "themes": (overview.get("groups") or {}).get("themes"),
        "megacaps": (overview.get("groups") or {}).get("mag7"),
        "sector_breadth_pct": overview.get("sector_breadth_pct"),
        "leaders": overview.get("leaders"),
        "laggards": overview.get("laggards"),
        "official_releases": (macro or {}).get("entries"),
        "upcoming_calendar": (calendar or {}).get("events"),
        "lead_story": (wires or {}).get("lead"),
        # The geopolitical leg. Previously only the single lead story reached the
        # written read, so world and politics coverage was invisible to it unless
        # the day's top story happened to come from one of those desks.
        "world_desk": next((d.get("entries") for d in (wires or {}).get("desks") or []
                            if d.get("id") == "world"), None),
        "politics_desk": next((d.get("entries") for d in (wires or {}).get("desks") or []
                               if d.get("id") == "politics"), None),
        "wire_window_hours": (wires or {}).get("window_hours"),
        "mechanical_description": mechanical.get("paragraphs"),
        # The overnight session worldwide, with each market's measured correlation
        # to the S&P attached. Passed in so the written note can reach for Asia or
        # Europe when they matter — and so it has the correlation in hand when it
        # is tempted to claim a link that the number does not support.
        "global_overnight": (global_context or {}).get("sessions"),
        "global_correlation_note": (global_context or {}).get("method"),
    }

    try:
        written = ai.write_morning_read(facts)
    except Exception as exc:                        # never lose the brief over this
        log.warning("morning read failed: %s: %s", type(exc).__name__, exc)
        written = None

    if written:
        written["fallback_available"] = True
        return written
    return mechanical

def _headline(spy_day: Optional[float], breadth: Optional[float],
              mag7: List[Dict[str, Any]]) -> str:
    """One line at the top. Describes shape, never cause."""
    if spy_day is None:
        return "Market moves unavailable"
    tech = [r for r in mag7 if r.get("day") is not None]
    tech_avg = sum(r["day"] for r in tech) / len(tech) if tech else None
    broad = breadth is not None and (breadth >= 73 or breadth <= 27)

    if abs(spy_day) < 0.25:
        return "Index flat, with movement underneath"
    up = spy_day > 0
    if broad:
        base = "Broad advance" if up else "Broad decline"
    else:
        base = "Higher, but narrowly" if up else "Lower, but narrowly"
    if tech_avg is not None and abs(tech_avg) > abs(spy_day) * 1.8 and tech_avg * spy_day > 0:
        base += ". Megacap technology doing the work"
    elif tech_avg is not None and tech_avg * spy_day < 0:
        base += ". Megacap technology going the other way"
    return base


# ----------------------------------------------------------------------- build

def today_key(now: Optional[datetime] = None) -> str:
    """The Eastern-time calendar date a brief belongs to."""
    return (now or datetime.now(timezone.utc)).astimezone(ET).date().isoformat()


def build(yf_provider, day: Optional[str] = None) -> Dict[str, Any]:
    """Assemble a brief from live sources and persist it under its ET date."""
    started = time.time()
    key = day or today_key()
    overview = _overview(yf_provider)
    macro = _macro_section()
    wires = _desks()
    calendar = events.upcoming()
    # Scored once here and passed down, rather than computed inside the morning
    # note. It was only ever an input to that prompt, which is why the Read tab
    # had nothing to render even though the score existed and was correct.
    index_regime = regime.score(overview)

    # The overnight session worldwide. Wrapped because it is eighteen symbols of
    # history from a second provider call — a failure there must cost the brief its
    # global section, not the whole brief.
    try:
        global_context = global_markets.build(yf_provider)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("global overnight unavailable: %s", exc)
        global_context = {"available": False, "reason": str(exc)[:140]}

    degraded = [s["id"] for s in macro["sources"] + wires["sources"] if s.get("error")]
    degraded += [f"calendar:{i}" for i in calendar.get("degraded", [])]

    payload = {
        "day": key,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "build_ms": int((time.time() - started) * 1000),
        "summary": _morning_read(overview, macro, calendar, wires, index_regime,
                                 global_context),
        "overview": overview,
        "index_regime": index_regime,
        "global_overnight": global_context,
        "macro": macro,
        "calendar": calendar,
        "wires": wires,
        "degraded_sources": degraded,
        "attribution": ("Headlines link to the publisher. Optic Terminal shows the "
                        "headline, source and time only. Follow the link to read "
                        "the article at its source."),
    }
    _save(key, payload)
    with _LOCK:
        _MEM[key] = {"at": time.time(), "payload": payload}
    return payload


def state(yf_provider, day: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    """What the endpoint serves.

    Asking for a past day reads the archive and never rebuilds — a brief dated
    last Tuesday should say what was known last Tuesday, not what today's feeds
    happen to still be carrying.
    """
    current = today_key()
    requested = day or current

    if requested != current:
        stored = _load(requested)
        if stored is None:
            return {"day": requested, "missing": True, "archive": archive(),
                    "reason": "No brief was recorded for that day."}
        return {**stored, "archive": archive(), "historical": True}

    if not force:
        with _LOCK:
            cached = _MEM.get(current)
        if cached and time.time() - cached["at"] < REBUILD_AFTER_SECONDS:
            return {**cached["payload"], "archive": archive(), "cached": True}
        stored = _load(current)
        if stored:
            age = time.time() - _parse_iso(stored.get("built_at"))
            if age < REBUILD_AFTER_SECONDS:
                with _LOCK:
                    _MEM[current] = {"at": time.time() - age, "payload": stored}
                return {**stored, "archive": archive(), "cached": True}

    return {**build(yf_provider, current), "archive": archive()}


def _parse_iso(raw: Optional[str]) -> float:
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return 0.0
