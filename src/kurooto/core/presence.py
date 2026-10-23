"""Going offline and coming back: a message when Kurooto stops or its computer goes away, and when it's back.

Going offline
    A clean stop (`kurooto stop` or `off`, the dashboard, signing out or shutting down where the system says so):
    before it exits, Kurooto sends "Kurooto is going offline (shutting down): calls and reminders will wait until it's
    back". It takes at most about 2.5 seconds and never holds up a shutdown longer. An update's restart says nothing.
    Sleep, a crash or a lost network: this computer can't speak, so your call line (if it's set up) notices the
    computer's link gone for `after_min` minutes and says so itself (on the phone app, and on Telegram once you've
    allowed it to keep your bot's token). Without a call line there's no message for those.

Coming back
    When Kurooto starts, when the computer wakes up (the clock jumps between two of its ticks), and when Telegram or
    the call line can be reached again after the network was down (repeated failures, timed from the first): one
    message, "Kurooto is back online (offline since 22:10, 7 h)" or "Back online: the network was down from 14:02 to
    14:31 (29 min)", with what it caught up on. Messages that couldn't reach Telegram meanwhile follow, in order,
    marked as delayed.

Not for anything shorter than `after_min` (except right after a goodbye: you were told it went, so you're told it's
back), nor an update's restart. Several sleeps or drops close together give one message: it goes once the computer has
been up for a minute. At night (or in focus time) it waits for the morning; if nothing said Kurooto had gone, it's
dropped then. Never a call.

Settings: notify.presence {on, after_min, channels ("telegram", "app"), line, line_telegram (None: asked once)}.
State: state/presence.json (heartbeat, the last stop, the message waiting, the offline periods of the last 15 days),
state/net-outbox.jsonl (Telegram messages kept while the network was down). Events: presence_offline, presence_online.

The offline periods (any length, and whether or not presence messages are on) are what core/health.py subtracts
before it calls something quiet: a sync that couldn't run while the lid was shut hasn't failed.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import threading
import time
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.notify import Message
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "notify",
    {
        "presence": {
            "on": True,  # say when Kurooto goes offline and when it's back
            "after_min": 10,  # away for less than this: nothing is said
            "channels": ["telegram"],  # where: "telegram", "app" (the phone app)
            "line": True,  # your call line says so when this computer can't (sleep, a crash, a lost network)
            "line_telegram": None,  # may your call line keep your bot's token for that? None: asked once
        }
    },
)

CHANNELS = ("telegram", "app")
TICK_S = 20  # how often it looks (and notices the clock jumping after sleep)
JUMP_S = 60  # a tick this much later than expected: the computer was asleep
SETTLE_S = 60  # the "back" message waits until the computer has been up this long (flapping makes one message)
ALIVE_S = 60  # the heartbeat on disk: when it was last running, if it didn't stop cleanly
BYE_S = 2.5  # the goodbye never takes longer than this
PROBE_S = 60  # while the network is down, try Telegram this often
OUTBOX_MAX = 200
GAPS_KEEP_S = 15 * 86400  # offline periods kept for core/health.py
GAPS_MAX = 400
ASK_AGAIN_S = 30 * 86400
WHY_UNKNOWN = "asleep, off or without internet"
LINE_ASK = (
    "When this computer goes offline without warning (sleep, a crash, a lost network), your call line can tell you "
    "here on Telegram. For that it keeps your Telegram bot's token on your Cloudflare account, beside your Gemini key. "
    "Allow it?"
)


def _network(err: BaseException) -> bool:
    """A request that never got an answer (no network, DNS, a timeout), not a "no" from the other side."""
    from kurooto.modules.telegram.api import TelegramError

    return isinstance(err, OSError) and not isinstance(err, TelegramError)


def when(ts: float, ref: float | None = None) -> str:
    """22:10, or Mon 22:10 on another day, or 12 Oct 22:10 a week or more before."""
    t, r = dt.datetime.fromtimestamp(ts), dt.datetime.fromtimestamp(ref if ref is not None else time.time())
    if t.date() == r.date():
        return f"{t:%H:%M}"
    if abs((r.date() - t.date()).days) < 7:
        return f"{t:%a %H:%M}"
    return f"{t.day} {t:%b %H:%M}"


def span(seconds: float) -> str:
    """40 min, 1 h 20 min, 7 h, 3 days."""
    m = max(1, round(seconds / 60))
    if m < 60:
        return f"{m} min"
    h, rest = divmod(m, 60)
    if h < 3 and rest:
        return f"{h} h {rest} min"
    if h < 48:
        return f"{round(m / 60)} h"
    return f"{round(m / 1440)} days"


class Presence:
    def __init__(self, app: App, clock=time.time):
        self.app = app
        self.clock = clock
        self.file = app.paths.state / "presence.json"
        self.outbox = app.paths.state / "net-outbox.jsonl"
        self._lock = threading.RLock()
        self._out_lock = threading.Lock()
        self._last: float | None = None  # the previous tick, by the wall clock
        self._alive = 0.0
        self._asked = 0.0
        self._said_bye = False
        self.net_fail_since: float | None = None  # first failure to reach Telegram or the call line since a success
        self.net_fails = 0
        self._net_try = 0.0
        app.ask.hooks["presence.line"] = self._line_answer

    # -------------------------------------------------------------------------------------- settings
    def setting(self, key: str):
        return (self.app.settings.get("notify.presence") or {}).get(key)

    def on(self) -> bool:
        return bool(self.setting("on"))

    def after_s(self) -> float:
        try:
            return max(1.0, float(self.setting("after_min") or 10)) * 60
        except (TypeError, ValueError):
            return 600.0

    def channels(self) -> list[str]:
        out = [c for c in (self.setting("channels") or []) if c in CHANNELS]
        if "telegram" in out and getattr(self.app, "app_main", lambda: False)():  # no Telegram: the phone app says it
            out = [c for c in out if c != "telegram"] + ([] if "app" in out else ["app"])
        return out

    def _load(self) -> dict:
        return jload(self.file, {}) or {}

    def _save(self, st: dict) -> None:
        jsave(self.file, st)

    # ------------------------------------------------------------------------------------ the daemon
    def start(self) -> None:
        """At the daemon's start: was it away long enough to say it's back? From its last stop, or else from the last
        heartbeat (it didn't stop cleanly: a crash, the power, being killed)."""
        t = self.clock()
        with self._lock:
            st = self._load()
            stop, alive = st.pop("stop", None), st.get("alive")
            st["alive"] = self._alive = t
            self._save(st)
        self._last = t
        if isinstance(stop, dict) and stop.get("at"):
            kind = "restart" if stop.get("reason") == "restart" else "stop"
            self.went_away(float(stop["at"]), t, kind, told=bool(stop.get("told")), why=str(stop.get("reason") or ""))
        elif alive:
            self.went_away(float(alive), t, "off")

    async def watch(self, stop: asyncio.Event) -> None:
        """The daemon's presence loop: a tick every TICK_S seconds."""
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.tick)
            except Exception as e:
                self.app.events.emit("presence_failed", error=f"{type(e).__name__}: {e}"[:200])
            try:
                await asyncio.wait_for(stop.wait(), timeout=TICK_S)
            except TimeoutError:
                pass

    def tick(self) -> None:
        t = self.clock()
        last, self._last = self._last, t
        if last is not None and t - last > TICK_S + JUMP_S:  # the clock jumped: the computer was asleep
            self.went_away(last, t, "sleep")
        if t - self._alive >= ALIVE_S:
            with self._lock:
                st = self._load()
                st["alive"] = self._alive = t
                self._save(st)
        if self.net_fail_since is not None and t - self._net_try >= PROBE_S:
            self._probe()
        self._maybe_send(t)
        self._maybe_flush()
        self._maybe_ask(t)

    # ------------------------------------------------------------------------------- going offline
    async def going_offline(self, why: str = "") -> None:
        """Kurooto is stopping: say so (at most about BYE_S seconds), once. Never raises."""
        if self._said_bye:
            return
        self._said_bye = True
        try:
            await asyncio.wait_for(self._going(why), BYE_S + 0.5)
        except Exception as e:
            self.app.events.emit("presence_failed", error=f"goodbye: {type(e).__name__}: {e}"[:200])

    async def _going(self, why: str) -> None:
        t = self.clock()
        restart = bool(getattr(self.app, "restart_requested", False))
        reason = "restart" if restart else (why or getattr(self.app, "stop_reason", "") or "shutting down")
        stop = {"at": t, "reason": reason, "told": []}
        with self._lock:  # first, so the next start knows whatever happens next
            st = self._load()
            st["stop"], st["alive"] = stop, t
            self._save(st)
        calls = self._calls()
        if restart or not self.on():
            if calls is not None:
                await self._line_bye(calls, {"restart": True}, 1.0)
            return
        hush = self.hush_at(t)
        text = self.bye_text(reason)
        tg = "telegram" in self.channels() and not hush and not self.net_down() and self._telegram() is not None
        jobs = [self._telegram_now(text)] if tg else []
        if calls is not None and self.setting("line"):
            bye = {"why": reason, "text": text, "later": self.line_text(), "told": ["telegram"] if tg else []}
            jobs.append(self._line_bye(calls, {**bye, "hush": bool(hush)}, BYE_S))
        results = await asyncio.gather(*jobs, return_exceptions=True)
        told = ["telegram"] if tg and results and results[0] is True else []
        line = results[-1] if calls is not None and self.setting("line") and results else None
        if isinstance(line, dict):
            told += [c for c in line.get("sent") or [] if c not in told]
        stop["told"] = told
        with self._lock:
            st = self._load()
            st["stop"] = stop
            self._save(st)
        self.app.events.emit("presence_offline", by="computer", reason=reason, told=told, held=bool(hush))

    def _telegram_now(self, text: str) -> asyncio.Future:
        """Send on Telegram from a thread of its own (a hanging DNS lookup can't hold up the exit); True if it went."""
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        tg = self._telegram()

        def go():
            ok = False
            try:
                api, chat = tg.api(), tg.setting("chat_id")
                link = {"is_disabled": True}
                api.call("sendMessage", {"chat_id": chat, "text": text, "link_preview_options": link}, timeout=BYE_S)
                ok = True
            except Exception as e:
                self.app.events.emit("notify_failed", channel="telegram", error=f"goodbye: {e}"[:200])
            try:
                loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(ok))
            except RuntimeError:  # the loop is gone already: nobody is waiting
                pass

        threading.Thread(target=go, name="goodbye", daemon=True).start()
        return asyncio.ensure_future(asyncio.wait_for(fut, BYE_S))

    async def _line_bye(self, calls, payload: dict, timeout: float) -> dict | None:
        try:
            return await calls.connector.admin("bye", timeout=timeout, **payload)
        except Exception:
            return None

    def end_session(self, why: str) -> None:
        """Windows is ending the session (core/endsession.py): say goodbye now (Windows waits for this), then stop."""
        loop = getattr(self.app, "_loop", None)
        if loop is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self.going_offline(why), loop).result(BYE_S + 1)
            except Exception:
                pass
        self.app.stop_reason = why
        self.app.request_stop()

    def listen_for_end_session(self) -> None:
        from kurooto.core import endsession

        try:
            endsession.watch(self.end_session)
        except Exception as e:
            self.app.events.emit("presence_failed", error=f"end of session: {e}"[:200])

    # ----------------------------------------------------------------------------------- the texts
    def _line_places_calls(self) -> bool:
        c = self.app.modules.get("calls")
        return bool(c is not None and self.app.is_on("calls") and c.worker_url() and not getattr(c, "silenced", False))

    def bye_text(self, reason: str) -> str:
        tail = (
            "reminders will wait until it's back; your call line still places scheduled calls"
            if self._line_places_calls()
            else "calls and reminders will wait until it's back"
        )
        return f"{self.app.name} is going offline ({reason}): {tail}."

    def line_text(self) -> str:
        """What your call line says when this computer is gone (it fills in the time and why)."""
        tail = "your call line still places scheduled calls" if self._line_places_calls() else "calls wait too"
        return f"{self.app.name} has been offline since %%SINCE%% (%%WHY%%): reminders wait until it's back; {tail}."

    def back_text(self, p: dict, t: float) -> str:
        since, back = float(p["since"]), float(p["back"])
        if set(p.get("kinds") or []) == {"net"}:
            head = f"Back online: the network was down from {when(since, t)} to {when(back, t)} ({span(back - since)})."
        else:
            head = f"{self.app.name} is back online (offline since {when(since, t)}, {span(back - since)})."
        late, rang = self._caught_up(p.get("mark"))
        more = []
        if late:
            more.append(f"{late} reminder{'s' if late > 1 else ''} went out late")
        if rang:
            more.append(f"your call line placed {rang} call{'s' if rang > 1 else ''} meanwhile")
        n = self._outbox_len()
        if n:
            more.append(
                f"{n} message{'s' if n > 1 else ''} that couldn't go out meanwhile follow{'' if n > 1 else 's'}"
            )
        return head + (f" {'; '.join(more)}." if more else "")

    def _caught_up(self, mark) -> tuple[int, int]:
        """Reminders that fired late and calls your call line placed, since it came back (from the event log)."""
        try:
            with open(self.app.events.file, "rb") as f:
                end = f.seek(0, 2)
                f.seek(int(mark or 0) if int(mark or 0) <= end else 0)  # smaller: the log was trimmed since (events.py)
                lines = f.read(4_000_000).decode("utf-8", "replace").splitlines()
        except (OSError, ValueError):
            return 0, 0
        late = rang = 0
        for ln in lines:
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            late += e.get("kind") == "reminder_fired" and bool(e.get("late"))
            rang += e.get("kind") == "call_rang_offline"
        return late, rang

    # ---------------------------------------------------------------------------------- coming back
    def went_away(self, since: float, back: float, kind: str, told: bool = False, why: str = "") -> bool:
        """An offline period ended (kind: stop, off, restart, sleep, net, line). Long enough (or you were told it
        went): a "back" message waits until the computer has been up SETTLE_S; periods close together merge."""
        self.note_gap(since, back, kind)
        if not self.on() or back - since < 0:
            return False
        short = back - since < self.after_s() and not told
        with self._lock:
            st = self._load()
            p = st.get("pending")
            if short and isinstance(p, dict):  # a short one while a message waits: it waits a little longer
                p["due"] = max(float(p.get("due") or 0), back + SETTLE_S)
                self._save(st)
                return False
            if short:
                return False
            if isinstance(p, dict):
                p["since"], p["back"] = min(float(p["since"]), since), max(float(p["back"]), back)
                p["told"] = bool(p.get("told")) or told
                p["kinds"] = sorted(set(p.get("kinds") or []) | {kind})
                p["why"] = p.get("why") or why
                p["due"] = max(float(p.get("due") or 0), back + SETTLE_S)
            else:
                try:
                    mark = self.app.events.file.stat().st_size
                except OSError:
                    mark = 0
                p = {"since": since, "back": back, "told": told, "kinds": [kind], "why": why}
                p.update(due=back + SETTLE_S, mark=mark)
            st["pending"] = p
            self._save(st)
        return True

    def note_gap(self, since: float, back: float, kind: str) -> None:
        """Keep an offline period (for core/health.py): those of the last 15 days, at most GAPS_MAX."""
        if back - since < 1:
            return
        with self._lock:
            st = self._load()
            gaps = [
                g for g in st.get("gaps") or [] if isinstance(g, list) and len(g) == 3 and g[1] > back - GAPS_KEEP_S
            ]
            gaps.append([round(since, 1), round(back, 1), kind])
            st["gaps"] = sorted(gaps)[-GAPS_MAX:]
            self._save(st)

    def offline(self, start: float, end: float) -> list[tuple[float, float]]:
        """The offline periods between start and end (clipped to them), the network outage going on now included."""
        out = []
        for g in self._load().get("gaps") or []:
            try:
                a, b = max(float(g[0]), start), min(float(g[1]), end)
            except (TypeError, ValueError, IndexError):
                continue
            if b > a:
                out.append((a, b))
        if self.net_down() and self.net_fail_since is not None and self.net_fail_since < end:
            out.append((max(self.net_fail_since, start), end))
        return out

    def line_report(self, away: dict | None) -> None:
        """The call line's welcome: it told you this computer was offline (since when, on which channels)."""
        if not isinstance(away, dict) or not away.get("told") or not away.get("channels"):
            return
        since = float(away.get("since") or 0) / 1000
        if not since or since <= float(self._load().get("back_at") or 0):
            return  # already said it's back since then
        if self.went_away(since, self.clock(), "line", told=True):
            self.app.events.emit("presence_offline", by="line", since=when(since), told=away.get("channels"))

    def _maybe_send(self, t: float) -> None:
        with self._lock:
            st = self._load()
            p = st.get("pending")
            if not isinstance(p, dict) or t < float(p.get("due") or 0) or self.net_down():
                return
            hush = self.hush_at(t)
            if hush:  # night or focus: it waits (and at night, it's dropped if nobody said Kurooto had gone)
                p["due"] = hush[0]
                p["night"] = bool(p.get("night")) or hush[1] == "night"
                self._save(st)
                return
        drop = bool(p.get("night")) and not p.get("told")
        done = list(p.get("sent") or [])  # reached already, the last time Telegram couldn't be
        sent, retry = ([], False) if drop else self._deliver(self.back_text(p, t), skip=done)
        sent = done + sent
        if retry:
            with self._lock:
                st = self._load()
                if isinstance(st.get("pending"), dict):
                    st["pending"]["sent"] = sent
                    self._save(st)
            return
        with self._lock:
            st = self._load()
            st.pop("pending", None)
            st["back_at"] = t
            self._save(st)
        self.app.events.emit(
            "presence_online",
            since=when(float(p["since"]), t),
            minutes=round((float(p["back"]) - float(p["since"])) / 60),
            kinds=p.get("kinds"),
            told=bool(p.get("told")),
            message="dropped (back before morning)" if drop else ("sent" if sent else "no channel"),
            sent=sent,
        )
        self._poke_line()  # the call line hears it's back (it clears what it told you)
        self.flush_outbox()

    def _deliver(self, text: str, skip: list[str] | None = None) -> tuple[list[str], bool]:
        """To your presence channels, directly (not through focus or the outbox). (sent, retry): retry when Telegram
        couldn't be reached."""
        sent, retry = [], False
        for name in self.channels():
            fn = self.app.notifier.channels.get(name)
            if fn is None or name in (skip or []):
                continue
            try:
                ref = fn(Message(text, kind="info"))
                if name == "telegram" and ref is not None:
                    self.net_ok("telegram")
                sent.append(name)
            except Exception as e:
                self.app.events.emit("notify_failed", channel=name, error=str(e)[:200])
                if name == "telegram" and self.net_failed("telegram", e):
                    retry = True
        return sent, retry and "telegram" not in sent

    def hush_at(self, t: float) -> tuple[float, str] | None:
        """Night (your night hours, or bedtime to the alarm) or focus time at t: (when it ends, "night"|"focus")."""
        av = self.app.availability
        local = dt.datetime.fromtimestamp(t)
        try:
            n = av.night(local)
            if n:
                return n[1].timestamp(), "night"
            f = av.focus_until(local)
            if f:
                return f.timestamp(), "focus"
        except Exception:
            return None
        return None

    def hush_windows(self, start: float, hours: float = 30) -> list[list[int]]:
        """When messages wait over the next `hours`, as [from ms, to ms] (for the call line)."""
        out: list[list[int]] = []
        t, end, step = start, start + hours * 3600, 900
        while t < end:
            h = self.hush_at(t)
            if not h or h[0] <= t:
                t += step
                continue
            a = t
            if t > start:  # where it starts, to the minute
                lo, hi = t - step, t
                while hi - lo > 60:
                    mid = (lo + hi) / 2
                    lo, hi = (lo, mid) if self.hush_at(mid) else (mid, hi)
                a = hi
            if out and a - out[-1][1] / 1000 <= 61:
                out[-1][1] = int(h[0] * 1000)
            else:
                out.append([int(a * 1000), int(h[0] * 1000)])
            t = h[0] + 1
        return out

    # ------------------------------------------------------------------------------------ the network
    def net_ok(self, source: str = "") -> None:
        """Telegram or the call line answered: if the network was down long enough, that's a "back" message."""
        t = self.clock()
        with self._lock:
            since, self.net_fail_since, self.net_fails, self._net_try = self.net_fail_since, None, 0, t
        if since is not None:
            self.went_away(since, t, "net")

    def net_failed(self, source: str, err: BaseException) -> bool:
        """A request failed. True if it was the network (Telegram saying no doesn't count)."""
        if not _network(err):
            return False
        t = self.clock()
        with self._lock:
            if self.net_fail_since is None:
                self.net_fail_since = t
            self.net_fails += 1
            self._net_try = t
        return True

    def net_down(self) -> bool:
        """Repeated failures to reach Telegram or the call line, and no answer since."""
        s = self.net_fail_since
        return s is not None and (self.net_fails >= 2 or self.clock() - s > PROBE_S)

    def _probe(self) -> None:
        from kurooto.modules.telegram.api import TelegramError

        tg = self._telegram()
        if tg is None:
            return
        try:
            tg.api().call("getMe", timeout=5)
            self.net_ok("probe")
        except TelegramError:
            self.net_ok("probe")
        except Exception as e:
            self.net_failed("probe", e)

    # ------------------------------------------------------------------------- the outbox (Telegram)
    def hold(self, msg: Message) -> bool:
        """The notifier asks before sending to Telegram: while the network is down, it's kept for later."""
        if not self.net_down():
            return False
        self._queue(msg)
        return True

    def failed(self, msg: Message, err: BaseException) -> None:
        """Sending to Telegram failed: if it was the network, keep it for later."""
        if self.net_failed("telegram", err):
            self._queue(msg)

    def _queue(self, msg: Message) -> None:
        rec = json.dumps({**msg.__dict__, "at": self.clock()}, ensure_ascii=False, default=str)
        with self._out_lock:
            try:
                lines = self.outbox.read_text(encoding="utf-8").splitlines()
            except OSError:
                lines = []
            lines = [*lines, rec][-OUTBOX_MAX:]
            self.outbox.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.app.events.emit("notify_queued", kind=msg.kind, why="network")

    def _outbox_len(self) -> int:
        try:
            return len([ln for ln in self.outbox.read_text(encoding="utf-8").splitlines() if ln.strip()])
        except OSError:
            return 0

    def _maybe_flush(self) -> None:
        if self.net_down() or not self._outbox_len():
            return
        p = self._load().get("pending")
        if isinstance(p, dict) and not p.get("night") and self.on():
            return  # the "back" message goes first; the delayed ones follow it
        self.flush_outbox()

    def flush_outbox(self) -> int:
        """Send what waited for the network, in order, each marked as delayed. Stops at the first network failure."""
        tg = self.app.notifier.channels.get("telegram")
        if tg is None:
            return 0
        with self._out_lock:
            try:
                lines = [ln for ln in self.outbox.read_text(encoding="utf-8").splitlines() if ln.strip()]
            except OSError:
                return 0
            self.outbox.unlink(missing_ok=True)
        n, rest = 0, []
        for i, ln in enumerate(lines):
            try:
                d = json.loads(ln)
                at = float(d.pop("at", 0) or 0)
                msg = Message(**d)
            except (ValueError, TypeError):
                continue
            mark = f"Delayed, from {when(at, self.clock())}"
            msg.title = f"{mark}: {msg.title}" if msg.title else mark
            try:
                tg(msg)
                n += 1
            except Exception as e:
                self.app.events.emit("notify_failed", channel="telegram", error=f"delayed: {e}"[:200])
                if self.net_failed("telegram", e):
                    rest = lines[i:]
                    break
        if rest:
            with self._out_lock:
                try:
                    newer = [ln for ln in self.outbox.read_text(encoding="utf-8").splitlines() if ln.strip()]
                except OSError:
                    newer = []
                self.outbox.write_text("\n".join([*rest, *newer][-OUTBOX_MAX:]) + "\n", encoding="utf-8")
        if n:
            self.app.events.emit("notify_delayed", n=n)
        return n

    # ---------------------------------------------------------------------------------- the call line
    def _telegram(self):
        tg = self.app.modules.get("telegram")
        if tg is None or not self.app.is_on("telegram") or tg.api() is None or not tg.setting("chat_id"):
            return None
        return tg

    def _calls(self):
        c = self.app.modules.get("calls")
        if c is None or not self.app.is_on("calls") or getattr(c.connector, "ws", None) is None:
            return None
        return c

    def _poke_line(self) -> None:
        c = self.app.modules.get("calls")
        if c is not None and self.app.is_on("calls"):
            c.connector.poke()

    def line_config(self) -> dict:
        """What the call line needs to speak for this computer (pushed with the rest of its state)."""
        on = bool(self.on() and self.setting("line"))
        chans = self.channels()
        tg = self._telegram()
        token = None
        if on and "telegram" in chans and self.setting("line_telegram") is True and tg is not None:
            token = {"token": self.app.secrets.get("telegram.token"), "chat": str(tg.setting("chat_id"))}
        return {
            "on": on,
            "after_min": self.after_s() / 60,
            "channels": [c for c in chans if c != "telegram" or token],
            "hush": self.hush_windows(self.clock()) if on else [],
            "text": self.line_text(),
            "why": WHY_UNKNOWN,
            "back_at": int(float(self._load().get("back_at") or 0) * 1000),
            "tg": token,
        }

    def _maybe_ask(self, t: float) -> None:
        """Once: may the call line keep your bot's token, to tell you on Telegram when this computer is gone?"""
        if t - self._asked < 6 * 3600:
            return
        self._asked = t
        calls = self.app.modules.get("calls")
        if not (self.on() and self.setting("line") and "telegram" in self.channels()):
            return
        if self.setting("line_telegram") is not None or self._telegram() is None:
            return
        if calls is None or not self.app.is_on("calls") or not calls.worker_url():
            return
        from kurooto.core.ask import OPEN

        st = self._load()
        q = self.app.ask.get(st["line_q"]) if st.get("line_q") else None
        if (q and q.get("status") in OPEN) or t - float(st.get("line_asked") or 0) < ASK_AGAIN_S:
            return
        qid = self.app.ask.ask(
            LINE_ASK, kind="approval", hook="presence.line", source="presence", title="Offline", why="presence.line"
        )
        with self._lock:
            st = self._load()
            st["line_q"], st["line_asked"] = qid, t
            self._save(st)

    def _line_answer(self, q: dict, answer: str) -> str:
        from kurooto.core.ask import APPROVE

        yes = str(answer).strip().lower() == APPROVE.lower()
        self.app.settings.set("notify.presence.line_telegram", yes)
        self._poke_line()
        if yes:
            return "Your call line will tell you here when this computer goes offline without warning."
        return (
            "OK: your call line won't keep your bot's token (Settings → notify.presence → line_telegram changes "
            'that). It can still tell the phone app: add "app" to notify.presence → channels.'
        )
