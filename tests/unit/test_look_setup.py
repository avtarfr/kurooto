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


def test_what_do_you_do_adds_what_suits_it_to_starter(env):
    from kurooto.web.api import ROLES, STARTER

    js, html = static("setup.js"), static("setup.html")
    for r in ("student", "working", "research", "other"):
        assert f'data-role="{r}"' in html, r
    assert "(m.roles || []).includes(role)" in js and "★ suits what you do" in js
    ids = set(env.app.modules)
    for r, extra in ROLES.items():
        assert set(extra) <= ids and not set(extra) & set(STARTER), r  # real features, none already in Starter
        assert not any(env.app.modules[i].extra for i in extra), r  # add-ons stay hand-picked


def test_setup_shows_what_matters_when_it_matters():
    js, html, css = static("setup.js"), static("setup.html"), static("style.css")
    # Notes: a new, empty folder with Kurooto's own layout folds the layout editor away and says Next is all there is
    assert "const fresh = !fit.notes && !fit.other_folder && !fit.undo" in js
    assert "nothing to fit in with" in js and "press Next." in js and "Change where each kind of note goes" in js
    assert '$(".fit-more:not([open])") ? ""' in js and "ontoggle: navHint" in js
    # Features: the daily message limit comes after the features, not before them
    feat = html.split('<section data-step="features">')[1].split("</section>")[0]
    assert feat.index('id="features"') < feat.index('id="calm-box"') < feat.index('class="nav"')
    assert ".wizard .calm { margin-top: 18px; }" in css
    # Phones: the hint beside Next gets its own line above the buttons instead of a narrow column
    phone = css.split("@media (max-width: 520px) {")[-1].split("\n}")[0]
    assert ".wizard .nav { flex-wrap: wrap; }" in phone and ".wizard .nav-hint { flex-basis: 100%; order: -1;" in phone


def test_the_channel_shown_is_the_one_picked_and_the_current_step_stays_readable_on_phones():
    js, css = static("setup.js"), static("style.css")
    assert 'b.dataset.channel === (now || "telegram")' in js  # Telegram's steps show first, so its button is on
    phone = css[css.index("@media (max-width: 520px) {\n") :]
    assert ".steps li.on button:hover { color: var(--accent-contrast); background: var(--accent); }" in phone
