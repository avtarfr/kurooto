"""Doubt queue: a doubt from a class, kept for the next one. "/doubt la why does the rank not change?" or "I have a
doubt about eigenvalues" adds a line to that subject's doubts note (<subject>/doubts.md; your notes layout says where
it goes). Before the subject's next class (doubts.before_min, 30 minutes), its open doubts come to you, each with a
button that ticks it off in the note. No AI: they're yours to ask in class, and nothing leaves the computer.

Which subject a doubt is for: the one you name (its name or short name), else the class that's on now or ended in the
last few hours (doubts.recent_h, 3), else you pick it from buttons.

    /doubt la <the doubt>     add one (longer doubts, or ones with several sentences, need /doubt)
    /doubts [subject]         the open ones, with Tick buttons
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid

from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.core.tools import TASK, add_to_section, write_note_file
from kurooto.modules.base import Command, Incoming, Intent, Module

register_defaults(
    "doubts",
    {
        "before_min": 30,  # open doubts come this long before the subject's next class
        "recent_h": 3,  # a doubt naming no subject is for the class that's on, or ended this many hours ago
        "to_revision": True,  # an open doubt about a topic ranks it with weak recall in Exam season's revision plan
        "share": False,  # open doubts go with a hint request for that subject and on a call before its class (your AI)
        "share_h": 3,  # ...a call this many hours before the class
    },
)

ADD = re.compile(
    r"^\s*(?:i\s+(?:have|had|'ve got|have got|got)\s+(?:a\s+|one\s+|another\s+)?doubts?|(?:a\s+|new\s+)?doubt)"
    r"(?:\s+(?:about|on|in|regarding|for|with|from))?\s*[:,-]?\s+(?P<what>\S.*)$",
    re.I,
)
SHOW = re.compile(
    r"^\s*(?:show|list|what are)\s+(?:me\s+)?(?:my\s+)?(?:open\s+)?doubts\b(?:\s+(?:in|for|on)\b)?\s*(?P<s>.*)$", re.I
)
SECTION = "Doubts"
MAX_LISTED = 8  # doubts per message with a Tick button each


def doubt_id(text: str) -> str:
    """A doubt's short id, from its words (so it's found again after the note was edited around it)."""
    norm = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(norm.encode()).hexdigest()[:8]


class Doubts(Module):
    id = "doubts"
    title = "Doubt queue"
    description = "Doubts from class, kept in each subject's notes and brought back before its next class."
    requires = ("subjects",)

    def __init__(self, app):
        super().__init__(app)
        self.dir = app.paths.state / "doubts"

    def start(self):
        self.every("before", "every 5m", self.before_class)

    # ---------------------------------------------------------------------------------------- the note
    def note(self, slug: str):
        return layout.path(self.app, "doubts", subject=slug)

    def _read(self, slug: str) -> str | None:
        f = self.note(slug)
        try:
            return f.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
        except (OSError, UnicodeDecodeError):
            return None  # not plain UTF-8: left alone

    def add(self, slug: str, text: str) -> str:
        """Add one doubt to the subject's note (made if it isn't there)."""
        text = re.sub(r"\s+", " ", text).strip()
        sub = self.app.modules["subjects"]
        name = sub.name_of(slug)
        if not text:
            return "What's the doubt? /doubt la why does the rank not change?"
        f = self.note(slug)
        old = self._read(slug)
        if old is None:
            return f"I couldn't add it: {layout.shown(self.app, f)} isn't plain text."
        if any(doubt_id(d) == doubt_id(text) for d in self.open(slug)):
            return f"That one is already on {name}'s doubts."
        if not old.strip():
            old = layout.frontmatter(self.app, "doubts", f, title=f"{name}: doubts", subject=slug)
            old += f"# {name}: doubts\n\nThey come back before the next class; tick them once they're answered.\n"
        write_note_file(f, add_to_section(old, SECTION, f"- [ ] {text} ({now():%Y-%m-%d})"))
        self.app.events.emit("doubt_added", subject=slug)
        n = len(self.open(slug))
        nxt = self.next_class(slug)
        when = f" before {name} {nxt:%a %H:%M}" if nxt else ""
        return f"Added to {name}'s doubts ({n} open). They come back{when or ' before its next class'}."

    def open(self, slug: str) -> list[str]:
        """The open doubts in the subject's note, in order (their text, without the box and date)."""
        out = []
        for ln in (self._read(slug) or "").splitlines():
            if TASK.match(ln):
                t = re.sub(r"^\s*(?:[-*+]|\d+[.)]) \[ \]\s*", "", ln).strip()
                out.append(re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)$", "", t))
        return out

    def tick(self, slug: str, did: str) -> bool:
        """Tick the open doubt with this id in the note. Nothing else in it changes."""
        text = self._read(slug)
        if not text:
            return False
        lines = text.split("\n")
        for i, ln in enumerate(lines):
            if TASK.match(ln):
                t = re.sub(r"^\s*(?:[-*+]|\d+[.)]) \[ \]\s*", "", ln).strip()
                if doubt_id(re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)$", "", t)) == did:
                    lines[i] = ln.replace("[ ]", "[x]", 1)
                    write_note_file(self.note(slug), "\n".join(lines))
                    self.app.events.emit("doubt_ticked", subject=slug)
                    return True
        return False

    # ------------------------------------------------------------------------------------ the classes
    def next_class(self, slug: str, days: int = 7) -> dt.datetime | None:
        sub = self.app.modules["subjects"]
        t = now()
        for d in range(days + 1):
            for c in sub.classes_on(t.date() + dt.timedelta(days=d)):
                if c.get("subject") == slug and c["start_dt"] > t:
                    return c["start_dt"]
        return None

    def current_subject(self) -> str | None:
        """The class that's on now, or the latest one that ended in the last recent_h hours."""
        return self.subject_at(now())

    def subject_at(self, t: dt.datetime) -> str | None:
        """The class that was on at t, or the latest one that ended in the recent_h hours before it (the notes sorter's
        class hint reads it too, sorter.by_class)."""
        recent = dt.timedelta(hours=float(self.setting("recent_h") or 0))
        hits = [
            c
            for c in self.app.modules["subjects"].classes_on(t.date())
            if c.get("subject") and c["start_dt"] <= t <= c["end_dt"] + recent
        ]
        return max(hits, key=lambda c: c["start_dt"])["subject"] if hits else None

    def before_class(self, payload: dict | None = None) -> int:
        """Every few minutes: a class starting within before_min with open doubts gets them sent, once."""
        t = now()
        ahead = dt.timedelta(minutes=float(self.setting("before_min") or 30))
        f = self.dir / "told.json"
        old = jload(f, {}) or {}
        today = t.date().isoformat()
        told = {k: v for k, v in old.items() if v >= (t.date() - dt.timedelta(days=2)).isoformat()}
        sent = 0
        for c in self.app.modules["subjects"].classes_on(t.date()):
            slug = c.get("subject")
            key = f"{today}|{c['start_dt']:%H:%M}|{slug}"
            if not slug or key in told or not (c["start_dt"] - ahead <= t < c["start_dt"]):
                continue
            told[key] = today
            items = self.open(slug)
            if items:
                head = f"Before {c['name']} at {c['start_dt']:%H:%M}: your open doubts"
                self._send(slug, items, head)
                self.app.events.emit("doubts_told", subject=slug, n=len(items))
                sent += 1
        if told != old:
            jsave(f, told)
        return sent

    # ------------------------------------------------------------------------- shared with your AI (0.9.0)
    def shared(self, slug: str) -> list[str]:
        """The subject's open doubts for an AI request (the hint ladder's), with doubts.share on; else none."""
        return self.open(slug)[:MAX_LISTED] if self.setting("share") else []

    def call_brief(self) -> dict:
        """On a call in the hours before a class (doubts.share_h) with open doubts: they're in the call's brief, so
        they can come up. Only with doubts.share on: the call's AI may be a cloud one."""
        if not self.setting("share"):
            return {}
        t = now()
        ahead = dt.timedelta(hours=float(self.setting("share_h") or 3))
        sub, out, seen = self.app.modules["subjects"], [], set()
        for c in sub.classes_on(t.date()):
            slug = c.get("subject")
            if not slug or slug in seen or not (t < c["start_dt"] <= t + ahead):
                continue
            seen.add(slug)
            items = self.open(slug)[:MAX_LISTED]
            if items:
                out.append(f"{c['name']} at {c['start_dt']:%H:%M}: " + "; ".join(items))
        return {"open_doubts_before_class": out} if out else {}

    # -------------------------------------------------------------------------------------- messages
    def _refs(self) -> dict:
        return jload(self.dir / "refs.json", {}) or {}

    def _send(self, slug: str, items: list[str], head: str, reply=None) -> None:
        refs = self._refs()
        lines, row, rows = [head], [], []
        for i, text in enumerate(items[:MAX_LISTED], 1):
            did = doubt_id(text)
            refs[did] = slug
            lines.append(f"{i}. {text}")
            row.append((f"Tick {i}", f"doubt:{did}:tick"))
            if len(row) == 4:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        more = len(items) - MAX_LISTED
        if more > 0:
            lines.append(f"…and {more} more in {layout.shown(self.app, self.note(slug))}")
        jsave(self.dir / "refs.json", dict(list(refs.items())[-300:]))
        text = "\n".join(lines)
        if reply is not None:
            reply(text, buttons=rows)
        else:
            self.app.notify(text, kind="reminder", buttons=rows, why="doubts.before_class", about=head, item=slug)

    def callbacks(self):
        return {"doubt": self._button}

    def _button(self, ref: str, act: str) -> str:
        if act == "tick":
            slug = self._refs().get(ref)
            if not slug:
                return "I don't know that doubt any more."
            return "Ticked in your notes." if self.tick(slug, ref) else "Already ticked (or changed in the note)."
        if act.startswith("s") and act[1:].isdigit():  # the subject for a doubt that named none
            pending = jload(self.dir / "pending.json", {}) or {}
            text = pending.pop(ref, None)
            jsave(self.dir / "pending.json", pending)
            subjects = self.app.modules["subjects"].subjects()
            i = int(act[1:])
            if text is None or i >= len(subjects):
                return "That doubt is gone; send it again."
            return self.add(subjects[i]["slug"], text)[:190]
        return "unknown button"

    def take(self, msg: Incoming, text: str) -> str | None:
        """A doubt from you: its subject named, from the class just now, or asked with buttons."""
        sub = self.app.modules["subjects"]
        text = text.strip()
        if not text:
            return "Usage: /doubt la why does the rank not change?"
        first, _, rest = text.partition(" ")
        slug = self._named(first.rstrip(":,-"))
        if slug and rest.strip():
            return self.add(slug, rest)
        found = sub.find_in(text)
        if len(found) == 1:
            return self.add(found[0], text)
        slug = self.current_subject()
        if slug and not found:
            return self.add(slug, text)
        subjects = sub.subjects()
        if not subjects:
            return "Add your subjects first (/subject add Linear Algebra (la)), then the doubt."
        pid = uuid.uuid4().hex[:8]
        pending = jload(self.dir / "pending.json", {}) or {}
        pending[pid] = text
        jsave(self.dir / "pending.json", dict(list(pending.items())[-50:]))
        rows, row = [], []
        for i, s in enumerate(subjects[:12]):
            row.append(((s.get("aliases") or [s["name"]])[0][:20], f"doubt:{pid}:s{i}"))
            if len(row) == 4:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        msg.reply("Which subject is this doubt for?", buttons=rows)
        return None

    def _named(self, word: str) -> str | None:
        """The subject this word names exactly (its slug, name or a short name), or None."""
        w = word.strip().lower()
        for s in self.app.modules["subjects"].subjects():
            if w and w in (s["slug"], s["name"].lower(), *(a.lower() for a in s.get("aliases", []))):
                return s["slug"]
        return None

    # ------------------------------------------------------------------------------------ what you send
    def commands(self):
        return [
            Command("doubt", "a doubt for the next class: /doubt la why does the rank not change?", self._doubt),
            Command("doubts", "your open doubts, with Tick buttons (/doubts la)", self._list),
        ]

    def _doubt(self, msg: Incoming, arg: str) -> str | None:
        return self.take(msg, arg)

    def _list(self, msg: Incoming, arg: str) -> str | None:
        sub = self.app.modules["subjects"]
        want = sub.resolve(arg.strip()) if arg.strip() else None
        if arg.strip() and not want:
            return f"No subject called {arg.strip()}."
        slugs = [want] if want else [s["slug"] for s in sub.subjects()]
        shown = 0
        for slug in slugs:
            items = self.open(slug)
            if items:
                self._send(slug, items, f"{sub.name_of(slug)}: open doubts", reply=msg.reply)
                shown += 1
        if not shown:
            return f"No open doubts{' for ' + sub.name_of(want) if want else ''}."
        return None

    def intents(self):
        def add(text: str):
            m = ADD.match(text)
            return {"what": m["what"]} if m else None

        def show(text: str):
            m = SHOW.match(text)
            return {"s": m["s"].strip(" ?.")} if m else None

        return [
            Intent(
                "add_doubt",
                "a doubt from class, for the next one",
                add,
                lambda m, s: self.take(m, s["what"]) or "It's saved once you tap its subject.",
                examples=("I have a doubt about why the rank doesn't change in la",),
            ),
            Intent(
                "show_doubts",
                "my open doubts",
                show,
                lambda m, s: self._list(m, s["s"]),
                questions=True,
                examples=("what are my doubts?", "show my doubts"),
            ),
        ]

    def help(self):
        return ['"I have a doubt about …", /doubt la …, /doubts']
