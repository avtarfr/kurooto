import json
import urllib.error
import urllib.request

import pytest

from kurooto.app import App
from kurooto.web.server import start
from tests.fakes.openai import FakeOpenAI
from tests.fakes.telegram import FakeTelegram


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    srv = start(app, port=18770)
    yield app, srv
    srv.stop()
    app.close()


def call(srv, path, body=None, headers=None, token=True):
    h = {"Content-Type": "application/json", **(headers or {})}
    if token:
        h["X-Kurooto"] = srv.token
    req = urllib.request.Request(
        srv.url.rstrip("/") + path,
        data=None if body is None else json.dumps(body).encode(),
        headers=h,
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (
                json.loads(raw) if r.headers.get("Content-Type", "").startswith("application/json") else raw.decode()
            )
    except urllib.error.HTTPError as e:
        return e.code, None


def test_protections(web):
    app, srv = web
    assert call(srv, "/health", token=False) == (200, {"ok": True, "version": call(srv, "/health")[1]["version"]})
    assert call(srv, "/api/state", token=False)[0] == 401
    assert call(srv, "/api/state", headers={"Host": "evil.example:18770"})[0] == 403
    assert call(srv, "/api/you", {"name": "x"}, headers={"Origin": "https://evil.example"})[0] == 403
    assert call(srv, "/static/../server.py")[0] == 404
    code, page = call(srv, "/setup", token=False)
    assert code == 200 and srv.token in page and "Set up Kurooto" in page


def test_a_bad_content_length_is_refused(web):
    import http.client

    app, srv = web
    for length, want in (("abc", 400), ("-1", 400), ("5000000", 413)):
        c = http.client.HTTPConnection("127.0.0.1", 18770, timeout=5)
        c.putrequest("POST", "/api/you")
        for k, v in (("X-Kurooto", srv.token), ("Content-Type", "application/json"), ("Content-Length", length)):
            c.putheader(k, v)
        c.endheaders()
        assert c.getresponse().status == want
        c.close()


def test_wizard_end_to_end(web):
    app, srv = web
    fake_tg, ai = FakeTelegram(), FakeOpenAI()
    try:
        app.settings.set("telegram.api_base", fake_tg.base)
        assert call(srv, "/api/you", {"name": "Riya", "timezone": "Europe/Berlin"})[1] == {
            "ok": True,
            "timezone": "Europe/Berlin",
        }
        st = call(srv, "/api/state")[1]
        assert st["you"]["name"] == "Riya" and st["brains"][0]["id"] == "agy" and st["brains"][0]["recommended"]
        assert st["hardware"]["recommendation"]["profile"] and "need_gb" in st["room"]
        call(
            srv,
            "/api/brain",
            {
                "main": "custom",
                "key": ai.key,
                "base_url": ai.base,
                "models": {"low": "fast", "medium": "fast", "high": "fast"},
            },
        )
        ai.answer = "KUROOTO-OK-0000"
        r = call(srv, "/api/brain/test", {"which": "custom"})[1]
        assert r["ok"] is False and "not as asked" in r["message"]
        bad = call(srv, "/api/telegram/token", {"token": "999:nope"})[1]
        assert bad == {"ok": False, "error": "Telegram didn't accept that token."}
        link = call(srv, "/api/telegram/token", {"token": fake_tg.token})[1]
        assert link["ok"] and link["link"].startswith("https://t.me/kurooto_test_bot?start=")
        fake_tg.message(f"/start {link['code']}")
        assert call(srv, "/api/telegram/poll", {"wait": 0})[1]["paired"] is True
        res = call(srv, "/api/modules/enable", {"ids": ["reminders", "chat", "deadlines"]})[1]["results"]
        assert all(v["ok"] for v in res.values()), res
        assert call(srv, "/api/setup/done", {})[1] == {"ok": True}
        assert "is set up" in fake_tg.texts()[-1] and app.settings.get("setup.done") is True
    finally:
        fake_tg.close()
        ai.close()


def test_brain_test_passes_when_it_echoes(web, monkeypatch):
    app, srv = web
    ai = FakeOpenAI()
    try:
        call(
            srv,
            "/api/brain",
            {"main": "custom", "key": ai.key, "base_url": ai.base, "models": {"medium": "m", "low": "m"}},
        )
        import kurooto.web.api as api_mod

        monkeypatch.setattr(api_mod.secrets, "randbelow", lambda n: 1234)
        ai.answer = "KUROOTO-OK-2234"
        assert call(srv, "/api/brain/test", {"which": "custom"})[1]["ok"] is True
    finally:
        ai.close()
