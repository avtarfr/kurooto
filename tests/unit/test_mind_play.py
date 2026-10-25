"""Brain, stage 17b: a play budget: capped, pre-registered, paid only for transfer, never shown unprompted."""

import time

import pytest

from kurooto import mind
from kurooto.core import power
from kurooto.mind import log as mlog
from kurooto.mind import play, whitelist
from kurooto.mind import scorekeeper as sk
from kurooto.mind.lab import runner

QS = [{"id": f"explain:c{i}", "kind": "explain", "text": f"explain concept {i}"} for i in range(3)]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    a.settings.set("mind.play.on", True)
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    monkeypatch.setattr(power, "on_ac", lambda: True)
    monkeypatch.setattr(runner, "lid_open", lambda: True)
    monkeypatch.setattr(runner, "hot", lambda: False)
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


class Clock:
    """A clock that moves only when a question is asked: each takes `step` minutes."""

    def __init__(self, step):
        self.t, self.step = 0.0, step

    def __call__(self):
        return self.t

    def ask(self, q):
        self.t += self.step * 60
        return f"an answer to {q['id']}"


def test_play_budget_capped(app):
    clock = Clock(8)
    out = play.run_session(app, asker=clock.ask, clock=clock, questions=QS)
    assert out["ran"] and out["asked"] == 2 and out["minutes"] <= 20  # a third would have run past the 20 minutes
    app.settings.set("mind.play.minutes_per_night", 5)
    clock2 = Clock(4)
    assert (
        play.run_session(app, asker=clock2.ask, clock=clock2, questions=[{**q, "id": q["id"] + "x"} for q in QS])[
            "minutes"
        ]
        <= 8
    )
    app.settings.set("mind.play.minutes_per_night", 60)
    clock3 = Clock(1)
    assert (
        play.run_session(app, asker=clock3.ask, clock=clock3, questions=[{**q, "id": q["id"] + "y"} for q in QS * 3])[
            "asked"
        ]
        == play.PER_SESSION
    )


def test_ac_only_and_off_by_default(app, monkeypatch):
    monkeypatch.setattr(power, "on_ac", lambda: False)
    assert "charger" in play.run_session(app, asker=lambda q: "x", questions=QS)["why"]
    monkeypatch.setattr(power, "on_ac", lambda: True)
    monkeypatch.setattr(runner, "hot", lambda: True)
    assert "hot" in play.run_session(app, asker=lambda q: "x", questions=QS)["why"]
    monkeypatch.setattr(runner, "hot", lambda: False)
    app.settings.set("mind.play.on", False)
    assert not play.run_session(app, asker=lambda q: "x", questions=QS)["ran"]
    assert "off" in play.listing(app)


def test_each_session_is_preregistered(app):
    play.run_session(app, asker=lambda q: "an answer", questions=QS)
    recs = mind.connect(app).log(kinds=["lab_prereg"])
    assert (
        recs and "play" in str(recs[-1].body) and recs[-1].body["n"] == 3
    )  # the hash is in the log before the questions
    assert not play.run_session(app, asker=lambda q: "x", questions=[])["ran"]


def test_play_credit_only_on_transfer(app):
    play.run_session(app, asker=lambda q: "answer", questions=QS[:1])
    oid = next(iter(play._state(app)["outputs"]))  # noqa: SLF001
    assert not play.credit(app, oid, 0.80, 0.80)  # no change
    assert not play.credit(app, oid, 0.80, 0.81)  # too small to be more than noise
    assert not play.credit(app, "nope", 0.5, 0.9)  # not a play output
    assert play._state(app)["credits"] == []  # noqa: SLF001
    assert play.credit(app, oid, 0.80, 0.84)
    assert not play.credit(app, oid, 0.80, 0.95)  # once
    play.run_session(app, asker=lambda q: "answer", questions=[{**QS[1], "id": "explain:other"}])
    other = [k for k in play._state(app)["outputs"] if k != oid][0]  # noqa: SLF001
    assert play.useful(app, other) and not play.useful(app, other)  # what he later finds useful counts too
    assert [c["kind"] for c in play._state(app)["credits"]] == ["harness", "useful"]  # noqa: SLF001
    assert not any("play" in m for m in whitelist.REWARD_SOURCES)  # nothing rewards it


def test_play_outputs_not_unprompted(app):
    play.run_session(app, asker=lambda q: "a secret thought", questions=QS)
    assert app.sent == []  # nothing said during play
    assert play.weekly(app) is False and app.sent == []  # and nothing in the digest while nothing transferred
    assert play.digest_section(app) == ""
    oid = next(iter(play._state(app)["outputs"]))  # noqa: SLF001
    play.credit(app, oid, 0.7, 0.8)
    assert play.weekly(app) is True and len(app.sent) == 1
    text, kw = app.sent[0]
    assert text.startswith("From my play time:") and kw["why"] == "mind.play" and "a secret thought" not in text
    assert play.weekly(app) is False  # told once
    assert "a secret thought" in (app.paths.state / "mind-play" / f"{oid}.md").read_text()  # kept, for when he asks
    assert oid in play.outputs(app)


def test_curiosity_picks_the_frontier_and_skips_what_it_just_played(app, monkeypatch):
    from pathlib import Path

    from kurooto.core import conceptgraph
    from kurooto.mind.tom import knowledge

    notes = {
        "zettel/lte": conceptgraph.Note(slug="zettel/lte", path=Path("x"), title="Local Thermodynamic Equilibrium")
    }
    monkeypatch.setattr(knowledge, "concepts", lambda a: notes)
    monkeypatch.setattr(knowledge, "frontier", lambda a, n=10: ["zettel/lte"])
    qs = play.curiosity(app)
    assert [q["id"] for q in qs] == ["explain:zettel/lte"] and "Local Thermodynamic Equilibrium" in qs[0]["text"]
    play.run_session(app, asker=lambda q: "x", questions=qs)
    assert play.curiosity(app) == []  # not again for two weeks
    st = play._state(app)  # noqa: SLF001
    st["played"]["explain:zettel/lte"] = time.time() - 15 * 86400
    play._save(app, st)  # noqa: SLF001
    assert len(play.curiosity(app)) == 1
