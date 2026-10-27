"""Voice (modules/voice): the gate's three classes, the portal opening only when Kurooto is talked to and closing at
once when it isn't, nothing sent while it's closed, dropped words never kept, the shape endpoint's estimate, and the
switches (listening, mute, night, calls, pause). Fakes stand in for the microphone, VAD, wake word, transcriber, local
model and the AI: no sound device or model is touched."""

import json
import threading
import time

import pytest

from kurooto.modules.base import Incoming
from kurooto.modules.voice import Voice
from kurooto.modules.voice import shape as shape_mod
from kurooto.modules.voice.gate import ADDRESSED, CHATTER, NOISE, Context, Gate, Heard, parse
from kurooto.modules.voice.names import NameMatcher, skeleton
from kurooto.modules.voice.portal import Portal


# ------------------------------------------------------------------------------------------------------ fakes
class Judge:
    """The local model: answers in turn, and counts what it was asked."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else None


class Brain:
    """The AI you picked: records every turn it gets."""

    def __init__(self, reply="It's due Friday."):
        self.got = []
        self.reply = reply

    def __call__(self, text):
        self.got.append(text)
        return self.reply


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Live:
    def __init__(self):
        self.sent = []

    def push(self, msg, only=None):
        self.sent.append(json.loads(json.dumps(msg, default=str)))

    def watched(self):
        return True


def gate(judge=None, **kw):
    return Gate(["Kurooto", "kuroto"], judge=judge, **kw)


# ------------------------------------------------------------------------------------------------- the gate
def test_no_speech_is_noise_and_the_model_isnt_asked():
    j = Judge()
    d = gate(j).decide(Heard(speech=False, text="whatever"))
    assert (d.klass, d.why) == (NOISE, "no speech") and j.prompts == []


def test_made_up_words_from_silence_are_noise():
    for text in ("", "Thank you.", "[Music]", "...", "you"):
        assert gate(Judge()).decide(Heard(speech=True, text=text)).klass == NOISE, text


def test_the_wake_word_is_addressed():
    j = Judge()
    d = gate(j).decide(Heard(speech=True, text="okay go what's due", wake=True))
    assert d.klass == ADDRESSED and d.confidence == 1.0 and j.prompts == []


def test_its_name_as_a_call_is_addressed_but_in_passing_goes_to_the_model():
    j = Judge('{"class": "chatter", "confidence": 0.9}')
    g = gate(j)
    for text in ("Kurooto, what's due tomorrow?", "hey kuroto remind me at 6", "what's the weather, Kurooto?"):
        assert g.decide(Heard(speech=True, text=text)).klass == ADDRESSED, text
    assert j.prompts == []
    d = g.decide(Heard(speech=True, text="I told my friend Kurooto reminds me of things"))
    assert d.klass == CHATTER and len(j.prompts) == 1 and "not as a call" in j.prompts[0]


def test_several_voices_with_no_address_are_chatter():
    j = Judge()
    d = gate(j).decide(Heard(speech=True, text="did you see the match yesterday", voices=2))
    assert d.klass == CHATTER and j.prompts == []


def test_the_local_model_decides_the_rest_with_a_threshold():
    h = Heard(speech=True, text="what time is the lab tomorrow")
    assert gate(Judge('{"class": "addressed", "confidence": 0.92}')).decide(h).klass == ADDRESSED
    unsure = gate(Judge('{"class": "addressed", "confidence": 0.5}'), threshold=0.7).decide(h)
    assert unsure.klass == CHATTER and "sure" in unsure.why
    assert gate(Judge('{"class": "noise", "confidence": 0.8}')).decide(h).klass == NOISE
    assert gate(Judge('```json\n{"class": "chatter", "confidence": 0.7}\n```')).decide(h).klass == CHATTER


def test_without_a_local_model_nothing_is_addressed_by_judgement():
    h = Heard(speech=True, text="can you set a timer")
    assert gate(None).decide(h).klass == CHATTER  # no model at all
    assert gate(Judge(None)).decide(h).klass == CHATTER  # the model didn't answer
    assert gate(Judge('{"class": "addressed", "confidence": 1}'), use_model=False).decide(h).klass == CHATTER


def test_a_question_inside_the_conversation_or_right_after_it_spoke_is_addressed():
    j = Judge()
    g = gate(j, close_s=8, after_speak_s=6)
    inside = Context(portal_open=True, since_portal_s=3)
    assert g.decide(Heard(speech=True, text="and what about thursday?"), inside).klass == ADDRESSED
    after = Context(since_spoke_s=2, last_reply="Shall I move it to Friday?")
    assert g.decide(Heard(speech=True, text="yes please"), after).klass == ADDRESSED
    assert j.prompts == []
    late = Context(since_spoke_s=30, last_reply="Shall I move it to Friday?")
    g.decide(Heard(speech=True, text="yes please"), late)
    assert len(j.prompts) == 1  # too late for the rule: the model judges
    told = Context(since_spoke_s=2, last_reply="It's due Friday.")
    g.decide(Heard(speech=True, text="no I'll get the snacks later"), told)
    assert len(j.prompts) == 2  # a "no" after a statement isn't a reply to it: the model judges


def test_right_after_the_wake_word_the_next_words_are_addressed():
    d = gate(Judge()).decide(Heard(speech=True, text="the lab report"), Context(portal_open=True, awaiting=True))
    assert d.klass == ADDRESSED and d.why == "right after it was called"


def test_the_models_answer_is_parsed_safely():
    assert parse('{"class": "addressed", "confidence": 2}') == (ADDRESSED, 1.0)
    assert parse("noise") == (NOISE, 0.5)
    assert parse("addressed or chatter") == (CHATTER, 0.0)
    assert parse("") == (CHATTER, 0.0)


MISHEARD = [
    "Kurooto, what's due?",
    "Kuroto what's due",
    "kurouto, set a timer",
    "Kuruto, are you there",
    "Curoto, remind me",
    "Kurato, what's next",
    "Kuro to, what time is it",
    "Coo roto, hello",
    "Kirito, what's on today",
    "Guru to, read that again",
    "Kuroo, stop",
    "Hey kuro, what's the time",
    "Kurroto, open my notes",
    "Kurotto what's due",
    "Kiroto, what's due",
    "what's due tomorrow, Kurooto?",
    "what's due tomorrow kuroto",
]
ORDINARY = [
    "that was cool",
    "auto mode is on",
    "curry for dinner",
    "ghetto blaster",
    "Kurt called earlier",
    "reset the router",
    "a new kurta",
    "karate class",
    "the curator said no",
    "a photo of tomato",
    "the grotto",
    "Kyoto in spring",
    "Toronto",
    "cure it",
    "quarter past",
    "put the kettle on",
]


def test_its_name_is_heard_as_whisper_may_spell_it():
    m = NameMatcher(["Kurooto"])
    missed = [t for t in MISHEARD if not m.called(t)]
    assert missed == []


def test_ordinary_words_arent_its_name():
    m = NameMatcher(["Kurooto"])
    wrong = [t for t in ORDINARY if m.called(t) or m.anywhere(t)]
    assert wrong == []
    for w in ("cool", "auto", "curry", "ghetto", "kurt", "router"):
        assert not m.anywhere(w), w


def test_name_variants_and_another_name():
    m = NameMatcher(["Nova"], variants=["no va"])
    assert m.called("no va, what's due") and m.called("Nova what's due") and not m.called("Kuroto, hi")
    assert NameMatcher(["Kurooto"], variants=["crouton"]).called("crouton, what's due")
    assert skeleton("kurooto") == skeleton("Guruto") == "krt"


def test_the_call_is_taken_off_before_anything_is_sent():
    m = NameMatcher(["Kurooto"])
    assert m.uncall("Hey Kuro to, what's due?") == "what's due?"
    assert m.uncall("what's due, Kurooto?") == "what's due"
    assert m.uncall("Kurooto") == ""
    assert m.uncall("what's due") == "what's due"


# ----------------------------------------------------------------------------------------------- the portal
def make_portal(brain=None, close_s=8):
    said, events, clock = [], [], Clock()
    p = Portal(
        send=brain or Brain(),
        speak=said.append,
        publish=lambda kind, **f: events.append((kind, f)),
        clock=clock,
        close_s=close_s,
    )
    return p, said, events, clock


def addressed(why="its name"):
    from kurooto.modules.voice.gate import Decision

    return Decision(ADDRESSED, 0.95, why)


def other(klass=CHATTER):
    from kurooto.modules.voice.gate import Decision

    return Decision(klass, 0.8, "the local model")


def test_the_portal_opens_only_when_addressed_and_closes_at_once_when_not():
    brain = Brain()
    p, said, events, clock = make_portal(brain)
    assert p.take(Heard(speech=True, text="they said it was fine"), other()) is None
    assert not p.open and brain.got == []
    reply = p.take(Heard(speech=True, text="Kurooto, when is the report due?"), addressed())
    assert reply == "It's due Friday." and p.open and brain.got == ["Kurooto, when is the report due?"]
    assert said == ["It's due Friday."]
    texts = [f for k, f in events if k == "voice_text"]
    assert texts == [{"who": "you", "text": "Kurooto, when is the report due?"}, {"who": "kurooto", "text": reply}]
    states = [f["state"] for k, f in events if k == "voice_state"]
    assert states == ["addressed", "thinking", "speaking", "addressed"]
    clock.t += 2
    assert p.take(Heard(speech=True, text="anyway as I was saying"), other()) is None
    assert not p.open and brain.got == ["Kurooto, when is the report due?"]  # nothing more went out
    assert events[-1] == (
        "voice_state",
        {"state": "closed", "portal": False, "listening": True, "why": "not addressed"},
    )


def test_the_portal_closes_after_close_s_of_silence():
    p, _said, events, clock = make_portal(close_s=8)
    p.take(Heard(speech=True, text="Kurooto, hi"), addressed())
    clock.t += 5
    p.tick()
    assert p.open
    clock.t += 4
    p.tick()
    assert not p.open and events[-1][1]["why"] == "silence"


def test_the_wake_word_alone_sends_nothing_and_waits_for_the_request():
    brain = Brain()
    p, said, _events, _clock = make_portal(brain)
    assert p.take(Heard(speech=True, text="Kurooto?"), addressed("the wake word"), text="") is None
    assert p.open and said == ["Yes?"] and brain.got == []
    assert p.context().awaiting
    p.take(Heard(speech=True, text="what's due"), addressed("right after it was called"))
    assert brain.got == ["what's due"] and not p.context().awaiting


def test_a_failing_brain_gets_a_short_apology_spoken():
    def broken(_t):
        raise RuntimeError("down")

    p, said, _e, _c = make_portal(broken)
    assert p.take(Heard(speech=True, text="Kurooto, hi"), addressed()) == "I couldn't get an answer just now."
    assert said == ["I couldn't get an answer just now."]


# ----------------------------------------------------------------------------------------------- the module
@pytest.fixture
def voice(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    v: Voice = app.modules["voice"]
    monkeypatch.setattr(v.parts, "missing", lambda keys: [])  # "set up": no packages or models needed in tests
    monkeypatch.setattr(v, "_on_call", lambda: False)
    monkeypatch.setattr(v, "_night", lambda: False)
    app.live = Live()
    ok, why = app.enable("voice")
    assert ok, why
    app.settings.set("voice.listen.on", True)
    v.brain = Brain()
    v.portal.send = v.brain
    v.spoken = []
    v.portal.speak = v.spoken.append
    v.judge = Judge()  # the local model (Voice.gate passes self.judge to the gate)
    yield v
    app.close()


def everything_kept(v) -> str:
    """Every file Kurooto wrote (state, logs, settings), as one text."""
    out = []
    for root in (v.app.paths.state, v.app.paths.logs, v.app.paths.config, v.app.paths.data):
        for f in root.rglob("*"):
            if f.is_file():
                try:
                    out.append(f.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
    return "\n".join(out)


def test_chatter_and_noise_send_nothing_and_their_words_are_never_kept(voice):
    voice.judge.answers = ['{"class": "chatter", "confidence": 0.9}']
    secret = "the pin for the locker is four four seven one"
    assert voice.hear(Heard(speech=True, text=secret)) is None
    assert voice.hear(Heard(speech=False, text="")) is None
    assert voice.brain.got == []  # nothing left the computer
    assert voice.heard[CHATTER] == 1 and voice.heard[NOISE] == 1
    assert "locker" not in everything_kept(voice)
    assert "locker" not in json.dumps(voice.app.live.sent)
    assert "locker" not in json.dumps(voice.status())
    assert not voice.portal.open


def test_addressed_speech_opens_the_portal_and_chatter_closes_it_at_once(voice):
    voice.judge.answers = ['{"class": "chatter", "confidence": 0.95}']
    assert voice.hear(Heard(speech=True, text="Kurooto, what's due this week?")) == "It's due Friday."
    assert voice.brain.got == ["what's due this week?"] and voice.portal.open
    assert voice.spoken == ["It's due Friday."]
    voice.hear(Heard(speech=True, text="no I'll get the snacks later, don't worry"))
    assert not voice.portal.open and len(voice.brain.got) == 1
    kinds = [m["kind"] for m in voice.app.live.sent]
    assert all(m["t"] == "voice" for m in voice.app.live.sent)
    assert "voice_text" in kinds and kinds[-1] == "voice_state"
    assert voice.app.live.sent[-1]["state"] == "closed"
    portal_events = [e for e in voice.app.events.tail(50) if e["kind"] == "voice_portal"]
    assert [e["open"] for e in portal_events] == [True, False]
    assert "snacks" not in everything_kept(voice)


def test_its_name_is_taken_out_before_anything_is_sent(voice):
    voice.hear(Heard(speech=True, text="Hey Kuroto, set a timer for ten minutes"))
    assert voice.brain.got == ["set a timer for ten minutes"]
    voice.portal.close("test")
    voice.hear(Heard(speech=True, text="Kurooto?"))  # the name alone: it answers "Yes?" and sends nothing
    assert voice.spoken[-1] == "Yes?" and len(voice.brain.got) == 1 and voice.portal.open
    voice.hear(Heard(speech=True, text="the lab report deadline"))
    assert voice.brain.got[-1] == "the lab report deadline"


def test_mute_stops_hearing_and_lasts(voice):
    assert voice._cmd(None, "mute").startswith("Muted")
    assert voice.muted() and voice.blocked() == "muted"
    assert voice.hear(Heard(speech=True, text="Kurooto, hello")) is None
    assert voice.brain.got == []
    ok, why = voice.say("hello")
    assert not ok and "muted" in why
    assert voice.mute(False) == "Unmuted." and not voice.muted()
    assert voice.hear(Heard(speech=True, text="Kurooto, hello")) is not None


def test_listening_is_its_own_switch(voice):
    voice.app.settings.set("voice.listen.on", False)
    assert voice.blocked() == "listening is off"
    assert voice.hear(Heard(speech=True, text="Kurooto, hello")) is None and voice.brain.got == []


def test_night_and_calls_stop_listening_unless_allowed(voice, monkeypatch):
    monkeypatch.setattr(voice, "_night", lambda: True)
    assert voice.blocked() == ""  # it listens at night by default (voice.listen.night)
    voice.app.settings.set("voice.listen.night", False)
    assert voice.blocked() == "night hours"
    assert voice.hear(Heard(speech=True, text="Kurooto, hello")) is None and voice.brain.got == []
    voice.app.settings.set("voice.listen.night", True)
    assert voice.blocked() == ""
    monkeypatch.setattr(voice, "_on_call", lambda: True)
    assert voice.blocked() == "you're on a call"
    assert voice.hear(Heard(speech=True, text="Kurooto, hello")) is None and voice.brain.got == []
    voice.app.settings.set("voice.listen.calls", True)
    assert voice.blocked() == ""


def test_paused_kurooto_doesnt_listen(voice):
    voice.app.power.pause()
    assert voice.blocked() == "Kurooto is paused"
    assert voice.hear(Heard(speech=True, text="Kurooto, hello")) is None and voice.brain.got == []
    voice.app.power.resume()
    assert voice.blocked() == ""


def test_turning_voice_off_closes_the_portal(voice):
    voice.hear(Heard(speech=True, text="Kurooto, hello"))
    assert voice.portal.open
    voice.app.disable("voice")
    assert not voice.portal.open
    assert voice.hear(Heard(speech=True, text="Kurooto, hello again")) is None and len(voice.brain.got) == 1


def test_speaking_switches(voice):
    voice.app.settings.set("voice.speak.on", False)
    tts, why = voice.tts()
    assert tts is None and "off" in why
    ok, why = voice.say("hello")
    assert not ok
    voice.app.settings.set("voice.speak.on", True)
    voice.app.settings.set("voice.speak.engine", "off")
    assert voice.tts()[0] is None


def test_what_it_needs_follows_the_switches(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    try:
        v = app.modules["voice"]
        assert v.wants() == ["pkg:audio", "pkg:kokoro", "model:kokoro"]
        ok, why = app.enable("voice")
        assert not ok and "needs setting up" in why and "GB" in why  # nothing fetched until you set it up
        app.settings.set("voice.listen.on", True)
        w = v.wants()
        assert {"pkg:listen", "model:vad", "model:whisper-base"} <= set(w)
        assert not any("wake" in k for k in w)  # no wake word model by default: its name wakes it
        app.settings.set("voice.listen.wake_word", "/models/my-own.onnx")
        assert {"pkg:wake", "model:wake-common"} <= set(v.wants())
        app.settings.set("voice.listen.wake_word", "")
        app.settings.set("voice.speak.engine", "piper")
        assert "model:piper" in v.wants() and "model:kokoro" not in v.wants()
        assert not app.is_on("voice")
    finally:
        app.close()


def test_the_api(voice):
    from kurooto.web.api import Api

    api = Api(voice.app)
    code, st = api.get("voice")
    assert code == 200 and st["on"] and st["listen"]["on"] and "heard" in st and "engines" in st
    code, out = api.post("voice/mute", {"on": True})
    assert code == 200 and out["muted"] is True
    code, out = api.post("voice/mute", {})
    assert out["muted"] is False
    code, out = api.post("voice/say", {"text": ""})
    assert code == 200 and not out["ok"]


def test_a_spoken_request_goes_through_like_a_chat_message(voice):
    voice.portal.send = Voice.ask_brain.__get__(voice)
    reply = voice.ask_brain("/voice")  # a command answers at once, nothing goes to an AI
    assert reply.startswith("Voice:")


# ------------------------------------------------------------------------------------------------ the shape
def test_the_shape_estimate_is_deterministic_and_follows_the_sounds(voice):
    from kurooto.web.api import Api

    api = Api(voice.app)
    code, a = api.post("voice/shape", {"text": "Hello there, Sam. Ready?"})
    _, b = api.post("voice/shape", {"text": "Hello there, Sam. Ready?"})
    assert code == 200 and a == b and a["source"] == "estimate" and a["rate"] == 50
    assert a["seconds"] == round(len(a["samples"]) / 50, 2) and all(0 <= x <= 1 for x in a["samples"])
    s = a["samples"]
    assert [0.0] * 8 == s[s.index(0.0) : s.index(0.0) + 8]  # the comma's pause
    vowel = shape_mod.estimate("aaa")
    hiss = shape_mod.estimate("sss")
    assert max(vowel) > 0.8 and max(hiss) < 0.35  # vowels loud, sibilants low
    assert shape_mod.estimate("pa")[:2] == [0.0, 0.78]  # a plosive: silence then a burst
    assert len(shape_mod.estimate("hello world", rate=2.0)) < len(shape_mod.estimate("hello world"))
    assert shape_mod.estimate("") == []


def test_the_shape_from_sound():
    import array

    pcm = array.array("h", [0] * 320 + [16000] * 320 + [-8000] * 320).tobytes()
    assert shape_mod.from_pcm(pcm, 16000) == [0.0, 1.0, 0.5]
    assert shape_mod.levels(array.array("h", [0] * 1600).tobytes())[0] == 0.0


def test_speech_is_cut_into_sentences_without_markdown():
    s = shape_mod.sentences("**Due** Friday. See [the note](https://x.y/z).\n- `lab` at 9")
    assert s == ["Due Friday.", "See the note.", "lab at 9"]


def test_every_answer_is_read_aloud_only_when_asked_for(voice, monkeypatch):
    from types import SimpleNamespace

    said = []
    monkeypatch.setattr(voice.speaker, "say", lambda text, wait=True: said.append(text) or (True, ""))
    job = SimpleNamespace(id="j1", lane="you", quiet=False, background=False)
    done = SimpleNamespace(ok=True, text="Your lab is at 9.")
    voice._job_done(job, done, {})
    assert said == []  # voice.speak.what is "voice" by default: only answers to what was said aloud
    voice.app.settings.set("voice.speak.what", "all")
    voice._job_done(job, done, {})
    voice._job_done(SimpleNamespace(id="j2", lane="bg", quiet=False, background=True), done, {})
    assert said == ["Your lab is at 9."]
    voice.mute(True)
    voice._job_done(job, done, {})
    assert said == ["Your lab is at 9."]


def test_a_reply_isnt_spoken_once_muted(voice, monkeypatch):
    said = []
    monkeypatch.setattr(voice.speaker, "say", lambda text, wait=True: said.append(text) or (True, ""))
    voice._portal_speak("one")
    voice.mute(True)
    voice._portal_speak("two")
    assert said == ["one"]


# ---------------------------------------------------------------------------- outputs (0.8.12, add_output)
class Tts:
    def synth(self, text):
        return (text.encode() * 100)[:3200], 16000  # stands for that sentence's sound


class Speakers:
    """This computer's Player: records what it was given, never plays."""

    def __init__(self):
        self.got = []

    def play(self, pcm, sr):
        self.got.append(pcm)

    def stop(self):
        pass


class Output:
    """An add-on's output: answers in turn (True, False or an exception), records each sentence, and whether Kurooto
    was holding its ears while it played."""

    def __init__(self, voice, *answers, block=False):
        self.v, self.answers, self.block = voice, list(answers), block
        self.got, self.held, self.stopped = [], [], []
        self.started = threading.Event()

    def __call__(self, pcm, sr, stop):
        assert isinstance(pcm, bytes) and sr == 16000
        self.got.append(pcm)
        self.held.append(self.v.speaker.holding())
        self.started.set()
        if self.block:
            self.stopped.append(stop.wait(5))
        a = self.answers.pop(0) if self.answers else True
        if isinstance(a, Exception):
            raise a
        return a


@pytest.fixture
def speakers(voice, monkeypatch):
    monkeypatch.setattr(voice, "tts", lambda: (Tts(), ""))
    voice.speaker.player = Speakers()
    return voice.speaker.player


def test_an_output_plays_instead_of_the_speakers(voice, speakers):
    out = Output(voice)
    voice.add_output(out)
    assert voice.say("One. Two.", wait=True)[0]
    assert len(out.got) == 2 and speakers.got == []
    assert out.held == [True, True]  # Kurooto doesn't hear itself while the other device plays
    assert sum(m["kind"] == "voice_speak" for m in voice.app.live.sent) == 2  # the shape is sent as before
    voice.speaker.until = 0
    assert not voice.speaker.holding()


def test_the_newest_output_first_and_false_falls_back(voice, speakers):
    old, new = Output(voice, True, False), Output(voice, False, False)
    voice.add_output(old)
    voice.add_output(new)
    voice.say("One. Two.", wait=True)
    assert len(new.got) == 2 and len(old.got) == 2  # newest asked first, then the older one
    assert speakers.got == [old.got[1]]  # neither took the second: this computer's speakers did


def test_a_raising_output_falls_back_and_is_told_once(voice, speakers):
    out = Output(voice, RuntimeError("phone gone"), RuntimeError("phone gone"))
    voice.add_output(out)
    voice.say("One. Two.", wait=True)
    assert len(out.got) == 2 and len(speakers.got) == 2
    failed = [e for e in voice.app.events.tail(50) if e.get("kind") == "voice_failed"]
    assert len(failed) == 1 and failed[0]["part"] == "output" and "phone gone" in failed[0]["error"]


@pytest.mark.parametrize("how", ["stop", "mute"])
def test_stop_and_mute_end_an_output_at_once(voice, speakers, how):
    out = Output(voice, block=True)
    voice.add_output(out)
    voice.say("One. Two. Three.")
    assert out.started.wait(5)
    voice.speaker.stop() if how == "stop" else voice.mute(True)
    for _ in range(200):
        if not voice.speaker.busy:
            break
        time.sleep(0.01)
    assert not voice.speaker.busy
    assert out.stopped == [True] and len(out.got) == 1 and speakers.got == []  # nothing more, nowhere else


def test_a_removed_output_isnt_used(voice, speakers):
    out = Output(voice)
    first, second = voice.add_output(out), voice.add_output(out)  # the same function twice
    first()
    first()  # each remove() takes only its own, and twice is harmless
    voice.say("One.", wait=True)
    assert len(out.got) == 1
    second()
    voice.say("Two.", wait=True)
    assert len(out.got) == 1 and len(speakers.got) == 1


# ------------------------------------------------------------------------------------- Voice ID (0.8.10)
class Stt:
    """The transcriber: says what it's told to, and counts each call (and how much sound it got)."""

    def __init__(self):
        self.said = ""
        self.calls = []

    def text(self, pcm):
        self.calls.append(len(pcm))
        return self.said


class WhoBrain:
    def __init__(self, reply="Sure."):
        self.got = []
        self.reply = reply

    def __call__(self, text, who=None):
        self.got.append((text, None if who is None else who.decision))
        return self.reply


@pytest.fixture
def vid(voice, monkeypatch):
    """Voice ID on and the owner (voice 1) enrolled, with a fake model, a fake bank and a fake transcriber."""
    from types import SimpleNamespace

    from tests.unit.test_voiceid import FakeEmbedder, make_bank, owner_samples

    x = voice.voiceid
    emb = FakeEmbedder()
    bank = make_bank(0.3, emb)
    bank.meta["model_sha256"] = x.model_sha()
    x.embed_fn = emb
    monkeypatch.setattr(x, "bank", lambda: bank)
    voice.app.settings.set("voice.speaker_id.on", True)
    assert x.train(session=SimpleNamespace(existing=[], samples=owner_samples(emb)))["saved"]
    stt = Stt()
    monkeypatch.setattr(voice, "stt", lambda: stt)
    voice.portal.send = WhoBrain()
    x.emb, x.stt_fake = emb, stt
    return x


def sound(voice=1, utt=1, seconds=3.0):
    from tests.unit.test_voiceid import pcm

    c = pcm(voice, utt, seconds=seconds)
    return bytes(c.pcm), c.flags


def hear(v, text, who_voice=1, utt=1, seconds=3.0):
    v.voiceid.stt_fake.said = text
    pcm_, flags = sound(who_voice, utt, seconds)
    return v.hear(Heard(speech=True, seconds=seconds), pcm_, flags)


def test_with_voice_id_off_nothing_is_embedded_and_the_speaker_is_unset(voice, monkeypatch):
    from tests.unit.test_voiceid import FakeEmbedder

    emb = FakeEmbedder()
    voice.voiceid.embed_fn = emb
    stt = Stt()
    stt.said = "Kurooto, what's due?"
    monkeypatch.setattr(voice, "stt", lambda: stt)
    got = []
    monkeypatch.setattr(voice.app, "handle", lambda msg: got.append(msg) or msg.reply("ok"))
    voice.portal.send = Voice.ask_brain.__get__(voice)
    pcm_, flags = sound()
    assert voice.hear(Heard(speech=True, seconds=3), pcm_, flags) == "ok"
    assert emb.calls == 0 and got[0].speaker == "" and got[0].speaker_by == ""


def test_the_owner_s_turn_carries_owner_and_a_guest_s_guest(vid, monkeypatch):
    v = vid.v
    got = []
    monkeypatch.setattr(v.app, "handle", lambda msg: got.append(msg) or msg.reply("ok"))
    v.portal.send = Voice.ask_brain.__get__(v)
    hear(v, "Kurooto, what's due?")
    assert got[-1].speaker == "owner" and got[-1].speaker_by == "voice" and got[-1].via == "voice"
    v.portal.close("test")
    hear(v, "Kurooto, what's due?", who_voice=55)
    assert got[-1].speaker == "guest"
    texts = [m for m in v.app.live.sent if m["kind"] == "voice_text" and m.get("who") == "you"]
    assert [m.get("speaker") for m in texts] == ["owner", "guest"]
    assert not any("score" in m for m in v.app.live.sent)


def test_a_guest_is_told_once_per_conversation(vid):
    v = vid.v
    r1 = hear(v, "Kurooto, what's the capital of France?", who_voice=55)
    assert r1.startswith("You can chat with me, but only my owner's voice can make me do things.")
    r2 = hear(v, "and of Spain?", who_voice=55, utt=2)
    assert r2 == "Sure."  # the same conversation: not again
    v.portal.close("silence")
    assert hear(v, "Kurooto, one more?", who_voice=55, utt=3).startswith("You can chat")
    assert [w for _t, w in v.portal.send.got] == ["guest", "guest", "guest"]
    v.app.settings.set("voice.speaker_id.tell_guests", False)
    v.portal.close("silence")
    assert hear(v, "Kurooto, and again?", who_voice=55, utt=4) == "Sure."


def test_owner_only_at_all_sends_and_shows_nothing(vid):
    v = vid.v
    v.app.settings.set("voice.speaker_id.mode", "owner_only_at_all")
    said = v.spoken
    assert hear(v, "Kurooto, what's due tomorrow?", who_voice=55) is None
    assert v.portal.send.got == [] and said == ["I only answer my owner's voice."]
    assert not any(m["kind"] == "voice_text" and m.get("who") == "you" for m in v.app.live.sent)
    assert not v.portal.open
    hear(v, "Kurooto, what's due tomorrow?", who_voice=55, utt=2)
    assert said == ["I only answer my owner's voice."]  # once a minute at most
    assert hear(v, "Kurooto, what's due tomorrow?") == "Sure."  # the owner still gets through


def test_someone_else_not_calling_it_is_never_transcribed(vid):
    v = vid.v
    stt = vid.stt_fake
    hear(v, "did you see the match last night, it was something", who_voice=55, seconds=8.0)
    assert stt.calls and max(stt.calls) < 8 * 16000 * 2  # only the edges, never the whole of it
    assert v.portal.send.got == [] and v.heard[CHATTER] == 1
    stt.calls.clear()
    hear(v, "Kurooto, what's the time?", who_voice=55, utt=2, seconds=8.0)
    assert len(stt.calls) == 2 and stt.calls[1] > stt.calls[0]  # the name at the edges: then all of it
    assert v.portal.send.got[-1] == ("what's the time?", "guest")


def test_without_the_gate_only_addressed_turns_are_checked(vid):
    v = vid.v
    v.app.settings.set("voice.speaker_id.gate", False)
    v.app.settings.set("voice.listen.conversation_mode", False)  # (it checks every voice, below)
    v.judge.answers = ['{"class": "chatter", "confidence": 0.9}']
    before = vid.emb.calls
    hear(v, "no I'll get the snacks later", who_voice=55)
    assert vid.emb.calls == before  # dropped by the gate: never embedded
    hear(v, "Kurooto, what's due?")
    assert vid.emb.calls == before + 1 and v.portal.send.got[-1] == ("what's due?", "owner")


def test_conversation_mode_stays_out_unless_called_by_name(vid):
    v = vid.v
    v.judge.answers = ['{"class": "addressed", "confidence": 0.95}'] * 5
    hear(v, "so are you coming to the lab tomorrow", who_voice=55)  # another voice: conversation mode
    assert vid.conversation()
    hear(v, "can you check when the lab is", utt=7)  # the owner, ambiguous: the local judge isn't asked
    assert v.portal.send.got == [] and not v.portal.open and v.judge.prompts == []
    hear(v, "Kurooto told me it moved to Friday", utt=8)
    assert v.portal.send.got == []
    hear(v, "Kurooto, when is the lab?", utt=9)
    assert v.portal.send.got == [("when is the lab?", "owner")]
    assert "conversation: staying out" in v.line()
    v.app.settings.set("voice.listen.conversation_mode", False)
    assert not vid.conversation()


def test_conversation_mode_notices_another_voice_with_the_gate_off_too(vid):
    """The two switches are separate: without the gate everything is written out as before, but another voice still
    puts Kurooto in conversation mode; with conversation mode off too, nothing is checked until it's addressed."""
    v = vid.v
    v.app.settings.set("voice.speaker_id.gate", False)
    v.judge.answers = ['{"class": "chatter", "confidence": 0.9}'] * 3
    before = vid.emb.calls
    hear(v, "are you coming to the lab tomorrow", who_voice=55)
    assert vid.emb.calls == before + 1 and vid.conversation()
    assert vid.stt_fake.calls[-1] == len(sound(55, 1, 3.0)[0])  # without the gate: written out in full, as before
    hear(v, "can you check when the lab is", utt=7)  # the owner, not by name: staying out
    assert v.portal.send.got == []
    hear(v, "Kurooto, when is the lab?", utt=9)
    assert v.portal.send.got == [("when is the lab?", "owner")]


def test_the_gate_drops_others_with_conversation_mode_off(vid):
    v = vid.v
    v.app.settings.set("voice.listen.conversation_mode", False)
    hear(v, "did you see the match last night, it was something", who_voice=55, seconds=8.0)
    assert v.portal.send.got == [] and v.heard[CHATTER] == 1 and not vid.conversation()


def test_voice_id_commands_refuse_voice(vid):
    v = vid.v
    for arg in ("id", "id forget", "enrol", "id retrain", "id undo all"):
        assert v._cmd(Incoming(text="/voice " + arg, via="voice", voice=True), arg) == (
            "That can't be done by voice: type it or use the dashboard."
        )
    assert v._cmd(Incoming(text="/voice id", via="telegram"), "id").startswith("Voice ID: on")
    replies = []
    msg = Incoming(text="/voice id forget", via="telegram", respond=lambda t, buttons=None: replies.append(buttons))
    assert v._cmd(msg, "id forget") is None and replies[0][0][0][1] == "vid:0:forget"
    assert v.voiceid.store.exists()  # nothing deleted before the tap


def test_listening_waits_while_enrolling(vid):
    v = vid.v
    vid.capturing = "enrolling your voice"
    assert v.blocked() == "enrolling your voice"
    assert hear(v, "Kurooto, hello") is None
    vid.capturing = ""
    assert v.blocked() == ""


def test_not_enrolled_fails_closed(vid):
    v = vid.v
    vid.forget()
    hear(v, "Kurooto, set an alarm for six")
    assert v.portal.send.got[-1] == ("set an alarm for six", "unsure")
    assert "doesn't know your voice yet" in v.line()
    ok, why = v.health()
    assert not ok and "doesn't know your voice yet" in why


def test_a_guest_s_request_is_blanked_once_voice_has_its_answer(vid, monkeypatch):
    """The guest's words don't stay in the request list (nothing later learns from them)."""
    v = vid.v
    forgot = []
    monkeypatch.setattr(v.app.jobs, "forget_guest", lambda jid: forgot.append(jid) or True)
    monkeypatch.setattr(v, "_wait_job", lambda msg: "The moon is far.")

    def handle(msg):
        msg.job = "jguest1"

    monkeypatch.setattr(v.app, "handle", handle)
    assert v.ask_brain("tell me about the moon", vid.check(sound(55)[0], 3.0)) == "The moon is far."
    assert forgot == ["jguest1"]
    monkeypatch.setattr(v, "_wait_job", lambda msg: "Sure.")
    v.ask_brain("what's due?", vid.check(sound(1, 7)[0], 3.0))  # the owner's: kept as always
    assert forgot == ["jguest1"]
