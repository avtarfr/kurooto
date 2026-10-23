"""Tell Kurooto, the iPhone Shortcut (0.6.0), without a call line: the computer's side of its links (listed, revoked,
the notice when one is made), the dashboard's endpoints, and the phone page's QR maker checked against segno. The
links themselves (made, scoped to sending a chat message, revoked, ended by unpairing) are tested end to end in
tests/integration/test_shortcut_line.py."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import segno

from kurooto.core import calm
from kurooto.modules.calls import deploy

QR_JS = Path(__file__).parent.parent / "js" / "qr.mjs"


class FakeConnector:
    """Records admin requests and answers like a line would (the shortcut ops), or like a line from before 0.6.0."""

    connected, version = True, "test"

    def __init__(self, old=False):
        self.sent, self.old = [], old
        self.tells = {"0123abcd": {"device": "89abcdef", "device_name": "iPhone"}}

    def admin_wait(self, op, **kw):
        self.sent.append((op, kw))
        if self.old and op.startswith("tell"):
            return {"error": "unknown op"}
        if op == "tells":
            made = {"created": "2026-10-23T08:00:00Z", "used": None}
            return {"tells": [{"id": k, **v, **made} for k, v in self.tells.items()]}
        if op == "tell-revoke":
            return {"ok": self.tells.pop(kw.get("tid", ""), None) is not None}
        if op == "revoke":
            return {"ok": kw.get("device") == "89abcdef"}
        if op == "devices":
            return {"devices": []}
        return {}


@pytest.fixture
def calls(env):
    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    env.on("calls")
    c = env.app.modules["calls"]
    c.connector = FakeConnector()
    return env


def test_links_are_listed_and_revoked_by_their_own_id(calls):
    c = calls.app.modules["calls"]
    assert [(s["id"], s["device_name"]) for s in c.shortcuts()] == [("0123abcd", "iPhone")]
    assert c.shortcut_revoke("not an id") is False and c.connector.sent[-1][0] == "tells"  # never asked
    assert c.shortcut_revoke("0123abcd") is True
    # `tid`, never `id`: that's the admin request's own, and a clash meant waiting for an answer that never came
    assert c.connector.sent[-1] == ("tell-revoke", {"tid": "0123abcd"})
    assert c.shortcut_revoke("0123abcd") is False and c.shortcuts() == []
    c.connector = FakeConnector(old=True)  # a line from before 0.6.0
    assert c.shortcuts() == [] and c.shortcut_revoke("0123abcd") is False


def test_unpairing_a_phone_sends_its_id_as_device(calls):
    c = calls.app.modules["calls"]
    assert c.revoke("89abcdef") is True and c.connector.sent[-1] == ("revoke", {"device": "89abcdef"})
    assert calls.say("/unpair 89abcdef") == "Removed."


def test_a_new_link_is_told_and_never_held(calls):
    c = calls.app.modules["calls"]
    c.on_event({"name": "shortcut_made", "id": "0123abcd", "device": "89abcdef", "device_name": "iPhone"})
    last = calls.fake.texts()[-1]
    assert "Tell Kurooto link was made on iPhone" in last and "revoke it on the dashboard" in last
    r = calm.REASONS["calls.shortcut_made"]
    assert r.exempt == "security" and r.stop is None


def test_the_dashboard_lists_and_revokes(calls):
    from kurooto.web.api import Api

    api = Api(calls.app)
    ph = api.get("phone")[1]
    assert ph["shortcuts"][0]["id"] == "0123abcd" and ph["devices"] == []
    assert api.post("phone/shortcut/revoke", {"id": "0123abcd"})[1] == {"ok": True}
    assert api.post("phone/shortcut/revoke", {"id": "0123abcd"})[1] == {"ok": False}
    calls.app.modules["calls"].connector.connected = False
    assert api.get("phone")[1]["shortcuts"] is None  # not asked while the line isn't connected


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node")
def test_the_phone_draws_the_same_qr_code_as_segno():
    # Data that fills each version exactly: segno pads a byte-aligned stream with a zero byte where the standard has
    # 0xEC (both scan), so padded codes differ in their pad codewords only.
    caps = [14, 26, 42, 62, 84, 106, 122, 152, 180, 213, 251, 287, 331, 362, 412, 450, 504, 560, 624, 666]
    base = "https://kurooto-abc.your-subdomain.workers.dev/tell/tk1.0123abcd." + "0123456789abcdef" * 45
    for version, n in enumerate(caps, 1):
        for mask in (version % 8, (version + 3) % 8):
            out = subprocess.run(["node", str(QR_JS), base[:n], str(mask)], capture_output=True, text=True, timeout=60)
            got = json.loads(out.stdout)
            want = segno.make(base[:n], error="m", mode="byte", version=version, mask=mask, boost_error=False, micro=0)
            rows = ["".join("1" if c & 1 else "0" for c in row) for row in want.matrix]
            assert got["version"] == version and got["rows"] == rows, (version, mask)
    # a real link: the smallest version that holds it, a mask of its own choosing, an SVG
    link = base[:111]
    got = json.loads(subprocess.run(["node", str(QR_JS), link], capture_output=True, text=True, timeout=60).stdout)
    assert got["version"] == segno.make(link, error="m", mode="byte", boost_error=False, micro=False).version
    assert 0 <= got["mask"] <= 7 and got["svg"] > 1000
