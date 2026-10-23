"""Turn on from chat: a plain-English request that a feature that's off would understand ("wake me at 7" with the
Morning alarm off) gets [Turn on] [Not now] instead of a guess. Turn on switches on that feature (and what it needs,
when that's ready), then does the request; Not now leaves everything as it was and, with Chat on, asks your AI
instead. A feature that needs setting up first says where. Setting turnon.offer (on). Only on Telegram and the phone
app, where a button can be tapped; the setup page's try-it box and a terminal go on to the AI as before.

The request waits for the tap in the state folder (turnon.json, the last 20, for a day), so a tap after a restart
still works. Rules only: no AI, nothing leaves the computer.
"""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.base import Incoming, Intent, Module

register_defaults("turnon", {"offer": True})  # a request a feature that's off understands: offer to turn it on
FILE = "turnon.json"
BUTTONS = ("telegram", "app")  # channels where a tap comes back; elsewhere (setup, a terminal) the AI answers as before
KEEP, KEEP_H = 20, 24


def _title(m: Module) -> str:
    return m.title.split(" (")[0]


def find(app: App, plain: str, mods: list[Module], asks: bool) -> tuple[Module, Intent] | None:
    """The feature that's off whose instant request takes this text, with that request."""
    for m in app.modules.values():
        if m in mods:
            continue
        try:
            intents = m.intents()
        except Exception as e:  # a feature that's off may not be able to say: never in the way
            app.events.emit("turnon_skipped", module=m.id, error=str(e)[:200])
            continue
        for it in intents:
            if asks and not it.questions:
                continue
            try:
                hit = it.match(plain) is not None
            except Exception as e:
                app.events.emit("turnon_skipped", module=m.id, error=str(e)[:200])
                hit = False
            if hit:
                return m, it
    return None


def offer(app: App, msg: Incoming, plain: str, mods: list[Module], asks: bool) -> bool:
    """Offer to turn on the feature that would do this request. True when it answered."""
    if not app.settings.get("turnon.offer", True) or msg.via not in BUTTONS:
        return False
    got = find(app, plain, mods, asks)
    if got is None:
        return False
    m, it = got
    title = _title(m)
    ready, why = m.ready()
    if not ready:
        msg.reply(f"That's for {title}, which is off and needs setting up first ({why}): Features → {title}.")
        return True
    ref = uuid.uuid4().hex[:8]
    with Lock(app.paths.state, "turnon", timeout=5):
        data = _load(app)
        data[ref] = {"module": m.id, "text": msg.text, "via": msg.via, "at": now().isoformat(timespec="seconds")}
        _save(app, data)
    from kurooto.app import met

    on = set(app.settings.get("modules.enabled") or [])
    needs = [_title(app.modules[r]) for r in m.requires if r in app.modules and not met(r, on, m)]
    also = f" (and {', '.join(needs)}, which it needs)" if needs else ""
    app.events.emit("turnon_offered", module=m.id, intent=it.name)
    msg.reply(
        f"That's for {title}, which is off. Turn it on{also} and do it?",
        buttons=[[("Turn on", f"ton:{ref}:on"), ("Not now", f"ton:{ref}:no")]],
    )
    return True


def button(app: App, ref: str, act: str) -> str:
    with Lock(app.paths.state, "turnon", timeout=5):
        data = _load(app)
        p = data.pop(ref, None)
        _save(app, data)
    if p is None:
        return "That's old now: ask again."
    m = app.modules.get(p["module"])
    if m is None:
        return "That feature is gone."
    reply = _replier(app, p)
    if act != "on":
        chat = app.modules.get("chat")
        if chat is not None and app.is_on("chat"):
            out = chat.ask(_incoming(p, reply))
            if out:
                reply(out)
            return "Asked your AI instead."
        return "OK, left as it is."
    from kurooto.app import met

    for r in [*m.requires, m.id]:
        if r in app.modules and not met(r, set(app.settings.get("modules.enabled") or []), m):
            ok, why = app.enable(r)
            if not ok:
                return f"Couldn't turn on {_title(app.modules[r])}: {why}"[:190]
    app.events.emit("turnon_done", module=m.id)
    from kurooto.modules.text import QUESTION, tidy

    plain = tidy(p["text"])
    asks = bool(QUESTION.search(plain))
    for it in m.intents():
        if asks and not it.questions:
            continue
        slots = it.match(plain)
        if slots is not None:
            reply(it.run(_incoming(p, reply), slots) or "Done.")
            break
    return f"{_title(m)} is on."


def _replier(app: App, p: dict):
    def reply(text, buttons=None):
        buttons = buttons if buttons is not None else getattr(text, "buttons", None)  # an Answer's Undo
        return app.notify(text, kind="result", buttons=buttons, why="asked")

    return reply


def _incoming(p: dict, reply) -> Incoming:
    from kurooto.modules.base import Incoming

    return Incoming(p["text"], via=p.get("via") or "telegram", respond=reply)


def _load(app: App) -> dict:
    data = jload(Path(app.paths.state) / FILE, {}) or {}
    cutoff = now() - dt.timedelta(hours=KEEP_H)
    return {k: v for k, v in data.items() if dt.datetime.fromisoformat(v["at"]) > cutoff}


def _save(app: App, data: dict) -> None:
    jsave(Path(app.paths.state) / FILE, dict(sorted(data.items(), key=lambda kv: kv[1]["at"])[-KEEP:]))
