"""Getting something to you: Telegram, the phone app and the desktop, as you've set them up.

During focus time, anything that isn't urgent waits in a queue and is delivered when focus ends.
A message that comes by itself carries its reason (why=, a reason id from core/calm.py; "asked" for an answer to
something you asked or did), the setting that controls it, and what it's about. Calm (core/calm.py) decides first: it
may hold it for the evening bundle or, if you stopped that kind, drop it. Its Why? / Less of this buttons go to
Telegram only; the phone app and the desktop get the plain message.
Channels are registered by the modules that provide them (Telegram, the phone app and its chat); the desktop is
built in. An answer to something you wrote in the phone app's chat (reply_to "app:<id>") goes back to that chat only.
Without Telegram (0.5.18: it's optional when the phone app is paired), the chat is where everything else goes, as with
notify.app_chat on, Why? / Less of this included; a file (a long answer, `kurooto send`) comes there as a link
(calls/chat.py: Google Drive with Drive upload on, else a sealed copy on your call line).
A channel that keeps its own copy of a question (the phone app) also registers a retract handler: when that question
is dealt with anywhere (answered on Telegram, a button tapped, expired), retract() takes its copy down.
A channel that can change a message it sent (Telegram) registers an edit handler: Calm folds several notices of one
kind a day (updates.done) into the first one with edit().
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from kurooto.core import desktop
from kurooto.core.config import register_defaults
from kurooto.mind import gate, records

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
        "app_chat": False,  # Kurooto's own messages (not app_kinds) also go to the app's chat; always without Telegram
    },
)

URGENT_KINDS = ("approval", "call")


def counts(data: str) -> bool:
    """A counting button ("dl:<id>:+1", one more part of a problem set done): its message stays where it is (on the
    phone too) so it can be tapped again; any other button takes its message off your phones."""
    return isinstance(data, str) and data.rpartition(":")[2].startswith("+")


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
    tail: str | None = None  # the text's own last line, to show quietly (the run receipt): Telegram puts it in italics
    # the envelope (core/calm.py): why it came by itself, which setting controls it, what it's about
    why: str | None = None  # a reason id ("deadlines.reminder"), or "asked" for an answer to you; None: not recorded
    setting: str | None = None  # the setting it comes from, when more precise than the reason's own
    about: str | None = None  # the deadline, class or item that triggered it, in words (Why? says it)
    item: str | None = None  # that item's id (a subject, a deadline), for Less of this
    due: str | None = None  # a deadline's due time (ISO): less than 12 hours away, it always comes
    rid: str | None = None  # its record in Calm's ledger (set by Calm)
    extra: list | None = None  # Telegram-only rows (Why? / Less of this)
    # Brain's gate (mind/gate.py): set only when Brain's read of you made this message quieter; the receipt says how
    state_read: dict | None = None
    before: Any = None  # the message as it was before that (Undo sends it)


Sender = Callable[[Message], Any]  # returns the channel's message id, or None
Retractor = Callable[[str | None, str | None, str | None], Any]  # (map_kind, map_ref, button data)
Editor = Callable[[Any, Message], Any]  # (the channel's message id, the new message): truthy when changed


class Notifier:
    def __init__(self, app: App):
        self.app = app
        self.channels: dict[str, Sender] = {}
        self.retractors: dict[str, Retractor] = {}
        self.editors: dict[str, Editor] = {}
        self.queue_file = app.paths.state / "focus-queue.jsonl"

    def register(self, name: str, send: Sender, retract: Retractor | None = None, edit: Editor | None = None) -> None:
        self.channels[name] = send
        if retract:
            self.retractors[name] = retract
        if edit:
            self.editors[name] = edit

    def unregister(self, name: str) -> None:
        self.channels.pop(name, None)
        self.retractors.pop(name, None)
        self.editors.pop(name, None)

    def edit(self, ref, msg: Message) -> bool:
        """Change a Telegram message Kurooto sent (its id) to this one, Why? / Less of this included. False when
        there's no Telegram or it didn't take the change (the message is gone, the network is down)."""
        fn = self.editors.get("telegram")
        if fn is None or ref is None:
            return False
        tmsg = replace(msg, buttons=[*(msg.buttons or []), *msg.extra], extra=None) if msg.extra else msg
        try:
            return bool(fn(ref, tmsg))
        except Exception as e:
            self.app.events.emit("notify_failed", channel="telegram", error=f"edit: {e}"[:200])
            return False

    def retract(self, map_kind: str | None = None, map_ref: str | None = None, button: str | None = None) -> None:
        """Something Kurooto asked was dealt with: channels take their copy of it down. Name it by the map_kind and
        map_ref it was sent with, or by the data of a button that was tapped."""
        for name, fn in list(self.retractors.items()):
            try:
                fn(map_kind, map_ref, button)
            except Exception as e:
                self.app.events.emit("notify_failed", channel=name, error=f"retract: {e}"[:200])

    def send(self, text: str, **kw) -> Any:
        """Deliver now (or queue it during focus). Returns the Telegram message id when there is one. Calm may hold
        it for the evening bundle (or drop a kind you stopped): then None."""
        msg = Message(str(text), **kw)
        verdict, msg, _receipt = self.gate(msg)  # Brain's gate, when it's on (mind/gate.py): only ever quieter
        if verdict != "send":
            return None
        calm = getattr(self.app, "calm", None)
        if calm is not None and calm.decide(msg) != "send":
            return None
        gate.sent(self.app, msg)  # it went out: it counts toward the hour, the day and the touches
        try:  # (Brain, stage 05) a promise in what it said is written down, to be kept or owned up to
            from kurooto.mind import promises

            promises.seen(self.app, msg.text, msg.why)
        except Exception:
            pass
        if msg.why and msg.why != "asked":  # one it starts by itself: its decision record (Brain, mind/records.py)
            records.decide(self.app, f"message:{msg.kind}", scored_reason=msg.why, source="rules")
        return self.release(msg)

    def gate(self, msg: Message):
        """("send" | "hold" | "block", the message maybe changed, its receipt): Brain's gate. Never raises: with it
        off, or on any failure, the message goes as it was."""
        try:
            return gate.check(self.app, msg)
        except gate.GateBreach:
            raise
        except Exception as e:
            self.app.events.emit("mind_gate_failed", error=f"{type(e).__name__}: {e}"[:200])
            return "send", msg, None

    def release(self, msg: Message) -> Any:
        """Past Calm: queue it during focus, else deliver it now (Calm's Send them as they come uses this too)."""
        if not msg.urgent and msg.kind not in URGENT_KINDS and self.app.availability.focus_until():
            with open(self.queue_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({**msg.__dict__, "buttons": msg.buttons}, ensure_ascii=False, default=str) + "\n")
            self.app.events.emit("notify_queued", kind=msg.kind)
            return None
        return self._deliver(msg)

    def _deliver(self, msg: Message) -> Any:
        s = self.app.settings
        ref = None
        to_app = isinstance(msg.reply_to, str) and msg.reply_to.startswith("app:")  # (calls/chat.py)
        if to_app and "chat" in self.channels:
            return self._to_chat(msg)
        if to_app:  # the chat is gone meanwhile (Phone calls turned off): Telegram gets it as a new message
            msg = replace(msg, reply_to=None)
        pres = getattr(self.app, "presence", None)  # the network is down: Telegram gets it later (core/presence.py)
        tmsg = replace(msg, buttons=[*(msg.buttons or []), *msg.extra], extra=None) if msg.extra else msg
        if "telegram" in self.channels and not (pres is not None and pres.hold(tmsg)):
            try:
                ref = self.channels["telegram"](tmsg)
                if pres is not None and ref is not None:
                    pres.net_ok("telegram")
            except Exception as e:
                self.app.events.emit("notify_failed", channel="telegram", error=str(e)[:200])
                if pres is not None:
                    pres.failed(tmsg, e)  # kept for later if it was the network
        if "app" in self.channels and msg.kind in (s.get("notify.app_kinds") or []):
            try:
                self.channels["app"](msg)
            except Exception as e:
                self.app.events.emit("notify_failed", channel="app", error=str(e)[:200])
        elif "chat" in self.channels and msg.kind != "call" and (self.app.app_main() or s.get("notify.app_chat")):
            try:  # without Telegram the chat is your channel: Calm's Why? / Less of this come there too, and files
                if self.app.app_main() or not msg.file:  # (with Telegram, a file is Telegram's document)
                    self.channels["chat"](tmsg if self.app.app_main() else msg)
            except Exception as e:
                self.app.events.emit("notify_failed", channel="chat", error=str(e)[:200])
        no_other_channel = ref is None and "app" not in self.channels
        if s.get("notify.desktop") and (msg.kind in (s.get("notify.desktop_kinds") or []) or no_other_channel):
            desktop.notify(msg.title or self.app.name, msg.text, urgent=msg.urgent)
        self.app.events.emit("notified", kind=msg.kind, delivered=ref is not None)
        calm = getattr(self.app, "calm", None)
        if calm is not None and msg.rid:
            calm.delivered(msg.rid, ref)
        return ref

    def _to_chat(self, msg: Message) -> Any:
        ref = None
        try:
            ref = self.channels["chat"](msg)
        except Exception as e:
            self.app.events.emit("notify_failed", channel="chat", error=str(e)[:200])
        s = self.app.settings
        if s.get("notify.desktop") and msg.kind in (s.get("notify.desktop_kinds") or []):
            desktop.notify(msg.title or self.app.name, msg.text, urgent=msg.urgent)
        self.app.events.emit("notified", kind=msg.kind, delivered=ref is not None, via="chat")
        return None  # not a Telegram message id

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
