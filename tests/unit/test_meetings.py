"""Any recurring meeting (core/meetings.py): "With: X (their role in your word)" and "Meets:" in Kurooto's block of the
project note; the evening-before brief for a weekly meeting with anyone; notes after the meeting become minutes through
your AI (a fake answer here); action items come back as buttons and become deadlines only on a tap."""

import datetime as dt
import json

from kurooto.core import infer, meetings
from kurooto.modules import research
from kurooto.modules.base import Incoming
from kurooto.providers.base import Result, Verdict
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MINUTES = """Summary:
- Went through the forcing sweep; the drift at high forcing is real
- Agreed the spin-up is long enough
Decisions:
- Drop the 2-layer runs
Action items:
- Send the sweep plots to Dr Okafor (by {due})
- Read the Brevik paper on drift
"""
NODATE = MINUTES.replace(" (by {due})", "")


def setup(env, chat=False):
    env.app.settings.set("availability.night.enabled", False)
    env.on("deadlines")
    if chat:  # minutes are written by your AI
        env.app.settings.set("brain.main", "gemini")
        env.app.secrets.set("gemini.api_key", "k")
        env.on("chat")
    return env.app


def said(app, text, voice=False):
    out = []
    app.handle(
        Incoming(
            text, via="telegram", message_id=77, voice=voice, respond=lambda t, buttons=None: out.append((t, buttons))
        )
    )
    return out


def okafor(app, ago_h=1.0):
    """A project with Dr Okafor and a meeting with him that started ago_h hours ago."""
    infer.observe(app, "I've started a project on glacier drift with Dr Sam Okafor.")
    note = research.project_note(app, "Glacier drift")
    start = dt.datetime.now().replace(second=0, microsecond=0) - dt.timedelta(hours=ago_h)
    app.modules["deadlines"].add("Meeting: Dr Sam Okafor", start)
    return note, start


def test_a_weekly_meeting_with_a_manager_gets_its_note_and_the_brief_the_evening_before(env):
    app = setup(env)
    tomorrow = dt.date.today() + dt.timedelta(days=1)
    told = infer.observe(
        app, f"I meet my manager Mira Castell every {DAYS[tomorrow.weekday()]} at 10 about onboarding."
    )
    assert told and "You meet Mira Castell every" in told[0]
    note = research.project_note(app, "Onboarding")
    text = note.read_text()
    body = meetings.block_body(text, meetings.BLOCK)
    assert body == f"With: Mira Castell (manager)\nMeets: every {DAYS[tomorrow.weekday()][:3]} 10:00"
    assert "## Meetings" in text and infer.projects_with(app) == [(note, "Mira Castell", "manager")]
    # said again: nothing twice; someone unknown with no role or title: nothing
    assert infer.observe(app, "I have a weekly call with Jun on Fridays at 5.") == []
    (brief,) = app.modules["deadlines"].meeting_briefs()
    assert brief.startswith("Tomorrow at 10:00: meeting with Mira Castell (Onboarding).")
    assert app.modules["deadlines"].meeting_briefs() == []  # once
    item = infer._load(app)["items"][-1]
    assert infer.undo(app, item["id"]).startswith("Undone: You meet Mira Castell")
    assert not note.exists()  # it made the note, which hadn't changed since


def test_a_weekly_meeting_with_a_project_person_keeps_your_lines_and_changes_only_its_block(env):
    app = setup(env)
    note = research.project_note(app, "Glacier drift")
    research.ensure_project(app, "Glacier drift")
    mine = "With: Dr Sam Okafor (supervisor)\nLast met: 2026-01-05\n"  # a note from before 0.5.20: your lines
    text = note.read_text().replace("# Glacier drift\n", "# Glacier drift\n\n" + mine, 1)
    text += "\n## Next steps\n- [ ] my own step\n"
    note.write_text(text)
    told = infer.observe(app, "We meet my guide Dr Okafor every Tuesday at 4.")
    assert told and "every Tue 16:00" in told[0]
    after = note.read_text()
    assert mine in after and "- [ ] my own step" in after  # yours, as it was
    assert meetings.block_body(after, meetings.BLOCK) == "Meets: every Tue 16:00"  # the role stays yours
    told = infer.observe(app, "Met Okafor today, we fixed the drift.")
    after = note.read_text()
    assert mine in after and f"Last met: {dt.date.today():%Y-%m-%d}" in meetings.block_body(after, meetings.BLOCK)
    assert meetings.last_met(after) == f"{dt.date.today():%Y-%m-%d}"


def test_notes_after_the_meeting_become_minutes_and_action_items_are_deadlines_only_on_a_tap(env):
    app = setup(env, chat=True)
    note, start = okafor(app)
    out = said(
        app, "Okafor liked the sweep, drift is real, drop the two layer runs, send him plots, read Brevik.", True
    )
    assert out and out[0][0].startswith("Taking this as your notes from the meeting with Dr Sam Okafor")
    assert out[0][1] == [[("Not about the meeting", out[0][1][0][0][1])]]
    oid = out[0][1][0][0][1].split(":")[1]
    job = app.jobs.recent(1)[0]
    assert job.title == "Minutes: meeting with Dr Sam Okafor" and "drop the two layer runs" in job.prompt
    payload = json.loads(app.jobs._db.execute("select then_payload from jobs where id=?", (job.id,)).fetchone()[0])
    due = dt.date.today() + dt.timedelta(days=3)
    n = len(env.fake.sent)
    app.jobs.then_actions["meetings.minutes"](job, Result(Verdict.OK, MINUTES.format(due=due)), payload)
    text = note.read_text()
    day = f"{start:%Y-%m-%d}"
    minutes = meetings.block_body(text, f"minutes-{day}")
    assert minutes.startswith(f"**Minutes, {start:%a %d %b %Y}, with Dr Sam Okafor**")
    assert "- Went through the forcing sweep" in minutes and "Decisions:\n- Drop the 2-layer runs" in minutes
    assert text.index(f"kurooto:minutes-{day}") > text.index("## Meetings")  # under the Meetings heading
    steps = meetings.block_body(text, meetings.STEPS)
    assert steps == "- [ ] Send the sweep plots to Dr Okafor\n- [ ] Read the Brevik paper on drift"
    assert text.index("## Next steps") < text.index(meetings.STEPS)
    assert f"Last met: {day}" in meetings.block_body(text, meetings.BLOCK)
    offer = [p for m, p in env.fake.sent[n:] if m == "sendMessage"][-1]
    assert "Minutes from the meeting with Dr Sam Okafor are in" in offer["text"]
    assert "1. Send the sweep plots to Dr Okafor (due" in offer["text"]
    labels = [b["text"] for row in json.loads(json.dumps(offer["reply_markup"]))["inline_keyboard"] for b in row]
    assert labels == ["Add 1: Send the sweep plots to Dr…", "Add 2: Read the Brevik paper on…", "None", "Later"]
    dl = app.modules["deadlines"]
    assert not any(d["title"].startswith("Send the sweep") for d in dl.items().values())  # never without the tap
    assert env.press(f"mtg:{oid}:a0").startswith("Added: Send the sweep plots to Dr Okafor, due")
    (it,) = [d for d in dl.items().values() if d["title"] == "Send the sweep plots to Dr Okafor"]
    assert it["due"].startswith(f"{due:%Y-%m-%d}T17:00")  # the date said in the meeting
    assert env.press(f"mtg:{oid}:a0") == "On your deadlines already."
    assert env.press(f"mtg:{oid}:none").startswith("No deadlines from them")
    assert env.press(f"mtg:{oid}:a1") == "That's dealt with already."
    assert not any(d["title"].startswith("Read the Brevik") for d in dl.items().values())


def test_later_brings_the_action_items_back_the_next_evening(env):
    app = setup(env, chat=True)
    note, start = okafor(app)
    out = said(app, "notes about the meeting with Okafor: he wants the plots and a reading of Brevik.")
    oid = out[0][1][0][0][1].split(":")[1]
    job = app.jobs.recent(1)[0]
    app.jobs.then_actions["meetings.minutes"](job, Result(Verdict.OK, NODATE), {"id": oid})
    assert env.press(f"mtg:{oid}:later") == "They'll come back tomorrow evening."
    assert meetings.offers_due(app) == 0  # not yet
    data = meetings._load(app)
    data["minutes"][oid]["later"] = dt.date.today().isoformat()
    meetings._save(app, data)
    assert meetings.offers_due(app) == 1
    assert "From the meeting with Dr Sam Okafor" in env.fake.texts()[-1] and "Add 1" in str(env.fake.sent[-1])
    # without a date said, an action item is due at the next meeting (none here: a week on)
    rec = meetings._load(app)["minutes"][oid]
    assert rec["items"][1]["due"].startswith(f"{dt.date.today() + dt.timedelta(days=7):%Y-%m-%d}T17:00")


def test_not_about_the_meeting_takes_the_minutes_out_and_asks_the_ai_as_usual(env):
    app = setup(env, chat=True)
    note, _start = okafor(app)
    before = note.read_text()
    # a short typed message just after the meeting goes on as usual
    said(app, "what's the weather like")
    assert not meetings._load(app)["minutes"]
    out = said(
        app,
        "So the plan for the weekend is long: groceries, the laundry, a call home, and then the novel I started.",
    )
    oid = out[0][1][0][0][1].split(":")[1]
    job = app.jobs.recent(1)[0]
    app.jobs.then_actions["meetings.minutes"](job, Result(Verdict.OK, NODATE), {"id": oid})
    assert note.read_text() != before
    assert env.press(f"mtg:{oid}:not") == "Left out of the meeting notes; your AI has it as a plain message."
    after = note.read_text()
    assert "kurooto:minutes" not in after and meetings.block_body(after, meetings.STEPS) is None
    assert "Last met" not in after
    assert app.jobs.recent(1)[0].prompt.startswith("So the plan for the weekend")
    assert env.press(f"mtg:{oid}:not") == "Done already."
    # tapped while the AI is still writing: the request is cancelled and the note stays as it is
    before = note.read_text()
    out = said(app, "about the meeting with Okafor: this one was meant for someone else really")
    oid = out[0][1][0][0][1].split(":")[1]
    job = app.jobs.recent(1)[0]
    assert env.press(f"mtg:{oid}:not").startswith("Left out of the meeting notes")
    assert app.jobs.get(job.id).status == "failed"
    app.jobs.then_actions["meetings.minutes"](job, Result(Verdict.OK, NODATE), {"id": oid})  # a late answer
    assert note.read_text() == before


def test_a_failed_answer_keeps_your_notes_as_you_sent_them(env):
    app = setup(env, chat=True)
    note, start = okafor(app, ago_h=0.5)
    out = said(app, "Notes from today's meeting: Okafor says the drift is real.")
    oid = out[0][1][0][0][1].split(":")[1]
    job = app.jobs.recent(1)[0]
    app.jobs.then_actions["meetings.minutes"](job, Result(Verdict.ERROR, "", detail="down"), {"id": oid})
    minutes = meetings.block_body(note.read_text(), f"minutes-{start:%Y-%m-%d}")
    assert "Your notes, as you sent them: Notes from today's meeting: Okafor says the drift is real." in minutes
    assert "couldn't write the minutes" in env.fake.texts()[-1]


def test_no_meeting_no_chat_or_long_after_nothing_is_taken(env):
    app = setup(env)
    okafor(app, ago_h=1)
    said(app, "about the meeting with Okafor: drift is real")  # chat is off: minutes need your AI
    assert not meetings._load(app)["minutes"]
    app.settings.set("brain.main", "gemini")
    app.secrets.set("gemini.api_key", "k")
    env.on("chat")
    said(app, "remind me about the meeting with Okafor tomorrow at 4")  # a request, not notes
    assert not meetings._load(app)["minutes"]
    app.settings.set("meetings.after_h", 0.5)  # the meeting was an hour ago
    said(app, "The plan for the weekend is long: groceries, the laundry, a call home, then finishing the novel too.")
    assert not meetings._load(app)["minutes"]


def test_the_brief_has_the_last_minutes_and_their_open_action_items(env):
    app = setup(env, chat=True)
    note, start = okafor(app)
    out = said(app, "about the meeting with my supervisor: plots and Brevik, drift is real.")
    oid = out[0][1][0][0][1].split(":")[1]
    job = app.jobs.recent(1)[0]
    app.jobs.then_actions["meetings.minutes"](job, Result(Verdict.OK, NODATE), {"id": oid})
    due = dt.datetime.combine(dt.date.today() + dt.timedelta(days=1), dt.time(15))
    brief = infer.brief(note, "Dr Sam Okafor", due)
    assert "Open next steps:\n- Send the sweep plots to Dr Okafor\n- Read the Brevik paper on drift" in brief
    assert f"From the minutes of {start:%Y-%m-%d}:\n- Went through the forcing sweep" in brief


def test_the_phone_apps_chat_gets_the_action_items_as_buttons_too(phone):  # noqa: F811
    from tests.unit.test_phone_chat import body

    app = setup(phone, chat=True)
    okafor(app)
    calls = phone.calls
    code, out = calls.handle_request(
        "POST", "/chat", json.dumps(body(app, "a" * 16, text="about the meeting with Okafor: plots, Brevik")).encode()
    )
    assert code == 200 and out["said"][0]["text"].startswith("Taking this as your notes")
    assert out["said"][0]["buttons"] == [{"label": "Not about the meeting"}]
    job = app.jobs.recent(1)[0]
    payload = json.loads(app.jobs._db.execute("select then_payload from jobs where id=?", (job.id,)).fetchone()[0])
    n_tg = len(phone.fake.texts())
    app.jobs.then_actions["meetings.minutes"](job, Result(Verdict.OK, NODATE), payload)
    m = [kw["msg"] for op, kw in phone.ops if op == "chat-say"][-1]
    assert m["re"] == "a" * 16 and "Action items" in m["text"] and len(phone.fake.texts()) == n_tg
    assert [b["label"] for b in m["buttons"]][-2:] == ["None", "Later"]
    code, got = calls.chat.take(body(app, "b" * 16, sealed=False, button=1, msg=m["id"]))
    assert code == 200 and got["note"].startswith("Added: Read the Brevik paper on drift")
    assert any(d["title"] == "Read the Brevik paper on drift" for d in app.modules["deadlines"].items().values())


def test_the_weekly_summary_mentions_people_only_from_the_project_notes(env):
    app = setup(env)
    env.on("weekly")
    tomorrow = dt.date.today() + dt.timedelta(days=1)
    infer.observe(app, f"I meet my manager Mira Castell every {DAYS[tomorrow.weekday()]} at 10 about onboarding.")
    note = research.project_note(app, "Onboarding")
    today = dt.date.today().isoformat()
    note.write_text(meetings.put(note.read_text(), f"minutes-{today}", "**Minutes**\n- went fine"), encoding="utf-8")
    infer.observe(app, "I've started a project on glacier drift with Dr Sam Okafor.")
    drift = research.project_note(app, "Glacier drift")
    old = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    text = meetings.set_fields(drift.read_text(), meets="every Mon 09:00", met=old)
    drift.write_text(text, encoding="utf-8")
    line = meetings.week_line(app)
    assert line.startswith("People (from your project notes): met Mira Castell (manager, Onboarding) ")
    assert "next: " in line and f"Mira Castell {tomorrow:%a} 10:00" in line.split("next: ")[1]
    assert "not met for a while: Dr Sam Okafor (last met" in line
    assert line in app.modules["weekly"].summary()
    n = len(env.fake.texts())
    app.settings.set("weekly.people", False)
    assert "People (" not in app.modules["weekly"].summary()
    assert len(env.fake.texts()) == n  # a line in the summary, never a message of its own
