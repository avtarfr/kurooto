"""Dream RSI, part three (core/tuning.py): the effort your requests get, which AI goes first and Start-by's sizes,
each replayed on what was recorded with today's rules always a candidate; one change a night across all areas (part
two's included), with Undo and a morning line; each change's outcome kept, and a kind you undid needs a clearer win;
a fix for a skill that keeps going wrong is only proposed (Apply or No), gated by the test cases."""

from __future__ import annotations

import datetime as dt
import json
import time
import uuid

import pytest

from kurooto.core import calm as calm_mod
from kurooto.core import events as events_mod
from kurooto.core import policy as policy_mod
from kurooto.core import tuning
from kurooto.modules import dreaming as dreaming_mod
from kurooto.providers import effort as effort_mod
from kurooto.providers.base import Result, Verdict

MON = dt.datetime(2026, 11, 2, 7, 30)


@pytest.fixture
def clock(env, monkeypatch):
    t = {"now": MON}
    for mod in (calm_mod, policy_mod, dreaming_mod, events_mod, tuning):
        monkeypatch.setattr(mod, "now", lambda: t["now"])
    env.app.settings.set("availability.night.enabled", False)
    return t


def job(app, *, ago_h: float, prompt: str = "", origin="low", level="low", verdict="ok", minutes=1.0, lane="you",
        corrected="", then="", payload=None, tries=()) -> str:  # fmt: skip
    """One finished request, `ago_h` hours before the clock, with its tries [(brain, verdict, seconds)]."""
    jid = "j" + uuid.uuid4().hex[:8]
    t = MON.timestamp() - ago_h * 3600
    with app.jobs._lock:
        app.jobs._db.execute(
            "insert into jobs(id,title,prompt,effort_req,effort,status,verdict,created,started,finished,seconds,lane,"
            "effort_from,corrected,then_action,then_payload) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (jid, prompt[:40], prompt or f"question {jid} about something else entirely", "auto", level,
             "ok" if verdict == "ok" else "failed", verdict, t, t, t + minutes * 60, minutes * 60, lane, origin,
             corrected, then, json.dumps(payload or {})),
        )  # fmt: skip
        for k, (brain, v, secs) in enumerate(tries):
            app.jobs._db.execute(
                "insert into attempts(job, brain, verdict, at, seconds, tool_calls) values(?,?,?,?,?,0)",
                (jid, brain, v, t + k, secs),
            )
    return jid


def missing_low_answers(app, n=10, missed=6):
    """Quick lookups rated low: most asked again within minutes, or corrected."""
    for k in range(n):
        h = 200 - k * 12
        if k < missed:
            if k % 2:
                job(app, ago_h=h, prompt=f"summary of week {k} lecture on group actions")
                job(app, ago_h=h - 0.1, prompt=f"summary of week {k} lecture on group actions please")
            else:
                job(app, ago_h=h, prompt=f"what does chapter {k} prove", corrected="that's not what I asked")
        else:
            job(app, ago_h=h, prompt=f"when is quiz {k}")
    for k in range(5):  # medium answers do fine, in about two minutes
        job(app, ago_h=150 - k * 10, origin="medium", level="medium", minutes=2, prompt=f"plan my day {k} with notes")


# ------------------------------------------------------------------------------------------- effort
def test_origin_and_the_tuned_level():
    assert effort_mod.pick_with_origin("high: why is the sky blue") == ("high", None)
    assert effort_mod.pick_with_origin("make revision notes for topology") == ("high", "notes")
    assert effort_mod.pick_with_origin("what's due") == ("medium", "medium")
    assert effort_mod.tuned("low", "low", {"low": "medium"}) == "medium"
    assert effort_mod.tuned("high", None, {"high": "low"}) == "high"  # a level you typed is never tuned
    assert effort_mod.tuned("medium", "medium", {"medium": "bogus"}) == "medium"


def test_effort_raised_when_quick_answers_keep_missing_with_a_line_and_undo(env, clock):
    app = env.app
    env.on("dreaming")
    missing_low_answers(app)
    d = tuning.night(app)
    assert d and d["area"] == "effort" and d["applied"] and d["target"] == "low" and d["set"] == "medium"
    assert app.settings.get("brain.effort_map") == {"low": "medium"}
    assert tuning.night(app) is None  # one round a night
    lines, buttons = tuning.morning(app, send=False)
    assert lines == [
        "Learned while you slept: requests the quick check calls quick now get medium effort, not low; 6 of the last "
        "13 were asked again, marked Wrong, corrected or ran out of time."
    ]
    assert buttons == [[("Undo", f"calm:{d['uid']}:undo")]]
    env.press(f"calm:{d['uid']}:undo")
    assert app.settings.get("brain.effort_map") == {}
    # the next night: the undone change counts against its kind, and the target is left alone
    clock["now"] = MON + dt.timedelta(days=1)
    assert tuning.night(app) is None or app.settings.get("brain.effort_map") == {}
    st = tuning._load(app)
    assert st["outcomes"]["effort.up"] == {"kept": 0, "undone": 1}
    assert tuning.trust(st, "effort.up") == 2.0 and tuning.trust(st, "effort.down") == 1.0
    assert "low" in tuning.blocked(app, st, "effort")
    assert "effort.up ×2" in tuning.show(app)


def test_effort_kept_when_answers_go_fine_and_the_margin_holds(env, clock):
    app = env.app
    for k in range(12):
        job(app, ago_h=100 - k * 5, prompt=f"when is lab {k}")
    d = tuning.night(app)
    assert d is None and app.settings.get("brain.effort_map") in ({}, None)
    last = [x for x in tuning._load(app)["decisions"] if x["area"] == "effort"][-1]
    assert not last["applied"] and last["best"] >= last["score"]  # today's is a candidate: never worse
    # misses, but a margin no replay clears
    clock["now"] = MON + dt.timedelta(days=1)
    missing_low_answers(app)
    app.settings.set("dreaming.tune_margin", 100)
    assert tuning.night(app) is None and app.settings.get("brain.effort_map") in ({}, None)
    # off: no round for it at all
    clock["now"] = MON + dt.timedelta(days=2)
    app.settings.set("dreaming.tune_margin", 3)
    app.settings.set("dreaming.tune_effort", False)
    tuning.night(app)
    assert app.settings.get("brain.effort_map") in ({}, None)
    assert not [x for x in tuning._load(app)["decisions"] if x["area"] == "effort" and x["at"][:10] == "2026-11-04"]


def test_kept_changes_earn_trust_back(env, clock):
    st = {"outcomes": {"sizing.down": {"kept": 0, "undone": 3}}}
    assert tuning.trust(st, "sizing.down") == 4.0
    st["outcomes"]["sizing.down"]["kept"] = 2
    assert tuning.trust(st, "sizing.down") == 3.0
    assert tuning.trust({"outcomes": {"x": {"undone": 9}}}, "x") == tuning.MAX_TRUST
    # a change left in place for KEPT_DAYS is counted as kept
    app = env.app
    missing_low_answers(app)
    d = tuning.night(app)
    clock["now"] = MON + dt.timedelta(days=tuning.KEPT_DAYS + 1)
    st = tuning._load(app)
    got = tuning.review(app, st)
    assert [x["outcome"] for x in got] == ["kept"] and st["outcomes"]["effort.up"]["kept"] == 1
    assert d["uid"]


def test_heard_marks_your_last_answer_as_missed(env, clock):
    app = env.app
    jid = "j" + uuid.uuid4().hex[:8]
    t = time.time()
    with app.jobs._lock:
        app.jobs._db.execute(
            "insert into jobs(id,title,prompt,status,verdict,created,finished,lane) values(?,?,?,?,?,?,?,?)",
            (jid, "q", "what is a sheaf", "ok", "ok", t - 60, t - 30, "you"),
        )
    assert tuning.heard(app, "what's due") is None
    assert tuning.heard(app, "that's not what I asked, I meant the lecture") == jid
    assert tuning.heard(app, "that's not what I asked") is None  # once per answer
    row = app.jobs._read("select corrected from jobs where id=?", (jid,))
    assert row[0] == "that's not what I asked, I meant the lecture"
    app.jobs.forget(0, time.time() + 1)  # forgotten with the request
    assert app.jobs._read("select corrected from jobs where id=?", (jid,))[0] == "-"


# --------------------------------------------------------------------------------------- fallbacks
def test_fallback_goes_first_where_the_main_ai_keeps_hitting_limits(env, clock):
    app = env.app
    app.settings.set("brain.main", "custom")
    app.settings.set("brain.fallback", "ollama")
    for k in range(8):  # medium requests: the main AI hits its limit, the fallback answers
        job(app, ago_h=100 - k * 8, origin="medium", level="medium",
            tries=[("custom", "rate_limited", 3), ("ollama", "ok", 40)])  # fmt: skip
    for k in range(4):  # low ones go fine on the main AI
        job(app, ago_h=90 - k * 8, tries=[("custom", "ok", 20)])
    d = tuning.night(app)
    assert d and d["area"] == "fallbacks" and d["target"] == "medium"
    assert app.settings.get("brain.fallback_first") == ["medium"]
    assert d["said"] == "medium-effort requests now try Ollama first, then your AI service"
    assert "failed 8 times on the last 8 of them (limits)" in d["why"]
    assert "medium effort: Ollama first" in tuning.show(app)


def test_the_tuned_order_and_effort_at_run_time(tmp_path, monkeypatch):
    from kurooto.app import App
    from tests.fakes.openai import FakeOpenAI

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    main, fb = FakeOpenAI(), FakeOpenAI(key="sk-other")
    app = App()
    try:
        app.secrets.set("custom.api_key", main.key)
        app.secrets.set("ollama.api_key", fb.key)
        app.settings.set("brain.base_urls", {"custom": main.base, "ollama": fb.base})
        models = {"low": "fast", "medium": "smart", "high": "smart"}
        app.settings.set("brain.models", {"custom": models, "ollama": models})
        app.settings.set("brain.main", "custom")
        app.settings.set("brain.fallback", "ollama")
        app.settings.set("brain.effort_map", {"medium": "high"})
        app.settings.set("brain.fallback_first", ["high"])
        jid = app.jobs.submit("is it raining", quiet=True)
        app.jobs.run_next()
        j = app.jobs.get(jid)
        assert (j.effort, j.brain) == ("high", "ollama")  # rated medium, tuned to high, where the fallback goes first
        assert app.jobs._read("select effort_from from jobs where id=?", (jid,))[0] == "medium"
        bg = app.jobs.submit("is it raining", quiet=True, background=True)
        app.jobs.run_next()
        assert (app.jobs.get(bg).effort, app.jobs.get(bg).brain) == ("medium", "custom")  # not your request
        typed = app.jobs.submit("low: is it raining", quiet=True)
        app.jobs.run_next()
        assert app.jobs.get(typed).effort == "low"
    finally:
        main.close()
        fb.close()
        app.close()


# ------------------------------------------------------------------------------------------ sizing
@pytest.fixture
def deadlines(env, clock, monkeypatch):
    from kurooto.modules import startby as sb_mod

    monkeypatch.setattr(sb_mod, "now", lambda: clock["now"])
    env.on("subjects", "deadlines", "study")
    env.say("/subject add Topology (topo)")
    assert env.app.enable("startby")[0]
    return env


def done_report(env, title: str, due: dt.datetime, study_h: dict[int, float]) -> str:
    """A report done the day before it was due, with that many hours of Topology on days before it."""
    dl = env.app.modules["deadlines"]
    dl.add(title, due, subject="topology")
    i = next(i for i, it in dl.items().items() if it["title"] == title)
    items = dl.items()
    items[i].update(status="done", done_at=(due - dt.timedelta(days=1)).isoformat())
    from kurooto.core.state import jsave

    jsave(dl.file, items)
    st = env.app.modules["study"]
    for back, h in study_h.items():
        st.add("topology", h * 3600, day=(due - dt.timedelta(days=back)).date())
    return i


def test_sizing_learns_from_study_time_and_your_taps(deadlines, clock):
    env, app = deadlines, deadlines.app
    for k in range(4):  # four reports, each about 5 hours of Topology in the days before it
        done_report(env, f"Topology report {k}", MON - dt.timedelta(days=10 + 16 * k), {2: 2.5, 3: 2.5})
    rows = tuning.samples(app)
    assert sorted((r["kind"], r["hours"], r["how"]) for r in rows) == [("report", 5.0, "study")] * 4
    d = tuning.night(app)
    assert d and d["area"] == "sizing" and d["target"] == "report" and d["set"] == 5.0
    assert app.settings.get("startby.sizes.report") == 5.0
    assert d["said"] == "Start-by sizes a report at about 5 h (a day), not 12 h"
    assert d["why"] == "the last 4 took about 5 h (4 from study time)"
    # a size you set yourself is never changed
    clock["now"] = MON + dt.timedelta(days=1)
    app.settings.set("startby.sizes.report", 20)
    st = tuning._load(app)
    got = tuning.sizing_plan(app, st)
    assert got is None or got[1] is None


# ------------------------------------------------------------------------------------- one a night
def test_one_change_a_night_across_all_areas(deadlines, clock):
    env, app = deadlines, deadlines.app
    missing_low_answers(app)
    for k in range(4):
        done_report(env, f"Topology report {k}", MON - dt.timedelta(days=10 + 16 * k), {2: 2.5, 3: 2.5})
    d = tuning.night(app)
    assert d["applied"]
    ds = [x for x in tuning._load(app)["decisions"] if x["at"][:10] == "2026-11-02"]
    assert sum(bool(x.get("applied")) for x in ds) == 1
    assert [x["area"] for x in ds if x.get("waited")] == ["sizing" if d["area"] == "effort" else "effort"]
    # the other goes in the next night
    clock["now"] = MON + dt.timedelta(days=1)
    d2 = tuning.night(app)
    assert d2["applied"] and d2["area"] != d["area"]


def test_dreaming_says_it_and_dream_policy_shows_every_area(env, clock):
    app = env.app
    env.on("dreaming")
    missing_low_answers(app)
    text = app.modules["dreaming"].report(send=True)
    assert "Learned while you slept: requests the quick check calls quick now get medium effort" in text
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p][-1]
    datas = [b["callback_data"] for row in sent["reply_markup"]["inline_keyboard"] for b in row]
    assert any(x.startswith("calm:") and x.endswith(":undo") for x in datas)
    shown = env.say("/dream policy")
    bits = (
        "When messages that come by themselves reach you",
        "Effort for your requests, tuned",
        "Which AI goes first",
        "Start-by sizes, tuned",
        "Fixes to skills that keep going wrong, proposed: off",
    )
    assert all(bit in shown for bit in bits)
    assert "effort: requests the quick check calls quick now get medium effort" in shown


# ------------------------------------------------------------------------------------------ proposals
def skills_on(env):
    env.app.secrets.set("custom.api_key", "sk-fake")
    env.app.settings.set("brain.base_urls", {"custom": "http://127.0.0.1:9/v1"})  # never reached: nothing runs
    env.app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
    env.app.settings.set("brain.main", "custom")
    env.on("chat", "skills", "learning", "dreaming")
    env.app.settings.set("dreaming.propose_prompts", True)


def test_a_skill_that_keeps_going_wrong_gets_a_proposal_never_applied_by_itself(env, clock):
    app = env.app
    skills_on(env)
    for k in range(3):
        job(app, ago_h=50 - k * 5, prompt=f"journal entry {k}", then="skills.done", payload={"name": "journal"},
            corrected="no, put the date in the title every time")  # fmt: skip
    tuning.night(app)
    st = tuning._load(app)
    p = st["proposal"]
    assert p["status"] == "waiting" and p["name"] == "journal" and p["n"] == 3
    asked = app.jobs.get(p["job"])
    assert asked.status == "queued" and "put the date in the title" in asked.prompt
    from kurooto.modules.skills import load_skill

    s = load_skill(app, "journal")
    old = open(s.path, encoding="utf-8").read()
    new = old.rstrip() + "\n\nPut the date in the title.\n"
    answer = Result(
        Verdict.OK,
        text=f"CHANGE: the title carries the date\nFIXES 1: yes\nFIXES 2: yes\nFIXES 3: no\n```skill\n{new}```",
    )
    payload = json.loads(app.jobs._read("select then_payload from jobs where id=?", (p["job"],))[0])
    tuning.proposal_ready(app, asked, answer, payload)
    p = tuning.proposal(app)
    assert p and p["fixes"] == 2
    assert load_skill(app, "journal").body == s.body  # nothing applied yet
    lines, buttons = tuning.morning(app, send=False)
    assert lines == [
        "A fix for /journal, which went wrong 3 times lately: the title carries the date. It fixes 2 of them by the "
        "AI's own replay; /dream proposal shows it."
    ]
    prop = p["prop"]  # 0.7.0: a proposal (core/proposals.py), with the diff and Apply / Change / Discard
    assert buttons == [[("Apply", f"prop:{prop}:apply"), ("Change", f"prop:{prop}:change"),
                        ("Discard", f"prop:{prop}:discard")]]  # fmt: skip
    assert "Put the date in the title." in env.say("/dream proposal")
    from kurooto.core import proposals

    assert "+Put the date in the title." in proposals.diff_text(app, proposals.get(app, prop))
    assert proposals.get(app, prop)["night"] and prop in env.say("/proposals")
    assert env.press(f"prop:{prop}:apply").startswith("Changed /journal")
    assert "Put the date in the title." in load_skill(app, "journal").body
    assert tuning.proposal(app) is None and proposals.get(app, prop)["status"] == "applied"
    d = tuning._load(app)["decisions"][-1]
    assert d["area"] == "prompts" and d["applied"] and tuning.live(app, d)


def test_a_proposal_that_fixes_too_little_or_gets_a_no(env, clock):
    app = env.app
    skills_on(env)
    for k in range(2):
        job(app, ago_h=30 - k * 5, prompt=f"journal {k}", then="skills.done", payload={"name": "journal"},
            corrected="that's wrong")  # fmt: skip
    tuning.night(app)
    p = tuning._load(app)["proposal"]
    from kurooto.modules.skills import load_skill

    old = open(load_skill(app, "journal").path, encoding="utf-8").read()
    payload = {"pid": p["pid"], "name": "journal", "base": tuning._sha(old), "n": 2, "cases": 2}
    weak = Result(Verdict.OK, text=f"CHANGE: x\nFIXES 1: no\nFIXES 2: no\n```skill\n{old.rstrip()}\nMore.\n```")
    tuning.proposal_ready(app, None, weak, payload)
    assert tuning._load(app)["proposal"]["status"] == "dropped" and tuning.proposal(app) is None
    # one that's offered, then declined: not proposed again for that skill, and the next needs a clearer win
    st = tuning._load(app)
    st["proposal"] = {**p, "status": "waiting"}
    tuning._save(app, st)
    good = Result(Verdict.OK, text=f"CHANGE: y\nFIXES 1: yes\nFIXES 2: yes\n```skill\n{old.rstrip()}\nMore.\n```")
    tuning.proposal_ready(app, None, good, payload)
    assert env.press(f"rsi:{p['pid']}:no").startswith("Left /journal as it is")
    st = tuning._load(app)
    assert "journal" in tuning.blocked(app, st, "prompts") and tuning.trust(st, "prompts") == 2.0
    assert open(load_skill(app, "journal").path, encoding="utf-8").read() == old
