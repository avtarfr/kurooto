"""`kurooto rotate` against the real Worker under `wrangler dev` (workerd; no Cloudflare account, nothing leaves the
machine), started three times on the same stored data: once with the first keys, once again with the same keys (an
update: nothing is forgotten), and once with the new keys `kurooto rotate` makes (the phones paired before, the call
links and open pairing codes stop working; the old computer key is refused).

Skipped unless the Worker's packages are installed (`npm ci` in src/kurooto/data/worker) and Node is on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest
from websockets.sync.client import connect

from kurooto.core import leave
from kurooto.modules.calls import deploy, line
from tests.integration.test_call_line import WORKER, Line, free_port, wait

pytestmark = pytest.mark.skipif(
    not (WORKER / "node_modules" / "wrangler").is_dir() or not shutil.which("node") or sys.platform == "win32",
    reason="needs Node and the Worker's packages (npm ci in src/kurooto/data/worker)",
)


class Dev:
    """`wrangler dev` on a copy of the Worker, with the keys given and the stored data kept between starts."""

    def __init__(self, tmp):
        self.tmp, self.port = tmp, free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.work = tmp / "worker"
        shutil.copytree(WORKER, self.work, ignore=shutil.ignore_patterns("node_modules", ".wrangler", "wrangler.toml"))
        (self.work / "node_modules").symlink_to(WORKER / "node_modules", target_is_directory=True)
        values = {
            "name": "kurooto-test",
            "owner_id": "owner",
            "tz": "UTC",
            "public_url": self.url,
            "version": "test",
            "live_model": "gemini-test-live",
            "ntfy_server": "http://127.0.0.1:9",  # nothing rings in this test
            "notes_repo": "",
        }
        tpl = (self.work / "wrangler.template.toml").read_text()
        (self.work / "wrangler.toml").write_text(deploy.render_toml(tpl, values))
        self.proc = None

    def start(self, sec: dict) -> Line:
        (self.work / ".dev.vars").write_text("".join(f"{k}='{v}'\n" for k, v in sec.items()))
        env = {**deploy.wrangler_env(self.tmp / "wcfg", self.tmp / "wcache"), "CI": "1", "PATH": os.environ["PATH"]}
        self.proc = subprocess.Popen(
            [
                "node",
                "node_modules/wrangler/bin/wrangler.js",
                "dev",
                "--ip",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--persist-to",
                str(self.tmp / "do"),
                "--show-interactive-dev-session=false",
                "--log-level",
                "warn",
            ],
            cwd=self.work,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        ln = Line(self.url)
        wait(lambda: ln.call("GET", "/health")[0] == 200 if self.proc.poll() is None else True, 90, "wrangler dev")
        assert self.proc.poll() is None, self.proc.stdout.read().decode()[-2000:]
        return ln

    def stop(self) -> None:
        if self.proc is None:
            return
        os.killpg(self.proc.pid, 15)
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, 9)
        self.proc = None

    def admin(self, connector_secret: str, op: str, **kw) -> dict:
        """What this computer's link asks the line (connector.py), over a WebSocket of its own."""
        ws_url = self.url.replace("http://", "ws://") + "/connect"
        with connect(ws_url, additional_headers={"x-connector-secret": connector_secret}, open_timeout=15) as ws:
            ws.send(json.dumps({"type": "admin", "id": "t1", "op": op, **kw}))
            while True:
                m = json.loads(ws.recv(timeout=20))
                if m.get("type") == "admin-reply":
                    return m["result"]


def pair(dev: Dev, ln: Line, sec: dict, code: str) -> dict:
    assert dev.admin(sec["CONNECTOR_SECRET"], "pair-code", code=code, minutes=15) == {"ok": True}
    status, got = ln.call("POST", "/pair/claim", {"code": code, "kind": "android", "name": "Test phone"})
    assert status == 200, got
    return got


def test_a_rotated_line_forgets_its_phones_links_and_codes(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "kurooto"))
    from kurooto.app import App

    app = App()
    dev = Dev(tmp_path)
    try:
        app.secrets.set("gemini.api_key", "fake-gemini-key")
        first = deploy.ensure_secrets(app)
        ln = dev.start(first)
        phone = pair(dev, ln, first, "ABCD2345")["device"]
        made_here = dev.admin(first["CONNECTOR_SECRET"], "ticket", hours=2)["ticket"]  # a /call link's key
        assert dev.admin(first["CONNECTOR_SECRET"], "pair-code", code="WXYZ6789", minutes=15) == {"ok": True}
        signed = line.ticket(first["CALL_SECRET"])  # a call link this computer made
        for key in (phone, made_here, signed):
            assert ln.call("GET", "/status", key=key)[0] == 200
        dev.stop()

        ln = dev.start(first)  # deployed again with the same keys (an update): everything still works
        assert ln.call("GET", "/status", key=phone)[0] == 200 and ln.call("GET", "/status", key=made_here)[0] == 200
        assert len(dev.admin(first["CONNECTOR_SECRET"], "devices")["devices"]) == 1
        dev.stop()

        for k in leave.LINE_KEYS:  # what `kurooto rotate` does before it deploys (core/leave.py: rotate_line)
            app.secrets.delete(k)
        new = deploy.ensure_secrets(app)
        assert all(new[k] != first[k] for k in ("CALL_SECRET", "CONNECTOR_SECRET", "NTFY_KEY", "NTFY_TOPIC"))
        ln = dev.start(new)
        for key in (phone, made_here, signed):
            assert ln.call("GET", "/status", key=key)[0] == 401
        assert ln.call("POST", "/pair/claim", {"code": "WXYZ6789", "kind": "android"})[0] == 401
        with pytest.raises(Exception):  # noqa: B017 (the old computer key: the WebSocket is refused)
            dev.admin(first["CONNECTOR_SECRET"], "devices")
        assert dev.admin(new["CONNECTOR_SECRET"], "devices") == {"devices": []}
        assert ln.call("GET", "/status", key=line.ticket(new["CALL_SECRET"]))[0] == 200
        again = pair(dev, ln, new, "QRST2345")  # pairing again works, and gets the new notification key
        assert again["ntfy"] == {"server": "http://127.0.0.1:9", "topic": new["NTFY_TOPIC"], "key": new["NTFY_KEY"]}
        assert again["vapid"] == new["VAPID_PUBLIC"] and ln.call("GET", "/status", key=again["device"])[0] == 200
        assert len(dev.admin(new["CONNECTOR_SECRET"], "devices")["devices"]) == 1
    finally:
        dev.stop()
        app.close()
