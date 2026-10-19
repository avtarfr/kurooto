"""GBrain upkeep: the nightly light steps, timelines, the weekly checkup, /timeline and the note_timeline tool, and a
busy brain. Every test uses a fake gbrain; nothing here ever runs against a real brain."""

import json
import os
import sys
import threading

import pytest

from kurooto.core import proc
from kurooto.core.lock import Lock
from kurooto.core.tools import agent_tools, run_tool
from kurooto.modules.gbrain import BUSY, UPKEEP_STEPS, gbrain_slug

DREAM_OK = {"schema_version": "1", "status": "ok", "phases": [{"phase": p, "status": "ok"} for p in UPKEEP_STEPS]}


class FakeGBrain:
    """Stands in for proc.run: records each gbrain command and answers from a table (by subcommand)."""

    def __init__(self, answers=None):
        self.calls, self.answers = [], dict(answers or {})

    def __call__(self, args, **kw):
        self.calls.append((args[1:], kw.get("env", {})))
        ans = self.answers.get(args[1], (0, ""))
        return proc.Result(ans[0], ans[1], ans[2] if len(ans) > 2 else "")

    def cmds(self):
        return [c[0] for c in self.calls]


@pytest.fixture
def g(env, monkeypatch):
    g = env.app.modules["gbrain"]
    monkeypatch.setattr(g.prereqs.items["gbrain"], "find", lambda: "/x/gbrain")
    (env.app.paths.state / "gbrain.json").write_text(json.dumps({"initialised": True, "embeddings": "off"}))
    env.app.settings.set("notify.desktop", False)
    return g


def use(monkeypatch, fake):
    monkeypatch.setattr("kurooto.modules.gbrain.proc.run", fake)
    return fake


def messages(env):
    return [p for m, p in env.fake.sent if m == "sendMessage"]


def test_upkeep_runs_the_light_steps_only(env, g, monkeypatch):
    env.app.settings.set("gbrain.upkeep", True)
    fake = use(monkeypatch, FakeGBrain({"dream": (0, "starting\n" + json.dumps(DREAM_OK))}))
    out = g.nightly()
    assert out == {"upkeep": (True, "ok")}
    args, envv = fake.calls[0]
    steps = [args[i + 1] for i, a in enumerate(args) if a == "--phase"]
    assert args[:4] == ["dream", "--json", "--dir", str(env.app.workspace)]
    assert steps == list(UPKEEP_STEPS)
    for heavy in ("lint", "sync", "consolidate", "propose_takes", "synthesize", "edge_contradictions", "purge"):
        assert heavy not in steps  # never rewrites note files, never calls an AI model
    assert envv["GBRAIN_HOME"] == str(g.home)  # Kurooto's own brain, never ~/.gbrain
    assert len(fake.calls) == 1  # the upkeep's extract step makes the timelines; no separate run
    ev = env.app.events.tail(1, {"gbrain_upkeep"})[-1]
    assert ev["ok"] is True and ev["failed"] == []
    assert list((env.app.paths.state / "gbrain").glob("upkeep-*.log"))


def test_upkeep_failure_is_told_once_until_it_works_again(env, g, monkeypatch):
    env.app.settings.set("gbrain.upkeep", True)
    bad = {"status": "partial", "phases": [{"phase": "embed", "status": "fail"}, {"phase": "extract", "status": "ok"}]}
    use(monkeypatch, FakeGBrain({"dream": (1, json.dumps(bad))}))
    before = len(messages(env))
    assert g.upkeep() == (False, "partial")
    told = messages(env)[before:]
    assert len(told) == 1 and "nightly upkeep didn't finish (steps: embed)" in told[0]["text"]
    g.upkeep()
    assert len(messages(env)) == before + 1  # not every night
    use(monkeypatch, FakeGBrain({"dream": (0, json.dumps(DREAM_OK))}))
    assert g.upkeep() == (True, "ok")
    use(monkeypatch, FakeGBrain({"dream": (1, json.dumps(bad))}))
    g.upkeep()
    assert len(messages(env)) == before + 2  # broke again after working: told again


def test_timelines_run_nightly_without_the_upkeep(env, g, monkeypatch):
    fake = use(monkeypatch, FakeGBrain({"extract": (0, "Timeline: created 3 entries from 2 pages\n")}))
    assert g.nightly() == {"timelines": (True, 3)}
    assert fake.cmds() == [["extract", "timeline", "--source", "db"]]
    assert env.app.events.tail(1, {"gbrain_timelines"})[-1]["entries"] == 3
    env.app.settings.set("gbrain.timelines", False)
    fake.calls.clear()
    assert g.nightly() == {} and fake.calls == []
    (env.app.paths.state / "gbrain.json").write_text("{}")  # not set up yet: nothing runs
    env.app.settings.set("gbrain.upkeep", True)
    assert g.nightly() == {} and fake.calls == []


def test_checkup_messages_only_when_something_needs_a_look(env, g, monkeypatch):
    info = {"findings": [{"id": "orphan_pages", "severity": "info", "title": "3 orphan pages"}], "worst": "info"}
    fake = use(monkeypatch, FakeGBrain({"advisor": (0, json.dumps(info))}))
    assert g.checkup() == [] and fake.calls == []  # off by default
    env.on("gbrain")
    env.app.settings.set("gbrain.checkup", True)
    before = len(messages(env))
    assert g.checkup() == [] and fake.cmds() == [["advisor", "--json"]]
    assert len(messages(env)) == before
    warn = {
        "worst": "critical",
        "findings": [
            {"id": "low_embed_coverage", "severity": "warn", "title": "Only 40% of pages are indexed by meaning"},
            {"id": "pending_migration", "severity": "critical", "title": "A schema update is waiting"},
            {"id": "backup_workspace_no_repo", "severity": "warn", "title": "No git repo"},
            {"id": "uninstalled_bundled_skills", "severity": "warn", "title": "skills", "workspace_dependent": True},
        ],
    }
    use(monkeypatch, FakeGBrain({"advisor": (2, json.dumps(warn)), "apply-migrations": (0, "done")}))
    found = g.checkup()
    assert [f["id"] for f in found] == ["low_embed_coverage", "pending_migration"]
    msg = messages(env)[-1]
    assert "Notes brain checkup: 2 thing(s) need a look." in msg["text"]
    assert "- A schema update is waiting (serious)" in msg["text"] and "No git repo" not in msg["text"]
    row = msg["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in row] == ["Update the brain", "Ignore these"]
    assert env.press(row[0]["callback_data"]) == "Updated."
    assert env.press(row[1]["callback_data"]) == "OK, the checkup won't mention those again."
    assert "low_embed_coverage" in env.app.settings.get("gbrain.checkup_ignore")
    n = len(messages(env))
    assert g.checkup() == [] and len(messages(env)) == n


def test_checkup_reads_an_older_text_report(env, g, monkeypatch):
    env.app.settings.set("gbrain.checkup", True)
    use(monkeypatch, FakeGBrain({"advisor": (1, "[OK] version\n[WARN] embeddings stale: run gbrain embed\n")}))
    assert [f["title"] for f in g.checkup()] == ["[WARN] embeddings stale: run gbrain embed"]


def test_timeline_command_and_tool(env, g, monkeypatch):
    out = "2026-10-01  Started the reading group [log]\n2026-10-08  Second session [log]\n"
    fake = use(monkeypatch, FakeGBrain({"timeline": (0, out)}))
    env.on("gbrain")
    assert env.say("/timeline Research/Reading Group.md") == out.strip()
    assert fake.cmds()[-1] == ["timeline", "research/reading-group"]
    assert "note_timeline" in [t.name for t in agent_tools(env.app)]
    run_tool(env.app, "note_timeline", {"slug": "research/reading-group", "since": "2026-10-05"})
    assert fake.cmds()[-1] == ["timeline", "research/reading-group", "--after", "2026-10-05"]
    run_tool(env.app, "note_timeline", {"slug": "research/reading-group", "since": "last week"})
    assert fake.cmds()[-1] == ["timeline", "research/reading-group"]  # not a date: ignored
    use(monkeypatch, FakeGBrain({"timeline": (0, "No timeline entries.\n")}))
    assert env.say("/timeline inbox/idea").startswith("No dated entries for inbox/idea yet.")
    assert env.say("/timeline").startswith("Which note?")
    keys = [j.key for j in env.app.scheduler.jobs("gbrain:")]
    assert {"gbrain:sync", "gbrain:nightly", "gbrain:checkup"} <= set(keys)


def test_a_busy_brain_is_skipped_not_waited_for(env, g, monkeypatch):
    fake = use(monkeypatch, FakeGBrain())
    held, release = threading.Event(), threading.Event()

    def hold():
        with Lock(env.app.paths.state, "gbrain"):
            held.set()
            release.wait(10)

    t = threading.Thread(target=hold)
    t.start()
    try:
        held.wait(5)
        ok, why = g.sync({"wait": 0})
        assert not ok and "busy" in why
        assert g.run("advisor", wait=0).code == BUSY
        assert fake.calls == []
    finally:
        release.set()
        t.join()
    assert g.sync({"wait": 0})[0] is True
    monkeypatch.setattr(g, "run", lambda *a, **k: proc.Result(BUSY, "", "busy"))
    env.on("gbrain")
    assert env.say("/notes compactness").startswith("The notes brain is busy")
    assert env.say("/timeline topology/compactness").startswith("The notes brain is busy")


def test_gbrain_slug():
    assert gbrain_slug("Research/Reading Group.md") == "research/reading-group"
    assert gbrain_slug("journal\\2026-10-19.md") == "journal/2026-10-19"
    assert gbrain_slug("Café  Notes/v1.0.0") == "cafe-notes/v1.0.0"
    assert gbrain_slug("../x/../y") == "x/y" and gbrain_slug("") == ""


@pytest.mark.skipif(os.name == "nt", reason="a shell-free fake executable needs a POSIX shebang")
def test_with_a_fake_gbrain_program(env, g, monkeypatch, tmp_path):
    """The real proc.run with a fake gbrain program: the arguments and the brain folder it gets."""
    rec = tmp_path / "calls.jsonl"
    exe = tmp_path / "bin" / "gbrain"
    exe.parent.mkdir()
    exe.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        f"open({str(rec)!r}, 'a').write(json.dumps([sys.argv[1:], os.environ.get('GBRAIN_HOME')]) + '\\n')\n"
        f"print(json.dumps({DREAM_OK!r}))\n"
    )
    exe.chmod(0o755)
    monkeypatch.setattr(g.prereqs.items["gbrain"], "find", lambda: str(exe))
    assert g.upkeep() == (True, "ok")
    args, home = json.loads(rec.read_text().splitlines()[0])
    assert args[0] == "dream" and home == str(g.home) and str(g.home).startswith(str(env.app.paths.data))
