"""What Face presence needs on this computer, fetched only when you tap Set up (Features → Face presence → Set up), or
installed from a folder on a computer without internet (`kurooto face install-from FOLDER`):

    package (by uv or pip into <app>/voice/py-<python version>, the folder Voice uses: one numpy for both)
        vision   opencv-python-headless (Apache-2.0; the wheel bundles FFmpeg's libraries (LGPL-2.1+), OpenBLAS
                 (BSD-3), libvpx (BSD), libpng, OpenSSL and the GCC runtime (GPL-3.0 with the runtime exception))
                 and numpy (BSD-3)                                                              ~0.14 GB
    models (into <app>/face/models), from OpenCV's model zoo, pinned to one commit and checked by sha256
        yunet    face_detection_yunet_2023mar.onnx: face detection (MIT, Shiqi Yu)              0.23 MB
        sface    face_recognition_sface_2021dec.onnx: face recognition (Apache-2.0)             38.7 MB
    optional (0.8.17, into the same folder), from MediaPipe's own model store, pinned to one stored version and sha256;
    fetched only when you tap Get the eye model on the Face page (look to talk by your eyes, gaze.py)
        iris     iris_landmark.tflite: MediaPipe Iris, eye and iris landmarks (Apache-2.0)        2.64 MB

github.com/opencv/opencv_zoo/raw/... redirects to media.githubusercontent.com (Git LFS), so the files are fetched
from there directly: the host core/egress.py lists is the one that serves the bytes. The iris model is the same file
as in google/mediapipe's repository at v0.8.10 (mediapipe/modules/iris_landmark), which no longer keeps it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto.modules.voice.parts import ModelFile, Package, Parts

if TYPE_CHECKING:
    from kurooto.app import App

ZOO = "https://media.githubusercontent.com/media/opencv/opencv_zoo/48b10fa505aeb51fbd127fc60a5c660040e823b7/models"
YUNET = "face_detection_yunet_2023mar.onnx"
SFACE = "face_recognition_sface_2021dec.onnx"
SFACE_SHA = "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"
YUNET_SHA = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
IRIS = "iris_landmark.tflite"
IRIS_URL = "https://storage.googleapis.com/mediapipe-assets/iris_landmark.tflite?generation=1662065468653224"
IRIS_SHA = "d1744d2a09c25f501d39eba4faff47e53ecca8852c5ce19bce8eeac39357521f"
FEATURE = "Face presence"

FACE_PACKAGES = {
    "vision": Package(
        "vision",
        ("opencv-python-headless>=4.10,<5", "numpy>=1.26"),
        "cv2",
        0.14,
        "OpenCV (headless) and numpy: the camera, finding faces and recognising yours",
    )
}
WANTS = ["pkg:vision", "model:yunet", "model:sface"]
EYES = ["model:iris"]  # optional: Set up doesn't fetch it, the Face page's Get the eye model does


def face_models() -> dict[str, list[ModelFile]]:
    return {
        "yunet": [ModelFile(YUNET, f"{ZOO}/face_detection_yunet/{YUNET}", 0.23, YUNET_SHA)],
        "sface": [ModelFile(SFACE, f"{ZOO}/face_recognition_sface/{SFACE}", 38.7, SFACE_SHA)],
        "iris": [ModelFile(IRIS, IRIS_URL, 2.64, IRIS_SHA)],
    }


def parts(app: App) -> Parts:
    return Parts(
        app.paths.app / "voice",
        app.paths.app,
        packages=FACE_PACKAGES,
        table=face_models(),
        models_dir=app.paths.app / "face" / "models",
        feature=FEATURE,
    )
