"""One life story (Brain, 0.8.0 stage 08): a single autobiography every part of Kurooto reads first (Telegram, the app's
chat,
calls, background jobs), so it is one agent rather than many sessions.

    core_signed.md / .sig   the fixed core, loaded verbatim; its sha256 is checked every time, and a mismatch refuses
    the story
                            and alerts you. Nothing here (and no nightly rebuild) can change it; it's a protected file
                            (stage 02)
    write_week(app, week)   each Sunday night: the week's journals roll up into a chapter in `<state>/mind-
    story/weeks/`. Code
                            picks the facts (the biggest swings, promises, what it did and changed); each line is a
                            journal
                            line that already passed stage 07's checks, and is checked again from its fact
    summary(app)            the self-summary, rebuilt nightly from the last 8 chapters and the core, within
    `mind.story.tokens` (800)
    prompt(app)             what goes in front of every AI request and every call: the summary, with its core
    quote / add_quoted      anything it ingested (a book page, mail, a note) appears only as a quoted datum with its
    source
                            pointer, in its own section, never as a belief or a goal (so "your real goal is X" can't
                            plant one)

Every line of a chapter cites the log records it comes from (`#seq`). Lines about you follow the read's forget cascade
(`forget_day`) and are struck when you strike them; lines about Kurooto's own acts stay. Files are in `<state>/mind-
story/`,
beside the journal, not in the scorekeeper's folder.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.mind import forgetting, journal

if TYPE_CHECKING:
    from kurooto.app import App

PART = "story"  # its switch: mind.story.on

register_defaults(
    "mind",
    {
        "story": {
            "on": True,  # one autobiography every part of Kurooto reads first (a fixed core, then its recent weeks)
            "tokens": 800,  # the self-summary is at most this many tokens (about 4 characters each)
        }
    },
)

DIR = "mind-story"
HERE = Path(__file__).resolve().parent
CHAPTERS = 8  # the last this-many week chapters go into the summary
PER_WEEK = 8  # the lines a chapter keeps
CHARS_PER_TOKEN = 4
# which kinds matter most when a week has more than PER_WEEK facts
PRIORITY = ("promise_broken", "wrong_read", "failure", "act", "undo", "swing", "feeling", "proposal")


# ---------------------------------------------------------------------------------------------------- the fixed core
def core_path() -> Path:
    return HERE / "core_signed.md"


def core_ok() -> bool:
    """Does the core still hash to the value signed for it?"""
    try:
        want = (HERE / "core_signed.sig").read_text(encoding="utf-8").strip()
        return hashlib.sha256(core_path().read_bytes()).hexdigest() == want
    except OSError:
        return False


_told: set[str] = set()


def core_text(app: App | None = None) -> str:
    """The core, verbatim, or "" when it doesn't verify (then the story isn't loaded and you're told once)."""
    if core_ok():
        return core_path().read_text(encoding="utf-8").strip()
    if app is not None and "core" not in _told:
        _told.add("core")
        app.events.emit("story_core_tampered")
        app.notify(
            "My fixed core text doesn't match its signature, so I'm not loading my story until it does.",
            kind="info",
            why="mind.story_core",
        )
    return ""


# -------------------------------------------------------------------------------------------------------- chapters
def folder(app: App) -> Path:
    d = app.paths.state / DIR / "weeks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def week_of(day: dt.date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def _days(week: str) -> list[dt.date]:
    y, w = week.split("-W")
    mon = dt.date.fromisocalendar(int(y), int(w), 1)
    return [mon + dt.timedelta(days=i) for i in range(7)]


def write_week(app: App, week: str | None = None) -> dict | None:
    """Roll the week's journals up into its chapter: the most telling lines, each re-checked from its fact."""
    if not mind.part_on(app, "story"):
        return None
    week = week or week_of(now().date() - dt.timedelta(days=1 if now().weekday() == 0 else 0))
    exist = {r.seq for r in mind.connect(app).log(0, None, 5000)}
    lines: list[dict] = []
    for day in _days(week):
        e = journal.read_day(app, day)
        for ln in (e or {}).get("lines", []):
            if ln.get("struck") or "fact" not in ln:
                continue
            f = journal.fact_of(ln["fact"])
            if journal.check(f, ln["text"], exist):
                continue  # re-checked from its fact: a line that fails isn't carried in
            lines.append({k: ln[k] for k in ("text", "seqs", "kind", "about_him", "day")} | {"struck": False})
    order = {k: i for i, k in enumerate(PRIORITY)}
    lines.sort(key=lambda ln: (order.get(ln["kind"], 99), ln["day"]))
    chapter = {"week": week, "lines": sorted(lines[:PER_WEEK], key=lambda ln: ln["day"]), "quoted": []}
    old = jload(folder(app) / f"{week}.json", None)
    if old:  # quoted data and strikes made since carry on
        chapter["quoted"] = old.get("quoted", [])
    jsave(folder(app) / f"{week}.json", chapter)
    (folder(app) / f"{week}.md").write_text(render(chapter), encoding="utf-8")
    return chapter


def render(ch: dict) -> str:
    rows = [f"# Week {ch['week']}", ""]
    for i, ln in enumerate(ch["lines"], 1):
        cite = ", ".join(f"#{s}" for s in ln["seqs"])
        rows.append(f"{i}. ~~{ln['text']}~~ (struck)" if ln.get("struck") else f"{i}. {ln['text']} [{cite}]")
    for q in ch.get("quoted", []):
        rows.append(f"- (quoted from {q['source']}, not my belief) “{q['text']}”")
    return "\n".join(rows) + "\n"


def chapters(app: App) -> list[dict]:
    out = []
    for f in sorted(folder(app).glob("*.json"))[-CHAPTERS:]:
        d = jload(f, None)
        if isinstance(d, dict):
            out.append(d)
    return out


# ---------------------------------------------------------------------------------------- ingested text, only quoted
def quote(source: str, text: str, limit: int = 160) -> str:
    """Anything it read elsewhere, as a quoted datum with its source: the only way it enters the story."""
    clean = " ".join(str(text).split())[:limit].replace("“", "'").replace("”", "'")
    return f"(quoted from {str(source)[:60]}, not my belief) “{clean}”"


def add_quoted(app: App, source: str, text: str, day: dt.date | None = None) -> None:
    week = week_of(day or now().date())
    ch = jload(folder(app) / f"{week}.json", None) or {"week": week, "lines": [], "quoted": []}
    ch["quoted"] = [*ch.get("quoted", []), {"source": str(source)[:60], "text": " ".join(str(text).split())[:160]}][
        -10:
    ]
    jsave(folder(app) / f"{week}.json", ch)
    (folder(app) / f"{week}.md").write_text(render(ch), encoding="utf-8")


# ----------------------------------------------------------------------------------------------------- the summary
def summary(app: App) -> str:
    """The core, then what it has lived lately (newest first, each line with its log records), then anything quoted, all
    within `mind.story.tokens`. "" when the story is off or the core doesn't verify."""
    if not mind.part_on(app, "story"):
        return ""
    core = core_text(app)
    if not core:
        return ""
    cap = int(app.settings.get("mind.story.tokens") or 800) * CHARS_PER_TOKEN
    out = [core]
    used = len(core)
    lived: list[str] = []
    for ch in reversed(chapters(app)):
        for ln in reversed(ch["lines"]):
            if ln.get("struck"):
                continue
            if ln.get("day") and forgetting.is_old_miss(
                app, ln["text"], dt.datetime.fromisoformat(ln["day"]).timestamp()
            ):
                continue  # a miss from long ago stays in the chapter (and the journal), but isn't repeated
            row = f"- {ln['text']} [{', '.join('#' + str(s) for s in ln['seqs'])}]"
            if used + len(row) + 40 > cap:
                break
            lived.append(row)
            used += len(row)
    if lived:
        out += ["", "What I've lived lately (each line cites my own log):", *lived]
    quoted = [q for ch in chapters(app) for q in ch.get("quoted", [])][-3:]
    for q in quoted:
        row = f"- {quote(q['source'], q['text'])}"
        if used + len(row) <= cap:
            out.append(row)
            used += len(row)
    return "\n".join(out)


def rebuild(app: App, payload: dict | None = None) -> str | None:
    """Nightly: the summary file, and what changed in it since last night (the diff `/story` can show)."""
    if not mind.part_on(app, "story"):
        return None
    new = summary(app)
    f = app.paths.state / DIR / "summary.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    old = f.read_text(encoding="utf-8") if f.exists() else ""
    if new:
        f.write_text(new, encoding="utf-8")
        (app.paths.state / DIR / "summary.prev.md").write_text(old, encoding="utf-8")
    return new


def prompt(app: App) -> str:
    """In front of every AI request and every call: "" with Brain or the story off, or the core not verifying."""
    s = summary(app)
    return f"Who you are, and what you've lived lately:\n{s}" if s else ""


def diff(app: App) -> list[str]:
    """The lines of the summary that are new since the night before."""
    cur = app.paths.state / DIR / "summary.md"
    prev = app.paths.state / DIR / "summary.prev.md"
    if not cur.exists():
        return []
    before = set(prev.read_text(encoding="utf-8").splitlines()) if prev.exists() else set()
    return [ln for ln in cur.read_text(encoding="utf-8").splitlines() if ln and ln not in before]


# ------------------------------------------------------------------------------------------------- strike and forget
def strike(app: App, week: str, n: int) -> str:
    f = folder(app) / f"{week}.json"
    ch = jload(f, None)
    if not ch or not 1 <= n <= len(ch["lines"]):
        return "No such line."
    ch["lines"][n - 1]["struck"] = True
    jsave(f, ch)
    (folder(app) / f"{week}.md").write_text(render(ch), encoding="utf-8")
    rebuild(app)
    return f"Struck line {n} of {week}."


def forget_day(app: App, day: str) -> int:
    """The read's forget cascade (stage 04): lines about you from that day leave the chapters and the summary. Lines
    about
    Kurooto's own acts stay. How many went."""
    n = 0
    for f in folder(app).glob("*.json"):
        ch = jload(f, None)
        if not isinstance(ch, dict):
            continue
        keep = [ln for ln in ch["lines"] if not (ln.get("about_him") and ln.get("day") == day)]
        if len(keep) != len(ch["lines"]):
            n += len(ch["lines"]) - len(keep)
            ch["lines"] = keep
            jsave(f, ch)
            f.with_suffix(".md").write_text(render(ch), encoding="utf-8")
    if n:
        rebuild(app)
    return n


def expire(app: App, days: int = 30) -> int:
    """Lines about you older than the mood store's 30 days leave, as the read's own numbers do."""
    cut = (now().date() - dt.timedelta(days=days)).isoformat()
    n = 0
    for f in folder(app).glob("*.json"):
        ch = jload(f, None)
        if not isinstance(ch, dict):
            continue
        keep = [ln for ln in ch["lines"] if not (ln.get("about_him") and str(ln.get("day", "9999")) < cut)]
        if len(keep) != len(ch["lines"]):
            n += len(ch["lines"]) - len(keep)
            ch["lines"] = keep
            jsave(f, ch)
            f.with_suffix(".md").write_text(render(ch), encoding="utf-8")
    return n


def status(app: App) -> str:
    if not mind.on(app):
        return "Brain is off (Features → Brain)."
    if not mind.part_on(app, "story"):
        return "The life story is off (mind.story.on)."
    s = rebuild(app) or summary(app)
    if not s:
        return "My story isn't loaded: my fixed core doesn't match its signature."
    d = diff(app)
    tail = ("\n\nNew since last night:\n" + "\n".join(d[:8])) if d else ""
    return s + tail
