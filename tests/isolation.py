"""Tests never see or change the computer they run on, even one with Kurooto installed and running.

start() runs once, from tests/conftest.py, before anything imports kurooto:

- a pretend home: HOME, USERPROFILE, XDG_{CONFIG,DATA,STATE,CACHE}_HOME, APPDATA, LOCALAPPDATA and KUROOTO_HOME
  (unless you set it for the run) point into a temporary folder, Path.home() follows HOME, and the keychain is
  keyring's null one (conftest gives every test a fresh pretend home of its own);
- stand-ins first on PATH: quiet notify-send/osascript (no popups), and loginctl, systemctl, launchctl and kurooto
  that refuse to do anything (only where the real ones exist, so `which` answers the same);
- a guard (an audit hook) that blocks and records any test opening for writing, creating, renaming or deleting
  anything in the real Kurooto install or the folders it changes (systemd user units, autostart, the app menu,
  ~/.gemini, the `kurooto` command), running the real loginctl/systemctl/launchctl/kurooto or a real program that
  changes the power mode (POWER: powerprofilesctl, sudo, ...; a test's own stand-ins are fine), or connecting to the
  real dashboard's port (binding it is refused too, so test servers move to the next port). A test that trips it
  fails; reads of those folders are only counted.
"""

from __future__ import annotations

import errno
import ipaddress
import json
import os
import shlex
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

DAEMON_PORT = 8770  # the dashboard's default port (web.port)
PROGRAMS = ("loginctl", "systemctl", "launchctl", "kurooto")  # never the real ones
QUIET = ("notify-send", "osascript")  # desktop popups: do nothing, successfully
# this computer's power mode (the Night performance add-on): never the real ones; a test's own stand-ins are fine
POWER = (
    "powerprofilesctl",
    "tuned-adm",
    "asusctl",
    "system76-power",
    "powercfg",
    "pmset",
    "sudo",
    "kurooto-legion-night",
)
REAL_POWER: dict[str, str] = {}  # where the real ones are (start())
_WRITE = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

ROOT: Path | None = None  # the session's temporary folder
BIN: Path | None = None  # the stand-ins
PORTS: set[int] = set()
PROTECTED: tuple[str, ...] = ()
KEEP_KUROOTO_HOME = bool(os.environ.get("KUROOTO_HOME"))  # set for the run by whoever runs the tests
violations: list[dict] = []  # {"test", "what", "path"}
reads: list[dict] = []
current = {"test": None}  # the running test's node id (conftest's hooks set it)
_inside = threading.local()


# ------------------------------------------------------------------------------------- the real folders
def _real_homes() -> list[Path]:
    homes = {os.environ.get("HOME"), os.environ.get("USERPROFILE"), os.path.expanduser("~")}
    try:
        import pwd

        homes.add(pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError, AttributeError):
        pass
    return [Path(h) for h in homes if h and os.path.isabs(h)]


def protected_paths(env: dict, homes: list[Path]) -> list[Path]:
    """The real install's folders and the places Kurooto changes outside them, on every OS."""
    out: list[Path] = []
    for h in homes:
        cfg, share, state, cache = h / ".config", h / ".local" / "share", h / ".local" / "state", h / ".cache"
        lib, local, roaming = h / "Library", h / "AppData" / "Local", h / "AppData" / "Roaming"
        out += [
            cfg / "kurooto",
            share / "kurooto",
            state / "kurooto",
            cache / "kurooto",
            cfg / "systemd" / "user",
            cfg / "autostart",
            share / "applications",
            h / ".gemini",
            h / ".local" / "bin" / "kurooto",
            lib / "Application Support" / "Kurooto",
            lib / "LaunchAgents",
            lib / "Logs" / "Kurooto",
            lib / "Caches" / "Kurooto",
            h / "Applications" / "Kurooto.app",
            h / "Applications" / "Kurooto Terminal.app",
            local / "Kurooto",
            local / "Programs" / "Kurooto",
            roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Kurooto.lnk",
            roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Kurooto Terminal.lnk",
        ]
    for var, subs in (
        ("XDG_CONFIG_HOME", ("kurooto", "systemd/user", "autostart")),
        ("XDG_DATA_HOME", ("kurooto", "applications")),
        ("XDG_STATE_HOME", ("kurooto",)),
        ("XDG_CACHE_HOME", ("kurooto",)),
        ("LOCALAPPDATA", ("Kurooto", "Programs/Kurooto")),
    ):
        if env.get(var) and os.path.isabs(env[var]):
            out += [Path(env[var], *s.split("/")) for s in subs]
    return out


def _real_ports(state_dirs: list[Path]) -> set[int]:
    """The running dashboard's port: the default, and whatever the real install wrote to its web.json."""
    ports = {DAEMON_PORT}
    for d in state_dirs:
        try:
            port = urlsplit(json.loads((d / "web.json").read_text(encoding="utf-8")).get("url") or "").port
        except (OSError, ValueError, AttributeError):
            continue
        if port:
            ports.add(port)
    return ports


# --------------------------------------------------------------------------------------------- the guard
def _norm(p) -> str | None:
    if isinstance(p, int) or p is None:
        return None
    try:
        return os.path.abspath(os.fsdecode(p))
    except (TypeError, ValueError):
        return None


def is_protected(p, resolve: bool = True) -> str | None:
    """The path (as text) when it's one of the real folders or inside one, else None."""
    s = _norm(p)
    if s is None:
        return None
    for cand in (s, os.path.realpath(s)) if resolve else (s,):
        if any(cand == r or cand.startswith(r + os.sep) for r in PROTECTED):
            return cand
    return None


def _record(what: str, path: str) -> None:
    violations.append({"test": current["test"], "what": what, "path": path})


def _refuse(what: str, path: str) -> None:
    _record(what, path)
    raise PermissionError(errno.EACCES, f"test isolation: tests don't {what} the real Kurooto install", path)


def _program(executable, args) -> list[str]:
    """The programs a process start would run: the executable, and the command a shell is handed."""
    out = []
    if executable is not None:
        out.append(os.fsdecode(executable))
    if isinstance(args, (list, tuple)) and len(args) >= 3 and os.fsdecode(args[1]) == "-c":
        try:
            words = shlex.split(os.fsdecode(args[2]))
        except ValueError:
            words = []
        out += words[:1]
    return out


def _check_program(prog: str, env) -> None:
    name = os.path.basename(prog).lower()
    for ext in (".exe", ".cmd", ".bat"):
        name = name.removesuffix(ext)
    if name in REAL_POWER:
        full = (
            os.path.abspath(prog) if os.path.dirname(prog) else shutil.which(prog, path=(env or os.environ).get("PATH"))
        )
        if full and os.path.realpath(full) == REAL_POWER[name]:
            _refuse(f"run {name} from", full)
        return
    if name not in PROGRAMS:
        return
    if os.path.dirname(prog):
        full = os.path.abspath(prog)
    else:  # found the way the process start finds it: on its own PATH when it has one
        full = shutil.which(prog, path=(env or os.environ).get("PATH"))
    if full and BIN is not None and os.path.dirname(os.path.abspath(full)) != str(BIN):
        _refuse(f"run {name} from", full)


def _local(host: str) -> bool:
    """This computer: loopback, or the unspecified address (which connects to it too)."""
    if host in ("", "localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return False
    return ip.is_loopback or ip.is_unspecified


def _hook(event: str, args: tuple) -> None:
    if getattr(_inside, "on", False):
        return
    _inside.on = True
    try:
        if event == "open":
            path, mode, flags = args
            writes = (isinstance(mode, str) and any(c in mode for c in "wax+")) or bool((flags or 0) & _WRITE)
            hit = is_protected(path, resolve=writes)
            if hit:
                if writes:
                    _refuse("write to", hit)
                reads.append({"test": current["test"], "path": hit})
        elif event in ("os.remove", "os.rmdir", "shutil.rmtree", "os.mkdir", "os.chmod", "os.utime", "os.truncate"):
            hit = is_protected(args[0])
            if hit:
                _refuse("change (" + event + ")", hit)
        elif event in ("os.rename", "os.link", "os.symlink"):
            for p in args[:2] if event == "os.rename" else args[1:2]:
                hit = is_protected(p)
                if hit:
                    _refuse("change (" + event + ")", hit)
        elif event == "sqlite3.connect":
            db = args[0]
            if not (isinstance(db, str) and "mode=ro" in db):
                hit = is_protected(db.removeprefix("file:").split("?")[0] if isinstance(db, str) else db)
                if hit:
                    _refuse("open a database in", hit)
        elif event == "subprocess.Popen":
            executable, argv, _cwd, env = args
            for prog in _program(executable, argv):
                _check_program(prog, env)
        elif event in ("os.posix_spawn", "os.exec"):
            _check_program(os.fsdecode(args[0]), args[2] if len(args) > 2 else None)
        elif event == "os.system":
            try:
                words = shlex.split(os.fsdecode(args[0]))
            except ValueError:
                words = []
            if words:
                _check_program(words[0], None)
        elif event in ("socket.connect", "socket.bind"):
            sock, address = args
            if isinstance(address, tuple) and len(address) >= 2 and address[1] in PORTS:
                host = str(address[0])
                if event == "socket.bind":  # like a running Kurooto had it: test servers take the next port
                    raise OSError(errno.EADDRINUSE, "test isolation: the real dashboard's port", host)
                if _local(host):
                    _record("connect to", f"{host}:{address[1]} (the running Kurooto)")
                    raise ConnectionRefusedError(
                        errno.ECONNREFUSED, "test isolation: tests don't talk to the running Kurooto"
                    )
    finally:
        _inside.on = False


# --------------------------------------------------------------------------------------------- the setup
def pretend_home(base: Path, env: dict | None = None) -> dict:
    """The variables for a pretend home in base (made if missing)."""
    home = base / "home"
    out = {
        "HOME": home,
        "USERPROFILE": home,
        "XDG_CONFIG_HOME": home / ".config",
        "XDG_DATA_HOME": home / ".local" / "share",
        "XDG_STATE_HOME": home / ".local" / "state",
        "XDG_CACHE_HOME": home / ".cache",
        "APPDATA": home / "AppData" / "Roaming",
        "LOCALAPPDATA": home / "AppData" / "Local",
    }
    if not KEEP_KUROOTO_HOME:
        out["KUROOTO_HOME"] = base / "kurooto"
    home.mkdir(parents=True, exist_ok=True)
    return {k: str(v) for k, v in out.items()}


def _stand_ins(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    win = sys.platform == "win32"
    for name in QUIET:
        (d / name).write_text("#!/bin/sh\nexit 0\n")
    if win:
        (d / "powershell.cmd").write_text("@exit /b 0\r\n")
    for name in PROGRAMS:
        if not shutil.which(name):
            continue  # not on this computer: `which` keeps saying so
        if win:
            (d / f"{name}.cmd").write_text(f"@echo {name}: not run in tests 1>&2\r\n@exit /b 1\r\n")
        else:
            (d / name).write_text(f"#!/bin/sh\necho '{name}: not run in tests' >&2\nexit 1\n")
    for f in d.iterdir():
        f.chmod(0o755)


def _home(cls=None) -> Path:
    """Path.home() in tests: the pretend home (HOME, or USERPROFILE on Windows), never this account's."""
    order = ("USERPROFILE", "HOME") if sys.platform == "win32" else ("HOME", "USERPROFILE")
    for var in order:
        if os.environ.get(var):
            return Path(os.environ[var])
    return Path(ROOT or tempfile.gettempdir()) / "home"


def start() -> None:
    global ROOT, BIN, PORTS, PROTECTED
    if ROOT is not None:
        return
    real_env = dict(os.environ)
    for name in POWER:
        found = shutil.which(name) or (f"/usr/local/bin/{name}" if os.path.isfile(f"/usr/local/bin/{name}") else None)
        if found:
            REAL_POWER[name] = os.path.realpath(found)
    homes = _real_homes()
    folders = protected_paths(real_env, homes)
    PROTECTED = tuple(sorted({s for p in folders for s in (os.path.abspath(p), os.path.realpath(p))}))
    states = [h / ".local" / "state" / "kurooto" for h in homes]
    if real_env.get("XDG_STATE_HOME"):
        states.append(Path(real_env["XDG_STATE_HOME"]) / "kurooto")
    PORTS = _real_ports(states)
    ROOT = Path(tempfile.mkdtemp(prefix="kurooto-tests-"))
    BIN = ROOT / "bin"
    _stand_ins(BIN)
    os.environ.update(pretend_home(ROOT))
    os.environ["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"  # never the real keychain
    os.environ["PATH"] = str(BIN) + os.pathsep + os.environ.get("PATH", "")
    Path.home = classmethod(_home)  # type: ignore[method-assign]
    sys.addaudithook(_hook)


def take(test: str) -> list[dict]:
    """This test's violations not reported yet (marks them reported)."""
    out = [v for v in violations if v["test"] == test and not v.get("reported")]
    for v in out:
        v["reported"] = True
    return out


def describe(found: list[dict]) -> str:
    return "Touched the real Kurooto install or its machine:\n" + "\n".join(
        f"  {v['what']} {v['path']}" + (f"  ({v['test']})" if v["test"] else "") for v in found
    )


def finish() -> None:
    if ROOT is not None:
        shutil.rmtree(ROOT, ignore_errors=True)
