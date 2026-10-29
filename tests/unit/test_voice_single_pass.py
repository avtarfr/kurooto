"""(0.9.2, a fix) One Whisper pass for a voice Voice ID is unsure of. The golden cases (what's sent, what's dropped)
were written first and pass on the code before the change; the pass counts are the change."""

# ruff: noqa: F811 (the fixtures imported from test_voice are taken as arguments)

import pytest

from kurooto.modules.voice.gate import CHATTER
from kurooto.modules.voice.speakerid import Verdict
from tests.unit.test_voice import hear, vid, voice  # noqa: F401 (pytest fixtures)

GOLDEN = [  # (what's said, seconds, sent as)
    ("Kurooto, what's the time?", 8.0, "what's the time?"),
    ("what's the time, Kurooto?", 8.0, None),  # careful with a voice not his: the name only first
    ("did you see the match last night, it was something", 8.0, None),
    ("I told Kurooto about it yesterday and it was fine", 8.0, None),
    ("Kurooto, what's the time?", 2.0, "what's the time?"),
]


@pytest.fixture
def unsure(vid, monkeypatch):
    v = vid.v
    monkeypatch.setattr(vid, "check", lambda *a, **k: Verdict("unsure", "not sure", 0.4, 3.0))
    return v


@pytest.mark.parametrize(("said", "seconds", "sent"), GOLDEN)
def test_golden_an_unsure_voice_is_sent_or_dropped_as_before(unsure, said, seconds, sent):
    v = unsure
    v.judge.answers = ['{"class": "chatter", "confidence": 0.9}'] * 3
    hear(v, said, seconds=seconds)
    if sent is None:
        assert v.portal.send.got == [] and v.heard[CHATTER] == 1
    else:
        assert v.portal.send.got == [(sent, "unsure")]


def test_an_unsure_voice_is_written_out_once(unsure):
    v = unsure
    stt = v.voiceid.stt_fake
    hear(v, "Kurooto, what's the time?", seconds=8.0)
    assert len(stt.calls) == 1 and stt.calls[0] > 8 * 16000 * 2 * 0.9  # the whole of it, once
    stt.calls.clear()
    v.portal.close("test")
    hear(v, "did you see the match last night", seconds=8.0, utt=2)
    assert len(stt.calls) == 1 and v.portal.send.got[-1:] == [("what's the time?", "unsure")]
    rows = v.turn_log
    assert [r["stt_runs"] for r in rows] == [1, 1] and rows[-1]["path"] == "dropped"
