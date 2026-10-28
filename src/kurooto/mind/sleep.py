"""Kurooto sleeps (Brain, 0.8.14, `mind.sleep.on`, on with Brain): while it's asleep it doesn't talk unless woken.

Its sleep window follows yours (`mind.sleep.follow_owner`, on):
    - With the wake-up alarm set, from your bedtime to the alarm (the same nights availability.night uses); otherwise
      Kurooto's own night hours (availability.night's from and to, whether or not they hold calls).
    - Your phone's readings refine it, when the screen, light and charging sensors are on (/senses): the screen off,
      the room dark and the phone charging for DOWN_MIN minutes is your sleep onset (up to EARLY_H hours before the
      window, which then starts there); the phone in use at the window's start holds it back, up to LATE_H hours (you're
      up late); the phone in use in the window's last UP_MIN minutes, the phone's own alarm, "I'm up" or the alarm
      ringing end it (you're up).
    - `mind.sleep.window` ("00:30-08:00") sets it by hand instead; follow_owner off uses the night hours as they are.
    - (0.8.18, `mind.sleep.desk_holds`, on) You at this computer (Face presence: your face, or your keyboard and mouse
      while it watches) hold the window back, by hand-set or not: it starts `mind.sleep.desk_after_min` (15) minutes
      after you were last there, up to the window's end. Once it's asleep the desk no longer holds it (the latch,
      `slept_until`): only being woken does, and after a wake the desk holds it again.

States: "drowsy" in the DROWSY_MIN minutes before the window (quieter: nothing is said aloud by itself), "asleep" in
it, "awake" otherwise. Asleep:
    - What Kurooto starts by itself isn't sent or said (core/notify.py asks hold()); it waits here and goes out, through
      the gate and Calm as usual, once the window is over. Exempt, never held: alarms, reminders and calls you asked
      for, close deadlines, approvals and questions you're waiting on, and every answer to you.
    - The being's eyes close (status reads state()).
    - (0.8.18, `mind.sleep.senses_off`, on) Its senses close too: Face presence pauses ("Kurooto is asleep") and Voice
      stops listening (senses_off()). Then only you wake it: /wake, a message, a tap or a call; its name can't, since
      nothing listens. Switch off: Voice still listens and its name wakes it (wake(app, "its name")).
    - (0.9.0) Using the dashboard or the phone app wakes it too (core/here.py's owner_here, as a tap does); your face
      or voice alone don't (that's mind.sleep.follow_desk).
    - (0.9.0, `mind.sleep.follow_desk`, on) The desk wakes it too: a look that opens a talk, talking over it with a
      turn, or a Live turn (DESK_WAKES); and Face presence seeing you at the desk in the night's last UP_MIN minutes,
      while it's awake or woken, is you being up (desk_up, from the minute's tick): the night ends, what waited goes.
    - Woken, it answers, and dozes off again after `mind.sleep.wake_minutes` (20) quiet minutes. What waited still
      waits for the morning: being woken to answer isn't being up.
    - The Brain's heavy work prefers this window (mind/senses/intero.py: gated()).

Public, for the other parts and add-ons:
    state(app) -> "awake" | "drowsy" | "asleep"
    asleep(app) -> bool                state(app) == "asleep", kept CACHE_S (for checks made every second)
    senses_off(app) -> bool            (0.8.18) asleep with mind.sleep.senses_off on: cameras and microphones stop
    wake(app, why, minutes=20)
    window(app) -> (start, end) | None, the current night's or the next one's, as local times
    last_night(app) -> (fell asleep, window end) | None   (0.9.0) the night just had, for the alarm (alarm.sleep_aware)
    external_asleep(app, asleep, source)  (0.9.0) an add-on's reading that you're asleep or awake again: always noted;
                                       it moves the night's start with mind.sleep.follow_external on (off)
    body_asleep(app, asleep)           the same, with source "body" (the name an add-on already probes)

State: `<state>/mind-sleep.json` (until when it's woken, when you got up, what waits, the last state, wakes a day).
Numbers and reason ids only, besides the waiting messages themselves; on this computer only.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "sleep"  # its switch: mind.sleep.on
register_defaults(
    "mind",
    {
        "sleep": {
            "on": True,  # Kurooto sleeps in your sleep window: nothing it starts by itself is sent or said then
            "follow_owner": True,  # the window follows your bedtime, alarm and phone; off: the night hours as set
            "window": "",  # "00:30-08:00" sets its sleep by hand ("" = follow the above)
            "wake_minutes": 20,  # woken by its name or a message, it dozes off again after this many quiet minutes
            # (0.8.18) asleep, Face presence pauses and Voice stops listening: only /wake, a message, a tap or a call
            # wakes it (its name can't). Off: Voice still listens while it sleeps and its name wakes it
            "senses_off": True,
            # (0.8.18) you at this computer (Face presence: your face, or keyboard and mouse) keep it from falling
            # asleep: the window starts desk_after_min minutes after you were last there
            "desk_holds": True,
            "desk_after_min": 15,
            # (0.9.0) the desk wakes it and ends its night: a look that opens a talk, talking over it or a Live turn
            # wakes it as its name does, and Face presence seeing you at the desk in the night's last 90 minutes
            # (awake or woken) is you being up, so what waited goes out
            "follow_desk": True,
            # (0.9.0) an add-on's own reading that you're asleep (a dark, quiet room, you away) moves its night's start
            # as your phone's does; off: the reading is only noted
            "follow_external": False,
        }
    },
)

FILE = "mind-sleep.json"
DROWSY_MIN = 30  # drowsy this long before the window
DOWN_MIN = 20  # screen off, dark and charging this long: your sleep onset
EARLY_H = 2  # an onset counts this far before the window at most
LATE_H = 2  # the phone in use holds the window back this long at most
UP_MIN = 90  # the phone in use this close to the window's end: you're up
RECENT_MIN = 15  # "in use" means in the last this many minutes
HELD_MAX = 200
WAKE_KINDS = {"message_in": "a message", "button_tapped": "a tap", "call_answered": "a call"}
UP_KINDS = {"alarm_up_now": "you said you're up", "alarm_rang": "the alarm rang"}
NAME_WHYS = ("its name", "the wake word", "tapped")  # what opened Voice's talk (voice/gate.py; 0.9.0: a tap)
DESK_WAKES = {"voice_portal": "a look", "voice_barge": "talking over it", "voice_live": "a Live turn"}  # (follow_desk)
DESK_UP_S = 120  # (follow_desk) Face presence had you at the desk this recently: you're at it now
HERE_WAKES = ("dashboard", "phone")  # (0.9.0) owner_here vias that wake it, as a tap does (core/here.py)
EVENTS = (*WAKE_KINDS, *UP_KINDS, *DESK_WAKES, "owner_here")  # the events it listens to
EXEMPT_KINDS = ("call", "approval", "reminder")
DUMP_SKIP = ("rid", "extra", "state_read", "before")
CACHE_S = 5.0  # asleep() is kept this long: Face presence and Voice ask every second

_lock = threading.Lock()
_cache: dict[int, tuple[float, bool]] = {}


def on(app: App) -> bool:
    return mind.part_on(app, PART)


def _load(app: App) -> dict:
    return jload(app.paths.state / FILE, {}) or {}


def _save(app: App, st: dict) -> None:
    jsave(app.paths.state / FILE, st)


# ------------------------------------------------------------------------------------------------- the window
def _hm(s) -> dt.time | None:
    try:
        return dt.time.fromisoformat(str(s).strip())
    except ValueError:
        return None


def _manual(app: App) -> tuple[dt.time, dt.time] | None:
    """mind.sleep.window, "HH:MM-HH:MM"; None when unset or unreadable."""
    raw = str(app.settings.get("mind.sleep.window") or "").strip()
    if "-" not in raw:
        return None
    a, b = (_hm(x) for x in raw.split("-", 1))
    return (a, b) if a and b and a != b else None


def _hours(app: App) -> tuple[dt.time, dt.time]:
    """Kurooto's own night hours (availability.night from/to), whether or not they hold calls."""
    n = app.settings.get("availability.night") or {}
    return _hm(n.get("from") or "23:30") or dt.time(23, 30), _hm(n.get("to") or "07:00") or dt.time(7, 0)


def _daily(t: dt.datetime, start: dt.time, end: dt.time) -> list[tuple[dt.datetime, dt.datetime]]:
    """The windows of these hours around t: the nights starting yesterday, today and tomorrow."""
    out = []
    for d in (t.date() - dt.timedelta(days=1), t.date(), t.date() + dt.timedelta(days=1)):
        s = dt.datetime.combine(d, start)
        e = dt.datetime.combine(d if end > start else d + dt.timedelta(days=1), end)
        out.append((s, e))
    return out


def _alarm_nights(app: App) -> list[tuple[dt.datetime, dt.datetime]]:
    """Bedtime to the alarm, for the nights the wake-up alarm covers (modules/alarm.py through availability)."""
    try:
        return list(app.availability._sleep_windows())
    except Exception:
        return []


def _phone_on(app: App, *sensors: str) -> bool:
    from kurooto.mind.senses import phone

    return all(phone.enabled(app, s) for s in sensors)


def _rows(app: App, sensor: str, since: float) -> list[dict]:
    from kurooto.mind.senses import store

    try:
        return store.events(app, f"phone:{sensor}", since)
    except Exception:
        return []


def _in_use(r: dict) -> bool:
    return r["kind"] in ("on_min", "unlocks") and r["n"] > 0


def phone_now(app: App, t: dt.datetime) -> dict:
    """What the phone's 5-minute readings say about the last 3 hours: {"down_since": ts | None (screen off, dark and
    charging since then, unbroken up to now), "last_use": ts | None (the screen last in use), "alarm": ts | None (its
    next alarm)}. Empty when follow_owner is off or the sensors are."""
    out: dict = {}
    if not app.settings.get("mind.sleep.follow_owner"):
        return out
    ts = t.timestamp()
    since = ts - 3 * 3600
    if _phone_on(app, "screen"):
        used = [r["t"] for r in _rows(app, "screen", since) if _in_use(r) and r["t"] <= ts]
        out["last_use"] = max(used) if used else None
    if _phone_on(app, "screen", "light", "charging"):
        screen, light, charge = (_rows(app, s, since) for s in ("screen", "light", "charging"))
        fresh = all(rows and ts - rows[-1]["t"] <= RECENT_MIN * 60 for rows in (screen, light, charge))
        if fresh:
            broken = [r["t"] for r in screen if _in_use(r)]
            broken += [r["t"] for r in light if r["target"] and r["target"] != "dark"]
            broken += [r["t"] for r in charge if r["kind"] == "on" and r["n"] <= 0]
            broken = [b for b in broken if b <= ts]
            first = min(r["t"] for rows in (screen, light, charge) for r in rows)
            out["down_since"] = (max(broken) + 300) if broken else first
    if _phone_on(app, "alarm"):
        rows = _rows(app, "alarm", ts - 86400)
        if rows and rows[-1]["n"] > 0:
            at = float(rows[-1]["n"])
            out["alarm"] = at / 1000 if at > 1e11 else at  # the phone says milliseconds
    return out


def _desk(app: App) -> float | None:
    """(0.8.18, mind.sleep.desk_holds) When Face presence last had you at this computer (time.time()), or None: the
    switch off, Face presence off or not watching, or you've stepped away."""
    if not app.settings.get("mind.sleep.desk_holds"):
        return None
    try:
        face = app.modules.get("face")
        if face is None or not app.is_on("face"):
            return None
        return face.desk_seen_at()
    except Exception:
        return None


def _desk_after(app: App) -> float:
    try:
        return max(1.0, float(app.settings.get("mind.sleep.desk_after_min") or 15))
    except (TypeError, ValueError):
        return 15.0


def _refine(app: App, s: dt.datetime, e: dt.datetime, t: dt.datetime, ph: dict, up_at: float | None):
    """One night, moved by what's known about you tonight: your onset, staying up, the phone's alarm, getting up, and
    (0.8.18) you at the desk."""
    if ph.get("alarm") and not app.settings.get("mind.sleep.window"):
        a = dt.datetime.fromtimestamp(ph["alarm"]).replace(microsecond=0)
        if s < a and abs((a - e).total_seconds()) <= 3 * 3600:
            e = a  # the phone's own alarm is when you get up
    if s - dt.timedelta(hours=EARLY_H) <= t < e:
        down = ph.get("down_since")
        if down is not None and t.timestamp() - down >= DOWN_MIN * 60:
            onset = dt.datetime.fromtimestamp(down).replace(microsecond=0)
            if s - dt.timedelta(hours=EARLY_H) <= onset < s:
                s = onset  # asleep early: it sleeps with you
        elif s <= t < s + dt.timedelta(hours=LATE_H):
            last = ph.get("last_use")
            if last is not None and t.timestamp() - last <= RECENT_MIN * 60:
                held_back = dt.datetime.fromtimestamp(last).replace(microsecond=0) + dt.timedelta(minutes=RECENT_MIN)
                s = max(s, min(held_back, s + dt.timedelta(hours=LATE_H)))  # still up: it waits for you
    last = ph.get("last_use")
    if last is not None:
        used = dt.datetime.fromtimestamp(last).replace(microsecond=0)
        if max(s + dt.timedelta(hours=1), e - dt.timedelta(minutes=UP_MIN)) <= used < e and used <= t:
            e = used  # the phone in use near the end: you're up
    if up_at is not None:
        u = dt.datetime.fromtimestamp(up_at).replace(microsecond=0)
        if s <= u < e:
            e = u
    ext = ph.get("external")
    if ext is not None and s - dt.timedelta(hours=EARLY_H) <= t < e:  # (0.9.0, follow_external) an add-on's reading
        onset = dt.datetime.fromtimestamp(ext).replace(microsecond=0)
        if s - dt.timedelta(hours=EARLY_H) <= onset < s and onset <= t:
            s = onset
    desk = ph.get("desk")
    if desk is not None and s <= t < e:  # (0.8.18) at the desk: it waits for you, up to the window's end
        held = dt.datetime.fromtimestamp(desk).replace(microsecond=0) + dt.timedelta(minutes=_desk_after(app))
        if held > s:
            s = min(held, e)
    return s, e


def window(app: App, t: dt.datetime | None = None) -> tuple[dt.datetime, dt.datetime] | None:
    """Tonight's sleep window (start, end) as local times: the one it's in, else the next one. None with sleep off."""
    if not on(app):
        return None
    t = t or now()
    manual = _manual(app)
    if manual:
        nights = _daily(t, *manual)
    else:
        nights = _alarm_nights(app) if app.settings.get("mind.sleep.follow_owner") else []
        nights += [
            (s, e) for s, e in _daily(t, *_hours(app)) if not any(a < e and s < b for a, b in nights)
        ]  # the alarm's nights take the place of the fixed hours they overlap
    ph = {} if manual else phone_now(app, t)
    st = _load(app)
    up = st.get("up_at")
    ext = _external_since(app, st)
    if ext is not None:
        ph = {**ph, "external": ext}
    if float(st.get("slept_until") or 0) <= t.timestamp():  # (0.8.18) asleep already: the desk no longer holds it
        desk = _desk(app)
        if desk is not None:
            ph = {**ph, "desk": desk}
    out = []
    for s, e in nights:
        if s >= e:
            continue
        s, e = _refine(app, s, e, t, ph, float(up) if up else None)  # by hand: only "I'm up" moves it
        if e > t and s < e:
            out.append((s, e))
    return min(out) if out else None


def external_asleep(app: App, asleep: bool, source: str = "addon") -> None:
    """(0.9.0) An add-on's own reading that you're asleep (asleep=True: since now) or awake again. Always noted (in
    the state file, and as a "<source>_sleep" event with the state only, as add-ons wrote before); it moves the night's
    start only with mind.sleep.follow_external on (_refine, like the phone's onset). Never raises."""
    try:
        src = "".join(c for c in str(source or "addon").lower() if c.isalnum() or c == "_")[:24] or "addon"
        t = now().timestamp()
        with _lock:
            st = _load(app)
            ext = st.setdefault("external", {})
            was = ext.get(src) or {}
            if bool(asleep):
                ext[src] = {"since": float(was.get("since") or t) if was.get("asleep") else t, "asleep": True}
            else:
                ext[src] = {"asleep": False, "at": t}
            _save(app, st)
        app.events.emit(f"{src}_sleep", state="asleep" if asleep else "awake")
    except Exception as e:
        try:
            app.events.emit("mind_sleep_failed", error=f"external: {type(e).__name__}"[:60])
        except Exception:
            pass


def body_asleep(app: App, asleep: bool) -> None:
    """The name an add-on already probes for (getattr): external_asleep with its source."""
    external_asleep(app, asleep, "body")


def _external_since(app: App, st: dict) -> float | None:
    """(follow_external) The earliest onset an add-on reports and still holds, or None (the switch off, or none)."""
    if not app.settings.get("mind.sleep.follow_external") or app.settings.get("mind.sleep.window"):
        return None
    got = [float(v["since"]) for v in (st.get("external") or {}).values() if v.get("asleep") and v.get("since")]
    return min(got) if got else None


# ------------------------------------------------------------------------------------------------- the state
def _woken(st: dict, t: dt.datetime) -> bool:
    return float(st.get("woke_until") or 0) > t.timestamp()


def resting(app: App, t: dt.datetime | None = None) -> bool:
    """Inside its sleep window, woken to answer or not: what it starts by itself waits."""
    t = t or now()
    w = window(app, t)
    return bool(w and w[0] <= t < w[1])


def state(app: App, t: dt.datetime | None = None) -> str:
    """Its state now: "awake", "drowsy" (the half hour before its window) or "asleep" (in it, and not woken)."""
    if not on(app):
        return "awake"
    t = t or now()
    w = window(app, t)
    if not w:
        return "awake"
    s, e = w
    if s <= t < e:
        st = _load(app)
        if _woken(st, t):
            return "awake"
        if float(st.get("slept_until") or 0) < e.timestamp():  # (0.8.18) the latch: the desk can't undo this
            with _lock:
                st = _load(app)
                st["slept_until"] = e.timestamp()
                night = st.get("night") or {}
                if float(night.get("until") or 0) <= s.timestamp():  # (0.9.0) a new night: its onset, for last_night
                    st["night"] = {"at": s.timestamp(), "until": e.timestamp()}
                _save(app, st)
        return "asleep"
    if s - dt.timedelta(minutes=DROWSY_MIN) <= t < s:
        return "drowsy"
    return "awake"


def asleep(app: App) -> bool:
    """state(app) == "asleep", kept CACHE_S: Face presence and Voice ask every second."""
    m = time.monotonic()
    hit = _cache.get(id(app))
    if hit is not None and m - hit[0] < CACHE_S:
        return hit[1]
    try:
        v = state(app) == "asleep"
    except Exception:
        v = False
    _cache[id(app)] = (m, v)
    return v


def last_night(app: App, t: dt.datetime | None = None) -> tuple[dt.datetime, dt.datetime] | None:
    """(0.9.0) The night just had or still on: (when it fell asleep, when the window ends), the onset as it was when
    it first went to sleep (your phone, the desk, an add-on all count). None when it hasn't slept in the last day."""
    t = t or now()
    night = _load(app).get("night") or {}
    a, b = float(night.get("at") or 0), float(night.get("until") or 0)
    if not a or not b or a > t.timestamp() or t.timestamp() - a > 86400:
        return None
    return dt.datetime.fromtimestamp(a).replace(microsecond=0), dt.datetime.fromtimestamp(b).replace(microsecond=0)


def senses_off(app: App) -> bool:
    """(0.8.18, mind.sleep.senses_off) Asleep with the switch on: Face presence pauses and Voice stops listening (and
    the Body add-on's phone camera and mic, which read this too)."""
    return bool(app.settings.get("mind.sleep.senses_off")) and asleep(app)


def wake(app: App, why: str, minutes: int = 20) -> None:
    """Woken (its name, a message from you): awake for `minutes`, each wake from now. Nothing changes when it isn't
    asleep or resting, beyond keeping it awake that long if the window starts meanwhile."""
    if not on(app):
        return
    t = now()
    was = state(app, t)
    with _lock:
        st = _load(app)
        st["woke_until"] = max(float(st.get("woke_until") or 0), t.timestamp() + max(1, int(minutes)) * 60)
        st["woke_why"] = str(why)[:40]
        st.pop("slept_until", None)  # (0.8.18) woken: the desk holds it again
        if was == "asleep":
            day = st.setdefault("wakes", {})
            day[t.date().isoformat()] = int(day.get(t.date().isoformat(), 0)) + 1
        _save(app, st)
    _cache.pop(id(app), None)  # its senses come back at once
    _changed(app)


def up(app: App, why: str) -> int:
    """You're up (you said so, the alarm rang): tonight's sleep ends now and what waited goes out."""
    if not on(app):
        return 0
    with _lock:
        st = _load(app)
        st["up_at"] = now().timestamp()
        st["up_why"] = str(why)[:40]
        _save(app, st)
    _changed(app)
    return release(app)


def _changed(app: App) -> str:
    """Note the state, and say a change to the event log and open pages (the being's eyes), once."""
    s = state(app)
    with _lock:
        st = _load(app)
        was = st.get("last_state")
        if was == s:
            return s
        st["last_state"] = s
        _save(app, st)
    try:
        app.events.emit("mind_sleep", state=s, was=was or "")
    except Exception:
        pass
    live = getattr(app, "live", None)
    if live is not None:
        try:
            live.push({"t": "mind", "kind": "sleep", "state": s})
        except Exception:
            pass
    return s


def on_event(app: App, rec: dict) -> None:
    """Events as they happen (modules/mind.py mirrors them here): you waking it, or getting up."""
    if not on(app):
        return
    kind = str(rec.get("kind") or "")
    try:
        if kind in WAKE_KINDS and resting(app):
            wake(app, WAKE_KINDS[kind], _wake_minutes(app))
        elif kind == "voice_portal" and rec.get("open") and rec.get("why") in NAME_WHYS and resting(app):
            wake(app, "its name", _wake_minutes(app))
        elif _desk_wake(app, kind, rec) and resting(app):  # (0.9.0, follow_desk) a look, talking over it, Live
            wake(app, DESK_WAKES[kind], _wake_minutes(app))
        elif kind == "owner_here" and rec.get("via") in HERE_WAKES and resting(app):  # you used the board or the app
            wake(app, f"you used the {rec.get('via')}", _wake_minutes(app))
        elif kind in UP_KINDS:
            up(app, UP_KINDS[kind])
    except Exception as e:  # never in the way of the event that came
        app.events.emit("mind_sleep_failed", error=f"{type(e).__name__}"[:60])


def _desk_wake(app: App, kind: str, rec: dict) -> bool:
    """(0.9.0, mind.sleep.follow_desk) You started a talk at the desk: a look opened it (gate.LOOKED), you talked
    over it with a turn, or Gemini Live answered you. Asleep with senses_off, nothing listens, so this matters while
    it's drowsy, woken, or with senses_off off."""
    if kind not in DESK_WAKES or not app.settings.get("mind.sleep.follow_desk"):
        return False
    if kind == "voice_portal":
        return bool(rec.get("open")) and rec.get("why") == "looked at"
    if kind == "voice_barge":
        return rec.get("outcome") == "turn"
    return rec.get("stage") == "answered"


def desk_up(app: App, t: dt.datetime | None = None) -> bool:
    """(0.9.0, mind.sleep.follow_desk) Face presence has you at the desk in the night's last UP_MIN minutes while
    it's awake or woken (never while asleep: the latch): you're up, so the night ends and what waited goes out. The
    minute's tick asks. True when it ended the night."""
    if not on(app) or not app.settings.get("mind.sleep.follow_desk"):
        return False
    t = t or now()
    w = window(app, t)
    if not w or not (w[0] <= t < w[1]) or t < w[1] - dt.timedelta(minutes=UP_MIN) or state(app, t) == "asleep":
        return False
    try:
        face = app.modules.get("face")
        seen = face.desk_seen_at() if face is not None and app.is_on("face") else None
    except Exception:
        seen = None
    if seen is None or t.timestamp() - seen > DESK_UP_S:
        return False
    up(app, "you're at the desk")
    return True


def _wake_minutes(app: App) -> int:
    try:
        return max(1, int(app.settings.get("mind.sleep.wake_minutes") or 20))
    except (TypeError, ValueError):
        return 20


# ------------------------------------------------------------------------------------------------- holding
def exempt(app: App, msg) -> bool:
    """Never held: answers to you, and what Calm always lets through (reminders and calls you set, the alarm, close
    deadlines, approvals)."""
    from kurooto.core.calm import ASKED

    if not msg.why or msg.why == ASKED or msg.kind in EXEMPT_KINDS or msg.urgent:
        return True
    calm = getattr(app, "calm", None)
    try:
        return bool(calm is not None and calm.exempt(msg.why, msg.kind, msg.urgent, msg.due))
    except Exception:
        return False


def hold(app: App, msg) -> bool:
    """core/notify.py asks before anything goes out: True when it waits here because Kurooto is asleep."""
    if not on(app) or exempt(app, msg) or not resting(app):
        return False
    body = {k: v for k, v in msg.__dict__.items() if k not in DUMP_SKIP}
    with _lock:
        st = _load(app)
        held = [*(st.get("held") or []), {"at": time.time(), "msg": body}]
        st["held"] = held[-HELD_MAX:]
        _save(app, st)
    app.events.emit("mind_sleep_held", why=str(msg.why)[:60])
    return True


def held_count(app: App) -> int:
    return len(_load(app).get("held") or [])


def release(app: App) -> int:
    """Once it's no longer resting: what waited goes out, in the order it came, through the gate and Calm as any
    message does (their limits apply). A question dealt with meanwhile doesn't. How many went."""
    if on(app) and resting(app):
        return 0
    with _lock:
        st = _load(app)
        held = st.get("held") or []
        if not held:
            return 0
        st["held"] = []
        _save(app, st)
    from kurooto.core.notify import Message

    n = 0
    for h in held:
        body = {k: v for k, v in (h.get("msg") or {}).items() if k in Message.__dataclass_fields__}
        if not body.get("text"):
            continue
        if body.get("map_kind") == "ask":
            try:
                from kurooto.core.ask import OPEN

                q = app.ask.get(body.get("map_ref") or "")
                if not q or q.get("status") not in OPEN:
                    continue
            except Exception:  # noqa: S110 (can't tell: it goes)
                pass
        try:
            app.notifier.send(body.pop("text"), **body)
            n += 1
        except Exception as e:
            app.events.emit("mind_sleep_failed", error=f"release: {type(e).__name__}"[:60])
    if n:
        app.events.emit("mind_sleep_released", n=n)
    return n


def tick(app: App, payload: dict | None = None) -> str | None:
    """Every minute: the state is noted (a change is said once), and once the night is over what waited goes out."""
    if not on(app):
        if held_count(app):
            release(app)  # turned off while asleep: nothing stays held
        return None
    s = _changed(app)
    try:
        desk_up(app)  # (0.9.0, follow_desk) at the desk near the night's end: you're up
    except Exception as e:
        app.events.emit("mind_sleep_failed", error=f"desk: {type(e).__name__}"[:60])
    if not resting(app) and held_count(app):
        release(app)
    return s


# ------------------------------------------------------------------------------------------------- what you see
def summary(app: App) -> dict:
    """For /mind, the console and status: the state, the window, what waits, the wakes tonight. Numbers only."""
    t = now()
    w = window(app, t)
    st = _load(app)
    return {
        "on": on(app),
        "state": state(app, t),
        "start": w[0].isoformat() if w else None,
        "end": w[1].isoformat() if w else None,
        "held": len(st.get("held") or []),
        "woke_until": st.get("woke_until") if _woken(st, t) else None,
        "wakes_today": int((st.get("wakes") or {}).get(t.date().isoformat(), 0)),
    }


def line(app: App) -> str:
    """One plain line for /mind."""
    if not on(app):
        return "Sleep: off."
    s = summary(app)
    if not s["start"]:
        return "Sleep: no window."
    a, b = (dt.datetime.fromisoformat(x) for x in (s["start"], s["end"]))
    when = f"{a:%H:%M} to {b:%H:%M}"
    if s["state"] == "asleep":
        out = f"Sleep: asleep until {b:%H:%M}"
    elif s["state"] == "drowsy":
        out = f"Sleep: drowsy, asleep from {a:%H:%M} to {b:%H:%M}"
    elif s["woke_until"]:
        out = f"Sleep: woken, dozing off again by {dt.datetime.fromtimestamp(s['woke_until']):%H:%M} ({when})"
    else:
        out = f"Sleep: awake; tonight {when}"
    return out + (f", {s['held']} waiting for the morning." if s["held"] else ".")


def forget(app: App) -> None:
    (app.paths.state / FILE).unlink(missing_ok=True)
