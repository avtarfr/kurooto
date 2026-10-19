"""The call line end to end on this computer: the real Worker under `wrangler dev` (workerd; no Cloudflare account,
nothing leaves the machine), the real connector and Phone calls feature, and fake Gemini, ntfy and Web Push servers.

Skipped unless the Worker's packages are installed (`npm ci` in src/kurooto/data/worker) and Node is on PATH.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

import kurooto
from kurooto.modules.calls import deploy, line
from tests.fakes.cloud import FakeCloud

WORKER = Path(kurooto.__file__).parent / "data" / "worker"
pytestmark = pytest.mark.skipif(
    not (WORKER / "node_modules" / "wrangler").is_dir() or not shutil.which("node") or sys.platform == "win32",
    reason="needs Node and the Worker's packages (npm ci in src/kurooto/data/worker)",
)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait(cond, timeout=20.0, what="condition"):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {what}")


class Loop:
    """What the daemon does for the Phone calls feature: run its background part on an event loop."""

    def __init__(self, app):
        self.app, self.ready = app, threading.Event()
        self.thread = threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True)
        self.thread.start()
        self.ready.wait(10)

    async def _main(self):
        self.stop = asyncio.Event()
        self.loop = asyncio.get_running_loop()
        self.app._stop, self.app._loop = self.stop, self.loop
        self.ready.set()
        await self.app.modules["calls"].background(self.stop)

    def halt(self):
        self.loop.call_soon_threadsafe(self.stop.set)
        self.thread.join(15)


class Line:
    def __init__(self, base):
        self.base = base

    def call(self, method, path, body=None, key=None, raw=None, ctype="application/json"):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        req = urllib.request.Request(self.base + path, data=data, method=method, headers={"content-type": ctype})
        if key:
            req.add_header("x-call-secret", key)
        try:
            with urllib.request.urlopen(req, timeout=70) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")
        except urllib.error.URLError:
            return 0, {}  # not listening (yet)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("line")
    old_home = os.environ.get("KUROOTO_HOME")
    os.environ["KUROOTO_HOME"] = str(tmp / "kurooto")
    from kurooto.app import App

    cloud = FakeCloud()
    app = App()
    sent = []
    app.settings.set("notify.desktop", False)
    app.notifier.register("telegram", lambda m: sent.append(m) or len(sent))
    app.settings.set("you.name", "Sam")
    app.settings.set("you.timezone", "Europe/Berlin")
    app.settings.set("calls.ntfy_server", cloud.base)
    app.settings.set("calls.live_model", "gemini-test-live")
    app.secrets.set("gemini.api_key", "fake-gemini-key")
    (app.workspace / "courses").mkdir(parents=True)
    (app.workspace / "courses" / "linear-algebra.md").write_text(
        "# Linear algebra\n\n## Eigenvalues\n\nDet(A - tI) = 0.\n"
    )

    port = free_port()
    url = f"http://127.0.0.1:{port}"
    work = tmp / "worker"
    shutil.copytree(WORKER, work, ignore=shutil.ignore_patterns("node_modules", ".wrangler", "wrangler.toml"))
    (work / "node_modules").symlink_to(WORKER / "node_modules", target_is_directory=True)
    tpl = (work / "wrangler.template.toml").read_text()
    (work / "wrangler.toml").write_text(
        deploy.render_toml(
            tpl,
            {
                "name": "kurooto-test",
                "owner_id": "owner",
                "tz": "Europe/Berlin",
                "public_url": url,
                "version": "test",
                "live_model": "gemini-test-live",
                "ntfy_server": cloud.base,
                "notes_repo": "",
            },
        )
    )
    sec = deploy.ensure_secrets(app)
    (work / ".dev.vars").write_text("".join(f"{k}='{v}'\n" for k, v in sec.items()))  # single quotes: literal
    env = {**deploy.wrangler_env(tmp / "wcfg", tmp / "wcache"), "CI": "1", "PATH": os.environ["PATH"]}
    proc = subprocess.Popen(
        [
            "node",
            "node_modules/wrangler/bin/wrangler.js",
            "dev",
            "--ip",
            "127.0.0.1",
            "--port",
            str(port),
            "--test-scheduled",
            "--persist-to",
            str(tmp / "do"),
            "--var",
            f"GEMINI_BASE_URL:{cloud.base}",
            "--show-interactive-dev-session=false",
            "--log-level",
            "warn",
        ],
        cwd=work,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    out = Line(url)
    try:
        wait(lambda: out.call("GET", "/health")[0] == 200 if proc.poll() is None else True, 90, "wrangler dev")
        assert proc.poll() is None, proc.stdout.read().decode()[-2000:]
        app.settings.set("calls.worker", {"url": url, "name": "kurooto-test"})
        loop = Loop(app)
        calls = app.modules["calls"]
        wait(lambda: calls.connector.connected, 30, "the connector")
        world = {"app": app, "calls": calls, "line": out, "cloud": cloud, "sent": sent, "loop": loop, "sec": sec}
        yield world
        world["loop"].halt()
    finally:
        os.killpg(proc.pid, 15)
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, 9)
        cloud.close()
        app.close()
        if old_home is None:
            os.environ.pop("KUROOTO_HOME", None)
        else:
            os.environ["KUROOTO_HOME"] = old_home


def test_health_and_link_auth(world):
    ln, calls = world["line"], world["calls"]
    code, h = ln.call("GET", "/health")
    assert code == 200 and h == {"ok": True, "version": "test"}
    assert ln.call("GET", "/status")[0] == 401
    assert ln.call("GET", "/status", key="nonsense")[0] == 401
    expired = line.ticket(world["sec"]["CALL_SECRET"], hours=-1)
    assert ln.call("GET", "/status", key=expired)[0] == 401
    t = calls.link().split("#", 1)[1]
    code, st = wait(
        lambda: (lambda r: r if r[1].get("assistant") else None)(ln.call("GET", "/status", key=t)),
        20,
        "the first state push",
    )
    assert code == 200 and st["computer"] == "online" and st["assistant"] == "Kurooto" and st["owner"] == "Sam"


def test_pairing(world):
    ln, calls = world["line"], world["calls"]
    p = calls.pair_start()
    assert p["link"].endswith(f"/pair#c={p['code']}") and "<svg" in p["svg"]
    assert ln.call("POST", "/pair/claim", {"code": "WRONGCODE", "kind": "android"})[0] == 401
    code, got = ln.call("POST", "/pair/claim", {"code": p["code"].lower(), "kind": "android", "name": "Test phone"})
    assert code == 200, got
    assert got["device"].startswith("d1.") and got["ntfy"]["topic"] == world["sec"]["NTFY_TOPIC"]
    assert got["ntfy"]["key"] == world["sec"]["NTFY_KEY"] and got["assistant"] == "Kurooto"
    assert ln.call("POST", "/pair/claim", {"code": p["code"], "kind": "android"})[0] == 401  # one use only
    world["android"] = got["device"]
    assert ln.call("GET", "/status", key=got["device"])[1]["device"] == got["id"]
    assert [d["name"] for d in calls.devices()] == ["Test phone"]
    wait(lambda: any("was paired" in m.text for m in world["sent"]), 10, "the paired notice")


def test_token_is_minted_with_the_pushed_setup(world):
    ln, cloud = world["line"], world["cloud"]
    code, t = ln.call("POST", "/token", {"purpose": "Evening check-in"}, key=world["android"])
    assert code == 200, t
    assert t["token"].startswith("auth_tokens/fake-") and t["model"] == "gemini-test-live" and t["offline"] is False
    sent = cloud.tokens[-1]
    assert sent["headers"]["x-goog-api-key"] == "fake-gemini-key"
    blob = json.dumps(sent["body"])
    assert "Sam's personal assistant" in blob and "%%NOW%%" not in blob and "Evening check-in" in blob
    assert "pending_items" in blob and "schedule_call" in blob
    assert "set_alarm" not in blob  # Morning alarm is off, so its tool isn't on calls


def test_tools_go_to_this_computer(world):
    ln, key = world["line"], world["android"]
    code, r = ln.call("POST", "/tool", {"name": "search_notes", "args": {"query": "eigenvalues"}}, key=key)
    assert code == 200 and r["result"]["hits"][0]["slug"] == "courses/linear-algebra"
    r = ln.call("POST", "/tool", {"name": "read_note", "args": {"slug": "courses/linear-algebra"}}, key=key)[1]
    assert "Det(A - tI)" in r["result"]
    r = ln.call("POST", "/tool", {"name": "read_note", "args": {"slug": "../../config/secrets"}}, key=key)[1]
    assert r["result"].startswith("No note")
    r = ln.call("POST", "/tool", {"name": "nonexistent", "args": {}}, key=key)[1]
    assert "no nonexistent tool" in r["result"]


def test_ringing_android_and_web(world):
    ln, calls, cloud = world["line"], world["calls"], world["cloud"]
    p = calls.pair_start()
    code, web = ln.call("POST", "/pair/claim", {"code": p["code"], "kind": "web", "name": "iPhone"})
    assert code == 200 and web["ntfy"] is None and web["vapid"] == world["sec"]["VAPID_PUBLIC"]
    sub = {"endpoint": f"{cloud.base}/push/abc", "keys": {}}
    assert ln.call("POST", "/push/subscribe", {"subscription": sub}, key=web["device"])[0] == 200
    n0, p0 = len(cloud.ntfy), len(cloud.pushes)
    since = calls.ring("Time to stretch")
    wait(lambda: len(cloud.ntfy) > n0 and len(cloud.pushes) > p0, 20, "the ring")
    msg = cloud.ntfy[-1]
    assert msg["topic"] == world["sec"]["NTFY_TOPIC"] and msg["message"].startswith("k1.")
    inner = json.loads(line.open_k1(world["sec"]["NTFY_KEY"], msg["message"]))
    assert inner["title"] == "Incoming call" and inner["message"] == "Time to stretch"
    assert "call" in inner["tags"] and f"since-{since}" in inner["tags"]
    # the push is VAPID-signed with this line's key, and carries nothing
    push = cloud.pushes[-1]
    assert push["len"] == 0
    auth = push["headers"]["authorization"]
    jwt = auth.split("t=")[1].split(",")[0]
    head, claims, sig = jwt.split(".")
    pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), line.unb64url(world["sec"]["VAPID_PUBLIC"]))
    raw = line.unb64url(sig)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    pub.verify(der, f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))
    assert json.loads(line.unb64url(claims))["aud"] == cloud.base
    # the web app asks what's ringing
    rings = ln.call("GET", "/pending", key=web["device"])[1]["rings"]
    assert rings[0]["reason"] == "Time to stretch" and rings[0]["since"] == since
    # "Later" from the phone: this computer hears it and calls back later
    assert ln.call("POST", "/ring-reply", {"since": since, "action": "later"}, key=world["android"])[0] == 200
    wait(lambda: calls.app.scheduler.jobs("calls:ring:"), 15, "the call-back")
    assert ln.call("GET", "/pending", key=web["device"])[1]["rings"] == []


def test_upload_and_transcript_reach_this_computer(world):
    ln, app, key = world["line"], world["app"], world["android"]
    q = "/upload?name=notes.txt&id=abc123&parts=2&part="
    assert ln.call("POST", q + "0", raw=b"hello ", key=key, ctype="application/octet-stream")[0] == 200
    code, r = ln.call("POST", q + "1", raw=b"world", key=key, ctype="application/octet-stream")
    assert code == 200 and r["saved"].startswith("inbox/")
    assert (app.workspace / r["saved"]).read_bytes() == b"hello world"
    lines = [{"who": "Sam", "text": "hi"}, {"who": "Kurooto", "text": "hello"}]
    assert ln.call("POST", "/transcript", {"lines": lines, "purpose": "test"}, key=key)[1] == {"ok": True}
    saved = list((app.paths.state / "calls" / "transcripts").glob("*.txt"))
    assert saved and "Sam: hi" in saved[-1].read_text()


def test_offline_brief_queue_and_cron(world):
    ln, app, calls, cloud, key = world["line"], world["app"], world["calls"], world["cloud"], world["android"]
    # a call due now, pushed to the line, then this computer goes away
    calls.schedule(datetime.datetime.now(), "Offline reminder call", key="t1")  # pokes the connector
    time.sleep(2.5)
    world["loop"].halt()
    wait(lambda: ln.call("GET", "/status", key=key)[1]["computer"] == "offline", 20, "offline")
    r = ln.call("POST", "/tool", {"name": "pending_items", "args": {}}, key=key)[1]["result"]
    assert "last sent" in r["note"] and "calls_planned" in r
    r = ln.call("POST", "/tool", {"name": "schedule_call", "args": {"when": "in 3 hours", "reason": "queued"}}, key=key)
    assert "Saved" in r[1]["result"]
    r = ln.call("POST", "/tool", {"name": "search_notes", "args": {"query": "eigenvalues linear"}}, key=key)[1]
    assert r["result"]["hits"][0]["slug"] == "courses/linear-algebra"  # the pushed index
    assert ln.call("GET", "/tasks", key=key)[1]["computer"] == "offline"
    code, t = ln.call("POST", "/token", {}, key=key)
    assert code == 200 and t["offline"] is True and "OFF right now" in json.dumps(world["cloud"].tokens[-1]["body"])
    # that call ends (the call page always says so); while it was on, the line held calls back
    assert ln.call("POST", "/transcript", {"lines": [], "ended": True}, key=key)[1] == {"ok": True, "queued": True}
    n0 = len(cloud.ntfy)
    with urllib.request.urlopen(ln.base + "/__scheduled?cron=*+*+*+*+*", timeout=30) as resp:
        assert resp.status == 200
    wait(lambda: len(cloud.ntfy) > n0, 15, "the cron ring")
    inner = json.loads(line.open_k1(world["sec"]["NTFY_KEY"], cloud.ntfy[-1]["message"]))
    assert inner["message"] == "Offline reminder call"
    # back online: the queued request is done, and the offline call is reported
    world["loop"] = Loop(app)
    wait(lambda: calls.connector.connected, 30, "reconnect")
    wait(lambda: any(j.payload.get("reason") == "queued" for j in app.scheduler.jobs("calls:ring:")), 15, "the queue")
    wait(lambda: any("your call line called you" in m.text for m in world["sent"]), 10, "the offline-call notice")
