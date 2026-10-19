import json

from kurooto.cli import main


def test_paths_and_doctor(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    assert main(["paths"]) == 0
    assert str(tmp_path) in capsys.readouterr().out
    assert main(["doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["problems"] == 0 and any(c["name"] == "config folder" for c in report["checks"])


def test_doctor_bundle_blanks_out_secrets_and_personal_details(env):
    import zipfile

    from kurooto import diagnostics

    app = env.app
    app.settings.set("you.name", "Samira")
    app.settings.set("notes_sync.repo", "samira/notes")
    fake_key = "AIza" + "FAKE" * 8 + "12345"  # built here so it never sits in the source as a key-shaped string
    app.secrets.set("gemini.api_key", fake_key)
    app.paths.logs.mkdir(parents=True, exist_ok=True)
    (app.paths.logs / "kurooto.log").write_text(
        f"INFO used key {fake_key} for Samira at samira@example.org "
        f"https://kurooto-abc.example.workers.dev/#t1.1760000000000.{'a' * 64} in {app.workspace}/notes\n"
    )
    app.jobs.submit("my very private question about my exam", title="private title")
    dest, names = diagnostics.bundle(app)
    assert {"doctor.json", "settings.json", "kurooto.log", "jobs.json", "events.json"} <= set(names)
    with zipfile.ZipFile(dest) as z:
        everything = "\n".join(z.read(n).decode() for n in z.namelist())
    for leaked in (
        "AIzaFAKE",
        "Samira",
        "samira",
        "example.org",
        "workers.dev",
        "t1.1760",
        str(app.workspace),
        "private question",
        "private title",
    ):
        assert leaked not in everything, leaked
    assert "[secret]" in everything and "[you]" in everything and "[notes folder]" in everything


def test_other_programs_can_message_you(env):
    from kurooto.web.api import Api

    api = Api(env.app)
    assert api.post("notify", {"text": "The backup finished.", "title": "Backup"})[1] == {"ok": True}
    assert env.fake.texts()[-1] == "Backup\n\nThe backup finished."
    assert api.post("notify", {"text": " "})[0] == 400
    assert api.post("notify", {"text": "x", "kind": "call"})[1]["ok"]  # unknown kinds become plain info


def test_notify_when_kurooto_isnt_running(env, monkeypatch, capsys):
    from kurooto.core import desktop

    shown = []
    monkeypatch.setattr(desktop, "notify", lambda title, text, urgent=False: shown.append((title, text)) or True)
    assert main(["notify", "--title", "Backup", "done"]) == 2
    assert shown == [("Backup", "done")] and "isn't running" in capsys.readouterr().err
