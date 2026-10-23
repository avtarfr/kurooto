"""Drive upload: files you send yourself go to a folder of Kurooto's own in your Google Drive ("Kurooto"), and you get
the link on Telegram. `kurooto send FILE --to drive` (or the AI's send_file with to=drive) sends one there; anything
bigger than Telegram's 50 MB goes there by itself (drive_upload.big_files).

Google's permission for this ("drive.file") covers only the files Kurooto itself makes: it can't see, open or change
anything else in your Drive. Nothing is shared: the link opens only for you (and whoever you share it with yourself,
in Drive). With several Google accounts, it uses the one you choose on its card (or /google use drive school).
"""

from __future__ import annotations

import json
import mimetypes
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.google import GoogleError, GooglePart, NeedsSignIn

register_defaults(
    "drive_upload",
    {
        "folder": "Kurooto",
        "big_files": True,  # files over Telegram's 50 MB come as a Drive link instead of not at all
        "temp_days": 7,  # those links last this many days, then the file is deleted from your Drive (0: kept)
    },
)
FOLDER = "application/vnd.google-apps.folder"
CHUNK = 8 * 2**20  # bytes per piece of a resumable upload (a multiple of 256 KiB, as Google wants)


def quoted(name: str) -> str:
    """A name inside a Drive search's single quotes."""
    return name.replace("\\", "\\\\").replace("'", "\\'")


class DriveUpload(GooglePart):
    id = "drive_upload"
    part = "drive_upload"
    title = "Drive upload"
    description = (
        "Files you send yourself (kurooto send FILE --to drive, or anything over Telegram's 50 MB) go to a Kurooto "
        "folder in your Google Drive; you get the link."
    )
    privacy = (
        "Uploads only the files you send to a folder of its own in your Google Drive. Google's permission covers only "
        "files Kurooto makes, so it can't see the rest of your Drive. Nothing is shared: the link opens only for you."
    )
    permission = (
        "Google will ask you to allow Kurooto to see, edit, create and delete only the specific Google Drive files it "
        "uses. Kurooto makes one folder (Kurooto) and puts the files you send there; it can't see your other files, "
        "and it shares nothing."
    )
    api_link = ("Turn on the Google Drive API", "https://console.cloud.google.com/apis/library/drive.googleapis.com")

    @property
    def file(self) -> Path:
        return self.app.paths.state / "drive-upload.json"

    @property
    def temp_file(self) -> Path:
        return self.app.paths.state / "drive-temporary.json"

    def start(self):
        self.every("expire", "daily 04:10", self.expire)

    def remember_temporary(self, fid: str, name: str) -> None:
        days = float(self.setting("temp_days") or 0)
        if not days or not fid:
            return
        rows = jload(self.temp_file, []) or []
        rows.append({"id": fid, "name": name, "delete_at": time.time() + days * 86400, "account": self.account})
        jsave(self.temp_file, rows[-500:])

    def expire(self, payload: dict | None = None) -> int:
        """Delete the temporary uploads whose days are up (a file you moved out of Kurooto's folder or deleted
        yourself is just forgotten). Returns how many went."""
        rows = jload(self.temp_file, []) or []
        keep, gone = [], 0
        for r in rows:
            if r.get("delete_at", 0) > time.time():
                keep.append(r)
                continue
            try:
                self.google.api("drive", f"/files/{r['id']}", method="DELETE")
                gone += 1
            except GoogleError as e:
                if e.code not in (404, 403):
                    keep.append(r)  # try again tomorrow
            except NeedsSignIn:
                keep.append(r)
        jsave(self.temp_file, keep)
        if gone:
            self.app.events.emit("drive_temporary_deleted", files=gone)
        return gone

    # ------------------------------------------------------------------------------------------ the folder
    def folder_id(self) -> str:
        """Kurooto's folder in your Drive: found (it can only see folders it made) or made, then remembered."""
        st = jload(self.file, {}) or {}
        name = str(self.setting("folder") or "Kurooto").strip() or "Kurooto"
        if st.get("id") and st.get("account") == self.account and st.get("name", name) == name:
            return st["id"]
        q = f"name = '{quoted(name)}' and mimeType = '{FOLDER}' and trashed = false"
        found = self.google.api(
            "drive", "/files?" + urllib.parse.urlencode({"q": q, "fields": "files(id)", "spaces": "drive"})
        ).get("files", [])
        if found:
            fid = found[0]["id"]
        else:
            fid = self.google.api("drive", "/files?fields=id", {"name": name, "mimeType": FOLDER})["id"]
        jsave(self.file, {"id": fid, "account": self.account, "name": name})
        return fid

    # ------------------------------------------------------------------------------------------ uploading
    def upload(self, path: Path, name: str | None = None) -> dict:
        """Upload one file into Kurooto's folder: {"id", "name", "webViewLink"}. A folder you deleted is made again."""
        path = Path(path)
        name = name or f"{now():%Y-%m-%d}-{path.name}"
        for attempt in (0, 1):
            folder = self.folder_id()
            try:
                return self._resumable(path, name, folder)
            except GoogleError as e:
                if e.code != 404 or attempt:
                    raise
                jsave(self.file, {})  # the folder is gone (deleted in Drive): make it again
        raise GoogleError(404, "Drive lost the folder")

    def _call(self, url: str, data: bytes, headers: dict, method: str) -> tuple[int, bytes, dict]:
        g = self.app.modules["google"]
        req = urllib.request.Request(  # noqa: S310 (Google's upload address, https)
            url,
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {g.access_token(self.account)}", **headers},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code == 308:  # "resume incomplete": send the next piece
                return 308, b"", dict(e.headers)
            if e.code == 401:
                g._lost_signin(self.account)
                raise NeedsSignIn("Google refused the sign-in") from None
            try:
                msg = json.loads(e.read()).get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                msg = ""
            raise GoogleError(e.code, f"Google said {e.code}: {msg}"[:300]) from None

    def _resumable(self, path: Path, name: str, folder: str) -> dict:
        g = self.app.modules["google"]
        size = path.stat().st_size
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        _, _, h = self._call(
            f"{g.ep('drive_upload')}/files?uploadType=resumable&fields=id,name,webViewLink",
            json.dumps({"name": name, "parents": [folder]}).encode(),
            {
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": mime,
                "X-Upload-Content-Length": str(size),
            },
            "POST",
        )
        where = {k.lower(): v for k, v in h.items()}.get("location")
        if not where:
            raise GoogleError(500, "Google didn't give an upload address")
        pos = 0
        with path.open("rb") as f:
            while True:
                f.seek(pos)
                chunk = f.read(CHUNK)
                last = pos + len(chunk) - 1
                rng = f"bytes {pos}-{last}/{size}" if chunk else f"bytes */{size}"
                code, body, h = self._call(where, chunk, {"Content-Range": rng, "Content-Type": mime}, "PUT")
                if code in (200, 201):
                    return json.loads(body or b"{}")
                got = {k.lower(): v for k, v in h.items()}.get("range", "")  # what Google has: "bytes=0-8388607"
                new = int(got.rsplit("-", 1)[-1]) + 1 if got else 0
                if new <= pos and chunk:
                    raise GoogleError(500, "the upload made no progress")
                pos = new

    # ---------------------------------------------------------------------------------- sending you a file
    def send(self, path: Path, caption: str = "", wait: bool = False, temporary: bool = False) -> tuple[bool, str]:
        """Upload in the background; the link comes to you when it's done. (ok, what to say now). temporary: deleted
        from your Drive after drive_upload.temp_days (what's too big for Telegram)."""
        ok, why = self.ready()
        if not ok:
            return False, f"Drive upload isn't ready: {why}."
        path = Path(path)
        size = path.stat().st_size
        t = threading.Thread(target=self._send_now, args=(path, caption, temporary), daemon=True, name="drive-upload")
        self.last = t
        t.start()
        if wait:
            t.join()
        return (
            True,
            f"Uploading {path.name} ({size / 2**20:.1f} MB) to your Google Drive; the link comes when it's done.",
        )

    def _send_now(self, path: Path, caption: str, temporary: bool = False) -> None:
        try:
            f = self.upload(path)
        except (NeedsSignIn, GoogleError, OSError) as e:
            self.app.notify(f"Couldn't upload {path.name} to Drive: {e}"[:300], kind="result", why="asked")
            self.app.events.emit("drive_upload_failed")
            return
        link = f.get("webViewLink") or f"https://drive.google.com/file/d/{f.get('id', '')}/view"
        folder = str(self.setting("folder") or "Kurooto")
        text = f"{caption.strip()}\n" if caption.strip() else ""
        days = float(self.setting("temp_days") or 0)
        lasts = ""
        if temporary and days:
            self.remember_temporary(str(f.get("id") or ""), path.name)
            lasts = f" It's deleted from your Drive in {days:g} days; move it out of the {folder} folder to keep it."
        self.app.notify(
            f"{text}{path.name} is in your Google Drive ({folder} folder): {link}{lasts}",
            kind="result",
            buttons=[[("Open in Drive", {"url": link})]],
            why="asked",
        )
        self.app.events.emit("file_sent", via="drive", bytes=path.stat().st_size)
