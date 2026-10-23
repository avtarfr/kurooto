"""Nightly look back: once a day the AI reads how the day went and proposes a few small improvements, each with the
evidence behind it. You answer each one with Apply, Observe longer or No; nothing changes without your tap.

What it reads: the day's events (what you answered, moved, skipped or ignored, and how fast), your answers to
Kurooto's questions, today's call transcripts and journal, and the settings it may change. What it can propose:
    setting   a new value for one of the settings in TUNABLE (times and thresholds; features can add their own)
    profile   a line for about-me/how-to-help-me.md in your notes (paths here are the default notes layout's)
    observe   something to watch for a while before deciding anything
    skill     a change to your copy of a skill (you see the change and tap Save; the old version is kept)
    idea      something new Kurooto could do for you, added to kurooto/ideas.md in your notes
"No" drops that idea for 30 days. "Observe longer" watches it for a week first ("observe 14" for 14 days).

You can steer it: /observe whether I study better before noon for 2 weeks (or say it, or ask on a call), /observing
lists what's being watched, each with Stop and +7 days (watch a week longer) buttons. When the watching ends, the
next look back tells you what it found.
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import re
import statistics
import threading
import uuid
from collections import Counter
from importlib import resources
from pathlib import Path

from kurooto import providers
from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.remember import add_line, has_line, help_brief, help_file, help_rel, sensitive

register_defaults(
    "retro",
    {
        "when": "daily 23:50",  # "weekly sun 21:00" looks back over the whole week instead
        "max_proposals": 3,
        "observe_days": 7,  # how long "Observe longer" (and /observe without a length) watches
        "no_days": 30,  # how long a "No" keeps that idea away
        "transcripts": True,  # read today's call transcripts
        "journal": True,  # read today's journal note
    },
)
# The settings it may propose changing, with what they mean. The meaning says the type: "time HH:MM" (add "or null"
# if it can be off), "(number)", "(true/false)" or "(one of: a, b, c)". A feature adds its own with tunable(), or with
# a `tunable = {"key": "meaning"}` attribute on its module class (read while that feature is on).
TUNABLE = {
    "checkins.times.evening": "time HH:MM or null",
    "checkins.times.midday": "time HH:MM or null",
    "availability.night.from": "time HH:MM",
    "availability.night.to": "time HH:MM",
    "deadlines.ping_h": "hours before a deadline for the first nudge (number)",
    "deadlines.urgent_h": "hours before a deadline for the urgent nudge (number)",
    "quiz.per_session": "questions per quiz session (number)",
    "capture.delay_min": "minutes after class before asking (number)",
}
ALIASES = {"config": "setting", "settings": "setting", "build": "idea", "feature": "idea", "line": "profile"}
CHOICES = ["Apply", "Observe longer", "No"]
LEARNED = "Learned in the nightly look back"
IDEAS_NOTE = "kurooto/ideas.md"  # in the default notes layout; layout.path(app, "ideas") is where it is
IDEAS_INTRO = (
    "# Ideas\n\nThings {name} could do for you, from the nightly look back (you approved each one). Tick one off, "
    "delete it, or ask for it.\n\n"
)
# events worth showing one by one (the rest are only counted)
DETAIL = (
    "checkin_",
    "call_",
    "calls_held",
    "capture_",
    "deadline_",
    "study_",
    "quiz_",
    "reminder_",
    "alarm_",
    "class_skip",
    "skill_",
    "routine_",
    "observe_",
    "retro_",
    "remember",
    "focus",
    "ignore",
    "morning_",
    "weekly_review",
    "question_later",
    "question_expired",
    "intent",
    "voice_note",
)
QUIET = {"call_transcript"}  # the transcripts themselves are read below
FALLBACK_INSTRUCTIONS = """You are the learning loop of a personal assistant. From the input below, propose at most
`max_proposals` small, evidence-backed changes (types: setting, profile, observe, skill, idea), and report what you
found for each item in `observations_ended`. Reply with JSON only: {"noticed": "...", "findings": [{"id": "...",
"finding": "..."}], "proposals": [{"type": "setting", "key": "...", "value": "...", "text": "...", "evidence": "..."}]}
"""
SKILL_EDIT = """Below is a skill file: instructions an AI assistant follows. Rewrite it to make this one change, and
keep everything else exactly as it is (the header between the --- lines, the wording, the order, the style).

The change: {change}

Don't use any tools and don't edit any files. Reply with the complete new file between a line ===BEGIN=== and a line
===END===, and nothing else.

The file now:
{text}
"""
OBSERVE = re.compile(
    r"^\s*(?:please\s+)?(?:observe|keep an eye on|watch(?=\s+(?:whether|if|how)\b)|notice(?=\s+(?:whether|if)\b))\s+"
    r"(?P<what>.+?)\s*$",
    re.I,
)
LENGTH = re.compile(
    r"\s+(?:for|over)\s+(?:the\s+next\s+)?(?P<n>\d+|an?|one|two|three|four|a couple of)\s*"
    r"(?P<unit>days?|weeks?|months?)\s*$",
    re.I,
)
WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "a couple of": 2}
UNIT_DAYS = {"d": 1, "w": 7, "m": 30}


def tunable(key: str, meaning: str) -> None:
    """Let the look back propose changes to one more setting (see TUNABLE for how `meaning` gives the type)."""
    TUNABLE[key] = meaning


def valid(meaning: str, value) -> bool:
    """Is `value` the right type for a setting with this meaning?"""
    if "time HH:MM" in meaning:
        if value is None:
            return "null" in meaning
        m = re.fullmatch(r"(\d{2}):(\d{2})", value) if isinstance(value, str) else None
        return bool(m) and int(m[1]) < 24 and int(m[2]) < 60
    if "(true/false)" in meaning:
        return isinstance(value, bool)
    one_of = re.search(r"\(one of:\s*([^)]*)\)", meaning)
    if one_of:
        return value in [x.strip() for x in one_of[1].split(",")]
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value < 1000


def split_length(text: str, default: int) -> tuple[str, int]:
    """("whether I study better before noon for 2 weeks", 7) -> ("whether I study better before noon", 14)."""
    m = LENGTH.search(text)
    if not m:
        return text.strip(" .,"), default
    n = m["n"].lower()
    count = int(n) if n.isdigit() else WORDS.get(n, 1)
    return text[: m.start()].strip(" .,"), max(1, min(count * UNIT_DAYS[m["unit"][0].lower()], 365))


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9:]+", str(s or "").lower()) if len(w) > 2}


def same_idea(a: dict, b: dict) -> bool:
    """Two proposals that are the same idea, however they're worded: the same setting, or mostly the same words."""
    if a.get("type") != b.get("type"):
        return False
    if a.get("type") == "setting":
        return a.get("main") == b.get("main")
    wa, wb = _words(a.get("main", "")), _words(b.get("main", ""))
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.5


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S).strip()


def _effort(text: str) -> str:
    m = re.search(r"^effort:\s*(low|medium|high)\s*$", text.split("\n---", 1)[0], re.M)
    return m[1] if m else "medium"


class Retro(Module):
    id = "retro"
    heavy = True  # waits for the charger on battery (saver mode, core/power.py)
    title = "Nightly look back"
    description = (
        "Once a day the AI suggests small improvements from how the day went (a setting, a line for your "
        "how-to-help-me note, a skill tweak, something to watch, an idea); you approve each. /observe, /observing."
    )
    requires = ("telegram", "chat")
    privacy = (
        "Once a day the AI you picked reads what happened (events, your answers to Kurooto's questions, today's call "
        "transcripts and journal, your how-to-help-me note and the settings it may change). Transcripts and the "
        "journal can be left out in Settings."
    )

    def __init__(self, app):
        super().__init__(app)
        self.file = app.paths.state / "retro.json"  # proposals waiting for your answer
        self.state_file = app.paths.state / "retro-state.json"  # what you declined and approved, the last run
        self.obs_file = app.paths.state / "observations.json"
        self._running = threading.Lock()
        app.jobs.then_actions["retro.skill_ready"] = self._skill_ready
        ask = getattr(app, "ask", None)
        if ask is not None:  # questions (core/ask.py): the answer can come from Telegram, the phone app or a call
            ask.hooks["retro.answer"] = self._hook

    def _hook(self, q: dict, answer: str) -> str:
        return self.answer(str((q.get("hook_payload") or {}).get("pid", "")), answer)

    def start(self):
        self.every("nightly", self.setting("when") or "daily 23:50", lambda p: self.run_in_background(nightly=True))
        # a nightly look back that waited for the AI's free limit to reset (core/quota.py), over the same days
        self.action("after_reset", lambda p: self.run_in_background(since=p.get("since"), nightly=True))

    def run_in_background(self, since: str | None = None, nightly: bool = False) -> bool:
        """Start a look back unless one is running (it can take minutes; other jobs shouldn't wait for it)."""
        if self._running.locked():
            return False
        threading.Thread(target=self.run, args=(since, nightly), name="retro", daemon=True).start()
        return True

    # ------------------------------------------------------------------------------------ the look back
    def run(self, since: str | None = None, nightly: bool = False) -> int:
        """Look back, report findings on observations that ended, and ask about each proposal. Returns how many
        proposals were asked. The nightly one is background work: while the AI's free limit is kept for you, it
        waits for the reset (and then looks back over the same days)."""
        if not self._running.acquire(blocking=False):
            return 0
        try:
            return self._run(since, nightly)
        finally:
            self._running.release()

    def _run(self, start: str | None = None, nightly: bool = False) -> int:
        brain = providers.build(self.app, self.app.settings.get("brain.main") or "")
        if not brain or not brain.available()[0]:
            return 0
        days = 7 if str(self.setting("when") or "").strip().lower().startswith("weekly") else 1
        since = dt.datetime.fromisoformat(start) if start else now() - dt.timedelta(days=days)
        instructions, effort = self.instructions()
        wait = self.app.quota.wait_until(self.app.quota.pool(brain, effort)) if nightly else None
        if wait is not None:
            when = dt.datetime.fromtimestamp(wait + 60)
            self.app.scheduler.at(
                when, "retro.after_reset", {"since": since.isoformat()}, key="retro:after-reset", module=self.id
            )
            self.app.events.emit("retro_waits", until=when.isoformat(timespec="minutes"))
            return 0
        active = [o for o in self.observations() if o["status"] == "active"]
        ended = [o for o in active if o["until"] <= now().isoformat()]
        ctx = self.context(since, [o for o in active if o not in ended], ended)
        learning = self.app.modules.get("learning")  # Learns from its own work: facts you stated (modules/learning.py)
        picks = learning.picks_facts() if learning is not None else 0
        if picks:
            from kurooto.modules.learning import REMEMBER_ASK

            instructions += "\n" + REMEMBER_ASK.format(n=picks)
            ctx["chats"] = learning.chats(since)
        prompt = instructions + "\n\nINPUT (JSON):\n" + json.dumps(ctx, ensure_ascii=False, indent=1, default=str)
        r = brain.complete(prompt[:120_000], effort=effort, timeout=600)
        out = self._parse(r.text) if r.ok else None
        if out is None:
            self.app.events.emit("retro_failed", reason="no answer" if not r.ok else "unreadable")
            return 0
        if picks:
            learning.keep_facts(out.get("remember"))  # kept at once, each with an Undo (no tap needed)
        found = {str(f.get("id")): str(f.get("finding") or "").strip() for f in out.get("findings") or [] if f}
        for o in ended:
            self._finish_observation(o, found.get(o["id"], ""))
        state = self._state()
        store = jload(self.file, {}) or {}
        asked: list[dict] = []
        for raw in out.get("proposals") or []:
            if len(asked) >= int(self.setting("max_proposals") or 3):
                break
            p = self.clean(raw) if isinstance(raw, dict) else None
            if not p or self._blocked(p, state, asked):
                continue
            pid = uuid.uuid4().hex[:8]
            store[pid] = {**p, "at": now().isoformat()}
            jsave(self.file, dict(list(store.items())[-100:]))
            self._ask(pid, store[pid])
            self.app.events.emit("retro_proposed", type=p["type"])
            asked.append(p)
        state["last"] = {
            "at": now().isoformat(timespec="minutes"),
            "noticed": str(out.get("noticed") or "")[:1500],
            "proposals": len(asked),
            "findings": len(ended),
        }
        self._save_state(state)
        self.app.events.emit("retro_ran", proposals=len(asked), findings=len(ended))
        return len(asked)

    @staticmethod
    def _parse(text: str) -> dict | None:
        text = text or ""
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        candidates = [m[1]] if m else []
        if "{" in text and "}" in text:
            candidates.append(text[text.index("{") : text.rindex("}") + 1])
        for c in candidates:
            try:
                out = json.loads(c)
            except ValueError:
                continue
            if isinstance(out, dict):
                return out
        return None

    def instructions(self) -> tuple[str, str]:
        """The look back's instructions (the retro skill: your copy in kurooto/skills/retro/ wins) and its effort."""
        try:
            from kurooto.modules.skills import load_skill

            s = load_skill(self.app, "retro")
            if s and s.body.strip():
                return s.body.strip(), s.effort or "high"
        except Exception:  # the skills feature isn't there (or failed): read the files directly
            pass
        mine = layout.path(self.app, "skills") / "retro" / "SKILL.md"
        for read in (
            lambda: mine.read_text(encoding="utf-8"),
            lambda: resources.files("kurooto.data").joinpath("skills", "retro", "SKILL.md").read_text("utf-8"),
        ):
            try:
                text = read()
            except OSError:
                continue
            if _strip_frontmatter(text):
                return _strip_frontmatter(text), _effort(text)
        return FALLBACK_INSTRUCTIONS, "medium"

    # ---------------------------------------------------------------------------------------- evidence
    def context(self, since: dt.datetime, observing: list[dict], ended: list[dict]) -> dict:
        state = self._state()
        cutoff = (now() - dt.timedelta(days=int(self.setting("no_days") or 30))).isoformat()
        return {
            "evidence": self.evidence(since),
            "answers": self._answers(since),
            "call_transcripts": self._transcripts(since) if self.setting("transcripts") else "",
            "journal": self._journal(since) if self.setting("journal") else "",
            "settings": {k: {"means": v, "now": self.app.settings.get(k)} for k, v in self.tunable().items()},
            "how_to_help_me": help_brief(self.app, limit=2500),
            "skills": self.skills(),
            "observing": [{"what": o["what"], "until": o["until"][:10]} for o in observing],
            "observations_ended": [{"id": o["id"], "what": o["what"], "since": o["created"][:10]} for o in ended],
            "declined_recently": [r["text"] for r in state["rejected"] if r["date"] >= cutoff][-30:],
            "applied_recently": [a["text"] for a in state["applied"]][-15:],
            "max_proposals": int(self.setting("max_proposals") or 3),
            "today": f"{now():%A %Y-%m-%d %H:%M}",
        }

    def evidence(self, since: dt.datetime) -> str:
        """What happened since then, as short lines: counts, then the events worth showing one by one."""
        evs = [e for e in self.app.events.tail(20000) if str(e.get("ts", "")) >= since.isoformat()]
        if not evs:
            return "Nothing happened."
        counts = Counter(e["kind"] for e in evs)
        lines = [
            f"{len(evs)} events since {since:%a %d %b %H:%M}.",
            "Counts: " + ", ".join(f"{k} {n}" for k, n in counts.most_common(60)),
        ]
        ans = [e for e in evs if e["kind"] == "question_answered"]
        if ans or counts["question_asked"]:
            secs = [float(e.get("seconds") or 0) for e in ans]
            line = f"Questions: asked {counts['question_asked']}, answered {len(ans)}"
            if secs:
                vias = Counter(e.get("via") or "?" for e in ans)
                hours = Counter(e["ts"][11:13] for e in ans)
                line += f" (median reply {statistics.median(secs) / 60:.0f} min; by channel "
                line += ", ".join(f"{k} {n}" for k, n in vias.items())
                line += "; at " + ", ".join(f"{h}h {n}" for h, n in sorted(hours.items())) + ")"
            lines.append(line + f", later {counts['question_later']}, expired {counts['question_expired']}.")
        jobs = [e for e in evs if e["kind"] == "job_done"]
        if jobs:
            fails = sum(1 for e in jobs if not e.get("ok"))
            med = statistics.median(float(e.get("seconds") or 0) for e in jobs)
            titles = [j.title[:60] for j in self.app.jobs.recent(40) if j.created >= since.timestamp() and j.title]
            lines.append(
                f"AI requests: {len(jobs)} ({fails} failed), median {med:.0f} s"
                + (f"; latest: {' | '.join(titles[:10])}" if titles else "")
            )
        detail = [e for e in evs if e["kind"].startswith(DETAIL) and e["kind"] not in QUIET]
        for e in detail[-60:]:
            fields = " ".join(
                f"{k}={str(v)[:60]}" for k, v in e.items() if k not in ("ts", "kind") and v not in (None, "", [], {})
            )
            lines.append(f"{e['ts'][5:16].replace('T', ' ')} {e['kind']} {fields}".rstrip())
        return "\n".join(lines)[:20000]

    def _answers(self, since: dt.datetime) -> list[dict]:
        """Kurooto's questions since then and what you answered (core/ask.py)."""
        ask = getattr(self.app, "ask", None)
        try:
            qs = ask.recent(since) if ask is not None else []
        except Exception:
            return []
        return [
            {
                "from": q.get("source") or "",
                "question": str(q.get("text") or "")[:160],
                "answer": str(q.get("answer") or "")[:240] if q.get("status") != "expired" else "(no answer)",
                "via": q.get("via") or "",
                "when": str(q.get("answered") or q.get("expired_at") or "")[11:16],
            }
            for q in qs[-25:]
        ]

    def _transcripts(self, since: dt.datetime, budget: int = 8000) -> str:
        d = self.app.paths.state / "calls" / "transcripts"
        parts = []
        for f in sorted(d.glob("*.txt")) if d.is_dir() else []:
            try:
                when = dt.datetime.strptime(f.stem, "%Y-%m-%d-%H%M%S")
            except ValueError:
                continue
            if when >= since:
                text = f.read_text(encoding="utf-8", errors="replace").strip()
                parts.append(f"--- call at {when:%a %H:%M} ---\n{text[:3000]}")
        return "\n".join(parts)[-budget:]

    def _journal(self, since: dt.datetime, budget: int = 6000) -> str:
        parts, day = [], since.date()
        while day <= now().date():
            f = layout.path(self.app, "daily", date=day.isoformat())
            if f.is_file():
                parts.append(f"--- {day:%a %d %b} ---\n{f.read_text(encoding='utf-8', errors='replace')[:3000]}")
            day += dt.timedelta(days=1)
        return "\n".join(parts)[-budget:]

    def tunable(self) -> dict:
        out = dict(TUNABLE)
        for m in self.app.enabled():
            extra = getattr(m, "tunable", None)
            if isinstance(extra, dict):
                out.update({str(k): str(v) for k, v in extra.items()})
        return out

    def skills(self) -> dict:
        """The skills it may propose changing: name -> what it's for."""
        out = {}
        if self.app.is_on("skills"):
            try:
                from kurooto.modules.skills import all_skills

                for name, s in all_skills(self.app).items():
                    if not getattr(s, "internal", False):
                        out[name] = str(getattr(s, "description", ""))[:160]
            except Exception:
                pass
        out.setdefault("retro", "this look back's own instructions")
        return dict(list(out.items())[:60])

    # --------------------------------------------------------------------------------------- proposals
    def clean(self, p: dict) -> dict | None:
        """A proposal from the AI, checked and tidied, or None if it can't be offered."""
        kind = str(p.get("type") or ("setting" if p.get("key") else "")).strip().lower()
        kind = ALIASES.get(kind, kind)
        text = re.sub(r"\s+", " ", str(p.get("text") or "")).strip()[:300]
        evidence = re.sub(r"\s+", " ", str(p.get("evidence") or p.get("why") or "")).strip()[:400]
        if kind == "setting":
            key, value = str(p.get("key") or p.get("path") or ""), p.get("value")
            tun = self.tunable()
            if key not in tun or not valid(tun[key], value):
                return None
            current = self.app.settings.get(key)
            if value == current:
                return None
            out = {"key": key, "value": value, "main": key}
            text = text or f"Set {key} to {json.dumps(value)} (now {json.dumps(current)})?"
        elif kind == "profile":
            line = re.sub(r"\s+", " ", str(p.get("line") or "")).strip().lstrip("-* ").rstrip()[:300]
            f = help_file(self.app)
            have = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""
            if not line or sensitive(line) or has_line(have, line):
                return None
            out = {"line": line, "main": line}
            text = text or "Add this to your how-to-help-me note?"
        elif kind == "observe":
            what = re.sub(r"\s+", " ", str(p.get("observe") or p.get("what") or "")).strip()[:300]
            try:
                days = max(1, min(int(p.get("days") or self.setting("observe_days") or 7), 60))
            except (TypeError, ValueError):
                days = int(self.setting("observe_days") or 7)
            if not what:
                return None
            out = {"observe": what, "days": days, "main": what}
            text = text or f"Watch {what} for {days} days?"
        elif kind == "skill":
            name = re.sub(r"[^a-z0-9-]", "", str(p.get("skill") or "").lower())
            change = re.sub(r"\s+", " ", str(p.get("change") or "")).strip()[:1500]
            if not name or not change or name not in self.skills() or self._skill_text(name) is None:
                return None
            out = {"skill": name, "change": change, "main": f"{name} {change}"}
            text = text or f"Change your {name} skill?"
        elif kind == "idea":
            idea = re.sub(r"\s+", " ", str(p.get("idea") or p.get("text") or "")).strip()[:400]
            if not idea:
                return None
            out = {"idea": idea, "main": idea}
            text = text or "Add this to your ideas list?"
        else:
            return None
        return {"type": kind, **out, "text": text, "evidence": evidence}

    def _blocked(self, p: dict, state: dict, asked: list[dict]) -> bool:
        """Declined lately, being watched first ("Observe longer"), or asked already tonight."""
        cutoff = (now() - dt.timedelta(days=int(self.setting("no_days") or 30))).isoformat()
        if any(r["date"] >= cutoff and same_idea(r, p) for r in state["rejected"]):
            return True
        watching = [o["proposal"] for o in self.observations() if o["status"] == "active" and o.get("proposal")]
        return any(same_idea(w, p) for w in watching) or any(same_idea(a, p) for a in asked)

    def _question(self, p: dict) -> str:
        text = p["text"]
        if p["type"] == "setting":
            text += f"\n({p['key']}: {json.dumps(self.app.settings.get(p['key']))} -> {json.dumps(p['value'])})"
        elif p["type"] == "profile":
            text += f'\nThe line for {help_rel(self.app)}: "{p["line"]}"'
        elif p["type"] == "skill":
            text += f"\nThe change to your {p['skill']} skill: {p['change']}\n(You'll see it before it's saved.)"
        elif p["type"] == "idea":
            text += f"\nThe idea: {p['idea']}"
        elif p["type"] == "observe":
            text += f"\nWatch: {p['observe']} ({p['days']} days)"
        return text + (f"\n\nWhy: {p['evidence']}" if p.get("evidence") else "")

    def _ask(self, pid: str, p: dict) -> None:
        text = self._question(p)
        ask = getattr(self.app, "ask", None)
        if ask is not None:
            ask.ask(
                text,
                choices=CHOICES,
                hook="retro.answer",
                hook_payload={"pid": pid},
                expires=dt.timedelta(days=3),
                source="retro",
                title="Suggestion",
                why="retro.suggestion",
            )
            return
        self.app.notify(
            text,
            kind="question",
            title="Suggestion",
            buttons=[
                [("Apply", f"retro:{pid}:yes"), ("Observe longer", f"retro:{pid}:observe"), ("No", f"retro:{pid}:no")]
            ],
            why="retro.suggestion",
        )

    def callbacks(self):
        return {"retro": self._button, "obs": self._obs_button}

    def _button(self, pid: str, act: str) -> str:
        words = {"yes": "Apply", "observe": "Observe longer", "no": "No", "save": "Save", "discard": "Discard"}
        return self.answer(pid, words.get(act, act))

    def answer(self, pid: str, answer: str) -> str:
        """Your answer to a proposal: Apply, Observe longer (or "observe 14"), No; then Save or Discard for a skill
        change you've seen."""
        store = jload(self.file, {}) or {}
        p = store.get(pid)
        if not p:
            return "That suggestion is gone."
        p.setdefault("type", "setting")  # proposals from before 0.2.0
        p.setdefault("main", p.get("key", ""))
        p.setdefault("text", f"Set {p.get('key')} to {json.dumps(p.get('value'))}")
        a = re.sub(r"\s+", " ", str(answer or "")).strip().lower()
        if p.get("status") in ("editing", "ready"):  # a skill change: Save or Discard now
            if a.startswith(("discard", "no")):
                self._drop(store, pid)
                if p.get("draft"):
                    Path(p["draft"]).unlink(missing_ok=True)
                self.app.events.emit("retro_answer", type="skill", answer="discard")
                return "Discarded; your skill is as it was."
            if a.startswith(("save", "yes", "apply")) and p.get("status") == "ready":
                return self._skill_save(pid, p, store)
            return "I'm still writing that change; you'll see it before anything is saved."
        if a.startswith(("apply", "yes", "approve", "ok", "sure", "do it")):
            self.app.events.emit("retro_answer", type=p["type"], answer="apply")
            return self._apply(pid, p, store)
        if a.startswith(("observe", "watch", "wait")):
            m = re.search(r"\d+", a)
            days = max(1, min(int(m[0]), 60)) if m else int(self.setting("observe_days") or 7)
            self._drop(store, pid)
            what = {"observe": p.get("observe"), "profile": p.get("line"), "idea": p.get("idea")}.get(p["type"])
            what = what or (f"the {p['skill']} skill: {p['change']}" if p["type"] == "skill" else p.get("text", ""))
            self.observe(what, days, source="retro", proposal={"type": p["type"], "main": p.get("main", "")})
            self.app.events.emit("retro_answer", type=p["type"], answer="observe")
            return f"OK, I'll keep watching for {days} days before suggesting it again."
        self._drop(store, pid)
        if a.startswith(("no", "skip", "deny", "never", "don't", "dont")):
            state = self._state()
            state["rejected"].append(
                {"date": now().isoformat(), "type": p["type"], "main": p.get("main", ""), "text": p.get("text", "")}
            )
            self._save_state(state)
            self.app.events.emit("retro_answer", type=p["type"], answer="no")
            return f"OK, I won't suggest that again for {int(self.setting('no_days') or 30)} days."
        self.app.events.emit("retro_answer", type=p["type"], answer="other")
        return "OK, I'll leave it as it is."

    def _drop(self, store: dict, pid: str) -> None:
        store.pop(pid, None)
        jsave(self.file, store)

    def _applied(self, p: dict, result: str) -> None:
        state = self._state()
        state["applied"] = [*state["applied"], {"date": now().isoformat(), "text": p.get("text", ""), "result": result}]
        self._save_state(state)
        self.app.events.emit("retro_applied", type=p["type"], key=p.get("key") or p.get("skill") or "")

    def _apply(self, pid: str, p: dict, store: dict) -> str:
        kind = p["type"]
        if kind == "skill":
            return self._skill_start(pid, p, store)
        self._drop(store, pid)
        if kind == "setting":
            key, value = p["key"], p["value"]
            tun = self.tunable()
            if key not in tun or not valid(tun[key], value):
                return f"Not changed: {key} can't take that value any more."
            self.app.settings.set(key, value)
            self.app.events.emit("setting_changed", key=key, via="retro")
            self._restart_owner(key)
            done = f"Done: {key} = {json.dumps(value)}."
        elif kind == "profile":
            added = add_line(self.app, LEARNED, f"{p['line']} ({now():%Y-%m-%d})")
            where = help_rel(self.app)
            done = f"Added to {where}." if added else f"{where} says that already."
        elif kind == "observe":
            done = self.observe(p["observe"], int(p.get("days") or 7), source="retro")
        elif kind == "idea":
            f = layout.path(self.app, "ideas")
            have = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""
            f.parent.mkdir(parents=True, exist_ok=True)
            head = layout.frontmatter(self.app, "ideas", f, title="Ideas", bare=True)
            text = have or head + IDEAS_INTRO.format(name=self.app.name)
            f.write_text(text.rstrip("\n") + f"\n- [ ] {p['idea']} ({now():%Y-%m-%d})\n", encoding="utf-8")
            done = f"Added to {layout.shown(self.app, f)}" + (
                " in your notes." if layout.of(self.app).inside_notes(f) else "."
            )
        else:
            return "I don't know how to apply that."
        self._applied(p, done)
        return done

    def _restart_owner(self, key: str) -> None:
        """Let the feature that owns the setting pick it up (its scheduled times are registered again)."""
        m = self.app.modules.get(key.split(".")[0])
        if m is not None and m.id != self.id and self.app.is_on(m.id):
            try:
                m.start()
            except Exception as e:
                self.app.events.emit("module_failed", module=m.id, error=f"{type(e).__name__}: {e}"[:300])

    # ------------------------------------------------------------------------------------ skill changes
    def _skill_path(self, name: str) -> tuple[Path | None, Path]:
        """(the file the skill is read from now, or None; where your own copy lives)."""
        mine = layout.path(self.app, "skills") / name / "SKILL.md"
        try:
            from kurooto.modules.skills import load_skill

            s = load_skill(self.app, name)
            if s is not None and getattr(s, "path", None):
                return Path(s.path), mine
        except Exception:
            pass
        if mine.is_file():
            return mine, mine
        shipped = resources.files("kurooto.data").joinpath("skills", name, "SKILL.md")
        return (Path(str(shipped)) if shipped.is_file() else None), mine

    def _skill_text(self, name: str) -> str | None:
        src, _ = self._skill_path(name)
        try:
            return src.read_text(encoding="utf-8") if src else None
        except OSError:
            return None

    def _skill_start(self, pid: str, p: dict, store: dict) -> str:
        text = self._skill_text(p["skill"])
        if text is None:
            self._drop(store, pid)
            return f"There's no {p['skill']} skill any more."
        p.update(status="editing", base=hashlib.sha256(text.encode()).hexdigest())
        store[pid] = p
        jsave(self.file, store)
        self.app.jobs.submit(
            SKILL_EDIT.format(change=p["change"], text=text),
            title=f"Skill change: {p['skill']}",
            effort="medium",
            quiet=True,
            then="retro.skill_ready",
            then_payload={"pid": pid},
            background=True,
        )
        return f"Writing the change to your {p['skill']} skill; you'll see it before anything is saved."

    def _skill_ready(self, job, result, payload) -> None:
        store = jload(self.file, {}) or {}
        pid = (payload or {}).get("pid", "")
        p = store.get(pid)
        if not p:
            return
        name = p["skill"]
        old = self._skill_text(name) or ""
        new = ""
        if result.ok:
            m = re.search(r"===BEGIN===\s*\n(.*?)\n\s*===END===", result.text or "", re.S)
            new = (m[1] if m else re.sub(r"\A```\w*\n|\n```\s*\Z", "", (result.text or "").strip())).strip() + "\n"
        why = ""
        if not result.ok:
            why = "the AI didn't answer (" + (result.detail or result.text or "no reason given")[:200] + ")"
        elif not new.strip() or new.strip() == old.strip():
            why = "the AI's version was the same as now"
        elif old.startswith("---") and not new.startswith("---"):
            why = "the AI's version lost the skill's header"
        if why:
            self._drop(store, pid)
            self.app.notify(f"Nothing changed in your {name} skill: {why}.", kind="result", why="asked")
            return
        draft = self.app.paths.state / "retro-skills" / f"{pid}.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(new, encoding="utf-8")
        diff = "\n".join(
            ln.rstrip()
            for ln in difflib.unified_diff(old.splitlines(), new.splitlines(), "now", "new", n=1, lineterm="")
        )
        if len(diff) > 3000:
            diff = diff[:3000] + "\n[... more changes]"
        p.update(status="ready", draft=str(draft))
        store[pid] = p
        jsave(self.file, store)
        self.app.notify(
            f"The change to your {name} skill (- removed, + added):\n\n{diff}\n\nSave it? The current version is kept "
            "as a backup.",
            kind="question",
            title="Skill change",
            buttons=[[("Save", f"retro:{pid}:save"), ("Discard", f"retro:{pid}:discard")]],
            why="asked",
        )

    def _skill_save(self, pid: str, p: dict, store: dict) -> str:
        name = p["skill"]
        old = self._skill_text(name)
        draft = Path(p.get("draft", ""))
        if old is None or not draft.is_file():
            self._drop(store, pid)
            return "That change is gone."
        if hashlib.sha256(old.encode()).hexdigest() != p.get("base"):
            self._drop(store, pid)
            draft.unlink(missing_ok=True)
            return f"Your {name} skill changed in the meantime, so nothing was saved; your edits stay."
        backup = self.app.paths.data / "backups" / "skills" / f"{name}-{now():%Y%m%d-%H%M%S}.md"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(old, encoding="utf-8")
        target = None
        sk = self.app.modules.get("skills")
        if sk is not None and hasattr(sk, "customize"):
            try:
                target = Path(sk.customize(name))
            except Exception:
                target = None
        target = target or self._skill_path(name)[1]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(draft.read_text(encoding="utf-8"), encoding="utf-8")
        draft.unlink(missing_ok=True)
        self._drop(store, pid)
        done = f"Saved your {name} skill (kurooto/skills/{name}/SKILL.md in your notes); the old one is in backups."
        self.app.events.emit("skill_edited", name=name)
        self._applied(p, done)
        return done

    # ------------------------------------------------------------------------------------- observations
    def observations(self) -> list[dict]:
        return [o for o in (jload(self.obs_file, []) or []) if isinstance(o, dict) and o.get("id")]

    def observe(self, what: str, days: int | None = None, source: str = "you", proposal: dict | None = None) -> str:
        what = re.sub(r"\s+", " ", str(what or "")).strip(" .")[:300]
        if not what:
            return "What should I keep an eye on? e.g. /observe whether I study better before noon for 2 weeks"
        days = max(1, min(int(days or self.setting("observe_days") or 7), 365))
        until = now() + dt.timedelta(days=days)
        o = {
            "id": "o" + uuid.uuid4().hex[:6],
            "what": what,
            "created": now().isoformat(timespec="seconds"),
            "until": until.isoformat(timespec="seconds"),
            "status": "active",
            "source": source,
            "proposal": proposal,
        }
        jsave(self.obs_file, [*self.observations(), o][-200:])
        self.app.events.emit("observe_added", id=o["id"], days=days, source=source)
        return f"Watching until {until:%a %d %b}: {what}. The nightly look back will tell you what it finds."

    def stop_observing(self, oid: str) -> str:
        items = self.observations()
        for o in items:
            if o["id"] == oid and o["status"] == "active":
                o["status"] = "stopped"
                jsave(self.obs_file, items)
                self.app.events.emit("observe_stopped", id=oid)
                return f"Stopped watching: {o['what']}"
        return "That isn't being watched any more."

    def _finish_observation(self, o: dict, finding: str) -> None:
        items = self.observations()
        for x in items:
            if x["id"] == o["id"]:
                x.update(status="ended", ended=now().isoformat(timespec="seconds"), finding=finding[:2000])
        jsave(self.obs_file, items)
        self.app.notify(
            f'What I found about "{o["what"]}" (watched since {o["created"][:10]}):\n'
            + (finding or "Nothing clear enough to say; there wasn't enough to go on."),
            kind="result",
            title="Finding",
            why="asked",
        )
        self.app.events.emit("observe_ended", id=o["id"], found=bool(finding))

    def extend_observing(self, oid: str, days: int | None = None) -> str:
        """Watch something longer: its end moves `days` (observe_days, 7 by default) later."""
        days = max(1, min(int(days or self.setting("observe_days") or 7), 365))
        items = self.observations()
        for o in items:
            if o["id"] == oid and o["status"] == "active":
                until = max(dt.datetime.fromisoformat(o["until"]), now()) + dt.timedelta(days=days)
                o["until"] = until.isoformat(timespec="seconds")
                jsave(self.obs_file, items)
                self.app.events.emit("observe_extended", id=oid, days=days)
                return f"Watching until {until:%a %d %b}: {o['what']}"
        return "That isn't being watched any more."

    def _obs_button(self, oid: str, act: str) -> str:
        if act == "ext":
            return self.extend_observing(oid)
        return self.stop_observing(oid) if act == "stop" else "ok"

    # ------------------------------------------------------------------------------- Telegram and calls
    def commands(self):
        return [
            Command("observe", "watch something first: /observe whether I sleep better for 2 weeks", self._cmd_observe),
            Command("observing", "what's being watched (with Stop and +7 days buttons)", self._cmd_observing),
            Command("lookback", "the last nightly look back; /lookback now runs one now", self._cmd_lookback),
        ]

    def _cmd_observe(self, msg: Incoming, arg: str) -> str:
        what, days = split_length(arg, int(self.setting("observe_days") or 7))
        return self.observe(what, days)

    def _cmd_observing(self, msg: Incoming, arg: str) -> str | None:
        items = [o for o in self.observations() if o["status"] == "active"]
        if not items:
            return "Nothing is being watched. /observe <what> [for N days]"
        more = int(self.setting("observe_days") or 7)
        for o in items[:15]:
            msg.reply(
                f"Until {dt.datetime.fromisoformat(o['until']):%a %d %b}: {o['what']}",
                buttons=[[("Stop", f"obs:{o['id']}:stop"), (f"+{more} days", f"obs:{o['id']}:ext")]],
            )
        return None

    def _cmd_lookback(self, msg: Incoming, arg: str) -> str:
        if arg.strip().lower() == "now":
            if self.run_in_background():
                return "Looking back now; any suggestions come as messages in a few minutes."
            return "A look back is running already."
        last = self._state().get("last")
        if not last:
            return f"No look back yet; the next is at {self.setting('when')}. /lookback now runs one now."
        head = f"Last look back: {last['at'].replace('T', ' ')}, {last['proposals']} suggestion(s), "
        return (head + f"{last['findings']} finding(s).\n{last.get('noticed') or ''}").strip()

    def intents(self):
        def match(text: str):
            m = OBSERVE.match(text)
            if not m:
                return None
            what, days = split_length(m["what"], int(self.setting("observe_days") or 7))
            return {"what": what, "days": days} if len(what) > 3 else None

        return [
            Intent("observe", "watch something for a while", match, lambda m, s: self.observe(s["what"], s["days"]))
        ]

    def help(self):
        return ['"observe whether … for 2 weeks", /observe, /observing, /lookback']

    def call_tools(self):
        return [
            Tool(
                "observe",
                "Keep an eye on something for a while before changing anything (e.g. 'whether they study better "
                "before noon'); the nightly look back reports what it found.",
                self._tool_observe,
                {"what": arg("what to watch, as a phrase"), "days": arg("how many days, e.g. 14 (optional)")},
                ("what",),
                offline="queue",
                hint='When they ask you to watch or observe something over days ("see whether ..."), call observe.',
            )
        ]

    def _tool_observe(self, a: dict) -> str:
        what, days = split_length(str(a.get("what", "")), int(self.setting("observe_days") or 7))
        m = re.search(r"\d+", str(a.get("days") or ""))
        return self.observe(what, int(m[0]) if m else days)

    # ------------------------------------------------------------------------------------------- state
    def _state(self) -> dict:
        s = jload(self.state_file, {}) or {}
        s.setdefault("rejected", [])
        s.setdefault("applied", [])
        return s

    def _save_state(self, s: dict) -> None:
        s["rejected"] = s["rejected"][-200:]
        s["applied"] = s["applied"][-50:]
        jsave(self.state_file, s)
