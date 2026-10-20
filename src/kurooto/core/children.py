"""Programs Kurooto started end when it stops.

On the way out (after the features' last steps) every program Kurooto started that's still running is asked to stop
(SIGTERM; on Windows the process is ended), and whatever is still there a few seconds later is killed: terminals and
what runs in them, the agent programs of AI requests and the helpers they started (`kurooto mcp`), your GBrain's
server, the call line's helpers, Ollama if Kurooto started it, add-ons' programs. Programs that left a terminal or
an agent program's session behind are found by their session too (macOS and Linux).

Programs opened for you on purpose (a note in your editor, a browser, a terminal window: core/opener.py,
modules/terminal) are yours: keep(pid) leaves them alone.
"""

from __future__ import annotations

import os
import sys
import time

import psutil

GRACE_S = 5.0  # between the polite stop and the kill
_kept: dict[int, float] = {}  # pid -> its start time (a pid alone can be another program's later)
_sessions: dict[int, None] = {}  # sessions Kurooto started (a session's id is its first program's pid)
SESSIONS_MAX = 2000


def session(pid: int) -> None:
    """A program started in a session of its own (an agent program, a terminal): at the end, everything still in
    that session goes too, also what outlived the program itself. (A session's id isn't given to a new program while
    anything is still in it, so this never reaches someone else's programs.)"""
    if sys.platform == "win32":
        return
    _sessions[int(pid)] = None
    while len(_sessions) > SESSIONS_MAX:
        _sessions.pop(next(iter(_sessions)))


def keep(pid: int) -> None:
    """A program started for you that should outlive Kurooto."""
    try:
        _kept[int(pid)] = psutil.Process(int(pid)).create_time()
    except (psutil.Error, ValueError):
        pass


def _kept_tree() -> set[int]:
    out: set[int] = set()
    for pid, born in list(_kept.items()):
        try:
            p = psutil.Process(pid)
            if p.create_time() != born:
                raise psutil.NoSuchProcess(pid)
            out |= {pid, *(c.pid for c in p.children(recursive=True))}
        except psutil.Error:
            _kept.pop(pid, None)
    return out


def _session_mates(leaders: set[int], skip: set[int]) -> list[psutil.Process]:
    """Processes in the sessions Kurooto started (a terminal's, an agent program's) that left its tree."""
    if sys.platform == "win32" or not leaders:
        return []
    out = []
    for p in psutil.process_iter():
        if p.pid in skip:
            continue
        try:
            if os.getsid(p.pid) in leaders:
                out.append(p)
        except OSError:
            continue
    return out


def ours(me: psutil.Process | None = None) -> list[psutil.Process]:
    """Every program Kurooto started that's still running, except the ones it keeps for you."""
    me = me or psutil.Process()
    try:
        tree = me.children(recursive=True)
    except psutil.Error:
        return []
    kept = _kept_tree()
    procs = [p for p in tree if p.pid not in kept]
    leaders = set()
    if sys.platform != "win32":
        for p in procs:
            try:
                if os.getsid(p.pid) == p.pid:
                    leaders.add(p.pid)
            except OSError:
                pass
    seen = {p.pid for p in procs} | kept | {me.pid}
    return procs + _session_mates(leaders | set(_sessions), seen)


def _running(p: psutil.Process) -> bool:
    """Still running (a program that ended but wasn't collected yet doesn't count)."""
    try:
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except psutil.Error:
        return False


def _wait(procs: list[psutil.Process], secs: float) -> list[psutil.Process]:
    end = time.monotonic() + secs
    left = [p for p in procs if _running(p)]
    while left and time.monotonic() < end:
        time.sleep(0.05)
        left = [p for p in left if _running(p)]
    return left


def stop_all(grace: float = GRACE_S, me: psutil.Process | None = None) -> dict:
    """Ask every program Kurooto started to stop, then kill what's left after `grace` seconds. {"stopped": n,
    "killed": n}."""
    procs = ours(me)
    for p in procs:
        try:
            p.terminate()  # SIGTERM; TerminateProcess on Windows
        except psutil.Error:
            pass
    alive = _wait(procs, grace)
    for p in alive:
        try:
            p.kill()
        except psutil.Error:
            pass
    _wait(alive, 3)
    return {"stopped": len(procs) - len(alive), "killed": len(alive)}
