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

0.8.10, the chat as a full replacement for Telegram (each part a switch in calls.*): separate chats ("sessions",
sessions.py; chat_sessions) each with its own AI context; replies that bring the quoted message to the AI; files both
ways shown inline (chat_files_inline: a file for the phone carries `file` with its sealed link, which the app opens
itself; a file from the phone goes up first as a shared file, then the message names it); editing, deleting and
pinning messages (chat_edit); "working"/"idle" while an AI request for a chat runs; and the being's sealed requests
from the paired Android phone (settings.set, module, note.get), applied exactly as the dashboard applies them and
answered sealed. Messages without `session` (older app versions) belong to "main". Every message carries its
`session`; this computer keeps the last 100 of each chat. The protocol: docs/wiki/dev/calls-and-phone.md.
"""

from __future__ import annotations

import base64
import contextlib
import json
import mimetypes
import os
import re
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.notify import counts
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Incoming
from kurooto.modules.calls import line
from kurooto.modules.calls.sessions import DESK, MAIN

if TYPE_CHECKING:
    from kurooto.core.notify import Message
    from kurooto.modules.calls import Calls

KEEP = 100  # messages kept here, for buttons and replies
KEEP_S = 7 * 86400
TEXT_MAX = 4000  # what you type
SAY_MAX = 6000  # what Kurooto says (the call line keeps this much too)
BUTTONS_MAX = 6  # buttons the app shows under one message; (0.8.17) more go on in a follow-up message
MORE = "More choices for the message above:"
ID = re.compile(r"[0-9a-f]{16}")
PREFIX = "app:"  # an Incoming's message_id, and the reply_to of what answers it
# files for the chat, kept sealed on the call line: the largest, how long, and the size of each part sent there
FILE_MAX = 10 * 2**20
FILE_HOURS = 24
FILE_PART = 384 * 1024  # base64 keeps each message to the call line under 1 MB
SHARED_KEEP = 20  # files shared from the phone remembered for the chat's AI
EDIT_S = 15 * 60  # your messages can be edited this long after they were sent
QUOTE_MAX = 200  # a reply shows this much of the message it answers
FID = re.compile(r"[\w-]{1,40}")  # a shared file's id (the upload's own)
SESSION_OPS = ("session.new", "session.rename", "session.delete", "session.pin", "read", "sync")
MSG_OPS = ("msg.edit", "msg.delete", "msg.pin")
BEING_OPS = (
    "settings.set",
    "module",
    "note.get",
    "voice.mute",
    "voice.room",  # (0.9.2) Today's Room card: the room mode
)  # the being on the phone (Views): only sealed, only now
OFF_NOW = "Your computer was off when you sent that, so it wasn't done. Try again now that it's on."
# (0.9.0) bedside mode opening or closing on a paired phone reaches this computer as a flag (no sensor): the event
# phone_bedside and calls/bedside.json; what may follow it (sleep, Calm's night) has its own switches, off
register_defaults("phone", {"bedside": {"signal": True}})
# (0.9.1, L81) feedback buttons (Wrong, Calm's Why? and Less of this): marked "quiet", so the app shows them as small
# text buttons after the message's own, never as its first, filled one
QUIET_BUTTON = re.compile(r"^(?:wrong:[^:]+:x|calm:[^:]+:(?:why|less))$")
WORKING_S = 3 * 3600  # a chat shows "working" at most this long without hearing the request ended
BOARD_KEEP = 20  # (0.9.1) the board talk box's requests whose answers are still to come, and answers kept for the
BOARD_KEEP_S = 12 * 3600  # "while you were away" summary, at most this many and this long


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
        self.working: dict[str, tuple[str, float]] = {}  # AI requests running for a chat: job -> (session, since)
        self._api = None  # the dashboard's own handlers, for the being's requests (web/api.py)
        # (0.9.1) the board's talk box: its AI requests still running (job -> what you typed, when), and the answers
        # that came (for the Desk chat and the "while you were away" summary), in memory only
        self.board_jobs: dict[str, tuple[str, float]] = {}
        self.board_answers: list[dict] = []

    @property
    def sessions(self):
        return self.calls.sessions

    def _lock(self):
        return Lock(self.app.paths.state, "calls-chat")

    def _load(self) -> list[dict]:
        t, msgs = time.time(), (jload(self.file, {}) or {}).get("msgs") or []
        return [m for m in msgs if isinstance(m, dict) and t - m.get("at", 0) < KEEP_S]

    @staticmethod
    def _trim(msgs: list[dict]) -> list[dict]:
        """The last KEEP of each chat."""
        seen: dict[str, int] = {}
        out = []
        for m in reversed(msgs):
            sid = m.get("session") or MAIN
            seen[sid] = seen.get(sid, 0) + 1
            if seen[sid] <= KEEP:
                out.append(m)
        return out[::-1]

    def _add(self, m: dict) -> None:
        with self._lock():
            msgs = self._load()
            msgs.append(m)
            jsave(self.file, {"msgs": self._trim(msgs)})
        self.live("msg", msg=self.public(m))

    def live(self, kind: str, **fields) -> None:
        """Tell the dashboard's open pages (its Chat page, web/chat_api.py): {"t": "chat", "kind": "msg" | "sessions" |
        "status" | "waiting", ...}. Only to this computer's own pages, and not at all with look.chat_page off."""
        live = getattr(self.app, "live", None)
        if live is None or self.app.settings.get("look.chat_page") is False:
            return
        try:
            live.push({"t": "chat", "kind": kind, **fields})
        except Exception:
            pass

    def _find(self, mid: str) -> dict | None:
        return next((m for m in self._load() if m["id"] == mid), None) if mid else None

    def _update(self, mid: str, change) -> dict | None:
        """Change one message in place (change(m) edits it); the message, or None if it isn't here."""
        with self._lock():
            msgs = self._load()
            m = next((x for x in msgs if x["id"] == mid), None)
            if m is None:
                return None
            change(m)
            m.pop("pushed", None)  # the call line hears the change (flush sends it again if it doesn't)
            jsave(self.file, {"msgs": msgs})
        self.live("msg", msg=self.public(m), update=True)
        return m

    def drop_session(self, sid: str) -> None:
        """A chat was deleted: its messages here go."""
        with self._lock():
            msgs = self._load()
            jsave(self.file, {"msgs": [m for m in msgs if (m.get("session") or MAIN) != sid]})
        self.live("sessions")

    def _session_of(self, mid: str) -> str:
        m = self._find(mid)
        return (m or {}).get("session") or MAIN

    @staticmethod
    def public(m: dict) -> dict:
        out = {k: v for k, v in m.items() if not k.startswith("_") and k != "pushed"}
        out.setdefault("session", MAIN)  # kept before 0.8.10: Kurooto's own chat
        return out

    # -------------------------------------------------------------------------------------- saying
    def say(
        self,
        text: str,
        buttons: list | None = None,
        re_id: str = "",
        title: str = "",
        mapped=None,
        session: str = "",
        file: dict | None = None,
    ) -> dict:
        """Put a message from Kurooto in the chat and send it to your phones: in `session`, else the chat of the
        message it answers (re_id), else Kurooto's own ("main"). file: {name, size, mime, url} shown inline."""
        shown, data = [], []
        for row in buttons or []:
            for label, target in row:
                if isinstance(target, dict) and str(target.get("url", "")).startswith("https://"):
                    shown.append({"label": _clip(label, 40), "url": target["url"]})
                    data.append("")
                elif isinstance(target, str):
                    b = {"label": _clip(label, 40)}
                    if QUIET_BUTTON.match(target):  # (0.9.1) Wrong, Why?, Less of this: the app shows them quietly
                        b["quiet"] = True
                    shown.append(b)
                    data.append(target)
        more = (shown[BUTTONS_MAX:], data[BUTTONS_MAX:])  # (0.8.17) more than the app shows: in a follow-up
        m = {
            "id": uuid.uuid4().hex[:16],
            "from": "kurooto",
            "text": _clip(text, SAY_MAX),
            "at": int(time.time()),
            "buttons": shown[:BUTTONS_MAX],
            "reply": bool(mapped),  # a reply to it goes to the feature that sent it (as on Telegram)
            "_data": data[:BUTTONS_MAX],  # stays here: the phone answers with the button's number
        }
        if title:
            m["title"] = _clip(title, 120)
        if re_id:
            m["re"] = re_id
        if mapped:
            m["_map"] = [mapped[0], str(mapped[1] or "")]
        sid = session or (self._session_of(re_id) if re_id else MAIN)
        if sid != MAIN and self.sessions.get(sid) is None:  # the chat was deleted meanwhile: Kurooto's own
            sid = MAIN
        m["session"] = sid
        if file:
            m["file"] = file
        self._add(m)
        self._push(m)
        self.sessions.touch(sid, m)
        if more[0]:  # the rest of the buttons, BUTTONS_MAX a message, each answering the same feature
            rows = [[(b["label"], {"url": b["url"]} if "url" in b else d)] for b, d in zip(*more, strict=True)]
            self.say(MORE, rows, re_id=re_id, mapped=mapped, session=sid)
        return m

    def send(self, msg: Message) -> str | None:
        """The `chat` channel: an answer to what you wrote in the app, or (notify.app_chat, or no Telegram) any
        message. A file comes as a link, a moment later (send_file)."""
        re_id = msg.reply_to[len(PREFIX) :] if answers_app(msg) else ""
        if msg.file:
            # a copy beside Telegram's (files.to_app): made before this returns, since a sender may delete the file
            # once it's sent (an add-on's picture lives in memory only while it's sent); FILE_MAX bounds the wait
            path = Path(msg.file)
            mirror = not self.app.app_main() and path.is_file() and path.stat().st_size <= FILE_MAX
            self.send_file(path, msg.text or "", re_id=re_id if ID.fullmatch(re_id) else "", wait=mirror)
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
            inline = None
            if self.calls.setting("chat_files_inline"):  # the app shows it in place; the button stays for older apps
                mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                inline = {"name": path.name[:120], "size": path.stat().st_size, "mime": mime, "url": link}
            self.say(
                f"{head}{path.name}: tap Open to read or save it on this phone (the link works {FILE_HOURS} hours).",
                [[("Open " + _clip(path.name, 30), {"url": link})]],
                re_id=re_id,
                file=inline,
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

    def shared(self, path: Path, note: str = "", fid: str = "", session: str = MAIN) -> None:
        """A file you shared from the phone landed here: remembered, so the chat's AI knows what "the PDF I just sent"
        is; one sent into a chat (fid: the upload's id) is found by the message that names it."""
        f = self.calls.dir / "shared.json"
        with Lock(self.app.paths.state, "calls-shared"):
            rows = [r for r in (jload(f, []) or []) if isinstance(r, dict)]
            row = {"name": path.name, "path": str(path), "note": note[:200], "at": int(time.time())}
            if fid:
                row.update(fid=fid, session=session)
            rows.append(row)
            jsave(f, rows[-SHARED_KEEP:])

    def _shared_file(self, fid: str) -> dict | None:
        rows = jload(self.calls.dir / "shared.json", []) or []
        return next((r for r in reversed(rows) if isinstance(r, dict) and fid and r.get("fid") == fid), None)

    def _push(self, m: dict) -> bool:
        def done(res):
            if res and not res.get("error"):
                self._mark_pushed(m["id"])

        changed = bool(m.get("edited") or m.get("deleted") or "pinned" in m)  # the line changes its copy
        return self.calls.connector.admin_later(
            "chat-say", then=done, msg=self.public(m), assistant=self.app.name, update=changed
        )

    def status(self, sid: str, state: str, job: str = "") -> bool:
        """`kind: "status"` for one chat (working while an AI request for it runs): to the phones connected to the
        call line, not kept, no notification. The dashboard's Chat page hears it too."""
        self.live("status", session=sid, state=state)
        return self.calls.connector.admin_later("chat-status", session=sid, state=state, job=job)

    # ------------------------------------------------------------------------------- the Desk chat (0.9.1)
    def desk_turn(self, you: str, reply: str, how: str = "spoken") -> bool:
        """(calls.chat_desk) One turn said at the desk (how: "spoken", "live", "typed" on the board's talk box) and its
        answer, into the Desk chat: kept here, on the dashboard's Chat page, and sealed to the call line like any chat
        message, quietly (no notification on the phone). Your turns only: the callers leave guests out. Its AI context
        (modules/chat.py) gets the turn too, so a message typed in the Desk chat follows on. True when it went in."""
        you, reply = str(you or "").strip(), str(reply or "").strip()
        if not you or not reply or not self.sessions.ensure_desk():
            return False
        t = int(time.time())
        mine = {"id": uuid.uuid4().hex[:16], "from": "you", "text": _clip(you, TEXT_MAX), "at": t, "session": DESK,
                "how": how}  # fmt: skip
        said = {"id": uuid.uuid4().hex[:16], "from": "kurooto", "text": _clip(reply, SAY_MAX), "at": t, "buttons": [],
                "reply": False, "session": DESK, "quiet": True, "_data": []}  # fmt: skip
        for m in (mine, said):
            self._add(m)
            self._push(m)
        self.sessions.touch(DESK, mine)
        self.sessions.touch(DESK, said)
        chat = self.app.modules.get("chat")
        if chat is not None and hasattr(chat, "session_turn"):
            try:
                chat.session_turn(DESK, you, reply)
            except Exception as e:
                self.app.events.emit("chat_desk_failed", error=f"{type(e).__name__}"[:80])
        self.app.events.emit("chat_desk", how=how)
        return True

    def board_job(self, jid: str, text: str) -> None:
        """(0.9.1) The board's talk box started an AI request: its answer goes to the Desk chat and the "while you were
        away" summary when it ends, even if the page that asked is closed by then."""
        if not jid:
            return
        self.board_jobs[jid] = (str(text or "")[:TEXT_MAX], time.time())
        while len(self.board_jobs) > BOARD_KEEP:
            self.board_jobs.pop(next(iter(self.board_jobs)))

    def _board_done(self, jid: str) -> None:
        got = self.board_jobs.pop(jid, None)
        if got is None:
            return
        job = self.app.jobs.get(jid)
        if job is None:
            return
        answer = str(job.result or "").strip() if job.status == "ok" else "That request failed (the jobs tab says why)."
        if not answer:
            return
        t = time.time()
        self.board_answers = [a for a in self.board_answers if t - a["at"] < BOARD_KEEP_S][-(BOARD_KEEP - 1) :]
        self.board_answers.append({"at": t, "asked": got[0][:200], "answer": answer[:SAY_MAX], "job": jid})
        self.desk_turn(got[0], answer, "typed")

    def answers_since(self, since: float) -> list[dict]:
        """(0.9.1) The board talk box's answers that came at or after `since` (time.time()): {at, asked, answer}."""
        return [dict(a) for a in self.board_answers if a["at"] >= since]

    def on_event(self, rec: dict) -> None:
        """(core/events.py subscribe) An AI request for a chat ended: it's idle again. A chat switch changed: the
        phones hear (the sessions message carries the switches)."""
        if rec.get("kind") == "setting_changed" and str(rec.get("key") or "").startswith("calls.chat_"):
            self.sessions.push()
            return
        if rec.get("kind") not in ("job_done", "job_ended", "job_cancelled"):
            return
        if str(rec.get("job") or "") in self.board_jobs:
            try:
                self._board_done(str(rec.get("job")))
            except Exception as e:  # never in the way of the event feed
                self.app.events.emit("chat_desk_failed", error=f"{type(e).__name__}"[:80])
        got = self.working.pop(str(rec.get("job") or ""), None)
        if got:
            self.status(got[0], "idle", str(rec.get("job")))
        t = time.time()
        for jid, (sid, since) in list(self.working.items()):  # one whose end was never heard (a restart)
            if t - since > WORKING_S:
                self.working.pop(jid, None)
                self.status(sid, "idle", jid)

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
        if self.sessions.dirty:  # the chats' list too
            self.sessions.push()
        return sum(bool(self._push(m)) for m in late)

    # ------------------------------------------------------------------------------------ from you
    def _busy(self, v) -> tuple[int, dict]:
        """(0.9.0) The phone app is in another call (a WhatsApp or Meet call) until `until` (ms), at most 3 hours;
        0 clears it. Kept apart from Kurooto's own calls (core/availability.py: phone_busy_until)."""
        import datetime as dt
        import time as _t

        until = (v or {}).get("until") if isinstance(v, dict) else v
        if isinstance(until, bool) or not isinstance(until, (int, float)):
            return 400, {"ok": False, "note": "No time in that."}
        av = self.app.availability
        if until <= 0 or until / 1000 <= _t.time():
            av.set_phone_busy(None)
        else:
            av.set_phone_busy(dt.datetime.fromtimestamp(min(until / 1000, _t.time() + 3 * 3600)))
        self.app.events.emit("phone_busy", on=until > 0)
        return 200, {"ok": True}

    def take(self, body: dict, queued: bool = False) -> tuple[int, dict]:
        """A chat message from a phone, passed on by the call line (now, or from its outbox: queued): {"device",
        "at", "id", and "k1" (sealed by the Android app) or the fields themselves (the iPhone app)}. The fields: "ts"
        (ms), "n" (a random nonce), and "text" (with "to": the id of Kurooto's message it replies to, optional), or
        "button" (its number) and "msg" (the id of Kurooto's message it's under), or "today" ({"id", "do"}: Done or
        +1 on a deadline on the app's Today screen, today.py). 0.8.10: "session" (a chat; none: "main"), "reply" (any
        message it replies to), "file" ({fid, name, mime, size}: a file shared first, named here), or "op" with
        "args" instead of text (session and message changes, the being's requests)."""
        mid = str(body.get("id") or "")
        if not ID.fullmatch(mid):
            return 400, {"ok": False, "note": "That message had no id."}
        fields = body
        sealed = bool(body.get("k1"))
        if sealed:
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
        if "busy" in fields:  # (0.9.0) the phone is in another call until then (ms; 0: not any more), no number
            return self._busy(fields["busy"])
        if "senses" in fields:  # the phone's senses, aggregated and sealed on the phone (mind/senses/phone.py)
            from kurooto.mind.senses import phone as senses_phone

            return senses_phone.ingest(self.app, fields["senses"])
        if "button" in fields:
            return self._button(str(fields.get("msg") or ""), fields["button"])
        if "today" in fields:  # Done or +1 on the app's Today screen (today.py)
            return self.calls.today.act(fields["today"])
        if fields.get("op"):
            return self._op(str(fields["op"]), fields, sealed, queued, str(body.get("device") or ""))
        sid = self.sessions.norm(fields.get("session"))
        if sid is None:
            return 400, {"ok": False, "note": "That message's chat isn't one."}
        text = str(fields.get("text") or "").strip()[:TEXT_MAX]
        sent = fields.get("file") if isinstance(fields.get("file"), dict) else None
        path = None
        if sent:
            if not self.calls.setting("chat_files_inline"):
                return 403, {"ok": False, "note": "Files in the chat are off (Settings: calls.chat_files_inline)."}
            row = self._shared_file(str(sent.get("fid") or "")) if FID.fullmatch(str(sent.get("fid") or "")) else None
            path = Path(row["path"]) if row else None
            if path is None or not path.is_file():
                return 404, {"ok": False, "note": "That file didn't reach your computer. Send it again."}
        if not text and path is None:
            return 400, {"ok": False, "note": "The message was empty."}
        to_id = str(fields.get("reply") or fields.get("to") or "")
        return self._yours(mid, sid, text, to_id, path, sent, bool(fields.get("voice")) and path is not None)

    def typed(self, text: str, session: str = "", reply: str = "", files: list | None = None) -> tuple[int, dict]:
        """A message typed on the dashboard's Chat page (web/chat_api.py, behind the dashboard's key): handled exactly
        as one typed in the app (the same session, its AI context, replies), and your phones see it as yours. files
        (0.9.0): [(path, card)] attached on the page (chat_api.attached), sent with it as a phone's file is."""
        sid = self.sessions.norm(session)
        if sid is None or (sid != MAIN and self.sessions.get(sid) is None):
            return 404, {"ok": False, "note": "There's no such chat."}
        text = str(text or "").strip()[:TEXT_MAX]
        if not text and not files:
            return 400, {"ok": False, "note": "The message was empty."}
        return self._yours(uuid.uuid4().hex[:16], sid, text, str(reply or ""), on="dashboard", more=files or [])

    def press(self, mid: str, n) -> tuple[int, dict]:
        """A button under one of Kurooto's messages, tapped on the dashboard's Chat page: as a tap in the app."""
        return self._button(str(mid or ""), n)

    def thread(self, sid: str) -> list[dict]:
        """One chat's messages, oldest first, as the phones get them (the buttons' data stays here)."""
        return [self.public(m) for m in self._load() if (m.get("session") or MAIN) == sid]

    def _yours(self, mid: str, sid: str, text: str, to_id: str, path: Path | None = None, sent: dict | None = None,
               voice: bool = False, on: str = "", more: list | None = None) -> tuple[int, dict]:  # fmt: skip
        """Your message (from the app, or the dashboard's Chat page: on="dashboard"): kept, sent to your phones, and
        handled like a Telegram message in its chat. path and sent: the file a phone shared with it; more: [(path,
        card)], the files attached on the dashboard (the message's `file` is the first, as the app shows one, and
        `files` lists them all when there are more)."""
        to = self._find(to_id)
        reply_to = {"kind": to["_map"][0], "ref": to["_map"][1]} if to and to.get("_map") else None
        mine = {"id": mid, "from": "you", "text": text, "at": int(time.time()), "session": sid}
        quote = None
        if to:
            mine["re"] = to["id"]
            quote = {"id": to["id"], "from": to.get("from", ""), "text": _clip(to.get("text") or "", QUOTE_MAX)}
            mine["quote"] = quote
        files = [(path, sent or {})] if path is not None else []
        files += list(more or [])
        cards = [
            {
                "name": _clip(c.get("name") or p.name, 120),
                "size": int(c.get("size") or p.stat().st_size),
                "mime": str(c.get("mime") or mimetypes.guess_type(p.name)[0] or "")[:100],
            }
            for p, c in files
        ]
        if cards:
            mine["file"] = cards[0]
        if len(cards) > 1:
            mine["files"] = cards
        self._add(mine)
        self._push(mine)  # your other phones see it too
        self.sessions.touch(sid, mine)
        said: list[dict] = []

        def respond(t, buttons=None):
            m = self.say(str(t), buttons, re_id=mid, session=sid)
            said.append(self.public(m))
            return PREFIX + m["id"]

        if voice:  # a voice note: what was heard becomes the message, as on Telegram (modules/voice_notes.py)
            vn = self.app.modules.get("voice_notes")
            if vn is None or not self.app.is_on("voice_notes"):
                respond("Voice notes are off. Turn on Voice notes in Settings (it uses your free Gemini key).")
                return 200, {"ok": True, "id": mid, "said": said}
            try:
                heard = vn.transcribe(path)
            except Exception as e:
                respond(f"Couldn't make out that voice note: {e}"[:300])
                return 200, {"ok": True, "id": mid, "said": said}
            respond(f"Heard: {heard[:600]}")
            text, files = (text + "\n" + heard).strip(), []

        self.app.events.emit(
            "phone_chat", chars=len(text), **({"files": len(files)} if files else {}), **({"on": on} if on else {})
        )
        inc = Incoming(
            text,
            via="app",
            message_id=PREFIX + mid,
            files=[p for p, _ in files],
            reply_to=reply_to,
            voice=voice,
            respond=respond,
            session=sid,
            quote={"from": quote["from"], "text": quote["text"]} if quote and not reply_to else None,
        )
        self.app.handle(inc)
        jid = str(getattr(inc, "job", "") or "")
        if jid:  # an AI request for this chat: "working" till it ends (on_event)
            self.working[jid] = (sid, time.time())
            self.status(sid, "working", jid)
        return 200, {"ok": True, "id": mid, "said": said}

    # ----------------------------------------------------------------------------------------- ops
    def change(self, op: str, args: dict) -> tuple[int, dict]:
        """A chat or a message changed on the dashboard's Chat page: the app's own session and message ops (never the
        being's requests, which only the paired phone makes)."""
        if op in SESSION_OPS:
            return self._session_op(op, args)
        if op in MSG_OPS:
            return self._msg_op(op, args)
        return 400, {"ok": False, "op": op[:20], "note": "The Chat page can't do that."}

    def _op(self, op: str, fields: dict, sealed: bool, queued: bool, device: str = "") -> tuple[int, dict]:
        """A change rather than a message. Its arguments are in "args" (or, the ones that aren't "id", beside it)."""
        args = {k: v for k, v in fields.items() if k not in ("id", "ts", "n", "op", "args")}
        if isinstance(fields.get("args"), dict):
            args.update(fields["args"])
        self.app.events.emit("phone_chat_op", op=op[:20])
        if op == "bedside":
            return self._bedside(bool(args.get("on")), sealed, queued)
        if op == "place_names":
            return self._place_names(args.get("names"), sealed)
        if op in BEING_OPS:
            return self._being(op, args, sealed, queued, device)
        if op in SESSION_OPS:
            return self._session_op(op, args)
        if op in MSG_OPS:
            return self._msg_op(op, args)
        return 400, {"ok": False, "op": op[:20], "note": "This computer doesn't know that yet. Update Kurooto."}

    def _bedside(self, on: bool, sealed: bool, queued: bool) -> tuple[int, dict]:
        """(0.9.0, phone.bedside.signal) A paired phone opened or closed bedside mode. One kept on the line while this
        computer was off is stale: dropped. Kept as {on, at} in calls/bedside.json, and the event phone_bedside."""
        if not sealed:
            return 403, {"ok": False, "op": "bedside", "note": "Only your paired Android phone can do that."}
        if queued or not self.app.settings.get("phone.bedside.signal"):
            return 200, {"ok": False, "op": "bedside"}
        jsave(self.calls.dir / "bedside.json", {"on": on, "at": time.time()})
        self.app.events.emit("phone_bedside", on=on)
        try:  # (0.9.1, mind.sleep.follow_bedside, off) Brain's night may start with it
            from kurooto.mind import sleep

            sleep.bedside(self.app, on)
        except Exception as e:
            self.app.events.emit("mind_sleep_failed", error=f"bedside: {type(e).__name__}"[:60])
        if not on:  # (0.9.1, notify.calm.night_bedside) what waited for bedside mode to close goes now
            with contextlib.suppress(Exception):
                self.app.calm.tick()
        return 200, {"ok": True, "op": "bedside"}

    def _place_names(self, names, sealed: bool) -> tuple[int, dict]:
        """(0.9.1, reminders.place_names) The names of the places saved on a paired phone (names only, never where
        they are), for matching a place you name in a reminder (modules/reminders.py). Kept in calls/place-names.json
        while the switch is on; with it off they're dropped and any kept are deleted."""
        f = self.calls.dir / "place-names.json"
        if not sealed:
            return 403, {"ok": False, "op": "place_names", "note": "Only your paired Android phone can do that."}
        s = self.app.settings
        if not (s.get("reminders.places") and s.get("reminders.place_names")):
            f.unlink(missing_ok=True)
            return 200, {"ok": False, "op": "place_names"}
        if not isinstance(names, list):
            return 400, {"ok": False, "op": "place_names", "note": "No names in that."}
        keep: list[str] = []
        for n in names[:50]:
            n = " ".join(str(n).split())[:40] if isinstance(n, str) else ""
            if n and n.lower() not in {k.lower() for k in keep}:
                keep.append(n)
        jsave(f, {"names": keep, "at": time.time()})
        self.app.events.emit("phone_place_names", n=len(keep))  # how many, never which
        return 200, {"ok": True, "op": "place_names"}

    def bedside(self, max_age_h: float = 12) -> bool:
        """Is bedside mode open on a paired phone (said within max_age_h)? For what may follow it later."""
        st = jload(self.calls.dir / "bedside.json", {}) or {}
        return bool(st.get("on")) and time.time() - float(st.get("at") or 0) < max_age_h * 3600

    def _session_op(self, op: str, a: dict) -> tuple[int, dict]:
        ss = self.sessions
        if op == "sync":
            ss.push()
            return 200, {"ok": True, "op": op, **ss.message()}
        sid = str(a.get("session") or "")
        if op == "read":
            ok, note = ss.read(sid or MAIN, str(a.get("upto") or ""))
        elif not ss.on():
            ok, note = False, "Separate chats are off (Settings: calls.chat_sessions)."
        elif op == "session.new":
            ok, note = ss.new(sid, str(a.get("title") or ""))
        elif op == "session.rename":
            ok, note = ss.rename(sid, str(a.get("title") or ""))
        elif op == "session.delete":
            ok, note = ss.delete(sid)
        else:  # session.pin
            ok, note = ss.pin(sid, bool(a.get("on")))
        return (200 if ok else 400), {"ok": ok, "op": op, "session": sid, "note": note, "sessions": ss.listing()}

    def _msg_op(self, op: str, a: dict) -> tuple[int, dict]:
        def no(note: str, code: int = 400):
            return code, {"ok": False, "op": op, "note": note}

        if not self.calls.setting("chat_edit"):
            return no("Editing, deleting and pinning messages is off (Settings: calls.chat_edit).", 403)
        target = str(a.get("target") or "")
        m = self._find(target)
        if m is None:
            return no("That message isn't on this computer any more.", 404)
        if op == "msg.pin":

            def change(x):
                x["pinned"] = bool(a.get("on"))

        elif m.get("from") != "you":
            return no("Only your own messages can be changed everywhere; delete it on this phone.", 403)
        elif op == "msg.edit":
            text = str(a.get("text") or "").strip()[:TEXT_MAX]
            if not text:
                return no("The new text was empty.")
            if m.get("deleted"):
                return no("That message was deleted.")
            if time.time() - float(m.get("at") or 0) > EDIT_S:
                return no(f"Messages can be edited for {EDIT_S // 60} minutes after they're sent.")

            def change(x):
                x.update(text=text, edited=True)

        else:  # msg.delete: everywhere (this phone alone is the app's own)

            def change(x):
                for k in ("file", "files", "quote", "buttons"):
                    x.pop(k, None)
                x.update(text="", deleted=True)

        m = self._update(target, change)
        if m is None:
            return no("That message isn't on this computer any more.", 404)
        self._push(m)
        return 200, {"ok": True, "op": op, "msg": self.public(m)}

    # --------------------------------------------------------------------------------- the being
    def _being(self, op: str, a: dict, sealed: bool, queued: bool, device: str = "") -> tuple[int, dict]:
        """The being on the phone (Views): a setting, a feature on or off, a note's text. Only from the paired
        Android phone (sealed), only while this computer is on (not from the call line's outbox); applied by the
        dashboard's own handlers (web/api.py: POST /api/settings, modules/enable|disable, GET /api/note), and
        answered sealed: {"ok", "op", "s1"} for the phone that asked alone (it gave the line its key; the line can't
        open it), else {"ok", "op", "k1"} with the chat's key."""
        if not sealed:
            return 403, {"ok": False, "op": op, "note": "Only your paired Android phone can do that."}
        if queued:
            return 409, {"ok": False, "op": op, "note": OFF_NOW}
        if self._api is None:
            from kurooto.web.api import Api

            self._api = Api(self.app)
        api = self._api
        if op == "settings.set":
            key = str(a.get("key") or "")
            code, out = api.post("settings", {"key": key, "value": a.get("value")})
            ok = code == 200 and bool(out.get("ok"))
            res = {"ok": ok, "key": key, "value": self.app.settings.get(key) if ok else None,
                   "note": "Saved." if ok else str(out.get("error") or "That didn't work.")}  # fmt: skip
        elif op == "module":
            mid, on = str(a.get("id") or a.get("module") or ""), bool(a.get("on"))
            if mid not in self.app.modules:
                res = {"ok": False, "id": mid, "note": "There's no such feature."}
            elif mid == "calls" and not on:  # it's what connects the phone: off only on the computer
                res = {"ok": False, "id": mid, "on": True, "note": "Phone calls connects this phone; turn it off on "
                       "your computer's dashboard."}  # fmt: skip
            else:
                if on:
                    code, out = api.post("modules/enable", {"ids": [mid]})
                    r = (out.get("results") or {}).get(mid) or {}
                else:
                    code, out = api.post("modules/disable", {"id": mid})
                    r = out
                res = {"ok": code == 200 and bool(r.get("ok")), "id": mid, "on": self.app.is_on(mid),
                       "note": str(r.get("message") or r.get("error") or "")}  # fmt: skip
        elif op == "voice.mute":  # the being's Mute: through the dashboard's own POST /api/voice/mute (flips it)
            code, out = api.post("voice/mute", {} if a.get("on") is None else {"on": bool(a.get("on"))})
            res = (
                {"ok": True, "muted": bool(out.get("muted")), "note": str(out.get("message") or "")}
                if code == 200
                else {"ok": False, "note": "Voice isn't on this computer (Features: Voice: talk and listen)."}
            )
        elif op == "voice.room":  # (0.9.2) the room mode, through the dashboard's own POST /api/voice/room
            code, out = api.post("voice/room", {"mode": str(a.get("mode") or ""), "by": "phone"})
            room = out.get("room") or {}
            res = (
                {
                    "ok": bool(out.get("ok")),
                    "mode": room.get("mode", ""),
                    "until_hm": room.get("until_hm", ""),
                    "note": str(out.get("message") or ""),
                }  # fmt: skip
                if code == 200
                else {"ok": False, "note": "Voice isn't on this computer (Features: Voice: talk and listen)."}
            )
        else:  # note.get
            nid = str(a.get("id") or a.get("note") or "")
            code, out = api.get("note", {"id": nid})
            res = (
                {"ok": True, "id": nid, "text": out.get("text", ""), "mtime": out.get("mtime")}
                if code == 200
                else {"ok": False, "id": nid, "note": "There's no such note."}
            )
        res["op"] = op
        self.app.events.emit("phone_being", op=op, ok=bool(res["ok"]))
        text = json.dumps(res)
        pub = self._phone_key(device)
        if pub:
            try:
                return 200, {"ok": bool(res["ok"]), "op": op, "s1": line.seal_s1(pub, text)}
            except ValueError:
                pass
        return 200, {
            "ok": bool(res["ok"]),
            "op": op,
            "k1": line.seal_k1(self.app.secrets.get("calls.ntfy_key") or "", text),
        }

    def _phone_key(self, device: str) -> str:
        """The public key the phone that asked gave the line (lidsafe, Today and views seal for it), or ""."""
        if not device:
            return ""
        try:
            devs = self.calls.connector.admin_wait("devices", timeout=10).get("devices") or []
        except Exception:
            return ""
        return next(
            (str(d.get("seal") or "") for d in devs if str(d.get("id")) == device and d.get("kind") == "android"), ""
        )

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
