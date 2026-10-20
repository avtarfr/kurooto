"""`kurooto top`: a status board in your terminal, laid out like btop. This computer: the processor (a history graph,
every core, its speed, load, temperatures, fans), memory and swap, the graphics card, the network's down and up
rates, disks, the battery, and the busiest processes (Kurooto's own marked ✦). Kurooto: running or not, the battery
mode, the call line, the features that run programs of their own, today, what's due, AI requests, what's next,
study today, your projects and recent events, with today's event count and a trace that beats with each event.

    kurooto top          the live board: q quits, r refreshes now, c / m sort the processes by cpu / memory
    kurooto top --once   one screen, printed (for scripts, or a terminal that can't redraw)

It only reads: Kurooto's files are opened read-only, and the rest comes from the running Kurooto's own page (the same
figures as the dashboard), so it's safe to run while Kurooto is busy. Any terminal that understands ANSI colours
works (Windows 10 and later, macOS, Linux); the colours are the dashboard's (look.palette), in true colour where the
terminal has it; NO_COLOR=1 turns colours off. What a computer can't tell (temperatures and fans on most Windows and
Mac computers, a graphics card's live figures) is left out.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import sqlite3
import sys
import textwrap
import time
from importlib import resources
from pathlib import Path

import psutil

from kurooto import __version__
from kurooto.core import proc
from kurooto.core.scheduler import describe
from kurooto.core.state import jload
from kurooto.core.vitals import Sampler, own_pids

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
SKIP_FS = ("squashfs", "tmpfs", "devtmpfs", "overlay", "proc", "sysfs", "autofs", "efivarfs", "fuse.portal")
FALLBACK = {  # the "kuro" palette's dark colours, if the pages' own can't be read
    "bg": "#0b0f0a", "fg": "#dad3c8", "dim": "#95a682", "line": "#26311f", "panel": "#151b12", "accent": "#6b8a42",
    "accent-text": "#a6c07a", "lav": "#8dbdb3", "pink": "#d6967a", "peach": "#ddb866", "sand": "#e4d8b4",
    "rose": "#b9a6cc", "ok": "#8ccb98", "warn": "#e2b550", "bad": "#e8735a",
}  # fmt: skip


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
    if seconds < 86400:
        return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}"
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


def _bytes(n: float | None) -> str:
    n = float(n or 0)
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit in ("B", "K") else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}T"


def mix(a: str, b: str, t: float) -> str:
    ra, rb = (int(a[i : i + 2], 16) for i in (1, 3, 5)), (int(b[i : i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ra, rb, strict=True))


def _css_palettes() -> dict[str, dict]:
    """The pages' dark palettes by name, from style.css (its first `:root, body.home` block is "kuro")."""
    out: dict[str, dict] = {}
    try:
        css = resources.files("kurooto.web").joinpath("static", "style.css").read_text(encoding="utf-8")
    except (OSError, ModuleNotFoundError):
        css = ""
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if "prefers-color-scheme" in sel or "body.home" not in sel:
            continue
        vals = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", body))
        m = re.search(r'data-palette="([a-z0-9_-]+)"', sel)
        if vals:
            out.setdefault(m.group(1) if m else "kuro", {**FALLBACK, **vals})
    out.setdefault("kuro", dict(FALLBACK))
    return out


def colours(settings) -> dict:
    """The dashboard's dark colours (names without the leading --): look.palette through core/palette.py where this
    version has it (it also follows a theme file or the desktop's colours), else the palette's values in style.css."""
    try:
        from kurooto.core import palette as pal  # type: ignore[attr-defined]
    except ImportError:
        pal = None
    if pal is not None and hasattr(pal, "current"):
        try:
            got = pal.current(settings, "dark")  # it reads only the look settings
            return {
                **FALLBACK,
                **{k.lstrip("-"): v for k, v in got.items() if isinstance(v, str) and v.startswith("#")},
            }
        except Exception:  # an older or newer shape: the palette's own values below
            pass
    pals = _css_palettes()
    name = settings.get("look.palette") if settings is not None else None
    return pals.get(name or "kuro") or pals["kuro"]


class Board:
    def __init__(self, p=None):
        from kurooto.core.paths import paths

        self.p = p or paths()
        self.sampler = Sampler(self.p.state / "hardware.json")
        self._slow: dict = {}
        self._slow_at = 0.0
        self._own: dict[int, str] = {}
        self._own_at = 0.0

    # -------------------------------------------------------------------------------------- the machine
    def machine(self, force: bool = False) -> dict:
        """core/vitals.py's reading (the same as the dashboard's), and the processes with Kurooto's own marked."""
        m = self.sampler.sample(force)
        pid = (jload(self.p.state / "daemon.json", {}) or {}).get("pid")
        if force or time.monotonic() - self._own_at > 10:
            alive = bool(pid) and proc.pid_alive(pid)
            self._own, self._own_at = (own_pids(pid) if alive else {}), time.monotonic()
        m["procs"] = self.sampler.processes(own=self._own.get, n=40)
        if not m.get("gpus"):
            hw = jload(self.p.state / "hardware.json", {}) or {}
            m["gpus"] = [
                {"name": g.get("name", "graphics"), "vram_gb": g.get("vram_gb")}
                for g in (hw.get("machine") or {}).get("gpus") or []
            ]
        return m

    # ----------------------------------------------------------------------------------------- Kurooto
    def _board(self, url: str | None) -> dict | None:
        """Kurooto's side of the dashboard (features, the call line, today, what's due…) from the running page."""
        if not url:
            return None
        import urllib.request

        from kurooto.core.secrets import Secrets

        try:
            token = Secrets(self.p.config).get("web.token") or ""
            req = urllib.request.Request(f"{url}api/board", headers={"X-Kurooto": token})  # noqa: S310 (127.0.0.1)
            with urllib.request.urlopen(req, timeout=4) as r:  # noqa: S310 (our own page)
                got = json.loads(r.read())
            return got if isinstance(got, dict) and "features" in got else None
        except Exception:  # not answering, an older version, the keychain locked: the board does without
            return None

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
            if bat is not None and bat.power_plugged is False:
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
                for key, action, payload, nxt in db.execute(
                    "select key, action, payload, next_run from schedule order by next_run limit 8"
                ):
                    try:
                        pl = json.loads(payload or "{}")
                    except ValueError:
                        pl = {}
                    sched.append({"key": key, "what": describe(action, key, pl)[:60], "when": nxt})
            except sqlite3.Error:
                pass
            finally:
                db.close()
        events, beats, today = [], [], time.strftime("%Y-%m-%d")
        tail = Events(p.state).tail(400)
        for e in tail[-12:]:
            extra = " ".join(
                f"{k}={v}"
                for k, v in e.items()
                if k not in ("ts", "kind") and isinstance(v, (int, float, bool, str)) and len(str(v)) < 24
            )
            events.append({"ts": e.get("ts", ""), "kind": e.get("kind", ""), "extra": extra[:80]})
        for e in tail:  # the trace: when each recent event happened
            try:
                beats.append(time.mktime(time.strptime(str(e.get("ts", ""))[:19], "%Y-%m-%dT%H:%M:%S")))
            except ValueError:
                continue
        questions = 0
        for f in (p.state / "ask").glob("q*.json") if (p.state / "ask").is_dir() else []:
            if (jload(f, {}) or {}).get("status") in ("open", "later"):
                questions += 1
        backup = jload(p.state / "backups.json", {}) or {}
        sync = jload(p.state / "notes-sync.json", {}) or {}
        url = (jload(p.state / "web.json", {}) or {}).get("url") if running else None
        board = self._board(url) if running else None
        self._slow = {
            "running": running,
            "pid": daemon.get("pid") if running else None,
            "url": url,
            "mode": mode,
            "why": why,
            "on": on,
            "jobs": jobs,
            "queued": queued,
            "active": active,
            "schedule": sched,
            "events": events,
            "beats": beats,
            "events_today": (board or {}).get("events_today")
            or sum(1 for e in tail if str(e.get("ts", "")).startswith(today)),
            "questions": questions,
            "backup_at": backup.get("at") if backup.get("ok") else None,
            "backup_error": backup.get("error") if not backup.get("ok") else "",
            "sync_ok": sync.get("ok"),
            "sync_at": sync.get("at"),
            "board": board,
            "palette": colours(settings),
        }
        return self._slow

    def collect(self, force: bool = False) -> dict:
        return {"machine": self.machine(force), "kurooto": self.kurooto(force), "now": time.time()}


# ----------------------------------------------------------------------------------------------- drawing
def colour_depth() -> int:
    """24 (true colour), 256 or 8 colours, from what the terminal says it is."""
    term, ct = os.environ.get("TERM", ""), os.environ.get("COLORTERM", "").lower()
    known = ("iTerm.app", "vscode", "WezTerm", "ghostty", "Hyper", "rio", "Tabby")
    if ct in ("truecolor", "24bit") or os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM") in known:
        return 24
    if any(x in term for x in ("kitty", "direct", "alacritty", "foot")) or sys.platform == "win32":
        return 24  # Windows 10 and later consoles have true colour
    if "256" in term or not term:
        return 256
    return 8


def _rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


BASIC = ((0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0), (0, 0, 238), (205, 0, 205), (0, 205, 205), (229, 229, 229))


class Style:
    """The palette's colours; meters, graphs and boxes in unicode, or plain ASCII where the terminal can't."""

    def __init__(self, colour: bool, unicode: bool, pal: dict | None = None, depth: int | None = None):
        self.colour, self.unicode = colour, unicode
        self.pal = {**FALLBACK, **(pal or {})}
        self.depth = depth or colour_depth()
        self.full, self.empty = ("■", "■" if colour else "·") if unicode else ("#", "-")
        self.sep = "·" if unicode else "|"
        self.ell = "…" if unicode else "..."
        self._codes: dict[str, str] = {}

    def code(self, hexcol: str) -> str:
        if hexcol not in self._codes:
            r, g, b = _rgb(hexcol)
            if self.depth == 24:
                c = f"38;2;{r};{g};{b}"
            elif self.depth == 256:

                def q(v: int) -> int:  # the 6x6x6 colour cube
                    return 0 if v < 48 else 1 if v < 115 else (v - 35) // 40

                c = f"38;5;{16 + 36 * q(r) + 6 * q(g) + q(b)}"
            else:
                near = min(range(8), key=lambda i: sum((x - y) ** 2 for x, y in zip(BASIC[i], (r, g, b), strict=True)))
                c = str(30 + near)
            self._codes[hexcol] = c
        return self._codes[hexcol]

    def fg(self, hexcol: str, s: str, bold: bool = False) -> str:
        if not self.colour or not s:
            return s
        return f"\x1b[{'1;' if bold else ''}{self.code(hexcol)}m{s}\x1b[0m"

    def p(self, name: str, s: str, bold: bool = False) -> str:
        return self.fg(self.pal.get(name) or self.pal["fg"], s, bold)

    def grad(self, v: float) -> str:
        """Cool to warm (the palette's lavender, peach, pink), as on the dashboard."""
        v = max(0.0, min(1.0, v or 0.0))
        a, b, t = ("lav", "peach", v * 2) if v < 0.5 else ("peach", "pink", (v - 0.5) * 2)
        return mix(self.pal[a], self.pal[b], t)

    def head(self, s: str) -> str:
        return self.p("accent-text", s, bold=True)

    def dim(self, s: str) -> str:
        return self.p("dim", s)

    def v(self, s: str) -> str:
        return self.p("fg", s)

    def ok(self, s: str) -> str:
        return self.p("ok", s)

    def warn(self, s: str) -> str:
        return self.p("warn", s)

    def bad(self, s: str) -> str:
        return self.p("bad", s)

    def line(self, s: str) -> str:
        return self.fg(mix(self.pal["lav"], self.pal["bg"], 0.55), s)

    def bar(self, frac: float | None, w: int) -> str:
        """A meter: filled cells coloured by where they sit, cool to warm; the rest faint."""
        frac = max(0.0, min(1.0, frac or 0.0))
        n = round(frac * w)
        cells = "".join(self.fg(self.grad(i / max(1, w - 1)), self.full) for i in range(n))
        return cells + self.line(self.empty * (w - n))

    def pct(self, v: float) -> str:
        return self.fg(self.grad(min(1.0, v)), f"{v * 100:3.0f}%")

    def temp(self, c: float | None) -> str:
        if c is None:
            return ""
        s = f"{c:.0f}°" if self.unicode else f"{c:.0f}C"
        return self.bad(s) if c >= 90 else self.warn(s) if c >= 80 else self.v(s)


UP_DOTS, DOWN_DOTS = (
    ((0x40, 0x04, 0x02, 0x01), (0x80, 0x20, 0x10, 0x08)),
    ((0x01, 0x02, 0x04, 0x40), (0x08, 0x10, 0x20, 0x80)),
)


def braille(st: Style, values, width: int, height: int, peak: float = 1.0, down: bool = False) -> list[str]:
    """A btop-style area graph: two readings per character, four rows of dots per line, newest on the right,
    coloured by height; `down` hangs it from the top (the network's upload). ASCII terminals get # columns."""
    width, height = max(1, width), max(1, height)
    per = 2 if st.unicode else 1
    vals = [max(0.0, min(1.0, (v or 0) / (peak or 1))) for v in list(values)[-width * per :]]
    vals = [0.0] * (width * per - len(vals)) + vals
    left, right = DOWN_DOTS if down else UP_DOTS
    rows = []
    for r in range(height):
        level = r if down else height - 1 - r  # rows of dots below this line (from the base)
        out = []
        for c in range(width):
            if not st.unicode:
                out.append("#" if round(vals[c] * height * 4) - level * 4 >= 2 else " ")
                continue
            a, b = (max(0, min(4, round(vals[2 * c + i] * height * 4) - level * 4)) for i in (0, 1))
            if level == 0 and not a and vals[2 * c] > 0:
                a = 1  # something, however little
            if level == 0 and not b and vals[2 * c + 1] > 0:
                b = 1
            bits = sum(left[:a]) + sum(right[:b])
            out.append(chr(0x2800 + bits) if bits else " ")
        rows.append(st.fg(st.grad(level / max(1, height - 1)) if height > 1 else st.grad(0.4), "".join(out)))
    return rows


def trace(st: Style, beats: list[float], width: int, now: float, span: float = 600) -> str:
    """One line that beats with each event of the last ten minutes, newest on the right."""
    if not st.unicode or width < 4:
        return ""
    cols = [0] * (width * 2)
    for t in beats:
        age = now - t
        if 0 <= age < span:
            cols[min(len(cols) - 1, int((1 - age / span) * len(cols)))] += 1
    out = []
    for c in range(width):
        a, b = cols[2 * c], cols[2 * c + 1]
        out.append(
            chr(0x2800 + (0x40 if not a else 0x04 if a == 1 else 0x01) + (0x80 if not b else 0x20 if b == 1 else 0x08))
        )
    return st.p("accent-text", "".join(out))


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


def box(st: Style, title: str, lines: list[str], w: int, h: int | None = None, meta: str = "") -> list[str]:
    """A thin box with its name set into the top line (`┌─┤CPU├──┤16 threads├┐`), exactly h lines high."""
    w = max(8, w)
    inner = w - 2
    if st.unicode:
        tl, tr, bl, br, hz, vt, lt, rt = "┌", "┐", "└", "┘", "─", "│", "┤", "├"
    else:
        tl, tr, bl, br, hz, vt, lt, rt = "+", "+", "+", "+", "-", "|", "[", "]"
    head = st.line(tl + hz + lt) + st.head(title.upper()) + st.line(rt)
    meta = meta if vlen(meta) <= inner - vlen(head) - 4 else meta[: max(0, inner - vlen(head) - 5)] + st.ell
    tail = (st.line(lt) + st.dim(meta) + st.line(rt)) if meta else ""
    room = w - vlen(head) - vlen(tail) - 1
    top = fit(head + st.line(hz * max(0, room)) + tail + st.line(tr), w)
    h = max(2, h if h is not None else len(lines) + 2)
    body = (lines + [""] * h)[: h - 2]
    side = st.line(vt)
    return [top] + [side + fit(" " + ln, inner) + side for ln in body] + [st.line(bl + hz * inner + br)]


def beside(a: list[str], b: list[str], wa: int, wb: int) -> list[str]:
    return [
        fit(a[i] if i < len(a) else "", wa) + fit(b[i] if i < len(b) else "", wb) for i in range(max(len(a), len(b)))
    ]


# ------------------------------------------------------------------------------------------- this computer
def cpu_box(m: dict, w: int, st: Style, compact: bool) -> list[str]:
    inner = w - 3
    cores = m.get("cores") or []
    hist = (m.get("hist") or {}).get("cpu") or []
    graph = braille(st, hist, inner - 5, 2 if compact else 4)
    graph[0] = fit(graph[0], inner - 5) + " " + st.pct(m["cpu"])
    lines = list(graph)
    ch = m.get("core_hist") or []
    if compact or inner < 44:  # one line of ticks, one per core
        ticks = "▁▂▃▄▅▆▇█" if st.unicode else "._-=+*#@"
        lines.append(st.dim("cores ") + "".join(st.fg(st.grad(c), ticks[min(7, int(c * 8))]) for c in cores))
    else:
        cols = 1 if len(cores) <= 8 else 2 if len(cores) <= 24 else 3 if len(cores) <= 48 else 4
        cw, rows = inner // cols, math.ceil(len(cores) / cols)
        mw = max(4, min(12, cw - 12 - (10 if cols <= 2 else 0)))
        gw = max(0, cw - mw - 13) if cols <= 2 else 0
        for r in range(rows):
            cells = []
            for c in range(cols):
                i = c * rows + r
                if i < len(cores):
                    cell = st.dim(f"C{i:<3}") + st.bar(cores[i], mw) + " " + st.pct(cores[i])
                    if gw > 2 and i < len(ch):
                        cell += " " + braille(st, ch[i], gw, 1)[0]
                    cells.append(fit(cell, cw - 1) + " ")
            lines.append("".join(cells))
    info = []
    if m.get("freq"):
        info.append(st.v(f"{m['freq']['cur'] / 1000:.1f}") + st.dim(" GHz"))
    if m.get("load"):
        info.append(st.dim("load ") + st.v(" ".join(f"{x:.2f}" for x in m["load"])))
    t = m.get("temps") or {}
    for key in ("cpu", "disk"):
        if t.get(key) is not None:
            info.append(st.dim(f"{key} ") + st.temp(t[key]))
    if m.get("fans"):
        info.append(st.dim("fans ") + st.v("/".join(str(f) for f in m["fans"])) + st.dim(" rpm"))
    if info:
        lines.append("  ".join(info))
    meta = f" {st.sep} ".join(x for x in (m.get("cpu_name") or "", f"{len(cores)} threads") if x)
    return box(st, "cpu", lines, w, meta=meta)


def mem_box(m: dict, w: int, st: Style, h: int | None = None) -> list[str]:
    mx = m.get("mem") or {}
    total = mx.get("total") or 1
    bw = max(4, w - 18)

    def row(k: str, frac: float, val: str) -> str:
        return st.dim(f"{k:<6}") + st.bar(frac, bw) + " " + st.v(val.rjust(7))

    lines = [
        row("used", mx.get("used", 0) / total, _bytes(mx.get("used"))),
        row("cache", mx.get("cached", 0) / total, _bytes(mx.get("cached"))),
        row("avail", mx.get("available", 0) / total, _bytes(mx.get("available"))),
    ]
    sw = m.get("swap")
    if sw:
        lines.append(row("swap", sw["pct"], _bytes(sw["used"])))
    return box(st, "mem", lines, w, h, meta=_bytes(mx.get("total")))


def gpu_box(m: dict, w: int, st: Style, h: int | None = None) -> list[str] | None:
    g, known = m.get("gpu"), (m.get("gpus") or [None])[0]
    if not g and not known:
        return None
    name = re.sub(r"^NVIDIA (GeForce )?", "", (g or {}).get("name") or (known or {}).get("name") or "")
    if g and not g.get("asleep"):
        bw = max(4, w - 20)
        lines = [
            st.dim("use   ") + st.bar(g["util"], bw) + " " + st.pct(g["util"]).rjust(7),
            st.dim("vram  ") + st.bar(g["mem_used"] / (g["mem_total"] or 1), bw) + " "
            + st.v(f"{_gb(g['mem_used'])}/{_gb(g['mem_total'])}".rjust(9)),
        ]  # fmt: skip
        bits = [st.temp(g.get("temp"))] if g.get("temp") is not None else []
        if g.get("watts") is not None:
            bits.append(st.v(f"{g['watts']:.0f}W") + (st.dim(f"/{g['watts_max']:.0f}W") if g.get("watts_max") else ""))
        tail = "  ".join(bits)
        lines.append(
            tail + "  " + braille(st, (m.get("hist") or {}).get("gpu") or [], max(1, w - 6 - vlen(tail)), 1)[0]
        )
    else:
        lines = [st.dim("asleep (saving power)" if g and g.get("asleep") else "no live figures")]
        vram = (known or {}).get("vram_gb")
        if vram:
            lines.append(st.dim("vram ") + st.v(f"{vram:g} GB"))
    return box(st, "gpu", lines, w, h, meta=name)


def net_box(m: dict, w: int, st: Style, h: int | None = None) -> list[str]:
    n, hist = m.get("net") or {}, m.get("hist") or {}
    peak = max([10240.0, *(hist.get("rx") or []), *(hist.get("tx") or [])])
    gw = max(4, w - 15)
    arrows = ("↓", "↑") if st.unicode else ("v", "^")
    rx = braille(st, hist.get("rx") or [], gw, 1, peak)[0]
    tx = braille(st, hist.get("tx") or [], gw, 1, peak, down=True)[0]
    lines = [
        st.p("lav", arrows[0]) + " " + st.v(f"{_bytes(n.get('rx'))}/s".ljust(9)) + rx,
        st.p("pink", arrows[1]) + " " + st.v(f"{_bytes(n.get('tx'))}/s".ljust(9)) + tx,
        st.dim("total ") + st.v(f"{arrows[0]}{_bytes(n.get('rx_total'))} {arrows[1]}{_bytes(n.get('tx_total'))}"),
    ]
    return box(st, "net", lines, w, h, meta=n.get("dev") or "no connection")


def disk_box(m: dict, w: int, st: Style, h: int | None = None) -> list[str]:
    lines = []
    for d in (m.get("disks") or [])[:4]:
        mount = d["mount"] if len(d["mount"]) <= 14 else st.ell + d["mount"][-(14 - len(st.ell)) :]
        lines.append(
            f"{mount:<14} {st.bar(d['pct'], max(4, w - 34))} {st.pct(d['pct'])} "
            + st.dim(f"{_gb(d['total'] - d['used'])} free")
        )
    b = m.get("battery")
    if b:
        state = st.dim("power") if b.get("ac") is None else st.ok("ac") if b["ac"] else st.warn("battery")
        extra = (st.dim(f" {_ago(b['secs'])} left") if b.get("secs") else "") + (
            st.dim(f" {b['watts']:.1f}W") if b.get("watts") else ""
        )
        lines.append(st.dim("power ") + state + " " + st.v(f"{b['pct']:.0f}%") + extra)
    io = m.get("io")
    meta = f"r {_bytes(io['read'])}/s w {_bytes(io['write'])}/s" if io else ""
    return box(st, "disks", lines or [st.dim("none to show")], w, h, meta=meta)


def proc_box(m: dict, w: int, h: int, st: Style, sort: str) -> list[str]:
    rows = sorted(m.get("procs") or [], key=lambda r: (-r["mem"], 0) if sort == "mem" else (-r["cpu"], -r["mem"]))
    nw = max(8, w - 34)
    mark = "✦" if st.unicode else "*"
    lines = [st.dim(f"{'pid':>8} {'process':<{nw}} {'thr':>4} {'cpu':>6} {'mem':>7}")]
    for r in rows[: max(0, h - 3)]:
        name = (f"{mark} " + ("kurooto" if r["own"] == "kurooto" else r["name"])) if r.get("own") else r["name"]
        name = name[:nw].ljust(nw)
        lines.append(
            st.dim(f"{r['pid']:>8}") + " " + (st.p("pink", name) if r.get("own") else st.v(name)) + " "
            + st.dim(f"{r.get('threads') or '':>4}") + " " + st.fg(st.grad(min(1, r["cpu"])), f"{r['cpu'] * 100:5.1f}%")
            + " " + st.v(f"{_bytes(r['mem']):>7}")
        )  # fmt: skip
    return box(st, "processes", lines, w, h, meta=f"by {sort} {st.sep} c/m {st.sep} {mark} kurooto")


def machine_column(m: dict, w: int, avail: int | None, st: Style, sort: str = "cpu") -> list[str]:
    """CPU, then MEM and GPU, NET and DISKS (side by side when there's room), then the processes in what's left
    (`avail` lines; None: a dozen)."""
    out = cpu_box(m, w, st, compact=avail is not None and avail < 44)
    for left, right in ((mem_box, gpu_box), (net_box, disk_box)):
        b = right(m, w - w // 2, st) if w >= 74 else None
        if b is not None:
            h = max(len(left(m, w // 2, st)), len(b))
            out += beside(left(m, w // 2, st, h), right(m, w - w // 2, st, h), w // 2, w - w // 2)
        else:
            out += left(m, w, st) + (right(m, w, st) or [])
    room = (avail - len(out)) if avail is not None else 15
    if room >= 5:
        out += proc_box(m, w, room, st, sort)
    return out


# ------------------------------------------------------------------------------------------------ Kurooto
def _service_line(st: Style, mark: str, name: str, pr: dict) -> str:
    return (
        st.p("pink", mark) + " " + st.v(f"{name[:13]:<14}") + st.dim("cpu ") + st.v(f"{pr['cpu'] * 100:4.1f}%")
        + st.dim("  mem ") + st.v(f"{_bytes(pr['mem']):>6}") + st.dim("  up ") + st.v(_ago(pr["up"]))
        + st.dim(f"  {pr['threads']} threads")
    )  # fmt: skip


def kurooto_column(k: dict, now: float, w: int, avail: int | None, st: Style) -> list[str]:
    b = k.get("board") or {}
    out: list[str] = []
    mark = "✦" if st.unicode else "*"
    # KUROOTO: running, the mode, the call line, Kurooto's own process and the features' programs, what's on
    lines = []
    if k["running"]:
        lines.append(st.ok("● running" if st.unicode else "running") + st.dim(f"  pid {k['pid']}  {k['url'] or ''}"))
    else:
        lines.append(st.bad("● not running" if st.unicode else "not running") + st.dim("  (kurooto start)"))
    mode = {"normal": st.ok, "saver": st.warn, "paused": st.warn, "off": st.bad}.get(k["mode"], st.dim)(k["mode"])
    bits = [st.dim("mode ") + mode + (st.dim(f" {k['why']}") if k["why"] else "")]
    if k["questions"]:
        bits.append(st.warn(f"{k['questions']} open question{'s' if k['questions'] > 1 else ''}") + st.dim(" (/q)"))
    if k.get("sync_at"):
        ok = k.get("sync_ok")
        bits.append(st.dim("notes synced " + _ago(now - k["sync_at"]) + " ago") if ok else st.bad("notes sync failing"))
    if k.get("backup_at"):
        bits.append(st.dim("backup " + _ago(now - k["backup_at"]) + " ago"))
    elif k.get("backup_error"):
        bits.append(st.bad("backup failing"))
    lines.append(st.dim(f" {st.sep} ").join(bits))
    link = b.get("link")
    if link:
        dia = "◆" if st.unicode else "*"
        if link.get("connected"):
            beat = f" {st.sep} heartbeat {_ago(link['beat'])} ago" if link.get("beat") is not None else ""
            lines.append(st.p("lav", dia) + " " + st.v("call line ") + st.ok("linked") + st.dim(beat))
        else:
            lines.append(
                st.bad(dia)
                + " "
                + st.v("call line ")
                + st.bad("offline")
                + st.dim(": calls still ring, without this computer")
            )
    if b.get("core"):
        lines.append(_service_line(st, mark, "kurooto", b["core"]))
    for f in b.get("features") or []:
        if f.get("down"):
            lines.append(
                st.bad("✗" if st.unicode else "x") + " " + st.v(f"{f['title'][:13]:<14}") + st.bad("not running")
            )
        elif f.get("proc"):
            lines.append(_service_line(st, mark, f["title"], f["proc"]))
    on = k["on"]
    wrapped = textwrap.wrap(", ".join(on), max(10, w - 21)) or ["none yet (open the dashboard: kurooto open)"]
    lines.append(st.dim(f"FEATURES ON ({len(on)}) ".ljust(17)) + st.v(wrapped[0]))
    lines += [
        " " * 17 + st.v(x + (f" {st.ell}" if i == 1 and len(wrapped) > 3 else "")) for i, x in enumerate(wrapped[1:3])
    ]
    out += box(st, "kurooto", lines, w, meta=f"{len(on)} on")
    # TODAY and DUE (from the running Kurooto), side by side when there's room
    if b:
        today = b.get("today") or {}
        tl = []
        for x in [x for x in today.get("items") or [] if x.get("state") not in ("done", "skipped")][:6]:
            when = x["at"] + (("–" if st.unicode else "-") + x["end"] if x.get("end") else "")
            now_ = x.get("state") == "now"
            tl.append(
                (st.p("accent-text", when) if now_ else st.v(when))
                + " "
                + st.v(x["what"])
                + (st.p("accent-text", "  now") if now_ else "")
            )
        if today.get("focus"):
            tl.append(st.warn(f"focus until {today['focus']}"))
        if today.get("quiet"):
            tl.append(st.warn(f"no calls until {today['quiet']}"))
        for c in b.get("calls") or []:
            if time.strftime("%Y-%m-%d", time.localtime(c["when"])) != time.strftime("%Y-%m-%d", time.localtime(now)):
                tl.append(
                    st.p("pink", "call ") + st.v(time.strftime("%a %H:%M", time.localtime(c["when"])) + " " + c["what"])
                )
        dl = []
        for d in (b.get("deadlines") or [])[:6]:
            h = d["hours"]
            when = (
                st.bad(f"overdue {_ago(-h * 3600)}") if h < 0 else (st.warn if h < 24 else st.v)(f"in {_ago(h * 3600)}")
            )
            dl.append(fit(when, 12) + " " + st.v(d["title"]))
        tbox, dbox = tl or [st.dim("nothing more today")], dl or [st.dim("nothing due")]
        due_meta = f"{b.get('deadlines_open', len(dl))} open"
        if w >= 90:
            hh = max(len(tbox), len(dbox)) + 2
            out += beside(
                box(st, "today", tbox, w // 2, hh),
                box(st, "due", dbox, w - w // 2, hh, meta=due_meta),
                w // 2,
                w - w // 2,
            )
        else:
            out += box(st, "today", tbox, w) + box(st, "due", dbox, w, meta=due_meta)
    # AI REQUESTS, with the local models; NEXT
    al = []
    status = {"ok": st.ok("ok  "), "failed": st.bad("fail"), "running": st.warn("run "), "queued": st.dim("wait")}
    for j in k["jobs"][:4]:
        secs = f"{j['seconds']:.0f}s" if j.get("seconds") else ""
        al.append(
            f"{status.get(j['status'], j['status'])} {st.dim(_ago(now - (j['created'] or now)).rjust(5))} "
            f"{st.v(j['title'][: max(10, w - 24)])} {st.dim(secs)}"
        )
    if not k["jobs"]:
        al.append(st.dim("none yet"))
    models = (b.get("agent") or {}).get("models")
    if models is not None:
        al.append(
            st.dim("local models ")
            + st.v(", ".join(f"{x['name']} {_bytes(x['vram'])}" for x in models) or "nothing loaded")
        )
    out += box(st, "ai requests", al, w, meta=f"{k['active']} running, {k['queued']} waiting")
    nl = [
        f"{st.dim(_until(s['when'], now).rjust(8))}  {st.v((s['what'] or s['key'])[: max(10, w - 14)])}"
        for s in k["schedule"][:4]
    ]
    out += box(st, "next", nl or [st.dim("nothing scheduled")], w)
    # STUDY TODAY and PROJECTS
    study = b.get("study")
    if study:
        top = max(r["seconds"] for r in study) or 1
        sl = [
            st.v(f"{r['name'][:12]:<13}")
            + st.bar(r["seconds"] / top, max(4, w - 26))
            + " "
            + st.v(f"{r['seconds'] / 3600:4.1f}h")
            for r in study[:4]
        ]
        out += box(st, "study today", sl, w, meta=f"{sum(r['seconds'] for r in study) / 3600:.1f}h")
    pl = []
    for r in (b.get("projects") or [])[:4]:
        bits = [st.dim("commit ") + st.v(_ago(now - r["last"])) if r.get("last") else st.dim("no commits")]
        if r.get("ahead"):
            bits.append(st.warn(f"{'↑' if st.unicode else ''}{r['ahead']} to push"))
        elif r.get("ahead") == 0:
            bits.append(st.dim("pushed"))
        if r.get("week"):
            bits.append(st.p("lav", f"+{r['week']} this week"))
        if r.get("dirty"):
            bits.append(st.dim(f"{r['dirty']} changed"))
        pl.append(
            st.p("pink", "⌥ " if st.unicode else "- ")
            + st.v(f"{r['name'][:20]:<21}")
            + st.dim(f" {st.sep} ").join(bits)
        )
    if pl:
        out += box(st, "projects", pl, w)
    # EVENTS: whatever room is left
    room = (avail - len(out)) if avail is not None else 10
    if room >= 3:
        el = []
        for e in reversed(k["events"]):
            hhmm = e["ts"][11:16] if len(e["ts"]) >= 16 else e["ts"]
            el.append(f"{st.dim(hhmm)} {st.v(e['kind'].replace('_', ' '))} {st.dim(e['extra'])}")
        out += box(
            st, "events", el or [st.dim("nothing yet")], w, room if avail is not None else min(room, len(el) + 2)
        )
    return out


def header(data: dict, w: int, st: Style) -> list[str]:
    """KUROOTO, the version, a light for Kurooto, Telegram and the call line, the date and time; then the uptime,
    today's events and a trace that beats with each of them."""
    k, m, now = data["kurooto"], data["machine"], data["now"]
    b = k.get("board") or {}
    dot = "●" if st.unicode else "*"

    def pill(ok: bool | None, name: str) -> str:
        return (st.dim if ok is None else st.ok if ok else st.bad)(dot) + " " + st.v(name)

    feats = {f["id"]: f for f in b.get("features") or []}
    pills = [pill(k["running"], "kurooto")]
    if "telegram" in feats:
        pills.append(pill(not feats["telegram"].get("down"), "telegram"))
    if b.get("link") is not None:
        pills.append(pill(b["link"].get("connected"), "call line"))
    local = time.localtime(now)
    clock = st.v(time.strftime("%a %d %b", local).upper()) + " " + st.p("sand", time.strftime("%H:%M:%S", local), True)
    left = " " + st.head("KUROOTO") + " " + st.dim(__version__) + "   " + "  ".join(pills)
    one = left + " " * max(1, w - vlen(left) - vlen(clock) - 1) + clock
    stat = (
        " "
        + st.dim("UP ")
        + st.v(_ago(m.get("uptime") or 0))
        + "   "
        + st.dim("EVENTS TODAY ")
        + st.v(str(k.get("events_today", 0)))
    )
    keys = st.dim(f"q quit {st.sep} r refresh {st.sep} c/m sort ")
    two = stat + "  " + trace(st, k.get("beats") or [], max(0, min(40, w - vlen(stat) - vlen(keys) - 4)), now)
    two = two + " " * max(1, w - vlen(two) - vlen(keys)) + keys
    return [fit(one, w), fit(two, w)]


def render(
    data: dict,
    width: int,
    height: int,
    colour: bool = True,
    unicode: bool = True,
    sort: str = "cpu",
    depth: int | None = None,
) -> list[str]:
    """The board as lines of exactly `width` visible characters (at most `height` lines)."""
    st = Style(colour, unicode, data["kurooto"].get("palette"), depth)
    width, height = max(30, width), max(10, height)
    lines = header(data, width, st)
    natural = height >= 1000  # --once without a size: everything at its natural height
    avail = None if natural else height - len(lines)
    if width >= 120:
        lw = max(60, width * 52 // 100)
        rw = width - lw - 1
        left = machine_column(data["machine"], lw, avail, st, sort)
        right = kurooto_column(data["kurooto"], data["now"], rw, avail, st)
        for i in range(max(len(left), len(right))):
            lines.append(fit(left[i] if i < len(left) else "", lw) + " " + fit(right[i] if i < len(right) else "", rw))
    else:  # one column: the machine first (fewer processes on a short terminal), then Kurooto
        mach = machine_column(data["machine"], width, None if natural else max(0, avail - 22), st, sort)
        rest = None if natural else max(0, avail - len(mach))
        lines += mach + kurooto_column(data["kurooto"], data["now"], width, rest, st)
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
        "█▁·■⣿┤".encode(stream.encoding or "ascii")
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
        w, h = shutil.get_terminal_size((100, 50))[0], 10_000
        m = re.fullmatch(r"(\d+)x(\d+)", size or "")
        if m:
            w, h = int(m[1]), int(m[2])
        board.collect(force=True)
        time.sleep(0.3)  # a real processor reading needs a moment between samples
        for ln in render(board.collect(force=True), w, h, colour, uni):
            out.write(ln.rstrip() + "\n")
        return 0
    out.write("\x1b[?1049h\x1b[?25l")
    sort = "cpu"
    try:
        with Keys() as keys:
            force = True
            while True:
                w, h = shutil.get_terminal_size((100, 40))
                frame = render(board.collect(force=force), w, h, colour, uni, sort)
                force = False
                out.write("\x1b[H" + "\n".join(ln + "\x1b[K" for ln in frame) + "\x1b[J")
                out.flush()
                key = keys.get(1.0)
                if key in ("q", "Q", "\x1b", "\x03"):
                    break
                if key in ("r", "R"):
                    force = True
                if key in ("c", "C", "m", "M"):
                    sort = "mem" if key in ("m", "M") else "cpu"
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        out.flush()
    return 0
