"""What the dashboard's Brain page shows (0.8.2): the Brain as islands of parts, with each one's switch.

`view(app)` is the JSON of GET /api/brain3d. Only plain facts: whether each part is on (its own `mind.<part>.on`), a
short state word, and counts the Brain already keeps (log records, imported past, projects in the lab, phone senses
enabled). Nothing of what a part has read or thought of you is in it: that stays in the commands (/thinking ...)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto import mind

if TYPE_CHECKING:
    from kurooto.app import App

COLORS = {
    "hq": "#9ccf5e",
    "body": "#e08a8a",
    "senses": "#7fb4d6",
    "memory": "#a99be0",
    "fore": "#e0b04f",
    "shop": "#6fcf9f",
    "cons": "#e0905a",
    "mirror": "#d98ac9",
}
SHADOW = {"forecast", "autonomy", "read"}  # start in shadow mode: they watch and score themselves first
PHONE = ("screen", "charging", "motion", "steps", "light", "places", "headphones", "dnd", "alarm", "wifi", "usage")

# island id, name, what it is, then its parts: (id, name, setting, what it does)
ISLANDS = [
    (
        "hq",
        "Headquarters",
        "what's on its mind now",
        [
            (
                "workspace",
                "Workspace",
                "mind.workspace.on",
                "Parts compete for the spotlight; only winners may act unasked.",
            ),
            ("attention", "Attention schema", "mind.attention.on", "A model of its own attention."),
            ("beliefs", "Beliefs", "mind.beliefs.on", "Every belief keeps its source."),
        ],
    ),
    (
        "fore",
        "Foresight",
        "read, forecast, plans",
        [
            ("read", "Read of your days", "mind.read.on", "Watches numbers about your days."),
            (
                "forecast",
                "Forecast",
                "mind.forecast.on",
                "21:00: what it expects of tomorrow, scored the next evening.",
            ),
            ("plans", "Week plans", "mind.plans.on", "A suggestion for the week, never a push."),
            ("harness", "Hidden harness", "mind.harness.on", "Measures how it does on tasks it has never seen."),
        ],
    ),
    (
        "cons",
        "Conscience",
        "promises, gate, limits",
        [
            ("promises", "Promises", "mind.promises.on", "What it said it would do, and whether it did."),
            ("gate", "Outbound gate", "mind.gate.on", "Everything that reaches you passes here."),
            ("autonomy", "Autonomy", "mind.autonomy.on", "Decides what it may do unasked, from your reactions."),
            ("stops", "Stops", "", "A stop freezes the drive; stopping is fine."),
            ("precedents", "Precedents", "mind.precedents.on", "Value conflicts asked once, then followed."),
        ],
    ),
    (
        "memory",
        "Memory vaults",
        "log, journal, story, past",
        [
            ("log", "Mind log", "", "Append-only, hash-chained; only the scorekeeper writes."),
            (
                "journal",
                "Journal",
                "mind.journal.on",
                "Its own states, reasons and mistakes, each checked against the log.",
            ),
            ("story", "Life story", "mind.story.on", "One autobiography every part reads first."),
            ("forget", "Forgetting", "mind.forget.on", "Old things fade; a forget goes everywhere."),
            ("history", "The past (import)", "mind.backfill.on", "Brain fed what Kurooto kept before it was on."),
        ],
    ),
    (
        "mirror",
        "Mirror",
        "model of you",
        [
            ("tom", "Model of you", "mind.tom.on", "What you know, want and prefer, each with its source."),
            ("tone", "Message tone", "mind.tone.on", "One word per message, with the local model only."),
            ("deep", "Deep-work hold", "mind.tom.attention", "Holds a message while you are deep in something."),
        ],
    ),
    (
        "senses",
        "Senses",
        "machine, activity, phone",
        [
            ("intero", "Machine", "mind.senses.intero", "Its own body: temperature, memory, disk."),
            (
                "activity",
                "Your activity",
                "mind.senses.activity",
                "The app in front, hashed titles, saves and commits. Never keystrokes.",
            ),
            ("phone", "Phone sensors", "", "Each sensor its own switch; sealed on the phone."),
        ],
    ),
    (
        "shop",
        "Workshop",
        "lab, skills, self-improvement",
        [
            ("lab", "Research lab", "mind.lab.on", "Pre-registered overnight experiments on projects you list."),
            (
                "improve",
                "Self-improvement",
                "mind.improve.on",
                "Changes only through the hidden harness and your say-so.",
            ),
            ("skills", "Skills", "mind.skills.on", "Solved tasks become tested skills; each starts by asking."),
            ("finetune", "Weekly fine-tune", "mind.finetune.on", "A local fine-tune on checked examples."),
            ("play", "Play", "mind.play.on", "A little nightly time on its own questions."),
        ],
    ),
    (
        "body",
        "Body",
        "budget, drive, feelings",
        [
            ("budget", "Body budget", "mind.budget.on", "Its own load, limits and setpoints."),
            ("feelings", "Feelings", "mind.feelings.on", "Computed states about specific items."),
            ("heartbeat", "Heartbeat", "mind.heartbeat.on", "What is not guaranteed while this computer is down."),
        ],
    ),
]


def _metrics(app: App, cid: str, st: dict) -> list[list[str]]:
    s = app.settings
    if cid == "log":
        return [["Records", f"{st.get('records', 0):,}"], ["Head", f"#{st.get('head', 0)}"]]
    if cid == "history":
        try:
            from kurooto.mind import history

            return [["Imported", f"{history.status(app)['imported']:,}"], ["Source", "event history"]]
        except Exception:
            return []
    if cid == "phone":
        n = sum(1 for p in PHONE if s.get(f"mind.senses.phone.{p}"))
        return [["Sensors enabled", f"{n} of {len(PHONE)}"]]
    if cid == "lab":
        return [["Projects", str(len(s.get("mind.lab.projects") or []))]]
    if cid in SHADOW:
        return [["Mode", "shadow (watches and scores itself)"]]
    return []


def view(app: App) -> dict:
    on = mind.on(app)
    try:
        st = mind.connect(app).state() if on else {}
    except Exception:
        st = {}
    islands, parts_on, total = [], 0, 0
    for iid, name, tag, parts in ISLANDS:
        comps = []
        for cid, cname, key, desc in parts:
            if cid == "phone":
                live = on and any(app.settings.get(f"mind.senses.phone.{p}") for p in PHONE)
                key = "mind.senses.phone.*"
            elif key:
                live = on and bool(app.settings.get(key))
            else:
                live = on  # the log and stops are always there with Brain
            word = "off" if not live else ("shadow" if cid in SHADOW else "on")
            comps.append(
                [
                    cid,
                    cname,
                    1 if live else 0,
                    word,
                    _metrics(app, cid, st) if live else [],
                    key or "(always with Brain)",
                    desc,
                ]
            )
            total += 1
            parts_on += 1 if live else 0
        islands.append({"id": iid, "n": name, "t": tag, "color": COLORS[iid], "comps": comps})
    return {
        "on": on,
        "islands": islands,
        "parts_on": parts_on,
        "parts_total": total,
        "records": int(st.get("records", 0) or 0),
        "mode": "shadow: forecast, autonomy, read" if on else "",
    }
