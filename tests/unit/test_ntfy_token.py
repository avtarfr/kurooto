"""An ntfy account token: set from the Phone tab or the setup page (checked with ntfy first), used when publishing with
a fallback to no token, and suggested by the health check once ntfy refuses rings for the shared address (429)."""

import urllib.error

import pytest

import kurooto.modules.calls as calls_mod
from kurooto.modules.calls import deploy
from kurooto.web.api import Api


@pytest.fixture
def calls(env, monkeypatch):
    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    env.on("calls")
    c = env.app.modules["calls"]
    monkeypatch.setattr(type(c.connector), "connected", property(lambda self: True))
    return env, c


class Sent:
    def __init__(self, codes):
        self.codes, self.auth = list(codes), []

    def __call__(self, req, timeout=10):
        self.auth.append(req.headers.get("Authorization"))
        code = self.codes.pop(0)
        if code != 200:
            raise urllib.error.HTTPError(req.full_url, code, "no", {}, None)

        class R:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return R()


def test_set_from_the_phone_tab_checked_first(calls, monkeypatch):
    env, c = calls
    monkeypatch.setattr(calls_mod, "check_ntfy_token", lambda server, tok: ("", "ntfy didn't accept that token."))
    r = Api(env.app).post("phone/ntfy", {"token": "tk_bad"})[1]
    assert r == {"ok": False, "message": "ntfy didn't accept that token."}
    assert not env.app.secrets.get("calls.ntfy_token")
    monkeypatch.setattr(calls_mod, "check_ntfy_token", lambda server, tok: ("lena", ""))
    monkeypatch.setattr(deploy, "needs_redeploy", lambda app: False)
    r = Api(env.app).post("phone/ntfy", {"token": "tk_good"})[1]
    assert r["ok"] and "(lena)" in r["message"] and env.app.secrets.get("calls.ntfy_token") == "tk_good"
    assert Api(env.app).get("phone")[1]["ntfy_token"] is True
    assert Api(env.app).post("phone/ntfy", {"token": ""})[1]["ok"]
    assert not env.app.secrets.get("calls.ntfy_token")


def test_publish_with_the_token_then_without_when_refused(calls, monkeypatch):
    env, c = calls
    env.app.secrets.set("calls.ntfy_token", "tk_x")
    sent = Sent([401, 200])
    monkeypatch.setattr(calls_mod.urllib.request, "urlopen", sent)
    assert c.publish_ntfy({"title": "t", "message": "m"})
    assert sent.auth == ["Bearer tk_x", None]


def test_refused_for_the_shared_address_the_health_check_suggests_a_token(calls, monkeypatch):
    env, c = calls
    assert c.health() == (True, "")
    monkeypatch.setattr(calls_mod.urllib.request, "urlopen", Sent([429]))
    assert not c.publish_ntfy({"title": "t", "message": "m"})
    ok, why = c.health()
    assert not ok and "ntfy refused 1 ring" in why and "Phone tab" in why
    env.app.secrets.set("calls.ntfy_token", "tk_x")
    assert c.health() == (True, "")
