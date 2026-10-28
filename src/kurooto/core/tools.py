"""What the AI can do for you, the same everywhere: on calls, in requests to an API brain (Gemini key, Ollama, any
OpenAI-compatible service), and for agent brains (agy, Claude Code) through `kurooto mcp`.

Every feature you turn on adds its own tools (Module.call_tools(), and Module.agent_tools() for ones that only make
sense in unattended work). Below, the ones that are always there:
- notes: search, read, list, create a note, add to one (at its end or a section's), tick a task, and edit_note, which
  replaces one exact passage; the note's previous version is kept first (Kurooto's state folder, note-history/), and
  Notes sync's history is there too;
- files: read_file and list_files, read-only, inside the folders core/places.py names (your notes, Kurooto's copies
  of Classroom and mail, Documents, Downloads, Screenshots), links followed and checked, hidden files left out;
- fetch_url: a web page as text (GET only; never this computer or a private network);
- sync_status: when each sync last ran, how it went, and when it runs next;
- kurooto_self: what Kurooto is running here (version, AIs and models, features and their health, the last day's
  failures) and, with part=manual, how it works (core/selfdoc.py).
Tools say whether they write (Tool.writes): text-only requests get none at all. A tool that sets an alarm, places a
call or does anything else on core/tap.py's list says so (Tool.guarded): outside a live call it waits for your Approve.
A request that changes files works in a scratch folder (core/scratch.py, tools_for()): its writing tools write only
there, and the change reaches you as a proposal (core/proposals.py). In any other AI request, edit_note's change to
your text becomes a proposal too (proposals.notes_edits).
"""

from __future__ import annotations

import ast
import datetime as dt
import html
import ipaddress
import os
import re
import shutil
import socket
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import egress, places, tap
from kurooto.core.state import jload
from kurooto.modules.calls.tools import Tool, arg, clip, keyword_search

if TYPE_CHECKING:
    from kurooto.app import App

# modules no AI tool may reach (Brain, stage 02): sleep inhibitors keep the computer awake, and only the owner's own
# settings use them (Stay awake on charger, the alarm); tests/unit/test_mind_stops.py checks the import graph
TOOL_NEVER = ("kurooto.core.inhibit",)
CALL_ONLY = {"run_task", "pending_items"}  # an unattended request doesn't start more requests or brief a call
MAX_NOTE = 200_000  # characters a tool may add in one go
BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')  # not allowed in file names on Windows
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}
FENCE = re.compile(r"^\s{0,3}(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
TASK = re.compile(r"^\s*(?:[-*+]|\d+[.)]) \[ \]")
CHUNK = 20_000  # characters of a file or page per answer; read_file's `start` gets the next part
MAX_FILE = 50 * 1024 * 1024  # bigger files aren't read
MAX_PAGE = 3 * 1024 * 1024  # bytes fetched from the web, at most
HISTORY = 20  # earlier versions kept per edited note
WRITE_EXT = {".md", ".txt", ".tex", ".bib", ".csv", ".json", ".yaml", ".yml", ".org", ".rst"}  # text files the AI makes


def note_path(root: Path, slug: str, must_exist: bool) -> Path | None:
    """The note's file inside the notes folder, or None if the name is unsafe (outside the folder, hidden, not a
    usable file name on every OS)."""
    slug = str(slug or "").strip().replace("\\", "/").removesuffix(".md").strip("/")
    if not slug or BAD_CHARS.search(slug):
        return None
    for part in slug.split("/"):
        if part in ("..", ".", "") or part.startswith(".") or part.split(".")[0].lower() in RESERVED:
            return None
    f = (root / f"{slug}.md").resolve()
    try:
        f.relative_to(root.resolve())
    except ValueError:
        return None
    if must_exist and not f.is_file():
        return None
    return f


def _headings(lines: list[str]):
    """(line index, level, title) of each Markdown heading, skipping front matter and fenced code."""
    fence, start = None, 0
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
        start = end + 1 if end else 0
    for i in range(start, len(lines)):
        m = FENCE.match(lines[i])
        if m:
            fence = m[1] if fence is None else (None if m[1] == fence else fence)
            continue
        if fence is None:
            h = HEADING.match(lines[i])
            if h:
                yield i, len(h[1]), h[2].strip()


def writable(app: App, name: str, must_exist: bool) -> tuple[Path | None, str]:
    """A file the AI may create or change: a note slug (inbox/an-idea) in the notes folder, or a path to a text file
    (.tex, .txt, .md, ...) relative to the notes folder or absolute, inside a folder core/places.py lets it write in.
    Links are followed and checked; hidden parts and odd names are refused. (path, "") or (None, why)."""
    raw = str(name or "").strip().replace("\\", "/")
    suffix = Path(raw).suffix.lower()
    absolute = raw.startswith(("/", "~")) or bool(re.match(r"^[A-Za-z]:/", raw))
    if not absolute and suffix not in WRITE_EXT - {".md"}:  # a note slug, as always
        f = note_path(places.notes_root(app), raw, must_exist)
        return (f, "") if f else (None, "That isn't a usable note name (or there's no such note).")
    if suffix not in WRITE_EXT:
        return None, f"Only text files: {', '.join(sorted(WRITE_EXT))}."
    p = Path(raw).expanduser()
    real = (p if p.is_absolute() else places.notes_root(app) / p).resolve()
    for root in places.write_roots(app):
        rr = root.resolve()
        if rr in real.parents:
            parts = real.relative_to(rr).parts
            if BAD_CHARS.search("/".join(parts)) or any(
                x.startswith(".") or x.split(".")[0].lower() in RESERVED for x in parts
            ):
                return None, "That isn't a usable file name (hidden, or characters Windows can't take)."
            if must_exist and not real.is_file():
                return None, "There's no such file."
            return real, ""
    return None, "That's outside the folders I may write in (your notes, course files, your add-ons' skills)."


def add_to_section(text: str, section: str, addition: str) -> str:
    """Put `addition` at the end of the "## section" (made at the end if missing), or at the end of the note when
    section is empty. Everything already there stays exactly as it was."""
    addition = addition.strip("\n")
    name = (section or "").strip().lstrip("#").strip()
    if not text.strip():
        return (f"## {name}\n" if name else "") + addition + "\n"
    if not name:
        return text.rstrip("\n") + "\n\n" + addition + "\n"
    lines = text.split("\n")
    heads = list(_headings(lines))
    hit = next(((i, lvl) for i, lvl, title in heads if title.lower() == name.lower()), None)
    if not hit:
        return text.rstrip("\n") + f"\n\n## {name}\n{addition}\n"
    i, lvl = hit
    end = next((j for j, level, _ in heads if j > i and level <= lvl), len(lines))
    k = end
    while k - 1 > i and not lines[k - 1].strip():  # after the section's last line, before its trailing blank lines
        k -= 1
    out = "\n".join(lines[:k] + addition.split("\n") + lines[k:])
    return out if out.endswith("\n") else out + "\n"


def write_note_file(f: Path, text: str, create: bool = False) -> None:
    """Write a note. create=True: a new note only (FileExistsError if one appeared meanwhile). Otherwise the
    change is atomic (a temporary file, then a rename) and keeps the file's own line endings."""
    f.parent.mkdir(parents=True, exist_ok=True)
    if create:
        with open(f, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return
    eol = "\n"
    if f.exists():
        with open(f, "rb") as fh:
            eol = "\r\n" if b"\r\n" in fh.read(65536) else "\n"
    tmp = f.with_name(f".{f.name}.tmp{os.getpid()}")
    with open(tmp, "w", encoding="utf-8", newline=eol) as fh:
        fh.write(text)
    for attempt in range(10):
        try:
            os.replace(tmp, f)
            return
        except PermissionError:  # Windows: a scanner or sync client holds it for a moment
            if attempt == 9:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05 * (attempt + 1))


def _read_strict(f: Path) -> str | None:
    """The note's text, or None if it isn't UTF-8 (then it's left alone rather than rewritten with lost bytes)."""
    try:
        return f.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


class NoteTools:
    def __init__(self, app: App):
        self.app = app

    @property
    def root(self) -> Path:
        return self.app.workspace

    def tools(self) -> list[Tool]:
        return [
            Tool(
                "search_notes",
                "Search their notes (courses, plans, journal, anything they wrote). Returns note slugs to read.",
                self.search,
                {
                    "query": arg("what to look for, in plain words"),
                    "exact": arg('"yes" to match the exact words rather than the meaning'),
                },
                ("query",),
                writes=False,
            ),
            Tool(
                "read_note",
                "Read one note by its slug, e.g. journal/2026-10-19 or linear-algebra/class-log.",
                self.read,
                {"slug": arg()},
                ("slug",),
                writes=False,
            ),
            Tool(
                "list_notes",
                "List the notes and folders in one folder of their notes ('' for the top).",
                self.listing,
                {"folder": arg()},
                writes=False,
            ),
            Tool(
                "write_note",
                "Create a NEW note or text file (fails if it exists; then use add_to_note or edit_note): a note slug "
                "like inbox/an-idea (Markdown), or a path such as linear-algebra/pack/week3.tex in their notes, their "
                "course files or their add-ons' skills.",
                self.write,
                {"slug": arg(), "text": arg("the whole note, Markdown")},
                ("slug", "text"),
                offline="queue",
                writes=True,
            ),
            Tool(
                "add_to_note",
                "Add text to an existing note (or create it): at the end of a '## section' (made if missing), or at "
                "the end of the note when section is empty. Never changes what's already there.",
                self.add,
                {"slug": arg(), "text": arg("what to add, Markdown"), "section": arg("heading text, optional")},
                ("slug", "text"),
                offline="queue",
                writes=True,
            ),
            Tool(
                "edit_note",
                "Change a note or text file (slug or path, as for write_note): replace one exact passage (copied from "
                "read_note or read_file, enough of it to be unique) with new text; empty new text removes it. Only "
                "when they asked for the change; the previous version is kept.",
                self.edit,
                {"slug": arg(), "old": arg("the exact text to replace"), "new": arg("what it becomes")},
                ("slug", "old"),
                offline="queue",
                writes=True,
            ),
            Tool(
                "tick_task",
                "Mark a '- [ ] task' in a note as done, by a few words of its text.",
                self.tick,
                {"slug": arg(), "task": arg("words from the task line")},
                ("slug", "task"),
                offline="queue",
                writes=True,
            ),
        ]

    def search(self, a: dict):
        q = str(a.get("query", ""))
        gb = self.app.modules.get("gbrain")
        if gb and self.app.is_on("gbrain"):  # Kurooto owns GBrain's index: agent programs search it through here
            exact = str(a.get("exact") or "").strip().lower() in ("yes", "true", "1")
            if exact:
                r = gb.run("search", q, timeout=120, wait=60)
                found = (r.out or "").strip() if r.ok else ""
            else:
                found = gb.search(q, n=6)
            if found:
                return clip(found, 3500)
        hits = keyword_search(self.root, q)
        return {"hits": hits} if hits else "Nothing found in the notes."

    def read(self, a: dict):
        f = note_path(self.root, a.get("slug", ""), must_exist=True)
        if not f:
            return f'No note "{a.get("slug", "")}".'
        return clip(f.read_text(encoding="utf-8", errors="replace"), 12000)

    def listing(self, a: dict):
        base = self.root
        folder = str(a.get("folder") or "").strip().replace("\\", "/").strip("/")
        if folder:
            p = note_path(self.root, folder + "/x", must_exist=False)
            if not p:
                return "That isn't a folder in the notes."
            base = p.parent
        if not base.is_dir():
            return f'No folder "{folder}".'
        notes, dirs = [], []
        for p in sorted(base.iterdir()):
            if p.name.startswith("."):
                continue
            if p.is_dir():
                dirs.append(p.name + "/")
            elif p.suffix == ".md":
                notes.append(f"{folder}/{p.stem}" if folder else p.stem)
        return {"folders": dirs[:100], "notes": notes[:300]}

    def _done(self, f: Path, what: str, chars: int) -> str:
        self.app.events.emit("note_written", how=what, chars=chars)
        try:
            rel = f.relative_to(self.root.resolve())
        except ValueError:  # course files or your add-ons' skills
            return str(f)
        return (rel.with_suffix("") if rel.suffix == ".md" else rel).as_posix()

    def write(self, a: dict):
        f, why = writable(self.app, a.get("slug", ""), must_exist=False)
        text = str(a.get("text") or "")
        if not f:
            return why
        if f.exists():
            return "That exists already: use edit_note (or add_to_note for a note) to change it."
        if not text.strip() or len(text) > MAX_NOTE:
            return "Nothing to write, or too long."
        if f.suffix == ".md" and not text.startswith("---\n") and f.is_relative_to(self.root.resolve()):
            from kurooto.core import layout  # the header your notes layout uses for agent-written notes

            m = re.match(r"#\s+(.+)", text.lstrip())
            text = layout.frontmatter(self.app, None, f, title=m[1].strip() if m else "") + text
        try:
            write_note_file(f, text.rstrip("\n") + "\n", create=True)
        except FileExistsError:
            return "That note exists already: use add_to_note to add to it."
        return f"Created {self._done(f, 'create', len(text))}."

    def add(self, a: dict):
        f = note_path(self.root, a.get("slug", ""), must_exist=False)
        text = str(a.get("text") or "")
        if not f:
            return "That isn't a usable note name."
        if not text.strip() or len(text) > MAX_NOTE:
            return "Nothing to add, or too long."
        old = _read_strict(f) if f.exists() else ""
        if old is None:
            return "That note isn't plain UTF-8 text, so I left it alone."
        write_note_file(f, add_to_section(old, str(a.get("section") or ""), text))
        return f"Added to {self._done(f, 'add', len(text))}."

    def edit(self, a: dict):
        f, why = writable(self.app, a.get("slug", ""), must_exist=True)
        old, new = str(a.get("old") or ""), str(a.get("new") or "")
        if not f:
            return why
        text = _read_strict(f)
        if text is None:
            return "That file isn't plain UTF-8 text, so I left it alone."
        if not old.strip():
            return "Say which exact text to replace (read_note shows it)."
        n = text.count(old)
        if n != 1:
            return "That text isn't in the file." if not n else f"That text is there {n} times; include more of it."
        self._keep(f, text)
        write_note_file(f, text.replace(old, new, 1))
        return f"Edited {self._done(f, 'edit', len(new))} (the previous version is kept)."

    def _keep(self, f: Path, text: str) -> None:
        """The file as it was, in Kurooto's state folder (note-history/), the last few versions per file."""
        try:
            rel = f.relative_to(self.root.resolve()).as_posix()
        except ValueError:
            rel = f.as_posix()
        rel = re.sub(r"[^\w-]+", "__", rel).strip("_")[-150:]
        d = self.app.paths.state / "note-history" / rel
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.md").write_text(text, encoding="utf-8")
        for old in sorted(d.glob("*.md"))[:-HISTORY]:
            old.unlink(missing_ok=True)

    def tick(self, a: dict):
        f = note_path(self.root, a.get("slug", ""), must_exist=True)
        words = [w for w in re.split(r"\W+", str(a.get("task", "")).lower()) if w]
        if not f or not words:
            return "No such note, or no task words."
        text = _read_strict(f)
        if text is None:
            return "That note isn't plain UTF-8 text, so I left it alone."
        lines = text.split("\n")
        hits = [i for i, ln in enumerate(lines) if TASK.match(ln) and all(w in ln.lower() for w in words)]
        if not hits:
            return "No open task matched those words."
        if len(hits) > 1:
            some = "; ".join(lines[i].strip()[:80] for i in hits[:5])
            return f"More than one open task matches ({some}). Use more words from the one you mean."
        lines[hits[0]] = lines[hits[0]].replace("[ ]", "[x]", 1)
        write_note_file(f, "\n".join(lines))
        self._done(f, "tick", 0)
        return f"Ticked: {lines[hits[0]].split('[x]', 1)[1].strip()[:120]}"


# ----------------------------------------------------------------------------------------- files and the web
def public_host(host: str) -> bool:
    """Does the name lead only to the public internet (not this computer, the local network, or a cloud's metadata
    address)? A page or note can't then steer the AI into poking at things on this side."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError):
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0].split("%")[0]).is_global for i in infos)


class _Checked(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlsplit(newurl)
        if u.scheme not in ("http", "https") or not public_host(u.hostname or ""):
            raise urllib.error.URLError("it redirects somewhere it may not go")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def page_text(raw: bytes, ctype: str) -> str:
    """A page as plain text: scripts and styles dropped, tags removed, entities decoded, blank lines squeezed."""
    m = re.search(r"charset=([\w-]+)", ctype or "")
    text = raw.decode(m.group(1) if m else "utf-8", errors="replace")
    if "html" not in (ctype or "") and not re.search(r"<html|<body|<p[ >]", text[:2000], re.I):
        return text
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    text = re.sub(r"(?is)<(script|style|noscript|svg|head)\b.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|section|article)>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return (f"# {html.unescape(title.group(1)).strip()}\n\n" if title else "") + text


def pdf_text(path: Path) -> str | None:
    """A PDF's text with pdftotext (Poppler) or pypdf, whichever this computer has; None if neither."""
    if shutil.which("pdftotext"):
        from kurooto.core import proc

        r = proc.run(["pdftotext", "-layout", str(path), "-"], timeout=120)
        if r.ok and r.out.strip():
            return r.out
    try:
        from pypdf import PdfReader  # optional; not a dependency
    except ImportError:
        return None
    try:
        return "\n\n".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    except Exception:
        return None


class FileTools:
    """Read-only files and the web, for the AI. The same folders agy may read (core/places.py)."""

    def __init__(self, app: App):
        self.app = app

    def tools(self) -> list[Tool]:
        where = "their notes, Documents, Downloads, Screenshots, or Kurooto's copies of Classroom and mail"
        return [
            Tool(
                "read_file",
                f"Read a file in {where}: text, Markdown, PDF, Word, PowerPoint, notebooks. A path relative to the "
                f"notes folder, or absolute (list_files shows the folders). Long files come in parts of {CHUNK} "
                "characters: pass start to go on.",
                self.read,
                {"path": arg(), "start": arg("character to start at, for the next part (optional)")},
                ("path",),
                writes=False,
            ),
            Tool(
                "list_files",
                f"List files in a folder of {where} ('' lists those folders). pattern: e.g. *.pdf, or **/*.md to "
                "look in subfolders too.",
                self.listing,
                {"path": arg(), "pattern": arg("optional, default *")},
                writes=False,
            ),
            Tool(
                "fetch_url",
                "Read a web page (http or https; GET only) as plain text.",
                self.fetch,
                {"url": arg()},
                ("url",),
                writes=False,
            ),
        ]

    def _where(self, path: str) -> tuple[Path | None, str]:
        """The real path if it's allowed (inside a root after following links, nothing hidden), else (None, why)."""
        raw = str(path or "").strip()
        if not raw:
            return None, "Which file?"
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = places.notes_root(self.app) / p
        real = p.resolve()
        for root in places.read_roots(self.app):
            rr = root.resolve()
            if real == rr or rr in real.parents:
                rel = real.relative_to(rr).parts
                if any(x.startswith(".") for x in rel):
                    return None, "Hidden files and folders are left alone."
                return real, ""
        return None, "That's outside the folders I may read (list_files with no path shows them)."

    def read(self, a: dict):
        f, why = self._where(a.get("path", ""))
        if not f:
            return why
        if not f.is_file():
            return "No such file." if not f.exists() else "That's a folder: use list_files."
        if f.stat().st_size > MAX_FILE:
            return f"That file is {f.stat().st_size // 1_000_000} MB: too big to read here."
        ext = f.suffix.lower()
        text = None
        if ext == ".pdf":
            text = pdf_text(f)
            if text is None:
                return "I can't read PDFs on this computer (install Poppler for pdftotext)."
        elif ext in (".docx", ".pptx", ".ipynb"):
            from kurooto.modules.google_classroom import extract_text

            text = extract_text(f)
        if text is None:
            raw = f.read_bytes()
            if b"\x00" in raw[:8192]:
                return f"That isn't a text file ({len(raw)} bytes); I can't read it."
            text = raw.decode("utf-8", errors="replace")
        try:
            start = max(0, int(str(a.get("start") or 0)))
        except ValueError:
            start = 0
        part = text[start : start + CHUNK]
        rest = len(text) - start - len(part)
        return part + (
            f"\n[… {rest} more characters: read_file again with start={start + len(part)}]" if rest > 0 else ""
        )

    def listing(self, a: dict):
        if not str(a.get("path") or "").strip():
            return {"folders": [str(r) for r in places.read_roots(self.app) if r.is_dir()]}
        d, why = self._where(a.get("path", ""))
        if not d:
            return why
        if not d.is_dir():
            return "That isn't a folder."
        pattern = str(a.get("pattern") or "*").strip() or "*"
        roots = places.read_roots(self.app)
        out = []
        for p in sorted(d.glob(pattern)):
            rel = p.relative_to(d)
            if any(x.startswith(".") for x in rel.parts) or not places.inside(p, roots):
                continue
            out.append(rel.as_posix() + "/" if p.is_dir() else f"{rel.as_posix()} ({p.stat().st_size // 1024} KB)")
            if len(out) >= 300:
                out.append("[… more; use a narrower pattern]")
                break
        return {"folder": str(d), "entries": out}

    def fetch(self, a: dict):
        url = str(a.get("url") or "").strip()
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            return "Only http and https addresses."
        if not public_host(u.hostname):
            return "That address is on this computer or a private network; I don't fetch those."
        opener = urllib.request.build_opener(_Checked)
        req = urllib.request.Request(  # noqa: S310 (http(s) only, checked above)
            url, headers={"User-Agent": "Kurooto (personal assistant)", "Accept": "*/*"}
        )
        try:
            with egress.urlopen(req, "pages your AI reads", timeout=20, own=True, opener=opener) as r:
                raw, ctype = r.read(MAX_PAGE + 1), r.headers.get("Content-Type", "")
        except (urllib.error.URLError, OSError, ValueError) as e:
            return f"Couldn't fetch it: {getattr(e, 'reason', e)}"[:300]
        cut = len(raw) > MAX_PAGE
        if "pdf" in ctype or raw[:5] == b"%PDF-":
            with tempfile.TemporaryDirectory() as tmp:
                f = Path(tmp) / "page.pdf"
                f.write_bytes(raw[:MAX_PAGE])
                text = pdf_text(f)
            if text is None:
                return "It's a PDF, and I can't read PDFs on this computer (install Poppler for pdftotext)."
        elif ctype and not re.search(r"text|json|xml|html", ctype):
            return f"That's not a page I can read ({ctype.split(';')[0]})."
        else:
            text = page_text(raw[:MAX_PAGE], ctype)
        return clip(text, CHUNK) + ("\n[the page was cut short]" if cut else "")


# --------------------------------------------------------------------------------------------------- syncs
SYNCS = [  # (module id, its timer, what to call it)
    ("notes_sync", "notes_sync:sync", "Notes sync (git)"),
    ("gbrain", "gbrain:sync", "Notes brain (GBrain)"),
    ("calendar", "calendar:refresh", "Calendar"),
    ("google", "google:classroom", "Classroom assignments"),
    ("classroom_notes", "classroom_notes:sync", "Classroom into notes"),
    ("mail_digest", "mail_digest:digest", "Mail digest"),
    ("research", "research:papers", "Research papers"),
    ("research", "research:logs", "Research project logs"),
]


def _outcome(last: str | None) -> str:
    """What a timer's action returned (the scheduler keeps it as text), in a few words."""
    if last is None:
        return "ok"
    try:
        v = ast.literal_eval(last.strip())
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        v = last.strip()
    if isinstance(v, tuple) and v and isinstance(v[0], bool):
        return ("ok" if v[0] else "failed") + (f": {v[1]}" if len(v) > 1 and v[1] else "")
    if isinstance(v, bool):
        return "ok" if v else "nothing to do"
    if isinstance(v, dict):
        return f"failed: {v['error']}" if v.get("error") else "ok"
    if isinstance(v, str) and re.match(r"^\w*(Error|Exception)\b", v):
        return f"failed: {v}"
    return f"ok: {v}"


def sync_status(app: App) -> dict:
    """Per sync that's on: when it last ran, how that went, when it runs next; and the last "sync everything"."""
    from kurooto.core import syncall

    def when(ts) -> str:
        return dt.datetime.fromtimestamp(ts).strftime("%a %d %b %H:%M") if ts else "never"

    out, off = [], []
    for mid, key, label in SYNCS:
        if mid not in app.modules:
            continue
        if not app.is_on(mid):
            off.append(label)
            continue
        job = app.scheduler.get(key)
        row = {
            "sync": label,
            "last": when(job.last_run if job else None),
            "result": _outcome(job.last_result) if job and job.last_run else "hasn't run yet",
            "next": when(job.next_run if job else None) if job else "not scheduled",
        }
        own = jload(getattr(app.modules[mid], "state_file", None) or Path(os.devnull), {}) or {}
        if own.get("at") and (not job or not job.last_run or own["at"] >= job.last_run):  # e.g. a sync you asked for
            row["last"], row["result"] = when(own["at"]), "ok" if own.get("ok") else f"failed: {own.get('error', '')}"
        out.append(row)
    st = syncall.status(app)
    everything = {
        "running": bool(st.get("running")),
        "last": when(st.get("finished") or st.get("started")),
        "summary": (st.get("text") or "")[:600],
    }
    return {"syncs": out, "off": sorted(set(off)) or "none", "sync_everything": everything}


def sync_tools(app: App) -> list[Tool]:
    from kurooto.core import syncall

    return [
        Tool(
            "sync_status",
            "When each sync last ran (notes sync, notes brain, calendar, Classroom, mail digest, research), how it "
            "went, and when it runs next; and the last 'sync everything'.",
            lambda a: sync_status(app),
            writes=False,
            hint="For 'is everything synced?' or 'when did my notes last sync?', call sync_status.",
        ),
        Tool(
            "sync_now",
            "Sync everything that syncs, now (Classroom, calendar, mail, notes, research): the same as /sync all. It "
            "runs in the background and sends them the result on Telegram when it's done.",
            lambda a: syncall.start(app)[1],
            offline="queue",
            writes=True,
            hint="'sync now' or 'check Classroom now': call sync_now (it reports on Telegram by itself).",
        ),
    ]


def agent_tools(app: App) -> list[Tool]:
    """Every tool for unattended work: the notes tools, then each enabled feature's own."""
    from kurooto.core import selfdoc  # kurooto_self: what Kurooto is running, for questions about itself

    out = NoteTools(app).tools() + FileTools(app).tools() + sync_tools(app) + [selfdoc.tool(app)]
    seen = {t.name for t in out}
    sources = [("ask", getattr(getattr(app, "ask", None), "agent_tools", None))]  # ask_user: a question to them
    for m in app.enabled():
        sources += [(m.id, getattr(m, "call_tools", None)), (m.id, getattr(m, "agent_tools", None))]
    for source, fn in sources:
        if not fn:
            continue
        try:
            for t in fn():
                if t.name not in seen and t.name not in CALL_ONLY:
                    out.append(t)
                    seen.add(t.name)
        except Exception as e:
            app.events.emit("tools_failed", module=source, error=str(e)[:200])
    return out


def _guest_job(app: App, job: str | None) -> bool:
    """(voice id) Is this AI request a guest's (core/guest.py)? Then it gets no tool, by any route."""
    jobs = getattr(app, "jobs", None)
    return bool(job and jobs is not None and hasattr(jobs, "audience") and jobs.audience(job) == "guest")


def tools_for(app: App, job: str | None = None) -> list[Tool]:
    """The tools one AI request gets. A change request (it works in a scratch folder, core/scratch.py): reading as
    always, writing only in that folder. Any other request: agent_tools(), with edit_note's changes to your notes
    becoming a proposal (proposals.notes_edits) instead of being made. A guest's request (Voice ID): none."""
    from kurooto.core import scratch

    if _guest_job(app, job):  # (voice id) a voice that isn't the owner's: no tools at all (core/guest.py)
        return []
    sc = scratch.for_job(app, job) if job else None
    if sc is not None and not sc.lazy:
        return scratch.tools(app, sc, job)
    base = agent_tools(app)
    if job and app.settings.get("proposals.notes_edits"):
        return scratch.lazy_tools(app, job, base)
    return base


def run_tool(app: App, name: str, args: dict, tools: list[Tool] | None = None, via: str = "ai", job: str | None = None):
    """Run one tool by name. Never raises: a problem comes back as a sentence the AI can read. job: the AI request
    this is a step of (its tool log, core/jobs.py:Jobs.note_step)."""
    if _guest_job(app, job):
        return "Not allowed: this request came from a voice that isn't the owner's."  # (voice id) core/guest.py
    tool = next((t for t in (tools if tools is not None else agent_tools(app)) if t.name == name), None)
    if not tool:
        return f"There's no {name} tool (that feature may be off)."
    args = args if isinstance(args, dict) else {}
    missing = [k for k in tool.required if args.get(k) is None or not str(args.get(k)).strip()]
    if missing:
        return f"{name} needs: {', '.join(missing)}."
    guarded = tap.action_of(tool, args)
    if guarded and via not in tap.DIRECT:  # never without a tap: an alarm, a call... waits for Approve (core/tap.py)
        return tap.ask_first(app, tool, guarded, args, via=via, job=job)
    app.events.emit("tool_used", name=name, via=via)
    keep = getattr(app, "keep", None)
    if via == "call" and keep is not None:  # a call that went on as text: counted like a live call's (core/keep.py)
        keep.used(keep.tool_owner(name), "tool")
    note = getattr(getattr(app, "jobs", None), "note_step", None)
    if job and note is not None:
        note(job, name, args)
    try:
        out = tool.run(args)
    except Exception as e:
        app.events.emit("tool_failed", name=name, error=f"{type(e).__name__}: {e}"[:200])
        return f"That failed: {type(e).__name__}: {e}"[:300]
    from kurooto.mind import act  # (0.9.0, mind.act.record_asked) a change you asked for, for the Sunday digest

    act.record_asked(app, tool, args, "call" if via == "call" else "chat")
    return out


def schema(t: Tool) -> dict:
    """JSON Schema for the tool's arguments (OpenAI functions and MCP both use this)."""
    out: dict = {"type": "object", "properties": dict(t.params)}
    if t.required:
        out["required"] = list(t.required)
    return out


def describe(t: Tool) -> dict:
    """One tool as the local API and `kurooto mcp` list it (writes: True, False, or None when it doesn't say)."""
    return {"name": t.name, "description": t.description, "schema": schema(t), "writes": t.writes}
