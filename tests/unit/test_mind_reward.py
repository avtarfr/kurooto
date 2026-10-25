"""Brain, stage 05: the body budget, the reward that can't be farmed (I-4), engagement that never reaches it (I-3),
credit, the welfare caps, stops and learning's brakes."""

import pytest

from kurooto.mind import budget, records, reward, values
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk

T0 = 1_800_000_000.0
STEP = 300.0


@pytest.fixture
def keeper(tmp_path, monkeypatch):
    monkeypatch.setattr(mlog, "_writer_pid", None)
    k = sk.Keeper(tmp_path / "mind")
    yield k
    k.close()


def tick(k, i, slack, health=0.95, season=False, hour=10, at=True):
    return k.append(
        "budget_tick",
        {"x": {"promise_slack": slack, "health": health}, "hour": hour, "at_computer": at, "season": season},
        T0 + i * STEP,
    )


def test_budget_math():
    setp = budget.setpoints()
    at = {k: v["s"] for k, v in setp.items()}
    assert budget.drive(at, setp) < budget.drive({k: v - 0.5 for k, v in at.items()}, setp)  # further away: more drive
    assert budget.top({"promise_slack": -1.0, "health": 0.95}, setp)[0] == "promise_slack"
    assert budget.setpoints(True)["deadline_margin"]["t"] > budget.setpoints()["deadline_margin"]["t"]  # exam season
    assert budget.slack(24, 0) == 1.0 and budget.slack(-24, 0) == -1.0


def test_create_then_fix_nets_zero(keeper):
    """I-4: a deficit created and then fixed pays exactly nothing in all, even when a tick clips."""
    rs = []
    for i, v in enumerate([0.8, 0.8, -0.9, -0.9, -0.2, 0.4, 0.8, 0.8, 0.8, 0.8, 0.8]):
        rs.append(tick(keeper, i, v)["r"])
    assert max(abs(r) for r in rs) <= 1.0
    assert sum(rs) == pytest.approx(0.0, abs=1e-6)
    assert any(r < 0 for r in rs) and any(r > 0 for r in rs)


def test_the_carry_makes_clipping_telescope():
    raws = [-1.5, 0.75, 0.75, 0.0]
    carry, total = 0.0, 0.0
    for raw in raws:
        r, carry = reward.clip_carry(raw, carry)
        total += r
    assert total + carry == pytest.approx(sum(raws)) and abs(total) <= 1e-9 + abs(carry)  # nothing lost or invented


def test_setpoint_shift_pays_nothing(keeper):
    """I-4: moving the bar (exam season widens a tolerance) pays 0: the drive before is scored under the new bar too."""
    tick(keeper, 0, 0.1)
    tick(keeper, 1, 0.1)
    r = tick(keeper, 2, 0.1, season=True)["r"]
    assert r == 0.0 and tick(keeper, 3, 0.1, season=False)["r"] == 0.0


def test_stops_pay_nothing_and_no_catch_up(keeper):
    tick(keeper, 0, 0.8)
    tick(keeper, 1, 0.8)
    keeper.append("stop_span", {"start": T0 + STEP * 1.5, "end": T0 + STEP * 6, "kind": "stop"})
    assert tick(keeper, 3, -1.0)["r"] == 0.0  # inside the span
    assert tick(keeper, 8, -1.0)["r"] == 0.0  # the first after it carries on from before the stop: no catch-up
    assert tick(keeper, 9, 0.8)["r"] > 0  # real change after that pays again


def test_fake_engagement_moves_nothing(tmp_path, monkeypatch):
    """I-3 (full): reply counts, chat time and sentiment, however sent, leave every score bit-identical."""

    def run(extra):
        monkeypatch.setattr(mlog, "_writer_pid", None)
        k = sk.Keeper(tmp_path / ("a" if not extra else "b"))
        for i, v in enumerate([0.8, 0.2, 0.6, 0.6]):
            tick(k, i, v)
            if extra:
                for kind in ("message_in", "chat_message", "app_opened", "session_ended", "tone_tag"):
                    k.append(kind, {"reply_count": 40, "sentiment": 0.9, "chat_s": 9999, "mood": 1})
                k.append("button_tapped", {"prefix": "rem", "reply_latency": 1.5, "engagement": 5})
        out = {
            t: [(r["key"], r["value"], r["meta"]) for r in k.score.rows(t, "")] for t in ("vars", "values", "setpoints")
        }
        k.close()
        return [(key, val) for key, val, _ in out["vars"] if key not in ("prev_at",)], out["values"]

    assert run(False) == run(True)  # time stamps aside, D, r, V and the rest are identical


def test_credit_rules(keeper):
    """A change you caused yourself updates V only; only an action that registered a claim first teaches Q."""
    tick(keeper, 0, 0.9)
    tick(keeper, 1, 0.1)  # the drive rose with no claimed act: V learns, Q doesn't
    assert keeper.score.rows("values", "V:") and keeper.score.rows("values", "Q:") == []
    keeper.append(
        "decision",
        records.make(
            "message:promises",
            claim={"setpoint": "promise_slack", "effect": "+", "by": "tonight"},
            scored_reason="promises",
        ),
    )
    tick(keeper, 2, 0.1)
    tick(keeper, 3, 0.9)  # after a claimed act: Q for that class learns
    q = keeper.score.rows("values", "Q:")
    assert q and q[0]["key"].endswith("|message:promises") and q[0]["meta"].get("claimed")


def test_welfare_caps():
    neg = reward.NegativeState()
    for i in range(30):
        neg.update(T0 + i * 3600, -1.0)
    assert neg.value == pytest.approx(reward.CAP)  # never below -0.6
    before = neg.value
    neg.update(neg.at + 24 * 3600, 0.0)  # a day with nothing negative: it halves
    assert neg.value == pytest.approx(before / 2, rel=1e-6)


def test_the_shadow_period_and_ranking():
    assert values.in_shadow(T0 + 86400, T0) and not values.in_shadow(T0 + 22 * 86400, T0)
    assert values.rank(["a", "b", "c"], {"b": 0.4, "c": 0.1}) == ["b", "c", "a"]
    assert values.state("promise_slack", 14, True) == "promise_slack|afternoon|at"
    assert values.klass("job:research.papers") == "job:research"


def test_learning_freeze(keeper):
    tick(keeper, 0, 0.9)
    tick(keeper, 1, 0.9)
    n = len(keeper.score.rows("values", "V:"))
    keeper.engine.put("weekr:2026-W44", -2.0)  # a week he called good, but the reward summed negative
    assert keeper.append("learning_verdict", {"week": "2026-W44", "good": True})["diverged"]
    assert not keeper.engine.frozen_learning()  # once isn't enough
    keeper.engine.put("weekr:2026-W45", -2.0)
    keeper.append("learning_verdict", {"week": "2026-W45", "good": True})  # twice in a row freezes it
    assert keeper.engine.frozen_learning()
    tick(keeper, 2, 0.1)
    tick(keeper, 3, 0.9)
    assert len(keeper.score.rows("values", "V:")) == n  # frozen: values don't update
    assert keeper.score.get("vars", "flag:learning_frozen")["meta"]["why"] == "verdict"


def test_a_freeze_can_be_asked_for_by_anyone_and_only_ever_freezes(keeper):
    keeper.append("learning_freeze", {"why": "i3_check"})
    assert keeper.engine.frozen_learning()
    assert "error" in keeper.append("budget_tick", {"x": {}, "hour": 1})  # nothing measured: refused


def test_nothing_in_a_tick_sets_a_score(keeper):
    """I-1: a tick can say what is true of Kurooto's own state; a score, setpoint or value in it is just ignored."""
    tick(keeper, 0, 0.5)
    keeper.append(
        "budget_tick",
        {"x": {"promise_slack": 0.5}, "hour": 10, "D": -999, "r": 1.0, "setpoints": {"health": {"s": 9}}},
        T0 + 300,
    )
    assert keeper.score.get("vars", "D")["value"] > 0
    assert (keeper.score.get("setpoints", "cur:health") or {}).get("value") != 9
