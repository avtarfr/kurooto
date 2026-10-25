"""The suite: which instances exist, which are hidden, and when they rotate.

Instances are made from the task templates (tasks/library.py) with a seeded generator. The practice pool's seed is
public; the
hidden pool's seed is derived from a secret kept in `<state>/mind/harness/hidden/secret` (0600), so a policy can't
regenerate
what it's tested on. Every `rotate_days` (30) a new epoch begins and both pools are made again; the old hidden
instances are
deleted. 70% of each task type's instances are hidden, 30% practice (7 and 3 of 10).

The hidden folder holds the instances' keys: only code in this package reads it (`test_harness_unreadable`: no tool,
job,
skill or proposal can reach it, it isn't under the notes, it's 0600; hardened mode: owned by the scorekeeper's user).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.mind.harness.tasks import TASK_TYPES

if TYPE_CHECKING:
    from kurooto.app import App

PER_TYPE = 10
HIDDEN_SHARE = 0.7
EPOCH0 = 1_767_225_600  # 1 Jan 2026 UTC
ROTATE_DAYS = 30


def root(app: App) -> Path:
    return app.paths.state / "mind" / "harness"


def hidden_dir(app: App) -> Path:
    return root(app) / "hidden"


def practice_dir(app: App) -> Path:
    return root(app) / "practice"


def epoch(app: App | None = None, now: float | None = None) -> int:
    days = ROTATE_DAYS
    if app is not None:
        v = app.settings.get("mind.harness.rotate_days")
        days = int(v) if isinstance(v, (int, float)) and v >= 1 else ROTATE_DAYS
    return int(((now if now is not None else time.time()) - EPOCH0) // (days * 86400))


def _private(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def secret(app: App) -> bytes:
    f = hidden_dir(app) / "secret"
    if not f.exists():
        hidden_dir(app).mkdir(parents=True, exist_ok=True)
        _private(hidden_dir(app), 0o700)
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(os.urandom(32))
    return f.read_bytes()


def _rng(seed: bytes) -> random.Random:
    return random.Random(int.from_bytes(hashlib.sha256(seed).digest()[:8], "big"))  # noqa: S311 (instances, not secrets)


def build(app: App, ep: int | None = None) -> dict:
    """Make this epoch's instances ({id, type, inputs, key, split}), write them (hidden 0600, practice plain), and drop
    the
    hidden ones of earlier epochs. Returns {"hidden": n, "practice": n, "epoch": ep}."""
    ep = epoch(app) if ep is None else ep
    key = secret(app)
    hidden, practice = [], []
    n_hidden = round(PER_TYPE * HIDDEN_SHARE)
    for tid, t in TASK_TYPES.items():
        for i in range(PER_TYPE):
            split = "hidden" if i < n_hidden else "practice"
            seed = (
                hmac.new(key, f"{tid}:{ep}:{i}".encode(), "sha256").digest()
                if split == "hidden"
                else f"practice:{tid}:{ep}:{i}".encode()
            )
            inst = t.make(_rng(seed))
            rec = {
                "id": f"{tid}-{ep}-{i}",
                "type": tid,
                "family": t.family,
                "inputs": inst["inputs"],
                "key": inst["key"],
                "split": split,
            }
            (hidden if split == "hidden" else practice).append(rec)
    hidden_dir(app).mkdir(parents=True, exist_ok=True)
    practice_dir(app).mkdir(parents=True, exist_ok=True)
    _private(hidden_dir(app), 0o700)
    for old in hidden_dir(app).glob("epoch-*.json"):
        old.unlink(missing_ok=True)
    for old in practice_dir(app).glob("epoch-*.json"):
        old.unlink(missing_ok=True)
    hf = hidden_dir(app) / f"epoch-{ep}.json"
    fd = os.open(hf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(hidden, fh)
    # the practice pool shows the inputs and the keys: it's for practising, and the actor may read it
    (practice_dir(app) / f"epoch-{ep}.json").write_text(json.dumps(practice), encoding="utf-8")
    return {"hidden": len(hidden), "practice": len(practice), "epoch": ep}


def load(app: App, split: str, ep: int | None = None) -> list[dict]:
    """The instances of one split in this epoch, made if they don't exist yet (or the epoch turned)."""
    ep = epoch(app) if ep is None else ep
    d = hidden_dir(app) if split == "hidden" else practice_dir(app)
    f = d / f"epoch-{ep}.json"
    if not f.exists():
        build(app, ep)
    return json.loads(f.read_text(encoding="utf-8"))


def inputs_only(inst: dict) -> dict:
    """What a policy is shown of an instance: its id, type and inputs, never the key."""
    return {"id": inst["id"], "type": inst["type"], "inputs": inst["inputs"]}
