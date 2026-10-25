"""0.8.0: copies among your notes: the detector, the garden's pass over all notes, and the sorter's question."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from kurooto.core import dupes, notedupes, sorting

BASE = " ".join(f"entropy{i} measures disorder of state {i % 7} in a closed system" for i in range(14))
OLD = time.time() - 3600


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["subjects", "sorter"])
    a.settings.set("sorter.ai", False)
    ws = Path(a.workspace)
    for d in ("physics", "zettel", "inbox"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    told = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: told.append((text, kw)))
    a.told = told
    a.modules["sorter"].start()
    yield a
    a.close()


def note(app, rel, text, age=3600):
    f = Path(app.workspace) / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    os.utime(f, (time.time() - age, time.time() - age))
    return f


# -------------------------------------------------------------------------------------------------- detector
def test_detector_exact_near_and_different():
    other = " ".join(f"quite another{i} subject about rivers {i}" for i in range(20))
    assert dupes.compare(BASE, BASE.upper()) == ("exact", 1.0)
    assert dupes.compare(BASE, "---\ntitle: x\n---\n[[a|" + BASE.split()[0] + "]] " + " ".join(BASE.split()[1:])) == (
        "exact",
        1.0,
    )  # markup and front matter don't count
    kind, score = dupes.compare(BASE, BASE + " plus one more sentence about heat engines and so on")
    assert kind == "near" and 0.85 <= score < 1
    assert dupes.compare(BASE, other) is None
    assert dupes.compare("too short to matter", "too short to matter") is None  # under 25 words: not copies of anything


def test_scan_finds_each_pair_once_exact_first():
    notes = {
        "a.md": BASE,
        "b.md": BASE.upper(),
        "c.md": BASE + " and a tail that was added later by hand here",
        "d.md": "x " * 40,
    }
    pairs = dupes.scan(notes)
    assert [(p.a, p.b, p.kind) for p in pairs][0] == ("a.md", "b.md", "exact")
    assert {p.key for p in pairs} == {"a.md|b.md", "a.md|c.md", "b.md|c.md"}
    ix = dupes.Index()
    for k, v in notes.items():
        ix.add(k, v)
    assert [n for n, _, _ in ix.near(BASE, exclude="a.md")][:1] == ["b.md"]
    ix.remove("b.md")
    assert "b.md" not in [n for n, _, _ in ix.near(BASE, exclude="a.md")]


# ---------------------------------------------------------------------------------------- the garden's pass
def test_garden_pass_covers_all_notes_including_old_ones(app):
    app.settings.set("integrate.duplicates_all", True)
    note(app, "physics/entropy.md", BASE, age=900 * 86400)  # years old
    note(app, "zettel/entropy-copy.md", BASE.upper(), age=3600)
    note(app, "zettel/rivers.md", " ".join(f"river{i} flows to the sea {i}" for i in range(30)))
    text = notedupes.night(app)
    assert "physics/entropy.md" in text and "zettel/entropy-copy.md" in text and "the same words" in text
    t, kw = app.told[-1]
    assert kw["why"] == "integrate.duplicates" and kw["buttons"][0][0][1].startswith("ndup:")
    assert notedupes.night(app) == ""  # one question a day
    assert len(notedupes.scan(app, per_day=5)) == 0  # asked: not again for two weeks
    assert len(notedupes.scan(app, per_day=5, again=True)) == 1


def test_garden_per_day_and_switch(app):
    for i in range(5):
        body = f"topic number {i} " + " ".join(f"unique{i}word{j} about thing {j}" for j in range(20))
        note(app, f"physics/a{i}.md", body)
        note(app, f"zettel/b{i}.md", body)
    assert len(notedupes.scan(app)) == 3  # integrate.duplicates_per_day
    app.settings.set("integrate.duplicates_per_day", 5)
    assert len(notedupes.scan(app)) == 5
    app.settings.set("integrate.duplicates_all", False)
    assert notedupes.night(app) == ""


def test_merge_keeps_everything_and_undoes(app):
    a = note(app, "physics/entropy.md", BASE)
    extra = "\n\nA line only the copy has: entropy never decreases in an isolated system overall."
    b = note(app, "zettel/entropy-copy.md", BASE + extra)
    pair = notedupes.scan(app)[0]
    text, buttons = notedupes.ask(app, [pair])
    pid = buttons[0][0][1].split(":")[1]
    said = notedupes.merge(app, pid)
    assert said.startswith("Merged")
    na, nb = a.read_text(), b.read_text()
    assert "## Merged from [[zettel/entropy-copy]]" in na and "only the copy has" in na  # nothing lost
    assert (
        nb.startswith("<!-- kurooto:merged-into [[physics/entropy]] -->") and "only the copy has" in nb
    )  # its own text stays
    assert notedupes.merge(app, pid).startswith("Not merged")  # already merged
    assert notedupes.scan(app, again=True) == []  # a redirect isn't compared again
    assert notedupes.undo(app, pid) == "Put back." and a.read_text() == BASE and b.read_text() == BASE + extra
    assert notedupes.undo(app, pid).startswith("There's nothing")
    assert notedupes.scan(app, again=True) == []  # undone: not asked again


def test_undo_leaves_a_file_you_changed(app):
    a = note(app, "physics/entropy.md", BASE)
    note(app, "zettel/entropy-copy.md", BASE.upper())
    _, buttons = notedupes.ask(app, notedupes.scan(app))
    pid = buttons[0][0][1].split(":")[1]
    notedupes.merge(app, pid)
    (Path(app.workspace) / "zettel/entropy-copy.md").write_text("I rewrote this since", encoding="utf-8")
    out = notedupes.undo(app, pid)
    assert "you changed it since" in out and "zettel/entropy-copy.md" in out and a.read_text() == BASE


def test_keep_both_is_never_asked_again(app):
    note(app, "physics/entropy.md", BASE)
    note(app, "zettel/entropy-copy.md", BASE.upper())
    _, buttons = notedupes.ask(app, notedupes.scan(app))
    pid = buttons[0][1][1].split(":")[1]
    assert notedupes.button(app, pid, "keep").startswith("Kept both")
    assert notedupes.scan(app, again=True) == []


# --------------------------------------------------------------------------------------------- the sorter
def test_sorter_asks_about_a_copy_instead_of_filing_it(app):
    note(app, "physics/entropy.md", BASE)
    note(app, "inbox/entropy-new.md", BASE.upper())
    out = app.modules["sorter"].run(force=True)
    assert out["moved"] == [] and (Path(app.workspace) / "inbox/entropy-new.md").exists()  # not filed
    t, kw = next((t, kw) for t, kw in app.told if "copy of physics/entropy.md" in t)
    acts = [b[1].split(":")[2] for row in kw["buttons"] for b in row]
    assert acts == ["keep", "merge", "skip"]
    assert (
        app.modules["sorter"].run(force=True)["asked"] == 0 and len([1 for t, _ in app.told if "copy of" in t]) == 1
    )  # asked once


def test_sorter_keep_both_files_it_normally_and_skip_leaves_it(app):
    note(app, "physics/entropy.md", BASE)
    f = note(app, "inbox/entropy-new.md", "---\ntitle: entropy\nsubject: physics\n---\n" + BASE.upper())
    app.modules["sorter"].run(force=True)
    kw = next(kw for t, kw in app.told if "copy of" in t)
    ref = kw["buttons"][0][0][1].split(":")[1]
    app.modules["sorter"]._button(ref, "skip")  # noqa: SLF001
    assert f.exists() and app.modules["sorter"].run(force=True)["moved"] == []  # left where it is, not asked again
    assert sum(1 for t, _ in app.told if "copy of" in t) == 1


def test_sorter_merge_and_undo(app):
    a = note(app, "physics/entropy.md", BASE)
    extra = " and only this copy says heat flows hot to cold"
    f = note(app, "inbox/entropy-new.md", BASE + extra)
    app.modules["sorter"].run(force=True)
    kw = next(kw for t, kw in app.told if "copy of" in t)
    ref = kw["buttons"][0][0][1].split(":")[1]
    said = app.modules["sorter"]._button(ref, "merge")  # noqa: SLF001
    assert "Merged" in said and "hot to cold" in a.read_text() and f.read_text().startswith("<!-- kurooto:merged-into")
    assert app.modules["sorter"].run(force=True)["moved"] == []  # a redirect isn't sorted
    undo_kw = app.told[-1][1]
    assert undo_kw["buttons"][0][0][1].endswith(":undo")
    assert app.modules["sorter"]._button(ref, "undo") == "Put back."  # noqa: SLF001
    assert a.read_text() == BASE and f.read_text() == BASE + extra


def test_sorter_switch_and_non_copies(app):
    note(app, "physics/entropy.md", BASE)
    note(
        app,
        "inbox/rivers.md",
        "---\nsubject: physics\n---\n" + " ".join(f"river{i} flows to the sea {i}" for i in range(30)),
    )
    app.modules["sorter"].run(force=True)
    assert not [1 for t, _ in app.told if "copy of" in t]  # a different note is just sorted
    app.settings.set("sorter.duplicates", False)
    note(app, "inbox/entropy-new.md", "---\nsubject: physics\n---\n" + BASE.upper(), age=OLD)
    app.modules["sorter"].run(force=True)
    assert not [1 for t, _ in app.told if "copy of" in t]  # off: as before
    _ = sorting
