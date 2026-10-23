"""0.3.0 loose ends: `kurooto note` follows the notes layout, doctor reports layout problems, and Settings → Starting
(at login or, on Linux, at boot) in the dashboard."""

import sys
from pathlib import Path

import pytest

from kurooto.app import App
from kurooto.core import autostart
from kurooto.web.api import Api


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    a = App()
    yield a
    a.close()


# ------------------------------------------------------------------------------------- kurooto note
def test_cli_note_goes_where_the_layout_puts_the_inbox(app, capsys):
    from kurooto.cli import main

    app.settings.set("notes.paths", {"inbox": "capture"})
    assert main(["note", "an idea about graphs"]) == 0
    path = Path(capsys.readouterr().out.strip())
    assert path.parent == app.workspace / "capture" and path.read_text().rstrip().endswith("an idea about graphs")


def test_cli_note_gets_the_zettelkasten_header(app, capsys):
    from kurooto.cli import main

    app.settings.set("notes.layout", "zettelkasten")
    assert main(["note", "--title", "Spectral idea", "Use", "the", "Laplacian"]) == 0
    path = Path(capsys.readouterr().out.strip())
    text = path.read_text()
    assert path.parent == app.workspace / "inbox" and text.startswith("---\nid: inbox/")
    assert "trust_tier" not in text  # your own words
    assert text.rstrip().endswith("Use the Laplacian")


# ------------------------------------------------------------------------------------- doctor
def test_doctor_reports_the_notes_layout(app):
    from kurooto import diagnostics

    assert diagnostics.layout_checks(app) == [("notes layout", True, "kurooto")]
    app.settings.set("notes.layout", "folders-please")
    app.settings.set("files.folder", str(app.workspace / "files"))
    rows = diagnostics.layout_checks(app)
    assert all(ok is False and name == "notes layout" for name, ok, _ in rows) and len(rows) == 2
    assert "isn't a layout" in rows[0][2] and "inside the notes folder" in rows[1][2]
    assert ("notes layout", False, rows[0][2]) in diagnostics.checks(app)


def test_doctor_names_the_files_folder(app, tmp_path):
    from kurooto import diagnostics

    app.settings.set("notes.layout", "zettelkasten")
    app.settings.set("files.folder", str(tmp_path / "files"))
    [(name, ok, detail)] = diagnostics.layout_checks(app)
    assert ok is True and detail.startswith("zettelkasten; files in ") and detail.endswith("files")


# ------------------------------------------------------------------------------------- Settings → Starting
def starting(api: Api) -> dict:
    code, body = api.get("settings")
    assert code == 200
    names = [s["section"] for s in body["sections"]]
    assert names.index("autostart") == names.index("power") + 1  # right after Power
    return next(s for s in body["sections"] if s["section"] == "autostart")


def test_starting_on_linux_offers_login_and_boot(app, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(autostart, "boot_possible", lambda home=None: (True, ""))
    monkeypatch.setattr(autostart, "status", lambda home=None: True)
    sec = starting(Api(app))
    assert sec["values"] == {"when": "login"} and sec["post"] == "autostart" and "fixed" not in sec
    assert [c[0] for c in sec["choices"]["when"]] == ["login", "boot"]
    assert "power cut" in sec["help"]["when"] and "doesn't start by itself" not in sec["help"]["when"]

    monkeypatch.setattr(autostart, "boot_possible", lambda home=None: (False, "Starting from boot needs systemd."))
    help_ = starting(Api(app))["help"]["when"]
    assert "needs systemd" in help_ and "doesn't start by itself" not in help_
    monkeypatch.setattr(autostart, "status", lambda home=None: False)  # off altogether: that's what matters
    help_ = starting(Api(app))["help"]["when"]
    assert "needs systemd" not in help_ and "`kurooto autostart on` turns that back on" in help_


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_starting_elsewhere_says_sign_in(app, monkeypatch, platform):
    why = {"win32": "Windows starts Kurooto when you sign in.", "darwin": "A Mac starts Kurooto when you log in."}
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(autostart, "boot_possible", lambda home=None: (False, why[platform]))
    sec = starting(Api(app))
    assert sec["fixed"] == {"when": "when you sign in"} and "choices" not in sec and "post" not in sec
    assert sec["help"]["when"] == why[platform]


def test_the_control_posts_to_autostart(app, monkeypatch):
    monkeypatch.delenv("KUROOTO_NO_AUTOSTART", raising=False)
    seen = []

    def set_when(choice, settings, secrets, state_dir, home=None):
        seen.append(choice)
        if choice == "boot":
            return False, "Linux didn't allow that from here."
        settings.set("autostart.when", choice)
        return True, "Kurooto starts when you log in."

    monkeypatch.setattr(autostart, "set_when", set_when)
    api = Api(app)
    assert api.post("autostart", {"when": "boot"}) == (
        200,
        {"ok": False, "message": "Linux didn't allow that from here.", "when": "login"},
    )
    assert api.post("autostart", {"when": "login"})[1]["ok"] is True and seen == ["boot", "login"]


def test_the_dashboard_renders_fixed_and_posted_settings():
    js = (Path(__file__).parents[2] / "src/kurooto/web/static/home.js").read_text()
    assert "sec.fixed" in js and "data-post" in js and "t.dataset.post" in js and "r.when" in js
    assert 'key === "notes.layout" ? NOTES' in js  # the notes layout is picked from a list, like the palette


# ------------------------------------------------------------------------------------- Settings: lists, not words
def test_settings_that_take_one_of_a_few_values_come_as_lists(app):
    """Your AI, its fallback, how requests are judged, updates and battery are picked from a list on the page (a
    word typed wrong there used to be saved as it was); Claude Code is named without the setup page's "Advanced"."""
    code, body = Api(app).get("settings")
    assert code == 200
    by = {s["section"]: s for s in body["sections"]}
    brain = by["brain"]["choices"]
    assert ["claude", "Claude Code"] in brain["main"] and ["", "none"] == brain["fallback"][0]
    assert [c[0] for c in brain["classify"]] == ["rules", "main", "ollama"]
    assert [c[0] for c in by["updates"]["choices"]["channel"]] == ["stable", "beta"]
    assert [c[0] for c in by["updates"]["choices"]["mode"]] == ["night", "ask", "off"]
    assert [c[0] for c in by["power"]["choices"]["on_battery"]] == ["saver", "normal", "pause"]
