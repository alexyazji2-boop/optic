"""index.html must never be served from a browser cache without revalidating.

This is a deploy invariant, not a nicety. StaticFiles sends ETag and
Last-Modified but no Cache-Control, and with no explicit policy a browser may
apply heuristic freshness and serve index.html with no request at all. The ?v=
key on the asset tags cannot rescue that, because it lives inside the HTML that
is itself stale: an old page goes on asking for the old app.js, and a shipped
change presents as having silently done nothing rather than as an error.

That is not hypothetical. It happened, and it cost a debugging session that
started by looking for the bug in the front-end code.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_index_must_be_revalidated():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "no-cache" in resp.headers.get("cache-control", "")


def test_assets_must_be_revalidated():
    for path in ("/app.js", "/charts.js", "/styles.css"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert "no-cache" in resp.headers.get("cache-control", ""), path


def test_asset_version_is_stamped_not_hardcoded():
    """The served version comes from the asset mtimes, so shipping an edit does
    not depend on anyone remembering to bump a literal by hand."""
    import re

    html = client.get("/").text
    versions = set(re.findall(r"(?:app\.js|charts\.js|styles\.css)\?v=(\d+)", html))
    assert len(versions) == 1, versions
    version = int(versions.pop())
    # A recent mtime, not the old hand-maintained counter (which was in the 300s).
    assert version > 1_000_000_000, version


def test_revalidation_is_cheap():
    """no-cache means "ask first", not "download again" — the ETag still turns a
    repeat visit into a 304 with an empty body."""
    first = client.get("/app.js")
    etag = first.headers["etag"]
    second = client.get("/app.js", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert not second.content
