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
answer comes like a chat answer) · question.answer {id, answer} · study.mode {on} · study.timer {do: start|pause|reset,
subject?}

    study_view(app, subject)        what the dashboard's Study mode shows (the timer, today's study per subject, what's
                                    due, start-by dates, recall cards, the subject's notes)
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


# ------------------------------------------------------------------------------------------------ Study mode
# The dashboard's Study mode (look.study_mode): the NOTES map large beside a STUDY pane, everything else hidden until
# it's off. /study mode on|off, "study mode", Alt+M and Ctrl+K → study all come here; the page follows the event.
NOTE_KINDS = ("course", "exam_prep", "doubts", "class_log")  # a subject's own pages first, then its notes by date
DATED = re.compile(r"^\d{4}-\d\d-\d\d-")  # a lecture note: <date>-<topic>.md (core/layout.py)


def study_mode(app: App, on: bool) -> str:
    app.settings.set("look.study_mode", bool(on))
    app.events.emit("study_mode", on=bool(on))
    if on:
        return "Study mode on: the dashboard shows your notes, the study timer and what's due. /study mode off ends it."
    return "Study mode off: the dashboard is back as it was."


def subject_notes(app: App, slug: str, limit: int = 40) -> list[dict]:
    """A subject's notes for Study mode: its course page, exam prep, doubts and class log, then its lecture and concept
    notes, newest first (where core/layout.py keeps them; in the zettelkasten layout, concept notes tagged with it).
    Ids are the notes map's (the path in the notes folder without .md)."""
    from kurooto.web.live import note_info

    root = Path(app.workspace)
    found: dict[Path, str] = {layout.path(app, k, subject=slug): k for k in NOTE_KINDS}
    folder = layout.path(app, "subject", subject=slug)
    if folder.is_dir():
        for f in folder.rglob("*.md"):
            if not any(x.startswith(".") for x in f.relative_to(folder).parts):
                found.setdefault(f, "lecture" if DATED.match(f.name) else "concept")
    concepts = layout.path(app, "concept", subject=slug, slug="x").parent
    if concepts != folder and concepts.is_dir():
        tag = re.compile(rf"^(?:tags:.*[\[ ,]{re.escape(slug)}[\],]|subject:\s*[\"']?{re.escape(slug)}\b)", re.M)
        for f in sorted(concepts.glob("*.md"))[:800]:
            try:
                with f.open(encoding="utf-8", errors="replace") as fh:
                    head = fh.read(600)
            except OSError:
                continue
            if tag.search(head):
                found.setdefault(f, "concept")
    rows = []
    for f, kind in found.items():
        info = note_info(f, root) if f.is_file() and f.is_relative_to(root) else None
        if info:
            rows.append({"id": info["id"], "title": info["title"], "kind": kind, "mtime": f.stat().st_mtime})
    rows.sort(key=lambda r: (NOTE_KINDS.index(r["kind"]) if r["kind"] in NOTE_KINDS else 9, -r["mtime"]))
    return rows[:limit]


def study_view(app: App, subject: str | None = None) -> dict:
    """What Study mode shows, for `subject` (else the timer's, else the one studied most today, else the first):
    the timer, today's study per subject, what's due in two weeks (quizzes and exams, tasks), start-by dates, recall
    cards (Quiz), the subject's notes, and the focus time that holds calls and messages."""
    out: dict = {"on": bool(app.settings.get("look.study_mode")), "features": sorted(m.id for m in app.enabled())}
    on = set(out["features"])
    subj = app.modules.get("subjects") if "subjects" in on else None
    st = app.modules.get("study") if "study" in on else None
    out["subjects"] = [{"slug": s["slug"], "name": s["name"]} for s in subj.subjects()] if subj else []
    slugs = [s["slug"] for s in out["subjects"]]
    out["timer"] = st.timer_view() if st else None
    out["focus_min"], out["break_min"] = (st.setting("focus_min"), st.setting("break_min")) if st else (25, 5)
    totals = st.totals(1) if st else {}
    out["today"] = [
        {"slug": k, "name": st.name_of(k), "seconds": round(v)}
        for k, v in sorted(totals.items(), key=lambda kv: -kv[1])
    ]
    slug = (subj.resolve(subject) if subj and subject else None) or (out["timer"] or {}).get("subject")
    slug = slug or next((r["slug"] for r in out["today"] if r["slug"] in slugs), None) or (slugs[0] if slugs else "")
    out["subject"] = slug
    out["name"] = subj.name_of(slug) if subj and slug else ""
    out["ai_policy"] = (subj.ai_policy(slug) or "") if subj and slug else ""  # allowed, hints, off; "": not set
    focus = app.availability.focus_until()
    out["focus"] = f"{focus:%H:%M}" if focus else None
    dl = app.modules.get("deadlines") if "deadlines" in on else None
    out["due"] = (
        [
            {"title": it["title"], "kind": it["kind"], "subject": it.get("subject") or "", "hours": round(h, 1)}
            for _, it, h in dl.upcoming(24 * 14)[:12]
        ]
        if dl
        else []
    )
    sb = app.modules.get("startby") if "startby" in on and dl else None
    out["start_by"] = sb.morning_rows() if sb else []
    qz = app.modules.get("quiz") if "quiz" in on else None
    out["recall"] = None
    if qz and slug and slug in qz.sources():  # its exam-prep or quiz notes
        _, items = qz.due(slug)
        out["recall"] = {
            "due": len(items),
            "cards": [{"text": v["text"], "section": v["section"]} for _, v in items[:3]],
        }
    out["notes"] = subject_notes(app, slug) if slug else []
    return out


def study_mode_act(app: App, args: dict) -> dict:
    v = args.get("on", True)
    on = v if isinstance(v, bool) else str(v).strip().lower() not in ("off", "false", "0", "no")
    return {"message": study_mode(app, on), "on": on}


def study_timer(app: App, args: dict) -> dict:
    st = _on(app, "study", "The Study tracker")
    do = str(args.get("do") or "")
    if do == "start":
        said = st.timer_start(str(args.get("subject") or "").strip() or None)
    elif do == "pause":
        said = st.timer_pause()
    elif do == "reset":
        said = st.timer_reset()
    else:
        raise Problem("Start, pause or reset?")
    return {"message": said, "timer": st.timer_view()}


# ------------------------------------------------------------------------------------------- one course
def subject_policy(app: App, args: dict) -> dict:
    """A course's AI policy from the Study pane: {"subject", "policy": allowed|hints|off|""}."""
    subj = _on(app, "subjects", "Subjects")
    slug = subj.resolve(str(args.get("subject") or ""))
    if not slug:
        raise Problem("Which subject?")
    said = subj.set_ai_policy(slug, str(args.get("policy") or ""))
    return {"message": said, "policy": subj.ai_policy(slug) or ""}


def notes_pdf(app: App, args: dict) -> dict:
    """A course's notes as one PDF (core/coursepdf.py), sent like /notes pdf: {"subject"}."""
    from kurooto.core import coursepdf

    return {"message": coursepdf.command(app, str(args.get("subject") or ""))}


def draft_check(app: App, args: dict) -> dict:
    """Check my draft for a file on this computer: {"path", "subject"?, "text"?}; the comments come as a message."""
    dr = _on(app, "drafts", "Check my draft")
    raw = str(args.get("path") or "").strip().strip("\"'")
    p = Path(raw).expanduser() if raw else None
    if p is None or not p.is_file():
        raise Problem("There's no file at that path.")
    subj = app.modules.get("subjects") if app.is_on("subjects") else None
    slug = subj.resolve(str(args.get("subject") or "")) if subj else None
    said = dr.check([p.resolve()], str(args.get("text") or ""), via="dashboard", subject=slug)
    return {"message": said + (" The comments come to your chat." if said.startswith("Checking") else "")}


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
    "study.mode": study_mode_act,
    "study.timer": study_timer,
    "subject.policy": subject_policy,
    "notes.pdf": notes_pdf,
    "draft.check": draft_check,
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
