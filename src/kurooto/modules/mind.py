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
import threading
import time
from pathlib import Path

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.events import subscribe
from kurooto.core.state import jload, jsave
from kurooto.mind import (
    act,
    attention,
    beliefs,
    feelings,
    gate,
    improve,
    journal,
    measure,
    mood,
    promises,
    signals,
    story,
    tone,
    workspace,
)
from kurooto.mind import log as mlog
from kurooto.mind import plans as mind_plans
from kurooto.mind.harness import indicators as harness_indicators
from kurooto.mind.harness import run as harness_run
from kurooto.mind.lab import report as lab_report
from kurooto.mind.lab import runner as lab_runner
from kurooto.mind.plans import tree as plans_tree
from kurooto.mind.senses import activity as senses_activity
from kurooto.mind.senses import intero as senses_intero
from kurooto.mind.senses import phone as senses_phone
from kurooto.mind.senses import store as senses_store
from kurooto.mind.skills import demos as skill_demos
from kurooto.mind.skills import distill as skill_distill
from kurooto.mind.skills import finetune as skill_finetune
from kurooto.mind.skills import library as skill_library
from kurooto.mind.tom import attention_of as tom_attention
from kurooto.mind.tom import beliefs_about as tom_beliefs
from kurooto.mind.tom import goals as tom_goals
from kurooto.mind.tom import knowledge as tom_knowledge
from kurooto.mind.tom import model as tom_model
from kurooto.mind.tom import prefs as tom_prefs
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
        # stage 10: the workspace's cycle (and on an alarm or call, at once), then the beliefs from today's read
        self.every("workspace", "every 1m", lambda p: workspace.cycle(self.app) and None)
        self.every("beliefs", "hourly", lambda p: beliefs.sync(self.app) if mind.on(self.app) else 0)
        # stage 11: the overnight lab (on the charger, lid open) and its morning note
        workspace.register_bidder("lab", lab_report.bid)
        self.every("lab", "daily 01:30", lambda p: lab_runner.nightly(self.app) and None)
        self.every("lab_digest", "daily 07:40", self._lab_digest)
        # stage 15: week-scale plans, remade each morning; one line on Sunday evening at most
        self.every("plans", "daily 06:10", lambda p: mind_plans.run(self.app) and None)
        self.every("plans_weekly", "weekly sun 19:20", lambda p: mind_plans.weekly(self.app) and None)
        # stage 14: the model of their mind (what they know, believe, want, prefer, attend to) and false-belief checks
        self.every("tom_sync", "hourly", self._tom_sync)
        self.every("tom_check", "every 30m", lambda p: tom_beliefs.check(self.app) and None)
        # stage 13: a body: its own machine every minute, the activity stream (opt-in), the totals kept 7 days raw
        workspace.register_bidder("body", senses_intero.bids)
        self.every("intero", "every 1m", lambda p: senses_intero.tick(self.app) and None)
        self.every("activity", "every 1m", lambda p: senses_activity.tick(self.app) and None)
        self.every("activity_poll", "every 5m", lambda p: senses_activity.poll(self.app) and None)
        self.every("senses_roll", "daily 04:30", lambda p: senses_store.rollup(self.app) and None)
        # stage 12: skills from tasks that worked out, the ones it noticed you repeat, retirement, the weekly fine-tune
        self.every("skills_distill", "daily 03:10", lambda p: skill_distill.nightly(self.app) and None)
        self.every("skills_offer", "daily 18:20", lambda p: skill_demos.offer(self.app) and None)
        self.every("skills_retire", "daily 04:20", lambda p: skill_library.retire_stale(self.app) and None)
        self.every("finetune", "daily 03:40", lambda p: skill_finetune.run(self.app) and None)
        # stage 09: the hidden harness, nightly and on the charger only
        self.every("harness", "daily 02:40", lambda p: harness_run.nightly(self.app) if mind.on(self.app) else None)

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
        if kind in ("alarm_rang", "call_rang") and workspace.on(self.app):  # a high-priority event: an immediate cycle
            workspace.poke(self.app, f"event:{kind}", "event", kind.replace("_", " "))
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
                "capabilities",
                "what Kurooto can do, measured on tasks it has never seen; /capabilities run measures now",
                self.capabilities_cmd,
                usage="/capabilities [run]",
            ),
            Command(
                "indicators",
                "Functional indicators (not evidence of sentience): ablation tests, with what was measured",
                self.indicators_cmd,
            ),
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
                "plan",
                "this week's suggested hours and which milestones may be missed: /plan, /plan effort <id> <hours>",
                self.plan_cmd,
                usage="/plan [effort <id> <hours>]",
            ),
            Command(
                "model",
                "what Kurooto thinks you know, believe, want and prefer; /model wrong <id>, /model forget <id>",
                self.model_cmd,
                usage="/model [knowledge|belief|goal|pref|attention|wrong <id>|forget <id>]",
            ),
            Command(
                "senses",
                "what Kurooto senses: its machine, your activity (if on), your phone's sensors (each opt-in)",
                self.senses_cmd,
                usage="/senses [on|off <sensor>|forget [sensor]|wifi label <id> <name>|body]",
            ),
            Command(
                "learned",
                "the skills Kurooto has learned: /learned, /learned run <name> <text>, /learned retire <name>",
                self.learned_cmd,
                usage="/learned [run <name> <text>|retire <name>]",
            ),
            Command(
                "lab",
                "the overnight lab: /lab, /lab protocol <project>, /lab run <project>, /lab add <folder>, /lab results",
                self.lab_cmd,
                usage="/lab [protocol <project> [approve]|run <project>|add <folder>|results]",
            ),
            Command(
                "improve",
                "Kurooto improving itself through gated proposals: /improve, /improve promote <id>",
                self.improve_cmd,
                usage="/improve [promote <id>]",
            ),
            Command(
                "thinking",
                "what Kurooto has on its mind right now, why, and how well it predicts its own attention; "
                "/thinking pin|unpin|mute|veto|unveto <item or part>",
                self.thinking_cmd,
                usage="/thinking [pin|unpin|mute|veto|unveto <item>]",
            ),
            Command(
                "beliefs",
                "what Kurooto believes, with where each belief came from and how sure it is; /beliefs <topic>",
                self.beliefs_cmd,
                usage="/beliefs [topic]",
            ),
            Command(
                "mind",
                "Brain: its scorekeeper, its log and whether the log checks out; /mind verify checks all of it; "
                "/mind gate shows what it held back or removed from messages today",
                self.cmd,
                usage="/mind [verify|gate]",
            ),
        ]

    def _lab_digest(self, payload: dict | None = None) -> bool:
        """Morning: what the lab did last night, nulls as much as wins (once per night)."""
        if not mind.part_on(self.app, "lab"):
            return False
        last = jload(self.app.paths.state / "lab" / "last-night.json", {}) or {}
        if not last or last.get("told") == last.get("at"):
            return False
        text = lab_report.digest(self.app)
        if not text:
            return False
        last["told"] = last.get("at")
        jsave(self.app.paths.state / "lab" / "last-night.json", last)
        self.app.notify(text, kind="info", why="mind.lab")
        return True

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

    def capabilities_cmd(self, msg: Incoming, arg: str) -> str:
        if (arg or "").strip().lower() == "run":
            if not mind.part_on(self.app, "harness"):
                return "The harness is off (mind.harness.on, with Brain)."
            res = harness_run.run(self.app)
            harness_run.report(self.app, res)
            return harness_run.capabilities(self.app)
        return harness_run.capabilities(self.app)

    def indicators_cmd(self, msg: Incoming, arg: str) -> str:
        if not mind.part_on(self.app, "harness"):
            return "The harness is off (mind.harness.on, with Brain)."
        return harness_indicators.page(self.app)

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

    def _tom_sync(self, payload: dict | None = None) -> int:
        if not tom_model.on(self.app):
            return 0
        n = tom_knowledge.from_notes(self.app) + tom_knowledge.from_quiz(self.app) + tom_goals.sync_deadlines(self.app)
        n += tom_prefs.sync(self.app) + len(tom_goals.infer_intentions(self.app))
        tom_attention.remember(self.app)
        return n

    def plan_cmd(self, msg: Incoming, arg: str) -> str:
        if not mind.on(self.app):
            return "Brain is off (Features → Brain)."
        w = (arg or "").split()
        if len(w) == 3 and w[0] == "effort":
            try:
                ok = plans_tree.set_effort(self.app, w[1], float(w[2]))
            except ValueError:
                ok = False
            return (
                f"Noted: {w[1]} is {w[2]} hours."
                if ok
                else "Use /plan effort <id> <hours> (the id is in brackets in /plan)."
            )
        return mind_plans.view(self.app)

    def model_cmd(self, msg: Incoming, arg: str) -> str:
        if not mind.on(self.app):
            return "Brain is off (Features → Brain)."
        w = (arg or "").split()
        if len(w) == 2 and w[0] == "wrong":
            return tom_model.wrong(self.app, w[1])
        if len(w) == 2 and w[0] == "forget":
            return tom_model.forget(self.app, w[1])
        return tom_model.report(self.app, w[0] if w else None)

    def senses_cmd(self, msg: Incoming, arg: str) -> str:
        if not mind.on(self.app):
            return "Brain is off (Features → Brain)."
        w = (arg or "").split()
        names = ["intero", "activity", *[f"phone.{s}" for s in senses_phone.SENSORS]]
        if w and w[0] == "body":
            return senses_intero.report(self.app)
        if len(w) == 2 and w[0] in ("on", "off"):
            key = w[1] if w[1] in names else (f"phone.{w[1]}" if f"phone.{w[1]}" in names else "")
            if not key:
                return "Senses: " + ", ".join(n.removeprefix("phone.") for n in names)
            self.app.settings.set(f"mind.senses.{key}", w[0] == "on")
            if w[0] == "off":
                senses_store.forget(
                    self.app,
                    None if key in ("intero",) else ("activity" if key == "activity" else "phone:" + key[6:]),
                    today_only=False,
                )
            return f"{key.removeprefix('phone.')}: {w[0]}" + (" (what it kept of it is gone)" if w[0] == "off" else "")
        if w and w[0] == "forget":
            sensor = None if len(w) < 2 else ("activity" if w[1] == "activity" else f"phone:{w[1]}")
            return f"Forgot {senses_store.forget(self.app, sensor)} reading(s) from today."
        if len(w) >= 4 and w[:2] == ["wifi", "label"]:
            return (
                "Labelled."
                if senses_phone.label_wifi(self.app, w[2], " ".join(w[3:]))
                else "That network code or name isn't valid."
            )
        lines = [
            f"- its own machine: {'on' if senses_intero.on(self.app) else 'off'} (/senses body)",
            "- your activity: "
            + (f"on: {senses_activity.today(self.app)}" if senses_activity.on(self.app) else "off (opt-in)"),
        ]
        for s in senses_phone.SENSORS:
            lines.append(
                f"- phone {s}: "
                + ("on: " + senses_phone.today(self.app, s) if senses_phone.enabled(self.app, s) else "off")
            )
        return (
            "What it senses (each opt-in, nothing leaves this computer):\n"
            + "\n".join(lines)
            + "\n/senses off <name> switches one off and deletes what it kept; /senses forget [name] clears today."
        )

    def callbacks(self):
        return {"skl": lambda ref, act: skill_demos.button(self.app, ref, act)}

    def learned_cmd(self, msg: Incoming, arg: str) -> str:
        if not mind.on(self.app):
            return "Brain is off (Features → Brain)."
        words = (arg or "").split(None, 2)
        if len(words) >= 2 and words[0].lower() == "retire":
            return "Retired." if skill_library.retire(self.app, words[1]) else f"There's no active skill {words[1]}."
        if len(words) >= 2 and words[0].lower() == "run":
            m = skill_library.meta(self.app, words[1])
            if not m or m.get("retired"):
                return f"There's no active skill {words[1]}."
            first = (m.get("inputs") or ["text"])[0]
            out = skill_library.run_by_owner(self.app, words[1], {first: words[2] if len(words) > 2 else ""})
            return out or "It gave nothing back."
        return skill_library.listing(self.app)

    def lab_cmd(self, msg: Incoming, arg: str) -> str:
        if not mind.on(self.app):
            return "Brain is off (Features → Brain)."
        if not mind.part_on(self.app, "lab"):
            return "The lab is off (mind.lab.on)."
        words = (arg or "").split()
        sub = words[0].lower() if words else ""
        if sub == "results":
            return lab_report.results(self.app)
        if sub == "add" and len(words) > 1:
            folder = " ".join(words[1:])
            if not Path(folder).expanduser().is_dir():
                return f"There's no folder {folder}."
            cur = list(self.app.settings.get("mind.lab.projects") or [])
            if folder not in cur:
                self.app.settings.set("mind.lab.projects", [*cur, folder])
            return f"Added. Next: /lab protocol {lab_runner.slug(Path(folder).name)}"
        if sub in ("protocol", "run") and len(words) > 1:
            slug = lab_runner.slug(words[1])
            root = lab_runner.projects(self.app).get(slug)
            if root is None:
                return f"{words[1]} isn't a lab project. /lab add <folder> first."
            if sub == "protocol":
                if len(words) > 2 and words[2].lower() == "approve":
                    return lab_runner.approve(self.app, slug, root)
                text, notes = lab_runner.draft(self.app, slug, root)
                st = lab_runner.status(self.app, slug, root)[0]
                where = lab_runner.protocol_file(self.app, slug, root)
                return (
                    f"Protocol for {slug} ({st}), in {where}:\n{text or '(none could be drafted)'}\n"
                    + "".join(f"- {n}\n" for n in notes)
                    + (f"Edit the file if it's off, then /lab protocol {slug} approve." if st != "approved" else "")
                )
            threading.Thread(target=self._lab_now, args=(slug, root), daemon=True).start()
            return f"Started a batch on {slug}; the result comes as a message (it runs when the computer can spare it)."
        return lab_report.listing(self.app)

    def _lab_now(self, slug: str, root) -> None:
        res = lab_runner.run_batch(self.app, slug, root)
        if res.get("finished"):
            self.app.notify(lab_report.batch_line(slug, res["analysis"], res["baseline"]), kind="result", why="asked")
        else:
            self.app.notify(f"{slug}: {res.get('why') or 'nothing ran'}.", kind="info", why="asked")

    def improve_cmd(self, msg: Incoming, arg: str) -> str:
        if not mind.on(self.app):
            return "Brain is off (Features → Brain)."
        words = (arg or "").split()
        if len(words) == 2 and words[0].lower() == "promote":
            return improve.promote(self.app, words[1])
        return improve.listing(self.app)

    def thinking_cmd(self, msg: Incoming, arg: str) -> str:
        if not mind.on(self.app):
            return "Brain is off (Features → Brain)."
        words = (arg or "").split()
        acts = {
            "pin": workspace.pin,
            "unpin": workspace.unpin,
            "mute": workspace.mute,
            "veto": workspace.veto,
            "unveto": workspace.unveto,
        }
        if len(words) == 2 and words[0].lower() in acts:
            return acts[words[0].lower()](self.app, words[1])
        return attention.report(self.app)

    def beliefs_cmd(self, msg: Incoming, arg: str) -> str:
        return beliefs.report(self.app, arg or "") if mind.on(self.app) else "Brain is off (Features → Brain)."

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
    shutil.rmtree(app.paths.state / "mind-senses", ignore_errors=True)  # the senses' readings, salt and totals
    shutil.rmtree(app.paths.state / "mind-skills", ignore_errors=True)  # the learned skills and the fine-tune's folder
    shutil.rmtree(app.paths.state / "lab", ignore_errors=True)  # the lab's protocols, pre-registrations and results
    for f in (
        "mind-gate.json",
        "mind-mood.json",
        "mind-tone.json",
        "mind-promises.json",
        "mind-feelings.json",
        "mind-acts.json",
        "mind-workspace.json",
        "mind-beliefs.json",
        "mind-improve.json",
        "mind-distilled.json",
        "mind-demos.json",
        "mind-finetune.json",
        "mind-intero.json",
        "mind-activity.json",
        "mind-tom.json",
        "mind-plans.json",
        "mind-plan-last.json",
    ):  # the gate's, the read's, the tone's, its promises' and its acts' own files
        (app.paths.state / f).unlink(missing_ok=True)
    app.events.emit("mind_deleted", records=n)
    return "Deleted Brain's data." if not d.exists() else "Couldn't delete all of it; /mind says what's left."
