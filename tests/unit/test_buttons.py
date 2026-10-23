"""Every button Kurooto sends has a handler, so tapping one on an old message after a restart does something (a
feature that's off says so). Buttons are ("Label", "<prefix>:<ref>:<action>"); App.callback routes the prefix."""

import re
from pathlib import Path

import kurooto

SRC = Path(kurooto.__file__).parent
CORE = {"calm", "upd", "ask", "health", "fixme", "job", "inf", "ton"}  # routed by App.callback itself
NOT_BUTTONS = {
    "http",
    "https",
    "ws",
    "wss",
    "a",
    "book",
    "quick",
    "bigger",
    "calls",
    "notes_sync",
    "calendar",
    "google",
    "classroom_notes",
    "mail_digest",
    "research",
}  # fmt: skip  (scheduler keys, log text, XML)


def test_every_button_prefix_has_a_handler(env):
    handlers = set(CORE)
    for m in env.app.modules.values():
        handlers |= set(m.callbacks())
    used: dict[str, set[str]] = {}
    for f in SRC.rglob("*.py"):
        for m in re.finditer(r'\(\s*"[^"\n]{1,40}"\s*,\s*f?"([a-z_]+):', f.read_text(encoding="utf-8")):
            used.setdefault(m[1], set()).add(f.name)
    missing = {p: sorted(fs) for p, fs in used.items() if p not in handlers | NOT_BUTTONS}
    assert not missing, f"buttons with no handler: {missing}"


def test_a_button_from_a_feature_thats_off_says_so(env):
    assert env.app.callback("dl:d123:done") == "that button is from a feature that's off now"
