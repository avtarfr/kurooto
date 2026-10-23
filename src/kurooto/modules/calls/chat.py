"""The phone app as a chat with Kurooto, beside Telegram (0.5.16): for places where Telegram is blocked or little
used. What you type in the app goes phone → your call line → this computer, and is handled exactly like a Telegram
message (App.handle, via "app"): commands, plain-English requests, Chat's AI. The answers, including the AI's later
ones (jobs answer with reply_to "app:<your message's id>"), go back the way questions do: this computer → your call
line → your phones (sealed ntfy for Android, an empty Web Push and a fetch for the iPhone app). Buttons under an
answer work as on Telegram: the phone sends the button's number, never its data, and App.callback does the rest.

With notify.app_chat on, Kurooto's own messages (reminders, results, info...) also appear in the chat, besides
Telegram; questions and approvals stay under "Waiting for you" (phone.py). Without Telegram (0.5.18: it's optional)
the chat is where they all go, as if app_chat were on.

Files (0.5.18): the chat carries no files, so where Telegram would get a document (a long answer, `kurooto send`, the
AI's send_file) the chat gets a link: Google Drive with Drive upload on (a copy deleted after drive_upload.temp_days),
else a sealed copy on your call line for FILE_HOURS (line.py "f1": the key is only in the link's #fragment; the
call line's file page opens it in the phone's browser), else a plain note that it stays on this computer, with its
path. Files you share from the phone are listed in <state>/calls/shared.json, so "summarise the PDF I just sent"
finds them (modules/chat.py).

The Android app seals what you type with the ntfy key (as it does answers); the iPhone app sends it over HTTPS with
its device key. Each message carries a random nonce and the time it was sent, so it's used once. While this
computer is off, it waits on the call line (the phone outbox) and comes here in order when it's back.

The call line keeps the chat's last 50 messages, each for at most 3 days, so a phone can catch up with the
computer off; this computer keeps the last 100 (for buttons and replies) in <state>/calls/chat.json.
"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.lock import Lock
from kurooto.core.notify import counts
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
# files for the chat, kept sealed on the call line: the largest, how long, and the size of each part sent there
FILE_MAX = 10 * 2**20
FILE_HOURS = 24
FILE_PART = 384 * 1024  # base64 keeps each message to the call line under 1 MB
SHARED_KEEP = 20  # files shared from the phone remembered for the chat's AI


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
        """The `chat` channel: an answer to what you wrote in the app, or (notify.app_chat, or no Telegram) any
        message. A file comes as a link, a moment later (send_file)."""
        re_id = msg.reply_to[len(PREFIX) :] if answers_app(msg) else ""
        if msg.file:
            self.send_file(Path(msg.file), msg.text or "", re_id=re_id if ID.fullmatch(re_id) else "")
            return None
        if not (msg.text or "").strip():
            return None
        mapped = (msg.map_kind, msg.map_ref) if msg.map_kind else None
        m = self.say(msg.text, msg.buttons, re_id=re_id if ID.fullmatch(re_id) else "", title=msg.title or "",
                     mapped=mapped)  # fmt: skip
        return PREFIX + m["id"]

    # --------------------------------------------------------------------------------------- files
    def send_file(self, path: Path, caption: str = "", re_id: str = "", wait: bool = False) -> tuple[bool, str]:
        """A file for you in the chat, as a link (made in the background: an upload can take a while). (ok, what
        to say now)."""
        path = Path(path)
        if not path.is_file():
            return False, f"There's no file {path.name}."
        t = threading.Thread(target=self._file_now, args=(path, caption, re_id), daemon=True, name="chat-file")
        t.start()
        if wait:
            t.join()
        return True, f"{path.name} comes to the phone app's chat as a link."

    def _file_now(self, path: Path, caption: str, re_id: str) -> None:
        head = caption.strip()
        head = f"{head}\n\n" if head and head != path.name else ""
        drive = self.app.modules.get("drive_upload")  # (google_drive.py) your own Drive, when it's set up
        if drive is not None and self.app.is_on("drive_upload") and drive.ready()[0]:
            try:
                link, said = drive.put(path, temporary=True)
                self.say(head + said, [[("Open in Drive", {"url": link})]], re_id=re_id)
                return
            except Exception as e:  # the call line next
                self.app.events.emit("drive_upload_failed", error=f"for the chat: {type(e).__name__}"[:200])
        link, why = self.to_line(path)
        if link:
            self.app.events.emit("file_sent", via="line", bytes=path.stat().st_size)
            self.say(
                f"{head}{path.name}: tap Open to read or save it on this phone (the link works {FILE_HOURS} hours).",
                [[("Open " + _clip(path.name, 30), {"url": link})]],
                re_id=re_id,
            )
            return
        page = (jload(self.app.paths.state / "web.json", {}) or {}).get("url") or ""
        self.say(
            f"{head}{path.name} stays on your computer ({why}): {path}"
            + (f". On the computer, the dashboard is at {page}" if page else "")
            + ". Turn on Drive upload (Features) to get files here as a Google Drive link.",
            re_id=re_id,
        )

    def to_line(self, path: Path) -> tuple[str, str]:
        """Put a sealed copy of a file on your call line for FILE_HOURS: (the link, "") or ("", why not). The key is
        made here and only goes in the link's #fragment (line.py f1)."""
        c = self.calls.connector
        if not self.calls.worker_url() or c.ws is None:
            return "", "your call line isn't connected right now"
        size = path.stat().st_size
        if size > FILE_MAX:
            return "", f"it's {size / 2**20:.0f} MB; your call line carries files up to {FILE_MAX // 2**20} MB"
        key = os.urandom(32)
        blob = line.seal_f1(key, path.read_bytes())
        fid = uuid.uuid4().hex
        parts = [blob[i : i + FILE_PART] for i in range(0, len(blob), FILE_PART)]
        for i, part in enumerate(parts):
            try:
                res = c.admin_wait(
                    "file-put", timeout=60, fid=fid, part=i, parts=len(parts), size=len(blob), hours=FILE_HOURS,
                    data=base64.b64encode(part).decode(),
                )  # fmt: skip
            except Exception as e:
                return "", f"your call line didn't take it: {type(e).__name__}"
            if res.get("error"):
                return "", str(res.get("note") or res["error"])[:200]
        frag = urllib.parse.urlencode({"i": fid, "k": line.b64url(key), "n": path.name[:120]})
        return f"{self.calls.worker_url()}/file#{frag}", ""

    def shared(self, path: Path, note: str = "") -> None:
        """A file you shared from the phone landed here: remembered, so the chat's AI knows what "the PDF I just sent"
        is."""
        f = self.calls.dir / "shared.json"
        with Lock(self.app.paths.state, "calls-shared"):
            rows = [r for r in (jload(f, []) or []) if isinstance(r, dict)]
            rows.append({"name": path.name, "path": str(path), "note": note[:200], "at": int(time.time())})
            jsave(f, rows[-SHARED_KEEP:])

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
        if out.strip() and out.strip().lower() != "ok":  # under a +1's answer, the +1 again (and on the notification)
            again = [[(m["buttons"][int(n)]["label"], target)]] if counts(target) else None
            self.say(out, again, re_id=mid)
        return 200, {"ok": True, "note": _clip(out, 300)}
