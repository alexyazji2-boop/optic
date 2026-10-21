"""Dossier with no company open (owner, 2026-10-21: "pressing dossier redirects me to the search bar, fix this
issue"): the sidebar's Dossier lands on its own start page at #/dossier, which offers a search box, the companies
opened recently, the reader's watchlist and well-known names. It still does not reopen an old company by itself.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"


def test_the_address_and_the_link(tmp_path):
    got = _run(tmp_path, f"""
      const R = await import('{(JS / "core/router.js").as_posix()}');
      const N = await import('{(JS / "nav.js").as_posix()}');
      print(JSON.stringify({{ r: R.parse('#/dossier'), aapl: R.parse('#/AAPL'), group: (N.groupOf('dossierstart') || {{}}).id }}));
    """)
    assert got["r"]["view"] == "dossierstart" and got["aapl"]["view"] == "overview" and got["group"] == "security", "the Dossier section is the current one there"
    shell = (JS / "ui/shell.js").read_text()
    assert "hrefFor(page.view, symbol)) : '#/dossier';" in shell, "no company open: the start page, never the search"
    page = (JS / "pages/dossierstart.js").read_text()
    assert "group('Opened recently'" in page and "group(list ? list.name : 'Your watchlist'" in page and "group('Well-known names'" in page
    assert "palette.open(f.q, { seed: q })" in page, "a company's name goes to the search with it, to choose from"
