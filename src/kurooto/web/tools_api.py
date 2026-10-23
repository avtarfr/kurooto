"""The local API for the AI's tools and for Kurooto's terminal commands.

GET  tools                     every tool unattended AI runs get: name, description, JSON schema
POST tools/call {name, args, job?}   run one (what `kurooto mcp` does for agent programs; job: the request it's a
                               step of, counted in core/jobs.py)
POST say {text}                plain English, as if typed on Telegram (`kurooto ask`); a bigger request becomes
                               a job whose answer comes back here instead of to Telegram
GET  job?id= / POST job {id}   how that job is going, and its answer
POST call {reason, at, alarm, force}   ring your phone now or later (`kurooto call`)
POST call/list · call/cancel {key}      the calls booked for later, and taking one off (`kurooto call --list/--cancel`)
GET  usage?days=7              AI requests per day per brain, and usage-limit hits; agy's own count from its logs;
                               today's free limits (quota: used, learned limit, when it resets; core/quota.py)
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
POSTS = ("tools/call", "say", "job", "call", "call/list", "call/cancel")
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
        from kurooto.providers.agy import log_usage

        return 200, {
            "days": days,
            "rows": app.jobs.usage(days),
            "agy": log_usage(days),
            "quota": app.quota.report(),
            "waiting": app.jobs.waiting(),
        }
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
        of = str(b.get("job") or "")[:40] or None  # an agent program's request: the tool use is one of its steps
        return 200, {"ok": True, "result": run_tool(app, name, args or {}, tools, via=via, job=of)}
    if path == "say":
        return say(app, str(b.get("text") or ""))
    if path == "job":
        return job(app, str(b.get("id", "")))
    if path == "call":
        ok, msg = place_call(
            app, str(b.get("reason") or ""), str(b.get("at") or ""), bool(b.get("alarm")), bool(b.get("force"))
        )
        return 200, {"ok": ok, "message": msg}
    if path == "call/list":
        return 200, {"ok": True, "calls": booked_calls(app)}
    if path == "call/cancel":
        ok, msg = cancel_call(app, str(b.get("key") or ""))
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
        return True, calls.schedule(when, reason, alarm=alarm, why="calls.own") + "."
    if not (force or alarm):
        why, until = app.availability.call_block()
        if not why and live_call(app):
            why, until = ON_A_CALL, now() + dt.timedelta(minutes=3)
        if why:
            t = until + dt.timedelta(minutes=2)
            calls.schedule(t, reason, why="calls.own")
            app.events.emit("call_held", why=why)
            return True, f"Held until {t:%H:%M} ({why}): {reason}"
    elif live_call(app):
        return False, "You're on a call right now, so I didn't ring. Try again when it's over."
    calls.ring(reason, alarm=alarm, why="calls.own")
    return True, f"Calling your phone: {reason}"


# ------------------------------------------------------------------- (ws5) scripts: calls booked, notify with buttons
def booked_calls(app: App) -> list[dict]:
    """The calls booked for later (`kurooto call --at`, held calls, ones the AI booked), soonest first. Check-ins and
    the alarm have their own commands, so they aren't listed here."""
    out = []
    for j in app.scheduler.jobs("calls:ring:"):
        at = dt.datetime.fromtimestamp(j.next_run).astimezone()
        out.append(
            {
                "key": j.key.removeprefix("calls:ring:"),
                "at": at.isoformat(timespec="minutes"),
                "when": f"{at:%a %d %b %H:%M}",
                "reason": str(j.payload.get("reason") or ""),
                "alarm": bool(j.payload.get("alarm")),
            }
        )
    return out


def cancel_call(app: App, key: str) -> tuple[bool, str]:
    key = key.strip().removeprefix("calls:ring:")
    if not key:
        return False, "Which call? `kurooto call --list` shows their keys."
    if not app.scheduler.cancel(f"calls:ring:{key}"):
        return False, f"There's no booked call {key} (`kurooto call --list` shows them)."
    calls = app.modules.get("calls")
    if calls is not None and app.is_on("calls"):
        try:
            calls.connector.poke()  # the call line forgets it too, so it doesn't ring while this computer is off
        except Exception:
            pass
    app.events.emit("call_cancelled", via="terminal")
    return True, f"Cancelled the call {key}."


NOTIFY_KINDS = ("info", "result", "reminder", "deadline", "question", "approval")


def notify_buttons(raw, click: str = "") -> tuple[list, str]:
    """Buttons for a message from a script: [["Label", "prefix:ref:action" or "https://..."], ...], one row each, and
    a link to open (--click). ([], "") when there are none; (_, why) when one isn't usable."""
    rows: list = []
    for item in raw or []:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            return [], "each button is a label and what it does"
        label, target = str(item[0]).strip()[:40], str(item[1]).strip()
        if not label or not target:
            return [], "a button needs a label and what it does: Label=prefix:ref:action, or Label=https://..."
        if target.startswith(("https://", "http://")):
            rows.append([(label, {"url": target})])
        elif len(target.encode("utf-8")) > 64:
            return [], f"the button {label!r} does too much: at most 64 bytes (Telegram's limit)"
        else:
            rows.append([(label, target)])
    if click:
        if not click.startswith(("https://", "http://")):
            return [], "--click takes a web address (https://...)"
        rows.append([("Open", {"url": click})])
    if len(rows) > 8:
        return [], "at most 8 buttons"
    return rows, ""


def notify_from_program(app: App, b: dict) -> tuple[int, dict]:
    """POST notify (`kurooto notify`): other programs on this computer message you through Kurooto, with buttons, a
    link to open and a reply to an earlier message if they like. The answer carries the Telegram message's id."""
    text = str(b.get("text", "")).strip()[:3500]
    if not text:
        return 400, {"error": "nothing to say"}
    kind = b.get("kind") if b.get("kind") in NOTIFY_KINDS else "info"
    title = str(b.get("title") or "").strip()[:80] or None
    buttons, why = notify_buttons(b.get("buttons"), str(b.get("click") or "").strip())
    if why:
        return 400, {"error": why}
    reply_to = b.get("reply_to")
    reply_to = int(reply_to) if isinstance(reply_to, (int, str)) and str(reply_to).strip().isdigit() else None
    ref = app.notify(
        text,
        title=title,
        kind=kind,
        urgent=bool(b.get("urgent")),
        buttons=buttons or None,
        reply_to=reply_to,
        why="asked",
    )
    app.events.emit("notify_external", source=(title or "")[:40])
    return 200, {"ok": True, "id": ref}
