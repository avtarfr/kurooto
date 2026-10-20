"""Class packs: the strict .kurooto-course schema (nothing personal fits, and an export never carries any), export
from your setup or a term note, import on Telegram with electives, lab batch and rule changes, re-import with a diff,
your own setup winning, remove and undo, the health check and the terminal commands."""

from __future__ import annotations

import copy
import datetime as dt
import json

import pytest

from kurooto.core.clock import now
from kurooto.modules import classpacks, recurring
from kurooto.modules import coursepack as cp
from tests.unit.test_study import last_buttons


def d(n: int) -> str:
    return (now().date() + dt.timedelta(days=n)).isoformat()


def exam_n() -> int:
    """A day for the midterm that's no Thursday or Friday (the quiz's days), so the two stay apart on the list."""
    return next(n for n in range(20, 30) if (now().date() + dt.timedelta(days=n)).weekday() not in (3, 4))


def a_pack() -> dict:
    return {
        "format": "kurooto-course",
        "version": 1,
        "title": "Year 2 section B",
        "checked": d(-2),
        "made": d(-1),
        "term": {
            "name": "Autumn",
            "starts": d(-60),
            "classes_end": d(30),
            "holidays": [{"from": d(3), "to": d(3), "what": "Holiday"}, {"from": d(10), "to": d(12), "what": "Break"}],
            "exam_periods": [{"from": d(35), "to": d(45), "what": "End-term exams"}],
        },
        "attendance": {"min_pct": 75, "labs": "separate"},
        "courses": [
            {"id": "linear-algebra", "name": "Linear Algebra", "short": ["la", "ma101"], "elective": False},
            {"id": "statistics", "name": "Statistics", "short": ["stats"], "elective": False,
             "attendance": {"min_pct": 80, "labs": "together"}},
            {"id": "machine-learning", "name": "Machine Learning", "short": ["ml"], "elective": True},
            {"id": "topology", "name": "Topology", "short": [], "elective": True},
        ],
        "classes": [
            {"course": "linear-algebra", "day": "mon", "start": "09:00", "end": "09:55"},
            {"course": "statistics", "day": "tue", "start": "11:00", "end": "11:55", "kind": "lecture", "batch": ""},
            {"course": "statistics", "day": "thu", "start": "14:00", "end": "16:55", "kind": "lab", "batch": "A"},
            {"course": "statistics", "day": "fri", "start": "14:00", "end": "16:55", "kind": "lab", "batch": "B"},
            {"course": "machine-learning", "day": "wed", "start": "10:00", "end": "10:55", "kind": "lecture",
             "batch": ""},
            {"course": "topology", "day": "wed", "start": "12:00", "end": "12:55", "kind": "lecture", "batch": ""},
        ],
        "quizzes": [
            {"course": "linear-algebra", "what": "Quiz", "every_weeks": 1, "day": "thu", "time": "10:00", "next": "",
             "until": "", "batch": ""}
        ],
        "exams": [{"course": "linear-algebra", "date": d(exam_n()), "time": "10:00", "what": "Midterm"}],
    }  # fmt: skip


SCHEMA_KEYS = cp.TOP | cp.TERM | cp.SPAN | cp.RULE | cp.COURSE | cp.CLASS | cp.QUIZ | cp.EXAM


def keys_in(obj) -> set:
    if isinstance(obj, dict):
        return set(obj) | set().union(*(keys_in(v) for v in obj.values()))
    if isinstance(obj, list):
        return set().union(*(keys_in(v) for v in obj)) if obj else set()
    return set()


@pytest.fixture
def packs(env):
    env.app.settings.set("availability.night.enabled", False)  # the tests run at the real time, maybe at night
    env.app.settings.set("notify.desktop", False)
    env.on("subjects", "deadlines", "classpacks")
    return env


def send(env, pack, fid="P1", name="section-b.kurooto-course"):
    raw = pack if isinstance(pack, bytes) else json.dumps(pack).encode()
    env.fake.files[f"docs/{fid}.pdf"] = raw
    return env.say("", document={"file_id": fid, "file_name": name})


def button(env, label_start: str) -> str:
    return next(b["callback_data"] for b in last_buttons(env) if b["text"].startswith(label_start))


# ------------------------------------------------------------------------------------------------ the schema
def test_a_pack_reads_back_the_same():
    p = cp.validate(a_pack())
    assert cp.load(cp.dumps(p)) == p
    assert p["courses"][0]["short"] == ["la", "ma101"] and p["classes"][2]["batch"] == "A"
    assert cp.batches(p) == ["A", "B"] and [c["id"] for c in cp.electives(p)] == ["machine-learning", "topology"]
    assert "4 courses (2 electives), 6 classes a week (lab batches A, B)" in cp.overview(p)
    assert cp.file_name(p) == f"year-2-section-b-{d(-1)}.kurooto-course"


def at(pack: dict, path: str, value):
    """The pack with one more field (or a changed one) at a dotted path: "courses.0.teacher"."""
    p = copy.deepcopy(pack)
    *head, last = path.split(".")
    cur = p
    for k in head:
        cur = cur[int(k)] if k.isdigit() else cur[k]
    cur[int(last) if last.isdigit() else last] = value
    return p


EMAIL = "sam" + "@" + "example.org"
PHONE = "+91 98" + "765 43210"
TOKEN = "123456" + "789:" + "AAH" + "x9" * 16


@pytest.mark.parametrize(
    "path, value, said",
    [
        ("notes", "my notes", '"notes", which a class pack never has'),
        ("skills", [], '"skills"'),
        ("owner", "Sam", '"owner"'),
        ("telegram_token", TOKEN, '"telegram_token"'),
        ("courses.0.teacher", "Prof. Sam", '"teacher"'),
        ("classes.0.room", "L1", '"room"'),
        ("term.notes", "x", '"notes"'),
        ("title", f"Section B, ask {EMAIL}", "an email address"),
        ("title", f"Section B {PHONE}", "a phone number"),
        ("courses.1.name", "Statistics (see https://example.org)", "a link"),
        ("courses.1.name", "[[stats/course]]", "a link"),
        ("title", "B, with @samq", "an @handle"),
        ("exams.0.what", "Midterm in /ho" + "me/sam/notes", "a file path"),
        ("courses.0.name", "Linear Algebra " + "a1B2c3D4e5F6g7H8i9J0k", "a key or token"),
        ("courses.0.short", ["la", TOKEN], "short names"),
        ("format", "something-else", "isn't a class pack"),
        ("version", 2, "doesn't read"),
        ("checked", "2026-02-30", "isn't a real date"),
        ("checked", d(5), "checked after it was made"),
        ("classes.0.course", "chemistry", "names a course that isn't in the pack"),
        ("classes.0.end", "08:00", "ends before it starts"),
        ("quizzes.0.every_weeks", 2, "needs a next date"),
        ("courses.0.elective", "yes", "true or false"),
        ("attendance", {"min_pct": 120}, "from 0 to 100"),
    ],
)
def test_the_schema_refuses_anything_else(path, value, said):
    with pytest.raises(cp.PackError) as e:
        cp.validate(at(a_pack(), path, value))
    assert said in str(e.value)


def test_files_that_arent_packs():
    with pytest.raises(cp.PackError, match="can't read it"):
        cp.load(b"\x00\x01 not json")
    with pytest.raises(cp.PackError, match="at most 200 KB"):
        cp.load(b" " * (cp.MAX_BYTES + 1))
    big = a_pack()
    big["classes"] = big["classes"] * 50
    with pytest.raises(cp.PackError, match="at most 250"):
        cp.validate(big)
    assert cp.personal("Midterm 2026-11-12 10:00") is None  # dates and times aren't phone numbers


def test_reading_what_someone_typed():
    p = cp.validate(a_pack())
    assert cp.read_change("la 80", p) == ("rule", {"course": "linear-algebra", "min_pct": 80})
    assert cp.read_change("Linear Algebra 70%", p) == ("rule", {"course": "linear-algebra", "min_pct": 70})
    assert cp.read_change("all 85", p) == ("rule", {"course": "*", "min_pct": 85})
    assert cp.read_change("stats labs separate", p) == ("rule", {"course": "statistics", "labs": "separate"})
    assert cp.read_change("la quiz off", p) == ("off", {"key": "linear-algebra|quiz"})
    assert cp.read_change("la midterm off", p) == ("off", {"key": "linear-algebra|midterm"})
    assert cp.read_change("la quiz fri 11:00", p) == (
        "move",
        {"key": "linear-algebra|quiz", "day": "fri", "time": "11:00"},
    )
    assert cp.read_change("electives ml, topology", p) == ("electives", {"ids": ["machine-learning", "topology"]})
    assert cp.read_change("batch b", p) == ("batch", {"batch": "B"})
    assert cp.read_change("checked 2026-10-18", p) == ("checked", {"date": "2026-10-18"})
    assert cp.read_change("la reset", p) == ("reset", {"course": "linear-algebra"})
    assert cp.read_change("batch Z", p) is None and cp.read_change("chemistry 80", p) is None
    assert cp.read_change("la 180", p) is None


# --------------------------------------------------------------------------------------------- importing
def test_import_on_telegram_with_electives_batch_and_a_changed_rule(packs):
    app, sub, dl = packs.app, packs.app.modules["subjects"], packs.app.modules["deadlines"]
    out = send(packs, a_pack())
    assert out.startswith("Class pack: Year 2 section B (Autumn).")
    assert f"Checked against the official timetable on {d(-2)}" in out
    assert "Your electives: none ticked" in out and "Your lab batch: none yet" in out
    assert "Attendance: 75%, labs counted separately; Statistics 80%, labs counted in" in out
    assert not list(app.workspace.glob("inbox/*kurooto-course*"))  # moved out of the notes
    assert list((app.paths.data / "classpacks" / "received").iterdir())
    assert packs.press(button(packs, "[ ] Machine Learning")).startswith("Machine Learning: ticked.")
    assert packs.press(button(packs, "Batch A")).startswith("Batch A.")
    packs.reply_to_last("la 80\nla quiz fri 11:00\nnonsense here")
    review = packs.fake.texts()[-1]
    assert "Your electives: Machine Learning" in review and "Your lab batch: A" in review
    assert "Linear Algebra 80%, labs counted separately (yours)" in review
    assert "Moved by you: Linear Algebra Quiz to Fri 11:00" in review
    assert any("I couldn't read: nonsense here" in t for t in packs.fake.texts()[-3:])
    assert sub.timetable() == []  # nothing counts before Import
    assert packs.press(button(packs, "Import")) == "Imported."
    assert packs.fake.texts()[-1].startswith("Class pack imported: Year 2 section B.")
    rows = {(c["day"], c["start"], c["subject"]) for c in sub.timetable()}
    assert rows == {("mon", "09:00", "linear-algebra"), ("tue", "11:00", "statistics"),
                    ("thu", "14:00", "statistics"), ("wed", "10:00", "machine-learning")}  # fmt: skip
    assert sub.resolve("ma101") == "linear-algebra" and sub.resolve("topology") is None
    assert d(3) in sub.holidays() and d(11) in sub.holidays() and sub.term_ends() == d(30)
    assert sub.no_classes(now().date() + dt.timedelta(days=40)) == "exams"
    items = {it["title"]: it for it in dl.items().values() if it["status"] == "open"}
    midterm = items["Linear Algebra Midterm"]
    assert midterm["due"] == f"{d(exam_n())}T10:00:00" and midterm["kind"] == "exam"
    quiz = [it for t, it in items.items() if t == "Linear Algebra: Quiz"]
    assert quiz and all(dt.date.fromisoformat(it["due"][:10]).weekday() == 4 for it in quiz)  # moved to Fridays
    assert "(class pack" in packs.say("/recurring")
    mod = app.modules["classpacks"]
    assert mod.attendance_rule("la") == {"min_pct": 80, "labs": "separate", "yours": True}
    assert mod.attendance_rule("Statistics") == {"min_pct": 80, "labs": "together", "yours": False}
    assert mod.class_kind("statistics", "thu", "14:00") == "lab"
    status = packs.say("/classpack")
    assert "Your electives: Machine Learning (of Machine Learning, Topology)." in status and "batch: A" in status
    out = packs.say("/classpack set stats 90")
    assert out.startswith("Statistics: at least 90%.") and "Attendance for Statistics: 80%" in out
    assert mod.attendance_rule("stats")["min_pct"] == 90


def test_reimporting_after_a_reshuffle_shows_the_diff_and_keeps_your_choices(packs):
    app = packs.app
    mod = app.modules["classpacks"]
    send(packs, a_pack())
    packs.press(button(packs, "[ ] Machine Learning"))
    packs.press(button(packs, "Batch A"))
    packs.reply_to_last("la 80")
    packs.press(button(packs, "Import"))
    new = a_pack()
    new["checked"], new["made"] = d(-1), d(0)
    new["classes"][2]["day"] = "wed"  # the batch A lab moves
    new["classes"][2]["start"], new["classes"][2]["end"] = "14:00", "16:55"
    new["term"]["holidays"].append({"from": d(5), "to": d(5), "what": "Founders day"})
    new["quizzes"][0]["time"] = "11:00"
    new["exams"][0]["date"] = d(exam_n() + 1)
    new["courses"][1]["attendance"]["min_pct"] = 85
    new["courses"].append({"id": "cryptography", "name": "Cryptography", "short": [], "elective": True})
    out = send(packs, new, fid="P2")
    assert "What changes for you from the pack you have" in out
    for line in [
        f"+ Holiday {d(5)}: Founders day",
        "Thu 14:00-16:55 Statistics (lab, batch A) -> Wed 14:00-16:55",
        "Linear Algebra Quiz: every week, Thu 10:00 -> every week, Thu 11:00",
        f"Linear Algebra Midterm: {d(exam_n())} 10:00 -> {d(exam_n() + 1)} 10:00",
        "Attendance for Statistics: 80%, labs counted in -> 85%, labs counted in",
    ]:
        assert line in out, line
    assert "Machine Learning" not in out.split("What changes")[1]  # still yours: not a change
    assert (
        "Your electives: Machine Learning" in out
        and "Your lab batch: A" in out
        and "[ ] Cryptography" in str(last_buttons(packs))
    )
    assert mod.attendance_rule("la")["min_pct"] == 80  # nothing changes before Import
    packs.press(button(packs, "Import"))
    assert mod.attendance_rule("la") == {"min_pct": 80, "labs": "separate", "yours": True}  # your change kept
    assert ("wed", "14:00") in {(c["day"], c["start"]) for c in app.modules["subjects"].timetable()}
    out = send(packs, new, fid="P3")
    assert out.startswith("That's the class pack you have already")


def test_your_own_setup_wins_over_the_pack(packs):
    app, sub = packs.app, packs.app.modules["subjects"]
    packs.say("/subject add Linear Algebra (la)")
    packs.say("/class mon 09:00-10:30 la")  # your own time for the same class
    packs.say(f"/term ends {d(25)}")
    f = recurring.note_file(app)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        recurring.new_note("Kurooto", now().date()) + "| la | Quiz | 1 | Fri | 09:00 | | |\n", encoding="utf-8"
    )
    send(packs, a_pack())
    packs.press(button(packs, "Import"))
    mon = [c for c in sub.timetable() if c["day"] == "mon"]
    assert mon == [{"day": "mon", "start": "09:00", "end": "10:30", "subject": "linear-algebra"}]
    assert sub.term_ends() == d(25)
    rows = [r for r in app.modules["deadlines"].recurring_rows() if r["slug"] == "linear-algebra"]
    assert [(r["day"], r.get("from_pack", False)) for r in rows] == [("fri", False)]  # your table's row wins
    assert app.modules["deadlines"].remove_recurring("la", "Quiz") is True  # your row; the pack's isn't touched


def test_remove_and_undo(packs):
    app, sub = packs.app, packs.app.modules["subjects"]
    assert packs.say("/classpack undo") == "Nothing to undo."
    send(packs, a_pack())
    packs.press(button(packs, "Import"))
    assert sub.timetable()
    assert packs.say("/classpack remove").startswith("Class pack removed")
    assert sub.timetable() == [] and sub.holidays() == []
    t = now().isoformat()
    assert not [it for it in app.modules["deadlines"].items().values() if it["status"] == "open" and it["due"] > t]
    assert packs.say("/classpack undo").startswith("Back to the class pack you had before (Year 2 section B")
    assert sub.timetable() and packs.say("/classpack").startswith("Class pack: Year 2 section B")
    assert packs.say("/classpack undo").startswith("Back to no class pack")


def test_cancel_refusals_and_the_feature_off(packs):
    app = packs.app
    out = send(packs, at(a_pack(), "courses.0.teacher", "Sam"))
    assert out.startswith("That isn't a class pack I can use") and "Nothing was imported" in out
    send(packs, a_pack(), fid="P2")
    assert packs.press(button(packs, "Cancel")) == "Cancelled; nothing changed."
    assert app.modules["classpacks"].active() is None
    app.disable("classpacks")
    out = send(packs, a_pack(), fid="P3")
    assert out.startswith("That's a class pack. Turn on Class packs")
    assert app.modules["subjects"].timetable() == []
    packs.on("files")
    assert send(packs, b"%PDF-1.4 a syllabus", fid="P4", name="syllabus.pdf").startswith("Saved to")  # still Files


# --------------------------------------------------------------------------------------------- exporting
def term_note() -> str:
    return f"""# Section B timetable

## Weekly timetable
| Day | Time | Subject | Code | Type | Batch |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Mon | 09:00-09:55 | [[linear-algebra/course|Linear Algebra]] | MA101 | Lecture | |
| Tue | 11:00-11:55 | Statistics | ST102 | | |
| Thu | 14:00-16:55 | Statistics | | Lab | A |
| Fri | 14:00-16:55 | Statistics | | Lab | B |
| Wed | 10:00-10:55 | Machine Learning | | Elective | |

## Key dates
| Date | What |
| :--- | :--- |
| {d(3)} | Holiday |
| {d(20)} | Linear Algebra midterm (10:00-11:00) |
| {d(30)} | Last day of classes |
| {d(35)} – {d(45)} | End-term exams |

## Recurring quizzes
| Subject | What | Every (weeks) | Day | Time | Next | Until |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Linear Algebra | Quiz | 1 | Thu | 10:00 | | |

## Attendance
| Course | Minimum | Labs |
| :--- | :--- | :--- |
| All | 75 | separate |
| Statistics | 80 | together |
"""


def test_export_from_a_term_note_with_batches_electives_quizzes_and_rules(packs):
    app = packs.app
    f = app.workspace / "terms" / "section-b.md"
    f.parent.mkdir(parents=True)
    f.write_text(term_note(), encoding="utf-8")
    pack, left, why = app.modules["classpacks"].draft_pack("terms/section-b")
    assert why == "" and left == []
    assert [c["id"] for c in pack["courses"]] == ["linear-algebra", "statistics", "machine-learning"]
    assert [c["id"] for c in pack["courses"] if c["elective"]] == ["machine-learning"]
    assert {(k["course"], k["kind"], k["batch"]) for k in pack["classes"] if k["kind"] == "lab"} == {
        ("statistics", "lab", "A"),
        ("statistics", "lab", "B"),
    }
    assert pack["quizzes"][0]["course"] == "linear-algebra" and pack["exams"][0]["what"] == "Linear Algebra midterm"
    assert pack["attendance"] == {"min_pct": 75, "labs": "separate"}
    assert pack["courses"][1]["attendance"] == {"min_pct": 80, "labs": "together"}
    assert pack["term"]["classes_end"] == d(30) and pack["term"]["exam_periods"][0]["what"] == "End-term exams"
    ok, said, out = app.modules["classpacks"].write(pack, d(0))
    assert ok and cp.read(out)["checked"] == d(0)


def test_export_from_your_setup_carries_nothing_personal(packs):
    app = packs.app
    app.settings.set("you.name", "Samira Quill")
    app.secrets.set("telegram.extra_token", TOKEN)
    packs.say("/subject add Linear Algebra (la, linalg)")
    packs.say("/subject add Statistics (stats)")
    packs.say("/class mon 09:00-09:55 la")
    packs.say("/class tue 11:00-11:55 stats")
    packs.say("/skip la")
    packs.say(f"/due {d(4)} 17:00 essay for Samira's club")
    (app.workspace / "inbox").mkdir(exist_ok=True)
    (app.workspace / "inbox" / "diary.md").write_text("Dear diary, a private thought.\n", encoding="utf-8")
    note = app.workspace / "terms" / "mine.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        f"## Key dates\n| Date | What |\n|---|---|\n| {d(3)} | Holiday |\n| {d(6)} | Samira's birthday party |\n"
        f"| {d(20)} | Linear Algebra midterm |\n| {d(21)} | Statistics quiz, write to {EMAIL} |\n",
        encoding="utf-8",
    )
    packs.say("/term note terms/mine")
    packs.say("/recurring add la quiz every week thu 10:00")
    mod = app.modules["classpacks"]
    pack, left, _ = mod.draft_pack()
    ok, said, f = mod.write(pack, d(0))
    text = f.read_text(encoding="utf-8")
    for personal in ["Samira", "Quill", "diary", "private", "essay", "club", TOKEN, "@", "skip"]:
        assert personal not in text, personal
    assert keys_in(json.loads(text)) <= SCHEMA_KEYS
    assert [c["id"] for c in pack["courses"]] == ["linear-algebra", "statistics"]
    assert [e["what"] for e in pack["exams"]] == ["Linear Algebra midterm"]
    assert any("email address" in x for x in left)
    assert pack["quizzes"][0]["day"] == "thu" and pack["term"]["holidays"][0]["from"] == d(3)


def test_export_on_telegram_ticks_electives_and_stamps_the_check(packs):
    app = packs.app
    packs.say("/subject add Linear Algebra (la)")
    packs.say("/subject add Machine Learning (ml)")
    packs.say("/class mon 09:00-09:55 la")
    packs.say("/class wed 10:00-10:55 ml")
    out = packs.say("/classpack export")
    assert out.startswith("A class pack of your setup.") and "It carries no names, notes, keys or skips" in out
    assert packs.press(button(packs, "[ ] Machine Learning")) == "Machine Learning: an elective."
    packs.reply_to_last("title Year 2 section B\nla 80\nall labs together")
    assert "Title: Year 2 section B." in packs.fake.texts()[-2]
    packs.reply_to_last(f"title mail {EMAIL}")
    assert "Not that title" in packs.fake.texts()[-2]
    assert packs.press(button(packs, "Checked today")).startswith("Made year-2-section-b-")
    assert [m for m, p in packs.fake.sent if m == "sendDocument"]
    f = next((app.paths.data / "classpacks").glob("*.kurooto-course"))
    p = cp.read(f)
    assert p["checked"] == d(0) and p["title"] == "Year 2 section B"
    assert [c["id"] for c in p["courses"] if c["elective"]] == ["machine-learning"]
    assert p["courses"][0]["attendance"] == {"min_pct": 80, "labs": "separate"}
    assert p["attendance"]["labs"] == "together"
    out = packs.say("/classpack export")
    packs.reply_to_last(f"checked {d(3)}")
    assert "hasn't come yet" in packs.fake.texts()[-1]


# ---------------------------------------------------------------------------------- health, clock, terminal
def test_health_check_and_draft_expiry_with_a_fake_clock(packs, monkeypatch):
    app, mod = packs.app, packs.app.modules["classpacks"]
    send(packs, a_pack())
    packs.press(button(packs, "Import"))
    check = mod.health_check()
    assert check.probe(False) == (True, f"checked against the official timetable on {d(-2)}")
    later = now() + dt.timedelta(days=45 + 15)
    monkeypatch.setattr(classpacks, "now", lambda: later)
    assert check.probe(False) == (False, f"your class pack is for a term that ended on {d(45)}")
    assert [r for r in app.health.evaluate(only="classpacks") if r.ok is False]
    monkeypatch.setattr(classpacks, "now", lambda: now())
    send(packs, at(a_pack(), "title", "Section C"), fid="P2")
    left = list((mod.dir / "drafts").glob("*.json"))
    monkeypatch.setattr(classpacks, "now", lambda: later)
    mod._new_draft("import", pack=a_pack())
    assert not any(f.exists() for f in left)  # a week-old review nobody finished is gone


def test_terminal_check_export_and_import(packs, tmp_path, monkeypatch, capsys):
    from kurooto import cli as cli_mod
    from kurooto.web.api import Api

    api = Api(packs.app)
    monkeypatch.setattr(cli_mod, "ask_running", lambda path, body=None: api.post(path, body or {})[1])
    good = tmp_path / "b.kurooto-course"
    good.write_text(json.dumps(a_pack()), encoding="utf-8")
    assert cli_mod.main(["classpack", "check", str(good)]) == 0
    assert "Year 2 section B: checked against the official timetable on" in capsys.readouterr().out
    bad = tmp_path / "bad.kurooto-course"
    bad.write_text(json.dumps(at(a_pack(), "skills", ["x"])), encoding="utf-8")
    assert cli_mod.main(["classpack", "check", str(bad)]) == 1
    note = tmp_path / "section.md"
    note.write_text(term_note(), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    code = cli_mod.main(
        ["classpack", "export", "--from", str(note), "--checked", "today", "--title", "Section B", "--out", str(out)]
    )
    assert code == 0
    made = next(out.glob("*.kurooto-course"))
    assert cp.read(made)["title"] == "Section B"
    assert cli_mod.main(["classpack", "export", "--from", str(note), "--checked", d(2)]) == 1
    assert cli_mod.main(["classpack", "import", str(made)]) == 0
    assert "Class pack: Section B." in packs.fake.texts()[-1]


def test_a_pack_changed_by_hand_and_your_own_recurring_row(packs):
    app = packs.app
    mod = app.modules["classpacks"]
    send(packs, a_pack())
    packs.press(button(packs, "Import"))
    out = packs.say("/recurring add la quiz every week fri 09:00")  # yours, over the pack's
    assert "already" not in out
    rows = [r for r in app.modules["deadlines"].recurring_rows() if r["slug"] == "linear-algebra"]
    assert [(r["day"], r.get("from_pack", False)) for r in rows] == [("fri", False)]
    rec = mod.record()
    rec["pack"]["owner"] = "Sam"
    mod.active_file.write_text(json.dumps(rec), encoding="utf-8")
    assert packs.say("/classpack").startswith("The imported class pack can't be read any more")
    assert mod.layer() is None and app.modules["subjects"].timetable() == []
    assert mod.health_check().probe(False)[0] is False
    assert packs.say("/classpack remove").startswith("Class pack removed")
