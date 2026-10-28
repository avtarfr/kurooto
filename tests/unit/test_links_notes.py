"""0.9.0, the links release, batch 2 (notes and knowledge): the links between the Quiz, revision, doubts, the concept
graph, Brain's model of what you know and the notes tools. Fake notes and fake AIs throughout; nothing leaves."""

from __future__ import annotations

import datetime as dt

import pytest

from kurooto import mind
from kurooto.core.state import jsave
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind.tom import knowledge


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind", "quiz"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def note(slug, title, links=()):
    from pathlib import Path

    from kurooto.core import conceptgraph

    return conceptgraph.Note(slug=slug, path=Path(slug), title=title, links=set(links), hash=slug + "1")


NOTES = {
    "zettel/lte": note("zettel/lte", "Local Thermodynamic Equilibrium", ["zettel/boltzmann"]),
    "zettel/boltzmann": note("zettel/boltzmann", "Boltzmann distribution"),
    "zettel/radiative-transfer": note("zettel/radiative-transfer", "Radiative transfer", ["zettel/lte"]),
}


@pytest.fixture
def notes(monkeypatch):
    monkeypatch.setattr(knowledge, "concepts", lambda app: dict(NOTES))
    return NOTES


# ------------------------------------------------------------------------------- L72: quiz items -> concept slugs
def test_cards_count_for_the_concept_they_name(app, notes):
    """A card Kurooto wrote names its concept; its text doesn't have to. A link card counts for both ends."""
    quiz = app.modules["quiz"]
    q = "Why does the source function equal the Planck function there?"
    iid = quiz.add_card("physics", q, concept="zettel/lte")
    quiz.grade("physics", iid, 5)
    links = {
        "items": {
            "l1": {
                "text": "How does radiative transfer use the other one?",
                "a": "zettel/radiative-transfer",
                "b": "zettel/boltzmann",
                "ef": 2.5,
                "interval": 0,
                "reps": 0,
                "due": "2026-01-01",
                "history": [{"date": "2026-01-01", "q": 1}],
            }
        }
    }
    jsave(quiz._dir() / f"{knowledge.LINKS}.json", links)
    assert knowledge.from_quiz(app) == 3
    assert knowledge.mastery(app, "zettel/lte") > knowledge.P_INIT
    assert knowledge.mastery(app, "zettel/radiative-transfer") < knowledge.P_INIT
    assert knowledge.mastery(app, "zettel/boltzmann") < knowledge.P_INIT
    assert knowledge.from_quiz(app) == 0  # each graded answer once


def test_a_card_without_a_concept_falls_back_to_names(app, notes):
    assert knowledge.item_slugs({"text": "State the Boltzmann distribution"}, NOTES) == ["zettel/boltzmann"]
    assert knowledge.item_slugs({"text": "State the Boltzmann distribution", "concept": "gone/x"}, NOTES) == [
        "zettel/boltzmann"
    ]


# ------------------------------------------------------------------------------------- L137: one /learned
@pytest.mark.parametrize("order", [["learning", "mind"], ["mind", "learning"]])
def test_learned_answers_both_lists_whichever_feature_is_first(env, order):
    """Brain and "Learns from its own work" both register /learned; whichever answers, both lists are reachable."""
    env.app.settings.set("modules.enabled", ["telegram", *order])
    out = env.say("/learned")
    assert "Nothing learned lately" in out and "No learned skills yet" in out
    assert env.say("/learned retire nosuch") == "There's no active skill nosuch."
    env.app.settings.set("modules.enabled", ["telegram", "learning"])
    assert "Brain's" in env.say("/learned run nosuch hello")
    assert env.say("/learned").startswith("Nothing learned lately")


# ------------------------------------------------------------------- L66: missed on a call -> doubts, hints -> gap
@pytest.fixture
def study(env):
    env.app.settings.set("availability.night.enabled", False)
    env.on("subjects")
    env.say("/subject add Linear Algebra (la)")
    env.on("doubts", "quiz")
    root = env.app.workspace / "linear-algebra"
    root.mkdir(parents=True, exist_ok=True)
    (root / "exam-prep.md").write_text(
        "# LA exam prep\n\n## Must know\n- State the rank-nullity theorem precisely\n"
        "- Define an eigenvector of a map\n",
        encoding="utf-8",
    )
    return env


def last_buttons(env):
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p]
    return [(b["text"], b["callback_data"]) for row in sent[-1]["reply_markup"]["inline_keyboard"] for b in row]


def test_questions_missed_on_a_call_are_offered_as_doubts_after_it(study):
    env, quiz = study, study.app.modules["quiz"]
    items = quiz.state("linear-algebra")["items"]
    ids = {v["text"]: k for k, v in items.items()}
    quiz._tool_grade({"subject": "linear-algebra", "item": ids["State the rank-nullity theorem precisely"], "grade": 1})
    quiz._tool_grade({"subject": "linear-algebra", "item": ids["Define an eigenvector of a map"], "grade": 5})
    env.app.availability.set_on_call(dt.datetime.now() + dt.timedelta(minutes=2))
    quiz._weak_offer({})  # still on the call: nothing yet
    assert not any("missed" in str(p.get("text", "")) for m, p in env.fake.sent if m == "sendMessage")
    env.app.availability.set_on_call(None)
    quiz.call_transcript("quiz:linear-algebra", [{"who": "you", "text": "hi"}])
    offer = [p["text"] for m, p in env.fake.sent if m == "sendMessage"][-1]
    assert "rank-nullity" in offer and "eigenvector" not in offer
    add = next(d for t, d in last_buttons(env) if t == "Add to doubts")
    assert env.press(add) == "Added 1 to your doubts."
    assert env.app.modules["doubts"].open("linear-algebra") == ["State the rank-nullity theorem precisely"]
    assert env.press(add) == "That offer is gone."


def test_no_doubt_offer_with_the_switch_off(study):
    env, quiz = study, study.app.modules["quiz"]
    env.app.settings.set("quiz.to_doubts", False)
    iid = next(iter(quiz.state("linear-algebra")["items"]))
    quiz._tool_grade({"subject": "linear-algebra", "item": iid, "grade": 0})
    quiz.call_transcript("quiz:linear-algebra", [])
    assert not (quiz._dir() / "call-weak.json").exists()
    assert not any("missed" in str(p.get("text", "")) for m, p in env.fake.sent if m == "sendMessage")


def test_the_last_hint_is_a_weak_sign_of_a_gap(app, notes):
    from kurooto.modules.hints import Hints

    h = Hints(app)
    ladder = {"idea": "Use the Boltzmann distribution", "setup": "s", "key": "k", "solution": ""}
    app.settings.set("modules.enabled", ["mind", "subjects", "hints"])
    h._step({"id": "ab12", "step": 2, "ladder": ladder, "problem": "a gas in a box", "policy": "hints"})
    assert knowledge.mastery(app, "zettel/boltzmann") < knowledge.P_INIT
    app.settings.set("hints.weak_sign", False)
    before = knowledge.mastery(app, "zettel/boltzmann")
    h._step({"id": "ab13", "step": 2, "ladder": ladder, "problem": "a gas in a box", "policy": "hints"})
    assert knowledge.mastery(app, "zettel/boltzmann") == before


# ------------------------------------------------------------------------- L67: a call's quiz, frontier first
def test_a_calls_quiz_puts_frontier_questions_first_among_the_due(app, notes, monkeypatch):
    from kurooto.mind import frontier

    quiz = app.modules["quiz"]
    for q, c in (
        ("Explain radiative transfer through a slab", "zettel/radiative-transfer"),
        ("Why does it hold in the deep interior?", "zettel/lte"),
        ("Write down the partition function form", "zettel/boltzmann"),
    ):
        quiz.add_card("physics", q, concept=c, due=dt.date.today())
    monkeypatch.setattr(
        frontier, "grades", lambda a: {"zettel/lte": frontier.FRONTIER, "zettel/boltzmann": frontier.SOLID}
    )
    before = quiz._tool_next({"subject": "physics"})
    assert "focus" not in before  # off by default: due order, as before
    app.settings.set("quiz.call_frontier", True)
    after = quiz._tool_next({"subject": "physics"})
    assert after["items"][0]["question"].startswith("Why does it hold")
    assert sorted(i["item"] for i in after["items"]) == sorted(i["item"] for i in before["items"])  # same set
    assert after["focus"] == ["Local Thermodynamic Equilibrium"]


# ------------------------------------------------------------- L63 / L65: mastery and doubts in the revision plan
from tests.unit.test_revision import SLUG, world  # noqa: E402, F401  (the revision plan's world and clock)


def names_why(app):
    return [(t["name"], t["why"]) for t in app.modules["exam_season"].revision.ranked(SLUG)[0]]


def test_an_open_doubt_ranks_its_topic_with_weak_recall(world):  # noqa: F811
    env, app, _ = world
    before = names_why(app)
    assert before[-1] == ("determinants", "")
    env.on("doubts")
    env.say("/doubt la why do determinants multiply?")
    after = names_why(app)
    assert after[-1] == ("determinants", "an open doubt") and len(after) == len(before)  # raised, nothing dropped
    assert [n for n, _ in after] == [n for n, _ in before]  # weak tier is next to last already: same order here
    app.settings.set("doubts.to_revision", False)
    assert names_why(app) == before


def test_mastery_orders_ungraded_topics_only_within_their_tier(world, monkeypatch):  # noqa: F811
    from kurooto.mind import frontier

    env, app, _ = world
    (app.workspace / SLUG / "2026-11-02-jordan-form.md").write_text("# Jordan form\n\n" + "word " * 80, "utf-8")
    (app.workspace / SLUG / "2026-11-03-spectral.md").write_text("# Spectral theorem\n\n" + "word " * 80, "utf-8")
    prep = app.workspace / SLUG / "exam-prep.md"
    text = prep.read_text("utf-8").replace(
        "- Lecture 3: Jordan form", f"- [[{SLUG}/2026-11-02-jordan-form|Jordan form]]"
    )
    prep.write_text(text.replace("- Spectral theorem", f"- [[{SLUG}/2026-11-03-spectral|Spectral theorem]]"), "utf-8")
    base = names_why(app)
    monkeypatch.setattr(frontier, "grades", lambda a: {f"{SLUG}/2026-11-03-spectral": frontier.FRONTIER})
    monkeypatch.setattr(
        frontier,
        "masteries",
        lambda a: {f"{SLUG}/2026-11-02-jordan-form": 0.9, f"{SLUG}/2026-11-03-spectral": 0.2},
    )
    assert names_why(app) == base  # off by default
    app.settings.set("exam_season.use_mastery", True)
    got = names_why(app)
    assert sorted(got) == sorted(base)  # the same topics, with the same tiers
    rest = [n for n, w in got if w == ""]
    assert rest.index("Spectral theorem") < rest.index("determinants") < rest.index("Jordan form")


def test_open_doubts_reach_a_call_before_class_only_when_shared(study, monkeypatch):
    from kurooto.modules import doubts as dmod

    env = study
    t = dt.datetime.combine(dt.date.today(), dt.time(8, 0))
    monkeypatch.setattr(dmod, "now", lambda: t)
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][t.weekday()]
    env.app.settings.set(
        "subjects.timetable", [{"day": day, "start": "10:00", "end": "11:00", "subject": "linear-algebra"}]
    )
    env.say("/doubt la why does the rank not change?")
    d = env.app.modules["doubts"]
    assert d.call_brief() == {} and d.shared("linear-algebra") == []  # doubts.share is off by default
    env.app.settings.set("doubts.share", True)
    assert d.call_brief() == {"open_doubts_before_class": ["Linear Algebra at 10:00: why does the rank not change?"]}
    assert d.shared("linear-algebra") == ["why does the rank not change?"]
    env.app.settings.set("doubts.share_h", 1)
    assert d.call_brief() == {}  # the class is two hours away


# ---------------------------------------------------------------------------- L73: reported exam results
def test_results_are_parsed_only_with_a_score_and_an_exam():
    from kurooto.mind.tom import results

    assert results.parse("I got 12/30 on the LA midterm") == (0.4, "midterm", "LA midterm")
    assert results.parse("scored 85% in the topology quiz")[:2] == (0.85, "quiz")
    assert results.parse("I got 3 apples on the way home") is None
    assert results.parse("I got 40/30 on the test") is None
    assert results.parse("what did I get on the LA midterm?") is None


def test_a_reported_result_is_evidence_a_line_and_an_offer(world, monkeypatch):  # noqa: F811
    from kurooto.mind.tom import knowledge, results

    env, app, clock = world
    monkeypatch.setattr(results, "now", lambda: clock["t"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    app.keeper = sk.Keeper(app.paths.state / "mind")
    env.on("mind")
    monkeypatch.setattr(mind.connect(app), "report", lambda kind, body: app.keeper.append(kind, body).get("ok", False))
    concept = f"{SLUG}/2026-11-09-determinants"
    monkeypatch.setattr(results, "concepts", lambda a, slug: [concept])
    before = knowledge.mastery(app, concept)
    out = env.say("I got 12/30 on the LA midterm")
    assert out.startswith("Noted: Linear Algebra midterm, 40%.")
    assert any("Plan 13 hours" in str(p.get("text")) for m, p in env.fake.sent if m == "sendMessage")
    assert knowledge.mastery(app, concept) < before
    prep = (app.workspace / SLUG / "exam-prep.md").read_text("utf-8")
    assert "<!-- kurooto:exam-results -->" in prep and ": midterm, 40%. A gap to revise." in prep
    assert "## Must know" in prep  # the note's own text is all still there
    offers = [p for m, p in env.fake.sent if m == "sendMessage" and "Plan 13 hours" in str(p.get("text"))]
    yes = next(b["callback_data"] for row in offers[-1]["reply_markup"]["inline_keyboard"] for b in row
               if b["text"].startswith("Yes"))  # fmt: skip
    assert "13 h" in env.press(yes) or "13" in str(app.settings.get("startby.exam_by_subject"))
    assert app.settings.get("startby.exam_by_subject.linear-algebra") == 13
    app.settings.set("mind.tom.from_chat", False)
    assert not str(env.say("I got 29/30 on the LA final exam") or "").startswith("Noted")
    app.keeper.close()
    mind.forget_client(app)


# ------------------------------------------------------------- L68: Classroom posts and Announcements lines
from tests.unit.test_gbrain_more import course  # noqa: E402, F401  (a Statistics course with notes and a deadline)


def test_the_course_timeline_has_classroom_posts_and_announcements(course, monkeypatch):  # noqa: F811
    import json

    from kurooto.modules import coursepages, google_classroom

    env, root, day, due = course
    app = env.app
    app.settings.set("classroom_notes.folders", {"Stats 101": "stats"})
    monkeypatch.setattr(app, "is_on", lambda m: m in ("subjects", "deadlines", "classroom_notes", "telegram"))
    at = f"{day}T05:30:00Z"
    posts = {"c1": {"name": "Stats 101", "posts": {"announcement:1": {"at": at, "title": "Quiz 2 moved", "url": ""}}}}
    (app.paths.state / "classroom-posts.json").write_text(json.dumps(posts))
    (root / "course.md").write_text("# Statistics\n\n## Announcements\n- 2026-01-01: too old\n"
                                    f"- {day}: lab moved to Friday\n")  # fmt: skip
    assert google_classroom.posts_of(app, "stats")[0]["title"] == "Quiz 2 moved"
    assert coursepages.write_all(app) == 1
    page = (root / "course.md").read_text()
    posted = google_classroom._local_day(at).isoformat()
    assert f"- **{posted}** | announcement — Quiz 2 moved" in page
    assert f"- **{day}** | announcement — lab moved to Friday" in page and "too old" not in page.split("kurooto:")[1]
    app.settings.set("gbrain.course_announcements", False)
    coursepages.write_all(app)
    assert "| announcement" not in (root / "course.md").read_text()


# -------------------------------------------------------------------------- L69: mail and Classroom on calls
def test_mail_and_classroom_lines_reach_calls_only_when_turned_on(env):
    import json

    from kurooto.providers.base import Result, Verdict

    app = env.app
    md, g = app.modules["mail_digest"], app.modules["google"]
    (md.dir / "batches").mkdir(parents=True, exist_ok=True)
    (md.dir / "batches" / "b1.json").write_text(json.dumps({"messages": [{"id": "m"}], "at": "2026-10-29T08:00:00"}))
    monkey = Result(Verdict.OK, "Needs you\n- the lab form by Friday\n\nNeeds you: 1, the lab form by Friday")
    md._done(None, monkey, {"batch": "b1.json"})
    at = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    posts = {"c": {"name": "Stats 101", "posts": {"a:1": {"at": at, "title": "Quiz 2 moved", "url": ""}}}}
    (app.paths.state / "classroom-posts.json").write_text(json.dumps(posts))
    assert md.call_brief() == {} and g.call_brief() == {}  # both off by default: a call's AI may be a cloud one
    app.settings.set("mail_digest.on_calls", True)
    app.settings.set("google.classroom_on_calls", True)
    assert md.call_brief()["mail_needs_you"].startswith("Needs you: 1, the lab form by Friday (mail digest, ")
    assert g.call_brief() == {"classroom_posts_today": ["Stats 101: Quiz 2 moved"]}


# ------------------------------------------------------------------------ L70: the class as a sorter hint
@pytest.fixture
def sapp(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    from pathlib import Path

    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["subjects", "sorter", "doubts"])
    a.settings.set("subjects.list", [{"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["LA"]},
                                     {"name": "Topology", "slug": "topology", "aliases": []}])  # fmt: skip
    a.settings.set("sorter.ai", False)
    ws = Path(a.workspace)
    for d in ("linear-algebra", "topology", "zettel", "inbox"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(a, "notify", lambda text, **kw: None)
    a.modules["sorter"].start()
    yield a
    a.close()


def test_the_class_is_a_hint_for_the_sorter_never_a_move(sapp):
    import os
    from pathlib import Path

    from kurooto.core import sorting

    t = dt.datetime.now() - dt.timedelta(minutes=30)
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][t.weekday()]
    start, end = (t - dt.timedelta(minutes=40)), (t - dt.timedelta(minutes=10))
    if start.date() != t.date():
        pytest.skip("too close to midnight for a class today")
    sapp.settings.set("subjects.timetable", [{"day": day, "start": f"{start:%H:%M}", "end": f"{end:%H:%M}",
                                              "subject": "topology"}])  # fmt: skip
    f = Path(sapp.workspace) / "inbox" / "scribbles.md"
    f.write_text("# scribbles\n\nopen covers and some thoughts about lunch\n", encoding="utf-8")
    os.utime(f, (t.timestamp(), t.timestamp()))
    s = sapp.modules["sorter"]
    assert sorting.class_folder(sapp, "inbox/scribbles.md") is None  # off by default
    s.run(force=True)
    before = sorting.load(sapp)["waiting"]["inbox/scribbles.md"]["guesses"]
    assert "topology" not in before[:1]
    sapp.settings.set("sorter.by_class", True)
    assert sorting.class_folder(sapp, "inbox/scribbles.md") == "topology"
    assert "a class whose folder is topology" in sorting.prompt(sapp, "inbox/scribbles.md", "x", "topology")
    s.run(force=True)
    assert f.exists()  # a hint only: still waiting
    assert sorting.load(sapp)["waiting"]["inbox/scribbles.md"]["guesses"][0] == "topology"


# ---------------------------------------------------------------- L64: the frontier as a tiebreak, never ahead
def test_link_cards_on_the_frontier_come_first_only_among_the_same_due_day(app, monkeypatch):
    from kurooto.mind import frontier

    links = app.modules["quiz"].links
    old, today = "2026-01-01", dt.date.today().isoformat()

    def card(a, b, due):
        h = [{"date": old, "q": 4}]
        return {"a": a, "b": b, "due": due, "reps": 1, "history": h, "text": f"{a} and {b}?"}

    st = {
        "items": {
            "c1": card("x/one", "x/two", old),  # overdue
            "c2": card("x/three", "x/four", today),
            "c3": card("x/lte", "x/five", today),
        }
    }
    monkeypatch.setattr(frontier, "grades", lambda a: {"x/lte": frontier.FRONTIER})
    assert links.next_card(st)[0] == "c1"
    st["items"].pop("c1")
    assert links.next_card(st)[0] == "c2"  # off by default: as before
    app.settings.set("quiz.links_frontier", True)
    assert links.next_card(st)[0] == "c3"
    st["items"]["c1"] = card("x/one", "x/two", old)
    assert links.next_card(st)[0] == "c1"  # never ahead of an overdue card


def test_the_study_push_names_the_next_concept_only_when_chosen(app, notes, monkeypatch):
    from kurooto.mind import frontier, study_push

    monkeypatch.setattr(frontier, "grades", lambda a: {"zettel/lte": frontier.FRONTIER})
    assert study_push.next_concepts(app, "zettel") == []
    app.settings.set("mind.study_push.frontier", True)
    assert study_push.next_concepts(app, "zettel") == ["Local Thermodynamic Equilibrium"]
    due = (dt.datetime.now() + dt.timedelta(days=3)).isoformat()
    r = {"subject": "zettel", "due": due, "logged": 0, "cards": None, "next": ["Local Thermodynamic Equilibrium"]}
    assert "Next up there: Local Thermodynamic Equilibrium." in study_push.line(app, r, None, 25)


# ------------------------------------------------------------- L92: what it set up, offered for your profile
def test_inferred_projects_and_classes_are_offered_with_a_role_never_a_name(env):
    import time as _time

    from kurooto.modules import fold

    app = env.app
    env.on("dreaming")
    app.settings.set("dreaming.fold_ai", "off")
    items = [
        {"kind": "project", "undone": False, "at": _time.time(), "line": "Started the project note x",
         "undo": {"file": str(app.workspace / "research" / "glacier-flow" / "index.md"),
                  "with": "With: Prof Lena Ortiz (supervisor)"}},
        {"kind": "project", "undone": False, "at": _time.time(), "line": "Started",
         "undo": {"file": str(app.workspace / "research" / "project-with-prof-ken-ito" / "index.md"),
                  "with": "With: Dr Ken Ito (advisor)"}},
        {"kind": "project", "undone": True, "at": _time.time(), "line": "x", "undo": {"file": "a/b/index.md"}},
    ]  # fmt: skip
    jsave(app.paths.state / "inferred.json", {"items": items, "seen": []})
    lines = [x for x, _ in fold.inferred(app)]
    assert lines == ["I have a project with my supervisor on glacier flow", "I have a project with my advisor"]
    assert not any("Ortiz" in x or "Ito" in x for x in lines)
    fold.scan(app, ai=False)
    text, buttons = fold.section(app, send=False)
    assert text.count("what it set up from what you said") == 1  # its own cap (dreaming.fold_inferred_max, 1)
    app.settings.set("dreaming.fold_inferred", False)
    assert fold.inferred(app) == []


# ---------------------------------------------------------------- L93: a remembered time rule, as a setting
def test_a_remembered_time_rule_is_offered_as_its_setting_with_undo(env):
    from kurooto.modules import remember

    app = env.app
    env.on("remember")
    rules = remember.time_rules(app, "I hate calls before 8")
    assert rules == [
        {"key": "availability.night.to", "value": "08:00", "said": "no calls before 08:00 (night hours end)"}
    ]
    assert remember.time_rules(app, "don't call me after 10")[0]["value"] == "22:00"
    assert remember.time_rules(app, "I'm usually up from 8 to 11pm")[0] == {
        "key": "startby.window",
        "value": "08:00-23:00",
        "said": "plan work between 08:00 and 23:00",
    }
    assert remember.time_rules(app, "I like short answers") == []
    before = app.settings.get("availability.night.to")
    env.say("remember that I hate calls before 8")
    offer = [p for m, p in env.fake.sent if m == "sendMessage" and "Shall I set that too" in str(p.get("text"))]
    assert offer and app.settings.get("availability.night.to") == before  # nothing set without the tap
    set_it = next(b["callback_data"] for row in offer[-1]["reply_markup"]["inline_keyboard"] for b in row
                  if b["text"] == "Set it")  # fmt: skip
    assert env.press(set_it).startswith("Set: no calls before 08:00")
    assert app.settings.get("availability.night.to") == "08:00"
    undo = [p for m, p in env.fake.sent if m == "sendMessage" and str(p.get("text")).startswith("Done: no calls")]
    env.press(undo[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"])
    assert app.settings.get("availability.night.to") == before
    app.settings.set("remember.offer_settings", False)
    n = len(env.fake.sent)
    env.say("remember that never call me after 11pm")
    assert not any("Shall I set" in str(p.get("text")) for m, p in env.fake.sent[n:] if m == "sendMessage")
