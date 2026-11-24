"""Pass 2, item 8 (2026-11-17): colour-coded link groups, named layouts kept on the account, and Home's grid on the
stock page (#/SYM/workspace).

The server keeps a layout as the workspace's own JSON, checked and capped (app/layouts.py), private to its owner, with
an owner kind and id so a later round can share one with a group. The three legs for every route: no user, another
user, and a request without the CSRF header.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import layouts
from app.auth import config
from tests.test_frontend_v2_stage0 import V2

GOOD = "tungsten-carbide-9"
client = TestClient(main.app)
other = TestClient(main.app)
BODY = {"layout": {"panels": [{"id": "quote", "span": 8, "h": "m", "hidden": False, "grp": "blue"},
                              {"id": "cnews", "span": 4, "h": "s", "hidden": False, "grp": "gold"},
                              {"id": "indices", "span": 12, "h": "m", "hidden": True}],
                   "groups": {"blue": "AAPL", "gold": "NVDA"}}}


@pytest.fixture(autouse=True)
def fresh(accounts):
    client.cookies.clear()
    other.cookies.clear()
    return accounts


def register(http, email):
    http.post("/api/auth/register", json={"first_name": "A", "last_name": "B", "email": email, "password": GOOD, "confirm_password": GOOD})
    return {"X-Optic-CSRF": http.cookies.get(config.CSRF_COOKIE)}


def test_a_named_layout_is_saved_on_the_account_and_read_back_from_another_session():
    h = register(client, "mine@example.com")
    r = client.put("/api/layouts/Earnings week", headers=h, json=BODY)
    assert r.status_code == 200 and r.json()["saved"] and r.json()["replaced"] is False
    # another browser: the same account signed in afresh
    again = TestClient(main.app)
    again.post("/api/auth/login", json={"email": "mine@example.com", "password": GOOD})
    got = again.get("/api/layouts").json()["layouts"]
    assert [x["name"] for x in got] == ["Earnings week"]
    assert got[0]["layout"]["groups"] == {"blue": "AAPL", "gold": "NVDA"} and got[0]["layout"]["panels"][1]["grp"] == "gold"
    assert client.put("/api/layouts/Earnings week", headers=h, json=BODY).json()["replaced"] is True


def test_no_user_another_user_and_no_csrf_are_refused():
    assert client.get("/api/layouts").status_code == 401
    assert client.put("/api/layouts/x", json=BODY).status_code in (401, 403)
    h = register(client, "mine@example.com")
    assert client.put("/api/layouts/Mine", json=BODY).status_code == 403, "no CSRF header"
    client.put("/api/layouts/Mine", headers=h, json=BODY)
    t = register(other, "theirs@example.com")
    assert other.get("/api/layouts").json()["layouts"] == [], "another reader's layouts are not listed"
    assert other.delete("/api/layouts/Mine", headers=t).status_code == 404, "nor deleted"
    assert client.delete("/api/layouts/Mine", headers=h).json()["layouts"] == []


def test_only_the_workspaces_own_shape_is_kept():
    for bad in ({"panels": []}, {"panels": [{"id": "Quote!", "span": 8}]}, {"panels": [{"id": "quote", "span": 7}]}, "x"):
        with pytest.raises(Exception):
            layouts.check_body(bad)
    ok = layouts.check_body({"panels": [{"id": "quote", "span": 8, "h": "zz", "grp": "red", "extra": 1}], "groups": {"blue": "AAPL", "red": "X", "gold": "<b>"}})
    assert ok == {"panels": [{"id": "quote", "span": 8, "h": "m", "hidden": False}], "groups": {"blue": "AAPL"}}
    with pytest.raises(Exception):
        layouts._name("x" * 41)


def test_an_account_keeps_at_most_twenty(monkeypatch):
    monkeypatch.setattr(layouts, "MAX_LAYOUTS", 2)
    h = register(client, "mine@example.com")
    assert client.put("/api/layouts/A", headers=h, json=BODY).status_code == 200
    assert client.put("/api/layouts/B", headers=h, json=BODY).status_code == 200
    r = client.put("/api/layouts/C", headers=h, json=BODY)
    assert r.status_code == 409 and "Delete one" in r.json()["detail"]


WS = (V2 / "js" / "pages" / "workspace.js").read_text()


def test_link_groups_move_only_their_own_panels():
    assert "const LINK_GROUPS = [['blue', 'Blue'], ['gold', 'Gold'], ['teal', 'Teal']];" in WS
    assert "grpOf(id) !== 'blue' && S.groups[grpOf(id)]" in WS, "a Gold or Teal panel shows its group's ticker"
    gl = WS[WS.index("function setGroupLink(sym, grp) {"):WS.index("function cycleGroup(id) {")]
    assert "grpOf(x.id) === grp" in gl and "the other panels are unchanged" in gl
    assert "grpOf(x.id) === 'blue'" in WS[WS.index("function setLink(sym, grp = 'blue') {"):WS.index("function setGroupLink")]
    assert "['pin', 'grp']" in WS, "a panel's group is kept between visits"


def test_named_layouts_say_when_a_save_lands_and_signed_out_say_where_the_layout_lives():
    assert "is saved on your account. Open it from any browser." in WS and "is updated on your account." in WS
    assert "Sign in to name a layout and keep it on your account; until then it is kept in this browser." in WS


def test_the_stock_page_opens_homes_grid_for_its_company_without_touching_homes_choice():
    router = (V2 / "js" / "core" / "router.js").read_text()
    assert "if (tab === 'workspace') return { view: 'stockgrid', symbol, params };" in router
    assert "stockgrid: P.workspace" in (V2 / "js" / "app.js").read_text()
    assert 'Open as panels' in (V2 / "js" / "pages" / "dossier-frame.js").read_text()
    assert "stock: { label: 'Company panels', company: true" in WS and ".filter(([, p]) => !p.company)" in WS
    assert "Object.assign({}, S, { preset: HOME.preset, link: HOME.link, linkChosen: HOME.linkChosen })" in WS
