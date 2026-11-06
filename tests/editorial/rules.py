"""The deterministic half of Optic's editorial review (Phase 12, 2026-11-02).

Each rule names the pattern from `docs/editorial/OPTIC_WRITING_STANDARDS.md` it checks (A to J are the directive's
families: commas, repeated structure, looping, stock transitions, inflated vocabulary, hype, over-explaining,
formatting, terminology, empty conclusions; X is house rules such as em dashes) and a severity:

* `error`: a phrase that is never right in Optic's copy ("cutting-edge", "It's important to note"). The gate in
  `tests/test_editorial_standards.py` fails on these in v2 and server copy unless `allow.txt` gives a reason.
* `warn`: usually weak, sometimes right ("comprehensive", a 45-word sentence, five commas). Listed for an editor,
  never failed on: the directive says not to reject valid text on punctuation counts, and a list of five tickers
  needs its commas.
* `info`: worth a look when the copy is being edited anyway ("various", "prior to").

Model prompts are checked for structure, not phrases: a prompt has to be able to say "never write 'great question'".
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from tests.test_client_copy_dashes import dashes_in_prose

PHRASE_KINDS = ("client", "server", "legal")


@dataclass(frozen=True)
class Rule:
    id: str
    family: str          # A..J, X
    severity: str        # error | warn | info
    message: str
    suggestion: str
    pattern: Optional[re.Pattern] = None
    check: Optional[Callable[[str], List[str]]] = None
    kinds: Tuple[str, ...] = PHRASE_KINDS


def _p(rx: str) -> re.Pattern:
    return re.compile(rx, re.I)


# ------------------------------------------------------------------------------------------ phrase rules
PHRASES: List[Rule] = [
    # D. stock transitions and chatbot openers: never informative in a terminal
    Rule("D1", "D", "error", "Stock transition that announces importance instead of showing it",
         "Delete the opener and state the fact", _p(r"\b(?:it(?:'|’)?s|it is) (?:important|worth|crucial|essential) to (?:note|mention|remember|understand|highlight)\b|\bit should be noted\b|\bneedless to say\b|\bworth (?:noting|mentioning) that\b")),
    Rule("D2", "D", "error", "Generic scene-setting opener", "Start with the finding",
         _p(r"\bin today'?s (?:fast-paced|rapidly|ever|dynamic|complex|volatile)|\b(?:rapidly|ever)[- ](?:evolving|changing) (?:landscape|world|market)|\bin the (?:realm|world) of\b")),
    Rule("D3", "D", "error", "Chatbot phrasing", "Answer directly",
         _p(r"\bgreat question\b|\blet(?:'|’)?s (?:dive|delve|explore|unpack|break (?:it|this) down)\b|\bi(?:'|’)?d be (?:happy|glad) to\b|\bhappy to help\b|\bas an ai\b|\blet me walk you through\b")),
    Rule("D4", "D", "error", "Filler that claims value instead of naming it", "Say what the figure or panel shows",
         _p(r"\b(?:valuable|actionable|powerful|deep|key|unique|rich) insights?\b|\bprovides? (?:valuable )?insights? into\b|\bthis highlights the importance\b|\bunderscores the importance\b|\bplays? an? (?:crucial|vital|pivotal|key) role\b|\ba testament to\b")),
    Rule("D5", "D", "warn", "Stock framing", "Usually deletable",
         _p(r"\bwhen it comes to\b|\bat the end of the day\b|\bin terms of\b|\bthe fact that\b|\bdive into\b|\bdeep[- ]dive\b|\bdelve\b|\bnavigat(?:e|ing) the (?:complexit|nuance)")),
    # E. inflated vocabulary
    Rule("E1", "E", "warn", "Inflated word", "use / to / before / help / start / many",
         _p(r"\butili[sz](?:e|es|ed|ing)\b|(?<!capacity )\butili[sz]ation\b|\bin order to\b|\bcommenc(?:e|es|ed|ing)\b|\bfacilitat(?:e|es|ed|ing)\b|\bendeavou?r\b|\bplethora\b|\bmyriad\b|\bleverag(?:es|ing)\b|\bby leveraging\b")),
    Rule("E2", "E", "info", "Vague quantity or wordy connective", "Name the thing or the number",
         _p(r"\ba (?:wide )?(?:range|variety) of\b|\bvarious\b|\bnumerous\b|\bprior to\b|\bsubsequent(?:ly)? to\b|\bwith regard to\b|\bin relation to\b")),
    # F. marketing exaggeration
    Rule("F1", "F", "error", "Unsupported promotional claim", "Describe what the feature does",
         _p(r"\brevolutionar(?:y|ize)|\bunparalleled\b|\bgame[- ]chang(?:ing|er)\b|\bcutting[- ]edge\b|\bstate[- ]of[- ]the[- ]art\b|\bworld[- ]class\b|\bbest[- ]in[- ]class\b|\bunmatched\b|\bunrivall?ed\b|\bnext[- ]gen(?:eration)?\b|\bgroundbreaking\b|\bindustry[- ]leading\b|\blightning[- ]fast\b|\bblazing(?:ly)?[- ]fast\b|\bai[- ](?:powered|driven)\b|\bsupercharg|\bharness the power\b|\bempower(?:s|ed|ing)?\b|\bseamless(?:ly)?\b|\beffortless(?:ly)?\b|\bunleash\b")),
    Rule("F2", "F", "warn", "Promotional adjective", "Cut it, or replace it with the measurement",
         _p(r"\bpowerful\b|\bcomprehensive\b|\brobust\b|\bsophisticated\b|\bintelligent\b|\bsmart(?:er)? (?:way|insights|investing)\b|\bunlock(?:s|ing)? (?:the|your|new|insights|potential)\b|\belevate\b|\bstreamlin")),
    # J. empty conclusions
    Rule("J1", "J", "warn", "Summary that repeats what was just said", "End on the last new fact or delete",
         _p(r"(?:^|[.!?]\s+)(?:in (?:conclusion|summary|short)|to (?:sum(?: it)? up|summari[sz]e)|all in all|overall),|\bas you can see\b|\bultimately, this (?:allows|helps|means)")),
    # error and empty-state copy
    Rule("X1", "X", "warn", "Generic or apologetic error copy", "Say what failed and what to do next, without apologising",
         _p(r"\bwe (?:encountered|apologi[sz]e)\b|\bunexpected (?:issue|error)\b|\ban error (?:has )?occurred\b|\bsomething went wrong\b|\b(?:please )?try again (?:later|at a later time)\b|\bat a later time\b|\boops\b|(?:^|[.!?]\s+)(?:sorry|unfortunately),?\b")),
    Rule("X2", "X", "warn", "Link text that does not say where it goes", "Name the destination",
         _p(r"\bclick here\b|\btap here\b")),
    Rule("X3", "X", "error", "Placeholder or development text in reader copy", "Write the real copy or remove it",
         re.compile(r"\b(?:TODO|FIXME|TBD|XXX)\b|\blorem ipsum\b", re.I)),
    Rule("X4", "X", "warn", "Exclamation mark in interface copy", "Use a full stop",
         re.compile(r"[A-Za-z0-9)\]][!](?=\s|$|[\"'”])")),
    Rule("X5", "X", "warn", "Word repeated", "Delete one",
         re.compile(r"\b(?!(?:that|had|is|do|very|bye|no|ha|so|go)\b)([A-Za-z]{2,})\s+\1\b", re.I)),
    Rule("X6", "X", "warn", "Space before punctuation", "Remove the space",
         re.compile(r"[A-Za-z0-9)] [,.;:?!](?:\s|$)")),
    Rule("X8", "X", "warn", "Sentence opener that adds nothing", "Start with the subject",
         _p(r"(?:^|[.!?]\s+)(?:simply|basically|essentially|actually|obviously|clearly|of course),? ")),
]


def _em_dash(text: str) -> List[str]:
    return dashes_in_prose(text)


EM_DASH = Rule("X7", "X", "error", "Em dash in reader copy (house rule)", "Use a colon, comma, full stop or 'to'",
               check=_em_dash, kinds=("client", "server"))

# ------------------------------------------------------------------------------------------ sentence rules
SENT = re.compile(r"(?<=[.!?])[\"'”)]?\s+(?=[\"'“(]?[A-Z0-9$])")
CONTENT = re.compile(r"[a-z][a-z'-]{2,}")
STOP = set("the and for with that this from into than then they them their there these those have has had was were are "
           "is its it's not but you your yours can will would could should about which what when where while also only "
           "more most less least each every such some any all one two its our out over under after before since because "
           "being been does did done how why who whom".split())


def sentences(text: str) -> List[str]:
    return [s.strip() for s in SENT.split(text) if s.strip()]


def _words(s: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'%$.-]*", s)


def _is_list(s: str) -> bool:
    parts = [p.strip() for p in s.split(",")]
    short = sum(1 for p in parts if len(_words(p)) <= 3)
    return len(parts) >= 4 and short >= 0.6 * len(parts)


def comma_heavy(text: str) -> List[str]:
    out = []
    for s in sentences(text):
        if s.count(",") >= 4 and len(_words(s)) >= 28 and not _is_list(s):
            out.append(s)
    return out


def long_sentence(text: str) -> List[str]:
    return [s for s in sentences(text) if len(_words(s)) >= 45 and not _is_list(s)]


def _opener(s: str) -> str:
    w = [x.lower() for x in _words(s)[:2]]
    if not w:
        return ""
    return " ".join(w) if w[0] in ("the", "a", "an", "this", "it", "its") and len(w) > 1 else w[0]


def repeated_openers(text: str) -> List[str]:
    ss = sentences(text)
    out, run = [], 1
    for i in range(1, len(ss)):
        if _opener(ss[i]) and _opener(ss[i]) == _opener(ss[i - 1]):
            run += 1
            if run == 3:
                out.append(" / ".join(x[:40] for x in ss[i - 2:i + 1]))
        else:
            run = 1
    return out


def _content(s: str) -> set:
    return {w for w in CONTENT.findall(s.lower()) if w not in STOP}


def looping(text: str) -> List[str]:
    ss = [s for s in sentences(text) if len(_content(s)) >= 6]
    out = []
    for i in range(len(ss)):
        for j in range(i + 1, len(ss)):
            a, b = _content(ss[i]), _content(ss[j])
            if len(a & b) / len(a | b) >= 0.6:
                out.append(ss[i][:60] + " ... " + ss[j][:60])
    return out


SENTENCE_RULES: List[Rule] = [
    Rule("A1", "A", "warn", "Sentence with many commas", "Split it, or cut the clauses that do not change the meaning",
         check=comma_heavy),
    Rule("G1", "G", "warn", "Sentence of 45 words or more", "Split it or cut it", check=long_sentence),
    Rule("B1", "B", "warn", "Three sentences in a row open the same way", "Vary the openings or merge them",
         check=repeated_openers),
    Rule("C1", "C", "warn", "Two sentences say nearly the same thing", "Keep the clearer one", check=looping),
]

ALL_RULES: List[Rule] = PHRASES + [EM_DASH] + SENTENCE_RULES
BY_ID = {r.id: r for r in ALL_RULES}


def check(text: str, kind: str) -> List[Dict[str, str]]:
    """Findings for one text: rule id, family, severity, the matched words, the message and the suggestion."""
    found: List[Dict[str, str]] = []
    if kind == "prompt":
        return found
    for r in ALL_RULES:
        if kind not in r.kinds:
            continue
        hits: List[str] = []
        if r.pattern is not None:
            hits = [m.group(0).strip() for m in r.pattern.finditer(text)]
        elif r.check is not None:
            hits = r.check(text)
        for h in hits[:3]:
            found.append({"rule": r.id, "family": r.family, "severity": r.severity, "match": h[:160],
                          "message": r.message, "suggestion": r.suggestion})
    return found


# ------------------------------------------------------------------------------------------ the whole corpus
# I. one thing, one name. Each group's first spelling is Optic's; the others are reported where they appear.
TERMS: List[Tuple[str, List[str]]] = [
    ("sign in", [r"\blog ?in\b", r"\blog-in\b"]),
    ("sign out", [r"\blog ?out\b", r"\blog-out\b"]),
    ("watchlist", [r"\bwatch list\b"]),
    ("email", [r"\be-mail\b"]),
    ("Milo", [r"\bPulse\b(?! strip)"]),
    ("P/E", [r"\bPE ratio\b", r"\bP\.E\.\b"]),
    ("year over year", [r"\byear-on-year\b", r"\byear on year\b"]),
    ("after-hours", [r"\bafterhours\b"]),
    ("pre-market", [r"\bpremarket\b"]),
]


def terminology(texts: Iterable, kinds: Sequence[str] = ("client", "server")) -> List[Dict[str, str]]:
    out = []
    for t in texts:
        if t.kind not in kinds:
            continue
        for canonical, variants in TERMS:
            for rx in variants:
                for m in re.finditer(rx, t.text, re.I if canonical != "Milo" else 0):
                    out.append({"file": t.file, "line": t.line, "rule": "I1", "family": "I", "severity": "warn",
                                "match": m.group(0), "message": "Inconsistent term",
                                "suggestion": "Optic says '{}'".format(canonical), "text": t.text[:200]})
    return out


def duplicates(texts: Iterable, min_words: int = 8) -> List[Dict[str, object]]:
    """The same sentence-length text written out in more than one file: a copy that will drift."""
    where: Dict[str, set] = defaultdict(set)
    for t in texts:
        if t.kind in ("client", "server") and len(_words(t.text)) >= min_words:
            where[t.text].add(t.file)
    return [{"text": k, "files": sorted(v)} for k, v in where.items() if len(v) > 1]


def summary(findings: Iterable[Dict[str, str]]) -> Dict[str, Counter]:
    by_rule, by_sev = Counter(), Counter()
    for f in findings:
        by_rule[f["rule"]] += 1
        by_sev[f["severity"]] += 1
    return {"rule": by_rule, "severity": by_sev}
