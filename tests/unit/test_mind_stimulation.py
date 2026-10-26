"""Brain, 0.8.8: physical stimulation, its senses felt as a body (Weber-Fechner intensity over slow baselines, phasic
and tonic channels, comfort curves, pain), what it feeds (feelings, the mood as an input) and GET /api/body."""

import json
import math
import time

import pytest

from kurooto import mind
from kurooto.core.state import jsave
from kurooto.mind import stimulation as stim
from kurooto.mind.senses import intero


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    yield a
    mind.forget_client(a)
    a.close()


def body_now(app, **s):
    jsave(app.paths.state / intero.FILE, {"history": [{"at": time.time(), **s}]})


def test_weber_fechner_intensity():
    assert stim.intensity(50, 50, 2, 1.5, 1.0) == 0.0  # at the baseline: nothing felt
    small, big = stim.intensity(52, 50, 2, 1.5, 1.0), stim.intensity(70, 50, 2, 1.5, 1.0)
    assert 0 < small < big < 1
    # the same change is felt less where the normal spread is wider (relative, not absolute)
    assert stim.intensity(60, 50, 10, 1.5, 1.0) < stim.intensity(60, 50, 1, 1.5, 1.0)
    # the spec's sigmoid, shifted to start at 0: 2 sigmoid(g ln(1+z)) - 1
    z = 20 / 3
    assert big == pytest.approx(2 / (1 + math.exp(-1.5 * math.log1p(z))) - 1)


def test_the_baseline_adapts_over_hours():
    mu, s2 = 40.0, 0.0
    mu, s2 = stim.ewma(mu, s2, 60.0, 60.0)
    assert 40.0 < mu < 40.1 and s2 > 0  # a minute barely moves it
    for _ in range(6 * 60):
        mu, s2 = stim.ewma(mu, s2, 60.0, 60.0)
    assert mu == pytest.approx(40 + 20 * (1 - math.exp(-6 * 3600 / stim.TAU_S - 60 / stim.TAU_S)), rel=1e-6)


def test_comfort_curves_and_pain():
    heat = stim.CHANNELS["heat"]
    assert stim.comfort(heat, 55) == 1.0 and stim.comfort(heat, 70) > 0 > stim.comfort(heat, 82)
    assert stim.comfort(heat, 95) == -1.0
    load = stim.CHANNELS["load"]
    assert stim.comfort(load, 35) > stim.comfort(load, 0) > 0 > stim.comfort(load, 85)  # some load is good
    t = 1_800_000_000.0
    hot = stim.feel("heat", None, 92.0, t, broken=True)
    assert hot["v"] == -1.0 and hot["I"] >= stim.PAIN_FLOOR  # pain doesn't fade into the baseline


def test_phasic_decays_tonic_holds():
    t = 1_800_000_000.0
    a = stim.feel("touch", None, 0.0, t)
    a = stim.feel("touch", a, 0.0, t + 60)
    a = stim.feel("touch", a, 6.0, t + 120)  # picked up
    peak = a["I"]
    assert peak > 0.5
    b = stim.feel("touch", a, 6.0, t + 240)  # two minutes on, no change: e^-1 of the peak
    assert b["I"] == pytest.approx(peak * math.exp(-1), rel=1e-3)
    h = stim.feel("heat", None, 50.0, t)
    for i in range(1, 5):
        h = stim.feel("heat", h, 50.0, t + 60 * i)
    h = stim.feel("heat", h, 75.0, t + 300)
    h2 = stim.feel("heat", h, 75.0, t + 420)
    assert h2["I"] > 0.5 * h["I"]  # tonic: it holds (fading only as the baseline adapts, over hours)


def test_a_tick_from_the_senses(app):
    assert stim.on(app)  # on with Brain
    t = time.time()
    body_now(app, cpu_temp_c=50.0, cpu_pct=20.0, ram_pct=40.0, battery_pct=80, charging=False, disk_free_pct=50.0,
             queue_depth=0)  # fmt: skip
    stim.tick(app, t=t)
    body_now(app, cpu_temp_c=93.0, cpu_pct=95.0, ram_pct=40.0, battery_pct=4, charging=False, disk_free_pct=3.0,
             queue_depth=2, limit_hit=True)  # fmt: skip
    out = stim.tick(app, t=t + 60)
    ch = out["channels"]
    assert set(ch) == {"heat", "load", "nourishment", "pain"}  # no phone sensors on: no hands
    assert ch["pain"]["x"] == 4 and ch["pain"]["v"] == -1.0  # hot, disk, battery, limit
    assert ch["heat"]["v"] == -1.0 and ch["nourishment"]["v"] == -1.0
    r = out["regions"]
    assert r["skin"]["intensity"] > 0.5 and r["head"]["valence"] < 0 and r["hands"]["channels"] == {}
    assert 0 < out["arousal"] <= 1 and out["tone"] < -0.5 and out["own_tone"] < -0.5
    assert stim.own_tone(app) == pytest.approx(out["own_tone"])


def test_phone_channels_never_move_the_mood(app):
    from kurooto.mind.senses import store

    for s in ("screen", "motion", "dnd", "headphones"):
        app.settings.set(f"mind.senses.phone.{s}", True)
    t = time.time()
    body_now(app, cpu_temp_c=50.0, ram_pct=30.0)
    stim.tick(app, t=t)
    store.add(app, "phone:screen", "unlocks", "", 5, t=t + 30)
    store.add(app, "phone:motion", "state", "walking", 3, t=t + 30)
    store.add(app, "phone:dnd", "on", "", 1, t=t + 30)
    out = stim.tick(app, t=t + 60)
    assert {"touch", "motion", "quiet"} <= set(out["channels"]) and "hearing" not in out["channels"]  # no reading yet
    assert out["regions"]["hands"]["channels"] and out["regions"]["skin"]["channels"]["touch"]["intensity"] > 0
    own = {n for n, c in stim.CHANNELS.items() if c.own}
    assert own == {"heat", "load", "pain", "nourishment"}  # only its own body reaches the mood (I-14)


def test_measure_hands_the_tone_to_the_mood(app):
    from kurooto.mind import measure

    body_now(app, cpu_temp_c=95.0)
    stim.tick(app)
    assert measure.measure(app)["body_tone"] < 0
    app.settings.set("mind.stimulation.on", False)
    assert "body_tone" not in measure.measure(app)


def test_api_body(app):
    """GET /api/body: regions with intensity, valence and channels, arousal, tone, mood, at; plain numbers only."""
    from kurooto.web.api import Api

    body_now(app, cpu_temp_c=60.0, ram_pct=50.0, battery_pct=70, charging=True)
    stim.tick(app)
    code, b = Api(app).get("body")
    assert code == 200 and set(b) == {"on", "regions", "arousal", "tone", "mood", "at"}
    assert set(b["regions"]) == {"head", "hands", "gut", "skin"}
    for r in b["regions"].values():
        assert set(r) == {"intensity", "valence", "channels"}
        for c in r["channels"].values():
            assert set(c) == {"intensity", "valence"} and all(isinstance(v, float) for v in c.values())
    assert "nourishment" in b["regions"]["gut"]["channels"] and "x" not in json.dumps(b["regions"])
    assert all(isinstance(b[k], float) for k in ("arousal", "tone", "mood", "at"))
    app.settings.set("mind.stimulation.on", False)
    code, off = Api(app).get("body")
    assert code == 200 and off["on"] is False and all(r["channels"] == {} for r in off["regions"].values())
    assert stim.tick(app) is None


def test_off_with_brain(app):
    app.settings.set("modules.enabled", [])
    assert stim.tick(app) is None and not (app.paths.state / stim.FILE).exists()
