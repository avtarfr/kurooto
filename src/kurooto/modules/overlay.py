"""Your add-ons: your own extra features, skills, prompts and default settings from a folder of yours (for example a
private repository you cloned), laid over Kurooto when you turn this on. The add-on features appear in the dashboard
under "Your add-ons", each off until you turn it on. What the folder may hold, and how a broken add-on is kept from
stopping Kurooto: core/overlay.py. /addons lists what loaded and what didn't, and the official add-ons with Add
buttons (core/official.py; /addons official lists only those).

It runs the Python files in the folder's modules/ with Kurooto's access to this computer, so only use add-ons you
wrote or trust. Updates never change the folder; turning this off unloads the add-ons.
"""

from __future__ import annotations

from pathlib import Path

from kurooto.core import overlay
from kurooto.core.config import register_defaults
from kurooto.modules.base import Answer, Command, Incoming, Module

register_defaults(
    "overlay",
    {
        "path": "",  # your add-ons folder (full path)
        "code": True,  # also run the Python add-ons in its modules/ (False: only skills, prompts and settings)
    },
)


class AddOns(Module):
    id = "overlay"
    title = "Your add-ons"
    description = "Your own extra features, skills and prompts from a folder of yours, e.g. a private repository."
    privacy = (
        "Runs the Python code in that folder's modules/ inside Kurooto, with its access to this computer: only use "
        "add-ons you wrote or trust. Nothing is sent anywhere by this feature itself."
    )

    def folder(self) -> Path | None:
        raw = self.setting("path") or ""
        return Path(raw).expanduser() if raw else None

    def ready(self):
        f = self.folder()
        if not f:
            return False, "name your add-ons folder (Set up)"
        if not f.is_absolute() or not f.is_dir():
            return False, f"there's no folder {f}"
        if overlay.inside_kurooto(self.app, f):
            return False, "the add-ons folder can't be inside Kurooto's own folders (updates replace those)"
        return True, ""

    def start(self):
        st = overlay.status(self.app)
        if st.get("path") != str(self.folder() or ""):  # turned on (or moved) while running: load them now
            overlay.unload(self.app)
            overlay.load(self.app)

    def stop(self):
        overlay.unload(self.app)
        super().stop()

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        st = overlay.status(self.app)
        n = len(st.get("modules") or [])
        what = f"{n} add-on feature{'s' if n != 1 else ''}"
        what += "".join(f", {k}" for k in ("skills", "prompts") if overlay.dirs(self.app, k))
        what += ", settings" if st.get("settings") else ""
        errs = st.get("errors") or []
        if errs:
            return False, f"{what}; {len(errs)} problem(s): " + "; ".join(
                f"{e['where']}: {e['error']}" for e in errs[-3:]
            )
        return True, f"{what} from {st.get('path')}"

    # --------------------------------------------------------------------------------------------- setup
    def setup_form(self) -> dict:
        return {
            "intro": "Paste the full path of your add-ons folder (for example a private repository of yours you "
            "cloned). It may hold modules/ (Python features), skills/, prompts/ and settings.json. The Python files "
            "run inside Kurooto with its access to this computer: only use add-ons you wrote or trust.",
            "links": [],
            "fields": [{"name": "path", "label": "Add-ons folder", "type": "text", "placeholder": "full path"}],
        }

    def configure(self, values: dict) -> dict:
        raw = str(values.get("path", "")).strip().strip('"')
        f = Path(raw).expanduser() if raw else None
        if not f or not f.is_absolute():
            return {"ok": False, "message": "Paste the folder's full path."}
        if not f.is_dir():
            return {"ok": False, "message": f"There's no folder {f}."}
        if overlay.inside_kurooto(self.app, f):
            return {"ok": False, "message": "Pick a folder outside Kurooto's own folders (updates replace those)."}
        self.app.settings.set("overlay.path", str(f))
        if self.app.is_on(self.id):
            overlay.unload(self.app)
            overlay.load(self.app)
        return {"ok": True, "message": f"Your add-ons come from {f}."}

    # ------------------------------------------------------------------------------------------ telegram
    def commands(self):
        return [
            Command(
                "addons",
                "your add-ons (your folder's and those added by link): what loaded, what didn't; the official ones "
                "with Add buttons (/addons official: just those)",
                self._cmd,
            )
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        from kurooto.core import official

        head = "Official add-ons (each pinned to one commit; you read its card before anything is added):"
        listed = [head, *official.lines(self.app.paths)]
        tap = official.buttons(self.app.paths) or None  # Add, Update: the card comes first (core/official.py)
        if arg.strip().lower() == "official":
            return Answer("\n".join(listed), tap)
        return Answer(self._text() + "\n\n" + "\n".join(listed), tap)

    def _text(self) -> str:
        st = overlay.status(self.app)
        linked = self.linked_lines()
        if not st.get("path"):
            return "\n".join([*linked, "", "No add-ons folder loaded: " + (self.ready()[1] or "turn it on again")])
        rows = [*linked, ""] if linked else []
        rows.append(f"Your add-ons from {st['path']}:")
        for mid in st.get("modules") or []:
            m = self.app.modules.get(mid)
            if m:
                rows.append(f"• {m.title or mid} ({'on' if self.app.is_on(mid) else 'off'})")
        for k in ("skills", "prompts"):
            if overlay.dirs(self.app, k):
                rows.append(f"• {k}/")
        if st.get("settings"):
            rows.append("• settings.json (defaults under yours)")
        for e in (st.get("errors") or [])[-5:]:
            rows.append(f"Problem: {e['where']}: {e['error']}")
        return "\n".join(rows)

    def linked_lines(self) -> list[str]:
        """The add-ons by link (core/addons.py), for /addons: each with its features, or why it didn't load."""
        linked = overlay.status(self.app).get("linked") or {}
        if not linked:
            return ["No add-ons by link (kurooto addons add <git url> on your computer, or the dashboard)."]
        rows = ["Added by link:"]
        for name, row in sorted(linked.items()):
            if row.get("problem"):
                rows.append(f"• {name}: didn't load: {row['problem']}")
                continue
            feats = [
                f"{m.title or mid} ({'on' if self.app.is_on(mid) else 'off'})"
                for mid in row.get("modules") or []
                if (m := self.app.modules.get(mid))
            ]
            off = " (official)" if self._official(name, row) else ""
            rows.append(f"• {name}{off} at {str(row.get('commit', ''))[:12]}: {', '.join(feats) or 'no features'}")
        return rows

    def _official(self, name: str, row: dict) -> bool:
        from kurooto.core import addons, official

        rec = addons.installed(self.app.paths).get(name) or {}
        return official.match(rec.get("url", ""), rec.get("commit", ""), name) is not None
