"""0.8.1: Brain is fed what happened before it was on (mind/history.py), the journal's folder and file name, a lab
folder in your repo that ignores itself, and a day's hours that can't be 36."""

import datetime as dt
import json
import time

import pytest

from kurooto import mind
from kurooto.mind import history, journal, mood
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind.lab import runner as lab_runner
from kurooto.mind.plans import pace


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    c = mind.connect(a)
    monkeypatch.setattr(c, "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    monkeypatch.setattr(c, "_request", lambda op, **kw: a.keeper.handle({"op": op, **kw}))
    monkeypatch.setattr(c, "running", lambda: (True, 1))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def write_events(app, lines):
    (app.paths.state).mkdir(parents=True, exist_ok=True)
    (app.paths.state / "events.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


def stamp(days_ago, hour=9):
    d = dt.datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0) - dt.timedelta(days=days_ago)
    return d.isoformat(timespec="seconds")


# ----------------------------------------------------------------------------------------------- the import
def test_the_import_keeps_ids_and_numbers_and_their_own_times(app):
    at = time.time() - 3 * 86400
    rows = [
        {"at": at, "kind": "deadline_snooze", "body": {"id": "d1", "title": "words of a title", "minutes": 30}},
        {"at": at + 5, "kind": "not_a_mirrored_kind", "body": {"id": "x"}},
        {"at": "yesterday", "kind": "deadline_moved", "body": {}},
        {"at": at + 9, "kind": "call_missed", "body": {"id": "c1"}},
    ]
    res = app.keeper.handle({"op": "import", "batch": "ev0000000", "rows": rows})
    assert res == {"ok": True, "rows": 2}
    got = mind.connect(app).history_rows()
    assert [(r["meta"]["k"], round(r["value"])) for r in got] == [
        ("deadline_snooze", round(at)),
        ("call_missed", round(at + 9)),
    ]
    assert "title" not in json.dumps(got) and "words" not in json.dumps(got)
    recs = mind.connect(app).log(kinds={"history_import"})
    body = recs[0].body
    body = json.loads(body) if isinstance(body, str) else body
    assert len(recs) == 1 and body["rows"] == 2
    assert mind.connect(app).verify().ok  # the chain still holds


def test_a_bad_batch_is_refused_and_a_rerun_rewrites_the_same_rows(app):
    assert app.keeper.handle({"op": "import", "batch": "Bad Batch!", "rows": []}).get("error") == "refused"
    assert app.keeper.handle({"op": "import", "batch": "ev1", "rows": "x"}).get("error") == "refused"
    row = {"at": time.time() - 86400, "kind": "reminder_fired", "body": {"id": "r1"}}
    for _ in range(2):
        app.keeper.handle({"op": "import", "batch": "ev1", "rows": [row]})
    assert len(mind.connect(app).history_rows()) == 1


def test_history_is_never_reward():
    """I-3, I-4: the imported past trains priors only. No reward module (REWARD = True) or reward source reads the
    history table or imports mind/history.py, and only the read's history, /mind and the Brain page import it."""
    import ast
    import pathlib

    from kurooto.mind import whitelist

    src = pathlib.Path(mind.__file__).parent.parent
    allowed = {"mind/mood.py", "mind/history.py", "modules/mind.py", "core/brainview.py"}
    reward = {m.removeprefix("kurooto.").replace(".", "/") + ".py" for m in whitelist.REWARD_MODULES}
    checked = 0
    for f in src.rglob("*.py"):
        rel = f.relative_to(src).as_posix()
        text = f.read_text(encoding="utf-8")
        tree = ast.parse(text)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
                names.update(f"{node.module}.{a.name}" for a in node.names)
            elif isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
        if "kurooto.mind.history" in names:
            assert rel in allowed, f"{rel} imports the imported past"
        is_reward = rel in reward or "REWARD = True" in text
        if is_reward:
            checked += 1
            assert '"history"' not in text and "history_rows" not in text, f"{rel}: a reward reads the imported past"
    assert checked >= 3  # the reward sources were really found and checked


# ----------------------------------------------------------------------------------------- run, status, forget
def test_run_reads_events_from_before_brain_and_only_then(app):
    app.keeper.append("started", {})  # Brain's own log begins now
    write_events(
        app,
        [
            {"ts": stamp(3), "kind": "deadline_snooze", "id": "a"},
            {"ts": stamp(3, 11), "kind": "deadline_moved", "id": "b"},
            {"ts": stamp(2), "kind": "deadline_snooze", "id": "c"},
            {"ts": stamp(2), "kind": "some_other_event", "id": "z"},
            {"ts": (dt.datetime.now() + dt.timedelta(hours=1)).isoformat(), "kind": "deadline_snooze", "id": "later"},
            "not json",
        ][:5],
    )
    assert "Turn on" in history.run(app)["error"]  # off until you turn it on
    app.settings.set("mind.backfill.on", True)
    p = history.plan(app)
    assert p["rows"] == 3 and p["kinds"] == {"deadline_snooze": 2, "deadline_moved": 1}
    res = history.run(app)
    assert res["rows"] == 3 and res["batches"] == 1
    again = history.run(app)
    assert again["rows"] == 3 and history.status(app)["imported"] == 3  # idempotent
    days = history.daily(app)
    assert sorted(sum(v.values()) for v in days.values()) == [1, 2]
    assert history.forget(app) == 3 and history.status(app)["imported"] == 0


def test_the_imported_past_starts_the_reads_history(app):
    app.keeper.append("started", {})
    write_events(
        app,
        [{"ts": stamp(4), "kind": "deadline_snooze", "id": "a"}, {"ts": stamp(4), "kind": "deadline_moved", "id": "b"}],
    )
    assert mood.history(app) == []
    app.settings.set("mind.backfill.on", True)
    history.run(app)
    (day,) = mood.history(app)
    assert day.sig == {"deadline_moves": 1.0}  # no alarm snoozes: the event history has none
    assert day.load == {"weekday": dt.date.fromisoformat(day.day).weekday()}
    app.settings.set("mind.backfill.on", False)
    assert mood.history(app) == []  # off: the past isn't used


def test_the_command_says_what_it_does(app):
    from kurooto.modules.mind import Mind

    m = Mind(app) if callable(Mind) else None
    app.keeper.append("started", {})
    write_events(app, [{"ts": stamp(2), "kind": "reminder_fired", "id": "a"}])
    assert "Nothing imported yet" in m.backfill([])
    app.settings.set("mind.backfill.on", True)
    assert "Would import 1 events" in m.backfill(["dry"])
    assert "Imported 1 events" in m.backfill(["run"])
    assert "1 days imported" in m.backfill([])
    assert m.backfill(["forget"]).startswith("Forgot 1")


# --------------------------------------------------------------------------------------- the journal's folder
def test_the_journal_goes_where_you_say_inside_your_notes(app, tmp_path):
    ws = tmp_path / "notes"
    ws.mkdir()
    app.settings.set("you.workspace", str(ws))
    assert journal.notes_path(app) == ws.resolve() / "Kurooto journal.md"
    app.settings.set("mind.journal.in_notes_folder", "inbox")
    app.settings.set("mind.journal.in_notes_file", "brain log")
    assert journal.notes_path(app) == ws.resolve() / "inbox" / "brain log.md"
    app.settings.set("mind.journal.in_notes_folder", "../outside")
    app.settings.set("mind.journal.in_notes_file", "a/b.md")
    assert (
        journal.notes_path(app) == ws.resolve() / "Kurooto journal.md"
    )  # never out of your notes, never a path in a name


# ------------------------------------------------------------------------------------------- lab, pace
def test_a_kurooto_folder_in_a_repo_ignores_itself(tmp_path):
    d = tmp_path / "proj" / ".kurooto"
    d.mkdir(parents=True)
    lab_runner.ignore_folder(d)
    assert (d / ".gitignore").read_text() == "*\n"
    other = tmp_path / "other"
    other.mkdir()
    lab_runner.ignore_folder(other)
    assert not (other / ".gitignore").exists()  # only a .kurooto folder, and nothing of the repo's own is touched


def test_a_day_left_open_cannot_count_as_36_hours(app, monkeypatch):
    class Study:
        def day(self, d):
            return {"x": 36.5 * 3600}

    monkeypatch.setitem(app.modules, "study", Study())
    real = app.is_on
    monkeypatch.setattr(app, "is_on", lambda m: True if m == "study" else real(m))
    hist = pace.history(app, dt.date.today())
    assert hist and max(max(v) for v in hist.values() if v) == pace.MAX_DAY_H
