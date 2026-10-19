"""Quick notes and prompts: /note <text> saves a thought straight into your notes' inbox (inbox/<date>-<words>.md),
and `kurooto note "text"` does the same from a terminal. Your prompt library is <notes>/prompts/*.md: /prompts lists
it, /prompt <name> sends one back so you can copy it, /prompt save <name> (the prompt on the next lines) adds one.
A prompt with `skill: true` in its header also becomes a skill (with the Skills feature on).
No AI is involved: what you write is saved as you wrote it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from kurooto.core import overlay
from kurooto.core.clock import now
from kurooto.modules.base import Command, Incoming, Module
from kurooto.modules.skills import parse, prompt_files, prompt_skill, slug


def capture(workspace: Path, text: str, title: str = "", source: str = "telegram", files=()) -> Path:
    """Save a quick note to inbox/<YYYY-MM-DD>-<first words>.md (never over an existing note). Returns its path."""
    text = (text or "").strip()
    stamp = now()
    words = title.strip() or " ".join(text.split()[:6]) or (Path(files[0]).stem if files else "")
    name = f"{stamp:%Y-%m-%d}-{slug(words, 50) or 'note'}"
    inbox = Path(workspace) / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    f, n = inbox / f"{name}.md", 2
    while f.exists():
        f, n = inbox / f"{name}-{n}.md", n + 1
    head = ["---", f"created: {stamp.isoformat()}", f"source: {source}", "tags: [inbox]"]
    if title.strip():
        head.insert(1, f"title: {json_str(title.strip())}")
    body = "\n".join([*head, "---", "", text]).rstrip() + "\n"
    links = [Path(os.path.relpath(Path(x), inbox)).as_posix() for x in files]
    if links:
        body += "\n" + "\n".join(f"- [{Path(x).name}]({x})" for x in links) + "\n"
    f.write_text(body, encoding="utf-8")
    return f


def json_str(s: str) -> str:
    """A header value, quoted when it needs to be."""
    return f'"{s.replace(chr(34), chr(39))}"' if re.search(r"[:#\[\]{}\"',&*!|>%@`]", s) else s


def prompts(workspace: Path, extra: list[Path] = ()) -> list[dict]:
    """Every prompt in <notes>/prompts: name (its path without .md), title, and whether it's also a skill. `extra`:
    more prompt folders (your add-ons'), listed after yours as add-ons/<name>."""
    out = []
    for root, prefix in [(Path(workspace) / "prompts", ""), *((Path(d), "add-ons/") for d in extra)]:
        out += _prompts_in(root, prefix)
    return out


def _prompts_in(root: Path, prefix: str) -> list[dict]:
    out = []
    for f in prompt_files(root):
        try:
            meta, body = parse(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        out.append(
            {
                "name": prefix + f.relative_to(root).with_suffix("").as_posix(),
                "title": (meta.get("title") or meta.get("name") or f.stem).strip(),
                "skill": prompt_skill(meta, f.stem),
                "body": body.strip(),
                "path": f,
            }
        )
    return out


def find_prompt(items: list[dict], want: str) -> dict | list[dict] | None:
    """By name, file name or title (any case); else the ones whose name or title contains it."""
    w = want.strip().lower().removesuffix(".md")
    if not w:
        return None
    for p in items:
        if w in (p["name"].lower(), p["name"].rsplit("/", 1)[-1].lower(), p["title"].lower()):
            return p
    hits = [p for p in items if w in p["name"].lower() or w in p["title"].lower()]
    return hits[0] if len(hits) == 1 else (hits or None)


class Library(Module):
    id = "library"
    title = "Quick notes and prompts"
    description = "/note saves a thought to your notes' inbox; /prompts and /prompt keep prompts you reuse."
    requires = ("telegram",)
    privacy = "Stays on this computer, in your notes folder."

    def commands(self):
        return [
            Command("note", "save a quick note to your inbox: /note buy graph paper", self._note),
            Command("prompts", "the prompts in your notes (prompts/)", self._prompts),
            Command("prompt", "one prompt to copy: /prompt <name>; /prompt save <name> adds one", self._prompt),
        ]

    def _note(self, msg: Incoming, arg: str) -> str:
        if not arg.strip() and not msg.files:
            return "What should I save? /note <text> (a photo or file with /note as its caption works too)"
        f = capture(self.app.workspace, arg, source=msg.via, files=msg.files)
        self.app.events.emit("note_captured", via=msg.via, chars=len(arg), files=len(msg.files))
        return f"Saved to {f.relative_to(self.app.workspace).as_posix()}."

    def _prompts(self, msg: Incoming, arg: str) -> str:
        items = prompts(self.app.workspace, overlay.dirs(self.app, "prompts"))
        if not items:
            return (
                "No prompts yet. Save one with /prompt save <name> and the prompt on the next lines, or put Markdown "
                "files in prompts/ in your notes."
            )
        rows = [
            f"{p['name']}{' (also /' + p['skill'] + ')' if p['skill'] else ''}"
            + (f": {p['title']}" if p["title"].lower() != p["name"].rsplit("/", 1)[-1].lower() else "")
            for p in items[:120]
        ]
        more = f"\n…and {len(items) - 120} more" if len(items) > 120 else ""
        return "Your prompts (/prompt <name> sends one):\n" + "\n".join(rows) + more

    def _prompt(self, msg: Incoming, arg: str) -> str:
        first, _, rest = arg.partition("\n")
        if first.strip().lower().startswith("save"):
            return self._save(first.strip()[4:].strip(), rest)
        items = prompts(self.app.workspace, overlay.dirs(self.app, "prompts"))
        hit = find_prompt(items, first)
        if not first.strip():
            return "Which one? /prompt <name> (/prompts lists them)"
        if hit is None:
            return f"No prompt matches {first.strip()!r}. /prompts lists them."
        if isinstance(hit, list):
            return "Which one? " + ", ".join(p["name"] for p in hit[:15])
        self.app.events.emit("prompt_used")
        return hit["body"] or "(that prompt is empty)"

    def _save(self, title: str, body: str) -> str:
        if not title or not body.strip():
            return (
                "Put the name after /prompt save and the prompt on the next lines:\n/prompt save summarise\n"
                "Summarise this in 5 bullets: …"
            )
        root = self.app.workspace / "prompts"
        root.mkdir(parents=True, exist_ok=True)
        base = slug(title, 60) or "prompt"
        f, n = root / f"{base}.md", 2
        while f.exists():
            f, n = root / f"{base}-{n}.md", n + 1
        f.write_text(
            f"---\ntitle: {json_str(title)}\ncreated: {now():%Y-%m-%d}\n---\n\n{body.strip()}\n", encoding="utf-8"
        )
        self.app.events.emit("prompt_saved")
        return f"Saved: /prompt {f.stem}"
