"""0.8.14, one being: Brain's status stream (mind/status.py), the three knobs, one temperament (mind/register.py),
mind.context for every request (providers/context.py), the /mind measurements (mind/console.py), and the being and
the phone drawing the status. Mood only changes how much Kurooto does unprompted: it never adds a confirm step to
something you asked for."""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

import kurooto
from kurooto import mind
from kurooto.core.state import jsave
from kurooto.mind import console, feelings, register, sleep, status, workspace
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind.tom import model as tom_model
from kurooto.providers import context as pctx

ROOT = Path(kurooto.__file__).parents[2]
STATIC = Path(kurooto.__file__).parent / "web" / "static"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    a.settings.set("mind.workspace.cycle_s", 0)
    monkeypatch.setattr(workspace, "BIDDERS", {})
    yield a
    status.stop(a)
    mind.forget_client(a)
    a.close()


class FakeDeadlines:
    def __init__(self, items):
        self._items = items

    def items(self):
        return self._items

    def upcoming(self, hours=336):
        return [(i, it, 30.0) for i, it in self._items.items()]


class Live:
    def __init__(self):
        self.got = []

    def push(self, msg, only=None):
        self.got.append(msg)


# --------------------------------------------------------------------------------------------- the status stream
def test_snapshot_is_enums_and_numbers_and_neutral_with_brain_off(app, monkeypatch):
    snap = status.snapshot(app)
    assert tuple(snap) == status.KEYS
    assert snap["mood"] in status.MOODS and 0.0 <= snap["arousal"] <= 1.0
    assert isinstance(snap["focus"], bool) and isinstance(snap["asleep"], bool) and isinstance(snap["held"], int)
    for v in snap.values():  # nothing but enums, numbers and ids: never a sentence
        assert v is None or isinstance(v, (bool, int, float)) or (isinstance(v, str) and " " not in v)
    app.settings.set("modules.enabled", [])
    assert status.snapshot(app) == status.NEUTRAL
    app.settings.set("modules.enabled", ["mind"])
    app.settings.set("mind.status.on", False)
    assert status.snapshot(app) == status.NEUTRAL


def test_focus_asleep_held_mood_and_top(app, monkeypatch):
    import datetime as dt

    app.availability.set_focus(dt.datetime.now() + dt.timedelta(hours=1))
    monkeypatch.setattr(sleep, "state", lambda a: "asleep")
    monkeypatch.setattr(workspace, "held_count", lambda a: 4, raising=False)
    monkeypatch.setattr(feelings, "mood_band", lambda a: "low")
    jsave(
        app.paths.state / workspace.FILE,
        {
            "winners": [
                {"item_id": "read:x", "kind": "read", "private": True},
                {"item_id": "lab:y", "kind": "lab", "private": False},
            ]
        },
    )
    snap = status.snapshot(app)
    assert snap["focus"] is True and snap["asleep"] is True and snap["held"] == 4 and snap["mood"] == "low"
    assert snap["top"] == "lab"  # the first winner that isn't about you
    monkeypatch.setattr(feelings, "mood_band", lambda a: "even")
    assert status.snapshot(app)["mood"] == "mid"


def test_held_falls_back_to_the_gates_own(app, monkeypatch):
    from kurooto.mind import gate

    monkeypatch.delattr(workspace, "held_count", raising=False)
    jsave(app.paths.state / gate.FILE, {"held": [{"until": time.time() + 600, "msg": {}}] * 2})
    assert status.snapshot(app)["held"] == 2


def test_uneasy_is_the_deadlines_id_never_its_title(app, monkeypatch):
    app.modules["deadlines"] = FakeDeadlines({"d42": {"title": "Measure theory sheet 5", "due": "2030-01-01T10:00"}})
    monkeypatch.setattr(app, "is_on", lambda m: m in ("mind", "deadlines"))
    jsave(
        app.paths.state / feelings.FILE,
        {
            "label": "uneasy",
            "arousal": 0.7,
            "concerns": [
                {"kind": "deadline", "item": "Measure theory sheet 5", "risk": 0.8, "concern": 0.8, "why": "due soon"}
            ],
        },
    )
    snap = status.snapshot(app)
    assert snap["uneasy"] == "deadline:d42" and snap["arousal"] == 0.7
    assert "Measure" not in repr(snap)  # the title only on this computer's own page (GET /api/mind/status)
    assert status.view(app)["uneasy_item"] == {
        "kind": "deadline",
        "id": "d42",
        "title": "Measure theory sheet 5",
        "tab": "today",
    }


def test_the_stream_pushes_on_a_change_only_to_pages_and_listeners(app, monkeypatch):
    live = app.live = Live()
    seen = []
    remove = status.add_listener(lambda a, snap: seen.append(snap))
    bad = status.add_listener(lambda a, snap: 1 / 0)  # one listener failing never stops the stream
    try:
        s = status.Stream(app)
        assert s.check() is True and s.check() is False  # the same snapshot again: nothing goes
        monkeypatch.setattr(workspace, "held_count", lambda a: 3, raising=False)
        assert s.check() is True
    finally:
        remove()
        bad()
    assert [m["held"] for m in live.got] == [0, 3] and all(m["t"] == "mind" and m["kind"] == "status" for m in live.got)
    assert set(live.got[0]) == {"t", "kind", "knobs", *status.KEYS}
    assert len(seen) == 2 and seen[1]["held"] == 3
    assert not app.events.tail(50, {"mind_status"})  # never into the event log


def test_the_stream_starts_with_brain_and_is_at_most_once_a_second(app, monkeypatch):
    live = app.live = Live()
    monkeypatch.setattr(status, "STALE_S", 0.05)
    s = status.start(app)
    deadline = time.time() + 3
    while not live.got and time.time() < deadline:
        time.sleep(0.02)
    n = 0
    for i in range(5):  # five changes in a burst: pushed no faster than once a second
        monkeypatch.setattr(workspace, "held_count", lambda a, i=i: i + 1, raising=False)
        status.poke(app)
        time.sleep(0.05)
    time.sleep(0.3)
    n = len(live.got)
    status.stop(app)
    assert 1 <= n <= 2 and s.last is not None


# ------------------------------------------------------------------------------------------------ the knobs
def test_knobs_from_mood_arousal_and_calibration(app, monkeypatch):
    monkeypatch.setattr(feelings, "mood_band", lambda a: "low")
    k = status.knobs(app)
    assert k["explore"] == 0.5 and k["interest_shift"] > 0 and k["ask"] is False and k["uncertainty"] is None
    monkeypatch.setattr(feelings, "mood_band", lambda a: "high")
    assert status.knobs(app)["explore"] == 1.0  # never more than you set
    from kurooto.mind import beliefs

    monkeypatch.setattr(beliefs, "brier", lambda a: {"saw": (8, 0.3), "inferred": (4, 0.28)})
    k = status.knobs(app)
    assert k["uncertainty"] == pytest.approx((8 * 0.3 + 4 * 0.28) / 12, abs=1e-3) and k["ask"] is True
    monkeypatch.setattr(beliefs, "brier", lambda a: {"saw": (40, 0.1)})
    assert status.knobs(app)["ask"] is False
    app.settings.set("mind.knobs.on", False)
    assert status.knobs(app) == status.KNOBS_NEUTRAL and status.explore(app) == 1.0


def test_its_own_acts_ask_first_while_its_beliefs_are_a_coin_flip(app, monkeypatch):
    from kurooto.mind import act, trust

    monkeypatch.setattr(trust, "may_act", lambda *a, **k: True)
    monkeypatch.setattr(act, "klass_of", lambda *a, **k: "R1")
    monkeypatch.setattr(mind.connect(app), "trust_rows", lambda: [])
    assert act.verdict(app, "calendar.block")["do"] is True
    monkeypatch.setattr(status, "knobs", lambda a, snap=None: {**status.KNOBS_NEUTRAL, "ask": True})
    v = act.verdict(app, "calendar.block")
    assert v["do"] is False and "guess" in v["why"]
    monkeypatch.setattr(act, "klass_of", lambda *a, **k: "R0")
    assert act.verdict(app, "calendar.block")["do"] is True  # R0 acts as before


# --------------------------------------------------------------------------------------------- one temperament
def test_register_from_mood_and_arousal(app):
    r = register.register
    assert r(app, {"mood": "low", "arousal": 0.2}) == "quiet"
    assert r(app, {"mood": "mid", "arousal": 0.5}) == "even"
    assert r(app, {"mood": "high", "arousal": 0.6}) == "lively"
    assert register.sentences(app, {"mood": "low", "arousal": 0.0}) < register.sentences(
        app, {"mood": "high", "arousal": 1.0}
    )
    app.settings.set("mind.register.on", False)
    assert r(app, {"mood": "low", "arousal": 0.0}) == "even"


def test_register_never_touches_replies(app, monkeypatch):
    monkeypatch.setattr(feelings, "mood_band", lambda a: "low")
    assert register.line(app, "you") == "" and "sentences" in register.line(app, "bg")
    assert register.opener(app, asked=True) == "" and register.opener(app, asked=False)
    assert register.rate(app, 1.1, unprompted=False) == 1.1
    slow = register.rate(app, 1.0, unprompted=True)
    monkeypatch.setattr(feelings, "mood_band", lambda a: "high")
    jsave(app.paths.state / feelings.FILE, {"arousal": 1.0})
    fast = register.rate(app, 1.0, unprompted=True)
    assert 0.92 <= slow < 1.0 < fast <= 1.08  # within 8% either way
    # what goes to an AI: a length only, never its state in words
    for text in (register.line(app, "bg"), register.opener(app)):
        assert not re.search(r"(?i)\b(mood|low|sad|aroused|arousal|feel)", text)


def test_voice_paces_only_what_it_says_unasked():
    src = (ROOT / "src/kurooto/modules/voice/__init__.py").read_text(encoding="utf-8")
    assert "self.speaker.say(text, wait=True, rate=self._unasked_rate())  # a greeting is said unasked" in src
    assert "self.speaker.say(result.text, wait=False)" in src  # an answer to you: its own rate, as before
    assert "rate=self._unasked_rate() if unprompted else None" in src


def test_a_call_it_placed_opens_as_its_register_says(app, monkeypatch):
    from kurooto.modules.calls import ASKED_WHYS

    calls = app.modules["calls"]
    monkeypatch.setattr(calls, "live_call", lambda: {"key": "k", "reason": "check-in", "why": "checkins.call"})
    assert "opener" in calls.pending()
    for why in ASKED_WHYS:
        monkeypatch.setattr(calls, "live_call", lambda why=why: {"key": "k", "reason": "x", "why": why})
        assert "opener" not in calls.pending()
    monkeypatch.setattr(calls, "live_call", lambda: None)  # he rang it: his call
    assert "opener" not in calls.pending()


# --------------------------------------------------------------------------------------------- mind.context
def _tom(app, n=600, shaky=("fubini-theorem", "dominated-convergence")):
    now = time.time()
    rows = [
        {
            "id": f"r{i}",
            "part": "knowledge",
            "subject": f"concept-{i}",
            "claim": "mastery solid",
            "p": 0.9,
            "source": "inferred",
            "confidence": 0.8,
            "updated": now - 3600,
            "evidence": ["quiz:a", "quiz:b"],
        }
        for i in range(n - len(shaky))
    ]
    rows += [
        {
            "id": f"s{i}",
            "part": "knowledge",
            "subject": s,
            "claim": "mastery some",
            "p": 0.45,
            "source": "inferred",
            "confidence": 0.6,
            "updated": now - i,
            "evidence": ["quiz:c", "note:d"],
        }
        for i, s in enumerate(shaky)
    ]
    rows.append(
        {
            "id": "old",
            "part": "knowledge",
            "subject": "old-topic",
            "claim": "mastery new",
            "p": 0.2,
            "source": "inferred",
            "confidence": 0.5,
            "updated": now - 40 * 86400,
            "evidence": ["a", "b"],
        }
    )
    jsave(app.paths.state / tom_model.FILE, {"rows": rows})


def test_mind_context_has_mastery_hints_and_winners_never_how_you_are(app):
    _tom(app)
    jsave(
        app.paths.state / workspace.FILE,
        {
            "winners": [
                {"item_id": "lab:p", "kind": "lab", "text": "the sorting experiment", "private": False},
                {"item_id": "read:2030", "kind": "read", "text": "seems stretched today", "private": True},
                {"item_id": "forecast:x", "kind": "forecast", "text": "a heavy tomorrow", "private": True},
            ]
        },
    )
    text = pctx.mind_context(app)
    assert "fubini theorem" in text and "dominated convergence" in text and "old topic" not in text
    assert "concept-1" not in text  # solid ones aren't hints
    assert "the sorting experiment" in text
    assert "stretched" not in text and "heavy tomorrow" not in text  # its read of you, a forecast of you: never
    whole = pctx.headless_context(app)
    assert "fubini theorem" in whole and "stretched" not in whole
    for word in ("tone", "your mood", "their mood", "stretched", "heart rate", "body state"):
        assert word not in text.lower()


def test_mind_context_is_a_file_read_under_50_ms(app, monkeypatch):
    _tom(app)
    from kurooto.mind.tom import knowledge

    monkeypatch.setattr(knowledge, "concepts", lambda a: pytest.fail("no notes scan"))  # files only, no model
    pctx.mind_context(app)  # warm
    t = []
    for _ in range(20):
        t0 = time.perf_counter()
        pctx.mind_context(app)
        t.append((time.perf_counter() - t0) * 1000)
    assert sorted(t)[int(0.95 * len(t))] < 50, t
    assert pctx.p95_ms() is not None


def test_mind_context_off_is_as_0813(app):
    _tom(app)
    jsave(
        app.paths.state / workspace.FILE,
        {"winners": [{"item_id": "lab:p", "kind": "lab", "text": "an experiment", "private": False}]},
    )
    app.settings.set("mind.context.on", False)
    assert pctx.mind_context(app) == ""
    whole = pctx.headless_context(app)
    assert "fubini" not in whole and "On my mind right now: an experiment (lab)" in whole
    app.settings.set("modules.enabled", [])
    assert "fubini" not in pctx.headless_context(app) and "sentences" not in pctx.headless_context(app, lane="bg")


def test_background_requests_get_the_register_and_yours_dont(app):
    assert "sentences" in pctx.headless_context(app, lane="bg")
    assert "sentences" not in pctx.headless_context(app, lane="you") and "sentences" not in pctx.headless_context(app)


# ------------------------------------------------------------------------- mood never taxes what you asked for
def test_mood_never_adds_a_confirm_step_to_a_requested_action(app, monkeypatch):
    from kurooto.core import tools as core_tools
    from kurooto.modules.calls.tools import Tool

    ran = []
    plain = Tool("note_this", "add a line to a note", lambda a: ran.append("plain") or "done")
    guarded = Tool("ring_me", "place a call", lambda a: ran.append("guarded") or "rang", guarded="call.place")
    asked_before = len(app.ask.pending())
    for band in ("low", "even", "high"):
        monkeypatch.setattr(feelings, "mood_band", lambda a, band=band: band)
        jsave(app.paths.state / feelings.FILE, {"arousal": 0.0 if band == "low" else 1.0})
        assert core_tools.run_tool(app, "note_this", {}, [plain]) == "done"  # asked: it just runs
        assert core_tools.run_tool(app, "ring_me", {}, [guarded], via="call") == "rang"  # on a call: it just runs
    assert ran == ["plain", "guarded"] * 3
    assert len(app.ask.pending()) == asked_before  # no question was added
    # and nothing on the path of a request reads the mood, the status or the register
    for f in ("core/tap.py", "core/tools.py", "core/ask.py", "core/intents.py", "modules/base.py"):
        p = ROOT / "src/kurooto" / f
        if p.exists():
            src = p.read_text(encoding="utf-8")
            assert not re.search(r"mood_band|self_mood|mind\.status|mind import status|register\.", src), f


# ------------------------------------------------------------------------------------------------ measurements
def test_decoration_audit_and_latency(app, monkeypatch):
    monkeypatch.setattr(mlog, "_writer_pid", None)
    k = sk.Keeper(app.paths.state / "mind")
    try:
        assert k.append("gate_receipt", {"did": "held", "why": "x"}).get("ok")
        assert k.append("gate_lint", {"did": "removed"}).get("ok")
        rec = {
            "id": "a1",
            "action": "message:mind.feeling",
            "candidates": [],
            "setpoints": [],
            "claim": None,
            "scored_reason": "",
            "stated_reason": "",
            "source": "rules",
            "risk_class": "",
        }
        assert k.append("decision", rec).get("ok")
        a = console.audit(app)
    finally:
        k.close()
    by = {r["id"]: r for r in a["parts"]}
    assert by["gate"]["changed"] == 2 and by["gate"]["decoration"] is False
    assert by["feelings"]["changed"] == 1
    assert by["workspace"]["changed"] == 0 and by["workspace"]["on"] and by["workspace"]["decoration"] is True
    assert "workspace" in a["decoration"]
    t = time.time()
    rows = [(t - 100, t - 100 + s) for s in (1, 2, 3, 4, 40)]
    monkeypatch.setattr(app.jobs, "_read", lambda sql, args=(), one=True: rows)
    lat = console.latency(app)
    assert lat["n"] == 5 and lat["p95_s"] == pytest.approx(40, abs=0.01)
    text = console.measures_text(app)
    assert "decoration" in text and "p95 40.0 s" in text
    code, out = console.view(app, {"view": "measurements"})
    assert code == 200 and {"audit", "latency"} <= set(out)


# --------------------------------------------------------------------------------------- the being and the phone
def test_the_being_draws_the_status_behind_its_switches():
    js = (STATIC / "being.js").read_text(encoding="utf-8")
    assert "function status(m)" in js and "status," in js
    assert "const shutEyes = () => glance() && (ST.focus || ST.asleep);" in js
    assert 'c.fillText("held"' in js and "uneasyAt()" in js and "opts.openItem" in js
    assert "ST.fogK" in js and "ST.moodK" in js and '(ST.mood === "low" ? -4 : 0)' in js
    assert "sad" not in js.split("function status(m)")[1].split("function update(m)")[0].lower()
    home = (STATIC / "home.js").read_text(encoding="utf-8")
    assert 'm.t === "mind"' in home and 'api("mind/status")' in home and "openItem: openUneasy" in home
    assert 'key === "look.being_status"' in home
    phone = (STATIC / "being-phone.js").read_text(encoding="utf-8")
    assert "PV.being.status(b.mind ?" in phone and "uneasy" in re.search(
        r"window\.KurootoBeing = \{([^}]*)\}", phone
    ).group(1)
    kt = (ROOT / "android/src/io/github/avtarfr/kurooto/OrganViews.kt").read_text(encoding="utf-8")
    assert 'j.optString("mind")' in kt and "MindLine(st)" in kt and "pane.uneasy()" in kt
    api = (ROOT / "src/kurooto/web/api.py").read_text(encoding="utf-8")
    assert 'path == "mind/status"' in api


def test_the_phones_copy_carries_the_status(app, monkeypatch):
    from kurooto.modules.calls import views as views_mod

    vw = views_mod.PhoneViews.__new__(views_mod.PhoneViews)
    vw.app = app
    monkeypatch.setattr(status, "cached", lambda a: {**status.NEUTRAL, "held": 2, "uneasy": "deadline:d1"})
    monkeypatch.setattr(status, "uneasy_target", lambda a, u: {"title": "Sheet 5", "kind": "deadline"})
    m = vw._being_mind()
    assert (
        m["held"] == 2 and m["uneasy_title"] == "Sheet 5" and set(m["knobs"]) == {"explore", "respond", "uncertainty"}
    )
    app.settings.set("mind.status.on", False)
    assert vw._being_mind() is None
