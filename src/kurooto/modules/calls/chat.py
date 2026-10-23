"""The phone app as a chat with Kurooto, beside Telegram (0.5.16): for places where Telegram is blocked or little
used. What you type in the app goes phone → your call line → this computer, and is handled exactly like a Telegram
message (App.handle, via "app"): commands, plain-English requests, Chat's AI. The answers, including the AI's later
ones (jobs answer with reply_to "app:<your message's id>"), go back the way questions do: this computer → your call
line → your phones (sealed ntfy for Android, an empty Web Push and a fetch for the iPhone app). Buttons under an
answer work as on Telegram: the phone sends the button's number, never its data, and App.callback does the rest.

With notify.app_chat on, Kurooto's own messages (reminders, results, info...) also appear in the chat, besides
Telegram; questions and approvals stay under "Waiting for you" (phone.py).

The Android app seals what you type with the ntfy key (as it does answers); the iPhone app sends it over HTTPS with
its device key. Each message carries a random nonce and the time it was sent, so it's used once. While this
computer is off, it waits on the call line (the phone outbox) and comes here in order when it's back.

The call line keeps the chat's last 50 messages, each for at most 3 days, so a phone can catch up with the
computer off; this computer keeps the last 100 (for buttons and replies) in <state>/calls/chat.json.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import TYPE_CHECKING

from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Incoming
from kurooto.modules.calls import line

if TYPE_CHECKING:
    from kurooto.core.notify import Message
    from kurooto.modules.calls import Calls

KEEP = 100  # messages kept here, for buttons and replies
KEEP_S = 7 * 86400
TEXT_MAX = 4000  # what you type
SAY_MAX = 6000  # what Kurooto says (the call line keeps this much too)
ID = re.compile(r"[0-9a-f]{16}")
PREFIX = "app:"  # an Incoming's message_id, and the reply_to of what answers it


def _clip(s: str, n: int) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def answers_app(msg: Message) -> bool:
    """This message answers something you wrote in the phone app's chat."""
    return isinstance(msg.reply_to, str) and msg.reply_to.startswith(PREFIX)


class PhoneChat:
    """The `chat` notify channel (registered by Phone calls) and the messages you type in the phone app."""

    def __init__(self, calls: Calls):
        self.calls = calls
        self.app = calls.app
        self.file = calls.dir / "chat.json"

    def _lock(self):
        return Lock(self.app.paths.state, "calls-chat")

    def _load(self) -> list[dict]:
        t, msgs = time.time(), (jload(self.file, {}) or {}).get("msgs") or []
        return [m for m in msgs if isinstance(m, dict) and t - m.get("at", 0) < KEEP_S]

    def _add(self, m: dict) -> None:
        with self._lock():
            msgs = self._load()
            msgs.append(m)
            jsave(self.file, {"msgs": msgs[-KEEP:]})

    def _find(self, mid: str) -> dict | None:
        return next((m for m in self._load() if m["id"] == mid), None) if mid else None

    @staticmethod
    def public(m: dict) -> dict:
        return {k: v for k, v in m.items() if not k.startswith("_") and k != "pushed"}

    # -------------------------------------------------------------------------------------- saying
    def say(self, text: str, buttons: list | None = None, re_id: str = "", title: str = "", mapped=None) -> dict:
        """Put a message from Kurooto in the chat and send it to your phones."""
        shown, data = [], []
        for row in buttons or []:
            for label, target in row:
                if isinstance(target, dict) and str(target.get("url", "")).startswith("https://"):
                    shown.append({"label": _clip(label, 40), "url": target["url"]})
                    data.append("")
                elif isinstance(target, str):
                    shown.append({"label": _clip(label, 40)})
                    data.append(target)
        m = {
            "id": uuid.uuid4().hex[:16],
            "from": "kurooto",
            "text": _clip(text, SAY_MAX),
            "at": int(time.time()),
            "buttons": shown[:6],
            "reply": bool(mapped),  # a reply to it goes to the feature that sent it (as on Telegram)
            "_data": data[:6],  # stays here: the phone answers with the button's number
        }
        if title:
            m["title"] = _clip(title, 120)
        if re_id:
            m["re"] = re_id
        if mapped:
            m["_map"] = [mapped[0], str(mapped[1] or "")]
        self._add(m)
        self._push(m)
        return m

    def send(self, msg: Message) -> str | None:
        """The `chat` channel: an answer to what you wrote in the app, or (notify.app_chat) any message."""
        if not (msg.text or "").strip():
            return None
        re_id = msg.reply_to[len(PREFIX) :] if answers_app(msg) else ""
        mapped = (msg.map_kind, msg.map_ref) if msg.map_kind else None
        m = self.say(msg.text, msg.buttons, re_id=re_id if ID.fullmatch(re_id) else "", title=msg.title or "",
                     mapped=mapped)  # fmt: skip
        return PREFIX + m["id"]

    def _push(self, m: dict) -> bool:
        def done(res):
            if res and not res.get("error"):
                self._mark_pushed(m["id"])

        return self.calls.connector.admin_later("chat-say", then=done, msg=self.public(m), assistant=self.app.name)

    def _mark_pushed(self, mid: str) -> None:
        with self._lock():
            msgs = self._load()
            for m in msgs:
                if m["id"] == mid:
                    m["pushed"] = True
                    jsave(self.file, {"msgs": msgs})
                    return

    def flush(self) -> int:
        """Send again, in order, what didn't reach the call line (it was down), if from the last hour."""
        t = time.time()
        late = [m for m in self._load() if not m.get("pushed") and t - m.get("at", 0) < 3600]
        return sum(bool(self._push(m)) for m in late)

    # ------------------------------------------------------------------------------------ from you
    def take(self, body: dict) -> tuple[int, dict]:
        """A chat message from a phone, passed on by the call line (now, or from its outbox): {"device", "at", "id",
        and "k1" (sealed by the Android app) or the fields themselves (the iPhone app)}. The fields: "ts" (ms), "n"
        (a random nonce), and "text" (with "to": the id of Kurooto's message it replies to, optional), or "button"
        (its number) and "msg" (the id of Kurooto's message it's under)."""
        mid = str(body.get("id") or "")
        if not ID.fullmatch(mid):
            return 400, {"ok": False, "note": "That message had no id."}
        fields = body
        if body.get("k1"):
            plain = line.open_k1(self.app.secrets.get("calls.ntfy_key") or "", str(body["k1"]))
            try:
                fields = json.loads(plain) if plain else None
            except ValueError:
                fields = None
            if not isinstance(fields, dict) or str(fields.get("id") or "") != mid:
                self.app.events.emit("phone_chat_refused", why="sealed")
                return 400, {"ok": False, "note": "That message couldn't be opened here. Pair the phone again."}
        why = self.calls.phone._spend_nonce(fields, body.get("at"))  # fresh, and used once (phone.py)
        if why:
            self.app.events.emit("phone_chat_refused", why=why)
            return 409, {"ok": False, "note": why.replace("answer", "message")}
        if "button" in fields:
            return self._button(str(fields.get("msg") or ""), fields["button"])
        text = str(fields.get("text") or "").strip()[:TEXT_MAX]
        if not text:
            return 400, {"ok": False, "note": "The message was empty."}
        to = self._find(str(fields.get("to") or ""))
        reply_to = {"kind": to["_map"][0], "ref": to["_map"][1]} if to and to.get("_map") else None
        mine = {"id": mid, "from": "you", "text": text, "at": int(time.time())}
        if to:
            mine["re"] = to["id"]
        self._add(mine)
        self._push(mine)  # your other phones see it too
        said: list[dict] = []

        def respond(t, buttons=None):
            m = self.say(str(t), buttons, re_id=mid)
            said.append(self.public(m))
            return PREFIX + m["id"]

        self.app.events.emit("phone_chat", chars=len(text))
        self.app.handle(Incoming(text, via="app", message_id=PREFIX + mid, reply_to=reply_to, respond=respond))
        return 200, {"ok": True, "id": mid, "said": said}

    def _button(self, mid: str, n) -> tuple[int, dict]:
        m = self._find(mid)
        try:
            target = (m or {}).get("_data", [])[int(n)]
        except (TypeError, ValueError, IndexError):
            target = ""
        if not target:
            return 400, {"ok": False, "note": "That button is out of date."}
        out = str(self.app.callback(target) or "")
        self.app.events.emit("phone_chat_button")
        if out.strip() and out.strip().lower() != "ok":
            self.say(out, re_id=mid)
        return 200, {"ok": True, "note": _clip(out, 300)}
