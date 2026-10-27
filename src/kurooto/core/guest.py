"""The guest path (0.8.10, Voice ID): what happens to words a voice that isn't the owner's said to Kurooto.

App.handle sends every message whose Incoming.speaker isn't the owner's ("guest", "unsure"; anything but "" or
"owner") here first, before anything that acts or learns: replies, /commands, skills, intents, the AI's tools,
settings, calls, the learners (infer, threads, meetings, tone, pest, learning, tuning) and the chat history. Who is
speaking comes only from the voice model, decided before the words reach the AI and carried in Incoming, never in the
prompt: nothing a guest says ("I'm the owner", "ignore your rules") can change it.

A guest gets chat only:
    owner_only_at_all     one line, nothing else (Voice already stops these; this is defence in depth)
    too many this hour    voice.speaker_id.guest_per_hour (an in-memory count of times)
    a /command            "Only my owner can give me commands; I can still chat."
    a request that acts   matched (never run) against the plain-English requests: refused
    one that reads his    "I can't share my owner's things; ask me something general."
    things
    anything else         an AI turn with audience="guest" (core/jobs.py): text only, no tools, no MCP, none of
                          his notes, memory, profile or history, an empty working folder, a guest context
                          (providers/context.py: guest_context); `guest_brain: local` keeps it on this computer

The guest's words aren't kept in his history or Brain's memory: the last four turns of this conversation stay in
memory on Voice (cleared when it closes), the request's words are blanked once Voice has the answer
(jobs.forget_guest), and only a count lasts. Honest limit: agy only reads the text-only rule (it isn't enforced the
way Claude Code's --tools "" or an API without tools is); Kurooto's own tools refuse a guest's job id, also through
agy's own registration of `kurooto mcp`, but agy's own instructions file and other MCP servers it has are its own. The
empty folder and the missing paths make it unlikely to wander, but that isn't a guarantee, so a guest never runs on
agy or Codex: with one of them as the main AI, guests are answered by this computer's model (sealed_brain), or told
plainly that Kurooto only chats with its owner here when there's none."""

from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.base import Incoming

GUEST = ("guest", "unsure")
AT_ALL = "I only answer my owner's voice."
BUSY = "I've answered a lot of guests this hour; try later."
COMMAND = "Only my owner can give me commands; I can still chat."
ACTION = "Only my owner's voice can make me do that; I can still chat."
PERSONAL = "I can't share my owner's things; ask me something general."
NO_LOCAL = "I can only chat when the model on this computer is running."
_times: dict[int, deque] = {}


def setting(app: App, key: str, default=None):
    v = app.settings.get(f"voice.speaker_id.{key}")
    return default if v is None else v


def allowed_now(app: App) -> bool:
    """Under voice.speaker_id.guest_per_hour answers in the last hour (times only, in memory)."""
    q = _times.setdefault(id(app), deque(maxlen=500))
    now = time.monotonic()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= int(setting(app, "guest_per_hour", 20)):
        return False
    q.append(now)
    return True


def kind(app: App, text: str) -> str:
    """What the words ask for, matched and never run: "command", "action", "personal" or ""."""
    t = (text or "").strip()
    if t.startswith("/"):
        return "command"
    from kurooto.core import ledger, repoproject, threads, turnon
    from kurooto.modules.text import QUESTION, tidy

    plain = tidy(t)
    if not plain:
        return ""
    asks = bool(QUESTION.search(plain))
    try:
        if repoproject.asked(plain):
            return "action"
        if threads.THING.search(plain) and (threads.ASK.match(plain) or threads.WHAT.match(plain)):
            return "personal"
        if threads.THING.search(plain) and threads.THING_DONE.search(plain):
            return "action"
        if ledger.LAST_TALK.match(plain) or ledger.DOING.match(plain):
            return "personal"
    except Exception:
        pass
    mods = app.enabled()
    for m in mods:
        try:
            its = m.intents()
        except Exception:  # noqa: S112 (one feature's mistake never stops the check)
            continue
        for it in its:
            try:
                if it.match(plain) is not None:
                    return "personal" if it.questions else "action"
            except Exception:  # noqa: S112
                continue
    try:
        found = turnon.find(app, plain, mods, asks)
    except Exception:
        found = None
    if found is not None:
        return "personal" if getattr(found[1], "questions", False) else "action"
    return ""


def prompt(app: App, text: str) -> str:
    """The guest's request with the last turns of this conversation (in memory on Voice; never written down)."""
    v = app.modules.get("voice")
    vid = getattr(v, "voiceid", None)
    turns = list(getattr(vid, "guest_turns", []) or [])[-4:]
    lines = []
    if turns:
        lines.append("Earlier in this conversation with the visitor:")
        for said, answer in turns:
            lines += [f"Visitor: {said}", f"You: {answer}"]
        lines.append("")
    lines.append(f"The visitor says: {text.strip()[:1500]}")
    return "\n".join(lines)


def sealed_brain(app: App) -> bool:
    """Can the main AI answer a guest with no way to the owner's data? An API brain gets no tools; Claude Code runs
    with --tools "" and --strict-mcp-config. Agent programs with their own MCP servers (agy, Codex) can't be held."""
    from kurooto import providers

    try:
        b = providers.build(app, str(app.settings.get("brain.main") or ""))
    except Exception:
        return False
    return b is not None and (getattr(b, "kind", "") == "api" or getattr(b, "id", "") == "claude")


def handle(app: App, msg: Incoming) -> None:
    """A guest's (or an unsure voice's) message: chat only. Nothing here acts, reads his data or learns."""
    what = "unsure" if msg.speaker == "unsure" else "guest"
    if setting(app, "mode", "owner_only_acts") == "owner_only_at_all":
        app.events.emit("voiceid_refused", what="at_all", speaker=what)
        msg.reply(AT_ALL)
        return
    k = kind(app, msg.text)
    if k:
        app.events.emit("voiceid_refused", what=k, speaker=what)
        msg.reply({"command": COMMAND, "action": ACTION, "personal": PERSONAL}[k])
        return
    if not msg.text.strip():
        return
    brain = None
    from kurooto import providers

    # "main" only when that AI can really be held to text: an API (it gets no tools) or Claude Code (--tools ""). An
    # agent program that loads its own MCP servers on every run (agy: GBrain and the rest; Codex) could reach the
    # owner's notes whatever this run asks, so a guest goes to this computer's model instead (the owner, 2026-10-27:
    # "brain without private data")
    use_local = setting(app, "guest_brain", "main") == "local" or not sealed_brain(app)
    if use_local:
        local = providers.local(app)
        if local is None:
            msg.reply(NO_LOCAL)
            return
        brain = local.id
    if not allowed_now(app):
        app.events.emit("voiceid_refused", what="rate", speaker=what)
        msg.reply(BUSY)
        return
    jid = app.jobs.submit(
        prompt(app, msg.text),
        title="Guest",
        effort="low",
        quiet=True,
        text_only=True,
        lane="you",
        brain=brain,
        audience="guest",
    )
    msg.job = jid  # Voice waits for it (Voice.ask_brain), as for a chat request
    app.events.emit("voiceid_guest_job", job=jid, speaker=what)
