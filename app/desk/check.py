"""Stage 4: check a draft against its evidence before it can be kept.

An edition is a JSON object whose every unit of text is {"text", "cites"}. The
checks are deterministic and each failure names the unit and the reason:

* every unit cites evidence that exists, and a link renders beside it;
* every number in the prose matches a figure in the evidence the unit cites,
  at the precision written (5.2% matches 5.217, 5.3% does not), or a
  difference of two cited figures, which is how "the Nasdaq lagged by half a
  point" is checked;
* units agree: a yield change carried in basis points may not be written as a
  percent, and a percent may not be written as basis points;
* a result whose consensus figures disagree is not called a beat or a miss
  without saying that they disagree;
* an expected move names its expiry, is not called an earnings forecast, and
  dealer positioning is written as an estimate;
* no instructions to buy, sell or chase, no price targets, no em dashes, no
  shouting, no exclamation marks;
* nothing stale is described as today's;
* the length fits the day.
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

SECTION_IDS = ("opening", "numbers", "why", "balance", "focus", "structure", "watch", "takeaways")

ALLOWED_CAPS = set("""CPI PPI PCE FOMC GDP ETF ETFS EPS OPEC IMF WTI VIX VVIX DXY USD SEC FTC DOJ AI US USA UK EU
ECB BOJ FDA IPO CEO CFO NYSE NASDAQ S&P HY OAS ATM IV FX GLP-1 YOY MOM TSMC ASML NATO OECD API EIA BLS BEA FRED
ISM PMI JOLTS COT ADR ETF. Q1 Q2 Q3 Q4 FY CFTC CBOE CME NYMEX COMEX FINRA FDIC OCC IRS GAAP EBIT EBITDA SPDR
OPEX VWAP CNBC NPR BBC AFP""".split())

_GENERIC_HEADLINES = re.compile(r"^(markets? (mixed|update|wrap|today)|stocks? (move|mixed)|daily (update|briefing)|"
                                r"what happened today|market recap)\b", re.I)
_ADVICE = re.compile(r"\b(you should (buy|sell|short)|(buy|sell) (now|the dip|the rip)|load up|go long|go short|"
                     r"take profits|price target|time to (buy|sell)|must[- ]own|chase (the|this) (move|rally))\b", re.I)
_IMPERATIVE_TRADE = re.compile(r"^(buy|sell|short|add|trim)\b", re.I)
_SENSATIONAL = re.compile(r"\b(skyrocket\w*|bloodbath|carnage|meltdown|crash(ed|es)?|annihilat\w*|massacre)\b", re.I)
_BEAT_MISS = re.compile(r"\b(beat|beats|topped|tops|exceeded|missed|miss|misses|fell short|shortfall|surprise)\b", re.I)
_CONFLICT_SAID = re.compile(r"\b(disagree|differ|two (consensus|estimates)|depends on which|conflict)\w*", re.I)
_EXPECTED_MOVE = re.compile(r"\b(expected move|priced for (a|an|about)|straddle)\b", re.I)
_DEALER = re.compile(r"\bdealer", re.I)
_ESTIMATE_WORDS = re.compile(r"\b(estimat\w*|model\w*|assum\w*|if dealers|would)\b", re.I)
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
           "october", "november", "december"]
_MON_RE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b", re.I)

# A number as written: optional sign and currency, digits with commas, decimals,
# an optional scale word and an optional unit.
_NUM = re.compile(
    r"(?<![\w.])([-+−]?)(\$?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*"
    r"(trillion|billion|million|bn|mn|tn|k\b|thousand)?\s*"
    r"(%|percent\b|per cent\b|bp\b|bps\b|basis points?|percentage points?|pp\b|points?\b|x\b|times\b)?", re.I)


def units(edition: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    """Every {"text", "cites"} unit with a path naming where it is."""
    for key in ("summary",):
        v = edition.get(key)
        if isinstance(v, dict):
            yield key, v
    for s in edition.get("sections") or []:
        sid = s.get("id") or "?"
        for i, p in enumerate(s.get("paragraphs") or []):
            yield "{}.p{}".format(sid, i + 1), p
        for i, it in enumerate(s.get("items") or []):
            yield "{}.i{}".format(sid, i + 1), it
        for part in ("good", "bad", "unresolved"):
            for i, it in enumerate(s.get(part) or []):
                yield "{}.{}{}".format(sid, part, i + 1), it


def _decimals(s: str) -> int:
    return len(s) - 1 if s else 0


def _candidates(ev: Dict[str, Any]) -> List[Tuple[float, str]]:
    """Every figure an evidence row carries, with the unit it is in."""
    out: List[Tuple[float, str]] = []

    def add(v: Any, unit: str) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)) and math.isfinite(v):
            out.append((float(v), unit))

    u = ev.get("unit") or ""
    add(ev.get("value"), u)
    # A figure kept in thousands, millions or billions may be written out in
    # full: claims of 197.0k are "197,000".
    mult = {"k": 1e3, "m": 1e6, "$bn": 1e9, "bn": 1e9}.get(u)
    if mult:
        for key in ("value",):
            if isinstance(ev.get(key), (int, float)):
                add(ev[key] * mult, u + "*")
        comp0 = ev.get("compare") or {}
        for key in ("value", "change"):
            if isinstance(comp0.get(key), (int, float)):
                add(comp0[key] * mult, u + "*")
    comp = ev.get("compare") or {}
    add(comp.get("value"), u)
    add(comp.get("reported"), u)
    add(comp.get("level"), "level")
    add(comp.get("change"), comp.get("change_unit") or u)
    if comp.get("change_unit") == "bp" and isinstance(comp.get("change"), (int, float)):
        add(comp["change"] / 100.0, "pp")
    for k, v in (ev.get("detail") or {}).items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                add(vv, "detail")
        else:
            add(v, "detail:" + k)
    return out


def _date_numbers(text: str) -> set:
    """Spans of numbers that are dates or times, which are not figures."""
    spans = set()
    for m in re.finditer(r"\b(19|20)\d{2}\b", text):
        spans.add(m.span())
    for m in _MON_RE.finditer(text):
        spans.add(m.span(2))
    for m in re.finditer(r"\b(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|"
                         r"november|december)\b", text, re.I):
        spans.add(m.span(1))
    # Durations are method, not figures: "the previous 20 sessions", "30 days".
    for m in re.finditer(r"\b\d{1,3}\s+(trading\s+)?(sessions?|days?|weeks?|months?|years?|quarters?)\b", text, re.I):
        spans.add(m.span())
    for m in re.finditer(r"\b\d{1,2}:\d{2}\b", text):
        spans.add(m.span())
    for m in re.finditer(r"\b\d{1,2}(st|nd|rd|th)\b", text):
        spans.add(m.span())
    for m in re.finditer(r"\b[QH][1-4]\b|\bFY\d{2,4}\b|\b\d{1,3}-day\b|\b\d{1,3}-week\b|\b\d{1,2}-year\b|\b\d{1,3}-month\b|"
                         r"\b\d{2,3}-day\b|\bS&P 500\b|\bNasdaq 100\b|\bRussell 2000\b|\bDow 30\b|\b\d+ (of|out of) \d+\b",
                         text):
        spans.add(m.span())
    return spans


def _inside(span: Tuple[int, int], spans: set) -> bool:
    return any(a <= span[0] and span[1] <= b for a, b in spans)


def numbers_in(text: str) -> List[Dict[str, Any]]:
    skip = _date_numbers(text)
    out = []
    for m in _NUM.finditer(text):
        if _inside(m.span(3), skip):
            continue
        sign, cur, whole, frac, scale, unit = m.groups()
        raw = whole.replace(",", "") + (frac or "")
        try:
            val = float(raw)
        except ValueError:
            continue
        word_scale = (scale or "").lower()
        unit_l = (unit or "").lower()
        # Small bare integers are counts in prose ("three sectors", "2 banks").
        if not cur and not unit_l and not word_scale and not frac and val <= 12:
            continue
        neg = sign in ("-", "−")
        out.append({"raw": m.group(0).strip(), "value": -val if neg else val, "abs": val,
                    "decimals": _decimals(frac or ""), "currency": bool(cur),
                    "scale": word_scale, "unit": unit_l, "span": m.span()})
    return out


def _scale(n: Dict[str, Any]) -> float:
    return {"trillion": 1e12, "tn": 1e12, "billion": 1e9, "bn": 1e9, "million": 1e6, "mn": 1e6,
            "thousand": 1e3, "k": 1e3}.get(n["scale"], 1.0)


def _unit_kind(u: str) -> str:
    if u in ("%", "percent", "per cent"):
        return "%"
    if u in ("bp", "bps") or u.startswith("basis point"):
        return "bp"
    if u.startswith("percentage point") or u == "pp":
        return "pp"
    if u.startswith("point"):
        return "pts"
    if u in ("x", "times"):
        return "x"
    return ""


def _matches(n: Dict[str, Any], v: float, decimals: int) -> bool:
    target = abs(v)
    written = n["abs"] * _scale(n)
    if _scale(n) != 1.0:
        # "$1.2 billion" against 1.21e9 or against a figure kept in $bn.
        for t in (target, target * 1e9, target * 1e6, target * 1e3):
            if t and abs(written - t) / t <= 0.05:
                return True
        return False
    if decimals == 0 and written >= 1000:
        return abs(written - target) / max(target, 1e-9) <= 0.005
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    # Allow the last written digit to be one off: 5.24 written as 5.2 or 5.3
    # is rounding, as is a figure kept to two places written to one.
    return abs(round(target, decimals) - written) <= tol * 2.01


def check_number(n: Dict[str, Any], cited: List[Dict[str, Any]]) -> Optional[str]:
    """None if the number is supported by the cited evidence, else why not."""
    uk = _unit_kind(n["unit"])
    cands = []
    for e in cited:
        cands.extend(_candidates(e))
    # Differences of two cited percentages: "lagged by 0.4 points".
    pcts = [v for v, u in cands if u in ("%", "% (+/-)")]
    for i in range(len(pcts)):
        for j in range(len(pcts)):
            if i != j:
                cands.append((pcts[i] - pcts[j], "pp"))
    ok_any, unit_conflict = False, None
    for v, u in cands:
        if not _matches(n, v, n["decimals"]):
            continue
        cu = "bp" if u == "bp" else "pp" if u == "pp" else "pts" if u == "pts" else "%" if u.startswith("%") else ""
        if uk == "%" and cu in ("bp", "pts"):
            unit_conflict = "{} is a change in {} in the evidence, written as a percent".format(n["raw"], u)
            continue
        if uk == "bp" and cu not in ("bp", "pp", ""):
            unit_conflict = "{} is written in basis points but the evidence figure is in {}".format(n["raw"], u)
            continue
        ok_any = True
        break
    if ok_any:
        return None
    # A figure quoted from a cited report's own headline ("OPEC sees demand
    # growth of 2.6 million bpd"): supported by that report, as attributed.
    for e in cited:
        if e.get("kind") in ("news", "filing", "calendar"):
            hay = " ".join(str(e.get(k) or "") for k in ("label", "text")) + " " + str(
                (e.get("compare") or {}).get("headline") or "")
            bare = n["raw"].lstrip("+-\u2212$").split()[0].rstrip("%")
            if bare and re.search(r"(?<![\d.]){}(?![\d])".format(re.escape(bare)), hay):
                return None
    return unit_conflict or "{} is not a figure in the cited evidence ({})".format(
        n["raw"], ", ".join(e["id"] for e in cited) or "nothing cited")


def run(edition: Dict[str, Any], bundle: Dict[str, Any], outline: Dict[str, Any]) -> Dict[str, Any]:
    evm = {e["id"]: e for e in bundle.get("evidence") or []}
    symbols = {(e.get("symbol") or "").upper() for e in evm.values() if e.get("symbol")}
    errors: List[str] = []
    warnings: List[str] = []

    head = (edition.get("headline") or "").strip()
    if not head:
        errors.append("headline: missing")
    elif len(head) > 120:
        errors.append("headline: longer than 120 characters")
    elif _GENERIC_HEADLINES.search(head):
        errors.append("headline: generic ({})".format(head))
    if not isinstance(edition.get("summary"), dict) or not (edition["summary"].get("text") or "").strip():
        errors.append("summary: missing")
    ids = [s.get("id") for s in edition.get("sections") or []]
    for sid in ids:
        if sid not in SECTION_IDS:
            errors.append("section {}: unknown".format(sid))
    if "opening" not in ids:
        errors.append("opening: missing")
    take = next((s for s in edition.get("sections") or [] if s.get("id") == "takeaways"), None)
    if not take or not (3 <= len(take.get("items") or []) <= 5):
        errors.append("takeaways: three to five points required")

    words = 0
    numbers_checked = 0
    for path, u in units(edition):
        text = (u.get("text") or "").strip()
        if not text:
            errors.append("{}: empty".format(path))
            continue
        words += len(text.split())
        cites = [c for c in (u.get("cites") or []) if isinstance(c, str)]
        missing = [c for c in cites if c not in evm]
        if missing:
            errors.append("{}: cites evidence that does not exist ({})".format(path, ", ".join(missing)))
        cited = [evm[c] for c in cites if c in evm]
        if not cited and path not in ("summary",):
            errors.append("{}: cites nothing".format(path))
        if path == "summary" and not cited:
            errors.append("summary: cites nothing")
        if cited and not any(e.get("url") for e in cited):
            warnings.append("{}: no cited evidence carries a link".format(path))
        # Numbers.
        for n in numbers_in(text):
            numbers_checked += 1
            why = check_number(n, cited)
            if why:
                errors.append("{}: {}".format(path, why))
        # Conflicting consensus.
        if _BEAT_MISS.search(text):
            for e in cited:
                if (e.get("detail") or {}).get("consensus_conflict") and not _CONFLICT_SAID.search(text):
                    errors.append("{}: calls a beat or miss for {} although its consensus figures disagree".format(
                        path, e.get("symbol")))
        # Options language.
        if _EXPECTED_MOVE.search(text):
            opts = [e for e in cited if e.get("kind") == "options" and (e.get("detail") or {}).get("expiry")]
            if not opts:
                errors.append("{}: an expected move without the options evidence it comes from".format(path))
            else:
                exp = date.fromisoformat(opts[0]["detail"]["expiry"])
                named = (exp.isoformat() in text or
                         re.search(r"\b{}\w*\.?\s+{}\b".format(_MONTHS[exp.month - 1][:3], exp.day), text, re.I) or
                         re.search(r"\b{}\s+{}\b".format(exp.day, _MONTHS[exp.month - 1]), text, re.I) or
                         exp.strftime("%A").lower() in text.lower())
                if not named:
                    errors.append("{}: expected move without its expiry ({})".format(path, exp.isoformat()))
                if re.search(r"\bearnings\b", text, re.I) and not re.search(r"\b(not|isn't|is not)\b[^.]*\bearnings\b", text, re.I):
                    # Only an event-isolated move (the term-structure method,
                    # flagged `event_move`) may be described as an earnings move.
                    if not any((e.get("detail") or {}).get("event_move") for e in opts):
                        errors.append("{}: an expiry-wide expected move described alongside earnings".format(path))
        if _DEALER.search(text) and not _ESTIMATE_WORDS.search(text):
            errors.append("{}: dealer positioning written as fact".format(path))
        # Advice and style.
        if _ADVICE.search(text):
            errors.append("{}: reads as an instruction to trade ({})".format(path, _ADVICE.search(text).group(0)))
        if path.startswith("takeaways") and _IMPERATIVE_TRADE.search(text):
            errors.append("{}: a takeaway that tells the reader to trade".format(path))
        if "—" in text:
            errors.append("{}: em dash".format(path))
        if "!" in text:
            errors.append("{}: exclamation mark".format(path))
        # Capitals for emphasis: an all-capitals word of four or more letters
        # that is not an acronym Optic uses or a ticker in the evidence.
        named = " ".join((e.get("label") or "") + " " + (e.get("source") or "") for e in cited)
        for w in re.findall(r"\b[A-Z]{4,}\b", text):
            if w not in ALLOWED_CAPS and w not in symbols and not re.search(r"\b{}\b".format(w), named):
                errors.append("{}: capitals for emphasis ({})".format(path, w))
        if _SENSATIONAL.search(text):
            warnings.append("{}: sensational word ({})".format(path, _SENSATIONAL.search(text).group(0)))
        # Stale evidence described as today's.
        if re.search(r"\btoday('s)?\b", text, re.I):
            for e in cited:
                if e.get("stale"):
                    errors.append("{}: describes {} as today's, but its latest figure is for {}".format(
                        path, e["id"], e.get("period")))
        # A single official figure's month.
        macro = [e for e in cited if e.get("kind") == "macro" and re.match(r"^\d{4}-\d{2}", e.get("period") or "")]
        if len(macro) == 1 and len(cited) <= 2:
            month = _MONTHS[int(macro[0]["period"][5:7]) - 1]
            named = [m for m in _MONTHS if re.search(r"\b{}\b".format(m), text, re.I)]
            if named and month not in named:
                errors.append("{}: {} describes {}, but the text names {}".format(
                    path, macro[0]["id"], month.title(), ", ".join(n.title() for n in named)))

    lo, hi = outline.get("target_words") or [700, 1100]
    if words > 1300:
        errors.append("length: {} words, over 1,300".format(words))
    elif words > hi * 1.15:
        warnings.append("length: {} words, above the {} to {} target".format(words, lo, hi))
    if words < lo * 0.6:
        warnings.append("length: {} words, short for the day".format(words))
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "stats": {"words": words, "numbers_checked": numbers_checked,
                      "units": sum(1 for _ in units(edition))}}
