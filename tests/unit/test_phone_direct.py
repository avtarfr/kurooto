"""The computer's side of the Android app's own connection to the call line (0.7.0): a message for the phones goes to
the line's /send (HTTPS with the connector secret) when the line's WebSocket is down, and to ntfy from here only when
the line can't be reached or can't reach the phone; a ring the line delivered isn't published again, and with no
Android phone paired nothing is; the device list says which phones are connected (the Phone tab, the health check).
The Worker's side: tests/integration/test_phone_direct_line.py; the app's: android/test/LinkTest.java."""

import json
import urllib.error

import pytest

import kurooto.modules.calls as calls_mod
from kurooto.modules.calls import deploy
from kurooto.web.api import Api

LINE = "https://kurooto-abc.your-subdomain.workers.dev"


@pytest.fixture
def calls(env, monkeypatch):
    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": LINE})
    env.on("calls")
    return env, env.app.modules["calls"]


class Net:
    """Fake urlopen: the line's /send answers `line` (a dict, an HTTP code, or None: unreachable); ntfy answers 200."""

    def __init__(self, line):
        self.line, self.sent = line, []

    def __call__(self, req, timeout=10):
        url = req.full_url
        self.sent.append((url, dict(req.header_items()), json.loads(req.data or b"{}")))
        if url == LINE + "/send":
            if self.line is None:
                raise urllib.error.URLError("unreachable")
            if isinstance(self.line, int):
                raise urllib.error.HTTPError(url, self.line, "no", {}, None)
        body = json.dumps(self.line if url == LINE + "/send" else {"id": "1"}).encode()

        class R:
            status = 200

            def read(self, n=-1):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return R()

    def urls(self):
        return [u for u, _, _ in self.sent]


def use(monkeypatch, line):
    net = Net(line)
    monkeypatch.setattr(calls_mod.urllib.request, "urlopen", net)
    return net


def test_the_line_takes_it_and_ntfy_isnt_used(calls, monkeypatch):
    env, c = calls
    net = use(monkeypatch, {"ok": True, "android": True, "phones": 1})
    assert c.send_phones({"title": "stop", "message": "", "tags": ["stop", "since-1"]})
    assert net.urls() == [LINE + "/send"]
    _, headers, body = net.sent[0]
    assert headers["X-connector-secret"] == env.app.secrets.get("calls.connector_secret")
    assert body == {"fields": {"title": "stop", "message": "", "tags": ["stop", "since-1"]}, "assistant": env.app.name}


@pytest.mark.parametrize("line", [None, 404, 401, {"ok": True, "android": False, "phones": 1}])
def test_ntfy_from_here_when_the_line_cant(calls, monkeypatch, line):
    env, c = calls
    net = use(monkeypatch, line)  # unreachable, an older line (no /send), refused, or no way to the phone
    assert c.send_phones({"title": "t", "message": "m"})
    assert net.urls() == [LINE + "/send", "https://ntfy.sh/"]


def test_no_android_phone_nothing_is_published(calls, monkeypatch):
    env, c = calls
    net = use(monkeypatch, {"ok": True, "android": False, "phones": 0})
    assert not c.send_phones({"title": "t", "message": "m"})
    assert net.urls() == [LINE + "/send"]


def test_a_ring_the_line_delivered_isnt_published_again(calls, monkeypatch):
    env, c = calls
    published = []
    monkeypatch.setattr(c, "publish_ntfy", lambda fields: published.append(fields["title"]) or True)
    c._ring_fallback({"title": "Incoming call"}, {"android": True, "phones": 1})
    c._ring_fallback({"title": "Incoming call"}, {"android": False, "phones": 0})  # nobody to ring
    assert published == []
    c._ring_fallback({"title": "Incoming call"}, {"android": False})  # a line from before 0.7.0
    c._ring_fallback({"title": "Incoming call"}, None)  # no answer
    assert published == ["Incoming call", "Incoming call"]


def test_the_phone_tab_shows_who_is_connected(calls, monkeypatch):
    env, c = calls
    monkeypatch.setattr(type(c.connector), "connected", property(lambda self: True))
    devs = [
        {"id": "a1", "name": "Pixel", "kind": "android", "created": "2026-10-01", "connected": False, "heard": None},
        {"id": "w1", "name": "iPhone", "kind": "web", "created": "2026-10-02", "push": True},
    ]
    monkeypatch.setattr(c.connector, "admin_wait", lambda op, **kw: {"devices": devs} if op == "devices" else {})
    ph = Api(env.app).get("phone")[1]
    assert ph["devices"][0]["connected"] is False and not c.phones_direct()
    devs[0]["connected"] = True
    Api(env.app).get("phone")
    assert c.phones_direct()
