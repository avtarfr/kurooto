"""0.9.1's core links: the phone's place names for reminders (L60), place events for add-ons (L114), the hours you
usually work on a subject (L119), what a kind of deadline really took (L144), open threads in the greeting and the
Agent plan (L45), bedside mode for sleep and Calm's evening bundle (L11), the desk-break bid (L22), one shared read
of the chat's turns (L94), learned skills tested and counted (L128), quiet feedback buttons in the app (L81) and the
phone's other calls (L87). Each behind its own switch. Fakes only: no AI, no network, no camera."""

# ruff: noqa: F811 (the fixtures imported from the other tests are taken as arguments)

from __future__ import annotations

import datetime as dt
import json
import time

import pytest

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.state import jload, jsave
from kurooto.mind.senses import phone as senses
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)
from tests.unit.test_phone_chat import body


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["subjects", "deadlines", "reminders", "study", "startby", "learning", "skills"])
    a.settings.set("availability.night.enabled", False)
    a.settings.set("subjects.list", [{"slug": "topology", "name": "Topology"}])
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)) or "m1")
    yield a
    mind.forget_client(a)
    a.close()


def add(app, title, hours, **kw):
    dl = app.modules["deadlines"]
    dl.add(title, now() + dt.timedelta(hours=hours), **kw)
    return next(i for i, it in dl.items().items() if it["title"] == title)


# ------------------------------------------------------------------------------------ L60 the phone's place names
def test_a_place_you_name_is_matched_to_one_saved_on_the_phone():
    from kurooto.modules.reminders import saved_place

    names = ["Library", "Chemistry lab", "Gym", "Physics lab"]
    assert saved_place("the library", names) == "Library"
    assert saved_place("lib", names) == "Library"
    assert saved_place("chem lab", names) == "Chemistry lab"
    assert saved_place("libary", names) == "Library"  # a slip of the keys
    assert saved_place("lab", names) is None  # two labs: your words go as they are
    assert saved_place("cafe", names) is None
    assert saved_place("", names) is None


def test_the_names_come_only_while_asked_for_and_match_the_reminder(phone, monkeypatch):
    app, pc = phone.app, phone.calls.chat
    f = app.paths.state / "calls" / "place-names.json"
    code, out = pc.take(body(app, "a" * 16, op="place_names", args={"names": ["Library", "Gym"]}))
    assert out["ok"] is False and not f.exists()  # reminders.place_names is off by default
    assert phone.calls.sessions.message()["switches"]["place_names"] is False
    app.settings.set("reminders.places", True)
    app.settings.set("reminders.place_names", True)
    assert phone.calls.sessions.message()["switches"]["place_names"] is True
    assert pc.take(body(app, "b" * 16, sealed=False, op="place_names", args={"names": ["X"]}))[0] == 403
    code, out = pc.take(body(app, "c" * 16, op="place_names", args={"names": ["Library", "library", "Gym", 3]}))
    assert out["ok"] and jload(f, {})["names"] == ["Library", "Gym"]
    assert [e for e in app.events.tail(20) if e["kind"] == "phone_place_names"][-1]["n"] == 2  # a count, no names
    env_on = app.modules["reminders"]
    sent = []
    monkeypatch.setattr(phone.calls.phone, "send", lambda m: sent.append(m) or True)
    monkeypatch.setattr(phone.calls, "ready", lambda: (True, ""))
    said = env_on.at_place("the lib", "return the book")
    assert sent[-1].title == "Library" and "(saved there)" in said
    env_on.at_place("cafe", "buy milk")
    assert sent[-1].title == "cafe"  # no match: as before
    app.settings.set("reminders.place_names", False)
    env_on.at_place("lib", "x")
    assert sent[-1].title == "lib" and not f.exists()  # off: the names are gone too


# ---------------------------------------------------------------------------------- L114 place events for add-ons
def test_a_fresh_place_event_reaches_an_add_on_without_its_label_in_the_log(app, monkeypatch):
    from kurooto.modules.base import Module

    got = []

    class Addon(Module):
        id = "someaddon"
        title = "An add-on"

        def place_event(self, label, event, when):
            got.append((label, event, when.date()))

    app.modules["someaddon"] = Addon(app)
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "someaddon"])
    t = now().timestamp()
    senses.place_hooks(app, "leave", "Library", t)
    assert got == [("Library", "leave", now().date())]
    ev = [e for e in app.events.tail(20) if e["kind"] == "phone_place"][-1]
    assert ev["event"] == "leave" and "Library" not in json.dumps(ev)
    app.settings.set("mind.senses.places_to_addons", False)
    senses.place_hooks(app, "arrive", "Library", t)
    assert len(got) == 1


# ------------------------------------------------------------------------------ L119 the hours you usually work
def test_the_hours_you_usually_work_on_a_subject_lead_the_plan_only_when_on(app, monkeypatch):
    from kurooto.modules.base import Module
    from kurooto.modules.startby import allocate

    class Habit(Module):
        id = "habit"
        title = "An add-on"

        def work_hours(self, subject, title):
            return {22: 0.9, 23: 1.5, "x": 1, 25: 1, 9: True} if subject == "topology" else {}

    app.modules["habit"] = Habit(app)
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "habit"])
    sb = app.modules["startby"]
    assert sb.habit_hours("topology") == {}  # startby.learn_from_model is off by default
    app.settings.set("startby.learn_from_model", True)
    assert sb.habit_hours("topology") == {22: 0.9, 23: 1.0}  # nonsense dropped, clipped to 0-1
    day = dt.datetime(2030, 1, 7)
    slots = [(day.replace(hour=9), day.replace(hour=23, minute=59))]
    item = [{"id": "a", "due": day + dt.timedelta(days=1), "hours": 1}]
    plain = allocate(item, slots, 1.0)
    assert plain["a"][0].hour == 22 and plain["a"][0].minute == 59  # as late as possible
    pieces: dict = {}
    allocate(item, slots, 1.0, pieces, habits={"a": {9: 1.0}})
    assert pieces["a"][0][0].hour == 9  # the hour you usually work on it, first


def test_the_study_push_offers_your_usual_hour(app, monkeypatch):
    from kurooto.mind import study_push

    sb = app.modules["startby"]
    t = dt.datetime(2030, 1, 7, 8, 0)
    monkeypatch.setattr(sb, "slots", lambda a, b: [(t.replace(hour=9), t.replace(hour=21))])
    assert study_push.slot(app, 25, t).hour == 9  # the first free stretch
    monkeypatch.setattr(sb, "habit_hours", lambda s, ti="": {19: 1.0} if s == "topology" else {})
    assert study_push.slot(app, 25, t, subject="topology").hour == 19
    assert study_push.slot(app, 25, t, subject="other").hour == 9


# ------------------------------------------------------------------------------ L144 what a kind really took
def test_what_the_last_problem_sets_took_is_offered_as_a_size(app, monkeypatch):
    sb, dl = app.modules["startby"], app.modules["deadlines"]
    for k, (title, hrs) in enumerate((("Topology problem set 1", 5), ("Topology problem set 2", 6))):
        j = add(app, title, 24 * (1 + k), subject="topology")
        items = dl.items()
        due = now() - dt.timedelta(days=20 - 7 * k)
        items[j].update(status="done", due=due.isoformat(), done_at=(due - dt.timedelta(hours=2)).isoformat())
        jsave(dl.file, items)
        app.events.emit("study_session_end", subject="topology", minutes=hrs * 60, deadline=j)
    assert sb.learned_h("topology", "problem_set") == (5.5, 2)
    i = add(app, "Topology problem set 3", 24 * 6, subject="topology")
    r = next(r for r in sb.plan() if r["id"] == i)
    assert r["hours"] == 3  # the guess; unchanged until the tap
    sb._tell(r)  # noqa: SLF001
    text, kw = app.sent[-1]
    assert "Your last 2 problem sets in Topology took about 5.5 h of study each." in text
    assert kw["buttons"][0] == [("Use 5.5 h", f"sby:{i}:5.5")]
    app.settings.set("startby.learned_line", False)
    sb._tell(r)  # noqa: SLF001
    assert "took about" not in app.sent[-1][0]
    app.settings.set("startby.learned_estimates", True)  # off by default: the guess replaced by itself
    sb._learned_memo = {}  # noqa: SLF001
    assert next(r for r in sb.plan() if r["id"] == i)["hours"] == 5.5


# ---------------------------------------------------------------------------------- L45 open threads with a due
def test_the_greeting_says_a_thread_due_today_last_and_never_with_others():
    from kurooto.modules.face import greet as gr
    from tests.unit.test_face import ITEMS, NOW

    due = NOW.replace(hour=18, minute=0)
    th = [("send the draft to Mira", due), ("book the room", due)]
    t, p = gr.compose(["next", "threads"], ITEMS, (0, 0), None, 0, False, NOW, threads=th)
    assert p[-1] == "threads" and "You said you'd send the draft to Mira (by 18:00). One more is due today too." in t
    assert gr.compose(["next"], ITEMS, (0, 0), None, 0, False, NOW, threads=th)[1] == ["next"]  # not asked for
    full = gr.compose(["next", "threads"], ITEMS, (0, 0), None, 0, True, NOW, with_others="full", threads=th)
    assert "threads" not in full[1]  # someone else in view: never, even with full
    long = [("x" * 80, due)]
    args = (["next", "waiting", "deadline", "held", "threads"], ITEMS, (2, 1), ("y" * 50, NOW), 3, False, NOW)
    t2, p2 = gr.compose(*args, threads=long)
    assert "threads" not in p2 and "next" in p2  # at the length limit it goes first


def test_a_thread_due_today_gets_a_block_in_free_time(env, monkeypatch):
    from kurooto.core import threads

    app = env.app
    plan = app.modules["agent_plan"]
    t = now().replace(hour=13, minute=5, second=0, microsecond=0)
    row = {"id": 7, "text": "send the draft to Mira", "due_dt": t.replace(hour=18)}
    monkeypatch.setattr(threads, "due_by", lambda a, edge, n=3: [row])
    monkeypatch.setattr(plan, "plan_ready", lambda: True)
    lab = {"start": t.replace(hour=13, minute=15), "end": t.replace(hour=14), "title": "Lab", "id": "e"}
    monkeypatch.setattr(plan, "plan_blocks", lambda day: [lab])
    monkeypatch.setattr(plan, "_busy_else", lambda a, b: [(t.replace(hour=14), t.replace(hour=15, minute=10))])
    planned, sent = [], []
    monkeypatch.setattr(plan, "plan_block", lambda s, e, title, **kw: planned.append((s, e, title)) or "Planned.")
    monkeypatch.setattr(app, "notify", lambda text, **kw: sent.append((text, kw)))
    assert plan.thread_slots(t) == 0  # agent_plan.thread_slot is off by default
    app.settings.set("agent_plan.thread_slot", True)
    assert plan.thread_slots(t) == 1
    s, e, title = planned[0]
    assert (s.hour, s.minute, (e - s).seconds // 60, title) == (15, 15, 30, "send the draft to Mira")
    assert sent[0][1]["buttons"] == [[("Remove", "apl:thread:1515")]] and sent[0][1]["why"] == "agent_plan.thread_slot"
    assert plan.thread_slots(t) == 0  # once a day


# ------------------------------------------------------------------------------------ L11 bedside's consumers
def test_bedside_mode_moves_the_night_only_with_its_switch(phone, monkeypatch):
    from kurooto.mind import sleep

    app, pc = phone.app, phone.calls.chat
    pc.take(body(app, "a" * 16, op="bedside", args={"on": True}))
    assert "bedside" not in (sleep._load(app).get("external") or {})  # noqa: SLF001 (off: nothing noted)
    app.settings.set("mind.sleep.follow_bedside", True)
    pc.take(body(app, "b" * 16, op="bedside", args={"on": True}))
    st = sleep._load(app)  # noqa: SLF001
    assert st["external"]["bedside"]["asleep"] is True
    assert sleep._external_since(app, st) == st["external"]["bedside"]["since"]  # noqa: SLF001
    app.settings.set("mind.sleep.follow_bedside", False)
    assert sleep._external_since(app, st) is None  # noqa: SLF001 (follow_external alone doesn't take bedside's)
    app.settings.set("mind.sleep.follow_bedside", True)
    pc.take(body(app, "c" * 16, op="bedside", args={"on": False}))
    assert sleep._load(app)["external"]["bedside"]["asleep"] is False  # noqa: SLF001


def test_the_evening_bundle_waits_for_bedside_mode_to_close(phone, monkeypatch):
    app, pc = phone.app, phone.calls.chat
    calm = app.calm
    bundled = []
    monkeypatch.setattr(calm, "bundle", lambda: bundled.append(1) or 1)
    monkeypatch.setattr(calm, "monthly", lambda: 0)
    monkeypatch.setattr(calm, "evening_at", lambda day=None: dt.datetime.combine(day or now().date(), dt.time(0)))
    pc.take(body(app, "a" * 16, op="bedside", args={"on": True}))
    app.settings.set("notify.calm.night_bedside", True)
    calm.tick()
    assert bundled == []  # in bed: it waits
    pc.take(body(app, "b" * 16, op="bedside", args={"on": False}))  # closing it lets it out
    assert bundled == [1]
    calm.tick()
    assert bundled == [1]  # once
    st = jload(calm.state_file, {})
    assert "bundle_held" not in st and st["bundle_day"] == now().date().isoformat()


# -------------------------------------------------------------------------------------------- L22 the break bid
def test_a_long_stretch_at_the_desk_bids_for_a_break_once(env, monkeypatch):
    app = env.app
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "face"])  # no camera set up
    face = app.modules["face"]
    t = now().replace(second=0, microsecond=0)
    spans = [(t - dt.timedelta(minutes=100), t)]
    monkeypatch.setattr(face, "desk_spans", lambda lo, hi: spans)
    sent = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: sent.append((text, kw)))
    assert face.desk_break(t) is False  # face.desk_break is off by default
    app.settings.set("face.desk_break", True)
    assert face.desk_break(t) is True
    assert sent[0][0] == "1 h 40 at the desk without a break. A few minutes up and away?"
    assert sent[0][1]["why"] == "face.desk_break"
    assert face.desk_break(t) is False  # once a stretch
    spans[:] = [(t - dt.timedelta(minutes=60), t)]
    assert face.desk_break(t) is False  # a new stretch, not long enough yet
    spans[:] = [(t - dt.timedelta(minutes=200), t - dt.timedelta(minutes=10))]
    assert face.desk_break(t) is False  # not at the desk now


# --------------------------------------------------------------------------------- L94 one read of the chat
def test_the_nightly_readers_share_one_read_and_say_the_same(app):
    from kurooto.core import infer, nightread

    f = app.paths.state / "chat" / "history.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    t = time.time()
    jsave(f, [{"at": t - 50, "user": "I'll send the draft tonight", "assistant": "ok"}, {"at": t - 10, "user": ""},
              "junk", {"at": t - 5, "user": "Organic Chemistry quiz on Friday"}])  # fmt: skip
    before = dict(nightread.reads)
    a = infer.recent_text(app, t - 100)
    b = nightread.said_since(app, t - 100)
    assert [x for x in a if x[0] == "chat"] == [("chat", "I'll send the draft tonight"),
                                               ("chat", "Organic Chemistry quiz on Friday")]  # fmt: skip
    assert [w for _at, w in b] == ["I'll send the draft tonight", "Organic Chemistry quiz on Friday"]
    assert nightread.reads["parsed"] == before["parsed"] + 1 and nightread.reads["shared"] >= before["shared"] + 1
    app.settings.set("memory.night_read", False)
    assert [w for _at, w in nightread.said_since(app, t - 100)] == [w for _at, w in b]  # off: the same, read again


# --------------------------------------------------------------------------- L128 learned skills, tested and counted
def _learned(app, name="tidy-notes"):
    from kurooto.core.tools import write_note_file
    from kurooto.modules.skills import user_dir

    lm = app.modules["learning"]
    f = user_dir(app) / name / "SKILL.md"
    write_note_file(f, f"---\nname: {name}\ndescription: tidy a note\nlearned: true\n---\nSteps.\n", create=True)
    lm._tested_new(name, {"title": "Tidy my Organic Chemistry note"})  # noqa: SLF001
    return lm, f


def test_a_learned_skill_keeps_two_cases_and_counts_its_uses(app):
    lm, _f = _learned(app)
    r = lm.tested()["tidy-notes"]
    assert len(r["cases"]) == 2 and r["uses"] == 0
    lm._tested_use("tidy-notes", "j1", "Tidied the note.")  # noqa: SLF001
    lm._tested_use("tidy-notes", "j2", "I couldn't find the note.")  # noqa: SLF001 (gave up: wrong)
    lm._tested_use("tidy-notes", "j2", "again")  # noqa: SLF001 (the same answer twice: counted once)
    lm._tested_wrong("tidy-notes", "j1")  # noqa: SLF001 (you corrected it)
    r = lm.tested()["tidy-notes"]
    assert (r["uses"], r["ok"], r["fail"]) == (2, 0, 2)
    assert lm.failing() == []  # fewer than three uses: not shown yet
    lm._tested_use("tidy-notes", "j3", "I can't.")  # noqa: SLF001
    assert [x["name"] for x in lm.failing()] == ["tidy-notes"]
    assert any("/tidy-notes: used 3, 0 fine, 3 wrong" in ln for ln in lm.tested_lines())
    app.settings.set("learning.skills_tested", False)
    assert lm.failing() == [] and lm.tested_lines() == []


def test_a_skill_going_wrong_is_offered_for_retiring_never_retired_by_itself(app):
    lm, f = _learned(app)
    for k in range(3):
        lm._tested_use("tidy-notes", f"j{k}", "I couldn't do it.")  # noqa: SLF001
    assert lm.tell_failing() == 1 and lm.tell_failing() == 0  # once
    text, kw = app.sent[-1]
    assert kw["buttons"] == [[("Retire", "lrn:tidy-notes:retire")]] and kw["why"] == "learning.skill_failing"
    assert f.exists()  # nothing happened by itself
    assert app.callback("lrn:tidy-notes:retire") == "Retired /tidy-notes."
    assert not f.exists()
    cid = app.sent[-1][1]["buttons"][0][0][1].split(":")[1]
    assert lm.undo(cid) == "/tidy-notes is back." and f.exists() and "learned: true" in f.read_text()


def test_a_skill_you_wrote_is_never_retired(app):
    from kurooto.core.tools import write_note_file
    from kurooto.modules.skills import user_dir

    lm = app.modules["learning"]
    f = user_dir(app) / "mine" / "SKILL.md"
    write_note_file(f, "---\nname: mine\ndescription: my own\n---\nSteps.\n", create=True)
    lm._tested_new("mine", {})  # noqa: SLF001
    assert "isn't one it learned" in lm.retire_skill("mine") and f.exists()


# ------------------------------------------------------------------------------- L81 quiet feedback buttons
def test_feedback_buttons_are_marked_quiet_for_the_app(phone):
    pc = phone.calls.chat
    m = pc.say("Done.", buttons=[[("Open", "x:1:open"), ("Wrong", "wrong:ab12:x")], [("Why?", "calm:r1:why"),
                                 ("Less of this", "calm:r1:less")]])  # fmt: skip
    shown = pc.public(m)["buttons"]
    assert [b.get("quiet", False) for b in shown] == [False, True, True, True]


# ------------------------------------------------------------------------------------- L87 the phone's other calls
def test_the_phone_is_asked_for_its_other_calls_only_when_something_uses_them(phone):
    app = phone.app
    assert phone.calls.sessions.message()["switches"]["phone_busy"] is False
    app.settings.set("voice.listen.phone_call", True)
    assert phone.calls.sessions.message()["switches"]["phone_busy"] is True
