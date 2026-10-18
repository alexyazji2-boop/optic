"""Which frontend a reader gets, and how v2's page is served.

Two apps live side by side: the classic app (static/index.html and its
siblings) and v2 (static/v2/). This module decides which one "/" serves and
builds v2's page.

Who gets what
  * ``OPTIC_DEFAULT_UI``: ``classic`` (the default) or ``v2``. What "/" serves
    when the reader has not chosen.
  * The ``optic_ui`` cookie (``classic`` or ``v2``), set by the "Try the new
    design" and "Use the classic app" links, overrides that for one browser.
  * ``OPTIC_V2_ACCESS``: ``owner`` (the default), ``all`` or ``off``. It fails
    closed: unset means the owner-only preview, and anything unreadable means
    ``off``. With ``owner``, v2 is served only to the signed-in owner; with
    ``off`` (the emergency shutdown) to nobody. Everyone v2 is closed to gets
    the classic app at "/" and "/v2/" whatever their optic_ui cookie says, is
    refused v2's files, and an open v2 tab is told on its next request
    (the ``X-Optic-V2: closed`` header) and moved to the classic app on its
    next navigation. The cookie itself is kept, so nothing a reader chose is
    lost when v2 opens again.
  * ``/classic`` always serves the classic app, so it stays one address away
    whatever "/" serves. Hash routes are the same in both apps.

Two ways back, both an environment setting and a restart. Nothing is migrated
in either direction; both apps read the same server data and browser keys.
  * Normal rollback, ``OPTIC_DEFAULT_UI=classic``: "/" serves the classic app
    again, but a reader who chose v2 (the cookie) keeps it.
  * Emergency shutdown, ``OPTIC_V2_ACCESS=off``: v2 is closed to everyone,
    the owner included, whatever anyone chose.

v2's page
  The HTML is served with absolute asset paths (so it works at "/" as well as
  "/v2/"), an import map that gives every module a content version, and a
  modulepreload list, so a cold load fetches the module graph in parallel and
  a warm load needs no revalidation at all: a versioned module address is
  cached as immutable, and an edit changes the address.
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

V2_PREFIX = "/v2/"
COOKIE = "optic_ui"


def default_ui() -> str:
    v = (os.environ.get("OPTIC_DEFAULT_UI") or "classic").strip().lower()
    return "v2" if v == "v2" else "classic"


def v2_access() -> str:
    raw = os.environ.get("OPTIC_V2_ACCESS")
    if raw is None or not raw.strip():
        return "owner"                      # fail closed: the preview, not the public
    v = raw.strip().lower()
    return v if v in ("all", "owner", "off") else "off"


def v2_allowed(is_owner: bool) -> bool:
    access = v2_access()
    if access == "off":
        return False
    return access == "all" or bool(is_owner)


def v2_path(path: str) -> bool:
    """Whether a request path is under v2, read the way any server or file
    system might: normalised, and without regard to case (macOS serves
    static/V2 from static/v2)."""
    p = posixpath.normpath("/" + (path or "").lstrip("/")).lower()
    return p == "/v2" or p.startswith("/v2/")


def v2_page_path(path: str) -> bool:
    p = posixpath.normpath("/" + (path or "").lstrip("/")).lower()
    return p in ("/v2", "/v2/index.html")


def choose(cookie: Optional[str], is_owner: bool) -> str:
    """What "/" serves this reader: 'v2' or 'classic'."""
    want = cookie if cookie in ("v2", "classic") else default_ui()
    if want == "v2" and not v2_allowed(is_owner):
        return "classic"
    return want


# ------------------------------------------------------------------ v2 page
_cache: Dict[str, Tuple[float, Any]] = {}


def _v2_files(v2_dir: Path):
    for p in sorted(v2_dir.rglob("*")):
        if p.is_file() and p.suffix in (".js", ".css", ".html") and "_fx" not in p.parts:
            yield p


def _content_versions(v2_dir: Path) -> Dict[str, str]:
    """Each module and stylesheet's short content hash, keyed by its site path.
    Recomputed only when a file under v2 changes (newest mtime as the key)."""
    newest = max((p.stat().st_mtime for p in _v2_files(v2_dir)), default=0.0)
    hit = _cache.get("versions")
    if hit and hit[0] == newest:
        return hit[1]
    out = {}
    for p in _v2_files(v2_dir):
        rel = p.relative_to(v2_dir).as_posix()
        out[V2_PREFIX + rel] = hashlib.sha1(p.read_bytes()).hexdigest()[:10]
    _cache["versions"] = (newest, out)
    return out


def v2_build(v2_dir: Path) -> str:
    """One stamp for the whole of v2, for an open tab to compare with."""
    versions = _content_versions(v2_dir)
    return hashlib.sha1(json.dumps(versions, sort_keys=True).encode()).hexdigest()[:12]


def v2_page(v2_dir: Path, classic_url: str = "/classic") -> str:
    """v2's index.html with absolute, versioned asset addresses."""
    versions = _content_versions(v2_dir)
    html = (v2_dir / "index.html").read_text(encoding="utf-8")

    def ver(path: str) -> str:
        v = versions.get(path)
        return f"{path}?v={v}" if v else path

    html = re.sub(r'href="css/([^"]+)"', lambda m: f'href="{ver(V2_PREFIX + "css/" + m.group(1))}"', html)
    html = re.sub(r'src="js/([^"]+)"', lambda m: f'src="{ver(V2_PREFIX + "js/" + m.group(1))}"', html)
    js = {k: f"{k}?v={v}" for k, v in versions.items() if k.endswith(".js")}
    importmap = json.dumps({"imports": js}, separators=(",", ":"))
    preload = "".join(f'<link rel="modulepreload" href="{u}">' for u in js.values())
    head_add = f'<script type="importmap">{importmap}</script>{preload}<meta name="optic-build" content="{v2_build(v2_dir)}">'
    # the import map must come before the first module script
    html = html.replace('<script type="module"', head_add + '<script type="module"', 1)
    html = html.replace("<html", f'<html data-classic="{classic_url}"', 1)
    return html


def cache_header(path: str, query: str) -> Optional[str]:
    """Versioned v2 assets never change at their address; everything else
    revalidates. While v2 is not open to all, a shared cache must not keep
    them (they are served per reader), so they are private."""
    if path.startswith(V2_PREFIX) and re.search(r"(^|&)v=[0-9a-f]{6,}", query or ""):
        return "{}, max-age=31536000, immutable".format("public" if v2_access() == "all" else "private")
    return None
