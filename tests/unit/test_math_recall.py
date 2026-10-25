"""Recall cards typeset their maths (0.8.0): KaTeX is vendored, served from allow-listed paths, used by home.js."""

from pathlib import Path

from kurooto.web import server

STATIC = Path(server.__file__).parent / "static"


def test_katex_is_served_and_nothing_else_under_vendor():
    assert server.static("vendor/katex/katex.min.js")
    css = server.static("vendor/katex/katex.min.css").decode()
    assert "KaTeX_Main-Regular.woff2" in css and ".ttf" not in css
    assert server.static("vendor/katex/fonts/KaTeX_Main-Regular.woff2")
    for bad in (
        "vendor/katex/../server.py",
        "vendor/katex/fonts/../../home.js",
        "vendor/katex/package.json",
        "vendor/other/x.js",
    ):
        assert server.static(bad) is None


def test_recall_cards_go_through_mathhtml():
    js = (STATIC / "home.js").read_text()
    assert "mathHtml(c.text" in js and "/static/vendor/katex/katex.min.js" in js and "trust: false" in js
    assert 'sm-card"><summary><span class="k">${esc(c.section' in js and "${esc(c.text)}</p></details>" not in js
