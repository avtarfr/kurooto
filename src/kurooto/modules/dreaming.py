"""Dreaming: Kurooto's work while you sleep, told once in the morning. Reading books into your notes (the concept
graph and its daily garden), the notes brain's upkeep, the look back after calls, skills and facts it learned,
handwritten notes it linked, things it set up from what you said: one message at dreaming.when ("While you slept"),
with the loose ends worth a look (your own open doubts, notes nothing links to yet, links that point nowhere, tasks
past due, AI requests that failed). Nothing new runs: it gathers what the night did from the event log and the
features' own state, so it costs nothing. While it's on, the concept graph's own morning line is folded into it. The
day after an exam or a heavy day it starts with one line saying the day will be lighter, with Not today; dreaming.when
follows when you're usually up once that's learned (core/rhythm.py).

The self-check (dreaming.self_check, on; the first part of Dream RSI): each morning it replays your test cases (Wrong
button and test cases, modules/cases.py) and says which ones that went right yesterday go wrong now, after an update
or a settings change, so a step back is caught the next day instead of when you next need it. It also counts the
requests it didn't understand and the Wrong taps since the last message (they wait for the Sunday look back).

Tuning its own messages (dreaming.tune_messages, on; Dream RSI part two, core/policy.py): before the message, it replays
the messages it sent you by itself under a few variants of when they come, applies the best if it clearly beats things
as they are (one change a night, with Undo) and says so in one line. /dream policy shows the rules and the decisions.

Curious and remembering (dreaming.curious, dreaming.resurface; modules/curious.py): one line about a topic you asked
about 3+ times this week with no note on it (Make a stub / Not interested), and one from a shared past, a note or quiz
subject from 10-30 days ago or an anniversary (Open it / Less of this). Each at most once a day, among the loose ends.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from kurooto.core import policy
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules import curious
from kurooto.modules.base import Command, Module

register_defaults(
    "dreaming",
    {
        "when": "daily 07:30",  # when the morning message comes (it covers everything since the last one)
        "loose_ends": True,  # also the loose ends: your open doubts, unlinked notes, broken links, tasks past due
        "self_check": True,  # replay your test cases each morning and say which ones went wrong since yesterday
    },
)
DOUBT = re.compile(r"(?ms)^## Doubts\n(.*?)(?=^#|\Z)")


class Dreaming(Module):
    id = "dreaming"
    title = "Dreaming"
    description = (
        "Everything Kurooto did while you slept (books read into your notes, links tidied, what it learned, notes it "
        "linked) in one morning message, with the loose ends worth a look."
    )
    privacy = "Stays on this computer: it only reads Kurooto's own log and your notes."

    @property
    def state_file(self) -> Path:
        return self.app.paths.state / "dreaming.json"

    def start(self):
        self.every("morning", self.setting("when") or "daily 07:30", self.morning)

    def commands(self):
        return [
            Command(
                "dream",
                "what Kurooto did since the last morning message, and the loose ends, now; /dream policy: when its "
                "own messages reach you, and what it tuned",
                self._cmd,
            )
        ]

    def _cmd(self, msg, arg: str) -> str | None:
        if arg.strip().lower() == "policy":
            return policy.show(self.app)
        text = self.report(send=False) or "Nothing happened overnight that's worth a line, and no loose ends."
        if self.buttons and msg.respond:  # the curious and resurfacing lines' buttons
            msg.reply(text, buttons=self.buttons)
            return None
        return text

    def callbacks(self):
        return {"drm": lambda ref, act: curious.button(self.app, ref, act)}

    # ------------------------------------------------------------------------------------- the morning
    def morning(self, payload: dict | None = None) -> str:
        return self.report(send=True)

    def since(self) -> dt.datetime:
        last = (jload(self.state_file, {}) or {}).get("at")
        floor = now() - dt.timedelta(hours=30)
        return max(floor, dt.datetime.fromisoformat(last)) if last else now() - dt.timedelta(hours=20)

    def events(self, since: dt.datetime) -> list[dict]:
        out = []
        for e in self.app.events.tail(20000):
            try:
                if dt.datetime.fromisoformat(e["ts"]) > since:  # after the last message (to the second)
                    out.append(e)
            except (KeyError, ValueError):
                continue
        return out

    def night(self, ev: list[dict]) -> list[str]:
        """What the night did, one line per kind of work (nothing for work that didn't happen)."""
        k = lambda name: [e for e in ev if e.get("kind") == name]  # noqa: E731
        out = []
        books, batches = k("book_read"), k("integrate_batch")
        if batches:
            new = sum(int(e.get("new") or 0) for e in batches)
            links = sum(int(e.get("links") or 0) for e in batches)
            out.append(
                f"Read {len(batches)} stretches of your books into your notes: {new} new concept notes, {links} links."
            )
        if books:
            pages = sum(int(e.get("pages") or 0) for e in books)
            out.append(f"Took in {len(books)} new book{'s' if len(books) != 1 else ''} ({pages} pages).")
        pruned = sum(int(e.get("links") or 0) for e in k("integrate_pruned"))
        if pruned:
            out.append(f"Tidied {pruned} links that pointed at notes that are gone.")
        hw = k("handwritten_linked")
        if hw:
            out.append(f"Linked {len(hw)} handwritten note{'s' if len(hw) != 1 else ''} to their lecture and concepts.")
        up = [e for e in k("gbrain_upkeep") if e.get("ok")]
        if up:
            out.append("Your notes brain ran its upkeep (links, facts, timelines).")
        lessons = sum(int(e.get("lessons") or 0) for e in k("call_reviewed"))
        if lessons:
            out.append(
                f"Learned {lessons} lesson{'s' if lessons != 1 else ''} for calls from looking back at them (/lessons)."
            )
        learned = len(k("learning_skill_learned")) + len(k("learning_skill_improved"))
        if learned:
            out.append(
                f"Learned or improved {learned} skill{'s' if learned != 1 else ''} from your requests (/learned)."
            )
        facts = sum(int(e.get("n") or 0) for e in k("learning_remembered"))
        if facts:
            out.append(f"Kept {facts} thing{'s' if facts != 1 else ''} you said in your how-to-help-me note.")
        inferred = k("inferred")
        if inferred:
            out.append(
                f"Set up {len(inferred)} thing{'s' if len(inferred) != 1 else ''} from what you said (/inferred)."
            )
        return out

    def loose_ends(self, ev: list[dict]) -> list[str]:
        if not self.setting("loose_ends"):
            return []
        out = []
        doubts = self.open_doubts()
        if doubts:
            more = f" (and {len(doubts) - 2} more)" if len(doubts) > 2 else ""
            out.append("Your open doubts: " + "; ".join(d[:90] for d in doubts[:2]) + more + ".")
        ig = self.app.modules.get("integrate")
        if ig is not None and self.app.is_on("integrate"):
            try:
                m = ig.metrics()
            except Exception:  # a graph mid-write: next morning
                m = {}
            if m.get("broken"):
                out.append(f"{m['broken']} links point at notes that don't exist (/graph).")
            if m.get("no_links_in"):
                out.append(f"{m['no_links_in']} notes nothing links to yet; the daily garden takes some each day.")
        dl = self.app.modules.get("deadlines")
        if dl is not None and self.app.is_on("deadlines"):
            late = [it for _i, it, h in dl.upcoming(0) if h < 0 and it["kind"] != "exam"]
            if late:
                out.append(
                    f"{len(late)} task{'s' if len(late) != 1 else ''} past due: {dl.full_title(late[0])}"
                    + (" and more." if len(late) > 1 else ".")
                )
        failed = [e for e in ev if e.get("kind") == "job_failed"]
        if failed:
            out.append(f"{len(failed)} AI request{'s' if len(failed) != 1 else ''} failed overnight (/jobs).")
        return out

    # ---------------------------------------------------------------------------------- the self-check
    def self_check(self, ev: list[dict]) -> tuple[list[str], list[str] | None]:
        """(lines, the test cases passing now): the ones that went right last time and go wrong now, and what was
        missed or marked wrong since the last message. Only the morning message stores the pass list (not /dream)."""
        if not self.setting("self_check"):
            return [], None
        out = []
        kept = [e for e in ev if e.get("kind") == "case_kept"]
        wrong = sum(1 for e in kept if e.get("wrong"))
        missed = len(kept) - wrong
        if wrong or missed:
            bits = [f"{missed} request{'s' if missed != 1 else ''} I didn't understand"] if missed else []
            bits += [f"{wrong} marked Wrong"] if wrong else []
            out.append(" and ".join(bits) + "; the Sunday look back shows them (/cases).")
        cases = self.app.modules.get("cases")
        if cases is None or not self.app.is_on("cases"):
            return out, None
        try:
            res = cases.suite()
        except Exception as e:  # a broken case must not cost the morning message
            self.app.events.emit("dreaming_check_failed", error=f"{type(e).__name__}: {e}"[:200])
            return out, None
        was = set((jload(self.state_file, {}) or {}).get("passing") or [])
        broke = [r for r in res["fail"] if r["id"] in was]
        if broke:
            r = broke[0]
            more = f" (and {len(broke) - 1} more)" if len(broke) > 1 else ""
            out.append(
                f"Went wrong since yesterday ({len(broke)} test case{'s' if len(broke) != 1 else ''}): "
                f'"{r["text"][:60]}" should be {r["expect"]}, got {r.get("got")}{more} (/cases).'
            )
            self.app.events.emit("dreaming_regressed", n=len(broke))
        return out, sorted(r["id"] for r in res["pass"])

    def open_doubts(self) -> list[str]:
        """Doubts you wrote in the last two weeks (handwritten notes' Doubts sections, "DOUBT:" lines in notes)."""
        root = Path(self.app.workspace)
        cutoff = now().timestamp() - 14 * 86400
        out = []
        for f in root.rglob("*.md"):
            try:
                if ".git" in f.parts or f.stat().st_mtime < cutoff:
                    continue
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for block in DOUBT.findall(text):
                out += [ln.lstrip("-* ").strip() for ln in block.splitlines() if ln.strip().startswith(("-", "*"))]
        return [d for d in dict.fromkeys(out) if d][:20]

    # --------------------------------------------------------------------------- curious and remembering
    buttons: list = []  # the last report's buttons (the curious and resurfacing lines')

    def curious_lines(self, send: bool) -> list[str]:
        """A gap in your notes you keep asking about, and a line from the past (modules/curious.py): at most one
        of each, with their buttons in self.buttons. Only the sent morning message marks them shown."""
        lines, self.buttons = [], []
        for on, line in (("curious", curious.curious_line), ("resurface", curious.resurface_line)):
            if not self.setting(on):
                continue
            try:
                text, buttons = line(self.app, send)
            except Exception as e:  # a note that can't be read must not cost the morning message
                self.app.events.emit("dreaming_check_failed", error=f"{on}: {type(e).__name__}: {e}"[:200])
                continue
            if text:
                lines.append(text)
                self.buttons += buttons
        return lines

    def report(self, send: bool = True) -> str:
        start = self.since()
        ev = self.events(start)
        did, ends = self.night(ev), self.loose_ends(ev)
        rh = getattr(self.app, "rhythm", None)
        light = rh.lighter_line(mark=send) if rh is not None else ""  # a lighter day (core/rhythm.py)
        checked, passing = self.self_check(ev)
        learned, undo = policy.morning(self.app, send)  # Dream RSI part two: one line, with its Undo
        did += learned
        ends += checked
        ends += self.curious_lines(send)
        if send:
            st = {"at": now().isoformat()}
            prev = (jload(self.state_file, {}) or {}).get("passing")
            st["passing"] = passing if passing is not None else prev
            jsave(self.state_file, st)
        if not did and not ends and not light:
            return ""
        parts = [light] if light else []
        if did:
            parts.append("While you slept:\n" + "\n".join(f"- {x}" for x in did))
        if ends:
            parts.append("Loose ends:\n" + "\n".join(f"- {x}" for x in ends))
        text = "\n\n".join(parts)
        if send:
            buttons = [[("Not today", "rhy:lighter:no")]] if light else []
            buttons += list(undo or []) + list(self.buttons or [])  # Dream RSI's Undo, the curious lines' buttons
            self.app.notify(text, kind="result", title="Dreaming", why="dreaming.morning", buttons=buttons or None)
        self.app.events.emit("dreaming_told", did=len(did), loose=len(ends), sent=send)
        return text
