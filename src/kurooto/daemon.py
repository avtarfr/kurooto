"""The background process: the scheduler, Telegram, the AI job queue and the local web page, all in one.

    kurooto run         run in the foreground (what the autostart entry starts, via supervise)
    kurooto supervise   run, and restart it if it crashes (with a back-off; tells you on Telegram after 3 crashes)

Only one copy runs at a time (a lock in the state folder).
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from kurooto.app import App
from kurooto.core.lock import Lock, Timeout
from kurooto.core.paths import paths
from kurooto.core.state import jsave

log = logging.getLogger("kurooto")
RESTART = 75  # the launcher starts the (possibly new) current version again


def setup_logging(logs: Path) -> None:
    logs.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(logs / "kurooto.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(h)
    if sys.stderr and sys.stderr.isatty():
        root.addHandler(logging.StreamHandler())
    root.setLevel(logging.INFO)


async def serve(app: App, stop: asyncio.Event, web: bool = True) -> None:
    app._stop, app._loop = stop, asyncio.get_running_loop()
    app.start()
    tasks = [
        asyncio.create_task(app.scheduler.run_forever(stop), name="scheduler"),
        asyncio.create_task(app.jobs.worker(stop), name="jobs"),
        asyncio.create_task(app.power.watch(stop), name="power"),
    ]
    server = None
    if web:
        from kurooto.web.server import start as start_web

        server = start_web(app)
        log.info("dashboard on %s", server.url)
    app.events.emit("started", pid=os.getpid())
    await stop.wait()
    tasks += list(app._background.values())
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    if server:
        server.stop()
    app.events.emit("stopped")


def run(web: bool = True) -> int:
    p = paths().ensure()
    setup_logging(p.logs)
    lock = Lock(p.state, "daemon", timeout=0)
    try:
        lock.acquire()
    except Timeout:
        print("Kurooto is already running.", file=sys.stderr)
        return 3
    try:
        jsave(p.state / "daemon.json", {"pid": os.getpid(), "started": time.time()})
        app = App(p)
        app.power.off_file.unlink(missing_ok=True)  # started on purpose: it's on

        async def main():
            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, stop.set)
                except (NotImplementedError, RuntimeError, ValueError):  # Windows: Ctrl+C raises KeyboardInterrupt
                    pass
            try:
                await serve(app, stop, web)
            except asyncio.CancelledError:
                pass

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
        restart = app.restart_requested
        app.close()
        return RESTART if restart else 0
    finally:
        lock.release()


def supervise() -> int:
    """Keep `kurooto run` going: restart it after a crash, waiting longer each time it crashes quickly."""
    p = paths().ensure()
    setup_logging(p.logs)
    jsave(p.state / "supervisor.json", {"pid": os.getpid(), "started": time.time()})
    crashes, backoff = 0, 5
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    while True:
        started = time.monotonic()
        child = subprocess.run([sys.executable, "-m", "kurooto", "run"], creationflags=flags)
        if child.returncode in (0, 3):  # stopped on purpose, or another copy is already running
            return child.returncode
        if child.returncode == RESTART:
            continue
        lived = time.monotonic() - started
        crashes = crashes + 1 if lived < 300 else 1
        backoff = min(backoff * 2, 300) if lived < 300 else 5
        log.error("kurooto run exited with %s after %.0fs; restarting in %ss", child.returncode, lived, backoff)
        if crashes == 3:
            try:
                app = App(p)
                app.notify(
                    f"{app.name} crashed three times in a row and keeps restarting. Logs: {p.logs}",
                    kind="info",
                    urgent=True,
                )
                app.close()
            except Exception:
                pass
        time.sleep(backoff)
