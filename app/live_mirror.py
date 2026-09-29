"""The live site's AI-written panels, for a copy that cannot write its own.

The Catalyst Library and the weekly update are written by the model, so a copy
of the terminal without a working Anthropic key can do neither. On 2026-09-28
the local copy's key had expired on 2026-09-10 and both panels showed an error.
The live site writes both on its own key and schedule, and the result is the
same for every reader, so a local copy can show that instead. It costs nobody
anything: nothing here asks the live site to write what it would not have
written anyway, and a forced rebuild is never passed through.

Only ever on a local copy. A hosted deployment does not read from another
server, which is also what stops the live site reading from itself.

The library needs the model only under CATALYST_READER=model. Under the rules
reader, the default since 2026-09-29, it costs nothing to fill, so a copy fills
its own and only the weekly update is mirrored, unless the setting below is on
(catalysts.mirrored).

OPTIC_MIRROR_LIVE decides when:
  auto (the default)  while this copy's own key cannot be used
  on                  always, so a copy with a key does not pay to write what
                      the live site has already written
  off                 never
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

from .runtime import is_hosted

log = logging.getLogger(__name__)

LIVE_URL = (os.environ.get("OPTIC_LIVE_URL") or "https://theopticterminal.com").rstrip("/")
MODE = (os.environ.get("OPTIC_MIRROR_LIVE") or "auto").strip().lower()
# How long to wait for the live site. The library is a read and answers in a
# fraction of a second. The weekly update is written on the first request of a
# week, and that request waits for the model: the first local copy of it timed
# out at fifteen seconds while the live site was writing it, then answered in
# 0.34s once it had.
TIMEOUT = {"/api/catalysts": 15.0, "/api/weekly": 120.0}
# How long a copy is reused. The library changes at most every six hours and
# the update once a week, so five and thirty minutes keep a page load from being
# a request to the live site without holding anything noticeably stale.
TTL = {"/api/catalysts": 300.0, "/api/weekly": 1800.0}
# A failure is remembered for a minute, so a live site that is down costs one
# timeout a minute rather than one on every page load.
FAIL_TTL = 60.0

_CACHE: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}
_LOCK = threading.Lock()


def active() -> bool:
    """Whether this copy shows the live site's panels instead of its own."""
    if is_hosted() or MODE == "off":
        return False
    if MODE == "on":
        return True
    from . import ai                        # local: ai is the heavier import
    return not ai.key_usable()


def why() -> str:
    if MODE == "on":
        return "This copy is set to show the live site's version (OPTIC_MIRROR_LIVE=on)."
    return ("This copy's Anthropic key cannot be used, so it shows the live site's "
            "version instead of writing its own.")


def _http_get(url: str, timeout: float = 15.0) -> bytes:
    request = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "OpticTerminal-local-copy"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch(path: str, params: Optional[Dict[str, Any]] = None,
          fresh: bool = False) -> Optional[Dict[str, Any]]:
    """The live site's answer at `path`, marked as coming from there, or None.

    `fresh` skips this copy's cache. It is never sent on: the live site
    decides for itself when to write anything.
    """
    pairs = sorted((k, v) for k, v in (params or {}).items() if v not in (None, ""))
    url = LIVE_URL + path + ("?" + urlencode(pairs) if pairs else "")
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(url)
    if hit is not None and not fresh:
        at, data = hit
        if now - at < (TTL.get(path, 300.0) if data is not None else FAIL_TTL):
            return _marked(data)
    try:
        data = json.loads(_http_get(url, TIMEOUT.get(path, 15.0)).decode("utf-8", "replace"))
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
    except Exception as exc:                                    # noqa: BLE001
        log.warning("live copy of %s unavailable: %s", path, exc)
        data = None
    with _LOCK:
        _CACHE[url] = (now, data)
    return _marked(data)


def _marked(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if data is None:
        return None
    out = dict(data)
    out["mirror"] = {"from": LIVE_URL, "why": why()}
    return out
