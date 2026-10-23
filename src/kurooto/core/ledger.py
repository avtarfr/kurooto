"""The memory ledger: one store, on this computer, of everything Kurooto remembers, each row with where it came from
and a way to forget it. Always encrypted at rest.

    gist      what a call, an AI request or a chat decided or did, once its words faded (core/gists.py)
    thread    something you're in the middle of: what you said you'd do, in a chat or on a call, or a task you
              started (core/threads.py)
    fact      a dated line Kurooto keeps in your how-to-help-me note (modules/remember.py)
    day       a daily note's headings and lines (your journal and plans)
    meeting   a dated line under a project note's "## Meetings" (core/infer.py writes them; you can too)

Facts, days and meetings are read from your notes when a note changes (at most once a minute, and nightly), so your
notes stay the source of truth: a row forgotten here stays forgotten here (a keyed hash of it is kept, so reading the
note again doesn't bring it back), and the note keeps it until you change it. Gists and threads live only here.

Encryption: each row's words and where it came from are sealed with AES-GCM under a 256-bit key made on first use and
kept in the platform keychain through core/secrets.py ("ledger.key"; the owner-only secrets file where there's no
keychain). On disk (state/ledger.db) stay only each row's kind, its state (a thread's open or done), its times and
keyed hashes. Search decrypts into memory and matches words there, so no index of your words is ever written. The key
never goes into Profile sync; Backups leave the ledger out unless backups.memory is on (a restored ledger opens only
where its key is). If the key can't be read (a keychain still locked), nothing is written or shown until it can, and a
new key is never made over rows an older one sealed.

/memory lists and finds rows (/memory <words>), /memory forget 3 drops one, /memory export writes the gists and
threads to a note in your inbox. "When did I last talk to Prof Ortiz?" and "what was I doing last Thursday?" are
answered from here and from the gists of what's still kept in full, by rules.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from kurooto.core.clock import now
from kurooto.core.lock import Lock
from kurooto.core.state import owner_only

if TYPE_CHECKING:
    from kurooto.app import App

KEY = "ledger.key"  # the secret's name (core/secrets.py); never in the profile (core/profile.py:NEVER)
SCHEMA = """
create table if not exists rows (
    id integer primary key, kind text not null, sub text not null default '', at real not null, upd real not null,
    src text, h text, blob blob not null
);
create index if not exists rows_kind on rows(kind, at);
create table if not exists seen (src text primary key, mtime real);
create table if not exists forgot (h text primary key, at real);
"""
NAMES = {  # kind -> how a row is named to you
    "gist": "gist",
    "thread": "thread",
    "fact": "how-to-help-me line",
    "day": "daily note",
    "meeting": "meeting",
}
NOTES = ("fact", "day", "meeting")  # read from your notes
REFRESH_S = 60  # notes are looked at again at most this often (and nightly)
DAYS_BACK = 730  # daily notes older than this aren't read
DAY_MAX = 1200  # a day row keeps at most this much of its note
LIVE_DAYS = 3  # what the AI is told comes from gists of what's still kept in full, this far back
SHOWN = 10
WHEN = "daily 04:30"
STOP = set(
    "the and for with that this from have has had was were are you your yours i'm i've i'll ill i'd what when where "
    "which who why how did does doing done not but all any can could would should will just about into onto over "
    "then than them they their there here its it's let me my mine our ours out off get got some more most much "
    "very really also too yet still last time thing things stuff today tonight tomorrow yesterday morning evening "
    "please thanks okay was were been being".split()
)
TITLES = {"prof", "professor", "dr", "mr", "mrs", "ms", "sir", "maam", "ma'am", "miss", "madam"}
DAY_LINE = re.compile(r"^(?:[-*+]\s+(?:\[[ xX]\]\s+)?)?(?P<text>\S.*)$")
MEETING = re.compile(r"^[-*]\s+(?P<date>\d{4}-\d{2}-\d{2}):?\s*(?P<text>\S.*)$")
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
LAST_TALK = re.compile(
    r"(?i)^(?:when (?:did|have) i (?:last )?(?:talk(?:ed)?|speak|spoke|chat(?:ted)?|meet|met|see|saw|call(?:ed)?|"
    r"hear from|heard from|email(?:ed)?|write to|wrote to)|when was (?:the )?last time i (?:talked|spoke|chatted|"
    r"met|saw|called|heard from|emailed|wrote to)|when did i last (?:have )?(?:a )?meeting)(?:\s+(?:to|with))?\s+"
    r"(?P<who>[^?.!]+?)[?.!\s]*$"
)
DOING = re.compile(
    r"(?i)^what (?:was i doing|did i do|was i up to|did i get done|happened|did i work on)\s+(?P<when>[^?!]+?)"
    r"[?.!\s]*$"
)
LOCKED = (
    "I can't open what I remember right now: the key to it isn't readable (if your keychain is locked, unlock it). "
    "Nothing was lost."
)


class Locked(Exception):
    """The ledger's key can't be read (yet): nothing is written or shown."""


def words(text: str) -> set[str]:
    """The words that make two lines about the same thing: lower case, three letters or more, no common words."""
    out = set()
    for w in re.findall(r"[a-z0-9][a-z0-9']{2,}", str(text or "").lower()):
        w = w[:-2] if w.endswith("'s") else w.strip("'")
        if len(w) >= 3 and w not in STOP:
            out.add(w)
    return out


class Ledger:
    def __init__(self, app: App):
        self.app = app
        self.file = Path(app.paths.state) / "ledger.db"
        self._db = sqlite3.connect(self.file, check_same_thread=False, isolation_level=None)
        owner_only(self.file)
        self._db.execute("pragma journal_mode=wal")
        self._db.executescript(SCHEMA)
        owner_only(self.file)  # and its -wal and -shm, now that they exist
        self._lock = threading.RLock()
        self._key: bytes | None = None
        self.read_at = 0.0  # when the notes were last looked at

    def close(self) -> None:
        self._db.close()

    # ------------------------------------------------------------------------------------------ the key
    def key(self) -> bytes:
        """The ledger's key: from the keychain (core/secrets.py), made on first use. Locked when it can't be read and
        rows an older key sealed are there: a new key would make them unreadable for good."""
        if self._key:
            return self._key
        with Lock(self.app.paths.state, "ledger-key", timeout=10):
            v = self.app.secrets.get(KEY)
            if not v:
                if self._db.execute("select 1 from rows limit 1").fetchone():
                    self.app.events.emit("ledger_locked")
                    raise Locked("the memory ledger's key can't be read")
                v = base64.b64encode(os.urandom(32)).decode()
                self.app.secrets.set(KEY, v)
                if self.app.secrets.get(KEY) != v:
                    raise Locked("the memory ledger's key couldn't be kept")
                self.app.events.emit("ledger_key_made")
        try:
            k = base64.b64decode(v)
        except ValueError:
            k = b""
        if len(k) != 32:
            raise Locked("the memory ledger's key isn't one")
        self._key = k
        return k

    def mac(self, *parts: str) -> str:
        """A keyed hash: the same words give the same value, which says nothing of them without the key."""
        k = hmac.new(self.key(), b"kurooto-ledger:mac", hashlib.sha256).digest()
        return hmac.new(k, "\x1f".join(parts).encode(), hashlib.sha256).hexdigest()[:32]

    def seal(self, kind: str, payload: dict) -> bytes:
        nonce = os.urandom(12)
        data = json.dumps(payload, ensure_ascii=False).encode()
        return nonce + AESGCM(self.key()).encrypt(nonce, data, f"kurooto-ledger:{kind}".encode())

    def unseal(self, kind: str, blob: bytes) -> dict | None:
        try:
            raw = AESGCM(self.key()).decrypt(blob[:12], blob[12:], f"kurooto-ledger:{kind}".encode())
            out = json.loads(raw)
        except (InvalidTag, ValueError):
            return None
        return out if isinstance(out, dict) else None

    # ------------------------------------------------------------------------------------------- rows
    def add(self, kind: str, text: str, at: float | None = None, sub: str = "", src=None, h=None, **extra) -> int:
        t = time.time()
        blob = self.seal(kind, {"text": str(text), **extra})
        with self._lock:
            cur = self._db.execute(
                "insert into rows(kind, sub, at, upd, src, h, blob) values(?,?,?,?,?,?,?)",
                (kind, sub, float(at or t), t, src, h, blob),
            )
        return int(cur.lastrowid)

    def rows(self, kinds: tuple[str, ...] = (), lo=None, hi=None, sub: str | None = None) -> list[dict]:
        """Rows (oldest first), decrypted: their payload plus id, kind, sub, at, upd, src."""
        sql, args = "select id, kind, sub, at, upd, src, blob from rows where 1=1", []
        if kinds:
            sql += f" and kind in ({','.join('?' * len(kinds))})"  # placeholders only
            args += list(kinds)
        for col, op, v in (("at", ">=", lo), ("at", "<", hi), ("sub", "=", sub)):
            if v is not None:
                sql += f" and {col} {op} ?"
                args.append(v)
        with self._lock:
            got = self._db.execute(sql + " order by at, id", args).fetchall()
        if not got:
            return []
        self.key()
        out, bad = [], 0
        for rid, kind, s, at, upd, src, blob in got:
            p = self.unseal(kind, blob)
            if p is None:
                bad += 1
                continue
            out.append({**p, "id": rid, "kind": kind, "sub": s, "at": at, "upd": upd, "src": src})
        if bad:
            self.app.events.emit("ledger_unreadable", n=bad)
        return out

    def get(self, rid: int) -> dict | None:
        with self._lock:
            r = self._db.execute("select kind from rows where id=?", (rid,)).fetchone()
        if not r:
            return None
        return next((x for x in self.rows((r[0],)) if x["id"] == rid), None)

    def update(self, rid: int, sub: str | None = None, **fields) -> bool:
        with self._lock:
            r = self._db.execute("select kind, blob from rows where id=?", (rid,)).fetchone()
            if not r:
                return False
            p = self.unseal(r[0], r[1])
            if p is None:
                return False
            p.update(fields)
            self._db.execute(
                "update rows set sub=coalesce(?, sub), upd=?, blob=? where id=?",
                (sub, time.time(), self.seal(r[0], p), rid),
            )
        return True

    def delete(self, ids) -> int:
        ids = [int(i) for i in ids]
        if not ids:
            return 0
        with self._lock:
            return self._db.executemany("delete from rows where id=?", [(i,) for i in ids]).rowcount

    def drop(self, kind: str, lo: float = 0, hi: float = 1e18) -> int:
        """Every row of a kind from [lo, hi); no key needed."""
        with self._lock:
            return self._db.execute("delete from rows where kind=? and at>=? and at<?", (kind, lo, hi)).rowcount

    def replace(self, kind: str, items: list[tuple[float, str, dict]]) -> None:
        """All rows of a kind, at once: (at, sub, payload). Sealed first, so a missing key changes nothing."""
        self.key()  # even for none: a missing key must never empty a kind
        t = time.time()
        sealed = [(kind, sub, float(at), t, self.seal(kind, p)) for at, sub, p in items]
        with self._lock:
            self._db.execute("begin")
            try:
                self._db.execute("delete from rows where kind=?", (kind,))
                self._db.executemany("insert into rows(kind, sub, at, upd, blob) values(?,?,?,?,?)", sealed)
                self._db.execute("commit")
            except Exception:
                self._db.execute("rollback")
                raise

    def counts(self) -> dict[str, int]:
        with self._lock:
            return dict(self._db.execute("select kind, count(*) from rows group by kind").fetchall())

    # ---------------------------------------------------------------------------------- from your notes
    def refresh(self, force: bool = False) -> int:
        """Read the notes that changed since last time into rows (facts, days, meetings); a note that's gone takes
        its rows with it. At most once a minute unless forced. How many notes were read."""
        if not force and time.time() - self.read_at < REFRESH_S:
            return 0
        self.read_at = time.time()
        read, have = 0, set()
        with self._lock:
            seen = dict(self._db.execute("select src, mtime from seen").fetchall())
            forgot = {r[0] for r in self._db.execute("select h from forgot")}
        for kind, f in note_sources(self.app):
            rel = _rel(self.app, f)
            src = self.mac("src", kind, rel)
            have.add(src)
            try:
                mtime = f.stat().st_mtime
            except OSError:
                continue
            if seen.get(src) == mtime:
                continue
            try:
                found = READERS[kind](self.app, f)
            except Exception as e:  # one note that can't be read never stops the rest
                self.app.events.emit("ledger_read_failed", what=kind, error=f"{type(e).__name__}"[:60])
                continue
            rows = []
            for at, text, extra in found:
                h = self.mac("row", kind, rel, text)
                if h not in forgot:
                    blob = self.seal(kind, {"text": text, "source": rel, **extra})
                    rows.append((kind, float(at), time.time(), src, h, blob))
            with self._lock:
                self._db.execute("begin")
                try:
                    self._db.execute("delete from rows where src=?", (src,))
                    self._db.executemany("insert into rows(kind, at, upd, src, h, blob) values(?,?,?,?,?,?)", rows)
                    self._db.execute("insert or replace into seen(src, mtime) values(?,?)", (src, mtime))
                    self._db.execute("commit")
                except Exception:
                    self._db.execute("rollback")
                    raise
            read += 1
        gone = [s for s in seen if s not in have]
        if gone:
            with self._lock:
                for s in gone:
                    self._db.execute("delete from rows where src=?", (s,))
                    self._db.execute("delete from seen where src=?", (s,))
        return read

    def forget_row(self, row: dict) -> None:
        """Drop one row; a row read from a note is remembered as forgotten (by a keyed hash) so it doesn't come back."""
        if row["kind"] in NOTES:
            h = self.mac("row", row["kind"], row.get("source") or "", row["text"])
            with self._lock:
                self._db.execute("insert or replace into forgot(h, at) values(?,?)", (h, time.time()))
        self.delete([row["id"]])


def of(app: App) -> Ledger:
    """The app's ledger, opened on first use."""
    led = app.__dict__.get("_ledger")
    if led is None:
        led = app.__dict__["_ledger"] = Ledger(app)
    return led


def close(app: App) -> None:
    led = app.__dict__.pop("_ledger", None)
    if led is not None:
        led.close()


def _rel(app: App, f: Path) -> str:
    from kurooto.core import layout

    return layout.shown(app, f)


# ----------------------------------------------------------------------------------------- reading notes
def note_sources(app: App) -> list[tuple[str, Path]]:
    """Every note the ledger reads: (kind, file)."""
    from kurooto.core import layout
    from kurooto.modules.remember import help_file

    out: list[tuple[str, Path]] = []
    f = help_file(app)
    if f.is_file():
        out.append(("fact", f))
    sample = layout.path(app, "daily", date="2000-01-01")
    if "2000-01-01" in sample.name and sample.parent.is_dir():
        edge = (now().date() - dt.timedelta(days=DAYS_BACK)).isoformat()
        pat = re.compile(re.escape(sample.name).replace("2000\\-01\\-01", r"(\d{4}-\d{2}-\d{2})") + "$")
        for g in sorted(sample.parent.glob(sample.name.replace("2000-01-01", "*"))):
            m = pat.match(g.name)
            if m and m.group(1) >= edge:
                out.append(("day", g))
    proj = layout.path(app, "project", project="x")
    root = proj.parent.parent
    for g in sorted(root.glob("*/" + proj.name)) if root.is_dir() else []:
        out.append(("meeting", g))
    return out


def _noon(day: str) -> float:
    return dt.datetime.combine(dt.date.fromisoformat(day), dt.time(12)).timestamp()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", text)).strip()


def _facts(app: App, f: Path) -> list[tuple[float, str, dict]]:
    from kurooto.modules.remember import kept_lines, sensitive

    return [(_noon(x["date"]), x["fact"], {"line": x["line"]}) for x in kept_lines(app) if not sensitive(x["fact"])]


def _day(app: App, f: Path) -> list[tuple[float, str, dict]]:
    """A daily note: its headings, then its lines (a health, money or password line is left out)."""
    from kurooto.modules.remember import sensitive

    day = re.search(r"\d{4}-\d{2}-\d{2}", f.name).group(0)
    text = re.sub(r"\A---\n.*?\n---\n", "", f.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    heads, lines = [], []
    for ln in text.splitlines():
        if re.match(r"^#\s", ln) or not ln.strip():
            continue
        if ln.startswith("## "):
            heads.append(ln[3:].strip())
            continue
        if ln.startswith("#"):
            continue
        m = DAY_LINE.match(ln.strip())
        if m and not sensitive(m["text"]):
            lines.append(_clean(m["text"]))
    if not heads and not lines:
        return []
    body = "; ".join(heads) + (": " if heads and lines else "") + " · ".join(lines)
    return [(_noon(day), body[:DAY_MAX], {})]


def _meetings(app: App, f: Path) -> list[tuple[float, str, dict]]:
    """A project note's "## Meetings" lines ("- 2026-10-20: met Ortiz, we fixed the forcing"), with who it's with."""
    from kurooto.core.infer import WITH_LINE
    from kurooto.modules.remember import sensitive

    text = f.read_text(encoding="utf-8", errors="replace")
    who = " and ".join(m["who"] for m in WITH_LINE.finditer(text))
    if not who:
        t = re.search(r"(?m)^# (.+)$", text)
        who = f"the {t.group(1).strip()} project" if t else "a project"
    out, inside = [], False
    for ln in text.splitlines():
        if ln.startswith("#"):
            inside = ln.strip().lower() == "## meetings"
            continue
        m = MEETING.match(ln.strip()) if inside else None
        if not m:
            continue
        try:
            at = _noon(m["date"])
        except ValueError:
            continue
        said = _clean(m["text"])
        line = f"Meeting with {who} (its words aren't kept)" if sensitive(said) else f"Meeting with {who}: {said}"
        out.append((at, line[:400], {}))
    return out


READERS = {"fact": _facts, "day": _day, "meeting": _meetings}


# ------------------------------------------------------------------------------------------- reading
def live(app: App, lo: float, hi: float) -> list[dict]:
    """Gists of what's still kept in full (calls, your requests, chats) in [lo, hi): made now, by the same rules as
    the ones kept when words fade (core/gists.py), never stored, never by a model."""
    from kurooto.core import gists

    out: list[dict] = []
    for kind, fn in gists.MAKERS.items():
        try:
            got = fn(app, lo, hi, local=False) if kind == "calls" else fn(app, lo, hi)
        except Exception as e:
            app.events.emit("ledger_live_failed", what=kind, error=f"{type(e).__name__}"[:60])
            continue
        out += [{"kind": "gist", "sub": g["kind"], "at": float(g["at"]), "text": g["text"], "live": True} for g in got]
    names = {g["text"].split(" · ", 1)[0] for g in out if g["sub"] == "request"}
    return [g for g in out if g["sub"] != "chat" or g["text"] not in names]


def locked(app: App) -> bool:
    """Is the ledger's key out of reach (a keychain still locked)?"""
    try:
        of(app).key()
    except Locked:
        return True
    return False


def everything(app: App, live_days: float = 0, fresh: bool = False) -> list[dict]:
    """Every row (the notes read again if they changed; fresh: even within the minute), with gists of what's still
    kept from the last live_days. Locked: none."""
    led = of(app)
    try:
        led.refresh(force=fresh)
        rows = led.rows()
    except Locked:
        return []
    if live_days:
        t = time.time()
        have = {(round(r["at"], 1), r["text"]) for r in rows if r["kind"] == "gist"}
        rows += [g for g in live(app, t - live_days * 86400, t + 60) if (round(g["at"], 1), g["text"]) not in have]
    return rows


def when_text(at: float, base: dt.datetime | None = None) -> str:
    """ "07:56 today", "07:56 yesterday", "Thu 22 Oct 07:56"."""
    t, base = dt.datetime.fromtimestamp(at), base or now()
    if t.date() == base.date():
        return f"{t:%H:%M} today"
    if t.date() == base.date() - dt.timedelta(days=1):
        return f"{t:%H:%M} yesterday"
    return f"{t:%a %d %b %H:%M}"


def said(r: dict) -> str:
    """How a thread came: "said on the call at 07:56 today", "said in a chat at 14:02 yesterday", "started ..."."""
    how = {"call": "said on the call", "chat": "said in a chat"}
    return f"{how.get(r.get('via'), 'started')} at {when_text(r['at'])}"


def label(r: dict) -> str:
    """Where a row is from, in a few words: "call at 07:56 today", "meeting, Tue 20 Oct (research/x/index.md)"."""
    day = f"{dt.datetime.fromtimestamp(r['at']):%a %d %b}"
    k, sub = r["kind"], r.get("sub")
    if k == "gist":
        what = {"call": "call", "request": "your AI request", "chat": "chat"}.get(sub, "gist")
        return f"{what} at {when_text(r['at'])}"
    if k == "thread":
        return f"{'open thread' if sub == 'open' else f'thread ({sub})'}, {said(r)}"
    if k == "meeting":
        return f"meeting, {day} ({r.get('source')})"
    if k == "day":
        return f"daily note, {day} ({r.get('source')})"
    return f"in {r.get('source')}"


# ------------------------------------------------------------------------------------- plain English
def a_past_day(text: str, base: dt.date | None = None) -> dt.date | None:
    """The day a question about the past means: "yesterday", "today", "last Thursday" or "on Thursday" (the latest
    one before today), "3 days ago", "on 20 Oct", "20 October", "Oct 20", "2026-10-20". None otherwise."""
    base = base or now().date()
    low = text.lower().strip()
    if re.search(r"\byesterday\b", low):
        return base - dt.timedelta(days=1)
    if re.search(r"\btoday\b|\bthis morning\b|\bearlier today\b", low):
        return base
    m = re.search(r"\b(\d{1,2}) days? ago\b", low)
    if m:
        return base - dt.timedelta(days=int(m.group(1)))
    m = re.search(r"\b(mon|tues|wednes|thurs|fri|satur|sun)day\b", low)
    if m:
        wd = [w[:3] for w in WEEKDAYS].index(m.group(1)[:3])
        back = (base.weekday() - wd) % 7 or 7
        return base - dt.timedelta(days=back)
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3})[a-z]*\b", low) or re.search(
        r"\b([a-z]{3})[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?\b", low
    )
    if m:
        d, mon = (m[1], m[2]) if m[1].isdigit() else (m[2], m[1])
        if mon in MONTHS:
            try:
                day = dt.date(base.year, MONTHS.index(mon) + 1, int(d))
            except ValueError:
                return None
            return day if day <= base else day.replace(year=base.year - 1)
    return None


def _snippet(text: str, want: set[str], n: int = 200) -> str:
    """The part of a row that has the words (a day row's line about them), cut to n characters."""
    parts = [p for p in re.split(r" · |; ", text) if p.strip()]
    hit = next((p for p in parts if want & words(p)), text) if want else text
    hit = hit.strip()
    return hit if len(hit) <= n else hit[: n - 1].rstrip() + "…"


def last_talk(app: App, who: str) -> str:
    """ "When did I last talk to Prof Lena Ortiz?": the newest rows that name them (meetings, daily notes, gists,
    threads), newest first."""
    names = [w for w in re.findall(r"[A-Za-z][\w'-]+", who) if w.lower().strip(".") not in TITLES]
    if not names:
        return "Who? Say their name, e.g. when did I last talk to Prof Ortiz."
    last = words(names[-1]) or {names[-1].lower()}
    want = words(" ".join(names)) or last
    if locked(app):
        return LOCKED
    rows = [r for r in everything(app, live_days=90, fresh=True) if last & words(r["text"])]
    if not rows:
        return (
            f"I have nothing with {who.strip()} in what I remember (meetings in project notes, daily notes, gists and "
            'threads). A project note\'s "## Meetings" lines count, and "met them today, ..." adds one.'
        )
    rows.sort(key=lambda r: (r["at"], len(want & words(r["text"]))), reverse=True)
    today = now().date()

    def one(r: dict) -> str:
        t = dt.datetime.fromtimestamp(r["at"])
        ago = (today - t.date()).days
        rel = "today" if ago == 0 else "yesterday" if ago == 1 else f"{ago} days ago"
        where = {"meeting": "a meeting", "day": "your daily note", "fact": "kept"}.get(r["kind"])
        if where:
            where += f" ({r.get('source')})"
        elif r["kind"] == "thread":
            where = f"a thread ({said(r).split(' at ')[0]})"
        else:
            where = {"call": "a call", "request": "your AI request", "chat": "a chat"}.get(r.get("sub"), "a gist")
            where += f" at {t:%H:%M}"
        return f"{t:%a %d %b} ({rel}), {where}: {_snippet(r['text'], want)}"

    out = [f"Last: {one(rows[0])}"]
    if len(rows) > 1:
        out.append("Before that:\n" + "\n".join(f"- {one(r)}" for r in rows[1:3]))
    return "\n".join(out)


def day_story(app: App, day: dt.date) -> str:
    """ "What was I doing last Thursday?": that day's daily note, meetings, gists and threads, in order."""
    if locked(app):
        return LOCKED
    lo = dt.datetime.combine(day, dt.time()).timestamp()
    hi = lo + 86400
    every = everything(app, live_days=max(LIVE_DAYS, (now().date() - day).days + 1), fresh=True)
    rows = [r for r in every if lo <= r["at"] < hi]
    closed = [r for r in every if r["kind"] == "thread" and lo <= float(r.get("closed_at") or 0) < hi]
    if not rows and not closed:
        return (
            f"Nothing remembered for {day:%a %d %b}: no daily note, meeting, gist or thread from that day. Calls and "
            "requests from then that were forgotten without a gist leave nothing."
        )
    rows.sort(key=lambda r: (r["kind"] != "day", r["at"]))
    out = [f"{day:%a %d %b}:"]
    for r in rows:
        if r["kind"] == "day":
            out.append(f"- Your daily note ({r.get('source')}): {_snippet(r['text'], set(), 400)}")
        elif r["kind"] == "fact":
            out.append(f"- Kept in {r.get('source')}: {r['text']}")
        elif r["kind"] in ("meeting",):
            out.append(f"- {r['text'][:300]}")
        else:
            t = dt.datetime.fromtimestamp(r["at"])
            what = {"call": "call", "request": "AI request", "chat": "chat"}.get(r.get("sub"), r["kind"])
            if r["kind"] == "thread":
                what = {"call": "said you'd, on a call", "chat": "said you'd"}.get(r.get("via"), "started")
            out.append(f"- {t:%H:%M} {what}: {r['text'][:240]}")
    for r in closed:
        out.append(f"- {dt.datetime.fromtimestamp(r['closed_at']):%H:%M} closed ({r.get('sub')}): {r['text'][:200]}")
    return "\n".join(out)[:3800]


def intent(app: App, text: str) -> tuple[str, str] | None:
    """The plain-English questions answered from the ledger: (intent name, the answer), or None."""
    m = LAST_TALK.match(text.strip())
    if m:
        return "memory_last_talk", last_talk(app, m["who"])
    m = DOING.match(text.strip())
    if m:
        day = a_past_day(m["when"])
        if day is not None:
            return "memory_day", day_story(app, day)
    return None


# ---------------------------------------------------------------------------------------------- /memory
def _row(i: int, r: dict) -> str:
    return f"{i}. {dt.datetime.fromtimestamp(r['at']):%d %b %Y} · {NAMES[r['kind']]} · {r['text'][:160]}"


def command(app: App, arg: str) -> str:
    """/memory: what's remembered, newest first and numbered; /memory <words>: the rows with all of them;
    /memory forget 3: drop number 3; /memory export: the gists and threads into a note."""
    arg = (arg or "").strip()
    led = of(app)
    try:
        led.refresh(force=True)  # only notes that changed are read
        items = list(reversed(led.rows()))  # a row's number is its place here
    except Locked:
        return LOCKED
    if re.fullmatch(r"(?i)export", arg):
        return export(app, items)
    m = re.fullmatch(r"(?i)(?:forget|drop|delete)\s+(\d{1,5})", arg)
    if m:
        n = int(m.group(1))
        if not 1 <= n <= len(items):
            return f"There's no row {n}; /memory shows them with their numbers."
        return forget(app, items[n - 1])
    if not items:
        return (
            "Nothing remembered yet. Gists of faded conversations, threads you're in the middle of, your "
            "how-to-help-me lines, daily notes and project meetings show up here."
        )
    want = [w for w in re.findall(r"\w+", arg.lower()) if w]
    hits = [(i, r) for i, r in enumerate(items, 1) if all(w in r["text"].lower() for w in want)]
    if not hits:
        return f"Nothing remembered has {arg!r}."
    counts = led.counts()
    have = ", ".join(f"{n} {NAMES[k]}{'s' if n != 1 else ''}" for k, n in sorted(counts.items()) if k in NAMES)
    head = f"Remembered with {arg!r}" if want else f"What I remember ({have}; encrypted on this computer)"
    body = "\n".join(_row(i, r) for i, r in hits[:SHOWN])
    more = f"\n…and {len(hits) - SHOWN} more" if len(hits) > SHOWN else ""
    tail = "\n/memory <words> finds; /memory forget 3 drops number 3; /memory export writes a note."
    return f"{head}:\n{body}{more}{tail}"[:3800]


def forget(app: App, row: dict) -> str:
    """Forget one row. A how-to-help-me line comes out of that note too (it's Kurooto's own line there); a daily note
    or a meeting stays in your note, which is yours."""
    led = of(app)
    note = ""
    if row["kind"] == "fact":
        from kurooto.modules.remember import remove_line

        note = (
            f" Taken out of {row.get('source')} too."
            if row.get("line") and remove_line(app, row["line"])
            else f" It's still in {row.get('source')} as you changed it; edit it there."
        )
    elif row["kind"] in NOTES:
        note = f" It's still in your note {row.get('source')}, which is yours to change."
    led.forget_row(row)
    app.events.emit("memory_forgotten", what=row["kind"])
    return f"Forgot it: {row['text'][:160]}.{note}"


def export(app: App, items: list[dict] | None = None) -> str:
    """/memory export: the gists and threads (what lives only here) as a Markdown note in your inbox; daily notes,
    meetings and how-to-help-me lines are your notes already."""
    from kurooto.core import layout
    from kurooto.core.tools import write_note_file

    led = of(app)
    try:
        rows = sorted(items if items is not None else led.rows(), key=lambda r: (r["at"], r["id"]))
    except Locked:
        return LOCKED
    stamp = now()
    f = layout.path(app, "note", slug=f"memory-{stamp:%Y-%m-%d-%H%M}")
    head = layout.frontmatter(app, "note", f, title="What Kurooto remembers")
    parts = [
        f"{head}# What {app.name} remembers ({stamp:%d %b %Y %H:%M})\n",
        f"Exported from {app.name}'s memory ledger, which stays encrypted on this computer. Daily notes, project "
        "meetings and your how-to-help-me note are your notes already, so they aren't repeated here.\n",
    ]
    for kind, title in (("thread", "Threads"), ("gist", "Gists")):
        got = [r for r in rows if r["kind"] == kind]
        if got:
            lines = []
            for r in got:
                state = f" ({r['sub']})" if kind == "thread" else ""
                how = f", {said(r)}" if kind == "thread" else ""
                lines.append(f"- {dt.datetime.fromtimestamp(r['at']):%Y-%m-%d %H:%M}{state}{how}: {r['text']}")
            parts.append(f"## {title}\n\n" + "\n".join(lines) + "\n")
    n = sum(1 for r in rows if r["kind"] in ("thread", "gist"))
    try:
        write_note_file(f, "\n".join(parts), create=True)
    except FileExistsError:
        return "An export from this minute is there already."
    app.events.emit("memory_exported", n=n)
    return f"Wrote {n} line{'s' if n != 1 else ''} (gists and threads) to {layout.shown(app, f)}."


def start(app: App) -> None:
    """Nightly: the notes read again, and threads nobody touched close (core/threads.py)."""
    import asyncio

    from kurooto.core import assembler, threads  # noqa: F401 (their memory.* settings are known from the start)

    def nightly() -> dict:
        out = {}
        try:
            out["notes"] = of(app).refresh(force=True)
            out["threads"] = threads.expire(app)
        except Locked:
            pass
        return out

    async def daily(payload: dict | None = None) -> dict:
        return await asyncio.to_thread(nightly)

    app.scheduler.action("memory.nightly", daily)
    app.scheduler.every("memory:nightly", WHEN, "memory.nightly", module="memory", misfire="coalesce")


__all__ = ["Ledger", "Locked", "of", "close", "words", "everything", "live", "label", "intent", "command", "start"]
