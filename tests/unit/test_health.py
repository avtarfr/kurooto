"""Kurooto keeps itself working (core/health.py, core/health_checks.py): a fake clock, fake sleeps and pauses, each
check, each fix, and what the daily pass says (or doesn't)."""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from kurooto.app import App
from kurooto.core.health import AUTO, FIXES, Check, Health, Latest
from kurooto.core.health_checks import github_expiry


class Clock:
    def __init__(self, t: float):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def add(self, seconds: float) -> float:
        self.t += seconds
        return self.t


DAY = dt.datetime(2026, 10, 18)  # a Sunday


def T(h: float, day: int = 0) -> float:
    return (DAY + dt.timedelta(days=day, hours=h)).timestamp()


def ev(app, t: float, kind: str, **fields) -> None:
    """An event in the log at a time of the test's choosing."""
    with open(app.events.file, "a", encoding="utf-8") as f:
        rec = {"ts": dt.datetime.fromtimestamp(t).isoformat()[:19], "kind": kind, **fields}
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def use(app, t: float) -> tuple[Health, Clock]:
    clock = Clock(t)
    h = Health(app, clock)
    h.running = lambda: True
    app.health = h
    return h, clock


def on(app, *ids: str) -> None:
    app.settings.set("modules.enabled", list(dict.fromkeys([*(app.settings.get("modules.enabled") or []), *ids])))


def timers(app, *ids: str) -> None:
    """The features' timers, as their start() would make them (without what start() does besides)."""
    for m in ids:
        app.scheduler.every(f"{m}:x", "every 15m", f"{m}.x", module=m)


def result(h: Health, cid: str, net: bool = False):
    return next(r for r in h.evaluate(net=net, only=cid, save=False) if r.id == cid)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    a = App()
    yield a
    a.close()


def notified(app) -> list[dict]:
    sent = []
    real = app.notify

    def grab(text, **kw):
        sent.append({"text": text, **kw})
        return real(text, **kw)

    app.notify = grab
    return sent


# ------------------------------------------------------------------------------------------- awake time
def test_a_shut_lid_is_not_a_failed_sync(app):
    on(app, "calendar")
    timers(app, "calendar")
    h, clock = use(app, T(8))
    ev(app, T(8), "calendar_synced", events=3)
    h.evaluate()  # first seen now
    app.presence.note_gap(T(9), T(21), "sleep")  # the lid was shut all day
    clock.t = T(22)
    assert result(h, "calendar").ok is True
    clock.t = T(8, 1)  # 24 h later, 12 of them asleep: just within 12 awake hours
    assert result(h, "calendar").ok is True
    clock.t = T(9, 1)
    r = result(h, "calendar")
    assert r.ok is False and r.kind == "quiet" and "13 h of that with this computer on" in r.detail
    assert r.fix == "sync" and r.fix_label == "Sync now"


def test_went_away_keeps_the_gap_even_with_presence_messages_off(app):
    app.settings.set("notify.presence.on", False)
    app.presence.went_away(T(1), T(5), "sleep")
    app.presence.went_away(T(6), T(6) + 0.5, "sleep")  # under a second: not kept
    assert app.presence.offline(T(0), T(4)) == [(T(1), T(4))]
    assert len(json.loads(app.presence.file.read_text())["gaps"]) == 1


def test_pauses_count_for_everyone_and_battery_saver_for_heavy_work(app):
    on(app, "gbrain", "calendar")
    timers(app, "gbrain", "calendar")
    h, clock = use(app, T(0))
    ev(app, T(0), "gbrain_sync", ok=True)
    ev(app, T(0), "calendar_synced")
    h.evaluate()
    h.power_changed("saver", T(1))
    h.power_changed("normal", T(20))
    clock.t = T(6, 1)  # 30 h; 19 of them on battery
    assert result(h, "gbrain").ok is True  # heavy: 11 h awake and allowed to run
    assert result(h, "calendar").ok is False  # not heavy: saver doesn't stop it
    h.power_changed("paused", T(6, 1))
    clock.t = T(23, 1)
    assert result(h, "gbrain").ok is True  # paused since: none of it counts
    ev(app, T(23, 1), "gbrain_sync", ok=False)  # a failed run isn't a success
    h.power_changed("normal", T(23, 1))
    clock.t = T(12, 2)  # 60 h: 19 on battery, 17 paused, 24 awake
    assert result(h, "gbrain").ok is True
    clock.t = T(14, 2)
    assert result(h, "gbrain").ok is False


def test_a_stopped_kurooto_counts_only_until_its_last_heartbeat(app):
    on(app, "calendar")
    timers(app, "calendar")
    h, clock = use(app, T(8))
    ev(app, T(8), "calendar_synced")
    h.evaluate()
    (app.paths.state / "presence.json").write_text(json.dumps({"alive": T(10)}))
    h.running = lambda: False
    clock.t = T(23)
    r = result(h, "calendar")
    assert r.ok is True and "worked 15 h ago" in r.detail


def test_latest_reads_only_what_was_added(app):
    lt = Latest(app.events.file)
    ev(app, T(1), "x", n=1)
    ev(app, T(2), "y")
    assert lt.get("x", "x", None, T(0))[1]["n"] == 1
    ev(app, T(3), "x", n=2)
    with open(app.events.file, "a", encoding="utf-8") as f:
        f.write('{"ts": "2026-10-18T04:00:00", "kind": "x", "n": 3')  # still being written
    assert lt.get("x", "x", None, T(0))[1]["n"] == 2
    with open(app.events.file, "a", encoding="utf-8") as f:
        f.write("}\n")
    assert lt.get("x", "x", None, T(0))[1]["n"] == 3
    assert lt.get("old", "y", None, T(5)) is None  # older than the horizon
    assert lt.get("odd", "x", lambda e: e["n"] == 1, T(0))[1]["n"] == 1


def test_never_worked_counts_from_when_it_was_turned_on(app):
    on(app, "calendar")
    timers(app, "calendar")
    h, clock = use(app, T(8))
    h.evaluate()  # the daemon's start
    ev(app, T(8), "module_enabled", module="calendar")
    assert result(h, "calendar").ok is None  # hasn't run yet: a note, not a problem
    clock.t = T(21)
    r = result(h, "calendar")
    assert r.ok is False and "hasn't worked yet" in r.detail


# ---------------------------------------------------------------------------------------------- checks
def test_telegram_check(env, monkeypatch):
    h, clock = use(env.app, time.time())
    r = next(r for r in h.evaluate(net=True) if r.id == "telegram")  # the daily pass keeps the answer
    assert r.ok is True and "answers" in r.detail
    assert result(h, "telegram").detail == r.detail  # without the internet: its last answer stands in
    env.fake.token = "999:other"  # the bot's token was revoked
    r = result(h, "telegram", net=True)
    assert r.ok is False and r.kind == "credential" and r.urgent and "doesn't accept" in r.detail
    env.app.settings.set("telegram.api_base", "http://127.0.0.1:9")  # no network: can't tell
    assert result(h, "telegram", net=True).ok is None


def test_telegram_check_notices_kurooto_stopped_reading(env):
    import asyncio

    h, _ = use(env.app, time.time())

    async def main():
        env.app._loop = asyncio.get_running_loop()
        try:
            return result(h, "telegram")
        finally:
            env.app._loop = None

    r = asyncio.run(main())
    assert r.ok is False and r.fix == "reconnect" and "stopped reading" in r.detail


def test_google_sign_in_dead_ending_and_classroom_quiet(app, monkeypatch):
    on(app, "google")
    g = app.modules["google"]
    app.secrets.set("google.client", json.dumps({"installed": {"client_id": "c", "client_secret": "s"}}))
    h, clock = use(app, T(8))
    app.secrets.set("google.tokens", json.dumps({"access_token": "a"}))
    r = result(h, "google")
    assert r.ok is False and r.kind == "credential" and "sign-in has ended" in r.detail and r.deadlines
    app.secrets.set("google.tokens", json.dumps({"refresh_token": "r", "refresh_expires": T(8, 3)}))
    r = result(h, "google")
    assert r.ok is False and "sign-in ends" in r.detail and "publish your Google app" in r.help
    app.secrets.set("google.tokens", json.dumps({"refresh_token": "r"}))
    ev(app, T(8), "classroom_synced")
    g.start()
    h.evaluate()
    assert result(h, "google").ok is True
    clock.t = T(11, 1)  # 27 h awake
    ran = threading.Event()
    monkeypatch.setattr(g, "classroom_sync", lambda: ran.set())
    r = result(h, "google")
    assert r.ok is False and r.kind == "quiet" and r.title == "Classroom sync" and r.fix == "sync"
    ok, said = h.fix("google")
    assert ok and "running it now" in said and ran.wait(5)


def test_google_keeps_when_a_testing_apps_sign_in_ends(app):
    g = app.modules["google"]
    g._save_tokens({"refresh_token": "r", "access_token": "a", "expires_in": 3600, "refresh_token_expires_in": 604799})
    assert 6.9 * 86400 < g.tokens()["refresh_expires"] - time.time() <= 7 * 86400
    g._save_tokens({"access_token": "b", "expires_in": 3600})  # a refresh keeps it
    assert "refresh_expires" in g.tokens()
    g._save_tokens({"refresh_token": "r2", "access_token": "c", "expires_in": 3600})  # a new sign-in, published app
    assert "refresh_expires" not in g.tokens()


class FakeGitHub:
    def __init__(self):
        self.status, self.expires = 200, ""
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                fake.auth = self.headers.get("Authorization")
                body = json.dumps({"private": True}).encode() if fake.status == 200 else b"{}"
                self.send_response(fake.status)
                if fake.expires:
                    self.send_header("github-authentication-token-expiration", fake.expires)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def test_notes_token_dead_or_expiring(app):
    gh = FakeGitHub()
    try:
        on(app, "notes_sync")
        app.settings.set("notes_sync.api", gh.base)
        app.settings.set("notes_sync.repo", "sam/notes")
        app.secrets.set("notes_sync.token", "github_pat_test")
        h, _ = use(app, time.time())
        r = result(h, "notes_sync", net=True)
        assert r.ok is not False and gh.auth == "Bearer github_pat_test"
        gh.expires = (dt.datetime.now(dt.UTC) + dt.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S UTC")
        r = result(h, "notes_sync", net=True)
        assert r.ok is False and r.kind == "credential" and "expires" in r.detail and "new fine-grained" in r.help
        gh.expires = (dt.datetime.now(dt.UTC) + dt.timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S UTC")
        assert result(h, "notes_sync", net=True).ok is not False
        gh.status = 401
        r = result(h, "notes_sync", net=True)
        assert r.ok is False and "doesn't accept your notes token" in r.detail
    finally:
        gh.server.shutdown()
    assert github_expiry("2026-11-01 00:00:00 UTC") == dt.datetime(2026, 11, 1, tzinfo=dt.UTC).timestamp()
    assert github_expiry("soon") is None and github_expiry(None) is None


def calls_ready(app) -> None:
    app.secrets.set("gemini.api_key", "k")
    app.settings.set("calls.worker", {"url": "http://127.0.0.1:9", "name": "w", "version": ""})
    for k in ("calls.call_secret", "calls.connector_secret", "calls.ntfy_topic", "calls.ntfy_key"):
        app.secrets.set(k, "x")


def test_call_line_link_and_cloudflare_login(app, monkeypatch):
    from kurooto.modules.calls import deploy

    on(app, "calls")
    calls_ready(app)
    monkeypatch.setattr(deploy, "needs_redeploy", lambda a: False)
    h, clock = use(app, T(8))
    ev(app, T(8), "calls_link", connected=False)
    clock.t = T(8) + 600  # dropped 10 minutes ago: it may come back by itself
    assert result(h, "calls").ok is not False
    clock.t = T(9)
    r = result(h, "calls")
    assert r.ok is False and r.kind == "link" and r.fix == "reconnect" and "isn't linked" in r.detail
    ev(app, T(9), "calls_link", connected=True)
    (app.paths.state / "calls").mkdir(parents=True, exist_ok=True)
    (app.paths.state / "calls" / "link.json").write_text(json.dumps({"connected": True}))
    monkeypatch.setattr(deploy, "needs_redeploy", lambda a: True)
    monkeypatch.setattr(deploy, "oauth_token", lambda d: None)
    r = result(h, "calls")
    assert r.ok is False and "Cloudflare sign-in is gone" in r.detail and not r.fix
    monkeypatch.setattr(deploy, "oauth_token", lambda d: "t")
    ev(app, T(9), "calls_line_updated", ok=False)
    assert "couldn't be updated" in result(h, "calls").detail


def test_alarm_not_planned_is_fixed_by_planning_it(app):
    on(app, "calls", "alarm")
    calls_ready(app)
    a = app.modules["alarm"]
    h, _ = use(app, time.time())
    assert result(h, "alarm").ok is True  # no alarm: nothing to check
    app.settings.set("alarm.daily", (dt.datetime.now() + dt.timedelta(hours=3)).strftime("%H:%M"))
    r = result(h, "alarm")
    assert r.ok is False and r.kind == "alarm" and r.fix == "alarm" and "isn't planned yet" in r.detail
    ok, said = h.fix("alarm")
    assert ok and "Alarm set for" in said and a.next() is not None
    r = result(h, "alarm")
    assert r.ok is True and "your call line has it" in r.detail


def test_alarm_path_broken(app, monkeypatch):
    from kurooto.core import health_checks

    on(app, "calls", "alarm")
    a = app.modules["alarm"]
    h, clock = use(app, time.time())
    a.set(dt.datetime.now().replace(microsecond=0) + dt.timedelta(hours=9))
    r = result(h, "alarm")
    assert r.ok is False and "can't ring: Phone calls isn't set up" in r.detail and not r.fix
    calls_ready(app)
    monkeypatch.setattr(health_checks, "linked", lambda app, c: False)
    r = result(h, "alarm")
    assert r.fix == "reconnect:calls" and r.fix_label == "Reconnect"
    monkeypatch.setattr(health_checks, "linked", lambda app, c: True)
    monkeypatch.setattr(health_checks, "_line_answers", lambda app, c: False)
    assert "doesn't answer" in result(h, "alarm", net=True).detail
    monkeypatch.setattr(health_checks, "_line_answers", lambda app, c: True)
    monkeypatch.setattr(health_checks, "_phones", lambda c: 0)
    assert "no phone is paired" in result(h, "alarm", net=True).detail
    monkeypatch.setattr(health_checks, "_phones", lambda c: 1)
    assert result(h, "alarm", net=True).ok is True


def test_backups_profile_and_notes_brain_go_quiet(app):
    on(app, "backups", "profile", "gbrain")
    timers(app, "backups", "profile", "gbrain")
    h, clock = use(app, T(0))
    ev(app, T(0), "backup_done", size=1)
    ev(app, T(0), "profile_save", ok=True)
    ev(app, T(0), "gbrain_sync", ok=True)
    h.evaluate()
    ev(app, T(30), "profile_save", ok=False)  # failed saves don't count
    clock.t = T(25)
    assert [result(h, c).ok for c in ("backups", "profile", "gbrain")] == [True, True, False]
    clock.t = T(73)
    rs = {c: result(h, c) for c in ("backups", "profile")}
    assert all(r.ok is False for r in rs.values())
    assert "plug in" in rs["backups"].help and not rs["backups"].fix


def test_stuck_queue_is_delivered(app):
    h, clock = use(app, time.time())
    assert result(h, "kurooto").ok is True
    q = app.notifier.queue_file
    q.write_text(json.dumps({"text": "held for focus", "kind": "info"}) + "\n")
    old = time.time() - 3600
    os.utime(q, (old, old))
    r = result(h, "kurooto")
    assert r.ok is False and r.fix == "deliver" and "1 message waited" in r.detail
    ok, said = h.fix("kurooto")
    assert ok and said == "Sent 1 waiting message." and not q.exists()
    assert app.scheduler.get("health:after:kurooto") is not None  # you'll hear whether it worked


# ----------------------------------------------------------------------------------------------- fixes
def test_missing_timers_are_put_back(app):
    on(app, "calendar")
    h, clock = use(app, T(8))
    ev(app, T(8), "calendar_synced")
    h.evaluate()
    clock.t = T(23)
    r = result(h, "calendar")
    assert r.ok is False and "timers are missing" in r.detail and r.fix == "rearm" and r.fix in AUTO
    ok, said = h.fix("calendar")
    assert ok and "timers are back" in said and app.scheduler.jobs("calendar:")


def test_reconnect_restarts_the_link(app, monkeypatch):
    on(app, "calls")
    calls_ready(app)
    h, clock = use(app, T(8))
    ev(app, T(8), "calls_link", connected=False)
    clock.t = T(10)
    did = []
    monkeypatch.setattr(app, "stop_background", lambda m: did.append(("stop", m.id)))
    monkeypatch.setattr(app, "start_background", lambda m: did.append(("start", m.id)))
    ok, said = h.fix("calls")
    assert ok and did == [("stop", "calls"), ("start", "calls")] and said == "Phone calls: reconnecting."


def test_no_fix_for_what_only_you_can_do_and_none_for_what_works(app):
    on(app, "calls")
    h, _ = use(app, T(8))
    ok, said = h.fix("calls")  # not set up: you have to
    assert not ok and "Nothing I can fix there myself" in said
    ok, said = h.fix("kurooto")
    assert not ok and "looks fine now" in said
    assert h.fix("nope") == (False, "There's no such check (or its feature is off).")
    assert set(FIXES) == {"sync", "rearm", "reconnect", "alarm", "deliver"}  # about five, all Kurooto's own state


def test_after_a_fix_you_hear_whether_it_worked(app):
    on(app, "calendar")
    h, clock = use(app, T(8))
    ev(app, T(8), "calendar_synced")
    h.evaluate()
    clock.t = T(23)
    sent = notified(app)
    assert "still isn't working" in h.after_fix("calendar")
    ev(app, T(23), "calendar_synced")
    timers(app, "calendar")
    assert h.after_fix("calendar") == "Calendar works again."
    assert len(sent) == 2


# ------------------------------------------------------------------------------------------ the daily pass
def test_daily_pass_is_silent_when_all_is_well(app):
    on(app, "calendar")
    timers(app, "calendar")
    h, clock = use(app, T(21))
    ev(app, T(20), "calendar_synced")
    sent = notified(app)
    assert h.daily() == {"told": [], "waiting": [], "digest": False}
    assert sent == []


def test_daily_pass_tries_the_safe_fix_first_then_looks_again(app, monkeypatch):
    from kurooto.core import health_checks

    monkeypatch.setattr(health_checks, "_line_answers", lambda app, c: True)
    monkeypatch.setattr(health_checks, "_phones", lambda c: 1)
    on(app, "calls", "alarm")
    calls_ready(app)
    app.settings.set("alarm.daily", (dt.datetime.now() + dt.timedelta(hours=3)).strftime("%H:%M"))
    h, _ = use(app, time.time())
    sent = notified(app)
    assert h.daily() == {"fixing": ["alarm"]}
    assert app.scheduler.get("health:recheck") is not None and sent == []
    assert h.recheck()["told"] == []  # it worked: nothing to say
    assert sent == []


def test_a_broken_alarm_path_says_set_your_own_alarm(app):
    on(app, "calls", "alarm")
    app.modules["alarm"].set(dt.datetime.now().replace(microsecond=0) + dt.timedelta(hours=9))
    h, _ = use(app, time.time())
    sent = notified(app)
    out = h.daily()
    assert out["told"] == ["alarm"]
    assert len(sent) == 1 and sent[0]["text"].endswith("Set your phone's own alarm too.")
    assert sent[0]["kind"] == "deadline"
    h.daily()
    assert len(sent) == 1  # told once


def test_a_deadline_in_48_h_makes_it_a_message_now_with_a_fix_button(env):
    app = env.app
    on(app, "deadlines", "calendar")
    timers(app, "calendar")
    app.modules["deadlines"].add("Lab report", dt.datetime.now() + dt.timedelta(hours=20))
    h, clock = use(app, time.time() - 20 * 3600)
    ev(app, clock.t, "calendar_synced")
    h.evaluate()
    clock.t = time.time()
    n = len(env.fake.texts())
    out = h.daily()
    assert out["told"] == ["calendar"]
    text = env.fake.texts()[n]
    assert text.startswith("Before Lab report") and "Calendar: hasn't worked since" in text
    kb = [p for m, p in env.fake.sent if m == "sendMessage"][-1]["reply_markup"]["inline_keyboard"]
    assert kb == [[{"text": "Sync now: Calendar", "callback_data": "health:calendar:fix"}]]
    h.daily()
    assert len(env.fake.texts()) == n + 1  # once per problem
    ev(app, time.time(), "calendar_synced")  # works again, then breaks again: news again
    h.recheck()
    assert "calendar" not in (h._load().get("told") or {})


def test_without_a_deadline_it_waits_for_the_weekly_summary(env):
    app = env.app
    on(app, "calendar", "weekly")
    timers(app, "calendar")
    h, clock = use(app, time.time() - 20 * 3600)
    ev(app, clock.t, "calendar_synced")
    h.evaluate()
    clock.t = time.time()
    n = len(env.fake.texts())
    out = h.daily()
    assert out == {"told": [], "waiting": ["calendar"], "digest": False} and len(env.fake.texts()) == n
    s = app.modules["weekly"].summary()
    assert "Needs a look:" in s and "- Calendar: hasn't worked since" in s and "/health" in s


def test_with_the_weekly_summary_off_one_sunday_message(app):
    on(app, "calendar")
    timers(app, "calendar")
    h, clock = use(app, T(8, -1))
    ev(app, T(8, -1), "calendar_synced")
    h.evaluate()
    clock.t = T(21)  # Sunday
    sent = notified(app)
    assert h.daily()["digest"] is True
    assert sent[0]["text"].startswith("Needs a look") and "Calendar" in sent[0]["text"]
    clock.t = T(21, 1)  # Monday
    assert h.daily()["digest"] is False
    clock.t = T(21, 7)  # next Sunday
    assert h.daily()["digest"] is True


def test_off_means_no_daily_pass(app):
    app.settings.set("health.on", False)
    h, _ = use(app, T(21))
    assert h.daily() == {"skipped": True} and h.board() == []


def test_start_registers_the_daily_pass_and_the_power_ledger(app):
    h, _ = use(app, T(8))
    h.start()
    assert app.scheduler.get("health:daily").spec == "daily 21:00"
    app.events.emit("power_mode", mode="paused", was="normal")
    assert h._load()["power"]["mode"] == "paused"
    h._unsub()


# ----------------------------------------------------------------------------------- who reads it
def test_telegram_health_command_and_fix_button(env):
    app = env.app
    on(app, "calendar")
    h, clock = use(app, T(8))
    assert env.say("/health").startswith("Everything Kurooto checks is working")
    ev(app, T(8), "calendar_synced")
    h.evaluate()
    clock.t = T(23)
    assert env.say("/health").startswith("1 of 3 checks need a look:")
    assert "Put its timers back" in str([p for m, p in env.fake.sent if m == "sendMessage"][-1]["reply_markup"])
    assert env.press("health:calendar:fix") == "Calendar: its timers are back."
    assert "/health" in app.help()


def test_doctor_api_cli_and_board(app, monkeypatch, capsys):
    from kurooto import cli, diagnostics
    from kurooto.web.api import Api
    from kurooto.web.live import Vitals

    on(app, "calendar")
    h, clock = use(app, T(8))
    ev(app, T(8), "calendar_synced")
    h.evaluate()
    clock.t = T(23)
    rows = {n: (ok, d) for n, ok, d in diagnostics.health_rows(app)}
    assert (
        rows["working: Calendar"][0] is False and "fix: kurooto doctor --fix calendar" in rows["working: Calendar"][1]
    )
    assert rows["working: Kurooto's queues"][0] is True
    api = Api(app)
    code, body = api.get("health")
    assert code == 200 and body["on"] and any(r["id"] == "calendar" and r["ok"] is False for r in body["results"])
    board = Vitals(app).board()
    assert board["health"][0]["id"] == "calendar" and board["health"][0]["fix_label"] == "Put its timers back"
    code, body = api.post("health/fix", {"id": "calendar"})
    assert body == {"ok": True, "message": "Calendar: its timers are back."}
    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: None)
    assert cli.main(["doctor", "--fix", "calendar"]) == 2
    monkeypatch.setattr(cli, "ask_running", lambda path, body=None: {"ok": True, "message": "done"})
    assert cli.main(["doctor", "--fix", "calendar"]) == 0 and "done" in capsys.readouterr().out


def test_an_add_ons_own_check(app):
    from kurooto.modules.base import Module

    class Mine(Module):
        id, title = "mine", "Mine"

        def health_check(self):
            return Check("mine", "My sync", every_h=1, events=("mine_ok",), help="Run it by hand.")

    class Broken(Module):
        id, title = "broken", "Broken"

        def health_check(self):
            raise RuntimeError("oops")

    app.modules["mine"], app.modules["broken"] = Mine(app), Broken(app)
    on(app, "mine", "broken")
    timers(app, "mine")
    h, clock = use(app, T(8))
    ev(app, T(8), "mine_ok")
    h.evaluate()
    clock.t = T(10)
    r = result(h, "mine")
    assert r.ok is False and r.line().endswith("Run it by hand")
    assert [c.id for c in h.checks()] == ["kurooto", "mine"]
    assert app.events.tail(5, {"health_failed"})
