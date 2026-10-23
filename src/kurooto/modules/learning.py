"""Learns from its own work: Kurooto keeps what its finished work teaches it, acts on it and tells you in one line,
with Undo. No review queue. In the spirit of Hermes Agent (Nous Research); the design only, none of its code.

Four parts, each with its own switch (Settings, the card on the Features page):
    search       a search index of past AI requests and their answers (jobs.db), call transcripts and chat turns,
                 kept up to date in Kurooto's state folder (learning/history.db, SQLite full-text search); /history
                 <words> searches it, and so can the AI (the search_history tool, for agy, Claude Code and API brains)
    skills       after a request that went well and took learning.skill_min_steps tool uses or more, one background
                 request on the second-look AI (low effort) decides whether how it was done is a procedure worth
                 keeping. If so: a new skill in your skills folder (learned: true, the request, the date), or a few
                 tips added to the skill that already does it ("## Learned from experience"), never a duplicate
    corrections  when you correct a skill's answer (a reply to it, or "no, ...", "that's wrong", "next time ..." soon
                 after it), the skill gets a line under "## Lessons" (or, rarely, the step that failed rewritten)
    remember     the nightly look back (modules/retro.py) also picks out up to learning.remember_max lasting facts
                 and preferences you stated in the day's chats and calls; they go into your how-to-help-me note by
                 Remember's rules (never health, money, passwords or other people's details)
Each change says so in one message with an Undo button; /learned lists the recent ones with theirs. Every change to a
skill file keeps the file as it was (state/learning/before/), and an Undo puts it back unless you edited it since.
Learned skills and lessons need Skills on; picking up facts needs the nightly look back on.

What leaves the computer: the index is built and kept here; passages the AI finds with search_history go to that AI
as part of its request. Learning a skill or a lesson sends the request, its answer and steps (or your correction and
the skill) to the second-look AI; picking up facts sends the day's requests to the AI the look back uses.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave, owner_only
from kurooto.modules.base import Command, Incoming, Module
from kurooto.modules.calls.tools import Tool, arg

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "learning",
    {
        "search": True,  # a search index of past requests, calls and chats on this computer: /history, search_history
        "skills": True,  # a request that took many steps can become a skill (or improve the one that does it)
        "corrections": True,  # a skill learns a lesson when you correct its answer
        "remember": True,  # the nightly look back keeps facts you stated in your chats and calls (how-to-help note)
        "skill_min_steps": 5,  # tool uses a request needs before it's looked at as a possible skill
        "remember_max": 3,  # facts kept a night, at most
        "brain": "",  # the AI that looks at finished work ("": the concept graph's second-look AI, else your main one)
    },
)

PARTS = {
    "search": "Search past requests, calls and chats (/history)",
    "skills": "Skills from requests that took many steps",
    "corrections": "Skills learn from your corrections",
    "remember": "Keep facts you state (nightly look back)",
}
CHECKS_A_DAY = 5  # requests looked at as possible skills, at most, a day
CORRECTION_WINDOW_S = 2 * 3600  # "no, ..." counts as a correction of a skill's answer this long after it
KEEP_CHANGES = 100
LEARNED_HEAD = "Learned from experience"
LESSONS_HEAD = "Lessons"
ASKED_CUT = "\n\nHow to work (the rules for every skill)"  # where a skill request's own words end (modules/skills.py)

# a message that corrects what came just before it
CORRECTION = re.compile(
    r"^\s*(?:no\b|nope\b|nah\b|wrong\b|not quite\b|actually\b|next time\b|that'?s (?:not right|wrong|incorrect)\b|"
    r"(?:that|this|it) (?:is|was|'s) (?:wrong|not right|incorrect)\b)",
    re.I,
)
# a reply to a skill's answer that may correct it (an answer to its question or a follow-up has none of these)
CORRECTING = re.compile(
    r"\b(?:no|not|wrong|incorrect|instead|should(?:n'?t)?|next time|don'?t|didn'?t|forgot|missed|always|never|"
    r"actually|rather|mistake|fix)\b",
    re.I,
)
# other people's details: a picked-up fact about the user only
OTHERS = re.compile(
    r"\b(?:my|his|her|their|our)\s+(?:mom|mum|mother|dad|father|parents?|brother|sister|siblings?|friends?|"
    r"girlfriend|boyfriend|wife|husband|partner|roommates?|flatmates?|colleagues?|boss|son|daughter|kids?|children|"
    r"cousins?|aunt|uncle|grand\w+)\b|\b(?:he|she|him|his|hers)\b|@|"
    r"\+\d{6,}|\b\d{10,}\b|\b\d{3,5}[ -]\d{3,4}[ -]\d{3,5}\b",  # and phone numbers
    re.I,
)

LEARN_SKILL = """You look back at a request an AI assistant (Kurooto) just finished for its user, to decide whether HOW
it was done is a reusable procedure worth keeping as a skill: instructions the assistant follows when the user types
one command.

What the user asked:
{asked}

The answer it gave (the end of it):
{answer}

The steps it took (tools it used, in order, with their arguments):
{steps}

Skills the assistant has already (name: what it does):
{skills}

Decide:
- NONE when it was a one-off (a question, a lookup, a conversation), when the steps only fit this one case, or when it
  needed anything that sends, deletes, spends or runs programs.
- IMPROVE <name> when a skill above already does this, or nearly: then give 1 to 5 short steps or tips learned here
  that would make that skill better. Don't repeat what it says already.
- NEW when it's a procedure the user is likely to want again (a weekly report, a way of filing things, a study log of
  a certain shape) and no skill above does it.

Reply in exactly one of these shapes and nothing else:

NONE: <a short reason>

IMPROVE <name>
- <a step or tip>

NEW
```skill
---
name: <lowercase-with-hyphens, 2 to 40 characters, not a name above>
description: <one line: what it does>
effort: <low | medium | high>
args: <a short hint of what to type after the command, or nothing>
---
<numbered steps, written to the AI that will follow them. Generalise: this request's specifics (its dates, subject,
file names) become $ARGUMENTS (what the user types after the command) or something to look up. Say which notes to read,
where to write and what to reply. Only these tools: {tools}. Never shell commands or programs; never delete or reword
what the user wrote; nothing sent to anyone else; no health, money or other people's private details. At most 50
lines.>
```"""

LESSON = """The user corrected the result of a skill: instructions an AI assistant (Kurooto) follows when they type
/{name}. Decide what the skill should learn so it goes right next time.

The skill file now:
{text}

What the skill answered (the end of it):
{answer}

What the user said about it:
{said}

Reply in exactly one of these shapes and nothing else:

NONE: <a short reason> (when it isn't a correction of how the skill works: a follow-up request, an answer to its
question, a detail true only this once)

LESSON: <one short instruction in the imperative, general enough for next time, e.g. "Put the week's dates in the
title.">

REWRITE
```skill
<the whole skill file with only the step that failed rewritten; everything else exactly as it is, the header between
the --- lines included>
```

Prefer LESSON; REWRITE only when a step plainly says the wrong thing. No health, money or other people's private
details."""

REMEMBER_ASK = """
Also, separately from the proposals: `chats` has what the user asked or said to the assistant today, in their own
words (call transcripts are above, when there are any). Pick out at most {n} lasting facts or preferences the user
stated about themselves or how they like to be helped ("I'm a morning person", "keep answers short", "my lab is on
Thursdays"), written as one short sentence each about the user. Only what they said plainly; nothing that's in
`how_to_help_me` already; never health, money, passwords, or anything about other people. Add them to your JSON
answer as "remember": ["...", ...]; an empty list is the usual answer."""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def asked(prompt: str) -> str:
    """What the user asked, from a request as it was queued: the chat's earlier turns and a skill's rules left out."""
    text = str(prompt or "")
    if "Current request:\n" in text:
        text = text.split("Current request:\n", 1)[1]
    return text.split(ASKED_CUT, 1)[0].strip()


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", str(s or "").lower()) if len(w) > 2}


def similar(a: str, b: str) -> bool:
    """Two names-and-descriptions that say mostly the same thing."""
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.5


# ------------------------------------------------------------------------------------------- the search index
def index_file(app: App) -> Path:
    return app.paths.state / "learning" / "history.db"


def index_size(app: App) -> int:
    f = index_file(app)
    return sum(p.stat().st_size for p in (f, f.with_name(f.name + "-wal"), f.with_name(f.name + "-shm")) if p.exists())


class History:
    """A full-text index of past requests and their answers, call transcripts and chat turns. On this computer only;
    brought up to date (new or changed items only) before each search and every 15 minutes."""

    LABEL = {"request": "AI request", "call": "call", "chat": "chat"}

    def __init__(self, app: App):
        self.app = app
        self.file = index_file(app)
        self._lock = threading.Lock()
        self.fts: bool | None = None  # SQLite's full-text search is there (else plain matching)

    def _con(self) -> sqlite3.Connection:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.file), timeout=10)
        con.execute("pragma journal_mode=wal")
        if self.fts is None:
            try:
                con.execute(
                    "create virtual table if not exists docs using fts5(title, body, key unindexed, kind unindexed, "
                    "at unindexed, tokenize='unicode61 remove_diacritics 2')"
                )
                self.fts = True
            except sqlite3.OperationalError:  # a Python built without FTS5: the same table, matched word by word
                con.execute("create table if not exists docs(title text, body text, key text, kind text, at real)")
                self.fts = False
        con.execute("create table if not exists marks(name text primary key, value text)")
        con.execute("create table if not exists answers(h text primary key)")
        owner_only(self.file)
        return con

    @staticmethod
    def _mark(con, name: str, default: str = "") -> str:
        row = con.execute("select value from marks where name=?", (name,)).fetchone()
        return row[0] if row else default

    @staticmethod
    def _put(con, key: str, kind: str, at: float, title: str, body: str) -> None:
        con.execute("delete from docs where key=?", (key,))
        con.execute(
            "insert into docs(title, body, key, kind, at) values(?,?,?,?,?)", (title[:200], body, key, kind, at)
        )

    def update(self) -> int:
        """Add what's new since the last time (requests, calls, chat turns). How many items were added."""
        with self._lock, contextlib.closing(self._con()) as con, con:
            return self._requests(con) + self._calls(con) + self._chats(con)

    def _requests(self, con) -> int:
        since = float(self._mark(con, "jobs", "0") or 0)
        n = 0
        for jid, title, prompt, result, finished, lane, then in self.app.jobs.finished_since(since):
            since = max(since, float(finished or 0))
            if lane != "you" or then.startswith("learning."):  # your own requests, not background work
                continue
            body = f"{asked(prompt)[:4000]}\n\n{str(result or '')[:8000]}"
            self._put(con, f"job:{jid}", "request", float(finished or 0), str(title or ""), body)
            con.execute("insert or ignore into answers(h) values(?)", (_sha(str(result or "")[:1200].strip()),))
            n += 1
        con.execute("insert or replace into marks(name, value) values('jobs', ?)", (repr(since),))
        return n

    def _calls(self, con) -> int:
        d = self.app.paths.state / "calls" / "transcripts"
        n = 0
        for f in sorted(d.glob("*.txt")) if d.is_dir() else []:
            try:
                when = dt.datetime.strptime(f.stem, "%Y-%m-%d-%H%M%S")
                mtime = repr(f.stat().st_mtime)
            except (ValueError, OSError):
                continue
            if self._mark(con, f"call:{f.stem}") == mtime:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")[:30000]
            self._put(con, f"call:{f.stem}", "call", when.timestamp(), f"Call on {when:%a %d %b %H:%M}", text)
            con.execute("insert or replace into marks(name, value) values(?, ?)", (f"call:{f.stem}", mtime))
            n += 1
        return n

    def _chats(self, con) -> int:
        since = float(self._mark(con, "chat", "0") or 0)
        n = 0
        for t in jload(self.app.paths.state / "chat" / "history.json", []) or []:
            at = float(t.get("at") or 0) if isinstance(t, dict) else 0
            if at <= since:
                continue
            since = max(since, at)
            answer = str(t.get("assistant") or "")
            if con.execute("select 1 from answers where h=?", (_sha(answer[:1200].strip()),)).fetchone():
                continue  # its request is in the index already
            user = str(t.get("user") or "")
            self._put(con, f"chat:{at!r}", "chat", at, user.split("\n")[0][:80], f"{user}\n\n{answer}")
            n += 1
        con.execute("insert or replace into marks(name, value) values('chat', ?)", (repr(since),))
        return n

    def search(self, query: str, days: float | None = None, limit: int = 8) -> list[dict]:
        """The best matches for the words, newest-first among equals: kind, when, title and the passage."""
        words = re.findall(r"\w+", str(query or "").lower())[:12]
        if not words:
            return []
        self.update()
        cutoff = time.time() - float(days) * 86400 if days else 0.0
        with self._lock, contextlib.closing(self._con()) as con:
            rows: list = []
            if self.fts:
                for joiner in (" AND ", " OR "):  # every word first; any of them when that finds nothing
                    match = joiner.join(f'"{w}"*' for w in words)
                    rows = con.execute(
                        "select key, kind, at, title, snippet(docs, 1, '«', '»', ' … ', 24) from docs "
                        "where docs match ? and at >= ? order by bm25(docs, 4.0, 1.0), at desc limit ?",
                        (match, cutoff, limit),
                    ).fetchall()
                    if rows:
                        break
            else:
                like = " and ".join("(lower(title) like ? or lower(body) like ?)" for _ in words)
                args = [x for w in words for x in (f"%{w}%", f"%{w}%")]
                found = con.execute(
                    f"select key, kind, at, title, body from docs where {like} and at >= ? order by at desc limit ?",  # noqa: S608 (placeholders only)
                    (*args, cutoff, limit),
                ).fetchall()
                rows = [(k, kd, at, ti, _around(body, words[0])) for k, kd, at, ti, body in found]
        return [
            {
                "kind": self.LABEL.get(kind, kind),
                "when": dt.datetime.fromtimestamp(float(at)).strftime("%a %d %b %Y %H:%M"),
                "title": title,
                "passage": re.sub(r"\s+", " ", passage or "").strip()[:400],
                "ref": key,
            }
            for key, kind, at, title, passage in rows
        ]

    def stats(self) -> int:
        if not self.file.exists():
            return 0
        with self._lock, contextlib.closing(self._con()) as con:
            return int(con.execute("select count(*) from docs").fetchone()[0])

    def old(self, cutoff: float) -> int:
        if not self.file.exists():
            return 0
        with self._lock, contextlib.closing(self._con()) as con:
            return int(con.execute("select count(*) from docs where at < ?", (cutoff,)).fetchone()[0])

    def prune(self, cutoff: float) -> int:
        """Forget what's older than cutoff (the Space keeper, with space.jobs_days). How many items went."""
        return self.forget(float("-inf"), cutoff)

    def forget(self, lo: float, hi: float) -> int:
        """Forget the items from [lo, hi) (also retention, core/retention.py). How many items went."""
        if not self.file.exists():
            return 0
        with self._lock, contextlib.closing(self._con()) as con:
            with con:
                n = con.execute("delete from docs where at >= ? and at < ?", (lo, hi)).rowcount
            if n:
                con.execute("vacuum")
            return n


def _around(text: str, word: str, width: int = 160) -> str:
    i = str(text or "").lower().find(word)
    return str(text or "")[max(0, i - width // 2) : max(0, i - width // 2) + width] if i >= 0 else str(text)[:width]


# ----------------------------------------------------------------------------------------------- the feature
class Learning(Module):
    id = "learning"
    title = "Learns from its own work"
    description = (
        "Keeps what its finished work teaches it: a search of past requests, calls and chats (/history), skills "
        "from requests that took many steps, lessons when you correct a skill, facts you state. It tells you each "
        "time, with Undo."
    )
    requires = ("chat",)
    extra = True  # an add-on: turned on by hand, never by a preset
    privacy = (
        "The search index of your past requests, calls and chats is built and kept on this computer; when the AI "
        "searches it, the passages it finds go to that AI. Learning a skill or a lesson sends the request, its answer "
        "and steps (or your correction and the skill) to the AI you use for second looks; picking up facts sends the "
        "day's requests to the AI the nightly look back uses."
    )

    def __init__(self, app):
        super().__init__(app)
        self.dir = app.paths.state / "learning"
        self.state_file = self.dir / "state.json"
        self.changes_file = self.dir / "changes.json"
        self.index = History(app)
        self._lock = threading.Lock()
        # registered at once: a judgement that finishes after a restart, or after the feature went off, isn't lost
        app.jobs.then_actions["learning.skill"] = self._skill_judged
        app.jobs.then_actions["learning.lesson"] = self._lesson_judged
        app.jobs.watchers.append(self._finished)

    def start(self):
        self.every("index", "every 15m", self._index_soon)

    def _index_soon(self, p=None) -> str:
        if self.setting("search"):
            threading.Thread(target=self._index_quietly, name="learning-index", daemon=True).start()
        return "indexing"

    def _index_quietly(self) -> None:
        try:
            self.index.update()
        except (sqlite3.Error, OSError) as e:
            self.app.events.emit("learning_index_failed", error=f"{type(e).__name__}: {e}"[:200])

    def part(self, name: str) -> bool:
        """Is this part on (and the feature)?"""
        return self.app.is_on(self.id) and bool(self.setting(name))

    def check_brain(self) -> str | None:
        """The AI that looks at finished work: learning.brain, else the concept graph's second-look AI (Claude Code
        beside agy when both are installed, so it doesn't wait behind your requests), else the main one."""
        own = str(self.setting("brain") or "").strip()
        if own:
            return own
        graph = self.app.modules.get("integrate")
        try:
            return (graph.roles()[1] if graph is not None else "") or None
        except Exception:
            return None

    # -------------------------------------------------------------------------------------------- state
    def _state(self) -> dict:
        return jload(self.state_file, {}) or {}

    def _save_state(self, st: dict) -> None:
        jsave(self.state_file, st)

    def changes(self) -> list[dict]:
        return [c for c in jload(self.changes_file, []) or [] if isinstance(c, dict) and c.get("id")]

    def _record(self, kind: str, **fields) -> str:
        cid = uuid.uuid4().hex[:8]
        c = {"id": cid, "kind": kind, "at": now().isoformat(timespec="seconds"), **fields}
        with self._lock:
            jsave(self.changes_file, [*self.changes(), c][-KEEP_CHANGES:])
        return cid

    def _keep_before(self, cid_hint: str, text: str) -> str:
        f = self.dir / "before" / f"{now():%Y%m%d-%H%M%S}-{cid_hint}.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        return str(f)

    # ------------------------------------------------------------------------------------ finished requests
    def _finished(self, job, result, info: dict) -> None:
        """Every finished request (core/jobs.py:Jobs.watchers): remember a skill's answer (for corrections), and
        look at a request that took many steps as a possible skill."""
        if not self.app.is_on(self.id) or not result.ok:
            return
        then = info.get("then") or ""
        if then in ("skills.done", "skills.latex"):
            name = str((info.get("payload") or {}).get("name") or "")
            if name:
                with self._lock:
                    st = self._state()
                    st["last_skill"] = {"name": name, "job": job.id, "at": time.time()}
                    self._save_state(st)
            return
        if then or job.lane != "you" or not self.setting("skills") or not self.app.is_on("skills"):
            return
        steps = info.get("steps") or []
        used = max(len(steps), int((result.usage or {}).get("tool_calls") or 0))
        if used < max(1, int(self.setting("skill_min_steps") or 5)):
            return
        with self._lock:
            st = self._state()
            day = f"{now():%Y-%m-%d}"
            checks = st.get("checks") if (st.get("checks") or {}).get("day") == day else {"day": day, "n": 0}
            if checks["n"] >= CHECKS_A_DAY:
                return
            checks["n"] += 1
            st["checks"] = checks
            self._save_state(st)
        self.judge_skill(job, result, steps)

    def judge_skill(self, job, result, steps: list[dict]) -> str:
        from kurooto.core.tools import agent_tools
        from kurooto.modules.skills import all_skills

        skills = {k: s for k, s in all_skills(self.app).items() if not s.internal}
        listed = "\n".join(f"- {k}: {s.description[:150]}" for k, s in sorted(skills.items())) or "(none yet)"
        log = "\n".join(f"{i}. {s.get('name')}({s.get('args', '')})" for i, s in enumerate(steps[:60], 1))
        tools = ", ".join(t.name for t in agent_tools(self.app)) or "the notes tools"
        prompt = LEARN_SKILL.format(
            asked=asked(job.prompt)[:4000],
            answer=str(result.text or "")[-3000:],
            steps=log or "(the AI used tools, but its program didn't report which)",
            skills=listed,
            tools=tools,
        )
        jid = self.app.jobs.submit(
            prompt,
            title=f"Worth a skill? {job.title[:50]}",
            effort="low",
            quiet=True,
            then="learning.skill",
            then_payload={"job": job.id, "title": job.title[:80], "day": f"{dt.date.fromtimestamp(job.created)}"},
            background=True,
            text_only=True,
            lane="chk",
            brain=self.check_brain(),
            why="learning.skill",
        )
        self.app.events.emit("learning_skill_checked", job=job.id, steps=len(steps))
        return jid

    # ---------------------------------------------------------------------------------- skills from experience
    def _skill_judged(self, job, result, payload: dict) -> None:
        if not result.ok:
            self.app.events.emit("learning_skill_failed", verdict=str(result.verdict)[:20])
            return
        if not self.part("skills") or not self.app.is_on("skills"):
            return
        from kurooto.modules.skills import extract_skill

        text = str(result.text or "").strip()
        first = re.sub(r"^[\s*#>`_]+", "", text.split("\n", 1)[0] if text else "")
        if not text or re.match(r"(?i)none\b", first):
            self.app.events.emit("learning_skill_none")
            return
        m = re.match(r"(?i)improve\s+/?([a-z0-9][a-z0-9-]{1,39})", first)
        if m:
            tips = [ln.strip()[2:].strip() for ln in text.splitlines()[1:] if ln.strip().startswith(("- ", "* "))]
            self._improve(m[1].lower(), tips, payload)
            return
        new = extract_skill(text)
        if new:
            self._new_skill(new, payload)
        else:
            self.app.events.emit("learning_skill_failed", verdict="unreadable")

    def _when(self, payload: dict) -> str:
        return "today's request" if payload.get("day") == f"{now():%Y-%m-%d}" else "an earlier request"

    def _new_skill(self, text: str, payload: dict) -> None:
        from kurooto.core.tools import write_note_file
        from kurooto.modules.skills import all_skills, make, user_dir

        s = make(text, "", "learned")
        if s is None:
            self.app.events.emit("learning_skill_failed", verdict="not a skill")
            return
        have = {k: v for k, v in all_skills(self.app).items() if not v.internal}
        if s.name in have or any(similar(f"{s.name} {s.description}", f"{k} {v.description}") for k, v in have.items()):
            self.app.events.emit("learning_skill_skipped", why="duplicate")  # never a second skill for the same thing
            return
        skills = self.app.modules.get("skills")
        if s.name in skills.reserved():
            self.app.events.emit("learning_skill_skipped", why="a command's name")
            return
        body = stamp(text, s.name, payload.get("title", ""), f"{now():%Y-%m-%d}")
        f = user_dir(self.app) / s.name / "SKILL.md"
        try:
            write_note_file(f, body, create=True)
        except FileExistsError:
            self.app.events.emit("learning_skill_skipped", why="exists")
            return
        cid = self._record("skill", name=s.name, file=str(f), after=_sha(body), created=True, job=payload.get("job"))
        self.app.events.emit("learning_skill_learned", name=s.name)
        self.app.notify(
            f"Learned a skill: /{s.name}, from {self._when(payload)}. /skills {s.name} to see it.",
            kind="info",
            buttons=[[("Undo", f"lrn:{cid}:undo")]],
            why="learning.skill",
            about=s.name,
        )

    def _editable(self, name: str):
        """(the skill, its file to change, whether that file is a new copy of a shipped or add-on one), or None."""
        from kurooto.modules.skills import load_skill

        s = load_skill(self.app, name)
        if s is None or s.internal or not s.path:
            return None
        if s.source in ("yours", "prompt"):
            return s, Path(s.path), False
        skills = self.app.modules.get("skills")
        try:
            return s, Path(skills.customize(s.name)), True  # your own copy, which replaces the shipped one for you
        except Exception:
            return None

    def _change(self, name: str, new_text_of, kind: str, **fields) -> str | None:
        """Change a skill's file (new_text_of(old text) -> new text or None) with a before-copy. The change's id."""
        from kurooto.core.tools import write_note_file

        got = self._editable(name)
        if got is None:
            return None
        s, f, created = got
        old = f.read_text(encoding="utf-8")
        new = new_text_of(old)
        if not new or new.strip() == old.strip():
            if created:  # nothing to change after all: the copy goes again
                f.unlink(missing_ok=True)
                with contextlib.suppress(OSError):
                    f.parent.rmdir()
            return None
        before = None if created else self._keep_before(s.name, old)
        write_note_file(f, new)
        return self._record(kind, name=s.name, file=str(f), after=_sha(new), created=created, before=before, **fields)

    def _improve(self, name: str, tips: list[str], payload: dict) -> None:
        from kurooto.core.tools import add_to_section
        from kurooto.modules.remember import has_line, sensitive

        day = f"{now():%Y-%m-%d}"

        def edit(old: str) -> str | None:
            fresh = [t[:200] for t in tips[:5] if t and sensitive(t) != "credentials" and not has_line(old, t)]
            return add_to_section(old, LEARNED_HEAD, "\n".join(f"- {t} ({day})" for t in fresh)) if fresh else None

        cid = self._change(name, edit, "improve", job=payload.get("job"))
        if cid is None:
            self.app.events.emit("learning_skill_skipped", why="nothing new to add")
            return
        self.app.events.emit("learning_skill_improved", name=name)
        self.app.notify(
            f'Improved a skill: /{name} learned from {self._when(payload)} (under "{LEARNED_HEAD}"). /skills {name} '
            "to see it.",
            kind="info",
            buttons=[[("Undo", f"lrn:{cid}:undo")]],
            why="learning.skill",
            about=name,
        )

    # ----------------------------------------------------------------------------------------- corrections
    def heard(self, msg: Incoming, text: str) -> None:
        """A message that isn't a reply (from App.handle; it goes on as usual): "no, ...", "that's wrong", "next
        time ..." soon after a skill's answer corrects that skill."""
        if not self.part("corrections") or not CORRECTION.match(text or ""):
            return
        last = self._state().get("last_skill") or {}
        if last.get("name") and time.time() - float(last.get("at") or 0) < CORRECTION_WINDOW_S:
            self.corrected(last["name"], last.get("job") or "", text)

    def corrected(self, name: str, jid: str, text: str, replied: bool = False) -> str | None:
        """Your words about a skill's answer (replied: a reply to it, from modules/skills.py). If they may correct
        it, the second-look AI decides the lesson. The judgement's job id, or None."""
        if not self.part("corrections") or not self.app.is_on("skills"):
            return None
        if replied and not CORRECTING.search(text or "") and not CORRECTION.match(text or ""):
            return None  # an answer to the skill's question, or a follow-up: nothing to learn
        from kurooto.modules.skills import load_skill

        s = load_skill(self.app, name)
        if s is None or s.internal or not s.path:
            return None
        prev = self.app.jobs.get(jid) if jid else None
        try:
            current = Path(s.path).read_text(encoding="utf-8")
        except OSError:
            return None
        out = self.app.jobs.submit(
            LESSON.format(
                name=s.name,
                text=current[:12000],
                answer=str(prev.result or "")[-3000:] if prev else "(not kept)",
                said=str(text).strip()[:1500],
            ),
            title=f"A lesson for /{s.name}?",
            effort="low",
            quiet=True,
            then="learning.lesson",
            then_payload={"name": s.name, "base": _sha(current)},
            background=True,
            text_only=True,
            lane="chk",
            brain=self.check_brain(),
            why="learning.lesson",
        )
        with self._lock:
            st = self._state()
            st.pop("last_skill", None)  # one correction per answer
            self._save_state(st)
        self.app.events.emit("learning_correction", name=s.name, replied=replied)
        return out

    def _lesson_judged(self, job, result, payload: dict) -> None:
        if not result.ok:
            self.app.events.emit("learning_lesson_failed", verdict=str(result.verdict)[:20])
            return
        if not self.part("corrections"):
            return
        from kurooto.core.tools import add_to_section
        from kurooto.modules.remember import has_line, sensitive
        from kurooto.modules.skills import extract_skill, make

        name = str(payload.get("name") or "")
        text = str(result.text or "").strip()
        first = re.sub(r"^[\s*#>`_]+", "", text.split("\n", 1)[0] if text else "")
        m = re.match(r"(?i)lesson\s*:\s*(.+)", first)
        if m:
            lesson = re.sub(r"\s+", " ", m[1]).strip().strip('"')[:240]
            if not lesson or sensitive(lesson):
                self.app.events.emit("learning_lesson_none")
                return
            day = f"{now():%Y-%m-%d}"

            def edit(old: str) -> str | None:
                return None if has_line(old, lesson) else add_to_section(old, LESSONS_HEAD, f"- {lesson} ({day})")

            cid = self._change(name, edit, "lesson", lesson=lesson)
            said = f"Lesson for /{name}: {lesson}"
        elif re.match(r"(?i)rewrite\b", first) and extract_skill(text):
            new = extract_skill(text)

            def edit(old: str) -> str | None:
                if _sha(old) != payload.get("base") and payload.get("base"):
                    return None  # the skill changed since the correction: leave it
                fixed = re.sub(r"(?m)^name:.*$", f"name: {name}", new, count=1)
                if make(fixed, name, "x") is None or (old.lstrip().startswith("---") and not fixed.startswith("---")):
                    return None  # not a usable skill, or its header was lost
                if not 0.5 <= len(fixed) / max(1, len(old)) <= 2.0:  # careful: one step, not a new skill
                    return None
                return fixed

            cid = self._change(name, edit, "rewrite")
            said = f"Rewrote the step of /{name} that went wrong, after your correction."
        else:
            self.app.events.emit("learning_lesson_none")
            return
        if cid is None:
            self.app.events.emit("learning_lesson_none")
            return
        self.app.events.emit("learning_lesson", name=name)
        self.app.notify(
            f"{said} /skills {name} to see it.",
            kind="info",
            buttons=[[("Undo", f"lrn:{cid}:undo")]],
            why="learning.lesson",
            about=name,
        )

    # ------------------------------------------------------------------------------- worth remembering (retro)
    def picks_facts(self) -> int:
        """How many facts tonight's look back may keep (0: this part is off)."""
        return max(0, int(self.setting("remember_max") or 0)) if self.part("remember") else 0

    def chats(self, since: dt.datetime, budget: int = 8000) -> str:
        """What you asked or said to the AI since then, in your words (your own requests, not background work)."""
        parts = []
        for _jid, _title, prompt, _result, finished, lane, then in self.app.jobs.finished_since(since.timestamp()):
            if lane == "you" and not then:
                parts.append(f"[{dt.datetime.fromtimestamp(finished):%H:%M}] {asked(prompt)[:1500]}")
        return "\n".join(parts)[-budget:]

    def keep_facts(self, items) -> list[str]:
        """The facts the look back picked: each through Remember's rules into the how-to-help note, then one message
        with an Undo for each. What was kept."""
        from kurooto.modules.remember import PICKED, help_rel, keep

        n = self.picks_facts()
        if not n or not isinstance(items, list):
            return []
        kept: list[tuple[str, str]] = []
        for raw in items[: n * 2]:
            if len(kept) >= n:
                break
            fact = re.sub(r"\s+", " ", str(raw or "")).strip()
            if not fact or OTHERS.search(fact):
                continue
            status, line = keep(self.app, fact, via="lookback", section=PICKED)
            if status == "kept":
                kept.append((self._record("remember", line=line), line))
        if not kept:
            return []
        self.app.events.emit("learning_remembered", n=len(kept))
        lines = "\n".join(f"{i}. {line.rsplit(' (', 1)[0]}" for i, (_c, line) in enumerate(kept, 1))
        self.app.notify(
            f"Kept from today's chats and calls, in {help_rel(self.app)}:\n{lines}",
            kind="info",
            buttons=[
                [(f"Undo {i}" if len(kept) > 1 else "Undo", f"lrn:{c}:undo") for i, (c, _l) in enumerate(kept, 1)]
            ],
            why="learning.remember",
        )
        return [line for _c, line in kept]

    # ------------------------------------------------------------------------------------------------ undo
    def undo(self, cid: str) -> str:
        from kurooto.core.tools import write_note_file
        from kurooto.modules.remember import remove_line

        with self._lock:
            items = self.changes()
            c = next((x for x in items if x["id"] == cid), None)
            if c is None:
                return "That change is too old to undo here."
            if c.get("undone"):
                return "Undone already."
            if c["kind"] == "remember":
                ok = remove_line(self.app, c["line"])
                said = (
                    "Taken out of your how-to-help-me note."
                    if ok
                    else "That line isn't in your how-to-help-me note as I wrote it any more, so I left the note alone."
                )
            else:
                f = Path(c["file"])
                try:
                    cur = f.read_text(encoding="utf-8")
                except OSError:
                    return f"/{c['name']}'s file is gone already, so there's nothing to undo."
                if _sha(cur) != c.get("after"):
                    where = f" (the earlier version is in {c['before']})" if c.get("before") else ""
                    return f"/{c['name']} changed since, so I left it as it is{where}."
                if c.get("created"):
                    f.unlink()
                    with contextlib.suppress(OSError):
                        f.parent.rmdir()
                elif c.get("before"):
                    write_note_file(f, Path(c["before"]).read_text(encoding="utf-8"))
                said = {
                    "skill": f"Removed the skill /{c['name']}.",
                    "improve": f"/{c['name']} is back as it was.",
                    "lesson": f"/{c['name']} is back as it was.",
                    "rewrite": f"/{c['name']} is back as it was.",
                }.get(c["kind"], "Undone.")
                ok = True
            c["undone"] = now().isoformat(timespec="seconds")
            jsave(self.changes_file, items)
        self.app.events.emit("learning_undone", kind=c["kind"], ok=ok)
        return said

    def callbacks(self):
        return {"lrn": lambda ref, act: self.undo(ref) if act == "undo" else "unknown button"}

    # ---------------------------------------------------------------------------------- commands and tools
    def commands(self):
        return [
            Command(
                "history",
                "search past requests, calls and chats: /history lab report (or /history 7d ...)",
                self._history,
            ),
            Command("learned", "what it learned lately (skills, lessons, facts), each with Undo", self._learned),
        ]

    def _history(self, msg: Incoming, arg: str) -> str:
        if not self.setting("search"):
            return "Searching past requests is off: Settings → Learns from its own work → learning.search."
        m = re.match(r"\s*(\d{1,4})d\b\s*(.*)\Z", arg or "", re.S)
        days, words = (int(m[1]), m[2]) if m else (None, arg or "")
        if not words.strip():
            return "What should I look for? e.g. /history lab report, or /history 7d linear algebra"
        hits = self.index.search(words, days)
        self.app.events.emit("history_searched", hits=len(hits), via=msg.via)
        if not hits:
            return "Nothing found in past requests, calls or chats" + (f" from the last {days} days." if days else ".")
        return "\n\n".join(f"{h['when']} · {h['kind']} · {h['title']}\n{h['passage']}" for h in hits)

    def _learned(self, msg: Incoming, arg: str) -> str | None:
        items = [c for c in self.changes() if not c.get("undone")][-10:]
        if not items:
            return "Nothing learned lately. It learns from requests that take many steps and from your corrections."
        for c in reversed(items):
            what = {
                "skill": f"a new skill, /{c.get('name')}",
                "improve": f"tips for /{c.get('name')}",
                "lesson": f"a lesson for /{c.get('name')}: {c.get('lesson', '')}",
                "rewrite": f"a rewritten step of /{c.get('name')}",
                "remember": f"kept: {str(c.get('line', '')).rsplit(' (', 1)[0]}",
            }.get(c["kind"], c["kind"])
            msg.reply(f"{c['at'][:16].replace('T', ' ')}: {what}", buttons=[[("Undo", f"lrn:{c['id']}:undo")]])
        return None

    def agent_tools(self):
        if not self.setting("search"):
            return []
        return [
            Tool(
                "search_history",
                "Search the user's past AI requests and their answers, call transcripts and chats with the assistant "
                "(on this computer), by words. Returns when, what kind, a title and the matching passage.",
                self._tool_search,
                {"query": arg("the words to look for"), "days": arg("only the last N days (optional)")},
                ("query",),
                writes=False,
                hint="When they refer to something asked, said or done before, call search_history.",
            )
        ]

    def _tool_search(self, a: dict):
        m = re.search(r"\d+", str(a.get("days") or ""))
        hits = self.index.search(str(a.get("query") or ""), int(m[0]) if m else None)
        self.app.events.emit("history_searched", hits=len(hits), via="ai")
        return {"hits": hits} if hits else "Nothing found in past requests, calls or chats."

    # ------------------------------------------------------------------------------------------- the card
    def card(self) -> dict:
        from kurooto.core.space import human

        n, size = self.index.stats(), human(index_size(self.app))
        lines = [f"Search index: {n} past requests, calls and chats ({size}), kept on this computer."]
        if not self.app.is_on("skills"):
            lines.append("Skills is off: learned skills and lessons wait until it's on.")
        if not self.app.is_on("retro"):
            lines.append("The nightly look back is off: facts you state are picked up only while it's on.")
        done = [c for c in self.changes() if not c.get("undone")]
        if done:
            lines.append(f"Learned lately: {len(done)} change{'s' if len(done) != 1 else ''} (/learned lists them).")
        return {
            "lines": lines,
            "toggles": [{"id": k, "label": v, "on": bool(self.setting(k))} for k, v in PARTS.items()],
        }

    def card_action(self, act: str, value) -> str:
        if act not in PARTS:
            return "There's no such part."
        self.app.settings.set(f"learning.{act}", bool(value))
        self.app.events.emit("learning_part", part=act, on=bool(value))
        return f"{PARTS[act]}: {'on' if value else 'off'}."


def stamp(text: str, name: str, title: str, day: str) -> str:
    """A learned skill's file: its header gets learned: true, the request it came from and the date (and loses any
    internal: line: a skill you can type)."""
    text = text.lstrip("﻿").replace("\r\n", "\n")
    m = re.match(r"---\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", text, re.S)
    head, body = (m[1], m[2]) if m else ("", text)
    keep = [ln for ln in head.split("\n") if ln.strip() and not re.match(r"(?i)\s*(internal|learned\w*)\s*:", ln)]
    keep = [f"name: {name}" if re.match(r"(?i)\s*name\s*:", ln) else ln for ln in keep]
    if not any(re.match(r"(?i)\s*name\s*:", ln) for ln in keep):
        keep.insert(0, f"name: {name}")
    title = re.sub(r"\s+", " ", re.sub(r'["\\]', "", str(title or ""))).strip()[:80] or "a request"
    keep += ["learned: true", f'learned_from: "{title}"', f"learned_on: {day}"]
    return "---\n" + "\n".join(keep) + "\n---\n" + body.lstrip("\n").rstrip("\n") + "\n"


def old_entries(app: App, cutoff: float) -> int:
    """Index items older than cutoff (core/space.py)."""
    return History(app).old(cutoff) if index_file(app).exists() else 0


def prune(app: App, cutoff: float) -> int:
    mod = app.modules.get("learning")
    return (mod.index if mod is not None else History(app)).prune(cutoff)


def forget(app: App, lo: float, hi: float) -> int:
    """Index items from [lo, hi) go (core/retention.py)."""
    mod = app.modules.get("learning")
    return (mod.index if mod is not None else History(app)).forget(lo, hi)
