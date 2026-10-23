"""Course notes to PDF (core/coursepdf.py): /notes pdf <course> takes the course page, the lecture notes by date and
the concept notes they link, turns their Markdown into LaTeX from the template, compiles it (Tectonic, else the
computer's LaTeX; faked here) and sends the PDF; maths that doesn't compile is shown as written instead."""

from __future__ import annotations

import shutil
import time

import pytest

from kurooto.core import coursepdf, layout
from kurooto.modules import skills as skills_mod


def test_markdown_becomes_latex():
    md = (
        "Intro with **bold**, *it* and `x_1` and a [[linear-algebra/2026-10-14-trace|trace note]].\n\n"
        "## Theorem\n\n"
        "Let $f: X \\to Y$ be 50% continuous & see https://example.org/a_b#c.\n\n"
        "$$\n\\int_0^1 f\\,dx\n$$\n\n"
        "- one\n  - nested\n- [ ] a task\n1. first\n\n"
        "| a | b |\n|---|---|\n| $x$ | y_z |\n\n"
        "> [!note] careful\n\n"
        "```python\nprint('}')\n```\n"
        "![[diagram.png]]\n"
    )
    tex = coursepdf.md_to_tex(md)
    assert r"\textbf{bold}" in tex and r"\emph{it}" in tex and r"\texttt{x\_1}" in tex and r"\emph{trace note}" in tex
    assert r"\subsection{Theorem}" in tex
    assert r"$f: X \to Y$" in tex and r"50\% continuous \&" in tex and r"\url{https://example.org/a_b\#c}" in tex
    assert "\\[\n\\int_0^1 f\\,dx\\]" in tex or "\\[\\int_0^1 f\\,dx\\]" in tex.replace("\n", "")
    assert tex.count(r"\begin{itemize}") == 2 and r"\item $\square$ a task" in tex and r"\begin{enumerate}" in tex
    assert r"\begin{tabular}" in tex and r"y\_z" in tex
    assert r"\textbf{Note.} careful" in tex and r"\begin{Verbatim}" in tex and "print('}')" in tex
    assert r"\emph{[image: diagram.png]}" in tex
    safe = coursepdf.md_to_tex("Let $\\myop{x}$ be.\n")
    assert "$\\myop{x}$" in safe
    assert r"\texttt{\$\textbackslash{}myop\{x\}\$}" in coursepdf.md_to_tex("Let $\\myop{x}$ be.\n", safe=True)


@pytest.fixture
def course(env):
    env.on("subjects")
    env.say("/subject add Linear Algebra (la)")
    app = env.app
    page = layout.path(app, "course", subject="linear-algebra")
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\ntags: [course]\n---\n# Linear Algebra\n\nSee [[eigenvalues]] and [[inbox/stray]].\n")
    for day, slug, body in [
        ("2026-10-14", "trace", "# Trace\n\nThe trace is basis-free; see [[eigenvalues]].\n"),
        (
            "2026-10-07",
            "matrices",
            "# Matrices\n\n<!-- kurooto:seen -->\nKurooto's lines\n<!-- /kurooto:seen -->\nMine.\n",
        ),
    ]:
        layout.path(app, "lecture", subject="linear-algebra", date=day, slug=slug).write_text(body)
    layout.path(app, "concept", subject="linear-algebra", slug="eigenvalues").write_text(
        "# Eigenvalues\n\n$Av=\\lambda v$\n"
    )
    stray = app.workspace / "inbox" / "stray.md"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("# Stray\n")
    return env


def test_which_notes_and_the_document(course):
    app = course.app
    got = coursepdf.notes_for(app, "linear-algebra")
    assert [p.name for p in got["course"]] == ["course.md"]
    assert [p.name for p in got["lectures"]] == ["2026-10-07-matrices.md", "2026-10-14-trace.md"]  # by date
    assert [p.name for p in got["concepts"]] == ["eigenvalues.md"]  # linked, in the course; not the inbox note
    text, n = coursepdf.document(app, "Linear Algebra", got)
    assert n == 4 and text.startswith(coursepdf.MARK)
    assert r"\title{Linear Algebra}" in text and r"\section{Matrices}" in text and "Kurooto's lines" not in text
    assert text.index(r"\section{Matrices}") < text.index(r"\section{Trace}") < text.index(r"\section{Eigenvalues}")
    assert "tags: [course]" not in text and "%%BODY%%" not in text


def test_notes_pdf_compiles_and_sends(course, monkeypatch):
    env = course
    made = []

    def fake_compile(app, tex, timeout=900):
        made.append(tex.read_text())
        if len(made) == 1 and "fail-me" in tex.read_text():
            return False, "! Undefined control sequence."
        tex.with_suffix(".pdf").write_bytes(b"%PDF-1.5 fake")
        return True, ""

    monkeypatch.setattr(skills_mod, "compile_tex", fake_compile)
    monkeypatch.setattr(skills_mod, "pdf_engine", lambda app: "tectonic")
    out = env.say("/notes pdf la")
    assert out.startswith("Making a PDF of Linear Algebra's notes (4 notes)")
    end = time.time() + 5
    while time.time() < end and not any(m == "sendDocument" for m, _ in env.fake.sent):
        time.sleep(0.05)
    docs = [p for m, p in env.fake.sent if m == "sendDocument"]
    assert docs
    tex = layout.file_path(env.app, "pack", "course-notes-linear-algebra.tex", subject="linear-algebra")
    assert tex.is_file() and tex.with_suffix(".pdf").is_file()
    # maths that doesn't compile: made again with the maths as written
    lec = layout.path(env.app, "lecture", subject="linear-algebra", date="2026-10-14", slug="trace")
    lec.write_text("# Trace\n\n$\\fail-me$\n")
    notes = coursepdf.notes_for(env.app, "linear-algebra")
    made.clear()
    ok, said = coursepdf.build(env.app, "linear-algebra", "Linear Algebra", notes)
    assert ok and len(made) == 2 and r"\texttt{\$\textbackslash{}fail-me\$}" in made[1]
    # a file of yours with that name is never written over
    tex.write_text("my own tex\n")
    assert coursepdf.out_path(env.app, "linear-algebra").name == "course-notes-linear-algebra-2.tex"


def test_without_a_latex_engine_the_tex_comes(course, monkeypatch):
    env = course
    monkeypatch.setattr(skills_mod, "pdf_engine", lambda app: None)
    notes = coursepdf.notes_for(env.app, "linear-algebra")
    ok, _ = coursepdf.build(env.app, "linear-algebra", "Linear Algebra", notes)
    assert not ok
    assert any(m == "sendDocument" for m, _ in env.fake.sent)
    assert "turn on Skills (Features) and tap Install Tectonic" in env.fake.texts()[-1]


def test_the_commands_answers_and_the_template(course):
    env = course
    assert env.say("/notes pdf").startswith("Which course?")
    assert env.say("/notes pdf nonsense").startswith("I don't know a course called nonsense")
    out = env.say("/notes pdf template")
    f = coursepdf.template_file(env.app)
    assert f.is_file() and "%%BODY%%" in f.read_text() and layout.shown(env.app, f) in out
    f.write_text(f.read_text().replace(r"\begin{document}", "% mine\n\\begin{document}"))
    text, _ = coursepdf.document(env.app, "LA", coursepdf.notes_for(env.app, "linear-algebra"))
    assert "% mine" in text


@pytest.mark.skipif(not (shutil.which("tectonic") or shutil.which("pdflatex")), reason="no LaTeX engine here")
def test_a_real_pdf(course):
    """With a LaTeX engine on this computer, the document really compiles."""
    env = course
    notes = coursepdf.notes_for(env.app, "linear-algebra")
    tex = coursepdf.out_path(env.app, "linear-algebra")
    tex.parent.mkdir(parents=True, exist_ok=True)
    tex.write_text(coursepdf.document(env.app, "Linear Algebra", notes)[0])
    ok, err = skills_mod.compile_tex(env.app, tex, timeout=300)
    assert ok, err
    assert tex.with_suffix(".pdf").read_bytes().startswith(b"%PDF")
