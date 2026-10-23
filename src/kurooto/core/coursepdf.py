"""Course notes to PDF: one course's notes as one PDF, from a LaTeX template, beside the revision packs. `/notes pdf la`
(or the dashboard's Study pane) takes the course page, the lecture notes in date order and the concept notes they
link, turns their Markdown into LaTeX (headings, lists, tables, code, links, and your maths as it is), and makes the
PDF with Tectonic (or the computer's own LaTeX, shell escape off), sent like other files (Telegram, or a link in the
phone app's chat). No AI is used and nothing of yours changes; the .tex and the PDF are kept where revision packs go.

The template is data/latex/course-notes.tex; `/notes pdf template` puts a copy beside the study pack prompt for you to
edit (%%COURSE%%, %%DATE%%, %%BODY%% are filled in), and that copy is used from then on. When the maths in a note
doesn't compile (a macro of your own, say), the PDF is made again with the maths shown as written.
"""

from __future__ import annotations

import os
import re
import threading
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import graphwrite, layout
from kurooto.core.clock import now

if TYPE_CHECKING:
    from kurooto.app import App

MARK = "% Made by Kurooto from your notes"  # the first line of a .tex Kurooto may write over
MAX_NOTES = 300  # notes in one PDF at most
MAX_CHARS = 3_000_000  # and this much Markdown
MAX_LINKED = 150  # concept notes linked from the course's notes
DATED = re.compile(r"^\d{4}-\d\d-\d\d-")
OWN_PAGES = ("exam_prep", "doubts", "class_log")
SPECIALS = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
            "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}  # fmt: skip
HEADS = ["section", "subsection", "subsubsection", "paragraph", "subparagraph", "subparagraph"]
TOKEN = re.compile(
    r"(?P<code>`[^`\n]+`)"
    r"|(?P<dmath>\$\$.+?\$\$)"
    r"|(?P<math>(?<![\\$\w])\$(?![\s$])[^$\n]+?(?<![\s\\])\$(?![\w$]))"
    r"|(?P<pmath>\\\(.+?\\\))"
    r"|(?P<img>!\[\[[^\]\n]+\]\]|!\[[^\]\n]*\]\([^)\n]*\))"
    r"|(?P<wiki>\[\[[^\]\n]+\]\])"
    r"|(?P<link>\[[^\]\n]+\]\([^)\s]+\))"
    r"|(?P<url>https?://[^\s)>\]]+)"
)
EMPH = re.compile(
    r"\*\*(?P<b1>.+?)\*\*|__(?P<b2>.+?)__|(?<![\w*])\*(?!\s)(?P<i1>.+?)(?<!\s)\*(?![\w*])"
    r"|(?<![\w_])_(?!\s)(?P<i2>.+?)(?<!\s)_(?![\w_])|~~(?P<s>.+?)~~|==(?P<h>.+?)=="
)
LIST = re.compile(r"^(?P<ind>[ \t]*)(?P<mark>[-*+]|\d{1,3}[.)])\s+(?P<text>.*)$")


# ---------------------------------------------------------------------------------------------- Markdown
def esc(text: str) -> str:
    return "".join(SPECIALS.get(ch, ch) for ch in text)


def _url(u: str) -> str:
    return u.replace("\\", "/").replace("%", r"\%").replace("#", r"\#").replace("{", "").replace("}", "")


def inline(text: str, safe: bool = False) -> str:
    """One line of Markdown as LaTeX: maths as written (safe=True: as text), code, links, emphasis, the rest
    escaped."""
    held: list[str] = []

    def hold(s: str) -> str:
        held.append(s)
        return f"\x00{len(held) - 1}\x00"

    def token(m: re.Match) -> str:
        k, t = m.lastgroup, m.group(0)
        if k in ("dmath", "math", "pmath"):
            if safe:
                return hold(r"\texttt{" + esc(t) + "}")
            return hold(r"\[" + t[2:-2] + r"\]" if k == "dmath" else t)
        if k == "code":
            return hold(r"\texttt{" + esc(t[1:-1]) + "}")
        if k == "img":
            name = re.sub(r"^!\[\[|\]\]$|^!\[[^\]]*\]\(|\)$", "", t).split("|")[0]
            return hold(r"\emph{[image: " + esc(Path(name).name) + "]}")
        if k == "wiki":
            target, _, alias = t[2:-2].partition("|")
            shown = alias or target.split("#")[0].rsplit("/", 1)[-1].replace("-", " ")
            return hold(r"\emph{" + esc(shown.strip()) + "}")
        if k == "link":
            label, url = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", t).groups()
            if not re.match(r"https?://", url):
                return hold(esc(label))
            return hold(r"\href{" + _url(url) + "}{" + esc(label) + "}")
        bare = t.rstrip(".,;:!?'\"")  # a sentence's full stop isn't part of the address
        return hold(r"\url{" + _url(bare) + "}") + esc(t[len(bare) :])

    text = TOKEN.sub(token, text)

    def emph(s: str) -> str:
        out, last = [], 0
        for m in EMPH.finditer(s):
            out.append(esc(s[last : m.start()]))
            g = m.groupdict()
            if g["b1"] or g["b2"]:
                out.append(r"\textbf{" + emph(g["b1"] or g["b2"]) + "}")
            elif g["i1"] or g["i2"]:
                out.append(r"\emph{" + emph(g["i1"] or g["i2"]) + "}")
            else:
                out.append(emph(g["s"] or g["h"] or ""))
            last = m.end()
        out.append(esc(s[last:]))
        return "".join(out)

    out = emph(text)
    for _ in range(3):  # held pieces may hold others (a link inside emphasis)
        out = re.sub(r"\x00(\d+)\x00", lambda m: held[int(m[1])], out)
    return out


def _table(rows: list[str], safe: bool) -> list[str]:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [c for c in cells if not all(re.fullmatch(r":?-{2,}:?", x or "-") for x in c)]
    if not cells:
        return []
    n = max(len(c) for c in cells)
    col = rf"p{{\dimexpr\linewidth/{n}-2\tabcolsep\relax}}"
    out = [r"\par\smallskip{\small", r"\begin{tabular}{" + col * n + "}", r"\hline"]
    for i, c in enumerate(cells):
        c = c + [""] * (n - len(c))
        row = " & ".join((r"\textbf{" + inline(x, safe) + "}") if i == 0 else inline(x, safe) for x in c)
        out.append(row + r" \\" + (r" \hline" if i == 0 else ""))
    out += [r"\hline", r"\end{tabular}}", r"\par"]
    return out


def md_to_tex(md: str, level: int = 1, safe: bool = False) -> str:
    """A note's Markdown (without its title) as LaTeX; its headings start one level below `level` (a note is a
    section, its ## a subsection...)."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    lists: list[tuple[int, str]] = []  # (indent, "itemize" | "enumerate")
    i = 0

    def close_lists(to: int = -1) -> None:
        while lists and lists[-1][0] > to:
            out.append(r"\end{" + lists.pop()[1] + "}")

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("```") or s.startswith("~~~"):  # a code block (```math: displayed maths)
            close_lists()
            fence, lang = s[:3], s[3:].strip().lower()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                body.append(lines[i])
                i += 1
            if lang in ("math", "latex-math") and not safe:
                out.append(r"\[" + "\n".join(body) + r"\]")
            else:
                safe_body = [b.replace(r"\end{Verbatim}", r"\end {Verbatim}") for b in body]
                out += [r"\begin{Verbatim}[fontsize=\small]", *safe_body, r"\end{Verbatim}"]
            i += 1
            continue
        if s.startswith("$$") and not (len(s) > 4 and s.endswith("$$")):  # displayed maths over several lines
            close_lists()
            body = [s[2:]]
            i += 1
            while i < len(lines) and "$$" not in lines[i]:
                body.append(lines[i])
                i += 1
            if i < len(lines):
                body.append(lines[i].split("$$")[0])
            text = "\n".join(b for b in body if b.strip())
            out.append(r"\texttt{" + esc(text) + "}" if safe else r"\[" + text + r"\]")
            i += 1
            continue
        if re.match(r"\\begin\{(equation|align|gather|multline|eqnarray)\*?\}", s):  # LaTeX maths as written
            close_lists()
            env = re.match(r"\\begin\{([a-z]+\*?)\}", s)[1]
            body = [ln]
            while i + 1 < len(lines) and f"\\end{{{env}}}" not in body[-1]:
                i += 1
                body.append(lines[i])
            out += [r"\begin{Verbatim}[fontsize=\small]", *body, r"\end{Verbatim}"] if safe else body
            i += 1
            continue
        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", s)
        if h:
            close_lists()
            depth = min(max(0, len(h[1]) - 2 + level), len(HEADS) - 1)  # ## is one below the note
            out.append("\\" + HEADS[depth] + "{" + inline(h[2], safe=True) + "}")
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            close_lists()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out += _table(rows, safe)
            continue
        if s.startswith(">"):
            close_lists()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q = lines[i].strip()[1:].strip()
                q = re.sub(r"^\[!(\w+)\][+-]?\s*", lambda m: f"**{m[1].title()}.** ", q)
                quote.append(inline(q, safe) if q else "")
                i += 1
            out += [r"\begin{quote}", "\n".join(x if x else r"\par" for x in quote), r"\end{quote}"]
            continue
        if re.fullmatch(r"(?:-{3,}|\*{3,}|_{3,})", s):
            close_lists()
            out.append(r"\par\medskip\noindent\rule{\linewidth}{0.3pt}\par\medskip")
            i += 1
            continue
        m = LIST.match(ln)
        if m:
            ind = len(m["ind"].expandtabs(4))
            kind = "enumerate" if m["mark"][0].isdigit() else "itemize"
            close_lists(ind)
            if lists and lists[-1][0] == ind and lists[-1][1] != kind:
                out.append(r"\end{" + lists.pop()[1] + "}")
            if (not lists or lists[-1][0] < ind) and len(lists) < 4:
                lists.append((ind, kind))
                out.append(r"\begin{" + kind + "}")
            box = re.match(r"^\[([ xX])\]\s*", m["text"])  # a task: "- [ ] ..." / "- [x] ..."
            mark = "" if not box else (r"$\square$ " if box[1] == " " else r"$\boxtimes$ ")
            out.append(r"\item " + mark + inline(m["text"][box.end() if box else 0 :], safe))
            i += 1
            continue
        if not s:
            nxt = next((x for x in lines[i + 1 :] if x.strip()), "")
            if lists and not (LIST.match(nxt) or nxt.startswith(("  ", "\t"))):
                close_lists()
            out.append("")
            i += 1
            continue
        out.append(inline(s, safe))  # a paragraph's line (or a list item's continuation)
        i += 1
    close_lists()
    return "\n".join(out).strip() + "\n"


def split_note(text: str, fallback: str) -> tuple[str, str]:
    """(its title, its Markdown without frontmatter, the title line or Kurooto's blocks)."""
    t = text.replace("\r\n", "\n")
    t = re.sub(r"\A---\n.*?\n---[ \t]*\n", "", t, flags=re.S)
    t = graphwrite.BLOCK_ANY.sub("", t)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    m = re.search(r"(?m)^#\s+(.+?)\s*#*$", t)
    if m:
        return m[1].strip(), (t[: m.start()] + t[m.end() :]).strip("\n")
    return fallback, t.strip("\n")


# ---------------------------------------------------------------------------------------------- which notes
def _stems(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    n = 0
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                out.setdefault(f[:-3].lower(), Path(dirpath) / f)
                n += 1
        if n > 20000:
            break
    return out


def notes_for(app: App, slug: str) -> dict[str, list[Path]]:
    """{"course": [the course page], "lectures": [by date], "concepts": [the concept notes they link]}."""
    from kurooto.core.tools import note_path

    root = Path(app.workspace)
    course = layout.path(app, "course", subject=slug)
    folder = layout.path(app, "subject", subject=slug)
    lectures = []
    if folder.is_dir():
        lectures = sorted(
            (
                p
                for p in folder.rglob("*.md")
                if DATED.match(p.name) and not any(x.startswith(".") for x in p.relative_to(folder).parts)
            ),
            key=lambda p: p.name,
        )
    have = {p.resolve() for p in [course, *lectures]}
    own = {layout.path(app, k, subject=slug).resolve() for k in OWN_PAGES}
    concept_dir = layout.path(app, "concept", subject=slug, slug="x").parent.resolve()
    stems: dict[str, Path] | None = None
    linked: list[Path] = []
    for f in [course, *lectures]:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for target in sorted(graphwrite.targets(graphwrite.BLOCK_ANY.sub("", text)), key=str.lower):
            p = note_path(root, target, must_exist=True)
            if p is None and "/" not in target:
                stems = stems if stems is not None else _stems(root)
                p = stems.get(target.lower())
            if p is None:
                continue
            p = p.resolve()
            if p in have or p in own or p.name.startswith(".") or DATED.match(p.name):
                continue
            if p.parent != concept_dir and p.parent != folder.resolve():
                continue
            have.add(p)
            linked.append(p)
            if len(linked) >= MAX_LINKED:
                break
    return {
        "course": [course] if course.is_file() else [],
        "lectures": lectures,
        "concepts": sorted(linked, key=lambda p: p.stem.lower()),
    }


# ---------------------------------------------------------------------------------------------- the document
def template_file(app: App) -> Path:
    """Your copy of the template, beside the study pack prompt (kurooto/ or master/)."""
    return layout.path(app, "study_pack_prompt").parent / "course-notes-template.tex"


def template(app: App) -> str:
    try:
        f = template_file(app)
        if f.is_file():
            t = f.read_text(encoding="utf-8")
            if "%%BODY%%" in t:
                return t
    except (OSError, UnicodeDecodeError):
        pass
    return resources.files("kurooto.data").joinpath("latex", "course-notes.tex").read_text(encoding="utf-8")


def make_template(app: App) -> tuple[Path, bool]:
    """Write Kurooto's template as your copy to edit (unless it's there). Returns (its path, whether it was made)."""
    f = template_file(app)
    if f.is_file():
        return f, False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        resources.files("kurooto.data").joinpath("latex", "course-notes.tex").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return f, True


def document(app: App, name: str, notes: dict[str, list[Path]], safe: bool = False) -> tuple[str, int]:
    """The LaTeX document and how many notes went in."""
    parts: list[str] = []
    count, size = 0, 0
    groups = [("", notes["course"]), ("Lecture notes", notes["lectures"]), ("Concept notes", notes["concepts"])]
    for title, files in groups:
        if not files:
            continue
        if title:
            parts.append(r"\part*{" + title + "}\n\\addcontentsline{toc}{part}{" + title + "}\n")
        for f in files:
            if count >= MAX_NOTES or size >= MAX_CHARS:
                break
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            size += len(text)
            head, body = split_note(text, f.stem.replace("-", " "))
            parts.append(r"\section{" + inline(head, safe=True) + "}")
            parts.append(r"\knote{" + esc(layout.shown(app, f)) + "}")
            parts.append(md_to_tex(body, level=1, safe=safe))
            count += 1
    body = "\n".join(parts) or "(No notes yet.)"
    t = template(app)
    t = t.replace("%%COURSE%%", esc(name)).replace("%%DATE%%", f"{now():%d %B %Y}").replace("%%BODY%%", body)
    if not t.startswith(MARK):
        t = f"{MARK} ({now():%Y-%m-%d}): /notes pdf.\n" + t
    return t, count


def out_path(app: App, slug: str) -> Path:
    """Where the .tex goes: beside the revision packs; a file of yours with that name is never written over."""
    f = layout.file_path(app, "pack", f"course-notes-{slug}.tex", subject=slug)
    n = 2
    while f.exists():
        try:
            with f.open(encoding="utf-8", errors="replace") as fh:
                if fh.readline().startswith(MARK):
                    return f
        except OSError:
            pass
        f = f.with_name(f"course-notes-{slug}-{n}.tex")
        n += 1
    return f


# ---------------------------------------------------------------------------------------------- the command
def course_of(app: App, text: str) -> tuple[str | None, str]:
    """(the course's slug, its name) from "/notes pdf <course>": a subject, else a folder of notes by that name."""
    text = text.strip()
    sub = app.modules.get("subjects")
    if sub is not None and app.is_on("subjects"):
        sl = sub.resolve(text)
        if sl:
            return sl, sub.name_of(sl)
    sl = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if sl and layout.path(app, "subject", subject=sl).is_dir():
        return sl, text
    return None, text


def command(app: App, arg: str) -> str:
    """/notes pdf <course> (and /notes pdf template)."""
    a = arg.strip()
    if a.lower() == "template":
        f, made = make_template(app)
        where = layout.shown(app, f)
        return (
            f"Your copy of the template is {where}{'' if made else ' (it was there already)'}. Edit it as you like; "
            "%%COURSE%%, %%DATE%% and %%BODY%% are filled in. Delete it to go back to Kurooto's."
        )
    if not a:
        return "Which course? /notes pdf la (its course page, lecture notes and the concept notes they link)"
    slug, name = course_of(app, a)
    if slug is None:
        return f"I don't know a course called {a}: /subject lists yours."
    notes = notes_for(app, slug)
    n = sum(len(v) for v in notes.values())
    if not n:
        return f"No notes for {name} yet (no course page and no lecture notes)."
    threading.Thread(target=build, args=(app, slug, name, notes), name="course-pdf", daemon=True).start()
    app.events.emit("course_pdf_started", notes=n)
    return f"Making a PDF of {name}'s notes ({n} notes); it comes here when it's ready (the first one takes longer)."


def build(app: App, slug: str, name: str, notes: dict[str, list[Path]]) -> tuple[bool, str]:
    """Write the .tex, make the PDF and send it; when the maths doesn't compile, once more with maths as text.
    Returns (whether a PDF went, what was said)."""
    from kurooto.modules.skills import compile_tex, pdf_engine, send_file

    tex = out_path(app, slug)
    tex.parent.mkdir(parents=True, exist_ok=True)
    text, count = document(app, name, notes)
    tex.write_text(text, encoding="utf-8")
    label = f"{name}: course notes ({count} notes)"
    if not pdf_engine(app):
        said = send_file(app, tex, f"{label}, as LaTeX: there's no LaTeX engine here to make the PDF.")[1]
        skills = app.modules.get("skills")
        if skills is not None and app.is_on("skills"):  # the same offer revision packs make
            ref = skills._remember_pack(tex, {"label": label, "name": "course-notes", "subject": slug})
            app.notify(
                "Install Tectonic so course notes come as PDFs?",
                kind="question",
                buttons=[[("Install Tectonic", f"skt:{ref}:install"), ("Not now", f"skt:{ref}:no")]],
                why="asked",
            )
        else:
            app.notify(
                "For a PDF, turn on Skills (Features) and tap Install Tectonic when it offers, or install TeX Live, "
                "MiKTeX or MacTeX; then /notes pdf again.",
                kind="info",
                why="asked",
            )
        return False, said
    ok, err = compile_tex(app, tex)
    plain = False
    if not ok:  # most often a macro of your own in the maths: again, with the maths as written
        text, count = document(app, name, notes, safe=True)
        tex.write_text(text, encoding="utf-8")
        ok, err2 = compile_tex(app, tex)
        plain = ok
        err = err if ok else err2
    if not ok:
        app.events.emit("course_pdf_failed")
        first = err.splitlines()[0][:200] if err else "no message"
        said = send_file(app, tex, f"{label}: the PDF didn't compile ({first}). Here's the LaTeX.")[1]
        return False, said
    pdf = tex.with_suffix(".pdf")
    note = " Some maths didn't compile, so it's shown as written." if plain else ""
    said = send_file(app, pdf, f"{label}.{note} Also kept at {layout.shown(app, pdf)}.")[1]
    app.events.emit("course_pdf_built", notes=count, bytes=pdf.stat().st_size, plain=plain)
    return True, said
