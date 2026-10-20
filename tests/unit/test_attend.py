"""Attendance and standing (modules/attendance.py): counting from the timetable and skips, holidays and exam periods,
each course's rule, labs on their own, corrections, /skip asking before it crosses the line, the Sunday line, the
plain-English question, the call tools, and marks behind "set up marks?". A fake clock throughout."""

from __future__ import annotations

import datetime as dt

import pytest

from kurooto.modules import attendance as att_mod
from kurooto.modules import subjects as subj_mod
from kurooto.modules import text as text_mod
from kurooto.modules.attendance import Course, grade_ranges

WED = dt.datetime(2026, 10, 21, 12, 0)  # a Wednesday, after the morning class
LA, STATS, PHL = "linear-algebra", "statistics", "physics-lab"


class Clock:
    def __init__(self, monkeypatch, t):
        self.t = t
        for mod in (att_mod, subj_mod, text_mod):
            monkeypatch.setattr(mod, "now", lambda: self.t)


def buttons(env):
    sent = [p for m, p in env.fake.sent if m == "sendMessage"]
    markup = sent[-1].get("reply_markup") or {}
    return [b for row in markup.get("inline_keyboard", []) for b in row]


@pytest.fixture
def term(env, monkeypatch):
    """Linear Algebra on Mon, Wed, Fri at 9, Statistics on Tue at 11 and a Physics Lab on Fri afternoon; counted from
    Mon 5 Oct, with 9 Oct a holiday and LA skipped on 14 Oct."""
    clock = Clock(monkeypatch, WED)
    env.app.settings.set("availability.night.enabled", False)
    env.on("subjects")
    env.say("/subject add Linear Algebra (la, linalg)")
    env.say("/subject add Statistics (stats)")
    env.say("/subject add Physics Lab (phl)")
    for row in ("mon 09:00-09:55 la", "wed 09:00-09:55 la", "fri 09:00-09:55 la", "tue 11:00-11:55 stats"):
        env.say(f"/class {row}")
    env.say("/class fri 14:00-16:55 phl")
    env.app.settings.set("subjects.holidays", ["2026-10-09"])
    env.app.modules["subjects"].set_skip([LA], day=dt.date(2026, 10, 14))
    env.on("attendance")
    env.app.settings.set("attendance.since", "2026-10-05")
    env.clock = clock
    return env


def course(env, key) -> Course:
    return env.app.modules["attendance"].courses()[key]


# ------------------------------------------------------------------------------------------------ the maths
def test_spare_and_lines():
    c = Course("la", "la", "Linear Algebra", "LA", False, 75, held=7, attended=6)
    assert c.pct == 85 and c.spare() == 1  # 6/8 is still 75%, 6/9 isn't
    assert c.line() == "Linear Algebra 85% (6/7), you can miss 1 more"
    c.left = 4  # 11 in the term: 10 attended at best, 8.25 needed
    assert c.spare() == 1 and c.line().endswith("you can miss 1 more this term")
    under = Course("st", "st", "Statistics", "ST", False, 75, held=24, attended=17)
    assert under.spare() < 0
    assert under.line() == "Statistics 70% (17/24): under 75%; go to the next 4 to get back"  # 21/28 = 75%
    under.left = 2
    assert "even going to every class left (at most 73%)" in under.line()
    under.left = 20  # far from the end: under now, fine by the end
    assert under.spare() == 4 and "under 75% for now; you can still miss 4 more this term" in under.line()
    full = Course("lab", "lab", "Physics Lab", "PHL", True, 100, held=3, attended=2)
    assert full.line() == "Physics Lab 66% (2/3): under 100%, which it can't get back to"
    assert Course("x", "x", "X", "X", False, 75).line() == "X: no classes yet"
    assert c.brief() == "LA 85%, 1 to spare" and under.brief() == "ST 70%, 4 to spare"


def test_grade_ranges():
    grades = {"A": 85, "B": 70, "C": 55, "D": 40}
    assert grade_ranges(31.5, 50, 100, grades) == [
        "A out of reach",
        "B 77%+",
        "C 47-76%",
        "D 17-46%",
        "under 17%: below D",
    ]
    assert grade_ranges(45, 50, 100, grades) == ["A 80%+", "B 50-79%", "C 20-49%", "D under 20%"]
    assert grade_ranges(90, 10, 100, {"A": 85}) == ["A whatever you get"]


# --------------------------------------------------------------------------------------------- counting
def test_off_until_turned_on(env):
    assert "attendance" not in (env.app.settings.get("modules.enabled") or [])
    assert env.app.modules["attendance"].requires == ("subjects",)
    env.on("subjects")
    env.say("/subject add Linear Algebra (la)")
    env.say("/class mon 09:00-09:55 la")
    assert "skipping: Linear Algebra" in env.say("/skip la")  # no attendance warning while it's off
    assert "Attendance" not in env.app.modules["weekly"].summary()


def test_counts_from_the_timetable(term):
    a = term.app.modules["attendance"]
    cs = a.courses()
    la = cs[LA]
    assert (la.attended, la.held) == (6, 7)  # 8 Mon/Wed/Fri mornings, 9 Oct a holiday, 14 Oct skipped
    assert (cs[STATS].attended, cs[STATS].held) == (3, 3)
    assert cs[PHL].lab and cs[PHL].held == 1  # a subject named like a lab is a lab; 9 Oct was a holiday
    assert cs[LA].left is None  # no last day of classes
    out = term.say("/attendance")
    assert "an estimate" in out
    assert "Linear Algebra 85% (6/7), you can miss 1 more" in out
    assert "/term ends" in out and "/attendance set la 23/30" in out
    term.say("/term ends 2026-10-30")
    la = course(term, LA)
    assert la.left == 4 and la.spare() == 1  # 23, 26, 28, 30 Oct still to come
    term.say("/term exams 2026-10-26 to 2026-10-28")
    assert course(term, LA).left == 2  # exam periods don't count
    term.clock.t = dt.datetime(2026, 11, 2, 12, 0)
    la = course(term, LA)
    assert la.ended and la.held == 9 and "the term's classes are over" in la.line()


def test_rules_and_labs(term):
    assert "Linear Algebra's rule is 90% now" in term.say("/attendance rule la 90")
    assert course(term, LA).rule == 90
    assert "follows the usual rule again" in term.say("/attendance rule la clear")
    assert "Every course's rule is 80% now" in term.say("/attendance rule 80")
    assert course(term, STATS).rule == 80 and course(term, PHL).rule == 75  # labs keep theirs
    term.say("/attendance rule labs 100")
    assert course(term, PHL).rule == 100
    term.say("/class thu 14:00-16:55 la")
    out = term.say("/attendance lab thu 14:00")
    assert "Thu 14:00 is the Linear Algebra lab now" in out
    cs = term.app.modules["attendance"].courses()
    assert cs[LA + ":lab"].name == "Linear Algebra lab" and cs[LA + ":lab"].held == 2 and cs[LA + ":lab"].rule == 100
    assert cs[LA].held == 7  # the lecture count is apart
    assert "Linear Algebra lab" in term.say("/attendance la lab")
    assert "no class starting Sat 10:00" in term.say("/attendance lab sat 10:00")
    term.say("/attendance lab thu 14:00 off")
    assert LA + ":lab" not in term.app.modules["attendance"].courses()
    term.say("/attendance rule all clear")
    assert course(term, STATS).rule == 75


def test_set_corrects_drift(term):
    out = term.say("/attendance set la 20/25")
    assert "20/25 as of now" in out and "Linear Algebra 80% (20/25)" in out
    term.clock.t = dt.datetime(2026, 10, 23, 10, 0)  # Friday's class is over
    assert (course(term, LA).attended, course(term, LA).held) == (21, 26)
    assert "set la clear" in term.say("/attendance la")
    assert "That's attended/held" in term.say("/attendance set la 30/25")
    term.say("/attendance set la clear")
    assert course(term, LA).held == 8
    assert "Counting from Mon 12 Oct" in term.say("/attendance since 2026-10-12")
    assert course(term, LA).held == 6


def test_since_is_the_day_it_was_turned_on(env, monkeypatch):
    Clock(monkeypatch, WED)
    env.on("subjects", "attendance")
    assert env.app.settings.get("attendance.since") == "2026-10-21"
    ok, why = env.app.modules["attendance"].health()
    assert not ok and "no classes on your timetable" in why
    check = env.app.modules["attendance"].health_check()
    assert check.probe(False)[0] is False


# ------------------------------------------------------------------------------------------------- /skip
def test_skip_asks_before_crossing_the_line(term):
    out = term.say("/skip la")  # today's class is over: 5/7 would be 71%
    assert "would leave you under the line" in out and "Linear Algebra 71% (5/7)" in out
    assert "Skip anyway?" in out
    assert [b["text"] for b in buttons(term)] == ["Skip anyway", "Don't skip"]
    subj = term.app.modules["subjects"]
    assert LA not in subj.skipped()
    keep = next(b["callback_data"] for b in buttons(term) if b["text"] == "Don't skip")
    assert "Not marked" in term.press(keep)
    assert LA not in subj.skipped()
    term.say("/skip la")
    go = next(b["callback_data"] for b in buttons(term) if b["text"] == "Skip anyway")
    assert "Marked: you're skipping Linear Algebra today" in term.press(go)
    assert LA in subj.skipped()
    assert "settled already" in term.press(go)
    assert course(term, LA).attended == 5


def test_skip_anyway_and_fine_skips(term):
    assert "skipping: Linear Algebra" in term.say("/skip la anyway")
    assert "Attendance (an estimate): Linear Algebra 71% (5/7)" in term.fake.texts()[-1]
    term.say("/attend la")
    out = term.say("not going to stats on tuesday")  # 3/3 so far: one planned skip is fine
    assert "On Tue 27 Oct you're skipping: Statistics" in out
    assert "you can miss 0 more (besides the 1 you've said you'll skip)" in out
    out = term.say("skipping la today")  # plain English: no buttons, a way to say it anyway
    assert "Not marked" in out and '"anyway"' in out
    assert "skipping: Linear Algebra" in term.say("skipping la today anyway")


def test_call_tool_warns_first(term):
    tool = next(t for t in term.app.modules["subjects"].call_tools() if t.name == "skip_class")
    out = tool.run({"subject": "Linear Algebra"})
    assert "Not marked" in out and "anyway=yes" in out
    assert LA not in term.app.modules["subjects"].skipped()
    assert "Skipping Linear Algebra today" in tool.run({"subject": "Linear Algebra", "anyway": "yes"})
    att_tool = next(t for t in term.app.modules["attendance"].call_tools() if t.name == "attendance")
    assert "Linear Algebra 71% (5/7)" in att_tool.run({"subject": "la"})
    assert att_tool.writes is False


def test_questions_dont_mark_skips(term):
    out = term.say("can I skip LA tomorrow?")  # Thursday: no LA lecture
    assert "has no class on Thu 22 Oct" in out
    out = term.say("can i skip la on friday")
    assert out.startswith("Yes. After skipping Linear Algebra on Fri 23 Oct")
    assert LA not in term.app.modules["subjects"].skipped(dt.date(2026, 10, 23))
    assert "Better not" in term.say("can I skip la today?")
    assert "Linear Algebra 85% (6/7)" in term.say("how's my attendance?")


def test_sunday_line(term):
    term.on("weekly")
    lines = [x for x in term.app.modules["weekly"].summary().splitlines() if x.startswith("Attendance")]
    assert lines == ["Attendance (an estimate): PHL 100%, 0 to spare; LA 85%, 1 to spare; Statistics 100%, 1 to spare"]
    term.app.settings.set("attendance.weekly", False)
    assert "Attendance" not in term.app.modules["weekly"].summary()


# -------------------------------------------------------------------------------------------------- marks
def test_standing_offers_marks_once(term):
    out = term.say("/standing")
    assert "Where you stand (an estimate)" in out and "Set up marks too?" in out
    labels = {b["text"]: b["callback_data"] for b in buttons(term)}
    assert set(labels) == {"Set up marks", "Not now"}
    assert "How to set up marks" in term.press(labels["Set up marks"])
    assert "/marks la weights" in term.fake.texts()[-1]
    term.say("/standing")
    assert "No marks, then" in term.press(next(b["callback_data"] for b in buttons(term) if b["text"] == "Not now"))
    assert "Set up marks too?" not in term.say("/standing")


def test_marks_and_grade_ranges(term):
    assert "Set Linear Algebra's weightage first" in term.say("/marks la midsem 21/30")
    out = term.say("/marks la weights midsem 30, quizzes 20, endsem 50")
    assert out == "Linear Algebra: midsem 30, quizzes 20, endsem 50."
    term.say("/marks la midsem 21/30")
    out = term.say("/marks linear algebra quizzes 10.5/20")
    assert "31.5 of the 50 so far" in out and "Grade lines" in out
    term.say("/marks grades A 85, B 70, C 55, D 40")
    out = term.say("/standing")
    assert "Set up marks too?" not in out
    assert "Marks: 31.5 of the 50 so far; on what's left (endsem, worth 50): A out of reach, B 77%+, C 47-76%" in out
    assert "no part called final" in term.say("/marks la final 40/50")
    term.say("/marks la endsem 32/50")
    assert "63.5 of 100, all in; that's C on your grade lines" in term.say("/marks la")
    term.say("/marks la weights midsem 30, quizzes 20, final 50")  # scores of parts that stay are kept
    assert "31.5 of the 50 so far" in term.say("/marks la")
    term.say("/marks la grades A 60")
    assert "A 57%+" in term.say("/marks la")  # a course's own lines win
    assert "forgotten" in term.say("/marks la clear")
    assert term.say("/marks").startswith("Marks, an estimate")
