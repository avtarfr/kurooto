"""Add-ons by link: `kurooto addons add <git url>` (or Features → Add-ons by link on the dashboard) brings in an add-on
someone published as a git repository. Nothing of it runs before you've seen its card and said yes.

    fetch(paths, url, ref)     clone it into a staging folder at one commit (a tag, a commit, or the newest commit of
                               a branch, turned into that commit's id: never a moving branch), read its manifest and
                               make its card. Returns a pending token and the card; nothing is added yet.
    install(paths, token, yes) your answer: yes moves it into <data>/addons/<name> (detached at that commit) and
                               records what you agreed to; anything else drops it.
    check_update(paths, name)  the same for a newer commit: its card again, and what changed (files, and on the card:
                               new hosts, programs, commands, code), then install(...) with your answer
    remove(paths, name)        moves it aside (<data>/addons/.kept/), with undo(paths, name) to put it back (an update
                               keeps the version before it the same way; the last KEEP of each are kept)
    loadable(paths)            what core/overlay.py loads at start: each add-on whose files are still exactly the ones
                               you agreed to (a digest of every file), else it's skipped with the reason

Official add-ons (core/official.py): the ones in Kurooto's own list, at the commit it pins; fetch(..., pin=commit)
checks out that commit, the card says "Official", and check_update moves one at an earlier official commit to the
newer one a newer Kurooto pins (still with the card and your yes).

The manifest, kurooto-addon.json at the repository's top (docs/wiki/dev/modules.md has the full format):

    {"name": "restic-backups", "title": "...", "description": "...", "version": "1.0.0", "kurooto": ">=0.6.0",
     "features": ["restic"], "commands": [{"name": "restic", "what": "..."}], "jobs": [{"id": "restic:backup",
     "what": "..."}], "tools": [], "hosts": [], "programs": [{"name": "restic", "online": true}], "classify": false}

The card is a contract, held when the add-on loads (core/overlay.py) and while it runs (core/fence.py): only the
features, commands, AI tools and jobs it names exist; its code reaches only the hosts it names and starts only the
programs it names; it sees your messages before Kurooto's own patterns only with "classify": true. Its skills/ and
prompts/ folders work as in your own add-ons folder.

Git runs without a terminal to ask for passwords, with no symbolic links, no submodules and no "ext::" transports;
the clone is counted in /egress as handed to git.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import proc
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.core.paths import Paths

register_defaults(
    "addons",
    {
        "on": True,  # load the add-ons you added by link (kurooto addons add); False: none load from the next start
        "official_updates": True,  # say once when Kurooto brings a newer official add-on you have; never updated alone
    },
)

MANIFEST = "kurooto-addon.json"
FILE = "addons.json"  # in the state folder: what you agreed to, what waits for your answer, what was kept
NAME = re.compile(r"[a-z][a-z0-9-]{1,39}")
FEATURE = re.compile(r"[a-z][a-z0-9_]{1,39}")
WORD = re.compile(r"[a-z0-9_]{1,40}")
ANY_WORD = re.compile(r"[a-z0-9_]{1,40}|\*")  # a command's name, or "*": ones you name yourself in its settings
HOST = re.compile(r"\.?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
PROGRAM = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}")
SHA = re.compile(r"[0-9a-f]{40}")
MAX_FILES = 2000
MAX_BYTES = 50_000_000
KEEP = 3  # versions kept aside per add-on (Remove, Update), for Undo
PENDING_S = 3600  # a card waits this long for your answer
FEATURE_NAME = "Add-ons by link"


class AddonError(Exception):
    """Something about an add-on Kurooto won't take, said in plain words."""


# ------------------------------------------------------------------------------------------------- places
def root(p: Paths) -> Path:
    return Path(p.data) / "addons"


def folder(p: Paths, name: str) -> Path:
    return root(p) / name


def package(name: str) -> str:
    """The Python package an add-on's modules/ loads as (core/fence.py fences it)."""
    return f"kurooto_linked.{name.replace('-', '_')}"


def _load(p: Paths) -> dict:
    d = jload(Path(p.state) / FILE, {}) or {}
    for k, v in (("addons", {}), ("pending", {}), ("kept", [])):
        if not isinstance(d.get(k), type(v)):
            d[k] = v
    return d


def _save(p: Paths, d: dict) -> None:
    jsave(Path(p.state) / FILE, d)


def _lock(p: Paths):
    Path(p.state).mkdir(parents=True, exist_ok=True)
    return Lock(Path(p.state), "addons", timeout=30)


def installed(p: Paths) -> dict[str, dict]:
    """Every add-on added by link: name -> its record (url, ref, commit, digest, manifest, added, updated)."""
    return _load(p)["addons"]


def kept(p: Paths, name: str | None = None) -> list[dict]:
    return [k for k in _load(p)["kept"] if name is None or k.get("name") == name]


# ------------------------------------------------------------------------------------------------ manifest
def _version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


def _named(raw, kind: str, rx: re.Pattern, key: str = "name") -> list[dict]:
    out = []
    for x in raw or []:
        d = {key: x, "what": ""} if isinstance(x, str) else dict(x) if isinstance(x, dict) else None
        if d is None or not isinstance(d.get(key), str) or not rx.fullmatch(d[key]):
            raise AddonError(f"its manifest lists a {kind} Kurooto can't read: {x!r}")
        out.append({key: d[key], "what": str(d.get("what") or "")[:200]})
    return out


def read_manifest(d: Path) -> dict:
    """The add-on's manifest, checked and tidied. Raises AddonError."""
    f = Path(d) / MANIFEST
    if not f.is_file():
        raise AddonError(f"it has no {MANIFEST} at its top, so it isn't a Kurooto add-on")
    try:
        m = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise AddonError(f"its {MANIFEST} isn't readable JSON ({e})") from e
    if not isinstance(m, dict):
        raise AddonError(f"its {MANIFEST} isn't a JSON object")
    name = str(m.get("name") or "")
    if not NAME.fullmatch(name):
        raise AddonError("its name has to be 2-40 lowercase letters, digits and dashes, starting with a letter")
    for k in ("features", "commands", "jobs", "tools", "hosts", "programs"):
        if not isinstance(m.get(k, []), list):
            raise AddonError(f'its manifest\'s "{k}" has to be a list')
    features = [str(x) for x in m.get("features") or []]
    bad = [x for x in features if not FEATURE.fullmatch(x)]
    if bad:
        raise AddonError(f"a feature id has to be lowercase letters, digits and _: {bad[0]!r}")
    jobs = _named(m.get("jobs"), "job", re.compile(r"[a-z][a-z0-9_]{1,39}:[a-z0-9_.-]{1,60}"), key="id")
    stray = [j["id"] for j in jobs if j["id"].split(":")[0] not in features]
    if stray:
        raise AddonError(f"the job {stray[0]} belongs to no feature it lists")
    hosts = []
    for h in m.get("hosts") or []:
        h = str(h).strip().lower()
        if not HOST.fullmatch(h) or (h.startswith(".") and h.count(".") < 2) or "." not in h.lstrip("."):
            raise AddonError(f"it asks for a host Kurooto won't allow: {h!r} (a name like api.example.org, or "
                             ".example.org for all of it)")  # fmt: skip
        hosts.append(h)
    programs = []
    for x in m.get("programs") or []:
        d = {"name": x} if isinstance(x, str) else x if isinstance(x, dict) else {}
        n = str(d.get("name") or "")
        if not PROGRAM.fullmatch(n) or "/" in n or "\\" in n:
            raise AddonError(f"it names a program Kurooto can't read: {x!r} (a program's name, not a path)")
        programs.append({"name": n, "online": bool(d.get("online")), "what": str(d.get("what") or "")[:200]})
    need = str(m.get("kurooto") or "").strip()
    if need and not re.fullmatch(r">=\s*\d+(?:\.\d+){0,2}", need):
        raise AddonError(f'its "kurooto" has to be like ">=0.6.0", not {need!r}')
    return {
        "name": name,
        "title": str(m.get("title") or name)[:80],
        "description": str(m.get("description") or "")[:400],
        "version": str(m.get("version") or "")[:20],
        "kurooto": need.replace(" ", ""),
        "features": features,
        "commands": _named(m.get("commands"), "command", ANY_WORD),  # "*": commands you name yourself
        "jobs": jobs,
        "tools": _named(m.get("tools"), "tool", WORD),
        "hosts": hosts,
        "programs": programs,
        "classify": bool(m.get("classify")),
        "homepage": str(m.get("homepage") or "")[:200],
        "license": str(m.get("license") or "")[:40],
    }


def fits(manifest: dict) -> str:
    """ "" when this version of Kurooto is new enough for it, else why not."""
    from kurooto import __version__

    need = manifest.get("kurooto") or ""
    if need and _version(__version__) < _version(need[2:]):
        return f"it needs Kurooto {need[2:]} or newer (this is {__version__}): update Kurooto first"
    return ""


# --------------------------------------------------------------------------------------------- the files
def files(d: Path) -> dict[str, str]:
    """Every file (but .git) by its path inside the add-on: its sha256. Raises AddonError for a link, or too much."""
    d = Path(d)
    out, total = {}, 0
    for top, dirs, names in os.walk(d, followlinks=False):
        rel_top = Path(top).relative_to(d)
        if rel_top == Path("."):
            dirs[:] = [x for x in dirs if x != ".git"]
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for x in [*dirs]:
            if (Path(top) / x).is_symlink():
                raise AddonError(f"it holds a link ({(rel_top / x).as_posix()}); add-ons can't")
        for n in names:
            f = Path(top) / n
            rel = (rel_top / n).as_posix()
            if f.is_symlink() or not f.is_file():
                raise AddonError(f"it holds a link or a special file ({rel}); add-ons can't")
            total += f.stat().st_size
            if len(out) >= MAX_FILES or total > MAX_BYTES:
                raise AddonError(f"it's too big for an add-on (over {MAX_FILES} files or {MAX_BYTES // 1_000_000} MB)")
            out[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def digest(d: Path) -> str:
    h = hashlib.sha256()
    for rel, sha in sorted(files(d).items()):
        h.update(f"{rel}\0{sha}\n".encode())
    return h.hexdigest()


def _code(d: Path) -> list[str]:
    m = Path(d) / "modules"
    return sorted(f.name for f in m.glob("*.py")) if m.is_dir() else []


def card(d: Path, manifest: dict, url: str = "", commit: str = "", ref: str = "") -> dict:
    """What the add-on adds, may reach and may start, and whether it runs code: what you agree to."""
    d = Path(d)
    code = _code(d)
    skills = sorted(x.parent.name for x in (d / "skills").glob("*/SKILL.md")) if (d / "skills").is_dir() else []
    prompts = sorted(x.stem for x in (d / "prompts").glob("*.md")) if (d / "prompts").is_dir() else []
    fs = files(d)
    warnings = []
    if code and not manifest["features"]:
        warnings.append("it has Python code but lists no features, so none of its code will load")
    if not code and manifest["features"]:
        warnings.append("it lists features but has no modules/*.py, so they won't appear")
    text = "\n".join(
        (d / "modules" / n).read_text(encoding="utf-8", errors="replace") for n in code if (d / "modules" / n).is_file()
    )
    if "classify_intent" in text and not manifest["classify"]:
        warnings.append("its code would see your messages first (classify_intent), but its card doesn't ask to, so "
                        "Kurooto won't let it")  # fmt: skip
    why = fits(manifest)
    if why:
        warnings.append(why)
    from kurooto.core import official

    off = official.match(url, commit, manifest["name"]) if url and commit else None
    return {
        **manifest,
        "official": off["tag"] if off else "",  # in Kurooto's official list, at its pinned commit (core/official.py)
        "url": url,
        "ref": ref,
        "commit": commit,
        "code": code,
        "skills": skills,
        "prompts": prompts,
        "files": len(fs),
        "size": sum((d / r).stat().st_size for r in fs),
        "warnings": warnings,
    }


def card_text(c: dict) -> str:
    """The card in words, for a terminal or a chat."""
    from kurooto.core.egress import size

    lines = [f"{c['title']} ({c['name']}{' ' + c['version'] if c.get('version') else ''})"]
    if c.get("description"):
        lines.append(c["description"])
    if c.get("url"):
        at = f" at {c['commit'][:12]}" if c.get("commit") else ""
        lines.append(f"From {c['url']}{at}{' (' + c['ref'] + ')' if c.get('ref') else ''}; it stays at that commit "
                     "until you update it.")  # fmt: skip
    if c.get("official"):
        lines.append(f"Official: in this Kurooto's list of official add-ons, at its {c['official']} commit.")
    adds = []
    if c["features"]:
        adds.append("features " + ", ".join(c["features"]))
    if c["commands"]:
        named = [f"/{x['name']}" for x in c["commands"] if x["name"] != "*"]
        if any(x["name"] == "*" for x in c["commands"]):
            named.append("commands you name yourself")
        adds.append("commands " + ", ".join(named))
    if c["jobs"]:
        adds.append("jobs " + ", ".join(x["id"] + (f": {x['what']}" if x["what"] else "") for x in c["jobs"]))
    if c["tools"]:
        adds.append("AI tools " + ", ".join(x["name"] for x in c["tools"]))
    if c["skills"]:
        adds.append("skills " + ", ".join(c["skills"]))
    if c["prompts"]:
        adds.append("prompts " + ", ".join(c["prompts"]))
    lines.append("Adds: " + ("; ".join(adds) if adds else "nothing Kurooto can see"))
    lines.append("May reach: " + (", ".join(c["hosts"]) if c["hosts"] else "nothing on the internet"))
    progs = [p["name"] + (" (goes online by itself: Kurooto can't see what it sends)" if p["online"] else "")
             for p in c["programs"]]  # fmt: skip
    lines.append("May start: " + (", ".join(progs) if progs else "no programs"))
    if c.get("classify"):
        lines.append("Sees each of your messages before Kurooto's own patterns (to pick what you're asking).")
    if c["code"]:
        lines.append(f"Runs code: YES. {len(c['code'])} Python file(s) run inside Kurooto with its access to this "
                     "computer (your files and keys). Kurooto holds it to this card, but that is a fence, not a "
                     "sandbox: only add it if you trust whoever wrote it.")  # fmt: skip
    else:
        lines.append("Runs code: no (skills, prompts or settings only).")
    lines.append(f"{c['files']} files, {size(c['size'])}.")
    lines += [f"Note: {w}." for w in c.get("warnings") or []]
    return "\n".join(lines)


def changes(old: Path | None, new: Path, old_manifest: dict | None, new_manifest: dict) -> dict:
    """What an update changes: files added, removed and changed (with lines), and what's new on the card."""
    a = files(old) if old and Path(old).is_dir() else {}
    b = files(new)
    changed = []
    for rel in sorted(set(a) & set(b)):
        if a[rel] == b[rel]:
            continue
        plus = minus = 0
        try:
            x = (Path(old) / rel).read_text(encoding="utf-8").splitlines()
            y = (Path(new) / rel).read_text(encoding="utf-8").splitlines()
            for ln in difflib.unified_diff(x, y, lineterm="", n=0):
                if ln.startswith("+") and not ln.startswith("+++"):
                    plus += 1
                elif ln.startswith("-") and not ln.startswith("---"):
                    minus += 1
        except (OSError, UnicodeDecodeError):
            pass
        changed.append({"file": rel, "plus": plus, "minus": minus})
    om = old_manifest or {}
    card_new = []
    for key, label in (("hosts", "may reach"), ("features", "features")):
        more = [x for x in new_manifest[key] if x not in (om.get(key) or [])]
        if more:
            card_new.append(f"{label}: {', '.join(more)}")
    for key, label, k in (("commands", "commands", "name"), ("tools", "AI tools", "name"), ("jobs", "jobs", "id"),
                          ("programs", "may start", "name")):  # fmt: skip
        had = {x[k] for x in om.get(key) or []}
        more = [x[k] for x in new_manifest[key] if x[k] not in had]
        if more:
            card_new.append(f"{label}: {', '.join(more)}")
    if new_manifest.get("classify") and not om.get("classify"):
        card_new.append("now sees your messages first")
    code_before = bool(old and _code(Path(old)))
    if _code(new) and not code_before:
        card_new.append("now runs code")
    return {
        "added": sorted(set(b) - set(a)),
        "removed": sorted(set(a) - set(b)),
        "changed": changed,
        "card": card_new,
    }


def changes_text(ch: dict) -> str:
    parts = []
    if ch["card"]:
        parts.append("New on its card: " + "; ".join(ch["card"]) + ".")
    files_said = []
    if ch["added"]:
        files_said.append(f"{len(ch['added'])} new ({', '.join(ch['added'][:6])}{'…' if len(ch['added']) > 6 else ''})")
    if ch["removed"]:
        files_said.append(f"{len(ch['removed'])} gone ({', '.join(ch['removed'][:6])})")
    if ch["changed"]:
        files_said.append(
            f"{len(ch['changed'])} changed ("
            + ", ".join(f"{x['file']} +{x['plus']} -{x['minus']}" for x in ch["changed"][:8])
            + ("…" if len(ch["changed"]) > 8 else "")
            + ")"
        )
    parts.append("Files: " + ("; ".join(files_said) if files_said else "the same") + ".")
    return "\n".join(parts)


# ----------------------------------------------------------------------------------------------------- git
def _git(p: Paths) -> str:
    from kurooto.core.prereqs import Prereqs

    try:
        exe = Prereqs(p.app, p.cache).items["git"].find()
    except Exception:
        exe = None
    exe = exe or proc.which("git")
    if not exe:
        raise AddonError("Git isn't installed (Notes sync's setup installs it, or your system's package manager)")
    return exe


def check_url(url: str) -> str:
    """A git address Kurooto will clone: https, ssh (ssh:// or git@host:path), file://, or a folder on this computer."""
    u = (url or "").strip()
    if not u or u.startswith("-") or any(c in u for c in "\n\r\t\0 "):
        raise AddonError("give the add-on's git address, e.g. https://github.com/someone/kurooto-habits")
    if "::" in u.split("/")[0] or re.match(r"(?i)^ext::|^fd::", u):
        raise AddonError("that kind of git address runs a program; Kurooto only clones https, ssh or a folder")
    if re.match(r"(?i)^(https|ssh|file)://", u) or re.match(r"^[\w.-]+@[\w.-]+:[^/\\]", u):
        return u
    if re.match(r"(?i)^http://", u):
        raise AddonError("use the https:// address: http could be changed on the way")
    if Path(u).expanduser().is_absolute() and Path(u).expanduser().is_dir():
        return str(Path(u).expanduser())
    raise AddonError("Kurooto clones https://, ssh:// (or git@host:path), file:// addresses or a folder's full path")


def _run_git(p: Paths, args: list[str], cwd: Path | None = None, timeout: float = 180) -> proc.Result:
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",  # never waits for a password nobody can type
        "GCM_INTERACTIVE": "never",
        "GIT_SSH_COMMAND": os.environ.get("GIT_SSH_COMMAND") or "ssh -o BatchMode=yes",
    }
    base = [_git(p)]
    for c in ("protocol.ext.allow=never", "protocol.fd.allow=never", "core.symlinks=false", "submodule.recurse=false",
              "advice.detachedHead=false"):  # fmt: skip
        base += ["-c", c]
    try:
        return proc.run([*base, *args], cwd=cwd, env=env, timeout=timeout)
    except OSError as e:
        raise AddonError(f"Git didn't run: {e}") from e


def _clone(p: Paths, url: str, ref: str, dest: Path) -> str:
    """Clone into dest and check out one commit (ref: a tag, a commit, a branch; "" the default branch's newest).
    Returns the commit's id."""
    from kurooto.core import egress

    egress.handed("git", FEATURE_NAME)
    r = _run_git(p, ["clone", "--quiet", "--no-checkout", "--config", "core.symlinks=false", "--", url, str(dest)])
    if not r.ok:
        raise AddonError(f"couldn't clone it: {(r.err or r.out).strip()[:300] or 'git failed'}")
    if ref and (ref.startswith("-") or not re.fullmatch(r"[\w./+-]{1,100}", ref)):
        raise AddonError(f"{ref!r} isn't a tag, branch or commit Kurooto can use")
    cands = [f"refs/tags/{ref}", f"refs/remotes/origin/{ref}", ref] if ref else ["HEAD"]
    commit = ""
    for c in cands:
        r = _run_git(p, ["rev-parse", "--verify", "--quiet", f"{c}^{{commit}}"], cwd=dest, timeout=30)
        if r.ok and SHA.fullmatch(r.out.strip()):
            commit = r.out.strip()
            break
    if not commit:
        raise AddonError(f"it has no tag, branch or commit called {ref!r}" if ref else "it has no commits")
    r = _run_git(p, ["checkout", "--quiet", "--detach", commit], cwd=dest, timeout=60)
    if not r.ok:
        raise AddonError(f"couldn't check out {commit[:12]}: {(r.err or r.out).strip()[:200]}")
    return commit


def _staging(p: Paths) -> Path:
    s = root(p) / ".staging"
    s.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for x in s.iterdir():  # cards nobody answered: gone after an hour
        try:
            if now - x.stat().st_mtime > PENDING_S:
                shutil.rmtree(x, ignore_errors=True)
        except OSError:
            pass
    return s


def _rmtree(d: Path) -> None:
    def unlock(fn, path, _exc):  # git's object files are read-only on Windows
        try:
            os.chmod(path, 0o700)
            fn(path)
        except OSError:
            pass

    if Path(d).exists():
        shutil.rmtree(d, onexc=unlock)


# ----------------------------------------------------------------------------------------- add and update
def fetch(p: Paths, url: str, ref: str = "", kind: str = "add", name: str = "", pin: str = "") -> dict:
    """Clone and make the card; nothing is added. {token, card, text, changes?}. Raises AddonError. pin: the commit
    to check out (an official add-on's, core/official.py), with ref kept only as its label (its tag)."""
    url = check_url(url)
    tok = uuid.uuid4().hex[:12]
    dest = _staging(p) / tok
    try:
        commit = _clone(p, url, pin or ref, dest)
        m = read_manifest(dest)
        if kind == "update" and m["name"] != name:
            raise AddonError(f"its name changed from {name} to {m['name']}: remove it and add it again")
        c = card(dest, m, url, commit, ref)
        dg = digest(dest)
    except BaseException:
        _rmtree(dest)
        raise
    out = {"token": tok, "card": c, "text": card_text(c)}
    with _lock(p):
        d = _load(p)
        have = d["addons"].get(m["name"])
        if kind == "add" and have:
            _rmtree(dest)
            raise AddonError(f"{m['name']} is added already (from {have['url']}): kurooto addons update {m['name']}")
        if kind == "update":
            ch = changes(folder(p, name), dest, (have or {}).get("manifest"), m)
            out["changes"], out["changes_text"] = ch, changes_text(ch)
        d["pending"] = {k: v for k, v in d["pending"].items() if time.time() - v.get("at", 0) < PENDING_S}
        d["pending"][tok] = {"kind": kind, "name": m["name"], "url": url, "ref": ref, "commit": commit,
                             "digest": dg, "manifest": m, "at": time.time()}  # fmt: skip
        _save(p, d)
    return out


def check_update(p: Paths, name: str, ref: str | None = None) -> dict:
    """A newer commit's card and changes, waiting for your answer; {"same": True} when there's nothing newer. An
    official add-on at an earlier official commit goes to the commit this Kurooto pins (core/official.py)."""
    from kurooto.core import official

    rec = installed(p).get(name)
    if not rec:
        raise AddonError(f"there's no add-on {name} (kurooto addons lists them)")
    e = official.update_for(rec) if ref is None else None
    if e is not None:
        out = fetch(p, rec["url"], e["tag"], kind="update", name=name, pin=e["commit"])
    else:
        out = fetch(p, rec["url"], (rec.get("ref") or "") if ref is None else ref, kind="update", name=name)
    if out["card"]["commit"] == rec["commit"]:
        drop(p, out["token"])
        return {"same": True, "commit": rec["commit"]}
    return out


def runs_code(p: Paths, token: str) -> bool:
    """Does the add-on whose card waits under this token run code (Python in modules/)?"""
    return bool(re.fullmatch(r"[0-9a-f]{12}", token or "")) and bool(_code(root(p) / ".staging" / token))


def drop(p: Paths, token: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{12}", token or ""):
        return
    with _lock(p):
        d = _load(p)
        d["pending"].pop(token, None)
        _save(p, d)
    _rmtree(root(p) / ".staging" / token)


def install(p: Paths, token: str, yes: bool, via: str = "typed") -> tuple[bool, str]:
    """Your answer to a card. Yes: it's added (or updated) at that commit; no: dropped, nothing kept."""
    if not re.fullmatch(r"[0-9a-f]{12}", token or ""):
        return False, "That card isn't waiting any more: look again."
    if not yes:
        drop(p, token)
        return False, "Not added; nothing was kept."
    with _lock(p):
        d = _load(p)
        pend = d["pending"].pop(token, None)
        src = root(p) / ".staging" / token
        if not pend or not src.is_dir() or time.time() - pend.get("at", 0) > PENDING_S:
            _save(p, d)
            _rmtree(src)
            return False, "That card isn't waiting any more (an hour passed, or it was answered): look again."
        try:
            same = digest(src) == pend["digest"]
        except AddonError:
            same = False
        if not same:
            _save(p, d)
            _rmtree(src)
            return False, "Its files changed after you saw the card, so it wasn't added. Look at it again."
        name, dest = pend["name"], folder(p, pend["name"])
        before = d["addons"].get(name)
        if pend["kind"] == "add" and before:
            _save(p, d)
            _rmtree(src)
            return False, f"{name} is added already: kurooto addons update {name}"
        if dest.exists():
            _keep(p, d, name, dest, before, "update" if before else "leftover")
        os.replace(src, dest)
        t = time.time()
        d["addons"][name] = {
            "name": name,
            "url": pend["url"],
            "ref": pend["ref"],
            "commit": pend["commit"],
            "digest": pend["digest"],
            "manifest": pend["manifest"],
            "added": (before or {}).get("added") or t,
            "updated": t,
            "consent": {"at": t, "via": via, "code": bool(_code(dest))},
        }
        _save(p, d)
    verb = "Updated" if before else "Added"
    return True, (
        f"{verb} {pend['manifest']['title']} at {pend['commit'][:12]}. Its features are under Features → Add-ons by "
        "link, each off until you turn it on." + (" Undo: kurooto addons undo " + name if before else "")
    )


def _keep(p: Paths, d: dict, name: str, src: Path, rec: dict | None, why: str) -> None:
    k = root(p) / ".kept"
    k.mkdir(parents=True, exist_ok=True)
    dest = k / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    os.replace(src, dest)
    d["kept"].append({"name": name, "dir": dest.name, "rec": rec, "why": why, "at": time.time()})
    mine = [x for x in d["kept"] if x["name"] == name]
    for old in mine[:-KEEP]:  # Kurooto's own copies past the last few
        _rmtree(k / old["dir"])
        d["kept"].remove(old)


def remove(p: Paths, name: str) -> tuple[bool, str]:
    """Moves it aside (its features stop at the next load); undo(name) puts it back."""
    with _lock(p):
        d = _load(p)
        rec = d["addons"].pop(name, None)
        if rec is None:
            return False, f"There's no add-on {name}."
        if folder(p, name).exists():
            _keep(p, d, name, folder(p, name), rec, "removed")
        _save(p, d)
    return True, f"Removed {rec['manifest']['title']}. Undo: kurooto addons undo {name} (or Undo on the dashboard)."


def undo(p: Paths, name: str) -> tuple[bool, str]:
    """Puts back what Remove or Update took away last (the current version, if any, is kept aside in its place)."""
    with _lock(p):
        d = _load(p)
        mine = [x for x in d["kept"] if x["name"] == name and x.get("rec")]
        if not mine:
            return False, f"Nothing of {name} is kept to put back."
        last = mine[-1]
        src = root(p) / ".kept" / last["dir"]
        if not src.is_dir():
            d["kept"].remove(last)
            _save(p, d)
            return False, f"The kept copy of {name} isn't there any more."
        rec = last["rec"]
        try:
            ok = digest(src) == rec.get("digest")
        except AddonError:
            ok = False
        if not ok:
            return False, f"The kept copy of {name} changed since, so it wasn't put back."
        d["kept"].remove(last)
        cur = d["addons"].get(name)
        if folder(p, name).exists():
            _keep(p, d, name, folder(p, name), cur, "undone")
        os.replace(src, folder(p, name))
        d["addons"][name] = rec
        _save(p, d)
    return True, f"Put back {rec['manifest']['title']} at {rec['commit'][:12]}."


# ------------------------------------------------------------------------------------------------ loading
def loadable(p: Paths) -> list[tuple[dict, Path, str]]:
    """(record, folder, problem) for each add-on by link; problem "" means it may load."""
    out = []
    for name, rec in sorted(installed(p).items()):
        f = folder(p, name)
        problem = ""
        if not f.is_dir():
            problem = "its folder is missing (kurooto addons remove, then add it again)"
        else:
            try:
                if digest(f) != rec.get("digest"):
                    problem = ("its files changed since you agreed to its card, so it didn't load: kurooto addons "
                               f"update {name} (or remove it and add it again)")  # fmt: skip
            except AddonError as e:
                problem = str(e)
        if not problem:
            problem = fits(rec.get("manifest") or {})
        out.append((rec, f, problem))
    return out


def show(p: Paths, name: str) -> str:
    rec = installed(p).get(name)
    if not rec:
        raise AddonError(f"there's no add-on {name}")
    try:
        c = card(folder(p, name), rec["manifest"], rec["url"], rec["commit"], rec.get("ref") or "")
        return card_text(c)
    except AddonError as e:
        return f"{name}: {e}"


def listing(p: Paths) -> list[dict]:
    """Each add-on by link for the dashboard and `kurooto addons`: its record, card and whether it may load."""
    out = []
    for rec, f, problem in loadable(p):
        try:
            c = card(f, rec["manifest"], rec["url"], rec["commit"], rec.get("ref") or "") if f.is_dir() else None
        except AddonError:
            c = None
        from kurooto.core import official

        off = official.match(rec["url"], rec["commit"], name=rec["name"])
        up = official.update_for(rec)
        out.append({**{k: rec[k] for k in ("name", "url", "ref", "commit", "added", "updated")},
                    "title": rec["manifest"]["title"], "problem": problem, "card": c,
                    "official": off["tag"] if off else "", "official_update": up["tag"] if up else ""})  # fmt: skip
    return out
