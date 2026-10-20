"""Getting something to you: Telegram, the phone app and the desktop, as you've set them up.

During focus time, anything that isn't urgent waits in a queue and is delivered when focus ends.
Channels are registered by the modules that provide them (Telegram, the phone app); the desktop is built in.
A channel that keeps its own copy of a question (the phone app) also registers a retract handler: when that question
is dealt with anywhere (answered on Telegram, a button tapped, expired), retract() takes its copy down.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kurooto.core import desktop
from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "notify",
    {
        "desktop": True,
        "desktop_kinds": ["call", "question", "approval", "deadline", "update"],
        # the phone app: calls ring it, and questions and approvals come with answer buttons. Add "reminder",
        # "deadline", "result" or "info" to get those there too (they still go to Telegram as well).
        "app_kinds": ["call", "question", "approval"],
    },
)

URGENT_KINDS = ("approval", "call")


@dataclass
class Message:
    text: str
    title: str | None = None
    buttons: list | None = None  # [[("label", "callback-data" | {"url": ...}), ...], ...]
    kind: str = "info"  # info | result | reminder | question | approval | deadline | call | update
    urgent: bool = False
    reply_to: Any = None  # channel-specific id of the message this answers
    map_kind: str | None = None  # remember what the sent message is about, for replies and buttons
    map_ref: str | None = None
    file: str | None = None  # a document to attach (long answers)


Sender = Callable[[Message], Any]  # returns the channel's message id, or None
Retractor = Callable[[str | None, str | None, str | None], Any]  # (map_kind, map_ref, button data)


class Notifier:
    def __init__(self, app: App):
        self.app = app
        self.channels: dict[str, Sender] = {}
        self.retractors: dict[str, Retractor] = {}
        self.queue_file = app.paths.state / "focus-queue.jsonl"

    def register(self, name: str, send: Sender, retract: Retractor | None = None) -> None:
        self.channels[name] = send
        if retract:
            self.retractors[name] = retract

    def unregister(self, name: str) -> None:
        self.channels.pop(name, None)
        self.retractors.pop(name, None)

    def retract(self, map_kind: str | None = None, map_ref: str | None = None, button: str | None = None) -> None:
        """Something Kurooto asked was dealt with: channels take their copy of it down. Name it by the map_kind and
        map_ref it was sent with, or by the data of a button that was tapped."""
        for name, fn in list(self.retractors.items()):
            try:
                fn(map_kind, map_ref, button)
            except Exception as e:
                self.app.events.emit("notify_failed", channel=name, error=f"retract: {e}"[:200])

    def send(self, text: str, **kw) -> Any:
        """Deliver now (or queue it during focus). Returns the Telegram message id when there is one."""
        msg = Message(str(text), **kw)
        if not msg.urgent and msg.kind not in URGENT_KINDS and self.app.availability.focus_until():
            with open(self.queue_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({**msg.__dict__, "buttons": msg.buttons}, ensure_ascii=False, default=str) + "\n")
            self.app.events.emit("notify_queued", kind=msg.kind)
            return None
        return self._deliver(msg)

    def _deliver(self, msg: Message) -> Any:
        s = self.app.settings
        ref = None
        pres = getattr(self.app, "presence", None)  # the network is down: Telegram gets it later (core/presence.py)
        if "telegram" in self.channels and not (pres is not None and pres.hold(msg)):
            try:
                ref = self.channels["telegram"](msg)
                if pres is not None and ref is not None:
                    pres.net_ok("telegram")
            except Exception as e:
                self.app.events.emit("notify_failed", channel="telegram", error=str(e)[:200])
                if pres is not None:
                    pres.failed(msg, e)  # kept for later if it was the network
        if "app" in self.channels and msg.kind in (s.get("notify.app_kinds") or []):
            try:
                self.channels["app"](msg)
            except Exception as e:
                self.app.events.emit("notify_failed", channel="app", error=str(e)[:200])
        no_other_channel = ref is None and "app" not in self.channels
        if s.get("notify.desktop") and (msg.kind in (s.get("notify.desktop_kinds") or []) or no_other_channel):
            desktop.notify(msg.title or self.app.name, msg.text, urgent=msg.urgent)
        self.app.events.emit("notified", kind=msg.kind, delivered=ref is not None)
        return ref

    def flush_queue(self) -> int:
        """Deliver what waited during focus (called when focus ends)."""
        try:
            lines = self.queue_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return 0
        self.queue_file.unlink(missing_ok=True)
        n = 0
        for ln in lines:
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            self._deliver(Message(**d))
            n += 1
        return n
