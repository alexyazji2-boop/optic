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
    monkeypatch.delenv("OPTIC_V2_ACCESS", raising=False)
    monkeypatch.setattr(main, "_is_owner", lambda request: False)
    client.cookies.clear()
    yield
    client.cookies.clear()


def test_by_default_root_is_classic_and_both_addresses_work():
    assert is_classic(client.get("/"))
    assert is_classic(client.get("/classic"))
    v2 = client.get("/v2/")
    assert is_v2(v2) and 'data-classic="/classic"' in v2.text
    # offered from the classic footer, because v2 is open to everyone by default
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
