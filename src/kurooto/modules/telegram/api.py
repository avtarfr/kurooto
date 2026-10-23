"""A small Telegram Bot API client (standard library only)."""

from __future__ import annotations

import json
import mimetypes
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = "https://api.telegram.org"
MAX_PARTS = 6  # a longer text comes as a file after its start (send)


class TelegramError(RuntimeError):
    def __init__(self, method: str, code: int | None, description: str):
        super().__init__(f"telegram {method}: {description}")
        self.code = code
        self.description = description


def button(label: str, v) -> dict:
    return {"text": label, "url": v["url"]} if isinstance(v, dict) else {"text": label, "callback_data": str(v)[:64]}


def keyboard(rows: list) -> dict:
    """rows: [[("label", "callback-data") or ("label", {"url": ...}), ...], ...]"""
    out = []
    for row in rows:
        out.append([button(label, v) for label, v in row])
    return {"inline_keyboard": out}


def split_text(text: str, limit: int = 3900) -> list[str]:
    """Telegram allows 4096 characters per message; split long text at line breaks where possible."""
    text = str(text) or "(empty)"
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        cut = cut if cut > limit // 3 else limit
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    return parts


def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, path in files.items():
        p = Path(path)
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        safe = re.sub(r'["\r\n]', "_", p.name)
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{safe}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode()
        body += p.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


class TelegramAPI:
    def __init__(self, token: str, base: str = API):
        self.token = token
        self.base = base.rstrip("/")

    def call(self, method: str, params: dict | None = None, files: dict | None = None, timeout: float = 40):
        url = f"{self.base}/bot{self.token}/{method}"
        params = params or {}
        if files:
            data, ctype = _multipart(
                {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in params.items()}, files
            )
        else:
            data, ctype = json.dumps(params).encode(), "application/json"
        req = urllib.request.Request(url, data=data, headers={"Content-Type": ctype})  # noqa: S310 (fixed https API)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
                res = json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                res = json.loads(e.read())
            except ValueError:
                raise TelegramError(method, e.code, str(e)) from None
        if not res.get("ok"):
            raise TelegramError(method, res.get("error_code"), res.get("description") or "failed")
        return res["result"]

    def me(self) -> dict:
        return self.call("getMe")

    def send(
        self,
        chat_id,
        text: str,
        buttons: list | None = None,
        reply_to=None,
        silent: bool = False,
        tail: str | None = None,
    ) -> int:
        """Send text (split if long; buttons go on the last part). Returns the last message id. Past MAX_PARTS
        messages, the start comes as messages and the whole text as a file after them: nothing is left out.
        tail: the text's last line, shown in italics (the run receipt under an answer)."""
        parts = split_text(text)
        whole = len(parts) > MAX_PARTS
        if whole:
            parts = [*parts[: MAX_PARTS - 1], "(It goes on: the whole text is in the file below.)"]
        mid = None
        for i, part in enumerate(parts):
            params = {
                "chat_id": chat_id,
                "text": part,
                "disable_notification": bool(silent),
                "link_preview_options": {"is_disabled": True},
            }
            if reply_to and i == 0:
                params["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
            if buttons and i == len(parts) - 1 and not whole:
                params["reply_markup"] = keyboard(buttons)
            if tail and i == len(parts) - 1 and part.endswith(tail):  # Telegram counts in UTF-16 code units
                n = len(tail.encode("utf-16-le")) // 2
                params["entities"] = [{"type": "italic", "offset": len(part.encode("utf-16-le")) // 2 - n, "length": n}]
            mid = self.call("sendMessage", params)["message_id"]
        if whole:
            import tempfile

            with tempfile.TemporaryDirectory() as d:
                f = Path(d) / "message.txt"
                f.write_text(str(text), encoding="utf-8")
                params = {"chat_id": chat_id, "disable_notification": bool(silent)}
                if buttons:
                    params["reply_markup"] = keyboard(buttons)
                mid = self.call("sendDocument", params, files={"document": f}, timeout=300)["message_id"]
        return mid

    def edit(self, chat_id, message_id: int, text: str, buttons: list | None = None) -> None:
        params = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": str(text)[:4000],
            "reply_markup": keyboard(buttons) if buttons else {"inline_keyboard": []},
        }
        try:
            self.call("editMessageText", params)
        except TelegramError:
            pass

    def document(self, chat_id, path: str | Path, caption: str | None = None, reply_to=None) -> int:
        params: dict = {"chat_id": chat_id}
        if caption:
            params["caption"] = caption[:1000]
        if reply_to:
            params["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        return self.call("sendDocument", params, files={"document": path}, timeout=300)["message_id"]

    def download(self, file_id: str, dest_dir: Path, name_hint: str, stamp: str) -> Path:
        info = self.call("getFile", {"file_id": file_id})
        if info.get("file_size", 0) > 20 * 1024 * 1024:
            raise RuntimeError("Telegram only lets bots download files up to 20 MB")
        url = f"{self.base}/file/bot{self.token}/{info['file_path']}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(info["file_path"]).suffix
        safe = re.sub(r"[^\w.-]+", "-", name_hint or "file").strip("-")[:60] or "file"
        dest = dest_dir / f"{stamp}-{safe}{'' if safe.endswith(ext) else ext}"
        with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310
            dest.write_bytes(r.read())
        return dest
