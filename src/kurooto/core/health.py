"""Kurooto keeps itself working: one health check per feature, a daily pass that stays quiet unless something matters,
and a few safe fixes.

The checks (core/health_checks.py for the built-in features; an add-on's Module.health_check() for its own) are
read-only. Each feature that's on has one, made of either or both of:
    how often it should work ("Classroom sync at least once in 26 h"), counted only in hours this computer was up and
        Kurooto wasn't paused: sleep, shutdowns and network outages (core/presence.py keeps them) and pauses don't
        count, nor does battery saver for features that wait for the charger. A shut lid is never a failed sync.
    a probe: a sign-in that has ended or ends soon (Google, the notes token on GitHub, the Cloudflare login, the
        Telegram bot), this computer's link to the call line, tonight's alarm, messages stuck in a queue.

At most one fix each, and only of Kurooto's own state, never your notes or other data:
    sync       runs the feature's own sync once now (what its timer does anyway)
    rearm      puts back its timers when they're missing, and runs work held for a pause that's over
    reconnect  restarts the link to your call line, or Telegram's reading of your messages
    alarm      plans your daily alarm again (if it isn't planned yet) and sends it to your call line
    deliver    sends what waited in Kurooto's own queues (focus time that's over, a network that's back)
Locks are the operating system's and go away with their program, so there's no stuck lock to clear.

Who reads the checks: `kurooto doctor` (and `kurooto doctor --fix ID`), the dashboard (a "needs a look" badge; the
Features tab lists them with Fix buttons), /health on Telegram, the weekly summary, and the daily pass (health.when,
21:00). The daily pass says nothing unless something is wrong, and even then:
    tonight's alarm might not ring: a message now, "set your phone's own alarm too";
    the Telegram bot stopped answering: a message now (on the desktop and the phone app, since Telegram can't);
    a problem that could make you miss a deadline or exam in the next 48 h: one message now, with a Fix button;
    anything else waits for the weekly summary (with that off, one message on Sundays).
Before it tells you, it tries a fix that's safe to run unasked (rearm, reconnect, alarm, deliver) and looks again ten
minutes later. Each problem is told once, until it's fixed and comes back.

Settings: health {on, when, auto_fix}. State: state/health.json (pauses and battery saver, what was told, the probes'
last answers). Events: health_checked, health_fixed, health_told.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "health",
    {
        "on": True,  # the daily pass (doctor, the dashboard and /health always check)
        "when": "daily 21:00",  # before bedtime: tonight's alarm is checked then
        "auto_fix": True,  # try a safe fix before telling you (never sync: that one waits for your tap)
    },
)

FIXES = {
    "sync": "Sync now",
    "rearm": "Put its timers back",
    "reconnect": "Reconnect",
    "alarm": "Set the alarm again",
    "deliver": "Send them now",
}
AUTO = ("rearm", "reconnect", "alarm", "deliver")  # safe to try before telling you
SOON_H = 48  # a deadline or exam this close makes a problem worth a message now
RECHECK_S = 600  # after a fix, look again this much later
KEEP_S = 15 * 86400  # how far back the event log and the pauses are read
PROBE_KEEP_S = 26 * 3600  # a probe's answer from the internet stands in this long when the internet isn't asked
DIGEST_S = 6.5 * 86400  # with the weekly summary off: at most one list of problems this often


@dataclass
class Check:
    """One feature's health check. Evaluating it never changes anything."""

    id: str  # the feature's id ("google"), or "kurooto" for Kurooto's own
    title: str  # what messages call it ("Classroom sync")
    module: str = ""  # checked only while this feature is on ("": always)
    every_h: float = 0  # should work at least once in this many awake hours (0: no such rule)
    events: tuple[str, ...] = ()  # the events that mean it worked
    ok_if: Callable[[dict], bool] | None = None  # ...when the event says so (e.g. ok=True)
    heavy: bool = False  # its work waits for the charger: battery saver doesn't count either
    probe: Callable[[bool], tuple | None] | None = None  # probe(net) -> (ok, detail[, fix]); None: ask the internet
    kind: str = "quiet"  # what a failed probe is: credential, link, alarm, queue
    fix: str = ""  # the fix when it's gone quiet (FIXES)
    sync: Callable[[], Any] | None = None  # what the "sync" fix runs
    deadlines: bool = False  # trouble here can make you miss a deadline or exam (it brings or delivers them)
    urgent: bool = False  # always worth a message at once
    help: str = ""  # what you can do yourself


@dataclass
class Result:
    id: str
    title: str
    ok: bool | None  # None: can't tell yet
    detail: str
    kind: str = ""  # quiet, credential, link, alarm, queue (what's wrong)
    fix: str = ""  # FIXES key, optionally ":<feature>" (reconnect:calls)
    deadlines: bool = False
    urgent: bool = False
    help: str = ""

    @property
    def fix_label(self) -> str:
        return FIXES.get(self.fix.partition(":")[0], "")

    def line(self) -> str:
        return f"{self.title}: {self.detail}" + ("" if self.fix or not self.help else f". {self.help.rstrip('.')}")


# ------------------------------------------------------------------------------------- the event log, read cheaply
def _lines_back(file: Path, end: int) -> Iterator[str]:
    """The event log's lines from byte `end` backwards (newest first)."""
    try:
        f = open(file, "rb")  # noqa: SIM115 (a generator keeps it open while it's read)
    except OSError:
        return
    with f:
        pos, rest = end, b""
        while pos > 0:
            n = min(1 << 20, pos)
            pos -= n
            f.seek(pos)
            parts = (f.read(n) + rest).split(b"\n")
            rest = parts[0]
            for ln in reversed(parts[1:]):
                if ln:
                    yield ln.decode("utf-8", "replace")
        if rest:
            yield rest.decode("utf-8", "replace")


def _ts(line: str) -> float | None:
    try:
        return dt.datetime.fromisoformat(line[8:27]).timestamp()  # {"ts": "2026-10-20T21:00:00", ...
    except ValueError:
        return None


class Latest:
    """The newest event of a kind (that passes a test), found from the end of the event log, remembered, and topped
    up from what was added since: asking again costs only the new lines."""

    def __init__(self, file: Path):
        self.file = file
        self.memo: dict[str, tuple[int, tuple[float, dict] | None]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, kind: str, test: Callable[[dict], bool] | None, horizon: float):
        needle = f'"kind": "{kind}"'

        def hit(line: str):
            if needle not in line:
                return None
            try:
                rec = json.loads(line)
            except ValueError:
                return None
            if rec.get("kind") != kind or (test is not None and not test(rec)):
                return None
            ts = _ts(line)
            return (ts, rec) if ts is not None else None

        with self._lock:
            try:
                size = self.file.stat().st_size
            except OSError:
                return None
            old = self.memo.get(key)
            if old is not None and old[0] <= size:
                found, upto = old[1], old[0]
                if size > upto:
                    with open(self.file, "rb") as f:
                        f.seek(upto)
                        chunk = f.read(size - upto)
                    cut = chunk.rfind(b"\n") + 1  # a line still being written waits for next time
                    for ln in chunk[:cut].decode("utf-8", "replace").splitlines():
                        h = hit(ln)
                        if h is not None:
                            found = h
                    upto += cut
                self.memo[key] = (upto, found)
                return found
            stop = dt.datetime.fromtimestamp(horizon).isoformat()[:19]
            found = None
            for ln in _lines_back(self.file, size):
                if ln[8:27] < stop and ln.startswith('{"ts": "'):
                    break
                found = hit(ln)
                if found is not None:
                    break
            self.memo[key] = (size, found)
            return found


def _merge(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted(s for s in spans if s[1] > s[0]):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


class Health:
    def __init__(self, app: App, clock: Callable[[], float] = time.time):
        self.app = app
        self.clock = clock
        self.file = app.paths.state / "health.json"
        self.latest = Latest(app.events.file)
        self._lock = threading.RLock()
        self._unsub = None

    # ------------------------------------------------------------------------------------------ basics
    def on(self) -> bool:
        return bool(self.app.settings.get("health.on"))

    def _load(self) -> dict:
        return jload(self.file, {}) or {}

    def _save(self, st: dict) -> None:
        jsave(self.file, st)

    def running(self) -> bool:
        """Is Kurooto running (this is it, or another process is)?"""
        if getattr(self.app, "_loop", None) is not None:
            return True
        from kurooto.core.proc import pid_alive

        d = jload(self.app.paths.state / "daemon.json", {}) or {}
        return bool(d.get("pid")) and pid_alive(d["pid"])

    def last_event(self, kind: str, test: Callable[[dict], bool] | None = None, key: str = "") -> tuple | None:
        """(when, the event) of the newest `kind` event in the last 15 days that passes `test`, or None."""
        return self.latest.get(key or kind, kind, test, self.clock() - KEEP_S)

    # -------------------------------------------------------------------------- awake time (no false alarms)
    def power_changed(self, mode: str, t: float | None = None) -> None:
        """Kurooto's power mode now (core/power.py): paused and battery-saver time is kept, for the quiet checks."""
        t = self.clock() if t is None else t
        with self._lock:
            st = self._load()
            cur = st.get("power") or {}
            if cur.get("mode") == mode:
                return
            spans = [s for s in st.get("power_spans") or [] if isinstance(s, list) and s[1] > t - KEEP_S]
            if cur.get("mode") not in (None, "normal") and cur.get("since"):
                spans.append([cur["since"], t, cur["mode"]])
            st["power"] = {"mode": mode, "since": t}
            st["power_spans"] = spans[-400:]
            self._save(st)

    def _on_event(self, rec: dict) -> None:
        if rec.get("kind") == "power_mode" and rec.get("mode"):
            self.power_changed(str(rec["mode"]))

    def away(self, start: float, end: float, heavy: bool = False) -> list[tuple[float, float]]:
        """When Kurooto couldn't have worked between start and end: offline (asleep, off, no network), paused, or
        (heavy work) in battery saver. Merged and clipped."""
        spans = [(max(a, start), min(b, end)) for a, b in self.app.presence.offline(start, end)]
        st = self._load()
        power = [tuple(s) for s in st.get("power_spans") or [] if isinstance(s, list) and len(s) == 3]
        cur = st.get("power") or {}
        if cur.get("mode") not in (None, "normal") and cur.get("since"):
            power.append((cur["since"], end, cur["mode"]))
        for a, b, mode in power:
            if mode == "paused" or (heavy and mode == "saver"):
                spans.append((max(float(a), start), min(float(b), end)))
        if not self.running():  # stopped: from its last heartbeat on, it was away too
            alive = (jload(self.app.paths.state / "presence.json", {}) or {}).get("alive")
            if alive and float(alive) < end:
                spans.append((max(float(alive), start), end))
        return _merge(spans)

    def awake_s(self, start: float, end: float, heavy: bool = False) -> float:
        if end <= start:
            return 0.0
        return max(0.0, (end - start) - sum(b - a for a, b in self.away(start, end, heavy)))

    # --------------------------------------------------------------------------------------- the registry
    def checks(self) -> list[Check]:
        """Kurooto's own check, then one per feature that's on and has one."""
        from kurooto.core.health_checks import kurooto

        out = [kurooto(self.app)]
        for m in self.app.enabled():
            try:
                c = m.health_check()
            except Exception as e:
                self.app.events.emit("health_failed", module=m.id, error=f"{type(e).__name__}: {e}"[:200])
                continue
            if isinstance(c, Check):
                c.module = c.module or m.id
                out.append(c)
        return out

    def evaluate(self, net: bool = False, only: str | None = None, save: bool = True) -> list[Result]:
        """Every check (or one). net: probes may use the internet (the daily pass, doctor); otherwise their last
        answer from it stands in. save: the daily pass and the fixes keep what they found; doctor, the dashboard and
        /health only look."""
        now = self.clock()
        checks = [c for c in self.checks() if only is None or c.id == only]
        st = self._load()
        probes = dict(st.get("probes") or {})
        first = dict(st.get("first") or {})
        out = []
        for c in checks:
            if c.every_h and c.id not in first:
                first[c.id] = now
            try:
                out.append(self._one(c, now, net, probes, first))
            except Exception as e:
                out.append(Result(c.id, c.title, None, f"its check failed: {type(e).__name__}: {e}"[:200]))
        if save:
            with self._lock:
                st = self._load()
                st["probes"] = {k: v for k, v in probes.items() if now - float(v[3]) < KEEP_S}
                st["first"] = first
                st["at"] = now
                self._save(st)
        return out

    def _one(self, c: Check, now: float, net: bool, probes: dict, first: dict) -> Result:
        said, oks = [], []
        res = Result(c.id, c.title, None, "", deadlines=c.deadlines, urgent=c.urgent, help=c.help)
        if c.probe is not None:
            try:
                p = c.probe(net)
            except Exception as e:
                p = (None, f"its check failed: {type(e).__name__}: {e}"[:200])
            if p is None:  # it needs the internet: its last answer from there, if recent
                old = probes.get(c.id)
                p = tuple(old[:3]) if old and now - float(old[3]) < PROBE_KEEP_S else (None, "not checked yet")
            elif net:
                probes[c.id] = [p[0], p[1], p[2] if len(p) > 2 else "", now]
            ok, detail, fix = p[0], str(p[1] or ""), str(p[2] if len(p) > 2 else "")
            if ok is False:
                res.ok, res.detail, res.kind, res.fix = False, detail, c.kind, fix
                return res
            oks.append(ok)
            if detail:
                said.append(detail)
        if c.every_h and c.events:
            ok, detail, fix = self._quiet(c, now, first)
            if ok is False:
                res.ok, res.detail, res.kind, res.fix = False, detail, "quiet", fix
                return res
            oks.append(ok)
            said.append(detail)
        res.ok = True if True in oks else None
        res.detail = "; ".join(s for s in said if s) or ("ok" if res.ok else "")
        return res

    def _quiet(self, c: Check, now: float, first: dict) -> tuple[bool | None, str, str]:
        """Has it worked within its window of awake hours?"""
        from kurooto.core.presence import span, when

        last = None
        for kind in c.events:
            hit = self.last_event(kind, c.ok_if, key=f"ok:{c.id}:{kind}")
            if hit and (last is None or hit[0] > last):
                last = hit[0]
        mod = c.module
        on = self.last_event("module_enabled", lambda e: e.get("module") == mod, key=f"on:{mod}") if mod else None
        base = max([x for x in (last, on[0] if on else None, first.get(c.id)) if x] or [now])
        awake = self.awake_s(base, now, c.heavy)
        if awake <= c.every_h * 3600:
            if last is None:
                return None, "hasn't run yet", ""
            return True, f"worked {span(now - last)} ago", ""
        ref = last or base
        detail = (
            f"hasn't worked since {when(ref, now)} ({span(awake)} of that with this computer on)"
            if last
            else f"hasn't worked yet ({span(awake)} with this computer on)"
        )
        fix = c.fix
        if mod and not self.app.scheduler.jobs(f"{mod}:"):
            detail += "; its timers are missing"
            fix = "rearm"
        m = self.app.modules.get(mod) if mod else None
        if m is not None:
            try:
                ok, why = m.health()
            except Exception:
                ok, why = True, ""
            if ok is False and why:
                detail += f" (it says: {why})"
        return False, detail, fix

    # ------------------------------------------------------------------------------------------ the fixes
    def _check(self, cid: str) -> Check | None:
        return next((c for c in self.checks() if c.id == cid), None)

    def fix(self, cid: str, auto: bool = False, result: Result | None = None) -> tuple[bool, str]:
        """Run the fix a problem offers. (did something, what was done or why not)."""
        c = self._check(cid)
        if c is None:
            return False, "There's no such check (or its feature is off)."
        r = result or next(iter(self.evaluate(only=cid, save=False)), None)
        if r is None or r.ok is not False:
            return False, f"{c.title} looks fine now."
        name, _, target = r.fix.partition(":")
        if name not in FIXES:
            return False, f"Nothing I can fix there myself: {r.help or r.detail}"
        try:
            said = getattr(self, f"_fix_{name}")(c, target or c.module)
        except Exception as e:
            self.app.events.emit("health_failed", check=cid, fix=name, error=f"{type(e).__name__}: {e}"[:200])
            return False, f"The fix didn't work: {type(e).__name__}: {e}"[:300]
        with self._lock:
            st = self._load()
            st.setdefault("tried", {})[cid] = {"at": self.clock(), "fix": name}
            self._save(st)
        self.app.events.emit("health_fixed", check=cid, fix=name, auto=auto)
        if not auto:  # you'll hear whether it worked
            self.app.scheduler.at(
                self.clock() + RECHECK_S, "health.after_fix", {"id": cid}, key=f"health:after:{cid}", grace_s=3600
            )
        return True, said

    def _module(self, mid: str):
        m = self.app.modules.get(mid)
        if m is None or not self.app.is_on(mid):
            raise RuntimeError(f"{mid} is off")
        return m

    def _fix_sync(self, c: Check, mid: str) -> str:
        if c.sync is None:
            raise RuntimeError("it has nothing to sync")
        self._fix_rearm(c, mid)

        def go():
            try:
                c.sync()
            except Exception as e:
                self.app.events.emit("health_failed", check=c.id, fix="sync", error=f"{type(e).__name__}: {e}"[:200])

        threading.Thread(target=go, name=f"health-{c.id}", daemon=True).start()
        return f"{c.title}: running it now. I'll look again in {RECHECK_S // 60} minutes."

    def _fix_rearm(self, c: Check, mid: str) -> str:
        m = self._module(mid)
        m.start()  # registering its timers again keeps their times (scheduler.every)
        self.app.start_background(m)
        self.app.power.release()
        return f"{c.title}: its timers are back."

    def _fix_reconnect(self, c: Check, mid: str) -> str:
        m = self._module(mid)
        self.app.stop_background(m)
        self.app.start_background(m)
        return f"{m.title}: reconnecting."

    def _fix_alarm(self, c: Check, mid: str) -> str:
        alarm = self._module("alarm")
        alarm._plan()  # the daily alarm, if it isn't planned yet (what midnight would do)
        alarm.keep_awake()
        calls = self.app.modules.get("calls")
        if calls is not None and self.app.is_on("calls"):
            if calls.connector.connected:
                calls.connector.poke()  # the call line hears it now
            else:
                self._fix_reconnect(c, "calls")
        at = alarm.next()
        return f"Alarm set for {at:%a %H:%M} and sent to your call line." if at else "No alarm to set."

    def _fix_deliver(self, c: Check, mid: str) -> str:
        n = 0
        if not self.app.availability.focus_until():
            n += self.app.notifier.flush_queue()
        if not self.app.presence.net_down():
            n += self.app.presence.flush_outbox()
        return f"Sent {n} waiting message{'s' if n != 1 else ''}."

    # ---------------------------------------------------------------------------------------- the daily pass
    def start(self) -> None:
        """At the daemon's start: the daily pass, the power ledger, and when each check was first seen."""
        from kurooto.core.events import subscribe

        sch = self.app.scheduler
        sch.action("health.daily", self._daily_job)
        sch.action("health.recheck", lambda p: asyncio.to_thread(self.recheck))
        sch.action("health.after_fix", lambda p: asyncio.to_thread(self.after_fix, p.get("id", "")))
        sch.every("health:daily", self.app.settings.get("health.when") or "daily 21:00", "health.daily")
        if self._unsub is None:
            self._unsub = subscribe(self._on_event)
        self.power_changed(self.app.power.current)
        self.evaluate(net=False)  # starts each window from now (nothing before 0.5.0 knew about sleep)

    async def _daily_job(self, payload: dict | None = None):
        return await asyncio.to_thread(self.daily)

    def daily(self) -> dict:
        """Check everything; try the safe fixes first (and look again in ten minutes), else decide what to say."""
        if not self.on():
            return {"skipped": True}
        results = self.evaluate(net=True)
        bad = [r for r in results if r.ok is False]
        self.app.events.emit("health_checked", checks=len(results), problems=len(bad))
        if self.app.settings.get("health.auto_fix"):
            tried = self._load().get("tried") or {}
            go = [r for r in bad if r.fix.partition(":")[0] in AUTO and r.id not in tried]
            for r in go:
                self.fix(r.id, auto=True, result=r)
            if go:
                self.app.scheduler.at(self.clock() + RECHECK_S, "health.recheck", key="health:recheck", grace_s=3600)
                return {"fixing": [r.id for r in go]}
        return self.decide(results)

    def recheck(self) -> dict:
        return self.decide(self.evaluate(net=True))

    def after_fix(self, cid: str) -> str:
        """Ten minutes after you tapped Fix: whether it worked."""
        r = next(iter(self.evaluate(net=True, only=cid)), None)
        if r is None:
            return ""
        if r.ok is False:
            text = f"{r.title} still isn't working: {r.detail}." + (f" {r.help}" if r.help else "")
        else:
            text = f"{r.title} works again."
        self.app.notify(text, kind="info")
        return text

    def threats(self) -> list[str]:
        """Deadlines and exams in the next 48 h ("Report (Thu 09:00)")."""
        dl = self.app.modules.get("deadlines")
        if dl is None or not self.app.is_on("deadlines"):
            return []
        try:
            soon = dl.upcoming(SOON_H)
        except Exception:
            return []
        return [f"{it['title']} ({it['due'][:16].replace('T', ' ')})" for _, it, h in soon if 0 < h <= SOON_H]

    def decide(self, results: list[Result]) -> dict:
        """Say now what can't wait; leave the rest for the weekly summary. Each problem is told once."""
        now = self.clock()
        bad = [r for r in results if r.ok is False]
        with self._lock:
            st = self._load()
            told, tried = st.get("told") or {}, st.get("tried") or {}
            for r in results:  # working again: if it breaks later, that's news again
                if r.ok is not False:
                    told.pop(r.id, None)
                    tried.pop(r.id, None)
            st["told"], st["tried"] = told, tried
            self._save(st)
        threats = self.threats() if any(r.deadlines for r in bad) else []
        alarm = [r for r in bad if r.kind == "alarm" and (told.get(r.id) or {}).get("detail") != r.detail]
        now_ = [r for r in bad if r.kind != "alarm" and (r.urgent or (r.deadlines and threats)) and r.id not in told]
        sent = []
        for r in alarm:
            text = f"{r.detail}. Set your phone's own alarm too." + self._tried(r, tried)
            self.app.notify(text, kind="deadline", buttons=self._buttons([r]))
            sent.append(r)
        if now_:
            if threats:
                more = f" and {len(threats) - 1} more" if len(threats) > 1 else ""
                head = f"Before {threats[0]}{more}, this needs a look:"
            else:
                head = f"{self.app.name} needs a look:"
            lines = [f"- {r.line()}.{self._tried(r, tried)}" for r in now_]
            self.app.notify("\n".join([head, *lines]), kind="deadline", buttons=self._buttons(now_))
            sent += now_
        rest = [r for r in bad if r not in sent and r.id not in told]
        digest = False
        if (
            rest
            and not self.app.is_on("weekly")
            and self._digest_day()
            and now - float(st.get("digest_at") or 0) > DIGEST_S
        ):
            lines = [f"- {r.line()}" for r in bad if r.kind != "alarm"]
            self.app.notify("\n".join(["Needs a look (Kurooto keeps itself working):", *lines]), kind="info")
            digest = True
        with self._lock:
            st = self._load()
            told = st.get("told") or {}
            for r in sent:
                told[r.id] = {"at": now, "detail": r.detail}
            st["told"] = told
            if digest:
                st["digest_at"] = now
            self._save(st)
        if sent:
            self.app.events.emit("health_told", checks=[r.id for r in sent], deadlines=len(threats))
        return {"told": [r.id for r in sent], "waiting": [r.id for r in rest], "digest": digest}

    def _digest_day(self) -> bool:
        """The weekly summary's day (Sunday unless weekly.when says otherwise)."""
        spec = str(self.app.settings.get("weekly.when") or "weekly sun 19:00").split()
        day = spec[1] if len(spec) == 3 else "sun"
        return dt.datetime.fromtimestamp(self.clock()).strftime("%a").lower() == day

    @staticmethod
    def _tried(r: Result, tried: dict) -> str:
        t = tried.get(r.id)
        return f" (I tried: {FIXES.get(t['fix'], t['fix']).lower()}; it didn't help.)" if t else ""

    @staticmethod
    def _buttons(rs: list[Result]) -> list | None:
        rows = [[(f"{r.fix_label}: {r.title}"[:40], f"health:{r.id}:fix")] for r in rs if r.fix_label]
        return rows[:4] or None

    # ---------------------------------------------------------------------------------- what others read
    def problems(self) -> list[Result]:
        """What's wrong now, from what can be known without the internet (and the probes' last answers)."""
        return [r for r in self.evaluate(net=False, save=False) if r.ok is False]

    def board(self) -> list[dict]:
        """For the dashboard: each problem, with its fix."""
        if not self.on():
            return []
        return [{**asdict(r), "fix_label": r.fix_label} for r in self.problems()]

    def weekly_lines(self) -> list[str]:
        bad = self.problems() if self.on() else []
        if not bad:
            return []
        return ["Needs a look:", *[f"- {r.line()}" for r in bad], "/health lists them with Fix buttons."]

    def command(self, arg: str = "") -> tuple[str, list | None]:
        """/health: what's wrong, with Fix buttons (/health now asks the internet too)."""
        results = self.evaluate(net=arg.strip().lower() in ("now", "all"), save=False)
        bad = [r for r in results if r.ok is False]
        if not bad:
            n = len(results)
            return f"Everything {self.app.name} checks is working ({n} check{'s' if n != 1 else ''}).", None
        lines = [f"- {r.line()}" for r in bad]
        return "\n".join([f"{len(bad)} of {len(results)} checks need a look:", *lines]), self._buttons(bad)

    def button(self, ref: str, act: str) -> str:
        if act != "fix":
            return "unknown button"
        return self.fix(ref)[1][:190]
