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
def ev_row(key, at, kind, body):
    return {"key": key, "at": at, "kind": kind, "body": body}


def test_the_import_keeps_ids_and_numbers_and_their_own_times(app):
    at = time.time() - 3 * 86400
    rows = [
        ev_row("ev:a:1", at, "deadline_snooze", {"id": "d1", "title": "words of a title", "minutes": 30}),
        ev_row("ev:b:1", at + 5, "not_a_mirrored_kind", {"id": "x"}),
        ev_row("ev:c:1", "yesterday", "deadline_moved", {}),
        ev_row("ev:d:1", at + 9, "call_missed", {"id": "c1"}),
    ]
    res = app.keeper.handle({"op": "import", "source": "events", "batch": "events-1", "rows": rows})
    assert res["ok"] and res["rows"] == 2 and res["bad"] == 2
    got = mind.connect(app).past_rows("events")
    assert [(r["kind"], round(r["ts"]), r["n"]) for r in got] == [
        ("deadline_snooze", round(at), 1),
        ("call_missed", round(at + 9), 2),
    ]
    assert "title" not in json.dumps(got) and "words" not in json.dumps(got)
    (rec,) = mind.connect(app).log(kinds={"history_import"})
    assert rec.body["rows"] == 2 and rec.body["source"] == "events" and rec.body["n"] == 2
    assert rec.body["head"] == mlog.PastLog(app.paths.state / "mind" / "history.db").head("events")[2]
    assert mind.connect(app).verify().ok  # the live chain still holds
    assert history.verify(app)["ok"]
    assert not any(r.kind in ("deadline_snooze", "call_missed") for r in mind.connect(app).log())  # not in the live log


def test_a_bad_batch_is_refused_and_a_rerun_adds_nothing_twice(app):
    assert app.keeper.handle({"op": "import", "source": "events", "batch": "Bad Batch!", "rows": []})["error"]
    assert app.keeper.handle({"op": "import", "source": "events", "batch": "ev1", "rows": "x"})["error"]
    assert app.keeper.handle({"op": "import", "source": "elsewhere", "batch": "ev1", "rows": []})["error"]
    row = ev_row("ev:r1:1", time.time() - 86400, "reminder_fired", {"id": "r1"})
    for _ in range(2):
        app.keeper.handle({"op": "import", "source": "events", "batch": "ev1", "rows": [row]})
    assert len(mind.connect(app).past_rows()) == 1
    assert len(mind.connect(app).log(kinds={"history_import"})) == 1  # nothing added: nothing to witness
    # a kind from another source is refused on this one; an earlier row than the head is left out (time order)
    r = app.keeper.handle({"op": "import", "source": "jobs", "batch": "j1", "rows": [ev_row("job:x", 5.0, "call", {})]})
    assert r["rows"] == 0 and r["bad"] == 1
    late = ev_row("ev:old:1", time.time() - 9 * 86400, "reminder_fired", {})
    assert app.keeper.handle({"op": "import", "source": "events", "batch": "ev2", "rows": [late]})["late"] == 1


def test_the_past_chain_catches_a_changed_or_cut_past(app):
    import sqlite3

    t = time.time() - 5 * 86400
    rows = [ev_row(f"ev:{i}:1", t + i, "reminder_fired", {"n": i}) for i in range(4)]
    app.keeper.handle({"op": "import", "source": "events", "batch": "ev1", "rows": rows})
    assert history.verify(app) == {"ok": True, "sources": {"events": 4}, "bad": None}
    db = sqlite3.connect(app.paths.state / "mind" / "history.db")
    db.execute("UPDATE past SET body = '{\"n\":9}' WHERE n = 2")
    db.commit()
    assert history.verify(app)["bad"] == {"source": "events", "n": 2, "why": "changed"}
    db.execute("UPDATE past SET body = '{\"n\":1}' WHERE n = 2")
    db.execute("DELETE FROM past WHERE n = 4")
    db.commit()
    db.close()
    assert history.verify(app)["bad"]["why"] == "cut short"  # the live log witnessed a head at 4


def test_the_real_scorekeeper_files_the_past_over_its_socket(tmp_path):
    """The request as it really travels (JSON over the scorekeeper's socket, a process of its own)."""
    from tests.unit.test_mind_spine import ask, end, start_keeper

    d = tmp_path / "mind"
    p = start_keeper(d)
    try:
        t = time.time() - 4 * 86400
        rows = [ev_row(f"job:{i}", t + i, "job", {"effort": "low", "ok": True, "seconds": 3.5}) for i in range(3)]
        assert ask(d, {"op": "import", "source": "jobs", "batch": "jobs-1", "rows": rows})["rows"] == 3
        assert ask(d, {"op": "import", "source": "jobs", "batch": "jobs-1", "rows": rows})["dup"] == 3
        past = mlog.PastLog(d / "history.db")
        assert past.counts() == {"jobs": 3} and past.verify()["ok"]
        assert ask(d, {"op": "history_forget", "source": "jobs"})["rows"] == 3
    finally:
        end(p)


def test_history_is_never_reward():
    """I-3, I-4: the imported past trains priors only. No reward module (REWARD = True) or reward source reads it (the
    history table, history.db, the client's past reads or mind/history.py), and only the parts that use it as a prior
    import mind/history.py."""
    import ast
    import pathlib

    from kurooto.mind import whitelist

    src = pathlib.Path(mind.__file__).parent.parent
    allowed = {
        "mind/mood.py",
        "mind/history.py",
        "modules/mind.py",
        "core/brainview.py",
        "mind/plans/pace.py",  # the pace prior
        "mind/tom/goals.py",  # how past deadlines went
    }
    reward = {m.removeprefix("kurooto.").replace(".", "/") + ".py" for m in whitelist.REWARD_MODULES}
    assert not allowed & reward
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
            for word in ('"history"', "history_rows", "past_rows", "past_heads", "history.db", "PastLog", "prior"):
                assert word not in text, f"{rel}: a reward reads the imported past ({word})"
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
        ],
    )
    assert "Turn on" in history.run(app)["error"]  # off until you turn it on
    app.settings.set("mind.backfill.on", True)
    p = history.plan(app)
    assert p["rows"] == 3 and p["kinds"] == {"deadline_snooze": 2, "deadline_moved": 1}
    res = history.run(app)
    assert res["rows"] == 3 and res["batches"] == 1
    again = history.run(app)
    assert again["rows"] == 0 and history.status(app)["imported"] == 3  # idempotent
    days = history.daily(app)
    assert sorted(sum(v.values()) for v in days.values()) == [1, 2]
    assert history.forget(app) == 3 and history.status(app)["imported"] == 0


def test_events_moved_aside_are_read_too(app):
    app.keeper.append("started", {})
    app.settings.set("mind.backfill.on", True)
    (app.paths.state).mkdir(parents=True, exist_ok=True)
    (app.paths.state / "events.jsonl.1").write_text(json.dumps({"ts": stamp(9), "kind": "reminder_fired"}) + "\n")
    write_events(app, [{"ts": stamp(2), "kind": "reminder_fired"}, {"ts": stamp(2), "kind": "reminder_fired"}])
    assert history.run(app, only="events")["rows"] == 3  # two identical lines are two events


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
    assert "Would import 1 rows" in m.backfill(["dry"])
    said = m.backfill(["run"])
    assert "Imported 1 rows" in said and "events" in said and "ETA" in said and "█" in said
    assert "1 days imported" in m.backfill([])
    assert "checks out" in m.backfill(["verify"])
    assert "No source" in m.backfill(["run", "nowhere"])
    assert m.backfill(["forget"]).startswith("Forgot 1")


def test_0_8_1s_table_is_still_read_then_replaced_by_the_chain(app):
    app.keeper.append("started", {})
    at = dt.datetime.fromisoformat(stamp(3)).timestamp()
    app.keeper.score._put("history", "h:ev0000000:00000", at, {"k": "deadline_moved"})  # what 0.8.1 left
    app.settings.set("mind.backfill.on", True)
    assert history.status(app)["old"] == 1
    assert list(history.daily(app).values()) == [{"deadline_moved": 1}]
    write_events(app, [{"ts": stamp(3), "kind": "deadline_moved"}])
    history.run(app)
    st = history.status(app)
    assert st["old"] == 0 and st["sources"] == {"events": 1} and st["imported"] == 1
    assert mind.connect(app).history_rows() == []
    (rec,) = mind.connect(app).log(kinds={"history_import"})
    assert rec.body["migrated"] == 1
    assert list(history.daily(app).values()) == [{"deadline_moved": 1}]


# ----------------------------------------------------------------------------------------- every source, faked
NAME, AMOUNT = "Priyanka Venkataraman", 7351
WORDS = ("Priyanka", "Venkataraman", "rupees", "landlord", "migraine", "real-analysis", "secret words")


def fake_stores(app, days_ago=10):
    """Every store the backfill reads, with words, a name and an amount planted where a careless reader would copy
    them."""
    import sqlite3

    st = app.paths.state
    st.mkdir(parents=True, exist_ok=True)
    t0 = dt.datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) - dt.timedelta(days=days_ago)
    day = t0.date().isoformat()
    write_events(
        app,
        [
            {"ts": t0.isoformat(), "kind": "deadline_added", "id": "d1", "title": f"pay {NAME} {AMOUNT} rupees",
             "amount": AMOUNT, "label": "migraine"},
            {"ts": (t0 + dt.timedelta(hours=1)).isoformat(), "kind": "deadline_moved"},
        ],
    )  # fmt: skip
    db = sqlite3.connect(st / "jobs.db")
    db.execute(
        "create table if not exists jobs (id text primary key, title text, prompt text, effort text, status text, "
        "verdict text, created real, seconds real, result text, lane text, background integer)"
    )
    for i, (status, verdict) in enumerate((("ok", "ok"), ("failed", "rate_limited"), ("queued", None))):
        db.execute(
            "insert into jobs (id, title, prompt, effort, status, verdict, created, seconds, result, lane, background) "
            "values (?,?,?,?,?,?,?,?,?,?,?)",
            (f"j{i}", f"ask {NAME}", f"my landlord wants {AMOUNT} rupees", "high", status, verdict,
             t0.timestamp() + i * 60, 12.5, "secret words", "you", 0),
        )  # fmt: skip
    db.commit()
    db.close()
    due = t0 + dt.timedelta(days=2)
    items = {}
    for i in range(3):
        items[f"x{i}"] = {
            "title": f"essay for {NAME}", "due": (due + dt.timedelta(days=i)).isoformat(), "status": "done",
            "done_at": (due + dt.timedelta(days=i) - dt.timedelta(hours=48)).isoformat(), "kind": "task",
            "subject": "real-analysis", "amount": AMOUNT, "sources": ["manual"],
        }  # fmt: skip
    (st / "deadlines.json").write_text(json.dumps(items))
    (st / "checkins").mkdir(exist_ok=True)
    (st / "checkins" / f"{day}.json").write_text(
        json.dumps(
            {"evening": {"time": "21:00", "status": "answered", "said": "migraine again"},
             "night": {"time": "00:30", "status": "skipped"}, NAME: {"time": "10:00", "status": "asked"}}
        )
    )  # fmt: skip
    (st / "quiz").mkdir(exist_ok=True)
    (st / "quiz" / "real-analysis.json").write_text(
        json.dumps({"items": {"i1": {"text": f"what did {NAME} prove", "history": [{"date": day, "q": 4},
                                                                                {"date": day, "q": 1}]}}})
    )  # fmt: skip
    (st / "quiz" / "session.json").write_text(json.dumps({"subject": "real-analysis", "left": 3}))
    (st / "calls" / "transcripts").mkdir(parents=True, exist_ok=True)
    ring = int(t0.timestamp()) + 3600
    rings = {
        str(ring): {"reason": f"call {NAME} about {AMOUNT}", "key": "deadlines:x0", "at": ring, "state": "answered"},
        str(ring + 7200): {"reason": "landlord", "key": f"{NAME}:x", "at": ring + 7200, "state": "missed"},
    }
    (st / "calls" / "rings.json").write_text(json.dumps(rings))
    end = dt.datetime.fromtimestamp(ring + 300)
    (st / "calls" / "transcripts" / f"{end:%Y-%m-%d-%H%M%S}.txt").write_text(f"you: {NAME} owes me {AMOUNT}\n")
    (st / "learning").mkdir(exist_ok=True)
    db = sqlite3.connect(st / "learning" / "history.db")
    db.execute("create table docs(title text, body text, key text, kind text, at real)")
    for kind in ("request", "call", "chat"):
        db.execute(
            "insert into docs values (?,?,?,?,?)", (NAME, f"{AMOUNT} rupees", f"{NAME}.txt", kind, t0.timestamp())
        )
    db.commit()
    db.close()
    (st / "study").mkdir(exist_ok=True)
    (st / "study" / f"{day}.json").write_text(json.dumps({"real-analysis": 3600, "real-analysis|manual": 600}))
    (st / "study" / "session.json").write_text(json.dumps({"slug": "real-analysis", "started": 1}))
    return t0


def everything_kept(app) -> str:
    """Every table Brain keeps, as text."""
    import sqlite3

    out = []
    for f in ("history.db", "log.db", "score.db"):
        db = sqlite3.connect(app.paths.state / "mind" / f)
        for (t,) in db.execute("select name from sqlite_master where type='table'"):
            out += [repr(r) for r in db.execute(f'select * from "{t}"')]  # noqa: S608
        db.close()
    return "\n".join(out)


def test_every_source_is_read_and_only_ids_and_numbers_reach_any_table(app):
    fake_stores(app)
    app.keeper.append("started", {})
    app.settings.set("mind.backfill.on", True)
    p = history.plan(app)
    assert {s: v["rows"] for s, v in p["sources"].items()} == {
        "events": 2, "jobs": 2, "deadlines": 6, "checkins": 2, "quiz": 1, "calls": 2, "learning": 2, "study": 1,
    }  # fmt: skip
    res = history.run(app)
    assert res["rows"] == 18 and not res.get("error")
    c = mind.connect(app)
    (job, _) = c.past_rows("jobs")
    assert job["body"] == {"effort": "high", "verdict": "ok", "ok": True, "lane": "you", "background": False,
                           "seconds": 12.5}  # fmt: skip
    (quiz,) = c.past_rows("quiz")
    assert quiz["body"]["asked"] == 2 and quiz["body"]["right"] == 1 and quiz["body"]["wrong"] == 1
    assert quiz["body"]["subj"] == history.subject_id("real-analysis")
    answered, missed = c.past_rows("calls")
    assert answered["body"] == {"state": "answered", "module": "deadlines", "alarm": False, "again": 0, "minutes": 5.0}
    assert missed["body"]["module"] == "other"  # not a feature's id: never the words before the colon
    assert {r["body"]["checkin"] for r in c.past_rows("checkins")} == {"evening", "night"}
    assert {r["body"]["via"] for r in c.past_rows("learning")} == {"request", "call"}  # chats left out
    (study,) = c.past_rows("study")
    assert study["body"] == {"seconds": 4200, "subjects": 1, "manual_s": 600}
    done = [r for r in c.past_rows("deadlines") if r["kind"] == "deadline_finished"]
    assert [r["body"]["done_before_h"] for r in done] == [48.0, 48.0, 48.0]
    # the redactions hold, in every table Brain has
    kept = everything_kept(app)
    for w in WORDS:
        assert w not in kept, w
    for r in c.past_rows():
        assert AMOUNT not in r["body"].values() and "amount" not in r["body"]
        assert all(not isinstance(v, str) or " " not in v for v in r["body"].values())
    for r in c.log():
        assert AMOUNT not in (r.body or {}).values()
    assert history.verify(app)["ok"] and c.verify().ok


def test_each_source_has_its_own_switch(app):
    fake_stores(app)
    app.keeper.append("started", {})
    app.settings.set("mind.backfill.on", True)
    for s in ("jobs", "calls", "learning"):
        app.settings.set(f"mind.backfill.{s}", False)
    assert set(history.plan(app)["sources"]) == {"events", "deadlines", "checkins", "quiz", "study"}
    history.run(app)
    assert set(history.status(app)["sources"]) == {"events", "deadlines", "checkins", "quiz", "study"}
    assert "is off" in history.run(app, only="jobs")["error"]
    app.settings.set("mind.backfill.on", False)
    assert history.enabled(app) == [] and history.study_days(app) == {}  # all off while backfill is off


def test_a_missing_store_is_skipped(app):
    app.keeper.append("started", {})
    app.settings.set("mind.backfill.on", True)
    res = history.run(app)
    assert res["rows"] == 0 and not res.get("error")
    assert all(v["total"] == 0 for v in res["sources"].values())


def test_a_half_run_resumes_where_it_stopped(app, monkeypatch):
    fake_stores(app)
    write_events(app, [{"ts": stamp(9, h), "kind": "reminder_fired", "n": h} for h in range(8, 15)])
    app.keeper.append("started", {})
    app.settings.set("mind.backfill.on", True)
    monkeypatch.setattr(history, "BATCH", 2)
    c = mind.connect(app)
    real, calls = c._request, []

    def flaky(op, **kw):
        calls.append(op)
        return {} if len(calls) == 3 else real(op, **kw)  # the scorekeeper goes away partway through

    monkeypatch.setattr(c, "_request", flaky)
    half = history.run(app)
    assert "run it again" in half["error"] and half["bars"]
    got = history.status(app)["sources"]
    assert 0 < sum(got.values()) < history.plan(app)["rows"]
    monkeypatch.setattr(c, "_request", real)
    seen = []
    full = history.run(app, progress=lambda s, d, t: seen.append((s, d, t)))
    assert sum(history.status(app)["sources"].values()) == history.plan(app)["rows"] == 7 + 16
    assert full["rows"] + sum(got.values()) == 23  # nothing twice
    assert history.verify(app)["ok"]
    assert seen and all(d <= t for _, d, t in seen) and seen[-1][1] == seen[-1][2]
    log = (app.paths.logs / "mind-backfill.log").read_text(encoding="utf-8")
    assert "ETA" in log and "█" in log and "stopped" in log


def test_forget_one_source_or_all(app):
    fake_stores(app)
    app.keeper.append("started", {})
    app.settings.set("mind.backfill.on", True)
    history.run(app)
    assert history.forget(app, "jobs") == 2
    assert "jobs" not in history.status(app)["sources"] and history.verify(app)["ok"]
    history.run(app, only="jobs")  # imported again, from the start of its chain
    assert history.status(app)["sources"]["jobs"] == 2 and history.verify(app)["ok"]
    history.forget(app)
    assert history.status(app)["imported"] == 0 and history.verify(app) == {"ok": True, "sources": {}, "bad": None}


# ----------------------------------------------------------------------------------------- the priors
def test_the_priors_come_from_what_the_past_really_holds(app):
    from kurooto.mind.tom import goals
    from kurooto.mind.tom import model as tom

    st = app.paths.state
    (st / "study").mkdir(parents=True, exist_ok=True)
    base = dt.date.today() - dt.timedelta(days=200)
    while base.weekday() != 1:  # Tuesdays
        base += dt.timedelta(days=1)
    for w in range(4):
        (st / "study" / f"{base + dt.timedelta(weeks=w)}.json").write_text(json.dumps({"x": 3 * 3600}))
    ago = next(n for n in range(100, 108) if (dt.date.today() - dt.timedelta(days=n)).weekday() not in (1, 3))
    fake_stores(app, days_ago=ago)  # on another weekday than the Tuesdays and the Thursday checked below
    app.keeper.append("started", {})
    app.settings.set("mind.backfill.on", True)
    history.run(app)
    assert history.pace_prior(app)[1] == 3.0
    assert pace.samples(app)[1][:3] == [3.0, 3.0, 3.0]  # a Tuesday with no recent samples: its real past, not 2 h
    assert pace.samples(app)[3] == [pace.PRIOR_H] * 3  # a weekday the past doesn't hold keeps the flat prior
    pri = history.forecast_priors(app, 1)
    assert set(pri) == {"study_min"} and pri["study_min"][0] == 180.0  # the only channel it holds that often
    assert mood.past_priors(app, base) == pri
    days = mood.history(app)
    tue = [d for d in days if d.day == base.isoformat()]
    assert tue and tue[0].sig == {"study_min": 180.0}
    assert all(set(d.sig) <= {"deadline_moves", "study_min"} for d in days)  # nothing made up
    pat = history.deadline_pattern(app)["task"]
    assert pat == {"n": 3, "done": 3, "late": 0, "lead_h": 48.0}
    app.settings.set("mind.tom.on", True)
    assert goals.from_past(app) == 1
    (row,) = [r for r in tom.rows(app, "goal") if goals.PAST in r["evidence"]]
    assert row["source"] == "inferred" and "about 2 days before" in row["claim"]
    history.forget(app)
    assert not [r for r in tom.rows(app, "goal") if goals.PAST in r["evidence"]]
    assert history.pace_prior(app) == {} and history.forecast_priors(app, 1) == {}


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
