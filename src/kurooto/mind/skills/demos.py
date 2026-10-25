"""Skills from what you do (Brain, 0.8.0 stage 12, opt-in: `mind.skills.from_demos`).

From the activity stream (stage 13 writes `<state>/activity.jsonl`, one JSON event per line: {t, kind, target}) it
finds a
short sequence you repeat ("every Monday: export the plots, then put them in the meeting note"): the same two to six
steps, in order, close together, on at least three different days. Each is offered once, as a question, never silently:
"I noticed you do X; want me to do it?" Yes makes it a candidate skill (it must still pass its regression cases and
starts at always-ask); No is remembered and it never asks about that sequence again. What it learns from is what you
did,
never whether you liked something. Targets are reduced to their shape (digits and dates become #), and only the shape
is kept.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import time
from typing import TYPE_CHECKING

from kurooto.core.state import jload, jsave
from kurooto.mind.skills import distill, library

if TYPE_CHECKING:
    from kurooto.app import App

FILE = "mind-demos.json"
GAP_S = 600  # steps of one sequence are at most this far apart
MIN_DAYS = 3
MIN_LEN, MAX_LEN = 2, 6
MAX_OFFERS = 3  # at a time
SHAPE = re.compile(r"\d+")


def shape(ev: dict) -> str:
    return f"{str(ev.get('kind') or '')[:30]}:{SHAPE.sub('#', str(ev.get('target') or ''))[:60]}"


def events(app: App, since: float | None = None) -> list[dict]:
    from kurooto.mind.senses import store

    return [e for e in store.events(app, "activity", since or 0.0) if e["kind"] in ("window", "cwd", "save", "commit")]


def bursts(evs: list[dict]) -> list[list[dict]]:
    """Runs of events with no gap longer than GAP_S."""
    out: list[list[dict]] = []
    for ev in evs:
        if out and ev["t"] - out[-1][-1]["t"] <= GAP_S:
            out[-1].append(ev)
        else:
            out.append([ev])
    return out


def detect(evs: list[dict], min_days: int = MIN_DAYS) -> list[dict]:
    """Sequences of 2 to 6 shapes seen in the same order in bursts on at least `min_days` different days, longest and
    most repeated first: [{id, shapes, days, count}]."""
    seen: dict[tuple, set] = {}
    count: dict[tuple, int] = {}
    for b in bursts(evs):
        shapes = [shape(e) for e in b]
        day = dt.datetime.fromtimestamp(b[0]["t"]).date().isoformat()
        got = set()
        for n in range(MIN_LEN, min(MAX_LEN, len(shapes)) + 1):
            for i in range(len(shapes) - n + 1):
                seq = tuple(shapes[i : i + n])
                if len(set(seq)) > 1 and seq not in got:  # not the same step over and over
                    got.add(seq)
        for seq in got:
            seen.setdefault(seq, set()).add(day)
            count[seq] = count.get(seq, 0) + 1
    found = [(s, d) for s, d in seen.items() if len(d) >= min_days]
    # keep a sequence only when no longer one with the same count contains it
    keep = []
    for s, d in sorted(found, key=lambda x: (-len(x[0]), -len(x[1]))):
        if not any(len(o) > len(s) and count[o] >= count[s] and _inside(s, o) for o, _ in keep):
            keep.append((s, d))
    return [
        {
            "id": hashlib.sha256("|".join(s).encode()).hexdigest()[:10],
            "shapes": list(s),
            "days": len(d),
            "count": count[s],
        }
        for s, d in keep
    ][:10]


def _inside(small: tuple, big: tuple) -> bool:
    return any(big[i : i + len(small)] == small for i in range(len(big) - len(small) + 1))


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("offers", {})
    return d


def on(app: App) -> bool:
    return library.on(app) and bool(app.settings.get("mind.skills.from_demos"))


def describe(shapes: list[str]) -> str:
    return ", then ".join(s.replace(":", " ") for s in shapes)


def offer(app: App, payload: dict | None = None) -> list[str]:
    """Offer new sequences, once each, at most MAX_OFFERS waiting at a time. Returns the ids offered."""
    if not on(app):
        return []
    st = _state(app)
    waiting = sum(1 for o in st["offers"].values() if o["state"] == "offered")
    out = []
    for seq in detect(events(app, time.time() - 60 * 86400)):
        if seq["id"] in st["offers"] or waiting + len(out) >= MAX_OFFERS:
            continue
        st["offers"][seq["id"]] = {"state": "offered", "shapes": seq["shapes"], "days": seq["days"], "at": time.time()}
        out.append(seq["id"])
        app.notify(
            f"I noticed you do this on {seq['days']} different days: {describe(seq['shapes'])}. "
            "Want me to learn to do it?",
            kind="question",
            why="mind.skill_offer",
            buttons=[[("Yes, learn it", f"skl:{seq['id']}:yes"), ("No", f"skl:{seq['id']}:no")]],
        )
    _save(app, st)
    return out


def _save(app: App, st: dict) -> None:
    for k in list(st["offers"])[:-200]:
        st["offers"].pop(k, None)
    jsave(app.paths.state / FILE, st)


def prompt_for(o: dict) -> str:
    return (
        "The owner repeats this sequence of steps on several days: "
        + describe(o["shapes"])
        + ". Write a reusable skill that does it for them. Answer with JSON only: slug, title, when, inputs (lowercase "
        'names), steps (numbered), kind ("prompt"), template (using {name} for inputs), cases (at least two: {inputs, '
        "expect: {contains: [...]}}). The skill only prepares or suggests; it never sends or deletes anything."
    )


def answer(app: App, oid: str, yes: bool, asker=None, runner=None) -> str:
    st = _state(app)
    o = st["offers"].get(oid)
    if not o or o["state"] != "offered":
        return "That offer has expired."
    if not yes:
        o["state"] = "declined"
        _save(app, st)
        return "OK. I won't ask about that again."
    o["state"] = "accepted"
    _save(app, st)
    raw = (asker or distill.ask_json)(app, prompt_for(o), "Skill: from a repeated sequence")
    if raw is None:
        return "I couldn't write that one just now."
    slug, why = library.admit(app, raw, {"source": "demo", "sequence": oid, "days": o["days"]}, runner)
    return (
        f"Learned it as {slug}. It asks before it runs."
        if slug
        else f"It didn't pass its own tests ({why}); nothing was added."
    )


def button(app: App, ref: str, act: str) -> str:
    return answer(app, ref, act == "yes")


def forget(app: App) -> None:
    (app.paths.state / FILE).unlink(missing_ok=True)


__all__ = ["detect", "offer", "answer", "button"]
