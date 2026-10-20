"""The top bar's session chip ("Regular session, After hours at 4 pm") stays on one line: its two parts are
spans in one inline-flex row, and no page's own class may reuse their names. Scan's "Compare the first four"
row was given `.sc-next` on 2026-10-20 and its 8px top margin pushed the chip's second half off the line."""
import re

from tests.test_frontend_v2_stage0 import V2

CHIP = {"sc-label", "sc-next"}


def test_the_chip_classes_belong_to_the_chip_alone():
    for css in (V2 / "css").glob("*.css"):
        rules = re.sub(r"/\*.*?\*/", "", css.read_text(), flags=re.S)   # comments may name the chip
        for line in rules.splitlines():
            for name in CHIP:
                for m in re.finditer(r"\.%s\b" % name, line):
                    assert line[:m.start()].rstrip().endswith(".session-chip"), f"{css.name}: {line.strip()[:90]}"
    for js in (V2 / "js").rglob("*.js"):
        src = js.read_text()
        for name in CHIP:
            if re.search(r'class="[^"]*\b%s\b' % name, src):
                assert js.name == "status.js", f"{js.name} uses {name}"
