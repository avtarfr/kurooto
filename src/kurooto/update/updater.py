"""Finding, checking and installing a new version next to the running one.

check()   read the channel pointer and the release manifest; both must be signed by a trusted key, the pointer
          must not be older than the last one seen (no replaying old releases), and the version must be newer
          than this one and not marked bad.
stage()   download, check each file's sha256, unpack into versions/<v>.partial, build its own .venv from the
          locked requirements, run its self-test, then rename it to versions/<v>.
switch()  remember the current version as previous, point current.json at the new one, start its probation.
Rollback happens in the launcher (crash loop during probation) or with rollback() here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from kurooto.core import proc
from kurooto.core.state import jload, jsave
from kurooto.update import signing

PAGES = "https://avtarfr.github.io/kurooto"


def vtuple(v: str) -> tuple:
    """'0.10.2' -> (0, 10, 2); a suffix like 'rc1' is ignored (pre-releases go out on the beta channel)."""
    out = []
    for part in v.split("+")[0].split("."):
        m = re.match(r"\d+", part)
        out.append(int(m[0]) if m else 0)
    return tuple(out + [0] * (3 - len(out)))


@dataclass
class Release:
    version: str
    channel: str
    issued: float
    files: dict  # name -> {"url", "sha256", "size"}
    notes: str = ""
    critical: bool = False  # signed in the manifest: installs even while a feature holds updates (exam season)


class UpdateError(RuntimeError):
    pass


class Updater:
    def __init__(self, app_dir: Path, state_dir: Path, base_url: str = PAGES, keys: list[str] | None = None):
        self.app = Path(app_dir)
        self.state = Path(state_dir)
        self.base = base_url.rstrip("/")
        self.keys = keys

    # ------------------------------------------------------------------------------------------- local
    def installed(self) -> str | None:
        return (jload(self.app / "current.json", {}) or {}).get("version")

    def managed(self) -> bool:
        """True when installed by the Kurooto installer (versions + launcher), so updates can be applied."""
        return (self.app / "launcher.py").exists() and bool(self.installed())

    def bad(self) -> list[str]:
        return jload(self.app / "bad.json", []) or []

    # --------------------------------------------------------------------------------------- checking
    def _get(self, url: str, timeout: float = 30) -> bytes:
        if not (url.startswith("https://") or url.startswith("http://127.0.0.1")):
            raise UpdateError("updates only come over https")
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (https checked above)
            return r.read()

    def _signed(self, url: str) -> dict:
        try:
            wrapper = json.loads(self._get(url))
        except ValueError as e:
            raise UpdateError(f"unreadable update file {url}") from e
        doc, sig = wrapper.get("doc"), wrapper.get("sig", "")
        if not isinstance(doc, dict) or not signing.verify(doc, sig, self.keys):
            raise UpdateError("an update file wasn't signed by a trusted key; ignored")
        return doc

    def check(self, channel: str = "stable") -> Release | None:
        ptr = self._signed(f"{self.base}/{channel}.json")
        seen = jload(self.state / "update-seen.json", {}) or {}
        if float(ptr.get("issued", 0)) < float(seen.get(channel, 0)):
            raise UpdateError("the update pointer is older than one already seen; ignored")
        seen[channel] = float(ptr.get("issued", 0))
        jsave(self.state / "update-seen.json", seen)
        version = str(ptr["version"])
        cur = self.installed()
        if (cur and vtuple(version) <= vtuple(cur)) or version in self.bad():
            return None
        man = self._signed(ptr["manifest_url"])
        if str(man.get("version")) != version:
            raise UpdateError("the release manifest doesn't match the pointer; ignored")
        notes, critical = man.get("notes", ""), bool(man.get("critical"))
        return Release(version, channel, float(ptr.get("issued", 0)), man["files"], notes, critical)

    # ---------------------------------------------------------------------------------------- staging
    def _download(self, name: str, f: dict, dest: Path) -> Path:
        out = dest / name
        h = hashlib.sha256()
        data = self._get(f["url"], timeout=300)
        h.update(data)
        if h.hexdigest() != f["sha256"]:
            raise UpdateError(f"{name} didn't match its signed checksum; not installed")
        out.write_bytes(data)
        return out

    def stage(self, rel: Release, uv: str, python: str, progress=print) -> Path:
        versions = self.app / "versions"
        final = versions / rel.version
        if final.exists():
            return final
        part = versions / f"{rel.version}.partial"
        shutil.rmtree(part, ignore_errors=True)
        part.mkdir(parents=True)
        try:
            tarball = next(n for n in rel.files if n.endswith(".tar.gz"))
            progress(f"Downloading Kurooto {rel.version}…")
            tgz = self._download(tarball, rel.files[tarball], part)
            src = part / "src"
            with tarfile.open(tgz) as t:
                for m in t.getmembers():
                    parts = Path(m.name).parts[1:]
                    if not parts or ".." in parts or Path(m.name).is_absolute():
                        continue
                    m.name = str(Path(*parts))
                    t.extract(m, src, filter="data")  # noqa: S202 (the "data" filter refuses unsafe members)
            tgz.unlink()
            install_into(part, src, uv, python, progress)
            progress("Checking the new version starts…")
            r = proc.run([str(venv_python(part)), "-m", "kurooto", "selftest"], timeout=300)
            if not r.ok:
                raise UpdateError(f"the new version failed its self-test: {(r.err or r.out)[-300:]}")
            os.replace(part, final)
            return final
        except Exception:
            shutil.rmtree(part, ignore_errors=True)
            raise

    # -------------------------------------------------------------------------------------- switching
    def switch(self, version: str) -> None:
        cur = self.installed()
        if cur and cur != version:
            jsave(self.app / "previous.json", {"version": cur})
        jsave(self.app / "current.json", {"version": version})
        jsave(self.app / "update.json", {"phase": "trial", "from": cur, "to": version, "since": time.time()})

    def probation_passed(self, version: str) -> bool:
        u = jload(self.app / "update.json", {}) or {}
        if u.get("phase") == "trial" and u.get("to") == version and time.time() - float(u.get("since", 0)) >= 300:
            jsave(self.app / "update.json", {**u, "phase": "ok", "ok_at": time.time()})
            return True
        return False

    def prune(self, keep: int = 3) -> None:
        """Keep the current, previous and one more; delete older versions."""
        keepers = {self.installed(), (jload(self.app / "previous.json", {}) or {}).get("version")}
        vs = sorted(
            (p for p in (self.app / "versions").glob("*") if p.is_dir() and not p.name.endswith(".partial")),
            key=lambda p: vtuple(p.name),
            reverse=True,
        )
        for p in vs[keep:]:
            if p.name not in keepers:
                shutil.rmtree(p, ignore_errors=True)


def venv_python(version_dir: Path) -> Path:
    v = Path(version_dir) / ".venv"
    return v / "Scripts" / "python.exe" if os.name == "nt" else v / "bin" / "python"


def install_into(version_dir: Path, src: Path, uv: str, python: str, progress=print) -> None:
    """Build a version's own .venv from its locked requirements (hash-checked), then the package itself."""
    progress("Preparing it…")
    r = proc.run([uv, "venv", "--python", python, str(Path(version_dir) / ".venv")], timeout=300)
    if not r.ok:
        raise UpdateError(f"couldn't make its Python environment: {r.err[-300:]}")
    py = str(venv_python(version_dir))
    req = src / "requirements.lock"
    if req.exists():
        r = proc.run([uv, "pip", "install", "--python", py, "--require-hashes", "-r", str(req)], timeout=900)
        if not r.ok:
            raise UpdateError(f"couldn't install its parts: {r.err[-300:]}")
    r = proc.run(
        [uv, "pip", "install", "--python", py, "--no-deps" if req.exists() else "--quiet", str(src)], timeout=900
    )
    if not r.ok:
        raise UpdateError(f"couldn't install it: {r.err[-300:]}")
