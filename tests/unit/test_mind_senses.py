"""Brain, stage 13: a body: interoception, the activity stream, phone sensors (I-11, I-14), and what is never done."""

import time

import pytest

from kurooto import mind
from kurooto.mind import gate
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind.senses import activity, intero, phone, store


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


BODY = {"cpu_temp_c": 60.0, "gpu_temp_c": 50.0, "vram_used_gb": 1.0, "ram_pct": 40.0, "swap_pct": 5.0,
        "battery_pct": 80, "charging": True, "disk_free_gb": 100.0, "queue_depth": 0}  # fmt: skip


# ----------------------------------------------------------------------------------------------- interoception
def test_intero_sampling(app, monkeypatch):
    s = intero.sample(app)  # the real machine: whatever it can say, without raising
    assert "at" in s and 0 <= s["ram_pct"] <= 100 and s["queue_depth"] == 0
    monkeypatch.setattr(intero, "sample", lambda a: {**BODY, "at": time.time()})
    assert intero.tick(app)["cpu_temp_c"] == 60.0
    assert "CPU temperature: 60.0" in intero.report(app) and intero.last_fine(app) == 1.0
    app.settings.set("mind.senses.intero", False)
    assert intero.tick(app) is None  # its own switch


def test_intero_bids_only_when_something_is_off(app, monkeypatch):
    hot = {**BODY, "cpu_temp_c": 91.0, "disk_free_gb": 1.0, "limit_hit": True}
    monkeypatch.setattr(intero, "sample", lambda a: {**hot, "at": time.time()})
    intero.tick(app)
    ids = {b.item_id for b in intero.bids(app, time.time())}
    assert ids == {"body:hot", "body:disk", "body:limit"} and intero.last_fine(app) < 0.8
    monkeypatch.setattr(intero, "sample", lambda a: {**BODY, "at": time.time()})
    intero.tick(app)
    assert intero.bids(app, time.time()) == []
    assert not any(b.private for b in intero.bids(app, time.time()))  # about the machine, never about you


def test_no_effect_model_of_owner(app):
    """I-14: the learned action-effect model has body variables as its only targets."""
    st = {}
    assert intero.learn(st, "lab", "cpu_temp_c", 12.0)
    for owner_thing in ("mood", "steps", "screen_min", "activity", "sleep", "reply_latency", "focus"):
        assert not intero.learn(st, "lab", owner_thing, 1.0)
    assert set(st["model"]["lab"]) == {"cpu_temp_c"}
    for _ in range(3):
        intero.observe(st, "lab", {"cpu_temp_c": 50, "mood": 3}, {"cpu_temp_c": 62, "mood": 9})
    assert set(st["model"]["lab"]) == {"cpu_temp_c"} and all(
        v in intero.BODY_VARS for a in st["model"].values() for v in a
    )
    import inspect

    src = inspect.getsource(intero)
    assert (
        "phone" not in src.replace("phone sensors", "") and "senses.activity" not in src
    )  # nothing about you feeds it


def test_sensorimotor_model_is_used_for_scheduling(app, monkeypatch):
    st = {"model": {}}
    for _ in range(4):
        intero.learn(st, "lab", "cpu_temp_c", 20.0)
    intero.jsave(app.paths.state / intero.FILE, {**st, "history": []})
    assert intero.expected(app, "lab", "cpu_temp_c") == 20.0 and intero.expected(app, "lab", "vram_used_gb") is None
    monkeypatch.setattr(intero, "sample", lambda a: {**BODY, "cpu_temp_c": 70.0})
    assert intero.would_overheat(app, "lab")  # 70 + 20 >= 85
    monkeypatch.setattr(intero, "sample", lambda a: {**BODY, "cpu_temp_c": 50.0})
    assert not intero.would_overheat(app, "lab")


# ---------------------------------------------------------------------------------------------------- activity
def test_activity_hashes_titles(app, monkeypatch):
    app.settings.set("mind.senses.activity", True)
    monkeypatch.setattr(activity, "active_window", lambda: ("kitty", "SECRET thesis chapter draft", None))
    activity.tick(app)
    raw = store.path(app).read_bytes()
    assert b"SECRET" not in raw and b"thesis" not in raw
    ev = store.events(app, "activity")
    assert {e["kind"] for e in ev} == {"title", "window"} and ev[0]["target"] != "SECRET thesis chapter draft"
    h1 = activity.hashed(app, "same title")
    assert h1 == activity.hashed(app, "same title") and h1 != activity.hashed(app, "other")
    assert len(h1) == 10 and "same" not in h1


def test_no_keystrokes_no_urls(app, monkeypatch):
    app.settings.set("mind.senses.activity", True)
    monkeypatch.setattr(
        activity, "active_window", lambda: ("firefox", "Intro video - YouTube - https://youtube.com/watch?v=abc", None)
    )
    activity.tick(app)
    ev = store.events(app, "activity")
    assert [e["target"] for e in ev] == ["browser:video"]  # a category, no title hash, no URL
    assert b"youtube.com" not in store.path(app).read_bytes() and b"watch" not in store.path(app).read_bytes()
    assert (
        activity.browser_category("Wikipedia - Lorenz system") == "docs"
        and activity.browser_category("some page") == "web"
    )
    import inspect

    src = inspect.getsource(activity).lower()
    for banned in ("keylog", "pynput", "screenshot", "grabwindow", "pyautogui", "imagegrab"):
        assert banned not in src  # nothing here can read keys or the screen


def test_activity_is_opt_in_and_off_collects_nothing(app, monkeypatch):
    monkeypatch.setattr(activity, "active_window", lambda: ("kitty", "x", None))
    assert activity.tick(app) is None and activity.poll(app) == 0 and not store.path(app).exists()


def test_saves_and_commits_in_projects(app, tmp_path):
    proj = tmp_path / "glacier-flow"
    proj.mkdir()
    app.settings.set("mind.lab.projects", [str(proj)])
    app.settings.set("mind.senses.activity", True)
    activity.jsave(app.paths.state / activity.FILE, {"polled": time.time() - 600})
    (proj / "model.py").write_text("x = 1")
    (proj / ".git").mkdir()
    (proj / ".git" / "ignored").write_text("no")
    assert activity.poll(app) == 1
    ev = store.events(app, "activity")
    assert ev[0]["kind"] == "save" and ev[0]["target"] == "glacier-flow/model.py"
    assert "1 saves in glacier-flow" in activity.today(app) or "saves" in activity.today(app)


# --------------------------------------------------------------------------------------------------- retention
def test_retention(app):
    old = time.time() - 9 * 86400
    store.add(app, "activity", "window", "kitty", t=old)
    store.add(app, "activity", "window", "kitty", t=old + 60)
    store.add(app, "activity", "window", "emacs", t=time.time())
    assert len(store.events(app, "activity")) == 3
    assert store.rollup(app) == 2
    ev = store.events(app, "activity")
    assert [e["target"] for e in ev] == ["emacs"]  # raw events: 7 days
    import datetime as dt

    day = dt.datetime.fromtimestamp(old).date().isoformat()
    assert store.totals(app, "activity", day) == {"window:kitty": 2.0}  # then only daily totals


def test_senses_off_per_sensor(app):
    app.settings.set("mind.senses.phone.steps", True)
    now_ms = int(time.time() * 1000)
    bins = [{"s": "steps", "t": now_ms, "total": 4000}, {"s": "light", "t": now_ms, "band": "dim"}]
    code, out = phone.ingest(app, {"bins": bins})
    assert code == 200 and out["kept"] == 1  # light is off: not kept
    assert [e["n"] for e in store.events(app, "phone:steps")] == [4000.0] and store.events(app, "phone:light") == []
    app.settings.set("mind.senses.phone.steps", False)
    assert phone.ingest(app, {"bins": bins})[1]["kept"] == 0
    store.add(app, "activity", "window", "kitty")
    assert store.forget(app, "phone:steps") == 1 and store.events(app, "phone:steps") == []
    assert len(store.events(app, "activity")) == 1  # one sensor's forgetting leaves the others


def test_phone_accepts_only_what_a_sensor_may_say(app):
    for s in phone.SENSORS:
        app.settings.set(f"mind.senses.phone.{s}", True)
    now_ms = int(time.time() * 1000)
    bad = [
        {"s": "microphone", "t": now_ms, "level": 30},  # not a sense
        {"s": "motion", "t": now_ms, "state": "flying", "min": 5},
        {"s": "light", "t": now_ms, "band": "<script>"},
        {"s": "steps", "t": now_ms, "total": "lots"},
        {"s": "steps", "t": now_ms, "total": True},
        {"s": "wifi", "t": now_ms, "id": "My Home Network"},  # a name, not a code
        {"s": "places", "t": now_ms, "event": "arrive", "label": "x" * 80},
        {"s": "steps", "t": 1, "total": 5},  # years old
        {"s": "steps", "t": now_ms + 10 * 86400 * 1000, "total": 5},  # from the future
        "not a dict",
    ]
    assert phone.ingest(app, {"bins": bad})[1]["kept"] == 0
    good = [
        {"s": "motion", "t": now_ms, "state": "walking", "min": 15},
        {"s": "wifi", "t": now_ms, "id": "a1b2c3d4e5f6"},
        {"s": "places", "t": now_ms, "event": "arrive", "label": "the lab"},
        {"s": "usage", "t": now_ms, "min": 190, "package": "com.example.app"},  # an extra field is ignored
    ]
    assert phone.ingest(app, {"bins": good})[1]["kept"] == 4
    assert b"com.example" not in store.path(app).read_bytes()  # never per app
    assert phone.ingest(app, {"nope": 1})[0] == 400
    assert phone.label_wifi(app, "a1b2c3d4e5f6", "home") and phone.wifi_label(app, "a1b2c3d4e5f6") == "home"
    assert not phone.label_wifi(app, "My Home", "x")


def test_phone_senses_all_off_by_default(app):
    assert not any(app.settings.get(f"mind.senses.phone.{s}") for s in phone.SENSORS)
    assert not app.settings.get("mind.senses.activity") and app.settings.get("mind.senses.intero")
    assert phone.ingest(app, {"bins": [{"s": "steps", "t": int(time.time() * 1000), "total": 1}]})[1]["kept"] == 0


def test_phone_aggregates_arrive_through_the_sealed_chat(app):
    """A phone's {"senses": ...} fields, sealed, reach phone.ingest through the same take() the app's chat uses."""
    import json
    import os

    from kurooto.modules.calls import line

    app.settings.set("mind.senses.phone.charging", True)
    app.settings.set("modules.enabled", ["mind", "calls"])
    key = app.secrets.get("calls.ntfy_key") or line.new_key()
    app.secrets.set("calls.ntfy_key", key)
    t = int(time.time() * 1000)
    f = {"id": "a" * 16, "ts": t, "n": os.urandom(16).hex(), "senses": {"bins": [{"s": "charging", "t": t, "on": 1}]}}
    body = {"device": "abcd1234", "at": t, "id": "a" * 16, "k1": line.seal_k1(key, json.dumps(f))}
    code, out = app.modules["calls"].chat.take(body)
    assert code == 200 and out["kept"] == 1 and store.events(app, "phone:charging")[0]["n"] == 1.0
    assert app.modules["calls"].chat.take(body)[0] == 409  # a reading is spent once


# ---------------------------------------------------------------------------------------------- the audit lint
def test_no_audit_lint():
    for s in (
        "You said you'd study tonight, but my activity data shows otherwise.",
        "Last week you told me you finished the notes. According to my window records you didn't open them.",
        "But the screen log says you were on YouTube.",
    ):
        text, removed = gate.lint(s, [], unprompted=False)
        assert removed and all(r == "audit" for _, r in removed) and text.strip() == "", s
    ok, removed = gate.lint("Your essay is due Friday. Want a revision block tonight?", [], unprompted=True)
    assert not removed and ok.startswith("Your essay")
    mixed, removed = gate.lint(
        "Good morning. You said you would study today, but my activity data disagrees. Tea?", [], True
    )
    assert [r for _, r in removed] == ["audit"] and "Good morning" in mixed and "disagrees" not in mixed


def test_the_gate_applies_the_audit_lint_to_answers_too(app):
    from kurooto.core.notify import Message

    verdict, msg, _ = gate.check(app, Message("You said you'd study, but my activity data says no.", why="asked"))
    assert verdict == "block"
