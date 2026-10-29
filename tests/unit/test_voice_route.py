"""route(facts) (0.9.2, modules/voice/trace.py) against the real flow: for every combination of the facts that pick a
turn's way (Voice ID's word, voice.listen.live, live_everyone, a face seen), an addressed turn is driven through
Voice.hear() with the fake Live server, and the way it actually went must be the one route() names. Written first, as
the golden table for pulling route() out of ask_brain without changing what it does."""

# ruff: noqa: F811 (the fixtures imported from test_voice / test_voice_live are taken as arguments)

import itertools

import pytest

from kurooto.core import guest
from kurooto.modules.voice import trace
from kurooto.modules.voice.speakerid import Verdict
from tests.unit.test_voice import voice  # noqa: F401 (pytest fixture)
from tests.unit.test_voice_live import lv, say  # noqa: F401 (pytest fixtures)

GRID = list(itertools.product(("owner", "unsure", "guest", ""), (False, True), (False, True), (False, True)))


def _expected(who, live, everyone, faced):
    if who == "owner":
        return "live" if live and (faced or everyone) else "brain"
    if live and everyone:
        return "live_guest"
    return "guest" if who else "brain"


@pytest.mark.parametrize(("who", "live", "everyone", "faced"), GRID)
def test_route_names_the_way_the_turn_really_went(lv, monkeypatch, who, live, everyone, faced):
    srv = lv.fake()
    monkeypatch.setattr(guest, "_times", {})
    lv.app.settings.set("voice.speaker_id.gate", False)  # words first, so every voice reaches the gate the same way
    lv.app.settings.set("voice.listen.live", live)
    lv.app.settings.set("voice.listen.live_everyone", everyone)
    if who:
        lv.who = Verdict(who, "test", 0.5, 2.0)
    else:
        monkeypatch.setattr(lv.voiceid, "on", lambda: False)
    if not faced:  # let through without a face seen (need_face doesn't apply)
        monkeypatch.setattr(lv, "face_gate", lambda: ("off", ""))
    got = []

    def handle(msg):
        got.append(msg.speaker)
        msg.respond("The usual way.")

    monkeypatch.setattr(lv.app, "handle", handle)
    say(lv, "Kurooto, how far away is the moon?", faced=faced)
    if srv.setups:
        went = "live" if "tools" in srv.setups[0] else "live_guest"
    else:
        assert len(got) == 1
        went = "guest" if got[0] not in ("", "owner") else "brain"
    want = _expected(who, live, everyone, faced)
    assert went == want
    facts = {"who": who, "live": live, "everyone": everyone, "faced": faced, "kept": live and (who == "owner" or
             everyone), "speak": True, "cut": False, "at_all": False}  # fmt: skip
    assert trace.route(facts) == want


def test_fallbacks():
    assert trace.fallback("live", "owner") == "brain"
    assert trace.fallback("live_guest", "unsure") == "guest"
    assert trace.fallback("live_guest", "") == "brain"
    assert trace.fallback("guest", "guest") == "guest"


def test_route_off_paths():
    base = {"who": "owner", "live": True, "everyone": True, "faced": True, "kept": True, "speak": True}
    assert trace.route(base) == "live"
    assert trace.route({**base, "speak": False}) == "brain"
    assert trace.route({**base, "cut": True}) == "brain"
    assert trace.route({**base, "kept": False}) == "brain"
    assert trace.route({**base, "who": "guest", "at_all": True}) == "guest"
    assert trace.route({**base, "who": "", "at_all": True}) == "brain"
