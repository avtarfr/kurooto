# ruff: noqa: E501
"""0.8.0: find a file by name or contents with a local index, and send it; no AI."""

from __future__ import annotations

import os
import shutil
import time

import pytest

from kurooto.core import finder


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["finder"])
    docs = tmp_path / "docs"
    (docs / "class").mkdir(parents=True)
    (docs / ".hidden").mkdir()
    (docs / "class" / "entropy-lecture.txt").write_text(
        "Entropy measures disorder; the second law says it never decreases."
    )
    (docs / "class" / "rivers.md").write_text("# Rivers\n\nWater flows to the sea through deltas.")
    (docs / "class" / "photo.jpg").write_bytes(b"\xff\xd8\xff" + b"0" * 50)
    (docs / ".hidden" / "secret.txt").write_text("entropy hidden")
    (docs / "id_rsa").write_text("entropy private key")
    (docs / "token.json").write_text('{"entropy": 1}')
    a.settings.set("finder.folders", [str(docs)])
    a.docs = docs
    told = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: told.append((text, kw)))
    a.told = told
    yield a
    a.close()


def test_index_and_search_by_content_and_name(app):
    out = finder.index(app)
    assert out["added"] >= 3 and out["finished"]
    hits = finder.search(app, "second law")
    assert (
        [h["name"] for h in hits] == ["entropy-lecture.txt"]
        and "[second]" in hits[0]["snippet"].lower()
        or "second" in hits[0]["snippet"].lower()
    )
    assert [h["name"] for h in finder.search(app, "photo")] == ["photo.jpg"]  # a name with no text
    assert [h["name"] for h in finder.search(app, "delta")] == ["rivers.md"]  # a prefix
    assert finder.search(app, "zzzz") == [] and finder.search(app, "") == []


def test_hidden_keys_and_tokens_are_never_indexed(app):
    finder.index(app)
    names = {h["name"] for h in finder.search(app, "entropy", 20)}
    assert names == {"entropy-lecture.txt"}  # not .hidden/, id_rsa, token.json


def test_incremental_and_removals(app):
    finder.index(app)
    again = finder.index(app)
    assert again["added"] == again["changed"] == again["removed"] == 0
    f = app.docs / "class" / "rivers.md"
    f.write_text("# Rivers\n\nGlaciers feed some of them.")
    os.utime(f, (time.time() + 5, time.time() + 5))
    (app.docs / "class" / "entropy-lecture.txt").unlink()
    out = finder.index(app)
    assert out["changed"] == 1 and out["removed"] == 1
    assert finder.search(app, "glaciers") and not finder.search(app, "disorder")


def test_a_budget_stops_early_and_never_prunes(app):
    finder.index(app)
    (app.docs / "class" / "rivers.md").unlink()
    cut = finder.index(app, budget_s=-1)
    assert cut["finished"] is False and cut["removed"] == 0
    assert finder.index(app)["removed"] == 1


def test_big_files_keep_their_name_only(app):
    app.settings.set("finder.read_mb", 0.00001)
    finder.index(app)
    assert not finder.search(app, "disorder") and finder.search(app, "entropy lecture")


def test_the_find_command_and_send(app, monkeypatch):
    mod = app.modules["finder"]
    replies = []

    class Msg:
        def reply(self, text, rows=None):
            replies.append((text, rows))

    app.settings.set("finder.folders", [])
    assert "Add a folder first" in mod.cmd(Msg(), "anything")
    app.settings.set("finder.folders", [str(app.docs)])
    finder.index(app)
    assert mod.cmd(Msg(), "second law") is None
    text, rows = replies[0]
    assert "entropy-lecture.txt" in text and rows[0][0][1].startswith("fnd:")
    sent = []
    from kurooto.modules import skills

    monkeypatch.setattr(
        skills, "send_file", lambda a, p, c, inside=None, to="": sent.append((p, inside)) or (True, "Sent.")
    )
    ref = rows[0][0][1].split(":")[1]
    assert mod._button(ref, "send") == "Sent." and sent[0][0].endswith("entropy-lecture.txt")  # noqa: SLF001
    mod._hits[ref] = "/etc/passwd"  # noqa: SLF001
    assert "isn't in a folder" in mod._button(ref, "send")  # nothing outside the chosen folders is sent  # noqa: SLF001
    assert "expired" in mod._button("nope", "send")  # noqa: SLF001
    assert "Nothing matches" in mod.cmd(Msg(), "zzzz qqqq")


def test_add_and_remove_folders(app, tmp_path):
    mod = app.modules["finder"]
    other = tmp_path / "more"
    other.mkdir()
    assert "Added" in mod.cmd(None, f"add {other}") and str(other) in app.settings.get("finder.folders")
    assert "no folder" in mod.cmd(None, "add /nowhere")
    mod.cmd(None, f"remove {other}")
    assert str(other) not in app.settings.get("finder.folders")
    assert str(app.docs) in mod.cmd(None, "folders")


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="no pdftotext")
def test_a_pdf_is_indexed_by_its_text(app):
    from tests.unit.test_inbox_reader import tiny_pdf

    (app.docs / "class" / "midsem.pdf").write_bytes(tiny_pdf("ARIMA models and unit roots covered after the midsem"))
    finder.index(app)
    assert [h["name"] for h in finder.search(app, "unit roots")] == ["midsem.pdf"]
