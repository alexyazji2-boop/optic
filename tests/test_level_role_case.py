"""Support and Resistance, capitalised where a level's role is printed.

The server sends `role` in its own lowercase vocabulary, `support` and
`resistance`, and the Key levels widget on the Charting tab printed it exactly
as it arrived. The Options tab's level tables already ran the same field
through cap(), so one terminal showed the same word two ways. Reported with a
screenshot of the widget.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _strip(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


APP = _strip((ROOT / "static/app.js").read_text())


def _fn(name: str) -> str:
    body = APP[APP.index("function " + name + "("):]
    return body[:body.index("\n}") + 2]


def test_the_key_levels_widget_capitalises_the_role():
    """It printed the server's `support` / `resistance` as they arrive. The
    Options tab's level tables already ran them through cap()."""
    body = _fn("wsWidgetBody")
    levels = body[body.index("if (id === 'levels')"):]
    levels = levels[:levels.index("if (id === 'patterns')")]
    assert "${esc(cap(l.role || ''))}" in levels
    assert "esc(l.role || '')" not in levels


def test_the_fibonacci_tooltip_capitalises_it_too():
    assert "['Role', cap(String(l.role || ''))]," in APP
    assert "['Role', String(l.role || '')]" not in APP
