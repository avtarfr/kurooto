"""How you like help (stage 14, part 4): the preferences it already keeps, made explicit with a source and the date
learned.

From your how-to-help-me note (source said: your own lines), and from what you undid or corrected (source inferred:
"undid its
changes to your notes twice: prefers to approve those first"). They only adjust level and timing, never framing.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from kurooto.mind.tom import model

if TYPE_CHECKING:
    from kurooto.app import App

PART = "pref"


def sync(app: App) -> int:
    n = 0
    try:
        from kurooto.modules.remember import help_brief

        for line in (help_brief(app) or "").splitlines():
            line = line.strip(" -*\t")
            old = model.get(app, model.key(PART, f"help:{model.norm(line)[:30]}", line))
            if old is not None and old.get("wrong"):
                continue  # you marked it wrong: reading the note again doesn't bring it back (0.9.0 fix)
            if len(line) >= 8 and model.put(
                app,
                PART,
                f"help:{model.norm(line)[:30]}",
                line,
                "said",
                1.0,
                ["how-to-help-me"],
                learned=time.strftime("%Y-%m-%d"),
            ):
                n += 1
    except Exception:  # noqa: S110 (no note yet)
        pass
    return n


def console_edit(app: App, act: str, rid: str) -> dict:
    """(0.9.0, mind.console.edit) The Brain console's Wrong and Forget on a row of the model of you, only on your
    click. A Wrong on a line from your how-to-help-me note offers to take that line out of the note, but only a line
    Kurooto wrote there (under one of its own headings), and only when you confirm ("unline")."""
    if not app.settings.get("mind.console.edit"):
        return {"ok": False, "said": "Editing from the console is off (mind.console.edit)."}
    r = model.get(app, rid)
    if r is None:
        return {"ok": False, "said": "That row is gone."}
    if act == "forget":
        return {"ok": True, "said": model.forget(app, rid)}
    if act == "wrong":
        out: dict = {"ok": True, "said": model.wrong(app, rid)}
        if r["part"] == PART and str(r["subject"]).startswith("help:") and kurooto_line(app, r["claim"]):
            out["offer"] = {"act": "unline", "id": rid, "line": r["claim"]}
        return out
    if act == "unline":
        from kurooto.modules.remember import remove_line

        if not r.get("wrong") or not kurooto_line(app, r["claim"]):
            return {"ok": False, "said": "Only a line Kurooto wrote, marked wrong first, can be taken out here."}
        done = remove_line(app, r["claim"])
        app.events.emit("mind_console_unline", ok=done)
        return {"ok": done, "said": "Taken out of your how-to-help-me note." if done else "It isn't in the note as "
                "written any more, so nothing changed."}  # fmt: skip
    return {"ok": False, "said": "No such action."}


def kurooto_line(app: App, line: str) -> bool:
    """Is "- line" in your how-to-help-me note under one of the headings Kurooto writes under (modules/remember.py:
    TOLD, PICKED, LEARNED)? Your own lines elsewhere are never offered."""
    from kurooto.modules import remember

    try:
        text = remember.help_file(app).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    heading = ""
    for ln in text.split("\n"):
        if ln.startswith("#"):
            heading = ln.lstrip("#").strip()
        elif ln.rstrip() == f"- {line}".rstrip():
            return heading in (remember.TOLD, remember.PICKED, remember.LEARNED)
    return False


def from_undo(app: App, what: str) -> None:
    """He undid or corrected something of this kind: a weak, inferred preference, firmer each time."""
    r = next((x for x in model.rows(app, PART) if x["subject"] == f"undo:{what}"), None)
    times = int(r.get("times", 0)) + 1 if r else 1
    model.put(
        app,
        PART,
        f"undo:{what}",
        f"prefers to check {what} before they happen (undone {times}x)",
        "inferred",
        min(0.9, 0.3 + 0.2 * times),
        [f"undo:{what}"],
        by_subject=True,
        times=times,
    )
