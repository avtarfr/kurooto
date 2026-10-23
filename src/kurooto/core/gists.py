"""Gists: conversations settle, the way memories do. Before Retention (core/retention.py) lets the words of a call, a
request or a chat fade (privacy.keep_days, when you set it, or /forget), it settles into one line of what was decided
or done: the meaning stays, the wording goes. The daily job lets words fade only once their gist exists.

    call      what the call was for and what its tools did ("set reminder: I'll remind you Fri 23 Oct at 09:00: ..."),
              from the call's own record of them, kept next to its transcript (<transcript>.did.json); tools that
              only read are named, never what they read. An older call without that record: the tools the event log
              saw during it, by name
    request   your own AI request: its title, how it ended and its run receipt (core/jobs.py), never the answer
    chat      a chat turn: its request's name (the first 80 characters, as Chat titles it), once

Rules only. With privacy.gist_model on and Local AI models on, a model on this computer adds one sentence of what a
call decided; never a cloud AI. A line that looks like a health, money or password detail (modules/remember.py's
rules) keeps only its kind and outcome.

Kept in the memory ledger (core/ledger.py: encrypted, in Kurooto's state folder, never in your notes) for good, or
privacy.gist_days when you set it (before 0.5.18 they were in gists.jsonl, moved there on first use). /gists shows the
latest, /gists <words> finds them, /gists forget 3 drops one. /forget 7d keeps them; /forget all asks.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "privacy",
    {
        "keep_gist": True,  # as a conversation's words fade, it settles into one line of what it decided (/gists)
        "gist_days": 0,  # gists go after this many days (0: kept for good, until you /forget all)
        "gist_model": False,  # a model on this computer (Local AI models) adds a sentence to a call's gist
    },
)

LINE_MAX = 300
SHOWN = 10  # /gists shows this many
DID = ".did.json"  # next to a transcript: what the call's tools did
READS = {"searched notes", "searched past answers", "read", "looked through files", "read books"}
OUTCOME = {"cancelled": "cancelled", "timeout": "ran out of time", "stuck": "got stuck"}
LOCAL_PROMPT = (
    "Below is a phone call between an assistant and its user. In one short sentence (at most 25 words), say what was "
    "decided or done. Nothing else; no names of other people, nothing about health or money.\n\n"
)


def on(app: App) -> bool:
    return bool(app.settings.get("privacy.keep_gist"))


def gists_file(app: App) -> Path:
    return Path(app.paths.state) / "gists.jsonl"


def _one(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _safe(text: str, kind: str) -> str:
    """A line that looks like a health, money or password detail keeps only what kind it was."""
    from kurooto.modules.remember import WHAT, sensitive

    what = sensitive(text)
    return f"{kind} about something {WHAT[what]} (its words aren't kept)" if what else text


# --------------------------------------------------------------------------------------------- calls
def note_call(transcript: Path, purpose: str, used: list[dict]) -> None:
    """Keep what a call's tools did next to its transcript (modules/calls:Calls.save_transcript); the gist is made
    from it when the transcript is forgotten, and it goes with the transcript."""
    try:
        side = transcript.with_name(transcript.stem + DID)
        did = [{"name": str(u.get("name") or ""), "result": str(u.get("result") or "")[:300]} for u in used or []]
        jsave(side, {"purpose": str(purpose or "")[:120], "did": did})
    except OSError:
        pass  # the transcript matters more than its gist


def _did(did: list[dict]) -> list[str]:
    from kurooto.core.jobs import ACTS

    out, reads = [], {}
    for d in did:
        name, res = str(d.get("name") or ""), _one(d.get("result") or "", 110)
        verb, noun = ACTS.get(name, ("", ""))
        if res.startswith(("That failed", "There's no", "I couldn't")):
            out.append(f"{name} failed")
        elif verb and verb not in READS:
            label = f"{verb} {noun}".strip()
            out.append(f"{label}: {res}" if res else label)
        else:
            reads[name] = reads.get(name, 0) + 1
    if reads:
        out.append("used " + ", ".join(reads))
    return out


def _call_tools_seen(app: App, lo: float, hi: float) -> list[str]:
    """The tools the event log saw calls use in [lo, hi), by name (for calls from before .did.json)."""
    names = []
    for ln in app.events.lines():
        try:
            rec = json.loads(ln)
            t = dt.datetime.fromisoformat(rec["ts"]).timestamp()
        except (ValueError, KeyError, TypeError):
            continue
        if t < lo:
            break
        if t < hi and rec.get("kind") == "calls_tool" and rec.get("name") not in names:
            names.append(str(rec.get("name")))
    return list(reversed(names))


def call_line(app: App, f: Path, when: float, before: float, local: bool = True) -> str:
    """One call's gist, from its .did.json (else the event log between the call before and this one). local=False:
    never a model, even when privacy.gist_model allows one (the ledger's gists of what's still kept)."""
    side = f.with_name(f.stem + DID)
    rec = jload(side, None) if side.exists() else None
    if isinstance(rec, dict):
        purpose, acts = rec.get("purpose") or "", _did(rec.get("did") or [])
    else:
        try:
            head = f.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
        except OSError:
            head = ""
        purpose = head[2:] if head.startswith("# ") else ""
        names = _call_tools_seen(app, max(before, when - 7200), when + 1)
        acts = [f"used {', '.join(names)}"] if names else []
    said = local_line(app, f) if local else ""
    line = "Call" + (f" ({_one(purpose, 60)})" if purpose else "") + ": " + ("; ".join(acts) or "nothing was set")
    return _safe(_one(line + (f". {said}" if said else ""), LINE_MAX), "a call")


def local_model(app: App) -> str | None:
    """The model on this computer a call's gist may use: privacy.gist_model on, Local AI models on, a helper model
    there. None otherwise (rules only)."""
    if not app.settings.get("privacy.gist_model") or not app.is_on("local_models"):
        return None
    lm = app.modules.get("local_models")
    try:
        have = lm.have()
        helpers = [m["tag"] for m in lm.wanted() if str(m.get("key", "")).startswith("helper")]
    except Exception:
        return None
    return next((t for t in helpers if t in have), None)


def local_line(app: App, f: Path) -> str:
    model = local_model(app)
    if not model:
        return ""
    try:
        text = f.read_text(encoding="utf-8", errors="replace")[-6000:]
        body = {
            "model": model,
            "prompt": LOCAL_PROMPT + text,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 60},
        }
        with app.modules["local_models"].api("/api/generate", body, timeout=120) as r:
            said = _one(json.loads(r.read()).get("response", ""), 160)
    except Exception as e:
        app.events.emit("gist_failed", what="local", error=f"{type(e).__name__}"[:60])
        return ""
    return "" if not said else said


def _calls(app: App, lo: float, hi: float, local: bool = True) -> list[dict]:
    from kurooto.core.retention import TRANSCRIPT, _in, _mtime

    d = Path(app.paths.state) / "calls" / "transcripts"
    out, before = [], 0.0
    for f in sorted(d.glob("*.txt")) if d.is_dir() else []:
        m = TRANSCRIPT.match(f.stem)
        try:
            t = dt.datetime.strptime(m.group(1), "%Y-%m-%d-%H%M%S").timestamp() if m else _mtime(f)
        except ValueError:
            t = _mtime(f)
        if _in(t, lo, hi):
            out.append({"at": t, "kind": "call", "text": call_line(app, f, t, before, local)})
        before = t or before
    return out


def _requests(app: App, lo: float, hi: float) -> list[dict]:
    out = []
    for title, status, verdict, receipt, when in app.jobs.ending(lo, hi):
        if not title or title == "(forgotten)":
            continue
        how = "answered" if status == "ok" else OUTCOME.get(verdict, "failed")
        line = " · ".join(x for x in (_one(title, 80), how, receipt) if x)
        out.append({"at": when, "kind": "request", "text": _safe(_one(line, LINE_MAX), "an AI request")})
    return out


def _chats(app: App, lo: float, hi: float) -> list[dict]:
    from kurooto.core.retention import _in

    f = Path(app.paths.state) / "chat" / "history.json"
    turns = (jload(f, []) or []) if f.exists() else []
    out = []
    for t in turns:
        if isinstance(t, dict) and _in(float(t.get("at") or 0), lo, hi):
            name = _one(str(t.get("user") or "").strip()[:80], 80)
            if name:
                out.append({"at": float(t["at"]), "kind": "chat", "text": _safe(name, "a chat")})
    return out


MAKERS = {"calls": _calls, "requests": _requests, "chats": _chats}


# ------------------------------------------------------------------------------------------- the store
def _old(app: App) -> list[dict]:
    """Gists from before the ledger (gists.jsonl, plain text)."""
    f = gists_file(app)
    out = []
    try:
        lines = f.read_text(encoding="utf-8").splitlines() if f.exists() else []
    except OSError:
        return []
    for ln in lines:
        try:
            g = json.loads(ln)
        except ValueError:
            continue
        if isinstance(g, dict) and g.get("text"):
            out.append(g)
    return out


def _move(app: App) -> None:
    """gists.jsonl (0.5.17) into the encrypted ledger, once; the plain file goes only after they're in."""
    if not gists_file(app).exists():
        return
    from kurooto.core import ledger

    old = _old(app)
    have = [{"at": r["at"], "kind": r["sub"], "text": r["text"]} for r in ledger.of(app).rows(("gist",))]
    _put(app, sorted([*have, *old], key=lambda g: g.get("at") or 0))
    gists_file(app).unlink(missing_ok=True)


def load(app: App) -> list[dict]:
    """Every gist, oldest first: {at, kind, text}. [] while the ledger's key can't be read."""
    from kurooto.core import ledger

    try:
        _move(app)
        return [{"at": r["at"], "kind": r["sub"], "text": r["text"]} for r in ledger.of(app).rows(("gist",))]
    except ledger.Locked:
        return []


def _put(app: App, items: list[dict]) -> None:
    from kurooto.core import ledger

    rows = [(float(g.get("at") or 0), str(g.get("kind") or ""), {"text": g["text"]}) for g in items]
    ledger.of(app).replace("gist", rows)


def _save(app: App, items: list[dict]) -> None:
    """All gists at once, into the ledger (raises ledger.Locked, changing nothing, while its key can't be read)."""
    _move(app)
    _put(app, items)


def keep(app: App, kind: str, lo: float, hi: float) -> int:
    """(retention, before a kind is forgotten) Make the gists of what [lo, hi) of that kind holds. A chat turn whose
    request already has its gist adds none. How many were made."""
    if not on(app) or kind not in MAKERS:
        return 0
    new = MAKERS[kind](app, lo, hi)
    if not new:
        return 0
    with Lock(app.paths.state, "gists"):
        have = load(app)
        names = {g["text"].split(" · ", 1)[0] for g in have if g.get("kind") in ("request", "chat")}
        names |= {g["text"].split(" · ", 1)[0] for g in new if g["kind"] == "request"}
        new = [g for g in new if g["kind"] != "chat" or g["text"] not in names]
        new = [{**g, "at": round(float(g["at"]), 1)} for g in new]
        made = {(g.get("kind"), g.get("at")) for g in have}  # made already (the words failed to go last time)
        new = [g for g in new if (g["kind"], g["at"]) not in made]
        _save(app, sorted([*have, *new], key=lambda g: g.get("at") or 0))
    if new:
        app.events.emit("gists_kept", what=kind, n=len(new))
    return len(new)


def drop_did(f: Path) -> None:
    """A forgotten transcript's .did.json goes with it."""
    f.with_name(f.stem + DID).unlink(missing_ok=True)


def expire(app: App, now: float | None = None) -> int:
    """(the daily Retention job) Gists older than privacy.gist_days go, when you set it. How many."""
    try:
        keep_days = max(0.0, float(app.settings.get("privacy.gist_days") or 0))
    except (TypeError, ValueError):
        keep_days = 0.0
    if not keep_days:
        return 0
    edge = (now or time.time()) - keep_days * 86400
    with Lock(app.paths.state, "gists"):
        have = load(app)
        left = [g for g in have if float(g.get("at") or 0) >= edge]
        if len(left) != len(have):
            _save(app, left)
    if len(have) - len(left):
        app.events.emit("gists_expired", n=len(have) - len(left))
    return len(have) - len(left)


def clear(app: App) -> int:
    """/forget all, when you chose to drop the gists too. How many went."""
    from kurooto.core import ledger

    with Lock(app.paths.state, "gists"):
        gists_file(app).unlink(missing_ok=True)
        n = ledger.of(app).drop("gist")
    return n


# ---------------------------------------------------------------------------------------------- /gists
def _row(i: int, g: dict) -> str:
    when = dt.datetime.fromtimestamp(float(g.get("at") or 0))
    return f"{i}. {when:%d %b %Y %H:%M} · {g['text']}"


def command(app: App, arg: str) -> str:
    """/gists: the latest; /gists <words>: the ones with all those words; /gists forget 3: drop number 3 (numbers
    count from the newest)."""
    arg = (arg or "").strip()
    items = list(reversed(load(app)))  # newest first; a gist's number is its place here
    m = re.fullmatch(r"(?i)(?:forget|drop|delete)\s+(\d{1,5})", arg)
    if m:
        n = int(m.group(1))
        if not 1 <= n <= len(items):
            return f"There's no gist {n}; /gists shows them with their numbers."
        gone = items.pop(n - 1)
        with Lock(app.paths.state, "gists"):
            _save(app, list(reversed(items)))
        app.events.emit("gist_forgotten")
        return f"Forgot it: {gone['text'][:200]}"
    if not items:
        why = "" if on(app) else " (privacy.keep_gist is off)"
        return (
            f"No gists yet{why}. As a conversation's words fade (privacy.keep_days, /forget), it settles into one "
            "line of what it decided, here."
        )
    words = [w for w in re.findall(r"\w+", arg.lower()) if w]
    hits = [(i, g) for i, g in enumerate(items, 1) if all(w in g["text"].lower() for w in words)]
    if not hits:
        return f"No gist has {arg!r}."
    head = f"Gists with {arg!r}" if words else "The latest gists"
    keep_days = app.settings.get("privacy.gist_days")
    kept = f"kept {keep_days} days" if keep_days else "kept until you /forget all"
    body = "\n".join(_row(i, g) for i, g in hits[:SHOWN])
    more = f"\n…and {len(hits) - SHOWN} more" if len(hits) > SHOWN else ""
    return f"{head} ({kept}; /gists forget 3 drops number 3):\n{body}{more}"[:3800]


__all__ = ["on", "note_call", "keep", "expire", "clear", "command", "load", "drop_did", "call_line"]
