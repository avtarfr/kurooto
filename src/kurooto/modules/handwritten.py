"""Handwritten notes: drop a PDF or a photo of handwritten pages into a folder (for example one your tablet's notes app
syncs to through Google Drive, OneDrive or Dropbox) and Kurooto writes it out as a Markdown note with the maths in
LaTeX, next to a copy of the original. Send /handwritten to process the folder now; otherwise it looks every 15
minutes.

The writing-out uses Gemini (your free key), or, on computers with 12 GB of graphics memory and Local models on,
a vision model on this computer for photos (PDFs still go to Gemini).
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module
from kurooto.modules.voice_notes import gemini_api

register_defaults(
    "handwritten",
    {
        "folder": "",  # where scans land; empty = <notes folder>/handwritten-inbox
        "into": "handwritten",  # where the notes go, inside your notes folder
        "every": "every 15m",
        "model": "gemini-flash-latest",
        "local": True,  # use the local vision model for photos when there is one
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


class Handwritten(Module):
    id = "handwritten"
    heavy = True  # waits for the charger on battery (saver mode, core/power.py)
    title = "Handwritten notes"
    description = "Scans and photos of handwritten pages become Markdown notes (maths in LaTeX), next to the original."
    privacy = "Pages go to Google (Gemini, your free key) to be written out, unless a local vision model handles them."

    def folder(self) -> Path:
        f = self.setting("folder")
        p = Path(f).expanduser() if f else self.app.workspace / "handwritten-inbox"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ready(self):
        if not self.app.secrets.get("gemini.api_key") and not self._local_model():
            return False, "needs your free Gemini key (AI brain → Gemini API key)"
        return True, ""

    def start(self):
        self.every("scan", self.setting("every") or "every 15m", lambda p: self.scan())

    # ------------------------------------------------------------------------------------- engines
    def _local_model(self) -> str | None:
        if not self.setting("local") or not self.app.is_on("local_models"):
            return None
        lm = self.app.modules["local_models"]
        return next((m["tag"] for m in lm.wanted() if m.get("key") == "vision"), None)

    def _gemini(self, data: bytes, mime: str) -> str:
        key = self.app.secrets.get("gemini.api_key")
        if not key:
            raise RuntimeError("no Gemini key")
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
            f"{gemini_api(self.app)}/models/{self.setting('model') or 'gemini-flash-latest'}:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310
                out = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Gemini said {e.code}") from None
        parts = ((out.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts).strip()

    def _ollama(self, model: str, data: bytes) -> str:
        lm = self.app.modules["local_models"]
        with lm.api(
            "/api/generate",
            {
                "model": model,
                "prompt": PROMPT,
                "images": [base64.b64encode(data).decode()],
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=900,
        ) as r:
            return json.loads(r.read()).get("response", "").strip()

    def write_out(self, f: Path) -> str:
        mime = KINDS[f.suffix.lower()]
        data = f.read_bytes()
        if len(data) > 18 * 1024 * 1024:
            raise RuntimeError("over 18 MB; split it into smaller files")
        local = self._local_model()
        if local and mime.startswith("image/") and mime != "image/heic":
            return self._ollama(local, data)
        return self._gemini(data, mime)

    # --------------------------------------------------------------------------------------- work
    def scan(self) -> list[str]:
        done = []
        with Lock(self.app.paths.state, "handwritten", timeout=5):
            seen_file = self.app.paths.state / "handwritten.json"
            seen = jload(seen_file, {}) or {}
            for f in sorted(self.folder().iterdir()):
                if not f.is_file() or f.suffix.lower() not in KINDS or f.name.startswith("."):
                    continue
                st = f.stat()
                sig = f"{st.st_size}:{int(st.st_mtime)}"
                if seen.get(f.name) == sig or now().timestamp() - st.st_mtime < 20:  # still being copied in
                    continue
                try:
                    md = self.write_out(f)
                    if not md:
                        raise RuntimeError("nothing could be read")
                except Exception as e:
                    seen[f.name] = sig  # don't retry a failing file every 15 minutes; it's retried if it changes
                    self.app.notify(f"Couldn't write out {f.name}: {e}"[:300], kind="info")
                    self.app.events.emit("handwritten_failed", error=str(e)[:200])
                    continue
                rel = self._file(f, md)
                seen[f.name] = sig
                done.append(rel)
                self.app.events.emit("handwritten_done", chars=len(md))
            jsave(seen_file, dict(list(seen.items())[-2000:]))
        if done:
            self.app.notify("Written out: " + ", ".join(done), kind="result")
        return done

    def _file(self, src: Path, md: str) -> str:
        m = re.search(r"^# (.+)$", md, re.M)
        title = (m.group(1) if m else src.stem).strip()
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "notes"
        base = self.app.workspace / (self.setting("into") or "handwritten") / f"{now():%Y-%m-%d}-{slug}"
        base.parent.mkdir(parents=True, exist_ok=True)
        n = 1
        while base.with_suffix(".md").exists():
            n += 1
            base = base.with_name(f"{base.name.rsplit('~', 1)[0]}~{n}")
        original = base.with_suffix(src.suffix.lower())
        shutil.copy2(src, original)
        note = (
            f"{md.rstrip()}\n\n---\nOriginal: [{original.name}]({original.name}) · written out {now():%Y-%m-%d %H:%M}\n"
        )
        base.with_suffix(".md").write_text(note, encoding="utf-8")
        return base.with_suffix(".md").relative_to(self.app.workspace).as_posix()

    def commands(self):
        return [Command("handwritten", "write out the handwritten pages waiting in the folder now", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        done = self.scan()
        return f"Done: {len(done)} written out." if done else f"Nothing new in {self.folder()}."
