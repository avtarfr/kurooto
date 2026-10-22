"""Sections of a book, from the text of its pages, and batches of them for reading by an AI.

Where the structure comes from, best first:
  1. the PDF's bookmarks (an outline),
  2. numbered headings in the text ("10.4 Pooling") and the running headers at the top of pages ("10.4. POOLING 295"),
  3. "Chapter 3 ..." lines (a book with no numbered sections).

A line that only points at a section ("Section 9.1", "Exercise 2.8", "Appendix B": a margin note or a cross-reference)
is never a heading: a heading has a title after its number, its numbers only go up, and it sits at the top of a page
or after a blank line. (A margin cross-reference once turned every chapter of a book into a list of other chapters'
sections.)

    sections(pages, outline, total)   [Section(level, number, title, first, last)]
    batches(sections, pages)          [Batch(id, title, first, last, sections)], 3 to 20 pages each, about 12
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

NUMBERED = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+([A-Za-z][^\n]{2,90}?)\s*$")
RUNNING = re.compile(
    r"^\s*(?:(\d{1,4})\s+)?(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+([A-Za-z][^\n]{2,90}?)(?:\s+(\d{1,4}))?\s*$"
)
WORDED = re.compile(
    r"^\s*(chapter|part|unit|lecture|appendix)\s+(\d+|[ivxlc]+|[A-Z])\b[.:]?\s+([A-Za-z].{2,80})$", re.I
)
REFERENCE = re.compile(
    r"^\s*(?:see\s+)?(?:section|sections|chapter|exercise|figure|table|appendix|equation|eq\.?|page|pp?\.)\s+"
    r"[\dA-Z][\d.\-A-Za-z]*\s*[.,;)]*\s*$",
    re.I,
)
SENTENCE = re.compile(r"[.;:,]\s*$|\b(?:the|of|and|is|are|we|this|that)\s*$", re.I)  # prose, not a title
MAX_BATCH = 20
MIN_BATCH = 3
TARGET = 12


@dataclass
class Section:
    level: int  # 1 = chapter, 2 = section, 3 = subsection
    number: str  # "10.4", or "" when the book has only titles
    title: str
    first: int
    last: int = 0


@dataclass
class Batch:
    id: str  # stable: first page and last page
    title: str
    first: int
    last: int
    sections: list[str] = field(default_factory=list)

    @property
    def pages(self) -> int:
        return self.last - self.first + 1


def key(number: str) -> tuple[int, ...]:
    return tuple(int(x) for x in number.split(".") if x.isdigit())


def is_reference(line: str) -> bool:
    return bool(REFERENCE.match(line))


def clean_title(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip(" .:·")
    return t[:100]


def heading(line: str) -> tuple[str, str] | None:
    """(number, title) when this line is a numbered heading; None for a reference, a sentence or a number alone."""
    if is_reference(line):
        return None
    m = NUMBERED.match(line)
    if not m:
        return None
    number, title = m[1], clean_title(m[2])
    if len(title.split()) > 12 or SENTENCE.search(title) or title.islower() and len(title) > 40:
        return None
    if re.fullmatch(r"[\d\s.,()-]+", title):
        return None
    return number, title


def top_lines(text: str, n: int = 4) -> list[str]:
    return [ln for ln in (text or "").splitlines() if ln.strip()][:n]


def running_header(text: str) -> tuple[str, str] | None:
    """A page's running header ("10.4. POOLING 295" or "292 10. CONVOLUTIONAL NETWORKS"): (number, title)."""
    for ln in top_lines(text, 3):
        if is_reference(ln):
            continue
        m = RUNNING.match(ln)
        if m and (m[1] or m[4]):  # a page number on one side: that is what makes it a running header
            title = clean_title(m[3])
            if title and not SENTENCE.search(title):
                return m[2], title
    return None


def from_outline(outline: list[tuple[int, str, int | None]], total: int, depth: int = 2) -> list[Section]:
    marks = [(lv, t, p) for lv, t, p in outline if p and lv <= depth and t.strip() and not is_reference(t)]
    out: list[Section] = []
    for i, (lv, title, first) in enumerate(marks):
        nxt = next((p for lv2, _, p in marks[i + 1 :] if lv2 <= lv), total + 1)
        m = re.match(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+(.*)$", title)
        out.append(
            Section(lv, m[1] if m else "", clean_title(m[2] if m else title), first, max(first, min(nxt - 1, total)))
        )
    return out


def from_text(pages: dict[int, str], total: int) -> list[Section]:
    """Sections from numbered headings and running headers, numbers only going up."""
    found: list[Section] = []
    last_key: tuple[int, ...] = ()
    for n in sorted(pages):
        text = pages[n]
        cands: list[tuple[str, str]] = []
        h = running_header(text)
        if h:
            cands.append(h)
        lines = (text or "").splitlines()
        for i, ln in enumerate(lines):
            if not ln.strip() or is_reference(ln):
                continue
            hd = heading(ln)
            if hd and (i < 6 or (i and not lines[i - 1].strip())):  # near the top, or after a blank line
                cands.append(hd)
        for number, title in cands:
            k = key(number)
            if not k:
                continue
            if found and found[-1].number == number:  # the same section's running header again
                if found[-1].title.isupper() and not title.isupper():
                    found[-1].title = title  # a running header is in capitals: keep the heading's own wording
                continue
            if last_key and k <= last_key and not (len(k) < len(last_key) and k > last_key[: len(k)]):
                continue  # not going up: a stray reference, or a list of other sections
            if len(k) > 1 and last_key and k[0] != last_key[0] and k[0] != last_key[0] + 1 and found:
                continue  # jumps to another chapter's numbers: a cross-reference, not this book's heading
            found.append(Section(min(len(k), 3), number, title, n))
            last_key = k
    return finish(found, total)


def worded(pages: dict[int, str], total: int) -> list[Section]:
    found: list[Section] = []
    for n in sorted(pages):
        for ln in top_lines(pages[n], 4):
            m = WORDED.match(ln)
            if m and not is_reference(ln):
                found.append(Section(1, "", re.sub(r"\s+", " ", ln).strip()[:100], n))
                break
    return finish(found, total)


def finish(found: list[Section], total: int) -> list[Section]:
    for i, s in enumerate(found):
        nxt = next((o.first for o in found[i + 1 :] if o.level <= s.level), total + 1)
        s.last = max(s.first, min(nxt - 1, total))
    return found


def sections(pages: dict[int, str], outline: list[tuple[int, str, int | None]], total: int) -> list[Section]:
    """The book's sections: from its bookmarks, else from its numbered headings, else from "Chapter N" lines."""
    out = from_outline(outline, total)
    if len(out) >= 2:
        return out
    out = from_text(pages, total)
    if len(out) >= 2:
        return out
    return worded(pages, total) or out


def batches(secs: list[Section], total: int, target: int = TARGET) -> list[Batch]:
    """Batches of 3 to 20 pages (about `target`) that follow the sections: small ones join the next, big ones are
    cut. Without sections, windows of `target` pages. Every page is in exactly one batch."""
    if total <= 0:
        return []
    units = [s for s in secs if s.level == 2]  # a chapter's sections, else (a book of chapters) the chapters
    if len(units) < 2:
        units = [s for s in secs if s.level == 1] or [s for s in secs if s.level <= 2]
    if not units:
        units = [Section(1, "", "", 1, total)]
    # make the units cover pages 1..total without gaps or overlap
    cover: list[Section] = []
    pos = 1
    for s in sorted(units, key=lambda u: (u.first, u.level)):
        if s.first < pos:
            continue
        if s.first > pos and cover:
            cover[-1].last = s.first - 1
        elif s.first > pos:
            s = Section(s.level, s.number, s.title, pos, s.last)
        cover.append(Section(s.level, s.number, s.title, s.first, s.last))
        pos = s.last + 1
    if cover:
        cover[0].first = 1
        cover[-1].last = total
    out: list[Batch] = []
    cur: Batch | None = None

    def close() -> None:
        nonlocal cur
        if cur:
            out.append(cur)
            cur = None

    for s in cover:
        pages = s.last - s.first + 1
        label = f"{s.number} {s.title}".strip()
        if pages > MAX_BATCH:  # cut a big section into even windows
            close()
            n = -(-pages // target)
            size = -(-pages // n)
            a = s.first
            for i in range(n):
                b = min(s.last, a + size - 1)
                out.append(Batch(f"{a}-{b}", f"{label} ({i + 1}/{n})".strip(), a, b, [s.number] if s.number else []))
                a = b + 1
            continue
        if cur is None:
            cur = Batch(f"{s.first}-{s.last}", label, s.first, s.last, [s.number] if s.number else [])
        elif cur.pages + pages <= max(target, MIN_BATCH) and cur.pages < MIN_BATCH + target // 2:
            cur.last = s.last
            cur.id = f"{cur.first}-{cur.last}"
            cur.title = f"{cur.title}; {label}" if label else cur.title
            if s.number:
                cur.sections.append(s.number)
        else:
            close()
            cur = Batch(f"{s.first}-{s.last}", label, s.first, s.last, [s.number] if s.number else [])
        if cur.pages >= target:
            close()
    close()
    # a last batch under the minimum joins the one before it
    if len(out) > 1 and out[-1].pages < MIN_BATCH:
        last = out.pop()
        out[-1].last = last.last
        out[-1].id = f"{out[-1].first}-{out[-1].last}"
    return out
