"""compile_latex (core/tools.py, N2 in 0.9.0): an agent that may not run pdflatex itself gets its PDF from Kurooto,
with shell escape off; the PDF goes beside the source in the files folder, else into it, and never into the notes
when a files folder is set. The real compile runs only where LaTeX is installed."""

from __future__ import annotations

import pytest

from kurooto.core import tools
from kurooto.modules import skills as sk

TEX = r"""\documentclass{article}
\begin{document}
\input{part}
\end{document}"""


def names(app):
    return {t.name for t in tools.agent_tools(app)}


def test_the_tool_has_a_switch(env):
    assert env.app.settings.get("tools.latex") is True
    assert "compile_latex" in names(env.app)
    env.app.settings.set("tools.latex", False)
    assert "compile_latex" not in names(env.app)


def test_where_the_pdf_goes(env, tmp_path):
    app = env.app
    notes_tex = app.workspace / "hw" / "hw08.tex"
    # no files folder: the notes are where files live, so beside the source
    assert tools.latex_dest(app, notes_tex) == notes_tex.parent
    files = tmp_path / "files"
    app.settings.set("files.folder", str(files))
    course = files / "linear-algebra" / "hw08.tex"
    assert tools.latex_dest(app, course) == course.parent
    # a files folder is set: a source in the notes never gets its PDF there
    out = tools.latex_dest(app, notes_tex)
    assert files in out.parents or out == files
    assert app.workspace not in out.parents
    assert str(files) in tools.latex_rule(app) and "compile_latex" in tools.latex_rule(app)
    app.settings.set("tools.latex", False)
    assert tools.latex_rule(app) == ""


def test_what_it_refuses(env, tmp_path, monkeypatch):
    app = env.app
    assert "needs" in tools.compile_latex(app, "")
    assert "no .tex file" in tools.compile_latex(app, str(tmp_path / "missing.tex"))
    outside = tmp_path / "elsewhere" / "x.tex"
    outside.parent.mkdir()
    outside.write_text(TEX, encoding="utf-8")
    assert "outside the folders" in tools.compile_latex(app, str(outside))
    inside = app.workspace / "x.tex"
    inside.write_text(TEX, encoding="utf-8")
    monkeypatch.setattr(sk, "pdf_engine", lambda a: None)
    assert "no LaTeX" in tools.compile_latex(app, "x.tex")


def test_errors_come_back(env, monkeypatch):
    app = env.app
    f = app.workspace / "bad.tex"
    f.write_text(TEX, encoding="utf-8")
    monkeypatch.setattr(sk, "pdf_engine", lambda a: "pdflatex")
    seen = []

    def fake(a, tex, timeout=900):
        seen.append((tex, timeout))
        return False, "! Undefined control sequence."

    monkeypatch.setattr(sk, "compile_tex", fake)
    out = tools.compile_latex(app, str(f))
    assert "Undefined control sequence" in out
    assert seen[0][0].parent != f.parent and seen[0][1] == tools.LATEX_TIMEOUT  # compiled in a copy
    assert not (app.workspace / "bad.pdf").exists()


def test_real_compile(env, tmp_path):
    """Runs where LaTeX is installed: the \\input beside it comes along, nothing but the PDF lands in the folder."""
    app = env.app
    if not sk.pdf_engine(app):
        pytest.skip("no LaTeX here")
    files = tmp_path / "files"
    app.settings.set("files.folder", str(files))
    d = files / "algebra"
    d.mkdir(parents=True)
    (d / "hw.tex").write_text(TEX, encoding="utf-8")
    (d / "part.tex").write_text("Rank--nullity.\n", encoding="utf-8")
    out = tools.run_tool(app, "compile_latex", {"path": str(d / "hw.tex")})
    assert out == f"Compiled: {d / 'hw.pdf'}", out
    assert sorted(p.name for p in d.iterdir()) == ["hw.pdf", "hw.tex", "part.tex"]
