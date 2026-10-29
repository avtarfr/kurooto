"""Checking LaTeX an AI wrote, before and after compiling it, so a request fixes its own document instead of answering
that it can't compile (0.9.0, N2b).

    check(text, folder)    a static self-check, before the first compile: unbalanced braces and \\begin/\\end,
                           commands that need a package that isn't loaded (xcolor's colour mixes such as
                           blue!50!black, also in hyperref's options; tikz and pgfplots; booktabs' rules; amsmath's
                           environments; ...), an optional argument with a "]" inside that needs braces
                           (\\begin{thm}[$E_h[g]$] -> \\begin{thm}[{$E_h[g]$}]), \\input/\\include/\\includegraphics
                           of files that aren't there, and minted (it needs shell escape, which is always off)
    log_errors(log)        the first errors of a failed compile, each with its line ("line 12: Undefined control
                           sequence \\E")
    compile_checked(...)   the compile tool's answer: the self-check, then one compile with shell escape off in a
                           copy of the source's folder; on a failure, the errors with their lines and what to do next.
                           A file's failed tries are counted: after the third the AI is told to stop and report the
                           error that's left, with its line.

Nothing here edits the document: the AI fixes its own source and calls the tool again. N2's compile_latex
(core/tools.py, branch f/v090-tools) and this file's thin version (core/studyflow.py: compile_latex when N2's tool isn't
there) both answer through compile_checked.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App

MAX_TRIES = 3  # failed compiles of one file before the AI is told to stop and report
LATEX_TIMEOUT = 300  # seconds for one compile (Tectonic's first run fetches packages)
COPY_MAX = (500, 50 * 2**20)  # files and bytes of the source's folder copied to compile in (its \input, figures)
MAX_FINDINGS = 12

# command or environment -> (the packages any of which provides it, why). Checked only when none of them is loaded,
# directly or through a package that loads it (LOADS).
NEEDS: list[tuple[re.Pattern, tuple[str, ...], str]] = [
    (re.compile(r"\\(?:textcolor|color|colorbox|fcolorbox|pagecolor|definecolor)\b"), ("xcolor", "color"), "colour"),
    (re.compile(r"\\begin\{(?:tikzpicture|scope)\}|\\tikz\b|\\usetikzlibrary\b"), ("tikz",), "TikZ"),
    (re.compile(r"\\begin\{(?:axis|semilogxaxis|semilogyaxis|loglogaxis)\}|\\addplot\b"), ("pgfplots",), "plots"),
    (re.compile(r"\\(?:toprule|midrule|bottomrule|cmidrule)\b"), ("booktabs",), "table rules"),
    (
        re.compile(
            r"\\begin\{(?:align|align\*|gather|gather\*|multline|multline\*|split|aligned|cases|pmatrix|bmatrix)\}"
            r"|\\(?:text|DeclareMathOperator|eqref|dfrac|tfrac|binom)\b"
        ),
        ("amsmath", "mathtools"),
        "AMS maths",
    ),
    (re.compile(r"\\(?:mathbb|mathfrak)\b"), ("amssymb", "amsfonts"), "blackboard letters"),
    (re.compile(r"\\begin\{proof\}|\\theoremstyle\b|\\qedhere\b"), ("amsthm",), "proofs"),
    (re.compile(r"\\(?:href|hypersetup|url)\b"), ("hyperref", "url"), "links"),
    (re.compile(r"\\includegraphics\b"), ("graphicx", "graphics"), "pictures"),
    (re.compile(r"\\(?:newtcolorbox|tcbset)\b|\\begin\{tcolorbox\}"), ("tcolorbox",), "boxes"),
    (re.compile(r"\\begin\{(?:enumerate|itemize|description)\}\[[^\]]*="), ("enumitem",), "list options"),
    (re.compile(r"\\(?:SI|si)\{"), ("siunitx",), "units"),
    (re.compile(r"\\begin\{lstlisting\}|\\lstinline\b"), ("listings",), "code listings"),
]
# packages (and classes) that load others
LOADS = {
    "tikz": {"xcolor", "pgf", "graphicx"},
    "pgfplots": {"tikz", "xcolor", "pgf", "graphicx"},
    "tcolorbox": {"xcolor", "tikz", "pgf"},
    "mathtools": {"amsmath"},
    "amssymb": {"amsfonts"},
    "beamer": {"xcolor", "hyperref", "amsmath", "amssymb", "graphicx", "tikz", "pgf", "amsthm", "url"},
    "hyperref": {"url"},
    "amsart": {"amsmath", "amsthm", "amsfonts"},
    "amsbook": {"amsmath", "amsthm", "amsfonts"},
    "physics": {"amsmath"},
    "empheq": {"mathtools", "amsmath"},
}
# a colour mix (xcolor's syntax: blue!50!black, red!20), anywhere a colour goes
MIX = re.compile(r"\b[a-zA-Z]+!\d{1,3}(?:![a-zA-Z]+)?\b")
COLOUR_KEYS = re.compile(r"\b(?:link|cite|url|file|menu|run|anchor)?(?:color|bordercolor)\s*=\s*\{?([^,}\]\s]+)")
NAMED_COLOURS = {"black", "white", "red", "green", "blue", "cyan", "magenta", "yellow"}  # color/hyperref know these
VERBATIM = re.compile(r"\\begin\{(verbatim\*?|lstlisting|minted|comment)\}.*?\\end\{\1\}", re.S)
INPUT = re.compile(r"\\(input|include|includegraphics)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
GRAPHIC_EXT = ("", ".pdf", ".png", ".jpg", ".jpeg", ".eps")


@dataclass
class Finding:
    line: int
    what: str  # what's wrong, in a sentence
    fix: str = ""  # what to change

    def __str__(self) -> str:
        return f"line {self.line}: {self.what}" + (f" Fix: {self.fix}" if self.fix else "")


def _strip(text: str) -> str:
    """The source with comments and verbatim blocks blanked out (same length and lines), so neither counts."""

    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m[0])

    text = VERBATIM.sub(blank, text)
    return re.sub(r"(?<!\\)%[^\n]*", blank, text)


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def packages(text: str) -> set[str]:
    """The packages a document loads, the class among them, and what they load in turn."""
    found: set[str] = set()
    for m in re.finditer(r"\\(?:usepackage|RequirePackage|documentclass)\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", text):
        found |= {p.strip() for p in m[1].split(",") if p.strip()}
    for _ in range(3):
        for p in list(found):
            found |= LOADS.get(p, set())
    return found


def _braces(text: str) -> list[Finding]:
    stack: list[int] = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2  # \{ \} \\ are characters, not groups
            continue
        if c == "{":
            stack.append(i)
        elif c == "}":
            if not stack:
                return [Finding(_line(text, i), "a closing brace } with no opening one.", "remove it or add the {")]
            stack.pop()
        i += 1
    if stack:
        return [Finding(_line(text, stack[-1]), "an opening brace { that's never closed.", "add the closing }")]
    return []


def _environments(text: str) -> list[Finding]:
    stack: list[tuple[str, int]] = []
    for m in re.finditer(r"\\(begin|end)\s*\{([^}]+)\}", text):
        name, at = m[2].strip(), _line(text, m.start())
        if m[1] == "begin":
            stack.append((name, at))
            continue
        if not stack:
            return [Finding(at, f"\\end{{{name}}} with no \\begin{{{name}}}.", "remove it or add the \\begin")]
        top, where = stack.pop()
        if top != name:
            return [
                Finding(
                    at,
                    f"\\end{{{name}}} closes \\begin{{{top}}} from line {where}.",
                    f"close {top} first (\\end{{{top}}}), or fix the name",
                )
            ]
    if stack:
        name, where = stack[-1]
        return [Finding(where, f"\\begin{{{name}}} is never closed.", f"add \\end{{{name}}}")]
    return []


def _optional_args(text: str) -> list[Finding]:
    """An optional argument with a [ ... ] inside it that isn't in braces: LaTeX ends the argument at the first "]",
    so \\begin{concept}[Lemma: $E_h[g(X)]=b$] breaks. The fix is braces around the whole argument."""
    out = []
    for m in re.finditer(r"\\(?:begin\s*\{[^}]+\}|item|section\*?|subsection\*?|caption|paragraph)\s*\[", text):
        i, depth, square, nested = m.end(), 0, 0, False
        while i < len(text):
            c = text[i]
            if c == "\\":
                i += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif depth == 0 and c == "[":
                square += 1
                nested = True
            elif depth == 0 and c == "]":
                if not square:
                    break
                square -= 1
            i += 1
        if nested and depth == 0:
            inner = text[m.end() : i]
            head = text[m.start() : m.end() - 1].strip()
            out.append(
                Finding(
                    _line(text, m.start()),
                    f"the optional argument of {head} has square brackets inside, so it ends too early.",
                    f"put it in braces: {head}[{{{inner.strip()}}}]",
                )
            )
    return out


def _needs(text: str, loaded: set[str]) -> list[Finding]:
    out = []
    for rx, pkgs, what in NEEDS:
        if loaded & set(pkgs):
            continue
        m = rx.search(text)
        if m:
            out.append(
                Finding(
                    _line(text, m.start()),
                    f"{m[0].strip()} ({what}) needs \\usepackage{{{pkgs[0]}}}, which isn't loaded.",
                    f"add \\usepackage{{{pkgs[0]}}} to the preamble",
                )
            )
    if "xcolor" not in loaded:  # a colour mix (blue!50!black) is xcolor's, also inside hyperref's options
        m = MIX.search(text)
        key = next((k for k in COLOUR_KEYS.finditer(text) if k[1].lower() not in NAMED_COLOURS), None)
        hit = m or key
        if hit is not None:
            shown = hit[0] if m else hit[0].strip()
            out.append(
                Finding(
                    _line(text, hit.start()),
                    f"the colour {shown} needs \\usepackage{{xcolor}}, which isn't loaded.",
                    "add \\usepackage{xcolor} before hyperref in the preamble",
                )
            )
    if re.search(r"\\(?:usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{[^}]*\bminted\b", text):
        m = re.search(r"\bminted\b", text)
        out.append(
            Finding(
                _line(text, m.start() if m else 0),
                "minted needs shell escape, which is always off here.",
                "use listings (\\usepackage{listings}, \\begin{lstlisting}) instead",
            )
        )
    return out


def _inputs(text: str, folder: Path | None) -> list[Finding]:
    if folder is None:
        return []
    out = []
    for m in INPUT.finditer(text):
        kind, name = m[1], m[2].strip()
        if not name or "#" in name or "\\" in name:
            continue  # a macro's argument, not a file
        exts = GRAPHIC_EXT if kind == "includegraphics" else ("", ".tex")
        base = (folder / name).resolve()
        if not any(Path(str(base) + e).is_file() for e in exts):
            out.append(
                Finding(
                    _line(text, m.start()),
                    f"\\{kind}{{{name}}}: there's no such file beside the document.",
                    "write that file there, or take the line out",
                )
            )
    return out


def check(text: str, folder: Path | None = None) -> list[Finding]:
    """The self-check's findings for a document's source, first problems first (line order). folder: where it is, to
    look for its \\input files and pictures."""
    clean = _strip(text or "")
    loaded = packages(clean)
    found = _braces(clean) + _environments(clean) + _optional_args(clean) + _needs(clean, loaded)
    found += _inputs(clean, folder)
    return sorted(found, key=lambda f: f.line)[:MAX_FINDINGS]


def check_file(tex: Path) -> list[Finding]:
    return check(tex.read_text(encoding="utf-8", errors="replace"), tex.parent)


# ------------------------------------------------------------------------------------------- after a compile
ERR = re.compile(r"^! (.+)$", re.M)
LINE = re.compile(r"^l\.(\d+)\s?(.*)$", re.M)
TECTONIC = re.compile(r"^error: (?:[^\n:]*\.tex):(\d+): (.+)$", re.M)
MISSING = re.compile(r"File `([^']+)\.(sty|cls)' not found")


def log_errors(log: str, limit: int = 5) -> list[str]:
    """The first errors of a compile's log (pdflatex's "! ..." with its "l.12 ..." line, or Tectonic's
    "error: x.tex:12: ..."), each with its line and the text it was at."""
    out: list[str] = []
    for m in TECTONIC.finditer(log or ""):
        out.append(f"line {m[1]}: {m[2].strip()}")
    for m in ERR.finditer(log or ""):
        what = m[1].strip()
        miss = MISSING.search(what)
        if miss:
            out.append(
                f"{miss[1]}.{miss[2]} isn't installed on this computer: take \\usepackage{{{miss[1]}}} out or use "
                "another package"
            )
            continue
        nxt = LINE.search(log, m.end(), m.end() + 1500)
        if nxt:
            near = nxt[2].strip()
            out.append(f"line {nxt[1]}: {what}" + (f" (at: {near[-60:]})" if near else ""))
        else:
            out.append(what)
    return list(dict.fromkeys(out))[:limit]


# ---------------------------------------------------------------------------------------------- the compile
_TRIES: dict[str, int] = {}  # a file's failed compiles in a row (this process), reset when one works
_TRIES_LOCK = threading.Lock()


def _workdir(tex: Path, tmp: Path) -> Path:
    """A copy to compile in, so the engine's leftovers never land in your folders: the source's folder when it's small
    (its \\input files and figures come along), else the .tex alone. Hidden files stay behind."""
    src, n, size = tex.parent, 0, 0
    files = []
    for f in src.rglob("*"):
        rel = f.relative_to(src)
        if any(part.startswith(".") for part in rel.parts) or not f.is_file() or f.is_symlink():
            continue
        n, size = n + 1, size + f.stat().st_size
        if n > COPY_MAX[0] or size > COPY_MAX[1]:
            files = []
            break
        files.append(rel)
    work = tmp / "src"
    for rel in files or [Path(tex.name)]:
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, work / rel)
    return work / tex.name


def default_dest(app: App, tex: Path) -> Path:
    """Where the PDF goes when the caller doesn't say: beside the source when that's in the files folder or the course
    files, else the files folder's (or the layout's) place for LaTeX documents. Never the notes folder's own root."""
    from kurooto.core import layout, places

    own = [r for r in (places.files_folder(app), places.course_files(app), places.work_folder(app)) if r is not None]
    if places.inside(tex, own):
        return tex.parent
    if places.files_folder(app) is None and places.inside(tex, places.write_roots(app)):
        if tex.parent.resolve() != places.notes_root(app).resolve():
            return tex.parent
    return layout.file_dir(app, "latex")


def resolve(app: App, path: str) -> tuple[Path | None, str]:
    """The .tex file the AI named (absolute, or in the notes), if it may read it; (None, why) otherwise."""
    from kurooto.core import places

    raw = str(path or "").strip().removeprefix("file://")
    if not raw:
        return None, "compile_latex needs the .tex file's path."
    tex = Path(os.path.expanduser(raw))
    if not tex.is_absolute():
        tex = Path(app.workspace) / tex
    if tex.suffix.lower() != ".tex" or not tex.is_file():
        return None, f"There's no .tex file at {raw}."
    if not places.inside(tex, places.read_roots(app)):
        return None, "That file is outside the folders I may read."
    return tex.resolve(), ""


def compile_checked(app: App, path: str, dest=None) -> str:
    """The compile tool's answer. The self-check first (its findings come back with the result, a compile is tried
    anyway: a finding can be wrong, a class may load the package); then one compile with shell escape off
    (modules/skills.py:compile_tex) in a copy of the source's folder; the PDF copied to dest(app, tex) (default_dest).
    A failure gives the errors with their lines and says to fix the source and try again, up to MAX_TRIES; after the
    last, to stop and report the error that's left with its line."""
    from kurooto.modules import skills

    tex, why = resolve(app, path)
    if tex is None:
        return why
    try:
        findings = check_file(tex)
    except OSError as e:
        return f"I couldn't read {tex.name}: {e}"
    found = "\n".join(f"- {f}" for f in findings)
    if not skills.pdf_engine(app):
        return "There's no LaTeX on this computer (TeX Live, MiKTeX or Tectonic); ask them to install one. " + (
            f"The self-check found:\n{found}" if found else "The self-check found nothing wrong."
        )
    out = (dest or default_dest)(app, tex)
    key = str(tex)
    with tempfile.TemporaryDirectory(prefix="kurooto-tex-") as tmp:
        work = _workdir(tex, Path(tmp))
        ok, err = skills.compile_tex(app, work, timeout=LATEX_TIMEOUT)
        log = work.with_suffix(".log")
        errors = log_errors(log.read_text(encoding="utf-8", errors="replace") if log.is_file() else "")
        pdf = work.with_suffix(".pdf")
        if ok and pdf.is_file():
            out.mkdir(parents=True, exist_ok=True)
            final = out / (tex.stem + ".pdf")
            shutil.copyfile(pdf, final)
            with _TRIES_LOCK:
                _TRIES.pop(key, None)
            app.events.emit("latex_compiled", findings=len(findings))
            return f"Compiled: {final}" + (f"\nThe self-check also noted (check them):\n{found}" if found else "")
    with _TRIES_LOCK:
        _TRIES[key] = tries = _TRIES.get(key, 0) + 1
    app.events.emit("latex_compile_failed", tries=tries, error=(errors or [err or "failed"])[0][:200])
    lines = [f"It didn't compile (try {tries} of {MAX_TRIES})."]
    if errors or err:
        lines.append("The first errors:\n" + "\n".join(f"- {e}" for e in errors or err.splitlines()[:6]))
    if found:
        lines.append("The self-check found:\n" + found)
    if tries >= MAX_TRIES:
        lines.append(
            "That was the last try: stop here and tell them the error that's left, with its line, and where the .tex "
            "is. Don't say you can't compile: say what's wrong."
        )
    else:
        lines.append("Fix the source (the first error first: it often causes the rest), then call compile_latex again.")
    return "\n".join(lines)
