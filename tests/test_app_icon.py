"""The bookmark, tab and home-screen icon.

There was none at all: no `<link rel="icon">` and no icon file in `static/`, so
Chrome drew its generic globe beside "Optic Terminal" in the bookmarks bar.
Reported from there, which is the one place the app is seen while nobody is
looking at it.

These are shape checks on the wiring, plus real reads of the PNG headers. A
`<link>` pointing at a file that is not there is exactly as broken as no link,
and it looks identical in the markup.
"""

import json
import os
import struct

INDEX = open("static/index.html", encoding="utf-8").read()
STATIC = "static"

PNGS = {
    "apple-touch-icon.png": 180,
    "icon-192.png": 192,
    "icon-512.png": 512,
}


def png_size(path):
    """Width and height out of the IHDR, without an image library."""
    with open(path, "rb") as fh:
        head = fh.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", head[16:24])


def test_the_document_declares_an_icon():
    assert 'rel="icon" href="/icon.svg" type="image/svg+xml"' in INDEX
    assert 'rel="apple-touch-icon"' in INDEX
    assert 'rel="manifest"' in INDEX


def test_every_declared_icon_exists():
    """The failure this file is really for. A link to a missing file renders the
    same generic globe as no link at all, and nothing in the page reports it.

    512 is reached through the manifest rather than a <link>, so it is checked
    over there; everything the document names directly is checked here."""
    linked = ["icon.svg", "site.webmanifest", "icon-192.png", "apple-touch-icon.png"]
    for name in linked:
        assert os.path.exists(os.path.join(STATIC, name)), name
        assert 'href="/%s"' % name in INDEX, name
    assert os.path.exists(os.path.join(STATIC, "icon-512.png"))


def test_the_pngs_are_the_sizes_they_claim():
    """`sizes="192x192"` on a 180px file is a lie the browser acts on."""
    for name, expect in PNGS.items():
        w, h = png_size(os.path.join(STATIC, name))
        assert (w, h) == (expect, expect), "%s is %dx%d" % (name, w, h)


def test_the_svg_carries_its_own_background():
    """The header mark is a hairline over whatever the page is. As a favicon
    that fails twice: at 16px the aperture closes into a grey smudge, and a
    transparent icon inverts itself between light and dark browser chrome. So
    the tile ships its own ground and thicker strokes."""
    svg = open(os.path.join(STATIC, "icon.svg"), encoding="utf-8").read()
    assert "<rect" in svg and "#0b0a09" in svg
    assert 'viewBox="0 0 32 32"' in svg


def test_the_manifest_is_valid_json_and_names_the_app():
    m = json.load(open(os.path.join(STATIC, "site.webmanifest"), encoding="utf-8"))
    assert m["name"] == "Optic Terminal"
    assert m["short_name"]
    srcs = [i["src"].lstrip("/") for i in m["icons"]]
    for name in ["icon.svg", "icon-192.png", "icon-512.png"]:
        assert name in srcs, name
    for icon in m["icons"]:
        assert os.path.exists(os.path.join(STATIC, icon["src"].lstrip("/"))), icon


def test_the_maskable_icon_is_the_large_one():
    """Android crops a maskable icon to whatever shape the launcher uses, so the
    one it is allowed to crop has to be the one with room to lose."""
    m = json.load(open(os.path.join(STATIC, "site.webmanifest"), encoding="utf-8"))
    maskable = [i for i in m["icons"] if "maskable" in (i.get("purpose") or "")]
    assert maskable, "no maskable icon"
    assert all(i["sizes"] == "512x512" for i in maskable), maskable
