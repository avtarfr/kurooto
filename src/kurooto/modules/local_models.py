"""Local models: small AI models on this computer through Ollama, picked for its hardware (see Your computer).
They take quick decisions (how hard a request is) and make the notes-brain index, privately and offline; the
main answers still come from the AI you picked. Not offered on computers without a graphics card or Apple Silicon.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request

from kurooto.core import egress
from kurooto.core.clock import now
from kurooto.core.lock import Lock
from kurooto.core.prereqs import Prereqs
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

OLLAMA = "http://127.0.0.1:11434"


class LocalModels(Module):
    setup_notes = (
        (
            "Ollama runs the models on this computer",
            "dashboard → Features → Local AI models → Set up (installs Ollama, pulls the models)",
            "turning it off offers to remove what Kurooto installed for it; `kurooto installed` and `kurooto remove`",
        ),
    )
    id = "local_models"
    heavy = True  # waits for the charger on battery (saver mode, core/power.py)
    title = "Local AI models"
    description = "Small models on this computer for quick decisions and the notes index: private and offline."
    privacy = "Runs entirely on this computer."

    def __init__(self, app):
        super().__init__(app)
        self.prereqs = Prereqs(app.paths.app, app.paths.cache)

    def wanted(self) -> list[dict]:
        """The models for this computer: what suits it (or the setup you chose: hardware.force_profile), plus the
        models you added (hardware.extra_models)."""
        from kurooto.core import hardware

        cached = (jload(self.app.paths.state / "hardware.json", {}) or {}).get("recommendation") or {}
        overridden = bool(
            self.app.settings.get("hardware.force_profile") or self.app.settings.get("hardware.extra_models")
        )
        rec = cached
        if overridden or not cached:  # your own setup (or nothing known yet): worked out from the machine
            try:
                rec = hardware.current(self.app).get("recommendation") or {}
            except (OSError, ValueError, KeyError, TypeError):
                rec = cached
        return rec.get("local_models") or []

    def vision_model(self) -> dict | None:
        """The model on this computer that reads pictures ({tag, size_gb, ...}): the vision model (12 GB cards), else
        a helper model that sees images too (gemma4:e4b on 8 GB cards). None when there's none."""
        from kurooto.core.hardware import _models

        table = _models().get("models") or {}
        wanted = self.wanted()
        hit = next((m for m in wanted if m.get("key") == "vision"), None)
        hit = hit or next((m for m in wanted if m.get("vision") or (table.get(m.get("key")) or {}).get("vision")), None)
        return hit

    def api(self, path: str, body: dict | None = None, timeout: float = 10):
        req = urllib.request.Request(  # noqa: S310 (Ollama on this computer)
            OLLAMA + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 (Ollama on this computer)

    def running(self) -> bool:
        try:
            with self.api("/api/tags", timeout=3) as r:
                return r.status == 200
        except OSError:
            return False

    def have(self) -> set[str]:
        try:
            with self.api("/api/tags", timeout=5) as r:
                return {m["name"] for m in json.loads(r.read()).get("models", [])}
        except OSError:
            return set()

    def serve(self) -> bool:
        """Start Ollama's server if it isn't running (Windows and macOS usually start it themselves)."""
        if self.running():
            return True
        exe = self.prereqs.items["ollama"].find()
        if not exe:
            return False
        env = {**os.environ, "OLLAMA_HOST": "127.0.0.1:11434"}
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if os.name == "nt" else 0
        child = subprocess.Popen(
            [exe, "serve"],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            start_new_session=os.name != "nt",
        )
        jsave(self.app.paths.state / "ollama-ours.json", {"pid": child.pid})
        from kurooto.core import children

        children.session(child.pid)  # Kurooto started it: it stops with Kurooto (core/children.py)
        import time

        for _ in range(40):
            if self.running():
                return True
            time.sleep(0.5)
        return False

    def ready(self):
        if not self.wanted():
            return False, "this computer is better off without local models (see Your computer)"
        if not self.prereqs.items["ollama"].find():
            return False, "needs setting up (installs Ollama and the models)"
        missing = [
            m["tag"]
            for m in self.wanted()
            if not any(
                h.split(":")[0] == m["tag"].split(":")[0] and (":" not in m["tag"] or h == m["tag"])
                for h in self.have()
            )
        ]
        if self.running() and missing:
            return False, f"needs setting up (downloads {', '.join(missing)})"
        return True, ""

    def setup(self, progress=print) -> tuple[bool, str]:
        models = self.wanted()
        extras = [p for p in (self.app.settings.get("hardware.extra_prereqs") or []) if p in self.prereqs.items]
        for key in extras:  # programs you asked for, installed like any other
            if not self.prereqs.items[key].find():
                ok, msg = self.prereqs.install(key, progress)
                progress(("✓ " if ok else "✗ ") + msg)
        if not models:
            return (
                (True, "Installed what you asked for.")
                if extras
                else (False, "This computer is better off without local models.")
            )
        if not self.prereqs.items["ollama"].find():
            ok, msg = self.prereqs.install("ollama", progress)
            if not ok:
                return False, msg
        if not self.serve():
            return False, "Ollama is installed but its server didn't start; restart the computer and try again."
        have = self.have()
        need = [m for m in models if m["tag"] not in have]
        room = self.prereqs.room([], extra_gb=sum(m["size_gb"] for m in need))
        if not room["ok"]:
            return False, (
                f"Not enough space for the models ({room['need_gb']} GB; {room['free_gb']} GB free and "
                f"{room['margin_gb']:g} GB kept spare)."
            )
        for m in need:
            ok, msg = self.pull(m["tag"], m["size_gb"], progress)
            if not ok:
                return False, msg
        self._wire_up(models)
        return True, "Local models are ready: " + ", ".join(m["tag"] for m in models)

    def pull(
        self, tag: str, size_gb: float, progress=print, feature: str = "Local AI models", by: str = "local_models"
    ) -> tuple[bool, str]:
        """Download one model through Ollama (its server running), with progress every 10%. A model Ollama didn't
        have goes on the receipt for `by` (core/uninstall.py); one it had stays yours."""
        from kurooto.core import uninstall

        had = uninstall.norm(tag) in {uninstall.norm(h) for h in self.have()}
        progress(f"Downloading {tag} ({size_gb:g} GB)…")
        egress.handed("Ollama", feature)  # Ollama downloads it from its registry
        with (
            Lock(self.app.paths.state, "ollama-pull"),
            self.api("/api/pull", {"model": tag, "stream": True}, timeout=3600) as r,
        ):
            last = -1
            for line in r:
                try:
                    st = json.loads(line)
                except ValueError:
                    continue
                if st.get("error"):
                    return False, f"Couldn't download {tag}: {st['error']}"
                if st.get("total"):
                    pct = int(st.get("completed", 0) * 100 / st["total"])
                    if pct // 10 != last:
                        last = pct // 10
                        progress(f"{tag}: {pct}%")
        if not had:
            try:
                size = (uninstall._ollama_tags() or {}).get(uninstall.norm(tag)) or int(size_gb * uninstall.GB)
                uninstall.record_model(self.app.paths.app, tag, size, by)
            except Exception:  # a receipt that can't be written never fails a download
                pass
        return True, ""

    def remove(self, tag: str) -> bool:
        """Remove a model Kurooto downloaded (the offline helper's, when it was too slow here)."""
        req = urllib.request.Request(  # noqa: S310 (Ollama on this computer)
            OLLAMA + "/api/delete",
            data=json.dumps({"model": tag}).encode(),
            headers={"Content-Type": "application/json"},
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(req, timeout=30):  # noqa: S310 (Ollama on this computer)
                pass
        except OSError:
            return False
        from kurooto.core import uninstall

        uninstall.forget(self.app.paths.app, f"model:{uninstall.norm(tag)}")
        return True

    def _wire_up(self, models: list[dict]) -> None:
        """Use the helper model for quick decisions; GBrain uses the embedding model on its own."""
        helper = next((m["tag"] for m in models if m["key"].startswith("helper")), None)
        if helper:
            ms = dict(self.app.settings.get("brain.models") or {})
            ms["ollama"] = {"low": helper, "medium": helper, "high": helper}
            self.app.settings.set("brain.models", ms)
            self.app.settings.set("brain.classify", "ollama")

    def start(self):
        self.every("keepalive", "every 10m", lambda p: self.serve() and self.guard())
        if self.app.power.current == "normal":
            self.serve()

    def loaded(self) -> list[dict]:
        """What Ollama has loaded now: [{"name", "size", "vram"}] (bytes; vram is the part on the graphics card)."""
        try:
            with self.api("/api/ps", timeout=3) as r:
                rows = json.loads(r.read()).get("models", [])
        except (OSError, ValueError):
            return []
        return [
            {"name": m["name"], "size": int(m.get("size") or 0), "vram": int(m.get("size_vram") or 0)} for m in rows
        ]

    def unload(self, name: str) -> None:
        with self.api("/api/generate", {"model": name, "keep_alive": 0}, timeout=30):
            pass

    def guard(self) -> list[str]:
        """No model half on the processor (slow, and it heats the laptop): when models together don't fit the
        graphics card, unload them, so the next request loads its one model fully on the card; a model that doesn't
        fit even alone is told once, with what to do. Returns what it did."""
        rows = self.loaded()
        spilled = [m for m in rows if m["size"] and m["vram"] < m["size"] * 0.98]
        if not spilled:
            return []
        if len(rows) > 1:
            for m in rows:
                try:
                    self.unload(m["name"])
                except OSError:
                    continue
            self.app.events.emit("local_models_spill", models=len(rows), unloaded=True)
            return [f"unloaded {', '.join(m['name'] for m in rows)}"]
        m = spilled[0]
        told = jload(self.app.paths.state / "ollama-spill.json", {}) or {}
        if m["name"] in told:
            return []
        on_cpu = round(100 * (1 - m["vram"] / m["size"]))
        told[m["name"]] = now().isoformat()
        jsave(self.app.paths.state / "ollama-spill.json", told)
        self.app.events.emit("local_models_spill", models=1, unloaded=False, on_cpu=on_cpu)
        self.app.notify(
            f"{m['name']} doesn't fit your graphics card: {on_cpu}% of it runs on the processor, which is slow and "
            "heats the laptop. Pick a smaller model for it (Features → Local AI models, or /models), or keep fewer "
            "programs on the graphics card.",
            kind="info",
            why="local_models.spill",
        )
        return [f"told: {m['name']} {on_cpu}% on the processor"]

    def rest(self) -> None:
        """On battery or paused: free the graphics memory (unload the models), and stop Ollama if we started it."""
        try:
            with self.api("/api/ps", timeout=3) as r:
                loaded = [m["name"] for m in json.loads(r.read()).get("models", [])]
            for name in loaded:
                with self.api("/api/generate", {"model": name, "keep_alive": 0}, timeout=30):
                    pass
        except OSError:
            loaded = []
        ours = (jload(self.app.paths.state / "ollama-ours.json", {}) or {}).get("pid")
        if ours:
            from kurooto.core.proc import kill_tree, pid_alive

            if pid_alive(ours, "ollama"):
                kill_tree(ours)
            (self.app.paths.state / "ollama-ours.json").unlink(missing_ok=True)
        self.app.events.emit("local_models_rest", unloaded=len(loaded), stopped=bool(ours))

    def commands(self):
        return [Command("models", "the local models and whether they're running", self._status)]

    def _status(self, msg: Incoming, arg: str) -> str:
        have = self.have()
        rows = [
            f"{'✓' if m['tag'] in have else '✗'} {m['tag']} ({m['size_gb']:g} GB): {m['use']}" for m in self.wanted()
        ]
        for m in self.loaded():
            share = round(100 * m["vram"] / m["size"]) if m["size"] else 100
            rows.append(
                f"loaded: {m['name']}, {share}% on the graphics card"
                + ("" if share >= 98 else " (the rest on the processor)")
            )
        return ("Ollama is running.\n" if self.running() else "Ollama isn't running.\n") + "\n".join(rows)
