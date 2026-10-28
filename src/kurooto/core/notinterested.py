"""Not interested: topics you don't care about (a club, a kind of event, a course you dropped). They're kept in your
notes at about-me/not-interested.md (or where your notes layout keeps it), one per line ("- drama club", or "- drama
club — not this term"), so you can edit the list like any note. The deadline radar leaves matching deadlines out, and
the mail and Classroom digests only count matching items instead of making tasks from them.

Other features use it like this (it works whether or not Deadlines is on):

    from kurooto.core.notinterested import ignored_topics, is_ignored
    is_ignored(app, "Drama club auditions on Friday")  # -> "drama club" (the matching topic) or None

Matching is case-insensitive, on whole words or phrases.

(0.9.0) notinterested.tell_ai (on): every AI request, call and desk talk is told the topics (providers/context.py), so
it doesn't bring them up on its own. notinterested.filter.<reader> (each off): that reader puts a matching item last
and tags it "you said not interested in X" (tag()), never hiding it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from kurooto.core import layout
from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from pathlib import Path

    from kurooto.app import App

register_defaults(
    "notinterested",
    {
        "tell_ai": True,  # every AI request, call and desk talk is told your not-interested topics (just the topics)
        # (0.9.0) more readers that use the list: each puts a matching item last and tags it, never hides it; each off
        "filter": {
            "research": False,  # new-paper digests: papers about a topic you skip go last, tagged
            "integrate": False,  # the concept graph's reading queue: class material about one is read last
            "quiz_links": False,  # link cards about one come after the others, tagged
            "retro": False,  # the nightly look back's ideas about one are offered last, tagged
            "frontier": False,  # Dreaming's frontier cards about one are made last, tagged; frontier scores halved
        },
    },
)

NOTE = "about-me/not-interested.md"  # in the default notes layout; note_file() is where it is
TELL_MAX = 30  # the most topics an AI is told (the first ones on the list)
LINE = re.compile(r"^\s*[-*]\s+(?!\[[ xX]\])(.+?)\s*$")
WHY = re.compile(r"\s+(?:—|–|--|-)\s+.*$")


def note_file(app: App) -> Path:
    return layout.path(app, "not_interested")


def rel(app: App) -> str:
    """The note's place in your notes, for messages ("about-me/not-interested.md")."""
    return layout.rel(app, "not_interested")


def _topic(line: str) -> str | None:
    m = LINE.match(line)
    if not m:
        return None
    t = WHY.sub("", m[1]).strip().strip("`*_\"'").strip()
    return t or None


def ignored_topics(app: App) -> list[str]:
    """The topics on the list, in the order written."""
    try:
        text = note_file(app).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[str] = []
    for ln in text.splitlines():
        t = _topic(ln)
        if t and t.lower() not in (x.lower() for x in out):
            out.append(t)
    return out


def matcher(app: App) -> Callable[[str], str | None]:
    """A fast check for many texts at once (reads the list once)."""
    pats = [(t, re.compile(r"(?<![a-z0-9])" + re.escape(t.lower()) + r"(?![a-z0-9])")) for t in ignored_topics(app)]

    def match(text: str) -> str | None:
        low = (text or "").lower()
        return next((t for t, p in pats if p.search(low)), None)

    return match


def is_ignored(app: App, text: str) -> str | None:
    """The topic on your not-interested list that this text is about, or None."""
    return matcher(app)(text)


def filter_on(app: App, reader: str) -> bool:
    """Is notinterested.filter.<reader> on?"""
    return bool(app.settings.get(f"notinterested.filter.{reader}"))


def tag(topic: str) -> str:
    """The words a demoted item carries."""
    return f"you said not interested in {topic}"


def demote(
    app: App,
    reader: str,
    items: list,
    text_of: Callable[[Any], str],
    tagged: Callable[[Any, str], Any] | None = None,
) -> list:
    """(0.9.0, notinterested.filter.<reader>) The same items with those about a not-interested topic moved last, in
    their order, each passed through tagged(item, tag(topic)) when given. Nothing is dropped. The list as it was with
    the switch off or no topics."""
    if not items or not filter_on(app, reader):
        return items
    match = matcher(app)
    keep, last = [], []
    for it in items:
        try:
            t = match(text_of(it) or "")
        except Exception:
            t = None
        if t:
            last.append(tagged(it, tag(t)) if tagged else it)
        else:
            keep.append(it)
    if last:
        app.events.emit("ignore_demoted", reader=reader, n=len(last))
    return keep + last


def add_topic(app: App, topic: str, why: str = "") -> bool:
    """Add a topic at the end of the list (the note is made if it doesn't exist). False if it's already there."""
    topic = re.sub(r"\s+", " ", topic).strip().strip(".!,;:\"'")
    if not topic or topic.lower() in (t.lower() for t in ignored_topics(app)):
        return False
    f = note_file(app)
    f.parent.mkdir(parents=True, exist_ok=True)
    old = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""
    line = f"- {topic}" + (f" — {why.strip()}" if why.strip() else "")
    if old.strip():
        text = old.rstrip("\n") + "\n" + line + "\n"
    else:
        text = (
            layout.frontmatter(app, "not_interested", f, title="Not interested") + "# Not interested\n\n"
            f"Topics I don't care about. {app.name} leaves matching deadlines out, and the mail and Classroom digests "
            f"only count matching items. One per line; edit freely.\n\n{line}\n"
        )
    f.write_text(text, encoding="utf-8")
    app.events.emit("ignore_added", chars=len(topic))
    return True


def remove_topic(app: App, topic: str) -> bool:
    """Take a topic off the list (only its own line goes; the rest of the note stays as it is)."""
    f = note_file(app)
    key = topic.strip().lower()
    try:
        lines = f.read_text(encoding="utf-8", errors="replace").split("\n")
    except OSError:
        return False
    keep = [ln for ln in lines if (_topic(ln) or "").lower() != key]
    if len(keep) == len(lines):
        return False
    f.write_text("\n".join(keep), encoding="utf-8")
    app.events.emit("ignore_removed")
    return True
