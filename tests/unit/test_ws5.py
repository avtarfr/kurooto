"""ws5: the flags scripts use (notify, call, sync), /status and /usage, the doctor's live checks, an add-on's intent
classifier, and skills exported to agent programs."""

import datetime as dt
import json
import time
from pathlib import Path

import pytest

from kurooto import cli
from kurooto.core import agent_export, overlay, syncall
from kurooto.modules.base import Module
from kurooto.web import tools_api
from kurooto.web.api import Api


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake home folder: agy's and the agents' skills folders and agy's logs live in it, never the real one."""
    h = tmp_path / "fakehome"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    assert Path.home() == h
    return h


def add_on(app, cls):
    """Load a feature the way core/overlay.py loads an add-on (guarded), and turn it on."""
    inst = cls(app)
    overlay.guard(app, inst)
    app.modules[inst.id] = inst
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), inst.id])
    return inst


# ============================================================================================ notify for scripts
def test_notify_with_buttons_a_link_and_a_reply(env):
    api = Api(env.app)
    code, r = api.post(
        "notify",
        {
            "text": "Run finished.",
            "kind": "question",
            "buttons": [["Rerun", "runs:42:again"], ["Logs", "https://example.org/run/42"]],
            "click": "https://example.org/run/42/plot",
        },
    )
    assert code == 200 and r["ok"] and isinstance(r["id"], int)
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    rows = sent["reply_markup"]["inline_keyboard"]
    assert rows[0] == [{"text": "Rerun", "callback_data": "runs:42:again"}]
    assert rows[1] == [{"text": "Logs", "url": "https://example.org/run/42"}]
    assert rows[2] == [{"text": "Open", "url": "https://example.org/run/42/plot"}]
    code, r2 = api.post("notify", {"text": "and the plot", "reply_to": r["id"]})
    assert code == 200
    assert [p for m, p in env.fake.sent if m == "sendMessage"][-1]["reply_parameters"]["message_id"] == r["id"]
    assert api.post("notify", {"text": "x", "buttons": [["Big", "x" * 65]]})[0] == 400
    assert api.post("notify", {"text": "x", "click": "file:///etc/passwd"})[0] == 400
    assert api.post("notify", {"text": "x", "buttons": [["", "a:b:c"]]})[0] == 400


def test_notify_cli_passes_the_flags(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: seen.append((path, body)) or {"ok": True, "id": 77})
    argv = ["notify", "--kind", "approval", "--button", "Yes=job:1:yes", "--button", "No=job:1:no"]
    argv += ["--click", "https://example.org", "--reply-to", "12", "--print-id", "done", "now"]
    assert cli.main(argv) == 0
    path, body = seen[-1]
    assert path == "notify" and body["text"] == "done now" and body["kind"] == "approval"
    assert body["buttons"] == [["Yes", "job:1:yes"], ["No", "job:1:no"]] and body["reply_to"] == 12
    assert body["click"] == "https://example.org" and capsys.readouterr().out.strip() == "77"
    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: {"error": "at most 8 buttons"})
    assert cli.main(["notify", "x"]) == 1 and "8 buttons" in capsys.readouterr().err


# ============================================================================================ calls from a shell
def test_call_list_and_cancel(env, monkeypatch, capsys):
    app = env.app
    app.scheduler.at(time.time() + 3600, "calls.ring", {"reason": "stretch", "key": "abc123"}, key="calls:ring:abc123")
    app.scheduler.at(time.time() + 7200, "calls.ring", {"reason": "up", "alarm": True}, key="calls:ring:wake")
    calls = tools_api.post(app, "call/list", {})[1]["calls"]
    assert [c["key"] for c in calls] == ["abc123", "wake"] and calls[1]["alarm"] and calls[0]["reason"] == "stretch"
    assert tools_api.post(app, "call/cancel", {"key": "nope"})[1]["ok"] is False
    assert tools_api.post(app, "call/cancel", {"key": "abc123"})[1] == {
        "ok": True,
        "message": "Cancelled the call abc123.",
    }
    assert app.scheduler.get("calls:ring:abc123") is None and app.scheduler.get("calls:ring:wake")

    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: tools_api.post(app, path, body or {})[1])
    assert cli.main(["call", "--list"]) == 0
    out = capsys.readouterr().out
    assert "wake" in out and "(alarm) up" in out and "--cancel KEY" in out
    assert cli.main(["call", "--cancel", "wake"]) == 0 and "Cancelled" in capsys.readouterr().out
    assert cli.main(["call", "--list"]) == 0 and "No calls booked" in capsys.readouterr().out
    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: None)
    assert cli.main(["call", "--list"]) == 1


# ============================================================================================ sync everything
def test_sync_everything_ends_with_a_backup(env, tmp_path, monkeypatch):
    app = env.app
    app.settings.set("backups.folder", str(tmp_path / "drive"))
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "calendar", "backups"])
    monkeypatch.setattr(app.modules["calendar"], "refresh", lambda p=None: 2)
    made = []
    monkeypatch.setattr(app.modules["backups"], "backup", lambda reason="now": made.append(reason) or (True, "1 MB"))
    assert syncall.run(app) == [
        ("Calendar", True, "2 events"),
        ("Backup", None, f"the backup folder isn't there ({tmp_path / 'drive'}); is the drive plugged in?"),
    ]
    (tmp_path / "drive").mkdir()
    assert syncall.run(app)[-1] == ("Backup", True, "1 MB") and made == ["sync"]


def test_sync_status_and_no_wait(env, monkeypatch, capsys):
    from kurooto.core.state import jsave

    app = env.app
    assert cli.main(["sync", "--status"]) == 0 and "No sync has run yet" in capsys.readouterr().out
    jsave(app.paths.state / "sync-all.json", {"running": False, "finished": time.time(), "text": "Synced: Calendar ok"})
    assert cli.main(["sync", "--status"]) == 0 and "Synced: Calendar ok" in capsys.readouterr().out
    jsave(app.paths.state / "sync-all.json", {"running": True, "started": time.time()})
    monkeypatch.setattr(cli, "wait_for_web", lambda seconds=40: None)
    assert cli.main(["sync", "--status"]) == 0 and "Running since" in capsys.readouterr().out
    seen = []
    monkeypatch.setattr(
        cli, "ask_running", lambda path, body=None: seen.append(body) or {"ok": True, "message": "Syncing."}
    )
    assert cli.main(["sync", "--no-wait"]) == 0 and seen == [{"notify": True}]
    assert "in the background" in capsys.readouterr().out


# ============================================================================================ /status, /usage
def test_status_has_due_alarm_checkins_jobs_and_add_on_lines(env, monkeypatch):
    app = env.app
    env.on("deadlines", "checkins")
    app.modules["deadlines"].add("essay draft", dt.datetime.now() + dt.timedelta(hours=20))
    monkeypatch.setattr(
        app.modules["checkins"], "today", lambda day=None: {"evening": {"time": "21:30", "status": "planned"}}
    )
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "alarm"])
    monkeypatch.setattr(app.modules["alarm"], "next", lambda: dt.datetime(2026, 10, 21, 7, 0))
    app.jobs.submit("summarise my week", title="Weekly summary")

    class Local(Module):
        id = "local_brain"
        title = "Local brain"

        def status_lines(self):
            return ["Local model: answering"]

    add_on(app, Local)
    text = env.say("/status")
    assert "Due in the next 3 days:\n  essay draft (" in text
    assert "Check-ins today: evening 21:30 (planned)" in text
    assert "Alarm: Wed 07:00" in text
    assert "Recent AI requests (/jobs):" in text and "Weekly summary" in text
    assert "Local model: answering" in text and text.rstrip().splitlines()[-1].startswith("On: ")

    class Broken(Module):
        id = "broken_status"
        title = "Broken"

        def status_lines(self):
            raise RuntimeError("boom")

    add_on(app, Broken)
    assert "Alarm: Wed 07:00" in env.say("/status")  # a failing add-on line never spoils /status


def test_usage_counts_agys_own_runs_from_its_logs(env, home, capsys):
    from kurooto.providers import agy

    log = home / ".gemini" / "antigravity-cli" / "log"
    log.mkdir(parents=True)
    today = dt.date.today()
    (log / f"cli-{today:%Y%m%d}_101010.log").write_text("streamGenerateContent\n" * 3)
    (log / f"cli-{today:%Y%m%d}_111111.log").write_text("streamGenerateContent\nRESOURCE_EXHAUSTED\n")
    old = today - dt.timedelta(days=30)
    (log / f"cli-{old:%Y%m%d}_090000.log").write_text("streamGenerateContent\n" * 50)
    rows = agy.log_usage(7)
    assert rows[-1] == {"day": today.isoformat(), "runs": 2, "requests": 4, "limited": 1}
    assert sum(r["requests"] for r in rows) == 4
    env.app.settings.set("modules.enabled", [*env.app.settings.get("modules.enabled"), "chat"])
    text = env.say("/usage")
    assert "agy itself" in text and "2 runs, 4 model requests, limit hit 1" in text
    assert "7-day total: 4 model requests, 2 runs." in text
    assert tools_api.get(env.app, "usage", {"days": "7"})[1]["agy"][-1]["runs"] == 2
    assert cli.main(["usage", "3"]) == 0 and "agy itself" in capsys.readouterr().out


def test_usage_without_agy_logs_says_nothing_about_agy(env, home):
    from kurooto.providers import agy

    assert agy.log_usage(7) == [] and agy.log_usage_text([]) == ""
    env.app.settings.set("modules.enabled", [*env.app.settings.get("modules.enabled"), "chat"])
    assert "agy itself" not in env.say("/usage")


# ============================================================================================ intent classifier
class Picker(Module):
    """A stand-in for a local model: answers from a table, can be slow or broken."""

    id = "picker"
    title = "Picker"
    answers: dict = {}
    delay = 0.0
    seen: list = []

    def classify_intent(self, text, intents):
        type(self).seen.append((text, [i["name"] for i in intents]))
        if self.delay:
            time.sleep(self.delay)
        got = type(self).answers.get(text)
        if isinstance(got, Exception):
            raise got
        return got


def classified(env) -> list[str]:
    return [e["name"] for e in env.app.events.tail(200) if e["kind"] == "intent" and e.get("via") == "classifier"]


@pytest.fixture
def picker(env):
    Picker.answers, Picker.delay, Picker.seen = {}, 0.0, []
    add_on(env.app, Picker)
    return Picker


def test_classifier_goes_first_with_its_own_slots(env, picker):
    picker.answers["leave me alone till the evening"] = {
        "intent": "hold_calls",
        "slots": {"until": "20:00"},
        "confidence": 0.9,
    }
    out = env.say("leave me alone till the evening")  # no built-in pattern knows this phrasing
    assert out.startswith("No calls until") and "20:00" in out
    assert env.app.availability.call_block()[0]
    assert classified(env) == ["hold_calls"]
    assert "hold_calls" in picker.seen[-1][1]


def test_classifier_without_slots_uses_the_requests_own_pattern(env, picker):
    picker.answers["no calls for 2 hours"] = "hold_calls"
    assert env.say("no calls for 2 hours").startswith("No calls until")
    picker.answers["calls hush"] = "hold_calls"  # its pattern can't fill the time: on to the usual route
    assert not env.say("calls hush").startswith("No calls until")


def test_classifier_falls_through(env, picker):
    unsure = "no calls for 1 hour"
    picker.answers[unsure] = {"intent": "hold_calls", "slots": {"until": "23:00"}, "confidence": 0.3}
    assert env.say(unsure).startswith("No calls until") and classified(env) == []  # unsure: the built-in answered
    picker.answers["no calls for 3 hours"] = RuntimeError("model down")
    assert env.say("no calls for 3 hours").startswith("No calls until")
    assert any("picker" in e["where"] for e in overlay.status(env.app)["errors"])
    picker.answers["no calls for 4 hours"] = {"intent": "made_up"}
    assert env.say("no calls for 4 hours").startswith("No calls until")
    picker.delay = 0.3
    Picker.classify_timeout = 0.05
    try:
        picker.answers["lalala"] = {"intent": "hold_calls", "slots": {"until": "20:00"}}
        assert "No calls" not in (env.say("lalala") or "")  # too slow: never used
        assert any(e["kind"] == "classifier_slow" for e in env.app.events.tail(30)) and classified(env) == []
    finally:
        del Picker.classify_timeout


def test_classifier_never_sees_long_or_several_requests_and_questions_only_go_to_question_intents(env, picker):
    env.on("deadlines")
    env.say("remind me at 9 to stretch and also call me at 10 and then hold all calls till 6")
    assert not picker.seen
    env.say("is anything due tomorrow?")
    offered = picker.seen[-1][1]
    assert "show_due" in offered and "hold_calls" not in offered and "add_deadline" not in offered
    env.say("no calls for 2 hours")
    assert {"hold_calls", "add_deadline", "show_due"} <= set(picker.seen[-1][1])


# ============================================================================================ doctor
def test_doctor_asks_telegram_and_add_ons(env):
    from kurooto import diagnostics

    class Disk(Module):
        id = "disk_watch"
        title = "Disk"

        def doctor_checks(self):
            return [("backup drive", False, "not mounted"), ("free space", True, "40 GB")]

    add_on(env.app, Disk)
    rows = {n: (ok, d) for n, ok, d in diagnostics.checks(env.app)}
    assert rows["Telegram bot"][0] is True and "answers" in rows["Telegram bot"][1]
    assert rows["Disk: backup drive"] == (False, "not mounted") and rows["Disk: free space"][0] is True
    env.app.secrets.set("telegram.token", "123456:" + "B" * 35)  # a token Telegram doesn't know
    rows = {n: (ok, d) for n, ok, d in diagnostics.checks(env.app)}
    assert rows["Telegram bot"][0] is False and "didn't answer" in rows["Telegram bot"][1]


def test_doctor_judges_the_call_line_from_the_running_kurooto(env, monkeypatch):
    from kurooto import diagnostics
    from kurooto.core.state import jsave
    from kurooto.modules.calls import deploy

    calls = env.app.modules["calls"]
    monkeypatch.setattr(calls, "ready", lambda: (True, ""))
    monkeypatch.setattr(calls, "worker_url", lambda: "https://line.example.org")
    monkeypatch.setattr(deploy, "health", lambda url, timeout=10: None)
    assert diagnostics.call_line(env.app, calls, True)[0] is False
    monkeypatch.setattr(deploy, "health", lambda url, timeout=10: {"ok": True})
    assert diagnostics.call_line(env.app, calls, False)[0] is None
    jsave(env.app.paths.state / "calls" / "link.json", {"connected": True})
    assert diagnostics.call_line(env.app, calls, True) == (
        True,
        "your call line answers, and this computer is linked to it",
    )
    jsave(env.app.paths.state / "calls" / "link.json", {"connected": False, "error": "401"})
    ok, why = diagnostics.call_line(env.app, calls, True)
    assert ok is False and "(401)" in why


# ============================================================================================ skills in agents
def test_skills_export_to_agy_and_back(env, home):
    app = env.app
    agy_dir = home / ".gemini" / "antigravity-cli" / "skills"
    (agy_dir / "journal").mkdir(parents=True)
    (agy_dir / "journal" / "SKILL.md").write_text("---\nname: journal\ndescription: mine\n---\nMy own journal.\n")
    (app.workspace / "prompts").mkdir()
    (app.workspace / "prompts" / "tighten.md").write_text(
        "---\nskill: tighten\ndescription: Tighten prose\n---\nTighten $ARGUMENTS\n"
    )
    assert agent_export.sync(app)["targets"] == []  # off until you turn it on
    assert not (agy_dir / "goodnight").exists()

    app.settings.set("agents.export", ["agy"])
    rep = agent_export.sync(app)
    assert "agy: goodnight" in rep["written"] and "agy: tighten" in rep["written"]
    assert not (agy_dir / "retro").exists()  # internal skills stay inside Kurooto
    text = (agy_dir / "goodnight" / "SKILL.md").read_text()
    assert text.startswith('---\nname: goodnight\ndescription: "Kurooto: ')
    assert str(app.workspace) in text and "$ARGUMENTS" in text and "Never delete" in text
    assert (agy_dir / "journal" / "SKILL.md").read_text().endswith("My own journal.\n")  # yours: untouched
    assert (agy_dir / "kurooto-journal" / "SKILL.md").read_text().startswith("---\nname: kurooto-journal\n")
    assert any("kurooto-journal" in r for r in rep["renamed"])

    again = agent_export.sync(app)
    assert again["written"] == [] and again["same"] == len(rep["written"])
    (agy_dir / "goodnight" / "SKILL.md").write_text("my edited goodnight\n")
    (app.workspace / "prompts" / "tighten.md").unlink()
    rep = agent_export.sync(app)
    assert "agy: tighten" in rep["removed"] and not (agy_dir / "tighten").exists()
    assert "agy: goodnight" in rep["edited"]
    assert (agy_dir / "goodnight" / "SKILL.md").read_text() == "my edited goodnight\n"

    app.settings.set("agents.export", [])
    rep = agent_export.sync(app)
    assert not (agy_dir / "kurooto-journal").exists() and not (agy_dir / "connect-notes").exists()
    assert (agy_dir / "journal" / "SKILL.md").exists()
    assert (agy_dir / "goodnight" / "SKILL.md").read_text() == "my edited goodnight\n"  # you edited it: yours
    assert not (agy_dir / "goodnight" / agent_export.MARK).exists()
    assert agent_export.sync(app)["removed"] == []


def test_export_skills_cli_prefix_agents_and_uninstall(env, home, capsys):
    app = env.app
    assert cli.main(["export-skills"]) == 0 and "Off." in capsys.readouterr().out
    assert cli.main(["export-skills", "on", "--to", "agy,agents"]) == 0
    assert "written or updated" in capsys.readouterr().out
    agents_dir = home / ".agents" / "skills"
    assert (agents_dir / "study-log" / "SKILL.md").exists()
    assert cli.main(["export-skills", "status"]) == 0
    out = capsys.readouterr().out
    assert "/study-log" in out and "Copilot CLI and other agents" in out
    app.settings.set("agents.prefix", "k-")
    agent_export.sync(app)
    assert (agents_dir / "k-study-log").exists() and not (agents_dir / "study-log").exists()
    assert cli.main(["export-skills", "on", "--to", "nowhere"]) == 2  # unknown places are refused
    assert not (home / ".claude").exists()  # Claude Code's folder only when asked for
    (agents_dir / "k-study-log" / "notes.txt").write_text("mine")  # something you put in one of its folders
    gone = agent_export.remove_all(app.paths.state, app.paths.config)
    assert gone and not (agents_dir / "k-journal").exists()
    assert (agents_dir / "k-study-log" / "notes.txt").read_text() == "mine"
    assert not (agents_dir / "k-study-log" / "SKILL.md").exists()
    assert agent_export.remove_all(app.paths.state, app.paths.config) == []


def test_doctor_line_and_the_hourly_update_only_while_on(env, home):
    from kurooto import diagnostics

    app = env.app
    assert agent_export.doctor_check(app) is None
    app.settings.set("agents.export", ["agy"])
    assert agent_export.doctor_check(app)[1] is None  # not yet
    agent_export.sync(app)
    name, ok, detail = agent_export.doctor_check(app)
    assert ok is True and "copies in agy" in detail
    assert any(n == "skills in agents" for n, _, _ in diagnostics.checks(app))
    assert app.scheduler.get("agents:export").payload == {"what": "skills into agent programs"}
    agent_export.start(app)
    app.settings.set("agents.export", [])
    agent_export.sync(app)
    assert app.scheduler.get("agents:export") is None and not (app.paths.state / agent_export.STATE).exists()


def test_uninstall_without_exports_touches_no_agent_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    state = tmp_path / "state"
    state.mkdir()
    assert agent_export.remove_all(state, tmp_path / "config") == []  # nothing recorded: nothing scanned


# ============================================================================================ ask-me for scripts
def test_ask_me_pending_and_waiting_on_an_earlier_question(env, monkeypatch, capsys):
    app = env.app
    api = Api(app)

    def running(path, body=None):
        code, r = api.post(path, body or {})
        return r if code == 200 else None

    monkeypatch.setattr(cli, "ask_running", running)
    qid = app.ask.ask("Which room?", choices=["A", "B"])
    assert cli.main(["ask-me", "--pending"]) == 0
    assert f"{qid}  Which room?  [A | B]" in capsys.readouterr().out
    assert cli.main(["ask-me", "--pending", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["id"] == qid
    assert cli.main(["ask-me", "--id", qid]) == 0 and capsys.readouterr().out.startswith("open")
    app.ask.answer(qid, "B", "test")
    assert cli.main(["ask-me", "--id", qid, "--wait", "--timeout", "0.05"]) == 0
    assert capsys.readouterr().out.strip() == "B"
    assert cli.main(["ask-me", "--pending"]) == 0 and "No open questions." in capsys.readouterr().out
    assert cli.main(["ask-me", "--id", "nope"]) == 2
