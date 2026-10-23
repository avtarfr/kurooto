"""Curious and remembering (modules/curious.py, in Dreaming's morning message): a topic asked about 3+ times this week
with no note gets one line (Make a stub / Not interested); a note or quiz subject from 10-30 days ago, or an
anniversary, gets one line (Open it / Less of this); neither comes back for 30 days."""

import datetime as dt
import os
import time

import pytest

from kurooto.core import layout
from kurooto.modules import curious

SUBJECTS = [{"slug": "stochastic-calculus", "name": "Stochastic Calculus", "aliases": ["stoch"]}]


@pytest.fixture
def dream(env, monkeypatch):
    app = env.app
    app.settings.set("subjects.list", SUBJECTS)
    env.on("subjects", "deadlines", "dreaming")
    asked: list[str] = []
    rows = lambda t, limit=500: [(f"j{i}", x, x, "", time.time(), "you", "") for i, x in enumerate(asked)]  # noqa: E731
    monkeypatch.setattr(app.jobs, "finished_since", rows)
    course = layout.path(app, "course", subject="stochastic-calculus")
    course.parent.mkdir(parents=True, exist_ok=True)
    course.write_text("# Stochastic Calculus\n\nMy course page.\n")
    return env, app.modules["dreaming"], asked


def offer(env, word):
    """The callback data of the last message's button with this label."""
    import json

    for _m, p in reversed(env.fake.sent):
        mk = p.get("reply_markup") if isinstance(p, dict) else None
        mk = json.loads(mk) if isinstance(mk, str) else mk or {}
        for row in mk.get("inline_keyboard", []):
            for b in row:
                if b["text"] == word:
                    return b["callback_data"]
    raise AssertionError(f"no {word} button")


def test_topic_phrases_are_conservative():
    got = curious.phrases("Can you derive the Fokker–Planck equation for an OU process?")
    assert "fokker planck equation" in got and got["fokker planck equation"] == "Fokker–Planck equation"
    assert curious.phrases("state Itô's lemma again")["ito lemma"] == "Itô's lemma"
    assert curious.phrases("what about Navier–Stokes") == {"navier stokes": "Navier–Stokes"}
    for plain in ("check Google Classroom for me", "remind Riya about the party", "make my notes better"):
        assert curious.phrases(plain) == {}, plain


def test_a_topic_asked_three_times_gets_a_stub_once(dream):
    env, d, asked = dream
    asked += [
        "explain the Fokker-Planck equation for stoch",
        "derive the Fokker–Planck equation",
        "Fokker Planck equation stationary solution?",
    ]
    text = d.morning()
    assert "You've asked about the Fokker-Planck equation 3 times this week and there's no note on it." in text
    stub = env.press(offer(env, "Make a stub"))
    assert stub == "Made a stub: stochastic-calculus/fokker-planck-equation."
    note = env.app.workspace / "stochastic-calculus" / "fokker-planck-equation.md"
    assert note.read_text().startswith("---\nmade_by:") and "# Fokker-Planck equation" in note.read_text()
    course = (env.app.workspace / "stochastic-calculus" / "course.md").read_text()
    assert "My course page." in course and "[[stochastic-calculus/fokker-planck-equation|" in course
    # a note now exists (and it was shown): not again
    assert "Fokker" not in (d.report(send=False) or "")


def test_not_interested_and_a_stub_note(dream, monkeypatch):
    env, d, asked = dream
    asked += ["what's Itô's lemma", "Itô's lemma proof", "use Itô's lemma here"]
    assert "Itô's lemma 3 times" in d.morning()
    out = env.press(offer(env, "Not interested"))
    assert out.startswith("OK, not interested in Itô's lemma")
    from kurooto.core.notinterested import ignored_topics

    assert ignored_topics(env.app) == ["Itô's lemma"]
    # a concept note that's only a stub, asked about by name
    m = env.app.workspace / "stochastic-calculus" / "martingale.md"
    m.write_text("# Martingale\n\nTODO\n")
    asked[:] = ["is this a martingale", "martingales and stopping times", "martingale convergence"]
    assert d.report(send=False) == ""  # one a day: today's was Itô's lemma
    monkeypatch.setattr(curious, "now", lambda: dt.datetime.now() + dt.timedelta(days=1))
    line = d.report(send=False)
    assert "You've asked about Martingale 3 times this week and its note is only a stub" in line


def test_a_note_from_twelve_days_ago_comes_back_once(dream, monkeypatch):
    env, d, asked = dream
    root = env.app.workspace / "stochastic-calculus"
    old = root / "2026-10-01-ito-integral.md"
    old.write_text("# The Itô integral\n\n" + "Lots of words about the integral, written in class. " * 5)
    t = time.time() - 12 * 86400
    os.utime(old, (t, t))
    dl = env.app.modules["deadlines"]
    dl.add("Stochastic Calculus midsem", dt.datetime.now() + dt.timedelta(days=5), kind="exam",
           subject="stochastic-calculus")  # fmt: skip
    text = d.morning()
    assert "You last worked on The Itô integral 12 days ago; Stochastic Calculus midsem is in 5 days." in text
    opened = []
    from kurooto.core import opener

    orig = opener.open_note
    opener.open_note = lambda s, p, f="": (opened.append(p), (True, ""))[1]
    try:
        assert env.press(offer(env, "Open it")) == "Opened it on your computer."
    finally:
        opener.open_note = orig
    assert opened == [old]
    assert "Itô integral" in d.report(send=False)  # /dream later today: today's line still
    monkeypatch.setattr(curious, "now", lambda: dt.datetime.now() + dt.timedelta(days=1))
    assert "Itô integral" not in (d.report(send=False) or "")  # not again for 30 days
    # Less of this: resurfacing off, with Undo
    assert env.app.settings.get("dreaming.resurface") is True
    out = curious.button(env.app, next(iter(curious.jload(curious.state_file(env.app), {})["offers"])), "less")
    assert out.startswith("Done: no more lines from the past") and env.app.settings.get("dreaming.resurface") is False


def test_an_anniversary(dream, monkeypatch):
    env, d, asked = dream
    note = layout.path(env.app, "project", project="ring-model")
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("# Ring model\n\n## Log\n- **2026-09-23** | git:ring — 2 commits: start\n")
    monkeypatch.setattr(curious, "now", lambda: dt.datetime(2026, 10, 23, 7, 30))
    assert "A month ago today you started work on Ring model." in d.report(send=False)
    assert curious.months_since(dt.date(2026, 1, 31), dt.date(2026, 2, 28)) == 1
    assert curious.months_since(dt.date(2025, 10, 23), dt.date(2026, 10, 23)) == 12
    assert curious.ago(12) == "A year ago today" and curious.ago(3) == "3 months ago today"
    assert curious.months_since(dt.date(2026, 9, 22), dt.date(2026, 10, 23)) is None


def test_off_and_call_searches_are_kept_and_forgotten(dream):
    env, d, asked = dream
    for _ in range(3):
        curious.searched(env.app, "Girsanov theorem")
    assert [a["via"] for a in curious.asks(env.app)] == ["call"] * 3
    env.app.settings.set("dreaming.curious", False)
    assert "Girsanov" not in (d.report(send=False) or "")
    env.app.settings.set("dreaming.curious", True)
    assert "the Girsanov theorem 3 times" in d.report(send=False)
    from kurooto.core import retention

    assert retention.forget(env.app, 0)["calls"] == 0 and curious.asks(env.app) == []


def test_a_note_under_another_name_or_a_course_page_is_not_a_gap(dream):
    env, d, asked = dream
    asked += ["Fokker-Planck equation again", "the Fokker–Planck equation", "Fokker Planck equation"]
    lec = env.app.workspace / "stochastic-calculus" / "2026-10-20-fokker-planck.md"
    lec.write_text("# Fokker-Planck\n\n" + "How a density moves under drift and diffusion, from class. " * 3)
    assert curious.gaps(env.app) == []
    lec.unlink()
    assert [g["topic"] for g in curious.gaps(env.app)] == ["the Fokker-Planck equation"]
    t = time.time() - 12 * 86400
    os.utime(env.app.workspace / "stochastic-calculus" / "course.md", (t, t))  # a course page isn't resurfaced
    assert curious.faded(env.app) == []
