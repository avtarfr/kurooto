"""Notes sorter (0.7.4): notes you drop in a scratch folder (inbox/ by default) are moved by themselves into the
folders of
your notes where they belong. Off until you turn it on (Features -> Notes sorter).

Every night (sorter.at) and on `/sort now`: the notes in the scratch folder that have sat a few minutes are placed by
rules first (a note's own subject:, a tag or a title naming one of your subjects, and what you taught it by moving a
note yourself); a note the rules can't place goes, as one short request, to your AI (sorter.ai), which may only pick a
folder you already have, with a confidence; below sorter.min_conf the note stays and is listed with its best guesses
and Move buttons. At most sorter.per_night notes a day.

It never deletes, merges or overwrites anything: a name already taken gets a number. Links in Kurooto's own text are
fixed; a note that notes of yours link to by its path waits (nothing of yours is rewritten). One message says what
moved, with Undo (/sort undo, kept as long as the move log). It doesn't move a note into a new top-level folder, or
into Kurooto's own folders.

It notices when a note belongs elsewhere: a note you move again after it filed it is learned from (like it goes where
you put it, and it's left alone), and, weekly (sorter.recheck), a note it moved that now clearly fits another folder
moves once more (at most monthly each, Undoable).

/sort            what's waiting and what moved lately
/sort now        a pass now
/sort undo       put the last pass back
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

from kurooto.core import notedupes, notesfit, sorting
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "sorter",
    {
        "folder": "inbox",  # the scratch folder, inside your notes: what lands here is sorted
        "at": "daily 03:30",  # when the nightly pass runs
        "per_night": 20,  # the most notes moved in a day
        "settle_min": 10,  # a note touched in the last this-many minutes is left (you may still be writing it)
        "min_conf": 0.75,  # how sure a guess must be before it's acted on
        "ai": True,  # ask your AI about a note the rules can't place (its first lines go to it); off: rules only
        "recheck": True,  # weekly: a note it moved that now clearly fits another folder moves once more
        "learn": True,  # a note you move again after it filed it teaches it
        "duplicates": True,  # a note in the scratch folder that copies one you already have is asked about, not filed
    },
)


class Sorter(Module):
    id = "sorter"
    title = "Notes sorter"
    description = (
        "Notes you drop in a scratch folder (inbox) are moved by themselves into the right folders of your notes: "
        "never deleted, never overwritten, always with Undo, and it learns from where you move one yourself."
    )
    privacy = (
        "Stays on this computer. For a note its rules can't place, the first lines go to your AI as one short request "
        "(switch it off with sorter.ai)."
    )

    def start(self) -> None:
        self.every("night", self.setting("at") or "daily 03:30", lambda p=None: self.run(), misfire="coalesce")
        self.app.jobs.then_actions["sorter.decided"] = self._decided

    # ------------------------------------------------------------------------------------------------------ a pass
    def run(self, force: bool = False) -> dict:
        """One pass. Returns what it did (also the text of /sort now)."""
        app = self.app
        out = {"moved": [], "waiting": 0, "asked": 0, "learned": 0, "log": ""}
        if not app.is_on(self.id):
            return out
        if self.setting("learn") is not False:
            out["learned"] = len(sorting.learn(app))
        root = Path(app.workspace)
        room = sorting.left_today(app)
        min_conf = float(self.setting("min_conf") or sorting.MIN_CONF)
        moves, taken = [], set()
        st = sorting.load(app)
        for rel in sorting.ready(app):
            text = notesfit._read(root / rel) or ""
            if self.setting("duplicates") is not False and self._dupe(rel, text, st):
                continue
            d = sorting.decide(app, rel, text)
            if d.folder and d.conf >= min_conf:
                if len(moves) < room:
                    to = sorting.free_name(root, d.folder, Path(rel).name, taken)
                    taken.add(to.lower())
                    moves.append({"from": rel, "to": to, "kind": "sorted"})
                continue
            if self.setting("ai") is not False and self._can_ask(st, rel, text, force):
                self._ask(rel, text, st)
                out["asked"] += 1
            else:
                self._wait(st, rel, d)
        if self.setting("recheck") is not False and (force or now().weekday() == 6):  # Sundays, and /sort now
            for m in sorting.recheck(app):
                if len(moves) < room and m["to"].lower() not in taken:
                    taken.add(m["to"].lower())
                    moves.append(m)
        sorting.save(app, st)
        out["waiting"] = len(sorting.load(app)["waiting"])
        if moves:
            res = self._move(moves)
            out["moved"], out["log"] = res["moved"], res["id"]
        self._tell(out)
        return out

    def _dupe(self, rel: str, text: str, st: dict) -> bool:
        """A note that copies one you have is asked about once (Keep both / Merge / Leave it), not filed. True: waits"""
        d = st.setdefault("dupes", {})
        sha = sorting.sha(text)
        rec = d.get(rel)
        if rec and rec.get("sha") == sha:
            return rec["state"] != "keep"  # keep both: it's sorted like any other note
        hits = notedupes.incoming(self.app, rel, text)
        if not hits:
            return False
        of, kind, score = hits[0]
        rid = "d" + sha[:8]
        d[rel] = {"id": rid, "of": of, "kind": kind, "score": score, "sha": sha, "state": "asked", "at": time.time()}
        how = "the same words" if kind == "exact" else f"{round(score * 100)}% the same words"
        self.app.notify(
            f"{rel} looks like a copy of {of} ({how}). Keep both and file it as usual, merge it into {of}, "
            "or leave it where it is?",
            kind="question",
            why="sorter.duplicate",
            buttons=[
                [("Keep both", f"srt:{rid}:keep"), ("Merge", f"srt:{rid}:merge"), ("Leave it", f"srt:{rid}:skip")]
            ],
        )
        return True

    def _dupe_button(self, st: dict, rel: str, act: str) -> str:
        rec = st["dupes"][rel]
        if act == "keep":
            rec["state"] = "keep"
            sorting.save(self.app, st)
            return "Kept both: it's filed like any other note at the next pass (/sort now)."
        if act == "skip":
            rec["state"] = "skip"
            sorting.save(self.app, st)
            return "Left where it is; I won't ask again."
        if act == "merge":
            ok, got = notedupes.merge_pair(self.app, rec["of"], rel, rec["kind"])
            if not ok:
                return f"Not merged: {got}."
            rec.update(state="merged", before=got)
            sorting.save(self.app, st)
            msg = f"Merged: {rel} now points at {rec['of']} and keeps its own text."
            self.app.notify(msg, kind="result", why="asked", buttons=[[("Undo", f"srt:{rec['id']}:undo")]])
            return msg
        if act == "undo" and rec.get("state") == "merged":
            changed = notedupes.restore(self.app, rec.get("before") or {})
            rec.update(state="skip")
            rec.pop("before", None)
            sorting.save(self.app, st)
            return "Put back." if not changed else f"Put back, except {', '.join(changed)} (you changed it since)."
        return "There's no such button."

    def _move(self, moves: list[dict], by: str = "sorter") -> dict:
        """Plan and do these moves. A note that notes of yours link to by its path is left (and said)."""
        p, left = sorting.plan(self.app, moves)
        st = sorting.load(self.app)
        for m in left:
            st["waiting"][m["from"]] = {
                "why": m["why"],
                "guesses": [str(Path(m["to"]).parent.as_posix())],
                "at": time.time(),
            }
        sorting.save(self.app, st)
        if p.clashes or not p.moves:
            return {"moved": [], "id": ""}
        res = sorting.apply(self.app, p, by)
        return {"moved": [(m["from"], m["to"]) for m in p.moves], "id": res.get("id", "")}

    def _wait(self, st: dict, rel: str, d: sorting.Decision) -> None:
        w = st["waiting"].setdefault(rel, {"at": time.time()})
        w.update({"why": d.why, "guesses": d.guesses or w.get("guesses", [])[:2]})

    def _can_ask(self, st: dict, rel: str, text: str, force: bool) -> bool:
        w = st["waiting"].get(rel) or {}
        return bool(text.strip()) and (force or time.time() - float(w.get("asked", 0)) > 86400)

    def _ask(self, rel: str, text: str, st: dict) -> None:
        """One short request for a note the rules couldn't place: the answer comes to _decided."""
        w = st["waiting"].setdefault(rel, {"at": time.time(), "why": "waiting for your AI"})
        w["asked"] = time.time()
        self.app.jobs.submit(
            sorting.prompt(self.app, rel, text),
            title=f"Sort a note: {Path(rel).stem[:40]}",
            effort="low",
            background=True,
            text_only=True,
            quiet=True,
            lane="bg",
            then="sorter.decided",
            then_payload={"rel": rel, "sha": sorting.sha(text)},
        )

    def _decided(self, job, result, payload: dict) -> None:
        """The AI's answer for one note: moved if it names a folder you have and is sure enough, else it waits with its
        best guess."""
        app = self.app
        rel = payload["rel"]
        root = Path(app.workspace)
        text = notesfit._read(root / rel)
        if text is None or sorting.sha(text) != payload.get("sha"):
            return  # moved, deleted or edited meanwhile: the next pass looks again
        d = sorting.answer(app, result.text) if result.ok else sorting.Decision(None, 0.0, "no answer", "ai")
        min_conf = float(self.setting("min_conf") or sorting.MIN_CONF)
        if d.folder and d.conf >= min_conf and sorting.left_today(app) > 0:
            to = sorting.free_name(root, d.folder, Path(rel).name, set())
            res = self._move([{"from": rel, "to": to, "kind": "sorted"}], by="ai")
            if res["moved"]:
                self._tell({"moved": res["moved"], "log": res["id"], "waiting": 0, "learned": 0, "asked": 0})
                return
        st = sorting.load(app)
        self._wait(st, rel, sorting.Decision(None, d.conf, d.why, "ai", [d.folder] if d.folder else []))
        sorting.save(app, st)

    # ------------------------------------------------------------------------------------------------------ telling
    def _tell(self, out: dict) -> None:
        app = self.app
        if out["moved"]:
            names = ", ".join(f"{Path(a).name} -> {str(Path(b).parent.as_posix())}" for a, b in out["moved"][:6])
            more = f" and {len(out['moved']) - 6} more" if len(out["moved"]) > 6 else ""
            buttons = [[("Undo", f"srt:{out['log']}:undo")]] if out["log"] else None
            app.notify(
                f"Sorted {len(out['moved'])} note{'s' if len(out['moved']) != 1 else ''}: {names}{more}.",
                kind="result",
                why="sorter.summary",
                buttons=buttons,
                title="Notes sorter",
            )

    def waiting_text(self) -> tuple[str, list]:
        """The notes that stayed, each with its best guesses as Move buttons (/sort)."""
        st = sorting.load(self.app)
        lines, rows = [], []
        have = set(sorting.folders(self.app))
        for i, (rel, w) in enumerate(sorted(st["waiting"].items())[:8]):
            if not (Path(self.app.workspace) / rel).exists():
                continue
            g = [x for x in w.get("guesses") or [] if x in have][:2]
            lines.append(f"- {rel}: {w.get('why', 'no folder fits')}")
            w["id"] = f"w{i}"
            if g:
                rows.append([(f"{Path(rel).stem[:14]} -> {x}"[:44], f"srt:{w['id']}:{k}") for k, x in enumerate(g)])
        sorting.save(self.app, st)
        return "\n".join(lines), rows

    # ------------------------------------------------------------------------------------------------------ you
    def callbacks(self):
        return {"srt": self._button}

    def _button(self, ref: str, act: str) -> str:
        st0 = sorting.load(self.app)
        mine = next((r for r, v in st0.get("dupes", {}).items() if v.get("id") == ref), "")
        if mine:
            return self._dupe_button(st0, mine, act)
        if act == "undo":
            return sorting.undo(self.app, ref)["message"]
        st = sorting.load(self.app)
        rel = next((r for r, w in st["waiting"].items() if w.get("id") == ref), "")
        w = st["waiting"].get(rel) or {}
        try:
            folder = (w.get("guesses") or [])[int(act)]
        except (ValueError, IndexError):
            return "That choice has expired: /sort lists what's waiting."
        if folder not in set(sorting.folders(self.app)) or not rel:
            return "That folder isn't there any more."
        root = Path(self.app.workspace)
        to = sorting.free_name(root, folder, Path(rel).name, set())
        res = self._move([{"from": rel, "to": to, "kind": "sorted"}], by="you")
        return f"Moved to {folder}." if res["moved"] else "I couldn't move that one; it stays."

    def commands(self) -> list[Command]:
        return [
            Command(
                "sort",
                "the notes sorter: what's waiting; /sort now runs it; /sort undo puts the last pass back",
                self.cmd,
                usage="/sort [now|undo]",
            )
        ]

    def cmd(self, msg: Incoming, arg: str) -> str | None:
        a = (arg or "").strip().lower()
        if a == "undo":
            return sorting.undo(self.app)["message"]
        if a == "now":
            out = self.run(force=True)
            return (
                f"Sorted {len(out['moved'])}, asked your AI about {out['asked']}, {out['waiting']} waiting "
                f"({out['learned']} learned from your own moves)."
            )
        st = sorting.load(self.app)
        day = now().date().isoformat()
        lines = [
            f"Scratch folder: {sorting.scratch_rel(self.app)}. Today {int(st['day'].get(day, 0))} of "
            f"{int(self.setting('per_night') or 20)} moved; {len(sorting.ready(self.app))} due."
        ]
        text, rows = self.waiting_text()
        if text:
            lines.append("Waiting for you:\n" + text)
        last = st["passes"][-1] if st["passes"] else None
        if last:
            when = dt.datetime.fromtimestamp(float(last["at"])).strftime("%d %b %H:%M")
            lines.append(f"Last pass: {last['moved']} moved, {when}. /sort undo puts it back.")
        msg.reply("\n".join(lines), rows or None)
        return None

    def health(self) -> tuple[bool, str]:
        d = sorting.scratch_dir(self.app)
        if not d.exists():
            return False, f"the scratch folder {sorting.scratch_rel(self.app)} isn't in your notes yet"
        return True, ""
