"""Egress: every request Kurooto makes on the internet goes through here, which counts it and checks where it goes.

    urlopen(req, feature)   in place of urllib.request.urlopen: the host is checked against the list, the request
                            and its bytes (out and in) are counted per day, host and feature
    allow(url, feature)     the same check and count for a connection made another way (the call line's websocket)
    handed(program, feature)  a program that goes online by itself (git, npm, wrangler, agy, Claude Code, Ollama):
                            Kurooto can't see what it sends, so it's counted as "handed to <program>"

It also notes, in memory only, whether requests get answers (net_down, failed_since): requests to two or more hosts
failing for want of a connection, with no answer from any since, is how the offline helper (core/helper.py) knows
the internet is down without pinging anything of its own.

The list is HOSTS (docs/PRIVACY.md's "Where requests go" table says the same, and a test keeps them equal), plus
what you set up yourself: a call site passes own=True for an address you gave (your calendar's link, your feeds,
your own AI service, your call line, your ntfy server, a page your AI reads for you), and privacy.allow_hosts adds
more. This computer (127.0.0.1, localhost) is always allowed and never counted: nothing leaves.

    privacy.egress   "record" (the default): everything is counted; a request to a host that isn't on the list is
                     counted as "not on the list" and still made
                     "enforce": such a request is refused with an error that names the host and how to allow it
                     "off": nothing is checked or counted

Record is the default because add-ons and endpoints changed in settings can reach hosts this list can't know of;
/egress shows any of them, so you can allow them and then turn enforce on. The ledger (state/egress.json) keeps
counts for DAYS days and no more; it never holds what was sent, only where, how often and how much.

Add-ons added by link (core/addons.py) are fenced apart (core/fence.py): their code reaches only the hosts on the card
you agreed to, in every mode (a refusal is Fenced, a kind of Blocked), and is counted as "add-on <name>".
"""

from __future__ import annotations

import datetime as dt
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock, Timeout
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.config import Settings

register_defaults(
    "privacy",
    {
        "egress": "record",  # record (count every request), enforce (also refuse hosts not on the list), off
        "allow_hosts": [],  # more hosts Kurooto may reach, e.g. ["feeds.example.org"]; ".example.org" for all of it
    },
)

MODES = ("record", "enforce", "off")
DAYS = 30  # the ledger keeps this many days
SHOWN = 7  # /egress shows the last week
MAX_ROWS = 300  # rows per day at most; past that, a day's new hosts are counted under "other"
LOOPBACK = ("127.0.0.1", "localhost", "::1")
GIT_ONLINE = ("fetch", "push", "pull", "clone", "ls-remote")  # git steps that talk to your repository
HOSTS = {  # host (".domain": any host under it) -> what reaches it; docs/PRIVACY.md lists the same
    "api.telegram.org": "Telegram",
    "generativelanguage.googleapis.com": "Gemini, with your key",
    "oauth2.googleapis.com": "Google sign-in",
    "classroom.googleapis.com": "Google Classroom",
    "gmail.googleapis.com": "Gmail",
    "www.googleapis.com": "Google Drive and Calendar",
    "api.github.com": "Notes sync and Profile sync",
    "github.com": "Notes sync; downloading Git, Tectonic, kitty and fish",
    "api.cloudflare.com": "Phone calls: setting up your call line",
    ".workers.dev": "Phone calls: your call line",
    "ntfy.sh": "Phone calls: ringing your phone",
    "nodejs.org": "Phone calls: downloading Node.js",
    "ollama.com": "Local AI models: downloading Ollama",
    "registry.ollama.ai": "Local AI models: model sizes",
    "export.arxiv.org": "Research",
    "api.biorxiv.org": "Research",
    "eutils.ncbi.nlm.nih.gov": "Research",
    "api.zotero.org": "Research: Zotero, with your key",
    "avtarfr.github.io": "Updates",
}

_on: dict = {}  # the running assistant's state folder and settings (attach)
_mem = threading.Lock()
_net: dict = {"ok": 0.0, "fails": []}  # the network as requests found it: the last answer, failures since (at, host)
NET_FRESH_S = 600  # failures older than this (and nothing tried since) no longer say the internet is down
NET_HOSTS = 2  # failures to this many hosts, with no answer from any, mean the internet is down


class Blocked(urllib.error.URLError):
    """A request refused because its host isn't on the list (privacy.egress is enforce). An URLError, so code that
    already copes with a network failure copes with this too."""

    def __init__(self, host: str, feature: str):
        super().__init__(
            f"Kurooto didn't connect to {host} ({feature}): it isn't on the list of places Kurooto sends to, and "
            f'privacy.egress is enforce. To allow it, add "{host}" to privacy.allow_hosts in Settings.'
        )
        self.host, self.feature = host, feature

    def __str__(self) -> str:
        return str(self.reason)


class Fenced(Blocked):
    """A request refused because an add-on added by link asked for a host its card doesn't declare (core/fence.py).
    Whatever privacy.egress says: the card is what you agreed to."""

    def __init__(self, host: str, addon: str, hosts):
        urllib.error.URLError.__init__(
            self,
            f"The add-on {addon} may only reach the hosts on its card ({', '.join(hosts) or 'none'}); {host} isn't "
            f"one, so Kurooto didn't connect to it. `kurooto addons show {addon}` shows its card.",
        )
        self.host, self.feature = host, f"add-on {addon}"


def attach(app: App) -> None:
    """The running assistant's settings and ledger; before this (a bare `kurooto` command) nothing is counted."""
    _on.update(state=Path(app.paths.state), settings=app.settings)
    with _mem:
        _net.update(ok=0.0, fails=[])


def _unreachable(err: BaseException) -> bool:
    """A request that never got an answer (no network, DNS, a timeout), not a "no" from the other side."""
    if isinstance(err, (urllib.error.HTTPError, Blocked)):
        return False
    return isinstance(err, (urllib.error.URLError, OSError))  # TimeoutError and socket errors are OSErrors


def seen(host: str, err: BaseException | None = None) -> None:
    """One request's outcome, for net_down: an answer (err None, or an HTTP error: the other side answered) or a
    failure to reach the host. This computer doesn't count."""
    if not host or host in LOOPBACK:
        return
    answered = err is None or isinstance(err, urllib.error.HTTPError)
    if not answered and not _unreachable(err):
        return
    with _mem:
        if answered:
            _net.update(ok=time.time(), fails=[])
        else:
            _net["fails"] = [*_net["fails"][-19:], (time.time(), host)]


def net_down(now: float | None = None) -> bool:
    """Is the internet down, as Kurooto's own requests found it? Failures to NET_HOSTS hosts or more, the last one
    recent, and no answer from anywhere since."""
    t = time.time() if now is None else now
    with _mem:
        fails = list(_net["fails"])
    if not fails or t - fails[-1][0] > NET_FRESH_S:
        return False
    return len({h for _at, h in fails}) >= NET_HOSTS


def answered_since(t: float) -> bool:
    """Did any host answer a request after t?"""
    with _mem:
        return float(_net["ok"]) >= t


def failed_since(t: float) -> bool:
    """Did a request fail to reach its host after t, with no answer from anywhere after it?"""
    with _mem:
        return any(at >= t for at, _h in _net["fails"])


def host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower().rstrip(".")


def mode(settings: Settings | None = None) -> str:
    s = settings or _on.get("settings")
    m = str((s.get("privacy.egress") if s is not None else None) or "record").strip().lower()
    return m if m in MODES else "record"


def _match(host: str, entries) -> bool:
    for e in entries:
        e = str(e or "").strip().lower()
        if e and (host == e.lstrip(".") or (e.startswith(".") and host.endswith(e))):
            return True
    return False


def listed(host: str, settings: Settings | None = None) -> bool:
    """On the list: Kurooto's own hosts, or one you added to privacy.allow_hosts."""
    s = settings or _on.get("settings")
    extra = (s.get("privacy.allow_hosts") if s is not None else None) or []
    return _match(host, HOSTS) or _match(host, extra if isinstance(extra, list) else [extra])


def _check(host: str, feature: str, own: bool) -> bool | None:
    """None: not counted (this computer, or privacy.egress off); else whether the host is on the list. Raises
    Blocked (and counts it) in enforce mode for a host that isn't on the list and isn't yours."""
    m = mode()
    if not host or host in LOOPBACK:
        return None
    from kurooto.core import fence  # an add-on by link asking: only the hosts on its card, whatever the mode

    fe = fence.owner()
    if fe is not None:
        if not fence.allowed(host, fe["hosts"]):
            if m != "off":
                record(host, feature, blocked=True)
            raise Fenced(host, fe["name"], fe["hosts"])
        return None if m == "off" else True
    if m == "off":
        return None
    ok = own or listed(host)
    if not ok and m == "enforce":
        record(host, feature, blocked=True)
        raise Blocked(host, feature)
    return ok


def allow(url: str, feature: str, own: bool = False) -> str:
    """Check one connection made another way (a websocket) and count it. Returns its host; raises Blocked like
    urlopen. own=True: an address you gave."""
    host = host_of(url)
    ok = _check(host, feature, own)
    if ok is not None:
        record(host, feature, unlisted=not ok)
    return host


def urlopen(req, feature: str, timeout: float = 30, own: bool = False, opener=None):
    """urllib.request.urlopen (or opener.open) through the ledger: checked, then counted with its bytes when the
    answer is closed. Use it as a context manager, as urlopen itself. own=True: an address you gave."""
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    data = getattr(req, "data", None)
    out = len(data) if isinstance(data, (bytes, bytearray)) else 0
    host = host_of(url)
    ok = _check(host, feature, own)
    go = opener.open if opener else urllib.request.urlopen  # looked up now: tests put a fake in its place
    try:
        r = go(req, timeout=timeout)
    except BaseException as e:
        seen(host, e)
        if ok is not None:
            record(host, feature, out=out, unlisted=not ok)  # it went out, whatever came back
        raise
    seen(host)
    if ok is None:
        return r
    return _Counted(r, lambda got: record(host, feature, out=out, got=got, unlisted=not ok))


class _Counted:
    """An answer whose bytes are counted as they're read; counted in the ledger once, when it's closed."""

    def __init__(self, r, done):
        self._outer, self._r, self._done, self.got = r, r, done, 0

    def __getattr__(self, name):
        return getattr(self._r, name)

    def __enter__(self):
        enter = getattr(self._outer, "__enter__", None)
        self._r = enter() if enter else self._outer
        return self

    def __exit__(self, *exc):
        self._finish()
        leave = getattr(self._outer, "__exit__", None)
        return leave(*exc) if leave else None

    def close(self):
        self._finish()
        shut = getattr(self._r, "close", None)
        if shut:
            shut()

    def _finish(self):
        done, self._done = self._done, None
        if done:
            done(self.got)

    def _count(self, b):
        self.got += len(b or b"")
        return b

    def read(self, *a):
        return self._count(self._r.read(*a))

    def read1(self, *a):
        return self._count(self._r.read1(*a))

    def readline(self, *a):
        return self._count(self._r.readline(*a))

    def readinto(self, b):
        n = self._r.readinto(b)
        self.got += n or 0
        return n

    def __iter__(self):
        for line in self._r:
            yield self._count(line)


def handed(program: str, feature: str) -> None:
    """A program that goes online by itself was started for a feature: counted as "handed to <program>"."""
    if mode() != "off":
        record("", feature, via=program)


# ---------------------------------------------------------------------------------------------------- ledger
def ledger_file(state: Path | None = None) -> Path | None:
    st = state or _on.get("state")
    return Path(st) / "egress.json" if st else None


def record(
    host: str,
    feature: str,
    out: int = 0,
    got: int = 0,
    blocked: bool = False,
    unlisted: bool = False,
    via: str = "",
    state: Path | None = None,
    now: float | None = None,
) -> None:
    """Add one request to today's row for (host or the program it was handed to, feature). Never raises: counting
    must not stop a request."""
    f = ledger_file(state)
    if f is None:
        return
    day = dt.date.fromtimestamp(now or time.time()).isoformat()
    try:
        with _mem, Lock(f.parent, "egress", timeout=2):
            led = jload(f, {}) or {}
            days = led.get("days") if isinstance(led.get("days"), dict) else {}
            rows = days.setdefault(day, {})
            key = f">{via}|{feature}" if via else f"{host}|{feature}"
            if key not in rows and len(rows) >= MAX_ROWS:
                key, host, via = f"other|{feature}", "other", ""
            r = rows.setdefault(key, {"host": host, "via": via, "feature": feature})
            r["n"] = r.get("n", 0) + 1
            for k, v in (("out", out), ("in", got), ("blocked", int(blocked)), ("unlisted", int(unlisted))):
                if v:
                    r[k] = r.get(k, 0) + int(v)
            led["days"] = {d: days[d] for d in sorted(days)[-DAYS:]}
            jsave(f, led)
    except (OSError, ValueError, Timeout):
        pass


def week(state: Path | None = None, days: int = SHOWN, now: float | None = None) -> list[dict]:
    """The last `days` days, one row per (host or program, feature): {host, via, feature, n, out, in, blocked,
    unlisted}, the busiest first."""
    f = ledger_file(state)
    led = (jload(f, {}) or {}) if f else {}
    since = (dt.date.fromtimestamp(now or time.time()) - dt.timedelta(days=days - 1)).isoformat()
    out: dict[str, dict] = {}
    for day, rows in (led.get("days") or {}).items():
        if day < since or not isinstance(rows, dict):
            continue
        for key, r in rows.items():
            t = out.setdefault(key, {"host": r.get("host", ""), "via": r.get("via", ""), "feature": r.get("feature")})
            for k in ("n", "out", "in", "blocked", "unlisted"):
                t[k] = t.get(k, 0) + int(r.get(k) or 0)
    return sorted(out.values(), key=lambda r: (-r["blocked"], -r["n"]))


def size(n: int) -> str:
    for unit, step in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= step:
            return f"{n / step:.1f} {unit}"
    return f"{n} B"


def command(app: App, arg: str = "") -> str:
    """/egress: where Kurooto's requests went in the last 7 days, per host and feature, with any blocked."""
    m = mode(app.settings)
    if m == "off":
        return "Counting requests is off (privacy.egress is off). Set it to record to see where they go."
    rows = week(Path(app.paths.state))
    if not rows:
        return f"Nothing has left this computer in the last {SHOWN} days (privacy.egress: {m})."
    lines = [f"What Kurooto sent out in the last {SHOWN} days (privacy.egress: {m}):"]
    blocked = [r for r in rows if r["blocked"]]
    unlisted = [r for r in rows if r["unlisted"] and not r["blocked"]]
    for r in rows:
        if r["via"]:
            runs = f"{r['n']} run{'s' if r['n'] != 1 else ''}"
            lines.append(f"- handed to {r['via']} ({r['feature']}): {runs}; what it sends, it sends itself")
            continue
        if r["blocked"] and r["n"] == r["blocked"]:
            continue
        n = r["n"] - r["blocked"]
        sent = f"{n} request{'s' if n != 1 else ''}, {size(r['out'])} out, {size(r['in'])} in"
        lines.append(f"- {r['host']} ({r['feature']}): {sent}{' (not on the list)' if r['unlisted'] else ''}")
    if blocked:
        lines += ["", "Blocked (not on the list):"]
        lines += [f"- {r['host']} ({r['feature']}): {r['blocked']} time{'s' * (r['blocked'] != 1)}" for r in blocked]
    if blocked or unlisted:
        lines += ["", 'To allow a host, add it to privacy.allow_hosts in Settings (e.g. ["feeds.example.org"]).']
    elif m == "record":
        lines += ["", "Everything went to hosts on the list; privacy.egress enforce would refuse any other."]
    return "\n".join(lines)


__all__ = [
    "HOSTS",
    "Blocked",
    "Fenced",
    "attach",
    "allow",
    "urlopen",
    "handed",
    "record",
    "week",
    "command",
    "listed",
    "mode",
]
