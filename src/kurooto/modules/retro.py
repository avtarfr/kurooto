"""Nightly look back: once a day the AI reads how the day went (what you answered, ignored, moved or snoozed) and
proposes at most three small changes to your settings, each with Approve / Skip. Nothing changes without your tap,
and it can only touch the settings in TUNABLE (times and thresholds), never anything else."""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from collections import Counter

from kurooto import providers
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Module

register_defaults("retro", {"when": "daily 23:50", "max_proposals": 3})
TUNABLE = {
    "checkins.times.evening": "time HH:MM or null",
    "checkins.times.midday": "time HH:MM or null",
    "availability.night.from": "time HH:MM",
    "availability.night.to": "time HH:MM",
    "deadlines.ping_h": "hours before a deadline for the first nudge (number)",
    "deadlines.urgent_h": "hours before a deadline for the urgent nudge (number)",
    "quiz.per_session": "questions per quiz session (number)",
    "capture.delay_min": "minutes after class before asking (number)",
}
PROMPT = """You help a personal assistant adapt to its user. Below is what happened today (counts of events) and the
current values of the settings you may change. Propose at most {n} small changes that would clearly help, or none.
Reply with JSON only: {{"proposals": [{{"key": "<one of the keys>", "value": <new value>, "why": "<one sentence>"}}]}}

Settings you may change (key: meaning = current value):
{settings}

Today's events (kind: count):
{events}
"""


class Retro(Module):
    id = "retro"
    heavy = True  # waits for the charger on battery (saver mode, core/power.py)
    title = "Nightly look back"
    description = "Once a day the AI suggests small changes to your settings from how the day went; you approve each."
    requires = ("telegram", "chat")
    privacy = "Counts of what happened today and your settings go to the AI you picked; never your messages."

    def start(self):
        self.every("nightly", self.setting("when") or "daily 23:50", lambda p: self.run())

    def run(self) -> int:
        brain = providers.build(self.app, self.app.settings.get("brain.main") or "")
        if not brain or not brain.available()[0]:
            return 0
        since = now() - dt.timedelta(hours=24)
        counts = Counter(e["kind"] for e in self.app.events.tail(5000) if e.get("ts", "") >= since.isoformat())
        settings = "\n".join(f"{k}: {v} = {json.dumps(self.app.settings.get(k))}" for k, v in TUNABLE.items())
        events = "\n".join(f"{k}: {n}" for k, n in counts.most_common(40)) or "(nothing happened)"
        r = brain.complete(
            PROMPT.format(n=self.setting("max_proposals") or 3, settings=settings, events=events),
            effort="medium",
            timeout=300,
        )
        m = re.search(r"\{.*\}", r.text or "", re.S)
        try:
            props = json.loads(m[0]).get("proposals", []) if m else []
        except ValueError:
            props = []
        store = jload(self.app.paths.state / "retro.json", {}) or {}
        sent = 0
        for p in props[: self.setting("max_proposals") or 3]:
            key, value = p.get("key"), p.get("value")
            if key not in TUNABLE or not self._valid(key, value):
                continue
            pid = uuid.uuid4().hex[:8]
            store[pid] = {"key": key, "value": value, "why": str(p.get("why", ""))[:300], "at": now().isoformat()}
            self.app.notify(
                f"Suggestion: set {key} to {json.dumps(value)} (now {json.dumps(self.app.settings.get(key))}).\n"
                f"{store[pid]['why']}",
                kind="approval",
                buttons=[[("Approve", f"retro:{pid}:yes"), ("Skip", f"retro:{pid}:no")]],
            )
            sent += 1
        jsave(self.app.paths.state / "retro.json", dict(list(store.items())[-100:]))
        self.app.events.emit("retro_ran", proposals=sent)
        return sent

    @staticmethod
    def _valid(key: str, value) -> bool:
        if "time HH:MM" in TUNABLE[key]:
            return (value is None and "null" in TUNABLE[key]) or (
                isinstance(value, str) and bool(re.fullmatch(r"\d{2}:\d{2}", value))
            )
        return isinstance(value, (int, float)) and 0 < value < 1000

    def callbacks(self):
        return {"retro": self._decide}

    def _decide(self, pid: str, act: str) -> str:
        store = jload(self.app.paths.state / "retro.json", {}) or {}
        p = store.pop(pid, None)
        jsave(self.app.paths.state / "retro.json", store)
        if not p:
            return "That suggestion is gone."
        if act != "yes":
            self.app.events.emit("retro_skipped", key=p["key"])
            return "Skipped."
        self.app.settings.set(p["key"], p["value"])
        self.app.events.emit("retro_applied", key=p["key"])
        return f"Done: {p['key']} = {json.dumps(p['value'])}."
