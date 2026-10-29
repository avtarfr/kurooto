"""The phone app's chats ("sessions", 0.8.10): besides the chat with Kurooto itself (id "main", always there, where
Kurooto's own messages land), each session is a separate AI conversation whose context carries over for as long as
it lives (modules/chat.py keeps each one's turns), like an AI web app. Telegram and "main" keep the old 2-hour window.

Kept in <state>/calls/sessions.json: {"rev", "sessions": {id: {id, title, created, updated, pinned, last, read,
named}}}. An id is 16 hex characters the phone makes (so it can start a chat with the computer off) or "main". A
session's title is its first message's first words, or with calls.chat_titles = "ai" a short title the AI writes
after the first answer; a title you gave it (session.rename) is never replaced. The list, with the commands from
/help, goes to the call line (op "chat-sessions") after each change, so a phone can catch up with the computer off;
the call line keeps each session's last 50 messages (worker.js). calls.chat_sessions off: everything is "main" again
and the session ops are refused (the sessions and their context stay until it's back on).

The protocol is in docs/wiki/dev/calls-and-phone.md ("The chat's protocol")."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.modules.calls import Calls

MAIN = "main"
SID = re.compile(r"[0-9a-f]{16}")
MAX = 100  # sessions at most (main included)
TITLE_MAX = 80
LAST_MAX = 120
WORDS = 6  # a title from the first message: this many words at most
COMMANDS_MAX = 100


def _clip(s: str, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def first_words(text: str) -> str:
    """A title from a message: its first few words, without Markdown marks."""
    words = re.sub(r"[*_`#>\[\]]+", "", str(text or "")).split()
    return _clip(" ".join(words[:WORDS]), 40)


class Sessions:
    def __init__(self, calls: Calls):
        self.calls = calls
        self.app = calls.app
        self.file = calls.dir / "sessions.json"
        self.dirty = False  # a change the call line hasn't heard yet (sent again by flush). Nothing goes at start:
        # the line gets the list with the first change or the app's first `sync`, so nothing of it leaves unless used

    def on(self) -> bool:
        return bool(self.calls.setting("chat_sessions"))

    def _lock(self):
        return Lock(self.app.paths.state, "calls-sessions")

    def _main(self, t: float) -> dict:
        return {"id": MAIN, "title": self.app.name or "Kurooto", "created": int(t), "updated": int(t), "pinned": True,
                "last": "", "read": "", "named": "fixed"}  # fmt: skip

    def _load(self) -> dict:
        d = jload(self.file, {}) or {}
        rows = {
            k: v
            for k, v in (d.get("sessions") or {}).items()
            if isinstance(v, dict) and (k == MAIN or SID.fullmatch(k))
        }
        if MAIN not in rows:
            rows[MAIN] = self._main(time.time())
        rows[MAIN]["title"] = self.app.name or "Kurooto"  # Kurooto's own chat carries the assistant's name
        return {"rev": int(d.get("rev") or 0), "sessions": rows}

    def _save(self, d: dict) -> None:
        d["rev"] = int(d.get("rev") or 0) + 1
        jsave(self.file, d)
        self.dirty = True

    # ------------------------------------------------------------------------------------- reading
    def norm(self, sid) -> str | None:
        """The session a message belongs to: "main" for none (old app versions) or with sessions off; None for an
        id that can't be one."""
        sid = str(sid or "").strip()
        if not sid or sid == MAIN or not self.on():
            return MAIN
        return sid if SID.fullmatch(sid) else None

    def get(self, sid: str) -> dict | None:
        return self._load()["sessions"].get(sid)

    def listing(self) -> list[dict]:
        """For the phone: main first, then pinned, then the latest."""
        rows = list(self._load()["sessions"].values()) if self.on() else [self._load()["sessions"][MAIN]]
        rows.sort(key=lambda r: (r["id"] != MAIN, not r.get("pinned"), -int(r.get("updated") or 0)))
        keys = ("id", "title", "created", "updated", "pinned", "last", "read")
        return [{k: r.get(k, "" if k in ("title", "last", "read") else 0) for k in keys} for r in rows]

    def commands(self) -> list[dict]:
        """The commands the "/" list offers, as Telegram's menu has them (/help, each feature's that's on, skills)."""
        tg = self.app.modules.get("telegram")
        try:
            menu = tg.menu() if tg is not None else []
        except Exception:
            menu = []
        return [{"name": m["command"], "help": m["description"]} for m in menu][:COMMANDS_MAX]

    def message(self, commands: bool = True) -> dict:
        """The `kind: "sessions"` message."""
        out: dict = {"kind": "sessions", "srev": self._load()["rev"], "sessions": self.listing()}
        if commands:
            out["commands"] = self.commands()
        out["switches"] = {k: bool(self.calls.setting(k)) for k in ("chat_sessions", "chat_files_inline", "chat_edit")}
        s = self.app.settings  # (0.9.1) what the phone may send: its place names (L60), its other calls (L87)
        out["switches"]["place_names"] = bool(s.get("reminders.places") and s.get("reminders.place_names"))
        out["switches"]["phone_busy"] = bool(s.get("calls.phone_busy") or s.get("voice.listen.phone_call"))
        return out

    def push(self, quiet: bool = False) -> bool:
        """The list (and the commands) to the call line, which keeps it and tells the phones (quiet: only the ones
        connected straight to it, no push notification: a read mark)."""
        m = self.message()
        self.calls.chat.live("sessions")  # the dashboard's Chat page asks for the list again

        def done(res):
            if res and not res.get("error"):
                self.dirty = False

        return self.calls.connector.admin_later(
            "chat-sessions",
            then=done,
            rev=m["srev"],
            sessions=m["sessions"],
            commands=m["commands"],
            switches=m["switches"],
            quiet=quiet,
        )

    # ------------------------------------------------------------------------------------- changing
    def touch(self, sid: str, m: dict) -> bool:
        """A message in a session: its last line and time; a session the computer hasn't heard of yet (made on the
        phone while it was off, its session.new lost) is made now, titled from this message. True if it was new."""
        with self._lock():
            d = self._load()
            rows = d["sessions"]
            new = sid not in rows
            if new:
                if len(rows) >= MAX or m.get("from") != "you":
                    return False
                rows[sid] = {"id": sid, "title": "", "created": int(m.get("at") or time.time()), "pinned": False,
                             "read": "", "named": ""}  # fmt: skip
            r = rows[sid]
            r["updated"] = int(m.get("at") or time.time())
            r["last"] = _clip(m.get("text") or (m.get("file") or {}).get("name") or "", LAST_MAX)
            named = False
            if not r.get("title") and m.get("from") == "you":
                r["title"] = first_words(m.get("text") or "") or _clip((m.get("file") or {}).get("name") or "", 40)
                r["named"] = "words" if r["title"] else ""
                named = bool(r["title"])
            if new or named:
                self._save(d)  # a new chat or a new title: the call line hears (pushed below)
            else:  # the last line changes with every message: the call line keeps its own (worker.js chatSay)
                jsave(self.file, d)
        if new or named:
            self.push()
        return new

    def new(self, sid: str, title: str = "") -> tuple[bool, str]:
        if sid == MAIN or not SID.fullmatch(sid or ""):
            return False, "That isn't a new chat's id."
        with self._lock():
            d = self._load()
            rows = d["sessions"]
            if sid in rows:  # sent again (the phone retried): the same chat
                return True, "That chat is there already."
            if len(rows) >= MAX:
                return False, f"You have {MAX} chats; delete one first."
            t = int(time.time())
            title = _clip(title, TITLE_MAX)
            rows[sid] = {"id": sid, "title": title, "created": t, "updated": t, "pinned": False, "last": "",
                         "read": "", "named": "you" if title else ""}  # fmt: skip
            self._save(d)
        self.app.events.emit("chat_session", op="new")
        self.push()
        return True, "New chat."

    def rename(self, sid: str, title: str) -> tuple[bool, str]:
        title = _clip(title, TITLE_MAX)
        if not title:
            return False, "A chat needs a name."
        if sid == MAIN:
            return False, "Kurooto's own chat keeps its name."
        return self._change(sid, {"title": title, "named": "you"}, "Renamed.")

    def pin(self, sid: str, on: bool) -> tuple[bool, str]:
        if sid == MAIN:
            return True, "Kurooto's own chat is always first."
        return self._change(sid, {"pinned": bool(on)}, "Pinned." if on else "Unpinned.")

    def read(self, sid: str, upto: str) -> tuple[bool, str]:
        return self._change(sid, {"read": str(upto or "")[:16]}, "", quiet=True)

    def _change(self, sid: str, fields: dict, said: str, quiet: bool = False) -> tuple[bool, str]:
        with self._lock():
            d = self._load()
            r = d["sessions"].get(sid)
            if r is None:
                return False, "There's no such chat."
            r.update(fields)
            self._save(d)
        self.push(quiet=quiet)
        return True, said

    def delete(self, sid: str) -> tuple[bool, str]:
        """The chat, its AI context and its messages here go; files sent in it stay where they were saved."""
        if sid == MAIN:
            return False, "Kurooto's own chat can't be deleted."
        with self._lock():
            d = self._load()
            if d["sessions"].pop(sid, None) is None:
                return True, "That chat is gone already."
            self._save(d)
        chat = self.app.modules.get("chat")
        if chat is not None and hasattr(chat, "forget_session"):
            chat.forget_session(sid)
        self.calls.chat.drop_session(sid)
        self.app.events.emit("chat_session", op="delete")
        self.push()
        return True, "Deleted."

    def set_title(self, sid: str, title: str, how: str) -> bool:
        """A title the AI wrote (how "ai"): kept only while you haven't named the chat yourself."""
        title = _clip(title, TITLE_MAX)
        with self._lock():
            d = self._load()
            r = d["sessions"].get(sid)
            if not title or r is None or r.get("named") in ("you", "fixed"):
                return False
            r.update(title=title, named=how)
            self._save(d)
        self.push()
        return True

    # --------------------------------------------------------------------------------------- titles
    def first_answer(self, sid: str, user: str, reply: str) -> str | None:
        """The first answer in a session: with calls.chat_titles = "ai", a short AI request names it (quiet, text
        only; the title lands through the then-action calls.chat_title). The job's id, or None."""
        if sid == MAIN or str(self.calls.setting("chat_titles") or "") != "ai":
            return None
        r = self.get(sid)
        if r is None or r.get("named") in ("you", "fixed", "ai"):
            return None
        prompt = (
            "Write a short title (at most 6 words, no quotes, no full stop) for a chat that starts like this. "
            f"Answer with the title only.\n\nUser: {user[:600]}\n\nAssistant: {reply[:600]}"
        )
        return self.app.jobs.submit(prompt, title="A chat's title", effort="low", quiet=True, text_only=True,
                                    lane="chk", then="calls.chat_title", then_payload={"session": sid})  # fmt: skip

    def titled(self, job, result, payload: dict) -> None:
        """(then-action calls.chat_title) The AI's title, its first line without quotes."""
        if not getattr(result, "ok", False) or not getattr(result, "text", ""):
            return
        line = next((x for x in str(result.text).splitlines() if x.strip()), "")
        title = line.strip().strip("\"'“”‘’*#").rstrip(".").strip()
        self.set_title(str(payload.get("session") or ""), title, "ai")
