"""Brain (0.8.0): Kurooto's mind, as a feature. Off until you turn it on; turned off, Kurooto is exactly as in 0.7.

This module starts the scorekeeper (kurooto/mind/scorekeeper.py) as a process of its own, starts it again if it dies
(waiting 1 s, then longer, up to a minute), and ends it with Kurooto. It mirrors a few kinds of events into the mind
log (ids and numbers only: mind/log.py MIRRORED), and answers /mind. Everything it keeps is in `<state>/mind/`, on
this computer only. Turning it off offers to delete that (Delete Brain's data / Keep it); nothing is deleted
otherwise.

The optional hardened mode (tools/mind_harden.sh, Linux and macOS): the scorekeeper runs as a system user of its own,
started by systemd or launchd, so not even a program running as you can change the log. Kurooto then only reads it.

The parts that grow from the spine (stages 02-17) each have their own switch, `mind.<part>.on`, and come with Brain.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.events import subscribe
from kurooto.mind import act, feelings, gate, journal, measure, mood, promises, signals, story, tone
from kurooto.mind import log as mlog
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "mind",
    {
        "hardened": False,  # the scorekeeper runs as its own user (tools/mind_harden.sh; its marker file does the same)
        "anchor_every": 1000,  # the log's head is written down every this many records (and once a day)
    },
)

BACKOFF_MAX_S = 60  # a scorekeeper that keeps dying is started again at most this often
STEADY_S = 300  # one that ran this long starts the wait from 1 s again
END_S = 5  # it's asked to stop, and killed if it hasn't after this long
CONFIRM_S = 7 * 86400  # Delete Brain's data works this long after it was offered


class Mind(Module):
    id = mind.MODULE
    title = "Brain"
    description = (
        "Kurooto's mind: a tamper-evident log of what it saw and decided, kept by a separate process the AI can't "
        "change. The parts that grow from it (forecasts, drives, a journal) each have their own switch."
    )
    privacy = "Stays on this computer: ids, kinds and numbers, never the words of your messages."
    processes = ("kurooto.mind.scorekeeper",)
    extra = True  # in no preset ("Everything" too): on only when you pick it yourself

    def __init__(self, app):
        super().__init__(app)
        self._unsub = None
        self._proc: subprocess.Popen | None = None
        self.restarts = 0
        self.started_at = 0.0

    @property
    def dir(self) -> Path:
        return self.app.paths.state / "mind"

    # ------------------------------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._unsub is None:
            self._unsub = subscribe(self._mirror)
        self.every("gate", "every 1m", lambda p: gate.release(self.app) if gate.on(self.app) else 0)  # held messages
        # stage 04 (shadow mode: computed, logged and shown, nothing depends on it yet); each part has its own switch
        self.every("signals", "hourly", self._signals)  # the day's numbers, then today's read
        self.every("tone", "hourly", lambda p: tone.batch(self.app) if mind.on(self.app) else 0)
        self.every("tone_roll", "daily 04:05", lambda p: tone.roll(self.app) if mind.on(self.app) else False)
        self.every("score", "daily 20:55", lambda p: mood.run_score(self.app) if mind.on(self.app) else False)
        self.every("forecast", "daily 21:00", lambda p: mood.run_forecast(self.app) if mind.on(self.app) else None)
        self.every("ask", "daily 19:30", lambda p: mood.ask(self.app) if mind.on(self.app) else False)
        # stage 05: the body budget, its promises and its feelings (each its own switch)
        self.every("budget", "every 5m", lambda p: measure.run(self.app) if mind.on(self.app) else False)
        self.every("promises", "every 5m", lambda p: promises.review(self.app) if mind.on(self.app) else {})
        self.every("feelings", "hourly", lambda p: feelings.tick(self.app) if mind.on(self.app) else None)
        self.every("feeling_say", "daily 17:30", lambda p: feelings.say(self.app) if mind.on(self.app) else False)
        self.every("act_digest", "weekly sun 19:10", lambda p: act.digest(self.app) if mind.on(self.app) else False)
        # stage 07: the day's journal, then the checker's own nightly self-check against corrupted copies of it
        self.every("journal", "daily 23:40", self._journal)
        # stage 08: the week's chapter on Sunday night, the summary rebuilt every night, old lines about you let go
        self.every(
            "story_week", "weekly sun 23:55", lambda p: story.write_week(self.app) if mind.on(self.app) else None
        )
        self.every("story_night", "daily 23:50", self._story_night)

    def _signals(self, payload: dict | None = None) -> int:
        """Hourly: the day's numbers go to the scorekeeper, then today's read is made from them."""
        if not mind.on(self.app):
            return 0
        n = signals.run(self.app, payload)
        mood.run_read(self.app, payload)
        return n

    def stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        c = mind._clients.get(id(self.app))
        if c is not None:
            c.flush(2.0)
        super().stop()
        self._end()

    def turned_off(self) -> None:
        """Brain was just turned off: say what it kept, and offer to delete it."""
        if not self.dir.exists():
            return
        n = mlog.MindLog(self.dir / "log.db").count()
        asked = int(time.time())
        self.app.notify(
            f"Brain is off. What it kept stays on this computer ({n:,} records in its log, and its scores) until you "
            "delete it. Turning it on again carries on from there.",
            kind="result",
            why="mind.off",
            buttons=[[("Delete Brain's data", f"mnd:{asked}:delete"), ("Keep it", "mnd:0:keep")]],
        )

    def _mirror(self, rec: dict) -> None:
        """An event, as it happens (core/events.py): the mirrored kinds go to the scorekeeper. Never blocks."""
        kind = str(rec.get("kind") or "")
        if mlog.mirrored(kind) and mind.on(self.app):
            mind.connect(self.app).report(kind, rec)

    # ------------------------------------------------------------------------------------------ the process
    def hardened(self) -> bool:
        """The scorekeeper runs as its own user (tools/mind_harden.sh leaves the marker; mind.hardened forces it)."""
        return bool(self.setting("hardened")) or (self.dir / "hardened").exists()

    def _cmd(self) -> list[str]:
        return [
            sys.executable,
            "-m",
            "kurooto.mind.scorekeeper",
            "--dir",
            str(self.dir),
            "--parent",
            str(os.getpid()),
            "--anchor-every",
            str(int(self.setting("anchor_every") or 1000)),
        ]

    def _spawn(self) -> subprocess.Popen:
        self.dir.mkdir(parents=True, exist_ok=True)
        mlog.private(self.dir, 0o700)
        self.app.paths.logs.mkdir(parents=True, exist_ok=True)
        err = open(self.app.paths.logs / "mind-scorekeeper.log", "a", encoding="utf-8")  # noqa: SIM115 (the child's)
        kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": err}
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            return subprocess.Popen(self._cmd(), **kw)  # noqa: S603 (our own module, our own interpreter)
        finally:
            err.close()

    def _end(self) -> None:
        p, self._proc = self._proc, None
        if p is None or p.poll() is not None:
            return
        try:
            p.terminate()
            p.wait(END_S)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(END_S)
        except OSError:
            pass

    async def background(self, stop: asyncio.Event) -> None:
        """Keep the scorekeeper running while Brain is on (hardened: systemd or launchd does, and this only waits)."""
        wait = 1.0
        try:
            while not stop.is_set():
                if not mind.on(self.app):  # turned off meanwhile: Kurooto stops this task too
                    break
                if self.hardened():
                    await self._sleep(stop, 60)
                    continue
                self._proc = await asyncio.to_thread(self._spawn)
                self.started_at = time.monotonic()
                self.app.events.emit("mind_keeper_started", pid=self._proc.pid)
                while self._proc is not None and self._proc.poll() is None and not stop.is_set():
                    await self._sleep(stop, 1)
                if stop.is_set() or self._proc is None:
                    break
                code = self._proc.returncode
                self.restarts += 1
                self.app.events.emit("mind_keeper_exited", code=code)
                if time.monotonic() - self.started_at >= STEADY_S:
                    wait = 1.0
                await self._sleep(stop, wait)
                wait = min(BACKOFF_MAX_S, wait * 2)
        finally:
            await asyncio.to_thread(self._end)

    @staticmethod
    async def _sleep(stop: asyncio.Event, secs: float) -> None:
        try:
            await asyncio.wait_for(stop.wait(), timeout=secs)
        except TimeoutError:
            pass

    # ------------------------------------------------------------------------------------------ what you see
    def health(self) -> tuple[bool, str]:
        c = mind.connect(self.app)
        up, _ = c.running()
        if not up:
            return False, "its scorekeeper isn't running (it's started again by itself; /mind says more)"
        return True, ""

    def dreaming_lines(self) -> list[str]:
        """The morning message's line: where the log is, so a rewritten log can be caught against what you saw."""
        c = mind.connect(self.app)
        st = c.state()
        if not st["head"]:
            return []
        return [f"Brain's log: {st['records']:,} records, head #{st['head']} {st['hash'][:12]}."]

    def commands(self) -> list[Command]:
        return [
            Command(
                "story",
                "Kurooto's one life story: its fixed core and what it has lived lately; /story strike <week> <line>",
                self.story_cmd,
                usage="/story [strike <YYYY-Www> <line>]",
            ),
            Command(
                "mindjournal",
                "Kurooto's own journal of its states, reasons and mistakes, every line checked against its log",
                self.journal_cmd,
                usage="/mindjournal [yesterday | <date> | strike <line> [date]]",
            ),
            Command(
                "autonomy",
                "what Kurooto may do without asking, by kind of action; /autonomy classify <action> R1",
                self.autonomy_cmd,
                usage="/autonomy [classify <action> <R0-R3>]",
            ),
            Command("budget", "Brain's body budget: its variables, drive, reward and current feeling", self.budget_cmd),
            Command("promises", "what Kurooto said it would do, and whether it did", self.promises_cmd),
            Command(
                "mood",
                "how Brain reads you and what it expects of tomorrow (it only watches for now)",
                self.mood_cmd,
                usage="/mood",
            ),
            Command(
                "mind",
                "Brain: its scorekeeper, its log and whether the log checks out; /mind verify checks all of it; "
                "/mind gate shows what it held back or removed from messages today",
                self.cmd,
                usage="/mind [verify|gate]",
            ),
        ]

    def _journal(self, payload: dict | None = None) -> dict | None:
        if not mind.on(self.app):
            return None
        out = journal.write_day(self.app)
        journal.selfcheck(self.app)
        return out

    def _story_night(self, payload: dict | None = None) -> str | None:
        if not mind.on(self.app):
            return None
        story.expire(self.app)
        return story.rebuild(self.app)

    def story_cmd(self, msg: Incoming, arg: str) -> str:
        words = (arg or "").split()
        if len(words) == 3 and words[0].lower() == "strike" and words[2].isdigit():
            return story.strike(self.app, words[1], int(words[2]))
        return story.status(self.app)

    def journal_cmd(self, msg: Incoming, arg: str) -> str:
        import datetime as dt

        from kurooto.core.clock import now

        if not mind.part_on(self.app, "journal"):
            return "The journal is off (mind.journal.on, with Brain)."
        words = (arg or "").split()
        today = now().date()
        if words and words[0].lower() == "strike" and len(words) >= 2 and words[1].isdigit():
            day = dt.date.fromisoformat(words[2]) if len(words) > 2 else today
            return journal.strike(self.app, day, int(words[1]))
        day = today
        if words and words[0].lower() == "yesterday":
            day = today - dt.timedelta(days=1)
        elif words:
            try:
                day = dt.date.fromisoformat(words[0])
            except ValueError:
                return "Say a date like 2026-10-25, yesterday, or strike <line> [date]."
        e = journal.read_day(self.app, day)
        if e is None:
            e = journal.write_day(self.app, day) and journal.read_day(self.app, day)
        if e is None:
            return f"No journal for {day.isoformat()} yet."
        return (
            journal.render(e)
            + f"(checked: {e['facts']} facts, {e['rejected']} lines the model wrote were replaced by the fixed words.)"
        )

    def autonomy_cmd(self, msg: Incoming, arg: str) -> str | None:
        words = (arg or "").split()
        if len(words) == 3 and words[0].lower() == "classify":
            return act.classify_cmd(self.app, words[1], words[2])
        text, buttons = act.status(self.app)
        msg.reply(text, buttons or None)
        return None

    def budget_cmd(self, msg: Incoming, arg: str) -> str:
        from kurooto.mind import report

        return report.budget_text(self.app)

    def promises_cmd(self, msg: Incoming, arg: str) -> str:
        return promises.listing(self.app) if mind.on(self.app) else "Brain is off (Features → Brain)."

    def mood_cmd(self, msg: Incoming, arg: str) -> str | None:
        text, buttons = mood.view(self.app)
        msg.reply(text, buttons or None)
        return None

    def cmd(self, msg: Incoming, arg: str) -> str:
        c = mind.connect(self.app)
        if (arg or "").strip().lower() == "learning":
            from kurooto.mind import report

            return report.learning_text(self.app)
        if (arg or "").strip().lower() == "gate":
            text, buttons = gate.status(self.app)
            msg.reply(text, buttons or None)
            return None
        if (arg or "").strip().lower() == "verify":
            r = c.verify()
            if r.ok:
                return f"Brain's log checks out: {r.records:,} records, every one in its place (#{r.head})."
            return f"Brain's log doesn't check out at #{r.first_bad_seq}: {r.why}. /mind says more."
        return self.status(c)

    def status(self, c) -> str:
        st = c.state()
        up, pid = c.running()
        lines = ["Brain is on."]
        if self.hardened():
            lines.append(f"Scorekeeper: {'running' if up else 'not running'} as its own user (hardened mode).")
        elif up:
            lines.append(f"Scorekeeper: running (process {pid}).")
        else:
            lines.append("Scorekeeper: not running right now; it's started again by itself.")
        a = st["anchor"]
        start = int(a["seq"]) if a else 1
        r = c.verify(start)  # quick: from the last anchor (/mind verify checks everything)
        state = "checks out" if r.ok else f"doesn't check out at #{r.first_bad_seq} ({r.why})"
        lines.append(f"Log: {st['records']:,} records, head #{st['head']} {st['hash'][:12]}, {state}.")
        if a:
            when = _when(a.get("at"))
            lines.append(f"Last anchor: #{a['seq']} {str(a['hash'])[:12]}{f', {when}' if when else ''}.")
        scored = sum(st["scores"].values())
        lines.append("Scores: none yet." if not scored else f"Scores: {scored} kept.")
        if st["waiting"]:
            lines.append(f"Waiting to be logged: {st['waiting']} (kept aside until the scorekeeper takes them).")
        if st["dropped"]:
            lines.append(f"Dropped since Kurooto started: {st['dropped']} (more came than could be kept).")
        return "\n".join(lines)


def _when(iso) -> str:
    try:
        t = dt.datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return ""
    return t.strftime("%d %b %H:%M")


def button(app, ref: str, act: str) -> str:
    """Delete Brain's data / Keep it, under the message that Brain is off (a core button: Brain is off by then)."""
    if act != "delete":
        return "Kept."
    try:
        asked = int(ref)
    except ValueError:
        return "That button has expired."
    if time.time() - asked > CONFIRM_S:
        return "That button has expired; turn Brain off again to be asked again."
    if mind.on(app):
        return "Brain is on again, so its data stays. Turn it off first."
    d = app.paths.state / "mind"
    c = mind.connect(app)
    up, _ = c.running()
    if up:
        return "Brain's scorekeeper is still stopping; try again in a minute."
    mind.forget_client(app)
    n = mlog.MindLog(d / "log.db").count() if d.exists() else 0
    shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(app.paths.state / "mind-journal", ignore_errors=True)  # its journal (mind/journal.py)
    shutil.rmtree(app.paths.state / "mind-story", ignore_errors=True)  # its life story (mind/story.py)
    for f in (
        "mind-gate.json",
        "mind-mood.json",
        "mind-tone.json",
        "mind-promises.json",
        "mind-feelings.json",
        "mind-acts.json",
    ):  # the gate's, the read's, the tone's, its promises' and its acts' own files
        (app.paths.state / f).unlink(missing_ok=True)
    app.events.emit("mind_deleted", records=n)
    return "Deleted Brain's data." if not d.exists() else "Couldn't delete all of it; /mind says what's left."
