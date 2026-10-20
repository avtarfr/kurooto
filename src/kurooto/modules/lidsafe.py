"""Reminders with the lid shut: when this computer is asleep or off, your Android phone still gets your reminders,
and in the morning the day's first class and what's due. Off until you turn it on; needs Phone calls and the
Kurooto app on an Android phone (an iPhone can't get these).

How: whenever your reminders change, every 10 minutes, and as this computer goes to sleep (where the system says so),
it works out what's timed in the next day (`lidsafe.hours`, 24): each reminder, and one morning line per day with
the first class and what's due that day. Each is sealed for each paired Android phone with a key only that phone has
(the app made it; calls/line.py "s1"), and the lot goes to your call line in one batch, sent again only when it
changed. Your call line keeps a time, an id and ciphertext it can't read.

Whichever side is awake at an item's time says it, once:
    this computer awake and linked: it claims the item from the call line, then says it as usual (a reminder on
        Telegram; the morning line isn't said here, where the morning page and your check-ins have it);
    this computer asleep or off: the call line's cron (every minute) sends it to your phones, which show it as a
        normal notification. On waking, a reminder that came due meanwhile is claimed first, and if the call line
        already sent it, it isn't said here too. The call line keeps one answer per item, so nothing comes twice.
A reminder due while the link to the call line is down waits for the link (2 minutes, or 30 after a sleep) and is
then said here anyway. One the call line couldn't get to your phones (5 tries, a minute apart) comes back here.

Going to sleep: Linux (logind, read with gdbus) and Windows (its power message) say so, and the batch goes once more
if anything changed. macOS doesn't tell programs; there it's the batch from the last change or the last 10 minutes.

Settings: lidsafe {hours, reminders, today, morning}. State: state/lidsafe/ (held.json: what the call line may hold
and when it last got the batch; waiting.json: reminders waiting for the call line's answer; said.json: which side
said what). Events: lidsafe_pushed, lidsafe_said_here, lidsafe_skipped, lidsafe_unclaimed, lidsafe_sent_by_line,
lidsafe_failed, lidsafe_sleep.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import threading
import time

from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.notinterested import matcher
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Module
from kurooto.modules.calls import line

register_defaults(
    "lidsafe",
    {
        "hours": 24,  # how far ahead your call line holds things (12 to 24)
        "reminders": True,  # your reminders
        "today": True,  # a morning line on your phone: the day's first class and what's due that day
        # when that line comes: your alarm that morning if one is set, else this; never later than 30 minutes
        # before the first class
        "morning": "07:30",
    },
)

HOLD_MAX = 40  # items in one batch (the soonest)
TEXT_MAX, TITLE_MAX = 300, 60
TOKEN_MAX = 2300  # a sealed copy must fit an ntfy message (4 KB) once the call line seals it again
BATCH_MAX = 100_000  # characters of sealed copies in one batch (the call line keeps it as one value)
REMINDER_UNTIL_S = 6 * 3600  # the call line sends a reminder at most this late
MORNING_UNTIL_S = 3 * 3600
CLASS_LEAD_MIN = 30
WAIT_S = 120  # a reminder due while the link is down waits this long for the call line's answer
WAIT_LATE_S = 1800  # ... this long if it came due while this computer slept (the call line has surely sent it)
CHECK_S = 600  # the batch is worked out again this often; it goes only if it changed ...
REFRESH_S = 3600  # ... or this long after the last one
RETRY_S = 30  # after a failed hand-over
STEP_S = 5
KEEP_S = 3 * 86400  # who said what, kept this long (the call line keeps its answers as long)
SLEEP_WAIT_S = 3  # at most this long holding up a sleep (Windows allows about 2 seconds)
OLD_LINE = "old line"


def item_id(kind: str, ref: str) -> str:
    return hashlib.sha256(f"{kind}:{ref}".encode()).hexdigest()[:16]


def _clip(s: str, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


class LidSafe(Module):
    id = "lidsafe"
    title = "Reminders with the lid shut"
    description = (
        "When this computer sleeps, your Android phone still gets your reminders, and in the morning the first class "
        "and what's due. Your call line holds them sealed: it sees only their times."
    )
    requires = ("calls",)
    privacy = (
        "The next day's reminders and morning lines go to your call line sealed for your Android phones: it keeps "
        "their times, not their text. When it sends one, it goes through ntfy.sh, still sealed."
    )

    def __init__(self, app):
        super().__init__(app)
        self.dir = app.paths.state / "lidsafe"
        self.clock = time.time
        self._dirty = True  # work the batch out and hand it over soon
        self._force = True  # ... even if it looks the same (just started, or linked again)
        self._checked = 0.0
        self._retry_at = 0.0
        self._was_up = False
        self._alock: asyncio.Lock | None = None  # one claim at a time (made on the loop that uses it)
        self._plock: asyncio.Lock | None = None  # one hand-over at a time
        self._watch: subprocess.Popen | None = None
        self._unwatch = None

    # ------------------------------------------------------------------------------------------ setup
    def _calls(self):
        c = self.app.modules.get("calls")
        return c if c is not None and self.app.is_on("calls") else None

    def _connector(self):
        c = self._calls()
        return c.connector if c is not None else None

    def ready(self) -> tuple[bool, str]:
        c = self.app.modules.get("calls")
        ok = c is not None and c.ready()[0]
        return (True, "") if ok else (False, "needs Phone calls set up, with the Android app paired")

    def start(self) -> None:
        self._dirty = self._force = True

    def stop(self) -> None:
        """Turned off: your call line drops what it holds (now if it's linked; else with the next state push, which
        says this is off), and reminders waiting for its answer are said here."""
        super().stop()
        c = self._connector()
        if c is not None:
            c.admin_later("sealed-put", items=[], rev=self._next_rev())
        with Lock(self.app.paths.state, "lidsafe"):
            st = self._held()
            st.update(ids={}, digest="", pushed_at=0)
            jsave(self.dir / "held.json", st)
        for iid in list(self._waiting()):
            w = self._take_waiting(iid)
            if w:
                self._say_here(iid, w)

    # ------------------------------------------------------------------------------------------- state
    def _held(self) -> dict:
        return jload(self.dir / "held.json", {}) or {}

    def _waiting(self) -> dict:
        return jload(self.dir / "waiting.json", {}) or {}

    def _said(self) -> dict:
        return jload(self.dir / "said.json", {}) or {}

    def _next_rev(self) -> int:
        with Lock(self.app.paths.state, "lidsafe"):
            st = self._held()
            st["rev"] = max(int(st.get("rev") or 0) + 1, time.time_ns() // 1000)
            jsave(self.dir / "held.json", st)
            return st["rev"]

    def _set_said(self, iid: str, by: str, **extra) -> None:
        t = self.clock()
        with Lock(self.app.paths.state, "lidsafe-said"):
            d = {k: v for k, v in self._said().items() if t - float(v.get("t") or 0) < KEEP_S}
            d[iid] = {"by": by, "t": t, **extra}
            jsave(self.dir / "said.json", d)

    def _take_waiting(self, iid: str) -> dict | None:
        """Take one waiting reminder off the list (only one taker gets it, so it's said at most once here)."""
        with Lock(self.app.paths.state, "lidsafe-waiting"):
            d = self._waiting()
            w = d.pop(iid, None)
            if w is not None:
                jsave(self.dir / "waiting.json", d)
            return w

    def poke(self) -> None:
        """Your reminders changed: hand the batch over soon."""
        self._dirty = True

    # ------------------------------------------------------------------------------------------ the batch
    def _hours(self) -> float:
        try:
            return min(24.0, max(12.0, float(self.setting("hours") or 24)))
        except (TypeError, ValueError):
            return 24.0

    def _item(self, iid: str, at: float, until_s: int, title: str, text: str) -> dict:
        return {
            "id": iid,
            "at": int(at),
            "until": int(at) + until_s,
            "title": _clip(title, TITLE_MAX),
            "text": _clip(text, TEXT_MAX),
        }

    def batch(self) -> list[dict]:
        """What's timed in the next `hours`: [{id, at, until, title, text}], soonest first, at most HOLD_MAX."""
        t = self.clock()
        end = t + self._hours() * 3600
        out = []
        if self.setting("reminders", True) and self.app.is_on("reminders"):
            for j in self.app.scheduler.jobs("reminders:"):
                ref = (j.payload or {}).get("ref")
                if j.action == "reminders.fire" and ref and not j.payload.get("lidsafe") and t < j.next_run <= end:
                    what = j.payload.get("what") or "you asked me to remind you"
                    out.append(
                        self._item(
                            item_id("rem", ref), j.next_run, REMINDER_UNTIL_S, self.app.name, f"Reminder: {what}"
                        )
                    )
        if self.setting("today", True):
            start = dt.datetime.fromtimestamp(t).date()
            for add in (0, 1):
                day = start + dt.timedelta(days=add)
                m = self.morning(day)
                if m and t < m["at"].timestamp() <= end:
                    out.append(
                        self._item(
                            item_id("day", day.isoformat()), m["at"].timestamp(), MORNING_UNTIL_S, "Today", m["text"]
                        )
                    )
        return sorted(out, key=lambda i: i["at"])[:HOLD_MAX]

    def morning(self, day: dt.date) -> dict | None:
        """A day's morning line: {"at", "text"} with the first class and what's due that day; None if neither."""
        first = None
        subj = self.app.modules.get("subjects")
        if subj is not None and self.app.is_on("subjects"):
            try:
                classes = subj.classes_on(day)
            except Exception as e:
                self.app.events.emit("lidsafe_failed", what="classes", error=str(e)[:200])
                classes = []
            first = classes[0] if classes else None
        due = []
        dl = self.app.modules.get("deadlines")
        if dl is not None and self.app.is_on("deadlines"):
            skip = matcher(self.app)
            for it in dl.items().values():
                if it.get("status") != "open" or skip(it.get("title", "")):
                    continue
                try:
                    d = dt.datetime.fromisoformat(it["due"])
                except (KeyError, TypeError, ValueError):
                    continue
                if d.date() == day:
                    due.append((d, str(it.get("title") or "")))
        parts = []
        if first:
            parts.append(f"First class {first['start_dt']:%H:%M}: {first.get('name') or first.get('subject')}.")
        if due:
            each = [title if f"{d:%H:%M}" == "23:59" else f"{title} ({d:%H:%M})" for d, title in sorted(due)[:6]]
            parts.append("Due today: " + "; ".join(each) + ".")
        if not parts:
            return None
        try:
            tm = dt.time.fromisoformat(str(self.setting("morning") or "07:30"))
        except ValueError:
            tm = dt.time(7, 30)
        at = self._alarm_on(day) or dt.datetime.combine(day, tm)
        if first:
            at = min(at, first["start_dt"] - dt.timedelta(minutes=CLASS_LEAD_MIN))
        return {"at": at, "text": " ".join(parts)}

    def _alarm_on(self, day: dt.date) -> dt.datetime | None:
        """That morning's alarm, if Morning alarm has one set (it rings from your call line by itself)."""
        a = self.app.modules.get("alarm")
        if a is None or not self.app.is_on("alarm"):
            return None
        try:
            at = a.next()
        except Exception:
            return None
        return at if at is not None and at.date() == day and at.hour < 12 else None

    def _seal(self, it: dict, keys: dict[str, str]) -> dict | None:
        body = json.dumps(
            {"id": it["id"], "title": it["title"], "text": it["text"], "at": it["at"]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        seal = {}
        for dev, pub in keys.items():
            try:
                tok = line.seal_s1(pub, body)
            except ValueError:
                continue  # not a key: that phone gets nothing until it sends a good one
            if len(tok) <= TOKEN_MAX:
                seal[dev] = tok
        return {"id": it["id"], "at": it["at"], "until": it["until"], "seal": seal} if seal else None

    def sealed_batch(self, plain: list[dict], keys: dict[str, str]) -> list[dict]:
        out, size = [], 0
        for it in plain:
            s = self._seal(it, keys)
            if s is None:
                continue
            size += sum(len(v) for v in s["seal"].values())
            if size > BATCH_MAX:
                break
            out.append(s)
        return out

    # ------------------------------------------------------------------------------------- the hand-over
    async def push(self, force: bool = False) -> dict:
        """Hand the batch to your call line, if it changed (or force). Raises when the link can't be used."""
        if self._plock is None:
            self._plock = asyncio.Lock()
        async with self._plock:
            return await self._push(force)

    async def _push(self, force: bool) -> dict:
        c = self._connector()
        if c is None or not c.connected:
            self._dirty = True
            return {"ok": False, "why": "not linked"}
        self._dirty = False
        self._checked = self.clock()
        plain = await asyncio.to_thread(self.batch)
        devs = await c.admin("devices")
        keys = {
            str(d["id"]): str(d["seal"])
            for d in devs.get("devices") or []
            if d.get("kind") == "android" and d.get("seal")
        }
        digest = hashlib.sha256(json.dumps([plain, sorted(keys.items())], sort_keys=True).encode()).hexdigest()
        st = self._held()
        fresh = self.clock() - float(st.get("pushed_at") or 0) < REFRESH_S
        if not (force or self._force) and digest == st.get("digest") and fresh and not st.get("error"):
            return {"ok": True, "same": True}
        sealed = await asyncio.to_thread(self.sealed_batch, plain, keys)
        rev = self._next_rev()
        text = {it["id"]: it["text"] for it in plain}
        t = self.clock()
        with Lock(self.app.paths.state, "lidsafe"):  # before it goes: an answer lost on the way leaves none unclaimed
            st = self._held()
            ids = {k: v for k, v in (st.get("ids") or {}).items() if float(v.get("until") or 0) > t - 86400}
            for s in sealed:
                ids[s["id"]] = {"at": s["at"], "until": s["until"], "text": text.get(s["id"], "")}
            st["ids"] = ids
            jsave(self.dir / "held.json", st)
        res = await c.admin("sealed-put", items=sealed, rev=rev)
        with Lock(self.app.paths.state, "lidsafe"):
            st = self._held()
            if res.get("error"):
                old = res["error"] == "unknown op"
                st.update(error=OLD_LINE if old else str(res["error"])[:200], error_at=t)
                if old:  # an older call line holds nothing
                    st["ids"] = {}
            elif res.get("ok"):
                st.update(digest=digest, pushed_at=t, phones=len(keys), held=int(res.get("held") or 0), error="")
                self._force = False
            jsave(self.dir / "held.json", st)
        for iid, by in (res.get("done") or {}).items():
            if by in ("line", "computer"):
                self._set_said(str(iid), by)
        if res.get("ok"):
            self.app.events.emit("lidsafe_pushed", items=len(sealed), phones=len(keys))
        return res

    def handed_over(self, action: str, p: dict) -> bool:
        """A feature is about to say something your call line may hold (Reminders, as one comes due). False: say it
        now, as usual. True: hold off; the call line's answer decides, and if it's this computer's to say, `action`
        runs again with the same payload (and "lidsafe": "here")."""
        if p.get("lidsafe"):
            return False
        iid = item_id("rem", str(p["ref"])) if action == "reminders.fire" and p.get("ref") else None
        if iid is None or iid not in (self._held().get("ids") or {}):
            return False
        by = (self._said().get(iid) or {}).get("by")
        if by == "line":
            self.app.events.emit("lidsafe_skipped", kind="reminder")
            return True
        if by == "computer":
            return False
        with Lock(self.app.paths.state, "lidsafe-waiting"):
            d = self._waiting()
            d[iid] = {"action": action, "payload": p, "since": self.clock()}
            jsave(self.dir / "waiting.json", d)
        self._kick()
        return True

    def _kick(self) -> None:
        """Ask the call line about what's waiting, now (from any thread)."""
        c = self._connector()
        loop = getattr(c, "loop", None)
        if c is not None and c.connected and loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.claim_waiting(), loop)

    async def _claim(self, ids: list[str]) -> dict[str, str]:
        c = self._connector()
        if not ids or c is None or not c.connected:
            return {}
        res = await c.admin("sealed-claim", ids=ids)
        if res.get("error") == "unknown op":  # an older call line holds nothing: everything is this computer's
            return dict.fromkeys(ids, "computer")
        out = {str(k): str(v) for k, v in (res.get("ids") or {}).items() if v in ("line", "computer")}
        for iid, by in out.items():
            self._set_said(iid, by)
        return out

    async def claim_waiting(self) -> int:
        """Reminders waiting for the call line's answer: said here if they're this computer's, else dropped (your
        phone has them). The number said here."""
        if self._alock is None:
            self._alock = asyncio.Lock()
        async with self._alock:
            ids = list(self._waiting())
            got = await self._claim(ids)
            n = 0
            for iid, by in got.items():
                w = self._take_waiting(iid)
                if w is None:
                    continue
                if by == "computer":
                    self._say_here(iid, w)
                    n += 1
                else:
                    self.app.events.emit("lidsafe_skipped", kind="reminder")
            return n

    async def acknowledge_due(self) -> dict[str, str]:
        """Items whose time came while this computer was awake and linked: claim them, so the call line doesn't
        send them once it's gone (the morning line, and reminders the scheduler hasn't run yet)."""
        t, said, waiting = self.clock(), self._said(), self._waiting()
        due = [
            iid
            for iid, v in (self._held().get("ids") or {}).items()
            if float(v.get("at") or 0) <= t < float(v.get("until") or 0) and iid not in said and iid not in waiting
        ]
        if self._alock is None:
            self._alock = asyncio.Lock()
        async with self._alock:
            return await self._claim(due)

    def _say_here(self, iid: str, w: dict) -> None:
        """Run the feature's action again, through the scheduler, marked as this computer's to say."""
        action = str(w.get("action") or "")
        mod = action.split(".", 1)[0]
        payload = {**(w.get("payload") or {}), "lidsafe": "here"}
        self.app.scheduler.at(self.app.scheduler.clock(), action, payload, key=f"{mod}:lidsafe-{iid}", module=mod)
        self._set_said(iid, "computer")
        self.app.events.emit("lidsafe_said_here", kind="reminder")

    def release_overdue(self) -> int:
        """Reminders that waited too long for the call line (no link): say them here now."""
        t, n = self.clock(), 0
        for iid, w in list(self._waiting().items()):
            p = w.get("payload") or {}
            limit = WAIT_LATE_S if (p.get("late_s") or p.get("missed")) else WAIT_S
            if t - float(w.get("since") or 0) < limit:
                continue
            w = self._take_waiting(iid)
            if w is not None:
                self._say_here(iid, w)
                self.app.events.emit("lidsafe_unclaimed", kind="reminder")
                n += 1
        return n

    def on_line_event(self, m: dict) -> None:
        """From the call line (calls/__init__.py passes these on)."""
        name, iid = m.get("name"), str(m.get("id") or "")
        if name == "device_key":  # a phone gave its key: seal for it too
            self._dirty = True
            return
        if not iid:
            return
        if name == "sealed_sent":
            self._set_said(iid, "line")
            self.app.events.emit("lidsafe_sent_by_line")
        elif name == "sealed_failed":
            was = (self._said().get(iid) or {}).get("by")
            self._set_said(iid, "computer", failed=True)
            self.app.events.emit("lidsafe_failed", what="send")
            text = ((self._held().get("ids") or {}).get(iid) or {}).get("text")
            if was == "line" and text:  # skipped here because the call line had it, which then couldn't send it
                self.app.notify(f"Your call line couldn't get this to your phone: {text}", kind="reminder")

    # ------------------------------------------------------------------------------------------- running
    async def step(self) -> None:
        """One round of the background loop (every few seconds)."""
        c = self._connector()
        up = bool(c is not None and c.connected)
        t = self.clock()
        if up and not self._was_up:  # linked again: the batch may be stale, and the line may have lost it (off)
            self._dirty = self._force = True
        self._was_up = up
        if t - self._checked >= CHECK_S:
            self._dirty = True
        if up:
            if self._dirty and t >= self._retry_at:
                try:
                    await self.push()
                except Exception as e:
                    self._dirty, self._retry_at = True, t + RETRY_S
                    with Lock(self.app.paths.state, "lidsafe"):
                        st = self._held()
                        st.update(error=f"{type(e).__name__}: {e}"[:200], error_at=t)
                        jsave(self.dir / "held.json", st)
            for go in (self.claim_waiting, self.acknowledge_due):
                try:
                    await go()
                except Exception:
                    pass  # tried again next round
        await asyncio.to_thread(self.release_overdue)

    async def background(self, stop: asyncio.Event) -> None:
        self._watch_sleep()
        try:
            while not stop.is_set():
                await self.step()
                try:
                    await asyncio.wait_for(stop.wait(), timeout=STEP_S)
                except TimeoutError:
                    pass
        finally:
            self._stop_watch()

    # ------------------------------------------------------------------------------------- going to sleep
    def going_to_sleep(self) -> bool:
        """The system says it's about to sleep: hand the batch over now if it changed (waits a few seconds at most;
        called from a thread of its own). True if the call line has the latest batch."""
        c = self._connector()
        loop = getattr(c, "loop", None)
        self.app.events.emit("lidsafe_sleep")
        if c is None or not c.connected or loop is None or not loop.is_running():
            return False
        try:
            res = asyncio.run_coroutine_threadsafe(self.push(), loop).result(SLEEP_WAIT_S)
        except Exception:
            return False
        return bool(res.get("ok"))

    def _watch_sleep(self) -> None:
        if sys.platform == "win32":
            from kurooto.core import endsession

            self._unwatch = endsession.on_suspend(self.going_to_sleep)
        elif sys.platform.startswith("linux") and shutil.which("gdbus"):
            # logind's PrepareForSleep(true) comes just before a suspend; gdbus prints each signal on a line
            cmd = ["gdbus", "monitor", "--system", "--dest", "org.freedesktop.login1"]
            try:
                self._watch = subprocess.Popen([*cmd, "--object-path", "/org/freedesktop/login1"], **_pipe())
            except OSError:
                return
            threading.Thread(target=self._logind, args=(self._watch,), name="lidsafe-sleep", daemon=True).start()

    def _stop_watch(self) -> None:
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None
        p, self._watch = self._watch, None
        if p is not None and p.poll() is None:
            p.terminate()

    def _logind(self, p: subprocess.Popen) -> None:
        for ln in p.stdout or []:
            if sleeping(ln):
                self.going_to_sleep()

    # ------------------------------------------------------------------------------------------ health
    def health_check(self):
        from kurooto.core.health import Check
        from kurooto.core.health_checks import linked
        from kurooto.core.presence import when

        def probe(net: bool) -> tuple | None:
            ok, why = self.ready()
            if not ok:
                return False, why
            st = self._held()
            if st.get("error") == OLD_LINE:
                return False, (
                    "your call line is older than this feature (it updates itself overnight, or now: Settings → "
                    "Features → Phone calls → Set up)"
                )
            calls = self._calls()
            if calls is not None and linked(self.app, calls) is False:
                return False, "this computer isn't linked to your call line, so it has an old batch", "reconnect:calls"
            if not st.get("pushed_at"):
                return None, "not handed over yet"
            if not st.get("phones"):
                return False, (
                    "no phone can open them yet: update the Kurooto app on your Android phone and open it once "
                    "(an iPhone can't get these)"
                )
            return True, (
                f"your call line holds {int(st.get('held') or 0)} for {st['phones']} phone(s), "
                f"as of {when(float(st['pushed_at']), self.clock())}"
            )

        return Check(
            "lidsafe",
            self.title,
            probe=probe,
            kind="link",
            help="Settings → Features → Phone calls: pair the Android app, or set the call line up again.",
        )


def sleeping(ln: str) -> bool:
    """A gdbus monitor line saying the system is about to sleep."""
    return "PrepareForSleep" in ln and "(true" in ln


def _pipe() -> dict:
    return {"stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL, "text": True}
