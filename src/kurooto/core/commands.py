"""The command table and /help (Telegram and the phone app's chat; the same function): every /command, Kurooto's own
(CORE, answered in App.handle) and each feature's (Module.commands()), and the plain words each feature understands at
once (Intent.examples), in groups, each with its page in the user wiki.

    /help           the index: one line per group with its commands (of what's on), and "/help <group>" for the rest
                    (always this form since 0.6.0: with everything merged, the full list no longer fits one message)
    /help <group>   one group in full (talking, reminders, calls, ...): what each command does, what you can just
                    say, the features in it that are off, and its wiki page
    /help all       every group, one message each
    /help <word>    what matches it, on or off

Every message stays under Telegram's 4096 characters (LIMIT); an index that won't fit one comes in two, split between
groups. A feature that isn't in a group lands in "More".
tests/unit/test_help.py fails when a command registered anywhere isn't in /help.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.base import Command, Intent, Module

LIMIT = 3900  # characters per message (Telegram takes 4096)

# Kurooto's own commands, answered in App.handle whatever is on: (names, what it does)
CORE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("q", "questions"), "open questions I asked you (reply to one to answer it)"),
    (("jobs",), "what the AI is working on and what waits, with Cancel buttons"),
    (("threads",), 'what you\'re in the middle of, with Done, Drop and Undo; also "did I finish that thing?"'),
    (("help", "start"), "this list; /help <group> shows one group in full, /help <word> finds a command or feature"),
    (("aboutme",), "what I know about you (your profile's In-brief part), and where to edit it"),
    (("persona",), "your persona card: how I talk to you (/persona tone: plain, /persona clear)"),
    (("inferred",), "what was set up from what you said (a project, a class, a meeting), with /inferred undo <id>"),
    (("forget",), "forget what I kept of our conversations: /forget 7d (or 2w, 12h), /forget all (asks first)"),
    (("gists",), "one line of what each forgotten call or request decided; /gists <words> finds them"),
    (
        ("memory",),
        'what I remember (encrypted): /memory <words> finds, /memory forget 3, /memory export; also "when did I '
        'last talk to Prof Ortiz?", "what was I doing last Thursday?"',
    ),
    (("helper",), "the offline helper: on, off, test"),
    (("egress",), "where my requests went in the last 7 days: each host and feature, requests, bytes, any blocked"),
    (("health",), "what isn't working, with Fix buttons (/health now checks online too)"),
    (("fixme",), "what's wrong and what to do, by rules (no AI needed); /fixme <what you see>, /fixme ai explains"),
    (("keep",), "what you used of each feature that's on (last 30 days); /keep <feature> offers Quiet and Off"),
    (("calm",), "messages that come by themselves: today's count, the limit and what waits"),
    (("why",), "why the last message that came by itself came"),
    (("notes",), "pdf <course>: a course's notes as one PDF; /notes pdf template: a copy of the template to edit"),
    (
        ("project",),
        "a project set up from its repository: /project add <github address | folder> [as <name>], /project update "
        '<name>, /project lists them; also "set up my project from github.com/owner/name"',
    ),
)
SYNC = (("sync",), "sync everything that's on (Classroom, calendar, research, notes brain)")  # while Notes sync is off


@dataclass(frozen=True)
class Group:
    key: str  # /help <key>
    title: str
    page: str  # docs/wiki/user/<page>.md
    modules: tuple[str, ...] = ()
    core: tuple[str, ...] = ()  # first names in CORE (and "sync")
    moved: tuple[str, ...] = ()  # commands of a feature in another group that belong here (Telegram's /hold)


GROUPS: tuple[Group, ...] = (
    Group(
        "talking",
        "Talking",
        "talking-to-kurooto",
        ("telegram", "chat", "voice_notes"),
        ("q", "jobs", "threads", "help"),
    ),
    Group("reminders", "Reminders and deadlines", "reminders-and-deadlines", ("reminders", "deadlines", "startby")),
    Group(
        "classes",
        "Classes and calendar",
        "classes-and-timetable",
        ("subjects", "commitments", "classpacks", "doubts", "capture", "calendar"),
    ),
    Group("study", "Study", "books-and-study", ("study", "books", "handwritten", "drafts")),
    Group("quiz", "Quiz and exams", "quiz-and-exams", ("quiz", "exam_season", "hints")),
    Group("calls", "Calls and phone", "calls", ("calls", "alarm", "lidsafe"), moved=("hold", "calls")),
    Group("checkins", "Check-ins and journal", "check-ins-and-journal", ("checkins", "dreaming", "weekly", "quests")),
    Group(
        "notes",
        "Notes",
        "notes-and-concept-graph",
        ("library", "gbrain", "notes_sync", "integrate", "files"),
        ("sync", "notes"),
    ),
    Group("skills", "Skills and routines", "skills-and-routines", ("skills",)),
    Group("research", "Research", "research", ("research", "research_addon"), ("project",)),
    Group(
        "google",
        "Google",
        "google",
        (
            "google",
            "classroom_notes",
            "mail_digest",
            "reply_drafts",
            "digest_email",
            "agent_plan",
            "google_calendar",
            "drive_upload",
        ),
    ),
    Group(
        "teaching",
        "Teaching Kurooto",
        "teaching-kurooto",
        ("remember", "retro", "learning", "cases"),
        ("aboutme", "persona", "inferred"),
    ),
    Group("privacy", "Privacy and memory", "privacy", (), ("forget", "gists", "memory", "egress")),
    Group(
        "settings",
        "Settings and upkeep",
        "your-computer",
        ("backups", "profile", "space", "local_models", "awake", "terminals", "terminal", "overlay"),
        ("health", "fixme", "keep", "calm", "why", "helper"),
    ),
)
MORE = Group("more", "More", "index")  # a feature no group names (an add-on, a new one)


def wiki(page: str = "") -> str:
    from kurooto.update.updater import PAGES

    return f"{PAGES}/wiki/user/{page}.html" if page else f"{PAGES}/wiki/"


def group_of(module_id: str) -> Group:
    return next((g for g in GROUPS if module_id in g.modules), MORE)


def find_group(word: str) -> Group | None:
    w = word.strip().lower()
    return next((g for g in (*GROUPS, MORE) if w in (g.key, g.title.lower())), None)


def _short(m: Module) -> str:
    return m.title.split(" (")[0]


def _commands(app: App, m: Module) -> list[Command]:
    try:
        return list(m.commands())
    except Exception as e:  # one feature's mistake never hides the others' commands
        app.events.emit("commands_failed", module=m.id, error=str(e)[:200])
        return []


def _intents(app: App, m: Module) -> list[Intent]:
    try:
        return list(m.intents())
    except Exception as e:  # a feature's intents failing must not take /help down
        app.events.emit("module_failed", module=m.id, error=f"in /help: {e}"[:300])
        return []


def _extra(app: App, m: Module, names: set[str]) -> list[str]:
    """Lines a feature adds to its help that aren't one of its commands ("/<skill> …  runs a skill")."""
    try:
        lines = [str(x) for x in m.help()]
    except Exception:
        return []
    return [x for x in lines if x.startswith("/") and x[1:].split(None, 1)[0].strip(",") not in names]


def _core(app: App, name: str) -> tuple[tuple[str, ...], str] | None:
    if name == "sync":
        return None if app.is_on("notes_sync") else SYNC
    if name == "notes" and not app.is_on("subjects"):  # /notes pdf <course>: listed once you have courses
        return None
    return next((c for c in CORE if c[0][0] == name), None)


def _say(it: Intent) -> str:
    """A request as /help shows it: its example phrasings, or what it does when it has none."""
    return ", ".join(f'"{x}"' for x in it.examples) if it.examples else it.description


def _line(names: tuple[str, ...], text: str) -> str:
    return f"{', '.join('/' + n for n in names)}  {text}"


def _parts(app: App, g: Group, on: list[Module]):
    """(command lines, plain-word lines, command names) of a group, for the features that are on."""
    lines, said, names = [], [], []
    for n in g.core:
        c = _core(app, n)
        if c:
            lines.append(_line(*c))
            names += c[0]
    for m in on:
        mine = group_of(m.id) == g
        cmds = [c for c in _commands(app, m) if (mine and c.name not in _moved()) or c.name in g.moved]
        if not mine and not cmds:
            continue
        lines += [_line((c.name,), c.help) for c in cmds]
        names += [c.name for c in cmds]
        if mine:
            lines += _extra(app, m, {c.name for c in _commands(app, m)})
            for it in _intents(app, m):
                said.append(_say(it))
    return lines, said, names


def _moved() -> set[str]:
    return {n for g in GROUPS for n in g.moved}


def section(app: App, g: Group, on: list[Module], offs: bool) -> str:
    """One group: its title and wiki page, each command with what it does, what you can just say, and (offs) the
    features in it that are off."""
    lines, said, _ = _parts(app, g, on)
    out = [f"{g.title} (more: {wiki(g.page)})", *lines]
    if said:
        out += ["Just say:", *(f"- {s}" for s in dict.fromkeys(said))]
    if offs:
        off = [m for m in app.modules.values() if group_of(m.id) == g and m not in on and m.title]
        for m in off:
            cmds = " ".join(f"/{c.name}" for c in _commands(app, m))
            out.append(f"Off: {_short(m)}{f' ({cmds})' if cmds else ''}. Features → {_short(m)} → Turn on.")
        if len(out) == 1:
            out.append("Nothing here yet.")
    return "\n".join(out)


def _footer(app: App) -> list[str]:
    out = []
    if app.app_main():
        out.append("You talk to me in the phone app's chat; Telegram is optional (Features → Telegram).")
    # a bundle's members (Check my draft in the Research add-on) are turned on with their bundle, not one by one
    offs = [m for m in app.modules.values() if not app.is_on(m.id) and m.title and not getattr(m, "bundle", "")]
    off = [m.title for m in offs if not getattr(m, "extra", False)]
    extras = len(offs) - len(off)  # add-ons that come with Kurooto: named in Features, counted here
    if off:
        out.append(
            f"Off right now ({len(off)}): "
            + ", ".join(off)
            + (f"; and {extras} add-on{'s' if extras != 1 else ''}" if extras else "")
            + ". /help <name> says what one does."
        )
    if not app.is_on("chat"):
        out.append("(Chat is off, so free text isn't sent to an AI.)")
    out.append(f"Everything, with examples, settings and fixes: {wiki()}")
    return out


def _clip(text: str) -> str:
    return text if len(text) <= LIMIT else text[: LIMIT - 2].rsplit("\n", 1)[0] + "\n…"


def help(app: App, arg: str = "") -> list[str]:
    """/help's messages, each under LIMIT characters."""
    on = app.enabled()
    on += [m for m in app.basics() if m not in on]  # Telegram's /pause, /focus... in the phone app's chat
    word = (arg or "").strip().lower()
    if word == "all":
        return [_clip(section(app, g, on, offs=True)) for g in (*GROUPS, MORE) if _shown(app, g, on, True)]
    g = find_group(word) if word else None
    if g is not None:
        return [_clip(section(app, g, on, offs=True))]
    if word:
        return [_clip(find(app, word))]
    head = (
        f"{app.name}, your assistant. Plain words work; so do these commands, by group. /help <group> shows a group in "
        "full: what each command does and what you can just say. /help all sends every group; /help <word> finds one."
    )
    index = []
    for g in (*GROUPS, MORE):
        if not _shown(app, g, on, False):
            continue
        _, said, names = _parts(app, g, on)
        say = f" · {len(said)} thing{'s' if len(said) > 1 else ''} to just say" if said else ""
        index.append(f"{g.title} (/help {g.key}; {wiki(g.page)}): {' '.join('/' + n for n in names)}{say}")
    return _pack([head, *index, "\n".join(_footer(app))])


def _pack(paragraphs: list[str]) -> list[str]:
    """Paragraphs (blank lines between them) in as few messages under LIMIT as they fit; each one clipped to fit."""
    out: list[str] = []
    for p in paragraphs:
        p = _clip(p)
        if out and len(out[-1]) + 2 + len(p) <= LIMIT:
            out[-1] += "\n\n" + p
        else:
            out.append(p)
    return out


def _shown(app: App, g: Group, on: list[Module], offs: bool) -> bool:
    lines, said, _ = _parts(app, g, on)
    return bool(lines or said) or (offs and any(group_of(m.id) == g for m in app.modules.values()))


def find(app: App, word: str) -> str:
    """/help <word>: Kurooto's own commands and every feature, on or off, whose name, commands or requests match."""
    on = app.enabled()
    hits: list[str] = []
    for names, h in (*CORE, SYNC):
        if any(word in n for n in names) or word in h.lower():
            hits.append(_line(names, h))
    for m in app.modules.values():
        state = "" if m in on else ' (off: turn it on in Features, or say "turn on ' + m.title.lower() + '")'
        about = f"{m.title} {m.description}".lower()
        cmds = [c for c in _commands(app, m) if word in c.name or word in c.help.lower()]
        said = [
            i for i in _intents(app, m) if word in i.description.lower() or any(word in x.lower() for x in i.examples)
        ]
        if word in about or cmds or said:
            hits.append(f"{m.title}{state}: {m.description}")
            hits += [f"  /{c.name}  {c.help}" for c in cmds]
            hits += [f"  - {_say(i)}" for i in said]
    if not hits:
        return f'Nothing here matches "{word}". The user wiki has everything: {wiki()}'
    return "\n".join([f'About "{word}":', *hits, "", f"More in the user wiki: {wiki()}"])
