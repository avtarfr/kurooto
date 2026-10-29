"""Study notes from an upload, as one request (0.9.0, N13; switch study.notes_workflow, on). "Read my handwritten notes
for <course> from <topic> to the end, drop what I already have, make a study pack for those topics, write deep notes
and give me a PDF" broke at every joint: the reader only ran on its own timer, and the AI had no way to build a pack,
compile LaTeX or file what it made. These are the AI's tools for it, each logged like any tool use (core/jobs.py); the
skill study-notes-from-upload (data/skills/) tells the AI the steps:

    find_uploads        new scans and PDFs: the handwritten folders, the notes, the files folder, Downloads; by course
                        and how recent; says which were written out already and where the note is
    read_handwritten    starts the handwritten reader (modules/handwritten.py) on that one file now, with its own
                        settings (a model on this computer, else Gemini only when handwritten.cloud allows), and waits
                        (or comes back with how far it got: "page 7 of 13"); the transcription with its "## Page N"
                        lines, from a topic's heading on when asked (N12's find_topic when it's there)
    build_study_pack    the /studypack pack (core/studypack.py) for a subject and topics, unpacked in Kurooto's cache
                        so the AI can read it: the folder, its PROMPT.md (your own study_pack_prompt note when you
                        made one) and its INDEX.md
    save_course_file    a document the AI made (PDF, .tex) into the course's files folder (files.folder/<course>, or
                        the layout's place inside the notes, never the notes' top folder), and a short source note in
                        the course's notes folder (sources/<course>/ in the Zettelkasten layout) linking it; a copy in
                        a folder you name (Downloads/...) on request
    study_progress      one line to you while it works ("reading page 7 of 13", "compiling")
    compile_latex       only when N2's tool (core/tools.py, tools.latex) isn't in this build: the same compile with the
                        self-check (core/latexcheck.py)

Nothing here sends anything anywhere: the PDF goes to you by the existing send_file tool. Turning the switch off takes
the tools, the skill and the plain-words request away at once.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import layout, places
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.calls.tools import Tool, arg

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "study",
    {
        # (0.9.0) "study notes from my upload" as one request: the AI may find your scans, read one now, build a study
        # pack, compile LaTeX and file the PDF in the course's files folder (skill study-notes-from-upload)
        "notes_workflow": True,
    },
)

SKILL = "study-notes-from-upload"
UPLOAD_DAYS = 14  # find_uploads looks this far back unless told otherwise
MAX_UPLOADS = 15
SCAN_MAX = 4000  # files looked at per folder
PDFS = {".pdf"}
PICTURES = {".png", ".jpg", ".jpeg", ".webp", ".heic"}
WAIT_S = 300  # read_handwritten waits this long at most, then says how far it got
POLL_S = 1.0
PROGRESS_S = 120  # while waiting, a "page 7 of 13" line to you at most this often
CHUNK = 24_000  # characters of a transcription per answer; `start` gets the next part
FILE_EXT = {".pdf", ".tex", ".bib", ".md", ".txt", ".png", ".jpg", ".jpeg", ".svg", ".zip"}
# what a Gemini read of a whole PDF is asked for here: the reader's own prompt, and the page lines the cut needs
PAGED = " Before each page's text, write a line '## Page N' with its page number."
LATEX_RULE = (
    "To make a PDF from LaTeX, compile it yourself with the compile_latex tool; never answer that you can't compile. "
    "If it fails, read the errors (each has its line), fix the .tex and compile again, up to three tries; then tell "
    "them the error that's left, with its line."
)


def on(app: App) -> bool:
    return bool(app.settings.get("study.notes_workflow"))


def _subject(app: App, text: str) -> tuple[str, str]:
    """(slug, name) of a course you named ("AN2", "real analysis 2"), through Subjects when it's on."""
    from kurooto.core.studypack import slug

    text = str(text or "").strip()
    subj = app.modules.get("subjects") if app.is_on("subjects") else None
    sid = subj.resolve(text) if subj is not None and text else None
    if sid:
        return sid, subj.name_of(sid)
    return (slug(text), text) if text else ("", "")


def _course_words(app: App, course: str) -> list[str]:
    """What names a course in a file's path: its slug, its short names, its name's words."""
    sid, name = _subject(app, course)
    out = [sid, course]
    subj = app.modules.get("subjects") if app.is_on("subjects") else None
    if subj is not None and sid:
        out += next((list(s.get("aliases") or []) for s in subj.subjects() if s.get("slug") == sid), [])
    out.append(name)
    return [w.lower() for w in dict.fromkeys(x.strip() for x in out if x and x.strip())]


def _names_course(rel: str, words: list[str]) -> bool:
    flat = re.sub(r"[^a-z0-9]+", " ", rel.lower())
    for w in words:
        w = re.sub(r"[^a-z0-9]+", " ", w).strip()
        if w and re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", flat):
            return True
    return False


# ---------------------------------------------------------------------------------------------- find_uploads
def _hw(app: App):
    return app.modules.get("handwritten")


def _hw_inbox(app: App) -> Path:
    """The handwritten scan folder, as the reader finds it (modules/handwritten.py: folder()), without making it."""
    hw = _hw(app)
    own = str(hw.setting("folder") or "") if hw is not None else ""
    old = Path(app.workspace) / "handwritten-inbox"
    return Path(own).expanduser() if own else old if old.is_dir() else layout.file_dir(app, "handwritten_inbox")


def upload_roots(app: App) -> list[tuple[str, Path]]:
    """Where uploads land, with a word for each: the handwritten scan folder and its originals, the files folder,
    the notes, Downloads, and the folder files sent from Telegram or the phone go to."""
    roots = [("handwritten folder", _hw_inbox(app))]
    try:
        roots.append(("handwritten originals", layout.file_dir(app, "handwritten")))
        roots.append(("sent files", layout.file_dir(app, "inbox")))
    except (KeyError, ValueError):
        pass
    files = places.files_folder(app)
    if files is not None:
        roots.append(("files folder", files))
    roots.append(("notes", Path(app.workspace)))
    down = places.user_folder("downloads")
    if down is not None:
        roots.append(("Downloads", down))
    seen: set[str] = set()
    out = []
    for label, p in roots:
        k = os.path.normcase(os.path.abspath(p))
        if k not in seen and Path(p).is_dir():
            seen.add(k)
            out.append((label, Path(p)))
    return out


def _known(app: App) -> dict:
    """What the reader wrote out already: {scan's name: {"note": path}} (modules/handwritten.py)."""
    return jload(app.paths.state / "handwritten-notes.json", {}) or {}


def find_uploads(app: App, course: str = "", days: str = "", kind: str = "") -> str:
    """find_uploads' answer: the newest scans and PDFs, newest first, with where they are and whether they were
    written out already."""
    try:
        back = max(1, min(365, int(str(days or UPLOAD_DAYS).split()[0])))
    except ValueError:
        back = UPLOAD_DAYS
    since = time.time() - back * 86400
    words = _course_words(app, course) if str(course or "").strip() else []
    inbox = os.path.normcase(os.path.abspath(_hw_inbox(app)))
    known = _known(app)
    found: dict[str, tuple[float, str, Path]] = {}
    for label, root in upload_roots(app):
        n = 0
        for dirpath, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__")]
            for name in names:
                n += 1
                if n > SCAN_MAX:
                    break
                f = Path(dirpath) / name
                ext = f.suffix.lower()
                in_inbox = os.path.normcase(os.path.abspath(dirpath)).startswith(inbox)
                if name.startswith(".") or not (ext in PDFS or (ext in PICTURES and in_inbox)):
                    continue
                if kind == "pdf" and ext not in PDFS:
                    continue
                try:
                    st = f.stat()
                except OSError:
                    continue
                if st.st_mtime < since:
                    continue
                rel = f.relative_to(root).as_posix()
                if words and not _names_course(rel, words) and not _names_course(_note_course(known, f), words):
                    continue
                found.setdefault(str(f.resolve()), (st.st_mtime, label, f))
            if n > SCAN_MAX:
                break
    if not found:
        what = f" for {course}" if words else ""
        return (
            f"No scans or PDFs{what} in the last {back} days in: "
            + ", ".join(f"{label} ({p})" for label, p in upload_roots(app))
            + ". Ask them where the file is, or look further back (days)."
        )
    lines = []
    for mtime, label, f in sorted(found.values(), key=lambda x: -x[0])[:MAX_UPLOADS]:
        size = f.stat().st_size
        rec = known.get(f.name) or {}
        note = f"; written out already: {layout.shown(app, rec['note'])}" if rec.get("note") else ""
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
        lines.append(f"- {f} ({label}, {max(1, size // 1024)} KB, {when}{note})")
    more = f" (the newest {MAX_UPLOADS} of {len(found)})" if len(found) > MAX_UPLOADS else ""
    return f"Scans and PDFs from the last {back} days{more}, newest first:\n" + "\n".join(lines)


def _note_course(known: dict, f: Path) -> str:
    """The written-out note's path for a scan (it may name the course), or ""."""
    return str((known.get(f.name) or {}).get("note") or "")


# ------------------------------------------------------------------------------------------ read_handwritten
@dataclass
class Read:
    """One file being read now: its thread and how far it got, or what came of it."""

    file: Path
    sig: str
    thread: threading.Thread | None = None
    status: str = "starting"
    total: int = 0
    error: str = ""
    waiting: bool = False  # not now (a busy graphics card, on battery): try again later
    done: bool = False


_READS: dict[str, Read] = {}
_READS_LOCK = threading.Lock()


def _sig(f: Path) -> str:
    st = f.stat()
    return f"{st.st_size}:{int(st.st_mtime)}"


def _store(app: App, f: Path) -> Path:
    h = hashlib.sha1(str(f).encode()).hexdigest()[:12]  # noqa: S324 (a file name, not security)
    return app.paths.state / "studyflow" / "reads" / h


def _saved(app: App, f: Path, sig: str) -> dict | None:
    """A finished read of this version of the file: {"text", "how", "note"}; None when there isn't one."""
    d = _store(app, f)
    meta = jload(d.with_suffix(".json"), {}) or {}
    md = d.with_suffix(".md")
    if meta.get("sig") != sig or not md.is_file():
        return None
    return {**meta, "text": md.read_text(encoding="utf-8")}


def _pages_done(app: App, hw, f: Path) -> int:
    pages = hw._cache(f.name) / "pages"
    return len(list(pages.glob("*.md"))) if pages.is_dir() else 0


def _transcribe(app: App, hw, r: Read) -> tuple[str, str]:
    """The file's Markdown and how it was read, the way the reader does it (modules/handwritten.py:_one): a PDF page by
    page by the model here (any time of day: you asked), else Gemini when handwritten.cloud allows."""
    from kurooto.modules import handwritten as H

    f = r.file
    mime = H.KINDS[f.suffix.lower()]
    model = hw.local_model()
    if mime == "application/pdf" and model:
        doc = hw._doc(f)
        if hw.drawable(doc):
            r.total = min(doc.pages(), int(hw.setting("max_pages") or 60))
            r.status = "waiting for the graphics card"
            hw.gpu_room(model)
            r.status = "reading"
            md, n = hw.read_pdf(f, r.sig, model, None)
            return md, f"by {model} on this computer, {n} pages, unchecked"
        if not hw._cloud_ok():
            raise RuntimeError(
                "its pages can't be drawn as pictures here: Poppler's PDF tools are needed (or handwritten.cloud for "
                "Gemini)"
            )
    r.status = "reading with Gemini" if not model or mime == "application/pdf" else "reading"
    md = hw.write_out(f, H.PROMPT + (PAGED if mime == "application/pdf" else ""))
    if not md:
        raise RuntimeError("nothing could be read")
    return md, (f"by {model} on this computer, unchecked" if model and mime != "application/pdf" else "by Gemini")


def _work(app: App, hw, r: Read) -> None:
    """The read itself, on its own thread, holding the reader's lock (the folder's scan waits, and this waits for a scan
    that's running, up to an hour)."""
    from kurooto.core.lock import Lock, Timeout
    from kurooto.modules import handwritten as H

    lock = Lock(app.paths.state, "handwritten", timeout=5)
    start = time.time()
    while True:
        try:
            lock.acquire()
            break
        except Timeout:
            r.status = f"waiting for the reader to finish what it's doing ({hw.status or 'the scan folder'})"
            if time.time() - start > 3600:
                r.error, r.waiting = "the reader stayed busy for an hour", True
                return
            time.sleep(15)
    try:
        md, how = _transcribe(app, hw, r)
        note = ""
        inbox = places.inside(r.file, [_hw_inbox(app)])
        if inbox:  # a scan in the reader's own folder: its note too, as the reader would have made it
            title = H._title(r.file) if r.total > 1 else ""
            note = hw._file(r.file, md, title=title, how=how)
            seen_f = app.paths.state / "handwritten.json"
            seen = jload(seen_f, {}) or {}
            seen[r.file.name] = r.sig
            jsave(seen_f, dict(list(seen.items())[-2000:]))
        d = _store(app, r.file)
        d.parent.mkdir(parents=True, exist_ok=True)
        d.with_suffix(".md").write_text(md, encoding="utf-8")
        jsave(d.with_suffix(".json"), {"sig": r.sig, "file": str(r.file), "how": how, "note": note})
        shutil.rmtree(hw._cache(r.file.name), ignore_errors=True)
        r.done = True
        app.events.emit("studyflow_read", note=bool(note))
    except H.Waiting as e:
        r.error, r.waiting = str(e), True
    except Exception as e:  # a read that failed says so; the next call starts it again
        r.error = str(e)[:300]
        app.events.emit("studyflow_read_failed", error=f"{type(e).__name__}: {e}"[:200])
    finally:
        lock.release()


def start_read(app: App, hw, f: Path) -> Read:
    """This file's read: the running one, or a new one started now."""
    sig = _sig(f)
    key = f"{f}|{sig}"
    with _READS_LOCK:
        r = _READS.get(key)
        if r is not None and (r.done or (r.thread is not None and r.thread.is_alive())):
            return r
        r = _READS[key] = Read(f, sig)
        r.thread = threading.Thread(target=_work, args=(app, hw, r), name="studyflow-read", daemon=True)
        r.thread.start()
    return r


def cut_from(text: str, topic: str) -> tuple[str, str]:
    """The part of a transcription from the heading that matches `topic` to the end, and a line saying where it
    starts; (text, why not) when no heading is close. N12's find_topic (modules/handwritten_overlap.py) when it's in
    this build, else a thin match of the same kind (_find_topic)."""
    try:
        from kurooto.modules.handwritten_overlap import find_topic  # N12 (f/v090-hwdup)
    except ImportError:
        find_topic = _find_topic
    hit = find_topic(text, topic)
    if hit is None:
        heads = [h for _, h in _headings(text) if not re.fullmatch(r"(?i)page\s+\d+", h)][:30]
        return text, f"No heading matches {topic!r}; the headings are: " + "; ".join(heads)
    line, head = hit
    lines = text.split("\n")
    page = next(
        (
            re.sub(r"\D", "", h)
            for i, h in reversed(_headings(text))
            if i <= line and re.fullmatch(r"(?i)page\s+\d+", h)
        ),
        "",
    )
    return "\n".join(lines[line:]), f"From the heading {head!r}" + (f" (page {page})" if page else "") + " to the end"


def _headings(text: str) -> list[tuple[int, str]]:
    out = []
    for i, ln in enumerate(text.split("\n")):
        m = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", ln) or re.match(r"^\s*\*\*([^*].*?)\*\*:?\s*$", ln)
        if m:
            out.append((i, m[1].strip().strip("*").strip().rstrip(":").strip()))
    return out


def _find_topic(text: str, topic: str) -> tuple[int, str] | None:
    """The thin heading match (used when N12's isn't in this build): the heading with the topic's words, or one inside
    the other, or close in spelling; the first one on a tie."""
    import difflib

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

    want = norm(topic)
    words = set(want.split()) - {"of", "the", "a", "an", "and", "in", "on"}
    if not want:
        return None
    best, score = None, 0.0
    for i, h in _headings(text):
        k = norm(h)
        if not k or re.fullmatch(r"page \d+", k):
            continue
        hw = set(k.split())
        if k == want:
            sc = 1.0
        elif min(len(k), len(want)) >= 4 and (want in k or k in want):
            sc = 0.9
        else:
            sc = max(difflib.SequenceMatcher(None, k, want).ratio(), len(hw & words) / len(hw | words or {""}))
        if sc > score:
            best, score = (i, h), sc
    return best if score >= 0.7 else None


def _wait_arg(v) -> float:
    s = str(v if v is not None else "true").strip().lower()
    if s in ("", "true", "yes", "on", "1"):
        return WAIT_S
    if s in ("false", "no", "off", "0"):
        return 0
    try:
        return max(0.0, min(float(s), WAIT_S))
    except ValueError:
        return WAIT_S


def _resolve_upload(app: App, raw: str) -> tuple[Path | None, str]:
    raw = str(raw or "").strip().removeprefix("file://")
    if not raw:
        return None, "Which file? Give its full path (find_uploads lists them)."
    f = Path(os.path.expanduser(raw))
    if not f.is_absolute():
        f = Path(app.workspace) / f
    if not f.is_file():
        return None, f"There's no file at {raw}."
    roots = places.read_roots(app) + [p for _, p in upload_roots(app)]
    if not places.inside(f, roots):
        return None, "That file is outside the folders I may read."
    return f.resolve(), ""


def read_handwritten(app: App, file: str, wait=None, from_topic: str = "", start: str = "") -> str:
    """read_handwritten's answer: the transcription (from a topic on when asked), or how far the read is."""
    from kurooto.modules import handwritten as H

    hw = _hw(app)
    if hw is None or not app.is_on("handwritten"):
        return "Handwritten notes is off: dashboard → Features → Handwritten notes → Turn on. Tell them so."
    f, why = _resolve_upload(app, file)
    if f is None:
        return why
    if f.suffix.lower() not in H.KINDS:
        return f"{f.name} isn't a scan the reader takes (PDF or a photo)."
    ok, why = hw.ready()
    if not ok:
        return f"The handwritten reader can't read it here: it {why}. Tell them so."
    got = _saved(app, f, _sig(f))
    if got is None:
        r = start_read(app, hw, f)
        budget, t0, told = _wait_arg(wait), time.time(), time.time()
        last_page = -1
        while not r.done and r.thread is not None and r.thread.is_alive() and time.time() - t0 < budget:
            time.sleep(POLL_S)
            page = _pages_done(app, hw, f)
            if r.total and page != last_page and time.time() - told >= PROGRESS_S:  # "told as it goes" (N13)
                app.notify(f"Reading {f.name}: page {min(page + 1, r.total)} of {r.total}.", kind="info", why="asked")
                told, last_page = time.time(), page
        got = _saved(app, f, r.sig) if r.done else None
        if got is None:
            if r.error:
                if r.waiting:
                    return f"Not now: {r.error}. Call read_handwritten again later, or tell them why it waits."
                return f"The reader failed on {f.name}: {r.error}"
            page = _pages_done(app, hw, f)
            far = f"page {min(page + 1, r.total)} of {r.total}" if r.total else r.status
            return (
                f"Still reading {f.name} ({far}). It carries on by itself: call read_handwritten with the same file "
                "again to wait for it (and tell them how far it is with study_progress)."
            )
    text = got["text"]
    head = f"Transcription of {f.name} ({got.get('how') or 'read'})"
    if got.get("note"):
        head += f"; written out as the note {got['note']}"
    if from_topic and from_topic.strip():
        text, where = cut_from(text, from_topic.strip())
        head += f". {where}"
    try:
        at = max(0, int(str(start or "0")))
    except ValueError:
        at = 0
    part = text[at : at + CHUNK]
    more = (
        f"\n\n[… {len(text) - at - CHUNK} more characters: call read_handwritten with start={at + CHUNK}]"
        if len(text) > at + CHUNK
        else ""
    )
    return f"{head}:\n\n{part}{more}"


# ------------------------------------------------------------------------------------------ build_study_pack
def pack_folder(app: App, subject: str) -> Path:
    return Path(app.paths.cache) / "study-packs" / f"{subject}-notes-pack"


def build_study_pack(app: App, subject: str, topics: str = "", aim: str = "") -> str:
    """build_study_pack's answer: the unpacked pack's folder, its PROMPT.md and its INDEX.md."""
    from kurooto.core import studypack

    sid, name = _subject(app, subject)
    if not sid:
        return "Which subject? Name the course."
    wanted = [t.strip() for t in re.split(r"[,;\n]+", str(topics or "")) if t.strip()] or None
    folder = pack_folder(app, sid)
    try:
        zip_path, info = studypack.build(
            app,
            sid,
            name if name != subject else "",
            str(aim or ""),
            dest=folder.with_suffix(".zip"),
            limit=None,
            topics=wanted,
        )
    except ValueError as e:
        return str(e)
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:  # our own zip: its names are paths we made, still checked
        for item in z.infolist():
            target = (folder / item.filename).resolve()
            if folder.resolve() not in target.parents or item.is_dir():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(item))
    prompt = (folder / "PROMPT.md").read_text(encoding="utf-8")
    index = (folder / "INDEX.md").read_text(encoding="utf-8")
    app.events.emit("studyflow_pack", notes=info["notes"], files=info["files"])
    work = places.work_folder(app) / sid
    work.mkdir(parents=True, exist_ok=True)
    tex = work / f"{now():%Y-%m-%d}-{sid}-study-notes.tex"
    said = (
        f"The study pack is unpacked in {folder} (the zip: {zip_path}): {info['class']} class files, "
        f"{info['books']} book extracts and {info['notes']} notes. Read its files with read_file. Write the notes by "
        f"its PROMPT.md, as LaTeX, at {tex} (write_note with that full path: Kurooto's work folder, where you may fix "
        "it freely), then compile_latex, then save_course_file for the PDF and the .tex."
    )
    return f"{said}\n\n--- PROMPT.md ---\n{prompt}\n--- INDEX.md ---\n{index[:6000]}"


# ------------------------------------------------------------------------------------------ save_course_file
def _filed(app: App) -> Path:
    return app.paths.state / "studyflow" / "filed.json"


def _free_name(dest: Path, src: Path, ours: bool) -> Path:
    """dest, or dest-2, dest-3 … when a different file of yours is there (one Kurooto filed before is replaced)."""
    if not dest.exists() or ours:
        return dest
    try:
        if dest.read_bytes() == src.read_bytes():
            return dest
    except OSError:
        pass
    n = 2
    while True:
        cand = dest.with_name(f"{dest.stem}-{n}{dest.suffix}")
        if not cand.exists():
            return cand
        n += 1


def _copy_dir(app: App, raw: str) -> tuple[Path | None, str]:
    """A folder you named for a copy ("Downloads/Study"): in Downloads, Documents or a folder the AI may write in."""
    raw = str(raw or "").strip()
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():
        p = Path.home() / p
    allowed = [x for x in (places.user_folder("downloads"), places.user_folder("documents")) if x is not None]
    allowed += places.write_roots(app)
    if not any(Path(os.path.abspath(p)) == Path(os.path.abspath(a)) or places.inside(p, [a]) for a in allowed):
        return None, f"I can only copy into Downloads, Documents, the notes or the files folder, not {raw}."
    if any(x.startswith(".") for x in p.parts[1:]):
        return None, "Not into a hidden folder."
    return p, ""


def save_course_file(app: App, course: str, path: str, title: str = "", copy_to: str = "") -> str:
    """save_course_file's answer: where the file went, the source note, and the copy."""
    from kurooto.core import graphwrite as gw
    from kurooto.core.tools import write_note_file

    sid, name = _subject(app, course)
    if not sid:
        return "Which course? Name it."
    raw = str(path or "").strip().removeprefix("file://")
    src = Path(os.path.expanduser(raw))
    if not src.is_absolute():
        src = Path(app.workspace) / src
    if not src.is_file():
        return f"There's no file at {raw}."
    if src.suffix.lower() not in FILE_EXT:
        return f"Only documents: {', '.join(sorted(FILE_EXT))}."
    roots = places.read_roots(app) + [Path(app.paths.cache) / "study-packs"]
    if not places.inside(src, roots):
        return "That file is outside the folders I may read."
    src = src.resolve()
    dest_dir = layout.file_dir(app, "subject", subject=sid)
    notes_root = places.notes_root(app).resolve()
    if dest_dir.resolve() == notes_root:  # never the notes' own top folder
        dest_dir = notes_root / sid / "files"
    filed = jload(_filed(app), {}) or {}
    if src.parent == dest_dir.resolve():
        dest = src
    else:
        target = dest_dir / src.name
        dest = _free_name(target, src, ours=filed.get(str(target)) is not None)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    filed[str(dest)] = {"at": now().isoformat(timespec="seconds"), "course": sid}
    jsave(_filed(app), dict(list(filed.items())[-2000:]))
    # the source note: <the course's notes folder>/<the file's name>.md, Kurooto's block listing what's filed
    note_dir = layout.path(app, "subject", subject=sid)
    stem = re.sub(r"[^a-z0-9]+", "-", dest.stem.lower()).strip("-") or "document"
    note = note_dir / f"{stem}.md"
    heading = title.strip() or re.sub(r"[-_]+", " ", dest.stem).strip().capitalize()
    link = layout.file_link(app, dest, note).removeprefix("!")
    kind = {".pdf": "PDF", ".tex": "LaTeX source"}.get(dest.suffix.lower(), dest.suffix.lstrip(".").upper())
    line = f"- {link}: {kind}, filed {now():%Y-%m-%d}"
    old = note.read_text(encoding="utf-8") if note.is_file() else None
    have = re.search(r"<!-- kurooto:files\b[^>]*-->(.*?)<!-- /kurooto:files -->", old or "", re.S)
    rows = [r for r in (have[1].strip().split("\n") if have else []) if r.strip() and f"]({_target(link)})" not in r]
    body = "\n".join([*rows, line])
    if old is None:
        front = layout.frontmatter(app, None, note, title=heading, tags=["source", sid, "study-notes"])
        if "trust_tier:" not in front:
            front = layout.frontmatter(
                app, None, note, title=heading, tags=["source", sid, "study-notes"], trust_tier="agent_written"
            )
        text = f"{front}# {heading}\n\nStudy notes for {name or sid}, made by Kurooto.\n\n" + gw.block("files", body)
        write_note_file(note, text + "\n", create=True)
    else:
        new = gw.put_block(old, "files", body)
        if not gw.guarded(old, new).ok:
            return (
                f"Filed {dest}, but the note {layout.shown(app, note)} couldn't be updated without changing your text."
            )
        write_note_file(note, new)
    said = f"Filed {dest} in {name or sid}'s files folder; the source note {layout.shown(app, note)} links it."
    if copy_to and str(copy_to).strip():
        folder, why = _copy_dir(app, copy_to)
        if folder is None:
            return said + " " + why
        folder.mkdir(parents=True, exist_ok=True)
        copy = _free_name(folder / dest.name, dest, ours=False)
        shutil.copy2(dest, copy)
        said += f" A copy is in {copy}."
    if src != dest and places.inside(src, [places.notes_root(app)]):
        said += (
            f" The original is still at {layout.shown(app, src)} (I don't delete it; tell them in case they want it "
            "gone)."
        )
    app.events.emit("studyflow_filed", kind=dest.suffix.lower()[:6])
    return said


def _target(link: str) -> str:
    m = re.search(r"\]\(([^)]*)\)$", link)
    return m[1] if m else link


# ---------------------------------------------------------------------------------------------- the tools
def progress(app: App, text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()[:300]
    if not text:
        return "Nothing to say."
    app.notify(text, kind="info", why="asked")
    return "Told them."


def n2_present() -> bool:
    """Is N2's compile_latex (core/tools.py, branch f/v090-tools) in this build? Then it's the compile tool."""
    from kurooto.core import tools as T

    return hasattr(T, "latex_tools")


def compile_available(app: App) -> bool:
    if n2_present():
        return bool(app.settings.get("tools.latex"))
    return on(app)


def latex_line(app: App) -> str:
    """For every AI request's context (providers/context.py): compile LaTeX yourself, fix and retry; "" without the
    tool."""
    return LATEX_RULE if compile_available(app) else ""


def compile_tool_thin(app: App) -> list[Tool]:
    """compile_latex when N2's isn't in this build (a merge keeps N2's and makes it answer through
    core/latexcheck.py:compile_checked)."""
    from kurooto.core import latexcheck

    if n2_present() or not on(app):
        return []
    return [
        Tool(
            "compile_latex",
            "Compile a LaTeX .tex file to a PDF (shell escape off), after a self-check for the usual mistakes "
            "(unbalanced braces or environments, a package not loaded, ']' inside an optional argument, missing "
            "\\input files). The answer gives the PDF's path, or the errors with their lines to fix.",
            lambda a: latexcheck.compile_checked(app, a.get("path")),
            {"path": arg("the .tex file's full path, or its path in the notes folder")},
            ("path",),
            writes=True,
            hint=LATEX_RULE,
        )
    ]


def tools(app: App) -> list[Tool]:
    """The workflow's tools (none when study.notes_workflow is off)."""
    if not on(app):
        return []
    return [
        Tool(
            "find_uploads",
            "The newest scans and PDFs they uploaded (the handwritten folder, the notes, the files folder, "
            "Downloads), newest first, by course and how recent, with whether each was written out already.",
            lambda a: find_uploads(app, a.get("course") or "", a.get("days") or "", a.get("kind") or ""),
            {
                "course": arg("the course, e.g. AN2 or real analysis 2, optional"),
                "days": arg("how many days back, default 14"),
                "kind": arg("pdf for PDFs only, optional"),
            },
            writes=False,
        ),
        Tool(
            "read_handwritten",
            "Read a handwritten scan or PDF now with Kurooto's handwritten reader (its own settings: a model on this "
            "computer, or Gemini only when they allow it) and get the transcription with its '## Page N' lines. "
            "It waits up to five minutes; a long PDF comes back with how far it got, and calling again carries on "
            "waiting. from_topic gives the part from that heading to the end.",
            lambda a: read_handwritten(
                app, a.get("file") or "", a.get("wait"), a.get("from_topic") or "", a.get("start") or ""
            ),
            {
                "file": arg("the scan's full path (from find_uploads)"),
                "wait": arg("true (the default) to wait for it, false to start it and come back, or seconds"),
                "from_topic": arg("only the part from this heading to the end, e.g. Functions of several variables"),
                "start": arg("for a long transcription: the character to go on from"),
            },
            ("file",),
            writes=True,  # a scan in the handwritten folder gets its note, as the reader makes it
        ),
        Tool(
            "build_study_pack",
            "Build the study pack for a course and topics (class material first, the books' chapters on the topics, "
            "their notes) and unpack it where you can read it: the folder, its PROMPT.md (how to write the notes) "
            "and INDEX.md. Nothing is sent to them.",
            lambda a: build_study_pack(app, a.get("subject") or "", a.get("topics") or "", a.get("aim") or ""),
            {
                "subject": arg("the course, e.g. AN2"),
                "topics": arg("the topics, comma-separated, e.g. inverse function theorem, implicit function theorem"),
                "aim": arg("what it's for, optional"),
            },
            ("subject",),
            writes=False,
        ),
        Tool(
            "save_course_file",
            "File a document you made (the PDF, the .tex) in the course's files folder, never the notes, and write "
            "or update a short source note in the course's notes folder that links it. copy_to also puts a copy in "
            "a folder they named (e.g. Downloads/Study). Use it for every document you make for a course.",
            lambda a: save_course_file(
                app, a.get("course") or "", a.get("path") or "", a.get("title") or "", a.get("copy_to") or ""
            ),
            {
                "course": arg("the course, e.g. AN2"),
                "path": arg("the file's full path"),
                "title": arg("the source note's title, optional"),
                "copy_to": arg("a folder for a copy, optional, e.g. Downloads/Study"),
            },
            ("course", "path"),
            writes=True,
        ),
        Tool(
            "study_progress",
            "Tell them in one short line how the work is going (reading page 7 of 13, building the pack, "
            "compiling, try 2 of 3). Use it between steps of a long request.",
            lambda a: progress(app, a.get("text") or ""),
            {"text": arg("one short line")},
            ("text",),
            writes=False,
        ),
        *compile_tool_thin(app),
    ]


def intent_match(app: App, text: str) -> dict | None:
    """ "make notes from my AN2 notes from functions of several variables", "write deep notes from this scan":
    the workflow's request, for the AI with the skill named (modules/skills.py intents)."""
    if not on(app):
        return None
    t = " ".join(str(text or "").split())
    if len(t) > 600 or t.startswith("/"):
        return None
    verb = re.match(r"(?i)^(?:(?:please|can you|could you|hey)[, ]+)?(make|write|build|create|prepare|turn|read)\b", t)
    if not verb:
        return None
    if not re.search(r"(?i)\bnotes\b", t):
        return None
    if not re.search(r"(?i)\b(?:from|out of|using|of)\s+(?:my|the|this|these|that|those)\b", t):
        return None
    if verb[1].lower() == "read" and not re.search(r"(?i)study pack|deep notes|\bpdf\b", t):
        return None
    if re.search(r"(?i)\bnote that\b|\bremind\b", t):
        return None
    return {"text": t}


def describe_json(app: App) -> str:  # pragma: no cover - a debugging aid for `kurooto mcp` users
    return json.dumps([t.name for t in tools(app)])
