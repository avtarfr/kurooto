"""Study packs and a syllabus's readings (0.8.13): its abbreviations ("B&D: Brockwell & Davis (Third Ed., 2016)"), a
table with a column per book and codes under them (C3, S2.3, D1.11, E3.2.2, C3 P1, SA.3), inline citations, each
matched to a book by its authors and turned into that book's pages; cited pages first, past the usual 250-page limit
up to studypack.cited_pages; another subject's notes kept out. Synthetic page texts only."""

import json
import zipfile
from pathlib import Path

from kurooto.core import studypack

SYLLABUS = """Time Series Analysis: syllabus
Abbreviations
B&D: Brockwell & Davis (Third Ed., 2016). S&S: Shumway & Stoffer (Fifth Ed., 2025). BJR&L: Box, Jenkins,
Reinsel & Ljung (Fifth Ed., 2016). C: Chapter, S: Section, D: Definition, P: Paragraph, E: Example.

Models of stationary TS data
 Topic Discussed                                                     B&D         S&S           BJR&L
 Backshift, forward shift and difference operators                   S1.5.1.1    S2.2          S1.2
 Linear filter/process model                                         S2.2        D1.11         S1.2
 AR(p) model, AR(p) as linear filter/process                         C3          C3            S1.2
 ARMA(p, q) model definition                                         S2.3, C3    C3            S1.2
 ARIMA(p, d, q) model definition                                     S6.1        C3            S1.2
Mean-0 AR(p) parameter estimation
 Theoretical autocovariance/correlation functions: Yule-Walker eq.   S5.1.1      S3.5
 Multivariate normal PDF: A refresher                                SA.3
 Theoretical autocovariance & autocorrelation functions              E3.2.2      S3.3
 Paradigm 2: Deal with non-stationary data directly through                      C3 P1         S1.2
"""


def codes(cited):
    return {(c.abbr, c.kind, c.num, c.label) for c in cited}


def test_a_syllabus_table_gives_each_books_codes_from_its_own_column():
    cited = studypack.citations([SYLLABUS])
    got = codes(cited)
    assert got == {
        ("B&D", "section", "1.5.1.1", ""),
        ("B&D", "section", "2.2", ""),
        ("B&D", "chapter", "3", ""),
        ("B&D", "section", "2.3", ""),
        ("B&D", "section", "6.1", ""),
        ("B&D", "section", "5.1.1", ""),
        ("B&D", "section", "A.3", ""),  # SA.3: section 3 of appendix A
        ("B&D", "item", "3.2.2", "Example"),
        ("S&S", "section", "2.2", ""),
        ("S&S", "item", "1.11", "Definition"),
        ("S&S", "chapter", "3", ""),
        ("S&S", "section", "3.5", ""),
        ("S&S", "section", "3.3", ""),
        ("S&S", "opening", "3", ""),  # C3 P1: chapter 3's first paragraph
        ("BJR&L", "section", "1.2", ""),
    }
    names = {c.abbr: c.names for c in cited}
    assert names["B&D"] == {"brockwell", "davis"} and names["BJR&L"] == {"box", "jenkins", "reinsel", "ljung"}
    assert {str(c) for c in cited} >= {"B&D SA.3", "S&S C3 P1", "S&S D1.11"}


def test_inline_citations_and_a_legend_of_their_own():
    text = (
        "B&D: Brockwell & Davis (2016). S&S: Shumway & Stoffer (2025). SA = section in appendix A; T: Theorem.\n"
        "Read B&D S2.3 and S&S 3.5, Ch. 4 before class; also B&D T2.1.1 and SA3. Salby Chapter 2."
    )
    got = codes(studypack.citations([text]))
    assert {
        ("B&D", "section", "2.3", ""),
        ("S&S", "section", "3.5", ""),
        ("S&S", "chapter", "4", ""),
        ("B&D", "item", "2.1.1", "Theorem"),
        ("B&D", "section", "A.3", ""),
        ("", "chapter", "2", ""),  # Salby, by name as before
    } <= got
    assert not any(num in ("2016", "2025") for _, _, num, _ in got)  # an edition's year isn't a chapter


def test_a_table_read_as_plain_text_column_by_column():
    text = (
        "B&D: Brockwell & Davis (2016). S&S: Shumway & Stoffer (2025).\nTopic Discussed\nBackshift\nLinear filter\n"
        "B&D\nS1.5.1.1\nS2.2\nS&S\nS2.2\nD1.11\nC3 P1\n"
    )
    assert codes(studypack.citations([text])) == {
        ("B&D", "section", "1.5.1.1", ""),
        ("B&D", "section", "2.2", ""),
        ("S&S", "section", "2.2", ""),
        ("S&S", "item", "1.11", "Definition"),
        ("S&S", "chapter", "3", ""),
        ("S&S", "opening", "3", ""),
    }


# ----------------------------------------------------------------------------------------- the books
def pages_of(n: int, marks: dict[int, str]) -> list[str]:
    return [marks.get(i, f"Some text on page {i}.") for i in range(1, n + 1)]


def bd_pages() -> list[str]:
    return pages_of(
        200,
        {
            1: "Peter J. Brockwell\nRichard A. Davis\nIntroduction to Time Series and Forecasting",
            3: "Contents\n1.5 Estimation and Elimination 20\n1.6 Testing 25\n2.2 Linear Processes 33\n"
            "2.3 Introduction to ARMA Processes 36\n3.2 The ACF and PACF 55\n5.1 Preliminary Estimation 91\n"
            "6.1 ARIMA Models 111\nA.3 The Multivariate Normal Distribution 185",
            10: "Chapter 1\nIntroduction",
            20: "1.5 Estimation and Elimination of Trend\ntext",
            21: "1.5.1 Estimation in the Absence of Seasonality\ntext",
            25: "1.6 Testing the Estimated Noise Sequence\ntext",
            30: "Chapter 2\nStationary Processes",
            31: "2.1 Basic Properties\ntext",
            33: "2.2 Linear Processes\ntext",
            36: "2.3 Introduction to ARMA Processes\ntext",
            37: "2.3 Introduction to ARMA Processes 37\nrunning head, the section goes on",
            40: "the end of 2.3\n2.4 Properties of the Sample Mean\ntext",
            50: "Chapter 3\nARMA Models\n3.1 ARMA(p, q) Processes\n3.2 The ACF and PACF\n3.3 Forecasting\n\nIn this"
            " chapter",
            51: "3.1 ARMA(p, q) Processes\ntext",
            55: "3.2 The ACF and PACF of an ARMA(p, q) Process\ntext",
            57: "a table of rainfall\n5.2 Mar 4.1 Apr\n6.3 May 2.2 Jun",  # numbers that look like headings
            60: "3.3 Forecasting ARMA Processes\ntext",
            70: "Chapter 4\nSpectral Analysis",
            71: "4.1 Spectral Densities\ntext",
            90: "Chapter 5\nModeling and Forecasting with ARMA Processes",
            91: "5.1 Preliminary Estimation\ntext",
            92: "5.1.1 Yule-Walker Estimation\ntext",
            95: "5.1.2 Burg's Algorithm\ntext",
            98: "5.2 Maximum Likelihood Estimation\ntext",
            110: "Chapter 6\nNonstationary and Seasonal Time Series Models",
            111: "6.1 ARIMA Models for Nonstationary Time Series\ntext",
            115: "6.2 Identification Techniques\ntext",
            180: "Appendix A\nRandom Variables and Probability Distributions",
            181: "A.1 Distribution Functions and Expectation\ntext",
            183: "A.2 Random Vectors\ntext",
            185: "A.3 The Multivariate Normal Distribution\ntext",
            189: "Appendix B\nStatistical Complements\nB.1 Least Squares Estimation\ntext",
        },
    )


def ss_pages() -> list[str]:
    marks = {
        1: "Robert H. Shumway\nDavid S. Stoffer\nTime Series Analysis and Its Applications",
        2: "Preface\nThe approach owes much to Box and Jenkins.",
        5: "Chapter 1\nCharacteristics of Time Series",
        12: "Definition 1.11 A linear process is defined as\ntext",
        20: "Chapter 2\nTime Series Regression and Exploratory Data Analysis",
        25: "2.2 Exploratory Data Analysis\ntext",
        28: "2.3 Smoothing in the Time Series Context\ntext",
        40: "Chapter 3\nARIMA Models",
        41: "3.1 Autoregressive Moving Average Models\ntext",
        50: "3.3 Autocorrelation and Partial Autocorrelation\nautocorrelation of an AR(p)",
        53: "3.4 Forecasting\ntext",
        55: "3.5 Estimation\nthe autocorrelation and Yule-Walker equations",
        60: "3.6 Integrated Models for Nonstationary Data\ntext",
        75: "Chapter 4\nSpectral Analysis and Filtering",
        80: "autocorrelation autocorrelation of the spectrum",
    }
    return pages_of(150, marks)


def bj_pages() -> list[str]:
    marks = {
        1: "George E. P. Box\nGwilym M. Jenkins\nGregory C. Reinsel\nGreta M. Ljung\nTime Series Analysis",
        5: "Chapter 1\nIntroduction",
        6: "1.1 Five Important Practical Problems\ntext",
        8: "1.2 Stochastic and Deterministic Dynamic Mathematical Models\ntext",
        12: "1.3 Basic Ideas in Model Building\ntext",
        20: "Chapter 2\nAutocorrelation Function and Spectrum",
        120: "Chapter 15\nAspects of Process Control",
    }
    for p in range(121, 141):
        marks[p] = "autocorrelation in process control, autocorrelation of the adjustments"
    return pages_of(150, marks)


def notes_pages() -> list[str]:
    marks = {1: "Exam notes, following Brockwell and Davis", 4: "autocorrelation autocorrelation, worked"}
    return pages_of(90, marks)


def book(tmp_path: Path, name: str, pages: list[str]) -> studypack.Source:
    d = tmp_path / name
    (d / "pages").mkdir(parents=True)
    for i, text in enumerate(pages, 1):
        (d / "pages" / f"{i:05d}.md").write_text(text, encoding="utf-8")
    return studypack.Source(Path(tmp_path / f"{name}.pdf"), name, len(pages), d, is_class=False)


def library(tmp_path):
    return [
        book(tmp_path, "Tsa Brockfield Davis", bd_pages()),
        book(tmp_path, "Tsa Ss", ss_pages()),
        book(tmp_path, "Time Series Analysis", bj_pages()),
        book(tmp_path, "Tsa Chapter1 Exam Notes", notes_pages()),
    ]


def test_each_code_turns_into_the_right_book_and_pages(tmp_path):
    bd, ss, bj, notes = library(tmp_path)
    plan = studypack.cited_pages([bd, ss, bj, notes], studypack.citations([SYLLABUS]))
    lines = "\n".join(plan.lines)
    assert "- B&D S2.3 → Tsa Brockfield Davis: pages 36-40" in lines  # past its running head, to 2.4's page
    assert "- B&D C3 → Tsa Brockfield Davis: pages 50-69" in lines  # "Chapter 3" to the page before "Chapter 4"
    assert "- B&D S5.1.1 → Tsa Brockfield Davis: pages 92-95" in lines
    assert "- B&D S6.1 → Tsa Brockfield Davis: pages 111-115" in lines
    assert "- B&D SA.3 → Tsa Brockfield Davis: pages 185-189" in lines
    assert "- B&D S1.5.1.1 → Tsa Brockfield Davis: pages 21-25 (as 1.5.1: 1.5.1.1 has no heading of its own)" in lines
    assert "- S&S D1.11 → Tsa Ss: pages 12-13" in lines  # the definition's page and the next
    assert "- S&S C3 P1 → Tsa Ss: pages 40-41" in lines  # the chapter's opening pages
    assert "- S&S S3.5 → Tsa Ss: pages 55-60" in lines
    assert "- BJR&L S1.2 → Time Series Analysis: pages 8-12" in lines  # by its authors on page 1, not S&S's preface
    assert "- B&D E3.2.2 (Tsa Brockfield Davis): not found in the book's text" in lines
    assert 3 not in plan.pages[id(bd)]  # the contents page isn't a heading
    # nor the list of sections opening chapter 3, nor a table's "5.2 Mar" on page 57
    assert studypack._Book(bd).section("3.2") == list(range(55, 61))
    assert id(notes) not in plan.pages  # exam notes naming Brockwell and Davis aren't their book
    assert set(range(50, 70)) <= plan.within[id(bd)] and 125 not in plan.within[id(bj)]


def test_a_citation_no_book_matches_says_so(tmp_path):
    _, ss, _, _ = library(tmp_path)
    plan = studypack.cited_pages([ss], studypack.citations([SYLLABUS]))
    assert "- BJR&L S1.2: no book in Books matches it (Box, Jenkins, Ljung, Reinsel)" in plan.lines
    assert "- B&D S2.3: no book in Books matches it (Brockwell, Davis)" in plan.lines


def test_cited_pages_go_in_whole_past_the_usual_limit_up_to_the_cap(tmp_path):
    marks = {}
    for ch in range(1, 6):  # five chapters of 70 pages: 350 cited pages, more than 250
        marks[(ch - 1) * 70 + 1] = f"Chapter {ch}\nTitle"
        marks[(ch - 1) * 70 + 2] = f"{ch}.1 Something Here\ntext"
    marks[351] = "Chapter 6\nThe End"
    big = book(tmp_path, "Brockwell Davis", pages_of(400, marks))
    cited = studypack.citations(["B&D: Brockwell & Davis (2016). Read B&D C1, C2, C3, C4, C5."])
    rx = studypack.pattern(["knitting"])
    pages, cut, cut0 = studypack.book_share([big], rx, cited, cap=400)[id(big)]
    assert pages == list(range(1, 351)) and cut == cut0 == 0
    pages, cut, cut0 = studypack.book_share([big], rx, cited, cap=300)[id(big)]
    assert len(pages) == 300 and cut0 == 50
    pages, _, _ = studypack.book_share([big], rx, cited, cap=0)[id(big)]  # off: the old limits
    assert len(pages) == studypack.MAX_BOOK_PAGES


def test_a_cited_books_pages_on_the_topic_come_only_from_its_cited_chapters(tmp_path):
    bd, ss, bj, notes = library(tmp_path)
    books = [bd, ss, bj, notes]
    share = studypack.book_share(books, studypack.pattern(["autocorrelation"]), studypack.citations([SYLLABUS]), 400)
    assert not set(range(121, 141)) & set(share[id(bj)][0])  # Box-Jenkins: only S1.2 is cited, not process control
    assert set(range(8, 13)) <= set(share[id(bj)][0])
    assert 80 not in share[id(ss)][0] and 50 in share[id(ss)][0]  # S&S chapter 4 isn't cited; chapter 3 is
    assert 4 in share[id(notes)][0]  # a book the syllabus doesn't cite still gives its pages on the topic


# ------------------------------------------------------------------------------------------ the pack
def seed(env):
    app = env.app
    env.on("subjects")
    env.say("/subject add Time Series Analysis (tsa)")
    env.say("/subject add Linear Algebra (la)")
    src = app.workspace.parent / "pdfs"
    src.mkdir()
    store = app.paths.data / "book-text" / "time-series-analysis"

    def read(fid, fname, pages):
        f = src / fname
        f.write_bytes(b"%PDF " + fname.encode())
        d = store / fid
        (d / "pages").mkdir(parents=True)
        for i, text in enumerate(pages, 1):
            (d / "pages" / f"{i:05d}.md").write_text(text, encoding="utf-8")
        meta = {"file": str(f), "title": fname.removesuffix(".pdf"), "pages": len(pages)}
        (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    read("syllabus", "TSA Syllabus.pdf", [SYLLABUS])
    read("bd", "Tsa Brockfield Davis.pdf", bd_pages())
    read("ss", "Tsa Ss.pdf", ss_pages())
    read("bj", "Time Series Analysis.pdf", bj_pages())
    read("notes", "Tsa Chapter1 Exam Notes.pdf", notes_pages())
    ws = app.workspace
    (ws / "handwritten").mkdir()
    (ws / "handwritten" / "matrices.md").write_text(
        "---\ncourse: linear-algebra\ntags: [handwritten, linear-algebra]\n---\n# Matrices\n"
        "autocorrelation matrix, autocorrelation, autocorrelation",
        "utf-8",
    )
    (ws / "handwritten" / "ar-models.md").write_text(
        "---\ncourse: time-series-analysis\n---\n# AR models\nautocorrelation of an AR(1)", "utf-8"
    )
    (ws / "zettel").mkdir()
    (ws / "zettel" / "toeplitz.md").write_text(
        "---\ntags: [zettel, linear-algebra]\n---\n# Toeplitz\nautocorrelation autocorrelation autocorrelation", "utf-8"
    )


def test_a_pack_with_a_syllabus_has_the_cited_sections_and_the_index_says_what_each_became(env):
    seed(env)
    path, info = studypack.build(env.app, "time-series-analysis", "TSA", "quiz on thursday")
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        index, prompt = z.read("INDEX.md").decode(), z.read("PROMPT.md").decode()
        bd = z.read("books/tsa-brockfield-davis-pages.md").decode()
        bj = z.read("books/time-series-analysis-pages.md").decode()
    assert info["cited"] and info["books"] == 3 and "class/TSA Syllabus.pdf" in names
    assert "<!-- page 36 -->" in bd and "<!-- page 185 -->" in bd and "<!-- page 150 -->" not in bd
    assert "<!-- page 8 -->" in bj and "<!-- page 125 -->" not in bj  # not chapter 15 (process control)
    assert "## Readings the class cites" in index
    assert "- B&D S2.3 → Tsa Brockfield Davis: pages 36-40" in index
    assert "- B&D E3.2.2 (Tsa Brockfield Davis): not found in the book's text" in index
    assert "Tsa Chapter1 Exam Notes (90 pages): the class cites nothing in it" in index
    assert "the sections the class material cites" in prompt
    env.app.settings.set("studypack.cited_pages", 0)  # off: without a topic, no book pages (as before)
    path, info = studypack.build(env.app, "time-series-analysis", "TSA", "quiz on thursday")
    with zipfile.ZipFile(path) as z:
        assert not any(n.startswith("books/") for n in z.namelist()) and not info["cited"]
        assert "studypack.cited_pages is 0" in z.read("INDEX.md").decode()


def test_a_whole_syllabus_as_the_aim_uses_the_citations_not_its_words(env):
    seed(env)
    aim = "exam on " + ", ".join(
        "backshift operators, linear filters, AR models, ARMA models, ARIMA models, Yule-Walker equations, "
        "multivariate normal, autocovariance, autocorrelation, non-stationary data".split(", ")
    )
    path, info = studypack.build(env.app, "time-series-analysis", "TSA", aim)
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        ss = z.read("books/tsa-ss-pages.md").decode()
        index = z.read("INDEX.md").decode()
    assert info["broad"] and info["cited"]
    assert "<!-- page 80 -->" not in ss and "<!-- page 50 -->" in ss  # no keyword-only pages
    assert not any("exam-notes" in n for n in names)
    assert "and 4 more" in index.splitlines()[0]
    assert "notes/handwritten/ar-models.md" in names  # the subject's own handwritten note
    assert "notes/handwritten/matrices.md" not in names


def test_another_subjects_note_on_the_same_words_stays_out(env, monkeypatch):
    seed(env)
    app = env.app
    path, _ = studypack.build(app, "time-series-analysis", "TSA", topics=["autocorrelation"])
    names = set(zipfile.ZipFile(path).namelist())
    assert "notes/handwritten/ar-models.md" in names  # course: this subject
    assert "notes/handwritten/matrices.md" not in names  # course: linear algebra, however often it says the word
    assert "notes/zettel/toeplitz.md" not in names  # tagged for linear algebra only

    class Brain:
        def search(self, q, n=10):
            return "handwritten/matrices.md and zettel/toeplitz.md and handwritten/ar-models.md"

    app.modules["gbrain"] = Brain()
    real = app.is_on
    monkeypatch.setattr(app, "is_on", lambda m: m == "gbrain" or real(m))
    found = studypack.brain_notes(app, ["autocorrelation"], "time-series-analysis")
    assert [p.name for p in found] == ["ar-models.md"]
    assert len(studypack.brain_notes(app, ["autocorrelation"])) == 3  # without a subject, as before
