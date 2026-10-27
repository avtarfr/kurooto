"""This computer's camera, through OpenCV, on Linux (V4L2), Windows (Media Foundation, then DirectShow) and macOS
(AVFoundation). It fails safely: no camera, a camera another program holds, or one the system blocks gives a reason
and no picture; every capture error closes and releases it.

    Linux    cv2.VideoCapture(i, CAP_V4L2). Cameras come from /sys/class/video4linux/video*/name; infrared ones
             ("IR", "Infrared") are skipped, and so are metadata nodes (a node that gives no frame). face.camera.device
             takes a number or part of a name. Busy: another process has /dev/videoN open (/proc/*/fd); V4L2 streams to
             one program at a time, which is why Face presence keeps the camera closed while you type.
    Windows  CAP_MSMF, then CAP_DSHOW; by number. Busy: the system's camera-use record (CapabilityAccessManager's
             webcam keys) shows an app still using it. Blocked: Settings → Privacy & security → Camera → "Let desktop
             apps access your camera" off shows up as a camera that opens but gives no frames.
    macOS    CAP_AVFOUNDATION. Several apps share a camera there, so Kurooto never blocks one, and there's no public
             way to tell it's busy; a camera that won't open counts as busy. Kurooto's Python needs the Camera
             permission; a background program may never be asked, so `kurooto face test-camera` from a terminal once
             brings the system's question up.

Frames stay in memory. Nothing here writes a picture anywhere.
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

V4L = Path("/sys/class/video4linux")
NO_FRAME_S = 2.0  # opened, but nothing came this long: blocked (a permission) or not a real camera
IR = re.compile(r"\b(ir|infrared)\b", re.I)

BLOCKED_WIN = 'Settings → Privacy & security → Camera → "Let desktop apps access your camera"'
BLOCKED_MAC = (
    "System Settings → Privacy & Security → Camera; allow the app that started Kurooto (Terminal or Kurooto's own "
    "launcher), or run `kurooto face test-camera` in a terminal once"
)


@dataclass
class Device:
    index: int
    name: str
    node: str = ""  # /dev/videoN on Linux


class CameraError(Exception):
    """why: one of "no camera", "busy", "blocked" (said in words by the module)."""

    def __init__(self, why: str, detail: str = ""):
        super().__init__(detail or why)
        self.why, self.detail = why, detail


def devices(platform: str | None = None, root: Path = V4L) -> list[Device]:
    """The ordinary cameras: on Linux by name (infrared ones left out); elsewhere the first few numbers."""
    platform = platform or sys.platform
    if not platform.startswith("linux"):
        return [Device(i, f"camera {i}") for i in range(3)]
    out = []
    for d in sorted(root.glob("video*"), key=lambda p: int(re.sub(r"\D", "", p.name) or 0)):
        try:
            name = (d / "name").read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if IR.search(name):
            continue
        idx = int(re.sub(r"\D", "", d.name) or 0)
        out.append(Device(idx, name, f"/dev/{d.name}"))
    return out


def pick(devs: list[Device], want: str) -> list[Device]:
    """face.camera.device: empty = in order; a number = that one; text = the cameras whose name holds it."""
    want = str(want or "").strip()
    if not want:
        return devs
    if want.isdigit():
        hit = [d for d in devs if d.index == int(want)]
        return hit or [Device(int(want), f"camera {want}", f"/dev/video{want}")]
    return [d for d in devs if want.lower() in d.name.lower()]


def holders(node: str, proc: Path = Path("/proc"), me: int | None = None) -> list[int]:
    """Linux: the processes (not this one) with this camera node open."""
    me = os.getpid() if me is None else me
    real = os.path.realpath(node)
    out = []
    for p in proc.iterdir() if proc.is_dir() else []:
        if not p.name.isdigit() or int(p.name) == me:
            continue
        try:
            for fd in (p / "fd").iterdir():
                try:
                    if os.readlink(fd) in (node, real):
                        out.append(int(p.name))
                        break
                except OSError:
                    continue
        except OSError:
            continue
    return out


def windows_busy() -> bool:
    """Windows: an app is using the camera now (its LastUsedTimeStop is 0), other than this Python."""
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return False
    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"
    me = Path(sys.executable).name.lower()

    def scan(path: str) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(k, i)
                    except OSError:
                        return False
                    i += 1
                    if sub == "NonPackaged" or me in sub.lower():
                        continue
                    try:
                        with winreg.OpenKey(k, sub) as s:
                            stop, _ = winreg.QueryValueEx(s, "LastUsedTimeStop")
                            if int(stop) == 0:
                                return True
                    except OSError:
                        continue
        except OSError:
            return False

    return scan(base + r"\NonPackaged") or scan(base)


class Camera:
    """One open camera. open() raises CameraError; read() gives a fresh frame or None; close() always releases."""

    def __init__(self, device: str = "", width: int = 640, height: int = 480, platform: str | None = None):
        self.want, self.width, self.height = device, int(width), int(height)
        self.platform = platform or sys.platform
        self.cap = None
        self.dev: Device | None = None
        self._last_frame = 0.0

    def busy(self) -> bool:
        """Is another program using it? (Linux: an open handle; Windows: the system's record; macOS: can't tell.)"""
        try:
            if self.platform.startswith("linux"):
                return any(holders(d.node) for d in pick(devices(self.platform), self.want) if d.node)
            if self.platform == "win32":
                return windows_busy()
        except Exception:
            return False
        return False

    def open(self) -> None:
        import cv2  # a part (modules/face/parts.py)

        devs = pick(devices(self.platform), self.want)
        if not devs:
            raise CameraError("no camera")
        if self.platform.startswith("linux"):
            if any(holders(d.node) for d in devs if d.node):
                raise CameraError("busy")
            backends = [cv2.CAP_V4L2]
        elif self.platform == "win32":
            if windows_busy():
                raise CameraError("busy")
            backends = [cv2.CAP_MSMF, cv2.CAP_DSHOW]
        else:
            backends = [cv2.CAP_AVFOUNDATION]
        opened_any = False
        for d in devs:
            for be in backends:
                cap = cv2.VideoCapture(d.index, be)
                if not cap.isOpened():
                    cap.release()
                    continue
                opened_any = True
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # reads are fresh
                except Exception:
                    pass
                end = time.monotonic() + NO_FRAME_S
                got = False
                while time.monotonic() < end:
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        got = True
                        del frame
                        break
                    time.sleep(0.05)
                if got:
                    self.cap, self.dev, self._last_frame = cap, d, time.monotonic()
                    return
                cap.release()  # a metadata node, or a camera the system blocks
        if not opened_any:
            raise CameraError("busy" if self.platform == "darwin" else "no camera")
        raise CameraError("blocked", BLOCKED_WIN if self.platform == "win32" else BLOCKED_MAC)

    def read(self):
        """A fresh frame (one grab first, so it isn't a stale buffered one), or None. An error closes the camera."""
        if self.cap is None:
            return None
        try:
            self.cap.grab()
            ok, frame = self.cap.read()
        except Exception:
            self.close()
            return None
        if not ok or frame is None:
            if time.monotonic() - self._last_frame > NO_FRAME_S:
                self.close()
            return None
        self._last_frame = time.monotonic()
        return frame

    def is_open(self) -> bool:
        return self.cap is not None

    def close(self) -> None:
        cap, self.cap = self.cap, None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
