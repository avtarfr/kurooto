"""Your rhythm: when you're around, lighter days after heavy ones, and noticing when you've gone quiet. Rules only, on
this computer; each change is said once, with Undo.

When you're around (availability.learn_night, on): once a day it looks at the last three weeks of what you did (your
messages, buttons you tapped, calls you answered, "I'm awake") and takes each day's longest quiet stretch of 4 to 16
hours. With 7 or more of them, the middle of their starts and of their ends (to the half hour) are your usual quiet
hours; nights that run into the afternoon are fine (08:00 to 16:00). When an end is an hour or more from the night
hours (availability.night), they move there, with one line and Undo: at most once a week, never night hours you set
yourself, and left alone for a month after an Undo. A stretch that ends just after Kurooto came back online says
nothing (it was catching up). Only those two times are kept, as when you're around.

With availability.learn_morning (on), what assumed a clock morning moves with them in the same line, unless you set it
yourself: the check-in day turns two hours before you're usually up (checkins.day_starts), Dreaming's morning message
comes half an hour after (dreaming.when) and Start-by's "Time to start" an hour after (startby.when). The alarm uses
the same times to suggest one when none is set (modules/alarm.py:Alarm.suggest).

Lighter days (notify.calm.lighter_after, on): the day after an exam (a deadline of kind "exam" that passed) or a heavy
day (HEAVY_H hours or more on the study tracker), half the daily limit of messages that come by themselves (rounded
up), the first check-in an hour later, and one line in the morning message (Dreaming's, or its own when Dreaming is
off) with Not today, which puts the day back as usual.

Noticing absence (availability.absence_days, 2; 0: off): nothing from you for that many days (no message, no tap, no
answered call) while Kurooto kept running: one message, "Haven't heard from you in two days. All good? Nothing's
urgent.", with I'm fine / Busy, quiet for a week. Never repeated, never a call, until you're back; it waits out the
night, focus, a hold on calls, a pause and a quiet week. Busy: no calls for a week (availability's quiet) and what
comes by itself waits for each evening's bundle (core/calm.py) until then.

State: state/rhythm.json (the usual quiet hours, the last change and its Undo, the day's lighter-day line, the absence
asked about, the quiet week).
"""

from __future__ import annotations

import datetime as dt
import math
import threading
from typing import TYPE_CHECKING

from kurooto.core.calm import ASKED
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "availability",
    {
        "learn_night": True,  # move the night hours to when you're usually quiet (not ones you set), with Undo
        "learn_morning": True,  # the check-in day, morning message and "Time to start" follow them (not ones you set)
        "absence_days": 2,  # nothing from you this many days: one gentle message (0: never)
    },
)
register_defaults("notify", {"calm": {"lighter_after": True}})  # after an exam or a heavy day: a lighter next day

ACTIVE = ("message_in", "button_tapped", "call_answered", "alarm_up_now")  # you did something
LEARN_DAYS, LEARN_NIGHTS, LEARN_GAP_MIN = 21, 7, 60  # look back, quiet stretches needed, minutes off before moving
QUIET_MIN_H, QUIET_MAX_H = 4, 16  # a stretch without you this long is a night
NIGHT_MIN_H, NIGHT_MAX_H = 4, 14  # a learned night's length
WAKE_FROM, WAKE_TO = 3 * 60, 18 * 60  # a learned night ends between 03:00 and 18:00 (afternoons are fine)
BACK_MIN = 10  # a stretch ending this soon after Kurooto came back online: it caught up, you didn't wake
AGAIN_DAYS, UNDONE_DAYS = 7, 30
MORNING = {  # setting -> (minutes from your usual wake, its form)
    "checkins.day_starts": (-120, "{}"),
    "dreaming.when": (30, "daily {}"),
    "startby.when": (60, "daily {}"),
}
MORNING_SAID = {
    "checkins.day_starts": "the check-in day turns at {}",
    "dreaming.when": "the morning message comes at {}",
    "startby.when": '"Time to start" comes at {}',
}
HEAVY_H = 8  # study hours that make a heavy day
LATER_MIN = 60  # a lighter day's first check-in comes this much later (said as "an hour")
QUIET_WEEK_DAYS = 7
WORDS = {1: "a day", 2: "two days", 3: "three days"}


def _m(hhmm: str) -> int:
    t = dt.time.fromisoformat(str(hhmm).strip().zfill(5))
    return t.hour * 60 + t.minute


def _hm(m: int) -> str:
    m %= 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def _apart(a: int, b: int) -> int:
    """Minutes between two times of day, around the clock."""
    d = abs(a - b) % 1440
    return min(d, 1440 - d)


def middle(mins: list[int]) -> int:
    """The middle of times of day (minutes), around the clock: 23:50 and 00:10 make midnight, not noon."""
    a = sum(math.sin(m / 1440 * 2 * math.pi) for m in mins)
    b = sum(math.cos(m / 1440 * 2 * math.pi) for m in mins)
    mean = round(math.atan2(a, b) / (2 * math.pi) * 1440) % 1440
    offs = sorted((m - mean + 720) % 1440 - 720 for m in mins)
    return (mean + offs[len(offs) // 2]) % 1440


class Rhythm:
    def __init__(self, app: App):
        self.app = app
        self.file = app.paths.state / "rhythm.json"
        self._lock = threading.Lock()

    def state(self) -> dict:
        return jload(self.file, {}) or {}

    def _put(self, **kw) -> None:
        with self._lock:
            st = self.state()
            st.update(kw)
            jsave(self.file, st)

    def start(self) -> None:
        sch = self.app.scheduler
        sch.action("rhythm.tick", lambda p: self.tick())
        sch.every("rhythm:tick", "every 30m", "rhythm.tick", module="rhythm", misfire="coalesce")

    def tick(self) -> dict:
        """Every half hour: once a day (not at night) the quiet hours; the lighter-day line; the absence check."""
        t, out = now(), {}
        night = self.app.availability.night(t)
        for name, fn in (("learned", self.learn), ("lighter", self.tell_lighter), ("absence", self.absence)):
            if night and name != "absence":  # absence checks the night itself
                continue
            if name == "learned":
                if self.state().get("looked") == t.date().isoformat():
                    continue
                self._put(looked=t.date().isoformat())
            try:
                out[name] = fn()
            except Exception as e:  # one part going wrong doesn't stop the others
                self.app.events.emit("rhythm_failed", part=name, error=f"{type(e).__name__}: {e}"[:200])
        return out

    # ------------------------------------------------------------------------------- when you're around
    def usual(self) -> dict | None:
        """Your usual quiet hours from the last three weeks: {"from", "to", "nights"}, or None (too few, or odd)."""
        since = now() - dt.timedelta(days=LEARN_DAYS)
        times = []
        for e in self.app.events.tail(50000, kinds=set(ACTIVE)):
            try:
                t = dt.datetime.fromisoformat(e["ts"]).replace(tzinfo=None)
            except (KeyError, ValueError):
                continue
            if t >= since:
                times.append(t)
        times.sort()
        pres = getattr(self.app, "presence", None)
        best: dict[dt.date, tuple[float, dt.datetime, dt.datetime]] = {}
        for a, b in zip(times, times[1:], strict=False):
            h = (b - a).total_seconds() / 3600
            if not QUIET_MIN_H <= h <= QUIET_MAX_H:
                continue
            if pres is not None:
                back = [y for _x, y in pres.offline(a.timestamp(), b.timestamp())]
                if any(y >= b.timestamp() - BACK_MIN * 60 for y in back):
                    continue  # the computer was off and caught up: not when you woke
            if h > best.get(b.date(), (0.0,))[0]:
                best[b.date()] = (h, a, b)
        if len(best) < LEARN_NIGHTS:
            return None
        bed = round(middle([a.hour * 60 + a.minute for _h, a, _b in best.values()]) / 30) * 30 % 1440
        wake = round(middle([b.hour * 60 + b.minute for _h, _a, b in best.values()]) / 30) * 30 % 1440
        if not (NIGHT_MIN_H * 60 <= (wake - bed) % 1440 <= NIGHT_MAX_H * 60 and WAKE_FROM <= wake <= WAKE_TO):
            return None
        return {"from": _hm(bed), "to": _hm(wake), "nights": len(best)}

    def usual_hours(self) -> dict | None:
        """The usual quiet hours as last learned (the alarm's suggestion reads them)."""
        u = self.state().get("usual")
        return u if isinstance(u, dict) and u.get("from") and u.get("to") else None

    def _raw(self, key: str) -> tuple[bool, object]:
        cur: object = self.app.settings.user()
        for k in key.split("."):
            if not isinstance(cur, dict) or k not in cur:
                return False, None
            cur = cur[k]
        return True, cur

    def _yours(self, key: str, last: dict) -> bool:
        """You set it yourself (not to what was learned last time)."""
        had, v = self._raw(key)
        return had and v != (last.get("to") or {}).get(key)

    def learn(self) -> str:
        """Move the night hours (and the morning) to when you're usually quiet. Returns the line told."""
        u = self.usual()
        if u:
            self._put(usual={**u, "at": now().isoformat(timespec="seconds")})
        s = self.app.settings
        if not u or not s.get("availability.learn_night"):
            return ""
        last = self.state().get("night") or {}
        if last.get("at") and now() - dt.datetime.fromisoformat(last["at"]) < dt.timedelta(
            days=UNDONE_DAYS if last.get("undone") else AGAIN_DAYS
        ):
            return ""
        bed, wake = _m(u["from"]), _m(u["to"])
        night = s.get("availability.night") or {}
        new: dict[str, str] = {}
        cur = f"{night.get('from') or '23:30'} to {night.get('to') or '07:00'}"
        if night.get("enabled") and not any(
            self._yours(k, last) for k in ("availability.night.from", "availability.night.to")
        ):
            try:
                off = _apart(bed, _m(night["from"])) >= LEARN_GAP_MIN or _apart(wake, _m(night["to"])) >= LEARN_GAP_MIN
            except (KeyError, ValueError):
                off = False
            if off:
                new = {"availability.night.from": u["from"], "availability.night.to": u["to"]}
        if s.get("availability.learn_morning"):
            for key, (add, form) in MORNING.items():
                v = str(s.get(key) or "")
                head, _, at = v.rpartition(" ")
                if self._yours(key, last) or head != form.rpartition(" ")[0] or "," in at:
                    continue  # yours, or not one time a day
                try:
                    if _apart(_m(at), wake + add) < LEARN_GAP_MIN:
                        continue
                except ValueError:
                    continue
                new[key] = form.format(_hm(wake + add))
        if not new:
            return ""
        was = {k: list(self._raw(k)) for k in new}
        for k, v in new.items():
            s.set(k, v)
        self._restart(new)
        self._put(night={"at": now().isoformat(timespec="seconds"), "from": was, "to": new})
        line = ""
        if "availability.night.from" in new:
            line = (
                f"Quiet hours at night (no calls) now run from {u['from']} to {u['to']}, not {cur}: that's when "
                f"you've been quiet on {u['nights']} of the last {LEARN_DAYS} days."
            )
        said = [MORNING_SAID[k].format(v.split(" ")[-1]) for k, v in new.items() if k in MORNING_SAID]
        if said:
            line += (" Mornings move with it: " if line else f"You're usually around from {u['to']}, so: ") + (
                "; ".join(said) + "."
            )
        self.app.events.emit("rhythm_night_learned", keys=sorted(new), nights=u["nights"])
        self.app.notify(line, kind="info", why="rhythm.night", buttons=[[("Undo", "rhy:night:undo")]])
        return line

    def _restart(self, keys) -> None:
        """Features whose timers read these settings take them now (their jobs are set at start)."""
        for mid in {k.split(".")[0] for k in keys} - {"availability"}:
            m = self.app.modules.get(mid)
            if m is not None and self.app.is_on(mid):
                try:
                    m.start()
                except Exception as e:
                    self.app.events.emit("module_failed", module=mid, error=f"{type(e).__name__}: {e}"[:300])

    def _undo_night(self) -> str:
        last = self.state().get("night") or {}
        if not last or last.get("undone"):
            return "Nothing to undo."
        for k, v in (last.get("to") or {}).items():
            if self.app.settings.get(k) == v:
                had, old = (last.get("from") or {}).get(k) or [False, None]
                if had:
                    self.app.settings.set(k, old)
                else:
                    self.app.settings.reset(k)
        self._restart(last.get("to") or {})
        self._put(night={**last, "undone": True, "at": now().isoformat(timespec="seconds")})
        self.app.events.emit("rhythm_night_undone")
        return "Back as it was; I'll leave your quiet hours alone for a month."

    # ------------------------------------------------------------------------------------- lighter days
    def day_start(self) -> dt.time:
        try:
            return dt.time.fromisoformat(self.app.settings.get("checkins.day_starts") or "05:00")
        except ValueError:
            return dt.time(5, 0)

    def day_of(self, t: dt.datetime | None = None) -> dt.date:
        s = self.day_start()
        return ((t or now()) - dt.timedelta(hours=s.hour, minutes=s.minute)).date()

    def lighter(self, day: dt.date | None = None) -> dict | None:
        """A lighter day (the check-in day, today unless given): {"why": "exam"|"heavy", "what"}, or None."""
        if not self.app.settings.get("notify.calm.lighter_after"):
            return None
        day = day or self.day_of()
        if self.state().get("not_today") == day.isoformat():
            return None
        start = dt.datetime.combine(day, self.day_start())
        prev = start - dt.timedelta(days=1)
        dl = self.app.modules.get("deadlines")
        if dl is not None and self.app.is_on("deadlines"):
            for it in dl.items().values():
                if it.get("kind") != "exam" or it.get("status") not in ("open", "done"):
                    continue
                try:
                    due = dt.datetime.fromisoformat(it["due"])
                except (KeyError, ValueError):
                    continue
                due = due.astimezone().replace(tzinfo=None) if due.tzinfo else due
                if prev <= due < start:
                    return {"why": "exam", "what": it.get("title") or "your exam"}
        st = self.app.modules.get("study")
        if st is not None and self.app.is_on("study"):
            h = sum(st.totals(1, last=prev.date()).values()) / 3600
            if h >= HEAVY_H:
                return {"why": "heavy", "what": f"{h:.0f} hours of study"}
        return None

    def lighter_limit(self, n: int) -> int:
        """Calm's daily limit today: half (rounded up) on a lighter day."""
        return max(1, -(-n // 2)) if n > 0 and self.lighter() else n

    def lighter_line(self, mark: bool = False) -> str:
        """The morning line, when today is a lighter one. mark: it's being sent (once a day)."""
        lt = self.lighter()
        if not lt:
            return ""
        day = self.day_of().isoformat()
        if mark and self.state().get("lighter_told") == day:
            return ""
        after = f"your exam ({lt['what']})" if lt["why"] == "exam" else f"yesterday's {lt['what']}"
        bits = ["fewer messages from me"]
        if self.app.is_on("checkins"):
            bits.append("the first check-in an hour later")
        if mark:
            self._put(lighter_told=day)
            self.app.events.emit("rhythm_lighter", why=lt["why"])
        return f"A lighter day after {after}: {' and '.join(bits)}."

    def tell_lighter(self) -> str:
        """Its own message, when Dreaming (whose morning message carries the line) is off."""
        if self.app.is_on("dreaming") or self.app.availability.focus_until():
            return ""
        line = self.lighter_line(mark=True)
        if line:
            self.app.notify(line, kind="info", why="rhythm.lighter", buttons=[[("Not today", "rhy:lighter:no")]])
        return line

    def _not_today(self) -> str:
        day = self.day_of()
        self._put(not_today=day.isoformat())
        ck = self.app.modules.get("checkins")
        if ck is not None and self.app.is_on("checkins"):
            ck.unlighten(day)
        self.app.events.emit("rhythm_lighter_cancelled")
        return "OK, a usual day."

    # ------------------------------------------------------------------------------------------ absence
    def last_seen(self) -> dt.datetime | None:
        for e in self.app.events.tail(1, kinds=set(ACTIVE)):
            try:
                return dt.datetime.fromisoformat(e["ts"]).replace(tzinfo=None)
            except (KeyError, ValueError):
                return None
        return None

    def quiet_week(self, t: dt.datetime | None = None) -> bool:
        """Busy, quiet for a week: what comes by itself waits for the evening bundle until then."""
        try:
            return dt.datetime.fromisoformat(self.state()["quiet_until"]) > (t or now())
        except (KeyError, ValueError, TypeError):
            return False

    def absence(self) -> str:
        """Nothing from you for availability.absence_days while Kurooto kept running: one gentle message."""
        try:
            days = int(self.app.settings.get("availability.absence_days") or 0)
        except (TypeError, ValueError):
            days = 0
        seen, t = self.last_seen(), now()
        if days <= 0 or seen is None or t - seen < dt.timedelta(days=days):
            return ""
        if (self.state().get("absence") or {}).get("seen") == seen.isoformat():
            return ""  # asked about this silence already
        pres = getattr(self.app, "presence", None)
        if pres is not None:
            off = sum(b - a for a, b in pres.offline(seen.timestamp(), t.timestamp()))
            if off > (t - seen).total_seconds() / 2:
                return ""  # Kurooto wasn't running most of the time: nothing to notice
        av = self.app.availability
        if av.night(t) or av.focus_until(t) or av.quiet_until(t) or self.quiet_week(t):
            return ""
        if getattr(self.app.power, "current", "") == "paused":
            return ""
        text = f"Haven't heard from you in {WORDS.get(days, f'{days} days')}. All good? Nothing's urgent."
        self._put(absence={"seen": seen.isoformat(), "asked": t.isoformat(timespec="seconds")})
        self.app.events.emit("rhythm_absence_asked", days=days)
        self.app.notify(
            text,
            kind="question",
            why="rhythm.absence",
            buttons=[[("I'm fine", "rhy:absence:fine"), ("Busy, quiet for a week", "rhy:absence:busy")]],
        )
        return text

    def _busy(self) -> str:
        until = (now() + dt.timedelta(days=QUIET_WEEK_DAYS)).replace(second=0)
        self.app.availability.set_quiet(until, reason="you said you're busy")
        self._put(quiet_until=until.isoformat())
        self.app.events.emit("rhythm_quiet_week", until=until.isoformat())
        text = (
            f"Quiet until {until:%a %d %b}: no calls, and what comes by itself waits for one message each evening. "
            "The alarm and your own reminders still come."
        )
        self.app.notify(text, kind="info", why=ASKED, buttons=[[("Undo", "rhy:quiet:undo")]])
        return "Quiet for a week."

    def _quiet_undo(self) -> str:
        if not self.quiet_week():
            return "Nothing to undo."
        self._put(quiet_until=None)
        self.app.availability.set_quiet(None)
        return "Back to usual."

    # ------------------------------------------------------------------------------------------ buttons
    def button(self, ref: str, act: str) -> str:
        """rhy:night:undo, rhy:lighter:no, rhy:absence:fine|busy, rhy:quiet:undo."""
        if ref == "night" and act == "undo":
            return self._undo_night()
        if ref == "lighter" and act == "no":
            return self._not_today()
        if ref == "absence" and act == "busy":
            return self._busy()
        if ref == "absence" and act == "fine":
            return "Good to hear."
        if ref == "quiet" and act == "undo":
            return self._quiet_undo()
        return "That button is out of date."
