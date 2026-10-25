"""Books and PDFs: your reference books and other PDFs, per subject, read overnight into text your AI can use when it
writes your notes.

Add a book in one of three ways:
    Telegram    send the PDF with a caption like "book for linear algebra" (Telegram lets bots fetch up to 20 MB)
    dashboard   Features → Books and PDFs: the PDF's place on this computer and its subject (the first book)
    a folder    drop it in the subject's books folder (/books folder says where; outside your notes)

At night, on the charger, Kurooto reads each new book page by page and picks the best way for each page:
    text        the PDF's own text (Poppler's pdftotext when it's installed, else Kurooto's built-in reader)
    tesseract   scanned pages, with Tesseract OCR if it's installed: plain text, so equations come out garbled
    vision      a vision model on this computer (Local models, graphics cards from 8 GB): the maths in
                LaTeX. Pages full of maths go to it even when they have text (books.latex)
    gemini      Google's Gemini with your free key, only if you turn on books.gemini: page pictures go to Google
It stops at 07:00 or when you unplug, and carries on the next night from the page where it stopped.

What it makes: the text with page markers in Kurooto's data folder (outside your notes), and an index note in your
notes, <subject>/books/<book>.md, with the chapters and their pages. With the Notes brain on, the text is indexed too.
Skills that write course notes then draw on books, Classroom materials and your own notes in the mix you choose
(core/sources.py), and cite pages.

    /books                      your books per subject, and how far the reading got
    /books read now             start reading now (on the charger)
    /books stop                 stop reading for now
    /books folder [subject]     where to drop books
    /books mix <subject> book 30 classroom 30 own 40     (or: prefer own book classroom; or: reset)
    /books setup                install Tesseract, for scanned pages
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from kurooto.core import egress, layout, proc, sources
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock, Timeout
from kurooto.core.pdfread import Pdf, PdfError, text_string
from kurooto.core.prereqs import Prereqs
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module
from kurooto.modules.calls.tools import Tool, arg, clip

register_defaults(
    "books",
    {
        "folder": "",  # your own folder for books, a subfolder per subject; empty: files.folder, else Kurooto's
        "at": "daily 01:00",  # when the night's reading starts
        "until": "07:00",  # when it stops (it carries on the next night)
        "ocr": "auto",  # who reads scanned pages: auto (Tesseract, else the vision model) | tesseract | vision | off
        "ocr_lang": "eng",  # Tesseract's languages, e.g. "eng+deu" (each needs its language data installed)
        "latex": "maths",  # vision reads for LaTeX: maths (pages whose maths came out in pieces) | all | never
        "gemini": False,  # True: pages nothing on this computer can read go to Gemini (your key) as pictures
        "gemini_model": "gemini-flash-latest",
        "dpi": 200,  # how sharp the page pictures are for OCR
        "brain": True,  # index the text into the notes brain when it's on
        "brain_source": "",  # an existing gbrain source (`gbrain sources list`) for the chunks; "" = the default one
        "after_read": [],  # your command, run after each book is read, with its subject and id added: ["prog", "-x"]
        "duplicates": True,  # a book that is a copy of one already read (the same file) is linked to it, not read again
        "max_mb": 400,  # bigger files are left alone
    },
)
ORDER = {  # who reads a scanned page, in order, per books.ocr
    "auto": ("tesseract", "vision", "gemini"),
    "tesseract": ("tesseract", "gemini"),
    "vision": ("vision", "gemini"),
    "gemini": ("gemini",),
    "off": (),
}
ROUTES = ("text", "tesseract", "vision", "gemini", "blank")
SAID = {"text": "text layer", "tesseract": "Tesseract", "vision": "vision model", "gemini": "Gemini", "blank": "blank"}
MATHS = re.compile(
    r"[=+−×÷∑∏∫∮∂√∞≤≥≠≈≡∈∉⊂⊆⊃∪∩∀∃∇→↦⇒⇔⊗⊕∘αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ^_]|"
    r"\b(?:lim|sup|inf|det|ker|dim|log|sin|cos|exp)\b"
)
CAPTION = re.compile(
    r"^\s*(?:(?:a|the|my|this|our|reference|text|course)\s+)*(?:book|textbook|reference)s?\s*"
    r"(?:for|in|on|of|:|-|–)\s*(?P<a>.+?)\s*[.!]*$|^\s*(?P<b>.+?)\s+(?:text)?books?\s*[.!]*$",
    re.I,
)
PAGE_PROMPT = (
    "This is page {page} of a book. Transcribe it as Markdown, exactly: keep headings, lists, numbered equations and "
    "theorem labels; write all mathematics in LaTeX ($…$ inline, $$…$$ for displays); describe each figure in one "
    "line in italics; write [unclear] where you can't read something. Don't add, explain or summarise anything. "
    "Output only the Markdown."
)
BRAIN_PAGES = 20  # pages per notes-brain page
START = "<!-- kurooto:book"
END = "<!-- /kurooto:book -->"
START_LINE = f"{START} (kept current by Kurooto from the book; write your own notes outside these markers) -->"
CHAPTER = re.compile(r"^\s*(chapter|part|unit|lecture|section)\s+([0-9]+|[ivxlc]+)\b[.:]?\s*(.{0,80})$", re.I)


def slug(text: str, n: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:n].strip("-") or "book"


def npages(n: int) -> str:
    return f"{n} page" if n == 1 else f"{n} pages"


def usable(text: str | None) -> bool:
    """Is this a real text layer? Enough letters, and few characters that didn't decode."""
    t = (text or "").strip()
    if not t:
        return False
    letters = sum(c.isalnum() for c in t)
    bad = sum(c == "�" or (ord(c) < 32 and c not in "\n\t\r") or 0xE000 <= ord(c) <= 0xF8FF for c in t)
    return letters >= 15 and bad <= 0.05 * len(t)


def mathy(text: str | None) -> bool:
    """A page full of maths (worth reading with the vision model, for LaTeX)."""
    t = text or ""
    hits = len(MATHS.findall(t))
    return hits >= 8 and hits >= 0.04 * max(1, len(t.split()))


def garbled(text: str | None) -> bool:
    """Has the page's maths come out of the text layer in pieces (equations as scattered one- and two-character
    lines, lone symbols)? Only those pages are worth a vision model's time: when the text layer carries the maths
    well, reading the page again as a picture changes little and costs seconds per page."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) < 8:
        return False
    tiny = sum(1 for ln in lines if len(ln) <= 3)
    return tiny >= 0.3 * len(lines)


def route(text: str | None, images: bool | None, engines: set[str], ocr: str = "auto", latex: str = "maths"):
    """How to read one page, best first: "text" (its text layer), "blank", or a reader of page pictures
    ("tesseract", "vision", "gemini"). `images`: whether the page has pictures (None: unknown)."""
    readers = [e for e in ORDER.get(ocr, ORDER["auto"]) if e in engines]
    if usable(text):
        if "vision" in readers and (latex == "all" or (latex == "maths" and mathy(text) and garbled(text))):
            return ["vision", "text"]
        return ["text"]
    has_text = bool((text or "").strip())
    if images is False:  # nothing to read but the (short) text: a chapter title, or an empty page
        return ["text"] if has_text else ["blank"]
    return readers + (["text"] if has_text else [])


# --------------------------------------------------------------------------------------------- one PDF
class Doc:
    """A PDF as Books reads it: Poppler when it's installed, the built-in reader otherwise (and for what Poppler
    doesn't tell: bookmarks, which pages have pictures)."""

    def __init__(self, path: Path, tools: dict[str, str | None], cache: Path):
        self.path, self.tools, self.cache = Path(path), tools, cache
        self.pdf: Pdf | None = None
        try:
            pdf = Pdf(self.path)
            self.pdf = None if pdf.encrypted or not pdf.page_count() else pdf  # Poppler reads those, if it's here
        except (PdfError, OSError, ValueError, RecursionError):
            self.pdf = None
        self._n: int | None = None

    def pages(self) -> int:
        if self._n is None:
            n = self.pdf.page_count() if self.pdf else 0
            if not n and self.tools.get("pdfinfo"):
                r = proc.run([self.tools["pdfinfo"], str(self.path)], timeout=60)
                m = re.search(r"^Pages:\s+(\d+)", r.out, re.M)
                n = int(m[1]) if m else 0
            self._n = n
        return self._n

    def title(self) -> str:
        if self.pdf:
            info = self.pdf.get(self.pdf.trailer.get("Info"))
            t = text_string(self.pdf.get(info.get("Title"))) if isinstance(info, dict) else ""
            t = re.sub(r"\s+", " ", t).strip()
            if 3 <= len(t) <= 160 and not re.fullmatch(r"(untitled|microsoft word.*|.*\.(pdf|docx?|tex|dvi))", t, re.I):
                return t
        stem = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{6}-", "", self.path.stem)  # Telegram's time stamp
        return re.sub(r"[_-]+", " ", stem).strip().title() or "A book"

    def text(self, n: int) -> str:
        if self.tools.get("pdftotext"):
            r = proc.run([self.tools["pdftotext"], "-f", str(n), "-l", str(n), str(self.path), "-"], timeout=120)
            if r.ok:
                return r.out.replace("\x0c", "").strip()
        if self.pdf:
            try:
                return self.pdf.page_text(n)
            except (PdfError, ValueError, IndexError, RecursionError):
                return ""
        return ""

    def images(self, n: int) -> bool | None:
        if not self.pdf:
            return None
        try:
            return self.pdf.has_images(n)
        except (PdfError, ValueError, IndexError, RecursionError):
            return None

    def picture(self, n: int, dpi: int = 200) -> tuple[bytes, str] | None:
        """The page as a picture: drawn by Poppler, else the scan stored in the page."""
        if self.tools.get("pdftoppm"):
            self.cache.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.cache) as d:
                out = Path(d) / "page"
                r = proc.run(
                    [self.tools["pdftoppm"], "-f", str(n), "-l", str(n), "-r", str(dpi), "-png", "-singlefile"]
                    + [str(self.path), str(out)],
                    timeout=300,
                )
                f = out.with_suffix(".png")
                if r.ok and f.is_file():
                    return f.read_bytes(), "image/png"
        if self.pdf:
            try:
                return self.pdf.page_image(n)
            except (PdfError, ValueError, IndexError, RecursionError):
                return None
        return None

    def outline(self) -> list[tuple[int, str, int | None]]:
        if not self.pdf:
            return []
        try:
            return self.pdf.outline()
        except (PdfError, ValueError, IndexError, RecursionError):
            return []


def chapters(outline: list[tuple[int, str, int | None]], pages: dict[int, str], total: int, depth: int = 2):
    """[(level, title, first page, last page)]: from the bookmarks, else from numbered headings and running headers,
    else from "Chapter 3 ..." lines (core/segment.py: a margin note like "Section 9.1" is never a heading)."""
    from kurooto.core import segment

    secs = segment.sections(pages, outline, total)
    out = [
        (
            s.level,
            f"{s.number} {s.title}".strip() if s.number and not s.title.startswith(s.number) else s.title,
            s.first,
            s.last,
        )
        for s in secs
        if s.level <= depth
    ]
    return out[:300]


def put_block(old: str | None, block: str, head: str) -> str:
    """Kurooto's part of an index note between its markers; what you wrote around it stays."""
    block = f"{START_LINE}\n{block.strip()}\n{END}"
    if old:
        i = old.find(START)
        j = old.find(END, i + 1) if i >= 0 else -1
        if i >= 0 and j > i:
            return old[:i] + block + old[j + len(END) :]
        return old.rstrip("\n") + "\n\n" + block + "\n"
    return head + block + "\n"


INSTALL_POPPLER = (
    "Arch: sudo pacman -S poppler; Debian or Ubuntu: sudo apt install poppler-utils; "
    "Fedora: sudo dnf install poppler-utils; macOS: brew install poppler"
)
IMAGES = {
    b"\xff\xd8\xff": "a JPEG photo",
    b"\x89PNG": "a PNG image",
    b"GIF8": "a GIF image",
    b"RIFF": "a WebP image or a media file",
}


def unreadable_why(path: Path, tools: dict) -> str:
    """Why a book gave no pages, said truthfully: not a PDF at all (by its first bytes), Poppler really missing,
    or a PDF that's encrypted or damaged."""
    try:
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError:
        return "the file can't be opened"
    if not head.lstrip().startswith(b"%PDF"):
        what = next((v for k, v in IMAGES.items() if head.startswith(k)), "not a PDF")
        return (
            f"this isn't a PDF: it's {what} named {path.suffix or 'without an extension'}. "
            "Rename it, or let the vision model or OCR read it"
        )
    if not any(tools.values()):
        return (
            f"Poppler isn't installed on this computer (install it: {INSTALL_POPPLER}), "
            "and the built-in reader couldn't read this PDF"
        )
    return "this PDF is encrypted or damaged, so it can't be read (Poppler is installed)"


class Books(Module):
    id = "books"
    title = "Books and PDFs"
    description = (
        "Reference books and PDFs per subject, read at night on the charger (text, or OCR for scanned pages), "
        "indexed in your notes and used, in the mix you choose, when the AI writes your course notes."
    )
    privacy = (
        "Books stay on this computer: their text is read here (the PDF's text, Tesseract, or a local vision "
        "model). Only if you turn on books.gemini do pictures of pages nothing here could read go to Google. "
        "Excerpts go to the AI you picked when it writes your notes."
    )
    heavy = True  # reads at night; on battery it waits for the charger

    def __init__(self, app):
        super().__init__(app)
        self.prereqs = Prereqs(app.paths.app, app.paths.cache)
        self._thread: threading.Thread | None = None
        self._halt = threading.Event()
        self._force = False
        self.status = ""  # what the reader is doing now, for /books

    # ------------------------------------------------------------------------------------------- places
    @property
    def store(self) -> Path:
        """The text of every book (with page markers), outside the notes."""
        return self.app.paths.data / "book-text"

    @property
    def brain_dir(self) -> Path:
        return self.app.paths.data / "book-brain"

    def roots(self) -> list[tuple[Path, str]]:
        """Where books are, as (folder, pattern): pattern "*" means one folder per subject in it, "*/books" a books
        folder inside each subject's folder."""
        own = str(self.setting("folder") or "").strip()
        if own:
            p = Path(os.path.expanduser(own))
            return [(p if p.is_absolute() else Path.home() / p, "*")]
        files = layout.files_root(self.app)
        if files is not None and not layout.of(self.app).inside_notes(files):
            return [(files, "*/books")]
        return [(self.app.paths.data / "books", "*")]

    def folder(self, subject: str) -> Path:
        root, pattern = self.roots()[0]
        s = slug(subject, 80)
        if pattern == "*/books":
            return root / s / "books"
        if root.is_dir():
            for p in root.iterdir():
                if p.is_dir() and not p.name.startswith("."):
                    if self.subject_of(p.name) == s or slug(p.name, 80) == s:
                        return p
        return root / s

    def library(self) -> list[dict]:
        """Every book: {"subject", "path", "id"} across all subdirectories."""
        out = []
        known: dict[str, str | None] = {}  # each folder name's subject, once a listing (0.6.1: a dashboard request)

        def subject_of(text: str) -> str | None:
            if text not in known:
                known[text] = self.subject_of(text)
            return known[text]

        for root, pattern in self.roots():
            if not root.is_dir():
                continue
            for sub in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
                d = sub / "books" if pattern == "*/books" else sub
                if not d.is_dir():
                    continue
                default_subj = subject_of(sub.name) or slug(sub.name, 80)
                for f in sorted(x for x in d.rglob("*") if x.suffix.lower() == ".pdf"):
                    if f.is_file() and not any(part.startswith(".") for part in f.relative_to(d).parts):
                        rel_parts = f.relative_to(d).parts[:-1]
                        subj = default_subj
                        sub_matched = False
                        if rel_parts:
                            for idx, part in enumerate(rel_parts):
                                s = subject_of(part)
                                if s and s != slug(part, 80):
                                    subj = s
                                    rem = rel_parts[idx + 1 :]
                                    stem = f.stem
                                    bid = (
                                        "-".join([slug(p, 80) for p in rem] + [slug(stem, 80)])
                                        if rem
                                        else slug(stem, 80)
                                    )
                                    sub_matched = True
                                    break
                        if not sub_matched:
                            rel = f.relative_to(d).with_suffix("")
                            bid = slug(str(rel)) if rel.parent != Path(".") else slug(f.stem)
                        out.append({"subject": subj, "path": f, "id": bid})
            for f in sorted(x for x in root.glob("*") if x.suffix.lower() == ".pdf"):
                if f.is_file() and not f.name.startswith("."):
                    subj = subject_of(f.stem) or "books"
                    out.append({"subject": subj, "path": f, "id": slug(f.stem)})
        return out

    def subject_of(self, text: str) -> str | None:
        subj = self.app.modules.get("subjects")
        if subj is not None and self.app.is_on("subjects"):
            hit = subj.resolve(text) or next(iter(subj.find_in(text)), None)
            if hit:
                return hit
        s = slug(text, 80)
        return s if s != "book" else None

    # ------------------------------------------------------------------------------------------ engines
    def tools(self) -> dict[str, str | None]:
        """Poppler's programs, where this computer has them."""
        hit = self.prereqs.items["poppler"].find() if "poppler" in self.prereqs.items else None
        d = Path(hit).parent if hit else None
        out = {}
        for name in ("pdftotext", "pdftoppm", "pdfinfo"):
            exe = None
            if d is not None:
                exe = next((str(d / n) for n in (name, f"{name}.exe") if (d / n).is_file()), None)
            out[name] = exe or shutil.which(name)
        return out

    def tesseract(self) -> str | None:
        return self.prereqs.items["tesseract"].find() if "tesseract" in self.prereqs.items else None

    def vision_model(self) -> str | None:
        """The local model that reads pages: the vision model (12 GB cards), else a helper that sees pictures too."""
        lm = self.app.modules.get("local_models")
        if lm is None or not self.app.is_on("local_models"):
            return None
        hit = lm.vision_model()
        return hit.get("tag") if hit else None

    def engines(self) -> set[str]:
        out = {"text"}
        if self.tesseract():
            out.add("tesseract")
        if self.vision_model():
            out.add("vision")
        if self.setting("gemini") and self.app.secrets.get("gemini.api_key"):
            out.add("gemini")
        return out

    def read_picture(self, engine: str, img: bytes, mime: str, page: int) -> str:
        """Text from a page picture, by one reader."""
        if engine == "tesseract":
            exe = self.tesseract()
            if not exe:
                raise RuntimeError("Tesseract isn't installed")
            ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/tiff": ".tif"}.get(mime, ".png")
            self.app.paths.cache.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.app.paths.cache) as d:
                f = Path(d) / f"page{ext}"
                f.write_bytes(img)
                r = proc.run([exe, str(f), "stdout", "-l", self.setting("ocr_lang") or "eng"], timeout=600)
            if not r.ok:
                raise RuntimeError(f"Tesseract: {(r.err or 'failed').strip()[-160:]}")
            return r.out
        if mime not in ("image/png", "image/jpeg"):
            raise RuntimeError("this page's picture needs Poppler to be drawn for the vision model")
        prompt = PAGE_PROMPT.format(page=page)
        if engine == "vision":
            model = self.vision_model()
            if not model:
                raise RuntimeError("no vision model on this computer")
            lm = self.app.modules["local_models"]
            body = {
                "model": model,
                "prompt": prompt,
                "images": [base64.b64encode(img).decode()],
                "stream": False,
                "options": {"temperature": 0.1},
            }
            with lm.api("/api/generate", body, timeout=900) as r:
                return json.loads(r.read()).get("response", "")
        if engine == "gemini":
            return self._gemini(img, mime, prompt)
        raise RuntimeError(f"no reader called {engine}")

    def _gemini(self, img: bytes, mime: str, prompt: str) -> str:
        from kurooto.modules.voice_notes import gemini_api

        key = self.app.secrets.get("gemini.api_key")
        if not key:
            raise RuntimeError("no Gemini key")
        model = self.setting("gemini_model") or "gemini-flash-latest"
        pool, quota = f"gemini:{model}", self.app.quota
        if quota.wait_until(pool) is not None:  # Google's free limit is kept for you today: the page waits a night
            raise RuntimeError("waits: Google's free limit is kept for your own requests today")
        body = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": mime, "data": base64.b64encode(img).decode()}},
                        {"text": prompt},
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
            with egress.urlopen(req, "Books and PDFs", timeout=300) as r:
                out = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                quota.record(pool, "rate_limited", e.read().decode("utf-8", "replace"), e.headers.get("Retry-After"))
            raise RuntimeError(f"Gemini said {e.code}") from None
        quota.record(pool)
        parts = ((out.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts)

    def read_page(self, doc: Doc, n: int, engines: set[str]) -> tuple[str | None, str]:
        """(text, how) for one page; (None, why) when nothing available can read it."""
        text = doc.text(n)
        plan = route(text, doc.images(n), engines, self.setting("ocr") or "auto", self.setting("latex") or "maths")
        why = "needs an OCR reader (/books setup installs Tesseract)"
        pic = None
        for step in plan:
            if step == "blank":
                return "", "blank"
            if step == "text":
                return text.strip(), "text"
            if pic is None:
                pic = doc.picture(n, int(self.setting("dpi") or 200)) or False
            if not pic:
                why = "needs Poppler to draw this page for OCR"
                continue
            try:
                out = _tidy(self.read_picture(step, pic[0], pic[1], n))
            except Exception as e:
                why = f"{SAID[step]}: {e}"[:160]
                continue
            if not out.strip():
                continue
            latex = self.setting("latex") or "maths"
            if step == "tesseract" and "vision" in engines and latex != "never" and mathy(out):
                try:  # maths read by Tesseract comes out garbled: the vision model writes it in LaTeX
                    better = _tidy(self.read_picture("vision", pic[0], pic[1], n))
                    if better.strip():
                        return better, "vision"
                except Exception:
                    pass
            return out, step
        return None, why

    # ------------------------------------------------------------------------------------------ reading
    def book_dir(self, b: dict) -> Path:
        return self.store / b["subject"] / b["id"]

    def meta(self, b: dict) -> dict:
        return jload(self.book_dir(b) / "meta.json", {}) or {}

    def _stop_now(self, until: dt.datetime | None) -> str | None:
        if self._halt.is_set():
            return "stopped"
        if not self.app.is_on(self.id) and self.app.modules.get(self.id) is self:
            return "turned off"
        if not self._force and not self.app.power.may_run(self):
            return "on battery"
        if until is not None and now() >= until:
            return "morning"
        return None

    def read_book(self, b: dict, until: dt.datetime | None = None) -> dict:
        """Read the pages of one book not read yet. Each page is saved as it's read, so an interruption loses at
        most the page being read."""
        d = self.book_dir(b)
        st = b["path"].stat()
        sig = f"{st.st_size}:{int(st.st_mtime)}"
        meta = self.meta(b)
        if meta.get("sig") != sig:  # a new book, or the file changed: start over
            shutil.rmtree(d / "pages", ignore_errors=True)
            meta = {"sig": sig, "added": now().isoformat(timespec="seconds"), "routes": {}, "skipped": {}}
        meta.update(subject=b["subject"], file=str(b["path"]), id=b["id"])
        if st.st_size > int(self.setting("max_mb") or 400) * 2**20:
            meta["problem"] = f"over {self.setting('max_mb') or 400} MB (books.max_mb)"
            jsave(d / "meta.json", meta)
            return {"book": b["id"], "result": "too big"}
        if (
            self.setting("duplicates") is not False
        ):  # the same file under another name or in another subject is read once
            dup = self.duplicate_of(b, meta)
            if dup:
                meta.update(duplicate_of=dup["id"])
                meta.pop("problem", None)
                jsave(d / "meta.json", meta)
                other = self.meta(dup)
                other["copies"] = sorted({*other.get("copies", []), b["id"]})
                jsave(self.book_dir(dup) / "meta.json", other)
                self.app.events.emit("book_duplicate")
                return {"book": b["id"], "result": "duplicate"}
        meta.pop("duplicate_of", None)
        doc = Doc(b["path"], self.tools(), self.app.paths.cache / "books")
        total = doc.pages()
        if not total:
            meta["problem"] = unreadable_why(b["path"], self.tools())
            jsave(d / "meta.json", meta)
            return {"book": b["id"], "result": "unreadable"}
        meta.pop("problem", None)
        meta["title"] = meta.get("title") or doc.title()
        meta["pages"] = total
        engines = sorted(self.engines())
        if meta.get("engines") != engines:  # a new reader since: try the pages that waited for one again
            meta["skipped"], meta["engines"] = {}, engines
        else:  # pages a reader failed on (a busy model, a network error) get another go; those waiting for one don't
            meta["skipped"] = {k: v for k, v in (meta.get("skipped") or {}).items() if v.startswith("needs")}
        pages = d / "pages"
        pages.mkdir(parents=True, exist_ok=True)
        read, last_save, stop = 0, time.monotonic(), None
        for n in range(1, total + 1):
            f = pages / f"{n:05d}.md"
            if f.exists() or str(n) in meta["skipped"]:
                continue
            stop = self._stop_now(until)
            if stop:
                break
            self.status = f"{meta['title']}: page {n} of {total}"
            try:
                text, how = self.read_page(doc, n, set(engines))
            except Exception as e:  # one bad page never stops the book
                text, how = None, f"{type(e).__name__}: {e}"[:160]
            if text is None:
                meta["skipped"][str(n)] = how
                continue
            tmp = f.with_suffix(".tmp")
            tmp.write_text(f"<!-- p. {n} · {how} -->\n{text.strip()}\n", encoding="utf-8")
            os.replace(tmp, f)
            meta["routes"][how] = meta["routes"].get(how, 0) + 1
            read += 1
            if time.monotonic() - last_save > 20:
                jsave(d / "meta.json", meta)
                last_save = time.monotonic()
        self.status = ""
        done = sum(1 for _ in pages.glob("*.md"))
        meta["done"] = done
        jsave(d / "meta.json", meta)
        if stop:
            return {"book": b["id"], "read": read, "result": stop}
        first = not meta.get("finished")
        if read or first or meta.get("indexed") is False:
            self.finish(b, meta, doc)
            if first:
                self._tell(meta)
        return {"book": b["id"], "read": read, "result": "done"}

    @staticmethod
    def fingerprint(path: Path) -> str:
        """A hash of the file's bytes (the same book copied or filed twice has the same one)."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:24]

    def duplicate_of(self, b: dict, meta: dict) -> dict | None:
        """The book this one is a copy of (the same bytes, already read or being read), or None. Sets meta["fp"]."""
        meta["fp"] = (
            meta.get("fp") if meta.get("fp_sig") == meta.get("sig") and meta.get("fp") else self.fingerprint(b["path"])
        )
        meta["fp_sig"] = meta.get("sig")
        for o in self.library():
            if o["id"] == b["id"]:
                continue
            m = self.meta(o)
            if (
                m.get("fp") == meta["fp"]
                and not m.get("duplicate_of")
                and (m.get("added") or "") <= (meta.get("added") or "~")
            ):
                return o
        return None

    def page_texts(self, b: dict) -> dict[int, str]:
        out = {}
        for f in sorted((self.book_dir(b) / "pages").glob("*.md")):
            try:
                out[int(f.stem)] = re.sub(r"\A<!--.*?-->\n", "", f.read_text(encoding="utf-8", errors="replace"))
            except (ValueError, OSError):
                continue
        return out

    def finish(self, b: dict, meta: dict, doc: Doc | None = None) -> None:
        """The whole text with page markers, the index note in the notes, and the notes brain."""
        d = self.book_dir(b)
        pages = self.page_texts(b)
        lines = [
            f"# {meta['title']}",
            f"<!-- {meta['file']} · {npages(meta['pages'])} · page numbers are the PDF's -->",
        ]
        for n in range(1, meta["pages"] + 1):
            body = pages.get(n)
            mark = "" if body is not None else f" (not read: {meta['skipped'].get(str(n), 'not yet')})"
            lines.append(f'\n<a id="p-{n}"></a>\n## [p. {n}]{mark}\n\n{(body or "").strip()}')
        tmp = d / "text.md.tmp"
        tmp.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        os.replace(tmp, d / "text.md")
        outline = (doc or Doc(b["path"], self.tools(), self.app.paths.cache / "books")).outline()
        meta["chapters"] = chapters(outline, pages, meta["pages"])
        meta["outline"] = [[lv, t, p] for lv, t, p in outline if p and lv <= 2][:600]  # the concept graph's batches
        meta["index"] = self.write_index(b, meta)
        meta["finished"] = meta.get("finished") or now().isoformat(timespec="seconds")
        meta["indexed"] = self.to_brain(b, meta, pages)
        jsave(d / "meta.json", meta)
        self._hubs()
        self._after_read(b)
        integrate = self.app.modules.get("integrate")  # the concepts of what was just read go into your notes
        if integrate is not None and self.app.is_on("integrate"):
            integrate.poke()
        self.app.events.emit("book_read", pages=meta["pages"], **{k: v for k, v in meta["routes"].items()})

    def _hubs(self) -> None:
        """Keep the home and research hubs linked (core/hubs.py), so a book's page isn't an island; never fails."""
        from kurooto.core import hubs

        try:
            hubs.ensure(self.app)
        except Exception as e:
            self.app.events.emit("hubs_failed", error=str(e)[:200])

    def _after_read(self, b: dict) -> None:
        """books.after_read: your own command (a list: the program, then its arguments) runs once a book is read, with
        its subject and id on the end, e.g. to link its concepts into your notes. Never through a shell; what it does
        is yours, and a failure is only logged."""
        cmd = self.setting("after_read")
        if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) for x in cmd):
            return
        r = proc.run([*cmd, b["subject"], b["id"]], timeout=300, cwd=self.app.workspace)
        if r.code != 0:
            self.app.events.emit("book_after_read_failed", book=b.get("id"), error=(r.err or r.out or "")[-200:])

    def write_index(self, b: dict, meta: dict) -> str:
        """<subject>/books/<book>.md in the notes: Kurooto's part between markers, yours around it."""
        lay = layout.of(self.app)
        note = lay.path("subject", subject=b["subject"]) / "books" / f"{b['id']}.md"
        how = ", ".join(f"{SAID.get(k, k)} {v}" for k, v in sorted(meta["routes"].items(), key=lambda kv: -kv[1]))
        course = lay.path("course", subject=b["subject"])
        if course.exists():
            where = lay.note_link(lay.link("course", subject=b["subject"]), from_note=note)
        else:
            # Check for project hubs or research maps (e.g. projects/<subfolder>/index, maps/research)
            s = b["subject"].lower().strip()
            ws = self.app.workspace
            hub = None
            for cand in [
                ws / "projects" / s / "index.md",
                ws / "projects" / f"{s}.md",
                ws / "books" / s / "index.md",
                ws / "maps" / f"{s}.md",
            ]:
                if cand.is_file():
                    hub = lay.note_link(cand.relative_to(ws).with_suffix("").as_posix(), from_note=note)
                    break
            if hub:
                research = lay.note_link("maps/research", from_note=note)
                where = f"{hub} · {research}" if (ws / "maps" / "research.md").is_file() else hub
            else:
                where = f"{b['subject']}"
        rows = [
            f"A book for {where}: {npages(meta['pages'])}, read {(meta.get('finished') or now().isoformat())[:10]} "
            f"({how or 'nothing yet'}).",
            "Page numbers are the PDF's own (p. 1 is its first page, often the cover).",
            f"Original: {lay.file_link(b['path'], note)}",
            f"Its text, with page markers (outside your notes): {self.book_dir(b) / 'text.md'}",
        ]
        if meta.get("skipped"):
            rows.append(f"Not read yet: {len(meta['skipped'])} page(s) ({next(iter(meta['skipped'].values()))}).")
        rows.append("\n## Chapters\n")
        chs = meta.get("chapters") or []
        rows += [f"{'  ' * (lv - 1)}- p. {a}–{z}: {t}" for lv, t, a, z in chs] or ["(no chapters found in the PDF)"]
        head = lay.frontmatter(None, note, title=meta["title"], tags=["book", b["subject"]]) + f"# {meta['title']}\n\n"
        old = note.read_text(encoding="utf-8", errors="replace") if note.exists() else None
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(put_block(old, "\n".join(rows), head), encoding="utf-8")
        return lay.shown(note)

    def to_brain(self, b: dict, meta: dict, pages: dict[int, str]) -> bool | None:
        """The text into the notes brain, BRAIN_PAGES pages per brain page (books/<subject>/<book>/p00001-00020).
        None when the brain is off; False when it was busy (tried again next night)."""
        gb = self.app.modules.get("gbrain")
        if not (self.setting("brain") and gb is not None and self.app.is_on("gbrain")):
            return None
        d = self.brain_dir / "books" / b["subject"] / b["id"]
        d.mkdir(parents=True, exist_ok=True)
        for a in range(1, meta["pages"] + 1, BRAIN_PAGES):
            z = min(meta["pages"], a + BRAIN_PAGES - 1)
            body = "\n\n".join(f"[p. {n}]\n{pages[n].strip()}" for n in range(a, z + 1) if pages.get(n, "").strip())
            if body:
                name = f"{meta['title']}, pp. {a}-{z}"
                (d / f"p{a:05d}-{z:05d}.md").write_text(
                    f"---\ntitle: {json.dumps(name)}\ntags: [book, {b['subject']}]\n---\n\n# {name}\n\n{body}\n",
                    encoding="utf-8",
                )
        args = ["import", str(self.brain_dir.resolve())]
        src = str(self.setting("brain_source") or "").strip()
        if src:
            args.extend(["--source-id", src])
        if (jload(self.app.paths.state / "gbrain.json", {}) or {}).get("embeddings", "off") == "off":
            args.append("--no-embed")
        r = gb.run(*args, timeout=3600, wait=0)
        if not r.ok and src and "exist" in f"{r.out}{r.err}".lower():  # a source GBrain doesn't have (yet)
            self.app.events.emit("book_source_missing", source=src, hint=f"gbrain sources add {src} --path <folder>")
        return bool(r.ok)

    def _tell(self, meta: dict) -> None:
        how = ", ".join(f"{v} by {SAID.get(k, k)}" for k, v in sorted(meta["routes"].items(), key=lambda kv: -kv[1]))
        waiting = f" {len(meta['skipped'])} page(s) wait for a reader: /books." if meta.get("skipped") else ""
        self.app.notify(
            f"Read “{meta['title']}” ({npages(meta['pages'])}: {how}). "
            f"Its chapters are in {meta.get('index')}.{waiting}",
            kind="result",
            title="Books",
            why="books.read",
            about=meta["title"],
        )

    def read_all(self, until: dt.datetime | None = None) -> dict:
        """Read every book with pages left, one at a time, until `until` or the charger is pulled."""
        try:
            with Lock(self.app.paths.state, "books", timeout=0):
                out = {"books": 0, "pages": 0, "stopped": ""}
                for b in self.library():
                    r = self.read_book(b, until)
                    out["books"] += 1 if r.get("read") else 0
                    out["pages"] += r.get("read", 0)
                    if r["result"] in ("stopped", "turned off", "on battery", "morning"):
                        out["stopped"] = r["result"]
                        break
                if out["stopped"] == "on battery":  # unplugged in the night: carry on when it's plugged in again
                    self.app.scheduler.at(now(), "books.now", {"night": True}, key="books:resume", module=self.id)
                self.app.events.emit("books_read", **out)
                return out
        except Timeout:
            return {"skipped": "already reading"}

    def night(self, t: dt.datetime | None = None) -> bool:
        """Is it reading time (books.at to books.until)? A night's reading held for the charger doesn't start in the
        middle of the day when you plug in."""
        t = t or now()
        m = re.search(r"(\d{1,2}):(\d{2})", self.setting("at") or "")
        start = dt.time(int(m[1]), int(m[2])) if m else dt.time(1, 0)
        end = dt.time.fromisoformat(self.setting("until") or "07:00")
        cur = t.time()
        return start <= cur < end if start < end else cur >= start or cur < end

    def _until(self) -> dt.datetime:
        t = dt.time.fromisoformat(self.setting("until") or "07:00")
        cur = now()
        end = cur.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        return end if end > cur else end + dt.timedelta(days=1)

    def spawn(self, until: dt.datetime | None = None, force: bool = False) -> bool:
        """Read in the background (books take hours); once at a time."""
        if self._thread is not None and self._thread.is_alive():
            return False
        self._halt.clear()
        self._force = force
        self._thread = threading.Thread(target=self.read_all, args=(until,), name="books", daemon=True)
        self._thread.start()
        return True

    # ------------------------------------------------------------------------------------------ lifecycle
    def ready(self):
        if not (jload(self.app.paths.state / "books.json", {}) or {}).get("set_up"):
            return False, "needs setting up (Set up, or add your first book below)"
        return True, ""

    def setup(self, progress=print) -> tuple[bool, str]:
        """Make the books folders; install Tesseract for scanned pages unless a vision model reads them."""
        self._folders()
        msg = ""
        if not self.tesseract() and not self.vision_model():
            ok, msg = self.prereqs.install("tesseract", progress)
            msg = (
                " " + msg
                if ok
                else f" Scanned pages need Tesseract, which didn't install ({msg}); PDFs with text work without it."
            )
        if not self.tools().get("pdftoppm"):
            msg += " Encrypted PDFs also need Poppler's PDF tools (optional; the manual says where to get them)."
        jsave(self.app.paths.state / "books.json", {"set_up": True})
        return True, f"Books are set up. Drop PDFs into {self.roots()[0][0]}, one folder per subject.{msg}"

    def setup_form(self) -> dict:
        return {
            "intro": "Your first book: a PDF on this computer, and the subject it's for. More can come from Telegram "
            '(send the PDF with "book for <subject>") or straight into the books folder.',
            "links": [],
            "fields": [
                {"name": "subject", "label": "Subject", "type": "text", "placeholder": "e.g. Linear Algebra"},
                {
                    "name": "path",
                    "label": "The PDF (its full path)",
                    "type": "text",
                    "placeholder": "e.g. ~/Downloads/x.pdf",
                },
            ],
        }

    def configure(self, values: dict) -> dict:
        ok, msg = self.add(str(values.get("path", "")), str(values.get("subject", "")), move=False)
        if ok:
            self._folders()
            jsave(self.app.paths.state / "books.json", {"set_up": True})
        return {"ok": ok, "message": msg}

    def _folders(self) -> None:
        subj = self.app.modules.get("subjects")
        if subj is not None and self.app.is_on("subjects"):
            for s in subj.subjects():
                self.folder(s["slug"]).mkdir(parents=True, exist_ok=True)

    def start(self):
        self.every("read", self.setting("at") or "daily 01:00", lambda p: self.night() and self.spawn(self._until()))
        self.app.scheduler.action(
            "books.now", lambda p: (not (p or {}).get("night") or self.night()) and self.spawn(self._until())
        )

    def stop(self):
        super().stop()
        self._halt.set()

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        stuck = [m.get("problem") for b in self.library() if (m := self.meta(b)).get("problem")]
        return (False, f"{len(stuck)} book(s) can't be read: {stuck[0]}") if stuck else (True, "")

    # ------------------------------------------------------------------------------------------ adding
    def add(self, src: str | Path, subject: str, move: bool = False) -> tuple[bool, str]:
        """Put a PDF into a subject's books folder (copied, or moved when it's Kurooto's own download)."""
        p = Path(os.path.expanduser(str(src).strip().strip('"').strip("'")))
        if not p.is_file():
            return False, f"There's no file at {p}."
        if p.suffix.lower() != ".pdf":
            return False, "Books must be PDFs."
        s = self.subject_of(subject or "")
        if not s:
            return False, "Which subject is it for?"
        d = self.folder(s)
        d.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{6}-", "", p.name)  # Telegram's time stamp
        dest, i = d / name, 2
        while dest.exists():
            dest = d / f"{Path(name).stem}-{i}.pdf"
            i += 1
        (shutil.move if move else shutil.copy2)(str(p), str(dest))
        n = Doc(dest, self.tools(), self.app.paths.cache / "books").pages()
        self.app.events.emit("book_added", pages=n)
        size = npages(n) if n else "pages not counted yet"
        subj = self.app.modules.get("subjects")
        new = ""
        if subj is not None and self.app.is_on("subjects") and s not in {x["slug"] for x in subj.subjects()}:
            new = f" ({s} isn't one of your subjects yet: /subject add {subject.strip()})"
        return (
            True,
            f"Added {dest.name} to {s}'s books ({size}).{new} I'll read it tonight on the charger; "
            "/books read now starts now.",
        )

    def take_book(self, msg: Incoming) -> str | None:
        """A PDF sent with "book for <subject>": into that subject's books (other files go on to Files)."""
        m = CAPTION.match(msg.text or "")
        if not m or not msg.files:
            return None
        subject = (m["a"] or m["b"] or "").strip()
        pdfs = [f for f in msg.files if f.suffix.lower() == ".pdf"]
        if not pdfs:
            return "Books must be PDFs."
        out = []
        for f in pdfs:
            ok, said = self.add(f, subject, move=True)
            out.append(said)
            if ok and not (jload(self.app.paths.state / "books.json", {}) or {}).get("set_up"):
                jsave(self.app.paths.state / "books.json", {"set_up": True})
        return "\n".join(out)

    # ----------------------------------------------------------------------------------------- telling you
    def overview(self) -> str:
        books = self.library()
        if not books:
            return f'No books yet. Send a PDF with "book for <subject>", or drop one into {self.roots()[0][0]}.'
        rows, by = [], {}
        for b in books:
            by.setdefault(b["subject"], []).append(b)
        for s, bs in sorted(by.items()):
            rows.append(f"{s}:")
            for b in bs:
                m = self.meta(b)
                total, done = m.get("pages") or 0, m.get("done") or 0
                if m.get("duplicate_of"):
                    orig = self.find(m["duplicate_of"])
                    state = "a copy of " + (
                        self.meta(orig).get("title") or orig["path"].name if orig else m["duplicate_of"]
                    )
                elif m.get("problem"):
                    state = m["problem"]
                elif not total:
                    state = "not started"
                elif m.get("finished") and done + len(m.get("skipped") or {}) >= total:
                    state = f"read ({npages(total)}" + (
                        f", {len(m['skipped'])} waiting for a reader)" if m.get("skipped") else ")"
                    )
                else:
                    state = f"{done} of {total} pages read"
                rows.append(f"  {m.get('title') or b['path'].name}: {state}")
        e = self.engines()
        readers = ", ".join(SAID[x] for x in ("tesseract", "vision", "gemini") if x in e) or "none (/books setup)"
        rows.append(f"Scanned pages: {readers}. Reading tonight from {(self.setting('at') or '').split()[-1]}.")
        if self.status:
            rows.append(f"Now reading: {self.status}.")
        return "\n".join(rows)

    def commands(self):
        return [
            Command(
                "books",
                "your books per subject and how far reading got (/books read now, folder, mix, setup)",
                self._cmd,
                usage="/books [read now | stop | folder [subject] | mix <subject> ... | setup]",
            )
        ]

    def _cmd(self, msg: Incoming, arg_text: str) -> str:
        a = arg_text.strip()
        word, _, rest = a.partition(" ")
        word, rest = word.lower(), rest.strip()
        if not a:
            return self.overview()
        if word in ("read", "now"):
            force = any(x in ("force", "--force") for x in rest.lower().split())
            left = sum(
                max(0, (self.meta(b).get("pages") or 1) - (self.meta(b).get("done") or 0)) for b in self.library()
            )
            if not self.library():
                return self.overview()
            on_battery = not self.app.power.may_run(self)
            if on_battery and not force:
                self.app.scheduler.at(now(), "books.now", key="books:now", module=self.id)
                return (
                    "This laptop is on battery: I'll start reading the moment it's plugged in "
                    "(or run /books read force)."
                )
            if not self.spawn(self._until(), force=force):
                return f"Already reading: {self.status or 'between pages'}."
            until = self.setting("until") or "07:00"
            how = " (forced on battery)" if on_battery else ""
            end = "or you stop it" if force else "or you unplug"
            return f"Reading now{how} ({left} page(s) left, until {until} {end})."
        if word == "stop":
            self._halt.set()
            return "Stopping after this page; it carries on tonight."
        if word == "folder":
            if rest:
                s = self.subject_of(rest)
                if not s:
                    return "Which subject?"
                self.folder(s).mkdir(parents=True, exist_ok=True)
                return f"Books for {s} go in {self.folder(s)}"
            self._folders()
            return f"Books go in {self.roots()[0][0]}, in a folder per subject."
        if word == "mix":
            subj_word, _, spec = rest.partition(" ")
            s = self.subject_of(subj_word) if subj_word else None
            if not s:
                return (
                    "Usage: /books mix <subject> book 30 classroom 30 own 40  (or prefer own book classroom, or reset)"
                )
            return sources.set_mix(self.app, s, spec) if spec.strip() else sources.describe_mix(self.app, s)
        if word == "setup":
            threading.Thread(target=self._setup_and_tell, name="books-setup", daemon=True).start()
            return "Setting up (Tesseract for scanned pages, if needed)…"
        return "Usage: /books [read now | stop | folder [subject] | mix <subject> ... | setup]"

    def _setup_and_tell(self) -> None:
        ok, msg = self.setup(progress=lambda line: None)
        self.app.notify(msg, kind="result" if ok else "info", title="Books", why="asked")

    # ---------------------------------------------------------------------------------------------- the AI
    def find(self, ref: str, subject: str = "") -> dict | None:
        """A book by its id, or words from its title or file name."""
        ref = (ref or "").strip().lower()
        books = [b for b in self.library() if not subject or b["subject"] == slug(subject, 80)]
        for b in books:
            if ref in (b["id"], b["path"].name.lower()):
                return b
        ws = sources.words(ref)
        best, top = None, 0
        for b in books:
            hay = f"{b['id']} {self.meta(b).get('title', '')}".lower()
            sc = sum(w in hay for w in ws)
            if sc > top:
                best, top = b, sc
        return best

    def book_excerpts(self, subject: str, ws: list[str], room: int) -> list[sources.Excerpt]:
        """The pages of a subject's books that best match the topic's words, cited by page."""
        if not ws:
            return []
        scored = []
        for b in self.library():
            if b["subject"] != subject:
                continue
            title = self.meta(b).get("title") or b["path"].stem
            for n, text in self.page_texts(b).items():
                sc = sources.score(text, ws)
                if sc:
                    scored.append((sc, title, n, text))
        scored.sort(key=lambda x: (-x[0], x[2]))
        out, left = [], room
        for sc, title, n, text in scored[:40]:
            if left < 300:
                break
            t = text.strip()[: min(3500, left)]
            out.append(sources.Excerpt("book", f"book: {title}, p. {n}", t, float(sc)))
            left -= len(t)
        return out

    def agent_tools(self):
        tools = [
            Tool(
                "course_sources",
                "Material for writing notes on a subject (and topic): the user's books (by page), Classroom materials "
                "and their own class notes, mixed in the shares they chose, each excerpt labelled with how to cite it. "
                "Call it before writing course notes, exam prep or a revision pack.",
                self._tool_sources,
                {"subject": arg("the notes folder, e.g. linear-algebra"), "topic": arg("what the notes are about")},
                ("subject",),
                writes=False,
            ),
            Tool(
                "list_books",
                "The user's books for a subject (or all), with their chapters and page ranges.",
                self._tool_list,
                {"subject": arg("e.g. linear-algebra (optional)")},
                writes=False,
            ),
            Tool(
                "read_book",
                "Read pages of one of the user's books (as read overnight), with [p. N] markers to cite: book = its id "
                "or title words, pages like 120-125 (at most 15 at a time).",
                self._tool_read,
                {"book": arg(), "pages": arg("e.g. 120-125"), "subject": arg("optional")},
                ("book", "pages"),
                writes=False,
            ),
        ]
        from kurooto.modules.google_classroom import write_exam_prep  # the same exam prep note Classroom keeps

        def exam_prep(a: dict) -> str:
            folder = str(a.get("subject", "")).strip().strip("/")
            out = write_exam_prep(self.app.workspace, folder, str(a.get("text", "")), folder, self.app.name)
            self.app.events.emit("exam_prep_updated")
            return out

        tools.append(
            Tool(
                "update_exam_prep",
                "Replace Kurooto's part of <subject>/exam-prep.md (between its markers) with the subject's current "
                "exam prep, Markdown with these sections: ## Next assessment, ## Covered so far, ## Must know, "
                "## Typical questions, ## Gaps. Text the user wrote outside the markers is kept.",
                exam_prep,
                {"subject": arg("the notes folder, e.g. linear-algebra"), "text": arg("the sections, Markdown")},
                ("subject", "text"),
                offline="queue",
                writes=True,
            )
        )
        return tools

    def _tool_sources(self, a: dict) -> str:
        subject = self.subject_of(str(a.get("subject", ""))) or ""
        if not subject:
            return "Which subject? Give its notes folder, e.g. linear-algebra."
        got = sources.gather(self.app, subject, str(a.get("topic") or ""), books=self.book_excerpts)
        self.app.events.emit("sources_used", **{k: v for k, v in got["chars"].items()})
        return got["text"]

    def _tool_list(self, a: dict):
        subject = slug(str(a.get("subject") or ""), 80) if a.get("subject") else ""
        rows = []
        for b in self.library():
            if subject and b["subject"] != subject:
                continue
            m = self.meta(b)
            chs = "; ".join(f"{t} (p. {x}–{z})" for lv, t, x, z in (m.get("chapters") or []) if lv == 1)[:1500]
            rows.append(
                f"- {b['id']} ({b['subject']}): {m.get('title') or b['path'].name}, {m.get('pages') or '?'} pages, "
                f"{m.get('done') or 0} read." + (f" Chapters: {chs}" if chs else "")
            )
        return "\n".join(rows) or "No books for that subject yet."

    def _tool_read(self, a: dict):
        b = self.find(str(a.get("book", "")), str(a.get("subject") or ""))
        if not b:
            return "No such book (list_books shows them)."
        m = re.fullmatch(r"\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*", str(a.get("pages", "")))
        if not m:
            return "Pages look like 120-125."
        lo = int(m[1])
        hi = min(int(m[2] or lo), lo + 14)
        texts = self.page_texts(b)
        title = self.meta(b).get("title") or b["path"].stem
        parts = [
            f"[p. {n}]\n{texts[n].strip()}" if n in texts else f"[p. {n}] (not read yet)" for n in range(lo, hi + 1)
        ]
        return clip(f"{title}\n\n" + "\n\n".join(parts), 30000)


def _tidy(text: str) -> str:
    """A reader's answer without a Markdown fence around it."""
    t = (text or "").strip()
    m = re.fullmatch(r"```(?:markdown|md)?\s*\n(.*)\n```", t, re.S)
    return (m[1] if m else t).strip()
