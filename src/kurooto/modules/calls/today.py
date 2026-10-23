"""The phone app's Today screen (0.6.0): the dashboard's Today data (core/actions.py:today) on the phone, with the
laptop asleep too, and the wake-up alarm copied to the phone so it rings there even when nothing else can.

What goes: the day, classes and calendar events, what's due (with parts done, "4/7", and what you can tap: Done, +1),
your reminders, the alarm (the next one in words, and every alarm still to ring as a time, for the phone's own
alarm), open threads, and how many questions wait. Nothing else from the day (no plan, no journal, no notes).

How: with each state push to your call line (every 5 minutes, and soon after something on it changes), this works the
list out and, if it changed (or every REFRESH_S), seals it for each paired Android phone with that phone's own key
(line.py "s1", as reminders with the lid shut are) and hands the lot over ("today-put"). Your call line keeps one
sealed copy per phone, which it can't read, and when the list changed it nudges the phones ("today" on ntfy); a phone
fetches its copy from /today when it's nudged, opened, or reconnects. The call line adds when it got the copy, which
the app shows as "as of 14:05". The iPhone app gets nothing: it has no key of its own.

What you tap on the Today screen (Done or +1 on a deadline) comes back like a chat button (chat.py): sealed, used once,
through the phone outbox while this computer is off, and here it's the very button Telegram's deadline message has
(dl:<id>:done, dl:<id>:+1; modules/deadlines.py). The phone names the deadline and the action, never callback data.

Off with calls.today = false: the call line drops its copies and the app says so.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from typing import TYPE_CHECKING

from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.calls import line

if TYPE_CHECKING:
    from kurooto.modules.calls import Calls

REFRESH_S = 900  # the same list goes again this often, so "as of" stays near the truth
TODAY_MAX = 40_000  # bytes of the list before sealing (the call line keeps one value per phone, sent all at once)
ROWS = {"classes": 12, "events": 12, "due": 20, "reminders": 10, "threads": 8}
ACTS = ("done", "+1")
DEADLINE_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
# what happened that the Today list shows: push it soon (core/events.py subscribe)
CHANGES = {
    "action", "deadline_added", "deadline_done", "deadline_ignore", "deadline_moved", "deadline_progress",
    "deadline_undo", "deadline_merged", "alarm_set", "alarm_cleared", "alarm_skipped", "alarm_daily", "alarm_rang",
    "reminder_set", "reminder_fired", "button_tapped", "thread_opened", "thread_closed", "thread_reopened",
    "calls_device_paired",
}  # fmt: skip


def _clip(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


class PhoneToday:
    """The Today list for the phone app, and what's tapped on it."""

    def __init__(self, calls: Calls):
        self.calls = calls
        self.app = calls.app
        self.file = calls.dir / "today.json"  # what was handed over last: digest, when, to which phones
        self.dirty = True

    # ------------------------------------------------------------------------------------------ the list
    def on(self) -> bool:
        return self.calls.setting("today") is not False

    def snapshot(self) -> dict:
        """What the phone shows. Stable while nothing changes (no "in 3 hours", no seconds), so an unchanged day
        isn't sent again."""
        from kurooto.core.actions import today

        t = today(self.app)
        out: dict = {"v": 1, "date": t.get("date", ""), "day": t.get("day", "")}
        out["classes"] = [
            {"time": str(c.get("time") or ""), "name": _clip(c.get("name"), 80), "skipping": bool(c.get("skipping"))}
            for c in (t.get("classes") or [])[: ROWS["classes"]]
        ]
        out["events"] = [_clip(e, 120) for e in (t.get("calendar") or [])[: ROWS["events"]]]
        out["due"] = self._due(t.get("deadlines") or [])
        out["reminders"] = [
            {"when": str(r.get("when") or ""), "what": _clip(r.get("what"), 120)}
            for r in (t.get("reminders") or [])[: ROWS["reminders"]]
        ]
        out["alarm"] = self._alarm(t.get("alarm_state"))
        out["threads"] = self._threads()
        out["questions"] = len(t.get("questions_full") or [])
        return out

    def _due(self, rows: list[dict]) -> list[dict]:
        dl = self.app.modules.get("deadlines")
        if dl is None or not self.app.is_on("deadlines"):
            return []
        from kurooto.modules.deadlines import due_day

        items, out = dl.items(), []
        for r in rows[: ROWS["due"]]:
            it = items.get(str(r.get("id")))
            if not it:
                continue
            exam = it.get("kind") == "exam"
            total, done = int(it.get("parts") or 0), int(it.get("parts_done") or 0)
            try:
                when = due_day(it["due"])
            except (KeyError, ValueError):
                when = str(it.get("due") or "")[:16]
            d = {"id": str(r["id"]), "title": _clip(dl.full_title(it), 120), "due": str(it["due"])[:16], "when": when}
            if exam:
                d["exam"] = True  # a quiz or exam isn't "done": nothing to tap
            else:
                d["acts"] = ["done"] + (["+1"] if total and done < total else [])
            if total:
                d["parts"], d["done"] = total, done
            out.append(d)
        return out

    def _alarm(self, state) -> dict:
        al = self.app.modules.get("alarm")
        if al is None or not self.app.is_on("alarm"):
            return {}
        try:
            ups = [int(a.timestamp()) for a in al.upcoming()]
        except Exception:
            ups = []
        state = state or {}
        return {
            "next": str(state.get("next") or ""),
            "daily": str(state.get("daily") or ""),
            "at": ups[:11],  # every alarm still to ring (the one set, then the rest you set), for the phone's copy
            "snooze_min": int(al.setting("snooze_min") or 10),
            "reason": _clip(al.setting("reason") or "Wake-up call", 80),
        }

    def _threads(self) -> list[dict]:
        from kurooto.core import threads

        if not threads.on(self.app):
            return []
        try:
            rows = threads.open_threads(self.app)
        except Exception:
            return []
        return [{"text": _clip(r.get("text"), 140)} for r in rows[: ROWS["threads"]]]

    @staticmethod
    def fit(snap: dict) -> str:
        """The list as sent, cut to TODAY_MAX bytes (the longest lists lose their last rows first)."""
        body = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
        while len(body.encode()) > TODAY_MAX:
            longest = max(("due", "events", "classes", "reminders", "threads"), key=lambda k: len(snap.get(k) or []))
            if not snap.get(longest):
                break
            snap[longest] = snap[longest][:-1]
            body = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
        return body

    # -------------------------------------------------------------------------------------- handing over
    def poke(self) -> None:
        """Something the list shows changed: hand it over with the next state push, which this asks for now."""
        self.dirty = True
        self.calls.connector.poke()

    def on_event(self, rec: dict) -> None:
        if rec.get("kind") in CHANGES and self.app.is_on("calls"):
            self.poke()

    async def push(self, c) -> dict:
        """Called with each state push (connector.py). Seals the list for each Android phone that gave its key and
        hands it over if it changed, the phones changed, or it's REFRESH_S old."""
        st = jload(self.file, {}) or {}
        if not self.on():
            if st.get("on", True):
                res = await c.admin("today-put", rev=self._rev(), seal={}, changed=True, off=True)
                if not res.get("error"):
                    jsave(self.file, {"rev": self._last_rev(), "on": False, "at": time.time()})
            return {"ok": True, "off": True}
        devs = await c.admin("devices")
        keys = {
            str(d["id"]): str(d["seal"])
            for d in devs.get("devices") or []
            if d.get("kind") == "android" and d.get("seal")
        }
        if not keys:
            return {"ok": True, "phones": 0}
        body = await asyncio.to_thread(lambda: self.fit(self.snapshot()))
        digest = hashlib.sha256(json.dumps([body, sorted(keys.items())]).encode()).hexdigest()
        t = time.time()
        same = digest == st.get("digest")
        if same and not self.dirty and t - float(st.get("at") or 0) < REFRESH_S:
            return {"ok": True, "same": True}
        self.dirty = False
        made = json.loads(body)
        made["made"] = int(t)  # when this computer worked it out (the call line adds when it got it)
        text = json.dumps(made, ensure_ascii=False, separators=(",", ":"))
        seal = {}
        for dev, pub in keys.items():
            try:
                seal[dev] = line.seal_s1(pub, text)
            except ValueError:
                continue  # not a key: that phone gets nothing until it sends a good one
        res = await c.admin("today-put", rev=self._rev(), seal=seal, changed=not same)
        if res.get("error"):
            self.dirty = True
            if res["error"] != "unknown op":  # an older call line: nothing to do until it's updated
                self.app.events.emit("phone_today_failed", error=str(res["error"])[:200])
            return res
        jsave(self.file, {"rev": self._last_rev(), "on": True, "digest": digest, "at": t, "phones": len(seal)})
        if not same:
            self.app.events.emit("phone_today_pushed", phones=len(seal), bytes=len(text))
        return res

    def _last_rev(self) -> int:
        return int((jload(self.file, {}) or {}).get("rev") or 0)

    def _rev(self) -> int:
        with Lock(self.app.paths.state, "calls-today"):
            st = jload(self.file, {}) or {}
            rev = max(int(st.get("rev") or 0) + 1, time.time_ns() // 1000)
            st["rev"] = rev
            jsave(self.file, st)
            return rev

    # ----------------------------------------------------------------------------------- what's tapped
    def act(self, req) -> tuple[int, dict]:
        """A tap on the Today screen: {"id": a deadline's id, "do": "done" | "+1"}. The same as that button on the
        deadline's Telegram message."""
        req = req if isinstance(req, dict) else {}
        i, do = str(req.get("id") or ""), str(req.get("do") or "")
        if do not in ACTS or not DEADLINE_ID.fullmatch(i):
            return 400, {"ok": False, "note": "That button is out of date."}
        dl = self.app.modules.get("deadlines")
        if dl is None or not self.app.is_on("deadlines"):
            return 400, {"ok": False, "note": "Deadlines is off: turn it on in Features."}
        it = dl.items().get(i)
        if it is None:
            j = next((k for k, v in dl.items().items() if i in v.get("aliases", [])), None)
            it = dl.items().get(j) if j else None
        if it is None:
            return 410, {"ok": False, "note": "That one is gone."}
        if it.get("kind") == "exam":
            return 400, {"ok": False, "note": "A quiz or exam isn't marked done."}
        if it.get("status") != "open":
            return 410, {"ok": False, "note": f"{it['title']} is already marked {it.get('status')}."}
        out = str(self.app.callback(f"dl:{i}:{do}") or "")
        self.app.events.emit("phone_today_act", act=do)
        return 200, {"ok": True, "note": _clip(out, 300)}
