"""Wrong button and test cases: what Kurooto got wrong, or didn't understand, becomes a test case, and a reviewed test
case can teach it your words for things.

A Wrong button sits under each reply to a plain-English request (and under the AI's answer to one). Tapping it, or
/wrong right after a reply, keeps that request as a case: the message, what Kurooto did with it, the time and the
settings that decided it. Every short request that no instant request understood (it went to the AI, or nowhere
with Chat off) is kept as a case too. Requests about health, money or passwords are never kept.

Once a month (a Sunday evening, `cases.review`) the look back shows the phrasings that came up most, each with
"Make it a test case". You then say what you meant, in words Kurooto already understands ("what's due"), or "the AI".
That makes it a test case. It also teaches the phrasing, "whats on my plate" now taken as "what's due", but only if
every test case that passed before still passes with it, and never for a request that sends, deletes, calls, rings
or approves anything (those always need their own words). /wrong <what you meant> does the same at once.

Learning from a rephrase (cases.learn_rephrased, on): when a short request nothing understood is followed within 3
minutes by you saying it again in words Kurooto does understand ("whats on my plate", then "what's due"), that pair
is noted on the case. The second time the same phrasing is followed by the same request, it's taught as above (only if
every test case that passed still passes, never for requests that send, delete, call, ring or approve), with a line
and Undo.

A taught phrasing is matched whole (case and punctuation aside) and goes first, before the usual patterns; the request
it stands for runs with today's time ("skip gym tomorrow" means tomorrow from now). Undo: /cases, Unlearn.

Everything stays on this computer, in Kurooto's state folder (state/cases/), out of backups, Profile sync and
`kurooto doctor --bundle`. Cases you didn't make test cases are forgotten after cases.keep_days, else
privacy.keep_days, else 30 days (/forget does it now). Events carry no text.
`kurooto cases` lists them; `kurooto cases export` writes the test cases as a pytest file that replays each one at its
own time and settings (read it before you share it); `kurooto cases check` runs them here.
"""

from __future__ import annotations

import datetime as dt
import pprint
import re
import sys
import threading
import uuid
from collections import Counter, OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import syncall
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.events import subscribe
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module
from kurooto.modules.text import QUESTION, tidy, too_complex

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.base import Intent

register_defaults(
    "cases",
    {
        "button": True,  # a Wrong button under replies to plain-English requests (/wrong works either way)
        "fallthroughs": True,  # keep short requests no instant request understood (they went to the AI)
        "keep_days": 0,  # cases you didn't make test cases are forgotten after this many days (0: privacy.keep_days)
        "review": "weekly sun 19:00",  # when the look back may show the phrasings that came up most...
        "review_days": 28,  # ...at most this often (about once a month)
        "review_max": 5,  # phrasings in one look back
        "learn": True,  # a test case may teach its phrasing (only if every test case that passed still passes)
        "learn_rephrased": True,  # the same not-understood phrasing, twice followed by the same request: learn it
        # 0.9.0: more places than Telegram and the terminal where requests are kept and Wrong works: "app" (the
        # phone app's chat, a Wrong button), "dashboard" (its chat), "voice" (saying "that's wrong" just after an
        # answer; your voice only). Remove one to leave it out
        "surfaces": ["app", "dashboard", "voice"],
        # 0.9.0: a Wrong on an answer that came from your notes or the concept graph is listed in Dreaming's morning
        # message as worth a look (nothing is changed in the notes)
        "to_dreaming": True,
    },
)
WRONG_SAID = re.compile(r"^(?:no,?\s+)?(?:that'?s|that\s+is|that\s+was|you'?re)\s+(?:wrong|not\s+right)\b", re.I)
SAID_S = 180  # "that's wrong" counts for an answer this recent
NOTES_TOOLS = {"search_notes", "graph_search", "concept_card", "graph_links", "read_note"}
# 0.9.0 (L82): one Wrong, several learners: name -> fn(app, case); each has its own switch and never raises out
WRONG_LISTENERS: dict = {}


def on_wrong(name: str, fn) -> None:
    """Register a learner that hears every Wrong (a case dict: id, did, job, tools; text only for those that keep the
    sensitive-words filter)."""
    WRONG_LISTENERS[name] = fn


# The learners' switches live with what they teach (registered here, where the Wrong comes from)
register_defaults("mind", {"trust": {"from_wrong": False}, "dream": {"from_wrong": True}})
register_defaults("retro", {"case_text": True})
register_defaults("learning", {"from_wrong": True})
NOT_ACTIONS = ("", "ai", "none", "sync", "other")


def _trust_learner(app: App, case: dict) -> None:
    """mind.trust.from_wrong (off): a Wrong on what a request did counts as a complaint against that kind of action,
    so Kurooto asks first before doing it on its own (mind/act.py; the scorekeeper keeps trust)."""
    did = str(case.get("did") or "")
    if not app.settings.get("mind.trust.from_wrong") or did in NOT_ACTIONS:
        return
    from kurooto.mind import act

    act.evidence(app, did, "complaint")


def _learning_learner(app: App, case: dict) -> None:
    """learning.from_wrong: a Wrong on a skill's answer is a correction of that skill (modules/learning.py), as
    "that's wrong" said just after it is."""
    if not app.settings.get("learning.from_wrong") or not app.is_on("learning") or not case.get("job"):
        return
    lm = app.modules.get("learning")
    last = (lm._state().get("last_skill") or {}) if lm is not None else {}  # noqa: SLF001
    if last.get("name") and last.get("job") == case["job"]:
        lm.corrected(last["name"], case["job"], case.get("note") or "That answer was wrong.")


def _notes_learner(app: App, case: dict) -> None:
    """cases.to_dreaming: a Wrong on an answer that used your notes or the concept graph is flagged for Dreaming's
    morning message (modules/dreaming.py: loose_ends), as an event with the tools' names only."""
    used = sorted(set(case.get("tools") or []) & NOTES_TOOLS)
    if app.settings.get("cases.to_dreaming") and used:
        app.events.emit("case_wrong_notes", case=case.get("id") or "", tools=",".join(used))


on_wrong("trust", _trust_learner)
on_wrong("learning", _learning_learner)
on_wrong("notes", _notes_learner)
# Dreaming (mind/dream.py: outcomes) and the look back (modules/retro.py: context) read the kept cases themselves

# Requests that are never learned from a phrasing: anything that sends, deletes, calls, rings or approves. Matched on
# a request's name and description (an add-on's too), so "call_me", "hold_calls", "quiz me ... by call" and the alarm
# keep needing their own words.
NEVER = re.compile(
    r"\b(?:send|sends|sent|sending|mail|mails|email|emails|message|messages|text|texts|post|posts|share|shares|"
    r"publish|delete|deletes|remove|removes|forget|erase|wipe|clear|cancel|cancels|call|calls|calling|ring|rings|"
    r"phone|approve|approves|approval|approvals|deny|pay|pays|buy|spend|order|alarm|alarms|wake)\b",
    re.I,
)
AI_WORDS = re.compile(r"^(?:(?:the\s+)?ai|(?:the\s+)?ai,?\s+as\s+now|as\s+now|(?:the\s+)?ai\s+is\s+right)$", re.I)
SHORT = 120  # longer requests that went to the AI are meant for it: not kept
MAX_CASES = 500
MAX_LEARNED = 200
DRAFTS = 100  # recent requests kept in memory (never on disk) until you tap Wrong
REPHRASE_S = 180  # a request understood this soon after one that wasn't: you said it again in other words
REPHRASE_TIMES = 2  # the same phrasing followed by the same request this often: learned
FILE = "cases/cases.json"  # in the state folder; backups skip state/cases (modules/backups.py)
SNAPSHOT_SKIP = re.compile(
    r"token|key|secret|password|chat|user|url|repo|email|account|workspace|folder|path|link|persona|remote|base", re.I
)
SAID = {
    "ai": "went to the AI",
    "none": "wasn't understood (Chat is off)",
    "sync": "synced everything",
    "other": "did something else",
    "repair": "got two readings to pick from",
}

_handling = threading.local()  # the request this thread is handling, for the routing's own "intent" event
_listening = False


def _heard(rec: dict) -> None:
    d = getattr(_handling, "draft", None)
    if d is not None and rec.get("kind") == "intent" and not d.get("did"):
        d["did"] = str(rec.get("name") or "")
        d["how"] = str(rec.get("via") or "pattern")


def _listen() -> None:
    global _listening
    if not _listening:
        subscribe(_heard)
        _listening = True


# ------------------------------------------------------------------------------------------- reading requests
def norm(text: str) -> str:
    """A phrasing as it's compared: no thanks/please, lower case, no punctuation, single spaces."""
    t = tidy(text or "").lower().replace("’", "'")
    return " ".join(re.sub(r"[^\w\s]", "", t).split())


def _intents(m) -> list[Intent]:
    try:
        return list(m.intents() or [])
    except Exception:
        return []


def _match(it: Intent, text: str):
    try:
        return it.match(text)
    except Exception:
        return None


def learnable(it: Intent) -> bool:
    """May a phrasing be taught for this request? Never for one that sends, deletes, calls, rings or approves."""
    words = f"{it.name} {it.description}".replace("_", " ").replace("-", " ")
    return not NEVER.search(words)


def find(learned: list[dict], plain: str) -> dict | None:
    key = norm(plain)
    return next((e for e in learned if e.get("phrase") == key), None) if key else None


def pattern(mods: list, text: str) -> tuple[Intent, dict] | None:
    """The instant request whose own pattern takes this text (questions only go to requests that answer them)."""
    plain = tidy(text)
    if not plain or too_complex(plain):
        return None
    asks = bool(QUESTION.search(plain))
    for m in mods:
        for it in _intents(m):
            if asks and not it.questions:
                continue
            slots = _match(it, plain)
            if slots is not None:
                return it, slots
    return None


def taught_target(mods: list, ex: dict) -> tuple[Intent, dict] | str | None:
    """What a taught phrasing does now: "ai", (the request, its slots read from the words it stands for), or None
    when that request is off, changed, or may not be learned."""
    if ex.get("intent") == "ai":
        return "ai"
    got = pattern(mods, ex.get("means") or "")
    if got is None or got[0].name != ex.get("intent") or not learnable(got[0]):
        return None
    return got


def route(app: App, text: str, learned: list[dict] | None = None) -> str:
    """Where a message would go, without doing anything: an instant request's name, "ai" (the AI you picked), "sync",
    "none" (nothing: Chat is off) or "/<command>". `learned`: taught phrasings, checked first as they are when you
    write. Add-ons' intent classifiers aren't asked (they can be slow); their requests' own patterns are."""
    text = (text or "").strip()
    if text.startswith("/"):
        return "/" + (text[1:].split(None, 1) or [""])[0].split("@")[0].lower()
    mods = app.enabled()
    plain = tidy(text)
    ex = find(learned or [], plain)
    if ex is not None:
        got = taught_target(mods, ex)
        if got is not None:
            return got if isinstance(got, str) else got[0].name
    got = pattern(mods, plain)
    if got is not None:
        return got[0].name
    if syncall.wanted(text):
        return "sync"
    return "ai" if text and app.is_on("chat") else "none"


# ------------------------------------------------------------------------------------------------ the store
class Store:
    """state/cases/cases.json: {"cases": {id: case}, "learned": [phrasing], "since", "last_review"}. Read and
    changed under a lock (the running Kurooto and `kurooto cases` may both write)."""

    def __init__(self, state_dir: Path):
        self.state = Path(state_dir)
        self.file = self.state / FILE
        self._cache: tuple[float, list] | None = None

    def load(self) -> dict:
        d = jload(self.file, {}) or {}
        d.setdefault("cases", {})
        d.setdefault("learned", [])
        return d

    def learned(self) -> list[dict]:
        """The taught phrasings (read again only when the file changed)."""
        try:
            mt = self.file.stat().st_mtime
        except OSError:
            return []
        if self._cache is None or self._cache[0] != mt:
            self._cache = (mt, list(self.load()["learned"]))
        return self._cache[1]

    def change(self, fn, keep_days: int = 30):
        """Run fn(data) under the lock, forget expired cases, save; returns what fn returned."""
        with Lock(self.state, "cases"):
            d = self.load()
            out = fn(d)
            self._prune(d, keep_days)
            jsave(self.file, d)
            self._cache = None
            return out

    def forget(self, lo: float, hi: float) -> int:
        """(retention) Forget the cases kept in [lo, hi) that you didn't make test cases. How many went."""

        def when(c: dict) -> float | None:
            try:
                return dt.datetime.fromisoformat(str(c.get("at") or "")).timestamp()
            except ValueError:
                return None

        with Lock(self.state, "cases"):
            d = self.load()
            gone = [
                k for k, c in d["cases"].items() if c.get("status") != "test" and lo <= (when(c) or float("nan")) < hi
            ]
            if gone:
                d["cases"] = {k: c for k, c in d["cases"].items() if k not in gone}
                jsave(self.file, d)
                self._cache = None
        return len(gone)

    @staticmethod
    def _prune(d: dict, keep_days: float) -> None:
        cut = (now() - dt.timedelta(days=keep_days)).isoformat() if keep_days and keep_days > 0 else ""
        cases = {k: c for k, c in d["cases"].items() if c.get("status") == "test" or str(c.get("at", "")) >= cut}
        if len(cases) > MAX_CASES:  # the oldest unreviewed go first
            new = sorted((c.get("at", ""), k) for k, c in cases.items() if c.get("status") != "test")
            for _, k in new[: len(cases) - MAX_CASES]:
                cases.pop(k, None)
        d["cases"] = cases
        d["learned"] = d["learned"][-MAX_LEARNED:]


# ----------------------------------------------------------------------------------------------- the feature
class Cases(Module):
    id = "cases"
    title = "Wrong button and test cases"
    description = (
        "A Wrong button on replies. What I got wrong, or sent to the AI, is kept as a test case, and once a month you "
        "can teach me your words for things."
    )
    requires = ("telegram",)
    privacy = (
        "Stays on this computer: in Kurooto's state folder, never in backups, Profile sync or the diagnostics zip. "
        "Cases you don't review are forgotten after 30 days."
    )

    def __init__(self, app: App):
        super().__init__(app)
        self.store = Store(app.paths.state)
        self._lock = threading.Lock()
        self._drafts: OrderedDict[str, dict] = OrderedDict()  # recent requests, in memory only
        self._jobs: OrderedDict[str, str] = OrderedDict()  # AI request id -> its case or draft
        self._last = ""  # the latest plain-English request on Telegram (/wrong marks it)
        self._last_voice = ""  # (0.9.0) the latest one said aloud ("that's wrong" marks it)
        _listen()
        if self._job_done not in app.jobs.watchers:  # (0.9.0) which tools an answer used, for Wrong's learners
            app.jobs.watchers.append(self._job_done)

    def surface(self, via: str) -> bool:
        """Requests from here are watched: Telegram and the terminal always, the rest by cases.surfaces."""
        return via in ("telegram", "terminal") or via in (self.setting("surfaces") or [])

    def _said_wrong(self, msg: Incoming, plain: str) -> bool:
        """(0.9.0) "that's wrong" said aloud just after an answer to something said aloud, in your voice: that
        request is marked Wrong. The words still go on as usual (to your AI)."""
        if not self.surface("voice") or msg.speaker not in ("", "owner") or not WRONG_SAID.match(plain):
            return False
        with self._lock:
            d = self._drafts.get(self._last_voice)
        if not d or not d.get("said"):
            return False
        try:
            age = (now() - dt.datetime.fromisoformat(d["at"])).total_seconds()
        except (KeyError, ValueError):
            return False
        if age > SAID_S:
            return False
        return self.wrong(d["id"], via="voice") is not None

    def _job_done(self, job, result, info) -> None:
        """An AI request this feature saw finished: the names of the tools it used, kept with its draft."""
        with self._lock:
            ref = self._jobs.get(getattr(job, "id", ""))
            d = self._drafts.get(ref) if ref else None
            if d is not None:
                d["tools"] = sorted({str(s.get("name") or "") for s in (info or {}).get("steps") or []} - {""})[:20]

    # ------------------------------------------------------------------------------------ while handling
    def watch(self, msg: Incoming, plain: str, mods: list):
        """Called for each message on its way to the instant requests: keeps it in memory, puts a Wrong button under
        the first reply, keeps it as a case if no instant request understood it, and returns what a taught
        phrasing says: (request, slots), "ai", or None."""
        text = (msg.text or "").strip()
        guest = msg.via == "voice" and msg.speaker not in ("", "owner")  # someone else's voice: nothing is kept
        if msg.via == "voice" and not guest:
            self._said_wrong(msg, plain)  # (0.9.0) "that's wrong": marked, and the words still go on as usual
        if msg.reply_to or msg.files or not plain or text.startswith("/") or not self.surface(msg.via) or guest:
            _handling.draft = None
            return None
        d = {
            "id": uuid.uuid4().hex[:8],
            "text": text[:2000],
            "via": msg.via,
            "at": now().isoformat(timespec="seconds"),
            "settings": self.snapshot(mods),
            "did": "",
            "how": "",
        }
        _handling.draft = d
        with self._lock:
            self._drafts[d["id"]] = d
            while len(self._drafts) > DRAFTS:
                self._drafts.popitem(last=False)
            if msg.via == "telegram":
                self._last = d["id"]
            elif msg.via == "voice":
                self._last_voice = d["id"]
        self._wrap(msg, d)
        ex = find(self.store.learned(), plain)
        if ex is None:
            return None
        got = taught_target(mods, ex)
        if got == "ai":
            d.update(did="ai", how="taught")
        return got

    def _wrap(self, msg: Incoming, d: dict) -> None:
        orig = msg.respond
        if orig is None:
            return

        def respond(text, buttons=None):
            first = not d.get("said")
            if first:
                d["said"] = str(text)[:300] or "-"
                _handling.draft = None
                self._replied(msg, d)
                if msg.via in ("telegram", "app", "dashboard") and self.setting("button", True):
                    buttons = [*(buttons or []), [("Wrong", f"wrong:{d['id']}:x")]]
            out = orig(text, buttons=buttons)
            if first and d.get("did") not in ("ai", "none", "sync", "other", "") and d.get("how") != "taught":
                self._rephrased(d)  # after the reply, so what was learned comes after the answer
            return out

        msg.respond = respond

    def _replied(self, msg: Incoming, d: dict) -> None:
        """The first reply: what was done is known now. Requests nothing understood become cases."""
        job = getattr(msg, "job", None)
        if job:
            d["job"] = job
            d["did"] = "ai"
            with self._lock:
                self._jobs[job] = d["id"]
                while len(self._jobs) > DRAFTS:
                    self._jobs.popitem(last=False)
        if not d.get("did"):
            d["did"] = "sync" if syncall.wanted(d["text"]) else "none" if not self.app.is_on("chat") else "other"
        if d["did"] in ("ai", "none") and d.get("how") != "taught" and self.setting("fallthroughs", True):
            if len(d["text"]) <= SHORT and not too_complex(tidy(d["text"])) and not self._sensitive(d["text"]):
                if not self._tested(d["text"]):  # a test case stands for it already
                    self._keep(d, "fallthrough")

    def _rephrased(self, d: dict) -> None:
        """d was understood: was it the request before it (kept, not understood, moments ago) said again? Noted on
        that case; the second time a phrasing is followed by the same request, it's learned (with Undo)."""
        if not self.setting("learn_rephrased", True) or not self.setting("learn", True):
            return
        with self._lock:
            ids = list(self._drafts)
        if d["id"] not in ids or ids.index(d["id"]) == 0:
            return
        p = self._drafts.get(ids[ids.index(d["id"]) - 1])
        if not p or p.get("via") != d.get("via") or p.get("did") not in ("ai", "none") or p.get("how") == "taught":
            return
        gap = (dt.datetime.fromisoformat(d["at"]) - dt.datetime.fromisoformat(p["at"])).total_seconds()
        if not 0 <= gap <= REPHRASE_S or norm(p["text"]) == norm(d["text"]):
            return
        data = self.store.load()
        if p["id"] not in data["cases"]:
            return  # not kept (long, sensitive, or a test case already stands for it)
        means, target = tidy(d["text"]), d["did"]

        def put(dd):
            if p["id"] in dd["cases"]:
                dd["cases"][p["id"]].update(rephrased=means[:300], rephrased_to=target)

        self.store.change(put, self._keep_days())
        key = norm(p["text"])
        times = sum(
            1
            for c in self.store.load()["cases"].values()
            if norm(c.get("text", "")) == key and c.get("rephrased_to") == target
        )
        self.app.events.emit("case_rephrased", intent=target, times=times)
        if times < REPHRASE_TIMES:
            return
        said, buttons = self.teach(p["id"], means)
        if not said.startswith("Learned"):
            return
        self.app.notify(
            f'You said "{_short(p["text"])}" and then "{_short(means)}" {times} times, so: {said}',
            kind="info",
            why="cases.rephrased",
            buttons=buttons,
        )

    def repaired(self, text: str, target: str, means: str, via: str = "telegram") -> None:
        """You picked one of two readings (core/repair.py): noted on a case for that phrasing. The REPHRASE_TIMES-th
        time the same phrasing is repaired to the same request, it's taught as above (only if every test case that
        passed still passes, never for requests that send, delete, call, ring or approve), with a line and Undo."""
        if not self.setting("learn", True) or self._sensitive(text) or too_complex(tidy(text)) or len(text) > SHORT:
            return
        d = {
            "id": uuid.uuid4().hex[:8],
            "text": text.strip()[:2000],
            "via": via,
            "at": now().isoformat(timespec="seconds"),
            "settings": self.snapshot(self.app.enabled()),
            "did": "repair",
        }
        self._keep(d, "repair", {"repaired_to": target, "means": tidy(means)[:300]})
        key = norm(text)
        times = sum(
            1
            for c in self.store.load()["cases"].values()
            if norm(c.get("text", "")) == key and c.get("repaired_to") == target and c.get("status") != "test"
        )
        self.app.events.emit("case_repaired", intent=target, times=times)
        got = pattern(self.app.enabled(), means)  # a phrasing is taught as words that name the request you picked
        if times < REPHRASE_TIMES or got is None or got[0].name != target:
            return
        said, buttons = self.teach(d["id"], means)
        if not said.startswith(("Learned", "Saved as a test case")):
            return
        self.app.notify(
            f'You picked "{_short(means)}" for "{_short(text)}" {times} times, so: {said}',
            kind="info",
            why="cases.repaired",
            buttons=buttons,
        )

    def expected(self, text: str) -> str | None:
        """What a test case says this phrasing should be (a request's name or "ai"), or None."""
        key = norm(text)
        cs = self.store.load()["cases"].values()
        return next((c["expect"] for c in cs if c.get("status") == "test" and norm(c["text"]) == key), None)

    def _tested(self, text: str) -> bool:
        key = norm(text)
        return any(c.get("status") == "test" and norm(c["text"]) == key for c in self.store.load()["cases"].values())

    @staticmethod
    def _sensitive(text: str) -> bool:
        from kurooto.modules.remember import sensitive

        return sensitive(text) is not None

    def snapshot(self, mods: list) -> dict:
        """The settings that decide where a message goes: the features that are on, the time zone, and your own
        values for the features with instant requests (sign-ins, chats, links and folders left out)."""
        own = self.app.settings.user()
        out: dict = {
            "modules": [m.id for m in mods],
            "you": {k: v for k, v in (own.get("you") or {}).items() if k in ("timezone", "language")},
        }
        for m in mods:
            sec = own.get(m.id)
            if isinstance(sec, dict) and sec and _intents(m):
                kept = {k: v for k, v in sec.items() if not SNAPSHOT_SKIP.search(k)}
                if kept:
                    out[m.id] = kept
        return out

    def _keep(self, d: dict, kind: str, extra: dict | None = None) -> dict:
        """A draft becomes a case on disk (or the case it is already gets `extra`)."""
        public = {k: v for k, v in d.items() if k not in ("how",)}

        def put(data):
            c = data["cases"].get(d["id"]) or {**public, "kind": kind, "status": "new", "wrong": False}
            c.update(extra or {})
            data["cases"][d["id"]] = c
            return dict(c)

        c = self.store.change(put, self._keep_days())
        self.app.events.emit("case_kept", kind=c["kind"], did=c.get("did", ""), wrong=bool(c.get("wrong")))
        return c

    # ------------------------------------------------------------------------------------------- Wrong
    def answer_buttons(self, job_id: str) -> list | None:
        """A Wrong button for the AI's answer to a request this feature saw."""
        with self._lock:
            ref = self._jobs.get(job_id)
        if not ref or not self.setting("button", True):
            return None
        return [[("Wrong", f"wrong:{ref}:x")]]

    def wrong(self, ref: str, note: str = "", via: str = "") -> dict | None:
        """Mark a request wrong: its case is kept (or made from the draft in memory). None if it's gone. Then every
        learner (WRONG_LISTENERS, 0.9.0) hears it."""
        with self._lock:
            d = self._drafts.get(ref)
        c = self.store.load()["cases"].get(ref)
        if d is None and c is None:
            return None
        base = dict(c or d)
        extra: dict = {"wrong": True, "wrong_at": now().isoformat(timespec="seconds")}
        if note:
            extra["note"] = note[:300]
        if base.get("job") and not base.get("answer"):
            j = self.app.jobs.get(base["job"])
            if j and j.result:
                extra["answer"] = j.result[:300]
        if c is not None and c.get("kind") == "fallthrough":
            extra["kind"] = "wrong"
        if via:
            extra["wrong_via"] = via
        if d is not None and d.get("tools"):
            extra["tools"] = d["tools"]
        kept = self._keep(base, "wrong", extra)
        self._heard_wrong(kept)
        return kept

    def _heard_wrong(self, c: dict) -> None:
        """One Wrong, to each learner (each checks its own switch). The case's text goes only where the sensitive-words
        filter lets it."""
        if not c:
            return
        case = {k: c.get(k) for k in ("id", "did", "job", "tools", "via", "at", "note")}
        if not self._sensitive(c.get("text") or ""):
            case["text"] = c.get("text") or ""
        for name, fn in list(WRONG_LISTENERS.items()):
            try:
                fn(self.app, case)
            except Exception as e:
                self.app.events.emit("cases_listener_failed", listener=name, error=type(e).__name__)

    def _button_wrong(self, ref: str, act: str) -> str:
        c = self.wrong(ref)
        if c is None:
            return "That request is too old to keep now (only the last 100 are kept in memory)."
        return "Kept as a case. It comes up in the monthly look back; /wrong <what you meant> teaches me now."

    def _cmd_wrong(self, msg: Incoming, arg: str) -> str | None:
        with self._lock:
            ref = self._last
        c = self.wrong(ref) if ref else None
        if c is None:
            return "Nothing to mark: /wrong works right after my reply to a plain-English request."
        if not arg.strip():
            return (
                f'Kept "{_short(c["text"])}" (it {self.did_text(c.get("did", ""))}). To teach me now: /wrong <how you '
                "would say it so I understand it>, or /wrong ai. Otherwise it comes up in the monthly look back."
            )
        text, buttons = self.teach(c["id"], arg.strip(), from_wrong=True)
        msg.reply(text, buttons=buttons)
        return None

    # ------------------------------------------------------------------------------------------ teaching
    def teach(self, cid: str, answer: str, from_wrong: bool = False) -> tuple[str, list | None]:
        """Your answer for a case: "the AI", or words I understand ("what's due"). It becomes a test case, and its
        phrasing is learned if every test case that passed still passes and the request may be learned."""
        data = self.store.load()
        c = data["cases"].get(cid)
        if c is None:
            return "That case is gone (cases you didn't review are kept for 30 days).", None
        said = _short(c["text"])
        raw = answer.strip().strip("\"'“”").strip()
        mods = self.app.enabled()
        got = None
        if AI_WORDS.match(raw.rstrip(".! ")):
            target, means = "ai", ""
        else:
            means = tidy(raw)
            if not means or too_complex(means):
                return "Say just one request, in a few words, or tap The AI.", self._ai_button(cid)
            if means.startswith("/"):
                return "Say it in words, not as a /command (or tap The AI).", self._ai_button(cid)
            got = pattern(mods, means)
            if got is None:
                if from_wrong:
                    self.store.change(lambda d: d["cases"].get(cid, {}).update(note=raw[:300]), self._keep_days())
                    return (
                        f'Kept with your note. I don\'t understand "{_short(means)}" either, so nothing is learned; '
                        "it comes up in the monthly look back. /help lists what I understand."
                    ), None
                return (
                    f'I don\'t understand "{_short(means)}" either. Try other words (/help lists what I understand), '
                    "or tap The AI.",
                    self._ai_button(cid),
                )
            target = got[0].name
        learned = [e for e in self.store.learned() if e.get("phrase") != norm(c["text"])]
        before = route(self.app, c["text"], self.store.learned())
        update = {"status": "test", "expect": target, "means": means, "reviewed": now().isoformat(timespec="seconds")}
        if got is not None and not learnable(got[0]):
            self._make_test(cid, update)
            return (
                f'Saved as a test case: "{said}" should be taken as "{got[0].description}". Requests that send, '
                f"delete, call, ring or approve are never learned from a phrasing, so it still {self.goes(before)}; "
                "say it the usual way.",
                None,
            )
        if before == target:
            self._make_test(cid, update)
            return f'Saved as a test case: "{said}" already {self.goes(target)}.', None
        if not self.setting("learn", True) or too_complex(tidy(c["text"])):
            self._make_test(cid, update)
            why = (
                "learning is off: cases.learn" if not self.setting("learn", True) else "too long to learn as a phrasing"
            )
            return f'Saved as a test case: "{said}" should {self._should(target)} ({why}).', None
        ex = {"phrase": norm(c["text"]), "intent": target, "means": means, "case": cid, "at": update["reviewed"]}
        cand = {**c, **update}
        ok, broken, passing = self.gate(cand, learned + [ex])
        if not ok:
            self._make_test(cid, update)
            first = broken[0] if broken else None
            why = (
                f"it would break {len(broken)} other test case{'s' if len(broken) != 1 else ''}, for example "
                f'"{_short(first["text"])}" (it should {self._should(first["expect"])})'
                if first
                else "it still wouldn't pass"
            )
            return f"Saved as a test case, but not learned: {why}.", None

        def put(d):
            d["cases"].setdefault(cid, c).update(update, learned=True)
            d["learned"] = [e for e in d["learned"] if e.get("phrase") != ex["phrase"]] + [ex]
            _drop_twins(d, cid)

        self.store.change(put, self._keep_days())
        self.app.events.emit("case_learned", intent=target, tests=passing)
        return (
            f'Learned: "{said}" is now {self._taken(target, means)}. All {passing} test case'
            f"{'s' if passing != 1 else ''} that passed still pass.",
            [[("Undo", f"case:{cid}:unlearn")]],
        )

    def _make_test(self, cid: str, update: dict) -> None:
        def put(d):
            if cid in d["cases"]:
                d["cases"][cid].update(update)
                _drop_twins(d, cid)

        self.store.change(put, self._keep_days())
        self.app.events.emit("case_reviewed", expect="ai" if update["expect"] == "ai" else "request")

    def gate(self, case: dict, learned: list[dict]) -> tuple[bool, list[dict], int]:
        """Would these taught phrasings keep every test case that passes now passing, and make `case` pass?
        Returns (ok, the test cases it would break, how many pass with it)."""
        now_ = self.suite()
        after = self.suite(learned, extra=[case])
        was = {r["id"] for r in now_["pass"]}
        broken = [r for r in after["fail"] if r["id"] in was]
        ok = not broken and any(r["id"] == case["id"] for r in after["pass"])
        return ok, broken, len(after["pass"])

    def suite(self, learned: list[dict] | None = None, extra: list[dict] | None = None) -> dict:
        """Every test case (and taught phrasing), routed as now: {"pass": [...], "fail": [...], "skip": [...]}; each
        row has id, text, expect and got. Skipped: the request it expects belongs to a feature that's off."""
        learned = self.store.learned() if learned is None else learned
        mods = self.app.enabled()
        offered = {it.name for m in mods for it in _intents(m)} | {"ai", "none", "sync"}
        tests = {
            c["id"]: c for c in self.store.load()["cases"].values() if c.get("status") == "test" and c.get("expect")
        }
        for c in extra or []:
            tests[c["id"]] = c
        mine = {e.get("case") for e in learned}
        rows = [
            {"id": c["id"], "text": c["text"], "expect": c["expect"], "taught": c["id"] in mine} for c in tests.values()
        ]
        rows += [
            {"id": f"taught:{e.get('case', '')}", "text": e["phrase"], "expect": e["intent"], "taught": True}
            for e in learned
            if not any(r["id"] == e.get("case") for r in rows)
        ]
        out: dict = {"pass": [], "fail": [], "skip": []}
        for r in rows:
            if r["expect"] not in offered:
                out["skip"].append(r)
                continue
            r["got"] = route(self.app, r["text"], learned)
            out["pass" if r["got"] == r["expect"] else "fail"].append(r)
        return out

    def unlearn(self, cid: str) -> str:
        def put(d):
            before = len(d["learned"])
            d["learned"] = [e for e in d["learned"] if e.get("case") != cid]
            if cid in d["cases"]:
                d["cases"][cid]["learned"] = False
            return before - len(d["learned"])

        if not self.store.change(put, self._keep_days()):
            return "Already unlearned."
        self.app.events.emit("case_unlearned")
        return "Unlearned; the test case stays (/cases)."

    # ------------------------------------------------------------------------------------- the look back
    def start(self) -> None:
        self.every("review", self.setting("review") or "weekly sun 19:00", lambda p: self.review())

        def since(d):
            d.setdefault("since", now().isoformat(timespec="seconds"))

        self.store.change(since, self._keep_days())

    def groups(self) -> list[dict]:
        """Cases waiting for review, by phrasing, most common first (Wrong taps count first); phrasings that are a test
        case or taught already are left out."""
        data = self.store.load()
        done = {norm(c["text"]) for c in data["cases"].values() if c.get("status") == "test"}
        done |= {e.get("phrase") for e in data["learned"]}
        by: dict[str, list[dict]] = {}
        for c in data["cases"].values():
            key = norm(c["text"])
            if c.get("status") != "test" and key and key not in done:
                by.setdefault(key, []).append(c)
        out = []
        for key, cs in by.items():
            cs.sort(key=lambda c: c.get("at", ""))
            wrong = sum(1 for c in cs if c.get("wrong"))
            out.append({"phrase": key, "case": cs[-1], "count": len(cs), "wrong": wrong})
        out.sort(key=lambda g: (-g["wrong"], -g["count"], g["case"].get("at", "")))
        return out

    def review(self, force: bool = False) -> int:
        """The look back's part: the phrasings that came up most, with Make it a test case. Once in review_days."""
        data = self.store.load()
        last = data.get("last_review") or data.get("since")
        days = int(self.setting("review_days") or 28)
        if not force and last and (now().date() - dt.datetime.fromisoformat(last).date()).days < days:
            return 0  # by calendar days, so a Sunday-evening review isn't put off a week by minutes
        rows = [g for g in self.groups() if force or g["wrong"] or g["count"] >= 2]
        rows = rows[: int(self.setting("review_max") or 5)]
        if not rows:
            return 0
        lines = [
            "Look back: what I got wrong or sent to the AI lately. Make one a test case and tell me what you meant; "
            "I learn it only if every test case still passes."
        ]
        buttons = []
        for i, g in enumerate(rows, 1):
            times = "once" if g["count"] == 1 else f"{g['count']} times"
            how = self.did_text(g["case"].get("did", ""))
            how = f"you tapped Wrong; it {how}" if g["wrong"] else how
            lines.append(f'{i}. "{_short(g["case"]["text"])}" ({times}; {how})')
            label = "Make it a test case" if len(rows) == 1 else f"Make {i} a test case"
            buttons.append([(label, f"case:{g['case']['id']}:test")])
        self.app.notify("\n".join(lines), kind="info", title="Look back", buttons=buttons, why="cases.review")
        self.store.change(lambda d: d.update(last_review=now().isoformat(timespec="seconds")), self._keep_days())
        self.app.events.emit("cases_review", shown=len(rows))
        return len(rows)

    def _ask_meaning(self, cid: str) -> str:
        c = self.store.load()["cases"].get(cid)
        if c is None:
            return "That case is gone."
        self.app.notify(
            f'What should "{_short(c["text"])}" do? Reply to this with words I already understand for it (for example '
            f'"what\'s due this week"), or tap The AI. Now it {self.did_text(c.get("did", ""))}.',
            kind="info",
            title="Test case",
            buttons=self._ai_button(cid),
            map_kind="case",
            map_ref=cid,
            why="asked",
        )
        return "Reply to my message with what you meant."

    def _ai_button(self, cid: str) -> list:
        return [[("The AI", f"case:{cid}:ai")]]

    # ----------------------------------------------------------------------------- Telegram and buttons
    def commands(self):
        return [
            Command(
                "wrong",
                "my last reply was wrong: keep it as a case (/wrong <what you meant> teaches me)",
                self._cmd_wrong,
            ),
            Command(
                "cases",
                "test cases and the phrasings you taught me (/cases review: the look back now)",
                self._cmd_cases,
            ),
        ]

    def help(self):
        return ["/wrong [what you meant], /cases, /cases review"]

    def callbacks(self):
        return {"wrong": self._button_wrong, "case": self._button_case}

    def replies(self):
        return {"case": self._reply}

    def _reply(self, msg: Incoming, ref: str) -> str | None:
        text, buttons = self.teach(ref, msg.text)
        msg.reply(text, buttons=buttons)
        return None

    def _button_case(self, ref: str, act: str) -> str:
        if act == "test":
            return self._ask_meaning(ref)
        if act == "ai":
            text, buttons = self.teach(ref, "the AI")
            self.app.notify(text, kind="info", title="Test case", buttons=buttons, why="asked")
            return _short(text, 180)
        if act == "unlearn":
            return self.unlearn(ref)
        return "ok"

    def _cmd_cases(self, msg: Incoming, arg: str) -> str | None:
        if arg.strip().lower() == "review":
            n = self.review(force=True)
            return None if n else "Nothing is waiting for review."
        data = self.store.load()
        r = self.suite()
        waiting = sum(1 for c in data["cases"].values() if c.get("status") != "test")
        keep = self._keep_days()
        head = (
            f"Test cases: {len(r['pass']) + len(r['fail']) + len(r['skip'])} ({len(r['pass'])} pass, "
            f"{len(r['fail'])} fail, {len(r['skip'])} for features that are off). Waiting for review: {waiting} "
            f"(kept {f'{keep:g} days' if keep else 'until you /forget them'}). `kurooto cases` on your computer "
            "lists and exports them."
        )
        learned = data["learned"]
        if not learned:
            return head + "\nNo phrasings taught yet."
        msg.reply(head + f"\nPhrasings you taught me ({len(learned)}):")
        for e in learned[-15:]:
            msg.reply(
                f'"{e["phrase"]}" is taken as {self._taken(e["intent"], e.get("means", ""))}',
                buttons=[[("Unlearn", f"case:{e.get('case', '')}:unlearn")]],
            )
        return None

    # ------------------------------------------------------------------------------------- health check
    def health_check(self):
        from kurooto.core.health import Check

        def probe(net: bool):
            if not self.store.learned():
                return True, "nothing taught yet"
            bad = [r for r in self.suite()["fail"] if r.get("taught")]
            if bad:
                n = len(bad)
                return False, f"{n} phrasing{'s' if n != 1 else ''} you taught no longer work{'s' if n == 1 else ''}"
            return True, f"{len(self.store.learned())} taught phrasings work"

        return Check(
            "cases",
            "Phrasings you taught",
            module=self.id,
            probe=probe,
            help="/cases shows them; Unlearn one, or teach it again",
        )

    # ------------------------------------------------------------------------------------------ helpers
    def _keep_days(self) -> float:
        from kurooto.core import retention

        return retention.days(self.app.settings, "cases")

    def _describe(self, name: str) -> str:
        for m in self.app.enabled():
            for it in _intents(m):
                if it.name == name:
                    return it.description
        return ""

    def did_text(self, did: str) -> str:
        """What happened to a request, after "it": went to the AI, was taken as "what's due"."""
        if not did:
            return "did something"
        if did in SAID:
            return SAID[did]
        if did.startswith("/"):
            return f"ran {did}"
        return f'was taken as "{self._describe(did) or did}"'

    def goes(self, target: str) -> str:
        """Where a request goes now, after "it": goes to the AI, is taken as "what's due"."""
        if target == "ai":
            return "goes to the AI"
        if target in SAID or target.startswith("/"):
            return self.did_text(target)
        return f'is taken as "{self._describe(target) or target}"'

    def _should(self, target: str) -> str:
        return "go to the AI" if target == "ai" else f'be taken as "{self._describe(target) or target}"'

    def _taken(self, target: str, means: str) -> str:
        if target == "ai":
            return "sent to the AI"
        return f'taken as "{means}"' if means else f'taken as "{self._describe(target) or target}"'


def _short(text: str, n: int = 80) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _drop_twins(d: dict, cid: str) -> None:
    """Other unreviewed cases with the same phrasing go: the test case stands for them."""
    key = norm(d["cases"].get(cid, {}).get("text", ""))
    for k in [k for k, c in d["cases"].items() if k != cid and c.get("status") != "test" and norm(c["text"]) == key]:
        d["cases"].pop(k, None)


# ------------------------------------------------------------------------------ `kurooto cases` and the export
HEADER = '"""Test cases kept by Kurooto ('  # an earlier export starts with it: only those are written over
EXPORT = '''"""Test cases kept by Kurooto ({n}), exported {when} with `kurooto cases export`.

Each one replays a message you sent, at its own time and with the settings you had then, and checks where it goes on
this version of Kurooto: an instant request by its name, "ai" (the AI you picked), "none" (nothing understood it with
Chat off) or "sync". Put this file in a Kurooto checkout's tests/ folder and run pytest. Phrasings you taught your own
Kurooto aren't used: a case that only passes with one is a pattern Kurooto could learn for everyone.

They hold what you typed and some of your settings: read them before you share this file.
"""

import pytest

from kurooto.modules.cases import replay

CASES = {cases}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case, tmp_path, monkeypatch):
    if not case.get("expect"):
        pytest.skip("not reviewed yet: set expect to an instant request's name, or 'ai'")
    assert replay(case, tmp_path, monkeypatch) == case["expect"]
'''
EXPORTED = ("id", "kind", "text", "at", "settings", "did", "expect", "means", "note")


def export_text(cases: list[dict], when: str | None = None) -> str:
    rows = [{k: c.get(k) for k in EXPORTED} for c in cases]
    body = pprint.pformat(rows, width=116, sort_dicts=False)
    return EXPORT.format(n=len(rows), when=when or now().strftime("%Y-%m-%d"), cases=body)


def replay(case: dict, home, monkeypatch) -> str:
    """Where a case's message goes on this version: a fresh Kurooto in `home`, the case's settings, its clock (every
    `now` Kurooto's code reads), without taught phrasings. For the exported tests."""
    from kurooto.app import App
    from kurooto.core import clock

    monkeypatch.setenv("KUROOTO_HOME", str(home))
    at = dt.datetime.fromisoformat(case["at"]).replace(tzinfo=None)
    real = clock.now
    for name, mod in list(sys.modules.items()):
        if name.startswith("kurooto") and getattr(mod, "now", None) is real:
            monkeypatch.setattr(mod, "now", lambda: at)
    app = App()
    try:
        for section, values in (case.get("settings") or {}).items():
            if section == "modules":
                app.settings.set("modules.enabled", [m for m in values if m in app.modules])
            elif isinstance(values, dict):
                for k, v in values.items():
                    app.settings.set(f"{section}.{k}", v)
        return route(app, case["text"])
    finally:
        app.close()


def list_text(data: dict) -> str:
    cases = sorted(data["cases"].values(), key=lambda c: c.get("at", ""), reverse=True)
    if not cases and not data["learned"]:
        return 'No cases yet. Turn on "Wrong button and test cases", then tap Wrong under a reply, or say /wrong.'
    lines = []
    tests = [c for c in cases if c.get("status") == "test"]
    rest = [c for c in cases if c.get("status") != "test"]
    if tests:
        lines.append(f"Test cases ({len(tests)}):")
        lines += [
            f"  {c['id']}  {c.get('at', '')[:16].replace('T', ' ')}  expect {c.get('expect')}"
            f"{' (taught)' if c.get('learned') else ''}  {_short(c['text'], 60)!r}"
            for c in tests
        ]
    if rest:
        kinds = Counter(c.get("kind") for c in rest)
        lines.append(
            f"Waiting for review ({len(rest)}: {kinds.get('wrong', 0)} wrong, {kinds.get('fallthrough', 0)} not "
            "understood):"
        )
        lines += [
            f"  {c['id']}  {c.get('at', '')[:16].replace('T', ' ')}  {c.get('kind', ''):11}  did {c.get('did') or '?'}"
            f"  {_short(c['text'], 60)!r}"
            for c in rest[:40]
        ]
    if data["learned"]:
        lines.append(f"Phrasings taught ({len(data['learned'])}):")
        lines += [
            f"  {e.get('case', '')}  {e['phrase']!r} -> {e['intent']}"
            + (f" ({e['means']!r})" if e.get("means") else "")
            for e in data["learned"]
        ]
    return "\n".join(lines)


def cli(action: str, ref: str = "", out: str = "", everything: bool = False) -> int:
    """`kurooto cases [list|check|export|forget]`."""
    from kurooto.core.config import Settings
    from kurooto.core.paths import paths

    p = paths().ensure()
    from kurooto.core import retention

    keep = retention.days(Settings(p.config / "settings.json"), "cases")
    store = Store(p.state)
    data = store.load()
    if action in ("", "list"):
        print(list_text(data))
        return 0
    if action == "export":
        cases = sorted(data["cases"].values(), key=lambda c: c.get("at", ""))
        cases = [c for c in cases if everything or c.get("status") == "test"]
        if not cases:
            print("No test cases to export yet (--all exports the ones waiting for review too).")
            return 1
        dest = Path(out or "test_kurooto_cases.py").expanduser().resolve()
        if dest.exists() and not dest.read_text(encoding="utf-8", errors="replace").startswith(HEADER):
            print(f"{dest} exists and isn't an earlier export; pick another file with --out.")
            return 1
        dest.write_text(export_text(cases), encoding="utf-8")
        print(
            f"Wrote {len(cases)} case{'s' if len(cases) != 1 else ''} to {dest}. They hold what you typed: read the "
            "file before you share it."
        )
        return 0
    if action == "check":
        from kurooto.app import App

        app = App()
        try:
            m = app.modules.get("cases")
            r = m.suite() if m is not None else {"pass": [], "fail": [], "skip": []}
        finally:
            app.close()
        for row in r["fail"]:
            print(f"FAIL {row['id']}  {_short(row['text'], 60)!r}: expected {row['expect']}, got {row['got']}")
        print(f"{len(r['pass'])} pass, {len(r['fail'])} fail, {len(r['skip'])} skipped (their feature is off).")
        return 1 if r["fail"] else 0
    if action == "forget":
        if not ref:
            print("Usage: kurooto cases forget <id>|all")
            return 2

        def drop(d):
            if ref == "all":
                n = len(d["cases"]) + len(d["learned"])
                d["cases"], d["learned"] = {}, []
                return n
            n = int(d["cases"].pop(ref, None) is not None)
            left = [e for e in d["learned"] if e.get("case") != ref]
            n += len(d["learned"]) - len(left)
            d["learned"] = left
            return n

        n = store.change(drop, keep)
        print(f"Forgot {n}." if n else f"No case {ref}.")
        return 0 if n else 1
    print(f"Unknown: {action}")
    return 2
