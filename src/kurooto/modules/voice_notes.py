"""Voice notes: send Kurooto a voice message on Telegram and it's written out, then handled like anything you
type (a reminder, a question for the AI, a note). Uses your free Gemini key: the audio goes to Google to be written
out, and on the free tier Google may use what you send to improve its products, so don't say anything you wouldn't
type. The recording itself is saved in your notes inbox."""

from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path

from kurooto.core import egress
from kurooto.core.config import register_defaults
from kurooto.modules.base import Module

register_defaults("voice_notes", {"model": "gemini-flash-latest", "api_base": ""})
API = "https://generativelanguage.googleapis.com/v1beta"


def gemini_api(app) -> str:
    """Google's Gemini API (tests point voice_notes.api_base at a fake)."""
    return (app.settings.get("voice_notes.api_base") or API).rstrip("/")


PROMPT = (
    "Write out this voice note exactly as spoken, in the language spoken (keep mixed languages as they are). "
    "Output only the words, no notes or labels. If there is no speech, output nothing."
)


class VoiceNotes(Module):
    id = "voice_notes"
    title = "Voice notes"
    description = "Send a voice message on Telegram: it's written out and handled like a typed message."
    requires = ("telegram",)
    telegram_only = True  # voice messages come to your bot; the phone app has none
    privacy = (
        "The recording goes to Google (Gemini, your free key) to be written out; free-tier data may be used by Google."
    )

    def ready(self):
        if not self.app.secrets.get("gemini.api_key"):
            return False, "needs your free Gemini key (AI model → Gemini API key)"
        return True, ""

    def transcribe(self, path: Path, timeout: float = 120) -> str:
        key = self.app.secrets.get("gemini.api_key")
        if not key:
            raise RuntimeError("no Gemini key")
        data = Path(path).read_bytes()
        if len(data) > 18 * 1024 * 1024:
            raise RuntimeError("voice notes can be at most about 18 MB")
        mime = mimetypes.guess_type(str(path))[0] or "audio/ogg"
        if path.suffix.lower() in (".oga", ".ogg", ".opus"):
            mime = "audio/ogg"
        body = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}},
                        {"text": PROMPT},
                    ]
                }
            ],
            "generationConfig": {"temperature": 0},
        }
        model = self.setting("model") or "gemini-flash-latest"
        req = urllib.request.Request(  # noqa: S310 (Google's API, https)
            f"{gemini_api(self.app)}/models/{model}:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
        )
        pool = f"gemini:{model}"  # voice notes count against your key's free limit too (core/quota.py)
        try:
            with egress.urlopen(req, "Voice notes", timeout=timeout) as r:
                out = json.loads(r.read())
        except urllib.error.HTTPError as e:
            body, detail = e.read().decode("utf-8", "replace"), ""
            try:
                detail = json.loads(body).get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                pass
            if e.code == 429:
                self.app.quota.record(pool, "rate_limited", body, e.headers.get("Retry-After"))
                if self.app.quota.used_up(pool):
                    raise RuntimeError(self.app.quota.line(pool)) from None
            raise RuntimeError(f"Gemini said {e.code}: {detail or e.reason}"[:300]) from None
        self.app.quota.record(pool)
        parts = ((out.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        text = " ".join(p.get("text", "") for p in parts).strip()
        self.app.events.emit("voice_note", seconds=None, chars=len(text))
        if not text:
            raise RuntimeError("no speech found")
        return text
