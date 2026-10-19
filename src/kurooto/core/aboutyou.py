"""About you: what your other AI accounts already know about you, gathered once so Kurooto starts out knowing you.

1. The setup page gives two prompts: one for the AI you use most, one for every other account. Run them in as many AI
   accounts as you can (ChatGPT, Claude, Gemini, Copilot, Perplexity, ...; old and work accounts too): each one knows
   different things.
2. Each report you bring back (pasted or uploaded) is kept privately in Kurooto's data folder, not in your notes.
3. "Build my profile" asks your AI to merge them into one profile, saved in your notes as about-me/profile.md, which
   you can read and edit. Its short "In brief" part goes along with every AI request Kurooto makes, so answers fit you.
"""

from __future__ import annotations

import re
import time
from importlib import resources
from typing import TYPE_CHECKING

from kurooto.core.clock import now

if TYPE_CHECKING:
    from kurooto.app import App

MAX_REPORT = 2_000_000  # characters
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
    def merge(self) -> str:
        """Ask the AI to merge the reports into one profile (in the background; the result lands in your notes)."""
        reps = sorted(self.dir.glob("*.md")) if self.dir.exists() else []
        if not reps:
            raise ValueError("Add at least one report first.")
        if not self.app.settings.get("brain.main"):
            raise ValueError("Pick an AI first (the AI step); it does the merging.")
        body = "\n\n".join(
            f"===== REPORT {i + 1} =====\n{f.read_text(encoding='utf-8')[:400_000]}" for i, f in enumerate(reps)
        )
        return self.app.jobs.submit(
            MERGE_PROMPT + "\n" + body, title="Building your profile", effort="high", quiet=True, then="aboutyou.save"
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
        if f.exists():  # keep the previous version next to it
            f.replace(f.with_name(f"profile-{time.strftime('%Y%m%d-%H%M%S')}.md"))
        f.write_text(
            f"# About me\n\nMade by {self.app.name} on {now():%Y-%m-%d} from {len(self.reports())} AI account "
            f'report(s). Edit it freely: Kurooto reads the "In brief" part before every request.\n\n{text}\n',
            encoding="utf-8",
        )
        self.app.events.emit("aboutyou_profile", chars=len(text))
        self.app.notify(
            f"Your profile is ready: {f.relative_to(self.app.workspace).as_posix()} in your notes. "
            "Have a look and fix anything that's off.",
            kind="result",
        )

    def brief(self, limit: int = 2500) -> str:
        """The profile's "In brief" part (what goes along with every AI request), or ""."""
        try:
            text = self.profile_file.read_text(encoding="utf-8")
        except OSError:
            return ""
        m = re.search(r"^## In brief[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        return (m.group(1) if m else "").strip()[:limit]

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
                "building": building,
                "updated": time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime)) if f.exists() else "",
            },
        }
