"""Your add-ons: your own extra features, skills, prompts and default settings from a folder of yours (for example a
private repository you cloned), laid over Kurooto when you turn this on. The add-on features appear in the dashboard
under "Your add-ons", each off until you turn it on. What the folder may hold, and how a broken add-on is kept from
stopping Kurooto: core/overlay.py. /addons lists what loaded and what didn't.

It runs the Python files in the folder's modules/ with Kurooto's access to this computer, so only use add-ons you
wrote or trust. Updates never change the folder; turning this off unloads the add-ons.
"""

from __future__ import annotations

from pathlib import Path

from kurooto.core import overlay
from kurooto.core.config import register_defaults
from kurooto.modules.base import Command, Incoming, Module

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
        return [Command("addons", "your add-ons: what loaded, and what didn't", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        st = overlay.status(self.app)
        if not st.get("path"):
            return "No add-ons loaded: " + (self.ready()[1] or "turn the feature on again")
        rows = [f"Your add-ons from {st['path']}:"]
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
