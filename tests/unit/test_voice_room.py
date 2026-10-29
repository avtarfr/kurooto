"""Room modes (0.9.2, modules/voice/room.py) and the one output stage (outstage.py). A mode only tightens Voice's saved
settings and never turns a feature on, ends by itself, is set by /room, the dashboard, the phone's op, a phrase in his
own verified voice and the add-on hook; silent plays nothing, night is quieter; every sound goes through levelling and
a -3 dBFS limiter. Fakes only: no sound device, microphone, camera or model."""

# ruff: noqa: F811 (the fixtures imported from test_voice are taken as arguments)

import array
import math
import struct

import pytest

from kurooto.modules.voice import outstage
from kurooto.modules.voice import room as room_mod
from kurooto.modules.voice.speakerid import Verdict
from tests.unit.test_voice import Speakers, Tts, voice  # noqa: F401 (pytest fixtures)


def events(v, kind):
    return [e for e in v.app.events.tail(200) if e.get("kind") == kind]


# ------------------------------------------------------------------------------------------------- the phrase
@pytest.mark.parametrize(
    "said,mode",
    [
        ("Night mode.", "night"),
        ("night mode please", "night"),
        ("Go silent", "silent"),
        ("switch to company mode", "company"),
        ("room silent", "silent"),
        ("I'm alone now.", "alone"),
        ("end night mode", "alone"),
        ("silent mode off", "alone"),
        ("normal mode", "alone"),
    ],
)
def test_the_phrases(said, mode):
    assert room_mod.phrase(said) == mode


@pytest.mark.parametrize(
    "said",
    ["night", "good night", "it was a silent night", "what mode is the night in", "the company called", "alone",
     "set a reminder for night mode tomorrow at nine because I keep forgetting"],
)  # fmt: skip
def test_ordinary_talk_isnt_a_mode(said):
    assert room_mod.phrase(said) is None


# ------------------------------------------------------------------------------------------------- the table
def test_alone_is_your_settings_as_they_are(voice):
    s = voice.app.settings
    s.set("voice.speak.what", "all")
    s.set("voice.speak.messages", True)
    assert voice.room.mode() == "alone"
    assert voice.setting("speak.what") == "all" and voice.setting("speak.messages") is True


def test_modes_only_tighten_and_never_turn_a_feature_on(voice):
    s = voice.app.settings
    s.set("voice.speak.what", "all")
    s.set("voice.speak.messages", True)
    s.set("voice.speak.ack", "word")
    s.set("voice.listen.live", True)
    s.set("voice.listen.look_anyone", True)
    voice.set_room_mode("company")
    assert voice.setting("speak.what") == "voice" and voice.setting("speak.messages") is False
    assert voice.setting("listen.look_anyone") is False and voice.setting("answers_questions") is False
    assert voice.setting("listen.live") is True  # his own Live turns aren't touched in company
    voice.set_room_mode("night")
    assert voice.setting("speak.ack") == "tone" and voice.setting("speak.on") is True
    voice.set_room_mode("silent")
    assert voice.setting("speak.on") is False and voice.setting("listen.live") is False
    # never on: a switch that's off stays off in every mode, and Voice ID's and Face's settings are never in a table
    s.set("voice.speak.messages", False)
    s.set("voice.listen.live_everyone", False)
    s.set("voice.speak.ack", "off")
    for m in room_mod.MODES:
        voice.set_room_mode(m)
        assert voice.setting("speak.messages") is False and voice.setting("listen.live_everyone") is False
        assert voice.setting("speak.ack") == "off"
    for table in room_mod.TABLE.values():
        assert not any(k.startswith(("speaker_id.", "listen.need_face", "listen.face_")) for k in table)
    assert s.get("voice.speak.what") == "all"  # the saved values are never changed


def test_a_mode_ends_by_itself(voice):
    clock = [1_000_000.0]
    voice.room.clock = lambda: clock[0]
    voice.app.settings.set("voice.room_modes.silent_h", 2)
    ok, said = voice.room.set("silent", by="test")
    assert ok and said.startswith("Silent mode until ")
    clock[0] += 2 * 3600 - 5
    assert voice.room.mode() == "silent"
    clock[0] += 10
    assert voice.room.mode() == "alone" and voice.setting("speak.on") is True
    ev = events(voice, "voice_room")
    assert ev[-1]["mode"] == "alone" and ev[-1]["by"] == "time" and ev[-1]["was"] == "silent"


def test_a_length_and_night_ending_with_the_night_hours(voice, monkeypatch):
    import datetime as dt

    clock = [1_000_000.0]
    voice.room.clock = lambda: clock[0]
    voice.set_room_mode("company", hours=0.5)
    assert voice.room.status()["until"] == pytest.approx(clock[0] + 1800)
    end = dt.datetime.fromtimestamp(clock[0] + 7 * 3600)
    monkeypatch.setattr(voice.app.availability, "night", lambda t, brain=True: ("you're asleep", end))
    voice.set_room_mode("night")
    assert voice.room.status()["until"] == pytest.approx(end.timestamp())


def test_the_switch_turns_every_mode_off_at_once(voice):
    voice.app.settings.set("voice.speak.what", "all")
    voice.set_room_mode("company")
    voice.app.settings.set("voice.room_modes.on", False)
    assert voice.room.mode() == "alone" and voice.setting("speak.what") == "all"
    ok, why = voice.room.set("night")
    assert not ok and "off" in why and voice.set_room_mode("night") is False and voice.room_mode() == ""


def test_it_lasts_a_restart_and_keeps_no_words(voice):
    voice.room.set("night", by="test")
    again = room_mod.Room(voice, voice.room.file)
    assert again.mode() == "night"
    assert set(again._state) == {"mode", "since", "until", "by"}


# ------------------------------------------------------------------------------------------- the ways in
def test_the_room_command(voice):
    assert voice._cmd_room(None, "").startswith("Room: alone")
    assert voice._cmd_room(None, "night").startswith("Night mode until")
    assert voice._cmd_room(None, "silent 30m").startswith("Silent mode until")
    assert voice._cmd_room(None, "off").startswith("Room mode: alone")
    assert "alone, company, night or silent" in voice._cmd_room(None, "loud")
    assert voice._cmd_room(None, "night soon").startswith("/room <mode>")
    assert any(c.name == "room" for c in voice.commands())


def test_said_aloud_only_his_verified_voice_sets_it(voice):
    voice.app.settings.set("voice.speaker_id.on", True)
    assert voice.room.heard("what's due tomorrow", Verdict("owner", "")) is None  # not a phrase: on to the AI
    assert voice.room.heard("night mode", Verdict("guest", "")) == room_mod.NOT_YOU
    assert voice.room.heard("night mode", Verdict("unsure", "")) == room_mod.NOT_YOU
    assert voice.room.mode() == "alone"
    assert voice.room.heard("night mode", Verdict("owner", "")).startswith("Night mode until")
    assert voice.room.mode() == "night" and events(voice, "voice_room")[-1]["by"] == "voice"
    voice.app.settings.set("voice.speaker_id.on", False)
    assert voice.room.heard("go silent", None) == room_mod.NO_ID and voice.room.mode() == "night"
    voice.app.settings.set("voice.room_modes.spoken", False)
    assert voice.room.heard("go silent", Verdict("owner", "")) is None


def test_the_phrase_never_reaches_the_ai(voice, monkeypatch):
    voice.app.settings.set("voice.speaker_id.on", True)
    sent = []
    monkeypatch.setattr(voice.app, "handle", lambda msg: sent.append(msg.text))
    said = voice.ask_brain("Night mode.", Verdict("owner", ""))
    assert said.startswith("Night mode until") and sent == []


def test_the_dashboard_and_the_add_on_hook(voice):
    from kurooto.web.api import Api

    api = Api(voice.app)
    code, out = api.post("voice/room", {"mode": "company"})
    assert code == 200 and out["ok"] and out["room"]["mode"] == "company"
    code, out = api.get("voice", {})
    assert out["room"]["mode"] == "company" and out["room"]["modes"] == list(room_mod.MODES)
    assert api.post("voice/room", {"mode": "night", "hours": "x"})[0] == 400
    # the Body face's hook: room_mode() -> the mode's word, set_room_mode(mode, source) -> True; "" ends it
    assert voice.room_mode() == "company"
    assert voice.set_room_mode("silent", source="body") is True
    assert voice.room_mode() == "silent" and voice.room_status()["by"] == "body"
    assert voice.set_room_mode("loud") is False and voice.room_mode() == "silent"
    pushed = [m for m in voice.app.live.sent if m["kind"] == "voice_room"]
    assert pushed and pushed[-1]["mode"] == "silent"
    assert voice.set_room_mode("") is True and voice.room_mode() == "alone"


def test_todays_copy_for_the_phone_has_the_room(voice):
    from kurooto.modules.calls.today import CHANGES, PhoneToday

    class Calls:
        app = voice.app
        dir = voice.app.paths.state

    voice.set_room_mode("night")
    assert PhoneToday(Calls())._room()["mode"] == "night" and "voice_room" in CHANGES
    voice.app.settings.set("voice.room_modes.on", False)
    assert PhoneToday(Calls())._room() is None


# ----------------------------------------------------------------------------------------- what's played
def loud(seconds=0.25, sr=16000, amp=0.98):
    n = int(seconds * sr)
    return b"".join(struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * 220 * i / sr))) for i in range(n))


def peak_db(pcm):
    a = array.array("h")
    a.frombytes(pcm)
    return 20 * math.log10(max(1, max(abs(x) for x in a)) / 32768)


def rms_db(pcm):
    a = array.array("h")
    a.frombytes(pcm)
    return 20 * math.log10(math.sqrt(sum(x * x for x in a) / len(a)) / 32768)


def test_silent_plays_nothing_and_shows_the_words(voice):
    voice.speaker.player = Speakers()
    voice.set_room_mode("silent")
    ok, _ = voice.say("The report is due Friday.", wait=True)
    assert not ok and voice.speaker.player.got == []
    assert [m for m in voice.app.live.sent if m["kind"] == "voice_text"][-1]["text"] == "The report is due Friday."
    voice.speaker.ack(loud(), 16000)  # any sound at all (the tone, Live's): nothing
    assert voice.speaker.player.got == []


def test_night_is_quieter_through_the_same_stage(voice, monkeypatch):
    class Loud(Tts):
        def synth(self, text):
            return loud(0.2), 16000

    monkeypatch.setattr(voice, "tts", lambda: (Loud(), ""))
    voice.speaker.player = Speakers()
    voice.say("One.", wait=True)
    voice.set_room_mode("night")
    voice.say("One.", wait=True)
    day, night = voice.speaker.player.got
    assert rms_db(night) == pytest.approx(rms_db(day) - 12, abs=1.0)


def test_the_limiter_keeps_every_sound_under_minus_three():
    out = outstage.process(loud(), 24000)
    assert peak_db(out) <= -2.99 and len(out) == len(loud())


def test_levelling_moves_half_way_and_leaves_soft_sounds_alone():
    quiet_speech = loud(amp=0.05)  # about -29 dBFS: a soft cue, left as it is
    assert outstage.process(quiet_speech, 16000) == quiet_speech
    mid = loud(amp=0.08)  # about -25 dBFS: moved half way to -20
    assert rms_db(outstage.process(mid, 16000)) == pytest.approx(rms_db(mid) + (-20 - rms_db(mid)) / 2, abs=0.3)
    level = loud(amp=0.1414)  # -20 dBFS, peak under the ceiling: the very same bytes
    assert outstage.process(level, 16000) == level


def test_the_same_piece_always_comes_out_the_same_and_odd_bytes_survive():
    p = loud(0.1)
    assert outstage.process(p, 16000) == outstage.process(p, 16000)
    assert outstage.process(p + b"\x01", 16000)[-1:] == b"\x01" and outstage.process(b"", 16000) == b""


def test_the_tone_stays_soft():
    from kurooto.modules.voice import fast

    t = fast.tone(fast.ACK_RATE)
    assert outstage.process(t, fast.ACK_RATE) == t
