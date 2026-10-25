"""What you believe (stage 14, part 2): about your work and about Kurooto's own state, from what you said and what it
told you.

"He believes the backup ran" (it said so on Monday; the backup failed on Tuesday). "He thinks the deadline is Friday"
(he
said so; Classroom says Thursday). `check` compares each such belief with what is true now, and when they disagree it
tells
you once, plainly, with the evidence: "You may think the backup ran on Monday; it failed on Tuesday at 03:10." The
message
goes through the gate with the purpose `correct_fact`, the one purpose allowed to change what you believe.

Only facts about your work and Kurooto's own state are tracked (DOMAINS). Never your opinions, values or personal
life: a
claim in any other domain isn't kept, and a topic on the deny-list isn't either (model.DENY).
"""

from __future__ import annotations

import datetime as dt
import time
from typing import TYPE_CHECKING

from kurooto.mind.tom import model

if TYPE_CHECKING:
    from kurooto.app import App

DOMAINS = ("backup", "deadline")
PART = "belief"


def told(app: App, domain: str, subject: str, claim: str, fact: dict, source: str = "said") -> dict | None:
    """Keep what you were told (or said): `fact` is the checkable part, {"type": "backup", "ok": True, "at": ts} or
    {"type": "deadline", "id": ..., "due": "2026-10-30T23:59"}. None for any other domain."""
    if domain not in DOMAINS or fact.get("type") != domain:
        return None
    return model.put(
        app, PART, f"{domain}:{subject}", claim, source, 0.9, [f"told:{int(time.time())}"], fact=fact, corrected=False
    )


def check_backup(app: App, fact: dict) -> tuple[bool | None, str]:
    last = app.modules["backups"].last() if app.is_on("backups") else {}
    if not last:
        return None, ""
    if fact.get("ok") and last.get("ok") is False and (last.get("failed_at") or 0) > (fact.get("at") or 0):
        when = dt.datetime.fromtimestamp(last["failed_at"])
        return False, f"it failed on {when:%A at %H:%M}"
    return True, ""


def check_deadline(app: App, fact: dict) -> tuple[bool | None, str]:
    dl = app.modules.get("deadlines")
    it = (dl.items().get(str(fact.get("id"))) if dl is not None and app.is_on("deadlines") else None) or None
    if not it or it.get("status") == "done":
        return None, ""
    if str(it.get("due") or "")[:16] != str(fact.get("due") or "")[:16]:
        when = dt.datetime.fromisoformat(it["due"])
        return False, f"it's now {when:%A %d %B at %H:%M}"
    return True, ""


CHECKS = {"backup": check_backup, "deadline": check_deadline}


def check(app: App, payload: dict | None = None) -> list[str]:
    """Look for beliefs the facts have overtaken; tell you once about each. Returns the row ids told about."""
    if not model.on(app) or not app.settings.get("mind.tom.false_beliefs"):
        return []
    told_ids = []
    for r in model.rows(app, PART):
        fact = r.get("fact")
        if not fact or r.get("corrected") or r.get("wrong") or r["subject"].split(":")[0] not in DOMAINS:
            continue
        try:
            ok, evidence = CHECKS[fact["type"]](app, fact)
        except Exception as e:  # a check that fails can't show a false belief
            app.events.emit("tom_check_failed", error=type(e).__name__)
            continue
        if ok is False:
            _tell(app, r, evidence)
            r["corrected"] = True
            model.put(
                app,
                PART,
                r["subject"],
                r["claim"],
                r["source"],
                r["confidence"],
                r.get("evidence"),
                fact=fact,
                corrected=True,
            )
            told_ids.append(r["id"])
    return told_ids


def _tell(app: App, r: dict, evidence: str) -> None:
    model.guard("correct_fact")
    app.notify(
        f"You may think {r['claim']}; {evidence}.",
        kind="info",
        why="mind.false_belief",
        purpose="correct_fact",
    )
