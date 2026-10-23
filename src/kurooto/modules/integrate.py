"""Concept graph: what you read in a book is woven into the notes you already have.

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

Which AI: integrate.roles {"bulk": "agy", "check": "claude"} (empty: chosen from what's installed; one program does
both). The two run side by side. With no agent program, your main AI (a Gemini key, say) does both, at its limit.

State: <state>/integrate/ (ledger.json, seen.json, chapters.json, garden.json, pending/, undo/, vectors.db).
Command: /graph (status), /graph now (start), /graph stop.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
from dataclasses import asdict
from pathlib import Path

from kurooto import providers
from kurooto.core import conceptgraph as cg
from kurooto.core import graphwrite as gw
from kurooto.core import integrate_ai as ai
from kurooto.core import layout, proc, segment
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.core.tools import write_note_file
from kurooto.modules.base import Command, Incoming, Module
from kurooto.providers.base import Verdict

register_defaults(
    "integrate",
    {
        "at": "daily 01:30",  # when the night's integration starts (it carries on batch after batch)
        "roles": {"bulk": "", "check": ""},  # the AI for the bulk work and for the second look ("": chosen for you)
        "batch_pages": 12,  # about this many pages per request
        "per_night": 300,  # the most batches in a night (a limit on how much of your AI's day it may use)
        "garden": True,  # each day, a second pass over the notes the reading touched and notes nothing links to
        "garden_per_day": 40,  # the most notes in that pass
        "embeddings": "auto",  # where meaning-based matching comes from: auto | ollama | gemini | off
        "rerank": "auto",  # a local model judges which notes belong together (a graphics card helps): auto | off
        "rerank_model": "",  # which one ("": the helper model of this computer's setup)
        "first": [],  # subjects to do first, e.g. ["deep-learning"]
        "order": "smallest",  # which books first: smallest (fewest pages: most books done soonest) | name
        "commit": True,  # one git commit per batch, when your notes are a repository
        "summary": True,  # one line each morning about what changed
    },
)
STALE_S = 3 * 3600  # a request that didn't come back in this long is asked again
TRIES = 3
PAGE_MARK = re.compile(r'<a id="p-(\d+)"></a>\n## \[p\. \d+\]\n')


def day() -> str:
    return f"{now():%Y-%m-%d}"


def short(text: str, n: int) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


class Integrate(Module):
    id = "integrate"
    title = "Concept graph"
    description = (
        "When a book has been read, weaves its concepts into your notes: new concept notes, links with their reasons, "
        "and the places each concept is met, checked before anything is written. Never changes your own text."
    )
    privacy = (
        "A few pages of a book's text at a time, and the titles and opening lines of related notes, go to the AI you "
        "picked (like any request). The checks and the matching run on this computer."
    )
    requires = ("books",)
    heavy = True  # night work: on battery it waits for the charger

    def __init__(self, app):
        super().__init__(app)
        self.lock = threading.RLock()
        self._index: cg.Index | None = None
        self._store: cg.VectorStore | None = None

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
        if self.setting("garden"):
            self.every("garden", "daily 06:20", self.garden)
        if self.setting("summary"):
            self.every("summary", "daily 07:10", self.summary)
        jobs = self.app.jobs
        jobs.then_actions["integrate.done"] = self._done
        jobs.then_actions["integrate.checked"] = self._checked
        jobs.then_actions["integrate.linked"] = self._linked

    # --------------------------------------------------------------------------------------------------- roles
    def roles(self) -> tuple[str, str]:
        """(bulk AI, check AI): your choice, else agy and Claude Code when both are installed (they run side by side),
        else the one there is for both, else your main AI."""
        want = self.setting("roles") or {}
        avail = []
        for k in providers.AGENT_PROGRAMS:
            b = providers.build(self.app, k)
            if b is not None and b.available()[0]:
                avail.append(k)
        main = self.app.settings.get("brain.main") or ""
        bulk = want.get("bulk") or (avail[0] if avail else main)
        check = want.get("check") or next((k for k in avail if k != bulk), bulk)
        return bulk, check

    # -------------------------------------------------------------------------------------------------- books
    def pages_of(self, b: dict) -> dict[int, str]:
        f = self.books.book_dir(b) / "text.md"
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            return {}
        parts = PAGE_MARK.split(text)
        return {int(parts[i]): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}

    def key(self, b: dict) -> str:
        return f"{b['subject']}/{b['id']}"

    def stub(self, b: dict) -> Path:
        return layout.of(self.app).path("subject", subject=b["subject"]) / "books" / f"{b['id']}.md"

    def plan(self, b: dict) -> list[segment.Batch]:
        """The batches of a book: its sections from the page text, sized by integrate.batch_pages."""
        pages = self.pages_of(b)
        total = max(pages) if pages else 0
        secs = segment.sections(pages, [], total)
        return segment.batches(secs, total, int(self.setting("batch_pages") or segment.TARGET))

    def ready_batches(self) -> list[tuple[dict, segment.Batch]]:
        """Every batch not done yet whose pages have all been read, in the order to do them."""
        self.inflight()  # forget requests that never came back, so they're asked again
        led = self.load("ledger.json", {})
        first = [str(x) for x in self.setting("first") or []]
        metas = {self.key(b): self.books.meta(b) for b in self.books.library()}
        smallest = str(self.setting("order") or "smallest") == "smallest"

        def rank(b: dict):
            pages = int(metas[self.key(b)].get("pages") or 0) if smallest else 0
            return (b["subject"] not in first, pages, b["subject"], b["id"])

        out = []
        for b in sorted(self.books.library(), key=rank):
            meta = metas[self.key(b)]
            done = int(meta.get("done") or 0)
            if not meta.get("pages") or not done:
                continue
            done_batches = (led.get("books", {}).get(self.key(b), {}) or {}).get("batches", {})
            for bt in self.plan(b):
                rec = done_batches.get(bt.id, {})
                if rec.get("state") in ("done", "failed", "queued", "checking"):
                    continue
                if bt.last <= done:
                    out.append((b, bt))
        return out

    # ---------------------------------------------------------------------------------------------- the ledger
    def record(self, b: dict, bt_id: str, **kw) -> dict:
        with self.lock:
            led = self.load("ledger.json", {})
            rec = (
                led.setdefault("books", {}).setdefault(self.key(b), {}).setdefault("batches", {}).setdefault(bt_id, {})
            )
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
        """(bulk requests out, second looks out); a request out for too long is forgotten (it will be asked again)."""
        led = self.load("ledger.json", {})
        bulk = chk = 0
        changed = False
        for bk in led.get("books", {}).values():
            for rec in bk.get("batches", {}).values():
                if rec.get("state") in ("queued", "checking"):
                    age = time.time() - (dt.datetime.fromisoformat(rec["at"]).timestamp() if rec.get("at") else 0)
                    if age > STALE_S:
                        rec["state"] = "pending"
                        changed = True
                    elif rec["state"] == "queued":
                        bulk += 1
                    else:
                        chk += 1
        if changed:
            self.save("ledger.json", led)
        return bulk, chk

    # ---------------------------------------------------------------------------------------------------- tick
    def index(self, refresh: bool = True) -> cg.Index:
        """The notes' index (rebuilt from the files: they change as batches are written)."""
        if self._store is None:
            self._store = cg.VectorStore(self.dir / "vectors.db")
        emb = cg.make_embedder(self.app) if str(self.setting("embeddings") or "auto") != "off" else None
        from kurooto.core.rerank import make_reranker

        return cg.Index(cg.scan(self.app), emb, self._store if emb else None, make_reranker(self.app))

    def tick(self, payload: dict | None = None) -> dict:
        """Ask for the next batch (one bulk request at a time per AI; second looks run beside it)."""
        if not self.app.is_on(self.id):
            return {}
        bulk_out, _ = self.inflight()
        out = {"submitted": 0}
        if bulk_out:
            return out
        led = self.load("ledger.json", {})
        today = (led.get("nights", {}) or {}).get(day(), {}).get("batches", 0)
        if today >= int(self.setting("per_night") or 300):
            return {**out, "limit": "per_night"}
        todo = self.ready_batches()
        if not todo:
            return {**out, "idle": True}
        b, bt = todo[0]
        self.submit_batch(b, bt)
        out["submitted"] = 1
        return out

    def poke(self) -> None:
        """A book was read: carry on tonight (the schedule would only start it at integrate.at)."""
        if self.app.is_on(self.id):
            threading.Thread(target=self.tick, name="integrate", daemon=True).start()

    def submit_batch(self, b: dict, bt: segment.Batch) -> str:
        pages = self.pages_of(b)
        meta = self.books.meta(b)
        index = self.index()
        text = ai.page_text(pages, bt.first, bt.last)
        near = index.candidates(f"{bt.title}. {text[:3000]}", "", None, limit=30, rerank=False)
        prompt = ai.batch_prompt(
            meta.get("title") or b["id"],
            b["subject"],
            bt.first,
            bt.last,
            bt.title,
            ai.cards_text(index, [c.slug for c in near]),
            text,
        )
        bulk, _ = self.roles()
        jid = self.app.jobs.submit(
            prompt,
            title=f"Concepts: {short(meta.get('title') or b['id'], 40)} pp. {bt.first}-{bt.last}",
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
        recs = list(
            ((self.load("ledger.json", {}).get("books", {}) or {}).get(self.key(b), {}) or {})
            .get("batches", {})
            .values()
        )
        recent = [r for r in recs if r.get("state") == "done"][-3:]
        concepts = sum(int(r.get("concepts") or 0) for r in recent)
        flagged = sum(int(r.get("flagged") or 0) for r in recent)
        return "medium" if concepts >= 4 and flagged / concepts > 0.3 else "low"

    def tries(self, b: dict, bid: str) -> int:
        led = self.load("ledger.json", {})
        return int((led.get("books", {}).get(self.key(b), {}).get("batches", {}).get(bid, {}) or {}).get("tries", 0))

    def find_book(self, key: str) -> dict | None:
        return next((b for b in self.books.library() if self.key(b) == key), None)

    # --------------------------------------------------------------------------------------------- the answer
    def _done(self, job, result, payload: dict) -> None:
        b = self.find_book(payload["book"])
        if b is None:
            return
        bid = payload["batch"]
        self.spend(result)
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
            base = cg.slug_of(c.name)
            slug_path = lay.path("concept", subject=b["subject"], slug=base)
            rel = self.rel(slug_path)
            n = 2
            while rel in taken or slug_path.exists():
                slug_path = lay.path("concept", subject=b["subject"], slug=f"{base}-{n}")
                rel = self.rel(slug_path)
                n += 1
            taken.add(rel)
            c.slug = rel

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
        answer = ai.parse_json(result.text) if result.ok else None
        kept, dropped = ai.apply_second_look(items, answer)
        pend.unlink(missing_ok=True)
        self.write(b, payload, concepts, self.index(), flagged=len(items), dropped=dropped)
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
        meta = self.books.meta(b)
        stub = self.stub(b)
        stub_slug = self.rel(stub)
        title = meta.get("title") or b["id"]
        journal: dict[str, str | None] = {}
        counts = {"new": 0, "same": 0, "links": 0, "skipped": 0}
        seen = self.load("seen.json", {})
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

        for c in core:
            path = root / f"{c.slug}.md"
            entry = {"book": self.key(b), "note": stub_slug, "title": title, "batch": bid, "pages": [first, last]}
            entry["update"] = c.update if c.same_as else ""
            entry["def"] = short(c.definition, 160) if not c.same_as else ""
            rows = seen.setdefault(c.slug, [])
            prev = next((r for r in rows if r["book"] == entry["book"] and r["batch"] == bid), None)
            if prev:  # the same batch again (the concept is now a note): keep what the first time said
                entry["def"] = entry["def"] or prev.get("def", "")
                entry["update"] = entry["update"] or prev.get("update", "")
            rows[:] = [r for r in rows if r is not prev] + [entry]
            lines = [
                (lk.target, gw.link_line(lk.relation, lk.target, lk.reason))
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
                    f"Source: {title}, pp. {first}–{last}",
                )
                body = gw.put_block(body, "seen", self.seen_body(seen[c.slug]))
                if put(path, None, body):
                    counts["new"] += 1
                    counts["links"] += len(lines)
            else:
                new, added = gw.add_links(old, lines)
                new = gw.put_block(new, "seen", self.seen_body(seen[c.slug]))
                new = self.add_alias(new, c.name, c.aliases)
                if new != old and put(path, old, new):
                    counts["same"] += 1
                    counts["links"] += added
        self.save("seen.json", seen)
        # the chapter note lists what it introduces
        chap = self.load("chapters.json", {})
        bk = chap.setdefault(self.key(b), {})
        bk[bid] = {"first": first, "last": last, "title": payload.get("title", ""), "concepts": [c.slug for c in core]}
        self.save("chapters.json", chap)
        if stub.is_file():
            old = stub.read_text(encoding="utf-8")
            new = gw.put_block(old, "concepts", self.chapter_body(bk, names_by_slug, index))
            if new != old:
                put(stub, old, new)
        # the course map lists the concepts the books introduced, in a block of its own
        course = lay.path("course", subject=b["subject"])
        if course.is_file():
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
                body = "## From the books\n" + "\n".join(
                    f"- [[{x}|{n}]]" for x, n in sorted(names.items(), key=lambda kv: kv[1].lower())
                )
                old = course.read_text(encoding="utf-8")
                new = gw.put_block(old, "books", body)
                if new != old:
                    put(course, old, new)
        self.undo(b, bid, journal)
        sha = self.commit(
            list(journal),
            f"books: {short(title, 40)} pp. {first}-{last} "
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
        self.queue_garden([c.slug for c in core])
        self.app.events.emit("integrate_batch", book=self.key(b), batch=bid, **counts)
        return counts

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
    def seen_body(rows: list[dict]) -> str:
        rows = sorted(rows, key=lambda r: (r["book"], r["pages"][0]))
        lines = ["## Seen in"]
        for r in rows:
            a, z = r["pages"]
            lines.append(f"- [[{r['note']}|{r['title']}]] pp. {a}–{z}")
        ups = [r for r in rows if r.get("update")]
        if ups:
            lines += ["", "### Added from the books"]
            lines += [f"- {r['title']} pp. {r['pages'][0]}–{r['pages'][1]}: {r['update']}" for r in ups]
        return "\n".join(lines)

    @staticmethod
    def chapter_body(bk: dict, names: dict, index: cg.Index) -> str:
        lines = ["## Concepts in this book"]
        for rec in sorted(bk.values(), key=lambda r: r["first"]):
            links = ", ".join(f"[[{s}]]" for s in rec["concepts"]) or "(none new)"
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
            for ln in old.split("\n"):
                m = gw.LINK_LINE.match(ln) and gw.WIKILINK.search(ln)
                t = m[1].strip().removesuffix(".md") if m else ""
                if m and t not in every and Path(t).name not in names:
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
                lines.append((t, gw.link_line(rel, t, reason)))
        if not lines:
            return
        old = path.read_text(encoding="utf-8")
        new, n = gw.add_links(old, lines)
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
            for t in gw.targets(text):
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
        for bk in led.get("books", {}).values():
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
        self.app.notify(line + ".", kind="result", title="Concept graph", why="integrate.summary")
        return line

    def health(self):
        if not self.app.modules["books"] or not self.app.is_on("books"):
            return False, "turn on Books and PDFs"
        c = self.counts()
        return True, f"{c['done']} batches done, {c['todo']} waiting"

    # ----------------------------------------------------------------------------------------------- command
    def commands(self):
        return [Command("graph", "the concept graph: /graph, /graph now, /graph stop", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        a = (arg or "").strip().lower()
        if a == "now":
            r = self.tick()
            return "Started." if r.get("submitted") else f"Nothing to start ({r or 'already running'})."
        if a == "stop":
            self.app.scheduler.cancel(f"{self.id}:night")
            return "Stopped for tonight; it starts again at its usual time."
        c, m = self.counts(), self.metrics()
        bulk, chk = self.roles()
        today = (self.load("ledger.json", {}).get("nights", {}) or {}).get(day(), {})
        spent = (
            f" Today: {today.get('requests', 0)} AI requests, about ${today.get('cost', 0):.2f} at API prices "
            "(a plan isn't billed per request; the plan's own limit is what runs out)."
            if today.get("requests")
            else ""
        )
        return (
            f"Concept graph: {c['done']} batches done, {c['todo']} waiting, {c['failed']} failed. "
            f"AI: {bulk or 'none'} (bulk), {chk or 'none'} (second look).{spent}\n"
            f"{m['concepts']} concepts, {m['links']} links; {m['broken']} broken, {m['no_links_in']} with no links in, "
            f"{m['boilerplate_reasons']} with a vague reason, the top three notes get {m['top3_share']:.0%} of links."
        )
