"""Listening better (0.8.13): careful calls when someone else may be talking, the conversation going on without its
name, being told off, the gate learning at night, Voice ID's face assist and the talk carry. Fakes only: no microphone,
camera or model is touched, and nothing here reads the real install."""

# ruff: noqa: F811 (the fixtures imported from test_voice are taken as arguments)

import json

from kurooto.core import nearby
from kurooto.modules.voice import learn
from kurooto.modules.voice import speakerid as sid
from kurooto.modules.voice.gate import ADDRESSED, CHATTER, TOLD_OFF, VETOED, Context, Decision, Heard, told_off
from kurooto.modules.voice.names import EXACT, KNOWN, NEAR, NameMatcher
from tests.unit.test_voice import (  # noqa: F401 (pytest fixtures)
    Judge,
    everything_kept,
    gate,
    hear,
    make_portal,
    vid,
    voice,
)

NO = '{"class": "chatter", "confidence": 0.9}'
YES = '{"class": "addressed", "confidence": 0.95}'


def said(text, **kw):
    return Heard(speech=True, text=text, **kw)


# ------------------------------------------------------------------------------------------- its name, how
def test_the_matcher_says_where_and_how_its_name_was_said():
    m = NameMatcher(["Kurooto"])
    c = m.call("Kurooto, what's due?")
    assert (c.where, c.kind, c.greeted, c.rest) == ("first", EXACT, False, "what's due?")
    assert m.call("hey kuroto set a timer").kind == KNOWN and m.call("hey kuroto set a timer").greeted
    assert not m.call("so Kurooto told me").greeted  # "so" opens a sentence; it isn't a greeting
    assert m.call("what's the weather, Kurooto?").where == "last"
    assert m.call("I told my friend Kurooto reminds me").where == "middle"
    assert m.kind("kurootoh") == NEAR and m.call("kurootoh what's due").kind == NEAR
    assert m.call("nothing here").where == ""


# ----------------------------------------------------------------------------------------- careful calls
def careful_cases():
    return (
        Context(speaker="unsure"),
        Context(speaker="guest"),
        Context(since_chatter_s=20),
        Context(faces=2),
    )


def test_owner_alone_keeps_the_old_name_rules():
    j = Judge()
    g = gate(j)
    for ctx in (Context(), Context(speaker="owner"), Context(since_chatter_s=90), Context(faces=1)):
        for text in ("what's the weather, Kurooto?", "kurootoh what's due", "Kurooto, what's due?"):
            assert g.decide(said(text), ctx).klass == ADDRESSED, (text, ctx)
    assert j.prompts == []


def test_unconfirmed_or_chatter_a_mention_isnt_a_call():
    for ctx in careful_cases():
        j = Judge(NO, NO, NO, NO)
        g = gate(j)
        for text in (
            "can you check this, Kurooto",  # its name at the end: the incident of 21:55
            "Kurooto told me it moved to Friday",  # first, but nothing addressed after it
            "I told my friend Kurooto reminds me of things",
            "kurootoh what's due",  # a near miss by sound only
        ):
            d = g.decide(said(text), ctx)
            assert d.klass == CHATTER and d.careful, (text, ctx)
        assert len(j.prompts) == 4 and "not a call" in j.prompts[0]


def test_unconfirmed_a_real_call_still_opens():
    for ctx in careful_cases():
        g = gate(Judge())
        for text in ("Kurooto, what's due tomorrow?", "hey Kurooto I need a timer", "hey kuroto, set a timer",
                     "Kurooto"):  # fmt: skip
            d = g.decide(said(text), ctx)
            assert d.klass == ADDRESSED and d.why == "its name", (text, ctx)


def test_the_careful_switch_turns_it_off():
    g = gate(Judge())
    assert g.decide(said("can you check this, Kurooto"), Context(speaker="unsure", careful=False)).addressed


def test_the_model_can_still_say_a_mention_was_for_it():
    d = gate(Judge(YES)).decide(said("can you check this, Kurooto"), Context(since_chatter_s=5))
    assert d.klass == ADDRESSED and d.why == "the local model"


# ------------------------------------------------------------------------------------- the conversation
def window(**kw):
    base = dict(portal_open=True, answered=True, since_spoke_s=12, follow_window_s=20, since_portal_s=12)
    return Context(**{**base, **kw})


def test_after_an_answer_the_same_voice_goes_on_without_its_name():
    j = Judge()
    g = gate(j)
    d = g.decide(said("I think the second one sounds better"), window())
    assert d.klass == ADDRESSED and d.why == "the conversation goes on" and j.prompts == []
    assert g.decide(said("I think the second one sounds better"), window(same_speaker=True)).addressed
    assert g.decide(said("I think the second one"), window(same_speaker=False)).klass == CHATTER  # model: none
    assert g.decide(said("I think the second one", voices=2), window()).klass == CHATTER
    assert not g.decide(said("I think the second one"), window(since_spoke_s=25)).addressed
    assert not g.decide(said("I think the second one"), window(answered=False)).addressed  # a greeting: not this
    assert not g.decide(said("I think the second one"), window(follow_window_s=0)).addressed


def test_in_conversation_mode_only_the_voice_that_opened_it_goes_on():
    g = gate(Judge())
    d = g.decide(said("and the other one too"), window(conversation=True, same_speaker=True))
    assert d.why == "the conversation goes on"
    d = g.decide(said("and the other one too"), window(conversation=True, same_speaker=None))
    assert d.why == "conversation: staying out"


def test_the_portal_stays_open_for_the_window_after_an_answer_only():
    p, _said, _events, clock = make_portal(close_s=8)
    p.follow_s = 20
    p.take(said("Kurooto, hi"), Decision(ADDRESSED, 0.95, "its name"))
    assert p.context().answered and p.opened_why == "its name"
    clock.t += 15
    p.tick()
    assert p.open
    clock.t += 6
    p.tick()
    assert not p.open
    p.invite("Welcome back.", 8)  # a greeting answers nobody: close_s as before
    clock.t += 9
    p.tick()
    assert not p.open


def test_chatter_is_remembered_as_a_time():
    p, _s, _e, clock = make_portal()
    assert p.context().since_chatter_s is None
    p.take(said("did you see the match"), Decision(CHATTER, 0.8, "the local model"))
    clock.t += 30
    assert p.context().since_chatter_s == 30
    p.take(said(""), Decision("noise", 0.9, "no words"))
    assert p.context().since_chatter_s == 30  # noise isn't people talking


# ------------------------------------------------------------------------------------------------ told off
def test_told_off_phrases():
    m = NameMatcher(["Kurooto"])
    for t in ("Stop.", "Kurooto, stop!", "not you", "No, not you, I was talking to him", "I wasn't talking to you",
              "shut up", "be quiet please", "go away", "never mind", "oh sorry never mind",
              "stop talking"):  # fmt: skip
        assert told_off(t, m), t
    for t in ("stop the timer", "never mind, what's the weather tomorrow", "what stop is it", "not yet"):
        assert not told_off(t, m), t


def test_told_off_counts_only_right_after_it_opened_or_spoke():
    g = gate(Judge(NO))
    assert g.decide(said("not you"), Context(portal_open=True, since_open_s=3)).why == TOLD_OFF
    assert g.decide(said("shut up"), Context(since_spoke_s=4)).why == TOLD_OFF
    assert g.decide(said("stop"), Context(speaking=True)).why == TOLD_OFF
    assert g.decide(said("never mind"), Context(portal_open=True, since_open_s=30, since_spoke_s=30)).why != TOLD_OFF
    assert g.decide(said("not you"), Context(since_spoke_s=4, told_off=False)).why != TOLD_OFF


# --------------------------------------------------------------------------------------------- the veto
def test_the_learned_veto_turns_down_borderline_openings_only():
    seen = []

    def veto(f):
        seen.append(f)
        return True

    g = gate(Judge(YES), veto=veto)
    assert g.decide(said("Kurooto, what's due?")).addressed  # the cap: its name first, its own spelling
    assert g.decide(said("hey kuroto set a timer")).addressed  # a known spelling: the cap too
    assert seen == []
    d = g.decide(said("kurootoh what's due"))  # a near miss: borderline
    assert d.klass == CHATTER and d.why == VETOED
    d = g.decide(said("what time is the lab tomorrow"))  # the local model's: borderline
    assert d.klass == CHATTER and d.why == VETOED
    assert g.decide(said("I think so"), window()).why == VETOED  # the conversation going on: borderline
    assert all("rule" in f and "text" not in f for f in seen)


# ----------------------------------------------------------------------------------------------- learning
def row(rule="the local model", **kw):
    return {"rule": rule, "name_exact": False, "name_near": False, "where": "", "voices": None, "speaker": "owner",
            "score": 0.7, "since_chatter_s": None, "faces": None, "careful": False, **kw}  # fmt: skip


def test_the_learner_needs_enough_rows_and_both_kinds(tmp_path):
    lr = learn.Learner(tmp_path)
    for _ in range(5):
        lr.record(row(), 1)
    out = lr.train()
    assert out["rows"] == 5 and not out["active"] and lr.chance(row()) is None and not lr.veto(row())


def test_the_learner_learns_misfires_and_vetoes_them(tmp_path):
    lr = learn.Learner(tmp_path)
    for _ in range(15):  # unsure voices with chatter just before, judged by the model: told off
        lr.record(row(speaker="unsure", score=0.4, since_chatter_s=5, careful=True), 0)
    for _ in range(15):  # the owner alone going on: went well
        lr.record(row("the conversation goes on"), 1)
    out = lr.train()
    assert out["active"] and out["rows"] == 30 and out["misfires"] == 15 and "w" not in out
    assert lr.veto(row(speaker="unsure", score=0.4, since_chatter_s=5, careful=True))
    assert not lr.veto(row("the conversation goes on"))
    assert lr.status()["vetoes"] == 1
    again = learn.Learner(tmp_path)  # kept in state: a restart keeps what it learned
    assert again.chance(row("the conversation goes on")) > 0.5


def test_the_learner_keeps_only_flags_and_numbers(tmp_path):
    lr = learn.Learner(tmp_path)
    lr.record({**row(), "text": "the pin is 4471", "rule": "something new", "e": [0.1] * 4}, 0)
    kept = json.loads((tmp_path / "gate-turns.jsonl").read_text())
    assert set(kept) == {*learn.KEYS, "label", "day"} and kept["rule"] == "other"
    assert "4471" not in (tmp_path / "gate-turns.jsonl").read_text()


# ------------------------------------------------------------------------------------------- the module
def test_told_off_stops_closes_and_notes_a_misfire(voice):
    stopped = []
    voice.speaker.stop = lambda: stopped.append(1)
    assert voice.hear(said("Kurooto, what's due this week?")) == "It's due Friday."
    assert voice.portal.open
    assert voice.hear(said("Not you, I was talking to my friend about the locker")) is None
    assert stopped and not voice.portal.open and len(voice.brain.got) == 1 and voice.spoken == ["It's due Friday."]
    ev = [e for e in voice.app.events.tail(50) if e["kind"] == "voice_misfire"]
    assert len(ev) == 1 and ev[0]["rule"] == "its name" and ev[0]["turn"] == "its name"
    rows = voice.learner.rows()
    assert len(rows) == 1 and rows[0]["label"] == 0 and rows[0]["rule"] == "its name" and rows[0]["name_exact"]
    kept = everything_kept(voice)
    assert "locker" not in kept and "friend" not in kept and "what's due" not in json.dumps(rows)
    portal = [e for e in voice.app.events.tail(50) if e["kind"] == "voice_portal"]
    assert portal[-1]["why"] == "told off"


def test_told_off_with_the_switch_off_is_an_ordinary_turn(voice):
    voice.app.settings.set("voice.listen.told_off", False)
    voice.hear(said("Kurooto, what's due this week?"))
    voice.hear(said("never mind"))
    assert not [e for e in voice.app.events.tail(50) if e["kind"] == "voice_misfire"]


def test_going_on_counts_as_good_and_the_statement_goes_through(voice):
    voice.hear(said("Kurooto, what's due this week?"))
    voice.hear(said("I think the lab report is first"))  # a statement, the same voice, right after: it goes on
    assert voice.brain.got == ["what's due this week?", "I think the lab report is first"]
    rows = voice.learner.rows()
    assert [r["label"] for r in rows] == [1] and rows[0]["rule"] == "its name"


def test_nothing_is_learned_with_learning_off(voice):
    voice.app.settings.set("voice.listen.learn_nightly", False)
    voice.hear(said("Kurooto, what's due this week?"))
    voice.hear(said("I think the lab report is first"))
    voice.hear(said("stop"))
    assert voice.learner.rows() == [] and voice.learn_nightly() is None


def test_the_nightly_fit_is_scheduled_and_reports_numbers(voice):
    jobs = voice.app.scheduler.get("voice:learn")
    assert jobs is not None
    for i in range(24):
        voice.learner.record(row(speaker="unsure" if i % 2 else "owner"), i % 2 == 0)
    out = voice.learn_nightly()
    assert out["active"] and out["rows"] == 24
    ev = [e for e in voice.app.events.tail(20) if e["kind"] == "voice_learned"][-1]
    assert ev["rows"] == 24 and ev["active"] is True and "w" not in ev
    st = voice.status()["learned"]
    assert st["rows"] == 24 and st["active"] and st["on"]
    assert "learned from 24 turns" in voice.line()


def test_forgetting_the_voice_forgets_the_learned_turns(voice):
    voice.learner.record(row(), 1)
    voice.learner.train()
    voice.voiceid.forget()
    assert voice.learner.rows() == [] and not voice.learner.model()


# ------------------------------------------------------------------------------------- Voice ID's help
def high(vid_, monkeypatch, on):
    """Thresholds that put the owner's voice in the "not sure" band (and others below it), when on[0]."""
    real = vid_.thresholds
    band = sid.Band(0.99, 0.2)
    monkeypatch.setattr(vid_, "thresholds", lambda t: sid.Thresholds(band, band) if on[0] else real(t))


def test_a_not_sure_voice_mentioning_it_is_careful(vid, monkeypatch):
    v = vid.v
    high(vid, monkeypatch, [True])
    v.app.settings.set("voice.speaker_id.face_assist", False)
    v.judge.answers = [NO]
    hear(v, "can you check this, Kurooto")
    assert v.portal.send.got == [] and not v.portal.open and len(v.judge.prompts) == 1
    hear(v, "Kurooto, what's due?", utt=2)
    assert v.portal.send.got == [("what's due?", "unsure")]


def test_face_assist_only_with_the_owner_alone_in_view(vid, monkeypatch):
    v = vid.v
    high(vid, monkeypatch, [True])
    nearby.set_view(v.app, 1, True)
    hear(v, "Kurooto, what's due?")
    assert v.portal.send.got[-1] == ("what's due?", "owner")
    v.portal.close("test")
    nearby.set_view(v.app, 2, False)
    hear(v, "Kurooto, what's due?", utt=2)
    assert v.portal.send.got[-1] == ("what's due?", "unsure")
    v.portal.close("test")
    nearby.set_view(v.app, 1, True)
    hear(v, "Kurooto, what's due?", who_voice=55, utt=3)  # someone else's voice: the face doesn't make it him
    assert v.portal.send.got[-1] == ("what's due?", "guest")
    v.portal.close("test")
    v.app.settings.set("voice.speaker_id.face_assist", False)
    hear(v, "Kurooto, what's due?", utt=4)
    assert v.portal.send.got[-1] == ("what's due?", "unsure")
    nearby.clear_view(v.app)


def test_a_face_confirmed_turn_that_went_well_refines_the_voice_print(vid, monkeypatch):
    v = vid.v
    v.app.settings.set("voice.speaker_id.adapt", True)
    high(vid, monkeypatch, [True])
    nearby.set_view(v.app, 1, True)
    before = len(vid.template().get("adapted") or [])
    hear(v, "Kurooto, what's due?")
    assert len(vid.template().get("adapted") or []) == before  # not yet: how it went isn't known
    hear(v, "and the one after that", utt=2)
    adapted = vid.template().get("adapted") or []
    assert len(adapted) == before + 1 and adapted[-1].get("face") and vid.face_learned == 1
    assert vid.status()["adapt"]["face"] == 1
    hear(v, "not you", utt=3)  # told off: the turn before it isn't learned from
    assert len(vid.template().get("adapted") or []) == before + 1
    nearby.clear_view(v.app)


def test_the_owner_s_conversation_carries_a_not_sure_voice(vid, monkeypatch):
    v = vid.v
    on = [False]
    high(vid, monkeypatch, on)
    hear(v, "Kurooto, what's due?")
    assert v.portal.send.got[-1] == ("what's due?", "owner")
    on[0] = True  # the same voice, now only "not sure": it stays his in the conversation he opened
    hear(v, "and what about the lab report", utt=2)
    assert v.portal.send.got[-1] == ("and what about the lab report", "owner")
    hear(v, "and the one after that", who_voice=55, utt=3)  # clearly someone else: not carried, not going on
    assert len(v.portal.send.got) == 2 and not v.portal.open
    v.app.settings.set("voice.speaker_id.carry_talk", False)
    on[0] = False
    hear(v, "Kurooto, what's due?", utt=4)
    on[0] = True
    hear(v, "what about the lab report?", utt=5)  # a question within close_s: sent, but as not sure
    assert v.portal.send.got[-1] == ("what about the lab report?", "unsure")


def test_decide_face_assist_and_talk_carry_rules():
    t = sid.Thresholds(sid.Band(0.5, 0.45), sid.Band(0.42, 0.37))
    face = sid.Ctx(face_owner=True)
    v = sid.decide(0.47, t, 3, face, face_assist=True)
    assert v.decision == "owner" and v.assisted and v.why == sid.FACE_WHY
    assert sid.decide(0.40, t, 3, face, face_assist=True).decision == "guest"  # below the margin: still not him
    assert sid.decide(0.47, t, 3, face, face_assist=True, strict=True).decision == "unsure"
    assert sid.decide(0.47, t, 3, sid.Ctx(face_owner=True, voices=2), face_assist=True).decision == "unsure"
    talk = sid.Ctx(portal_session=2, last_owner_at=100, last_owner_session=2, now=115, portal_open=True)
    v = sid.decide(0.47, t, 3, talk, carry_talk=True, carry_talk_s=20)
    assert v.decision == "owner" and v.carried and v.why == sid.TALK_WHY
    assert sid.decide(0.47, t, 3, talk, carry_talk=True, carry_talk_s=10).decision == "unsure"
    closed = sid.Ctx(portal_session=2, last_owner_at=100, last_owner_session=2, now=115, portal_open=False)
    assert sid.decide(0.47, t, 3, closed, carry_talk=True).decision == "unsure"


def test_face_presence_sets_the_view_from_each_frame(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    try:
        f = app.modules["face"]
        f._on_watch("view", faces=1, owner_alone=True)
        assert nearby.view(app) == (1, True)
        f._on_watch("watch", on=False, why="stopped")
        assert nearby.view(app) is None
    finally:
        app.close()
