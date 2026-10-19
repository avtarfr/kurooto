"""Terminals: real terminals in the dashboard's Terminals tab (Alt+1 to Alt+4 switch between them):
    agent   the AI program you use (agy, Codex or Claude Code), started in your notes folder, as you'd run it yourself
    shell   your usual shell (PowerShell on Windows)
    ask     `kurooto ask`: plain English, like Telegram, in a terminal
    logs    Kurooto's log as it's written
They keep running when the page is closed; opening it again shows where they were. One that ends starts again when
you press a key in it. Each starts the first time you open it.

Only for a computer that's yours alone: anyone who can open your dashboard can type into these terminals. The
dashboard only answers this computer, needs a key that only its own page gets, and refuses other websites. On Linux,
Kurooto also checks that each request comes from your own user account, and refuses it if it can't tell.
"""

from __future__ import annotations

import base64
import contextlib
import io
import os
import shutil
import sys
import threading
import time
from pathlib import Path

from kurooto.modules.base import Module

LIMIT = 400_000  # bytes of each terminal's screen kept, to show again when a page opens
WINDOWS = sys.platform == "win32"


# ------------------------------------------------------------------------------------------- who's asking
def peer_uid(client_port: int, server_port: int, proc_net: str = "/proc/net") -> int | None:
    """Linux: the user account that owns the connection coming from client_port to our server_port, read from the
    kernel's socket table. None if it can't be found."""
    for name in ("tcp", "tcp6"):
        try:
            rows = Path(proc_net, name).read_text(encoding="ascii", errors="replace").splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            f = row.split()
            if len(f) < 8:
                continue
            try:
                lport = int(f[1].rsplit(":", 1)[1], 16)
                rport = int(f[2].rsplit(":", 1)[1], 16)
            except (IndexError, ValueError):
                continue
            if lport == client_port and rport == server_port:
                try:
                    return int(f[7])
                except ValueError:
                    return None
    return None


def same_user(client_address, server_port: int, platform: str | None = None, proc_net: str = "/proc/net") -> bool:
    """May this connection use the terminals? On Linux only if it's from this user account (refused when unsure);
    elsewhere the dashboard's own protections apply (see the module's description)."""
    if (platform or sys.platform) != "linux":
        return True
    try:
        uid = peer_uid(int(client_address[1]), int(server_port), proc_net)
    except (TypeError, ValueError, IndexError):
        return False
    return uid is not None and uid == os.getuid()


# --------------------------------------------------------------------------------------------- the ptys
class Pty:
    """A program in a pseudo-terminal: ptyprocess on macOS and Linux, pywinpty (ConPTY) on Windows."""

    def __init__(self, argv: list[str], cwd: str, env: dict, cols: int, rows: int):
        if WINDOWS:
            from winpty import PtyProcess  # pywinpty

            self.p = PtyProcess.spawn(argv, cwd=cwd, env=env, dimensions=(rows, cols))
        else:
            from ptyprocess import PtyProcess

            self.p = PtyProcess.spawn(argv, cwd=cwd, env=env, dimensions=(rows, cols))

    def read(self) -> bytes:
        """Blocks; b"" when the program has ended."""
        try:
            data = self.p.read(65536)
        except (EOFError, OSError):
            return b""
        return data.encode("utf-8", "replace") if isinstance(data, str) else data

    def write(self, data: bytes) -> None:
        self.p.write(data.decode("utf-8", "replace") if WINDOWS else data)

    def resize(self, cols: int, rows: int) -> None:
        self.p.setwinsize(rows, cols)

    def alive(self) -> bool:
        try:
            return bool(self.p.isalive())
        except Exception:
            return False

    def exit_code(self) -> int | None:
        try:
            if not WINDOWS:
                self.p.wait()
            return self.p.exitstatus
        except Exception:
            return None

    def kill(self) -> None:
        try:
            self.p.terminate(force=True)
        except Exception:
            pass


class Term:
    def __init__(self, name: str, profile: dict, push, spawn=Pty):
        self.name = name
        self.profile = profile
        self.push = push  # push(name, data bytes, viewers set, replay bool)
        self.spawn_fn = spawn
        self.lock = threading.Lock()
        self.buf = bytearray()
        self.pty = None
        self.alive = False
        self.size = (120, 32)
        self.viewers: set = set()
        self.owner = None
        self.started = 0.0

    def spawn(self) -> None:
        cols, rows = self.size
        try:
            self.pty = self.spawn_fn(self.profile["argv"], self.profile["cwd"], self.profile["env"], cols, rows)
        except Exception as e:  # the program isn't there, or the OS refused
            note = f"\r\n[couldn't start {self.profile['argv'][0]}: {e}]\r\n".encode()
            self.buf += note
            self.push(self.name, note, set(self.viewers), False)
            self.alive = False
            return
        self.alive, self.started = True, time.time()
        threading.Thread(target=self._reader, args=(self.pty,), name=f"term-{self.name}", daemon=True).start()

    def _reader(self, pty) -> None:
        while True:
            data = pty.read()
            if not data:
                break
            with self.lock:
                self.buf += data
                if len(self.buf) > LIMIT:
                    del self.buf[: len(self.buf) - LIMIT]
                viewers = set(self.viewers)
            self.push(self.name, data, viewers, False)
        code = pty.exit_code()
        note = f"\r\n\x1b[2m[{self.name} ended{f' ({code})' if code else ''}; press a key to start it again]\x1b[0m\r\n"
        with self.lock:
            if self.pty is pty:
                self.alive = False
            self.buf += note.encode()
            viewers = set(self.viewers)
        self.push(self.name, note.encode(), viewers, False)

    def attach(self, cid, cols: int, rows: int) -> None:
        with self.lock:
            self.viewers.add(cid)
            self.owner = cid
            self.size = (max(20, min(400, int(cols))), max(5, min(200, int(rows))))
            if self.pty is None:
                self.spawn()
            elif self.alive:
                self.pty.resize(*self.size)
            replay = bytes(self.buf)
        self.push(self.name, replay, {cid}, True)

    def leave(self, cid) -> None:
        with self.lock:
            self.viewers.discard(cid)
            if self.owner == cid:
                self.owner = None

    def resize(self, cid, cols: int, rows: int) -> None:
        with self.lock:
            if cid not in self.viewers:
                return
            self.owner = cid  # the terminal follows whoever last sized or typed in it
            self.size = (max(20, min(400, int(cols))), max(5, min(200, int(rows))))
            if self.alive and self.pty is not None:
                self.pty.resize(*self.size)

    def write(self, data: bytes) -> None:
        with self.lock:
            if not self.alive:
                self.buf += b"\x1bc"  # a fresh screen for the new run
                self.spawn()
                return
            pty = self.pty
        pty.write(data)

    def restart(self) -> None:
        self.stop()
        with self.lock:
            self.buf = bytearray()
            self.spawn()

    def stop(self) -> None:
        with self.lock:
            pty, self.pty, self.alive = self.pty, None, False
        if pty is not None:
            pty.kill()


# --------------------------------------------------------------------------------------------- the module
def _cli_has(command: str) -> bool:
    """Does this version's `kurooto` command have this subcommand?"""
    from kurooto import cli

    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            cli.main([command, "--help"])
    except SystemExit as e:
        return e.code in (0, None)
    except Exception:
        return False
    return True


class Terminals(Module):
    id = "terminals"
    title = "Terminals"
    description = "Real terminals in the dashboard: your AI's own program, a shell, `kurooto ask` and Kurooto's log."
    privacy = (
        "Stays on this computer. Only turn this on if you're the only person who uses this computer: anyone who can "
        "open your dashboard can type into these terminals."
    )

    def __init__(self, app):
        super().__init__(app)
        self.terms: dict[str, Term] = {}
        self._profiles: dict | None = None
        self._lock = threading.Lock()

    def ready(self):
        try:
            if WINDOWS:
                import winpty  # noqa: F401
            else:
                import ptyprocess  # noqa: F401
        except ImportError:
            return False, "the terminal library is missing (reinstall Kurooto)"
        return True, ""

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        if sys.platform == "linux" and not Path("/proc/net/tcp").exists():
            return False, "can't check who's connecting (/proc/net/tcp is missing), so terminals refuse everyone"
        running = [n for n, t in self.terms.items() if t.alive]
        return True, f"{len(self.profiles())} terminals" + (f", {len(running)} running" if running else "")

    def stop(self):
        self.shutdown()
        super().stop()

    def shutdown(self) -> None:
        for t in list(self.terms.values()):
            t.stop()
        self.terms.clear()

    # ------------------------------------------------------------------------------------------ profiles
    def _env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONSTARTUP", "PYTHONINSPECT")}
        env.update(TERM="xterm-256color", COLORTERM="truecolor", KUROOTO_TERMINAL="1")
        return env

    def _shell(self) -> list[str]:
        if WINDOWS:
            for name in ("pwsh", "powershell"):
                exe = shutil.which(name)
                if exe:
                    return [exe, "-NoLogo"]
            return [os.environ.get("COMSPEC") or "cmd.exe"]
        sh = os.environ.get("SHELL") or shutil.which("bash") or "/bin/sh"
        return [sh, "-l"] if Path(sh).name in ("bash", "zsh", "fish", "ksh", "sh", "dash") else [sh]

    def profiles(self) -> dict[str, dict]:
        """name -> {title, argv, cwd, env}; worked out once (the AI program can change in Settings: refresh())."""
        with self._lock:
            if self._profiles is not None:
                return self._profiles
            from kurooto import providers
            from kurooto.core import proc

            env, home = self._env(), str(Path.home())
            out: dict[str, dict] = {}
            main = self.app.settings.get("brain.main") or ""
            brain = providers.build(self.app, main) if main else None
            exe = getattr(brain, "exe", None) if brain is not None and getattr(brain, "kind", "") == "cli" else None
            if exe:
                argv = list(exe) if isinstance(exe, list) else proc.resolve_cmd_shim(str(exe))
                out["agent"] = {"title": brain.label, "argv": argv, "cwd": str(self.app.workspace), "env": env}
            out["shell"] = {"title": "Shell", "argv": self._shell(), "cwd": home, "env": env}
            if _cli_has("ask"):
                out["ask"] = {"title": "Ask", "argv": [sys.executable, "-m", "kurooto", "ask"], "cwd": home, "env": env}
            out["logs"] = {
                "title": "Logs",
                "argv": [sys.executable, "-m", "kurooto", "logs", "-f"],
                "cwd": home,
                "env": env,
            }
            self._profiles = out
            return out

    def refresh(self) -> None:
        with self._lock:
            self._profiles = None

    # ------------------------------------------------------------------------------------------- sessions
    def _push(self, name: str, data: bytes, viewers: set, replay: bool) -> None:
        live = getattr(self.app, "live", None)
        if live is None or not viewers:
            return
        live.push({"t": "pty", "n": name, "d": base64.b64encode(data).decode(), "replay": replay}, only=viewers)

    def term(self, name: str) -> Term | None:
        prof = self.profiles().get(name)
        if prof is None:
            return None
        with self._lock:
            t = self.terms.get(name)
            if t is None:
                t = self.terms[name] = Term(name, prof, self._push)
            return t

    def listing(self) -> list[dict]:
        return [
            {"name": n, "title": p["title"], "alive": bool(self.terms.get(n) and self.terms[n].alive)}
            for n, p in self.profiles().items()
        ]

    def handle(self, name: str, action: str, b: dict) -> tuple[int, dict]:
        """What the page sends: attach, input, resize, leave, restart."""
        t = self.term(name)
        if t is None:
            return 404, {"error": "no such terminal"}
        cid = b.get("cid")
        try:
            cols, rows = int(b.get("cols") or 120), int(b.get("rows") or 32)
        except (TypeError, ValueError):
            cols, rows = 120, 32
        if action == "attach":
            if cid is None:
                return 400, {"error": "no page id"}
            t.attach(cid, cols, rows)
            self.app.events.emit("terminal_opened", name=name)
        elif action == "input":
            data = str(b.get("data") or "")
            if len(data) > 100_000:
                return 413, {"error": "too much at once"}
            t.write(data.encode("utf-8"))
        elif action == "resize":
            t.resize(cid, cols, rows)
        elif action == "leave":
            t.leave(cid)
        elif action == "restart":
            t.restart()
        else:
            return 404, {"error": "unknown action"}
        return 200, {"ok": True, "alive": t.alive}

    def page_gone(self, cid) -> None:
        """A dashboard page closed: it no longer watches any terminal (the terminals keep running)."""
        for t in list(self.terms.values()):
            t.leave(cid)
