"""Notes layout: where Kurooto puts each kind of note in your notes folder, and where it keeps files (photos, PDFs,
revision packs, handwriting originals, Classroom files). Every feature asks here, so one setting moves them all.

    notes.layout   "kurooto" (the default: journal/, about-me/, a folder per subject, research/, kurooto/) or
                   "zettelkasten" (dailies/, master/, sources/<subject>/, maps/, zettel/, projects/, digests/)
    notes.paths    your own place for any kind of note, over the layout's: {"daily": "diary/{date}.md"}
    files.folder   a folder outside your notes for photos, PDFs and packs; empty = inside the notes, as before
    files.links    how notes link to files outside the notes: "" (the layout's way), "relative" or "file" (file://)

Features ask like this (`app` may also be a Layout, or a plain notes folder for the default layout):

    from kurooto.core import layout
    layout.path(app, "daily", date="2026-10-20")              # <notes>/journal/2026-10-20.md
    layout.rel(app, "course", subject="linear-algebra")       # "linear-algebra/course.md"
    layout.link(app, "project", project="thesis")             # "research/thesis/index", for a [[wikilink]]
    layout.file_dir(app, "subject", subject="linear-algebra") # where that subject's photos and PDFs go
    layout.file_link(app, pdf, note)                          # "[x.pdf](files/x.pdf)", from that note
    layout.frontmatter(app, "lecture", path, title="Eigenvalues", subject="linear-algebra")

A custom place is a path inside the notes folder with the kind's fields in braces ({date}, {subject}, {slug},
{project}, {time}); a template that doesn't work falls back to the layout's own place.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kurooto.core.clock import now
from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.core.config import Settings

register_defaults("notes", {"layout": "kurooto", "paths": {}})
register_defaults("files", {"folder": "", "links": ""})

DEFAULT = "kurooto"

# kind -> (what it is, its fields). Kinds without ".md" in their template are folders.
KINDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "daily": ("the daily note (journal, plans, check-ins, study hours)", ("date",)),
    "profile": ("your profile (who you are, for the AI)", ()),
    "how_to_help": ("how you like to be helped", ()),
    "not_interested": ("topics you don't care about", ()),
    "recurring": ("recurring quizzes and tests", ()),
    "ideas": ("ideas from the nightly look back", ()),
    "skills": ("your own skills (folder)", ()),
    "prompts": ("your prompt library (folder)", ()),
    "inbox": ("quick notes and captures (folder)", ()),
    "note": ("a loose note an agent writes", ("slug",)),
    "subject": ("a subject's folder", ("subject",)),
    "course": ("a subject's course page", ("subject",)),
    "class_log": ("a subject's class log (after-class notes)", ("subject",)),
    "lecture": ("a lecture note", ("subject", "date", "slug")),
    "concept": ("a concept note (one idea)", ("subject", "slug")),
    "exam_prep": ("a subject's exam prep", ("subject",)),
    "doubts": ("a subject's doubts, for its next class", ("subject",)),
    "home": ("the home note, linking your hubs and courses", ()),
    "research": ("the research hub, listing your projects", ()),
    "project": ("a research project's note", ("project",)),
    "runs": ("a project's experiment runs (folder)", ("project",)),
    "handwritten": ("handwritten notes, written out (folder)", ()),
    "mail": ("a mail digest", ("date", "time")),
}

PRESETS: dict[str, dict[str, str]] = {
    "kurooto": {
        "daily": "journal/{date}.md",
        "profile": "about-me/profile.md",
        "how_to_help": "about-me/how-to-help-me.md",
        "not_interested": "about-me/not-interested.md",
        "recurring": "kurooto/recurring.md",
        "ideas": "kurooto/ideas.md",
        "skills": "kurooto/skills",
        "prompts": "prompts",
        "inbox": "inbox",
        "note": "inbox/{slug}.md",
        "subject": "{subject}",
        "course": "{subject}/course.md",
        "class_log": "{subject}/class-log.md",
        "lecture": "{subject}/{date}-{slug}.md",
        "concept": "{subject}/{slug}.md",
        "exam_prep": "{subject}/exam-prep.md",
        "doubts": "{subject}/doubts.md",
        "home": "index.md",
        "research": "research/index.md",
        "project": "research/{project}/index.md",
        "runs": "research/{project}/runs",
        "handwritten": "handwritten",
        "mail": "mail/{date}-{time}.md",
    },
    "zettelkasten": {
        "daily": "dailies/{date}.md",
        "profile": "master/profile.md",
        "how_to_help": "master/how-to-help-me.md",
        "not_interested": "master/not-interested.md",
        "recurring": "master/recurring-assessments.md",
        "ideas": "master/ideas.md",
        "skills": "master/skills",
        "prompts": "prompts",
        "inbox": "inbox",
        "note": "inbox/{slug}.md",
        "subject": "sources/{subject}",
        "course": "maps/courses/{subject}.md",
        "class_log": "sources/{subject}/class-log.md",
        "lecture": "sources/{subject}/{date}-{slug}.md",
        "concept": "zettel/{slug}.md",
        "exam_prep": "sources/{subject}/exam-prep.md",
        "doubts": "sources/{subject}/doubts.md",
        "home": "maps/index.md",
        "research": "maps/research.md",
        "project": "projects/{project}/index.md",
        "runs": "projects/{project}/runs",
        "handwritten": "handwritten",
        "mail": "digests/mail-{date}-{time}.md",
    },
}

# Files (binaries): kind -> folder. With files.folder set they go under it (FILES_OUTSIDE); otherwise inside the notes
# folder where each layout keeps them (FILES_INSIDE). Classroom's downloads stay in Kurooto's data folder then.
FILE_KINDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "inbox": ("photos, PDFs and documents you send (Telegram, the phone app)", ()),
    "subject": ("a subject's photos and files (after-class notes)", ("subject",)),
    "pack": ("revision packs (LaTeX and PDF); subject 'revision-packs' when there's none", ("subject",)),
    "latex": ("other LaTeX documents skills make", ()),
    "handwritten": ("originals of handwritten pages", ()),
    "handwritten_inbox": ("where new handwritten scans are dropped", ()),
    "classroom": ("Classroom's downloaded course files", ("subject",)),
    "project": ("a research project's files", ("project",)),
}
FILES_OUTSIDE = {
    "inbox": "inbox",
    "subject": "{subject}",
    "pack": "{subject}",
    "latex": "inbox",
    "handwritten": "handwritten",
    "handwritten_inbox": "handwritten-inbox",
    "classroom": "{subject}",
    "project": "{project}",
}
FILES_INSIDE = {
    "kurooto": {
        "inbox": "inbox",
        "subject": "{subject}/files",
        "pack": "{subject}",
        "latex": "inbox",
        "handwritten": "",  # next to the written-out note
        "handwritten_inbox": "handwritten-inbox",
        "project": "research/{project}/files",
    },
    "zettelkasten": {
        "inbox": "attachments/inbox",
        "subject": "attachments/{subject}",
        "pack": "attachments/{subject}",
        "latex": "attachments/inbox",
        "handwritten": "attachments/handwritten",
        "handwritten_inbox": "attachments/handwritten-inbox",
        "project": "attachments/{project}",
    },
}
LINKS = {"kurooto": "relative", "zettelkasten": "file"}  # how notes link to files outside the notes folder

# Agent-written note headers, per layout. "kurooto": made_by and date. "zettelkasten": id (the note's path without
# .md), aliases, tags, trust_tier: agent_written (the daily note is yours, so it gets no trust_tier).
KUROOTO_TAGS = {"exam_prep": ["exam-prep"]}
ZETTEL_TAGS = {
    "daily": ["daily-notes"],
    "lecture": ["source", "{subject}", "lecture"],
    "concept": ["zettel", "agent-written", "{subject}"],
    "exam_prep": ["exam-prep", "{subject}"],
    "doubts": ["source", "{subject}", "doubts"],
    "class_log": ["source", "{subject}", "class-log"],
    "course": ["map", "course", "{subject}"],
    "home": ["map", "home"],
    "research": ["map", "research"],
    "project": ["project"],
    "note": ["fleeting"],
    "mail": ["digest", "mail"],
    "handwritten": ["handwritten"],
    "how_to_help": ["master", "assistant"],
    "not_interested": ["master", "assistant"],
    "recurring": ["master", "assistant"],
    "ideas": ["master", "assistant"],
    "profile": ["master", "about-me"],
}

SHOWN = {"date": "<YYYY-MM-DD>", "time": "<HHMM>", "subject": "<subject>", "slug": "<slug>", "project": "<project>"}
IMAGES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".svg")


def _clean(v: Any) -> str:
    """A field value that can't climb out of its folder: no slashes, no leading dots."""
    s = re.sub(r"[\\/]+", "-", str(v).strip()).lstrip(".").strip()
    return s or "untitled"


def _yaml(s: str) -> str:
    return json.dumps(s, ensure_ascii=False) if re.search(r"[:#\[\]{},&*!|>%@`\"']|^\s|\s$", s) or not s else s


class Layout:
    """Where notes and files go for one notes folder. `settings` None: the default layout, files inside the notes."""

    def __init__(self, root, settings: Settings | None = None, assistant: str = "Kurooto", data: Path | None = None):
        self.root = Path(root)
        self.settings = settings
        self.assistant = assistant or "Kurooto"
        self.data = Path(data) if data else None  # Kurooto's data folder (Classroom files live there by default)

    # ------------------------------------------------------------------------------------------ settings
    def _get(self, key: str, default=None):
        return self.settings.get(key, default) if self.settings is not None else default

    @property
    def preset(self) -> str:
        p = str(self._get("notes.layout") or DEFAULT).strip().lower()
        return p if p in PRESETS else DEFAULT

    def custom(self) -> dict[str, str]:
        raw = self._get("notes.paths") or {}
        return (
            {k: str(v).strip() for k, v in raw.items() if k in KINDS and str(v or "").strip()}
            if isinstance(raw, dict)
            else {}
        )

    def is_default(self) -> bool:
        """The kurooto layout, no custom places, files inside the notes: everything where it always was."""
        return self.preset == DEFAULT and not self.custom() and self.files_root() is None

    def template(self, kind: str) -> str:
        if kind not in KINDS:
            raise KeyError(f"no such kind of note: {kind}")
        return self.custom().get(kind) or PRESETS[self.preset][kind]

    # ---------------------------------------------------------------------------------------- notes
    def _fields(self, kind: str, fields: dict) -> dict:
        t = now()
        out = {"date": t.date().isoformat(), "time": f"{t:%H%M}", "slug": "note"}
        out.update({k: v for k, v in fields.items() if v is not None and v != ""})
        for need in KINDS[kind][1]:
            if need not in out:
                raise ValueError(f"{kind} needs {need}")
        return {k: _clean(v) for k, v in out.items()}

    def _render(self, kind: str, tmpl: str, f: dict) -> str | None:
        try:
            s = tmpl.format_map(f)
        except (KeyError, ValueError, IndexError, AttributeError):
            return None
        if ".md" in PRESETS[DEFAULT][kind] and not s.endswith(".md"):
            s += ".md"
        return s

    def path(self, kind: str, **fields) -> Path:
        """Where this note (or folder) is: an absolute path, inside the notes folder unless you chose otherwise."""
        f = self._fields(kind, fields)
        tmpl = self.template(kind)
        s = self._render(kind, tmpl, f)
        if s is not None:
            p = Path(os.path.expanduser(s))
            if p.is_absolute():  # your own place outside the notes (only from notes.paths)
                return p
            if ".." not in Path(s).parts:
                return self.root / s
        return self.root / self._render(kind, PRESETS[self.preset][kind], f)

    def rel(self, kind: str, **fields) -> str:
        """The same place as a path inside the notes folder ("journal/2026-10-20.md"), or absolute if it's outside."""
        return self.shown(self.path(kind, **fields))

    def link(self, kind: str, **fields) -> str:
        """A [[wikilink]] target: the path inside the notes folder without .md."""
        r = self.rel(kind, **fields)
        return r[:-3] if r.endswith(".md") else r

    def shape(self, kind: str, **fields) -> str:
        """The place with placeholders for what isn't given ("dailies/<YYYY-MM-DD>"), without .md, for the AI."""
        f = {**SHOWN, **{k: v for k, v in fields.items()}}
        tmpl = self.template(kind)
        s = self._render(kind, tmpl, f) or self._render(kind, PRESETS[self.preset][kind], f) or ""
        return s[:-3] if s.endswith(".md") else s

    def kind_of_folder(self, folder: str) -> bool:
        """Is this top-level folder name one Kurooto uses for something other than a subject?"""
        tops = set()
        for kind in KINDS:
            if kind == "subject":
                continue
            first = self.shape(kind).split("/")[0]
            if first and not first.startswith("<"):
                tops.add(first)
        return folder in tops

    # ---------------------------------------------------------------------------------------- files
    def files_root(self) -> Path | None:
        """files.folder (absolute), or None when files stay inside the notes."""
        f = str(self._get("files.folder") or "").strip()
        if not f:
            return None
        p = Path(os.path.expanduser(f))
        return p if p.is_absolute() else Path.home() / p

    def file_dir(self, kind: str, **fields) -> Path:
        """The folder a kind of file goes in: under files.folder when it's set, else where the layout keeps it."""
        if kind not in FILE_KINDS:
            raise KeyError(f"no such kind of file: {kind}")
        f = {k: _clean(v) for k, v in fields.items() if v is not None and v != ""}
        for need in FILE_KINDS[kind][1]:
            if need not in f:
                raise ValueError(f"{kind} files need {need}")
        root = self.files_root()
        if root is not None:
            return root / FILES_OUTSIDE[kind].format_map(f)
        if kind == "classroom":
            return (self.data or self.root.parent) / "classroom" / f["subject"]
        inside = FILES_INSIDE[self.preset][kind].format_map(f)
        if kind == "handwritten" and not inside:
            return self.path("handwritten")
        return self.root / inside

    def file_path(self, kind: str, name: str, **fields) -> Path:
        return self.file_dir(kind, **fields) / _clean(name)

    def inside_notes(self, p) -> bool:
        try:
            Path(os.path.abspath(p)).relative_to(os.path.abspath(self.root))
            return True
        except ValueError:
            return False

    def shown(self, p) -> str:
        """How to name a path to you: inside the notes folder relative to it ("inbox/x.pdf"), else in full."""
        a = Path(os.path.abspath(p))
        try:
            return a.relative_to(os.path.abspath(self.root)).as_posix()
        except ValueError:
            return str(a)

    def link_style(self) -> str:
        s = str(self._get("files.links") or "").strip().lower()
        return s if s in ("relative", "file") else LINKS[self.preset]

    def file_target(self, file, note) -> str:
        """The link target for a file, from a note: relative inside the notes (and in the "relative" style), else a
        file:// link."""
        file, note = Path(os.path.abspath(file)), Path(os.path.abspath(note))
        if self.inside_notes(file) or self.link_style() == "relative":
            try:
                return os.path.relpath(file, note.parent).replace(os.sep, "/").replace(" ", "%20")
            except ValueError:  # another drive (Windows)
                pass
        return file.as_uri()

    def file_link(self, file, note, label: str | None = None) -> str:
        """A Markdown link to a file from a note; images are shown in place when the link is relative."""
        file = Path(file)
        target = self.file_target(file, note)
        text = (label or file.name).replace("[", "(").replace("]", ")")
        embed = file.suffix.lower() in IMAGES and not target.startswith("file:")
        return f"{'!' if embed else ''}[{text}]({target})"

    # ---------------------------------------------------------------------------------- note headers
    def frontmatter(
        self,
        kind: str | None = None,
        path=None,
        *,
        title: str = "",
        tags: list[str] | None = None,
        agent: bool = True,
        bare: bool = False,
        **extra,
    ) -> str:
        """The header a new note gets, in the layout's style, ending in a blank line ("" for none).

        kurooto: made_by and date (plus tags and extra); `bare=True` for notes that never had a header there.
        zettelkasten: id (the note's path without .md), aliases, tags, trust_tier: agent_written (unless
        agent=False, e.g. the daily note), plus extra."""
        fields = {k: str(v) for k, v in extra.items() if k in ("subject", "project")}
        rest = {k: v for k, v in extra.items() if k not in ("subject", "project") and v not in (None, "")}
        if self.preset == "zettelkasten":
            if tags is None:
                tags = [t.format_map({**SHOWN, **fields}) for t in ZETTEL_TAGS.get(kind or "", [])]
                tags = [t for t in tags if t and "<" not in t]
            nid = ""
            if path is not None:
                nid = self.shown(path)
                nid = nid[:-3] if nid.endswith(".md") else nid
                if not self.inside_notes(path):
                    nid = Path(path).stem
            lines = [
                f"id: {_yaml(nid)}" if nid else None,
                f"aliases: [{_yaml(title)}]" if title else "aliases: []",
                f"tags: [{', '.join(_yaml(t) for t in tags)}]",
                "trust_tier: agent_written" if agent else None,
            ]
        else:
            if bare:
                return ""
            lines = [f"made_by: {_yaml(self.assistant)}", f"date: {now():%Y-%m-%d}"]
            tags = KUROOTO_TAGS.get(kind or "", []) if tags is None else tags
            if tags:
                lines.append(f"tags: [{', '.join(_yaml(t) for t in tags)}]")
        lines += [f"{k}: {v if isinstance(v, (int, float)) else _yaml(str(v))}" for k, v in rest.items()]
        return "---\n" + "\n".join(x for x in lines if x) + "\n---\n\n"

    # ------------------------------------------------------------------------------------------ the AI
    def describe(self) -> str:
        """For the AI: where things go in this layout. "" for the default layout (the skills already say it)."""
        if self.is_default():
            return ""
        s = self.shape
        parts = [
            f"daily note {s('daily')}",
            f"a subject's course page {s('course')}, its lecture notes {s('lecture')}, exam prep {s('exam_prep')} "
            f"and class log {s('class_log')}",
            f"concept notes {s('concept')}",
            f"research projects {s('project')} (all listed in {s('research')})",
            f"loose notes and ideas {s('note')}",
            f"mail digests {s('mail')}",
            f"how they like to be helped {s('how_to_help')}, their profile {s('profile')}, not-interested topics "
            f"{s('not_interested')}, recurring quizzes {s('recurring')}",
        ]
        out = (
            "Their notes have their own layout (paths inside the notes folder, without .md; where a skill names "
            "other places, use these instead): " + "; ".join(parts) + "."
        )
        if self.preset == "zettelkasten":
            out += (
                " New notes you write start with a header of id (the note's path without .md), aliases, tags and "
                "trust_tier: agent_written; links are [[wikilinks]] to note paths without .md."
            )
        root = self.files_root()
        if root is not None:
            how = "file:// links" if self.link_style() == "file" else "relative links"
            out += (
                f" Files (PDFs, photos, scans, slides) are kept outside the notes in {root}, in a folder per subject "
                f"or project: link to them ({how}) and never copy them into the notes folder."
            )
        return out

    def translate(self, text: str) -> str:
        """A skill's instructions with the default layout's places swapped for this layout's ("journal/<date>" ->
        "dailies/<date>"). Unchanged for the default layout."""
        if self.preset == DEFAULT and not self.custom():
            return text
        s = self.shape

        def prefix(kind: str, field: str) -> str | None:
            shape, mark = s(kind), SHOWN[field]
            return shape.split(mark)[0] if mark in shape else None

        about = s("profile").rpartition("/")[0]
        rules: list[tuple[str, str | None]] = [
            (r"journal/(?=<|\d{4}-\d\d-\d\d|YYYY)", prefix("daily", "date")),
            *[
                rule
                for ph in ("<subject>", "<folder>")  # the subject's slug, as skills write it
                for rule in (
                    (ph + r"/course\b", s("course", subject=ph)),
                    (ph + r"/exam-prep\b", s("exam_prep", subject=ph)),
                    (ph + r"/class-log\b", s("class_log", subject=ph)),
                    (ph + r"/<concept-slug>", s("concept", subject=ph, slug="<concept-slug>")),
                    (ph + "/", s("subject", subject=ph) + "/"),
                )
            ],
            (r"about-me/how-to-help-me\b", s("how_to_help")),
            (r"about-me/profile\b", s("profile")),
            (r"about-me/not-interested\b", s("not_interested")),
            (r"about-me/", about + "/" if about else None),
            (r"kurooto/recurring\b", s("recurring")),
            (r"kurooto/ideas\b", s("ideas")),
            (r"kurooto/skills\b", s("skills")),
            (r"research/index\b", s("research")),
            (r"research/", prefix("project", "project")),
            (r"mail/(?=<|\d{4}-\d\d-\d\d)", prefix("mail", "date")),
            (r"inbox/", s("inbox") + "/"),
            (r"handwritten/", s("handwritten") + "/"),
        ]
        live = [(pat, rep) for pat, rep in rules if rep is not None]
        rx = re.compile("|".join(f"(?P<r{i}>(?<![\\w./-]){pat})" for i, (pat, _) in enumerate(live)))

        def swap(m: re.Match) -> str:
            return live[int(m.lastgroup[1:])][1]

        return rx.sub(swap, text)

    def check(self) -> list[str]:
        """Problems with the layout settings, in plain words (for the health check)."""
        out = []
        raw = str(self._get("notes.layout") or DEFAULT).strip().lower()
        if raw not in PRESETS:
            out.append(f'notes.layout "{raw}" isn\'t a layout; using "{DEFAULT}" (or "zettelkasten")')
        for kind, tmpl in self.custom().items():
            sample = {k: "x" for k in SHOWN}
            if self._render(kind, tmpl, sample) is None or ".." in Path(tmpl).parts:
                out.append(f"notes.paths.{kind} \"{tmpl}\" doesn't work; using the layout's own place")
        root = self.files_root()
        if root is not None:
            if self.inside_notes(root):
                out.append(f"files.folder {root} is inside the notes folder, so files still go into the notes")
            elif root.exists() and not root.is_dir():
                out.append(f"files.folder {root} isn't a folder")
        return out


def of(x, settings: Settings | None = None) -> Layout:
    """The layout for an App (its settings and notes folder), a Layout, or a plain notes folder (the default layout
    unless `settings` is given)."""
    if isinstance(x, Layout):
        return x
    if hasattr(x, "settings") and hasattr(x, "workspace"):
        p = getattr(x, "paths", None)
        return Layout(x.workspace, x.settings, getattr(x, "name", "Kurooto"), getattr(p, "data", None))
    return Layout(Path(x), settings)


def for_install() -> Layout:
    """The layout of this computer's Kurooto, without starting it (for terminal commands)."""
    from kurooto.app import default_workspace
    from kurooto.core.config import Settings
    from kurooto.core.paths import paths

    p = paths().ensure()
    s = Settings(p.config / "settings.json")
    ws = s.get("you.workspace")
    return Layout(Path(ws) if ws else default_workspace(), s, s.get("you.assistant_name") or "Kurooto", p.data)


# ---------------------------------------------------------------------------- the same, for an app in one call
def path(app, kind: str, **fields) -> Path:
    return of(app).path(kind, **fields)


def rel(app, kind: str, **fields) -> str:
    return of(app).rel(kind, **fields)


def link(app, kind: str, **fields) -> str:
    return of(app).link(kind, **fields)


def shown(app, p) -> str:
    return of(app).shown(p)


def file_dir(app, kind: str, **fields) -> Path:
    return of(app).file_dir(kind, **fields)


def file_path(app, kind: str, name: str, **fields) -> Path:
    return of(app).file_path(kind, name, **fields)


def file_link(app, file, note, label: str | None = None) -> str:
    return of(app).file_link(file, note, label)


def files_root(app) -> Path | None:
    return of(app).files_root()


def frontmatter(app, kind: str | None = None, path=None, **kw) -> str:
    return of(app).frontmatter(kind, path, **kw)


def describe(app) -> str:
    return of(app).describe()


def translate(app, text: str) -> str:
    return of(app).translate(text)
