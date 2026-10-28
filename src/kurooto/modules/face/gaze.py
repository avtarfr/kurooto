"""Where your eyes look (0.8.17, voice.listen.look_gaze): look to talk by your eyes on the camera, not only by your
head's turn. YuNet's five points say where the head points; the iris says where the eyes do.

    the owner's face in a frame (YuNet's points in the full frame's pixels: detection runs on a small copy, the eyes
    are cut from the frame as it came, so a sharper camera gives sharper eyes)
      -> each eye: a square EYE_CROP x the eyes' distance around YuNet's eye point, turned level (the eyes' roll) and
         scaled to 64x64 in one warpAffine; the picture's left eye (your right one) mirrored, as MediaPipe does
      -> iris_landmark.tflite (MediaPipe Iris, Apache-2.0) through OpenCV's dnn: 71 eye-contour and brow points and
         5 iris points, about 2 ms an eye on a laptop's CPU
      -> offset(): the iris centre along the line between the eye's corners (contour points 0 and 8), h: -1 at the
         picture's left corner, 1 at its right; across that line, v: down positive, in eye widths. An eye open less
         than OPEN_MIN of its width (a blink) gives nothing.
      -> Eyes(h, v): the mean of the eyes read
      del the crops (nothing is kept: two numbers a frame, in memory)

    angles(): degrees from the camera's lens, against your calibration (your eyes and head while you looked at it):
        head   yaw: atan(yaw / YAW_K), less the calibration's; pitch: atan((pitch - the calibration's) / PITCH_K)
        eyes   asin(h / EYE_H) and asin(v / EYE_V), each less the calibration's
        gaze = head + eyes (sideways: your left negative, as pose() gives the yaw; up and down: down positive), so a
        head turned a little with the eyes back on the lens is looking at it, and a head facing it with the eyes on
        the screen below isn't.
      EYE_H, EYE_V: an eyeball's radius (about 12 mm) over half the eye's width (about 15 mm), and over its whole
      width. Estimates: the calibration's zero point and the tolerances (look_gaze_yaw_deg, look_gaze_pitch_deg)
      absorb what they get wrong.

Calibration (the Face page, Calibrate my eyes): CAL_S seconds of frames of you (recognised, alone, facing it) looking
at the lens; the medians of h, v, yaw and pitch, how many frames and when, go into your sealed template (Template.gaze).
Never a frame, a crop or a point. Without one, look to talk goes by the head's turn, and says so.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Protocol

from kurooto.modules.face.vision import PITCH_K, YAW_K, Face

INPUT = 64  # the model's eye picture: 64x64, RGB in 0..1
OUTS = ("output_eyes_contours_and_brows", "output_iris")
EYE_CROP = 1.0  # the eye's square: this many times the distance between YuNet's eye points (MediaPipe: 2.3 eye widths)
MIN_EYES_PX = 12.0  # eyes closer together than this (in the frame's pixels) are too small to read
OPEN_MIN = 0.12  # an eye open less than this share of its width is blinking: no reading
EYE_H, EYE_V = 0.8, 0.4  # how far the iris moves at 90 degrees: in half eye widths (h), in eye widths (v)
CAL_S = 3.0  # calibration: this long of good frames
CAL_MIN = 8  # and at least this many
CAL_MAX_S = 15.0  # no calibration within this long from the first frame: it ends and says why
CAL_YAW = 0.2  # calibrating: the head turned at most this (pose yaw, about 17 degrees) from the camera
CAL_SPREAD = 0.2  # the eyes' h wandered more than this (median absolute deviation): look at the lens and try again
NUMBERS = ("h", "v", "yaw", "pitch")


@dataclass
class Eyes:
    h: float  # the iris along the eye: -1 the picture's left corner, 1 its right
    v: float  # across: down positive, in eye widths
    n: int = 2  # how many eyes were read


class Gazer(Protocol):
    def eyes(self, frame: Any, face: Face) -> Eyes | None: ...


def offset(contour, iris) -> tuple[float, float, float] | None:
    """(h, v, open) for one eye from its contour (at least 16 points (x, y): 0 and 8 the corners, 4 and 12 the lids'
    middles) and its iris centre, all in one picture's coordinates; None when the corners coincide."""
    (x0, y0), (x8, y8) = contour[0], contour[8]
    if x8 < x0:  # left to right in the picture
        (x0, y0), (x8, y8) = (x8, y8), (x0, y0)
    w = math.hypot(x8 - x0, y8 - y0)
    if w < 1e-6:
        return None
    ux, uy = (x8 - x0) / w, (y8 - y0) / w
    cx, cy = iris
    t = ((cx - x0) * ux + (cy - y0) * uy) / w
    mx, my = (x0 + x8) / 2, (y0 + y8) / 2
    v = ((cx - mx) * -uy + (cy - my) * ux) / w  # the normal (-uy, ux) points down when the eye is level
    (ax, ay), (bx, by) = contour[4], contour[12]
    return 2 * t - 1, v, math.hypot(ax - bx, ay - by) / w


def eyes_of(readings: list[tuple[float, float, float] | None]) -> Eyes | None:
    """The mean of the open eyes' (h, v); None when none was read."""
    ok = [r for r in readings if r is not None and r[2] >= OPEN_MIN]
    if not ok:
        return None
    return Eyes(sum(r[0] for r in ok) / len(ok), sum(r[1] for r in ok) / len(ok), len(ok))


def _eye_deg(x: float, reach: float) -> float:
    return math.degrees(math.asin(max(-1.0, min(1.0, float(x) / reach))))


def angles(h: float, v: float, yaw: float, pitch: float, cal: dict) -> tuple[float, float]:
    """(sideways, up-down) degrees from the lens: the head's turn and the eyes' together, against the calibration.
    yaw as pose() gives it (mirrored: your left negative); h and v from the camera's own picture."""
    head_h = math.degrees(math.atan(float(yaw) / YAW_K)) - math.degrees(math.atan(float(cal["yaw"]) / YAW_K))
    head_v = math.degrees(math.atan((float(pitch) - float(cal["pitch"])) / PITCH_K))
    # the picture isn't mirrored: the iris moving to its right (h up) is your eyes turning to your left
    eye_h = -(_eye_deg(h, EYE_H) - _eye_deg(cal["h"], EYE_H))
    eye_v = _eye_deg(v, EYE_V) - _eye_deg(cal["v"], EYE_V)
    return head_h + eye_h, head_v + eye_v


def valid(cal) -> bool:
    """A calibration with its four numbers."""
    try:
        return isinstance(cal, dict) and all(math.isfinite(float(cal[k])) for k in NUMBERS)
    except (KeyError, TypeError, ValueError):
        return False


class Calibration:
    """CAL_S seconds (and CAL_MIN frames) of your eyes and head while you look at the lens: their medians. Frames
    without a reading (no face, a blink, turned away) count for nothing and reset nothing."""

    def __init__(self):
        self.rows: list[tuple[float, float, float, float]] = []
        self.first: float | None = None

    def feed(self, eyes: Eyes, yaw: float, pitch: float, now: float) -> None:
        if self.first is None:
            self.first = now
        self.rows.append((float(eyes.h), float(eyes.v), float(yaw), float(pitch)))

    def share(self, now: float) -> float:
        """How far along it is, 0..1."""
        if self.first is None:
            return 0.0
        return round(min(1.0, (now - self.first) / CAL_S, len(self.rows) / CAL_MIN), 2)

    def done(self, now: float) -> bool:
        return self.first is not None and (self.share(now) >= 1.0 or now - self.first >= CAL_MAX_S)

    def result(self, at: float) -> dict | str:
        """The numbers kept (four medians, the frame count and the time), or why there are none."""
        if len(self.rows) < CAL_MIN:
            return "Not enough clear frames of your eyes: more light on your face, then try again."
        hs = [r[0] for r in self.rows]
        mid = statistics.median(hs)
        if statistics.median(abs(x - mid) for x in hs) > CAL_SPREAD:
            return "Your eyes moved about: look at the camera's lens the whole time, then try again."
        out = {k: round(statistics.median(r[i] for r in self.rows), 4) for i, k in enumerate(NUMBERS)}
        return {**out, "n": len(self.rows), "at": round(at)}


# ------------------------------------------------------------------------------------------- OpenCV's own
class CvGazer:
    def __init__(self, path: str):
        import cv2  # a part (modules/face/parts.py), never in Kurooto's own install

        self.cv2 = cv2
        self.net = cv2.dnn.readNetFromTFLite(str(path))

    def _eye(self, frame, cx: float, cy: float, side: float, ang: float, flip: bool):
        import numpy as np

        cv2 = self.cv2
        n = max(INPUT, round(side))  # cut at the frame's own sharpness, then shrunk evenly (INTER_AREA) to 64x64
        s, c, sn = side / n, math.cos(ang), math.sin(ang)
        f = -1.0 if flip else 1.0
        half = n / 2
        # the cut's (u, v) -> the frame's (x, y): around the eye, turned by the roll, mirrored for one eye
        m = np.array(
            [[s * f * c, -s * sn, cx - half * (s * f * c) + half * s * sn],
             [s * f * sn, s * c, cy - half * (s * f * sn) - half * s * c]],
            dtype=np.float64,
        )  # fmt: skip
        cut = cv2.warpAffine(
            frame, m, (n, n), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE
        )
        crop = cv2.resize(cut, (INPUT, INPUT), interpolation=cv2.INTER_AREA) if n != INPUT else cut
        del cut
        blob = cv2.dnn.blobFromImage(crop, 1 / 255.0, (INPUT, INPUT), 0, swapRB=True)
        del crop
        self.net.setInput(blob)
        cont, iris = self.net.forward(list(OUTS))
        del blob
        pts = [(float(x), float(y)) for x, y, _z in cont.reshape(-1, 3)[:16]]
        ic = (float(iris.reshape(-1, 3)[0][0]), float(iris.reshape(-1, 3)[0][1]))
        if flip:  # back to the picture's own left and right
            pts = [(INPUT - x, y) for x, y in pts]
            ic = (INPUT - ic[0], ic[1])
        return offset(pts, ic)

    def eyes(self, frame, face: Face) -> Eyes | None:
        (rx, ry), (lx, ly) = face.landmarks[:2]
        d = math.hypot(lx - rx, ly - ry)
        if d < MIN_EYES_PX:
            return None
        ang = math.atan2(ly - ry, lx - rx)
        side = EYE_CROP * d
        return eyes_of([self._eye(frame, rx, ry, side, ang, True), self._eye(frame, lx, ly, side, ang, False)])


def opencv_gazer(path) -> CvGazer:
    return CvGazer(str(path))
