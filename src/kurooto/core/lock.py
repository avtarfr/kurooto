"""Named cross-process locks (Windows, macOS and Linux), kept in state/locks."""

from __future__ import annotations

from pathlib import Path

from filelock import FileLock, Timeout

__all__ = ["Lock", "Timeout"]


def Lock(state_dir: Path, name: str, timeout: float = -1) -> FileLock:
    """with Lock(paths.state, "jobs"): ...   timeout=-1 waits forever; 0 fails at once with Timeout."""
    d = Path(state_dir) / "locks"
    d.mkdir(parents=True, exist_ok=True)
    return FileLock(str(d / f"{name}.lock"), timeout=timeout)
