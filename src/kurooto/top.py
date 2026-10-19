"""`kurooto top`: a status board in your terminal. This computer (processor, memory, graphics card, disks, battery)
and Kurooto (running or not, battery mode, features on, AI requests, what's scheduled next, recent events).

    kurooto top          the live board: q quits, r refreshes now
    kurooto top --once   one screen, printed (for scripts, or a terminal that can't redraw)

It only reads: Kurooto's files are opened read-only, so it's safe to run while Kurooto is busy. Any terminal that
understands ANSI colours works (Windows 10 and later, macOS, Linux); NO_COLOR=1 turns colours off.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import textwrap
import time
from pathlib import Path

import psutil

from kurooto import __version__
from kurooto.core import proc
from kurooto.core.state import jload

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
SKIP_FS = ("squashfs", "tmpfs", "devtmpfs", "overlay", "proc", "sysfs", "autofs", "efivarfs", "fuse.portal")


# ------------------------------------------------------------------------------------------------- reading
def _ro(db: Path) -> sqlite3.Connection | None:
    """A read-only connection, or None if the database isn't there yet."""
    if not db.exists():
        return None
    try:
        return sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=1)
    except sqlite3.Error:
        return None


def _ago(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 172800:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _until(ts: float, now: float) -> str:
    d = ts - now
    if d <= 0:
        return "due"
    return "in " + _ago(d)


def _gb(n: float) -> str:
    return f"{n / 1024**3:.1f}G" if n >= 1024**3 else f"{n / 1024**2:.0f}M"


class Board:
    def __init__(self, p=None):
        from kurooto.core.paths import paths

        self.p = p or paths()
        psutil.cpu_percent(percpu=True)  # the first reading is always 0: prime it
        self._gpu: list[dict] = []
        self._gpu_at = 0.0
        self._slow: dict = {}
        self._slow_at = 0.0
        self._nvidia = proc.which("nvidia-smi")

    # -------------------------------------------------------------------------------------- the machine
    def machine(self) -> dict:
        cores = psutil.cpu_percent(percpu=True)
        vm, sw = psutil.virtual_memory(), psutil.swap_memory()
        try:
            load = os.getloadavg()
        except (AttributeError, OSError):
            load = None
        temp = None
        try:
            for name, entries in (psutil.sensors_temperatures() or {}).items():
                if entries and name in ("k10temp", "coretemp", "cpu_thermal", "acpitz", "zenpower"):
                    temp = round(entries[0].current)
                    break
        except (AttributeError, OSError):
            pass
        try:
            bat = psutil.sensors_battery()
        except Exception:
            bat = None
        disks, seen = [], set()
        try:
            parts = psutil.disk_partitions(all=False)
        except OSError:
            parts = []
        for part in parts:
            if part.fstype in SKIP_FS or part.device in seen or "/snap/" in part.mountpoint or "cdrom" in part.opts:
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
            except (OSError, PermissionError):
                continue
            if u.total < 1024**3 or (u.total, u.free) in seen:  # one container's volumes (APFS, btrfs) show once
                continue
            seen.add(part.device)
            seen.add((u.total, u.free))
            disks.append({"mount": part.mountpoint, "used": u.used, "total": u.total, "pct": u.percent / 100})
        return {
            "cpu": sum(cores) / max(1, len(cores)) / 100,
            "cores": [c / 100 for c in cores],
            "load": load,
            "temp": temp,
            "mem": vm.percent / 100,
            "mem_used": vm.total - vm.available,
            "mem_total": vm.total,
            "swap": sw.percent / 100,
            "swap_total": sw.total,
            "battery": None if bat is None else {"pct": bat.percent, "ac": bool(bat.power_plugged)},
            "disks": disks[:6],
            "gpus": self.gpus(),
            "uptime": time.time() - psutil.boot_time(),
        }

    def gpus(self) -> list[dict]:
        """Graphics cards: live load and memory for NVIDIA cards (nvidia-smi), else the names Kurooto detected."""
        if time.monotonic() - self._gpu_at < 5 and self._gpu_at:
            return self._gpu
        self._gpu_at = time.monotonic()
        out = []
        if self._nvidia:
            r = proc.run(
                [
                    self._nvidia,
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                timeout=4,
            )
            for line in r.out.splitlines() if r.ok else []:
                f = [x.strip() for x in line.split(",")]
                if len(f) >= 5:
                    try:
                        out.append(
                            {
                                "name": f[0],
                                "load": float(f[1]) / 100,
                                "mem_used": float(f[2]) * 1024**2,
                                "mem_total": float(f[3]) * 1024**2,
                                "temp": float(f[4]),
                            }
                        )
                    except ValueError:
                        continue
        if not out:
            hw = jload(self.p.state / "hardware.json", {}) or {}
            for g in (hw.get("machine") or {}).get("gpus") or []:
                out.append({"name": g.get("name", "graphics"), "vram": g.get("vram_gb")})
        self._gpu = out
        return out

    # ----------------------------------------------------------------------------------------- Kurooto
    def kurooto(self, force: bool = False) -> dict:
        if not force and self._slow and time.monotonic() - self._slow_at < 3:
            return self._slow
        self._slow_at = time.monotonic()
        p, now = self.p, time.time()
        from kurooto.core.config import Settings
        from kurooto.core.events import Events

        settings = Settings(p.config / "settings.json")
        daemon = jload(p.state / "daemon.json", {}) or {}
        running = bool(daemon.get("pid")) and proc.pid_alive(daemon["pid"])
        mode, why = "normal", ""
        pause = jload(p.state / "pause.json", {}) or {}
        if pause.get("paused") and (pause.get("until") is None or pause["until"] > now):
            mode = "paused"
            why = (
                "until you resume"
                if pause.get("until") is None
                else f"until {time.strftime('%H:%M', time.localtime(pause['until']))}"
            )
        else:
            try:
                bat = psutil.sensors_battery()
            except Exception:
                bat = None
            if bat is not None and not bat.power_plugged:
                setting = settings.get("power.on_battery") or "saver"
                mode = {"pause": "paused", "saver": "saver"}.get(setting, "normal")
                why = "on battery" if mode != "normal" else ""
        if (p.state / "off.json").exists() and not running:
            mode, why = "off", "turned off (kurooto on)"
        try:
            from kurooto.modules.catalog import CATALOG

            titles = {c.id: c.title for c in CATALOG}
        except Exception:
            titles = {}
        on = [titles.get(m, m) for m in settings.get("modules.enabled") or []]
        jobs, queued, active = [], 0, 0
        db = _ro(p.state / "jobs.db")
        if db is not None:
            try:
                for title, status, effort, seconds, created in db.execute(
                    "select title, status, effort, seconds, created from jobs order by created desc limit 6"
                ):
                    jobs.append(
                        {
                            "title": title or "",
                            "status": status,
                            "effort": effort,
                            "seconds": seconds,
                            "created": created,
                        }
                    )
                queued = db.execute("select count(*) from jobs where status='queued'").fetchone()[0]
                active = db.execute("select count(*) from jobs where status='running'").fetchone()[0]
            except sqlite3.Error:
                pass
            finally:
                db.close()
        sched = []
        db = _ro(p.state / "schedule.db")
        if db is not None:
            try:
                for key, payload, nxt in db.execute(
                    "select key, payload, next_run from schedule order by next_run limit 8"
                ):
                    try:
                        pl = json.loads(payload or "{}")
                    except ValueError:
                        pl = {}
                    what = pl.get("what") or pl.get("name") or ""
                    sched.append({"key": key, "what": str(what)[:60], "when": nxt})
            except sqlite3.Error:
                pass
            finally:
                db.close()
        events = []
        for e in Events(p.state).tail(12):
            extra = " ".join(
                f"{k}={v}"
                for k, v in e.items()
                if k not in ("ts", "kind") and isinstance(v, (int, float, bool, str)) and len(str(v)) < 24
            )
            events.append({"ts": e.get("ts", ""), "kind": e.get("kind", ""), "extra": extra[:80]})
        questions = 0
        for f in (p.state / "ask").glob("q*.json") if (p.state / "ask").is_dir() else []:
            if (jload(f, {}) or {}).get("status") in ("open", "later"):
                questions += 1
        backup = jload(p.state / "backups.json", {}) or {}
        sync = jload(p.state / "notes-sync.json", {}) or {}
        self._slow = {
            "running": running,
            "pid": daemon.get("pid") if running else None,
            "url": (jload(p.state / "web.json", {}) or {}).get("url") if running else None,
            "mode": mode,
            "why": why,
            "on": on,
            "jobs": jobs,
            "queued": queued,
            "active": active,
            "schedule": sched,
            "events": events,
            "questions": questions,
            "backup_at": backup.get("at") if backup.get("ok") else None,
            "backup_error": backup.get("error") if not backup.get("ok") else "",
            "sync_ok": sync.get("ok"),
            "sync_at": sync.get("at"),
        }
        return self._slow

    def collect(self, force: bool = False) -> dict:
        return {"machine": self.machine(), "kurooto": self.kurooto(force), "now": time.time()}


# ----------------------------------------------------------------------------------------------- drawing
class Style:
    def __init__(self, colour: bool, unicode: bool):
        self.colour, self.unicode = colour, unicode
        self.full, self.empty = ("█", "░") if unicode else ("#", "-")
        self.sep = "·" if unicode else "|"
        self.ell = "…" if unicode else "..."

    def c(self, code: str, s: str) -> str:
        return f"\x1b[{code}m{s}\x1b[0m" if self.colour else s

    def head(self, s: str) -> str:
        return self.c("1;36", s)

    def dim(self, s: str) -> str:
        return self.c("2", s)

    def ok(self, s: str) -> str:
        return self.c("32", s)

    def warn(self, s: str) -> str:
        return self.c("33", s)

    def bad(self, s: str) -> str:
        return self.c("31", s)

    def bar(self, frac: float | None, w: int) -> str:
        frac = max(0.0, min(1.0, frac or 0.0))
        n = round(frac * w)
        col = "32" if frac < 0.6 else "33" if frac < 0.85 else "31"
        return self.c(col, self.full * n) + self.dim(self.empty * (w - n))


def vlen(s: str) -> int:
    return len(ANSI.sub("", s))


def fit(s: str, w: int) -> str:
    """Cut a coloured line to w visible characters (escape codes kept) and pad it."""
    if vlen(s) <= w:
        return s + " " * (w - vlen(s))
    out, n, i = [], 0, 0
    while i < len(s) and n < w:
        m = ANSI.match(s, i)
        if m:
            out.append(m.group(0))
            i = m.end()
            continue
        out.append(s[i])
        n += 1
        i += 1
    return "".join(out) + "\x1b[0m" * ("\x1b[" in s) + " " * (w - n)


def machine_lines(m: dict, w: int, st: Style) -> list[str]:
    bw = max(8, min(40, w - 30))
    out = [st.head("THIS COMPUTER")]
    extra = []
    if m.get("load"):
        extra.append(f"load {m['load'][0]:.2f}")
    if m.get("temp"):
        extra.append(f"{m['temp']}°C" if st.unicode else f"{m['temp']}C")
    out.append(f"cpu   {st.bar(m['cpu'], bw)} {m['cpu'] * 100:3.0f}%  " + st.dim(" ".join(extra)))
    cores = m.get("cores") or []
    if cores and w >= 30:
        ticks = "▁▂▃▄▅▆▇█" if st.unicode else "._-=+*#@"
        row = "".join(ticks[min(7, int(c * 8))] for c in cores)
        for i in range(0, len(row), max(8, w - 8)):
            out.append(st.dim("      " + row[i : i + max(8, w - 8)]))
    out.append(
        f"mem   {st.bar(m['mem'], bw)} {m['mem'] * 100:3.0f}%  " + st.dim(f"{_gb(m['mem_used'])}/{_gb(m['mem_total'])}")
    )
    if m.get("swap_total"):
        out.append(f"swap  {st.bar(m['swap'], bw)} {m['swap'] * 100:3.0f}%")
    for g in m.get("gpus") or []:
        name = str(g.get("name", "graphics"))[: max(10, w - 6)]
        if "load" in g:
            out.append(f"gpu   {st.bar(g['load'], bw)} {g['load'] * 100:3.0f}%  " + st.dim(f"{g['temp']:.0f}C"))
            out.append(st.dim(f"      {name}, {_gb(g['mem_used'])}/{_gb(g['mem_total'])} memory"))
        else:
            vram = f", {g['vram']:g} GB" if g.get("vram") else ""
            out.append("gpu   " + st.dim(f"{name}{vram}"))
    b = m.get("battery")
    if b:
        state = st.ok("on the charger") if b["ac"] else st.warn("on battery")
        out.append(f"power {st.bar(b['pct'] / 100, bw)} {b['pct']:3.0f}%  {state}")
    out.append(st.head("DISKS"))
    for d in m.get("disks") or []:
        mount = d["mount"] if len(d["mount"]) <= 14 else st.ell + d["mount"][-(14 - len(st.ell)) :]
        out.append(
            f"{mount:<14} {st.bar(d['pct'], max(6, bw - 8))} {d['pct'] * 100:3.0f}%  "
            + st.dim(f"{_gb(d['total'] - d['used'])} free")
        )
    out.append(st.dim(f"up {_ago(m['uptime'])}"))
    return out


def kurooto_lines(k: dict, now: float, w: int, st: Style) -> list[str]:
    out = [st.head("KUROOTO")]
    if k["running"]:
        out.append(st.ok("running") + st.dim(f"  pid {k['pid']}  {k['url'] or ''}"))
    else:
        out.append(st.bad("not running") + st.dim("  (kurooto start)"))
    mode = {"normal": st.ok, "saver": st.warn, "paused": st.warn, "off": st.bad}.get(k["mode"], st.dim)(k["mode"])
    out.append(f"mode  {mode}" + st.dim(f"  {k['why']}" if k["why"] else ""))
    if k["questions"]:
        out.append(st.warn(f"{k['questions']} open question{'s' if k['questions'] > 1 else ''}") + st.dim("  (/q)"))
    bits = []
    if k.get("sync_at"):
        bits.append(
            ("notes synced " + _ago(now - k["sync_at"]) + " ago") if k.get("sync_ok") else st.bad("notes sync failing")
        )
    if k.get("backup_at"):
        bits.append("backup " + _ago(now - k["backup_at"]) + " ago")
    elif k.get("backup_error"):
        bits.append(st.bad("backup failing"))
    if bits:
        out.append(st.dim(f" {st.sep} ").join(bits))
    on = k["on"]
    out.append(st.head(f"FEATURES ON ({len(on)})"))
    out += textwrap.wrap(", ".join(on), max(10, w)) or [st.dim("none yet (open the dashboard: kurooto open)")]
    out.append(st.head("AI REQUESTS") + st.dim(f"  {k['active']} running, {k['queued']} waiting"))
    for j in k["jobs"][:5]:
        status = {"ok": st.ok("ok  "), "failed": st.bad("fail"), "running": st.warn("run "), "queued": st.dim("wait")}
        secs = f"{j['seconds']:.0f}s" if j.get("seconds") else ""
        out.append(
            f"{status.get(j['status'], j['status'])} {st.dim(_ago(now - (j['created'] or now)).rjust(4))} "
            f"{j['title'][: max(10, w - 22)]} {st.dim(secs)}"
        )
    if not k["jobs"]:
        out.append(st.dim("none yet"))
    out.append(st.head("NEXT"))
    for s in k["schedule"][:6]:
        what = s["what"] or s["key"]
        out.append(f"{_until(s['when'], now):>8}  {what[: max(10, w - 11)]}")
    if not k["schedule"]:
        out.append(st.dim("nothing scheduled"))
    out.append(st.head("RECENT"))
    for e in reversed(k["events"][-8:]):
        hhmm = e["ts"][11:16] if len(e["ts"]) >= 16 else e["ts"]
        out.append(f"{st.dim(hhmm)} {e['kind']} {st.dim(e['extra'])}")
    return out


def render(data: dict, width: int, height: int, colour: bool = True, unicode: bool = True) -> list[str]:
    """The board as lines of exactly `width` visible characters (at most `height` lines)."""
    st = Style(colour, unicode)
    width, height = max(30, width), max(10, height)
    k = data["kurooto"]
    clock = time.strftime("%H:%M:%S", time.localtime(data["now"]))
    head = st.head(f" KUROOTO {__version__}") + st.dim(f"  {clock}  q quit  r refresh")
    lines = [fit(head, width)]
    if width >= 100:
        lw = width // 2 - 1
        rw = width - lw - 3
        sep = " " + st.dim("│" if unicode else "|") + " "
        left = machine_lines(data["machine"], lw, st)
        right = kurooto_lines(k, data["now"], rw, st)
        for i in range(max(len(left), len(right))):
            a = fit(left[i] if i < len(left) else "", lw)
            b = fit(right[i] if i < len(right) else "", rw)
            lines.append(a + sep + b)
    else:
        for ln in machine_lines(data["machine"], width, st) + kurooto_lines(k, data["now"], width, st):
            lines.append(fit(ln, width))
    out = [fit(ln, width) for ln in lines[:height]]
    if not unicode:  # a terminal that can't show them: names and titles from your data too
        out = [ln.encode("ascii", "replace").decode("ascii") for ln in out]
    return out


# ------------------------------------------------------------------------------------------------ the loop
def _windows_ansi() -> bool:
    """Windows 10+: let this console understand ANSI escape codes."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        return bool(k.SetConsoleMode(h, mode.value | 0x0004))  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        return False


def _can_unicode(stream) -> bool:
    try:
        "█▁·".encode(stream.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


class Keys:
    """Single key presses without waiting for Enter, on every OS."""

    def __enter__(self):
        self.old = None
        if sys.platform != "win32" and sys.stdin.isatty():
            import termios
            import tty

            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def get(self, timeout: float) -> str:
        if sys.platform == "win32":
            import msvcrt

            end = time.monotonic() + timeout
            while time.monotonic() < end:
                if msvcrt.kbhit():
                    return msvcrt.getwch()
                time.sleep(0.05)
            return ""
        import select

        if not sys.stdin.isatty():
            time.sleep(timeout)
            return ""
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        return os.read(self.fd, 8).decode("utf-8", "replace")[:1] if r else ""

    def __exit__(self, *a):
        if self.old is not None:
            import termios

            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)


def main(once: bool = False, size: str = "") -> int:
    out = sys.stdout
    board = Board()
    colour = out.isatty() and not os.environ.get("NO_COLOR") and _windows_ansi()
    uni = _can_unicode(out)
    if once or not out.isatty():
        w, h = shutil.get_terminal_size((100, 50))
        m = re.fullmatch(r"(\d+)x(\d+)", size or "")
        if m:
            w, h = int(m[1]), int(m[2])
        time.sleep(0.2)  # a real processor reading needs a moment between samples
        for ln in render(board.collect(force=True), w, 10_000, colour, uni):
            out.write(ln.rstrip() + "\n")
        return 0
    out.write("\x1b[?1049h\x1b[?25l")
    try:
        with Keys() as keys:
            force = True
            while True:
                w, h = shutil.get_terminal_size((100, 40))
                frame = render(board.collect(force=force), w, h, colour, uni)
                force = False
                out.write("\x1b[H" + "\n".join(ln + "\x1b[K" for ln in frame) + "\x1b[J")
                out.flush()
                key = keys.get(1.0)
                if key in ("q", "Q", "\x1b", "\x03"):
                    break
                if key in ("r", "R"):
                    force = True
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        out.flush()
    return 0
