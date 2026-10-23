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
from kurooto.modules.base import Command, Incoming, Module
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
ALWAYS = ("status",)  # commands that answer even while their feature is off (/help and /jobs are Kurooto's own)


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
        from kurooto.core.quota import Quota  # free AI limits: counted, learned, kept for you (core/quota.py)

        self.quota = Quota(self)
        from kurooto.core.jobs import Jobs

        self.jobs = Jobs(self)
        from kurooto.update.service import Updates

        self.updates = Updates(self)
        self.jobs.then_actions["aboutyou.save"] = self.about.save_profile
        from kurooto.core.ask import Ask  # questions and approvals for you, from any feature (app.ask)

        self.ask = Ask(self)
        from kurooto.providers.agy import consent_answer  # may agy use Kurooto's tools? (asked once, providers/agy.py)

        self.ask.hooks["agy.tools"] = lambda q, answer: consent_answer(self, q, answer)
        from kurooto import providers

        providers.drop_retired(self)  # an AI that's no longer offered (Codex) isn't left as the main one
        from kurooto.core.presence import Presence  # "going offline" / "back online" messages (core/presence.py)

        self.presence = Presence(self)
        from kurooto.core.health import Health  # Kurooto keeps itself working: checks, the daily pass, fixes

        self.health = Health(self)
        from kurooto.core.calm import Calm  # (calm) why each message came, Less of this, the daily limit

        self.calm = Calm(self)
        from kurooto.core.keep import Keep  # what you use of each feature; day 10 and monthly: Keep, Quiet or Off

        self.keep = Keep(self)
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
            from kurooto.core import upgrade  # a feature Kurooto no longer has (Attendance) is turned off, settings go

            upgrade.drop_retired(self)
        except Exception as e:
            self.events.emit("module_failed", module="upgrade", error=f"{type(e).__name__}: {e}"[:300])
        try:
            from kurooto.core import zones  # a time zone saved under an old name gets today's (core/zones.py)

            zones.settle(self)
        except Exception as e:
            self.events.emit("module_failed", module="zones", error=f"{type(e).__name__}: {e}"[:300])
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
        try:  # (ws5) your skills as slash commands in agy and other agents, when that's on (core/agent_export.py)
            from kurooto.core import agent_export

            agent_export.start(self)
            from kurooto.core import reserve

            reserve.start(self)  # Markdown copies of alarms, deadlines, settings... an AI program can just open
        except Exception as e:
            self.events.emit("module_failed", module="agent_export", error=str(e)[:300])
        for m in self.enabled():
            try:
                m.start()
                self.start_background(m)
            except Exception as e:
                self.events.emit("module_failed", module=m.id, error=f"{type(e).__name__}: {e}"[:300])
        try:
            self.health.start()  # the daily pass, after the features' timers are in (core/health.py)
        except Exception as e:
            self.events.emit("module_failed", module="health", error=f"{type(e).__name__}: {e}"[:300])
        try:
            self.calm.start()  # (calm) the evening bundle and the monthly suggestion (core/calm.py)
        except Exception as e:
            self.events.emit("module_failed", module="calm", error=f"{type(e).__name__}: {e}"[:300])
        try:
            self.keep.start()  # day 10, then monthly: features you don't use (core/keep.py)
        except Exception as e:
            self.events.emit("module_failed", module="keep", error=f"{type(e).__name__}: {e}"[:300])
        try:
            from kurooto.core import retention  # what's older than privacy.keep_days goes, daily (core/retention.py)

            retention.start(self)
        except Exception as e:
            self.events.emit("module_failed", module="retention", error=f"{type(e).__name__}: {e}"[:300])

    # ------------------------------------------------------------------------------------- messages
    def handle(self, msg: Incoming, also: list[Module] | None = None) -> None:
        """Route one message from you: a reply to something Kurooto asked, a /command, files, a plain-English
        request that runs instantly, or (if Chat is on) a request for the AI. `also`: features that answer this
        message as if they were on (the setup page's try-it box, web/tryit.py)."""
        mods = self.enabled() + [m for m in also or [] if not self.is_on(m.id)]
        self.events.emit("message_in", via=msg.via, chars=len(msg.text), files=len(msg.files))
        if msg.reply_to:  # (calm) you answered one of its messages (core/calm.py)
            self.calm.touched(map_kind=msg.reply_to.get("kind"), map_ref=msg.reply_to.get("ref"))
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
                    self.keep.used(m.id, "reply", msg.via)
                    out = h(msg, msg.reply_to.get("ref"))
                    if out:
                        msg.reply(out)
                    return
        text = msg.text.strip()
        if text.startswith("/"):
            name, arg = (text[1:].split(None, 1) + ["", ""])[:2]  # "/journal\nmy day" works too
            name = name.split("@")[0].lower()
            if name in ("start", "help"):
                msg.reply(self.help(arg if name == "help" else ""))
                return
            if name == "aboutme":  # your profile's In-brief part, and where to edit it (core/aboutyou.py)
                msg.reply(self.about.for_chat())
                return
            if name in ("q", "questions"):  # open questions, with their buttons (core/ask.py)
                out = self.ask.command(msg, arg.strip())
                if out:
                    msg.reply(out)
                return
            if name == "health":  # what isn't working, with Fix buttons (core/health.py)
                text, buttons = self.health.command(arg)
                msg.reply(text, buttons=buttons)
                return
            if name == "keep":  # what you used of each feature, with Quiet and Off (core/keep.py)
                text, buttons = self.keep.command(arg)
                msg.reply(text, buttons=buttons)
                return
            if name == "fixme":  # what to do, by rules: it works when the AI is what broke (core/fixme.py)
                from kurooto.core import fixme

                text, buttons = fixme.command(self, msg, arg)
                msg.reply(text, buttons=buttons)
                return
            if name in ("calm", "why"):  # (calm) the daily limit, what's turned down; why the last one came
                text, buttons = self.calm.command(arg) if name == "calm" else self.calm.why_last()
                msg.reply(text, buttons=buttons)
                return
            if name == "inferred":  # what was set up from what you said, with undo (core/infer.py)
                from kurooto.core import infer

                msg.reply(infer.command(self, arg))
                return
            if name == "jobs":  # what the AI is working on and what waits, with Cancel buttons (core/jobs.py)
                text, buttons = self.jobs.command(arg)
                msg.reply(text, buttons=buttons)
                return
            if name == "forget":  # forget the last 7 days (or all) of what's kept now (core/retention.py)
                from kurooto.core import retention

                text, buttons = retention.command(self, arg)
                msg.reply(text, buttons=buttons)
                return
            if name == "gists":  # one line of what each forgotten conversation decided (core/gists.py)
                from kurooto.core import gists

                msg.reply(gists.command(self, arg))
                return
            for m in mods:
                for c in m.commands():
                    if c.name == name:
                        self.keep.used(m.id, "command", msg.via)
                        out = c.handler(msg, arg.strip())
                        if out:
                            msg.reply(out)
                        return
            found = self.off_command(name, mods)  # a feature that's off: how to turn it on, never the AI
            if found is not None:
                m, c = found
                if c is not None and name in ALWAYS:  # /status answers with Telegram off too (from a terminal)
                    out = c.handler(msg, arg.strip())
                    if out:
                        msg.reply(out)
                    return
                title = m.title.split(" (")[0]  # "Google (Classroom, Gmail drafts)": Google
                msg.reply(f"{title} is off: Features → {title} → Turn on.")
                return
            skills = self.modules.get("skills")  # not a command: a skill (/journal, /study-log, yours), if it's one
            if skills is not None and self.is_on("skills"):
                out = skills.typed(msg, name, arg.strip())
                if out is not None:
                    msg.reply(out)
                    return
        learning = self.modules.get("learning") if self.is_on("learning") else None
        if learning is not None and text:  # "no, ..." just after a skill's answer teaches it (it goes on as usual)
            learning.heard(msg, text)
        if text and not text.startswith("/"):  # "I got a project under Prof X": set up what it states (core/infer.py)
            from kurooto.core import infer

            infer.observe(self, text, via=msg.via)
        books = self.modules.get("books")  # a PDF sent as "book for <subject>" goes to that subject's books
        if msg.files and books is not None and self.is_on("books"):
            out = books.take_book(msg)
            if out:
                msg.reply(out)
                return
        packs = self.modules.get("classpacks")  # a .kurooto-course file: a class pack to review (modules/classpacks.py)
        if msg.files and packs is not None:
            out = packs.take_pack(msg)
            if out is not None:
                if out:
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
        calls = self.modules.get("calls")  # (livefallback) a call that went on as text: what you write is part of it
        if calls is not None and self.is_on("calls") and calls.textcall.takes(msg):
            return
        plain = tidy(text)
        cases = self.modules.get("cases") if self.is_on("cases") else None  # (wrong) Wrong button, taught phrasings
        taught = cases.watch(msg, plain, mods) if cases is not None else None  # (request, slots), "ai" or None
        if taught and taught != "ai":
            self.events.emit("intent", name=taught[0].name, via="taught")
            self.keep.used(self.keep.intent_owner(taught[0].name, mods), "intent", msg.via)
            msg.reply(taught[0].run(msg, taught[1]) or "Done.")
            return
        if plain and not too_complex(plain) and taught != "ai":
            asks = bool(QUESTION.search(plain))
            from kurooto.core import overlay  # (ws5) an add-on's intent classifier goes first (core/overlay.py)

            picked = overlay.classify(self, plain, mods, asks)
            if picked:
                self.events.emit("intent", name=picked[0].name, via="classifier")
                self.keep.used(self.keep.intent_owner(picked[0].name, mods), "intent", msg.via)
                msg.reply(picked[0].run(msg, picked[1]) or "Done.")
                return
            for m in mods:
                for it in m.intents():
                    if asks and not it.questions:
                        continue
                    slots = it.match(plain)
                    if slots is not None:
                        self.events.emit("intent", name=it.name)
                        self.keep.used(m.id, "intent", msg.via)
                        msg.reply(it.run(msg, slots) or "Done.")
                        return
            from kurooto.core import turnon  # a feature that's off would do it: [Turn on] [Not now]

            if turnon.offer(self, msg, plain, mods, asks):
                return
        from kurooto.core import syncall  # "sync everything", and /sync while Notes sync is off (core/syncall.py)

        if syncall.wanted(text) or text.lower().split("@")[0] == "/sync":
            msg.reply(syncall.start(self)[1])
            return
        chat = self.modules.get("chat")
        if chat and chat in mods and (text or msg.files):  # a photo or file comes with it, for the AI to open
            out = chat.ask(msg)
            if out:
                msg.reply(out)
            return
        if msg.files:  # saved (Telegram puts what you send in your notes' inbox), but nothing here reads it
            from kurooto.core import layout

            msg.reply(
                f"Saved to {', '.join(layout.shown(self, f) for f in msg.files)}. To have your AI look at it, turn on "
                "Chat; to have it filed into your notes, turn on Files into notes (Features)."
            )
            return
        msg.reply(
            "I can't answer free text yet: turn on Chat (it uses the AI you picked) in Settings. /help lists "
            "what works now."
        )

    def off_command(self, name: str, mods: list[Module]) -> tuple[Module, Command | None] | None:
        """The feature that's off whose /command this is (with the command), or Skills for one of your skills while
        Skills is off; None otherwise. /sync isn't one: it syncs everything while Notes sync is off."""
        if not name or name in ("sync", "start", "help"):
            return None
        for m in self.modules.values():
            if m in mods:
                continue
            try:
                cmds = m.commands()
            except Exception as e:  # one feature's mistake never hides the others' commands
                self.events.emit("commands_failed", module=m.id, error=str(e)[:200])
                cmds = []
            for c in cmds:
                if c.name == name:
                    return m, c
        sk = self.modules.get("skills")
        if sk is not None and sk not in mods:
            from kurooto.modules.skills import load_skill

            s = load_skill(self, name.replace("_", "-"))
            if s is not None and not s.internal:
                return sk, None
        return None

    def callback(self, data: str) -> str:
        """A button you tapped: "<prefix>:<ref>:<action>"."""
        prefix, ref, act = (data.split(":", 2) + ["", ""])[:3]
        self.notifier.retract(button=data)  # the phone app's copy of that message goes (core/notify.py)
        self.calm.touched(button=data)  # (calm) you tapped it: answered (core/calm.py)
        if prefix == "calm":  # Why? / Less of this / Undo / the monthly suggestion (core/calm.py)
            return self.calm.button(ref, act)
        if prefix == "upd":
            return self.updates.button(ref, act)
        if prefix == "ask":
            return self.ask.button(ref, act)
        if prefix == "health":  # a Fix button (core/health.py)
            return self.health.button(ref, act)
        if prefix == "fixme":  # Ask my AI under /fixme's answer (core/fixme.py)
            from kurooto.core import fixme

            return fixme.button(self, ref, act)
        if prefix == "job":  # a Cancel button under /jobs (core/jobs.py)
            return self.jobs.button(ref, act)
        if prefix == "fgt":  # Forget everything / Keep it under /forget all (core/retention.py)
            from kurooto.core import retention

            return retention.button(self, ref, act)
        if prefix == "inf":  # Undo under something set up from what you said (core/infer.py)
            from kurooto.core import infer

            return infer.undo(self, ref)
        if prefix == "ton":  # Turn on / Not now under a request a feature that's off would do (core/turnon.py)
            from kurooto.core import turnon

            return turnon.button(self, ref, act)
        if prefix == "keep":  # Keep / Quiet / Off under the day-10 and monthly question (core/keep.py)
            return self.keep.button(ref, act)
        for m in self.enabled():
            h = m.callbacks().get(prefix)
            if h:
                self.keep.used(m.id, "button")
                try:
                    return h(ref, act) or "ok"
                except Exception as e:
                    return f"error: {e}"[:190]
        return "that button is from a feature that's off now"

    CORE_HELP = (
        ("q", "open questions I asked you (reply to one to answer it)"),
        ("aboutme", "what I know about you (your profile's In-brief part), and where to edit it"),
        ("health", "what isn't working, with Fix buttons (/health now checks online too)"),
        ("fixme", "what's wrong and what to do, by rules (no AI needed); /fixme <what you see>, /fixme ai explains"),
        ("calm", "messages that come by themselves: today's count and limit"),
        ("why", "why the last message that came by itself came"),
        ("jobs", "what the AI is working on and what waits, with Cancel buttons"),
        ("keep", "what you used of each feature that's on (last 30 days); /keep <feature> offers Quiet and Off"),
        ("inferred", "what was set up from what you said (a project, a class, a meeting), with /inferred undo <id>"),
        ("forget", "forget what I kept of our conversations: /forget 7d (or 2w, 12h), /forget all"),
        ("gists", "one line of what each forgotten call or request decided; /gists <words> finds them"),
        ("help", "this list; /help <word> finds a command or feature, on or off"),
    )

    def help(self, arg: str = "") -> str:
        """/help: every command and instant request of the features that are on, the features that are off, and the
        user wiki for the rest. /help <word>: what matches it, on or off (Kurooto knows all of itself)."""
        from kurooto.update.updater import PAGES

        wiki = f"{PAGES}/wiki/"
        on = self.enabled()
        word = (arg or "").strip().lower()
        if word:
            return self._help_find(word, wiki)
        lines = [f"{self.name}, your assistant. Plain words work; so do these."]
        for m in on:
            cmds = m.help()
            if cmds:
                lines += ["", f"{m.title}:", *cmds]
        lines += ["", "Kurooto itself:", *(f"/{n}  {h}" for n, h in self.CORE_HELP)]
        if not self.is_on("notes_sync"):
            lines.append("/sync  sync everything that's on (Classroom, calendar, research, notes brain)")
        said = []
        for m in on:
            try:
                said += [i.description for i in m.intents()]
            except Exception as e:  # a feature's intents failing must not take /help down
                self.events.emit("module_failed", module=m.id, error=f"in /help: {e}"[:300])
        if said:
            lines += ["", "Understood at once, in plain words:", *(f"- {d}" for d in dict.fromkeys(said))]
        off = [m.title for m in self.modules.values() if m not in on and m.title]
        if off:
            lines += ["", f"Off right now ({len(off)}): " + ", ".join(off) + ". /help <name> says what one does."]
        if not self.is_on("chat"):
            lines.append("(Chat is off, so free text isn't sent to an AI.)")
        lines += ["", f"Everything, with examples, settings and fixes: {wiki}"]
        return "\n".join(lines)

    def _help_find(self, word: str, wiki: str) -> str:
        on = self.enabled()
        hits: list[str] = []
        for n, h in self.CORE_HELP:
            if word in n or word in h.lower():
                hits.append(f"/{n}  {h}")
        for m in self.modules.values():
            state = "" if m in on else ' (off: turn it on in Features, or say "turn on ' + m.title.lower() + '")'
            about = f"{m.title} {m.description}".lower()
            try:
                cmds = [c for c in m.commands() if word in c.name or word in c.help.lower()]
                said = [i.description for i in m.intents() if word in i.description.lower()]
            except Exception:
                cmds, said = [], []
            if word in about or cmds or said:
                hits.append(f"{m.title}{state}: {m.description}")
                hits += [f"  /{c.name}  {c.help}" for c in cmds]
                hits += [f"  - {d}" for d in said]
        if not hits:
            return f'Nothing here matches "{word}". The user wiki has everything: {wiki}'
        return "\n".join([f'About "{word}":', *hits, "", f"More in the user wiki: {wiki}"])

    def _job_done(self, job, outcome: str, err: BaseException | None) -> None:
        if outcome in ("error", "missing-action"):
            why = str(err) if err else f"no action {job.action!r}"  # job.last_result is the run before this one
            self.events.emit("job_failed", key=job.key, outcome=outcome, error=why[:300])

    def close(self) -> None:
        if self._stop is not None:  # the assistant itself is stopping (not a `kurooto` command): last words
            self.jobs.halt()  # running AI requests stop where they are; they run again at the next start
            for m in self.enabled():
                down = getattr(m, "shutdown", None)  # e.g. Notes sync sends up what's left
                if down:
                    try:
                        down()
                    except Exception as e:
                        self.events.emit("module_failed", module=m.id, error=f"at shutdown: {e}"[:300])
        self.scheduler.close()
        self.jobs.close()
