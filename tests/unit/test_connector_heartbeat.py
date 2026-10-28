"""The call line's heartbeat (modules/calls/connector.py, N3 in 0.9.0): a line that looks silent gets one more ping and
a few seconds before it's called dead, so a busy or suspended computer doesn't drop a working line; a line that really
went quiet is still dropped."""

from __future__ import annotations

import asyncio
import logging
import time
from types import SimpleNamespace

from kurooto.modules.calls import connector as cmod


class FakeWs:
    """Answers a ping with a pong (through the connector, as _reader does) unless it's dead."""

    def __init__(self, conn, alive=True):
        self.conn, self.alive, self.sent = conn, alive, []

    async def send(self, raw):
        self.sent.append(raw)
        if self.alive:
            asyncio.get_running_loop().call_later(0.05, setattr, self.conn, "last_pong", time.time())


def make(monkeypatch, ping=0.05, dead=0.2, confirm=0.3):
    monkeypatch.setattr(cmod, "PING_S", ping)
    monkeypatch.setattr(cmod, "DEAD_S", dead)
    monkeypatch.setattr(cmod, "CONFIRM_S", confirm)
    return cmod.Connector(SimpleNamespace(app=SimpleNamespace()))


def test_a_stale_line_that_answers_the_extra_ping_stays(monkeypatch):
    c = make(monkeypatch)
    ws = FakeWs(c)
    c.last_pong = time.time() - 10  # looks long dead: the loop was held up, say

    async def run():
        t = asyncio.create_task(c._heartbeat(ws))
        await asyncio.sleep(0.6)
        assert not t.done()  # still connected
        t.cancel()

    asyncio.run(run())
    assert ws.sent.count("ping") >= 2


def test_a_line_that_stays_silent_is_dropped(monkeypatch):
    c = make(monkeypatch)
    ws = FakeWs(c, alive=False)
    c.last_pong = time.time() - 10

    async def run():
        await asyncio.wait_for(c._heartbeat(ws), timeout=2)  # returns: reconnect

    asyncio.run(run())
    assert ws.sent == ["ping"]  # the one confirming ping, then dead


def test_a_frame_already_waiting_counts(monkeypatch):
    c = make(monkeypatch)
    ws = FakeWs(c, alive=False)
    c.last_pong = time.time() - 10

    async def run():
        asyncio.get_running_loop().call_soon(setattr, c, "last_pong", time.time())  # read on the yield
        assert await c._still_there(ws)

    asyncio.run(run())
    assert ws.sent == []  # no extra ping needed


def test_a_late_wakeup_is_logged(monkeypatch, caplog):
    c = make(monkeypatch, ping=0.05)
    monkeypatch.setattr(cmod, "LAG_S", 0.0)
    ws = FakeWs(c)
    c.last_pong = time.time()

    async def run():
        t = asyncio.create_task(c._heartbeat(ws))
        await asyncio.sleep(0.01)
        time.sleep(0.1)  # the event loop is held up
        await asyncio.sleep(0.1)
        t.cancel()

    with caplog.at_level(logging.INFO, logger="kurooto.calls"):
        asyncio.run(run())
    assert any("woke" in r.message and "late" in r.message for r in caplog.records)
