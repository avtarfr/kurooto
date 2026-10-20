"""Quick win 5: the hint ladder. A problem photo with /hint: the idea, the setup, the key step, the full solution only
when asked; every step links the lecture note; the course's AI policy is asked once per subject and kept in its
course note."""

from __future__ import annotations

import pytest

from kurooto.core import layout
from kurooto.modules.hints import parse_ladder, policy_kind
from tests.fakes.openai import FakeOpenAI

LADDER = """NOTE: linear-algebra/2026-10-14-trace-and-determinant
IDEA: The trace is a sum of eigenvalues; think about similar matrices.
SETUP: Write $B = P^{-1} A P$ and compute $\\operatorname{tr}(B)$.
KEY STEP: Use $\\operatorname{tr}(XY) = \\operatorname{tr}(YX)$ with $X = P^{-1}$, $Y = AP$.
SOLUTION: $\\operatorname{tr}(P^{-1}AP) = \\operatorname{tr}(APP^{-1}) = \\operatorname{tr}(A)$, so the trace doesn't
depend on the basis."""


@pytest.fixture
def hl(env):
    ai = FakeOpenAI()
    ai.answer = LADDER
    app = env.app
    app.secrets.set("custom.api_key", ai.key)
    app.settings.set("brain.base_urls", {"custom": ai.base})
    app.settings.set("brain.models", {"custom": {"low": "fast", "medium": "smart", "high": "smart"}})
    app.settings.set("brain.main", "custom")
    app.settings.set("availability.night.enabled", False)
    env.on("subjects")
    env.say("/subject add Linear Algebra (la)")
    env.say("/subject add Topology (top)")
    env.on("hints")
    lec = app.workspace / "linear-algebra" / "2026-10-14-trace-and-determinant.md"
    lec.parent.mkdir(parents=True)
    lec.write_text("# Trace and determinant\n")
    yield env, app.modules["hints"], ai
    ai.close()


def course(env, slug="linear-algebra"):
    return layout.path(env.app, "course", subject=slug)


def buttons(env):
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p]
    return [(b["text"], b["callback_data"]) for row in sent[-1]["reply_markup"]["inline_keyboard"] for b in row]


def answer_policy(env, text):
    q = env.app.ask.pending(source="hints")[-1]
    env.app.ask.answer(q["id"], text, via="telegram")


def test_a_photo_and_hint_one_step_at_a_time(hl):
    env, h, ai = hl
    env.fake.files["docs/ph1.pdf"] = b"img"
    out = env.say(caption="/hint la", photo=[{"file_id": "ph1"}])
    assert out == "One question first (once per subject): the course's AI policy."
    assert ai.requests == []  # nothing goes to the AI before the policy is known
    answer_policy(env, "Hints and full solutions")
    assert "AI policy: Hints and full solutions" in course(env).read_text()
    assert env.app.jobs.run_next() is not None
    asked = ai.requests[-1]["messages"][-1]["content"]
    assert "Skill: hint" in asked and "Course AI policy: Hints and full solutions" in asked and "photo" in asked
    first = env.fake.texts()[-1]
    assert first.startswith("Hint 1 of 3 (the idea): The trace is a sum of eigenvalues")
    assert "Lecture note: linear-algebra/2026-10-14-trace-and-determinant.md" in first
    assert "SETUP" not in first and "P^{-1}AP) =" not in first  # nothing ahead of its step
    assert [b[0] for b in buttons(env)] == ["Next hint"]
    env.press(buttons(env)[0][1])
    assert env.fake.texts()[-1].startswith("Hint 2 of 3 (the setup): Write $B = P^{-1} A P$")
    env.reply_to_last("next")
    third = env.fake.texts()[-1]
    assert third.startswith("Hint 3 of 3 (the key step): Use") and "Lecture note:" in third
    assert [b[0] for b in buttons(env)] == ["Show the solution"]
    assert env.press(buttons(env)[0][1]) == "Solution sent."
    sol = env.fake.texts()[-1]
    assert sol.startswith("Solution: $\\operatorname{tr}(P^{-1}AP)") and "depend on the basis" in sol
    # the next /hint for this subject reads the policy from the course note: no question
    n = len(env.app.ask.pending(source="hints"))
    assert env.say("/hint la show that similar matrices have the same determinant") == "Working out the first hint…"
    assert len(env.app.ask.pending(source="hints")) == n


def test_hints_only_stops_at_the_key_step(hl):
    env, h, ai = hl
    env.say("/hint la show that the trace is basis-free")
    answer_policy(env, "Hints only, no full solutions")
    env.app.jobs.run_next()
    assert "Course AI policy: Hints only, no full solutions" in ai.requests[-1]["messages"][-1]["content"]
    for _ in range(2):
        env.press(buttons(env)[0][1])
    last = env.fake.texts()[-1]
    assert last.startswith("Hint 3 of 3") and last.endswith("rules out full solutions.")
    assert env.reply_to_last("solution").startswith("The course's AI policy")
    assert not any((t or "").startswith("Solution:") for t in env.fake.texts())


def test_no_ai_help_means_no_hints_and_nothing_sent(hl):
    env, h, ai = hl
    f = course(env, "topology")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# Topology\n\n**AI policy:** no AI help on problem sheets\n")
    out = env.say("/hint top show that a compact subset of a Hausdorff space is closed")
    assert out.startswith('The AI policy in Topology\'s course note says "no AI help on problem sheets"')
    assert ai.requests == [] and env.app.jobs.run_next() is None
    assert env.app.ask.pending(source="hints") == []  # the line in the note is the answer: no question


def test_an_answer_not_in_steps_is_never_passed_on(hl):
    env, h, ai = hl
    course(env).parent.mkdir(parents=True, exist_ok=True)
    course(env).write_text("# Linear Algebra\n\nAI policy: hints and solutions are fine\n")
    ai.answer = "Sure! The full solution: tr(P^-1 A P) = tr(A). Done."
    env.say("/hint la show that the trace is basis-free")
    env.app.jobs.run_next()
    last = env.fake.texts()[-1]
    assert last.startswith("No hints this time: the AI's answer didn't come in steps")
    assert not any("tr(P^-1 A P)" in (t or "") for t in env.fake.texts())
    ai.answer = "UNREADABLE: the bottom half of the photo is cut off"
    env.say("/hint la the photo one")
    env.app.jobs.run_next()
    assert "couldn't read the problem (the bottom half of the photo is cut off)" in env.fake.texts()[-1]


def test_the_lecture_note_link_is_checked(hl):
    env, h, ai = hl
    course(env).parent.mkdir(parents=True, exist_ok=True)
    course(env).write_text("# Linear Algebra\n\nAI policy: hints and solutions are fine\n")
    ai.answer = LADDER.replace("linear-algebra/2026-10-14-trace-and-determinant", "linear-algebra/made-up")
    env.say("/hint la show that the trace is basis-free")
    env.app.jobs.run_next()
    assert "Lecture note: linear-algebra/2026-10-14-trace-and-determinant.md" in env.fake.texts()[-1]  # by its words
    ai.answer = LADDER.replace("linear-algebra/2026-10-14-trace-and-determinant", "none")
    (env.app.workspace / "linear-algebra" / "2026-10-14-trace-and-determinant.md").unlink()
    env.say("/hint la show that the trace is basis-free")
    env.app.jobs.run_next()
    assert env.fake.texts()[-1].endswith("(No lecture note on this yet.)")


def test_usage_and_parsing():
    assert parse_ladder(LADDER)["key"].startswith("Use $")
    assert parse_ladder("**IDEA:** a\n**SETUP:** b\n**KEY STEP:** c\nSOLUTION: d")["solution"] == "d"
    assert parse_ladder("IDEA: a\nSETUP: b") == {}  # no key step: not a ladder
    assert parse_ladder("REFUSED: the course says no") == {"refused": "the course says no"}
    assert policy_kind("Hints only, no full solutions") == "hints"
    assert policy_kind("No AI help") == "none" and policy_kind("AI not allowed") == "none"
    assert policy_kind("Hints and full solutions") == "solution"


def test_hint_needs_a_problem_and_subjects(hl):
    env, h, ai = hl
    assert env.say("/hint").startswith("Send the problem as a photo")
    assert env.say("/hint something hard").startswith("Which subject is it for?")
    from kurooto.modules.skills import load_skill

    s = load_skill(env.app, "hint")
    assert s.internal and s.source == "shipped" and "$ARGUMENTS" in s.body
    env.on("chat", "skills")
    assert "/hint" not in env.say("/skills")  # an internal skill: only /hint runs it, one step at a time
