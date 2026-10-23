"""The LaTeX writing tracker (the Research add-on): a nightly build of the LaTeX folders you attach, and one morning
line when a build broke or you wrote something.

You attach a folder yourself (`/latex add ~/papers/thesis [main.tex]`, a typed command: core/tap.py's repo.attach);
nothing is searched for on the disk. Each night (research_addon.latex_when) each attached document is built with
Tectonic (untrusted mode: no shell escape), or the computer's own LaTeX when Tectonic isn't installed, into Kurooto's
cache folder: your folder gets no build files. From the build's log come the errors (with their line), undefined
references and missing citations; from the .tex files the document takes in (\\input, \\include, \\subfile) comes a
word count (an estimate, like texcount's: prose only, no maths, no commands), kept per day so "words added since
yesterday" is today's count less the last one before today.

A missing citation can get a BibTeX entry suggested by your AI, only when you tap for it; the entry comes as a message
with Add to <file>.bib / Discard, and nothing is written to your .bib until you tap Add.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import egress, proc
from kurooto.core.clock import now
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

STATE = "research-latex.json"
SKIP_DIRS = {".git", "node_modules", "build", "_build", "out", "__pycache__"}
MAIN_NAMES = ("main.tex", "thesis.tex", "paper.tex", "report.tex", "article.tex")
MAX_FILES = 300
KEEP_DAYS = 60


# --------------------------------------------------------------------------------------------- the files
def mains(folder: Path) -> list[Path]:
    """The documents in a folder: .tex files (three levels down at most) with \\documentclass in them."""
    out = []
    for root, dirs, files in os.walk(folder):
        depth = len(Path(root).relative_to(folder).parts)
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS and depth < 3]
        for f in files:
            if f.endswith(".tex"):
                p = Path(root) / f
                try:
                    head = p.read_text(encoding="utf-8", errors="replace")[:20000]
                except OSError:
                    continue
                if re.search(r"^[^%\n]*\\documentclass", head, re.M):
                    out.append(p)
    return sorted(out)


def pick_main(folder: Path, given: str = "") -> tuple[Path | None, str]:
    """The document to build: the one you named, the only one there, or one called main.tex (thesis.tex, ...)."""
    if given:
        p = (folder / given).resolve()
        if not p.is_file() or not p.name.endswith(".tex"):
            return None, f"there's no {given} in {folder}"
        return p, ""
    found = mains(folder)
    if not found:
        return None, f"no LaTeX document (a .tex with \\documentclass) in {folder}"
    if len(found) == 1:
        return found[0], ""
    for name in MAIN_NAMES:
        hit = [p for p in found if p.name == name]
        if len(hit) == 1:
            return hit[0], ""
    names = ", ".join(str(p.relative_to(folder)) for p in found[:5])
    return None, f"{len(found)} documents there ({names}): name one, /latex add {folder} <file.tex>"


INCLUDE = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")


def _no_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def tex_files(main: Path) -> list[Path]:
    """The main file and every .tex it takes in (\\input, \\include, \\subfile), inside its folder."""
    root = main.parent.resolve()
    seen: list[Path] = []
    todo = [main.resolve()]
    while todo and len(seen) < MAX_FILES:
        f = todo.pop(0)
        if f in seen or not f.is_file():
            continue
        seen.append(f)
        try:
            text = _no_comments(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for name in INCLUDE.findall(text):
            name = name.strip()
            for base in (root, f.parent):
                p = (base / name).resolve()
                if p.suffix != ".tex":
                    p = p.with_name(p.name + ".tex")
                if p.is_file() and p.is_relative_to(root):
                    todo.append(p)
                    break
    return seen


MATH_ENVS = r"equation|align|alignat|gather|multline|eqnarray|displaymath|math|flalign|tikzpicture|verbatim|lstlisting"
NO_PROSE = (
    r"\\(?:label|ref|eqref|cref|Cref|autoref|pageref|nameref|cite\w*|citep|citet|input|include|subfile|usepackage|"
    r"documentclass|begin|end|includegraphics|bibliography\w*|addbibresource|url|href|newcommand|renewcommand|"
    r"DeclareMathOperator|setlength|vspace|hspace|bibitem)\*?(?:\s*\[[^\]]*\])*(?:\s*\{[^{}]*\})?"
)


def prose(text: str, body_only: bool = False) -> str:
    """The words of a .tex file: no comments, maths, commands or references."""
    t = _no_comments(text)
    if body_only:
        m = re.search(r"\\begin\{document\}(.*?)(?:\\end\{document\}|\Z)", t, re.S)
        t = m.group(1) if m else ""
    t = re.sub(rf"\\begin\{{({MATH_ENVS})\*?\}}.*?\\end\{{\1\*?\}}", " ", t, flags=re.S)
    t = re.sub(r"\$\$.*?\$\$|\$[^$]*\$|\\\[.*?\\\]|\\\(.*?\\\)", " ", t, flags=re.S)
    t = re.sub(NO_PROSE, " ", t)
    t = re.sub(r"\\[A-Za-z@]+\*?|\\.", " ", t)
    return re.sub(r"[{}\[\]&~^_]", " ", t)


WORD = re.compile(r"[^\W\d_][\w'’-]*")


def count_words(main: Path) -> int:
    total = 0
    for f in tex_files(main):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total += len(WORD.findall(prose(text, body_only=f == main.resolve())))
    return total


def bib_files(main: Path) -> list[Path]:
    """The .bib files the document names (\\bibliography{a,b} or \\addbibresource{x.bib})."""
    out = []
    for f in tex_files(main):
        try:
            text = _no_comments(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for names in re.findall(r"\\bibliography\s*\{([^}]+)\}", text):
            out += [n.strip() if n.strip().endswith(".bib") else n.strip() + ".bib" for n in names.split(",")]
        out += [n.strip() for n in re.findall(r"\\addbibresource(?:\[[^\]]*\])?\s*\{([^}]+)\}", text)]
    root = main.parent.resolve()
    paths = []
    for n in out:
        p = (root / n).resolve()
        if p.is_relative_to(root) and p not in paths:
            paths.append(p)
    return paths


def cite_context(main: Path, key: str) -> str:
    """The sentence a citation key is cited in (for the AI to tell which paper it is)."""
    for f in tex_files(main):
        try:
            text = _no_comments(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        m = re.search(rf"\\cite\w*\*?(?:\[[^\]]*\])*\{{[^}}]*\b{re.escape(key)}\b[^}}]*\}}", text)
        if m:
            start = max(text.rfind(".", 0, m.start()) + 1, m.start() - 300)
            end = text.find(".", m.end())
            end = len(text) if end < 0 else min(end + 1, m.end() + 300)
            return re.sub(r"\s+", " ", text[start:end]).strip()
    return ""


# ------------------------------------------------------------------------------------------------- the log
def _unwrap(text: str) -> str:
    """TeX breaks log lines at 79 characters: join them back."""
    out, buf = [], ""
    for ln in text.splitlines():
        buf += ln
        if len(ln) != 79:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return "\n".join(out)


def parse_log(log: str, stderr: str = "", blg: str = "") -> dict:
    """{"errors": [{"line", "file", "message"}], "refs": [...], "cites": [...]} from a build's log."""
    text = _unwrap(log)
    lines = text.splitlines()
    errors: list[dict] = []
    for i, ln in enumerate(lines):
        if ln.startswith("! "):
            msg = ln[2:].strip()
            line = next((int(m[1]) for x in lines[i + 1 : i + 8] if (m := re.match(r"l\.(\d+)", x))), None)
            errors.append({"line": line, "file": "", "message": msg})
    for ln in stderr.splitlines():
        m = re.match(r"\s*error:\s*(?:(?P<f>[^:\n]+\.tex):(?P<l>\d+):\s*)?(?P<m>.+)", ln)
        if m and not re.search(r"halted on|potentially-recoverable|failed to compile|see the log", m["m"], re.I):
            errors.append({"line": int(m["l"]) if m["l"] else None, "file": m["f"] or "", "message": m["m"].strip()})
    seen, uniq = set(), []
    for e in errors:
        k = (e["line"], e["message"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    refs = re.findall(r"Reference [`'](.+?)' on page \d+ undefined", text)
    cites = re.findall(r"Citation [`'](.+?)' on page \d+ undefined", text)
    cites += re.findall(r"could not be found\s*\(biblatex\)\s*in the database:\s*\(biblatex\)\s*(\S+)", text)
    cites += re.findall(r"I didn't find a database entry for \"([^\"]+)\"", blg)
    return {"errors": uniq[:20], "refs": list(dict.fromkeys(refs))[:50], "cites": list(dict.fromkeys(cites))[:50]}


# ------------------------------------------------------------------------------------------------ the build
def engine(app: App) -> tuple[str, str] | None:
    """("tectonic", path) or ("latexmk" / "pdflatex", path), or None: nothing to build with."""
    from kurooto.modules.skills import system_tex, tectonic

    exe = tectonic(app)
    if exe:
        return "tectonic", exe
    own = system_tex(app)
    return (Path(own).stem.lower(), own) if own else None


def build(app: App, main: Path, outdir: Path, timeout: int = 900) -> dict:
    """Build one document into outdir (Kurooto's cache, never your folder) and read its log."""
    from kurooto.modules.skills import TEX_ENV

    eng = engine(app)
    if eng is None:
        return {"ok": False, "engine": "", "errors": [], "refs": [], "cites": [], "missing_engine": True}
    kind, exe = eng
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    try:
        if kind == "tectonic":
            egress.handed("Tectonic", "Research add-on: LaTeX tracker")  # it fetches LaTeX packages it lacks
            env = {**os.environ, "TECTONIC_CACHE_DIR": str(app.paths.cache / "tectonic")}
            res = proc.run(
                [exe, "--untrusted", "--chatter", "minimal", "--keep-logs", "--outdir", str(outdir), main.name],
                timeout=timeout,
                env=env,
                cwd=main.parent,
            )
        elif kind == "latexmk":
            res = proc.run(
                [exe, "-norc", "-pdf", "-interaction=nonstopmode", "-no-shell-escape", "-silent", "-f",
                 f"-outdir={outdir}", main.name],
                timeout=timeout,
                env=TEX_ENV,
                cwd=main.parent,
            )  # fmt: skip
        else:  # pdflatex: twice, for the references
            for _ in range(2):
                res = proc.run(
                    [exe, "-interaction=nonstopmode", "-no-shell-escape", f"-output-directory={outdir}", main.name],
                    timeout=timeout,
                    env=TEX_ENV,
                    cwd=main.parent,
                )
    except OSError as e:
        return {"ok": False, "engine": kind, "errors": [{"line": None, "file": "", "message": str(e)}], "refs": [],
                "cites": []}  # fmt: skip

    def read(suffix: str) -> str:
        try:
            return (outdir / (main.stem + suffix)).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    found = parse_log(read(".log"), res.err + "\n" + res.out, read(".blg"))
    if res.code is None:
        found["errors"].insert(0, {"line": None, "file": "", "message": f"the build took over {timeout // 60} min"})
    elif not res.ok and not found["errors"]:
        found["errors"].append({"line": None, "file": "", "message": f"{kind} stopped (exit {res.code})"})
    return {"ok": not found["errors"], "engine": kind, "seconds": round(time.monotonic() - t0, 1), **found}


# ------------------------------------------------------------------------------------------------ the tracker
def key(path: str) -> str:
    return hashlib.sha1(str(path).encode()).hexdigest()[:10]  # noqa: S324 (a name, not security)


def name_of(rec: dict) -> str:
    return Path(rec.get("path") or "").name or "document"


class Tracker:
    """The attached documents (settings research_addon.latex_repos) and what each night's build found
    (state/research-latex.json)."""

    def __init__(self, app: App):
        self.app = app
        self.file = app.paths.state / STATE

    def repos(self) -> list[dict]:
        return [r for r in self.app.settings.get("research_addon.latex_repos") or [] if isinstance(r, dict)]

    def state(self) -> dict:
        return jload(self.file, {}) or {}

    def save(self, st: dict) -> None:
        jsave(self.file, st)

    # ---------------------------------------------------------------------------------- attaching
    def attach(self, folder: str, main: str = "") -> str:
        """`/latex add <folder> [main.tex]`: you typed it (core/tap.py repo.attach)."""
        path = Path(folder).expanduser()
        if not path.is_dir():
            return f"There's no folder {folder}."
        path = path.resolve()
        tex, why = pick_main(path, main)
        if tex is None:
            return why[0].upper() + why[1:] + "."
        rel = str(tex.relative_to(path))
        repos = [r for r in self.repos() if Path(r.get("path") or "") != path]
        self.app.settings.set("research_addon.latex_repos", [*repos, {"path": str(path), "main": rel}])
        return (
            f"Following {path.name} ({rel}): a build every night, and a line in the morning when it broke or you "
            "wrote. /latex build tries it now."
        )

    def detach(self, folder: str) -> str:
        want = Path(folder).expanduser()
        keep = [
            r
            for r in self.repos()
            if Path(r.get("path") or "") != want.resolve() and Path(r.get("path") or "").name != folder.strip()
        ]
        if len(keep) == len(self.repos()):
            return f"I'm not following {folder}."
        self.app.settings.set("research_addon.latex_repos", keep)
        return f"Stopped following {folder}. Your files are as they were."

    # ---------------------------------------------------------------------------------------- nightly
    def run_all(self) -> list[dict]:
        """Build every attached document and keep what each found (and its words for today)."""
        st = self.state()
        out = []
        timeout = int(self.app.settings.get("research_addon.latex_timeout_min") or 15) * 60
        for r in self.repos():
            out.append(self.run_one(st, r, timeout))
        self.save(st)
        self.app.events.emit("latex_built", docs=len(out), broken=sum(1 for x in out if x.get("errors")))
        return out

    def run_one(self, st: dict, r: dict, timeout: int = 900) -> dict:
        folder = Path(r.get("path") or "")
        rec = st.setdefault(key(str(folder)), {"path": str(folder), "words": {}})
        main = folder / str(r.get("main") or "")
        if not main.is_file():
            res = {"ok": False, "errors": [{"line": None, "file": "", "message": f"{main} isn't there"}], "refs": [],
                   "cites": [], "engine": ""}  # fmt: skip
        else:
            res = build(self.app, main, self.app.paths.cache / "latex" / key(str(folder)), timeout)
            if not res.get("missing_engine"):
                today = now().date().isoformat()
                words = dict(rec.get("words") or {})
                words[today] = count_words(main)
                rec["words"] = dict(sorted(words.items())[-KEEP_DAYS:])
        rec["n"] = int(rec.get("n") or 0) + 1  # which build this is: the morning line tells each one once
        res = {**res, "at": now().isoformat(timespec="seconds"), "n": rec["n"], "main": str(r.get("main") or "")}
        if rec.get("last") and not rec["last"].get("missing_engine"):
            rec["prev"] = rec["last"]
        rec["last"] = res
        rec["path"] = str(folder)
        return {**res, "path": str(folder)}

    def added(self, rec: dict) -> int | None:
        """Words added since yesterday: the latest count less the last one from an earlier day."""
        words = sorted((rec.get("words") or {}).items())
        if len(words) < 2:
            return None
        return words[-1][1] - words[-2][1]

    # ---------------------------------------------------------------------------------------- the line
    def news(self, st: dict, rec: dict) -> tuple[str, bool]:
        """(what to say about one document, whether it broke) or ("", False) when nothing broke and nothing was
        written."""
        last, prev = rec.get("last") or {}, rec.get("prev") or {}
        if last.get("missing_engine"):
            return "", False
        name = name_of(rec)
        bits, broke = [], False
        errs = last.get("errors") or []
        if errs and (not prev or len(errs) > len(prev.get("errors") or [])):
            e = errs[0]
            where = f" (line {e['line']})" if e.get("line") else ""
            bits.append(f"{len(errs)} error{'s' if len(errs) > 1 else ''}: {e['message'][:80]}{where}")
            broke = True
        elif prev.get("errors") and not errs:
            bits.append("builds again")
        new_refs = [x for x in last.get("refs") or [] if x not in (prev.get("refs") or [])]
        new_cites = [x for x in last.get("cites") or [] if x not in (prev.get("cites") or [])]
        if new_refs:
            bits.append(f"undefined reference{'s' if len(new_refs) > 1 else ''} {', '.join(new_refs[:3])}")
            broke = True
        if new_cites:
            bits.append(f"missing citation{'s' if len(new_cites) > 1 else ''} {', '.join(new_cites[:3])}")
            broke = True
        n = self.added(rec)
        if n:
            bits.append(f"{n:+,} words")
        return (f"{name}: {'; '.join(bits)}" if bits else ""), broke

    def morning(self) -> tuple[str, list] | None:
        """The one morning line, for builds not reported yet: (text, buttons) or None."""
        st = self.state()
        parts, buttons = [], []
        for r in self.repos():
            rec = st.get(key(str(Path(r.get("path") or ""))))
            if not rec or not rec.get("last") or rec.get("reported") == rec["last"].get("n"):
                continue
            rec["reported"] = rec["last"].get("n")
            line, _ = self.news(st, rec)
            if line:
                parts.append(line)
            new = [c for c in rec["last"].get("cites") or [] if c not in ((rec.get("prev") or {}).get("cites") or [])]
            for c in new[: 3 - len(buttons)]:
                buttons.append([(f"BibTeX for {c[:24]}", f"rlx:{self.pend(st, rec, c)}:bib")])
        self.save(st)
        if not parts:
            return None
        return "LaTeX: " + ". ".join(parts) + ". (/latex for the rest)", buttons

    # ---------------------------------------------------------------------------------- the citations
    def pend(self, st: dict, rec: dict, cite: str) -> str:
        """A short id for a missing citation, for its button."""
        ref = hashlib.sha1(f"{rec.get('path')}|{cite}".encode()).hexdigest()[:8]  # noqa: S324 (a name)
        p = st.setdefault("_pending", {})
        p[ref] = {**p.get(ref, {}), "path": rec.get("path"), "main": (rec.get("last") or {}).get("main"), "key": cite}
        st["_pending"] = dict(list(p.items())[-100:])
        return ref

    def pending(self, ref: str) -> dict | None:
        return (self.state().get("_pending") or {}).get(ref)

    def set_pending(self, ref: str, **kw) -> None:
        st = self.state()
        p = st.setdefault("_pending", {})
        if ref in p:
            p[ref].update(kw)
            self.save(st)


def bibtex_prompt(key: str, context: str) -> str:
    return (
        f"A LaTeX document cites the key `{key}`, and the .bib file has no entry for it. The sentence it's cited in: "
        f'"{context or "(not found)"}". Which paper or book is it most likely? Answer with one BibTeX entry using '
        f"exactly the key {key}, in a ```bibtex block, then one line on how sure you are. Use only fields you're "
        "sure of (no made-up DOI or pages). If you can't tell which work it is, say so and give no entry."
    )


def entry_from(answer: str, key: str) -> str:
    """The BibTeX entry in the AI's answer (its key set to `key`), or ""."""
    m = re.search(r"@(\w+)\s*\{\s*([^,\s]*)\s*,", answer or "")
    if not m or m[1].lower() in ("comment", "string", "preamble"):
        return ""
    depth, i = 0, answer.index("{", m.start())
    for j in range(i, len(answer)):
        depth += {"{": 1, "}": -1}.get(answer[j], 0)
        if depth == 0:
            body = answer[m.start() : j + 1]
            return re.sub(r"^@(\w+)\s*\{\s*[^,\s]*\s*,", lambda x: f"@{x[1]}{{{key},", body, count=1).strip()
    return ""


def add_entry(bib: Path, key: str, entry: str) -> str:
    """Append the entry to the .bib (after you tapped Add), never twice."""
    try:
        text = bib.read_text(encoding="utf-8", errors="replace") if bib.exists() else ""
    except OSError as e:
        return f"Couldn't read {bib.name}: {e}"
    if re.search(rf"@\w+\s*\{{\s*{re.escape(key)}\s*,", text):
        return f"{bib.name} has an entry for {key} already; left as it is."
    stamp = dt.date.today().isoformat()
    add = f"\n% Added on {stamp} after you tapped Add: suggested by your AI, so check it against the paper.\n{entry}\n"
    with open(bib, "a", encoding="utf-8") as f:
        f.write(("\n" if text and not text.endswith("\n") else "") + add)
    return f"Added {key} to {bib.name}."
