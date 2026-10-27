"""Make the being's anatomy (0.8.9, static/being.js): a brain, its deep structures, a heart, the cerebrum's volume.

Run once by hand; the result is checked in at src/kurooto/web/static/body/anatomy.bin (the dashboard never runs this):

    uv run --no-project --with numpy --with scikit-image python tools/gen_body_meshes.py

Everything is made from signed-distance shapes here, so nothing of anyone else's scan or model is in it. The shape
follows human anatomy in proportion (1 unit = 100 mm; x right, y up, z front): two hemispheres split by the
longitudinal fissure, the lateral (Sylvian) fissure above a temporal lobe, the central sulcus, a flattened base, the
cerebellum with folia, the brainstem. The folds are a narrow-band Gaussian random field (sum of random plane waves at
a gyral wavelength of about 17 mm): its level sets make the labyrinth of gyri and sulci a real cortex has. Grey matter
is the pial surface; white matter is the same field 2.5 mm inside, so its gyral cores follow the folds. Each vertex is
labelled with its region (lobe or structure), which the dashboard maps to Kurooto's parts.

File: b"KBM1", a uint32 JSON header length, the JSON header ({meshes: [{name, verts, tris, scale, off}]}), then per mesh
int16 positions (x, y, z quantised to scale), uint32 triangle indices, uint8 region per vertex.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np
from skimage import measure

RNG = np.random.default_rng(20261027)
REGIONS = [
    "prefrontal",  # 0 Foresight
    "orbitofrontal",  # 1 Conscience
    "precentral",  # 2 Conscience (action)
    "parietal",  # 3 Senses (touch)
    "occipital",  # 4 Senses (vision)
    "temporal",  # 5 Memory
    "tpj",  # 6 Mirror (temporoparietal junction)
    "cerebellum",  # 7 Workshop
    "brainstem",  # 8 Body
    "thalamus",  # 9 Headquarters
    "callosum",  # 10 Headquarters (white matter bridge)
    "hippocampus",  # 11 Memory
    "ventricle",  # 12
    "caudate",  # 13 Workshop (habits)
    "insula",  # 14 Body
    "heart",  # 15
    "body",  # 16
]


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def ellipsoid(x, y, z, c, r):
    """Approximate signed distance to an ellipsoid (good near the surface)."""
    px, py, pz = (x - c[0]) / r[0], (y - c[1]) / r[1], (z - c[2]) / r[2]
    k0 = np.sqrt(px * px + py * py + pz * pz)
    k1 = np.sqrt((px / r[0]) ** 2 + (py / r[1]) ** 2 + (pz / r[2]) ** 2)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def waves(x, y, z, n, wavelength, seed):
    """A narrow-band Gaussian random field, std about 1: n plane waves at one wavelength, random directions, phases."""
    rng = np.random.default_rng(seed)
    k = 2 * np.pi / wavelength
    f = np.zeros_like(x)
    for _ in range(n):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        f += np.cos(k * (d[0] * x + d[1] * y + d[2] * z) + rng.uniform(0, 2 * np.pi))
    return f * np.sqrt(2.0 / n)


def grid(lo, hi, step):
    axes = [np.arange(lo[i], hi[i] + step, step, dtype=np.float32) for i in range(3)]
    x, y, z = np.meshgrid(*axes, indexing="ij")
    return x, y, z, axes


def hemisphere_shape(x, y, z, s):
    """One hemisphere without folds: one cerebrum shape (narrower and lower at the front, highest over the parietal
    lobe, a blunt occipital pole), a temporal lobe hanging below the front half with its pole forward, a flat base and
    a flat medial face."""
    cx = s * 0.335
    zz = np.clip(z, -1.2, 1.2)
    # the outline seen from the side: taller toward the back, a little narrower at the front
    ry = 0.43 + 0.05 * np.tanh(-zz * 2.0) - 0.06 * np.clip(zz - 0.45, 0, 1) * 4
    rx = 0.33 - 0.05 * np.clip(zz - 0.30, 0, 1) * 2 - 0.03 * np.clip(-zz - 0.55, 0, 1) * 2
    yc = 0.10 + 0.02 * np.tanh(-zz * 2.0)
    px, py, pz = (x - cx) / rx, (y - yc) / ry, (z + 0.04) / 0.82
    k = np.sqrt(px * px + py * py + pz * pz)
    d = (k - 1.0) * np.minimum(np.minimum(rx, ry), 0.82)
    temporal = ellipsoid(x, y, z, (s * 0.44, -0.24, 0.04), (0.205, 0.18, 0.44))
    d = smin(d, temporal, 0.025)  # small blend: a crease stays where the Sylvian fissure runs
    d = smax(d, -(x * s - 0.014), 0.012)  # the medial face: the longitudinal fissure between the hemispheres
    d = smax(d, -(y + 0.36 + 0.06 * np.clip(-z, 0, 1)), 0.04)  # the flat base
    tent = ellipsoid(x, y, z, (0, -0.44, -0.60), (0.62, 0.20, 0.34))  # room for the cerebellum (the tentorium)
    d = smax(d, -tent, 0.05)
    return d


def fissures(x, y, z, s):
    """Depth to carve along the lateral (Sylvian) fissure and the central sulcus (both > 0 where they cut)."""
    sy = (y + 0.10) - 0.20 * np.clip(-(z - 0.25), -0.3, 1.3)  # rises toward the back
    syl = (
        np.exp(-((sy / 0.018) ** 2))
        * np.clip((0.42 - z) / 0.15, 0, 1)
        * np.clip((z + 0.40) / 0.15, 0, 1)
        * (np.abs(x) > 0.22)
    )
    cz = z - (0.04 + 0.16 * np.clip((y - 0.15) / 0.40, -1, 1)) - 0.025 * np.sin(16 * y + 1)
    cen = np.exp(-((cz / 0.013) ** 2)) * (y > -0.05 + 0.2 * (1 - np.abs(x) / 0.4) * 0)
    return syl * 0.11, cen * 0.075


def cerebrum(step):
    lo, hi = (-0.78, -0.72, -1.02), (0.78, 0.66, 0.92)
    x, y, z, axes = grid(lo, hi, step)
    d = np.minimum(hemisphere_shape(x, y, z, 1), hemisphere_shape(x, y, z, -1))
    # folds: a warped narrow-band field, gyri about 17 mm across; crowns rounded, sulci narrow and deep
    w = 0.05 * waves(x, y, z, 6, 0.9, 7)
    g = waves(x + w, y + w * 0.7, z - w * 0.5, 40, 0.17, 11)
    # sulci along the field's zero lines (they make the labyrinth a cortex has): narrow, deep grooves; gyri between
    tent = ellipsoid(x, y, z, (0, -0.44, -0.60), (0.62, 0.20, 0.34))
    fade = np.clip((tent - 0.01) / 0.10, 0, 1) * np.clip((y + 0.40) / 0.08, 0, 1)  # flatter under, over the cerebellum
    d = d + fade * (-0.012 + 0.075 * np.exp(-((g / 0.42) ** 2)))
    syl, cen = (np.zeros_like(x), np.zeros_like(x))
    for s in (1, -1):
        a, b = fissures(x, y, z, s)
        syl += a * (np.sign(x) == s)
        cen += b * (np.sign(x) == s)
    d = d + syl + cen
    return d, axes, (x, y, z)


def cerebellum_sdf(step):
    lo, hi = (-0.66, -0.82, -1.00), (0.66, -0.18, -0.25)
    x, y, z, axes = grid(lo, hi, step)
    d = smin(ellipsoid(x, y, z, (0.24, -0.46, -0.56), (0.30, 0.19, 0.27)),
             ellipsoid(x, y, z, (-0.24, -0.46, -0.56), (0.30, 0.19, 0.27)), 0.07)  # fmt: skip
    d = smin(d, ellipsoid(x, y, z, (0, -0.44, -0.60), (0.10, 0.17, 0.25)), 0.04)  # the vermis
    d = smax(d, y + 0.31 - 0.20 * (z + 0.6), 0.03)  # its flat top, under the occipital lobe
    # folia: thin parallel folds running across, following the angle around the cerebellum's centre
    rr = np.sqrt(x * x * 0.35 + (y - 0.10) ** 2 + (z + 0.05) ** 2)  # shells around a point above and in front of it
    folia = 0.009 * np.tanh(2.2 * np.sin(2 * np.pi * rr / 0.028 + 0.5 * np.sin(x * 6)))
    return d - folia, axes, (x, y, z)


def brainstem_sdf(step):
    lo, hi = (-0.2, -1.25, -0.55), (0.2, -0.05, 0.12)
    x, y, z, axes = grid(lo, hi, step)
    t = np.clip((y + 0.15) / -0.85, 0, 1.3)  # 0 at the midbrain, 1 at the end of the medulla
    cz = -0.12 - 0.20 * t
    r = (
        0.115 - 0.040 * np.minimum(t, 1) - 0.03 * np.clip(t - 1, 0, 1) * 3 + 0.055 * np.exp(-(((t - 0.38) / 0.12) ** 2))
    )  # the pons bulges forward
    d = np.sqrt((x / 1.15) ** 2 + (z - cz - 0.02 * np.exp(-(((t - 0.38) / 0.12) ** 2))) ** 2) - r
    d = np.maximum(d, -(y + 1.18))
    d = np.maximum(d, y + 0.12)
    return d, axes, (x, y, z)


def deep_sdf(step):
    """Thalamus, corpus callosum, lateral ventricles, hippocampus, caudate: labelled separately."""
    lo, hi = (-0.62, -0.45, -0.70), (0.62, 0.40, 0.60)
    x, y, z, axes = grid(lo, hi, step)
    th = np.minimum(ellipsoid(x, y, z, (0.08, -0.02, -0.08), (0.07, 0.06, 0.13)),
                    ellipsoid(x, y, z, (-0.08, -0.02, -0.08), (0.07, 0.06, 0.13)))  # fmt: skip
    # corpus callosum: an arch over the ventricles, thick at the splenium (back) and the genu (front)
    ang = np.arctan2(y - 0.02, z + 0.04)
    rad = np.sqrt((y - 0.02) ** 2 + (z + 0.04) ** 2)
    thick = 0.030 + 0.020 * (np.cos(ang) ** 8) + 0.012 * np.exp(-(((ang - 3.0) / 0.4) ** 2))
    cc = np.maximum(np.abs(rad - 0.30) - thick, np.abs(x) - 0.30 * np.sqrt(np.clip(np.sin(ang), 0, 1)) - 0.04)
    cc = np.maximum(cc, -(y - 0.05 - 0.0 * z))
    hip = 9 * np.ones_like(x)
    for s in (1, -1):
        a = np.clip((z + 0.30) / 0.55, 0, 1)
        hx, hy = s * (0.27 + 0.03 * a), -0.22 + 0.08 * (1 - a) ** 2
        hip = np.minimum(hip, np.sqrt((x - hx) ** 2 + (y - hy) ** 2) - 0.035 + 0.006 * np.sin(z * 70)
                         + 9 * ((z < -0.32) | (z > 0.25)))  # fmt: skip
    cd = 9 * np.ones_like(x)
    for s in (1, -1):
        cd = np.minimum(cd, ellipsoid(x, y, z, (s * 0.13, 0.12, 0.18), (0.05, 0.06, 0.16)))
    return {"thalamus": th, "callosum": cc, "hippocampus": hip, "caudate": cd}, axes, (x, y, z)


def heart_sdf(step):
    """A heart, apex down and to the left: two ventricles, two atria, the aortic arch, the pulmonary trunk, cavae."""
    lo, hi = (-0.85, -0.95, -0.65), (0.85, 1.05, 0.65)
    x, y, z, axes = grid(lo, hi, step)
    # turn it as it sits in the chest: apex toward the front-left-bottom
    a = 0.55
    xr, yr = x * np.cos(a) - y * np.sin(a), x * np.sin(a) + y * np.cos(a)
    lv = ellipsoid(xr, yr, z, (0.10, -0.22, -0.02), (0.30, 0.52, 0.32))
    rv = ellipsoid(xr, yr, z, (-0.16, -0.12, 0.10), (0.26, 0.42, 0.26))
    la = ellipsoid(xr, yr, z, (0.14, 0.30, -0.12), (0.22, 0.18, 0.20))
    ra = ellipsoid(xr, yr, z, (-0.26, 0.24, 0.00), (0.22, 0.22, 0.22))
    d = smin(smin(lv, rv, 0.10), smin(la, ra, 0.08), 0.10)
    # the interventricular groove on the front
    d = d + 0.025 * np.exp(-(((xr + 0.02 + 0.10 * yr) / 0.03) ** 2)) * (z > 0) * (yr < 0.15)

    def tube(p0, p1, r):
        p0, p1 = np.array(p0), np.array(p1)
        v = p1 - p0
        t = np.clip(((x - p0[0]) * v[0] + (y - p0[1]) * v[1] + (z - p0[2]) * v[2]) / (v @ v), 0, 1)
        return np.sqrt((x - p0[0] - t * v[0]) ** 2 + (y - p0[1] - t * v[1]) ** 2 + (z - p0[2] - t * v[2]) ** 2) - r

    # aorta: up from the left ventricle, the arch, down behind
    arch = 9 * np.ones_like(x)
    pts = [
        (0.02, 0.35, 0.05),
        (0.02, 0.62, 0.02),
        (0.10, 0.84, -0.08),
        (0.30, 0.86, -0.22),
        (0.42, 0.70, -0.32),
        (0.44, 0.10, -0.36),
    ]
    for p0, p1 in zip(pts, pts[1:], strict=False):
        arch = np.minimum(arch, tube(p0, p1, 0.095))
    for p0, p1 in (((0.08, 0.85, -0.08), (0.00, 1.02, -0.06)), ((0.20, 0.88, -0.16), (0.20, 1.03, -0.16)),
                   ((0.30, 0.86, -0.22), (0.38, 1.02, -0.24))):  # fmt: skip
        arch = np.minimum(arch, tube(p0, p1, 0.045))  # the three branches off the arch
    pulm = smin(
        tube((-0.10, 0.25, 0.20), (-0.04, 0.62, 0.10), 0.085),
        tube((-0.04, 0.60, 0.10), (-0.36, 0.66, -0.05), 0.06),
        0.05,
    )
    pulm = smin(pulm, tube((-0.04, 0.60, 0.10), (0.30, 0.55, -0.12), 0.06), 0.05)
    svc = tube((-0.40, 0.30, 0.0), (-0.40, 0.90, -0.02), 0.07)
    ivc = tube((-0.36, 0.02, -0.08), (-0.36, -0.55, -0.12), 0.07)
    d = smin(d, arch, 0.06)
    d = smin(d, pulm, 0.05)
    d = smin(np.minimum(d, svc), ivc, 0.04)
    d = d - 0.0025 * waves(x, y, z, 10, 0.16, 3)  # the surface isn't glass-smooth
    return d, axes, (x, y, z)


def body_sdf(step):
    """A human figure, standing, for the body map: head, neck, torso, arms, hands, legs (1 unit = 0.5 m here)."""
    lo, hi = (-0.62, -1.02, -0.22), (0.62, 1.02, 0.22)
    x, y, z, axes = grid(lo, hi, step)

    def cap(p0, p1, r0, r1):
        p0, p1 = np.array(p0), np.array(p1)
        v = p1 - p0
        t = np.clip(((x - p0[0]) * v[0] + (y - p0[1]) * v[1] + (z - p0[2]) * v[2]) / (v @ v), 0, 1)
        return np.sqrt((x - p0[0] - t * v[0]) ** 2 + (y - p0[1] - t * v[1]) ** 2 + (z - p0[2] - t * v[2]) ** 2) - (
            r0 + (r1 - r0) * t
        )

    d = ellipsoid(x, y, z, (0, 0.86, 0.0), (0.085, 0.11, 0.10))  # head
    d = smin(d, cap((0, 0.74, 0), (0, 0.66, 0), 0.045, 0.05), 0.03)  # neck
    d = smin(d, ellipsoid(x, y, z, (0, 0.44, 0.0), (0.20, 0.22, 0.11)), 0.06)  # chest
    d = smin(d, ellipsoid(x, y, z, (0, 0.18, 0.0), (0.16, 0.16, 0.10)), 0.08)  # abdomen
    d = smin(d, ellipsoid(x, y, z, (0, 0.0, 0.0), (0.18, 0.11, 0.11)), 0.06)  # pelvis
    for s in (1, -1):
        d = smin(d, cap((s * 0.20, 0.60, 0), (s * 0.27, 0.32, 0.01), 0.055, 0.045), 0.04)  # upper arm
        d = smin(d, cap((s * 0.27, 0.32, 0.01), (s * 0.31, 0.06, 0.04), 0.045, 0.035), 0.03)  # forearm
        d = smin(d, ellipsoid(x, y, z, (s * 0.32, -0.02, 0.05), (0.035, 0.07, 0.025)), 0.02)  # hand
        d = smin(d, cap((s * 0.09, -0.04, 0), (s * 0.10, -0.48, 0.0), 0.075, 0.055), 0.04)  # thigh
        d = smin(d, cap((s * 0.10, -0.48, 0.0), (s * 0.10, -0.92, -0.02), 0.055, 0.04), 0.03)  # shin
        d = smin(d, ellipsoid(x, y, z, (s * 0.10, -0.96, 0.04), (0.045, 0.03, 0.09)), 0.02)  # foot
    return d, axes, (x, y, z)


def label_cortex(v):
    x, y, z = v[:, 0], v[:, 1], v[:, 2]
    lab = np.full(len(v), 0, np.uint8)
    cen = 0.05 + 0.18 * np.clip((y - 0.15) / 0.45, -1, 1)
    syl = -0.17 + 0.42 * np.clip(-(z - 0.20), -0.2, 1.2) * 0.32
    lab[(z > cen + 0.10) & (y > -0.05)] = 0  # prefrontal
    lab[(z > 0.20) & (y <= -0.05)] = 1  # orbitofrontal (the underside of the frontal lobe)
    lab[(z <= cen + 0.10) & (z > cen - 0.02) & (y > syl)] = 2  # precentral (motor strip)
    lab[(z <= cen - 0.02) & (z > -0.50) & (y > syl)] = 3  # parietal (postcentral: touch)
    lab[z <= -0.50] = 4  # occipital
    lab[(y <= syl) & (z > -0.50) & (z <= 0.20)] = 5  # temporal
    lab[(y <= syl + 0.09) & (y > syl - 0.10) & (z <= -0.12) & (z > -0.50)] = 6  # temporoparietal junction
    lab[(np.abs(x) < 0.30) & (y < 0.05) & (y > -0.25) & (np.abs(z) < 0.25)] = 14  # insula/medial: deep
    return lab


def mesh(d, axes, level=0.0):
    step = float(axes[0][1] - axes[0][0])
    verts, faces, _, _ = measure.marching_cubes(d, level=level, spacing=(step, step, step), allow_degenerate=False)
    verts += np.array([axes[0][0], axes[1][0], axes[2][0]], dtype=np.float32)
    return verts.astype(np.float32), faces.astype(np.uint32)


def pack(meshes: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]]) -> bytes:
    head, blobs, off = [], [], 0
    for name, v, f, lab in meshes:
        scale = float(np.abs(v).max()) / 32000.0
        q = np.round(v / scale).astype(np.int16)
        b = q.tobytes() + f.tobytes() + lab.astype(np.uint8).tobytes()
        b += b"\0" * ((-len(b)) % 4)
        head.append({"name": name, "verts": len(v), "tris": len(f), "scale": scale, "off": off})
        blobs.append(b)
        off += len(b)
    hj = json.dumps({"regions": REGIONS, "meshes": head}).encode()
    hj += b" " * ((-len(hj)) % 4)
    return b"KBM1" + struct.pack("<I", len(hj)) + hj + b"".join(blobs)


def main(out: Path) -> None:
    step = 0.0125
    meshes = []
    d, axes, _ = cerebrum(step)
    v, f = mesh(d, axes, 0.0)
    meshes.append(("grey", v, f, label_cortex(v)))
    d, axes, _ = cerebellum_sdf(step * 0.8)
    v, f = mesh(d, axes)
    meshes.append(("cerebellum", v, f, np.full(len(v), 7)))
    d, axes, _ = brainstem_sdf(step)
    v, f = mesh(d, axes)
    meshes.append(("brainstem", v, f, np.full(len(v), 8)))
    parts, axes, _ = deep_sdf(step)
    for name, dd in parts.items():
        v, f = mesh(dd, axes)
        meshes.append((name, v, f, np.full(len(v), REGIONS.index(name))))
    d, axes, _ = heart_sdf(0.018)
    v, f = mesh(d, axes)
    meshes.append(("heart", v, f, np.full(len(v), 15)))
    data = pack(meshes)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    # the cerebrum's distance field as a volume, for the dissection plane: uint8, 128 = the pial surface, ±0.1 units
    d, axes, _ = cerebrum(0.0125)
    vol = np.clip((d / 0.1) * 127.5 + 128, 0, 255).astype(np.uint8)
    head = {"shape": list(vol.shape), "lo": [float(a[0]) for a in axes], "step": 0.0125, "white": 0.045, "range": 0.1}
    hj = json.dumps(head).encode()
    hj += b" " * ((-len(hj)) % 4)
    (out.parent / "cerebrum.vol").write_bytes(
        b"KBV1" + struct.pack("<I", len(hj)) + hj + vol.transpose(2, 1, 0).tobytes()
    )
    print("volume", vol.shape)
    for name, v, f, _ in meshes:
        print(f"{name:12s} {len(v):8d} verts {len(f):8d} tris")
    print(f"{out}: {len(data) / 1e6:.2f} MB")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("src/kurooto/web/static/body/anatomy.bin"))
