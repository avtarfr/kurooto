"""Finding notes that are copies of each other (0.8.0): the detector the notes sorter and the garden share. No AI.

    norm(text)            a note's words as they're compared: front matter, links' markup, case and spacing removed
    exact_key(text)       a hash of norm(text): two notes with the same key say the same thing
    sketch(text)          a small fingerprint (the 64 smallest hashes of 5-word shingles) for finding near copies fast
    similarity(a, b)      the share of 5-word shingles two notes have in common (Jaccard), 0 to 1
    Index                 add notes (id -> text); `near(text)` the ids that are copies or near copies of it, best first
    scan(notes)           every pair in a set of notes: [Pair(a, b, kind, score)]

kind is "exact" (the same words) or "near" (at least NEAR of the shingles shared: a note edited a little, or one
pasted into
another). Notes under MIN_WORDS words are too short to call copies of anything.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

SHINGLE = 5
SKETCH = 64
NEAR = 0.85
MIN_WORDS = 25
SHARE_MIN = 6  # sketch hashes two notes share before they're compared in full
FRONT = re.compile(r"\A---\n.*?\n---\n", re.S)
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]|\[([^\]]*)\]\([^)]*\)")
WORD = re.compile(r"[a-z0-9]+")


def norm(text: str) -> str:
    t = FRONT.sub("", text or "", count=1)
    t = LINK.sub(lambda m: m[2] or m[1] or m[3] or "", t)
    return " ".join(WORD.findall(t.lower()))


def exact_key(text: str) -> str:
    return hashlib.sha1(norm(text).encode(), usedforsecurity=False).hexdigest()[:16]  # noqa: S324


def _h(s: str) -> int:
    return int.from_bytes(hashlib.sha1(s.encode(), usedforsecurity=False).digest()[:8], "big")  # noqa: S324


def shingles(text: str) -> set[int]:
    w = norm(text).split()
    if len(w) < SHINGLE:
        return set()
    return {_h(" ".join(w[i : i + SHINGLE])) for i in range(len(w) - SHINGLE + 1)}


def sketch(text: str) -> list[int]:
    return sorted(shingles(text))[:SKETCH]


def words(text: str) -> int:
    return len(norm(text).split())


def similarity(a: str, b: str) -> float:
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return 0.0
    return round(len(sa & sb) / len(sa | sb), 4)


@dataclass(frozen=True)
class Pair:
    a: str
    b: str
    kind: str  # "exact" | "near"
    score: float

    @property
    def key(self) -> str:
        return "|".join(sorted((self.a, self.b)))


def compare(a: str, b: str) -> tuple[str, float] | None:
    """("exact" | "near", score) when the two are copies, else None."""
    if words(a) < MIN_WORDS or words(b) < MIN_WORDS:
        return None
    if exact_key(a) == exact_key(b):
        return "exact", 1.0
    s = similarity(a, b)
    return ("near", s) if s >= NEAR else None


class Index:
    """Notes by id, with their sketches, so a note is compared only with the few that share some of its shingles."""

    def __init__(self) -> None:
        self.text: dict[str, str] = {}
        self.sk: dict[str, list[int]] = {}
        self.by_hash: dict[int, set[str]] = {}
        self.exact: dict[str, set[str]] = {}

    def add(self, nid: str, text: str) -> None:
        if nid in self.text:
            self.remove(nid)
        if words(text) < MIN_WORDS:
            return
        self.text[nid] = text
        self.sk[nid] = sketch(text)
        for h in self.sk[nid]:
            self.by_hash.setdefault(h, set()).add(nid)
        self.exact.setdefault(exact_key(text), set()).add(nid)

    def remove(self, nid: str) -> None:
        text = self.text.pop(nid, None)
        for h in self.sk.pop(nid, []):
            self.by_hash.get(h, set()).discard(nid)
        if text is not None:
            self.exact.get(exact_key(text), set()).discard(nid)

    def near(self, text: str, exclude: str = "") -> list[tuple[str, str, float]]:
        """[(id, kind, score)] of the notes that are copies of this text, best first."""
        if words(text) < MIN_WORDS:
            return []
        out: dict[str, tuple[str, float]] = {
            n: ("exact", 1.0) for n in self.exact.get(exact_key(text), set()) if n != exclude
        }
        share: dict[str, int] = {}
        for h in sketch(text):
            for n in self.by_hash.get(h, ()):
                if n != exclude and n not in out:
                    share[n] = share.get(n, 0) + 1
        for n, c in share.items():
            if c >= SHARE_MIN:
                s = similarity(text, self.text[n])
                if s >= NEAR:
                    out[n] = ("near", s)
        return sorted(((n, k, s) for n, (k, s) in out.items()), key=lambda x: (-x[2], x[0]))


def scan(notes: dict[str, str]) -> list[Pair]:
    """Every copy pair among these notes (each pair once), exact ones first, then by score."""
    ix = Index()
    for nid, text in notes.items():
        ix.add(nid, text)
    seen: set[str] = set()
    out: list[Pair] = []
    for nid in sorted(ix.text):
        for other, kind, score in ix.near(ix.text[nid], exclude=nid):
            p = Pair(*sorted((nid, other)), kind, score)  # type: ignore[arg-type]
            if p.key not in seen:
                seen.add(p.key)
                out.append(p)
    return sorted(out, key=lambda p: (p.kind != "exact", -p.score, p.key))
