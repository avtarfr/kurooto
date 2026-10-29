"""Link recall cards, part of the Quiz: the concept graph's links (a concept note's "- needs:: [[b]] — reason" lines,
modules/integrate.py) become review cards. Since 0.6.0 they also come from your course notes (lecture notes and course
pages: a typed line like that, or "- [[b]]: a reason of five words or more"), and from the concepts the graph read
out of Classroom files and handwritten notes (their course is the item's); new cards whose concepts you met in class
in the last 14 days come first. A card asks how two concepts relate ("How is Itô's lemma used in the
Fokker-Planck equation?"); you answer by replying in your own words, then see the link's reason and where to read
(the book pages from the concept graph's "Seen in", the best match in the subject's own notes and Classroom files,
core/sources.py), and grade yourself. Spacing and storage are the quiz's own (state/quiz/_links.json, Quiz.grade).

With quiz.links on, up to quiz.links_per_day cards (at most 5) come at quiz.links_at, also to the phone app (they are
questions), never during a class, focus time, a call or the night: a card due then waits until it's over. A card you
haven't answered holds back the next one that day. quiz.links_check: a local model (Local AI models, Ollama) says
how close your answer came before you grade; never a cloud AI.

    /card     a link card now          /cards    how many, what's due, how you did (/cards on, /cards off)
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import conceptgraph as cg
from kurooto.core import layout, sources
from kurooto.core.availability import ON_CALL
from kurooto.core.clock import now
from kurooto.core.graphwrite import RELATIONS, lint_reason
from kurooto.core.layout import link_targets
from kurooto.core.state import jsave
from kurooto.modules.base import Incoming

if TYPE_CHECKING:
    from kurooto.modules.quiz import Quiz

SUBJECT = "_links"  # the quiz file the cards live in (no subject's slug can start with "_")
MOST = 5  # cards a day, whatever quiz.links_per_day says
LINK = r"(\[\[[^\]]+\]\]|\[[^\]\n]*\]\([^)\n]+\))"  # a [[wikilink]] or a [markdown](link.md) (notes.links)
LINE = re.compile(r"^\s*[-*] (" + "|".join(RELATIONS) + r"):: " + LINK + r"\s*[—–-]+\s*(.+?)\s*$")
PLAIN = re.compile(r"^\s*[-*] " + LINK + r"\s*(?::|[—–]|-)\s*(.+?)\s*$")  # "- [[b]]: reason"
RECENT_DAYS = 14  # new cards about what you met in class this recently come first
ASK = {  # relation -> the question, from the note that has the link (a) to its target (b)
    "needs": "Why does {a} need {b}?",
    "generalises": "How does {a} generalise {b}?",
    "special-case-of": "How is {a} a special case of {b}?",
    "example-of": "How is {a} an example of {b}?",
    "contrasts-with": "How does {a} differ from {b}?",
    "equivalent-to": "Why are {a} and {b} the same thing?",
    "part-of": "How is {a} part of {b}?",
    "used-in": "How is {a} used in {b}?",
}
NONE = (
    "No link cards yet: they come from the links between concept notes (the concept graph writes them, or a line "
    'like "- needs:: [[other-note]] — why" under ## Links).'
)
GRADES = (("Forgot", 0), ("Hard", 3), ("Good", 4), ("Easy", 5))  # the quiz's own scale
CHECK = (
    "A student is reviewing how two ideas in their notes relate. Say in one short sentence whether their answer "
    "gets the relation right, starting with Yes, Partly or No.\n\nQuestion: {q}\nThe notes say: {reason}\n"
    "Their answer: {answer}\n"
)


def card_id(a: str, b: str) -> str:
    return hashlib.sha1(f"{a}|{b}".encode(), usedforsecurity=False).hexdigest()[:8]


class LinkCards:
    """Link recall cards for one Quiz module."""

    def __init__(self, quiz: Quiz):
        self.quiz = quiz

    @property
    def app(self):
        return self.quiz.app

    def save(self, st: dict) -> None:
        jsave(self.quiz._dir() / f"{SUBJECT}.json", st)

    def on(self) -> bool:
        return bool(self.quiz.setting("links"))

    def per_day(self) -> int:
        try:
            return max(0, min(MOST, int(self.quiz.setting("links_per_day") or 0)))
        except (TypeError, ValueError):
            return 0

    # ---------------------------------------------------------------------------------------------- the cards
    def links(self) -> dict[str, dict]:
        """Every link with a reason between two notes: the concept notes' typed links, and your course notes' typed
        links or "- [[b]]: reason" lines. Card id -> {a, b, relation, reason, text, subject, recent}."""
        notes, seen = cg.scan(self.app), self._seen()
        course = self.course_notes(notes)
        pool = {**notes, **{s: n for s, (n, _) in course.items()}}
        by_name: dict[str, str] = {}
        for s in sorted(notes):  # a card is about a concept: links go to concept notes only
            by_name.setdefault(Path(s).name, s)
        recent = self.recent(seen, course)
        out: dict[str, dict] = {}
        for slug, n in pool.items():
            try:
                lines = n.path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for ln in lines:
                m = LINE.match(ln)
                if m:
                    rel, link, reason = m[1], m[2], m[3]
                else:
                    m = PLAIN.match(ln)
                    if not m or lint_reason(m[2]):
                        continue  # a link without a reason worth asking about
                    rel, link, reason = "", m[1], m[2]
                found = link_targets(link, slug + ".md")
                target = found[0] if found else ""
                target = target if target in notes else by_name.get(target, "") if "/" not in target else ""
                if slug in course and target and not cg.concept_like(notes[target]):
                    continue  # from your course notes, only links to a concept (not a lecture or the course page)
                if not target or target == slug:
                    continue
                a, b = n.title, notes[target].title
                subject = course[slug][1] if slug in course else self.subject_of(seen, slug, target)
                out[card_id(slug, target)] = {
                    "a": slug,
                    "b": target,
                    "relation": rel,
                    "reason": reason.rstrip("."),
                    "names": [a, b],
                    "text": ASK.get(rel, "How does {a} relate to {b}?").format(a=a, b=b),
                    "subject": subject,
                    "recent": slug in recent or target in recent,
                }
        return out

    def course_notes(self, concepts: dict) -> dict[str, tuple[cg.Note, str]]:
        """Each subject's own notes (lecture notes, the course page, what Classroom filed), not the concept notes and
        not the books' index notes: slug -> (note, subject)."""
        subj = self.app.modules.get("subjects")
        if subj is None or not self.app.is_on("subjects"):
            return {}
        lay = layout.of(self.app)
        root = Path(self.app.workspace)
        out: dict[str, tuple[cg.Note, str]] = {}
        for s in subj.subjects():
            folder = lay.path("subject", subject=s["slug"])
            files = sorted(folder.rglob("*.md")) if folder.is_dir() else []
            for f in [*files, lay.path("course", subject=s["slug"])]:
                if not f.is_file() or root not in f.parents:
                    continue
                rel = f.relative_to(root)
                if any(x.startswith(".") for x in rel.parts) or "books" in rel.parts[:-1]:
                    continue
                n = cg.read_note(root, f)
                if n and n.slug not in concepts:
                    out[n.slug] = (n, s["slug"])
        return out

    def recent(self, seen: dict, course: dict) -> set[str]:
        """Notes met in class lately: concepts read from a Classroom file or handwritten notes dated in the last
        RECENT_DAYS days, and dated course notes from then."""
        cut = (dt.date.today() - dt.timedelta(days=RECENT_DAYS)).isoformat()
        ig = self.app.modules.get("integrate")
        items = ig.items() if ig is not None else {}
        out = set()
        for slug, rows in seen.items():
            for r in rows or []:
                if str((items.get(str(r.get("book"))) or {}).get("date") or "") >= cut:
                    out.add(slug)
        for slug, (n, _) in course.items():
            m = re.match(r"\d{4}-\d{2}-\d{2}", n.path.name)
            if m and m[0] >= cut:
                out.add(slug)
        return out

    def subject_of(self, seen: dict, *slugs: str) -> str:
        """The subject of a concept: the book its pages came from (or the class file or handwritten notes, read into
        the graph), else its folder (the plain layout)."""
        ig = self.app.modules.get("integrate")
        items = ig.items() if ig is not None else {}
        for s in slugs:
            for r in seen.get(s) or []:
                book = str(r.get("book", ""))
                if book in items and items[book].get("subject"):
                    return str(items[book]["subject"])
                if "/" in book:
                    return book.split("/")[0]
        first = slugs[0].split("/")[0] if "/" in slugs[0] else ""
        return first if first and (Path(self.app.workspace) / first).is_dir() and first != "zettel" else ""

    def _seen(self) -> dict:
        ig = self.app.modules.get("integrate")
        seen = ig.load("seen.json", {}) if ig is not None else {}
        return seen if isinstance(seen, dict) else {}

    def state(self) -> dict:
        """The cards in the quiz's storage, brought up to date with the notes (a link that's gone stays, marked)."""
        st = self.quiz.load(SUBJECT)
        found = self.links()
        today = dt.date.today().isoformat()
        for iid, card in found.items():
            it = st["items"].setdefault(
                iid, {"section": "Links", "ef": 2.5, "interval": 0, "reps": 0, "due": today, "history": []}
            )
            it.update(card, gone=False)
        if found:
            for iid, it in st["items"].items():
                if iid not in found:
                    it["gone"] = True
        self.save(st)
        return st

    def next_card(self, st: dict) -> tuple[str, dict] | None:
        """What's due: cards seen before first (the most overdue), then new ones."""
        today = dt.date.today().isoformat()
        due = [(k, v) for k, v in st["items"].items() if not v.get("gone") and v["due"] <= today]
        ready = self.frontier()

        def order(kv):
            new = kv[1]["reps"] == 0 and not kv[1]["history"]
            front = 0 if {kv[1].get("a"), kv[1].get("b")} & ready else 1  # same due day: frontier first
            return (new, new and not kv[1].get("recent"), kv[1]["due"], front, kv[0])  # new ones met in class first

        due.sort(key=order)
        from kurooto.core import notinterested  # (0.9.0, notinterested.filter.quiz_links) about a skipped topic: last

        due = notinterested.demote(
            self.app,
            "quiz_links",
            due,
            lambda kv: f"{kv[1].get('text', '')} {' '.join(self.names(kv[1]))} {kv[1].get('subject', '')}",
            lambda kv, why: (kv[0], {**kv[1], "not_interested": why}),
        )
        return due[0] if due else None

    def frontier(self) -> set[str]:
        """quiz.links_frontier (0.9.0, off): the concepts at your frontier or partly known (mind/frontier.py); a card
        touching one comes first among the cards due the same day, never ahead of an overdue one. Else none."""
        if not self.quiz.setting("links_frontier"):
            return set()
        try:
            from kurooto.mind import frontier

            return {s for s, g in frontier.grades(self.app).items() if g in (frontier.FRONTIER, frontier.STARTED)}
        except Exception:
            return set()

    def sent_today(self, st: dict) -> int:
        day = st.get("day") or {}
        return int(day.get("n", 0)) if day.get("date") == dt.date.today().isoformat() else 0

    # ------------------------------------------------------------------------------------------------ sending
    def send(self, why: str = "asked") -> str:
        """A card now: its question, as a message you reply to. Returns what to tell you."""
        st = self.state()
        pick = self.next_card(st)
        if not pick:
            return NONE if not st["items"] else "No link card is due right now."
        iid, it = pick
        name = self.quiz.name_of(it.get("subject") or "")
        why_last = f"\n({it['not_interested']})" if it.get("not_interested") else ""
        self.app.notify(
            f"Link card{' (' + name + ')' if name else ''}:\n{it['text']}{why_last}\n\nReply in your own words.",
            kind="question",
            map_kind="qlink",
            map_ref=iid,
            why=why,
            about=it["text"],
        )
        if why != "asked":  # the ones that came by themselves count toward the day's
            today = dt.date.today().isoformat()
            st["day"] = {"date": today, "n": self.sent_today(st) + 1}
            st["open"] = {"id": iid, "date": today}
            self.save(st)
        self.app.events.emit("quiz_link_card", by=why)
        return ""

    def busy(self, t: dt.datetime) -> tuple[str | None, dt.datetime | None]:
        """A class, focus time, a call or the night: no card now (until when). "No calls till X" lets cards through."""
        av = self.app.availability
        for reason, until in (("focus", av.focus_until(t)), (ON_CALL, av.on_call_until(t))):
            if until:
                return reason, until
        n = av.night(t)
        if n:
            return n
        for name, b in sorted(av.blockers.items()):
            r = None if name.startswith("focus:") else b(t)
            if r:
                return r
        return None, None

    def tick(self, p: dict | None = None) -> str:
        """quiz.links_at (and after a wait): one card, if one is due, today's are not used up, the last was answered,
        and you're not in a class or focus time. Returns what happened, for tests and logs."""
        if (p or {}).get("missed") or not self.on():
            return "off"
        st = self.quiz.load(SUBJECT)
        today = dt.date.today().isoformat()
        if self.sent_today(st) >= self.per_day():
            return "enough"
        if (st.get("open") or {}).get("date") == today:
            return "waiting"  # the last one isn't answered yet
        t = now()
        reason, until = self.busy(t)
        if reason:
            if until and until.date() == t.date():
                self.app.scheduler.at(
                    until + dt.timedelta(minutes=5), "quiz.links_later", key="quiz:links:later", module="quiz"
                )
            return f"held ({reason})"
        return self.send(why="quiz.links") or "sent"

    # ------------------------------------------------------------------------------------- answer and grade
    def answer(self, msg: Incoming, iid: str) -> str | None:
        st = self.quiz.load(SUBJECT)
        it = st["items"].get(iid)
        if not it:
            return "That card is gone."
        if (st.get("open") or {}).get("id") == iid:
            st.pop("open", None)
            self.save(st)
        a, b = self.names(it)
        said = f"{a} {it['relation']} {b}" if it.get("relation") else f"{a} → {b}"
        lines = [f"The note says: {said}: {it['reason']}."]
        look = self.where(it)
        if look:
            lines.append("Where to read: " + "; ".join(look) + ".")
        said = self.check(it, msg.text)
        if said:
            lines.append(f"Local check: {said}")
        lines.append("How did you do?")
        buttons = [[(label, f"ql:{iid}:{q}") for label, q in GRADES]]
        if msg.via == "app":  # the phone's reply note can't carry buttons: the grading comes as its own message
            self.app.notify("\n".join(lines), kind="question", buttons=buttons, why="asked")
            return "The answer and the grade buttons are in the next message."
        msg.reply("\n".join(lines), buttons=buttons)
        return None

    @staticmethod
    def names(it: dict) -> tuple[str, str]:
        n = it.get("names") or [s.rsplit("/", 1)[-1].replace("-", " ") for s in (it["a"], it["b"])]
        return n[0], n[1]

    def where(self, it: dict) -> list[str]:
        """The book pages of both concepts (the concept graph's "Seen in"), then the best match in the subject's own
        notes and Classroom files."""
        out: list[str] = []
        seen = self._seen()
        for s in (it["a"], it["b"]):
            for r in (seen.get(s) or [])[:2]:
                pages = r.get("pages") or []
                if len(pages) == 2:
                    unit = r.get("unit") or "pages"  # a class file's slides, or parts of a text with no pages
                    at = "" if unit == "parts" else f" {'slides' if unit == 'slides' else 'pp.'} {pages[0]}–{pages[1]}"
                    out.append(f"{r.get('title') or r.get('book')}{at}")
        subject = it.get("subject") or ""
        if subject:
            own, cls = sources.notes_material(self.app, subject)
            ws = sources.words(" ".join(self.names(it)))
            for items in (own, cls):
                mine = [e for e in items if not {it["a"], it["b"]} & set(link_targets(e.cite))]
                best = sources.pick(mine, ws, 6000) if ws else []
                if best:
                    out.append(best[0].cite)
        return list(dict.fromkeys(out))[:5]

    def check(self, it: dict, answer: str) -> str:
        """quiz.links_check: one sentence from the local model on how close the answer came; "" without one."""
        if not self.quiz.setting("links_check") or not answer.strip():
            return ""
        lm = self.app.modules.get("local_models")
        if lm is None or not self.app.is_on("local_models"):
            return ""
        model = next((m["tag"] for m in lm.wanted() if str(m.get("key", "")).startswith("helper")), "")
        if not model:
            return ""
        body = {
            "model": model,
            "prompt": CHECK.format(q=it["text"], reason=it["reason"], answer=answer[:1500]),
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 60},
        }
        try:
            with lm.api("/api/generate", body, timeout=60) as r:
                said = str(json.loads(r.read().decode("utf-8")).get("response") or "")
        except (OSError, ValueError):
            return ""
        return re.sub(r"\s+", " ", said).strip()[:300]

    def button(self, iid: str, act: str) -> str:
        try:
            q = int(act or 0)
        except ValueError:
            q = 0
        it = self.quiz.load(SUBJECT)["items"].get(iid)
        if not it:
            return "That card is gone."
        out = self.quiz.grade(SUBJECT, iid, q)
        if q < 3:
            look = self.where(it)
            out += f" Worth a read: {look[0]}." if look else ""
        return out

    # ------------------------------------------------------------------------------------------------ commands
    def cmd_card(self, msg: Incoming, arg: str) -> str | None:
        return self.send() or None

    def cmd_cards(self, msg: Incoming, arg: str) -> str:
        word = arg.strip().lower()
        if word in ("on", "off"):
            self.app.settings.set("quiz.links", word == "on")
            self.quiz.start()
            if word == "off":
                return "Link cards are off. /card still gives one."
            return f"Link cards are on: up to {self.per_day()} a day at {self.quiz.setting('links_at')}."
        st = self.state()
        items = [v for v in st["items"].values() if not v.get("gone")]
        if not items:
            return NONE
        today = dt.date.today().isoformat()
        grades = [h["q"] for v in items for h in v["history"]]
        week = (dt.date.today() - dt.timedelta(days=7)).isoformat()
        recent = [h["q"] for v in items for h in v["history"] if h["date"] >= week]
        rows = [
            f"Link cards: {len(items)} ({sum(1 for v in items if v['history'])} seen, "
            f"{sum(1 for v in items if v['due'] <= today)} due today).",
            f"Answered: {len(grades)} in all, {len(recent)} in the last 7 days"
            + (f", {sum(1 for q in recent if q >= 3)} of them right." if recent else "."),
        ]
        if self.on():
            rows.append(
                f"On: up to {self.per_day()} a day at {self.quiz.setting('links_at')} ({self.sent_today(st)} today)."
            )
        else:
            rows.append("Off: /cards on sends them by themselves; /card gives one now.")
        return "\n".join(rows)
