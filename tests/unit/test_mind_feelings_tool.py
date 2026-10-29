"""0.9.3: brain_feelings (mind.tools.feelings), Kurooto's own feeling in words with what it's about, why and what it
does about it; never its read of you (I-11, I-14). And the fix with it: a reminder or deadline that does what a promise
to remind said closes the promise and rechecks the feeling then, not on the next timer."""

import asyncio
import re

import pytest

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.state import jsave
from kurooto.mind import feelings, promises

EVERY_DAY = {"days": [0, 1, 2, 3, 4, 5, 6], "at": "19:00"}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind", "reminders"])
    monkeypatch.setattr(a, "notify", lambda text, **kw: "m1")
    yield a
    mind.forget_client(a)
    a.close()


def uneasy_about_a_promise(app, monkeypatch):
    """The desk's case: a call promised a daily reminder it hadn't set; uneasy about it, its mood low."""
    promises.seen(app, "I'll remind you to book the lab slot tomorrow.", "said.call")
    row = promises._state(app)["rows"][-1]
    t = now().timestamp()
    jsave(
        app.paths.state / feelings.FILE,
        {
            "label": "uneasy", "object": "promise_slack", "item": row["act"], "valence": -0.4321, "arousal": 0.6234,
            "at": t, "recheck_at": t + 3 * 3600, "program": feelings.PROGRAMS["uneasy"],
            "concerns": [
                {"kind": "deadline", "item": "Organic Chemistry: Quiz", "risk": 0.694, "concern": 0.694,
                 "why": "due in 22 hours"},
                {"kind": "body", "item": "my own machine", "risk": 0.4, "concern": 0.24, "why": "running hot"},
                {"kind": "news", "item": "the papers you follow", "risk": 0.5, "concern": 0.2,
                 "why": "its last check failed"},
                {"kind": "notes", "item": "your notes", "risk": 0.0, "concern": 0.0, "why": "fine"},
            ],
        },
    )  # fmt: skip
    monkeypatch.setattr(feelings, "mood_band", lambda a: "low")
    monkeypatch.setattr(feelings, "mood_why", lambda a, days=7: "3 things went worse than I expected this week")
    # the read's tone hint exists, and must never reach the tool
    monkeypatch.setattr(feelings, "hint", lambda a: "Keep it short and calm; they have a lot on.")
    return row


def tool(app):
    return next((t for t in app.modules["mind"].call_tools() if t.name == "brain_feelings"), None)


def test_it_says_its_feeling_what_about_why_and_what_it_does(app, monkeypatch):
    uneasy_about_a_promise(app, monkeypatch)
    t = tool(app)
    assert t is not None and t.writes is False and "brain_feelings" in t.hint and "how are you" in t.hint
    said = t.run({})
    assert "My own running mood is low: 3 things went worse than I expected this week." in said
    assert "I feel uneasy about something I said I'd do: remind you to book the lab slot" in said
    assert '"I\'ll remind you to book the lab slot tomorrow" on a call' in said and "it's due tomorrow" in said
    assert "It isn't done yet: no reminder for it is set." in said
    assert "recheck it every 3 hours" in said and "never makes me message you more" in said
    assert "Organic Chemistry: Quiz (due in 22 hours)" in said and "my own machine (running hot)" in said
    assert "the papers you follow (its last check failed)" in said and "your notes" not in said  # nothing at risk
    # words only: no valence, arousal, risk or concern numbers, and nothing of the read
    for bad in ("0.43", "0.62", "0.69", "0.24", "%", "valence", "arousal", "a lot on", "tone", "you seem", "forecast"):
        assert bad not in said, bad
    numbers = re.findall(r"\d+", re.sub(r"\b\d\d:\d\d\b", "", said))
    assert set(numbers) <= {"3", "22"}, numbers  # "every 3 hours", "due in 22 hours", "3 things": and times


def test_once_the_reminder_exists_the_promise_closes_and_the_feeling_is_rechecked(app, monkeypatch):
    row = uneasy_about_a_promise(app, monkeypatch)
    app.scheduler.at(
        now().timestamp() + 3600, "reminders.fire", {"what": "Book the lab slot", "repeat": EVERY_DAY},
        key="reminders:r1", module="reminders",
    )  # fmt: skip
    said = tool(app).run({})  # in hand already, before any recheck
    assert 'It\'s in hand now: a reminder "Book the lab slot" exists, repeating every day' in said
    ticked = []

    def tick(a, p=None):  # as the real one: no promise open now, so no item (the drive still lags: still uneasy)
        st = {**feelings.state(a), "item": feelings.item_of(a, "promise_slack")}
        jsave(a.paths.state / feelings.FILE, st)
        return ticked.append(1) or st

    monkeypatch.setattr(feelings, "tick", tick)
    from kurooto.mind import measure

    monkeypatch.setattr(measure, "run", lambda a, p=None: True)
    assert feelings.recheck(app, "reminder_set") is not None and ticked == [1]
    r = next(x for x in promises._state(app)["rows"] if x["id"] == row["id"])
    assert r["state"] == "kept" and r["kept_by"] == "item"
    kept = app.events.tail(5, {"promise_kept"})
    assert kept and kept[-1]["by_item"] is True and "text" not in kept[-1]  # the log: ids and numbers, no words
    said = tool(app).run({})
    assert feelings.state(app)["item"] == ""
    assert "something I said I'd do: remind you to book the lab slot" in said  # still says which, and why
    assert 'Since then it\'s been kept: a reminder "Book the lab slot" exists, repeating every day.' in said
    assert "it eases over the next ones" in said
    assert "rechecked it at" in said and "when a reminder was set" in said
    assert app.events.tail(3, {"mind_feeling_recheck"})


def test_a_recheck_waits_when_nothing_is_about_a_promise(app, monkeypatch):
    jsave(app.paths.state / feelings.FILE, {"label": "uneasy", "object": "health", "item": "keeping things working"})
    monkeypatch.setattr(feelings, "tick", lambda a, p=None: pytest.fail("ticked"))
    assert feelings.recheck(app, "reminder_set") is None
    app.settings.set("mind.feelings.on", False)
    assert feelings.recheck(app, "reminder_set") is None


def test_a_reminder_or_deadline_change_schedules_the_recheck(app, monkeypatch):
    m = app.modules["mind"]
    m._mirror({"kind": "reminder_set", "at": "x"})
    job = app.scheduler.get("mind:feelings_recheck")
    assert job is not None and job.action == "mind.feelings_recheck" and job.payload == {"why": "reminder_set"}
    assert job.next_run - now().timestamp() <= 60  # soon, not on the 6 hour timer
    got = []
    monkeypatch.setattr(feelings, "recheck", lambda a, why="": got.append(why) or {"label": "uneasy"})
    assert asyncio.run(m._feelings_recheck({"why": "deadline_added"})) is None and got == ["deadline_added"]
    app.scheduler.cancel("mind:feelings_recheck")
    m._mirror({"kind": "reminder_fired"})  # not a change to what exists
    assert app.scheduler.get("mind:feelings_recheck") is None


def test_its_switch_and_the_feelings_switch(app, monkeypatch):
    uneasy_about_a_promise(app, monkeypatch)
    assert tool(app) is not None
    assert "brain_feelings says why" in feelings.prompt(app, read_hint=False)
    app.settings.set("mind.tools.feelings", False)
    assert tool(app) is None and {t.name for t in app.modules["mind"].call_tools()} == {
        "brain_plan", "brain_free_time", "brain_precedents"
    }  # fmt: skip
    assert "brain_feelings" not in feelings.prompt(app, read_hint=False)
    app.settings.set("mind.tools.feelings", True)
    app.settings.set("mind.feelings.on", False)
    assert tool(app) is None and feelings.view(app).startswith("Brain's feelings are off")


def test_what_counts_as_the_promised_thing():
    p = "I'll remind you to book the lab slot tomorrow"
    assert promises.matches(p, "Book the lab slot") and promises.matches(p, "book lab slot")
    assert not promises.matches(p, "book a cab") and not promises.matches(p, "Organic Chemistry: Quiz")
    assert promises.matches("I'll remind you Friday about the lab", "Lab report")
    assert not promises.matches("I'll remind you at 6", "anything at all")  # nothing it's about: never matched


def test_a_deadline_counts_too(app):
    promises.seen(app, "I'll remind you about the lab report tomorrow.", "deadlines.reminder")
    row = promises._state(app)["rows"][-1]
    dl = app.modules["deadlines"]
    app.settings.set("modules.enabled", ["mind", "reminders", "deadlines"])
    import types

    dl.items = types.MethodType(
        lambda self: {"d1": {"title": "Lab report", "status": "open", "due": "2030-01-01T09:00", "kind": "task"}}, dl
    )
    assert promises.item_for(app, row) == {"kind": "deadline", "text": "Lab report", "repeat": ""}
    assert promises.review(app)["kept"] == 1


def test_calls_and_desk_live_are_told_when_to_use_it(env):
    app = env.app
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "mind"])
    calls = app.modules["calls"]
    assert "brain_feelings" in calls.config_template()["systemInstruction"]
    app.settings.set("mind.tools.feelings", False)
    assert "brain_feelings" not in calls.config_template()["systemInstruction"]
    mind.forget_client(app)
