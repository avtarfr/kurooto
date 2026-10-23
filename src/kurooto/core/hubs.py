"""The hub notes that keep your notes from being separate islands: a home note (maps/index.md, or index.md in the plain
layout) that lists the research hub and every course, a research hub that exists from the start (with what you work on,
if you said), and a one-line link from each course page back to both. Only lines are added: nothing you wrote is
changed, and a line that's already there isn't added twice.

Run after Classroom files new items and after a book is read (the places new notes appear), never at start-up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto.core import layout

if TYPE_CHECKING:
    from kurooto.app import App

HOME = """# Home

Where everything starts: your hubs and your courses. {name} keeps the lists below up to date; write your own text
anywhere, it's never changed.

## Hubs

## Courses
"""
BACK = "<!-- kurooto:hubs -->\nHome: {home} · Research: {research}"


def _subjects(app: App) -> list[tuple[str, str]]:
    subj = app.modules.get("subjects")
    if subj is None or not app.is_on("subjects"):
        return []
    return [(s["slug"], s["name"]) for s in subj.subjects()]


def ensure(app: App) -> list[str]:
    """Make the hubs and link the courses to them. Returns what it did (for the event log)."""
    from kurooto.core.tools import add_to_section
    from kurooto.modules import research

    lay = layout.of(app)
    did: list[str] = []
    about = (app.settings.get("research.about") or "").strip()
    had_research = lay.path("research").exists()
    research.ensure_hub(lay, app.name, about)
    if not had_research:
        did.append("research hub")
    home = lay.path("home")
    if not home.exists():
        home.parent.mkdir(parents=True, exist_ok=True)
        home.write_text(
            lay.frontmatter("home", home, title="Home", bare=True) + HOME.format(name=app.name),
            encoding="utf-8",
        )
        did.append("home note")
    text = home.read_text(encoding="utf-8")
    have = set(lay.note_targets(text, home))  # what the home note links already, in either link style
    lines = []
    research_t, home_t = lay.link("research"), lay.link("home")
    if research_t not in have:
        lines.append(("Hubs", f"- {lay.note_link(research_t, 'Research', from_note=home)}"))
    for slug, name in _subjects(app):
        course = lay.path("course", subject=slug)
        if not course.is_file():
            continue
        target = lay.link("course", subject=slug)
        if target not in have:
            lines.append(("Courses", f"- {lay.note_link(target, name, from_note=home)}"))
        ctext = course.read_text(encoding="utf-8", errors="replace")
        if "kurooto:hubs" not in ctext and home_t not in lay.note_targets(ctext, course):
            back = BACK.format(
                home=lay.note_link(home_t, "Home", from_note=course),
                research=lay.note_link(research_t, "Research", from_note=course),
            )
            course.write_text(ctext.rstrip("\n") + "\n\n" + back + "\n", encoding="utf-8")
            did.append(f"{slug} course page")
    for section, line in lines:
        text = add_to_section(text, section, line)
        did.append(line)
    if lines:
        home.write_text(text, encoding="utf-8")
    if did:
        app.events.emit("hubs_updated", did=len(did))
    return did
