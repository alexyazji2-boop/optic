"""Classic parity, batch B4b (2026-10-21): attachments in Milo, checked in the browser and on the server. The browser's
rules run in JavaScriptCore and the server's in Python. The interactions (the file picker, drag and drop, removing,
the fifth file, sending, the server's own refusals and what the saved conversation keeps) were driven in headless
Chrome against the stand-in model (~/Optic/work/classic-parity/b4b_check.py). That is stand-in verification: the
model provider's own handling of the files was not exercised. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B4b.
"""
import base64

from app import ai
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
MILO = (JS / "ui/milo.js").read_text()
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


def test_the_browser_checks_type_size_count_and_the_files_own_bytes(tmp_path):
    got = _run(tmp_path, f"""
      globalThis.localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
      const M = await import('{(JS / "ui/milo.js").as_posix()}');
      print(JSON.stringify({{
        png: M.bytesMatch('image/png', '\\x89PNG\\r\\n\\x1a\\nIHDR'), exe: M.bytesMatch('image/png', 'MZ\\x90\\x00'), pdf: M.bytesMatch('application/pdf', '%PDF-1.7'),
        gif: M.bytesMatch('image/gif', 'GIF89a..'), webp: M.bytesMatch('image/webp', 'RIFF\\x00\\x00\\x00\\x00WEBPVP8 '), riff: M.bytesMatch('image/webp', 'RIFF\\x00\\x00\\x00\\x00WAVEfmt '),
        ok: M.attachProblem({{ type: 'image/png', size: 1000 }}, 0), txt: M.attachProblem({{ type: 'text/plain', size: 10 }}, 0),
        big: M.attachProblem({{ type: 'image/png', size: 5 * 1024 * 1024 + 1 }}, 0), fifth: M.attachProblem({{ type: 'image/png', size: 10 }}, 4), empty: M.attachProblem({{ type: 'image/png', size: 0 }}, 0),
        sizes: [M.fmtSize(74), M.fmtSize(2048), M.fmtSize(3 * 1048576)] }}));
    """)
    assert got["png"] and not got["exe"] and got["pdf"] and got["gif"] and got["webp"] and not got["riff"]
    assert got["ok"] == "" and got["txt"] == "not a PNG, JPEG, GIF, WebP or PDF"
    assert got["big"] == "larger than the 5 MB limit" and got["fifth"] == "only 4 files can go with one question" and got["empty"] == "the file is empty"
    assert got["sizes"] == ["74 bytes", "2 KB", "3.0 MB"]


def test_the_server_checks_them_again_whatever_the_browser_says():
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    blocks, problems = ai.attachment_blocks([
        {"name": "a.png", "media_type": "image/png", "data": b64(PNG)},
        {"name": "r.pdf", "media_type": "application/pdf", "data": b64(b"%PDF-1.4 x")},
        {"name": "fake.png", "media_type": "image/png", "data": b64(b"MZ\x90\x00exe")},
        {"name": "t.txt", "media_type": "text/plain", "data": b64(b"hello")},
    ])
    assert [b["type"] for b in blocks] == ["image", "document"]
    assert problems == ["fake.png: this is not a PNG file, whatever its name says", "t.txt: text/plain is not supported (PNG, JPEG, GIF, WebP or PDF)"]
    blocks, problems = ai.attachment_blocks([{"name": "b.png", "media_type": "image/png", "data": "!!!!"},
                                             {"name": "h.png", "media_type": "image/png", "data": b64(PNG + b"\0" * (ai.ATTACH_MAX_BYTES + 1))}])
    assert not blocks and problems == ["b.png: the file did not arrive whole; attach it again", "h.png: larger than the 5 MB limit"]
    blocks, problems = ai.attachment_blocks([{"name": f"{i}.png", "media_type": "image/png", "data": b64(PNG)} for i in range(6)])
    assert len(blocks) == ai.ATTACH_MAX_FILES and problems == ["only the first 4 files were sent"]


def test_refusals_reach_the_reader_and_nothing_is_kept():
    src = (V2.parent.parent / "app/ai.py").read_text()
    assert 'yield _sse("attachments", {"problems": meta["problems"][:ATTACH_MAX_FILES + 1]})' in src, "v2 keeps the list under the answer"
    assert "Nothing is written to disk." in src
    assert "else if (ev === 'attachments')" in MILO and "Not sent with this question:" in MILO
    # the saved conversation is role and content only: no file data, no file names
    persist = MILO[MILO.index("function persist()"):MILO.index("/* ---------------- state")]
    assert "({ role: m.role, content: String(m.content || '').slice(0, MAX_CHARS) })" in persist
    assert "Sent with your next question to Milo's model provider. Optic does not keep them." in MILO
    assert "if (going.length && !S.files.length) S.files = going;" in MILO, "a send that failed gives the files back"
    assert "im.src = f.thumb" in MILO and 'src="${f.thumb}"' not in MILO, "the template turns data: into #, so the thumbnail is set directly"
