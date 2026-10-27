"""Voice ID (0.8.10, modules/voice/speakerid.py, enrol.py, voiceid.py, core/biometric.py): calibration, the decision,
the quality checks, the enrolment session, improving over time, the sealed template, the parts and the API.

Fakes and synthetic data only: no microphone, no model file, no real voice. FakeEmbedder reads a marker written into
the synthetic sound (which voice, which utterance) and returns normalize(base[voice] + 0.35 * noise[utterance]), so the
owner and others are separable but not perfectly. The optional real-model test runs only with KUROOTO_TEST_MODELS."""

# ruff: noqa: S311 (seeded random numbers make the synthetic voices; nothing here is a secret)

from __future__ import annotations

import array
import base64
import json
import math
import os
import random
import stat
import struct
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from kurooto.core.biometric import BioStore, Locked
from kurooto.modules.voice import enrol
from kurooto.modules.voice import speakerid as sid

DIM = 64  # small vectors keep the tests quick; the maths doesn't care about the size
MAGIC = (13, -13, 13, -13)  # marks the start of each frame in the synthetic sound (quiet: it barely changes levels)
RATE = 16000


# ---------------------------------------------------------------------------------------------- fakes
def gauss(seed: int, dim: int = DIM) -> list[float]:
    r = random.Random(seed)
    return [r.gauss(0, 1) for _ in range(dim)]


class FakeEmbedder:
    """normalize(base[voice] + spread * noise[utterance]); `cold` adds more noise. Counts its calls."""

    def __init__(self, spread: float = 0.35, dim: int = DIM):
        self.spread, self.dim, self.calls = spread, dim, 0

    def vec(self, voice: int, utt: int, cold: int = 0) -> list[float]:
        base = sid.normalize(gauss(1000 + voice, self.dim))
        noise = sid.normalize(gauss(50000 + voice * 1000 + utt, self.dim))
        s = self.spread * (1 + cold)
        return sid.normalize([b + s * n for b, n in zip(base, noise, strict=True)])

    def __call__(self, pcm: bytes) -> list[float]:
        self.calls += 1
        a = array.array("h")
        a.frombytes(bytes(pcm[: len(pcm) - len(pcm) % 2]))
        for i in range(max(0, len(a) - 8)):
            if tuple(a[i : i + 4]) == MAGIC:  # where in the utterance it starts counts too (per second or so)
                return self.vec(a[i + 4], a[i + 5] * 100 + a[i + 7] // 32, a[i + 6])
        raise ValueError("no marker")


def pcm(voice=1, utt=1, seconds=2.0, level=6000, noise=60, cold=0, pre_s=0.3, clip=False) -> enrol.Cut:
    """Synthetic sound: pre_s of low noise, then a sine burst ("speech") with a marker at each frame's start."""
    r = random.Random(voice * 7919 + utt)
    n_pre = int(pre_s * RATE) // enrol.FRAME * enrol.FRAME
    n_sp = int(seconds * RATE) // enrol.FRAME * enrol.FRAME
    out = array.array("h")
    for i in range(n_pre + n_sp):
        x = r.gauss(0, noise)
        if i >= n_pre:
            x += level * math.sin(2 * math.pi * 220 * i / RATE)
        if clip and i >= n_pre and i % 50 == 0:
            x = 32767
        out.append(max(-32768, min(32767, int(x))))
    for f in range(0, len(out), enrol.FRAME):
        out[f : f + 8] = array.array("h", [*MAGIC, voice, utt, cold, f // enrol.FRAME])
    flags = bytes([0] * (n_pre // enrol.FRAME) + [1] * (n_sp // enrol.FRAME))
    return enrol.Cut(bytearray(out.tobytes()), flags)


def make_bank(owner_mix: float = 0.0, emb: FakeEmbedder | None = None, speakers: int = 120) -> sid.Bank:
    """Impostors: other voices, optionally pulled toward the owner (voice 1) by owner_mix; short crops noisier."""
    emb = emb or FakeEmbedder()
    owner = emb.vec(1, 0) if owner_mix else None
    rows, kinds = [], []
    for spk in range(speakers):
        for u in range(2):
            for kind, extra in ((sid.KIND_FULL, 0.0), (sid.KIND_3S, 0.2), (sid.KIND_15, 1.2)):
                v = emb.vec(100 + spk, u)
                v = [x + extra * y for x, y in zip(v, sid.normalize(gauss(9 + spk * 31 + u + kind)), strict=True)]
                if owner:
                    v = [x + owner_mix * o for x, o in zip(v, owner, strict=True)]
                rows.append(array.array("f", sid.normalize(v)))
                kinds.append(kind)
    return sid.Bank({"model_sha256": "x"}, bytes(kinds), rows)


def owner_samples(emb: FakeEmbedder, n: int = 21, voice: int = 1, conds=None, start: int = 1) -> list[dict]:
    conds = conds or ["normal"] * 5 + ["quiet"] * 3 + ["far"] * 3 + ["noise"] * 3 + ["calls"] * 4 + ["free"] * 3
    out = []
    for i in range(n):
        e = emb.vec(voice, start + i)
        s = sid.normalize([x + 0.5 * y for x, y in zip(e, sid.normalize(gauss(77 + i)), strict=True)])
        out.append({"e": e, "s": s, "cond": conds[i % len(conds)]})
    return out


# ------------------------------------------------------------------------------------------ calibration
def test_calibration_orders_and_clamps():
    emb = FakeEmbedder()
    res = sid.calibrate(owner_samples(emb), make_bank(0.5, emb), strictness="normal", margin=0.05)
    t = res["thresholds"]
    for b in (t.long, t.short):
        assert b.unsure < b.accept
        assert sid.CLAMP[0] <= b.accept <= sid.CLAMP[1]
        assert b.unsure <= b.accept - 0.05 + 1e-9
    assert t.short.accept <= t.long.accept  # short crops score lower on both sides
    r = res["report"]
    assert r["grade"] == "good" and r["n"] == 21 and r["dropped"] == 0 and r["bank_rows"] == 720


def test_strict_is_above_every_impostor_and_relaxed_is_below_normal():
    emb = FakeEmbedder()
    bank = make_bank(0.6, emb)
    samples = owner_samples(emb)
    strict = sid.calibrate(samples, bank, strictness="strict")["thresholds"]
    normal = sid.calibrate(samples, bank, strictness="normal")["thresholds"]
    relaxed = sid.calibrate(samples, bank, strictness="relaxed")["thresholds"]
    c = sid.calibrate(samples, bank)["centroid"]
    worst = max(bank.scores(c, (sid.KIND_FULL, sid.KIND_3S)))
    assert strict.long.accept >= min(sid.CLAMP[1], worst + sid.STRICT_PAD) - 1e-9
    assert relaxed.long.accept <= normal.long.accept <= strict.long.accept


def test_outliers_are_dropped_at_most_ten_percent_and_named():
    emb = FakeEmbedder()
    samples = owner_samples(emb)
    for i in (12, 13, 14):  # three "far" samples that are someone else's voice
        samples[i] = {**samples[i], "e": emb.vec(55, i), "cond": "far"}
    r = sid.calibrate(samples, make_bank(0.3, emb))["report"]
    assert r["dropped"] == 2  # 10% of 21
    assert r["dropped_by_cond"] == {"far": 2} and "far from the microphone" in r["dropped_line"]


def test_grades_good_fair_and_weak():
    emb = FakeEmbedder(spread=0.35)
    assert sid.calibrate(owner_samples(emb), make_bank(0.3, emb))["report"]["grade"] == "good"
    noisy = FakeEmbedder(spread=1.4)
    weak = sid.calibrate(owner_samples(noisy), make_bank(1.2, noisy), strictness="strict")["report"]
    assert weak["grade"] == "weak" and "add" in weak["advice"]
    grades = set()
    for spread in (0.8, 0.9, 1.0, 1.1, 1.2):
        e = FakeEmbedder(spread=spread)
        grades.add(sid.calibrate(owner_samples(e), make_bank(0.9, e))["report"]["grade"])
    assert "fair" in grades or {"good", "weak"} <= grades


def test_too_few_samples_is_refused():
    emb = FakeEmbedder()
    with pytest.raises(ValueError, match="at least 12"):
        sid.calibrate(owner_samples(emb, 11), make_bank(0, emb))


def test_frr_matches_a_hand_count_and_the_override_replaces_both():
    assert sid.frr([0.2, 0.5, 0.6, 0.7], 0.55) == 0.5
    t = sid.Thresholds(sid.Band(0.5, 0.45), sid.Band(0.42, 0.37))
    o = sid.override(t, 0.62, 0.05)
    assert (o.long.accept, o.short.accept) == (0.62, 0.62) and abs(o.long.unsure - 0.57) < 1e-9
    assert sid.override(t, 0.0, 0.05) is t
    emb = FakeEmbedder()
    r = sid.calibrate(owner_samples(emb), make_bank(0.3, emb), threshold=0.7)
    assert r["thresholds"].long.accept == 0.7 and r["calibrated"].long.accept != 0.7 and r["report"]["override"]


def test_a_threshold_or_margin_setting_is_held_to_its_range():
    """voice.speaker_id.threshold can't make a stranger "you" (a 0.05 would let nearly anyone act), and the margin
    can't widen "not sure" so far that any short reply carries."""
    t = sid.Thresholds(sid.Band(0.5, 0.45), sid.Band(0.42, 0.37))
    low = sid.override(t, 0.05, 0.05)
    assert low.long.accept == low.short.accept == sid.OVERRIDE[0] == 0.30
    assert sid.override(t, 7.0, 0.05).long.accept == sid.OVERRIDE[1]
    assert sid.override(t, float("nan"), 0.05) is t and sid.override(t, -1, 0.05) is t
    assert sid.override(t, "x", 0.05) is t
    wide = sid.override(t, 0.6, 5.0)
    assert abs(wide.long.unsure - (0.6 - sid.MARGIN_MAX)) < 1e-9
    assert sid.override(t, 0.6, -1).long.unsure < 0.6  # never above accept
    b = sid.band([0.1, 0.2, 0.3] * 20, "normal", 9.0)
    assert b.unsure >= b.accept - sid.MARGIN_MAX - 1e-9
    assert sid.margin_of(None) == 0.05 and sid.margin_of(float("inf")) == 0.05


def test_the_bank_file_round_trips(tmp_path):
    emb = FakeEmbedder()
    bank = make_bank(0.2, emb, speakers=5)
    f = tmp_path / "impostors-x.bin"
    sid.write_bank(f, bank.rows, list(bank.kinds), {"model_sha256": "abc", "source": "test"})
    back = sid.read_bank(f)
    assert back.meta["model_sha256"] == "abc" and back.meta["kinds"] == [10, 10, 10]
    assert len(back.rows) == 30 and back.kinds == bank.kinds
    assert abs(sid.dot(back.rows[3], bank.rows[3]) - 1) < 1e-2  # float16
    f.write_bytes(b"not a bank")
    assert sid.read_bank(f) is None


# ----------------------------------------------------------------------------------------------- decide
T = sid.Thresholds(sid.Band(0.5, 0.45), sid.Band(0.42, 0.37))


def test_decide_rows():
    assert sid.decide(None, None, 3, missing="no voice print").decision == "unsure"
    assert sid.decide(0.9, T, 3, missing="locked").why == "locked"
    assert sid.decide(0.9, T, 3, sid.Ctx(voices=2)).why == "two voices"
    assert sid.decide(0.55, T, 3).decision == "owner"
    assert sid.decide(0.47, T, 3).decision == "unsure"
    assert sid.decide(0.2, T, 3).decision == "guest"
    short = sid.decide(0.44, T, 2.0)  # short thresholds: accept 0.42
    assert short.decision == "owner" and short.short
    assert sid.decide(0.9, T, 0.6).why == "too short to tell"


def test_carry_only_in_the_same_session_within_carry_s_and_not_clearly_someone_else():
    ctx = sid.Ctx(portal_session=3, last_owner_at=100.0, last_owner_session=3, now=108.0)
    v = sid.decide(0.4, T, 0.6, ctx)
    assert v.decision == "owner" and v.carried and v.why == "a short reply right after you"
    other = sid.Ctx(portal_session=4, last_owner_at=100.0, last_owner_session=3, now=108.0)
    assert sid.decide(0.4, T, 0.6, other).decision == "unsure"
    late = sid.Ctx(portal_session=3, last_owner_at=100.0, last_owner_session=3, now=130.0)
    assert sid.decide(0.4, T, 0.6, late).decision == "unsure"
    assert sid.decide(0.1, T, 0.6, ctx).decision == "unsure"  # clearly low: not carried
    assert sid.decide(0.4, T, 0.6, ctx, strict=True).decision == "unsure"
    assert sid.decide(0.4, T, 0.6, ctx, carry=False).decision == "unsure"


def test_the_verdict_travels_without_its_score():
    v = sid.decide(0.55, T, 3)
    assert "score" not in v.public() and v.public()["who"] == "you"


# ---------------------------------------------------------------------------------------------- quality
NORMAL = enrol.BY_KEY["normal"]


def test_quality_checks_say_why():
    assert enrol.quality(pcm(seconds=0.9), NORMAL).reason.startswith("Too short: I heard 0.9 s")
    assert enrol.quality(pcm(clip=True), NORMAL).reason.startswith("Too loud")
    assert enrol.quality(pcm(level=100, noise=5), NORMAL).reason.startswith("Too quiet")
    assert enrol.quality(pcm(level=1500, noise=900), NORMAL).reason.startswith("Too much noise")
    assert enrol.quality(pcm(), NORMAL).ok
    calls = enrol.BY_KEY["calls"]
    assert enrol.quality(pcm(seconds=1.0), calls).ok  # 0.8 s is enough for a short request
    assert "keep it short" in enrol.quality(pcm(seconds=5.0), calls).reason


def test_the_conditions_are_checked_against_the_normal_voice():
    ref = enrol.Ref(level_db=enrol.stats(pcm())["level_db"], noise_db=enrol.stats(pcm())["noise_db"])
    quiet, far, noise = enrol.BY_KEY["quiet"], enrol.BY_KEY["far"], enrol.BY_KEY["noise"]
    assert "more quietly" in enrol.quality(pcm(), quiet, ref).reason
    assert enrol.quality(pcm(level=2500, noise=20), quiet, ref).ok
    assert "step back" in enrol.quality(pcm(), far, ref).reason
    assert "background noise" in enrol.quality(pcm(), noise, ref).reason
    assert enrol.quality(pcm(level=6000, noise=1500), noise, ref).ok


def test_a_microphone_that_evens_out_loudness_still_lets_quiet_and_far_pass():
    """Reported: the quiet step never passed. Automatic gain lifts a quiet voice back to the normal level, and the
    room's noise with it: the speech's height above the noise is what drops."""
    ref = enrol.Ref(level_db=enrol.stats(pcm())["level_db"], noise_db=enrol.stats(pcm())["noise_db"])
    quiet, far = enrol.BY_KEY["quiet"], enrol.BY_KEY["far"]
    lifted = pcm(level=6000, noise=200)  # as loud as before, the noise floor 10 dB up
    assert enrol.quality(lifted, quiet, ref).ok and enrol.quality(lifted, far, ref).ok
    assert "more quietly" in enrol.quality(pcm(level=6000, noise=80), quiet, ref).reason  # 2.5 dB: not quiet


def test_the_phrase_check_uses_the_transcript():
    p = "Seven bright orange kites drifted over the quiet harbour."
    assert enrol.quality(pcm(), NORMAL, transcript="seven bright orange kites drifted over a harbour", prompt=p).ok
    bad = enrol.quality(pcm(), NORMAL, transcript="what's for dinner tonight", prompt=p)
    assert bad.reason.startswith("I didn't hear the sentence")
    assert enrol.quality(pcm(), NORMAL, transcript="anything", prompt=p, own_words=True).ok


def test_the_voice_checks_copies_and_someone_else():
    emb = FakeEmbedder()
    a = [emb.vec(1, i) for i in range(3)]
    assert "identical" in enrol.voice_checks(emb.vec(1, 2), a).reason
    assert enrol.voice_checks(emb.vec(1, 9), a[:2] + [emb.vec(1, 5)]).ok
    assert enrol.voice_checks(emb.vec(42, 9), a[:2]).ok  # only from the 4th sample on
    assert "someone else" in enrol.voice_checks(emb.vec(42, 9), a).reason


def test_control_words():
    assert enrol.control_word("Stop.") == "stop" and enrol.control_word("skip this") == "skip"
    assert enrol.control_word("say it again") == "repeat"
    assert enrol.control_word("stop the kettle before it boils over") == ""


# ---------------------------------------------------------------------------------------------- session
class Mic:
    """Gives the owner's synthetic samples in order, or what a script says (None: a timeout)."""

    def __init__(self, script=None, voice=1):
        self.script = list(script or [])
        self.n = 0
        self.voice = voice
        self.cuts: list[enrol.Cut] = []

    def __call__(self, timeout, cancel):
        if cancel.is_set():
            return None
        self.n += 1
        item = self.script.pop(0) if self.script else "auto"
        if item is None or callable(item):
            if callable(item):
                item()
            return None
        cut = item if isinstance(item, enrol.Cut) else None
        if cut is None:
            cut = self.auto()
        self.cuts.append(cut)
        return cut

    def auto(self):
        return pcm(self.voice, self.n, seconds=2.0)


class Plan:
    """What the session asks for next decides the sample: quiet/far softer, noise noisier, calls short, free long."""

    def __init__(self, s_ref):
        self.s = s_ref
        self.n = 0

    def __call__(self, timeout, cancel):
        if cancel.is_set():
            return None
        self.n += 1
        sess = self.s() if callable(self.s) else self.s[0]
        while sess is None:  # the session object isn't handed over yet
            threading.Event().wait(0.01)
            sess = self.s()
        c = sess.cond.key
        kw = {"normal": {}, "quiet": {"level": 2500, "noise": 20}, "far": {"level": 2500, "noise": 20},
              "noise": {"noise": 1500}, "calls": {"seconds": 1.4}, "free": {"seconds": 10.0}}[c]  # fmt: skip
        return pcm(1, self.n, **kw)


def session(capture, stt=None, **kw):
    said, events = [], []
    emb = FakeEmbedder()
    s = enrol.Session(
        capture=capture, embed=emb, stt=stt, speak=said.append, publish=lambda k, **f: events.append((k, f)),
        rng=random.Random(1), timeout_s=0.01, idle_s=0.3, **kw,
    )  # fmt: skip
    return s, said, events, emb


def test_a_session_walks_all_six_conditions():
    holder = []
    s, said, events, emb = session(lambda t, c: Plan(holder)(t, c))
    holder.append(s)
    p = Plan(holder)
    s.capture = p
    assert s.run() == "done"
    assert s.vectors() == 21 and s.enough() == (True, "")
    assert {x["cond"] for x in s.samples} == {"normal", "quiet", "far", "noise", "calls", "free"}
    assert all(a["ok"] for a in s.attempts) and len(s.attempts) == 19
    assert said[0].startswith("Voice enrolment.") and said[-1] == "That's all twenty-one."
    assert any("step back about two metres" in x for x in said)
    assert any(k == "voiceid_attempt" for k, _ in events)
    for _k, f in events:  # never a vector, sound or transcript
        assert not any(isinstance(v, list) and len(v) > 16 for v in f.values())


def test_rejections_say_why_with_their_number():
    s, said, _e, _emb = session(None)
    s.capture = Mic([pcm(1, 1, seconds=0.9), pcm(1, 2)])
    s.plan = [enrol.Condition("normal", "n", "n", 1, 1.5)]
    s.run()
    assert s.attempts[0]["ok"] is False and s.message == "#2: got it."
    assert said[2].startswith("Too short") and said[2].endswith("Once more.")


def test_control_words_skip_stop_and_are_never_samples():
    words = iter(["PROMPT", "skip", "stop"])
    box = []
    s, _said, _e, _emb = session(None, stt=lambda pcm: (lambda w: box[0].prompt if w == "PROMPT" else w)(next(words)))
    box.append(s)
    s.capture = Mic()
    s.plan = [enrol.BY_KEY["normal"]]
    s.plan[0] = enrol.Condition("normal", "n", "n", 3, 1.5)
    s.plan.append(enrol.BY_KEY["quiet"])
    assert s.run() == "stopped"
    assert s.vectors() == 1 and s.done_in("normal") == 1  # "skip" can't skip the normal voice; "stop" ends it


def test_skip_pause_continue_keep():
    s, _said, _e, _emb = session(None)
    s.plan = [enrol.Condition("normal", "n", "n", 1, 1.5), enrol.BY_KEY["quiet"], enrol.BY_KEY["far"]]
    s.capture = Mic([pcm(1, 1), lambda: s.command("skip"), lambda: s.command("pause"), "auto", "auto", "auto"])
    t = threading.Thread(target=s.run)
    t.start()
    for _ in range(100):
        if s.state == "paused":
            break
        threading.Event().wait(0.01)
    assert s.state == "paused" and s.skipped == ["quiet"]
    s.command("keep")
    t.join(2)
    assert s.state == "kept" and s.vectors() == 1


def test_two_timeouts_pause_then_idle_ends_it():
    s, said, _e, _emb = session(None)
    s.capture = Mic([None, None])
    assert s.run() == "stopped"
    assert any("I'm pausing" in x for x in said) and "ten minutes" in s.message


def test_the_minimum_to_build():
    emb = FakeEmbedder()
    s, *_ = session(Mic())
    s.existing = owner_samples(emb, 11)
    assert not s.enough()[0]
    s.existing = [dict(x, cond="normal") for x in owner_samples(emb, 14)]
    assert "short requests" in s.enough()[1]
    s.existing = [dict(x, cond=c) for x, c in zip(owner_samples(emb, 14), ["normal", "calls"] * 7, strict=True)]
    assert "3 conditions" in s.enough()[1]
    s.existing[0]["cond"] = "far"
    assert s.enough() == (True, "")


def test_sound_buffers_are_zeroed_after_each_sample():
    s, *_ = session(None)
    m = Mic()
    s.capture = m
    s.plan = [enrol.Condition("normal", "n", "n", 2, 1.5)]
    s.run()
    assert m.cuts and all(not c.pcm for c in m.cuts) and s.held == len(m.cuts)


# ---------------------------------------------------------------------------------------------- adapter
def enrolled_template(emb, bank):
    res = sid.calibrate(owner_samples(emb), bank)
    c = sid.to_b64(res["centroid"])
    return {"centroid": c, "centroid_enrolled": c, "thresholds": res["thresholds"].to_dict(), "adapted": []}


def test_the_adapter_takes_only_confident_long_owner_turns_with_caps():
    emb = FakeEmbedder()
    bank = make_bank(0.3, emb)
    tpl = enrolled_template(emb, bank)
    a = sid.Adapter(bank)
    e = emb.vec(1, 500)
    acc = sid.Thresholds.from_dict(tpl["thresholds"]).long.accept
    good = sid.Verdict("owner", "your voice", acc + 0.2, 3.0)
    assert a.consider(tpl, e, sid.Verdict("owner", "a short reply right after you", 0.9, 3, carried=True), None,
                      "2026-10-27") == (False, "not a sure turn")  # fmt: skip
    assert a.consider(tpl, e, sid.Verdict("unsure", "not sure it was you", 0.9, 3), None, "d")[0] is False
    assert a.consider(tpl, e, sid.Verdict("owner", "your voice", acc + 0.01, 3), None, "d")[1] == "not sure enough"
    assert a.consider(tpl, e, sid.Verdict("owner", "your voice", 0.99, 1.5), None, "d")[1] == "too short"
    assert a.consider(tpl, e, good, 2, "d")[1] == "two voices"
    for i in range(3):
        assert a.consider(tpl, emb.vec(1, 600 + i), good, None, "2026-10-27", per_day=2, cap=3)[0] is (i < 2)
    assert len(tpl["adapted"]) == 2
    for i in range(3):
        a.consider(tpl, emb.vec(1, 700 + i), good, None, f"2026-10-{28 + i}", per_day=2, cap=3)
    assert len(tpl["adapted"]) == 3 and tpl["adapted"][0]["day"] == "2026-10-28"  # FIFO
    assert tpl["centroid"] != tpl["centroid_enrolled"] and "calibrated" in tpl  # thresholds derived again


def test_the_drift_guard_and_undo():
    emb = FakeEmbedder()
    bank = make_bank(0.3, emb)
    tpl = enrolled_template(emb, bank)
    a = sid.Adapter(bank)
    good = sid.Verdict("owner", "your voice", 0.99, 3.0)
    look_alike = FakeEmbedder(spread=0.0)
    took = [a.consider(tpl, look_alike.vec(77, 0), good, None, "2026-10-27", per_day=50, cap=50)[1] for _ in range(1)]
    assert took == ["drift"] and tpl["drift_stopped"] and tpl["adapted"] == []
    tpl["drift_stopped"] = False
    a.consider(tpl, emb.vec(1, 801), good, None, "2026-10-26")
    a.consider(tpl, emb.vec(1, 802), good, None, "2026-10-27")
    assert a.undo(tpl, "today", "2026-10-27") == 1 and len(tpl["adapted"]) == 1
    assert a.undo(tpl, "all", "2026-10-27") == 1 and tpl["adapted"] == []
    assert sid.from_b64(tpl["centroid"]) == pytest.approx(sid.from_b64(tpl["centroid_enrolled"]), abs=2e-3)


# --------------------------------------------------------------------------------------------- the store
class Secrets:
    def __init__(self):
        self.d = {}

    def get(self, k):
        return self.d.get(k)

    def set(self, k, v):
        self.d[k] = v

    def delete(self, k):
        self.d.pop(k, None)


def store(tmp_path):
    app = SimpleNamespace(paths=SimpleNamespace(state=tmp_path), secrets=Secrets())
    return BioStore(app, "voice"), app


def test_the_template_is_sealed_and_round_trips(tmp_path):
    st, app = store(tmp_path)
    v = FakeEmbedder().vec(1, 1)
    data = {"samples": [{"e": sid.to_b64(v), "cond": "normal"}], "centroid": sid.to_b64(v)}
    assert st.load() is None and not st.exists()
    st.save(data)
    assert st.file == tmp_path / "voiceid" / "template.bin"
    raw = st.file.read_bytes()
    for bad in (b"samples", b"centroid", sid.to_b64(v).encode()[:16], base64.b64decode(sid.to_b64(v))[:16]):
        assert bad not in raw
    assert st.load()["samples"][0]["cond"] == "normal"
    assert app.secrets.get("biometric.voice.key")
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(st.file).st_mode) == 0o600
        assert stat.S_IMODE(os.stat(st.dir).st_mode) == 0o700


def test_a_wrong_key_or_a_flipped_byte_is_locked_and_forget_deletes_both(tmp_path):
    st, app = store(tmp_path)
    st.save({"x": 1})
    raw = bytearray(st.file.read_bytes())
    raw[20] ^= 1
    st.file.write_bytes(bytes(raw))
    with pytest.raises(Locked):
        st.load()
    st.save({"x": 2})
    app.secrets.set("biometric.voice.key", base64.b64encode(os.urandom(32)).decode())
    with pytest.raises(Locked):
        st.load()
    app.secrets.delete("biometric.voice.key")
    with pytest.raises(Locked):
        st.load()
    with pytest.raises(Locked):  # never a new key over an old template
        st.save({"x": 3})
    assert st.forget() is True
    assert not st.file.exists() and app.secrets.get("biometric.voice.key") is None
    assert st.forget() is False


def test_the_key_and_the_folder_never_travel(tmp_path):
    from kurooto.core import profile
    from kurooto.diagnostics import KNOWN_SECRETS
    from kurooto.modules import backups

    assert "biometric.voice.key" in KNOWN_SECRETS and "biometric.voice.key" in profile.NEVER
    assert "voiceid" in backups.SKIP_STATE_DIRS
    sec = Secrets()
    sec.names = lambda: ["biometric.voice.key", "telegram.token"]
    assert "biometric.voice.key" not in backups.known_secret_names(sec)


def test_backups_skip_the_voice_print(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.core.paths import paths
    from kurooto.modules import backups

    p = paths()
    (p.state / "voiceid").mkdir(parents=True, exist_ok=True)
    (p.state / "voiceid" / "template.bin").write_bytes(b"sealed")
    (p.state / "deadlines.json").write_text("{}")
    names = [arc for arc, _f in backups.sources(p, None, notes=False, secrets=False, index=False)]
    assert any(n.endswith("deadlines.json") for n in names)
    assert not any("voiceid" in n for n in names)


# ---------------------------------------------------------------------------------------------- parts
def test_what_voice_id_needs(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    try:
        v = app.modules["voice"]
        assert not any("voiceid" in k for k in v.wants())
        app.settings.set("voice.speaker_id.on", True)
        w = v.wants()
        assert {"pkg:voiceid", "model:voiceid-campplus-en", "pkg:listen", "model:vad"} <= set(w)
        app.settings.set("voice.speaker_id.model", "campplus-multi")
        assert "model:voiceid-campplus-multi" in v.wants()
    finally:
        app.close()


def parts(tmp_path, monkeypatch, content=b"model bytes"):
    import hashlib

    from kurooto.modules.voice import parts as pm

    p = pm.Parts(tmp_path / "voice", tmp_path)
    digest = hashlib.sha256(content).hexdigest()
    p.table["voiceid-campplus-en"] = [pm.ModelFile("voiceid/tiny.onnx", "https://github.com/x/tiny.onnx", 0.1, digest)]
    return p, pm


class Resp:
    def __init__(self, data):
        self.data, self.headers = data, {"Content-Length": str(len(data))}

    def read(self, n):
        out, self.data = self.data[:n], self.data[n:]
        return out

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_a_download_is_checked_against_its_checksum(tmp_path, monkeypatch):
    p, pm = parts(tmp_path, monkeypatch)
    monkeypatch.setattr(pm.egress, "urlopen", lambda url, feature, timeout=60: Resp(b"changed bytes"))
    ok, msg = p.download_model("voiceid-campplus-en", lambda m: None)
    assert not ok and "didn't match its checksum" in msg and "nothing was kept" in msg
    assert not list((tmp_path / "voice" / "models").rglob("*"))[1:]  # no file, no .part
    assert not p.has_model("voiceid-campplus-en")
    monkeypatch.setattr(pm.egress, "urlopen", lambda url, feature, timeout=60: Resp(b"model bytes"))
    assert p.download_model("voiceid-campplus-en", lambda m: None)[0] and p.has_model("voiceid-campplus-en")


def test_install_from_a_file(tmp_path, monkeypatch):
    p, pm = parts(tmp_path, monkeypatch)
    good = tmp_path / "in" / "tiny.onnx"
    good.parent.mkdir()
    good.write_bytes(b"model bytes")
    ok, msg = p.add_file(good)
    assert ok and p.has_model("voiceid-campplus-en")
    bad = tmp_path / "in2" / "tiny.onnx"
    bad.parent.mkdir()
    bad.write_bytes(b"something else")
    p2, _ = parts(tmp_path / "b", monkeypatch)
    assert "didn't match" in p2.add_file(bad)[1] and not p2.has_model("voiceid-campplus-en")
    stray = tmp_path / "in" / "x.onnx"
    stray.write_bytes(b"1")
    assert "isn't a part" in p.add_file(stray)[1]
    kokoro = tmp_path / "kokoro-v1.0.onnx"
    kokoro.write_bytes(b"k")
    assert "no checksum pinned" in p.add_file(kokoro)[1]


def test_a_wheel_is_installed_with_no_index(tmp_path, monkeypatch):
    p, pm = parts(tmp_path, monkeypatch)
    ran = []
    monkeypatch.setattr(p, "installer", lambda: ["uv", "pip", "install", "--python", "py"])
    monkeypatch.setattr(pm.proc, "run", lambda cmd, timeout=0: ran.append(cmd) or SimpleNamespace(ok=True))
    whl = tmp_path / "w" / "kaldi_native_fbank-1.22.1-cp312-cp312-manylinux.whl"
    whl.parent.mkdir()
    whl.write_bytes(b"w")
    ok, _msg = p.add_file(whl)
    assert ok and ran[0][-1] == str(whl)
    assert ran[0][5:9] == ["--no-index", "--find-links", str(whl.parent), "--target"]
    other = tmp_path / "w" / "requests_oauth-1.0-py3-none-any.whl"
    other.write_bytes(b"w")
    assert "isn't a package" in p.add_file(other)[1]


# --------------------------------------------------------------------------------------- the module, API
class Live:
    def __init__(self):
        self.sent = []

    def push(self, msg, only=None):
        self.sent.append(json.loads(json.dumps(msg, default=str)))

    def watched(self):
        return True


@pytest.fixture
def vid(tmp_path, monkeypatch):
    """Voice on, listening on, Voice ID on with a fake model and bank; nothing enrolled yet."""
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    v = app.modules["voice"]
    monkeypatch.setattr(v.parts, "missing", lambda keys: [])
    monkeypatch.setattr(v, "_on_call", lambda: False)
    monkeypatch.setattr(v, "_night", lambda: False)
    monkeypatch.setattr(v, "microphone", lambda: (True, "Test mic"))
    app.live = Live()
    assert app.enable("voice")[0]
    app.settings.set("voice.listen.on", True)
    app.settings.set("voice.speaker_id.on", True)
    emb = FakeEmbedder()
    bank = make_bank(0.3, emb)
    bank.meta["model_sha256"] = v.voiceid.model_sha()
    x = v.voiceid
    x.embed_fn = emb
    x.stt_fn = lambda pcm: ""
    monkeypatch.setattr(x, "bank", lambda: bank)
    x.emb = emb
    yield x
    app.close()


def enrol_owner(x) -> dict:
    raw = owner_samples(x.emb)
    return x.train(session=SimpleNamespace(existing=[], samples=raw))


def test_train_saves_a_good_template_and_status_holds_no_vector(vid):
    assert not vid.enrolled() and vid.problem() == "no voice print"
    out = enrol_owner(vid)
    assert out["ok"] and out["saved"] and out["report"]["grade"] == "good"
    assert vid.enrolled() and vid.store.exists()
    from kurooto.web.api import Api

    code, st = Api(vid.app).get("voice/id")
    assert code == 200 and st["enrolled"] and st["grade"] == "good" and st["samples"]["total"] == 21

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            assert not (len(o) > 16 and all(isinstance(v, float) for v in o)), "a vector in the answer"
            for v in o:
                walk(v)

    walk(st)
    for e in vid.app.events.tail(200):  # numbers that are vectors or scores never go into the event log
        assert not any(isinstance(v, float) for v in e.values() if not isinstance(v, bool)) or e["kind"] in (
            "job_done",
        ), e


def test_a_weak_template_waits_for_use_it_anyway(vid, monkeypatch):
    noisy = FakeEmbedder(spread=1.4)
    bank = make_bank(1.2, noisy)
    bank.meta["model_sha256"] = vid.model_sha()
    monkeypatch.setattr(vid, "bank", lambda: bank)
    vid.app.settings.set("voice.speaker_id.strictness", "strict")
    out = vid.train(session=SimpleNamespace(existing=[], samples=owner_samples(noisy)))
    assert out["ok"] and not out["saved"] and not vid.enrolled() and "weak" in out["message"]
    from kurooto.web.api import Api

    code, r = Api(vid.app).post("voice/id/train", {"use_anyway": True})
    assert r["saved"] and vid.enrolled()


def test_a_mismatched_impostor_set_refuses_to_train(vid, monkeypatch):
    bank = make_bank(0.3, vid.emb, speakers=3)
    monkeypatch.setattr(vid, "bank", lambda: bank)
    out = enrol_owner(vid)
    assert not out["ok"] and "doesn't match this model" in out["message"]


def test_forget_deletes_the_file_and_the_key_from_every_way(vid):
    enrol_owner(vid)
    assert vid.app.secrets.get("biometric.voice.key")
    from kurooto.web.api import Api

    api = Api(vid.app)
    assert api.post("voice/id/forget", {})[1]["ok"] is False  # it needs the confirm
    assert api.post("voice/id/forget", {"confirm": True})[1]["ok"]
    assert not vid.store.exists() and vid.app.secrets.get("biometric.voice.key") is None and not vid.enrolled()
    assert any(e["kind"] == "voiceid_forgotten" for e in vid.app.events.tail(20))
    enrol_owner(vid)
    assert vid.app.callback("vid:0:forget").startswith("Forgot your voice")
    assert not vid.store.exists()


def test_forget_all_includes_the_voice_print(vid):
    from kurooto.core import retention

    enrol_owner(vid)
    text, buttons = retention.command(vid.app, "all")
    assert "your voice print (Voice ID)" in text
    ref = buttons[0][0][1].split(":")[1]
    retention.button(vid.app, ref, "all")
    assert not vid.store.exists() and vid.app.secrets.get("biometric.voice.key") is None


def test_a_session_through_the_api_builds_the_template(vid):
    vid.capture_with = Plan(lambda: vid.session)
    vid.stt_fn = lambda pcm: vid.session.prompt if vid.session else ""  # it heard the sentence
    from kurooto.web.api import Api

    api = Api(vid.app)
    r = api.post("voice/id/session", {"action": "start"})[1]
    assert r["ok"], r
    vid._thread.join(20)
    assert vid.enrolled() and vid.capturing == ""
    st = api.get("voice/id")[1]
    assert st["grade"] in ("good", "fair") and st["samples"]["total"] == 21
    assert all(m.get("kind", "").startswith(("voice", "voiceid")) for m in vid.app.live.sent)
    for m in vid.app.live.sent:
        assert not any(isinstance(v, list) and len(v) > 16 for v in m.values())


def test_a_sentence_still_going_at_the_timeout_is_waited_for(vid, monkeypatch):
    """Reported: the test said it heard nothing. Speech that began inside the window was dropped when the window
    closed before the sentence ended; now it's waited for to its end."""
    import time

    from kurooto.modules.voice import audio

    def frames(n, amp):
        r = random.Random(n)
        return [array.array("h", [int(amp * math.sin(i / 3) + r.gauss(0, 30)) for i in range(audio.FRAME)]).tobytes()
                for _ in range(n)]  # fmt: skip

    class SlowMic:  # quiet, then 1.6 s of loud "speech" over about 0.6 s, then quiet
        def __init__(self, device=""):
            self.closed = False

        def frames(self):
            for f in frames(5, 0):
                yield f
            for f in frames(50, 6000):
                time.sleep(0.012)
                yield f
            while not self.closed:
                time.sleep(0.005)
                yield frames(1, 0)[0]

        def close(self):
            self.closed = True

    monkeypatch.setattr(audio, "Mic", SlowMic)
    monkeypatch.setattr(vid.v.parts, "has_model", lambda key: False)  # the energy VAD
    vid.capture_with = None
    capture, close = vid._mic_capture(15)
    try:
        cut = capture(0.2, threading.Event())  # speech starts inside 0.2 s and ends well after it
    finally:
        close()
    assert cut is not None and cut.speech_s > 1.0


def test_the_test_step_scores_me_and_someone_else(vid):
    enrol_owner(vid)
    vid.capture_with = lambda t, c: pcm(1, 900, seconds=3.0)
    me = vid.test("me")
    assert me["ok"] and me["decision"] == "owner" and me["pass"] and 0 < me["score"] <= 1
    vid.capture_with = lambda t, c: pcm(55, 3, seconds=3.0)
    other = vid.test("other")
    assert other["decision"] == "guest" and other["pass"]
    lt = vid.template()["last_test"]
    assert (lt["me_tries"], lt["me_passed"], lt["other_tries"], lt["other_passed"]) == (1, 1, 1, 1)
    assert vid.test("synthetic")["ok"] is False  # no Kokoro here


def test_improving_and_its_undo_through_the_api(vid):
    enrol_owner(vid)
    vid.app.settings.set("voice.speaker_id.adapt", True)
    for i in range(3):
        vid.check(bytes(pcm(1, 1000 + i, seconds=3.0).pcm), 3.0)
    assert len(vid.template()["adapted"]) == 3
    from kurooto.web.api import Api

    r = Api(vid.app).post("voice/id/adapt", {"undo": "all"})[1]
    assert r["ok"] and r["count"] == 0 and vid.template()["adapted"] == []


def test_the_card_and_its_switches(vid):
    v = vid.v
    assert "doesn't know your voice yet" in v.card()["lines"][0]
    assert "open Your voice" in v.card_action("speaker_id.on", True)
    assert v.card_action("speaker_id.adapt", True) == "Improving over time: on." and vid.s("adapt")
    assert v.card_action("speaker_id.on", False) == "Voice ID: off." and not vid.on()


def test_the_page_is_served(vid):
    from importlib import resources

    html = resources.files("kurooto.web").joinpath("static", "voiceid.html").read_text(encoding="utf-8")
    js = resources.files("kurooto.web").joinpath("static", "voiceid.js").read_text(encoding="utf-8")
    assert "Capture" in html and "Train" in html and "Improve" in html and "voiceid.js" in html
    assert "api/voice/id" not in js or "voice/id" in js
    assert "/voice-id" in resources.files("kurooto.web").joinpath("static", "home.js").read_text(encoding="utf-8")


@pytest.mark.skipif(not os.environ.get("KUROOTO_TEST_MODELS"), reason="needs KUROOTO_TEST_MODELS with the CAM++ file")
def test_the_real_model_on_synthetic_noise():
    f = Path(os.environ["KUROOTO_TEST_MODELS"]) / "3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx"
    if not f.is_file():
        pytest.skip("the model file isn't there")
    e = sid.Embedder(f)
    r = random.Random(3)
    noise = struct.pack("<48000h", *(int(r.gauss(0, 3000)) for _ in range(48000)))
    v = e.embed(noise)
    assert len(v) == int(e.meta.get("output_dim", len(v))) and abs(sid.dot(v, v) - 1) < 1e-4
    assert e.rate == 16000


def test_add_samples_kept_for_later_keeps_the_voice_print_in_use(vid):
    """Manage -> Add samples, then Keep for later: the voice print still checks turns (it once lost its centroid and
    every turn crashed); a Retrain takes the new samples in."""
    enrol_owner(vid)
    more = owner_samples(vid.emb, 2, conds=["other"] * 2, start=500)
    vid._keep(SimpleNamespace(existing=owner_samples(vid.emb), samples=more))
    assert vid.enrolled() and vid.problem() == ""
    assert len(vid.template()["samples"]) == 23
    v = vid.check(bytes(pcm(1, 901, seconds=3.0).pcm), 3.0)
    assert v.decision == "owner"
    vid._tpl = {k: x for k, x in vid.template().items() if k != "centroid"}  # damaged: never a crash, unsure
    assert vid.problem() == "no voice print"
    assert vid.check(bytes(pcm(1, 902, seconds=3.0).pcm), 3.0).decision == "unsure"


def test_a_low_threshold_setting_never_lets_a_stranger_act(vid):
    enrol_owner(vid)
    vid.app.settings.set("voice.speaker_id.threshold", 0.01)
    th = vid.thresholds(vid.template())
    assert th.long.accept == th.short.accept == sid.OVERRIDE[0]
    stranger = vid.check(bytes(pcm(55, 3, seconds=3.0).pcm), 3.0)
    assert stranger.decision != "owner"


def test_start_over_keeps_the_old_voice_print_until_the_new_one_is_built_and_undo_puts_it_back(vid):
    enrol_owner(vid)
    old = vid.template()
    vid.capture_with = Plan(lambda: vid.session)
    vid.stt_fn = lambda pcm: vid.session.prompt if vid.session else ""
    from kurooto.web.api import Api

    api = Api(vid.app)
    r = api.post("voice/id/session", {"action": "again"})[1]
    assert r["ok"], r
    assert len(vid.session.plan) == 6 and vid.session.existing == []  # the whole plan, from nothing
    assert vid.enrolled() and vid.template()["centroid"] == old["centroid"]  # still in use meanwhile
    vid._thread.join(20)
    new = vid.template()
    assert vid.enrolled() and new["centroid"] != old["centroid"] and len(new["samples"]) == 21
    assert api.get("voice/id")[1]["can_undo"]
    assert api.post("voice/id/undo", {})[1]["ok"]
    assert vid.template()["centroid"] == old["centroid"] and vid.template()["samples"] == old["samples"]


def test_a_start_over_kept_for_later_goes_on_with_the_whole_plan(vid):
    enrol_owner(vid)
    old = vid.template()
    some = owner_samples(vid.emb, 6, conds=["normal"] * 5 + ["quiet"], start=700)
    vid._keep(SimpleNamespace(existing=[], samples=some, fresh=True))
    t = vid.template()
    assert t["reenrol"] and len(t["samples"]) == 6 and t["centroid"] == old["centroid"] and vid.enrolled()
    assert vid.previous is old  # Undo brings the old samples back too
    vid.capture_with = lambda timeout, cancel: None  # nothing heard: it only has to start
    r = vid.start_session()
    assert r["ok"] and len(vid.session.plan) == 6 and len(vid.session.existing) == 6
    vid.session.command("stop")
    vid._thread.join(5)
