"""One model, named once.

Switched from `claude-opus-5` to Opus 5.5 after the pricing page listed the
former under Legacy models at $5 / $25 per MTok against Opus 5.5 at $4 / $20.
Against Pulse's measured payload that is about 680 messages to about 850 for
the same $100 of credit.

What these guard is not the choice -- that is a product decision and will
change again -- but that making it stays a one-line edit. A second call site
naming its own model would keep the old one quietly, on exactly the calls
nobody thought to check, and the bill would say so before anything else did.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from app import ai

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted((ROOT / "app").rglob("*.py"))


def test_pulse_runs_on_opus_5_5():
    assert ai.MODEL == "claude-opus-5-5"


def test_no_call_names_a_model_of_its_own():
    """Parsed rather than grepped, so a model id inside a comment or a
    docstring -- this file's own, for one -- cannot be mistaken for a call
    argument. Any keyword `model=` in a call must pass the constant, or the
    `getattr(final, "model", MODEL)` form that reports what the API used."""
    offenders = []
    for path in SOURCES:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg == "model" and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    offenders.append("{}:{} model={!r}".format(
                        path.name, node.lineno, kw.value.value))
    assert not offenders, "a call bypasses MODEL: {}".format(offenders)


def test_no_module_hardcodes_a_claude_model_id():
    """The other way a second model gets in: a string constant somewhere that
    a call later reads. Only `app/ai.py` may define one, and only as MODEL."""
    pattern = re.compile(r"^claude-(opus|sonnet|haiku|fable)[-0-9a-z.]*$")
    found = []
    for path in SOURCES:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and pattern.match(node.value):
                found.append("{}:{} {!r}".format(path.name, node.lineno, node.value))
    assert found == ["ai.py:{} 'claude-opus-5-5'".format(
        next(n.lineno for n in ast.walk(ast.parse((ROOT / "app/ai.py").read_text()))
             if isinstance(n, ast.Assign)
             and any(getattr(t, "id", None) == "MODEL" for t in n.targets)))], found
