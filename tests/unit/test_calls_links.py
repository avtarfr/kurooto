"""The 0.9.0 links into phone calls, desk Live and the shared context builder (providers/context.py): what every AI
request is told reaches calls too, call lessons reach every lane, the senses line, read-only agent tools on calls, and
the rest. Each new behaviour has its own switch; these tests turn each off as well."""

# ruff: noqa: F811 (the fixtures imported from test_calls are taken as arguments)
from __future__ import annotations

from kurooto.core import notinterested
from kurooto.modules import remember
from kurooto.providers import context
from tests.unit.test_calls import calls  # noqa: F401 (a pytest fixture)
from tests.unit.test_learning import ai, app, propose, retro_questions  # noqa: F401 (pytest fixtures, helpers)
from tests.unit.test_phone import phone  # noqa: F401 (a pytest fixture)
from tests.unit.test_phone_today import today  # noqa: F401 (a pytest fixture)


def profile(app, text="A maths student who likes long walks."):
    f = app.workspace / "about-me" / "profile.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"# Profile\n\n## In brief\n\n{text}\n", encoding="utf-8")


# ------------------------------------------------------------------------- L1, L5: what calls are told about you
def test_a_call_hears_who_they_are_how_to_help_and_the_not_interested_topics(calls):
    app = calls.app
    c = app.modules["calls"]
    profile(app)
    remember.keep(app, "Keep answers short")
    notinterested.add_topic(app, "drama club")
    brief = c.pending(context=True)
    about = brief["about_them"]
    assert "likes long walks" in about and "Keep answers short" in about and "drama club" in about
    assert "about_them" not in c.pending()  # the look back and turn-by-turn calls have headless_context already
    tool = next(t for t in c.tools() if t.name == "pending_items")
    assert "about_them" in tool.run({})  # the call's own tool, and so the brief the call line keeps offline
    app.settings.set("calls.context_brief", False)
    assert "about_them" not in c.pending(context=True)


def test_the_call_brief_never_carries_the_read_hint_and_skips_learned_on_calls(calls, monkeypatch):
    from kurooto import mind
    from kurooto.mind import feelings

    app = calls.app
    monkeypatch.setattr(mind, "part_on", lambda a, part: part == "feelings")
    monkeypatch.setattr(feelings, "hint", lambda a: "Keep it short and calm; they have a lot on.")
    monkeypatch.setattr(feelings, "state", lambda a: {})
    remember.add_line(app, remember.LEARNED_CALLS, "Ask when class ends before setting a reminder (2026-10-01)")
    about = context.call_context(app)
    assert feelings.RULE in about and "they have a lot on" not in about
    assert "Ask when class ends" not in about  # the call hears it as one of its lessons instead
    assert "they have a lot on" in context.headless_context(app)  # every other request as before
    assert "Ask when class ends" in context.headless_context(app)


def test_tell_ai_adds_one_line_to_every_request_and_off_leaves_it_as_it_was(env):
    app = env.app
    before = context.headless_context(app)
    notinterested.add_topic(app, "drama club")
    notinterested.add_topic(app, "chess society", "not this term")
    line = context.not_interested_part(app)
    assert "drama club; chess society" in line and "not this term" not in line
    assert line in context.headless_context(app)
    app.settings.set("notinterested.tell_ai", False)
    assert context.not_interested_part(app) == ""
    assert context.headless_context(app).replace(before.split("\n")[1], "") == before.replace(
        before.split("\n")[1], ""
    )  # the same text (the time line aside)


def test_desk_live_hears_it_in_its_setup(calls):
    app = calls.app
    c = app.modules["calls"]
    profile(app)
    from kurooto.modules.voice.live import Live

    lv = Live(app.modules["voice"])
    si = lv.setup(c, "m")["systemInstruction"]["parts"][0]["text"]
    assert "likes long walks" in si
    app.settings.set("calls.context_brief", False)
    assert "likes long walks" not in lv.setup(c, "m")["systemInstruction"]["parts"][0]["text"]


# ------------------------------------------------------------------------------- L5: the readers, each its own switch
def test_demote_moves_matching_items_last_and_tags_them_only_with_its_switch_on(env):
    app = env.app
    notinterested.add_topic(app, "drama club")
    items = ["Drama club auditions", "Linear algebra notes", "Probability sheet"]
    assert notinterested.demote(app, "research", items, str, lambda x, why: f"{x} ({why})") == items  # off
    app.settings.set("notinterested.filter.research", True)
    out = notinterested.demote(app, "research", items, str, lambda x, why: f"{x} ({why})")
    assert out[:2] == ["Linear algebra notes", "Probability sheet"]
    assert out[2] == "Drama club auditions (you said not interested in drama club)"
    assert notinterested.demote(app, "retro", items, str) == items  # every reader has its own switch


def test_research_digest_puts_a_skipped_topic_last_never_drops_it(env, monkeypatch):
    app = env.app
    notinterested.add_topic(app, "drama club")
    r = app.modules["research"]
    papers = [
        {"id": "1", "title": "Drama club as social network", "authors": ["A. Writer"], "source": "arXiv", "summary": "",
         "link": "https://example.com/1", "group": "g"},
        {"id": "2", "title": "Spectral gaps", "authors": ["B. Writer"], "source": "arXiv", "summary": "",
         "link": "https://example.com/2", "group": "g"},
    ]  # fmt: skip
    monkeypatch.setattr(r, "collect", lambda mark_seen=True: ([dict(p) for p in papers], []))
    app.settings.set("research.rank", False)
    app.settings.set("research.save_note", False)
    r.papers()
    text = env.fake.texts()[-1]
    assert text.index("Drama club") < text.index("Spectral gaps")  # as before, off
    app.settings.set("notinterested.filter.research", True)
    r.papers()
    text = env.fake.texts()[-1]
    assert text.index("Spectral gaps") < text.index("Drama club") and "(you said not interested in drama club)" in text


def test_retro_offers_an_idea_about_a_skipped_topic_last_and_tagged(app, env, ai):
    env.on("chat", "retro")
    notinterested.add_topic(app, "drama club")
    app.settings.set("notinterested.filter.retro", True)
    app.settings.set("retro.max_proposals", 5)
    propose(
        ai,
        {"type": "idea", "idea": "Remind me of drama club rehearsals", "text": "Add to ideas?"},
        {"type": "idea", "idea": "A Sunday reading list", "text": "Add this one?"},
    )
    assert app.modules["retro"].run() == 2
    qs = retro_questions(app)
    assert "Sunday reading list" in qs[0]["text"]
    assert "drama club rehearsals" in qs[1]["text"] and "(you said not interested in drama club)" in qs[1]["text"]


def test_link_cards_about_a_skipped_topic_come_after_the_others(env):
    import datetime as dt

    app = env.app
    notinterested.add_topic(app, "drama club")
    lc = app.modules["quiz"].links
    today = dt.date.today().isoformat()
    card = {"reps": 0, "history": [], "due": today}
    st = {
        "items": {
            "a": {**card, "text": "How does drama club relate to stage fright?", "a": "x/drama-club", "b": "x/fear"},
            "b": {**card, "text": "How is the rank used in the kernel?", "a": "x/rank", "b": "x/kernel"},
        }
    }
    assert lc.next_card(st)[0] == "a"
    app.settings.set("notinterested.filter.quiz_links", True)
    iid, it = lc.next_card(st)
    assert iid == "b"
    st["items"].pop("b")
    iid, it = lc.next_card(st)
    assert iid == "a" and it["not_interested"] == "you said not interested in drama club"
    assert "not_interested" not in st["items"]["a"]  # the stored card is left as it was


def test_the_reading_queue_reads_a_skipped_topic_last(env):
    app = env.app
    notinterested.add_topic(app, "drama club")
    ig = app.modules["integrate"]
    items = {
        "c:1": {"source": "classroom", "key": "c:1", "title": "Drama club handout", "date": "2026-10-02", "added": "2"},
        "c:2": {"source": "classroom", "key": "c:2", "title": "Lecture 4", "date": "2026-10-01", "added": "1"},
    }
    ig.items = lambda: items
    ig.sources = lambda: ["classroom"]
    assert [it["key"] for it in ig.queued_items()] == ["c:1", "c:2"]
    app.settings.set("notinterested.filter.integrate", True)
    assert [it["key"] for it in ig.queued_items()] == ["c:2", "c:1"]


# --------------------------------------------------------------------------- L2: call lessons reach every lane
def test_call_lessons_are_copied_into_how_to_help_me_and_kept_in_step(calls):
    from kurooto.modules.calls import review
    from kurooto.providers.base import Result, Verdict

    app = calls.app
    c = app.modules["calls"]

    def learned(*lines):
        text = "Nothing slipped through.\n```lessons\n" + "".join(f"- {x}\n" for x in lines) + "```"
        review.reviewed(c, None, Result(Verdict.OK, text), {})

    learned("When they say after class, ask when class ends before setting the reminder.")
    note = remember.help_file(app).read_text(encoding="utf-8")
    assert "## Learned on calls\n- When they say after class, ask when class ends before setting the reminder (" in note
    assert "ask when class ends" in context.headless_context(app)  # every lane hears it now
    assert review.lessons(app) == ["When they say after class, ask when class ends before setting the reminder."]
    keys = {r["section"] for r in remember.kept_lines(app)}
    assert remember.LEARNED_CALLS in keys  # the 90-day "Still true?" covers it
    learned("When they say after class, always ask when that class ends before setting any reminder.")  # replaces
    note = remember.help_file(app).read_text(encoding="utf-8")
    assert "before setting the reminder (" not in note and "before setting any reminder (" in note
    review.command(app, "forget 1")
    assert "Learned on calls\n- " not in remember.help_file(app).read_text(encoding="utf-8")
    app.settings.set("calls.lessons_everywhere", False)
    learned("Keep the morning call under two minutes.")
    assert "under two minutes" not in remember.help_file(app).read_text(encoding="utf-8")
    assert review.lessons(app) == ["Keep the morning call under two minutes."]  # the call's own list as before


# ------------------------------------------------------------------------------------- L4: the senses on a call
def test_a_call_hears_which_senses_are_on_and_when_they_were_at_the_desk(calls, monkeypatch):
    import time

    app = calls.app
    c = app.modules["calls"]
    assert c.pending(context=True)["senses"] == "Face presence is off; Voice ID is off."
    face = app.modules["face"]
    real = app.is_on
    monkeypatch.setattr(app, "is_on", lambda mid: mid == "face" or real(mid))
    monkeypatch.setattr(face, "desk_seen_at", lambda: time.time() - 600)
    line = c.senses_line()
    assert line.startswith("Face presence is on (at the desk 10 minutes ago, ") and "Voice ID is off" in line
    monkeypatch.setattr(face, "desk_seen_at", lambda: None)
    monkeypatch.setattr(face, "away_now", lambda: True)
    assert "they're away from the desk" in c.senses_line()
    app.settings.set("calls.tell_senses", False)
    assert "senses" not in c.pending(context=True)


# ------------------------------------------------------------------------- L123: read-only agent tools on calls
def test_read_only_agent_tools_are_offered_on_calls_and_never_the_writing_ones(calls, monkeypatch):
    from kurooto.modules.calls.tools import Tool

    app = calls.app
    c = app.modules["calls"]
    books = app.modules["books"]
    monkeypatch.setattr(
        books,
        "agent_tools",
        lambda: [
            Tool("read_book", "Read a book's pages.", lambda a: "pages", writes=False),
            Tool("update_exam_prep", "Write exam prep.", lambda a: "ok", writes=True),
            Tool("unknown_kind", "Not marked.", lambda a: "?"),
            Tool("guarded_read", "Guarded.", lambda a: "?", writes=False, guarded="send.out"),
        ],
    )
    real = app.enabled
    monkeypatch.setattr(app, "enabled", lambda: [*real(), books])  # Books on (it needs a book to turn on for real)
    names = {t.name for t in c.tools()}
    assert "read_book" in names
    assert not names & {"update_exam_prep", "unknown_kind", "guarded_read"}
    assert c.run_tool("read_book", {}) == "pages"
    app.settings.set("calls.read_tools", {"books": False})
    assert "read_book" not in {t.name for t in c.tools()}
    app.settings.set("calls.read_tools", {})
    app.settings.set("calls.read_agent_tools", False)
    assert "read_book" not in {t.name for t in c.tools()}


def test_a_classroom_file_is_marked_as_only_reading(env):
    tools = {t.name: t for t in env.app.modules["classroom_notes"].agent_tools()}
    assert tools["read_course_file"].writes is False and tools["update_exam_prep"].writes is None


# ------------------------------------------------------------------- L134, L84, L32: more on the phone's Today
def test_today_says_whether_the_laptop_camera_is_on_with_face_presence_on(today, monkeypatch):
    app = today.app
    assert "camera" not in today.today.snapshot()  # Face presence off: nothing
    face = app.modules["face"]
    real = app.is_on
    monkeypatch.setattr(app, "is_on", lambda mid: mid == "face" or real(mid))
    monkeypatch.setattr(face, "line", lambda: "camera on: an add-on is looking (curiosity)")
    assert today.today.snapshot()["camera"] == {"on": True, "why": "camera on: an add-on is looking (curiosity)"}
    monkeypatch.setattr(face, "line", lambda: "resting: camera off while you use the computer")
    assert today.today.snapshot()["camera"]["on"] is False
    app.settings.set("face.phone_badge", False)
    assert "camera" not in today.today.snapshot()


def test_today_counts_held_messages_and_proposals_and_send_now_releases_them(today, monkeypatch):
    app = today.app
    monkeypatch.setattr(app.calm, "held", lambda: [{"id": 1}, {"id": 2}])
    released = []
    monkeypatch.setattr(app.calm, "release", lambda cap=None: released.append(1) or 2)
    snap = today.today.snapshot()
    assert snap["waiting"]["held"] == 2 and snap["waiting"]["proposals"] == 0
    code, out = today.today.act({"do": "send_held"})
    assert code == 200 and out["note"] == "Sent 2 held messages." and released == [1]
    app.settings.set("calls.today_waiting", False)
    assert "waiting" not in today.today.snapshot()
    assert today.today.act({"do": "send_held"})[0] == 400 and released == [1]


def test_today_shows_the_plan_and_what_to_start_and_their_events_push_it(today, monkeypatch):
    from kurooto.core import actions
    from kurooto.modules.calls import today as today_mod

    real = actions.today
    monkeypatch.setattr(
        actions,
        "today",
        lambda app: {
            **real(app),
            "plan": "## Plan\n- [ ] 09:00 Problem set 3\n- Read chapter 4",
            "start": [{"title": "Essay", "when": "start today · due Fri"}],
            "study_h": 1.5,
        },
    )
    snap = today.today.snapshot()
    assert snap["plan"] == ["09:00 Problem set 3", "Read chapter 4"]
    assert snap["start"] == [{"title": "Essay", "when": "start today · due Fri"}] and snap["study_h"] == 1.5
    assert {"class_skip", "plan_rescheduled", "startby_planned", "revision_planned"} <= today_mod.CHANGES
    today.app.settings.set("calls.today_plan", False)
    assert not {"plan", "start", "study_h"} & set(today.today.snapshot())


# ------------------------------------------------------------------------- L96, L97: calls feed Brain's numbers
def test_your_call_lines_go_to_the_local_tone_tagger_and_never_kurootos(env, monkeypatch):
    from kurooto.mind import tone

    app = env.app
    lines = [
        {"who": "Kurooto", "text": "Morning."},
        {"who": "Asha", "text": "Ugh, so tired"},
        {"who": "(note)", "text": "x"},
    ]
    got = []
    monkeypatch.setattr(tone, "seen", lambda a, text: got.append(text))
    monkeypatch.setattr(tone, "tier", lambda a: "none")
    assert tone.from_call(app, lines) == 0 and got == []  # tone off (no tier): nothing
    monkeypatch.setattr(tone, "tier", lambda a: "cpu")
    assert tone.from_call(app, lines) == 1 and got == ["Ugh, so tired"]
    app.settings.set("mind.tone.calls", False)
    assert tone.from_call(app, lines) == 0


def test_a_later_on_the_alarm_call_counts_as_a_snooze_and_skips_count_in_hours(env):
    import datetime as dt

    from kurooto.core.clock import now
    from kurooto.mind import signals

    app = env.app
    day = (now() - dt.timedelta(hours=signals.DAY_STARTS)).date()
    app.events.emit("call_later", key="alarm:next")
    app.events.emit("call_later", key="alarm:next")
    app.events.emit("call_later", key="reminder:x")
    app.events.emit("call_later")  # before 0.9.0 the event had no key: not a snooze
    assert signals.collect(app, day)["snoozes"] == 2.0
    env.on("subjects")
    wd = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][day.weekday()]
    app.settings.set("subjects.list", [{"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["la"]}])
    app.settings.set("subjects.timetable", [{"day": wd, "start": "09:00", "end": "10:30", "subject": "linear-algebra"}])
    assert signals.collect(app, day)["class_skip_h"] == 0.0
    app.modules["subjects"].set_skip(["linear-algebra"], day=day)
    assert signals.collect(app, day)["class_skip_h"] == 1.5
    app.settings.set("mind.read.snoozes", False)
    app.settings.set("mind.read.skipped_classes", False)
    assert not {"snoozes", "class_skip_h"} & set(signals.collect(app, day))


def test_a_ring_reply_event_names_its_call(calls):
    c = calls.app.modules["calls"]
    c.on_event({"name": "ring_reply", "since": "nope", "action": "later"})
    ev = [e for e in calls.app.events.tail(50) if e.get("kind") == "call_later"][-1]
    assert ev["key"] == ""  # an unknown ring: still emitted, with an empty key


# ------------------------------------------------------------------------------- L27: changed since the brief
def test_a_tool_that_changes_the_day_says_so_and_marks_the_plan(calls, monkeypatch):
    from kurooto.modules import daily
    from kurooto.modules.calls.tools import Tool

    app = calls.app
    c = app.modules["calls"]
    extra = [
        Tool("move_deadline", "Move one.", lambda a: "Moved Problem set 3 to Fri 18:00."),
        Tool("remove_deadline", "Remove one.", lambda a: "I don't know that deadline."),
    ]
    real = c.tools
    monkeypatch.setattr(c, "tools", lambda: real() + extra)
    out = c.run_tool("move_deadline", {}, since="s1")
    assert out.startswith("Moved Problem set 3") and "Changed since this call's brief" in out
    assert daily.plan_stale(app) == "a deadline moved"
    assert c.run_tool("remove_deadline", {}) == "I don't know that deadline."  # nothing changed: no line
    assert daily.plan_stale(app) == "a deadline moved"
    assert len(c.tool_log["s1"][0]["result"]) <= 300


# ------------------------------------------------------------------------- L38, L39: what's said on a call counts
def test_what_you_said_on_a_call_is_read_like_a_message(calls, monkeypatch):
    from kurooto.core import infer

    app = calls.app
    c = app.modules["calls"]
    calls.on("remember")
    seen = []
    monkeypatch.setattr(infer, "observe", lambda a, text, via="chat": seen.append((text, via)) or [])
    lines = [
        {"who": "Kurooto", "text": "Hi, anything new?"},
        {"who": "You", "text": "I got a project under Prof Rao."},
        {"who": "You", "text": "Remember that I hate calls before 8."},
        {"who": "(note)", "text": "[Task finished] done"},
    ]
    assert c._after_infer(lines) == 1
    assert seen == [("I got a project under Prof Rao.\nRemember that I hate calls before 8.", "call")]
    assert "I hate calls before 8 (" in remember.help_file(app).read_text(encoding="utf-8")
    assert "From your call, noted in" in calls.fake.texts()[-1]
    assert c._after_infer(lines) == 0  # kept already: nothing said twice
    app.settings.set("calls.after_infer", False)
    seen.clear()
    assert c._after_infer(lines) == 0 and seen == []


def test_a_call_can_close_an_open_thread_while_it_is_on(calls):
    from kurooto.core import threads

    app = calls.app
    c = app.modules["calls"]
    app.settings.set("memory.threads", True)
    threads.add(app, "send the lab report draft to the group", via="chat")
    names = {t.name for t in c.tools()}
    assert "close_thread" in names
    assert c.run_tool("close_thread", {"what": "the poster"}).startswith("No open thread matches")
    out = c.run_tool("close_thread", {"what": "I sent the lab report draft"})
    assert out.startswith('Closed: "send the lab report draft') and threads.open_threads(app) == []
    app.settings.set("calls.threads_live", False)
    assert "close_thread" not in {t.name for t in c.tools()}


# ---------------------------------------------------------------------------- L46: a call placed while moving
def test_a_self_placed_call_while_moving_uses_the_phones_speech_only_when_switched_on(calls, monkeypatch):
    from kurooto.mind import gate
    from kurooto.mind.senses import phone as phone_sense

    app = calls.app
    c = app.modules["calls"]
    voices = []
    monkeypatch.setattr(c.connector, "admin_later", lambda op, then=None, **kw: voices.append(kw["voice"]) or True)
    monkeypatch.setattr(app.calm, "call_ok", lambda *a, **k: True)
    monkeypatch.setattr(gate, "check_call", lambda *a, **k: "ring")
    monkeypatch.setattr(c, "busy_with", lambda key="": "")
    monkeypatch.setattr(phone_sense, "moving", lambda a, now=None: "walking")
    c.ring("Evening check-in", key="checkins:evening", why="checkins.call")
    assert voices[-1] != "phone"  # off by default: as before
    app.settings.set("calls.mode_when_moving", True)
    c.ring("Evening check-in again", key="checkins:evening", why="checkins.call")
    assert voices[-1] == "phone"
    c.ring("You asked me to call", why="calls.own")  # a call you asked for: untouched
    assert voices[-1] != "phone"
    c.ring("Wake up", alarm=True, key="alarm:next")  # the alarm: untouched
    assert voices[-1] != "phone"
    monkeypatch.setattr(phone_sense, "moving", lambda a, now=None: "")
    c.ring("Evening check-in, still", key="checkins:evening", why="checkins.call")
    assert voices[-1] != "phone"


def test_moving_reads_only_a_fresh_motion_bin_with_the_sense_on(env, monkeypatch):
    import time

    from kurooto.mind.senses import phone as phone_sense
    from kurooto.mind.senses import store

    app = env.app
    monkeypatch.setattr(phone_sense, "enabled", lambda a, s: s == "motion")
    t = time.time()
    store.add(app, "phone:motion", "state", "walking", 5, t=t - 1200)
    assert phone_sense.moving(app, now=t) == ""  # 20 minutes old: stale
    store.add(app, "phone:motion", "state", "vehicle", 5, t=t - 60)
    assert phone_sense.moving(app, now=t) == "vehicle"
    store.add(app, "phone:motion", "state", "still", 5, t=t - 10)
    assert phone_sense.moving(app, now=t) == ""
