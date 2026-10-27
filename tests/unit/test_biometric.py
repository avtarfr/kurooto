"""core/biometric.py: the sealed template (AES-GCM, bound to its feature), the key that's never remade over an old
template, forgetting with the key first, the calibration's edge cases, and numpy's .npz read and written without
numpy. No camera, microphone or model: made-up vectors only."""

import base64
import json
import math
import random

import pytest

from kurooto.core import biometric
from kurooto.core.biometric import Locked, TemplateStore, calibrate, load_impostors, npz_read, npz_write, unit


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    yield a
    a.close()


def vec(seed, n=128):
    r = random.Random(seed)  # noqa: S311 (made-up test data, not secrets)
    return unit([r.gauss(0, 1) for _ in range(n)])


def test_seal_and_unseal_round_trip(app):
    s = TemplateStore(app, "face")
    payload = {"samples": [{"e": biometric.pack(vec(1)), "step": "front"}], "grade": "good"}
    s.save(payload, {"enrolled": True, "samples": 1})
    assert s.load() == payload
    raw = s.file.read_bytes()
    assert b"samples" not in raw and b"{" not in raw[:2] and payload["samples"][0]["e"].encode()[:12] not in raw
    assert s.status() == {"enrolled": True, "samples": 1}


def test_a_blob_from_another_feature_doesnt_open(app):
    face, other = TemplateStore(app, "face"), TemplateStore(app, "voice_id")
    face.key()
    app.secrets.set("voice_id.key", app.secrets.get("face.key"))  # even with the same key: the AAD differs
    blob = other.seal({"x": 1})
    assert face.unseal(blob) is None and other.unseal(blob) == {"x": 1}
    assert face.unseal(b"short") is None


def test_a_lost_key_locks_and_no_new_key_is_made_over_the_template(app):
    s = TemplateStore(app, "face")
    s.save({"x": 1})
    app.secrets.delete("face.key")
    fresh = TemplateStore(app, "face")
    with pytest.raises(Locked):
        fresh.key()
    assert app.secrets.get("face.key") is None and not fresh.readable()
    with pytest.raises(Locked):
        fresh.load()


def test_a_wrong_key_reads_nothing(app):
    s = TemplateStore(app, "face")
    s.save({"x": 1})
    app.secrets.set("face.key", base64.b64encode(b"\x01" * 32).decode())
    assert TemplateStore(app, "face").load() is None


def test_forget_deletes_the_key_first(app, monkeypatch):
    s = TemplateStore(app, "face")
    s.save({"x": 1}, {"enrolled": True})
    seen = []
    real = app.secrets.delete

    def delete(name):
        seen.append((name, s.file.exists()))
        real(name)

    monkeypatch.setattr(app.secrets, "delete", delete)
    gone = s.forget()
    assert seen[0] == ("face.key", True)  # the key went while the template was still there
    assert gone == ["the key", "the template", "its status"]
    assert not s.file.exists() and not s.status_file.exists() and not s.dir.exists()
    assert app.secrets.get("face.key") is None


def test_calibrate_with_impostors_meets_the_target_and_keeps_the_floor():
    r = random.Random(3)  # noqa: S311 (made-up test data, not secrets)
    imp = [r.gauss(0.45, 0.05) for _ in range(5000)]
    th = calibrate([0.8] * 50, imp, 1e-3, 3.09, 0.363)
    assert th.method == "impostors" and th.impostors == 5000
    assert sum(x >= th.hi for x in imp) / len(imp) <= 1e-3
    assert math.isclose(th.lo, th.hi - 0.10)
    low = [r.gauss(0.0, 0.05) for _ in range(5000)]
    th2 = calibrate([0.8] * 50, low, 1e-3, 3.09, 0.363)
    assert th2.hi == 0.363 and th2.t_far < 0.363  # the floor holds when the impostors are far off


def test_the_gaussian_guards_the_strict_end():
    imp = [0.1] * 4990 + [0.3] * 10  # a lumpy set: the empirical quantile alone says 0.3 at 1e-4
    m, sd = biometric.mean_std(imp)
    th = calibrate([], imp, 1e-4, 3.72, 0.0)
    assert th.t_far == max(biometric.quantile(imp, 1 - 1e-4), m + 3.72 * sd)


def test_calibrate_edge_cases():
    same = calibrate([0.7] * 30, [0.2] * 100, 1e-3, 3.09, 0.363)  # identical scores: std 0
    assert same.hi == 0.363
    tiny = calibrate([0.7], [0.1, 0.2], 1e-3, 3.09, 0.363)  # too few impostors to say anything
    assert tiny.method == "floor" and math.isclose(tiny.hi, 0.413)
    none = calibrate([0.7], None, 1e-3, 3.09, 0.363)
    assert none.method == "floor"
    over = calibrate([0.7], [0.1] * 100, 1e-3, 3.09, 0.363, override=0.5)
    assert over.method == "override" and over.hi == 0.5 and math.isclose(over.lo, 0.4)
    loose = calibrate([0.7], [0.1] * 100, 1e-3, 3.09, 0.363, override=0.1)  # a setting never goes under the floor
    assert loose.method == "override" and loose.hi == 0.363
    assert calibrate([], [0.0] * 100, 1e-3, 3.09, 0.1).lo == 0.20  # T_lo never below 0.20


def test_npz_round_trip_and_the_impostor_set(tmp_path):
    rows = [vec(i) for i in range(30)]
    f = tmp_path / "imp.npz"
    npz_write(f, emb=rows, model_sha256="abc", source="made up")
    d = npz_read(f)
    assert d["model_sha256"] == "abc" and d["source"] == "made up" and len(d["emb"]) == 30
    assert all(abs(a - b) < 2e-3 for a, b in zip(d["emb"][0], rows[0], strict=True))  # float16
    got = load_impostors(f, "abc")
    assert got is not None and len(got) == 30 and abs(sum(x * x for x in got[0]) - 1) < 1e-6
    assert load_impostors(f, "another model") is None
    assert load_impostors(tmp_path / "missing.npz", "abc") is None
    (tmp_path / "bad.npz").write_bytes(b"not a zip")
    assert load_impostors(tmp_path / "bad.npz", "abc") is None


def test_pack_is_float16_base64():
    v = vec(9)
    back = biometric.unpack(biometric.pack(v))
    assert len(back) == 128 and max(abs(a - b) for a, b in zip(v, back, strict=True)) < 1e-3
    assert json.dumps(biometric.pack(v))  # a plain string


def test_the_face_template_is_owner_only_from_its_first_byte(app, monkeypatch):
    import os
    import stat

    if os.name == "nt":
        pytest.skip("POSIX modes")
    seen = []
    real = os.replace

    def spy(src, dst):  # the temporary file, just before it becomes the template
        seen.append(stat.S_IMODE(os.stat(src).st_mode))
        return real(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    old = os.umask(0o022)
    try:
        s = TemplateStore(app, "face")
        s.save({"x": 1}, {"enrolled": True})
    finally:
        os.umask(old)
    assert seen[0] == 0o600  # the template (then its status file)
    assert stat.S_IMODE(s.file.stat().st_mode) == 0o600 and stat.S_IMODE(s.dir.stat().st_mode) == 0o700
    assert not list(s.dir.glob("*.tmp*"))
