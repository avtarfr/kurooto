"""A play budget (Brain, 0.8.0 stage 17b, off by default: `mind.play.on`).

A small, fixed amount of nightly time (`mind.play.minutes_per_night`, 20) in which Kurooto explores questions *it*
chooses on your topics,
out of curiosity rather than because a task asked: a different way to explain a concept you found hard, a hunch, a
link between two notes.
It runs on the charger only, with the lid open and the computer not hot, and each session is pre-registered like a lab
batch (the plan's
hash is in Brain's log before the first question).

It is paid only for **gains that transfer**: an improvement on the hidden harness that a play output made, or a result
you later say
was useful (`/play useful <id>`). Nothing else is credited, so play can't be farmed, and a credit changes nothing but
what the weekly
digest may say. Outputs are kept in `<state>/mind-play/` and are never shown unprompted; "From my play time" appears
in the Sunday
digest only when something transferred.
"""

from __future__ import annotations

import datetime as dt
import time
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core import power
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "play"  # its switch: mind.play.on
FILE = "mind-play.json"
MIN_GAIN = 0.02  # a harness gain this big (hidden or practice split, 0 to 1) counts as a transfer
PER_SESSION = 3
REPEAT_DAYS = 14

register_defaults(
    "mind",
    {
        "play": {
            "on": False,  # off until you turn it on: a little nightly time to explore its own questions on your topics
            "minutes_per_night": 20,  # on the charger only; credited only for what transfers or what you find useful
        }
    },
)


def on(app: App) -> bool:
    return mind.part_on(app, "play")


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    for k, v in (("played", {}), ("outputs", {}), ("credits", []), ("told", 0.0)):
        d.setdefault(k, v)
    return d


def _save(app: App, d: dict) -> None:
    d["credits"] = d["credits"][-200:]
    jsave(app.paths.state / FILE, d)


def ready(app: App) -> tuple[bool, str]:
    from kurooto.mind.lab import runner

    if not on(app):
        return False, "play is off (mind.play.on)"
    if not power.on_ac():
        return False, "it isn't on the charger"
    if not runner.lid_open():
        return False, "the lid is closed"
    if runner.hot():
        return False, "the computer is hot"
    return True, ""


def curiosity(app: App) -> list[dict]:
    """Questions it might choose: concepts on the frontier of what you know (low mastery, neighbours known), then
    anything the lab or
    Dreaming left open. [{id, kind, text}]; ones it played in the last two weeks are left out."""
    out: list[dict] = []
    try:
        from kurooto.mind.tom import knowledge

        notes = knowledge.concepts(app)
        for slug in knowledge.frontier(app, 6):
            title = notes[slug].title if slug in notes else slug
            out.append(
                {
                    "id": "explain:" + slug,
                    "kind": "explain",
                    "text": f"Find a clearer way to explain {title} to someone who knows its neighbours but not this.",
                }
            )
    except Exception:  # noqa: S110
        pass
    played = _state(app)["played"]
    cut = time.time() - REPEAT_DAYS * 86400
    return [q for q in out if float(played.get(q["id"]) or 0) < cut]


def _prereg(app: App, qs: list[dict]) -> str:
    from kurooto.mind.lab import prereg

    proto = SimpleNamespace(metric="transfer", direction="max", min_effect=MIN_GAIN, seeds=1, space="free", weak=True)
    rec = prereg.make(
        "play",
        proto,
        "exploring these questions yields something that transfers",
        [{"id": q["id"], "config": {"kind": q["kind"]}} for q in qs],
        0.0,
        "stops at the night's minutes",
    )
    return prereg.register(app, "play", rec)


def run_session(app: App, asker=None, clock=time.monotonic, questions: list[dict] | None = None) -> dict:
    """One night's play, within `minutes_per_night`: {"ran", "why", "asked", "minutes"}. Never says anything to you."""
    ok, why = ready(app)
    if not ok:
        return {"ran": False, "why": why, "asked": 0, "minutes": 0.0}
    qs = (questions if questions is not None else curiosity(app))[:PER_SESSION]
    if not qs:
        return {"ran": False, "why": "nothing it's curious about right now", "asked": 0, "minutes": 0.0}
    budget = float(app.settings.get("mind.play.minutes_per_night") or 20) * 60
    _prereg(app, qs)  # the plan is in the log before the first question
    if asker is None:
        from kurooto.mind.skills.library import ask_text as asker_  # noqa: N813

        def asker(q):  # noqa: E306
            return asker_(app, q["text"] + "\nAnswer in under 200 words.", "Play: " + q["kind"])

    t0, spent, asked, longest = clock(), 0.0, 0, 0.0
    st = _state(app)
    for q in qs:
        spent = clock() - t0
        if asked and spent + longest > budget:  # the next one would run past the night's minutes
            break
        if spent >= budget:
            break
        t1 = clock()
        text = asker(q)
        longest = max(longest, clock() - t1)
        if text:
            oid = "o" + uuid.uuid4().hex[:7]
            d = app.paths.state / "mind-play"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{oid}.md").write_text(f"# {q['text']}\n\n{text}\n", encoding="utf-8")
            st["outputs"][oid] = {"q": q["id"], "at": time.time(), "credited": False}
        st["played"][q["id"]] = time.time()
        asked += 1
    _save(app, st)
    return {"ran": True, "why": "", "asked": asked, "minutes": round((clock() - t0) / 60, 1)}


def credit(app: App, oid: str, before: float, after: float) -> bool:
    """A play output made the hidden harness's score go from `before` to `after`: credited only if the gain is real (>=
    MIN_GAIN)."""
    st = _state(app)
    o = st["outputs"].get(oid)
    if o is None or o["credited"] or after - before < MIN_GAIN:
        return False
    o["credited"] = True
    st["credits"].append({"id": oid, "at": time.time(), "kind": "harness", "gain": round(after - before, 4)})
    _save(app, st)
    return True


def useful(app: App, oid: str) -> bool:
    """You say a play output turned out useful: credited (once)."""
    st = _state(app)
    o = st["outputs"].get(oid)
    if o is None or o["credited"]:
        return False
    o["credited"] = True
    st["credits"].append({"id": oid, "at": time.time(), "kind": "useful", "gain": 0.0})
    _save(app, st)
    return True


def digest_section(app: App, now: float | None = None) -> str:
    """ "From my play time", only when something transferred in the last week and hasn't been told yet. Else ""."""
    now = now or time.time()
    st = _state(app)
    new = [c for c in st["credits"] if c["at"] > max(now - 7 * 86400, float(st["told"]))]
    if not on(app) or not new:
        return ""
    lines = []
    for c in new:
        o = st["outputs"].get(c["id"]) or {}
        why = f"it lifted the harness by {c['gain']:.2f}" if c["kind"] == "harness" else "you found it useful"
        lines.append(f"- {o.get('q', c['id']).replace('explain:', 'a clearer way to explain ')}: {why} ({c['id']})")
    return "From my play time:\n" + "\n".join(lines)


def weekly(app: App, payload: dict | None = None, now: float | None = None) -> bool:
    text = digest_section(app, now)
    if not text:
        return False
    st = _state(app)
    st["told"] = now or time.time()
    _save(app, st)
    app.notify(text, kind="info", why="mind.play")
    return True


def listing(app: App) -> str:
    if not on(app):
        return "Play is off (mind.play.on). It's a little nightly time for it to explore its own questions."
    st = _state(app)
    return (
        f"Play: {len(st['played'])} question(s) explored, {len(st['credits'])} credited "
        "(only gains that transfer count).\n"
        "Its outputs aren't shown unless you ask: /play outputs; /play useful <id> says one helped."
    )


def outputs(app: App) -> str:
    st = _state(app)
    rows = sorted(st["outputs"].items(), key=lambda kv: -kv[1]["at"])[:10]
    return (
        "\n".join(
            f"- {oid}: {o['q']} ({dt.datetime.fromtimestamp(o['at']):%d %b})" + (" credited" if o["credited"] else "")
            for oid, o in rows
        )
        or "Nothing yet."
    )
