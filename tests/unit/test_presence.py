"""Going offline and coming back (core/presence.py): a fake clock, the fake Telegram, no network."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import socket
import sys
import time

import pytest

from kurooto.core import endsession
from kurooto.core.presence import SETTLE_S, TICK_S, Presence, span, when
from kurooto.modules.telegram.api import TelegramAPI


class Clock:
    def __init__(self, t: dt.datetime):
        self.t = t.timestamp()

    def __call__(self) -> float:
        return self.t

    def at(self, t: dt.datetime) -> float:
        self.t = t.timestamp()
        return self.t

    def add(self, seconds: float) -> float:
        self.t += seconds
        return self.t


DAY = dt.datetime(2026, 10, 20)


def T(h: int, m: int = 0, day: int = 0) -> dt.datetime:
    return DAY + dt.timedelta(days=day, hours=h, minutes=m)


def fresh(app, clock) -> Presence:
    """What a new start of the daemon has: a new Presence (nothing in memory), the same files."""
    p = Presence(app, clock)
    app.presence = p
    return p


def settle(p: Presence, clock: Clock, ticks: int = 4) -> None:
    for _ in range(ticks):
        clock.add(SETTLE_S / 3 + 1)
        p.tick()


def awake(p: Presence, clock: Clock, until: dt.datetime) -> None:
    """The computer stays up until then (a tick every TICK_S, so no clock jump)."""
    while clock.t < until.timestamp():
        clock.t = min(clock.t + TICK_S, until.timestamp())
        p.tick()


def texts(env) -> list[str]:
    return [t for t in env.fake.texts() if t]


def presence_events(app, kind: str) -> list[dict]:
    return [e for e in app.events.tail(200) if e["kind"] == kind]


@pytest.fixture
def pres(env):
    clock = Clock(T(12))
    env.clock = clock
    env.p = fresh(env.app, clock)
    return env


def test_wording():
    assert span(40 * 60) == "40 min" and span(80 * 60) == "1 h 20 min" and span(7 * 3600 + 600) == "7 h"
    assert span(3 * 86400) == "3 days"
    ref = T(9).timestamp()
    assert when(T(8, 5).timestamp(), ref) == "08:05"
    assert when(T(22, 10, day=-1).timestamp(), ref) == f"{T(22, 10, day=-1):%a} 22:10"


def test_clean_stop_says_goodbye_and_the_next_start_says_its_back(pres):
    app, clock = pres.app, pres.clock
    pres.p.start()
    app.stop_reason = "stopped"
    asyncio.run(pres.p.going_offline())
    assert texts(pres)[-1] == "Kurooto is going offline (stopped): calls and reminders will wait until it's back."
    off = presence_events(app, "presence_offline")[-1]
    assert off["by"] == "computer" and off["told"] == ["telegram"] and off["reason"] == "stopped"
    n = len(texts(pres))
    clock.at(T(19))  # seven hours later, a new start
    p = fresh(app, clock)
    p.start()
    p.tick()
    assert len(texts(pres)) == n  # waits until it has been up a minute
    settle(p, clock)
    assert texts(pres)[n:] == ["Kurooto is back online (offline since 12:00, 7 h)."]
    on = presence_events(app, "presence_online")[-1]
    assert on["message"] == "sent" and on["minutes"] == 420 and on["sent"] == ["telegram"]


def test_a_goodbye_is_always_followed_by_back_even_when_short(pres):
    app, clock = pres.app, pres.clock
    pres.p.start()
    asyncio.run(pres.p.going_offline("stopped"))
    clock.add(120)  # back two minutes later: you were told it went, so you're told it's back
    p = fresh(app, clock)
    p.start()
    settle(p, clock)
    assert texts(pres)[-1] == "Kurooto is back online (offline since 12:00, 2 min)."


def test_update_restart_says_nothing(pres):
    app, clock = pres.app, pres.clock
    pres.p.start()
    app.restart_requested = True
    n = len(texts(pres))
    asyncio.run(pres.p.going_offline())
    assert len(texts(pres)) == n
    assert json.loads(pres.p.file.read_text())["stop"]["reason"] == "restart"
    app.restart_requested = False
    clock.add(90)
    p = fresh(app, clock)
    p.start()
    settle(p, clock)
    assert len(texts(pres)) == n and not presence_events(app, "presence_online")
    # a restart that took long (an update that kept failing) is time away like any other
    app.restart_requested = True
    asyncio.run(p.going_offline())
    app.restart_requested = False
    clock.add(40 * 60)
    p = fresh(app, clock)
    p.start()
    settle(p, clock)
    assert texts(pres)[-1].startswith("Kurooto is back online (offline since") and "40 min" in texts(pres)[-1]


def test_crash_or_power_loss_counts_from_the_heartbeat(pres):
    app, clock = pres.app, pres.clock
    pres.p.start()
    clock.add(30)
    pres.p.tick()  # running...
    clock.add(3 * 3600)  # ...then gone without a goodbye; back three hours later
    p = fresh(app, clock)
    p.start()
    settle(p, clock)
    assert texts(pres)[-1] == "Kurooto is back online (offline since 12:00, 3 h)."
    # a crash the supervisor restarts in seconds says nothing
    n = len(texts(pres))
    clock.add(15)
    p = fresh(app, clock)
    p.start()
    settle(p, clock)
    assert len(texts(pres)) == n


def test_wake_from_sleep_is_a_clock_jump(pres):
    clock = pres.clock
    pres.p.start()
    clock.add(20)
    pres.p.tick()
    n = len(texts(pres))
    clock.at(T(14, 30))  # the lid was closed for about 2.5 hours
    pres.p.tick()
    settle(pres.p, clock)
    assert texts(pres)[n:] == ["Kurooto is back online (offline since 12:00, 2 h 30 min)."]
    # a short nap says nothing
    clock.add(20)
    pres.p.tick()
    clock.add(5 * 60)
    pres.p.tick()
    settle(pres.p, clock)
    assert len(texts(pres)) == n + 1


def test_several_sleeps_close_together_give_one_message(pres):
    clock = pres.clock
    pres.p.start()
    n = len(texts(pres))
    clock.at(T(12, 30))
    pres.p.tick()  # back after 30 min...
    clock.add(20)
    pres.p.tick()  # ...for 20 seconds,
    clock.add(3 * 60)
    pres.p.tick()  # asleep 3 min (too short to count, but the message keeps waiting),
    clock.add(20)
    pres.p.tick()
    clock.at(T(12, 50))
    pres.p.tick()  # and 15 min more
    settle(pres.p, clock)
    assert texts(pres)[n:] == ["Kurooto is back online (offline since 12:00, 50 min)."]


def test_back_in_the_night_waits_for_the_morning_or_is_dropped(pres):
    app, clock = pres.app, pres.clock
    clock.at(T(22))
    pres.p.start()
    clock.add(20)
    pres.p.tick()
    clock.at(T(2, day=1))  # woke at 2 am (night: 23:30-07:00): nothing said it had gone, so it's dropped
    pres.p.tick()
    settle(pres.p, clock)
    n = len(texts(pres))
    awake(pres.p, clock, T(7, 1, day=1))
    assert len(texts(pres)) == n
    assert presence_events(app, "presence_online")[-1]["message"].startswith("dropped")


def test_a_goodbye_at_night_waits_and_back_in_the_night_comes_in_the_morning(pres):
    app, clock = pres.app, pres.clock
    clock.at(T(21))
    pres.p.start()
    asyncio.run(pres.p.going_offline("stopped"))  # 21:00: said now
    told = len(texts(pres))
    clock.at(T(2, day=1))
    p = fresh(app, clock)
    p.start()
    settle(p, clock)
    assert len(texts(pres)) == told  # back at 2 am: you were told it went, so it's said, but in the morning
    awake(p, clock, T(7, 0, day=1))
    assert texts(pres)[-1] == f"Kurooto is back online (offline since {T(21):%a} 21:00, 5 h)."
    # going offline in the night: not said (your call line says it in the morning if it's still away)
    clock.at(T(23, 45, day=1))
    n = len(texts(pres))
    p = fresh(app, clock)
    p.start()
    asyncio.run(p.going_offline("shutting down"))
    assert len(texts(pres)) == n
    assert presence_events(app, "presence_offline")[-1]["held"] is True


def test_off_means_nothing_is_said(pres):
    app, clock = pres.app, pres.clock
    app.settings.set("notify.presence.on", False)
    pres.p.start()
    n = len(texts(pres))
    asyncio.run(pres.p.going_offline("stopped"))
    clock.add(5 * 3600)
    p = fresh(app, clock)
    p.start()
    settle(p, clock)
    assert len(texts(pres)) == n


def test_goodbye_never_holds_up_the_exit(pres, monkeypatch):
    real = TelegramAPI.call

    def slow(self, method, params=None, files=None, timeout=40):
        if method == "sendMessage":
            time.sleep(8)
        return real(self, method, params, files, timeout)

    monkeypatch.setattr(TelegramAPI, "call", slow)
    pres.p.start()
    t0 = time.monotonic()
    asyncio.run(pres.p.going_offline("stopped"))
    assert time.monotonic() - t0 < 3.5
    assert json.loads(pres.p.file.read_text())["stop"]["told"] == []  # it didn't go, so the next start says back


def test_catch_up_is_counted(pres):
    app, clock = pres.app, pres.clock
    pres.p.start()
    clock.add(20)
    pres.p.tick()
    clock.add(2 * 3600)
    pres.p.tick()  # back; then the scheduler catches up and the call line reports
    app.events.emit("reminder_fired", late=True)
    app.events.emit("reminder_fired", late=True)
    app.events.emit("reminder_fired", late=False)
    app.events.emit("call_rang_offline", key="x")
    settle(pres.p, clock)
    assert texts(pres)[-1] == (
        "Kurooto is back online (offline since 12:00, 2 h). 2 reminders went out late; your call line placed 1 call "
        "meanwhile."
    )


def dead_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]  # closed again: connecting is refused, like no network


def test_network_down_then_back_with_the_messages_that_waited(pres):
    app, clock = pres.app, pres.clock
    clock.at(T(14, 2))
    pres.p.start()
    good = app.settings.get("telegram.api_base")
    app.settings.set("telegram.api_base", f"http://127.0.0.1:{dead_port()}")  # Telegram can't be reached
    n = len(texts(pres))
    app.notify("Reminder: stretch")
    clock.add(30)
    app.notify("Your AI answered", title="Result")
    assert pres.p.net_down() and pres.p.net_fail_since == T(14, 2).timestamp()
    clock.add(30)
    app.notify("Reminder: water")  # known down: kept without trying
    assert [e["why"] for e in presence_events(app, "notify_queued")] == ["network"] * 3
    awake(pres.p, clock, T(14, 31))  # still down: it tries Telegram every minute
    assert pres.p.net_down() and pres.p._outbox_len() == 3
    app.settings.set("telegram.api_base", good)  # the network is back: Telegram's next poll gets through
    app.modules["telegram"]._net_seen(None)
    pres.p.tick()
    assert len(texts(pres)) == n  # one minute up first
    settle(pres.p, clock)
    sent = [p for m, p in pres.fake.sent if m == "sendMessage"][n:]
    assert sent[0]["text"] == (
        "Back online: the network was down from 14:02 to 14:31 (29 min). 3 messages that couldn't go out meanwhile "
        "follow."
    )
    assert [p["text"] for p in sent[1:]] == [
        "Delayed, from 14:02\n\nReminder: stretch",
        "Delayed, from 14:02: Result\n\nYour AI answered",
        "Delayed, from 14:03\n\nReminder: water",
    ]
    assert not pres.p.outbox.exists() and not pres.p.net_down()


def test_a_short_network_drop_says_nothing_but_delivers_what_waited(pres):
    app, clock = pres.app, pres.clock
    clock.at(T(15))
    pres.p.start()
    good = app.settings.get("telegram.api_base")
    app.settings.set("telegram.api_base", f"http://127.0.0.1:{dead_port()}")
    n = len(texts(pres))
    app.notify("Reminder: call home")
    clock.add(61)
    pres.p.tick()
    app.settings.set("telegram.api_base", good)
    clock.add(120)
    pres.p.tick()  # back after 3 minutes: under the threshold, no message; what waited goes now
    assert texts(pres)[n:] == ["Delayed, from 15:00\n\nReminder: call home"]


def test_telegram_saying_no_is_not_the_network(pres):
    app = pres.app
    pres.p.start()
    pres.fake.fail["sendMessage"] = (400, "Bad Request: chat not found")
    app.notify("hello")
    assert pres.p.net_fail_since is None and not pres.p.outbox.exists()


def test_network_and_sleep_merge(pres):
    clock = pres.clock
    pres.p.start()
    clock.add(20)
    pres.p.tick()
    pres.p.net_failed("line", ConnectionRefusedError())  # the network went as the lid closed
    clock.at(T(16))
    pres.p.tick()  # woke up
    pres.p.net_ok("line")
    settle(pres.p, clock)
    assert texts(pres)[-1] == "Kurooto is back online (offline since 12:00, 4 h)."


def test_what_the_call_line_said_while_away(pres):
    app, clock = pres.app, pres.clock
    pres.p.start()
    awake(pres.p, clock, T(13))
    since = T(12, 40).timestamp() * 1000
    pres.p.line_report({"since": since, "told": since + 600_000, "channels": ["telegram"]})
    assert presence_events(app, "presence_offline")[-1]["by"] == "line"
    settle(pres.p, clock)
    assert texts(pres)[-1] == "Kurooto is back online (offline since 12:40, 20 min)."
    n = len(texts(pres))
    pres.p.line_report({"since": since, "told": since + 600_000, "channels": ["telegram"]})  # said already
    settle(pres.p, clock)
    assert len(texts(pres)) == n
    pres.p.line_report({"since": since + 9e6, "told": 0, "channels": []})  # the line said nothing
    settle(pres.p, clock)
    assert len(texts(pres)) == n


def test_line_config_and_the_question_about_the_bot_token(pres):
    app, clock = pres.app, pres.clock
    cfg = pres.p.line_config()
    assert cfg["on"] is True and cfg["after_min"] == 10 and cfg["tg"] is None and cfg["channels"] == []
    assert "%%SINCE%%" in cfg["text"] and "%%WHY%%" in cfg["text"]
    night = [w for w in cfg["hush"] if abs(w[0] / 1000 - T(23, 30).timestamp()) <= 60]
    assert night and night[0][1] == int(T(7, day=1).timestamp() * 1000)
    # with a call line, it asks once whether the line may keep the bot's token
    app.settings.set("calls.worker", {"url": "https://kurooto-test.example.workers.dev"})
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "calls"])
    pres.p.tick()
    q = [q for q in app.ask.pending() if q.get("source") == "presence"]
    assert len(q) == 1 and q[0]["kind"] == "approval" and "token" in q[0]["text"]
    clock.add(7 * 3600)
    pres.p.tick()
    assert len([q for q in app.ask.pending() if q.get("source") == "presence"]) == 1  # not twice
    app.ask.answer(q[0]["id"], "Approve", via="test")
    assert app.settings.get("notify.presence.line_telegram") is True
    cfg = pres.p.line_config()
    assert cfg["tg"] == {"token": pres.fake.token, "chat": "7"} and cfg["channels"] == ["telegram"]
    app.settings.set("notify.presence.line", False)
    assert pres.p.line_config()["on"] is False and pres.p.line_config()["tg"] is None


def test_the_call_line_gets_it_with_its_state(pres):
    app = pres.app
    app.settings.set("calls.worker", {"url": "https://kurooto-test.example.workers.dev"})
    st = app.modules["calls"].state_message()
    assert st["presence"]["on"] is True and "hush" in st["presence"]


def test_the_daemon_says_goodbye_when_it_stops(pres, monkeypatch):
    from kurooto.daemon import serve

    app = pres.app
    app.presence = Presence(app)  # the real clock
    app.settings.set("availability.night", {"enabled": False, "from": "23:30", "to": "07:00"})  # whenever it runs

    async def main():
        stop = asyncio.Event()
        task = asyncio.create_task(serve(app, stop, web=False))
        await asyncio.sleep(0.5)
        stop.set()
        await task

    asyncio.run(main())
    assert texts(pres)[-1] == "Kurooto is going offline (shutting down): calls and reminders will wait until it's back."


@pytest.mark.skipif(sys.platform == "win32", reason="elsewhere it does nothing")
def test_end_session_listener_is_windows_only():
    assert endsession.watch(lambda why: None) is None


def test_end_session_messages(monkeypatch):
    """What the hidden window does with Windows' end-of-session messages (the same code on every system)."""
    got = []
    monkeypatch.setattr(endsession, "_on_end", got.append)
    assert endsession.handle(endsession.WM_QUERYENDSESSION, 0, 0) == 1
    assert endsession.handle(endsession.WM_ENDSESSION, 0, 0) == 0 and got == []  # the session goes on after all
    assert endsession.handle(endsession.WM_ENDSESSION, 1, 0) == 0
    assert endsession.handle(endsession.WM_ENDSESSION, 1, endsession.ENDSESSION_LOGOFF) == 0
    assert got == ["shutting down", "signing out"]
    assert endsession.handle(0x0001, 0, 0) is None  # anything else: Windows' default
    monkeypatch.setattr(endsession, "_on_end", lambda why: 1 / 0)
    assert endsession.handle(endsession.WM_ENDSESSION, 1, 0) == 0  # a failing goodbye never stops Windows


def test_end_session_says_goodbye_then_stops(pres, monkeypatch):
    stopped = []
    monkeypatch.setattr(pres.app, "request_stop", lambda: stopped.append(pres.app.stop_reason))
    pres.p.end_session("signing out")  # no running loop here: it still stops, with the reason
    assert stopped == ["signing out"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' end of session")
def test_end_session_on_windows():  # pragma: no cover
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32")  # its own copy: typed here without changing ctypes.windll for anyone else
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    first, got = [], []
    assert endsession.watch(first.append)
    assert endsession.watch(got.append)  # one window per process: a second watch changes what it calls
    hwnd = user32.FindWindowW(endsession.CLASS, None)
    assert hwnd
    assert user32.SendMessageW(hwnd, endsession.WM_QUERYENDSESSION, 0, 0) == 1
    user32.SendMessageW(hwnd, endsession.WM_ENDSESSION, 1, 0)
    user32.SendMessageW(hwnd, endsession.WM_ENDSESSION, 1, endsession.ENDSESSION_LOGOFF)
    assert got == ["shutting down", "signing out"] and first == []
