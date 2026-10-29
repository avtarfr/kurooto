"""The greeting when you sit down at your desk after a while: made by rules on this computer (no AI request), about
three sentences and at most 220 characters, spoken through Voice. Then Voice's conversation opens (Portal.invite), not
in "awaiting" mode, so "what's on today?" or "yes" goes to your AI without its name, and chatter nearby closes it.

    always    "Welcome back." ("Morning." the first time a day, before 12:00)
    next      the next thing today (the dashboard's Today): "Next: Linear Algebra at 14:00, in 40 minutes."
    waiting   counts only: "Two questions and one approval wait for you."
    deadline  one due within 24 hours, its title and time: "Problem set 3 is due at 23:59."
    held      how many messages wait for the evening (never what they say)
    answers   (0.9.0) how many answers weren't read aloud while you were away (face.away.hold_desktop, or
              voice.speak.stop_when_gone): "One answer came while you were away; say yes to hear it." A yes right
              after is read here, by Voice (Voice.read_held), not sent to the AI. Counts only, never what they say
    ending    "Want to go through them?" when something waits and the conversation will open

Your name (0.9.0, persona.templates): with "what to call you" on your persona card, the opening carries it ("Welcome
back, Sam.") only while nobody else is in view; it doesn't count toward the 220 characters, so it never pushes a part
out. The card's avoid line applies as punctuation only (core/persona.py:template).

Add-ons' lines (0.9.0, face.greet.addons, off): an add-on may add one short line of its own (Face.greet_part), said
after every part above, so it's the first to go at the length limit and never pushes one of them out; only with nobody
else in view. Known guests (0.9.0, face.addons.known_guests): an add-on may say, as a yes or no only, that everyone
else in view is someone it knows (Face.known_guests); then "skip" greets them "short" instead.

Someone else in view (face.greet.with_others): skip (the default: no greeting at all), short ("Welcome back." only,
no conversation), or full. Class and deadline names are never spoken in front of someone else unless you chose full.

When it may greet (may_greet): face.greet.on; Voice on, able to speak and not muted; no call block (a call, "no calls
till", focus, the night, a class you attend, a calendar event, #nocall); Kurooto not paused; the gap and the day's cap;
and Calm's rules for spoken words (Calm.speak_ok, reason face.greet: exam season and a quiet week silence it).
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App

MAX_CHARS = 220
PARTS = ("next", "waiting", "deadline", "held", "answers")
NUMBERS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine"}


def number(n: int) -> str:
    return NUMBERS.get(n, str(n))


def plural(n: int, one: str, many: str) -> str:
    return f"{number(n).lower()} {one if n == 1 else many}"


def _minutes(at: str, now: dt.datetime) -> int | None:
    try:
        h, m = (int(x) for x in at.split(":")[:2])
    except ValueError:
        return None
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return round((t - now).total_seconds() / 60)


def compose(
    parts,
    items: list[dict],
    waiting: tuple[int, int],
    deadline: tuple[str, dt.datetime] | None,
    held: int,
    others: bool,
    now: dt.datetime,
    first_today: bool = False,
    with_others: str = "skip",
    talk: bool = True,
    name: str = "",
    extra: list[tuple[str, str]] | tuple = (),
    answers: int = 0,
) -> tuple[str, list[str]]:
    """The greeting's text and the names of the parts said (the event carries the names, never the text). name: what
    to call you, said only with nobody else in view and not counted toward MAX_CHARS."""
    opening = "Morning." if first_today and now.hour < 12 else "Welcome back."
    if others and with_others != "full":
        return "Welcome back.", []
    named = f"{opening[:-1]}, {name.strip()}." if name.strip() and not others else opening
    name_len = len(named) - len(opening)  # not counted toward MAX_CHARS
    said: list[tuple[str, str]] = []
    for p in parts or ():
        if p == "next":
            nxt = next((i for i in items if i.get("state") == "next"), None)
            if nxt:
                mins = _minutes(str(nxt.get("at") or ""), now)
                when = f", in {mins} minutes" if mins is not None and 0 < mins <= 90 else ""
                said.append((p, f"Next: {str(nxt.get('what') or '').strip()[:60]} at {nxt.get('at')}{when}."))
        elif p == "waiting":
            q, a = waiting
            if q or a:
                bits = [plural(q, "question", "questions")] if q else []
                bits += [plural(a, "approval", "approvals")] if a else []
                verb = "waits" if q + a == 1 else "wait"
                text = " and ".join(bits)
                said.append((p, f"{text[0].upper()}{text[1:]} {verb} for you."))
        elif p == "deadline" and deadline:
            title, due = deadline
            day = "" if due.date() == now.date() else " tomorrow" if due.date() == now.date() + dt.timedelta(1) else ""
            said.append((p, f"{title.strip()[:60]} is due{day} at {due:%H:%M}."))
        elif p == "held" and held:
            said.append((p, f"{plural(held, 'message waits', 'messages wait').capitalize()} for this evening."))
        elif p == "answers" and answers:  # (0.9.0) last, so the trim drops it before the parts that came before it
            came = f"{plural(answers, 'answer', 'answers').capitalize()} came while you were away"
            said.append((p, f"{came}; say yes to hear {'it' if answers == 1 else 'them'}." if talk else f"{came}."))
    for p, line in extra:  # (0.9.0) add-ons' lines last: the first to go at the limit
        if line.strip():
            said.append((p, line.strip()))
    # (0.9.0) with held answers offered, the yes is theirs: no second question
    waits = any(p in ("waiting", "held") for p, _ in said) and not any(p == "answers" for p, _ in said)
    ending = " Want to go through them?" if waits and talk else ""
    while said:
        text = " ".join([named, *[t for _, t in said]]) + ending
        if len(text) - name_len <= MAX_CHARS:
            return text, [p for p, _ in said]
        said.pop()  # the last part goes first
        waits = any(p in ("waiting", "held") for p, _ in said) and not any(p == "answers" for p, _ in said)
        ending = " Want to go through them?" if waits and talk else ""
    return named, []


def may_greet(app: App, face, others: bool, now: dt.datetime | None = None) -> tuple[bool, str]:
    """(True, "") or (False, why not) — every rule in the module docstring, Calm last (it records the decision)."""
    from kurooto.core.clock import now as clock_now

    now = now or clock_now()
    s = face.setting
    if not s("greet.on"):
        return False, "greetings are off"
    v = app.modules.get("voice")
    if v is None or not app.is_on("voice"):
        return False, "Voice is off"
    if v.muted():
        return False, "Voice is muted"
    try:
        tts, _why = v.tts()
    except Exception:
        tts = None
    if tts is None:
        return False, "Voice can't speak"
    reason, _until = app.availability.call_block(now)
    if reason:
        return False, str(reason)
    if app.power.current == "paused":
        return False, "Kurooto is paused"
    if others and str(s("greet.with_others") or "skip") == "skip" and not face.known_guest():
        return False, "someone else is here"
    g = face.greets()
    gap = float(s("greet.gap_min") or 60) * 60
    if g.get("last") and now.timestamp() - float(g["last"]) < gap:
        return False, "greeted a little while ago"
    if g.get("day") == now.date().isoformat() and int(g.get("n") or 0) >= int(s("greet.per_day") or 3):
        return False, "enough greetings today"
    if not app.calm.speak_ok("face.greet", about="arrival"):
        return False, "Calm held it"
    return True, ""
