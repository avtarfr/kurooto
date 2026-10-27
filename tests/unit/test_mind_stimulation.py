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
    assert set(b["regions"]) == {"head", "hands", "gut", "skin", "face"}
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


# ------------------------------------------------------------------------------------------------- another device
class FakeLive:
    def __init__(self):
        self.msgs = []

    def push(self, msg, only=None):
        self.msgs.append(json.loads(json.dumps(msg)))  # as the stream sends it


def test_an_add_ons_readings_map_to_physical_analogues():
    x = stim.translate({
        "light_lux": 99.0, "proximity_cm": 0.0, "accel_x": 0.0, "accel_y": 9.80665, "accel_z": 3.0,
        "gyro_x": 0.3, "gyro_y": 0.4, "gyro_z": 0.0, "heading_deg": 90.0, "screen_on": 1, "loudness_db": 55.0,
        "picked_up": True, "battery_temp_c": 33.5, "battery_pct": 60, "charging": 1,
    })  # fmt: skip
    assert x["brightness"] == pytest.approx(2.0)  # log10(1 + lux): a room
    assert x["closeness"] == 1.0 and x["eyes"] == 1.0 and x["handled"] == 1.0
    a = math.sqrt(9.80665**2 + 9.0)
    assert x["sway"] == pytest.approx(a - stim.G) and x["tilt"] == pytest.approx(math.degrees(math.acos(9.80665 / a)))
    assert x["turning"] == pytest.approx(0.5) and x["heading"] == 90.0
    assert x["loudness"] == 55.0 and x["temperature"] == 33.5 and x["satiety"] == 70.0  # +10 on the charger
    # the table: each a channel of the body map, in its region, of its kind, never its own body (so never the mood)
    want = {"brightness": ("face", False), "closeness": ("face", True), "sway": ("face", True), "tilt": ("face", False),
            "turning": ("face", True), "heading": ("face", False), "eyes": ("face", False),
            "loudness": ("face", False), "handled": ("skin", True), "temperature": ("skin", False),
            "satiety": ("gut", False)}  # fmt: skip
    assert set(x) == set(want)
    for name, (region, phasic) in want.items():
        ch = stim.CHANNELS[name]
        assert (ch.region, ch.phasic, ch.own) == (region, phasic, False), name
    # the other ways of saying it: near, full-scale loudness; a compass going round 359 -> 1 is a 2-degree turn
    assert stim.translate({"near": 1})["closeness"] == 1.0 and stim.translate({"proximity_cm": 8})["closeness"] == (
        pytest.approx(0.2)
    )
    assert stim.translate({"loudness_dbfs": -40.0})["loudness"] == 60.0
    assert stim.translate({"heading_deg": 1.0}, heading_was=359.0)["heading"] == pytest.approx(361.0)
    assert stim.translate({"accel_x": 0.0, "accel_y": 0.0, "accel_z": 0.0}) == {"sway": stim.G}  # falling: no tilt


def test_unknown_or_bad_readings_are_ignored(app):
    junk = {"mic_words": 1.0, "light_lux": "bright", "proximity_cm": float("nan"), "accel_x": 1.0,
            "battery_pct": 400, "charging": 1, 3: 4, "loudness_db": None}  # fmt: skip
    assert stim.translate(junk) == {} and stim.translate("not a dict") == {}  # half an accelerometer: nothing
    assert stim.feed(app, "body phone", junk) is False and stim.feed(app, "body phone", "light") is False
    app.live = FakeLive()
    assert stim.feed(app, "body phone", {"light_lux": 10.0, "who": 7, "charging": 1}) is True
    (m,) = app.live.msgs
    assert m["readings"] == {"light_lux": 10.0, "charging": 1.0} and set(m["channels"]) == {"brightness"}


def test_off_means_nothing_done(app):
    app.live = FakeLive()
    for off in (("mind.stimulation.addons", False), ("mind.stimulation.on", False)):
        app.settings.set(*off)
        assert stim.feed(app, "body phone", {"light_lux": 100.0}) is False
        app.settings.set(off[0], True)
    app.settings.set("modules.enabled", [])  # Brain off
    assert stim.feed(app, "body phone", {"light_lux": 100.0}) is False
    assert app.live.msgs == [] and stim.tick(app) is None


def test_fed_readings_are_felt_at_the_tick_and_never_move_the_mood(app):
    body_now(app, cpu_temp_c=50.0, ram_pct=30.0)
    stim.tick(app)
    own = stim.state(app)["own_tone"]
    for g in (0.0, 4.0, 0.0):  # shaken once between ticks: felt at its strongest, not its latest
        assert stim.feed(app, "body phone", {"accel_x": 0.0, "accel_y": 9.80665 + g, "accel_z": 0.0})
    stim.feed(app, "body phone", {"battery_pct": 3, "battery_temp_c": 48.0, "light_lux": 5000.0, "near": 1})
    out = stim.tick(app)
    ch = out["channels"]
    assert ch["sway"]["x"] == pytest.approx(4.0) and ch["tilt"]["x"] == pytest.approx(0.0)
    assert ch["closeness"]["x"] == 1.0 and ch["brightness"]["x"] == pytest.approx(math.log10(5001.0))
    assert ch["satiety"]["v"] == -1.0 and ch["temperature"]["v"] == -1.0  # a dying, hot device hurts there...
    assert ch["temperature"]["I"] >= stim.PAIN_FLOOR and ch["pain"]["x"] == 0  # ...not in its own head
    assert out["own_tone"] == pytest.approx(own)  # its own body's tone, the mood's only input, is as it was
    assert {"sway", "tilt", "closeness", "brightness"} <= set(out["regions"]["face"]["channels"])
    assert "satiety" in out["regions"]["gut"]["channels"] and "temperature" in out["regions"]["skin"]["channels"]
    assert stim.tick(app)["channels"]["sway"]["x"] == 0.0  # the next tick: the latest again
    code, b = __import__("kurooto.web.api", fromlist=["Api"]).Api(app).get("body")
    assert code == 200 and "sway" in b["regions"]["face"]["channels"] and "x" not in json.dumps(b["regions"])
    assert not list(app.paths.state.glob("*addon*")) and not list(app.paths.state.glob("*device*"))  # memory only
    stim.forget(app)
    assert "sway" not in stim.tick(app)["channels"]


def test_the_live_message_shape(app, monkeypatch):
    app.live = FakeLive()
    assert stim.feed(app, "body phone", {"light_lux": 120.0, "gyro_x": 1.0, "gyro_y": 0.0, "gyro_z": 0.0})
    assert stim.feed(app, "body phone", {"light_lux": 130.0})  # within 0.2 s: kept, not sent again
    (m,) = app.live.msgs
    assert set(m) == {"t", "source", "readings", "channels", "at"} and m["t"] == "senses"
    assert m["source"] == "body phone" and isinstance(m["at"], float)
    assert m["readings"] == {"light_lux": 120.0, "gyro_x": 1.0, "gyro_y": 0.0, "gyro_z": 0.0}
    assert m["channels"] == {"brightness": round(math.log10(121.0), 3), "turning": 1.0}
    assert all(isinstance(v, float) for d in (m["readings"], m["channels"]) for v in d.values())  # numbers only
    monkeypatch.setattr(stim, "LIVE_S", 0.0)
    stim.feed(app, "<script>", {"screen_on": 0})  # a name it can't show: a plain one instead
    assert app.live.msgs[-1]["source"] == "another device" and app.live.msgs[-1]["channels"] == {"eyes": 0.0}


def test_the_being_reacts_to_them_apart_from_your_phone():
    from pathlib import Path

    import kurooto

    static = Path(kurooto.__file__).parent / "web" / "static"
    home, js = (static / "home.js").read_text(encoding="utf-8"), (static / "being.js").read_text(encoding="utf-8")
    assert 'else if (m.t === "senses") { if (BEING) BEING.senses(m); }' in home
    assert "senses: far," in js and "SENSE = {}, FAR = null" in js  # its own store, not your phone's SENSE
    for organ, reading in (("pupil", 'fc("brightness")'), ("lids", 'fc("eyes")'), ("otoliths", 'fc("sway")'),
                           ("otoliths", 'fc("tilt")'), ("otoliths", 'fc("turning")'), ("cilia", 'fc("closeness")'),
                           ("cochlea", 'fc("loudness")'), ("coil", 'fc("temperature")')):  # fmt: skip
        assert reading in js, organ
    assert "rows: (await senseRows(k)).concat(farRows(k))," in js
