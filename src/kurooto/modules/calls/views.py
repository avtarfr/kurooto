"""Systems and the Notes map on the Android app (0.7.0): the dashboard's two drawings, drawn on the phone by the very
same code (web/static/views/), from copies this computer seals for each phone. Off by default (calls.views).

What goes:
  notes    the notes map: each note's path in your notes folder, its title, when it changed and how many words it
           has, and which notes link to which (with the layout's research hub and each project's entry in it, which
           the map uses for its regions). Never what a note says. A big folder is cut to calls.views_notes notes
           (NOTES_MAX by default; the best linked first) and calls.views_links links (LINKS_MAX; the links between the
           least linked notes first: a book's hundreds of
           "Seen in" links go before anything else); the copy says how many were left out.
  systems  what SYSTEMS shows: each feature that's on, how busy it was in the last 2 minutes, its process (cpu,
           memory, threads, uptime), when it last did something and runs next, whether it's down; what needs a look
           (the health lines /health gives); Kurooto's own cpu and memory, the processor's load, and today's classes
           and events as times only (no names), for the clock round the core.

How: each copy is gzipped and sealed once with a fresh key, and that key is sealed for each Android phone with the
phone's own key (line.py "v1": s1 per phone, as the Today list is), so your call line keeps one copy and a short head
per phone and can read neither. It goes over the link in parts ("view-put"), and the call line keeps only the newest of
each. Notes: checked with each state push (every 5 minutes, connector.py), sent when they changed (at most every
NOTES_MIN_S) and once an hour anyway, so "as of" stays near the truth. Systems: only while a phone is watching: the
app says so every ~20 s ("views_watch" from the call line, Calls.on_event), and this sends a fresh copy every
SYSTEMS_S until WATCH_S pass without a word. With this computer asleep, the phone shows its last copy with "as of".

Off (calls.views = false, the dashboard's Phone card): one "view-put {off}" and the call line drops its copies. The
iPhone (web) app gets nothing: it has no key of its own.

The being (0.8.10, calls.views_being, on while calls.views is): the dashboard's board (web/static/being.js) runs on the
phone too, from the Notes map's copy (the graph, with its "Seen in" links) and a "being" block in each Systems copy
(being_snapshot): every feature's cell on or off, the AI requests running and answered lately (their titles), what's
scheduled next (its labels) and the calls booked, the call line's link, this computer's readings (the coil's bars),
Voice's state, the last events (their kinds and times only: they fire the sparks), the board's look, and, when they
changed or a phone starts watching (else at most every SETTINGS_S), the settings its panels show (their values,
without the tooltips) and the Brain's parts with their switches. Never what a note says: a preview is asked for when
you tap a note (chat.py "note.get", answered sealed for that phone).

The Brain (0.8.10, calls.views_brain, with calls.views and Brain on): the Brain console's copy (mind/console.py
snapshot: decisions with their reasons and evidence, the timeline, each part's switches and what it's doing,
experiments, beliefs, skills, plans, the model of you, senses as counts, what it forgot, stops and limits, the journal
and story headings; nothing named for money or health), sealed the same way as kind "brain". Sent only while a phone
watches it (the app's /view/watch?kind=brain, every ~20 s), every BRAIN_S; the call line keeps the last copy for when
this computer is asleep. Turned off (calls.views_brain, mind.console.on or Brain), the next watch gets an "off" copy in
its place, so the phone keeps nothing of the Brain.
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import hashlib
import json
import time
from collections import Counter
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.calls import line

if TYPE_CHECKING:
    from kurooto.modules.calls import Calls

register_defaults(
    "calls",
    {
        "views_brain": True,  # the Brain on the app's Views (with calls.views and Brain on), sent only while watched
    },
)
BRAIN_S = 6  # a fresh Brain copy this often while a phone watches it (it reads the mind log: a little slower)

KINDS = ("notes", "systems")
NOTES_MAX = 5000  # notes in the phone's copy of the map by default (calls.views_notes; the best linked kept)
LINKS_MAX = 20000  # links in it by default (calls.views_links; those between the least linked notes kept first)
# (0.7.2: were 1500 and 6000, a guess at what an old phone draws smoothly; a copy is gzipped, so 2,600 notes is far
# below VIEW_MAX. A copy that would still be too big is cut further, a quarter at a time: fit_notes)
TITLE_MAX = 80
NOTES_MIN_S = 180  # changed notes go at most this often
NOTES_REFRESH_S = 3600  # unchanged, the same copy goes again this often ("as of" on the phone)
SYSTEMS_S = 4  # a fresh Systems copy this often while a phone watches
WATCH_S = 30  # ...until this long without the phone saying it's still watching (it says so every ~20 s)
KEYS_S = 60  # the phones' keys are asked for again after this long
PART = 96 * 1024  # bytes of a sealed copy per "view-put" (the call line's VIEW_PART)
VIEW_MAX = 2 * 1024 * 1024  # the most a sealed copy may be (24 parts: the call line's VIEW_PARTS)
HEALTH_ROWS = 8
# the being (0.8.10): how much of each list goes, how far back events go, how often unchanged settings go again
BEING_JOBS, BEING_SCHED, BEING_EVENTS, BEING_EVENT_S = 10, 12, 40, 600
SETTINGS_S = 60


def _clip(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def trim_notes(payload: dict, notes_max: int = NOTES_MAX, links_max: int = LINKS_MAX) -> dict:
    """The notes graph (web/live.py Graph.payload) as the phone's copy: notes as [path, title, mtime, words] in path
    order, links as pairs of their places in that list ([i, j, 1] for a link only in a provenance block: "Seen in", a
    reading list), cut to notes_max notes and links_max links (provenance-only ones go first)."""
    nodes, links = list(payload.get("nodes") or []), list(payload.get("links") or [])
    via = {(e[0], e[1]) for e in links if len(e) > 2 and e[2]}
    deg: Counter = Counter()
    for e in links:
        deg[e[0]] += 1
        deg[e[1]] += 1
    total = {"notes": len(nodes), "links": len(links)}
    if len(nodes) > notes_max:
        nodes = sorted(nodes, key=lambda n: (-deg[n["id"]], -float(n.get("mtime") or 0), n["id"]))[:notes_max]
    nodes.sort(key=lambda n: n["id"])
    at = {n["id"]: i for i, n in enumerate(nodes)}
    pairs = sorted({(at[e[0]], at[e[1]]) for e in links if e[0] in at and e[1] in at})
    ids = [n["id"] for n in nodes]
    if len(pairs) > links_max:
        seen_in = lambda p: (ids[p[0]], ids[p[1]]) in via  # noqa: E731
        pairs = sorted(sorted(pairs, key=lambda p: (seen_in(p), deg[ids[p[0]]] + deg[ids[p[1]]], p))[:links_max])
    research = {}
    for p, e in sorted((payload.get("research") or {}).items())[:30]:
        research[str(p)[:80]] = {
            "name": _clip(e.get("name"), 60),
            "topics": [t for t in e.get("topics") or [] if t in at][:40],
        }
    lay = payload.get("layout") or {}
    return {
        "v": 1,
        "kind": "notes",
        "nodes": [
            [
                n["id"][:200],
                _clip(n.get("title") or n["id"], TITLE_MAX),
                int(n.get("mtime") or 0),
                int(n.get("words") or 0),
            ]
            for n in nodes
        ],
        "links": [[a, b, 1] if (ids[a], ids[b]) in via else [a, b] for a, b in pairs],
        "layout": {k: str(v)[:120] for k, v in lay.items() if k in ("research", "project")},
        "research": research,
        "total": total,
        "cut": {"notes": total["notes"] - len(nodes), "links": total["links"] - len(pairs)},
    }


def fit_notes(payload: dict, notes_max: int, links_max: int, limit: int = VIEW_MAX) -> dict:
    """trim_notes, cut a quarter at a time while the gzipped copy would be bigger than 90% of limit (sealing adds a
    little), so a huge folder still reaches the phone instead of failing as "too big"."""
    while True:
        snap = trim_notes(payload, notes_max, links_max)
        size = len(gzip.compress(json.dumps(snap, ensure_ascii=False, separators=(",", ":")).encode(), mtime=0))
        if size <= limit * 0.9 or notes_max <= 50:
            return snap
        notes_max, links_max = max(50, notes_max * 3 // 4), max(50, links_max * 3 // 4)


class PhoneViews:
    """The phone app's copies of SYSTEMS and the notes map: made, sealed for each Android phone and handed over."""

    def __init__(self, calls: Calls):
        self.calls = calls
        self.app = calls.app
        self.file = calls.dir / "views.json"  # what was handed over: on, and per kind its rev, digest, when, size
        self.graph = None  # the notes graph, read again only where files changed (web/live.py Graph)
        self.vitals = None  # what SYSTEMS reads (web/live.py Vitals), made on first use
        self.until = 0.0  # a phone watches Systems until then
        self.looping = False  # Systems copies are being sent (on the connector's loop)
        self.keys_at, self.keys = 0.0, {}
        self.dirty = False
        self.watchers: set[str] = set()  # the phones watching in this stretch (a new one gets the being's settings)
        self.being_sent = ("", 0.0)  # the being's settings and Brain parts last sent: their digest, when
        self._api = None  # the dashboard's own handlers (web/api.py), for the settings the being's panels show

    def on(self) -> bool:
        return self.calls.setting("views") is True

    # ------------------------------------------------------------------------------------------ the copies
    def notes_snapshot(self) -> dict:
        from kurooto.web.live import Graph, graph_layout

        root = self.app.workspace
        if self.graph is None or self.graph.root != root:
            self.graph = Graph(root)
        self.graph.lay = graph_layout(self.app)
        self.graph.scan()
        n = int(self.calls.setting("views_notes") or NOTES_MAX)
        e = int(self.calls.setting("views_links") or LINKS_MAX)
        return fit_notes(self.graph.payload, max(50, n), max(50, e))

    def systems_snapshot(self) -> dict:
        import psutil

        from kurooto.web.live import Vitals, cells_of

        app = self.app
        if self.vitals is None:
            self.vitals = Vitals(app)
        b = self.vitals.board()
        busy = any(j.status in ("queued", "running") for j in app.jobs.active())
        health: dict[str, str] = {}
        rows = []
        for r in (b.get("health") or [])[:HEALTH_ROWS]:
            line_ = _clip(f"{r.get('title', '')}: {r.get('detail', '')}", 160)
            health.setdefault(str(r.get("id")), line_)
            rows.append(
                {"id": str(r.get("id")), "title": _clip(r.get("title"), 60), "detail": _clip(r.get("detail"), 140)}
            )
        features = []
        for f in b["features"]:
            p = f.get("proc") or None
            features.append(
                {
                    "id": f["id"],
                    "title": _clip(f["title"], 60),
                    "events": int(f.get("events") or 0),
                    "last": None if f.get("last") is None else int(f["last"]),
                    "next": None if f.get("next") is None else int(f["next"]),
                    "proc": {
                        "cpu": round(float(p.get("cpu") or 0), 4),
                        "mem": int(p.get("mem") or 0),
                        "threads": int(p.get("threads") or 0),
                        "up": int(p.get("up") or 0),
                        "n": int(p.get("n") or 1),
                    }
                    if p
                    else None,
                    "down": bool(f.get("down")),
                    "idle": bool(f.get("idle")),
                    "intermittent": bool(f.get("intermittent")),
                    **({"health": health[f["id"]]} if f["id"] in health else {}),
                }
            )
        core = b.get("core") or {}
        link = b.get("link")
        items = [
            {k: x[k] for k in ("at", "end", "kind", "state") if k in x}  # times only: the clock draws no names
            for x in ((b.get("today") or {}).get("items") or [])
        ]
        try:
            cpu, mem = psutil.cpu_percent(interval=None) / 100, psutil.virtual_memory().percent / 100
        except Exception:
            cpu = mem = 0.0
        return {
            "v": 1,
            "kind": "systems",
            "name": _clip(app.name, 40),
            "version": str(b.get("version") or ""),
            "sys": {"cpu": round(cpu, 3), "mem": round(mem, 3)},
            "cells": [
                {k: c[k] for k in ("id", "title", "act", "events")}
                for c in cells_of(app, b["features"], busy)
                if c["on"]
            ],
            "features": features,
            "core": {"cpu": round(float(core.get("cpu") or 0), 4), "mem": int(core.get("mem") or 0)} if core else {},
            "link": {"connected": bool(link.get("connected"))} if link else None,
            "today": {"items": items[:16]},
            "health": rows,
            **({"being": self.being_snapshot(b)} if self.calls.setting("views_being") is not False else {}),
        }

    # ------------------------------------------------------------------------------------------ the being
    def being_snapshot(self, board: dict | None = None) -> dict:
        """What the being on the phone (Views → Being, 0.8.10) draws beyond Systems, in the dashboard's own shapes
        (web/live.py snapshot: cells, jobs, schedule, link, calls, sys; GET /api/voice, /api/settings, /api/brain3d)
        so being.js reads them as it does there. No note text, no tooltips."""
        from kurooto.web.live import cells_of

        app = self.app
        if self.vitals is None:
            from kurooto.web.live import Vitals

            self.vitals = Vitals(app)
        b = board if board is not None else self.vitals.board()
        jobs = app.jobs.recent(BEING_JOBS)
        seen = {j.id for j in jobs}
        jobs = [j for j in app.jobs.active() if j.id not in seen] + jobs
        busy = any(j.status in ("queued", "running") for j in jobs)
        nowts = time.time()
        sched = [j for j in app.scheduler.jobs() if j.next_run >= nowts - 60]
        sched.sort(key=lambda j: j.next_run)
        link = b.get("link")
        out = {
            "cells": [
                {
                    "id": c["id"],
                    "title": _clip(c["title"], 60),
                    "on": bool(c["on"]),
                    "act": round(float(c["act"]), 3),
                    "events": int(c["events"]),
                }  # fmt: skip
                for c in cells_of(app, b["features"], busy)
            ],
            "jobs": [{"status": j.status, "title": _clip(j.title, 60)} for j in jobs[:BEING_JOBS]],
            "schedule": [{"when": int(j.next_run), "what": _clip(j.label, 60)} for j in sched[:BEING_SCHED]],
            "calls": [{"when": int(c["when"]), "what": _clip(c.get("what"), 60)} for c in b.get("calls") or []],
            "link": {"connected": bool(link.get("connected")), "beat": link.get("beat")} if link else {"off": True},
            "sys": self._being_sys(),
            "events": self._being_events(nowts),
            "voice": self._being_voice(),
            "look": {
                "theme": str(app.settings.get("look.being_theme") or "void"),
                "hints": app.settings.get("look.being_hints") is not False,
                "rest": app.settings.get("look.being_resting_sparks") is not False,
            },
        }
        out.update(self._being_settings())
        return out

    def _being_sys(self) -> dict:
        """This computer's readings for the coil (being.js pcHTML) and the heat it feels: the dashboard's, cut down."""
        try:
            s = self.vitals.machine()
        except Exception:
            return {}
        g = s.get("gpu") or None
        temps = {}
        for k, v in list((s.get("temps") or {}).items())[:4]:
            vals = [float(x) for x in (v if isinstance(v, list) else [v]) if isinstance(x, (int, float))]
            if vals:
                temps[_clip(k, 16)] = round(max(vals), 1)
        bat = s.get("battery")
        return {
            "cpu": round(float(s.get("cpu") or 0), 3),
            "cores": [round(float(c or 0), 3) for c in (s.get("cores") or [])[:16]],
            "mem": round(float(s.get("mem") or 0), 3),
            "mem_used": int(s.get("mem_used") or 0),
            "mem_total": int(s.get("mem_total") or 0),
            "swap": round(float(s.get("swap") or 0), 3),
            "gpu": {k: g.get(k) for k in ("asleep", "util", "temp", "mem_used", "mem_total") if k in g}
            if isinstance(g, dict)
            else None,
            "disks": [
                {
                    "mount": _clip(d.get("mount"), 24),
                    "pct": round(float(d.get("pct") or 0), 3),
                    "free": int(d.get("free") or 0),
                }
                for d in (s.get("disks") or [])[:3]
                if isinstance(d, dict)
            ],
            "battery": {"percent": bat.get("percent"), "ac": bool(bat.get("ac"))} if isinstance(bat, dict) else None,
            "temps": temps,
            "cpu_name": _clip(s.get("cpu_name"), 60),
            "load": [round(float(x), 2) for x in (s.get("load") or [])[:3]],
        }

    def _being_events(self, nowts: float) -> list[dict]:
        """The last events, kind and time only (a phone's sense reading keeps its number): the sparks."""
        out = []
        for e in self.app.events.tail(BEING_EVENTS):
            try:
                ts = time.mktime(time.strptime(str(e.get("ts", ""))[:19], "%Y-%m-%dT%H:%M:%S"))
            except ValueError:
                continue
            if nowts - ts > BEING_EVENT_S:
                continue
            row = {"kind": _clip(e.get("kind"), 40), "ts": int(ts)}
            if e.get("kind") == "senses_phone" and isinstance(e.get("value"), (int, float)):
                row.update(sensor=_clip(e.get("sensor"), 30), value=e["value"])
            out.append(row)
        return out

    def _being_voice(self) -> dict | None:
        """Voice's state for the ear and the mute button (GET /api/voice, cut down); None without Voice."""
        v = self.app.modules.get("voice")
        if v is None:
            return None
        try:
            st = v.status()
        except Exception:
            return None
        sp = st.get("speak") or {}
        return {
            "on": bool(st.get("on")),
            "state": _clip(st.get("state"), 30),
            "listening": bool(st.get("listening")),
            "why": _clip(st.get("why"), 80),
            "portal": bool(st.get("portal")),
            "muted": bool(st.get("muted")),
            "line": _clip(st.get("line"), 160),
            "speak": {"engine": _clip(sp.get("engine"), 30), "voice": _clip(sp.get("voice"), 30)},
        }

    def _being_settings(self) -> dict:
        """The settings the being's panels show (GET /api/settings without the tooltips) and the Brain's parts with
        their switches (GET /api/brain3d, cut to what being.js reads), when they changed, a phone started watching or
        SETTINGS_S passed; else only their digest (the phone keeps the last ones)."""
        from kurooto.core import brainview

        if self._api is None:
            from kurooto.web.api import Api

            self._api = Api(self.app)
        try:
            secs = [{k: v for k, v in s.items() if k != "tips"} for s in self._api._settings().get("sections") or []]
        except Exception:
            secs = []
        try:
            b = brainview.view(self.app)
            brain = {
                "on": bool(b.get("on")),
                "islands": [
                    {"id": i.get("id"), "comps": [[c[0], c[1], c[2], c[3], [], c[5], ""] for c in i.get("comps") or []]}
                    for i in b.get("islands") or []
                ],
            }
        except Exception:
            brain = None
        body = json.dumps([secs, brain], sort_keys=True, default=str)
        digest = hashlib.sha256(body.encode()).hexdigest()[:16]
        was, at = self.being_sent
        if digest == was and time.time() - at < SETTINGS_S:
            return {"settings_digest": digest}
        self.being_sent = (digest, time.time())
        return {
            "settings_digest": digest,
            "settings": {"sections": json.loads(json.dumps(secs, default=str))},
            "brain": brain,
        }

    # ---------------------------------------------------------------------------------------- handing over
    async def _phones(self, c, fresh: bool = False) -> dict[str, str]:
        """The Android phones that gave a key: {device id: public key}."""
        if fresh or time.time() - self.keys_at > KEYS_S:
            devs = await c.admin("devices")
            self.keys = {
                str(d["id"]): str(d["seal"])
                for d in devs.get("devices") or []
                if d.get("kind") == "android" and d.get("seal")
            }
            self.keys_at = time.time()
        return self.keys

    def _rev(self, kind: str) -> int:
        with Lock(self.app.paths.state, "calls-views"):
            st = jload(self.file, {}) or {}
            k = st.setdefault(kind, {})
            rev = max(int(k.get("rev") or 0) + 1, time.time_ns() // 1000)
            k["rev"] = rev
            jsave(self.file, st)
            return rev

    def _note(self, kind: str, **kw) -> None:
        with Lock(self.app.paths.state, "calls-views"):
            st = jload(self.file, {}) or {}
            st.setdefault(kind, {}).update(kw)
            jsave(self.file, st)

    async def put(self, c, kind: str, snap: dict, keys: dict[str, str]) -> dict:
        """Seal one copy (v1: once, with its key sealed for each phone) and hand it over in parts."""
        snap = {**snap, "made": int(time.time())}
        text = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
        key, blob = await asyncio.to_thread(line.pack_v1, text)
        if len(blob) > VIEW_MAX:
            return {"error": "too big", "bytes": len(blob)}
        rev = await asyncio.to_thread(self._rev, kind)
        head = line.head_v1(kind, rev, key, blob)
        seal = {}
        for dev, pub in keys.items():
            try:
                seal[dev] = line.seal_s1(pub, head)
            except ValueError:
                continue  # not a key: that phone gets nothing until it sends a good one
        if not seal:
            return {"ok": True, "phones": 0}
        parts = [blob[i : i + PART] for i in range(0, len(blob), PART)]
        for i, part in enumerate(parts):
            extra = {"keys": seal, "size": len(blob)} if i == 0 else {}
            res = await c.admin(
                "view-put", view=kind, rev=rev, part=i, parts=len(parts), data=base64.b64encode(part).decode(), **extra
            )
            if res.get("error"):
                return res
        return {"ok": True, "phones": len(seal), "bytes": len(blob), "raw": len(text), "parts": len(parts), "rev": rev}

    async def push(self, c) -> dict:
        """With each state push (connector.py): turned off, the call line drops its copies (once); on, the notes map
        goes when it changed (at most every NOTES_MIN_S) or is NOTES_REFRESH_S old, or a phone is new."""
        st = jload(self.file, {}) or {}
        if not self.on():
            if st.get("on"):
                res = await c.admin("view-put", off=True)
                if not res.get("error") or res["error"] == "unknown op":
                    self._set_on(False)
            return {"ok": True, "off": True}
        if not st.get("on"):
            self._set_on(True)
        keys = await self._phones(c, fresh=True)
        if not keys:
            return {"ok": True, "phones": 0}
        snap = await asyncio.to_thread(self.notes_snapshot)
        body = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(json.dumps([body, sorted(keys.items())]).encode()).hexdigest()
        was = st.get("notes") or {}
        t, at = time.time(), float(was.get("at") or 0)
        same_phones = was.get("phones_digest") == hashlib.sha256(json.dumps(sorted(keys)).encode()).hexdigest()
        if digest == was.get("digest") and t - at < NOTES_REFRESH_S:
            return {"ok": True, "same": True}
        if same_phones and digest != was.get("digest") and t - at < NOTES_MIN_S:
            return {"ok": True, "soon": True}  # changed again too soon: the next state push takes it
        res = await self.put(c, "notes", snap, keys)
        if res.get("error"):
            if res["error"] != "unknown op":  # an older call line: nothing to do until it's updated
                self.app.events.emit("phone_views_failed", view="notes", error=str(res["error"])[:200])
            return res
        self._note(
            "notes",
            digest=digest,
            at=t,
            phones=res.get("phones", 0),
            bytes=res.get("bytes", 0),
            phones_digest=hashlib.sha256(json.dumps(sorted(keys)).encode()).hexdigest(),
        )
        if digest != was.get("digest"):
            self.app.events.emit(
                "phone_views_pushed", view="notes", phones=res.get("phones", 0), bytes=res.get("bytes", 0),
                notes=len(snap["nodes"]), cut=snap["cut"]["notes"],
            )  # fmt: skip
        return res

    def _set_on(self, on: bool) -> None:
        with Lock(self.app.paths.state, "calls-views"):
            st = jload(self.file, {}) or {}
            st["on"] = on
            if not on:
                st.pop("notes", None)  # turned on again later: the map goes at once
            jsave(self.file, st)

    # ---------------------------------------------------------------------------------- watching Systems
    def watch(self, m: dict | None = None) -> bool:
        """A phone has Systems open (the call line passes its "views_watch" on): fresh copies every SYSTEMS_S until
        WATCH_S pass without another word. Called from a thread. False when off or not connected."""
        if (m or {}).get("kind") == "brain":  # the Brain view (0.8.10): its own copies, below
            return self.watch_brain()
        c = self.calls.connector
        if not self.on() or c.loop is None or c.ws is None:
            return False
        started = time.time() >= self.until
        if started:
            self.watchers = set()
        dev = str((m or {}).get("device") or "")
        if dev not in self.watchers:  # a phone that starts watching gets the being's settings in its first copy
            self.watchers.add(dev)
            self.being_sent = ("", 0.0)
        self.until = time.time() + WATCH_S
        if not self.looping:
            self.looping = True
            asyncio.run_coroutine_threadsafe(self._watching(c), c.loop)
            if started:
                self.app.events.emit("phone_views_watching", view="systems")
        return True

    async def _watching(self, c) -> None:
        try:
            while self.on() and time.time() < self.until and c.ws is not None:
                t0 = time.time()
                try:
                    keys = await self._phones(c)
                    if not keys:
                        break
                    snap = await asyncio.to_thread(self.systems_snapshot)
                    res = await self.put(c, "systems", snap, keys)
                    if res.get("error"):
                        if res["error"] != "unknown op":
                            self.app.events.emit("phone_views_failed", view="systems", error=str(res["error"])[:200])
                        break
                except (ConnectionError, TimeoutError):
                    break
                await asyncio.sleep(max(0.5, SYSTEMS_S - (time.time() - t0)))
        finally:
            self.looping = False

    def on_event(self, rec: dict) -> None:
        """calls.views changed (the Phone card, Settings): the state push soon says it to the call line."""
        self.brain_event(rec)
        if rec.get("kind") == "setting_changed" and str(rec.get("key") or "") == "calls.views":
            if not self.on():
                self.until = 0.0
            self.calls.connector.poke()

    # ---------------------------------------------------------------------------------- the Brain (0.8.10)
    brain_until = 0.0  # a phone watches the Brain until then
    brain_looping = False
    brain_sent_off = False  # an "off" copy went in place of the last one

    def brain_on(self) -> bool:
        """calls.views and calls.views_brain on, Brain on, and its console's switch (mind.console.on) on."""
        from kurooto import mind
        from kurooto.mind import console

        return (
            self.on() and self.calls.setting("views_brain") is not False and mind.on(self.app) and console.on(self.app)
        )

    def brain_snapshot(self) -> dict:
        """The Brain console's copy for the phone (mind/console.py): plain facts, decisions with their evidence."""
        from kurooto.mind import console

        return console.snapshot(self.app, phone=True)

    def brain_off_snapshot(self) -> dict:
        from kurooto import mind

        if not mind.on(self.app):
            why = "Brain is off on your computer (Features → Brain)."
        elif self.calls.setting("views_brain") is False:
            why = "The Brain on the phone is off on your computer (Settings → Phone calls → views_brain)."
        else:
            why = "The Brain console is off on your computer (mind.console.on)."
        return {"v": 1, "kind": "brain", "off": True, "why": why}

    def watch_brain(self) -> bool:
        """A phone has the Brain open: fresh copies every BRAIN_S until WATCH_S pass without another word; turned
        off, one "off" copy replaces what the call line kept. Called from a thread."""
        c = self.calls.connector
        if not self.on() or c.loop is None or not c.loop.is_running() or c.ws is None:
            return False
        started = time.time() >= self.brain_until
        self.brain_until = time.time() + WATCH_S
        if not self.brain_looping:
            self.brain_looping = True
            asyncio.run_coroutine_threadsafe(self._watching_brain(c), c.loop)
            if started:
                self.app.events.emit("phone_views_watching", view="brain")
        return True

    async def _watching_brain(self, c) -> None:
        try:
            while self.on() and time.time() < self.brain_until and c.ws is not None:
                t0 = time.time()
                try:
                    keys = await self._phones(c)
                    if not keys:
                        break
                    if not self.brain_on():
                        if not self.brain_sent_off:
                            res = await self.put(c, "brain", self.brain_off_snapshot(), keys)
                            self.brain_sent_off = not res.get("error")
                        break
                    snap = await asyncio.to_thread(self.brain_snapshot)
                    res = await self.put(c, "brain", snap, keys)
                    if res.get("error"):
                        if res["error"] != "unknown op":
                            self.app.events.emit("phone_views_failed", view="brain", error=str(res["error"])[:200])
                        break
                    self.brain_sent_off = False
                except (ConnectionError, TimeoutError):
                    break
                await asyncio.sleep(max(0.5, BRAIN_S - (time.time() - t0)))
        finally:
            self.brain_looping = False

    def brain_event(self, rec: dict) -> None:
        """calls.views_brain or mind.console.on turned off, or Brain turned off: the phone's copy is replaced by an
        "off" one now, if the line is there (otherwise at the next watch)."""
        key = str(rec.get("key") or "")
        off = (rec.get("kind") == "setting_changed" and key in ("calls.views_brain", "mind.console.on")) or (
            rec.get("kind") == "module_disabled" and rec.get("module") == "mind"
        )
        if not off or self.brain_on() or not self.on():
            return
        self.brain_until = 0.0
        c = self.calls.connector
        if c.loop is None or not c.loop.is_running() or c.ws is None or self.brain_looping:
            return
        self.brain_sent_off = False
        self.brain_looping = True
        self.brain_until = time.time() + 1
        asyncio.run_coroutine_threadsafe(self._watching_brain(c), c.loop)
