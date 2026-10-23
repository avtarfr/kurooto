"""The fence around add-ons added by link (core/addons.py): their code may reach only the hosts, and start only the
programs, that their card declared when you agreed to it.

    add(package, name, hosts, programs)   fence one add-on's Python package (kurooto_linked.<name>); core/overlay.py
                                          does this when it loads the add-on
    owner()                               the fenced add-on whose code is asking, or None (Kurooto's own code, your
                                          own add-ons folder, or a library called by either)
    allowed(host, hosts)                  is this host one of these ("host", or ".domain" for all of it)?

How it works: a Python audit hook (sys.addaudithook) sees each name lookup, socket connection and program start in
this process. It walks the call stack from the innermost frame: the first frame that belongs to Kurooto decides that
it's Kurooto's (its own rules apply: core/egress.py), and the first that belongs to a fenced add-on decides that the
add-on's card applies. Library frames (urllib, subprocess, requests) are passed over, and so are Kurooto's
pass-throughs (core/egress.py, core/proc.py), so an add-on can't reach an undeclared host by calling egress.urlopen
or start an undeclared program through proc.run. A message the add-on asks Kurooto to send you (app.notify) is
Kurooto's own request, made under Kurooto's own list.

What it isn't: a sandbox. Code you agreed to runs inside Kurooto with its access to this computer, and Python code
that sets out to get around a fence (a thread started on a library function alone, ctypes, a program it was allowed
that goes online by itself) can. The card and your consent are the line; the fence stops mistakes and casual
overreach, and says so in /egress and `kurooto doctor`. Loopback (this computer) is never fenced.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import PurePath

ROOT = "kurooto_linked"  # the package every add-on by link loads under (core/overlay.py)
PASS = ("kurooto.core.egress", "kurooto.core.proc", "kurooto.core.fence")  # Kurooto's pass-throughs
OWN = ("kurooto", "kurooto_addons")  # Kurooto's own code, and your own add-ons folder (core/overlay.py)
LOOPBACK = ("127.0.0.1", "localhost", "::1", "0.0.0.0")  # noqa: S104 (a host compared, nothing bound)
NET = frozenset({"socket.getaddrinfo", "socket.connect"})
RUN = frozenset({"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile"})
WATCHED = NET | RUN
WINDOW = 60.0  # seconds a lookup that was allowed lets this thread connect to what it found

_fences: dict[str, dict] = {}  # package -> {"name", "hosts", "programs", "online"}
_installed = False
_local = threading.local()
_mem = threading.Lock()


class ProgramFenced(PermissionError):
    """An add-on by link tried to start a program its card doesn't name."""

    def __init__(self, name: str, program: str, programs):
        allowed = ", ".join(programs) or "none"
        super().__init__(
            f"The add-on {name} may only start the programs on its card ({allowed}); {program or 'a shell'} isn't "
            "one. Kurooto didn't start it."
        )


def add(package: str, name: str, hosts=(), programs=(), online=()) -> None:
    """Fence an add-on's package: what it may reach and start from now on."""
    with _mem:
        _fences[package] = {
            "name": name,
            "hosts": tuple(str(h).lower() for h in hosts),
            "programs": tuple(_prog(p) for p in programs),
            "online": tuple(_prog(p) for p in online),
        }
    _install()


def remove(package: str) -> None:
    with _mem:
        _fences.pop(package, None)


def clear() -> None:
    with _mem:
        _fences.clear()


def fenced() -> dict[str, dict]:
    return dict(_fences)


def _prog(p: str) -> str:
    n = PurePath(str(p)).name.lower()
    for ext in (".exe", ".cmd", ".bat", ".com"):
        if n.endswith(ext):
            return n[: -len(ext)]
    return n


def allowed(host: str, hosts) -> bool:
    h = str(host or "").lower().rstrip(".").strip("[]")
    if not h or h in LOOPBACK or h.startswith("127."):
        return True
    for e in hosts or ():
        e = str(e).strip().lower()
        if e and (h == e.lstrip(".") or (e.startswith(".") and h.endswith(e))):
            return True
    return False


def owner(frame=None) -> dict | None:
    """The fenced add-on whose code is running here (innermost first), or None when Kurooto's own code is."""
    return _walk(frame or sys._getframe(1))[0]


def _walk(f) -> tuple[dict | None, bool]:
    """(the fence that applies, whether core/egress.py is on the way: it counts the request itself)."""
    via_egress = False
    while f is not None:
        mod = f.f_globals.get("__name__") or ""
        if mod in PASS:
            via_egress = via_egress or mod == "kurooto.core.egress"
        elif mod == ROOT or mod.startswith(ROOT + "."):
            for pkg, fe in _fences.items():
                if mod == pkg or mod.startswith(pkg + "."):
                    return fe, via_egress
            return {
                "name": mod.split(".")[1] if "." in mod else ROOT,
                "hosts": (),
                "programs": (),
                "online": (),
            }, via_egress
        elif any(mod == o or mod.startswith(o + ".") for o in OWN):
            return None, via_egress
        f = f.f_back
    return None, via_egress


def _install() -> None:
    global _installed
    if not _installed:
        sys.addaudithook(_hook)  # can't be taken off again: it does nothing while no add-on is fenced
        _installed = True


def _hook(event: str, args: tuple) -> None:
    if event not in WATCHED or not _fences:
        return
    fe, via_egress = _walk(sys._getframe(1))
    if fe is None:
        return
    if event == "socket.getaddrinfo":
        host = args[0]
        if host is None:
            return
        host = host.decode("ascii", "replace") if isinstance(host, (bytes, bytearray)) else str(host)
        if allowed(host, fe["hosts"]):
            _local.until = time.monotonic() + WINDOW
            if not via_egress and host.lower() not in LOOPBACK and not host.startswith("127."):
                _count(host, fe)
            return
        _local.until = 0.0
        _refuse(host, fe)
    elif event == "socket.connect":
        addr = args[1] if len(args) > 1 else None
        if not isinstance(addr, tuple) or not addr:
            return  # a local (unix) socket
        ip = str(addr[0])
        if allowed(ip, fe["hosts"]) or getattr(_local, "until", 0.0) > time.monotonic():
            return
        _refuse(ip, fe)
    else:
        prog = _program(event, args)
        if prog and prog in fe["programs"] and event in ("subprocess.Popen", "os.exec", "os.posix_spawn", "os.spawn"):
            if prog in fe["online"]:
                _count("", fe, via=prog)
            return
        raise ProgramFenced(fe["name"], prog, fe["programs"])


def _program(event: str, args: tuple) -> str:
    try:
        if event == "subprocess.Popen":
            exe, argv = args[0], args[1]
            if not exe:
                exe = argv if isinstance(argv, (str, bytes)) else (list(argv) or [""])[0]
                if isinstance(exe, (str, bytes)) and isinstance(argv, (str, bytes)):
                    exe = (str(exe).split() or [""])[0]
            return _prog(exe.decode() if isinstance(exe, bytes) else str(exe))
        if event in ("os.exec", "os.posix_spawn"):
            return _prog(str(args[0]))
        if event == "os.spawn":
            return _prog(str(args[1]))
    except (IndexError, TypeError, ValueError):
        pass
    return ""  # os.system and os.startfile: a shell or the desktop, never on a card


def _feature(fe: dict) -> str:
    return f"add-on {fe['name']}"


def _count(host: str, fe: dict, via: str = "") -> None:
    from kurooto.core import egress

    if egress.mode() != "off":
        egress.record(host, _feature(fe), via=via)


def _refuse(host: str, fe: dict) -> None:
    from kurooto.core import egress

    if egress.mode() != "off":
        egress.record(host, _feature(fe), blocked=True)
    raise egress.Fenced(host, fe["name"], fe["hosts"])
