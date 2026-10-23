"""Missed-class catch-up: a class skipped, or over before you were up, gets a catch-up task due before the course's
next class and a lecture note stub; a class you were up for doesn't; "Went to ..." takes it back."""

import datetime as dt
import json

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


SLIDES = {"id": "m1", "title": "Slides: radiative transfer", "alternateLink": "https://classroom.example.com/m1"}
POTA = {"id": "c7", "name": "PHY 3203: Physics of the Atmosphere"}  # a Classroom course naming one of the subjects


def _classroom(env, monkeypatch, clock, google_on=True):
    """Google's Classroom on (as far as the catch-up asks), and what its checks remember."""
    from kurooto.modules import google_classroom as gc

    monkeypatch.setattr(gc, "now", lambda: clock["t"])
    if google_on:
        env.app.settings.set("modules.enabled", [*env.app.settings.get("modules.enabled"), "google"])
    gc.remember_posts(
        env.app,
        POTA,
        [
            ("material", {**SLIDES, "creationTime": "2026-10-23T06:10:00Z"}),
            ("announcement", {"id": "a1", "text": "No class on Monday", "creationTime": "2026-10-20T04:00:00Z"}),
        ],
    )
    return gc


def test_with_classroom_the_catch_up_lists_that_days_posts_and_later_ones_join_the_stub(sub, monkeypatch):
    env, s, clock = sub
    gc = _classroom(env, monkeypatch, clock)
    monkeypatch.setattr(s, "woke_at", lambda day: dt.datetime.combine(DAY, dt.time(8)))
    s.set_skip(["physics-of-the-atmosphere"], day=DAY)
    (line,) = s.catch_up()
    assert line.endswith("; on Classroom that day: Slides: radiative transfer https://classroom.example.com/m1")
    assert "No class on Monday" not in line  # another day's post
    assert "on Classroom that day" in env.fake.texts()[-1]
    from kurooto.core import layout

    stub = layout.path(env.app, "lecture", subject="physics-of-the-atmosphere", date="2026-10-23", slug="missed-class")
    text = stub.read_text()
    assert "## Classroom posts that day\n\n- [Slides: radiative transfer](https://classroom.example.com/m1)\n\n" in text
    assert text.index("## Classroom posts that day") < text.index("## What was covered")
    # the problem sheet goes up after the catch-up: it joins the stub, no second message
    sent = len(env.fake.texts())
    sheet = {"id": "w4", "title": "Problem sheet 4", "alternateLink": "https://classroom.example.com/w4"}
    gc.remember_posts(env.app, POTA, [("coursework", {**sheet, "creationTime": "2026-10-23T10:30:00Z"})])
    assert s.catch_up() == [] and len(env.fake.texts()) == sent
    text = stub.read_text()
    assert (
        text.count("## Classroom posts that day") == 1
        and "- [Problem sheet 4](https://classroom.example.com/w4)" in text
    )
    # "Went to ...": the stub goes, though it changed (Kurooto changed it)
    assert s.callbacks()["cup"]("2026-10-23|physics-of-the-atmosphere", "went").startswith("OK")
    assert not stub.exists()


def test_a_stub_you_wrote_in_gets_no_more_posts(sub, monkeypatch):
    env, s, clock = sub
    gc = _classroom(env, monkeypatch, clock)
    s.set_skip(["physics-of-the-atmosphere"], day=DAY)
    monkeypatch.setattr(s, "woke_at", lambda day: dt.datetime.combine(DAY, dt.time(8)))
    s.catch_up()
    from kurooto.core import layout

    stub = layout.path(env.app, "lecture", subject="physics-of-the-atmosphere", date="2026-10-23", slug="missed-class")
    stub.write_text(stub.read_text() + "Hydrostatic balance, scale height.\n")
    mine = stub.read_text()
    gc.remember_posts(env.app, POTA, [("material", {"id": "m2", "title": "More", "creationTime": "2026-10-23T11:00Z"})])
    s.catch_up()
    assert stub.read_text() == mine


def test_without_classroom_the_catch_up_is_as_before(sub, monkeypatch):
    env, s, clock = sub
    _classroom(env, monkeypatch, clock, google_on=False)  # posts kept from when it was on
    monkeypatch.setattr(s, "woke_at", lambda day: dt.datetime.combine(DAY, dt.time(8)))
    s.set_skip(["physics-of-the-atmosphere"], day=DAY)
    (line,) = s.catch_up()
    assert "Classroom" not in line
    from kurooto.core import layout

    stub = layout.path(env.app, "lecture", subject="physics-of-the-atmosphere", date="2026-10-23", slug="missed-class")
    assert "## Classroom posts" not in stub.read_text()


def test_classroom_posts_are_kept_a_month_and_by_course(env, monkeypatch):
    from kurooto.modules import google_classroom as gc

    monkeypatch.setattr(gc, "now", lambda: dt.datetime.combine(DAY, dt.time(12)))
    monkeypatch.setattr(gc, "not_interested", lambda a, text: "pep rally" if "pep rally" in text.lower() else None)
    gc.remember_posts(
        env.app,
        POTA,
        [
            ("material", {**SLIDES, "creationTime": "2026-10-23T06:10:00Z"}),
            ("announcement", {"id": "a2", "text": "Pep rally tomorrow", "creationTime": "2026-10-23T06:00:00Z"}),
            ("material", {"id": "m0", "title": "Old slides", "creationTime": "2026-08-01T06:00:00Z"}),
        ],
    )
    kept = json.loads((env.app.paths.state / "classroom-posts.json").read_text())
    assert kept["c7"]["name"] == POTA["name"] and list(kept["c7"]["posts"]) == ["material:m1"]
    env.app.settings.set("modules.enabled", [*env.app.settings.get("modules.enabled"), "google", "subjects"])
    env.app.settings.set("subjects.list", [{"slug": "pota", "name": "Physics of the Atmosphere", "aliases": []}])
    assert [p["title"] for p in gc.posts_on(env.app, "pota", DAY)] == ["Slides: radiative transfer"]
    env.app.settings.set("classroom_notes.folders", {POTA["name"]: "atmosphere"})  # your folder for it wins
    assert gc.posts_on(env.app, "pota", DAY) == [] and gc.posts_on(env.app, "atmosphere", DAY)
