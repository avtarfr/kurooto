"""The last parity gaps before 0.4.0: any header row in the recurring table, quiz requests that ring with
quiz.by_call, the term note read live (timetable, holidays, exam periods, term end, key dates as deadlines), the
notes map's open command, `kurooto ask-me --then`, and the Telegram "/" menu."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time

import pytest

from kurooto.core import opener
from kurooto.core.clock import now
from kurooto.modules import recurring, termnote
from tests.unit.test_skills import ai  # noqa: F401 (a fixture)
from tests.unit.test_study import calls, calls_for, last_buttons, study, write_prep  # noqa: F401 (fixtures too)


# ------------------------------------------------------------------------------- recurring headers
def test_a_course_headed_recurring_table_has_no_stray_row(study):  # noqa: F811
    text = (
        "# Recurring assessments\n\n| Course | What | Every | Day | Time | Next | Until |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| la | Quiz | 1 | Thu | 10:00 | | |\n\n"
        "| Paper | Kind |\n| topology | Test |\n\n| Thing | Type | Weeks |\n|---|---|---|\n| stats | Test | 2 |\n"
    )
    rows = recurring.parse(text)
    assert [(r["subject"], r["what"], r["every"]) for r in rows] == [
        ("la", "Quiz", 1),
        ("topology", "Test", 1),
        ("stats", "Test", 2),
    ]
    added = recurring.insert(text, "| topology | Quiz | 1 | Fri | | | |")
    assert added.split("\n")[5] == "| topology | Quiz | 1 | Fri | | | |"  # at the end of the first table
    f = recurring.note_file(study.app)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text.split("\n\n| Paper")[0] + "\n", encoding="utf-8")
    dl = study.app.modules["deadlines"]
    dl.scan_recurring()
    assert study.app.ask.pending() == []  # the header isn't a rule with an unknown day
    assert any(it["title"] == "Linear Algebra: Quiz" for it in dl.items().values())


# ------------------------------------------------------------------------------------ quiz by call
def test_quiz_by_call_rings_for_slash_quiz_and_quiz_me(calls):  # noqa: F811
    app = calls.app
    calls.on("quiz")
    write_prep(app, "topology", 2)
    write_prep(app)
    app.settings.set("quiz.by_call", True)
    calls.say("/quiz topology")
    assert calls_for(app, "quiz:topology")
    assert calls.say("/quiz topology here") == "2 due in topology."  # "here" keeps it on Telegram
    calls.say("quiz me on linear algebra")
    assert calls_for(app, "quiz:linear-algebra")
    app.settings.set("quiz.by_call", False)  # as before: it asks
    calls.say("/quiz topology")
    assert [b["text"] for b in last_buttons(calls)] == ["Here", "By call"]


def test_quiz_by_call_without_phone_calls_texts(study):  # noqa: F811
    study.on("quiz")
    write_prep(study.app, "topology", 2)
    study.app.settings.set("quiz.by_call", True)
    assert study.say("/quiz topology") == "2 due in topology."
    assert study.say("quiz me on topology").startswith("2 due in topology.")


# ------------------------------------------------------------------------------------- term note
def d(n: int) -> str:
    return (now().date() + dt.timedelta(days=n)).isoformat()


def term_text(extra_dates: str = "", extra_classes: str = "") -> str:
    today = now().strftime("%A")
    return f"""# Autumn term

Some words of mine.

## Weekly timetable
| Day | Time | Subject | Code |
| :--- | :--- | :--- | :--- |
| **{today}** | 09:00-09:55 | [[linear-algebra/course\\|Linear Algebra]] | `MA101` |
| | 11:00–11:55 | [[statistics/course|Statistics]] | ST200 |
| | 12:00-13:00 | Lunch | |
| Tue, Thu | 2:00–2:50 pm | Topology | |
{extra_classes}
## Key dates
| Date | What | Source |
| :--- | :--- | :--- |
| {d(1)} | Holiday (Founders' day) | calendar |
| {d(3)} – {d(4)} | Mid-term break | calendar |
| {d(5)} | MA101 Quiz 2 (10:00-10:50, room 4) | me |
| {d(6)} | Statistics project due | me |
| {d(7)} | Last date for grade submission | calendar |
| {d(9)} | Last day of classes | calendar |
| {d(12)} to {d(20)} | End-term examinations | calendar |
| {d(25)} | Results | calendar |
{extra_dates}
## Subjects
- [[linear-algebra/course]]
"""


def test_term_note_format():
    t = termnote.parse(term_text())
    assert [(c["day"], c["start"], c["end"], c["slug"]) for c in t["classes"]][1:] == [
        (now().strftime("%a").lower(), "11:00", "11:55", "statistics"),
        ("tue", "14:00", "14:50", "topology"),
        ("thu", "14:00", "14:50", "topology"),
    ]
    assert t["subjects"][0] == {"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["ma101"]}
    assert t["holidays"] == [d(1), d(3), d(4)] and t["exam_periods"] == [[d(12), d(20)]] and t["term_ends"] == d(9)
    kinds = {x["what"]: (x["kind"], x["time"]) for x in t["dates"]}
    assert kinds["MA101 Quiz 2"] == ("exam", "10:00") and kinds["Statistics project due"] == ("due", "")
    assert kinds["Results"] == ("date", "") and kinds["Holiday"] == ("holiday", "")
    assert termnote.span("11:00-12:30 pm") == ("11:00", "12:30") and termnote.time_in("due 5 pm") == "17:00"
    assert termnote.time_in("Quiz (9:00–9:50 am, room 1)") == "09:00"
    k = termnote.parse("## Key dates\n| When | Event | Kind |\n|---|---|---|\n| 2026-11-02 | Essay | due |\n")
    assert k["dates"][0]["kind"] == "due" and k["dates"][0]["explicit"]
    z = termnote.parse(
        "## Weekly timetable\n| Day | Time | Course | Code | Room |\n| :--- | :--- | :--- | :--- | :--- |\n"
        "| **Mon** | 09:00–09:55 | [[maps/courses/number-theory\\|Number Theory]] | `NT201` | L1 |\n"
        "| | 10:00–10:55 | Lab | | |\n"
    )
    assert [(c["slug"], c["name"], c["code"]) for c in z["classes"]] == [
        ("number-theory", "Number Theory", "NT201"),
        ("lab", "Lab", ""),
    ]


def test_term_note_read_live(study):  # noqa: F811
    app, sub, dl = study.app, study.app.modules["subjects"], study.app.modules["deadlines"]
    f = app.workspace / "terms" / "autumn.md"
    f.parent.mkdir(parents=True)
    f.write_text(term_text(), encoding="utf-8")
    (app.workspace / "linear-algebra").mkdir()
    (app.workspace / "linear-algebra" / "course.md").write_text(
        f"# Linear Algebra\n## Tasks\n- [ ] Linear Algebra quiz 2 ({d(5)} 10:00)\n", encoding="utf-8"
    )
    assert "I can't find" in study.say("/term note terms/spring")
    out = study.say("/term note terms/autumn")
    assert "4 classes, 3 holidays, 1 exam period, 8 key dates" in out and "whenever it changes" in out
    assert sub.resolve("ma101") == "linear-algebra" and sub.resolve("statistics") == "statistics"
    topology = ["topology"] if now().weekday() in (1, 3) else []  # its classes are on Tuesdays and Thursdays
    assert [c["subject"] for c in sub.classes_on()] == ["linear-algebra", "statistics", *topology]
    assert sub.no_classes(now().date() + dt.timedelta(days=1)) == "holiday"
    assert sub.no_classes(now().date() + dt.timedelta(days=4)) == "holiday"
    assert sub.no_classes(now().date() + dt.timedelta(days=10)) == "term over"
    assert sub.no_classes(now().date() + dt.timedelta(days=13)) == "exams"
    assert "Last day of classes: " + d(9) in study.say("/term")
    dl.refresh()  # the hourly pass: the notes' own task joins the note's key date
    items = {it["title"]: it for it in dl.items().values() if it["status"] == "open"}
    quiz = items["MA101 Quiz 2"] if "MA101 Quiz 2" in items else items["Linear Algebra quiz 2"]
    assert quiz["due"] == f"{d(5)}T10:00:00" and quiz["kind"] == "exam" and quiz["subject"] == "linear-algebra"
    assert sorted(quiz["sources"]) == ["notes:linear-algebra/course.md", "term-note"]  # kept once
    assert items["Statistics project due"]["kind"] == "task" and items["Statistics project due"]["subject"]
    assert not {"Last date for grade submission", "Results", "End-term examinations"} & set(items)
    # you edit the note: a row goes, a class comes; Kurooto follows without being told
    text = term_text(extra_classes="| Sat, Sun | 07:00-07:30 | Topology | |\n").replace(
        f"| {d(6)} | Statistics project due | me |\n", ""
    )
    f.write_text(text, encoding="utf-8")
    later = time.time() + 5
    os.utime(f, (later, later))
    assert ("sat", "07:00") in {(c["day"], c["start"]) for c in sub.timetable()}
    assert sub._term_watch() is True and sub._term_watch() is False
    gone = [it for it in dl.items().values() if it["title"] == "Statistics project due"]
    assert gone[0]["status"] == "gone"
    # your own settings still win
    app.settings.set("subjects.term_ends", d(2))
    assert sub.term_ends() == d(2)
    out = study.say("/term note off")
    assert out.startswith("Term note off") and sub.timetable() == []
    assert all(it["status"] != "open" for it in dl.items().values() if it.get("sources") == ["term-note"])


def test_term_note_auto_in_the_zettelkasten_layout(study):  # noqa: F811
    app, sub = study.app, study.app.modules["subjects"]
    app.settings.set("notes.layout", "zettelkasten")
    maps = app.workspace / "maps"
    maps.mkdir()
    old = "## Key dates\n| Date | What |\n|---|---|\n| 2020-01-06 | Quiz 1 |\n| 2020-04-30 | Last day of classes |\n"
    (maps / "semester-9.md").write_text(old, encoding="utf-8")
    (maps / "semester-10.md").write_text(old.replace("2020", "2021"), encoding="utf-8")
    app.settings.set("subjects.term_note", "auto")
    assert sub.term_path().name == "semester-10.md"  # neither is current: the newest name (10 after 9)
    (maps / "semester-3.md").write_text(term_text(), encoding="utf-8")  # this one covers today
    sub._glob_cache = None
    assert sub.term_path().name == "semester-3.md" and sub.health() == (True, "")
    app.settings.set("subjects.term_note", "maps/semester-99")
    assert sub.health()[0] is False and sub.term()["classes"] == []


# ----------------------------------------------------------------------------------- open a note
def test_open_with_command(monkeypatch, tmp_path):
    note = tmp_path / "my notes" / "a b.md"
    assert opener.argv_for("kitty nvim {path}", note) == ["kitty", "nvim", str(note)]
    assert opener.argv_for("code --new-window", note) == ["code", "--new-window", str(note)]
    assert opener.argv_for("ed {folder}/x {path}", note, "/n") == ["ed", "/n/x", str(note)]
    assert opener.argv_for("'unclosed", note) == [] and opener.argv_for("", note) == []
    started: list = []
    monkeypatch.setattr(opener, "spawn", lambda argv: started.append(argv))
    monkeypatch.setattr(opener, "which", lambda name: f"/bin/{name}" if name == "kitty" else None)
    monkeypatch.setattr(opener, "open_default", lambda p: started.append(["default", str(p)]) or True)
    assert opener.open_note({"notes.open_with": "kitty nvim {path}"}, note) == (True, "")
    assert started[-1] == ["/bin/kitty", "nvim", str(note)]
    ok, why = opener.open_note({"notes.open_with": "nope {path}"}, note)
    assert ok and "isn't on this computer" in why and started[-1] == ["default", str(note)]
    assert opener.open_note({}, note) == (True, "") and started[-1][0] == "default"


def test_dashboard_opens_notes_with_the_setting(env, monkeypatch):
    from kurooto.web.api import Api

    (env.app.workspace / "inbox").mkdir(parents=True, exist_ok=True)
    (env.app.workspace / "inbox" / "idea.md").write_text("# Idea\n", encoding="utf-8")
    seen: list = []
    monkeypatch.setattr(opener, "spawn", lambda argv: seen.append(argv))
    monkeypatch.setattr(opener, "which", lambda name: sys.executable)
    api = Api(env.app)
    assert any("open_with" in s["values"] for s in api._settings()["sections"] if s["section"] == "notes")
    assert api.post("settings", {"key": "notes.open_with", "value": "kitty nvim {path}"}) == (200, {"ok": True})
    assert api.post("open-note", {"id": "inbox/idea"}) == (200, {"ok": True})
    assert seen[-1][1:] == ["nvim", str((env.app.workspace / "inbox" / "idea.md").resolve())]
    assert api.post("open-note", {"id": "../outside"})[0] == 404


# ------------------------------------------------------------------------------- ask-me --then
@pytest.fixture
def cli(env, monkeypatch):
    """The CLI talking to this test's assistant directly, with sleeps that let 'you' answer."""
    from kurooto import cli as cli_mod
    from kurooto.web.api import Api

    env.app.settings.set("notify.desktop", False)
    api = Api(env.app)
    monkeypatch.setattr(cli_mod, "ask_running", lambda path, body=None: api.post(path, body or {})[1])
    answers: list = []

    def sleep(s):
        if answers:
            qid = env.app.ask.pending()[-1]["id"]
            env.app.ask.answer(qid, answers.pop(0), "telegram")

    monkeypatch.setattr("time.sleep", sleep)
    return answers


def then_script(tmp_path) -> tuple[str, str]:
    out = tmp_path / "then-out.json"
    script = tmp_path / "record.py"
    script.write_text(f"import json, sys\nopen({str(out)!r}, 'w').write(json.dumps(sys.argv[1:]))\n")
    return json.dumps([sys.executable, str(script), "{answer}", "id={id}"]), str(out)


def test_ask_me_then_runs_the_command_with_the_answer(env, cli, capsys, tmp_path):
    from kurooto.cli import main, then_argv, then_fill

    assert then_argv('notify-send "Your answer" {answer}') == ["notify-send", "Your answer", "{answer}"]
    assert then_fill(["echo", "{answer}"], "a; rm -rf ~", "q1") == ["echo", "a; rm -rf ~"]  # one argument, no shell
    then, out = then_script(tmp_path)
    cli.append("proofs; and $(more)")
    assert main(["ask-me", "Which?", "--wait", "--timeout", "1", "--then", then]) == 0
    qid = env.app.ask.recent()[-1]["id"]
    assert json.loads(open(out).read()) == ["proofs; and $(more)", f"id={qid}"]
    assert capsys.readouterr().out.strip() == "proofs; and $(more)"
    assert main(["ask-me", "Which?", "--then", "'unclosed"]) == 2


def test_ask_me_then_in_the_background(env, cli, capsys, tmp_path, monkeypatch):
    from kurooto.cli import main

    started: list = []

    class P:
        def __init__(self, cmd, **kw):
            started.append(cmd)

    monkeypatch.setattr(subprocess, "Popen", P)
    then, out = then_script(tmp_path)
    assert main(["ask-me", "Ship it?", "--expires", "6h", "--then", then]) == 0
    qid = capsys.readouterr().out.strip()
    cmd = started[-1]
    assert cmd[cmd.index("--id") + 1] == qid and cmd[cmd.index("--timeout") + 1] == "360" and "--bg" in cmd
    assert json.loads(cmd[cmd.index("--then") + 1]) == json.loads(then)
    monkeypatch.undo()  # the background copy itself, run here
    from kurooto import cli as cli_mod
    from kurooto.web.api import Api

    api = Api(env.app)
    monkeypatch.setattr(cli_mod, "ask_running", lambda path, body=None: api.post(path, body or {})[1])
    monkeypatch.setattr("time.sleep", lambda s: env.app.ask.answer(qid, "yes please", "telegram"))
    assert main(cmd[cmd.index("ask-me") :]) == 0
    assert json.loads(open(out).read()) == ["yes please", f"id={qid}"]
    bad = json.dumps(["kurooto-no-such-program-x", "{answer}"])
    q2 = env.app.ask.ask("Again?", source="cli")
    monkeypatch.setattr("time.sleep", lambda s: env.app.ask.answer(q2, "ok", "telegram"))
    assert main(["ask-me", "--id", q2, "--wait", "--timeout", "1", "--then", bad, "--bg"]) == 127
    assert "failed" in env.fake.texts()[-1]


# --------------------------------------------------------------------------------- Telegram menu
def menu_calls(env, method="setMyCommands"):
    return [p for m, p in env.fake.sent if m == method]


def test_telegram_menu_follows_the_features(env, ai):  # noqa: F811
    tg = env.tg
    assert tg.sync_menu() is True
    cmds = {c["command"]: c["description"] for c in menu_calls(env)[-1]["commands"]}
    assert {"help", "status", "q", "aboutme", "skills", "term_setup", "journal"} <= set(cmds)
    assert all(3 <= len(v) <= 100 for v in cmds.values()) and len(cmds) <= 100
    assert cmds["pause"] == "pause me" and "-" not in "".join(cmds)
    assert tg.sync_menu() is False and len(menu_calls(env)) == 1  # nothing changed: Telegram isn't asked again
    env.on("subjects")
    assert tg._menu_tick() is True and "term" in {c["command"] for c in menu_calls(env)[-1]["commands"]}
    assert tg._menu_tick() is False
    seen: list = []
    env.app.modules["skills"].run = lambda name, *a, **k: seen.append(name) or "j1"
    assert env.say("/term_setup algebra and topology") == "On it." and seen == ["term-setup"]
    env.app.settings.set("telegram.menu", False)
    assert tg._menu_tick() is True and len(menu_calls(env, "deleteMyCommands")) == 1
    assert tg.sync_menu() is False


# ------------------------------------------------------------------- programs that run now and then
def test_a_feature_whose_programs_run_now_and_then_is_idle_not_down(env, tmp_path):
    from pathlib import Path

    from kurooto import top
    from kurooto.web.live import Vitals
    from tests.unit.test_dense import board_data

    app = env.app
    env.on("reminders", "deadlines")
    app.modules["reminders"].processes = (Path(sys.executable).name[:12],)  # this test's own python: running
    app.modules["deadlines"].processes = ("no-such-backup-xyz",)  # not running now
    for m in ("reminders", "deadlines"):
        app.modules[m].processes_intermittent = True
    try:
        feats = {f["id"]: f for f in Vitals(app).board()["features"]}
    finally:
        for m in ("reminders", "deadlines"):
            del app.modules[m].processes, app.modules[m].processes_intermittent
    assert feats["deadlines"]["idle"] is True and feats["deadlines"]["down"] is False
    assert feats["reminders"]["proc"]["mem"] > 0 and not feats["reminders"]["idle"] and not feats["reminders"]["down"]
    assert feats["reminders"]["intermittent"] and not feats["telegram"]["intermittent"]
    assert not feats["telegram"]["idle"] and not feats["telegram"]["down"]  # names no programs
    data = board_data(tmp_path)
    data["kurooto"]["board"]["features"].append(
        {"id": "backups", "title": "Backups", "proc": None, "down": False, "idle": True, "intermittent": True}
    )
    flat = "\n".join(top.ANSI.sub("", ln) for ln in top.render(data, 200, 70, colour=False))
    assert "Backups" in flat and [ln for ln in flat.split("\n") if "Backups" in ln and "idle" in ln]
