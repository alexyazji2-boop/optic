"""Every screen run, kept so a result can be reproduced (owner's Handoff 8: "audit log of filter sets + results for
reproducibility").

One line per run: when, the request in words if there was one, the filters exactly as applied (peer bounds with the
value they came to), what the data was (the ranking's time and bar date, the fundamentals' periods), the fingerprint
of the two, and the symbols in order. The same fingerprint must always come with the same symbols; a test holds the
screener to that. Nothing about the reader is kept: no account, no address.

A plain file in the data folder, trimmed to its last KEEP lines when it grows past MAX_LINES, so it never needs a
migration or a job to clean it.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from .. import feeds

log = logging.getLogger(__name__)

LOG_PATH = os.path.join(feeds._DATA_DIR, "screener_runs.jsonl")
MAX_LINES = 5000
KEEP = 2500
_LOCK = threading.Lock()
_COUNT = {"path": None, "lines": 0}


def record(result: Dict[str, Any], text: Optional[str] = None) -> None:
    """Keep one run. Never raises: a log that cannot be written costs the record, not the screen."""
    if not isinstance(result, dict) or not result.get("available"):
        return
    entry = {"at": time.time(), "text": (text or None), "fingerprint": result.get("fingerprint"),
             "filters": result.get("filters"), "states": result.get("states"), "sort": result.get("sort"),
             "direction": result.get("direction"), "peers": result.get("peers"), "as_of": result.get("as_of"),
             "matched": result.get("matched"), "considered": result.get("considered"),
             "symbols": result.get("symbols")}
    try:
        with _LOCK:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            if _COUNT["path"] != LOG_PATH:
                try:
                    with open(LOG_PATH) as fh:
                        _COUNT.update(path=LOG_PATH, lines=sum(1 for _ in fh))
                except OSError:
                    _COUNT.update(path=LOG_PATH, lines=0)
            with open(LOG_PATH, "a") as fh:
                fh.write(json.dumps(entry, sort_keys=True) + "\n")
            _COUNT["lines"] += 1
            if _COUNT["lines"] > MAX_LINES:
                with open(LOG_PATH) as fh:
                    tail = fh.readlines()[-KEEP:]
                with open(LOG_PATH + ".tmp", "w") as fh:
                    fh.writelines(tail)
                os.replace(LOG_PATH + ".tmp", LOG_PATH)
                _COUNT["lines"] = len(tail)
    except (OSError, TypeError, ValueError) as exc:
        log.warning("screen_log: could not keep a run: %s", exc)


def runs(fingerprint: Optional[str] = None) -> List[Dict[str, Any]]:
    """The runs kept, oldest first, or only those with one fingerprint."""
    try:
        with open(LOG_PATH) as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError):
        return []
    return [r for r in rows if fingerprint is None or r.get("fingerprint") == fingerprint]
