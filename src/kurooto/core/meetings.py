"""Meetings with someone: a project note's "With: X (role)" person (their role in your own word: supervisor, guide,
manager, coach), met once ("a meeting with X on Friday at 4" becomes a "Meeting: X" deadline, core/infer.py) or every
week ("I meet my manager Priya Rao every Monday at 10" puts "Meets: every Mon 10:00" in the project note).

    the evening before   a brief from the project note (modules/deadlines.py:meeting_briefs, infer.brief)
    after it             a voice note, or a typed note of 20 words or more, sent within meetings.after_h hours of its
                         start (and not a request something else answers), or a message that starts "about the meeting
                         with X:", becomes minutes in the project note through your AI (one request), in Kurooto's block
                         for that day. [Not about the meeting] takes them out and sends the message to your AI as usual.
    action items         the minutes' action items go under "## Next steps" and come back as buttons: each becomes a
                         deadline only when you tap it; None; Later (they come back the next evening).

The note's "With:", "Meets:" and "Last met:" lines live in Kurooto's block (<!-- kurooto:meeting -->) and its action
items in another under "## Next steps" (<!-- kurooto:next-steps -->). Only those blocks and the minutes' own blocks are
rewritten; what you wrote is never changed (lines and headings may be added). A note from before 0.5.20 keeps its own
"With:" and "Last met:" lines; the newest "Last met" date anywhere in the note counts.
"""

from __future__ import annotations

import datetime as dt
import re
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.base import Incoming

register_defaults(
    "meetings",
    {
        "minutes": True,  # notes you send after a meeting with a project's person become minutes through your AI
        "after_h": 3,  # hours after a meeting's start that a voice note or a long typed note counts as notes from it
    },
)

FILE = "meetings.json"
KEEP = 60  # minutes requests and offers remembered (for the buttons)
TEXT_DAYS = (
    2  # the words you sent are kept this long (for Not about the meeting); the AI request's own copy is jobs.db's
)
BLOCK = "meeting"  # With:, Meets:, Last met:
STEPS = "next-steps"  # the minutes' action items, under ## Next steps
BUTTONS = 4  # action items offered as buttons at once (the phone app's chat shows six buttons: these, None, Later)
MIN_WORDS = 20  # a typed message this long, sent after a meeting, is taken as notes from it (a voice note: 8)
LAST_MET_ANY = re.compile(r"(?m)^Last met:\s*(\d{4}-\d{2}-\d{2})\s*$")
MEETS = re.compile(r"(?m)^Meets:\s*every\s+(?P<days>.+?)\s+(?P<t>\d{1,2}:\d{2})\s*$")
EXPLICIT = re.compile(  # at the start, then a colon or a dash: "about the meeting with Okafor: ...", "Notes from
    # today's meeting - ...". "Remind me about the meeting with Okafor at 4" isn't one.
    r"(?i)^\s*(?:(?:my\s+|some\s+)?(?:notes|minutes)\s+)?(?:about|from|for|on|of|re)\s+(?:the|my|our|today'?s|"
    r"this morning'?s|this afternoon'?s|yesterday'?s|tonight'?s)\s+meeting(?:\s+with\s+(?P<who>[\w.' -]{2,40}?))?"
    r"\s*[:\-–—]"
)
MINUTES_HEAD = re.compile(r"(?im)^\s*(summary|decisions|action items)\s*:\s*$")
BY = re.compile(r"\(\s*by\s+(\d{4}-\d{2}-\d{2})\s*\)")
NONE = re.compile(r"(?i)^\s*(?:none|nothing|n/?a|-)\.?\s*$")

PROMPT = """These are my notes from a meeting with {who} ({role}) on {day} about my project "{project}". Today is \
{today}. Write minutes from them for my project note. Use only what my notes say; add nothing. Plain text, no emojis.
Reply in exactly this form and nothing else:

Summary:
- one line per point discussed
Decisions:
- one line each, or "- none"
Action items:
- one line each: what to do, who does it if it isn't me, and "(by YYYY-MM-DD)" only if a date was said; or "- none"
{earlier}
My notes:
{text}"""


def _block_rx(key: str) -> re.Pattern:
    return re.compile(rf"<!-- kurooto:{re.escape(key)}\b[^>]*-->\n?(.*?)\n?<!-- /kurooto:{re.escape(key)} -->", re.S)


def block_body(text: str, key: str) -> str | None:
    m = _block_rx(key).search(text)
    return m[1].strip("\n") if m else None


def put(text: str, key: str, body: str, at: int | None = None) -> str:
    """The text with Kurooto's `key` block holding `body` (replaced in place; else put at `at`, or the end)."""
    from kurooto.core.graphwrite import block

    new = block(key, body)
    rx = _block_rx(key)
    if rx.search(text):
        return rx.sub(lambda _: new, text, count=1)
    if at is None:
        return text.rstrip("\n") + "\n\n" + new + "\n"
    return text[:at] + new + "\n" + text[at:]


def drop(text: str, key: str) -> str:
    k = re.escape(key)
    return re.sub(rf"<!-- kurooto:{k}\b[^>]*-->.*?<!-- /kurooto:{k} -->\n?", "", text, count=1, flags=re.S)


def outside(text: str) -> str:
    """What's yours in a note: everything but Kurooto's blocks."""
    from kurooto.core.graphwrite import BLOCK_ANY

    return BLOCK_ANY.sub("", text)


# ----------------------------------------------------------------------------- the note's meeting lines
def last_met(text: str) -> str | None:
    """The newest "Last met: <date>" in the note (Kurooto's block, or a line of yours from before 0.5.20)."""
    dates = LAST_MET_ANY.findall(text)
    return max(dates) if dates else None


def schedule(text: str) -> tuple[list[str], str] | None:
    """ "Meets: every Tue, Thu 10:00" -> (["tue", "thu"], "10:00")."""
    from kurooto.modules.commitments import parse_days

    m = MEETS.search(text)
    if not m:
        return None
    days = parse_days(m["days"].replace(",", " "))
    h, mi = (int(x) for x in m["t"].split(":"))
    return (days, f"{h:02d}:{mi:02d}") if days and h < 24 and mi < 60 else None


def meets_text(days: list[str], start: str) -> str:
    from kurooto.modules.commitments import days_text

    return f"every {days_text(days)} {start}"


def set_fields(
    text: str, who: str | None = None, role: str | None = None, meets: str | None = None, met: str | None = None
) -> str:
    """The note with Kurooto's meeting block updated: a "With: <who> (<role>)" line (added when nobody's With line names
    them; its role changed only inside the block), "Meets: <meets>", "Last met: <met>" (only ever moved forward). The
    block is made under the last "With:" line, else under the title."""
    from kurooto.core.infer import WITH_LINE

    body = block_body(text, BLOCK)
    lines = body.split("\n") if body else []
    if who:
        surname = who.split()[-1].lower()
        mine = next((i for i, ln in enumerate(lines) if (m := WITH_LINE.match(ln)) and _same(m["who"], surname)), None)
        theirs = any(_same(m["who"], surname) for m in WITH_LINE.finditer(outside(text)))
        if mine is not None and role:
            lines[mine] = f"With: {WITH_LINE.match(lines[mine])['who']} ({role})"
        elif mine is None and not theirs:
            at = max((i + 1 for i, ln in enumerate(lines) if ln.startswith("With:")), default=0)
            lines.insert(at, f"With: {who} ({role or 'with'})")
    if met and met >= (last_met(text) or ""):
        lines = [ln for ln in lines if not ln.startswith("Last met:")]
        at = max((i + 1 for i, ln in enumerate(lines) if ln.startswith("With:")), default=0)
        lines.insert(at, f"Last met: {met}")
    if meets:
        lines = [ln for ln in lines if not ln.startswith("Meets:")]
        lines.append(f"Meets: {meets}")
    if not lines or "\n".join(lines) == (body or ""):
        return text
    if body is not None:
        return put(text, BLOCK, "\n".join(lines))
    from kurooto.core.graphwrite import block

    new = block(BLOCK, "\n".join(lines))
    w = list(WITH_LINE.finditer(text))
    if w:  # under your last "With:" line (and the "Last met:" under it)
        at = w[-1].start()
        while True:
            end = text.find("\n", at)
            if end < 0:
                return text + "\n" + new + "\n"
            at = end + 1
            if not re.match(r"(?:With|Last met|Meets):", text[at:]):
                return text[:at] + new + "\n" + text[at:]
    h = re.search(r"(?m)^# .*\n", text)
    if h:  # under the title
        return text[: h.end()] + "\n" + new + "\n" + text[h.end() :]
    return new + "\n\n" + text


def _same(who: str, surname: str) -> bool:
    return who.split()[-1].lower() == surname if who.split() else False


# ------------------------------------------------------------------------------------------ when they are
def on_day(app: App, day: dt.date, deadlines: bool = True) -> list[tuple[Path, str, dt.datetime]]:
    """The meetings on a day with someone a project note is With: its "Meets:" schedule, and (deadlines=True) open
    "Meeting: <who>" deadlines. [(note, who, start)], earliest first; one per note and start."""
    from kurooto.core import infer

    people = infer.projects_with(app)
    out: dict[tuple[str, str], tuple[Path, str, dt.datetime]] = {}
    for note in {n for n, _, _ in people}:
        try:
            got = schedule(note.read_text(encoding="utf-8"))
        except OSError:
            continue
        if got and ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[day.weekday()] in got[0]:
            start = dt.datetime.combine(day, dt.time.fromisoformat(got[1]))
            who = next(p for n, p, _ in people if n == note)
            out[(str(note), start.isoformat())] = (note, who, start)
    dl = app.modules.get("deadlines")
    if deadlines and dl is not None and app.is_on("deadlines"):
        for it in dl.items().values():
            if it.get("status") not in ("open", "done") or not it["title"].startswith("Meeting:"):
                continue
            start = dt.datetime.fromisoformat(it["due"]).replace(tzinfo=None)
            who = it["title"].removeprefix("Meeting:").strip()
            hit = next((n for n, p, _ in people if who and _same(p, who.split()[-1].lower())), None)
            if start.date() == day and hit is not None:
                out.setdefault((str(hit), start.isoformat()), (hit, who, start))
    return sorted(out.values(), key=lambda x: x[2])


def recent(app: App, t: dt.datetime | None = None, hours: float | None = None) -> tuple[Path, str, dt.datetime] | None:
    """The meeting that started within the last `hours` (meetings.after_h): (note, who, start), the latest one."""
    t = (t or now()).replace(tzinfo=None)
    hours = float(app.settings.get("meetings.after_h") or 3) if hours is None else hours
    got = [
        m
        for d in (t.date() - dt.timedelta(days=1), t.date())
        for m in on_day(app, d)
        if m[2] <= t <= m[2] + dt.timedelta(hours=hours)
    ]
    return got[-1] if got else None


def next_after(app: App, note: Path, t: dt.datetime) -> dt.datetime | None:
    """The next meeting in this note after `t`, within three weeks."""
    for k in range(1, 22):
        for n, _who, start in on_day(app, t.date() + dt.timedelta(days=k)):
            if n == note:
                return start
    return None


def person(app: App, words: str) -> tuple[Path, str] | None:
    """The project note and person these words name ("Okafor", "my guide", "Priya"): a With line's surname, first name
    or role."""
    from kurooto.core import infer

    low = [w for w in re.findall(r"[a-z][\w'-]*", words.lower()) if w not in ("my", "the", "our", "with")]
    for note, who, role in infer.projects_with(app):
        names = {w.lower().strip(".") for w in who.split()}
        if any(w in names for w in low) or (role.lower() in low and role.lower() != "with"):
            return note, who
    return None


# ---------------------------------------------------------------------------------------------- state
def _load(app: App) -> dict:
    data = jload(Path(app.paths.state) / FILE, {}) or {}
    data.setdefault("minutes", {})
    data.setdefault("briefed", [])
    return data


def _save(app: App, data: dict) -> None:
    if len(data["minutes"]) > KEEP:
        for k in sorted(data["minutes"], key=lambda k: data["minutes"][k].get("at", 0))[: len(data["minutes"]) - KEEP]:
            del data["minutes"][k]
    for r in data["minutes"].values():  # your words only while Not about the meeting may still need them
        if time.time() - float(r.get("at") or 0) > TEXT_DAYS * 86400:
            r.pop("text", None)
    data["briefed"] = data["briefed"][-KEEP:]
    jsave(Path(app.paths.state) / FILE, data)


def briefed(app: App, note: Path, day: dt.date) -> bool:
    """Mark the brief for this note's meeting on that day as sent. False when it was sent already."""
    key = f"{note}|{day.isoformat()}"
    with Lock(app.paths.state, "meetings", timeout=5):
        data = _load(app)
        if key in data["briefed"]:
            return False
        data["briefed"].append(key)
        _save(app, data)
    return True


# -------------------------------------------------------------------------------------- notes -> minutes
def take(app: App, msg: Incoming, text: str, window: bool = False) -> bool:
    """A message that's notes from a meeting: its minutes are on their way (one AI request). One that starts "about
    the meeting with X:" (EXPLICIT) at any time; window=True: a voice note or a long typed note just after a meeting
    (called only for what would otherwise go to the AI). True when it was taken."""
    if not text or text.startswith("/") or msg.files or not app.settings.get("meetings.minutes"):
        return False
    if not app.is_on("chat"):  # minutes are written by your AI
        return False
    hit = None
    m = EXPLICIT.search(text)
    if m:
        said = person(app, m["who"]) if m["who"] else None
        got = recent(app, hours=36)
        if said and got and got[0] == said[0]:
            hit = got
        elif said:
            hit = (said[0], said[1], now().replace(tzinfo=None))
        elif got:
            hit = got
    elif window:
        words = len(text.split())
        if (msg.voice and words >= 8) or (words >= MIN_WORDS and not text.rstrip().endswith("?")):
            hit = recent(app)
    if hit is None:
        return False
    submit(app, msg, text, *hit)
    return True


def submit(app: App, msg: Incoming, text: str, note: Path, who: str, start: dt.datetime) -> str:
    """Ask the AI for minutes from these notes (one request); they go into the note when it answers."""
    from kurooto.core import infer, layout

    body = note.read_text(encoding="utf-8")
    day = start.date().isoformat()
    role = next((r for n, p, r in infer.projects_with(app) if n == note and p == who), "with")
    title = re.search(r"(?m)^# (.+)$", body)
    earlier = block_body(body, f"minutes-{day}")
    prompt = PROMPT.format(
        who=who,
        role=role,
        day=f"{start:%A %d %B %Y}",
        project=title[1].strip() if title else note.parent.name,
        today=f"{now():%A %Y-%m-%d}",
        earlier=f"\nMinutes I have from this meeting already (keep what they say, add the new notes):\n{earlier}\n"
        if earlier
        else "",
        text=text.strip(),
    )
    oid = uuid.uuid4().hex[:8]
    jid = app.jobs.submit(
        prompt,
        title=f"Minutes: meeting with {who}"[:80],
        effort="low",
        quiet=True,
        text_only=True,
        then="meetings.minutes",
        then_payload={"id": oid},
    )
    rec = {
        "note": str(note),
        "who": who,
        "day": day,
        "start": start.isoformat(),
        "text": text.strip(),
        "job": jid,
        "reply_to": msg.message_id,
        "at": time.time(),
        "status": "writing",
    }
    with Lock(app.paths.state, "meetings", timeout=5):
        data = _load(app)
        data["minutes"][oid] = rec
        _save(app, data)
    app.events.emit("meeting_notes", voice=bool(msg.voice), words=len(text.split()))
    msg.reply(
        f"Taking this as your notes from the meeting with {who} ({start:%a %d %b %H:%M}): your AI is writing the "
        f"minutes into {layout.shown(app, note)}.",
        buttons=[[("Not about the meeting", f"mtg:{oid}:not")]],
    )
    return oid


def parse(answer: str) -> tuple[dict[str, list[str]], bool]:
    """The AI's minutes as {"summary": [...], "decisions": [...], "action items": [...]}, and whether they had the
    form asked for."""
    out: dict[str, list[str]] = {"summary": [], "decisions": [], "action items": []}
    cur, seen = None, False
    for ln in (answer or "").splitlines():
        h = MINUTES_HEAD.match(ln)
        if h:
            cur, seen = h[1].lower(), True
            continue
        item = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln).strip()
        if cur and item and not NONE.match(item):
            out[cur].append(item[:300])
    return out, seen and bool(out["summary"] or out["decisions"] or out["action items"])


def minutes_written(app: App, job, result, payload: dict) -> None:
    """The AI's answer (jobs then-action "meetings.minutes"): the minutes into the note, the action items under Next
    steps and offered as buttons. A failed answer keeps your notes as you sent them, so nothing is lost."""
    from kurooto.core import layout

    oid = str(payload.get("id") or "")
    with Lock(app.paths.state, "meetings", timeout=5):
        data = _load(app)
        rec = data["minutes"].get(oid)
        if rec is None or rec.get("status") != "writing":
            return  # "Not about the meeting" came first
        note = Path(rec["note"])
        if not note.is_file():
            rec["status"] = "gone"
            _save(app, data)
            return
        got, ok = parse(result.text if result.ok else "")
        day = dt.date.fromisoformat(rec["day"])
        head = f"**Minutes, {day:%a %d %b %Y}, with {rec['who']}**"
        if ok:
            parts = [head]
            for name, label in (("summary", ""), ("decisions", "Decisions:"), ("action items", "Action items:")):
                if got[name]:
                    parts += ([label] if label else []) + [f"- {x}" for x in got[name]]
            body = "\n".join(parts)
        else:
            earlier = block_body(note.read_text(encoding="utf-8"), f"minutes-{rec['day']}")
            said = " ".join(rec["text"].split())
            body = (earlier + "\n" if earlier else head + "\n") + f"- Your notes, as you sent them: {said}"
        before = note.read_text(encoding="utf-8")
        undo = {  # what Kurooto's blocks held before, for Not about the meeting
            "minutes": block_body(before, f"minutes-{rec['day']}"),
            "meeting": block_body(before, BLOCK),
            "steps": [],
        }
        text = _write_minutes(before, rec["day"], body)
        items = [_item(x) for x in got["action items"]] if ok else []
        if items:
            had = block_body(text, STEPS) or ""
            text = _add_steps(text, [x["text"] for x in items])
            undo["steps"] = [ln for ln in (block_body(text, STEPS) or "").split("\n") if ln and ln not in had]
        text = set_fields(text, met=rec["day"])
        note.write_text(text, encoding="utf-8")
        start = dt.datetime.fromisoformat(rec["start"])
        nxt = next_after(app, note, max(start, now().replace(tzinfo=None)))
        for x in items:
            if not x["due"]:
                d = nxt or dt.datetime.combine(now().date() + dt.timedelta(days=7), dt.time(17))
                x["due"] = d.isoformat()
        rec.update(status="open" if items else "done", items=items, undo=undo, ok=ok)
        _save(app, data)
    app.events.emit("meeting_minutes", ok=ok, items=len(items))
    shown = layout.shown(app, note)
    if not ok:
        line = f"Your AI couldn't write the minutes, so your notes went into {shown} as you sent them."
    else:
        line = f"Minutes from the meeting with {rec['who']} are in {shown}."
    if items:
        text_out, buttons = offer(oid, rec)
        app.notify(f"{line}\n\n{text_out}", kind="question", why="asked", reply_to=rec["reply_to"], buttons=buttons)
    else:
        app.notify(line + (" No action items." if ok else ""), kind="result", why="asked", reply_to=rec["reply_to"])


def _item(line: str) -> dict:
    by = BY.search(line)
    due = None
    if by:
        try:
            due = dt.datetime.combine(dt.date.fromisoformat(by[1]), dt.time(17)).isoformat()
        except ValueError:
            due = None
    return {"text": " ".join(BY.sub("", line).split()).rstrip(" .;,")[:200], "due": due, "added": None}


def _write_minutes(text: str, day: str, body: str) -> str:
    key = f"minutes-{day}"
    if block_body(text, key) is not None:
        return put(text, key, body)
    m = re.search(r"(?m)^## Meetings[ \t]*\n", text)
    if m:  # newest first, right under the heading (like the dated lines)
        return put(text, key, body, at=m.end())
    from kurooto.core.graphwrite import block
    from kurooto.core.tools import add_to_section

    return add_to_section(text, "Meetings", block(key, body))


def _add_steps(text: str, items: list[str]) -> str:
    """The action items as "- [ ] ..." lines in Kurooto's block under ## Next steps (the lines there are kept as they
    are, ticked or edited; only new ones are added)."""
    body = block_body(text, STEPS)
    have = {re.sub(r"^- \[[ xX]\]\s*", "", ln).strip().lower() for ln in (body or "").splitlines()}
    new = [f"- [ ] {x}" for x in items if x.lower() not in have]
    if not new:
        return text
    if body is not None:
        return put(text, STEPS, "\n".join([*body.split("\n"), *new]) if body.strip() else "\n".join(new))
    from kurooto.core.graphwrite import block

    if re.search(r"(?m)^## Next steps[ \t]*$", text):
        from kurooto.core.tools import add_to_section

        return add_to_section(text, "Next steps", block(STEPS, "\n".join(new)))
    for head in ("## Meetings", "## Log"):  # a new section, before these
        m = re.search(rf"(?m)^{head}[ \t]*$", text)
        if m:
            return text[: m.start()] + "## Next steps\n" + block(STEPS, "\n".join(new)) + "\n\n" + text[m.start() :]
    return text.rstrip("\n") + "\n\n## Next steps\n" + block(STEPS, "\n".join(new)) + "\n"


# --------------------------------------------------------------------------------------- the action items
def _short(s: str, n: int = 28) -> str:
    return s if len(s) <= n else (s[: n - 1].rsplit(" ", 1)[0] or s[: n - 1]).rstrip(" ,;:") + "…"


def offer(oid: str, rec: dict) -> tuple[str, list]:
    """The action items not made deadlines yet, with a button each (the first BUTTONS), None and Later."""
    left = [(i, x) for i, x in enumerate(rec.get("items") or []) if not x.get("added")]
    rows = [
        f"{k + 1}. {x['text']} (due {dt.datetime.fromisoformat(x['due']):%a %d %b})" for k, (_, x) in enumerate(left)
    ]
    buttons = [[(f"Add {k + 1}: {_short(x['text'])}", f"mtg:{oid}:a{i}")] for k, (i, x) in enumerate(left[:BUTTONS])]
    buttons.append([("None", f"mtg:{oid}:none"), ("Later", f"mtg:{oid}:later")])
    more = f"\n({len(left) - BUTTONS} more are under Next steps in the note.)" if len(left) > BUTTONS else ""
    return "Action items (each becomes a deadline only if you tap it):\n" + "\n".join(rows) + more, buttons


def button(app: App, oid: str, act: str) -> str:
    """mtg:<id>:a<n> (that action item becomes a deadline), none, later, not (not notes from the meeting)."""
    with Lock(app.paths.state, "meetings", timeout=5):
        data = _load(app)
        rec = data["minutes"].get(oid)
        if rec is None:
            return "That meeting's notes aren't remembered any more."
        writing = rec["job"] if act == "not" and rec.get("status") == "writing" else None
        if act == "not":
            out = _not_minutes(app, rec)
        elif act == "none":
            rec["status"] = "done"
            out = "No deadlines from them. They're still under Next steps in the note."
        elif act == "later":
            rec.update(status="later", later=(now().date() + dt.timedelta(days=1)).isoformat())
            out = "They'll come back tomorrow evening."
        elif act.startswith("a") and act[1:].isdigit():
            out = _add(app, rec, int(act[1:]))
        else:
            return "That button is out of date."
        _save(app, data)
    if writing:  # outside the lock: its then-action runs now, sees "not" and leaves the note alone
        app.jobs.cancel(writing)
    app.events.emit("meeting_button", act=act[:1] if act.startswith("a") else act)
    return out


def _add(app: App, rec: dict, i: int) -> str:
    items = rec.get("items") or []
    if not 0 <= i < len(items) or rec.get("status") not in ("open", "later"):
        return "That's dealt with already."
    x = items[i]
    if x.get("added"):
        return "On your deadlines already."
    dl = app.modules.get("deadlines")
    if dl is None or not app.is_on("deadlines"):
        return "Deadlines is off: Features → Deadlines → Turn on, then tap again."
    out = dl.add(x["text"], dt.datetime.fromisoformat(x["due"]), source="meeting", kind="task")
    x["added"] = time.time()
    if all(y.get("added") for y in items):
        rec["status"] = "done"
    return out


def _not_minutes(app: App, rec: dict) -> str:
    """Not notes from the meeting: Kurooto's blocks in the note go back to what they held before (the minutes, the
    Last met line, the action items it added), and the message goes to your AI as a plain message."""
    if rec.get("status") == "not":
        return "Done already."
    if rec.get("undo"):  # written already (still writing: button() cancels the request)
        note, u = Path(rec["note"]), rec["undo"]
        try:
            text = note.read_text(encoding="utf-8")
        except OSError:
            text = None
        if text is not None:
            key = f"minutes-{rec['day']}"
            text = put(text, key, u["minutes"]) if u.get("minutes") else drop(text, key)
            text = put(text, BLOCK, u["meeting"]) if u.get("meeting") else drop(text, BLOCK)
            steps = block_body(text, STEPS)
            if steps is not None and u.get("steps"):
                left = [ln for ln in steps.split("\n") if ln not in u["steps"]]
                text = put(text, STEPS, "\n".join(left)) if any(x.strip() for x in left) else drop(text, STEPS)
            note.write_text(text, encoding="utf-8")
    added = [x for x in rec.get("items") or [] if x.get("added")]
    rec.update(status="not", items=[], undo=None)
    words = rec.pop("text", "")
    if added:  # deadlines you tapped stay yours: /deadlines drops them
        app.events.emit("meeting_not_kept_deadlines", n=len(added))
    if app.is_on("chat") and words:
        app.jobs.submit(words, title=words[:80], reply_to=rec.get("reply_to"))
        return "Left out of the meeting notes; your AI has it as a plain message."
    return "Left out of the meeting notes."


def offers_due(app: App) -> int:
    """Action items you said Later to, back the next evening (with the meeting brief's run). How many came."""
    n = 0
    with Lock(app.paths.state, "meetings", timeout=5):
        data = _load(app)
        due = [
            (k, r)
            for k, r in data["minutes"].items()
            if r.get("status") == "later" and r.get("later", "9999") <= now().date().isoformat()
        ]
        for _k, r in due:
            r["status"] = "open"
        if due:
            _save(app, data)
    for k, r in due:
        text, buttons = offer(k, r)
        app.notify(
            f"From the meeting with {r['who']} on {dt.date.fromisoformat(r['day']):%a %d %b}. {text}",
            kind="question",
            why="meetings.actions",
            about=r["who"],
            buttons=buttons,
        )
        n += 1
    return n


# ------------------------------------------------------------------------------------- the weekly summary
MINUTES_DAY = re.compile(r"<!-- kurooto:minutes-(\d{4}-\d{2}-\d{2})\b")
QUIET_DAYS = 21  # someone you meet every week, not met for this long, gets a mention


def week_line(app: App, days: int = 7) -> str:
    """One line for the weekly summary about the people in your project notes, only from what's logged there: who you
    met this week (minutes or "Last met" in the note), who's next in the coming week, and anyone you meet regularly
    ("Meets:") not met for QUIET_DAYS days. Never a message of its own. "" when there's nothing to say."""
    from kurooto.core import infer

    t = now().replace(tzinfo=None)
    since = (t.date() - dt.timedelta(days=days - 1)).isoformat()
    met: list[str] = []
    nxt: list[tuple[dt.datetime, str]] = []
    quiet: list[str] = []
    seen: set[tuple[str, str]] = set()
    for note, who, role in infer.projects_with(app):
        key = (str(note), who.split()[-1].lower() if who.split() else who)
        if key in seen:
            continue
        seen.add(key)
        try:
            text = note.read_text(encoding="utf-8")
        except OSError:
            continue
        h = re.search(r"(?m)^# (.+)$", text)
        project = (h[1].strip() if h else note.parent.name)[:40]
        name = f"{who} ({role}, {project})" if role and role != "with" else f"{who} ({project})"
        days_met = sorted({d for d in [*MINUTES_DAY.findall(text), *LAST_MET_ANY.findall(text)] if d >= since})
        if days_met:
            met.append(f"{name} {', '.join(f'{dt.date.fromisoformat(d):%a}' for d in days_met)}")
        upcoming = next_after(app, note, t)
        if upcoming is not None and upcoming - t <= dt.timedelta(days=7):
            nxt.append((upcoming, f"{who} {upcoming:%a %H:%M}"))
        last = last_met(text)
        if schedule(text) and last and (t.date() - dt.date.fromisoformat(last)).days >= QUIET_DAYS:
            quiet.append(f"{who} (last met {dt.date.fromisoformat(last):%d %b})")
    parts = []
    if met:
        parts.append("met " + "; ".join(met))
    if nxt:
        parts.append("next: " + "; ".join(x for _, x in sorted(nxt)))
    if quiet:
        parts.append("not met for a while: " + "; ".join(quiet))
    return ("People (from your project notes): " + ". ".join(parts) + ".") if parts else ""
