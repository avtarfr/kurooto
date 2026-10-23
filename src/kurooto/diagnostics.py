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
    "ledger.key",
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
    "calls.ntfy_token",
    "notes_sync.token",
    "google.client",
    "google.tokens",
    "calendar.ics",
    "profile.token",
    "profile.key",
]
SENSITIVE_KEYS = re.compile(
    r"name|chat|user|url|repo|topic|link|email|workspace|folder|keywords|list|timetable|persona|"
    r"questions|reason|holidays|remote",
    re.I,
)


class Redactor:
    def __init__(self, app):
        self.values = []
        accounts = [f"google.tokens.{a}" for a in app.settings.get("google.accounts") or [] if isinstance(a, str)]
        for n in sorted(set(app.secrets.names()) | set(KNOWN_SECRETS) | set(accounts)):  # (ws2) other Google accounts
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


def checks(app, health: bool = True, net: bool = True) -> list[tuple[str, bool, str]]:
    """Doctor's rows. health: with the health checks' rows (/fixme reads those itself); net: Telegram is asked."""
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
    tz = timezone_check(app)
    if tz:
        out.append(tz)
    main = app.settings.get("brain.main")
    if main:
        b = providers.build(app, main)
        ok, why = b.available() if b else (False, "unknown brain")
        out.append((f"AI: {providers.CHOICES.get(main, main)}", ok, why or "ready"))
    else:
        out.append(("AI", None, "none picked yet (open the setup page)"))
    for m in app.enabled():
        try:
            ok, why = (
                call_line(app, m, running) if m.id == "calls" and getattr(app, "_loop", None) is None else m.health()
            )
        except Exception as e:
            ok, why = False, f"{type(e).__name__}: {e}"
        out.append((m.title, ok, why or "ok"))
    out += more_checks(app, net)
    out += health_rows(app) if health else []
    out += layout_checks(app)
    if "backups" in app.modules and not app.is_on("backups"):  # say when nothing is backed up (a note)
        from kurooto.modules.backups import age_line

        out.append(("Backups", *age_line(p)))
    pre = Prereqs(p.app, p.cache)
    for st in pre.status().values():
        if st["installed"]:
            out.append((f"installed: {st['title']}", True, "yes"))
    return out


# ----------------------------------------------------------------------- (ws5) live checks, and add-ons' own lines
def call_line(app, calls, running: bool) -> tuple[bool | None, str]:
    """`kurooto doctor` runs beside Kurooto, not inside it, so the link to your call line is judged from what the
    running Kurooto recorded, after asking the call line itself whether it's up."""
    from kurooto.core.state import jload
    from kurooto.modules.calls import deploy

    ok, why = calls.ready()
    if not ok:
        return ok, why
    h = deploy.health(calls.worker_url(), timeout=8)
    if not h or not h.get("ok"):
        return False, "your call line doesn't answer (no internet? Settings → Phone calls → Set up redeploys it)"
    if not running:
        return None, "your call line answers; Kurooto isn't running, so this computer isn't linked to it"
    link = jload(app.paths.state / "calls" / "link.json", {}) or {}
    if link.get("connected"):
        return True, "your call line answers, and this computer is linked to it"
    return False, "your call line answers, but this computer isn't linked to it" + (
        f" ({link['error']})" if link.get("error") else " (kurooto logs shows why)"
    )


def more_checks(app, net: bool = True) -> list[tuple[str, bool | None, str]]:
    """Telegram answers (not only set up), your skills in agent programs, and what add-ons check themselves."""
    out: list[tuple[str, bool | None, str]] = []
    tg = app.modules.get("telegram")
    if net and tg is not None and app.is_on("telegram") and tg.ready()[0]:
        try:
            me = tg.api().call("getMe", None, None, 8)
            out.append(("Telegram bot", True, f"@{me.get('username') or '?'} answers"))
        except Exception as e:
            out.append(("Telegram bot", False, f"Telegram didn't answer: {getattr(e, 'description', e)}"[:200]))
    try:
        from kurooto.core import agent_export

        line = agent_export.doctor_check(app)
        if line:
            out.append(line)
    except Exception as e:
        out.append(("skills in agents", False, f"{type(e).__name__}: {e}"[:200]))
    for m in app.enabled():  # an add-on's own checks (core/overlay.py: doctor_checks)
        fn = getattr(m, "doctor_checks", None)
        if not callable(fn):
            continue
        try:
            rows = fn() or []
        except Exception as e:
            rows = [(m.title, False, f"its checks failed: {type(e).__name__}: {e}")]
        for r in list(rows)[:20]:
            if isinstance(r, (list, tuple)) and len(r) == 3:
                ok = r[1] if r[1] in (True, False, None) else bool(r[1])
                out.append((f"{m.title}: {r[0]}"[:60], ok, str(r[2])[:300]))
    return out


def health_rows(app) -> list[tuple[str, bool | None, str]]:
    """Kurooto keeps itself working (core/health.py): each feature's check, read-only, asking the internet too."""
    try:
        results = app.health.evaluate(net=True, save=False)
    except Exception as e:
        return [("working", False, f"the checks failed: {type(e).__name__}: {e}"[:200])]
    out = []
    for r in results:
        detail = r.detail or ("ok" if r.ok else "")
        if r.ok is False:
            detail += f"; fix: kurooto doctor --fix {r.id}" if r.fix_label else (f". {r.help}" if r.help else "")
        out.append((f"working: {r.title}"[:60], r.ok, detail[:400]))
    return out


def layout_checks(app) -> list[tuple[str, bool | None, str]]:
    """Your notes layout's settings (notes.layout, notes.paths, files.folder): one line per problem, or the layout in
    use when there's none."""
    from kurooto.core import layout

    try:
        lay = layout.of(app)
        problems = lay.check()
    except Exception as e:
        return [("notes layout", False, f"{type(e).__name__}: {e}"[:200])]
    if problems:
        return [("notes layout", False, why) for why in problems]
    files = lay.files_root()
    return [("notes layout", True, lay.preset + (f"; files in {files}" if files else ""))]


def timezone_check(app) -> tuple[str, bool, str] | None:
    """Your time zone (Settings → You) and this computer's should be the same: until 0.2.1, some times (repeating
    ones: check-in planning, the look back, digests) follow the setting and others (reminders, check-ins) the
    computer's clock. Compared by what they mean (the same clock over the next year), so an old name and today's
    (Europe/Kiev, Europe/Kyiv) are the same zone (core/zones.py)."""
    import datetime as dt

    from kurooto.core import zones

    name = str(app.settings.get("you.timezone") or "").strip()
    if not name:
        return None
    if not zones.valid(name):
        return ("time zone", False, f"{name!r} isn't a time zone name Kurooto knows (Settings → You → timezone)")
    if not zones.matches_computer(name):
        here = zones.computer_zone() or dt.datetime.now().astimezone().tzname()
        return (
            "time zone",
            False,
            f"{name} (Settings → You) isn't this computer's time zone ({here}): some times follow one and some "
            "the other. Set them the same.",
        )
    return ("time zone", True, f"{name}, the same as this computer")


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
