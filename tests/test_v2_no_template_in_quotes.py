"""No quoted string in the v2 front end holds `${`: a template placeholder only works inside backticks.

The Alerts page (static/v2/js/pages/alerts.js, scheduleLine) said "Prices can be ${delays.upTo()} behind the exchange"
to every signed-in reader, the code itself as text, because the sentence was a single-quoted string (round-one
corrections, 2026-11-10). Nothing failed: the file parsed and the page drew. This reads every file under static/v2/js
with a small tokenizer that knows comments, regular expressions and template literals (including the strings inside a
template's ${...}), and fails on any '...' or "..." literal that contains `${`."""
from __future__ import annotations

import re

import app.main as main

JS = main.STATIC_DIR / "v2" / "js"
# after these a `/` starts a regular expression, not a division
REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^") | {"", "return", "typeof", "case", "in", "of", "new", "delete", "void", "throw", "else", "do", "yield", "await", "=>"}
WORD = re.compile(r"[A-Za-z0-9_$]+")


def quoted_strings(src: str):
    """[(line, text)] for every single- or double-quoted string literal in `src`, outside comments, regular
    expressions and template text."""
    out, i, n = [], 0, len(src)
    stack, depth, prev = [], 0, ""

    def template(j):
        """Scan template text from j; return (index after the closing backtick, False) or (index after `${`, True)."""
        while j < n:
            ch = src[j]
            if ch == "\\":
                j += 2
                continue
            if ch == "`":
                return j + 1, False
            if src.startswith("${", j):
                return j + 2, True
            j += 1
        return n, False

    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            out.append((src.count("\n", 0, i) + 1, src[i + 1:j]))
            i, prev = j + 1, "str"
            continue
        if c == "`":
            i, expr = template(i + 1)
            if expr:
                # an expression starts after `${`, where a `/` opens a regular expression (`${/^https?:/.test(u) ? ...`)
                stack.append(depth)
                prev = "{"
            else:
                prev = "str"
            continue
        if c == "/" and prev in REGEX_AFTER:
            j, cls = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    cls = True
                elif src[j] == "]":
                    cls = False
                elif src[j] == "/" and not cls:
                    break
                j += 1
            i = j + 1
            while i < n and src[i].isalpha():
                i += 1
            prev = "str"
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            if stack and depth == stack[-1]:
                stack.pop()
                i, expr = template(i + 1)
                if expr:
                    stack.append(depth)
                    prev = "{"
                else:
                    prev = "str"
                continue
            depth -= 1
        m = WORD.match(src, i)
        if m:
            prev, i = m.group(0), m.end()
            continue
        if src.startswith("=>", i):
            prev, i = "=>", i + 2
            continue
        prev = ")" if c in ")]" else c
        i += 1
    return out


def test_the_tokenizer_finds_the_placeholder_in_a_quoted_string_and_nowhere_else():
    src = """const a = 'Prices can be ${delays.upTo()} behind';   // '${in a comment}'
const b = `fine ${x ? 'yes' : "no"} and ${`nested ${'${in a nested quote}'}`}`;
const r = /'${not a string}'/g, d = 4 / 2 / 1;
/* "${in a block comment}" */ const e = html`<p title="${t}">${'plain'}${/^h'${x}'/i.test(u) ? 'y' : ''}</p>`;"""
    found = [text for _, text in quoted_strings(src) if "${" in text]
    assert found == ["Prices can be ${delays.upTo()} behind", "${in a nested quote}"], found
    assert ("yes" in [t for _, t in quoted_strings(src)]) and ("plain" in [t for _, t in quoted_strings(src)])


def test_no_quoted_string_in_the_v2_front_end_holds_a_template_placeholder():
    files = sorted(JS.rglob("*.js"))
    assert len(files) > 50, "the walk found the front end"
    bad = [f"{p.relative_to(JS)}:{line}: {text[:80]}" for p in files for line, text in quoted_strings(p.read_text()) if "${" in text]
    assert bad == [], "a placeholder inside quotes shows as text; use backticks:\n" + "\n".join(bad)
