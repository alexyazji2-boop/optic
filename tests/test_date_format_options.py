"""No date format mixes a style with the parts it is made of.

`dateStyle` and `timeStyle` cannot be combined with `timeZoneName`, `hour`, `month` or any other part: V8 throws
"Invalid option : option" and JavaScriptCore "dateStyle and timeStyle may not be used with other DateTimeFormat
options". The printable research sheet's footer did exactly that, so #/SYM/sheet threw on render in every browser
and stayed on its loading skeleton (investor audit, 2026-10-27). The rule is the platform's, so it is checked
everywhere a format is written, not just on that page.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FILES = sorted((ROOT / "static").rglob("*.js"))
CALL = re.compile(r"(?:toLocale(?:Date|Time)?String|DateTimeFormat)\(\s*[^,()]*,\s*\{([^{}]*)\}")
PARTS = ("weekday", "era", "year", "month", "day", "dayPeriod", "hour", "minute", "second",
         "fractionalSecondDigits", "timeZoneName")


def _mixed(opts: str) -> bool:
    keys = set(re.findall(r"(\w+)\s*:", opts))
    return bool(keys & {"dateStyle", "timeStyle"}) and bool(keys & set(PARTS))


def test_the_scan_finds_the_sheets_old_footer():
    old = "x.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short', timeZoneName: 'short' })"
    assert [m for m in CALL.findall(old) if _mixed(m)], "the pattern that broke the sheet is caught"
    assert not [m for m in CALL.findall("x.toLocaleString('en-US', { dateStyle: 'medium' })") if _mixed(m)]


def test_no_format_in_the_front_end_mixes_a_style_with_parts():
    bad = []
    for f in FILES:
        for m in CALL.findall(f.read_text(encoding="utf-8", errors="ignore")):
            if _mixed(m):
                bad.append(f"{f.relative_to(ROOT)}: {{{m.strip()}}}")
    assert not bad, bad


def test_the_sheets_footer_format_runs_in_javascriptcore(tmp_path):
    jsc = Path("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc")
    if not jsc.exists():
        pytest.skip("jsc not available")
    sheet = (ROOT / "static/v2/js/pages/sheet.js").read_text()
    m = re.search(r"Generated \$\{(new Date\(\)\.toLocaleString\([^`]*?\))\}", sheet)
    assert m, "the footer still says when the sheet was generated"
    script = tmp_path / "f.js"
    script.write_text(f"print({m.group(1)})")
    out = subprocess.run([str(jsc), str(script)], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0 and re.search(r"\d{4}(,| at) \d{1,2}:\d{2}", out.stdout), out.stdout + out.stderr
