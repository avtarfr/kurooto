"""Desktop helpers: small things around Kurooto's alarm and messages on a desktop computer.

    the alarm rings      your phone rings through KDE Connect too (handy when it's on silent in another room), and
                         the screen wakes up (Hyprland, Sway or X11), so the morning page is there when you sit down
    a message comes      a short KDE Connect ping to your phone for the kinds you pick (a deadline, a reminder):
                         only "Kurooto: deadline", never the message itself
    /findphone           rings your phone now

It only starts kdeconnect-cli, hyprctl, swaymsg and xset, as its card says, and sends nothing on the internet:
KDE Connect talks to your phone over your own network.
"""

from __future__ import annotations

import os
import sys
import threading

from kurooto.core import events, proc
from kurooto.core.config import register_defaults
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "desktop_helpers",
    {
        "phone": "",  # your phone's KDE Connect name or id (empty: the first one KDE Connect can reach)
        "ring_on_alarm": True,  # ring the phone through KDE Connect when Kurooto's alarm rings
        "wake_screen_on_alarm": True,  # wake the screen when the alarm rings (Hyprland, Sway or X11)
        "ping_kinds": [],  # kinds of Kurooto's messages that also ping the phone, e.g. ["deadline", "reminder"]
    },
)

KINDS = ("info", "result", "reminder", "deadline", "question", "approval")


class DesktopHelpers(Module):
    id = "desktop_helpers"
    title = "Desktop helpers"
    description = "Rings your phone through KDE Connect and wakes the screen at the alarm; pings for chosen messages."
    privacy = "Talks to your phone through KDE Connect on your own network; nothing goes on the internet."

    def __init__(self, app):
        super().__init__(app)
        self._off = None

    def kde(self) -> str | None:
        return proc.which("kdeconnect-cli")

    def screen_cmd(self) -> list[str] | None:
        """How to wake the screen in this session, or None."""
        if sys.platform != "linux":
            return None
        env = os.environ
        if env.get("HYPRLAND_INSTANCE_SIGNATURE") and proc.which("hyprctl"):
            return ["hyprctl", "dispatch", "dpms", "on"]
        if env.get("SWAYSOCK") and proc.which("swaymsg"):
            return ["swaymsg", "output * power on"]
        if env.get("DISPLAY") and proc.which("xset"):
            return ["xset", "dpms", "force", "on"]
        return None

    def ready(self):
        if not self.kde() and not self.screen_cmd():
            return False, "install KDE Connect (kdeconnect-cli), or run a Hyprland, Sway or X11 session"
        return True, ""

    def start(self):
        if self._off is None:
            self._off = events.subscribe(self._event)

    def stop(self):
        self.shutdown()
        super().stop()

    def shutdown(self):  # Kurooto is stopping: stop listening
        if self._off is not None:
            self._off()
            self._off = None

    # ------------------------------------------------------------------------------------------------ work
    def _event(self, rec: dict) -> None:
        kind = rec.get("kind")
        if kind == "alarm_rang":
            threading.Thread(target=self.alarm, name="desktop-helpers", daemon=True).start()
        elif kind == "notified" and rec.get("subkind") in (self.setting("ping_kinds") or []):
            threading.Thread(target=self.ping, args=(str(rec.get("subkind")),), daemon=True).start()

    def device(self) -> list[str]:
        """kdeconnect-cli's arguments for your phone: -n name, -d id, or the first reachable one."""
        want = str(self.setting("phone") or "").strip()
        exe = self.kde()
        if not exe:
            return []
        r = proc.run([exe, "-a", "--id-name-only"], timeout=15)
        rows = [ln.split(" ", 1) for ln in (r.out or "").splitlines() if ln.strip()] if r.ok else []
        for row in rows:
            if want and want in (row[0], row[1] if len(row) > 1 else ""):
                return ["-d", row[0]]
        return ["-d", rows[0][0]] if rows and not want else []

    def ring(self) -> tuple[bool, str]:
        exe = self.kde()
        if not exe:
            return False, "KDE Connect isn't installed (kdeconnect-cli)"
        dev = self.device()
        if not dev:
            return False, "KDE Connect can't reach your phone (is it on the same network and paired?)"
        r = proc.run([exe, *dev, "--ring"], timeout=15)
        return r.ok, "Ringing your phone." if r.ok else f"KDE Connect didn't ring it: {(r.err or r.out)[:150]}"

    def ping(self, kind: str) -> bool:
        exe, dev = self.kde(), self.device()
        if not exe or not dev:
            return False
        return proc.run([exe, *dev, "--ping-msg", f"Kurooto: {kind}"], timeout=15).ok

    def wake(self) -> bool:
        cmd = self.screen_cmd()
        return bool(cmd) and proc.run(cmd, timeout=10).ok

    def alarm(self) -> None:
        if self.setting("wake_screen_on_alarm"):
            self.wake()
        if self.setting("ring_on_alarm"):
            ok, why = self.ring()
            self.app.events.emit("desktop_helpers_ring", ok=ok)

    # ------------------------------------------------------------------------------------------ commands
    def commands(self):
        return [Command("findphone", "ring your phone through KDE Connect", self._find)]

    def _find(self, msg: Incoming, arg: str) -> str:
        return self.ring()[1]

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        parts = []
        if self.kde():
            parts.append("KDE Connect")
        if self.screen_cmd():
            parts.append("screen wake")
        return True, " and ".join(parts)
