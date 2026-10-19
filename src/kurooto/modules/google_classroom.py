"""Classroom → notes: three times a day Kurooto reads your Google Classroom (read-only): materials, coursework,
announcements, and the Drive files your teachers attach or link. The AI then files each course into your notes:
a note per lecture or problem set in <subject>/, the course page <subject>/course.md (lecture notes, exams,
announcements), and an always-current <subject>/exam-prep.md. Kurooto keeps only the part of exam-prep.md between
its markers current; anything you write around it stays as you wrote it. Due dates found in posts (exams, quizzes,
moved deadlines) go into Deadlines; assignment due dates already arrive there through the Google feature.

    /classnotes                  file what's new now
    /classnotes courses          your courses and the notes folder each one goes to
    /classnotes skip <words>     leave out a course (words from its name); /classnotes unskip <words>

It asks Google for two permissions the Classroom deadlines don't need: course materials (read-only) and Google
Drive (read-only, so it can open the files attached to posts; it opens nothing else). Downloaded files stay in
Kurooto's own data folder, not in your notes. Posts about topics on your not-interested list are only counted.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import urllib.parse
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from kurooto.core import proc
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock, Timeout
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming
from kurooto.modules.calls.tools import Tool, arg, clip
from kurooto.modules.google import GoogleError, GooglePart, NeedsSignIn, due_of, not_interested, run_skill

register_defaults(
    "classroom_notes",
    {
        "at": "daily 07:00,13:00,19:00",
        "skip": [],  # courses to leave out: words from their names
        "folders": {},  # a course's exact name -> the notes folder you want it in (otherwise Kurooto picks one)
        "files": True,  # download the Drive files attached to posts and read their text
        "max_file_mb": 30,
        "backfill_days": 60,  # the first run files posts from this many days back
    },
)
KINDS = (  # what Classroom calls them: (our name, the collection, the list's key)
    ("material", "courseWorkMaterials", "courseWorkMaterial"),
    ("coursework", "courseWork", "courseWork"),
    ("announcement", "announcements", "announcements"),
)
APPS = "application/vnd.google-apps."
EXPORT = {  # Google's own files -> a text version Drive can give us
    APPS + "document": ("text/plain", ".txt"),
    APPS + "presentation": ("text/plain", ".txt"),
    APPS + "spreadsheet": ("text/csv", ".csv"),
}
DRIVE_FILE = re.compile(
    r"(?:drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:export=\w+&)?id=)|"
    r"docs\.google\.com/(?:document|presentation|spreadsheets)/d/)([\w-]{20,})"
)
DRIVE_FOLDER = re.compile(r"drive\.google\.com/drive/(?:u/\d+/)?folders/([\w-]{20,})")
URL = re.compile(r"https?://[^\s<>\"'()\[\]]+")
TEXT_EXT = {".txt", ".md", ".csv", ".tex", ".py", ".r", ".m", ".json"}
PER_BATCH = 12  # items per AI request
BUDGET = 120_000  # characters of file text per request (more can be read with read_course_file)
START = "<!-- kurooto:exam-prep"  # Kurooto's part of exam-prep.md starts with this line...
END = "<!-- /kurooto:exam-prep -->"  # ...and ends with this one
START_LINE = f"{START} (kept current by Kurooto from your courses; write your own notes outside these markers) -->"


def slugify(text: str, n: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:n].strip("-") or "untitled"


# ------------------------------------------------------------------------------------------------ file text
def extract_text(path: Path) -> str | None:
    """The text of a downloaded file, where that's possible without extra software (PDFs need pdftotext)."""
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXT:
            return path.read_text(encoding="utf-8", errors="replace")
        if ext == ".ipynb":
            cells = json.loads(path.read_text(encoding="utf-8", errors="replace")).get("cells", [])
            return "\n\n".join("".join(c.get("source", [])) for c in cells)
        if ext == ".docx":
            return _xml_text(path, ["word/document.xml"], "p")
        if ext == ".pptx":
            with zipfile.ZipFile(path) as z:
                slides = sorted(
                    (n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                    key=lambda n: int(re.search(r"\d+", n.rsplit("/", 1)[1]).group()),
                )
            return _xml_text(path, slides, "p", sep="slide")
        if ext == ".pdf" and shutil.which("pdftotext"):
            r = proc.run(["pdftotext", "-layout", str(path), "-"], timeout=120)
            return r.out if r.ok and r.out.strip() else None
    except Exception:
        return None
    return None


def _xml_text(path: Path, members: list[str], para: str, sep: str = "") -> str:
    """Text runs from Office XML parts (Word paragraphs, slide shapes), one line per paragraph."""
    out = []
    with zipfile.ZipFile(path) as z:
        for i, name in enumerate(members, 1):
            root = ElementTree.fromstring(z.read(name))  # noqa: S314 (a file from the user's own Classroom)
            lines = []
            for p in root.iter():
                if p.tag.rsplit("}", 1)[-1] == para:
                    t = "".join(x.text or "" for x in p.iter() if x.tag.rsplit("}", 1)[-1] == "t")
                    if t.strip():
                        lines.append(t)
            out.append((f"--- {sep} {i} ---\n" if sep else "") + "\n".join(lines))
    return "\n\n".join(out)


def write_exam_prep(root: Path, folder: str, text: str, course: str, made_by: str) -> str:
    """Put Kurooto's exam prep for a course between its markers in <folder>/exam-prep.md; nothing else changes."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", folder or ""):
        return "The subject must be a notes folder name like linear-algebra."
    text = re.sub(r"<!--\s*/?kurooto:exam-prep.*?-->", "", text or "").strip()
    if not text:
        return "Nothing to write."
    block = f"{START_LINE}\n{text}\n{END}"
    f = root / folder / "exam-prep.md"
    if f.exists():
        old = f.read_text(encoding="utf-8", errors="replace")
        i = old.find(START)
        j = old.find(END, i + 1) if i >= 0 else -1
        new = old[:i] + block + old[j + len(END) :] if i >= 0 and j > i else old.rstrip("\n") + "\n\n" + block + "\n"
    else:
        f.parent.mkdir(parents=True, exist_ok=True)
        new = (
            f"---\nmade_by: {made_by}\ndate: {now():%Y-%m-%d}\ntags: [exam-prep]\n---\n\n"
            f"# Exam prep: {course or folder}\n\n{block}\n"
        )
    f.write_text(new, encoding="utf-8")
    return f"Updated {folder}/exam-prep.md."


class ClassroomNotes(GooglePart):
    id = "classroom_notes"
    part = "classroom_notes"
    title = "Classroom → notes"
    description = (
        "Three times a day, new Classroom materials, coursework and announcements (with the files attached) filed "
        "into your notes by the AI: a note per lecture, a course page and an always-current exam-prep note."
    )
    privacy = (
        "Reads your Google Classroom and the Drive files attached to its posts (read-only; it asks Google for "
        "Classroom materials and Drive read access). Files stay in Kurooto's data folder; posts and file text go to "
        "the AI you picked to write the notes. Nothing is changed in Classroom or Drive."
    )
    permission = (
        "Google will ask you to allow Kurooto to see your Classroom course materials and to see and download your "
        "Google Drive files (read-only). Kurooto opens only the files attached to or linked from Classroom posts."
    )
    api_link = ("Turn on the Google Drive API", "https://console.cloud.google.com/apis/library/drive.googleapis.com")
    heavy = True

    @property
    def dir(self) -> Path:
        return self.app.paths.state / "classroom-notes"

    @property
    def files_dir(self) -> Path:
        return self.app.paths.data / "classroom"

    def start(self):
        self.every("sync", self.setting("at") or "daily 07:00,13:00,19:00", self.sync)
        self.app.jobs.then_actions["classroom_notes.filed"] = self._filed

    # ------------------------------------------------------------------------------------------ courses
    def skipped(self, course: str) -> bool:
        name = course.lower()
        return any(w.strip().lower() in name for w in self.setting("skip") or [] if w.strip())

    def folder(self, course: str) -> str:
        """The notes folder for a course: your choice, else a subject of yours it names, else its name as a slug."""
        chosen = (self.setting("folders") or {}).get(course)
        if chosen:
            return slugify(chosen)
        known = jload(self.dir / "folders.json", {}) or {}
        if course in known:
            return known[course]
        slug = None
        subj = self.app.modules.get("subjects")
        if subj is not None and self.app.is_on("subjects"):
            low, best = course.lower(), 0
            for s in subj.subjects():
                for cand in [s.get("name", ""), s.get("slug", "").replace("-", " "), *s.get("aliases", [])]:
                    cand = cand.strip().lower()
                    if len(cand) >= 2 and re.search(rf"\b{re.escape(cand)}\b", low) and len(cand) > best:
                        slug, best = s["slug"], len(cand)
        slug = slug or slugify(re.sub(r"\([^)]*\)", "", course), 50)
        known[course] = slug
        jsave(self.dir / "folders.json", known)
        return slug

    # ------------------------------------------------------------------------------------------- fetching
    def sync(self, p: dict | None = None) -> dict:
        """Fetch what's new in Classroom, keep it as one batch per course, and hand the batches to the AI."""
        if not self.allowed():
            return {"skipped": "needs Google's OK"}
        try:
            with Lock(self.app.paths.state, "classroom-notes", timeout=0):
                try:
                    found = self.fetch()
                except NeedsSignIn:
                    return {"error": "needs sign-in"}
                except Exception as e:
                    self.app.events.emit("classroom_notes_failed", error=str(e)[:200])
                    return {"error": str(e)[:200]}
                queued = self.queue()
        except Timeout:
            return {"skipped": "already running"}
        self.app.events.emit("classroom_notes_fetched", **found, queued=queued)
        return {**found, "queued": queued}

    def fetch(self) -> dict:
        g = self.google
        seen_file = self.dir / "seen.json"
        seen = jload(seen_file, {}) or {}
        first = not seen
        cutoff = (now() - dt.timedelta(days=self.setting("backfill_days") or 60)).date().isoformat() if first else ""
        out = {"items": 0, "courses": 0, "not_interested": 0}
        courses = list(g.pages("classroom", "/courses", "courses", {"studentId": "me", "courseStates": "ACTIVE"}))
        for c in courses:
            name = c.get("name") or "a course"
            if self.skipped(name) or not_interested(self.app, name):
                continue
            folder, items, ignored = self.folder(name), [], 0
            for kind, coll, key in KINDS:
                try:
                    found = list(g.pages("classroom", f"/courses/{c['id']}/{coll}", key, {"pageSize": 50}, limit=4))
                except GoogleError as e:  # e.g. a course that doesn't share materials
                    self.app.events.emit("classroom_notes_unreadable", kind=kind, code=e.code)
                    continue
                for it in found:
                    iid = f"{c['id']}:{kind}:{it['id']}"
                    stamp = it.get("updateTime") or it.get("creationTime") or "?"
                    if seen.get(iid) == stamp:
                        continue
                    seen[iid] = stamp
                    date = (it.get("creationTime") or it.get("updateTime") or now().isoformat())[:10]
                    if date < cutoff:  # the first run only goes back so far
                        continue
                    text = it.get("description") or it.get("text") or ""
                    if not_interested(self.app, f"{it.get('title', '')} {text[:400]}"):
                        ignored += 1
                        continue
                    items.append(self.item(kind, it, text, folder, date))
            if items or ignored:
                self._save_batches(name, folder, sorted(items, key=lambda x: x["date"]), ignored)
                out["courses"] += 1
            out["items"] += len(items)
            out["not_interested"] += ignored
        jsave(seen_file, seen)  # only after the batches are written: a crash in between files twice, never not at all
        return out

    def item(self, kind: str, it: dict, text: str, folder: str, date: str) -> dict:
        due = due_of(it)
        rec = {
            "kind": kind,
            "title": it.get("title") or ("announcement" if kind == "announcement" else "untitled"),
            "date": date,
            "due": f"{due:%Y-%m-%d %H:%M}" if due else "",
            "url": it.get("alternateLink", ""),
            "text": clip(text, 6000),
            "files": [],
            "links": [],
        }
        for m in it.get("materials", []):
            if "driveFile" in m:
                df = m["driveFile"].get("driveFile", {})
                rec["files"].append(self.drive_file(df.get("id", ""), df.get("title"), df.get("alternateLink"), folder))
            elif "link" in m:
                rec["links"].append(m["link"].get("url", ""))
            elif "youtubeVideo" in m:
                rec["links"].append(m["youtubeVideo"].get("alternateLink", ""))
            elif "form" in m:
                rec["links"].append(m["form"].get("formUrl", ""))
        for url in dict.fromkeys(u.rstrip(".,;:") for u in URL.findall(text)):  # Drive links written in the post
            if (f := DRIVE_FILE.search(url)) and not any(f.group(1) in (x.get("link") or "") for x in rec["files"]):
                rec["files"].append(self.drive_file(f.group(1), None, url, folder))
            elif d := DRIVE_FOLDER.search(url):
                rec["files"] += self.drive_folder(d.group(1), url, folder)
            elif url not in rec["links"]:
                rec["links"].append(url)
        rec["links"] = [x for x in rec["links"] if x]
        return rec

    def drive_folder(self, fid: str, url: str, folder: str) -> list[dict]:
        try:
            files = self.google.api(
                "drive",
                f"/files?{urllib.parse.urlencode({'q': f"'{fid}' in parents and trashed=false"})}"
                "&fields=files(id,name,mimeType)&pageSize=30&supportsAllDrives=true&includeItemsFromAllDrives=true",
            ).get("files", [])
        except GoogleError as e:
            return [{"title": "a Drive folder", "link": url, "note": f"no access ({e.code})"}]
        out = []
        for f in files[:15]:
            if f.get("mimeType") == APPS + "folder":
                out.append({"title": f.get("name"), "link": url, "note": "a folder inside it, not opened"})
            else:
                out.append(self.drive_file(f["id"], f.get("name"), None, folder))
        if len(files) > 15:
            out.append({"title": f"{len(files) - 15} more files in that folder", "link": url, "note": "not opened"})
        return out

    def drive_file(self, fid: str, title: str | None, link: str | None, folder: str) -> dict:
        """Download one Drive file into Kurooto's data folder and read its text, when that's possible."""
        rec = {"title": title or "a Drive file", "link": link or f"https://drive.google.com/file/d/{fid}/view"}
        if not self.setting("files"):
            return {**rec, "note": "files are off (classroom_notes.files)"}
        cap = int(self.setting("max_file_mb") or 30) * 2**20
        g = self.google
        try:
            meta = g.api("drive", f"/files/{fid}?fields=id,name,mimeType,size&supportsAllDrives=true")
            mime, name = meta.get("mimeType", ""), meta.get("name") or title or fid
            rec["title"] = title or name
            stem, ext = Path(name).stem, Path(name).suffix.lower()
            if mime in EXPORT:
                out_mime, ext = EXPORT[mime]
                data = g.api("drive", f"/files/{fid}/export?mimeType={urllib.parse.quote(out_mime)}", raw=cap)
            elif mime.startswith(APPS):
                return {**rec, "note": f"a Google {mime.removeprefix(APPS)}: open the link"}
            elif mime.startswith(("video/", "audio/", "image/")):
                return {**rec, "note": f"{mime.split('/')[0]}: open the link"}
            elif int(meta.get("size") or 0) > cap:
                return {**rec, "note": f"too large ({int(meta['size']) // 2**20} MB): open the link"}
            else:
                data = g.api("drive", f"/files/{fid}?alt=media&supportsAllDrives=true", raw=cap)
        except NeedsSignIn:
            raise
        except GoogleError as e:
            return {**rec, "note": "too large: open the link" if e.code == 413 else f"no access ({e.code})"}
        except Exception as e:
            return {**rec, "note": f"not downloaded ({type(e).__name__})"}
        path = self.files_dir / folder / f"{now():%Y-%m-%d}-{slugify(stem, 50)}-{fid[:6]}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        text = extract_text(path)
        rel = path.relative_to(self.files_dir).as_posix()
        if text and text.strip():
            if path.suffix not in (".txt",):
                path.with_name(path.name + ".txt").write_text(text, encoding="utf-8")
            return {**rec, "file": rel, "chars": len(text)}
        return {**rec, "file": rel, "path": str(path), "note": "no text read from it (open the file if you can)"}

    def _save_batches(self, course: str, folder: str, items: list[dict], ignored: int) -> None:
        d = self.dir / "batches"
        stamp = f"{now():%Y%m%d-%H%M%S}"
        chunks = [items[i : i + PER_BATCH] for i in range(0, len(items), PER_BATCH)] or [[]]
        for n, chunk in enumerate(chunks):
            if not chunk:
                continue
            jsave(
                d / f"{stamp}-{folder}-{n}.json",
                {"course": course, "folder": folder, "items": chunk, "not_interested": ignored if n == 0 else 0},
            )

    # ------------------------------------------------------------------------------------- the AI's turn
    def file_text(self, rel: str) -> str | None:
        base = self.files_dir.resolve()
        f = (base / str(rel or "")).resolve()
        try:
            f.relative_to(base)
        except ValueError:
            return None
        for cand in (f.with_name(f.name + ".txt"), f):
            if cand.is_file() and (cand.suffix in TEXT_EXT or cand == f.with_name(f.name + ".txt")):
                return cand.read_text(encoding="utf-8", errors="replace")
        return None

    def render(self, b: dict) -> str:
        """A batch as the text the classroom-digest skill reads."""
        folder, budget = b["folder"], BUDGET
        lines = [
            f"Course: {b['course']}",
            f"Notes folder: {folder}/ (course page {folder}/course.md, exam prep {folder}/exam-prep.md)",
            f"New or changed items: {len(b['items'])}",
        ]
        if b.get("not_interested"):
            lines.append(f"Skipped (not interested): {b['not_interested']}")
        for n, it in enumerate(b["items"], 1):
            lines += [
                "",
                f"=== {n}. {it['kind']}: {it['title']} ({it['date']}) ===",
                f"Link: {it['url']}" if it.get("url") else None,
                f"Due: {it['due']}" if it.get("due") else None,
                "Post:",
                it.get("text") or "(no text)",
            ]
            for f in it.get("files", []):
                head = f"- File: {f.get('title')} ({f.get('link')})"
                text = self.file_text(f["file"]) if f.get("chars") else None
                if text:
                    take = max(2000, min(len(text), budget // 2, 30000))
                    budget = max(0, budget - min(len(text), take))
                    more = (
                        f"\n  [characters 0-{take} of {len(text)}; read the rest with read_course_file(file="
                        f'"{f["file"]}", start={take})]'
                        if len(text) > take
                        else ""
                    )
                    lines.append(f"{head}\n  file id: {f['file']}\n  ----- text -----\n{text[:take]}\n  -----{more}")
                elif f.get("path"):
                    lines.append(f"{head}\n  saved at {f['path']}: {f.get('note', '')}")
                else:
                    lines.append(f"{head}: {f.get('note', 'not read')}")
            if it.get("links"):
                lines.append("Links: " + " ".join(it["links"]))
        return "\n".join(x for x in lines if x is not None)

    def queue(self) -> int:
        """Hand every batch that isn't already with the AI to it (failed ones are tried again)."""
        n = 0
        with Lock(self.app.paths.state, "classroom-notes-queue"):
            pend = jload(self.dir / "queued.json", {}) or {}
            for b in sorted((self.dir / "batches").glob("*.json")):
                job = self.app.jobs.get(pend.get(b.name, "")) if pend.get(b.name) else None
                if job and job.status in ("queued", "running"):
                    continue
                data = jload(b, {}) or {}
                if not data.get("items"):
                    b.unlink(missing_ok=True)
                    continue
                pend[b.name] = run_skill(
                    self.app,
                    "classroom-digest",
                    self.render(data),
                    title=f"Classroom → notes: {data['course']}",
                    then="classroom_notes.filed",
                    payload={"batch": b.name},
                )
                n += 1
            jsave(self.dir / "queued.json", {k: v for k, v in pend.items() if (self.dir / "batches" / k).exists()})
        return n

    def _filed(self, job, result, payload) -> None:
        b = self.dir / "batches" / str(payload.get("batch", "x")).replace("/", "")
        data = jload(b, {}) or {}
        if not data:
            return
        if result.ok:
            b.unlink(missing_ok=True)
            n = len(data.get("items", []))
            self.app.notify(
                f"Classroom: filed {n} new item{'s' if n != 1 else ''} from {data['course']} into {data['folder']}/.",
                kind="result",
            )
            self.app.events.emit("classroom_notes_filed", items=n)
            return
        data["tries"] = data.get("tries", 0) + 1
        jsave(b, data)
        self.app.events.emit("classroom_notes_not_filed", tries=data["tries"])
        if data["tries"] == 3:
            self.app.notify(
                f"Classroom: the AI couldn't file the new posts from {data['course']} three times "
                f"({result.detail[:120] or result.verdict}). I'll keep trying at the next check.",
                kind="info",
            )

    # -------------------------------------------------------------------------------------------- tools
    def agent_tools(self):
        return [
            Tool(
                "read_course_file",
                "Read the text of a file Kurooto downloaded from Google Classroom, by its file id, from a character "
                "offset (15,000 characters at a time).",
                self._tool_read,
                {"file": arg("the file id from the batch"), "start": arg("character offset, default 0")},
                ("file",),
            ),
            Tool(
                "update_exam_prep",
                "Replace Kurooto's part of <subject>/exam-prep.md (between its markers) with the course's current "
                "exam prep, Markdown with these sections: ## Next assessment, ## Covered so far, ## Must know, "
                "## Typical questions, ## Gaps. Text the user wrote outside the markers is kept.",
                self._tool_exam_prep,
                {"subject": arg("the notes folder, e.g. linear-algebra"), "text": arg("the sections, Markdown")},
                ("subject", "text"),
                offline="queue",
            ),
        ]

    def _tool_read(self, a: dict):
        text = self.file_text(str(a.get("file", "")))
        if text is None:
            return "No such file (use a file id from the batch)."
        try:
            start = max(0, int(str(a.get("start") or 0)))
        except ValueError:
            start = 0
        part = text[start : start + 15000]
        return f"[characters {start}-{start + len(part)} of {len(text)}]\n{part}" if part else "Past the end."

    def _tool_exam_prep(self, a: dict):
        folder = str(a.get("subject", "")).strip().strip("/")
        course = next((c for c, f in (jload(self.dir / "folders.json", {}) or {}).items() if f == folder), folder)
        out = write_exam_prep(self.app.workspace, folder, str(a.get("text", "")), course, self.app.name)
        self.app.events.emit("exam_prep_updated")
        return out

    # ----------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command(
                "classnotes",
                "file new Classroom posts into your notes now (/classnotes courses, skip, unskip)",
                self._cmd,
                usage="/classnotes [courses | skip <words> | unskip <words>]",
            )
        ]

    def _cmd(self, msg: Incoming, arg_text: str) -> str:
        word, _, rest = arg_text.strip().partition(" ")
        word, rest = word.lower(), rest.strip()
        if word in ("skip", "unskip"):
            if not rest:
                return f"Usage: /classnotes {word} <words from the course's name>"
            skip = [w for w in self.setting("skip") or [] if w.lower() != rest.lower()]
            self.app.settings.set("classroom_notes.skip", [*skip, rest] if word == "skip" else skip)
            return f'Courses with "{rest}" in their name are {"left out" if word == "skip" else "filed again"}.'
        if word == "courses":
            if not self.allowed():
                return f"Not yet: {self.ready()[1]}."
            try:
                cs = list(
                    self.google.pages("classroom", "/courses", "courses", {"studentId": "me", "courseStates": "ACTIVE"})
                )
            except (NeedsSignIn, GoogleError) as e:
                return f"Couldn't read Classroom: {e}"
            rows = [
                f"{c.get('name')}: {'skipped' if self.skipped(c.get('name', '')) else self.folder(c.get('name', ''))}/"
                for c in cs
            ]
            return "\n".join(rows) or "No active courses."
        r = self.sync()
        if r.get("error"):
            return f"Couldn't check Classroom: {r['error']}"
        if r.get("skipped"):
            return f"Not now: {r['skipped']}."
        if not r.get("items"):
            return "Nothing new in Classroom." + (
                f" ({r['queued']} earlier batch(es) sent to the AI again.)" if r.get("queued") else ""
            )
        return f"Found {r['items']} new item(s) in {r['courses']} course(s); the AI is filing them into your notes now."

    def call_brief(self) -> dict:
        waiting = len(list((self.dir / "batches").glob("*.json")))
        return {"classroom_waiting_to_file": waiting} if waiting else {}
