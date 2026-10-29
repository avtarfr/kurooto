"""LaTeX an AI wrote, checked before and after compiling (0.9.0, N2b): the static self-check (two real mistakes from a
night's request among them), the first errors of a log with their lines, and the compile tool's answer, which counts
the tries and says to stop after the third. The compile itself is faked, except one real compile when LaTeX is here."""

import shutil

import pytest

from kurooto.core import latexcheck as L
from kurooto.modules import skills

HYPERREF_COLOUR = r"""\documentclass{article}
\usepackage{amsmath}
\usepackage[colorlinks=true,linkcolor=blue!50!black,urlcolor=blue]{hyperref}
\begin{document}
See \href{https://example.com}{the notes}.
\end{document}
"""
CONCEPT_BRACKETS = r"""\documentclass{article}
\usepackage{amsmath,amsthm}
\newtheorem{concept}{Concept}
\newcommand{\E}{\mathrm{E}}
\newcommand{\gt}{g}
\newcommand{\gb}{b}
\begin{document}
\begin{concept}[Lemma: $\E_h[\gt(X)]=\gb$]
Unbiased.
\end{concept}
\begin{concept}[{Fine: $\E[X]$}]
Braced already.
\end{concept}
\end{document}
"""


def lines(found):
    return [str(f) for f in found]


def test_a_colour_mix_in_hyperrefs_options_needs_xcolor():
    found = lines(L.check(HYPERREF_COLOUR))
    assert found == [
        "line 3: the colour blue!50!black needs \\usepackage{xcolor}, which isn't loaded. Fix: add "
        "\\usepackage{xcolor} before hyperref in the preamble"
    ]
    assert L.check(HYPERREF_COLOUR.replace("\\usepackage{amsmath}", "\\usepackage{amsmath,xcolor}")) == []


def test_square_brackets_inside_an_optional_argument_need_braces():
    found = L.check(CONCEPT_BRACKETS)
    assert len(found) == 1 and found[0].line == 8
    assert found[0].fix == "put it in braces: \\begin{concept}[{Lemma: $\\E_h[\\gt(X)]=\\gb$}]"


def test_braces_environments_packages_and_missing_files(tmp_path):
    (tmp_path / "part1.tex").write_text("x", "utf-8")
    (tmp_path / "fig.png").write_bytes(b"png")
    tex = r"""\documentclass{article}
\begin{document}
% a } in a comment doesn't count, nor \{ escaped
\begin{itemize}
\item one {two
\end{enumerate}
\toprule
\begin{tikzpicture}\end{tikzpicture}
\begin{align} a \end{align}
\input{part1}
\input{part2}
\includegraphics{fig}
\includegraphics{missing}
\end{document}
"""
    found = lines(L.check(tex, tmp_path))
    assert any(x.startswith("line 5: an opening brace {") for x in found)
    assert any(x.startswith("line 6: \\end{enumerate} closes \\begin{itemize} from line 4.") for x in found)
    assert any("\\toprule (table rules) needs \\usepackage{booktabs}" in x for x in found)
    assert any("(TikZ) needs \\usepackage{tikz}" in x for x in found)
    assert any("(AMS maths) needs \\usepackage{amsmath}" in x for x in found)
    assert any(x.startswith("line 11: \\input{part2}: there's no such file") for x in found)
    assert any(x.startswith("line 13: \\includegraphics{missing}") for x in found)
    assert not any("part1" in x or "{fig}" in x for x in found)
    assert "graphicx" in " ".join(found)  # \includegraphics without graphicx
    pgf = "\\documentclass{article}\\usepackage{pgfplots}\\begin{document}\\begin{tikzpicture}\\color{red!20}"
    assert not any("tikz" in x or "colour" in x for x in lines(L.check(pgf + "\\end{tikzpicture}\\end{document}")))
    assert "shell escape" in " ".join(lines(L.check("\\usepackage{minted}\\begin{document}\\end{document}")))


def test_the_first_errors_of_a_log_come_with_their_lines():
    log = """This is pdfTeX
! Undefined control sequence.
l.12 Text \\gt
              (X)
! LaTeX Error: File `pgfplots.sty' not found.
"""
    assert L.log_errors(log) == [
        "line 12: Undefined control sequence. (at: Text \\gt)",
        "pgfplots.sty isn't installed on this computer: take \\usepackage{pgfplots} out or use another package",
    ]
    assert L.log_errors("error: notes.tex:7: Missing $ inserted") == ["line 7: Missing $ inserted"]


@pytest.fixture
def files(env, tmp_path):
    env.app.settings.set("files.folder", str(tmp_path / "files"))
    d = tmp_path / "files" / "an2"
    d.mkdir(parents=True)
    return d


def test_the_tool_counts_tries_and_says_to_stop_after_the_third(env, files, monkeypatch):
    tex = files / "notes.tex"
    tex.write_text(CONCEPT_BRACKETS, "utf-8")
    monkeypatch.setattr(skills, "pdf_engine", lambda app: "pdflatex")

    def fail(app, work, timeout=0):
        work.with_suffix(".log").write_text("! Missing $ inserted.\nl.8 \\begin{concept}[Lemma: $\\E_h[\n", "utf-8")
        return False, "failed"

    monkeypatch.setattr(skills, "compile_tex", fail)
    out = L.compile_checked(env.app, str(tex))
    assert out.startswith("It didn't compile (try 1 of 3).") and "- line 8: Missing $ inserted." in out
    assert "put it in braces" in out and "call compile_latex again" in out
    L.compile_checked(env.app, str(tex))
    out = L.compile_checked(env.app, str(tex))
    assert "(try 3 of 3)" in out and "That was the last try" in out and "Don't say you can't compile" in out

    def works(app, work, timeout=0):
        work.with_suffix(".pdf").write_bytes(b"%PDF ok")
        return True, ""

    monkeypatch.setattr(skills, "compile_tex", works)
    tex.write_text(CONCEPT_BRACKETS.replace("[Lemma: $\\E_h[\\gt(X)]=\\gb$]", "[{Lemma}]"), "utf-8")
    out = L.compile_checked(env.app, str(tex))
    assert out == f"Compiled: {files / 'notes.pdf'}" and (files / "notes.pdf").read_bytes() == b"%PDF ok"
    assert not (files / "notes.log").exists()  # the engine's leftovers stay in the copy
    monkeypatch.setattr(skills, "compile_tex", fail)
    assert "(try 1 of 3)" in L.compile_checked(env.app, str(tex))  # a success starts the count again


def test_no_latex_here_still_gives_the_self_check(env, files, monkeypatch):
    tex = files / "x.tex"
    tex.write_text(HYPERREF_COLOUR, "utf-8")
    monkeypatch.setattr(skills, "pdf_engine", lambda app: None)
    out = L.compile_checked(env.app, str(tex))
    assert out.startswith("There's no LaTeX on this computer") and "blue!50!black" in out
    assert L.compile_checked(env.app, "/nowhere/x.tex").startswith("There's no .tex file")


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="no LaTeX on this computer")
def test_a_real_compile_of_the_fixed_document(env, files):
    tex = files / "real.tex"
    tex.write_text(HYPERREF_COLOUR.replace("\\usepackage{amsmath}", "\\usepackage{amsmath,xcolor}"), "utf-8")
    out = L.compile_checked(env.app, str(tex))
    assert out == f"Compiled: {files / 'real.pdf'}", out
