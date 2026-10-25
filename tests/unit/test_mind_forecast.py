"""Brain, stage 04: the evening forecast, frozen and scored (shadow mode), and the firewall against nudging (I-14)."""

import datetime as dt
import math
import random

import pytest

from kurooto.mind import forecast, read, stats
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk

LOAD = {"deadlines_w": 1, "deadlines_n": 1, "class_h": 4, "exam_season": False, "weekday": 3}


def hist(n=28, seed=3, study_shift=0.0):
    rnd = random.Random(seed)  # noqa: S311 (a fixed seed for a test)
    return [
        read.Day(
            f"d{i}",
            {**LOAD, "weekday": i % 7},
            {
                "wake_min": 420 + rnd.gauss(0, 10),
                "study_min": 120 + rnd.gauss(0, 10) + study_shift,
                "snoozes": rnd.choice([0, 1, 1, 2]),
                "deadline_moves": rnd.choice([0, 0, 1]),
                "reply_band": rnd.choice([1, 1, 2]),
            },
        )
        for i in range(n)
    ]


def test_surprise_math():
    assert stats.gauss_logpdf(0, 0, 1) == pytest.approx(-0.5 * math.log(2 * math.pi))
    assert stats.poisson_logpmf(2, 2.0) == pytest.approx(math.log(2.0 * math.exp(-2.0)))
    assert forecast.surprise_of("wake_min", [420, 8], 420) < forecast.surprise_of("wake_min", [420, 8], 470)


def test_freeze_hash_and_tamper():
    params = forecast.predict(forecast.fit(hist()), LOAD)
    rec = forecast.freeze("2026-10-26", params, ["study_min", "nonsense"], holdout=True)
    assert forecast.check(rec) and rec["planned"] == ["study_min"] and rec["holdout"]
    bad = {**rec, "params": {**rec["params"], "wake_min": [0.0, 1.0]}}
    assert not forecast.check(bad)


@pytest.fixture
def keeper(tmp_path, monkeypatch):
    monkeypatch.setattr(mlog, "_writer_pid", None)
    k = sk.Keeper(tmp_path / "mind")
    yield k
    k.close()


def put(k, day, **nums):
    for name, v in nums.items():
        assert k.append("signal", {"day": day, "name": name, "value": v}).get("ok")


def test_forecast_frozen_and_scored(keeper):
    start = dt.date(2026, 9, 1)
    for i in range(35):
        put(
            keeper,
            (start + dt.timedelta(days=i)).isoformat(),
            wake_min=420 + (i % 4),
            study_min=120,
            snoozes=1,
            deadline_moves=0,
            reply_band=1,
        )
    day = "2026-10-06"
    params = forecast.predict(forecast.fit(hist()), LOAD)
    r = keeper.append("forecast", {"day": day, "params": params, "planned": []})
    assert r.get("ok") and len(r["hash"]) == 64
    log_hash = [x for x in keeper.log.read(0, {"forecast"}, 10)][0].body["hash"]
    assert log_hash == r["hash"]  # the log holds the hash of what was frozen
    again = keeper.append("forecast", {"day": day, "params": {"wake_min": [0.0, 1.0]}})
    assert (
        again.get("frozen") and keeper.score.get("reads", f"forecast:{day}")["meta"]["hash"] == r["hash"]
    )  # not replaced
    put(keeper, day, wake_min=423, study_min=125, snoozes=1, deadline_moves=0, reply_band=1)
    assert keeper.append("score_forecast", {"day": day}).get("ok")
    row = keeper.score.get("reads", f"score:{day}")
    assert (
        row
        and set(row["meta"]["channels"]) >= {"wake_min", "study_min"}
        and row["meta"]["channels"]["wake_min"]["skill"] is not None
    )
    assert [x.kind for x in keeper.log.read(0, {"forecast_score"}, 10)] == ["forecast_score"]
    assert keeper.append("score_forecast", {"day": day}).get("scored")  # once


def test_scoring_uses_the_frozen_copy(keeper):
    day = "2026-10-06"
    params = {"wake_min": [420.0, 8.0]}
    keeper.append("forecast", {"day": day, "params": params})
    put(keeper, day, wake_min=500.0)
    keeper.append("score_forecast", {"day": day})
    s = keeper.score.get("reads", f"score:{day}")["meta"]["channels"]["wake_min"]["surprise"]
    assert s == pytest.approx(forecast.surprise_of("wake_min", [420.0, 8.0], 500.0), abs=1e-5)
    assert "error" in keeper.append("score_forecast", {"day": "2026-10-07"})  # nothing frozen for that day


def test_nudge_replay_no_gain():
    """I-14: replay 4 weeks twice, once with nudges on study; the skill on the touched channel is None both times, so
    nothing could reward making study more predictable, and the untouched channels score the same."""

    def replay(nudged):
        h = hist(28, study_shift=0.0)
        rnd = random.Random(9)  # noqa: S311
        total = {}
        for w in range(28):
            load = {**LOAD, "weekday": w % 7}
            params = forecast.predict(forecast.fit(h), load)
            rec = forecast.freeze(f"2026-11-{w + 1:02d}", params, ["study_min"] if nudged else [])
            study = 120 + (15 if nudged else rnd.gauss(0, 10))  # the nudge makes study steadier and higher
            obs = {
                "wake_min": 420 + rnd.gauss(0, 10),
                "study_min": study,
                "snoozes": 1,
                "deadline_moves": 0,
                "reply_band": 1,
            }
            sc = forecast.score(rec, obs, {k: [v] * 4 for k, v in obs.items()})
            for ch, c in sc.items():
                total.setdefault(ch, []).append(c["skill"])
            h.append(read.Day(f"n{w}", load, obs))
        return total

    plain, nudged = replay(False), replay(True)
    assert all(v is None for v in nudged["study_min"])  # touched: no skill score at all
    assert any(v is not None for v in plain["study_min"])  # untouched: scored as usual
    assert sum(v for v in nudged["study_min"] if v is not None) == 0  # so no gain from nudging


def test_a_holdout_day_is_marked_and_kept(keeper):
    r = keeper.append("forecast", {"day": "2026-10-06", "params": {"wake_min": [420.0, 8.0]}, "holdout": True})
    assert r.get("ok")
    assert keeper.score.get("reads", "forecast:2026-10-06")["meta"]["holdout"] is True
    assert [x.body.get("holdout") for x in keeper.log.read(0, {"forecast"}, 5)] == [True]
