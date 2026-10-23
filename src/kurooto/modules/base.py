"""What a feature module looks like. Every feature is a module, and every module is off until you turn it on.

A module can provide: Telegram commands, handlers for replies to its messages and for its buttons, plain-English
intents, scheduled jobs (registered in start(), keyed "<module id>:..."), settings with defaults, and a check
that it's set up. Turning a module off cancels its jobs; its data stays unless you choose to delete it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kurooto.app import App


@dataclass
class Incoming:
    """A message from you, from any channel."""

    text: str
    via: str = "telegram"
    message_id: Any = None
    files: list[Path] = field(default_factory=list)
    reply_to: dict | None = None  # {"kind": ..., "ref": ...} when it answers one of Kurooto's messages
    voice: bool = False
    respond: Callable[..., Any] | None = None  # respond(text, buttons=None) -> message id

    def reply(self, text: str, buttons: list | None = None) -> Any:
        buttons = buttons if buttons is not None else getattr(text, "buttons", None)  # an Answer brings its own
        return self.respond(text, buttons=buttons) if self.respond else None


class Answer(str):
    """An intent's answer that comes with buttons (an Undo): it's still the text, and Incoming.reply sends the
    buttons with it, so a request can offer Undo without replying itself."""

    buttons: list | None

    def __new__(cls, text: str, buttons: list | None = None):
        s = super().__new__(cls, text)
        s.buttons = buttons
        return s


@dataclass
class Command:
    name: str  # without the slash
    help: str
    handler: Callable[[Incoming, str], str | None]  # (message, argument text) -> reply text, or None if it replied
    usage: str = ""


@dataclass
class Intent:
    """A plain-English request that runs instantly (no AI needed), e.g. "remind me at 9 to call mum"."""

    name: str
    description: str
    match: Callable[[str], dict | None]  # text -> slots, or None if it isn't this request
    run: Callable[[Incoming, dict], str]
    questions: bool = False  # True: it answers questions ("what's due?"); False: questions go to the AI
    examples: tuple[str, ...] = ()  # what you'd say, as /help shows it ("wake me at 6:45")
    guarded: str = ""  # the "never without a tap" action it performs (core/tap.py), e.g. "alarm.set"


class Module:
    id = ""
    title = ""
    description = ""
    requires: tuple[str, ...] = ()
    # "telegram" in requires means somewhere to talk to you: Telegram or the phone app's chat (app.py:met). True: it
    # works only on Telegram itself (voice messages, files sent to the bot)
    telegram_only = False
    privacy = "Stays on this computer."
    extra = False  # an add-on that comes with Kurooto: in no preset ("Everything" too), listed apart, on only by hand
    heavy = False  # True: its scheduled work waits for the charger when the laptop is on battery ("saver" mode)
    # processes that are this feature's own work, by program name ("ollama") or a piece of the command line
    # ("bots/reply.js"): the dashboard's cell and `kurooto top` show their cpu, memory, uptime and threads, and the
    # cell turns grey and dashed when none is running. Add-ons use it to watch programs Kurooto didn't start.
    processes: tuple[str, ...] = ()
    # True for programs that only run now and then (a backup run, a nightly job): with none running the cell says
    # "idle" (not grey, not dashed), and "running" with the figures while one does. Its health is still health().
    processes_intermittent = False

    def __init__(self, app: App):
        self.app = app

    # what it offers
    def commands(self) -> list[Command]:
        return []

    def callbacks(self) -> dict[str, Callable[[str, str], str]]:
        """Button handlers by prefix: {"rem": fn(ref, action) -> short note shown to you}."""
        return {}

    def replies(self) -> dict[str, Callable[[Incoming, str], str | None]]:
        """Handlers for your replies to messages it sent, by the kind it gave them: {"question": fn(msg, ref)}."""
        return {}

    def intents(self) -> list[Intent]:
        return []

    def help(self) -> list[str]:
        return [f"/{c.name}  {c.help}" for c in self.commands()]

    # lifecycle
    def ready(self) -> tuple[bool, str]:
        """Is it set up enough to run? (False, "what's missing") otherwise."""
        return True, ""

    def start(self) -> None:
        """Register scheduler actions and jobs. Called at startup for every enabled module, and when enabled."""

    def stop(self) -> None:
        self.app.scheduler.cancel_prefix(f"{self.id}:")

    def health(self) -> tuple[bool, str]:
        return self.ready()

    def health_check(self):
        """Its one check for "Kurooto keeps itself working" (core/health.py): a Check, or None. The built-in
        features' checks are in core/health_checks.py; an add-on returns its own."""
        from kurooto.core.health_checks import builtin

        return builtin(self)

    # helpers
    def setting(self, key: str, default=None):
        return self.app.settings.get(f"{self.id}.{key}", default)

    def every(self, name: str, spec: str, action: Callable, payload: dict | None = None, **kw) -> None:
        self.app.scheduler.action(f"{self.id}.{name}", action)
        self.app.scheduler.every(f"{self.id}:{name}", spec, f"{self.id}.{name}", payload, module=self.id, **kw)

    def action(self, name: str, fn: Callable) -> str:
        self.app.scheduler.action(f"{self.id}.{name}", fn)
        return f"{self.id}.{name}"
