"""After class: a couple of minutes after each class in your timetable ends, Kurooto asks what was worth keeping.
Reply on Telegram (a line or two, photos of the board or slides, files, a voice note) and it goes into that subject's
class log in your notes (<subject>/class-log.md, or where your notes layout keeps it), with the photos and files moved
to the subject's files folder (<subject>/files/, or under files.folder outside your notes) and linked. With Chat on,
the AI also writes a proper study log for the class (the study-log skill).

"Nothing new" ends it; "Later" keeps the question for your evening check-in call. No questions for classes you skip
(/skip), on holidays, in exam periods or after the term's last day (Subjects: /term).

Only some subjects: capture.subjects lists the ones to ask about (empty: every subject), capture.skip_subjects the
ones never to ask about (a subject's short name, full name or alias works in both).
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules import daily
from kurooto.modules.base import Incoming, Module

register_defaults(
    "capture",
    {
        "delay_min": 2,
        "study_log": True,  # with Chat on, the AI writes one
        "subjects": [],  # ask only after these subjects' classes; empty: every subject
        "skip_subjects": [],  # never ask after these
    },
)

IMAGES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")


class Capture(Module):
    id = "capture"
    title = "After-class notes"
    description = (
        "A couple of minutes after each class ends, you're asked what was worth keeping; replies go to its log."
    )
    requires = ("telegram", "subjects")
    privacy = (
        "Your replies, photos and files go into the subject's class log in your notes, on this computer. With Chat on, "
        "your reply and the files you sent go to the AI you picked, to write a study log (capture.study_log)."
    )

    def start(self):
        self.action("ask", self._ask)
        self.app.ask.hooks["capture.answer"] = self._hook
        self.every("plan", "daily 00:10", lambda p: self._plan())
        self._plan()

    def stop(self):
        super().stop()
        self.app.ask.hooks.pop("capture.answer", None)

    # ------------------------------------------------------------------------------------- state
    def _state_file(self, day: dt.date) -> Path:
        return self.app.paths.state / "capture" / f"{day.isoformat()}.json"

    def _set(self, day: str, slug: str, **kw) -> None:
        d = dt.date.fromisoformat(day)
        st = jload(self._state_file(d), {}) or {}
        st[slug] = {**st.get(slug, {}), **kw}
        jsave(self._state_file(d), st)

    def statuses(self, day: dt.date | None = None) -> dict[str, str]:
        """{subject: "asked" | "answered" | "nothing" | "later" | "skipped"} for a day's classes."""
        out = {}
        for slug, s in (jload(self._state_file(day or now().date()), {}) or {}).items():
            status = s.get("status", "")
            if status == "asked" and s.get("qid"):
                q = self.app.ask.get(s["qid"]) or {}
                status = "later" if q.get("status") == "later" else status
            out[slug] = status
        return out

    # ------------------------------------------------------------------------------------ asking
    def _chosen(self, key: str) -> set[str]:
        """The subjects in capture.subjects or capture.skip_subjects, as slugs ("all" or nothing: none)."""
        v = self.setting(key) or []
        if isinstance(v, str):
            v = [] if v.strip().lower() in ("", "all") else v.split(",")
        subjects = self.app.modules["subjects"]
        return {subjects.resolve(str(x)) or str(x).strip().lower() for x in v if str(x).strip()}

    def wanted(self, slug: str) -> bool:
        """Is the after-class question on for this subject? capture.subjects (if any) and not capture.skip_subjects."""
        only = self._chosen("subjects")
        return slug not in self._chosen("skip_subjects") and (not only or slug in only)

    def _plan(self) -> None:
        subjects = self.app.modules["subjects"]
        delay = dt.timedelta(minutes=self.setting("delay_min") or 2)
        for c in subjects.classes_on():
            if not c.get("subject"):
                continue  # a class-calendar event that doesn't name one of your subjects: no log to write it into
            if not self.wanted(c["subject"]):
                continue
            at = c["end_dt"] + delay
            if at > now():
                self.app.scheduler.at(
                    at,
                    "capture.ask",
                    {"subject": c["subject"], "name": c["name"], "day": at.date().isoformat(), "start": c["start"]},
                    key=f"capture:{c['subject']}:{c['end']}",
                    module=self.id,
                    grace_s=3 * 3600,
                )

    def _ask(self, p: dict) -> None:
        subjects = self.app.modules["subjects"]
        day = dt.date.fromisoformat(p["day"])
        if not self.wanted(p["subject"]):  # taken off after the day was planned
            self.app.events.emit("capture_skipped", subject=p["subject"], why="not_chosen")
            return
        if p["subject"] in subjects.skipped(day):
            self._set(p["day"], p["subject"], status="skipped")
            self.app.events.emit("capture_skipped", subject=p["subject"], why="skipped")
            return
        why = subjects.no_classes(day)  # an exam period or the term's end, set after the day was planned
        if why:
            self.app.events.emit("capture_skipped", subject=p["subject"], why=why.replace(" ", "_"))
            return
        qid = self.app.ask.ask(
            f"How was {p['name']}? Anything worth keeping (a definition, a doubt, homework)? Reply here: a line or "
            "two, or photos of the board or slides.",
            choices=["Nothing new"],
            hook="capture.answer",
            hook_payload={"subject": p["subject"], "name": p["name"], "day": p["day"], "start": p.get("start", "")},
            expires=dt.timedelta(hours=20),
            source=self.id,
            title="After class",
            why="capture.after_class",
            about=p["name"],
            item=p["subject"],
            ws_item=f"class:{p['subject']}",
        )
        self._set(p["day"], p["subject"], status="asked", qid=qid)
        self.app.events.emit("capture_asked", subject=p["subject"])

    # ----------------------------------------------------------------------------------- answers
    def _hook(self, q: dict, answer: str) -> str | None:
        """Your answer (from Telegram, the app or a call): into the class log, and a study log by the AI."""
        p = q.get("hook_payload") or {}
        slug, day = p.get("subject", ""), p.get("day") or now().date().isoformat()
        if not slug:
            return None
        if q.get("nothing"):
            self._set(day, slug, status="nothing")
            self.app.events.emit("capture_nothing", subject=slug)
            return f"OK, nothing new from {p.get('name') or slug}."
        files = [self.app.workspace / f for f in q.get("files") or []]
        text = "" if answer == "(files)" else answer
        return self.save(slug, day, text, files, name=p.get("name"), start=p.get("start", ""))

    def save(self, slug: str, day: str, text: str, files: list[Path], name: str | None = None, start: str = "") -> str:
        """Add what you said, and the files (moved to the subject's files folder and linked), to its class log."""
        name = name or self.app.modules["subjects"].name_of(slug)
        f = layout.path(self.app, "class_log", subject=slug)
        f.parent.mkdir(parents=True, exist_ok=True)
        kept = [
            self._file_away(x, layout.file_dir(self.app, "subject", subject=slug), day) for x in files if x.is_file()
        ]
        links = [layout.file_link(self.app, p, f) for p in kept]
        new = not f.exists()
        with open(f, "a", encoding="utf-8") as out:
            if new:
                head = layout.frontmatter(self.app, "class_log", f, title=f"{name}: class log", bare=True, subject=slug)
                out.write(f"{head}# {name}: class log\n")
            body = "\n\n".join(x for x in [text.strip(), "\n".join(links)] if x)
            out.write(f"\n## {day}\n\n{body}\n")
        self._set(day, slug, status="answered")
        self.app.events.emit("capture_answered", subject=slug, files=len(kept))
        note = f"Saved to {layout.shown(self.app, f)}" + (f" with {len(kept)} file(s)" if kept else "") + "."
        if self.setting("study_log"):
            when = f" at {start}" if start else ""
            jid = daily.run_skill(
                self.app,
                "study-log",
                f"{name}, class on {day}{when}. What I said about it: {text.strip() or '(only the files)'}",
                files=kept or None,
                title=f"Study log: {name}",
            )
            if jid:
                note += " The AI is writing a study log for it."
        return note

    def _file_away(self, src: Path, folder: Path, day: str) -> Path:
        """Move a file you sent (it arrived in the inbox) to the subject's files; leave it where it is if that fails."""
        stem = src.name if src.name.startswith(day) else f"{day}-{src.name}"
        dest, n = folder / stem, 1
        try:
            folder.mkdir(parents=True, exist_ok=True)
            while dest.exists():
                dest = folder / f"{Path(stem).stem}-{n}{Path(stem).suffix}"
                n += 1
            shutil.move(str(src), str(dest))
            return dest
        except OSError:
            return src

    def replies(self):
        return {"capture": self._answer}

    def _answer(self, msg: Incoming, ref: str) -> str:
        """A reply to an after-class question sent before questions went through app.ask (an older message)."""
        slug, _, day = ref.partition("|")
        return self.save(slug, day or now().date().isoformat(), msg.text, list(msg.files))

    def callbacks(self):
        return {"cap": lambda ref, act: "OK."}
