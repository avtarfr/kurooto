"""Never without a tap (docs/ROADMAP.md): what Kurooto does only when you asked for it yourself or tapped to approve
it. The AI, a guess from what you said (core/infer.py) or a schedule of its own never does these by itself.

GUARDED below names each guarded action, the ways it can be approved (WAYS) and where it happens. Code says which
guarded action it performs with a tag: `Tool(..., guarded="alarm.set")` (modules/calls/tools.py) for the AI's tools,
`Intent(..., guarded="call.place")` (modules/base.py) for plain-English requests. tests/unit/test_tap.py walks every
tool and every request, catches any that reaches a guarded action without its tag, and checks each tag's way is one
this table allows.

The AI's tools: on a live call you're on the line, you asked, and the call says what it did, so a tool runs. Anywhere
else (an AI request, an agent program over `kurooto mcp`, the local API) a guarded tool isn't run: it becomes an
Approve / Deny question (core/ask.py), and runs when you tap Approve (core/tools.py:run_tool, ask_first() here).

BY_ITSELF below is the other side: the data fixes the nightly look back (modules/retro.py) makes without a tap, each
said in one line with Undo. None of them is a guarded action; anything outward, an alarm or a call waits for a tap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.calls.tools import Tool

HOOK = "tap.tool"  # app.ask.hooks: the Approve that runs a tool that waited (App.__init__)
DIRECT = ("call",)  # run_tool's `via` where you're the one asking: a live call (one that went on as text too)

WAYS = {
    "typed": "you typed the /command yourself (Telegram, the phone app's chat, `kurooto ask` or `kurooto call`)",
    "said": "you asked in plain words in the chat, an instant request (no AI), and the answer says what was done",
    "call": "you asked on a live call; the AI on the line does it while you're there and says so",
    "button": "a button you tap: under a suggestion (Set 07:00), Turn on, the dashboard or the phone app",
    "approval": "an Approve / Deny question (or Send / Edit / Discard); nothing happens before you tap",
    "confirm": "a second step with its own button (/forget all: Forget everything / Keep it)",
}


@dataclass(frozen=True)
class Guard:
    what: str  # in plain words, for the approval question and /help
    ways: tuple[str, ...]  # keys of WAYS
    where: str  # what does it, for the wikis


GUARDED: dict[str, Guard] = {
    "alarm.set": Guard(
        "set, move or clear an alarm",
        ("typed", "said", "call", "button", "approval"),
        '/alarm, "wake me at 6:45", set_alarm on a call, Set under the alarm suggestion, the dashboard and the phone '
        "app; an AI request asks first",
    ),
    "call.place": Guard(
        "place a call or book one",
        ("typed", "said", "call", "approval"),
        '"call me at 5", "call me now", "I\'m awake", "quiz me by call", /quiz <subject> call, `kurooto call`, '
        "schedule_call and call_now on a call; an AI request asks first. Calls of features you turned on (check-ins, "
        "the alarm, deadline calls) ring at the times you set",
    ),
    "mail.read": Guard(
        "read mail from a new sender, domain, label or search",
        ("typed", "button"),
        "/mail read, /mail query, /mail in label and /mail in from (Email in), Features → Mail digest; never by the AI",
    ),
    "send.out": Guard(
        "send something to someone else (mail, a message, publishing)",
        ("approval",),
        "a reply draft waits in Gmail until you tap Send; nothing else sends to anyone but you",
    ),
    "repo.attach": Guard(
        "attach a code repository to a project",
        ("typed", "button"),
        "/repos add <folder> [as <project>], /latex add <folder> [main.tex] (Research add-on), /project add <address> "
        'and `kurooto project add`; Set it up under "set up my project from <address>" and the Research card\'s '
        "Add a project from a repository; repositories are never searched for on the disk",
    ),
    "addon.install": Guard(
        "add or update an add-on by link (code that runs inside Kurooto), official ones too",
        ("typed", "button"),
        "`kurooto addons add|update` after its card (yes typed, or --yes; `add <name>` for an official one), Features "
        "→ Add-ons (Add or Update after the card, with the box for code ticked), /addons's Add and Update buttons "
        "(the card comes as a message; only its Add / Update button adds); never by the AI, a request or a schedule",
    ),
    "proposal.apply": Guard(
        "apply a change the AI proposed to your files (notes, a project, a skill)",
        ("typed", "button"),
        "Apply under a proposal (Telegram, the phone app's chat, the morning message, the dashboard's Proposals page) "
        "and /proposals apply <id>; never by the AI, a request or a schedule (core/proposals.py)",
    ),
    "data.delete": Guard(
        "delete your data",
        ("typed", "confirm", "button"),
        "/forget 7d and /forget all (after Forget everything), /memory forget, /gists forget, Undo and Drop buttons, "
        "Keep A / Keep B under the morning message's \"Worth a look\", Delete Brain's data after Brain is turned off; "
        "the AI never deletes (a note it changes keeps its earlier version)",
    ),
}


# Buttons that perform a guarded action (their prefix -> the action): each needs "button" among its ways
# (tests/unit/test_tap.py). oad: an official add-on's Add / Update (core/official.py)
BUTTONS: dict[str, str] = {
    "oad": "addon.install",
    "mnd": "data.delete",  # Delete Brain's data, offered when Brain is turned off (modules/mind.py)
}


# What the nightly look back may change by itself (with Undo), because it is sure and it's only your own data.
BY_ITSELF: dict[str, str] = {
    "deadline.merge": "two copies of one deadline (Classroom's and the one you said) become one",
}


def action_of(tool: Tool, args: dict) -> str:
    """The guarded action this tool would perform with these arguments, or "" (not guarded, or it asks by itself)."""
    if not tool.guarded or tool.asks:
        return ""
    if tool.guard_if is not None:
        try:
            if not tool.guard_if(args):
                return ""
        except Exception:  # unsure: asked like the rest
            pass
    return tool.guarded


def _shown(args: dict) -> str:
    return ", ".join(f"{k}: {str(v).strip()[:120]}" for k, v in args.items() if str(v).strip()) or "no details"


def ask_first(app: App, tool: Tool, action: str, args: dict, via: str = "ai", job: str | None = None) -> str:
    """Instead of running a guarded tool: an Approve / Deny question, and what the AI should tell the user."""
    g = GUARDED[action]
    payload = {"tool": tool.name, "args": args}
    for q in app.ask.pending(kind="approval", source="tap"):
        hp = q.get("hook_payload") or {}
        if hp.get("tool") == tool.name and hp.get("args") == args:
            return f"Not done: it already waits for the user's tap (approval {q['id']}). Tell them; don't ask again."
    who = {"mcp": "An AI program (through kurooto mcp)", "api": "A program on this computer"}.get(via, "An AI request")
    title = ""
    jobs = getattr(app, "jobs", None)
    if job and jobs is not None:
        try:
            j = jobs.get(job)
            title = f' ("{j.title[:60]}")' if j and j.title else ""
        except Exception:
            title = ""
    qid = app.ask.approval(
        f"{who}{title} wants to {g.what}: {tool.name} ({_shown(args)}). Do it?",
        hook=HOOK,
        hook_payload=payload,
        source="tap",
        title="Your OK first",
        why="tap.approval",
        about=tool.name,
    )
    app.events.emit("tap_asked", tool=tool.name, action=action, via=via)
    return (
        f"Not done yet: to {g.what} needs the user's tap. They've been asked to approve it (approval {qid}); it "
        "happens only if they tap Approve. Tell them it's waiting for their OK; don't ask again or try another way."
    )


def approved(app: App, q: dict, answer: str) -> str:
    """The answer to ask_first's question: Approve runs the tool as it was asked for; anything else leaves it."""
    from kurooto.core.ask import APPROVE
    from kurooto.core.tools import agent_tools

    p = q.get("hook_payload") or {}
    name, args = str(p.get("tool") or ""), p.get("args") if isinstance(p.get("args"), dict) else {}
    if answer != APPROVE:
        app.events.emit("tap_denied", tool=name)
        return "Not done; left as it is."
    tool = next((t for t in agent_tools(app) if t.name == name), None)
    if tool is None:
        return f"Couldn't: {name} isn't there any more (its feature may be off)."
    app.events.emit("tap_approved", tool=name)
    try:
        out: Any = tool.run(args)
    except Exception as e:
        app.events.emit("tool_failed", name=name, error=f"{type(e).__name__}: {e}"[:200])
        return f"That failed: {type(e).__name__}: {e}"[:190]
    return str(out)[:190] if out else "Done."
