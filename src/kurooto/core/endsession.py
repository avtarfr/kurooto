"""Windows: hear that you're signing out or shutting down, so Kurooto can say it's going offline first.

A program without a window (Kurooto runs with no console window) gets no warning when Windows ends the session: it's
just stopped. A hidden window does get one (WM_QUERYENDSESSION, then WM_ENDSESSION), so this makes one, in a thread of
its own, and calls on_end("signing out" or "shutting down") from WM_ENDSESSION. Windows waits for that (a few seconds
at most) before it ends the program.

There's one window per process (a window class can be registered only once): watch() makes it the first time and,
after that, only changes what it calls. handle() is what the window does with a message, kept apart so it can be
tested anywhere. The same window hears that the computer is about to sleep (WM_POWERBROADCAST, PBT_APMSUSPEND) for
whoever asked with on_suspend() (Reminders with the lid shut: modules/lidsafe.py).

Elsewhere this does nothing: macOS and Linux send SIGTERM (or SIGHUP), which the daemon already treats as a stop.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

WM_QUERYENDSESSION, WM_ENDSESSION = 0x0011, 0x0016
WM_POWERBROADCAST, PBT_APMSUSPEND = 0x0218, 0x0004
ENDSESSION_LOGOFF = 0x80000000
CLASS = "KurootoEndSession"

_on_end: Callable[[str], None] | None = None  # what the window calls (the latest watch())
_thread: threading.Thread | None = None
_lock = threading.Lock()
_on_suspend: list[Callable[[], None]] = []  # called when the computer is about to sleep


def watch(on_end: Callable[[str], None] | None) -> threading.Thread | None:
    """Call on_end when Windows ends the session. The window is made once per process; later calls change what it
    calls (None keeps it). Returns its thread once the window exists (None elsewhere, or if it couldn't be made)."""
    global _on_end, _thread
    if sys.platform != "win32":
        return None
    with _lock:
        if on_end is not None:
            _on_end = on_end
        if _thread is None or not _thread.is_alive():
            ready = threading.Event()
            _thread = threading.Thread(target=_run, args=(ready,), name="end-session", daemon=True)
            _thread.start()
            ready.wait(5)
        return _thread if _thread.is_alive() else None


def handle(msg: int, wparam: int, lparam: int) -> int | None:
    """What the hidden window does with a message: its result, or None for Windows' default handling."""
    if msg == WM_QUERYENDSESSION:
        return 1  # fine to end; the goodbye comes with WM_ENDSESSION
    if msg == WM_ENDSESSION:
        fn = _on_end
        if wparam and fn is not None:  # wparam 0: the session isn't ending after all
            try:
                fn("signing out" if (lparam or 0) & ENDSESSION_LOGOFF else "shutting down")
            except Exception:
                pass
        return 0
    if msg == WM_POWERBROADCAST:
        if wparam == PBT_APMSUSPEND:  # Windows allows about 2 seconds before it sleeps
            for fn in list(_on_suspend):
                try:
                    fn()
                except Exception:
                    pass
        return 1
    return None


def on_suspend(fn: Callable[[], None]) -> Callable[[], None]:
    """Windows: also call fn (from the window's thread) when the computer is about to sleep. Returns how to stop
    that. Elsewhere it does nothing."""
    if sys.platform != "win32":
        return lambda: None
    _on_suspend.append(fn)
    watch(None)
    return lambda: _on_suspend.remove(fn) if fn in _on_suspend else None


def _run(ready: threading.Event) -> None:  # pragma: no cover (Windows only; tests/unit/test_presence.py)
    try:
        _window(ready)
    finally:
        ready.set()


def _window(ready: threading.Event) -> None:  # pragma: no cover (Windows only)
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    lresult = ctypes.c_ssize_t
    wndproc_t = ctypes.WINFUNCTYPE(lresult, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", wndproc_t),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = lresult
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.restype = lresult
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE

    def proc(hwnd, msg, wparam, lparam):
        out = handle(msg, wparam, lparam)
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam) if out is None else out

    callback = wndproc_t(proc)  # kept referenced for as long as the window lives
    hinst = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSW()
    wc.lpfnWndProc = callback
    wc.hInstance = hinst
    wc.lpszClassName = CLASS
    if not user32.RegisterClassW(ctypes.byref(wc)):
        return
    hwnd = user32.CreateWindowExW(0, CLASS, "Kurooto", 0, 0, 0, 0, 0, None, None, hinst, None)  # never shown
    if not hwnd:
        return
    ready.set()
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
