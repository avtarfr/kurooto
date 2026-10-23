"""A textbook filed from Classroom (0.6.1): a course's "Books" post with the textbook's PDF attached. Its concepts point
"Seen in" at a source note of its own (like a book's index note), not at the class note it was filed with, which used
to become a hub of hundreds of links; what was written before moves there at start, inside Kurooto's blocks only, with
before-copies. A fake AI answers; the rest is real."""

import json

from kurooto.modules import integrate as ig
from tests.unit.test_integrate import PAGES, USER_TEXT, answer, c_ad, world  # noqa: F401 (a fixture)

SUBJ = "deep-learning"
POST = f"sources/{SUBJ}/2026-08-05-books"
TITLE = "Wallace Hobbs Atmospheric Science"
SOURCE = f"sources/{SUBJ}/books/wallace-hobbs-atmospheric-science"
CONCEPT = "zettel/automatic-differentiation"


def textbook(pages: int = 90) -> str:
    """A long PDF's text as pdftotext writes it (a form feed between pages): the book's pages first, then filler."""
    rest = [
        f"Page {n}. The lapse rate and the hydrostatic balance are developed with worked examples." * 3
        for n in range(len(PAGES) + 1, pages + 1)
    ]
    return "\f".join([*PAGES.values(), *rest]) + "\f"


def file_textbook(env) -> dict:
    ws = env.app.workspace
    post = ws / f"{POST}.md"
    post.parent.mkdir(parents=True, exist_ok=True)
    post.write_text("# Books\n\nThe course follows these two books.\n", encoding="utf-8")
    key = env.integrate.queue_item("classroom", textbook(), SUBJ, TITLE, POST, date="2026-08-05")
    return env.integrate.items()[key]


def read_first_batch(env) -> None:
    env.fake_ai.answer = answer(c_ad(pages=[4, 5]))
    todo = env.integrate.ready_batches()
    assert todo[0][0]["title"] == TITLE
    env.integrate.submit_batch(*todo[0])
    assert env.app.jobs.run_next()


def test_class_material_or_a_textbook_by_length_and_title():
    k = ig.Integrate.kind_for
    pdf = lambda n: "\f".join(f"page {i}" for i in range(n))  # noqa: E731
    assert k("classroom", "Atmospheric Physics", pdf(120)) == "book"
    assert k("classroom", "Week 3", pdf(30)) == "class"
    assert k("classroom", "Lecture notes on convection", pdf(60)) == "class"  # the title says so
    assert k("classroom", "Atmospheric Physics 2nd edition", pdf(20)) == "book"
    assert k("classroom", "Slides", "--- slide 1 ---\na\n--- slide 2 ---\nb") == "class"
    assert k("classroom", "Notes", "word " * 40_000) == "class"  # 66 parts of about a page; the title says
    assert k("classroom", "Untitled", "word " * 40_000) == "book"  # 41 to 80 and the title doesn't say
    assert k("classroom", "Notes", "word " * 100_000) == "book"  # 166: a book whatever it's called
    assert k("handwritten", "Untitled", pdf(120)) == "class"  # only Classroom files can be textbooks


def test_a_textbooks_concepts_point_at_its_own_source_note_not_the_post_it_came_with(world):  # noqa: F811
    env = world
    item = file_textbook(env)
    assert item["kind"] == "book" and item["note"] == POST
    read_first_batch(env)
    ws = env.app.workspace
    concept = (ws / f"{CONCEPT}.md").read_text(encoding="utf-8")
    assert f"- [[{SOURCE}|{TITLE}]] pp. 1–" in concept and POST not in concept
    src = (ws / f"{SOURCE}.md").read_text(encoding="utf-8")
    assert f"# {TITLE}\n" in src and f"<!-- kurooto:source item={item['key']} -->" in src
    assert f"filed with [[{POST}|Books]]" in src and "## Concepts in this book" in src and f"[[{CONCEPT}|" in src
    post = (ws / f"{POST}.md").read_text(encoding="utf-8")
    assert "The course follows these two books." in post  # yours stays
    assert f"Textbook: [[{SOURCE}|{TITLE}]]" in post and CONCEPT not in post  # one line, not every concept
    assert json.loads((env.integrate.dir / "seen.json").read_text())[CONCEPT][0]["note"] == SOURCE


def test_what_was_written_before_moves_to_the_source_note_with_before_copies(world, monkeypatch):  # noqa: F811
    env = world
    item = file_textbook(env)
    # as 0.6.0 wrote it: Seen in points at the post, and the post lists every concept
    monkeypatch.setattr(ig.Integrate, "booklike", lambda self, b: False)
    read_first_batch(env)
    monkeypatch.undo()
    ws = env.app.workspace
    note = ws / f"{CONCEPT}.md"
    old = note.read_text(encoding="utf-8")
    assert f"[[{POST}|{TITLE}]]" in old
    # the user writes in the concept note, outside Kurooto's blocks
    note.write_text(old + USER_TEXT, encoding="utf-8")
    before = note.read_text(encoding="utf-8")
    data = env.integrate.load("items.json", {})
    for k in ("kind", "moved", "source_note"):
        data["items"][item["key"]].pop(k, None)
    env.integrate.save("items.json", data)
    assert f"## Concepts in {TITLE}" in (ws / f"{POST}.md").read_text(encoding="utf-8")

    assert env.integrate.migrate_booklike() == {"items": 1, "notes": 1}
    after = note.read_text(encoding="utf-8")
    assert f"[[{SOURCE}|{TITLE}]]" in after and POST not in after
    assert after.endswith(USER_TEXT)  # your text, as it was
    from kurooto.core import graphwrite as gw

    assert gw.outside(after) == gw.outside(before)
    post = (ws / f"{POST}.md").read_text(encoding="utf-8")
    assert f"Textbook: [[{SOURCE}|{TITLE}]]" in post and f"## Concepts in {TITLE}" not in post
    assert (ws / f"{SOURCE}.md").is_file()
    undo = json.loads((env.integrate.dir / "undo" / f"{SUBJ}-{item['id']}-moved.json").read_text())
    assert undo[str(note)] == before and undo[str(ws / f"{SOURCE}.md")] is None
    it = env.integrate.items()[item["key"]]
    assert it["kind"] == "book" and it["moved"] and it["source_note"] == SOURCE
    assert env.integrate.migrate_booklike() == {"items": 0, "notes": 0}  # once


def test_a_lecture_file_stays_class_material_and_its_note_lists_its_concepts(world):  # noqa: F811
    env = world
    from tests.unit.test_integrate_sources import LECTURE, file_batch, slides

    got = file_batch(env, slides())
    item = env.integrate.items()[got.pop()]
    assert item["kind"] == "class" and not env.integrate.booklike(item)
    assert env.integrate.stub(item) == env.app.workspace / f"{LECTURE}.md"
