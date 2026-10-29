"""Voice ID per microphone and "that was me" (0.9.2; modules/voice/devices.py, voiceid.py; voice.speaker_id.per_device,
voice.speaker_id.claim). Fakes only: the owner "through a phone" is his fake vector pulled toward a fixed channel
direction, so the enrolled print is unsure of him there; no microphone, no model, no real voice."""

# ruff: noqa: S311

from __future__ import annotations

import time

import pytest

from kurooto.modules.voice import devices
from kurooto.modules.voice import speakerid as sid
from tests.unit.test_voiceid import FakeEmbedder, enrol_owner, gauss, make_bank, pcm, vid  # noqa: F401

CH = sid.normalize(gauss(4242))


def phone(emb):
    """The owner's voice heard through another microphone: the same base, pulled toward the channel."""
    return lambda raw: sid.normalize([a + 1.5 * c for a, c in zip(emb(raw), CH, strict=True)])


class PhoneEmb(FakeEmbedder):
    def vec(self, voice, utt, cold=0):
        return sid.normalize([a + 1.5 * c for a, c in zip(super().vec(voice, utt, cold), CH, strict=True)])


def turn(i, voice=1, seconds=3.0):
    return bytes(pcm(voice, 3000 + i, seconds=seconds).pcm)


@pytest.fixture
def on_phone(vid, monkeypatch):  # noqa: F811
    """Enrolled on "Test mic"; now listening through "Body mic", his face alone in view, nothing being said."""
    enrol_owner(vid)
    vid.app.settings.set("voice.listen.device", "Body mic")
    vid.app.settings.set("voice.speaker_id.face_assist", False)  # the print's own verdicts, not the face's help
    vid.app.settings.set("voice.speaker_id.per_device_per_day", 20)  # a day's cap of 10 would take two days here
    vid.embed_fn = phone(vid.emb)
    pb = make_bank(0.3, PhoneEmb())  # the impostors heard through the same channel
    pb.meta.update(model_sha256=vid.model_sha(), channel="phone (simulated)")
    vid._banks[f"{vid.model()}-phone"] = pb
    monkeypatch.setattr(vid, "face_owner", lambda: True)
    vid.v.speaker.until = 0.0
    sent = []
    monkeypatch.setattr(vid.app, "notify", lambda text, **kw: sent.append((text, kw)))
    vid.sent = sent
    return vid


def wait_built(x, dev="Body mic", s=5.0):
    end = time.monotonic() + s
    while time.monotonic() < end:
        d = devices.entry(x.template(), dev) or {}
        if d.get("print") and not x._building:
            return d
        time.sleep(0.02)
    raise AssertionError("not built")


# ------------------------------------------------------------------------------------------------ the rules
def test_enrolled_on_by_mic_or_mics_and_unknown_counts_as_it():
    assert devices.enrolled_on({"mic": "Test mic"}, "Test mic")
    assert not devices.enrolled_on({"mic": "Test mic"}, "Body mic")
    assert devices.enrolled_on({"mics": ["Body mic via pipewire"]}, "Body mic")
    assert devices.enrolled_on({}, "anything")  # an older print that doesn't say: as before


def test_samples_are_capped_a_day_and_in_all_and_due_at_twelve():
    d = devices.new()
    e = sid.normalize(gauss(1))
    for _i in range(3):
        assert devices.add(d, e, "face", "2026-10-29", 3)[0]
    assert devices.add(d, e, "face", "2026-10-29", 3) == (False, "enough for today")
    assert devices.add(d, e, "claim", "2026-10-29", 3)[0]  # a claim has its own count
    for i in range(60):
        devices.add(d, e, "face", f"day{i}", 3)
    assert len(d["samples"]) == devices.KEEP_MAX and devices.due(d)
    d["built_n"], d["state"] = devices.KEEP_MAX - 2, "weak"
    assert not devices.due(d)  # a weak one is built again only after REBUILD_EVERY more
    devices.decide(d, False)
    assert d["state"] == "declined" and d["samples"] == [] and not devices.add(d, e, "face", "x", 3)[0]


# ------------------------------------------------------------------------------------------------ bootstrap
def test_a_phone_microphone_learns_its_own_print_and_asks_once(on_phone):
    x = on_phone
    assert x.device() == "Body mic" and not devices.enrolled_on(x.template(), "Body mic")
    before = [x.check(turn(i), 3.0).decision for i in range(4)]
    assert "owner" not in before  # the enrolled print doesn't know him through this microphone
    for i in range(4, 12):
        x.check(turn(i), 3.0)
    d = wait_built(x)
    assert d["state"] == "ready" and d["print"]["bank"] == "phone" and len(d["samples"]) == 12
    assert len(x.sent) == 1 and x.sent[0][1]["why"] == "voice.id_device"
    ((use, no),) = x.sent[0][1]["buttons"]
    assert use[1].endswith(":devuse") and no[1].endswith(":devno") and "Body mic" not in use[1]
    assert x.check(turn(50), 3.0).decision != "owner"  # not used before his yes
    ref = use[1].split(":")[1]
    assert "now knows you" in x._button(ref, "devuse")
    assert devices.entry(x.template(), "Body mic")["state"] == "on"
    assert x.check(turn(51), 3.0).decision == "owner"  # its own print now
    assert x.check(bytes(pcm(77, 5, seconds=3.0).pcm), 3.0).decision != "owner"  # a stranger there still isn't
    x.app.settings.set("voice.listen.device", "")  # back on the enrolment's microphone: the enrolled print
    x.embed_fn = x.emb
    assert x.check(turn(52), 3.0).decision == "owner"


def test_only_proven_turns_are_samples(on_phone, monkeypatch):
    x = on_phone

    def n():
        return len((devices.entry(x.template(), "Body mic") or {}).get("samples") or [])

    x.check(turn(1), 1.5)  # under 2 s
    x.check(turn(2), 3.0, voices=2)  # two voices
    x.check(turn(3), 3.0, adapt=False)  # spoken over its own voice
    x.v.speaker.until = time.monotonic()  # it just spoke
    x.check(turn(4), 3.0)
    x.v.speaker.until = 0.0
    monkeypatch.setattr(x, "face_owner", lambda: False)  # his face isn't alone in view
    x.check(turn(5), 3.0)
    assert n() == 0
    monkeypatch.setattr(x, "face_owner", lambda: True)
    x.check(turn(6), 3.0)
    assert n() == 1
    x.app.settings.set("voice.speaker_id.per_device", False)
    x.check(turn(7), 3.0)
    assert n() == 1  # off: nothing more kept


def test_no_drops_them_and_forget_starts_again(on_phone):
    x = on_phone
    for i in range(12):
        x.check(turn(i), 3.0)
    wait_built(x)
    out = x.device_answer("1", "no")
    assert out["ok"] and devices.entry(x.template(), "Body mic")["samples"] == []
    x.check(turn(40), 3.0)
    assert devices.entry(x.template(), "Body mic")["state"] == "declined"
    assert x.device_answer("Body mic", "forget")["ok"] and devices.entry(x.template(), "Body mic") is None
    assert "1. Body mic" in x.v._cmd_mics("") or "No other microphone" in x.v._cmd_mics("")


def test_adapt_is_frozen_on_a_microphone_without_its_own_print(on_phone):
    """The fix: before, phone turns refined the enrolled print until the drift guard stopped it for good."""
    x = on_phone
    x.app.settings.set("voice.speaker_id.adapt", True)
    x.app.settings.set("voice.speaker_id.per_device", False)
    x.embed_fn = x.emb  # even turns it's very sure of
    for i in range(5):
        x.check(turn(100 + i), 3.0)
    t = x.template()
    assert t.get("adapted") == [] and not t.get("drift_stopped")
    x.app.settings.set("voice.listen.device", "")  # on the enrolment's microphone it learns as before
    for i in range(3):
        x.check(turn(200 + i), 3.0)
    assert len(x.template()["adapted"]) == 3


def test_status_and_the_api_carry_no_vector(on_phone):
    x = on_phone
    for i in range(3):
        x.check(turn(i), 3.0)
    from kurooto.web.api import Api

    st = Api(x.app).get("voice/id")[1]
    (d,) = st["devices"]
    assert d["name"] == "Body mic" and d["samples"] == 3 and d["state"] == "learning" and d["now"]
    assert all(not isinstance(v, list) for v in d.values())
    r = Api(x.app).post("voice/id/device", {"device": d["ref"], "action": "use"})[1]
    assert not r["ok"] and "no print" in r["message"]
    x.forget()
    assert x.template() is None and x._claim is None


# ------------------------------------------------------------------------------------------- that was me
def test_a_claim_needs_his_face_a_recent_unsure_turn_and_is_capped(on_phone, monkeypatch):
    x = on_phone
    raw = turn(300)
    v = x.check(raw, 3.0)
    assert v.decision == "unsure" and x._claim is not None
    held = x._claim["pcm"]
    monkeypatch.setattr(x, "face_owner", lambda: False)
    assert x.claim()[:2] == (False, "not with only your face in view")
    monkeypatch.setattr(x, "face_owner", lambda: True)
    ok, why, back, speech_s = x.claim()
    assert ok and back == raw and speech_s == 3.0
    assert not any(held)  # the held copy is zeroed
    assert x.claim()[1] == "nothing to claim"
    forced = x.check(back, 3.0)
    assert forced.decision == "owner" and forced.why == "you said it was you" and forced.assisted
    assert x.check(back, 3.0).decision != "owner"  # once only
    x.app.settings.set("voice.speaker_id.claim_per_day", 1)
    x.check(turn(301), 3.0)
    assert x.claim()[1] == "enough claims for today"


def test_a_claim_expires_and_is_dropped(on_phone):
    x = on_phone
    x.check(turn(310), 3.0)
    x._claim["at"] -= 60
    assert x.claim()[1] == "nothing to claim"
    x._drop_claim()
    assert x._claim is None


def test_a_claimed_turn_is_a_sample_for_that_microphone(on_phone):
    x = on_phone
    x.embed_fn = lambda raw: sid.normalize([a + 2.0 * c for a, c in zip(x.emb(raw), CH, strict=True)])
    assert x.check(turn(320), 1.5).decision == "unsure"  # too short to be a face-proven sample, enough for a claim
    assert devices.entry(x.template(), "Body mic") is None
    assert x.claim()[0]
    d = devices.entry(x.template(), "Body mic")
    assert d["samples"][0]["how"] == "claim"


def test_the_tap_claims_and_the_turn_is_heard_again(on_phone, monkeypatch):
    x = on_phone
    v = x.v

    class L:
        def running(self):
            return True

    v.listener = L()
    try:
        x.check(turn(330), 3.0)
        while not v._work.empty():
            v._work.get_nowait()
        assert v.tapped() == (True, "")
        item = v._work.get_nowait()
        assert item[0] == turn(330) and v.portal.open
        ev = [e for e in x.app.events.tail(50) if e["kind"] == "voiceid_claimed"]
        assert ev and not any(isinstance(v, float) for v in ev[-1].values())  # no score in the event log
        x.app.settings.set("voice.speaker_id.claim", False)
        x.check(turn(331), 3.0)
        assert x._claim is None  # off: nothing held
    finally:
        v.listener = None


# ------------------------------------------------------------------------------------------------ the banks
@pytest.mark.parametrize("model", ["campplus-en", "campplus-multi"])
def test_the_phone_banks_ship_and_match_the_plain_ones(model):
    plain, ph = sid.read_bank(sid.bank_path(model)), sid.read_bank(sid.bank_path(model, "phone"))
    assert ph is not None and len(ph.rows) == len(plain.rows) and ph.kinds == plain.kinds
    assert ph.meta["model_sha256"] == plain.meta["model_sha256"] and "simulated" in ph.meta["channel"]


def test_without_a_phone_bank_the_plain_one_is_used(on_phone, monkeypatch):
    x = on_phone
    x._banks[f"{x.model()}-phone"] = None
    assert x.device_bank()[1] == "plain"
