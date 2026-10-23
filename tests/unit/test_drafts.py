"""Check my draft (modules/drafts.py): a draft sent with "check this" (or /check) gets comments pointing at lines or
places, never a rewrite; the course is guessed or asked; its AI policy (subjects' ai_policy: allowed, hints, off)
turns the check down or off; notes get the comments in a Kurooto block in the matching lecture note."""

from __future__ import annotations

import pytest

from kurooto.core import actions, layout
from kurooto.modules.drafts import numbered, parse_check, tidy_comments, wants
from tests.fakes.openai import FakeOpenAI

ANSWER = """KIND: proof
NOTE: none
SUMMARY: The induction is set up well but the step case skips a case.
- L3 | gap | The step from $n$ to $n+1$ assumes $n \\ge 2$, but the base case is $n = 1$.
- L4 | justify | Why the sum telescopes is never said.
- L5 | error | Replace it with $\\sum_{k=1}^{n+1} k$ and the proof is done.
"""
DRAFT = "\\begin{proof}\nBy induction on $n$.\nAssume it holds for $n$.\nThen the sum telescopes.\nSo it holds.\n"


@pytest.fixture
def dr(env):
    ai = FakeOpenAI()
    ai.answer = ANSWER
    app = env.app
    app.secrets.set("custom.api_key", ai.key)
    app.settings.set("brain.base_urls", {"custom": ai.base})
    app.settings.set("brain.models", {"custom": {"low": "fast", "medium": "smart", "high": "smart"}})
    app.settings.set("brain.main", "custom")
    app.settings.set("availability.night.enabled", False)
    env.on("subjects")
    env.say("/subject add Linear Algebra (la)")
    env.say("/subject add Topology (top)")
    env.on("drafts")
    real = env.fake.answer

    def answer(method, p):  # files keep their own extension (the fake gives every file .pdf)
        if method == "getFile" and "." in p["file_id"]:
            return {"file_id": p["file_id"], "file_path": f"docs/{p['file_id']}", "file_size": 10}
        return real(method, p)

    env.fake.answer = answer
    yield env, app.modules["drafts"], ai
    ai.close()


def tex_file(env, name="induction.tex", body=DRAFT):
    env.fake.files[f"docs/{name}"] = body.encode()
    return {"file_id": name, "file_name": name}


def asked(ai) -> str:
    return ai.requests[-1]["messages"][-1]["content"]


def test_what_counts_as_a_request_and_the_answers_form():
    assert wants("check this") and wants("Can you check my proof for la?") and wants("please review my essay")
    assert not wants("check the calendar") and not wants("checking in") and not wants("what's due")
    assert not wants("check this out!")
    got = parse_check(ANSWER)
    assert got["kind"] == "proof" and got["summary"].startswith("The induction") and len(got["comments"]) == 3
    assert got["comments"][1] == ("L4", "justify", "Why the sum telescopes is never said.")
    assert parse_check("UNREADABLE: blurry") == {"unreadable": "blurry"}
    assert parse_check("Here is the corrected proof: ...") == {}
    kept, dropped = tidy_comments(got["comments"], None, 15)
    assert dropped == 1 and [c[0] for c in kept] == ["L3", "L4"]  # the one that hands over the fix is left out
    short, _ = tidy_comments([("L1", "gap", "A step is missing. You need the lemma from lecture 3 here.")], "hints", 9)
    assert short == [("L1", "gap", "A step is missing.")]
    assert numbered("a\nb").splitlines() == ["1| a", "2| b"]


def test_a_tex_file_with_check_this_is_marked_line_by_line(dr):
    env, d, ai = dr
    out = env.say(caption="check this for la", document=tex_file(env))
    assert out == "Checking induction.tex for Linear Algebra…"
    assert env.app.jobs.run_next() is not None
    prompt = asked(ai)
    assert "Skill: check-draft" in prompt and "Course: Linear Algebra" in prompt
    assert "3| Assume it holds for $n$." in prompt and "Course AI policy: not set" in prompt
    text = env.fake.texts()[-1]
    assert text.startswith("Checked induction.tex (Linear Algebra): The induction is set up well")
    assert "1. L3 (gap): The step from $n$ to $n+1$" in text and "2. L4 (needs a reason)" in text
    assert "Replace it with" not in text and "(1 comment left out: they gave the fix away.)" in text
    assert "Nothing was rewritten" in text and "/subject policy linear-algebra hints" in text


def test_check_this_just_after_a_photo_and_the_course_from_the_class_or_asked(dr):
    env, d, ai = dr
    env.fake.files["docs/ph1.jpg"] = b"img"
    env.say(photo=[{"file_id": "ph1.jpg"}])  # a photo on its own: filed as usual, and remembered for a moment
    out = env.say("check this")
    assert out == "One question first: which course it's for."  # two subjects, none named: asked
    assert ai.requests == []
    q = env.app.ask.pending(source="drafts")[-1]
    assert q["choices"] == ["Linear Algebra", "Topology", "Not for a course"]
    env.app.ask.answer(q["id"], "Topology", via="telegram")
    env.app.jobs.run_next()
    assert "Course: Topology" in asked(ai) and ".jpg" in asked(ai)
    assert env.fake.texts()[-1].startswith("Checked ")


def test_the_courses_ai_policy_turns_it_down_or_off(dr):
    env, d, ai = dr
    assert env.say("/subject policy la hints").startswith("Linear Algebra: hints only")
    assert "[AI: hints]" in env.say("/subject")
    env.say(caption="/check la", document=tex_file(env))
    env.app.jobs.run_next()
    assert "Course AI policy: hints only" in asked(ai)
    assert "(No AI policy set" not in env.fake.texts()[-1]
    n = len(ai.requests)
    assert env.say("/subject policy top off").startswith("Topology: no AI help")
    out = env.say(caption="check my proof for top", document=tex_file(env, "p.tex"))
    assert out.startswith("Topology's AI policy is off, so I don't check drafts for it.")
    assert len(ai.requests) == n and env.app.jobs.run_next() is None
    # the Hint ladder goes by it too, and asks nothing
    env.on("hints")
    assert env.say("/hint top show it").startswith("The AI policy in Topology's course settings says")
    assert env.say("/subject policy la").startswith("Linear Algebra: AI policy hints")
    assert env.say("/subject policy la clear").endswith("(treated as allowed).")
    env.say("/subject add Topology (top, topo)")  # adding it again keeps its policy
    assert env.app.modules["subjects"].ai_policy("topology") == "off"


def test_notes_get_a_block_in_their_lecture_note_and_nothing_of_theirs_changes(dr):
    env, d, ai = dr
    lec = layout.path(env.app, "lecture", subject="linear-algebra", date="2026-10-14", slug="eigenvalues")
    lec.parent.mkdir(parents=True, exist_ok=True)
    mine = "# Eigenvalues\n\nMy own words about $Av = \\lambda v$.\n"
    lec.write_text(mine)
    ai.answer = ANSWER.replace("KIND: proof", "KIND: notes").replace(
        "NOTE: none", "NOTE: linear-algebra/2026-10-14-eigenvalues"
    )
    env.fake.files["docs/n.jpg"] = b"img"
    env.say(caption="check my notes for la", photo=[{"file_id": "n.jpg"}])
    env.app.jobs.run_next()
    text = lec.read_text()
    assert text.startswith(mine.rstrip("\n")) and "<!-- kurooto:draft-check -->" in text
    assert "- L3 (gap):" in text and "Replace it with" not in text
    assert "Also in linear-algebra/2026-10-14-eigenvalues.md" in env.fake.texts()[-1]
    env.say(caption="check my notes for la", photo=[{"file_id": "n.jpg"}])  # again: the block is replaced
    env.app.jobs.run_next()
    assert lec.read_text().count("<!-- kurooto:draft-check -->") == 1


def test_an_answer_not_in_comments_is_never_passed_on(dr):
    env, d, ai = dr
    ai.answer = "Sure! Here's your proof rewritten properly: By strong induction ..."
    env.say(caption="/check la", document=tex_file(env))
    env.app.jobs.run_next()
    last = env.fake.texts()[-1]
    assert last.startswith("No check this time: the AI's answer didn't come as comments")
    assert "strong induction" not in last
    ai.answer = "UNREADABLE: the photo is cut off"
    env.say(caption="/check la", document=tex_file(env))
    env.app.jobs.run_next()
    assert "couldn't read induction.tex (the photo is cut off)" in env.fake.texts()[-1]


def test_nothing_sent_and_other_messages_go_on_as_usual(dr):
    env, d, ai = dr
    assert env.say("check my essay").startswith("Send the draft")
    assert env.say("/check").startswith("Send the draft")
    env.fake.files["docs/x.zip"] = b"PK"
    assert env.say(caption="check this", document={"file_id": "x.zip", "file_name": "x.zip"}).startswith(
        "I can check photos, PDFs"
    )
    assert ai.requests == []


def test_the_dashboard_course_box(dr, tmp_path):
    env, d, ai = dr
    f = tmp_path / "essay.md"
    f.write_text("An essay.\nWith two lines.\n")
    r = actions.act(env.app, "draft.check", {"path": str(f), "subject": "la"})
    assert r["ok"] and r["message"].startswith("Checking essay.md for Linear Algebra…")
    env.app.jobs.run_next()
    assert "2| With two lines." in asked(ai) and env.fake.texts()[-1].startswith("Checked essay.md")
    assert not actions.act(env.app, "draft.check", {"path": str(tmp_path / "gone.md")})["ok"]
    r = actions.act(env.app, "subject.policy", {"subject": "la", "policy": "hints"})
    assert r["ok"] and r["policy"] == "hints"
    assert actions.study_view(env.app, "la")["ai_policy"] == "hints"
    assert actions.act(env.app, "subject.policy", {"subject": "la", "policy": "maybe"})["message"].startswith(
        "The AI policy is"
    )
