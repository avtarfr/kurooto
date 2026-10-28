"""The dashboard's Chat page (0.8.14, look.chat_page): the phone app's chat on this computer. The same chats
("sessions") and the same messages as the app (modules/calls/chat.py keeps them in <state>/calls/chat.json), the
questions under the app's "Waiting for you" (calls/phone.py), and a box to write in the open chat. What you write
here is handled exactly as a message typed in the app (PhoneChat.typed), a button or an answer goes the same way as a
tap in the app (PhoneChat.press, PhoneApp.act), so a question settles everywhere at once. New messages reach the open
page live as {"t": "chat", ...} on the dashboard's stream (PhoneChat.live).

Everything here is behind the dashboard's key and Host check like the rest of /api; nothing new leaves this computer
(your phones hear what you write and tap through your call line, as they do when you use the app).

Attachments (0.9.0, dashboard.chat_attach): a picture pasted or dropped on the page, or a file picked with its
paperclip, goes up first in parts (chat/upload: the dashboard takes at most 4 MB a request, web/server.py) and is kept
in Kurooto's own state (<state>/chat-files, core/places.py chat_files; never your notes) under a name made here, with
the time and a random id, never a path from the page. Then chat/send names it by that id, and it goes with the
message as a file sent from the phone does (PhoneChat._yours: Incoming.files), so the chat's AI is told where it is
and gets a picture as a picture (modules/chat.py: Task.images). Limits as Telegram's: a file up to 20 MB, at most 10 to
a message. A picture is told by its first bytes, not its name: it's saved with the suffix of what it really is, and a
file named like a picture that isn't one is refused.

GET chat: {on, name, sessions (with unread), working, waiting, switches, attach}. GET chat/thread?session=ID:
{session, msgs}. POST chat/send {session, text, reply?, files?: [id]}, chat/upload {part, parts, size, name, data
(base64), id (after the first part)}, chat/button {msg, n}, chat/answer {item, answer | button | dismiss}, chat/op
{op, ...} (the app's session and message ops: read, session.new / rename / delete / pin, msg.edit / delete / pin)."""

from __future__ import annotations

import base64
import binascii
import mimetypes
import re
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.places import chat_files
from kurooto.core.state import owner_only
from kurooto.providers.openai_compat import PICTURE_TYPES

if TYPE_CHECKING:
    from kurooto.app import App

GETS = ("chat", "chat/thread")
POSTS = ("chat/send", "chat/button", "chat/answer", "chat/op", "chat/upload")
OFF = "The Chat page is off (Settings: look.chat_page)."
ATTACH_OFF = "Attaching files on the Chat page is off (Settings: dashboard.chat_attach)."
FILE_MAX = 20 * 2**20  # one file, at most (what Telegram lets a bot take)
FILES_MAX = 10  # files with one message, at most (a Telegram album)
PART = 2 * 2**20  # each part of an upload: in base64 it stays under the dashboard's 4 MB a request
PART_S = 3600  # an upload left unfinished this long is removed when the next one starts
UID = re.compile(r"[0-9a-f]{16}")
SAVED = re.compile(r"\d{4}-\d\d-\d\d-\d{6}-([0-9a-f]{16})-(.+)")  # how an attached file is named here
HEIF = (b"heic", b"heix", b"hevc", b"heim", b"heis")  # an iPhone's photos (HEIC), by their ftyp brand
NO_CALLS = "The phone app's chat comes with Phone calls: turn it on in Features (Alt+F), then pair the app."


def _calls(app: App):
    """(None, the refusal) or (the Phone calls module, None)."""
    if app.settings.get("look.chat_page") is False:
        return None, (403, {"ok": False, "off": True, "note": OFF})
    calls = app.modules.get("calls")
    if calls is None or not app.is_on("calls"):
        return None, (200, {"ok": False, "on": False, "note": NO_CALLS})
    return calls, None


def unread(msgs: list[dict], read: str) -> int:
    """Kurooto's messages after the last one read (the session's "read": the id the app or this page marked)."""
    ids = [m.get("id") for m in msgs]
    start = ids.index(read) + 1 if read and read in ids else 0
    return sum(1 for m in msgs[start:] if m.get("from") != "you" and not m.get("deleted"))


def get(app: App, path: str, q: dict) -> tuple[int, dict]:
    calls, no = _calls(app)
    if no:
        return no
    pc, ss = calls.chat, calls.sessions
    if path == "chat/thread":
        sid = ss.norm(q.get("session"))
        if sid is None or ss.get(sid) is None:
            return 404, {"ok": False, "note": "There's no such chat."}
        return 200, {"ok": True, "session": sid, "msgs": pc.thread(sid)}
    by: dict[str, list[dict]] = {}
    for m in pc._load():
        by.setdefault(m.get("session") or "main", []).append(m)
    rows = [{**r, "unread": unread(by.get(r["id"], []), r.get("read") or "")} for r in ss.listing()]
    return 200, {
        "ok": True,
        "on": True,
        "name": app.name or "Kurooto",
        "sessions": rows,
        "working": sorted({sid for sid, _ in pc.working.values()}),
        "waiting": calls.phone.inbox()["items"],
        "switches": ss.message(commands=False)["switches"],
        "attach": {"on": attach_on(app), "max": FILE_MAX, "count": FILES_MAX, "part": PART},
    }


def post(app: App, path: str, b: dict) -> tuple[int, dict]:
    calls, no = _calls(app)
    if no:
        return no
    pc = calls.chat
    if path == "chat/upload":
        return upload(app, b)
    if path == "chat/send":
        files, no = attached(app, b.get("files"))
        if no:
            return no
        return pc.typed(str(b.get("text") or ""), str(b.get("session") or ""), str(b.get("reply") or ""), files)
    if path == "chat/button":
        return pc.press(str(b.get("msg") or ""), b.get("n"))
    if path == "chat/answer":
        fields = {k: b[k] for k in ("answer", "button", "dismiss") if k in b}
        if not fields:
            return 400, {"ok": False, "note": "Which answer?"}
        return calls.phone.act(str(b.get("item") or ""), fields)
    if path == "chat/op":
        args = {k: v for k, v in b.items() if k != "op"}
        return pc.change(str(b.get("op") or ""), args)
    return 404, {"error": "not found"}


# ------------------------------------------------------------------------------------------------- attachments
def attach_on(app: App) -> bool:
    return app.settings.get("dashboard.chat_attach") is not False


def picture(head: bytes) -> str:
    """The suffix of the picture these first bytes start, or "" when they aren't one Kurooto hands an AI as a picture
    (providers/openai_compat.py PICTURE_TYPES)."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[4:8] == b"ftyp" and head[8:12] in HEIF:
        return ".heic"
    return ""


def _clean(name) -> str:
    """A file's name from the page, made safe to keep: no folders, no leading dots, nothing but letters, digits, dots
    and dashes, 80 characters at most."""
    base = re.split(r"[\\/]", str(name or ""))[-1]
    return re.sub(r"[^\w.-]+", "-", base).strip("-.")[:80].strip("-.") or "file"


def _sweep(folder: Path) -> None:
    """Uploads left unfinished (the page was closed halfway) go after PART_S."""
    for f in folder.glob(".part-*"):
        try:
            if time.time() - f.stat().st_mtime > PART_S:
                f.unlink()
        except OSError:
            pass


def card(f: Path) -> dict:
    """What the page and the chat show of an attached file: {id, name, size, mime, picture}."""
    m = SAVED.fullmatch(f.name)
    uid, name = (m.group(1), m.group(2)) if m else ("", f.name)
    pic = f.suffix.lower() in PICTURE_TYPES  # only ever saved with a picture's suffix when its bytes are one
    mime = PICTURE_TYPES[f.suffix.lower()] if pic else mimetypes.guess_type(name)[0] or "application/octet-stream"
    return {"id": uid, "name": name, "size": f.stat().st_size, "mime": mime, "picture": pic}


def upload(app: App, b: dict) -> tuple[int, dict]:
    """One part of a file attached on the page, in order. The first part gets the upload's id; the last one checks
    what the file is and keeps it under its own name. (code, {ok, id, part} or {ok, file: card})."""
    if not attach_on(app):
        return 403, {"ok": False, "off": True, "note": ATTACH_OFF}
    try:
        part, parts, size = int(b.get("part") or 0), int(b.get("parts") or 0), int(b.get("size") or 0)
    except (TypeError, ValueError):
        return 400, {"ok": False, "note": "That upload didn't make sense."}
    if size <= 0:
        return 400, {"ok": False, "note": "That file is empty."}
    if size > FILE_MAX:
        return 413, {
            "ok": False,
            "note": f"That file is {size / 2**20:.1f} MB; the chat takes files up to {FILE_MAX // 2**20} MB.",
        }
    if parts != -(-size // PART) or not 0 <= part < parts:
        return 400, {"ok": False, "note": "That upload's parts don't add up."}
    try:
        data = base64.b64decode(str(b.get("data") or ""), validate=True)
    except (ValueError, binascii.Error):
        return 400, {"ok": False, "note": "That upload didn't make sense."}
    last = part == parts - 1
    if len(data) != (size - PART * (parts - 1) if last else PART):
        return 400, {"ok": False, "note": "That upload's parts don't add up."}
    folder = chat_files(app)
    folder.mkdir(parents=True, exist_ok=True)
    if part == 0:
        _sweep(folder)
        uid = uuid.uuid4().hex[:16]
    else:
        uid = str(b.get("id") or "")
        if not UID.fullmatch(uid):
            return 400, {"ok": False, "note": "That upload had no id."}
    tmp = folder / f".part-{uid}"
    if part > 0 and (not tmp.is_file() or tmp.stat().st_size != part * PART):
        return 409, {"ok": False, "note": "That upload was cut short. Attach the file again."}
    with open(tmp, "wb" if part == 0 else "ab") as f:
        f.write(data)
    if part == 0:
        owner_only(tmp)
    if not last:
        return 200, {"ok": True, "id": uid, "part": part}
    with open(tmp, "rb") as f:
        pic = picture(f.read(16))
    name = _clean(b.get("name"))
    if not pic and Path(name).suffix.lower() in PICTURE_TYPES:  # named like a picture, but its bytes aren't one
        tmp.unlink(missing_ok=True)
        return 415, {"ok": False, "note": f"{name} is named like a picture but isn't one, so it wasn't attached."}
    if pic:  # saved as what it is, whatever it was called
        name = (Path(name).stem if Path(name).suffix.lower() in PICTURE_TYPES else name)[:70] + pic
    dest = folder / f"{now():%Y-%m-%d-%H%M%S}-{uid}-{name}"
    tmp.replace(dest)
    app.events.emit("chat_attached", bytes=size, picture=bool(pic))
    return 200, {"ok": True, "file": card(dest)}


def attached(app: App, ids) -> tuple[list[tuple[Path, dict]], tuple[int, dict] | None]:
    """The files a message from the page names (their ids from chat/upload): ([(path, card)], None), or ([], the
    refusal)."""
    if not ids:
        return [], None
    if not attach_on(app):
        return [], (403, {"ok": False, "off": True, "note": ATTACH_OFF})
    if not isinstance(ids, list) or len(ids) > FILES_MAX:
        return [], (400, {"ok": False, "note": f"A message can carry at most {FILES_MAX} files."})
    folder, out = chat_files(app), []
    for i in ids:
        i = str(i)
        if not UID.fullmatch(i):
            return [], (400, {"ok": False, "note": "That file isn't one attached here."})
        f = next((p for p in folder.glob(f"*-{i}-*") if SAVED.fullmatch(p.name)), None) if folder.is_dir() else None
        if f is None or not f.is_file():
            return [], (404, {"ok": False, "note": "That file isn't on this computer any more. Attach it again."})
        out.append((f, card(f)))
    return out, None
