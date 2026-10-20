"""Performance and recovery (backlog task 14, 2026-10-20): pages load when first opened, the first load
preloads only the shell, a page's own modules are fetched side by side, and a page left behind is not kept in
memory by its chart slots.

Measured in headless Chrome on a throttled phone profile (150 ms round trip, 1.6 Mbps, 4x CPU) with an empty
browser cache (~/Optic/work/v2-backlog/perf_check.py --cold) and over 40 route changes
(perf_repeat.py); the numbers are in docs/frontend-v2/BACKLOG-2026-10-20.md, task 14.
"""
import json
import re
from pathlib import Path

from app import frontend
from tests.test_frontend_v2_stage0 import V2

APP = (V2 / "js/app.js").read_text()
CHART = (V2 / "js/ui/chart.js").read_text()


def test_only_the_shell_imports_pages_statically():
    static_pages = set(re.findall(r"^import [^;]*from '\./pages/([a-z-]+)\.js';", APP, re.M))
    assert static_pages == {"settings", "signin", "bridge"}, static_pages
    for page in ("workspace", "dossier", "chart", "options", "compare", "financials", "earnings", "watchlist"):
        assert f"lazy(() => import('./pages/{page}.js'), '{page}')" in APP, page


def test_a_later_route_wins_a_race_and_a_failed_fetch_says_so():
    show = APP[APP.index("async function show(route)"):APP.index("const main = $('#main');")]
    assert "const my = ++SHOW" in show and show.count("if (my !== SHOW) return;") == 2
    assert "Its code could not be fetched" in show
    assert "p = null; throw e;" in APP, "a failed fetch is tried again next time, not cached as failed"


def test_the_first_load_preloads_the_shell_and_maps_every_module():
    page = frontend.v2_page(V2)
    imports = json.loads(re.search(r'<script type="importmap">(.*?)</script>', page).group(1))["imports"]
    pre = set(re.findall(r'<link rel="modulepreload" href="([^"]+)">', page))
    shell = frontend.static_graph(V2)
    assert pre == {imports[k] for k in shell}
    assert "/v2/js/pages/chart.js" in imports and "/v2/js/pages/chart.js" not in shell
    assert len(shell) < len(imports) / 2
    graph = json.loads(re.search(r'<script type="application/json" id="v2-graph">(.*?)</script>', page).group(1))
    assert imports["/v2/js/pages/chart.js"] in graph["chart"], "a page's graph includes the page"
    assert not (set(graph["chart"]) & pre), "and nothing the shell already preloads"


def test_static_graph_follows_static_imports_only(tmp_path):
    js = tmp_path / "js"
    (js / "pages").mkdir(parents=True)
    (js / "app.js").write_text("import { a } from './a.js';\nconst p = () => import('./pages/x.js');\n")
    (js / "a.js").write_text("export * from './b.js';\nexport const a = 1;\n")
    (js / "b.js").write_text("export const b = 2;\n")
    (js / "pages" / "x.js").write_text("import { a } from '../a.js';\n")
    assert frontend.static_graph(tmp_path) == {"/v2/js/app.js", "/v2/js/a.js", "/v2/js/b.js"}


def test_warming_waits_for_the_first_page_and_a_costly_connection():
    warm = APP[APP.index("function warmNext()"):APP.index("let SHOW = 0;")]
    assert "c.saveData" in warm and "2g" in warm
    assert "rendered.then(warmLater" in APP


def test_chart_slots_of_pages_left_are_dropped_on_the_next_mount():
    mount = CHART[CHART.index("export function mountCharts"):CHART.index("root.querySelectorAll")]
    assert "slots.forEach((el) => { if (!el.isConnected) slots.delete(el); });" in mount
