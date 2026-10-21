"""Markets' instrument rows open the instrument's full chart, as Classic's did (owner, 2026-10-21: "when i click the
charts here, load a subchart like i used to on the classic version"), and the chart offers a way back to the page it
was opened from (Classic's "Back to Macro"). Driven in headless Chrome by
~/Optic/work/classic-parity/macro_subchart_check.py (mouse at 1440, emulated taps at 390).
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"


def test_the_rows_and_the_way_back(tmp_path):
    mac = (JS / "pages/macro.js").read_text()
    assert '<tr class="inst-row" data-v2-inst="${r.symbol}">' in mac and 'class="inst-spark" href="#/instrument/${encodeURIComponent(r.symbol)}"' in mac
    assert "if ((b = t('tr[data-v2-inst]')) && !t('a, button, input, select, summary'))" in mac, "a press anywhere on the row, not on its own controls"
    got = _run(tmp_path, f"""
      const R = await import('{(JS / "core/router.js").as_posix()}');
      print(JSON.stringify({{ before: R.previous() }}));
    """)
    assert got["before"] is None
    ins = (JS / "pages/instrument.js").read_text()
    assert "const prev = previous(); if (!prev) return '';" in ins and "Back to ${label}" in ins and "if (r.view === 'instrument') return '';" in ins
    assert "let prevHash = null, curHash = null;" in (JS / "core/router.js").read_text()
