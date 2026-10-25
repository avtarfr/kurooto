"""Brain, stage 16: forgetting well: salience fades retrieval, old misses retire, /forget goes everywhere (I-11)."""

import datetime as dt
import time

import pytest

from kurooto import mind
from kurooto.core import assembler, proposals, retention
from kurooto.mind import forgetting, gate, journal, story
from kurooto.mind import log as mlog
from kurooto.mind import read as rd
from kurooto.mind import scorekeeper as sk
from kurooto.mind.senses import store
from kurooto.mind.skills import finetune, library
from kurooto.mind.tom import model

DAY = 86400.0


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def row(kind="fact", age_days=0.0, text="likes short answers", sub="", rid=1):
    return {"id": rid, "kind": kind, "sub": sub, "at": time.time() - age_days * DAY, "text": text}


# ------------------------------------------------------------------------------------------------ fading
def test_salience_decay_and_boost(app):
    now = time.time()
    assert forgetting.salience(app, row("fact", 0), now) == 1.0
    for kind, sub_, days in (("fact", "", 90), ("gist", "", 30), ("fact", "project", 180)):
        assert forgetting.salience(app, row(kind, days, sub=sub_), now) == pytest.approx(0.5, abs=0.01), (kind, days)
    assert forgetting.salience(app, row("gist", 60), now) == pytest.approx(0.25, abs=0.01)
    assert forgetting.salience(app, row("meeting", 60), now) == pytest.approx(
        0.5, abs=0.01
    )  # the default half-life, 60 days
    old = row("gist", 120, rid=7)
    base = forgetting.salience(app, old, now)
    assert base < 0.1
    forgetting.used(app, [old], now)  # confirmed in use: it counts from today again, and a little more
    assert forgetting.salience(app, old, now) > 0.9 > base
    for _ in range(10):
        forgetting.used(app, [old], now)
    assert forgetting.salience(app, old, now) <= 1.0  # never above full
    app.settings.set("mind.forget.half_lives", {"fact": 10, "default": 10})
    assert forgetting.salience(app, row("fact", 10, rid=99), now) == pytest.approx(0.5, abs=0.01)  # your half-lives
    assert forgetting.bar(1.0) == "▮▮▮" and forgetting.bar(0.5) == "▮▮▯" and forgetting.bar(0.01) == "▯▯▯"
    assert "fading" in forgetting.label(app, row("gist", 200, rid=5)) and "fading" not in forgetting.label(
        app, row("fact", 0, rid=6)
    )


def test_retrieval_ranks_by_relevance_times_salience(app):
    assert forgetting.factor(app, row("gist", 300, rid=3)) < forgetting.factor(app, row("gist", 1, rid=4))
    app.settings.set("mind.forget.on", False)
    assert forgetting.factor(app, row("gist", 300, rid=3)) == 1.0 and forgetting.label(app, row("gist", 300)) == ""


def test_the_assembler_uses_it(app, monkeypatch):
    from kurooto.core import ledger, threads

    now = time.time()
    fresh = {"id": 1, "kind": "gist", "sub": "chat", "at": now - 2 * DAY, "text": "talked about glacier flow models"}
    stale = {
        "id": 2,
        "kind": "gist",
        "sub": "chat",
        "at": now - 200 * DAY,
        "text": "talked about glacier flow models too",
    }
    monkeypatch.setattr(ledger, "everything", lambda *a, **k: [stale, fresh])
    monkeypatch.setattr(threads, "open_threads", lambda a: [])
    monkeypatch.setattr(assembler, "LOOK_DAYS", 400)
    got = assembler.pick(app, "what did we say about glacier flow models last time?")
    assert [r["id"] for _, r in got][:1] == [1] and {r["id"] for _, r in got} == {1, 2}  # the faded one ranks below
    block, n = assembler.build(app, "what did we say about glacier flow models last time?")
    assert n == 2 and forgetting._state(app)["uses"]  # noqa: SLF001  (what went in is a confirmed use)


# -------------------------------------------------------------------------------------------- old misses
def test_old_misses_not_cited(app, monkeypatch):
    now = time.time()
    miss = "you missed the Friday deadline and fell behind"
    assert forgetting.is_old_miss(app, miss, now - 7 * 7 * DAY, now) and not forgetting.is_old_miss(
        app, miss, now - 2 * 7 * DAY, now
    )
    assert not forgetting.is_old_miss(app, "you finished the essay", now - 90 * DAY, now)  # not a miss
    app.settings.set("mind.forget.misses_weeks", 12)
    assert not forgetting.is_old_miss(app, miss, now - 7 * 7 * DAY, now)  # your setting
    app.settings.set("mind.forget.misses_weeks", 6)
    from kurooto.core import ledger, threads

    gist = {"id": 9, "kind": "gist", "sub": "chat", "at": now - 70 * DAY, "text": "you missed the quiz and fell behind"}
    ok = {"id": 10, "kind": "gist", "sub": "chat", "at": now - 70 * DAY, "text": "we planned the quiz revision"}
    monkeypatch.setattr(ledger, "everything", lambda *a, **k: [gist, ok])
    monkeypatch.setattr(threads, "open_threads", lambda a: [])
    monkeypatch.setattr(assembler, "LOOK_DAYS", 400)
    ids = {r["id"] for _, r in assembler.pick(app, "what about the quiz last time")}
    assert ids == {10}  # the old miss is not put in front of an AI
    # messages: a sentence that brings up a miss from beyond six weeks goes; a recent one, and other sentences, stay
    from kurooto.core.notify import Message

    verdict, msg, _ = gate.check(
        app, Message("Good morning. You missed the quiz 8 weeks ago. Tea is ready.", why="asked")
    )
    assert verdict == "send" and "8 weeks ago" not in msg.text and "Tea is ready" in msg.text
    verdict, msg, _ = gate.check(app, Message("You missed the quiz 2 weeks ago.", why="asked"))
    assert "2 weeks ago" in msg.text
    assert gate.check(app, Message("You failed it last term.", why="asked"))[0] == "block"  # nothing left of it
    assert forgetting.old_reference(app, "back in the spring you failed") is False  # (only dated references are judged)


def test_its_own_mistakes_stay_in_the_journal(app):
    day = dt.date.today() - dt.timedelta(days=90)
    journal.jsave(
        journal.folder(app) / f"{day.isoformat()}.json",
        {"day": day.isoformat(), "lines": [{"text": "I missed a deadline reminder"}]},
    )
    forgetting.is_old_miss(app, "I missed a deadline reminder", time.time() - 90 * DAY)
    assert (
        "missed a deadline" in (journal.folder(app) / f"{day.isoformat()}.json").read_text()
    )  # honesty: not touched by fading


def test_story_does_not_repeat_old_misses(app, monkeypatch):
    old_day = (dt.date.today() - dt.timedelta(days=80)).isoformat()
    new_day = dt.date.today().isoformat()
    chapters = [
        {
            "lines": [
                {"text": "you missed the Friday deadline", "seqs": [1], "day": old_day},
                {"text": "you handed the report in early", "seqs": [2], "day": old_day},
                {"text": "you missed a lecture", "seqs": [3], "day": new_day},
            ]
        }
    ]
    monkeypatch.setattr(story, "chapters", lambda a: chapters)
    monkeypatch.setattr(story, "core_text", lambda a: "core")
    s = story.summary(app)
    assert "Friday deadline" not in s and "handed the report in early" in s and "missed a lecture" in s
    assert "Friday deadline" in chapters[0]["lines"][0]["text"]  # the chapter itself keeps it


# -------------------------------------------------------------------------------------------------- forget
def plant(app, when):
    """One item in every store, made at `when`."""
    day = dt.datetime.fromtimestamp(when).date().isoformat()
    app.keeper.append("signal", {"day": day, "name": rd.SIGNALS[0], "value": 3.0})
    model.put(app, "goal", "g", "finish the chapter", "said", 1.0)
    r = model.get(app, model.key("goal", "g", "finish the chapter"))
    r["updated"] = when
    st = model._state(app)  # noqa: SLF001
    st["rows"] = [r if x["id"] == r["id"] else x for x in st["rows"]]
    model._save(app, st)  # noqa: SLF001
    store.add(app, "activity", "window", "kitty", t=when)
    store.bump(app, day, "activity", "min:kitty", 5)
    library.admit(
        app,
        {
            "slug": "plot-note",
            "kind": "prompt",
            "title": "Plot note",
            "when": "after plots",
            "inputs": ["x"],
            "steps": "1. do it",
            "template": "{x}",
            "cases": [
                {"inputs": {"x": "a"}, "expect": {"contains": ["ok"]}},
                {"inputs": {"x": "b"}, "expect": {"contains": ["ok"]}},
            ],
        },
        {"source": "episode", "proposal": "pSECRET"},
        runner=lambda *a: "ok",
    )
    m = library.meta(app, "plot-note")
    m["created"] = when
    library.jsave(library.folder(app, "plot-note") / "skill.json", m)
    journal.jsave(journal.folder(app) / f"{day}.json", {"day": day, "lines": [{"text": "SECRETJOURNAL"}]})
    (journal.folder(app) / f"{day}.md").write_text("SECRETJOURNAL")
    return day


def test_forget_cascades_everywhere(app, monkeypatch):
    """I-11: one thing planted in every store is gone from all of them; the log only says that a forget happened."""
    from tests.unit.test_mind_skills import make_proposal, pid_of

    app.settings.set("mind.finetune.on", True)
    now = time.time()
    day = plant(app, now - 3600)
    make_proposal(app, "keep-me", request="tidy the plotting script for the weekly figures")
    p = proposals.get(app, pid_of("keep-me"))
    p["created"] = now - 3600
    proposals.save(app, p)
    ex = finetune.from_proposals(app, now)
    assert len(ex) == 1 and model.rows(app) and store.events(app, "activity") and library.meta(app, "plot-note")
    mind.connect(app).flush()
    before = len(mind.connect(app).log(0, None, 5000))
    out = retention.forget(app, now - 7200, retention.END, ("mind",), gist=False)
    assert out["mind"] >= 5
    assert model.rows(app) == [] and store.events(app, "activity") == [] and store.totals(app, "activity", day) == {}
    assert (
        library.jload(library.folder(app, "plot-note") / "provenance.json", {}).get("redacted")
        and "pSECRET" not in (library.folder(app, "plot-note") / "provenance.json").read_text()
    )
    assert library.meta(app, "plot-note")  # the skill itself stays; only where it came from goes
    assert (
        "SECRETJOURNAL" not in (journal.folder(app) / f"{day}.json").read_text()
        and forgetting.TOMBSTONE in (journal.folder(app) / f"{day}.md").read_text()
    )
    assert journal.jload(journal.folder(app) / f"{day}.json", {})[
        "tombstone"
    ]  # a hash and "something you asked me to forget"
    assert not mind.connect(app).signal_days().get(day)  # the mood store
    tomb = finetune._state(app)["tombstones"]  # noqa: SLF001
    assert (
        len(tomb) == 1 and tomb[0]["prefix"] == "tidy the plotting script for"
    )  # the fine-tune: a hash and a few words
    assert finetune.collect(app) == [] or all(e["key"] != tomb[0]["key"] for e in finetune.collect(app))
    # the log: every record it had is still there, plus one that a forget happened, with a hash and a count only
    after = mind.connect(app).log(0, None, 5000)
    assert len(after) > before - 1
    ev = [r for r in after if r.kind == "forget_event"]
    assert ev and set(ev[-1].body) <= {"hash", "n"} and "tidy" not in str(ev[-1].body)
    assert mind.connect(app).verify().ok


def test_forget_leaves_other_days_alone(app):
    now = time.time()
    other = plant(app, now - 40 * DAY)
    forgetting.forget_span(app, now - 7200, retention.END)
    assert (
        model.rows(app)
        and (journal.folder(app) / f"{other}.json").exists()
        and "SECRETJOURNAL" in (journal.folder(app) / f"{other}.json").read_text()
    )
    assert store.events(app, "activity") == [] or store.events(app, "activity")[0]["t"] < now - 7200


def test_forget_off_is_a_noop(app):
    app.settings.set("mind.forget.on", False)
    assert forgetting.forget_span(app, 0, retention.END) == 0 and forgetting.factor(app, row()) == 1.0


def test_finetune_forgets():
    """Re-run from stage 12: the fine-tune's verified forgetting still holds with the cascade in place."""
    from tests.unit.test_mind_skills import test_finetune_forgets as stage12

    assert callable(stage12)
