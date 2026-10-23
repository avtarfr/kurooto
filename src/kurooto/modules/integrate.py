"""Concept graph: what you read in a book, and your class materials, are woven into the notes you already have.

What gets read (integrate.sources): books (modules/books.py), the Classroom files filed into your notes
(modules/google_classroom.py: slides, handouts, PDFs, solutions with at least 1,500 characters of text, MIN_CHARS; a
short announcement isn't), and, when you add "handwritten", your handwritten notes once they're written out and linked
(modules/handwritten_links.py). Each item that isn't a book is read once: it's keyed by the hash of its text, so a file
filed again unchanged isn't read again and an edited one is. They share one queue and one night's budget with the
books: the newest class material first (it's what you're studying now), then what /graph backfill classroom queued
(the materials filed before 0.5.19, the oldest course first), then the books in their order. A copy of each item's text
is kept in <state>/integrate/texts/, so moving the file doesn't lose it; its "Seen in" lines point at the note it was
filed into (the lecture note Classroom → notes wrote, else the course page; the handwritten note itself). A textbook
filed from Classroom (a course's "Books" post with the PDF attached: core/studypack.py:is_class says it's a book) gets
a source note of its own instead, <subject>/books/<its title>.md, like a book's index note (0.6.1).

After a restart (0.6.1): a batch whose request the restart lost is asked again at once (inflight, core/jobs.py:settled),
and inside tonight's reading window the night carries on (resume).

When a book has been read, its text is cut into batches that follow its sections (core/segment.py, 3 to 20 pages). For
each batch, one AI request (the bulk AI) is shown the pages and the few existing notes that may be related (found with
keywords, names and, where this computer has them, embeddings: core/conceptgraph.py, nothing is "read by an AI" to find
them), and answers with the concepts the pages develop, how each relates to your other notes, and what an existing
note lacks. Plain checks then run on the answer (core/integrate_ai.py); anything doubtful goes to a second look by the
other AI program (the check AI), or the same one told to be strict, and is dropped unless that confirms it. What
survives is written into your notes (core/graphwrite.py): a new concept note per new concept, typed links with their
reasons, "Seen in" lines on existing notes, and the chapter note's list of what it introduces. Only lines are added;
nothing you wrote is changed. Each batch is one git commit when your notes are a repository.

Every day, the concepts the new reading touched, and notes with no links in, get a second pass against everything
that's there now (the "garden"); the day's changes are one line on Telegram.

Near-duplicate concepts (integrate.duplicates, core/graphmerge.py): each morning, up to three pairs of notes that look
like one concept (the same name, a shared alias, or embeddings at least 0.92 alike) come as one question with Merge /
Keep both / Add alias, each with Undo; /graph same asks now. Notation (integrate.notation): the bulk AI also says how
the pages write each concept (B_t, W_t, where 2pi goes in a Fourier transform), with a quote; rows whose quote isn't
in the pages are dropped, and when a second source writes it differently the note gets a "Notation" table in
Kurooto's block. It's a part of the Research add-on (modules/research_addon.py): tables are written only while the
add-on is on.

Which AI: integrate.roles {"bulk": "agy", "check": "claude"} (empty: chosen from what's installed; one program does
both). The two run side by side. With no agent program, your main AI (a Gemini key, say) does both, at its limit.

How much a night: integrate.per_night "auto" fits it to that AI by itself (core/readbudget.py): learned for a
subscription (Claude Code, agy), a share of a free Gemini key's day, money for an API key, no limit for the model on
this computer; a number is a hard ceiling. The night starts 5 hours before you usually wake, never later than
integrate.at.

State: <state>/integrate/ (ledger.json: "books" per book and "items" per other item; items.json: what was queued
from Classroom and handwritten notes; texts/, seen.json, chapters.json, garden.json, stopped.json, budget.json,
pending/, undo/, vectors.db). Command: /graph (status), /graph now (start), /graph stop (until the next night's start),
/graph backfill classroom (read the Classroom files filed before), /graph same (look-alike concept notes now).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import threading
import time
from dataclasses import asdict
from pathlib import Path

from kurooto import providers
from kurooto.core import conceptgraph as cg
from kurooto.core import graphmerge, layout, proc, readbudget, segment
from kurooto.core import graphwrite as gw
from kurooto.core import integrate_ai as ai
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.core.tools import write_note_file
from kurooto.modules.base import Command, Incoming, Module
from kurooto.providers.base import Verdict


def _wiki(target: str, label: str | None = None) -> str:
    return layout.render_link("wiki", target, label)


register_defaults(
    "integrate",
    {
        "at": "daily 01:30",  # when the night's integration starts (it carries on batch after batch)
        "roles": {"bulk": "", "check": ""},  # the AI for the bulk work and for the second look ("": chosen for you)
        "batch_pages": 12,  # about this many pages per request
        "per_night": "auto",  # batches a night: auto (fitted to your AI's plan by itself) or a number (a hard ceiling)
        "share_pct": 60,  # a subscription's usage window (or a free key's day): the most of it reading takes
        "max_cost_per_night": 0.5,  # an API key: the most a night's reading may cost (USD, as the service reports it)
        "price_per_mtok": {"in": 2.0, "out": 8.0},  # an API key that reports no cost: its USD per million tokens
        "garden": True,  # each day, a second pass over the notes the reading touched and notes nothing links to
        "garden_per_day": 40,  # the most notes in that pass
        "embeddings": "auto",  # where meaning-based matching comes from: auto | ollama | gemini | off
        "rerank": "auto",  # a local model judges which notes belong together (a graphics card helps): auto | off
        "rerank_model": "",  # which one ("": the helper model of this computer's setup)
        "sources": ["books", "classroom"],  # what's read into the graph: books, classroom (filed files), handwritten
        "first": [],  # subjects to do first, e.g. ["deep-learning"]
        "order": "smallest",  # which books first: smallest (fewest pages: most books done soonest) | name
        "commit": True,  # one git commit per batch, when your notes are a repository
        "summary": True,  # one line each morning about what changed
        "duplicates": True,  # each morning, up to 3 pairs of look-alike concept notes: Merge / Keep both / Add alias
        "notation": True,  # a Notation table when a second source writes a concept differently (a switch on the card)
    },
)
STALE_S = 3 * 3600  # a request that didn't come back in this long is asked again
TRIES = 3
PAGE_MARK = re.compile(r'<a id="p-(\d+)"></a>\n## \[p\. \d+\]\n')
SOURCES = ("books", "classroom", "handwritten", "repos")  # what integrate.sources may name
# less text (an announcement, a one-line post) isn't read; repos: a project's README, docs, notebooks' text, paper
MIN_CHARS = {"classroom": 1500, "handwritten": 800, "repos": 600}
PART_CHARS = 3000  # text with no pages of its own is cut into parts of about this many characters (about a page)
SLIDE = re.compile(r"^--- slide \d+ ---$", re.M)  # how Classroom writes out a .pptx (google_classroom._xml_text)
NAMED = {
    "books": ("book", "books"),
    "classroom": ("class file", "class files"),
    "handwritten": ("handwritten", "handwritten"),
    "repos": ("repository file", "repository files"),
}
SEEN_HEAD = {  # what a "Seen in" block calls the lines each source adds to an existing note
    "books": "### Added from the books",
    "classroom": "### Added from class",
    "handwritten": "### Added from your handwritten notes",
    "repos": "### Added from your projects' repositories",
}


def day() -> str:
    return f"{now():%Y-%m-%d}"


def short(text: str, n: int) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def h1(path: Path) -> str | None:
    """A note's title (its first "# " heading), or None."""
    try:
        m = re.search(r"^# (.+)$", Path(path).read_text(encoding="utf-8", errors="replace"), re.M)
    except OSError:
        return None
    return m[1].strip() if m else None


def text_hash(text: str) -> str:
    """What an item is known by: the hash of its text with the spacing evened out (a file downloaded again unchanged
    is the same item; one with a word changed is a new one)."""
    return hashlib.sha256(re.sub(r"\s+", " ", text or "").strip().encode("utf-8")).hexdigest()


def split_pages(text: str) -> tuple[dict[int, str], str]:
    """The pages of an item's text and what they are: a PDF's own pages (pdftotext puts a form feed between them),
    slides, else parts of about PART_CHARS characters cut at paragraphs."""
    t = (text or "").replace("\r\n", "\n")
    if "\f" in t:
        pages = [p.strip() for p in t.split("\f")]
        unit = "pages"
    elif len(SLIDE.findall(t)) >= 2:
        pages = [p.strip() for p in SLIDE.split(t)]
        pages = pages[1:] if not pages[0] else pages
        unit = "slides"
    else:
        pages, cur = [], ""
        for para in re.split(r"\n\s*\n", t):
            if cur and len(cur) + len(para) > PART_CHARS:
                pages.append(cur.strip())
                cur = ""
            cur += para + "\n\n"
            while len(cur) > 2 * PART_CHARS:  # one huge paragraph: cut it
                pages.append(cur[:PART_CHARS].strip())
                cur = cur[PART_CHARS:]
        if cur.strip():
            pages.append(cur.strip())
        unit = "parts"
    while pages and not pages[-1]:
        pages.pop()
    return {i: p for i, p in enumerate(pages, 1)}, unit


class Integrate(Module):
    id = "integrate"
    title = "Concept graph"
    description = (
        "When a book has been read (and when Classroom files a lecture's slides or handouts), weaves its concepts into "
        "your notes: new concept notes, links with their reasons, and the places each concept is met, checked before "
        "anything is written. Never changes your own text."
    )
    privacy = (
        "A few pages of a book's text (or of a class file, or your handwritten notes when you add them) at a time, and "
        "the titles and opening lines of related notes, go to the AI you picked (like any request). The checks and the "
        "matching run on this computer."
    )
    requires = ("books",)
    heavy = True  # night work: on battery it waits for the charger

    def __init__(self, app):
        super().__init__(app)
        self.lock = threading.RLock()
        self._index: cg.Index | None = None
        self._store: cg.VectorStore | None = None
        self.budget = readbudget.Budget(app, lambda: self.roles()[0])  # how much a night (integrate.per_night)
        # each item's batches and what they were planned from (its text file, outline, size): planning splits the whole
        # text, and the dashboard's card asks for every queued item's batches on each request (0.6.1)
        self._plans: dict[str, tuple] = {}
        # each book's page numbers that have text, and what they were read from (its text file's mtime, size, inode)
        self._have: dict[str, tuple] = {}

    # ------------------------------------------------------------------------------------------------- places
    @property
    def dir(self) -> Path:
        return self.app.paths.state / "integrate"

    def load(self, name: str, default):
        return jload(self.dir / name, default)

    def save(self, name: str, data) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        jsave(self.dir / name, data)

    @property
    def books(self):
        return self.app.modules["books"]

    def start(self):
        self.action("soon", lambda p=None: self.tick())
        self.every("night", self.setting("at") or "daily 01:30", self.tick)
        self.every("retry", "every 3h", self.tick)  # carries on after a limit has reset
        self.every("plan", "hourly", self.plan_night)  # tonight's start, from when you wake (alarm, night hours)
        self.plan_night()
        for step in (self.migrate_booklike, self.resume):  # (0.6.1) never in the way of the rest of start
            try:  # textbooks filed from Classroom get a source note of their own; then requests a restart lost are
                step()  # asked again, and tonight's reading carries on
            except Exception as e:
                self.app.events.emit("module_failed", module=self.id, error=f"{step.__name__}: {e}"[:300])
        if self.setting("garden"):
            self.every("garden", "daily 06:20", self.garden)
        if self.setting("summary"):
            self.every("summary", "daily 07:10", self.summary)
        self.every("duplicates", "daily 06:25", lambda p=None: graphmerge.night(self, p))
        jobs = self.app.jobs
        jobs.then_actions["integrate.done"] = self._done
        jobs.then_actions["integrate.checked"] = self._checked
        jobs.then_actions["integrate.linked"] = self._linked

    # --------------------------------------------------------------------------------------------------- roles
    def roles(self) -> tuple[str, str]:
        """(bulk AI, check AI): your choice, else agy and Claude Code when both are installed (they run side by side),
        else the one there is for both, else your main AI. A role whose AI is at its limit (providers/fallback.py)
        goes to the next one set up in the fallback order (brain.fallback, else the automatic one) until the reset,
        so reading goes on, on that AI's own budget (core/readbudget.py keeps one per AI)."""
        want = self.setting("roles") or {}
        avail = []
        for k in providers.AGENT_PROGRAMS:
            b = providers.build(self.app, k)
            if b is not None and b.available()[0]:
                avail.append(k)
        main = self.app.settings.get("brain.main") or ""
        bulk = want.get("bulk") or (avail[0] if avail else main)
        check = want.get("check") or next((k for k in avail if k != bulk), bulk)
        return self.stand_in(bulk), self.stand_in(check)

    def stand_in(self, bid: str) -> str:
        """This role's AI, or while it waits for a limit's reset, the first other one set up in the fallback order."""
        fb = providers.fallback
        if not bid or "rate_limited" not in fb.triggers(self.app) or not fb.cooling(self.app, bid):
            return bid
        other = next((b.id for b in fb.candidates(self.app, {bid}) if not fb.cooling(self.app, b.id)), None)
        return other or bid

    # ------------------------------------------------------------------------------------------------ sources
    def sources(self) -> list[str]:
        """What's read into the graph (integrate.sources), in SOURCES order; unknown names are ignored."""
        v = self.setting("sources")
        if isinstance(v, str):
            v = re.split(r"[,\s]+", v)
        if not isinstance(v, (list, tuple)):
            v = ["books", "classroom"]
        want = {str(x).strip().lower() for x in v}
        return [x for x in SOURCES if x in want]

    def reads(self, source: str) -> bool:
        return source in self.sources()

    @staticmethod
    def source_of(b: dict) -> str:
        """What an item is: "books" for a book (from modules/books.py), else the source it was queued from."""
        return b.get("source") or "books"

    def section(self, b: dict) -> str:
        """Where the ledger keeps it: "books" (as before 0.5.19) or "items" (everything else)."""
        return "books" if self.source_of(b) == "books" else "items"

    def entry(self, led: dict, b: dict) -> dict:
        return (led.get(self.section(b), {}) or {}).get(self.key(b), {}) or {}

    def items(self) -> dict[str, dict]:
        return (self.load("items.json", {}) or {}).get("items", {}) or {}

    def queue_item(
        self,
        source: str,
        text: str,
        subject: str,
        title: str,
        note: str,
        date: str = "",
        course: str = "",
        backfill: bool = False,
        order: int = 0,
    ) -> str | None:
        """Queue a text that isn't a book (a Classroom file, handwritten notes) to be read like one. Its key, or None:
        the graph is off, that source isn't read, there's too little text, or the same text was queued before."""
        if not self.app.is_on(self.id) or not self.reads(source) or source == "books":
            return None
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", subject or ""):
            return None  # no subject, no place for its concept notes
        if len(re.sub(r"\s+", " ", text or "").strip()) < MIN_CHARS.get(source, 1500):
            return None
        h = text_hash(text)[:16]
        key = f"{source}:{h}"
        with self.lock:
            data = self.load("items.json", {}) or {}
            items = data.setdefault("items", {})
            if key in items:
                return None  # read once: the same text filed again isn't read again
            d = self.dir / "texts"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{h}.txt").write_text(text, encoding="utf-8")
            items[key] = {
                "source": source,
                "key": key,
                "id": h,
                "subject": subject,
                "title": short(title or subject, 120),
                "course": course,
                "note": note,
                "date": date,
                "added": now().isoformat(timespec="seconds"),
                "backfill": backfill,
                "order": order,
                "kind": self.kind_for(source, title, text),
                "moved": True,  # (0.6.1) its Seen in lines point at the right note from the start
            }
            self.save("items.json", data)
        self.app.events.emit("integrate_queued", source=source, subject=subject)
        return key

    def queued_items(self) -> list[dict]:
        """The items of the sources read, in the order to read them: what was filed lately, newest first; then what a
        backfill queued, in its order (the oldest course first)."""
        on = set(self.sources())
        items = [it for it in self.items().values() if it.get("source") in on]
        fresh = sorted(
            (it for it in items if not it.get("backfill")),
            key=lambda it: (it.get("date") or "", it.get("added") or ""),
            reverse=True,
        )
        back = sorted((it for it in items if it.get("backfill")), key=lambda it: int(it.get("order") or 0))
        return fresh + back

    def take_classroom(self, batch: dict) -> int:
        """Classroom → notes filed a batch (modules/google_classroom.py): each file in it with real text, and a post
        long enough to be material itself, is queued to be read like a book. How many were queued."""
        if not self.app.is_on(self.id) or not self.reads("classroom"):
            return 0
        cn = self.app.modules.get("classroom_notes")
        folder, course = str(batch.get("folder") or ""), str(batch.get("course") or "")
        n = 0
        for it in batch.get("items") or []:
            post, date = str(it.get("title") or ""), str(it.get("date") or "")
            for f in it.get("files") or []:
                text = cn.file_text(f["file"]) if cn is not None and f.get("chars") and f.get("file") else None
                if not text:
                    continue
                name = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", str(f.get("title") or "")).strip() or post
                note = self.source_note(folder, post, date, [str(f.get("title") or ""), name])
                n += bool(self.queue_item("classroom", text, folder, name, note, date=date, course=course))
            text = str(it.get("text") or "")
            if len(text) >= MIN_CHARS["classroom"]:  # a long post (notes typed into Classroom itself)
                note = self.source_note(folder, post, date, [post])
                n += bool(self.queue_item("classroom", text, folder, post, note, date=date, course=course))
        return n

    def take_handwritten(
        self, note: Path, subject: str, title: str, day: str = "", backfill: bool = False, order: int = 0
    ) -> str | None:
        """Handwritten notes were written out and linked (modules/handwritten_links.py): queue the transcription to be
        read like a book, when integrate.sources has "handwritten"."""
        if not self.app.is_on(self.id) or not self.reads("handwritten"):
            return None
        from kurooto.modules.handwritten_links import parts

        try:
            got = parts(Path(note).read_text(encoding="utf-8"))
        except OSError:
            return None
        if got is None:
            return None
        return self.queue_item(
            "handwritten",
            got[1],
            subject,
            title or Path(note).stem,
            self.rel(note),
            date=day,
            backfill=backfill,
            order=order,
        )

    def backfill_handwritten(self) -> int:
        """Queue the handwritten notes linked before the graph read them: every note handwritten_links has a subject
        for, the oldest day first, after what's written from now on. (Notes not linked yet: /handwritten link links
        them, and each is queued once linked.) Notes queued."""
        if not self.app.is_on(self.id) or not self.reads("handwritten"):
            return 0
        st = jload(self.app.paths.state / "handwritten-links.json", {}) or {}
        order = max((int(it.get("order") or 0) for it in self.items().values()), default=0)
        n = 0
        root = Path(self.app.workspace)
        for rel, rec in sorted((st.get("notes") or {}).items(), key=lambda kv: (kv[1].get("day") or "", kv[0])):
            if not rec.get("subject"):
                continue
            note = root / (rel if rel.endswith(".md") else rel + ".md")
            if not note.is_file():
                continue
            order += 1
            if self.take_handwritten(note, rec["subject"], rec.get("title") or "", rec.get("day") or "", True, order):
                n += 1
        with self.lock:
            data = self.load("items.json", {}) or {}
            data.setdefault("backfill", {})["handwritten"] = now().isoformat(timespec="seconds")
            self.save("items.json", data)
        return n

    def source_note(self, subject: str, title: str, date: str = "", names: list[str] = ()) -> str:
        """The note a class file was filed into, as a [[link]] path: the lecture note Classroom → notes wrote for its
        post (the post's date and title), else a dated note in the subject's folder that names the file, else the
        course page."""
        from kurooto.modules.google_classroom import slugify

        lay = layout.of(self.app)
        if date and title:
            p = lay.path("lecture", subject=subject, date=date, slug=slugify(title))
            if p.is_file():
                return self.rel(p)
        folder = lay.path("lecture", subject=subject, date=date or "2000-01-01", slug="x").parent
        wants = {slugify(n, 200) for n in names if n and len(slugify(n, 200)) >= 5}
        if folder.is_dir() and wants:
            for f in sorted(folder.glob("*.md"), reverse=True):  # dated names: the newest first
                if not re.match(r"\d{4}-\d{2}-\d{2}-", f.name):
                    continue
                try:
                    body = gw.BLOCK_ANY.sub("", f.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    continue
                norm = f"-{slugify(body, 10**9)}-"
                if any(f"-{w}-" in norm for w in wants):
                    return self.rel(f)
        return self.rel(lay.path("course", subject=subject))

    # ---------------------------------------------------------------------------- textbooks filed from Classroom
    @staticmethod
    def kind_for(source: str, title: str, text: str) -> str:
        """ "book" for class material that is a textbook (a course's reading list with the PDF attached), else "class":
        core/studypack.py:is_class, by length (more than 80 pages: a book; 40 or fewer: class material) and then what
        the title says. A text with no pages of its own counts its parts (about a page each); slides are class
        material unless the title says it's a book."""
        if source != "classroom":
            return "class"
        from kurooto.core.studypack import is_class

        pages, unit = split_pages(text)
        n = len(pages) if unit in ("pages", "parts") else 0
        return "class" if is_class(str(title or ""), n, 1) else "book"

    def booklike(self, b: dict) -> bool:
        """A Classroom item that is a textbook (kind_for; worked out once and kept in items.json)."""
        if self.source_of(b) != "classroom":
            return False
        kind = b.get("kind")
        if kind not in ("book", "class"):
            try:
                text = (self.dir / "texts" / f"{b['id']}.txt").read_text(encoding="utf-8")
            except OSError:
                return False
            kind = b["kind"] = self.kind_for("classroom", b.get("title") or "", text)
            self.set_item(b["key"], kind=kind)
        return kind == "book"

    def set_item(self, key: str, **kw) -> None:
        with self.lock:
            data = self.load("items.json", {}) or {}
            it = (data.get("items") or {}).get(key)
            if it is None:
                return
            it.update(kw)
            self.save("items.json", data)

    def book_note(self, b: dict) -> Path:
        """A textbook filed from Classroom: the source note its concepts point to, like a book's index note:
        <subject>/books/<its title>.md (layout "subject"). The same book read by Books already has one there: that
        one. A note of that name that's yours or another item's: <title>-<hash6>.md. Chosen once (items.json
        "source_note")."""
        root = Path(self.app.workspace)
        if b.get("source_note"):
            return root / f"{b['source_note']}.md"
        from kurooto.modules.books import START as BOOK_START
        from kurooto.modules.books import slug

        folder = layout.of(self.app).path("subject", subject=b["subject"]) / "books"
        path = folder / f"{slug(self.title_of(b), 80)}.md"
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            if BOOK_START not in text and f"item={b['key']}" not in text:
                path = folder / f"{path.stem}-{b['id'][:6]}.md"
        b["source_note"] = self.rel(path)
        self.set_item(b["key"], source_note=b["source_note"])
        return path

    def source_block(self, b: dict, path: Path, chap: dict, names: dict[str, str]) -> str:
        """Kurooto's part of a textbook's source note: what it is, where it was filed, what it introduced."""
        lay = layout.of(self.app)
        to = lambda t, label=None: lay.note_link(t, label, from_note=path)  # noqa: E731
        pages, unit = self.item_text(b)
        size = f"{len(pages)} {unit}" if unit != "parts" else "a text with no pages of its own"
        course = lay.path("course", subject=b["subject"])
        where = to(self.rel(course), h1(course)) if course.is_file() else b["subject"]
        post = Path(self.app.workspace) / f"{b['note']}.md"
        filed = f", filed with {to(b['note'], h1(post))}" if post.is_file() and post != course else ""
        lines = [
            f"A textbook from Classroom for {where} ({size}{filed}{', ' + b['date'] if b.get('date') else ''}).",
            "Its concepts point here (Seen in), not to the class note it came with.",
            "",
            "## Concepts in this book",
        ]
        for rec in sorted(chap.values(), key=lambda r: r["first"]):
            links = ", ".join(to(x, names.get(x)) for x in rec["concepts"]) or "(none new)"
            at = self.where({"pages": [rec["first"], rec["last"]], "unit": unit}).strip()
            head = " ".join(x for x in (at, rec.get("title") or "") if x)
            lines.append(f"- {head}: {links}" if head else f"- {links}")
        return "\n".join(lines)

    def write_book_note(self, b: dict, put, linker) -> None:
        """A textbook filed from Classroom: its source note (made, or Kurooto's block in it replaced), and one line
        in the class note it came with pointing at it (the material block that used to list every concept)."""
        path = self.stub(b)
        chap = (self.load("chapters.json", {}) or {}).get(self.key(b), {})
        names = {x: h1(Path(self.app.workspace) / f"{x}.md") for rec in chap.values() for x in rec["concepts"]}
        title = self.title_of(b)
        old = path.read_text(encoding="utf-8") if path.is_file() else None
        from kurooto.modules.books import START as BOOK_START

        if old is not None and BOOK_START in old:
            pass  # the same book read by Books: its index note is Books' own (its concepts block is the book's)
        else:
            body = self.source_block(b, path, chap, names)
            if old is None:
                lay = layout.of(self.app)
                front = lay.frontmatter(None, path, title=title, tags=["book", b["subject"]])
                put(path, None, gw.put_block(f"{front}# {title}\n", "source", body, f"item={b['key']}"))
            else:
                new = gw.put_block(old, "source", body, f"item={b['key']}")
                if new != old:
                    put(path, old, new)
        post = Path(self.app.workspace) / f"{b['note']}.md"
        course = layout.of(self.app).path("course", subject=b["subject"])
        if post.is_file() and post != course and post != path:
            old = post.read_text(encoding="utf-8")
            line = f"Textbook: {linker(post)(self.rel(path), title)} (its concepts are listed there)."
            new = gw.put_block(old, f"material{b['id'][:8]}", line)
            if new != old:
                put(post, old, new)

    def migrate_booklike(self) -> dict:
        """(0.6.1) Textbooks filed from Classroom before 0.6.1 had their concepts' "Seen in" point at the class note
        they came with (a reading list, say), which made that note a hub of hundreds of links. Each such item now gets
        its own source note (book_note), and the "Seen in" blocks of its concepts point there; only Kurooto's blocks
        change (guarded), each file's before-copy is kept in undo/<subject>-<id>-moved.json, and it's one git commit
        per item. Runs at start; an item done is marked "moved", so it's once. {"items", "notes"} moved."""
        out = {"items": 0, "notes": 0}
        if not self.app.is_on(self.id):
            return out
        todo = [
            it
            for it in self.items().values()
            if it.get("source") == "classroom" and not it.get("moved") and self.booklike(it)
        ]
        if not todo:
            return out
        with self.lock:
            seen = self.load("seen.json", {}) or {}
            for it in todo:
                n = self.move_item(it, seen)
                self.set_item(it["key"], moved=True)
                if n is not None:
                    out["items"] += 1
                    out["notes"] += n
            self.save("seen.json", seen)
        if out["items"]:
            self.app.events.emit("integrate_moved", **out)
        return out

    def move_item(self, it: dict, seen: dict) -> int | None:
        """One textbook item's move (migrate_booklike): its rows in `seen` (changed in place) and its concepts' "Seen
        in" blocks point at its source note, which is written. Notes changed, or None when nothing was written."""
        root, lay, key = Path(self.app.workspace), layout.of(self.app), it["key"]
        to = self.rel(self.book_note(it))
        slugs = [s for s, rows in seen.items() if any(r.get("book") == key and r.get("note") != to for r in rows)]
        done = self.entry(self.load("ledger.json", {}), it).get("batches", {})
        if not slugs and not any((r or {}).get("state") == "done" for r in done.values()):
            return None  # not read yet: its concepts will point at its own note
        journal: dict[str, str | None] = {}

        def put(path: Path, old: str | None, new: str) -> bool:
            if old is not None and not gw.guarded(old, new).ok:
                self.app.events.emit("integrate_refused", note=str(path.name), why="moving Seen in")
                return False
            journal[str(path)] = old
            write_note_file(path, new, create=old is None)
            return True

        def linker(note: Path):
            return lambda t, label=None: lay.note_link(t, label, from_note=note)

        n = 0
        for s in slugs:
            for r in seen[s]:
                if r.get("book") == key:
                    r["note"] = to
            path = root / f"{s}.md"
            try:
                old = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if re.search(r"<!-- kurooto:seen\b", old):
                new = gw.put_block(old, "seen", self.seen_body(seen[s], linker(path)))
                n += new != old and put(path, old, new)
        self.write_book_note(it, put, linker)
        if not journal:
            return None
        self.undo(it, "moved", journal)
        title = short(self.title_of(it), 40)
        self.commit(list(journal), f"graph: {title} is a textbook: its concepts' Seen in points at its own note")
        return n

    def backfill_classroom(self) -> tuple[int, int]:
        """Queue the Classroom files filed before the graph read them (before 0.5.19): the oldest course first, each
        course's files oldest first, after what's filed from now on. Read within each night's budget like the rest.
        (files queued, courses)."""
        from kurooto.modules.google_classroom import TEXT_EXT, slugify

        cn = self.app.modules.get("classroom_notes")
        if cn is None or not self.app.is_on(self.id) or not self.reads("classroom"):
            return 0, 0
        known = jload(cn.dir / "folders.json", {}) or {}
        folders = set(known.values()) | {slugify(v) for v in (cn.setting("folders") or {}).values() if v}
        found: dict[str, list[tuple[str, str, str]]] = {}  # folder -> [(date, title, text)]
        for root in dict.fromkeys([cn.files_dir, self.app.paths.data / "classroom"]):
            for folder in sorted(folders):
                d = root / folder
                if not d.is_dir():
                    continue
                for f in sorted(d.iterdir()):
                    if not f.is_file() or (f.suffix == ".txt" and f.with_suffix("").is_file()):
                        continue  # a file's text beside it: read with the file
                    side = f.with_name(f.name + ".txt")
                    src = side if side.is_file() else f if f.suffix.lower() in TEXT_EXT else None
                    if src is None:
                        continue
                    try:
                        text = src.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    m = re.match(r"(\d{4}-\d{2}-\d{2})-(.*)$", f.stem)
                    date, rest = (m[1], m[2]) if m else ("", f.stem)
                    if len(rest) > 7 and rest[-7] == "-":
                        rest = rest[:-7]  # the Drive file's id, after its name
                    title = rest.replace("-", " ").strip()
                    found.setdefault(folder, []).append((date, title[:1].upper() + title[1:], text))
        course_of = {v: k for k, v in known.items()}
        order = max((int(it.get("order") or 0) for it in self.items().values()), default=0)
        n, courses = 0, set()
        for folder in sorted(found, key=lambda f: (min(x[0] or "9999" for x in found[f]), f)):
            for date, title, text in sorted(found[folder], key=lambda x: (x[0], x[1])):
                order += 1
                note = self.source_note(folder, "", date, [title])
                if self.queue_item(
                    "classroom", text, folder, title, note, date, course_of.get(folder, ""), backfill=True, order=order
                ):
                    n += 1
                    courses.add(folder)
        with self.lock:
            data = self.load("items.json", {}) or {}
            data.setdefault("backfill", {})["classroom"] = now().isoformat(timespec="seconds")
            self.save("items.json", data)
        return n, len(courses)

    # -------------------------------------------------------------------------------------------------- books
    def pages_of(self, b: dict) -> dict[int, str]:
        if self.source_of(b) != "books":
            return self.item_text(b)[0]
        f = self.books.book_dir(b) / "text.md"
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            return {}
        parts = PAGE_MARK.split(text)
        return {int(parts[i]): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}

    def pages_read(self, b: dict) -> set[int]:
        """A book's page numbers that have text: pages_of's, kept while its text file stays the same (the dashboard's
        card asks for every book's on each request, 0.6.1)."""
        f = self.books.book_dir(b) / "text.md"
        try:
            st = f.stat()
        except OSError:
            return set()
        sig = (st.st_mtime_ns, st.st_size, st.st_ino)
        kept = self._have.get(str(f))
        if kept and kept[0] == sig:
            return set(kept[1])
        pages = frozenset(self.pages_of(b))
        self._have[str(f)] = (sig, pages)
        return set(pages)

    def item_text(self, b: dict) -> tuple[dict[int, str], str]:
        """An item's pages and what they are (pages, slides or parts), from the copy of its text."""
        try:
            text = (self.dir / "texts" / f"{b['id']}.txt").read_text(encoding="utf-8")
        except OSError:
            return {}, "parts"
        return split_pages(text)

    def key(self, b: dict) -> str:
        if self.source_of(b) != "books":
            return b["key"]
        return f"{b['subject']}/{b['id']}"

    def title_of(self, b: dict) -> str:
        if self.source_of(b) != "books":
            return b.get("title") or b["id"]
        return self.books.meta(b).get("title") or b["id"]

    def stub(self, b: dict) -> Path:
        """The note an item's concepts point back to ("Seen in"): a book's index note; the note a class file was filed
        into, or, for a textbook filed from Classroom, a source note of its own (book_note); the handwritten note
        itself."""
        if self.booklike(b):  # a textbook filed from Classroom: a source note of its own, like a book's (0.6.1)
            return self.book_note(b)
        if self.source_of(b) != "books":
            return Path(self.app.workspace) / f"{b['note']}.md"
        return layout.of(self.app).path("subject", subject=b["subject"]) / "books" / f"{b['id']}.md"

    def plan(self, b: dict, led: dict | None = None) -> list[segment.Batch]:
        """The batches of a book, over all its pages: its sections (from its bookmarks, as the chapter list has them,
        else from the page text), sized by integrate.batch_pages. A book whose batches began before 0.5.8 keeps the
        batches it began with (the ledger's "plan": "text": no bookmarks, up to the last page read), so nothing is
        asked twice. Anything else: its sections from its text, the same way. `led`: the ledger, when the caller has
        just read it (ready_batches: reading it again for every book was half the dashboard's request, 0.6.1)."""
        books = self.source_of(b) == "books"
        f = self.books.book_dir(b) / "text.md" if books else self.dir / "texts" / f"{b['id']}.txt"
        try:
            st = f.stat()
            sig: tuple = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = ()
        if not books:
            size = int(self.setting("batch_pages") or 12)
            made_from: tuple = (sig, size)
        else:
            meta = self.books.meta(b)
            led = self.load("ledger.json", {}) if led is None else led
            bk = (led.get("books", {}) or {}).get(self.key(b), {}) or {}
            outline: list[tuple[int, str, int]] = []
            by_outline = bk.get("plan", "text" if bk.get("batches") else "outline") == "outline"
            if by_outline:
                outline = [(int(lv), str(t), int(p)) for lv, t, p in meta.get("outline") or [] if p]
            size = int(self.setting("batch_pages") or segment.TARGET)
            made_from = (sig, size, by_outline, tuple(outline), int(meta.get("pages") or 0))
        kept = self._plans.get(self.key(b))
        if kept and kept[0] == made_from:
            return list(kept[1])
        pages = self.pages_of(b)
        if not books:
            total = max(pages) if pages else 0
            out = segment.batches(segment.sections(pages, [], total), total, size)
        else:
            total = (made_from[4] if by_outline else 0) or (max(pages) if pages else 0)
            out = segment.batches(segment.sections(pages, outline, total), total, size)
        self._plans[self.key(b)] = (made_from, out)
        return list(out)

    def ready_batches(self) -> list[tuple[dict, segment.Batch]]:
        """Every batch not done yet whose pages have all been read, in the order to do them: class material (newest
        first) and handwritten notes, then a backfill's, then the books."""
        self.inflight()  # forget requests that never came back, so they're asked again
        led = self.load("ledger.json", {})
        out = []
        for it in self.queued_items():
            done_batches = self.entry(led, it).get("batches", {})
            for bt in self.plan(it, led):
                if (done_batches.get(bt.id, {}) or {}).get("state") not in ("done", "failed", "queued", "checking"):
                    out.append((it, bt))
        if not self.reads("books"):
            return out
        first = [str(x) for x in self.setting("first") or []]
        library = self.books.library()
        metas = {self.key(b): self.books.meta(b) for b in library}
        smallest = str(self.setting("order") or "smallest") == "smallest"

        def rank(b: dict):
            pages = int(metas[self.key(b)].get("pages") or 0) if smallest else 0
            return (b["subject"] not in first, pages, b["subject"], b["id"])

        for b in sorted(library, key=rank):
            meta = metas[self.key(b)]
            if not meta.get("pages") or not meta.get("done"):
                continue
            # a page is ready when its text is there; one the reader skipped (waiting for OCR, say) doesn't hold its
            # batch back once the book's reading pass is over ("done" counts pages read, not the last page number)
            have = self.pages_read(b) | ({int(n) for n in meta.get("skipped") or {}} if meta.get("finished") else set())
            done_batches = (led.get("books", {}).get(self.key(b), {}) or {}).get("batches", {})
            for bt in self.plan(b, led):
                rec = done_batches.get(bt.id, {})
                if rec.get("state") in ("done", "failed", "queued", "checking"):
                    continue
                if all(p in have for p in range(bt.first, bt.last + 1)):
                    out.append((b, bt))
        return out

    # ---------------------------------------------------------------------------------------------- the ledger
    def record(self, b: dict, bt_id: str, **kw) -> dict:
        with self.lock:
            led = self.load("ledger.json", {})
            bk = led.setdefault(self.section(b), {}).setdefault(self.key(b), {})
            # how plan() cuts the book, fixed at its first batch: "text" for one begun before bookmarks were used
            bk.setdefault("plan", "text" if bk.get("batches") else "outline")
            rec = bk.setdefault("batches", {}).setdefault(bt_id, {})
            rec.update(kw)
            rec["at"] = now().isoformat(timespec="seconds")
            self.save("ledger.json", led)
            return rec

    def spend(self, result) -> None:
        """Count a request's cost as the AI program reports it (Claude Code gives it in dollars at API prices: on a
        plan nothing is billed, but it says how big the request was) and the request itself."""
        cost = float((getattr(result, "usage", None) or {}).get("cost") or 0)
        self.bump_night(requests=1, cost=round(cost, 5))

    def bump_night(self, **inc) -> None:
        with self.lock:
            led = self.load("ledger.json", {})
            n = led.setdefault("nights", {}).setdefault(day(), {})
            for k, v in inc.items():
                n[k] = n.get(k, 0) + v
            led["nights"] = dict(sorted(led["nights"].items())[-30:])
            self.save("ledger.json", led)

    def inflight(self) -> tuple[int, int]:
        """(bulk requests out, second looks out). A request out for too long (STALE_S) is forgotten, and so, at once,
        is one whose job is gone from the job queue (a restart or an update cut it off before its answer was written,
        say: core/jobs.py:settled); either is asked again."""
        with self.lock:
            led = self.load("ledger.json", {})
            bulk = chk = 0
            changed = False
            for bk in [*led.get("books", {}).values(), *led.get("items", {}).values()]:
                for rec in bk.get("batches", {}).values():
                    if rec.get("state") not in ("queued", "checking"):
                        continue
                    age = time.time() - (dt.datetime.fromisoformat(rec["at"]).timestamp() if rec.get("at") else 0)
                    if age > STALE_S or self.lost(rec):
                        if rec["state"] == "checking" and rec.get("job"):  # its second look won't come: no leftovers
                            (self.dir / "pending" / f"{rec['job']}.json").unlink(missing_ok=True)
                        rec["state"] = "pending"
                        rec["why"] = "asked again: its request " + ("took too long" if age > STALE_S else "was lost")
                        changed = True
                    elif rec["state"] == "queued":
                        bulk += 1
                    else:
                        chk += 1
            if changed:
                self.save("ledger.json", led)
        return bulk, chk

    def lost(self, rec: dict) -> bool:
        """A queued or checking batch whose request no longer is in the job queue, and whose answer will never come:
        Kurooto restarted (an update, a crash) after the job had ended but before its answer was written, or the job
        is gone. One that a restart cut off mid-run isn't lost: the job queue runs it again (Jobs.recover)."""
        jid = rec.get("check_job") if rec.get("state") == "checking" else rec.get("job")
        settled = getattr(self.app.jobs, "settled", None)
        return bool(jid) and settled is not None and settled(jid)

    # ---------------------------------------------------------------------------------------------------- tick
    def index(self, refresh: bool = True) -> cg.Index:
        """The notes' index (rebuilt from the files: they change as batches are written)."""
        if self._store is None:
            self._store = cg.VectorStore(self.dir / "vectors.db")
        emb = cg.make_embedder(self.app) if str(self.setting("embeddings") or "auto") != "off" else None
        from kurooto.core.rerank import make_reranker

        return cg.Index(cg.scan(self.app), emb, self._store if emb else None, make_reranker(self.app))

    def stopped_until(self) -> dt.datetime | None:
        """After /graph stop: when the next night's start lifts it (kept in stopped.json, so a restart keeps it)."""
        until = (self.load("stopped.json", {}) or {}).get("until")
        if not until or float(until) <= now().timestamp():
            return None
        return dt.datetime.fromtimestamp(float(until))

    def hold(self) -> dt.datetime:
        """Start no more batches (the nightly start, the 3-hourly retry, the 20-minute retry, a book just read or a
        batch's answer) until the next night's start; /graph now goes on at once."""
        from kurooto.core.scheduler import next_after

        tz = self.app.scheduler.tz
        nxt = next_after(self.setting("at") or "daily 01:30", now().astimezone(tz), tz).astimezone(tz)
        self.save("stopped.json", {"until": nxt.timestamp()})  # the night's own start goes ahead
        self.app.scheduler.cancel(f"{self.id}:soon")
        return nxt.replace(tzinfo=None)

    def tick(self, payload: dict | None = None) -> dict:
        """Ask for the next batch (one bulk request at a time per AI; second looks run beside it)."""
        if not self.app.is_on(self.id):
            return {}
        out = {"submitted": 0}
        if self.stopped_until():
            return {**out, "stopped": True}
        bulk_out, _ = self.inflight()
        if bulk_out:
            return out
        stop = self.budget.gate()  # tonight's budget, or a limit's reset (core/readbudget.py)
        if stop:
            return {**out, **stop}
        todo = self.ready_batches()
        if not todo:
            return {**out, "idle": True}
        b, bt = todo[0]
        self.submit_batch(b, bt)
        out["submitted"] = 1
        return out

    def plan_night(self, payload: dict | None = None) -> None:
        """Start the next night early when you wake early: 5 hours before, so a 5-hour usage window the reading opens
        has reset when you get up (integrate.at stays the latest start)."""
        nxt = self.budget.next_start()
        if nxt and nxt[0] < nxt[1]:
            self.app.scheduler.at(nxt[0], "integrate.soon", key=f"{self.id}:early", module=self.id)
        else:
            self.app.scheduler.cancel(f"{self.id}:early")

    def resume(self) -> bool:
        """Kurooto (re)started, after an update, say: batches whose requests the restart lost go back to pending at
        once (inflight), and when it's inside tonight's reading window (Budget.window), not held by /graph stop,
        nothing is in flight and the budget gate lets a batch go, the night carries on in a minute through the
        nightly start's own path (integrate.soon: tick), instead of waiting for tomorrow's integrate.at. True when
        that was booked."""
        if not self.app.is_on(self.id):
            return False
        bulk, _ = self.inflight()
        if bulk or self.stopped_until() or not self.budget.in_window() or self.budget.gate():
            return False
        self.app.scheduler.at(now() + dt.timedelta(minutes=1), "integrate.soon", key=f"{self.id}:soon", module=self.id)
        return True

    def poke(self) -> None:
        """A book was read: carry on tonight (the schedule would only start it at integrate.at)."""
        if self.app.is_on(self.id):
            threading.Thread(target=self.tick, name="integrate", daemon=True).start()

    def submit_batch(self, b: dict, bt: segment.Batch) -> str:
        pages = self.pages_of(b)
        title, src = self.title_of(b), self.source_of(b)
        index = self.index()
        text = ai.page_text(pages, bt.first, bt.last)
        near = index.candidates(f"{bt.title}. {text[:3000]}", "", None, limit=30, rerank=False)
        prompt = ai.batch_prompt(
            title,
            b["subject"],
            bt.first,
            bt.last,
            bt.title,
            ai.cards_text(index, [c.slug for c in near]),
            text,
            source=src,
            unit=self.item_text(b)[1] if src != "books" else "pages",
        )
        bulk, _ = self.roles()
        where = f"pp. {bt.first}-{bt.last}" if src == "books" else f"({NAMED[src][0]}, {bt.first}-{bt.last})"
        jid = self.app.jobs.submit(
            prompt,
            title=f"Concepts: {short(title, 40)} {where}",
            effort=self.effort_for(b, bt),
            background=True,
            text_only=True,
            quiet=True,
            lane="bg",
            brain=bulk or None,
            then="integrate.done",
            then_payload={"book": self.key(b), "batch": bt.id, "first": bt.first, "last": bt.last, "title": bt.title},
        )
        self.record(b, bt.id, state="queued", job=jid, tries=self.tries(b, bt.id))
        return jid

    def effort_for(self, b: dict, bt: segment.Batch) -> str:
        """The effort (so the model size) for a batch: the small, quick one by default; the next one up for a batch
        that failed before, and for a book whose recent batches needed many second looks (its text is hard)."""
        if self.tries(b, bt.id):
            return "medium"
        recs = list(self.entry(self.load("ledger.json", {}), b).get("batches", {}).values())
        recent = [r for r in recs if r.get("state") == "done"][-3:]
        concepts = sum(int(r.get("concepts") or 0) for r in recent)
        flagged = sum(int(r.get("flagged") or 0) for r in recent)
        return "medium" if concepts >= 4 and flagged / concepts > 0.3 else "low"

    def tries(self, b: dict, bid: str) -> int:
        led = self.load("ledger.json", {})
        return int((self.entry(led, b).get("batches", {}).get(bid, {}) or {}).get("tries", 0))

    def find_book(self, key: str) -> dict | None:
        """A book (by "subject/id") or another item (by "source:hash") from its key."""
        item = self.items().get(key)
        if item is not None:
            return item
        return next((b for b in self.books.library() if self.key(b) == key), None)

    # --------------------------------------------------------------------------------------------- the answer
    def _done(self, job, result, payload: dict) -> None:
        b = self.find_book(payload["book"])
        if b is None:
            return
        bid = payload["batch"]
        self.spend(result)
        self.budget.seen(job, result)
        data = ai.parse_json(result.text) if result.ok else None
        if data is None and getattr(result, "verdict", None) in (Verdict.RATE_LIMITED, Verdict.AUTH):
            # the AI's limit (or its sign-in): nothing is wrong with the batch; it's asked again later (every few
            # hours, and at night), without counting as a failed try
            self.record(b, bid, state="pending", why=short(result.detail or result.verdict.value, 120))
            self.app.events.emit("integrate_waiting", why=result.verdict.value)
            # try again in 20 minutes: often only the stand-in AI was signed out or at its limit, and the main one is
            # fine again by then (the 3-hourly retry is the fallback)
            self.app.scheduler.at(
                now() + dt.timedelta(minutes=20), "integrate.soon", key=f"{self.id}:soon", module=self.id
            )
            return
        if data is None:
            tries = self.tries(b, bid) + 1
            self.record(
                b,
                bid,
                state="pending" if tries < TRIES else "failed",
                tries=tries,
                why=short(result.detail or "no usable answer", 120),
            )
            self.bump_night(failed=1 if tries >= TRIES else 0)
            self.tick()
            return
        pages = self.pages_of(b)
        index = self.index()
        concepts = ai.read_batch(data)
        self.assign(concepts, index, b)
        names = {c.name_key: c.slug for c in concepts if c.slug}
        concepts, items = ai.check(concepts, index, pages, names)
        payload = {**payload, "job": job.id}
        if not items:
            self.write(b, payload, concepts, index, flagged=0, dropped=0)
            self.tick()
            return
        pend = self.dir / "pending"
        pend.mkdir(parents=True, exist_ok=True)
        ser = [
            {
                "id": it.id,
                "kind": it.kind,
                "ci": concepts.index(it.concept),
                "li": it.concept.links.index(it.link) if it.link else -1,
                "target": it.target,
                "why": it.why,
            }
            for it in items
        ]
        (pend / f"{job.id}.json").write_text(
            json.dumps({"concepts": [asdict(c) for c in concepts], "items": ser}, ensure_ascii=False), encoding="utf-8"
        )
        _, chk = self.roles()
        prompt = ai.CHECK_PROMPT.format(
            items=ai.items_text(items, index, names, pages), relations=", ".join(gw.RELATIONS)
        )
        jid = self.app.jobs.submit(
            prompt,
            title=f"Second look: {short(payload['title'], 40)}",
            effort="medium",
            background=True,
            text_only=True,
            quiet=True,
            lane="chk",
            brain=chk or None,
            then="integrate.checked",
            then_payload={**payload, "pending": job.id},
        )
        self.record(b, bid, state="checking", check_job=jid)
        self.tick()  # the next batch goes while this one is looked at

    def assign(self, concepts: list[ai.Proposed], index: cg.Index, b: dict) -> None:
        """Slugs for the concepts: an existing note when the name matches one (so no duplicate is made)."""
        taken = set(index.notes)
        lay = layout.of(self.app)
        for c in concepts:
            if c.role != "core":
                continue
            if not c.same_as:
                hit, _ = index.match_name(c.name, c.aliases)
                if hit:
                    c.same_as = hit
            if c.same_as and c.same_as in index.notes:
                c.slug = c.same_as
                continue
            c.slug = self.fresh_slug(c, b, taken, lay)

    def fresh_slug(self, c: ai.Proposed, b: dict, taken: set[str], lay=None) -> str:
        """A new note's slug for a concept: its name, with -2, -3... when that's taken."""
        lay = lay or layout.of(self.app)
        base = cg.slug_of(c.name)
        slug_path = lay.path("concept", subject=b["subject"], slug=base)
        rel = self.rel(slug_path)
        n = 2
        while rel in taken or slug_path.exists():
            slug_path = lay.path("concept", subject=b["subject"], slug=f"{base}-{n}")
            rel = self.rel(slug_path)
            n += 1
        taken.add(rel)
        return rel

    def rel(self, path: Path) -> str:
        return Path(path).relative_to(Path(self.app.workspace)).with_suffix("").as_posix()

    def _checked(self, job, result, payload: dict) -> None:
        b = self.find_book(payload["book"])
        pend = self.dir / "pending" / f"{payload['pending']}.json"
        if b is None or not pend.is_file():
            return
        saved = json.loads(pend.read_text(encoding="utf-8"))
        concepts = [self.revive(d) for d in saved["concepts"]]
        items = [
            ai.Item(
                s["id"],
                s["kind"],
                concepts[s["ci"]],
                concepts[s["ci"]].links[s["li"]] if s["li"] >= 0 else None,
                s["target"],
                s["why"],
            )
            for s in saved["items"]
        ]
        self.spend(result)
        self.budget.seen(job, result)
        answer = ai.parse_json(result.text) if result.ok else None
        kept, dropped = ai.apply_second_look(items, answer)
        pend.unlink(missing_ok=True)
        index = self.index()
        taken = set(index.notes) | {c.slug for c in concepts if c.slug}
        for c in concepts:  # a merge the second look turned down: a note of its own, not lines in the other one
            if c.role == "core" and not c.same_as and c.slug in index.notes:
                c.slug = self.fresh_slug(c, b, taken)
        self.write(b, payload, concepts, index, flagged=len(items), dropped=dropped)
        self.tick()

    @staticmethod
    def revive(d: dict) -> ai.Proposed:
        d = dict(d)
        d["links"] = [ai.Link(**lk) for lk in d.get("links", [])]
        return ai.Proposed(**d)

    # ---------------------------------------------------------------------------------------------- writing
    def write(self, b: dict, payload: dict, concepts: list[ai.Proposed], index: cg.Index, flagged: int, dropped: int):
        """Write what survived into the notes, then commit. Returns the counts."""
        lay = layout.of(self.app)
        root = Path(self.app.workspace)
        bid, first, last = payload["batch"], payload["first"], payload["last"]
        src = self.source_of(b)
        stub = self.stub(b)
        stub_slug = self.rel(stub)
        title = self.title_of(b)
        journal: dict[str, str | None] = {}
        counts = {"new": 0, "same": 0, "links": 0, "skipped": 0}
        seen = self.load("seen.json", {})
        notation = self.load("notation.json", {}) or {}
        made = self.load("made.json", {}) or {}
        core = [c for c in concepts if c.role == "core" and c.slug]
        names_by_slug = {c.slug: c for c in core}  # only what gets a note: a dropped concept is linked by nobody

        def put(path: Path, old: str | None, new: str) -> bool:
            if old is not None:
                chk = gw.guarded(old, new)
                if not chk.ok:
                    self.app.events.emit("integrate_refused", note=str(path.name), why=chk.why)
                    counts["skipped"] += 1
                    return False
            journal[str(path)] = old
            write_note_file(path, new, create=old is None)
            return True

        style = lay.note_style

        def linker(note: Path):
            """Links written into `note`, in your link style (notes.links)."""
            return lambda target, label=None: lay.note_link(target, label, from_note=note)

        for c in core:
            path = root / f"{c.slug}.md"
            here = f"{c.slug}.md"
            entry = {"book": self.key(b), "note": stub_slug, "title": title, "batch": bid, "pages": [first, last]}
            if src != "books":
                entry |= {"source": src, "unit": self.item_text(b)[1]}
            entry["update"] = c.update if c.same_as else ""
            entry["def"] = short(c.definition, 160) if not c.same_as else ""
            rows = seen.setdefault(c.slug, [])
            prev = next((r for r in rows if r["book"] == entry["book"] and r["batch"] == bid), None)
            if prev:  # the same batch again (the concept is now a note): keep what the first time said
                entry["def"] = entry["def"] or prev.get("def", "")
                entry["update"] = entry["update"] or prev.get("update", "")
            rows[:] = [r for r in rows if r is not prev] + [entry]
            marks = self.add_notation(notation, c, entry, title, first, last)
            table = self.notation_body(marks) if self.notation_on() else ""
            lines = [
                (lk.target, gw.link_line(lk.relation, lk.target, lk.reason, style, here))
                for lk in c.links
                if lk.target != c.slug and (lk.target in index.notes or lk.target in names_by_slug)
            ]
            old = path.read_text(encoding="utf-8") if path.is_file() else None
            if old is None:
                front = lay.frontmatter("concept", path, title=c.name, subject=b["subject"], tags=None)
                front = self.with_aliases(front, c.name, c.aliases)
                body = gw.new_note(
                    front,
                    gw.Concept(c.name, c.slug, c.aliases, c.definition, c.formulas, c.kind),
                    [ln for _, ln in lines],
                    f"Source: {title}{self.where({'pages': [first, last], **entry}, ',')}",
                )
                body = gw.put_block(body, "seen", self.seen_body(seen[c.slug], linker(path)))
                if table:
                    body = gw.put_block(body, "notation", table)
                if put(path, None, body):
                    made[c.slug] = gw.outside_hash(body)  # what Kurooto wrote: a merge may move it (graphmerge)
                    counts["new"] += 1
                    counts["links"] += len(lines)
            else:
                new, added = gw.add_links(old, lines, here)
                new = gw.put_block(new, "seen", self.seen_body(seen[c.slug], linker(path)))
                if table:
                    new = gw.put_block(new, "notation", table)
                new = self.add_alias(new, c.name, c.aliases)
                if new != old and put(path, old, new):
                    counts["same"] += 1
                    counts["links"] += added
        self.save("seen.json", seen)
        self.save("notation.json", notation)
        self.save("made.json", made)
        # the chapter note lists what it introduces
        chap = self.load("chapters.json", {})
        bk = chap.setdefault(self.key(b), {})
        bk[bid] = {"first": first, "last": last, "title": payload.get("title", ""), "concepts": [c.slug for c in core]}
        self.save("chapters.json", chap)
        course = lay.path("course", subject=b["subject"])
        if stub.is_file() and src == "books":
            old = stub.read_text(encoding="utf-8")
            new = gw.put_block(old, "concepts", self.chapter_body(bk, names_by_slug, index, linker(stub)))
            if new != old:
                put(stub, old, new)
        elif src == "classroom" and self.booklike(b):
            self.write_book_note(b, put, linker)
        elif stub.is_file() and src == "classroom" and stub != course:
            # the lecture note it was filed into lists what it introduces, in a block of its own per file
            slugs = list(dict.fromkeys(x for rec in bk.values() for x in rec["concepts"]))
            to = linker(stub)
            body = f"## Concepts in {title}\n" + (", ".join(to(x) for x in slugs) or "(none new)")
            old = stub.read_text(encoding="utf-8")
            new = gw.put_block(old, f"material{b['id'][:8]}", body)
            if new != old:
                put(stub, old, new)
        # the course map lists the concepts the books introduced, in a block of its own
        if course.is_file() and src == "books":
            slugs: list[str] = []
            for key, rec in chap.items():
                if key.split("/")[0] == b["subject"]:
                    for batch in rec.values():
                        slugs += [x for x in batch["concepts"] if x not in slugs]
            if slugs:
                names = {
                    x: index.notes[x].title if x in index.notes else names_by_slug[x].name
                    for x in slugs
                    if x in index.notes or x in names_by_slug
                }
                to = linker(course)
                body = "## From the books\n" + "\n".join(
                    f"- {to(x, n)}" for x, n in sorted(names.items(), key=lambda kv: kv[1].lower())
                )
                old = course.read_text(encoding="utf-8")
                new = gw.put_block(old, "books", body)
                if new != old:
                    put(course, old, new)
        self.undo(b, bid, journal)
        at = f" pp. {first}-{last}" if src == "books" else ""
        sha = self.commit(
            list(journal),
            f"{src}: {short(title, 40)}{at} "
            f"(+{counts['new']} notes, +{counts['links']} links, {counts['same']} updated)",
        )
        self.record(
            b, bid, state="done", concepts=len(core), flagged=flagged, dropped=dropped, commit=sha or "", **counts
        )
        self.bump_night(
            batches=1,
            new=counts["new"],
            links=counts["links"],
            updated=counts["same"],
            flagged=flagged,
            dropped=dropped,
        )
        job = self.app.jobs.get(payload["job"]) if payload.get("job") else None
        self.budget.count(job.brain if job is not None and job.brain else None)  # the AI that read it: its budget
        self.queue_garden([c.slug for c in core])
        graphmerge.fresh(self, [c.slug for c in core])
        self.app.events.emit("integrate_batch", book=self.key(b), batch=bid, **counts)
        return counts

    def add_notation(self, notation: dict, c: ai.Proposed, entry: dict, title: str, first: int, last: int) -> list:
        """This batch's notation rows for a concept (checked already: integrate_ai.check_notation) in place of what the
        same batch said before; the concept's rows from every source, in the table's order."""
        mine = (entry["book"], entry["batch"])
        rows = [r for r in notation.get(c.slug) or [] if (r["book"], r["batch"]) != mine]
        label = f"{title}{self.where({**entry, 'pages': [first, last]}, ',')}"
        have = {(r["book"], ai.squash(r["symbol"])) for r in rows}
        for n in c.notation:
            if (entry["book"], ai.squash(n["symbol"])) in have:
                continue
            have.add((entry["book"], ai.squash(n["symbol"])))
            rows.append({"book": entry["book"], "batch": entry["batch"], "source": label, **n})
        rows.sort(key=lambda r: (r.get("what", "").lower(), r["source"]))
        if rows:
            notation[c.slug] = rows
        else:
            notation.pop(c.slug, None)
        return rows

    def notation_on(self) -> bool:
        """Notation tables whenever the graph reads (books, class files, handwritten notes), unless
        integrate.notation is off (a switch on this card and in Settings)."""
        return bool(self.setting("notation"))

    @staticmethod
    def notation_body(rows: list[dict]) -> str:
        """The "Notation" table, when two sources write the concept differently ("" otherwise)."""
        return gw.notation_table(rows)

    @staticmethod
    def with_aliases(front: str, name: str, aliases: list[str]) -> str:
        names = [name] + [a for a in aliases if a.lower() != name.lower()]
        if not re.search(r"^aliases:", front, re.M):
            return front
        return re.sub(
            r"^aliases:.*$",
            "aliases: [" + ", ".join(json.dumps(n, ensure_ascii=False) for n in names) + "]",
            front,
            count=1,
            flags=re.M,
        )

    @staticmethod
    def add_alias(text: str, name: str, aliases: list[str]) -> str:
        m = re.search(r"^aliases:\s*\[(.*)\]\s*$", text, re.M)
        if not m:
            return text
        have = [x.strip().strip("\"'") for x in m[1].split(",") if x.strip()]
        low = {h.lower() for h in have}
        add = [
            n
            for n in [name, *aliases]
            if n and n.lower() not in low and cg.normalise(n) not in {cg.normalise(h) for h in have}
        ]
        if not add:
            return text
        new = "aliases: [" + ", ".join(json.dumps(x, ensure_ascii=False) for x in [*have, *add]) + "]"
        return text[: m.start()] + new + text[m.end() :]

    @staticmethod
    def where(r: dict, sep: str = "") -> str:
        """Where in its source a row is: " pp. 3–14" for a book or a PDF's pages, " slides 2–9", nothing for parts of
        a text with no pages of its own."""
        a, z = r["pages"]
        unit = r.get("unit") or "pages"
        return f"{sep} pp. {a}–{z}" if unit == "pages" else f"{sep} slides {a}–{z}" if unit == "slides" else ""

    @classmethod
    def seen_body(cls, rows: list[dict], link=None) -> str:
        """The "Seen in" block; `link(target, label)` writes a link (default: [[wikilinks]])."""
        link = link or _wiki
        rows = sorted(rows, key=lambda r: (r["book"], r["pages"][0]))
        lines = ["## Seen in"]
        lines += dict.fromkeys(f"- {link(r['note'], r['title'])}{cls.where(r)}" for r in rows)
        for src, head in SEEN_HEAD.items():
            ups = [r for r in rows if r.get("update") and (r.get("source") or "books") == src]
            if ups:
                lines += ["", head]
                lines += [f"- {r['title']}{cls.where(r)}: {r['update']}" for r in ups]
        return "\n".join(lines)

    @staticmethod
    def chapter_body(bk: dict, names: dict, index: cg.Index, link=None) -> str:
        link = link or _wiki
        lines = ["## Concepts in this book"]
        for rec in sorted(bk.values(), key=lambda r: r["first"]):
            links = ", ".join(link(s) for s in rec["concepts"]) or "(none new)"
            lines.append(f"- pp. {rec['first']}–{rec['last']}{(' ' + rec['title']) if rec['title'] else ''}: {links}")
        return "\n".join(lines)

    def undo(self, b: dict, bid: str, journal: dict) -> None:
        d = self.dir / "undo"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{b['subject']}-{b['id']}-{bid}.json").write_text(
            json.dumps(journal, ensure_ascii=False), encoding="utf-8"
        )
        for old in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-60]:
            old.unlink(missing_ok=True)

    def commit(self, paths: list[str], message: str) -> str | None:
        """One commit for the files a batch wrote, when the notes are a git repository (the rest of the work tree
        is left alone)."""
        root = Path(self.app.workspace)
        git = proc.which("git", [])
        if not self.setting("commit") or not git or not (root / ".git").exists() or not paths:
            return None
        try:
            rel = [str(Path(p).relative_to(root)) for p in paths]
            if proc.run([git, "-C", str(root), "add", "--", *rel], timeout=60).code != 0:
                return None
            r = proc.run([git, "-C", str(root), "commit", "-q", "-m", message, "--", *rel], timeout=60)
            if r.code != 0:
                return None
            return proc.run([git, "-C", str(root), "rev-parse", "--short", "HEAD"], timeout=30).out.strip()
        except (OSError, ValueError):
            return None

    # ------------------------------------------------------------------------------------------------- garden
    def queue_garden(self, slugs: list[str]) -> None:
        with self.lock:
            g = self.load("garden.json", {"queue": [], "last": {}})
            q = [s for s in g.get("queue", []) if s not in slugs] + [s for s in slugs if s]
            g["queue"] = q[-2000:]
            self.save("garden.json", g)

    def orphans(self, index: cg.Index) -> list[str]:
        """Notes no other concept note links to."""
        inbound: set[str] = set()
        for n in index.notes.values():
            inbound |= {t for t in n.links if t != n.slug}
        return sorted(s for s in index.notes if s not in inbound)

    def garden(self, payload: dict | None = None) -> dict:
        """The daily second pass: the notes the reading touched, then notes nothing links to, each against what's there
        now. One short request per note (to the check AI); the answer's links are checked the same way."""
        if not self.app.is_on(self.id) or not self.setting("garden"):
            return {}
        index = self.index()
        if not index.notes:
            return {}
        self.prune_dangling(index)
        g = self.load("garden.json", {"queue": [], "last": {}})
        limit = int(self.setting("garden_per_day") or 40)
        pick: list[str] = []
        queue = [s for s in g.get("queue", []) if s in index.notes]
        for s in queue:
            if len(pick) < limit:
                pick.append(s)
        for s in self.orphans(index):
            if len(pick) < limit and s not in pick and g.get("last", {}).get(s) != day():
                pick.append(s)
        g["queue"] = [s for s in queue if s not in pick]
        _, chk = self.roles()
        sent = 0
        for s in pick:
            n = index.notes[s]
            cands = [c for c in index.candidates(n.head, n.title, n.aliases, limit=9) if c.slug != s][:8]
            if not cands:
                continue
            prompt = ai.LINK_NOTES_PROMPT.format(
                note=json.dumps(index.card(s), ensure_ascii=False), cards=ai.cards_text(index, [c.slug for c in cands])
            )
            self.app.jobs.submit(
                prompt,
                title=f"Linking: {short(n.title, 40)}",
                effort="low",
                background=True,
                text_only=True,
                quiet=True,
                lane="chk",
                brain=chk or None,
                then="integrate.linked",
                then_payload={"note": s},
            )
            g.setdefault("last", {})[s] = day()
            sent += 1
        self.save("garden.json", g)
        return {"asked": sent}

    def prune_dangling(self, index: cg.Index) -> int:
        """Take out the typed link lines Kurooto wrote (`- relation:: [[x]] — …`) whose note doesn't exist: a concept
        that was dropped after a second look, or a note you deleted. Your own links are never touched."""
        root = Path(self.app.workspace)
        every = {p.relative_to(root).with_suffix("").as_posix() for p in root.rglob("*.md") if ".git" not in p.parts}
        names = {Path(x).name for x in every}
        fixed, paths = 0, []
        for n in index.notes.values():
            try:
                old = n.path.read_text(encoding="utf-8")
            except OSError:
                continue
            keep = []
            here = n.slug + ".md"
            for ln in old.split("\n"):
                t = gw.line_target(ln, here)  # a typed link line, [[wikilink]] or markdown
                if t and t not in every and Path(t).name not in names:
                    fixed += 1
                    continue
                keep.append(ln)
            new = "\n".join(keep)
            if new != old and gw.guarded(old, new).ok:
                write_note_file(n.path, new)
                paths.append(str(n.path))
        if paths:
            self.commit(paths, f"graph: {fixed} link{'s' if fixed != 1 else ''} to notes that don't exist taken out")
            self.app.events.emit("integrate_pruned", links=fixed)
        return fixed

    def _linked(self, job, result, payload: dict) -> None:
        self.spend(result)
        self.budget.seen(job, result)
        data = ai.parse_json(result.text) if result.ok else None
        s = payload["note"]
        path = Path(self.app.workspace) / f"{s}.md"
        if not data or not path.is_file():
            return
        index = self.index()
        lines = []
        for lk in data.get("links") or []:
            if not isinstance(lk, dict):
                continue
            t = str(lk.get("target") or "").removesuffix(".md")
            rel, reason = str(lk.get("relation") or "").lower(), str(lk.get("reason") or "")
            try:
                conf = float(lk.get("confidence", 0.5))
            except (TypeError, ValueError):
                conf = 0.5
            if t in index.notes and t != s and rel in gw.RELATIONS and not gw.lint_reason(reason) and conf >= 0.5:
                lines.append((t, gw.link_line(rel, t, reason, layout.of(self.app).note_style, f"{s}.md")))
        if not lines:
            return
        old = path.read_text(encoding="utf-8")
        new, n = gw.add_links(old, lines, f"{s}.md")
        if n and gw.guarded(old, new).ok:
            write_note_file(path, new)
            self.bump_night(links=n, garden=1)
            self.commit([str(path)], f"graph: {n} link{'s' if n != 1 else ''} for {Path(s).name}")

    # ------------------------------------------------------------------------------------------------ metrics
    def metrics(self) -> dict:
        """How good the graph is, in numbers: broken links, notes nothing links to, links with a reason that fits any
        pair, the share of links going to the three busiest notes, and names that collide."""
        root = Path(self.app.workspace)
        index = self.index()
        every = {p.relative_to(root).with_suffix("").as_posix() for p in root.rglob("*.md") if ".git" not in p.parts}
        base = {Path(s).name for s in every}
        broken = generic = total = 0
        indeg: dict[str, int] = {}
        for n in index.notes.values():
            text = n.path.read_text(encoding="utf-8", errors="ignore")
            for t in gw.targets(text, n.slug + ".md"):
                total += 1
                indeg[t] = indeg.get(t, 0) + 1
                if t not in every and t not in base:
                    broken += 1
            generic += sum(
                1 for ln in text.splitlines() if gw.GENERIC_ANY.search(ln) or re.search(r"::.*— related to", ln)
            )
        top3 = sum(sorted(indeg.values(), reverse=True)[:3])
        names: dict[str, int] = {}
        for n in index.notes.values():
            for nm in n.names:
                names[cg.normalise(nm)] = names.get(cg.normalise(nm), 0) + 1
        return {
            "concepts": len(index.notes),
            "links": total,
            "broken": broken,
            "no_links_in": len(self.orphans(index)),
            "boilerplate_reasons": generic,
            "top3_share": round(top3 / total, 3) if total else 0.0,
            "name_collisions": sum(1 for v in names.values() if v > 1),
        }

    # ---------------------------------------------------------------------------------------------- reporting
    def counts(self) -> dict:
        led = self.load("ledger.json", {})
        c = {"done": 0, "failed": 0, "pending": 0}
        for bk in [*led.get("books", {}).values(), *led.get("items", {}).values()]:
            for rec in bk.get("batches", {}).values():
                st = rec.get("state")
                c["done" if st == "done" else "failed" if st == "failed" else "pending"] += 1
        c["todo"] = len(self.ready_batches())
        return c

    def summary(self, payload: dict | None = None) -> str:
        n = (self.load("ledger.json", {}).get("nights", {}) or {}).get(day(), {})
        if not n:
            return ""
        line = (
            f"Concept graph: {n.get('batches', 0)} batches, +{n.get('new', 0)} concept notes, "
            f"+{n.get('links', 0)} links, {n.get('updated', 0)} notes updated"
        )
        if n.get("requests"):
            line += f"; {n['requests']} AI requests (about ${n.get('cost', 0):.2f} at API prices)"
        if n.get("flagged"):
            line += f"; {n['flagged']} doubtful, {n.get('dropped', 0)} dropped after a second look"
        if n.get("failed"):
            line += f"; {n['failed']} batches failed"
        if not self.app.is_on("dreaming"):  # Dreaming's morning message has it then (modules/dreaming.py)
            self.app.notify(line + ".", kind="result", title="Concept graph", why="integrate.summary")
        return line

    def waiting(self) -> dict[str, int]:
        """How many items of each source have a batch waiting to be read."""
        keys: dict[str, str] = {}
        for b, _ in self.ready_batches():
            keys.setdefault(self.key(b), self.source_of(b))
        per = {src: 0 for src in SOURCES}
        for src in keys.values():
            per[src] += 1
        return {k: v for k, v in per.items() if v}

    def waiting_line(self) -> str:
        """ "Waiting to be read: 2 books, 5 class files, 1 handwritten." (empty when nothing waits)"""
        per = self.waiting()
        if not per:
            return ""
        return "Waiting to be read: " + ", ".join(f"{n} {NAMED[k][n != 1]}" for k, n in per.items()) + "."

    def backfill_hw_said(self, n: int) -> str:
        if not self.reads("handwritten"):
            return 'Handwritten notes aren\'t read into the graph: add "handwritten" to integrate.sources first.'
        if not n:
            return (
                "No handwritten notes waiting: those linked before are read already or too short; /handwritten link "
                "links older ones, and each is queued once linked."
            )
        return f"Queued {n} handwritten note{'s' if n != 1 else ''}, the oldest first, within each night's budget."

    def backfill_said(self, n: int, courses: int) -> str:
        if not self.reads("classroom"):
            return 'Class materials aren\'t read into the graph: add "classroom" to integrate.sources first.'
        if not n:
            return "No Classroom files waiting: those filed before are read already, or none had enough text."
        return (
            f"Queued {n} Classroom file{'s' if n != 1 else ''} from {courses} course{'s' if courses != 1 else ''}, "
            "the oldest course first. They're read within each night's budget, after what's filed from now on."
        )

    def card(self) -> dict:
        """The dashboard's card: tonight's reading budget, how it was decided, the last limit (and, for a free Gemini
        key with little room, that agy or the model on this computer reads books better); what's waiting, by source; a
        switch per source, and one to read the Classroom files filed before."""
        lines = self.budget.lines()
        wait = self.waiting_line()
        on = self.sources()
        toggles = [
            {"id": f"source:{k}", "label": label, "on": k in on}
            for k, label in (
                ("books", "Read books"),
                ("classroom", "Read class materials Classroom files into your notes"),
                ("handwritten", "Read your handwritten notes"),
                ("repos", "Read your projects' repositories (README, docs): /project add"),
            )
        ]
        toggles.append(
            {
                "id": "notation",
                "label": "Notation tables (when two sources write a concept differently)",
                "on": self.notation_on(),
            }
        )
        if self.app.is_on("classroom_notes") and "classroom" in on:
            done = bool((self.load("items.json", {}) or {}).get("backfill", {}).get("classroom"))
            toggles.append(
                {
                    "id": "backfill:classroom",
                    "label": "Also read the Classroom files filed before" + (" (queued)" if done else ""),
                    "on": done,
                    "disabled": done,
                }
            )
        return {"lines": [*lines, wait] if wait else lines, "toggles": toggles}

    def card_action(self, act: str, value) -> str:
        """A switch on the card: a source (integrate.sources), or the Classroom backfill."""
        if act.startswith("source:") and act[7:] in SOURCES:
            k, cur = act[7:], self.sources()
            new = [x for x in SOURCES if (x in cur and x != k) or (x == k and value)]
            self.app.settings.set("integrate.sources", new)
            return f"Read into the graph: {', '.join(new) or 'nothing'}."
        if act == "notation":
            self.app.settings.set("integrate.notation", bool(value))
            return "Notation tables: " + ("on." if value else "off.")
        if act == "backfill:classroom":
            return self.backfill_said(*self.backfill_classroom()) if value else "Already queued."
        return "There's no such switch."

    def health(self):
        if not self.app.modules["books"] or not self.app.is_on("books"):
            return False, "turn on Books and PDFs"
        c = self.counts()
        return True, f"{c['done']} batches done, {c['todo']} waiting"

    # ----------------------------------------------------------------------------------------------- command
    def callbacks(self):
        return {"dup": lambda ref, act: graphmerge.button(self, ref, act)}

    def commands(self):
        return [
            Command(
                "graph",
                "the concept graph: /graph, /graph now, /graph stop, /graph same (look-alike concept notes), "
                "/graph backfill classroom | handwritten | all",
                self._cmd,
                usage="/graph [now | stop | same | backfill classroom | handwritten | all]",
            )
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        a = (arg or "").strip().lower()
        if a == "now":
            (self.dir / "stopped.json").unlink(missing_ok=True)
            r = self.tick()
            if r.get("limit") in ("per_night", "cost", "hit"):
                return "Nothing to start: " + " ".join(self.budget.lines())
            return "Started." if r.get("submitted") else f"Nothing to start ({r or 'already running'})."
        if a in ("same", "duplicates", "dupes"):
            text, buttons = graphmerge.ask_now(self)
            if buttons and msg.respond:
                msg.reply(text, buttons=buttons)
                return None
            return text
        if a.startswith("backfill"):
            what = a.split()[1:]
            if what == ["classroom"]:
                return self.backfill_said(*self.backfill_classroom())
            if what == ["handwritten"]:
                return self.backfill_hw_said(self.backfill_handwritten())
            if what == ["all"]:  # every source that's on: books are queued as they're found already
                said = []
                if self.reads("classroom"):
                    said.append(self.backfill_said(*self.backfill_classroom()))
                if self.reads("handwritten"):
                    said.append(self.backfill_hw_said(self.backfill_handwritten()))
                return " ".join(said) or "Only books are read (integrate.sources); they're queued as they're found."
            return (
                "Usage: /graph backfill classroom | handwritten | all (reads what was filed or written before, "
                "night by night)."
            )
        if a == "stop":
            nxt = self.hold()
            return (
                f"Stopped: no new batches until its usual start, {nxt:%a %H:%M} (a batch already asked for still "
                "finishes). /graph now goes on sooner."
            )
        c, m = self.counts(), self.metrics()
        bulk, chk = self.roles()
        today = (self.load("ledger.json", {}).get("nights", {}) or {}).get(day(), {})
        spent = (
            f" Today: {today.get('requests', 0)} AI requests, about ${today.get('cost', 0):.2f} at API prices "
            "(a plan isn't billed per request; the plan's own limit is what runs out)."
            if today.get("requests")
            else ""
        )
        budget = "".join(f"\n{ln}" for ln in self.budget.lines())
        wait = self.waiting_line()
        return (
            f"Concept graph: {c['done']} batches done, {c['todo']} waiting, {c['failed']} failed. "
            + (f"{wait} " if wait else "")
            + f"Reads: {', '.join(self.sources()) or 'nothing'} (integrate.sources). "
            f"AI: {bulk or 'none'} (bulk), {chk or 'none'} (second look).{spent}{budget}\n"
            f"{m['concepts']} concepts, {m['links']} links; {m['broken']} broken, {m['no_links_in']} with no links in, "
            f"{m['boilerplate_reasons']} with a vague reason, the top three notes get {m['top3_share']:.0%} of links."
        )
