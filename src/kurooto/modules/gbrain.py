"""Notes brain (GBrain): an index of your notes folder you can search by meaning, which your AI also uses as
memory. It runs on this computer with its own built-in database (no Docker, no server).

Kurooto keeps its brain in its own data folder (never ~/.gbrain), syncs your notes into it every 15 minutes,
and offers /notes <question>. How the index is made depends on your computer:
    ollama   a small embedding model on this computer (computers with a graphics card or Apple Silicon)
    gemini   Google's embedding model with your free Gemini key (computers without one); note text goes to Google
    off      keyword search only; nothing leaves the computer

Three more things it can do, each on its own switch in Settings:
    timelines  (on)   nightly, dated log lines in your notes ("- **2026-10-19** | source — what happened") become
                      each note's timeline: /timeline <note>, and your AI can ask "when did I ...?"
    upkeep     (off)  nightly upkeep: GBrain's "dream" cycle, light steps only (links, facts, timelines, the index,
                      orphaned pages). Steps that would rewrite your note files or call an AI model are left out.
                      Heavy, so it waits for the charger.
    checkup    (off)  a weekly checkup (GBrain's advisor); you get a message only when something needs a look.
The upkeep's steps are GBrain's own phase names (gbrain.upkeep_steps); add others (lint, sync, the repair steps,
consolidate, edge_contradictions...) if you want them, knowing some rewrite note files or call the AI model GBrain is
set up with. Kurooto never runs purge.

Your own GBrain (gbrain.managed = false): Kurooto uses a GBrain you already run, for example one on Postgres, instead
of making its own: gbrain.exe is your gbrain program (empty: the one on your PATH) and gbrain.home its GBRAIN_HOME
(empty: GBrain's default). Kurooto doesn't own that brain: it never creates, migrates, upgrades or reconfigures it. It
searches it, adds pages through gbrain's own commands (books, for example), keeps one of its sources in step with
your notes when you name it (gbrain.source: `gbrain sync` and `gbrain embed --stale` every 15 minutes), and runs the
nightly steps you turn on. With gbrain.agy_mcp, agy also gets your brain's own MCP server ("gbrain"), after you
approve it like Kurooto's own tools.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import unicodedata
import uuid
from pathlib import Path

from kurooto.core import egress, proc
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock, Timeout
from kurooto.core.prereqs import Prereqs
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module
from kurooto.modules.calls.tools import Tool, arg, clip

register_defaults(
    "gbrain",
    {
        "embeddings": "auto",
        "sync": "every 15m",
        "timelines": True,  # nightly: dated log lines become timelines (no AI, nothing leaves the computer)
        "upkeep": False,  # nightly upkeep, light steps only (heavy: waits for the charger)
        "checkup": False,  # weekly checkup; a message only when something needs a look
        "nightly": "daily 03:00",
        "checkup_when": "weekly sun 19:30",
        "upkeep_steps": [],  # the upkeep's steps (GBrain's phase names); empty: the light ones (UPKEEP_STEPS)
        "managed": True,  # Kurooto runs its own brain; False: your own GBrain (gbrain.exe, gbrain.home)
        "exe": "",  # your own GBrain: your gbrain program; empty: the one on your PATH
        "home": "",  # your own GBrain: its GBRAIN_HOME; empty: GBrain's default
        "source": "",  # your own GBrain: the source that is your notes folder, kept in step (empty: you do that)
        "agy_mcp": False,  # your own GBrain: agy gets its MCP tools too (asked first)
        "mcp_surface": "full",  # what that MCP server offers agy: full | starter | verbs
        # checkup findings that don't apply to a brain Kurooto runs for you (ids, or the start of one)
        "checkup_ignore": [
            "backup_",
            "mcp_",
            "chronicle",
            "auto_chronicle",
            "uninstalled_",
            "publish_skills_off",
            "writeback_consent",
            "version_drift",
            "embeddings_disabled",
            "schema_pack",
            "host",
        ],
    },
)
MODELS = {"ollama": "ollama:nomic-embed-text", "gemini": "google:gemini-embedding-2"}
# The upkeep's steps (GBrain's own phase names). Left out on purpose: lint and the repair steps (they rewrite note
# files), sync (Kurooto's own import does that), and the steps that call an AI model (consolidate, takes, synthesis,
# contradictions), which could run on a paid key and once ran a laptop's CPU at full heat for an hour.
UPKEEP_STEPS = ("backlinks", "extract", "extract_facts", "embed", "orphans")
# GBrain's phases (v0.60) you may add to gbrain.upkeep_steps. purge is never run: it deletes pages for good.
PHASES = (
    "lint", "backlinks", "sync", "fence_repair", "content_repair", "unindexed_files", "synthesize", "extract",
    "extract_facts", "extract_atoms", "resolve_symbol_edges", "patterns", "synthesize_concepts",
    "recompute_emotional_weight", "consolidate", "propose_takes", "grade_takes", "calibration_profile",
    "edge_contradictions", "drift", "standing_questions", "chronicle", "facts_drain", "conversation_facts_backfill",
    "enrich_thin", "skillopt", "embed", "orphans", "schema-suggest",
)  # fmt: skip
# what Kurooto runs on a brain it doesn't own: reading it, adding pages, keeping a source in step, the nightly steps
EXTERNAL_OK = {"query", "search", "timeline", "extract", "dream", "advisor", "import", "sync", "embed", "--version"}
ONLINE = ("sync", "embed", "query", "embeddings", "dream")  # steps that may reach its AI models (core/egress.py)
BUSY = 75  # the exit code run() gives when the brain is busy (another step holds it)
MIGRATIONS = ("pending_migration", "apply_migrations", "migration")


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
        self._threads: dict[str, threading.Thread] = {}
        self.busy = False  # the last search found the brain busy

    # ------------------------------------------------------------------------------------- plumbing
    def external(self) -> bool:
        """Your own GBrain (gbrain.managed = false), not one Kurooto runs."""
        return self.setting("managed") is False

    def brain_home(self) -> Path | None:
        """The brain's GBRAIN_HOME: Kurooto's own folder, or yours (None: GBrain's default)."""
        if not self.external():
            return self.home
        h = str(self.setting("home") or "").strip()
        return Path(os.path.expanduser(h)) if h else None

    def exe(self) -> str | None:
        if self.external():
            own = str(self.setting("exe") or "").strip()
            if own:
                p = Path(os.path.expanduser(own))
                return str(p) if p.is_file() else None
            return proc.which("gbrain")
        return self.prereqs.items["gbrain"].find()

    def env(self) -> dict:
        env = {**os.environ, "GBRAIN_NO_AUTOPILOT_INSTALL": "1"}
        env["GBRAIN_SELF_UPGRADE_MODE"] = "off"  # Kurooto pins GBrain's version: no update checks, no upgrade notes
        if self.external():  # your brain's own settings; only its folder and program are Kurooto's to say
            home = self.brain_home()
            if home is not None:
                env["GBRAIN_HOME"] = str(home)
            exe = self.exe()
            if exe:  # its folders first (Bun's bin, where gbrain lives with bun)
                env["PATH"] = os.pathsep.join([*map(str, link_dirs(exe)), env.get("PATH", "")])
            return env
        env["GBRAIN_HOME"] = str(self.home)
        bun_bin = str(Path.home() / ".bun" / "bin")
        env["PATH"] = bun_bin + os.pathsep + env.get("PATH", "")
        key = self.app.secrets.get("gemini.api_key")
        if key and self.embeddings() == "gemini":
            env["GOOGLE_GENERATIVE_AI_API_KEY"] = key
        return env

    def run(self, *args: str, timeout: float = 600, wait: float = -1) -> proc.Result:
        """Run gbrain. `wait`: how long to wait for the brain if another step is using it (-1: as long as it takes);
        if it's still busy after that, the result has code BUSY. On your own brain, only what Kurooto may do there
        runs (EXTERNAL_OK): never init, migrations or config changes."""
        exe = self.exe()
        if not exe:
            return proc.Result(1, "", "GBrain isn't installed" if not self.external() else "can't find your gbrain")
        if self.external() and (not args or args[0] not in EXTERNAL_OK):
            return proc.Result(
                1, "", f"Kurooto doesn't run `gbrain {args[0] if args else ''}` on a brain it doesn't own"
            )
        home = self.brain_home()
        if args and args[0] in ONLINE and (self.external() or self.embeddings() == "gemini"):
            egress.handed("GBrain", "Notes brain")  # its index is made with Gemini (or your own brain's models)
        try:
            with Lock(self.app.paths.state, "gbrain", timeout=wait):  # its database allows one writer at a time
                return proc.run(
                    [exe, *args], timeout=timeout, env=self.env(), cwd=home if home and home.exists() else None
                )
        except Timeout:
            return proc.Result(BUSY, "", "the notes brain is busy (its nightly upkeep, or a sync)")

    def embeddings(self) -> str:
        choice = self.setting("embeddings") or "auto"
        if choice != "auto":
            return choice
        hw = jload(self.app.paths.state / "hardware.json", {}) or {}
        if (hw.get("recommendation") or {}).get("embeddings") == "ollama":
            return "ollama"
        return "gemini" if self.app.secrets.get("gemini.api_key") else "off"

    def initialised(self) -> bool:
        if self.external():
            return bool(self.exe())
        return (jload(self.app.paths.state / "gbrain.json", {}) or {}).get("initialised", False)

    # ---------------------------------------------------------------------------------------- setup
    def ready(self):
        if self.external():
            if not self.exe():
                return False, "can't find your gbrain program (set gbrain.exe, or put gbrain on your PATH)"
            home = self.brain_home()
            if home is not None and not home.is_dir():
                return False, f"your brain's folder isn't there: {home} (gbrain.home)"
            return True, ""
        if not self.exe():
            return False, "needs setting up (installs Bun and GBrain, about 0.5 GB)"
        if not self.initialised():
            return False, "needs setting up (creates your notes brain)"
        return True, ""

    def setup(self, progress=print) -> tuple[bool, str]:
        """Install what it needs, create the brain, choose the index type, and import your notes once. Your own
        brain is only checked: Kurooto searches it once to see it answers."""
        if self.external():
            ok, why = self.ready()
            if not ok:
                return False, why[:1].upper() + why[1:] + "."
            progress("Checking your brain answers…")
            r = self.run("search", "kurooto", timeout=300)
            if not r.ok:
                return False, f"Your gbrain didn't answer: {(r.err or r.out).strip()[-300:] or f'exit {r.code}'}"
            jsave(self.app.paths.state / "gbrain.json", {"initialised": True, "external": True, "embeddings": "own"})
            src = self.setting("source")
            return True, "Kurooto uses your own brain now" + (
                f"; it keeps the source {src} in step with your notes." if src else "."
            )
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
        if self.external():
            return self.sync_source(payload)
        args = ["import", str(self.app.workspace)]
        if (jload(self.app.paths.state / "gbrain.json", {}) or {}).get("embeddings", "off") == "off":
            args.append("--no-embed")
        r = self.run(*args, timeout=1800, wait=(payload or {}).get("wait", -1))
        if r.code == BUSY:
            return False, r.err
        out = (r.out or "").strip().splitlines()
        summary = next((ln.strip() for ln in out if "imported" in ln), "")
        self.app.events.emit("gbrain_sync", ok=r.ok)
        return r.ok, summary or (r.err[-200:] if not r.ok else "")

    def sync_source(self, payload: dict | None = None) -> tuple[bool, str]:
        """Your own brain: bring the source that is your notes folder up to date (gbrain.source), then embed what
        changed, with the brain's own settings. Nothing when no source is named."""
        src = str(self.setting("source") or "").strip()
        if not src:
            return True, "your brain keeps itself in step (no gbrain.source)"
        wait = (payload or {}).get("wait", -1)
        r = self.run("sync", "--source", src, "--no-hard-deadline", timeout=1800, wait=wait)
        if r.code == BUSY:
            return False, r.err
        if r.ok:
            self.run("embed", "--stale", "--source", src, timeout=1800, wait=wait)
        out = (r.out or "").strip().splitlines()
        summary = next((ln.strip() for ln in out if "imported" in ln.lower()), "")
        self.app.events.emit("gbrain_sync", ok=r.ok, external=True)
        return r.ok, summary or ((r.err or r.out)[-200:] if not r.ok else "")

    def start(self):
        # in a worker thread, so the rest of Kurooto keeps running; a sync that finds the brain busy waits for next time
        self.every("sync", self.setting("sync") or "every 15m", lambda p: asyncio.to_thread(self.sync, {"wait": 0}))
        self.every("nightly", self.setting("nightly") or "daily 03:00", lambda p: self._spawn("nightly", self.nightly))
        self.every(
            "checkup",
            self.setting("checkup_when") or "weekly sun 19:30",
            lambda p: self._spawn("checkup", self.checkup),
        )

    def _spawn(self, name: str, fn) -> bool:
        """Run long work in the background (the upkeep can take most of an hour), once at a time."""
        t = self._threads.get(name)
        if t is not None and t.is_alive():
            return False
        self._threads[name] = threading.Thread(target=fn, name=f"gbrain-{name}", daemon=True)
        self._threads[name].start()
        return True

    # ------------------------------------------------------------------------------------ the nightly work
    def nightly(self) -> dict:
        """Timelines, then the upkeep, each only if it's on. The upkeep's own steps include the timelines."""
        if not self.initialised() or not self.exe():
            return {}
        out = {}
        if self.setting("upkeep"):
            out["upkeep"] = self.upkeep()
        elif self.setting("timelines"):
            out["timelines"] = self.timelines()
        return out

    def timelines(self) -> tuple[bool, int]:
        """Turn dated log lines ("- **YYYY-MM-DD** | source — summary") into timeline entries. No AI involved."""
        r = self.run("extract", "timeline", "--source", "db", timeout=1800)
        m = re.search(r"Timeline:\D*?(\d+)\s+entries", r.out or "")
        n = int(m[1]) if m else 0
        self.app.events.emit("gbrain_timelines", ok=r.ok, entries=n)
        return r.ok, n

    def upkeep_steps(self) -> list[str]:
        """The upkeep's steps: gbrain.upkeep_steps (GBrain's phase names, unknown ones and purge left out), else the
        light ones."""
        chosen = [str(x).strip() for x in self.setting("upkeep_steps") or [] if str(x).strip() in PHASES]
        return list(dict.fromkeys(chosen)) or list(UPKEEP_STEPS)

    def upkeep(self) -> tuple[bool, str]:
        """GBrain's nightly maintenance (its "dream" cycle) with the steps in upkeep_steps (the light ones unless
        you choose). Your own brain runs over its own sources; Kurooto's over your notes folder."""
        args = ["dream", "--json"] if self.external() else ["dream", "--json", "--dir", str(self.app.workspace)]
        for step in self.upkeep_steps():
            args += ["--phase", step]
        started = now()
        r = self.run(*args, timeout=3600)
        logs = self.app.paths.state / "gbrain"
        logs.mkdir(parents=True, exist_ok=True)
        log = logs / f"upkeep-{started:%Y-%m-%d}.log"
        log.write_text(((r.out or "") + "\n" + (r.err or ""))[-200_000:], encoding="utf-8")
        for old in sorted(logs.glob("upkeep-*.log"))[:-14]:  # keep two weeks of its own logs
            old.unlink(missing_ok=True)
        report = _json(r.out) or {}
        steps = [p for p in report.get("phases") or [] if isinstance(p, dict)]
        failed = [str(p.get("phase")) for p in steps if p.get("status") == "fail"]
        status = str(report.get("status") or ("ok" if r.ok else "failed"))
        ok = r.ok and status != "failed" and not failed
        secs = round((now() - started).total_seconds())
        self.app.events.emit("gbrain_upkeep", ok=ok, status=status, failed=failed, seconds=secs)
        state = jload(self.app.paths.state / "gbrain.json", {}) or {}
        if ok:
            state.pop("upkeep_told", None)
        elif not state.get("upkeep_told"):  # once, until it works again
            state["upkeep_told"] = True
            which = f" (steps: {', '.join(failed)})" if failed else ""
            self.app.notify(
                f"The notes brain's nightly upkeep didn't finish{which}. Search still works, and it tries again "
                f"tomorrow night. Details: {log}",
                kind="info",
                why="gbrain.upkeep",
            )
        jsave(self.app.paths.state / "gbrain.json", state)
        return ok, status

    def checkup(self) -> list[dict]:
        """GBrain's advisor; a message (once a week at most) only if something is a warning or worse."""
        if not self.initialised() or not self.exe() or not self.setting("checkup"):
            return []
        r = self.run("advisor", "--json", timeout=600)  # exit 1 / 2 mean warnings / critical: the report is still there
        report = _json(r.out)
        ignore = [str(x) for x in self.setting("checkup_ignore") or []]
        if report is not None:
            found = [
                {"id": str(f.get("id")), "severity": f.get("severity"), "title": str(f.get("title") or f.get("id"))}
                for f in report.get("findings") or []
                if isinstance(f, dict)
                and f.get("severity") in ("warn", "critical")
                and not f.get("workspace_dependent")
                and not any(str(f.get("id")).startswith(x) for x in ignore)
            ]
        else:  # an older GBrain without --json: its text report marks them [WARN] / [CRIT]
            found = [
                {"id": ln.strip()[:80], "severity": "warn", "title": ln.strip()[:200]}
                for ln in (r.out or "").splitlines()
                if re.match(r"^\s*\[(WARN|CRIT|ERROR)", ln)
            ]
        self.app.events.emit("gbrain_checkup", ok=report is not None or r.ok, items=len(found))
        if found:
            ref = uuid.uuid4().hex[:8]
            jsave(self.app.paths.state / "gbrain-checkup.json", {ref: [f["id"] for f in found]})
            lines = [f"- {f['title']}" + (" (serious)" if f["severity"] == "critical" else "") for f in found[:8]]
            buttons = [("Ignore these", f"gbrain:{ref}:ignore")]
            if any(f["id"] in MIGRATIONS for f in found) and not self.external():
                buttons.insert(0, ("Update the brain", f"gbrain:{ref}:migrate"))
            self.app.notify(
                f"Notes brain checkup: {len(found)} thing(s) need a look.\n" + "\n".join(lines),
                kind="info",
                title="Notes brain checkup",
                buttons=[buttons],
                why="gbrain.checkup",
            )
        return found

    def callbacks(self):
        return {"gbrain": self._button}

    def _button(self, ref: str, act: str) -> str:
        ids = (jload(self.app.paths.state / "gbrain-checkup.json", {}) or {}).get(ref)
        if ids is None:
            return "That checkup is old; the next one comes on Sunday."
        if act == "ignore":
            have = list(self.setting("checkup_ignore") or [])
            self.app.settings.set("gbrain.checkup_ignore", have + [i for i in ids if i not in have])
            return "OK, the checkup won't mention those again."
        if act == "migrate":
            if self.external():
                return "Kurooto doesn't change a brain it doesn't own: run `gbrain apply-migrations` yourself."
            r = self.run("apply-migrations", "--yes", "--no-autopilot-install", timeout=1800, wait=0)
            if r.code == BUSY:
                return "The brain is busy right now; try again in a while."
            return "Updated." if r.ok else "That didn't work: " + (r.err or r.out)[-150:]
        return "ok"

    # ------------------------------------------------------------------------------------- using it
    def search(self, question: str, n: int = 5) -> str:
        r = self.run("query", question, timeout=120, wait=60)
        if not r.ok and r.code != BUSY:
            r = self.run("search", question, timeout=120, wait=60)
        self.busy = r.code == BUSY
        return (r.out or "").strip() if r.ok else ""  # "": callers fall back to a keyword search

    def timeline(self, note: str, since: str = "") -> str:
        """A note's timeline: its dated log lines, oldest first (from the last nightly run)."""
        slug = gbrain_slug(note)
        if not slug:
            return "Which note? e.g. /timeline research/reading-group"
        args = ["timeline", slug]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", since or ""):
            args += ["--after", since]
        r = self.run(*args, timeout=120, wait=30)
        out = (r.out or "").strip()
        if r.code == BUSY:
            return "The notes brain is busy with its upkeep; try again in a while."
        if not r.ok or not out or out.startswith("No timeline entries"):
            return (
                f'No dated entries for {slug} yet. Lines like "- **{now():%Y-%m-%d}** | source — what '
                'happened" in a note become its timeline overnight.'
            )
        return re.sub(r"(?m)^(\d{4}-\d{2}-\d{2})T00:00:00(?:\.000)?Z", r"\1", out)  # dates only

    def commands(self):
        return [
            Command("notes", "search your notes by meaning: /notes what is a compact space", self._notes),
            Command("timeline", "a note's dated log: /timeline research/reading-group", self._timeline),
        ]

    def _timeline(self, msg: Incoming, arg: str) -> str:
        return clip(self.timeline(arg), 3500)

    def agent_tools(self):
        return [
            Tool(
                "note_timeline",
                "The dated entries of one note (its '- **YYYY-MM-DD** | ...' log lines), oldest first. Good for "
                "'when did I last ...?' once you know which note; slug like research/reading-group.",
                lambda a: clip(self.timeline(str(a.get("slug", "")), str(a.get("since") or "")), 6000),
                {"slug": arg(), "since": arg("only entries on or after YYYY-MM-DD (optional)")},
                ("slug",),
            )
        ]

    def _notes(self, msg: Incoming, arg: str) -> str:
        if not arg:
            return "Usage: /notes <what you're looking for>"
        out = self.search(arg)
        if not out and self.busy:
            return "The notes brain is busy with its upkeep; try again in a while."
        return out[:3500] if out else "Nothing in your notes about that."


def link_dirs(exe: str) -> list[Path]:
    """The folders a program's links pass through (~/.local/bin/gbrain -> <bun>/bin/gbrain -> ...), nearest first:
    where bun is, next to the gbrain it installed."""
    p, out = Path(exe), []
    for _ in range(8):
        out.append(p.parent)
        if not p.is_symlink():
            break
        p = p.parent / os.readlink(p)
    return list(dict.fromkeys(out))


def serve_command(exe: str) -> list[str]:
    """How to start GBrain's MCP server from another program (agy): through the bun next to it, when there is one,
    so it doesn't depend on that program's PATH."""
    for d in link_dirs(exe):
        for name in ("bun", "bun.exe"):
            if (d / name).is_file():
                return [str(d / name), exe, "serve"]
    return [exe, "serve"]


def gbrain_slug(note: str) -> str:
    """The name GBrain gives a note: its path without .md, each part lowercased, accents and odd characters dropped,
    spaces as hyphens ("Research/Reading Group.md" -> "research/reading-group")."""
    parts = []
    for seg in str(note or "").strip().replace("\\", "/").removesuffix(".md").strip("/").split("/"):
        seg = "".join(c for c in unicodedata.normalize("NFD", seg) if not unicodedata.combining(c))
        seg = re.sub(r"[^\w.\s-]", "", unicodedata.normalize("NFC", seg).lower())
        seg = re.sub(r"-+", "-", re.sub(r"\s+", "-", seg)).strip("-")
        if seg and seg not in (".", ".."):
            parts.append(seg)
    return "/".join(parts)


def _json(text: str) -> dict | None:
    """The JSON document in a command's output (it may print lines before it)."""
    text = text or ""
    if "{" not in text:
        return None
    try:
        out = json.loads(text[text.index("{") : text.rindex("}") + 1])
    except ValueError:
        return None
    return out if isinstance(out, dict) else None
