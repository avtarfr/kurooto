"""Brain, stage 15: week-scale plans: goal trees, rollouts, calibration, and what plans may and may not do."""

import datetime as dt
import json
import random

import pytest

from kurooto import mind
from kurooto.mind import log as mlog
from kurooto.mind import plans, whitelist, workspace
from kurooto.mind import scorekeeper as sk
from kurooto.mind.plans import pace, rollout, score, tree


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind", "deadlines"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


TODAY = dt.date(2026, 11, 2)  # a Monday


def node(i, due_days, effort, deps=(), guessed=False, frac=0.0):
    return tree.Node(
        i,
        i,
        "task",
        dt.datetime.combine(TODAY + dt.timedelta(days=due_days), dt.time(23, 59)),
        effort,
        list(deps),
        frac,
        "deadline",
        guessed,
    )


FLAT = {wd: [4.0, 4.0, 4.0] for wd in range(7)}


def put_deadlines(app, items):
    app.modules["deadlines"].file.write_text(json.dumps(items))


def future(days):
    return (dt.datetime.now() + dt.timedelta(days=days)).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------------------------------- trees
def test_tree_from_deadlines_and_milestones(app, monkeypatch):
    put_deadlines(
        app,
        {
            "e1": {"title": "Atmosphere: Quiz 2", "kind": "exam", "due": future(3), "status": "open"},
            "t1": {
                "title": "Problem set 4",
                "kind": "assignment",
                "due": future(6),
                "status": "open",
                "parts": 4,
                "parts_done": 1,
            },
            "t2": {"title": "Old one", "kind": "assignment", "due": future(2), "status": "done"},
            "t3": {
                "title": "Fully done",
                "kind": "assignment",
                "due": future(5),
                "status": "open",
                "parts": 2,
                "parts_done": 2,
            },
        },
    )
    from kurooto.core import repoproject

    monkeypatch.setattr(
        repoproject,
        "records",
        lambda a: {
            "github.com/me/glacier": {
                "key": "github.com/me/glacier",
                "milestones": [
                    {"title": "Methods draft", "due": future(14)[:10], "effort_h": 10},
                    {"title": "no date"},
                ],
            }
        },
    )
    from kurooto.mind.tom import goals

    goals.stated(app, "finish reading the survey paper", future(8))
    nodes = {n.id.split(":")[0] + ":" + n.title: n for n in tree.build(app)}
    titles = {n.title for n in nodes.values()}
    assert titles == {
        "Atmosphere: Quiz 2",
        "Problem set 4",
        "Methods draft",
        "finish reading the survey paper",
    }  # done ones and undated drop out
    ps = next(n for n in nodes.values() if n.title == "Problem set 4")
    assert ps.done_frac == 0.25 and ps.left_h < ps.effort_h and ps.kind == "task"
    assert next(n for n in nodes.values() if n.title == "Atmosphere: Quiz 2").kind == "milestone"
    md = next(n for n in nodes.values() if n.title == "Methods draft")
    assert md.source == "repo" and md.effort_h == 10 and not md.guessed
    assert next(n for n in nodes.values() if n.source == "goal").guessed
    assert tree.set_effort(app, ps.id, 7.5) and next(n for n in tree.build(app) if n.id == ps.id).effort_h == 7.5
    assert not next(n for n in tree.build(app) if n.id == ps.id).guessed  # yours now
    assert not tree.set_effort(app, "bad id!", 3) and not tree.set_effort(app, ps.id, 0)
    assert [n.due for n in tree.build(app)] == sorted(n.due for n in tree.build(app))


# --------------------------------------------------------------------------------------------------- pace
def test_pace_pulls_toward_a_prior_and_draws_sensibly(app):
    s = pace.samples(app, TODAY)
    assert all(len(v) == pace.PRIOR_N and set(v) == {pace.PRIOR_H} for v in s.values())  # nothing recorded: the prior
    rng = random.Random(1)  # noqa: S311
    draws = [pace.draw(rng, s, 0) for _ in range(200)]
    assert min(draws) >= 1.6 and max(draws) <= 2.4
    assert "Mon 2.0 h" in pace.describe(s)


# ----------------------------------------------------------------------------------------------- rollouts
def test_rollout_respects_dependencies():
    """B is due before A, so earliest-deadline-first would do B first, but B waits for A: B never finishes before A."""
    a, b = node("A", 9, 8.0), node("B", 6, 4.0, ["A"])
    res, alloc = rollout.simulate([a, b], FLAT, TODAY, 28, n=300, seed=3)
    assert res["B"].p50 >= res["A"].p50 and res["B"].p90 >= res["A"].p90
    assert sum(alloc["B"][:1]) == 0 and sum(alloc["A"][:1]) > 0  # the first day goes to A
    free = node("C", 6, 4.0)
    res2, _ = rollout.simulate([a, free], FLAT, TODAY, 28, n=300, seed=3)
    assert res2["C"].p50 < res["B"].p50  # without the dependency C is done sooner


def test_a_dependency_cycle_is_dropped_not_looped():
    a, b = node("A", 5, 2.0, ["B"]), node("B", 5, 2.0, ["A"])
    deps = rollout.acyclic([a, b])
    assert sum(len(v) for v in deps.values()) == 1  # one edge went, so both can finish
    res, _ = rollout.simulate([a, b], FLAT, TODAY, 14, n=100, seed=1)
    assert res["A"].finished == 1.0 and res["B"].finished == 1.0
    assert rollout.acyclic([node("X", 3, 1, ["nope", "X"])]) == {"X": []}


def test_risk_and_bands():
    easy = node("easy", 20, 4.0)
    tight = node("tight", 1, 30.0)
    res, alloc = rollout.simulate([easy, tight], FLAT, TODAY, 28, n=400, seed=2)
    assert res["easy"].risk == 0 and res["tight"].risk == 1.0
    assert res["easy"].p50 <= res["easy"].p90 and res["tight"].p50 > TODAY + dt.timedelta(days=1)
    assert sum(sum(h) for h in alloc.values()) <= 7 * 4.4 + 0.1  # never more than the days can hold
    nowhere, _ = rollout.simulate([node("huge", 5, 500.0)], FLAT, TODAY, 14, n=100, seed=1)
    assert (
        nowhere["huge"].p50 is None and nowhere["huge"].finished == 0 and nowhere["huge"].risk == 1.0
    )  # never finishing is late
    zero, _ = rollout.simulate([node("done", 3, 5.0, frac=1.0)], FLAT, TODAY, 7, n=50, seed=1)
    assert zero["done"].risk == 0


def test_free_time_caps_the_days():
    res, _ = rollout.simulate(
        [node("n", 20, 8.0)], FLAT, TODAY, 28, n=200, seed=1, free=lambda d: 1.0
    )  # one free hour a day
    assert res["n"].p50 >= TODAY + dt.timedelta(days=5)  # 8 hours at one hour a day


def test_rollouts_are_repeatable():
    n = [node("a", 10, 6.0, guessed=True), node("b", 12, 6.0)]
    one = rollout.simulate(n, FLAT, TODAY, 21, n=200, seed=9)
    two = rollout.simulate(n, FLAT, TODAY, 21, n=200, seed=9)
    assert one == two and one != rollout.simulate(n, FLAT, TODAY, 21, n=200, seed=10)


# ---------------------------------------------------------------------------------------------- scoring
def test_calibration_score(app):
    p50 = (TODAY + dt.timedelta(days=5)).isoformat()
    st = tree._state(app)  # noqa: SLF001
    st["predictions"] = [
        {
            "on": (TODAY - dt.timedelta(days=14)).isoformat(),
            "nodes": {f"d:{i}": {"p50": p50, "due": p50} for i in range(8)},
        }
    ]
    tree.jsave(app.paths.state / tree.FILE, st)
    early, late = TODAY + dt.timedelta(days=2), TODAY + dt.timedelta(days=9)
    half = lambda i: early if int(i.split(":")[1]) % 2 else late  # noqa: E731
    n, frac, skill = score.calibration(app, TODAY, finish=half)
    assert n == 8 and frac == 0.5 and skill == 1.0  # about half before their p50: calibrated
    n, frac, skill = score.calibration(app, TODAY, finish=lambda i: early)
    assert frac == 1.0 and skill == 0.0  # always early: the plans were too pessimistic
    n, frac, skill = score.calibration(app, TODAY, finish=lambda i: late if i.endswith(("0", "1", "2")) else None)
    assert n == 3 and skill is None  # too few to say
    n, _, skill = score.calibration(app, TODAY - dt.timedelta(days=10), finish=half)
    assert n == 0 and skill is None  # a plan under a week old isn't scored yet


def test_no_credit_for_compliance():
    """The score reads only when things finished; nothing about the allocation or following it goes in."""
    import ast
    import inspect

    tree_ = ast.parse(inspect.getsource(score))
    names = {n.id for n in ast.walk(tree_) if isinstance(n, ast.Name)} | {
        a.arg for n in ast.walk(tree_) if isinstance(n, ast.arguments) for a in n.args
    }
    assert not [x for x in names if "alloc" in x.lower() or "follow" in x.lower() or "complian" in x.lower()]
    assert not any("plans" in m for m in whitelist.REWARD_SOURCES)  # no reward reads it
    assert list(inspect.signature(score.calibration).parameters) == ["app", "today", "finish"]


def test_plans_are_recorded_weekly(app):
    res = {"d:x": rollout.Result("d:x", "x", dt.datetime(2026, 11, 9), TODAY + dt.timedelta(days=3), None, 0.1, 1.0)}
    score.record(app, res, TODAY)
    score.record(app, res, TODAY + dt.timedelta(days=3))
    assert len(tree._state(app)["predictions"]) == 1  # noqa: SLF001
    score.record(app, res, TODAY + dt.timedelta(days=8))
    assert len(tree._state(app)["predictions"]) == 2  # noqa: SLF001


# -------------------------------------------------------------------------------------------- the use
def test_risk_raises_standing_bid(app):
    put_deadlines(
        app,
        {
            "hard": {"title": "Thesis chapter", "kind": "assignment", "due": future(1), "status": "open"},
            "easy": {"title": "Short reading", "kind": "assignment", "due": future(25), "status": "open"},
        },
    )
    tree.set_effort(app, "d:hard", 20)
    tree.set_effort(app, "d:easy", 1)
    plan = plans.run(app, seed=1, today=dt.date.today())
    assert plan["results"]["d:hard"].risk > 0.9 and plan["results"]["d:easy"].risk < 0.1
    ids = {b.item_id: b for b in workspace.bid_standing(app, 0)}
    assert "goal:plan-d:hard" in ids and "goal:plan-d:easy" not in ids
    assert ids["goal:plan-d:hard"].urgency > 0.9  # a standing bid that grows with the risk
    tree.set_effort(app, "d:hard", 1)
    plans.run(app, seed=1, today=dt.date.today())
    assert "goal:plan-d:hard" not in {
        b.item_id for b in workspace.bid_standing(app, 0)
    }  # the risk went; so did the bid


def test_plan_messages_capped(app):
    put_deadlines(app, {"hard": {"title": "Thesis chapter", "kind": "assignment", "due": future(1), "status": "open"}})
    tree.set_effort(app, "d:hard", 60)
    assert plans.weekly(app, now=1_000_000.0) is True
    assert plans.weekly(app, now=1_000_000.0 + 3 * 86400) is False  # once a week
    assert len(app.sent) == 1 and app.sent[0][1]["why"] == "mind.plan" and "Thesis chapter" in app.sent[0][0]
    assert "% on time at your current pace" in app.sent[0][0]
    assert plans.weekly(app, now=1_000_000.0 + 7 * 86400) is True  # next week, again
    tree.set_effort(app, "d:hard", 0.5)
    assert plans.weekly(app, now=1_000_000.0 + 15 * 86400) is False  # nothing at risk: nothing said


def test_no_message_when_nothing_is_at_risk_and_never_a_nag(app):
    put_deadlines(app, {"e": {"title": "Reading", "kind": "assignment", "due": future(30), "status": "open"}})
    tree.set_effort(app, "d:e", 1)
    assert plans.weekly(app, now=1.0) is False and app.sent == []
    import inspect

    src = inspect.getsource(plans).lower()
    for word in ("remind", "guilt", "overdue", "you should", "you must"):
        assert word not in src.replace("never steer", "")


def test_view_is_a_suggestion(app):
    put_deadlines(app, {"a": {"title": "Lab report", "kind": "assignment", "due": future(4), "status": "open"}})
    tree.set_effort(app, "d:a", 6)
    text = plans.view(app)
    assert "A suggestion for this week" in text and "Lab report" in text and "% late" in text and "not a to-do" in text
    assert "/plan effort" in text
    app.settings.set("mind.plans.on", False)
    assert "off" in plans.view(app) and plans.run(app) is None and plans.weekly(app) is False


def test_nothing_to_plan(app):
    assert "Nothing to plan" in plans.view(app)
