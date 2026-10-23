"""Hint ladder: a problem you're stuck on, one step at a time. Send a photo of it with "/hint la" as the caption (or
type it: /hint la show that the trace is basis-free) and you get the idea first; Next hint gives the setup, then the
key step; the full solution only when you ask for it ("solution", or the button after the key step). Every step links
the lecture note the problem belongs to.

The AI works out the whole ladder once (the shipped `hint` skill; your own copy in your skills folder replaces it),
and Kurooto shows it a step at a time. Before the first /hint for a subject, it asks what the course allows for AI
help and keeps your answer as an "AI policy: ..." line in the subject's course note; after that it reads the line
from there (change it in the note any time). "No full solutions" ends the ladder at the key step; "no AI help" means
no hints for that subject at all. A policy set for the course itself (/subject policy la hints, or the dashboard's
Study pane: allowed, hints or off) comes first, and then nothing is asked.

    /hint <subject> <the problem>, or a photo with /hint <subject> as its caption
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from kurooto import providers
from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.state import jload, jsave
from kurooto.core.tools import add_to_section, write_note_file
from kurooto.modules.base import Command, Incoming, Module

POLICY = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?AI[ -]?policy(?:\*\*)?\s*[:\-–]\s*(?P<p>\S.*?)\s*$", re.I | re.M)
NO_SOLUTION = re.compile(
    r"\b(?:no (?:full |complete |worked )?solutions?|hints? only|only hints?|not (?:the )?(?:full |complete )?"
    r"solutions?|without (?:full )?solutions?)\b",
    re.I,
)
NO_AI = re.compile(r"\b(?:no ai|not allowed|forbidden|prohibited|banned|no help)\b", re.I)
CHOICES = ["Hints and full solutions", "Hints only, no full solutions", "No AI help"]
STEPS = [("idea", "IDEA", "the idea"), ("setup", "SETUP", "the setup"), ("key", "KEY STEP", "the key step")]
LABELS = r"NOTE|IDEA|SETUP|KEY STEP|SOLUTION|UNREADABLE|REFUSED"
NEXT = re.compile(r"^\s*(?:next|next hint|more|another( hint)?|go on|continue|hint)\s*[.!]?\s*$", re.I)
SOLUTION = re.compile(
    r"^\s*(?:(?:show (?:me )?)?(?:the )?(?:full )?solution|answer|show (?:me )?the answer)\s*[.!]?\s*$", re.I
)


def policy_kind(line: str) -> str:
    """ "solution" (hints and the full solution), "hints" (no full solutions) or "none" (no AI help)."""
    if NO_SOLUTION.search(line):
        return "hints"
    if NO_AI.search(line):
        return "none"
    return "solution"


def parse_ladder(text: str) -> dict:
    """The AI's answer as {note, idea, setup, key, solution} (or {unreadable} / {refused}); {} if it isn't one."""
    parts = re.split(rf"(?m)^\s*(?:\*\*)?({LABELS})(?:\*\*)?\s*:\s*", text or "")
    found = {parts[i].upper(): parts[i + 1].strip().strip("`").strip() for i in range(1, len(parts) - 1, 2)}
    if "UNREADABLE" in found:
        return {"unreadable": found["UNREADABLE"]}
    if "REFUSED" in found:
        return {"refused": found["REFUSED"]}
    out = {key: found.get(label, "") for key, label, _ in STEPS}
    if not all(out.values()):
        return {}
    out["solution"] = found.get("SOLUTION", "")
    out["note"] = found.get("NOTE", "")
    return out


class Hints(Module):
    id = "hints"
    title = "Hint ladder"
    description = (
        "Stuck on a problem? A photo and /hint: the idea, the setup, the key step, the solution only if asked."
    )
    requires = ("subjects",)
    privacy = "The problem (its photo or text) and the notes the AI reads go to the AI you picked."

    def __init__(self, app):
        super().__init__(app)
        self.dir = app.paths.state / "hints"
        app.jobs.then_actions["hints.ready"] = self._ready  # an answer that arrives after it's turned off isn't lost
        app.ask.hooks["hints.policy"] = self._policy_answer

    # --------------------------------------------------------------------------------------- the state
    def _file(self, hid: str) -> Path:
        return self.dir / f"{re.sub(r'[^a-z0-9]', '', hid)}.json"

    def _load(self, hid: str) -> dict | None:
        return jload(self._file(hid), None)

    def _save(self, h: dict) -> None:
        jsave(self._file(h["id"]), h)
        old = sorted(self.dir.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-100]  # the last 100 ladders
        for p in old:
            p.unlink(missing_ok=True)

    # ---------------------------------------------------------------------------------- the AI policy
    def course_note(self, slug: str) -> Path:
        return layout.path(self.app, "course", subject=slug)

    def policy(self, slug: str) -> str | None:
        """The course's policy set as a setting (/subject policy, in its words: CHOICES), else the "AI policy: ..."
        line from the subject's course note, or None if it has neither."""
        sub = self.app.modules.get("subjects")
        row = next((s for s in sub.subjects() if s["slug"] == slug), None) if sub is not None else None
        set_ = {"allowed": CHOICES[0], "hints": CHOICES[1], "off": CHOICES[2]}.get(str((row or {}).get("ai_policy")))
        if set_:
            return set_
        try:
            m = POLICY.search(self.course_note(slug).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return None
        return m["p"].strip("* ") if m else None

    def _keep_policy(self, slug: str, answer: str) -> None:
        f = self.course_note(slug)
        try:
            old = f.read_text(encoding="utf-8")
        except FileNotFoundError:
            name = self.app.modules["subjects"].name_of(slug)
            old = layout.frontmatter(self.app, "course", f, title=name, subject=slug) + f"# {name}\n"
        except (OSError, UnicodeDecodeError):
            return  # not plain text: asked again next time rather than rewritten
        line = f"AI policy: {answer.strip()} (your answer to {self.app.name}, {now():%Y-%m-%d})"
        write_note_file(f, add_to_section(old, "", line))

    def _policy_answer(self, q: dict, answer: str) -> str | None:
        p = q.get("hook_payload") or {}
        slug, hid = p.get("subject", ""), p.get("hint", "")
        if not slug or not answer.strip():
            return None
        self._keep_policy(slug, answer)
        self.app.events.emit("hint_policy_set", kind=policy_kind(answer))
        h = self._load(hid) if hid else None
        if h is not None and h.get("status") == "policy":
            return self._go(h)
        return None

    # ---------------------------------------------------------------------------------------- starting
    def _subject(self, text: str) -> tuple[str | None, str]:
        """The subject (named first, or anywhere once) and the rest of the text."""
        sub = self.app.modules["subjects"]
        first, _, rest = text.strip().partition(" ")
        w = first.strip(":,-").lower()
        for s in sub.subjects():
            if w and w in (s["slug"], s["name"].lower(), *(a.lower() for a in s.get("aliases", []))):
                return s["slug"], rest.strip()
        found = sub.find_in(text)
        if len(found) == 1:
            return found[0], text.strip()
        subjects = sub.subjects()
        return (subjects[0]["slug"], text.strip()) if len(subjects) == 1 else (None, text.strip())

    def _cmd(self, msg: Incoming, arg: str) -> str:
        slug, problem = self._subject(arg)
        files = [str(f) for f in msg.files]
        if not files and not problem:
            return (
                "Send the problem as a photo with /hint and its subject as the caption (/hint la), or type it: "
                "/hint la show that the trace is basis-free."
            )
        if slug is None:
            return "Which subject is it for? Put its short name first: /hint la …"
        hid = uuid.uuid4().hex[:8]
        h = {"id": hid, "subject": slug, "problem": problem, "files": files, "step": 0, "status": "new"}
        line = self.policy(slug)
        if line is None:
            h["status"] = "policy"
            self._save(h)
            name = self.app.modules["subjects"].name_of(slug)
            self.app.ask.ask(
                f"Before the first hint for {name}: what does the course allow for AI help? I'll keep your answer "
                f'as an "AI policy" line in {layout.shown(self.app, self.course_note(slug))} and go by it.',
                choices=CHOICES,
                hook="hints.policy",
                hook_payload={"subject": slug, "hint": hid},
                source=self.id,
                title="AI policy",
                why="asked",
            )
            return "One question first (once per subject): the course's AI policy."
        return self._go(h)

    def _go(self, h: dict) -> str:
        """Ask the AI for the ladder, going by the course's AI policy."""
        from kurooto.modules.skills import load_skill, skill_prompt

        sub = self.app.modules["subjects"]
        line = self.policy(h["subject"]) or "not given"
        kind = policy_kind(line)
        name = sub.name_of(h["subject"])
        if kind == "none":
            h["status"] = "refused"
            self._save(h)
            self.app.events.emit("hint_refused", why="policy")
            where = "course settings" if line == CHOICES[2] else "course note"
            return f'The AI policy in {name}\'s {where} says "{line}", so no hints from me for {name}.'
        args = (
            f"Subject: {name} (its notes folder: {layout.rel(self.app, 'subject', subject=h['subject'])})\n"
            f"Course AI policy: {line}\nThe problem: {h['problem'] or '(in the file below)'}"
        )
        files = [Path(f) for f in h.get("files", []) if Path(f).exists()]
        prompt = skill_prompt(self.app, "hint", args, files)
        skill = load_skill(self.app, "hint")
        h.update(status="working", policy=kind, policy_line=line)
        self._save(h)
        self.app.jobs.submit(
            prompt,
            title=f"/hint {name}",
            effort=skill.effort if skill else "medium",
            quiet=True,
            then="hints.ready",
            then_payload={"id": h["id"]},
        )
        self.app.events.emit("hint_started", subject=h["subject"], files=len(files))
        return "Working out the first hint…"

    # ------------------------------------------------------------------------------------------ the AI
    def _ready(self, job, result, payload: dict) -> None:
        h = self._load(str(payload.get("id", "")))
        if h is None:
            return
        if not result.ok:
            from kurooto.core.jobs import FRIENDLY

            label = providers.label(job.brain or "", job.brain or "the AI")
            h["status"] = "failed"
            self._save(h)
            self.app.notify(FRIENDLY.get(result.verdict, "It failed.").format(brain=label), kind="result", why="asked")
            return
        ladder = parse_ladder(result.text)
        if "unreadable" in ladder:
            h["status"] = "failed"
            self._save(h)
            self.app.notify(
                f"I couldn't read the problem ({ladder['unreadable']}). Send it again, sharper or typed.", why="asked"
            )
            return
        if "refused" in ladder or not ladder:
            h["status"] = "failed"
            self._save(h)  # never pass on an answer that isn't in steps: it could give the whole solution away
            why = ladder.get("refused") or "the AI's answer didn't come in steps"
            self.app.notify(f"No hints this time: {why}. /hint again to retry.", kind="result", why="asked")
            return
        h.update(ladder=ladder, note=self._lecture_note(h, ladder), status="ready", step=0)
        self._save(h)
        self._step(h)

    def _lecture_note(self, h: dict, ladder: dict) -> str:
        """The lecture note to link: the AI's pick if it's a real note in the subject's folder, else the one whose
        name shares the most words with the problem and the idea; "" if there's none."""
        root = self.app.workspace
        pick = ladder.get("note", "").strip().strip("[]").removesuffix(".md")
        if pick and pick.lower() != "none":
            f = (root / f"{pick}.md").resolve()
            if f.is_file() and root.resolve() in f.parents:
                return layout.shown(self.app, f)
        folder = layout.path(self.app, "subject", subject=h["subject"])
        skip = {"course", "doubts", "exam-prep", "class-log"}
        notes = [p for p in folder.glob("*.md") if p.stem not in skip] if folder.is_dir() else []
        words = set(re.findall(r"[a-z]{4,}", f"{h.get('problem', '')} {ladder.get('idea', '')}".lower()))
        scored = [(len(words & set(re.findall(r"[a-z]{4,}", p.stem.lower()))), p.stem, p) for p in notes]
        best = max(scored, default=None)
        return layout.shown(self.app, best[2]) if best and best[0] > 0 else ""

    # --------------------------------------------------------------------------------------- the ladder
    def _step(self, h: dict) -> None:
        i = int(h.get("step", 0))
        key, _, what = STEPS[i]
        text = f"Hint {i + 1} of {len(STEPS)} ({what}): {h['ladder'][key]}"
        text += f"\n\nLecture note: {h['note']}" if h.get("note") else "\n\n(No lecture note on this yet.)"
        if i + 1 < len(STEPS):
            buttons = [[("Next hint", f"hint:{h['id']}:next")]]
        elif h.get("policy") == "solution":
            buttons = [[("Show the solution", f"hint:{h['id']}:solution")]]
        else:
            buttons = None
            text += "\n\nThat's the last hint: the course's AI policy rules out full solutions."
        self.app.notify(text, kind="result", buttons=buttons, map_kind="hint", map_ref=h["id"], why="asked")
        self.app.events.emit("hint_step", step=i + 1)

    def advance(self, hid: str, act: str) -> str:
        h = self._load(hid)
        if h is None or h.get("status") != "ready":
            return "That hint ladder is gone; /hint again."
        if act == "solution":
            if h.get("policy") != "solution":
                return f'The course\'s AI policy ("{h.get("policy_line", "")}") rules out full solutions.'
            if not h["ladder"].get("solution"):
                return "There's no solution in this ladder; /hint again."
            note = f"\n\nLecture note: {h['note']}" if h.get("note") else ""
            self.app.notify(f"Solution: {h['ladder']['solution']}{note}", kind="result", why="asked")
            h["status"] = "solved"
            self._save(h)
            self.app.events.emit("hint_solution", after_step=int(h.get("step", 0)) + 1)
            return "Solution sent."
        if act == "next":
            if int(h.get("step", 0)) + 1 >= len(STEPS):
                return "That was the last hint" + (": ask for the solution." if h.get("policy") == "solution" else ".")
            h["step"] = int(h.get("step", 0)) + 1
            self._save(h)
            self._step(h)
            return "Next hint sent."
        return "unknown button"

    def callbacks(self):
        return {"hint": self.advance}

    def replies(self):
        return {"hint": self._reply}

    def _reply(self, msg: Incoming, ref: str) -> str | None:
        """A reply of "next" or "solution" to a hint: the step it brings is the answer."""
        act = "solution" if SOLUTION.match(msg.text) else "next" if NEXT.match(msg.text) else ""
        if not act:
            return 'Reply "next" for the next hint, or "solution" for the full solution.'
        out = self.advance(ref, act)
        return None if out in ("Next hint sent.", "Solution sent.") else out

    def commands(self):
        return [Command("hint", "stuck on a problem? a photo with /hint la: one hint at a time", self._cmd)]
