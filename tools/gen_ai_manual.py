#!/usr/bin/env python3
"""Keep src/kurooto/data/ai-manual.md (the manual Kurooto's own AI reads: core/selfdoc.py) true to the code.

The part above the marker line is written by hand: how Kurooto works, where things are, what the AI may and may not do.
Everything below it is written here from the code itself: every feature (id, title, what it does, its commands),
Kurooto's own commands, the actions that need the user's tap (core/tap.py) and the settings' sections, with a
fingerprint of every setting's name, so a feature, command, tap rule or setting added without regenerating fails
`--check` (tests/unit/test_ai_manual.py, and tools/release.py's build), and every release ships a current manual.

    python tools/gen_ai_manual.py           write it
    python tools/gen_ai_manual.py --check   exit 1 when it's out of date
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "kurooto" / "data" / "ai-manual.md"
MARKER = "<!-- Everything below is written by tools/gen_ai_manual.py from the code. Don't edit it by hand. -->"
sys.path.insert(0, str(ROOT / "src"))


def _settings() -> list[tuple[str, object, str]]:
    spec = importlib.util.spec_from_file_location("gen_settings_guide", ROOT / "tools" / "gen_settings_guide.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.collect()


def _first(text: str, n: int = 150) -> str:
    s = re.split(r"(?<=[.!?])\s", " ".join(str(text or "").split()), maxsplit=1)[0]
    return (s if len(s) <= n else s[: n - 1] + "…").replace("|", "\\|")


def generated() -> str:
    """The part below the marker."""
    home = tempfile.mkdtemp(prefix="kurooto-manual-")
    old = os.environ.get("KUROOTO_HOME")
    os.environ["KUROOTO_HOME"] = home  # a scratch Kurooto: nothing of anyone's own is read
    try:
        from kurooto.app import App
        from kurooto.core import commands, tap

        app = App()
        try:
            mods = list(app.modules.values())
            rows = [(m.id, m.title, _first(m.description), [c.name for c in m.commands()]) for m in mods]
        finally:
            app.close()
    finally:
        if old is None:
            os.environ.pop("KUROOTO_HOME", None)
        else:
            os.environ["KUROOTO_HOME"] = old
    out = [
        MARKER,
        "",
        "## Features",
        "",
        "Every feature is off until the user turns it on (Features in the dashboard). `kurooto_self` says which are on "
        "and whether each works.",
        "",
        "| Id | Feature | What it does | Commands |",
        "|---|---|---|---|",
    ]
    for mid, title, desc, cmds in rows:
        out.append(f"| `{mid}` | {title} | {desc} | {' '.join(f'/{c}' for c in cmds) or '-'} |")
    out += ["", "## Kurooto's own commands", "", "| Command | What it does |", "|---|---|"]
    for names, what in (*commands.CORE, commands.SYNC):
        out.append(f"| {', '.join(f'/{n}' for n in names)} | {' '.join(what.split()).replace('|', '\\|')} |")
    out += [
        "",
        "## Never without the user's tap",
        "",
        "You never do these by yourself. A tool that would is turned into an Approve / Deny question for the user, "
        "and you say it waits for their tap.",
        "",
        "| Action | What it is | How it's approved |",
        "|---|---|---|",
    ]
    for key, g in tap.GUARDED.items():
        out.append(f"| `{key}` | {g.what} | {', '.join(g.ways)} |")
    if tap.BY_ITSELF:
        out += ["", "Done without a tap (sure, only the user's own data, said in one line with Undo):"]
        out += [f"- `{k}`: {v}" for k, v in tap.BY_ITSELF.items()]
    settings = _settings()
    sections: dict[str, int] = {}
    for name, _, _ in settings:
        top = name.split(".")[0]
        sections[top] = sections.get(top, 0) + 1
    finger = hashlib.sha256("\n".join(n for n, _, _ in settings).encode()).hexdigest()[:16]
    out += [
        "",
        "## Settings",
        "",
        f"{len(settings)} settings in {len(sections)} sections; each one, its default and what it does: "
        "docs/SETTINGS_GUIDE.md (on the site: SETTINGS_GUIDE). The ones that differ from their defaults are in "
        "reserve/settings.md. Sections:",
        "",
        ", ".join(f"`{k}` ({n})" for k, n in sections.items()) + ".",
        "",
        f"<!-- settings fingerprint: {finger} -->",
        "",
    ]
    return "\n".join(out)


def render(current: str) -> str:
    if MARKER not in current:
        raise SystemExit(f"{OUT}: the marker line is missing")
    return current.split(MARKER)[0] + generated()


def main() -> int:
    current = OUT.read_text(encoding="utf-8")
    text = render(current)
    if "--check" in sys.argv:
        if current != text:
            print("src/kurooto/data/ai-manual.md is out of date: python tools/gen_ai_manual.py", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
