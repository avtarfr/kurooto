#!/usr/bin/env python3
"""Make Face presence's bundled impostor set (maintainer only; never at install, never on users' computers, never on
anyone's own photos): src/kurooto/data/face-impostors.npz.

    uv run --with opencv-python-headless --with numpy python tools/face_impostors.py FOLDER SFACE.onnx YUNET.onnx

FOLDER holds synthetic face images (the candidate source is SFHQ, github.com/SelfishGene/SFHQ-dataset: MIT-licensed,
made-up faces; see docs/wiki/dev/face.md for its caveats, and ship it only with the owner's OK). For each image: YuNet
finds faces (score >= 0.9, exactly one, or the image is skipped), SFace aligns and embeds it; at most one embedding per
image, up to --max (5,000). The npz holds:

    emb           M x 128, float16, unit vectors
    model_sha256  the SFace file's sha256 (load_impostors refuses a set made with another model file)
    source        a short text: where the images came from

It prints how many images were read, used and skipped, and the impostor score distribution against a random split of
the set itself (one half's centroid against the other half), so a wildly off set shows before it ships.
"""

from __future__ import annotations

import argparse
import hashlib
import random
import statistics
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from kurooto.core.biometric import dot, mean_unit, npz_write, unit  # noqa: E402

OUT = ROOT / "src" / "kurooto" / "data" / "face-impostors.npz"
IMAGES = (".jpg", ".jpeg", ".png", ".webp")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def build(
    files: Iterable[Path], detect: Callable, embed: Callable, read: Callable, limit: int = 5000
) -> tuple[list[list[float]], dict]:
    """detect(img) -> faces (each with .score); embed(img, face) -> 128 floats; read(path) -> an image or None."""
    out: list[list[float]] = []
    seen = {"read": 0, "unreadable": 0, "no face": 0, "several faces": 0}
    for f in files:
        if len(out) >= limit:
            break
        img = read(f)
        if img is None:
            seen["unreadable"] += 1
            continue
        seen["read"] += 1
        faces = [x for x in detect(img) if x.score >= 0.9]
        if not faces:
            seen["no face"] += 1
            continue
        if len(faces) > 1:
            seen["several faces"] += 1
            continue
        out.append(unit(embed(img, faces[0])))
        del img
    seen["used"] = len(out)
    return out, seen


def spread(emb: list[list[float]], seed: int = 7) -> dict:
    """One random half's centroid scored against the other half: what an impostor set looks like to a template."""
    if len(emb) < 4:
        return {}
    idx = list(range(len(emb)))
    random.Random(seed).shuffle(idx)  # noqa: S311 (a fixed seed for a repeatable split, not secrets)
    half = len(idx) // 2
    c = mean_unit([emb[i] for i in idx[:half]])
    scores = sorted(dot(emb[i], c) for i in idx[half:])
    return {
        "n": len(scores),
        "median": round(statistics.median(scores), 3),
        "p99": round(scores[int(0.99 * (len(scores) - 1))], 3),
        "max": round(scores[-1], 3),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("sface", type=Path)
    ap.add_argument("yunet", type=Path)
    ap.add_argument("--max", type=int, default=5000)
    ap.add_argument("--source", default="SFHQ synthetic faces (github.com/SelfishGene/SFHQ-dataset, MIT)")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    import cv2  # the maintainer's own environment (uv run --with opencv-python-headless)

    sys.path.insert(0, str(ROOT / "src"))
    from kurooto.modules.face.vision import opencv_detector, opencv_embedder

    det, emb = opencv_detector(a.yunet, 4), opencv_embedder(a.sface)
    files = sorted(p for p in a.folder.rglob("*") if p.suffix.lower() in IMAGES)
    rows, seen = build(
        files,
        lambda img: det.detect(img, 0.9),
        lambda img, f: emb.feature(emb.align(img, f)),
        lambda p: cv2.imread(str(p)),
        a.max,
    )
    if not rows:
        print("No faces found: nothing written.", seen)
        return 1
    npz_write(a.out, emb=rows, model_sha256=sha256(a.sface), source=a.source)
    print(f"Wrote {a.out} ({a.out.stat().st_size / 1e6:.1f} MB): {seen}")
    print("Impostor scores against a random half's centroid:", spread(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
