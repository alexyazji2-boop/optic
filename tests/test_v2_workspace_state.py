"""Home as a personal workspace (backlog task 4, 2026-10-20): what a saved workspace survives.

The workspace module's own load() runs in JavaScriptCore against stored states from every earlier
version; the page itself was checked in headless Chrome at 360, 390, 430, 768 and 1440 px
(~/Optic/work/v2-backlog/ws_check.py: customize, reload, move with the menu and by keyboard, hide and
add, reset and save with Undo, phone heights after desktop changes, two tabs, sparse panels).
"""
import json

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"


def load_with(tmp_path, stored):
    return _run(tmp_path, f"""
      localStorage.setItem('optic.session.holder.v1', 'guest');
      localStorage.setItem('optic.v2.workspace.v1', {json.dumps(json.dumps(stored))});
      const w = await import('{(JS / "pages/workspace.js").as_posix()}');
      const S = w._test.load();
      const ids = (k) => S.layouts[k].filter((x) => !x.hidden).map((x) => x.id);
      print(JSON.stringify({{ v: S.v, preset: S.preset, link: S.link, custom: S.custom, fold: S.fold,
        market: ids('market'), options: ids('options'), mine: ids('mine'), spans: S.layouts.market.map((x) => x.span),
        std: w._test.defaults('market').map((x) => x.id), settings: S.settings }}));
    """)


MARKET = ['indices', 'regime', 'expected', 'sectors', 'quote', 'watch', 'calendar', 'earnings', 'priority', 'news', 'desk', 'movers', 'portfolio']


def v4(**over):
    base = {"v": 4, "preset": "market", "locked": False, "link": "NVDA", "fold": {"market": {"news": False}},
            "layouts": {"market": [{"id": i, "span": 6, "h": "m", "hidden": False} for i in MARKET]}}
    base.update(over)
    return base


def test_a_changed_layout_survives_a_version_change(tmp_path):
    moved = MARKET[1:] + MARKET[:1]                       # Indices moved to the end
    got = load_with(tmp_path, v4(layouts={"market": [{"id": i, "span": 6, "h": "m", "hidden": False} for i in moved]}))
    assert got["v"] == 5 and got["market"] == moved and got["custom"].get("market") is True
    assert got["link"] == "NVDA" and got["fold"] == {"market": {"news": False}}   # before: all thrown away


def test_a_layout_nobody_changed_follows_the_standard(tmp_path):
    std = [["indices", 12, "m"], ["regime", 4, "m"], ["expected", 4, "m"], ["sectors", 4, "m"], ["quote", 8, "m"], ["watch", 4, "s"],
           ["calendar", 6, "s"], ["earnings", 6, "s"], ["priority", 6, "m"], ["news", 6, "s"], ["desk", 6, "m"], ["movers", 6, "s"], ["portfolio", 12, "m"]]
    stored = v4(layouts={"market": [{"id": i, "span": s, "h": h, "hidden": False} for i, s, h in std] + [{"id": "economy", "span": 12, "h": "m", "hidden": True}]})
    got = load_with(tmp_path, stored)
    assert "market" not in got["custom"]                  # so a panel added to the standard later reaches it
    assert got["market"] == got["std"]


def test_an_unknown_layout_name_falls_back_without_wiping_my_desk(tmp_path):
    got = load_with(tmp_path, v4(preset="gone", layouts={"mine": [{"id": "quote", "span": 8, "h": "m"}, {"id": "watch", "span": 4, "h": "s"}]}))
    assert got["preset"] == "market" and got["mine"] == ["quote", "watch"] and got["custom"].get("mine") is True


def test_my_desk_from_the_oldest_versions_still_comes_through(tmp_path):
    got = load_with(tmp_path, {"v": 2, "preset": "mine", "link": "AMD", "layouts": {"mine": [{"id": "indices", "span": 12}, {"id": "news", "span": 6}]}})
    assert got["preset"] == "mine" and got["mine"] == ["indices", "news"] and got["link"] == "AMD"


def test_a_broken_saved_layout_is_made_safe(tmp_path):
    junk = [{"id": "indices", "span": 7, "h": "huge"}, {"id": "indices", "span": 12}, {"id": "no-such-panel"}, None, {"id": "quote", "span": "wide"}]
    got = load_with(tmp_path, v4(layouts={"market": junk}))
    assert got["market"] == ["indices", "quote"]          # one of each, known panels only
    assert got["spans"][:2] == [6, 8] or got["spans"][:2] == [8, 8]   # 7 snaps to the grid's steps; "wide" becomes the panel's own
    assert all(s in (3, 4, 6, 8, 12) for s in got["spans"])


def test_panel_settings_are_kept_between_visits(tmp_path):
    got = load_with(tmp_path, v4(settings={"sectors": {"period": "chg_1m"}, "contracts": {"side": "put", "expiry": "2026-11-20"}, "nope": {"x": 1}}))
    out = _run(tmp_path, f"""
      localStorage.setItem('optic.session.holder.v1', 'guest');
      localStorage.setItem('optic.v2.workspace.v1', {json.dumps(json.dumps(v4(settings={"sectors": {"period": "chg_1m"}, "contracts": {"side": "put", "expiry": "2026-11-20"}})))});
      const w = await import('{(JS / "pages/workspace.js").as_posix()}');
      w._test.load(); w._test.save();
      print(localStorage.getItem('optic.v2.workspace.v1'));
    """)
    assert out["settings"]["sectors"] == {"period": "chg_1m"}
    assert out["settings"]["contracts"]["side"] == "put" and "expiry" not in out["settings"]["contracts"]   # an expiry is per ticker
    assert out["v"] == 5


def test_the_page_keeps_phone_heights_and_menus_apart_from_the_desktop():
    css = (V2 / "css/pages.css").read_text()
    assert '.ws-panel[data-kind="list"] .ws-body { height: auto; max-height: 300px; flex: none; }' in css
    assert '.ws-panel[data-sparse] .ws-body { height: auto; flex: none; }' in css
    assert '.ws-panel[data-span="3"]' in css and '[style*="--span:' not in css
    src = (JS / "pages/workspace.js").read_text()
    assert 'class="ws-menu menu"' in src and 'class="ws-add menu"' in src      # closed by a click elsewhere or Escape
    assert "pointercancel" in src and "if (!moved) return;" in src            # touch, and a press is not a move
    assert "S.custom[S.preset] = true" in src and "delete S.custom[k]" in src
