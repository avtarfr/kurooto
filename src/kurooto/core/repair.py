"""Repair with two readings: when a short request could be either of two instant requests, ask which, with both as
buttons, instead of guessing.

When an instant request's own pattern takes your words, it runs as always (the first one that does): that's no
guess. When none does, each request with an example phrasing (from its description: "what's due, deadlines this
week") close to your words is a reading, scored by that closeness (difflib, 0 to 1, on the words as modules/cases.py
compares them), and runs as that example says it. Only examples with nothing to fill in (no time, no name) count, and
never a request that sends, deletes, calls, rings or approves (modules/cases.py: learnable).
When the best two are different requests, both at least MIN and within CLOSE of each other, you get 'Did you mean
"what's due" or "what's on today"?' with [what's due] [what's on today] [Neither]. Otherwise nothing changes: it goes
on as before (to your AI with Chat on). Neither does that too.

A tap runs that reading. After two repairs of the same phrasing to the same request it's taught, through Wrong button
and test cases (modules/cases.py: Cases.repaired, then teach, which learns it only if every test case that passed
still passes), with a line and Undo; a phrasing that's a test case already is taken as it says, without asking. Only
on Telegram and the phone app, where a button can be tapped. Setting repair.on (on).

The question waits for a tap in the state folder (repair.json, the last 20, for a day), so a tap after a restart still
works. Rules only: no AI, nothing leaves the computer.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.base import Incoming, Intent, Module

register_defaults("repair", {"on": True})  # two close readings of a request: ask which, with both as buttons
FILE = "repair.json"
BUTTONS = ("telegram", "app")  # channels where a tap comes back
KEEP, KEEP_H = 20, 24
MIN = 0.75  # a near example counts as a reading from this closeness
CLOSE = 0.08  # ...and two readings are close when their scores are this near


def _intents(m: Module) -> list[Intent]:
    try:
        return list(m.intents() or [])
    except Exception:
        return []


def _match(it: Intent, text: str):
    try:
        return it.match(text)
    except Exception:
        return None


def examples(it: Intent) -> list[str]:
    """A request's example phrasings, from its description: "what's due, deadlines this week" -> two."""
    return [p.strip().strip("\"'“”") for p in re.split(r",\s*|;\s*|\s+or\s+", it.description or "") if p.strip()]


def _blank(slots) -> bool:
    return isinstance(slots, dict) and not any(v not in (None, "", [], {}) for v in slots.values())


def _label(text: str) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= 32 else text[:31].rstrip() + "…"


def readings(plain: str, mods: list[Module], asks: bool) -> list[dict]:
    """The requests this could be, best first, one row each: {"intent", "score", "means" (the words it runs with),
    "label"}. None when a request's own pattern takes it (that one runs, as always)."""
    from kurooto.modules.cases import learnable, norm
    from kurooto.modules.text import tidy

    key = norm(plain)
    near: dict[str, dict] = {}
    for m in mods:
        for it in _intents(m):
            if asks and not it.questions:
                continue
            if _match(it, plain) is not None:
                return []
            if not learnable(it) or not key:
                continue
            for ex in examples(it):
                t = tidy(ex)
                if not _blank(_match(it, t)):
                    continue
                score = SequenceMatcher(None, key, norm(t)).ratio()
                if score > near.get(it.name, {}).get("score", 0):
                    near[it.name] = {"intent": it.name, "score": round(score, 3), "means": t, "label": _label(t)}
    return sorted(near.values(), key=lambda r: -r["score"])


def close(rows: list[dict]) -> bool:
    return len(rows) >= 2 and rows[1]["score"] >= MIN and rows[0]["score"] - rows[1]["score"] <= CLOSE


def offer(app: App, msg: Incoming, plain: str, mods: list[Module], asks: bool) -> bool:
    """Ask which of two close readings this is (or run the one a test case names). True when it answered."""
    if not app.settings.get("repair.on", True) or msg.via not in BUTTONS:
        return False
    rows = readings(plain, mods, asks)
    if not close(rows):
        return False
    a, b = rows[0], rows[1]
    cases = app.modules.get("cases") if app.is_on("cases") else None
    known = cases.expected(plain) if cases is not None else None
    for r in (a, b):
        if r["intent"] == known:  # you said which before, and it's a test case now
            return run(app, r, msg)
    ref = uuid.uuid4().hex[:8]
    with Lock(app.paths.state, "repair", timeout=5):
        data = _load(app)
        data[ref] = {"text": msg.text, "via": msg.via, "at": now().isoformat(timespec="seconds"), "readings": [a, b]}
        _save(app, data)
    app.events.emit("repair_asked", first=a["intent"], second=b["intent"])
    msg.reply(
        f'Did you mean "{a["label"]}" or "{b["label"]}"?',
        buttons=[[(a["label"], f"rpr:{ref}:0"), (b["label"], f"rpr:{ref}:1")], [("Neither", f"rpr:{ref}:no")]],
    )
    return True


def run(app: App, r: dict, msg: Incoming, via: str = "repair") -> bool:
    """Run one reading: the request by its name, with the words it reads (via: who picked it, for the event)."""
    from kurooto.modules.text import tidy

    for m in app.enabled():
        for it in _intents(m):
            if it.name != r["intent"]:
                continue
            slots = _match(it, tidy(r["means"]))
            if slots is None:
                return False
            app.events.emit("intent", name=it.name, via=via)
            app.keep.used(m.id, "intent", msg.via)
            msg.reply(it.run(msg, slots) or "Done.")
            return True
    return False


def button(app: App, ref: str, act: str) -> str:
    with Lock(app.paths.state, "repair", timeout=5):
        data = _load(app)
        p = data.pop(ref, None)
        _save(app, data)
    if p is None:
        return "That's old now: say it again."
    reply = _replier(app)
    from kurooto.modules.base import Incoming

    msg = Incoming(p["text"], via=p.get("via") or "telegram", respond=reply)
    if act not in ("0", "1"):
        app.events.emit("repair_neither")
        chat = app.modules.get("chat")
        if chat is not None and app.is_on("chat"):
            out = chat.ask(msg)
            if out:
                reply(out)
            return "Asked your AI instead."
        return "OK, left as it is."
    r = p["readings"][int(act)]
    if not run(app, r, msg):
        return "That request is off now."
    cases = app.modules.get("cases") if app.is_on("cases") else None
    if cases is not None:  # the second repair of this phrasing to this request teaches it (modules/cases.py)
        cases.repaired(p["text"], r["intent"], r["means"], via=msg.via)
    return "OK."


def _replier(app: App):
    def reply(text, buttons=None):
        return app.notify(text, kind="result", buttons=buttons, why="asked")

    return reply


def _load(app: App) -> dict:
    data = jload(Path(app.paths.state) / FILE, {}) or {}
    cutoff = now() - dt.timedelta(hours=KEEP_H)
    return {k: v for k, v in data.items() if dt.datetime.fromisoformat(v["at"]) > cutoff}


def _save(app: App, data: dict) -> None:
    jsave(Path(app.paths.state) / FILE, dict(sorted(data.items(), key=lambda kv: kv[1]["at"])[-KEEP:]))
