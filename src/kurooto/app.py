"""The running assistant: core services, the modules you've turned on, and where your messages go."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from kurooto.core.availability import Availability
from kurooto.core.config import Settings, register_defaults
from kurooto.core.events import Events
from kurooto.core.notify import Notifier
from kurooto.core.paths import Paths, paths
from kurooto.core.power import Power
from kurooto.core.scheduler import Scheduler
from kurooto.core.secrets import Secrets
from kurooto.modules.base import Incoming, Module
from kurooto.modules.text import QUESTION, tidy, too_complex

register_defaults(
    "you",
    {
        "name": "",  # what Kurooto calls you
        "timezone": "",  # IANA name, e.g. Europe/Berlin; empty = this computer's
        "workspace": "",  # your notes folder; empty = Documents/Kurooto
        "assistant_name": "Kurooto",
        "language": "follow",  # answer in the language you write in
    },
)
register_defaults("modules", {"enabled": []})


def default_workspace(home: Path | None = None) -> Path:
    if os.environ.get("KUROOTO_HOME") and home is None:  # tests and portable installs stay inside their folder
        return Path(os.environ["KUROOTO_HOME"]) / "workspace"
    home = home or Path.home()
    docs = home / "Documents"
    return (docs if docs.is_dir() or sys.platform in ("win32", "darwin") else home) / "Kurooto"


class App:
    def __init__(self, p: Paths | None = None):
        self.paths = (p or paths()).ensure()
        self.settings = Settings(self.paths.config / "settings.json")
        self.secrets = Secrets(self.paths.config)
        self.events = Events(self.paths.state)
        self.availability = Availability(self.paths.state, self.settings)
        self.scheduler = Scheduler(self.paths.state / "schedule.db", tz=self.settings.get("you.timezone") or None)
        self.scheduler.gates["quiet"] = self.availability.quiet_gate
        self.scheduler.gates["call_block"] = self.availability.call_gate
        self.scheduler.on_result = self._job_done
        self.notifier = Notifier(self)
        self.power = Power(self)
        from kurooto.core.aboutyou import AboutYou

        self.about = AboutYou(self)
        self.scheduler.hold = self.power.hold
        from kurooto.core.jobs import Jobs

        self.jobs = Jobs(self)
        from kurooto.update.service import Updates

        self.updates = Updates(self)
        self.jobs.then_actions["aboutyou.save"] = self.about.save_profile
        from kurooto.core.ask import Ask  # questions and approvals for you, from any feature (app.ask)

        self.ask = Ask(self)
        from kurooto.providers.agy import consent_answer  # may agy use Kurooto's tools? (asked once, providers/agy.py)

        self.ask.hooks["agy.tools"] = lambda q, answer: consent_answer(self, q, answer)
        from kurooto.core.presence import Presence  # "going offline" / "back online" messages (core/presence.py)

        self.presence = Presence(self)
        self.stop_reason = ""  # why it's stopping, for the "going offline" message ("stopped", "turned off")
        self.restart_requested = False
        self._stop = None  # the daemon's stop event, so an update can ask for a restart
        self._loop = None
        self._background: dict = {}  # module id -> its running background task (Telegram polling, the call line)
        self.modules: dict[str, Module] = {}
        from kurooto.modules.catalog import CATALOG

        for cls in CATALOG:
            self.modules[cls.id] = cls(self)
        from kurooto.core import overlay  # your own add-ons (core/overlay.py), only when you've turned them on

        overlay.load(self)

    @property
    def name(self) -> str:
        return self.settings.get("you.assistant_name") or "Kurooto"

    @property
    def workspace(self) -> Path:
        w = self.settings.get("you.workspace")
        ws = Path(w) if w else default_workspace()
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def notify(self, text: str, **kw):
        return self.notifier.send(text, **kw)

    # -------------------------------------------------------------------------------------- modules
    def enabled(self) -> list[Module]:
        on = set(self.settings.get("modules.enabled") or [])
        return [m for m in self.modules.values() if m.id in on]

    def is_on(self, module_id: str) -> bool:
        return module_id in (self.settings.get("modules.enabled") or [])

    def enable(self, module_id: str) -> tuple[bool, str]:
        m = self.modules.get(module_id)
        if not m:
            return False, f"no feature called {module_id}"
        missing = [r for r in m.requires if not self.is_on(r)]
        if missing:
            return False, f"{m.title} needs {', '.join(self.modules[r].title for r in missing)} first"
        ok, why = m.ready()
        if not ok:
            return False, why
        on = list(self.settings.get("modules.enabled") or [])
        if module_id not in on:
            self.settings.set("modules.enabled", [*on, module_id])
        m.start()
        self.start_background(m)
        self.events.emit("module_enabled", module=module_id)
        return True, f"{m.title} is on"

    def disable(self, module_id: str) -> tuple[bool, str]:
        users = [m.title for m in self.enabled() if module_id in m.requires]
        if users:
            return False, f"turn off {', '.join(users)} first; they use it"
        m = self.modules.get(module_id)
        if m:
            m.stop()
            self.stop_background(m)
        self.settings.set(
            "modules.enabled", [x for x in (self.settings.get("modules.enabled") or []) if x != module_id]
        )
        self.events.emit("module_disabled", module=module_id)
        return True, f"{m.title if m else module_id} is off"

    def start_background(self, m: Module) -> None:
        """Start a module's long-running part (its `background(stop)` coroutine) on the daemon's loop, once."""
        loop, stop = self._loop, self._stop
        if loop is None or stop is None or not hasattr(m, "background") or not loop.is_running():
            return
        if not self.power.may_run(m):  # on battery or paused: it starts when that ends
            return

        def go():
            t = self._background.get(m.id)
            if t is None or t.done():
                self._background[m.id] = loop.create_task(self._guard(m, stop), name=m.id)

        loop.call_soon_threadsafe(go)

    async def _guard(self, m: Module, stop) -> None:
        import asyncio

        while not stop.is_set():
            try:
                await m.background(stop)
                return
            except asyncio.CancelledError:
                raise
            except Exception as e:  # a crash in one feature never takes the others down
                self.events.emit("module_failed", module=m.id, error=f"{type(e).__name__}: {e}"[:300])
                try:
                    await asyncio.wait_for(stop.wait(), timeout=30)
                except TimeoutError:
                    pass

    def stop_background(self, m: Module) -> None:
        t, loop = self._background.pop(m.id, None), self._loop
        if t is not None and loop is not None and loop.is_running():
            loop.call_soon_threadsafe(t.cancel)

    def request_stop(self) -> None:
        """Stop, and don't come back (exit 0: the launcher and supervisor leave it stopped)."""
        if self._stop is not None:
            loop = getattr(self, "_loop", None)
            (loop.call_soon_threadsafe(self._stop.set) if loop else self._stop.set())

    def request_restart(self) -> None:
        """Stop, and tell the launcher to start again (on whatever version current.json now names)."""
        self.restart_requested = True
        if self._stop is not None:
            loop = getattr(self, "_loop", None)
            (loop.call_soon_threadsafe(self._stop.set) if loop else self._stop.set())

    def start(self) -> None:
        """Start the update checks and every enabled module (register its jobs and actions)."""
        try:
            from kurooto.core import upgrade  # coming from an older version: what changes once (core/upgrade.py)

            upgrade.run(self)
        except Exception as e:
            self.events.emit("module_failed", module="upgrade", error=f"{type(e).__name__}: {e}"[:300])
        try:
            self.updates.start()
        except Exception as e:
            self.events.emit("module_failed", module="updates", error=str(e)[:300])
        try:
            self.ask.start()
        except Exception as e:
            self.events.emit("module_failed", module="ask", error=str(e)[:300])
        try:
            self.presence.start()  # back after being away? (core/presence.py)
        except Exception as e:
            self.events.emit("module_failed", module="presence", error=str(e)[:300])
        for m in self.enabled():
            try:
                m.start()
                self.start_background(m)
            except Exception as e:
                self.events.emit("module_failed", module=m.id, error=f"{type(e).__name__}: {e}"[:300])

    # ------------------------------------------------------------------------------------- messages
    def handle(self, msg: Incoming) -> None:
        """Route one message from you: a reply to something Kurooto asked, a /command, files, a plain-English
        request that runs instantly, or (if Chat is on) a request for the AI."""
        mods = self.enabled()
        self.events.emit("message_in", via=msg.via, chars=len(msg.text), files=len(msg.files))
        if msg.reply_to and msg.reply_to.get("kind") == "ask":  # an answer to a question (core/ask.py)
            out = self.ask.reply(msg, msg.reply_to.get("ref"))
            if out:
                msg.reply(out)
            return
        if msg.reply_to:
            for m in mods:
                h = m.replies().get(msg.reply_to.get("kind"))
                if h:
                    self.notifier.retract(msg.reply_to.get("kind"), msg.reply_to.get("ref"))  # off your phones
                    out = h(msg, msg.reply_to.get("ref"))
                    if out:
                        msg.reply(out)
                    return
        text = msg.text.strip()
        if text.startswith("/"):
            name, arg = (text[1:].split(None, 1) + ["", ""])[:2]  # "/journal\nmy day" works too
            name = name.split("@")[0].lower()
            if name in ("start", "help"):
                msg.reply(self.help())
                return
            if name == "aboutme":  # your profile's In-brief part, and where to edit it (core/aboutyou.py)
                msg.reply(self.about.for_chat())
                return
            if name in ("q", "questions"):  # open questions, with their buttons (core/ask.py)
                out = self.ask.command(msg, arg.strip())
                if out:
                    msg.reply(out)
                return
            for m in mods:
                for c in m.commands():
                    if c.name == name:
                        out = c.handler(msg, arg.strip())
                        if out:
                            msg.reply(out)
                        return
            skills = self.modules.get("skills")  # not a command: a skill (/journal, /study-log, yours), if it's one
            if skills is not None and self.is_on("skills"):
                out = skills.typed(msg, name, arg.strip())
                if out is not None:
                    msg.reply(out)
                    return
        if msg.files:
            for m in mods:
                h = getattr(m, "take_files", None)
                if h:
                    out = h(msg)
                    if out:
                        msg.reply(out)
                    return
        plain = tidy(text)
        if plain and not too_complex(plain):
            asks = bool(QUESTION.search(plain))
            for m in mods:
                for it in m.intents():
                    if asks and not it.questions:
                        continue
                    slots = it.match(plain)
                    if slots is not None:
                        self.events.emit("intent", name=it.name)
                        msg.reply(it.run(msg, slots) or "Done.")
                        return
        from kurooto.core import syncall  # "sync everything", and /sync while Notes sync is off (core/syncall.py)

        if syncall.wanted(text) or text.lower().split("@")[0] == "/sync":
            msg.reply(syncall.start(self)[1])
            return
        chat = self.modules.get("chat")
        if chat and self.is_on("chat") and text:
            out = chat.ask(msg)
            if out:
                msg.reply(out)
            return
        msg.reply(
            "I can't answer free text yet: turn on Chat (it uses the AI you picked) in Settings. /help lists "
            "what works now."
        )

    def callback(self, data: str) -> str:
        """A button you tapped: "<prefix>:<ref>:<action>"."""
        prefix, ref, act = (data.split(":", 2) + ["", ""])[:3]
        self.notifier.retract(button=data)  # the phone app's copy of that message goes (core/notify.py)
        if prefix == "upd":
            return self.updates.button(ref, act)
        if prefix == "ask":
            return self.ask.button(ref, act)
        for m in self.enabled():
            h = m.callbacks().get(prefix)
            if h:
                try:
                    return h(ref, act) or "ok"
                except Exception as e:
                    return f"error: {e}"[:190]
        return "that button is from a feature that's off now"

    def help(self) -> str:
        lines = [f"{self.name}, your assistant. Plain English works; these commands do too:"]
        for m in self.enabled():
            lines += m.help()
        lines.append("/q  open questions I asked you (reply to one to answer it)")
        lines.append("/aboutme  what I know about you (your profile's In-brief part), and where to edit it")
        if not self.is_on("notes_sync"):
            lines.append("/sync  sync everything that's on (Classroom, calendar, research, notes brain)")
        if not self.is_on("chat"):
            lines.append("(Chat is off, so free text isn't sent to an AI.)")
        return "\n".join(lines)

    def _job_done(self, job, outcome: str, err: BaseException | None) -> None:
        if outcome in ("error", "missing-action"):
            self.events.emit("job_failed", key=job.key, outcome=outcome, error=str(err or job.last_result)[:300])

    def close(self) -> None:
        if self._stop is not None:  # the assistant itself is stopping (not a `kurooto` command): last words
            for m in self.enabled():
                down = getattr(m, "shutdown", None)  # e.g. Notes sync sends up what's left
                if down:
                    try:
                        down()
                    except Exception as e:
                        self.events.emit("module_failed", module=m.id, error=f"at shutdown: {e}"[:300])
        self.scheduler.close()
        self.jobs.close()
