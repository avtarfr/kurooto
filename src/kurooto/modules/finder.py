"""Find files: an opt-in, local index of the folders you choose (no AI), and `/find <words>` with a Send button on each
hit."""

from __future__ import annotations

import datetime as dt
import os
import threading
import time
from pathlib import Path

from kurooto.core import finder
from kurooto.modules.base import Command, Incoming, Module

PENDING_MAX = 40


class Finder(Module):
    id = "finder"
    title = "Find files"
    description = (
        "Ask for a file by what it's called or what's in it (/find lecture notes entropy) and get it sent to you: a "
        "local index of the folders you choose, made on this computer without an AI."
    )
    privacy = (
        "Stays on this computer: the index is a file in Kurooto's folder. Only a file you tap Send on goes anywhere "
        "(your own "
        "Telegram, or your Drive if you set that up). Keys and hidden folders are never read."
    )

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, str] = {}

    def start(self) -> None:
        self.every("index", "daily 04:50", lambda p=None: self.reindex(), thread=True)

    def reindex(self, budget_s: float = 1800) -> dict:
        if not self.app.is_on(self.id):
            return {}
        return finder.index(self.app, budget_s)

    def health(self) -> tuple[bool, str]:
        if not finder.folders(self.app):
            return False, "no folders yet: /find add <folder>"
        return True, ""

    def callbacks(self):
        return {"fnd": self._button}

    def commands(self) -> list[Command]:
        return [
            Command(
                "find",
                "find a file by name or contents and get it sent: /find <words>; /find add <folder>, folders, reindex",
                self.cmd,
                usage="/find <words> | add <folder> | remove <folder> | folders | reindex",
            )
        ]

    def cmd(self, msg: Incoming, arg: str) -> str | None:
        a = (arg or "").strip()
        low = a.lower()
        cur = list(self.app.settings.get("finder.folders") or [])
        if low.startswith("add "):
            p = Path(os.path.expanduser(a[4:].strip()))
            if not p.is_dir():
                return f"There's no folder {a[4:].strip()}."
            if str(p) not in cur:
                self.app.settings.set("finder.folders", [*cur, str(p)])
            threading.Thread(target=self.reindex, daemon=True).start()
            return f"Added {p}. Indexing it now; /find <words> works as it fills in."
        if low.startswith("remove "):
            want = os.path.expanduser(a[7:].strip())
            self.app.settings.set("finder.folders", [f for f in cur if os.path.expanduser(f) != want])
            return "Removed. (Its files drop out of the index at the next pass.)"
        if low == "folders" or not a:
            return (
                "Indexed folders:\n" + "\n".join(f"- {f}" for f in cur)
                if cur
                else "No folders yet: /find add <folder>."
            ) + "\n/find <words> searches them."
        if low == "reindex":
            threading.Thread(target=self.reindex, daemon=True).start()
            return "Indexing now."
        if not cur:
            return "Add a folder first: /find add ~/Documents"
        hits = finder.search(self.app, a)
        if not hits:
            return f"Nothing matches {a!r} in {len(cur)} folder(s)."
        lines, rows = [], []
        for i, h in enumerate(hits, 1):
            when = dt.datetime.fromtimestamp(h["mtime"]).strftime("%d %b %Y")
            small = f"{h['size'] / 1024:.0f} KB" if h["size"] < 10**6 else f"{h['size'] / 10**6:.1f} MB"
            lines.append(f"{i}. {h['name']} ({small}, {when})" + (f"\n   {h['snippet']}" if h["snippet"] else ""))
            key = f"{int(time.time()) % 100000}{i}"
            self._hits[key] = h["path"]
            rows.append([(f"Send {i}", f"fnd:{key}:send")])
        for k in list(self._hits)[:-PENDING_MAX]:
            self._hits.pop(k, None)
        msg.reply("\n".join(lines), rows)
        return None

    def _button(self, ref: str, act: str) -> str:
        path = self._hits.get(ref)
        if not path:
            return "That list has expired: /find again."
        if not finder.inside(self.app, path):
            return "That file isn't in a folder I'm allowed to send from."
        from kurooto.modules.skills import send_file

        return send_file(self.app, path, "", inside=finder.folders(self.app))[1]
