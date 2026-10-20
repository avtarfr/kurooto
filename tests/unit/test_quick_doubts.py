"""Quick win 3: the doubt queue. Doubts go into the subject's doubts note (notes layout API); the open ones come back
before that subject's next class with a Tick button each; no AI."""

from __future__ import annotations

import datetime as dt

import pytest

from kurooto.core import layout
from kurooto.modules import doubts as dmod

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@pytest.fixture
def dq(env, monkeypatch):
    env.app.settings.set("availability.night.enabled", False)
    env.on("subjects")
    env.say("/subject add Linear Algebra (la)")
    env.say("/subject add Topology (top)")
    env.on("doubts")
    t = {"now": dt.datetime.combine(dt.date.today(), dt.time(8, 40))}
    monkeypatch.setattr(dmod, "now", lambda: t["now"])
    return env, env.app.modules["doubts"], t


def note(env, slug="linear-algebra"):
    return layout.path(env.app, "doubts", subject=slug)


def buttons(env):
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p]
    return [(b["text"], b["callback_data"]) for row in sent[-1]["reply_markup"]["inline_keyboard"] for b in row]


def test_a_doubt_goes_into_the_subjects_note(dq):
    env, d, _ = dq
    out = env.say("/doubt la why does the rank not change?")
    assert out.startswith("Added to Linear Algebra's doubts (1 open)")
    text = note(env).read_text()
    assert text.startswith("---\n") and "# Linear Algebra: doubts" in text and "## Doubts\n" in text
    assert f"- [ ] why does the rank not change? ({dt.date.today():%Y-%m-%d})" in text
    assert env.say("/doubt la why does the rank not change?") == "That one is already on Linear Algebra's doubts."
    # plain words, the subject named anywhere
    assert "Topology's doubts" in env.say("I have a doubt about compactness in top")
    assert d.open("topology") == ["compactness in top"]
    assert "Topology's doubts" in env.say("I have a doubt about Topology: is every compact set closed")
    assert d.open("topology")[-1] == "is every compact set closed"


def test_your_own_text_in_the_note_stays(dq):
    env, d, _ = dq
    f = note(env)
    f.parent.mkdir(parents=True, exist_ok=True)
    mine = (
        "# My LA doubts\n\nAsk the TA on Friday.\n\n## Doubts\n- [x] old one\n- [ ] kernel vs null space\n\n"
        "## Later\nstuff\n"
    )
    f.write_text(mine)
    env.say("/doubt la is the trace basis-free?")
    text = f.read_text()
    assert text.startswith("# My LA doubts\n\nAsk the TA on Friday.\n\n## Doubts\n- [x] old one\n- [ ] kernel vs null")
    assert "- [ ] is the trace basis-free?" in text.split("## Later")[0] and text.endswith("## Later\nstuff\n")
    assert d.open("linear-algebra") == ["kernel vs null space", "is the trace basis-free?"]


def test_no_subject_named_uses_the_class_just_now_else_asks(dq):
    env, d, t = dq
    day = DAYS[t["now"].weekday()]
    env.say(f"/class {day} 07:30-08:25 top")
    assert "Topology's doubts" in env.say("I have a doubt about Gibbs free energy")  # top ended 15 min ago
    t["now"] = t["now"].replace(hour=13)
    out = env.say("I have a doubt about Gibbs free energy again")
    assert out == "It's saved once you tap its subject."
    labels = buttons(env)
    assert [x[0] for x in labels] == ["la", "top"]
    assert env.press(labels[0][1]).startswith("Added to Linear Algebra's doubts")
    assert d.open("linear-algebra") == ["Gibbs free energy again"]


def test_open_doubts_come_before_the_next_class_with_tick_buttons(dq):
    env, d, t = dq
    day = DAYS[t["now"].weekday()]
    env.say(f"/class {day} 09:00-09:55 la")
    env.say("/doubt la why does the rank not change?")
    env.say("/doubt la is the trace basis-free?")
    t["now"] = t["now"].replace(hour=8, minute=0)
    assert d.before_class() == 0  # an hour before: not yet
    t["now"] = t["now"].replace(hour=8, minute=35)
    assert d.before_class() == 1
    msg = env.fake.texts()[-1]
    assert msg.startswith("Before Linear Algebra at 09:00: your open doubts")
    assert "1. why does the rank not change?" in msg and "2. is the trace basis-free?" in msg
    assert d.before_class() == 0  # once per class
    ticks = buttons(env)
    assert [x[0] for x in ticks] == ["Tick 1", "Tick 2", "Why?", "Less of this"]
    assert env.press(ticks[0][1]) == "Ticked in your notes."
    assert env.press(ticks[0][1]) == "Already ticked (or changed in the note)."
    assert "- [x] why does the rank not change?" in note(env).read_text()
    assert d.open("linear-algebra") == ["is the trace basis-free?"]
    listed = env.say("/doubts")
    assert listed.startswith("Linear Algebra: open doubts") and "rank" not in listed
    assert env.say("/doubts top") == "No open doubts for Topology."


def test_a_skipped_class_or_one_without_doubts_sends_nothing(dq):
    env, d, t = dq
    day = DAYS[t["now"].weekday()]
    env.say(f"/class {day} 09:00-09:55 la")
    env.say(f"/class {day} 09:00-09:55 top")
    env.say("/doubt la why does the rank not change?")
    env.app.modules["subjects"].set_skip(["linear-algebra"], day=t["now"].date())
    n = len(env.fake.texts())
    assert d.before_class() == 0 and len(env.fake.texts()) == n


def test_zettelkasten_layout_and_custom_place(dq):
    env, d, _ = dq
    env.app.settings.set("notes.layout", "zettelkasten")
    env.say("/doubt la what's a dual basis?")
    f = env.app.workspace / "sources" / "linear-algebra" / "doubts.md"
    text = f.read_text()
    assert "trust_tier: agent_written" in text and "id: sources/linear-algebra/doubts" in text
    env.app.settings.set("notes.paths", {"doubts": "questions/{subject}.md"})
    env.say("/doubt top what's a net?")
    assert (env.app.workspace / "questions" / "topology.md").read_text().count("- [ ] what's a net?") == 1


def test_doubts_need_subjects_and_are_off_until_turned_on(env):
    from kurooto.web.api import MODULE_ORDER

    assert "doubts" in MODULE_ORDER and not env.app.is_on("doubts")
    ok, why = env.app.enable("doubts")
    assert not ok and "Subjects" in why
