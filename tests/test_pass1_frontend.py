"""v2 is the only front end, and Classic is one setting away (Pass 1, 2026-11-09; app/frontend.py OPTIC_CLASSIC).

With the setting off (the default) every public page address serves v2, whatever cookie or older setting a reader
or the deployment carries; with it on, Classic is served exactly as before (tests/test_frontend_switch.py holds
those rules, under the setting). /api/health and the owner's Metrics page name the active front end in both
states. The route table is walked, not listed by hand, so a page route added later is held to the same rule."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import app.main as main
from app import frontend

client = TestClient(main.app)
JS = main.STATIC_DIR / "v2" / "js"


def is_v2(r):
    return r.status_code == 200 and 'name="optic-build"' in r.text and 'type="importmap"' in r.text


def is_classic(r):
    return r.status_code == 200 and 'id="legal-footer"' in r.text and not is_v2(r)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("OPTIC_CLASSIC", "OPTIC_DEFAULT_UI", "OPTIC_V2_ACCESS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(main, "_is_owner", lambda request: False)
    client.cookies.clear()
    yield
    client.cookies.clear()


def page_routes():
    """Every GET route that answers with a page rather than data: the app's own HTML routes, read from the route
    table, plus the classic page's file address, which the static mount answers."""
    out = set()
    for r in main.app.routes:
        if isinstance(r, APIRoute) and "GET" in r.methods and not r.path.startswith("/api/") and r.include_in_schema is False \
                and "{" not in r.path:
            out.add(r.path)
    out.add("/index.html")
    return sorted(out)


def test_the_route_table_has_the_page_routes_this_test_is_about():
    # if this list shrinks the walk below proves nothing
    assert {"/", "/classic", "/v2/", "/v2/index.html", "/index.html"} <= set(page_routes())


@pytest.mark.parametrize("cookie", [None, "classic", "v2"])
def test_with_classic_off_every_public_page_serves_v2(monkeypatch, cookie):
    # older settings that once served Classic are not read while it is off
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "classic")
    monkeypatch.setenv("OPTIC_V2_ACCESS", "owner")
    if cookie:
        client.cookies.set("optic_ui", cookie)
    for path in page_routes():
        r = client.get(path)
        assert is_v2(r), "{} did not serve v2 (cookie {})".format(path, cookie)
        assert 'data-classic-off="1"' in r.text
        assert "X-Optic-V2" not in r.headers or r.headers["X-Optic-V2"] != "closed"


def test_with_classic_on_classic_is_served_again(monkeypatch):
    monkeypatch.setenv("OPTIC_CLASSIC", "on")
    assert is_classic(client.get("/"))
    assert is_classic(client.get("/classic"))
    assert is_classic(client.get("/index.html"))


@pytest.mark.parametrize("value,on", [("on", True), ("1", True), ("true", True), ("yes", True), ("off", False), ("", False), ("onn", False)])
def test_only_a_clear_yes_turns_classic_on(monkeypatch, value, on):
    monkeypatch.setenv("OPTIC_CLASSIC", value)
    assert frontend.classic_on() is on


def test_health_names_the_front_end_in_both_states(monkeypatch):
    h = client.get("/api/health").json()
    assert h["frontend"] == {"active": "v2", "classic": False, "setting": "OPTIC_CLASSIC"}
    assert h["usage_capture"] is True
    monkeypatch.setenv("OPTIC_CLASSIC", "on")
    h = client.get("/api/health").json()
    assert h["frontend"]["active"] == "classic" and h["frontend"]["classic"] is True
    # Classic on with the old v2 default and v2 open to all: the public gets v2, and health says so
    monkeypatch.setenv("OPTIC_DEFAULT_UI", "v2")
    monkeypatch.setenv("OPTIC_V2_ACCESS", "all")
    assert client.get("/api/health").json()["frontend"]["active"] == "v2"


def test_the_owner_panel_names_the_front_end_and_the_setting():
    src = (JS / "pages" / "reports.js").read_text()
    assert "function frontEnd()" in src and "${frontEnd()}" in src
    assert "(D.health || {}).frontend" in src
    assert "To turn it back on, set ${f.setting}=on and restart." in src


def test_the_classic_link_is_not_offered_when_classic_is_off():
    src = (JS / "core" / "legal.js").read_text()
    assert "CLASSIC_OFF ? '' :" in src and "dataset.classicOff" in src


def test_the_setting_is_documented_in_the_example_environment_and_the_readme():
    root = Path(main.STATIC_DIR).parent
    assert "OPTIC_CLASSIC=" in (root / ".env.example").read_text()
    assert "OPTIC_CLASSIC" in (root / "DEPLOY.md").read_text()
