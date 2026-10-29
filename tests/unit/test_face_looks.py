"""Add this look (0.9.0, face.looks.on): a short capture of how you look now, added to your face model as enrolled
samples of their own look, after a check that it's safe. All with fakes: made-up unit vectors (a "hair up" look is
the base turned away from it, so your enrolment scores it "unsure"), scripted faces, a fake camera; no camera is
opened, no model loaded, no picture looked at. Each test draws from its own seeded Random, so the order they run in
changes nothing."""
# ruff: noqa: F811 (the fixtures imported from the other tests are taken as arguments)

import json
import math
import random
from pathlib import Path

import pytest

from kurooto.core import calm, tap
from kurooto.core.biometric import unit
from kurooto.modules.base import Incoming
from kurooto.modules.face import enrol as en
from kurooto.modules.face import model as mo
from kurooto.modules.face.enrol import Look
from tests.unit import test_face as tf
from tests.unit.test_face import (
    BASE,
    GOOD,
    Clock,
    app,  # noqa: F401 (pytest fixtures)
    events,
    face,
    frame,
    judge,
    ready,  # noqa: F401
    rvec,
    samples,
    trained,  # noqa: F401
    you,
)


def _off(x: list[float], v: list[float]) -> list[float]:
    d = sum(a * b for a, b in zip(x, v, strict=True))
    return [a - d * b for a, b in zip(x, v, strict=True)]


def turned(c: list[float], cos: float, seed: int, away: list[list[float]]) -> list[float]:
    """A direction at this cosine from the centroid c, at right angles to whatever else the other centroids hold: the
    same person looking different (or, far enough, someone else), scored exactly against the enrolment in use."""
    basis: list[list[float]] = []
    for v in [c, *away]:  # Gram-Schmidt
        for b in basis:
            v = _off(v, b)
        basis.append(unit(v))
    o = rvec(random.Random(seed))  # noqa: S311 (made-up test data, not secrets)
    for b in basis:
        o = _off(o, b)
    o = unit(o)
    s = math.sqrt(1 - cos * cos)
    return unit([cos * a + s * x for a, x in zip(c, o, strict=True)])


# Set for each test by _looks below, from the enrolment that test uses:
ENROLLED: list = []  # the made-up enrolment's samples (tests without the trained fixture)
C: list[float] = BASE  # its "base" centroid
# "hair up": a frame of it scores about 0.38 against your enrolment, "unsure" (0.313 to 0.413), and so does their
# average: the same person by OpenCV's 0.363
HAIR: list[float] = BASE
# too far: each low-noise frame still scores about 0.34 ("unsure", not a stranger), but the average isn't 0.363
FAR: list[float] = BASE


@pytest.fixture(autouse=True)
def _looks(request):
    """The same draws whatever order the tests run in (test_face's shared Random reseeded), and the looks built
    against the enrolment actually in use, so every margin is what the comments say."""
    global C, HAIR, FAR, ENROLLED
    state = tf.R.getstate()  # put back after the test: the other files' draws stay as they were
    tf.R.seed(42)
    if "trained" in request.fixturenames:
        t = request.getfixturevalue("trained").template()
        ENROLLED = [x for x in t.samples if not mo.is_look(x.step)]
    else:
        ENROLLED = samples()
    cents = dict(mo.centroids(ENROLLED))
    C = cents["base"]
    others = [v for k, v in cents.items() if k != "base"]
    HAIR = turned(C, 0.38, 7, others)
    FAR = turned(C, 0.345, 8, others)
    yield
    tf.R.setstate(state)


@pytest.fixture
def r():
    return random.Random(1234)  # noqa: S311 (made-up test data, not secrets)


def hair_up(r):
    return you(HAIR, noise=0.1, r=r)


def owners(classify, r, n=20) -> int:
    return sum(classify(hair_up(r))[0] == "owner" for _ in range(n))


def feed_look(f, make, limit=200):
    """Drive the look's session with frames from make(i) until it ends; returns the clock."""
    sess = f.session
    clock = Clock()
    sess.clock = clock
    sess.started = sess.last_fetch = sess._tick_at = sess._last_frame_at = clock.t
    i = 0
    while sess.state != "ended" and i < limit:
        f.cam.frames = [make(i)]
        clock.t += 0.6
        sess.step()
        i += 1
    return clock


def hair_frames(r):
    return lambda i: frame([face(dx=(i % 40) * 4.0)], [hair_up(r)])


def results(f):
    return [m for m in f.pushed if m.get("kind") == "look_result"]


@pytest.fixture
def notes(app, monkeypatch):
    sent = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: sent.append((text, kw)))
    return sent


# ------------------------------------------------------------------------------------------------- the plan
def test_the_look_plan_takes_enrolment_s_checks_and_only_frames_like_you(r):
    mine = mo.centroids(ENROLLED)
    p = Look(60, {}, lambda e: mo.score(e, mine), 0.313, "hair up")
    assert p.current().key == "look" and p.progress()["need"] == en.LOOK_TARGET and not p.ready()
    two = frame([face(), face(x=40, h=100)], [hair_up(r), rvec(r)])
    assert judge(p, two, 1.0).reason == en.R_TWO
    assert judge(p, frame([face(h=30.0)], [hair_up(r)]), 2.0).reason == en.R_FAR
    assert judge(p, frame([face()], [hair_up(r)], [{**GOOD, "blur": 5.0}]), 3.0).reason == en.R_BLUR
    assert judge(p, frame([face(yaw=0.5)], [hair_up(r)]), 4.0).reason == en.R_LOOK_TURN
    assert judge(p, frame([face()], [rvec(r)]), 5.0).reason == en.R_LOOK_NOT_YOU  # a stranger's frame
    t = 10.0
    for i in range(en.LOOK_TARGET):
        t += 1.0
        v = judge(p, frame([face(dx=i * 5.0, yaw=0.2 if i % 2 else -0.2)], [hair_up(r)]), t)
        assert v.ok, (i, v.reason)
    assert p.current() is None and p.ready() and p.total() == en.LOOK_TARGET
    assert {s.step for s in p.samples} == {"look"}
    assert "nothing to skip" in p.act("skip")


# ------------------------------------------------------------------------------------------------ the check
def test_a_look_like_you_is_safe_and_one_too_far_is_refused(r):
    base = list(ENROLLED)
    look = [mo.Sample(hair_up(r), "look", i) for i in range(10)]
    assert mo.look_check(base, [], look, None) == ""
    far = [mo.Sample(you(FAR, noise=0.1, r=r), "look", i) for i in range(10)]
    mine = mo.centroids(base)
    assert all(mo.score(s.e, mine) >= 0.313 for s in far)  # every frame "unsure", none a stranger...
    assert "too far from your face model" in mo.look_check(base, [], far, None)  # ...but not safe as a whole
    assert "only 6 clear samples" in mo.look_check(base, [], look[:6], None)
    strangers = [mo.Sample(rvec(r), "look", i) for i in range(10)]
    assert "too far" in mo.look_check(base, [], strangers, None)


def test_a_look_is_anchored_to_the_enrolment_never_to_another_look(r):
    t = mo.Template("sha")
    t.samples = list(ENROLLED)
    t.add_look("hair up", [mo.Sample(hair_up(r), "look", i) for i in range(10)], 1.0)
    beyond = unit([1.35 * h - 0.35 * b for h, b in zip(HAIR, C, strict=True)])  # one more step away from you
    nxt = [mo.Sample(you(beyond, noise=0.1, r=r), "look", i) for i in range(10)]
    assert mo.score(mo.mean_unit([s.e for s in nxt]), [("l", HAIR)]) > 0.9  # close to the first look...
    assert "too far" in mo.look_check(t.samples, [], nxt, None)  # ...still measured against your enrolment


def test_with_impostors_a_look_that_would_push_the_cut_off_over_you_is_refused(r):
    base = list(ENROLLED)
    look = [mo.Sample(hair_up(r), "look", i) for i in range(10)]
    plain = [rvec(r) for _ in range(1000)]
    assert mo.look_check(base, [], look, plain) == ""  # unrelated faces: the cut-off stays, your TAR stays
    near = plain + [unit([h + 0.2 * x for h, x in zip(HAIR, rvec(r), strict=True)]) for _ in range(100)]
    why = mo.look_check(base, [], look, near)  # many faces like the look: keeping them out would lock you out
    assert "too close to other faces" in why and "instead of" in why


def test_looks_have_their_own_centroid_and_round_trip_without_their_labels_in_the_status(r):
    t = mo.Template("sha")
    t.samples = list(ENROLLED)
    n0 = len(t.samples)
    t.retrain(None, "", "normal", 0, en.TARGETS)
    assert owners(t.classify, r) <= 8  # mostly "unsure" before
    look = t.add_look("hair up", [mo.Sample(hair_up(r), "look", i) for i in range(10)], 5.0)
    rep = t.retrain(None, "", "normal", 0, en.TARGETS)
    assert any(g == "look:" + look["id"] for g, _ in t.cents) and owners(t.classify, r) >= 19
    assert all(not k.startswith("look:") for k in rep["per_step"]) and rep["samples"] == n0 + 10
    st = t.status()
    assert st["looks"] == 1 and "hair up" not in json.dumps(st)
    assert all(not k.startswith("look") for k in st["per_step"])
    back = mo.Template.from_payload(json.loads(json.dumps(t.to_payload())))
    assert back.looks == t.looks and owners(back.classify, r) >= 19
    back.use_looks = False  # face.looks.on off: the look's centroid doesn't count, the cut-off is the same
    assert owners(back.classify, r) <= 8 and back.hi == t.hi
    assert t.remove_look(look["id"]) == look and len(t.samples) == n0 and t.looks == []
    assert t.remove_look("nope") is None


# ---------------------------------------------------------------------------------------------- the session
def test_add_this_look_adds_samples_and_recognises_you_with_it(app, trained, r):
    f = trained
    hi = f.template().hi
    assert owners(f._classify, r) <= 8  # mostly "unsure" before
    ok, out = f.look_start("  hair\nup ", cid=7)
    assert ok and out["stage"] == "looking" and f.stage() == "looking" and f.cam.opened == 2
    assert out["plan"]["label"] == "hair up"
    feed_look(f, hair_frames(r))
    s = f.session
    assert s.state == "ended" and not f.cam.open_now and s.plan.samples == []
    res = results(f)
    assert len(res) == 1 and res[0]["ok"] and 'Added "hair up" (10 samples)' in res[0]["message"]
    t = f.template()
    assert [x["label"] for x in t.looks] == ["hair up"] and t.looks[0]["n"] == 10 and len(t.samples) == 62
    assert owners(f._classify, r) >= 19
    assert all(f._classify(rvec(r))[0] == "stranger" for _ in range(20))  # nobody else gets in
    assert t.hi >= hi and f.status()["can_undo"]
    assert f.status()["model"]["looks"][0]["label"] == "hair up"
    assert f.store.status()["looks"] == 1 and f.store.status()["samples"] == 62
    ev = [e for e in events(app) if e["kind"] == "face_look"]
    assert ev and set(ev[-1]) == {"ts", "kind", "result", "count"} and ev[-1]["result"] == "added"
    looks = [m for m in f.pushed if m.get("kind") == "look"]
    assert looks and all("e" not in m and "embedding" not in m for m in looks) and looks[-1]["got"] == 10


def test_the_label_and_the_samples_are_kept_only_sealed(app, trained, r):
    f = trained
    f.look_start("hair up")
    feed_look(f, hair_frames(r))
    assert f.template().looks
    blob = f.store.file.read_bytes()
    assert b"hair up" not in blob and b"look:" not in blob
    assert "hair up" not in f.store.status_file.read_text(encoding="utf-8")
    f._tpl = None  # unsealed again from the file
    assert f.template().looks[0]["label"] == "hair up"


def test_a_look_too_far_is_refused_with_the_reason_and_nothing_changes(app, trained, r):
    f = trained
    n0 = len(f.template().samples)
    f.look_start("someone")
    feed_look(f, lambda i: frame([face(dx=(i % 40) * 4.0)], [you(FAR, noise=0.1, r=r)]))
    res = results(f)[-1]
    assert not res["ok"] and "wasn't added" in res["message"] and "too far" in res["message"], res
    assert len(f.template().samples) == n0 and f.template().looks == [] and not f.status()["can_undo"]
    assert [e["result"] for e in events(app) if e["kind"] == "face_look"] == ["refused"]


def test_a_stranger_or_nobody_gives_too_few_frames(app, trained, r):
    f = trained
    f.look_start()
    clock = feed_look(f, lambda i: frame([face(dx=(i % 40) * 4.0)], [rvec(r)]))
    res = results(f)[-1]
    assert not res["ok"] and res["message"].startswith("Only 0 clear frames") and f.template().looks == []
    assert clock.t - 10_000.0 <= en.LOOK_S + 1.0  # it ended by itself after LOOK_S of capturing
    assert not f.cam.open_now
    f.look_start()
    feed_look(f, lambda i: frame([], []))
    assert results(f)[-1]["message"].startswith("Only 0 clear frames")


def test_when_a_look_may_start(app, trained, monkeypatch):
    f = trained
    app.settings.set("face.looks.on", False)
    assert "Add this look is off" in f.look_start()[1]["message"]
    app.settings.set("face.looks.on", True)
    monkeypatch.setattr(f, "_on_call", lambda: True)
    assert "call" in f.look_start()[1]["message"]
    monkeypatch.setattr(f, "_on_call", lambda: False)
    ok, out = f.look_start()
    assert ok and f.session.plan.label == "Look 1"
    assert "Another" in f.look_start()[1]["message"]
    f.test_stop(out["session"])
    assert results(f)[-1]["message"] == "Add this look stopped. Nothing was added."
    t = f.template()
    t.looks = [{"id": str(i), "label": f"l{i}", "at": 0, "n": 7} for i in range(mo.LOOKS_MAX)]
    assert "the most it keeps" in f.look_start()[1]["message"]
    t.looks = []
    f.forget()
    assert "Enrol first" in f.look_start()[1]["message"]


def test_switching_it_off_stops_the_session_and_the_looks_stop_counting(app, trained, r):
    f = trained
    f.look_start("hair up")
    sess = f.session
    sess.clock = Clock()
    f.cam.frames = [hair_frames(r)(0)]
    sess.step()
    app.settings.set("face.looks.on", False)
    sess.step()
    assert sess.state == "ended" and not f.cam.open_now and f.template().looks == []
    assert "turned off" in results(f)[-1]["message"]
    app.settings.set("face.looks.on", True)
    f.look_start("hair up")
    feed_look(f, hair_frames(r))
    assert owners(f._classify, r) >= 19
    app.settings.set("face.looks.on", False)
    assert owners(f._classify, r) <= 8  # at once, no retrain
    app.settings.set("face.looks.on", True)
    assert owners(f._classify, r) >= 19


def test_remove_a_look_and_undo_it(app, trained, r):
    f = trained
    f.look_start("hair up")
    feed_look(f, hair_frames(r))
    lid = f.looks()[0]["id"]
    from kurooto.web.api import Api

    api = Api(app)
    code, out = api.post("face/look/remove", {"id": lid})
    assert out["ok"] and 'Removed "hair up"' in out["message"] and f.looks() == []
    assert len(f.template().samples) == 52
    assert api.post("face/look/remove", {"id": lid})[1]["ok"] is False
    assert api.post("face/undo", {})[1]["ok"] and f.looks()[0]["label"] == "hair up"
    assert [e["result"] for e in events(app) if e["kind"] == "face_look"] == ["added", "removed"]


def test_forget_takes_the_looks_too(app, trained, r):
    f = trained
    f.look_start("hair up")
    feed_look(f, hair_frames(r))
    f.forget()
    assert not f.store.exists() and f.looks() == []


# ------------------------------------------------------------------------------------ the ways to start it
def test_the_command_from_a_chat_and_from_the_terminal(app, trained, notes, r):
    f = trained
    m = Incoming(text="/face add-look hair up")
    said = f._cmd(m, "add-look hair up")
    assert said.startswith("Look at this computer's camera now") and "I'll say how it went" in said
    assert f.session.kind == "look" and not f.session.preview  # no page: no JPEG is made
    feed_look(f, hair_frames(r))
    assert f.session._jpeg is None
    assert notes and notes[-1][1]["why"] == "face.look" and 'Added "hair up"' in notes[-1][0]
    notes.clear()
    t = Incoming(text="/face add-look", via="terminal")
    assert "I'll say" not in f._cmd(t, "add-look")
    assert f.look_status()["session"] == {"state": "capturing", "got": 0, "need": en.LOOK_TARGET}
    feed_look(f, hair_frames(r))
    st = f.look_status()
    assert st["session"] is None and st["last"]["ok"] and "Look 2" in st["last"]["message"]
    assert not notes  # the terminal prints it (cli.py face_add_look)
    assert "typed only" in f._cmd(Incoming(text="/face add-look", via="voice"), "add-look")
    assert "typed only" in f._cmd(Incoming(text="/face add-look", voice=True), "add-look")
    app.settings.set("face.looks.on", False)
    assert "is off" in f._cmd(m, "add-look")


def test_the_api_routes(app, trained, r):
    from kurooto.web.api import Api

    api = Api(app)
    code, st = api.get("face")
    assert st["looks"] == {"on": True, "max": mo.LOOKS_MAX, "samples": en.LOOK_TARGET, "s": en.LOOK_S}
    assert st["model"]["looks"] == []
    code, out = api.post("face/look/start", {"cid": "7", "label": "hair up"})
    assert out["ok"] and api.get("face")[1]["stage"] == "looking"
    trained.cam.frames = [hair_frames(r)(0)]
    trained.session.step()
    assert api.face_frame({"s": out["session"]}) == b"\xff\xd8 not a real picture"  # the page's preview
    assert api.post("face/look/status", {})[1]["session"]["got"] == 1
    assert api.post("face/look/stop", {"session": out["session"]})[1]["ok"]
    assert not trained.cam.open_now and trained.looks() == []


def test_the_rules_around_it():
    assert tap.GUARDED["camera.open"].ways == ("typed", "button")
    assert "/face add-look" in tap.GUARDED["camera.open"].where
    rr = calm.REASONS["face.look"]
    assert rr.exempt == "own" and rr.stop is None
    from kurooto.core.config import Settings

    assert Settings(Path("/nonexistent/x.json")).get("face.looks.on") is True
