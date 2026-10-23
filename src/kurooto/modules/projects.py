"""Help with your project: the AI works on a project of yours (a thesis in LaTeX, code, a report) in a scratch folder
of its own, and what it did comes back as a proposal you apply, change or discard (core/scratch.py, core/proposals.py).

    /project                         your projects, and which ones the AI may help with
    /project help on|off <name>      let the AI help with that project (off for every project until you say so)
    /project help <name> <what>      "/project help thesis add footnotes to chapter 2 citing refs.bib"
    /project checks <name> <command> run that (its tests, a LaTeX build) in the scratch folder after the AI's changes,
                                     with a time limit and no network; /project checks <name> off; /project checks
                                     <name> shows it and what Kurooto would suggest
    /project add <folder> [as <name>]   a folder of yours as a project (a typed command only: core/tap.py repo.attach)
Plain words work too: "in my thesis add footnotes to chapter 2 citing refs.bib", "help with my thesis: fix the
failing test". The dashboard's Proposals page has the same.

Where projects come from (sources(), easy to extend: SOURCES): Research's repositories (/repos, research.repos and
research.projects), the LaTeX documents you attached (/latex add, the Research add-on), and projects.folders (Settings
or /project add). A git repository gets a worktree on a new branch, and Apply makes one commit on your current branch;
any other folder gets a mirror, and Apply writes the files with Undo.

One request at a time per project. The AI's write access for the request is its scratch folder only; nothing outside
it is written, nothing is pushed or sent, and checks run only where a sandbox keeps them inside it with no network.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

from kurooto import providers
from kurooto.core import proposals, scratch
from kurooto.core.config import register_defaults
from kurooto.modules.base import Command, Incoming, Intent, Module

register_defaults(
    "projects",
    {
        "folders": {},  # project name -> folder, for projects that aren't Research's repositories (/project add)
        "help": [],  # the projects the AI may help with (/project help on <name>); none until you say so
        "checks": {},  # project name -> the command that checks it (its tests, a LaTeX build); none until you set one
        "check_timeout_s": 300,  # a check is stopped after this many seconds
        "effort": "high",  # how hard the AI thinks about project work (low, medium, high, auto)
    },
)

NAME = r"(?P<name>[\w .'’-]{1,40}?)"
# "help with my thesis: fix the failing test", "in my thesis project, add ...": a project, whatever its name
ASK_SAID = re.compile(
    r"(?i)^(?:please\s+)?(?:help\s+(?:me\s+)?with\s+(?:my|the)\s+" + NAME + r"(?:\s+(?:project|repo|repository))?"
    r"\s*:|(?:in|for|on)\s+(?:my|the)\s+" + NAME.replace("name", "name2") + r"\s+(?:project|repo|repository)\s*[:,]?)"
    r"\s*(?P<what>\S.{3,})$"
)
# "in my thesis add footnotes to chapter 2 citing refs.bib": only when "thesis" is one of your projects
ASK_PLAIN = re.compile(r"(?i)^(?:please\s+)?(?:in|for|on)\s+(?:my|the)\s+" + NAME + r"\s*[:,]?\s+(?P<what>\S.{3,})$")


def research_repos(app) -> dict[str, Path]:
    out: dict[str, Path] = {}
    mapping = app.settings.get("research.projects") or {}
    for repo in app.settings.get("research.repos") or []:
        p = Path(str(repo)).expanduser()
        name = next((str(v) for k, v in mapping.items() if v and Path(str(k)).expanduser() == p), p.name)
        out.setdefault(name, p)
    return out


def latex_documents(app) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for r in app.settings.get("research_addon.latex_repos") or []:
        if isinstance(r, dict) and r.get("path"):
            p = Path(str(r["path"])).expanduser()
            out.setdefault(p.name, p)
    return out


def own_folders(app) -> dict[str, Path]:
    return {str(k): Path(str(v)).expanduser() for k, v in (app.settings.get("projects.folders") or {}).items() if v}


# where projects come from: each fn(app) -> {name: folder}. A project made from a GitHub repository (another feature)
# adds its own source here; the first source that names a project wins
SOURCES: list[Callable] = [own_folders, research_repos, latex_documents]


def sources(app) -> dict[str, Path]:
    """Every project Kurooto knows: name -> its folder (absolute)."""
    out: dict[str, Path] = {}
    for fn in SOURCES:
        try:
            for name, folder in fn(app).items():
                out.setdefault(str(name), Path(os.path.abspath(folder)))
        except Exception as e:  # one source's mistake never hides the others
            app.events.emit("projects_source_failed", error=f"{type(e).__name__}: {e}"[:200])
    return out


def suggest_checks(folder: Path) -> str:
    """A check command that fits what's in the folder (shown, never set by itself)."""
    if any(folder.glob("*.tex")):
        main = next((p.name for p in sorted(folder.glob("*.tex")) if "\\documentclass" in _head(p)), "")
        return f"latexmk -pdf -interaction=nonstopmode -halt-on-error {main}".strip() if main else ""
    if (folder / "pyproject.toml").exists() or (folder / "pytest.ini").exists() or (folder / "tests").is_dir():
        return "python -m pytest -q"
    if (folder / "package.json").exists():
        return "npm test"
    if (folder / "Cargo.toml").exists():
        return "cargo test --offline"
    if (folder / "Makefile").exists():
        return "make test"
    return ""


def _head(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return ""


class Projects(Module):
    id = "projects"
    title = "Help with your project"
    description = (
        "The AI works on a project of yours (a thesis, code, a report) in a scratch folder of its own; what it did "
        "comes back as a proposal with the diff, which you apply, change or discard."
    )
    privacy = (
        "The files the AI needs from that project go to the AI you picked, as any request does. It writes only in a "
        "scratch folder on this computer; nothing is pushed or sent."
    )

    def ready(self):
        main = self.app.settings.get("brain.main")
        if not main:
            return False, "pick an AI brain first"
        b = providers.build(self.app, main)
        ok, why = b.available() if b else (False, "unknown brain")
        return (True, "") if ok else (False, f"{providers.CHOICES.get(main, main)}: {why}")

    # ------------------------------------------------------------------------------------------ projects
    def known(self) -> dict[str, Path]:
        return sources(self.app)

    def find(self, name: str) -> tuple[str, Path] | None:
        want = str(name or "").strip().strip("\"'").lower()
        if not want:
            return None
        known = self.known()
        for k, v in known.items():
            if k.lower() == want:
                return k, v
        hits = [(k, v) for k, v in known.items() if k.lower().startswith(want) or want in k.lower().split()]
        return hits[0] if len(hits) == 1 else None

    def helps(self, name: str) -> bool:
        return name.lower() in [str(x).lower() for x in self.setting("help") or []]

    def checks_of(self, name: str) -> str:
        cmds = self.setting("checks") or {}
        return str(next((v for k, v in cmds.items() if k.lower() == name.lower()), "") or "")

    # -------------------------------------------------------------------------------------------- asking
    def start_help(self, name: str, what: str, msg: Incoming | None = None) -> str:
        """The AI's request for this project, in a scratch folder: a proposal comes back."""
        hit = self.find(name)
        if hit is None:
            return f'No project "{name}". /project lists them.'
        name, folder = hit
        if not self.helps(name):
            return (
                f"The AI doesn't help with {name} yet: /project help on {name} lets it (it works in a scratch folder)."
            )
        if not folder.is_dir():
            return f"{name}'s folder isn't there: {folder}."
        what = str(what or "").strip()
        if len(what) < 4:
            return f"What should it do in {name}? /project help {name} <what to do>"
        busy = scratch.busy(self.app, folder)
        if busy:
            return f"The AI is already working on {name} ({busy}); one request at a time. /jobs shows it."
        try:
            sc = scratch.create(self.app, folder, name, project=name, checks=self.checks_of(name))
        except Exception as e:
            return f"Couldn't make a scratch folder for {name}: {e}"[:300]
        kind = "a git repository" if sc.kind == "git" else "a folder"
        prompt = f'Help with their project "{name}" (its folder: {folder}; {kind}).\nTheir request: {what}'
        terminal = msg is not None and msg.via in ("terminal", "setup")
        reply_to = None if msg is None or terminal else msg.message_id
        jid = proposals.submit(self.app, sc, prompt, f"{name}: {what}"[:80], reply_to=reply_to, source="project",
                               request=what, effort=str(self.setting("effort") or "high"))  # fmt: skip
        if msg is not None:
            msg.job = jid
        where = "a worktree on its own branch" if sc.kind == "git" else "a scratch copy"
        return f"On it, in {where} of {name}: the change comes as a proposal to Apply, Change or Discard."

    # ------------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command(
                "project",
                "help with a project in a scratch folder: /project help <name> <what to do>; /project help on|off "
                "<name>; /project checks <name> <command>|off; /project add <folder> [as <name>]; /project lists them",
                self._cmd,
            )
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str | None:
        words = arg.strip()
        m = re.fullmatch(r"(?is)help\s+(on|off)\s+(.+)", words)
        if m:
            return self.switch(m[2], m[1].lower() == "on")
        m = re.fullmatch(r"(?is)help\s+(\S+)\s+(.+)", words)
        if m:
            name, what = m[1], m[2]
            hit = self.find(name)
            if hit is None:  # a two-word project name: "/project help my thesis add ..."
                for k in self.known():
                    if words[5:].strip().lower().startswith(k.lower() + " "):
                        name, what = k, words[5:].strip()[len(k) :].strip()
                        break
            return self.start_help(name, what, msg)
        m = re.fullmatch(r"(?is)checks\s+(.+?)(?:\s+(off|.+))?", words)
        if m:
            return self.set_checks(m[1], m[2])
        m = re.fullmatch(r"(?is)add\s+(.+?)(?:\s+as\s+(.+))?", words)
        if m:
            return self.add(m[1].strip().strip('"'), (m[2] or "").strip().strip('"'))
        if words and words.lower() not in ("list", "ls"):
            return "Usage: /project help <name> <what to do>, /project help on|off <name>, /project checks <name> ..."
        return self.listing()

    def listing(self) -> str:
        known = self.known()
        if not known:
            return (
                "No projects yet: /project add <folder> [as <name>], or Research's /repos add <folder>. Then /project "
                "help on <name>."
            )
        lines = ["Your projects (the AI helps only where it says so):"]
        for name, folder in sorted(known.items()):
            on = "helps" if self.helps(name) else "off"
            ck = self.checks_of(name)
            lines.append(f"- {name}: {folder} · {on}" + (f" · checks: {ck}" if ck else ""))
        lines.append("/project help on <name>, then /project help <name> <what to do>.")
        return "\n".join(lines)

    def switch(self, name: str, on: bool) -> str:
        hit = self.find(name)
        if hit is None:
            return f'No project "{name.strip()}". /project lists them.'
        name = hit[0]
        cur = [x for x in self.setting("help") or [] if str(x).lower() != name.lower()]
        self.app.settings.set("projects.help", [*cur, name] if on else cur)
        if on:
            return (
                f"The AI may help with {name} now: /project help {name} <what to do>, or just say it. It works in a "
                "scratch folder and you get a proposal; nothing changes before you tap Apply."
            )
        return f"The AI won't help with {name} any more."

    def set_checks(self, name: str, cmd: str | None) -> str:
        hit = self.find(name)
        if hit is None:
            return f'No project "{name.strip()}". /project lists them.'
        name, folder = hit
        cmds = {k: v for k, v in (self.setting("checks") or {}).items() if k.lower() != name.lower()}
        if not cmd:
            have = self.checks_of(name)
            tip = suggest_checks(folder)
            return (f"{name}'s checks: {have}." if have else f"{name} has no checks.") + (
                f" For this folder: /project checks {name} {tip}" if tip and tip != have else ""
            )
        if cmd.strip().lower() == "off":
            self.app.settings.set("projects.checks", cmds)
            return f"No checks for {name} any more."
        self.app.settings.set("projects.checks", {**cmds, name: cmd.strip()})
        box = scratch.sandbox(folder, []) is not None
        return (
            f"After the AI's changes to {name}, Kurooto runs `{cmd.strip()}` in the scratch folder "
            f"({int(self.setting('check_timeout_s') or 300)} s at most, no network) and the proposal says how it went."
            + ("" if box else " This computer has no sandbox for them (bubblewrap on Linux), so they won't run here.")
        )

    def add(self, folder: str, name: str) -> str:
        p = Path(folder).expanduser()
        if not p.is_absolute() or not p.is_dir():
            return "Give the whole path of a folder that exists: /project add /home/you/thesis [as thesis]."
        name = name or p.name
        cur = dict(self.setting("folders") or {})
        cur[name] = str(p)
        self.app.settings.set("projects.folders", cur)
        return f"{name} is a project now ({p}). /project help on {name} lets the AI help with it."

    # -------------------------------------------------------------------------------------------- intents
    def intents(self):
        return [
            Intent(
                "project_help",
                "help with one of your projects, as a proposal",
                self._match,
                lambda msg, slots: self.start_help(slots["name"], slots["what"], msg),
                examples=(
                    "help with my thesis: add footnotes to chapter 2 citing refs.bib",
                    "in my thesis project, write the README's install section",
                ),
            )
        ]

    def _match(self, text: str) -> dict | None:
        """A project request: said as one ("help with my thesis: ..."), or "in my <project> ..." naming one of yours.
        Which project and whether the AI may help is start_help's to say."""
        text = str(text or "").strip()
        m = ASK_SAID.match(text)
        if m:
            return {"name": (m["name"] or m["name2"] or "").strip(), "what": m["what"].strip()}
        m = ASK_PLAIN.match(text)
        if m and self.find(m["name"]) is not None:
            return {"name": m["name"].strip(), "what": m["what"].strip()}
        return None
