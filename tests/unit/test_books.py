"""Books and PDFs: the built-in PDF reader, choosing how each page is read, reading that resumes where it stopped,
the index note, books from Telegram, and the source mix with its citations. No real OCR and no network: fakes."""

import datetime as dt
import zlib

import pytest

from kurooto.core import sources
from kurooto.core.clock import now
from kurooto.core.pdfread import Pdf, operations, parse_cmap
from kurooto.core.state import jsave
from kurooto.modules.books import Books, Doc, chapters, mathy, put_block, route, usable

LOREM = (
    "A vector space over a field F is a set V with an addition and a scalar multiplication satisfying the usual "
    "axioms. Linear maps preserve both operations."
)


# ------------------------------------------------------------------------------------------- fixture PDFs
def _esc(s: str) -> bytes:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1")


def make_pdf(path, pages, outline=(), compress=True):
    """A small PDF: each page is ("text", "line\\nline") drawn in Helvetica, or ("image", (w, h, gray bytes)), a
    scanned page (one picture, no text). outline: [(title, page number)]. Written by hand, xref and all."""
    objs: dict[int, bytes] = {}
    n_pages = len(pages)
    page_nums = [4 + 3 * i for i in range(n_pages)]
    objs[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    for i, (kind, body) in enumerate(pages):
        pnum, cnum, inum = page_nums[i], page_nums[i] + 1, page_nums[i] + 2
        if kind == "text":
            lines = body.split("\n")
            ops = b"BT /F1 11 Tf 72 720 Td " + b" 0 -14 Td ".join(b"(" + _esc(x) + b") Tj" for x in lines) + b" ET"
            res = b"<< /Font << /F1 3 0 R >> >>"
            objs[inum] = b"<< >>"
        else:
            w, h, px = body
            ops = f"q {w} 0 0 {h} 0 0 cm /Im1 Do Q".encode()
            data = zlib.compress(px)
            objs[inum] = (
                (
                    f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray "
                    f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} >>\nstream\n"
                ).encode()
                + data
                + b"\nendstream"
            )
            res = f"<< /XObject << /Im1 {inum} 0 R >> >>".encode()
        if compress:
            data = zlib.compress(ops)
            objs[cnum] = f"<< /Length {len(data)} /Filter /FlateDecode >>\nstream\n".encode() + data + b"\nendstream"
        else:
            objs[cnum] = f"<< /Length {len(ops)} >>\nstream\n".encode() + ops + b"\nendstream"
        objs[pnum] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {cnum} 0 R /Resources ".encode()
            + res
            + b" >>"
        )
    kids = " ".join(f"{p} 0 R" for p in page_nums)
    objs[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode()
    cat = b"<< /Type /Catalog /Pages 2 0 R"
    if outline:
        top = 4 + 3 * n_pages
        items = [top + 1 + i for i in range(len(outline))]
        objs[top] = f"<< /Type /Outlines /First {items[0]} 0 R /Last {items[-1]} 0 R /Count {len(items)} >>".encode()
        for i, (title, page) in enumerate(outline):
            nxt = f" /Next {items[i + 1]} 0 R" if i + 1 < len(items) else ""
            objs[items[i]] = (
                b"<< /Title ("
                + _esc(title)
                + f") /Parent {top} 0 R /Dest [{page_nums[page - 1]} 0 R /Fit]{nxt} >>".encode()
            )
        cat += f" /Outlines {top} 0 R".encode()
    objs[1] = cat + b" >>"
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + objs[num] + b"\nendobj\n"
    xref = len(out)
    size = max(objs) + 1
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for num in range(1, size):
        out += f"{offsets.get(num, 0):010d} {'n' if num in offsets else 'f'} \n".encode()
    out += f"trailer\n<< /Size {size} /Root 1 0 R /Info << /Title (Linear Algebra) >> >>\n".encode()
    out += f"startxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


SCAN = (40, 30, bytes((x * 7 + y * 3) % 256 for y in range(30) for x in range(40)))


@pytest.fixture
def pdfs(tmp_path):
    text = make_pdf(
        tmp_path / "text.pdf",
        [("text", "Chapter 1 Vector spaces\n" + LOREM), ("text", "Eigenvalues (and eigenvectors)\n" + LOREM)],
        outline=[("1 Vector spaces", 1), ("2 Eigenvalues", 2)],
    )
    scanned = make_pdf(tmp_path / "scan.pdf", [("image", SCAN), ("image", SCAN)], compress=False)
    mixed = make_pdf(tmp_path / "mixed.pdf", [("text", LOREM), ("image", SCAN), ("text", ""), ("image", SCAN)])
    return {"text": text, "scan": scanned, "mixed": mixed}


# ------------------------------------------------------------------------------------------- the reader
def test_builtin_reader_text_outline_and_title(pdfs):
    p = Pdf(pdfs["text"])
    assert p.page_count() == 2 and not p.encrypted
    assert "Eigenvalues (and eigenvectors)" in p.page_text(2)
    assert "scalar multiplication" in p.page_text(1)
    assert p.outline() == [(1, "1 Vector spaces", 1), (1, "2 Eigenvalues", 2)]
    assert not p.has_images(1)
    assert Doc(pdfs["text"], {}, pdfs["text"].parent).title() == "Linear Algebra"


def test_builtin_reader_gives_the_scan_of_an_image_only_page(pdfs):
    p = Pdf(pdfs["scan"])
    assert p.page_count() == 2
    assert p.page_text(1) == ""
    assert p.has_images(1)
    data, mime = p.page_image(1)
    assert mime == "image/png" and data.startswith(b"\x89PNG")
    assert zlib.decompress(data[data.index(b"IDAT") + 4 : data.index(b"IEND") - 8])[1:41] == SCAN[2][:40]


def test_cmap_and_content_operations():
    cmap, width = parse_cmap(
        b"begincodespacerange <0000> <FFFF> endcodespacerange 1 beginbfchar <0003> <03BB> endbfchar "
        b"1 beginbfrange <0010> <0012> <0041> endbfrange"
    )
    assert width == 2 and cmap[3] == "λ" and cmap[0x11] == "B"
    ops = list(operations(b"BT /F1 9 Tf (a\\(b\\)) Tj BI /W 1 /H 1 ID \x00\x01 EI [(x) -300 (y)] TJ ET"))
    assert [o for o, _ in ops] == ["BT", "Tf", "Tj", "BI", "TJ", "ET"]
    assert ops[2][1] == [b"a(b)"]


def test_not_a_pdf_is_refused(tmp_path):
    f = tmp_path / "x.pdf"
    f.write_bytes(b"hello")
    assert Doc(f, {}, tmp_path).pages() == 0


# ------------------------------------------------------------------------------------------- the route
@pytest.mark.parametrize(
    "text,images,engines,ocr,latex,want",
    [
        (LOREM, False, {"text"}, "auto", "maths", ["text"]),  # a text layer: read it
        ("", True, {"text", "tesseract", "vision"}, "auto", "maths", ["tesseract", "vision"]),  # a scan: OCR
        ("", True, {"text", "vision"}, "auto", "maths", ["vision"]),  # no Tesseract: the vision model
        ("", True, {"text"}, "auto", "maths", []),  # nothing can read it (yet)
        ("", True, {"text", "tesseract", "gemini"}, "off", "maths", []),  # OCR off
        ("", True, {"text", "gemini"}, "auto", "maths", ["gemini"]),  # Gemini only when it's an engine (opt-in)
        ("", False, {"text", "tesseract"}, "auto", "maths", ["blank"]),  # nothing on the page
        ("Chapter 2", False, {"text", "tesseract"}, "auto", "maths", ["text"]),  # a title page
        ("x", None, {"text", "tesseract"}, "auto", "maths", ["tesseract", "text"]),  # unknown: OCR, else the text
        (
            "a=b+c, x^2 = y_1 ∑ ∫ α β γ ≤ ≥ " * 6,  # maths the text layer carried well: no second reading
            False,
            {"text", "vision"},
            "auto",
            "maths",
            ["text"],
        ),
        (
            "\n".join(
                ["Let the loss be", "E", "=", "∑", "n", "(", "y", "−", "t", "n", ")", "2", "and x^2 ≤ ∫ α β γ"] * 2
            ),
            False,
            {"text", "vision"},
            "auto",
            "maths",
            ["vision", "text"],  # maths in pieces: worth reading as a picture
        ),
        ("a=b+c, x^2 = y_1 ∑ ∫ α β γ ≤ ≥ " * 6, False, {"text", "vision"}, "auto", "never", ["text"]),
        (LOREM, False, {"text", "vision"}, "auto", "all", ["vision", "text"]),
    ],
)
def test_route_per_page(text, images, engines, ocr, latex, want):
    assert route(text, images, engines, ocr, latex) == want


def test_text_quality_and_maths():
    assert usable(LOREM) and not usable("�" * 50 + "ab") and not usable("  ")
    assert mathy("Let λ be an eigenvalue: det(A − λI) = 0, so ∑ λ_i = tr A and ∏ λ_i = det A, x^2 ≤ y")
    assert not mathy(LOREM)


# ------------------------------------------------------------------------------------------- the module
@pytest.fixture
def books(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    from kurooto.app import App

    app = App()
    app.power.current = "normal"  # tests run on a charger, whatever this laptop is doing
    bk = Books(app)
    app.modules["books"] = bk
    jsave(app.paths.state / "books.json", {"set_up": True})
    ok, why = app.enable("books")
    assert ok, why
    monkeypatch.setattr(bk, "tools", lambda: {"pdftotext": None, "pdftoppm": None, "pdfinfo": None})
    yield bk
    app.close()


class FakeOCR:
    """Stands in for Tesseract and the vision model; can interrupt the reading after some pages."""

    def __init__(self, bk, stop_after=None):
        self.bk, self.stop_after, self.calls = bk, stop_after, []

    def __call__(self, engine, img, mime, page):
        assert img.startswith(b"\x89PNG") and mime == "image/png"
        self.calls.append((engine, page))
        if self.stop_after and len(self.calls) >= self.stop_after:
            self.bk._halt.set()  # as if the charger were pulled now
        return f"OCR text of page {page} by {engine}"


def test_each_page_read_its_best_way_and_reading_resumes(books, pdfs, monkeypatch):
    d = books.folder("linear-algebra")
    d.mkdir(parents=True)
    (d / "mixed.pdf").write_bytes(pdfs["mixed"].read_bytes())
    monkeypatch.setattr(books, "engines", lambda: {"text", "tesseract"})
    ocr = FakeOCR(books, stop_after=1)
    monkeypatch.setattr(books, "read_picture", ocr)
    b = books.library()[0]
    assert b == {"subject": "linear-algebra", "path": d / "mixed.pdf", "id": "mixed"}

    first = books.read_book(b)
    assert first["result"] == "stopped" and first["read"] == 2  # page 1 (text), page 2 (OCR), then interrupted
    pages = books.book_dir(b) / "pages"
    assert sorted(p.name for p in pages.iterdir()) == ["00001.md", "00002.md"]
    assert "· text -->" in (pages / "00001.md").read_text(encoding="utf-8") and "OCR text of page 2" in (
        pages / "00002.md"
    ).read_text(encoding="utf-8")

    books._halt.clear()
    ocr.stop_after = None
    second = books.read_book(b)
    assert second == {"book": "mixed", "read": 2, "result": "done"}
    assert ocr.calls == [("tesseract", 2), ("tesseract", 4)]  # page 2 not read twice; page 3 has no text: blank
    meta = books.meta(b)
    assert meta["routes"] == {"text": 1, "tesseract": 2, "blank": 1} and meta["done"] == 4
    text = (books.book_dir(b) / "text.md").read_text(encoding="utf-8")
    assert '<a id="p-4"></a>\n## [p. 4]' in text and "OCR text of page 4" in text
    assert books.read_book(b)["read"] == 0  # nothing left


def test_pages_wait_for_a_reader_and_are_read_when_one_arrives(books, pdfs, monkeypatch):
    d = books.folder("linear-algebra")
    d.mkdir(parents=True)
    (d / "scan.pdf").write_bytes(pdfs["scan"].read_bytes())
    monkeypatch.setattr(books, "engines", lambda: {"text"})
    b = books.library()[0]
    assert books.read_book(b)["read"] == 0
    meta = books.meta(b)
    assert set(meta["skipped"]) == {"1", "2"} and "Tesseract" in meta["skipped"]["1"]
    assert "Not read yet: 2 page(s)" in (books.app.workspace / meta["index"]).read_text(encoding="utf-8")
    monkeypatch.setattr(books, "engines", lambda: {"text", "vision"})
    monkeypatch.setattr(books, "read_picture", FakeOCR(books))
    assert books.read_book(b)["read"] == 2
    assert books.meta(b)["routes"] == {"vision": 2} and not books.meta(b)["skipped"]


def test_maths_from_tesseract_goes_to_the_vision_model(books, pdfs, monkeypatch):
    seen = []

    def fake(engine, img, mime, page):
        seen.append(engine)
        return "λ = a+b, x^2 = y_1, ∑ α ≤ β = γ ∫ = δ" if engine == "tesseract" else "$\\lambda = a + b$"

    monkeypatch.setattr(books, "read_picture", fake)
    doc = Doc(pdfs["scan"], {}, books.app.paths.cache)
    assert books.read_page(doc, 1, {"text", "tesseract", "vision"}) == ("$\\lambda = a + b$", "vision")
    assert seen == ["tesseract", "vision"]
    books.app.settings.set("books.latex", "never")
    assert books.read_page(doc, 1, {"text", "tesseract", "vision"})[1] == "tesseract"


def test_index_note_has_chapters_and_keeps_your_text(books, pdfs, monkeypatch):
    d = books.folder("linear-algebra")
    d.mkdir(parents=True)
    (d / "axler.pdf").write_bytes(pdfs["text"].read_bytes())
    b = books.library()[0]
    books.read_book(b)
    note = books.app.workspace / "linear-algebra" / "books" / "axler.md"
    text = note.read_text(encoding="utf-8")
    assert text.startswith("---\nmade_by: ") and "# Linear Algebra" in text
    assert "- p. 1–1: 1 Vector spaces" in text and "- p. 2–2: 2 Eigenvalues" in text
    note.write_text(text + "\nMy own remark about this book.\n", encoding="utf-8")
    books.finish(b, books.meta(b))
    again = note.read_text(encoding="utf-8")
    assert "My own remark about this book." in again and again.count("<!-- /kurooto:book -->") == 1


def test_chapters_from_page_headings_without_bookmarks():
    pages = {1: "Preface\nwords", 2: "Chapter 1 Groups\ntext", 5: "CHAPTER 2: Rings\ntext"}
    assert chapters([], pages, 9) == [(1, "Chapter 1 Groups", 2, 4), (1, "CHAPTER 2: Rings", 5, 9)]
    assert put_block("mine\n", "new", "") == (
        "mine\n\n<!-- kurooto:book (kept current by Kurooto from the book; write your own notes outside these "
        "markers) -->\nnew\n<!-- /kurooto:book -->\n"
    )


def test_reading_stops_in_the_morning_and_on_battery(books, pdfs, monkeypatch):
    d = books.folder("algebra")
    d.mkdir(parents=True)
    (d / "t.pdf").write_bytes(pdfs["text"].read_bytes())
    b = books.library()[0]
    past = now() - dt.timedelta(minutes=1)
    assert books.read_book(b, until=past)["result"] == "morning"
    books.app.power.current = "saver"
    assert books.read_all()["stopped"] == "on battery"
    assert books.app.scheduler.get("books:resume").action == "books.now"  # carries on when plugged in again
    assert not (books.book_dir(b) / "pages" / "00001.md").exists()


@pytest.mark.parametrize(
    "wanted,want",
    [
        ([{"key": "helper-large", "tag": "gemma4:e4b", "vision": True}], "gemma4:e4b"),  # 8 GB cards: the helper reads
        ([{"key": "helper-large", "tag": "h"}, {"key": "vision", "tag": "v"}], "v"),  # 12 GB: the vision model first
        ([{"key": "embed", "tag": "e"}], None),  # nothing that sees pictures
    ],
)
def test_vision_model_comes_from_local_models(books, monkeypatch, wanted, want):
    lm = books.app.modules["local_models"]
    monkeypatch.setattr(lm, "wanted", lambda: wanted)
    assert books.vision_model() is None  # Local models off
    books.app.settings.set("modules.enabled", [*books.app.settings.get("modules.enabled"), "local_models"])
    assert books.vision_model() == want
    assert ("vision" in books.engines()) == bool(want)


def test_the_night_window(books):
    day = dt.datetime(2026, 10, 20)
    assert books.night(day.replace(hour=1, minute=30)) and not books.night(day.replace(hour=9))
    books.app.settings.set("books.at", "daily 23:00")
    assert books.night(day.replace(hour=23, minute=30)) and books.night(day.replace(hour=6))
    assert not books.night(day.replace(hour=7)) and not books.night(day.replace(hour=15))


def test_books_folder_follows_files_folder_outside_the_notes(books, tmp_path):
    assert books.folder("Linear Algebra") == books.app.paths.data / "books" / "linear-algebra"
    books.app.settings.set("files.folder", str(tmp_path / "files"))
    assert books.folder("linear-algebra") == tmp_path / "files" / "linear-algebra" / "books"
    books.app.settings.set("books.folder", str(tmp_path / "mybooks"))
    assert books.folder("linear-algebra") == tmp_path / "mybooks" / "linear-algebra"


def test_tools_list_and_read_book_pages(books, pdfs):
    d = books.folder("linear-algebra")
    d.mkdir(parents=True)
    (d / "axler.pdf").write_bytes(pdfs["text"].read_bytes())
    books.read_book(books.library()[0])
    tools = {t.name: t for t in books.agent_tools()}
    assert "Linear Algebra, 2 pages" in tools["list_books"].run({"subject": "linear-algebra"})
    out = tools["read_book"].run({"book": "linear algebra", "pages": "2-3"})
    assert "[p. 2]\nEigenvalues" in out and "[p. 3] (not read yet)" in out
    assert {"course_sources", "update_exam_prep"} <= set(tools)


# ------------------------------------------------------------------------------------------- Telegram
def test_a_pdf_sent_as_a_book_goes_to_the_subject(env, pdfs):
    bk = Books(env.app)
    env.app.modules["books"] = bk
    jsave(env.app.paths.state / "books.json", {"set_up": True})
    env.on("books")
    env.fake.files["docs/abc.pdf"] = pdfs["text"].read_bytes()
    reply = env.say(caption="book for Linear Algebra", document={"file_id": "abc", "file_name": "axler.pdf"})
    assert reply.startswith("Added axler.pdf to linear-algebra's books (2 pages).")
    assert (env.app.paths.data / "books" / "linear-algebra" / "axler.pdf").is_file()
    assert not list((env.app.workspace / "inbox").glob("*.pdf"))  # moved out of the notes
    assert "linear-algebra:" in env.say("/books")


# ------------------------------------------------------------------------------------------- the mix
def test_mix_weights_renormalise_over_the_sources_there_are():
    w = sources.weights({"mix": {"book": 0.3, "classroom": 0.3, "own": 0.4}})
    assert w == pytest.approx({"book": 0.3, "classroom": 0.3, "own": 0.4})
    used = sources.renormalise(w, ["book", "own"])  # no Classroom materials for this subject
    assert used == pytest.approx({"book": 0.3 / 0.7, "classroom": 0.0, "own": 0.4 / 0.7})
    assert sources.renormalise(w, []) == {"book": 0.0, "classroom": 0.0, "own": 0.0}
    assert sources.weights({"prefer": ["own", "book"], "mix": {"classroom": 1}}) == pytest.approx(
        {"book": 1 / 3, "classroom": 0.0, "own": 2 / 3}
    )
    assert sources.weights({"mix": {"book": "x", "own": -1}}) == pytest.approx(sources.DEFAULT_MIX)


def test_shares_respect_caps_and_pass_unused_room_on():
    w = {"book": 0.5, "classroom": 0.0, "own": 0.5}
    assert sources.shares(w, {"book": 50000, "own": 50000}, 10000) == {"book": 5000, "classroom": 0, "own": 5000}
    # own has little: what it can't use goes to the book
    assert sources.shares(w, {"book": 50000, "own": 1000}, 10000) == {"book": 9000, "classroom": 0, "own": 1000}
    # a cap holds even when there's room
    assert sources.shares(w, {"book": 50000, "own": 50000}, 10000, {"book": 2000}) == {
        "book": 2000,
        "classroom": 0,
        "own": 8000,
    }


def test_subject_mix_settings_and_the_command(books):
    app = books.app
    assert sources.set_mix(app, "linear-algebra", "book 50 own 50") == "linear-algebra: books 50% · your own notes 50%."
    assert sources.config(app, "linear-algebra")["mix"] == {"book": 0.5, "own": 0.5}
    assert sources.config(app, "statistics")["mix"] == sources.DEFAULT_MIX
    assert "in this order: your own notes, books" in sources.set_mix(app, "linear-algebra", "prefer mine, textbook")
    assert "general mix" in sources.set_mix(app, "linear-algebra", "reset")
    assert "isn't a source" in sources.set_mix(app, "x", "wiki 40")


def test_gather_mixes_the_sources_and_labels_citations(books, pdfs):
    app = books.app
    ws = app.workspace / "linear-algebra"
    ws.mkdir(parents=True)
    (ws / "eigen-tricks.md").write_text(
        "# Eigen tricks\n\nMy trick: the eigenvalue of a triangular matrix is on the diagonal.\n", encoding="utf-8"
    )
    (ws / "2026-10-12-eigenvalues.md").write_text(
        "---\nmade_by: Kurooto\ndate: 2026-10-12\n---\n\n# Eigenvalues\n\n"
        "## Covered\nAI summary of eigenvalue facts.\n\n"
        "## My notes\nEigenvalue: Av = λv, written in class.\n\n## Files\n- none\n",
        encoding="utf-8",
    )
    (ws / "2026-10-10-problem-set-3.md").write_text(
        "---\nmade_by: Kurooto\n---\n\n# Problem set 3\n\n## Covered\nEigenvalue problems.\n\n## From the post\n"
        "Solve the eigenvalue questions by Friday.\n",
        encoding="utf-8",
    )
    (ws / "2026-10-01-unrelated.md").write_text("# Groups\n\nNothing about the topic.\n", encoding="utf-8")
    d = books.folder("linear-algebra")
    d.mkdir(parents=True)
    (d / "axler.pdf").write_bytes(pdfs["text"].read_bytes())
    books.read_book(books.library()[0])

    got = sources.gather(app, "linear-algebra", "eigenvalues", books=books.book_excerpts)
    t = got["text"]
    assert "(book: Linear Algebra, p. 2)" in t and "(book: Linear Algebra, p. 1)" not in t
    assert "(your notes: [[linear-algebra/eigen-tricks]])" in t
    assert "(your notes: [[linear-algebra/2026-10-12-eigenvalues]], My notes)" in t
    assert (
        "Eigenvalue: Av = λv, written in class." in t
        and "AI summary" not in t.split("=== your own notes")[1].split("===")[0]
    )
    assert "(Classroom: Problem set 3 [[linear-algebra/2026-10-10-problem-set-3]])" in t
    assert "Groups" not in t and "Linear Algebra" in t
    assert all(got["chars"][s] > 0 for s in sources.SOURCES)

    sources.set_mix(app, "linear-algebra", "book 100")  # only books count for this subject now
    got = sources.gather(app, "linear-algebra", "eigenvalues", books=books.book_excerpts)
    assert got["chars"]["own"] == 0 and got["chars"]["classroom"] == 0 and got["chars"]["book"] > 0

    sources.set_mix(app, "linear-algebra", "reset")
    (d / "axler.pdf").unlink()
    got = sources.gather(app, "linear-algebra", "eigenvalues", books=books.book_excerpts)
    assert got["used"]["book"] == 0 and got["used"]["own"] == pytest.approx(0.4 / 0.7)
    assert "nothing found in books" in got["text"]

    tool = {t.name: t for t in books.agent_tools()}["course_sources"]
    assert "Sources for linear-algebra" in tool.run({"subject": "Linear Algebra", "topic": "eigenvalue"})


def test_library_finds_books_in_nested_subdirectories(books, pdfs):
    d = books.folder("linear-algebra")
    nested = d / "chapterwise" / "part1"
    nested.mkdir(parents=True)
    (nested / "vectors.pdf").write_bytes(pdfs["text"].read_bytes())
    (d / "root_book.pdf").write_bytes(pdfs["text"].read_bytes())

    lib = books.library()
    ids = {b["id"]: b for b in lib}
    assert "root-book" in ids
    assert "chapterwise-part1-vectors" in ids
    assert ids["chapterwise-part1-vectors"]["subject"] == "linear-algebra"
    assert ids["chapterwise-part1-vectors"]["path"] == nested / "vectors.pdf"


# ------------------------------------------------------------------------------------------- the skills
def test_notes_skills_draw_on_the_source_mix_and_cite(env):
    from pathlib import Path

    from kurooto.modules.skills import all_skills

    found = all_skills(env.app)
    s = found["exam-prep"]  # new: exam prep from all three sources, for subjects without Classroom too
    assert s.source == "shipped" and s.effort == "high" and "$ARGUMENTS" in s.body and s.args
    for name in ("study-log", "classroom-digest", "revision-pack", "add-to-notes", "exam-prep"):
        text = Path(found[name].path).read_text(encoding="utf-8")
        assert "course_sources" in text and "p. 123" in text, name
        assert "shell command" not in text and "python" not in text.lower(), name


def test_library_finds_pdfs_whatever_the_case_of_the_extension(books, pdfs):
    d = books.folder("linear-algebra")
    d.mkdir(parents=True, exist_ok=True)
    (d / "Upper.PDF").write_bytes(pdfs["text"].read_bytes())
    (d / "deep" / "er").mkdir(parents=True)
    (d / "deep" / "er" / "Mixed.Pdf").write_bytes(pdfs["text"].read_bytes())
    ids = {b["id"] for b in books.library()}
    assert {"upper", "deep-er-mixed"} <= ids


def test_a_book_read_runs_your_after_read_command_with_its_subject_and_id(books, tmp_path):
    out = tmp_path / "seen.txt"
    script = tmp_path / "hook.py"
    script.write_text(f"import sys\nopen({str(out)!r}, 'w').write(' '.join(sys.argv[1:]))\n", encoding="utf-8")
    import sys

    books.app.settings.set("books.after_read", [sys.executable, str(script)])
    books._after_read({"subject": "linear-algebra", "id": "vectors"})
    assert out.read_text() == "linear-algebra vectors"
    books.app.settings.set("books.after_read", [])
    out.unlink()
    books._after_read({"subject": "x", "id": "y"})
    assert not out.exists()


def test_no_personal_paths_in_the_shipped_code():
    from pathlib import Path

    import kurooto

    bad = ("ultimate-ai-" + "automation", "/mnt/" + "data", str(Path.home()))  # this author's, and any author's, home
    hits = [
        f"{f.name}: {b}"
        for f in Path(kurooto.__file__).parent.rglob("*")
        if f.suffix in (".py", ".js", ".html", ".css", ".md") and f.is_file()
        for b in bad
        if b in f.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not hits


def test_a_book_that_isnt_a_pdf_is_said_so_truthfully(tmp_path):
    from kurooto.modules import books

    img = tmp_path / "img_2.pdf"
    img.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    why = books.unreadable_why(img, {"pdftotext": "/usr/bin/pdftotext"})
    assert "isn't a PDF" in why and "JPEG photo" in why and "Poppler" not in why  # not blamed on a missing program
    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(b"%PDF-1.4\n" + b"0" * 50)
    assert "encrypted or damaged" in books.unreadable_why(pdf, {"pdftotext": "/usr/bin/pdftotext"})
    missing = books.unreadable_why(pdf, {"pdftotext": None, "pdftoppm": None, "pdfinfo": None})
    assert "Poppler isn't installed" in missing and "pacman -S poppler" in missing and "brew install poppler" in missing
