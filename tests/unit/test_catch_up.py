"""Missed-class catch-up: a class skipped, or over before you were up, gets a catch-up task due before the course's
next class and a lecture note stub; a class you were up for doesn't; "Went to ..." takes it back."""

import datetime as dt

import pytest

from kurooto.modules import subjects as subjects_mod

DAY = dt.date(2026, 10, 23)  # a Friday


@pytest.fixture
def sub(env, monkeypatch):
    app = env.app
    clock = {"t": dt.datetime.combine(DAY, dt.time(17, 0))}
    monkeypatch.setattr(subjects_mod, "now", lambda: clock["t"])
    app.settings.set(
        "subjects.list",
        [
            {"slug": "physics-of-the-atmosphere", "name": "Physics of the Atmosphere", "aliases": ["pota"]},
            {"slug": "point-set-topology", "name": "Point Set Topology", "aliases": ["pst"]},
            {"slug": "time-series", "name": "Time Series", "aliases": ["tsa"]},
        ],
    )
    app.settings.set(
        "subjects.timetable",
        [
            {"day": "fri", "start": "11:00", "end": "11:55", "subject": "physics-of-the-atmosphere"},
            {"day": "fri", "start": "14:00", "end": "14:55", "subject": "point-set-topology"},
            {"day": "fri", "start": "16:00", "end": "16:55", "subject": "time-series"},
            {"day": "mon", "start": "11:00", "end": "11:55", "subject": "physics-of-the-atmosphere"},
        ],
    )
    env.on("subjects", "deadlines")
    return env, app.modules["subjects"], clock


def test_classes_over_before_you_were_up_get_a_catch_up(sub, monkeypatch):
    env, s, clock = sub
    woke = dt.datetime.combine(DAY, dt.time(15, 10))
    monkeypatch.setattr(s, "woke_at", lambda day: woke)
    lines = s.catch_up()
    assert [x.split(" (")[0] for x in lines] == ["Physics of the Atmosphere", "Point Set Topology"]  # not TSA at 16
    dl = env.app.modules["deadlines"]
    items = {it["title"]: it for it in dl.items().values()}
    pota = items["Catch up: Physics of the Atmosphere (Fri 23 Oct class)"]
    assert pota["due"].startswith("2026-10-26T11:00") and pota["kind"] == "task"  # Monday's class
    assert items["Catch up: Point Set Topology (Fri 23 Oct class)"]["due"].startswith("2026-10-30T14:00")  # next Fri
    from kurooto.core import layout

    note = layout.path(env.app, "lecture", subject="physics-of-the-atmosphere", date="2026-10-23", slug="missed-class")
    assert "## What was covered" in note.read_text()
    assert s.catch_up() == []  # once
    # "Went to ..."
    out = s.callbacks()["cup"]("2026-10-23|physics-of-the-atmosphere", "went")
    assert out.startswith("OK, you went") and not note.exists()
    assert dl.items()[pota_id(dl, "Physics")]["status"] == "ignored"


def pota_id(dl, word):
    return next(i for i, it in dl.items().items() if word in it["title"])


def test_a_skipped_class_and_an_existing_lecture_note(sub, monkeypatch):
    env, s, clock = sub
    monkeypatch.setattr(s, "woke_at", lambda day: dt.datetime.combine(DAY, dt.time(8)))
    from kurooto.core import layout

    have = layout.path(env.app, "lecture", subject="point-set-topology", date="2026-10-23", slug="compactness")
    have.parent.mkdir(parents=True, exist_ok=True)
    have.write_text("# Compactness\n")
    s.set_skip(["point-set-topology"], day=DAY)
    lines = s.catch_up()
    assert len(lines) == 1 and "skipped" in lines[0] and "2026-10-23-compactness" in lines[0]


def test_off_or_up_in_time_nothing(sub, monkeypatch):
    env, s, clock = sub
    monkeypatch.setattr(s, "woke_at", lambda day: None)
    assert s.catch_up() == []
    env.app.settings.set("subjects.catch_up", False)
    s.set_skip(["time-series"], day=DAY)
    assert s.catch_up() == []


def test_no_next_class_due_in_three_days(sub, monkeypatch):
    env, s, clock = sub
    env.app.settings.set(
        "subjects.timetable", [{"day": "fri", "start": "11:00", "end": "11:55", "subject": "time-series"}]
    )
    env.app.settings.set("subjects.term_ends", "2026-10-24")  # no classes after the term
    monkeypatch.setattr(s, "woke_at", lambda day: dt.datetime.combine(DAY, dt.time(15)))
    assert s.catch_up()
    (it,) = env.app.modules["deadlines"].items().values()
    assert it["due"].startswith("2026-10-26T18:00")
