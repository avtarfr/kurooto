import hashlib
import io
import json
import os
import sys
import tarfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from kurooto.core.prereqs import Prereqs


class Files:
    def __init__(self):
        self.files = {}
        fs = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = fs.files.get(self.path)
                self.send_response(200 if body is not None else 404)
                self.send_header("Content-Length", str(len(body or b"")))
                self.end_headers()
                self.wfile.write(body or b"")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def files():
    f = Files()
    yield f
    f.server.shutdown()


def zip_of(entries):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return b.getvalue()


def manifest(kind_step, programs, dirs):
    osn = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    return {
        "thing": {
            "title": "Thing",
            "size_gb": 0.01,
            "programs": programs,
            "dirs": {osn: dirs},
            "install": {osn: kind_step},
        }
    }


def exe(name):
    return name + (".exe" if os.name == "nt" else "")


def test_zip_install_refuses_path_escapes(files, tmp_path):
    files.files["/thing.zip"] = zip_of({f"bin/{exe('thing')}": b"#!", "../../evil.txt": b"x", "/abs.txt": b"x"})
    m = Prereqs(
        tmp_path / "app",
        tmp_path / "cache",
        manifest=manifest(
            {"kind": "download-zip", "url": files.base + "/thing.zip", "into": "{app}/thing"},
            ["thing"],
            ["{app}/thing/bin"],
        ),
    )
    ok, msg = m.install("thing", progress=lambda s: None, margin_gb=0)
    assert ok, msg
    assert (tmp_path / "app/thing/bin" / exe("thing")).exists()
    assert not (tmp_path / "evil.txt").exists() and not (tmp_path / "app/evil.txt").exists()


def test_node_lts_is_checksum_verified(files, tmp_path, monkeypatch):
    osn = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    from kurooto.core import prereqs as pr

    a = "arm64" if pr.arch() == "arm64" else "x64"
    v = "v22.0.0"
    if osn == "windows":
        name = f"node-{v}-win-{a}.zip"
        data = zip_of({f"node-{v}-win-{a}/node.exe": b"MZ"})
    else:
        ext = "tar.gz" if osn == "macos" else "tar.xz"
        name = f"node-{v}-{'darwin' if osn == 'macos' else 'linux'}-{a}.{ext}"
        b = io.BytesIO()
        with tarfile.open(fileobj=b, mode="w:gz" if ext == "tar.gz" else "w:xz") as t:
            info = tarfile.TarInfo(f"node-{v}/bin/node")
            info.size, info.mode = 2, 0o755
            t.addfile(info, io.BytesIO(b"#!"))
        data = b.getvalue()
    files.files["/dist/index.json"] = json.dumps(
        [{"version": "v23.0.0", "lts": False}, {"version": v, "lts": "Jod"}]
    ).encode()
    files.files[f"/dist/{v}/SHASUMS256.txt"] = f"{hashlib.sha256(data).hexdigest()}  {name}\n".encode()
    files.files[f"/dist/{v}/{name}"] = data
    m = Prereqs(tmp_path / "app", tmp_path / "cache", manifest=manifest({"kind": "node-lts"}, [], []))
    assert m._node(lambda s: None, dist=files.base + "/dist") == (True, v)
    assert (tmp_path / "app/node" / ("node.exe" if osn == "windows" else "bin/node")).exists()
    files.files[f"/dist/{v}/SHASUMS256.txt"] = f"{'0' * 64}  {name}\n".encode()
    with pytest.raises(ValueError, match="checksum"):
        m._node(lambda s: None, dist=files.base + "/dist")


def test_not_enough_space_refuses_before_downloading(files, tmp_path):
    m = Prereqs(
        tmp_path / "app",
        tmp_path / "cache",
        manifest=manifest(
            {"kind": "download-zip", "url": files.base + "/x.zip", "into": "{app}"}, ["nothing-here"], []
        ),
    )
    m.items["thing"].size_gb = 10_000
    ok, msg = m.install("thing", progress=lambda s: None)
    assert not ok and "Not enough space" in msg and not (tmp_path / "cache").exists()
    r = m.room(["thing"])
    assert r["ok"] is False and r["need_gb"] == 10_000


def test_only_https_downloads(tmp_path):
    m = Prereqs(tmp_path / "app", tmp_path / "cache", manifest={})
    with pytest.raises(ValueError):
        m._download("http://example.com/x.zip", lambda s: None)


def test_real_manifest_loads_for_every_os(tmp_path):
    here = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    for osn in ("windows", "macos", "linux"):
        m = Prereqs(tmp_path, tmp_path, os=osn)
        assert {"agy", "ollama", "node", "telegram-desktop"} <= set(m.items)
        assert all(p.step.get("kind") for p in m.items.values())
        if osn == here:  # other systems' paths can't be judged by this one's rules
            assert all(Path(str(d)).is_absolute() for p in m.items.values() for d in p.dirs)


def test_untar_streams_from_disk_never_whole_in_memory(tmp_path, monkeypatch):
    """Ollama's Linux archive is gigabytes unpacked; reading it whole once got Kurooto killed for memory."""
    import io as _io

    zstandard = pytest.importorskip("zstandard")  # only installed on Linux, where Ollama's archive is .tar.zst

    from kurooto.core import prereqs as pq

    raw = _io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as t:
        for name, data in (("ollama/bin/ollama", b"#!/bin/sh\n"), ("ollama/lib/a.so", b"x" * 4096), ("../evil", b"no")):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, _io.BytesIO(data))
    archive = tmp_path / "ollama-linux-amd64.tar.zst"
    archive.write_bytes(zstandard.ZstdCompressor().compress(raw.getvalue()))
    real = pq.Path.read_bytes
    monkeypatch.setattr(
        pq.Path,
        "read_bytes",
        lambda self: (_ for _ in ()).throw(AssertionError("read whole")) if self == archive else real(self),
    )
    pq.Prereqs._untar(archive, tmp_path / "out", strip=1)
    assert (tmp_path / "out" / "bin" / "ollama").read_bytes() == b"#!/bin/sh\n"
    assert (tmp_path / "out" / "lib" / "a.so").stat().st_size == 4096
    assert not (tmp_path / "evil").exists()  # nothing lands outside the target folder
