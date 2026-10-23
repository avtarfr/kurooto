"""Fitting Kurooto to the notes you already have (0.5.20): read the folder, propose where each kind of note goes, and
move the notes Kurooto wrote to the new places. No AI: names, dates and counts only.

    scan(root)               what's there: top-level folders, how daily notes are named and where ("Daily Notes/
                             2026-10-20.md", "dailies/", "2026/10/20.md"), [[wikilinks]] or markdown links (with or
                             without .md), the frontmatter keys in use, where subject folders live, an inbox
    propose(root, current)   notes.layout and the lines of notes.paths from that, each with how sure it is and why,
                             and a preview ("Daily notes -> Daily Notes/2026-10-20.md")
    plan(root, old, new)     a dry run: Kurooto's own notes (made_by, or trust_tier: agent_written) that would move,
                             the links that would be fixed, and what stays. Nothing is written.
    apply_plan(...)          the plan, only when its digest matches the one you were shown; a move log for Undo
    undo(...)                puts the notes, the link fixes and the settings back

What moves: only notes with Kurooto's header. Daily notes (they hold your words, and have no header), your profile and
every note of yours stay where they are; new ones go to the new place. Links are fixed only in Kurooto's text: its own
notes, its `<!-- kurooto:x -->` blocks in your notes, and the hub lists it keeps in the home note. Links in your own
text that point at a moved note are listed, never changed. A move whose new place is taken is a clash, and a plan with a
clash isn't applied. The move log is kept in Kurooto's state folder (notes-moves/), so Undo works with or without git;
in a notes folder that is a git repository the moves show up as renames.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import posixpath
import re
import time
import urllib.parse
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

SKIP = {".git", ".obsidian", ".trash", ".stfolder", ".vscode", "node_modules", "__pycache__"}
MAX_FILES = 20000  # notes read at most (a bigger folder is read in part, and says so)
HEAD = 4096  # bytes read for a note's header
SAMPLE = 3000  # notes read in full for links (the rest for headers only)

FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:", re.M)
WIKI = re.compile(r"\[\[([^\]\|#\n]+)((?:#[^\]\|\n]*)?(?:\|[^\]\n]*)?)\]\]")
MDLINK = re.compile(r"(!?)\[([^\]\n]*)\]\(\s*(<[^>\n]+>|[^)\s]+)(\s+\"[^\"\n]*\")?\s*\)")
BLOCK = re.compile(r"<!-- kurooto:(?P<k>[\w.-]+)[^>]*-->.*?<!-- /kurooto:(?P=k) -->", re.S)
ONE_LINE = re.compile(r"<!-- kurooto:hubs -->[^\n]*\n[^\n]*")  # hubs.BACK: a marker and the line under it
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)

# The lines you see and can change; the places that follow from them are worked out (paths_from).
LINES = (
    ("daily", "Daily notes"),
    ("inbox", "Quick notes (inbox)"),
    ("subject", "Subject folders"),
    ("concept", "Concept notes"),
    ("project", "Research projects"),
)
SAMPLE_SUBJECT = "linear-algebra"
PREVIEW = (
    ("daily", "Daily notes", {}),
    ("note", "Quick notes", {"slug": "an-idea"}),
    ("course", "A course page", {"subject": SAMPLE_SUBJECT}),
    ("lecture", "Lecture notes", {"subject": SAMPLE_SUBJECT, "slug": "eigenvalues"}),
    ("exam_prep", "Exam prep", {"subject": SAMPLE_SUBJECT}),
    ("concept", "Concept notes", {"subject": SAMPLE_SUBJECT, "slug": "eigenvalues"}),
    ("project", "A research project", {"project": "thesis"}),
    ("profile", "Your profile", {}),
    ("mail", "Mail digests", {"time": "0700"}),
)
SUBJECT_PARENTS = {
    "sources",
    "courses",
    "course",
    "subjects",
    "classes",
    "modules",
    "lectures",
    "semester",
    "semesters",
    "school",
    "university",
    "uni",
    "college",
    "study",
    "studies",
}
INBOXES = {"inbox": 0.85, "fleeting": 0.7, "fleeting notes": 0.7, "capture": 0.7, "captures": 0.7, "quick notes": 0.7}
CONCEPTS = {"zettel": 0.7, "zettelkasten": 0.7, "permanent": 0.6, "permanent notes": 0.6, "concepts": 0.6}
PROJECTS = {"projects": 0.6, "research": 0.6}
COURSE_FILES = {"course.md", "class-log.md", "exam-prep.md", "doubts.md"}
ZK_TOPS = {"dailies", "zettel", "maps", "sources", "master"}
KU_TOPS = {"journal", "about-me", "kurooto", "research"}
FIELD_RX = {
    "date": r"\d{4}-\d{2}-\d{2}",
    "time": r"\d{4}",
    "year": r"\d{4}",
    "month": r"\d{2}",
    "day": r"\d{2}",
}
FOLDER_KINDS = ("handwritten", "runs", "inbox")  # Kurooto's notes inside these folders keep their place in them
TAG_WORDS = {"zettel", "agent-written", "source", "lecture", "doubts", "class-log", "exam-prep", "map", "course"}


def norm(name: str) -> str:
    """A folder name as compared: "10 Courses" and "02-courses" are "courses"."""
    return re.sub(r"^[\d\s._-]+", "", name).strip().lower()


def front_of(text: str) -> str:
    m = FRONT.match(text)
    return m[1] if m else ""


def kuroto_wrote(front: str) -> bool:
    """A note with an agent's header (core/sources.py agent_written): made_by, or trust_tier: agent_written."""
    return bool(re.search(r"^(made_by:|trust_tier:\s*agent_written)", front, re.M))


def ours(front: str, L: layout.Layout) -> bool:
    """A note Kurooto wrote, as far as a move goes: made_by (its header in its own layout), or trust_tier:
    agent_written only where the layout in use is the zettelkasten (the header Kurooto writes there; other agents
    write it too, so it doesn't count in a folder Kurooto laid out its own way)."""
    if re.search(r"^made_by:", front, re.M):
        return True
    return L.preset == "zettelkasten" and bool(re.search(r"^trust_tier:\s*agent_written", front, re.M))


def _read(p: Path, limit: int | None = None) -> str | None:
    try:
        with open(p, encoding="utf-8", newline="") as f:
            return f.read(limit) if limit else f.read()
    except (OSError, UnicodeDecodeError):
        return None


def walk(root: Path, limit: int = MAX_FILES) -> tuple[list[str], list[str], bool]:
    """(notes, folders) inside root as paths with "/" ("Daily Notes/2026-10-20.md"), and whether it stopped early.
    Hidden folders (.git, .obsidian) and node_modules are left out."""
    notes: list[str] = []
    dirs: list[str] = []
    cut = False
    root = Path(root)
    for here, ds, fs in os.walk(root):
        ds[:] = sorted(d for d in ds if not d.startswith(".") and d not in SKIP)
        rel = Path(here).relative_to(root).as_posix()
        if rel != ".":
            dirs.append(rel)
        for f in sorted(fs):
            if f.lower().endswith(".md") and not f.startswith("."):
                notes.append(f if rel == "." else f"{rel}/{f}")
                if len(notes) >= limit:
                    return notes, dirs, True
    return notes, dirs, cut


# ------------------------------------------------------------------------------------------------ reading
def daily_shape(rel: str) -> str | None:
    """The place a daily note's path shows, as a template: "Daily Notes/{date}.md", "{year}/{month}/{day}.md"."""
    parts = rel.split("/")
    stem = parts[-1][:-3]
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", stem)
    if m:
        (y, mo, d), head, tail = m.groups(), parts[:-1], "{date}.md"
    elif (
        len(parts) >= 3
        and re.fullmatch(r"\d{2}", stem)
        and re.fullmatch(r"\d{4}", parts[-3])
        and re.fullmatch(r"\d{2}", parts[-2])
    ):
        (y, mo, d), head, tail = (parts[-3], parts[-2], stem), parts[:-3], "{year}/{month}/{day}.md"
    else:
        return None
    try:
        dt.date(int(y), int(mo), int(d))
    except ValueError:
        return None
    out: list[str] = []
    for p in head:  # "2026/10/2026-10-20.md" -> "{year}/{month}/{date}.md"
        out.append("{year}" if p == y else "{month}" if p == mo and out[-1:] == ["{year}"] else p)
    return "/".join([*out, tail])


@dataclass
class Scan:
    root: Path
    exists: bool = False
    notes: list[str] = field(default_factory=list)
    dirs: list[str] = field(default_factory=list)
    cut: bool = False
    fronts: dict[str, str] = field(default_factory=dict)  # note -> its header
    texts: dict[str, str] = field(default_factory=dict)  # notes read in full (for links)

    def view(self) -> dict:
        return facts(self)


def scan(root, limit: int = MAX_FILES) -> Scan:
    """Read the folder: names, headers, and links from up to SAMPLE notes. Nothing is written."""
    root = Path(os.path.expanduser(str(root)))
    sc = Scan(root=root, exists=root.is_dir())
    if not sc.exists:
        return sc
    sc.notes, sc.dirs, sc.cut = walk(root, limit)
    for i, rel in enumerate(sc.notes):
        full = i < SAMPLE
        t = _read(root / rel, None if full else HEAD)
        if t is None:
            continue
        sc.fronts[rel] = front_of(t)
        if full:
            sc.texts[rel] = t
    return sc


# the last folder read for the setup page's Notes step: (folder, what it was read from, the scan without its full
# texts, its facts). Each visit read every note again: 0.2 s for 2,000 notes (0.6.1).
_LAST: list = []


def scanned(root) -> tuple[Scan, dict]:
    """scan() and facts(), kept while the folder's notes stay the same: the same notes and folders, each note with the
    same modification time and size. Only facts() reads the full texts, so the kept scan drops them."""
    root = Path(os.path.expanduser(str(root)))
    if not root.is_dir():
        sc = scan(root)
        return sc, facts(sc)
    notes, dirs, cut = walk(root)
    seen = []
    for rel in notes:
        try:
            st = os.stat(os.path.join(root, rel))
            seen.append((rel, st.st_mtime_ns, st.st_size))
        except OSError:
            seen.append((rel, None, None))
    sig = (str(root), tuple(dirs), cut, tuple(seen))
    if _LAST and _LAST[0] == sig:
        return _LAST[1], copy.deepcopy(_LAST[2])
    sc = scan(root)
    fx = facts(sc)
    sc.texts = {}
    _LAST[:] = [sig, sc, fx]
    return sc, copy.deepcopy(fx)


def facts(sc: Scan) -> dict:
    """What the folder shows, in numbers (for the proposal and the setup page)."""
    top = Counter(n.split("/")[0] for n in sc.notes if "/" in n)
    tops = sorted({d.split("/")[0] for d in sc.dirs})
    # daily notes
    shapes = Counter(s for n in sc.notes if (s := daily_shape(n)))
    dated = sum(shapes.values())
    daily = None
    if shapes:
        tmpl, n = shapes.most_common(1)[0]
        example = next(x for x in sc.notes if daily_shape(x) == tmpl)
        daily = {"template": tmpl, "count": n, "dated": dated, "example": example}
    # links
    wiki = md_with = md_without = wiki_paths = wiki_ext = 0
    for t in sc.texts.values():
        for m in WIKI.finditer(t):
            wiki += 1
            wiki_paths += "/" in m[1]
            wiki_ext += m[1].strip().lower().endswith(".md")
        for m in MDLINK.finditer(t):
            if m[1]:
                continue
            target = m[3].strip("<>").split("#")[0]
            if not target or SCHEME.match(target):
                continue
            last = target.rsplit("/", 1)[-1]
            if last.lower().endswith(".md"):
                md_with += 1
            elif "." not in last:
                md_without += 1
    md = md_with + md_without
    links = {"wikilinks": wiki, "markdown": md, "with_md": md_with, "without_md": md_without, "paths": wiki_paths}
    links["style"] = "" if not (wiki or md) else "wikilinks" if wiki >= md else "markdown"
    links["confidence"] = round(max(wiki, md) / (wiki + md), 2) if wiki or md else 0.0
    links["wiki_ext"] = wiki_ext
    # headers
    keys: Counter = Counter()
    with_front = 0
    for f in sc.fronts.values():
        if f:
            with_front += 1
            keys.update(set(KEY.findall(f)))
    agent = sum(1 for f in sc.fronts.values() if kuroto_wrote(f))
    return {
        "folder": str(sc.root),
        "exists": sc.exists,
        "notes": len(sc.notes),
        "cut": sc.cut,
        "agent_notes": agent,
        "top": [{"name": k, "notes": top.get(k, 0)} for k in tops],
        "root_notes": sum(1 for n in sc.notes if "/" not in n),
        "daily": daily,
        "links": links,
        "frontmatter": {"notes": with_front, "keys": [[k, n] for k, n in keys.most_common(12)]},
    }


def _subjects(sc: Scan) -> tuple[str, float, str] | None:
    """Where subject folders live: a template ("Courses/{subject}"), how sure, and why."""
    # a folder holding Kurooto's course files is a subject, wherever it is
    parents = Counter()
    for n in sc.notes:
        parts = n.split("/")
        if len(parts) >= 2 and parts[-1] in COURSE_FILES:
            parents["/".join(parts[:-2])] += 1
    if parents:
        where, n = parents.most_common(1)[0]
        tmpl = f"{where}/{{subject}}" if where else "{subject}"
        return tmpl, 0.85, f"{n} subject folder{'s' if n > 1 else ''} with course pages in {where or 'the top level'}"
    kids: dict[str, set[str]] = {}
    for d in sc.dirs:
        parts = d.split("/")
        for depth in (1, 2):
            if len(parts) == depth + 1 and norm(parts[depth - 1]) in SUBJECT_PARENTS:
                kids.setdefault("/".join(parts[:depth]), set()).add(parts[depth])
    if not kids:
        return None
    where = min(kids, key=lambda k: (-len(kids[k]), k.count("/"), k))
    n = len(kids[where])
    eg = ", ".join(sorted(kids[where])[:3])
    return f"{where}/{{subject}}", (0.8 if n >= 2 else 0.6), f"{where}/ holds {n} folder{'s' if n > 1 else ''} ({eg})"


def _named(sc: Scan, names: dict[str, float]) -> tuple[str, float] | None:
    best = None
    for d in sc.dirs:
        if "/" in d:
            continue
        c = names.get(norm(d))
        if c and (best is None or c > best[1]):
            best = (d, c)
    return best


def _projects(sc: Scan) -> tuple[str, float, str] | None:
    hit = _named(sc, PROJECTS)
    if not hit:
        return None
    top, c = hit
    subs = {d.split("/")[1] for d in sc.dirs if d.startswith(top + "/") and d.count("/") == 1}
    if subs:
        return f"{top}/{{project}}/index.md", c, f"{top}/ has a folder per project ({', '.join(sorted(subs)[:3])})"
    hubs = {"index.md", "readme.md", f"{top.lower()}.md"}  # the folder's own hub note isn't a project
    if any(n.startswith(top + "/") and n.count("/") == 1 and n.split("/")[1].lower() not in hubs for n in sc.notes):
        return f"{top}/{{project}}.md", c - 0.1, f"{top}/ has a note per project"
    return None


def choose_layout(sc: Scan, fx: dict) -> tuple[str, float, str]:
    tops = {norm(t["name"]) for t in fx["top"]}
    zk, ku = len(tops & ZK_TOPS), len(tops & KU_TOPS)
    keys = dict((k, n) for k, n in fx["frontmatter"]["keys"])
    have = fx["frontmatter"]["notes"] or 0
    if have and min(keys.get("id", 0), keys.get("aliases", 0)) / have > 0.5:
        zk += 2
    if fx["daily"] and fx["daily"]["template"].startswith("dailies/"):
        zk += 1
    if fx["daily"] and fx["daily"]["template"].startswith("journal/"):
        ku += 1
    if not zk and not ku:
        return "kurooto", 0.5, "Nothing in the folder points either way, so Kurooto's own layout"
    if zk > ku:
        said = sorted(tops & ZK_TOPS)
        why = f"folders {', '.join(said)}" if said else "notes with id and aliases headers"
        return (
            "zettelkasten",
            round(min(0.95, 0.5 + 0.15 * (zk - ku)), 2),
            f"{why[0].upper()}{why[1:]} look like a zettelkasten",
        )
    said = ", ".join(sorted(tops & KU_TOPS)) or "nothing"
    return "kurooto", round(min(0.95, 0.5 + 0.15 * (ku - zk)), 2), f"Folders {said} are Kurooto's own"


def propose(root, current: layout.Layout | None = None, sc: Scan | None = None, fx: dict | None = None) -> dict:
    """notes.layout and a line per kind of note, each with a confidence (0 to 1) and why, the notes.paths that follow,
    and a preview. `current` is the layout in use (its custom places outside the lines are kept). `fx`: facts(sc),
    when the caller has them (scanned())."""
    sc = sc or scan(root)
    fx = facts(sc) if fx is None else fx
    preset, conf, why = choose_layout(sc, fx) if sc.exists and sc.notes else ("kurooto", 0.5, "The folder is empty")
    P = layout.PRESETS[preset]
    lines: list[dict] = []

    in_use = {k: current.template(k) for k, _ in LINES} if current is not None and current.preset == preset else {}

    def line(kind: str, label: str, found: tuple | None, none_why: str) -> None:
        if found:
            tmpl, c, w = found
            lines.append({"kind": kind, "label": label, "template": tmpl, "confidence": round(c, 2), "why": w,
                          "found": True})  # fmt: skip
        elif in_use.get(kind, P[kind]) != P[kind]:  # nothing found: the place you have now stays
            lines.append({"kind": kind, "label": label, "template": in_use[kind], "confidence": 0.5,
                          "why": "nothing found: the place in use now", "found": False})  # fmt: skip
        else:
            lines.append({"kind": kind, "label": label, "template": P[kind], "confidence": 0.5, "why": none_why,
                          "found": False})  # fmt: skip

    d = fx["daily"]
    daily = None
    if d:
        share = d["count"] / max(1, d["dated"])
        c = min(0.95, share * (0.5 + 0.1 * min(d["count"], 5)))
        daily = (d["template"], c, f"{d['count']} daily note{'s' if d['count'] > 1 else ''} like {d['example']}")
    for kind, label in LINES:
        if kind == "daily":
            line(kind, label, daily, "no daily notes found: the layout's place")
        elif kind == "inbox":
            hit = _named(sc, INBOXES)
            line(kind, label, (hit[0], hit[1], f"a folder called {hit[0]}") if hit else None, "no inbox folder found")
        elif kind == "subject":
            line(kind, label, _subjects(sc), "no subject folders found: the layout's place")
        elif kind == "concept":
            hit = _named(sc, CONCEPTS)
            found = (f"{hit[0]}/{{slug}}.md", hit[1], f"a folder called {hit[0]}") if hit else None
            line(kind, label, found, "the layout's place")
        elif kind == "project":
            line(kind, label, _projects(sc), "no projects folder found: the layout's place")
    chosen = {x["kind"]: x["template"] for x in lines}
    cur_paths = current.custom() if current is not None else {}
    paths = merged_paths(preset, chosen, cur_paths)
    said = notes_about(fx)
    style = link_style(fx, current)
    cur_links = current.note_style if current is not None else "wiki"
    return {
        **fx,
        "layout": preset,
        "layout_confidence": conf,
        "layout_why": why,
        "lines": lines,
        "paths": paths,
        "preview": preview(preset, paths, sc.root),
        "said": said,
        "link_style": style,
        "current": {"layout": current.preset, "paths": cur_paths, "links": cur_links} if current is not None else None,
        "same": current is not None and current.preset == preset and cur_paths == paths and cur_links == style["value"],
    }


def link_style(fx: dict, current: layout.Layout | None = None) -> dict:
    """notes.links from how the notes link: {"value": "wiki" | "markdown", "confidence", "why", "found"}. Nothing to
    go by: the style in use stays."""
    lk = fx["links"]
    n = lk["wikilinks"] + lk["markdown"]
    if lk["style"] == "markdown":
        return {"value": "markdown", "confidence": lk["confidence"], "found": True,
                "why": f"{lk['markdown']} of {n} links between notes are markdown links"}  # fmt: skip
    if lk["style"] == "wikilinks":
        return {"value": "wiki", "confidence": lk["confidence"], "found": True,
                "why": f"{lk['wikilinks']} of {n} links between notes are [[wikilinks]]"}  # fmt: skip
    cur = current.note_style if current is not None else "wiki"
    return {"value": cur, "confidence": 0.5, "found": False, "why": "no links between notes found: the style in use"}


def notes_about(fx: dict) -> list[str]:
    """Plain lines about what was found that no setting changes (yet)."""
    out = []
    lk = fx["links"]
    if lk["style"] == "markdown":
        ext = "with .md" if lk["with_md"] >= lk["without_md"] else "without .md"
        out.append(
            f"Your notes link with markdown links ({ext}). Kurooto can write its links the same way (Links: "
            "markdown), as [Name](path.md) relative to the note."
        )
    elif lk["style"] == "wikilinks":
        out.append("Your notes link with [[wikilinks]], as Kurooto does by default.")
    keys = [k for k, _ in fx["frontmatter"]["keys"]]
    if keys:
        out.append(f"Headers in your notes use: {', '.join(keys[:8])}.")
    if fx["cut"]:
        out.append(f"The folder is big: the first {fx['notes']} notes were read.")
    return out


def paths_from(preset: str, lines: dict[str, str]) -> dict[str, str]:
    """notes.paths from the lines: each line, the places that follow from it (a course page in the subject folder, a
    quick note in the inbox, a project's runs beside its note), minus what equals the layout's own place."""
    P = layout.PRESETS[preset]
    out: dict[str, str] = {}
    for kind, tmpl in lines.items():
        t = str(tmpl or "").strip().replace("\\", "/").strip("/")
        if kind in layout.KINDS and t and t.removesuffix(".md") != P[kind].removesuffix(".md"):
            out[kind] = t  # a line left at the layout's own place follows the lines it depends on
    derived: dict[str, str] = {}
    if "inbox" in out:
        derived["note"] = out["inbox"] + "/{slug}.md"
    if "subject" in out:
        sp = P["subject"] + "/"
        for k in ("course", "class_log", "lecture", "exam_prep", "doubts", "concept"):
            if P[k].startswith(sp):
                derived[k] = out["subject"] + "/" + P[k][len(sp) :]
    if "project" in out and re.search(r"/\{project\}/index(\.md)?$", out["project"]):
        derived["runs"] = out["project"].rsplit("/", 1)[0] + "/runs"
    for k, v in derived.items():
        out.setdefault(k, v)

    def same(a: str, b: str) -> bool:
        return a.removesuffix(".md") == b.removesuffix(".md")

    return {k: v for k, v in out.items() if not same(v, P[k])}


def touched(lines: dict[str, str]) -> set[str]:
    """The kinds the lines decide (themselves and what follows from them)."""
    t = set(lines)
    if "inbox" in t:
        t.add("note")
    if "subject" in t:
        t |= {"course", "class_log", "lecture", "exam_prep", "doubts"}
    if "project" in t:
        t.add("runs")
    return t


def merged_paths(preset: str, lines: dict[str, str], current: dict[str, str]) -> dict[str, str]:
    """The lines' places, plus your earlier custom places for kinds the lines don't decide."""
    keep = {k: v for k, v in (current or {}).items() if k not in touched(lines) and k in layout.KINDS}
    return {**keep, **paths_from(preset, lines)}


class _Values:
    """A Layout's settings from plain values (a proposal, or what's in effect)."""

    def __init__(self, values: dict):
        self.values = values

    def get(self, key: str, default=None):
        return self.values.get(key, default)


def layout_for(
    root, preset: str, paths: dict, base: layout.Layout | None = None, links: str | None = None
) -> layout.Layout:
    v = {"notes.layout": preset, "notes.paths": dict(paths or {})}
    v["notes.links"] = links if links in layout.NOTE_STYLES else (base.note_style if base is not None else "wiki")
    if base is not None:
        v["files.folder"] = base._get("files.folder") or ""
        v["files.links"] = base._get("files.links") or ""
    return layout.Layout(Path(root), _Values(v), base.assistant if base else "Kurooto")  # type: ignore[arg-type]


def preview(preset: str, paths: dict, root=".", day: dt.date | None = None) -> list[dict]:
    """Where each kind of note would go: [{"kind", "label", "path"}], with today's date and an example subject."""
    L = layout_for(root, preset, paths)
    day = day or now().date()
    out = []
    for kind, label, fields in PREVIEW:
        out.append({"kind": kind, "label": label, "path": L.rel(kind, date=day.isoformat(), **fields)})
    return out


# ------------------------------------------------------------------------------------------------ moving
def _matchers(L: layout.Layout) -> list[tuple[str, re.Pattern, bool]]:
    """(kind, a pattern for its place, folder?) for every kind, the most specific places first."""
    out = []
    for kind in layout.KINDS:
        tmpl = L.template(kind)
        folder = ".md" not in layout.PRESETS[layout.DEFAULT][kind]
        if folder and kind not in FOLDER_KINDS:
            continue
        if folder:
            tmpl = tmpl.rstrip("/")
        elif not tmpl.endswith(".md"):
            tmpl += ".md"
        if os.path.isabs(os.path.expanduser(tmpl)) or ".." in tmpl.split("/"):
            continue
        rx, lit, pos, seen = "", 0, 0, set()
        for m in re.finditer(r"\{(\w+)\}", tmpl):
            chunk = tmpl[pos : m.start()]
            rx += re.escape(chunk)
            lit += len(chunk)
            name = m[1]
            if name in seen:
                rx += f"(?P={name})"
            else:
                rx += f"(?P<{name}>{FIELD_RX.get(name, '[^/]+')})"
                seen.add(name)
            pos = m.end()
        chunk = tmpl[pos:]
        rx += re.escape(chunk)
        lit += len(chunk)
        if folder:
            rx += r"/(?P<_rest>.+\.md)"
            lit -= 1
        out.append((lit, len(seen), kind, re.compile(rx + r"\Z"), folder))
    out.sort(key=lambda x: (-x[0], x[1]))
    return [(k, rx, f) for _, _, k, rx, f in out]


def kind_of(L: layout.Layout, rel: str, matchers=None) -> tuple[str, dict, str] | None:
    """Which kind of note this place is in a layout, with its fields: ("lecture", {"subject": .., ...}, rest)."""
    for kind, rx, _folder in matchers if matchers is not None else _matchers(L):
        m = rx.match(rel)
        if not m:
            continue
        f = {k: v for k, v in m.groupdict().items() if k != "_rest"}
        if "subject" in f and L.kind_of_folder(f["subject"].split("/")[0]):
            continue  # "inbox/x.md" isn't a subject called inbox
        if "date" in f:
            try:
                dt.date.fromisoformat(f["date"])
            except ValueError:
                continue
        return kind, f, m.groupdict().get("_rest") or ""
    return None


def _subject_from(front: str) -> str:
    m = re.search(r"^subject:\s*\"?([^\"\n]+?)\"?\s*$", front, re.M)
    if m:
        return m[1].strip()
    m = re.search(r"^tags:\s*\[(.*?)\]", front, re.M)
    if m:
        for t in (x.strip().strip("\"'") for x in m[1].split(",")):
            if t and t not in TAG_WORDS:
                return t
    return ""


@dataclass
class Edit:
    file: str  # where it is after the moves
    before: str
    after: str
    fixed: int


@dataclass
class Plan:
    root: Path
    moves: list[dict] = field(default_factory=list)  # {"from", "to", "kind"}
    clashes: list[dict] = field(default_factory=list)  # {"from", "to", "why"}
    left: list[dict] = field(default_factory=list)  # Kurooto's notes that can't move: {"path", "why"}
    daily_left: int = 0  # daily notes staying where they are
    daily_from: str = ""
    edits: list[Edit] = field(default_factory=list)
    theirs: list[dict] = field(default_factory=list)  # your notes with links to moved notes: {"file", "links"}
    git: bool = False
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)

    @property
    def digest(self) -> str:
        h = hashlib.sha256()
        h.update(json.dumps([self.moves, self.before, self.after], sort_keys=True).encode())
        for e in self.edits:
            h.update(e.file.encode() + hashlib.sha256(e.before.encode()).digest())
        return h.hexdigest()[:16]

    def view(self, limit: int = 50) -> dict:
        return {
            "moves": self.moves[:limit],
            "count": len(self.moves),
            "clashes": self.clashes,
            "left": self.left[:limit],
            "daily_left": self.daily_left,
            "daily_from": self.daily_from,
            "fixes": [{"file": e.file, "links": e.fixed} for e in self.edits][:limit],
            "fixed": sum(e.fixed for e in self.edits),
            "theirs": self.theirs[:limit],
            "their_links": sum(x["links"] for x in self.theirs),
            "git": self.git,
            "digest": self.digest,
            "ok": not self.clashes,
        }


def _spans(text: str, ours: bool, hub: bool) -> list[tuple[int, int]]:
    """Kurooto's text in a note: all of it in its own notes; its blocks (and hub lists in the home note) in yours."""
    if ours:
        return [(0, len(text))]
    out = [(m.start(), m.end()) for m in BLOCK.finditer(text)]
    out += [(m.start(), m.end()) for m in ONE_LINE.finditer(text)]
    if hub:  # the lists hubs.py keeps: "- [[target|Name]]" or "- [Name](target.md)" lines
        out += [
            (m.start(), m.end())
            for m in re.finditer(r"^- (?:\[\[[^\]\n]+\]\]|\[[^\]\n]*\]\([^)\n]+\))[ \t]*$", text, re.M)
        ]
    return out


def _inside(pos: int, spans) -> bool:
    return any(a <= pos < b for a, b in spans)


def _md_target(new: str, angle: bool, encoded: bool) -> str:
    if angle:
        return f"<{new}>"
    return urllib.parse.quote(new, safe="/#.-_~()!$&'*+,;=:@") if encoded or " " in new else new


def fix_links(text: str, rel: str, new_rel: str, moved: dict[str, str], ours: bool, hub: bool = False):
    """The note with links to moved notes pointing at their new places, in Kurooto's text only, and its own relative
    links kept right when it moved itself. Returns (text, links fixed, links to moved notes left in your text)."""
    links = {a[:-3]: b[:-3] for a, b in moved.items()}
    spans = _spans(text, ours, hub)
    fixed = theirs = 0
    out, pos = [], 0
    edits: list[tuple[int, int, str]] = []
    for m in WIKI.finditer(text):
        t = m[1].strip()
        key = t[:-3] if t.lower().endswith(".md") else t
        if key not in links:
            continue
        if not _inside(m.start(), spans):
            theirs += 1
            continue
        new = links[key] + (t[-3:] if t.lower().endswith(".md") else "")
        edits.append((m.start(), m.end(), f"[[{new}{m[2]}]]"))
        fixed += 1
    old_dir, new_dir = posixpath.dirname(rel), posixpath.dirname(new_rel)
    for m in MDLINK.finditer(text):
        raw = m[3]
        angle = raw.startswith("<")
        target = raw[1:-1] if angle else raw
        if not target or SCHEME.match(target) or target.startswith(("#", "/")):
            continue
        path, _, anchor = target.partition("#")
        encoded = "%" in path
        plain = urllib.parse.unquote(path)
        where = posixpath.normpath(posixpath.join(old_dir, plain)) if plain else ""
        hit = where if where in moved else where + ".md" if where + ".md" in moved else None
        if hit is None and rel == new_rel:
            continue
        if not _inside(m.start(), spans):
            theirs += hit is not None
            continue
        if hit is not None:
            dest = moved[hit]
            if not plain.lower().endswith(".md"):
                dest = dest[:-3]
            fixed += 1
        else:
            dest = where  # this note moved: the same file from its new folder
        new = posixpath.relpath(dest, new_dir or ".")
        new = _md_target(new, angle, encoded) + (f"#{anchor}" if anchor else "")
        if new != raw:
            edits.append((m.start(3), m.end(3), new))
    for a, b, s in sorted(edits):
        out.append(text[pos:a])
        out.append(s)
        pos = b
    out.append(text[pos:])
    return "".join(out), fixed, theirs


def _new_id(text: str, old: str, new: str) -> str:
    """A zettelkasten header's id: (the note's path without .md) for its new place."""
    m = FRONT.match(text)
    if not m:
        return text
    head = re.sub(
        rf"^id:[ \t]*\"?{re.escape(old[:-3])}\"?[ \t]*$",
        lambda _: f"id: {layout._yaml(new[:-3])}",
        m[1],
        count=1,
        flags=re.M,
    )
    return text[: m.start(1)] + head + text[m.end(1) :]


def plan(root, old: layout.Layout, new: layout.Layout, sc: Scan | None = None) -> Plan:
    """A dry run of moving Kurooto's own notes from `old`'s places to `new`'s. Nothing is written."""
    root = Path(os.path.expanduser(str(root)))
    p = Plan(
        root=root,
        git=(root / ".git").exists(),
        before={"notes.layout": old.preset, "notes.paths": old.custom(), "notes.links": old.note_style},
        after=new_after(new),
    )
    if not root.is_dir():
        return p
    notes, _dirs, _cut = walk(root) if sc is None else (sc.notes, sc.dirs, sc.cut)
    fronts = sc.fronts if sc is not None else {}
    match = _matchers(old)
    daily_old, daily_new = old.shape("daily"), new.shape("daily")
    p.daily_from = daily_old if daily_old != daily_new else ""
    for rel in notes:
        front = fronts.get(rel)
        if front is None:
            front = front_of(_read(root / rel, HEAD) or "")
        k = kind_of(old, rel, match)
        if k is None:
            continue
        kind, fields, rest = k
        if not ours(front, old):
            p.daily_left += kind == "daily" and bool(p.daily_from)
            continue
        if "subject" in layout.KINDS[kind][1] and "subject" not in fields:
            subj = _subject_from(front)
            if subj:
                fields["subject"] = subj
        try:
            dst = new.rel(kind, **fields)
        except ValueError as e:
            need = str(e).rsplit(" ", 1)[-1]
            p.left.append({"path": rel, "why": f"its new place needs a {need}, and the note doesn't say"})
            continue
        if rest:
            dst = f"{dst}/{rest}"
        if os.path.isabs(dst):
            p.left.append({"path": rel, "why": "its new place is outside the notes folder"})
            continue
        if dst != rel:
            p.moves.append({"from": rel, "to": dst, "kind": kind})
    # clashes: the new place is taken, or two notes would land on one place
    seen: dict[str, str] = {}
    sources = {m["from"] for m in p.moves}
    for m in p.moves:
        low = m["to"].lower()
        if low in seen:
            p.clashes.append({**m, "why": f"{seen[low]} would move there too"})
        elif (root / m["to"]).exists() and not _same(root / m["from"], root / m["to"]):
            why = "a note is already there" if m["to"] not in sources else "a note that moves too is there now"
            p.clashes.append({**m, "why": why})
        seen.setdefault(low, m["from"])
    if not p.moves:
        return p
    # links: fixed in Kurooto's text, counted in yours
    moved = {m["from"]: m["to"] for m in p.moves}
    hubs = {old.rel("home"), old.rel("research")}
    for rel in notes:
        text = _read(root / rel)
        if text is None:
            continue
        new_rel = moved.get(rel, rel)
        mine = ours(front_of(text), old)
        after, fixed, theirs = fix_links(text, rel, new_rel, moved, mine, hub=rel in hubs)
        if rel in moved and mine:
            after = _new_id(after, rel, new_rel)
        if after != text:
            p.edits.append(Edit(new_rel, text, after, fixed))
        if theirs:
            p.theirs.append({"file": rel, "links": theirs})
    return p


# ------------------------------------------------------------------------------------------- apply and undo
class Refused(Exception):
    pass


def _same(a: Path, b: Path) -> bool:
    """One file under two spellings (a disk that ignores case), not two files."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _write(p: Path, text: str) -> None:
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _logs(state_dir: Path) -> Path:
    return Path(state_dir) / "notes-moves"


def apply_plan(p: Plan, state_dir: Path, digest: str) -> dict:
    """Move the notes and fix the links as the plan says, if it's the plan you were shown (same digest). The move log
    goes in state_dir/notes-moves/; something that goes wrong halfway is put back."""
    if digest != p.digest:
        raise Refused("Your notes changed since the plan was shown: look at the new plan before moving.")
    if p.clashes:
        raise Refused(f"{len(p.clashes)} note(s) would land where a note already is; nothing was moved.")
    if not p.moves:
        return {"id": "", "moved": 0, "fixed": 0, "log": ""}
    root = p.root
    stamp = f"{time.strftime('%Y%m%d-%H%M%S')}-{p.digest[:6]}"
    log: dict[str, Any] = {
        "id": stamp,
        "at": now().isoformat(timespec="seconds"),
        "root": str(root),
        "before": p.before,
        "after": p.after,
        "moves": [],
        "edits": [],
        "made": [],
        "removed": [],
        "undone": "",
    }
    file = _logs(state_dir) / f"{stamp}.json"
    try:
        for m in p.moves:
            src, dst = root / m["from"], root / m["to"]
            if not src.is_file():
                raise Refused(f"{m['from']} isn't there any more")
            case_only = dst.exists() and _same(src, dst)  # only the case changes, on a disk that ignores it
            if dst.exists() and not case_only:
                raise Refused(f"{m['to']} is taken")
            missing = [d for d in reversed(dst.parents) if not d.exists() and d != root and root in d.parents]
            dst.parent.mkdir(parents=True, exist_ok=True)
            log["made"] += [d.relative_to(root).as_posix() for d in missing]
            if case_only:  # Daily Notes/x.md -> daily notes/x.md on a disk that ignores case: through another name
                tmp = src.with_name(src.name + ".kurooto-move")
                os.rename(src, tmp)
                os.rename(tmp, dst)
            else:
                os.rename(src, dst)
            log["moves"].append([m["from"], m["to"]])
        for e in p.edits:
            f = root / e.file
            if _read(f) != e.before:
                raise Refused(f"{e.file} changed while moving")
            _write(f, e.after)
            log["edits"].append({"file": e.file, "before": e.before, "after_sha": _sha(e.after)})
        for frm, _ in log["moves"]:  # folders the moves left empty
            d = (root / frm).parent
            while d != root and root in d.parents and d.is_dir() and not any(d.iterdir()):
                d.rmdir()
                log["removed"].append(d.relative_to(root).as_posix())
                d = d.parent
    except Exception:
        _put_back(root, log)
        log["undone"] = "failed while moving; put back"
        jsave(file, log)
        raise
    jsave(file, log)
    return {"id": stamp, "moved": len(log["moves"]), "fixed": sum(e.fixed for e in p.edits), "log": str(file)}


def _put_back(root: Path, log: dict) -> list[str]:
    problems = []
    for e in reversed(log["edits"]):
        f = root / e["file"]
        cur = _read(f)
        if cur is not None and _sha(cur) == e["after_sha"]:
            _write(f, e["before"])
        else:
            problems.append(f"{e['file']} was changed since, so its links stay as they are")
    for d in log.get("removed", []):
        (root / d).mkdir(parents=True, exist_ok=True)
    for frm, to in reversed(log["moves"]):
        src, dst = root / to, root / frm
        case_only = dst.exists() and _same(src, dst)
        if src.is_file() and (not dst.exists() or case_only):
            dst.parent.mkdir(parents=True, exist_ok=True)
            if case_only:
                tmp = src.with_name(src.name + ".kurooto-move")
                os.rename(src, tmp)
                os.rename(tmp, dst)
            else:
                os.rename(src, dst)
        else:
            problems.append(f"{to} couldn't go back to {frm}")
    for d in reversed(log.get("made", [])):
        p = root / d
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    return problems


def last(state_dir: Path) -> dict | None:
    """The newest move that hasn't been undone, for an Undo button."""
    d = _logs(state_dir)
    for f in sorted(d.glob("*.json"), reverse=True) if d.is_dir() else []:
        log = jload(f, {}) or {}
        if log.get("moves") is not None and not log.get("undone"):
            return {"id": log.get("id"), "at": log.get("at"), "moved": len(log.get("moves") or [])}
    return None


def undo(state_dir: Path, log_id: str = "") -> dict:
    """Put a move back (the newest, or `log_id`): the notes, the links fixed, the folders. Returns what it did and
    the settings to restore ("before")."""
    d = _logs(state_dir)
    files = sorted(d.glob("*.json"), reverse=True) if d.is_dir() else []
    for f in files:
        log = jload(f, {}) or {}
        if log.get("undone") or (log_id and log.get("id") != log_id):
            continue
        problems = _put_back(Path(log["root"]), log)
        log["undone"] = now().isoformat(timespec="seconds")
        jsave(f, log)
        return {"ok": not problems, "id": log["id"], "moved_back": len(log["moves"]), "problems": problems,
                "before": log.get("before") or {}}  # fmt: skip
    raise Refused("Nothing to undo.")


# -------------------------------------------------------------------------------------- for the app and the page
def _folder(app: App, folder: str | None) -> Path:
    if not folder:
        return app.workspace
    return Path(os.path.expanduser(str(folder).strip().strip('"')))


def lines_in(b: dict) -> tuple[str, dict[str, str]]:
    """The layout and lines a page sent, checked: known kinds only, short templates, no '..'."""
    preset = str(b.get("layout") or "").strip().lower()
    if preset not in layout.PRESETS:
        raise ValueError("layout: kurooto or zettelkasten")
    raw = b.get("lines") or {}
    if not isinstance(raw, dict):
        raise ValueError("lines: {kind: place}")
    out = {}
    for k, v in raw.items():
        if k not in dict(LINES) or not isinstance(v, str) or len(v) > 200:
            raise ValueError(f"not a line: {k}")
        if ".." in v.replace("\\", "/").split("/"):
            raise ValueError(f"{k}: a place inside the notes folder, without ..")
        out[k] = v
    return preset, out


def view(app: App, folder: str | None = None) -> dict:
    """GET notes/fit: what the folder shows and the proposal, the layout in use, and the last move to undo."""
    root = _folder(app, folder)
    cur = layout.of(app)
    out = propose(root, cur, *scanned(root))
    out["workspace"] = str(app.workspace)
    out["other_folder"] = os.path.abspath(root) != os.path.abspath(app.workspace)
    out["in_use"] = {
        "layout": cur.preset,
        "paths": cur.custom(),
        "links": cur.note_style,
        "lines": {k: cur.template(k) for k, _ in LINES},
    }
    out["presets"] = {p: {k: layout.PRESETS[p][k] for k, _ in LINES} for p in layout.PRESETS}
    out["undo"] = last(app.paths.state)
    return out


def _new(app: App, b: dict) -> tuple[Path, layout.Layout, layout.Layout, bool]:
    preset, lines = lines_in(b)
    root = _folder(app, b.get("folder"))
    cur = layout.of(app)
    paths = merged_paths(preset, lines, cur.custom())
    links = str(b.get("links") or "").strip().lower()
    if links and links not in layout.NOTE_STYLES:
        raise ValueError("links: wiki or markdown")
    new = layout_for(root, preset, paths, cur, links or None)
    other = os.path.abspath(root) != os.path.abspath(app.workspace)
    return root, cur, new, other


def check(app: App, b: dict) -> dict:
    """POST notes/fit/preview: the preview, problems with the places, and the move plan (a dry run)."""
    root, cur, new, other = _new(app, b)
    if not root.is_dir():
        return {"ok": False, "error": f"{root} isn't a folder"}
    old = layout_for(root, cur.preset, cur.custom(), cur)
    p = plan(root, old, new) if not other else Plan(root=root, before={}, after={})
    p.after = new_after(new)
    return {
        "ok": True,
        "problems": new.check(),
        "preview": preview(new.preset, new.custom(), root),
        "plan": p.view(),
        "other_folder": other,
        "layout": new.preset,
        "paths": new.custom(),
        "links": new.note_style,
    }


def apply(app: App, b: dict) -> dict:
    """POST notes/fit/apply: the settings, and the moves if Kurooto's notes are in the way (only with the digest of
    the plan that was shown)."""
    root, cur, new, other = _new(app, b)
    if not root.is_dir():
        raise Refused(f"{root} isn't a folder")
    if problems := new.check():
        raise Refused("; ".join(problems))
    s = app.settings
    result: dict[str, Any] = {"moved": 0, "fixed": 0, "id": ""}
    if other:  # another notes folder: Kurooto writes there from now on; nothing moves between folders
        if str(b.get("digest") or "") != Plan(root=root, before={}, after={**new_after(new)}).digest:
            raise Refused("Look at the plan first.")
        s.set("you.workspace", str(root))
        app.events.emit("setting_changed", key="you.workspace")
    else:
        old = layout_for(root, cur.preset, cur.custom(), cur)
        p = plan(root, old, new)
        result = apply_plan(p, app.paths.state, str(b.get("digest") or ""))
    s.set("notes.layout", new.preset)
    s.set("notes.paths", new.custom())
    s.set("notes.links", new.note_style)
    app.events.emit("setting_changed", key="notes.layout")
    if result["moved"]:
        app.events.emit("notes_moved", moved=result["moved"], id=result["id"])
    return {
        "ok": True,
        **result,
        "layout": new.preset,
        "paths": new.custom(),
        "links": new.note_style,
        "workspace": str(app.workspace),
    }


def new_after(new: layout.Layout) -> dict:
    return {"notes.layout": new.preset, "notes.paths": new.custom(), "notes.links": new.note_style}


def undo_app(app: App, log_id: str = "") -> dict:
    """POST notes/fit/undo: the notes back, and the layout settings as they were before the move."""
    r = undo(app.paths.state, log_id)
    before = r.pop("before")
    for k in ("notes.layout", "notes.paths", "notes.links"):
        if k in before:
            app.settings.set(k, before[k])
    app.events.emit("setting_changed", key="notes.layout")
    return r
