"""The Space keeper: it finds Kurooto's own leftovers (old backup zips past a count, size or age limit, downloads, made
zips, big logs, old finished requests, the concept graph's old before-copies), says how much that is, removes them, and
never touches the newest backup, your notes or anything it doesn't own."""

import os
import sqlite3
import time

import pytest

from kurooto.core import space


@pytest.fixture
def world(env, tmp_path):
    app = env.app
    folder = tmp_path / "backups"
    folder.mkdir()
    app.settings.set("backups.folder", str(folder))
    app.settings.set("backups.keep", 20)
    app.settings.set("space.backups_max_gb", 0)
    app.settings.set("space.cache_days", 14)
    env.on("space")
    env.folder = folder
    return env


def zip_at(folder, stamp, mb=1, age_days=0):
    f = folder / f"kurooto-backup-{stamp}.zip"
    f.write_bytes(b"x" * int(mb * 1024 * 1024))
    t = time.time() - age_days * 86400
    os.utime(f, (t, t))
    return f


def age(p, days):
    t = time.time() - days * 86400
    os.utime(p, (t, t))


def test_backups_beyond_the_count_the_size_or_the_age_go_but_never_the_newest(world):
    env = world
    zs = [zip_at(env.folder, f"2026102{i}-010000", mb=2, age_days=10 - i) for i in range(1, 6)]
    (env.folder / "my-own-file.zip").write_bytes(b"mine" * 1000)  # not Kurooto's: never touched
    env.app.settings.set("backups.keep", 4)
    items = space.plan(env.app)
    assert [i.paths for i in items if i.kind == "backups"] == [[zs[0]]]
    env.app.settings.set("backups.keep", 20)
    env.app.settings.set("space.backups_max_gb", 5 / 1024)  # 5 MB: two of five zips fit, the newest is kept
    gone = {p for i in space.plan(env.app) if i.kind == "backups" for p in i.paths}
    assert gone == set(zs[:3]) and zs[-1] not in gone
    env.app.settings.set("space.backups_max_gb", 0)
    env.app.settings.set("space.backups_max_age_days", 7)
    gone = {p for i in space.plan(env.app) if i.kind == "backups" for p in i.paths}
    assert gone and zs[-1] not in gone and all(p.name.startswith("kurooto-backup-") for p in gone)
    out = space.clean(env.app, space.plan(env.app))
    assert out["failed"] == 0 and out["freed"] > 0
    assert (env.folder / "my-own-file.zip").exists() and zs[-1].exists()


def test_one_backup_is_never_removed_whatever_the_limits(world):
    env = world
    only = zip_at(env.folder, "20261021-010000", mb=3, age_days=100)
    env.app.settings.set("space.backups_max_gb", 0.0001)
    env.app.settings.set("space.backups_max_age_days", 1)
    assert not [i for i in space.plan(env.app) if i.kind == "backups"]
    assert only.exists()


def test_old_downloads_and_made_zips_go_and_fresh_ones_stay(world):
    env = world
    cache = env.app.paths.cache
    for sub in ("downloads", "study-packs", "send"):
        (cache / sub).mkdir(parents=True, exist_ok=True)
    old, fresh = cache / "downloads" / "node.zip", cache / "send" / "files.zip"
    old.write_bytes(b"x" * 2048)
    age(old, 30)
    fresh.write_bytes(b"x" * 2048)
    cut = cache / "downloads" / "big.part"
    cut.write_bytes(b"x" * 10)
    age(cut, 3)
    space.clean(env.app, space.plan(env.app))
    assert not old.exists() and not cut.exists() and fresh.exists()


def test_a_huge_log_is_cut_to_its_newest_lines(world):
    env = world
    env.app.settings.set("space.log_mb", 1)
    log = env.app.paths.logs / "kurooto.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("".join(f"line {i} " + "x" * 90 + "\n" for i in range(30000)), encoding="utf-8")
    assert log.stat().st_size > 1024 * 1024
    space.clean(env.app, space.plan(env.app))
    text = log.read_text(encoding="utf-8")
    assert log.stat().st_size <= 600 * 1024 and text.endswith("\n") and "line 29999" in text and "line 0 " not in text
    assert text.splitlines()[0].startswith("line ")  # no half line at the start


def test_old_finished_requests_are_forgotten_and_running_ones_are_not(world):
    env = world
    jobs = env.app.jobs
    a = jobs.submit("old one", background=True, quiet=True)
    b = jobs.submit("running one", background=True, quiet=True)
    db = jobs._db
    db.execute("update jobs set status='ok', finished=?, result='answer' where id=?", (time.time() - 90 * 86400, a))
    db.execute("update jobs set status='running', finished=null where id=?", (b,))
    db.commit()
    items = [i for i in space.plan(env.app) if i.kind == "jobs"]
    assert len(items) == 1 and "1 finished AI request" in items[0].what
    jobs._db.close() if False else None
    out = space.clean(env.app, items)
    assert out["failed"] == 0
    con = sqlite3.connect(str(env.app.paths.state / "jobs.db"))
    ids = {r[0] for r in con.execute("select id from jobs")}
    con.close()
    assert a not in ids and b in ids


def test_the_concept_graphs_old_work_files_go(world):
    env = world
    d = env.app.paths.state / "integrate" / "undo"
    d.mkdir(parents=True)
    old, new = d / "a.json", d / "b.json"
    old.write_text("{}")
    new.write_text("{}")
    age(old, 60)
    space.clean(env.app, space.plan(env.app))
    assert not old.exists() and new.exists()


def test_nothing_to_clean_says_so_and_the_command_reports_and_cleans(world):
    env = world
    assert space.report([]).startswith("Nothing to clean")
    zip_at(env.folder, "20261001-010000", mb=1, age_days=50)
    zip_at(env.folder, "20261002-010000", mb=1, age_days=40)
    env.app.settings.set("backups.keep", 1)
    out = env.say("/space")
    assert "Kurooto takes" in out and "backup zips" in out and "/space clean does it" in out
    assert env.say("/space clean").startswith("Cleaned off")
    assert env.say("/space").endswith("Nothing to clean: Kurooto isn't holding on to anything it doesn't need.")


def test_the_weekly_run_cleans_and_a_big_clean_is_one_line(world):
    env = world
    zip_at(env.folder, "20261001-010000", mb=60, age_days=50)
    zip_at(env.folder, "20261002-010000", mb=1, age_days=40)
    env.app.settings.set("backups.keep", 1)
    out = env.app.modules["space"].run_clean()
    assert out["freed"] >= 60 * 1024 * 1024
    assert any("Space keeper: cleaned off" in (t or "") for t in env.fake.texts())


def test_human_sizes():
    assert space.human(512) == "512 B" and space.human(2048) == "2.0 KB" and space.human(3 * 1024**2) == "3.0 MB"
    assert space.human(5 * 1024**3) == "5.0 GB"
