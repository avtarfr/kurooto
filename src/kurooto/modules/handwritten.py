"""Handwritten notes: drop a PDF or a photo of handwritten pages into a folder (for example one your tablet's notes app
syncs to through Google Drive, OneDrive or Dropbox) and Kurooto writes it out as a Markdown note with the maths in
LaTeX, linked to the original (a copy next to the note or in your files folder, or the file where it is:
handwritten.keep_original). Send /handwritten to process the folder now; otherwise it looks every 15 minutes.

Who reads the pages:
    this computer   a model that reads pictures, through Local models: the vision model on 12 GB graphics cards, or
                    the helper model on 8 GB cards (gemma4:e4b reads handwriting too), or one you name
                    (handwritten.local_model). Photos are read right away. PDFs are read page by page at night on the
                    charger (handwritten.pdf_hours), each page saved as it's done, so unplugging or the morning only
                    pauses it: it carries on from the next page. It waits while the graphics card is busy with
                    something else. Drawing a tablet's PDF pages as pictures needs Poppler's PDF tools.
    Gemini          with no model here, your free Gemini key reads them (handwritten.cloud; off: they wait for a model
                    here instead).
The note keeps Kurooto's part between markers: when the original changes (you edited the page on your tablet), only
that part is written again; what you wrote around it stays.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

from kurooto.core import layout, proc
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock, Timeout
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module
from kurooto.modules.voice_notes import gemini_api

register_defaults(
    "handwritten",
    {
        "folder": "",  # where scans land; empty = handwritten-inbox in your notes (or in your files folder)
        "into": "",  # where the notes go, inside your notes folder; empty = your notes layout's (handwritten/)
        "every": "every 15m",
        "model": "gemini-flash-latest",
        "local": True,  # a model on this computer reads the pages when there is one (photos and PDFs)
        "local_model": "",  # an Ollama model of your choice that reads pictures; empty: Local models' pick
        "cloud": True,  # with no model here, Gemini (your key) reads them; False: they wait for a model here
        "pdf_hours": "23:00-07:00",  # when the model here reads PDFs (on the charger); "" any time
        "dpi": 110,  # how sharp the page pictures are
        "max_pages": 60,  # pages written out per PDF
        "keep_original": "copy",  # copy (next to the note, or in files.folder) | link (leave it where it is)
    },
)
KINDS = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
}
PROMPT = (
    "These are handwritten notes. Write them out as clean Markdown: keep the structure (headings, lists, numbered "
    "steps), write all mathematics in LaTeX ($…$ inline, $$…$$ for displays), and keep the original language. "
    "Describe any diagram in one line in italics. Where something can't be read, write [unclear]. Start with a "
    "'# ' title that says what the notes are about. Output only the Markdown."
)
PAGE_PROMPT = (
    "This is page {page} of handwritten notes. Transcribe it into Markdown: keep the author's structure and wording, "
    "write all mathematics in LaTeX ($…$ inline, $$…$$ for displays), keep the original language, and describe any "
    "diagram in one line in italics. Write [unclear] where you can't read something. Don't explain, summarise or add "
    "anything. Output only the Markdown."
)
START = "<!-- kurooto:handwritten"
END = "<!-- /kurooto:handwritten -->"
START_LINE = f"{START} (written out by Kurooto from the original; write your own notes outside these markers) -->"
TRIES = 5  # runs in a row the model here may fail to answer on a PDF before it's given up (and you're told)


class Waiting(Exception):
    """Not now (the night, a busy graphics card, Ollama not running, unplugged): tried again on a later scan."""


class Handwritten(Module):
    id = "handwritten"
    heavy = True  # waits for the charger on battery (saver mode, core/power.py)
    title = "Handwritten notes"
    description = (
        "Scans and photos of handwritten pages become Markdown notes (maths in LaTeX), linked to the original."
    )
    privacy = (
        "Pages are read by a model on this computer when there is one; otherwise they go to Google (Gemini, your "
        "free key), unless you turn that off (handwritten.cloud)."
    )

    def __init__(self, app):
        super().__init__(app)
        self._thread: threading.Thread | None = None
        self._halt = threading.Event()
        self.status = ""  # what it's doing now, for /handwritten status

    def folder(self) -> Path:
        f = self.setting("folder")
        old = self.app.workspace / "handwritten-inbox"  # a scan folder already in your notes keeps being used
        p = Path(f).expanduser() if f else old if old.is_dir() else layout.file_dir(self.app, "handwritten_inbox")
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ready(self):
        if self.local_model():
            return True, ""
        if not self.setting("cloud"):
            return False, "needs a model on this computer that reads pictures (Local models), or handwritten.cloud on"
        if not self.app.secrets.get("gemini.api_key"):
            return False, "needs your free Gemini key (AI brain → Gemini API key), or Local models on a graphics card"
        return True, ""

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        model = self.local_model()
        who = f"read on this computer by {model}" if model else "read by Gemini"
        return True, who + (f"; {self.status}" if self.status else "")

    def start(self):
        self.every("scan", self.setting("every") or "every 15m", lambda p: self.spawn())

    def stop(self):
        super().stop()  # its 15-minute scan with it
        self._halt.set()

    # ------------------------------------------------------------------------------------- engines
    def local_model(self) -> str | None:
        """The model on this computer that reads the pages: handwritten.local_model, else Local models' pick."""
        if not self.setting("local"):
            return None
        own = str(self.setting("local_model") or "").strip()
        if own:
            return own
        if not self.app.is_on("local_models"):
            return None
        lm = self.app.modules.get("local_models")
        m = lm.vision_model() if lm is not None else None
        return m["tag"] if m else None

    _local_model = local_model  # its name before 0.4.0

    def _model_gb(self, model: str) -> float:
        lm = self.app.modules.get("local_models")
        for m in lm.wanted() if lm is not None else []:
            if m.get("tag") == model:
                return float(m.get("size_gb") or 0)
        return 0.0

    def gpu_room(self, model: str) -> None:
        """Raise Waiting unless the model can run now: Ollama is up, and the model is loaded already or the graphics
        card has room for it (it's never loaded while something else, say a training run, fills the card)."""
        lm = self.app.modules["local_models"]
        try:
            with lm.api("/api/ps", timeout=5) as r:
                loaded = {str(m.get("name") or m.get("model")) for m in json.loads(r.read()).get("models", [])}
        except (OSError, ValueError):
            raise Waiting("Ollama isn't running") from None
        if model in loaded or f"{model}:latest" in loaded:
            return
        smi = proc.which("nvidia-smi")
        if not smi:
            return  # no NVIDIA tools: Ollama decides
        r = proc.run([smi, "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"], timeout=10)
        try:
            used, total = (int(float(x)) for x in r.out.strip().splitlines()[0].split(","))
        except (ValueError, IndexError):
            return
        need = int((self._model_gb(model) or 6.5) * 1024) + 300
        if total - used < need:
            raise Waiting(f"the graphics card is busy ({used} of {total} MiB in use)")

    def _gemini(self, data: bytes, mime: str) -> str:
        key = self.app.secrets.get("gemini.api_key")
        if not key:
            raise RuntimeError("no Gemini key")
        model = self.setting("model") or "gemini-flash-latest"
        pool, quota = f"gemini:{model}", self.app.quota
        if quota.wait_until(pool) is not None:  # background work: Google's free limit is kept for you until the reset
            raise Waiting("Google's free limit is kept for your own requests until it resets")
        body = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}},
                        {"text": PROMPT},
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.1},
        }
        req = urllib.request.Request(  # noqa: S310 (Google's API, https)
            f"{gemini_api(self.app)}/models/{model}:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310
                out = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:  # a limit: it waits and is tried again later, not written off
                quota.record(pool, "rate_limited", e.read().decode("utf-8", "replace"), e.headers.get("Retry-After"))
                raise Waiting(f"Gemini said {e.code}") from None
            raise RuntimeError(f"Gemini said {e.code}") from None
        quota.record(pool)
        parts = ((out.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts).strip()

    def _ollama(self, model: str, data: bytes, prompt: str = PROMPT) -> str:
        lm = self.app.modules["local_models"]
        body = {
            "model": model,
            "prompt": prompt,
            "images": [base64.b64encode(data).decode()],
            "stream": False,
            "think": False,
            "options": {"temperature": 0},
        }
        with lm.api("/api/generate", body, timeout=900) as r:
            return _tidy(json.loads(r.read()).get("response", ""))

    def _cloud_ok(self) -> bool:
        return bool(self.setting("cloud") and self.app.secrets.get("gemini.api_key"))

    def write_out(self, f: Path) -> str:
        """A photo (by the model here, or Gemini), or a whole PDF by Gemini: Markdown starting with a '# ' title."""
        mime = KINDS[f.suffix.lower()]
        data = f.read_bytes()
        local = self.local_model()
        if local and mime.startswith("image/") and mime != "image/heic":
            self.gpu_room(local)
            try:
                return self._ollama(local, data, PROMPT)
            except OSError as e:
                raise Waiting(f"the model here didn't answer ({e})") from None
        if not self._cloud_ok():
            raise RuntimeError(
                "nothing here can read it (HEIC photos need Gemini: handwritten.cloud)"
                if local
                else "needs a model on this computer that reads pictures (Local models), or Gemini (handwritten.cloud)"
            )
        if len(data) > 18 * 1024 * 1024:
            raise RuntimeError("over 18 MB; split it into smaller files")
        return self._gemini(data, mime)

    # ---------------------------------------------------------------------------- PDFs, page by page
    def pdf_tools(self) -> dict[str, str | None]:
        """Poppler's programs where this computer has them (as Books finds them)."""
        from kurooto.modules.books import Books

        books = self.app.modules.get("books") or Books(self.app)
        return books.tools()

    def _doc(self, f: Path):
        from kurooto.modules.books import Doc

        return Doc(f, self.pdf_tools(), self.app.paths.cache / "handwritten")

    @staticmethod
    def drawable(doc) -> bool:
        """Can this PDF's pages be drawn as pictures here? Poppler draws any page; without it, only scanned pages
        (a picture stored in the page) can be."""
        if not doc.pages():
            return False
        return bool(doc.tools.get("pdftoppm")) or bool(doc.images(1))

    def _hours(self) -> tuple[dt.time, dt.time] | None:
        m = re.fullmatch(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", str(self.setting("pdf_hours") or "").strip())
        return (dt.time(int(m[1]), int(m[2])), dt.time(int(m[3]), int(m[4]))) if m else None

    def in_hours(self, t: dt.datetime | None = None) -> bool:
        """Is it time for the model here to read PDFs (handwritten.pdf_hours)?"""
        h = self._hours()
        if h is None:
            return True
        a, b = h
        cur = (t or now()).time()
        return a <= cur < b if a < b else cur >= a or cur < b

    def hours_end(self, t: dt.datetime | None = None) -> dt.datetime | None:
        h = self._hours()
        if h is None:
            return None
        cur = t or now()
        end = cur.replace(hour=h[1].hour, minute=h[1].minute, second=0, microsecond=0)
        return end if end > cur else end + dt.timedelta(days=1)

    def _stop_now(self, until: dt.datetime | None) -> str | None:
        if self._halt.is_set():
            return "stopped"
        if not self.app.is_on(self.id) and self.app.modules.get(self.id) is self:
            return "turned off"
        if not self.app.power.may_run(self):
            return "on battery"
        if until is not None and now() >= until:
            return "morning"
        return None

    def _cache(self, name: str) -> Path:
        h = hashlib.sha1(name.encode()).hexdigest()[:10]  # noqa: S324 (a folder name, not security)
        return self.app.paths.state / "handwritten" / f"{_slug(Path(name).stem, 40)}-{h}"

    def read_pdf(self, f: Path, sig: str, model: str, until: dt.datetime | None = None) -> tuple[str, int]:
        """Each page by the model here, saved as it's done: (Markdown, pages). Waiting when it has to stop."""
        d = self._cache(f.name)
        meta = jload(d / "meta.json", {}) or {}
        if meta.get("sig") != sig:  # new, or changed since: start over
            shutil.rmtree(d / "pages", ignore_errors=True)
            meta = {"sig": sig, "tries": 0}
        doc = self._doc(f)
        total = doc.pages()
        if not total:
            raise RuntimeError("this PDF can't be read here (encrypted or unusual; Poppler's PDF tools read more)")
        n_max = min(total, int(self.setting("max_pages") or 60))
        pages = d / "pages"
        pages.mkdir(parents=True, exist_ok=True)
        dpi = int(self.setting("dpi") or 110)
        try:
            for n in range(1, n_max + 1):
                pf = pages / f"{n:05d}.md"
                if pf.exists():
                    continue
                stop = self._stop_now(until)
                if stop:
                    raise Waiting(f"{stop}: {f.name} is at page {n} of {n_max}")
                self.status = f"writing out {f.name}: page {n} of {n_max}"
                pic = doc.picture(n, dpi)
                if not pic or pic[1] not in ("image/png", "image/jpeg"):
                    raise RuntimeError(f"page {n} can't be drawn as a picture here (Poppler's PDF tools draw any page)")
                try:
                    text = self._ollama(model, pic[0], PAGE_PROMPT.format(page=n))
                except OSError as e:  # busy, timed out, Ollama gone: this page again next time
                    meta["tries"] = int(meta.get("tries") or 0) + 1
                    if meta["tries"] >= TRIES:
                        raise RuntimeError(f"the model here kept failing on page {n} ({e})") from None
                    raise Waiting(f"the model here didn't answer on page {n} ({e})") from None
                tmp = pf.with_suffix(".tmp")
                tmp.write_text(text.strip() + "\n", encoding="utf-8")
                os.replace(tmp, pf)
                meta["tries"] = 0
        finally:
            self.status = ""
            jsave(d / "meta.json", meta)
        texts = [(n, (pages / f"{n:05d}.md").read_text(encoding="utf-8").strip()) for n in range(1, n_max + 1)]
        md = texts[0][1] if n_max == 1 else "\n\n".join(f"## Page {n}\n\n{t or '(blank)'}" for n, t in texts)
        if total > n_max:
            md += f"\n\n(The first {n_max} of {total} pages: handwritten.max_pages.)"
        return md, n_max

    # --------------------------------------------------------------------------------------- work
    def _one(self, f: Path, sig: str, force: bool, until: dt.datetime | None) -> str:
        """Write out one file; the note (as shown). Raises Waiting to be tried again later."""
        mime = KINDS[f.suffix.lower()]
        model = self.local_model()
        if mime == "application/pdf" and model:
            doc = self._doc(f)
            if self.drawable(doc):
                if not force and not self.in_hours():
                    self._tell_waiting(f, doc.pages())
                    raise Waiting("waiting for the night")
                self.gpu_room(model)
                md, n = self.read_pdf(f, sig, model, until)
                note = self._file(f, md, title=_title(f), how=f"by {model} on this computer, {_pages(n)}, unchecked")
                shutil.rmtree(self._cache(f.name), ignore_errors=True)
                return note
            if not self._cloud_ok():
                raise RuntimeError(
                    "its pages can't be drawn as pictures here: install Poppler's PDF tools (or turn on "
                    "handwritten.cloud for Gemini)"
                )
        md = self.write_out(f)
        if not md:
            raise RuntimeError("nothing could be read")
        how = f"by {model} on this computer, unchecked" if model and mime != "application/pdf" else "by Gemini"
        return self._file(f, md, how=how)

    def scan(self, force: bool = False, until: dt.datetime | None = None) -> list[str]:
        """Write out what's new in the folder. `force`: PDFs too outside handwritten.pdf_hours (/handwritten)."""
        lock = Lock(self.app.paths.state, "handwritten", timeout=5)
        try:
            lock.acquire()
        except Timeout:
            return []
        done = []
        try:
            seen_file = self.app.paths.state / "handwritten.json"
            failed_file = self.app.paths.state / "handwritten-failed.json"
            seen = jload(seen_file, {}) or {}
            failed = jload(failed_file, {}) or {}
            for f in sorted(self.folder().iterdir()):
                if not f.is_file() or f.suffix.lower() not in KINDS or f.name.startswith("."):
                    continue
                st = f.stat()
                sig = f"{st.st_size}:{int(st.st_mtime)}"
                if seen.get(f.name) == sig or now().timestamp() - st.st_mtime < 20:  # still being copied in
                    continue
                if self._stop_now(until) in ("stopped", "turned off"):
                    break
                try:
                    rel = self._one(f, sig, force, until)
                except Waiting:
                    continue
                except Exception as e:
                    seen[f.name] = sig  # don't retry a failing file every 15 minutes; it's retried if it changes
                    failed[f.name] = str(e)[:200]
                    self.app.notify(
                        f"Couldn't write out {f.name}: {e}"[:300], kind="info", why="handwritten.failed", about=f.name
                    )
                    self.app.events.emit("handwritten_failed", error=str(e)[:200])
                    continue
                seen[f.name] = sig
                failed.pop(f.name, None)
                done.append(rel)
                self.app.events.emit("handwritten_done")
                jsave(seen_file, dict(list(seen.items())[-2000:]))
            jsave(seen_file, dict(list(seen.items())[-2000:]))
            jsave(failed_file, failed)
        finally:
            lock.release()
        if done:
            self.app.notify("Written out: " + ", ".join(done), kind="result", why="handwritten.done")
        return done

    def spawn(self, force: bool = False) -> bool:
        """Scan in the background (a PDF read here can take hours), once at a time."""
        if self._thread is not None and self._thread.is_alive():
            return False
        self._halt.clear()
        until = None if force or not self.in_hours() else self.hours_end()
        self._thread = threading.Thread(target=self.scan, args=(force, until), name="handwritten", daemon=True)
        self._thread.start()
        return True

    def _tell_waiting(self, f: Path, pages: int) -> None:
        """Once per version of a PDF: it'll be written out at night."""
        told_file = self.app.paths.state / "handwritten-told.json"
        told = jload(told_file, {}) or {}
        st = f.stat()
        key = f"{st.st_size}:{int(st.st_mtime)}"
        if told.get(f.name) == key:
            return
        told[f.name] = key
        jsave(told_file, dict(list(told.items())[-500:]))
        self.app.notify(
            f"Got {f.name} ({_pages(pages)}). I'll write it out with the model on this computer at night "
            f"({self.setting('pdf_hours')}, on the charger); /handwritten starts it now.",
            kind="info",
            why="handwritten.got",
            about=f.name,
        )

    # --------------------------------------------------------------------------------------- the note
    def _file(self, src: Path, md: str, title: str = "", how: str = "") -> str:
        """The note for this original: a new one, or (the original changed) the same one with Kurooto's part
        written again and yours kept."""
        m = re.match(r"\A\s*# (.+)\n?", md)
        body = md[m.end() :].strip() if m else md.strip()
        title = (m.group(1).strip() if m else "") or title or _title(src)
        notes_file = self.app.paths.state / "handwritten-notes.json"
        known = jload(notes_file, {}) or {}
        prev = known.get(src.name) or {}
        note = Path(prev["note"]) if prev.get("note") else None
        if note is None or not note.exists():
            into = self.setting("into")
            folder = self.app.workspace / into if into else layout.path(self.app, "handwritten")
            base = folder / f"{now():%Y-%m-%d}-{_slug(title)}"
            files = layout.file_dir(self.app, "handwritten")
            files = folder if files == layout.path(self.app, "handwritten") else files  # "next to the note"
            n = 1
            while base.with_suffix(".md").exists() or (files / f"{base.name}{src.suffix.lower()}").exists():
                n += 1
                base = base.with_name(f"{base.name.rsplit('~', 1)[0]}~{n}")
            note = base.with_suffix(".md")
            copy = files / f"{base.name}{src.suffix.lower()}"
        else:
            copy = Path(prev.get("copy") or note.with_suffix(src.suffix.lower()))
        note.parent.mkdir(parents=True, exist_ok=True)
        if str(self.setting("keep_original") or "copy").lower() == "link":
            original, kept = src, ""
        else:
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, copy)
            original, kept = copy, str(copy)
        link = layout.file_link(self.app, original, note).removeprefix("!")
        block = f"{body}\n\n---\nOriginal: {link} · written out {now():%Y-%m-%d %H:%M}" + (f" {how}" if how else "")
        old = note.read_text(encoding="utf-8", errors="replace") if note.exists() else None
        head = layout.frontmatter(self.app, "handwritten", note, title=title, bare=True) + f"# {title}\n\n"
        note.write_text(put_block(old, block, head), encoding="utf-8")
        known[src.name] = {"note": str(note), "copy": kept}
        jsave(notes_file, dict(list(known.items())[-2000:]))
        return layout.shown(self.app, note)

    # ------------------------------------------------------------------------------------- telegram
    def commands(self):
        return [
            Command(
                "handwritten",
                "write out the handwritten pages waiting in the folder now (/handwritten status, /handwritten retry)",
                self._cmd,
            )
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        a = arg.strip().lower()
        failed_file = self.app.paths.state / "handwritten-failed.json"
        if a == "status":
            busy = self._thread is not None and self._thread.is_alive()
            failed = jload(failed_file, {}) or {}
            lines = [self.status or ("Working on the folder." if busy else "Nothing going on.")]
            lines += [f"Couldn't: {k} ({v})" for k, v in list(failed.items())[:5]]
            return "\n".join(lines)
        if a == "retry":  # files that failed get another go
            failed = jload(failed_file, {}) or {}
            seen = jload(self.app.paths.state / "handwritten.json", {}) or {}
            jsave(self.app.paths.state / "handwritten.json", {k: v for k, v in seen.items() if k not in failed})
            jsave(failed_file, {})
        if self.local_model() and any(p.suffix.lower() == ".pdf" for p in self.folder().iterdir()):
            if not self.spawn(force=True):
                return f"Already at it: {self.status or 'working on the folder'}."
            return "Writing out what's waiting with the model on this computer; you'll get a message when it's done."
        done = self.scan(force=True)
        return f"Done: {len(done)} written out." if done else f"Nothing new in {self.folder()}."


def put_block(old: str | None, block: str, head: str) -> str:
    """Kurooto's part of the note between its markers; what you wrote around it stays."""
    block = f"{START_LINE}\n{block.strip()}\n{END}"
    if old:
        i = old.find(START)
        j = old.find(END, i + 1) if i >= 0 else -1
        if i >= 0 and j > i:
            return old[:i] + block + old[j + len(END) :]
        return old.rstrip("\n") + "\n\n" + block + "\n"
    return head + block + "\n"


def _slug(text: str, n: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:n].strip("-") or "notes"


def _title(f: Path) -> str:
    """A title from the file's name ("lecture_07-eigenvalues.pdf" -> "Lecture 07 eigenvalues")."""
    t = re.sub(r"\s+", " ", re.sub(r"_+|(?<=\w)-(?=\w)", " ", f.stem)).strip()
    return (t[:1].upper() + t[1:]) if t else "Handwritten notes"


def _pages(n: int) -> str:
    return f"{n} page" if n == 1 else f"{n} pages"


def _tidy(text: str) -> str:
    """A model's answer without a Markdown fence around it."""
    t = (text or "").strip()
    m = re.fullmatch(r"```(?:markdown|md)?\s*\n(.*)\n```", t, re.S)
    return (m[1] if m else t).strip()
