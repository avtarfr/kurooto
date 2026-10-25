"""0.8.0: a job that takes more than a moment runs on a thread, so Kurooto's loop (heartbeat, replies) isn't held up."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    yield a
    a.close()


def test_a_threaded_job_does_not_block_the_loop(app):
    from kurooto.modules.base import Module

    class M(Module):
        id = "tm"
        title = "T"

    m = M(app)
    seen = {}

    def slow(p=None):
        seen["thread"] = threading.current_thread() is not threading.main_thread()
        time.sleep(0.4)
        return "done"

    m.every("slow", "every 1m", slow, thread=True)
    fn = app.scheduler.actions["tm.slow"]

    async def go():
        beats = []

        async def beat():
            for _ in range(6):
                beats.append(time.monotonic())
                await asyncio.sleep(0.05)

        t = asyncio.create_task(beat())
        out = await fn({})
        await t
        return out, beats

    out, beats = asyncio.run(go())
    assert out == "done" and seen["thread"]
    gaps = [b - a for a, b in zip(beats, beats[1:], strict=False)]
    assert max(gaps) < 0.2  # the loop kept beating while the job slept


def test_the_heavy_nightly_jobs_are_threaded(app):
    import inspect

    from kurooto.modules import integrate, mind

    src = inspect.getsource(mind.Mind.start) + inspect.getsource(integrate.Integrate.start)
    for name in (
        "lab",
        "play",
        "harness",
        "tom_sync",
        "intero",
        "duplicates",
        "note_dupes",
        "finetune",
        "skills_distill",
    ):
        i = src.index(f'"{name}"', src.index("self.every(", max(0, src.index(f'"{name}"') - 40)))
        assert "thread=True" in src[i : i + 260].split("self.every(")[0], name
