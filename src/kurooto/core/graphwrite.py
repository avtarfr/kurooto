"""Writing into your notes for the concept graph, safely. Only lines are added, or one marked block is replaced; nothing
you wrote is changed, and a write that would change text outside Kurooto's blocks is refused.

Kurooto's blocks look like `<!-- kurooto:seen -->` ... `<!-- /kurooto:seen -->`. A note keeps at most one of each kind
(seen: where the concept is met in books; concepts: what a chapter note introduces), so running again replaces the block
and everything else stays the same.

Links are typed and carry their reason, one line each, in a `## Links` section:

    - special-case-of:: [[zettel/reverse-mode-ad]] — the deltas are the adjoints on a layered graph

The relation words: needs, generalises, special-case-of, example-of, contrasts-with, equivalent-to, part-of, used-in.
A reason that would be true of any pair of notes ("related to", "connected formulation", "alignment") is refused.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

RELATIONS = (
    "needs",
    "generalises",
    "special-case-of",
    "example-of",
    "contrasts-with",
    "equivalent-to",
    "part-of",
    "used-in",
)
GENERIC = re.compile(
    r"^\s*(?:related to|see also|connected|connection|topical|alignment|aligned with|source textbook|research program|"
    r"relevant to|similar to|associated with|links? to|also see)\b",
    re.I,
)
GENERIC_ANY = re.compile(r"connected formulation|syllabus (?:&|and) examination|research program alignment", re.I)
BLOCK = "<!-- kurooto:{key} -->"
BLOCK_END = "<!-- /kurooto:{key} -->"
BLOCK_ANY = re.compile(r"<!-- kurooto:(?P<k>[\w.-]+)[^>]*-->.*?<!-- /kurooto:(?P=k) -->", re.S)
OLD_BOOK_BLOCK = re.compile(r"<!-- kurooto:book\b.*?<!-- /kurooto:book -->", re.S)
LINK_LINE = re.compile(r"^- (?:" + "|".join(RELATIONS) + r"):: \[\[")
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def lint_reason(reason: str) -> str | None:
    """Why a link's reason isn't good enough, or None when it is."""
    r = re.sub(r"\s+", " ", reason or "").strip()
    if len(r.split()) < 5:
        return "too short to say anything"
    if GENERIC.match(r) or GENERIC_ANY.search(r):
        return "it would be true of any two notes"
    return None


def link_line(relation: str, target: str, reason: str) -> str:
    reason = re.sub(r"\s+", " ", reason).strip().rstrip(".")
    return f"- {relation}:: [[{target}]] — {reason}"


def block(key: str, body: str, attrs: str = "") -> str:
    head = f"<!-- kurooto:{key} {attrs} -->" if attrs else BLOCK.format(key=key)
    return f"{head}\n{body.strip()}\n{BLOCK_END.format(key=key)}"


def put_block(text: str, key: str, body: str, attrs: str = "") -> str:
    """The note with its `key` block replaced (or added at the end), the rest exactly as it was."""
    new = block(key, body, attrs)
    pat = re.compile(rf"<!-- kurooto:{re.escape(key)}\b[^>]*-->.*?<!-- /kurooto:{re.escape(key)} -->", re.S)
    if pat.search(text):
        return pat.sub(lambda _: new, text, count=1)
    return text.rstrip("\n") + "\n\n" + new + "\n"


def outside(text: str) -> str:
    """The text with every Kurooto block (and the lines it added to a `## Links` section) taken out: what's yours."""
    t = BLOCK_ANY.sub("", text)
    kept = (ln for ln in t.splitlines() if not LINK_LINE.match(ln) and not re.match(r"^##\s+Links\s*$", ln))
    return "\n".join(kept)


def outside_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", outside(text)).strip().encode("utf-8")).hexdigest()


def targets(text: str) -> set[str]:
    return {m[1].strip().removesuffix(".md") for m in WIKILINK.finditer(text)}


def add_links(text: str, lines: list[tuple[str, str]]) -> tuple[str, int]:
    """Add [(target, line)] to the `## Links` section, skipping targets the note already links. Returns the text and
    how many lines went in."""
    from kurooto.core.tools import add_to_section

    have = targets(text)
    fresh = []
    for target, line in lines:
        if target not in have:
            fresh.append(line)
            have.add(target)
    if not fresh:
        return text, 0
    return add_to_section(text, "Links", "\n".join(fresh)), len(fresh)


@dataclass
class Check:
    """What a write is allowed to change: `ok` is False (and `why` says) if text outside Kurooto's lines moved."""

    ok: bool = True
    why: str = ""


def guarded(old: str, new: str) -> Check:
    if outside_hash(old) != outside_hash(new):
        return Check(False, "it would have changed text that isn't Kurooto's")
    return Check()


@dataclass
class Concept:
    """A concept as it is written into a new note."""

    name: str
    slug: str  # the note's path without .md
    aliases: list[str] = field(default_factory=list)
    definition: str = ""
    formulas: list[str] = field(default_factory=list)
    kind: str = "definition"
    tags: list[str] = field(default_factory=list)


def new_note(front: str, c: Concept, links: list[str], source_line: str) -> str:
    body = [f"{front}# {c.name}", "", c.definition.strip() or f"{c.name}."]
    for f in c.formulas[:6]:
        f = f.strip().strip("$")
        if f:
            body += ["", f"$${f}$$"]
    body += ["", "## Links", *(links or [])]
    body += ["", "---", source_line.strip()]
    return "\n".join(body).rstrip() + "\n"
