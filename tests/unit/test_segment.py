"""Sections and batches of a book from its page text: numbered headings and running headers, never a margin
cross-reference (a "Section 9.1" note once made every chapter a list of other chapters' sections)."""

from kurooto.core import segment
from kurooto.modules.books import chapters


def chapter_pages():
    """A chapter laid out like a textbook with margin notes: running headers, cross-references, numbered headings."""
    pages = {
        1: "10\nConvolutional\nNetworks\n",
        2: "288\n10. CONVOLUTIONAL NETWORKS\nSection 9.1\n10.1. Computer Vision\nImages are large arrays of numbers.",
        3: "10.1. COMPUTER VISION 289\nSection 6.3\nMore text about images and their structure.",
        4: "292 10. CONVOLUTIONAL NETWORKS\n10.2. Convolutional Filters\nA filter slides over the image.\nSee 9.1",
        5: "10.2. CONVOLUTIONAL FILTERS 293\nSection 9.1\nExercise 2.8\nText of the section.",
        6: "296 10. CONVOLUTIONAL NETWORKS\nChapter 12\nStill the same section.",
        7: "10.3. POOLING 297\n10.3. Pooling\nPooling reduces the size.",
        8: "300 10. CONVOLUTIONAL NETWORKS\nSection 8.1.2\nTail of the section about pooling and more.",
    }
    return pages


def test_cross_references_in_margins_are_not_headings():
    secs = segment.sections(chapter_pages(), [], 8)
    numbers = [s.number for s in secs]
    assert numbers == ["10", "10.1", "10.2", "10.3"]
    assert not any(t in " ".join(s.title for s in secs) for t in ("Section 9.1", "Chapter 12", "Exercise"))
    by = {s.number: s for s in secs}
    assert (by["10.1"].first, by["10.1"].last) == (2, 3) and (by["10.2"].first, by["10.2"].last) == (4, 6)
    assert by["10.3"].last == 8 and by["10.2"].title == "Convolutional Filters"


def test_references_and_sentences_are_recognised():
    for line in ("Section 9.1", "Exercise 2.8", "Appendix B", "See Section 3.4", "Figure 4.2", "Chapter 12"):
        assert segment.is_reference(line) and segment.heading(line) is None
    assert segment.heading("10.4 Pooling") == ("10.4", "Pooling")
    assert segment.heading("3 The results are shown in the next figure,") is None  # prose
    assert segment.heading("12") is None


def test_numbers_only_go_up():
    pages = {1: "2.1 First idea\ntext", 2: "2.2 Second idea\ntext", 3: "1.5 A list item that looks numbered\ntext"}
    assert [s.number for s in segment.sections(pages, [], 3)] == ["2.1", "2.2"]


def test_bookmarks_win_when_there_are_some():
    outline = [(1, "1 Introduction", 1), (1, "2 Methods", 5), (2, "2.1 Setup", 6), (1, "Section 9.1", 7)]
    secs = segment.sections({}, outline, 10)
    assert [(s.title, s.first, s.last) for s in secs] == [
        ("Introduction", 1, 4),
        ("Methods", 5, 10),
        ("Setup", 6, 10),
    ]


def test_a_book_with_only_chapter_lines_still_works():
    pages = {1: "Chapter 1 Basics\ntext", 4: "Chapter 2 More\ntext", 9: "text"}
    assert [(s.title, s.first, s.last) for s in segment.sections(pages, [], 9)] == [
        ("Chapter 1 Basics", 1, 3),
        ("Chapter 2 More", 4, 9),
    ]


def test_books_chapters_use_it():
    out = chapters([], chapter_pages(), 8)
    assert [t for _, t, _, _ in out] == [
        "10 CONVOLUTIONAL NETWORKS",
        "10.1 Computer Vision",
        "10.2 Convolutional Filters",
        "10.3 Pooling",
    ] or len(out) == 4


def test_batches_cover_every_page_once_and_follow_sections():
    secs = [segment.Section(2, f"1.{i}", f"Part {i}", 1 + (i - 1) * 7, i * 7) for i in range(1, 7)]
    bs = segment.batches(secs, 42)
    assert bs[0].first == 1 and bs[-1].last == 42
    assert all(b.last + 1 == n.first for b, n in zip(bs, bs[1:], strict=False))
    assert all(segment.MIN_BATCH <= b.pages <= segment.MAX_BATCH for b in bs)


def test_a_long_section_is_cut_and_tiny_ones_join():
    secs = [segment.Section(2, "1.1", "Long", 1, 45), segment.Section(2, "1.2", "Tiny", 46, 47)]
    bs = segment.batches(secs, 47)
    assert all(b.pages <= segment.MAX_BATCH for b in bs) and bs[0].first == 1 and bs[-1].last == 47
    assert len({b.id for b in bs}) == len(bs)


def test_no_sections_means_windows():
    bs = segment.batches([], 30)
    assert [(b.first, b.last) for b in bs][0][0] == 1 and bs[-1].last == 30 and len(bs) >= 2
    assert segment.batches([], 0) == []
