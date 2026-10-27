"""Your phone as a second channel: Kurooto's questions and approvals reach the phone app, not only its calls.

What goes there is set by notify.app_kinds: questions and approvals by default (calls always ring it); add
"reminder", "deadline", "result" or "info" to get those there too. Each message goes this computer → your call
line → your phones. The Android app gets it as an end-to-end encrypted ntfy message (the same key as rings) and
shows a notification with a Reply box, the question's choices, Approve / Deny, or the message's buttons. An iPhone
gets a Web Push with nothing in it, and the Home Screen app then fetches what's waiting from the call line.

Your answer comes back the same way: the Android app seals it with that key, so the call line can't read it; the
iPhone app sends it over HTTPS with its device key. Either way it can be used once (a random nonce and the time it
was sent), and the call line passes it here, or keeps it until this computer is back on. Here it answers the
question (app.ask, via "app"), presses the button you tapped, or goes to the feature that asked, as a reply.

The call line keeps a copy of what's open (at most 40 items, each gone after a day or once it's dealt with
anywhere) so the iPhone app can list it while this computer is off.

Cards (0.6.0): a check-in or quiz question carries "card" ("checkin" / "quiz"), and the Android app shows it on its
main screen as a card with an answer box and its buttons. A reply whose answer comes with buttons (the quiz's Forgot /
Hard / Good / Easy) can't put them in the reply note, so they come as the next message: the next card. A "place"
message (a location reminder, modules/reminders.py) is kept by the Android app, not shown as a question.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import uuid
from typing import TYPE_CHECKING

from kurooto.core.lock import Lock
from kurooto.core.notify import Message, counts
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Incoming
from kurooto.modules.calls import line

if TYPE_CHECKING:
    from kurooto.modules.calls import Calls

MAX_ITEMS = 40
KEEP_S = 24 * 3600  # a message (not a question from app.ask) stays on the phone's list this long
TEXT_MAX = 3000
FRESH_MS = 10 * 60_000  # an answer must reach the call line within 10 minutes of being sent (clock skew included)
NONCE_KEEP_MS = 2 * 86400_000
OPEN = ("open", "later")
GONE = "That's no longer open: it was answered somewhere else, or it expired."


def _clip(s: str, n: int) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


# What the phone app shows as an answerable card on its main screen (0.6.0): the check-in, and quiz questions with
# their self-grading. Told by what the message is about, or by its buttons' data (a grading message has no map).
CARDS = {"checkin": "checkin", "quiz": "quiz", "qlink": "quiz"}
CARD_BUTTONS = {"chk": "checkin", "qz": "quiz", "ql": "quiz"}


def card_of(map_kind: str | None, data: list[str]) -> str:
    """ "checkin", "quiz" or "" for a message about `map_kind` with these buttons' data."""
    if map_kind in CARDS:
        return CARDS[map_kind]
    for d in data:
        if isinstance(d, str) and d.partition(":")[0] in CARD_BUTTONS:
            return CARD_BUTTONS[d.partition(":")[0]]
    return ""


class PhoneApp:
    """The `app` notify channel (registered by Phone calls) and the answers that come back from phones."""

    def __init__(self, calls: Calls):
        self.calls = calls
        self.app = calls.app
        self.file = calls.dir / "inbox.json"
        self.nonce_file = calls.dir / "answer-nonces.json"

    # ------------------------------------------------------------------------------------------ storage
    def _load(self) -> dict:
        d = jload(self.file, {}) or {}
        return {"rev": int(d.get("rev") or 0), "items": [i for i in d.get("items") or [] if isinstance(i, dict)]}

    def _save(self, d: dict) -> int:
        """Save with a new revision: a microsecond clock that only goes up, so the call line can tell an older
        snapshot of the list from a newer one."""
        d["rev"] = max(int(d.get("rev") or 0) + 1, time.time_ns() // 1000)
        d["items"] = d["items"][-MAX_ITEMS:]
        jsave(self.file, d)
        return d["rev"]

    def _lock(self):
        return Lock(self.app.paths.state, "calls-inbox")

    def _ask(self):
        return getattr(self.app, "ask", None)

    def _open(self, it: dict, t: float) -> bool:
        if it.get("qid"):
            ask = self._ask()
            q = ask.get(it["qid"]) if ask else None
            return bool(q) and q.get("status") in OPEN
        return it.get("until", 0) > t

    # -------------------------------------------------------------------------------------- sending
    def item(self, msg: Message) -> dict | None:
        """What the phone shows for a message: its text, and how you can answer (Reply, choices, buttons)."""
        t = int(time.time())
        it = {
            "id": uuid.uuid4().hex[:16],
            "kind": msg.kind,
            "title": _clip(msg.title or self.app.name, 120),
            "text": _clip(msg.text, TEXT_MAX),
            "at": t,
            "until": t + KEEP_S,
        }
        if msg.map_kind == "ask":
            ask = self._ask()
            q = ask.get(str(msg.map_ref)) if ask else None
            if not q:
                return None
            pub = ask.public(q)
            try:
                until = int(dt.datetime.fromisoformat(str(pub.get("expires"))).timestamp())
            except (TypeError, ValueError):
                until = t + 2 * KEEP_S
            it.update(
                qid=pub["id"],
                until=until,
                text=_clip(pub.get("text") or msg.text, TEXT_MAX),
                choices=[_clip(c, 60) for c in (pub.get("choices") or [])][:8],
                reply=pub.get("kind") != "approval",
                later=True,
            )
            return it
        buttons, data = [], []
        for row in msg.buttons or []:
            for label, target in row:
                if isinstance(target, dict) and str(target.get("url", "")).startswith("https://"):
                    buttons.append({"label": _clip(label, 40), "url": target["url"]})
                    data.append("")
                elif isinstance(target, str):
                    buttons.append({"label": _clip(label, 40)})
                    data.append(target)
        it.update(buttons=buttons[:4], reply=bool(msg.map_kind))
        it["_data"] = data[:4]  # stays here: the phone answers with the button's number, never its data
        if msg.map_kind:
            it["_map"] = [msg.map_kind, str(msg.map_ref or "")]
        card = card_of(msg.map_kind, data)
        if card:
            it["card"] = card
        return it

    @staticmethod
    def public(it: dict) -> dict:
        return {k: v for k, v in it.items() if not k.startswith("_") and k != "pushed"}

    def send(self, msg: Message) -> str | None:
        """The `app` channel: show it on your phones. Calls aren't sent here (ringing does that)."""
        if msg.kind == "call":
            return None
        it = self.item(msg)
        if not it:
            return None
        with self._lock():
            d = self._load()
            t = time.time()
            d["items"] = [i for i in d["items"] if self._open(i, t)] + [it]
            rev = self._save(d)
        self._push(it, rev)
        self.calls.chat.live("waiting")  # the dashboard's Chat page lists what's open too
        self.app.events.emit("phone_message", kind=msg.kind)
        return it["id"]

    def _push(self, it: dict, rev: int) -> bool:
        def done(res):
            if res and not res.get("error"):
                self._mark_pushed(it["id"])

        return self.calls.connector.admin_later(
            "notify", then=done, item=self.public(it), rev=rev, assistant=self.app.name
        )

    def _mark_pushed(self, item_id: str) -> None:
        with self._lock():
            d = self._load()
            for i in d["items"]:
                if i["id"] == item_id:
                    i["pushed"] = True
                    jsave(self.file, d)  # same revision: the list the phone sees didn't change
                    return

    def flush(self) -> int:
        """Send again what didn't reach the call line (it was down when the message was sent), if still recent."""
        t, n = time.time(), 0
        d = self._load()
        for i in d["items"]:
            if not i.get("pushed") and t - i.get("at", 0) < 3600 and self._open(i, t):
                n += bool(self._push(i, d["rev"]))
        return n

    def inbox(self) -> dict:
        """What's open, for the call line's copy (the iPhone app lists it, even with this computer off)."""
        t = time.time()
        d = self._load()
        return {"rev": d["rev"], "items": [self.public(i) for i in d["items"] if self._open(i, t)]}

    def retract(self, map_kind: str | None = None, map_ref: str | None = None, button: str | None = None) -> int:
        """It was dealt with somewhere (answered, a button tapped, expired): take it off your phones."""

        def hit(i: dict) -> bool:
            if map_kind == "ask" and map_ref and i.get("qid") == str(map_ref):
                return True
            if map_kind and i.get("_map") == [map_kind, str(map_ref or "")]:
                return True
            return bool(button) and button in (i.get("_data") or [])

        return self._remove(hit)

    def _remove(self, hit) -> int:
        with self._lock():
            d = self._load()
            gone = [i["id"] for i in d["items"] if hit(i)]
            if not gone:
                return 0
            d["items"] = [i for i in d["items"] if i["id"] not in gone]
            rev = self._save(d)
        self.calls.connector.admin_later("notify-clear", ids=gone, rev=rev)
        self.calls.chat.live("waiting")
        return len(gone)

    # ------------------------------------------------------------------------------------- answers
    def answer(self, body: dict) -> tuple[int, dict]:
        """An answer from a phone, passed on by the call line: {"device", "at", "item", and "k1" (sealed by the
        Android app) or the fields themselves (the iPhone app)}. The fields: "ts" (ms), "n" (a random nonce), and
        one of "answer" (a choice, typed text, "later", "approve"/"deny"), "button" (its number), "dismiss"."""
        item_id = str(body.get("item") or "")
        fields = body
        if body.get("k1"):
            plain = line.open_k1(self.app.secrets.get("calls.ntfy_key") or "", str(body["k1"]))
            try:
                fields = json.loads(plain) if plain else None
            except ValueError:
                fields = None
            if not isinstance(fields, dict) or str(fields.get("item") or "") != item_id:
                self.app.events.emit("phone_answer_refused", why="sealed")
                return 400, {"ok": False, "note": "That answer couldn't be opened here. Pair the phone again."}
        why = self._spend_nonce(fields, body.get("at"))
        if why:
            self.app.events.emit("phone_answer_refused", why=why)
            return 409, {"ok": False, "note": why}
        return self.act(item_id, fields)

    def act(self, item_id: str, fields: dict) -> tuple[int, dict]:
        """Do an answer to one open item: from a phone (answer, once its seal and nonce are checked) or from the
        dashboard's Chat page (web/chat_api.py, behind the dashboard's key). The same path, so it settles everywhere."""
        d = self._load()
        it = next((i for i in d["items"] if i["id"] == item_id), None)
        if not it or not self._open(it, time.time()):
            return 410, {"ok": False, "note": GONE}
        if fields.get("dismiss"):
            self._remove(lambda i: i["id"] == item_id)
            return 200, {"ok": True, "note": "Dismissed."}
        if "button" in fields:
            return self._button(it, fields["button"])
        text = str(fields.get("answer") or "").strip()[:4000]
        if not text:
            return 400, {"ok": False, "note": "The answer was empty."}
        if it.get("qid"):
            ask = self._ask()
            r = ask.answer(it["qid"], text, via="app") if ask else {"ok": False, "note": GONE}
            self._remove(lambda i: i["id"] == item_id)
            self.app.events.emit("phone_answered", kind=it["kind"], ok=bool(r.get("ok")))
            return 200, {"ok": bool(r.get("ok")), "note": str(r.get("note") or "")[:300]}
        if not it.get("_map"):
            return 400, {"ok": False, "note": "That message doesn't take a reply."}
        said: list[str] = []
        more: list[tuple[str, list]] = []  # what came with buttons (the quiz's Forgot / Hard / Good / Easy)

        def respond(t, buttons=None):
            if buttons:
                more.append((str(t), buttons))
            else:
                said.append(str(t))

        mk, ref = it["_map"]
        self.app.handle(Incoming(text, via="app", reply_to={"kind": mk, "ref": ref}, respond=respond))
        self._remove(lambda i: i["id"] == item_id)
        for t, buttons in more:  # a reply note can't carry buttons: they come as the next message (a card in the app)
            self.send(Message(t, title=it.get("title"), buttons=buttons, kind="question"))
        self.app.events.emit("phone_answered", kind=it["kind"], ok=True)
        note = " ".join(said) or ("The rest is in the next message." if more else "Sent.")
        return 200, {"ok": True, "note": _clip(note, 300)}

    def _button(self, it: dict, n) -> tuple[int, dict]:
        data = it.get("_data") or []
        try:
            target = data[int(n)]
        except (TypeError, ValueError, IndexError):
            target = ""
        if not target:
            return 400, {"ok": False, "note": "That button is out of date."}
        out = self.app.callback(target)  # also retracts this message from your phones (App.callback)
        if not counts(target):  # a +1 stays open: the phone shows it again, and the next tap counts too
            self._remove(lambda i: i["id"] == it["id"])
        self.app.events.emit("phone_button", kind=it["kind"])
        return 200, {"ok": True, "note": _clip(out, 300)}

    def _spend_nonce(self, fields: dict, at) -> str | None:
        """None if this answer is fresh and new; else why it's refused (stale, or already used)."""
        n = str(fields.get("n") or "")
        try:
            ts, at = int(fields.get("ts")), int(at or time.time() * 1000)
        except (TypeError, ValueError):
            return "The answer had no time on it."
        if not re.fullmatch(r"[0-9a-f]{16,64}", n):
            return "The answer had no nonce."
        if abs(at - ts) > FRESH_MS:
            return "That answer is too old (or this phone's clock is off). Try again."
        with Lock(self.app.paths.state, "calls-nonces"):
            seen = jload(self.nonce_file, {}) or {}
            if n in seen:
                return "That answer was already used."
            cut = at - NONCE_KEEP_MS
            seen = {k: v for k, v in seen.items() if isinstance(v, int) and v > cut}
            seen[n] = ts
            jsave(self.nonce_file, seen)
        return None
