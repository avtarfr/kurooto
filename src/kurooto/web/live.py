"""What the dashboard shows, kept fresh: the machine (core/vitals.py: processor, memory, graphics card, network,
disks, battery, processes, each with a short history), each feature's activity, the AI jobs, what's scheduled, the
notes graph (notes and their [[links]] in your notes folder), and Kurooto's side of the dense board (Vitals.board():
each feature's own programs, the call line, today, what's due, the AI's corner, study today, projects, today's events;
`kurooto top` reads it from GET /api/board). Pushed to open pages over a server-sent-events stream; nothing is
computed while no page is open."""

from __future__ import annotations

import datetime as dt
import json
import os
import queue
import re
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import psutil

from kurooto import __version__
from kurooto.core import events as events_mod
from kurooto.core import proc
from kurooto.core.clock import now
from kurooto.core.state import jload
from kurooto.core.vitals import Sampler, own_pids

if TYPE_CHECKING:
    from kurooto.app import App

SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", ".kurooto"}
LINK = re.compile(r"(?<!!)\[\[([^\]|#^]+)")
# which feature an event belongs to, for the pulses in SYSTEMS
EVENT_CELL = [
    ("message_in", "telegram"),
    ("telegram", "telegram"),
    ("notified", "telegram"),
    ("job", "chat"),
    ("intent", "telegram"),
    ("reminder", "reminders"),
    ("checkin", "checkins"),
    ("deadline", "deadlines"),
    ("gbrain", "gbrain"),
    ("quiz", "quiz"),
    ("files", "files"),
    ("class_", "subjects"),
    ("calls_held", "telegram"),
    ("call", "calls"),
    ("alarm", "alarm"),
    ("voice_note", "voice_notes"),
    ("awake", "awake"),
    ("calendar", "calendar"),
    ("notes_sync", "notes_sync"),
    ("google", "google"),
    ("classroom", "google"),
    ("gmail", "google"),
    ("handwritten", "handwritten"),
    ("study", "study"),
    ("research", "research"),
    ("capture", "capture"),
    ("retro", "retro"),
    ("update", "core"),
    ("module_", "core"),
    ("started", "core"),
]


def cell_of(kind: str) -> str:
    return next((c for prefix, c in EVENT_CELL if kind.startswith(prefix)), "core")


# ---------------------------------------------------------------------------------------- notes graph
def note_info(path: Path, root: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    rel = path.relative_to(root).with_suffix("").as_posix()
    fm = re.match(r"^---\n(.*?)\n---", text, re.S)
    title = None
    if fm:
        m = re.search(r"^title:\s*['\"]?(.+?)['\"]?\s*$", fm.group(1), re.M)
        title = m.group(1) if m else None
    if not title:
        m = re.search(r"^# (.+)$", text, re.M)
        title = m.group(1).strip() if m else path.stem
    return {
        "id": rel,
        "title": title[:80],
        "group": rel.split("/")[0] if "/" in rel else "root",
        "words": len(text.split()),
        "targets": sorted({t.strip().removesuffix(".md") for t in LINK.findall(text)}),
    }


class Graph:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.infos: dict[str, dict] = {}
        self.mtimes: dict[str, float] = {}
        self.payload = {"nodes": [], "links": [], "changed": [], "version": 0}

    def scan(self) -> bool:
        """Re-read changed notes. Returns True if the graph changed."""
        new, files = {}, {}
        for dirpath, dirs, names in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for n in names:
                if n.endswith(".md"):
                    p = Path(dirpath) / n
                    try:
                        new[p.relative_to(self.root).with_suffix("").as_posix()] = p.stat().st_mtime
                        files[p.relative_to(self.root).with_suffix("").as_posix()] = p
                    except OSError:
                        continue
            if len(new) > 5000:
                break
        changed = [k for k, m in new.items() if self.mtimes.get(k) != m]
        removed = [k for k in self.mtimes if k not in new]
        first = self.payload["version"] == 0
        if not (changed or removed or first):
            return False
        for k in changed:
            info = note_info(files[k], self.root)
            if info:
                self.infos[k] = info
        for k in removed:
            self.infos.pop(k, None)
        self.mtimes = new
        by_base, lower = {}, {k.lower(): k for k in self.infos}
        for k in self.infos:
            by_base.setdefault(k.split("/")[-1].lower(), k)
        links = set()
        for k, info in self.infos.items():
            for t in info["targets"]:
                dst = lower.get(t.lower()) or by_base.get(t.split("/")[-1].lower())
                if dst and dst != k:
                    links.add((k, dst))
        nodes = [
            {"id": k, "title": i["title"], "group": i["group"], "words": i["words"], "mtime": self.mtimes.get(k, 0)}
            for k, i in self.infos.items()
        ]
        self.payload = {
            "nodes": nodes,
            "links": sorted(links),
            "changed": [] if first else changed,
            "version": self.payload["version"] + 1,
        }
        return True


# --------------------------------------------------------------------------------------------- vitals
# feature -> the process names that are its own work (shown on its cell: cpu, memory, uptime, threads)
CELL_PROCS = {"local_models": ("ollama",)}
# scheduled plumbing that isn't something happening to you today (refreshes, sweeps, saves)
PLUMBING = re.compile(r"\.(tick|refresh|sweep|soon|check|probation|logs|idle|write|plan|unstick|missed|task_check)$")


class Vitals:
    def __init__(self, app: App):
        self.app = app
        self.sampler = Sampler(app.paths.state / "hardware.json")
        self.cache: dict[str, tuple[float, object]] = {}
        self._brain = ("", "")
        self._procs: dict[int, psutil.Process] = {}

    def _cached(self, key: str, ttl: float, fn, default=None):
        at, value = self.cache.get(key, (0.0, default))
        if not at or time.monotonic() - at >= ttl:
            try:
                value = fn()
            except Exception:  # one broken source mustn't stop the page
                pass
            self.cache[key] = (time.monotonic(), value)
        return value

    def machine(self) -> dict:
        s = self.sampler.sample()
        hw = jload(self.app.paths.state / "hardware.json", None)
        if hw is None and not getattr(self, "_detecting", False):  # read the machine once, in the background
            self._detecting = True
            threading.Thread(target=self._detect, daemon=True).start()
        hw = hw or {}
        try:
            disk = psutil.disk_usage(str(self.app.paths.data.anchor or "/"))
        except OSError:
            disk = None
        bat = s["battery"]
        mem = s["mem"]
        return {
            "cpu": s["cpu"],
            "cores": s["cores"],
            "mem": mem["pct"],
            "mem_used": mem["used"],
            "mem_total": mem["total"],
            "swap": (s["swap"] or {}).get("pct", 0),
            "rx": s["net"]["all_rx"],
            "tx": s["net"]["all_tx"],
            "temps": s["temps"],
            "battery": None if bat is None else {"percent": bat["pct"], "ac": bat["ac"], "secs": bat["secs"]},
            "disk_free": disk.free if disk else 0,
            "disk_total": disk.total if disk else 1,
            "uptime": s["uptime"],
            "profile": (hw.get("recommendation") or {}).get("profile"),
            "gpus": (hw.get("machine") or {}).get("gpus", []),
            # the dense STATUS board (core/vitals.py has what each one means)
            "threads": s["threads"],
            "phys": s["phys"],
            "cpu_name": s["cpu_name"],
            "freq": s["freq"],
            "load": s["load"],
            "fans": s["fans"],
            "memx": mem,
            "swapx": s["swap"],
            "gpu": s["gpu"],
            "net": s["net"],
            "disks": s["disks"],
            "io": s["io"],
            "power": bat,
            "hist": {**s["hist"], "cores": [h[-40:] for h in s["core_hist"]]},
        }

    def _detect(self) -> None:
        from dataclasses import asdict

        from kurooto.core import hardware
        from kurooto.core.state import jsave

        m = hardware.detect(self.app.paths.app)
        jsave(
            self.app.paths.state / "hardware.json",
            {"machine": m.to_dict(), "recommendation": asdict(hardware.recommend(m)), "at": time.time()},
        )

    # ---------------------------------------------------------------------------------------- Kurooto's side
    def _watch(self) -> dict[str, tuple[str, ...]]:
        """The features that name processes as their own work (Module.processes), that are on."""
        out = {}
        for m in self.app.modules.values():
            names = tuple(getattr(m, "processes", ()) or ()) or CELL_PROCS.get(m.id, ())
            if names and self.app.is_on(m.id):
                out[m.id] = names
        return out

    def _own(self) -> dict:
        """Kurooto's own processes (pid -> label) and each watching feature's (feature -> pids)."""
        own = own_pids(os.getpid())
        watch = self._watch()
        mine: dict[str, set[int]] = {cell: set() for cell in watch}
        if watch:
            for p in psutil.process_iter(
                ["name", "cmdline"] if any("/" in w or "." in w for ws in watch.values() for w in ws) else ["name"]
            ):
                name = (p.info.get("name") or "").lower()
                cmd = " ".join(p.info.get("cmdline") or []) if "cmdline" in p.info else ""
                for cell, wanted in watch.items():
                    if any(name.startswith(w.lower()) or ("/" in w or "." in w) and w in cmd for w in wanted):
                        mine[cell].add(p.pid)
                        own.setdefault(p.pid, p.info.get("name") or cell)
        terms = self.app.modules.get("terminals")
        if terms is not None and self.app.is_on("terminals"):
            for t in list(getattr(terms, "terms", {}).values()):
                pty = getattr(t, "pty", None)
                pid = getattr(getattr(pty, "p", None), "pid", None) or getattr(pty, "pid", None)
                if pid:
                    mine.setdefault("terminals", set()).update(own_pids(pid))
        awake = self.app.modules.get("awake")
        holder = getattr(awake, "holder", None) if awake is not None and self.app.is_on("awake") else None
        if holder is not None and holder.poll() is None:
            mine.setdefault("awake", set()).add(holder.pid)
        return {"pids": own, "cells": mine, "watched": set(watch)}

    def _sum(self, pids: set[int]) -> dict:
        """cpu (1.0 = one core), memory, threads and uptime of these processes together; {} if none is running."""
        cpu = mem = threads = 0
        started = None
        for pid in pids:
            try:
                p = self._procs.get(pid)
                if p is None:  # the same object each time: its cpu reading is the use since the last one
                    p = self._procs[pid] = psutil.Process(pid)
                with p.oneshot():
                    cpu += p.cpu_percent(None) / 100
                    mem += p.memory_info().rss
                    threads += p.num_threads()
                    started = min(started or p.create_time(), p.create_time())
            except (psutil.Error, OSError):
                self._procs.pop(pid, None)
                continue
        if started is None:
            return {}
        return {"cpu": round(cpu, 4), "mem": mem, "threads": threads, "up": time.time() - started, "n": len(pids)}

    def _today(self, sched: list) -> dict:
        """Today: classes, calendar events and what's scheduled for you (not Kurooto's own upkeep), and any focus
        or no-calls hold."""
        app, t = self.app, now()
        day, items = t.date(), []
        subj = app.modules.get("subjects")
        if subj is not None and app.is_on("subjects"):
            skipped = subj.skipped(day)
            for c in subj.classes_on(day, include_skipped=True):
                state = (
                    "skipped"
                    if c["subject"] in skipped
                    else "now"
                    if c["start_dt"] <= t < c["end_dt"]
                    else "done"
                    if c["end_dt"] <= t
                    else "next"
                )
                items.append(
                    {"at": f"{c['start_dt']:%H:%M}", "end": f"{c['end_dt']:%H:%M}", "what": c["name"], "kind": "class",
                     "state": state}
                )  # fmt: skip
        cal = app.modules.get("calendar")
        if cal is not None and app.is_on("calendar"):
            ta = dt.datetime.now().astimezone()  # the calendar's times carry their zone
            for e in cal.day(day)[:12]:
                if e.get("all_day"):
                    continue
                state = "done" if e["end_dt"] <= ta else "now" if e["start_dt"] <= ta else "next"
                items.append(
                    {"at": f"{e['start_dt']:%H:%M}", "end": f"{e['end_dt']:%H:%M}", "what": e["title"][:60],
                     "kind": "event", "state": state}
                )  # fmt: skip
        end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0)).timestamp()
        for j in sched:
            if j.next_run >= end or (j.spec or "").startswith("every") or PLUMBING.search(j.action):
                continue
            if j.action.startswith("updates."):
                continue
            mod = j.module or j.action.partition(".")[0]
            kind = "call" if mod in ("calls", "alarm") else "job"
            items.append(
                {"at": time.strftime("%H:%M", time.localtime(j.next_run)), "what": j.label[:60], "kind": kind,
                 "state": "next", "module": mod}
            )  # fmt: skip
        items.sort(key=lambda x: x["at"])
        av = app.availability
        focus, quiet = av.focus_until(), av.quiet_until()
        return {
            "items": items[:16],
            "focus": f"{focus:%H:%M}" if focus else None,
            "quiet": f"{quiet:%H:%M}" if quiet else None,
        }

    def _models(self) -> list[dict] | None:
        """Models loaded in Ollama right now, if Local AI models is on."""
        lm = self.app.modules.get("local_models")
        if lm is None or not self.app.is_on("local_models"):
            return None
        try:
            with lm.api("/api/ps", timeout=0.8) as r:
                ms = json.loads(r.read()).get("models", [])
        except (OSError, ValueError):
            return []
        return [{"name": m.get("name", "?"), "vram": m.get("size_vram", 0)} for m in ms]

    def _study(self) -> list[dict] | None:
        st = self.app.modules.get("study")
        if st is None or not self.app.is_on("study"):
            return None
        subj = self.app.modules.get("subjects")
        rows = []
        for slug, secs in sorted(st.totals(1).items(), key=lambda kv: -kv[1]):
            name = subj.name_of(slug) if subj is not None else slug
            rows.append({"name": name or slug, "seconds": round(secs)})
        return rows[:6]

    def _projects(self) -> list[dict]:
        """look.projects (or Research's repositories): each one's last commit and what isn't pushed yet."""
        s = self.app.settings
        folders = s.get("look.projects") or (s.get("research.repos") if self.app.is_on("research") else []) or []
        git = proc.which("git")
        out = []
        for f in folders[:8]:
            p = Path(str(f)).expanduser()
            row = {"name": p.name or str(p), "last": None, "ahead": None, "dirty": None, "week": None}
            if git and (p / ".git").exists():
                try:
                    r = proc.run([git, "-C", str(p), "log", "-1", "--format=%ct"], timeout=4)
                    row["last"] = int(r.out.strip()) if r.ok and r.out.strip().isdigit() else None
                    r = proc.run([git, "-C", str(p), "rev-list", "--count", "--since=7.days", "HEAD"], timeout=4)
                    row["week"] = int(r.out.strip()) if r.ok and r.out.strip().isdigit() else None
                    r = proc.run([git, "-C", str(p), "rev-list", "--count", "@{u}..HEAD"], timeout=4)
                    row["ahead"] = int(r.out.strip()) if r.ok and r.out.strip().isdigit() else None
                    r = proc.run([git, "-C", str(p), "status", "--porcelain", "-uno"], timeout=4)
                    row["dirty"] = len(r.out.splitlines()) if r.ok else None
                except OSError:
                    pass
            out.append(row)
        return out

    def _events_today(self) -> int:
        today = now().date().isoformat()
        return sum(1 for e in self.app.events.tail(5000) if str(e.get("ts", "")).startswith(today))

    def _brain_name(self) -> dict:
        main = self.app.settings.get("brain.main") or ""
        if self._brain[0] != main:
            from kurooto import providers

            self._brain = (main, providers.CHOICES.get(main, main))
        return {"id": main, "label": self._brain[1]}

    def _link(self) -> dict | None:
        """The call line's link (Phone calls): connected, since when, the last heartbeat; None when it's off."""
        calls = self.app.modules.get("calls")
        if calls is None or not self.app.is_on("calls"):
            return None
        c = getattr(calls, "connector", None)
        pong = getattr(c, "last_pong", 0) or 0
        return {
            "connected": bool(getattr(c, "connected", False)),
            "since": getattr(c, "connected_since", 0) or None,
            "beat": time.time() - pong if pong else None,
        }

    def board(self, recent: list[dict] | None = None, sched: list | None = None) -> dict:
        """Kurooto's side of the dense board and `kurooto top`: each feature that's on (its processes, its last event,
        its next scheduled run), Kurooto's own process, the call line, today, what's due, the AI's corner, study
        today, projects, and the number of events today."""
        app = self.app
        recent = app.events.tail(400) if recent is None else recent
        sched = app.scheduler.jobs() if sched is None else sched
        nowts = time.time()
        counts: dict[str, int] = {}
        last: dict[str, float] = {}
        for e in recent:
            try:
                ts = time.mktime(time.strptime(e["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
            except (KeyError, ValueError):
                continue
            last[cell_of(e["kind"])] = ts
            if nowts - ts < 120:
                counts[cell_of(e["kind"])] = counts.get(cell_of(e["kind"]), 0) + 1
        nxt: dict[str, float] = {}
        for j in sched:
            mod = j.module or j.action.partition(".")[0]  # a job's feature (one-off jobs may not say)
            if j.next_run >= nowts and mod not in nxt:
                nxt[mod] = j.next_run
        own = self._cached("own", 10, self._own, {"pids": {}, "cells": {}, "watched": set()})
        features = []
        for m in app.enabled():
            pids = own["cells"].get(m.id)
            p = self._sum(pids) if pids else None
            now_and_then = m.id in own["watched"] and bool(getattr(m, "processes_intermittent", False))
            features.append(
                {
                    "id": m.id,
                    "title": m.title,
                    "events": counts.get(m.id, 0),
                    "last": nowts - last[m.id] if m.id in last else None,
                    "next": nxt.get(m.id),
                    "proc": p or None,
                    "down": m.id in own["watched"] and not p and not now_and_then,  # its programs should run
                    "idle": now_and_then and not p,  # programs that run now and then (Module.processes_intermittent)
                    "intermittent": now_and_then,
                }
            )
        deadlines, open_n = [], 0
        dmod = app.modules.get("deadlines")
        if dmod and app.is_on("deadlines"):
            deadlines = [
                {"title": it["title"], "hours": round(h, 1), "kind": it["kind"], "subject": it.get("subject")}
                for _, it, h in dmod.upcoming(336)[:8]
            ]
            open_n = sum(1 for it in dmod.items().values() if it.get("status") == "open")
        first = next((j for j in sched if j.next_run >= nowts), None)
        calls = [
            {"when": j.next_run, "what": j.label[:60]}
            for j in sched
            if (j.module or j.action.partition(".")[0]) in ("calls", "alarm")
            and j.kind == "once"
            and j.next_run >= nowts
        ][:3]
        return {
            "name": app.name,
            "version": __version__,
            "features": features,
            "core": self._sum({os.getpid()}),
            "link": self._link(),
            "today": self._cached("today", 15, lambda: self._today(sched), {"items": []}),
            "deadlines": deadlines,
            "deadlines_open": open_n,
            "agent": {
                "brain": self._brain_name(),
                "models": self._cached("models", 10, self._models),
                "scheduled": len(sched),
                "next": {"what": first.label[:40], "when": first.next_run} if first else None,
            },
            "calls": calls,
            "study": self._cached("study", 30, self._study),
            "projects": self._cached("projects", 60, self._projects, []),
            "events_today": self._cached("events_today", 10, self._events_today, 0),
            "health": self._cached("health", 60, app.health.board, []),  # what needs a look (core/health.py)
        }

    def snapshot(self) -> dict:
        app = self.app
        recent = app.events.tail(400)
        jobs = app.jobs.recent(8)
        running = [j for j in jobs if j.status in ("queued", "running")]
        all_jobs = app.scheduler.jobs()
        b = self.board(recent, all_jobs)
        by_id = {f["id"]: f for f in b["features"]}
        cells = []
        for m in app.modules.values():
            on = app.is_on(m.id)
            n = by_id.get(m.id, {}).get("events", 0)
            act = min(1.0, n / 6) + (0.6 if m.id == "chat" and running else 0)
            cells.append({"id": m.id, "title": m.title, "on": on, "act": min(1.0, act), "events": n})
        sched = [
            {"key": j.key, "when": j.next_run, "what": j.label, "kind": j.kind, "module": j.module}
            for j in all_jobs[:40]
        ]
        own = self._cached("own", 10, self._own, {"pids": {}, "cells": {}, "watched": set()})
        return {
            "t": "body",
            "sys": self.machine(),
            "cells": cells,
            "jobs": [
                {
                    "id": j.id,
                    "title": j.title,
                    "status": j.status,
                    "verdict": j.verdict,
                    "effort": j.effort,
                    "seconds": j.seconds,
                    "created": j.created,
                }
                for j in jobs
            ],
            "schedule": sched,
            "updates": app.updates.status(),
            "power": {"mode": app.power.current, "why": app.power.why()},
            "procs": self.sampler.processes(own=own["pids"].get, n=30),
            **b,
        }


# --------------------------------------------------------------------------------------------- stream
class Live:
    """Fans updates out to every open dashboard page."""

    def __init__(self, app: App):
        self.app = app
        self.clients: dict[int, queue.Queue] = {}
        self.lock = threading.Lock()
        self.graph = Graph(app.workspace)
        self.vitals = Vitals(app)
        self._stop = threading.Event()
        events_mod.subscribe(self._event)
        threading.Thread(target=self._loop, name="live", daemon=True).start()

    def _event(self, rec: dict) -> None:
        self.push({"t": "event", "cell": cell_of(rec.get("kind", "")), **rec})

    def push(self, msg: dict, only: set | None = None) -> None:
        """To every open page, or `only` to these pages (a terminal's output goes to the pages showing it)."""
        data = json.dumps(msg, default=str, separators=(",", ":"))
        with self.lock:
            for cid, q in self.clients.items():
                if only is not None and cid not in only:
                    continue
                try:
                    q.put_nowait(data)
                except queue.Full:
                    pass

    def add(self) -> tuple[int, queue.Queue]:
        q: queue.Queue = queue.Queue(maxsize=2000)
        with self.lock:
            cid = id(q)
            self.clients[cid] = q
        q.put_nowait(json.dumps({"t": "graph", **self.graph.payload}, separators=(",", ":")))
        try:
            q.put_nowait(json.dumps(self.vitals.snapshot(), default=str, separators=(",", ":")))
        except Exception:
            pass
        q.put_nowait(json.dumps({"t": "hello", "cid": cid}, separators=(",", ":")))  # the page's id (terminals)
        return cid, q

    def drop(self, cid: int) -> None:
        with self.lock:
            self.clients.pop(cid, None)
        terms = self.app.modules.get("terminals")
        if terms is not None:
            terms.page_gone(cid)

    def _loop(self) -> None:
        last_graph = 0.0
        while not self._stop.is_set():
            if self.clients:
                try:
                    if time.monotonic() - last_graph > 5:
                        last_graph = time.monotonic()
                        self.graph.root = self.app.workspace
                        if self.graph.scan():
                            self.push({"t": "graph", **self.graph.payload})
                    self.push(self.vitals.snapshot())
                except Exception as e:
                    self.app.events.emit("dashboard_error", error=str(e)[:200])
            self._stop.wait(2)

    def stop(self) -> None:
        self._stop.set()
