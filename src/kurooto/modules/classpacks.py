"""Class packs: one student exports the section's setup as a small `.kurooto-course` file; classmates send it to their
own Kurooto, tick their electives and lab batch, and the timetable, term dates, holidays, recurring quizzes, dated
exams and attendance rules work from day one.

    /classpack export                 a pack of your setup (subjects, timetable, term note, recurring quizzes)
    /classpack export from terms/b    a pack of one term note alone (it can list every lab batch and elective)
    (send a .kurooto-course file)     its review: tick your electives and lab batch, change any rule, Import
    /classpack                        what you have: the pack, your choices, its rules
    /classpack set la 80              change a rule (also: la labs together, la quiz off, la quiz fri 11:00, la reset,
                                      all 80, electives ml, topology, batch B)
    /classpack remove                 take it out (your own setup stays); /classpack undo goes back one step

What a pack carries, and the checks that keep anything personal out of it, are in coursepack.py. Each pack is stamped
"checked against the official timetable on <date>": the maker has to give that date before the file is made, and
the review shows it to everyone who imports it.

An imported pack sits under your own setup, never in it, and nothing is written into your notes: Subjects reads its
courses, classes, holidays, exam periods and last day of classes under your term note and your own /class and /term
(yours win), Deadlines reads its quizzes under your recurring table and its exams with the term note's key dates,
and the attendance rules are here for an attendance feature to read (attendance_rule()). Importing again after a
mid-term reshuffle shows what changes for you before anything does, and keeps your electives, batch and changes.

State: <state>/classpacks/active.json (the pack, your choices and changes, and the one before it for undo) and
drafts/<id>.json (packs being reviewed or made; a week). Packs you make go to <data>/classpacks/, packs you're sent
to <data>/classpacks/received/. Events: classpack_imported, classpack_exported, classpack_refused, classpack_changed,
classpack_removed (counts only).
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import uuid
from pathlib import Path

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules import coursepack as cp
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "classpacks",
    {
        "min_pct": 75,  # the section's attendance rule in packs you make: at least this many percent of classes,
        "labs": "separate",  # with labs counted on their own ("separate") or together with the lectures ("together")
    },
)
PREFIX = "cpk"
DRAFT_DAYS = 7
STALE_DAYS = 14  # a pack whose term ended this long ago is worth a word in the weekly health list
SHOWN = 25  # lines of a diff in one message


class ClassPacks(Module):
    id = "classpacks"
    title = "Class packs"
    description = (
        "Your section's timetable, term dates, holidays, recurring quizzes and attendance rules in one file to "
        "share; import a classmate's and tick your electives and lab batch."
    )
    requires = ("telegram", "subjects")
    privacy = (
        "Stays on this computer. A pack you make is sent to your own Telegram for you to forward; it carries no "
        "names, keys or notes."
    )

    def __init__(self, app):
        super().__init__(app)
        self._cache: tuple | None = None  # ((mtime, size), what the active pack means for you)

    # --------------------------------------------------------------------------------------------- files
    @property
    def dir(self) -> Path:
        return self.app.paths.state / "classpacks"

    @property
    def active_file(self) -> Path:
        return self.dir / "active.json"

    @property
    def out_dir(self) -> Path:
        return self.app.paths.data / "classpacks"

    def record(self) -> dict:
        rec = jload(self.active_file, {})
        return rec if isinstance(rec, dict) else {}

    def active(self) -> dict | None:
        """The imported pack with your choices: {pack, electives, batch, changes, imported, previous}, or None."""
        rec = self.record()
        return rec if rec.get("pack") else None

    def _save(self, rec: dict) -> None:
        jsave(self.active_file, rec)
        self._cache = None

    def layer(self) -> dict | None:
        """What the imported pack means for you (coursepack.choose), read again whenever it changes."""
        try:
            st = self.active_file.stat()
        except OSError:
            self._cache = None
            return None
        sig = (st.st_mtime_ns, st.st_size)
        if self._cache and self._cache[0] == sig:
            return self._cache[1]
        rec, lay = self.active(), None
        if rec:
            try:
                pack = cp.validate(rec["pack"])
                lay = cp.choose(pack, rec.get("electives") or [], rec.get("batch") or "", rec.get("changes"))
            except (cp.PackError, KeyError, TypeError, ValueError):
                lay = None
        self._cache = (sig, lay)
        return lay

    # ------------------------------------------------------------------------------ what other features read
    def under(self, note: dict) -> dict:
        """Subjects: the term note's data over the pack's (the note wins where both say something)."""
        return cp.under(note, self.layer())

    def quiz_rows(self) -> list[dict]:
        """Deadlines: the pack's recurring quizzes for you, as rows of the recurring table (the table's rows win)."""
        lay = self.layer() or {"quizzes": []}
        keys = ("what", "every", "day", "time", "next", "until")
        return [
            {"subject": q["course"], **{k: q[k] for k in keys}, "line": "", "from_pack": True} for q in lay["quizzes"]
        ]

    def _subjects(self):
        s = self.app.modules.get("subjects")
        return s if s is not None and self.app.is_on("subjects") else None

    def attendance_rules(self) -> dict[str, dict]:
        """Each pack course's attendance rule, by your subject's slug: {"min_pct": 75, "labs": "separate" or
        "together", "yours": True when you changed it}. Empty without a pack."""
        lay = self.layer()
        if not lay:
            return {}
        sub = self._subjects()
        return {((sub.resolve(s["slug"]) if sub else None) or s["slug"]): dict(lay["rules"][s["slug"]])
                for s in lay["subjects"]}  # fmt: skip

    def attendance_rule(self, subject: str) -> dict | None:
        """One subject's rule from the pack ("la", "Linear Algebra"), or None when the pack doesn't have it."""
        sub = self._subjects()
        slug = (sub.resolve(subject) if sub else None) or subject
        return self.attendance_rules().get(slug)

    def class_kind(self, subject: str, day: str, start: str) -> str:
        """lecture, lab or tutorial: what the pack says a class is ("lecture" when it doesn't have it)."""
        sub = self._subjects()
        for c in (self.layer() or {"classes": []})["classes"]:
            mine = (sub.resolve(c["slug"]) if sub else None) or c["slug"]
            if (mine, c["day"], c["start"]) == (subject, day, start):
                return c["kind"]
        return "lecture"

    # -------------------------------------------------------------------------------------------- drafts
    def _draft_file(self, did: str) -> Path:
        return self.dir / "drafts" / f"{did}.json"

    def _draft(self, did: str) -> dict | None:
        if not re.fullmatch(r"[0-9a-f]{8}", did or ""):
            return None
        d = jload(self._draft_file(did), None)
        return d if isinstance(d, dict) and d.get("pack") else None

    def _new_draft(self, kind: str, **data) -> dict:
        old = (now() - dt.timedelta(days=DRAFT_DAYS)).isoformat()
        for f in (self.dir / "drafts").glob("*.json"):
            if str((jload(f, {}) or {}).get("created", "")) < old:
                f.unlink(missing_ok=True)  # Kurooto's own reviews nobody finished
        d = {"id": uuid.uuid4().hex[:8], "kind": kind, "created": now().isoformat(), **data}
        jsave(self._draft_file(d["id"]), d)
        return d

    def _put(self, d: dict) -> None:
        jsave(self._draft_file(d["id"]), d)

    def _drop(self, d: dict) -> None:
        self._draft_file(d["id"]).unlink(missing_ok=True)

    # ------------------------------------------------------------------------------------------ importing
    def take_pack(self, msg: Incoming) -> str | None:
        """A file sent on Telegram that's a class pack: its review ("" when the review was sent). None for any other
        file, which goes on to Files."""
        packs = [f for f in msg.files if cp.looks_like(f)]
        if not packs:
            return None
        if not self.app.is_on(self.id):
            return "That's a class pack. Turn on Class packs (dashboard → Features) and send it again to import it."
        f = packs[0]
        try:
            pack = cp.read(f)
        except cp.PackError as e:
            self.app.events.emit("classpack_refused", how="telegram")
            return f"That isn't a class pack I can use: {e}. Nothing was imported."
        keep = self.out_dir / "received" / f.name
        try:  # out of your notes' inbox: it's Kurooto's to keep
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), keep)
        except OSError:
            keep = f
        return self.review(pack, keep.name)

    def start_import(self, path: Path) -> tuple[bool, str]:
        """`kurooto classpack import FILE`: the review on Telegram."""
        try:
            pack = cp.read(path)
        except cp.PackError as e:
            self.app.events.emit("classpack_refused", how="file")
            return False, f"{Path(path).name} isn't a class pack I can use: {e}. Nothing was imported."
        said = self.review(pack, Path(path).name)
        return True, said or "Its review is on your Telegram: tick your electives and lab batch there, then Import."

    def review(self, pack: dict, name: str = "") -> str:
        """Start reviewing a pack before it's imported. "" when the review went out, else what to say instead."""
        rec = self.active()
        if rec and cp.same(rec["pack"], pack):
            return (
                f"That's the class pack you have already (checked {pack['checked']}); nothing changes. "
                "/classpack set changes your electives, batch or rules."
            )
        old = rec or {}
        el = {c["id"] for c in cp.electives(pack)}
        d = self._new_draft(
            "import",
            pack=pack,
            file=name,
            electives=[e for e in old.get("electives") or [] if e in el],
            batch=old.get("batch") if old.get("batch") in cp.batches(pack) else "",
            changes=old.get("changes") or {},
        )
        self._send_review(d)
        return ""

    def _layer_of(self, d: dict) -> dict:
        return cp.choose(d["pack"], d.get("electives") or [], d.get("batch") or "", d.get("changes"))

    @staticmethod
    def _example(pack: dict) -> str:
        c = pack["courses"][0]
        return (c["short"] or [c["id"]])[0]

    def _review_text(self, d: dict) -> str:
        pack, lay = d["pack"], self._layer_of(d)
        name = (f": {pack['title']}" if pack["title"] else "") + (
            f" ({pack['term']['name']})" if pack["term"]["name"] else ""
        )
        out = [
            f"Class pack{name}.",
            f"Checked against the official timetable on {pack['checked']} by whoever made it; where it differs from "
            "the official timetable, the official one is right.",
            f"In it: {cp.overview(pack)}.",
            f"For you: {cp.counts(lay)}.",
        ]
        els = cp.electives(pack)
        if els:
            took = [c["name"] for c in els if c["id"] in (d.get("electives") or [])]
            out.append(f"Your electives: {', '.join(took) or 'none ticked'} (tap to tick or untick).")
        if cp.batches(pack):
            out.append(f"Your lab batch: {d.get('batch') or 'none yet, so batch classes are left out'} (tap yours).")
        out.append(cp.rules_line(pack, lay) + ".")
        out += self._yours(d, pack)
        if not self.app.is_on("deadlines") and (lay["quizzes"] or lay["exams"]):
            out.append("Deadlines is off: turn it on for the quizzes and exams.")
        old, rec = self.layer(), self.active()
        if old is not None and rec:
            lines = cp.diff(old, lay)
            when = str(rec.get("imported", ""))[:10]
            if lines:
                out.append(f"\nWhat changes for you from the pack you have (imported {when}):")
                out += lines[:SHOWN] + ([f"... and {len(lines) - SHOWN} more"] if len(lines) > SHOWN else [])
            else:
                out.append(f"\nNothing changes for you from the pack you have (imported {when}).")
        ex = self._example(pack)
        out.append(
            f'\nTo change a rule before importing, reply to this message: "{ex} 80" (attendance), "{ex} labs '
            f'together", "{ex} quiz off", "{ex} quiz fri 11:00", "all 80".'
        )
        return "\n".join(out)

    @staticmethod
    def _yours(rec: dict, pack: dict) -> list[str]:
        """What you turned off or moved."""
        ch = rec.get("changes") or {}
        names = {c["id"]: c["name"] for c in pack["courses"]}

        def label(key: str) -> str:
            course, _, what = key.partition("|")
            hit = next(
                (x["what"] for x in pack["quizzes"] + pack["exams"] if cp.qkey(x["course"], x["what"]) == key), what
            )
            return f"{names.get(course, course)} {hit}"

        out = []
        if ch.get("off"):
            out.append("Left out by you: " + ", ".join(label(k) for k in ch["off"]) + ".")
        if ch.get("moved"):
            out.append("Moved by you: " + ", ".join(f"{label(k)} to {v['day'].title()} {v['time']}".rstrip()
                                                     for k, v in ch["moved"].items()) + ".")  # fmt: skip
        return out

    def _review_buttons(self, d: dict) -> list:
        did, pack = d["id"], d["pack"]
        rows: list = []
        els = cp.electives(pack)[:12]
        tick = [
            (("[x] " if c["id"] in (d.get("electives") or []) else "[ ] ") + c["name"][:28], f"{PREFIX}:{did}:e{i}")
            for i, c in enumerate(els)
        ]
        rows += [tick[i : i + 2] for i in range(0, len(tick), 2)]
        bs = cp.batches(pack)[:8]
        pick = [
            (f"Batch {b}" + (" (yours)" if b == d.get("batch") else ""), f"{PREFIX}:{did}:b{i}")
            for i, b in enumerate(bs)
        ]
        rows += [pick[i : i + 4] for i in range(0, len(pick), 4)]
        last = [("Import", f"{PREFIX}:{did}:go")]
        if els or bs:
            last.append(("Show again", f"{PREFIX}:{did}:show"))
        rows.append([*last, ("Cancel", f"{PREFIX}:{did}:x")])
        return rows

    def _send_review(self, d: dict) -> None:
        text = self._review_text(d) if d["kind"] == "import" else self._making_text(d)
        buttons = self._review_buttons(d) if d["kind"] == "import" else self._making_buttons(d)
        self.app.notify(text, kind="info", buttons=buttons, map_kind="classpack", map_ref=d["id"])

    def _import_button(self, d: dict, action: str) -> str:
        pack = d["pack"]
        if action == "go":
            return self._apply(d)
        if action == "show":
            self._send_review(d)
            return "Sent again below."
        m = re.fullmatch(r"([eb])(\d+)", action)
        if not m:
            return "That button isn't one I know."
        i = int(m[2])
        if m[1] == "e":
            els = cp.electives(pack)
            if i >= len(els):
                return "That elective isn't in the pack."
            cid, chosen = els[i]["id"], list(d.get("electives") or [])
            chosen = [x for x in chosen if x != cid] if cid in chosen else [*chosen, cid]
            d["electives"] = chosen
            said = f"{els[i]['name']}: {'ticked' if cid in chosen else 'not ticked'}"
        else:
            bs = cp.batches(pack)
            if i >= len(bs):
                return "That batch isn't in the pack."
            d["batch"] = "" if d.get("batch") == bs[i] else bs[i]
            said = f"Batch {bs[i]}" + ("" if d["batch"] else ": not yours")
        self._put(d)
        lay = self._layer_of(d)
        return f"{said}. For you: {cp.week(lay)} classes a week. Import when it's right (Show again lists it)."

    def _apply(self, d: dict) -> str:
        old = self.active()
        was = self.layer() if old else None
        prev = {k: v for k, v in (old or {}).items() if k != "previous"}
        rec = {
            "pack": d["pack"],
            "electives": d.get("electives") or [],
            "batch": d.get("batch") or "",
            "changes": d.get("changes") or {},
            "imported": now().isoformat(),
            "file": d.get("file") or "",
            "previous": prev,
        }
        self._save(rec)
        self._drop(d)
        self._refresh()
        lay = self.layer() or self._layer_of(d)
        changed = len(cp.diff(was, lay)) if was else 0
        self.app.events.emit(
            "classpack_imported",
            courses=len(lay["subjects"]),
            classes=len(lay["classes"]),
            quizzes=len(lay["quizzes"]),
            exams=len(lay["exams"]),
            again=old is not None,
            changes=changed,
        )
        title = f": {d['pack']['title']}" if d["pack"]["title"] else ""
        text = (
            f"Class pack imported{title}. For you: {cp.counts(lay)}. Your own classes (/class), term dates (/term), "
            "term note and recurring table win where they say something else. /classpack shows it; /classpack "
            "remove takes it out (/classpack undo goes back)."
        )
        if not self.app.is_on("deadlines") and (lay["quizzes"] or lay["exams"]):
            text += " Turn on Deadlines for its quizzes and exams."
        self.app.notify(text, kind="result")
        return "Imported."

    def _refresh(self) -> None:
        """Deadlines reads the pack's exams and quizzes now, not at its next hourly pass."""
        self._cache = None
        dl = self.app.modules.get("deadlines")
        if dl is None or not self.app.is_on("deadlines"):
            return
        for scan in ("scan_term", "scan_recurring"):
            try:
                getattr(dl, scan)()
            except Exception as e:  # the hourly pass tries again
                self.app.events.emit("deadlines_source_failed", source=scan, error=str(e)[:200])

    # ------------------------------------------------------------------------------------------- changes
    def _change(self, rec: dict, pack: dict, kind: str, a: dict, making: bool) -> str:
        """One change, to a pack being imported or the imported one (rec: electives, batch, changes), or, making
        a pack, to the pack itself. Returns what it did, in a few words."""
        names = {c["id"]: c["name"] for c in pack["courses"]}
        who = "every course" if a.get("course") == "*" else names.get(a.get("course", ""), "")
        if kind in ("title", "elective", "holiday_off") and not making:
            return "That's for making a pack (/classpack export)."
        if kind == "batch" and making:
            return "Lab batches come from the timetable: a Batch column in the term note (/classpack export from it)."
        if kind == "title":
            try:
                pack["title"] = cp.title(a["text"])
            except cp.PackError as e:
                return f"Not that title: {e}."
            return f"Title: {pack['title']}."
        if kind == "electives":
            el = {c["id"] for c in cp.electives(pack)}
            if making:
                for c in pack["courses"]:
                    c["elective"] = c["id"] in a["ids"]
                return "Electives: " + (", ".join(names[i] for i in a["ids"]) or "none") + "."
            if any(i not in el for i in a["ids"]):
                return (
                    "Only the pack's electives can be ticked: "
                    + (", ".join(names[i] for i in el) or "it has none")
                    + "."
                )
            rec["electives"] = list(a["ids"])
            return "Your electives: " + (", ".join(names[i] for i in a["ids"]) or "none") + "."
        if kind == "batch":
            rec["batch"] = a["batch"]
            return f"Your lab batch: {a['batch'] or 'none'}."
        if kind == "elective":
            for c in pack["courses"]:
                if c["id"] == a["course"]:
                    c["elective"] = a["on"]
            return f"{who}: {'an elective' if a['on'] else 'everyone takes it'}."
        if kind == "holiday_off":
            before = len(pack["term"]["holidays"])
            pack["term"]["holidays"] = [h for h in pack["term"]["holidays"] if not h["from"] <= a["date"] <= h["to"]]
            return (
                "Holiday left out." if len(pack["term"]["holidays"]) < before else f"There's no holiday on {a['date']}."
            )
        if kind in ("rule", "reset") and making:
            if kind == "reset":
                for c in pack["courses"]:
                    if a["course"] in ("*", c["id"]):
                        c.pop("attendance", None)
                return f"{who}: the section's rule."
            if a["course"] == "*":
                pack["attendance"] = {**pack["attendance"], **{k: a[k] for k in ("min_pct", "labs") if k in a}}
                return f"The section's rule: {cp.rule_text(pack['attendance'])}."
            for c in pack["courses"]:
                if c["id"] == a["course"]:
                    c["attendance"] = {**(c.get("attendance") or pack["attendance"]),
                                       **{k: a[k] for k in ("min_pct", "labs") if k in a}}  # fmt: skip
                    return f"{who}: {cp.rule_text(c['attendance'])}."
        ch = rec.setdefault("changes", {})
        if kind == "rule":
            r = ch.setdefault("rules", {}).setdefault(a["course"], {})
            r.update({k: a[k] for k in ("min_pct", "labs") if k in a})
            said = []
            if "min_pct" in a:
                said.append(f"at least {a['min_pct']}%")
            if "labs" in a:
                said.append("labs counted separately" if a["labs"] == "separate" else "labs counted in")
            return f"{who}: {', '.join(said)}."
        if kind == "reset":
            course = a["course"]
            if course == "*":
                ch.clear()
                return "Every rule as the pack says."
            ch.get("rules", {}).pop(course, None)
            ch["off"] = [k for k in ch.get("off", []) if not k.startswith(course + "|")]
            ch["moved"] = {k: v for k, v in ch.get("moved", {}).items() if not k.startswith(course + "|")}
            return f"{who}: as the pack says."
        if kind in ("off", "on", "move"):
            label = self._label(pack, a["key"])
            if making:
                course, _, what = a["key"].partition("|")
                if kind == "off":
                    for part in ("quizzes", "exams"):
                        pack[part] = [x for x in pack[part] if cp.qkey(x["course"], x["what"]) != a["key"]]
                    return f"{label}: left out of the pack."
                if kind == "move":
                    for q in pack["quizzes"]:
                        if cp.qkey(q["course"], q["what"]) == a["key"]:
                            q["next"] = cp.moved_next(q["next"], a["day"])
                            q["day"], q["time"] = a["day"], a["time"]
                    return f"{label}: {a['day'].title()} {a['time']}."
                return f"{label} is in the pack."
            off = [k for k in ch.get("off", []) if k != a["key"]]
            if kind == "off":
                off.append(a["key"])
            ch["off"] = off
            if kind == "move":
                ch.setdefault("moved", {})[a["key"]] = {"day": a["day"], "time": a["time"]}
                return f"{label}: {a['day'].title()} {a['time']}."
            return f"{label}: {'left out' if kind == 'off' else 'back in'}."
        return "I couldn't do that."

    @staticmethod
    def _label(pack: dict, key: str) -> str:
        names = {c["id"]: c["name"] for c in pack["courses"]}
        course, _, what = key.partition("|")
        hit = next((x["what"] for x in pack["quizzes"] + pack["exams"] if cp.qkey(x["course"], x["what"]) == key), what)
        return f"{names.get(course, course)} {hit}"

    def _changes(self, rec: dict, pack: dict, text: str, making: bool) -> tuple[list[str], list[str], str]:
        """Every change in a message (one per line, or separated by ";"): (what was done, what couldn't be read, the
        "checked" date if it gave one)."""
        said, bad, checked = [], [], ""
        for line in re.split(r"[\n;]+", text or ""):
            if not line.strip():
                continue
            m = re.fullmatch(r"\s*holidays?\s+(\d{4}-\d{2}-\d{2})\s+(?:off|out|drop)\s*", line, re.I)
            got = ("holiday_off", {"date": m[1]}) if m else cp.read_change(line, pack)
            if got is None:
                bad.append(line.strip())
            elif got[0] == "checked":
                checked = got[1]["date"]
            else:
                said.append(self._change(rec, pack, got[0], got[1], making))
        return said, bad, checked

    def _reply(self, msg: Incoming, ref: str) -> str | None:
        """A reply to a pack's review: changes to it (and, making one, "checked <date>")."""
        d = self._draft(ref)
        if d is None:
            return "That pack review has expired: send the file again (or /classpack export)."
        making = d["kind"] == "export"
        said, bad, checked = self._changes(d, d["pack"], msg.text, making)
        ex = self._example(d["pack"])
        if bad and not said and not checked:
            return f'I couldn\'t read that. Replies like "{ex} 80", "{ex} labs together", "{ex} quiz off", ' + (
                '"title Year 2 section B", "checked 2026-10-18".' if making else '"electives ...", "batch B".'
            )
        self._put(d)
        if making and checked:
            return self._finish(d, checked)[1]
        note = " ".join(said) + (f" (I couldn't read: {'; '.join(bad)})" if bad else "")
        self.app.events.emit("classpack_changed", n=len(said), making=making)
        if note:
            msg.reply(note)
        self._send_review(d)
        return None

    def change(self, text: str) -> str:
        """/classpack set ...: change the imported pack's rules or your choices; says what changes for you."""
        rec = self.active()
        if not rec:
            return "There's no class pack yet; send one here to import it."
        was = self.layer()
        pack = cp.validate(rec["pack"])
        said, bad, _ = self._changes(rec, pack, text, making=False)
        if not said:
            ex = self._example(pack)
            return f"I couldn't read that. e.g. /classpack set {ex} 80, {ex} labs together, {ex} quiz off, batch B."
        self._save(rec)
        self._refresh()
        lines = cp.diff(was, self.layer()) if was else []
        self.app.events.emit("classpack_changed", n=len(said), making=False)
        out = " ".join(said) + (f" (I couldn't read: {'; '.join(bad)})" if bad else "")
        return out + ("\n" + "\n".join(lines[:SHOWN]) if lines else "")

    # -------------------------------------------------------------------------------------------- making
    def _default_rule(self) -> dict:
        labs = self.setting("labs")
        try:
            pct = max(0, min(100, int(self.setting("min_pct"))))
        except (TypeError, ValueError):
            pct = cp.DEFAULT_RULE["min_pct"]
        return {"min_pct": pct, "labs": labs if labs in cp.LABS else "separate"}

    def source_from_setup(self) -> dict:
        """What Kurooto knows of your term (Subjects with your term note and an imported pack, Deadlines' recurring
        quizzes), as a pack's source (coursepack.build). Never your skips, notes or anything else of yours."""
        sub = self._subjects()
        if sub is None:
            return {}
        rec, lay = self.active(), self.layer()
        el, rules, base = set(), {}, None
        if rec and lay:  # a pack you imported: its electives, lab batches, kinds and the section's rules carry over
            pack = cp.validate(rec["pack"])
            el = {sub.resolve(c["id"]) or c["id"] for c in cp.electives(pack)}
            rules = {sub.resolve(c["id"]) or c["id"]: c["attendance"] for c in pack["courses"] if c.get("attendance")}
            base = pack["attendance"]
        seen = {}
        for c in (lay or {"classes": []})["classes"]:
            seen[(sub.resolve(c["slug"]) or c["slug"], c["day"], c["start"])] = (c["kind"], c["batch"])
        classes = []
        for c in sub.timetable():
            kind, batch = seen.get((c["subject"], c["day"], c["start"]), ("", ""))
            classes.append({**c, "slug": c["subject"], "name": sub.name_of(c["subject"]), "kind": kind, "batch": batch})
        quizzes = []
        dl = self.app.modules.get("deadlines")
        if dl is not None and self.app.is_on("deadlines"):
            for r in dl.recurring_rows():
                quizzes.append({**r, "subject": r["slug"]})
        return {
            "subjects": [{**s, "elective": s["slug"] in el} for s in sub.subjects()],
            "classes": classes,
            "holidays": sub.holidays(),
            "exam_periods": sub.exam_periods(),
            "term_ends": sub.term_ends(),
            "dates": sub.key_dates(),
            "quizzes": quizzes,
            "rules": rules,
            "attendance": base,
        }

    def note_path(self, raw: str, anywhere: bool = False) -> Path | None:
        """A term note by its path in your notes (terms/2026-autumn, with or without .md or [[ ]]); anywhere=True
        (a terminal) also takes a file outside them."""
        raw = re.sub(r"^\[\[|\]\]$", "", (raw or "").strip()).split("|")[0].strip()
        if not raw:
            return None
        p = Path(raw).expanduser()
        p = p if p.is_absolute() else self.app.workspace / raw
        if not anywhere and not p.resolve().is_relative_to(self.app.workspace.resolve()):
            return None  # from Telegram: only a note in your notes
        for f in (p, p.with_name(p.name + ".md")):
            if f.is_file():
                return f
        return None

    def draft_pack(self, note: str = "", anywhere: bool = False) -> tuple[dict | None, list[str], str]:
        """(a pack not checked yet, what was left out, or why there's none)."""
        if note:
            p = self.note_path(note, anywhere)
            if p is None:
                return None, [], f"I can't find {note} in your notes (a path like terms/2026-autumn)."
            src = cp.source_from_note(p.read_text(encoding="utf-8", errors="replace"))
        else:
            src = self.source_from_setup()
        pack, left = cp.build(src, now().date(), src.get("attendance") or self._default_rule())
        if not pack["courses"]:
            where = f"{note} has no timetable with classes" if note else "Subjects has no subjects yet"
            return None, left, f"There's nothing to put in a pack: {where} (/subject, /class, or /term note)."
        return pack, left, ""

    def start_export(self, note: str = "") -> str:
        pack, left, why = self.draft_pack(note)
        if pack is None:
            return why
        d = self._new_draft("export", pack=pack, left=left, source=note)
        self._send_review(d)
        return ""

    def _making_text(self, d: dict) -> str:
        pack = d["pack"]
        src = f" from {d['source']}" if d.get("source") else " of your setup"
        out = [f"A class pack{src}" + (f": {pack['title']}" if pack["title"] else "") + f". {cp.overview(pack)}."]
        out.append(
            "Courses: " + ", ".join(c["name"] + (" (elective)" if c["elective"] else "") for c in pack["courses"]) + "."
        )
        hols = pack["term"]["holidays"]
        if hols:
            out.append("Holidays: " + "; ".join(f"{cp.span_text(h['from'], h['to'])} {h['what']}" for h in hols) + ".")
        lay = cp.choose(pack, [c["id"] for c in cp.electives(pack)], "", None)
        out.append(cp.rules_line(pack, lay) + ".")
        left = d.get("left") or []
        if left:
            out.append(f"Left out ({len(left)}): " + "; ".join(left[:6]) + (" ..." if len(left) > 6 else ""))
        out.append("It carries no names, notes, keys or skips: only the section's timetable, dates, quizzes and rules.")
        ex = self._example(pack)
        out.append(
            f'\nTap the electives (courses not everyone takes). Reply to change anything: "title Year 2 section B", '
            f'"{ex} 80" or "all 80" (attendance), "{ex} labs together", "{ex} quiz off", "holiday 2026-10-02 off".'
        )
        out.append(
            'Check it against the official timetable, then tap "Checked today" (or reply "checked 2026-10-18"): '
            "I'll make the file and send it to you to forward."
        )
        return "\n".join(out)

    def _making_buttons(self, d: dict) -> list:
        did = d["id"]
        tick = [
            (("[x] " if c["elective"] else "[ ] ") + c["name"][:28], f"{PREFIX}:{did}:e{i}")
            for i, c in enumerate(d["pack"]["courses"][:16])
        ]
        rows = [tick[i : i + 2] for i in range(0, len(tick), 2)]
        return [*rows, [("Checked today, make it", f"{PREFIX}:{did}:ok"), ("Cancel", f"{PREFIX}:{did}:x")]]

    def _making_button(self, d: dict, action: str) -> str:
        if action == "ok":
            ok, said = self._finish(d, now().date().isoformat())
            if not ok or len(said) > 190:
                self.app.notify(said, kind="result")
            return said if len(said) <= 190 else ("Made." if ok else "Not made: see the message.")
        m = re.fullmatch(r"e(\d+)", action)
        courses = d["pack"]["courses"]
        if not m or int(m[1]) >= len(courses):
            return "That button isn't one I know."
        c = courses[int(m[1])]
        c["elective"] = not c["elective"]
        self._put(d)
        return f"{c['name']}: {'an elective' if c['elective'] else 'everyone takes it'}."

    def _finish(self, d: dict, checked: str) -> tuple[bool, str]:
        """Make the file: stamped with the day it was checked against the official timetable, sent to you."""
        today = now().date()
        if checked in ("today", "yesterday"):
            checked = (today - dt.timedelta(days=checked == "yesterday")).isoformat()
        if checked > today.isoformat():
            return False, "That day hasn't come yet: check it against the official timetable first."
        ok, said, f = self.write(d["pack"], checked)
        if not ok or f is None:
            return False, said
        self._drop(d)
        from kurooto.modules.skills import send_file

        title = f" for {d['pack']['title']}" if d["pack"]["title"] else ""
        sent, how = send_file(
            self.app,
            f,
            caption=f"Class pack{title}, checked against the official timetable on {checked}. Forward it to your "
            "classmates: they send it to their own Kurooto to import it.",
        )
        return True, f"Made {f.name}. " + (how if sent else f"It's in {f.parent}.")

    def write(self, pack: dict, checked: str, out: Path | None = None) -> tuple[bool, str, Path | None]:
        """Stamp and write a pack (to `out`, or Kurooto's data folder). (ok, what happened, the file)."""
        pack = {**pack, "checked": checked, "made": now().date().isoformat()}
        try:
            text = cp.dumps(pack)
        except cp.PackError as e:
            return False, f"The pack didn't pass its own check ({e}); nothing was made.", None
        f = Path(out) if out else self.out_dir / cp.file_name(pack)
        if f.is_dir():
            f = f / cp.file_name(pack)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        self.app.events.emit(
            "classpack_exported",
            courses=len(pack["courses"]),
            classes=len(pack["classes"]),
            quizzes=len(pack["quizzes"]),
        )
        return True, f"Made {f.name}: {cp.overview(cp.validate(pack))}.", f

    # ---------------------------------------------------------------------------------------- buttons
    def callbacks(self):
        return {PREFIX: self._button}

    def replies(self):
        return {"classpack": self._reply}

    def _button(self, ref: str, action: str) -> str:
        d = self._draft(ref)
        if d is None:
            return "That pack review has expired; send the file again (or /classpack export)."
        if action == "x":
            self._drop(d)
            return "Cancelled; nothing changed."
        return self._import_button(d, action) if d["kind"] == "import" else self._making_button(d, action)

    # ------------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command(
                "classpack",
                "your section's setup as a file to share, or a classmate's to import: /classpack export",
                self._command,
                "/classpack · /classpack export [from <note>] · /classpack set la 80 · /classpack remove · undo",
            )
        ]

    def _command(self, msg: Incoming, arg: str) -> str | None:
        a, low = arg.strip(), arg.strip().lower()
        try:
            if not a:
                return self.status()
            if low.split()[0] == "export":
                note = re.sub(r"^from\s+", "", a[6:].strip(), flags=re.I)
                return self.start_export(note) or None
            if low.startswith("set "):
                return self.change(a[4:])
        except cp.PackError as e:  # the stored pack was changed by hand
            return f"The imported class pack can't be read any more ({e}). /classpack remove takes it out."
        if low in ("remove", "off", "delete"):
            return self.remove()
        if low == "undo":
            return self.undo()
        return (
            "Usage: /classpack (what you have), /classpack export [from <note>], /classpack set la 80 (or la labs "
            "together, la quiz off, electives ..., batch B), /classpack remove, /classpack undo. To import a pack, "
            "send its .kurooto-course file here."
        )

    def status(self) -> str:
        rec = self.active()
        if not rec:
            return (
                "No class pack yet. Send a classmate's .kurooto-course file here to import it; /classpack export "
                "makes one of your setup to share."
            )
        pack, lay = cp.validate(rec["pack"]), self.layer() or self._layer_of(rec)
        name = (f": {pack['title']}" if pack["title"] else "") + (
            f" ({pack['term']['name']})" if pack["term"]["name"] else ""
        )
        out = [
            f"Class pack{name}, checked against the official timetable on {pack['checked']}; imported "
            f"{str(rec.get('imported', ''))[:10]}.",
            f"For you: {cp.counts(lay)}.",
        ]
        els = cp.electives(pack)
        if els:
            took = [c["name"] for c in els if c["id"] in (rec.get("electives") or [])]
            out.append(f"Your electives: {', '.join(took) or 'none'} (of {', '.join(c['name'] for c in els)}).")
        if cp.batches(pack):
            out.append(f"Your lab batch: {rec.get('batch') or 'none'} (of {', '.join(cp.batches(pack))}).")
        out.append(cp.rules_line(pack, lay) + ".")
        out += self._yours(rec, pack)
        ex = self._example(pack)
        out.append(
            f"/classpack set {ex} 80 changes a rule (also {ex} labs together, {ex} quiz off, electives ..., "
            "batch ...); /classpack remove takes it out."
        )
        return "\n".join(out)

    def remove(self) -> str:
        rec = self.active()
        if not rec:
            return "There's no class pack to remove."
        self._save({"previous": {k: v for k, v in rec.items() if k != "previous"}})
        self._refresh()
        self.app.events.emit("classpack_removed")
        return (
            "Class pack removed: its classes, dates, quizzes and rules don't count any more; your own setup stays. "
            "/classpack undo brings it back."
        )

    def undo(self) -> str:
        rec = self.record()
        if "previous" not in rec:
            return "Nothing to undo."
        prev = rec.get("previous") or {}
        cur = {k: v for k, v in rec.items() if k != "previous"}
        self._save({**prev, "previous": cur} if prev.get("pack") else {"previous": cur})
        self._refresh()
        self.app.events.emit("classpack_changed", n=1, making=False, undo=True)
        if prev.get("pack"):
            title = prev["pack"].get("title") or "the one before"
            return f"Back to the class pack you had before ({title}, checked {prev['pack'].get('checked')})."
        return "Back to no class pack (/classpack undo again brings it back)."

    # ------------------------------------------------------------------------------------------- health
    def health_check(self):
        """Kurooto keeps itself working: the imported pack still reads, and its term isn't long over."""
        from kurooto.core.health import Check

        def probe(net: bool):
            rec = self.active()
            if rec is None:
                return True, ""
            try:
                pack = cp.validate(rec["pack"])
            except cp.PackError as e:
                return False, f"the imported pack can't be read any more ({e})"
            ends = [pack["term"]["classes_end"], *(p["to"] for p in pack["term"]["exam_periods"])]
            ends += [e["date"] for e in pack["exams"]]
            end = max([x for x in ends if x] or [""])
            if end and (now().date() - dt.date.fromisoformat(end)).days > STALE_DAYS:
                return False, f"your class pack is for a term that ended on {end}"
            return True, f"checked against the official timetable on {pack['checked']}"

        return Check(self.id, self.title, probe=probe, help="Send this term's pack here, or /classpack remove")
