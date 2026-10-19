"""What the dashboard shows, kept fresh: the machine (psutil), each feature's activity, the AI jobs, what's
scheduled, and the notes graph (notes and their [[links]] in your notes folder). Pushed to open pages over a
server-sent-events stream; nothing is computed while no page is open."""

from __future__ import annotations

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
from kurooto.core.state import jload

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
class Vitals:
    def __init__(self, app: App):
        self.app = app
        self._net = None
        psutil.cpu_percent(percpu=True)

    def machine(self) -> dict:
        vm, sw = psutil.virtual_memory(), psutil.swap_memory()
        cores = [c / 100 for c in psutil.cpu_percent(percpu=True)]
        io = psutil.net_io_counters()
        now = time.monotonic()
        rx = tx = 0.0
        if self._net:
            dt = max(0.1, now - self._net[0])
            rx, tx = (io.bytes_recv - self._net[1]) / dt, (io.bytes_sent - self._net[2]) / dt
        self._net = (now, io.bytes_recv, io.bytes_sent)
        temps = {}
        try:
            for name, entries in (psutil.sensors_temperatures() or {}).items():
                if entries and name in ("k10temp", "coretemp", "cpu_thermal", "acpitz"):
                    temps["cpu"] = round(entries[0].current)
                    break
        except (AttributeError, OSError):
            pass
        bat = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
        disk = psutil.disk_usage(str(self.app.paths.data.anchor or "/"))
        hw = jload(self.app.paths.state / "hardware.json", None)
        if hw is None and not getattr(self, "_detecting", False):  # read the machine once, in the background
            self._detecting = True
            threading.Thread(target=self._detect, daemon=True).start()
        hw = hw or {}
        return {
            "cpu": sum(cores) / max(1, len(cores)),
            "cores": cores,
            "mem": vm.percent / 100,
            "mem_used": vm.used,
            "mem_total": vm.total,
            "swap": sw.percent / 100,
            "rx": rx,
            "tx": tx,
            "temps": temps,
            "battery": None if bat is None else {"percent": bat.percent, "ac": bat.power_plugged},
            "disk_free": disk.free,
            "disk_total": disk.total,
            "uptime": time.time() - psutil.boot_time(),
            "profile": (hw.get("recommendation") or {}).get("profile"),
            "gpus": (hw.get("machine") or {}).get("gpus", []),
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

    def snapshot(self) -> dict:
        app = self.app
        recent = app.events.tail(400)
        now = time.time()
        counts: dict[str, int] = {}
        for e in recent:
            try:
                age = now - time.mktime(time.strptime(e["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
            except (KeyError, ValueError):
                continue
            if age < 120:
                counts[cell_of(e["kind"])] = counts.get(cell_of(e["kind"]), 0) + 1
        jobs = app.jobs.recent(8)
        running = [j for j in jobs if j.status in ("queued", "running")]
        cells = []
        for m in app.modules.values():
            on = app.is_on(m.id)
            act = min(1.0, counts.get(m.id, 0) / 6) + (0.6 if m.id == "chat" and running else 0)
            cells.append({"id": m.id, "title": m.title, "on": on, "act": min(1.0, act), "events": counts.get(m.id, 0)})
        sched = [
            {
                "key": j.key,
                "when": j.next_run,
                "what": j.payload.get("what") or j.payload.get("name") or j.key,
                "kind": j.kind,
            }
            for j in app.scheduler.jobs()[:40]
        ]
        deadlines = []
        dmod = app.modules.get("deadlines")
        if dmod and app.is_on("deadlines"):
            deadlines = [
                {"title": it["title"], "hours": round(h, 1), "kind": it["kind"]} for _, it, h in dmod.upcoming(336)[:8]
            ]
        return {
            "t": "body",
            "version": __version__,
            "name": app.name,
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
            "deadlines": deadlines,
            "updates": app.updates.status(),
            "power": {"mode": app.power.current, "why": app.power.why()},
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
