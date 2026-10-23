"""Skills: ready-made instructions for the AI, each run with one command: /journal, /study-log, /add-to-notes,
/assignment, /connect-notes, /term-setup, /goodnight, /morning, /morning-prep, and /pack for a revision PDF.

Make your own: /newskill <what it should do> has the AI write one; you see it in full and tap Save (or Discard).
Run any skill or request on a schedule: /every monday 9:00 /journal plan my week; /routines lists them.
The evening before a quiz or exam (from Deadlines), a revision pack for it: offered with a button, or built by itself
(skills.auto_pack: ask | auto | off).
Reply to a skill's answer to carry on (answer its questions, ask for changes).

Where skills live:
    shipped     inside Kurooto (data/skills/<name>/SKILL.md); updates bring new versions
    yours       <notes>/kurooto/skills/<name>/SKILL.md; one with a shipped skill's name replaces it for you
    prompts     <notes>/prompts/*.md with `skill: true` (or `skill: <name>`) in its header
(those are the default notes layout's folders; core/layout.py says where yours are). A skill's instructions name the
default layout's places (journal/<YYYY-MM-DD>, <subject>/course); they're swapped for your layout's when it runs.

A SKILL.md is Markdown with a short header, then the instructions; $ARGUMENTS becomes what you typed after the
command:
    ---
    name: journal
    description: one line: what it does
    effort: low | medium | high
    args: what to type after /journal
    ---
"""

from __future__ import annotations

import datetime as dt
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import providers
from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "skills",
    {
        "auto_pack": "ask",  # the evening before a quiz or exam: ask (a button) | auto (build it) | off
        "auto_pack_after": "16:00",  # not before this time of day, 12 to 36 hours before it
    },
)

NAME = re.compile(r"[a-z0-9][a-z0-9-]{1,39}")
EFFORTS = ("low", "medium", "high")
TELEGRAM_MAX = 50 * 1024 * 1024  # what a bot may send
MAX_ROUTINES = 30
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SPECIAL = {"inbox", "journal", "kurooto", "research", "about-me", "handwritten", "prompts", "revision-packs", "terms"}

RULES = """How to work (the rules for every skill):
- Their notes are Markdown files in their notes folder. Use Kurooto's notes tools when you have them: search_notes \
and list_notes to find notes, read_note to read one, write_note to create a note, add_to_note to add to one (at the \
end, or under a "## section"), tick_task to tick a "- [ ]" task. Without those tools, read and edit the Markdown \
files directly, by the same rules. Use the other tools you have for actions (reminders, the alarm, deadlines, \
check-ins); if a step needs a tool you don't have, skip it and say so in one line.
- Don't run shell commands, and don't write scripts or programs.
- Never delete, reorder or reword what they wrote: only create notes or add to them. Their own words go in verbatim.
- Every link you add carries a short reason: "- [[linear-algebra/course]]: where this lecture belongs". Links are \
note paths inside the notes folder, without ".md". Never link a note that doesn't exist.
- Keep health and medical details, money, passwords, and other people's private details out of the notes. If what \
they gave you has any, leave those parts out and say what you left out.
- Nothing goes to anyone but them: don't message, mail or share with anyone else, don't spend money, don't delete.
- Your answer reaches them as a chat message: short, plain text, saying what you did and where."""

NEWSKILL = """Write a new skill for Kurooto, their assistant. What they want it to do: {want}

A skill is a Markdown file, SKILL.md, that Kurooto sends to the AI as a request when they type /<name> <words>.
Reply with ONLY the file, in exactly this form:

---
name: <lowercase-with-hyphens, 2 to 40 characters; not one of: {taken}>
description: <one line: what it does, for the list of skills>
effort: <low | medium | high: how hard the AI should think>
args: <a short hint of what to type after the command, or nothing>
---
<the instructions, written to the AI that will run them: numbered steps, which notes to read and where to write
(their notes folder uses inbox/, journal/<YYYY-MM-DD> for the daily note, a folder per subject with course and
exam-prep notes, research/, about-me/), and what to reply. $ARGUMENTS is replaced by the words they type after the
command.>

The instructions may use these tools: {tools}. They must not run shell commands or programs, delete or reword
anything they wrote, send anything to anyone else, or put health, money or other people's private details in notes.
Keep it under 60 lines. Don't create or change any files yourself; only reply with the file."""

FIX_LATEX = """This LaTeX document failed to compile with Tectonic. The errors:
{errors}

Reply with the whole corrected document in one ```latex block (from \\documentclass to \\end{{document}}), using
standard packages only, and nothing else.

```latex
{tex}
```"""


# ------------------------------------------------------------------------------------------- the files
@dataclass
class Skill:
    name: str
    description: str
    body: str
    effort: str = "auto"  # low | medium | high | auto
    args: str = ""  # a hint of what to type after the command
    source: str = "shipped"  # shipped | yours | prompt
    path: str = ""
    internal: bool = False  # used by a feature, never typed: hidden from /skills and /<name>
    output: str = ""  # "latex": the answer is a LaTeX document, saved and compiled to a PDF


def parse(text: str) -> tuple[dict, str]:
    """A Markdown file's `---` header (simple `key: value` lines) and the text after it."""
    text = text.lstrip("﻿").replace("\r\n", "\n")
    m = re.match(r"---\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m[1].split("\n"):
        k, sep, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if not sep or not re.fullmatch(r"[a-z_][\w-]*", k):
            continue
        if len(v) >= 2 and v[0] == v[-1] == "'":
            v = v[1:-1].replace("''", "'")
        elif len(v) >= 2 and v[0] == v[-1] == '"':
            v = v[1:-1].replace('\\"', '"')
        meta[k] = v
    return meta, m[2]


def truthy(v) -> bool:
    return str(v or "").strip().lower() in ("true", "yes", "on", "1")


def make(text: str, name: str, source: str, path: str = "") -> Skill | None:
    """A skill from a SKILL.md's text, or None if it isn't usable (bad name, no instructions)."""
    meta, body = parse(text)
    name = (name or meta.get("name") or "").strip().lower()
    if not NAME.fullmatch(name) or not body.strip():
        return None
    effort = (meta.get("effort") or "").strip().lower()
    return Skill(
        name=name,
        description=(meta.get("description") or meta.get("title") or name).strip(),
        body=body.strip() + "\n",
        effort=effort if effort in EFFORTS else "auto",
        args=(meta.get("args") or "").strip(),
        source=source,
        path=path,
        internal=truthy(meta.get("internal")),
        output=(meta.get("output") or "").strip().lower(),
    )


def user_dir(app: App) -> Path:
    return layout.path(app, "skills")


def prompt_files(root: Path) -> list[Path]:
    """The prompts in a prompt library folder (<notes>/prompts), README aside."""
    if not root.is_dir():
        return []
    return sorted(
        p
        for p in root.rglob("*.md")
        if p.name.lower() != "readme.md" and not any(x.startswith(".") for x in p.relative_to(root).parts)
    )


def prompt_skill(meta: dict, stem: str) -> str | None:
    """A prompt's skill name: `skill: true` (named by `name:` or the file) or `skill: <name>`; None if it isn't one."""
    flag = str(meta.get("skill") or "").strip().lower()
    if not flag or flag in ("false", "no", "off", "0"):
        return None
    return flag if NAME.fullmatch(flag) and flag not in ("true", "yes", "on") else slug(meta.get("name") or stem)


def all_skills(app: App) -> dict[str, Skill]:
    """Every skill by name: shipped ones, then prompts marked as skills, then yours (later ones replace earlier)."""
    out: dict[str, Skill] = {}
    try:
        shipped = resources.files("kurooto.data").joinpath("skills")
        for d in sorted(shipped.iterdir(), key=lambda d: d.name):
            f = d.joinpath("SKILL.md")
            if d.is_dir() and f.is_file():
                s = make(f.read_text(encoding="utf-8"), d.name, "shipped", str(f))
                if s:
                    out[s.name] = s
    except (FileNotFoundError, NotADirectoryError):
        pass
    from kurooto.core import overlay  # your add-ons' skills and prompts (core/overlay.py), when they're on

    for root in overlay.dirs(app, "skills"):
        for d in sorted(root.iterdir()):
            f = d / "SKILL.md"
            if f.is_file() and NAME.fullmatch(d.name):
                s = make(f.read_text(encoding="utf-8", errors="replace"), d.name, "add-on", str(f))
                if s:
                    out[s.name] = s
    for f in [p for root in overlay.dirs(app, "prompts") for p in prompt_files(root)]:
        meta, _ = parse(f.read_text(encoding="utf-8", errors="replace"))
        name = prompt_skill(meta, f.stem)
        s = make(f.read_text(encoding="utf-8", errors="replace"), name, "add-on", str(f)) if name else None
        if s:
            out[s.name] = s
    for f in prompt_files(layout.path(app, "prompts")):
        try:
            meta, _ = parse(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        name = prompt_skill(meta, f.stem)
        if not name:
            continue
        s = make(f.read_text(encoding="utf-8", errors="replace"), name, "prompt", str(f))
        if s:
            out[s.name] = s
    ud = user_dir(app)
    if ud.is_dir():
        for d in sorted(ud.iterdir()):
            f = d / "SKILL.md"
            if f.is_file() and NAME.fullmatch(d.name):
                s = make(f.read_text(encoding="utf-8", errors="replace"), d.name, "yours", str(f))
                if s:
                    out[s.name] = s
    return out


def load_skill(app: App, name: str) -> Skill | None:
    return all_skills(app).get(str(name or "").strip().lower().lstrip("/"))


def slug(text: str, n: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:n].strip("-")


def rel(app: App, f) -> str:
    p = Path(f)
    try:
        return p.resolve().relative_to(app.workspace.resolve()).as_posix()
    except ValueError:
        return str(p)


def build(app: App, s: Skill, args: str = "", files=()) -> str:
    """The request the AI gets: the skill's instructions with the arguments filled in, the files, the rules."""
    args = (args or "").strip()
    body = layout.translate(app, s.body)  # the default layout's places -> yours (core/layout.py)
    if "$ARGUMENTS" in body:
        body = body.replace("$ARGUMENTS", args or "(nothing given)")
    elif args:
        body = body.rstrip() + f"\n\nWhat they gave you: {args}\n"
    if files:
        body = body.rstrip() + "\n\nFiles they sent with it (paths in their notes folder unless given in full): "
        body += ", ".join(rel(app, f) for f in files) + "\n"
    return f"Skill: {s.name} ({s.description})\n\n{body.rstrip()}\n\n{RULES}\n"


def skill_prompt(app: App, name: str, args: str = "", files=()) -> str | None:
    """The full request for a skill (your copy first, then the shipped one); None if there's no such skill. Works
    with the Skills feature off, for features that run a skill themselves."""
    s = load_skill(app, name)
    return build(app, s, args, files) if s else None


# ------------------------------------------------------------------------------------ files to you
def send_file(app: App, path, caption: str = "", inside: list[Path] | None = None, to: str = "") -> tuple[bool, str]:
    """Send a file to your Telegram (up to 50 MB). `inside`: the folders it must be in (for the AI's tool). to="drive",
    or a bigger file with Drive upload on: into your Google Drive instead, and you get the link."""
    try:
        p = Path(os.path.expanduser(str(path))).resolve(strict=True)
    except (OSError, RuntimeError):
        return False, f"There's no file {path}."
    if not p.is_file():
        return False, f"{p.name} isn't a file."
    if inside is not None and not any(p.is_relative_to(Path(d).resolve()) for d in inside):
        return False, "I can only send files from the notes folder."
    size = p.stat().st_size
    if size == 0:
        return False, f"{p.name} is empty."
    drive = app.modules.get("drive_upload")  # Google Drive (google_drive.py)
    on = drive is not None and app.is_on("drive_upload")
    if to == "drive" or (size > TELEGRAM_MAX and on and drive.setting("big_files")):
        if not on:
            return False, "Drive upload is off: on this computer, dashboard → Features → Drive upload → Set up."
        return drive.send(p, caption, temporary=to != "drive")  # too big for Telegram: a link that lasts a few days
    if size > TELEGRAM_MAX:
        more = " Turn on Drive upload to get bigger files as a Drive link." if drive is not None else ""
        return False, f"{p.name} is {size / 1024 / 1024:.0f} MB; Telegram takes files up to 50 MB.{more}"
    if "telegram" not in app.notifier.channels:
        return False, "Telegram isn't set up, so there's nowhere to send it."
    focus = app.availability.focus_until()
    ref = app.notify(caption.strip()[:900] or p.name, kind="result", file=str(p), why="asked")
    app.events.emit("file_sent", bytes=size, queued=ref is None and bool(focus))
    if ref is None and focus:
        return True, f"{p.name} comes to your Telegram when focus ends ({focus:%H:%M})."
    if ref is None:
        return False, f"Telegram didn't take {p.name}; try again in a minute."
    return True, f"Sent {p.name} to your Telegram."


def send_files(
    app: App, paths, caption: str = "", inside: list[Path] | None = None, zip_name: str = ""
) -> tuple[bool, str]:
    """Send several files: one or two as they are, more as one zip (so Telegram isn't flooded and nothing is lost
    to its rate limit). Every file must be inside `inside` (when given); the zip is kept under Telegram's limit."""
    import zipfile

    files: list[Path] = []
    for raw in paths:
        try:
            p = Path(os.path.expanduser(str(raw))).resolve(strict=True)
        except (OSError, RuntimeError):
            return False, f"There's no file {raw}."
        if not p.is_file():
            return False, f"{p.name} isn't a file."
        if inside is not None and not any(p.is_relative_to(Path(d).resolve()) for d in inside):
            return False, "I can only send files from the notes folder."
        if p not in files:
            files.append(p)
    if not files:
        return False, "No files to send."
    if len(files) <= 2:
        said = [send_file(app, f, caption if i == 0 else "", inside=inside)[1] for i, f in enumerate(files)]
        return True, " ".join(said)
    total = sum(f.stat().st_size for f in files)
    drive = app.modules.get("drive_upload")
    to_drive = drive is not None and app.is_on("drive_upload") and drive.setting("big_files")
    if total > TELEGRAM_MAX and not to_drive:
        return False, (
            f"Those files are {total / 1024 / 1024:.0f} MB together; Telegram takes up to 50 MB. Send fewer, or "
            "turn on Drive upload to get them as a Drive link."
        )
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", zip_name or "files").strip("-") or "files"
    dest = Path(app.paths.cache) / "send" / (name if name.endswith(".zip") else name + ".zip")
    dest.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as z:
        for f in files:
            arc, n = f.name, 2
            while arc.lower() in seen:
                arc, n = f"{f.stem}-{n}{f.suffix}", n + 1
            seen.add(arc.lower())
            z.write(f, arc)
    ok, msg = send_file(app, dest, caption or f"{len(files)} files")
    return ok, (f"{len(files)} files in one zip: " if ok else "") + msg


# ------------------------------------------------------------------------------------------ routines
WHEN = re.compile(
    r"^\s*(?:every\s+)?(?P<days>day|daily|weekdays?|weekends?|"
    r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*(?:\s*(?:,|and|&)\s*(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*)*)"
    r"\s+(?:at\s+)?(?P<time>\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?)(?=\s|$)\s*(?P<what>.*)\Z",
    re.I | re.S,
)


ASKS = re.compile(
    r"(?:please\s+)?(?:send|remind|tell|give|make|run|do|write|plan|summari[sz]e|check|ask|quiz|show|list|review|"
    r"prepare|draft|build|update|connect|journal|log|read|look|find|pick|suggest|create)\b",
    re.I,
)


LINK = re.compile(r"https?://\S+")
NOT_FILING = re.compile(  # words around a link that ask for something else than filing it
    r"(?:can|could|would|will|please|pls|summari[sz]e|explain|read|translate|open|tell|is|are|what|why|how|do|does|"
    r"compare|reply|answer|send|share|watch|listen)\b",
    re.I,
)


def parse_every(text: str) -> dict:
    """ "monday 9:00 /journal plan my week" -> a routine. Raises ValueError with a usage hint."""
    m = WHEN.match(text or "")
    if not m or not m["what"].strip():
        raise ValueError(
            "Usage: /every monday 9:00 /journal plan my week   (day: daily, weekdays, weekends, a day or "
            "days like mon,thu; then a time; then a /skill or command, or a request for the AI)"
        )
    t = re.fullmatch(r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?", m["time"].strip().lower())
    h, mi, ap = int(t[1]), int(t[2] or 0), t[3]
    if ap == "pm" and h < 12:
        h += 12
    elif ap == "am" and h == 12:
        h = 0
    if h > 23 or mi > 59:
        raise ValueError(f"There's no time {m['time'].strip()}.")
    hm = f"{h:02d}:{mi:02d}"
    d = m["days"].lower()
    if d in ("day", "daily"):
        only, label = None, f"Every day at {hm}"
    elif d.startswith("weekday"):
        only, label = [0, 1, 2, 3, 4], f"Weekdays at {hm}"
    elif d.startswith("weekend"):
        only, label = [5, 6], f"Weekends at {hm}"
    else:
        only = sorted({DAYS.index(x[:3]) for x in re.findall(r"[a-z]+", d) if x[:3] in DAYS})
        label = f"{', '.join(DAYS[i].title() for i in only)} at {hm}"
    spec = f"weekly {DAYS[only[0]]} {hm}" if only and len(only) == 1 else f"daily {hm}"
    return {
        "spec": spec,
        "only": only if only and len(only) > 1 else None,
        "label": label,
        "what": m["what"].strip(),
    }


# --------------------------------------------------------------------------------------------- LaTeX
def extract_latex(text: str) -> str | None:
    """The LaTeX document in an answer (a ```latex block, or a bare \\documentclass ... \\end{document})."""
    t = (text or "").replace("\r\n", "\n")
    for m in re.finditer(r"```(?:latex|tex)?[ \t]*\n(.*?)```", t, re.S | re.I):
        if "\\documentclass" in m[1] and "\\end{document}" in m[1]:
            return m[1].strip() + "\n"
    m = re.search(r"\\documentclass.*?\\end\{document\}", t, re.S)
    return m[0].strip() + "\n" if m else None


def extract_skill(text: str) -> str | None:
    """The SKILL.md in an answer: a fenced block that starts with a header, or the text from the first header."""
    t = (text or "").replace("\r\n", "\n")
    for m in re.finditer(r"```[a-zA-Z]*[ \t]*\n(.*?)```", t, re.S):
        if re.match(r"\s*---\n", m[1]):
            return m[1].strip() + "\n"
    m = re.search(r"^---\n.*?^---[ \t]*$", t, re.S | re.M)
    return t[m.start() :].strip() + "\n" if m else None


def tectonic(app: App) -> str | None:
    """The Tectonic LaTeX engine (an optional prerequisite), if it's installed."""
    from kurooto.core.prereqs import Prereqs

    p = Prereqs(app.paths.app, app.paths.cache).items.get("tectonic")
    return p.find() if p else None


def system_tex(app: App) -> str | None:
    """A LaTeX engine already on this computer (TeX Live, MiKTeX, MacTeX): latexmk, else pdflatex."""
    from kurooto.core import proc

    for name in ("latexmk", "pdflatex"):
        exe = proc.which(name, [])
        if exe:
            return exe
    return None


def pdf_engine(app: App) -> str | None:
    """What makes a PDF from LaTeX here: Tectonic if it's installed, else the computer's own LaTeX."""
    return tectonic(app) or system_tex(app)


def _tex_errors(res) -> str:
    lines = (res.out + "\n" + res.err).splitlines()
    errs = [ln for ln in lines if re.search(r"\berror\b|^!", ln, re.I) and "fontconfig" not in ln.lower()]
    return "\n".join(errs[:12])[:1500] or ("it took too long" if res.code is None else "it failed")


def compile_tex(app: App, tex: Path, timeout: int = 900) -> tuple[bool, str]:
    """Make the PDF next to the .tex: with Tectonic (untrusted mode: no shell escape; the first run downloads the LaTeX
    packages it needs into Kurooto's cache folder, which takes a few minutes), else with the computer's own LaTeX."""
    from kurooto.core import proc

    exe = tectonic(app)
    own = None if exe else system_tex(app)
    if not exe and not own:
        return False, "There's no LaTeX engine (Tectonic isn't installed, and neither is LaTeX)"
    kept = {e for e in (".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk") if tex.with_suffix(e).exists()}
    try:
        if exe:
            env = {**os.environ, "TECTONIC_CACHE_DIR": str(app.paths.cache / "tectonic")}
            res = proc.run(
                [exe, "--untrusted", "--chatter", "minimal", "--outdir", str(tex.parent), str(tex)],
                timeout=timeout,
                env=env,
                cwd=tex.parent,
            )
        elif Path(own).stem.lower() == "latexmk":
            res = proc.run(
                [
                    own,
                    "-pdf",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-silent",
                    f"-outdir={tex.parent}",
                    str(tex),
                ],
                timeout=timeout,
                cwd=tex.parent,
            )
        else:  # twice, for the references and the table of contents
            for _ in range(2):
                res = proc.run(
                    [own, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape",
                     f"-output-directory={tex.parent}", str(tex)],
                    timeout=timeout,
                    cwd=tex.parent,
                )  # fmt: skip
                if not res.ok:
                    break
    except OSError as e:
        return False, str(e)
    finally:
        for e in (".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk"):
            if e not in kept:
                tex.with_suffix(e).unlink(missing_ok=True)  # what the engine leaves beside the PDF
    if res.ok and tex.with_suffix(".pdf").is_file():
        return True, ""
    return False, _tex_errors(res)


# ------------------------------------------------------------------------------------------- module
class Skills(Module):
    id = "skills"
    title = "Skills"
    description = (
        "Ready-made instructions for the AI, one command each (/journal, /study-log, /pack for a revision PDF, ...); "
        "/newskill writes your own, /every runs one on a schedule."
    )
    requires = ("chat",)
    privacy = (
        "What you send with a skill, and the notes it reads, go to the AI you picked. Your own skills and revision "
        "packs are files in your notes folder."
    )

    def __init__(self, app):
        super().__init__(app)
        self.dir = app.paths.state / "skills"
        self.routines_file = app.paths.data / "skills" / "routines.json"
        # registered at once, so an answer that arrives after the feature was turned off isn't lost
        app.jobs.then_actions["skills.done"] = self._done
        app.jobs.then_actions["skills.drafted"] = self._drafted
        app.jobs.then_actions["skills.latex"] = self._latex

    # ----------------------------------------------------------------------------------- lifecycle
    def start(self):
        self.app.scheduler.action("skills.routine", self._routine)
        for r in self.routines():
            self._schedule(r)
        self.every("autopack", "every 30m", self.auto_packs)

    # -------------------------------------------------------------------------------------- running
    def all(self) -> dict[str, Skill]:
        return all_skills(self.app)

    def get(self, name: str) -> Skill | None:
        return load_skill(self.app, name)

    def reserved(self) -> set[str]:
        """Command names a skill can't take (they belong to features)."""
        out = {"start", "help", "jobs"}  # /jobs is Kurooto's own (core/jobs.py)
        for m in self.app.modules.values():
            try:
                out |= {c.name for c in m.commands()}
            except Exception as e:  # one feature's mistake never hides the others' commands
                self.app.events.emit("skills_commands_failed", module=m.id, error=str(e)[:200])
        return out

    def run(
        self,
        name: str,
        args: str = "",
        reply_to=None,
        then: str | None = None,
        then_payload: dict | None = None,
        quiet: bool = False,
        background: bool = False,
        files=None,
        title: str | None = None,
        lane: str | None = None,
    ) -> str:
        """Run a skill as an AI request; returns the job id. Without `then` or `quiet`, the answer comes to you as a
        reply you can answer back (which runs the skill again with your reply). lane="bg": automatic work, which never
        holds up your own requests (core/jobs.py)."""
        s = load_skill(self.app, name)
        if s is None:
            raise KeyError(f"there's no skill called {name}")
        first = (args or "").strip().split("\n")[0][:60]
        title = title or f"/{s.name} {first}".strip()
        payload = dict(then_payload or {})
        if then is None and not quiet:
            quiet = True
            payload = {"name": s.name}
            if s.output == "latex":
                then = "skills.latex"
                tex = layout.file_path(self.app, "latex", f"{now():%Y-%m-%d}-{s.name}.tex")
                payload.update(tex=layout.shown(self.app, tex), label=s.name)
            else:
                then = "skills.done"
        jid = self.app.jobs.submit(
            build(self.app, s, args, files or ()),
            title=title[:80],
            effort=s.effort,
            reply_to=reply_to,
            quiet=quiet,
            then=then,
            then_payload=payload,
            background=background,
            lane=lane,
        )
        self.app.events.emit("skill_run", name=s.name, source=s.source, job=jid)
        return jid

    def typed(self, msg: Incoming, name: str, args: str) -> str | None:
        """/<name> args from you: runs the skill, or None if there's no such skill (the message goes on). "_" works
        for "-" (Telegram's menu can't show "-"): /term_setup runs term-setup."""
        name = name.strip().lower().replace("_", "-")
        if not NAME.fullmatch(name) or name in self.reserved():
            return None
        if name == "revision-pack":
            return self._pack(msg, args)
        s = load_skill(self.app, name)
        if s is None or s.internal:
            return None
        self.run(s.name, args, reply_to=msg.message_id, files=msg.files)
        return "On it."

    def customize(self, name: str) -> Path:
        """Your own copy of a skill (copied from the shipped one the first time), to change it. Returns its path."""
        s = load_skill(self.app, name)
        if s is None:
            raise KeyError(f"there's no skill called {name}")
        f = user_dir(self.app) / s.name / "SKILL.md"
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(Path(s.path).read_text(encoding="utf-8") if s.path else s.body, encoding="utf-8")
            self.app.events.emit("skill_copied", name=s.name, source=s.source)
        return f

    # -------------------------------------------------------------------------------------- answers
    def _deliver(self, job, result, payload: dict, extra: str = "") -> None:
        """Like the usual answer, but tied to the skill: replying to it runs the skill again with your reply."""
        from kurooto.core.jobs import FRIENDLY, LONG, result_path

        label = providers.CHOICES.get(job.brain or "", job.brain or "AI")
        head = f"[{label} · {job.effort or '?'}{'' if result.ok else ' · failed'}] {job.title}"
        body = (result.text if result.ok else FRIENDLY.get(result.verdict, "It failed.").format(brain=label)) + extra
        reply_to = int(job.reply_to) if job.reply_to and job.reply_to.isdigit() else job.reply_to
        tie = {"map_kind": "skill", "map_ref": f"{payload.get('name', '')}|{job.id}"} if result.ok else {}
        if len(body) > LONG:
            md = result_path(self.app, job.id)
            md.write_text(body, encoding="utf-8")
            self.app.notify(
                f"{head}\n\n{body[:1500]}\n\n[…the full answer is attached]",
                kind="result",
                reply_to=reply_to,
                **tie,
                why="asked",
            )
            self.app.notify(job.title, kind="result", file=str(md), why="asked")
        else:
            self.app.notify(f"{head}\n\n{body}", kind="result", reply_to=reply_to, **tie, why="asked")

    def _done(self, job, result, payload: dict) -> None:
        self._deliver(job, result, payload)

    def replies(self):
        return {"skill": self._again}

    def _again(self, msg: Incoming, ref: str) -> str:
        name, _, jid = (ref or "").partition("|")
        s = load_skill(self.app, name)
        if s is None:
            return f"The skill {name} is gone."
        prev = self.app.jobs.get(jid) if jid else None
        learning = self.app.modules.get("learning")  # a correction teaches the skill a lesson (modules/learning.py)
        if learning is not None and self.app.is_on("learning"):
            learning.corrected(s.name, jid, msg.text, replied=True)
        before = (prev.result or "")[-3000:] if prev else ""
        args = msg.text.strip()
        if before:
            args += f"\n\n(This is their reply to your previous answer for this skill, which was:\n{before}\n)"
        if s.name == "revision-pack":
            return self._pack(msg, args)
        self.run(s.name, args, reply_to=msg.message_id, files=msg.files)
        return "On it."

    # ------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command("skills", "the skills you can run (/skills journal shows one)", self._list),
            Command("newskill", "the AI writes a new skill for you: /newskill <what it should do>", self._newskill),
            Command("every", "run something on a schedule: /every monday 9:00 /journal plan my week", self._every),
            Command("routines", "what runs on a schedule, with Cancel buttons", self._routines),
            Command("pack", "a revision PDF from your notes: /pack linear algebra midterm", self._pack),
            Command(
                "studypack",
                "bundle course materials into a zip with an AI prompt: /studypack <subject>",
                self._studypack,
            ),
        ]

    def help(self):
        return [*super().help(), "/<skill> …  runs a skill, e.g. /journal what I did today"]

    def _list(self, msg: Incoming, arg: str) -> str:
        skills = {k: s for k, s in self.all().items() if not s.internal}
        taken = self.reserved()
        want = arg.strip().lower().lstrip("/")
        if want.startswith("copy "):
            try:
                f = self.customize(want[5:].strip().lstrip("/"))
            except KeyError as e:
                return str(e).strip("'").capitalize() + "."
            return f"Your copy is {rel(self.app, f)}: edit it there; it replaces the shipped one for you."
        if want:
            s = skills.get(want)
            if not s:
                return f"There's no skill called {want}. /skills lists them."
            where = {
                "shipped": "comes with Kurooto (/skills copy " + s.name + " makes your own copy to change)",
                "yours": f"yours: {rel(self.app, s.path)}",
                "prompt": f"from your prompts: {rel(self.app, s.path)}",
                "add-on": f"from your add-ons: {s.path}",
            }[s.source]
            return (
                f"/{s.name} {s.args}".strip()
                + f"\n{s.description}\nEffort: {s.effort}. Where: {where}."
                + ("\n(A command of the same name wins, so this one can't be typed.)" if s.name in taken else "")
            )
        if not skills:
            return "No skills yet. /newskill <what it should do> writes one."
        rows = []
        for s in sorted(skills.values(), key=lambda s: (s.source != "shipped", s.name)):
            mark = {"shipped": "", "add-on": " (add-on)"}.get(s.source, " (yours)")
            hint = f" {s.args}" if s.args else ""
            rows.append(f"/{s.name}{hint}{mark}\n   {s.description}")
        return (
            "Skills (reply to an answer to carry on; /skills <name> for details):\n\n"
            + "\n".join(rows)
            + "\n\n/newskill writes a new one; /every runs one on a schedule."
        )

    # ------------------------------------------------------------------------------------- new skills
    def _newskill(self, msg: Incoming, arg: str) -> str:
        want = arg.strip()
        if not want:
            return "What should it do? e.g. /newskill every Sunday, turn my week's daily notes into a short review"
        from kurooto.core.tools import agent_tools

        tools = ", ".join(t.name for t in agent_tools(self.app)) or "the notes tools"
        taken = ", ".join(sorted(self.reserved() | set(self.all())))
        self.app.jobs.submit(
            NEWSKILL.format(want=want, taken=taken, tools=tools),
            title=f"New skill: {want.splitlines()[0][:60]}",
            effort="medium",
            reply_to=msg.message_id,
            quiet=True,
            then="skills.drafted",
            then_payload={"want": want[:300]},
        )
        self.app.events.emit("skill_draft_asked", chars=len(want))
        return "Writing it; you'll see the whole skill before anything is saved."

    def _free(self, name: str) -> str:
        taken = self.reserved() | set(self.all())
        base = slug(name) or "my-skill"
        if len(base) < 2:
            base = f"{base}-skill"
        cand, n = base, 2
        while cand in taken:
            cand = f"{base[:36]}-{n}"
            n += 1
        return cand

    def _drafted(self, job, result, payload: dict) -> None:
        from kurooto.core.jobs import FRIENDLY

        if not result.ok:
            label = providers.CHOICES.get(job.brain or "", job.brain or "AI")
            self.app.notify(
                "I couldn't write that skill: " + FRIENDLY.get(result.verdict, "it failed.").format(brain=label),
                kind="result",
                why="asked",
            )
            return
        text = extract_skill(result.text)
        s = make(text, "", "draft") if text else None
        if s is None:
            self.app.notify(
                "The AI's answer wasn't a usable skill (it needs a header with a name, then instructions). Try "
                "/newskill again with a little more detail.",
                kind="result",
                why="asked",
            )
            self.app.events.emit("skill_draft_failed")
            return
        name = self._free(s.name)
        if name != s.name:
            text = re.sub(r"(?m)^name:.*$", f"name: {name}", text, count=1)
        text = re.sub(r"(?mi)^internal:.*\n", "", text, count=1)  # a skill you make is one you can type
        did = uuid.uuid4().hex[:8]
        jsave(self.dir / "drafts" / f"{did}.json", {"name": name, "text": text, "created": time.time()})
        self.app.notify(
            f"Here's a new skill, /{name}. Save it to use it; you can change the file later in your notes "
            f"(kurooto/skills/{name}/SKILL.md).\n\n{text}",
            kind="result",
            buttons=[[("Save", f"skn:{did}:save"), ("Discard", f"skn:{did}:discard")]],
            why="asked",
        )
        self.app.events.emit("skill_drafted", name=name)

    def callbacks(self):
        return {
            "skn": self._draft_button,
            "skr": self._routine_button,
            "skt": self._tectonic_button,
            "skp": self._auto_pack_button,
        }

    def _draft_button(self, ref: str, act: str) -> str:
        f = self.dir / "drafts" / f"{re.sub(r'[^a-f0-9]', '', ref)}.json"
        d = jload(f, None)
        if not d:
            return "That draft is gone."
        if act == "discard":
            f.unlink(missing_ok=True)
            self.app.events.emit("skill_discarded", name=d["name"])
            return "Discarded."
        name = d["name"]
        if name in self.reserved() | set(self.all()) or (user_dir(self.app) / name).exists():
            name = self._free(name)  # something took the name since the draft
        text = re.sub(r"(?m)^name:.*$", f"name: {name}", d["text"], count=1)
        out = user_dir(self.app) / name / "SKILL.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        f.unlink(missing_ok=True)
        self.app.events.emit("skill_saved", name=name)
        s = load_skill(self.app, name)
        self.app.notify(f"Saved. Try it: /{name}{' ' + s.args if s and s.args else ''}", kind="result", why="asked")
        return f"Saved as /{name}"

    # --------------------------------------------------------------------------------------- routines
    def routines(self) -> list[dict]:
        return jload(self.routines_file, []) or []

    def _save_routines(self, items: list[dict]) -> None:
        jsave(self.routines_file, items)

    def _schedule(self, r: dict) -> None:
        self.app.scheduler.every(
            f"skills:routine:{r['id']}", r["spec"], "skills.routine", {"id": r["id"]}, module=self.id
        )

    def add_routine(self, text: str) -> str:
        r = parse_every(text)
        what = r["what"]
        if what.startswith("/"):
            name = re.split(r"[\s@]", what[1:], maxsplit=1)[0].lower()
            if name == "every":
                return "A routine can't set up routines."
            if name not in self.reserved() and not load_skill(self.app, name):
                return f"There's no /{name} command or skill. /skills lists the skills, /help the commands."
        with Lock(self.app.paths.state, "skills-routines"):
            items = self.routines()
            if len(items) >= MAX_ROUTINES:
                return f"That's {MAX_ROUTINES} routines already; /routines lets you cancel some."
            r = {"id": uuid.uuid4().hex[:6], **r, "created": now().isoformat()}
            self._save_routines([*items, r])
        self.app.scheduler.action("skills.routine", self._routine)
        self._schedule(r)
        self.app.events.emit("routine_added", what=what.split()[0][:40], spec=r["spec"])
        nxt = self.app.scheduler.get(f"skills:routine:{r['id']}")
        when = f" First: {nxt.when.astimezone():%a %d %b %H:%M}." if nxt and not r["only"] else ""
        return f"{r['label']}: {what}.{when} /routines lists or cancels it."

    def cancel_routine(self, rid: str) -> bool:
        with Lock(self.app.paths.state, "skills-routines"):
            items = self.routines()
            keep = [x for x in items if x["id"] != rid]
            self._save_routines(keep)
        self.app.scheduler.cancel(f"skills:routine:{rid}")
        if len(keep) != len(items):
            self.app.events.emit("routine_cancelled")
        return len(keep) != len(items)

    def _every(self, msg: Incoming, arg: str) -> str:
        try:
            return self.add_routine(arg)
        except ValueError as e:
            return str(e)

    def _routines(self, msg: Incoming, arg: str) -> str | None:
        items = self.routines()
        if not items:
            return "Nothing runs on a schedule yet. /every monday 9:00 /journal plan my week sets one up."
        for r in items:
            msg.reply(f"{r['label']}: {r['what'][:300]}", buttons=[[("Cancel", f"skr:{r['id']}:x")]])
        return None

    def _routine_button(self, ref: str, act: str) -> str:
        return "Cancelled." if self.cancel_routine(ref) else "Already gone."

    def _routine(self, p: dict):
        r = next((x for x in self.routines() if x["id"] == p.get("id")), None)
        if r is None:
            self.app.scheduler.cancel(f"skills:routine:{p.get('id')}")
            return "gone"
        if r.get("only") and now().weekday() not in r["only"]:
            return "not today"
        what = r["what"]
        self.app.events.emit("routine_ran", what=what.split()[0][:40])
        if what.startswith("/"):
            m = re.match(r"/([\w-]+)(?:@\S+)?\s*(.*)\Z", what, re.S)
            name, args = (m[1].lower(), m[2]) if m else ("", "")
            if name and name not in self.reserved() and load_skill(self.app, name):
                if name == "revision-pack":
                    return self.pack_for(args, title_prefix="Routine: ", lane="bg")
                return self.run(name, args, title=f"Routine: {what[:60]}", lane="bg")

            def respond(text, buttons=None):
                return self.app.notify(
                    f"{r['label']}: {what[:60]}\n\n{text}", buttons=buttons, kind="result", why="asked"
                )

            incoming = Incoming(text=what, via="routine", respond=respond)
            threading.Thread(target=self.app.handle, args=(incoming,), name="routine", daemon=True).start()
            return "ran"
        return self.app.jobs.submit(what, title=f"Routine: {what[:60]}", lane="bg")

    def intents(self):
        def match(text: str):
            if not re.match(r"\s*every\s+(?:day|weekday|weekend|mon|tue|wed|thu|fri|sat|sun)", text, re.I):
                return None
            try:
                what = parse_every(text)["what"]
            except ValueError:
                return None
            # a request ("send me ...", "/journal ..."), not a fact ("every monday at 9 I have a lab")
            return {"text": text} if what.startswith("/") or ASKS.match(what) else None

        def link(text: str):
            found = LINK.findall(text)
            rest = LINK.sub("", text).strip(" \t\n-:,.")
            if len(found) != 1 or len(rest.split()) > 12 or NOT_FILING.match(rest):
                return None
            return {"args": f"{found[0]} {rest}".strip()}

        def file_link(msg: Incoming, slots: dict) -> str:
            self.run("add-to-notes", slots["args"], reply_to=msg.message_id)
            return "Filing it into your notes…"

        return [
            Intent("routine", "do something on a schedule", match, lambda m, s: self.add_routine(s["text"])),
            Intent("file_link", "a link on its own: filed into the notes", link, file_link),
        ]

    # ---------------------------------------------------------------------------------- revision packs
    def _subject(self, text: str) -> tuple[str | None, str, str]:
        """(notes folder or None, the subject's name, what the pack is for) from "/pack linear algebra midterm"."""
        words = text.split()
        subjects = self.app.modules.get("subjects") if self.app.is_on("subjects") else None
        for k in range(min(4, len(words)), 0, -1):
            head, rest = " ".join(words[:k]).strip(":,"), " ".join(words[k:])
            sl = subjects.resolve(head) if subjects else None
            if sl:
                return sl, subjects.name_of(sl), rest
            sl = slug(head)
            if (
                sl
                and sl not in SPECIAL
                and not self._layout_folder(sl)
                and layout.path(self.app, "subject", subject=sl).is_dir()
            ):
                return slug(head), head, rest
        head, _, rest = text.partition(":")
        return None, head.strip(), rest.strip()

    def _layout_folder(self, name: str) -> bool:
        """A top-level folder your notes layout uses for something else (not a subject)."""
        return layout.of(self.app).kind_of_folder(name)

    def pack_for(self, text: str, reply_to=None, title_prefix: str = "", lane: str | None = None) -> str:
        """Start a revision pack; returns the job id. lane="bg" for one nobody asked for just now."""
        folder, name, what = self._subject(text)
        day = f"{now():%Y-%m-%d}"
        out = (
            layout.file_path(self.app, "pack", f"revision-pack-{day}.tex", subject=folder)
            if folder
            else layout.file_path(self.app, "pack", f"{day}-{slug(name, 50) or 'pack'}.tex", subject="revision-packs")
        )
        tex = layout.shown(self.app, out)
        lay = layout.of(self.app)
        args = (
            f"Subject: {name}."
            + (
                f" Its notes are in {lay.link('subject', subject=folder)}/ (course page "
                f"{lay.link('course', subject=folder)}, exam prep {lay.link('exam_prep', subject=folder)})."
                if folder
                else ""
            )
            + f" What it's for: {what or 'the next quiz or exam'}."
        )
        return self.run(
            "revision-pack",
            args,
            reply_to=reply_to,
            quiet=True,
            then="skills.latex",
            then_payload={"name": "revision-pack", "tex": tex, "label": f"Revision pack: {name}", "subject": folder},
            title=f"{title_prefix}Revision pack: {name}"[:80],
            lane=lane,
        )

    # ------------------------------------------------------------------- packs before quizzes and exams
    def auto_packs(self, p: dict | None = None) -> int:
        """The evening before a quiz or exam with a subject (12 to 36 hours ahead, after skills.auto_pack_after): a
        revision pack, offered with a button (ask) or built (auto). Once per quiz or exam."""
        mode = str(self.setting("auto_pack") or "off").strip().lower()
        dl = self.app.modules.get("deadlines") if self.app.is_on("deadlines") else None
        if mode not in ("ask", "auto") or dl is None or not load_skill(self.app, "revision-pack"):
            return 0
        t = now()
        try:
            after = dt_time(str(self.setting("auto_pack_after") or "16:00"))
        except ValueError:
            after = dt_time("16:00")
        if t.time() < after:
            return 0
        f = self.dir / "auto-packs.json"
        with Lock(self.app.paths.state, "skills-packs"):
            done = jload(f, {}) or {}
            todo = [e for e in dl.exams_soon(2) if e.get("subject") and 12 <= e["hours"] <= 36 and e["id"] not in done]
            for e in todo:
                done[e["id"]] = {"at": t.isoformat(timespec="seconds"), "text": self._pack_text(dl, e), "mode": mode}
            if todo:
                cutoff = t.timestamp() - 60 * 86400  # forgotten after two months
                keep = {k: v for k, v in done.items() if _ts(v.get("at")) >= cutoff}
                jsave(f, keep)
        for e in todo:
            text = done[e["id"]]["text"]
            if mode == "auto":  # nobody is waiting on it: it never holds up your own requests
                self.pack_for(text, title_prefix="Before your exam: ", lane="bg")
                self.app.events.emit("auto_pack", mode="auto")
                continue
            self.app.notify(
                f"{e['title']} is {e['when']}. A revision pack for it tonight?",
                kind="question",
                title="Revision pack",
                buttons=[[("Build it", f"skp:{e['id']}:yes"), ("No thanks", f"skp:{e['id']}:no")]],
                why="packs.offer",
                about=e["title"],
            )
            self.app.events.emit("auto_pack", mode="ask")
        return len(todo)

    @staticmethod
    def _pack_text(dl, e: dict) -> str:
        """What to /pack for a quiz or exam: "<subject>: <title> on Fri 24 Oct 10:00"."""
        when = dt.datetime.fromisoformat(e["due"]).strftime("%a %d %b %H:%M")
        return f"{e['subject']}: {e['title']} on {when}"

    def _auto_pack_button(self, ref: str, act: str) -> str:
        d = (jload(self.dir / "auto-packs.json", {}) or {}).get(ref)
        if not d:
            return "That one is old."
        if act != "yes":
            self.app.events.emit("auto_pack_declined")
            return "OK, no pack."
        if d.get("built"):
            return "It's on its way already."
        with Lock(self.app.paths.state, "skills-packs"):
            all_ = jload(self.dir / "auto-packs.json", {}) or {}
            all_.setdefault(ref, d)["built"] = True
            jsave(self.dir / "auto-packs.json", all_)
        self.pack_for(d["text"], title_prefix="Before your exam: ")
        self.app.events.emit("auto_pack_accepted")
        return "Building it; it comes here in a few minutes."

    def _studypack(self, msg: Incoming, arg: str) -> str:
        """/studypack <subject> [what it's for]: the subject's notes and course files in a zip with a prompt for another
        AI (core/studypack.py), sent here."""
        text = arg.strip()
        if not text:
            return (
                "Which subject? /studypack deep learning quiz on thursday (the rest says what it's for; name a topic "
                "to narrow it: /studypack pota quiz on thermodynamics). /studypack prompt: edit what packs ask the AI."
            )
        m = re.fullmatch(r"prompt(?:\s+(reset|default))?", text, re.I)
        if m:  # the prompt every pack gives the other AI, as a note of yours to edit
            from kurooto.core import layout, studypack

            f, made = studypack.make_prompt_file(self.app, reset=bool(m[1]))
            where = layout.shown(self.app, f)
            if m[1]:
                return f"The study-pack prompt is back to Kurooto's own, in {where}."
            return (
                f"{'Made' if made else 'Your'} study-pack prompt: {where}. Edit it in your notes; every pack uses it "
                "from now on ({name}, {topics} and {aim} are filled in; the note's top lists them all). "
                "/studypack prompt reset puts Kurooto's back."
            )
        subj = self.app.modules.get("subjects")
        found = subj.find_in(text) if subj is not None and self.app.is_on("subjects") else []
        if found:
            sid, name = found[0], subj.name_of(found[0])
            aim = re.sub(re.escape(name), "", text, count=1, flags=re.I).strip(" ,:-")
            for alias in [sid, *next((x.get("aliases", []) for x in subj.subjects() if x["slug"] == sid), [])]:
                aim = re.sub(r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", "", aim, count=1, flags=re.I)
            aim = aim.strip(" ,:-")
        else:
            sid, _, aim = text.partition(" ")
            name = ""
        return self._send_study_pack(sid, name, aim, msg.message_id)

    def _send_study_pack(self, subject: str, name: str, aim: str, reply_to=None, topics=None) -> str:
        from kurooto.core import studypack

        drive = self.app.modules.get("drive_upload")
        big = drive is not None and self.app.is_on("drive_upload") and drive.setting("big_files")
        try:  # with Drive upload on nothing is left out: a pack over Telegram's 50 MB comes as a Drive link
            zip_path, info = studypack.build(self.app, subject, name, aim, limit=None if big else -1, topics=topics)
        except ValueError as e:
            return str(e)
        title = name or subject.replace("-", " ").title()
        ok, said = send_file(
            self.app, zip_path, f"Study pack: {title}. Upload it to your AI and paste the prompt below."
        )
        if (
            ok and "telegram" in self.app.notifier.channels
        ):  # the prompt on its own, ready to copy (it's in the zip too)
            self.app.notify(
                studypack.prompt_text(title, aim, info["topics"], self.app),
                kind="result",
                title=f"Prompt for the {title} pack",
                why="asked",
            )
        left = (
            f" {len(info['left_out'])} file(s) didn't fit in Telegram's 50 MB; INDEX.md lists them (Drive upload "
            "sends bigger packs as a link)."
            if info["left_out"]
            else ""
        )
        if info["topics"]:
            return (
                f"On {', '.join(info['topics'])}: {info['class']} class files first, then {info['books']} book "
                f"extracts (only their pages on it), and {info['notes']} notes, in one zip.{left} {said}"
            )
        return f"{info['notes']} notes and {info['files']} course files in one zip.{left} {said}"

    def _pack(self, msg: Incoming, arg: str) -> str:
        if not arg.strip():
            return "Which subject? /pack linear algebra (add what it's for: /pack linear algebra midterm friday)"
        if not load_skill(self.app, "revision-pack"):
            return "The revision-pack skill is missing."
        self.pack_for(arg.strip(), reply_to=msg.message_id)
        pdf = "" if pdf_engine(self.app) else " (as LaTeX: PDFs need Tectonic, which I'll offer to install)"
        return f"Building a revision pack{pdf}; it comes here in a few minutes."

    def _latex(self, job, result, payload: dict) -> None:
        """A skill answered with a LaTeX document: save it in the notes, compile it, send the PDF."""
        tex = extract_latex(result.text) if result.ok else None
        if not tex:
            extra = "" if not result.ok else "\n\n(No LaTeX document in that answer, so there's no PDF this time.)"
            self._deliver(job, result, payload, extra)
            return
        from kurooto.core.tools import note_path

        target = str(payload.get("tex") or "").removesuffix(".tex")
        if target and Path(target).is_absolute():  # files outside the notes (files.folder, core/layout.py)
            f = Path(target + ".tex")
        else:
            f = note_path(self.app.workspace, target, must_exist=False) if target else None
        if f is None:
            f = layout.file_path(self.app, "latex", f"{now():%Y-%m-%d}-pack.md")
        f = f.with_suffix(".tex")
        if f.exists() and not payload.get("overwrite"):
            n = 2
            while f.with_name(f"{f.stem}-{n}.tex").exists():
                n += 1
            f = f.with_name(f"{f.stem}-{n}.tex")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(tex, encoding="utf-8")
        summary = re.sub(r"```.*?```", "", result.text, flags=re.S).strip()[-400:]
        payload = {**payload, "tex": rel(self.app, f), "summary": summary, "reply_to": job.reply_to, "lane": job.lane}
        self.app.events.emit("latex_saved", name=payload.get("name"), chars=len(tex))
        threading.Thread(target=self._finish_pack, args=(f, payload), name="latex", daemon=True).start()

    def _finish_pack(self, f: Path, payload: dict) -> None:
        label = payload.get("label") or "Your PDF"
        if not pdf_engine(self.app):
            ref = self._remember_pack(f, payload)
            send_file(
                self.app,
                f,
                f"{label} (LaTeX; it's also {self._kept_at(f)}). For a PDF next time, install "
                "Tectonic, a small LaTeX engine (about 25 MB, plus about 50 MB of LaTeX packages it fetches the first "
                "time).",
            )
            no = self.dir / "tectonic-declined"
            if not no.exists() or time.time() - no.stat().st_mtime > 30 * 86400:  # asked at most once a month
                self.app.notify(
                    "Install Tectonic so packs come as PDFs?",
                    kind="question",
                    buttons=[[("Install Tectonic", f"skt:{ref}:install"), ("Not now", f"skt:{ref}:no")]],
                    why="asked",
                )
            return
        ok, err = compile_tex(self.app, f)
        if ok:
            pdf = f.with_suffix(".pdf")
            send_file(self.app, pdf, f"{label}. {payload.get('summary', '')}".strip()[:900])
            self._link_in_daily(pdf, label, payload.get("subject"))
            self.app.events.emit("pdf_built", name=payload.get("name"), bytes=pdf.stat().st_size)
            return
        self.app.events.emit("pdf_failed", name=payload.get("name"), attempt=payload.get("attempt", 1))
        if payload.get("attempt", 1) < 2:  # one more go: the AI fixes its own LaTeX
            self.app.jobs.submit(
                FIX_LATEX.format(errors=err or "(no message)", tex=f.read_text(encoding="utf-8")[:60000]),
                title=f"Fixing: {label}"[:80],
                effort="medium",
                quiet=True,
                then="skills.latex",
                then_payload={**payload, "tex": payload["tex"], "attempt": 2, "overwrite": True},
                lane=payload.get("lane"),
            )
            return
        send_file(
            self.app,
            f,
            f"{label}: it didn't compile ({err.splitlines()[0][:200] if err else 'no message'}). "
            f"Here's the LaTeX; it's also {self._kept_at(f)}.",
        )

    def _kept_at(self, f: Path) -> str:
        """Where a pack is kept, for messages: "in your notes: x/y.tex" or "at /full/path.tex"."""
        where = layout.shown(self.app, f)
        return f"in your notes: {where}" if layout.of(self.app).inside_notes(f) else f"at {where}"

    def _remember_pack(self, f: Path, payload: dict) -> str:
        ref = uuid.uuid4().hex[:8]
        with Lock(self.app.paths.state, "skills-packs"):
            d = jload(self.dir / "packs.json", {}) or {}
            d[ref] = {
                "tex": rel(self.app, f),
                "label": payload.get("label"),
                "name": payload.get("name"),
                "subject": payload.get("subject"),
            }
            jsave(self.dir / "packs.json", dict(list(d.items())[-50:]))
        return ref

    def _tectonic_button(self, ref: str, act: str) -> str:
        d = (jload(self.dir / "packs.json", {}) or {}).get(ref)
        if act == "no":
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / "tectonic-declined").touch()
            self.app.events.emit("tectonic_declined")
            return "OK. Packs come as LaTeX."
        if act == "install":
            threading.Thread(target=self._install, args=(ref if d else None,), name="tectonic", daemon=True).start()
            return "Installing Tectonic…"
        if act == "pdf" and d:
            f = self.app.workspace / d["tex"]
            if f.is_file():
                threading.Thread(target=self._finish_pack, args=(f, {**d, "attempt": 2}), daemon=True).start()
                return "Making the PDF (the first one takes a few minutes)…"
        return "That pack is gone."

    def _install(self, ref: str | None) -> None:
        from kurooto.core.prereqs import Prereqs

        ok, msg = Prereqs(self.app.paths.app, self.app.paths.cache).install("tectonic", progress=lambda s: None)
        self.app.events.emit("tectonic_installed" if ok else "tectonic_install_failed")
        if not ok:
            self.app.notify(msg, kind="result", why="asked")
            return
        d = (jload(self.dir / "packs.json", {}) or {}).get(ref) if ref else None
        f = self.app.workspace / d["tex"] if d else None
        if f is not None and f.is_file():  # the pack that was waiting: no second tap
            self.app.notify(
                "Tectonic is installed. Making that PDF now; the first one takes a few minutes while it fetches the "
                "LaTeX packages.",
                kind="result",
                why="asked",
            )
            self._finish_pack(f, {**d, "attempt": 2})
            return
        self.app.notify(
            "Tectonic is installed: revision packs come as PDFs now. The first PDF takes a few minutes while it "
            "fetches the LaTeX packages.",
            kind="result",
            why="asked",
        )

    def _link_in_daily(self, pdf: Path, label: str, subject: str | None = None) -> None:
        """Link the PDF from today's daily note, and from the subject's course page if it has one."""
        from kurooto.core.tools import add_to_section
        from kurooto.modules import daily

        day = f"{now():%Y-%m-%d}"
        f = daily.note_path(self.app)
        f.parent.mkdir(parents=True, exist_ok=True)
        new = layout.frontmatter(self.app, "daily", f, agent=False, bare=True) + f"# {day}\n"
        old = f.read_text(encoding="utf-8", errors="replace") if f.exists() else new
        f.write_text(add_to_section(old, "Added", f"- {label}: {layout.file_link(self.app, pdf, f)}"), encoding="utf-8")
        course = layout.path(self.app, "course", subject=subject) if subject else None
        if course is not None and course.is_file():
            text = course.read_text(encoding="utf-8", errors="replace")
            line = f"- {day}: {layout.file_link(self.app, pdf, course)}"
            if line not in text:
                course.write_text(add_to_section(text, "Revision packs", line), encoding="utf-8")

    # ------------------------------------------------------------------------------------ tools
    def call_tools(self):
        return [
            Tool(
                "send_file",
                "Send them a file from their notes folder on Telegram (up to 50 MB), e.g. a PDF you made. With Drive "
                "upload on, to=drive (or a bigger file) puts it in their Google Drive and sends the link.",
                self._tool_send,
                {
                    "path": arg("the file's path inside the notes folder, e.g. linear-algebra/revision-pack.pdf"),
                    "caption": arg("one line about it, optional"),
                    "to": arg("telegram (the default) or drive"),
                },
                ("path",),
                offline="queue",
                hint="send_file sends them a file from their notes on Telegram. When they ask for files, send them "
                "(send_file, send_files, study_pack): never answer with file paths or file:// links.",
            ),
            Tool(
                "send_files",
                "Send them several files on Telegram: up to two as they are, more as one zip. When they ask for "
                "'the files' or 'everything about X', find them (list_files, search_notes) and send them with this.",
                self._tool_send_many,
                {
                    "paths": arg("the files' paths, one per line (inside the notes folder or the course files folder)"),
                    "zip_name": arg("a name for the zip when there are more than two, optional"),
                    "caption": arg("one line about them, optional"),
                },
                ("paths",),
                offline="queue",
            ),
            Tool(
                "study_pack",
                "Send them a zip with one subject's notes and course files and a prompt they can give another AI "
                "(Claude, ChatGPT) to write deeper notes. Use it for 'send me everything for my X quiz'.",
                self._tool_study_pack,
                {
                    "subject": arg("the subject, e.g. deep learning or its short name"),
                    "aim": arg("what it's for, e.g. quiz on Thursday, optional"),
                    "topics": arg(
                        "optional: the syllabus to narrow it to, comma-separated, e.g. thermodynamics, lapse rate; "
                        "class material is put first and books give only their pages on it"
                    ),
                },
                ("subject",),
                offline="queue",
            ),
        ]

    def _sendable(self) -> list[Path]:
        """Where a tool may send files from: your notes, files and course files, Kurooto's Classroom copies."""
        from kurooto.core.places import write_roots

        return [*write_roots(self.app), self.app.paths.data / "classroom", Path(self.app.paths.cache) / "study-packs"]

    def _tool_send(self, a: dict) -> str:
        p = Path(str(a.get("path") or "").strip())
        if not p.is_absolute():
            p = self.app.workspace / p
        to = "drive" if str(a.get("to") or "").strip().lower() == "drive" else ""
        return send_file(self.app, p, str(a.get("caption") or ""), inside=self._sendable(), to=to)[1]

    def _tool_send_many(self, a: dict) -> str:
        raw = a.get("paths") or ""
        items = raw if isinstance(raw, list) else re.split(r"[\n;]+", str(raw))
        paths = []
        for x in items:
            x = str(x).strip().removeprefix("file://").strip()
            if not x:
                continue
            q = Path(x)
            paths.append(q if q.is_absolute() else self.app.workspace / q)
        return send_files(
            self.app, paths, str(a.get("caption") or ""), inside=self._sendable(), zip_name=str(a.get("zip_name") or "")
        )[1]

    def _tool_study_pack(self, a: dict) -> str:
        text = str(a.get("subject") or "").strip()
        subj = self.app.modules.get("subjects")
        sid = subj.resolve(text) if subj is not None and self.app.is_on("subjects") else None
        topics = [x.strip() for x in str(a.get("topics") or "").split(",") if x.strip()] or None
        return self._send_study_pack(
            sid or text, subj.name_of(sid) if sid else "", str(a.get("aim") or ""), topics=topics
        )


def dt_time(text: str) -> dt.time:
    """A time of day from "16:00" (ValueError if it isn't one)."""
    return dt.time.fromisoformat(text.strip().zfill(5))


def _ts(iso) -> float:
    try:
        return dt.datetime.fromisoformat(str(iso)).timestamp()
    except ValueError:
        return 0.0
