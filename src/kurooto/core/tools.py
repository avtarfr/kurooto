"""What the AI can do for you, the same everywhere: on calls, in requests to an API brain (Gemini key, FreeLLMAPI,
Ollama, ...), and for agent brains (agy, Codex, Claude Code) through `kurooto mcp`.

Every feature you turn on adds its own tools (Module.call_tools(), and Module.agent_tools() for ones that only make
sense in unattended work). The notes tools below never change what's already written: a new note is created, or text
is added to the end of a note or of one of its sections; the only edit is ticking a "- [ ]" task.
"""

from __future__ import annotations

import os
import re
import time
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.modules.calls.tools import Tool, arg, clip, keyword_search

if TYPE_CHECKING:
    from pathlib import Path

    from kurooto.app import App

CALL_ONLY = {"run_task", "pending_items"}  # an unattended request doesn't start more requests or brief a call
MAX_NOTE = 200_000  # characters a tool may add in one go
BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')  # not allowed in file names on Windows
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}
FENCE = re.compile(r"^\s{0,3}(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
TASK = re.compile(r"^\s*(?:[-*+]|\d+[.)]) \[ \]")


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
                {"query": arg("what to look for, in plain words")},
                ("query",),
            ),
            Tool(
                "read_note",
                "Read one note by its slug, e.g. journal/2026-10-19 or linear-algebra/class-log.",
                self.read,
                {"slug": arg()},
                ("slug",),
            ),
            Tool(
                "list_notes",
                "List the notes and folders in one folder of their notes ('' for the top).",
                self.listing,
                {"folder": arg()},
            ),
            Tool(
                "write_note",
                "Create a NEW note (fails if it exists; use add_to_note then). Markdown; slug like inbox/an-idea.",
                self.write,
                {"slug": arg(), "text": arg("the whole note, Markdown")},
                ("slug", "text"),
                offline="queue",
            ),
            Tool(
                "add_to_note",
                "Add text to an existing note (or create it): at the end of a '## section' (made if missing), or at "
                "the end of the note when section is empty. Never changes what's already there.",
                self.add,
                {"slug": arg(), "text": arg("what to add, Markdown"), "section": arg("heading text, optional")},
                ("slug", "text"),
                offline="queue",
            ),
            Tool(
                "tick_task",
                "Mark a '- [ ] task' in a note as done, by a few words of its text.",
                self.tick,
                {"slug": arg(), "task": arg("words from the task line")},
                ("slug", "task"),
                offline="queue",
            ),
        ]

    def search(self, a: dict):
        q = str(a.get("query", ""))
        gb = self.app.modules.get("gbrain")
        if gb and self.app.is_on("gbrain"):
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
        return f.relative_to(self.root.resolve()).with_suffix("").as_posix()

    def write(self, a: dict):
        f = note_path(self.root, a.get("slug", ""), must_exist=False)
        text = str(a.get("text") or "")
        if not f:
            return "That isn't a usable note name (no dot at the start, none of :*?<>|, inside the notes)."
        if f.exists():
            return "That note exists already: use add_to_note to add to it."
        if not text.strip() or len(text) > MAX_NOTE:
            return "Nothing to write, or too long."
        if not text.startswith("---\n"):
            text = f"---\nmade_by: {self.app.name}\ndate: {now():%Y-%m-%d}\n---\n\n" + text
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


def agent_tools(app: App) -> list[Tool]:
    """Every tool for unattended work: the notes tools, then each enabled feature's own."""
    out = NoteTools(app).tools()
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


def run_tool(app: App, name: str, args: dict, tools: list[Tool] | None = None, via: str = "ai"):
    """Run one tool by name. Never raises: a problem comes back as a sentence the AI can read."""
    tool = next((t for t in (tools if tools is not None else agent_tools(app)) if t.name == name), None)
    if not tool:
        return f"There's no {name} tool (that feature may be off)."
    args = args if isinstance(args, dict) else {}
    missing = [k for k in tool.required if args.get(k) is None or not str(args.get(k)).strip()]
    if missing:
        return f"{name} needs: {', '.join(missing)}."
    app.events.emit("tool_used", name=name, via=via)
    try:
        return tool.run(args)
    except Exception as e:
        app.events.emit("tool_failed", name=name, error=f"{type(e).__name__}: {e}"[:200])
        return f"That failed: {type(e).__name__}: {e}"[:300]


def schema(t: Tool) -> dict:
    """JSON Schema for the tool's arguments (OpenAI functions and MCP both use this)."""
    out: dict = {"type": "object", "properties": dict(t.params)}
    if t.required:
        out["required"] = list(t.required)
    return out


def describe(t: Tool) -> dict:
    """One tool as the local API and `kurooto mcp` list it."""
    return {"name": t.name, "description": t.description, "schema": schema(t)}
