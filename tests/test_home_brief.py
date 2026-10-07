"""Home as a daily brief: the reader's own names, each thing said once.

Measured on Home at 1440x900 on 2026-10-06, before: the quick picks were the
same eight examples for a reader who had opened INTC and PLTR the day before;
four setups triggering on the close carried the same two-sentence explanation
four times; and the server wrote an em dash into reader-facing copy in nine
places the client-side pass never saw ("XLK — Technology" on the Today band).
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = """
      function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
      function cap(s) { return s; }
      const DAILY_LINK_LABEL = { swing: 'Swing setups', chart: 'Chart' };
    """ + _fn("function dailyChangeRow(it, repeatWhy) {") + _fn("function dailyChangeRows(items) {")
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_a_returning_reader_sees_their_own_names():
    fn = _fn("function renderHome() {")
    assert "const recent = recentSymbols();" in fn
    assert "const picks = recent.length ? recent : HOME_QUICK_PICKS;" in fn
    assert "recent.length ? 'Recent' : 'Or jump to'" in fn
    assert '<span class="label">${quickLabel}</span>' in fn
    # A stored symbol is markup on the way out, like any other string.
    assert 'data-pick="${esc(t)}">${esc(t)}</button>' in fn


def test_an_explanation_shared_by_several_changes_is_said_once():
    why = "A rule's trigger on a completed candle. It is for review, not an order."
    out = _run("""
      var items = [
        { symbol: 'AMD', headline: 'AMD A setup triggered', why: %(w)s, link: { view: 'swing' } },
        { symbol: 'QQQ', headline: 'QQQ 2 setups triggered', why: %(w)s, link: { view: 'swing' } },
        { symbol: 'AMD', headline: 'AMD Closed at a 52-week high', why: 'No overhead level.',
          link: { view: 'chart' } },
        { symbol: 'SPY', headline: 'SPY 3 setups triggered', why: %(w)s, link: { view: 'swing' } },
      ];
      var html = dailyChangeRows(items);
      print('RESULT:' + JSON.stringify({ html: html }));
    """ % {"w": json.dumps(why)})
    html = out["html"]
    assert html.count("for review, not an order") == 1
    assert html.count("No overhead level.") == 1
    assert html.count('class="dc-item') == 4, "every change is still listed"


def _reader_strings(path):
    """String constants in a module, less its docstrings."""
    tree = ast.parse(path.read_text())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docs.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            yield node.lineno, node.value


def test_the_server_writes_no_em_dash_into_a_sentence():
    """The house rule is no em dashes in reader-facing copy, and the pass that
    enforced it read static/ only. A bare dash standing for a missing figure is
    a table's placeholder, not copy; a regex character class is not copy; and
    feeds.py's notes on rejected feeds are the operator's, never rendered."""
    found = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        if path.name == "feeds.py":
            continue
        for line, text in _reader_strings(path):
            if "—" not in text or text.strip() == "—":
                continue
            if "[" in text and "\\s" in text:      # a pattern, not a sentence
                continue
            found.append(f"{path.relative_to(ROOT)}:{line}: {text.strip()[:70]}")
    assert not found, "\n".join(found)


def test_the_pe_bands_quote_cheap_with_quote_marks():
    """`\\\\u201c` in a plain string is a backslash and five letters, so the
    method note read `so \\u201ccheap\\u201d means cheap against itself`."""
    src = (ROOT / "app/analytics/pe_history.py").read_text()
    assert "\\\\u201c" not in src and "\\\\u201d" not in src
