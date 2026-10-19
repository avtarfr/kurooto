"""Notes brain (GBrain): an index of your notes folder you can search by meaning, which your AI also uses as
memory. It runs on this computer with its own built-in database (no Docker, no server).

Kurooto keeps its brain in its own data folder (never ~/.gbrain), syncs your notes into it every 15 minutes,
and offers /notes <question>. How the index is made depends on your computer:
    ollama   a small embedding model on this computer (computers with a graphics card or Apple Silicon)
    gemini   Google's embedding model with your free Gemini key (computers without one); note text goes to Google
    off      keyword search only; nothing leaves the computer
"""

from __future__ import annotations

import os
from pathlib import Path

from kurooto.core import proc
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.prereqs import Prereqs
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

register_defaults("gbrain", {"embeddings": "auto", "sync": "every 15m"})
MODELS = {"ollama": "ollama:nomic-embed-text", "gemini": "google:gemini-embedding-2"}


class GBrain(Module):
    id = "gbrain"
    heavy = True  # waits for the charger on battery (saver mode, core/power.py)
    title = "Notes brain (GBrain)"
    description = "Search your notes by meaning (/notes …), and give your AI a memory of them."
    privacy = (
        "The index stays on this computer. If it uses Gemini for the index (computers without a graphics "
        "card), note text is sent to Google to make it."
    )

    def __init__(self, app):
        super().__init__(app)
        self.home = app.paths.data / "gbrain"
        self.prereqs = Prereqs(app.paths.app, app.paths.cache)

    # ------------------------------------------------------------------------------------- plumbing
    def exe(self) -> str | None:
        return self.prereqs.items["gbrain"].find()

    def env(self) -> dict:
        env = {**os.environ, "GBRAIN_HOME": str(self.home), "GBRAIN_NO_AUTOPILOT_INSTALL": "1"}
        bun_bin = str(Path.home() / ".bun" / "bin")
        env["PATH"] = bun_bin + os.pathsep + env.get("PATH", "")
        key = self.app.secrets.get("gemini.api_key")
        if key and self.embeddings() == "gemini":
            env["GOOGLE_GENERATIVE_AI_API_KEY"] = key
        return env

    def run(self, *args: str, timeout: float = 600) -> proc.Result:
        exe = self.exe()
        if not exe:
            return proc.Result(1, "", "GBrain isn't installed")
        with Lock(self.app.paths.state, "gbrain"):  # its built-in database allows one writer at a time
            return proc.run(
                [exe, *args], timeout=timeout, env=self.env(), cwd=self.home if self.home.exists() else None
            )

    def embeddings(self) -> str:
        choice = self.setting("embeddings") or "auto"
        if choice != "auto":
            return choice
        hw = jload(self.app.paths.state / "hardware.json", {}) or {}
        if (hw.get("recommendation") or {}).get("embeddings") == "ollama":
            return "ollama"
        return "gemini" if self.app.secrets.get("gemini.api_key") else "off"

    def initialised(self) -> bool:
        return (jload(self.app.paths.state / "gbrain.json", {}) or {}).get("initialised", False)

    # ---------------------------------------------------------------------------------------- setup
    def ready(self):
        if not self.exe():
            return False, "needs setting up (installs Bun and GBrain, about 0.5 GB)"
        if not self.initialised():
            return False, "needs setting up (creates your notes brain)"
        return True, ""

    def setup(self, progress=print) -> tuple[bool, str]:
        """Install what it needs, create the brain, choose the index type, and import your notes once."""
        for key in ("bun", "gbrain"):
            if not self.prereqs.items[key].find():
                ok, msg = self.prereqs.install(key, progress)
                if not ok:
                    return False, msg
        self.home.mkdir(parents=True, exist_ok=True)
        emb = self.embeddings()
        if not self.initialised():
            progress("Creating your notes brain…")
            r = self.run("init", "--pglite", "--no-embedding", timeout=600)
            if not r.ok:
                return False, f"GBrain couldn't create the brain: {(r.err or r.out)[-300:]}"
            self.run("apply-migrations", "--yes", "--no-autopilot-install", timeout=600)
            if emb in MODELS:
                progress(f"Turning on the {emb} index…")
                r = self.run("embeddings", "enable", "--embedding-model", MODELS[emb], timeout=600)
                if not r.ok:
                    progress(f"The {emb} index couldn't start ({(r.err or r.out)[-160:]}); keyword search works.")
                    emb = "off"
            jsave(self.app.paths.state / "gbrain.json", {"initialised": True, "embeddings": emb})
        progress("Reading your notes into it…")
        ok, msg = self.sync()
        return ok, ("Your notes brain is ready. " + msg) if ok else msg

    def sync(self, payload: dict | None = None) -> tuple[bool, str]:
        args = ["import", str(self.app.workspace)]
        if (jload(self.app.paths.state / "gbrain.json", {}) or {}).get("embeddings", "off") == "off":
            args.append("--no-embed")
        r = self.run(*args, timeout=1800)
        out = (r.out or "").strip().splitlines()
        summary = next((ln.strip() for ln in out if "imported" in ln), "")
        self.app.events.emit("gbrain_sync", ok=r.ok)
        return r.ok, summary or (r.err[-200:] if not r.ok else "")

    def start(self):
        self.every("sync", self.setting("sync") or "every 15m", lambda p: self.sync(p))

    # ------------------------------------------------------------------------------------- using it
    def search(self, question: str, n: int = 5) -> str:
        r = self.run("query", question, timeout=120)
        if not r.ok:
            r = self.run("search", question, timeout=120)
        return (r.out or "").strip()

    def commands(self):
        return [Command("notes", "search your notes by meaning: /notes what is a compact space", self._notes)]

    def _notes(self, msg: Incoming, arg: str) -> str:
        if not arg:
            return "Usage: /notes <what you're looking for>"
        out = self.search(arg)
        return out[:3500] if out else "Nothing in your notes about that."
