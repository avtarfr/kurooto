"""Link recall cards: the concept graph's links become quiz cards, answered by reply, revealed with the link's reason
and where to read (book pages, your notes, Classroom files), graded with the quiz's buttons and spacing; by themselves
only with quiz.links on, up to the day's number, never in a class."""

import datetime as dt
import io
import json

import pytest

from kurooto.core import layout
from kurooto.core.state import jload, jsave
from kurooto.modules import quiz_links

SUBJ = "stochastic-calculus"
NOON = dt.datetime.combine(dt.date.today(), dt.time(12, 0))


@pytest.fixture
def cards(env, monkeypatch):
    app = env.app
    app.settings.set("notes.layout", "zettelkasten")
    monkeypatch.setattr(quiz_links, "now", lambda: NOON)
    ws = app.workspace
    (ws / "zettel").mkdir(parents=True)
    (ws / "zettel" / "itos-lemma.md").write_text(
        "# Itô's lemma\n\nThe chain rule for diffusions.\n\n## Links\n"
        "- used-in:: [[zettel/fokker-planck]] — its generator gives the drift and diffusion terms of the equation\n"
        "- needs:: [[zettel/nowhere]] — a link to a note that isn't there is no card\n",
        encoding="utf-8",
    )
    (ws / "zettel" / "fokker-planck.md").write_text("# Fokker-Planck\n\nHow a density evolves.\n", encoding="utf-8")
    lecture = layout.path(app, "lecture", subject=SUBJ, date="2026-10-20", slug="diffusions")
    lecture.parent.mkdir(parents=True)
    lecture.write_text("# Diffusions\n\nFokker Planck from the lemma, done in class.\n", encoding="utf-8")
    files = layout.file_dir(app, "classroom", subject=SUBJ)
    files.mkdir(parents=True, exist_ok=True)
    (files / "2026-10-21-sheet-4.pdf.txt").write_text("Exercise: derive Fokker Planck with the lemma.", "utf-8")
    seen = {
        "zettel/itos-lemma": [
            {"book": f"{SUBJ}/primer", "note": "x", "title": "Diffusions Primer", "batch": "40-52", "pages": [40, 52]}
        ]
    }
    jsave(app.paths.state / "integrate" / "seen.json", seen)
    env.on("quiz")
    return env, app.modules["quiz"].links


def last(env):
    return [p for m, p in env.fake.sent if m == "sendMessage"][-1]


def test_a_card_answered_by_reply_shows_the_reason_and_where_to_read_then_grades(cards):
    env, lc = cards
    assert env.say("/card") is not None
    asked = last(env)["text"]
    assert asked.startswith("Link card (stochastic-calculus):\nHow is Itô's lemma used in Fokker-Planck?"), asked
    env.reply_to_last("the generator of the diffusion is the operator whose adjoint evolves the density")
    shown = last(env)
    assert "its generator gives the drift and diffusion terms of the equation." in shown["text"]
    where = shown["text"].split("Where to read: ")[1]
    assert where.startswith(
        "Diffusions Primer pp. 40–52; your notes: [[sources/stochastic-calculus/2026-10-20-diffusions]]"
    )
    assert "Classroom file: 2026-10-21-sheet-4.pdf" in where
    labels = [b["text"] for b in shown["reply_markup"]["inline_keyboard"][0]]
    assert labels == ["Forgot", "Hard", "Good", "Easy"]
    out = env.press(shown["reply_markup"]["inline_keyboard"][0][0]["callback_data"])
    assert out.startswith("Grade 0/5. Next time:") and out.endswith("Worth a read: Diffusions Primer pp. 40–52.")
    st = jload(env.app.paths.state / "quiz" / "_links.json", {})
    (card,) = st["items"].values()  # the dangling link made no card
    assert card["history"][-1]["q"] == 0 and card["section"] == "Links" and card["subject"] == SUBJ
    assert env.say("/card") == "No link card is due right now."
    assert env.say("/cards").startswith("Link cards: 1 (1 seen, 0 due today).\nAnswered: 1 in all")


def test_on_their_own_only_when_on_never_in_class_and_up_to_the_days_number(cards):
    env, lc = cards
    assert lc.tick() == "off"
    assert env.say("/cards on").startswith("Link cards are on: up to 3 a day")
    assert env.app.scheduler.get("quiz:links") is not None
    env.app.availability.blockers["subjects:class"] = lambda t: ("in Topology", t + dt.timedelta(hours=1))
    assert lc.tick() == "held (in Topology)"
    later = env.app.scheduler.get("quiz:links:later")
    assert later is not None and later.action == "quiz.links_later"
    del env.app.availability.blockers["subjects:class"]
    assert lc.tick() == "sent"
    assert last(env)["text"].startswith("Link card")
    assert lc.tick() == "waiting"  # the last one isn't answered
    env.app.settings.set("quiz.links_per_day", 1)
    env.reply_to_last("drift and diffusion")
    assert lc.tick() == "enough"
    env.app.settings.set("quiz.links_per_day", 50)
    assert lc.per_day() == 5


def test_the_phone_gets_the_grade_buttons_as_their_own_message(cards):
    from kurooto.modules.base import Incoming

    env, lc = cards
    lc.send()
    iid = next(iter(lc.state()["items"]))
    said = []
    out = lc.answer(Incoming("drift", via="app", respond=lambda t, buttons=None: said.append(t)), iid)
    assert out.startswith("The answer and the grade buttons") and not said
    assert [b["text"] for b in last(env)["reply_markup"]["inline_keyboard"][0]][0] == "Forgot"


def test_the_local_check_only_with_a_local_model_and_only_when_asked(cards, monkeypatch):
    env, lc = cards
    it = next(iter(lc.state()["items"].values()))
    assert lc.check(it, "drift") == ""  # off by default
    env.app.settings.set("quiz.links_check", True)
    assert lc.check(it, "drift") == ""  # Local AI models is off
    lm = env.app.modules["local_models"]
    env.app.settings.set("modules.enabled", [*env.app.settings.get("modules.enabled"), "local_models"])
    asked = []

    def api(path, body=None, timeout=10):
        asked.append((path, body))
        return io.BytesIO(json.dumps({"response": "Partly: the drift is right,\n the diffusion is missing."}).encode())

    monkeypatch.setattr(lm, "wanted", lambda: [{"key": "helper", "tag": "tiny:1b"}])
    monkeypatch.setattr(lm, "api", api)
    assert lc.check(it, "drift") == "Partly: the drift is right, the diffusion is missing."
    assert asked[0][0] == "/api/generate" and asked[0][1]["model"] == "tiny:1b"
