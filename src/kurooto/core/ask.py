"""Questions and approvals: any feature, background AI request or script on this computer can ask you something, and
act on the answer when it comes.

A question reaches you on Telegram (its choices as buttons, plus Later; reply to it to type an answer), on the desktop,
in the phone app, and on your next call. The first answer wins, wherever it came from. "Later" keeps it open for the
next call; "Nothing new" is understood as an answer that there's nothing to add. Unanswered questions expire (after
two days unless the asker said otherwise). An approval is a yes/no question (Approve / Deny) asked before anything
that needs your OK; the asker waits for it, and nothing happens without it.

    qid = app.ask.ask("Which chapter is the quiz on?", choices=["3", "4"], hook="study.quiz_topic", source="study")
    app.ask.hooks["study.quiz_topic"] = lambda q, answer: ...   # runs once, with the first answer

Each question is a small JSON file in the state folder (ask/<id>.json), kept ask.keep_days, else privacy.keep_days,
else 30 days after it's settled.
What you answered, where and how fast is recorded as events (question_asked, question_answered, question_later,
question_expired), which the weekly retro reads.
"""

from __future__ import annotations

import datetime as dt
import re
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.base import Incoming

register_defaults(
    "ask",
    {
        "expire_hours": 48,  # an unanswered question expires after this long, unless its asker said otherwise
        "keep_days": 0,  # answered and expired questions are forgotten after this many days (0: privacy.keep_days)
    },
)

KINDS = ("question", "approval")
OPEN = ("open", "later")
APPROVE, DENY = "Approve", "Deny"
NOTHING = "Nothing new"
_LATER = re.compile(r"^(l|later|ask (me )?later|(ask me )?on the next call|not now)$")
_NOTHING = re.compile(r"^(nothing( new| to add)?( today)?|skip|nothing new to add)$")
_YES = re.compile(r"^(yes|yep|yeah|y|ok|okay|sure|approve[ds]?|go ahead|do it|allow(ed)?)\b")
_NO = re.compile(r"^(no|nope|n|deny|denied|don'?t|do not|stop|cancel|reject(ed)?)\b")

Hook = Callable[[dict, str], Any]  # (the question, the answer text) -> optional short note for you


def _local(t: dt.datetime) -> dt.datetime:
    """A naive local time (what now() returns), from an aware or naive datetime."""
    return t.astimezone().replace(tzinfo=None, microsecond=0) if t.tzinfo else t.replace(microsecond=0)


def _when(q: dict, key: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(q[key]) if q.get(key) else None
    except ValueError:
        return None


class Ask:
    def __init__(self, app: App):
        self.app = app
        self.dir = app.paths.state / "ask"
        self.hooks: dict[str, Hook] = {"ask.ai": self._hook_ai}
        self._announced: dict[str, float] = {}  # approval id -> when a call was last told about it

    # ------------------------------------------------------------------------------------------- asking
    def ask(
        self,
        text: str,
        choices: list[str] | None = None,
        kind: str = "question",
        hook: str | None = None,
        hook_payload: dict | None = None,
        expires: dt.datetime | dt.timedelta | str | None = None,
        source: str = "",
        title: str | None = None,
        deliver: bool = True,
        why: str | None = None,
        about: str | None = None,
        item: str | None = None,
    ) -> str:
        """Ask now (Telegram, desktop, phone app; the next call) and return the question's id.

        kind "approval" gets the choices Approve / Deny unless you give others (e.g. Send / Edit / Discard). `hook`
        names a function in app.ask.hooks that runs once with the first answer (not on Later, not on expiry).
        `expires` is a datetime, a timedelta, or text like "2d", "6h", "tomorrow 9am"; None means the default (two
        days). `title` replaces the "Question" label. `why`, `about`, `item`: the envelope (core/calm.py): why it's
        asked (a reason id, or "asked" when it follows something you just did), what it's about, that item's id.
        """
        kind = kind if kind in KINDS else "question"
        text = str(text or "").strip()
        if not text:
            raise ValueError("a question needs some text")
        if kind == "approval" and not [c for c in choices or [] if str(c).strip()]:
            choices = [APPROVE, DENY]
        clean: list[str] = []
        for c in choices or []:
            c = str(c).strip()[:60]
            if c and c.lower() not in (x.lower() for x in clean) and c.lower() != "later":
                clean.append(c)
        q = {
            "id": "q" + uuid.uuid4().hex[:8],
            "text": text[:2000],
            "kind": kind,
            "choices": clean[:8],
            "source": str(source or ""),
            "title": title or "",
            "hook": hook or "",
            "hook_payload": hook_payload or {},
            "created": now().isoformat(),
            "ts": time.time(),  # orders questions asked within the same second
            "expires": self._expiry(expires).isoformat(),
            "status": "open",
            "answer": None,
            "via": None,
            "answered": None,
            "files": [],
            "msg": None,
            "why": why,
            "about": about,
            "item": item,
        }
        self._save(q)
        if deliver:
            self._set_msg(q["id"], self._deliver(q))
        self.app.events.emit(
            "question_asked", id=q["id"], kind=kind, source=q["source"], choices=len(q["choices"]), hook=q["hook"]
        )
        return q["id"]

    def approval(self, text: str, **kw) -> str:
        """ask(text, kind="approval", ...)."""
        return self.ask(text, kind="approval", **kw)

    def _expiry(self, e) -> dt.datetime:
        if isinstance(e, dt.datetime):
            return _local(e)
        if isinstance(e, dt.timedelta):
            return now() + e
        if isinstance(e, str) and e.strip():
            return parse_when(e)
        return now() + dt.timedelta(hours=float(self.app.settings.get("ask.expire_hours") or 48))

    def label(self, q: dict) -> str:
        return q.get("title") or ("Approval needed" if q["kind"] == "approval" else "Question")

    def buttons(self, q: dict) -> list:
        """Telegram buttons: each choice (an approval's side by side), then Later."""
        cs = [(c, f"ask:{q['id']}:{i}") for i, c in enumerate(q["choices"])]
        rows = [cs] if q["kind"] == "approval" and len(cs) <= 3 else [[b] for b in cs]
        return [*rows, [("Later", f"ask:{q['id']}:L")]]

    def _deliver(self, q: dict, why: str | None = None) -> Any:
        hint = "Tap an answer, or reply to this message to type one." if q["choices"] else "Reply to this to answer."
        return self.app.notify(
            f"{q['text']}\n\n{hint}",
            kind=q["kind"],
            title=self.label(q),
            buttons=self.buttons(q),
            map_kind="ask",
            map_ref=q["id"],
            urgent=q["kind"] == "approval",
            why=why or q.get("why"),
            about=q.get("about"),
            item=q.get("item"),
        )

    def resend(self, qid: str) -> bool:
        """Deliver an open question again (it gets new buttons; replies to either message answer it)."""
        q = self.get(qid)
        if not q or q["status"] not in OPEN:
            return False
        mid = self._deliver(q, why="asked")  # you asked to see it again
        if mid is not None:
            self._edit(q, "(asked again below)", retract=False)
            self._set_msg(qid, mid)
        return True

    def _set_msg(self, qid: str, mid) -> None:
        """Remember the Telegram message (to edit it later), without undoing an answer that came in meanwhile."""
        if mid is None:
            return
        with Lock(self.app.paths.state, "ask"):
            cur = self.get(qid)
            if cur:
                cur["msg"] = mid
                self._save(cur)

    # ------------------------------------------------------------------------------------------ reading
    def _file(self, qid: str):
        return self.dir / f"{re.sub(r'[^a-z0-9]', '', str(qid).lower())[:20] or '-'}.json"

    def _save(self, q: dict) -> None:
        jsave(self._file(q["id"]), q)

    def get(self, qid: str) -> dict | None:
        q = jload(self._file(qid))
        return q if isinstance(q, dict) and q.get("id") else None

    def all(self) -> list[dict]:
        out = []
        for f in sorted(self.dir.glob("q*.json")) if self.dir.is_dir() else []:
            q = jload(f)
            if isinstance(q, dict) and q.get("id"):
                out.append(q)
        return sorted(out, key=lambda q: (q.get("created") or "", q.get("ts") or 0))

    def pending(self, kind: str | None = None, source: str | None = None) -> list[dict]:
        """Open questions (including ones kept for later), oldest first. Overdue ones are expired on the way."""
        t, out = now(), []
        for q in self.all():
            if q.get("status") not in OPEN:
                continue
            exp = _when(q, "expires")
            if exp and exp < t:
                self._expire(q)
                continue
            if (kind is None or q["kind"] == kind) and (source is None or q.get("source") == source):
                out.append(q)
        return out

    def recent(self, since: dt.datetime | None = None, source: str | None = None) -> list[dict]:
        """Questions settled (answered or expired) since a time, oldest first; default the last 24 hours."""
        since = _local(since) if since else now() - dt.timedelta(days=1)
        out = []
        for q in self.all():
            done = _when(q, "answered") or _when(q, "expired_at")
            if done and done >= since and (source is None or q.get("source") == source):
                out.append(q)
        return out

    def public(self, q: dict) -> dict:
        """What the API, calls and the phone see of a question."""
        keys = "id text kind choices source title status answer via created answered expires".split()
        return {k: q.get(k) for k in keys}

    # ------------------------------------------------------------------------------------------ answers
    def answer(self, qid: str, text: str, via: str = "telegram", files: list[str] | None = None) -> dict:
        """Answer a question. The first answer wins: later ones get ok=False and say what the answer was.

        Returns the question (as public() shows it) plus "ok" (this call settled it, or kept it for later) and
        "note" (a short line to show you). "Later" keeps it open for the next call; "Nothing new" answers it.
        """
        via = str(via or "unknown")[:20]
        with Lock(self.app.paths.state, "ask"):
            q = self.get(qid)
            if not q:
                return {"id": qid, "ok": False, "note": "There's no such question (it may be old)."}
            exp = _when(q, "expires")
            if q["status"] in OPEN and exp and exp < now():
                self._expire(q, locked=True)
                q = self.get(qid) or q
            if q["status"] == "answered":
                return {**self.public(q), "ok": False, "note": f"Already answered: {q['answer']} (via {q['via']})."}
            if q["status"] == "expired":
                return {**self.public(q), "ok": False, "note": "That question expired; it's no longer needed."}
            raw = str(text or "").strip()
            low = re.sub(r"[.!\s]+$", "", raw.lower())
            if _LATER.match(low) or low.startswith("later ("):
                q.update(status="later", later_at=now().isoformat(), later_via=via)
                self._save(q)
                later = True
            else:
                later = False
                ans = self._normalise(q, raw, low, bool(files))
                if ans is None:
                    tip = (
                        f"{' or '.join(q['choices'])}?"
                        if q["kind"] == "approval"
                        else "Type an answer, or tap one of the buttons."
                    )
                    return {**self.public(q), "ok": False, "note": tip}
                q.update(
                    status="answered",
                    answer=ans,
                    via=via,
                    answered=now().isoformat(),
                    files=[str(f) for f in (files or [])],
                    nothing=ans == NOTHING,
                )
                self._save(q)
        if later:
            self.app.events.emit("question_later", id=q["id"], kind=q["kind"], source=q.get("source"), via=via)
            self._edit(q, "Later: I'll ask again on the next call (/q lists open questions).")
            return {**self.public(q), "ok": True, "note": "Kept for later."}
        created = _when(q, "created") or now()
        idx = q["choices"].index(q["answer"]) if q["answer"] in q["choices"] else None
        self.app.events.emit(
            "question_answered",
            id=q["id"],
            kind=q["kind"],
            source=q.get("source"),
            via=via,
            seconds=round((now() - created).total_seconds()),
            choice=idx,
            nothing=bool(q.get("nothing")),
        )
        calm = getattr(self.app, "calm", None)
        if calm is not None:  # (calm) answered, for the monthly look at what you rarely answer
            calm.touched(map_kind="ask", map_ref=q["id"])
        shown = q["answer"] + (f" + {len(q['files'])} file(s)" if q["files"] else "")
        self._edit(q, f"Answered: {shown[:300]} (via {via})")
        note = self._run_hook(q) or (f"{q['answer']}." if q["kind"] == "approval" else f"Got it: {shown[:120]}")
        return {**self.public(q), "ok": True, "note": note}

    def later(self, qid: str, via: str = "telegram") -> dict:
        return self.answer(qid, "later", via)

    def _normalise(self, q: dict, raw: str, low: str, has_files: bool) -> str | None:
        """The answer as stored: a choice when it names one, Approve / Deny for approvals, or the text itself."""
        for c in q["choices"]:
            if low == c.lower():
                return c
        if q["kind"] == "approval":  # never guessed: yes / no only map onto Approve / Deny
            if q["choices"] == [APPROVE, DENY]:
                return APPROVE if _YES.match(low) else DENY if _NO.match(low) else None
            n = int(low) if low.isdigit() else 0
            return q["choices"][n - 1] if 1 <= n <= len(q["choices"]) else None
        if low.isdigit() and q["choices"] and 1 <= int(low) <= len(q["choices"]):
            return q["choices"][int(low) - 1]  # typed numbers count from 1
        if _NOTHING.match(low):
            return NOTHING
        return raw[:4000] if raw else ("(files)" if has_files else None)

    def _run_hook(self, q: dict) -> str | None:
        name = q.get("hook")
        if not name:
            return None
        fn = self.hooks.get(name)
        if fn is None:  # its feature is off now; the answer is kept and the event says so
            self.app.events.emit("question_hook_missing", id=q["id"], hook=name)
            return None
        try:
            out = fn(dict(q), q["answer"])
            return out if isinstance(out, str) and out.strip() else None
        except Exception as e:
            self.app.events.emit("question_hook_failed", id=q["id"], hook=name, error=f"{type(e).__name__}: {e}"[:300])
            return None

    def _hook_ai(self, q: dict, answer: str) -> str | None:
        """Built-in hook "ask.ai": the answer starts an AI request. hook_payload: {"prompt": "... {answer} ...",
        "title": ..., "effort": ...}. "Nothing new" starts nothing."""
        p = q.get("hook_payload") or {}
        if q.get("nothing") or not p.get("prompt"):
            return None
        files = " ".join(q.get("files") or [])
        prompt = str(p["prompt"]).replace("{answer}", answer).replace("{files}", files).replace("{id}", q["id"])
        self.app.jobs.submit(prompt, title=str(p.get("title") or "Your answer")[:80], effort=p.get("effort", "auto"))
        return "Got it; working on it."

    # ---------------------------------------------------------------------------------------- expiring
    def sweep(self, payload: dict | None = None) -> int:
        """Expire overdue questions and forget settled ones after keep_days (privacy.keep_days unless ask.keep_days
        is set). Runs every 10 minutes."""
        from kurooto.core import retention

        n = len([q for q in self.all() if q.get("status") in OPEN]) - len(self.pending())
        keep = retention.days(self.app.settings, "ask")
        if keep:
            self.forget(0, (now() - dt.timedelta(days=keep)).timestamp())
        return n

    def forget(self, lo: float, hi: float) -> int:
        """Forget the questions settled (answered or expired) in [lo, hi); open ones stay. How many went."""
        n = 0
        for q in self.all():
            done = _when(q, "answered") or _when(q, "expired_at")
            if q.get("status") not in OPEN and done and lo <= done.timestamp() < hi:
                self._file(q["id"]).unlink(missing_ok=True)
                n += 1
        return n

    def expire(self, qid: str) -> bool:
        """Close an open question now (its asker stopped waiting): no answer will be taken for it."""
        q = self.get(qid)
        if not q or q.get("status") not in OPEN:
            return False
        self._expire(q)
        return (self.get(qid) or {}).get("status") == "expired"

    def _expire(self, q: dict, locked: bool = False) -> None:
        if not locked:
            with Lock(self.app.paths.state, "ask"):
                cur = self.get(q["id"])
                if not cur or cur.get("status") not in OPEN:
                    return
                q = cur
                q.update(status="expired", expired_at=now().isoformat())
                self._save(q)
        else:
            q.update(status="expired", expired_at=now().isoformat())
            self._save(q)
        created = _when(q, "created") or now()
        self.app.events.emit(
            "question_expired",
            id=q["id"],
            kind=q["kind"],
            source=q.get("source"),
            seconds=round((now() - created).total_seconds()),
        )
        self._edit(q, "(expired: no longer needed)")

    def start(self) -> None:
        self.app.scheduler.action("ask.sweep", self.sweep)
        self.app.scheduler.every("ask:sweep", "every 10m", "ask.sweep", module="ask", misfire="coalesce")

    # ------------------------------------------------------------------------------------------ Telegram
    def _edit(self, q: dict, line: str, retract: bool = True) -> None:
        """Show the outcome under the question on Telegram (its buttons go), and clear it on other channels."""
        retract = getattr(self.app.notifier, "retract", None) if retract else None
        if retract:
            try:
                retract("ask", q["id"])
            except Exception as e:
                self.app.events.emit("notify_failed", channel="retract", error=str(e)[:200])
        tg = self.app.modules.get("telegram")
        if not q.get("msg") or not tg or not self.app.is_on("telegram"):
            return
        api, chat = tg.api(), tg.setting("chat_id")
        if api and chat:
            try:
                api.edit(chat, q["msg"], f"{self.label(q)}: {q['text']}\n\n{line}")
            except Exception as e:
                self.app.events.emit("notify_failed", channel="telegram", error=f"edit: {e}"[:200])

    def button(self, ref: str, act: str) -> str:
        """A tapped button, "ask:<id>:<choice index | L>"."""
        if act == "L":
            return self.answer(ref, "later", "telegram")["note"]
        q = self.get(ref)
        if not q:
            return "There's no such question (it may be old)."
        try:
            choice = q["choices"][int(act)]
        except (ValueError, IndexError):
            return "That button is out of date."
        return self.answer(ref, choice, "telegram")["note"]

    def reply(self, msg: Incoming, ref: str) -> str:
        """You replied to a question on Telegram (text, a voice note, photos or files)."""
        rels = []
        for f in msg.files:
            try:
                rels.append(f.relative_to(self.app.workspace).as_posix())
            except ValueError:
                rels.append(str(f))
        return self.answer(ref, msg.text, msg.via, files=rels)["note"]

    def command(self, msg: Incoming, arg: str) -> str | None:
        """/q: open questions, each with its buttons; reply to one to answer it."""
        items = self.pending()
        if not items:
            return "No open questions."
        for q in items[:8]:
            when = _when(q, "created")
            head = f"{self.label(q)} ({when:%a %H:%M})" if when else self.label(q)
            later = " Kept for later." if q["status"] == "later" else ""
            mid = msg.reply(f"{head}: {q['text']}\n\nReply to answer.{later}", buttons=self.buttons(q))
            tg = self.app.modules.get("telegram")
            if mid is not None and msg.via == "telegram" and tg:
                tg.map_set(mid, "ask", q["id"])
        return f"{len(items) - 8} more; answer these first." if len(items) > 8 else None

    def status_line(self) -> str:
        n = len(self.pending())
        return f"Open questions: {n} (/q)" if n else ""

    # ----------------------------------------------------------------------------------------- calls
    def call_brief(self) -> dict:
        items = self.pending()
        if not items:
            return {}
        return {
            "open_questions": [
                {
                    "id": q["id"],
                    "kind": q["kind"],
                    "question": q["text"][:400],
                    **({"choices": q["choices"]} if q["choices"] else {}),
                    **({"kept_for_this_call": True} if q["status"] == "later" else {}),
                }
                for q in items[:10]
            ]
        }

    def call_tools(self) -> list:
        from kurooto.modules.calls.tools import Tool, arg

        return [
            Tool(
                "answer_question",
                "Record their answer to an open question (ids are in pending_items under open_questions). Use their "
                'own words, or the choice they picked. "later" keeps it for next time; "nothing new" is an answer.',
                lambda a: self.answer(str(a.get("id", "")), str(a.get("answer", "")), "call")["note"],
                {"id": arg("the question's id"), "answer": arg("their answer")},
                ("id", "answer"),
                offline="queue",
                hint="Ask the open_questions from pending_items naturally, one at a time, and save each answer with "
                "answer_question (approvals with answer_approval). Never answer one for them.",
            ),
            Tool(
                "answer_approval",
                "Record their decision on an approval: one of its choices (Approve or Deny unless pending_items lists "
                'others), or "later". Only after they clearly decided; never decide for them.',
                self._call_approval,
                {"id": arg("the approval's id"), "decision": arg('one of its choices, or "later"')},
                ("id", "decision"),
                offline="queue",
            ),
        ]

    def _call_approval(self, a: dict) -> str:
        q = self.get(str(a.get("id", "")))
        if q and q["kind"] != "approval":
            return "That's a question, not an approval: use answer_question."
        return self.answer(str(a.get("id", "")), str(a.get("decision", "")), "call")["note"]

    def agent_tools(self) -> list:
        """For unattended AI requests: ask you something; your answer starts a follow-up request."""
        from kurooto.modules.calls.tools import Tool, arg

        return [
            Tool(
                "ask_user",
                "Ask the user a short question you can't answer yourself (it reaches them on Telegram, the phone "
                "and their next call). Don't wait for it: their answer starts a new request with the `then` "
                "instructions, where {answer} is replaced by what they said. At most 3 open at a time.",
                self._ai_ask,
                {
                    "question": arg("the question, short and self-contained"),
                    "choices": arg('optional answers to offer as buttons, separated by "|", e.g. "yes|no"'),
                    "then": arg("what to do once they answer, as a full request; use {answer} for their answer"),
                },
                ("question", "then"),
            )
        ]

    def _ai_ask(self, a: dict) -> str:
        if len(self.pending(source="ai")) >= 3:
            return "There are already 3 questions from AI requests waiting for an answer; don't ask more now."
        then = str(a.get("then") or "").strip()
        if not then:
            return "Say what to do with the answer (then)."
        if "{answer}" not in then:
            then += "\n\nTheir answer: {answer}"
        try:
            qid = self.ask(
                str(a.get("question") or "")[:600],
                choices=[c for c in str(a.get("choices") or "").split("|") if c.strip()],
                hook="ask.ai",
                hook_payload={"prompt": then[:4000], "title": "Your answer"},
                source="ai",
            )
        except ValueError as e:
            return str(e)
        return f"Asked (question {qid}). Their answer will start a new request; you can finish now."

    def call_approvals(self, every_s: float = 3600) -> list[dict]:
        """Open approvals a call in progress hasn't been told about yet (the call page asks them, once an hour)."""
        t, out = time.monotonic(), []
        for q in self.pending(kind="approval"):
            last = self._announced.get(q["id"])
            if last is None or t - last > every_s:
                self._announced[q["id"]] = t
                out.append({"id": q["id"], "question": q["text"][:400]})
        return out
