"""The built-in features' health checks (core/health.py), one per feature. Read-only: a check looks at Kurooto's
state, the event log and, when the internet may be asked, the service itself (Telegram's getMe, the notes repository
on GitHub, your call line's /health); it never changes anything. The fixes live in core/health.py.

    telegram    the bot answers (a revoked token is a dead sign-in), and Kurooto is still reading your messages
    google      every Google account in use is signed in and doesn't end within 8 days (Testing apps end after 7);
                with Classroom on, Classroom synced within 26 awake hours
    notes_sync  the GitHub token works and doesn't expire within 10 days (GitHub warns 7 days ahead); a sync within
                24 awake hours (on the charger: it waits for it)
    calendar    a refresh within 12 awake hours
    calls       this computer is linked to your call line, the line answers, and the Cloudflare login it needs for
                updates is there
    alarm       tonight's alarm is planned, your call line has it and answers, and a phone is paired to ring
    backups, profile, gbrain   their last good run within 72, 72 and 24 awake hours
    kurooto     no message stuck in Kurooto's own queues
"""

from __future__ import annotations

import datetime as dt
import urllib.error
import urllib.request
from collections.abc import Callable

from kurooto.core import egress
from kurooto.core.health import Check

CRED_WARN_S = {"google": 8 * 86400, "github": 10 * 86400}  # a sign-in ending sooner than this is a problem
LINK_GRACE_S = 15 * 60  # the call line's link may drop this long (awake) before it's a problem


def builtin(m) -> Check | None:
    fn = BUILTIN.get(m.id)
    return fn(m) if fn else None


def _when(app, ts: float) -> str:
    from kurooto.core.presence import when

    return when(ts, app.health.clock())


# --------------------------------------------------------------------------------------------- Telegram
def telegram(m) -> Check:
    app = m.app

    def probe(net: bool):
        from kurooto.modules.telegram.api import TelegramError

        ok, why = m.ready()
        if not ok:
            return False, why
        loop = getattr(app, "_loop", None)
        if loop is not None and loop.is_running():
            t = app._background.get(m.id)
            if (t is None or t.done()) and app.power.may_run(m):
                return False, f"{app.name} stopped reading your messages", "reconnect"
        if not net:
            return None
        try:
            me = m.api().call("getMe", None, None, 8)
        except TelegramError as e:
            if e.code in (401, 404):
                return False, "Telegram doesn't accept your bot's token any more (revoked, or the bot was deleted)"
            return None, f"Telegram said: {e.description}"[:200]
        except OSError:
            return None, "couldn't reach Telegram just now"
        return True, f"@{me.get('username') or '?'} answers"

    return Check(
        "telegram",
        "Telegram bot",
        probe=probe,
        kind="credential",
        urgent=True,  # everything else reaches you through it
        help="Make a new token with @BotFather (/token) and paste it on the setup page.",
    )


# ----------------------------------------------------------------------------------------------- Google
def google(m) -> Check:
    from kurooto.modules.google import MAIN, SCOPES

    app = m.app
    classroom = bool(m.setting("classroom"))

    def probe(net: bool):
        if not m.client():
            return False, "its Google client is missing (Features → Google → Set up)"
        now = app.health.clock()
        names = list(dict.fromkeys(a for p in SCOPES if m.setting(p) for a in m.accounts_for(p))) or [MAIN]
        soon = []
        for a in names:
            t = m.tokens(a)
            who = "Google" if a == MAIN else f"{a} Google"
            if not t.get("refresh_token"):
                return False, f"your {who} sign-in has ended, so what uses it is paused"
            exp = t.get("refresh_expires")
            if exp and float(exp) - now < CRED_WARN_S["google"]:
                soon.append((float(exp), who))
        if soon:
            exp, who = min(soon)
            verb = "ended" if exp <= now else "ends"
            return False, f"your {who} sign-in {verb} {_when(app, exp)}"
        return True, "signed in"

    return Check(
        "google",
        "Classroom sync" if classroom else "Google sign-in",
        every_h=26 if classroom else 0,
        events=("classroom_synced",) if classroom else (),
        probe=probe,
        kind="credential",
        fix="sync" if classroom else "",
        sync=m.classroom_sync if classroom else None,
        deadlines=True,  # Classroom brings your assignments
        help="Features → Google → Save signs you in again; if that's needed every week, publish your Google app "
        "(MANUAL: Google, step 4).",
    )


# ------------------------------------------------------------------------------------------- Notes sync
def github_expiry(header: str | None) -> float | None:
    """GitHub's github-authentication-token-expiration header ("2026-11-01 00:00:00 UTC") as a timestamp."""
    if not header:
        return None
    try:
        return dt.datetime.strptime(header.strip().replace(" UTC", " +0000"), "%Y-%m-%d %H:%M:%S %z").timestamp()
    except ValueError:
        return None


def notes_sync(m) -> Check:
    from kurooto.modules.notes_sync import TOKEN

    app = m.app

    def probe(net: bool):
        if m.setting("remote"):  # a local repository (tests): no token
            return True, ""
        tok, repo = app.secrets.get(TOKEN), m.setting("repo")
        if not tok or not repo:
            return False, m.ready()[1] or "not connected to a repository"
        if not net:
            return None
        req = urllib.request.Request(  # noqa: S310 (GitHub's API, https): read-only
            f"{m.setting('api')}/repos/{repo}",
            headers={
                "Authorization": f"Bearer {tok}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "kurooto",
            },
        )
        try:
            with egress.urlopen(req, "Notes sync", timeout=20) as r:
                exp = github_expiry(r.headers.get("github-authentication-token-expiration"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "GitHub doesn't accept your notes token any more (it expired or was deleted)"
            if e.code == 404:
                return False, "your notes token can't see the repository any more"
            return None, f"GitHub answered {e.code}"
        except OSError:
            return None, "couldn't reach GitHub just now"
        now = app.health.clock()
        if exp and exp - now < CRED_WARN_S["github"]:
            verb = "expired" if exp <= now else "expires"
            return False, f"your GitHub token for notes {verb} {_when(app, exp)}"
        return True, "token works" + (f" until {dt.datetime.fromtimestamp(exp):%d %b %Y}" if exp else "")

    return Check(
        "notes_sync",
        "Notes sync",
        every_h=24,
        events=("notes_synced",),
        heavy=True,
        probe=probe,
        kind="credential",
        fix="sync",
        sync=m.sync,
        help="Make a new fine-grained token (the same repository, Contents: Read and write) and paste it: Features → "
        "Notes sync → Set up.",
    )


# --------------------------------------------------------------------------------------------- Calendar
def calendar(m) -> Check:
    return Check(
        "calendar",
        "Calendar",
        every_h=12,
        events=("calendar_synced",),
        fix="sync",
        sync=m.refresh,
        deadlines=True,  # your timetable and deadline-like events
        help="If your calendar's link changed, paste the new one (Features → Calendar).",
    )


# ----------------------------------------------------------------------------------- calls and the alarm
def linked(app, calls) -> bool | None:
    """Is this computer linked to the call line? False only when it hasn't been for LINK_GRACE_S awake; None when
    Kurooto isn't running (nothing is linked then) or it can't tell yet."""
    h = app.health
    if not h.running():
        return None
    if getattr(app, "_loop", None) is not None:
        if calls.connector.connected:
            return True
    else:
        from kurooto.core.state import jload

        if (jload(app.paths.state / "calls" / "link.json", {}) or {}).get("connected"):
            return True
    last = h.last_event("calls_link")  # when the link last went up or down
    if last is not None:
        since = last[0]
    else:
        on = h.last_event("module_enabled", lambda e: e.get("module") == "calls", key="on:calls")
        since = on[0] if on else (h._load().get("first") or {}).get("calls")
    if not since:
        return None
    return False if h.awake_s(since, h.clock()) > LINK_GRACE_S else None


def cloudflare(app) -> str:
    """What's wrong with the Cloudflare login your call line's updates need ("" if nothing)."""
    from kurooto.modules.calls import deploy

    last = app.health.last_event("calls_line_updated")
    failed = last is not None and last[1].get("ok") is False
    try:
        needed = deploy.needs_redeploy(app)
    except Exception:
        needed = False
    if not (needed or failed):
        return ""
    if not deploy.oauth_token(app.paths.config):
        return "your Cloudflare sign-in is gone, so your call line can't be updated"
    return "your call line couldn't be updated after Kurooto's last update" if failed else ""


def _line_answers(app, calls) -> bool | None:
    from kurooto.modules.calls import deploy

    h = deploy.health(calls.worker_url(), timeout=8)
    if h and h.get("ok"):
        return True
    return None if app.presence.net_down() else False


def calls(m) -> Check:
    app = m.app

    def probe(net: bool):
        ok, why = m.ready()
        if not ok:
            return False, why
        if linked(app, m) is False:
            return False, "this computer isn't linked to your call line", "reconnect"
        cf = cloudflare(app)
        if cf:
            return False, cf
        if net and _line_answers(app, m) is False:
            return False, "your call line doesn't answer"
        return True, "linked to your call line" if getattr(app, "_loop", None) is not None else "set up"

    return Check(
        "calls",
        "Call line",
        probe=probe,
        kind="link",
        deadlines=True,  # deadline calls go through it
        help="Settings → Features → Phone calls → Set up redeploys it (and signs in to Cloudflare again).",
    )


def _phones(calls) -> int | None:
    """How many phones are paired with the call line (None: can't ask now)."""
    if not calls.connector.connected:
        return None
    try:
        return len(calls.devices())
    except Exception:
        return None


def _daily_due(m, now: float) -> dt.datetime | None:
    """When the daily alarm should ring next (within a day), from alarm.daily and alarm.days."""
    from kurooto.modules.alarm import DAYS

    t = m.setting("daily")
    if not t:
        return None
    base = dt.datetime.fromtimestamp(now)
    for add in (0, 1):
        day = base.date() + dt.timedelta(days=add)
        try:
            at = dt.datetime.combine(day, dt.time.fromisoformat(t))
        except ValueError:
            return None
        if DAYS[day.weekday()] in (m.setting("days") or DAYS) and at > base:
            return at
    return None


def alarm(m) -> Check:
    app = m.app

    def probe(net: bool):
        now = app.health.clock()
        nxt = m.next()
        if nxt is None:
            due = _daily_due(m, now)
            if due is None:
                return True, "no alarm in the next day"
            return (
                False,
                f"Your daily alarm ({due:%a %H:%M}) isn't planned yet, so your call line doesn't have it (it would be "
                "planned at midnight, if this computer is awake then)",
                "alarm",
            )
        at = nxt.timestamp()
        if at - now > 86400:
            return True, f"next alarm {_when(app, at)}"
        lead = f"Your alarm at {_when(app, at)}"
        calls_m = app.modules.get("calls")
        if calls_m is None or not app.is_on("calls") or not calls_m.ready()[0]:
            return False, f"{lead} can't ring: Phone calls isn't set up"
        if linked(app, calls_m) is False:
            return False, f"{lead} might not ring: this computer isn't linked to your call line", "reconnect:calls"
        if net:
            if _line_answers(app, calls_m) is False:
                return False, f"{lead} might not ring: your call line doesn't answer"
            if _phones(calls_m) == 0:
                return False, f"{lead} can't ring: no phone is paired with your call line (Phone tab)"
        return True, f"{lead}: your call line has it"

    return Check("alarm", "Morning alarm", probe=probe, kind="alarm", urgent=True)


# -------------------------------------------------------------------------------- the ones that just run
def _ok(e: dict) -> bool:
    return e.get("ok") is not False


def backups(m) -> Check:
    return Check(
        "backups",
        "Backups",
        every_h=72,
        events=("backup_done",),
        heavy=True,
        help="Backups run on the charger: plug in for a while, or send /backup.",
    )


def profile(m) -> Check:
    return Check(
        "profile",
        "Profile sync",
        every_h=72,
        events=("profile_save",),
        ok_if=_ok,
        help="/profile save tries now and says what's wrong.",
    )


def gbrain(m) -> Check:
    return Check(
        "gbrain",
        "Notes brain",
        every_h=24,
        events=("gbrain_sync",),
        ok_if=lambda e: bool(e.get("ok")),
        heavy=True,
        fix="sync",
        sync=lambda: m.sync({"wait": 0}),
    )


BUILTIN: dict[str, Callable] = {
    "telegram": telegram,
    "google": google,
    "notes_sync": notes_sync,
    "calendar": calendar,
    "calls": calls,
    "alarm": alarm,
    "backups": backups,
    "profile": profile,
    "gbrain": gbrain,
}


# ------------------------------------------------------------------------------------ Kurooto's own queues
STUCK_S = 1800  # a queue that hasn't moved this long while it could have


def kurooto(app) -> Check:
    def probe(net: bool):
        now = app.health.clock()
        n = 0
        q = app.notifier.queue_file
        if q.exists() and not app.availability.focus_until() and now - q.stat().st_mtime > STUCK_S:
            n += sum(1 for ln in q.read_text(encoding="utf-8").splitlines() if ln.strip())
        out = app.presence.outbox
        if out.exists() and not app.presence.net_down() and now - out.stat().st_mtime > STUCK_S:
            n += app.presence._outbox_len()
        if n:
            return False, f"{n} message{'s' if n > 1 else ''} waited in a queue and never went out", "deliver"
        return True, ""

    return Check("kurooto", f"{app.name}'s queues", probe=probe, kind="queue")
