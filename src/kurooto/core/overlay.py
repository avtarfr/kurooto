"""Your own add-ons (the "overlay"): a folder of yours, for example a private repository you cloned, that Kurooto
lays over itself when you turn on "Your add-ons" and name the folder (overlay.path):

    modules/*.py              extra features: Module subclasses, listed in the dashboard under "Your add-ons" and
                              off until you turn each one on (files starting with _ are helpers, imported by name:
                              `from kurooto_addons import helpers`)
    skills/<name>/SKILL.md    extra skills (your own in your notes still win over them)
    prompts/*.md              extra prompts, listed as add-ons/<name> by /prompts
    settings.json             defaults laid under your own settings (what you set yourself still wins)

modules/ is Python code that runs inside Kurooto with its access to this computer, so nothing here loads until you
turn the feature on, and only from the folder you name (overlay.code turns the Python part off and keeps the rest).
A broken add-on never stops Kurooto: a file that fails to load is skipped, and an add-on that fails while running
is cut off from that one call; both are logged and shown in `kurooto doctor`. Updates never touch this folder.
"""

from __future__ import annotations

import importlib
import logging
import re
import sys
import time
import types
from pathlib import Path

from kurooto.core import config
from kurooto.core.state import jload

log = logging.getLogger("kurooto.overlay")
PACKAGE = "kurooto_addons"
GUARDED = ("commands", "callbacks", "replies", "intents", "help", "call_tools", "agent_tools", "call_brief")
SAFE = {"callbacks": dict, "replies": dict, "help": list, "call_brief": str}  # what a failing one gives
NO_DEFAULTS = ("modules", "overlay", "profile")  # an add-on folder can't turn features on or move itself


def folder(app) -> Path | None:
    """The add-ons folder, when "Your add-ons" is on and the folder is there."""
    if not app.is_on("overlay"):
        return None
    raw = app.settings.get("overlay.path") or ""
    p = Path(raw).expanduser() if raw else None
    return p if p and p.is_absolute() and p.is_dir() else None


def dirs(app, kind: str) -> list[Path]:
    """[<add-ons>/<kind>] when that folder exists ("skills", "prompts"); [] when add-ons are off."""
    f = folder(app)
    d = f / kind if f else None
    return [d] if d and d.is_dir() else []


def inside_kurooto(app, p: Path) -> bool:
    """Is that folder one of Kurooto's own (an update or an uninstall may replace those)?"""
    try:
        r = p.expanduser().resolve()
    except OSError:
        return False
    for own in (app.paths.app, app.paths.config, app.paths.data, app.paths.state, app.paths.cache):
        o = Path(own).resolve()
        if r == o or o in r.parents or r in o.parents:
            return True
    return False


def status(app) -> dict:
    return getattr(app, "overlay", None) or {"path": "", "modules": [], "errors": [], "settings": False}


def _fail(app, where: str, e: BaseException) -> None:
    st = status(app)
    err = f"{type(e).__name__}: {e}"[:300]
    st["errors"] = [x for x in st["errors"] if x["where"] != where][-19:] + [
        {"where": where, "error": err, "at": time.time()}
    ]
    app.overlay = st
    log.warning("add-on %s failed: %s", where, err)
    try:
        app.events.emit("addon_failed", where=where[:80], error=err)
    except Exception:
        pass


def load(app) -> dict:
    """Lay the add-ons over Kurooto: their settings defaults, and (overlay.code) their features. Never raises."""
    config.set_layer({})
    st = {"path": "", "modules": [], "errors": [], "settings": False}
    app.overlay = st
    try:
        f = folder(app)
        if not f:
            return st
        if inside_kurooto(app, f):
            _fail(app, "folder", ValueError("the add-ons folder can't be inside Kurooto's own folders"))
            return st
        st["path"] = str(f)
        sf = f / "settings.json"
        if sf.is_file():
            d = jload(sf, None)
            if isinstance(d, dict):
                config.set_layer({k: v for k, v in d.items() if k not in NO_DEFAULTS and isinstance(v, dict)})
                st["settings"] = True
            else:
                _fail(app, "settings.json", ValueError("isn't a JSON object"))
        if app.settings.get("overlay.code", True) is not False:
            _modules(app, f / "modules")
    except Exception as e:  # nothing in here may stop Kurooto from starting
        _fail(app, "add-ons", e)
    return status(app)


def unload(app) -> None:
    """Turned off: the add-ons stop and leave the feature list (Python can't forget their code until a restart)."""
    config.set_layer({})
    for mid in list(status(app).get("modules") or []):
        m = app.modules.pop(mid, None)
        if m is None:
            continue
        try:
            m.stop()
        except Exception as e:
            _fail(app, f"{mid}.stop", e)
        app.stop_background(m)
    app.overlay = {"path": "", "modules": [], "errors": [], "settings": False}


def _modules(app, d: Path) -> None:
    if not d.is_dir():
        return
    from kurooto.modules.base import Module

    pkg = sys.modules.get(PACKAGE)
    if pkg is None or list(getattr(pkg, "__path__", [])) != [str(d)]:
        pkg = types.ModuleType(PACKAGE)
        pkg.__path__ = [str(d)]
        pkg.__doc__ = "Your own add-ons (core/overlay.py)."
        sys.modules[PACKAGE] = pkg
    for py in sorted(d.glob("*.py")):
        if py.name.startswith(("_", ".")) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", py.stem):
            continue
        name = f"{PACKAGE}.{py.stem}"
        sys.modules.pop(name, None)  # loaded fresh each start
        try:
            mod = importlib.import_module(name)
        except BaseException as e:  # a syntax error, a missing import, even sys.exit(): skipped, never fatal
            if isinstance(e, KeyboardInterrupt):
                raise
            _fail(app, py.name, e)
            continue
        found = [
            c
            for c in vars(mod).values()
            if isinstance(c, type) and issubclass(c, Module) and c is not Module and c.__module__ == name
        ]
        for cls in found:
            mid = str(getattr(cls, "id", "") or "")
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", mid):
                _fail(app, f"{py.name}: {cls.__name__}", ValueError("needs an id: lowercase letters, digits and _"))
                continue
            if mid in app.modules:
                _fail(app, f"{py.name}: {cls.__name__}", ValueError(f"the id {mid!r} is taken by another feature"))
                continue
            try:
                inst = cls(app)
            except Exception as e:
                _fail(app, f"{py.name}: {cls.__name__}", e)
                continue
            guard(app, inst)
            app.modules[mid] = inst
            status(app)["modules"].append(mid)


def guard(app, m) -> None:
    """Wrap an add-on so a failure in it stays in it: what it offers is checked call by call."""
    m.addon = True
    mid = m.id

    def wrap(name, fn, default):
        def safe(*a, **kw):
            try:
                return fn(*a, **kw)
            except Exception as e:
                _fail(app, f"{mid}.{name}", e)
                return default() if callable(default) else default

        return safe

    for name in GUARDED:
        fn = getattr(m, name, None)
        if fn is None:
            continue
        default = SAFE.get(name, list)
        if name == "commands":
            fn = _commands(app, mid, fn)
        elif name == "intents":
            fn = _intents(app, mid, fn)
        elif name in ("replies", "callbacks"):
            fn = _handlers(app, mid, name, fn)
        setattr(m, name, wrap(name, fn, default))
    for name in ("ready", "health"):
        fn = getattr(m, name)

        def checked(fn=fn, name=name):
            try:
                return fn()
            except Exception as e:
                _fail(app, f"{mid}.{name}", e)
                return False, f"your add-on failed: {type(e).__name__}: {e}"[:200]

        setattr(m, name, checked)
    for name in ("start", "stop", "take_files"):
        fn = getattr(m, name, None)
        if fn is not None:
            setattr(m, name, wrap(name, fn, None))


def _said(app, mid: str, where: str, e: Exception) -> str:
    _fail(app, f"{mid}.{where}", e)
    return f"Your add-on {mid} failed: {type(e).__name__}: {e}"[:300]


def _commands(app, mid, fn):
    from kurooto.modules.base import Command

    def commands():
        out = []
        for c in fn() or []:

            def handler(msg, arg, h=c.handler, name=c.name):
                try:
                    return h(msg, arg)
                except Exception as e:
                    return _said(app, mid, f"/{name}", e)

            out.append(Command(c.name, c.help, handler, c.usage))
        return out

    return commands


def _intents(app, mid, fn):
    from kurooto.modules.base import Intent

    def intents():
        out = []
        for it in fn() or []:

            def match(text, f=it.match, name=it.name):
                try:
                    return f(text)
                except Exception as e:
                    _fail(app, f"{mid}.{name}", e)
                    return None

            def run(msg, slots, f=it.run, name=it.name):
                try:
                    return f(msg, slots)
                except Exception as e:
                    return _said(app, mid, name, e)

            out.append(Intent(it.name, it.description, match, run, it.questions))
        return out

    return intents


def _handlers(app, mid, what, fn):
    def handlers():
        out = {}
        for key, h in (fn() or {}).items():

            def safe(*a, h=h, key=key):
                try:
                    return h(*a)
                except Exception as e:
                    return _said(app, mid, f"{what}.{key}", e)

            out[key] = safe
        return out

    return handlers
