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
(calls/chat.py: Google Drive with Drive upload on, else a sealed copy on your call line). With Telegram and
notify.app_chat on, a file goes to both (files.to_app, 0.9.0).
A channel that keeps its own copy of a question (the phone app) also registers a retract handler: when that question
is dealt with anywhere (answered on Telegram, a button tapped, expired), retract() takes its copy down.
A channel that can change a message it sent (Telegram) registers an edit handler: Calm folds several notices of one
kind a day (updates.done) into the first one with edit().
With Brain on (0.8.14), a message that came by itself also bids at the workspace's door after Brain's gate
(mind/workspace.py): it goes when it wins, at a natural break, and its decision record says what it expects to come of
it (mind/records.py). The chat's copy of such a message gets a "Why this?" button too (Calm's Why?, answered with what
the gate and the door did).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from kurooto.core import desktop
from kurooto.core.config import register_defaults
from kurooto.mind import gate, records, workspace

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
        # 0.9.0, follow me (Face presence): while you've stepped away, desktop_kinds also go to the phone app (the
        # desktop pop-up still waits for you); off: as before
        "follow_me": False,
        "desk_silent_phone": False,  # ...and while you're at the desk, Telegram's copy comes silently (needs follow_me)
        "desk_first": False,  # ...and while you're at the desk, every message also pops up here (needs follow_me)
        # someone else at the desk (a second face looking, another voice): the pop-up says only "A message from
        # Kurooto"; the full text is on your phone, Telegram and the dashboard as usual
        "guests_hold": False,
        "desktop_retract": True,  # a pop-up for a question closes once it's answered anywhere (Linux)
        # 0.9.0: while the phone is on Do Not Disturb (its dnd sense, Brain), what isn't urgent waits as during focus
        # and calls Kurooto places by itself wait; the alarm, your reminders, approvals and close deadlines don't
        "respect_phone_dnd": False,
    },
)

GENERIC = "A message from Kurooto: the full text is on your phone, Telegram and the dashboard."
DESK_S = 120  # Face presence saw you at this computer this recently: you're at the desk

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
    # (0.9.0) the same item as Brain's workspace names it: deadline:<id>, class:<subject> or quiz:<deadline id>,
    # kept apart from `item` so Less of this keeps reading the bare id: it counts double at the door while the item is
    # on Brain's mind, and Calm's recheck (core/calm.py: still) reads it; the gate's stage-10 rule and fatigue use it
    # only with mind.workspace.item_fatigue on
    ws_item: str | None = None
    due: str | None = None  # a deadline's due time (ISO): less than 12 hours away, it always comes
    rid: str | None = None  # its record in Calm's ledger (set by Calm)
    extra: list | None = None  # Telegram-only rows (Why? / Less of this)
    # Brain's gate (mind/gate.py): set only when Brain's read of you made this message quieter; the receipt says how
    state_read: dict | None = None
    before: Any = None  # the message as it was before that (Undo sends it)
    purpose: str | None = (
        None  # what Brain's model of you was used for: level, timing or correct_fact (mind/tom/model.py)
    )
    # Brain's door (mind/workspace.py, 0.8.14): numbers for this message's bid, {"stake", "urgency", "surprise"} each
    # 0..1, when a feature knows better than the default its Calm reason gives (a surprise check-in, say)
    bid: dict | None = None
    silent: bool = False  # (0.9.0) Telegram's copy without a sound (notify.desk_silent_phone)


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
        self.shown: list[tuple] = []  # (0.9.0) desktop pop-ups that can be closed: (map_kind, map_ref, data, id)
        # (0.9.1) told after each message went out, with it: Voice says some aloud at the desk (voice.speak.messages)
        self.on_deliver: list[Callable[[Message], None]] = []

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
        try:
            self._desktop_retract(map_kind, map_ref, button)
        except Exception as e:
            self.app.events.emit("notify_failed", channel="desktop", error=f"retract: {e}"[:200])

    def _desktop_retract(self, map_kind, map_ref, button) -> None:
        """(0.9.0, notify.desktop_retract) The desktop's own copies: a pop-up showing is closed, and one held while
        you're away (Face presence) won't show."""
        if not self.app.settings.get("notify.desktop_retract"):
            return

        def gone(key) -> bool:
            k, ref, data = key
            if button and button in data:
                return True
            return bool(map_kind and map_ref is not None and k == map_kind and str(ref) == str(map_ref))

        face = (getattr(self.app, "modules", None) or {}).get("face")
        if face is not None and hasattr(face, "drop_held"):
            face.drop_held(gone)
        keep = []
        for k, ref, data, nid in self.shown:
            if gone((k, ref, data)):
                desktop.close(nid)
                self.app.events.emit("notify_retracted", channel="desktop")
            else:
                keep.append((k, ref, data, nid))
        self.shown = keep

    def send(self, text: str, **kw) -> Any:
        """Deliver now (or queue it during focus). Returns the Telegram message id when there is one. Calm may hold
        it for the evening bundle (or drop a kind you stopped): then None."""
        msg = Message(str(text), **kw)
        try:  # (Brain, 0.8.14) Kurooto is asleep: what it starts by itself waits for the morning (mind/sleep.py)
            from kurooto.mind import sleep

            if sleep.hold(self.app, msg):
                return None
        except Exception as e:  # never loses a message: it goes as before
            self.app.events.emit("mind_sleep_failed", error=f"hold: {type(e).__name__}"[:60])
        verdict, msg, _receipt = self.gate(msg)  # Brain's gate, when it's on (mind/gate.py): only ever quieter
        if verdict != "send":
            return None
        msg = self.temperament(msg)  # (Brain, 0.8.16) its temperament sets how long its own words are
        go, door = workspace.door(self.app, msg)  # (Brain, 0.8.14) it bids at the door; only winners go, at a break
        if not go:
            return None
        calm = getattr(self.app, "calm", None)
        if calm is not None and calm.decide(msg) != "send":
            return None
        gate.sent(self.app, msg)  # it went out: it counts toward the hour, the day and the touches
        try:  # (Brain, 0.8.8) not-a-pest: it waits an hour for an answer; the talk reward's "its own ping" fact
            from kurooto.mind import pest

            pest.sent(self.app, msg)
        except Exception:
            pass
        try:  # (Brain, stage 05) a promise in what it said is written down, to be kept or owned up to
            from kurooto.mind import promises

            promises.seen(self.app, msg.text, msg.why)
            if msg.why == "asked":  # (0.9.0, mind.promises.answers) a promise in an answer to you counts too
                promises.said(self.app, msg.text, "answer")
        except Exception:
            pass
        if msg.why and msg.why != "asked":  # one it starts by itself: its decision record (Brain, mind/records.py)
            expect = records.expectation(self.app, msg)  # 0.8.14: what it expects to come of it (a reply, done in 2 h)
            did = records.decide(self.app, f"message:{msg.kind}", scored_reason=msg.why, source="rules", expect=expect)
            records.track(self.app, did, msg, expect, door)
        return self.release(msg)

    def temperament(self, msg: Message) -> Message:
        """(Brain, 0.8.16: mind.register.templates) a message that came by itself, not exempt and not an answer,
        keeps the register's number of sentences (mind/register.py: shorten). Never raises: on any failure it goes as
        it was."""
        if not msg.why or msg.why == "asked" or msg.reply_to:
            return msg
        try:
            from kurooto.mind import register

            if not register.templates_on(self.app) or workspace.exempt(self.app, msg):
                return msg
            text = register.shorten(msg.text, register.sentences(self.app), msg.buttons)
        except Exception as e:
            self.app.events.emit("mind_register_failed", error=f"{type(e).__name__}"[:60])
            return msg
        if text == msg.text:
            return msg
        self.app.events.emit("mind_register_shortened", why=str(msg.why)[:40], cut=len(msg.text) - len(text))
        return replace(msg, text=text)

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
        if (
            not msg.urgent
            and msg.kind not in URGENT_KINDS
            and (self.app.availability.focus_until() or self._phone_dnd(msg))
        ):
            with open(self.queue_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({**msg.__dict__, "buttons": msg.buttons}, ensure_ascii=False, default=str) + "\n")
            self.app.events.emit("notify_queued", kind=msg.kind)
            return None
        return self._deliver(msg)

    def _phone_dnd(self, msg: Message) -> bool:
        """(0.9.0, notify.respect_phone_dnd) The phone is on Do Not Disturb and this one can wait (not exempt by
        Calm's rules: the alarm, your reminders, approvals, a deadline under 12 hours, urgent)."""
        if not self.app.settings.get("notify.respect_phone_dnd") or msg.why == "asked" or msg.reply_to:
            return False
        calm = getattr(self.app, "calm", None)
        try:
            if calm is not None and calm.exempt(msg.why, msg.kind, msg.urgent, msg.due):
                return False
            from kurooto.mind.senses import phone

            return phone.dnd_on(self.app)
        except Exception:
            return False

    def flush_dnd(self) -> int:
        """Do Not Disturb ended (or the phone stopped saying so): what waited goes now, unless focus time still holds
        it. Called when the phone's readings come in, and by Calm's five-minute tick."""
        if self.app.availability.focus_until() or not self.queue_file.exists():
            return 0
        try:
            from kurooto.mind.senses import phone

            if phone.dnd_on(self.app):
                return 0
        except Exception:
            pass
        return self.flush_queue()

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
        if self._desk_quiet(msg):  # (0.9.0) at the desk: Telegram's copy without a sound
            tmsg = replace(tmsg, silent=True)
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
                # (with Telegram, a file is Telegram's document, and a link in the chat too with files.to_app, 0.9.0)
                if self.app.app_main() or not msg.file or s.get("files.to_app"):
                    self.channels["chat"](tmsg if self.app.app_main() else records.with_why(self.app, msg))
            except Exception as e:
                self.app.events.emit("notify_failed", channel="chat", error=str(e)[:200])
        no_other_channel = ref is None and "app" not in self.channels
        desk_first = s.get("notify.follow_me") and s.get("notify.desk_first") and self.at_desk()  # (0.9.0)
        if s.get("notify.desktop") and (
            msg.kind in (s.get("notify.desktop_kinds") or []) or no_other_channel or desk_first
        ):
            self._desktop(msg)
        self.app.events.emit("notified", kind=msg.kind, delivered=ref is not None)
        calm = getattr(self.app, "calm", None)
        if calm is not None and msg.rid:
            calm.delivered(msg.rid, ref)
        for fn in list(self.on_deliver):  # (0.9.1) in addition to every copy above, never instead of one
            try:
                fn(msg)
            except Exception as e:
                self.app.events.emit("notify_failed", channel="on_deliver", error=f"{type(e).__name__}"[:100])
        return ref

    def _to_chat(self, msg: Message) -> Any:
        ref = None
        try:
            ref = self.channels["chat"](msg)
        except Exception as e:
            self.app.events.emit("notify_failed", channel="chat", error=str(e)[:200])
        s = self.app.settings
        if s.get("notify.desktop") and msg.kind in (s.get("notify.desktop_kinds") or []):
            self._desktop(msg)
        self.app.events.emit("notified", kind=msg.kind, delivered=ref is not None, via="chat")
        return None  # not a Telegram message id

    def _desktop(self, msg: Message) -> None:
        """A desktop pop-up, or held while you've stepped away from the desk (face.away.hold_desktop): Face presence
        shows what waited when you're back (at most 20, the oldest dropped)."""
        s = self.app.settings
        face = (getattr(self.app, "modules", None) or {}).get("face")
        away = getattr(self.app, "away_from_desk", None)
        data = tuple(str(b[1]) for row in msg.buttons or [] for b in row if isinstance(b, (list, tuple)) and len(b) > 1)
        key = (msg.map_kind, msg.map_ref, data)
        gone = away is not None and away()
        if gone:
            self._follow(msg)  # (0.9.0, notify.follow_me) away: a copy on the phone app as well
        if face is not None and gone and s.get("face.away.hold_desktop"):
            face.hold_desktop(msg.title or self.app.name, msg.text, msg.urgent, key=key)
            return
        title, text = msg.title or self.app.name, msg.text
        if s.get("notify.guests_hold") and self.guests_here():  # (0.9.0) someone else could read it here
            title, text = self.app.name, GENERIC
            self.app.events.emit("notify_generic", channel="desktop")
        desktop.last_id = ""
        ok = desktop.notify(title, text, urgent=msg.urgent)
        nid = desktop.last_id
        if ok and nid and (msg.map_kind or data):
            self.shown = [*self.shown[-49:], (msg.map_kind, msg.map_ref, data, nid)]

    def _follow(self, msg: Message) -> None:
        """(0.9.0, notify.follow_me) Away from the desk: a message the desktop would show also goes to the phone app,
        when the app doesn't already get its kind (notify.app_kinds)."""
        s = self.app.settings
        if not s.get("notify.follow_me") or "app" not in self.channels or msg.kind in (s.get("notify.app_kinds") or []):
            return
        try:
            self.channels["app"](msg)
            self.app.events.emit("notify_followed", kind=msg.kind)
        except Exception as e:
            self.app.events.emit("notify_failed", channel="app", error=str(e)[:200])

    def at_desk(self) -> bool:
        """Face presence saw you at this computer in the last DESK_S seconds. False when it can't tell (off)."""
        import time

        face = (getattr(self.app, "modules", None) or {}).get("face")
        try:
            seen = face.desk_seen_at() if face is not None and self.app.is_on("face") else None
        except Exception:
            return False
        return seen is not None and time.time() - seen < DESK_S

    def _desk_quiet(self, msg: Message) -> bool:
        s = self.app.settings
        if not (s.get("notify.follow_me") and s.get("notify.desk_silent_phone")):
            return False
        return not msg.urgent and msg.kind not in URGENT_KINDS and self.at_desk()

    def guests_here(self) -> bool:
        """Someone besides you is at the desk: two faces close and looking (Face presence), or a voice that isn't
        yours lately (Voice ID). Counts only, never who."""
        from kurooto.core import biometric, nearby

        try:
            return nearby.facing_many(self.app) or biometric.voice_others(self.app)
        except Exception:
            return False

    def _recheck(self, msg: Message) -> Message | None:
        """(0.9.0) A message that waited, with what changed meanwhile (core/calm.py: recheck); as it was on any
        failure."""
        try:
            from kurooto.core.calm import recheck

            return recheck(self.app, msg)
        except Exception:
            return msg

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
            m = self._recheck(Message(**d))  # (0.9.0) what changed during focus, said with it
            if m is not None:
                self._deliver(m)
                n += 1
        return n
