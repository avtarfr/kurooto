"""Kurooto Terminal: Kurooto in a real terminal window of its own, laid out like the dashboard's terminals. One tab
each for your AI's own program (agy, Codex or Claude Code, started in your notes folder), your shell, Kurooto chat
(`kurooto ask`) and Kurooto's log, with `kurooto top` as a column beside the first tab; all in Kurooto's colours.
`kurooto term` opens it; turning this feature on adds "Kurooto Terminal" to your app menu.

    Linux, macOS   kitty: your own if you have it, or the official kitty that Set up or `kurooto term --install`
                   puts in Kurooto's folder (no admin). The shell is fish if you have it (Kurooto can get the
                   official fish too, the same way), otherwise your own.
    Windows        Windows Terminal: Kurooto adds its profiles and colours as a "fragment" (no admin). PowerShell.

Settings (terminal.*): tabs (in order: agent, shell, chat, logs, top), top ("left": a column beside the first tab;
"tab"; "off"), shell ("auto": fish if you have it, else yours; or a program, e.g. "zsh"), font_size, kitty (Linux
and macOS: off uses your usual terminal, a window per tab), default (make Kurooto Terminal your default terminal:
see defaults.py; off undoes it), default_opens (what a default-terminal launch opens on Linux: "shell", one window
with your shell in Kurooto's colours, or "layout", the whole window; on Windows it's always the shell). Turning the
feature off removes the launchers and Kurooto's Windows Terminal profiles and undoes "default terminal". Nothing
leaves this computer.
"""

from __future__ import annotations

import threading

from kurooto.core.config import register_defaults
from kurooto.modules.base import Module

register_defaults(
    "terminal",
    {
        "tabs": ["agent", "shell", "chat", "logs"],  # in order; agent = your AI's own program, when it's installed
        "top": "left",  # kurooto top: "left" (a column beside the first tab), "tab" (a tab of its own) or "off"
        "shell": "auto",  # auto: fish if you have it, otherwise your own shell (PowerShell on Windows); or a name
        "font_size": 11,
        "kitty": True,  # Linux and macOS: kitty (yours, or Kurooto's copy); off: your usual terminal, a window a tab
        "default": False,  # Kurooto Terminal as your default terminal (opt-in; turning it off undoes it)
        "default_opens": "shell",  # as the default terminal, a launch opens: "shell" (one tab) or "layout" (all)
    },
)
WATCH = ("terminal.", "brain.main", "look.palette", "you.assistant_name", "you.workspace")


class KurootoTerminal(Module):
    id = "terminal"
    title = "Kurooto Terminal"
    description = (
        "Kurooto in a terminal window of its own: your AI's program, your shell, Kurooto chat and its log, with the "
        "status board beside them, in Kurooto's colours (kitty on Linux and macOS, Windows Terminal on Windows). "
        "Adds Kurooto Terminal to your app menu; `kurooto term` opens it too."
    )
    privacy = (
        "Stays on this computer. Turning it on adds a Kurooto Terminal launcher to your app menu (and Kurooto's "
        'profiles to Windows Terminal); turning it off removes them and undoes "default terminal".'
    )

    def __init__(self, app):
        super().__init__(app)
        self._unsub = None
        self._lock = threading.Lock()
        self._last: tuple = ()
        self._stopped = True  # turned off: a sync still queued must not put the launcher back

    # ---------------------------------------------------------------------------------------------- set up
    def _plan(self):
        from kurooto.modules.terminal.plan import build

        # the Features tab asks often: find the programs, but don't run `kitty --version`
        return build(self.app.settings, self.app.paths.app, self.app.workspace, version_of=lambda exe: ())

    def ready(self):
        if self._plan().terminal:
            return True, ""
        return False, "needs a terminal program: Set up gets the official kitty into Kurooto's folder (about 45 MB)"

    def setup(self, progress=print) -> tuple[bool, str]:
        """Get kitty and fish into Kurooto's folder, from their official releases (checksums checked)."""
        from kurooto.modules.terminal.run import Context, install, missing

        ctx = Context(self.app.paths)
        keys = missing(ctx, self._plan())
        if not keys:
            return True, "Everything Kurooto Terminal uses is here."
        ok, lines = install(ctx, keys, progress)
        return ok, " ".join(lines)

    def health(self):
        from pathlib import PureWindowsPath

        from kurooto.modules.terminal import defaults

        plan = self._plan()
        if not plan.terminal:
            return False, "no terminal program (`kurooto term --install` gets kitty)"
        what = {"wt": "Windows Terminal", "console": "console windows", "terminal-app": "Terminal"}.get(
            plan.terminal, plan.terminal
        )
        shell = PureWindowsPath(plan.shell[0]).name if plan.shell else "?"
        default = ", your default terminal" if defaults.status(self.app.paths.state / "terminal") else ""
        return True, f"{what}, {len(plan.tabs)} tabs, {shell}{default}"

    # ------------------------------------------------------------------------------------------- lifecycle
    def start(self) -> None:
        with self._lock:
            self._stopped = False
        if self._unsub is None:
            from kurooto.core.events import subscribe

            self._unsub = subscribe(self._on_event)
        threading.Thread(target=self.sync, name="terminal-sync", daemon=True).start()  # PowerShell can be slow

    def stop(self) -> None:
        """Turned off: the launcher, the Windows Terminal profiles and "default terminal" go."""
        unsub, self._unsub = self._unsub, None
        if unsub:
            unsub()
        with self._lock:
            self._stopped, self._last = True, ()
            remove_everything(self.app.paths)
        super().stop()

    def _on_event(self, rec: dict) -> None:
        if rec.get("kind") == "setting_changed" and str(rec.get("key", "")).startswith(WATCH):
            threading.Thread(target=self.sync, name="terminal-sync", daemon=True).start()

    def sync(self) -> None:
        """Bring the launcher, Windows Terminal's profiles and "default terminal" in line with the settings."""
        from kurooto.modules.terminal import defaults

        with self._lock:
            if self._stopped or not self.app.is_on(self.id):
                return
            try:
                state = self.app.paths.state / "terminal"
                self._last = self.files(self.app.settings, self.app.paths, self.app.workspace, self._last)
                rec = defaults.status(state)
                want, have = bool(self.setting("default")), rec is not None
                opens = str(self.setting("default_opens") or "shell")
                moved = have and rec.get("os") == "linux" and rec.get("entry") != defaults.entry(opens)
                if want and (not have or moved):
                    from kurooto.modules.terminal.launchers import outside

                    ok, msg = defaults.apply(self._plan().os, state, *outside(), opens=opens)
                    self.app.events.emit("terminal_default", on=True, ok=ok)
                    if not ok:
                        self.app.notify(f"Kurooto Terminal couldn't become your default terminal: {msg}", why="asked")
                elif have and not want:
                    defaults.undo(state)
                    self.app.events.emit("terminal_default", on=False, ok=True)
            except Exception as e:
                self.app.events.emit("module_failed", module=self.id, error=f"{type(e).__name__}: {e}"[:300])

    @staticmethod
    def files(settings, p, workspace, last: tuple = ()) -> tuple:
        """The launcher in your app menu and, on Windows, Kurooto's profiles in Windows Terminal. The launcher is
        only made again when what it runs changed (`last`: what was made before)."""
        from kurooto.modules.terminal import launchers, look, wt
        from kurooto.modules.terminal.plan import build, kurooto_argv

        home, env = launchers.outside()
        plan = build(settings, p.app, workspace, version_of=lambda exe: ())
        cmd = kurooto_argv("term", app_dir=p.app)
        wt_exe, wt_args = None, None
        if plan.os == "windows":
            wt.write_fragment(plan, look.colours(plan.palette), home, env)
            if plan.terminal == "wt":
                wt_exe, wt_args = plan.exe, wt.args(plan, profiles=True)
        made = (plan.os, str(home), tuple(cmd), wt_exe, tuple(wt_args or ()))
        if made != last or not launchers.where(plan.os, home, env).exists():
            launchers.install(plan.os, cmd, home, env, wt=wt_exe, wt_args=wt_args)
        return made


def remove_everything(p) -> list[str]:
    """Undo everything Kurooto Terminal put outside Kurooto's own folders: "default terminal", the launcher and the
    Windows Terminal profiles (when it's turned off, and by `kurooto uninstall`)."""
    from kurooto.modules.terminal import defaults, launchers, wt
    from kurooto.modules.terminal.plan import os_name

    home, env = launchers.outside()
    done = []
    if defaults.status(p.state / "terminal"):
        done.append(defaults.undo(p.state / "terminal", home, env)[1])
    if launchers.remove(os_name(), home, env):
        done.append("Removed the Kurooto Terminal launcher.")
    if os_name() == "windows" and wt.remove_fragment(home, env):
        done.append("Removed Kurooto's Windows Terminal profiles.")
    return done
