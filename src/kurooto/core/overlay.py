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

Add-ons by link (core/addons.py: `kurooto addons add <git url>`) load here too, each from its own folder under
Kurooto's data, whether or not "Your add-ons" is on: as the package kurooto_linked.<name> (so their helpers are
imported relatively: `from . import _helpers`), only when their files are exactly the ones you agreed to, and held to
their card (load_linked): only the features, commands, AI tools and jobs it names, only the hosts and programs it names
(core/fence.py), and an intent classifier only with "classify": true. Their skills/ and prompts/ count as yours, but
Kurooto's AI programs never write into them (places.write_roots).

Extension points an add-on feature (a Module in modules/) may define, besides what every feature can:

    classify_intent(text, intents) -> None | "name" | {"intent": name, "slots": {...}, "confidence": 0.0-1.0}
        Picks the plain-English request a message is, before Kurooto's own patterns try (a local model, say).
        `intents` lists what's on: [{"name", "description", "questions"}]. Without "slots", the request's own
        pattern fills them in (and when it can't, the message goes on as usual). None, an unknown name, "other",
        a confidence under 0.6, an error, or no answer within `classify_timeout` seconds (default 2, at most 10)
        all fall through to Kurooto's own patterns. Long messages and several requests in one never reach it, and
        questions only go to requests that answer questions.
    status_lines() -> [str]     extra lines for /status on Telegram
    dreaming_lines() -> [str]   loose ends for Dreaming's morning message (at most 2; only when there's something
                                worth a look, e.g. Night performance's "couldn't switch")
    doctor_checks() -> [(name, ok True|False|None, detail)]   extra lines for `kurooto doctor` (False counts as a
                                problem; None is a note)
    health_check() -> core.health.Check | None   its one check for the daily pass, the dashboard and doctor: how
                                often it should work (an event it emits) and/or a read-only probe
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
    "dreaming_lines",
    "doctor_checks",
    "health_check",
)
SAFE = {  # what a failing one gives instead
    "callbacks": dict,
    "replies": dict,
    "help": list,
    "call_brief": str,
    "classify_intent": None,
    "health_check": None,
}
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


def dirs(app, kind: str, linked: bool = True) -> list[Path]:
    """[<add-ons>/<kind>] when that folder exists ("skills", "prompts"); [] when add-ons are off. linked: also the
    add-ons by link that loaded (core/addons.py)."""
    f = folder(app)
    d = f / kind if f else None
    out = [d] if d and d.is_dir() else []
    if linked:
        for row in (status(app).get("linked") or {}).values():
            x = Path(row.get("folder") or "") / kind
            if not row.get("problem") and row.get("folder") and x.is_dir():
                out.append(x)
    return out


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


def _empty() -> dict:
    return {"path": "", "modules": [], "errors": [], "settings": False, "linked": {}, "linked_modules": []}


def status(app) -> dict:
    """{path, modules, errors, settings} of your add-ons folder, and {linked: {name: {folder, modules, problem}},
    linked_modules} of the add-ons by link."""
    st = getattr(app, "overlay", None) or _empty()
    for k, v in _empty().items():
        st.setdefault(k, v)
    return st


def all_modules(app) -> list[str]:
    """Every add-on feature's id: your folder's, then the add-ons by link's."""
    st = status(app)
    return [*st["modules"], *st["linked_modules"]]


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
    """Lay the add-ons over Kurooto: your folder's settings defaults and (overlay.code) features, then the add-ons by
    link (addons.on). Never raises."""
    prev = getattr(app, "overlay", None) or {}
    config.set_layer({})
    st = _empty()
    if prev.get("linked_loaded"):  # "Your add-ons" turned on again: the add-ons by link are loaded already
        st.update(linked=prev["linked"], linked_modules=prev["linked_modules"], linked_loaded=True)
    app.overlay = st
    try:
        f = folder(app)
        if f and inside_kurooto(app, f):
            _fail(app, "folder", ValueError("the add-ons folder can't be inside Kurooto's own folders"))
        elif f:
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
    if not st.get("linked_loaded"):
        load_linked(app)
    return status(app)


def _drop(app, mids: list[str]) -> None:
    for mid in mids:
        m = app.modules.pop(mid, None)
        if m is None:
            continue
        try:
            m.stop()
        except Exception as e:
            _fail(app, f"{mid}.stop", e)
        app.stop_background(m)


def unload(app) -> None:
    """Turned off: your folder's add-ons stop and leave the feature list (Python can't forget their code until a
    restart). The add-ons by link stay (they have their own switch, addons.on)."""
    config.set_layer({})
    st = status(app)
    _drop(app, list(st.get("modules") or []))
    app.overlay = {**_empty(), **{k: st[k] for k in ("linked", "linked_modules", "linked_loaded") if k in st}}


def load_linked(app) -> None:
    """The add-ons by link (core/addons.py): each whose files are the ones you agreed to, held to its card."""
    from kurooto.core import addons, fence

    st = status(app)
    st["linked"], st["linked_modules"], st["linked_loaded"] = {}, [], True
    if app.settings.get("addons.on", True) is False:
        return
    try:
        rows = addons.loadable(app.paths)
    except Exception as e:
        _fail(app, "add-ons by link", e)
        return
    for rec, f, problem in rows:
        name, man = rec["name"], rec.get("manifest") or {}
        st["linked"][name] = {"folder": str(f), "modules": [], "problem": problem, "commit": rec.get("commit", "")}
        if problem:
            _fail(app, f"add-on {name}", ValueError(problem))
            continue
        pkg = addons.package(name)
        fence.add(
            pkg,
            name,
            man.get("hosts") or (),
            [p["name"] for p in man.get("programs") or []],
            [p["name"] for p in man.get("programs") or [] if p.get("online")],
        )
        got = _modules(app, f / "modules", pkg, man)
        st["linked"][name]["modules"] = got
        st["linked_modules"] += got


def reload_linked(app) -> dict:
    """After an add, update, remove or undo: the add-ons by link stop and load again; the features of theirs you had
    on start again. Returns the status."""
    from kurooto.core import fence

    st = status(app)
    _drop(app, list(st.get("linked_modules") or []))
    for name in list(st.get("linked") or {}):
        from kurooto.core import addons

        fence.remove(addons.package(name))
    load_linked(app)
    for mid in status(app)["linked_modules"]:
        m = app.modules.get(mid)
        if m is not None and app.is_on(mid):
            m.start()
            app.start_background(m)
    return status(app)


def _package(name: str, d: Path) -> None:
    """The package an add-on's files import as (made fresh, with every module of it forgotten, at each load)."""
    for k in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
        sys.modules.pop(k, None)
    parent = name.rpartition(".")[0]
    if parent and parent not in sys.modules:
        root = types.ModuleType(parent)
        root.__path__ = []
        root.__doc__ = "Add-ons by link (core/addons.py)."
        sys.modules[parent] = root
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(d)]
    pkg.__doc__ = "An add-on (core/overlay.py)."
    sys.modules[name] = pkg


def _modules(app, d: Path, package: str = PACKAGE, manifest: dict | None = None) -> list[str]:
    """Load the features in d (an add-ons folder's modules/). manifest: an add-on by link's, which they're held to."""
    if not d.is_dir():
        return []
    from kurooto.modules.base import Module

    linked = manifest is not None
    if linked:
        _package(package, d)
    else:
        pkg = sys.modules.get(PACKAGE)
        if pkg is None or list(getattr(pkg, "__path__", [])) != [str(d)]:
            pkg = types.ModuleType(PACKAGE)
            pkg.__path__ = [str(d)]
            pkg.__doc__ = "Your own add-ons (core/overlay.py)."
            sys.modules[PACKAGE] = pkg
    where = f"{manifest['name']}/" if linked else ""
    loaded = []
    for py in sorted(d.glob("*.py")):
        if py.name.startswith(("_", ".")) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", py.stem):
            continue
        name = f"{package}.{py.stem}"
        sys.modules.pop(name, None)  # loaded fresh each start
        try:
            mod = importlib.import_module(name)
        except BaseException as e:  # a syntax error, a missing import, even sys.exit(): skipped, never fatal
            if isinstance(e, KeyboardInterrupt):
                raise
            _fail(app, where + py.name, e)
            continue
        found = [
            c
            for c in vars(mod).values()
            if isinstance(c, type) and issubclass(c, Module) and c is not Module and c.__module__ == name
        ]
        for cls in found:
            mid = str(getattr(cls, "id", "") or "")
            here = f"{where}{py.name}: {cls.__name__}"
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", mid):
                _fail(app, here, ValueError("needs an id: lowercase letters, digits and _"))
                continue
            if mid in app.modules:
                _fail(app, here, ValueError(f"the id {mid!r} is taken by another feature"))
                continue
            if linked and mid not in manifest.get("features", []):
                _fail(app, here, ValueError(f"the feature {mid!r} isn't on its card, so it didn't load"))
                continue
            try:
                inst = cls(app)
            except Exception as e:
                _fail(app, here, e)
                continue
            guard(app, inst)
            if linked:
                held(app, inst, manifest)
            app.modules[mid] = inst
            loaded.append(mid)
            if not linked:
                status(app)["modules"].append(mid)
    return loaded


class _Every(set):
    def __contains__(self, _x) -> bool:
        return True


def held(app, m, manifest: dict) -> None:
    """Hold an add-on by link to its card: what it offers beyond it is left out (and said once in the problems)."""
    name, mid = manifest["name"], m.id
    m.linked = name
    m.linked_card = manifest
    told: set = set()

    def say(what: str, which: str) -> None:
        if (what, which) not in told:
            told.add((what, which))
            _fail(app, f"{name}.{mid}", ValueError(f"the {what} {which!r} isn't on its card, so it was left out"))

    def only(fn, what: str, allowed: set, key):
        def inner(*a, **kw):
            out = []
            for x in fn(*a, **kw) or []:
                k = key(x)
                if k in allowed:
                    out.append(x)
                else:
                    say(what, k)
            return out

        return inner

    cmds = {c["name"] for c in manifest.get("commands") or []}
    if "*" in cmds:  # commands you name yourself (its card says so): any name
        cmds = _Every()
    tools = {t["name"] for t in manifest.get("tools") or []}
    jobs = {j["id"] for j in manifest.get("jobs") or []}
    m.commands = only(m.commands, "command", cmds, lambda c: c.name)
    for kind in ("agent_tools", "call_tools"):
        if callable(getattr(m, kind, None)):
            setattr(m, kind, only(getattr(m, kind), "AI tool", tools, lambda t: t.name))
    every = m.every

    def every_held(job: str, spec: str, action, payload=None, **kw):
        if f"{mid}:{job}" not in jobs:
            say("job", f"{mid}:{job}")
            return None
        return every(job, spec, action, payload, **kw)

    m.every = every_held
    if not manifest.get("classify") and callable(getattr(m, "classify_intent", None)):
        m.classify_intent = None  # it may not see your messages first: its card didn't ask


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

            out.append(
                Intent(
                    it.name,
                    it.description,
                    match,
                    run,
                    it.questions,
                    tuple(getattr(it, "examples", ()) or ()),
                    getattr(it, "guarded", "") or "",
                )
            )
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
