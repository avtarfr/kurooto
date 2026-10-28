"""0.9.0, the links release, batch 2 (notes and knowledge): the links between the Quiz, revision, doubts, the concept
graph, Brain's model of what you know and the notes tools. Fake notes and fake AIs throughout; nothing leaves."""

from __future__ import annotations

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
    iid = quiz.add_card("physics", "Why does the source function equal the Planck function there?", concept="zettel/lte")
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
