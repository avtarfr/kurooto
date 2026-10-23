"""Keep or drop: what you actually use of each feature, counted on this computer, and now and then the question
whether to keep it.

Counted per feature and day (state/keep.json, days kept 90; and when each was last used): plain-English requests it
answered at once, its /commands, taps on its messages' buttons, its tools used on a call, and your replies to its
messages. The setup page's try-it box doesn't count. Nothing leaves the computer.

Day 10 after Kurooto started counting (a new install: from its first start; an update: from the version that brought
this), once setup is done: one message with each feature that's on, its use in those 10 days and the messages it sent
by itself (from Calm's records), and Keep / Quiet / Off per feature. Quiet: it keeps working, but what it sends by
itself stops (its kinds go on Calm's own stop list, notify.calm.stopped); Off: the feature is turned off the usual way
(App.disable). Both through Calm, with its Undo. Keep (or Quiet): not asked about again for 90 days. Then, checked
daily and at most once a month: features that are on, unused for 60 days and still running scheduled jobs get the
same question. Nothing is turned down without a tap.

keep.ask (on) turns the questions off; /keep shows the counts any time (/keep 60: the last 60 days), /keep <feature>
its line with the buttons. Telegram, the channel these come on, is never asked about.
"""

from __future__ import annotations

import datetime as dt
import threading
from typing import TYPE_CHECKING

from kurooto.core.calm import ASKED, REASONS, Change
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.base import Module

register_defaults("keep", {"ask": True})  # day 10, then monthly: Keep / Quiet / Off for features you don't use
FIRST_DAYS, UNUSED_DAYS, MONTH_DAYS, AGAIN_DAYS, KEEP_DAYS = 10, 60, 30, 90, 90
HOW = {"intent": "request", "command": "command", "button": "button", "tool": "call tool", "reply": "reply"}
PLURAL = {"reply": "replies"}
NEVER = ("telegram",)  # the channel the question comes on
MAX_ROWS = 15  # features with buttons in one message (Telegram allows about a hundred buttons)


def _title(m: Module) -> str:
    return m.title.split(" (")[0]


def _n(n: int, word: str) -> str:
    return f"{n} {word if n == 1 else PLURAL.get(word, word + 's')}"


class Keep:
    def __init__(self, app: App):
        self.app = app
        self.file = app.paths.state / "keep.json"
        self._lock = threading.Lock()

    def state(self) -> dict:
        return jload(self.file, {}) or {}

    # --------------------------------------------------------------------------------------- counting
    def used(self, module: str, how: str, via: str = "") -> None:
        """You used this feature: one request, command, button, call tool or reply."""
        if not module or via == "setup":
            return
        t = now()
        try:
            with self._lock:
                st = self.state()
                day = st.setdefault("used", {}).setdefault(module, {}).setdefault(t.date().isoformat(), {})
                day[how] = int(day.get(how) or 0) + 1
                st.setdefault("last", {})[module] = t.timestamp()
                jsave(self.file, st)
        except Exception as e:  # counting never gets in the way of what you asked
            self.app.events.emit("keep_failed", error=f"{type(e).__name__}: {e}"[:200])

    def intent_owner(self, name: str, mods: list[Module]) -> str:
        """The feature whose instant request this is (one picked by an add-on's classifier, or taught)."""
        for m in mods:
            try:
                if any(i.name == name for i in m.intents()):
                    return m.id
            except Exception as e:  # one feature's mistake never stops the count
                self.app.events.emit("keep_failed", error=f"{m.id}: {e}"[:200])
        return ""

    def tool_owner(self, name: str) -> str:
        """The feature a call tool belongs to (Phone calls for its own and the shared ones)."""
        for m in self.app.enabled():
            fn = getattr(m, "call_tools", None)
            if m.id == "calls" or fn is None:
                continue
            try:
                if any(t.name == name for t in fn()):
                    return m.id
            except Exception as e:
                self.app.events.emit("keep_failed", error=f"{m.id}: {e}"[:200])
        return "calls"

    def counts(self, days: int, end: dt.datetime | None = None) -> dict[str, dict[str, int]]:
        """Per feature, its uses by kind in the `days` days before `end` (now)."""
        end = end or now()
        first = (end - dt.timedelta(days=days)).date().isoformat()
        out: dict[str, dict[str, int]] = {}
        for mid, by_day in (self.state().get("used") or {}).items():
            for day, hows in by_day.items():
                if first <= day <= end.date().isoformat():
                    tot = out.setdefault(mid, {})
                    for how, n in hows.items():
                        tot[how] = tot.get(how, 0) + int(n or 0)
        return out

    def sent_by(self, since: float) -> dict[str, int]:
        try:
            return self.app.calm.sent_by(since)
        except Exception as e:
            self.app.events.emit("keep_failed", error=f"messages: {e}"[:200])
            return {}

    # ---------------------------------------------------------------------------------------- the lines
    def features(self) -> list[Module]:
        return [m for m in self.app.enabled() if m.id not in NEVER]

    def line(self, m: Module, use: dict[str, int], sent: int) -> str:
        total = sum(use.values())
        parts = [_n(use[h], w) for h, w in HOW.items() if use.get(h)]
        said = f"used {_n(total, 'time')} ({', '.join(parts)})" if total else "not used"
        if sent:
            said += f"; {_n(sent, 'message')} by itself"
        return f"- {_title(m)}: {said}"

    def quiet_change(self, m: Module) -> Change | None:
        """Quiet: what this feature sends by itself goes on Calm's stop list (None: nothing of it left to quiet)."""
        if not self.app.calm.on():
            return None
        stopped = list(self.app.settings.get("notify.calm.stopped") or [])
        ids = [r.id for r in REASONS.values() if r.owner == m.id and not r.exempt and r.stop is not None]
        new = [i for i in ids if i not in stopped]
        if not new:
            return None
        return Change(
            f"{_title(m)} keeps working but stops messaging you", key="notify.calm.stopped", value=[*stopped, *new]
        )

    def can_off(self, m: Module) -> bool:
        return self.app.is_on(m.id) and not any(m.id in o.requires for o in self.app.enabled())

    def row(self, m: Module) -> list | None:
        """[Keep] [Quiet] [Off] for one feature (only the ones that can do something)."""
        row = [(f"{_title(m)[:20]}: Keep", f"keep:{m.id}:keep")]
        if self.quiet_change(m) is not None:
            row.append(("Quiet", f"keep:{m.id}:quiet"))
        if self.can_off(m):
            row.append(("Off", f"keep:{m.id}:off"))
        return row if len(row) > 1 else None

    def _ask(self, head: str, mods: list[Module], days: int, since: float) -> int:
        use, sent = self.counts(days), self.sent_by(since)
        mods = sorted(mods, key=lambda m: (sum(use.get(m.id, {}).values()), -sent.get(m.id, 0), m.title))
        rows = [r for r in (self.row(m) for m in mods) if r][:MAX_ROWS]
        if not rows:
            return 0
        lines = [head, *(self.line(m, use.get(m.id, {}), sent.get(m.id, 0)) for m in mods)]
        lines.append(
            "Keep, Quiet (it keeps working but stops messaging you) or Off; Undo puts either back. Nothing changes "
            "unless you tap. /keep shows the counts any time."
        )
        self.app.notify("\n".join(lines), kind="question", title="Keep or drop", why="keep.ask", buttons=rows)
        self.app.events.emit("keep_asked", features=len(rows))
        return len(rows)

    # ---------------------------------------------------------------------------------------- the questions
    def start(self) -> None:
        with self._lock:
            st = self.state()
            if not st.get("since"):  # counting starts now: day 10 is from here
                st["since"] = now().timestamp()
                jsave(self.file, st)
        sch = self.app.scheduler
        sch.action("keep.tick", lambda p: self.tick())
        sch.every("keep:tick", "daily 12:00", "keep.tick", module="keep", respect="quiet")

    def tick(self) -> str:
        """Daily: the day-10 question, or the monthly one when it's due. Returns which it asked ("" for none)."""
        t = now().timestamp()
        with self._lock:
            st = self.state()
            since = float(st.get("since") or t)
            st.setdefault("since", since)
            for by_day in (st.get("used") or {}).values():  # days older than KEEP_DAYS go
                cut = (now() - dt.timedelta(days=KEEP_DAYS)).date().isoformat()
                for day in [d for d in by_day if d < cut]:
                    by_day.pop(day)
            jsave(self.file, st)
        if not self.app.settings.get("setup.done"):
            return ""
        if not st.get("first") and t - since >= FIRST_DAYS * 86400:
            self._mark("first", t)
            if self.app.settings.get("keep.ask") and self._ask(
                "Ten days in: what you used of each feature that's on, and what it sent by itself.",
                self.features(),
                FIRST_DAYS,
                since,
            ):
                return "first"
            return ""
        if not self.app.settings.get("keep.ask") or t - since < UNUSED_DAYS * 86400:
            return ""
        if t - float(st.get("monthly_at") or 0) < MONTH_DAYS * 86400:
            return ""
        idle = self.idle()
        if idle and self._ask(
            f"Not used in {UNUSED_DAYS} days, but still running on a schedule:",
            idle,
            UNUSED_DAYS,
            t - UNUSED_DAYS * 86400,
        ):
            self._mark("monthly_at", t)
            return "monthly"
        return ""

    def idle(self) -> list[Module]:
        """Features that are on, unused for UNUSED_DAYS, with recurring jobs, not kept in the last AGAIN_DAYS."""
        st, t = self.state(), now().timestamp()
        last, answered = st.get("last") or {}, st.get("answered") or {}
        out = []
        for m in self.features():
            if t - float(last.get(m.id) or 0) < UNUSED_DAYS * 86400:
                continue
            if t - float(answered.get(m.id) or 0) < AGAIN_DAYS * 86400:
                continue
            if any(j.kind == "recurring" for j in self.app.scheduler.jobs(f"{m.id}:")):
                out.append(m)
        return out

    def _mark(self, key: str, value, module: str = "") -> None:
        with self._lock:
            st = self.state()
            if module:
                st.setdefault(key, {})[module] = value
            else:
                st[key] = value
            jsave(self.file, st)

    # ------------------------------------------------------------------------------------------- buttons
    def button(self, ref: str, act: str) -> str:
        """keep:<feature>:keep|quiet|off. Quiet and Off go through Calm, with its Undo."""
        m = self.app.modules.get(ref)
        if m is None:
            return "That feature isn't here any more."
        if act == "keep":
            self._mark("answered", now().timestamp(), m.id)
            self.app.events.emit("keep_answer", module=m.id, answer="keep")
            return f"OK, {_title(m)} stays as it is."[:190]
        if act == "quiet":
            c = self.quiet_change(m)
            if c is None:
                return f"{_title(m)} is already quiet."[:190]
        elif act == "off":
            if not self.app.is_on(m.id):
                return f"{_title(m)} is already off."[:190]
            c = Change(f"turns off {_title(m)}", module=m.id)
        else:
            return "That button is from an older version."
        ok, said, uid = self.app.calm.apply(c, why="keep.ask")
        if not ok:
            return said[:190]
        self._mark("answered", now().timestamp(), m.id)
        self.app.events.emit("keep_answer", module=m.id, answer=act)
        self.app.notify(f"Done: {said}.", kind="info", why=ASKED, buttons=[[("Undo", f"calm:{uid}:undo")]])
        return f"Done: {said}."[:190]

    # ------------------------------------------------------------------------------------------- /keep
    def command(self, arg: str = "") -> tuple[str, list | None]:
        """/keep: the last 30 days per feature that's on; /keep 60: other days; /keep <feature>: its line, buttons."""
        a = arg.strip().lower()
        days = int(a) if a.isdigit() and 1 <= int(a) <= KEEP_DAYS else 30
        st = self.state()
        since = float(st.get("since") or now().timestamp())
        if a and not a.isdigit():
            m = next(
                (x for x in self.features() if a in (x.id, x.id.replace("_", " ")) or _title(x).lower().startswith(a)),
                None,
            )
            if m is None:
                return f'No feature that\'s on is called "{a}". /keep lists them.', None
            use, sent = self.counts(days).get(m.id, {}), self.sent_by(now().timestamp() - days * 86400).get(m.id, 0)
            row = self.row(m)
            return f"In the last {days} days:\n{self.line(m, use, sent)}", [row] if row else None
        use, sent = self.counts(days), self.sent_by(now().timestamp() - days * 86400)
        mods = sorted(self.features(), key=lambda m: (-sum(use.get(m.id, {}).values()), m.title))
        if not mods:
            return "No features are on.", None
        lines = [f"What you used in the last {days} days (counted since {dt.datetime.fromtimestamp(since):%a %d %b}):"]
        lines += [self.line(m, use.get(m.id, {}), sent.get(m.id, 0)) for m in mods]
        lines.append("/keep <feature> offers Quiet and Off for one; /keep 60 counts 60 days.")
        return "\n".join(lines), None
