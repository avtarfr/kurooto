"""What Kurooto is running, written for its own AI: so a question about Kurooto itself ("why didn't it ring?", "which
model answered?", "is my AI at its limit?") is answered from the facts, not guessed.

Two parts:
    the manual (data/ai-manual.md, shipped): how Kurooto works, where things are, what the AI may and may not do. Its
        tables (features, commands, guarded actions, settings) are written from the code by tools/gen_ai_manual.py,
        and a test and tools/release.py fail when they're out of date, so every release carries a current one.
    this computer's part (<state>/reserve/self.md, written here): the version and update channel, the OS and hardware
        profile, the AIs set up (models, fallback order, any waiting for a limit's reset), each feature that's on
        with its health check, the last day's failures and where logs and settings are.

self.md is written at start and looked at every 10 minutes with the other reserve files (core/reserve.py), and when it's
read (refresh): written again when the version, the features that are on, the AI settings or the update channel
changed, or when it's older than MAX_AGE_S. It sits in the reserve folder, which agent programs may read, beside a
copy of the manual (reserve/ai-manual.md). Nothing in it is what was asked, answered,
said or written (no request titles, no error text: an error is named by its kind), and no secrets: keys and tokens
are never read here.

Who reads it: the tool `kurooto_self` (every AI, and agent programs through `kurooto mcp`, which also offers it as the
MCP resources kurooto://self and kurooto://manual), /fixme's Ask my AI (it's put in the request), and any request that
asks about Kurooto itself (for_request: it goes in that request's context). AGENTS.md points a user's own agent at it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import re
import threading
import time
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import __version__

if TYPE_CHECKING:
    from kurooto.app import App

FILE = "self.md"
MANUAL = "ai-manual.md"
MAX_AGE_S = 600  # read after this long, it's written again (the failures and health move on)
DAY_S = 86400
MAX_FAILS = 12  # kinds of failure listed
CONTEXT_MAX = 6000  # characters of it a request's context gets
# a request about Kurooto itself: its context gets this computer's part
ABOUT_ME = re.compile(
    r"\b(kurooto|(which|what) (ai|model|brain)s? (are|did|do|does|is|was|answered|made|decided)|"
    r"your (ai|model|brain)|fallback|rate.?limit|usage limit|"
    r"(isn'?t|not|doesn'?t|don'?t|stopped|never) (working|ringing|answering|responding|syncing|arriving)|"
    r"why (did|didn'?t|does|doesn'?t|is|isn'?t|was|wasn'?t) (you|it|kurooto|my (alarm|phone|call|reminder|bot|sync|"
    r"notes?|digest))|diagnos\w*|troubleshoot\w*|fixme|what('?s| is) running|(which|what) features)\b",
    re.I,
)
SAFE = re.compile(r"^[\w.:@/+ -]{1,60}$")  # an event field value kept as it is (an id, a verdict, a brain)
KEEP = ("brain", "verdict", "module", "check", "pool", "lane", "effort", "name", "src", "layer", "stage", "via")
_lock = threading.Lock()


def path(app: App) -> Path:
    return app.paths.state / "reserve" / FILE


def manual_text() -> str:
    """The shipped manual (data/ai-manual.md)."""
    try:
        return resources.files("kurooto.data").joinpath(MANUAL).read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return ""


def manual_path() -> str:
    try:
        return str(resources.files("kurooto.data").joinpath(MANUAL))
    except Exception:
        return "data/ai-manual.md (inside Kurooto's program folder)"


# ------------------------------------------------------------------------------------------------- the facts
def fingerprint(app: App) -> str:
    """What self.md depends on that changes by someone's hand: the version, what's on, the AI settings, the channel."""
    s = app.settings
    parts = [
        __version__,
        sorted(s.get("modules.enabled") or []),
        s.get("brain") or {},
        s.get("updates.channel"),
        s.get("quota.on"),
    ]
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _when(ts: float | None) -> str:
    if not ts:
        return "never"
    d = dt.datetime.fromtimestamp(float(ts))
    return f"{d:%a %d %b %H:%M}"


def _machine(app: App) -> list[str]:
    from kurooto.core import hardware
    from kurooto.core.state import jload

    cached = (jload(app.paths.state / "hardware.json", {}) or {}).get("machine")
    try:
        m = hardware.Machine.from_dict(cached) if cached else hardware.detect(app.paths.app)
    except Exception:
        m = None
    out = [f"- OS: {platform.system()} {platform.release()} ({platform.machine()}), Python {platform.python_version()}"]
    if m is not None:
        gpus = ", ".join(f"{g.name}" + (f" {g.vram_gb:g} GB" if g.vram_gb else "") for g in m.gpus) or "none found"
        power = "battery" if m.battery else "no battery"
        out += [
            f"- CPU: {m.cpu} ({m.cores} cores, {m.threads} threads); memory {m.ram_gb:g} GB; graphics: {gpus}",
            f"- Hardware profile: {hardware.profile(m)} (what decides the local models offered); {power}",
        ]
    force = app.settings.get("hardware.force_profile")
    if force:
        out.append(f"- Hardware profile forced to {force} (hardware.force_profile)")
    try:
        out.append(f"- Power mode now: {app.power.current} ({app.power.why() or 'normal'})")
    except Exception:
        pass
    return out


def _brain_line(app: App, bid: str) -> str:
    from kurooto import providers
    from kurooto.providers import fallback

    b = providers.build(app, bid)
    if b is None:
        return f"{bid} (unknown here)"
    ok, why = b.available()
    state = "ready" if ok else why
    if ok and b.kind == "cli" and not b.has_worked(app):
        state = "installed, hasn't answered here yet"
    until = fallback.cooling(app, bid)
    if until:
        state += f"; at its limit, skipped until {_when(until)}"
    models = getattr(b, "levels", None)
    if isinstance(models, dict):  # agy: (model, effort) per level
        ms = {k: v[0] for k, v in models.items()}
    else:
        ms = getattr(b, "models", None) or {}
    shown = ", ".join(f"{k} {v}" for k, v in ms.items() if k in ("low", "medium", "high") and v)
    return f"{providers.CHOICES.get(bid, bid)} [{bid}]: {state}" + (f"; models: {shown}" if shown else "")


def _brains(app: App) -> list[str]:
    from kurooto.providers import fallback

    s = app.settings
    out = []
    main = s.get("brain.main") or ""
    out.append(f"- Main AI: {_brain_line(app, main)}" if main else "- Main AI: none picked (Settings → AI)")
    picked = fallback.chosen(app)
    on = ", ".join(sorted(fallback.triggers(app))) or "nothing"
    first = s.get("brain.fallback_first")
    if picked:
        out.append("- Your fallbacks (brain.fallback), in order, on any failure:")
        out += [f"  - {_brain_line(app, b)}" for b in picked]
    elif fallback.triggers(app):
        out.append(f"- No fallback picked: at a limit (brain.fallback_on: {on}) these take over, in order:")
        out += [f"  - {_brain_line(app, b)}" for b in fallback.AUTO if b != main]
    else:
        out.append("- No fallback: brain.fallback is empty and brain.fallback_on is []")
    if first:
        out.append(f"- The fallback goes first at these efforts (brain.fallback_first, tuned at night): {first}")
    how = s.get("brain.classify") or "rules"
    local = ((s.get("brain.models") or {}).get("ollama") or {}).get("medium")
    out.append(
        f"- Quick decisions (how hard a request is): {how}"
        + (f"; the model on this computer: {local}" if local else "")
        + " (the run receipt says 'decided by ...' when an AI made it)"
    )
    helper = getattr(app, "helper", None)  # core/helper.py
    if helper is not None and s.get("local_helper.on"):
        try:
            tag = helper.model().get("tag") or "?"
            state = "ready" if helper.ready() else "not ready (its speed test or the model is missing)"
            down = helper.holds()
        except Exception:
            tag, state, down = "?", "unknown", False
        out.append(
            f"- Offline helper (local_helper): {tag}, {state}; quick decisions when the rules would decide alone"
            + ("; the internet is down now: AI requests wait for it (that isn't a fallback)" if down else "")
        )
    roles = s.get("integrate.roles") or {}
    if app.is_on("integrate"):
        try:
            bulk, chk = app.modules["integrate"].roles()
            out.append(
                f"- Concept graph: {bulk or 'none'} reads (bulk), {chk or 'none'} checks"
                + (" (your choice)" if roles.get("bulk") or roles.get("check") else "")
            )
        except Exception:
            pass
    try:
        for r in app.quota.report():
            lim = f" of {r['limit']}" if r.get("limit") else ""
            back = f", used up until {_when(r['until'])}" if r.get("until") else ""
            out.append(f"- Today's count for {r['label']}: {r['used']}{lim} {r['unit']}{back}")
    except Exception:
        pass
    return out


def _requests(app: App) -> list[str]:
    from kurooto.providers.base import short_model

    out = []
    for j in app.jobs.recent(8):
        if j.status in ("queued", "running"):
            out.append(f"- {j.status}, {j.lane} lane, {j.brain or 'no AI yet'} (since {_when(j.started or j.created)})")
            continue
        model = f" {short_model(j.model, j.effort or '')}" if j.model else ""
        took = f", {j.seconds:.0f} s" if j.seconds else ""
        out.append(
            f"- {_when(j.created)}: {j.status}"
            + (f" ({j.verdict})" if j.verdict and j.verdict != "ok" else "")
            + f", {j.brain or '-'}{model}, {j.effort or '-'}{took}, {j.lane} lane"
        )
    return out or ["- none yet"]


def _features(app: App) -> list[str]:
    results = {}
    try:
        for r in app.health.evaluate(net=False, save=False):
            results[r.id] = r
    except Exception as e:
        results["_"] = type(e).__name__
    on = [m for m in app.modules.values() if app.is_on(m.id)]
    out = []
    for m in on:
        r = results.get(m.id)
        if r is None or not hasattr(r, "ok"):
            state = "on"
        elif r.ok is False:
            state = f"NOT WORKING: {str(r.detail)[:160]}" + (f" (fix: /fixme fix {r.id})" if r.fix_label else "")
        elif r.ok is None:
            state = "on, can't tell yet" + (f" ({str(r.detail)[:100]})" if r.detail else "")
        else:
            state = "working" + (f" ({str(r.detail)[:100]})" if r.detail else "")
        out.append(f"- {m.id} ({m.title}): {state}")
    other = [r for k, r in results.items() if hasattr(r, "ok") and k not in app.modules and r.ok is False]
    out += [f"- {r.title}: NOT WORKING: {str(r.detail)[:160]}" for r in other]
    off = sorted(m.id for m in app.modules.values() if not app.is_on(m.id))
    return (out or ["- none on"]) + [f"- Off: {', '.join(off) or 'none'}"]


def _safe(k: str, v) -> str | None:
    if k == "error":  # error text can quote what it was working on: only its kind
        kind = str(v).split(":", 1)[0].strip()
        return kind if re.fullmatch(r"[A-Za-z_][\w.]{0,40}", kind) else None
    if k in KEEP and isinstance(v, (str, int, float, bool)) and SAFE.match(str(v)):
        return str(v)
    return None


def failures(app: App, now: float | None = None) -> list[str]:
    """The last day's failures from the event log, counted by kind: no contents, only kinds, AIs, verdicts, features
    and an error's kind."""
    from kurooto.core.events import lines_back

    now = time.time() if now is None else now
    since = dt.datetime.fromtimestamp(now - DAY_S)
    seen: dict[str, list] = {}
    for f in (app.events.file, app.events.older):
        stop = False
        for ln in lines_back(f):
            try:
                rec = json.loads(ln)
                ts = dt.datetime.fromisoformat(str(rec.get("ts")))
            except (ValueError, TypeError):
                continue
            if ts.tzinfo is not None:
                ts = ts.astimezone().replace(tzinfo=None)
            if ts < since:
                stop = True
                break
            kind = str(rec.get("kind") or "")
            bad = (kind == "job_done" and rec.get("ok") is False) or re.search(
                r"fail|crash|error|limit|stuck|timeout|retired|denied", kind
            )
            if not bad:
                continue
            fields = [f"{k}={x}" for k in (*KEEP, "error") if k in rec and (x := _safe(k, rec[k])) is not None]
            key = " ".join([kind, *fields])
            got = seen.setdefault(key, [0, ts])
            got[0] += 1
        if stop:
            break
    rows = sorted(seen.items(), key=lambda kv: kv[1][1], reverse=True)[:MAX_FAILS]
    return [f"- {n}x {key} (last {t:%H:%M})" for key, (n, t) in rows] or ["- none in the last 24 hours"]


def build(app: App) -> str:
    """This computer's part, as Markdown."""
    from kurooto.core.state import jload

    p = app.paths
    daemon = jload(p.state / "daemon.json", {}) or {}
    channel = app.settings.get("updates.channel") or "stable"
    lines = [
        f"# What {app.name} is running",
        "",
        f"Written {dt.datetime.now():%a %d %b %Y %H:%M} by Kurooto {__version__}. For you, its AI: read this before "
        "answering a question about Kurooto itself. It holds no messages, notes or secrets. How Kurooto works, and "
        f"what you may and may not do: the manual ({manual_path()}; the tool kurooto_self with part=manual).",
        "",
        "## Kurooto",
        f"- Version {__version__}, update channel {channel}, updates {app.settings.get('updates.mode') or 'night'}",
        f"- Background program: started {_when(daemon.get('started'))}"
        if daemon
        else "- Background program: not started on this computer yet",
        f"- Assistant name: {app.name}",
        "",
        "## This computer",
        *_machine(app),
        "",
        "## AI",
        *_brains(app),
        "",
        "## Last requests (newest first; what was asked isn't here)",
        *_requests(app),
        "",
        "## Features (on, with their health check)",
        *_features(app),
        "",
        "## Failures in the last 24 hours (from the event log; kinds only)",
        *failures(app),
        "",
        "## Where things are",
        f"- Settings: {p.config / 'settings.json'} (change them in the dashboard's Settings, not by hand)",
        f"- Log: {p.logs / 'kurooto.log'}; what happened: {p.state / 'events.jsonl'} (one JSON line per event)",
        f"- AI requests: {p.state / 'jobs.db'}; limits: {p.state / 'quota.json'}, {p.state / 'brain-limits.json'}",
        f"- What's set or due (alarms, deadlines, the calendar, settings): {p.state / 'reserve'} (agent-guide.md)",
        f"- Notes folder: {app.workspace}",
        f"- This file: {path(app)}",
        "",
        "## Looking further",
        "- Inside a Kurooto request: the tools kurooto_self (this) and sync_status; `kurooto` itself never runs "
        "there, so ask the user to send /health (what isn't working, with Fix buttons), /fixme (what to do, by rules) "
        "or /jobs (what the AI is doing), or to run `kurooto doctor`.",
        "- Your own agent on this computer (outside a request): `kurooto doctor` (read-only checks; exit code = "
        "problems), `kurooto doctor --json`, `kurooto logs -n 100`, `kurooto jobs`, `kurooto fixme`.",
        "",
    ]
    return "\n".join(lines)


def write(app: App) -> Path:
    """Write self.md now."""
    from kurooto.core.state import jsave

    text = build(app)
    f = path(app)
    with _lock:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f"{f.name}.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(f)
        jsave(app.paths.state / "reserve" / ".self.json", {"fingerprint": fingerprint(app), "at": time.time()})
    return f


def stale(app: App, max_age: float = MAX_AGE_S) -> bool:
    from kurooto.core.state import jload

    meta = jload(app.paths.state / "reserve" / ".self.json", {}) or {}
    f = path(app)
    if not f.exists() or meta.get("fingerprint") != fingerprint(app):
        return True
    return time.time() - float(meta.get("at") or 0) > max_age


def refresh(app: App, max_age: float = MAX_AGE_S) -> str:
    """self.md, written again first if it's out of date. Never fails: a broken part says so."""
    try:
        if stale(app, max_age):
            write(app)
        return path(app).read_text(encoding="utf-8")
    except Exception as e:
        app.events.emit("selfdoc_failed", error=type(e).__name__)
        return f"(What Kurooto is running couldn't be written: {type(e).__name__}.)"


def wanted(prompt: str, name: str = "") -> bool:
    """Is this request about Kurooto itself (by its name, or the name you gave it)?"""
    prompt = prompt or ""
    if name and name.lower() != "kurooto" and re.search(rf"\b{re.escape(name)}\b", prompt, re.I):
        return True
    return bool(ABOUT_ME.search(prompt))


def for_request(app: App, prompt: str) -> str:
    """For a request about Kurooto itself: this computer's part, for its context ("" for any other request)."""
    if not wanted(prompt, app.name) or f"# What {app.name} is running" in (prompt or ""):  # (/fixme ai has it)
        return ""
    text = refresh(app)
    if len(text) > CONTEXT_MAX:
        text = text[:CONTEXT_MAX] + "\n…(the rest: the tool kurooto_self)"
    return f"About Kurooto on this computer, for this question (from {path(app)}):\n{text}"


def tool(app: App):
    """The tool every AI gets: kurooto_self."""
    from kurooto.modules.calls.tools import Tool, arg

    def run(a: dict) -> str:
        part = str(a.get("part") or "running").lower()
        if part.startswith("man"):
            return manual_text() or "The manual isn't in this installation."
        return refresh(app)

    return Tool(
        "kurooto_self",
        "What Kurooto is running on this computer: its version, the AIs and models set up (and any at a limit), the "
        "fallback order, each feature that's on and whether it works, the last day's failures, where logs and "
        "settings are. part=manual gives how Kurooto works and what you may and may not do. Read it before answering "
        "any question about Kurooto itself.",
        run,
        params={"part": arg("running (default): this computer's state; manual: how Kurooto works")},
        writes=False,
        hint="For a question about Kurooto itself (why something didn't happen, which AI or model, what's on), call "
        "kurooto_self first.",
    )
