"""Your command words: keep the short words you're used to typing. A word of yours stands for a command or the start
of a request, and typing it works as if you'd typed what it stands for:

    /words add j = /journal         /j had a good day          -> /journal had a good day
    /words add deep = high:         /deep why does this fail   -> high: why does this fail (a harder AI request)
    /words add due = what's due     /due                       -> what's due

It changes nothing else: what a word stands for goes through Kurooto exactly as if you'd typed it, with the same
rules (anything that needs your tap still does). A word can't stand for another word, and Kurooto's own commands and
your features' commands always win over a word of the same name.
"""

from __future__ import annotations

import re

from kurooto.core.config import register_defaults
from kurooto.modules.base import Answer, Command, Incoming, Module

register_defaults(
    "habits",
    {
        "words": {},  # your words and what each stands for, e.g. {"j": "/journal", "deep": "high:"}
    },
)

WORD = re.compile(r"[a-z][a-z0-9_]{0,30}")
TYPED = re.compile(r"^/(?P<w>[a-z][a-z0-9_]{0,30})\b")
ADD = re.compile(r"^add\s+/?(?P<w>\S+)\s*(?:=|as|->)\s*(?P<to>.+)$", re.I | re.S)


class Habits(Module):
    id = "habits"
    title = "Your command words"
    description = "Short words of your own for commands and requests you type often: /j for /journal, and so on."
    privacy = "Stays on this computer: a word only stands for what you type."

    def words(self) -> dict[str, str]:
        w = self.setting("words") or {}
        return (
            {str(k).lower(): str(v) for k, v in w.items() if WORD.fullmatch(str(k).lower())}
            if isinstance(w, dict)
            else {}
        )

    def taken(self) -> set[str]:
        """Command names Kurooto or a feature already answers (they win over a word)."""
        from kurooto.core.commands import CORE

        names = {n for names, _ in CORE for n in names} | {"words"}
        for m in self.app.modules.values():
            if m is self:
                continue
            try:
                names |= {c.name for c in m.commands()}
            except Exception:  # noqa: S112 (a feature whose commands fail has none to take)
                continue
        return names

    # ------------------------------------------------------------------------------------------ a word typed
    def _run(self, msg: Incoming, word: str, rest: str) -> str:
        text = f"{self.words().get(word, '').strip()} {rest.strip()}".strip()
        said: list[tuple[str, list | None]] = []
        waiting = True

        def respond(t, buttons=None):  # what comes back at once is this word's answer; anything later goes on
            if waiting:
                said.append((str(t), buttons))
                return None
            return msg.respond(t, buttons=buttons) if msg.respond else None

        self.app.handle(Incoming(text, via=msg.via, message_id=msg.message_id, files=msg.files, respond=respond))
        waiting = False
        for t, b in said[:-1]:
            if msg.respond:
                msg.respond(t, buttons=b)
        if said:
            t, b = said[-1]
            return Answer(t, b)
        return f"Sent as: {text[:80]}"

    # ------------------------------------------------------------------------------------------ commands
    def commands(self):
        out = [Command("words", "your command words: /words add j = /journal, /words remove j", self._cmd)]
        for w, to in sorted(self.words().items()):  # each word of yours (its card says: commands you name yourself)
            out.append(Command(w, f"your word for {to[:40]}", lambda msg, arg, w=w: self._run(msg, w, arg)))
        return out

    def _cmd(self, msg: Incoming, arg: str) -> str:
        a = arg.strip()
        words = self.words()
        if not a:
            if not words:
                return "No command words yet. /words add j = /journal makes /j work like /journal."
            return "Your command words:\n" + "\n".join(f"/{k} → {v}" for k, v in sorted(words.items()))
        m = ADD.match(a)
        if m:
            w, to = m["w"].lower().lstrip("/"), m["to"].strip()
            if not WORD.fullmatch(w):
                return "A word is letters, digits and _, starting with a letter (up to 31)."
            if w in self.taken():
                return f"/{w} is already a command; a word of the same name would never be used."
            t = TYPED.match(to)
            if t and t["w"].lower() in words:
                return "A word can't stand for another word: give what that one stands for instead."
            if len(to) > 300:
                return "That's long for a word: up to 300 characters."
            self.app.settings.set("habits.words", {**words, w: to})
            return f"/{w} now works like {to}. /words remove {w} takes it away."
        r = re.match(r"^(?:remove|rm|forget)\s+/?(\S+)$", a, re.I)
        if r:
            w = r[1].lower()
            if w not in words:
                return f"/{w} isn't one of your words."
            self.app.settings.set("habits.words", {k: v for k, v in words.items() if k != w})
            return f"/{w} is gone."
        return "/words, /words add j = /journal, /words remove j"
