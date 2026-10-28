"""After every call, a second look: a stronger AI request reads the transcript and the tools the call used, does what
was asked but slipped through (misheard, forgotten, a tool that failed), and writes down how calls could go better.

    review(calls, lines, tools, purpose)   queue the look (calls.review on, and a call that said something)
    lessons(app) -> list[str]              what calls have learned, newest last; config_template tells every call
    reviewed(...)                          the request's follow-up: keep its lessons, tell you in one message

Safe things it does by itself (a reminder, a note, a deadline, a journal line), like any request of yours; anything that
sends, calls or spends it only lists. The lessons are a plain file you can read and edit (/lessons; /lessons forget 2),
at most calls.lessons_max of them: a new one that says the same as an old one replaces it.

(0.9.0, calls.lessons_everywhere) Each lesson is also copied as a dated line under "Learned on calls" in the
how-to-help-me note (modules/remember.py LEARNED_CALLS), so every AI request follows it; lessons.md stays the call's
source. A lesson replaced, dropped past the cap or forgotten with /lessons takes its own line out too (only a line
still as Kurooto wrote it). The note's 90-day "Still true?" asks about these lines like the others; Forget there takes
the line out of the note only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now

if TYPE_CHECKING:
    from kurooto.app import App

MIN_LINES = 4  # a call that only rang and hung up has nothing to learn from
FENCE = re.compile(r"```lessons\s*\n(.*?)```", re.S | re.I)


def lessons_file(app: App) -> Path:
    return app.paths.state / "calls" / "lessons.md"


def lessons(app: App) -> list[str]:
    f = lessons_file(app)
    if not f.is_file():
        return []
    return [
        ln[2:].strip() for ln in f.read_text(encoding="utf-8", errors="replace").splitlines() if ln.startswith("- ")
    ]


def save_lessons(app: App, items: list[str]) -> None:
    f = lessons_file(app)
    f.parent.mkdir(parents=True, exist_ok=True)
    head = "# What calls have learned\n\nEvery call is told these. Edit or delete lines freely.\n\n"
    f.write_text(head + "".join(f"- {x}\n" for x in items), encoding="utf-8")


def everywhere(app: App, before: list[str], after: list[str]) -> int:
    """(calls.lessons_everywhere) Keep the note's "Learned on calls" lines in step with lessons.md: a lesson that's gone
    takes its line out, a new one is added with today's date (Remember's rules: never health, money or passwords).
    How many lines were added."""
    if not app.settings.get("calls.lessons_everywhere"):
        return 0
    from kurooto.modules import remember

    gone = {remember.fact_key(x.rstrip(".")) for x in before if x not in after}
    if gone:
        for rec in remember.kept_lines(app):
            if rec["section"] == remember.LEARNED_CALLS and rec["key"] in gone:
                remember.remove_line(app, rec["line"])
    added = 0
    for x in after:
        if x not in before:
            added += remember.keep(app, x, via="call", section=remember.LEARNED_CALLS)[0] == "kept"
    return added


def _key(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", s.lower())}


def merge(old: list[str], new: list[str], cap: int) -> list[str]:
    """New lessons go last; one that shares most of its words with an old one replaces it; the oldest drop past cap."""
    out = list(old)
    for n in new:
        n = " ".join(n.split())[:300]
        if not n:
            continue
        kn = _key(n)
        same = [o for o in out if kn and len(kn & _key(o)) >= 0.6 * min(len(kn), len(_key(o)) or 1)]
        out = [o for o in out if o not in same] + [n]
    return out[-cap:] if cap > 0 else []


def review(calls, lines: list[dict], tools: list[dict], purpose: str = "") -> str | None:
    app = calls.app
    if not calls.setting("review") or len(lines) < MIN_LINES or not app.settings.get("brain.main"):
        return None
    name = app.name
    said = "".join(f"{x.get('who', '?')}: {x.get('text', '')}\n" for x in lines)[-24000:]
    used = (
        "\n".join(f"- {t['name']}({t['args']}) -> {t['result']}" for t in tools)
        if tools
        else "(none: no tool was used on this call)"
    )
    known = "\n".join(f"- {x}" for x in lessons(app)) or "(none yet)"
    try:  # what's on their lists now, with the ids the tools take
        state = json.dumps(calls.pending(), ensure_ascii=False, default=str)[:6000]
    except Exception:  # a feature's brief failing mustn't stop the look back
        state = "(couldn't be read)"
    prompt = f"""You are reviewing a phone call {name} (the voice assistant) just had with its user, to catch what
slipped through and to make the next calls better. Speech recognition on calls is imperfect: read past garbled words.

Why the call happened: {purpose or "the user called"}
Ended: {now():%Y-%m-%d %H:%M}

The transcript:
{said}
Tools the call used, with what they returned:
{used}

Their lists right now, with ids (deadlines, reminders, check-ins, calls):
{state}

What calls already know (don't repeat these):
{known}

Do this:
1. Go through every change the user asked for on the call, one by one: something done or submitted, cancelled or not
   happening, moved to a new date, added, renamed, a reminder or call set or changed. For each, check the tool log
   above: did the right tool run, on the right item, and did it answer that it worked? The list right now shows the
   result. Calls often say "done" when no tool ran, or use the wrong tool: ignore_topic or remember for "I don't have
   that quiz" (that's remove_deadline), remember for "I have a quiz on Thursday" (that's add_deadline, or the existing
   one is right). Fix each one now with the right tool (mark_deadline_done, remove_deadline, move_deadline,
   add_deadline, reminders, unignore_topic to undo a wrong ignore_topic). Also do anything else they asked for that
   slipped through (a reminder, a note, a journal line, an answer they wanted). Anything that sends a message, places a
   call or spends: don't do it, list it.
2. Think about how the call itself could have gone better (it misunderstood something, asked too much, missed a cue,
   talked too long, used the wrong tool). Write 0 to 3 lessons: short, general instructions for future calls, in the
   imperative ("When they say 'after class', ask when class ends before setting the reminder."). No names or details
   of other people, nothing secret, nothing true only of this one call. None is fine when the call went well.

Answer in this shape, briefly:
First line: one sentence for the user on what you fixed, or "Nothing slipped through."
Then, if any: "Needs you:" and what you listed in step 1.
Last, always:
```lessons
- a lesson
```
(an empty block when there's nothing to learn)."""
    return app.jobs.submit(
        prompt,
        title="Call review",
        effort=str(calls.setting("review_effort") or "high"),
        quiet=True,
        then="calls.reviewed",
        lane="bg",
        why="calls.review",
        brain=str(calls.setting("review_brain") or "") or None,
    )


def reviewed(calls, job, result, payload: dict) -> None:
    app = calls.app
    if not result.ok:
        app.events.emit("call_review_failed", verdict=str(getattr(result, "verdict", ""))[:20])
        return
    text = str(result.text or "").strip()
    m = FENCE.search(text)
    new = [ln.strip()[2:].strip() for ln in (m.group(1) if m else "").splitlines() if ln.strip().startswith("- ")]
    body = FENCE.sub("", text).strip()
    if new:
        before = lessons(app)
        after = merge(before, new, int(calls.setting("lessons_max") or 12))
        save_lessons(app, after)
        try:  # the copy in how-to-help-me never stands in the way of the lessons themselves
            everywhere(app, before, after)
        except Exception as e:
            app.events.emit("call_lessons_copy_failed", error=type(e).__name__)
    app.events.emit("call_reviewed", lessons=len(new))
    quiet = not new and (not body or body.lower().startswith("nothing slipped"))
    if quiet:
        return  # nothing fixed, nothing learned: no message
    parts = [f"After the call: {body}" if body else "After the call:"]
    if new:
        parts.append("Learned for next time:\n" + "\n".join(f"- {x}" for x in new) + "\n(/lessons to see or remove)")
    app.notify("\n\n".join(parts), kind="info", why="calls.review")


def command(app: App, arg: str) -> str:
    """/lessons: what calls have learned; /lessons forget 2 removes one; /lessons clear removes all."""
    items = lessons(app)
    m = re.fullmatch(r"(?:forget|remove|drop)\s+(\d+)", arg.strip(), re.I)
    if m:
        i = int(m.group(1))
        if not 1 <= i <= len(items):
            return f"There's no lesson {i}." if items else "Calls haven't learned anything yet."
        before = list(items)
        gone = items.pop(i - 1)
        save_lessons(app, items)
        everywhere(app, before, items)
        return f"Forgot: {gone}"
    if arg.strip().lower() == "clear":
        save_lessons(app, [])
        everywhere(app, items, [])
        return "Forgot every lesson."
    if not items:
        return "Calls haven't learned anything yet. After each call Kurooto looks back and keeps what would help."
    return (
        "What calls have learned:\n"
        + "\n".join(f"{i}. {x}" for i, x in enumerate(items, 1))
        + "\n\n/lessons forget 2 removes one; /lessons clear removes them all."
    )
