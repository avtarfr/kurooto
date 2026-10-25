"""Copies among your notes (0.8.0): the garden's pass over all of them, and the questions both it and the notes sorter
ask.

The garden (core/graphmerge.py) already asks about concept notes that look like one concept (by name, alias or
meaning). This is the
text side, over *all* your notes, old ones too (every night it compares everything, a few pairs asked at a time): two
notes that say
the same thing (exact) or nearly the same (near, core/dupes.py). No AI.

    scan(app)              the copy pairs not asked about yet, exact first: [Pair]
    ask(app, pairs)        one question per pair: Keep both / Merge / Add nothing, with Undo after a merge
    merge(app, pid)        exact copy: the second note gets a redirect line at the top and keeps its text; near copy:
    the lines the
                           second has that the first doesn't go into the first under "Merged from [[...]]", and the
                           second gets the
                           redirect line. Nothing is deleted; each file's before-copy is kept for Undo.
    undo(app, pid)         both files back as they were (a file you changed since stays as it is, and it says so)
    incoming(app, rel, text)   for the sorter: the notes already in your folders that a note in the scratch folder
    copies

Nothing here moves, merges or deletes without your tap. State: `<state>/notedupes.json`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import dupes, notesfit
from kurooto.core.clock import now
from kurooto.core.state import jload, jsave
from kurooto.core.tools import write_note_file

if TYPE_CHECKING:
    from kurooto.app import App

FILE = "notedupes.json"
READ_MAX = 300_000  # characters read of one note
NOTES_MAX = 20_000
REASK_DAYS = 14
DONE = ("keep", "merge")
REDIRECT = "<!-- kurooto:merged-into [[{to}]] -->"
WHY = {"exact": "the same words", "near": "almost the same words ({pct}% alike)"}


def _load(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("pairs", {})
    d.setdefault("sorter", {})
    return d


def _save(app: App, d: dict) -> None:
    jsave(app.paths.state / FILE, d)


def pid_of(a: str, b: str) -> str:
    return "n" + hashlib.sha1("|".join(sorted((a, b))).encode(), usedforsecurity=False).hexdigest()[:8]  # noqa: S324


def skip_dirs(app: App) -> set[str]:
    from kurooto.core import sorting

    return (
        set(notesfit.SKIP)
        | {"about-me", "prompts", "skills", "journal", "dailies", "Daily Notes"}
        | {sorting.scratch_rel(app).split("/")[0]}
    )


def notes(app: App, limit: int = NOTES_MAX) -> dict[str, str]:
    """Every note of yours (relative path -> text), except Kurooto's own folders and the scratch folder."""
    root = Path(app.workspace)
    if not root.is_dir():
        return {}
    rels, _dirs, _cut = notesfit.walk(root, limit)
    skip = skip_dirs(app)
    out = {}
    for rel in rels:
        if rel.split("/")[0] in skip or not rel.lower().endswith(".md"):
            continue
        text = notesfit._read(root / rel, READ_MAX)  # noqa: SLF001
        if text is not None:
            out[rel] = text
    return out


def redirected(text: str) -> bool:
    return "kurooto:merged-into" in text


def scan(app: App, per_day: int | None = None, again: bool = False) -> list[dupes.Pair]:
    """The copy pairs that haven't been asked or answered (or were asked more than REASK_DAYS ago), exact first."""
    st = _load(app)
    today = now().date()
    skip = set()
    for rec in st["pairs"].values():
        key = "|".join(sorted((rec["a"], rec["b"])))
        if rec.get("state") in DONE or rec.get("state") == "skip":
            skip.add(key)
        elif not again and rec.get("asked"):
            try:
                if (today - dt.date.fromisoformat(rec["asked"])).days < REASK_DAYS:
                    skip.add(key)
            except ValueError:
                pass
    all_notes = {r: t for r, t in notes(app).items() if not redirected(t)}
    pairs = [p for p in dupes.scan(all_notes) if p.key not in skip]
    most = per_day if per_day is not None else int(app.settings.get("integrate.duplicates_per_day") or 3)
    return pairs[: max(1, most)]


def _first(a: str, b: str) -> tuple[str, str]:
    """Which note keeps (the older name by path order is arbitrary; prefer the shorter path, then the one that sorts
    first)."""
    return (a, b) if (len(a), a) <= (len(b), b) else (b, a)


def ask(app: App, pairs: list[dupes.Pair]) -> tuple[str, list]:
    """The question and its buttons; the pairs are recorded as asked."""
    st = _load(app)
    lines, buttons = ["Notes that look like copies of each other:"], []
    for i, p in enumerate(pairs, 1):
        keep, other = _first(p.a, p.b)
        pid = pid_of(p.a, p.b)
        st["pairs"][pid] = {
            "a": keep,
            "b": other,
            "kind": p.kind,
            "score": p.score,
            "asked": now().date().isoformat(),
            "state": "open",
        }
        why = WHY[p.kind].format(pct=round(p.score * 100))
        lines.append(f"{i}. {keep} and {other}: {why}.")
        buttons.append([(f"{i} Merge", f"ndup:{pid}:merge"), (f"{i} Keep both", f"ndup:{pid}:keep")])
    _save(app, st)
    lines.append(
        "Merge keeps the first and points the second at it; nothing is deleted, and Undo puts both back. "
        "Keep both: never asked again."
    )
    return "\n".join(lines), buttons


def _unique_lines(keep_text: str, other_text: str) -> list[str]:
    have = {" ".join(dupes.WORD.findall(x.lower())) for x in keep_text.splitlines()}
    out = []
    for ln in other_text.splitlines():
        key = " ".join(dupes.WORD.findall(ln.lower()))
        if key and key not in have and not ln.startswith(("---", "<!--")):
            out.append(ln)
            have.add(key)
    return out


def merge_texts(keep_rel: str, keep_text: str, other_rel: str, other_text: str, kind: str) -> tuple[str, str]:
    """(the kept note's new text, the other note's new text)."""
    stem = Path(other_rel).with_suffix("").as_posix()
    new_keep = keep_text
    if kind == "near":
        extra = _unique_lines(keep_text, other_text)
        if extra:
            new_keep = keep_text.rstrip("\n") + f"\n\n## Merged from [[{stem}]]\n\n" + "\n".join(extra) + "\n"
    redirect = REDIRECT.format(to=Path(keep_rel).with_suffix("").as_posix()) + "\n\n"
    return new_keep, redirect + other_text


def merge_pair(app: App, keep_rel: str, other_rel: str, kind: str) -> tuple[bool, dict | str]:
    """Merge `other_rel` into `keep_rel`. (True, {rel: [before, after]}) for Undo, or (False, why)."""
    root = Path(app.workspace)
    ka, kb = root / keep_rel, root / other_rel
    ta, tb = notesfit._read(ka), notesfit._read(kb)  # noqa: SLF001
    if ta is None or tb is None:
        return False, "one of those notes is gone"
    if redirected(ta) or redirected(tb):
        return False, "one of them is merged already"
    na, nb = merge_texts(keep_rel, ta, other_rel, tb, kind)
    write_note_file(ka, na)
    write_note_file(kb, nb)
    return True, {keep_rel: [ta, na], other_rel: [tb, nb]}


def restore(app: App, before: dict) -> list[str]:
    """Put the files back as they were; the ones you changed since stay as they are (their paths are returned)."""
    root, changed = Path(app.workspace), []
    for rel, (old, new) in before.items():
        if notesfit._read(root / rel) == new:  # noqa: SLF001
            write_note_file(root / rel, old)
        else:
            changed.append(rel)
    return changed


def merge(app: App, pid: str) -> str:
    st = _load(app)
    rec = st["pairs"].get(pid)
    if rec is None:
        return "That question is gone."
    ok, got = merge_pair(app, rec["a"], rec["b"], rec["kind"])
    if not ok:
        return f"Not merged: {got}."
    rec.update(state="merge", at=now().isoformat(timespec="seconds"), before=got)
    _save(app, st)
    app.events.emit("notedupes_merged", kind=rec["kind"])
    return f"Merged: {rec['b']} now points at {rec['a']} and keeps its own text."


def keep(app: App, pid: str) -> str:
    st = _load(app)
    rec = st["pairs"].get(pid)
    if rec is None:
        return "That question is gone."
    rec.update(state="keep", at=now().isoformat(timespec="seconds"))
    _save(app, st)
    return "Kept both; that pair won't be asked about again."


def undo(app: App, pid: str) -> str:
    st = _load(app)
    rec = st["pairs"].get(pid)
    if rec is None or rec.get("state") != "merge":
        return "There's nothing to undo there."
    changed = restore(app, rec.get("before") or {})
    if not changed:
        rec.update(state="keep", undone=True)  # an undone merge: not asked again
        rec.pop("before", None)
    _save(app, st)
    return (
        "Put back."
        if not changed
        else f"Put back, except {', '.join(changed)}: you changed it since, so it stays as it is."
    )


def button(app: App, pid: str, act: str) -> str:
    if act == "merge":
        said = merge(app, pid)
    elif act == "keep":
        said = keep(app, pid)
    elif act == "undo":
        return undo(app, pid)
    else:
        return "There's no such button."
    if said.startswith("Merged"):
        app.notify(said, kind="result", buttons=[[("Undo", f"ndup:{pid}:undo")]], why="asked")
    return said[:190]


def night(app: App, payload: dict | None = None) -> str:
    """The nightly question: up to `integrate.duplicates_per_day` pairs (none if none, or one went today)."""
    if not app.settings.get("integrate.duplicates_all"):
        return ""
    st = _load(app)
    if st.get("sent") == now().date().isoformat():
        return ""
    pairs = scan(app)
    if not pairs:
        return ""
    text, buttons = ask(app, pairs)
    st = _load(app)
    st["sent"] = now().date().isoformat()
    _save(app, st)
    app.notify(text, kind="question", buttons=buttons, why="integrate.duplicates", about=f"{len(pairs)} pairs")
    app.events.emit("notedupes_asked", pairs=len(pairs))
    return text


# ------------------------------------------------------------------------------------------------- the sorter
def incoming(app: App, rel: str, text: str) -> list[tuple[str, str, float]]:
    """The notes in your folders that this scratch note copies: [(their path, kind, score)], best first."""
    if dupes.words(text) < dupes.MIN_WORDS:
        return []
    ix = dupes.Index()
    for r, t in notes(app).items():
        if r != rel and not redirected(t):
            ix.add(r, t)
    return ix.near(text, exclude=rel)
