"""Time zone names: an old name and today's name for the same place are one zone (Europe/Kiev and Europe/Kyiv,
Asia/Saigon and Asia/Ho_Chi_Minh, US/Eastern and America/New_York).

Some browsers (Chrome, Edge) still report several old names, and a computer may use either, so zones are compared by
what they mean (the same UTC offsets, hour by hour, over the next year), never by name. A zone is saved under today's
name: the one tzdata's zone.tab lists for that place, found through tzdata's links. When an old name could be one of
several places (it links to a zone that several places share now), it's kept as it is; it still works.
"""

from __future__ import annotations

import datetime as dt
import functools
import os
import zoneinfo
from importlib import resources
from pathlib import Path

UTC_NAMES = ("Etc/UTC", "Etc/GMT")  # what "UTC", "GMT", "Etc/Universal", "Zulu"... lead to: saved as "UTC"


def _read(name: str) -> str:
    """A tzdata file (tzdata.zi, zone.tab): from the system's zone files first, as zoneinfo itself looks, then from
    the tzdata package (Windows, and systems without the files). "" if neither has it."""
    for folder in zoneinfo.TZPATH:
        try:
            return (Path(folder) / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    try:
        return resources.files("tzdata").joinpath("zoneinfo", name).read_text(encoding="utf-8")
    except (ModuleNotFoundError, OSError, UnicodeDecodeError):
        return ""


@functools.cache
def _tables() -> tuple[dict[str, str], frozenset[str]]:
    """(old name -> what it links to, today's names)."""
    links: dict[str, str] = {}
    for line in _read("tzdata.zi").splitlines():
        if line.startswith("L "):
            parts = line.split()
            if len(parts) >= 3:
                links[parts[2]] = parts[1]
    current = set()
    for line in _read("zone.tab").splitlines():
        cols = line.split("\t")
        if not line.startswith("#") and len(cols) >= 3:
            current.add(cols[2].strip())
    return links, frozenset(current | {"UTC"} if current else ())


@functools.cache
def _known() -> dict[str, str]:
    """Every zone name zoneinfo knows, by its lower-case spelling."""
    try:
        return {z.lower(): z for z in zoneinfo.available_timezones()}
    except Exception:
        return {}


def _final(name: str, links: dict[str, str]) -> str:
    for _ in range(10):
        if name not in links:
            break
        name = links[name]
    return name


def valid(name: str) -> bool:
    """A zone name this computer's time zone data knows."""
    if not name or not isinstance(name, str):
        return False
    try:
        zoneinfo.ZoneInfo(name)
        return True
    except (zoneinfo.ZoneInfoNotFoundError, ValueError, OSError, TypeError):
        return False


def canonical(name: str | None) -> str:
    """Today's name for a zone: "Europe/Kiev" -> "Europe/Kyiv", "Etc/UTC" -> "UTC", "europe/kyiv" ->
    "Europe/Kyiv". A name it can't place with certainty, or doesn't know, comes back as it was given (trimmed)."""
    n = (name or "").strip()
    if not n:
        return ""
    links, current = _tables()
    if n in current:
        return n
    if n not in links and not valid(n):
        n = _known().get(n.lower(), n)  # a slip in the capitals
        if n in current:
            return n
    target = _final(n, links)
    if target in UTC_NAMES:
        return "UTC"
    same = [z for z in current if _final(z, links) == target]
    if len(same) == 1:
        return same[0]
    tail = n.rsplit("/", 1)[-1].lower()
    named = [z for z in same if z.rsplit("/", 1)[-1].lower() == tail]
    return named[0] if len(named) == 1 else n


def names() -> list[str]:
    """Today's zone names, for a picker: one per place, plus UTC."""
    current = _tables()[1]
    return sorted(current) if current else sorted(_known().values())


def _hours(days: int, start: dt.datetime | None = None):
    t = (start or dt.datetime.now(dt.UTC)).replace(minute=0, second=0, microsecond=0)
    for h in range(days * 24 + 1):
        yield t + dt.timedelta(hours=h)


def same_zone(a: str | None, b: str | None, days: int = 366) -> bool:
    """Do two zone names mean the same clock, now and for the next year? Unknown names only match themselves."""
    if canonical(a) == canonical(b):
        return True
    if not (valid(a or "") and valid(b or "")):
        return False
    za, zb = zoneinfo.ZoneInfo(a or ""), zoneinfo.ZoneInfo(b or "")
    return all(t.astimezone(za).utcoffset() == t.astimezone(zb).utcoffset() for t in _hours(days))


def matches_computer(name: str | None, days: int = 366) -> bool:
    """Does this zone keep the same clock as this computer, now and for the next year?"""
    if not valid(name or ""):
        return False
    z = zoneinfo.ZoneInfo(name or "")
    return all(t.astimezone(z).utcoffset() == t.astimezone().utcoffset() for t in _hours(days))


def computer_zone() -> str:
    """This computer's zone by today's name, when it says: TZ, or where /etc/localtime points (Linux, macOS). ""
    when it doesn't say (Windows names its zones its own way)."""
    tz = os.environ.get("TZ", "").strip().lstrip(":")
    if tz and not tz.startswith("/") and valid(tz):
        return canonical(tz)
    try:
        real = os.path.realpath("/etc/localtime")
    except OSError:
        real = ""
    if "zoneinfo/" in real:
        n = real.split("zoneinfo/", 1)[1]
        for prefix in ("posix/", "right/"):
            n = n.removeprefix(prefix)
        if valid(n):
            return canonical(n)
    try:
        n = Path("/etc/timezone").read_text(encoding="utf-8").strip()  # older Debian and Ubuntu
    except (OSError, UnicodeDecodeError):
        n = ""
    return canonical(n) if valid(n) else ""


def settle(app) -> str:
    """At start: a saved zone under an old name is saved under today's name (Settings → You). Returns the new name,
    or "" when nothing changed."""
    old = str(app.settings.get("you.timezone") or "").strip()
    new = canonical(old)
    if not old or new == old or not valid(new):
        return ""
    app.settings.set("you.timezone", new)
    try:
        app.scheduler.tz = zoneinfo.ZoneInfo(new)
    except Exception:
        pass
    return new
