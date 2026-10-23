"""Check-in and quiz cards in the phone app (0.5.22): the phone gets a "card" field on check-in and quiz questions, a
reply from the card reaches the feature, and the quiz's self-grading (which comes with buttons) arrives as its own
card instead of being lost from the reply note. Through the call line's outbox too (the laptop asleep)."""

from __future__ import annotations

from kurooto.modules.calls.phone import card_of
from tests.unit import test_phone
from tests.unit.test_phone import last_item, post, sealed

phone = test_phone.phone  # the fixture: Phone calls set up, without a call line


def test_card_of():
    assert card_of("checkin", []) == "checkin"
    assert card_of("quiz", []) == "quiz" and card_of("qlink", []) == "quiz"
    assert card_of(None, ["qz:topology|abc:4"]) == "quiz"
    assert card_of(None, ["", "chk:evening|2026-10-20:skip"]) == "checkin"
    assert card_of("fakeq", ["fq:r1:none"]) == "" and card_of(None, []) == ""


def test_an_evening_check_in_is_a_card_answered_into_the_journal(phone):
    app = phone.app
    phone.on("checkins")
    day = app.modules["checkins"].day_of().isoformat()
    app.notify(
        "Evening check-in: How did today go?",
        kind="question",
        map_kind="checkin",
        map_ref=f"evening:{day}",
        buttons=[[("In 30 min", f"chk:evening|{day}:p30"), ("Not tonight", f"chk:evening|{day}:not")]],
    )
    it = last_item(phone)
    assert it["card"] == "checkin" and it["reply"] is True
    assert [b["label"] for b in it["buttons"]] == ["In 30 min", "Not tonight"]
    code, out = post(phone, sealed(app, {"answer": "Finished the problem set, skipped the gym"}, it["id"]))
    assert code == 200 and out["ok"] and "journal" in out["note"]
    journal = "\n".join(p.read_text(encoding="utf-8") for p in app.workspace.rglob("*.md"))
    assert "Finished the problem set, skipped the gym" in journal


def test_other_questions_are_no_card(phone):
    app = phone.app
    app.notify("How was the lecture?", kind="question", map_kind="fakeq", map_ref="r1")
    assert "card" not in last_item(phone)


def test_a_quiz_answer_from_a_card_brings_the_grading_card(phone):
    app = phone.app
    phone.on("quiz")
    d = app.workspace / "topology"
    d.mkdir()
    (d / "exam-prep.md").write_text(
        "# Topology\n## Must know\n- A compact metric space is sequentially compact.\n", encoding="utf-8"
    )
    app.modules["quiz"].ask_next("topology")
    q = last_item(phone)
    assert q["card"] == "quiz" and q["reply"] is True and "compact metric space" in q["text"]
    # sent while the computer was off: the call line's outbox hands it over when it's back
    phone.calls.on_queue([{"kind": "answer", "body": sealed(app, {"answer": "every sequence converges"}, q["id"])}])
    grade = last_item(phone)
    assert grade["id"] != q["id"] and grade["card"] == "quiz" and grade["reply"] is False
    assert [b["label"] for b in grade["buttons"]] == ["Forgot", "Hard", "Good", "Easy"]
    assert "The note says" in grade["text"]
    code, out = post(phone, sealed(app, {"button": 2}, grade["id"]))
    assert code == 200 and out["note"].startswith("Grade 4/5")
    assert [i["id"] for i in phone.phone.inbox()["items"]] == []  # both cards are done
