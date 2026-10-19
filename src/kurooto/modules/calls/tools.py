"""What the assistant can do during a call. Each feature you turn on adds its own tools (Module.call_tools()) and its
part of "what needs your attention" (Module.call_brief()); a tool for a feature that's off doesn't exist on calls.

Each tool says what happens when your computer is off during a call: "queue" (done when it's back), "brief"
(answered from what the computer last sent) or "needs" (the assistant says it can't right now).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", ".kurooto", "attachments", "templates"}


@dataclass
class Tool:
    name: str
    description: str
    run: Callable[[dict], Any]
    params: dict = field(default_factory=dict)  # name -> JSON schema of the argument
    required: tuple[str, ...] = ()
    offline: str = "needs"  # needs | queue | brief
    hint: str = ""  # one line for the call's instructions: when to use it

    def declaration(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "behavior": "NON_BLOCKING",
            "parameters": {"type": "object", "properties": self.params, "required": list(self.required)},
        }


def arg(desc: str = "") -> dict:
    return {"type": "string", "description": desc} if desc else {"type": "string"}


def clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n] + "\n[…]"


# ------------------------------------------------------------------------------------------------- notes
def note_files(root: Path, limit: int = 5000):
    n = 0
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in names:
            if name.endswith(".md"):
                yield Path(dirpath) / name
                n += 1
                if n >= limit:
                    return


def note_entry(path: Path, root: Path) -> dict | None:
    """A compact index entry: slug, title, aliases, headings, a summary line (what the call line searches offline)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    body = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    m = re.search(r"^# (.+)$", body, re.M)
    title = m.group(1).strip() if m else path.stem
    a = re.search(r"^aliases:\s*\[(.*)\]", text, re.M)
    heads = " | ".join(h.strip() for h in re.findall(r"^##+ (.+)$", body, re.M)[:12])
    summary = re.sub(r"\s+", " ", re.sub(r"^#.*$", "", body, flags=re.M)).strip()[:220]
    return {
        "s": path.relative_to(root).with_suffix("").as_posix(),
        "t": title[:120],
        "a": (a.group(1) if a else "")[:200],
        "h": heads[:400],
        "m": summary,
    }


def notes_index(root: Path, max_bytes: int = 1_500_000) -> list[dict]:
    out, size = [], 0
    for p in note_files(root):
        e = note_entry(p, root)
        if not e:
            continue
        size += sum(len(v) for v in e.values()) + 40
        if size > max_bytes:
            break
        out.append(e)
    return out


def keyword_search(root: Path, query: str, n: int = 6) -> list[dict]:
    words = [w for w in re.split(r"\W+", query.lower()) if len(w) > 2]
    scored = []
    for e in notes_index(root):
        hay = {k: v.lower() for k, v in e.items()}
        sc = sum(
            (5 if w in hay["t"] else 0)
            + (4 if w in hay["a"] else 0)
            + (3 if w in hay["s"] else 0)
            + (2 if w in hay["h"] else 0)
            + (1 if w in hay["m"] else 0)
            for w in words
        )
        if sc:
            scored.append((sc, e))
    scored.sort(key=lambda x: -x[0])
    return [{"slug": e["s"], "title": e["t"], "headings": e["h"], "summary": e["m"]} for _, e in scored[:n]]


def read_note(root: Path, slug: str) -> str | None:
    slug = str(slug or "").strip().removesuffix(".md").lstrip("/")
    if not slug or any(part in ("..", "") for part in slug.split("/")):
        return None
    f = (root / f"{slug}.md").resolve()
    try:
        f.relative_to(root.resolve())
    except ValueError:
        return None
    return f.read_text(encoding="utf-8", errors="replace") if f.is_file() else None
