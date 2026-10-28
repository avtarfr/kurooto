"""0.9.0, the links release, batch 2: papers you add to Zotero read into the concept graph after the books (L71),
and the courses with an exam coming up read first (L74). A fake AI; the queue and its order are real."""

from __future__ import annotations

import datetime as dt

from tests.unit.test_integrate import world  # noqa: F401 (a fixture: Books and the concept graph, a fake AI)

# ---------------------------------------------------------- L71 / L74: papers into the graph; exam courses first

PAPER = {
    "id": "arxiv:2601.00001",
    "title": "Reverse-mode automatic differentiation for sparse networks",
    "authors": ["A. Writer", "B. Coder"],
    "summary": "We show how reverse-mode automatic differentiation computes gradients of sparse networks. " * 6,
    "link": "https://arxiv.org/abs/2601.00001",
}


def test_papers_are_read_only_when_chosen_and_after_the_books(world):  # noqa: F811
    env = world
    ig = env.integrate
    assert ig.take_paper(PAPER) is None  # "papers" isn't in integrate.sources by default
    env.app.settings.set("integrate.sources", ["books", "classroom", "reference", "papers"])
    key = ig.take_paper(PAPER)
    assert key and key.startswith("papers:") and ig.take_paper(PAPER) is None  # read once
    ready = ig.ready_batches()
    kinds = [ig.source_of(b) for b, _ in ready]
    assert kinds[-1] == "papers" and "books" in kinds and kinds.index("books") < kinds.index("papers")
    toggles = {t["id"] for t in ig.card()["toggles"]}
    assert "source:papers" in toggles


def test_courses_with_an_exam_coming_up_are_read_first_when_chosen(world, monkeypatch):  # noqa: F811
    env = world
    ig = env.integrate
    env.app.settings.set("integrate.sources", ["books", "classroom", "reference"])
    long = "Gradient checks compare an analytic gradient with a finite difference, entry by entry. " * 30
    a = ig.queue_item("classroom", long, "topology", "Topology handout", "topology/handout", date="2026-10-20")
    other = long.replace("Gradient checks", "Jacobian checks")
    b = ig.queue_item("classroom", other, "deep-learning", "DL slides", "dl/slides", date="2026-10-01")
    assert a and b
    order = [it["subject"] for it in ig.queued_items()]
    assert order == ["topology", "deep-learning"]  # newest first, as before
    es = env.app.modules["exam_season"]
    monkeypatch.setattr(env.app, "is_on", lambda m, on=env.app.is_on: m == "exam_season" or on(m))
    soon = (dt.datetime.now() + dt.timedelta(days=3)).date()
    monkeypatch.setattr(es, "exams", lambda: [{"subject": "deep-learning", "day": soon}])
    assert [it["subject"] for it in ig.queued_items()] == order  # off by default
    env.app.settings.set("exam_season.graph_first", True)
    assert [it["subject"] for it in ig.queued_items()] == ["deep-learning", "topology"]  # moved up, none dropped


# -------------------------------------------------------------------- L19: the night's reading yields to a turn
def test_the_graph_holds_a_batch_only_while_a_voice_turn_lasts(world, monkeypatch):  # noqa: F811
    from kurooto.core import power

    env = world
    ig = env.integrate
    monkeypatch.setattr(power, "owner_turn", lambda app: "a voice turn")
    monkeypatch.setattr(ig, "submit_batch", lambda b, bt: "job")
    assert ig.tick().get("submitted") == 1  # off by default: as before
    env.app.settings.set("integrate.yield_to_owner", True)
    out = ig.tick()
    assert out.get("held") == "a voice turn" and env.app.scheduler.get("integrate:soon")
    monkeypatch.setattr(power, "owner_turn", lambda app: "")
    assert ig.tick().get("submitted") == 1  # the turn ended: on it goes


def test_waiting_for_the_owner_counts_the_wait(monkeypatch):
    from kurooto.core import power

    turns = iter(["a voice turn", "a voice turn", ""])
    clock = {"t": 0.0}
    monkeypatch.setattr(power, "owner_turn", lambda app: next(turns))
    tick = lambda s: clock.__setitem__("t", clock["t"] + s)  # noqa: E731
    waited = power.wait_for_owner(object(), sleep=tick, clock=lambda: clock["t"])
    assert waited == 1.0
