"""Seeing faces: OpenCV's YuNet finds them, SFace turns each into 128 numbers, all on this computer, on the CPU.

    frame (BGR, capture size) -> downscale to 320 wide -> YuNet (score >= 0.8 watching, 0.9 enrolling; NMS 0.3)
      faces scaled back to full size -> for each big enough and good enough (blur, light):
          FaceRecognizerSF.alignCrop(frame, face) -> feature() -> L2-normalised 128 floats (in memory only)
      del frame, crops, embeddings

The interfaces below let every test run without OpenCV (fakes stand in): Detector.detect, Embedder.align / stats /
feature, Frames.size / mean / jpeg. opencv_detector() and opencv_embedder() build the real ones; cv2 is imported only
inside them (it's a part, never in Kurooto's own install).

Why a face must be found before it's embedded: SFace scores two unrelated non-face crops (noise) at a cosine of
about 0.84 against each other, so only crops YuNet accepts with a high score are ever turned into numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

DETECT_W = 320  # frames are looked at this wide (YuNet is quick there; faces at a desk are big enough)
SCORE_WATCH = 0.8
SCORE_ENROL = 0.9
SCORE_OTHER = 0.6  # a second face at this score counts as someone else in view
PREVIEW_W, PREVIEW_H, PREVIEW_Q = 320, 240, 60  # the enrolment page's preview: JPEGs made in memory, never kept


@dataclass
class Face:
    box: tuple[float, float, float, float]  # x, y, w, h in the frame's pixels
    landmarks: tuple[tuple[float, float], ...]  # right eye, left eye, nose tip, right and left mouth corners
    score: float

    @property
    def height(self) -> float:
        return float(self.box[3])


@dataclass
class Stats:
    """Of the aligned 112x112 grey crop: sharpness (variance of the Laplacian), mean light, share of blown pixels."""

    blur: float
    mean: float
    bright: float


@dataclass
class Pose:
    yaw: float  # 0 frontal; negative: turned to your left; about 0.3 is 25 degrees
    roll: float  # degrees
    pitch: float  # (nose - eyes) / (mouth - eyes): judged against your own front step, not a constant


class Detector(Protocol):
    def detect(self, frame: Any, min_score: float) -> list[Face]: ...


class Embedder(Protocol):
    def align(self, frame: Any, face: Face) -> Any: ...
    def stats(self, crop: Any) -> Stats: ...
    def feature(self, crop: Any) -> list[float]: ...


class Frames(Protocol):
    def size(self, frame: Any) -> tuple[int, int]: ...
    def mean(self, frame: Any) -> float: ...
    def jpeg(self, frame: Any) -> bytes: ...


def pose(face: Face, mirror: bool = True) -> Pose:
    """From YuNet's five landmarks. mirror=True: the preview is mirrored, so your left is on the screen's left and
    turning to your left gives a negative yaw (the camera's own picture is the other way round)."""
    (rx, ry), (lx, ly), (nx, ny), (mrx, mry), (mlx, mly) = face.landmarks[:5]
    ex, ey = (rx + lx) / 2, (ry + ly) / 2
    d = math.hypot(lx - rx, ly - ry) or 1.0
    yaw = (nx - ex) / d
    if mirror:
        yaw = -yaw
    roll = math.degrees(math.atan2(ly - ry, lx - rx))
    my = (mry + mly) / 2
    pitch = (ny - ey) / ((my - ey) or 1.0)
    return Pose(yaw, roll, pitch)


# pose()'s yaw is the nose's offset over the eyes' distance, about k * tan(angle): 0.3 at 25 degrees gives k
YAW_K = 0.3 / math.tan(math.radians(25))


def yaw_degrees(yaw: float) -> float:
    """pose()'s yaw as degrees away from facing the camera (0 to 90, the side doesn't matter); an estimate."""
    return math.degrees(math.atan(abs(float(yaw)) / YAW_K))


# (0.8.17) pose()'s pitch moves by about PITCH_K * tan(angle) when the head nods by that angle: a typical face's nose
# tip stands out from the eyes more than the mouth does (enrolment's chin up or down, 0.06 off the front: 13 degrees)
PITCH_K = 0.26


def pitch_degrees(pitch: float, front: float) -> float:
    """pose()'s pitch as degrees nodded away from `front` (your enrolment's front step), the side doesn't matter."""
    return math.degrees(math.atan(abs(float(pitch) - float(front)) / PITCH_K))


def moved(a: Face | None, b: Face | None) -> float:
    """How far the landmarks moved between two sightings, in pixels (the largest of the five)."""
    if a is None or b is None:
        return math.inf
    return max(math.hypot(x1 - x2, y1 - y2) for (x1, y1), (x2, y2) in zip(a.landmarks, b.landmarks, strict=False))


# ------------------------------------------------------------------------------------------- OpenCV's own
def _cv2():
    import cv2  # a part (modules/face/parts.py), never in Kurooto's own install

    return cv2


class CvDetector:
    def __init__(self, path: str, threads: int = 1):
        cv2 = _cv2()
        cv2.setNumThreads(threads)
        self.cv2 = cv2
        self.det = cv2.FaceDetectorYN.create(
            str(path), "", (DETECT_W, 240), SCORE_OTHER, 0.3, 50, cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_CPU
        )

    def detect(self, frame, min_score: float) -> list[Face]:
        h, w = frame.shape[:2]
        k = DETECT_W / float(w) if w > DETECT_W else 1.0
        small = self.cv2.resize(frame, (round(w * k), round(h * k))) if k != 1.0 else frame
        self.det.setInputSize((small.shape[1], small.shape[0]))
        _, rows = self.det.detect(small)
        del small
        out = []
        for r in [] if rows is None else rows:
            score = float(r[14])
            if score < min_score:
                continue
            box = tuple(float(v) / k for v in r[:4])
            lms = tuple((float(r[4 + 2 * i]) / k, float(r[5 + 2 * i]) / k) for i in range(5))
            out.append(Face(box, lms, score))  # type: ignore[arg-type]
        return out


class CvEmbedder:
    def __init__(self, path: str):
        cv2 = _cv2()
        self.cv2 = cv2
        self.rec = cv2.FaceRecognizerSF.create(str(path), "", cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_CPU)

    def align(self, frame, face: Face):
        import numpy as np

        row = np.array([*face.box, *[c for p in face.landmarks for c in p], face.score], dtype=np.float32).reshape(
            1, 15
        )
        return self.rec.alignCrop(frame, row)

    def stats(self, crop) -> Stats:
        cv2 = self.cv2
        grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur = float(cv2.Laplacian(grey, cv2.CV_64F).var())
        out = Stats(blur, float(grey.mean()), float((grey >= 250).mean()))
        del grey
        return out

    def feature(self, crop) -> list[float]:
        f = self.rec.feature(crop).flatten()
        n = float((f * f).sum()) ** 0.5 or 1.0
        out = [float(x) / n for x in f]
        del f
        return out


class CvFrames:
    def __init__(self):
        self.cv2 = _cv2()

    def size(self, frame) -> tuple[int, int]:
        return int(frame.shape[1]), int(frame.shape[0])

    def mean(self, frame) -> float:
        small = self.cv2.resize(frame, (64, 48))
        return float(small.mean())

    def jpeg(self, frame) -> bytes:
        cv2 = self.cv2
        small = cv2.resize(frame, (PREVIEW_W, PREVIEW_H))
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_Q])
        del small
        return bytes(buf) if ok else b""


def opencv_detector(path, threads: int = 1) -> CvDetector:
    return CvDetector(str(path), threads)


def opencv_embedder(path) -> CvEmbedder:
    return CvEmbedder(str(path))


def opencv_frames() -> CvFrames:
    return CvFrames()
