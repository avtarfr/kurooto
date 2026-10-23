"""Writing into your notes for the concept graph, safely. Only lines are added, or one marked block is replaced; nothing
you wrote is changed, and a write that would change text outside Kurooto's blocks is refused.

Kurooto's blocks look like `<!-- kurooto:seen -->` ... `<!-- /kurooto:seen -->`. A note keeps at most one of each kind
(seen: where the concept is met in books; concepts: what a chapter note introduces), so running again replaces the block
and everything else stays the same.

Links are typed and carry their reason, one line each, in a `## Links` section:

    - special-case-of:: [[zettel/reverse-mode-ad]] — the deltas are the adjoints on a layered graph

The relation words: needs, generalises, special-case-of, example-of, contrasts-with, equivalent-to, part-of, used-in.
A reason that would be true of any pair of notes ("related to", "connected formulation", "alignment") is refused.

Merging two notes about one concept (0.5.22, modules/integrate.py): the kept note gets the other's typed links, "Seen
in" rows, names (as aliases) and notation, plus a `merged` block saying what came from where; the other gets a
`merged-into` block under its title (a redirect). Its own text stays, unless Kurooto wrote all of it (the text outside
its blocks is exactly as the concept graph made it: `made_by_graph`), when it shrinks to the title and the redirect,
its text having moved into the kept note's `merged` block. Typed link lines elsewhere that pointed at it point at the
kept note. Every file's before-copy is kept for Undo.

A concept met in a second source with other notation gets a `notation` block: a table of what each source writes,
each row's quote checked against its pages (core/integrate_ai.py).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

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


def put_block_top(text: str, key: str, body: str) -> str:
    """Like put_block, but a new block goes under the note's title (where a redirect is seen first)."""
    pat = re.compile(rf"<!-- kurooto:{re.escape(key)}\b[^>]*-->.*?<!-- /kurooto:{re.escape(key)} -->", re.S)
    new = block(key, body)
    if pat.search(text):
        return pat.sub(lambda _: new, text, count=1)
    h = re.search(r"(?m)^# .*\n?", text)
    if not h:
        return new + "\n\n" + text
    head = text[: h.end()] if text[: h.end()].endswith("\n") else text[: h.end()] + "\n"
    return head + "\n" + new + "\n" + text[h.end() :]


def drop_block(text: str, key: str) -> str:
    """The note without its `key` block (and the blank line it leaves)."""
    k = re.escape(key)
    return re.sub(rf"\n?<!-- kurooto:{k}\b[^>]*-->.*?<!-- /kurooto:{k} -->\n?", "\n", text, count=1, flags=re.S)


def link_lines(text: str) -> list[tuple[str, str]]:
    """Kurooto's typed link lines in a note: [(target, line)]."""
    out = []
    for ln in text.splitlines():
        m = LINK_LINE.match(ln) and WIKILINK.search(ln)
        if m:
            out.append((m[1].strip().removesuffix(".md"), ln))
    return out


def drop_link_lines(text: str, only: set[str] | None = None) -> str:
    """The note without Kurooto's typed link lines (to the targets in `only`, when given)."""
    keep = []
    for ln in text.split("\n"):
        m = LINK_LINE.match(ln) and WIKILINK.search(ln)
        if m and (only is None or m[1].strip().removesuffix(".md") in only):
            continue
        keep.append(ln)
    return "\n".join(keep)


def retarget(text: str, old: str, new: str) -> str:
    """Kurooto's typed link lines to `old` point at `new` instead; one that would repeat a link to `new` goes."""
    have = targets(text) - {old}
    out = []
    for ln in text.split("\n"):
        m = LINK_LINE.match(ln) and WIKILINK.search(ln)
        if m and m[1].strip().removesuffix(".md") == old:
            if new in have:
                continue
            ln = ln[: m.start()] + f"[[{new}]]" + ln[m.end() :]
            have.add(new)
        out.append(ln)
    return "\n".join(out)


def own_body(text: str) -> str:
    """What a note says outside Kurooto's lines, without its frontmatter, title and source line: the text a merge
    moves when Kurooto wrote all of it."""
    t = re.sub(r"\A---\n.*?\n---\n?", "", outside(text), count=1, flags=re.S)
    t = re.sub(r"(?m)^# .*$", "", t, count=1)
    t = re.sub(r"(?m)^---\s*$", "", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def made_by_graph(text: str, made_hash: str | None) -> bool:
    """Is all the text outside Kurooto's blocks as the concept graph wrote it (its hash when it was made)?"""
    return bool(made_hash) and outside_hash(text) == made_hash


def redirect_note(text: str, target: str, title: str, day: str) -> str:
    """A note that Kurooto wrote all of, cut to its frontmatter, title and a merged-into block."""
    m = re.match(r"\A---\n.*?\n---\n?", text, re.S)
    front = m[0] if m else ""
    h = re.search(r"(?m)^# .*$", text)
    head = h[0] if h else f"# {Path(target).name}"
    body = f"Merged into [[{target}|{title}]] on {day}: its definition, links and where it's seen are there now."
    return f"{front}{head}\n\n{block('merged-into', body)}\n"


def cell(text: str) -> str:
    """Text for a table cell: one line, pipes escaped."""
    return re.sub(r"\s+", " ", str(text or "")).strip().replace("|", "\\|")


def math_cell(symbol: str) -> str:
    """Notation for a table cell: LaTeX-looking text (or a short symbol) in $...$, a convention in words as it is."""
    s = cell(symbol)
    if "$" in s or not s:
        return s
    return f"${s}$" if re.search(r"[\\_^{}]", s) or len(s) <= 3 else s


def notation_table(rows: list[dict]) -> str:
    """The "Notation" block's body, when the sources write the concept differently: [{"source", "symbol", "what"}].
    Empty when only one source has notation or every source writes it the same way."""
    per: dict[str, set[str]] = {}
    for r in rows:
        per.setdefault(r["source"], set()).add(re.sub(r"[^a-z0-9]+", "", str(r["symbol"]).lower()))
    if len(per) < 2 or len({frozenset(v) for v in per.values()}) < 2:
        return ""
    lines = ["## Notation", "| Source | Notation | What it stands for |", "|---|---|---|"]
    for r in rows[:16]:
        lines.append(f"| {cell(r['source'])} | {math_cell(r['symbol'])} | {cell(r['what'])} |")
    return "\n".join(lines)


def outside(text: str) -> str:
    """The text with every Kurooto block (and the lines it added to a `## Links` section) taken out: what's yours."""
    t = BLOCK_ANY.sub("", text)
    kept = (
        ln
        for ln in t.splitlines()
        if not LINK_LINE.match(ln) and not re.match(r"^##\s+Links\s*$", ln) and not ln.startswith("aliases:")
    )
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
