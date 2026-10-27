"""Free-tier reserve: the day's free AI limit is kept for what you're waiting on.

Google doesn't say how much of a free limit is left, so Kurooto counts the requests to each limit itself (each model of
your Gemini key, agy, another service) and learns the limit the first time the service answers "429: limit reached":
Google's answer often names the number, otherwise the count so far is the limit. It learns when the limit comes back
the same way: from the answer's own hint ("retry in 5h", "resets at 12:30"), else Google's day, which ends at midnight
Pacific time. agy's count comes from agy's own logs, so the runs you type yourself count too.

Once a day's count passes `background_pct` (70%) of a known limit, background work waits: the Classroom digest, the
nightly look back, skill changes, research digests, book and handwritten pages read by Gemini, and the quick "how hard
is this" question (which moves to the model on this computer, or to the rules, instead). The rest stays for calls,
voice notes, the morning plan and your own requests. Nothing is dropped: waiting requests stay in the queue and run
after the reset, or as soon as that limit answers again. A limit that's used up gets a plain line instead of an error:
"Google's free limit for today is used up, resets at 12:30; your calls and alarm still work." /usage shows each
limit, what's used of it and when it resets.

Settings (quota.*):
    on              true; false: background work never waits (counting and the plain line stay)
    background_pct  70: background work waits once a day's count reaches this share of the known limit
    limits          {}: your own numbers, which win over learned ones: {"gemini:gemini-flash-latest": 250, "agy": 900}
    soft            learned: a limit Kurooto learned from its own count is a measure, not a rule: it's shown, but
                    background work never waits for it (only a "limit reached" answer pauses a brain, until
                    the reset it names);
                    all: Google's own numbers are soft too; off: every known limit keeps its reserve (before 0.7.5)
    local           quick: the "how hard is this" question moves to the model on this computer (Local AI models);
                    background: queued background work moves there too instead of waiting; off: nothing moves
Only counts and times are kept (quota.json in Kurooto's state folder): nothing of what was asked.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults("quota", {"on": True, "background_pct": 70, "limits": {}, "soft": "learned", "local": "quick"})

PACIFIC = ZoneInfo("America/Los_Angeles")  # Google's daily free limits reset at midnight Pacific time
LOCAL = ("ollama",)  # models on this computer: no limit to keep
LONG_S = 3600  # "try again in" this long or longer: the day's limit, not a per-minute one
DAY = re.compile(r"per\s*day|daily|\bRPD\b", re.I)
MINUTE = re.compile(r"per\s*minute|per\s*second|\bRPM\b|\bTPM\b", re.I)
DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*(h|hrs?|hours?|m|mins?|minutes?|s|secs?|seconds?)\b", re.I)
AFTER = re.compile(
    r"(?:reset|retry|try again|available again)\w*\s+(?:in|after)\s+((?:\d+(?:\.\d+)?\s*[a-z]+[\s,]*(?:and\s+)?)+)",
    re.I,
)
AT = re.compile(r"reset\w*\s+(?:at|on)\s+(\d{1,2}):(\d{2})\s*([ap])?\.?m?\.?\s*(UTC|GMT|PST|PDT|PT)?\b", re.I)


# ------------------------------------------------------------------------------------- what a 429 says
def _json(text: str):
    """The first JSON value in the text (Google's error body, maybe after other words), or None."""
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    try:
        return json.JSONDecoder().raw_decode(text, min(starts))[0] if starts else None
    except ValueError:
        return None


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _seconds(text: str) -> float:
    unit = {"h": 3600, "m": 60, "s": 1}
    return sum(float(n) * unit[u[0].lower()] for n, u in DURATION.findall(text))


def hints(text: str, retry_after: float | None = None, at: float | None = None) -> dict:
    """What a "limit reached" answer says: {"per": "day" | "minute" | None, "limit": the number Google names,
    "retry_s": seconds to wait, "reset_at": when it comes back (a timestamp), "model": Google's name for the model}.
    Reads Google's JSON error (QuotaFailure, RetryInfo), its message, a Retry-After header and plain text."""
    text, at = str(text or "")[:50_000], time.time() if at is None else at
    out: dict = {"per": None, "limit": None, "retry_s": None, "reset_at": None, "model": None}
    out["retry_s"] = float(retry_after) if retry_after else None
    for d in _walk(_json(text)):
        if "quotaId" in d or "quotaMetric" in d:
            per = "day" if DAY.search(f"{d.get('quotaId', '')} {d.get('quotaMetric', '')}") else None
            per = per or ("minute" if MINUTE.search(str(d.get("quotaId", ""))) else None)
            if per == "day" or out["per"] is None:
                out["per"] = per or out["per"]
                if per == "day" and str(d.get("quotaValue", "")).isdigit():
                    out["limit"] = int(d["quotaValue"])
                out["model"] = (d.get("quotaDimensions") or {}).get("model") or out["model"]
        if isinstance(d.get("retryDelay"), str) and out["retry_s"] is None:
            out["retry_s"] = _seconds(d["retryDelay"]) or None
    if out["per"] is None:
        out["per"] = "day" if DAY.search(text) else "minute" if MINUTE.search(text) else None
    if out["limit"] is None and out["per"] == "day" and (m := re.search(r"\blimit:\s*(\d+)", text)):
        out["limit"] = int(m[1])
    if out["model"] is None and (m := re.search(r"\bmodel:\s*([\w.\-]+)", text)):
        out["model"] = m[1]
    if out["retry_s"] is None and (m := AFTER.search(text)):
        out["retry_s"] = _seconds(m[1]) or None
    if m := AT.search(text):
        h, mi, ampm, zone = int(m[1]) % 24, int(m[2]), (m[3] or "").lower(), (m[4] or "").upper()
        h = h + 12 if ampm == "p" and h < 12 else 0 if ampm == "a" and h == 12 else h
        tz = dt.UTC if zone in ("UTC", "GMT") else PACIFIC if zone in ("PST", "PDT", "PT") else None
        base = dt.datetime.fromtimestamp(at, tz) if tz else dt.datetime.fromtimestamp(at)
        if mi < 60:
            when = base.replace(hour=h, minute=mi, second=0, microsecond=0)
            out["reset_at"] = (when if when > base else when + dt.timedelta(days=1)).timestamp()
    return out


def daily(h: dict) -> bool | None:
    """Is this the day's limit? True, False (a per-minute one, which passes by itself) or None (it doesn't say)."""
    if h.get("reset_at") or h.get("per") == "day":
        return True
    if h.get("retry_s"):
        return h["retry_s"] >= LONG_S
    return False if h.get("per") == "minute" else None


# ------------------------------------------------------------------------------------- limits and days
def pool_id(brain: str, model: str | None = None, kind: str = "api") -> str | None:
    """Which limit a request counts against: each model of an API key has its own ("gemini:gemini-flash-latest");
    an agent program (agy, Claude Code, each extra Claude account: "claude:work") has one; a model on this computer
    has none (None)."""
    if not brain or brain in LOCAL:
        return None
    return f"{brain}:{model}" if kind == "api" and model else brain


def google(pool: str) -> bool:
    return pool.startswith("gemini:") or pool == "agy"


def day_start(pool: str, t: float) -> float:
    """When this limit's day began: midnight Pacific time for Google's limits, local midnight for anything else."""
    d = dt.datetime.fromtimestamp(t, PACIFIC) if google(pool) else dt.datetime.fromtimestamp(t)
    return d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def day_end(pool: str, t: float) -> float:
    tz = PACIFIC if google(pool) else None
    d = (dt.datetime.fromtimestamp(t, tz) if tz else dt.datetime.fromtimestamp(t)).date() + dt.timedelta(days=1)
    return dt.datetime.combine(d, dt.time(), tzinfo=tz).timestamp()


def label(pool: str) -> str:
    from kurooto import providers

    if providers.claude_accounts.is_id(pool):  # an extra Claude account ("claude:work") is one limit of its own
        return providers.label(pool)
    brain, _, model = pool.partition(":")
    name = "Gemini key" if brain == "gemini" else "agy" if brain == "agy" else providers.label(brain, brain)
    return f"{name}, {model}" if model else name


class Quota:
    def __init__(self, app: App):
        self.app = app
        self.file = app.paths.state / "quota.json"
        self.clock = time.time  # tests use a fake clock
        self.log_folder = None  # agy's logs (providers/agy.py log_dir()); tests point it at a sandbox
        self._lock = threading.RLock()

    def setting(self, key: str):
        return self.app.settings.get(f"quota.{key}")

    def on(self) -> bool:
        return self.setting("on") is not False

    # ---------------------------------------------------------------------------------- counting
    def pool(self, brain, effort: str = "medium") -> str | None:
        """The limit a brain's request at this effort counts against."""
        if brain is None:
            return None
        models = getattr(brain, "models", None)
        model = (models.get(effort) or models.get("medium")) if isinstance(models, dict) else None
        return pool_id(brain.id, model, brain.kind)

    def count(self, brain, model: str | None, result) -> None:
        """A brain's meter (providers.build attaches it): one request, and what came back (None: an answer)."""
        if result is None:
            return self.record(pool_id(brain.id, model, brain.kind), "ok")
        hint = (result.usage or {}).get("limit") if isinstance(result.usage, dict) else None
        self.record(pool_id(brain.id, model, brain.kind), result.verdict, result.detail, result.retry_after_s, hint)

    def record(self, pool: str | None, verdict="ok", detail: str = "", retry_after=None, hint=None) -> None:
        """One request to a limit. A "limit reached" answer teaches the limit and when it comes back; an answer from
        a limit thought used up means it's back (and that 429 wasn't the day's limit, unless it said so)."""
        if not pool:
            return
        v, back = str(getattr(verdict, "value", verdict)), False
        t = self.clock()
        with self._lock:
            data = jload(self.file, {}) or {}
            p = self._entry(data, pool, t)
            if v == "rate_limited":
                learned = self._hit(pool, p, t, hint or hints(detail, retry_after, t))
            else:
                learned = None
                if v != "auth":  # a request turned away at the door doesn't count
                    p["count"] = int(p.get("count", 0)) + 1
                if v == "ok" and p.get("until"):
                    back = self._back(p)
                used, unit = self._used(pool, p)
                if p.get("limit_src") == "count" and p.get("unit") == unit and used > int(p.get("limit") or 0):
                    p["limit"] = used  # past what was learned without a 429: it's at least this
            jsave(self.file, data)
        if learned:
            self.app.events.emit("quota_limit", pool=pool, **learned)
        if back:
            self.app.events.emit("quota_back", pool=pool)
            jobs = getattr(self.app, "jobs", None)
            if jobs is not None:
                jobs.resume()

    def _who(self, pool: str) -> str | None:
        """Who a limit belongs to, where that can change under the same name: the Claude account signed in (a
        fingerprint), since switching accounts gives a fresh limit. None for every other limit."""
        from kurooto.providers import claude_accounts

        return claude_accounts.signed_in_as(self.app, pool) if claude_accounts.is_claude(pool) else None

    def _entry(self, data: dict, pool: str, t: float) -> dict:
        """This limit's record for the current day (a new day, the limit coming back, or another account signed in
        starts the count again)."""
        p = data.setdefault("pools", {}).setdefault(pool, {"count": 0, "since": day_start(pool, t)})
        start = day_start(pool, t)
        if p.get("until") and p.get("who") and self._who(pool) not in (None, p["who"]):
            p.update(count=0, since=t)  # another account: its own limit, not the one that ran out
            for k in ("until", "until_src", "who", "reserved"):
                p.pop(k, None)
        if p.get("until") and t >= p["until"]:
            start = max(start, p["until"])
            p.pop("until", None)
            p.pop("until_src", None)
        if start > float(p.get("since") or 0):
            p.update(count=0, since=start)
            p.pop("reserved", None)
        return p

    def _hit(self, pool: str, p: dict, t: float, h: dict) -> dict | None:
        p["hit"] = t
        who = self._who(pool)
        if who:
            p["who"] = who  # the account that ran out (a fingerprint)
        if h.get("model"):
            p["model"] = h["model"]
        day = daily(h)
        if day is False:  # a per-minute limit: it passes by itself
            p["minute_hits"] = int(p.get("minute_hits", 0)) + 1
            return None
        again = bool(p.get("until"))  # used up already (a stale one was cleared by _entry): nothing new to learn
        if h.get("reset_at"):
            p["until"], p["until_src"] = max(h["reset_at"], t + 60), "hint"
        elif (h.get("retry_s") or 0) >= LONG_S:
            p["until"], p["until_src"] = t + h["retry_s"], "hint"
        else:
            p["until"], p["until_src"] = day_end(pool, t), "google" if pool.startswith("gemini:") else "estimate"
        used, unit = self._used(pool, p)
        new, how = (h["limit"], "google") if h.get("limit") else (used, "count")
        if new <= 0 or (how == "count" and (again or p.get("limit_src") == "google")):
            return None  # Google's own number stays; the count only teaches a limit Google didn't name
        old = p.get("limit")
        if how == "count" and p.get("limit_src") == "count" and old and new < int(old) * 0.5:
            return None  # the count's window had just started over: this isn't the limit, so the learned figure stays
        if not again:
            p["prev"] = {k: p.get(k) for k in ("limit", "limit_src", "unit", "learned")}
        p.update(limit=new, limit_src=how, unit=unit, learned=t)
        return {"limit": new, "source": how, "until": p["until"]}

    def _back(self, p: dict) -> bool:
        if p.get("until_src") != "hint" and p.get("limit_src") == "count" and isinstance(p.get("prev"), dict):
            prev = p.pop("prev")  # it answered again before the reset: that 429 wasn't the day's limit
            for k, v in prev.items():
                if v is None:
                    p.pop(k, None)
                else:
                    p[k] = v
        for k in ("until", "until_src", "who"):
            p.pop(k, None)
        return True

    def _used(self, pool: str, p: dict) -> tuple[int, str]:
        """How much of this limit is used today, and in what: "requests" (Kurooto's count), or "agy-log" (every agy
        run on this computer, from agy's own logs, also the ones you typed)."""
        n = int(p.get("count", 0))
        if pool == "agy":
            from kurooto.providers.agy import log_requests_since

            logged = log_requests_since(float(p.get("since") or 0), self.log_folder)
            if logged is not None and (logged or not n):
                return logged, "agy-log"
        return n, "requests"

    # ---------------------------------------------------------------------------------- deciding
    def status(self, pool: str) -> dict:
        """One limit today: used, limit (None: not known yet), where the limit came from, the share used, whether
        it's used up (until) and when it comes back (resets)."""
        t = self.clock()
        with self._lock:
            data = jload(self.file, {}) or {}
            p = dict(self._entry(data, pool, t))
        used, unit = self._used(pool, p)
        mine = (self.setting("limits") or {}).get(pool)
        if isinstance(mine, int) and mine > 0:
            limit, src = mine, "setting"
        elif p.get("limit") and p.get("unit", "requests") == unit:
            limit, src = int(p["limit"]), p.get("limit_src") or "count"
        else:
            limit, src = None, None
        return {
            "pool": pool,
            "label": label(pool),
            "used": used,
            "unit": unit,
            "limit": limit,
            "source": src,
            "learned": p.get("learned") if src in ("count", "google") else None,
            "pct": round(100 * used / limit) if limit else None,
            "until": p.get("until"),
            "until_src": p.get("until_src"),
            "resets": p.get("until") or day_end(pool, t),
            "model": p.get("model"),
        }

    def used_up(self, pool: str | None) -> float | None:
        """When a used-up limit comes back (a timestamp), or None if it isn't used up."""
        return self.status(pool)["until"] if pool else None

    def wait_until(self, pool: str | None) -> float | None:
        """Background work for this limit: None, go ahead; else the time to wait for (the reset). It waits once the
        limit is used up, or once the day's count reaches quota.background_pct of a known limit."""
        if not pool or not self.on():
            return None
        s = self.status(pool)
        if s["until"]:
            return s["until"]
        pct = self.setting("background_pct")
        pct = pct if isinstance(pct, (int, float)) and 0 < pct <= 100 else 70
        if s["limit"] and not self.soft(s) and s["used"] >= s["limit"] * pct / 100:
            self._reserving(pool, s)
            return s["resets"]
        return None

    def soft(self, s: dict) -> bool:
        """Is this limit only a measure (quota.soft)? A figure you set yourself (quota.limits) is always kept."""
        mode = self.setting("soft")
        if mode == "off" or s.get("source") == "setting":
            return False
        return mode == "all" or s.get("source") == "count"

    def _reserving(self, pool: str, s: dict) -> None:
        """Note it once a day per limit (the look back and the dashboard's activity read it)."""
        with self._lock:
            data = jload(self.file, {}) or {}
            p = self._entry(data, pool, self.clock())
            if p.get("reserved"):
                return
            p["reserved"] = self.clock()
            jsave(self.file, data)
        self.app.events.emit("quota_reserve", pool=pool, used=s["used"], limit=s["limit"], until=s["resets"])

    def arrange(self, chain: list, effort: str, background: bool) -> tuple[list, float | None]:
        """The brains a request tries, in order, and (for background work) when to try again if it can't go now.
        Your own requests try a used-up limit last. Background work skips limits kept for you; with nothing left it
        moves to the model on this computer (quota.local = background), or waits: ([], reset). A request that
        moved there returns the reset too, so it waits instead of failing when the model here can't do it."""
        if not self.on() or not chain:
            return chain, None
        if not background:
            return sorted(chain, key=lambda b: bool(self.used_up(self.pool(b, effort)))), None
        keep, waits = [], []
        for b in chain:
            w = self.wait_until(self.pool(b, effort))
            if w is None:
                keep.append(b)
            else:
                waits.append(w)
        if keep:
            return keep, None
        local = self.local() if self.setting("local") == "background" else None
        return ([local] if local is not None else []), min(waits)

    def local(self):
        from kurooto import providers

        return providers.local(self.app)

    # ---------------------------------------------------------------------------------- saying it
    def when(self, ts: float, about: bool = False) -> str:
        """ "at 12:30", "tomorrow at 12:30", "on Wed 22 Oct at 12:30" (local time)."""
        d = dt.datetime.fromtimestamp(ts)
        today = dt.datetime.fromtimestamp(self.clock()).date()
        hm = f"at {'about ' if about else ''}{d:%H:%M}"
        if d.date() == today:
            return hm
        return f"tomorrow {hm}" if d.date() == today + dt.timedelta(days=1) else f"on {d:%a %d %b} {hm}"

    def still_works(self) -> str:
        calls, alarm = self.app.is_on("calls"), self.app.is_on("alarm")
        if calls and alarm:
            return "your calls and alarm still work"
        if calls or alarm:
            return f"your {'calls still work' if calls else 'alarm still works'}"
        return "reminders still work"

    def line(self, pool: str | None, name: str = "") -> str:
        """The plain line for a used-up limit: "Google's free limit for today is used up, resets at 12:30; your calls
        and alarm still work." """
        s = self.status(pool) if pool else {}
        until = s.get("until") or s.get("resets")
        about = s.get("until_src") == "estimate" or (not s.get("until") and pool is not None and not google(pool))
        if pool and pool.startswith("gemini:"):
            head = "Google's free limit for today is used up"
        elif pool == "agy":
            head = "agy's limit for today is used up"
        else:
            head = f"{name or 'The AI'}'s limit for today is used up"
        when = f", resets {self.when(until, about)}" if until else ""
        return f"{head}{when}; {self.still_works()}."

    def report(self) -> list[dict]:
        """Every limit with something to show today: used, learned or set, or used up."""
        data = jload(self.file, {}) or {}
        pools = set(data.get("pools") or {}) | set(self.setting("limits") or {})
        rows = [self.status(p) for p in sorted(pools)]
        return [r for r in rows if r["used"] or r["limit"] or r["until"]]

    def text(self) -> str:
        """The lines /usage adds: each limit today, and the background work waiting for a reset."""
        rows = self.report()
        if not rows:
            return ""
        pct = self.setting("background_pct") or 70
        lines = ["\nToday's limits (counted here; Google doesn't say what's left):"]
        for r in rows:
            what = "model requests" if r["unit"] == "agy-log" else "requests"
            if r["until"]:
                about = r["until_src"] == "estimate"
                lines.append(f"{r['label']}: used up ({r['used']} {what}), back {self.when(r['until'], about)}.")
                continue
            if r["limit"]:
                src = {"google": "Google's number", "setting": "your setting"}.get(r["source"]) or (
                    f"learned {dt.datetime.fromtimestamp(r['learned']):%d %b}" if r.get("learned") else "learned"
                )
                soft = self.soft(r)
                wait = f"; background work waits from {int(r['limit'] * pct / 100)}" if self.on() and not soft else ""
                src += ", soft: only a measure" if soft else ""
                lines.append(
                    f"{r['label']}: {r['used']} of {r['limit']} {what} ({r['pct']}%, {src}){wait}. "
                    f"Resets {self.when(r['resets'], not google(r['pool']))}."
                )
            else:
                lines.append(
                    f"{r['label']}: {r['used']} {what}; the limit isn't known yet (learned the first time it's "
                    "reached)."
                )
        jobs = getattr(self.app, "jobs", None)
        n = jobs.waiting() if jobs is not None else 0
        if n:
            lines.append(f"{n} background request{'s wait' if n != 1 else ' waits'} for a reset.")
        return "\n".join(lines)
