"""Study packs pick a book's chapters by headings and citations, not scattered words (0.9.0, N14): a pack on several
variables took the chapter on series of functions, which mentions the words more often, instead of the one titled for
them. Synthetic page texts only."""

import json
import zipfile
from pathlib import Path

from kurooto.core import studypack

TOPICS = ["functions of several variables", "differentiation", "inverse function theorem", "implicit function theorem"]


def analysis_book(numbered: bool = False) -> list[str]:
    """A 60-page analysis book: chapter 7 (series of functions) says the topics' words on every page, chapter 9 (several
    variables) has them in its title and section headings and seldom in its text. numbered: no "Chapter N" headings,
    only numbered items (7.1 Definition ...), as many books' text comes out."""
    pages = ["Preface. This book is about analysis."] * 2
    body7 = (
        "Differentiation of a sequence of functions needs care: differentiation term by term fails. The inverse "
        "function of a limit, differentiation again, functions of several kinds."
    )
    for i in range(20):  # pages 3-22
        head = ("Chapter 7\nSEQUENCES AND SERIES OF FUNCTIONS\n" if not numbered else "") if i == 0 else ""
        if i == 6:
            head = "UNIFORM CONVERGENCE AND DIFFERENTIATION\n"
        item = f"7.{i + 1} Theorem Let f be a function.\n" if numbered else ""
        pages.append(f"SEQUENCES AND SERIES OF FUNCTIONS {100 + i}\n{head}{item}{body7}")
    for i in range(16):  # pages 23-38
        head = "Chapter 8\nSOME SPECIAL FUNCTIONS\n" if i == 0 and not numbered else ""
        item = f"8.{i + 1} Definition A power series.\n" if numbered else ""
        extra = " Power series converge; power series again." if i == 4 else ""
        pages.append(f"SOME SPECIAL FUNCTIONS {120 + i}\n{head}{item}Exponential and trigonometric.{extra}")
    heads9 = {0: "LINEAR TRANSFORMATIONS", 4: "DIFFERENTIATION", 8: "THE INVERSE FUNCTION THEOREM"}
    heads9[12] = "THE IMPLICIT FUNCTION THEOREM"
    for i in range(20):  # pages 39-58
        head = "Chapter 9\nFUNCTIONS OF SEVERAL VARIABLES\n" if i == 0 and not numbered else ""
        sec = heads9.get(i, "")
        item = f"9.{i + 1} Definition Let E be open.\n" if numbered else ""
        pages.append(f"FUNCTIONS OF SEVERAL VARIABLES {140 + i}\n{head}{sec}\n{item}Let A be a linear map of R^n.")
    pages += ["INDEX\nfunction, 1; differentiation, 2; inverse function, 3", "Bibliography"]
    return pages


def source(tmp_path: Path, pages: list[str], name: str = "Principles of Analysis") -> studypack.Source:
    d = tmp_path / name
    (d / "pages").mkdir(parents=True)
    for i, text in enumerate(pages, 1):
        (d / "pages" / f"{i:05d}.md").write_text(text, encoding="utf-8")
    return studypack.Source(Path(tmp_path / f"{name}.pdf"), name, len(pages), d, is_class=False)


def test_a_phrase_finds_its_words_with_small_words_between():
    rx = studypack.pattern(studypack.topics_of("functions of several variables to the end"))
    assert studypack.hits(rx, "Chapter 9: Functions of Several Variables") == 1


def test_the_chapter_named_for_the_topic_wins_over_one_that_says_its_words_more(tmp_path):
    for numbered in (False, True):
        s = source(tmp_path / str(numbered), analysis_book(numbered))
        rx = studypack.pattern(TOPICS)
        texts = s.page_texts()
        assert sum(studypack.hits(rx, texts[p - 1]) for p in range(3, 23)) > 2 * sum(
            studypack.hits(rx, texts[p - 1]) for p in range(39, 59)
        )  # chapter 7 says the words far more often
        why: list[str] = []
        t0, t1, t2 = studypack.book_tiers(s, rx, [], why=why)
        pages = set(t0 + t1 + t2)
        assert set(range(39, 59)) <= set(t1)  # chapter 9, whole
        assert not pages & set(range(3, 23)), numbered  # nothing of chapter 7
        assert any(x.startswith("chapter 9") and "headings name" in x and "(whole)" in x for x in why), why
        assert any(x.startswith("not chapter 7") for x in why), why
        assert any("outside these chapters, left out" in x for x in why), why


def test_a_topic_no_chosen_chapter_names_still_gets_its_pages(tmp_path):
    s = source(tmp_path, analysis_book())
    pages = studypack.book_pages(s, studypack.pattern([*TOPICS, "power series"]))
    assert {26, 27, 28} <= set(pages)  # chapter 8's page on power series, with a page either side
    assert not set(pages) & set(range(3, 23))


def test_the_class_citing_a_chapter_counts_for_it(tmp_path):
    s = source(tmp_path, analysis_book())
    rx = studypack.pattern(["power series"])  # only chapter 8's text says it; the class cites chapter 7
    choice = studypack.choose_chapters(s, s.page_texts(), rx, cited=set(range(3, 6)))
    assert [c.num for c in choice.chosen] == ["7"] and choice.chosen[0].cited


def test_bookmarks_give_the_chapters_when_books_has_them(tmp_path):
    s = source(tmp_path, analysis_book())
    s.chapters = [
        [1, "7 Sequences and Series of Functions", 3, 22],
        [2, "Uniform Convergence and Differentiation", 9, 10],
        [1, "8 Some Special Functions", 23, 38],
        [1, "9 Functions of Several Variables", 39, 58],
        [2, "The Inverse Function Theorem", 47, 50],
    ]
    t0, t1, t2 = studypack.book_tiers(s, studypack.pattern(TOPICS), [])
    assert set(range(39, 59)) <= set(t1) and not set(t0 + t1 + t2) & set(range(3, 23))


def test_a_book_without_chapters_is_picked_by_its_words_as_before(tmp_path):
    pages = ["x"] * 30
    pages[9] = "differentiation and differentiation"
    s = source(tmp_path, pages)
    why: list[str] = []
    assert studypack.book_tiers(s, studypack.pattern(["differentiation"]), [], why=why)[2] == [10, 9, 11]
    assert why == []


def test_the_index_says_which_chapters_were_taken_and_why(env):
    app = env.app
    env.on("subjects")
    env.say("/subject add Analysis Two (an)")
    src = app.workspace.parent / "pdfs"
    src.mkdir()
    d = app.paths.data / "book-text" / "analysis-two" / "analysis"
    (d / "pages").mkdir(parents=True)
    for i, text in enumerate(analysis_book(), 1):
        (d / "pages" / f"{i:05d}.md").write_text(text, encoding="utf-8")
    (src / "Principles of Analysis.pdf").write_bytes(b"%PDF book")
    meta = {"file": str(src / "Principles of Analysis.pdf"), "title": "Principles of Analysis", "pages": 60}
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    path, info = studypack.build(app, "analysis-two", "Analysis Two", topics=TOPICS)
    with zipfile.ZipFile(path) as z:
        index = z.read("INDEX.md").decode()
        book = z.read("books/principles-of-analysis-pages.md").decode()
    assert "## Chapters taken from the books, and why" in index
    assert "- Principles of Analysis: chapter 9 (FUNCTIONS OF SEVERAL VARIABLES), pages 39-58 (whole)" in index
    assert "- Principles of Analysis: not chapter 7" in index
    assert "<!-- page 39 -->" in book and "<!-- page 5 -->" not in book
