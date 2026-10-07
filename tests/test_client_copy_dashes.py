"""No em dash in a sentence the client draws.

The house rule ("No em dashes in user-facing copy") was enforced one module at
a time: a test per panel that grew one, each reading its own strings. The
gaps between them are where six survived, found by walking the rendered DOM of
every view: the Alerts empty state, the release calendar's tooltip, the Vanna
caveat, the MACD crossover sentence and two lines on the Paper Desk.

This reads every string and template literal in the client scripts, with the
comments skipped, because the comments are full of em dashes on purpose and
the rule is about what reaches a screen. A lone dash standing for a missing
value in a table cell is a glyph rather than punctuation, so only a dash with
words on both sides counts.
"""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"
SCRIPTS = [STATIC / "app.js", STATIC / "auth.js", *sorted((STATIC / "components").glob("*.js"))]

TAG = re.compile(r"<[^>]*>")


def dashes_in_prose(text):
    """The dashes in `text` that are punctuation. A dash is a placeholder only
    when it stands alone: the whole literal, or the whole content of an
    element, with nothing beside it, not even a space. `' \u2014 '` between
    two values is a joiner, which is the server's "XLK \u2014 Technology"."""
    marked = TAG.sub("\x00", text)
    bad = []
    for m in re.finditer("\u2014", marked):
        before = marked[m.start() - 1] if m.start() else "\x00"
        after = marked[m.end()] if m.end() < len(marked) else "\x00"
        if before != "\x00" or after != "\x00":
            bad.append(marked[max(0, m.start() - 50):m.end() + 50].replace("\x00", " "))
    return bad


# Characters after which a `/` opens a regular expression rather than divides.
REGEX_PRECEDES = set("(,=:[!&|?{};+-*%<>~^")


def literals(src):
    """(line, text) for each string literal and each text run of a template
    literal. Comments are skipped and `${...}` expressions are walked as code,
    so a string nested inside a template is returned on its own."""
    out = []
    i, n, line = 0, len(src), 1
    stack = []          # per open template: -1 in its text, else brace depth in ${}
    prev = ""
    while i < n:
        if stack and stack[-1] == -1:
            buf, start = [], line
            while i < n:
                c = src[i]
                if c == "\\":
                    buf.append(src[i:i + 2])
                    i += 2
                    continue
                if c == "`":
                    stack.pop()
                    i += 1
                    break
                if c == "$" and src[i + 1:i + 2] == "{":
                    stack[-1] = 0
                    i += 2
                    break
                if c == "\n":
                    line += 1
                buf.append(c)
                i += 1
            out.append((start, "".join(buf)))
            prev = ")"
            continue
        c = src[i]
        two = src[i:i + 2]
        if two == "//":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if two == "/*":
            j = src.find("*/", i + 2)
            end = n if j < 0 else j + 2
            line += src.count("\n", i, end)
            i = end
            continue
        if c in "'\"":
            j, buf, start = i + 1, [], line
            while j < n and src[j] != c:
                if src[j] == "\\":
                    buf.append(src[j:j + 2])
                    j += 2
                    continue
                if src[j] == "\n":
                    line += 1
                buf.append(src[j])
                j += 1
            out.append((start, "".join(buf)))
            i = j + 1
            prev = "a"
            continue
        if c == "`":
            stack.append(-1)
            i += 1
            continue
        if c == "/" and (prev in REGEX_PRECEDES or prev == ""):
            j, in_class = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                elif src[j] == "/" and not in_class:
                    break
                j += 1
            i = j + 1
            prev = "a"
            continue
        if stack and stack[-1] >= 0:
            if c == "{":
                stack[-1] += 1
            elif c == "}":
                if stack[-1] == 0:
                    stack[-1] = -1
                    i += 1
                    continue
                stack[-1] -= 1
        if c == "\n":
            line += 1
        if not c.isspace():
            prev = "a" if (c.isalnum() or c in "_$") else c
        i += 1
    return out, stack


def test_the_reader_never_sees_an_em_dash_between_words():
    offenders = []
    for path in SCRIPTS:
        found, _ = literals(path.read_text(encoding="utf-8"))
        for line, text in found:
            for snippet in dashes_in_prose(text):
                offenders.append(f"{path.name}:{line}: {' '.join(snippet.split())}")
    assert not offenders, "em dash in reader-facing copy:\n" + "\n".join(offenders)


def test_the_scanner_reads_the_whole_file_and_skips_comments():
    """A tokenizer that lost its place would pass the test above by returning
    nothing. So: every template it opened, it closed; it found the strings it
    should; and the em dashes it skipped are the ones in comments."""
    src = (STATIC / "app.js").read_text(encoding="utf-8")
    found, stack = literals(src)
    assert stack == [], "a template literal was never closed: the scan lost its place"
    texts = [t for _, t in found]
    assert len(texts) > 10000
    assert any("Everything: theme" in t or "Theme, time zone, chart preferences" in t for t in texts)
    assert src.count("—") > 500                     # the comments' own
    assert sum(t.count("—") for t in texts) < 120   # the cells' placeholders


def test_a_lone_placeholder_is_not_prose():
    assert not dashes_in_prose("\u2014")
    assert not dashes_in_prose('<td class="muted">\u2014</td>')
    assert not dashes_in_prose("</td><td>\u2014</td><td>")
    assert dashes_in_prose(" \u2014 ")                                  # a joiner
    assert dashes_in_prose('look at this again" \u2014 a level')
    assert dashes_in_prose('<span class="neg"> \u2014 wide; a real fill</span>')
    assert dashes_in_prose("s \u2014")                                   # before a ${}
