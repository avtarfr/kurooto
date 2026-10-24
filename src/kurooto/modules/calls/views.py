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

from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.calls import line

if TYPE_CHECKING:
    from kurooto.modules.calls import Calls

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
        c = self.calls.connector
        if not self.on() or c.loop is None or c.ws is None:
            return False
        started = time.time() >= self.until
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
        if rec.get("kind") == "setting_changed" and str(rec.get("key") or "") == "calls.views":
            if not self.on():
                self.until = 0.0
            self.calls.connector.poke()
