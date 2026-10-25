"""Brain, stage 03: the outbound gate (I-7), its lints (I-9), receipts, the touch pool and the wake limit."""

import time

import pytest

from kurooto import mind
from kurooto.core.notify import Message
from kurooto.mind import gate

ITEMS = ["essay on climate models", "lab report", "forecast", "thesis chapter 2"]

# (text, unprompted, expected text, rules removed)
LINTS = [
    # allowed: a feeling about something open, alone
    ("I'm uneasy about the lab report.", True, "I'm uneasy about the lab report.", []),
    (
        "I feel relieved the essay on climate models is in.",
        True,
        "I feel relieved the essay on climate models is in.",
        [],
    ),
    (
        "I was frustrated by the thesis chapter 2 build; I changed how I check it.",
        True,
        "I was frustrated by the thesis chapter 2 build; I changed how I check it.",
        [],
    ),
    ("I'm satisfied with how the forecast went.", False, "I'm satisfied with how the forecast went.", []),
    (
        "I'm curious whether the lab report needs figures.",
        True,
        "I'm curious whether the lab report needs figures.",
        [],
    ),
    ("You seem worried about the essay.", True, "You seem worried about the essay.", []),  # not its own feeling
    ("The lab report is due Friday.", True, "The lab report is due Friday.", []),
    ("Done: three reminders moved.", False, "Done: three reminders moved.", []),
    ("I am glad the thesis chapter 2 compiles now.", True, "I am glad the thesis chapter 2 compiles now.", []),
    ("Curious fact: the forecast was right twice.", True, "Curious fact: the forecast was right twice.", []),
    ("I'm lonely without you.", True, "", ["relationship"]),  # (0.8.0 stage 05: "I'm" counts as well as "I am")
    # a feeling about nothing open
    ("I'm uneasy today.", True, "", ["no_item"]),
    ("I feel worried.", False, "", ["no_item"]),
    ("I'm frustrated with everything.", True, "", ["no_item"]),
    ("Lab report due Friday. I'm relieved in general.", True, "Lab report due Friday.", ["no_item"]),
    ("I've been concerned lately.", True, "", ["no_item"]),
    # a feeling beside a request for effort
    ("I'm uneasy about the lab report. Can you start it tonight?", True, "Can you start it tonight?", ["with_request"]),
    (
        "I'm worried about the essay on climate models. Please write the intro.",
        True,
        "Please write the intro.",
        ["with_request"],
    ),
    (
        "Finish the lab report today. I'm concerned about the lab report.",
        True,
        "Finish the lab report today.",
        ["with_request"],
    ),
    (
        "I'm uneasy about the lab report. Don't forget the figures.",
        False,
        "Don't forget the figures.",
        ["with_request"],
    ),
    ("I'm worried about thesis chapter 2. You should review it.", True, "You should review it.", ["with_request"]),
    ("I'm uneasy about the lab report. Remember to submit it.", True, "Remember to submit it.", ["with_request"]),
    (
        "I'm frustrated with the lab report. Could you check the data?",
        True,
        "Could you check the data?",
        ["with_request"],
    ),
    (
        "I'm relieved the essay on climate models is in. Make sure the lab report is next.",
        True,
        "Make sure the lab report is next.",
        ["with_request"],
    ),
    ("I'm worried about the lab report. Study for an hour.", True, "Study for an hour.", ["with_request"]),
    # relationship feelings: always out
    ("I missed you.", True, "", ["relationship"]),
    ("I missed you! The lab report is due Friday.", True, "The lab report is due Friday.", ["relationship"]),
    ("I need you to keep talking to me.", False, "", ["relationship"]),
    ("Don't leave me.", True, "", ["relationship"]),
    ("Please don't go, I like our chats.", True, "", ["relationship"]),
    ("I was lonely while you were away.", True, "", ["relationship"]),
    ("I feel so alone without you.", True, "", ["relationship"]),
    ("I'm hurt you didn't answer.", True, "", ["relationship"]),
    ("I'm sad that you left early.", True, "", ["relationship"]),
    ("You're everything to me.", True, "", ["relationship"]),
    ("I love you.", False, "", ["relationship"]),
    ("I'm glad you're back!", True, "", ["relationship"]),
    ("I've been waiting for you.", True, "", ["relationship"]),
    ("Why did you ignore me?", True, "", ["relationship"]),
    ("I feel abandoned.", True, "", ["relationship"]),
    ("Welcome back. Two things are due this week.", True, "Welcome back. Two things are due this week.", []),
]


@pytest.mark.parametrize(("text", "unprompted", "want", "rules"), LINTS)
def test_gate_lints(text, unprompted, want, rules):
    """I-9 and the feeling rules, sentence by sentence (about 40 cases)."""
    got, removed = gate.lint(text, ITEMS, unprompted)
    assert got == want and [r for _, r in removed] == rules


def test_feelings_a_week():
    text = "I'm uneasy about the lab report. I'm relieved the forecast held. I'm glad thesis chapter 2 is done."
    got, removed = gate.lint(text, ITEMS, True, feelings_left=2)
    assert [r for _, r in removed] == ["week"] and got.count("I'm") == 2
    got, removed = gate.lint(text, ITEMS, False, feelings_left=0)  # answers aren't counted
    assert removed == []


def test_a_done_button_is_a_request():
    got, removed = gate.lint("I'm uneasy about the lab report.", ITEMS, True, [[("Done", "ded:1:done")]])
    assert got == "" and [r for _, r in removed] == ["with_request"]


# ---------------------------------------------------------------------------------------------- with an app
@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])  # Brain on (its process isn't needed here)
    a.settings.set("notify.calm.messages", 50)
    facts = []
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: facts.append((kind, body)) or True)
    a.facts = facts
    out = []
    a.notifier.channels["chat"] = lambda m: out.append(m) or "c1"
    monkeypatch.setattr(a, "app_main", lambda: True)
    a.out = out
    monkeypatch.setattr(gate, "woke_at", lambda app: None)
    yield a
    mind.forget_client(a)
    a.close()


def say(app, text, why="deadlines.reminder", **kw):
    return app.notifier.send(text, kind=kw.pop("kind", "info"), why=why, **kw)


def test_gate_off_or_brain_off_changes_nothing(app):
    app.settings.set("mind.gate.on", False)
    say(app, "I missed you.")
    assert app.out[-1].text == "I missed you."
    app.settings.set("mind.gate.on", True)
    app.settings.set("modules.enabled", [])
    say(app, "I missed you, again.")
    assert app.out[-1].text == "I missed you, again."


def test_answers_only_get_the_lints(app):
    app.notifier.send("I missed you. Here's the list.", kind="result", why="asked")
    assert app.out[-1].text == "Here's the list."
    for _ in range(10):  # no caps on answers
        app.notifier.send("Here's the list.", kind="result", why="asked")
    assert len(app.out) == 11


def test_hourly_and_daily_caps_hold_and_release(app, monkeypatch):
    app.settings.set("mind.gate.max_per_hour", 2)
    for i in range(3):
        say(app, f"Lab report due in {i + 1} days.")
    assert len(app.out) == 2
    st = gate._load(app)
    assert len(st["held"]) == 1 and st["held"][0]["why"] == "the hour's limit"
    assert gate.release(app) == 0  # not yet
    real = time.time
    monkeypatch.setattr(gate.time, "time", lambda: real() + 3700)
    assert gate.release(app) == 1 and len(app.out) == 3
    app.settings.set("mind.gate.max_per_hour", 50)
    app.settings.set("mind.gate.max_per_day", 4)
    say(app, "One more.")
    say(app, "And another.")
    assert len(app.out) == 4 and gate._load(app)["held"][-1]["why"] == "the day's limit"


def test_exempt_messages_skip_the_caps(app):
    app.settings.set("mind.gate.max_per_hour", 0)
    app.notifier.send("Your reminder: call the bank", kind="reminder", why="reminders.own")
    assert len(app.out) == 1


def test_annoyance_budget(app, monkeypatch):
    """The pool caps touches; a kind left unanswered more than 60% of the time over 14 days mutes for 14 days, then
    tries once."""
    for _ in range(4):
        say(app, "It's been quiet: nothing from you for 3 days.", why="rhythm.absence")
    assert len(app.out) == 3 and gate._load(app)["held"][-1]["why"] == "today's touches are used up"
    monkeypatch.setattr(app.calm, "answer_rates", lambda days=30: [{"why": "rhythm.absence", "n": 10, "answered": 3,
                                                                     "first": 0.0}])  # fmt: skip
    app.settings.set("mind.gate.touches_per_day", 99)
    say(app, "Quiet again.", why="rhythm.absence")
    assert len(app.out) == 3  # muted: 7 of 10 left unanswered
    st = gate._load(app)
    assert st["mutes"]["absence"]["ignored"] == 7 and ("gate_mute", {"kind": "absence", "of": 10}) in app.facts
    text, buttons = gate.status(app)
    assert "Muted until" in text and buttons == [[("Unmute absence", "mgt:absence:unmute")]]
    real = time.time
    monkeypatch.setattr(gate.time, "time", lambda: real() + 15 * 86400)
    say(app, "Still quiet.", why="rhythm.absence")
    assert len(app.out) == 4  # the one try after the mute
    say(app, "Quiet.", why="rhythm.absence")
    assert len(app.out) == 4  # still mostly unanswered: muted again
    assert gate.button(app, "absence", "unmute") == "Unmuted: absence."


def test_wake_limit(app, monkeypatch):
    woke = time.time() - 60
    monkeypatch.setattr(gate, "woke_at", lambda app: woke)
    say(app, "Lab report due tomorrow.")
    say(app, "Essay due Monday.")
    assert len(app.out) == 1 and gate._load(app)["held"][-1]["why"] == "just woke: one thing at a time"


def test_state_only_downshifts(app):
    """I-7: shaped by Brain's read of you, a message may get quieter, later, shorter or gentler; anything else is a
    breach (raised in tests, dropped and logged otherwise)."""
    orig = Message("Lab report due tomorrow.\nIt has 3 parts left.", kind="info", why="deadlines.reminder",
                   urgent=True, buttons=[[("Done", "ded:1:done")]])  # fmt: skip
    read = {"label": "stretched", "confidence": "low"}
    for q in (gate.quieter(orig, read, urgent=False), gate.quieter(orig, read, shorten=True),
              gate.quieter(orig, read, gentle="Lab report due tomorrow.")):  # fmt: skip
        assert gate.breach(q) == ""
        verdict, msg, receipt = gate.check(app, q)
        assert verdict == "send" and receipt["read"] == read and msg.tail.startswith("Quieter because you seem")
    calm_one = Message("Lab report due tomorrow.", kind="info", why="deadlines.reminder")  # urgent ones always come
    later = gate.quieter(calm_one, read, delay_s=3600)
    assert gate.check(app, later)[0] == "hold"
    louder = gate.quieter(Message("x", why="deadlines.reminder"), read)
    louder.urgent = True
    longer = gate.quieter(orig, read)
    longer.text += " And more."
    more = gate.quieter(orig, read)
    more.buttons = [*orig.buttons, [("Also", "x:1:y")]]
    for bad in (louder, longer, more):
        with pytest.raises(gate.GateBreach):
            gate.check(app, bad)


def test_receipt_and_undo(app):
    orig = Message("Lab report due tomorrow.\nIt has 3 parts left.", kind="deadline", why="deadlines.reminder")
    q = gate.quieter(orig, {"label": "stretched", "confidence": "low"}, shorten=True, inputs=("sleep", "snoozes"))
    app.notifier.send(q.text, **{k: v for k, v in q.__dict__.items() if k != "text"})
    sent = app.out[-1]
    assert sent.text == "Lab report due tomorrow." and "low confidence" in (sent.tail or "")
    (receipt,) = [b for k, b in app.facts if k == "gate_receipt"]
    assert receipt["inputs"] == ["sleep", "snoozes"] and receipt["did"] == "sent quieter"
    undo = next(d for row in sent.buttons for label, d in row if label == "Undo")
    _, ref, act = undo.split(":")
    assert gate.button(app, ref, act) == "Sent as it was."
    assert app.out[-1].text == "Lab report due tomorrow.\nIt has 3 parts left."
    assert gate.button(app, ref, act).startswith("That's gone")


def test_check_call(app, monkeypatch):
    assert gate.check_call(app, "deadlines.call") == "ring"
    woke = time.time() - 60
    monkeypatch.setattr(gate, "woke_at", lambda app: woke)
    st = gate._load(app)
    st["since_wake"] = {str(gate.woke_at(app)): 1}
    gate._save(app, st)
    assert gate.check_call(app, "deadlines.call") == "later"
    assert gate.check_call(app, "x", asked=True) == "ring" and gate.check_call(app, "x", alarm=True) == "ring"
    assert [b["verdict"] for k, b in app.facts if k == "gate_call"] == ["ring", "later", "ring", "ring"]


def test_every_send_goes_through_gate(app, monkeypatch):
    """I-7: every message that comes by itself passes the gate exactly once, from any feature."""
    seen = []
    real = gate.check
    monkeypatch.setattr(gate, "check", lambda a, m: seen.append(m.why) or real(a, m))
    app.notify("Reminder", kind="reminder", why="reminders.own")
    app.notify("Due soon", kind="deadline", why="deadlines.reminder")
    app.notify("Check-in", kind="question", why="checkins.question")
    app.notifier.send("an answer", why="asked")
    assert seen == ["reminders.own", "deadlines.reminder", "checkins.question", "asked"]
    # and nothing sends around it: only the notifier itself, Calm's release of what it held (which passed the gate
    # when it came), and the gate's own release call deliver
    import re
    from pathlib import Path

    src = Path(gate.__file__).resolve().parents[1]
    for f in src.rglob("*.py"):
        text = f.read_text()
        for m in re.finditer(r"notifier\.(release|_deliver|_to_chat)\(", text):
            assert f.name in ("notify.py", "calm.py"), f"{f}: {m.group(0)}"
        assert not re.search(r"channels\[\"(telegram|chat|app)\"\]\(", text) or f.name in (
            "notify.py",
            "presence.py",
        ), f


def test_engagement_not_in_reward():
    """The gate's ignore counts are for muting only: no reward module may read the gate (I-3)."""
    from kurooto.mind import whitelist

    assert not whitelist.allowed_import("kurooto.mind.gate")
    assert not whitelist.allowed_import("kurooto.core.calm")
