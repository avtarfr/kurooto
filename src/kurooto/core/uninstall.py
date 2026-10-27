"""What Kurooto installed on this computer, and taking it away again.

The receipt (<app>/installed.json: this computer's only, so it's never in a backup or a profile) lists what Kurooto
itself put on the computer:

    program   a program from data/prereqs.toml (Ollama, Node.js, Bun, GBrain, kitty, ...): the files and folders its
              install made (compared with a look just before it ran), the package it is in winget, Flatpak, Homebrew
              or Bun, or its own uninstaller
    model     an Ollama model it downloaded (modules/local_models.py)

Kurooto's own folders for a feature (Voice's packages and models in <app>/voice) are its own by definition and listed
with the receipt.

Something that was here before Kurooto never gets on the receipt: a program that's found isn't installed, a model
Ollama already has isn't downloaded, and of the folders an install touches only what wasn't there before is written
down. Removing never goes past the receipt: paths are checked again (inside your home folder or Kurooto's own, never a
shared folder such as ~/.local/bin itself), and a folder Kurooto made that now holds things of yours stays (Ollama's
model store with models you pulled yourself; Bun's folder with your own global packages).

    kurooto installed, /installed   the list: sizes, the features each is for, and what uses it now
    kurooto remove <thing>          one of them (with what only it needs: Ollama's models), after a yes
    turning a feature off           a question with what it brought and its size: Remove / Keep (uninstall.offer)
    This computer's setup           the same for Ollama models the new setup no longer uses (hardware.*)
    kurooto uninstall               everything on the receipt, then Kurooto (uninstall.with_programs)

Never by the AI, a request or a schedule: core/tap.py's "install.remove".
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.prereqs import Prereq, Prereqs

register_defaults(
    "uninstall",
    {
        "offer": True,  # turning a feature off asks whether to remove what Kurooto installed for it, with the size
        "with_programs": True,  # kurooto uninstall also removes the programs and models Kurooto installed
    },
)

RECEIPT = "installed.json"
HOOK = "uninstall.offer"  # app.ask.hooks: Remove / Keep under the offer (App.__init__)
GB = 1024**3
Say = Callable[[str], None]
# folders in your home that hold other programs' things too: never removed as a whole, only what's in them
SHARED = {
    ".local",
    ".local/bin",
    ".local/share",
    ".local/state",
    ".config",
    ".cache",
    "bin",
    "Applications",
    "Library",
    "Library/Application Support",
    "AppData",
    "AppData/Local",
    "AppData/Roaming",
    "AppData/Local/Programs",
    "Desktop",
    "Documents",
    "Downloads",
}
# Kurooto's own folders for one feature: (the folder under <app>, what it is, the features it's for)
OWN = {"voice": ("voice", "Voice's speech packages and models", ("voice",))}
BRAINS = ("agy", "claude")  # programs that are an AI you pick (brain.main / brain.fallback), not a feature's


@dataclass
class Thing:
    id: str  # program:<key> | model:<tag> | folder:<name>
    kind: str  # program | model | folder
    name: str  # what you type after `kurooto remove`
    title: str
    bytes: int
    estimate: bool  # the size is the manifest's estimate (a package whose files Kurooto can't see)
    features: list[str]  # what it's for: module ids, or local_helper
    entry: dict = field(default_factory=dict)
    users: list[str] = field(default_factory=list)  # what uses it now (filled by things_for)

    @property
    def size(self) -> str:
        return ("about " if self.estimate else "") + human(self.bytes)


def human(n: int) -> str:
    for unit, div in (("GB", GB), ("MB", 1024**2), ("KB", 1024)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} B"


def norm(tag: str) -> str:
    """Ollama's own name for a model: "nomic-embed-text" is "nomic-embed-text:latest"."""
    tag = str(tag or "").strip()
    return tag if ":" in tag or not tag else f"{tag}:latest"


# ------------------------------------------------------------------------------------------------ the receipt
def _file(app_dir: Path) -> Path:
    return Path(app_dir) / RECEIPT


def _lock(app_dir: Path):
    from filelock import FileLock

    Path(app_dir).mkdir(parents=True, exist_ok=True)
    return FileLock(str(_file(app_dir)) + ".lock", timeout=30)


def load(app_dir: Path) -> dict[str, dict]:
    doc = jload(_file(app_dir), {}) or {}
    items = doc.get("items") if isinstance(doc, dict) else None
    return {k: v for k, v in (items or {}).items() if isinstance(v, dict)} if isinstance(items, dict) else {}


def _write(app_dir: Path, items: dict) -> None:
    jsave(_file(app_dir), {"version": 1, "items": items})


def _put(app_dir: Path, iid: str, entry: dict) -> None:
    with _lock(app_dir):
        items = load(app_dir)
        items[iid] = entry
        _write(app_dir, items)


def forget(app_dir: Path, iid: str) -> None:
    with _lock(app_dir):
        items = load(app_dir)
        if items.pop(iid, None) is not None:
            _write(app_dir, items)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# -------------------------------------------------------------------------------------------- where it may go
def _abs(p) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(p))))


def _inside(p: Path, base: Path) -> bool:
    try:
        _abs(p).relative_to(_abs(base))
        return True
    except ValueError:
        return False


def safe(path, app_dir: Path) -> bool:
    """May this path ever be removed? Strictly inside your home folder or Kurooto's own, never the home, Kurooto's
    folder or one of their parents, and never a folder other programs share (SHARED)."""
    p, home, app = _abs(path), _abs(Path.home()), _abs(app_dir)
    if p in (home, app) or _inside(home, p) or _inside(app, p):
        return False
    if _inside(p, app):
        return True
    if not _inside(p, home):
        return False
    return p.relative_to(home).as_posix() not in SHARED


def _roots(paths) -> list[Path]:
    """The paths without the ones inside another of them."""
    ps = sorted({_abs(p) for p in paths}, key=lambda p: len(p.parts))
    out: list[Path] = []
    for p in ps:
        if not any(_inside(p, q) for q in out):
            out.append(p)
    return out


def _there(p: Path) -> bool:
    return p.exists() or p.is_symlink()


def _bytes(paths) -> int:
    from kurooto.core.space import size

    return sum(size(p) for p in _roots(paths) if _there(p))


def _names(d: Path) -> list[str] | None:
    try:
        return sorted(x.name for x in Path(d).iterdir()) if Path(d).is_dir() else None
    except OSError:
        return None


def _stem(name: str) -> str:
    low = name.lower()
    for ext in (".exe", ".cmd", ".bat", ".ps1"):
        if low.endswith(ext):
            return name[: -len(ext)]
    return name


# ------------------------------------------------------------------------------------------- recording programs
def _targets(pre: Prereqs, p: Prereq) -> list[Path]:
    from kurooto.core.prereqs import expand

    out = [Path(d) for d in p.dirs]
    if p.step.get("into"):
        out.append(expand(p.step["into"], pre.app_dir))
    seen, uniq = set(), []
    for t in out:
        if str(_abs(t)) not in seen:
            seen.add(str(_abs(t)))
            uniq.append(_abs(t))
    return uniq


def _bun_global(name: str) -> Path:
    return Path.home() / ".bun" / "install" / "global" / "node_modules" / name


def _package_there(pre: Prereqs, p: Prereq) -> bool:
    """Is the package this install would add already there (installed by you, its program just not found)?"""
    from kurooto.core import proc

    kind = p.step.get("kind")
    try:
        if kind == "flatpak" and shutil.which("flatpak"):
            return proc.run(["flatpak", "info", "--user", p.step["id"]], timeout=30).ok
        if kind == "brew":
            brew = _brew()
            return bool(brew) and proc.run([brew, "list", "--versions", p.step["formula"]], timeout=60).ok
        if kind == "bun-global" and p.programs:
            return _there(_bun_global(p.programs[0]))
        if kind == "npm-global":
            return _there(pre.app_dir / "npm" / "lib" / "node_modules" / _npm_name(p.step.get("spec", "")))
    except (OSError, KeyError):
        return True  # unsure: treated as yours
    return False


def _brew() -> str | None:
    return shutil.which("brew") or next(
        (b for b in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew") if Path(b).is_file()), None
    )


def _npm_name(spec: str) -> str:
    s = spec.strip()
    if s.startswith("@"):
        return "@" + s[1:].split("@", 1)[0]
    return s.split("@", 1)[0]


def look(pre: Prereqs, p: Prereq) -> dict:
    """Just before installing p: the folders its files may land in (and what's in them), whether each path it may
    make is there, and whether its package is there already."""
    return {
        "targets": {str(t): _names(t) for t in _targets(pre, p)},
        "owns": {str(_abs(o)): _there(Path(o)) for o in p.owns},
        "package": _package_there(pre, p),
    }


def record_program(pre: Prereqs, p: Prereq, before: dict, exe: str | None) -> dict | None:
    """After p installed: what it made that wasn't there before goes on the receipt. Returns the entry (None when
    there's nothing Kurooto could take away again, e.g. a vendor's script that put it somewhere unknown)."""
    from kurooto.core.prereqs import expand

    app = _abs(pre.app_dir)
    kind = p.step.get("kind")
    into = _abs(expand(p.step["into"], pre.app_dir)) if p.step.get("into") else None
    stems = {n.lower() for n in p.programs}
    paths: list[Path] = []
    if kind == "node-lts":
        paths.append(app / "node")
    for t_str, had in (before.get("targets") or {}).items():
        t = _abs(t_str)
        if _inside(t, app) and t != app:  # Kurooto's own folder for it: the folder right under <app>
            paths.append(app / t.relative_to(app).parts[0])
            continue
        now = _names(t) or []
        if had is None and t != into and safe(t, app):  # a vendor's own folder that wasn't there (…/Programs/Ollama)
            paths.append(t)
            continue
        new = [n for n in now if n not in (had or [])]
        if t == into:
            want = p.step.get("app")
            new = [n for n in new if not want or n == want]
        else:
            new = [n for n in new if _stem(n).lower() in stems]
        paths += [t / n for n in new]
    owns = [o for o, existed in (before.get("owns") or {}).items() if not existed]
    package: dict = {}
    if not before.get("package"):
        if kind == "winget":
            package = {"manager": "winget", "id": p.step["id"]}
        elif kind == "flatpak" and shutil.which("flatpak"):
            package = {"manager": "flatpak", "id": p.step["id"]}
        elif kind == "brew":
            package = {"manager": "brew", "formula": p.step["formula"]}
        elif kind == "bun-global" and p.programs:
            package = {"manager": "bun", "name": p.programs[0]}
        elif kind == "npm-global":
            package = {"manager": "npm", "name": _npm_name(p.step["spec"]), "prefix": str(app / "npm")}
    uninstaller: list[str] = []
    if kind == "download-run" and exe:
        found = sorted(Path(exe).parent.glob("unins*.exe"))
        if found:
            uninstaller = [str(found[0]), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    paths = [x for x in _roots(paths) if safe(x, app)]
    owns = [o for o in owns if safe(o, app)]
    if not (paths or package or uninstaller):
        return None
    measured = _bytes(paths + [Path(o) for o in owns])
    entry = {
        "kind": "program",
        "key": p.key,
        "title": p.title,
        "how": kind,
        "paths": [str(x) for x in paths],
        "owns": owns,
        "package": package,
        "uninstaller": uninstaller,
        "bytes": measured or int(p.size_gb * GB),
        "estimate": not measured,
        "features": list(p.features),
        "at": _now(),
    }
    _put(app, f"program:{p.key}", entry)
    return entry


def record_model(app_dir: Path, tag: str, size: int, by: str) -> None:
    """An Ollama model Kurooto downloaded (only call it when Ollama didn't have it before)."""
    t = norm(tag)
    _put(
        app_dir,
        f"model:{t}",
        {"kind": "model", "tag": t, "title": f"{t} (Ollama model)", "bytes": int(size), "features": [by], "at": _now()},
    )


# ------------------------------------------------------------------------------------------------ Ollama
def _ollama() -> str:
    """Ollama's address: the one Local AI models uses (one place, so a test's fake catches both)."""
    from kurooto.modules import local_models

    return local_models.OLLAMA


def _ollama_tags() -> dict[str, int] | None:
    """What Ollama has now ({name: bytes}), or None when it isn't running."""
    try:
        with urllib.request.urlopen(_ollama() + "/api/tags", timeout=3) as r:  # noqa: S310 (Ollama on this computer)
            return {norm(m["name"]): int(m.get("size") or 0) for m in json.loads(r.read()).get("models", [])}
    except (OSError, ValueError, KeyError):
        return None


def _delete_one(tag: str) -> bool:
    req = urllib.request.Request(  # noqa: S310 (Ollama on this computer)
        _ollama() + "/api/delete",
        data=json.dumps({"model": tag}).encode(),
        headers={"Content-Type": "application/json"},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=60):  # noqa: S310 (Ollama on this computer)
            return True
    except urllib.error.HTTPError as e:
        return e.code == 404  # it isn't there (any more)
    except OSError:
        return False


def _ollama_delete(tags: list[str], exe: str | None) -> dict[str, bool]:
    """Delete models through Ollama's own API (its blobs are shared between models, so never by hand). With Ollama
    stopped (Kurooto is being uninstalled), its server runs for the moment it takes, then exactly that process ends."""
    child = None
    if _ollama_tags() is None and exe:
        from kurooto.core import proc

        try:
            child = subprocess.Popen(
                [exe, "serve"],
                env={**os.environ, "OLLAMA_HOST": "127.0.0.1:11434"},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            child = None
        for _ in range(40):
            if _ollama_tags() is not None:
                break
            time.sleep(0.5)
        try:
            return {t: _delete_one(t) for t in tags}
        finally:
            if child is not None:
                proc.kill_tree(child.pid)
    return {t: _delete_one(t) for t in tags}


def _still_holds(key: str, folder: Path, going: set[str]) -> str:
    """A folder Kurooto's install made that now holds things of yours: what they are ("" when it holds nothing else)."""
    if key == "ollama":
        man = folder / "models" / "manifests"
        if man.is_dir() and any(f.is_file() for f in man.rglob("*")):
            return "models you pulled yourself are in it"
    if key == "bun":
        pkg = jload(folder / "install" / "global" / "package.json", {}) or {}
        mine = set((pkg.get("dependencies") or {}) if isinstance(pkg, dict) else {}) - going
        if mine:
            return f"your own global packages are in it ({', '.join(sorted(mine)[:3])})"
    return ""


# ------------------------------------------------------------------------------------------------ the list
def _prereqs(app_dir: Path) -> Prereqs:
    from kurooto.core.prereqs import Prereqs

    return Prereqs(app_dir, app_dir)


def things(app_dir: Path, pre: Prereqs | None = None) -> list[Thing]:
    """What's on the receipt and still here, plus Kurooto's own folders for a feature. What's gone (you removed it
    yourself) leaves the receipt on the way."""
    app = _abs(app_dir)
    pre = pre or _prereqs(app)
    items = load(app)
    tags = _ollama_tags() if any(v.get("kind") == "model" for v in items.values()) else None
    out: list[Thing] = []
    gone: list[str] = []
    for iid, it in items.items():
        if it.get("kind") == "program":
            key = str(it.get("key") or "")
            paths = [Path(x) for x in it.get("paths") or []]
            p = pre.items.get(key)
            here = any(_there(x) for x in paths) or (
                bool(it.get("package") or it.get("uninstaller")) and p is not None and bool(p.find())
            )
            if not here:
                gone.append(iid)
                continue
            measured = _bytes(paths + [Path(o) for o in it.get("owns") or []])
            out.append(
                Thing(
                    iid,
                    "program",
                    key,
                    str(it.get("title") or key),
                    measured or int(it.get("bytes") or 0),
                    not measured,
                    list(p.features if p is not None else it.get("features") or []),
                    it,
                )
            )
        elif it.get("kind") == "model":
            tag = norm(it.get("tag") or "")
            if tags is not None and tag not in tags:
                gone.append(iid)
                continue
            size = (tags or {}).get(tag) or int(it.get("bytes") or 0)
            out.append(
                Thing(iid, "model", tag, str(it.get("title") or tag), size, False, list(it.get("features") or []), it)
            )
    for name, (sub, title, feats) in OWN.items():
        d = app / sub
        if d.is_dir():
            entry = {"path": str(d)}
            out.append(Thing(f"folder:{name}", "folder", name, title, _bytes([d]), False, list(feats), entry))
    if gone:
        with _lock(app):
            items = load(app)
            for iid in gone:
                items.pop(iid, None)
            _write(app, items)
    order = {"model": 0, "folder": 1, "program": 2}
    return sorted(out, key=lambda t: (order.get(t.kind, 3), t.title.lower()))


def _feature_on(app: App, f: str) -> bool:
    if f == "local_helper":
        return bool(app.settings.get("local_helper.on"))
    return app.is_on(f)


def _feature_title(app: App, f: str) -> str:
    if f == "local_helper":
        return "Offline helper"
    m = app.modules.get(f)
    return m.title if m is not None else f


def model_users(app: App) -> dict[str, list[str]]:
    """Which Ollama models are used now, and by what."""
    out: dict[str, list[str]] = {}

    def add(tag: str, who: str) -> None:
        if tag:
            ws = out.setdefault(norm(tag), [])
            if who not in ws:
                ws.append(who)

    lm = app.modules.get("local_models")
    if lm is not None and app.is_on("local_models"):
        try:
            for m in lm.wanted():
                add(m.get("tag", ""), lm.title)
        except Exception:  # a machine that can't be read: its models count as used
            for iid in load(app.paths.app):
                if iid.startswith("model:"):
                    add(iid[len("model:") :], lm.title)
    if app.is_on("gbrain") and lm is not None:
        try:
            for m in lm.wanted():
                if "embed" in str(m.get("key") or "") or "embed" in str(m.get("tag") or ""):
                    add(m.get("tag", ""), "GBrain")
        except Exception:
            pass
    if app.settings.get("local_helper.on"):
        try:
            add(app.helper.model().get("tag", ""), "Offline helper")
        except Exception:
            pass
    brain = app.settings.get("brain") or {}
    picks = [brain.get("main"), brain.get("classify")]
    fb = brain.get("fallback")
    picks += fb if isinstance(fb, list) else [fb]
    if "ollama" in picks:
        ms = (brain.get("models") or {}).get("ollama") or {}
        for tag in ms.values() if isinstance(ms, dict) else [ms]:
            add(str(tag or ""), "your AI settings (brain.models)")
    return out


def _brain_users(app: App, key: str) -> list[str]:
    brain = app.settings.get("brain") or {}
    picks = [str(brain.get("main") or "")]
    fb = brain.get("fallback")
    picks += [str(x) for x in (fb if isinstance(fb, list) else [fb]) if x]
    return ["your AI (brain.main or brain.fallback)"] if any(x.split(":")[0] == key for x in picks) else []


def users(app: App, t: Thing, all_things: list[Thing] | None = None, used: dict | None = None) -> list[str]:
    """What uses it now: removing it would break these."""
    if t.kind == "model":
        return list((used if used is not None else model_users(app)).get(t.name, []))
    who = [_feature_title(app, f) for f in t.features if _feature_on(app, f)]
    if t.kind == "program" and t.name in BRAINS:
        who += _brain_users(app, t.name)
    if t.kind == "program" and t.name == "ollama":
        used = used if used is not None else model_users(app)
        for ws in used.values():
            who += [w for w in ws if w not in who]
    if t.kind == "program" and t.name == "bun":  # GBrain runs on Bun: a GBrain of yours keeps it
        on_receipt = any(x.name == "gbrain" for x in all_things or [])
        if not on_receipt and _there(_bun_global("gbrain")):
            who.append("GBrain (installed by you)")
    return who


def things_for(app: App) -> list[Thing]:
    ts = things(app.paths.app)
    used = model_users(app)
    for t in ts:
        t.users = users(app, t, ts, used)
    return ts


def with_needs(chosen: list[Thing], all_things: list[Thing]) -> list[Thing]:
    """What goes along: Ollama's models on the receipt go with Ollama, GBrain (on the receipt) with Bun."""
    out = list(chosen)
    ids = {t.id for t in out}
    names = {t.name for t in out if t.kind == "program"}
    for t in all_things:
        if t.id in ids:
            continue
        if ("ollama" in names and t.kind == "model") or (
            "bun" in names and t.kind == "program" and (t.entry.get("package") or {}).get("manager") == "bun"
        ):
            out.append(t)
            ids.add(t.id)
    return out


def find(all_things: list[Thing], word: str) -> Thing | None:
    w = word.strip().lower()
    for t in all_things:
        if w in (t.id.lower(), t.name.lower(), t.title.lower()):
            return t
    return next((t for t in all_things if t.kind == "model" and t.name == norm(w)), None)


# ------------------------------------------------------------------------------------------------ removing
def _rm(p: Path) -> bool:
    try:
        if p.is_symlink() or p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)
    except OSError:
        return False
    return not _there(p)


def _pkg_remove(pre: Prereqs, pkg: dict) -> tuple[bool, str]:
    from kurooto.core import proc

    m = pkg.get("manager")
    if m == "winget":
        cmd = ["winget", "uninstall", "-e", "--id", pkg["id"], "--silent", "--accept-source-agreements"]
    elif m == "flatpak":
        cmd = ["flatpak", "uninstall", "--user", "-y", pkg["id"]]
    elif m == "brew":
        brew = _brew()
        if not brew:
            return False, "Homebrew isn't there to remove it"
        cmd = [brew, "uninstall", pkg["formula"]]
    elif m == "bun":
        bun = pre.items["bun"].find() if "bun" in pre.items else None
        if not bun:
            return True, ""  # Bun is gone, so is its global folder's use: the paths below go
        cmd = [bun, "remove", "-g", pkg["name"]]
    elif m == "npm":
        node = pre.items["node"].find() if "node" in pre.items else None
        if not node:
            return True, ""
        npm = Path(node).parent / ("npm.cmd" if os.name == "nt" else "npm")
        cmd = [str(npm), "uninstall", "-g", "--prefix", pkg["prefix"], pkg["name"]]
    else:
        return False, f"don't know how to remove a {m} package"
    if not shutil.which(cmd[0]) and not Path(cmd[0]).is_file():
        return False, f"{cmd[0]} isn't there to remove it"
    try:
        res = proc.run(cmd, timeout=900)
    except OSError as e:
        return False, str(e)[:200]
    return res.ok, (res.err or res.out).strip()[-200:]


def _remove_program(app_dir: Path, pre: Prereqs, t: Thing, going: set[str]) -> tuple[bool, str]:
    from kurooto.core import proc

    it = t.entry
    pkg = it.get("package") or {}
    if pkg:
        ok, err = _pkg_remove(pre, pkg)
        if not ok:
            return False, f"{t.title}: not removed ({err or 'its package manager said no'})"
    un = it.get("uninstaller") or []
    if un and Path(un[0]).is_file():
        try:
            res = proc.run(list(un), timeout=900)
        except OSError as e:
            return False, f"{t.title}: its uninstaller didn't run ({e})"[:200]
        if not res.ok:
            return False, f"{t.title}: its uninstaller failed"
    left = []
    for p in _roots(it.get("paths") or []):
        if _there(p) and safe(p, app_dir) and not _rm(p):
            left.append(str(p))
    kept = []
    for o in it.get("owns") or []:
        o = Path(o)
        if not _there(o) or not safe(o, app_dir):
            continue
        why = _still_holds(t.name, o, going) if o.is_dir() else ""
        if why:
            kept.append(f"{o} stays: {why}")
        elif not _rm(o):
            left.append(str(o))
    if left:
        return False, f"{t.title}: couldn't remove {', '.join(left[:3])} (in use, or no permission)"
    return True, f"{t.title}: removed ({t.size})" + (f"; {'; '.join(kept)}" if kept else "")


def remove(app_dir: Path, chosen: list[Thing], say: Say = print, app: App | None = None) -> tuple[bool, list[str]]:
    """Remove these (models first, then a program after what runs on it). Only what's on the receipt, and its paths
    are checked again here. Returns (all went, a line for each)."""
    app_dir = _abs(app_dir)
    pre = _prereqs(app_dir)
    lines: list[str] = []
    ok_all = True
    models = [t for t in chosen if t.kind == "model"]
    if models:
        exe = pre.items["ollama"].find() if "ollama" in pre.items else None
        done = _ollama_delete([t.name for t in models], exe)
        for t in models:
            if done.get(t.name):
                forget(app_dir, t.id)
                lines.append(f"{t.title}: removed ({t.size})")
            else:
                ok_all = False
                lines.append(f"{t.title}: not removed (Ollama didn't answer; try again with it running)")
            say(lines[-1])
    for t in [t for t in chosen if t.kind == "folder"]:
        d = Path(t.entry.get("path") or "")
        if _inside(d, app_dir) and d != app_dir and _rm(d):
            lines.append(f"{t.title}: removed ({t.size})")
        else:
            ok_all = False
            lines.append(f"{t.title}: couldn't remove {d}")
        say(lines[-1])
    progs = [t for t in chosen if t.kind == "program"]
    going = {t.name for t in progs}
    progs.sort(key=lambda t: 0 if (t.entry.get("package") or {}).get("manager") in ("bun", "npm") else 1)
    for t in progs:
        if t.name == "ollama" and app is not None:  # an Ollama Kurooto started stops first (exactly that process)
            lm = app.modules.get("local_models")
            if lm is not None:
                try:
                    lm.rest()
                except Exception:
                    pass
        ok, line = _remove_program(app_dir, pre, t, going)
        if ok:
            forget(app_dir, t.id)
        ok_all = ok_all and ok
        lines.append(line)
        say(line)
    if app is not None:
        app.events.emit("uninstalled", things=[t.id for t in chosen], ok=ok_all, bytes=sum(t.bytes for t in chosen))
    return ok_all, lines


# ------------------------------------------------------------------------------------------------ offering
def _open_offers(app: App) -> set[str]:
    out: set[str] = set()
    for q in app.ask.pending(source="uninstall"):
        out |= set((q.get("hook_payload") or {}).get("ids") or [])
    return out


def _listing(ts: list[Thing]) -> str:
    return ", ".join(f"{t.title} ({t.size})" for t in ts)


def offer(app: App, chosen: list[Thing], because: str) -> str:
    """Ask Remove / Keep for these (never asked twice while a question waits). A line saying so, or ""."""
    waiting = _open_offers(app)
    chosen = [t for t in chosen if t.id not in waiting and not t.users]
    if not chosen:
        return ""
    total = sum(t.bytes for t in chosen)
    lines = "\n".join(f"- {t.title}: {t.size}" for t in chosen)
    one = len(chosen) == 1
    app.ask.approval(
        f"{because} Kurooto installed {'this' if one else 'these'} for it, and nothing that's on uses "
        f"{'it' if one else 'them'} now:\n{lines}\n\nRemove {'it' if one else 'them'} ({human(total)})? Only what "
        "Kurooto installed goes; anything that was on this computer before it stays.",
        choices=[f"Remove ({human(total)})", "Keep"],
        hook=HOOK,
        hook_payload={"ids": [t.id for t in chosen]},
        source="uninstall",
        title="Remove what it installed?",
        why="asked",
        about=because[:80],
    )
    return (
        f" It installed {_listing(chosen)}; Remove or Keep is waiting for you (Today → Waiting for you, or your chat)."
    )


def after_off(app: App, feature: str) -> str:
    """A feature just went off: offer to remove what it brought that nothing else uses (uninstall.offer)."""
    if app.settings.get("uninstall.offer") is False:
        return ""
    try:
        ts = things_for(app)
        mine = [t for t in ts if feature in t.features and not t.users]
        if any(t.name == "ollama" and t.kind == "program" for t in mine):
            mine = with_needs(mine, [t for t in ts if not t.users])
        return offer(app, mine, f"{_feature_title(app, feature)} is off.")
    except Exception as e:  # turning a feature off never fails over this
        app.events.emit("uninstall_offer_failed", feature=feature, error=f"{type(e).__name__}: {e}"[:200])
        return ""


def after_hardware(app: App) -> str:
    """This computer's setup changed (hardware.force_profile, hardware.extra_models): offer the Ollama models
    Kurooto downloaded that nothing uses now."""
    if app.settings.get("uninstall.offer") is False:
        return ""
    try:
        ts = things_for(app)
        idle = [t for t in ts if t.kind == "model" and not t.users]
        return offer(app, idle, "This computer's new setup doesn't use some models.")
    except Exception as e:
        app.events.emit("uninstall_offer_failed", feature="hardware", error=f"{type(e).__name__}: {e}"[:200])
        return ""


def after_setting(app: App, key: str, value) -> str:
    """A setting changed on the dashboard: hardware.* and turning the offline helper off can leave things unused."""
    if key.startswith("hardware."):
        return after_hardware(app)
    if key == "local_helper.on" and value is False:
        return after_off(app, "local_helper")
    return ""


def _spawn(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, name="uninstall", daemon=True).start()


def answered(app: App, q: dict, answer: str) -> str:
    """Remove / Keep under the offer. Remove checks again that nothing uses each one now, then removes them in the
    background and says how it went."""
    if not str(answer or "").startswith("Remove"):
        return "Kept. `kurooto installed` (or /installed) lists it, and Remove there takes it away later."
    ids = list((q.get("hook_payload") or {}).get("ids") or [])
    ts = {t.id: t for t in things_for(app)}
    todo = [ts[i] for i in ids if i in ts and not ts[i].users]
    stays = [f"{ts[i].title} ({', '.join(ts[i].users)} uses it now)" for i in ids if i in ts and ts[i].users]
    if not todo:
        return "Nothing to remove" + (f": {'; '.join(stays)}." if stays else ": it's gone already.")

    def go() -> None:
        from kurooto.core.calm import ASKED

        try:
            ok, lines = remove(app.paths.app, todo, say=lambda s: None, app=app)
            text = ("Removed what you asked.\n" if ok else "Not everything went.\n") + "\n".join(lines)
        except Exception as e:  # never a silent failure
            text = f"Removing failed: {type(e).__name__}: {e}"[:300]
        if stays:
            text += "\nKept: " + "; ".join(stays)
        app.notify(text, kind="result", title="What it installed", why=ASKED)

    _spawn(go)
    return f"Removing {_listing(todo)}…"


# ------------------------------------------------------------------------------------------------ /installed
def _short(iid: str) -> str:
    return hashlib.sha256(iid.encode()).hexdigest()[:10]


def report(ts: list[Thing], pre: Prereqs | None = None, app: App | None = None) -> str:
    """The list, for the terminal and the chat (with `app`, the features by their titles)."""
    if not ts:
        head = "Kurooto hasn't installed anything outside Python on this computer (or it was removed since)."
    else:
        total = sum(t.bytes for t in ts)
        rows = []
        for t in ts:
            feats = [_feature_title(app, f) for f in t.features] if app is not None else t.features
            what = ", ".join(feats) if feats else "you or your AI"
            use = f"used by {', '.join(t.users)}" if t.users else "not used now"
            rows.append(f"- {t.title}: {t.size}, for {what}; {use} (kurooto remove {t.name})")
        head = (
            f"What Kurooto installed on this computer ({len(ts)}, {human(total)}):\n"
            + "\n".join(rows)
            + "\nRemoving one takes only what Kurooto put there; what a feature that's on uses stays until it's off."
        )
    if pre is not None:
        on = {t.name for t in ts if t.kind == "program"}
        yours = [p.title for k, p in pre.items.items() if k not in on and p.find()]
        if yours:
            head += "\nHere, but not installed by Kurooto (never removed by it): " + ", ".join(yours) + "."
    return head


def command(app: App, arg: str = "") -> tuple[str, list]:
    """/installed: the list, with a Remove… button for each one nothing uses (the button asks Remove / Keep)."""
    ts = things_for(app)
    buttons = [[(f"Remove {t.name}…", f"uni:{_short(t.id)}:ask")] for t in ts if not t.users][:8]
    return report(ts, app=app), buttons


def button(app: App, ref: str, act: str) -> str:
    """Remove… under /installed: the Remove / Keep question for that one (and what goes with it)."""
    ts = things_for(app)
    t = next((x for x in ts if _short(x.id) == ref), None)
    if t is None:
        return "It isn't on the list any more."
    if t.users:
        return f"{t.title} is used by {', '.join(t.users)}; turn that off first."
    said = offer(app, with_needs([t], [x for x in ts if not x.users]), f"You asked to remove {t.title}.")
    return "Asked: Remove or Keep." if said else "That question is waiting already."
