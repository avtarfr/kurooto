"""Study links (0.9.0): Brain's study push Yes still sets the reminder, which now carries "Start 25 min" for Study
mode's timer tied to the deadline, and Study mode opens on that subject (L53, mind.study_push.start_timer); your own
reminders wait for a focus's break when you ask for it (L57, reminders.wait_for_break, off)."""

import datetime as dt

import pytest

from kurooto import mind
from kurooto.core import actions
from kurooto.core.clock import now
from kurooto.mind import study_push
from kurooto.mind.status import uneasy_target


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind", "subjects", "deadlines", "reminders", "study"])
    a.settings.set("availability.night.enabled", False)
    a.settings.set("subjects.list", [{"slug": "measure-theory", "name": "Measure Theory", "aliases": ["mt"]}])
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)) or "m1")
    yield a
    mind.forget_client(a)
    a.close()


def _deadline(app, title, hours, **kw):
    dl = app.modules["deadlines"]
    dl.add(title, now() + dt.timedelta(hours=hours), **kw)
    return next(i for i, it in dl.items().items() if it["title"] == title)


def _fire_reminder(app, key):
    job = app.scheduler.get(key)
    assert job is not None, key
    app.modules["reminders"]._fire(job.payload)  # noqa: SLF001
    return app.sent[-1]


def test_yes_sets_the_reminder_and_it_offers_to_start_the_timer(app):
    i = _deadline(app, "Measure Theory problem set", 60, subject="measure-theory")
    assert study_push.push(app)
    day = now().date().isoformat()
    assert study_push.button(app, day, "yes").startswith("Done: I'll remind you at ")
    text, kw = _fire_reminder(app, f"reminders:msp{day.replace('-', '')}")
    assert text.startswith("Reminder: 25 min of Measure Theory")
    rows = [[b[0] for b in row] for row in kw["buttons"]]
    assert rows == [["+10 min", "+1 h"], ["Start 25 min"]]
    data = kw["buttons"][1][0][1]
    assert data == f"msp:{day}:start"
    said = study_push.button(app, day, "start")
    assert said.startswith("Measure Theory: focus until ")  # only now, on the tap
    st = app.modules["study"]
    assert st.timer()["deadline"] == i and st.session()["deadline"] == i
    ev = app.events.tail(20, kinds={"study_session_start"})[-1]
    assert ev["deadline"] == i and ev["subject"] == "measure-theory"
    st.timer_reset()


def test_study_mode_and_the_glow_open_on_the_uneasy_subject(app):
    app.settings.set("subjects.list", [{"slug": "topology", "name": "Topology"},
                                       {"slug": "measure-theory", "name": "Measure Theory"}])  # fmt: skip
    i = _deadline(app, "Measure Theory problem set", 60, subject="measure-theory")
    assert actions.study_view(app)["subject"] == "topology"  # the first, before any line
    assert study_push.push(app)
    assert actions.study_view(app)["subject"] == "measure-theory"
    assert uneasy_target(app, f"deadline:{i}")["subject"] == "measure-theory"
    app.settings.set("mind.study_push.start_timer", False)
    assert actions.study_view(app)["subject"] == "topology"
    assert "subject" not in uneasy_target(app, f"deadline:{i}")


def test_off_the_reminder_is_as_before(app):
    app.settings.set("mind.study_push.start_timer", False)
    _deadline(app, "Measure Theory problem set", 60, subject="measure-theory")
    assert study_push.push(app)
    day = now().date().isoformat()
    study_push.button(app, day, "yes")
    _text, kw = _fire_reminder(app, f"reminders:msp{day.replace('-', '')}")
    assert [[b[0] for b in row] for row in kw["buttons"]] == [["+10 min", "+1 h"]]


# ------------------------------------------------------------------------------- reminders wait for a break
def test_reminders_wait_for_the_break_only_when_asked(app):
    rem, st = app.modules["reminders"], app.modules["study"]
    rem.add(now() + dt.timedelta(minutes=5), "stretch", key="reminders:r1")
    st.timer_start("mt")
    text, _ = _fire_reminder(app, "reminders:r1")
    assert text == "Reminder: stretch"  # off by default: it comes in the focus as before
    app.settings.set("reminders.wait_for_break", True)
    n = len(app.sent)
    rem._fire({"what": "call the library", "ref": "r2"})  # noqa: SLF001
    assert len(app.sent) == n  # waits
    job = app.scheduler.get("reminders:waitr2")
    assert job is not None and job.payload["released"] is True
    assert dt.datetime.fromtimestamp(job.next_run) <= dt.datetime.fromisoformat(st.timer()["ends"]) + dt.timedelta(
        seconds=1
    )
    st.timer_reset()  # a reset brings it at once
    assert app.sent[-1][0] == "Reminder: call the library"
    assert app.scheduler.get("reminders:waitr2") is None
    rem._fire({"what": "no focus now", "ref": "r3"})  # noqa: SLF001
    assert app.sent[-1][0] == "Reminder: no focus now"
