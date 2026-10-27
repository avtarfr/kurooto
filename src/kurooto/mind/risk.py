"""Action classes and the risk classifier (Brain, 0.8.0 stage 06): how risky each thing Kurooto might do on its own is.

Code assigns the class from the action's id, never the AI. The AI may *raise* a class (it can say "this one's riskier
than
you think"), never lower it; an action nobody has classified is ALWAYS until you classify it (`/autonomy classify`).

    R0  reversible, inward        draft a note in its scratch folder, recheck, tidy its own state, run a local
    analysis, prepare
    R1  reversible, your things   move a study block within today, snooze a non-urgent reminder, reorder today's list,
    tag
                                  its own note block, queue a background job, merge a duplicate deadline
    R2  reversible but noticeable reschedule across days, write into your notes (through a proposal), change a setting
    of
                                  its own that isn't about safety
    R3  hard to reverse           change a setting that affects the messages you get
    ALWAYS (never unlockable, I-8) the actions in core/tap.py's GUARDED: deleting your data, sending anything outward,
    money,
                                  alarms, calls, attaching repositories, installing anything, editing a protected
                                  file, applying
                                  a proposal to your files
"""

from __future__ import annotations

from kurooto.core.tap import GUARDED

PART = "autonomy"  # its switch: mind.autonomy.on

ORDER = ("R0", "R1", "R2", "R3", "ALWAYS")
CLASSES: dict[str, str] = {
    # R0
    "draft.note": "R0", "recheck": "R0", "tidy.state": "R0", "analysis.local": "R0", "prepare": "R0",
    # R1
    "study.move_block": "R1", "reminder.snooze_nonurgent": "R1", "list.reorder_today": "R1", "note.tag_own_block": "R1",
    "job.queue": "R1", "deadline.merge": "R1",
    "study.block": "R1", "job.revision_pack": "R1", "dream.keep_card": "R1",  # 0.8.16 (mind.act.more)
    # R2
    "schedule.cross_day": "R2", "notes.write_proposal": "R2", "setting.own_nonsafety": "R2",
    "deadline.reshape": "R2", "dream.keep_lesson": "R2",  # 0.8.16: across days; a line in your how-to-help-me note
    # R3
    "setting.message_affecting": "R3",
    # ALWAYS, besides everything in GUARDED
    "money.spend": "ALWAYS", "install.any": "ALWAYS", "protected.edit": "ALWAYS",
}  # fmt: skip
PRIORS = {"R0": (9.0, 1.0), "R1": (4.0, 2.0), "R2": (2.0, 4.0), "R3": (1.0, 9.0)}
IMPACT = {"R0": 0.25, "R1": 1.0, "R2": 2.0, "R3": 4.0}
THRESH = {"R0": 0.5, "R1": 0.75, "R2": 0.9, "R3": 0.97}
LABELS = {
    "R0": "reversible and inward", "R1": "reversible, about your things", "R2": "reversible but noticeable",
    "R3": "hard to reverse", "ALWAYS": "always asks",
}  # fmt: skip


def classify(action: str, ai_class: str | None = None) -> str:
    """The class of this action: from the table (GUARDED ones and anything unknown are ALWAYS); the AI's `ai_class` can
    only make it higher."""
    base = "ALWAYS" if action in GUARDED else CLASSES.get(action, "ALWAYS")
    if ai_class in ORDER and ORDER.index(ai_class) > ORDER.index(base):
        return ai_class
    return base


def always(action: str, never: set[str] | None = None) -> bool:
    """Does this action always ask: a guarded one, an unknown one, or one you said never for?"""
    return classify(action) == "ALWAYS" or action in (never or set())


def all_actions() -> dict[str, str]:
    """Every action Kurooto knows the class of: the table, and each guarded action as ALWAYS."""
    return {**{a: "ALWAYS" for a in GUARDED}, **CLASSES}
