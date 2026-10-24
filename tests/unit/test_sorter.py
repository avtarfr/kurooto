"""0.7.4: the notes sorter: a scratch folder's notes move by themselves into the folders where they belong, never
deleting or overwriting anything, with Undo, and noticing when a note belongs elsewhere. Fake AI answers stand in for
the AI."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

from kurooto import providers
from kurooto.core import sorting
from kurooto.providers.base import Result, Task, Verdict

OLD = time.time() - 3600  # long enough ago that a note has "settled"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["subjects", "sorter"])
    a.settings.set("subjects.list", [{"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["LA"]},
                                     {"name": "Topology", "slug": "topology", "aliases": []}])  # fmt: skip
    a.settings.set("sorter.ai", False)
    ws = Path(a.workspace)
    for d in ("linear-algebra", "topology", "zettel", "inbox"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    told = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: told.append((text, kw)))
    a.told = told
    a.modules["sorter"].start()  # (the settings above skip app.enable, which would)
    yield a
    a.close()


def note(app, rel, text, age=3600):
    f = Path(app.workspace) / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    os.utime(f, (time.time() - age, time.time() - age))
    return f


def snapshot(app) -> dict[str, str]:
    """Every file of the notes: its path -> a hash of its content (a move shows as the same hash at another path)."""
    out = {}
    for f in Path(app.workspace).rglob("*"):
        if f.is_file() and ".git" not in f.parts:
            out[f.relative_to(app.workspace).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def contents(app) -> list[str]:
    return sorted(snapshot(app).values())


def sorter(app):
    return app.modules["sorter"]


# ---------------------------------------------------------------------------------------------- moving, never deleting
def test_a_note_with_a_subject_moves_to_its_folder_and_nothing_is_lost(app):
    note(app, "inbox/eigen.md", "---\nsubject: LA\n---\n# Eigenvalues\nAv = lv.\n")
    note(app, "inbox/knots.md", "---\ntags: [topology]\n---\n# Knots\n")
    before = contents(app)
    out = sorter(app).run()
    ws = Path(app.workspace)
    assert (ws / "linear-algebra" / "eigen.md").is_file() and (ws / "topology" / "knots.md").is_file()
    assert not (ws / "inbox" / "eigen.md").exists() and (ws / "inbox").is_dir()  # the scratch folder stays
    assert contents(app) == before  # the same contents, nothing deleted, nothing changed
    assert len(out["moved"]) == 2 and out["log"]
    text, kw = app.told[-1]
    assert "Sorted 2 notes" in text and kw["buttons"] == [[("Undo", f"srt:{out['log']}:undo")]]


def test_a_title_naming_a_subject_places_it_and_a_name_that_is_taken_gets_a_number(app):
    note(app, "linear-algebra/notes.md", "# older\n")
    note(app, "inbox/notes.md", "# Linear Algebra: week 3\nx\n")
    before = contents(app)
    sorter(app).run()
    ws = Path(app.workspace)
    assert (ws / "linear-algebra" / "notes.md").read_text() == "# older\n"  # never overwritten
    assert (ws / "linear-algebra" / "notes-2.md").read_text().startswith("# Linear Algebra: week 3")
    assert contents(app) == sorted(before)


def test_only_the_scratch_folder_moves_and_recent_or_marked_notes_wait(app):
    note(app, "zettel/idea.md", "---\nsubject: LA\n---\n# not in the scratch folder\n")
    note(app, "inbox/typing.md", "---\nsubject: LA\n---\n# still being written\n", age=30)
    note(app, "inbox/stay.md", "---\nsubject: LA\nsort: no\n---\n# keep here\n")
    before = snapshot(app)
    assert sorter(app).run()["moved"] == []
    assert snapshot(app) == before


def test_a_new_top_level_folder_or_a_private_one_is_never_a_place(app):
    note(app, "about-me/profile.md", "# me\n")
    note(app, "inbox/x.md", "---\nsubject: nothing-like-this\n---\n# x\n")
    assert "about-me" not in sorting.folders(app) and "inbox" not in sorting.folders(app)
    assert sorter(app).run()["moved"] == []


def test_the_scratch_folder_cannot_point_outside_the_notes(app):
    for bad in ("../elsewhere", "/etc", "C:/x", ".hidden", ""):
        app.settings.set("sorter.folder", bad)
        assert sorting.scratch_rel(app) == "inbox"


def test_a_pass_stops_at_the_nights_limit(app):
    app.settings.set("sorter.per_night", 2)
    for i in range(5):
        note(app, f"inbox/n{i}.md", f"---\nsubject: LA\n---\n# n{i}\n")
    assert len(sorter(app).run()["moved"]) == 2
    assert len(sorter(app).run()["moved"]) == 0  # the same day: nothing more
    assert len(list((Path(app.workspace) / "inbox").glob("*.md"))) == 3


# ---------------------------------------------------------------------------------------------- links
def test_links_in_kurooto_text_are_fixed_and_a_note_your_own_notes_link_to_waits(app):
    note(app, "inbox/a.md", "---\nsubject: LA\n---\n# A\n")
    note(app, "inbox/b.md", "---\nsubject: LA\n---\n# B\n")
    note(app, "zettel/mine.md", "# mine\nSee [[inbox/b]] for more.\n")  # your own text links to b by its path
    note(app, "zettel/kuro.md", "---\nmade_by: kurooto\n---\n# kuro\nSee [[inbox/a]].\n")  # Kurooto's text links to a
    sorter(app).run()
    ws = Path(app.workspace)
    assert (ws / "linear-algebra" / "a.md").is_file()
    assert (ws / "inbox" / "b.md").is_file()  # waits: moving it would break your link
    assert "[[linear-algebra/a]]" in (ws / "zettel" / "kuro.md").read_text()
    assert (ws / "zettel" / "mine.md").read_text() == "# mine\nSee [[inbox/b]] for more.\n"  # yours is untouched
    assert "link" in sorting.load(app)["waiting"]["inbox/b.md"]["why"]


# ---------------------------------------------------------------------------------------------- undo
def test_undo_puts_everything_back_exactly(app):
    note(app, "inbox/a.md", "---\nsubject: LA\n---\n# A\n")
    note(app, "inbox/b.md", "---\ntags: [topology]\n---\n# B\n")
    note(app, "zettel/kuro.md", "---\nmade_by: kurooto\n---\n# kuro\nSee [[inbox/a]].\n")
    before = snapshot(app)
    out = sorter(app).run()
    assert snapshot(app) != before
    msg = sorter(app)._button(out["log"], "undo")
    assert msg == "Put back." and snapshot(app) == before
    assert sorting.undo(app)["ok"] is False  # nothing left to undo


def test_sort_undo_command_and_status(app):
    note(app, "inbox/a.md", "---\nsubject: LA\n---\n# A\n")
    replies = []

    class Msg:
        def reply(self, text, buttons=None):
            replies.append((text, buttons))

    sorter(app).cmd(Msg(), "now")
    assert (Path(app.workspace) / "linear-algebra" / "a.md").is_file()
    sorter(app).cmd(Msg(), "")
    assert "Scratch folder: inbox" in replies[-1][0] and "Last pass: 1 moved" in replies[-1][0]
    assert sorter(app).cmd(Msg(), "undo") == "Put back."
    assert (Path(app.workspace) / "inbox" / "a.md").is_file()


# ---------------------------------------------------------------------------------------------- what it can't place
def test_a_note_it_cannot_place_stays_and_is_listed_with_guesses(app):
    note(app, "inbox/odd.md", "# Notes on topology and linear algebra together\nx\n")
    note(app, "inbox/zzz.md", "# a grocery list\nmilk\n")
    out = sorter(app).run()
    ws = Path(app.workspace)
    assert (ws / "inbox" / "zzz.md").is_file() and out["moved"] == [] and out["waiting"] == 2
    text, rows = sorter(app).waiting_text()
    assert "inbox/zzz.md" in text and rows  # odd.md has guesses (the folders named in it)
    button = rows[0][0][1]
    ref, act = button.split(":")[1:]
    assert sorter(app)._button(ref, act).startswith("Moved to")
    assert not (ws / "inbox" / "odd.md").exists()


# ---------------------------------------------------------------------------------------------- the AI step
class Chooser:
    id, label, kind = "main", "an AI", "api"

    def __init__(self, folder, conf=0.9):
        self.reply, self.tasks = json.dumps({"folder": folder, "confidence": conf, "why": "its topic"}), []

    def available(self):
        return True, ""

    def run(self, task: Task):
        self.tasks.append(task)
        return Result(Verdict.OK, self.reply, 1.0)


def with_ai(app, monkeypatch, folder, conf=0.9):
    brain = Chooser(folder, conf)
    monkeypatch.setattr(providers, "build", lambda a, w: brain if w == "main" else None)
    app.settings.set("brain.main", "main")
    app.settings.set("sorter.ai", True)
    return brain


def test_the_ai_places_a_note_the_rules_cannot(app, monkeypatch):
    brain = with_ai(app, monkeypatch, "zettel")
    note(app, "inbox/idea.md", "# A thought about habits\nsmall steps\n")
    assert sorter(app).run()["asked"] == 1
    app.jobs.run_next("bg")
    assert (Path(app.workspace) / "zettel" / "idea.md").is_file()
    assert (
        "Folders:" in brain.tasks[0].prompt
        and "- zettel" in brain.tasks[0].prompt
        and "- inbox" not in brain.tasks[0].prompt
    )


@pytest.mark.parametrize(
    ("folder", "conf"), [("a-folder-that-is-not-there", 0.95), ("zettel", 0.3), (None, 0.9), ("../..", 0.99)]
)
def test_a_bad_or_unsure_ai_answer_leaves_the_note_alone(app, monkeypatch, folder, conf):
    with_ai(app, monkeypatch, folder, conf)
    f = note(app, "inbox/idea.md", "# A thought about habits\n")
    sorter(app).run()
    app.jobs.run_next("bg")
    assert f.is_file() and "inbox/idea.md" in sorting.load(app)["waiting"]


def test_the_ai_is_asked_once_a_day_and_not_when_off(app, monkeypatch):
    brain = with_ai(app, monkeypatch, "zettel", 0.2)
    note(app, "inbox/idea.md", "# A thought\n")
    sorter(app).run()
    app.jobs.run_next("bg")
    assert sorter(app).run()["asked"] == 0 and len(brain.tasks) == 1
    app.settings.set("sorter.ai", False)
    note(app, "inbox/two.md", "# Another thought\n")
    assert sorter(app).run()["asked"] == 0


# ---------------------------------------------------------------------------------------------- learning and noticing
def test_a_note_you_move_yourself_teaches_it_and_is_left_alone(app):
    note(app, "inbox/vector-spaces.md", "# Vector spaces\nbasis and span\n---\n")
    note(app, "inbox/vector-bases.md", "# Vector bases\nbasis and span\n")
    sorter(app).run()  # no rule fits: both wait
    ws = Path(app.workspace)
    assert (ws / "inbox" / "vector-spaces.md").is_file()
    # the owner files one himself, and Kurooto sorts something by rule so it has a moved entry to watch
    st = sorting.load(app)
    f = ws / "inbox" / "vector-spaces.md"
    text = f.read_text()
    to = ws / "zettel" / "vector-spaces.md"
    to.write_text(text)
    f.unlink()
    st["moved"]["inbox/vector-spaces.md"] = {
        "from": "inbox/x.md", "sha": sorting.sha(text), "at": time.time() - 100, "n": 1, "by": "sorter",
        "keys": sorted(sorting.tokens("Vector spaces basis span")),
    }  # fmt: skip
    sorting.save(app, st)
    assert sorting.learn(app) == ["zettel/vector-spaces.md"]
    st = sorting.load(app)
    assert st["rules"][-1]["folder"] == "zettel" and sorting.sha(text) in st["pinned"]
    # a similar note now goes where he put the first
    similar = note(app, "inbox/vector-bases.md", "# Vector bases\nbasis and span\n")
    sorter(app).run()
    assert not similar.exists() and (ws / "zettel" / "vector-bases.md").is_file()


def test_a_moved_note_that_now_fits_elsewhere_moves_once_more_but_not_twice(app):
    note(app, "inbox/a.md", "---\nsubject: LA\n---\n# A\n")
    sorter(app).run()
    ws = Path(app.workspace)
    moved = ws / "linear-algebra" / "a.md"
    moved.write_text("---\nsubject: Topology\n---\n# A, now about topology\n")  # the note changed: it's about topology
    st = sorting.load(app)
    st["moved"]["linear-algebra/a.md"]["at"] = time.time() - 8 * 86400
    st["moved"]["linear-algebra/a.md"]["sha"] = "changed"
    sorting.save(app, st)
    out = sorter(app).run(force=True)
    assert (ws / "topology" / "a.md").is_file() and out["moved"] == [("linear-algebra/a.md", "topology/a.md")]
    # a month's wait before it can move again
    moved2 = ws / "topology" / "a.md"
    moved2.write_text("---\nsubject: LA\n---\n# back to algebra\n")
    app.settings.set("sorter.per_night", 99)
    assert sorting.recheck(app) == []


# ---------------------------------------------------------------------------------------------- the switch
def test_off_means_nothing_moves(app):
    note(app, "inbox/a.md", "---\nsubject: LA\n---\n# A\n")
    app.settings.set("modules.enabled", ["subjects"])
    before = snapshot(app)
    assert sorter(app).run()["moved"] == [] and snapshot(app) == before


def test_the_sorter_has_a_switch_a_help_entry_and_a_reason(app):
    from kurooto.core import calm, commands, tap

    assert "sorter" in [m for g in commands.GROUPS for m in g.modules]
    assert "sorter.summary" in calm.REASONS and "notes.sort" in tap.BY_ITSELF
    s = app.settings.get("sorter")
    assert {"folder", "per_night", "ai", "recheck", "learn", "min_conf", "settle_min", "at"} <= set(s)


def test_the_ring_message_gives_a_long_button_its_own_row():
    row = lambda extra: [  # noqa: E731
        [("Answer", {"url": "u"}), *[b for b in extra if len(str(b[0])) <= 10]],
        *[[b] for b in extra if len(str(b[0])) > 10],
    ]
    got = row([("Tomorrow morning", "chk:n:defer"), ("Skip", "chk:n:skip")])
    assert got == [[("Answer", {"url": "u"}), ("Skip", "chk:n:skip")], [("Tomorrow morning", "chk:n:defer")]]
