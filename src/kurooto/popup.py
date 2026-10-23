"""`kurooto ask --popup`: a small window to type one request in; the answer shows in the window (Enter sends, Esc
closes). Tk, from Python's standard library; nothing to install where Python has it.

The hotkey that opens it is set in your system, bound to the command `kurooto ask --popup` (dashboard → Settings →
Quick ask shows the exact command for this computer): Windows, a shortcut key on a Start-menu link
(`kurooto ask --shortcut` makes one); macOS, a Shortcuts shortcut with a keyboard shortcut; Linux, your desktop's
keyboard settings (GNOME, KDE, Hyprland's or sway's config). Wayland lets no program grab a key for itself, so
Kurooto doesn't pretend to: your desktop runs the command when you press the key.
"""

from __future__ import annotations

import queue
import sys
import threading
from collections.abc import Callable

WIDTH, HEIGHT = 560, 260


class Asker:
    """What the window does, apart from the window: send one request, then the answer (or why there's none).
    say(text) -> the running Kurooto's reply dict or None; wait(job, minutes) -> (ok, answer)."""

    def __init__(self, say: Callable, wait: Callable, minutes: int = 10):
        self.say, self.wait, self.minutes = say, wait, minutes

    def ask(self, text: str, progress: Callable[[str], None] = lambda s: None) -> str:
        text = text.strip()
        if not text:
            return ""
        r = self.say(text)
        if r is None:
            return "Kurooto isn't running, or didn't take that (`kurooto on` starts it)."
        if not r.get("job"):
            return "\n".join(r.get("replies") or []) or "Done."
        progress("Working on it…")
        ok, answer = self.wait(r["job"], self.minutes)
        if ok is None:
            return f"Still going; the answer comes on your phone too (kurooto ask --job {r['job']})."
        return answer or ("Done." if ok else "It didn't work.")


def run(minutes: int = 10) -> int:
    """Open the window; returns when it's closed."""
    try:
        import tkinter as tk
    except ImportError:
        print(
            "This Python has no Tk, so there's no window. `kurooto ask` asks in a terminal instead (on Linux, the "
            "python3-tk / tk package adds Tk).",
            file=sys.stderr,
        )
        return 2
    from kurooto.cli import say, wait_job

    try:
        root = tk.Tk()
    except tk.TclError as e:
        print(f"No window can open here ({e}). `kurooto ask` asks in a terminal instead.", file=sys.stderr)
        return 2
    build(root, Asker(say, wait_job, minutes))
    root.mainloop()
    return 0


def build(root, asker: Asker) -> dict:
    """The window's parts on a Tk root: a line to type in, the answer below. Returns them (and send()), for tests."""
    import tkinter as tk

    results: queue.Queue = queue.Queue()
    root.title("Kurooto")
    root.attributes("-topmost", True)
    x = (root.winfo_screenwidth() - WIDTH) // 2
    y = max(0, (root.winfo_screenheight() - HEIGHT) // 3)
    root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
    root.minsize(360, 160)
    frame = tk.Frame(root, padx=12, pady=12)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text="Ask Kurooto (Enter sends, Esc closes)", anchor="w").pack(fill="x")
    entry = tk.Entry(frame, font=("TkDefaultFont", 13))
    entry.pack(fill="x", pady=(4, 8))
    out = tk.Text(frame, wrap="word", height=6, relief="flat", borderwidth=0, font=("TkDefaultFont", 11))
    out.pack(fill="both", expand=True)
    out.configure(state="disabled")

    def show(text: str) -> None:
        out.configure(state="normal")
        out.delete("1.0", "end")
        out.insert("1.0", text)
        out.configure(state="disabled")

    def send(_event=None) -> None:
        text = entry.get().strip()
        if not text:
            return
        entry.delete(0, "end")
        show("…")

        def work() -> None:
            results.put(asker.ask(text, results.put))

        threading.Thread(target=work, daemon=True).start()

    def poll() -> None:
        try:
            while True:
                show(results.get_nowait())
        except queue.Empty:
            pass
        root.after(100, poll)

    entry.bind("<Return>", send)
    root.bind("<Escape>", lambda e: root.destroy())
    root.after(100, poll)
    root.after(50, lambda: (root.focus_force(), entry.focus_set()))
    return {"entry": entry, "out": out, "send": send}
