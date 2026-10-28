"""Brain dreaming about the day (0.8.14): at night, while it sleeps, it goes over what the day held and brings a few
things to the morning message (modules/dreaming.py) for you to keep or drop. mind.dream.on turns all of it off, and
each part has its own switch, all with Brain:

    cards    (mind.dream.cards, on) 1 to 3 concepts you studied or wrote about that day (concept notes you changed,
             quiz cards you answered, study time on their subject) that its model of what you know (mind/tom) puts on
             your frontier (mind/frontier.py: not mastered, prerequisites solid) become quiz cards, written by the model
             on this computer from your own note (a plain "what is ...?" card without one; never a cloud AI). They wait
             in the morning message, each with Keep and Drop; a kept card goes into Quiz, first due about a day after
             it was written, marked as Kurooto's. /mind shows how you recall them next to your own cards.
    lessons  (mind.dream.lessons, on) the day's outcomes replayed: what you undid, the messages that went unanswered
             or got Less of this (the not-a-pest model's counts, mind/pest.py), the times you told Voice off, and its
             guesses about you that you marked wrong. Rules turn the clear patterns into 1 to 3 lines for your
             how-to-help-me note ("Fewer nudges in the evening"); Keep writes the line there (modules/remember.py,
             under "Learned in the nightly look back", with Undo), Not that drops it for good.
    voice    (mind.dream.voice, on) one line about the nightly voice learning (modules/voice/learn.py, 04:10): how many
             of yesterday's turns it learned from, and a misfire pattern seen twice or more ("it woke to your name
             at the end of a sentence 3 times"). Counts and flags only: no words.

The night's work runs at WHEN, the first of those times Brain is asleep (mind/sleep.py, when there) and its machine
can spare the GPU (mind/senses/intero.py's ok(), when there); at the last one it writes the cards without the model.
Nothing here is sent by itself: it all waits for the morning message. A line shown twice without a tap is let go.
Kept in `<state>/mind-dream.json`: the waiting cards and lines, and counts.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.mind import frontier

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.conceptgraph import Note

register_defaults(
    "mind",
    {
        "dream": {
            "on": True,  # Brain goes over the day at night, for the morning message (each piece has its switch too)
            "cards": True,  # nightly quiz cards for what you studied that's on your frontier, kept by a tap
            "cards_max": 3,  # at most this many a night (1 to 3)
            "lessons": True,  # nightly how-to-help-me lines from the day's outcomes, written only when you tap Keep
            "voice": True,  # one morning line on what the nightly voice learning saw (counts only)
            # 0.9.0: the lessons also learn from what the look back after calls flagged and from proposals you
            # discarded (counts only, never a call's words)
            "from_calls": True,
            "from_proposals": True,
        }
    },
)

PART = "dream"  # its switch: mind.dream.on (and one for each piece)
FILE = "mind-dream.json"
WHEN = "daily 00:15,01:15,02:15,03:15,04:15,05:15,06:15"  # after the journal (23:40) and the story (23:50)
LAST_HOUR = 6  # the last try of the night: the cards are written without the model if it couldn't run before
SHOWN_MAX = 2  # shown this many times without a tap: let go
PENDING_MAX = 12
LESSONS_MAX = 3
PATTERN_MIN = 2  # a voice misfire pattern is mentioned when seen this many times
REJECTED = ("ignored", "less", "mute")
CARD_PROMPT = (
    "Write one revision question from a student's own note, to test the idea in it. Reply with one line: the question, "
    "then ' :: ', then the answer in at most 25 words. Use only what the note says.\n"
    "Concept: {title}\nNote: {text}\nLine:"
)
PEST_WORDS = {
    "finding": "findings",
    "nudge": "nudges",
    "excitement": "excited or worried lines",
    "check-in": "check-ins",
}
FEATURE_WORDS = {
    "sorter": "sorting your files",
    "inferred": "setting things up from what you say",
    "learning": "learning skills from your requests",
    "revision": "the revision plan",
    "dreaming": "Dreaming's tidying",
    "rhythm": "moving your night hours",
    "plan": "rescheduling your plan",
    "retro": "the weekly look back's fixes",
    "handwritten": "linking handwritten notes",
    "class": "class catch-ups",
    "hook": "question follow-ups",
    "proposal": "proposed changes",
    "voiceid": "Voice ID adapting",
    "remember": "rechecking your how-to-help-me lines",
}
TOM_WORDS = {
    "knowledge": "what you know",
    "belief": "what you believe",
    "goal": "what you're aiming for",
    "pref": "what you prefer",
    "attention": "what you're paying attention to",
}
VOICE_PATTERNS = (  # (flag, value, words): what a told-off turn had in common
    ("where", "last", "it woke to your name at the end of a sentence"),
    ("where", "middle", "it woke to your name in the middle of a sentence"),
    ("name_near", True, "it woke to a word that only sounded like its name"),
    ("voices2", True, "it answered while two or more people were talking"),
    ("rule", "the conversation goes on", "it took the conversation going on as meant for it"),
    ("rule", "it follows the conversation", "it joined a conversation it was only following"),
    ("rule", "the local model", "it went with the local model's guess"),
    ("speaker", "guest", "it answered a voice that wasn't yours"),
)


# ----------------------------------------------------------------------------------------------------- switches
def cards_on(app: App) -> bool:
    return mind.part_on(app, PART) and bool(app.settings.get("mind.dream.cards"))


def lessons_on(app: App) -> bool:
    return mind.part_on(app, PART) and bool(app.settings.get("mind.dream.lessons"))


def voice_on(app: App) -> bool:
    return mind.part_on(app, PART) and bool(app.settings.get("mind.dream.voice"))


def cards_max(app: App) -> int:
    v = app.settings.get("mind.dream.cards_max")
    return max(1, min(3, int(v))) if isinstance(v, (int, float)) else 3


# ------------------------------------------------------------------------------------------------------- state
def _load(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    for k, v in (("nights", {}), ("cards", []), ("lessons", []), ("decided", {}), ("undo", {}), ("counts", {})):
        if not isinstance(d.get(k), type(v)):
            d[k] = v
    return d


def _save(app: App, d: dict) -> None:
    d["nights"] = dict(sorted(d["nights"].items())[-14:])
    d["cards"] = d["cards"][-PENDING_MAX:]
    d["lessons"] = d["lessons"][-PENDING_MAX:]
    d["decided"] = dict(list(d["decided"].items())[-500:])
    d["undo"] = dict(list(d["undo"].items())[-30:])
    jsave(app.paths.state / FILE, d)


def forget(app: App) -> None:
    (app.paths.state / FILE).unlink(missing_ok=True)


def _h(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode(), usedforsecurity=False).hexdigest()[:10]


def _span(day: dt.date) -> tuple[float, float]:
    lo = dt.datetime.combine(day, dt.time(0)).timestamp()
    return lo, lo + 86400.0


def the_day(t: dt.datetime | None = None) -> dt.date:
    """The day the night is about: the one that just ended (at 00:15 or 06:15 alike, yesterday)."""
    return ((t or now()) - dt.timedelta(hours=12)).date()


def _count(d: dict, key: str) -> None:
    d["counts"][key] = int(d["counts"].get(key) or 0) + 1


# ------------------------------------------------------------------------------------------- may it work now
def _gate(app: App) -> tuple[bool, str]:
    """(may the model run now, why not): Brain asleep, when its sleep (mind/sleep.py) is there, and the machine able
    to spare the GPU (mind/senses/intero.py's ok(), when there). Either missing counts as yes."""
    try:
        from kurooto.mind import sleep as msleep

        if getattr(msleep, "on", lambda a: True)(app) and msleep.state(app) == "awake":
            return False, "awake"
    except Exception:  # noqa: S110 (no sleep yet, or it failed: the night's times are the window)
        pass
    try:
        from kurooto.mind.senses import intero

        ok = getattr(intero, "ok", None)
        if ok is not None:
            fine, why = ok(app, "gpu")
            if not fine:
                return False, str(why or "busy")[:60]
    except Exception:  # noqa: S110
        pass
    return True, ""


# ------------------------------------------------------------------------------------------------- the cards
def studied(app: App, day: dt.date, notes: dict[str, Note]) -> list[str]:
    """Concepts he studied or wrote about that day, the strongest sign first: notes he changed, quiz cards he answered
    that name them, then study time on their subject."""
    from kurooto.mind.tom import knowledge

    lo, hi = _span(day)
    out: list[str] = []
    for slug, n in notes.items():
        try:
            if lo <= n.path.stat().st_mtime < hi:
                out.append(slug)
        except OSError:
            continue
    quiz = app.modules.get("quiz")
    if quiz is not None and app.is_on("quiz"):
        qdir = app.paths.state / "quiz"
        for f in sorted(qdir.glob("*.json")) if qdir.is_dir() else []:
            items = (jload(f, {}) or {}).get("items") if f.stem not in ("session", "offered", "cards") else None
            for it in (items or {}).values() if isinstance(items, dict) else []:
                if any(isinstance(g, dict) and g.get("date") == day.isoformat() for g in it.get("history") or []):
                    out += knowledge.mentions(str(it.get("text") or ""), notes)
    study = app.modules.get("study")
    if study is not None and app.is_on("study"):
        try:
            subjects = {k.split("|")[0] for k, v in study.day(day).items() if float(v or 0) >= 600}
        except Exception:
            subjects = set()
        for slug in notes:
            if subjects & set(slug.split("/")):
                out.append(slug)
    return list(dict.fromkeys(out))


def subject_of(app: App, note: Note) -> str | None:
    """The subject a concept note belongs to: a folder on its path that's one of yours, or the one its title names."""
    s = app.modules.get("subjects")
    if s is None or not app.is_on("subjects"):
        return None
    try:
        rel = note.path.relative_to(Path(app.workspace)).with_suffix("").parts
    except ValueError:
        rel = Path(note.slug).parts
    for part in reversed(rel):
        slug = s.resolve(part) or s.resolve(part.replace("-", " "))
        if slug:
            return slug
    found = s.find_in(note.title)
    return found[0] if len(found) == 1 else None


def _model_card(app: App, note: Note) -> tuple[str, str] | None:
    from kurooto.mind import tone

    mdl = tone.model(app)
    if not mdl:
        return None
    body = {
        "model": mdl,
        "prompt": CARD_PROMPT.format(title=note.title, text=(note.head or note.summary)[:1500]),
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 90},
    }
    try:
        with app.modules["local_models"].api("/api/generate", body, timeout=90) as r:
            said = str(json.loads(r.read().decode("utf-8")).get("response") or "")
    except Exception:
        return None
    line = next((ln.strip() for ln in said.splitlines() if "::" in ln), "")
    q, _, a = line.partition("::")
    q, a = re.sub(r"\s+", " ", q).strip(" -*\"'"), re.sub(r"\s+", " ", a).strip(" \"'")
    if not (12 <= len(q) <= 200 and q.endswith("?")) or not a:
        return None  # a reply that isn't one question and an answer: the plain card instead
    return q, a[:240]


def write_card(app: App, note: Note, use_model: bool = True) -> tuple[str, str, bool]:
    """(question, answer, whether the model wrote it): from the local model when it can, else a plain card."""
    got = _model_card(app, note) if use_model else None
    if got:
        return got[0], got[1], True
    return f"What is {note.title}, and when does it apply?", (note.summary or "")[:240], False


def make_cards(app: App, day: dt.date, use_model: bool = True) -> int:
    """The night's cards: concepts studied that day that are on his frontier, not carded before. How many."""
    if not cards_on(app) or not app.is_on("quiz"):
        return 0
    from kurooto.mind.tom import knowledge, model

    if not model.on(app):
        return 0
    notes = knowledge.concepts(app)
    ps = frontier.masteries(app)
    picks = [s for s in studied(app, day, notes) if frontier.on_frontier(s, notes, ps)]
    st = _load(app)
    seen = {c["slug"] for c in st["cards"]} | {k[2:] for k in st["decided"] if k.startswith("c:")}
    new = []
    for slug in [s for s in picks if s not in seen][: cards_max(app)]:
        q, a, by_model = write_card(app, notes[slug], use_model)  # the model's turn: outside the lock
        new.append({
            "ref": uuid.uuid4().hex[:8], "slug": slug, "title": notes[slug].title[:80], "q": q, "a": a,
            "subject": subject_of(app, notes[slug]), "made": now().date().isoformat(), "model": by_model, "shown": 0,
        })  # fmt: skip
    if new:
        with Lock(app.paths.state, "mind-dream"):
            st = _load(app)
            st["cards"] += new
            _save(app, st)
    return len(new)


# ------------------------------------------------------------------------------------------------ the lessons
def _ts(rec: dict) -> float | None:
    try:
        return dt.datetime.fromisoformat(str(rec["ts"])).timestamp()
    except (KeyError, ValueError):
        return None


def voice_rows(app: App, day: dt.date) -> list[dict]:
    """The nightly voice learner's rows for that day (modules/voice/learn.py): flags and a label, never words."""
    f = app.paths.state / "voice" / "gate-turns.jsonl"
    try:
        lines = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("day") == day.isoformat() and r.get("label") in (0, 1):
            out.append(r)
    return out


def voice_pattern(misfires: list[dict]) -> tuple[str, int] | None:
    """The commonest thing the told-off turns had in common, when it's PATTERN_MIN or more."""
    c: Counter = Counter()
    for r in misfires:
        flags = {**r, "voices2": (r.get("voices") or 0) >= 2, "name_near": bool(r.get("name_near"))}
        for key, val, words in VOICE_PATTERNS:
            if flags.get(key) == val:
                c[words] += 1
    if not c:
        return None
    words, n = c.most_common(1)[0]
    return (words, n) if n >= PATTERN_MIN else None


def outcomes(app: App, day: dt.date) -> dict:
    """The day's outcomes, counts only: undos per feature, unprompted messages turned down per (kind, time of day),
    told-off voice turns and their pattern, and its guesses about him marked wrong per part."""
    lo, hi = _span(day)
    undos: Counter = Counter()
    for rec in app.events.tail(20000):
        k = str(rec.get("kind") or "")
        if k.endswith(("_undone", "_undo")):
            t = _ts(rec)
            if t is not None and lo <= t < hi:
                undos[k.split("_")[0]] += 1
    pest: Counter = Counter()
    try:
        from kurooto.mind import pest as mpest

        for r in (jload(app.paths.state / mpest.FILE, {}) or {}).get("pending") or []:
            if r.get("done") in REJECTED and lo <= float(r.get("at") or 0) < hi:
                kind, band = (str(r.get("cell") or "").split("|") + ["", ""])[:2]
                if kind:
                    pest[(kind, band)] += 1
    except Exception:  # noqa: S110 (no pest counts: no lesson from them)
        pass
    rows = voice_rows(app, day)
    mis = [r for r in rows if r["label"] == 0]
    wrong: Counter = Counter()
    try:
        from kurooto.mind.tom import model

        for r in model.rows(app):
            if r.get("wrong") and lo <= float(r.get("updated") or 0) < hi:
                wrong[r["part"]] += 1
    except Exception:  # noqa: S110
        pass
    cases: Counter = Counter()  # (0.9.0) Wrong taps, by what the request did (mind.dream.from_wrong)
    calls = 0  # (0.9.0) lessons the look back after calls found (mind.dream.from_calls)
    made: dict = {}
    dropped: Counter = Counter()  # (0.9.0) proposals you discarded, by what made them (mind.dream.from_proposals)
    s = app.settings
    for rec in app.events.tail(20000):
        t, k = _ts(rec), str(rec.get("kind") or "")
        if k == "proposal_made":
            made[str(rec.get("id") or "")] = str(rec.get("source") or "")
        if t is None or not lo <= t < hi:
            continue
        if k == "case_kept" and rec.get("wrong") and s.get("mind.dream.from_wrong"):
            cases[str(rec.get("did") or "")] += 1
        elif k == "call_reviewed" and s.get("mind.dream.from_calls"):
            calls += int(rec.get("lessons") or 0)
        elif k == "proposal_discarded" and s.get("mind.dream.from_proposals"):
            dropped[made.get(str(rec.get("id") or ""), "") or "night"] += 1
    return {"undos": undos, "pest": pest, "voice": len(mis), "pattern": voice_pattern(mis), "wrong": wrong,
            "cases": cases, "calls": calls, "proposals": dropped}  # fmt: skip


def distil(out: dict) -> list[dict]:
    """Rules: the clear patterns in the day's outcomes as how-to-help-me lines, strongest first, at most LESSONS_MAX."""
    found: list[tuple[int, dict]] = []
    for (kind, band), n in out["pest"].items():
        if n >= 2:
            what = PEST_WORDS.get(kind, kind + "s")
            found.append((n, {"kind": "pest", "line": f"Fewer {what} in the {band or 'day'}",
                              "why": f"{n} went unanswered or got Less of this"}))  # fmt: skip
    for feature, n in out["undos"].items():
        if n >= 2:
            what = FEATURE_WORDS.get(feature, feature.replace("-", " "))
            found.append((n, {"kind": "undo", "line": f"Ask before {what} changes something by itself",
                              "why": f"you undid it {n} times"}))  # fmt: skip
    if out["pattern"]:
        words, n = out["pattern"]
        found.append((n, {"kind": "voice", "line": "In voice, answer only when your name comes first in what I say",
                          "why": f"{words} {n} times and was told off"}))  # fmt: skip
    for part, n in out["wrong"].items():
        found.append((n, {"kind": "wrong", "line": f"Ask me before assuming {TOM_WORDS.get(part, part)}",
                          "why": f"{n} guess{'es' if n != 1 else ''} about it marked wrong"}))  # fmt: skip
    for did, n in (out.get("cases") or {}).items():  # (0.9.0) Wrong taps
        if n < 2 or did in ("", "none", "sync", "other"):
            continue
        line = ("When a short request of mine isn't clear, ask what I meant before answering" if did == "ai"
                else f"Check with me before taking a request as {did.replace('_', ' ')}")  # fmt: skip
        found.append((n, {"kind": "case", "line": line, "why": f"{n} answers marked Wrong"}))
    if int(out.get("calls") or 0) >= 2:  # (0.9.0) the look back after calls
        n = int(out["calls"])
        found.append((n, {"kind": "calls", "line": "On calls, keep to the lessons from earlier calls (/lessons)",
                          "why": f"the look back after calls found {n} things to do better"}))  # fmt: skip
    for source, n in (out.get("proposals") or {}).items():  # (0.9.0) proposals you discarded
        if n >= 2:
            found.append((n, {"kind": "proposal", "line": f"Fewer proposals from {source.replace('_', ' ')}",
                              "why": f"you discarded {n}"}))  # fmt: skip
    found.sort(key=lambda x: -x[0])
    return [x[1] for x in found[:LESSONS_MAX]]


def propose_lessons(app: App, day: dt.date) -> int:
    if not lessons_on(app):
        return 0
    from kurooto.modules import remember

    try:
        f = remember.help_file(app)
        note = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""
    except Exception:
        note = ""
    found = distil(outcomes(app, day))
    n = 0
    with Lock(app.paths.state, "mind-dream"):
        st = _load(app)
        waiting = {x["h"] for x in st["lessons"]}
        for les in found:
            h = _h("l", les["line"])
            if h in waiting or f"l:{h}" in st["decided"] or (note and remember.has_line(note, les["line"])):
                continue
            st["lessons"].append({**les, "h": h, "ref": uuid.uuid4().hex[:8], "day": day.isoformat(), "shown": 0})
            n += 1
        _save(app, st)
    return n


# --------------------------------------------------------------------------------------------------- the night
def nightly(app: App, payload: dict | None = None) -> dict | None:
    """At WHEN: the cards (once a night, when the model may run, or plainly at the last try) and the lessons (once a
    night). Returns what it did, None with Brain off."""
    if not mind.on(app):
        return None
    t = now()
    day = the_day(t)
    key = day.isoformat()
    with Lock(app.paths.state, "mind-dream"):
        night = dict(_load(app)["nights"].get(key) or {})
    did: dict = {}
    if "lessons" not in night and lessons_on(app):
        did["lessons"] = night["lessons"] = propose_lessons(app, day)
    if "cards" not in night and cards_on(app):
        ok, why = _gate(app)
        last = LAST_HOUR <= t.hour < 12
        if ok or last:
            did["cards"] = night["cards"] = make_cards(app, day, use_model=ok)
        else:
            did["deferred"] = night["deferred"] = why
    with Lock(app.paths.state, "mind-dream"):
        st = _load(app)
        st["nights"][key] = {**(st["nights"].get(key) or {}), **night}
        _save(app, st)
    if did:
        app.events.emit("mind_dream_night", cards=int(did.get("cards") or 0), lessons=int(did.get("lessons") or 0),
                        deferred=bool(did.get("deferred")))  # fmt: skip
    return did


# ------------------------------------------------------------------------------------------------ the morning
def voice_line(app: App, day: dt.date | None = None) -> str:
    """Voice's night, in one line: the turns of that day it learned from and a misfire pattern. "" with nothing."""
    if not voice_on(app) or not app.is_on("voice") or not app.settings.get("voice.listen.learn_nightly"):
        return ""
    day = day or (now().date() - dt.timedelta(days=1))
    rows = voice_rows(app, day)
    if not rows:
        return ""
    mis = [r for r in rows if r["label"] == 0]
    line = f"Voice learned from {len(rows)} of yesterday's turn{'s' if len(rows) != 1 else ''} ({len(mis)} told off)"
    pat = voice_pattern(mis)
    if pat:
        line += f"; {pat[0]} {pat[1]} times"
    return line + "."


def section(app: App, send: bool) -> tuple[str, list]:
    """The morning message's part: (text, button rows). Only the sent message counts as showing a line."""
    if not mind.on(app):
        return "", []
    parts, buttons = [], []
    v = voice_line(app)
    if v:
        parts.append(v)
    with Lock(app.paths.state, "mind-dream"):
        st = _load(app)
        cards, lessons = [], []
        for kind, items, out in (("c", st["cards"], cards), ("l", st["lessons"], lessons)):
            keep = []
            for it in items:
                if send and int(it.get("shown") or 0) >= SHOWN_MAX:
                    st["decided"][f"{kind}:{it['slug'] if kind == 'c' else it['h']}"] = "let go"
                    continue
                keep.append(it)
                if len(out) < 3 and (kind == "l" or cards_on(app)) and (kind == "c" or lessons_on(app)):
                    out.append(it)
                    if send:
                        it["shown"] = int(it.get("shown") or 0) + 1
            items[:] = keep
        if send:
            _save(app, st)
    kept: list[str] = []
    if send:  # 0.8.16 (mind.act.more): what Brain is trusted to keep, it keeps itself and says so, with Undo
        for kind, out in (("c", cards), ("l", lessons)):
            for it in list(out):
                did = _auto_keep(app, kind, it)
                if did is None:
                    continue
                out.remove(it)
                kept.append(did["out"][0])
                buttons += [[(f"Undo: {(it.get('title') or it.get('line') or '')[:24]}", b[1]) for b in row]
                            for row in did["buttons"]]  # fmt: skip
    if kept:
        parts.append("Kept by itself (its trust in these is earned; Undo below takes one back):\n"
                     + "\n".join(f"- {k}" for k in kept))  # fmt: skip
    if cards:
        lines = []
        for n, c in enumerate(cards, 1):
            lines.append(f"{n}. {c['q']} ({c['title']})")
            buttons.append([(f"{n}: Keep", f"mdr:c{c['ref']}:keep"), (f"{n}: Drop", f"mdr:c{c['ref']}:drop")])
        parts.append(
            "Cards for what you studied (a kept one comes up in /quiz about a day after it was written; nothing is "
            "added until you tap Keep):\n" + "\n".join(lines)
        )
    if lessons:
        lines = []
        for n, les in zip("ABC", lessons, strict=False):
            lines.append(f"{n}. {les['line']} ({les['why']} on {_short(les['day'])})")
            buttons.append([(f"{n}: Keep", f"mdr:l{les['ref']}:keep"), (f"{n}: Not that", f"mdr:l{les['ref']}:no")])
        parts.append(
            "For your how-to-help-me note, from the day's outcomes (nothing is written until you tap Keep):\n"
            + "\n".join(lines)
        )
    return "\n\n".join(parts), buttons


def _short(day: str) -> str:
    try:
        return f"{dt.date.fromisoformat(day):%a %d %b}"
    except ValueError:
        return day


# ------------------------------------------------------------------------------------------------- the buttons
def button(app: App, ref: str, act: str) -> str:
    """mdr:c<ref>:keep|drop, mdr:l<ref>:keep|no, mdr:u<uid>:undo."""
    if not mind.on(app):
        return "Brain is off (Features → Brain)."
    kind, ref = ref[:1], ref[1:]
    if kind == "u":
        return undo(app, ref)
    with Lock(app.paths.state, "mind-dream"):
        st = _load(app)
        pool = st["cards"] if kind == "c" else st["lessons"] if kind == "l" else []
        it = next((x for x in pool if x["ref"] == ref), None)
        if it is None:
            return "That's settled already, or was let go."
        dkey = f"c:{it['slug']}" if kind == "c" else f"l:{it['h']}"
        if act in ("drop", "no"):
            pool.remove(it)
            st["decided"][dkey] = "dropped"
            _count(st, "cards_dropped" if kind == "c" else "lessons_dropped")
            _save(app, st)
            app.events.emit("mind_dream_answer", what="card" if kind == "c" else "lesson", how="dropped")
            return "Dropped." if kind == "c" else "Left out; I won't offer that one again."
        if act != "keep":
            return "unknown button"
    said = _keep(app, kind, ref)
    if isinstance(said, tuple):
        try:  # 0.8.16: a Keep is an OK for its kind (mind.act.more), so Brain's trust in keeping them can grow
            from kurooto.mind import act as _act

            _act.answered(app, KEEP_ACTION[kind], True)
        except ImportError:
            pass
        app.notify(said[0], kind="info", why="asked", buttons=[[("Undo", f"mdr:u{said[1]}:undo")]])
        return said[0][:190]
    return said


KEEP_ACTION = {"c": "dream.keep_card", "l": "dream.keep_lesson"}  # their kinds for Brain's trust (mind/act.py)


def _keep(app: App, kind: str, ref: str) -> tuple[str, str] | str:
    """Keep a waiting card (into Quiz) or lesson (into the how-to-help-me note): (what was said, its undo id), or a
    line saying why it couldn't be."""
    with Lock(app.paths.state, "mind-dream"):
        st = _load(app)
        pool = st["cards"] if kind == "c" else st["lessons"] if kind == "l" else []
        it = next((x for x in pool if x["ref"] == ref), None)
        if it is None:
            return "That's settled already, or was let go."
        dkey = f"c:{it['slug']}" if kind == "c" else f"l:{it['h']}"
        if kind == "c":
            quiz = app.modules.get("quiz")
            if quiz is None or not app.is_on("quiz"):
                return "Quiz is off, so the card can't go anywhere yet (Features → Quiz); it waits here."
            made = dt.date.fromisoformat(it["made"])
            due = max(made + dt.timedelta(days=1), now().date())
            iid = quiz.add_card(it.get("subject"), it["q"], by="kurooto", concept=it["slug"], due=due, answer=it["a"])
            if not iid:
                return "That card was too short to keep."
            rec = {"what": "card", "subject": quiz_subject(it), "iid": iid, "item": it, "key": dkey}
            said = f"Added to your quiz cards (first due {due:%a %d %b}): {it['q']}"
        else:
            from kurooto.modules.remember import LEARNED, add_line

            line = f"{it['line']} (from the day's outcomes, {it['day']})"
            if not add_line(app, LEARNED, line):
                pool.remove(it)
                st["decided"][dkey] = "kept"
                _save(app, st)
                return "It's in your how-to-help-me note already."
            rec = {"what": "lesson", "line": line, "item": it, "key": dkey}
            said = f"Added to your how-to-help-me note: {it['line']}"
        pool.remove(it)
        st["decided"][dkey] = "kept"
        _count(st, "cards_kept" if kind == "c" else "lessons_kept")
        uid = uuid.uuid4().hex[:8]
        st["undo"][uid] = {**rec, "at": time.time()}
        _save(app, st)
    app.events.emit("mind_dream_answer", what=rec["what"], how="kept")
    return said, uid


def _auto_keep(app: App, kind: str, it: dict) -> dict | None:
    """0.8.16 (mind.act.more): once Brain's trust in keeping its cards (R1) or lessons (R2) is earned, it keeps the
    morning's ones itself and the message says so, with Undo. None: it asks with Keep / Drop as before."""
    try:
        from kurooto.mind import act
    except ImportError:
        return None
    if kind == "c" and (app.modules.get("quiz") is None or not app.is_on("quiz")):
        return None
    _register_undo()
    return act.attempt(
        app,
        KEEP_ACTION[kind],
        lambda _: (lambda r: r if isinstance(r, tuple) else None)(_keep(app, kind, it["ref"])),
        summary=f"kept a {'quiz card' if kind == 'c' else 'how-to-help-me line'} from the night",
        undo_from=lambda out: {"uid": out[1]},
    )


def _register_undo() -> None:
    try:
        from kurooto.mind import act
    except ImportError:
        return
    for action in KEEP_ACTION.values():
        act.register(action, undoer=lambda app, p: undo(app, str((p or {}).get("uid") or "")))


def quiz_subject(it: dict) -> str:
    from kurooto.modules.quiz import CARD_FALLBACK, slugify

    return slugify(it.get("subject") or "") or CARD_FALLBACK


def undo(app: App, uid: str) -> str:
    with Lock(app.paths.state, "mind-dream"):
        st = _load(app)
        rec = st["undo"].pop(uid, None)
        if rec is None:
            return "That's undone already, or too old to undo."
        if rec["what"] == "card":
            quiz = app.modules.get("quiz")
            gone = bool(quiz is not None and quiz.remove_card(rec["subject"], rec["iid"]))
            _count(st, "cards_undone")
            st["counts"]["cards_kept"] = max(0, int(st["counts"].get("cards_kept") or 0) - 1)
            where = "your quiz cards"
        else:
            from kurooto.modules.remember import remove_line

            gone = remove_line(app, rec["line"])
            st["counts"]["lessons_kept"] = max(0, int(st["counts"].get("lessons_kept") or 0) - 1)
            where = "your how-to-help-me note"
        st["decided"].pop(rec["key"], None)
        _save(app, st)
    app.events.emit("mind_dream_undone", what=rec["what"])
    return f"Taken out of {where}." if gone else f"It had changed in {where} since, so it's left as it is."


# ------------------------------------------------------------------------------------------------ the measures
def recall(app: App) -> dict:
    """Graded answers on Kurooto's cards and on your own (3 or more out of 5 counts as recalled): {"mine": [right, n],
    "kurooto": [right, n]}. Information only."""
    out = {"mine": [0, 0], "kurooto": [0, 0]}
    qdir = app.paths.state / "quiz"
    for f in sorted(qdir.glob("*.json")) if qdir.is_dir() else []:
        if f.stem in ("session", "offered", "cards"):
            continue
        items = (jload(f, {}) or {}).get("items")
        for it in items.values() if isinstance(items, dict) else []:
            if not isinstance(it, dict):
                continue
            who = "kurooto" if it.get("by") == "kurooto" else "mine"
            for g in it.get("history") or []:
                if isinstance(g, dict) and isinstance(g.get("q"), (int, float)):
                    out[who][1] += 1
                    out[who][0] += int(g["q"] >= 3)
    return out


def _pct(right: int, n: int) -> str:
    return f"{right}/{n} ({right / n:.0%})" if n else "none yet"


def mind_lines(app: App) -> list[str]:
    """For /mind: the cards kept and dropped, recall on them next to your own cards, and the lessons kept."""
    if not mind.on(app):
        return []
    c = _load(app)["counts"]
    out = []
    if cards_on(app) or c.get("cards_kept") or c.get("cards_dropped"):
        r = recall(app)
        out.append(
            f"Dream cards: {int(c.get('cards_kept') or 0)} kept, {int(c.get('cards_dropped') or 0)} dropped; recalled "
            f"{_pct(*r['kurooto'])} on them, {_pct(*r['mine'])} on your own cards."
        )
    if lessons_on(app) or c.get("lessons_kept") or c.get("lessons_dropped"):
        out.append(
            f"Dream lessons: {int(c.get('lessons_kept') or 0)} kept in your how-to-help-me note, "
            f"{int(c.get('lessons_dropped') or 0)} left out."
        )
    return out


_register_undo()  # Undo under what Brain kept by itself works after a restart too

__all__ = ["nightly", "section", "button", "undo", "recall", "mind_lines", "voice_line", "outcomes", "distil", "WHEN"]
