"""Calm by default: every message Kurooto sends you on its own says why it came, and there's a daily limit.

Each such message carries a reason (which feature sent it and what for), the setting that controls it, and what it's
about (the deadline, class or project). On Telegram it gets two buttons:
    Why?          which feature, which setting (and its value now), and what it was about, from what was recorded
                  when it was sent; "No reason recorded" when whatever sent it didn't say (an add-on, a script)
    Less of this  Stop / Fewer / Another time, each changing one setting (the feature's own where it has one), with
                  Undo. Another time means: these wait for the evening bundle.
The phone app, the desktop and calls get the plain message, as before.

The daily limit (notify.calm.messages, 6; notify.calm.calls, 1): past it, messages wait for one evening bundle
(notify.calm.evening_at, 20:00); a call past it isn't placed and waits there as a line with a call link. After that
time, messages come as they are. Never held, never stoppable: the alarm, approvals, your own reminders, a deadline less
than 12 hours away, and anything urgent (Kurooto can't work until you act). Answers to what you asked or did aren't
counted at all, and neither are update notices (updates.done): several in a day fold into one (on Telegram the first is
changed in place to the newest, "and 2 earlier today"; where it can't be changed, the newest comes with that line).

The first time a day the limit holds a message, one line says so at once (exempt, uncounted), with three buttons:
Send them as they come today (the limit is off for the rest of the day, and what it held goes out now, in order),
Raise to 12 (notify.calm.messages doubled, with Undo; held ones go out up to the new limit) and Fine. Only the daily
limit's holds bring it; exam season, a quiet week and the per-kind rules below have their own reasons. The evening
bundle's first line says how many waited and why ("held by the daily limit of 6"); /calm shows today's count, the
limit and how many wait.

Two more per-kind rules, which Dreaming tunes by itself (core/policy.py, Dream RSI part two), each with Undo:
notify.calm.habituate (kind -> N: after N in a row you left unanswered, these wait for the evening bundle until you
answer one: getting used to things) and notify.calm.windows (kind -> "10:00-18:00": outside those hours they wait).

During exam season (modules/exam_season.py, its "budget" part), only deadlines, quizzes, the alarm and exam season
itself come during the day; the rest waits for the evening. On a lighter day after an exam or a heavy one
(core/rhythm.py, notify.calm.lighter_after) the daily limit is half; in a quiet week you asked for, whatever can wait
waits for each evening's bundle.

Once a month, from the same records: "you answered 1 of 19 after-class questions: turn them off?" (Apply / No), only
for kinds of questions you're meant to answer.

notify.calm.on = false restores the old behaviour exactly: nothing held, no buttons, nothing recorded.
What's recorded (state/calm.db, kept 45 days): when, the reason, the setting, what it was about, the first 300
characters (only privacy.keep_days, core/retention.py), and whether you tapped or answered it; a waiting message in
full until its evening.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import sqlite3
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave, owner_only

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.notify import Message

register_defaults(
    "notify",
    {
        "calm": {
            "on": True,  # reasons, Why? and Less of this, the daily limit; off: everything comes as it always did
            "messages": 6,  # messages a day that come by themselves; more wait for the evening bundle
            "calls": 1,  # calls a day that come by themselves (the alarm and calls you asked for don't count)
            "evening_at": "20:00",  # the evening bundle: what waited today
            "monthly": True,  # once a month: a kind of question you rarely answer, and whether to turn it off
            "stopped": [],  # kinds stopped with Less of this (when their feature has no setting of its own)
            "evening": [],  # kinds that always wait for the evening bundle (Less of this → Another time)
            "fewer": {},  # kind -> at most this many a day; more wait for the evening (Less of this → Fewer)
            "habituate": {},  # kind -> after this many in a row unanswered, they wait for the evening until you answer
            "windows": {},  # kind -> "10:00-18:00": outside these hours they wait for the evening bundle
        }
    },
)

ASKED = "asked"  # an answer to something you asked or did: never held, never counted, no buttons
KEEP_DAYS = 45
SUGGEST_EVERY_DAYS = 30
SUGGEST_MIN = 8  # at least this many questions of a kind in 30 days before it's suggested
SUGGEST_RATIO = 0.2  # ...and you answered at most this share of them
SUGGEST_AGAIN_DAYS = 90  # "No" keeps that kind out of the suggestion this long
DEADLINE_H = 12  # a deadline closer than this always comes
BUNDLE_CHARS = 3800  # one Telegram message
IGNORED_H = 3  # a message you could answer counts as ignored once it's this many hours old and still unanswered

EXEMPT = {
    "alarm": "it's about your alarm",
    "approval": "it asks for your OK",
    "own": "it's a reminder you set yourself",
    "deadline": f"a deadline is less than {DEADLINE_H} hours away",
    "urgent": "Kurooto can't do its job until you act on it",
    "security": "it's about who can reach your call line",
    "bundle": "it's the evening bundle itself",
    "limit": "it says the day's limit was reached, once a day",
}
TITLES = {  # features that aren't modules
    "ai": "The AI",
    "kurooto": "Kurooto",
    "health": "Kurooto keeps itself working",
    "updates": "Updates",
    "calm": "Calm",
    "agy": "agy",
    "claude": "Claude Code",
    "presence": "Online and offline messages",
    "reply_drafts": "Reply drafts",
    "keep": "Keep or drop",
    "rhythm": "Your rhythm",
}


@dataclass
class Change:
    """What one Less-of-this action does: one setting gets a new value, or one feature goes off."""

    said: str
    key: str = ""
    value: Any = None
    module: str = ""


Action = Callable[["App", dict], Change | None]
MUTE, FEATURE, DAILY = "mute", "feature", "daily"


@dataclass(frozen=True)
class Reason:
    id: str
    what: str  # plain words: why it came
    many: str = ""  # what they're called together ("after-class questions")
    setting: str = ""  # the setting that controls it
    stop: Action | str | None = MUTE  # MUTE: Calm's own list; FEATURE: the feature goes off; None: no Stop
    fewer: Action | str | None = None  # DAILY: at most one a day; None: no Fewer
    later: bool = True  # Another time (the evening bundle) is offered
    exempt: str = ""  # one of EXEMPT: never held, never stopped
    suggest: bool = False  # a question you're meant to answer: the monthly suggestion may offer to stop it
    feature: str = ""
    counted: bool = True  # False: not counted against the daily limit, and never held by it
    fold: bool = False  # several in a day fold into one (Calm._fold)

    @property
    def owner(self) -> str:
        return self.feature or self.id.split(".")[0]

    @property
    def plural(self) -> str:
        return self.many or self.what


def to(value, said: str) -> Action:
    """Stop / Fewer: the message's own setting gets this value."""
    return lambda app, rec: Change(said, key=rec.get("setting") or "", value=value) if rec.get("setting") else None


def _ping_stop(app: App, rec: dict) -> Change:
    urgent = app.settings.get("deadlines.urgent_h") or 6
    said = f"no more reminders a day ahead; the last {urgent} hours' ones still come"
    return Change(said, key="deadlines.ping_h", value=urgent)


def _first_time(key: str) -> Action:
    """'daily 08:00,18:00' -> 'daily 08:00' (one a day instead of several)."""

    def fn(app: App, rec: dict) -> Change | None:
        spec = str(app.settings.get(key) or "").strip()
        head, _, times = spec.partition(" ")
        if head != "daily" or "," not in times:
            return None
        first = times.split(",")[0].strip()
        return Change(f"once a day, at {first}", key=key, value=f"daily {first}")

    return fn


def _weekly(key: str, day: str) -> Action:
    """'daily 08:00' -> 'weekly <day> 08:00'."""

    def fn(app: App, rec: dict) -> Change | None:
        spec = str(app.settings.get(key) or "").strip()
        head, _, at = spec.partition(" ")
        if head != "daily" or "," in at or not at:
            return None
        return Change(f"once a week ({day.title()} {at})", key=key, value=f"weekly {day} {at}")

    return fn


def _double(key: str, unit: str) -> Action:
    def fn(app: App, rec: dict) -> Change | None:
        try:
            n = int(app.settings.get(key) or 0)
        except (TypeError, ValueError):
            return None
        if n <= 0:
            return None
        return Change(f"half as often ({n * 2} {unit} instead of {n})", key=key, value=n * 2)

    return fn


def _skip_subject(app: App, rec: dict) -> Change | None:
    slug = rec.get("item") or ""
    skip = list(app.settings.get("capture.skip_subjects") or [])
    if not slug or slug in skip:
        return None
    return Change(f"none after {rec.get('about') or slug}", key="capture.skip_subjects", value=[*skip, slug])


def inside(window: str, t: dt.datetime) -> bool:
    """Is t within "10:00-18:00" (a window past midnight wraps)? A window that can't be read lets everything in."""
    try:
        a, b = (dt.time.fromisoformat(x.strip().zfill(5)) for x in str(window).split("-", 1))
    except ValueError:
        return True
    tt = t.time()
    return (a <= tt or tt < b) if a > b else a <= tt < b


def streak(rows, at: float) -> int:
    """How many in a row you left unanswered as of `at`: rows are (sent ts, answered ts or None), newest first; ones
    younger than IGNORED_H hours don't count yet, and one answered by then ends the run."""
    n = 0
    for ts, answered in rows:
        if ts > at - IGNORED_H * 3600:
            continue
        if answered is not None and answered <= at:
            break
        n += 1
    return n


def R(rid: str, what: str, **kw) -> Reason:
    return Reason(rid, what, **kw)


# Every reason a message comes by itself. A message without one says "No reason recorded" (it isn't guessed).
REASONS: dict[str, Reason] = {
    r.id: r
    for r in (
        # ------------------------------------------------------------------ never held, never stopped
        R("reminders.own", "a reminder you set", exempt="own", stop=None, later=False),
        R("calls.own", "a call you asked for", exempt="own", stop=None, later=False),
        R("study.timer", "the end of a study session you started with a length", exempt="own", stop=None),
        R("quiz.checkin", "a quiz time you set", exempt="own", stop=None, later=False),
        R(
            "calendar.remind",
            "a reminder before an event in your calendar",
            setting="calendar.remind_min",
            exempt="own",
            stop=None,
        ),
        R("research.remind", "a reminder you asked for about a project", exempt="own", stop=None),
        R("lidsafe.failed", "a reminder of yours your call line couldn't get to your phone", exempt="own", stop=None),
        R("alarm.ring", "your wake-up alarm", exempt="alarm", stop=None, later=False),
        R(
            "exam_season.leave",
            "the alarm to leave for an exam",
            setting="exam_season.leave_alarm",
            exempt="alarm",
            stop=None,
        ),
        R(
            "exam_season.alarm_check",
            "the nightly alarm check during exams",
            setting="exam_season.alarm_check",
            exempt="alarm",
            stop=None,
        ),
        R("health.alarm", "tonight's alarm might not ring", exempt="alarm", stop=None),
        R("calls.device_paired", "a device was paired with your call line", exempt="security", stop=None),
        R("reply_drafts.approval", "a reply draft waiting for Send, Edit or Discard", exempt="approval", stop=None),
        R("agy.consent", "whether agy may use Kurooto's tools", exempt="approval", stop=None),
        R(
            "tap.approval",
            "an AI request wants to set an alarm or place a call: your OK first",
            exempt="approval",
            stop=None,
        ),
        R(
            "presence.line",
            "whether your call line may say when this computer is offline",
            exempt="approval",
            stop=None,
        ),
        R(
            "calm.bundle",
            "the evening bundle: what waited today",
            setting="notify.calm.evening_at",
            exempt="bundle",
            stop=None,
        ),
        R(
            "calm.limit",
            "the day's limit was reached, so the rest wait for the evening bundle",
            setting="notify.calm.messages",
            exempt="limit",
            stop=None,
            later=False,
        ),
        R("ai.limit", "the AI you picked hit a limit or was signed out", setting="brain.fallback", stop=None),
        R("google.signin", "a Google sign-in ended, so what uses it is paused", stop=None),
        R("kurooto.crash", "Kurooto kept crashing", stop=None),
        R("calls.no_line", "a call that couldn't ring because your call line wasn't connected", stop=None),
        # ------------------------------------------------------------------------------ deadlines and study
        R(
            "deadlines.reminder",
            "a reminder before something on your deadline list is due",
            many="deadline reminders",
            setting="deadlines.ping_h",
            stop=_ping_stop,
        ),
        R(
            "deadlines.call",
            "the call a few hours before a deadline",
            setting="deadlines.call",
            stop=to(False, "no deadline calls; a message comes instead"),
        ),
        R(
            "deadlines.overdue",
            'an "Overdue?" question after a deadline passed',
            many='"Overdue?" questions',
            setting="deadlines.overdue_check",
            stop=to(False, 'no more "Overdue?" questions'),
            suggest=True,
        ),
        R(
            "deadlines.meeting_brief",
            "the evening before a meeting: the project since you last met",
            setting="deadlines.meeting_brief",
        ),
        R(
            "meetings.actions",
            "a meeting's action items you said Later to, back the next evening",
            setting="meetings.minutes",
        ),
        R("deadlines.exam_mode", "exam mode starting for a quiz or exam", setting="deadlines.exam_mode_days"),
        R(
            "startby.tell",
            "a start-by date for a deadline (an estimate)",
            many="start-by messages",
            setting="startby.tell",
            stop=to(False, "no more start-by messages (/startby still shows them)"),
        ),
        R(
            "startby.ask_exams",
            "how long a subject's exams take to prepare for",
            setting="startby.ask_exams",
            stop=to(False, "no more of these questions"),
            suggest=True,
            many="exam-preparation questions",
        ),
        R(
            "quiz.offer",
            "the evening before a quiz or exam, an offer to practise",
            many="practice offers",
            setting="quiz.offer_at",
            stop=to("", "no more practice offers (/quiz still works)"),
            later=False,
            suggest=True,
        ),
        R(
            "quiz.exam_daily",
            "exam mode's daily practice check-in",
            many="practice check-ins",
            setting="quiz.exam_daily",
            stop=to("", "no daily practice check-ins"),
            later=False,
            suggest=True,
        ),
        R("quiz.call", "a quiz by call", setting="quiz.by_call", stop=to(False, "quizzes come as messages")),
        R(
            "quiz.links",
            "a link recall card: how two of your concepts relate",
            many="link cards",
            setting="quiz.links",
            stop=to(False, "no more link cards by themselves (/card still gives one)"),
            fewer=DAILY,
            suggest=True,
        ),
        R(
            "packs.offer",
            "an offer to build a revision pack before an exam",
            many="revision pack offers",
            setting="skills.auto_pack",
            stop=to("off", "no more revision pack offers"),
            suggest=True,
            feature="skills",
        ),
        R(
            "capture.after_class",
            "after a class, a question about what was worth keeping",
            many="after-class questions",
            setting="capture.skip_subjects",
            stop=FEATURE,
            fewer=_skip_subject,
            suggest=True,
        ),
        R(
            "doubts.before_class",
            "your open doubts before a subject's class",
            many="doubt lists",
            setting="doubts.before_min",
            later=False,
        ),
        R("exam_season.start", "exam season starting"),
        R(
            "exam_season.eve",
            "the evening before an exam: where it is, seat, calculator, ID",
            many="exam-eve questions",
            setting="exam_season.eve",
            stop=to(False, "no more exam-eve questions"),
            later=False,
            suggest=True,
        ),
        R(
            "exam_season.debrief",
            "a two-minute debrief after an exam",
            many="exam debriefs",
            setting="exam_season.debrief",
            stop=to(False, "no more exam debriefs"),
            suggest=True,
        ),
        R(
            "exam_season.revise",
            "the evening question: did you cover today's revision topics?",
            many="revision questions",
            setting="exam_season.revision_ask",
            stop=to(False, "no more revision questions"),
            later=False,
            suggest=True,
        ),
        # ----------------------------------------------------------------------------------- your day
        R(
            "checkins.question",
            "a check-in you set up",
            many="check-in questions",
            setting="checkins.times",
            stop=to(None, "that check-in is off"),
            later=False,
            suggest=True,
        ),
        R(
            "checkins.call",
            "a check-in by call",
            setting="checkins.by_call",
            stop=to(False, "check-ins come as messages"),
        ),
        R("checkins.moved", "a check-in call that moved to another time", setting="checkins.by_call"),
        R("startby.window", "Start-by's day window moved to when you're up", setting="startby.learn_window"),
        R(
            "rhythm.night",
            "the night hours (and mornings) moved to when you're usually quiet",
            setting="availability.learn_night",
            stop=to(False, "the night hours stay where they are"),
        ),
        R(
            "rhythm.lighter",
            "a lighter day after an exam or a heavy day",
            setting="notify.calm.lighter_after",
            stop=to(False, "no more lighter days"),
            later=False,
        ),
        R(
            "rhythm.absence",
            "a check after days of not hearing from you",
            setting="availability.absence_days",
            stop=to(0, "no more of these"),
            later=False,
        ),
        R(
            "alarm.suggest",
            "an alarm suggested before your usual bedtime, with none set",
            setting="alarm.suggest",
            stop=to(False, "no more alarm suggestions"),
            later=False,
        ),
        R(
            "startby.negotiate",
            "a reshaped plan for a slipping deadline, instead of the same reminder again",
            many="reshaped plans",
            setting="startby.negotiate",
            stop=to(False, "no more reshaped plans; reminders come as before"),
        ),
        R("startby.moved", "the part of a deadline's work you moved to today", exempt="own", stop=None),
        R(
            "cases.rephrased",
            "a phrasing learned because you said it again in other words",
            setting="cases.learn_rephrased",
        ),
        R("cases.repaired", "a phrasing learned because you picked the same reading twice", setting="cases.learn"),
        R("subjects.catch_up", "a catch-up for a class you missed", setting="subjects.catch_up"),
        R("checkins.learned", "a check-in's time moved to when you've been doing it", setting="checkins.learn_times"),
        R("weekly.summary", "the weekly summary", setting="weekly.when", stop=FEATURE),
        R("weekly.call", "the Sunday review call", setting="weekly.call", stop=to(False, "no Sunday review call")),
        R(
            "quests.day",
            "a first-week quest",
            many="first-week quests",
            setting="quests.days",
            stop=FEATURE,
            suggest=True,
        ),
        # ------------------------------------------------------------------------------------- Google
        R(
            "google.announcement",
            "a new announcement in one of your Classroom courses",
            many="Classroom announcements",
            setting="google.classroom",
            fewer=DAILY,
        ),
        R("google.setup", "a Google feature that's paused until you set it up again"),
        R("classroom_notes.filed", "Classroom posts filed into your notes", setting="classroom_notes.at", fewer=DAILY),
        R("classroom_notes.failed", "Classroom posts the AI couldn't file"),
        R(
            "mail_digest.digest",
            "your mail digest",
            many="mail digests",
            setting="mail_digest.at",
            stop=FEATURE,
            fewer=_first_time("mail_digest.at"),
        ),
        R("mail_digest.setup", "what the mail digest may read", setting="mail_digest.read"),
        R("mail_digest.failed", "a mail digest that didn't come together"),
        R("digest_email.failed", "the digest couldn't be emailed to you"),
        # ---------------------------------------------------------------------------- notes and research
        R(
            "research.papers",
            "the new-papers digest",
            setting="research.papers",
            fewer=_weekly("research.papers", "mon"),
        ),
        R(
            "research_addon.latex",
            "the LaTeX tracker's morning line: a build that broke, or words written",
            many="LaTeX tracker lines",
            setting="research_addon.latex",
            stop=to(False, "the LaTeX tracker is off (its card switches it back on)"),
        ),
        R(
            "research.idle",
            "a question about a project with no commits for a while",
            many="questions about quiet projects",
            setting="research.idle_days",
            stop=to(0, "no more questions about quiet projects"),
            fewer=_double("research.idle_days", "days"),
            suggest=True,
        ),
        R(
            "retro.suggestion",
            "a suggestion from the look back",
            many="look-back suggestions",
            setting="retro.when",
            stop=FEATURE,
            fewer=_weekly("retro.when", "sun"),
            suggest=True,
        ),
        R(
            "retro.routine",
            "a routine the look back saw in your records (the same thing at the same time, 3+ weeks)",
            many="routines from the look back",
            setting="retro.routines",
            stop=to(False, "no more routines suggested from your records"),
            suggest=True,
        ),
        R(
            "retro.fixed",
            "a data fix the look back was sure of (two copies of one deadline), with Undo",
            many="data fixes from the look back",
            setting="retro.fixes",
            stop=to(False, "no more data fixes by the look back"),
        ),
        R(
            "learning.skill",
            "a skill learned (or improved) from a request that took many steps",
            many="learned skills",
            setting="learning.skills",
            stop=to(False, "no more skills learned from requests"),
            fewer=DAILY,
        ),
        R(
            "learning.lesson",
            "a lesson a skill took from your correction",
            setting="learning.corrections",
            stop=to(False, "skills don't take lessons from corrections any more"),
        ),
        R(
            "learning.remember",
            "facts from your chats and calls kept in your how-to-help-me note",
            setting="learning.remember",
            stop=to(False, "nothing more is kept by itself"),
        ),
        R(
            "remember.recheck",
            "a line in your how-to-help-me note that hasn't come up in a while: still true?",
            many="still-true questions",
            setting="remember.recheck_days",
            stop=to(0, "no more still-true questions"),
            suggest=True,
        ),
        R(
            "cases.review",
            "the look back at what you typed that I didn't understand",
            setting="cases.review_days",
            fewer=_double("cases.review_days", "days"),
        ),
        R("handwritten.got", "a PDF of handwriting to be written out at night"),
        R("handwritten.done", "handwritten pages written out into notes", fewer=DAILY),
        R("handwritten.failed", "a handwritten file that couldn't be written out"),
        R("handwritten.linked", "handwritten notes linked to their lecture, course page and concepts", fewer=DAILY),
        R("books.read", "a book that was read", setting="books.at"),
        R("space.cleaned", "the Space keeper cleaned off old files", setting="space.when"),
        R("integrate.summary", "what the concept graph did overnight", setting="integrate.at"),
        R("gbrain.upkeep", "the notes brain's nightly upkeep didn't finish", setting="gbrain.upkeep"),
        R(
            "gbrain.checkup",
            "the notes brain's weekly checkup",
            setting="gbrain.checkup",
            stop=to(False, "no weekly checkup"),
        ),
        R("notes_sync.clash", "notes that changed in two places at once"),
        R("notes_sync.failed", "Notes sync didn't work"),
        R("profile.failed", "Profile sync didn't work"),
        R("backups.failed", "a backup didn't work"),
        # ---------------------------------------------------------------------------------- Kurooto itself
        R("health.now", "something that stopped working, before a deadline or exam", setting="health.on"),
        R("health.digest", "things that stopped working and need a look", setting="health.on"),
        R("updates.available", "a new version to install (updates.mode is ask)", setting="updates.mode", stop=None),
        R("updates.failed", "an update that couldn't be prepared", setting="updates.mode"),
        R("updates.done", "Kurooto updated itself", setting="updates.mode", counted=False, fold=True),
        R("updates.rolled_back", "an update that was undone because it kept crashing", setting="updates.mode"),
        R("updates.whats_new", "what's new after an update"),
        R("calls.line_update", "your call line couldn't be updated", setting="updates.mode"),
        R("calls.rang_offline", "a call your call line placed while this computer was off"),
        R("calls.held", "a call that waits for a better time"),
        R("calls.review", "what Kurooto fixed and learned looking back at a call", setting="calls.review"),
        R("local_models.spill", "a local model that doesn't fit your graphics card", setting="local_models"),
        R("dreaming.morning", "what Kurooto did while you slept, and the loose ends", setting="dreaming.when"),
        R(
            "infer.done",
            "something set up from what you said (a project, a class, a quiz, a routine)",
            setting="infer.on",
        ),
        R(
            "calm.monthly",
            "the monthly look at what you rarely answer",
            setting="notify.calm.monthly",
            stop=to(False, "no more monthly suggestions"),
            later=False,
        ),
        R(
            "keep.ask",
            "a look at what you use of each feature, with Keep, Quiet and Off",
            many="questions about the features you use",
            setting="keep.ask",
            stop=to(False, "no more questions about the features you use (/keep still shows the counts)"),
        ),
    )
}


def _jsonable(rows) -> list:
    return [[list(b) if isinstance(b, tuple) else b for b in row] for row in rows or []]


def _data(buttons) -> list[str]:
    """The callback data of a message's buttons (not links)."""
    out = []
    for row in buttons or []:
        for b in row:
            if isinstance(b, (list, tuple)) and len(b) == 2 and isinstance(b[1], str):
                out.append(b[1])
    return out


SCHEMA = """
create table if not exists sent (
    id text primary key, ts real, day text, why text, setting text, feature text, about text, item text,
    kind text, title text, text text, state text, held text, ref text, buttons text, map_kind text, map_ref text,
    answered real, exempt text, budgeted integer, msg text
);
create index if not exists sent_day on sent(day, state);
create index if not exists sent_why on sent(why, ts);
"""


class Calm:
    def __init__(self, app: App):
        self.app = app
        self.db_file = app.paths.state / "calm.db"
        self.state_file = app.paths.state / "calm.json"
        self.undo_file = app.paths.state / "calm-undo.json"
        self._lock = threading.RLock()
        self._ready = False

    # ------------------------------------------------------------------------------------------ settings
    def s(self, key: str, default=None):
        v = self.app.settings.get(f"notify.calm.{key}")
        return default if v is None else v

    def on(self) -> bool:
        return bool(self.s("on", True))

    def limit(self, key: str, default: int) -> int:
        try:
            return max(0, int(self.s(key, default)))
        except (TypeError, ValueError):
            return default

    def day_limit(self) -> int:
        """notify.calm.messages, halved on a lighter day after an exam or a heavy one (core/rhythm.py)."""
        n = self.limit("messages", 6)
        rh = getattr(self.app, "rhythm", None)
        return rh.lighter_limit(n) if rh is not None else n

    def evening_at(self, day: dt.date | None = None) -> dt.datetime:
        try:
            t = dt.time.fromisoformat(str(self.s("evening_at", "20:00")).strip().zfill(5))
        except ValueError:
            t = dt.time(20, 0)
        return dt.datetime.combine(day or now().date(), t)

    # ---------------------------------------------------------------------------------------- the ledger
    @contextlib.contextmanager
    def _db(self):
        with self._lock:
            db = sqlite3.connect(self.db_file, timeout=10)
            try:
                if not self._ready:
                    db.executescript(SCHEMA)
                    owner_only(self.db_file)
                    self._ready = True
                db.row_factory = sqlite3.Row
                yield db
                db.commit()
            finally:
                db.close()

    def _insert(self, rec: dict) -> None:
        cols = ",".join(rec)
        with self._db() as db:
            db.execute(f"insert into sent({cols}) values({','.join('?' * len(rec))})", tuple(rec.values()))  # noqa: S608

    def get(self, rid: str) -> dict | None:
        with self._db() as db:
            row = db.execute("select * from sent where id=?", (rid,)).fetchone()
        return dict(row) if row else None

    def _count(self, day: str, why: str | None = None, kind: str = "msg") -> int:
        q = "select count(*) from sent where day=? and budgeted=1 and state in ('sent','rang')"
        args: list = [day]
        q += " and kind='ring'" if kind == "ring" else " and kind!='ring'"
        if why:
            q += " and why=?"
            args.append(why)
        with self._db() as db:
            return int(db.execute(q, args).fetchone()[0])

    def today(self) -> dict:
        """Today's numbers: messages and calls counted against the limit, and what waits for the evening."""
        day = now().date().isoformat()
        with self._db() as db:
            waiting = int(db.execute("select count(*) from sent where state='held'").fetchone()[0])
            by_limit = int(db.execute("select count(*) from sent where state='held' and held='budget'").fetchone()[0])
        return {
            "messages": self._count(day),
            "messages_max": self.day_limit(),
            "calls": self._count(day, kind="ring"),
            "calls_max": self.limit("calls", 1),
            "waiting": waiting,
            "waiting_limit": by_limit,  # of those, held by the daily limit
            "flowing": self.flowing(),  # Send them as they come today: the limit is off today
            "evening_at": f"{self.evening_at():%H:%M}",
        }

    def flowing(self, t: dt.datetime | None = None) -> bool:
        """You tapped Send them as they come today: the daily limit holds nothing more today."""
        day = (t or now()).date().isoformat()
        return (jload(self.state_file, {}) or {}).get("flow_day") == day

    # ------------------------------------------------------------------------------------------ deciding
    def reason(self, why: str | None) -> Reason | None:
        return REASONS.get(why or "")

    def exempt(self, why: str | None, kind: str = "", urgent: bool = False, due: str | None = None) -> str:
        """Why this one always comes ("" if it doesn't)."""
        r = self.reason(why)
        if r is not None and r.exempt:
            return r.exempt
        if kind == "approval":
            return "approval"
        if urgent:
            return "urgent"
        if due:
            try:
                d = dt.datetime.fromisoformat(str(due))
                d = d.astimezone().replace(tzinfo=None) if d.tzinfo else d
            except ValueError:
                return ""
            if dt.timedelta(0) <= d - now() < dt.timedelta(hours=DEADLINE_H):
                return "deadline"
        return ""

    def exam_keep(self) -> tuple | None:
        """During exam season (with its budget part on): the features whose messages still come during the day."""
        es = self.app.modules.get("exam_season")
        if es is None or not self.app.is_on("exam_season") or not es.setting("budget"):
            return None
        try:
            b = es.budget_during_exams()
        except Exception as e:
            self.app.events.emit("calm_failed", error=f"exam season: {e}"[:200])
            return None
        return tuple(b["keep"]) if b else None

    def _wait(self, why: str, feature: str, t: dt.datetime, counted: bool = True) -> str:
        """Why a message waits for the evening bundle ("" if it goes now)."""
        keep = self.exam_keep()
        if keep is not None and feature not in keep:
            return "exams"  # even after this evening's bundle: until the next one
        rh = getattr(self.app, "rhythm", None)
        if rh is not None and rh.quiet_week(t):
            return "quiet"  # Busy, quiet for a week (core/rhythm.py): each evening's bundle
        if t >= self.evening_at(t.date()):
            return ""
        if why in (self.s("evening") or []):
            return "evening"
        cap = (self.s("fewer") or {}).get(why)
        if cap is not None and self._count(t.date().isoformat(), why=why) >= int(cap):
            return "fewer"
        n = (self.s("habituate") or {}).get(why)
        if n and self.ignored(why, t) >= int(n):
            return "habit"
        window = (self.s("windows") or {}).get(why)
        if window and not inside(window, t):
            return "window"
        if counted and self._count(t.date().isoformat()) >= self.day_limit() and not self.flowing(t):
            return "budget"
        return ""

    def ignored(self, why: str, t: dt.datetime) -> int:
        """How many of this kind you could answer came in a row without an answer (streak())."""
        with self._db() as db:
            rows = db.execute(
                "select ts, answered from sent where why=? and state in ('sent','bundled') and "
                "(buttons!='[]' or map_kind!='') order by ts desc, rowid desc limit 30",
                (why,),
            ).fetchall()
        return streak([(float(a), b) for a, b in rows], t.timestamp())

    def decide(self, msg: Message) -> str:
        """Before a message goes out: "send", "hold" (for the evening bundle) or "stop" (you stopped this kind).
        Only messages that came by themselves are looked at; anything going wrong here lets the message through."""
        if not self.on() or msg.why == ASKED or msg.kind == "call":
            return "send"
        try:
            return self._decide(msg)
        except Exception as e:
            self.app.events.emit("calm_failed", error=f"{type(e).__name__}: {e}"[:200])
            return "send"

    def _decide(self, msg: Message) -> str:
        t = now()
        r = self.reason(msg.why)
        msg.rid = "n" + uuid.uuid4().hex[:10]
        if r is not None and not msg.setting:
            msg.setting = r.setting or None
        rec = {
            "id": msg.rid,
            "ts": t.timestamp(),
            "day": t.date().isoformat(),
            "why": msg.why or "",
            "setting": msg.setting or "",
            "feature": r.owner if r else (msg.why or "").split(".")[0],
            "about": (msg.about or "")[:200],
            "item": (msg.item or "")[:120],
            "kind": msg.kind,
            "title": (msg.title or "")[:120],
            "text": msg.text[:300],
            "buttons": json.dumps(_data(msg.buttons)),
            "map_kind": msg.map_kind or "",
            "map_ref": str(msg.map_ref or ""),
            "budgeted": 0,
        }
        ex = self.exempt(msg.why, msg.kind, msg.urgent, msg.due)
        if ex or not msg.why:
            self._insert({**rec, "state": "sent", "exempt": ex})
            return "send"
        if msg.why in (self.s("stopped") or []):
            self._insert({**rec, "state": "stopped"})
            self.app.events.emit("calm_stopped", why=msg.why)
            return "stop"
        counted = r is None or r.counted
        wait = self._wait(msg.why, rec["feature"], t, counted)
        if wait:
            body = {k: v for k, v in msg.__dict__.items() if k not in ("rid", "extra")}
            body["buttons"] = _jsonable(msg.buttons)
            self._insert(
                {**rec, "state": "held", "held": wait, "msg": json.dumps(body, ensure_ascii=False, default=str)}
            )
            self.app.events.emit("calm_held", why=msg.why, held=wait)
            if wait == "budget":
                self._tell_limit(t)
            return "hold"
        msg.extra = [[("Why?", f"calm:{msg.rid}:why"), ("Less of this", f"calm:{msg.rid}:less")]]
        if r is not None and r.fold and self._fold(msg, rec):
            return "folded"
        self._insert({**rec, "state": "sent", "budgeted": 1 if counted else 0})
        return "send"

    def _fold(self, msg: Message, rec: dict) -> bool:
        """A kind that folds (updates.done) came earlier today: this one says "(and N earlier today)". On Telegram the
        first of them is changed in place to it (True: nothing new is sent); otherwise it comes as a new message."""
        with self._db() as db:
            rows = db.execute(
                "select ref from sent where day=? and why=? and state='sent' order by ts, rowid",
                (rec["day"], rec["why"]),
            ).fetchall()
        if not rows:
            return False
        msg.text = f"{msg.text.rstrip().rstrip('.')} (and {len(rows)} earlier today)."
        rec["text"] = msg.text[:300]
        ref = next((x[0] for x in rows if x[0]), None)
        if ref is None or not self.app.notifier.edit(ref, msg):
            return False
        self._insert({**rec, "state": "sent", "budgeted": 0, "ref": ref})
        self.app.events.emit("calm_folded", why=rec["why"], earlier=len(rows))
        return True

    def _tell_limit(self, t: dt.datetime) -> None:
        """The first message the daily limit holds today: one line says so at once, with what you can do. Never
        fails the message it's about."""
        day = t.date().isoformat()
        try:
            with self._lock:
                st = jload(self.state_file, {}) or {}
                if st.get("limit_told") == day:
                    return
                st["limit_told"] = day
                jsave(self.state_file, st)
            lim, n = self.day_limit(), self.limit("messages", 6)
            if lim <= 0:  # nothing by itself during the day is what you chose
                return
            came = "messages that came by themselves" if lim != 1 else "message that came by itself"
            text = (
                f"That's today's {lim} {came}. The rest wait for the evening bundle at "
                f"{self.evening_at(t.date()):%H:%M}, which lists each one."
            )
            if lim != n:
                text += f" (Today is a lighter day: half the usual {n}.)"
            self.app.notify(
                text,
                kind="info",
                why="calm.limit",
                buttons=[
                    [("Send them as they come today", f"calm:{day}:flow")],
                    [(f"Raise to {n * 2}", f"calm:{day}:raise"), ("Fine", f"calm:{day}:fine")],
                ],
            )
            self.app.events.emit("calm_limit_told", limit=lim)
        except Exception as e:
            self.app.events.emit("calm_failed", error=f"limit notice: {type(e).__name__}: {e}"[:200])

    def release(self, cap: int | None = None) -> int:
        """Today's messages the daily limit held go out now, in the order they came, with Why? and Less of this
        (cap: only while today's count is under it). A question dealt with meanwhile doesn't. How many went."""
        from kurooto.core.ask import OPEN
        from kurooto.core.notify import Message

        day = now().date().isoformat()
        with self._db() as db:
            rows = db.execute(
                "select * from sent where state='held' and held='budget' and day=? order by ts, rowid", (day,)
            ).fetchall()
        n = 0
        for rec in (dict(x) for x in rows):
            if cap is not None and self._count(day) >= cap:
                break
            if rec.get("map_kind") == "ask":
                q = self.app.ask.get(rec.get("map_ref") or "")
                if not q or q.get("status") not in OPEN:
                    with self._db() as db:
                        db.execute("update sent set state='settled', msg=null where id=?", (rec["id"],))
                    continue
            try:
                body = json.loads(rec.get("msg") or "{}")
                m = Message(**{k: v for k, v in body.items() if k in Message.__dataclass_fields__})
            except (ValueError, TypeError):
                m = Message(rec.get("text") or "", kind=rec.get("kind") or "info")
            with self._db() as db:
                db.execute("update sent set state='sent', budgeted=1, msg=null where id=?", (rec["id"],))
            m.rid = rec["id"]
            m.extra = [[("Why?", f"calm:{m.rid}:why"), ("Less of this", f"calm:{m.rid}:less")]]
            try:
                self.app.notifier.release(m)
            except Exception as e:
                self.app.events.emit("calm_failed", error=f"release: {type(e).__name__}: {e}"[:200])
            n += 1
        if n:
            self.app.events.emit("calm_released", items=n)
        return n

    def delivered(self, rid: str, ref) -> None:
        """The Telegram message id, so Why? and Less of this can answer under it."""
        if ref is None:
            return
        try:
            with self._db() as db:
                db.execute("update sent set ref=? where id=?", (str(ref), rid))
        except sqlite3.Error as e:
            self.app.events.emit("calm_failed", error=f"delivered: {e}"[:200])

    def call_ok(self, why: str | None, key: str = "", alarm: bool = False, due: str | None = None) -> bool:
        """Before a call rings: True to ring. One a day by default (the alarm, calls you asked for and a deadline
        under 12 hours away always ring; the same call again, e.g. its repeat, isn't counted twice)."""
        if not self.on() or alarm or not why or why == ASKED:
            return True
        try:
            r = self.reason(why)
            if self.exempt(why, due=due):
                return True
            t = now()
            day = t.date().isoformat()
            with self._db() as db:
                again = db.execute(
                    "select 1 from sent where day=? and kind='ring' and item=? and state='rang'", (day, key)
                ).fetchone()
            if key and again:
                return True
            feature = r.owner if r else why.split(".")[0]
            keep = self.exam_keep()
            over = (keep is not None and feature not in keep) or self._count(day, kind="ring") >= self.limit("calls", 1)
            rec = {
                "id": "c" + uuid.uuid4().hex[:10],
                "ts": t.timestamp(),
                "day": day,
                "why": why,
                "setting": r.setting if r else "",
                "feature": feature,
                "item": key[:120],
                "kind": "ring",
                "state": "call_held" if over else "rang",
                "budgeted": 0 if over else 1,
            }
            self._insert(rec)
            if over:
                self.app.events.emit("calm_call_held", why=why)
            return not over
        except Exception as e:
            self.app.events.emit("calm_failed", error=f"call: {type(e).__name__}: {e}"[:200])
            return True

    def hold(self, text: str, why: str | None, **kw) -> None:
        """Straight into the evening bundle (a call that wasn't placed)."""
        from kurooto.core.notify import Message

        msg = Message(text, why=why, **kw)
        t = now()
        r = self.reason(why)
        body = {k: v for k, v in msg.__dict__.items() if k not in ("rid", "extra")}
        body["buttons"] = _jsonable(msg.buttons)
        self._insert(
            {
                "id": "n" + uuid.uuid4().hex[:10],
                "ts": t.timestamp(),
                "day": t.date().isoformat(),
                "why": why or "",
                "setting": (r.setting if r else "") or "",
                "feature": r.owner if r else "",
                "kind": msg.kind,
                "title": (msg.title or "")[:120],
                "text": text[:300],
                "state": "held",
                "held": "calls",
                "buttons": "[]",
                "budgeted": 0,
                "msg": json.dumps(body, ensure_ascii=False, default=str),
            }
        )

    # --------------------------------------------------------------------------------- answered or not
    def touched(self, button: str | None = None, map_kind: str | None = None, map_ref=None) -> None:
        """You tapped a button on one of these messages, or replied to it: it counts as answered (for the monthly
        suggestion). Why? and Less of this don't count."""
        if not self.on() or (button and button.startswith("calm:")):
            return
        since = (now() - dt.timedelta(days=KEEP_DAYS)).timestamp()
        try:
            with self._db() as db:
                if button:
                    row = db.execute(
                        "select id from sent where ts>=? and instr(buttons, ?)>0 and answered is null "
                        "order by ts desc, rowid desc limit 1",
                        (since, json.dumps(button)),
                    ).fetchone()
                elif map_kind:
                    row = db.execute(
                        "select id from sent where ts>=? and map_kind=? and map_ref=? and answered is null "
                        "order by ts desc, rowid desc limit 1",
                        (since, map_kind, str(map_ref or "")),
                    ).fetchone()
                else:
                    return
                if row:
                    db.execute("update sent set answered=? where id=?", (now().timestamp(), row[0]))
        except sqlite3.Error as e:
            self.app.events.emit("calm_failed", error=f"touched: {e}"[:200])

    # ---------------------------------------------------------------------------------- the evening bundle
    def start(self) -> None:
        sch = self.app.scheduler
        sch.action("calm.tick", lambda p: self.tick())
        sch.every("calm:tick", "every 5m", "calm.tick", module="calm", misfire="coalesce")

    def tick(self) -> dict:
        """Every few minutes: once it's evening, the bundle (and the monthly suggestion, when it's time)."""
        t = now()
        st = jload(self.state_file, {}) or {}
        out: dict = {}
        if t >= self.evening_at(t.date()) and st.get("bundle_day") != t.date().isoformat():
            st["bundle_day"] = t.date().isoformat()
            jsave(self.state_file, st)
            out["bundled"] = self.bundle()
            out["suggested"] = self.monthly()
            self.prune()
        return out

    def held(self) -> list[dict]:
        with self._db() as db:
            rows = db.execute("select * from sent where state='held' order by ts, rowid").fetchall()
        return [dict(r) for r in rows]

    def bundle(self) -> int:
        """What waited today, as one message (its buttons numbered by item); files come after it. The phone app
        gets the waiting questions one by one, as it would have."""
        from kurooto.core.ask import OPEN
        from kurooto.core.notify import Message

        items, settled = [], []
        for rec in self.held():
            if rec.get("map_kind") == "ask":  # a question answered meanwhile (/q, a call) or expired: not again
                q = self.app.ask.get(rec.get("map_ref") or "")
                if not q or q.get("status") not in OPEN:
                    settled.append(rec["id"])
                    continue
            try:
                body = json.loads(rec.get("msg") or "{}")
                items.append((rec, Message(**{k: v for k, v in body.items() if k in Message.__dataclass_fields__})))
            except (ValueError, TypeError):
                items.append((rec, Message(rec.get("text") or "", kind=rec.get("kind") or "info")))
        if settled:
            with self._db() as db:
                db.executemany("update sent set state='settled', msg=null where id=?", [(x,) for x in settled])
        if not items:
            return 0
        exams = any(rec.get("held") == "exams" for rec, _ in items)
        lim = self.day_limit()
        held: dict[str, int] = {}
        for rec, _ in items:
            held[rec.get("held") or ""] = held.get(rec.get("held") or "", 0) + 1
        why = {k: BUNDLED.get(k, "over the limit").format(lim=lim) for k in held}
        head = f"This evening's bundle: {len(items)} message{'s' if len(items) != 1 else ''} that waited"
        if len(held) == 1:
            head += f", {why[next(iter(held))]}"
        else:
            head += " (" + "; ".join(f"{n} {why[k]}" for k, n in held.items()) + ")"
        head += ". /calm changes the limit."
        parts: list[tuple[list[str], list, list]] = [([head], [], [])]
        for i, (_rec, m) in enumerate(items, 1):
            body = f"{m.title}: {m.text}" if m.title else m.text
            line = f"{i}. {body}"
            if len(line) > 1200:
                line = line[:1200] + "…"
            lines, rows, maps = parts[-1]
            if sum(len(x) + 2 for x in lines) + len(line) > BUNDLE_CHARS:
                parts.append(([], [], []))
                lines, rows, maps = parts[-1]
            lines.append(line)
            for row in m.buttons or []:
                rows.append([(f"{i}: {b[0]}"[:60], b[1]) for b in row if isinstance(b, (list, tuple)) and len(b) == 2])
            if m.map_kind:
                maps.append((m.map_kind, m.map_ref))
        for lines, rows, maps in parts:
            one = maps[0] if len(maps) == 1 else (None, None)
            self.app.notify(
                "\n\n".join(lines),
                kind="info",
                why="calm.bundle",
                buttons=rows[:40] or None,
                map_kind=one[0],
                map_ref=one[1],
            )
        app_ch = self.app.notifier.channels.get("app")
        kinds = self.app.settings.get("notify.app_kinds") or []
        for _, m in items:
            if m.file:
                self.app.notify(m.text, kind=m.kind, file=m.file, why="calm.bundle")
            if app_ch is not None and m.kind in kinds:
                try:
                    app_ch(m)
                except Exception as e:
                    self.app.events.emit("notify_failed", channel="app", error=str(e)[:200])
        with self._db() as db:
            db.executemany("update sent set state='bundled', msg=null where id=?", [(rec["id"],) for rec, _ in items])
        self.app.events.emit("calm_bundle", items=len(items), exams=exams)
        return len(items)

    def prune(self) -> None:
        cutoff = (now() - dt.timedelta(days=KEEP_DAYS)).timestamp()
        with self._db() as db:
            db.execute("delete from sent where ts<? and state!='held'", (cutoff,))
        undo = jload(self.undo_file, {}) or {}
        keep = {k: v for k, v in undo.items() if float(v.get("at") or 0) >= cutoff}
        if len(keep) != len(undo):
            jsave(self.undo_file, keep)

    def forget(self, lo: float, hi: float) -> int:
        """(retention) The words of messages recorded in [lo, hi) go; when, why and whether you answered stay for
        their 45 days. A message still waiting for the evening keeps its words until then. How many."""
        with self._db() as db:
            return db.execute(
                "update sent set text='', title='' where ts>=? and ts<? and state!='held' "
                "and (coalesce(text,'')!='' or coalesce(title,'')!='')",
                (lo, hi),
            ).rowcount

    # ------------------------------------------------------------------------------------------ Why?
    def title_of(self, feature: str) -> str:
        m = self.app.modules.get(feature)
        return m.title if m is not None else TITLES.get(feature, feature.replace("_", " ").title())

    def why_text(self, rec: dict | None) -> str:
        if rec is None:
            return f"I don't have a record of that message any more (they're kept {KEEP_DAYS} days)."
        if not rec.get("why"):
            return (
                "No reason recorded for that message: whatever sent it didn't say why (Kurooto's own features "
                "always do, so it came from an add-on or a script)."
            )
        r = self.reason(rec["why"])
        if r is None:
            return f"Its reason is {rec['why']!r} (an add-on's own; nothing more was recorded)."
        lines = [f"Why: {self.title_of(r.owner)}, {r.what}."]
        if rec.get("about"):
            lines.append(f"About: {rec['about']}.")
        key = rec.get("setting") or r.setting
        if key:
            sec = key.split(".")[0]
            where = self.title_of(sec) if sec in self.app.modules else sec.title()
            lines.append(f"Setting: {key} = {json.dumps(self.app.settings.get(key))} (Settings → {where}).")
        elif r.stop == MUTE:
            lines.append("Setting: none of its own; Less of this → Stop turns these off (notify.calm.stopped).")
        if rec.get("exempt"):
            lines.append(f"It always comes: {EXEMPT[rec['exempt']]}.")
        elif rec.get("state") == "bundled":
            lines.append(f"It waited for the evening bundle ({HELD.get(rec.get('held') or '', 'over the limit')}).")
        sent = dt.datetime.fromtimestamp(float(rec["ts"]))
        t = self.today()
        lines.append(f"Sent {sent:%a %H:%M}. Today: {t['messages']} of {t['messages_max']} messages.")
        return "\n".join(lines)

    # ------------------------------------------------------------------------------------- Less of this
    def options(self, rec: dict) -> list[tuple[str, str, Change]]:
        """(act, label, change) for each Less-of-this action this message's kind has."""
        r = self.reason(rec.get("why"))
        if r is None or r.exempt or rec.get("exempt"):
            return []
        out: list[tuple[str, str, Change]] = []
        stop = self._change(r, r.stop, rec, "stop")
        if stop is not None:
            out.append(("stop", "Stop", stop))
        fewer = self._change(r, r.fewer, rec, "fewer")
        if fewer is not None:
            out.append(("fewer", "Fewer", fewer))
        if r.later and r.id not in (self.s("evening") or []):
            later = list(self.s("evening") or [])
            said = f"they wait for the evening bundle ({self.evening_at():%H:%M})"
            out.append(("later", "Another time", Change(said, key="notify.calm.evening", value=[*later, r.id])))
        return out

    def _change(self, r: Reason, spec, rec: dict, act: str) -> Change | None:
        if spec is None:
            return None
        if spec == MUTE:
            stopped = list(self.s("stopped") or [])
            if r.id in stopped:
                return None
            return Change(f"no more {r.plural}", key="notify.calm.stopped", value=[*stopped, r.id])
        if spec == FEATURE:
            if not self.app.is_on(r.owner):
                return None
            return Change(f"turns off {self.title_of(r.owner)}", module=r.owner)
        if spec == DAILY:
            fewer = dict(self.s("fewer") or {})
            if fewer.get(r.id) == 1:
                return None
            return Change(
                "at most one a day; the rest wait for the evening", key="notify.calm.fewer", value={**fewer, r.id: 1}
            )
        try:
            return spec(self.app, rec)
        except Exception as e:
            self.app.events.emit("calm_failed", error=f"{act} {r.id}: {e}"[:200])
            return None

    def less_text(self, rec: dict) -> tuple[str, list | None]:
        r = self.reason(rec.get("why"))
        if r is None:
            return self.why_text(rec) + "\nThere's no setting to turn down for it.", None
        if r.exempt or rec.get("exempt"):
            ex = rec.get("exempt") or r.exempt
            return f"These always come ({EXEMPT.get(ex, ex)}), so there's nothing to turn down here.", None
        opts = self.options(rec)
        if not opts:
            return f"Nothing left to turn down for {r.plural}.", None
        lines = [f"Less of these: {r.plural}."] + [f"{label}: {c.said}." for _, label, c in opts]
        return "\n".join(lines), [[(label, f"calm:{rec['id']}:{act}") for act, label, _ in opts]]

    def apply(self, c: Change, why: str = "") -> tuple[bool, str, str | None]:
        """Make one change; (ok, what happened, undo id)."""
        if c.module:
            ok, said = self.app.disable(c.module)
            if not ok:
                return False, said, None
            undo = {"module": c.module}
        else:
            had, old = self._raw(c.key)
            self.app.settings.set(c.key, c.value)
            undo = {"key": c.key, "had": had, "old": old}
        uid = "u" + uuid.uuid4().hex[:8]
        store = jload(self.undo_file, {}) or {}
        store[uid] = {**undo, "said": c.said, "why": why, "at": now().timestamp()}
        jsave(self.undo_file, dict(list(store.items())[-200:]))
        self.app.events.emit("calm_less", why=why, key=c.key or c.module)
        return True, c.said, uid

    def _raw(self, key: str) -> tuple[bool, Any]:
        """Your own value for a setting (not the default), and whether there is one."""
        cur: Any = self.app.settings.user()
        for k in key.split("."):
            if not isinstance(cur, dict) or k not in cur:
                return False, None
            cur = cur[k]
        return True, cur

    def undo(self, uid: str) -> str:
        store = jload(self.undo_file, {}) or {}
        u = store.pop(uid, None)
        if u is None:
            return "That can't be undone any more."
        if u.get("module"):
            ok, said = self.app.enable(u["module"])
            if not ok:
                return f"Couldn't turn it back on: {said}"
        elif u.get("had"):
            self.app.settings.set(u["key"], u.get("old"))
        else:
            self.app.settings.reset(u["key"])
        jsave(self.undo_file, store)
        self.app.events.emit("calm_undo", why=u.get("why", ""))
        return f'Undone: back to how it was before "{u.get("said", "that change")}".'

    # ---------------------------------------------------------------------------------------- buttons
    def button(self, ref: str, act: str) -> str:
        """calm:<record>:why|less|stop|fewer|later, calm:<undo>:undo, calm:<reason>:apply|no|unstop."""
        if act == "undo":
            text = self.undo(ref)
            self._say(text, None)
            return text[:190]
        if act in ("apply", "no", "unstop"):
            return self._by_reason(ref, act)
        if act in ("flow", "raise", "fine"):
            return self._limit_button(ref, act)
        rec = self.get(ref)
        if rec is None:
            return self.why_text(None)[:190]
        if act == "why":
            _, buttons = self.less_text(rec)
            self._say(self.why_text(rec), [[("Less of this", f"calm:{ref}:less")]] if buttons else None, rec)
            return "Why it came: below."
        if act == "less":
            text, buttons = self.less_text(rec)
            self._say(text, buttons, rec)
            return "Pick one below." if buttons else text[:190]
        opt = next((c for a, _, c in self.options(rec) if a == act), None)
        if opt is None:
            return "That's already done, or not possible any more."
        ok, said, uid = self.apply(opt, rec.get("why") or "")
        if not ok:
            return said[:190]
        self._say(f"Done: {said}.", [[("Undo", f"calm:{uid}:undo")]], rec)
        return f"Done: {said}."[:190]

    def _limit_button(self, day: str, act: str) -> str:
        """The buttons under the line that says the day's limit was reached."""
        if act == "fine":
            return f"OK, they come at {self.evening_at():%H:%M}."
        if act == "flow":
            if day != now().date().isoformat():
                return "That was about an earlier day; today's limit holds as usual."
            with self._lock:
                st = jload(self.state_file, {}) or {}
                st["flow_day"] = day
                jsave(self.state_file, st)
            self.app.events.emit("calm_flow", day=day)
            n = self.release()
            said = f"Today they come as they happen{f'; the {n} that waited are below' if n else ''}."
            return said[:190]
        n = self.limit("messages", 6)
        if n <= 0:
            return "There's no limit to raise: /calm 6 sets one."
        c = Change(f"up to {n * 2} messages a day by themselves (was {n})", key="notify.calm.messages", value=n * 2)
        ok, said, uid = self.apply(c, "calm.limit")
        if not ok:
            return said[:190]
        out = self.release(cap=self.day_limit()) if day == now().date().isoformat() else 0
        more = f" {out} that waited come now." if out else ""
        self._say(f"Done: {said}.{more}", [[("Undo", f"calm:{uid}:undo")]])
        return f"Done: {said}."[:190]

    def _say(self, text: str, buttons, rec: dict | None = None) -> None:
        ref = rec.get("ref") if rec else None
        reply = int(ref) if ref and str(ref).isdigit() else None
        self.app.notify(text, kind="info", why=ASKED, buttons=buttons, reply_to=reply)

    def _by_reason(self, why: str, act: str) -> str:
        r = self.reason(why)
        if r is None:
            return "That kind of message isn't known any more."
        if act == "unstop":
            stopped = [x for x in (self.s("stopped") or []) if x != why]
            self.app.settings.set("notify.calm.stopped", stopped)
            return f"{r.plural[:1].upper()}{r.plural[1:]} come again."[:190]
        st = jload(self.state_file, {}) or {}
        if act == "no":
            st.setdefault("declined", {})[why] = now().timestamp()
            jsave(self.state_file, st)
            self.app.events.emit("calm_suggestion", why=why, answer="no")
            return "OK, they stay."
        rec = self._latest(why)
        stop = self._change(r, r.stop, rec or {"why": why, "setting": r.setting}, "stop")
        if stop is None:
            return "That's already off."
        ok, said, uid = self.apply(stop, why)
        self.app.events.emit("calm_suggestion", why=why, answer="apply")
        if not ok:
            return said[:190]
        self._say(f"Done: {said}.", [[("Undo", f"calm:{uid}:undo")]])
        return f"Done: {said}."[:190]

    def _latest(self, why: str) -> dict | None:
        with self._db() as db:
            row = db.execute("select * from sent where why=? order by ts desc, rowid desc limit 1", (why,)).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------------------- the monthly look
    def answer_rates(self, days: int = 30) -> list[dict]:
        """Per kind of question you're meant to answer: how many came in `days` days, and how many you answered."""
        since = (now() - dt.timedelta(days=days)).timestamp()
        with self._db() as db:
            rows = db.execute(
                "select why, count(*), sum(answered is not null), min(ts) from sent where ts>=? and "
                "state in ('sent','bundled') and (buttons!='[]' or map_kind!='') and why!='' group by why",
                (since,),
            ).fetchall()
        return [{"why": w, "n": int(n), "answered": int(a or 0), "first": float(f)} for w, n, a, f in rows]

    def monthly(self) -> str | None:
        """Once a month: the kind of question you answered least (8 or more, a fifth or fewer answered), and
        whether to turn it off. Returns the reason id it asked about."""
        if not self.on() or not self.s("monthly", True):
            return None
        t = now().timestamp()
        st = jload(self.state_file, {}) or {}
        if t - float(st.get("suggested_at") or 0) < SUGGEST_EVERY_DAYS * 86400:
            return None
        with self._db() as db:
            first = db.execute("select min(ts) from sent").fetchone()[0]
        if first is None or t - float(first) < (SUGGEST_EVERY_DAYS - 2) * 86400:
            return None  # a month of records first
        declined = st.get("declined") or {}
        best = None
        for row in self.answer_rates():
            r = self.reason(row["why"])
            if r is None or not r.suggest or row["n"] < SUGGEST_MIN or row["answered"] > SUGGEST_RATIO * row["n"]:
                continue
            if t - float(declined.get(row["why"]) or 0) < SUGGEST_AGAIN_DAYS * 86400:
                continue
            rec = self._latest(row["why"]) or {"why": row["why"], "setting": r.setting}
            stop = self._change(r, r.stop, rec, "stop")
            if stop is None:
                continue
            key = (row["answered"] / row["n"], -row["n"])
            if best is None or key < best[0]:
                best = (key, row, r, stop)
        if best is None:
            return None
        _, row, r, stop = best
        st["suggested_at"] = t
        jsave(self.state_file, st)
        self.app.notify(
            f"In the last 30 days you answered {row['answered']} of {row['n']} {r.plural}. Turn them off? "
            f"({stop.said[:1].upper()}{stop.said[1:]}; Undo puts it back.)",
            kind="question",
            title="Calm",
            why="calm.monthly",
            about=r.plural,
            buttons=[[("Apply", f"calm:{r.id}:apply"), ("No", f"calm:{r.id}:no")]],
        )
        self.app.events.emit("calm_suggestion", why=r.id, answer="asked")
        return r.id

    def sent_by(self, since: float) -> dict[str, int]:
        """Per feature, the messages and calls that came by themselves since then (not your own reminders)."""
        with self._db() as db:
            rows = db.execute(
                "select feature, count(*) from sent where ts>=? and state in ('sent','bundled','rang') and why!='' "
                "and coalesce(exempt,'')!='own' group by feature",
                (since,),
            ).fetchall()
        return {f: int(n) for f, n in rows}

    # ---------------------------------------------------------------------------------------- /calm, /why
    def command(self, arg: str = "") -> tuple[str, list | None]:
        """/calm: today's numbers and what's turned down; /calm on|off, /calm 8, /calm calls 2, /calm evening 21:00."""
        a = arg.strip().lower().split()
        if a == ["off"]:
            self.app.settings.set("notify.calm.on", False)
            return "Calm is off: everything comes as it happens, with no Why? buttons. /calm on brings it back.", None
        if a == ["on"]:
            self.app.settings.set("notify.calm.on", True)
        elif len(a) == 1 and a[0].isdigit():
            self.app.settings.set("notify.calm.messages", int(a[0]))
        elif len(a) == 2 and a[0] == "calls" and a[1].isdigit():
            self.app.settings.set("notify.calm.calls", int(a[1]))
        elif len(a) == 2 and a[0] == "evening":
            try:
                at = dt.time.fromisoformat(a[1].zfill(5))
            except ValueError:
                return "Which time? /calm evening 21:00", None
            self.app.settings.set("notify.calm.evening_at", f"{at:%H:%M}")
        elif a:
            return "/calm, /calm on, /calm off, /calm 8 (messages a day), /calm calls 2, /calm evening 21:00", None
        if not self.on():
            return "Calm is off: everything comes as it happens. /calm on turns it on.", None
        t = self.today()
        of = "messages (the limit is off today)" if t["flowing"] else f"of {t['messages_max']} messages"
        held = f", {t['waiting_limit']} of them held by the daily limit" if t["waiting_limit"] else ""
        lines = [
            f"Today: {t['messages']} {of} and {t['calls']} of {t['calls_max']} calls that came by themselves; "
            f"{t['waiting']} waiting for the evening bundle ({t['evening_at']}){held}.",
            "Always come: the alarm, approvals, your own reminders, deadlines under 12 hours, anything urgent. "
            "Update notices aren't counted.",
        ]
        if self.exam_keep() is not None:
            lines.append("Exam season: during the day only deadlines, quizzes and the alarm come.")
        buttons = []
        for label, key in (("Stopped", "stopped"), ("Evening only", "evening")):
            names = [self.reason(x).plural if self.reason(x) else x for x in self.s(key) or []]
            if names:
                lines.append(f"{label}: {', '.join(names)}.")
        fewer = self.s("fewer") or {}
        if fewer:
            names = [self.reason(x).plural if self.reason(x) else x for x in fewer]
            lines.append(f"One a day: {', '.join(names)}.")
        name = lambda x: self.reason(x).plural if self.reason(x) else x  # noqa: E731
        habit = self.s("habituate") or {}
        if habit:
            bits = [f"{name(x)} after {n} unanswered in a row" for x, n in habit.items()]
            lines.append(f"Evening once you stop answering: {', '.join(bits)}.")
        windows = self.s("windows") or {}
        if windows:
            lines.append("Only at some hours: " + ", ".join(f"{name(x)} ({w})" for x, w in windows.items()) + ".")
        for x in (self.s("stopped") or [])[:5]:
            r = self.reason(x)
            buttons.append([(f"Start {r.plural if r else x} again"[:60], f"calm:{x}:unstop")])
        lines.append("/why: why the last one came. /calm 8, /calm calls 2, /calm evening 21:00, /calm off.")
        return "\n".join(lines), buttons or None

    def last(self) -> dict | None:
        with self._db() as db:
            row = db.execute(
                "select * from sent where kind!='ring' and state in ('sent','bundled') and why!='calm.bundle' "
                "order by ts desc, rowid desc limit 1"
            ).fetchone()
        return dict(row) if row else None

    def why_last(self) -> tuple[str, list | None]:
        """/why: the last message that came by itself."""
        if not self.on():
            return "Calm is off, so nothing is recorded. /calm on turns it on.", None
        rec = self.last()
        if rec is None:
            return "Nothing has come by itself yet.", None
        _, buttons = self.less_text(rec)
        head = f'The last one ({dt.datetime.fromtimestamp(float(rec["ts"])):%a %H:%M}): "{rec["text"][:80]}"\n'
        return head + self.why_text(rec), [[("Less of this", f"calm:{rec['id']}:less")]] if buttons else None


HELD = {
    "budget": "the day's limit was reached",
    "quiet": "you asked for a quiet week",
    "fewer": "you asked for fewer of these",
    "evening": "you asked for these in the evening",
    "exams": "exam season",
    "calls": "the day's call was used",
    "habit": "you hadn't answered the last few of these",
    "window": "it came outside the hours set for these",
}
BUNDLED = {  # the bundle's first line: why they waited
    "budget": "held by the daily limit of {lim}",
    "fewer": "because you asked for fewer of these",
    "evening": "because you asked for these in the evening",
    "exams": "because of exam season (during the day only deadlines, quizzes and the alarm come)",
    "calls": "because the day's call was used",
    "habit": "because you hadn't answered the last few of these",
    "window": "because they came outside the hours set for them",
    "quiet": "because of your quiet week",
}
