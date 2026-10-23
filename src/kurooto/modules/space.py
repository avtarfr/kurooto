"""Space keeper: cleans off what Kurooto has piled up (old backup zips beyond a size or age limit, downloads, made zips,
big logs, old finished AI requests, the concept graph's old before-copies) so it never starts taking too much room.

Only Kurooto's own leftovers go (core/space.py lists exactly what); never your notes, files or books. Weekly, and on
request: /space shows what it would remove, /space clean does it, `kurooto space` does the same in a terminal.
"""

from __future__ import annotations

from kurooto.core import space
from kurooto.modules.base import Command, Incoming, Module


class Space(Module):
    id = "space"
    title = "Space keeper"
    description = (
        "Cleans off Kurooto's own old backups, downloads, logs and finished requests, so it never takes too much room."
    )
    privacy = "Stays on this computer. Only Kurooto's own leftovers are ever removed."

    def start(self):
        self.every("clean", self.setting("when") or "weekly sun 04:30", self.run_clean)

    def run_clean(self, payload: dict | None = None) -> dict:
        if not self.app.is_on(self.id):
            return {}
        items = space.plan(self.app)
        if not items:
            return {"freed": 0}
        out = space.clean(self.app, items)
        if out["freed"] >= 50 * 1024 * 1024:  # worth a line; small weekly tidying isn't
            self.app.notify(
                f"Space keeper: cleaned off {space.human(out['freed'])} of old backups and leftovers.",
                kind="result",
                title="Space keeper",
                why="space.cleaned",
            )
        return out

    def health(self):
        warn = space.low_disk(self.app)
        total = sum(space.footprint(self.app).values())
        return (None, warn) if warn else (True, f"Kurooto takes {space.human(total)}")

    def commands(self):
        return [Command("space", "what Kurooto takes and what can go: /space, /space clean", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        items = space.plan(self.app)
        if (arg or "").strip().lower() == "clean":
            out = space.clean(self.app, items)
            tail = f" ({out['failed']} couldn't be removed)" if out["failed"] else ""
            return f"Cleaned off {space.human(out['freed'])}{tail}."
        parts = ", ".join(f"{k}: {space.human(v)}" for k, v in space.footprint(self.app).items())
        return f"Kurooto takes {parts}.\n{space.report(items)}" + ("\n/space clean does it." if items else "")
