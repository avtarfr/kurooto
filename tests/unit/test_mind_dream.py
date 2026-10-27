"""Brain, 0.8.14 group C: dreaming about the day (frontier cards, how-to-help lessons, the voice line), the frontier
score add-ons use, one worry in place of five nudges, and check-ins that come early on a surprise."""

import datetime as dt
import json
import os
import time
from pathlib import Path

import pytest

from kurooto import mind
from kurooto.core import conceptgraph
from kurooto.core.clock import now
from kurooto.core.state import jsave
from kurooto.mind import dream, forecast, frontier, study_push
from kurooto.mind import pest as mpest
from kurooto.mind.tom import knowledge


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind", "quiz", "subjects", "deadlines", "reminders", "checkins", "dreaming"])
    a.settings.set("mind.tom.on", True)
    a.settings.set("availability.night.enabled", False)
    a.settings.set("subjects.list", [{"slug": "measure-theory", "name": "Measure Theory", "aliases": ["mt"]}])
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)) or "m1")
    frontier.forget_cache()
    yield a
    frontier.forget_cache()
    mind.forget_client(a)
    a.close()


def note(root: Path, slug: str, title: str, links=(), body="") -> conceptgraph.Note:
    p = root / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"# {title}\n{body}\n", encoding="utf-8")
    return conceptgraph.Note(slug=slug, path=p, title=title, links=set(links), hash=slug + "1", summary=body, head=body)


@pytest.fixture
def notes(app, monkeypatch):
    root = Path(app.workspace)
    ns = {
        "measure-theory/fubini": note(
            root,
            "measure-theory/fubini",
            "Fubini theorem",
            ["measure-theory/product"],
            "Swap the order of integration for integrable functions.",
        ),  # fmt: skip
        "measure-theory/product": note(root, "measure-theory/product", "Product measure"),
        "measure-theory/radon": note(root, "measure-theory/radon", "Radon Nikodym", ["measure-theory/abs"]),
        "measure-theory/abs": note(root, "measure-theory/abs", "Absolute continuity"),
    }
    monkeypatch.setattr(knowledge, "concepts", lambda a: dict(ns))
    return ns


def solid(app, slug):
    for _ in range(6):
        knowledge.observe(app, slug, True, 1.0, "quiz:x")


# ------------------------------------------------------------------------------------------------- frontier
def test_frontier_score(app, notes):
    solid(app, "measure-theory/product")
    knowledge.observe(app, "measure-theory/radon", False, 0.2, "asked:1")  # started, but its prerequisite isn't solid
    frontier.forget_cache()
    assert frontier.score(app, "Today: when does Fubini theorem let me swap integrals?") == frontier.FRONTIER
    assert frontier.score(app, "the product measure on a rectangle") == frontier.SOLID
    assert frontier.score(app, "Radon Nikodym derivative") == frontier.STARTED
    assert frontier.score(app, "Absolute continuity") == frontier.UNKNOWN  # nothing seen, too far ahead
    assert frontier.score(app, "nothing that names a concept") == 0.0 and frontier.score(app, "") == 0.0
    app.settings.set("mind.tom.on", False)
    assert frontier.score(app, "Fubini theorem") == 0.0  # the model off: no score


def test_frontier_score_is_quick_from_the_cache(app, notes):
    calls = []
    orig = knowledge.concepts
    knowledge_concepts = lambda a: calls.append(1) or orig(a)  # noqa: E731
    import kurooto.mind.tom.knowledge as kmod

    kmod.concepts = knowledge_concepts
    try:
        for _ in range(50):
            frontier.score(app, "Fubini theorem")
    finally:
        kmod.concepts = orig
    assert len(calls) == 1  # the notes are read once per CACHE_S, not per call


# ----------------------------------------------------------------------------------------------------- cards
def test_dream_cards_from_the_days_study_kept_by_a_tap(app, notes):
    solid(app, "measure-theory/product")
    day = dream.the_day()
    for n in notes.values():  # only Fubini's note was changed that day
        t = time.mktime((day - dt.timedelta(days=3)).timetuple())
        os.utime(n.path, (t, t))
    t = time.mktime(dt.datetime.combine(day, dt.time(15)).timetuple())
    os.utime(notes["measure-theory/fubini"].path, (t, t))
    assert dream.make_cards(app, day, use_model=False) == 1
    assert dream.make_cards(app, day, use_model=False) == 0  # carded once
    text, buttons = dream.section(app, send=True)
    assert "What is Fubini theorem" in text and "Keep" in str(buttons)
    ref = next(b[1] for row in buttons for b in row if b[1].endswith(":keep") and b[1].startswith("mdr:c"))
    said = dream.button(app, ref.split(":")[1], "keep")
    assert said.startswith("Added to your quiz cards")
    quiz = app.modules["quiz"]
    assert "measure-theory" in quiz.card_subjects()
    st = quiz.load("measure-theory")
    (iid, it), = st["items"].items()  # fmt: skip
    assert it["by"] == "kurooto" and it["concept"] == "measure-theory/fubini" and it["answer"]
    assert it["due"] == (now().date() + dt.timedelta(days=1)).isoformat()  # first due about a day after
    assert dream.button(app, ref.split(":")[1], "keep").startswith("That's settled")
    undo = app.sent[-1][1]["buttons"][0][0][1]
    assert dream.button(app, undo.split(":")[1], "undo") == "Taken out of your quiz cards."
    assert not quiz.load("measure-theory")["items"] and not quiz.card_subjects()


def test_cards_are_let_go_after_two_mornings_and_need_the_switch(app, notes):
    st = dream._load(app)
    card = {"ref": "r1", "slug": "measure-theory/fubini", "title": "Fubini theorem", "q": "What is it?", "a": "x"}
    st["cards"].append({**card, "subject": "measure-theory", "made": now().date().isoformat(), "shown": 0})
    dream._save(app, st)
    assert dream.section(app, send=True)[0] and dream.section(app, send=True)[0]
    assert dream.section(app, send=True)[0] == ""  # shown twice without a tap: let go
    assert dream.make_cards(app, dream.the_day()) == 0  # and not carded again
    app.settings.set("mind.dream.cards", False)
    assert dream.make_cards(app, dream.the_day()) == 0


def test_a_card_from_the_local_model(app, notes, monkeypatch):
    from kurooto.mind import tone

    monkeypatch.setattr(tone, "model", lambda a: "helper")

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"response": "When may you swap the order of integration? :: For integrable f."}).encode()

    class LM:
        def api(self, path, body, timeout=60):
            assert "Fubini" in body["prompt"]
            return Resp()

    monkeypatch.setitem(app.modules, "local_models", LM())
    q, a, by_model = dream.write_card(app, notes["measure-theory/fubini"])
    assert by_model and q.endswith("?") and a == "For integrable f."


# --------------------------------------------------------------------------------------------------- lessons
def test_lessons_from_the_days_outcomes(app):
    day = now().date()
    t = time.time()
    jsave(app.paths.state / mpest.FILE, {"pending": [
        {"kind": "nudge", "at": t, "cell": "nudge|evening|free", "done": "ignored"},
        {"kind": "nudge", "at": t, "cell": "nudge|evening|free", "done": "less"},
        {"kind": "finding", "at": t, "cell": "finding|morning|free", "done": "welcome"},
    ]})  # fmt: skip
    app.events.emit("sorter_undone")
    app.events.emit("sorter_undone")
    out = dream.outcomes(app, day)
    lines = [x["line"] for x in dream.distil(out)]
    assert (
        "Fewer nudges in the evening" in lines and "Ask before sorting your files changes something by itself" in lines
    )
    assert dream.propose_lessons(app, day) == 2 and dream.propose_lessons(app, day) == 0
    text, buttons = dream.section(app, send=True)
    assert "how-to-help-me note" in text and "Fewer nudges in the evening" in text
    ref = next(b[1] for row in buttons for b in row if b[1].startswith("mdr:l") and b[1].endswith(":keep"))
    assert dream.button(app, ref.split(":")[1], "keep").startswith("Added to your how-to-help-me note")
    from kurooto.modules.remember import help_file

    assert "(from the day's outcomes, " in help_file(app).read_text(encoding="utf-8")
    undo = app.sent[-1][1]["buttons"][0][0][1]
    assert dream.button(app, undo.split(":")[1], "undo") == "Taken out of your how-to-help-me note."
    app.settings.set("mind.dream.lessons", False)
    assert dream.propose_lessons(app, day) == 0


# ------------------------------------------------------------------------------------------------ the voice line
def test_voice_line_counts_and_a_pattern_never_words(app):
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "voice"])
    app.settings.set("voice.listen.learn_nightly", True)
    y = (now().date() - dt.timedelta(days=1)).isoformat()
    rows = [{"rule": "its name", "where": "last", "label": 0, "day": y}] * 3
    rows += [{"rule": "its name", "where": "first", "label": 1, "day": y}] * 5
    rows += [{"rule": "its name", "where": "last", "label": 0, "day": "2000-01-01"}]
    f = app.paths.state / "voice" / "gate-turns.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    line = dream.voice_line(app)
    assert line == (
        "Voice learned from 8 of yesterday's turns (3 told off); it woke to your name at the end of a sentence 3 times."
    )
    assert dream.section(app, send=False)[0].startswith("Voice learned from 8")
    app.settings.set("mind.dream.voice", False)
    assert dream.voice_line(app) == ""


def test_the_morning_message_carries_the_dream_section(app):
    st = dream._load(app)
    st["lessons"].append({"ref": "q1", "h": "h1", "line": "Fewer nudges in the evening", "why": "2 went unanswered",
                          "day": now().date().isoformat(), "kind": "pest", "shown": 0})  # fmt: skip
    dream._save(app, st)
    text = app.modules["dreaming"].report(send=True)
    assert "Fewer nudges in the evening" in text
    assert any("mdr:lq1:keep" in str(kw.get("buttons")) for _t, kw in app.sent)
    app.settings.set("modules.enabled", [m for m in app.settings.get("modules.enabled") if m != "mind"])
    assert "Fewer nudges" not in (app.modules["dreaming"].report(send=False) or "")  # Brain off: as 0.8.13


def test_the_night_defers_cards_while_awake_and_writes_them_at_the_last_try(app, notes, monkeypatch):
    monkeypatch.setattr(dream, "_gate", lambda a: (False, "awake"))
    made = []
    monkeypatch.setattr(dream, "make_cards", lambda a, d, use_model=True: made.append(use_model) or 0)
    monkeypatch.setattr(dream, "now", lambda: dt.datetime.combine(dt.date.today(), dt.time(2, 15)))
    did = dream.nightly(app)
    assert did["deferred"] == "awake" and made == []
    monkeypatch.setattr(dream, "now", lambda: dt.datetime.combine(dt.date.today(), dt.time(6, 15)))
    dream.nightly(app)
    assert made == [False]  # the last try: written without the model
    dream.nightly(app)
    assert made == [False]  # once a night


def test_recall_on_its_cards_next_to_his_own(app):
    qd = app.paths.state / "quiz"
    qd.mkdir(parents=True, exist_ok=True)
    jsave(qd / "measure-theory.json", {"items": {
        "a": {"text": "mine", "history": [{"q": 4}, {"q": 1}]},
        "k": {"text": "its", "by": "kurooto", "history": [{"q": 5}]},
    }})  # fmt: skip
    assert dream.recall(app) == {"mine": [1, 2], "kurooto": [1, 1]}
    assert any("recalled 1/1 (100%) on them, 1/2 (50%) on your own" in x for x in dream.mind_lines(app))


# --------------------------------------------------------------------------------------------- one worry
def _deadline(app, title, hours, **kw):
    dl = app.modules["deadlines"]
    dl.add(title, now() + dt.timedelta(hours=hours), **kw)
    return next(i for i, it in dl.items().items() if it["title"] == title)


def test_one_morning_line_folds_the_subjects_nudges(app):
    i = _deadline(app, "Measure Theory problem set", 60, subject="measure-theory")
    text = study_push.push(app)
    assert text.startswith("Uneasy about Measure Theory: due ") and "min logged this week" in text
    assert "cards due" in text and text.rstrip().endswith("?")
    msg, kw = app.sent[-1]
    assert kw["why"] == "mind.study_push" and [b[0] for b in kw["buttons"][0]] == ["Yes", "Later"]
    assert study_push.push(app) is None  # once a day
    assert study_push.folded(app, "measure-theory") and not study_push.folded(app, "topology")
    dl = app.modules["deadlines"]
    n = len(app.sent)
    dl._chase("ping", i, dl.items()[i], 20)
    assert len(app.sent) == n  # the day-before reminder is folded
    dl._chase("urgent", i, dl.items()[i], 5)
    assert len(app.sent) == n + 1  # the six-hour one never is
    day = now().date().isoformat()
    said = study_push.button(app, day, "yes")
    assert said.startswith("Done: I'll remind you at ")
    assert study_push.button(app, day, "later") == "Already answered."


def test_no_line_when_off_or_nothing_close(app):
    _deadline(app, "Measure Theory essay", 24 * 6.5, subject="measure-theory")
    assert study_push.pick(app) is None  # six and a half days out: not uneasy enough
    _deadline(app, "Measure Theory quiz prep", 3, subject="measure-theory")
    assert study_push.pick(app) is None  # inside the urgent window: its own reminders, never folded
    _deadline(app, "Measure Theory sheet", 30, subject="measure-theory")
    app.settings.set("mind.study_push.on", False)
    assert study_push.push(app) is None and not study_push.folded(app, "measure-theory")


def test_start_by_and_exam_practice_fold_too(app, monkeypatch):
    jsave(app.paths.state / study_push.FILE, {"day": now().date().isoformat(), "subject": "measure-theory"})
    quiz = app.modules["quiz"]
    assert quiz._folded("measure-theory") and not quiz._folded("topology")
    due = (now() + dt.timedelta(days=5)).isoformat()
    exam = {"id": "e1", "subject": "measure-theory", "title": "MT midsem", "due": due, "when": "Fri"}
    monkeypatch.setattr(quiz, "exams", lambda: [exam])
    monkeypatch.setattr(quiz, "due_count", lambda s: 4)
    quiz._exam_daily({})
    assert not app.sent  # exam mode's daily practice check-in is folded in
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "startby"])
    sb = app.modules["startby"]
    assert sb._folded({"subject": "measure-theory"}) and not sb._folded({"subject": "x"})


# ------------------------------------------------------------------------------------------ surprise check-ins
def _plan_checkin(app, name="evening", hhmm=None):
    ck = app.modules["checkins"]
    day = ck.day_of()
    if (now() + dt.timedelta(minutes=20)).date() != now().date():
        pytest.skip("too close to midnight for a check-in later today")
    t = hhmm or (now() + dt.timedelta(minutes=10)).strftime("%H:%M")
    jsave(ck._file(day), {name: {"time": t, "status": "planned"}})
    return ck, day


def test_a_deadline_moved_twice_brings_the_next_checkin_early(app):
    ck, day = _plan_checkin(app)
    i = _deadline(app, "Measure Theory sheet", 48, subject="measure-theory")
    dl = app.modules["deadlines"]
    dl.move(i, now() + dt.timedelta(days=3))
    assert forecast.surprise(app) is None
    dl.move(i, now() + dt.timedelta(days=4))
    assert forecast.surprise(app) == "moved_twice"
    assert forecast.surprise_tick(app) == "moved_twice"
    assert ck.today(day)["evening"]["status"] == "asked"
    assert any(t.startswith("Evening check-in: A bit earlier than usual.") for t, _ in app.sent)
    assert forecast.surprise_tick(app) is None  # once a day


def test_no_surprise_checkin_in_class_or_asleep_or_off(app, monkeypatch):
    ck, day = _plan_checkin(app)
    monkeypatch.setattr(forecast, "surprise", lambda a, t=None: "moved_twice")
    app.availability.blockers["subjects:class"] = lambda t: ("in class", t + dt.timedelta(minutes=30))
    assert forecast.surprise_tick(app) is None
    del app.availability.blockers["subjects:class"]
    monkeypatch.setattr(forecast, "_asleep", lambda a, t: True)
    assert forecast.surprise_tick(app) is None
    monkeypatch.setattr(forecast, "_asleep", lambda a, t: False)
    app.settings.set("mind.checkins.surprise", False)
    assert forecast.surprise_tick(app) is None and ck.today(day)["evening"]["status"] == "planned"


def test_late_wake_needs_the_phone_up_and_no_sign_with_kurooto(app, monkeypatch):
    t = dt.datetime.combine(now().date(), dt.time(11, 0))
    monkeypatch.setattr(forecast, "frozen", lambda a, d: {"params": {"wake_min": [7 * 60.0, 20.0]}})
    monkeypatch.setattr(forecast, "_phone_up", lambda a, since: True)
    monkeypatch.setattr(app.events, "tail", lambda n=50, kinds=None: [])
    assert forecast.surprise(app, t) == "late_wake"  # 4 h past 07:00, phone up, nothing with Kurooto
    assert forecast.surprise(app, dt.datetime.combine(now().date(), dt.time(8, 30))) is None  # not 2 h yet
    monkeypatch.setattr(forecast, "_phone_up", lambda a, since: False)
    assert forecast.surprise(app, t) is None  # no sign he's up: no surprise


def test_one_switch_turns_all_of_its_dreaming_off(app):
    st = dream._load(app)
    les = {"ref": "q1", "h": "h1", "line": "Fewer nudges", "why": "2", "day": now().date().isoformat(), "shown": 0}
    st["lessons"].append(les)
    dream._save(app, st)
    assert dream.section(app, send=False)[0]
    app.settings.set("mind.dream.on", False)
    assert dream.section(app, send=False)[0] == "" and not dream.cards_on(app) and not dream.voice_on(app)
    assert dream.nightly(app) == {}
