"""Installing what Kurooto needs (agy, Ollama, Node, Telegram Desktop) from official sources, without admin rights
where the vendor allows it, and checking there's room on the disk first. The list lives in data/prereqs.toml.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
import tarfile
import tomllib
import urllib.request
import webbrowser
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from kurooto.core import proc

Progress = Callable[[str], None]
NODE_DIST = "https://nodejs.org/dist"


def os_name() -> str:
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def arch() -> str:
    m = platform.machine().lower()
    return "arm64" if m in ("arm64", "aarch64") else "amd64"


def expand(p: str, app_dir: Path) -> Path:
    p = p.replace("{app}", str(app_dir))
    for var in ("LOCALAPPDATA", "APPDATA", "USERPROFILE"):
        p = p.replace(f"%{var}%", os.environ.get(var, str(Path.home())))
    return Path(os.path.expanduser(p))


@dataclass
class Prereq:
    key: str
    title: str
    why: str
    size_gb: float
    programs: list[str]
    dirs: list[Path]
    step: dict
    signin: list[str] = field(default_factory=list)
    signin_hint: str = ""
    serve: list[str] = field(default_factory=list)
    check: list[str] = field(default_factory=list)  # a command that must succeed too (e.g. macOS's git stub)

    def find(self) -> str | None:
        for name in self.programs:
            hit = proc.which(name, self.dirs)
            if hit:
                if self.check:
                    try:
                        if not proc.run(self.check, timeout=15).ok:
                            return None
                    except OSError:
                        return None
                return hit
        return None


class Prereqs:
    def __init__(self, app_dir: Path, cache_dir: Path, os: str | None = None, manifest: dict | None = None):
        self.app_dir = Path(app_dir)
        self.cache = Path(cache_dir) / "downloads"
        self.os = os or os_name()
        if manifest is None:
            with resources.files("kurooto.data").joinpath("prereqs.toml").open("rb") as f:
                manifest = tomllib.load(f)
        self.items: dict[str, Prereq] = {}
        for key, d in manifest.items():
            self.items[key] = Prereq(
                key,
                d["title"],
                d.get("why", ""),
                float(d.get("size_gb", 0)),
                d.get("programs", []),
                [expand(x, self.app_dir) for x in d.get("dirs", {}).get(self.os, [])],
                d.get("install", {}).get(self.os, {}),
                d.get("signin", []),
                d.get("signin_hint", ""),
                d.get("serve", []),
                d.get("check", {}).get(self.os, []),
            )

    # ------------------------------------------------------------------------------------ planning
    def status(self) -> dict[str, dict]:
        return {
            k: {
                "title": p.title,
                "why": p.why,
                "size_gb": p.size_gb,
                "installed": bool(p.find()),
                "manual": p.step.get("kind") == "url",
            }
            for k, p in self.items.items()
        }

    def need_gb(self, keys: list[str], extra_gb: float = 0.0) -> float:
        return round(
            sum(self.items[k].size_gb for k in keys if k in self.items and not self.items[k].find()) + extra_gb, 2
        )

    @staticmethod
    def free_gb(target: Path) -> float:
        probe = Path(target)
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        return round(shutil.disk_usage(probe).free / 1024**3, 1)

    def room(self, keys: list[str], extra_gb: float = 0.0, margin_gb: float = 5.0, target: Path | None = None) -> dict:
        """Is there room for this selection? {need, free, margin, ok}"""
        need, free = self.need_gb(keys, extra_gb), self.free_gb(target or self.app_dir)
        return {"need_gb": need, "free_gb": free, "margin_gb": margin_gb, "ok": free - need >= margin_gb}

    # ------------------------------------------------------------------------------------ installing
    def install(self, key: str, progress: Progress = print, margin_gb: float = 5.0) -> tuple[bool, str]:
        p = self.items[key]
        if p.find():
            return True, f"{p.title} is already installed."
        r = self.room([key], margin_gb=margin_gb)
        if not r["ok"]:
            return False, (
                f"Not enough space: {p.title} needs about {p.size_gb:g} GB and only {r['free_gb']:g} GB is "
                f"free (Kurooto keeps {margin_gb:g} GB spare)."
            )
        kind = p.step.get("kind")
        progress(f"Installing {p.title}…")
        try:
            if kind == "script":
                ok, msg = self._script(p)
            elif kind == "download-run":
                f = self._download(p.step["url"], progress)
                res = proc.run([str(f), *p.step.get("args", [])], timeout=1200)
                ok, msg = res.ok, res.err[-300:]
            elif kind == "download-zip":
                url = (p.step.get("urls") or {}).get(arch()) or p.step["url"]
                f = self._download(
                    url, progress, sha256=(p.step.get("sha256s") or {}).get(arch()) or p.step.get("sha256")
                )
                self._unzip(f, expand(p.step["into"], self.app_dir))
                ok, msg = True, ""
            elif kind == "download-tar":
                url = ((p.step.get("urls") or {}).get(arch()) or p.step["url"]).replace("{arch}", arch())
                f = self._download(
                    url, progress, sha256=(p.step.get("sha256s") or {}).get(arch()) or p.step.get("sha256")
                )
                self._untar(f, expand(p.step["into"], self.app_dir))
                ok, msg = True, ""
            elif kind == "node-lts":
                ok, msg = self._node(progress)
            elif kind == "npm-global":
                npm = self.items["node"].find() if "node" in self.items else None
                if not npm:
                    ok_n, msg_n = self.install("node", progress, margin_gb)
                    if not ok_n:
                        return False, f"Node.js is needed first: {msg_n}"
                node_dir = Path(self.items["node"].find()).parent
                npm_cli = node_dir / ("npm.cmd" if self.os == "windows" else "npm")
                prefix = self.app_dir / "npm"
                res = proc.run([str(npm_cli), "install", "-g", "--prefix", str(prefix), p.step["spec"]], timeout=1800)
                ok, msg = res.ok, (res.out + res.err)[-400:]
            elif kind == "bun-global":
                bun = self.items["bun"].find() if "bun" in self.items else None
                if not bun:
                    return False, "Install Bun first."
                env = {**os.environ, "GBRAIN_NO_AUTOPILOT_INSTALL": "1"}
                res = proc.run([bun, "install", "-g", p.step["spec"]], timeout=1800, env=env)
                ok, msg = res.ok, (res.out + res.err)[-400:]
            elif kind == "winget":
                if not shutil.which("winget"):
                    return False, "winget isn't available on this PC; please install it from the Microsoft Store."
                res = proc.run(
                    [
                        "winget",
                        "install",
                        "-e",
                        "--id",
                        p.step["id"],
                        "--scope",
                        "user",
                        "--silent",
                        "--accept-package-agreements",
                        "--accept-source-agreements",
                    ],
                    timeout=1200,
                )
                ok, msg = res.ok, (res.out + res.err)[-300:]
            elif kind == "flatpak":
                if shutil.which("flatpak"):
                    res = proc.run(["flatpak", "install", "--user", "-y", "flathub", p.step["id"]], timeout=1800)
                    ok, msg = res.ok, res.err[-300:]
                else:
                    webbrowser.open(p.step["fallback"])
                    return False, f"Opened the {p.title} download page; install it from there."
            elif kind == "brew":  # Homebrew installs as you (no admin); without it, the project's page opens
                brew = shutil.which("brew") or next(
                    (b for b in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew") if Path(b).is_file()), None
                )
                if not brew:
                    webbrowser.open(p.step["fallback"])
                    return False, f"Opened the {p.title} page; install it from there (or install Homebrew first)."
                res = proc.run([brew, "install", p.step["formula"]], timeout=1800)
                ok, msg = res.ok, (res.out + res.err)[-300:]
            elif kind == "url":
                webbrowser.open(p.step["url"])
                return False, f"Opened the {p.title} download page; install it from there."
            else:
                return False, f"I don't know how to install {p.title} on this system."
        except Exception as e:
            return False, f"Installing {p.title} failed: {type(e).__name__}: {e}"[:400]
        if ok and p.find():
            progress(f"{p.title} is installed.")
            return True, f"{p.title} is installed."
        if ok and p.step.get("then"):  # an installer that finishes in its own window (e.g. Apple's)
            return False, p.step["then"]
        return False, f"{p.title} didn't install cleanly. {msg}".strip()

    def _script(self, p: Prereq) -> tuple[bool, str]:
        if self.os == "windows":
            args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", p.step["script"]]
        else:
            args = ["bash", "-c", p.step["script"]]
        res = proc.run(args, timeout=900)
        return res.ok, (res.out + res.err)[-400:]

    def _download(self, url: str, progress: Progress, sha256: str | None = None) -> Path:
        if not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
            raise ValueError("only https downloads")
        self.cache.mkdir(parents=True, exist_ok=True)
        dest = self.cache / url.rstrip("/").rsplit("/", 1)[-1]
        tmp = dest.with_suffix(dest.suffix + ".part")
        h = hashlib.sha256()
        with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:  # noqa: S310 (https checked above)
            total = int(r.headers.get("Content-Length") or 0)
            done, last = 0, -1
            while chunk := r.read(1 << 20):
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                pct = int(done * 100 / total) if total else -1
                if pct != last and pct % 10 == 0:
                    progress(f"Downloading {dest.name}: {pct}%")
                    last = pct
        if sha256 and h.hexdigest() != sha256:
            tmp.unlink(missing_ok=True)
            raise ValueError(f"{dest.name} didn't match its published checksum; not used")
        os.replace(tmp, dest)
        return dest

    @staticmethod
    def _unzip(f: Path, dest: Path, strip: int = 0) -> None:
        """Unpack a zip, refusing absolute paths and "..", optionally dropping leading folders."""
        dest.mkdir(parents=True, exist_ok=True)
        root = dest.resolve()
        with zipfile.ZipFile(f) as z:
            for m in z.infolist():
                parts = Path(m.filename).parts[strip:]
                if not parts or ".." in parts or Path(m.filename).is_absolute() or ":" in parts[0]:
                    continue
                target = root.joinpath(*parts)
                if root not in target.resolve().parents and target.resolve() != root:
                    continue
                if m.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(m))
                    mode = (m.external_attr >> 16) & 0o777
                    if mode and os.name != "nt":
                        target.chmod(mode)

    @staticmethod
    def _untar(f: Path, dest: Path, strip: int = 0) -> None:
        """Unpack while reading from disk: never the whole archive in memory (Ollama's is gigabytes unpacked, and
        holding it all once got Kurooto killed by the out-of-memory killer)."""
        dest.mkdir(parents=True, exist_ok=True)

        def unpack(t: tarfile.TarFile) -> None:
            for m in t:  # in order: works for a stream too
                parts = Path(m.name).parts[strip:]
                if not parts or ".." in parts or Path(m.name).is_absolute():
                    continue
                m.name = str(Path(*parts))
                t.extract(m, dest, filter="data")  # noqa: S202 (the "data" filter refuses unsafe members)

        if f.name.endswith(".zst"):
            import zstandard

            with open(f, "rb") as fh, zstandard.ZstdDecompressor().stream_reader(fh) as reader:
                with tarfile.open(fileobj=reader, mode="r|") as t:
                    unpack(t)
        else:
            with tarfile.open(f, mode="r:*") as t:
                unpack(t)

    def _node(self, progress: Progress, dist: str = NODE_DIST) -> tuple[bool, str]:
        with urllib.request.urlopen(f"{dist}/index.json", timeout=30) as r:  # noqa: S310
            versions = json.loads(r.read())
        v = next(x for x in versions if x.get("lts"))["version"]
        a = "arm64" if arch() == "arm64" else "x64"
        name = {
            "windows": f"node-{v}-win-{a}.zip",
            "macos": f"node-{v}-darwin-{a}.tar.gz",
            "linux": f"node-{v}-linux-{a}.tar.xz",
        }[self.os]
        with urllib.request.urlopen(f"{dist}/{v}/SHASUMS256.txt", timeout=30) as r:  # noqa: S310
            sums = dict(line.split()[::-1] for line in r.read().decode().splitlines() if line.strip())
        f = self._download(f"{dist}/{v}/{name}", progress, sha256=sums.get(name))
        dest = self.app_dir / "node"
        shutil.rmtree(dest, ignore_errors=True)
        if name.endswith(".zip"):
            self._unzip(f, dest, strip=1)
        else:
            self._untar(f, dest, strip=1)
        return True, v

    # ------------------------------------------------------------------------------------- signing in
    def open_signin(self, key: str) -> tuple[bool, str]:
        """Open a terminal window running the tool's sign-in, so you can log in in your browser."""
        p = self.items[key]
        exe = p.find()
        if not exe or not p.signin:
            return False, f"{p.title} isn't installed yet."
        cmd = [exe, *p.signin[1:]]
        if self.os == "windows":
            proc.run(
                ["cmd", "/c", "start", f"Sign in to {p.title}", "powershell", "-NoExit", "-Command", f"& '{exe}'"],
                timeout=20,
            )
        elif self.os == "macos":
            script = f'tell application "Terminal" to do script "{exe}"'
            proc.run(["osascript", "-e", script, "-e", 'tell application "Terminal" to activate'], timeout=20)
        else:
            for term in (
                "x-terminal-emulator",
                "gnome-terminal",
                "konsole",
                "kitty",
                "alacritty",
                "xfce4-terminal",
                "xterm",
            ):
                if shutil.which(term):
                    import subprocess

                    subprocess.Popen([term, "-e", *cmd], start_new_session=True)
                    break
            else:
                return False, f"Open a terminal and run: {' '.join(cmd)}"
        return True, p.signin_hint or "A sign-in window opened."
