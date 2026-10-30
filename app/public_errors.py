"""Exception text made fit for a response (SEC-16, Phase 10 security review).

About thirty places answered a public request with `str(exc)`, and an upstream library's message can carry the host
it called, a URL with its query string, or a file path on this server. The sentence stays, since most of these are
Optic's own words ("needs a positive cash flow") or say usefully what failed; the hosts, URLs and paths inside it go.
The whole text is still the log's where the caller logs it.
"""
from __future__ import annotations

import re

_URL = re.compile(r"\b(?:https?|wss?|ftp)://[^\s'\")>]+", re.I)
_HOST = re.compile(r"\bhost=['\"][^'\"]*['\"]", re.I)
_URL_PATH = re.compile(r"\burl: /\S*", re.I)
_PATH = re.compile(r"(?<![\w.:/])/(?:[\w.\-]+/)+[\w.\-]*")


def public(exc: BaseException, limit: int = 120) -> str:
    """`str(exc)` without hosts, URLs or file paths, on one line, at most `limit` characters."""
    text = str(exc) or type(exc).__name__
    text = _URL.sub("[address]", text)
    text = _HOST.sub("host=[source]", text)
    text = _URL_PATH.sub("url: [path]", text)
    text = _PATH.sub("[path]", text)
    return " ".join(text.split())[:limit]
