"""Windows: hear that you're signing out or shutting down, so Kurooto can say it's going offline first.

A program without a window (Kurooto runs with no console window) gets no warning when Windows ends the session: it's
just stopped. A hidden window does get one (WM_QUERYENDSESSION, then WM_ENDSESSION), so this makes one, in a thread of
its own, and calls on_end("signing out" or "shutting down") from WM_ENDSESSION. Windows waits for that (a few seconds
at most) before it ends the program.

Elsewhere this does nothing: macOS and Linux send SIGTERM (or SIGHUP), which the daemon already treats as a stop.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

WM_QUERYENDSESSION, WM_ENDSESSION = 0x0011, 0x0016
ENDSESSION_LOGOFF = 0x80000000
CLASS = "KurootoEndSession"


def watch(on_end: Callable[[str], None]) -> threading.Thread | None:
    if sys.platform != "win32":
        return None
    t = threading.Thread(target=_run, args=(on_end,), name="end-session", daemon=True)
    t.start()
    return t


def _run(on_end: Callable[[str], None]) -> None:  # pragma: no cover (Windows only; tests/unit/test_presence.py)
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

    said = []

    def proc(hwnd, msg, wparam, lparam):
        if msg == WM_QUERYENDSESSION:
            return 1  # fine to end; the goodbye comes with WM_ENDSESSION
        if msg == WM_ENDSESSION:
            if wparam and not said:
                said.append(1)
                try:
                    on_end("signing out" if (lparam or 0) & ENDSESSION_LOGOFF else "shutting down")
                except Exception:
                    pass
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

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
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
