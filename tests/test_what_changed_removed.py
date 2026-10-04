"""The "What changed since you last opened" panel is gone.

The reader said it was not useful. Its readings lived in this browser's
storage, and those are cleared once so they do not linger.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def test_the_panel_and_its_snapshots_are_gone():
    for name in ("renderWhatChanged", "priorSnapshot", "writeSnapshot", "changesBetween", "whatchanged"):
        assert name not in APP, name
    assert ".wc-block" not in CSS and ".wc-list" not in CSS


def test_the_stored_readings_are_cleared():
    assert "try { localStorage.removeItem('optic.snapshots.v1'); } catch (e)" in APP
