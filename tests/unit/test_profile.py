"""Profile sync: the encrypted profile in your own repository (a local bare repository stands in for GitHub), saving,
restoring on a fresh computer (a fresh KUROOTO_HOME), a wrong passphrase, tampered files, two computers, and that no
secret is ever written in plain text."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from kurooto.app import App
from kurooto.core import profile as core
from kurooto.modules import catalog
from kurooto.modules.overlay import AddOns
from kurooto.modules.profile import Profile, describe

PHRASE = "correct horse battery"
# token-shaped test values, put together here so the privacy scanner doesn't take them for real ones
TG_TOKEN = "123456789" + ":" + "AAH" + "q" * 32
GEMINI = "AI" + "za" + "SyTestGeminiKeyThatMustNotLeakAnywhere"
CF_LOGIN = 'oauth_token = "cf-oauth-secret-value-abcdefghij"\nrefresh_token = "cf-refresh-secret-klmnopqrst"\n'


@pytest.fixture(autouse=True)
def registered(monkeypatch):
    """Profile sync and Your add-ons in the catalog (until the coordinator registers them), and a cheap scrypt."""
    cat = list(catalog.CATALOG)
    for cls in (Profile, AddOns):
        if cls not in cat:
            cat.append(cls)
    monkeypatch.setattr(catalog, "CATALOG", cat)
    monkeypatch.setattr(core, "KDF", {"n": 2**12, "r": 8, "p": 1})


def git(cwd, *args) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def computer(monkeypatch, home: Path) -> App:
    monkeypatch.setenv("KUROOTO_HOME", str(home))
    return App()


@pytest.fixture
def bare(tmp_path) -> Path:
    r = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(r))
    return r


def setup_a(app: App, bare: Path) -> None:
    """A computer that's been used for a while."""
    s, sec = app.settings, app.secrets
    s.set("you.name", "Sam")
    s.set("you.timezone", "Europe/Berlin")
    s.set("checkins.evening", "21:30")
    s.set("telegram.chat_id", 4242)
    s.set("calls.worker", {"url": "https://k-line.example.workers.dev", "name": "k-line"})
    s.set("brain.agy.io_mode", "pty")  # this computer's own quirk
    s.set("backups.folder", "/no/such/drive/backups")  # a drive the new computer doesn't have
    sec.set("telegram.token", TG_TOKEN)
    sec.set("gemini.api_key", GEMINI)
    sec.set("calls.connector_secret", "connector-secret-0123456789abcdef")
    sec.set("web.token", "this-computers-dashboard-key")
    for mid in ("telegram", "reminders", "deadlines", "subjects"):
        ok, why = app.enable(mid)
        assert ok, why
    s.set("modules.enabled", [*s.get("modules.enabled"), "backups"])
    p = app.paths
    (p.state / "quiz").mkdir(parents=True, exist_ok=True)
    (p.state / "quiz" / "linear-algebra.json").write_text('{"items": {"q1": {"box": 3}}}', encoding="utf-8")
    (p.state / "quiz" / "session.json").write_text('{"open": true}', encoding="utf-8")  # not worth moving
    (p.state / "deadlines.json").write_text('{"items": [{"title": "Problem set 4"}]}', encoding="utf-8")
    (p.state / "observations.json").write_text('[{"text": "skips Friday check-ins"}]', encoding="utf-8")
    (p.state / "events.jsonl").write_text('{"kind": "message_in"}\n', encoding="utf-8")  # history: never moves
    (p.data / "skills").mkdir(parents=True, exist_ok=True)
    (p.data / "skills" / "routines.json").write_text('[{"id": "r1", "text": "/journal"}]', encoding="utf-8")
    (p.data / "about-you").mkdir(parents=True, exist_ok=True)
    (p.data / "about-you" / "report.md").write_text("private report", encoding="utf-8")  # promised never to sync
    cf = p.config / "cloudflare" / ".wrangler" / "config"
    cf.mkdir(parents=True, exist_ok=True)
    (cf / "default.toml").write_text(CF_LOGIN, encoding="utf-8")
    app.modules["reminders"].add(
        __import__("datetime").datetime.now() + __import__("datetime").timedelta(days=2), "call the dentist"
    )
    s.set("profile.remote", str(bare))
    ok, msg = core.connect(app, PHRASE, PHRASE, progress=lambda line: None)
    assert ok, msg
    s.set("modules.enabled", [*s.get("modules.enabled"), "profile"])


def every_file_text(root: Path) -> str:
    out = []
    for f in root.rglob("*"):
        if f.is_file():
            out.append(f.read_bytes().decode("utf-8", "replace"))
    return "\n".join(out)


# ----------------------------------------------------------------------------------------------- encryption
def test_key_locks_and_unlocks_and_refuses_wrong_or_changed():
    dek, kf = core.new_key(PHRASE)
    assert core.unlock(kf, PHRASE) == dek
    with pytest.raises(core.WrongPassphrase):
        core.unlock(kf, "not the passphrase")
    with pytest.raises(core.Damaged):  # a key file asking for a huge scrypt cost isn't even tried
        core.unlock({**kf, "n": 2**24}, PHRASE)
    with pytest.raises(core.ProfileError):
        core.new_key("short")
    env = core.seal(dek, kf["id"], "settings", b'{"a": 1}')
    assert core.unseal(dek, kf["id"], "settings", env) == b'{"a": 1}'
    with pytest.raises(core.Damaged):  # a part can't pass for another part
        core.unseal(dek, kf["id"], "secrets", env)


# --------------------------------------------------------------------------------------------- round trip
def test_save_then_restore_on_a_fresh_computer(tmp_path, monkeypatch, bare):
    a = computer(monkeypatch, tmp_path / "a")
    setup_a(a, bare)
    st = core.status(a)
    assert st["saved"] and st["counts"]["secrets"] >= 4 and st["counts"]["scheduled"] == 1
    assert "Holds" in describe(st)
    machine_a = core.local(a)["machine"]
    a.close()

    # nothing personal leaves in plain text: not in the files, not anywhere in the repository's history
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", "-b", core.BRANCH, str(bare), str(clone))
    history = git(clone, "log", "-p", "--all")
    written = every_file_text(clone) + history + every_file_text(tmp_path / "a" / "data" / "profile")
    for secret in (TG_TOKEN, GEMINI, "connector-secret-0123456789abcdef", "cf-oauth-secret", "cf-refresh-secret"):
        assert secret not in written
    for personal in ("Sam", "Europe/Berlin", "Problem set 4", "skips Friday", "call the dentist", "k-line"):
        assert personal not in written
    assert PHRASE not in written and PHRASE not in every_file_text(tmp_path / "a")
    assert sorted(p.name for p in (clone / core.FOLDER).iterdir()) == [
        "README.md",
        "key.json",
        "manifest.json",
        "secrets.enc",
        "settings.enc",
        "state.enc",
    ]
    assert git(bare, "branch", "--list").split() == [core.BRANCH]  # its own branch; main (your notes) untouched

    # a new computer: nothing but the repository and the passphrase
    b = computer(monkeypatch, tmp_path / "b")
    lines = []
    report = core.restore(b, PHRASE, remote=str(bare), progress=lines.append)
    s = b.settings
    assert s.get("you.name") == "Sam" and s.get("checkins.evening") == "21:30" and s.get("telegram.chat_id") == 4242
    assert s.get("calls.worker")["url"] == "https://k-line.example.workers.dev"
    assert s.get("brain.agy.io_mode") != "pty"  # found out again on this computer
    assert s.get("backups.folder") == ""  # that drive isn't here
    assert any("backups.folder" in n for n in report["notes"])
    assert b.secrets.get("telegram.token") == TG_TOKEN and b.secrets.get("gemini.api_key") == GEMINI
    assert b.secrets.get("calls.connector_secret") == "connector-secret-0123456789abcdef"
    assert b.secrets.get("web.token") != "this-computers-dashboard-key"  # this computer's own
    p = b.paths
    assert (p.config / "cloudflare" / ".wrangler" / "config" / "default.toml").read_text() == CF_LOGIN
    assert json.loads((p.state / "quiz" / "linear-algebra.json").read_text())["items"]["q1"]["box"] == 3
    assert not (p.state / "quiz" / "session.json").exists()
    assert "Problem set 4" in (p.state / "deadlines.json").read_text()
    assert (p.data / "skills" / "routines.json").exists() and (p.state / "observations.json").exists()
    assert not (p.state / "events.jsonl").exists() or "message_in" not in (p.state / "events.jsonl").read_text()
    assert not (p.data / "about-you").exists()
    jobs = [j for j in b.scheduler.jobs("reminders:")]
    assert len(jobs) == 1 and jobs[0].payload["what"] == "call the dentist"
    on = s.get("modules.enabled")
    assert {"telegram", "reminders", "deadlines", "subjects", "profile"} <= set(on)
    assert "backups" not in on and [x["id"] for x in report["left"]] == ["backups"]
    assert report["left"][0]["setup"] is False and report["counts"]["features"] == 5
    assert any("old computer" in n for n in report["notes"])
    assert core.local(b)["machine"] != machine_a
    assert any("Found your profile" in line for line in lines)

    # and it keeps saving from here, over the old computer's (which it took over by restoring)
    s.set("checkins.evening", "22:00")
    ok, msg = core.save(b)
    assert ok, msg
    b.close()


def test_unchanged_profile_makes_no_new_commit(tmp_path, monkeypatch, bare):
    a = computer(monkeypatch, tmp_path / "a")
    setup_a(a, bare)
    assert core.save(a) == (True, "Saved your profile.")  # Profile sync itself was turned on since
    n = len(git(bare, "log", "--format=%H", core.BRANCH).split())
    assert core.save(a) == (True, "Nothing changed since the last save.")
    assert len(git(bare, "log", "--format=%H", core.BRANCH).split()) == n
    a.settings.set("checkins.evening", "20:00")
    assert core.save(a) == (True, "Saved your profile.")
    log = git(bare, "log", "--format=%H", "--name-only", "-1", core.BRANCH)
    assert ".kurooto-profile/settings.enc" in log and ".kurooto-profile/state.enc" not in log  # only what changed
    a.close()


def test_wrong_passphrase_changes_nothing(tmp_path, monkeypatch, bare):
    a = computer(monkeypatch, tmp_path / "a")
    setup_a(a, bare)
    a.close()
    b = computer(monkeypatch, tmp_path / "b")
    before = b.settings.user()
    with pytest.raises(core.WrongPassphrase):
        core.restore(b, "not my passphrase at all", remote=str(bare), progress=lambda line: None)
    assert b.settings.user() == before and not b.secrets.get("telegram.token")
    assert not core.cached_key(b)
    b.close()


@pytest.mark.parametrize("what", ["state", "manifest", "swap", "rollback"])
def test_a_tampered_profile_is_refused(tmp_path, monkeypatch, bare, what):
    a = computer(monkeypatch, tmp_path / "a")
    setup_a(a, bare)
    old_state = git(bare, "show", f"{core.BRANCH}:{core.FOLDER}/state.enc")
    (a.paths.state / "deadlines.json").write_text('{"items": []}', encoding="utf-8")
    assert core.save(a)[0]
    a.close()
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", "-b", core.BRANCH, str(bare), str(clone))
    d = clone / core.FOLDER
    if what == "state":
        env = json.loads((d / "state.enc").read_text())
        raw = bytearray(__import__("base64").b64decode(env["data"]))
        raw[5] ^= 1
        env["data"] = __import__("base64").b64encode(bytes(raw)).decode()
        (d / "state.enc").write_text(json.dumps(env))
    elif what == "manifest":
        m = json.loads((d / "manifest.json").read_text())
        m["machine"] = "someone-else"
        (d / "manifest.json").write_text(json.dumps(m))
    elif what == "swap":
        shutil.copy(d / "secrets.enc", d / "settings.enc")
    else:  # an older (genuine) copy of a part put back
        (d / "state.enc").write_text(old_state)
    git(clone, "commit", "-qam", "changed by hand")
    git(clone, "push", "-q", "origin", core.BRANCH)
    b = computer(monkeypatch, tmp_path / "b")
    with pytest.raises(core.Damaged):
        core.restore(b, PHRASE, remote=str(bare), progress=lambda line: None)
    assert not b.secrets.get("telegram.token") and not b.settings.get("you.name")
    b.close()


def test_two_computers_never_overwrite_each_other_silently(tmp_path, monkeypatch, bare):
    a = computer(monkeypatch, tmp_path / "a")
    setup_a(a, bare)
    a.close()
    b = computer(monkeypatch, tmp_path / "b")
    b.settings.set("profile.remote", str(bare))
    with pytest.raises(core.WrongPassphrase):  # joining someone's profile needs its passphrase
        core.connect(b, "a different passphrase", "a different passphrase", progress=lambda line: None)
    ok, msg = core.connect(b, PHRASE, PHRASE, progress=lambda line: None)
    assert ok and "already there" in msg
    ok, msg = core.save(b)
    assert not ok and "another computer" in msg  # held: restore it, or save over it
    ok, msg = core.save(b, force=True)
    assert ok
    a = computer(monkeypatch, tmp_path / "a")
    ok, msg = core.save(a)  # now the first computer is the one that's behind
    assert not ok and "another computer" in msg
    assert "Another computer saved it" in describe(core.status(a))
    a.close()
    b.close()


def test_saved_soon_after_a_setting_changes(tmp_path, monkeypatch, bare):
    a = computer(monkeypatch, tmp_path / "a")
    setup_a(a, bare)
    a.modules["profile"].start()
    try:
        a.events.emit("setting_changed", key="checkins.evening")
        j = a.scheduler.get("profile:soon")
        assert j and 9 * 60 < j.next_run - time.time() <= 10 * 60
        assert a.modules["profile"].health()[0] is True
        assert a.modules["profile"]._cmd(None, "").startswith("Profile sync: on.")
    finally:
        a.modules["profile"].stop()
    a.close()


def test_restore_from_the_setup_page_turns_features_on(tmp_path, monkeypatch, bare):
    """The setup page restores inside the running assistant: features are turned on the normal way."""
    import asyncio

    from kurooto.web.api import Api

    a = computer(monkeypatch, tmp_path / "a")
    setup_a(a, bare)
    a.close()
    b = computer(monkeypatch, tmp_path / "b")
    b.settings.set("profile.remote", str(bare))
    loop = asyncio.new_event_loop()
    b._loop = loop  # as inside `kurooto run` (not running: no background tasks start)
    api = Api(b)
    try:
        code, out = api.post("profile/restore", {"passphrase": "wrong passphrase!!"})
        assert out["started"]
        for _ in range(200):
            if not api._installing:
                break
            time.sleep(0.05)
        assert "doesn't open" in api.get("profile")[1]["report"]["error"]
        code, out = api.post("profile/restore", {"passphrase": PHRASE})
        for _ in range(200):
            if not api._installing:
                break
            time.sleep(0.05)
        st = api.get("profile")[1]
        assert st["report"]["counts"]["secrets"] >= 4, api.progress
        assert b.is_on("telegram") and b.is_on("reminders") and b.is_on("profile")
        assert "backups" in st["wanted"]
    finally:
        b._loop = None
        loop.close()
        b.close()


def test_cli_restore_and_status(tmp_path, monkeypatch, bare, capsys):
    from kurooto import cli

    a = computer(monkeypatch, tmp_path / "a")
    setup_a(a, bare)
    a.close()
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "b"))
    monkeypatch.setenv(cli.PASSPHRASE, PHRASE)
    monkeypatch.setattr(cli, "wait_for_web", lambda seconds=40: None)
    assert cli.main(["profile", "restore", "--remote", str(bare), "--yes", "--no-start"]) == 0
    out = capsys.readouterr().out
    assert "Restored." in out and "Backups" in out
    assert cli.main(["profile", "status"]) == 0
    assert "Profile sync: on." in capsys.readouterr().out
    monkeypatch.setenv(cli.PASSPHRASE, "wrong wrong wrong")
    assert cli.main(["profile", "restore", "--remote", str(bare), "--yes", "--no-start"]) == 1
    assert "doesn't open" in capsys.readouterr().out


def test_cli_save_the_first_time_connects(tmp_path, monkeypatch, bare, capsys):
    from kurooto import cli

    c = computer(monkeypatch, tmp_path / "c")
    c.settings.set("profile.remote", str(bare))
    c.close()
    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: None)  # Kurooto isn't running
    monkeypatch.setenv(cli.PASSPHRASE, PHRASE)
    assert cli.main(["profile", "save"]) == 0
    assert "saved, encrypted" in capsys.readouterr().out
    assert cli.main(["profile", "save"]) == 0  # Profile sync itself was turned on since: that's a change
    assert cli.main(["profile", "save"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "Nothing changed since the last save."
    c = App()
    assert c.is_on("profile") and c.modules["profile"].ready() == (True, "")
    c.close()
