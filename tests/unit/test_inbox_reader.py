# ruff: noqa: E501
"""0.8.0: files dropped in the scratch folder (a handout, a 'topics covered' list, slides) are read into notes, no AI."""

from __future__ import annotations

import os
import shutil
import time
import zipfile
from pathlib import Path

import pytest

from kurooto.core import inboxreader


def tiny_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)


def docx(path: Path, text: str) -> None:
    body = "".join(f"<w:p><w:r><w:t>{ln}</w:t></w:r></w:p>" for ln in text.split("\n"))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "word/document.xml",
            f'<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>',
        )


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["sorter"])
    (Path(a.workspace) / "inbox").mkdir(parents=True, exist_ok=True)
    yield a
    a.close()


def drop(app, name, data, age=3600):
    f = Path(app.workspace) / "inbox" / name
    f.write_bytes(data) if isinstance(data, bytes) else f.write_text(data, encoding="utf-8")
    os.utime(f, (time.time() - age, time.time() - age))
    return f


TOPICS = "Topics discussed after the midsem exams: AR(p) models, MA(q) models, ARMA, ARIMA, the roots outside the unit disc condition."


def test_off_by_default_reads_nothing(app):
    drop(app, "topics.txt", TOPICS)
    assert inboxreader.read_new(app) == [] and not (Path(app.workspace) / "inbox" / "topics.md").exists()


def test_text_docx_and_pdf_become_notes_and_originals_stay(app):
    app.settings.set("sorter.read_files", True)
    t = drop(app, "topics.txt", TOPICS)
    d = drop(app, "handout.docx", b"")
    docx(d, "Week 5 handout\nStationary processes and their autocovariance functions are covered here in some detail.")
    os.utime(d, (time.time() - 3600, time.time() - 3600))
    got = dict(inboxreader.read_new(app))
    assert set(got) == {"inbox/topics.txt", "inbox/handout.docx"}
    n = (Path(app.workspace) / got["inbox/topics.txt"]).read_text()
    assert (
        n.startswith("---\n")
        and "kind: reference" in n
        and "trust_tier: agent_written" in n
        and "ARIMA" in n
        and "not a book" in n
    )
    assert "Stationary processes" in (Path(app.workspace) / got["inbox/handout.docx"]).read_text()
    assert t.read_text() == TOPICS and d.exists()  # the originals are untouched
    assert inboxreader.read_new(app) == []  # each file once


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="no pdftotext")
def test_a_pdf(app):
    app.settings.set("sorter.read_files", True)
    drop(
        app,
        "after-midsem.pdf",
        tiny_pdf("Topics covered after the midsem: ARIMA models and unit roots in time series data"),
    )
    got = inboxreader.read_new(app)
    assert len(got) == 1 and "ARIMA models" in (Path(app.workspace) / got[0][1]).read_text()


def test_settling_hidden_secrets_size_and_empty(app):
    app.settings.set("sorter.read_files", True)
    drop(app, "fresh.txt", TOPICS + " (fresh)", age=5)  # still being written
    drop(app, ".hidden.txt", TOPICS)
    drop(app, "token-notes.pem", TOPICS)
    drop(app, "empty.txt", "hi")
    drop(app, "huge.txt", TOPICS)
    app.settings.set("sorter.read_mb", 0.00001)
    assert inboxreader.read_new(app) == []
    app.settings.set("sorter.read_mb", 25)
    assert inboxreader.read_new(app) == [("inbox/huge.txt", "inbox/huge.md")]  # empty and hidden and unsettled stay out
    assert inboxreader.read_new(app, force=True)[0][0] == "inbox/fresh.txt"  # /sort now doesn't wait for it to settle
    assert inboxreader.skipped(app) == ["inbox/empty.txt"]


def test_a_name_that_is_taken_and_a_long_file(app):
    app.settings.set("sorter.read_files", True)
    (Path(app.workspace) / "inbox" / "list.md").write_text("my own note", encoding="utf-8")
    drop(app, "list.txt", "word " * 40000)
    note = inboxreader.read_new(app)[0][1]
    text = (Path(app.workspace) / note).read_text()
    assert note == "inbox/list-2.md" and (Path(app.workspace) / "inbox" / "list.md").read_text() == "my own note"
    assert "the rest of the file is cut here" in text and len(text) < inboxreader.MAX_CHARS + 2000


def test_the_sorter_reads_then_files_the_note(app):
    app.settings.set("sorter.read_files", True)
    app.settings.set("sorter.ai", False)
    app.settings.set("modules.enabled", ["sorter"])
    app.modules["sorter"].start()
    told = []
    app.notify = lambda text, **kw: told.append((text, kw))
    drop(app, "topics.txt", TOPICS)
    out = app.modules["sorter"].run(force=True)
    assert out["read"] == [("inbox/topics.txt", "inbox/topics.md")]
    assert any(kw.get("why") == "sorter.read" and "originals are untouched" in t for t, kw in told)
    assert (Path(app.workspace) / "inbox" / "topics.md").exists()  # next pass files it like any note


def test_a_file_read_from_the_inbox_is_queued_for_the_graph(app):
    app.settings.set("sorter.read_files", True)
    app.settings.set("modules.enabled", ["sorter", "integrate", "subjects"])
    app.settings.set("subjects.list", [{"name": "Time Series Analysis", "slug": "time-series-analysis", "aliases": []}])
    text = (
        "Time Series Analysis: topics covered after the midsem. "
        + "AR(p) models are stationary when the roots lie outside the unit disc. " * 12
    )
    drop(app, "topics.txt", text)
    drop(app, "other.txt", "General notes on nothing in particular. " * 15)
    inboxreader.read_new(app)
    items = {k: v for k, v in app.modules["integrate"].items().items()}
    subjects = sorted(v["subject"] for v in items.values() if v["source"] == "reference")
    assert subjects == [
        "reference",
        "time-series-analysis",
    ]  # its subject when the text names one subject, else "reference"
    assert all(v["note"] in ("inbox/topics", "inbox/other") for v in items.values())
    app.settings.set("integrate.sources", ["books", "classroom"])  # switched off: nothing more is queued
    drop(app, "later.txt", "Some later handout text about topology. " * 15)
    inboxreader.read_new(app)
    assert len([v for v in app.modules["integrate"].items().values() if v["source"] == "reference"]) == 2
