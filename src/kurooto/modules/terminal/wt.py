"""Kurooto Terminal in Windows Terminal: a "fragment" (a small settings file that Windows Terminal reads from its
Fragments folder in your user profile; no admin) with Kurooto's profiles and colour scheme, and the `wt` command line
that opens the tabs. Windows Terminal's own settings.json is only changed for "default terminal" (defaults.py).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from pathlib import Path

from kurooto.modules.terminal.look import wt_scheme
from kurooto.modules.terminal.plan import Plan, Tab, program_name

APP = "Kurooto"  # the fragment's folder; with each profile's name it makes the profile's GUID
SCHEME = "Kurooto"
NAMESPACE = uuid.UUID("f65ddb7e-706b-4499-8a50-40313caf510a")  # Windows Terminal's, for fragments' profiles
COLUMN = 0.68  # the first tab's share beside `kurooto top`
STORE = "Microsoft.WindowsTerminal_8wekyb3d8bbwe"
PREVIEW = "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe"


def local_appdata(home: Path | None = None, env: dict | None = None) -> Path:
    env = os.environ if env is None else env
    return Path(env.get("LOCALAPPDATA") or (home or Path.home()) / "AppData" / "Local")


def fragment_dir(home: Path | None = None, env: dict | None = None) -> Path:
    return local_appdata(home, env) / "Microsoft" / "Windows Terminal" / "Fragments" / APP


def guid(profile: str, app: str = APP) -> str:
    """The GUID Windows Terminal gives a fragment's profile: UUIDv5 of the app's name, then of the profile's name,
    both as UTF-16LE (Microsoft's documented scheme)."""
    app_ns = uuid.uuid5(NAMESPACE, app.encode("utf-16-le"))
    return "{" + str(uuid.uuid5(app_ns, profile.encode("utf-16-le"))) + "}"


def profile_name(t: Tab) -> str:
    """The main profile, "Kurooto", is your shell in Kurooto's colours (the one "default terminal" picks)."""
    return {"shell": APP, "chat": f"{APP} chat", "top": f"{APP} top", "logs": f"{APP} logs"}.get(
        t.key, f"{APP} {t.title}"
    )


def _profiles(plan: Plan) -> list[Tab]:
    """Every tab's profile, the shell's always (it's the main one), in the order the tabs open."""
    tabs = ([plan.top] if plan.top else []) + plan.tabs
    if not any(t.key == "shell" for t in tabs):
        tabs.append(Tab("shell", program_name(plan.shell[0]), plan.shell, str(Path.home())))
    out, seen = [], set()
    for t in tabs:
        if profile_name(t) not in seen:
            seen.add(profile_name(t))
            out.append(t)
    return out


def fragment(plan: Plan, colours: dict[str, str]) -> dict:
    profiles = []
    for t in _profiles(plan):
        name = profile_name(t)
        p = {
            "guid": guid(name),
            "name": name,
            "commandline": subprocess.list2cmdline(t.argv),
            "startingDirectory": t.cwd,
            "colorScheme": SCHEME,
            "font": {"size": plan.font_size},
            "cursorShape": "bar",
            "hidden": False,
        }
        if t.key != "shell":  # Kurooto's own tabs keep their names; your shell's tab follows what runs in it
            p.update(tabTitle=t.title, suppressApplicationTitle=True)
        profiles.append(p)
    return {"profiles": profiles, "schemes": [wt_scheme(colours, SCHEME)]}


def write_fragment(plan: Plan, colours: dict[str, str], home: Path | None = None, env: dict | None = None) -> Path:
    d = fragment_dir(home, env)
    d.mkdir(parents=True, exist_ok=True)
    f = d / "kurooto.json"
    text = json.dumps(fragment(plan, colours), indent=2, ensure_ascii=False) + "\n"
    if not f.is_file() or f.read_text(encoding="utf-8", errors="replace") != text:
        tmp = f.with_name(f"{f.name}.tmp{os.getpid()}")
        tmp.write_text(text, encoding="utf-8")  # UTF-8 without a byte-order mark, as Windows Terminal wants
        os.replace(tmp, f)
    return f


def remove_fragment(home: Path | None = None, env: dict | None = None) -> bool:
    import shutil

    d = fragment_dir(home, env)
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False


def has_fragment(home: Path | None = None, env: dict | None = None) -> bool:
    return (fragment_dir(home, env) / "kurooto.json").is_file()


def _tab(t: Tab, profiles: bool) -> list[str]:
    if profiles:
        return ["-p", profile_name(t)]
    return ["--title", t.title, "--suppressApplicationTitle", "-d", t.cwd, *t.argv]


def args(plan: Plan, profiles: bool = True) -> list[str]:
    """`wt` arguments for the whole window. profiles=False: no fragment (Kurooto Terminal is off), so each tab
    says what to run itself and has Windows Terminal's usual colours."""
    out = ["-w", "new"]
    for i, t in enumerate(plan.tabs):
        if i:
            out.append(";")
        if i == 0 and plan.top is not None:
            out += ["new-tab", *_tab(plan.top, profiles), ";", "split-pane", "-V", "-s", f"{COLUMN:g}"]
            out += _tab(t, profiles)
        else:
            out += ["new-tab", *_tab(t, profiles)]
    return out + [";", "focus-tab", "-t", "0"]


def one(argv: list[str], title: str = "", cwd: str = "", profiles: bool = True) -> list[str]:
    """`wt` arguments for one tab in a new window running a command (or the Kurooto profile's shell)."""
    out = ["-w", "new", "new-tab"]
    if profiles:
        out += ["-p", APP]
    if title:
        out += ["--title", title]
    if cwd:
        out += ["-d", cwd]
    return out + list(argv)


# ------------------------------------------------------------------------------- Windows Terminal's settings
def settings_files(home: Path | None = None, env: dict | None = None) -> list[Path]:
    """Where Windows Terminal keeps settings.json: the Store version, Preview, then an unpackaged install."""
    local = local_appdata(home, env)
    return [
        local / "Packages" / STORE / "LocalState" / "settings.json",
        local / "Packages" / PREVIEW / "LocalState" / "settings.json",
        local / "Microsoft" / "Windows Terminal" / "settings.json",
    ]


DEFAULT = re.compile(r'("defaultProfile"\s*:\s*")([^"]*)(")')


def _live(text: str):
    """The defaultProfile entry that isn't commented out (settings.json may have // comments)."""
    for m in DEFAULT.finditer(text):
        start = text.rfind("\n", 0, m.start()) + 1
        if "//" not in text[start : m.start()]:
            return m
    return None


def current_default(text: str) -> str | None:
    m = _live(text)
    return m.group(2) if m else None


def _object_start(text: str) -> int:
    """Where the settings object's { is: the first one that isn't in a comment."""
    i, n = 0, len(text)
    while i < n:
        if text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                return -1
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = j + 2 if j >= 0 else n
        elif text[i] == "{":
            return i
        else:
            i += 1
    return -1


def with_default(text: str, value: str) -> tuple[str, str | None]:
    """settings.json with defaultProfile set to value, and the value it had (None: it had none). Only that value
    changes; comments, order and spacing stay as they were."""
    m = _live(text)
    if m:
        return text[: m.start(2)] + value + text[m.end(2) :], m.group(2)
    i = _object_start(text)
    if i < 0:
        raise ValueError("Windows Terminal's settings file isn't a settings object")
    empty = text[i + 1 :].lstrip().startswith("}")
    nl = "\r\n" if "\r\n" in text else "\n"  # the file's own line endings
    return text[: i + 1] + f'{nl}    "defaultProfile": "{value}"' + ("" if empty else ",") + text[i + 1 :], None


def without_default(text: str, ours: str, previous: str | None) -> str:
    """Undo with_default: the old value back (or the entry gone if there was none), only while it's still ours."""
    m = _live(text)
    if not m or m.group(2) != ours:
        return text
    if previous is not None:
        return text[: m.start(2)] + previous + text[m.end(2) :]
    line = re.compile(r'(?:\r?\n)?[ \t]*"defaultProfile"\s*:\s*"' + re.escape(ours) + r'"[ \t]*,?')
    return line.sub("", text, count=1)
