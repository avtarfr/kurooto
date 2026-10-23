"""Your skills as slash commands in your agent programs: Kurooto's skills, your add-ons' skills, your own skills and
the prompts you marked `skill: true`, written into the skills folder of the agent programs you use, so typing /journal
in agy runs the same instructions as /journal on Telegram.

Off until you turn it on: `kurooto export-skills on` (agy), `kurooto export-skills on --to agy,agents`, or the
setting agents.export. Where they go:

    agy       ~/.gemini/antigravity-cli/skills/<name>/SKILL.md   Antigravity: /name
    agents    ~/.agents/skills/<name>/SKILL.md                   Copilot CLI (/name), others that read it
    claude    ~/.claude/skills/<name>/SKILL.md                   Claude Code: /name (only when you ask for it)

Each folder Kurooto writes carries a .kurooto-skill marker, and only those folders are ever changed or removed:
a skill you made yourself in that program is never touched. If one of yours has the same name, Kurooto's goes in as
kurooto-<name> instead; agents.prefix (e.g. "k-") puts a prefix on all of them. A copy you edited by hand is left as
you made it. They're brought up to date when Kurooto starts (so after every update) and every hour: new and changed
skills are written, ones that are gone are removed. `kurooto export-skills off`, emptying agents.export, and
`kurooto uninstall` remove every copy Kurooto made.

Each copy says where your notes folder is and carries the same rules as a skill run by Kurooto (only add to notes,
never delete, nothing goes to anyone else).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "agents",
    {
        "export": [],  # where your skills go as slash commands: "agy", "agents" (Copilot CLI and others), "claude"
        "prefix": "",  # put before every exported skill's name, e.g. "k-" for /k-journal
        # your own scripts your AI programs may run unattended (full paths; each does one thing): not shells or
        # interpreters (bash, python, node...), which would run anything
        "scripts": [],
    },
)

TARGETS = {
    "agy": (".gemini", "antigravity-cli", "skills"),
    "agents": (".agents", "skills"),
    "claude": (".claude", "skills"),
}
LABELS = {"agy": "agy", "agents": "Copilot CLI and other agents", "claude": "Claude Code"}
MARK = ".kurooto-skill"
STATE = "agent-skills.json"
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def target_dir(target: str, home: Path | None = None) -> Path:
    return (home or Path.home()).joinpath(*TARGETS[target])


def wanted_targets(app: App) -> list[str]:
    raw = app.settings.get("agents.export") or []
    if isinstance(raw, str):
        raw = [raw]
    return [t for t in TARGETS if t in raw]


def _prefix(app: App) -> str:
    p = re.sub(r"[^a-z0-9-]+", "-", str(app.settings.get("agents.prefix") or "").lower()).lstrip("-")
    return p[:20]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _marker(d: Path) -> dict | None:
    """Kurooto's marker in a skill folder ({} if it's there but unreadable), or None if the folder isn't Kurooto's."""
    f = d / MARK
    if not f.is_file():
        return None
    return jload(f, {}) or {}


def render(app: App, skill, name: str) -> str:
    """The SKILL.md an agent program gets: the skill's instructions, where the notes are, and the rules."""
    from kurooto.modules.skills import RULES

    desc = f"Kurooto: {skill.description}".replace("\n", " ").strip()
    body = skill.body.rstrip()
    if "$ARGUMENTS" not in body:
        body += "\n\nWhat they gave you: $ARGUMENTS"
    args = f" After the command they type: {skill.args}." if skill.args else ""
    return (
        f"---\nname: {name}\ndescription: {json.dumps(desc, ensure_ascii=False)}\n---\n\n"
        f"Their notes folder is {app.workspace}; note paths below are inside it.{args}\n\n"
        f"{body}\n\n{RULES}\n"
    )


def _remove(d: Path) -> str:
    """Take one of Kurooto's copies away: "removed", or "kept" when you edited it (then it's yours: the marker goes)."""
    m = _marker(d)
    if m is None:
        return "not ours"
    f = d / "SKILL.md"
    try:
        edited = f.is_file() and m.get("sha") and _sha(f.read_text(encoding="utf-8")) != m["sha"]
        if edited:
            (d / MARK).unlink(missing_ok=True)
            return "kept"
        f.unlink(missing_ok=True)
        (d / MARK).unlink(missing_ok=True)
        try:
            d.rmdir()  # only when empty: anything you put in the folder stays
        except OSError:
            pass
        return "removed"
    except OSError:
        return "failed"


def _ours(root: Path, install: str) -> list[Path]:
    """Kurooto's copies in a skills folder, made by this install."""
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        m = _marker(d) if d.is_dir() else None
        if m is not None and m.get("install") in (install, None):
            out.append(d)
    return out


def sync(app: App) -> dict:
    """Bring the copies in line with the skills you have now, in the places agents.export names, and remove them
    from places it no longer names. Returns what happened: written, removed, renamed (yours had the name), edited
    (yours now, left alone), problems. One at a time (the hourly update and a terminal may overlap)."""
    from kurooto.core.lock import Lock

    with Lock(app.paths.state, "agent-skills", timeout=60):
        return _sync(app)


def _sync(app: App) -> dict:
    from kurooto.modules.skills import all_skills

    rep: dict = {"targets": [], "written": [], "same": 0, "removed": [], "renamed": [], "edited": [], "problems": []}
    st_file = app.paths.state / STATE
    before = jload(st_file, {}) or {}
    targets = wanted_targets(app)
    if not targets and not before.get("targets"):
        return rep
    install = str(app.paths.config)
    skills = {n: s for n, s in all_skills(app).items() if not s.internal} if targets else {}
    prefix = _prefix(app)
    for t in sorted(set(targets) | set(before.get("targets") or [])):
        root = target_dir(t)
        keep: set[str] = set()
        if t in targets:
            rep["targets"].append(t)
            for name, s in skills.items():
                folder = f"{prefix}{name}"[:64]
                d = root / folder
                if d.exists() and _marker(d) is None:  # one of yours has this name: ours goes in beside it
                    d = root / f"kurooto-{name}"[:64]
                    if d.exists() and _marker(d) is None:
                        rep["problems"].append(f"{t}: {folder} and {d.name} are both yours; left alone")
                        continue
                    rep["renamed"].append(f"{t}: /{d.name} (you have your own /{folder})")
                keep.add(d.name)
                text = render(app, s, d.name)
                f = d / "SKILL.md"
                m = _marker(d)
                try:
                    cur = f.read_text(encoding="utf-8") if m is not None and f.is_file() else None
                    if cur == text:
                        rep["same"] += 1
                        continue
                    if cur is not None and m.get("sha") and _sha(cur) != m["sha"]:
                        rep["edited"].append(f"{t}: {d.name}")  # you changed it: yours now
                        continue
                    d.mkdir(parents=True, exist_ok=True)
                    f.write_text(text, encoding="utf-8")
                    jsave(d / MARK, {"sha": _sha(text), "skill": name, "source": s.source, "install": install})
                    rep["written"].append(f"{t}: {d.name}")
                except OSError as e:
                    rep["problems"].append(f"{t}: {d.name}: {e}"[:200])
        for d in _ours(root, install):
            if d.name not in keep:
                how = _remove(d)
                if how in ("removed", "kept"):
                    rep["removed" if how == "removed" else "edited"].append(f"{t}: {d.name}")
    if targets:
        jsave(
            st_file,
            {
                "targets": rep["targets"],
                "at": time.time(),
                "count": len(rep["written"]) + rep["same"],
                "problems": rep["problems"],
                "renamed": rep["renamed"],
            },
        )
    else:  # turned off and cleaned up: nothing left to keep up to date
        st_file.unlink(missing_ok=True)
    _schedule(app, bool(targets))
    if rep["written"] or rep["removed"] or rep["problems"]:
        app.events.emit(
            "skills_exported", written=len(rep["written"]), removed=len(rep["removed"]), problems=len(rep["problems"])
        )
    return rep


def refresh(app: App, payload: dict | None = None) -> dict | None:
    """The hourly (and at start) update; never raises."""
    try:
        return sync(app)
    except Exception as e:
        app.events.emit("skills_export_failed", error=f"{type(e).__name__}: {e}"[:200])
        return None


def _schedule(app: App, on: bool) -> None:
    """The hourly update is booked only while skills are exported (`kurooto export-skills on` books it from a
    terminal too: the running Kurooto reads its schedule every half minute)."""
    booked = app.scheduler.get("agents:export") is not None
    if on and not booked:
        app.scheduler.every("agents:export", "hourly", "agents.export", {"what": "skills into agent programs"})
    elif not on and booked:
        app.scheduler.cancel("agents:export")


def start(app: App) -> None:
    """At start (so after every update too): bring the copies up to date in the background, when there are any."""
    import threading

    app.scheduler.action("agents.export", lambda p: refresh(app, p))
    if wanted_targets(app) or (app.paths.state / STATE).exists():
        threading.Thread(target=refresh, args=(app,), name="skills-export", daemon=True).start()
    else:
        _schedule(app, False)


def remove_all(state: Path, config: Path) -> list[str]:
    """`kurooto uninstall`: remove every copy this install made (it recorded where). Your own skills stay."""
    st = jload(state / STATE, {}) or {}
    out = []
    for t in st.get("targets") or []:
        if t not in TARGETS:
            continue
        for d in _ours(target_dir(t), str(config)):
            if _remove(d) == "removed":
                out.append(f"{t}: {d.name}")
    (state / STATE).unlink(missing_ok=True)
    return out


def status(app: App) -> dict:
    """What's exported where (for `kurooto export-skills status` and `kurooto doctor`)."""
    st = jload(app.paths.state / STATE, {}) or {}
    install = str(app.paths.config)
    where = {t: [d.name for d in _ours(target_dir(t), install)] for t in wanted_targets(app)}
    return {"targets": wanted_targets(app), "skills": where, "at": st.get("at"), "problems": st.get("problems") or []}


def report(rep: dict) -> str:
    """A few lines for a terminal."""
    if not rep["targets"] and not rep["removed"]:
        return "Not exporting skills (kurooto export-skills on turns it on)."
    lines = []
    if rep["targets"]:
        n = len(rep["written"]) + rep["same"]
        lines.append(
            f"{n} skill cop{'ies' if n != 1 else 'y'} in {', '.join(LABELS[t] for t in rep['targets'])}"
            f" ({len(rep['written'])} written or updated)."
        )
    if rep["removed"]:
        lines.append(f"Removed {len(rep['removed'])}: " + ", ".join(rep["removed"][:12]))
    for r in rep["renamed"][:12]:
        lines.append(f"  {r}")
    for r in rep["edited"][:12]:
        lines.append(f"  {r}: you edited it, so it's yours now and Kurooto leaves it alone")
    for p in rep["problems"][:12]:
        lines.append(f"  ! {p}")
    return "\n".join(lines)


def doctor_check(app: App) -> tuple[str, bool | None, str] | None:
    """One `kurooto doctor` line when skills are exported."""
    targets = wanted_targets(app)
    if not targets:
        return None
    st = jload(app.paths.state / STATE, {}) or {}
    if not st.get("at"):
        return (
            "skills in agents",
            None,
            "not exported yet (Kurooto does it within the hour, or: kurooto export-skills on)",
        )
    probs = st.get("problems") or []
    where = ", ".join(LABELS[t] for t in targets)
    if probs:
        return ("skills in agents", False, f"{where}: {len(probs)} problem(s): {'; '.join(probs[:2])}")
    return ("skills in agents", True, f"{st.get('count', 0)} copies in {where}")
