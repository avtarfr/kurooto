"""The dashboard's Chat page (0.8.14, look.chat_page): the phone app's chat on this computer. The same chats
("sessions") and the same messages as the app (modules/calls/chat.py keeps them in <state>/calls/chat.json), the
questions under the app's "Waiting for you" (calls/phone.py), and a box to write in the open chat. What you write
here is handled exactly as a message typed in the app (PhoneChat.typed), a button or an answer goes the same way as a
tap in the app (PhoneChat.press, PhoneApp.act), so a question settles everywhere at once. New messages reach the open
page live as {"t": "chat", ...} on the dashboard's stream (PhoneChat.live).

Everything here is behind the dashboard's key and Host check like the rest of /api; nothing new leaves this computer
(your phones hear what you write and tap through your call line, as they do when you use the app).

GET chat: {on, name, sessions (with unread), working, waiting, switches}. GET chat/thread?session=ID: {session, msgs}.
POST chat/send {session, text, reply?}, chat/button {msg, n}, chat/answer {item, answer | button | dismiss},
chat/op {op, ...} (the app's session and message ops: read, session.new / rename / delete / pin, msg.edit / delete /
pin)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App

GETS = ("chat", "chat/thread")
POSTS = ("chat/send", "chat/button", "chat/answer", "chat/op")
OFF = "The Chat page is off (Settings: look.chat_page)."
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
    }


def post(app: App, path: str, b: dict) -> tuple[int, dict]:
    calls, no = _calls(app)
    if no:
        return no
    pc = calls.chat
    if path == "chat/send":
        return pc.typed(str(b.get("text") or ""), str(b.get("session") or ""), str(b.get("reply") or ""))
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
