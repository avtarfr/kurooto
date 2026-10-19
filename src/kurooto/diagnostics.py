"""`kurooto doctor` (what's working and what isn't) and `kurooto doctor --bundle` (a zip to send someone helping you).

The bundle never contains your messages, notes, journal, transcripts, AI requests or answers. Secrets (tokens, keys,
links) are replaced with [secret]; names, email addresses, web addresses and your folders are replaced too. Nothing
is sent anywhere: the zip is saved on this computer, and you decide whether to send it. Look inside first.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

from kurooto import __version__

PATTERNS = [
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"), "[secret]"),  # Telegram bot token
    (re.compile(r"AIza[0-9A-Za-z_-]{30,}"), "[secret]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "[secret]"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"), "[secret]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[secret]"),
    (re.compile(r"\b(?:d1\.[0-9a-f]{8}\.[0-9a-f]{64}|t1\.\d{13}\.[0-9a-f]{64}|k1\.[A-Za-z0-9_-]{20,})"), "[secret]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), "[email]"),
    (re.compile(r"https?://[^\s\"'<>]+"), "[web address]"),
]
# the keychain can't be listed, so the names Kurooto uses are listed here
KNOWN_SECRETS = [
    "web.token",
    "telegram.token",
    "gemini.api_key",
    "freellmapi.api_key",
    "custom.api_key",
    "ollama.api_key",
    "calls.call_secret",
    "calls.connector_secret",
    "calls.ntfy_topic",
    "calls.ntfy_key",
    "calls.vapid_jwk",
    "calls.vapid_public",
    "calls.github_token",
    "notes_sync.token",
    "google.client",
    "google.tokens",
    "calendar.ics",
]
SENSITIVE_KEYS = re.compile(
    r"name|chat|user|url|repo|topic|link|email|workspace|folder|keywords|list|timetable|persona|"
    r"questions|reason|holidays|remote",
    re.I,
)


class Redactor:
    def __init__(self, app):
        self.values = []
        for n in sorted(set(app.secrets.names()) | set(KNOWN_SECRETS)):
            v = app.secrets.get(n)
            if v and len(v) >= 6:
                self.values.append(v)
                if v.startswith(("[", "{")):  # JSON-held secrets: their parts too
                    self.values += [x for x in re.findall(r'"([^"]{12,})"', v)]
        self.paths = sorted({str(p) for p in (app.workspace, Path.home())}, key=len, reverse=True)
        self.name = app.settings.get("you.name") or ""

    def text(self, s: str) -> str:
        for v in sorted(self.values, key=len, reverse=True):
            s = s.replace(v, "[secret]")
        for rx, sub in PATTERNS:
            s = rx.sub(sub, s)
        for p in self.paths:
            s = s.replace(p, "~" if p == str(Path.home()) else "[notes folder]")
        if len(self.name) >= 2:
            s = re.sub(rf"\b{re.escape(self.name)}\b", "[you]", s)
        return s

    def obj(self, o, key: str = ""):
        if isinstance(o, dict):
            return {k: self.obj(v, k) for k, v in o.items()}
        if isinstance(o, list):
            return "[set]" if o and SENSITIVE_KEYS.search(key) else [self.obj(x, key) for x in o]
        if isinstance(o, str):
            return ("[set]" if o else "") if SENSITIVE_KEYS.search(key) else self.text(o)
        return o


def checks(app) -> list[tuple[str, bool, str]]:
    from kurooto import providers
    from kurooto.core.prereqs import Prereqs
    from kurooto.core.state import jload

    p = app.paths
    out = [
        ("python", sys.version_info >= (3, 12), platform.python_version()),
        ("os", True, f"{platform.system()} {platform.release()} ({platform.machine()})"),
    ]
    for name in ("config", "data", "state", "logs"):
        folder = getattr(p, name)
        out.append((f"{name} folder", _writable(folder), str(folder)))
    free = shutil.disk_usage(p.data if p.data.exists() else Path.home()).free / 1024**3
    out.append(("free space", free >= 5, f"{free:.1f} GB (Kurooto keeps 5 GB spare)"))
    daemon = jload(p.state / "daemon.json", {}) or {}
    from kurooto.core.proc import pid_alive

    running = bool(daemon.get("pid")) and pid_alive(daemon["pid"])
    out.append(("running", True if running else None, "yes" if running else "no: start it with `kurooto start`"))
    main = app.settings.get("brain.main")
    if main:
        b = providers.build(app, main)
        ok, why = b.available() if b else (False, "unknown brain")
        out.append((f"AI: {providers.CHOICES.get(main, main)}", ok, why or "ready"))
    else:
        out.append(("AI", None, "none picked yet (open the setup page)"))
    for m in app.enabled():
        try:
            ok, why = m.health()
        except Exception as e:
            ok, why = False, f"{type(e).__name__}: {e}"
        out.append((m.title, ok, why or "ok"))
    pre = Prereqs(p.app, p.cache)
    for st in pre.status().values():
        if st["installed"]:
            out.append((f"installed: {st['title']}", True, "yes"))
    return out


def _writable(folder: Path) -> bool:
    import tempfile

    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder):
            pass
        return True
    except OSError:
        return False


def bundle(app, dest: Path | None = None) -> tuple[Path, list[str]]:
    """Write the diagnostics zip. Returns (where, what's in it)."""
    from kurooto.core.state import jload

    r = Redactor(app)
    dest = dest or app.paths.data / f"kurooto-diagnostics-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    files: dict[str, str] = {}
    files["doctor.json"] = json.dumps(
        [{"name": r.text(n), "ok": ok, "detail": r.text(str(d))} for n, ok, d in checks(app)], indent=1
    )
    files["versions.json"] = json.dumps(
        {
            "kurooto": __version__,
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()} {platform.machine()}",
        },
        indent=1,
    )
    files["settings.json"] = json.dumps(r.obj(app.settings.user()), indent=1, default=str)
    files["features.json"] = json.dumps(
        [
            {"id": m.id, "on": app.is_on(m.id), "ready": m.ready()[0], "why": r.text(m.ready()[1])}
            for m in app.modules.values()
        ],
        indent=1,
    )
    hw = jload(app.paths.state / "hardware.json", None)
    if hw:
        files["hardware.json"] = json.dumps(hw, indent=1, default=str)
    files["jobs.json"] = json.dumps(  # how AI requests went, never what they said
        [
            {"status": j.status, "verdict": j.verdict, "brain": j.brain, "effort": j.effort, "seconds": j.seconds}
            for j in app.jobs.recent(30)
        ],
        indent=1,
    )
    events = []
    for e in app.events.tail(400):
        keep = {
            k: v for k, v in e.items() if isinstance(v, (int, float, bool)) or k in ("ts", "kind", "module", "verdict")
        }
        if "error" in e:
            keep["error"] = r.text(str(e["error"]))[:300]
        events.append(keep)
    files["events.json"] = json.dumps(events, indent=1, default=str)
    log = app.paths.logs / "kurooto.log"
    if log.exists():
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()[-1500:]
        files["kurooto.log"] = r.text("\n".join(lines))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr(name, text)
        z.writestr("README.txt", __doc__.strip() + "\n")
    return dest, sorted(files)
