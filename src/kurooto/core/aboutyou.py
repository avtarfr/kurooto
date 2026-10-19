"""About you: what your other AI accounts already know about you, gathered once so Kurooto starts out knowing you.

1. The setup page gives two prompts: one for the AI you use most, one for every other account. Run them in as many AI
   accounts as you can (ChatGPT, Claude, Gemini, Copilot, Perplexity, ...; old and work accounts too): each one knows
   different things.
2. Each report you bring back (pasted or uploaded) is kept privately in Kurooto's data folder, not in your notes.
3. "Build my profile" asks your AI to merge them into one profile, saved in your notes as about-me/profile.md. Its
   short "In brief" part goes along with every AI request Kurooto makes, so answers fit you.
4. Edit it right there (the setup page's About you step, or the dashboard's About you tab), or in your notes. Saving
   keeps the previous version beside it (profile-<date>.md). Building it again never replaces your edits silently: if
   you changed it since it was built, Kurooto asks first, and a profile you edit while a new one is being built stays
   as it is (the new one goes beside it as profile-new-<date>.md). /aboutme on Telegram shows the In-brief part.
"""

from __future__ import annotations

import hashlib
import re
import time
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

MAX_REPORT = 2_000_000  # characters
MAX_PROFILE = 200_000  # characters: a profile is a few pages; this is far beyond that
BRIEF = re.compile(r"^## In brief[^\n]*\n(.*?)(?=^## |\Z)", re.S | re.M)


class Edited(ValueError):
    """The profile was changed since it was built: building it again needs a yes first."""


def brief_of(text: str, limit: int = 2500) -> str:
    """A profile's "In brief" part: exactly what goes along with every AI request ("" if there's none)."""
    m = BRIEF.search((text or "").replace("\r\n", "\n"))
    return (m.group(1) if m else "").strip()[:limit]


def brief_warning(text: str) -> str:
    """What's wrong with a profile's In-brief part, in a line ("" if nothing)."""
    if not re.search(r"^## In brief", text or "", re.M):
        return (
            'There\'s no "## In brief" section, so nothing from your profile goes along with your requests. Add one '
            "(a few lines about you, under that heading) if you want it to."
        )
    if not brief_of(text):
        return 'The "## In brief" section is empty, so nothing from your profile goes along with your requests.'
    return ""


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _keep(f: Path, stem: str = "profile") -> Path:
    """A free name beside f for a kept version: <stem>-<date>-<time>.md (-2, -3… if that's taken)."""
    base = f"{stem}-{time.strftime('%Y%m%d-%H%M%S')}"
    out, n = f.with_name(f"{base}.md"), 2
    while out.exists():
        out, n = f.with_name(f"{base}-{n}.md"), n + 1
    return out


MERGE_PROMPT = """Below are reports that different AI accounts wrote about me: what each knows about who I am,
how I work and how I use AI. Merge them into ONE profile for my personal assistant (Kurooto), which runs on my
computer and uses the profile as background for everything it does for me.

Rules:
- Combine what agrees; keep each finding's confidence label (Explicit / Repeated / Inferred / Unknown) and which
  report(s) it came from. Something several reports say independently counts as Repeated.
- Where reports conflict, keep both with their dates and sources, and say which looks current.
- Leave out passwords, keys, card or ID numbers and other credentials; leave out sensitive personal attributes unless I
  stated them and they matter for how the assistant should help.
- Don't invent anything. Keep it concrete and useful; skip generic personality talk.

Write Markdown, starting with exactly this heading and section:

## In brief (for the assistant)
At most 250 words: who I am, what I'm working towards right now, how I like to be helped and spoken to, and the
boundaries to respect. This part goes along with every request, so make every word count.

Then these sections:
## Who I am
## Goals and current projects
## Routines, schedule and commitments
## How I work, learn and decide
## How to talk to me and help me
## Tools, devices and services
## How I use AI today
## Recurring problems and things worth automating
## Privacy and boundaries
## Contradictions and open questions
## Ideas for setting up Kurooto
(Concrete suggestions that map to its features: reminders, check-ins, deadlines, subjects and timetable, quiz, calendar,
research sources, notes, phone calls, the morning alarm. Only where the evidence supports them.)
## Sources
(Each report: which AI and account, its date, and what it could and couldn't access.)

Output only the profile.

The reports:
"""


def prompt(which: str, source: str = "") -> str:
    """One of the two prompts ("main" or "other"), filled in for the AI account you'll paste it into."""
    name = "main-account.md" if which == "main" else "other-account.md"
    text = resources.files("kurooto.data").joinpath("prompts", name).read_text(encoding="utf-8")
    source = source.strip() or ("my main AI account" if which == "main" else "another of my AI accounts")
    prefix = re.sub(r"[^A-Z0-9]+", "_", source.upper()).strip("_")[:30] or "ACCOUNT"
    return text.replace("{{SOURCE}}", source).replace("{{PREFIX}}", prefix)


class AboutYou:
    def __init__(self, app: App):
        self.app = app
        self.dir = app.paths.data / "about-you"

    @property
    def profile_file(self):
        return self.app.workspace / "about-me" / "profile.md"

    @property
    def state_file(self):
        return self.app.paths.state / "aboutyou.json"  # the profile as last built, to tell when you've edited it

    # ------------------------------------------------------------------------------------- reports
    def reports(self) -> list[dict]:
        out = []
        for f in sorted(self.dir.glob("*.md")) if self.dir.exists() else []:
            head = f.read_text(encoding="utf-8", errors="replace")[:400]
            m = re.search(r"^<!-- from: (.*?) · added: (.*?) -->", head)
            out.append(
                {
                    "id": f.stem,
                    "label": m.group(1) if m else f.stem,
                    "added": m.group(2) if m else "",
                    "chars": f.stat().st_size,
                }
            )
        return out

    def add(self, label: str, text: str) -> dict:
        text = (text or "").replace("\r\n", "\n").strip()
        label = re.sub(r"\s+", " ", label or "").strip()[:80] or "an AI account"
        if len(text) < 200:
            raise ValueError("That's too short to be a report: paste the AI's whole answer (or upload the file).")
        if len(text) > MAX_REPORT:
            raise ValueError("That's over 2 million characters; split it, or ask the AI for a tighter report.")
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            self.dir.chmod(0o700)
        except OSError:
            pass
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:40] or "account"
        f = self.dir / f"{now():%Y%m%d-%H%M%S}-{slug}.md"
        f.write_text(f"<!-- from: {label} · added: {now():%Y-%m-%d %H:%M} -->\n{text}\n", encoding="utf-8")
        f.chmod(0o600)
        self.app.events.emit("aboutyou_report", chars=len(text))
        return {"id": f.stem, "label": label}

    def remove(self, rid: str) -> bool:
        f = self.dir / f"{re.sub(r'[^A-Za-z0-9-]', '', rid)}.md"
        if f.exists():
            f.unlink()
            return True
        return False

    # ------------------------------------------------------------------------------------- profile
    def merge(self, replace: bool = False) -> str:
        """Ask the AI to merge the reports into one profile (in the background; the result lands in your notes).
        If you've edited the profile since it was built, this raises Edited unless `replace` (you said yes)."""
        reps = sorted(self.dir.glob("*.md")) if self.dir.exists() else []
        if not reps:
            raise ValueError("Add at least one report first.")
        if not self.app.settings.get("brain.main"):
            raise ValueError("Pick an AI first (the AI step); it does the merging.")
        if not replace and self.edited():
            raise Edited(
                "You've changed your profile since it was built. Building it again replaces your changes (your "
                "version is kept beside it as profile-<date>.md, so you can copy things back). Build it again anyway?"
            )
        body = "\n\n".join(
            f"===== REPORT {i + 1} =====\n{f.read_text(encoding='utf-8')[:400_000]}" for i, f in enumerate(reps)
        )
        return self.app.jobs.submit(
            MERGE_PROMPT + "\n" + body,
            title="Building your profile",
            effort="high",
            quiet=True,
            then="aboutyou.save",
            then_payload={"base": _hash(self.text()) if self.profile_file.exists() else ""},
        )

    def save_profile(self, job, result, payload) -> None:
        if not result.ok or "## In brief" not in result.text:
            self.app.notify(
                "Building your profile didn't work this time: "
                + (result.detail or result.text)[:300]
                + " Try again from the setup page (About you).",
                kind="result",
            )
            return
        text = result.text[result.text.index("## In brief") :].strip()
        f = self.profile_file
        f.parent.mkdir(parents=True, exist_ok=True)
        doc = (
            f"# About me\n\nMade by {self.app.name} on {now():%Y-%m-%d} from {len(self.reports())} AI account "
            f'report(s). Edit it freely: Kurooto reads the "In brief" part before every request.\n\n{text}\n'
        )
        base = (payload or {}).get("base")
        if f.exists() and (_hash(self.text()) != base if base is not None else self.edited()):
            # you changed it while this one was being built: yours stays as it is, the new one goes beside it
            new = _keep(f, "profile-new")
            new.write_text(doc, encoding="utf-8")
            self.app.events.emit("aboutyou_profile", chars=len(text), kept_yours=True)
            self.app.notify(
                "Your new profile is ready, but you changed yours while it was being built, so yours stays as it is. "
                f"The new one is {new.relative_to(self.app.workspace).as_posix()} in your notes: copy over what you "
                "want.",
                kind="result",
            )
            return
        if f.exists():  # keep the previous version next to it
            f.replace(_keep(f))
        f.write_text(doc, encoding="utf-8")
        jsave(self.state_file, {"built": _hash(doc), "at": time.time()})
        self.app.events.emit("aboutyou_profile", chars=len(text))
        self.app.notify(
            f"Your profile is ready: {f.relative_to(self.app.workspace).as_posix()} in your notes. "
            "Have a look and fix anything that's off.",
            kind="result",
        )

    def brief(self, limit: int = 2500) -> str:
        """The profile's "In brief" part (what goes along with every AI request), or ""."""
        return brief_of(self.text(), limit)

    def text(self) -> str:
        try:
            return self.profile_file.read_text(encoding="utf-8")
        except OSError:
            return ""

    def edited(self) -> bool:
        """Was the profile changed since Kurooto built it? (One it didn't build, or built before it kept track, counts
        as yours.)"""
        if not self.profile_file.exists():
            return False
        built = (jload(self.state_file, {}) or {}).get("built")
        return built != _hash(self.text())

    def save_text(self, text: str) -> dict:
        """Your edit, from the setup page or the dashboard. The previous version is kept beside it. Raises
        ValueError for an empty or absurdly long text; a missing In-brief part is only a warning."""
        text = (text or "").replace("\r\n", "\n").strip()
        if not text:
            raise ValueError(
                "The profile can't be empty. To start again, build it again (About you on the setup page)."
            )
        if len(text) > MAX_PROFILE:
            raise ValueError(f"That's over {MAX_PROFILE:,} characters: a profile is a few pages. Shorten it.")
        f = self.profile_file
        changed = text + "\n" != self.text()
        if changed:
            f.parent.mkdir(parents=True, exist_ok=True)
            if f.exists():
                f.replace(_keep(f))
            f.write_text(text + "\n", encoding="utf-8")
            self.app.events.emit("aboutyou_edited", chars=len(text))
        return {"ok": True, "changed": changed, **self.view()}

    def view(self) -> dict:
        """The profile for the editor: its text, its In-brief part, and what's off about it."""
        f, text = self.profile_file, self.text()
        return {
            "exists": f.exists(),
            "path": str(f),
            "text": text,
            "brief": brief_of(text),
            "warning": brief_warning(text) if f.exists() else "",
            "edited": self.edited(),
            "updated": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime)) if f.exists() else "",
        }

    def for_chat(self) -> str:
        """/aboutme: the In-brief part, and where to edit the whole profile."""
        url = (jload(self.app.paths.state / "web.json", {}) or {}).get("url") or (
            f"http://127.0.0.1:{self.app.settings.get('web.port') or 8770}/"
        )
        rel = "about-me/profile.md"
        if not self.profile_file.exists():
            return (
                "No profile yet. Build one on your computer: the setup page's About you step "
                f"({url}setup) gathers what your other AI accounts know about you."
            )
        b = self.brief()
        head = (
            f"What goes along with every AI request (the In-brief part of {rel} in your notes):\n\n{b}"
            if b
            else f"Your profile ({rel} in your notes) has no In-brief part, so nothing from it goes along with your "
            "requests."
        )
        return f"{head}\n\nEdit it on your computer: {url}#about (the dashboard's About you tab), or in your notes."

    def status(self) -> dict:
        f = self.profile_file
        building = any(
            j.title == "Building your profile" and j.status in ("queued", "running") for j in self.app.jobs.recent(10)
        )
        return {
            "reports": self.reports(),
            "profile": {
                "exists": f.exists(),
                "path": str(f),
                "brief": self.brief(),
                "edited": self.edited(),
                "building": building,
                "updated": time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime)) if f.exists() else "",
            },
        }
