"""More than one Claude account: each extra one is its own AI ("claude:work"), with its own sign-in, limits and line in
the run receipt.

Claude Code keeps a sign-in per config folder: the CLAUDE_CONFIG_DIR environment variable names the folder, and its
sign-in lives there (`.credentials.json` on Linux and Windows; on macOS a keychain item whose name carries a hash of
the folder). Your usual sign-in (`claude`, no folder) stays exactly as before. Each extra account gets a folder of
Kurooto's own, <data>/claude-accounts/<key>/, which you sign in to once; every run of that account is started with
CLAUDE_CONFIG_DIR pointing there. Kurooto never opens, copies or prints what's in it, never writes into your own
~/.claude, and leaves the folder out of backups unless backups.secrets is on. Removing an account deletes only that
folder (after your yes).

Settings:
    brain.claude_accounts   {"work": {"name": "Work"}}: the extra accounts, by key; the brain id is "claude:<key>",
                            usable wherever a brain id is (brain.main, brain.fallback, integrate.roles...). Changed
                            from the setup page's AI step, Settings → Claude accounts, or `kurooto ai`.
Models: brain.models["claude:work"], else brain.models.claude, else Claude Code's defaults.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "brain",
    {
        "claude_accounts": {},  # extra Claude accounts, each its own AI "claude:<key>": {"work": {"name": "Work"}}
    },
)

PREFIX = "claude:"
FOLDER = "claude-accounts"  # in Kurooto's data folder
KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")
NAME_MAX = 40
ENV = "CLAUDE_CONFIG_DIR"  # Claude Code's own: the config folder, where its sign-in lives
TERMS = (
    "Using a second subscription to get around the first one's usage limits may not be allowed by Anthropic's "
    "terms; check them for your use."
)
_NAMES: dict[str, str] = {}  # key -> name, as last read (labels where no app is at hand: providers.label)


@dataclass
class Account:
    key: str
    name: str

    @property
    def id(self) -> str:
        return PREFIX + self.key

    @property
    def label(self) -> str:
        return f"Claude Code ({self.name})"


def is_id(bid: str | None) -> bool:
    """Is this an extra Claude account's brain id ("claude:work")?"""
    s = str(bid or "")
    return s.startswith(PREFIX) and bool(KEY.match(s[len(PREFIX) :]))


def is_claude(bid: str | None) -> bool:
    """Claude Code, your usual sign-in or an extra account."""
    return bid == "claude" or is_id(bid)


def key_of(bid: str) -> str:
    return str(bid)[len(PREFIX) :] if is_id(bid) else ""


def _clean_name(name: str) -> str:
    return " ".join(str(name or "").replace("(", " ").replace(")", " ").split())[:NAME_MAX]


def accounts(app: App) -> list[Account]:
    """The extra accounts, in the order they were added."""
    raw = app.settings.get("brain.claude_accounts") or {}
    out = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            if not KEY.match(str(k)):
                continue
            name = _clean_name((v or {}).get("name") if isinstance(v, dict) else v) or str(k)
            out.append(Account(str(k), name))
    _NAMES.clear()
    _NAMES.update({a.key: a.name for a in out})
    return out


def ids(app: App) -> list[str]:
    return [a.id for a in accounts(app)]


def get(app: App, bid_or_key: str) -> Account | None:
    """An account by brain id ("claude:work"), key ("work") or name ("Work")."""
    s = str(bid_or_key or "").strip()
    key = key_of(s) if s.startswith(PREFIX) else s
    every = accounts(app)
    return next((a for a in every if a.key == key), None) or next(
        (a for a in every if a.name.lower() == s.lower()), None
    )


def label(bid: str) -> str:
    """ "Claude Code (work)" for an extra account's id, from the names last read."""
    key = key_of(bid)
    return f"Claude Code ({_NAMES.get(key, key)})"


def root(app: App) -> Path:
    return Path(os.path.abspath(app.paths.data / FOLDER))


def folder(app: App, key: str) -> Path:
    """Where this account's sign-in lives: Kurooto's own folder, the same absolute path for the sign-in and every run
    (on macOS the keychain item is named after it)."""
    if not KEY.match(key):
        raise ValueError("not an account key")
    return root(app) / key


def ensure_folder(app: App, key: str) -> Path:
    f = folder(app, key)
    f.mkdir(parents=True, exist_ok=True)
    try:
        f.chmod(0o700)  # only you (a no-op on Windows, where the folder is yours already)
    except OSError:
        pass
    return f


def env(app: App, key: str) -> dict[str, str]:
    """What a run or the sign-in of this account adds to the environment."""
    return {ENV: str(folder(app, key))}


def _new_key(app: App, name: str) -> str:
    have = {a.key for a in accounts(app)}
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24].strip("-")
    if base and base != "claude" and base not in have:
        return base
    n = 2
    while (f"{base[:20]}-{n}" if base else str(n)) in have:
        n += 1
    return f"{base[:20]}-{n}" if base else str(n)


def _save(app: App, every: list[Account]) -> None:
    app.settings.set("brain.claude_accounts", {a.key: {"name": a.name} for a in every})
    accounts(app)


def add(app: App, name: str = "") -> Account:
    """A new extra account (its folder made, not yet signed in). The name is yours to choose ("work"); without one it's
    numbered ("2")."""
    name = _clean_name(name)
    every = accounts(app)
    if name and any(a.name.lower() == name.lower() for a in every):
        raise ValueError(f"there's already a Claude account called {name}")
    key = _new_key(app, name)
    acc = Account(key, name or key)
    ensure_folder(app, key)
    _save(app, [*every, acc])
    app.events.emit("claude_account_added", brain=acc.id)
    return acc


def rename(app: App, bid_or_key: str, name: str) -> Account:
    """A new name to show; the brain id (and so every setting naming it) stays."""
    acc = get(app, bid_or_key)
    if acc is None:
        raise ValueError("no such Claude account")
    name = _clean_name(name)
    if not name:
        raise ValueError("give it a name")
    every = accounts(app)
    if any(a.name.lower() == name.lower() and a.key != acc.key for a in every):
        raise ValueError(f"there's already a Claude account called {name}")
    for a in every:
        if a.key == acc.key:
            a.name = name
    _save(app, every)
    return Account(acc.key, name)


def remove(app: App, bid_or_key: str) -> tuple[Account, list[str]]:
    """Forget an extra account: delete Kurooto's folder for it (its sign-in there; nothing of yours) and take it out
    of the settings that name it. Returns it and the settings it was taken out of. Only after your yes (the caller
    asks)."""
    acc = get(app, bid_or_key)
    if acc is None:
        raise ValueError("no such Claude account")
    f = folder(app, acc.key)
    base = root(app)
    if f.is_symlink():
        f.unlink()
    elif f.is_dir() and f.resolve().parent == base.resolve():  # only ever inside Kurooto's own folder
        shutil.rmtree(f)
    _save(app, [a for a in accounts(app) if a.key != acc.key])
    changed = _forget(app, acc.id)
    worked_file(app, acc.id).unlink(missing_ok=True)
    from kurooto.providers import fallback

    fallback.clear(app, acc.id)
    app.events.emit("claude_account_removed", brain=acc.id)
    return acc, changed


def _forget(app: App, bid: str) -> list[str]:
    """Take a removed account out of the brain settings that name it."""
    s, changed = app.settings, []
    if s.get("brain.main") == bid:
        s.set("brain.main", "")
        changed.append("brain.main")
    fb = s.get("brain.fallback")
    if isinstance(fb, list) and bid in fb:
        s.set("brain.fallback", [x for x in fb if x != bid])
        changed.append("brain.fallback")
    elif fb == bid:
        s.set("brain.fallback", "")
        changed.append("brain.fallback")
    if s.get("brain.classify") == bid:
        s.set("brain.classify", "rules")
        changed.append("brain.classify")
    models = s.get("brain.models") or {}
    if isinstance(models, dict) and bid in models:
        s.set("brain.models", {k: v for k, v in models.items() if k != bid})
        changed.append("brain.models")
    return changed


def worked_file(app: App, bid: str) -> Path:
    """Brain.worked_file's name for it (no ":" in a file name, for Windows)."""
    return app.paths.state / f"{bid.replace(':', '-')}-worked.json"


def rows(app: App) -> list[dict]:
    """Every Claude account for the setup page and Settings: your usual sign-in first, then the extra ones."""
    from kurooto.providers import fallback

    out = []
    for a in accounts(app):
        out.append(
            {
                "id": a.id,
                "key": a.key,
                "name": a.name,
                "label": a.label,
                "folder_here": folder(app, a.key).is_dir(),  # not here: sign in again (a profile from elsewhere)
                "working": worked_file(app, a.id).exists(),  # it has answered here (a request, or Test it)
                "limited_until": fallback.cooling(app, a.id),
            }
        )
    return out
