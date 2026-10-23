"""Check my draft: send a draft before you hand it in (a photo of a proof, a PDF, a .tex derivation, an essay, accounts
working, code) with "check this" as the caption, or /check, and your AI marks what to look at: gaps, unclear steps,
errors and missing justification, each pointing at a line (L12-14) or a place on the page. It never rewrites the work
or gives a solution: a comment that would give the fix away is left out.

    a file with the caption "check this" (or "check my proof for la", "/check la the induction step")
    "check this" just after you sent the file (Telegram, or a file shared from the phone app)
    /check la ~/essay.md      in the dashboard's chat or `kurooto ask`, a file on this computer

The course is guessed like other features do (named in the message or the file's name, the file's folder, the class
going on or just over, your only subject) and asked when unclear. Its AI policy (/subject policy la allowed|hints|off,
or the dashboard's Study pane) turns the check down (hints: only where each problem is, never how to fix it) or off.
Notes that are checked (a lecture note, or what the AI says are notes) also get the comments in a Kurooto block in the
matching lecture note (drafts.note_block); nothing of yours in it changes.

The draft goes to the AI you picked; a text file goes in numbered line by line, so comments can name lines.
"""

from __future__ import annotations

import datetime as dt
import re
import time
import uuid
from pathlib import Path

from kurooto import providers
from kurooto.core import graphwrite, layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "drafts",
    {
        "max_comments": 15,  # at most this many comments on one draft
        "note_block": True,  # notes that are checked: the comments also go in a block in the matching lecture note
        "recent_minutes": 15,  # "check this" after you sent a file checks that file if it came this recently
    },
)

CHECK = re.compile(
    r"^\s*(?:(?:please|pls|hey|ok|so|can you|could you|would you|kurooto,?)\s+)*(?:check|review|mark|look over|go "
    r"over|proofread)\s+(?P<what>this|that|it|these|my\s+(?P<mine>draft|attempt|proof|essay|code|working|workings|"
    r"derivation|answer|solution|notes?|assignment|homework|program|script|report|accounts|lab report|write-?up))"
    r"\b(?P<rest>.*)$",
    re.I | re.S,
)
TEXT_TYPES = {
    ".tex", ".md", ".txt", ".rmd", ".qmd", ".py", ".r", ".jl", ".m", ".c", ".cc", ".cpp", ".h", ".hpp", ".java",
    ".js", ".ts", ".rs", ".go", ".sh", ".csv", ".sql", ".hs", ".ml", ".scala", ".kt", ".swift", ".f90", ".bib",
}  # fmt: skip
OTHER_TYPES = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif", ".docx", ".odt", ".rtf", ".ipynb"}
MAX_TEXT = 60_000  # characters of a text file numbered into the request; past that it goes as a file
LABEL = {"gap": "gap", "unclear": "unclear", "error": "error", "justify": "needs a reason"}
COMMENT = re.compile(
    r"^\s*[-*•]\s*(?P<where>[^|\n]{1,90}?)\s*\|\s*(?P<cat>gap|unclear|error|justify|justification|missing "
    r"justification)\s*\|\s*(?P<what>\S.*?)\s*$",
    re.I | re.M,
)
# a comment that hands over the fix instead of pointing at the problem: left out
REWRITE = re.compile(
    r"```|\\begin\{(?:align|equation|proof)|\b(?:replace (?:it |this |that |line \S+ |L\d+ )?with|should read|"
    r"rewrite (?:it|this|that) as|corrected (?:version|line|code|proof)|fixed (?:version|code)|"
    r"here(?:'s| is) (?:the|a) (?:fix|corrected|correct)|the (?:correct|right|final) answer is|"
    r"change (?:it|this|that) to)\b",
    re.I,
)
LONG = {"allowed": 360, "hints": 140, None: 360}  # a comment's length at most, by the course's AI policy
POLICY_WORDS = {
    "allowed": "AI help allowed",
    "hints": "hints only: say where each problem is and its kind, never how to fix it",
    None: "not set (treat it as allowed)",
}
NOT_FOR = "Not for a course"


def wants(text: str) -> bool:
    """A request to check a draft: "check this", "can you check my proof for la" (not "check this out")."""
    m = CHECK.match(text or "")
    return bool(m) and not re.match(r"\s*out\b", m["rest"], re.I)


def parse_check(text: str) -> dict:
    """The AI's answer as {kind, note, summary, comments: [(where, cat, what)]} (or {unreadable} / {refused}); {} if it
    isn't in the form asked for."""
    t = (text or "").strip().strip("`").strip()
    m = re.search(r"(?m)^\s*UNREADABLE\s*:\s*(.+)$", t)
    if m:
        return {"unreadable": m[1].strip()}
    m = re.search(r"(?m)^\s*REFUSED\s*:\s*(.+)$", t)
    if m:
        return {"refused": m[1].strip()}

    def field(name: str) -> str:
        f = re.search(rf"(?m)^\s*(?:\*\*)?{name}(?:\*\*)?\s*:\s*(.*)$", t)
        return f[1].strip().strip("*").strip() if f else ""

    summary = field("SUMMARY")
    comments = []
    for c in COMMENT.finditer(t):
        cat = c["cat"].lower()
        cat = "justify" if "justif" in cat else cat
        comments.append((c["where"].strip().strip("`"), cat, c["what"].strip()))
    if not summary and not comments:
        return {}
    return {"kind": field("KIND").lower(), "note": field("NOTE"), "summary": summary, "comments": comments}


def tidy_comments(comments: list, policy: str | None, most: int) -> tuple[list, int]:
    """Comments as they may be shown: none that gives the fix away, each cut to its policy's length, at most `most`.
    Returns (kept, how many were left out for giving a fix away)."""
    kept, dropped = [], 0
    for where, cat, what in comments:
        if REWRITE.search(what) or what.count("$$") > 1:
            dropped += 1
            continue
        limit = LONG.get(policy, 360)
        if policy == "hints":
            what = re.split(r"(?<=[.!?])\s", what, maxsplit=1)[0]
        if len(what) > limit:
            cut = what[:limit].rsplit(" ", 1)[0]
            what = cut.rstrip(",;:") + "…"
        kept.append((where[:90], cat, what))
    return kept[: max(1, int(most or 15))], dropped


def shown_name(f) -> str:
    """A file's name as you'd know it: without the time stamp Telegram's inbox puts in front."""
    return re.sub(r"^\d{4}-\d\d-\d\d-\d{6}-", "", Path(f).name)


def numbered(text: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    w = len(str(len(lines)))
    return "\n".join(f"{i + 1:>{w}}| {ln}" for i, ln in enumerate(lines))


class Drafts(Module):
    id = "drafts"
    title = "Check my draft"
    description = (
        'Before you hand it in: a photo, PDF, .tex, essay or code with "check this", and the gaps, unclear steps and '
        "errors are marked, nothing rewritten."
    )
    privacy = "The draft you send and the course notes the AI reads go to the AI you picked."
    extra = True  # an add-on: on only by hand
    bundle = "research_addon"  # part of the Research add-on bundle (its card turns them on and off together)

    def __init__(self, app):
        super().__init__(app)
        self.dir = app.paths.state / "drafts"
        self._recent: list[tuple[float, list[str]]] = []  # files you sent lately (Telegram), for "check this" after
        app.jobs.then_actions["drafts.ready"] = self._ready  # an answer that comes after it's turned off isn't lost
        app.ask.hooks["drafts.course"] = self._course_answer

    # --------------------------------------------------------------------------------------- the state
    def _file(self, did: str) -> Path:
        return self.dir / f"{re.sub(r'[^a-z0-9]', '', did)}.json"

    def _load(self, did: str) -> dict | None:
        return jload(self._file(did), None)

    def _save(self, d: dict) -> None:
        jsave(self._file(d["id"]), d)
        for p in sorted(self.dir.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-100]:  # the last 100 checks
            p.unlink(missing_ok=True)

    # ---------------------------------------------------------------------------------- what to check
    def take(self, msg: Incoming) -> str | None:
        """App.handle, before files are filed: "check this" with a file (or just after one) starts a check; a file
        sent with anything else is remembered for a moment, and the message goes on as usual (None)."""
        text = msg.text or ""
        if msg.files and not wants(text):
            self._recent = [*self._recent[-4:], (time.time(), [str(f) for f in msg.files])]
            return None
        m = CHECK.match(text)
        if not m or not wants(text):
            return None
        files = [Path(f) for f in msg.files] or self._recent_files(msg.via)
        if not files:
            if m["mine"]:  # "check my proof" with nothing sent: how to
                return self._how()
            return None  # "check this" about something else: the rest of Kurooto takes it
        return self.check(files, m["rest"], via=msg.via, reply_to=msg.message_id, msg=msg)

    def _how(self) -> str:
        return (
            'Send the draft (a photo, PDF, .tex, essay or code file) with "check this" as its caption, or /check with '
            "the course: /check la. I'll mark gaps, unclear steps and errors; nothing gets rewritten."
        )

    def _recent_files(self, via: str) -> list[Path]:
        """What you sent in the last drafts.recent_minutes: Telegram's last file, or the phone app's last share."""
        window = 60 * float(self.setting("recent_minutes") or 15)
        if via == "app":
            rows = jload(self.app.paths.state / "calls" / "shared.json", []) or []
            rows = [r for r in rows if isinstance(r, dict) and time.time() - r.get("at", 0) < window]
            return [Path(rows[-1]["path"])] if rows and Path(rows[-1]["path"]).is_file() else []
        hit = next((fs for at, fs in reversed(self._recent) if time.time() - at < window), [])
        return [Path(f) for f in hit if Path(f).is_file()]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        files = [Path(f) for f in msg.files] or self._recent_files(msg.via)
        rest = arg
        if not files and msg.via in ("terminal", "dashboard", "setup"):  # a file on this computer, named
            found, rest = self._path_in(arg)
            files = [found] if found else []
        if not files:
            return self._how()
        return self.check(files, rest, via=msg.via, reply_to=msg.message_id, msg=msg)

    @staticmethod
    def _path_in(text: str) -> tuple[Path | None, str]:
        """A file's path in what you typed (/check la ~/essay.md), and the rest."""
        for tok in re.findall(r'"[^"]+"|\'[^\']+\'|\S+', text or ""):
            raw = tok.strip("\"'")
            if not re.match(r"^(?:~|/|[A-Za-z]:[\\/]|\.{1,2}[\\/])", raw):
                continue
            p = Path(raw).expanduser()
            if p.is_file():
                return p.resolve(), (text.replace(tok, " ")).strip()
        return None, text

    # ---------------------------------------------------------------------------------------- the course
    def _subjects(self):
        sub = self.app.modules.get("subjects")
        return sub if sub is not None and self.app.is_on("subjects") and sub.subjects() else None

    def _course(self, text: str, files: list[Path]) -> tuple[str | None, bool, str]:
        """(the course's slug or None, whether that's sure, the rest of the text): named first ("la the induction
        step"), named anywhere once, in a file's name or folder, the class going on or just over, the only one."""
        sub = self._subjects()
        text = re.sub(r"^\s*(?:for|in|from)\s+", "", (text or "").strip(" ,.:;-?!"), flags=re.I)
        if sub is None:
            return None, True, text
        words = text.split()
        for k in range(min(4, len(words)), 0, -1):
            sl = sub.resolve(" ".join(words[:k]).strip(",:;"))
            if sl:
                rest = " ".join(words[k:]).strip(" ,:;-")
                return sl, True, re.sub(r"^(?:on|about|esp\.?|especially)\s+", "", rest, flags=re.I)
        found = sub.find_in(text)
        if len(found) == 1:
            return found[0], True, text
        for f in files:
            named = sub.find_in(re.sub(r"[-_.]+", " ", f.stem))
            if len(named) == 1:
                return named[0], True, text
            for s in sub.subjects():
                folder = layout.path(self.app, "subject", subject=s["slug"])
                try:
                    if folder.is_dir() and f.resolve().is_relative_to(folder.resolve()):
                        return s["slug"], True, text
                except OSError:
                    continue
        t = now()
        for c in sub.classes_on(t.date()):
            if c["start_dt"] - dt.timedelta(minutes=10) <= t <= c["end_dt"] + dt.timedelta(minutes=30):
                return c["subject"], True, text
        items = sub.subjects()
        return (items[0]["slug"], True, text) if len(items) == 1 else (None, False, text)

    def _course_answer(self, q: dict, answer: str) -> str | None:
        d = self._load(str((q.get("hook_payload") or {}).get("id", "")))
        if d is None or d.get("status") != "course":
            return None
        sub = self._subjects()
        slug = sub.resolve(answer) if sub is not None and answer.strip() != NOT_FOR else None
        if slug is None and answer.strip() != NOT_FOR and sub is not None:
            slug = next((s["slug"] for s in sub.subjects() if s["name"] == answer.strip()), None)
        d["subject"] = slug
        return self._go(d)

    # ---------------------------------------------------------------------------------------- starting
    def check(
        self,
        files: list[Path],
        text: str = "",
        via: str = "telegram",
        reply_to=None,
        msg: Incoming | None = None,
        subject: str | None = None,
    ) -> str:
        """Start a check of these files; returns what to say now."""
        files = [Path(f) for f in files if Path(f).is_file()]
        bad = [shown_name(f) for f in files if f.suffix.lower() not in TEXT_TYPES | OTHER_TYPES]
        files = [f for f in files if f.suffix.lower() in TEXT_TYPES | OTHER_TYPES]
        if not files:
            what = f" ({', '.join(bad)})" if bad else ""
            return f"I can check photos, PDFs, .tex, essays (.md, .txt, .docx) and code files{what}."
        slug, sure, focus = self._course(text, files)
        if subject:
            slug, sure = subject, True
        did = uuid.uuid4().hex[:8]
        d = {
            "id": did,
            "files": [str(f) for f in files],
            "focus": focus.strip()[:300],
            "via": via,
            "reply_to": reply_to,
            "subject": slug,
            "status": "new",
        }
        if not sure:
            sub = self._subjects()
            if via in ("terminal", "setup"):
                return "Which course is it for? Name it first: /check la " + " ".join(shown_name(f) for f in files)
            d["status"] = "course"
            self._save(d)
            names = [s["name"] for s in sub.subjects()][:8] if sub is not None else []
            self.app.ask.ask(
                f"Which course is {shown_name(files[0])} for? Its AI policy decides how much I say.",
                choices=[*names, NOT_FOR],
                hook="drafts.course",
                hook_payload={"id": did},
                source=self.id,
                title="Check my draft",
                why="asked",
            )
            return "One question first: which course it's for."
        return self._go(d, msg)

    def _go(self, d: dict, msg: Incoming | None = None) -> str:
        """Ask the AI for the comments, going by the course's AI policy."""
        from kurooto.modules.skills import load_skill, skill_prompt

        sub = self._subjects()
        slug = d.get("subject")
        name = sub.name_of(slug) if sub is not None and slug else ""
        policy = sub.ai_policy(slug) if sub is not None and slug else None
        files = [Path(f) for f in d["files"] if Path(f).exists()]
        if policy == "off":
            d["status"] = "refused"
            self._save(d)
            self.app.events.emit("draft_refused", why="policy")
            return (
                f"{name}'s AI policy is off, so I don't check drafts for it. If the course allows hints: "
                f"/subject policy {slug} hints."
            )
        if not files:
            return "That file is gone; send it again."
        most = int(self.setting("max_comments") or 15)
        parts = [
            f"Course: {name} (its notes folder: {layout.rel(self.app, 'subject', subject=slug)}/)"
            if slug
            else "Course: none given",
            f"Course AI policy: {POLICY_WORDS.get(policy, POLICY_WORDS[None])}",
            f"At most {most} comments.",
        ]
        if d.get("focus"):
            parts.append(f"What they asked you to look at: {d['focus']}")
        lectures = self._lectures(slug) if slug else []
        if lectures:
            parts.append("The course's lecture notes: " + ", ".join(layout.shown(self.app, f) for f in lectures[:30]))
        as_files = []
        for f in files:
            body = self._text(f)
            if body is None:
                as_files.append(f)
                continue
            parts.append(f"The draft {shown_name(f)}, numbered line by line:\n\n{numbered(body)}")
        prompt = skill_prompt(self.app, "check-draft", "\n".join(parts), as_files)
        if prompt is None:
            return "The check-draft skill is missing."
        skill = load_skill(self.app, "check-draft")
        d.update(status="working", policy=policy)
        self._save(d)
        jid = self.app.jobs.submit(
            prompt,
            title=f"Check: {shown_name(files[0])}"[:80],
            effort=skill.effort if skill else "medium",
            quiet=True,
            then="drafts.ready",
            then_payload={"id": d["id"]},
        )
        if msg is not None and d.get("via") == "terminal":
            msg.job = jid  # the dashboard's chat and `kurooto ask` print the answer themselves
        self.app.events.emit(
            "draft_check_started", subject=slug or "", files=len(files), text=len(files) - len(as_files)
        )
        what = shown_name(files[0]) + (f" and {len(files) - 1} more" if len(files) > 1 else "")
        return f"Checking {what}{f' for {name}' if name else ''}…"

    @staticmethod
    def _text(f: Path) -> str | None:
        """A text draft's contents to number, or None (not text, too long, unreadable): then it goes as a file."""
        if f.suffix.lower() not in TEXT_TYPES:
            return None
        try:
            t = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        return t if 0 < len(t) <= MAX_TEXT else None

    def _lectures(self, slug: str) -> list[Path]:
        from kurooto.core.actions import DATED

        folder = layout.path(self.app, "subject", subject=slug)
        if not folder.is_dir():
            return []
        return sorted((p for p in folder.rglob("*.md") if DATED.match(p.name)), key=lambda p: p.name, reverse=True)

    # ------------------------------------------------------------------------------------------ the AI
    def _ready(self, job, result, payload: dict) -> None:
        d = self._load(str(payload.get("id", "")))
        if d is None:
            return
        say = d.get("via") != "terminal"  # the dashboard's chat and `kurooto ask` showed the answer themselves

        def tell(text: str) -> None:
            if say:
                self.app.notify(text, kind="result", reply_to=d.get("reply_to"), why="asked")

        if not result.ok:
            from kurooto.core.jobs import FRIENDLY

            label = providers.CHOICES.get(job.brain or "", job.brain or "the AI")
            d["status"] = "failed"
            self._save(d)
            tell(FRIENDLY.get(result.verdict, "It failed.").format(brain=label))
            return
        got = parse_check(result.text)
        name = shown_name(d["files"][0])
        if "unreadable" in got:
            d["status"] = "failed"
            self._save(d)
            tell(f"I couldn't read {name} ({got['unreadable']}). Send it again, sharper, or as a file.")
            return
        if "refused" in got or not got:
            d["status"] = "failed"
            self._save(d)  # never pass on an answer that isn't in comments: it could be the work rewritten
            why = got.get("refused") or "the AI's answer didn't come as comments"
            tell(f"No check this time: {why}. /check again to retry.")
            return
        comments, dropped = tidy_comments(got["comments"], d.get("policy"), int(self.setting("max_comments") or 15))
        note = self._note_block(d, got, comments)
        d.update(status="done", comments=len(comments), note=note)
        self._save(d)
        tell(self.message(d, got, comments, dropped, note))
        self.app.events.emit(
            "draft_checked",
            comments=len(comments),
            dropped=dropped,
            kind=got.get("kind") or "",
            note=bool(note),
        )

    def message(self, d: dict, got: dict, comments: list, dropped: int, note: str) -> str:
        sub = self._subjects()
        slug = d.get("subject")
        name = sub.name_of(slug) if sub is not None and slug else ""
        head = f"Checked {shown_name(d['files'][0])}{f' ({name})' if name else ''}: {got.get('summary') or 'done.'}"
        rows = [f"{i}. {where} ({LABEL.get(cat, cat)}): {what}" for i, (where, cat, what) in enumerate(comments, 1)]
        out = head + ("\n\n" + "\n".join(rows) if rows else "\n\nNothing to mark.")
        out += "\n\nNothing was rewritten: these point at what to look at; the fixing is yours."
        if dropped:
            out += f" ({dropped} comment{'s' if dropped > 1 else ''} left out: they gave the fix away.)"
        if note:
            out += f"\nAlso in {note}."
        if slug and d.get("policy") is None:
            out += f"\n(No AI policy set for {name}: /subject policy {slug} hints or off if the course limits AI help.)"
        return out

    # --------------------------------------------------------------------------------------- the note
    def _note_block(self, d: dict, got: dict, comments: list) -> str:
        """Notes that were checked: the comments in a Kurooto block in the matching lecture note (the note itself when
        a note was sent). Returns the note as shown, or ""."""
        if not self.setting("note_block"):
            return ""
        target = self._target(d, got)
        if target is None:
            return ""
        try:
            old = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""  # not plain text: left alone
        rows = [f"- {where} ({LABEL.get(cat, cat)}): {what}" for where, cat, what in comments] or ["- Nothing to mark."]
        body = (
            f"## {self.app.name}'s check of {shown_name(d['files'][0])} ({now():%Y-%m-%d})\n\n"
            f"{got.get('summary') or ''}\n\n" + "\n".join(rows)
        )
        new = graphwrite.put_block(old, "draft-check", body)
        if not graphwrite.guarded(old, new).ok:
            return ""
        from kurooto.core.tools import write_note_file

        write_note_file(target, new)
        return layout.shown(self.app, target)

    def _target(self, d: dict, got: dict) -> Path | None:
        root = self.app.workspace.resolve()
        for f in d["files"]:  # a note of yours that was sent: its own block
            p = Path(f).resolve()
            if p.suffix.lower() == ".md" and p.is_file() and root in p.parents:
                return p
        if got.get("kind") != "notes" or not d.get("subject"):
            return None
        lectures = self._lectures(d["subject"])
        pick = (got.get("note") or "").strip().strip("[]`").removesuffix(".md")
        if pick and pick.lower() != "none":
            f = (self.app.workspace / f"{pick}.md").resolve()
            if f.is_file() and f in {x.resolve() for x in lectures}:
                return f
        words = set(re.findall(r"[a-z]{4,}", f"{got.get('summary', '')} {Path(d['files'][0]).stem}".lower()))
        scored = [(len(words & set(re.findall(r"[a-z]{4,}", p.stem.lower()))), p.name, p) for p in lectures]
        best = max(scored, default=None)
        return best[2] if best and best[0] > 0 else None

    # ------------------------------------------------------------------------------------------ commands
    def commands(self):
        return [
            Command(
                "check",
                'check a draft before you hand it in: a photo or file with /check la (or "check this"); nothing '
                "rewritten",
                self._cmd,
            )
        ]

    def help(self) -> list[str]:
        return [
            *super().help(),
            '"check this" as a file\'s caption, or just after sending it: the same check',
        ]
