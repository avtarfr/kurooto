"""The dense dashboard's panes and pages (0.5.1): any pane fills the board, the panes menu hides some (look.panes), the
pages open over the whole board with Alt keys, Features and Settings have a search box, and features that are off can
be hidden from the Features page (look.hidden_features) without changing what the API says about them. The page's
behaviour is checked in a headless browser by hand; these keep the pieces and the settings in place."""

from importlib import resources

import pytest

STATIC = resources.files("kurooto.web") / "static"


@pytest.fixture
def page():
    read = lambda name: (STATIC / name).read_text(encoding="utf-8")  # noqa: E731
    js = "".join(read(n) for n in ("views/common.js", "views/systems.js", "views/notesmap.js", "home.js"))  # one page
    return read("home.html"), js, read("home.css")


def test_the_board_has_a_panes_menu_and_a_page_over_it(page):
    html, js, css = page
    for pane in ("status", "systems", "brain", "notes", "terminal"):
        assert f'data-pane="{pane}"' in html
    assert 'id="panes-ctl"' in html and 'id="pane-page"' in html and 'id="ov-body"' in html
    assert html.count('<i class="mx"></i>') == 4  # STATUS, SYSTEMS, BRAIN, NOTES; TERMINAL's border is drawn by home.js
    assert "function applyPanes" in js and "function maxPane" in js and "function openPage" in js
    assert 'api("settings", { key: "look.panes"' in js  # the choice is a setting: other browsers see it too
    assert "one pane always stays" in js


def test_alt_keys_open_the_pages_but_a_terminal_keeps_its_own(page):
    _, js, _ = page
    keys = js.split("const PKEY = ")[1].split(";")[0]
    for tab in ("brain", "today", "activity", "jobs", "schedule", "features", "phone", "research", "about", "settings"):
        assert f"{tab}:" in keys, tab
    assert 'brain: "b"' in keys and 'features: "f"' in keys and 'settings: "s"' in keys
    letters = [part.split('"')[1] for part in keys.split(",")]
    assert len(letters) == len(set(letters)) == 10  # one key each
    assert "!inTerm(e.target)" in js  # Alt+F is a word forward in a shell
    assert "alt+f features · alt+s settings" in js  # the keys are in the borders


def test_the_pane_grid_reflows_for_what_shows(page):
    _, js, _ = page
    grid = js.split("function paneGrid")[1].split("\n}\n")[0]
    assert '"tabs", "tabs"' in grid and "minmax(440px, 34%)" in grid  # STATUS keeps its width; TERMINAL spans the rest


def test_features_and_settings_have_a_search_that_marks_what_it_found(page):
    _, js, css = page
    assert 'findBar("features", "features")' in js and 'findBar("settings", "settings")' in js
    assert "nothing matches '${q}'" in js and 'k.className = "hit"' in js and "mark.hit" in css
    assert 'e.code === "KeyF"' in js and 'e.key === "/"' in js  # Ctrl+F or / with the page open
    assert "its settings: " in js  # found by a setting, not by what the card says


def test_hidden_features_only_change_the_page(page):
    _, js, _ = page
    assert "!m.on && HIDDEN_F.has(m.id)" in js  # a feature that's on is never hidden
    assert 'key: "look.hidden_features"' in js and "Show hidden (" in js and "Unhide" in js
    assert 'tag-h">hidden</span>' in js  # a search shows hidden ones, marked


def test_dense_colours_stay_in_the_palette(page):
    _, _, css = page
    dense = [ln for ln in css.splitlines() if "body.dense" in ln and "color:" in ln]
    assert dense and not any("#" in ln for ln in dense)


def test_the_settings_are_lists_and_hiding_leaves_the_api_alone(env):
    from kurooto.web.server import start
    from tests.unit.test_dashboard import call

    app = env.app
    assert app.settings.get("look.panes") == [] and app.settings.get("look.hidden_features") == []
    srv = start(app, port=18975)
    try:
        before = [m["id"] for m in call(srv, "/api/state")[1]["modules"]]
        assert call(srv, "/api/settings", {"key": "look.panes", "value": ["notes", "status"]})[1] == {"ok": True}
        assert call(srv, "/api/settings", {"key": "look.panes", "value": "notes"})[0] == 400  # a list or nothing
        assert call(srv, "/api/settings", {"key": "look.hidden_features", "value": ["quiz"]})[1] == {"ok": True}
        look = next(s for s in call(srv, "/api/settings")[1]["sections"] if s["section"] == "look")
        assert look["values"]["panes"] == ["notes", "status"] and look["values"]["hidden_features"] == ["quiz"]
        assert [m["id"] for m in call(srv, "/api/state")[1]["modules"]] == before  # the API still lists every feature
    finally:
        srv.stop()


def test_panels_and_legends_fold_and_open_on_hover_or_l(page):
    _, js, _ = page
    assert "let LEGENDS = false" in js and 'localStorage.getItem("kurooto.dash.legends")' in js
    assert 'e.key === "l"' in js and '!document.activeElement.closest(".xterm")' in js  # not inside a terminal
    assert "inside(this.mouse, this.openRects[key])" in js and "inside(this.mouse, this.legendRect)" in js
    assert "l legends" in js  # the key is in the border


def test_r_toggles_recent_only_with_the_notes_map_on_screen_and_not_while_typing(page):
    _, js, _ = page
    line = next(ln for ln in js.splitlines() if 'e.key === "R"' in ln)
    assert 'paneShown("notes")' in line and "this.cv.getClientRects().length" in line
    rest = js[js.index(line) :][:400]
    assert '"SELECT"' in rest and "isContentEditable" in rest and '.closest(".xterm")' in rest


def test_question_mark_explains_the_board(page):
    html, js, css = page
    assert 'id="guide"' in html and "The core" in html and "Each dot" in html and "neighbourhoods" in html
    line = next(ln for ln in js.splitlines() if 'e.key === "?"' in ln)
    assert "!typing" in line  # not while typing or in a terminal
    assert "? what's this" in js and ".guide {" in css
