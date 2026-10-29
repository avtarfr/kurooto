"""Dreaming folds what it learned into your profile: each night (04:50) it reads what you said since the last time (your
chats with Kurooto, your calls, the AI requests you made, your journal and daily notes) for lines that state something
lasting about you or how you like to be helped, and the morning message (modules/dreaming.py) offers a few, "For your
profile", each with Keep and Not that. Nothing is written until you tap Keep; each Keep has an Undo.

    about you     "I'm a second-year geology student", "I work as a data analyst", "my thesis is on sea ice"
                  -> a line in Kurooto's own block of your profile (about-me/profile.md; core/aboutyou.py), which goes
                     along with every AI request next to its In-brief part
    how to help   "don't call me before 9", "I prefer short answers", "I'm most focused in the evenings"
                  -> a line in your how-to-help-me note, under "Learned in the nightly look back" (modules/remember.py)

Every line keeps where it came from and when: "- I prefer short answers (from a call, 2026-10-23)". Your words are
kept as you said them, never reworded. Rules pick the lines: in the first person, a statement (not a question, not
"maybe" or "if"), not only about today, nothing already in the profile or the how-to-help-me note, nothing about
other people (a "he", "she", "my friend" or a phone number, so a forwarded or pasted message isn't learned from), and
never health, money or passwords. With dreaming.fold_ai "local" (the default) the model on this computer, when there
is one, takes a second look at each line the rules found and drops what isn't lasting; "main" asks your own AI (only
those lines go to it); "off" leaves it to the rules. Not that drops a line for good; a line shown twice without a tap
is let go. /dream fold looks now.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave, owner_only

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "dreaming",
    {
        "fold": True,  # offer lasting things you said for your profile in the morning message (Keep / Not that)
        "fold_ai": "local",  # a second look at what the rules found: local (this computer), main (your AI), off
        "fold_max": 3,  # at most this many in one morning message; the rest wait for the next ones
        "fold_inferred": True,  # also offer the projects and classes it set up from what you said (/inferred)
        "fold_inferred_max": 1,  # ...at most this many a morning, besides fold_max (never ahead of your own lines)
    },
)

WHEN = "daily 04:50"  # after consolidating (04:45)
FIRST_DAYS = 2  # the first look goes this far back
SHOWN_MAX = 2  # a line shown this many times without a tap is let go
PENDING_MAX = 20
AI_MAX = 8  # second looks a night
MIN, MAX = 12, 200  # characters a line may have
WHERE = {
    "chat": "a chat",
    "call": "a call",
    "request": "an AI request",
    "journal": "your journal",
    "inferred": "what it set up from what you said",
}
ROLE = re.compile(r"\((?P<role>[a-z][a-z -]{1,30})\)\s*$")
LEAD = r"^(?:(?:btw|fyi|also|oh|and|so|ok|okay|just so you know|for the record|for context)[,:]?\s+)*"
ABOUT = re.compile(
    LEAD + r"(?:i(?:'m| am) (?:a|an) (?!(?:bit|little|lot|while|few|tad|mess|wreck|sec|minute)\b)\w"
    r"|i(?:'m| am) (?:studying|majoring in|based in|from|learning|doing (?:a|an|my) (?:phd|ph\.d|master'?s|"
    r"bachelor'?s|degree|bs|ms|msc|bsc|ba|ma)\b|in (?:my )?(?:first|second|third|fourth|final|last|\d\w*) year)"
    r"|i (?:study|major in|work (?:at|as|for|in)|teach|live in|moved to|speak|grew up in)\b"
    r"|my (?:major|field|research(?: area)?|job|role|degree|programme|program|thesis|dissertation|team|time ?zone|"
    r"first language|native language|mother tongue|pronouns|department|university|college|school|company|"
    r"workplace) is\b)",
    re.I,
)
HELP = re.compile(
    LEAD + r"(?:(?:please\s+)?(?:don't|do not|never)\s+(?:call|message|text|ping|remind|wake|disturb|bother|notify)"
    r"\s+me\b|(?:please\s+)?(?:always|only)\s+(?:call|message|text|remind|give|tell|ask|answer|reply|write|show|"
    r"keep|send)\b|i (?:prefer|like it when you|'d rather you|would rather you|want you to|need you to|hate it when "
    r"you|don't like it when you|can't stand it when you)\b|i (?:like|prefer|want|need|hate|dislike) (?:short|shorter|"
    r"brief|long|longer|detailed|bullet|plain|simple|quick)\b|(?:keep|make) (?:your |the )?(?:answers|replies|"
    r"messages|reminders|summaries|explanations)\b|i(?:'m| am) (?:most |more |usually )?(?:productive|focused|"
    r"awake|alert|free|busy|unavailable|asleep|offline) (?:in|on|at|before|after|until|between|every|most|during)\b"
    r"|i (?:usually|normally|always|never) (?:wake|sleep|study|work|go to bed|get up|check)\b)",
    re.I,
)
SKIP = re.compile(
    r"\b(?:today|tonight|tomorrow|yesterday|this (?:morning|afternoon|evening|week|weekend)|right now|at the moment|"
    r"for now|just now|later|if|maybe|might|perhaps|probably|not sure|i think|i guess|i wonder|could you|can you|"
    r"would you|should i|remember that|keep in mind)\b",
    re.I,
)
ASKS = re.compile(
    r"(?i)^\s*(?:what|when|why|how|who|where|which|(?:do|does|did|can|could|should|would|will|shall|am|is|are|was|"
    r"were|have|has)\s+(?:i|we|you|he|she|they|it|there|my|our|the|a|an)\b)"
)
AI_PROMPT = (
    "A line someone said to their personal assistant. Answer with one word: KEEP if it states something lasting about "
    "them (who they are, what they study or do) or how they like to be helped; SKIP if it's only about now, about "
    "someone else, a joke, a quote or not about them.\n\nLine: {line}\n"
)


def on(app: App) -> bool:
    return bool(app.settings.get("dreaming.fold"))


def state_file(app: App) -> Path:
    return Path(app.paths.state) / "dreaming-fold.json"


def _load(app: App) -> dict:
    st = jload(state_file(app), {}) or {}
    for k, v in (("items", []), ("decided", {}), ("undo", {}), ("marks", {})):
        st.setdefault(k, v)
    return st


def _save(app: App, st: dict) -> None:
    jsave(state_file(app), st)
    owner_only(state_file(app))  # your words wait here until you tap


def _h(text: str) -> str:
    return hashlib.sha256(_norm(text).encode("utf-8")).hexdigest()[:16]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _sentences(text: str) -> list[str]:
    return [s.strip(" -*\t") for s in re.split(r"(?<=[.!?])\s+|\n+", str(text or "")) if s.strip(" -*\t")]


# ------------------------------------------------------------------------------------------------ the rules
def kind_of(sentence: str) -> str:
    """ "about" (a lasting fact about you), "help" (how you like to be helped) or "" (nothing to keep)."""
    from kurooto.modules.learning import OTHERS
    from kurooto.modules.remember import sensitive

    s = re.sub(r"\s+", " ", sentence).strip()
    if not MIN <= len(s) <= MAX or s.endswith("?") or ASKS.match(s) or SKIP.search(s):
        return ""
    if sensitive(s) or OTHERS.search(s):  # never health, money, passwords, or anyone else
        return ""
    if HELP.search(s):
        return "help"
    if ABOUT.search(s):
        return "about"
    return ""


def tidy(sentence: str) -> str:
    s = re.sub(r"\s+", " ", sentence).strip().rstrip(".!")
    s = re.sub(LEAD, "", s, flags=re.I).strip()
    return s[:1].upper() + s[1:]


# ------------------------------------------------------------------------------------------------ what you said
def _since(st: dict, name: str) -> float:
    return float(st["marks"].get(name) or (time.time() - FIRST_DAYS * 86400))


def said(app: App, st: dict) -> list[tuple[str, str, float]]:
    """(source, sentence, when) for everything you said since the last look; the marks move on in st."""
    out: list[tuple[str, str, float]] = []
    lo = _since(st, "chat")  # your chats with Kurooto (your own turns)
    top = lo
    from kurooto.core import nightread

    for t in nightread.turns(app):  # (0.9.1) the one read shared with infer and the history index
        at = float(t.get("at") or 0)
        if at > lo:
            top = max(top, at)
            out += [("chat", s, at) for s in _sentences(str(t.get("user") or "")[:2000])]
    st["marks"]["chat"] = top
    lo = _since(st, "request")  # the AI requests you made (not background work)
    top = lo
    try:
        from kurooto.modules.learning import asked

        for _jid, _title, prompt, _result, finished, lane, then in app.jobs.finished_since(lo):
            top = max(top, float(finished or 0))
            if lane == "you" and not then:
                out += [("request", s, float(finished)) for s in _sentences(asked(prompt)[:2000])]
    except Exception as e:  # the jobs store mid-write: next night
        app.events.emit("dreaming_check_failed", error=f"fold requests: {type(e).__name__}"[:200])
    st["marks"]["request"] = top
    lo = _since(st, "call")  # your lines on calls
    top = lo
    d = Path(app.paths.state) / "calls" / "transcripts"
    for f in sorted(d.glob("*.txt")) if d.is_dir() else []:
        try:
            mt = f.stat().st_mtime
            if mt <= lo:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")[:30000]
        except OSError:
            continue
        top = max(top, mt)
        for ln in text.splitlines():
            who, _, words = ln.partition(": ")
            if words and who not in (app.name, "(note)", "?") and not ln.startswith("#"):
                out += [("call", s, mt) for s in _sentences(words)]
    st["marks"]["call"] = top
    lo = _since(st, "journal")  # your journal and daily notes: your own lines, not Kurooto's blocks
    top = lo
    from kurooto.core import layout
    from kurooto.core.graphwrite import outside

    day = dt.date.fromtimestamp(lo) - dt.timedelta(days=1)
    while day <= now().date():
        f = layout.path(app, "daily", date=day.isoformat())
        day += dt.timedelta(days=1)
        try:
            if not f.is_file() or f.stat().st_mtime <= lo:
                continue
            mt = f.stat().st_mtime
            text = outside(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        top = max(top, mt)
        text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
        for ln in text.splitlines():
            if ln.strip() and not ln.lstrip().startswith(("#", ">", "|")):
                out += [("journal", s, mt) for s in _sentences(re.sub(r"^\s*[-*+]\s+(?:\[[ xX]\]\s+)?", "", ln))]
    st["marks"]["journal"] = top
    return out


def known(app: App) -> list[str]:
    """What's already kept: your profile and your how-to-help-me note, line by line."""
    from kurooto.modules.remember import help_file

    out = []
    for f in (getattr(app, "about", None) and app.about.profile_file, help_file(app)):
        try:
            out += [ln.strip(" -*") for ln in f.read_text(encoding="utf-8", errors="replace").splitlines()]
        except (OSError, AttributeError, TypeError):
            continue
    return [x for x in out if x]


def _is_known(line: str, have: list[str]) -> bool:
    from kurooto.modules.learning import similar

    n = _norm(line)
    return any(n and (n in _norm(x) or similar(line, x)) for x in have)


def second_look(app: App, items: list[dict]) -> list[dict]:
    """The lines the second look keeps (all of them when it's off or there's no model to ask)."""
    how = str(app.settings.get("dreaming.fold_ai") or "off").strip().lower()
    if how not in ("local", "main") or not items:
        return items
    from kurooto.modules.consolidate import _brain

    brain = _brain(app, how)
    if brain is None:
        return items
    out = []
    for i, it in enumerate(items):
        if i >= AI_MAX:
            out.append(it)
            continue
        try:
            r = brain.complete(AI_PROMPT.format(line=it["text"][:300]), effort="low", timeout=60)
        except Exception as e:
            app.events.emit("dreaming_check_failed", error=f"fold ai: {type(e).__name__}"[:200])
            return out + items[i:]
        word = (getattr(r, "text", "") or "").strip().upper() if getattr(r, "ok", False) else "KEEP"
        if not word.startswith("SKIP"):
            out.append(it)
    app.events.emit("dreaming_second_look", asked=min(len(items), AI_MAX), kept=len(out), how=how)
    return out


# ------------------------------------------------------------------------------------------------ the scan
def scan(app: App, ai: bool = True) -> int:
    """Read what you said since the last look; new lines join the ones waiting. How many were new. Nothing is
    written to your notes."""
    if not on(app):
        return 0
    with Lock(app.paths.state, "dreaming-fold"):
        st = _load(app)
        heard = said(app, st)
        have = known(app) + [it["text"] for it in st["items"]]
        found = []
        for src, sentence, at in heard:
            kind = kind_of(sentence)
            if not kind:
                continue
            text = tidy(sentence)
            h = _h(text)
            if h in st["decided"] or _is_known(text, have):
                continue
            have.append(text)
            found.append({"ref": uuid.uuid4().hex[:8], "h": h, "kind": kind, "text": text, "src": src,
                          "day": dt.date.fromtimestamp(at).isoformat(), "shown": 0})  # fmt: skip
        for text, at in inferred(app):  # Kurooto's own summaries: no second look needed, never a name
            h = _h(text)
            if h in st["decided"] or _is_known(text, have):
                continue
            have.append(text)
            found.append({"ref": uuid.uuid4().hex[:8], "h": h, "kind": "about", "text": text, "src": "inferred",
                          "day": dt.date.fromtimestamp(at).isoformat(), "shown": 0})  # fmt: skip
        st["scanned"] = time.time()
        _save(app, st)
    if ai:
        mine = second_look(app, [f for f in found if f["src"] != "inferred"])  # outside the lock: a model is slow
        found = mine + [f for f in found if f["src"] == "inferred"]
    with Lock(app.paths.state, "dreaming-fold"):
        st = _load(app)
        st["items"] = (st["items"] + found)[-PENDING_MAX:]
        _save(app, st)
    if found:
        app.events.emit("dreaming_fold_found", n=len(found))
    return len(found)


def inferred(app: App) -> list[tuple[str, float]]:
    """dreaming.fold_inferred (0.9.0): the projects and classes core/infer.py set up and you didn't undo, each as a line
    for your profile in Kurooto's words, with a role and never a name ("I have a project with my supervisor on glacier
    flow", "I have a weekly Linear Algebra lab (Mon 09:00)"). (line, when it was set up)."""
    if not app.settings.get("dreaming.fold_inferred"):
        return []
    from kurooto.core import infer

    out = []
    for it in infer._load(app).get("items") or []:  # noqa: SLF001
        if it.get("undone"):
            continue
        u = it.get("undo") or {}
        if it.get("kind") == "project":
            m = ROLE.search(str(u.get("with") or ""))
            role = m["role"] if m else "supervisor"
            rel = Path(str(u.get("file") or "x")).parent.name.replace("-", " ").strip()
            who = str(u.get("with") or "").removeprefix("With:").split("(")[0].strip().lower()
            last = who.split()[-1] if who else ""
            topic = (
                ""
                if not rel or (last and last in rel.lower()) or rel.lower().startswith(("project", "thesis"))
                else rel
            )
            line = f"I have a project with my {role}" + (f" on {topic}" if topic else "")
        elif it.get("kind") == "class" and isinstance(u.get("class"), dict):
            c, subj = u["class"], app.modules.get("subjects")
            name = subj.name_of(c.get("subject", "")) if subj is not None else c.get("subject", "")
            what = (
                "lab"
                if " lab " in f" {it.get('line', '')} "
                else "tutorial"
                if "tutorial" in str(it.get("line"))
                else "class"
            )
            line = f"I have a weekly {name} {what} ({str(c.get('day', '')).title()} {c.get('start', '')})"
        else:
            continue
        out.append((line, float(it.get("at") or time.time())))
    return out


# ------------------------------------------------------------------------------------------- the morning
def target(app: App, kind: str) -> str:
    from kurooto.core import layout
    from kurooto.modules.remember import help_rel

    return layout.rel(app, "profile") if kind == "about" else help_rel(app)


def _when(day: str) -> str:
    try:
        return f"{dt.date.fromisoformat(day):%d %b}"
    except ValueError:
        return day


def section(app: App, send: bool) -> tuple[str, list]:
    """The morning message's part: ("For your profile ...", button rows). Only the sent message counts as showing a
    line."""
    if not on(app):
        return "", []
    st = jload(state_file(app), {}) or {}
    if time.time() - float(st.get("scanned") or 0) > 20 * 3600:
        try:
            scan(app, ai=False)
        except Exception as e:  # never at the cost of the morning message
            app.events.emit("dreaming_check_failed", error=f"fold: {type(e).__name__}: {e}"[:200])
    try:
        most = max(1, int(app.settings.get("dreaming.fold_max") or 3))
    except (TypeError, ValueError):
        most = 3
    try:  # Kurooto's own summaries have a cap of their own: they never take one of your lines' places
        also = max(0, int(app.settings.get("dreaming.fold_inferred_max") or 0))
    except (TypeError, ValueError):
        also = 1
    lines, buttons, mine, extra = [], [], 0, 0
    with Lock(app.paths.state, "dreaming-fold"):
        st = _load(app)
        keep = []
        for it in st["items"]:
            if it["h"] in st["decided"]:
                continue
            if send and int(it.get("shown") or 0) >= SHOWN_MAX:
                continue  # shown twice and left: let go
            keep.append(it)
            if it.get("src") == "inferred":
                if extra >= also:
                    continue
                extra += 1
            else:
                if mine >= most:
                    continue
                mine += 1
            n = len(lines) + 1
            to = "your profile" if it["kind"] == "about" else "how to help you"
            lines.append(f'{n}. "{it["text"]}" ({WHERE.get(it["src"], it["src"])}, {_when(it["day"])}) → {to}')
            buttons.append([(f"{n}: Keep", f"dfo:{it['ref']}:keep"), (f"{n}: Not that", f"dfo:{it['ref']}:no")])
            if send:
                it["shown"] = int(it.get("shown") or 0) + 1
        if send:
            st["items"] = keep
            _save(app, st)
    if not lines:
        return "", []
    head = "For your profile (what you said that seems to last; nothing is written until you tap Keep):"
    return head + "\n" + "\n".join(lines), buttons


def button(app: App, ref: str, act: str) -> str:
    """dfo:<item>:keep|no under the morning message; dfo:<undo>:undo after a Keep."""
    if act == "undo":
        return undo(app, ref)
    with Lock(app.paths.state, "dreaming-fold"):
        st = _load(app)
        it = next((x for x in st["items"] if x["ref"] == ref), None)
        if it is None or it["h"] in st["decided"]:
            return "That's settled already."
        st["items"] = [x for x in st["items"] if x is not it]
        if act == "no":
            st["decided"][it["h"]] = "no"
            _save(app, st)
            app.events.emit("dreaming_fold", how="no", kind=it["kind"])
            return "Left out; I won't offer that one again."
        if act != "keep":
            return "unknown button"
        line = f"{it['text']} (from {WHERE.get(it['src'], it['src'])}, {it['day']})"
        if it["kind"] == "about":
            if not hasattr(app, "about"):
                return "Your profile isn't available here."
            added = app.about.add_learned(line)
        else:
            from kurooto.modules.remember import LEARNED, add_line

            added = add_line(app, LEARNED, line)
        st["decided"][it["h"]] = "kept"
        uid = ""
        if added:
            uid = uuid.uuid4().hex[:8]
            st["undo"][uid] = {"kind": it["kind"], "line": line, "item": it, "at": time.time()}
            st["undo"] = dict(list(st["undo"].items())[-30:])
        _save(app, st)
    app.events.emit("dreaming_fold", how="keep", kind=it["kind"], src=it["src"])
    where = target(app, it["kind"])
    if not added:
        return f"It's in {where} already."
    said_ = f"Added to {where}: {it['text']}"
    app.notify(said_, kind="info", why="asked", buttons=[[("Undo", f"dfo:{uid}:undo")]])
    return said_[:190]


def undo(app: App, uid: str) -> str:
    with Lock(app.paths.state, "dreaming-fold"):
        st = _load(app)
        rec = st["undo"].pop(uid, None)
        if rec is None:
            return "That's undone already, or too old to undo."
        if rec["kind"] == "about":
            gone = app.about.remove_learned(rec["line"]) if hasattr(app, "about") else False
        else:
            from kurooto.modules.remember import remove_line

            gone = remove_line(app, rec["line"])
        st["decided"].pop(rec["item"]["h"], None)
        st["items"].append({**rec["item"], "shown": 0})  # offered again, in case the Keep was a slip
        _save(app, st)
    app.events.emit("dreaming_fold_undone", kind=rec["kind"])
    where = target(app, rec["kind"])
    if not gone:
        return f"That line changed in {where} since, so it's left as it is."
    return f"Taken out of {where}."


def show(app: App) -> str:
    """/dream fold: look now and show what waits."""
    if not on(app):
        return "Folding what I learn into your profile is off (dreaming.fold)."
    new = scan(app, ai=True)
    text, _ = section(app, send=False)
    if not text:
        return "Nothing new to add to your profile from what you said lately."
    return (f"{new} new. " if new else "") + text


__all__ = ["scan", "section", "button", "undo", "show", "kind_of", "WHEN"]
