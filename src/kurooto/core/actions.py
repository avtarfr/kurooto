"""Actions: the everyday things you do with Kurooto, the same from every place you can do them (the dashboard's Today
page now; the phone app next). Each one calls the very method the Telegram command and the AI's tool call, so the
three can't behave differently.

    today()                         what the Today page shows: the day, classes, what's due (with ids to tick), your
                                    reminders (with ids to cancel or snooze), check-ins, the alarm, open questions,
                                    today's journal lines and what's in the inbox
    act(app, name, args)            one action; {"ok", "message", ...}; never raises

Actions: journal.add {text} · note.capture {text} · reminder.add {when, what} · reminder.cancel {key} ·
reminder.snooze {key, minutes} · deadline.add {title, when, course?} · deadline.done {id} · deadline.move {id, when} ·
alarm.set {when} · alarm.skip {day} · alarm.clear · alarm.daily {time or "off"} · checkin.skip {name} ·
checkin.postpone {name, minutes} (later today) · checkin.defer {name} (to tomorrow morning) · ask {text} (a job: its
answer comes like a chat answer) · question.answer {id, answer}
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import layout
from kurooto.core.clock import now, parse_when

if TYPE_CHECKING:
    from kurooto.app import App


class Problem(Exception):
    """An action that can't be done, with a sentence that says why."""


def _on(app: App, mod: str, what: str):
    m = app.modules.get(mod)
    if m is None or not app.is_on(mod):
        raise Problem(f"{what} is off: turn it on in Features.")
    return m


def _text(args: dict, key: str = "text") -> str:
    t = str(args.get(key) or "").strip()
    if not t:
        raise Problem("Nothing to save.")
    return t


# ----------------------------------------------------------------------------------------------- the day
def journal_lines(app: App, day: dt.date | None = None) -> list[str]:
    """Today's journal entries (the "Journal" sections of the daily note), newest last."""
    from kurooto.modules import daily

    f = daily.note_path(app, day)
    if not f.is_file():
        return []
    text = f.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in re.finditer(r"^## Journal[^\n]*\n+(.*?)(?=^## |\Z)", text, re.S | re.M):
        body = m.group(1).strip()
        if body:
            out.append(body)
    return out


def inbox_note(app: App) -> Path:
    return layout.path(app, "note", slug=f"{now():%Y-%m-%d}-captured")


def today(app: App) -> dict:
    from kurooto.modules.daily import morning_view

    out = morning_view(app)
    rem = app.modules.get("reminders")
    if rem is not None and app.is_on("reminders"):
        out["reminders"] = [
            {
                "key": j.key.split(":", 1)[1],
                "when": j.when.astimezone().strftime("%a %H:%M"),
                "what": j.payload.get("what", ""),
            }
            for j in app.scheduler.jobs("reminders:")[:30]
        ]
    dl = app.modules.get("deadlines")
    if dl is not None and app.is_on("deadlines"):
        out["deadlines"] = [
            {
                "id": i,
                "title": it["title"],
                "subject": it.get("subject") or "",
                "due": it["due"][:16],
                "hours": round(h, 1),
            }
            for i, it, h in dl.upcoming(24 * 21)[:30]
        ]
    al = app.modules.get("alarm")
    if al is not None and app.is_on("alarm"):
        nxt = al.next()
        out["alarm_state"] = {
            "next": f"{nxt:%a %d %b %H:%M}" if nxt else "",
            "daily": al.setting("daily") or "",
            "status": al.status(),
        }
    ck = app.modules.get("checkins")
    if ck is not None and app.is_on("checkins"):
        out["checkin_names"] = [
            {"name": n, "time": c.get("time") or "", "status": c.get("status", "")} for n, c in ck.today().items()
        ]
    out["questions_full"] = [
        {"id": q["id"], "text": q["text"][:300], "choices": q.get("choices") or []} for q in app.ask.pending()[:8]
    ]
    out["journal"] = journal_lines(app)
    inbox = inbox_note(app)
    out["inbox_today"] = (
        len([ln for ln in inbox.read_text(encoding="utf-8", errors="replace").splitlines() if ln.startswith("- ")])
        if inbox.is_file()
        else 0
    )
    out["features"] = sorted(m.id for m in app.enabled())
    return out


# ------------------------------------------------------------------------------------------------ actions
def journal_add(app: App, args: dict) -> dict:
    from kurooto.modules import daily

    text = _text(args)
    f = daily.append(app, f"Journal {now():%H:%M}", text)
    app.events.emit("journal_added", via=args.get("_via", "dashboard"), chars=len(text))
    return {"message": f"Saved in {layout.shown(app, f)}."}


def note_capture(app: App, args: dict) -> dict:
    from kurooto.core.tools import add_to_section, write_note_file

    text = _text(args)
    f = inbox_note(app)
    old = (
        f.read_text(encoding="utf-8")
        if f.is_file()
        else (layout.frontmatter(app, "note", f, title=f"Captured {now():%Y-%m-%d}") + f"# Captured {now():%Y-%m-%d}\n")
    )
    line = f"- {now():%H:%M} {' '.join(text.split())}"
    write_note_file(f, add_to_section(old, "", line))
    app.events.emit("note_captured", via=args.get("_via", "dashboard"))
    return {"message": f"Saved to {layout.shown(app, f)}."}


def reminder_add(app: App, args: dict) -> dict:
    rem = _on(app, "reminders", "Reminders")
    try:
        when = parse_when(str(args.get("when") or ""))
    except ValueError:
        raise Problem(f"I couldn't read the time {args.get('when')!r}.") from None
    return {"message": rem.add(when, _text(args, "what"))}


def reminder_cancel(app: App, args: dict) -> dict:
    _on(app, "reminders", "Reminders")
    key = str(args.get("key") or "")
    if not re.fullmatch(r"[0-9a-f]{4,16}", key) or not app.scheduler.cancel(f"reminders:{key}"):
        raise Problem("That reminder is gone already.")
    return {"message": "Reminder cancelled."}


def reminder_snooze(app: App, args: dict) -> dict:
    rem = _on(app, "reminders", "Reminders")
    key = str(args.get("key") or "")
    job = app.scheduler.get(f"reminders:{key}") if re.fullmatch(r"[0-9a-f]{4,16}", key) else None
    if job is None:
        raise Problem("That reminder is gone already.")
    minutes = max(1, min(24 * 60, int(args.get("minutes") or 10)))
    what = job.payload.get("what", "")
    app.scheduler.cancel(f"reminders:{key}")
    base = max(now(), job.when.astimezone().replace(tzinfo=None))
    return {"message": rem.add(base + dt.timedelta(minutes=minutes), what)}


def _tool(app: App, name: str, args: dict, via: str) -> dict:
    from kurooto.core.tools import agent_tools, run_tool

    tools = agent_tools(app)
    if not any(t.name == name for t in tools):
        raise Problem("That feature is off: turn it on in Features.")
    return {"message": str(run_tool(app, name, args, tools, via=via))}


def deadline_add(app: App, args: dict) -> dict:
    _on(app, "deadlines", "Deadlines")
    return _tool(
        app,
        "add_deadline",
        {"title": _text(args, "title"), "due": str(args.get("when") or ""), "course": str(args.get("course") or "")},
        args.get("_via", "dashboard"),
    )


def deadline_done(app: App, args: dict) -> dict:
    _on(app, "deadlines", "Deadlines")
    return _tool(app, "mark_deadline_done", {"id": str(args.get("id") or "")}, args.get("_via", "dashboard"))


def deadline_move(app: App, args: dict) -> dict:
    _on(app, "deadlines", "Deadlines")
    return _tool(
        app,
        "move_deadline",
        {"id": str(args.get("id") or ""), "due": str(args.get("when") or "")},
        args.get("_via", "dashboard"),
    )


def alarm_set(app: App, args: dict) -> dict:
    al = _on(app, "alarm", "The alarm")
    return {"message": al._tool({"time": _text(args, "when")})}


def alarm_skip(app: App, args: dict) -> dict:
    al = _on(app, "alarm", "The alarm")
    return {"message": al._tool({"time": f"skip {str(args.get('day') or 'tomorrow')}"})}


def alarm_clear(app: App, args: dict) -> dict:
    return {"message": _on(app, "alarm", "The alarm").clear()}


def alarm_daily(app: App, args: dict) -> dict:
    al = _on(app, "alarm", "The alarm")
    t = str(args.get("time") or "").strip()
    return {"message": al._tool({"time": f"daily {t or 'off'}"})}


def checkin_skip(app: App, args: dict) -> dict:
    ck = _on(app, "checkins", "Check-ins")
    return {"message": ck.skip(_text(args, "name"), via=args.get("_via", "dashboard"))}


def checkin_defer(app: App, args: dict) -> dict:
    ck = _on(app, "checkins", "Check-ins")
    return {"message": ck.defer(_text(args, "name"), via=args.get("_via", "dashboard"))}


def checkin_postpone(app: App, args: dict) -> dict:
    ck = _on(app, "checkins", "Check-ins")
    minutes = max(1, min(12 * 60, int(args.get("minutes") or 30)))
    return {"message": ck.postpone(_text(args, "name"), minutes, via=args.get("_via", "dashboard"))}


def ask(app: App, args: dict) -> dict:
    from kurooto.web import tools_api

    code, out = tools_api.post(app, "say", {"text": _text(args)})
    if code != 200 or not out.get("ok", True):
        raise Problem(out.get("error") or "That didn't work.")
    return {
        "message": "\n".join(out.get("replies") or []) or ("Working on it." if out.get("job") else "Done."),
        **({"job": out["job"]} if out.get("job") else {}),
    }


def question_answer(app: App, args: dict) -> dict:
    qid, ans = str(args.get("id") or ""), str(args.get("answer") or "").strip()
    if not qid or not ans:
        raise Problem("Which question, and what's the answer?")
    got = app.ask.answer(qid, ans, via=args.get("_via", "dashboard"))
    if not got or not got.get("ok"):
        raise Problem((got or {}).get("note") or "That question isn't open any more.")
    return {"message": got.get("note") or "Answered."}


ACTIONS = {
    "journal.add": journal_add,
    "note.capture": note_capture,
    "reminder.add": reminder_add,
    "reminder.cancel": reminder_cancel,
    "reminder.snooze": reminder_snooze,
    "deadline.add": deadline_add,
    "deadline.done": deadline_done,
    "deadline.move": deadline_move,
    "alarm.set": alarm_set,
    "alarm.skip": alarm_skip,
    "alarm.clear": alarm_clear,
    "alarm.daily": alarm_daily,
    "checkin.skip": checkin_skip,
    "checkin.postpone": checkin_postpone,
    "checkin.defer": checkin_defer,
    "ask": ask,
    "question.answer": question_answer,
}


def act(app: App, name: str, args: dict | None = None, via: str = "dashboard") -> dict:
    fn = ACTIONS.get(name)
    if fn is None:
        return {"ok": False, "message": f"There's no action {name!r}."}
    args = {**(args if isinstance(args, dict) else {}), "_via": via}
    try:
        out = fn(app, args)
    except Problem as e:
        return {"ok": False, "message": str(e)}
    except Exception as e:  # a feature's own trouble: a sentence, never a broken page
        app.events.emit("action_failed", action=name, error=f"{type(e).__name__}: {e}"[:200])
        return {"ok": False, "message": f"That failed: {type(e).__name__}: {e}"[:300]}
    app.events.emit("action", name=name, via=via)
    return {"ok": True, **out}
