"""Dreaming consolidates: each night it looks over what Kurooto remembers for the same thing kept twice and for lines
that disagree, and the morning message (modules/dreaming.py) lists them as one short section, each with Keep A /
Keep B / Both true (Keep both for a duplicate). Nothing changes until you tap, and every change has an Undo.

    duplicates      two gists of the same kind (core/gists.py) or two of Kurooto's own lines in your how-to-help-me
                    note (modules/remember.py) that say the same thing: the same words once normalised, or the same
                    key terms with the same dates and numbers
    disagreements   a how-to-help-me line against another one or against your notes (daily notes and project meetings
                    from the last 30 days, through the memory ledger, core/ledger.py), two notes, or a note against an
                    open deadline: the same key terms (and the same "Quiz 3", "Assignment 2") with a different date,
                    weekday, time or number ("Quiz 3 is due Fri" vs "Quiz 3 is due Mon"). Gists are records of what
                    happened, so they're only checked for duplicates. With the notes brain on, its contradictions
                    report joins (GBrain's find-contradictions, from the last `gbrain eval suspected-contradictions`
                    you ran: Kurooto never runs that probe, which uses an AI model)

Rules first. A pair that's close but not clear (shared key terms, below the bar) can get a second opinion
(dreaming.consolidate_ai): "local" asks the model on this computer when there is one (nothing leaves it), "main" your
own AI (only how-to-help-me lines and note lines go to it, never a gist), "off" none; at most 8 a night.

What a tap does: a how-to-help-me line Kurooto wrote is taken out of the note; a gist is dropped from the ledger (its
words are kept sealed for the Undo); a deadline moves to the date the note says. A line of your own notes is never
changed: Kurooto says where it is, for you to change. Both true remembers the pair so it doesn't come back. An item
shown twice without a tap is let go.

State: <state>/dreaming-consolidate.json holds references only (a line's hash, a gist's row number, a note's path and
a keyed hash of its line), the pairs settled (keyed hashes) and the Undo records (a gist's words sealed with the
ledger's key).
"""

from __future__ import annotations

import base64
import datetime as dt
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "dreaming",
    {
        "consolidate": True,  # duplicates and lines that disagree in what it remembers: Keep A / Keep B / Both true
        "consolidate_ai": "local",  # a second opinion on near misses: local (this computer), main (your AI), off
        "consolidate_max": 3,  # at most this many in one morning message; the rest wait for the next ones
    },
)

WHEN = "daily 04:45"  # after the ledger's nightly read of your notes (core/ledger.py, 04:30)
NOTE_DAYS = 30  # notes and gists this recent are compared
SHOWN_MAX = 2  # an item shown this many times without a tap is let go
AI_MAX = 8  # second opinions a night
PENDING_MAX = 30
TEXT = 90  # characters of each side shown
STALE_H = 20  # a scan older than this is redone (rules only) before the morning message
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
ID_WORDS = (
    "quiz|assignment|homework|hw|lecture|chapter|problem set|pset|ps|lab|test|exam|midterm|tutorial|sheet|week|unit|"
    "section|part|project|lesson|module|paper|question|q"
)
IDENT = re.compile(rf"\b({ID_WORDS})\s*(?:no\.?\s*|#\s*)?(\d{{1,3}})\b")
ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?)"
)
DAY_MONTH = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{MONTH}\b")
MONTH_DAY = re.compile(rf"\b{MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b")
WEEKDAY = re.compile(
    r"\b(mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|saturday|sunday)\b"
)
TIMEISH = re.compile(r"\b(before|after|at|by|until|till|from|around)\s+(\d{1,2})\b(?![:.]\d|\s*(?:am|pm)\b)")
SCHEDULE = re.compile(
    r"\b(?:due|deadline|submit\w*|hand(?:ed)? in|moved|postponed|preponed|rescheduled|scheduled|shifted|is on|is at|"
    r"will be on|happens on)\b"
)
CLOCK = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\b(\d{1,2}):(\d{2})\b")
NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
REL_DAY = re.compile(r"\b(today|tonight|tomorrow)\b")
WORD = re.compile(r"[a-z][a-z']{2,}")
STOP = set(
    "the and for with that this from have has had was were are you your yours i'm i've i'll i'd what when where which "
    "who why how did does doing done not but all any can could would should will just about into onto over then than "
    "them they their there here its it's let me my mine our ours out off get got some more most much very really also "
    "too yet still last time thing things stuff today tonight tomorrow yesterday morning evening please thanks okay "
    "been being is on at by in of to a an be it no yes am pm every each next this week day days now don't dont do "
    "never".split()
)
KIND_WORDS = {"date": "dates", "time": "times", "num": "numbers"}


def on(app: App) -> bool:
    return bool(app.settings.get("dreaming.consolidate"))


def state_file(app: App) -> Path:
    return Path(app.paths.state) / "dreaming-consolidate.json"


# ------------------------------------------------------------------------------------------------ reading a line
def stem(w: str) -> str:
    w = w.strip("'")
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _next_weekday(base: dt.date, wd: int) -> dt.date:
    return base + dt.timedelta(days=(wd - base.weekday()) % 7)


@dataclass
class Read:
    terms: set[str] = field(default_factory=set)
    ids: set[str] = field(default_factory=set)
    values: dict[str, set[str]] = field(default_factory=dict)
    norm: str = ""


def read(text: str, base: dt.date) -> Read:
    """A line's key terms, its identifiers ("quiz#3"), and its values by kind: dates (a weekday is the next one on or
    after the line's own day), times and other numbers."""
    low = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", str(text or "").lower())
    out = Read(norm=re.sub(r"[^a-z0-9]+", " ", low).strip())
    vals: dict[str, set[str]] = {}

    def put(kind: str, v: str) -> None:
        vals.setdefault(kind, set()).add(v)

    for m in IDENT.finditer(low):
        word = "problem set" if m[1] in ("pset", "ps") else m[1]
        out.ids.add(f"{word.replace(' ', '')}#{int(m[2])}")
    low = IDENT.sub(" ", low)
    for m in ISO.finditer(low):
        try:
            put("date", dt.date(int(m[1]), int(m[2]), int(m[3])).isoformat())
        except ValueError:
            pass
    low = ISO.sub(" ", low)
    for rx, order in ((DAY_MONTH, (1, 2)), (MONTH_DAY, (2, 1))):
        for m in rx.finditer(low):
            d, mon = m[order[0]], m[order[1]]
            if mon[:3] in MONTHS:
                try:
                    day = dt.date(base.year, MONTHS.index(mon[:3]) + 1, int(d))
                except ValueError:
                    continue
                if (base - day).days > 180:
                    day = day.replace(year=base.year + 1)
                put("date", day.isoformat())
                low = low.replace(m[0], " ")
    for m in WEEKDAY.finditer(low):
        put("date", _next_weekday(base, WEEKDAYS.index(m[1][:3])).isoformat())
    low = WEEKDAY.sub(" ", low)
    for m in REL_DAY.finditer(low):
        put("date", (base + dt.timedelta(days=1 if m[1] == "tomorrow" else 0)).isoformat())
    for m in CLOCK.finditer(low):
        if m[3]:
            h, mins = int(m[1]) % 12 + (12 if m[3] == "pm" else 0), int(m[2] or 0)
        else:
            h, mins = int(m[4]), int(m[5])
        if h < 24 and mins < 60:
            put("time", f"{h:02d}:{mins:02d}")
    low = CLOCK.sub(" ", low)
    for m in TIMEISH.finditer(low):
        if int(m[2]) < 24:
            put("time", f"{int(m[2]):02d}:00")
    low = TIMEISH.sub(lambda m: m[1] + " ", low)
    for m in NUMBER.finditer(low):
        put("num", m[0])
    out.values = vals
    out.terms = {stem(w) for w in WORD.findall(NUMBER.sub(" ", low)) if w not in STOP and not re.fullmatch(MONTH, w)}
    out.terms |= out.ids
    return out


def overlap(a: Read, b: Read) -> tuple[int, float, float]:
    """(shared key terms, shared over the smaller set, shared over both)."""
    common = len(a.terms & b.terms)
    if not common:
        return 0, 0.0, 0.0
    return common, common / min(len(a.terms), len(b.terms)), common / len(a.terms | b.terms)


def ids_clash(a: Read, b: Read) -> bool:
    """ "Quiz 3" and "Quiz 4": two different things, however alike the rest."""
    return bool(a.ids and b.ids and not a.ids & b.ids)


def differs(a: Read, b: Read, kinds: tuple[str, ...]) -> str:
    """The first kind of value both lines give and disagree on ("date", "time", "num"), or ""."""
    for k in kinds:
        if a.values.get(k) and b.values.get(k) and not a.values[k] & b.values[k]:
            return k
    return ""


# ---------------------------------------------------------------------------------------------- what's compared
@dataclass
class Side:
    t: str  # fact | gist | note | deadline | gbrain
    ref: dict  # what's stored to find it again (no words of a gist)
    text: str
    where: str
    day: dt.date
    group: str = ""  # two sides of one group are never compared (lines of one daily note)
    sub: str = ""  # a gist's kind
    due: str = ""  # a deadline's due date (ISO)
    n: float = 0  # its place, for which of a pair is A: the older (a gist's time, a line's place in its note)
    r: Read = field(default_factory=Read)

    @property
    def sid(self) -> str:
        return "|".join(f"{k}={self.ref[k]}" for k in sorted(self.ref))


def _mac(app: App, *parts: str) -> str:
    from kurooto.core import ledger

    return ledger.of(app).mac("consolidate", *parts)


def _short(day: dt.date) -> str:
    return f"{day:%a %d %b}"


def facts(app: App) -> list[Side]:
    from kurooto.modules.remember import help_rel, kept_lines

    out = []
    for i, x in enumerate(kept_lines(app)):
        try:
            day = dt.date.fromisoformat(x["date"])
        except ValueError:
            continue
        ref = {"t": "fact", "key": x["key"], "line": x["line"], "section": x["section"]}
        out.append(Side("fact", ref, x["fact"], f"{help_rel(app)}, {day:%d %b}", day, n=i))
    return out


def gists(app: App, rows: list[dict]) -> list[Side]:
    from kurooto.core import ledger

    out = []
    for r in rows:
        if r["kind"] != "gist":
            continue
        day = dt.date.fromtimestamp(r["at"])
        ref = {"t": "gist", "id": r["id"]}
        out.append(Side("gist", ref, r["text"], ledger.label(r), day, sub=r.get("sub") or "", n=r["at"]))
    return out


def lines_of(app: App, kind: str, src: str) -> list[str]:
    """The lines the ledger reads from one note: a daily note's lines (headings left out), a project's meetings."""
    from kurooto.core.ledger import DAY_LINE, _clean, _meetings
    from kurooto.modules.remember import sensitive

    f = Path(app.workspace) / src
    if kind == "meeting":
        return [line for _at, line, _x in _meetings(app, f)]
    text = re.sub(r"\A---\n.*?\n---\n", "", f.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    out = []
    for ln in text.splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        m = DAY_LINE.match(ln.strip())
        if m and not sensitive(m["text"]):
            out.append(_clean(m["text"]))
    return out


def note_lines(app: App, rows: list[dict]) -> list[Side]:
    """Each line of the daily notes and project meetings the ledger holds from the last NOTE_DAYS."""
    out = []
    for r in rows:
        if r["kind"] not in ("day", "meeting"):
            continue
        day = dt.date.fromtimestamp(r["at"])
        src = str(r.get("source") or "")
        try:
            got = lines_of(app, r["kind"], src)
        except OSError:
            continue
        for p in got:
            if len(p) < 8:
                continue
            ref = {"t": "note", "k": r["kind"], "src": src, "h": _mac(app, "note", src, p)}
            where = f"{src}, {_short(day)}" if r["kind"] == "day" else src
            out.append(Side("note", ref, p, where, day, group=f"{r['kind']}:{src}" if r["kind"] == "day" else ""))
    return out


def deadline_sides(app: App) -> list[Side]:
    dl = app.modules.get("deadlines")
    if dl is None or not app.is_on("deadlines"):
        return []
    out = []
    today = now().date()
    for i, it in dl.items().items():
        if it.get("status") != "open":
            continue
        try:
            due = dt.datetime.fromisoformat(str(it["due"])[:19])
        except (KeyError, ValueError):
            continue
        if not -7 <= (due.date() - today).days <= 90:
            continue
        title = dl.full_title(it)
        s = Side("deadline", {"t": "deadline", "id": i}, f"{title}, due {due:%a %d %b}", "your deadlines", today)
        s.due = due.date().isoformat()
        s.r = read(title, today)
        s.r.terms.add("due")
        s.r.values = {"date": {s.due}}
        out.append(s)
    return out


def gbrain_pairs(app: App) -> list[tuple[Side, Side, str]]:
    """The notes brain's contradictions report, when it's on: (A, B, what they disagree about)."""
    gb = app.modules.get("gbrain")
    if gb is None or not app.is_on("gbrain"):
        return []
    try:
        found = gb.contradictions()
    except Exception as e:  # its report must never cost the night
        app.events.emit("dreaming_check_failed", error=f"gbrain: {type(e).__name__}"[:200])
        return []
    today = now().date()
    out = []
    for f in found:
        sides = []
        for k in ("a", "b"):
            m = f.get(k) or {}
            slug, text = str(m.get("slug") or ""), re.sub(r"\s+", " ", str(m.get("text") or "")).strip()
            if not slug or not text:
                break
            when = str(m.get("effective_date") or "")
            where = f"{slug}" + (f", {when}" if when else "")
            ref = {"t": "gbrain", "slug": slug, "text": text[:240]}
            sides.append(Side("gbrain", ref, text[:240], where, today, n=len(sides)))  # A and B as GBrain gave them
        if len(sides) == 2:
            out.append((sides[0], sides[1], str(f.get("axis") or "")[:80]))
    return out


# ------------------------------------------------------------------------------------------------- finding pairs
@dataclass
class Found:
    kind: str  # dup | clash
    a: Side
    b: Side
    why: str


def _pairs(sides: list[Side], min_common: int = 2):
    """Pairs that share at least min_common key terms (an index of terms, not every pair)."""
    index: dict[str, list[int]] = {}
    for i, s in enumerate(sides):
        for t in s.r.terms:
            index.setdefault(t, []).append(i)
    count: dict[tuple[int, int], int] = {}
    for ids in index.values():
        if len(ids) > 200:  # a word in everything says nothing
            continue
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                k = (ids[x], ids[y])
                count[k] = count.get(k, 0) + 1
    for (i, j), n in count.items():
        if n >= min_common:
            yield sides[i], sides[j]


def same(a: Side, b: Side) -> bool:
    if a.r.norm and a.r.norm == b.r.norm:
        return True
    common, _small, both = overlap(a.r, b.r)
    return common >= 2 and both >= 0.75 and a.r.values == b.r.values and a.r.ids == b.r.ids


def check(a: Side, b: Side) -> tuple[str, str]:
    """("dup" | "clash" | "near" | "", why) for one pair, by rules."""
    if a.group and a.group == b.group:
        return "", ""
    kinds = {a.t, b.t}
    if a.t == b.t and a.t in ("fact", "gist") and (a.t != "gist" or a.sub == b.sub):
        if (a.t != "gist" or a.day == b.day) and same(a, b):  # a gist a day of one routine isn't a copy
            return "dup", "the same thing twice"
    if "gist" in kinds or kinds == {"deadline"}:
        return "", ""
    if ids_clash(a.r, b.r):
        return "", ""
    common, small, both = overlap(a.r, b.r)
    if common < 2:
        return "", ""
    # a how-to-help-me line is a standing claim: any date, time or number counts; notes and deadlines are dated
    # events, so only a different date for the same thing does
    value_kinds = ("date", "time", "num") if "fact" in kinds else ("date",)
    if small >= 0.75:
        k = differs(a.r, b.r, value_kinds)
        if k == "date" and any(s.t == "note" and not SCHEDULE.search(s.text.lower()) for s in (a, b)):
            k = ""  # "studied for quiz 3 on Thursday" says when you did something, not when it's due
        if k:
            return "clash", f"different {KIND_WORDS[k]}"
    if 0.5 <= small and both >= 0.34 and "fact" in kinds:
        return "near", ""
    return "", ""


# ------------------------------------------------------------------------------------------------ second opinion
AI_PROMPT = (
    "Two lines from one person's notes and assistant memory. Answer with one word: SAME if they say the same thing, "
    "CLASH if they can't both be true (a different date, time or number for the same thing), else DIFFERENT.\n\n"
    "A: {a}\nB: {b}\n"
)


def _brain(app: App, how: str):
    from kurooto import providers

    if how == "local":
        return providers.local(app)
    if how == "main":
        brain = providers.build(app, app.settings.get("brain.main") or "")
        quota = getattr(app, "quota", None)
        if brain is not None and quota is not None and quota.wait_until(quota.pool(brain, "low")) is not None:
            return providers.local(app)  # its free limit is kept for you
        return brain if brain is not None and brain.available()[0] else None
    return None


def second_opinion(app: App, near: list[tuple[Side, Side]]) -> list[Found]:
    how = str(app.settings.get("dreaming.consolidate_ai") or "off").strip().lower()
    if how not in ("local", "main") or not near:
        return []
    brain = _brain(app, how)
    if brain is None:
        return []
    out = []
    for a, b in near[:AI_MAX]:
        if "gist" in (a.t, b.t):
            continue  # gists never leave the ledger for an AI
        try:
            r = brain.complete(AI_PROMPT.format(a=a.text[:300], b=b.text[:300]), effort="low", timeout=60)
        except Exception as e:
            app.events.emit("dreaming_check_failed", error=f"consolidate ai: {type(e).__name__}"[:200])
            break
        word = (getattr(r, "text", "") or "").strip().upper() if getattr(r, "ok", False) else ""
        if word.startswith("SAME") and a.t == b.t == "fact":
            out.append(Found("dup", a, b, "the same thing twice (a second opinion)"))
        elif word.startswith("CLASH"):
            out.append(Found("clash", a, b, "they disagree (a second opinion)"))
    app.events.emit("dreaming_second_opinion", asked=min(len(near), AI_MAX), found=len(out), how=how)
    return out


# ------------------------------------------------------------------------------------------------------ the scan
def _load(app: App) -> dict:
    st = jload(state_file(app), {}) or {}
    st.setdefault("items", [])
    st.setdefault("decided", {})
    st.setdefault("undo", {})
    return st


def pair_key(app: App, a: Side, b: Side) -> str:
    return _mac(app, "pair", *sorted((a.sid, b.sid)))


def scan(app: App, ai: bool = True) -> int:
    """Look over what's remembered; new items join the ones waiting. How many were new. Nothing is changed."""
    from kurooto.core import ledger

    if not on(app) or ledger.locked(app):
        return 0
    led = ledger.of(app)
    try:
        led.refresh()
        lo = time.time() - NOTE_DAYS * 86400
        rows = [r for r in led.rows(("gist", "day", "meeting")) if r["at"] >= lo]
    except ledger.Locked:
        return 0
    sides = facts(app) + gists(app, rows) + note_lines(app, rows) + deadline_sides(app)
    for s in sides:
        if s.t != "deadline":
            s.r = read(s.text, s.day)
    found: list[Found] = []
    near: list[tuple[Side, Side]] = []
    for a, b in _pairs(sides):
        kind, why = check(a, b)
        if kind == "near":
            near.append((a, b))
        elif kind:
            found.append(Found(kind, a, b, why))
    if ai:
        found += second_opinion(app, near)
    found += [Found("clash", a, b, why or "your notes brain says they disagree") for a, b, why in gbrain_pairs(app)]
    new = 0
    with Lock(app.paths.state, "dreaming-consolidate"):
        st = _load(app)
        have = {it["pair"] for it in st["items"]}
        for f in found:
            a, b = (f.a, f.b) if (f.a.day, f.a.n, f.a.sid) <= (f.b.day, f.b.n, f.b.sid) else (f.b, f.a)  # A: older
            key = pair_key(app, a, b)
            if key in have or key in st["decided"]:
                continue
            have.add(key)
            st["items"].append(
                {
                    "ref": uuid.uuid4().hex[:8],
                    "kind": f.kind,
                    "why": f.why,
                    "pair": key,
                    "a": a.ref,
                    "b": b.ref,
                    "found": now().isoformat(timespec="seconds"),
                    "shown": 0,
                }
            )
            new += 1
        st["items"] = st["items"][-PENDING_MAX:]
        st["scanned"] = time.time()
        jsave(state_file(app), st)
    app.events.emit(
        "dreaming_consolidate",
        dups=sum(1 for f in found if f.kind == "dup"),
        clashes=sum(1 for f in found if f.kind == "clash"),
        new=new,
        compared=len(sides),
    )
    return new


# ------------------------------------------------------------------------------------- finding a side again
def resolve(app: App, ref: dict) -> Side | None:
    """A stored side as it is now; None when it's gone or changed (then the item is let go)."""
    t = ref.get("t")
    today = now().date()
    if t == "fact":
        from kurooto.modules.remember import help_rel, kept_lines

        x = next((x for x in kept_lines(app) if x["key"] == ref.get("key")), None)
        if x is None:
            return None
        return Side("fact", {**ref, "line": x["line"]}, x["fact"], f"{help_rel(app)}, {x['date']}", today)
    if t == "gist":
        from kurooto.core import ledger

        try:
            r = ledger.of(app).get(int(ref.get("id") or 0))
        except ledger.Locked:
            return None
        if r is None or r["kind"] != "gist":
            return None
        return Side("gist", ref, r["text"], ledger.label(r), today, sub=r.get("sub") or "")
    if t == "note":
        src = str(ref.get("src") or "")
        try:
            got = lines_of(app, str(ref.get("k") or "day"), src)
        except OSError:
            return None
        hit = next((p for p in got if _mac(app, "note", src, p) == ref.get("h")), None)
        if hit is None:
            return None
        m = re.search(r"\d{4}-\d{2}-\d{2}", src)
        day = dt.date.fromisoformat(m[0]) if m and ref.get("k") != "meeting" else today
        return Side("note", ref, hit, src, day)
    if t == "deadline":
        dl = app.modules.get("deadlines")
        it = (dl.items() if dl is not None else {}).get(str(ref.get("id")))
        if not it or it.get("status") != "open":
            return None
        try:
            due = dt.datetime.fromisoformat(str(it["due"])[:19])
        except ValueError:
            return None
        s = Side("deadline", ref, f"{dl.full_title(it)}, due {due:%a %d %b}", "your deadlines", today)
        s.due = due.isoformat()
        return s
    if t == "gbrain":
        return Side("gbrain", ref, str(ref.get("text") or ""), str(ref.get("slug") or ""), today)
    return None


# -------------------------------------------------------------------------------------------- the morning section
def _q(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return f'"{s if len(s) <= TEXT else s[: TEXT - 1].rstrip() + "…"}"'


def section(app: App, send: bool) -> tuple[str, list]:
    """The morning message's part: ("Worth a look in what I remember: ...", button rows). A scan that's stale is
    redone first, by rules only. Only the sent message counts as showing an item."""
    if not on(app):
        return "", []
    st = jload(state_file(app), {}) or {}
    if time.time() - float(st.get("scanned") or 0) > STALE_H * 3600:
        try:
            scan(app, ai=False)
        except Exception as e:  # never at the cost of the morning message
            app.events.emit("dreaming_check_failed", error=f"consolidate: {type(e).__name__}: {e}"[:200])
    try:
        most = max(1, int(app.settings.get("dreaming.consolidate_max") or 3))
    except (TypeError, ValueError):
        most = 3
    lines, buttons = [], []
    with Lock(app.paths.state, "dreaming-consolidate"):
        st = _load(app)
        keep, gone = [], []
        for it in st["items"]:
            a, b = resolve(app, it["a"]), resolve(app, it["b"])
            if a is None or b is None or it["pair"] in st["decided"]:
                continue  # one side is gone or changed: nothing to ask
            keep.append(it)
            if send and int(it.get("shown") or 0) >= SHOWN_MAX:
                gone.append(it)  # shown twice and left: let go, and not asked again
                continue
            if len(lines) >= most:
                continue
            n = len(lines) + 1
            head = "The same thing twice" if it["kind"] == "dup" else f"These disagree ({it['why']})"
            lines.append(f"{n}. {head}: A {_q(a.text)} ({a.where}); B {_q(b.text)} ({b.where}).")
            third = ("Keep both", "both") if it["kind"] == "dup" else ("Both true", "both")
            buttons.append(
                [
                    (f"{n}: Keep A", f"dcn:{it['ref']}:a"),
                    (f"{n}: Keep B", f"dcn:{it['ref']}:b"),
                    (f"{n}: {third[0]}", f"dcn:{it['ref']}:{third[1]}"),
                ]
            )
            if send:
                it["shown"] = int(it.get("shown") or 0) + 1
        if send:
            for it in gone:
                st["decided"][it["pair"]] = {"how": "unanswered", "at": now().isoformat(timespec="seconds")}
            st["items"] = [it for it in keep if it not in gone]
            jsave(state_file(app), st)
    if not lines:
        return "", []
    more = sum(1 for it in st["items"] if it["pair"] not in st["decided"]) - len(lines)
    tail = f"\n({more} more wait for the next mornings.)" if more > 0 else ""
    return "Worth a look in what I remember (nothing changes until you tap):\n" + "\n".join(lines) + tail, buttons


# ------------------------------------------------------------------------------------------------------ the taps
def _undo_point(st: dict, rec: dict) -> str:
    uid = uuid.uuid4().hex[:8]
    st["undo"] = {**dict(list(st["undo"].items())[-19:]), uid: rec}
    return uid


def _let_go(app: App, side: Side, kept: Side) -> tuple[str, dict | None]:
    """What happens to the side not kept: (what to say, the Undo record or None)."""
    if side.t == "fact":
        from kurooto.modules.remember import help_rel, remove_line

        if not remove_line(app, side.ref["line"]):
            return "That line isn't in your how-to-help-me note as I wrote it any more, so I left it alone.", None
        return f"Took {_q(side.text)} out of {help_rel(app)}.", {
            "do": "fact",
            "section": side.ref.get("section"),
            "line": side.ref["line"],
        }
    if side.t == "gist":
        from kurooto.core import ledger

        led = ledger.of(app)
        r = led.get(int(side.ref["id"]))
        if r is None:
            return "That gist is gone already.", None
        sealed = led.seal("gist", {"text": r["text"], "at": r["at"], "sub": r.get("sub") or ""})
        led.delete([r["id"]])
        app.events.emit("gist_forgotten")
        return "Dropped the other gist.", {"do": "gist", "blob": base64.b64encode(sealed).decode()}
    if side.t == "deadline" and kept.t != "deadline":
        days = sorted(read(kept.text, _day_of(kept)).values.get("date") or [])
        dl = app.modules.get("deadlines")
        if len(days) == 1 and dl is not None:
            it = dl.items().get(str(side.ref["id"])) or {}
            old = str(it.get("due") or "")
            try:
                was = dt.datetime.fromisoformat(old[:19])
            except ValueError:
                return "That deadline is gone.", None
            when = dt.datetime.combine(dt.date.fromisoformat(days[0]), was.time())
            said = dl.move(str(side.ref["id"]), when)
            return said, {"do": "deadline", "id": side.ref["id"], "due": old[:19]}
        return "I couldn't tell which date the note means, so the deadline is as it was (/deadlines).", None
    where = side.where.split(",")[0]
    return f"{_q(side.text)} is in your note {where}; that's yours to change.", None


def _day_of(side: Side) -> dt.date:
    if side.t == "note":
        m = re.search(r"\d{4}-\d{2}-\d{2}", str(side.ref.get("src") or ""))
        if m:
            try:
                return dt.date.fromisoformat(m[0])
            except ValueError:
                pass
    return side.day


def button(app: App, ref: str, act: str) -> str:
    """dcn:<item>:a|b|both, under the morning message's section; dcn:<undo>:undo after a change."""
    if act == "undo":
        return undo(app, ref)
    with Lock(app.paths.state, "dreaming-consolidate"):
        st = _load(app)
        it = next((x for x in st["items"] if x["ref"] == ref), None)
        if it is None or it["pair"] in st["decided"]:
            return "That's settled already."
        a, b = resolve(app, it["a"]), resolve(app, it["b"])
        if a is None or b is None:
            st["items"] = [x for x in st["items"] if x is not it]
            jsave(state_file(app), st)
            return "One of the two changed since, so there's nothing to settle."
        if act == "both":
            said, rec = ("Kept both; I won't ask about these two again." if it["kind"] == "dup" else
                         "Both true, then; I won't ask about these two again."), None  # fmt: skip
        elif act in ("a", "b"):
            kept, other = (a, b) if act == "a" else (b, a)
            said, rec = _let_go(app, other, kept)
        else:
            return "unknown button"
        st["decided"][it["pair"]] = {"how": act, "at": now().isoformat(timespec="seconds")}
        st["items"] = [x for x in st["items"] if x is not it]
        uid = _undo_point(st, {**rec, "pair": it["pair"], "item": it}) if rec else ""
        jsave(state_file(app), st)
    app.events.emit("dreaming_settled", how=act, kind=it["kind"], sides=f"{it['a']['t']}/{it['b']['t']}")
    if uid:
        app.notify(said, kind="info", why="asked", buttons=[[("Undo", f"dcn:{uid}:undo")]])
    return said[:190]


def undo(app: App, uid: str) -> str:
    with Lock(app.paths.state, "dreaming-consolidate"):
        st = _load(app)
        rec = st["undo"].pop(uid, None)
        if rec is None:
            return "That's undone already, or too old to undo."
        st["decided"].pop(rec.get("pair"), None)
        if rec.get("item") and rec["do"] != "gist":  # asked again (a gist put back is a new row: not the same pair)
            st["items"].append(rec["item"])
        jsave(state_file(app), st)
    if rec["do"] == "fact":
        from kurooto.modules.remember import add_line

        add_line(app, rec.get("section") or "You told me", rec["line"])
        said = "Put back."
    elif rec["do"] == "gist":
        from kurooto.core import ledger

        led = ledger.of(app)
        p = led.unseal("gist", base64.b64decode(rec["blob"]))
        if p is None:
            return "I can't open what was kept for the Undo."
        led.add("gist", p["text"], at=p["at"], sub=p.get("sub") or "")
        said = "The gist is back."
    elif rec["do"] == "deadline":
        dl = app.modules.get("deadlines")
        if dl is None:
            return "Deadlines is off."
        dl.move(str(rec["id"]), dt.datetime.fromisoformat(rec["due"]))
        said = "The deadline is back on its old date."
    else:
        return "ok"
    app.events.emit("dreaming_settle_undone", what=rec["do"])
    return said


def show(app: App) -> str:
    """/dream check: look now (rules, and the second opinion when allowed) and show what waits."""
    if not on(app):
        return "Consolidating is off (dreaming.consolidate)."
    new = scan(app, ai=True)
    text, _ = section(app, send=False)
    if not text:
        return "Nothing to consolidate: no duplicates or lines that disagree."
    return (f"{new} new. " if new else "") + text


__all__ = ["scan", "section", "button", "undo", "show", "read", "check", "WHEN"]
