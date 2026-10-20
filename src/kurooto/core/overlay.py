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

Extension points an add-on feature (a Module in modules/) may define, besides what every feature can:

    classify_intent(text, intents) -> None | "name" | {"intent": name, "slots": {...}, "confidence": 0.0-1.0}
        Picks the plain-English request a message is, before Kurooto's own patterns try (a local model, say).
        `intents` lists what's on: [{"name", "description", "questions"}]. Without "slots", the request's own
        pattern fills them in (and when it can't, the message goes on as usual). None, an unknown name, "other",
        a confidence under 0.6, an error, or no answer within `classify_timeout` seconds (default 2, at most 10)
        all fall through to Kurooto's own patterns. Long messages and several requests in one never reach it, and
        questions only go to requests that answer questions.
    status_lines() -> [str]     extra lines for /status on Telegram
    doctor_checks() -> [(name, ok True|False|None, detail)]   extra lines for `kurooto doctor` (False counts as a
                                problem; None is a note)
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
GUARDED = (
    "commands",
    "callbacks",
    "replies",
    "intents",
    "help",
    "call_tools",
    "agent_tools",
    "call_brief",
    "classify_intent",
    "status_lines",
    "doctor_checks",
)
SAFE = {"callbacks": dict, "replies": dict, "help": list, "call_brief": str, "classify_intent": None}  # if one fails
CLASSIFY_TIMEOUT = 2.0  # seconds an intent classifier gets (an add-on's classify_timeout may change it, up to 10)
MIN_CONFIDENCE = 0.6
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


# ------------------------------------------------------------------------------------------- intent classifiers
def classify(app, text: str, mods: list, asks: bool = False):
    """An add-on's classifier picks the request first (see the docstring at the top): (intent, slots), or None to let
    Kurooto's own patterns try. Any failure, a slow answer or an unsure one is a None."""
    import threading

    pickers = [m for m in mods if callable(getattr(m, "classify_intent", None))]
    if not pickers:
        return None
    intents = {}
    for m in mods:
        for it in m.intents():
            if it.name not in intents and (it.questions or not asks):
                intents[it.name] = it
    if not intents:
        return None
    offered = [{"name": n, "description": it.description, "questions": it.questions} for n, it in intents.items()]
    for m in pickers:
        try:
            wait = min(max(float(getattr(m, "classify_timeout", CLASSIFY_TIMEOUT) or CLASSIFY_TIMEOUT), 0.05), 10.0)
        except (TypeError, ValueError):
            wait = CLASSIFY_TIMEOUT
        box: list = []

        def ask(m=m, box=box):
            try:
                box.append(("ok", m.classify_intent(text, [dict(o) for o in offered])))
            except Exception as e:  # a built-in feature's classifier; add-ons' are guarded already
                box.append(("error", e))

        t = threading.Thread(target=ask, name=f"classify-{m.id}", daemon=True)
        t.start()
        t.join(wait)
        if not box:
            app.events.emit("classifier_slow", module=m.id, seconds=wait)
            continue
        kind, got = box[0]
        if kind == "error":
            _fail(app, f"{m.id}.classify_intent", got)
            continue
        if isinstance(got, str):
            got = {"intent": got}
        if not isinstance(got, dict):
            continue
        it = intents.get(str(got.get("intent") or ""))
        if it is None:
            continue
        conf = got.get("confidence")
        if isinstance(conf, (int, float)) and conf < MIN_CONFIDENCE:
            continue
        slots = got.get("slots")
        if not isinstance(slots, dict):
            try:
                slots = it.match(text)
            except Exception:
                slots = None
        if slots is None:
            continue
        return it, slots
    return None
