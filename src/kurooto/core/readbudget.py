"""Tonight's reading budget for the concept graph (integrate.per_night = "auto"): how many book batches it reads, fitted
to the AI you read with by itself, so the reading never uses up what you need yourself.

- **A subscription program** (Claude Code, agy) shares one usage pool with your own chats, and the numbers aren't
  published. The budget is learned: 30 batches the first night (or the most read in one night before, if that's more);
  +50% after each night that read its whole budget with no limit hit (up to 300); a limit halves it, and nothing more
  is read until that limit's reset. Claude's 5-hour window and its weekly cap are told apart by how far away the reset
  is (over 6 hours: weekly); a weekly limit also starts the next week lower (the share of what that week fit, per
  night). Once a limit has shown what fits in one window (a 5-hour window; agy's day), a night reads at most
  integrate.share_pct (60%) of that, so the rest is yours. That number is forgotten after 14 days without a limit, so a
  bigger plan is noticed.
- **A free Gemini key**: integrate.share_pct of its learned daily limit (core/quota.py); learned as above until the
  limit is known. Under 10 batches a night, /graph and the feature's card say agy or the model on this computer reads
  books better.
- **An API key** (an OpenAI-compatible service with a key): money, integrate.max_cost_per_night (0.50, in the currency
  the service reports, USD), from the cost each answer reports, else estimated from its tokens at
  integrate.price_per_mtok.
- **The model on this computer** (Ollama, or any service at 127.0.0.1): no budget; the battery rules apply as before.

A number in integrate.per_night is a hard ceiling on all of that. The night starts 5 hours before you usually wake
(the alarm, else availability.night), so a 5-hour window the reading opened has reset when you get up; not before
bedtime, and never later than integrate.at. A night runs from one night's start to the next.

State: <state>/integrate/budget.json, per AI: the learned number and why, what fit in a window, the last limit, batch
times of the last 8 days, and 30 nights of history (budget, how it was decided, batches read, money spent, limit hit).
"""

from __future__ import annotations

import datetime as dt
import math
import re
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

FIRST = 30  # batches the first night, before anything is known
GROW = 1.5  # after a night that read its whole budget with no limit hit
FLOOR = 5  # a limit never halves it below this
MOST = 300  # the learned number never grows past this
WINDOW_S = 5 * 3600  # Claude's usage window
WEEKLY_S = 6 * 3600  # a reset further away than this: the weekly cap, not the 5-hour window
WEEK_S = 7 * 86400
TINY = 10  # under this many batches a night, a free key is the wrong AI for books
FORGET_S = 14 * 86400  # what fit in a window is forgotten after this long without a limit
KEEP_S = 8 * 86400  # batch times kept (for the week's count)
PLANS = ("claude", "agy")  # subscription programs: one usage pool shared with your own use
SHARE = 60
COST = 0.50
PRICE = {"in": 2.0, "out": 8.0}  # USD per million tokens, when the service reports no cost
NAMES = {"claude": "Claude", "agy": "agy", "gemini": "your Gemini key"}
KINDS = {"window": "the 5-hour window", "week": "the weekly limit", "day": "the day's limit"}


def kind(brain) -> str:
    """What limits a brain: "plan" (a subscription), "free" (a free Gemini key), "money" (an API key), "local" (a model
    on this computer) or "none" (no AI)."""
    if brain is None:
        return "none"
    if brain.id in PLANS:
        return "plan"
    local = getattr(brain, "local", None)
    if brain.id == "ollama" or (callable(local) and local()):
        return "local"
    if brain.id == "gemini":
        return "free"
    return "money" if brain.kind == "api" else "plan"


def cost_of(usage: dict, prices: dict | None = None) -> float:
    """What one answer cost: the cost the service reports, else its tokens at the given prices (per million)."""
    usage = usage if isinstance(usage, dict) else {}
    for k in ("cost", "total_cost", "total_cost_usd"):
        if isinstance(usage.get(k), (int, float)) and not isinstance(usage.get(k), bool):
            return float(usage[k])
    p = {**PRICE, **(prices if isinstance(prices, dict) else {})}
    tin = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    tout = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    try:
        return (float(tin) * float(p["in"]) + float(tout) * float(p["out"])) / 1e6
    except (TypeError, ValueError):
        return 0.0


class Budget:
    def __init__(self, app: App, bulk: Callable[[], str]):
        self.app = app
        self.bulk = bulk  # the AI the budget is for: the concept graph's bulk role
        self.clock = time.time  # tests use a fake clock
        self.lock = threading.RLock()

    @property
    def file(self):
        return self.app.paths.state / "integrate" / "budget.json"

    def setting(self, key: str):
        return self.app.settings.get(f"integrate.{key}")

    def ceiling(self) -> int | None:
        """integrate.per_night as a number (a hard ceiling), or None for "auto"."""
        v = self.setting("per_night")
        if isinstance(v, str) and v.strip().isdigit():
            v = int(v.strip())
        return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None

    def share(self) -> int:
        v = self.setting("share_pct")
        return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v <= 100 else SHARE

    def max_cost(self) -> float:
        v = self.setting("max_cost_per_night")
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else COST

    def brain(self, bid: str):
        from kurooto import providers

        return providers.build(self.app, bid) if bid else None

    # ------------------------------------------------------------------------------------------------- the night
    def at_time(self) -> dt.time:
        m = re.fullmatch(r"daily\s+(\d{1,2}):(\d{2})", str(self.setting("at") or "").strip())
        if m and int(m[1]) < 24 and int(m[2]) < 60:
            return dt.time(int(m[1]), int(m[2]))
        return dt.time(1, 30)

    def sleep(self, day: dt.date) -> tuple[dt.datetime | None, dt.datetime | None]:
        """(bedtime, wake) of the night that ends on the morning of `day`: the alarm's when it covers that night, else
        the night hours (availability.night), else (None, None)."""
        av = getattr(self.app, "availability", None)
        for bed, wake in av._sleep_windows() if av is not None else []:
            if wake.date() == day:
                return bed, wake
        n = self.app.settings.get("availability.night") or {}
        if not n.get("enabled") or n.get("alarm_only"):
            return None, None
        try:
            frm, to = dt.time.fromisoformat(n["from"]), dt.time.fromisoformat(n["to"])
        except (KeyError, TypeError, ValueError):
            return None, None
        bed = dt.datetime.combine(day if frm < to else day - dt.timedelta(days=1), frm)
        return bed, dt.datetime.combine(day, to)

    def plan(self, day: dt.date) -> tuple[dt.datetime, dt.datetime]:
        """(start, latest) of the night that ends on `day`. latest is integrate.at; the start is 5 hours before you
        wake, so a 5-hour window the reading opened has reset when you get up, but not before bedtime, and never later
        than integrate.at."""
        at = self.at_time()
        bed, wake = self.sleep(day)
        if wake is None:
            latest = dt.datetime.combine(day if at < dt.time(12) else day - dt.timedelta(days=1), at)
            return latest, latest
        latest = dt.datetime.combine(day, at)
        if latest > wake:
            latest -= dt.timedelta(days=1)
        early = wake - dt.timedelta(seconds=WINDOW_S)
        if bed is not None:
            early = max(early, bed)
        return min(latest, early), latest

    def night(self, t: float | None = None) -> str:
        """Which night it is: the morning it ends on (a night runs from its start to the next night's start)."""
        now = dt.datetime.fromtimestamp(self.clock() if t is None else t)
        for day in (now.date() + dt.timedelta(days=1), now.date(), now.date() - dt.timedelta(days=1)):
            if self.plan(day)[0] <= now:
                return day.isoformat()
        return (now.date() - dt.timedelta(days=2)).isoformat()

    def next_start(self) -> tuple[dt.datetime, dt.datetime] | None:
        """(start, latest) of the next night that hasn't started yet."""
        now = dt.datetime.fromtimestamp(self.clock())
        for day in (now.date(), now.date() + dt.timedelta(days=1), now.date() + dt.timedelta(days=2)):
            s, latest = self.plan(day)
            if s > now:
                return s, latest
        return None

    # ---------------------------------------------------------------------------------------------- the budget
    def _load(self) -> dict:
        return jload(self.file, {}) or {}

    def _save(self, data: dict) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        jsave(self.file, data)

    def _record(self, data: dict, bid: str) -> dict:
        return data.setdefault("brains", {}).setdefault(bid or "-", {})

    def _seed(self) -> tuple[int, str]:
        """The first night's number: 30, or the most the concept graph read in one night before (the ledger), if
        that's more."""
        led = jload(self.app.paths.state / "integrate" / "ledger.json", {}) or {}
        most = max((int(n.get("batches") or 0) for n in (led.get("nights") or {}).values()), default=0)
        if most > FIRST:
            return min(most, MOST), "the most read in one night before"
        return FIRST, "the first night's start, to see what your plan allows"

    def _cap(self, b: dict) -> int:
        """What the learned number may not grow past: 300, the share of what fit in a window, your ceiling."""
        caps = [MOST]
        if b.get("capacity"):
            caps.append(max(1, int(b["capacity"] * self.share() / 100)))
        if self.ceiling():
            caps.append(self.ceiling())
        return min(caps)

    def _roll(self, b: dict, key: str, t: float) -> None:
        """A new night: learn from the last one (+50% if it read its whole budget with no limit), forget a window
        capacity nobody has seen for 14 days."""
        if b.get("night") == key:
            return
        prev = (b.get("nights") or {}).get(b.get("night") or "")
        if b.get("capacity") and t - float(b.get("capacity_at") or 0) > FORGET_S:
            b.pop("capacity", None)
            b.pop("capacity_at", None)
        if "learned" not in b:
            b["learned"], b["why"] = self._seed()
        elif (
            prev
            and prev.get("kind") in ("plan", "free")
            and not prev.get("hit")
            and prev.get("batches")
            and int(prev.get("used") or 0) >= int(prev["batches"])
        ):
            old = int(b["learned"])
            new = max(old, min(math.ceil(old * GROW), self._cap(b)))
            if new > old:
                b["learned"], b["why"] = new, f"up from {old} after a night that read its whole budget with no limit"
        b["night"] = key
        nights = b.setdefault("nights", {})
        nights.setdefault(key, {"used": 0, "spent": 0.0})
        b["nights"] = dict(sorted(nights.items())[-30:])

    def _decide(self, b: dict, k: str, brain, t: float) -> tuple[int | None, float | None, str]:
        """Tonight's budget: (batches or None, money or None, how it was decided)."""
        ceil = self.ceiling()
        if k in ("local", "none"):
            if ceil:
                return ceil, None, f"your ceiling (integrate.per_night = {ceil})"
            return None, None, "no limit: the AI runs on this computer" if k == "local" else "no AI to read with"
        if k == "money":
            return ceil, self.max_cost(), "an API key is paid per request: integrate.max_cost_per_night"
        pct = self.share()
        if k == "free":
            quota = getattr(self.app, "quota", None)
            s = quota.status(quota.pool(brain, "low")) if quota is not None and brain is not None else {}
            if s.get("limit"):
                n = max(1, int(s["limit"] * pct / 100))
                how = f"{pct}% of your Gemini key's daily limit ({s['limit']} requests)"
                return (
                    (ceil, None, f"your ceiling (integrate.per_night = {ceil})")
                    if ceil and ceil < n
                    else (n, None, how)
                )
        n = int(b.get("learned") or FIRST)
        how = f"learned: {n} batches, {b.get('why') or 'learned'}"
        cap = b.get("capacity")
        if cap and int(cap * pct / 100) <= n:
            n = max(1, int(cap * pct / 100))
            at = float(b.get("capacity_at") or 0)
            when = (
                "tonight" if self.night(at) == self.night(t) else "last night" if t - at < 36 * 3600 else self.day(at)
            )
            how = f"learned: {n} batches, {pct}% of the {cap} that fit {when}"
        if ceil and ceil < n:
            n, how = ceil, f"your ceiling (integrate.per_night = {ceil})"
        return n, None, how

    @staticmethod
    def day(ts) -> str:
        return f"on {dt.datetime.fromtimestamp(float(ts or 0)):%d %b}"

    def tonight(self, save: bool = True) -> dict:
        """Tonight's budget for the bulk AI: {"brain", "kind", "night", "batches" (None: no limit), "cost" (None: not
        in money), "used", "spent", "how", "hold_until", "last_hit", "advice"}. A new night learns from the last."""
        bid = self.bulk() or ""
        brain = self.brain(bid)
        k = kind(brain)
        t = self.clock()
        key = self.night(t)
        with self.lock:
            data = self._load()
            b = self._record(data, bid)
            self._roll(b, key, t)
            rec = b["nights"][key]
            batches, cost, how = self._decide(b, k, brain, t)
            rec.update(kind=k, batches=batches, cost=cost, how=how)
            if save:
                self._save(data)
        hold = b.get("hold_until")
        out = {
            "brain": bid,
            "kind": k,
            "night": key,
            "batches": batches,
            "cost": cost,
            "used": int(rec.get("used") or 0),
            "spent": float(rec.get("spent") or 0),
            "how": how,
            "hold_until": hold if hold and hold > t else None,
            "last_hit": b.get("last_hit"),
            "advice": "",
        }
        if k == "free" and batches is not None and batches < TINY:
            out["advice"] = (
                f"A free Gemini key leaves room for only {batches} batches a night: agy (free with a Google account) "
                "or the model on this computer (Local AI models) reads books much better."
            )
        return out

    def gate(self) -> dict | None:
        """None: the next batch may go; else why not ({"limit": "hit" | "per_night" | "cost", "until"})."""
        r = self.tonight()
        if r["hold_until"]:
            return {"limit": "hit", "until": r["hold_until"]}
        if r["batches"] is not None and r["used"] >= r["batches"]:
            return {"limit": "per_night"}
        if r["cost"] is not None and r["spent"] >= r["cost"]:
            return {"limit": "cost"}
        return None

    # ------------------------------------------------------------------------------------------- what happened
    def count(self, bid: str | None = None) -> None:
        """A batch was read."""
        bid = self.bulk() if bid is None else bid
        t = self.clock()
        with self.lock:
            data = self._load()
            b = self._record(data, bid)
            self._roll(b, self.night(t), t)
            b["done"] = [x for x in b.get("done") or [] if x > t - KEEP_S] + [t]
            b["nights"][b["night"]]["used"] = int(b["nights"][b["night"]].get("used") or 0) + 1
            self._save(data)

    def spend(self, bid: str, cost: float) -> None:
        if cost <= 0:
            return
        t = self.clock()
        with self.lock:
            data = self._load()
            b = self._record(data, bid)
            self._roll(b, self.night(t), t)
            rec = b["nights"][b["night"]]
            rec["spent"] = round(float(rec.get("spent") or 0) + cost, 5)
            self._save(data)

    def seen(self, job, result) -> None:
        """A concept-graph request came back: note a limit the bulk AI hit (also one the job's stand-in answered
        for: core/jobs.py lists every limit in result.usage["limits"]), and what an API key's answer cost."""
        bid = self.bulk() or ""
        if not bid:
            return
        usage = getattr(result, "usage", None) or {}
        hits = [h for h in usage.get("limits") or [] if isinstance(h, dict) and h.get("brain") == bid]
        verdict = str(getattr(getattr(result, "verdict", None), "value", ""))
        if not hits and verdict == "rate_limited" and getattr(job, "brain", None) in (bid, None):
            hits = [{"brain": bid, "retry_after_s": result.retry_after_s, "detail": result.detail}]
        for h in hits[:1]:  # one request, one limit
            self.hit(bid, h)
        if getattr(job, "brain", None) == bid and verdict == "ok" and kind(self.brain(bid)) == "money":
            self.spend(bid, cost_of(usage, self.setting("price_per_mtok")))

    def hit(self, bid: str, h: dict) -> dict | None:
        """The bulk AI hit a limit: which one (by how far away its reset is), halve the learned number (a weekly limit
        starts the week lower), keep what fit in that window, and hold reading until the reset."""
        from kurooto.core import quota as q

        k = kind(self.brain(bid))
        if k not in ("plan", "free"):  # an API key's limits are quota's and the queue's; a local model has none
            return None
        t = float(h.get("at") or self.clock())
        detail = str(h.get("detail") or "")
        retry = h.get("retry_after_s")
        retry = float(retry) if isinstance(retry, (int, float)) and retry > 0 else None
        hint = q.hints(detail, retry, t)
        if bid != "claude" and q.daily(hint) is False:
            return None  # a per-minute limit (Google's): it passes by itself
        reset = t + retry if retry else hint.get("reset_at") or ((t + hint["retry_s"]) if hint.get("retry_s") else None)
        if bid == "claude" or (bid not in ("agy", "gemini") and k == "plan"):
            weekly = bool(re.search(r"\bweek", detail, re.I)) or (reset is not None and reset - t > WEEKLY_S)
            which = "week" if weekly else "window"
            reset = reset or t + (86400 if weekly else WINDOW_S)
        else:
            which = "day"
            reset = reset or q.day_end("agy" if bid in ("agy", "gemini") else bid, t)
        with self.lock:
            data = self._load()
            b = self._record(data, bid)
            self._roll(b, self.night(t), t)
            rec = b["nights"][b["night"]]
            if float(b.get("hold_until") or 0) > t:  # already holding for a limit: only the reset can move
                b["hold_until"] = max(float(b["hold_until"]), reset)
                self._save(data)
                return None
            done = [x for x in b.get("done") or [] if x <= t]
            if which == "window":
                since = reset - WINDOW_S if reset - t <= WINDOW_S else t - WINDOW_S
            elif which == "day":
                since = q.day_start("agy" if bid in ("agy", "gemini") else bid, t)
            else:
                since = t - WEEK_S
            fit = sum(1 for x in done if x >= since)
            old = int(b.get("learned") or FIRST)
            if which == "week":
                per_night = int(fit * self.share() / 100 / 7)
                new = max(FLOOR, min(old // 2, per_night or old // 2))
                why = f"lowered after the weekly limit ({fit} batches fit in that week)"
            else:
                new = max(FLOOR, old // 2)
                why = f"halved after {KINDS[which]} on {dt.datetime.fromtimestamp(t):%d %b at %H:%M}"
                if fit:
                    b["capacity"], b["capacity_at"], b["capacity_kind"] = fit, t, which
            b["learned"], b["why"] = new, why
            b["hold_until"] = reset
            b["last_hit"] = {"at": t, "kind": which, "reset": reset, "fit": fit}
            rec["hit"] = which
            self._save(data)
        self.app.events.emit("integrate_limit", brain=bid, limit=which, reset=reset, learned=new, fit=fit)
        return b["last_hit"]

    # ---------------------------------------------------------------------------------------------- saying it
    def when(self, ts: float) -> str:
        quota = getattr(self.app, "quota", None)
        if quota is not None:
            return quota.when(ts)
        return f"at {dt.datetime.fromtimestamp(ts):%H:%M}"

    def lines(self, save: bool = True) -> list[str]:
        """What /graph, /usage and the feature's card say about tonight's budget."""
        r = self.tonight(save=save)
        if r["kind"] == "none":
            return []
        name = NAMES.get(r["brain"], r["brain"])
        if r["cost"] is not None:
            head = (
                f"Tonight's reading budget: ${r['cost']:.2f} ({r['how']}); ${r['spent']:.2f} spent, "
                f"{r['used']} batches read."
            )
        elif r["batches"] is None:
            head = f"Tonight's reading: {r['used']} batches; {r['how']}."
        else:
            head = f"Tonight's reading budget: {r['batches']} batches ({r['how']}); {r['used']} read so far."
        out = [head]
        if r["hold_until"]:
            out.append(f"Reading waits for {name}'s limit, which resets {self.when(r['hold_until'])}.")
        hit = r.get("last_hit")
        if hit:
            at = dt.datetime.fromtimestamp(hit["at"])
            after = f" after {hit['fit']} batches in it" if hit.get("fit") else ""
            out.append(
                f"Last limit: {KINDS.get(hit['kind'], hit['kind'])} on {at:%a %d %b %H:%M}{after}; "
                f"{'resets' if hit['reset'] > self.clock() else 'reset'} {self.when(hit['reset'])}."
            )
        if r["advice"]:
            out.append(r["advice"])
        return out


def usage_text(app: App) -> str:
    """The lines /usage adds about the concept graph's reading budget (nothing when the feature is off)."""
    m = getattr(app, "modules", {}).get("integrate")
    if not m or not app.is_on("integrate") or not hasattr(m, "budget"):
        return ""
    try:
        lines = m.budget.lines(save=False)
    except Exception:
        return ""
    return ("\n\nConcept graph:\n" + "\n".join(lines)) if lines else ""
