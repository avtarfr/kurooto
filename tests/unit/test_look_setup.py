"""The setup page's guidance: words explained, what each step is for and what skipping means, errors that say how
to fix them, progress on long steps, and a bar when Kurooto stops answering (checked in a real browser; this keeps the
pieces from going missing)."""

from importlib import resources


def static(name: str) -> str:
    return resources.files("kurooto.web").joinpath("static", name).read_text(encoding="utf-8")


def test_setup_page_guides_and_explains():
    js, html, css = static("setup.js"), static("setup.html"), static("style.css")
    for word in ("API key", "token", "repository", "iCal", "MCP", "OAuth", "Cloudflare", "GBrain", "agy", "passphrase"):
        assert f'["{word}", "' in js, word  # the glossary explains it
    assert "function navHint" in js and "function working" in js and "function trouble" in js
    assert "Save and test" in js and "FIX = {" in js and "Paste your key first" in js
    assert "isn't a time zone name" in js and 'list="tz-list"' in html
    assert "Paste the token BotFather sent you first" in js and "Check the token" in html
    assert "Open the dashboard" in js and "Go back to it" in js and "alert(" not in js
    assert 'class="rail"' in html and "@media (min-width: 1100px)" in css and ".wizard .nav { position: sticky" in css
    assert "kurootoLook" in static("palette.js") and "/api/look" in static("palette.js")
