"""Remember: tell Kurooto how you like to be helped ("remember that I hate calls before 8") and it keeps it.

What you tell it goes into your notes, in about-me/how-to-help-me.md (or where your notes layout keeps it), which you
can read and edit like any note: your edits win, and Kurooto never rewords or removes a line (except taking out one
it added itself, when you tap that line's Undo). A short version of that note goes along with every AI request
Kurooto makes, next to the "In brief" part of your profile. The nightly look back adds lines there too, but only the
ones you approve, or, with Learns from its own work on, facts you stated (keep(), under PICKED, each with an Undo).

It won't keep health, money or password details: those would travel with every AI request. Reminders and your own
notes are the place for them.

Rechecking (remember.recheck_days, 90): a line Kurooto wrote in its own sections (TOLD, PICKED, LEARNED; lines you
wrote anywhere else are never touched) that hasn't come up in that many days (not in what you asked or said on a
call, not said again, not kept with Keep; an edited line counts as new) gets a quiet "Still true?" with Keep, Change
and Forget, at most two a week. Forget takes the line out, Change asks for the new wording by reply; each has an
Undo. What's tracked: per line (by a hash of its words), when it last came up, in state/remember/recheck.json.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import time
import uuid
from typing import TYPE_CHECKING

from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg

if TYPE_CHECKING:
    from pathlib import Path

    from kurooto.app import App

register_defaults(
    "remember",
    {
        "recheck_days": 90,  # a kept line that hasn't come up in this many days gets one "Still true?" (0: never)
        "offer_settings": True,  # a line with a time rule ("no calls before 8") offers the matching setting (a tap)
    },
)

HOUR = r"(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?\s*(?P<ap>[ap]\.?m\.?)?"
NO_CALLS = re.compile(  # "I hate calls before 8", "don't call me before 9am", "no calls after 10 pm"
    r"\b(?:(?:hate|no|don'?t want|dislike|never)\s+(?:any\s+)?(?:phone\s+)?calls?"
    r"|(?:don'?t|do not|never)\s+(?:ever\s+)?(?:call|ring|wake)\s+me)\s+(?P<side>before|after|past)\s+" + HOUR,
    re.I,
)
UP_HOURS = re.compile(  # "I'm usually up from 8 to 23", "I work best between 9 and 6pm", "I study from 10am to 10pm"
    r"\bi(?:'m| am)?\s+(?:usually\s+|mostly\s+|normally\s+)?(?:up|awake|free|around|work(?:ing)?(?: best)?|"
    r"stud(?:y|ying)(?: best)?)\s+(?:from|between)\s+(?P<a>\d{1,2}(?:[:.]\d{2})?\s*(?:[ap]\.?m\.?)?)\s+"
    r"(?:to|and|till|until|-)\s+(?P<b>\d{1,2}(?:[:.]\d{2})?\s*(?:[ap]\.?m\.?)?)",
    re.I,
)
HELP_NOTE = "about-me/how-to-help-me.md"  # in the default notes layout; help_file() / help_rel() say where it is
TOLD = "You told me"
PICKED = "Picked up from your chats and calls"  # what Learns from its own work keeps by itself (modules/learning.py)
LEARNED = "Learned in the nightly look back"  # what you approved from the nightly look back (modules/retro.py)
MANAGED = (TOLD, PICKED, LEARNED)  # the sections Kurooto writes in; only their dated lines are ever rechecked
RECHECK_WHEN = "daily 18:30"
RECHECK_WEEK = 2  # at most this many "Still true?" in 7 days...
RECHECK_GAP_DAYS = 3  # ...this many days apart
KEPT_LINE = re.compile(  # "- fact (2026-10-23)", or with where it came from: "- fact (from a call, 2026-10-23)"
    r"^- (?P<fact>\S.*?) \((?:(?P<src>from [^()]{1,40}?), )?(?P<date>\d{4}-\d{2}-\d{2})\)\s*$"
)
COMMON = set(
    "that this with when what have like from they them than then always never really just want would should "
    "about into your mine some more most much very please".split()
)
YES = {"yes", "y", "keep", "still true", "true", "yep", "it is", "still is"}
NO = {"no", "n", "forget", "forget it", "not any more", "not anymore", "nope", "remove"}
INTRO = (
    "# How to help me\n\n"
    "What {name} has learned about how you like to be helped. Edit it freely: what you write here wins, and {name} "
    "reads it before every AI request. It never rewords or removes a line.\n"
)
MAX_FACT = 300
REMEMBER = re.compile(r"^\s*(?:please\s+)?(?:remember|keep in mind)(?:\s+that\b|\s*:)\s*(?P<fact>.+?)\s*$", re.I)
SENSITIVE = {
    "health": re.compile(
        r"\b(?:health|medic(?:al|ine|ation)s?|meds|diagnos\w*|illness|disease|disorder|symptoms?|therap(?:y|ist)|"
        r"doctor|hospital|prescri\w+|pregnan\w*|allerg\w*|depress\w*|anxiety|adhd|insulin|blood (?:pressure|sugar)|"
        r"mental health|surgery|pills?)\b",
        re.I,
    ),
    "money": re.compile(
        r"\b(?:bank|salary|income|loans?|debts?|credit cards?|debit cards?|card number|account number|iban|"
        r"invest\w*|stocks|crypto|tax(?:es)?|rent|savings|net worth|money)\b|[$€£₹¥]\s*\d",
        re.I,
    ),
    "credentials": re.compile(
        r"\b(?:passwords?|passcodes?|passphrase|pin (?:code|number)|otp|api[ -]?keys?|tokens?|secrets?|log-?ins?|"
        r"usernames?|recovery (?:code|phrase)|seed phrase|social security|passport (?:number|no)|id number)\b",
        re.I,
    ),
}
REFUSE = (
    "I'd rather not keep that: {what} details would go along with every AI request. Your own notes (or a reminder) "
    "are a better place for it."
)
WHAT = {"health": "health", "money": "money", "credentials": "password and login"}


def sensitive(text: str) -> str | None:
    """Which kind of detail Kurooto won't keep ("health", "money", "credentials"), or None."""
    return next((k for k, rx in SENSITIVE.items() if rx.search(text or "")), None)


def help_file(app: App) -> Path:
    return layout.path(app, "how_to_help")


def help_rel(app: App) -> str:
    """The note's place in your notes, for messages ("about-me/how-to-help-me.md")."""
    return layout.rel(app, "how_to_help")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"\((?:from [^()]*?, )?\d{4}-\d{2}-\d{2}[^)]*\)", "", s.lower())).strip()


def has_line(text: str, line: str) -> bool:
    """Is this (or the same words) already a line of the note?"""
    want = _norm(line)
    return bool(want) and any(_norm(ln.lstrip("-* ")) == want for ln in text.splitlines())


def add_line(app: App, section: str, line: str) -> bool:
    """Add "- line" at the end of the note's "## section" (made if missing). False if it's there already. Nothing
    else in the note changes."""
    from kurooto.core.tools import add_to_section

    f = help_file(app)
    head = layout.frontmatter(app, "how_to_help", f, title="How to help me", bare=True)
    text = f.read_text(encoding="utf-8", errors="replace") if f.exists() else head + INTRO.format(name=app.name)
    if has_line(text, line):
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(add_to_section(text, section, f"- {line}"), encoding="utf-8")
    return True


def remove_line(app: App, line: str) -> bool:
    """Take out one line Kurooto added ("- line", exactly as it was written), for an Undo. False if it isn't there
    as written any more (you changed or removed it): then nothing changes."""
    f = help_file(app)
    try:
        text = f.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    lines = text.split("\n")
    want = f"- {line}".rstrip()
    hit = next((i for i, ln in enumerate(lines) if ln.rstrip() == want), None)
    if hit is None:
        return False
    from kurooto.core.tools import write_note_file

    write_note_file(f, "\n".join(lines[:hit] + lines[hit + 1 :]))
    return True


def _swap(app: App, line: str, new: str) -> bool:
    """Put "- new" where "- line" is (exactly as it was written). False if it isn't there as written any more."""
    f = help_file(app)
    try:
        text = f.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    lines = text.split("\n")
    hit = next((i for i, ln in enumerate(lines) if ln.rstrip() == f"- {line}".rstrip()), None)
    if hit is None:
        return False
    from kurooto.core.tools import write_note_file

    lines[hit] = f"- {new}"
    write_note_file(f, "\n".join(lines))
    return True


def keep(app: App, fact: str, via: str = "telegram", section: str = TOLD) -> tuple[str, str]:
    """Keep one fact by Remember's rules: one short line, never health, money or password details, never twice. It
    goes at the end of "## section" with today's date. (status, detail): "kept" and the line as written; "refused"
    and which kind of detail; "known"; "empty"; "long"."""
    fact = re.sub(r"\s+", " ", str(fact or "")).strip().rstrip(".")
    if not fact:
        return "empty", ""
    if len(fact) > MAX_FACT:
        return "long", ""
    kind = sensitive(fact)
    if kind:
        app.events.emit("remember_refused", what=kind, via=via)
        return "refused", kind
    fact = fact[0].upper() + fact[1:]
    line = f"{fact} ({now():%Y-%m-%d})"
    if not add_line(app, section, line):
        touch(app, fact_key(fact))  # said again: it came up (rechecking)
        return "known", ""
    app.events.emit("remembered", chars=len(fact), via=via)
    return "kept", line


def _hhmm(text: str, evening: bool = False) -> str | None:
    """ "8", "8am", "10 pm", "22:30" -> "HH:MM"; a bare hour under 12 is taken in the evening when `evening`."""
    m = re.fullmatch(r"\s*" + HOUR + r"\s*", text or "", re.I)
    if not m:
        return None
    h, mi, ap = int(m["h"]), int(m["m"] or 0), (m["ap"] or "").lower()[:1]
    if ap == "p" and h < 12:
        h += 12
    elif ap == "a" and h == 12:
        h = 0
    elif not ap and evening and h < 12:
        h += 12
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None


def time_rules(app: App, fact: str) -> list[dict]:
    """The settings a kept line's time rule maps to ({key, value, said}); none when it has none, or it's what they
    are already. Only offered, never set without a tap (remember.offer_settings)."""
    out = []
    m = NO_CALLS.search(fact or "")
    night = app.settings.get("availability.night") or {}
    if m:
        side = m["side"].lower()
        at = _hhmm(m[0][m.start("h") - m.start() :], evening=side != "before")
        if at and side == "before" and night.get("to") != at:
            out.append({"key": "availability.night.to", "value": at, "said": f"no calls before {at} (night hours end)"})
        elif at and side in ("after", "past") and night.get("from") != at:
            out.append({"key": "availability.night.from", "value": at, "said": f"no calls after {at} (night hours)"})
    w = UP_HOURS.search(fact or "")
    if w:
        a, b = _hhmm(w["a"]), _hhmm(w["b"])
        if a and b and b <= a:
            b = _hhmm(w["b"], evening=True)
        if a and b and a < b and app.settings.get("startby.window") != f"{a}-{b}":
            out.append({"key": "startby.window", "value": f"{a}-{b}", "said": f"plan work between {a} and {b}"})
    return out


def help_brief(app: App, limit: int = 1500) -> str:
    """The note without its title and the standard intro, for the AI's context; cut at `limit` characters."""
    try:
        text = help_file(app).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = text.replace(INTRO.format(name=app.name), "")
    lines = [ln.rstrip() for ln in text.splitlines() if not re.match(r"^#\s", ln)]
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if not re.search(r"^\s*[-*]\s+\S|^[^#\s]", body, re.M):  # only headings left: nothing to tell
        return ""
    if len(body) > limit:
        body = body[:limit].rsplit("\n", 1)[0] + f"\n(…the rest is in {help_rel(app)})"
    return body


# ------------------------------------------------------------------------------------------- rechecking
def fact_key(fact: str) -> str:
    """A line's stable key: a hash of its words without the date, so an edited line is a new one."""
    return hashlib.sha256(_norm(fact).encode()).hexdigest()[:12]


def kept_lines(app: App) -> list[dict]:
    """The dated lines Kurooto wrote under its own sections (MANAGED): {key, fact, line, section, date}. Lines you
    wrote anywhere else, or without a date, are left out."""
    try:
        text = help_file(app).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out, section = [], ""
    for ln in text.splitlines():
        if re.match(r"^#{1,2}\s", ln):
            section = ln[3:].strip() if ln.startswith("## ") else ""
            continue
        m = KEPT_LINE.match(ln.rstrip())
        if m and section in MANAGED:
            line = ln.rstrip()[2:]
            out.append(
                {"key": fact_key(m["fact"]), "fact": m["fact"], "line": line, "section": section, "date": m["date"]}
            )
    return out


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{4,}", str(s or "").lower()) if w not in COMMON}


def came_up(fact: str, text: str) -> bool:
    """Does this text bring the fact up? Most of its words (at least two, or its only one) are there."""
    want = _words(fact)
    hit = len(want & _words(text))
    return bool(want) and hit >= min(len(want), max(2, (len(want) + 1) // 2))


def recheck_file(app: App):
    return app.paths.state / "remember" / "recheck.json"


def touch(app: App, key: str, how: str = "used") -> None:
    """A fact came up (said again, in a request, or kept with Keep): its days start again."""
    with Lock(app.paths.state, "remember"):
        st = jload(recheck_file(app), {}) or {}
        st.setdefault("facts", {}).setdefault(key, {})[how] = time.time()
        jsave(recheck_file(app), st)


def _last(rec: dict) -> float:
    return max(float(rec.get(k) or 0) for k in ("seen", "used", "kept", "asked"))


class Remember(Module):
    id = "remember"
    title = "Remember"
    description = (
        'Tell it how you like to be helped ("remember that I hate calls before 8"); it keeps that in your notes '
        "and every AI request follows it."
    )
    requires = ("telegram",)
    privacy = (
        "Kept in your notes (about-me/how-to-help-me.md); a short version goes along with each request to the AI you "
        "picked. Health, money and password details are refused."
    )

    def start(self):
        self.every("recheck", RECHECK_WHEN, lambda p: self.recheck())

    def remember(self, fact: str, via: str = "telegram") -> str:
        status, detail = keep(self.app, fact, via)
        if status == "empty":
            return "What should I remember? e.g. /remember I hate calls before 8"
        if status == "long":
            return f"That's long for one line (keep it under {MAX_FACT} characters); your notes suit longer things."
        if status == "refused":
            return REFUSE.format(what=WHAT[detail])
        if status == "known":
            return "I know that already."
        self._offer_settings(fact)
        return f"Noted in {help_rel(self.app)}: {detail.rsplit(' (', 1)[0]}."

    # ----------------------------------------------------------------------- time rules -> settings (0.9.0)
    def _offer_settings(self, fact: str) -> None:
        """remember.offer_settings: a time rule in what you asked it to remember ("I hate calls before 8") is offered
        as the setting that does it, with Set it / No; a tap sets it through Calm (core/calm.py), with Undo."""
        if not self.setting("offer_settings"):
            return
        try:
            rules = time_rules(self.app, fact)
        except Exception as e:
            self.app.events.emit("remember_failed", error=f"rules: {type(e).__name__}"[:60])
            return
        if not rules:
            return
        rid = uuid.uuid4().hex[:8]
        f = self.app.paths.state / "remember" / "offers.json"
        offers = jload(f, {}) or {}
        offers[rid] = rules
        jsave(f, dict(list(offers.items())[-20:]))
        said = "; ".join(r["said"] for r in rules)
        self.app.notify(
            f"Shall I set that too: {said}?",
            kind="question",
            buttons=[[("Set it", f"rms:{rid}:set"), ("No", f"rms:{rid}:no")]],
            why="asked",
        )

    def _settings_button(self, ref: str, act: str) -> str:
        f = self.app.paths.state / "remember" / "offers.json"
        offers = jload(f, {}) or {}
        rules = offers.pop(ref, None)
        if rules is None:
            return "That offer is gone."
        jsave(f, offers)
        if act != "set":
            return "Left as it is; the line is still in your note."
        from kurooto.core.calm import Change

        done = []
        for r in rules:
            ok, said, uid = self.app.calm.apply(Change(r["said"], key=r["key"], value=r["value"]), why="asked")
            if ok and uid:
                done.append(said)
                self.app.notify(f"Done: {said}.", kind="info", buttons=[[("Undo", f"calm:{uid}:undo")]], why="asked")
        return f"Set: {'; '.join(done)}." if done else "Nothing changed."

    # ---------------------------------------------------------------------------------------- rechecking
    def recheck_days(self) -> float:
        try:
            return max(0.0, float(self.setting("recheck_days") or 0))
        except (TypeError, ValueError):
            return 90.0

    def recheck(self) -> str | None:
        """The daily look: note which kept lines came up since last time, then ask about the one quiet longest, if
        one has been quiet recheck_days and fewer than RECHECK_WEEK were asked this week. The line asked, or None."""
        days = self.recheck_days()
        if not days:
            return None
        t, lines = time.time(), kept_lines(self.app)
        with Lock(self.app.paths.state, "remember"):
            st = jload(recheck_file(self.app), {}) or {}
            first, facts = "scanned" not in st, st.get("facts") or {}
            for x in lines:  # a new (or edited) line counts from now; on the very first look, from its date
                rec = facts.setdefault(x["key"], {})
                if "seen" not in rec:
                    day = dt.datetime.strptime(x["date"], "%Y-%m-%d").timestamp() if first else t
                    rec["seen"] = min(day, t)
            facts = {k: v for k, v in facts.items() if k in {x["key"] for x in lines}}
            self._came_up(lines, facts, float(st.get("scanned") or 0))
            sent = [s for s in st.get("sent", []) if t - s < 7 * 86400]
            stale = sorted(
                (x for x in lines if t - _last(facts[x["key"]]) >= days * 86400), key=lambda x: _last(facts[x["key"]])
            )
            pick = None
            if stale and len(sent) < RECHECK_WEEK and not (sent and t - max(sent) < RECHECK_GAP_DAYS * 86400):
                pick = stale[0]
                facts[pick["key"]]["asked"] = t
                sent.append(t)
            st.update(facts=facts, sent=sent, scanned=t)
            jsave(recheck_file(self.app), st)
        if pick is None:
            return None
        said = dt.datetime.strptime(pick["date"], "%Y-%m-%d")
        key = pick["key"]
        self.app.notify(
            f'Still true? "{pick["fact"]}" (in {help_rel(self.app)} since {said:%d %b %Y}; it hasn\'t come up in '
            f"{days:g} days). Reply with new wording to change it.",
            kind="info",
            buttons=[[("Keep", f"rck:{key}:keep"), ("Change", f"rck:{key}:change"), ("Forget", f"rck:{key}:forget")]],
            why="remember.recheck",
            about=pick["fact"][:80],
            map_kind="recheck",
            map_ref=key,
        )
        self.app.events.emit("remember_recheck", section=pick["section"][:40])
        return pick["line"]

    def _came_up(self, lines: list[dict], facts: dict, since: float) -> None:
        """Lines that came up in what you asked (your own requests, chats) or said on a call since `since`."""
        from kurooto.modules.learning import asked

        said: list[tuple[float, str]] = []
        while True:
            rows = self.app.jobs.finished_since(since)
            said += [(r[4], asked(r[2])[-4000:]) for r in rows if r[5] == "you" and not r[6]]
            if len(rows) < 500:
                break
            since = rows[-1][4]
        d = self.app.paths.state / "calls" / "transcripts"
        for f in sorted(d.glob("*.txt")) if d.is_dir() else []:
            try:
                when = f.stat().st_mtime
                if when > since:
                    text = f.read_text(encoding="utf-8", errors="replace")
                    said.append((when, "\n".join(ln for ln in text.splitlines() if ln.startswith("You:"))))
            except OSError:
                continue
        for x in lines:
            for when, text in said:
                if came_up(x["fact"], text):
                    rec = facts[x["key"]]
                    rec["used"] = max(float(rec.get("used") or 0), when)

    def _find(self, key: str) -> dict | None:
        return next((x for x in kept_lines(self.app) if x["key"] == key), None)

    def _undo_point(self, rec: dict) -> str:
        uid = uuid.uuid4().hex[:8]
        with Lock(self.app.paths.state, "remember"):
            st = jload(recheck_file(self.app), {}) or {}
            st["undo"] = {**dict(list((st.get("undo") or {}).items())[-19:]), uid: rec}
            jsave(recheck_file(self.app), st)
        return uid

    def _said(self, text: str, uid: str) -> None:
        self.app.notify(text, kind="info", why="asked", buttons=[[("Undo", f"rck:{uid}:undo")]])

    def _button(self, ref: str, act: str) -> str:
        """Keep, Change and Forget under a "Still true?"; Undo after Change or Forget ("rck:<key or undo>:<act>")."""
        if act == "undo":
            return self._undo(ref)
        x = self._find(ref)
        if x is None:
            return "That line isn't in your how-to-help-me note as I wrote it any more, so I left it alone."
        if act == "keep":
            touch(self.app, ref, "kept")
            self.app.events.emit("remember_rechecked", answer="keep")
            return f"Kept. I'll ask again only if it hasn't come up in {self.recheck_days():g} days."
        if act == "forget":
            return self._forget(x)
        if act == "change":
            self.app.notify(
                f'How should "{x["fact"]}" read now? Reply to this with the new wording.',
                kind="info",
                why="asked",
                map_kind="recheck",
                map_ref=ref,
            )
            return "Reply with the new wording."
        return "unknown button"

    def _forget(self, x: dict) -> str:
        if not remove_line(self.app, x["line"]):
            return "That line isn't in your how-to-help-me note as I wrote it any more, so I left it alone."
        uid = self._undo_point({"do": "forget", "line": x["line"], "section": x["section"]})
        self.app.events.emit("remember_rechecked", answer="forget")
        self._said(f"Taken out of {help_rel(self.app)}: {x['fact']}", uid)
        return "Taken out."

    def _change(self, x: dict, wording: str) -> str:
        fact = re.sub(r"\s+", " ", wording).strip().rstrip(".")
        if not fact:
            return "What should it say instead?"
        if len(fact) > MAX_FACT:
            return f"That's long for one line (keep it under {MAX_FACT} characters)."
        kind = sensitive(fact)
        if kind:
            self.app.events.emit("remember_refused", what=kind, via="recheck")
            return REFUSE.format(what=WHAT[kind])
        new = f"{fact[0].upper()}{fact[1:]} ({now():%Y-%m-%d})"
        if not _swap(self.app, x["line"], new):
            return "That line isn't in your how-to-help-me note as I wrote it any more, so I left it alone."
        uid = self._undo_point({"do": "change", "line": x["line"], "new": new})
        self.app.events.emit("remember_rechecked", answer="change")
        self._said(f"Changed in {help_rel(self.app)}: {new.rsplit(' (', 1)[0]}", uid)
        return "Changed."

    def _undo(self, uid: str) -> str:
        with Lock(self.app.paths.state, "remember"):
            st = jload(recheck_file(self.app), {}) or {}
            rec = (st.get("undo") or {}).pop(uid, None)
            jsave(recheck_file(self.app), st)
        if rec is None:
            return "That's undone already, or too old to undo."
        if rec["do"] == "forget":
            add_line(self.app, rec["section"], rec["line"])
            said = "Put back."
        elif _swap(self.app, rec["new"], rec["line"]):
            said = "Back as it was."
        else:
            return "That line changed since, so I left the note alone."
        self.app.events.emit("remember_recheck_undone", what=rec["do"])
        return said

    def _reply(self, msg: Incoming, ref: str) -> str:
        """A reply to "Still true?" (or to "How should it read now?"): yes keeps it, no forgets it, anything else is
        the new wording."""
        x = self._find(ref)
        if x is None:
            return "That line isn't in your how-to-help-me note as I wrote it any more, so I left it alone."
        text = msg.text.strip()
        low = text.lower().rstrip(".!")
        if low in YES:
            return self._button(ref, "keep")
        if low in NO:
            return self._forget(x)
        helper = getattr(self.app, "helper", None)  # "yeah, still" / "not really": the offline helper reads it
        said = helper.yes_no("Is this still true?", text) if helper is not None else None
        if said is not None:
            return self._button(ref, "keep") if said else self._forget(x)
        return self._change(x, text)

    def callbacks(self):
        return {"rck": self._button, "rms": self._settings_button}

    def replies(self):
        return {"recheck": self._reply}

    # ------------------------------------------------------------------------------------------ Telegram
    def commands(self):
        return [Command("remember", "keep how you like to be helped: /remember I hate calls before 8", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        if arg:
            return self.remember(arg, via=msg.via)
        brief = help_brief(self.app, limit=3000)
        if not brief:
            return 'Nothing yet. /remember <how you like to be helped>, or say "remember that ...".'
        return f"What I keep in mind ({help_rel(self.app)}; edit it any time):\n\n{brief}"

    def intents(self):
        def match(text: str):
            m = REMEMBER.match(text)
            return {"fact": m["fact"]} if m and not re.match(r"(?i)to\b", m["fact"]) else None

        return [
            Intent(
                "remember",
                "remember how you like to be helped",
                match,
                lambda m, s: self.remember(s["fact"]),
                examples=("remember that I hate calls before 8",),
            )
        ]

    def help(self):
        return ['"remember that …", /remember']

    # --------------------------------------------------------------------------------------------- calls
    def call_tools(self):
        return [
            Tool(
                "remember",
                "Keep a lasting preference they state about how to help them, in their words (e.g. 'no calls "
                "before 8'). Not for tasks or dates (use reminders). Health, money and passwords are refused.",
                lambda a: self.remember(str(a.get("fact", "")), via="call"),
                {"fact": arg("the preference, one short sentence")},
                ("fact",),
                offline="queue",
                hint='When they say "remember that ..." or state a lasting preference, call remember with it.',
            )
        ]
