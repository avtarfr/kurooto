"""The concept graph reads more than books (0.5.19): Classroom files filed into the notes and, when chosen, handwritten
notes, in one queue with the books and one night's budget. A fake AI answers; the rest is real: the queue and its
order, the read-once hashes, the batches, the checks, the writes and /graph."""

import json

from kurooto.core.state import jsave
from kurooto.modules import integrate as ig
from kurooto.modules.handwritten import END, START_LINE
from kurooto.providers.base import Result, Verdict
from tests.unit.test_integrate import PAGES, answer, c_ad, run_all, world  # noqa: F401 (a fixture)

SUBJ = "deep-learning"
LECTURE = f"sources/{SUBJ}/2026-10-20-lecture-8-automatic-differentiation"
FILLER = (
    "These slides go with lecture 8. The exercises at the end ask for the gradient of a small two-layer network by "
    "hand, then with a library, and compare the two answers line by line.\n\n"
)


def slides(extra: str = "") -> str:
    """A class file's text as Classroom writes out a .pptx: the book's pages as slides, enough to be read."""
    body = "".join(f"--- slide {n} ---\n{t}\n\n" for n, t in PAGES.items())
    return body + f"--- slide 7 ---\n{FILLER * 8}{extra}"


def file_batch(env, text: str, post: str = "Lecture 8: automatic differentiation", name: str = "Lecture 8 slides"):
    """Classroom → notes as it files a batch: the file downloaded (and its text beside it), the batch the AI filed,
    and the lecture note the AI wrote for the post. Returns what filing it queued into the graph."""
    app = env.app
    cn = app.modules["classroom_notes"]
    rel = f"{SUBJ}/2026-10-20-{name.lower().replace(' ', '-')}-abc123.pptx"
    f = cn.files_dir / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"pptx")
    f.with_name(f.name + ".txt").write_text(text, encoding="utf-8")
    item = {
        "kind": "material",
        "title": post,
        "date": "2026-10-20",
        "text": "Slides for today.",
        "files": [{"title": f"{name}.pptx", "link": "https://drive.example/x", "file": rel, "chars": len(text)}],
        "links": [],
    }
    data = {"course": "Deep Learning (DL 301)", "folder": SUBJ, "items": [item], "not_interested": 0}
    n = len(list((cn.dir / "batches").glob("*.json"))) if (cn.dir / "batches").is_dir() else 0
    jsave(cn.dir / "batches" / f"b{n}.json", data)
    lec = app.workspace / f"{LECTURE}.md"
    if not lec.exists():
        lec.parent.mkdir(parents=True, exist_ok=True)
        lec.write_text("# Lecture 8: automatic differentiation\n\n## Covered\nSlides.\n", encoding="utf-8")
    before = set(env.integrate.items())
    cn._filed(None, Result(Verdict.OK, "Filed."), {"batch": f"b{n}.json"})
    return set(env.integrate.items()) - before


def class_ready(env):
    return [(b, bt) for b, bt in env.integrate.ready_batches() if b.get("source") == "classroom"]


# ------------------------------------------------------------------------------------------------ Classroom
def test_a_class_file_is_read_once_into_concept_notes_seen_in_its_lecture_note(world):  # noqa: F811
    env = world
    got = file_batch(env, slides())
    assert len(got) == 1
    item = env.integrate.items()[got.pop()]
    assert item["note"] == LECTURE and item["subject"] == SUBJ and item["title"] == "Lecture 8 slides"
    # newest class material goes before the book that was waiting
    todo = env.integrate.ready_batches()
    assert todo[0][0]["source"] == "classroom" and todo[-1][0]["id"] == "bishop"
    env.fake_ai.answer = answer(c_ad(pages=[4, 5]))
    assert env.integrate.tick() == {"submitted": 1}
    run_all(env)
    prompt = json.dumps(env.fake_ai.requests[0])
    assert "Course material: Lecture 8 slides" in prompt and "slides" in prompt and "Bishop" not in prompt
    ws = env.app.workspace
    new = (ws / "zettel" / "automatic-differentiation.md").read_text(encoding="utf-8")
    assert f"- [[{LECTURE}|Lecture 8 slides]] slides 1–7" in new  # Seen in: the note it was filed into
    assert "Source: Lecture 8 slides, slides 1–7" in new
    lec = (ws / f"{LECTURE}.md").read_text(encoding="utf-8")
    assert "## Covered\nSlides." in lec  # what was there stays
    assert "## Concepts in Lecture 8 slides\n[[zettel/automatic-differentiation]]" in lec
    led = env.integrate.load("ledger.json", {})
    assert led["items"][item["key"]]["batches"]["1-7"]["state"] == "done"
    assert list(led["books"]) == ["deep-learning/bishop"]  # the book came next, in the same queue, kept as before
    # the same file filed again (downloaded again, a new batch) isn't read again; an edited one is
    assert file_batch(env, slides()) == set()
    assert class_ready(env) == []
    edited = file_batch(env, slides("Added after class: the reverse sweep stores every intermediate value."))
    assert len(edited) == 1 and len(class_ready(env)) == 1


def test_a_short_announcement_or_post_is_not_queued(world):  # noqa: F811
    env = world
    assert file_batch(env, "Midterm on Nov 5, 10:00 in LH-1.\n", post="Midterm", name="Notice") == set()
    assert class_ready(env) == []


def test_without_classroom_in_the_sources_nothing_is_queued_from_it(world):  # noqa: F811
    env = world
    env.app.settings.set("integrate.sources", ["books"])
    assert file_batch(env, slides()) == set()
    assert env.integrate.backfill_classroom() == (0, 0)
    assert 'add "classroom" to integrate.sources' in env.say("/graph backfill classroom")
    # and with no books in it, a book waits too (nothing is read)
    env.app.settings.set("integrate.sources", [])
    assert env.integrate.ready_batches() == [] and env.integrate.tick().get("idle")


def test_a_class_file_with_no_lecture_note_points_at_the_course_page(world):  # noqa: F811
    env = world
    key = env.integrate.queue_item("classroom", slides(), SUBJ, "Handout", env.integrate.source_note(SUBJ, "Handout"))
    assert env.integrate.items()[key]["note"] == f"maps/courses/{SUBJ}"


def test_a_lecture_note_is_found_by_the_file_it_lists(world):  # noqa: F811
    env = world
    ws = env.app.workspace
    note = ws / "sources" / SUBJ / "2026-10-19-week-8.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("# Week 8\n\n## Files\n- [Lecture 8 slides.pptx](https://drive.example/x)\n", encoding="utf-8")
    other = ws / "sources" / SUBJ / "2026-10-21-week-9.md"
    other.write_text("# Week 9\n\n## Files\n- [Lecture 80 notes.pdf](https://drive.example/y)\n", encoding="utf-8")
    assert env.integrate.source_note(SUBJ, "", "", ["Lecture 8 slides"]) == f"sources/{SUBJ}/2026-10-19-week-8"


# ------------------------------------------------------------------------------------------------- backfill
def backfill_world(env):
    """Classroom files filed before 0.5.19, as they lie in Kurooto's data folder: two courses."""
    cn = env.app.modules["classroom_notes"]
    jsave(cn.dir / "folders.json", {"Deep Learning (DL 301)": SUBJ, "Topology (MTH 310)": "topology"})
    files = {
        f"{SUBJ}/2026-09-02-lecture-1-a1b2c3.pdf": FILLER * 12 + "Lecture one.",
        f"{SUBJ}/2026-09-09-lecture-2-d4e5f6.pdf": FILLER * 12 + "Lecture two.",
        f"{SUBJ}/2026-09-10-notice-g7h8i9.pdf": "Room change.",  # too short: never read
        "topology/2026-08-20-open-sets-j1k2l3.txt": FILLER * 12 + "Open sets.",
    }
    for rel, text in files.items():
        f = cn.files_dir / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix == ".txt":
            f.write_text(text, encoding="utf-8")
        else:
            f.write_bytes(b"%PDF")
            f.with_name(f.name + ".txt").write_text(text, encoding="utf-8")
    (cn.files_dir / SUBJ / "2026-09-11-photo-m1n2o3.png").write_bytes(b"png")  # no text: left alone


def test_backfill_queues_what_was_filed_before_oldest_course_first_within_the_budget(world):  # noqa: F811
    env = world
    backfill_world(env)
    out = env.say("/graph backfill classroom")
    assert out.startswith("Queued 3 Classroom files from 2 courses, the oldest course first."), out
    order = [(it["subject"], it["title"]) for it in env.integrate.queued_items()]
    assert order == [("topology", "Open sets"), (SUBJ, "Lecture 1"), (SUBJ, "Lecture 2")]
    assert env.integrate.backfill_classroom() == (0, 0)  # again: nothing new
    # something filed from now on goes before the backfill
    file_batch(env, slides())
    assert env.integrate.queued_items()[0]["title"] == "Lecture 8 slides"
    # one night's budget: one batch, then it waits for the next night
    env.app.settings.set("integrate.per_night", 1)
    env.fake_ai.answer = answer()
    assert env.integrate.tick() == {"submitted": 1}
    run_all(env)
    assert env.integrate.tick().get("limit") == "per_night"
    assert len(class_ready(env)) == 3


def test_the_card_has_a_switch_per_source_and_the_backfill(world, monkeypatch):  # noqa: F811
    env = world
    backfill_world(env)
    on = env.app.is_on  # Classroom → notes needs Google's OK to be on: here it just is
    monkeypatch.setattr(env.app, "is_on", lambda mid: mid == "classroom_notes" or on(mid))
    card = env.integrate.card()
    ids = {t["id"]: t for t in card["toggles"]}
    assert ids["source:books"]["on"] and ids["source:classroom"]["on"] and not ids["source:handwritten"]["on"]
    assert not ids["backfill:classroom"]["on"]
    assert env.integrate.card_action("backfill:classroom", True).startswith("Queued 3 Classroom files")
    assert env.integrate.card()["toggles"][-1]["disabled"]
    env.integrate.card_action("source:handwritten", True)
    assert env.app.settings.get("integrate.sources") == ["books", "classroom", "handwritten"]


# ----------------------------------------------------------------------------------------------- handwritten
def handwritten_note(env, text: str):
    note = env.app.workspace / "handwritten" / "2026-10-21-phase-change.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(f"# Phase change\n\n{START_LINE}\n{text}\n{END}\n\nMy own line.\n", encoding="utf-8")
    return note


def test_handwritten_notes_are_read_only_when_chosen(world):  # noqa: F811
    env = world
    note = handwritten_note(env, FILLER * 8)
    linker = env.app.modules["handwritten"].linker
    got = {"title": "Phase change", "subject": SUBJ, "day": "2026-10-21"}
    linker.to_graph(note, got)
    assert env.integrate.items() == {}  # not in integrate.sources by default
    env.app.settings.set("integrate.sources", ["books", "classroom", "handwritten"])
    linker.to_graph(note, {**got, "subject": ""})  # no subject: no place for its concept notes
    assert env.integrate.items() == {}
    linker.to_graph(note, got)
    (item,) = env.integrate.items().values()
    assert item["source"] == "handwritten" and item["note"] == "handwritten/2026-10-21-phase-change"
    assert "My own line." not in (env.integrate.dir / "texts" / f"{item['id']}.txt").read_text(encoding="utf-8")
    linker.to_graph(note, got)  # linked again (/handwritten link): the same text isn't read twice
    assert len(env.integrate.items()) == 1
    env.fake_ai.answer = answer()
    env.integrate.tick()
    run_all(env)
    assert "Handwritten notes: Phase change" in json.dumps(env.fake_ai.requests[0])


# ------------------------------------------------------------------------------------------------- /graph
def test_graph_shows_the_queue_split_by_source(world):  # noqa: F811
    env = world
    file_batch(env, slides())
    file_batch(env, slides("A second file."), name="Lecture 8 notes")
    env.app.settings.set("integrate.sources", ["books", "classroom", "handwritten"])
    env.integrate.take_handwritten(handwritten_note(env, FILLER * 8), SUBJ, "Phase change")
    out = env.say("/graph")
    assert "Waiting to be read: 1 book, 2 class files, 1 handwritten." in out, out
    assert "Reads: books, classroom, handwritten (integrate.sources)." in out


def test_pages_of_a_text_pdf_pages_slides_or_parts():
    pages, unit = ig.split_pages("one\fthree\f\f")
    assert unit == "pages" and pages == {1: "one", 2: "three"}
    pages, unit = ig.split_pages("--- slide 1 ---\nA\n\n--- slide 2 ---\nB")
    assert unit == "slides" and pages == {1: "A", 2: "B"}
    pages, unit = ig.split_pages(("word " * 300 + "\n\n") * 5)
    assert unit == "parts" and len(pages) == 5 and all(len(p) <= 2 * ig.PART_CHARS for p in pages.values())
    assert ig.text_hash("a  b\n") == ig.text_hash("a b")
