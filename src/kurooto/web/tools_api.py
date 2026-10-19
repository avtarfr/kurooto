"""The local API for the AI's tools and for Kurooto's terminal commands.

GET  tools                     every tool unattended AI runs get: name, description, JSON schema
POST tools/call {name, args}   run one (what `kurooto mcp` does for agent programs)
POST say {text}                plain English, as if typed on Telegram (`kurooto ask`); a bigger request becomes
                               a job whose answer comes back here instead of to Telegram
GET  job?id= / POST job {id}   how that job is going, and its answer
POST call {reason, at, alarm, force}   ring your phone now or later (`kurooto call`)
GET  usage?days=7              AI requests per day per brain, and usage-limit hits
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from kurooto.core.clock import now, parse_when
from kurooto.core.jobs import FRIENDLY
from kurooto.core.state import jsave
from kurooto.core.tools import agent_tools, describe, run_tool
from kurooto.modules.base import Incoming
from kurooto.providers.base import Verdict

if TYPE_CHECKING:
    from kurooto.app import App

GETS = ("tools", "job", "usage")
POSTS = ("tools/call", "say", "job", "call")
ON_A_CALL = "you're on a call"  # the reason a no-call rule gives while a call is live (see update/service.py)


def get(app: App, path: str, q: dict) -> tuple[int, dict]:
    if path == "tools":
        from kurooto.core.mcp import tools_cache

        listed = [describe(t) for t in agent_tools(app)]
        try:
            jsave(tools_cache(app.paths), listed)  # what `kurooto mcp` lists while Kurooto is off
        except OSError:
            pass
        return 200, {"tools": listed}
    if path == "job":
        return job(app, str(q.get("id", "")))
    if path == "usage":
        try:
            days = max(1, min(int(q.get("days") or 7), 60))
        except ValueError:
            days = 7
        return 200, {"days": days, "rows": app.jobs.usage(days)}
    return 404, {"error": "not found"}


def post(app: App, path: str, b: dict) -> tuple[int, dict]:
    if path == "tools/call":
        name, args = str(b.get("name") or ""), b.get("args")
        tools = agent_tools(app)
        if not any(t.name == name for t in tools):
            return 404, {"ok": False, "error": f"There's no {name} tool (that feature may be off)."}
        if args is not None and not isinstance(args, dict):
            return 400, {"ok": False, "error": "args must be an object"}
        via = b.get("via") if b.get("via") in ("mcp", "dashboard", "terminal") else "api"
        return 200, {"ok": True, "result": run_tool(app, name, args or {}, tools, via=via)}
    if path == "say":
        return say(app, str(b.get("text") or ""))
    if path == "job":
        return job(app, str(b.get("id", "")))
    if path == "call":
        ok, msg = place_call(
            app, str(b.get("reason") or ""), str(b.get("at") or ""), bool(b.get("alarm")), bool(b.get("force"))
        )
        return 200, {"ok": ok, "message": msg}
    return 404, {"error": "not found"}


def say(app: App, text: str) -> tuple[int, dict]:
    """Route it like a message: a /command or an instant request answers now; anything else for the AI becomes
    a job (Chat sees via="terminal" and keeps the answer off Telegram)."""
    text = text.strip()[:4000]
    if not text:
        return 400, {"ok": False, "error": "nothing to say"}
    replies: list[str] = []
    msg = Incoming(text=text, via="terminal", respond=lambda t, buttons=None: replies.append(str(t)))
    app.handle(msg)
    jid = getattr(msg, "job", None)
    return 200, {"ok": True, "job": jid, "replies": [] if jid else replies}


def job(app: App, jid: str) -> tuple[int, dict]:
    j = app.jobs.get(jid) if jid else None
    if not j:
        return 404, {"ok": False, "error": "no such request"}
    out = {
        "ok": True,
        "id": j.id,
        "title": j.title,
        "status": j.status,
        "verdict": j.verdict,
        "brain": j.brain,
        "effort": j.effort,
        "seconds": j.seconds,
    }
    if j.status in ("ok", "failed"):
        from kurooto import providers

        label = providers.CHOICES.get(j.brain or "", j.brain or "the AI")
        try:
            v = Verdict(j.verdict or "error")
        except ValueError:
            v = Verdict.ERROR
        out["answer"] = j.result if j.status == "ok" else FRIENDLY.get(v, "It failed.").format(brain=label)
        out["label"] = label
    return 200, out


def live_call(app: App) -> bool:
    """Is a call going on right now? The phone feature keeps that state (availability.on_call_until); a no-call
    rule that says "you're on a call" counts too."""
    on_call = getattr(app.availability, "on_call_until", None)
    if on_call is not None:
        try:
            if on_call() is not None:
                return True
        except Exception:  # a broken check never stops a call on its own
            pass
    t = now()
    for b in list(app.availability.blockers.values()):
        try:
            if (b(t) or ("",))[0] == ON_A_CALL:
                return True
        except Exception:
            pass
    return False


def place_call(app: App, reason: str, at: str = "", alarm: bool = False, force: bool = False) -> tuple[bool, str]:
    """`kurooto call`: ring your phone now, or at a time. A call now waits out the no-call rules (classes, /hold,
    focus, night) unless it's forced or an alarm; nothing ever rings during a live call."""
    calls = app.modules.get("calls")
    reason = reason.strip()[:300]
    if not calls or not app.is_on("calls"):
        return False, "Phone calls are off: turn them on in Settings → Features → Phone calls."
    if not reason:
        return False, "Say what the call is for."
    if at:
        try:
            when = parse_when(at)
        except ValueError:
            return False, f"I couldn't read the time {at!r} (try 17:30, 'in 20 min' or 'tomorrow 7:00')."
        return True, calls.schedule(when, reason, alarm=alarm) + "."
    if not (force or alarm):
        why, until = app.availability.call_block()
        if not why and live_call(app):
            why, until = ON_A_CALL, now() + dt.timedelta(minutes=3)
        if why:
            t = until + dt.timedelta(minutes=2)
            calls.schedule(t, reason)
            app.events.emit("call_held", why=why)
            return True, f"Held until {t:%H:%M} ({why}): {reason}"
    elif live_call(app):
        return False, "You're on a call right now, so I didn't ring. Try again when it's over."
    calls.ring(reason, alarm=alarm)
    return True, f"Calling your phone: {reason}"
