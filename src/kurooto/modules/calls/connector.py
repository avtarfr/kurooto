"""This computer's end of your call line: one outbound WebSocket to the Worker (works behind any router or campus
network; nothing listens for the internet here). The Worker passes requests from calls (tools, finished tasks,
transcripts, shared files) down it, and this answers them. Every 5 minutes, and whenever your scheduled calls
change, it pushes what calls need while the computer is off: the call setup, a brief, and the upcoming calls.

What waited on the line while this computer was off (requests from calls, and what you did on your phone: answers,
chat messages, shared files, the "phone outbox") is taken one item at a time, in order, each removed from the line
once it's done here (_drainer), so nothing is lost or done twice.

Reconnects with back-off. A connect that hangs is dropped after 15 s, and a link that goes silent (no "pong" to the
30 s "ping" for 75 s, e.g. after the network changed) is dropped and redialled, so a dead link never leaves the
Worker thinking the computer is on.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from typing import TYPE_CHECKING

from kurooto.core import egress
from kurooto.core.state import jsave

if TYPE_CHECKING:
    from kurooto.modules.calls import Calls

log = logging.getLogger("kurooto.calls")
PING_S, DEAD_S, STATE_S, INDEX_S = 30, 75, 300, 3600


class Connector:
    def __init__(self, calls: Calls):
        self.calls = calls
        self.app = calls.app
        self.ws = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.connected_since = 0.0
        self.last_pong = 0.0
        self.waiting: dict[str, asyncio.Future] = {}
        self.dirty = asyncio.Event()  # the scheduled calls changed: push now
        self.outbox = asyncio.Event()  # something waits on the line for this computer: take it
        self.last_index = 0.0
        self.version = ""

    @property
    def connected(self) -> bool:
        return self.ws is not None and time.time() - self.last_pong < DEAD_S

    def _state(self, connected: bool, error: str = "") -> None:
        jsave(
            self.app.paths.state / "calls" / "link.json",
            {"connected": connected, "since": self.connected_since or None, "at": time.time(), "error": error},
        )

    # ------------------------------------------------------------------------------------------- loop
    async def run(self, stop: asyncio.Event) -> None:
        from websockets.asyncio.client import connect

        self.loop = asyncio.get_running_loop()
        self.dirty, self.outbox = asyncio.Event(), asyncio.Event()  # Events are tied to one loop; a restart has another
        backoff = 2
        while not stop.is_set():
            url, secret = self.calls.worker_url(), self.app.secrets.get("calls.connector_secret")
            if not url or not secret:
                await _sleep(stop, 30)
                continue
            ws_url = url.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/connect"
            try:
                egress.allow(ws_url, "Phone calls", own=True)  # your call line, counted once per connection
                async with connect(
                    ws_url,
                    additional_headers={"x-connector-secret": secret},
                    open_timeout=15,
                    ping_interval=None,  # our own text ping: the Worker answers it without waking up
                    max_size=8 * 1024 * 1024,
                    user_agent_header="kurooto",
                ) as ws:
                    backoff = 2
                    await self._session(ws, stop)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if getattr(self.app, "presence", None) is not None:  # no network? (core/presence.py)
                    self.app.presence.net_failed("line", e)
                self._state(False, f"{type(e).__name__}: {e}"[:200])
                log.info("call line: %s; retrying in %ss", e, backoff)
            finally:
                if self.ws is not None:
                    self.app.events.emit("calls_link", connected=False)
                self.ws = None
                for f in self.waiting.values():
                    if not f.done():
                        f.set_exception(ConnectionError("the call line disconnected"))
                self.waiting.clear()
            await _sleep(stop, backoff)
            backoff = min(60, backoff * 2)

    async def _session(self, ws, stop: asyncio.Event) -> None:
        self.ws, self.connected_since, self.last_pong = ws, time.time(), time.time()
        self._state(True)
        self.app.events.emit("calls_link", connected=True)
        if getattr(self.app, "presence", None) is not None:
            self.app.presence.net_ok("line")
        self.outbox.clear()
        await ws.send(json.dumps({"type": "hello", "pull": True}))  # pull: hand over what waited one at a time
        tasks = [
            asyncio.create_task(self._reader(ws)),
            asyncio.create_task(self._heartbeat(ws)),
            asyncio.create_task(self._pusher()),
            asyncio.create_task(self._drainer()),
            asyncio.create_task(stop.wait()),
        ]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._state(False)
            try:
                await ws.close()
            except Exception:
                pass

    async def _reader(self, ws) -> None:
        async for raw in ws:
            self.last_pong = time.time()
            if raw == "pong":
                continue
            try:
                m = json.loads(raw)
            except ValueError:
                continue
            kind = m.get("type")
            if kind == "request":
                asyncio.create_task(self._answer(ws, m))
            elif kind == "admin-reply":
                f = self.waiting.pop(m.get("id"), None)
                if f and not f.done():
                    f.set_result(m.get("result") or {})
            elif kind == "welcome":
                self.version = m.get("version", "")
                await asyncio.to_thread(self.calls.on_queue, m.get("queue") or [])  # a line from before 0.5.16
                if m.get("outbox"):
                    self.outbox.set()
                if m.get("away") and getattr(self.app, "presence", None) is not None:  # it told you this was offline
                    await asyncio.to_thread(self.app.presence.line_report, m["away"])
                self.dirty.set()
            elif kind == "event":
                await asyncio.to_thread(self.calls.on_event, m)
            elif kind == "outbox":  # something was left on the line while this computer looked away
                self.outbox.set()

    async def _heartbeat(self, ws) -> None:
        while True:
            await asyncio.sleep(PING_S)
            if time.time() - self.last_pong > DEAD_S:
                log.info("call line: no heartbeat; reconnecting")
                return
            await ws.send("ping")

    async def _pusher(self) -> None:
        while True:
            try:
                await self.push_state()
            except Exception as e:
                log.warning("call line: push failed: %s", e)
            try:
                await asyncio.wait_for(self.dirty.wait(), timeout=STATE_S)
                await asyncio.sleep(1)  # let a burst of changes settle into one push
            except TimeoutError:
                pass
            self.dirty.clear()

    async def _drainer(self) -> None:
        """Take what waits on the line, oldest first: ask for the next item, handle it here, and say it's done with
        the next ask (the line then drops it and tells the phone it went through). Never returns (a session ends
        when one of its tasks does)."""
        while True:
            await self.outbox.wait()
            self.outbox.clear()
            done, tools = None, 0
            try:
                while True:
                    res = await self.admin("outbox", timeout=30, **({"done": done} if done else {}))
                    it = res.get("item")
                    if not isinstance(it, dict):
                        break  # nothing left (or a line that doesn't know "outbox": it sent all in its welcome)
                    status, note = await asyncio.to_thread(self.calls.take_queued, it)
                    tools += it.get("kind") == "tool"
                    done = {"seq": it.get("seq"), "status": status, "note": note}
            except Exception as e:
                log.info("call line: taking what waited stopped: %s", e)
                await asyncio.sleep(5)
                self.outbox.set()  # try again (on this link; a new one asks anyway)
            if tools:
                await asyncio.to_thread(self.calls.queued_tools_done, tools)

    async def push_state(self) -> None:
        if self.ws is None:
            return
        msg = await asyncio.to_thread(self.calls.state_message)
        await self.ws.send(json.dumps({"type": "state", **msg}, default=str))
        if time.time() - self.last_index > INDEX_S and self.calls.offline_notes():
            self.last_index = time.time()
            items = await asyncio.to_thread(self.calls.index_items)
            parts = [items[i : i + 1500] for i in range(0, len(items), 1500)] or [[]]
            for i, part in enumerate(parts):
                await self.ws.send(json.dumps({"type": "index", "part": i, "parts": len(parts), "items": part}))

    async def _answer(self, ws, m: dict) -> None:
        try:
            body = base64.b64decode(m["body_b64"]) if m.get("body_b64") else (m.get("body") or "").encode()
            status, out = await asyncio.to_thread(
                self.calls.handle_request, m.get("method", "GET"), m.get("path", "/"), body
            )
        except Exception as e:
            status, out = 500, {"error": f"{type(e).__name__}: {e}"[:300]}
        try:
            await ws.send(
                json.dumps({"type": "reply", "id": m.get("id"), "status": status, "body": json.dumps(out, default=str)})
            )
        except Exception:
            pass  # the link dropped meanwhile; the Worker times the request out

    # ---------------------------------------------------------------------------------------- admin
    async def admin(self, op: str, timeout: float = 20, **kw) -> dict:
        if self.ws is None:
            raise ConnectionError("not connected to your call line")
        rid = uuid.uuid4().hex
        fut = asyncio.get_running_loop().create_future()
        self.waiting[rid] = fut
        await self.ws.send(json.dumps({"type": "admin", "id": rid, "op": op, **kw}))
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self.waiting.pop(rid, None)

    def admin_wait(self, op: str, timeout: float = 25, **kw) -> dict:
        """From a thread that isn't the event loop (the web page, Telegram handlers): wait for the answer."""
        if self.loop is None or not self.loop.is_running() or self.ws is None:
            raise ConnectionError("not connected to your call line")
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            raise RuntimeError("admin_wait on the event loop would wait forever; use admin_later")
        return asyncio.run_coroutine_threadsafe(self.admin(op, **kw), self.loop).result(timeout)

    def admin_later(self, op: str, then=None, **kw) -> bool:
        """Fire and forget (safe from any thread, including the event loop); then(result | None) when it's done."""
        if self.loop is None or self.ws is None:
            return False

        async def go():
            try:
                res = await self.admin(op, **kw)
            except Exception as e:
                res = {"error": str(e)}
            if then:
                await asyncio.to_thread(then, res)

        self.loop.call_soon_threadsafe(lambda: asyncio.ensure_future(go()))
        return True

    def poke(self) -> None:
        """Push the state soon (scheduled calls changed)."""
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self.dirty.set)


async def _sleep(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass
