"""The concepts already in your notes, and finding the ones a new piece of reading may touch. No AI is used here.

    scan(app)                  every concept note: slug, title, aliases, a short summary, its links, a hash of its text
    Index(notes, embedder)     candidates(text, names): the notes worth showing an AI, best first
    normalise(name)            the form names are compared in ("Back-propagation" == "backpropagation")

Candidates come from four places, then are merged and ranked:
    alias / title match        the name (or an alias) is the same as a note's, or very close: the "this already exists"
                               signal, and the one that keeps duplicates from being made
    keyword ranking            BM25 over each note's title, aliases and opening text (pure Python, any computer)
    embeddings                 when this computer has a model for them (Ollama's nomic-embed-text, or a Gemini key):
                               meaning, not words; vectors are kept by text hash so a note is embedded once
    neighbours                 the notes the best matches already link to

Every new concept is compared with every concept this way, in milliseconds, so nothing depends on an AI reading the
whole vault: the AI is shown the few notes that matter.

    near_duplicates(index)     pairs of notes that look like one concept (0.6.0): the same name, a name they share
                               (an alias), or embeddings at least 0.92 alike; modules/integrate.py asks about them

A note merged into another (a `<!-- kurooto:merged-into -->` block naming it) is a redirect: it isn't offered as a
candidate, and its names find the note it was merged into.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import re
import sqlite3
import struct
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import egress
from kurooto.core.layout import link_targets

if TYPE_CHECKING:
    from kurooto.app import App

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
TYPED = re.compile(r"^\s*[-*] ([a-z-]+):: (\[\[.+|\[.+)$", re.M)  # a typed link line: relation, its link and reason
MERGED = re.compile(  # a redirect's target: the first link inside its merged-into block
    r"<!-- kurooto:merged-into\b[^>]*-->(?:(?!<!-- /kurooto:merged-into).)*?\[\[([^\]|#]+)", re.S
)
NOT_CONCEPT = re.compile(r"^(?:\d{4}-\d{2}-\d{2}|course$|class-log$|exam-prep$|doubts$|index$|readme$)", re.I)
DUP_COSINE = 0.92  # embeddings this alike: two notes about one concept
FRONT = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
STOP = set(
    "a an the of and or to in on for with by from as at is are be this that these those it its we you can which "
    "than then into over under between using use used given let such also not no if when where how what".split()
)
SUMMARY_CHARS = 280
BODY_CHARS = 1500  # how much of a note is searched


def normalise(name: str) -> str:
    """A name in the form names are compared: lowercase, no accents, only letters and digits."""
    t = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", t)


def words(text: str) -> list[str]:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return [w for w in re.findall(r"[a-z][a-z0-9]{2,}", t) if w not in STOP]


def slug_of(name: str) -> str:
    t = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:70] or "concept"


@dataclass
class Note:
    slug: str  # the link target without .md, e.g. "zettel/backpropagation"
    path: Path
    title: str
    aliases: list[str] = field(default_factory=list)
    summary: str = ""
    head: str = ""  # what is searched
    links: set[str] = field(default_factory=set)  # slugs it links to
    hash: str = ""
    typed: dict[str, str] = field(default_factory=dict)  # target -> relation, from its typed link lines
    redirect: str = ""  # merged into this note (a redirect), else ""

    @property
    def names(self) -> list[str]:
        return [self.title, *self.aliases, Path(self.slug).name.replace("-", " ")]


def parse_front(text: str) -> tuple[dict, str]:
    """(simple frontmatter fields, the body): aliases as a list, other values as strings."""
    m = FRONT.match(text)
    if not m:
        return {}, text
    out: dict = {}
    for ln in m[1].splitlines():
        if ":" in ln and not ln.startswith((" ", "-")):
            k, _, v = ln.partition(":")
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                out[k.strip()] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
            else:
                out[k.strip()] = v.strip("\"'")
    return out, text[m.end() :]


def read_note(root: Path, path: Path) -> Note | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    front, body = parse_front(text)
    slug = path.relative_to(root).with_suffix("").as_posix()
    h1 = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    title = (h1[1] if h1 else path.stem.replace("-", " ")).strip()
    aliases = front.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    prose = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    prose = re.sub(r"^#.*$|^\s*[-*]\s+\w[\w-]*::.*$", "", prose, flags=re.M).strip()
    prose = re.sub(r"\s+", " ", prose)
    links = set(link_targets(body, slug + ".md"))  # [[wikilinks]] and markdown links alike (notes.links)
    typed: dict[str, str] = {}
    for m in TYPED.finditer(body):  # a typed link line in either link style
        found = link_targets(m[2], slug + ".md")
        if found:
            typed[found[0]] = m[1]
    red = MERGED.search(body)
    return Note(
        slug,
        path,
        title,
        [a for a in aliases if a],
        prose[:SUMMARY_CHARS],
        prose[:BODY_CHARS],
        links,
        hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        typed,
        red[1].strip().removesuffix(".md") if red else "",
    )


def concept_dirs(app: App) -> list[Path]:
    """Where concept notes live: the concept folder of the layout (zettel/), or each subject's folder."""
    from kurooto.core import layout

    lay = layout.of(app)
    dirs: list[Path] = []
    probe = lay.path("concept", subject="x", slug="y")
    root = Path(app.workspace)
    if probe.parent.name == "x":  # the plain layout keeps concepts in each subject's folder
        subj = app.modules.get("subjects")
        subjects = [s["slug"] for s in subj.subjects()] if subj is not None and app.is_on("subjects") else []
        dirs = [lay.path("concept", subject=s, slug="y").parent for s in subjects]
    else:
        dirs = [probe.parent]
    return [d for d in dict.fromkeys(dirs) if d.is_dir() and root in [d, *d.parents]]


def scan(app: App) -> dict[str, Note]:
    root = Path(app.workspace)
    out: dict[str, Note] = {}
    for d in concept_dirs(app):
        for f in sorted(d.rglob("*.md")):
            if any(part.startswith(".") for part in f.relative_to(root).parts):
                continue
            n = read_note(root, f)
            if n:
                out[n.slug] = n
    return out


# ------------------------------------------------------------------------------------------------- embeddings
Embedder = Callable[[list[str]], list[list[float]] | None]


class VectorStore:
    """Embeddings kept by the hash of the text they came from (state/integrate/vectors.db): a note is embedded once."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute("create table if not exists v (h text primary key, dim integer, vec blob)")

    def get(self, h: str) -> list[float] | None:
        r = self.db.execute("select dim, vec from v where h=?", (h,)).fetchone()
        return list(struct.unpack(f"{r[0]}f", r[1])) if r else None

    def put(self, h: str, vec: list[float]) -> None:
        self.db.execute("insert or replace into v values(?,?,?)", (h, len(vec), struct.pack(f"{len(vec)}f", *vec)))
        self.db.commit()

    def close(self) -> None:
        self.db.close()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


# ----------------------------------------------------------------------------------------------------- candidates
@dataclass
class Candidate:
    slug: str
    score: float
    evidence: list[str] = field(default_factory=list)  # alias, title, keyword, embedding, neighbour
    cosine: float | None = None
    rerank: float | None = None  # P(yes) from the reranker (core/rerank.py), when there is one

    @property
    def exists(self) -> bool:
        return "alias" in self.evidence or "title" in self.evidence


class Index:
    """Keyword ranking and (when there's an embedder) vectors over the concept notes."""

    def __init__(
        self, notes: dict[str, Note], embedder: Embedder | None = None, store: VectorStore | None = None, reranker=None
    ):
        # a note merged into another is left out; its names find the note it was merged into
        self.redirects = {s: n.redirect for s, n in notes.items() if n.redirect and n.redirect != s}
        merged = {s: notes[s] for s in self.redirects}
        notes = {s: n for s, n in notes.items() if s not in self.redirects}
        self.notes = notes
        self.embedder, self.store = embedder, store
        self.reranker = reranker  # core/rerank.py: a local model that judges pairs, where this computer can run one
        self.tf: dict[str, Counter] = {}
        self.df: Counter = Counter()
        self.len: dict[str, int] = {}
        self.by_name: dict[str, str] = {}
        for s, n in notes.items():
            toks = words(" ".join([n.title] * 3 + n.aliases * 3 + [n.head]))
            c = Counter(toks)
            self.tf[s], self.len[s] = c, len(toks)
            self.df.update(c.keys())
            for name in n.names:
                self.by_name.setdefault(normalise(name), s)
        for s, n in merged.items():
            target = self.redirects[s]
            for _ in range(8):  # merged into a note that was merged on
                if target not in self.redirects:
                    break
                target = self.redirects[target]
            if target in notes:
                for name in n.names:
                    self.by_name.setdefault(normalise(name), target)
        self.avg = (sum(self.len.values()) / len(self.len)) if self.len else 1.0
        self.vec: dict[str, list[float]] = {}
        self.embed_notes()

    def doc_text(self, n: Note) -> str:
        return f"{n.title}. {', '.join(n.aliases)}. {n.head}"[:1200]

    def embed_notes(self) -> None:
        if self.embedder is None or self.store is None:
            return
        need: list[tuple[str, str]] = []
        for s, n in self.notes.items():
            h = text_hash(getattr(self.embedder, "tag", "") + self.doc_text(n))
            v = self.store.get(h)
            if v is not None:
                self.vec[s] = v
            else:
                need.append((s, h))
        for i in range(0, len(need), 16):
            chunk = need[i : i + 16]
            vecs = self.embedder([self.doc_text(self.notes[s]) for s, _ in chunk])
            if not vecs or len(vecs) != len(chunk):
                self.embedder = None  # unreachable now: keywords only for this run
                return
            for (s, h), v in zip(chunk, vecs, strict=False):
                self.store.put(h, v)
                self.vec[s] = v

    def bm25(self, text: str, limit: int = 20) -> list[tuple[str, float]]:
        q = Counter(words(text))
        n_docs = max(1, len(self.notes))
        scores: dict[str, float] = {}
        for s, tf in self.tf.items():
            sc = 0.0
            for w, qn in q.items():
                f = tf.get(w, 0)
                if not f:
                    continue
                idf = math.log(1 + (n_docs - self.df[w] + 0.5) / (self.df[w] + 0.5))
                sc += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * self.len[s] / self.avg)) * (1 + math.log(qn))
            if sc:
                scores[s] = sc
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
        best = top[0][1] if top else 1.0
        return [(s, sc / best) for s, sc in top]

    def match_name(self, name: str, aliases: list[str] | None = None) -> tuple[str | None, str]:
        """(slug, "alias" | "title") when this concept is one that's already here, else (None, "")."""
        for nm in [name, *(aliases or [])]:
            s = self.by_name.get(normalise(nm))
            if s:
                return s, "alias" if normalise(nm) != normalise(self.notes[s].title) else "title"
        key = normalise(name)
        if len(key) >= 6:
            close = difflib.get_close_matches(key, list(self.by_name), n=1, cutoff=0.9)
            if close:
                return self.by_name[close[0]], "title"
        return None, ""

    def candidates(
        self,
        text: str,
        name: str = "",
        aliases: list[str] | None = None,
        limit: int = 8,
        query_vec=None,
        rerank: bool = True,
    ) -> list[Candidate]:
        found: dict[str, Candidate] = {}

        def add(s: str, score: float, why: str, cos: float | None = None) -> None:
            c = found.setdefault(s, Candidate(s, 0.0))
            c.score = max(c.score, score)
            if why not in c.evidence:
                c.evidence.append(why)
            if cos is not None:
                c.cosine = cos

        if name:
            s, why = self.match_name(name, aliases)
            if s:
                add(s, 3.0, why)
        for s, sc in self.bm25(f"{name} {' '.join(aliases or [])} {text}", limit * 3):
            add(s, sc, "keyword")
        if self.vec and self.embedder is not None:
            qv = query_vec
            if qv is None:
                got = self.embedder([f"{name}. {text}"[:1200]])
                qv = got[0] if got else None
            if qv:
                ranked = sorted(((cosine(qv, v), s) for s, v in self.vec.items()), reverse=True)[: limit * 2]
                for cs, s in ranked:
                    if cs >= 0.5:
                        add(s, cs, "embedding", cs)
        top = sorted(found.values(), key=lambda c: -c.score)[:3]
        for c in top:  # the neighbours of the best matches
            for t in self.notes[c.slug].links:
                if t in self.notes and t not in found:
                    add(t, 0.15, "neighbour")
        ranked = sorted(found.values(), key=lambda c: (-c.score, c.slug))
        if rerank and self.reranker is not None and not self.reranker.dead and (name or text):
            head = ranked[: max(limit * 2, limit)]
            judged = self.rerank(head, f"{name}: {text}"[:900])
            if judged is not head:  # the model answered: what it dropped stays dropped (no leftovers fill the gaps)
                return judged[:limit]
        return ranked[:limit]

    def rerank(self, cands: list[Candidate], query: str) -> list[Candidate]:
        """Reorder candidates with the reranker: a name match always stays (that's what "already exists" means); the
        rest are ordered by a blend of the earlier score and the model's odds, and ones it is sure about (< 0.08) are
        dropped. If the model can't be reached the order is left as it was."""
        rest = [c for c in cands if not c.exists]
        if not rest:
            return cands
        docs = [f"{self.notes[c.slug].title}. {self.notes[c.slug].summary}" for c in rest]
        got = self.reranker.scores(query, docs)
        if all(g is None for g in got):
            return cands
        top = max((c.score for c in rest), default=1.0) or 1.0
        for c, g in zip(rest, got, strict=False):
            if g is not None:
                c.rerank = g
                if "rerank" not in c.evidence:
                    c.evidence.append("rerank")
                c.score = 0.4 * (c.score / top) + 0.6 * g
        keep = [c for c in rest if c.rerank is None or c.rerank >= 0.08]
        return sorted([c for c in cands if c.exists] + keep, key=lambda c: (not c.exists, -c.score, c.slug))

    def card(self, slug: str) -> dict:
        n = self.notes[slug]
        return {
            "slug": slug,
            "title": n.title,
            "aliases": n.aliases[:6],
            "summary": n.summary,
            "links": sorted(n.links)[:8],
        }


# ------------------------------------------------------------------------------------------------ near-duplicates
@dataclass
class Pair:
    """Two notes that look like one concept: `a` is the one a merge keeps (more links in, then more text)."""

    a: str
    b: str
    why: str  # name | alias | meaning
    score: float
    shared: str = ""  # the name they share (alias), or the cosine (meaning)

    @property
    def key(self) -> str:
        return pair_key(self.a, self.b)


def pair_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


DISTINCT = {"needs", "generalises", "special-case-of", "example-of", "contrasts-with", "part-of", "used-in"}


def concept_like(n: Note) -> bool:
    """A note that is one idea: not a dated (lecture) note, a course page, a class log or a book's index note (in the
    plain layout they share the subject's folder with the concept notes)."""
    return not NOT_CONCEPT.match(n.path.stem) and "books" not in n.slug.split("/")[:-1]


def keeper(index: Index, a: str, b: str) -> tuple[str, str]:
    """(the note a merge keeps, the other): more notes linking in, then more text, then the shorter path."""
    inbound = {a: 0, b: 0}
    for n in index.notes.values():
        for t in (a, b):
            if t in n.links and n.slug != t:
                inbound[t] += 1

    def rank(s: str):
        n = index.notes[s]
        return (-inbound[s], -len(n.head), len(s), s)

    first, second = sorted((a, b), key=rank)
    return first, second


def near_duplicates(
    index: Index, skip: set[str] | frozenset = frozenset(), focus: list[str] | None = None, cutoff: float = DUP_COSINE
) -> list[Pair]:
    """Pairs of notes that look like one concept, the surest first: the same name (normalised), a name they share (a
    title or alias of one is a title or alias of the other, 3+ characters), or embeddings at least `cutoff` alike
    (when there are vectors; `focus` limits that part to these notes against all, as it costs n x m). Pairs whose key
    is in `skip` (answered before) and pairs one of which already links the other as a different concept (needs,
    generalises, special-case-of, ...) are left out. No AI."""
    found: dict[str, Pair] = {}

    def distinct(a: str, b: str) -> bool:
        return index.notes[a].typed.get(b) in DISTINCT or index.notes[b].typed.get(a) in DISTINCT

    def add(a: str, b: str, why: str, score: float, shared: str = "") -> None:
        k = pair_key(a, b)
        if a == b or k in skip or k in found or distinct(a, b):
            return
        keep, other = keeper(index, a, b)
        found[k] = Pair(keep, other, why, score, shared)

    by_title: dict[str, list[str]] = {}
    by_any: dict[str, list[tuple[str, str]]] = {}
    ideas = {s: n for s, n in index.notes.items() if concept_like(n)}
    for s, n in sorted(ideas.items()):
        by_title.setdefault(normalise(n.title), []).append(s)
        for nm in dict.fromkeys([n.title, *n.aliases]):
            k = normalise(nm)
            if len(k) >= 3:
                by_any.setdefault(k, []).append((s, nm))
    for slugs in by_title.values():
        for i, a in enumerate(slugs):
            for b in slugs[i + 1 :]:
                add(a, b, "name", 1.0, index.notes[a].title)
    for rows in by_any.values():
        slugs = list(dict.fromkeys(s for s, _ in rows))
        for i, a in enumerate(slugs):
            for b in slugs[i + 1 :]:
                add(a, b, "alias", 0.95, next(nm for s, nm in rows if s == a))
    if index.vec:
        norm = {s: math.sqrt(sum(x * x for x in v)) or 1.0 for s, v in index.vec.items()}
        mine = [s for s in (focus if focus is not None else list(index.vec)) if s in index.vec and s in ideas]
        for a in mine:
            va, na = index.vec[a], norm[a]
            for b, vb in index.vec.items():
                if b == a or b not in ideas or pair_key(a, b) in found:
                    continue
                cs = sum(x * y for x, y in zip(va, vb, strict=False)) / (na * norm[b])
                if cs >= cutoff:
                    add(a, b, "meaning", round(cs, 3), f"{cs:.2f}")
    return sorted(found.values(), key=lambda p: (-p.score, p.key))


# ------------------------------------------------------------------------------------------- where vectors come from
class HttpEmbedder:
    """Embeddings from Ollama (nomic-embed-text, on this computer) or from Google's API with your Gemini key. Calling
    it returns one vector per text, or None when the service can't be reached (then keywords alone do the work)."""

    def __init__(self, kind: str, base: str = "", key: str = "", model: str = "", timeout: float = 60.0):
        self.kind, self.timeout = kind, timeout
        self.base = base or (
            "http://127.0.0.1:11434" if kind == "ollama" else "https://generativelanguage.googleapis.com"
        )
        self.key = key
        self.model = model or ("nomic-embed-text" if kind == "ollama" else "gemini-embedding-001")
        self.tag = f"{kind}:{self.model}:"

    def __call__(self, texts: list[str]) -> list[list[float]] | None:
        try:
            if self.kind == "ollama":
                body = {"model": self.model, "input": texts}
                url = f"{self.base}/api/embed"
            else:
                body = {
                    "requests": [{"model": f"models/{self.model}", "content": {"parts": [{"text": t}]}} for t in texts]
                }
                url = f"{self.base}/v1beta/models/{self.model}:batchEmbedContents?key={self.key}"
            req = urllib.request.Request(  # noqa: S310 (a fixed https or localhost address)
                url, json.dumps(body).encode(), {"Content-Type": "application/json"}, method="POST"
            )
            with egress.urlopen(req, "notes index", timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            vecs = (
                data.get("embeddings") if self.kind == "ollama" else [e["values"] for e in data.get("embeddings", [])]
            )
            return [list(map(float, v)) for v in vecs] if vecs and len(vecs) == len(texts) else None
        except (OSError, ValueError, KeyError, urllib.error.URLError):
            return None


def make_embedder(app: App) -> HttpEmbedder | None:
    """The best source of embeddings this computer has: Ollama with the model pulled, else the Gemini key; else None."""
    choice = str(app.settings.get("integrate.embeddings") or "auto")
    if choice == "off":
        return None
    if choice in ("auto", "ollama"):
        e = HttpEmbedder("ollama")
        if e(["test"]):
            return e
    key = app.secrets.get("gemini.api_key")
    if choice in ("auto", "gemini") and key:
        e = HttpEmbedder("gemini", key=key)
        if e(["test"]):
            return e
    return None
