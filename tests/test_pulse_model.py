"""Two models, each named once.

Switched from `claude-opus-5` to Opus 5.5 after the pricing page listed the
former under Legacy models at $5 / $25 per MTok against Opus 5.5 at $4 / $20.
Then, on 2026-09-29, Pulse alone to Sonnet 5 at the owner's request ("use
sonnet 5 for pulse, change it from Opus"): the chat panel and the live research
it runs. The pieces Optic writes and caches stayed on Opus 5.5.

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


def test_pulse_runs_on_sonnet_5():
    assert ai.PULSE_MODEL == "claude-sonnet-5"


def test_the_written_pieces_stay_on_opus_5_5():
    assert ai.MODEL == "claude-opus-5-5"


def _names_in(fn_name):
    tree = ast.parse((ROOT / "app/ai.py").read_text())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn_name)
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}


def test_pulse_asks_its_own_model_and_nothing_else_does():
    """Both of Pulse's routes, the chat and the research it runs, on
    PULSE_MODEL and never on MODEL; every writer on MODEL and never on
    PULSE_MODEL. The status the panel reads names the model that answers it."""
    for fn in ("stream_chat", "deep_research"):
        names = _names_in(fn)
        assert "PULSE_MODEL" in names and "MODEL" not in names, fn
    for fn in ("write_earnings_brief", "write_sector_read", "_write_weekly",
               "extract_catalysts", "write_catalyst_read", "write_morning_desk",
               "write_morning_read"):
        names = _names_in(fn)
        assert "MODEL" in names and "PULSE_MODEL" not in names, fn
    assert "PULSE_MODEL" in _names_in("available")


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


def _price_list_keys(tree):
    """The model ids that are keys of `PRICES` in `app/ai_store.py`.

    A price list names models without calling any of them: the usage page
    needs a price for whichever model answered, including a fallback model the
    API chose, so it lists more than the two this file pins."""
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "PRICES" \
                and isinstance(node.value, ast.Dict):
            return {id(key) for key in node.value.keys}
    return set()


def test_no_module_hardcodes_a_claude_model_id():
    """The other way a third model gets in: a string constant somewhere that
    a call later reads. Only `app/ai.py` may define one, and only as MODEL or
    PULSE_MODEL. The one exception is the price list's keys, which no call
    reads (see `_price_list_keys`)."""
    pattern = re.compile(r"^claude-(opus|sonnet|haiku|fable)[-0-9a-z.]*$")
    found = []
    for path in SOURCES:
        tree = ast.parse(path.read_text(), filename=str(path))
        prices = _price_list_keys(tree) if path.name == "ai_store.py" else set()
        for node in ast.walk(tree):
            if id(node) in prices:
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and pattern.match(node.value):
                found.append("{}:{} {!r}".format(path.name, node.lineno, node.value))
    tree = ast.parse((ROOT / "app/ai.py").read_text())
    line = {getattr(t, "id", None): n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Assign) for t in n.targets}
    assert found == ["ai.py:{} 'claude-opus-5-5'".format(line["MODEL"]),
                     "ai.py:{} 'claude-sonnet-5'".format(line["PULSE_MODEL"])], found
