"""The notes sorter's logic (0.7.4): notes that land in a scratch folder (inbox/ by default) are moved into the
folders of
your notes where they belong, by themselves, within limits. Never deletes anything, never overwrites, every pass can be
undone, and it notices when a note belongs somewhere else.

    ready(app)               the notes in the scratch folder that are due (not touched in the last few minutes, not
    marked
                             `sort: no`)
    decide(app, rel, text)   where one note belongs by rules, no AI: a learned rule (from your own moves), the note's
    own
                             `subject:` / `course:`, a tag or its title naming a subject; a folder that exists, or None
    plan(app, moves)         a dry run (core/notesfit.py's planner): clashes, the links fixed in Kurooto's own text, and
                             the notes your own links point at (those wait: a path link of yours would break)
    apply(app, plan, by)     the moves, one log with Undo (core/notesfit.py), and what's kept to learn from
    learn(app)               the notes it moved that you moved again: a rule, and the note is never moved back
    recheck(app)             the notes it moved, weekly: one that clearly fits another folder now moves once more (at
    most
                             once a month each)

Where a note may go: only a folder that already exists in your notes (a subject's folder, zettel/, sources/<course>/),
never a new top-level folder, never Kurooto's own folders (journal, about-me, prompts, skills, the scratch folder). A
note it can't place with confidence stays and is listed with its best guesses. The state is `<state>/sorter/state.json`.

The sorter's AI request (core/sorting.py:prompt / answer) is made by modules/sorter.py for the notes the rules couldn't
place; nothing here talks to an AI.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import layout, notesfit
from kurooto.core.clock import now
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

SKIP_DIRS = notesfit.SKIP | {"about-me", "kurooto", "prompts", "skills", "journal", "dailies", "Daily Notes"}
MIN_CONF = 0.75  # below this a guess isn't acted on
MONTH_S = 30 * 86400
WEEK_S = 7 * 86400
KEEP_DAYS = 60  # what's remembered of a moved note (to notice your own move of it)
STOP = frozenset(
    (
        "the and for with from that this are was were have has not but you your our about into over then than what "
        "when how why who its their them they his her him she can will would could should one two note notes new"
    ).split()
)


@dataclass
class Decision:
    folder: str | None  # relative to the notes folder, no slash at the end; None: can't place it
    conf: float = 0.0
    why: str = ""
    by: str = "rules"  # rules | learned | ai
    guesses: list[str] = field(default_factory=list)


# ------------------------------------------------------------------------------------------------------------ state
def state_file(app: App) -> Path:
    return app.paths.state / "sorter" / "state.json"


def load(app: App) -> dict:
    st = jload(state_file(app), {}) or {}
    for k, v in (("moved", {}), ("rules", []), ("pinned", {}), ("waiting", {}), ("passes", []), ("day", {})):
        st.setdefault(k, v)
    return st


def save(app: App, st: dict) -> None:
    t = time.time()
    st["moved"] = {k: v for k, v in st["moved"].items() if t - float(v.get("at", 0)) < KEEP_DAYS * 86400}
    st["passes"] = st["passes"][-60:]
    st["rules"] = st["rules"][-200:]
    jsave(state_file(app), st)


def setting(app: App, key: str, default=None):
    v = app.settings.get(f"sorter.{key}")
    return default if v is None else v


def scratch_rel(app: App) -> str:
    """The scratch folder, relative to the notes, checked: inside the notes, no '..', not a hidden or private folder."""
    given = str(setting(app, "folder", "inbox") or "inbox").strip()
    raw = given.strip("/\\").replace("\\", "/")
    parts = [p for p in raw.split("/") if p]
    if (
        not parts
        or ".." in parts
        or any(p.startswith(".") for p in parts)
        or given.startswith(("/", "\\"))
        or ":" in given
    ):
        return "inbox"
    return "/".join(parts)


def scratch_dir(app: App) -> Path:
    return Path(app.workspace) / scratch_rel(app)


# ------------------------------------------------------------------------------------------------------------ reading
def read_front(text: str) -> dict:
    """The simple `key: value` and list lines of a note's header, lower-cased keys (no YAML library needed)."""
    block = notesfit.front_of(text)
    out: dict = {}
    key = None
    for ln in block.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", ln)
        if m:
            key, val = m.group(1).lower(), m.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                out[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
            elif val:
                out[key] = val.strip("'\"")
            else:
                out[key] = []
        elif key and re.match(r"^\s+-\s+", ln) and isinstance(out.get(key), list):
            out[key].append(re.sub(r"^\s+-\s+", "", ln).strip().strip("'\""))
    return out


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9-]{2,}", (text or "").lower()) if w not in STOP}


def title_of(rel: str, text: str, front: dict) -> str:
    t = front.get("title")
    if isinstance(t, str) and t:
        return t
    m = re.search(r"(?m)^#\s+(.+)$", text)
    return m.group(1).strip() if m else Path(rel).stem.replace("-", " ")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def private_dirs(app: App) -> set[str]:
    """Folders a note is never sorted into (Kurooto's own places and the scratch folder)."""
    lay = layout.of(app)
    out = {scratch_rel(app)}
    for k in ("skills", "prompts", "inbox"):
        try:
            out.add(lay.rel(k))
        except Exception:
            pass
    return {o.strip("/") for o in out}


def folders(app: App) -> list[str]:
    """Where a note may go: folders that already exist in the notes, two levels down at most."""
    root = Path(app.workspace)
    private = private_dirs(app)
    out: list[str] = []
    try:
        top = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return out
    for d in top:
        if d.name in SKIP_DIRS or d.name.startswith("."):
            continue
        rel = d.name
        if rel not in private:
            out.append(rel)
        try:
            for sub in sorted(p for p in d.iterdir() if p.is_dir() and not p.name.startswith(".")):
                r2 = f"{rel}/{sub.name}"
                if sub.name not in SKIP_DIRS and r2 not in private:
                    out.append(r2)
        except OSError:
            pass
    return out


def ready(app: App) -> list[str]:
    """The notes in the scratch folder due for sorting: Markdown, not hidden, not touched in the last settle_min
    minutes,
    not marked `sort: no`. Oldest first."""
    root, d = Path(app.workspace), scratch_dir(app)
    if not d.is_dir():
        return []
    settle = float(setting(app, "settle_min", 10) or 0) * 60
    t = time.time()
    out = []
    for f in sorted(d.rglob("*.md")):
        rel = f.relative_to(root).as_posix()
        if any(part.startswith(".") for part in f.relative_to(root).parts) or not f.is_file():
            continue
        try:
            st = f.stat()
        except OSError:
            continue
        if t - st.st_mtime < settle:
            continue
        text = notesfit._read(f, notesfit.HEAD) or ""
        if str(read_front(text).get("sort", "")).lower() in ("no", "false", "keep"):
            continue
        out.append((st.st_mtime, rel))
    return [r for _, r in sorted(out)]


# ------------------------------------------------------------------------------------------------------------ rules
def decide(app: App, rel: str, text: str) -> Decision:
    """Where this note belongs, by rules (no AI). Folder None when none fits."""
    have = set(folders(app))
    front = read_front(text)
    st = load(app)
    toks = tokens(f"{title_of(rel, text, front)} {' '.join(map(str, front.get('tags') or []))} {text[:400]}")
    # 1. what you taught it by moving a note of the same kind
    best, hit = 0.0, None
    for r in st["rules"]:
        keys = set(r.get("keys") or [])
        if keys and r.get("folder") in have:
            score = len(keys & toks) / max(1, len(keys | toks))
            if score > best:
                best, hit = score, r
    if hit is not None and best >= 0.34:
        return Decision(hit["folder"], min(0.95, 0.6 + best), "like a note you moved there yourself", "learned")
    # 2. the note says its subject
    subj = app.modules.get("subjects")
    guesses: list[str] = []

    def folder_of(name: str) -> str | None:
        if subj is None or not name:
            return None
        try:
            slug = subj.resolve(name)
        except ValueError:
            slug = None
        if not slug:
            return None
        for cand in (layout.of(app).rel("subject", subject=slug), slug, f"sources/{slug}"):
            if cand in have:
                return cand
        return None

    for key in ("subject", "course", "class"):
        v = front.get(key)
        v = v[0] if isinstance(v, list) and v else v
        f = folder_of(str(v or ""))
        if f:
            return Decision(f, 0.95, f"its {key}: {v}")
    for tag in front.get("tags") or []:
        f = folder_of(str(tag).lstrip("#"))
        if f:
            return Decision(f, 0.85, f"its tag #{tag}")
    title = title_of(rel, text, front).lower()
    named: dict[str, str] = {}  # the subjects its title names, by folder
    for s in subj.subjects() if subj is not None and app.is_on("subjects") else []:
        for name in [s["name"], s["slug"], *s.get("aliases", [])]:
            n = str(name).lower().strip()
            if len(n) >= 4 and n in title:
                f = folder_of(s["slug"])
                if f:
                    named[f] = s["name"]
                else:
                    guesses.append(s["slug"])
                break
    if len(named) == 1:
        ((f, who),) = named.items()
        return Decision(f, 0.8, f"its title names {who}")
    guesses = [*named, *guesses]  # two subjects named: not sure which, so it waits with both as guesses
    # nothing sure: the folders whose names share words with the note, as guesses
    for f in sorted(have, key=lambda x: -len(tokens(x.replace("/", " ")) & toks))[:2]:
        if tokens(f.replace("/", " ")) & toks:
            guesses.append(f)
    return Decision(None, 0.0, "no rule fits", "rules", guesses[:2])


def prompt(app: App, rel: str, text: str) -> str:
    """The one short question for the AI: which of these folders, as JSON."""
    opts = folders(app)
    return (
        "Sort one note into a folder of the user's notes. Reply with ONLY a JSON object "
        '{"folder": "<one of the folders below, exactly, or null>", "confidence": <0 to 1>, "why": "<five words>"}. '
        "Use null when none clearly fits; never invent a folder.\n\nFolders:\n"
        + "\n".join(f"- {o}" for o in opts[:80])
        + f"\n\nThe note ({rel}):\n{text[:1500]}"
    )


def answer(app: App, raw: str) -> Decision:
    """The AI's reply, checked: a folder that exists, a confidence, nothing else is trusted."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return Decision(None, 0.0, "no answer", "ai")
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return Decision(None, 0.0, "unreadable answer", "ai")
    f = d.get("folder")
    try:
        conf = max(0.0, min(1.0, float(d.get("confidence") or 0)))
    except (TypeError, ValueError):
        conf = 0.0
    if not isinstance(f, str) or f.strip("/") not in set(folders(app)):
        return Decision(None, conf, "the AI named no folder you have", "ai")
    return Decision(f.strip("/"), conf, str(d.get("why") or "the AI's choice")[:60], "ai")


# ------------------------------------------------------------------------------------------------------------ moving
def free_name(root: Path, folder: str, name: str, taken: set[str]) -> str:
    """folder/name, or folder/name-2, -3 ... when that's taken (by a file or by another move in this pass). Nothing is
    ever overwritten."""
    stem, ext = os.path.splitext(name)
    n, rel = 1, f"{folder}/{name}"
    while (root / rel).exists() or rel.lower() in taken:
        n += 1
        rel = f"{folder}/{stem}-{n}{ext}"
    return rel


def plan(app: App, moves: list[dict]) -> tuple[notesfit.Plan, list[dict]]:
    """(the plan for these moves ({"from", "to", "kind"}), those left out). Left out: a note your own notes link to by a
    path that would break (it waits; nothing of yours is rewritten)."""
    root = Path(app.workspace)
    lay = layout.of(app)
    sc = notesfit.scanned(root)[0] if root.is_dir() else None
    p = notesfit.plan_moves(root, moves, lay, sc)
    if not p.theirs:
        return p, []
    left, keep = [], []
    for m in moves:
        one = notesfit.plan_moves(root, [m], lay, sc)
        if one.theirs:
            left.append({**m, "why": "notes of yours link to it by its path; moving it would break those links"})
        else:
            keep.append(m)
    return (notesfit.plan_moves(root, keep, lay, sc) if keep else notesfit.Plan(root=root)), left


def apply(app: App, p: notesfit.Plan, by: str = "sorter") -> dict:
    """Move them. The scratch folder stays even when it's empty; one log with Undo; each moved note is remembered by
    what
    it said, to notice when you move it again."""
    if not p.moves:
        return {"id": "", "moved": 0, "fixed": 0}
    res = notesfit.apply_plan(p, app.paths.state, p.digest, keep=(scratch_rel(app),))
    root = Path(app.workspace)
    st = load(app)
    t = time.time()
    for m in p.moves:
        text = notesfit._read(root / m["to"]) or ""
        prev = st["moved"].pop(m["from"], {})  # a note moved again: one entry, with how many times
        st["moved"][m["to"]] = {
            "from": m["from"],
            "sha": sha(text),
            "at": t,
            "n": int(prev.get("n", 0)) + 1,
            "by": by,
            "keys": sorted(tokens(f"{title_of(m['to'], text, read_front(text))} {text[:400]}"))[:24],
        }
    day = now().date().isoformat()
    st["day"] = {day: int(st["day"].get(day, 0)) + len(p.moves)}
    st["passes"].append({"id": res["id"], "at": t, "moved": len(p.moves), "by": by})
    for m in p.moves:
        st["waiting"].pop(m["from"], None)
    save(app, st)
    app.events.emit("sorter_moved", moved=len(p.moves), fixed=res.get("fixed", 0), by=by)
    return res


def left_today(app: App) -> int:
    day = now().date().isoformat()
    return max(0, int(setting(app, "per_night", 20) or 20) - int(load(app)["day"].get(day, 0)))


def undo(app: App, log_id: str = "") -> dict:
    """Put a pass back (the newest, or log_id); what was moved is forgotten, so it isn't learned as a correction."""
    st = load(app)
    ids = [p["id"] for p in reversed(st["passes"]) if p.get("id") and not p.get("undone")]
    want = log_id or (ids[0] if ids else "")
    if not want:
        return {"ok": False, "message": "There's nothing of the sorter's to undo."}
    out = notesfit.undo(app.paths.state, want)
    st = load(app)
    for p in st["passes"]:
        if p.get("id") == want:
            p["undone"] = time.time()
    for k in [k for k, v in st["moved"].items() if v.get("from") and not (Path(app.workspace) / k).exists()]:
        st["moved"].pop(k, None)
    save(app, st)
    app.events.emit("sorter_undone", id=want)
    return {"ok": True, "message": "Put back.", **{k: v for k, v in out.items() if k in ("problems", "moved")}}


# ------------------------------------------------------------------------------------------------------------ learning
def learn(app: App) -> list[str]:
    """Notes it moved that you moved again: a rule from what each said (like it goes where you put it), and the note is
    left alone from now on. Returns the notes' new places. Looks for a note by its name and content, never by
    guessing."""
    root = Path(app.workspace)
    st = load(app)
    gone = [(to, v) for to, v in st["moved"].items() if not (root / to).exists() and not v.get("corrected")]
    if not gone:
        return []
    names: dict[str, list[str]] = {}
    for rel in notesfit.walk(root)[0]:
        names.setdefault(Path(rel).name.lower(), []).append(rel)
    found = []
    for to, v in gone:
        for cand in names.get(Path(to).name.lower(), []):
            text = notesfit._read(root / cand)
            if text is not None and sha(text) == v.get("sha") and cand != to:
                folder = str(Path(cand).parent.as_posix())
                if folder in (".", ""):
                    break
                st["rules"].append({"keys": v.get("keys") or [], "folder": folder, "at": time.time()})
                st["pinned"][v["sha"]] = folder
                v["corrected"] = cand
                found.append(cand)
                break
    if found:
        save(app, st)
        app.events.emit("sorter_learned", rules=len(found))
    return found


def recheck(app: App) -> list[dict]:
    """The notes it moved: any now clearly in the wrong folder? Returns moves ({"from", "to", "kind"}) for those: at
    least a
    week since it moved, a month since it last moved it, your own moves left alone, and only on a confident rule or
    learned match (the AI isn't asked again)."""
    root = Path(app.workspace)
    st = load(app)
    out, taken = [], set()
    t = time.time()
    for to, v in list(st["moved"].items()):
        wait = WEEK_S if int(v.get("n", 1)) <= 1 else MONTH_S  # a first look after a week, then at most monthly
        if v.get("corrected") or v.get("sha") in st["pinned"] or t - float(v.get("at", 0)) < wait:
            continue
        f = root / to
        text = notesfit._read(f)
        if text is None:
            continue
        d = decide(app, to, text)
        here = str(Path(to).parent.as_posix())
        if d.folder and d.conf >= 0.85 and d.folder != here:
            out.append({"from": to, "to": free_name(root, d.folder, Path(to).name, taken), "kind": "resorted"})
            taken.add(out[-1]["to"].lower())
    return out
