"""(0.9.0) "<deadline> is done" in plain words (modules/deadlines.py: done_said, by_words, done_by_words): a slip of the
keyboard in the done word is forgiven ("Organic Hw is doje"), "hw" plus a course's name or short name finds that
course's nearest open homework, two that fit equally ask with buttons, and nothing is marked without one clear match.
The AI's mark_deadline_done and move_deadline take words as well as an id, and list_deadlines gives jobs the ids."""

import datetime as dt

import pytest

from kurooto.modules.deadlines import done_said, done_word

TITLE = "2026-08-CH3105 Organic chemistry: Homework problems {:02d}"


def _last(env) -> dict:
    return [p for m, p in env.fake.sent if m == "sendMessage"][-1]


def _buttons(p: dict) -> list[tuple[str, str]]:
    rows = (p.get("reply_markup") or {}).get("inline_keyboard", [])
    return [(b["text"], b.get("callback_data", "")) for row in rows for b in row]


def _at(hours: float) -> dt.datetime:
    return dt.datetime.now().replace(second=0, microsecond=0) + dt.timedelta(hours=hours)


def _setup(env, *more):
    """Two courses (Organic Chemistry, short name ochem; Linear Algebra, la), homework 08 of the first due three hours
    ago, homework 09 in a week, and a Linear Algebra problem set due in an hour (nearer in time than either)."""
    env.on("deadlines", "subjects")
    env.app.settings.set(
        "subjects.list",
        [
            {"name": "Organic Chemistry", "slug": "organic-chemistry", "aliases": ["ochem"]},
            {"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["la"]},
        ],
    )
    dl = env.app.modules["deadlines"]
    dl.add(TITLE.format(8), _at(-3), subject="organic-chemistry")
    dl.add(TITLE.format(9), _at(24 * 7 - 3), subject="organic-chemistry")
    dl.add("Problem set 4", _at(1), subject="linear-algebra")
    for title, hours, subject in more:
        dl.add(title, _at(hours), subject=subject)
    return dl


def _id(dl, title: str) -> str:
    return next(i for i, it in dl.items().items() if it["title"] == title)


# ------------------------------------------------------------------------------------------------- the done word
@pytest.mark.parametrize(
    "word", ["done", "doje", "dun", "donee", "odne", "dpne", "finished", "finsihed", "submited", "completd", "Done"]
)
def test_small_slips_of_the_done_word_count(word):
    assert done_word(word)


@pytest.mark.parametrize("word", ["gone", "none", "dine", "dome", "tone", "dont", "don", "finishes", "fine", "dinner"])
def test_real_words_near_it_do_not(word):
    assert not done_word(word)


@pytest.mark.parametrize(
    ("text", "what"),
    [
        ("Organic Hw is doje", "Organic Hw"),
        ("ochem hw dun", "ochem hw"),
        ("LA problem set 4 donee", "LA problem set 4"),
        ("I finsihed the organic hw", "the organic hw"),
        ("submited the essay draft", "the essay draft"),
        ("the essay's done now", "the essay"),
        ("I handed in the lab report", "the lab report"),
        ("I'm done with the essay", "the essay"),
    ],
)
def test_what_is_done_is_read_from_the_sentence(text, what):
    assert done_said(text) == what


@pytest.mark.parametrize(
    "text",
    [
        "organic hw is not done",
        "organic hw isn't done",
        "organic hw will be done tomorrow",
        "organic hw almost done",
        "is the organic hw done?",
        "did I finish the organic hw",
        "I'm done",
        "the party is gone",
        "ps3 4/7 done",
        "remind me when the hw is done",
    ],
)
def test_not_done_questions_and_other_words_are_not(text):
    assert done_said(text) is None


# ----------------------------------------------------------------------------------------------- in the chat
def test_the_typo_marks_that_courses_nearest_homework_with_undo(env):
    dl = _setup(env)
    hw8, hw9, la = _id(dl, TITLE.format(8)), _id(dl, TITLE.format(9)), _id(dl, "Problem set 4")
    out = env.say("Organic Hw is doje")
    assert out.startswith("Marked done: ") and "Homework problems 08" in out
    items = dl.items()
    assert items[hw8]["status"] == "done" and items[hw9]["status"] == "open" and items[la]["status"] == "open"
    ((label, undo),) = _buttons(_last(env))
    assert label == "Undo" and env.press(undo).startswith("Undone")
    assert dl.items()[hw8]["status"] == "open"


def test_a_short_name_and_a_number_pick_the_one(env):
    dl = _setup(env)
    assert "Homework problems 09" in env.say("ochem hw 9 dun")  # 08 is nearer, but the number says 09
    assert dl.items()[_id(dl, TITLE.format(9))]["status"] == "done"
    assert dl.items()[_id(dl, TITLE.format(8))]["status"] == "open"
    assert "Problem set 4" in env.say("LA problem set donee")
    assert dl.items()[_id(dl, "Problem set 4")]["status"] == "done"


def test_two_that_fit_as_well_ask_with_buttons(env):
    dl = _setup(env, ("Homework problems 10", -2, "organic-chemistry"))
    assert env.say("organic hw is done").startswith("Which one is done? ")
    got = _buttons(_last(env))
    want = {_id(dl, TITLE.format(8)), _id(dl, "Homework problems 10")}
    assert {d.split(":")[1] for _, d in got} >= want and all(d.endswith(":done") for _, d in got)
    assert all(it["status"] == "open" for it in dl.items().values())  # nothing guessed
    assert env.press(f"dl:{_id(dl, 'Homework problems 10')}:done").startswith("Marked done")


def test_homework_words_alone_need_a_single_one(env):
    dl = _setup(env)
    assert env.say("hw is done").startswith("Which one is done? ")  # three courses' homework: never by time alone
    assert all(it["status"] == "open" for it in dl.items().values())


def test_words_that_name_no_deadline_are_left_to_the_ai(env):
    dl = _setup(env)
    out = env.say("the laundry is done")
    assert not (out or "").startswith(("Marked done", "Which one"))
    assert all(it["status"] == "open" for it in dl.items().values())


# --------------------------------------------------------------------------------------------- the AI's tools
def test_mark_deadline_done_takes_words_and_keeps_the_id_path(env):
    from kurooto.core.tools import run_tool

    dl = _setup(env)
    hw8, la = _id(dl, TITLE.format(8)), _id(dl, "Problem set 4")
    out = run_tool(env.app, "mark_deadline_done", {"what": "organic homework"})
    assert "Homework problems 08" in out and "Marked done" in out
    assert dl.items()[hw8]["status"] == "done"
    assert run_tool(env.app, "mark_deadline_done", {"id": la}) == "Marked done."  # by id: as before
    assert run_tool(env.app, "mark_deadline_done", {"id": "d00000000"}) == "That one is gone."
    assert "Homework problems 09" in run_tool(env.app, "mark_deadline_done", {"id": "organic hw 9"})  # a title as id
    assert run_tool(env.app, "mark_deadline_done", {}).startswith("Say which deadline")
    assert run_tool(env.app, "mark_deadline_done", {"what": "chemistry lab"}).startswith("No open deadline fits")


def test_a_tie_returns_the_candidates_with_ids_and_marks_nothing(env):
    from kurooto.core.tools import run_tool

    dl = _setup(env, ("Homework problems 10", -2, "organic-chemistry"))
    out = run_tool(env.app, "mark_deadline_done", {"what": "organic hw"})
    assert out.startswith("More than one open deadline fits")
    assert _id(dl, TITLE.format(8)) in out and _id(dl, "Homework problems 10") in out
    assert all(it["status"] == "open" for it in dl.items().values())
    moved = run_tool(env.app, "move_deadline", {"what": "organic hw", "due": "2026-12-01 17:00"})
    assert moved.startswith("More than one")


def test_move_deadline_by_words(env):
    from kurooto.core.tools import run_tool

    dl = _setup(env)
    la = _id(dl, "Problem set 4")
    out = run_tool(env.app, "move_deadline", {"what": "la problem set", "due": "2026-12-01 17:00"})
    assert out.startswith("Moved: Problem set 4") and dl.items()[la]["due"].startswith("2026-12-01T17:00")
    hw9 = _id(dl, TITLE.format(9))
    assert run_tool(env.app, "move_deadline", {"id": hw9, "due": "2026-12-02 09:00"}).startswith("Moved")


def test_jobs_can_list_deadlines_with_their_ids(env):
    from kurooto.core import reserve
    from kurooto.core.tools import agent_tools, run_tool, tools_for

    dl = _setup(env)
    tool = next(t for t in agent_tools(env.app) if t.name == "list_deadlines")
    assert tool.writes is False and tool.offline == "brief"  # read-only; on a call, answered while it's off too
    assert "list_deadlines" in {t.name for t in tools_for(env.app, None)}
    rows = run_tool(env.app, "list_deadlines", {})["deadlines"]
    assert [r["id"] for r in rows][:2] == [_id(dl, "Problem set 4"), _id(dl, TITLE.format(8))]  # nearest in time
    assert all({"id", "title", "subject", "due"} <= set(r) for r in rows)
    only = run_tool(env.app, "list_deadlines", {"what": "organic hw"})["deadlines"]
    assert {r["id"] for r in only} == {_id(dl, TITLE.format(8)), _id(dl, TITLE.format(9))}
    assert run_tool(env.app, "list_deadlines", {"what": "geology"})["deadlines"] == []
    done = next(t for t in agent_tools(env.app) if t.name == "mark_deadline_done")
    assert "list_deadlines" in done.description and "what" in done.params and not done.required
    assert f"(id {_id(dl, 'Problem set 4')})" in reserve.deadlines_md(env.app)
