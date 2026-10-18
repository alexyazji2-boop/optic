"""Which frontend "/" serves, /classic and /v2/, the owner-only preview gate,
and v2's versioned, immutable assets (app/frontend.py). The rollback is the
environment, so these are the rollback's tests too."""
from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import frontend

client = TestClient(main.app)
V2 = main.STATIC_DIR / "v2"


def is_v2(r):
    return 'name="optic-build"' in r.text and 'type="importmap"' in r.text


def is_classic(r):
    return 'id="legal-footer"' in r.text and not is_v2(r)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.delenv("OPTIC_DEFAULT_UI", raising=False)
    # most tests are about the switch itself, with v2 open to all; the access
    # tests below set or unset it themselves
    monkeypatch.setenv("OPTIC_V2_ACCESS", "all")
    monkeypatch.setattr(main, "_is_owner", lambda request: False)
    client.cookies.clear()
    yield
    client.cookies.clear()


def test_with_v2_open_to_all_root_is_still_classic_and_both_addresses_work():
    assert is_classic(client.get("/"))
    assert is_classic(client.get("/classic"))
    v2 = client.get("/v2/")
    assert is_v2(v2) and 'data-classic="/classic"' in v2.text
    # offered from the classic footer, because v2 is open to everyone
    assert 'data-v2-available="1"' in client.get("/").text


def test_a_reader_choice_overrides_the_default_both_ways(monkeypatch):
    client.cookies.set("optic_ui", "v2")
    assert is_v2(client.get("/"))
    assert is_classic(client.get("/classic"))           # always classic
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "v2")
    client.cookies.set("optic_ui", "classic")
    assert is_classic(client.get("/"))
    client.cookies.clear()
    assert is_v2(client.get("/"))                       # the new default


def test_rollback_is_one_setting(monkeypatch):
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "v2")
    assert is_v2(client.get("/"))
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "classic")
    assert is_classic(client.get("/"))
    assert frontend.choose(None, False) == "classic"
    assert frontend.choose("nonsense", False) == "classic"


def test_owner_only_preview_shows_v2_to_the_owner_alone(monkeypatch):
    monkeypatch.setenv("OPTIC_V2_ACCESS", "owner")
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "v2")
    client.cookies.set("optic_ui", "v2")
    guest_root, guest_v2 = client.get("/"), client.get("/v2/")
    assert is_classic(guest_root) and is_classic(guest_v2)
    assert 'data-v2-available="1"' not in guest_root.text   # not offered to them either
    monkeypatch.setattr(main, "_is_owner", lambda request: True)
    assert is_v2(client.get("/v2/")) and is_v2(client.get("/"))
    assert 'data-v2-available="1"' in client.get("/classic").text


def test_versioned_v2_assets_are_immutable_and_the_rest_revalidate():
    page = client.get("/v2/").text
    imports = json.loads(re.search(r'<script type="importmap">(.*?)</script>', page).group(1))["imports"]
    assert "/v2/js/app.js" in imports and "/v2/js/ui/milo.js" in imports
    for path, url in imports.items():
        assert (V2 / path[len("/v2/"):]).exists(), path
        assert url.startswith(path + "?v=")
    url = imports["/v2/js/core/dom.js"]
    r = client.get(url)
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    assert client.get("/v2/js/core/dom.js").headers["cache-control"] == "no-cache"
    assert client.get("/app.js").headers["cache-control"] == "no-cache"
    # every module the page preloads is one the import map names
    assert set(re.findall(r'<link rel="modulepreload" href="([^"]+)">', page)) == set(imports.values())


def test_build_stamps_are_separate_for_the_two_apps():
    d = client.get("/api/build").json()
    assert d["build"] and d["v2"]
    assert d["v2"] == frontend.v2_build(V2)
    assert f'name="optic-build" content="{d["v2"]}"' in client.get("/v2/").text


def test_an_open_v2_tab_learns_of_a_rollback(monkeypatch):
    # v2 as the default and open to all: an open tab is told nothing new
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "v2")
    d = client.get("/api/build").json()
    assert d["ui"] == "v2" and d["v2_open"] is True
    # rolled back to classic: a reader who never chose is pointed at classic,
    # one who chose v2 keeps it
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "classic")
    assert client.get("/api/build").json()["ui"] == "classic"
    assert client.get("/api/build", cookies={"optic_ui": "v2"}).json()["ui"] == "v2"
    # closed to all but the owner: everyone else is told, whatever they chose
    monkeypatch.setenv("OPTIC_V2_ACCESS", "owner")
    d = client.get("/api/build", cookies={"optic_ui": "v2"}).json()
    assert d["v2_open"] is False and d["ui"] == "classic"
    monkeypatch.setattr(main, "_is_owner", lambda request: True)
    d = client.get("/api/build", cookies={"optic_ui": "v2"}).json()
    assert d["v2_open"] is True and d["ui"] == "v2"



# ------------------------------------------------------------- fails closed
V2_ADDRESSES = ["/v2/", "/v2", "/v2/index.html", "/V2/", "/V2/index.html", "/v2//", "/v2/./index.html",
                "/v2/js/app.js", "/v2/js/core/dom.js", "/v2/css/base.css", "/V2/JS/APP.JS", "/v2/js/../index.html",
                "/%76%32/index.html", "/v2/index.html?x=1"]


def _no_v2_reaches(cookie=None):
    if cookie:
        client.cookies.set("optic_ui", cookie)
    for path in V2_ADDRESSES:
        r = client.get(path, follow_redirects=True)
        assert not is_v2(r), path
        assert "export function" not in r.text and "export const" not in r.text, path   # no v2 module source
        assert r.status_code in (200, 404), (path, r.status_code)
    assert not is_v2(client.get("/"))


def test_unset_access_is_the_owner_only_preview(monkeypatch):
    monkeypatch.delenv("OPTIC_V2_ACCESS", raising=False)
    assert frontend.v2_access() == "owner"
    _no_v2_reaches()                                 # signed out
    _no_v2_reaches(cookie="v2")                      # a v2 preference from before
    assert 'data-v2-available="1"' not in client.get("/").text
    monkeypatch.setattr(main, "_is_owner", lambda request: True)
    assert is_v2(client.get("/v2/"))


@pytest.mark.parametrize("value", ["", "  ", "everyone", "true", "1", "Owner ", "OFF"])
def test_an_unreadable_setting_fails_closed(monkeypatch, value):
    monkeypatch.setenv("OPTIC_V2_ACCESS", value)
    assert frontend.v2_access() in ("owner", "off")
    _no_v2_reaches(cookie="v2")


def test_a_non_owner_account_is_refused_every_v2_address(monkeypatch):
    monkeypatch.setenv("OPTIC_V2_ACCESS", "owner")
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "v2")      # even with v2 as the default
    _no_v2_reaches(cookie="v2")
    assert client.get("/api/build").headers.get("x-optic-v2") == "closed"


def test_the_owner_gets_v2_files_privately(monkeypatch):
    monkeypatch.setenv("OPTIC_V2_ACCESS", "owner")
    monkeypatch.setattr(main, "_is_owner", lambda request: True)
    page = client.get("/v2/")
    assert is_v2(page)
    url = json.loads(re.search(r'<script type="importmap">(.*?)</script>', page.text).group(1))["imports"]["/v2/js/app.js"]
    r = client.get(url)
    assert r.status_code == 200 and r.headers["cache-control"].startswith("private") and "Cookie" in r.headers.get("vary", "")
    assert client.get("/api/build").headers.get("x-optic-v2") is None


def test_emergency_shutdown_closes_v2_to_everyone_whatever_they_chose(monkeypatch):
    monkeypatch.setenv("OPTIC_V2_ACCESS", "off")
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "v2")
    monkeypatch.setattr(main, "_is_owner", lambda request: True)   # the owner included
    _no_v2_reaches(cookie="v2")
    d = client.get("/api/build")
    assert d.headers.get("x-optic-v2") == "closed"
    assert d.json()["v2_open"] is False and d.json()["ui"] == "classic"
    # the reader's own choice is not erased: it comes back when v2 reopens
    assert client.cookies.get("optic_ui") == "v2"
    monkeypatch.setenv("OPTIC_V2_ACCESS", "all")
    assert is_v2(client.get("/"))


def test_a_normal_rollback_keeps_an_explicit_v2_choice(monkeypatch):
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "classic")
    assert is_classic(client.get("/"))
    client.cookies.set("optic_ui", "v2")
    assert is_v2(client.get("/"))
    assert client.get("/api/build").headers.get("x-optic-v2") is None
