"""0.7.3: the fixes from the 24 Oct bug list: a slow "On it", a call over a call, a refused agy run, Profile sync on a
fresh install, and the concept graph's tools. Fake brains stand in for the AI."""

from __future__ import annotations

import json
import time

import pytest

from kurooto import providers
from kurooto.providers.base import Result, Task, Verdict


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    yield a
    a.close()


# ---------------------------------------------------------------------------------------------- 1: a slow "On it"
def test_telegram_has_threads_of_its_own_and_notes_a_late_message(app):
    tg = app.modules["telegram"]
    assert tg._poller._thread_name_prefix == "tg-poll" and tg._handlers._thread_name_prefix == "tg-handle"
    now = time.time()
    tg._lag([{"update_id": 1, "message": {"date": int(now) - 3}}, {"update_id": 2, "message": {"date": int(now) - 68}}])
    lag = [e for e in app.events.tail(10) if e["kind"] == "telegram_lag"]
    assert [e["update"] for e in lag] == [2] and lag[0]["seconds"] >= 67


def test_a_request_you_typed_goes_before_automatic_work(app):
    j = app.jobs
    auto = j.submit("write the journal", title="Journal", lane="bg")
    mine = j.submit("what's due?", title="mine", reply_to="telegram:1")
    other_auto = j.submit("another", title="auto2")  # same lane as yours, but nobody waits for it
    assert j._claim("you") == mine and j._claim("you") == other_auto and j._claim("bg") == auto


def test_the_check_in_notes_run_beside_what_you_type(app):
    import inspect

    from kurooto.modules import checkins

    src = inspect.getsource(checkins.Checkins._notes)
    assert src.count('lane="bg"') == 2  # the journal and the study logs


# ---------------------------------------------------------------------------------------------- 2: a call over a call
def test_a_call_waits_for_one_of_its_own(app):
    calls = app.modules["calls"]
    calls.dir.mkdir(parents=True, exist_ok=True)
    assert calls.busy_with() == ""
    rings = calls.dir / "rings.json"
    rings.write_text(
        json.dumps({"1": {"reason": "x", "alarm": False, "key": "k", "at": time.time(), "state": "ringing"}})
    )
    assert calls.busy_with() == "a call is ringing"
    assert calls.ring("deadline: essay", key="deadlines:essay", why="deadlines.call") == ""  # waits
    assert calls.ring("you asked me to call", key="", why="calls.own") != ""  # a call you asked for goes through
    assert [e for e in app.events.tail(5) if e["kind"] == "call_not_placed" and e.get("busy") == "a call is ringing"]
    rings.write_text(
        json.dumps({"1": {"reason": "x", "alarm": False, "key": "k", "at": time.time() - 600, "state": "ringing"}})
    )
    assert calls.busy_with() == ""  # a ring nobody answered long ago doesn't block
    rings.write_text(
        json.dumps({"1": {"reason": "x", "alarm": False, "key": "k", "at": time.time(), "state": "answered"}})
    )
    (calls.dir / "live.json").write_text(json.dumps({"key": "k", "reason": "check-in", "at": time.time()}))
    assert calls.busy_with() == "a call is going on"


def test_an_alarm_rings_even_over_a_call(app):
    calls = app.modules["calls"]
    calls.dir.mkdir(parents=True, exist_ok=True)
    (calls.dir / "live.json").write_text(json.dumps({"key": "k", "reason": "check-in", "at": time.time()}))
    assert calls.busy_with() and "busy" not in str([e for e in app.events.tail(3) if e["kind"] == "call_not_placed"])
    calls.ring("wake up", alarm=True, key="alarm:ring")
    assert not [e for e in app.events.tail(5) if e["kind"] == "call_not_placed" and e.get("busy")]


def test_the_phone_checks_it_is_in_a_call_before_ringing():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "android/src/io/github/avtarfr/kurooto/ListenService.java").read_text()
    assert "static boolean phoneBusy(" in src and "MODE_IN_CALL" in src and "MODE_IN_COMMUNICATION" in src
    assert "!alarm && !local && phoneBusy(this)" in src  # an alarm still rings


# ---------------------------------------------------------------------------------------------- 3: a refused agy run
def test_the_ai_is_told_never_to_run_code_to_look_inside_kurooto(app):
    from kurooto.providers.context import headless_context

    text = headless_context(app)
    assert "Never run commands or scripts" in text and "refused" in text


class Refused:
    """An AI whose first try runs a command unattended runs refuse (after using a tool); its second, told not to,
    finishes."""

    id, label, kind = "agy", "Antigravity", "cli"

    def __init__(self, second=Verdict.OK):
        self.tasks, self.second = [], second

    def available(self):
        return True, ""

    def prepare(self, app):
        pass

    def mark_worked(self, app):
        pass

    def run(self, task: Task):
        self.tasks.append(task)
        if len(self.tasks) == 1:
            return Result(
                Verdict.DENIED, "", 2.0, "agy stopped: it tried something unattended runs aren't allowed to do"
            )
        return Result(self.second, "Done.", 2.0) if self.second == Verdict.OK else Result(self.second, "", 2.0, "no")


def test_a_refused_run_is_tried_once_more_and_told_what_is_done(app, monkeypatch):
    brain = Refused()
    monkeypatch.setattr(providers, "build", lambda a, w: brain if w == "agy" else None)
    app.settings.set("brain.main", "agy")
    jid = app.jobs.submit("write my journal")
    job_steps = app.jobs.steps.setdefault(jid, [])
    job_steps.append({"name": "write_note", "args": "{}"})  # what it did before the refused command
    app.jobs.run_next()
    assert len(brain.tasks) == 2
    assert "Don't run commands" in brain.tasks[1].prompt and "write_note" in brain.tasks[1].prompt
    assert "Don't run commands" not in brain.tasks[0].prompt
    assert [e for e in app.events.tail(20) if e["kind"] == "job_retried"]
    job = app.jobs.get(jid)
    assert job.status == "ok" and job.result == "Done."


def test_a_second_refusal_is_final(app, monkeypatch):
    brain = Refused(second=Verdict.DENIED)
    monkeypatch.setattr(providers, "build", lambda a, w: brain if w == "agy" else None)
    app.settings.set("brain.main", "agy")
    jid = app.jobs.submit("write my journal")
    app.jobs.run_next()
    assert len(brain.tasks) == 2  # once more, not forever
    assert app.jobs.get(jid).status == "failed"


# ---------------------------------------------------------------------------------------------- 5: Profile sync, fresh
def test_profile_sync_on_a_fresh_install_says_what_to_do(app):
    m = app.modules["profile"]
    assert not m.notes_sync_set()
    f = m.setup_form()
    assert [x["name"] for x in f["fields"]] == ["repo", "token", "passphrase", "again"]
    assert "empty" not in " ".join(x["label"] for x in f["fields"][:2])  # nothing to leave empty without Notes sync
    assert len(f["steps"]) == 4 and "PRIVATE" in f["steps"][0] and "owner/name" in f["steps"][2]
    ok, why = app.enable("profile")
    assert not ok and "no repository" in why  # the card shows the form beside this
    p = "correct horse battery staple"
    r = m.configure({"repo": "", "token": "", "passphrase": p, "again": p})
    assert not r["ok"] and "fill in a private repository" in r["message"]
    r = m.configure({"repo": "someone/kurooto-profile", "token": "", "passphrase": p, "again": p})
    assert not r["ok"] and "token" in r["message"]


def test_profile_sync_with_notes_sync_set_up_keeps_its_short_form(app):
    app.settings.set("notes_sync.repo", "someone/notes")
    f = app.modules["profile"].setup_form()
    assert "steps" not in f and "empty: Notes sync's" in f["fields"][0]["label"]


# ---------------------------------------------------------------------------------------------- 6: graph tools
def test_the_concept_graph_has_read_only_tools(app):
    from kurooto.core.tools import agent_tools

    names = {"graph_status", "graph_search", "concept_card", "graph_links"}
    assert not names & {t.name for t in agent_tools(app)}  # off with the feature
    app.settings.set("modules.enabled", ["integrate"])
    app.settings.set("notes.layout", "zettelkasten")
    tools = {t.name: t for t in agent_tools(app)}
    assert names <= set(tools) and all(tools[n].writes is False for n in names)
    notes = app.workspace / "zettel"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "eigenvalue.md").write_text(
        "---\nid: zettel/eigenvalue\naliases: [eigenvalues]\n---\n# Eigenvalue\nA scalar with Av = lv. "
        "Needs [[zettel/matrix]].\n"
    )
    (notes / "matrix.md").write_text("# Matrix\nA grid of numbers. See [[zettel/eigenvalue]].\n")
    found = tools["graph_search"].run({"query": "eigenvalue"})
    assert "zettel/eigenvalue" in found
    assert "Eigenvalue" in tools["concept_card"].run({"slug": "zettel/eigenvalue"})
    links = tools["graph_links"].run({"slug": "zettel/matrix"})
    assert "Linked from:" in links and "zettel/eigenvalue" in links
    assert "No such concept" in tools["concept_card"].run({"slug": "nope"})
    assert "concepts" in tools["graph_status"].run({})
