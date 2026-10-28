"""The 0.8.17 call fixes on your computer's side: skipping many classes (or commitments) is one tool call, and the end
of a call sent twice (the call page closing, the app hanging up a call its screen was closed on) is kept once."""

from __future__ import annotations

import json

from kurooto.core.clock import now

SUBJECTS = [
    {"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["la"]},
    {"name": "Probability", "slug": "probability", "aliases": ["prob"]},
    {"name": "Real Analysis", "slug": "real-analysis", "aliases": ["ra"]},
]


def today_classes(app):
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now().weekday()]
    app.settings.set("subjects.list", SUBJECTS)
    app.settings.set(
        "subjects.timetable",
        [
            {"day": day, "start": "09:00", "end": "09:55", "subject": "linear-algebra"},
            {"day": day, "start": "10:00", "end": "10:55", "subject": "probability"},
        ],
    )


def test_skip_class_takes_one_several_or_all_of_today_in_one_call(env):
    app = env.app
    env.on("subjects")
    today_classes(app)
    sub = app.modules["subjects"]
    assert sub._tool_skip({"subject": "la"}) == "Skipping Linear Algebra today."  # the old single argument
    assert sub.skipped() == {"linear-algebra"}
    sub.set_skip(["linear-algebra"], add=False)
    out = sub._tool_skip({"subjects": ["prob", "Real Analysis", "chemistry"]})
    assert out == "Skipping Probability, Real Analysis today. I don't know: chemistry."
    assert sub.skipped() == {"probability", "real-analysis"}
    sub.set_skip(["probability", "real-analysis"], add=False)
    for said in (["all"], ["all classes"], ["All of today's classes"], ["everything"]):
        assert sub._tool_skip({"subjects": said}) == "Skipping all of today's classes: Linear Algebra, Probability."
    assert sub.skipped() == {"linear-algebra", "probability"}  # not Real Analysis: no class today
    assert sub._tool_skip({"subject": "all"}).startswith("Skipping all of today's classes")
    assert sub._tool_skip({"subjects": ["chemistry"]}) == "I don't know that subject."
    app.settings.set("subjects.timetable", [])
    assert sub._tool_skip({"subjects": ["all"]}) == "There are no classes today."


def test_the_call_is_told_to_skip_many_in_one_call(env):
    app = env.app
    env.on("subjects")
    env.on("commitments")
    tools = {t.name: t for t in app.modules["calls"].tools()}
    d = tools["skip_class"].declaration()["parameters"]
    assert d["required"] == [] and d["properties"]["subjects"]["type"] == "array"
    assert tools["skip_commitment"].declaration()["parameters"]["properties"]["names"]["items"] == {"type": "string"}
    si = app.modules["calls"].config_template()["systemInstruction"]
    assert "ONE skip_class call with subjects" in si and "never skip_commitment" in si


def test_skip_commitment_takes_several_or_all_of_today(env):
    app = env.app
    env.on("commitments")
    env.say("/busy add gym daily 18:00-19:00")
    env.say("/busy add shift daily 20:00-23:00")
    com = app.modules["commitments"]
    assert com._tool_skip({"name": "gym"}).startswith("Skipping gym today")  # the old single argument
    com.set_skip("gym", add=False)
    assert com._tool_skip({"names": ["gym", "shift"]}) == "Skipping gym, shift today; calls are allowed then."
    for n in ("gym", "shift"):
        com.set_skip(n, add=False)
    assert com._tool_skip({"names": ["all"]}) == "Skipping gym, shift today; calls are allowed then."
    assert com.skipped() == {"gym", "shift"}
    assert com._tool_skip({"names": ["yoga"]}) == "I don't know that one."


def test_the_same_end_of_a_call_twice_is_kept_once(env):
    import datetime as dt

    app = env.app
    app.settings.set("availability.night.enabled", False)
    c = app.modules["calls"]
    said = [{"who": "Sam", "text": "I skipped all classes"}, {"who": "Kurooto", "text": "Done."}]
    body = json.dumps({"lines": said, "since": "31", "ended": True, "layer": "live"}).encode()
    app.availability.set_on_call(now() + dt.timedelta(seconds=90))
    assert c.handle_request("POST", "/transcript", body) == (200, {"ok": True})
    assert app.availability.on_call_until() is None  # the end of the call: "on a call" is over
    app.availability.set_on_call(now() + dt.timedelta(seconds=90))
    assert c.handle_request("POST", "/transcript", body) == (200, {"ok": True, "again": True})
    assert app.availability.on_call_until() is None  # cleared again all the same
    assert len(list((app.paths.state / "calls" / "transcripts").glob("*.txt"))) == 1
    other = json.dumps({"lines": said, "since": "32", "ended": True}).encode()  # another call that said the same
    c.handle_request("POST", "/transcript", other)
    assert len(list((app.paths.state / "calls" / "transcripts").glob("*.txt"))) == 2
