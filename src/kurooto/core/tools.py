"""What the AI can do for you, the same everywhere: on calls, in requests to an API brain (Gemini key, FreeLLMAPI,
Ollama, ...), and for agent brains (agy, Codex, Claude Code) through `kurooto mcp`.

Every feature you turn on adds its own tools (Module.call_tools(), and Module.agent_tools() for ones that only make
sense in unattended work). The notes tools below never change what's already written: a new note is created, or text
is added to the end of a note or of one of its sections; the only edit is ticking a "- [ ]" task.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.modules.calls.tools import Tool, arg, clip, keyword_search, note_files, read_note

if TYPE_CHECKING:
    from pathlib import Path

    from kurooto.app import App

CALL_ONLY = {"run_task", "pending_items"}  # an unattended request doesn't start more requests or brief a call
MAX_NOTE = 200_000  # characters a tool may add in one go


def note_path(root: Path, slug: str, must_exist: bool) -> Path | None:
    """The note's file inside the notes folder, or None if the name is unsafe (outside the folder, not a note)."""
    slug = str(slug or "").strip().replace("\\", "/").removesuffix(".md").strip("/")
    if not slug or any(part in ("..", ".", "") or part.startswith(".") for part in slug.split("/")):
        return None
    f = (root / f"{slug}.md").resolve()
    try:
        f.relative_to(root.resolve())
    except ValueError:
        return None
    if must_exist and not f.is_file():
        return None
    return f


def add_to_section(text: str, section: str, addition: str) -> str:
    """Put `addition` at the end of the "## section" (made at the end if missing), leaving everything else as is."""
    addition = addition.strip("\n")
    if not section:
        return text.rstrip("\n") + "\n\n" + addition + "\n"
    m = re.search(rf"^(#{{1,6}})\s+{re.escape(section.strip().lstrip('#').strip())}\s*$", text, re.M | re.I)
    if not m:
        return text.rstrip("\n") + f"\n\n## {section.strip().lstrip('#').strip()}\n{addition}\n"
    level = len(m.group(1))
    nxt = re.compile(rf"^#{{1,{level}}}\s", re.M).search(text, m.end())
    end = nxt.start() if nxt else len(text)
    head, body, tail = text[: m.end()], text[m.end() : end].rstrip("\n"), text[end:]
    return head + body + "\n" + addition + "\n" + ("\n" + tail if tail else "")


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
                "List the notes in a folder of their notes ('' for the top).",
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
        text = read_note(self.root, a.get("slug", ""))
        return clip(text, 12000) if text is not None else f'No note "{a.get("slug", "")}".'

    def listing(self, a: dict):
        base = self.root
        folder = str(a.get("folder") or "").strip("/")
        if folder:
            p = note_path(self.root, folder + "/x", must_exist=False)
            if not p:
                return "That isn't a folder in the notes."
            base = p.parent
        if not base.is_dir():
            return f'No folder "{folder}".'
        notes = sorted(p.relative_to(self.root).with_suffix("").as_posix() for p in note_files(base, limit=400))
        dirs = sorted(d.name + "/" for d in base.iterdir() if d.is_dir() and not d.name.startswith("."))
        return {"folders": dirs[:100], "notes": notes[:300]}

    def _write(self, f: Path, text: str, what: str) -> None:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        self.app.events.emit("note_written", how=what, chars=len(text))

    def write(self, a: dict):
        f = note_path(self.root, a.get("slug", ""), must_exist=False)
        text = str(a.get("text") or "")
        if not f:
            return "That isn't a usable note name (letters, digits, - and / only, inside the notes)."
        if f.exists():
            return "That note exists already: use add_to_note to add to it."
        if not text.strip() or len(text) > MAX_NOTE:
            return "Nothing to write, or too long."
        if not text.startswith("---\n"):
            text = f"---\nmade_by: {self.app.name}\ndate: {now():%Y-%m-%d}\n---\n\n" + text
        self._write(f, text.rstrip("\n") + "\n", "create")
        return f"Created {f.relative_to(self.root).with_suffix('').as_posix()}."

    def add(self, a: dict):
        f = note_path(self.root, a.get("slug", ""), must_exist=False)
        text = str(a.get("text") or "")
        if not f:
            return "That isn't a usable note name."
        if not text.strip() or len(text) > MAX_NOTE:
            return "Nothing to add, or too long."
        old = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""
        self._write(f, add_to_section(old, str(a.get("section") or ""), text), "add")
        return f"Added to {f.relative_to(self.root).with_suffix('').as_posix()}."

    def tick(self, a: dict):
        f = note_path(self.root, a.get("slug", ""), must_exist=True)
        words = [w for w in re.split(r"\W+", str(a.get("task", "")).lower()) if w]
        if not f or not words:
            return "No such note, or no task words."
        lines = f.read_text(encoding="utf-8", errors="replace").split("\n")
        for i, ln in enumerate(lines):
            if re.match(r"^\s*[-*] \[ \]", ln) and all(w in ln.lower() for w in words):
                lines[i] = ln.replace("[ ]", "[x]", 1)
                self._write(f, "\n".join(lines), "tick")
                return f"Ticked: {ln.strip()[6:][:120]}"
        return "No open task matched those words."


def agent_tools(app: App) -> list[Tool]:
    """Every tool for unattended work: the notes tools, then each enabled feature's own."""
    out = NoteTools(app).tools()
    seen = {t.name for t in out}
    for m in app.enabled():
        for getter in ("call_tools", "agent_tools"):
            fn = getattr(m, getter, None)
            if not fn:
                continue
            try:
                for t in fn():
                    if t.name not in seen and t.name not in CALL_ONLY:
                        out.append(t)
                        seen.add(t.name)
            except Exception as e:
                app.events.emit("tools_failed", module=m.id, error=str(e)[:200])
    return out


def run_tool(app: App, name: str, args: dict, tools: list[Tool] | None = None):
    tool = next((t for t in (tools if tools is not None else agent_tools(app)) if t.name == name), None)
    if not tool:
        return f"There's no {name} tool (that feature may be off)."
    app.events.emit("tool_used", name=name)
    try:
        return tool.run(args or {})
    except Exception as e:
        return f"That failed: {type(e).__name__}: {e}"[:300]


def schema(t: Tool) -> dict:
    """JSON Schema for the tool's arguments (OpenAI functions and MCP both use this)."""
    return {"type": "object", "properties": t.params, "required": list(t.required)}
