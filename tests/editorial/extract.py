"""Every piece of text Optic can put in front of a reader, with where it lives (Phase 12, 2026-11-02).

Four kinds of source, read as text rather than run:

* `client`: string literals and template-literal text in the v2 scripts (`static/v2/js`), Classic's scripts
  (`static/app.js`, `static/auth.js`, `static/components/`) and the two HTML shells, plus the attributes a reader
  sees (title, aria-label, placeholder, alt). Comments are skipped: they are full of words no reader sees.
* `server`: prose-shaped string constants in `app/` that reach a page or an API answer: notes, reasons, errors,
  labels, the deterministic writers' sentences (What Matters Today, Simple Analysis, the compiled Desk).
* `prompt`: the instructions Optic gives a model (`*_PROMPT`, `POLICY_TEXT`, the level, horizon and framework
  blocks). They are not shown to readers, but every model-written sentence a reader sees comes out of them, so
  they are inventoried and traced, and the phrase rules treat them differently (a prompt may quote a banned phrase
  as the thing not to write).
* `legal`: the Terms, Privacy and disclaimer text. Inventoried and checked, never rewritten here (counsel's).

What is left out on purpose: docstrings and comments, log lines (`log.info(...)` and friends), exceptions that never
reach a reader (`raise ValueError`), SQL, regular expressions, CSS, URLs, storage keys and other identifiers. The
filter is a heuristic, written down in `_prose()`; the inventory says how many literals it read and kept.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from tests.test_client_copy_dashes import literals as js_literals

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
V2 = STATIC / "v2" / "js"
APP = ROOT / "app"

TAG = re.compile(r"<[^>]*>")
HOLE = "\u2026"                      # what a `${...}` or `{}` hole reads as in an inventoried string
ATTR = re.compile(r"""\b(title|aria-label|placeholder|alt|data-tip|aria-description)\s*=\s*(["'])(.*?)\2""", re.S)
WORD = re.compile(r"[A-Za-z][A-Za-z'\u2019-]*")
LOG_CALLS = {"debug", "info", "warning", "warn", "error", "exception", "critical"}
LOG_NAMES = {"log", "logger", "logging", "_log", "LOG"}
PROMPT_NAME = re.compile(r"(PROMPT|POLICY_TEXT|INSTRUCTION)")
# Modules whose prose is model instructions rather than reader copy (the level, horizon and framework blocks)
PROMPT_MODULES = {"app/knowledge.py": ("prompt_for", "_LEVEL_PROMPTS", "PROMPTS"),
                  "app/horizon.py": ("prompt_for",), "app/research/milo.py": ("prompt",),
                  "app/editorial.py": ("WRITING_RULES",)}
LEGAL_FILES = ("static/v2/js/core/legal.js", "static/v2/js/pages/legalpages.js")


@dataclass
class Text:
    file: str                      # repo-relative path
    line: int
    kind: str                      # client | server | prompt | legal
    text: str                      # the visible words, markup removed, holes as an ellipsis
    where: str = ""                # route or component (`route_of`)
    attr: Optional[str] = None     # the attribute it came from, for title/aria-label/placeholder text
    symbol: Optional[str] = None   # the Python constant or function it sits in
    findings: List[Dict[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------------------------- the prose filter
_CODEY = re.compile(r"^(?:[#.]?[a-z0-9_-]+(?:[ .:#>[\]=\"'*-][a-z0-9_-]*)*|[\w./:-]+\.(?:js|css|json|png|svg|html)|"
                    r"https?://\S+|/[\w/{}.:-]*|[A-Z_]{3,}|[\w.-]+\.v\d+)$")
_SQL = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|PRAGMA|WITH|DROP)\b", re.I)
_REGEXY = re.compile(r"\\[bdswBDSW]|\(\?[:=!<]|\[\^|\{\d+,?\d*\}")


def _prose(text: str, min_words: int = 2) -> bool:
    """Whether a literal reads as words for a person. Two letter-words at least (one for a capitalised label inside
    markup, handled by the caller), and not code: no CSS selector or class list, path, URL, storage key, SQL or regex."""
    t = text.strip()
    if not t or len(t) > 100000:
        return False
    if _SQL.match(t) or _REGEXY.search(t):
        return False
    if re.search(r'[\w-]="', t):            # the inside of a tag a template hole cut open: ` style="left:`
        return False
    words = WORD.findall(t)
    if len(words) < min_words:
        return False
    if _CODEY.match(t):
        return False
    # an all-lowercase run of hyphenated tokens is a class list ("btn btn-quiet sm"); a run of key:value is CSS
    if all(re.fullmatch(r"[a-z0-9_-]+", w) for w in t.split()) and any("-" in w or "_" in w for w in t.split()):
        return False
    if re.search(r"[a-z-]+\s*:\s*[^;]+;", t) and t.count(";") >= 1 and not re.search(r"[.!?]\s", t):
        return False
    letters = sum(ch.isalpha() for ch in t)
    return letters >= max(4, 0.45 * len(t.replace(HOLE, "")))


def _visible(raw: str) -> Tuple[str, List[Tuple[str, str]]]:
    """A template run's words with the markup taken out, and the reader-facing attributes found in its tags."""
    attrs = [(m.group(1), m.group(3)) for m in ATTR.finditer(raw)]
    # A template run is cut at each `${...}`, so it can start inside a tag (`" class="x">Text`) or end inside one
    # (`Text <a href="`): the half-tag at either end is markup, not words.
    first_gt, first_lt = raw.find(">"), raw.find("<")
    if first_gt >= 0 and (first_lt < 0 or first_gt < first_lt):
        raw = raw[first_gt + 1:]
    last_lt, last_gt = raw.rfind("<"), raw.rfind(">")
    if last_lt > last_gt:
        raw = raw[:last_lt]
    text = TAG.sub(" ", raw)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text, attrs


# ---------------------------------------------------------------------------------------------- client scripts
def client_files() -> List[Path]:
    files = sorted(V2.rglob("*.js"))
    files += [STATIC / "app.js", STATIC / "auth.js", *sorted((STATIC / "components").glob("*.js"))]
    return [f for f in files if f.exists()]


def _js_texts(path: Path) -> Iterator[Text]:
    return js_texts_from(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8"))


def js_texts_from(rel: str, src: str) -> Iterator[Text]:
    kind = "legal" if rel in LEGAL_FILES else "client"
    found, _ = js_literals(src)
    for line, raw in found:
        text, attrs = _visible(raw)
        if _prose(text) or (("<" in raw) and re.fullmatch(r"[A-Z][a-z]{2,}[.?]?", text or "")):
            yield Text(rel, line, kind, text)
        for name, value in attrs:
            v = re.sub(r"\s+", " ", value).strip()
            if _prose(v, 1) and "${" not in v:
                yield Text(rel, line, kind, v, attr=name)


def _html_texts(path: Path) -> Iterator[Text]:
    rel = path.relative_to(ROOT).as_posix()
    src = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"),
                 path.read_text(encoding="utf-8"), flags=re.S)
    for m in re.finditer(r">([^<]+)<", src):
        text = re.sub(r"\s+", " ", m.group(1)).strip()
        if _prose(text, 1):
            yield Text(rel, src.count("\n", 0, m.start()) + 1, "client", text)
    for m in ATTR.finditer(src):
        v = re.sub(r"\s+", " ", m.group(3)).strip()
        if _prose(v, 1):
            yield Text(rel, src.count("\n", 0, m.start()) + 1, "client", v, attr=m.group(1))
    for m in re.finditer(r'<meta\s+name="description"\s+content="([^"]+)"', src):
        yield Text(rel, src.count("\n", 0, m.start()) + 1, "client", m.group(1), attr="meta description")


# ---------------------------------------------------------------------------------------------- server code
def server_files() -> List[Path]:
    return sorted(p for p in APP.rglob("*.py") if "__pycache__" not in p.parts)


def _docstring_ids(tree: ast.AST) -> set:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _skipped_ids(tree: ast.AST) -> set:
    """Strings inside log calls and inside exceptions other than HTTPException: never shown to a reader."""
    out = set()
    for node in ast.walk(tree):
        skip = False
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr in LOG_CALLS:
                base = f.value
                name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "") if isinstance(base, ast.Attribute) else ""
                if name in LOG_NAMES or (isinstance(base, ast.Call) and getattr(base.func, "attr", "") == "getLogger"):
                    skip = True
            if isinstance(f, ast.Name) and f.id in ("print",):
                skip = True
        if isinstance(node, ast.Raise) and node.exc is not None:
            exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            name = exc.id if isinstance(exc, ast.Name) else getattr(exc, "attr", "")
            if name not in ("HTTPException",):
                skip = True
        if isinstance(node, ast.Assert):
            skip = True
        if isinstance(node, ast.Subscript):          # dict["key"] lookups
            for sub in ast.walk(node.slice if hasattr(node, "slice") else node):
                out.add(id(sub))
        if skip:
            for sub in ast.walk(node):
                out.add(id(sub))
    return out


def _joined(node: ast.JoinedStr) -> str:
    parts = []
    for v in node.values:
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            parts.append(v.value)
        else:
            parts.append(HOLE)
    return "".join(parts)


def _py_texts(path: Path) -> Iterator[Text]:
    return py_texts_from(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8"))


def py_texts_from(rel: str, src: str) -> Iterator[Text]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return
    docs, skipped = _docstring_ids(tree), _skipped_ids(tree)
    # which top-level name or function each node sits in, for the prompt test and the inventory's "symbol" column
    owner: Dict[int, str] = {}
    for top in tree.body:
        name = None
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = top.name
        elif isinstance(top, (ast.Assign, ast.AnnAssign)):
            targets = top.targets if isinstance(top, ast.Assign) else [top.target]
            name = next((t.id for t in targets if isinstance(t, ast.Name)), None)
        for sub in ast.walk(top):
            if name:
                owner.setdefault(id(sub), name)
    prompt_owners = PROMPT_MODULES.get(rel, ())
    seen_joined = set()
    for node in ast.walk(tree):
        if id(node) in docs or id(node) in skipped:
            continue
        if isinstance(node, ast.JoinedStr):
            for v in node.values:
                seen_joined.add(id(v))
            text = _joined(node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in seen_joined:
            text = node.value
        else:
            continue
        sym = owner.get(id(node))
        is_prompt = bool(sym and (PROMPT_NAME.search(sym) or sym in prompt_owners))
        text = re.sub(r"\{[^{}]*\}", HOLE, text) if "{" in text and "}" in text else text
        visible = re.sub(r"\s+", " ", text).strip()
        if not _prose(visible, 3 if not is_prompt else 2):
            continue
        yield Text(rel, getattr(node, "lineno", 0), "prompt" if is_prompt else "server", visible, symbol=sym)


# ---------------------------------------------------------------------------------------------- routes
# Which page or component a source file draws, in the reader's terms. v2 routes are the router's hash addresses.
V2_PAGES = {
    "home": "Home (#/)", "overview-simple": "Dossier Overview, Simple (#/T)", "overview-research": "Dossier Overview, Advanced (#/T)",
    "dossier": "Dossier frame and Overview (#/T)", "dossier-frame": "Dossier header (#/T/*)", "dossierstart": "Dossier start (no symbol)",
    "chart": "Chart (#/T/chart)", "chart-chrome": "Chart toolbar (#/T/chart)", "chart-studies": "Chart studies (#/T/chart)",
    "chart-widgets": "Chart side widgets (#/T/chart)", "options": "Options (#/T/options)", "options-panels": "Options panels (#/T/options)",
    "options-picker": "Options position builder (#/T/options)", "earnings": "Earnings (#/T/earnings)",
    "financials": "Financials (#/T/financials)", "valuation-scenarios": "Valuation scenarios (#/T/valuation)",
    "dcf": "Valuation, fair value (#/T/valuation)", "investing": "Investing (#/T/investing)", "news": "News (#/T/news)",
    "analysts": "Analysts (#/T/analysts)", "insiders": "Insiders (#/T/insiders)", "signals": "Signals (#/T/signals)",
    "setups": "Setups (#/T/setups)", "sheet": "Sheet (#/T/sheet)", "thesis": "Thesis (#/T/thesis)",
    "instrument": "Instrument (#/instrument/X)", "explore": "Markets: Explore (#/explore)", "macro": "Markets: Macro (#/macro)",
    "indices": "Markets: Indices (#/indices)", "read": "Markets: Read (#/read)", "market-shared": "Markets shared panels",
    "earningsweek": "Markets: Earnings this week (#/earnings-week)", "compare": "Compare (#/compare)",
    "scan": "Discover: Scan (#/scan)", "scan-shortlist": "Discover: Shortlist (#/scan)", "watchlist": "Watchlist (#/watchlist)",
    "alerts": "Alerts (#/alerts)", "paper": "Positions: Paper Desk (#/paper)", "paper-replay": "Positions: Replays (#/paper)",
    "tracker": "Positions: Tracker (#/tracker)", "brokerage": "Brokerage (#/brokerage)", "retirement": "Retirement (#/retirement)",
    "saved": "Saved research (#/saved)", "reports": "Reports (#/reports)", "settings": "Settings (#/settings)",
    "signin": "Sign in and account (#/signin)", "legalpages": "Terms and Privacy (#/terms, #/privacy)", "tabs": "Dossier tabs",
    "workspace": "Workspace", "bridge": "Classic bridge", "journal": "Journal",
}
V2_UI = {"milo": "Milo panel (every page)", "shell": "Shell: sidebar, top bar, phone bar", "palette": "Command palette",
         "levelslider": "Knowledge level slider", "states": "Loading, empty and error states", "toast": "Toasts",
         "typeahead": "Search box", "term": "Glossary terms", "glossmark": "Glossary marks", "drawer": "Drawers"}


def route_of(rel: str, symbol: Optional[str] = None) -> str:
    p = Path(rel)
    if rel.startswith("static/v2/js/pages/"):
        return "v2 " + V2_PAGES.get(p.stem, p.stem)
    if rel.startswith("static/v2/js/ui/"):
        return "v2 " + V2_UI.get(p.stem, "Component: " + p.stem)
    if rel.startswith("static/v2/js/core/"):
        return "v2 shared: " + p.stem
    if rel.startswith("static/v2/js/"):
        return "v2 app shell"
    if rel == "static/v2/index.html":
        return "v2 page shell (index.html)"
    if rel.startswith("static/"):
        return "Classic (/classic): " + p.name
    if rel == "app/ai.py":
        return "Milo and the AI writers: " + (symbol or "ai.py")
    if rel.startswith("app/"):
        return "Server: " + rel[4:] + (" " + symbol if symbol else "")
    return rel


# ---------------------------------------------------------------------------------------------- everything
def inventory() -> Tuple[List[Text], Dict[str, int]]:
    """(texts, counts) over every source. `counts` says how many files each kind read."""
    out: List[Text] = []
    counts = {"client_files": 0, "html_files": 0, "server_files": 0}
    for f in client_files():
        counts["client_files"] += 1
        out.extend(_js_texts(f))
    for f in (STATIC / "v2" / "index.html", STATIC / "index.html"):
        if f.exists():
            counts["html_files"] += 1
            out.extend(_html_texts(f))
    for f in server_files():
        counts["server_files"] += 1
        out.extend(_py_texts(f))
    for t in out:
        t.where = route_of(t.file, t.symbol)
    return out, counts


def by_kind(texts: Iterable[Text]) -> Dict[str, int]:
    got: Dict[str, int] = {}
    for t in texts:
        got[t.kind] = got.get(t.kind, 0) + 1
    return got
