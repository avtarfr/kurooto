"""The NOTES map's mastery rings (L132, 0.9.0, look.notes_mastery): Brain's grade of each concept as a word, from
mind/frontier.py; nothing with the switch or Brain's model of what you know off."""

from __future__ import annotations

from kurooto.web import server  # noqa: F401 (the look.* settings are declared there)
from kurooto.web.api import Api


def test_the_map_gets_grades_as_words(env, monkeypatch):
    from kurooto.mind import frontier

    app = env.app
    assert Api(app).get("notes/mastery") == (200, {"on": False})  # Brain's model of what you know is off
    monkeypatch.setattr(frontier, "grades", lambda a: {"zettel/rank": 1.0, "zettel/span": 0.1, "zettel/x": 0.0})
    code, out = Api(app).get("notes/mastery")
    assert code == 200 and out == {"on": True, "grades": {"zettel/rank": "frontier", "zettel/span": "solid"}}
    app.settings.set("look.notes_mastery", False)
    assert Api(app).get("notes/mastery")[1] == {"on": False}
