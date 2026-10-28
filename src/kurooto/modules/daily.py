"""The day's note and the AI work around it, shared by check-ins, the alarm, the Sunday review, the study tracker and
after-class notes.

Your daily note is journal/<YYYY-MM-DD>.md in your notes folder (or where your notes layout keeps it,
core/layout.py). Kurooto only ever adds to it: a new section at the end
("## Study hours", "## Evening check-in"), never changing what's there. The plan for the day is the newest "## Plan…"
section (the draft written before your alarm, or the one you settled on the morning call).

Work for the AI goes through a skill (journal, study-log, morning-prep, morning): the AI follows the skill's steps, your
own copy of the skill if you made one. With Chat off there's no AI, so callers keep your own words instead.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import layout
from kurooto.core.clock import now

if TYPE_CHECKING:
    from kurooto.app import App


def note_path(app: App, day: dt.date | None = None) -> Path:
    return layout.path(app, "daily", date=(day or now().date()).isoformat())


def append(app: App, heading: str, body: str, day: dt.date | None = None) -> Path:
    """Add "## heading" with body at the end of the day's note (made if missing); what's there stays as it is."""
    day = day or now().date()
    f = note_path(app, day)
    f.parent.mkdir(parents=True, exist_ok=True)
    new = not f.exists()
    with open(f, "a", encoding="utf-8") as out:
        if new:
            out.write(layout.frontmatter(app, "daily", f, agent=False, bare=True) + f"# {day.isoformat()}\n")
        out.write(f"\n## {heading}\n\n{body.strip()}\n")
    from kurooto.core import infer  # a journal line can set something up ("I got a project under Prof X")

    infer.observe(app, body, via="journal")
    return f


def sections(text: str, prefix: str) -> list[str]:
    """Every "## <prefix>…" section of a note (heading line included), in order."""
    out = []
    for m in re.finditer(rf"^##\s+{re.escape(prefix)}\b.*$", text, re.M | re.I):
        nxt = re.compile(r"^#{1,2}\s", re.M).search(text, m.end())
        out.append(text[m.start() : nxt.start() if nxt else len(text)].strip())
    return out


def has_section(app: App, prefix: str, day: dt.date | None = None) -> bool:
    f = note_path(app, day)
    return f.is_file() and bool(sections(f.read_text(encoding="utf-8", errors="replace"), prefix))


def plan(app: App, day: dt.date | None = None, limit: int = 4000) -> str:
    """The day's plan: the newest "## Plan…" section of its daily note, or "" if there isn't one."""
    f = note_path(app, day)
    if not f.is_file():
        return ""
    found = sections(f.read_text(encoding="utf-8", errors="replace"), "Plan")
    return found[-1][:limit] if found else ""


def mark_plan_stale(app: App, what: str) -> None:
    """(0.9.0) Something changed the day after its plan was drafted (a call moved a deadline, skipped a class): kept
    for today in state (never written into the note), so Today and the dashboard can say so."""
    from kurooto.core.state import jload, jsave

    f = app.paths.state / "daily" / "plan-stale.json"
    today = now().date().isoformat()
    st = jload(f, {}) or {}
    items = st.get("what", []) if st.get("date") == today else []
    if what not in items:
        items = [*items, what][-6:]
    f.parent.mkdir(parents=True, exist_ok=True)
    jsave(f, {"date": today, "what": items, "at": now().isoformat(timespec="minutes")})


def plan_stale(app: App, day: dt.date | None = None) -> str:
    """What changed today since the plan was drafted ("a deadline moved; a class skipped"), or ""."""
    from kurooto.core.state import jload

    st = jload(app.paths.state / "daily" / "plan-stale.json", {}) or {}
    if st.get("date") != (day or now().date()).isoformat():
        return ""
    return "; ".join(str(x) for x in st.get("what") or [])


def ai_on(app: App) -> bool:
    """Is there an AI to hand work to? (Chat is on.)"""
    return app.is_on("chat")


def run_skill(
    app: App,
    name: str,
    args: str = "",
    *,
    title: str | None = None,
    files: list[Path] | None = None,
    quiet: bool = False,
    then: str | None = None,
    then_payload: dict | None = None,
    background: bool = False,
    reply_to=None,
    lane: str | None = None,
) -> str | None:
    """Hand work to the AI through a skill (your copy of it, or the shipped one). Returns the job id, or None when
    there's no AI (Chat is off) or no such skill."""
    if not ai_on(app):
        return None
    from kurooto.modules.skills import skill_prompt

    sk = app.modules.get("skills")
    if sk is not None and app.is_on("skills"):
        try:
            return sk.run(
                name,
                args=args,
                reply_to=reply_to,
                then=then,
                then_payload=then_payload,
                quiet=quiet,
                background=background,
                files=files,
                title=title,
                lane=lane,
            )
        except KeyError:
            return None
    prompt = skill_prompt(app, name, args, files or ())  # works with the Skills feature off
    if not prompt:
        return None
    return app.jobs.submit(
        prompt,
        title=title or name,
        reply_to=reply_to,
        quiet=quiet,
        then=then,
        then_payload=then_payload,
        background=background,
        lane=lane,
    )


def their_words(app: App, lines: list[dict]) -> str:
    """Your side of a call transcript, one line per turn."""
    ai = app.name
    return "\n".join(x.get("text", "").strip() for x in lines if x.get("who") != ai and x.get("text", "").strip())


def transcript(app: App, lines: list[dict], limit: int = 30000) -> str:
    """Both sides of a call, "Name: what they said" per turn (for the AI, which needs the questions too)."""
    you = app.settings.get("you.name") or "Me"
    ai = app.name
    out = "\n".join(
        f"{ai if x.get('who') == ai else you}: {x.get('text', '').strip()}" for x in lines if x.get("text", "").strip()
    )
    return out[-limit:]


def morning_view(app: App) -> dict:
    """What the morning page shows: today's plan, classes, calendar, check-ins, the alarm, what's due, study so far."""
    today = now().date()
    out: dict = {
        "date": today.isoformat(),
        "day": f"{today:%A %d %B}",
        "name": app.settings.get("you.name") or "",
        "plan": plan(app, today, 8000),
        "note": layout.link(app, "daily", date=today.isoformat()),
        "note_exists": note_path(app, today).is_file(),
    }

    def part(key: str, fn) -> None:
        try:
            value = fn()
        except Exception as e:  # one feature's trouble never blanks the page
            app.events.emit("morning_view_failed", part=key, error=str(e)[:200])
            return
        if value:
            out[key] = value

    if app.is_on("subjects"):
        subj = app.modules["subjects"]
        part(
            "classes",
            lambda: [
                {"time": f"{c['start']}–{c['end']}", "name": c["name"], "skipping": c["subject"] in subj.skipped()}
                for c in subj.classes_on(include_skipped=True)
            ],
        )
    if app.is_on("calendar"):
        part("calendar", lambda: app.modules["calendar"].call_brief().get("calendar_today"))
    if app.is_on("checkins"):
        part(
            "checkins",
            lambda: [
                {"name": n, "time": c.get("time") or "", "status": c.get("status", "")}
                for n, c in app.modules["checkins"].today().items()
            ],
        )
    if app.is_on("alarm"):
        part("alarm", lambda: (lambda at: f"{at:%a %H:%M}" if at else "")(app.modules["alarm"].next()))
    dl = app.modules.get("deadlines")
    if dl is not None and app.is_on("deadlines") and hasattr(dl, "deadlines_soon"):
        from kurooto.modules.deadlines import due_day

        part(
            "due",
            lambda: [
                {"title": f"{d['title']} {d['parts']}", "when": f"due {due_day(d['due'])}"}  # "ps3 4/7", "due Fri"
                if d.get("parts")
                else {"title": d.get("title", ""), "when": d.get("when") or d.get("due", "")}
                for d in dl.deadlines_soon()  # deadlines.plan_h ahead
            ],
        )
    sb = app.modules.get("startby")
    if sb is not None and app.is_on("startby"):
        part("start", sb.morning_rows)  # start-by dates that have come (modules/startby.py)
    if app.is_on("study"):
        part("study_h", lambda: round(sum(app.modules["study"].totals(1).values()) / 3600, 1))
    part("questions", lambda: [q["text"][:200] for q in app.ask.pending()[:5]])
    part("plan_stale", lambda: plan_stale(app, today) if out.get("plan") else "")  # (0.9.0) changed since drafted
    return out
