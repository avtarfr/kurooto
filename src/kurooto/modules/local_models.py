"""Local models: small AI models on this computer through Ollama, picked for its hardware (see Your computer).
They take quick decisions (how hard a request is) and make the notes-brain index, privately and offline; the
main answers still come from the AI you picked. Not offered on computers without a graphics card or Apple Silicon.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request

from kurooto.core.lock import Lock
from kurooto.core.prereqs import Prereqs
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

OLLAMA = "http://127.0.0.1:11434"


class LocalModels(Module):
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
            progress(f"Downloading {m['tag']} ({m['size_gb']:g} GB)…")
            with (
                Lock(self.app.paths.state, "ollama-pull"),
                self.api("/api/pull", {"model": m["tag"], "stream": True}, timeout=3600) as r,
            ):
                last = -1
                for line in r:
                    try:
                        st = json.loads(line)
                    except ValueError:
                        continue
                    if st.get("error"):
                        return False, f"Couldn't download {m['tag']}: {st['error']}"
                    if st.get("total"):
                        pct = int(st.get("completed", 0) * 100 / st["total"])
                        if pct // 10 != last:
                            last = pct // 10
                            progress(f"{m['tag']}: {pct}%")
        self._wire_up(models)
        return True, "Local models are ready: " + ", ".join(m["tag"] for m in models)

    def _wire_up(self, models: list[dict]) -> None:
        """Use the helper model for quick decisions; GBrain uses the embedding model on its own."""
        helper = next((m["tag"] for m in models if m["key"].startswith("helper")), None)
        if helper:
            ms = dict(self.app.settings.get("brain.models") or {})
            ms["ollama"] = {"low": helper, "medium": helper, "high": helper}
            self.app.settings.set("brain.models", ms)
            self.app.settings.set("brain.classify", "ollama")

    def start(self):
        self.every("keepalive", "every 10m", lambda p: self.serve())
        if self.app.power.current == "normal":
            self.serve()

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
        return ("Ollama is running.\n" if self.running() else "Ollama isn't running.\n") + "\n".join(rows)
