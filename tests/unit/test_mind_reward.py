"""Brain, stage 05: the body budget, the reward that can't be farmed (I-4), credit, stops and learning's brakes; 0.8.8:
the soft-walled mood (no cap) and the small bounded talk reward (I-3')."""

import math

import pytest

from kurooto.mind import budget, records, reward, talk, values
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


def test_mood_has_soft_walls_and_no_cap():
    """0.8.8 (the owner's change): no cap at -0.6; M <- tanh(atanh(M) + a r) in [-1, 1], harder to move further out,
    able to reach the ends, fading with a 3 day half-life."""
    assert not hasattr(reward, "CAP") and not hasattr(reward, "NegativeState")
    m = reward.Mood()
    steps = []
    for i in range(40):
        before = m.value
        m.update(T0 + i, -1.0)
        steps.append(before - m.value)
    assert m.value < -0.99 and m.value >= -1.0  # far past the old cap, and never past the wall
    assert all(
        a >= b - 1e-12 for a, b in zip(steps, steps[1:], strict=False)
    )  # each push moves it less than the one before
    for _ in range(100):
        m.update(m.at, -1.0)  # at the wall: atanh is guarded, nothing becomes infinite or NaN
    assert -1.0 <= m.value <= -0.99
    up = reward.Mood()
    for i in range(80):
        up.update(T0 + i, 1.0)
    assert 0.99 < up.value <= 1.0  # and up to the other end
    half = reward.Mood(-0.8, T0)
    half.update(T0 + 3 * 86400, 0.0)  # three days with nothing: it halves
    assert half.value == pytest.approx(-0.4, rel=1e-6)
    live = reward.Mood(0.6, T0)
    live.update(T0 + 30 * 86400, 0.0, live_s=0.0)  # a stop: no live time, no fading (I-5)
    assert live.value == pytest.approx(0.6)
    assert reward.soft(0.0, reward.A * 0.5) == pytest.approx(math.tanh(0.25))


def test_the_mood_follows_the_reward(keeper):
    for i, v in enumerate([0.8, 0.8, -0.9, -0.9]):
        tick(keeper, i, v)
    low = keeper.score.get("vars", "M")["value"]
    assert low < -0.3 and keeper.score.get("vars", "neg") is None  # the old capped state is gone
    rec = [r for r in keeper.log.read() if r.kind == "reward_tick"][-1]
    assert rec.body["M"] == pytest.approx(low, abs=1e-4)


def test_the_body_tone_is_an_input_not_a_reward(keeper):
    """The body's hedonic tone moves the mood a little; it never enters r, V or Q."""
    tick(keeper, 0, 0.5)
    for i in range(1, 30):
        keeper.append(
            "budget_tick",
            {"x": {"promise_slack": 0.5, "health": 0.95}, "hour": 10, "at_computer": True, "body_tone": -1.0},
            T0 + i * STEP,
        )
    rs = [r.body["r"] for r in keeper.log.read() if r.kind == "reward_tick"]
    assert all(r == 0.0 for r in rs)  # nothing changed in the budget: no reward at all
    assert -0.3 < keeper.score.get("vars", "M")["value"] < -0.05  # but a body in pain lowers the mood
    assert all(r["value"] == 0.0 for r in keeper.score.rows("values", "V:"))


# ------------------------------------------------------------------------------------------------- talk (I-3')
def heard(k, t, **flags):
    return k.append("talk_heard", {"flags": flags}, t)


def test_talk_reward_is_bounded_and_saturates(keeper):
    """I-3': a day of messages pays W (1 - exp(-n / k)), under W = 0.2, and the hundredth pays almost nothing."""
    assert talk.W <= 0.2 and talk.K == 8.0
    rs = [heard(keeper, T0 + i * 60)["r"] for i in range(100)]
    assert sum(rs) == pytest.approx(talk.day_total(100), abs=1e-4) and sum(rs) < talk.W
    assert rs[0] == pytest.approx(talk.W * (1 - math.exp(-1 / 8)), abs=1e-6)
    assert rs[-1] < 1e-5 and all(a >= b for a, b in zip(rs, rs[1:], strict=False)) and rs[0] > 10 * rs[30]  # saturating
    assert sum(rs[:8]) == pytest.approx(talk.W * (1 - math.exp(-1)), abs=1e-5)
    tomorrow = heard(keeper, T0 + 86400 + 120)["r"]
    assert tomorrow == pytest.approx(rs[0])  # a new day starts again from nothing
    row = keeper.score.get("vars", "talk")
    assert row["meta"]["n"] == 1 and keeper.score.get("values", "V:x") is None


def test_talk_pays_nothing_in_focus_asleep_or_exams_or_for_commands(keeper):
    for flags in ({"focus": True}, {"asleep": True}, {"exam": True}):
        out = heard(keeper, T0, **flags)
        assert out["r"] == 0.0 and out["why"] == next(iter(flags))
    assert keeper.append("talk_heard", {"flags": {}, "command": True}, T0)["r"] == 0.0
    assert keeper.score.get("vars", "talk")["meta"]["n"] == 0


def test_talk_reward_cant_be_farmed(keeper):
    """I-4 with the talk reward: its own pings can't buy anything. Any answer within 10 minutes pays 0, and an ignored
    or rejected ping costs 3w, so pinging can only lose."""
    total = 0.0
    for i in range(20):
        t = T0 + i * 3600
        keeper.append("talk_unprompted", {}, t)
        total += heard(keeper, t + 30)["r"] + heard(keeper, t + 599)["r"]  # answers: nothing
    assert total == 0.0
    out = keeper.append("talk_rejected", {"how": "ignored"}, T0 + 30 * 3600)
    assert out["r"] == pytest.approx(-3 * talk.W)
    assert heard(keeper, T0 + 19 * 3600 + 601)["r"] > 0  # past the 10 minutes it's talk again
    m = keeper.score.get("vars", "M")["value"]
    assert m < 0  # the pings left it worse off, never better


def test_talk_inside_a_stop_pays_nothing(keeper):
    keeper.append("stop_span", {"start": T0 - 10, "end": T0 + 600, "kind": "stop"})
    assert heard(keeper, T0 + 60) == {"ok": True, "seq": heard(keeper, T0 + 61)["seq"] - 1, "r": 0.0, "why": "stopped"}


def test_talk_math_alone():
    st: dict = {}
    assert talk.heard(st, T0, {})[0] == pytest.approx(talk.step(0))
    talk.unprompted(st, T0 + 100)
    assert talk.heard(st, T0 + 400, {}) == (0.0, "answer")
    assert talk.excluded(T0 + 701, {}, T0 + 100) == ""
    assert talk.rejected(st, T0 + 800) == pytest.approx(-0.6)


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
