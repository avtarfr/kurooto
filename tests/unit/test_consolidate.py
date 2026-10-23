"""Dreaming consolidates (modules/consolidate.py): the same thing remembered twice and lines that disagree, found by
rules each night, shown in the morning message with Keep A / Keep B / Both true; nothing changes until a tap, and each
change has an Undo. Gist words never reach the state file."""

import datetime as dt
import json
import time

import pytest

from kurooto.core import gists, ledger, proc
from kurooto.core.clock import now
from kurooto.core.state import jload
from kurooto.modules import consolidate as cons
from kurooto.modules import remember
from kurooto.providers.base import Result, Verdict

MON = dt.date(2026, 10, 19)


def side(t, text, day=MON, sub="", group=""):
    s = cons.Side(t, {"t": t, "x": text}, text, "here", day, group=group, sub=sub)
    s.r = cons.read(text, day)
    return s


def test_reading_a_line():
    r = cons.read("Quiz 3 is due Fri at 5pm", MON)
    assert r.ids == {"quiz#3"} and r.values == {"date": {"2026-10-23"}, "time": {"17:00"}}
    assert r.terms == {"due", "quiz#3"}
    assert cons.read("No calls before 8", MON).values == {"time": {"08:00"}}
    assert cons.read("Exam on 3 Nov", MON).values == {"date": {"2026-11-03"}}
    assert cons.read("Got 3 marks for it", MON).values == {"num": {"3"}}  # not the 3rd of March
    assert cons.read("I sat with Mira on Sunday", MON).values == {"date": {"2026-10-25"}}  # "sat" isn't a day


def test_the_rules():
    assert cons.check(side("fact", "No calls before 8"), side("fact", "Don't call me before 8am")) == (
        "dup",
        "the same thing twice",
    )
    assert cons.check(side("fact", "No calls before 8"), side("fact", "No calls before 9")) == (
        "clash",
        "different times",
    )
    due_fri = side("note", "Quiz 3 is due Fri", MON)
    moved = side("note", "Quiz 3 moved, due Mon now", MON + dt.timedelta(days=2))
    assert cons.check(due_fri, moved) == ("clash", "different dates")
    assert cons.check(due_fri, side("note", "Quiz 4 is due Mon", MON))[0] == ""  # two quizzes
    studied = side("note", "Studied for quiz 3 on Thursday", MON)
    assert cons.check(studied, moved)[0] == ""  # when you did something, not when it's due
    a, b = side("gist", "Call (wake-up): set alarm", sub="call"), side("gist", "Call (wake-up): set alarm", sub="call")
    assert cons.check(a, b)[0] == "dup"
    b.day = MON + dt.timedelta(days=1)
    assert cons.check(a, b)[0] == ""  # a routine's gist each day isn't a copy
    assert cons.check(side("gist", "Quiz 3 due Fri"), side("note", "Quiz 3 is due Mon"))[0] == ""  # gists: copies only
    one = side("note", "Quiz 3 is due Fri", group="day:j")
    assert cons.check(one, side("note", "Quiz 3 is due Mon", group="day:j"))[0] == ""  # one note's own lines


def keyboard(env) -> dict:
    """The last message's buttons: label -> callback data."""
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    markup = sent.get("reply_markup") or {}
    markup = json.loads(markup) if isinstance(markup, str) else markup
    return {b["text"]: b["callback_data"] for row in markup.get("inline_keyboard", []) for b in row}


def buttons_of(env):
    return {k: v for k, v in keyboard(env).items() if v.startswith("dcn:")}


def help_text(app):
    return remember.help_file(app).read_text()


def test_two_lines_that_disagree_wait_for_a_tap_and_undo(env):
    app = env.app
    env.on("dreaming")
    remember.keep(app, "No calls before 8")
    remember.keep(app, "No calls before 9")
    before = help_text(app)
    text = app.modules["dreaming"].morning()
    assert "Worth a look in what I remember (nothing changes until you tap):" in text
    assert '1. These disagree (different times): A "No calls before 8"' in text and '"No calls before 9"' in text
    assert help_text(app) == before  # never a silent edit
    btn = buttons_of(env)
    assert set(btn) == {"1: Keep A", "1: Keep B", "1: Both true"}
    said = env.press(btn["1: Keep B"])
    assert said.startswith('Took "No calls before 8" out of')
    assert "No calls before 8" not in help_text(app) and "No calls before 9" in help_text(app)
    assert env.press(keyboard(env)["Undo"]) == "Put back."
    assert "No calls before 8" in help_text(app)
    assert env.press(btn["1: Keep B"]) != "That's settled already."  # asked again after the Undo
    st = jload(cons.state_file(app), {})
    assert not st["items"] and len(st["decided"]) == 1


def test_both_true_is_remembered_and_shown_twice_is_let_go(env):
    app = env.app
    env.on("dreaming")
    remember.keep(app, "Gym at 7 on weekdays")
    remember.keep(app, "Gym at 6 on weekdays")
    dream = app.modules["dreaming"]
    dream.morning()
    btn = buttons_of(env)
    assert env.press(btn["1: Both true"]).startswith("Both true, then")
    cons.scan(app)
    assert cons.section(app, send=False) == ("", [])  # not asked again
    remember.keep(app, "Stand-up call at 10")
    remember.keep(app, "Stand-up call at 11")
    cons.scan(app)
    for _ in range(2):
        assert "Stand-up call" in cons.section(app, send=True)[0]
    assert cons.section(app, send=True) == ("", [])  # shown twice without a tap: let go


def test_a_note_against_a_deadline_moves_it_only_on_a_tap(env):
    app = env.app
    env.on("deadlines", "dreaming")
    dl = app.modules["deadlines"]
    today = now().date()
    fri = today + dt.timedelta(days=(4 - today.weekday()) % 7 or 7)
    dl.add("Stats quiz 3", dt.datetime.combine(fri, dt.time(17, 0)))
    i = next(iter(dl.items()))
    yesterday = today - dt.timedelta(days=1)
    note = app.workspace / "journal" / f"{yesterday.isoformat()}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    mon = fri + dt.timedelta(days=3)
    note.write_text(f"# {yesterday}\n\n- Stats quiz 3 postponed, due {mon:%d %b} now\n- Lunch with Mira\n")
    text = app.modules["dreaming"].morning()
    assert "These disagree (different dates)" in text and "Stats quiz 3" in text
    assert dl.items()[i]["due"].startswith(fri.isoformat())  # nothing moved yet
    btn = buttons_of(env)
    said = env.press(btn["1: Keep A"])  # A: the note (the older line)
    assert said.startswith("Moved: Stats quiz 3") and dl.items()[i]["due"].startswith(mon.isoformat())
    assert "postponed" in note.read_text()  # your note is never changed
    assert env.press(keyboard(env)["Undo"]) == "The deadline is back on its old date."
    assert dl.items()[i]["due"].startswith(fri.isoformat())


def test_duplicate_gists_merge_on_a_tap_and_their_words_stay_sealed(env):
    app = env.app
    env.on("dreaming")
    t = time.time() - 3600
    gists._save(
        app,
        [
            {"at": t, "kind": "request", "text": "Plan my zeolite revision · answered"},
            {"at": t + 60, "kind": "request", "text": "Plan my zeolite revision · answered"},
        ],
    )
    assert cons.scan(app) == 1
    raw = cons.state_file(app).read_bytes()
    assert b"zeolite" not in raw  # references only
    text, rows = cons.section(app, send=True)
    assert text.count("zeolite") == 2 and "The same thing twice" in text
    assert [b[0] for b in rows[0]] == ["1: Keep A", "1: Keep B", "1: Keep both"]
    assert len(gists.load(app)) == 2
    assert env.press(rows[0][0][1]) == "Dropped the other gist."
    assert len(gists.load(app)) == 1
    assert b"zeolite" not in cons.state_file(app).read_bytes()  # the Undo keeps them sealed
    assert env.press(keyboard(env)["Undo"]) == "The gist is back."
    assert len(gists.load(app)) == 2


def test_off_and_a_locked_ledger_do_nothing(env):
    app = env.app
    remember.keep(app, "No calls before 8")
    remember.keep(app, "No calls before 9")
    app.settings.set("dreaming.consolidate", False)
    assert cons.scan(app) == 0 and cons.section(app, send=True) == ("", [])
    app.settings.set("dreaming.consolidate", True)
    ledger.of(app).add("gist", "x")  # rows sealed under a key...
    app.secrets.delete(ledger.KEY)  # ...that can't be read now
    ledger.close(app)
    assert cons.scan(app) == 0


def test_a_second_opinion_only_when_allowed(env, monkeypatch):
    app = env.app
    remember.keep(app, "Send weekly summaries on Sunday evening")
    remember.keep(app, "Weekly summaries should arrive Sunday night")
    asked = []

    class Brain:
        def complete(self, prompt, **kw):
            asked.append(prompt)
            return Result(Verdict.OK, "SAME")

    monkeypatch.setattr(cons, "_brain", lambda app, how: Brain())
    app.settings.set("dreaming.consolidate_ai", "off")
    cons.scan(app)
    assert asked == [] and cons.section(app, send=False) == ("", [])
    app.settings.set("dreaming.consolidate_ai", "local")
    cons.scan(app)
    assert len(asked) == 1 and "Weekly summaries" in asked[0]
    assert "The same thing twice" in cons.section(app, send=False)[0]


@pytest.fixture
def g(env, monkeypatch):
    g = env.app.modules["gbrain"]
    monkeypatch.setattr(g.prereqs.items["gbrain"], "find", lambda: "/x/gbrain")
    (env.app.paths.state / "gbrain.json").write_text(json.dumps({"initialised": True, "embeddings": "off"}))
    return g


def test_the_notes_brains_contradictions_join_the_morning(env, g, monkeypatch):
    app = env.app
    report = {
        "run_id": 4,
        "contradictions": [
            {
                "verdict": "contradiction",
                "severity": "medium",
                "axis": "the room of the exam",
                "a": {"slug": "stats/course", "text": "The midterm is in room 101."},
                "b": {"slug": "journal/2026-10-20", "text": "Midterm in room 204."},
            },
            {"verdict": "temporal_supersession", "severity": "high", "axis": "x", "a": {}, "b": {}},
            {"verdict": "contradiction", "severity": "low", "axis": "a name", "a": {}, "b": {}},
        ],
    }
    seen = []

    def run(*args, **kw):
        seen.append(args)
        return proc.Result(0, json.dumps(report), "")

    monkeypatch.setattr(g, "run", run)
    env.on("gbrain", "dreaming")
    assert [f["axis"] for f in g.contradictions()] == ["the room of the exam"]
    assert seen[-1] == ("find-contradictions", "--json", "--limit", "20")  # reads the last report; never the probe
    text = app.modules["dreaming"].report(send=False)
    assert "These disagree (the room of the exam)" in text and "room 101" in text
    btn = cons.section(app, send=False)[1][0]
    assert env.press(btn[1][1]).endswith("is in your note stats/course; that's yours to change.")
    app.settings.set("gbrain.contradictions", False)
    n = len(seen)
    assert g.contradictions() == [] and len(seen) == n
