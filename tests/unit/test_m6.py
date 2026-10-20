"""M6: Handwritten notes (a fake Gemini) and the Study tracker (window titles faked). Research: test_research.py."""

from __future__ import annotations

import os
import time

import pytest

from kurooto.modules import study as study_mod
from tests.fakes.cloud import FakeCloud

SUBJECTS = [
    {"slug": "linear-algebra", "name": "Linear Algebra", "aliases": ["LA"]},
    {"slug": "probability", "name": "Probability", "aliases": ["prob"]},
]


# ------------------------------------------------------------------------------------------ handwritten
def test_handwritten_pages_become_notes(env):
    cloud = FakeCloud()
    try:
        env.app.secrets.set("gemini.api_key", "k")
        env.app.settings.set("voice_notes.api_base", cloud.base)
        cloud.transcript = "# Eigenvalues and eigenvectors\n\n$$A v = \\lambda v$$"
        env.on("handwritten")
        hw = env.app.modules["handwritten"]
        f = hw.folder() / "scan 01.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        os.utime(f, (time.time() - 60, time.time() - 60))
        (hw.folder() / "notes.txt").write_text("ignored")
        done = hw.scan()
        assert (
            len(done) == 1
            and done[0].startswith("handwritten/")
            and done[0].endswith("-eigenvalues-and-eigenvectors.md")
        )
        note = (env.app.workspace / done[0]).read_text()
        assert "$$A v = \\lambda v$$" in note and "Original: [" in note
        assert (env.app.workspace / done[0]).with_suffix(".pdf").read_bytes() == b"%PDF-1.4 fake"
        assert cloud.generate[-1]["body"]["contents"][0]["parts"][0]["inline_data"]["mime_type"] == "application/pdf"
        assert hw.scan() == []  # already done
        assert "Written out:" in env.fake.texts()[-1]
        fresh = hw.folder() / "still-copying.jpg"
        fresh.write_bytes(b"x")
        assert hw.scan() == []  # too new: it may still be copying in
    finally:
        cloud.close()


# ------------------------------------------------------------------------------------------------ study
@pytest.fixture
def study(env, monkeypatch):
    env.app.settings.set("subjects.list", SUBJECTS)
    env.on("subjects", "study")
    titles = {"t": "linear-algebra-week3.pdf — PDF viewer"}
    monkeypatch.setattr(study_mod, "active_title", lambda: titles["t"])
    st = env.app.modules["study"]  # a fake idle probe: not locked, idle as titles["idle"] says
    st.probe = __import__("types").SimpleNamespace(
        locked=lambda: False, idle_seconds=lambda title=None: titles["idle"], how=""
    )
    titles["idle"] = 10.0
    return env, st, titles, monkeypatch


def test_study_counts_the_subject_in_the_window(study):
    env, st, titles, mp = study
    assert st.sample(30) == "linear-algebra"
    titles["t"] = "prob problem sheet 4 - Google Chrome"
    assert st.sample(30) == "probability"
    titles["t"] = "notes/probability/bayes.md - VS Code"
    assert st.sample(30) == "probability"
    titles["t"] = "YouTube - cats"
    assert st.sample(30) is None
    titles["idle"] = 900.0
    titles["t"] = "Linear Algebra"
    assert st.sample(30) is None  # away from the keyboard
    assert st.totals() == {"linear-algebra": 30, "probability": 60}
    assert "titles" not in str(st.day())  # only minutes are kept
    assert env.say("/studied 2h LA") == "Logged 2.0 h of Linear Algebra."
    assert env.say("/studied 2h basket weaving").startswith("I don't know the subject")
    report = env.say("/study")
    assert report.startswith("Today (2.0 h):") and "Linear Algebra: 2.0 h" in report
    env.on("weekly")
    assert "Study: 2.0 h (2 subjects)" in env.app.modules["weekly"].summary()
