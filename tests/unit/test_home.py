"""home: backups (the zip, keeping N, restore, the CLI), sync everything (/sync all, notes pushed after AI requests
and at shutdown), research projects (project notes, the hub note, mapping, the idle-project question), runlog, watch,
logs, `kurooto top` and the doctor's new lines."""

from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

needs_git = pytest.mark.skipif(not shutil.which("git"), reason="needs git")


@pytest.fixture(autouse=True)
def nowhere_real(tmp_path_factory):
    """Even if a test loses KUROOTO_HOME, nothing reaches this computer's real folders or keychain: home, the XDG
    folders and LOCALAPPDATA point into a temporary folder, and secrets go to a file. (Its own MonkeyPatch, so a
    test's monkeypatch can't undo it.)"""
    mp = pytest.MonkeyPatch()
    home = tmp_path_factory.mktemp("home")
    mp.setenv("HOME", str(home))
    mp.setenv("USERPROFILE", str(home))
    for var in ("LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        mp.setenv(var, str(home / var.lower()))
    mp.setenv("KUROOTO_SECRETS", "file")
    yield
    mp.undo()


def git(cwd, *args, env=None):
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, **(env or {})},
    ).stdout


def wait_for(cond, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


# ================================================================================================== backups
FAKE_KEY = "-".join(["not", "a", "real", "key"])


def _fill(app):
    """Some of everything a backup might hold."""
    from kurooto.modules import backups as b

    app.settings.set("you.name", "Sam")
    app.secrets.set("gemini.api_key", FAKE_KEY)
    (app.paths.config / "cloudflare").mkdir(exist_ok=True)
    (app.paths.config / "cloudflare" / "login.json").write_text('{"token": "x"}', encoding="utf-8")
    (app.paths.data / "about-you").mkdir(exist_ok=True)
    (app.paths.data / "about-you" / "report.md").write_text("about me", encoding="utf-8")
    (app.paths.data / "kurooto-diagnostics-1.zip").write_text("old bundle", encoding="utf-8")
    (app.paths.data / "gbrain").mkdir(exist_ok=True)
    (app.paths.data / "gbrain" / "index.bin").write_bytes(b"\0" * 100)
    (app.paths.state / "web.json").write_text("{}", encoding="utf-8")
    (app.paths.state / "profile.json").write_text('{"machine": "x"}', encoding="utf-8")
    (app.paths.state / "notes.json").write_text("{}", encoding="utf-8")
    app.scheduler.at(time.time() + 3600, "x.y", key="test:one")
    ws = app.workspace
    (ws / "linear-algebra").mkdir(exist_ok=True)
    (ws / "linear-algebra" / "class-log.md").write_text("# Class log\n\nmine\n", encoding="utf-8")
    (ws / ".git").mkdir(exist_ok=True)
    (ws / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    return b


def test_the_zip_holds_settings_data_and_state_but_not_secrets(env, tmp_path):
    app = env.app
    b = _fill(app)
    out = tmp_path / "drive"
    out.mkdir()
    dest, man = b.make_zip(app.paths, out, app.workspace)
    names = set(zipfile.ZipFile(dest).namelist())
    assert "config/settings.json" in names and "state/notes.json" in names and "data/about-you/report.md" in names
    assert "state/schedule.db" in names and "data/gbrain/index.bin" in names
    assert not any(n.startswith(("notes/", "config/cloudflare")) for n in names)
    assert "config/secrets.json" not in names and "secrets.json" not in names
    assert "state/web.json" not in names and "data/kurooto-diagnostics-1.zip" not in names
    assert "state/profile.json" not in names
    assert not any(n.endswith(("-wal", "-shm")) or "/locks/" in n for n in names)
    assert man["secrets"] is False and man["notes"] is False
    # the database copy is a real, consistent database
    z = zipfile.ZipFile(dest)
    (tmp_path / "s.db").write_bytes(z.read("state/schedule.db"))
    assert sqlite3.connect(tmp_path / "s.db").execute("select key from schedule where key='test:one'").fetchone()
    assert "sign in again" in z.read("README.txt").decode()


def test_notes_and_secrets_only_when_asked(env, tmp_path):
    app = env.app
    b = _fill(app)
    out = tmp_path / "cloud"
    out.mkdir()
    dest, man = b.make_zip(app.paths, out, app.workspace, notes=True, secrets=app.secrets, index=False)
    z = zipfile.ZipFile(dest)
    names = set(z.namelist())
    assert "notes/linear-algebra/class-log.md" in names and not any(n.startswith("notes/.git") for n in names)
    assert "config/cloudflare/login.json" in names and not any(n.startswith("data/gbrain") for n in names)
    assert json.loads(z.read("secrets.json"))["gemini.api_key"] == FAKE_KEY
    assert man["secrets"] is True and "PASSWORDS AND KEYS" in z.read("README.txt").decode()


def test_keeps_the_newest_n_and_nothing_else(tmp_path):
    from kurooto.modules.backups import listing, prune

    for i in range(5):
        (tmp_path / f"kurooto-backup-2026010{i + 1}-120000.zip").write_text("z", encoding="utf-8")
    (tmp_path / "my-photos.zip").write_text("mine", encoding="utf-8")
    old_part = tmp_path / ".kurooto-backup-20250101-000000.zip.part"
    old_part.write_text("half", encoding="utf-8")
    os.utime(old_part, (time.time() - 3 * 86400, time.time() - 3 * 86400))
    gone = prune(tmp_path, 2)
    assert gone == [
        "kurooto-backup-20260101-120000.zip",
        "kurooto-backup-20260102-120000.zip",
        "kurooto-backup-20260103-120000.zip",
    ]
    assert [f.name for f in listing(tmp_path)] == [
        "kurooto-backup-20260104-120000.zip",
        "kurooto-backup-20260105-120000.zip",
    ]
    assert (tmp_path / "my-photos.zip").exists() and not old_part.exists()


def test_the_feature(env, tmp_path):
    app = env.app
    _fill(app)
    bk = app.modules["backups"]
    assert app.enable("backups")[0] is False  # no folder yet
    form = bk.setup_form()
    assert form["fields"][0]["name"] == "folder" and "yours alone" in form["intro"]
    assert bk.configure({"folder": "relative/path"})["ok"] is False
    assert bk.configure({"folder": str(tmp_path / "missing")})["ok"] is False
    assert bk.configure({"folder": str(app.workspace)})["ok"] is False  # not inside the notes
    drive = tmp_path / "drive"
    drive.mkdir()
    assert bk.configure({"folder": str(drive)})["ok"]
    env.on("backups")
    assert app.scheduler.get("backups:run").spec == "daily 03:30"
    assert bk.health()[0] is None  # no backup yet: a note, not a problem
    assert env.say("/backup").startswith("Backing up now")
    assert wait_for(lambda: any("Backed up" in t for t in env.fake.texts()))
    ok, detail = bk.health()
    assert ok is True and detail.startswith("last backup")
    assert len(list(drive.glob("kurooto-backup-*.zip"))) == 1
    assert bk.backup("scheduled") == (True, "a recent backup is still fresh")
    assert bk.catch_up() is None
    assert "kurooto-backup-" in env.say("/backups")
    # the drive is unplugged: a note for a while, a problem after three days
    shutil.rmtree(drive)
    assert bk.health()[0] is None and "isn't there now" in bk.health()[1]
    st = json.loads(bk.state_file.read_text(encoding="utf-8"))
    st["at"] -= 4 * 86400
    bk.state_file.write_text(json.dumps(st), encoding="utf-8")
    assert bk.health()[0] is False
    n = len(env.fake.texts())
    assert bk.backup("scheduled")[0] is False
    assert len(env.fake.texts()) == n + 1 and "isn't there" in env.fake.texts()[-1]
    bk.backup("scheduled")
    assert len(env.fake.texts()) == n + 1  # told once a day at most


def test_restore_puts_it_back_and_never_overwrites_a_note(env, tmp_path):
    from kurooto.core.secrets import Secrets
    from kurooto.modules import backups as b

    app = env.app
    _fill(app)
    ws = app.workspace
    (ws / "inbox").mkdir(exist_ok=True)
    (ws / "inbox" / "idea.md").write_text("an idea\n", encoding="utf-8")
    out = tmp_path / "drive"
    out.mkdir()
    dest, _ = b.make_zip(app.paths, out, ws, notes=True, secrets=app.secrets)
    # afterwards: a setting changed, a note deleted, a note rewritten, the token gone, a stale journal beside a db;
    # and Kurooto stopped (on Windows, an open database can't be replaced)
    app.close()
    app.settings.set("you.name", "Someone else")
    (ws / "inbox" / "idea.md").unlink()
    (ws / "linear-algebra" / "class-log.md").write_text("# Class log\n\nnewer text\n", encoding="utf-8")
    app.secrets.delete("gemini.api_key")
    (app.paths.state / "jobs.db-wal").write_text("stale", encoding="utf-8")
    man = b.read_manifest(dest)
    assert man["has_notes"] and man["has_secrets"]
    got = b.restore(dest, app.paths, secrets=Secrets(app.paths.config), progress=lambda s: None)
    assert app.settings.get("you.name") == "Sam"
    assert (ws / "inbox" / "idea.md").read_text(encoding="utf-8") == "an idea\n"
    assert (ws / "linear-algebra" / "class-log.md").read_text(encoding="utf-8") == "# Class log\n\nnewer text\n"
    kept = list(ws.glob("restored-*/linear-algebra/class-log.md"))
    assert len(kept) == 1 and "mine" in kept[0].read_text(encoding="utf-8")
    assert app.secrets.get("gemini.api_key") == FAKE_KEY
    assert not (app.paths.state / "jobs.db-wal").exists()
    assert got["notes_added"] >= 1 and got["notes_kept"] == 1


def test_restore_changes_nothing_while_kurooto_still_has_its_files(env, tmp_path, monkeypatch):
    from kurooto.modules import backups as b

    app = env.app
    out = tmp_path / "d"
    out.mkdir()
    dest, _ = b.make_zip(app.paths, out, None)
    names = zipfile.ZipFile(dest).namelist()
    assert "state/jobs.db" in names and not any(n.endswith(b.JOURNALS) for n in names)
    db = tmp_path / "check.db"
    db.write_bytes(zipfile.ZipFile(dest).read("state/jobs.db"))
    assert sqlite3.connect(db).execute("pragma journal_mode").fetchone()[0] == "delete"  # self-contained
    app.settings.set("you.name", "Now")
    (app.paths.state / "daemon.json").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    with monkeypatch.context() as mp:  # (never monkeypatch.undo(): it would also undo env's KUROOTO_HOME)
        mp.setattr("kurooto.core.proc.pid_alive", lambda pid, must="": True)
        with pytest.raises(b.InUse, match="running"):
            b.restore(dest, app.paths, progress=lambda s: None)
    (app.paths.state / "daemon.json").unlink()
    busy = app.paths.state / "jobs.db"
    monkeypatch.setattr(b, "_in_use", lambda files: [busy] if busy in files else [])  # Windows: held open
    with pytest.raises(b.InUse, match="jobs.db is still open"):
        b.restore(dest, app.paths, progress=lambda s: None)
    assert app.settings.get("you.name") == "Now"  # nothing was changed
    from kurooto import cli

    assert os.environ["KUROOTO_HOME"] == str(app.paths.config.parent)  # still inside the test's own folder
    assert cli.main(["restore", str(dest), "--yes", "--no-start"]) == 1  # "Nothing was restored"
    assert app.settings.get("you.name") == "Now"


def test_files_held_open_are_found(tmp_path):
    from kurooto.modules import backups as b

    f = tmp_path / "a.db"
    f.write_bytes(b"x")
    assert b._in_use([f, tmp_path / "missing.db"]) == []  # free (and a missing one is fine)
    assert f.read_bytes() == b"x" and not list(tmp_path.glob("*.restore-check"))


def test_restore_from_another_kind_of_computer_uses_the_default_notes_folder(env, tmp_path):
    from kurooto.modules import backups as b

    app = env.app
    app.settings.set("you.workspace", "Q:\\Notes\\Kurooto" if os.name != "nt" else "/srv/notes")
    out = tmp_path / "d"
    out.mkdir()
    dest, _ = b.make_zip(app.paths, out, None)
    app.close()
    got = b.restore(dest, app.paths, progress=lambda s: None)
    assert app.settings.get("you.workspace") == "" and got["workspace"]


def test_a_zip_that_writes_outside_is_refused(tmp_path):
    from kurooto.modules.backups import read_manifest

    for bad in ("../evil.txt", "/etc/x", "config/../../x", "elsewhere/x", "C:/x"):
        z = tmp_path / "bad.zip"
        with zipfile.ZipFile(z, "w") as zz:
            zz.writestr("manifest.json", "{}")
            zz.writestr(bad, "x")
        with pytest.raises(ValueError):
            read_manifest(z)
    with zipfile.ZipFile(tmp_path / "plain.zip", "w") as zz:
        zz.writestr("config/settings.json", "{}")
    with pytest.raises(ValueError, match="isn't a Kurooto backup"):
        read_manifest(tmp_path / "plain.zip")


def test_backup_and_restore_commands(env, tmp_path, monkeypatch, capsys):
    from kurooto import cli

    app = env.app
    _fill(app)
    assert cli.main(["backup"]) == 1 and "No backup folder" in capsys.readouterr().out
    drive = tmp_path / "usb"
    drive.mkdir()
    assert cli.main(["backup", "--to", str(drive)]) == 0
    zips = list(drive.glob("kurooto-backup-*.zip"))
    assert len(zips) == 1 and json.loads((app.paths.state / "backups.json").read_text(encoding="utf-8"))["ok"]
    calls = []
    monkeypatch.setattr(cli, "stop_gracefully", lambda timeout=90: calls.append("graceful") or True)
    monkeypatch.setattr(cli, "stop", lambda quiet=False: calls.append("stop"))
    monkeypatch.setattr(cli, "start_background", lambda: calls.append("start") or 0)
    monkeypatch.setattr(cli, "wait_for_web", lambda s=0: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert cli.main(["restore", str(zips[0])]) == 1 and calls == []  # said no: nothing happens
    app.close()  # as if stopped (on Windows, an open database can't be replaced)
    app.settings.set("you.name", "Changed")
    assert cli.main(["restore", str(zips[0]), "--yes"]) == 0
    assert calls == ["graceful", "stop", "start"] and app.settings.get("you.name") == "Sam"
    assert list((app.paths.data / "restore-safety").glob("kurooto-backup-*.zip"))
    assert cli.main(["restore", str(tmp_path / "nope.zip"), "--yes"]) == 1


# =================================================================================== stopping before a restore
FAKE_DAEMON = """import signal, sys, time
out, polite = sys.argv[1], sys.argv[2] == 'polite'
def term(*a):
    open(out, 'w').write('graceful')
    sys.exit(0)
signal.signal(signal.SIGTERM, term if polite else signal.SIG_IGN)
open(out + '.up', 'w').write('up')
time.sleep(60)
"""


def _fake_daemon(app, tmp_path, polite):
    out = tmp_path / f"{polite}.txt"
    p = subprocess.Popen([sys.executable, "-c", FAKE_DAEMON, str(out), polite, "kurooto"])
    assert wait_for(lambda: Path(f"{out}.up").exists())
    (app.paths.state / "daemon.json").write_text(json.dumps({"pid": p.pid}), encoding="utf-8")
    return p, out


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM; on Windows the page's power/stop is the only way")
def test_stop_asks_first_and_forces_only_after_the_timeout(env, tmp_path, monkeypatch):
    from kurooto import cli

    app = env.app
    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: None)  # its page doesn't answer
    p, out = _fake_daemon(app, tmp_path, "polite")
    assert cli.stop_gracefully(10) is True and out.read_text(encoding="utf-8") == "graceful"
    p.wait(5)
    p, out = _fake_daemon(app, tmp_path, "stubborn")  # ignores the request
    t0 = time.monotonic()
    assert cli.stop_gracefully(1) is False and 0.9 < time.monotonic() - t0 < 5 and p.poll() is None
    cli.stop(quiet=True)  # then it's forced
    assert p.wait(5) is not None and not out.exists()
    # its page answers: that's how it's asked (and on Windows the only way)
    p, out = _fake_daemon(app, tmp_path, "polite")
    asked = []
    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: asked.append(path) or p.terminate() or {"ok": 1})
    assert cli.stop_gracefully(10) is True and asked == ["power/stop"]
    (app.paths.state / "daemon.json").unlink()
    assert cli.stop_gracefully(1) is True  # not running


def test_the_page_can_stop_it_the_normal_way(env, monkeypatch):
    from kurooto.web.api import Api

    stopped = []
    monkeypatch.setattr(env.app, "request_stop", lambda: stopped.append(1))
    assert Api(env.app).post("power/stop", {})[1]["ok"] is True
    assert wait_for(lambda: stopped == [1])


@needs_git
@pytest.mark.skipif(sys.platform == "win32", reason="runs a real daemon process")
def test_a_real_daemon_sends_up_its_notes_when_stopped_for_a_restore(env, tmp_path):
    from kurooto import cli

    app = env.app
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    app.settings.set("notes_sync.remote", str(remote))
    app.settings.set("web.port", 18960)
    (app.workspace / "a.md").write_text("# A\n", encoding="utf-8")
    assert app.modules["notes_sync"].first_sync()[0]
    env.on("notes_sync")
    app.settings.set("modules.enabled", ["notes_sync"])  # only it: no Telegram in the real daemon
    (app.workspace / "late.md").write_text("# Written just before the restore\n", encoding="utf-8")
    log = open(tmp_path / "daemon.log", "w", encoding="utf-8")
    d = subprocess.Popen([sys.executable, "-m", "kurooto", "run"], stdout=log, stderr=log, env={**os.environ})
    try:
        assert cli.wait_for_web(60), (tmp_path / "daemon.log").read_text(encoding="utf-8")[-2000:]
        assert cli.stop_gracefully(90) is True
        assert d.wait(10) == 0
    finally:
        if d.poll() is None:
            d.kill()
    files = git(tmp_path, "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main")
    assert "late.md" in files  # Notes sync's shutdown step ran before it stopped


# ============================================================================================ sync everything
def test_sync_everything_runs_whats_on_in_order(env, monkeypatch):
    from kurooto.core import syncall

    app = env.app
    ran = []
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "calendar", "research", "gbrain"])
    monkeypatch.setattr(app.modules["calendar"], "refresh", lambda p=None: ran.append("calendar") or 12)
    monkeypatch.setattr(app.modules["research"], "project_logs", lambda: ran.append("research") or 0)

    def boom(p=None):
        ran.append("gbrain")
        raise RuntimeError("index locked")

    monkeypatch.setattr(app.modules["gbrain"], "sync", boom)
    res = syncall.run(app)
    assert ran == ["calendar", "research", "gbrain"]
    assert res == [
        ("Calendar", True, "12 events"),
        ("Research", True, "no new commits"),
        ("Notes brain", False, "RuntimeError: index locked"),
    ]
    text = syncall.summary(res)
    assert text.startswith("Synced everything that's on (2 ok, 1 failed):") and "Calendar: ok, 12 events" in text


def test_sync_everything_from_telegram(env, monkeypatch):
    from kurooto.core import syncall

    for t in ("sync everything", "Sync all", "/sync all", "please sync everything now", "sync it all"):
        assert syncall.wanted(t), t
    for t in ("sync my notes", "sync everything and call me", "what does sync all do"):
        assert not syncall.wanted(t), t
    assert env.say("sync everything").startswith("Nothing to sync")
    assert env.say("/sync").startswith("Nothing to sync")  # Notes sync is off, so /sync is sync everything
    app = env.app
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "calendar"])
    monkeypatch.setattr(app.modules["calendar"], "refresh", lambda p=None: 3)
    assert env.say("sync everything") == "Syncing Calendar. I'll send one line each when it's done."
    assert wait_for(lambda: "Calendar: ok, 3 events" in (env.fake.texts()[-1] or ""))
    assert syncall.status(app)["running"] is False
    assert "/sync  sync everything" in env.say("/help")


@needs_git
def test_notes_go_up_after_ai_requests_and_at_shutdown(env, tmp_path, monkeypatch):
    app = env.app
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    app.settings.set("notes_sync.remote", str(remote))
    ns = app.modules["notes_sync"]
    (app.workspace / "a.md").write_text("# A\n", encoding="utf-8")
    assert ns.first_sync()[0]
    env.on("notes_sync")
    app.events.emit("job_done", job="j1", ok=True)
    first = app.scheduler.get("notes_sync:soon")
    assert first is not None and 100 < first.next_run - time.time() <= 120
    app.events.emit("job_done", job="j2", ok=True)
    assert app.scheduler.get("notes_sync:soon").next_run == first.next_run  # one push for a burst
    # /sync all goes to everything, /sync to the notes
    monkeypatch.setattr("kurooto.core.syncall.start", lambda a, notify=True: (True, "started everything"))
    assert env.say("/sync all") == "started everything"
    (app.workspace / "b.md").write_text("# B\n", encoding="utf-8")
    assert env.say("/sync") == "Notes synced."
    ns.stop()  # turning it off removes the listener
    app.events.emit("job_done", job="j3", ok=True)
    assert app.scheduler.get("notes_sync:soon") is None
    ns.start()
    # at shutdown (the assistant stopping, not a command): what's left goes up, and the listener goes
    (app.workspace / "c.md").write_text("# C\n", encoding="utf-8")
    calls = []
    real = ns.sync
    monkeypatch.setattr(ns, "sync", lambda quick=False: calls.append(quick) or real(quick=quick))
    app._stop = object()
    app.close()
    app._stop = None
    assert calls == [True] and ns._unsub is None
    assert "c.md" in git(tmp_path, "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main")


# ============================================================================================ research projects
def _repo(tmp_path, name="my-model", days_ago=0):
    repo = tmp_path / name
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    when = time.strftime("%Y-%m-%dT12:00:00", time.localtime(time.time() - days_ago * 86400))
    for msg in ("add the model", "fit the closure"):
        (repo / "f.txt").write_text(msg, encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", msg, env={"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})
    return repo


@needs_git
def test_projects_mapping_and_the_hub_note(env, tmp_path):
    from kurooto.modules.research import log_lines

    app = env.app
    app.settings.set("research.topics", ["x"])
    env.on("research")
    repo = _repo(tmp_path, "model_v2")
    out = env.say(f"/repos add {repo} as Climate model")
    assert "→ Climate model" in out
    r = app.modules["research"]
    assert r.project_of(repo) == "Climate model" and r.projects() == {"Climate model": [str(repo)]}
    assert r.project_logs() == 1
    note = app.workspace / "research" / "climate-model" / "index.md"
    text = note.read_text(encoding="utf-8")
    assert "git:model_v2 — 2 commits: add the model; fit the closure" in text
    hub = (app.workspace / "research" / "index.md").read_text(encoding="utf-8")
    assert "[[research/climate-model/index|Climate model]]" in hub
    # your own words stay as they are; lines are only added
    note.write_text(
        text.replace("Notes on this project go here.", "My plan: test the closure.") + "\n## Ideas\n\nmine\n",
        encoding="utf-8",
    )
    log_lines(app.workspace, "Climate model", ["- **2026-10-20** | you — a line"])
    after = note.read_text(encoding="utf-8")
    assert "My plan: test the closure." in after and after.index("a line") < after.index("## Ideas")
    assert after.endswith("## Ideas\n\nmine\n")
    assert r.health()[0] is True
    shutil.rmtree(repo)
    assert r.health() == (False, f"repository folder missing: {repo} (/repos remove it, or put it back)")


@needs_git
def test_a_quiet_project_gets_one_question(env, tmp_path):
    app = env.app
    app.settings.set("research.topics", ["x"])
    env.on("research")
    repo = _repo(tmp_path, "solver", days_ago=6)
    env.say(f"/repos add {repo}")
    r = app.modules["research"]
    assert r.idle_check() == ["solver"]
    assert r.idle_check() == []  # once per quiet stretch
    q = [q for q in app.ask.pending() if q["source"] == "research"]
    assert len(q) == 1 and "No commits to solver for 6 days" in q[0]["text"]
    assert q[0]["choices"] == ["Busy", "Working off-git", "Remind me tomorrow", "Pausing it"]
    app.ask.answer(q[0]["id"], "Remind me tomorrow", "test")
    assert app.scheduler.get("research:remind:solver") is not None
    log = (app.workspace / "research" / "solver" / "index.md").read_text(encoding="utf-8")
    assert "| you — Remind me tomorrow" in log
    r._remind({"project": "solver"})
    assert "remind you about solver" in env.fake.texts()[-1]
    app.settings.set("research.idle_days", 0)
    assert r.idle_check() == []


# ================================================================================================== runlog
@needs_git
def test_runlog_keeps_config_git_state_metrics_and_a_log_line(env, tmp_path, monkeypatch):
    from kurooto.runlog import RunError, Runlog, parse_values

    app = env.app
    repo = _repo(tmp_path, "fitter")
    (repo / "f.txt").write_text("uncommitted change", encoding="utf-8")
    rl = Runlog(app.paths, app.workspace)
    rid = rl.start("Fitter", "stress test", {"F": 24}, repo)
    d = app.workspace / "research" / "fitter" / "runs" / rid
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    assert meta["dirty"] is True and len(meta["commit"]) == 40 and meta["status"] == "running"
    assert "uncommitted change" in (d / "diff.patch").read_text(encoding="utf-8")
    assert json.loads((d / "config.json").read_text(encoding="utf-8")) == {"F": 24}
    rl.metric(parse_values(["loss=0.5", "acc=0.75"]), step=1)
    rl.metric(parse_values(["loss=0.25", "note=diverged"]), step=2)
    rl.note("blew up at t=812")
    assert parse_values(["n=3"]) == {"n": 3}
    with pytest.raises(RunError):
        parse_values(["oops"])
    monkeypatch.setenv("KUROOTO_RUN", rid[-6:])  # a unique end of the id is enough
    r = rl.end("failed")
    assert r["status"] == "failed" and r["last"]["loss"] == 0.25
    rows = (d.parent / "index.csv").read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("run,start") and rid in rows[1]
    log = (app.workspace / "research" / "fitter" / "index.md").read_text(encoding="utf-8")
    assert "run:stress test — failed after" in log and f"runs/{rid}/run|details" in log
    assert "## Result" in (d / "run.md").read_text(encoding="utf-8") and "blew up" in (d / "notes.md").read_text(
        encoding="utf-8"
    )
    with pytest.raises(RunError, match="already ended"):
        rl.end("ok", rid)
    monkeypatch.delenv("KUROOTO_RUN")
    with pytest.raises(RunError, match="no run going"):
        rl.metric({"x": 1})
    assert [x["run"] for x in rl.ls("Fitter")] == [rid]


def test_runlog_command(env, capsys):
    from kurooto import cli

    assert cli.main(["runlog", "start", "demo", "--config", "[1]"]) == 2
    assert "JSON object" in capsys.readouterr().out
    assert cli.main(["runlog", "start", "demo", "--name", "a", "--config", '{"lr": 0.1}']) == 0
    rid = capsys.readouterr().out.strip()
    assert cli.main(["runlog", "metric", "loss=1.5", "--step", "3"]) == 0
    assert cli.main(["runlog", "note", "all", "good"]) == 0
    assert cli.main(["runlog", "end"]) == 0 and rid in capsys.readouterr().out
    assert cli.main(["runlog", "ls"]) == 0 and "loss=1.5" in capsys.readouterr().out


# ======================================================================================================= watch
def test_watch_passes_output_through_and_reports(env, tmp_path):
    from kurooto import watch

    out = io.BytesIO()
    code, text = watch.run(
        [sys.executable, "-c", "import sys; print('step 1'); print('\\x1b[31mred\\x1b[0m'); sys.exit(3)"], 2, out=out
    )
    assert code == 3 and b"step 1" in out.getvalue()
    head, _, rest = text.partition("\n\nLast lines:\n")
    assert head.startswith("Failed: python") and "(exit 3)" in head
    assert rest.splitlines() == ["step 1", "red"]
    code, text = watch.run([sys.executable, "-c", "print('ok')"], 0, out=io.BytesIO())
    assert code == 0 and text.startswith("Done: ") and "Last lines" not in text
    assert watch.label(["python3", "-u", "train.py", "--epochs", "3"]) == "python3 train.py"
    assert watch.label(["/usr/bin/make", "all"]) == "make"
    assert watch.last_lines(b"10%\r50%\r100%\ndone\n", 5) == ["100%", "done"]
    log = (env.app.paths.state / "watch.log").read_text(encoding="utf-8").splitlines()
    assert len(log) == 2 and log[0].split("\t")[1] == "3"


def test_watch_sends_through_kurooto_or_the_desktop(env, monkeypatch, capsys):
    from kurooto import cli, watch
    from kurooto.core import desktop

    sent, shown = [], []
    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: sent.append((path, body)) or {"ok": True})
    monkeypatch.setattr(desktop, "notify", lambda *a, **k: shown.append(a) or True)
    assert cli.main(["watch", "--lines", "1", "--", sys.executable, "-c", "print('hi')"]) == 0
    assert sent[0][0] == "notify" and sent[0][1]["kind"] == "result" and sent[0][1]["text"].endswith("hi")
    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: None)
    assert watch.main(["--", sys.executable, "-c", "raise SystemExit(4)"]) == 4
    assert shown and "isn't running" in capsys.readouterr().err
    assert watch.main([]) == 2


def test_watch_can_log_a_run(env, monkeypatch):
    from kurooto import cli, watch

    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: {"ok": True})
    code, text = watch.run([sys.executable, "-c", "print('x')"], 1, project="demo", out=io.BytesIO())
    assert code == 0 and "Logged as run" in text
    log = (env.app.workspace / "research" / "demo" / "index.md").read_text(encoding="utf-8")
    assert "— ok after" in log


def test_logs_follow(tmp_path):
    import threading

    from kurooto.watch import follow_log

    log = tmp_path / "kurooto.log"
    log.write_text("".join(f"line {i}\n" for i in range(100)), encoding="utf-8")
    out = io.StringIO()
    follow_log(log, 3, follow=False, out=out)
    assert out.getvalue() == "line 97\nline 98\nline 99\n"
    out, done = io.StringIO(), threading.Event()

    def later():
        time.sleep(0.7)
        log.write_text("rotated\n", encoding="utf-8")  # smaller: a new file
        time.sleep(0.7)
        with open(log, "a", encoding="utf-8") as f:
            f.write("more\n")
        time.sleep(0.8)
        done.set()

    threading.Thread(target=later, daemon=True).start()
    follow_log(log, 1, follow=True, out=out, stop=done.is_set)
    assert out.getvalue().startswith("line 99\n") and "rotated" in out.getvalue() and "more" in out.getvalue()


# ======================================================================================================= top
def test_top_reads_and_draws(env):
    from kurooto import top

    app = env.app
    env.on("reminders")
    app.jobs.submit("Summarise my week", title="Summarise my week")
    app.scheduler.at(time.time() + 600, "x.y", {"what": "check-in call"}, key="checkins:evening")
    app.events.emit("reminder_fired", n=1)
    b = top.Board(app.paths)
    data = b.collect(force=True)
    k = data["kurooto"]
    assert k["running"] is False and "Reminders" in k["on"] and k["queued"] == 1
    assert k["jobs"][0]["title"] == "Summarise my week" and any(s["what"] == "check-in call" for s in k["schedule"])
    assert k["events"][-1]["kind"] == "reminder_fired"
    for w, h in ((70, 60), (150, 60), (30, 10)):
        lines = top.render(data, w, h)
        assert lines and all(top.vlen(ln) == max(30, w) for ln in lines), w
        assert len(lines) <= max(10, h)
    flat = "\n".join(top.ANSI.sub("", ln) for ln in top.render(data, 150, 80, colour=False))
    for part in ("KUROOTO", "THIS COMPUTER", "FEATURES ON", "Reminders", "Summarise my week", "check-in call", "cpu"):
        assert part in flat, part
    ascii_only = "\n".join(top.render(data, 150, 80, colour=False, unicode=False))
    assert ascii_only.isascii() and "\x1b[" not in ascii_only
    assert top.fit("\x1b[31mabcdef\x1b[0m", 3) == "\x1b[31mabc\x1b[0m"


def test_top_on_a_mac_and_without_unicode(env, monkeypatch):
    from collections import namedtuple

    from kurooto import top

    Part = namedtuple("Part", "device mountpoint fstype opts")
    Usage = namedtuple("Usage", "total used free percent")
    gb = 1024**3
    parts = [
        Part("/dev/disk3s1s1", "/", "apfs", "ro,local"),
        Part("/dev/disk3s6", "/System/Volumes/VM", "apfs", "rw"),
        Part("/dev/disk3s5", "/System/Volumes/Data", "apfs", "rw"),
        Part("/dev/disk5s1", "/Volumes/Backup Drive For Photos", "exfat", "rw"),
    ]
    usage = {
        "/": Usage(460 * gb, 11 * gb, 200 * gb, 5.2),
        "/System/Volumes/VM": Usage(460 * gb, 2 * gb, 200 * gb, 1.0),
        "/System/Volumes/Data": Usage(460 * gb, 240 * gb, 200 * gb, 54.5),
        "/Volumes/Backup Drive For Photos": Usage(1000 * gb, 100 * gb, 900 * gb, 10.0),
    }
    monkeypatch.setattr(top.psutil, "disk_partitions", lambda all=False: parts)
    monkeypatch.setattr(top.psutil, "disk_usage", lambda mp: usage[mp])
    monkeypatch.delattr(top.psutil, "sensors_temperatures", raising=False)  # macOS has none
    monkeypatch.setattr(top.psutil, "sensors_battery", lambda: None)
    data = top.Board(env.app.paths).collect(force=True)
    assert [d["mount"] for d in data["machine"]["disks"]] == ["/", "/Volumes/Backup Drive For Photos"]
    data["kurooto"]["on"] = ["Café notes"]
    lines = top.render(data, 80, 80, colour=False, unicode=False)
    assert all(ln.isascii() and top.vlen(ln) == 80 for ln in lines)
    assert any("... For Photos" in ln for ln in lines) and any("Caf? notes" in ln for ln in lines)


def test_top_once(env, capsys):
    from kurooto import cli

    assert cli.main(["top", "--once", "--size", "90x40"]) == 0
    out = capsys.readouterr().out
    assert "KUROOTO" in out and "not running" in out


# ===================================================================================================== doctor
def test_doctor_reports_backups(env, tmp_path):
    from kurooto import diagnostics

    rows = {n: (ok, d) for n, ok, d in diagnostics.checks(env.app)}
    assert rows["Backups"] == (None, "off: nothing is backed up (Features → Backups)")
    drive = tmp_path / "d"
    drive.mkdir()
    env.app.settings.set("backups.folder", str(drive))
    env.on("backups")
    assert env.app.modules["backups"].backup()[0]
    rows = {n: (ok, d) for n, ok, d in diagnostics.checks(env.app)}
    assert rows["Backups"][0] is True and rows["Backups"][1].startswith("last backup")
