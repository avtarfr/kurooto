"""0.8.10: the Brain console (mind/console.py, GET /api/brain/console, static/views/brainconsole.js): decisions that
open to their reasons and evidence, a timeline filtered by part and day, search, each part's switches and settings next
to what it's doing, experiments, beliefs, skills, plans, the model of you, what it forgot, stops and limits, the journal
and story headings. Read-only, plain facts: nothing named for money or health, senses as counts."""

from __future__ import annotations

import datetime as dt
import json
import os
import time

import pytest

from kurooto import mind
from kurooto.core.state import jsave
from kurooto.mind import console, records
from kurooto.mind import log as mlog

PRIVATE_LINE = "words-that-stay-in-their-own-file"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    yield a
    mind.forget_client(a)
    a.close()


def write_log(app, monkeypatch, rows):
    """The test plays the scorekeeper for a moment (only it writes the log)."""
    monkeypatch.setattr(mlog, "_writer_pid", os.getpid())
    lg = mlog.MindLog(app.paths.state / "mind" / "log.db", writable=True)
    seqs = [lg.append(kind, body, ts) for kind, body, ts in rows]
    lg.close()
    monkeypatch.setattr(mlog, "_writer_pid", None)
    return seqs


@pytest.fixture
def brain(app, monkeypatch):
    now = time.time()
    yday = now - 86400
    dec = records.make(
        "message:deadline",
        candidates=[{"action": "message:deadline", "score": 0.8}, {"action": "wait", "score": 0.3}],
        setpoints=["deadlines_met"],
        claim={"setpoint": "deadlines_met", "effect": "+", "by": "2026-11-01"},
        scored_reason="calm.deadline_soon",
        source="rules",
        id="d" * 32,
    )
    seqs = write_log(
        app,
        monkeypatch,
        [
            ("deadline_added", {"id": "dl1"}, yday),
            ("job_ended", {"id": "j1", "verdict": "ok"}, yday + 60),
            ("deadline_added", {"id": "dl2"}, now - 400),
            ("decision", dec, now - 300),
            ("gate_receipt", {"did": "sent", "would_have": "sent", "msg_id": "m1"}, now - 299),
            ("outcome", {"decision": "d" * 32, "result": "acted"}, now - 200),
            ("stop_span", {"start": now - 7200, "end": now - 3600, "gap": "sleep"}, now - 3600),
            ("forget_event", {"hash": "ab12", "n": 4}, now - 100),
            ("lab_result", {"project": "ring-model", "wins": 2, "replicated": 1}, now - 90),
            ("budget_tick", {"payment_amount": 31337.77, "load": 0.4}, now - 50),
        ],
    )
    s = app.paths.state
    jsave(
        s / "mind-beliefs.json",
        {
            "rows": [
                {"id": "b1", "text": "The essay is due Friday", "source": "said", "confidence": 1.0, "topic": "essay",
                 "at": now - 500, "outcome": None},
                {"id": "b2", "text": "Rent goes out on the first", "source": "saw", "confidence": 1.0, "topic": "",
                 "at": now - 400, "outcome": None},
                {"id": "b3", "text": "Mornings go better after an early night", "source": "inferred",
                 "confidence": 0.6, "topic": "", "at": now - 300, "outcome": True},
            ]
        },
    )  # fmt: skip
    jsave(
        s / "mind-tom.json",
        {
            "rows": [
                {"id": "t1", "part": "knowledge", "subject": "linear algebra", "claim": "knows eigenvalues",
                 "source": "saw", "confidence": 0.8, "evidence": ["q1"], "updated": now},
                {"id": "t2", "part": "goal", "subject": "doctor", "claim": "see the doctor", "source": "said",
                 "confidence": 1, "evidence": [], "updated": now},
            ],
            "forgot": ["x"],
        },
    )  # fmt: skip
    jsave(
        s / "mind-workspace.json",
        {"winners": [{"item_id": "deadline:dl2", "kind": "deadline", "text": "Essay draft", "salience": 0.7},
                     {"item_id": "read:today", "kind": "read", "text": PRIVATE_LINE, "salience": 0.5,
                      "private": True}]},
    )  # fmt: skip
    jsave(s / "mind-forget.json", {"forgets": 2, "uses": {}})
    improve = {"rows": [{"id": "c1", "layer": "L1", "title": "Shorter digest", "status": "shadow"}]}
    jsave(s / "mind-improve.json", improve)
    from kurooto.mind.skills import library

    sk = library.folder(app, "summarise-lecture")
    sk.mkdir(parents=True, exist_ok=True)
    skill = {"slug": "summarise-lecture", "title": "Summarise a lecture", "kind": "prompt", "when": "after a class",
             "status": "always-ask", "uses": 3, "ok": 2, "updated": now}  # fmt: skip
    jsave(sk / "skill.json", skill)
    from kurooto.mind import journal

    day = dt.date.today().isoformat()
    (s / journal.DIR).mkdir(parents=True, exist_ok=True)
    jsave(s / journal.DIR / "index.json", {day: {"lines": 3, "rejected": 1, "facts": 4}})
    jsave(
        s / journal.DIR / f"{day}.json",
        {"day": day, "lines": [{"text": "I sent one reminder about a deadline.", "seqs": [seqs[3]], "struck": False}]},
    )
    (s / "mind-story" / "weeks").mkdir(parents=True, exist_ok=True)
    chapter = {"week": "2026-W43", "lines": [{"text": PRIVATE_LINE}], "quoted": []}
    jsave(s / "mind-story" / "weeks" / "2026-W43.json", chapter)
    return {"seqs": seqs, "decision": dec["id"]}


def test_off_says_so_and_brain_off_is_plain(app):
    app.settings.set("mind.console.on", False)
    code, out = console.view(app, {})
    assert code == 200 and out["off"] and "mind.console.on" in out["why"]
    app.settings.set("mind.console.on", True)
    app.settings.set("modules.enabled", [])
    code, out = console.view(app, {})
    assert code == 200 and out["on"] is False and out["records"] == 0 and out["parts_on"] == 0


def test_the_switch_is_a_documented_setting():
    from pathlib import Path

    guide = (Path(__file__).parents[2] / "docs" / "SETTINGS_GUIDE.md").read_text(encoding="utf-8")
    assert "`mind.console.on`" in guide and "`calls.views_brain`" in guide


def test_a_decision_opens_to_its_reasons_and_evidence(app, brain):
    _, out = console.view(app, {})
    d = out["decisions"][0]
    assert d["id"] == brain["decision"] and d["action"] == "message:deadline" and d["outcome"] == "acted"
    assert d["reason"] == "calm.deadline_soon" and d["candidates"][1] == {"action": "wait", "score": 0.3}
    code, full = console.view(app, {"view": "decision", "id": brain["decision"]})
    assert code == 200 and full["claim"] == {"setpoint": "deadlines_met", "effect": "+", "by": "2026-11-01"}
    ev = full["evidence"]
    assert [r["kind"] for r in ev["before"]][-1] == "deadline_added"  # what set it off
    assert ev["after"][0]["kind"] == "gate_receipt" and "outcome" in [r["kind"] for r in ev["after"]]
    assert ev["learned"][0] == ["Its class", "ALWAYS: always asks"]  # a message it starts always asks first
    assert ev["journal"] == [{"day": dt.date.today().isoformat(), "text": "I sent one reminder about a deadline."}]
    assert console.view(app, {"view": "decision", "id": "nope"})[0] == 404
    assert console.view(app, {"view": "decision", "id": "x' OR 1=1 --"})[0] == 404


def test_the_timeline_filters_by_part_and_day_and_pages(app, brain):
    _, t = console.view(app, {"view": "timeline"})
    assert [r["seq"] for r in t["rows"]] == sorted(brain["seqs"], reverse=True)
    _, t = console.view(app, {"view": "timeline", "part": "autonomy"})
    assert {r["kind"] for r in t["rows"]} == {"decision", "outcome"}
    _, t = console.view(app, {"view": "timeline", "part": "log"})
    assert {r["kind"] for r in t["rows"]} == {"deadline_added", "job_ended"}  # what it saw: Kurooto's own events
    _, t = console.view(app, {"view": "timeline", "part": "gate"})
    assert [r["kind"] for r in t["rows"]] == ["gate_receipt"]
    yday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    _, t = console.view(app, {"view": "timeline", "day": yday})
    assert {r["kind"] for r in t["rows"]} <= {"deadline_added", "job_ended"} and t["day"] == yday
    _, t = console.view(app, {"view": "timeline", "limit": "3"})
    assert len(t["rows"]) == 3 and t["more"]
    _, t2 = console.view(app, {"view": "timeline", "limit": "3", "before": str(t["rows"][-1]["seq"])})
    assert t2["rows"][0]["seq"] == t["rows"][-1]["seq"] - 1
    assert console.view(app, {"view": "timeline", "part": "Robert'); DROP"})[0] == 400


def test_nothing_named_for_money_or_health_and_senses_are_counts(app, brain):
    _, out = console.view(app, {})
    text = json.dumps(out)
    assert "payment_amount" not in text and "31337.77" not in text  # a money field (no timestamp holds 31337.77)
    assert "Rent goes out" not in text and out["beliefs"]["hidden"] == 1
    assert "see the doctor" not in text and out["model"]["counts"]["goal"] == 1
    assert PRIVATE_LINE not in text  # a private spotlight item, the story's sentences
    assert out["thinking"]["rows"][0]["text"] == "Essay draft" and out["thinking"]["rows"][1]["text"] == ""
    for r in out["senses"]["rows"]:
        assert set(r) == {"id", "name", "on", "today"} and isinstance(r["today"], int)
    assert out["memory"]["story"] == [{"week": "2026-W43", "lines": 1, "struck": 0, "quoted": 0}]
    assert out["memory"]["journal"][0] == {"day": dt.date.today().isoformat(), "lines": 3, "rejected": 1, "facts": 4}
    assert out["memory"]["forgot"]["times"] == 2 and out["memory"]["forgot"]["events"][0]["n"] == 4
    assert console.clean_text("pay the hospital bill") == console.LEFT_OUT


def test_each_part_has_its_switch_settings_and_what_it_is_doing(app, brain):
    _, out = console.view(app, {})
    ps = {p["id"]: p for isl in out["islands"] for p in isl["parts"]}
    assert len(ps) == out["parts_total"] == 31
    gate = ps["gate"]
    assert gate["switch"] == "mind.gate.on" and gate["settings"][0]["key"] == "mind.gate.on"
    assert {"mind.gate.max_per_day", "mind.gate.max_per_hour"} <= {s["key"] for s in gate["settings"]}
    assert gate["doing"]["n24"] == 1 and "gate" in gate["doing"]["line"] and "today" in gate["doing"]["now"]
    assert ps["autonomy"]["doing"]["n24"] == 2
    assert ps["log"]["doing"]["n"] == 3 and any(s["key"] == "mind.console.on" for s in ps["log"]["settings"])
    assert all(s["key"] != "mind.tom.attention" for s in ps["tom"]["settings"])
    assert ps["deep"]["settings"][0]["key"] == "mind.tom.attention"
    app.settings.set("mind.lab.projects", ["/home/someone/research/ring"])
    _, out = console.view(app, {})
    lab = {p["id"]: p for isl in out["islands"] for p in isl["parts"]}["lab"]
    assert next(s for s in lab["settings"] if s["key"] == "mind.lab.projects")["value"] == "1 folder"


def test_experiments_beliefs_skills_and_plans(app, brain):
    _, out = console.view(app, {})
    assert out["experiments"]["improve"][0]["status"] == "shadow"
    assert out["skills"]["rows"][0]["slug"] == "summarise-lecture" and out["skills"]["rows"][0]["ok"] == 2
    b = {r["id"]: r for r in out["beliefs"]["rows"]}
    assert b["b3"]["source"] == "inferred" and b["b3"]["outcome"] is True
    assert out["plans"]["on"] in (True, False) and isinstance(out["plans"].get("rows", []), list)
    assert out["memory"]["stops"]["spans"][0]["kind"] == "sleep"


def test_search_finds_the_log_and_the_rest(app, brain):
    _, r = console.view(app, {"view": "search", "q": "deadline"})
    assert {x["kind"] for x in r["log"]} >= {"deadline_added", "decision"}
    _, r = console.view(app, {"view": "search", "q": "eigen"})
    assert r["other"][0]["in"] == "model"
    _, r = console.view(app, {"view": "search", "q": "max_per_hour"})
    assert any(x["in"] == "settings" and x["part"] == "gate" for x in r["other"])
    _, r = console.view(app, {"view": "search", "q": "mind.gate.on"})  # a switch reads on or off, not True
    assert next(x for x in r["other"] if x["text"] == "mind.gate.on")["note"] in ("on", "off")
    _, r = console.view(app, {"view": "search", "q": "100%"})  # a wildcard is a character here
    assert r["log"] == []


def test_the_phones_copy_carries_evidence_and_is_small(app, brain):
    snap = console.snapshot(app, phone=True)
    assert snap["kind"] == "brain" and snap["decisions"][0]["evidence"]["after"]
    assert len(json.dumps(snap)) < 400_000


def test_the_api_route():
    from pathlib import Path

    api = (Path(__file__).parents[2] / "src" / "kurooto" / "web" / "api.py").read_text(encoding="utf-8")
    assert 'path == "brain/console"' in api and "console.view(self.app, q)" in api
