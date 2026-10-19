"""Pairing your Telegram during setup: the code is found however it's sent, a /start without it gets a hint, and
every reason it can't work (another program, a webhook, a revoked token, an old link, no internet) reaches the page."""

import json
import time
from importlib import resources

import pytest

from kurooto.app import App
from kurooto.modules.telegram import PairingProblem
from kurooto.web.api import Api
from tests.fakes.telegram import FakeTelegram


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    fake = FakeTelegram()
    app = App()
    app.settings.set("telegram.api_base", fake.base)
    yield app, app.modules["telegram"], fake, Api(app)
    fake.close()
    app.close()


def poll(api):
    return api.post("telegram/poll", {"wait": 0})[1]


@pytest.mark.parametrize(
    "sent", ["/start  {code}  ", "/start {upper}", "/start@kurooto_test_bot {code}", "/START {code}"]
)
def test_the_code_is_found_however_it_was_sent(env, sent):
    app, tg, fake, api = env
    code = tg.pair_start(fake.token)["code"]
    fake.message(sent.format(code=code, upper=code.upper()))
    assert poll(api)["paired"] is True
    assert app.settings.get("telegram.chat_id") == 7 and app.is_on("telegram")


def test_start_without_the_code_gets_a_hint_once(env):
    app, tg, fake, api = env
    code = tg.pair_start(fake.token)["code"]
    fake.message("/start")
    r = poll(api)
    assert r["paired"] is False and r["problem"] == "no_code" and r["retry"] is True
    assert r["error"] == "Got a /start without the code: send the full message shown here."
    hint = fake.texts()[-1]
    assert hint.startswith("Almost:") and code not in hint and code.lower() not in hint.lower()
    fake.message("/start oldcode")  # an old link: the same hint, but not sent twice to the same chat
    n = len(fake.texts())
    assert poll(api)["problem"] == "no_code" and len(fake.texts()) == n
    fake.message("/start", chat=8, chat_type="group")  # groups are ignored
    assert poll(api) == {"paired": False}
    fake.message(f"/start {code}")
    assert poll(api)["paired"] is True


def test_another_program_reading_the_bot(env):
    app, tg, fake, api = env
    tg.pair_start(fake.token)
    fake.fail["getUpdates"] = (409, "Conflict: terminated by other getUpdates request")
    r = poll(api)
    assert r["problem"] == "conflict" and r["retry"] is True and "Another program is reading" in r["error"]
    assert "@BotFather" in r["error"]


def test_a_webhook_is_found_and_disconnected(env):
    app, tg, fake, api = env
    code = tg.pair_start(fake.token)["code"]
    fake.webhook = "https://example.org/hook"
    fake.fail["getUpdates"] = (409, "Conflict: can't use getUpdates method while webhook is active")
    r = poll(api)
    assert r["problem"] == "webhook" and "web address" in r["error"]
    assert api.post("telegram/webhook-off", {})[1] == {"ok": True}
    assert ("deleteWebhook", {"drop_pending_updates": False}) in fake.sent
    fake.message(f"/start {code}")
    assert poll(api)["paired"] is True


def test_revoked_token(env):
    app, tg, fake, api = env
    tg.pair_start(fake.token)
    fake.fail["getUpdates"] = (401, "Unauthorized")
    r = poll(api)
    assert r["problem"] == "revoked" and r["retry"] is False and r["error"].startswith("That token was revoked.")


def test_expired_link_and_a_new_one(env):
    app, tg, fake, api = env
    tg.pair_start(fake.token)
    f = tg.dir / "pairing.json"
    p = json.loads(f.read_text())
    p["created"] = time.time() - 3601
    f.write_text(json.dumps(p))
    r = poll(api)
    assert r["problem"] == "expired" and r["retry"] is False and r["error"] == "This link expired: get a new one."
    new = api.post("telegram/relink", {})[1]
    assert new["ok"] and new["code"] != p["code"] and new["link"].endswith(new["code"])
    fake.message(f"/start {new['code']}")
    assert poll(api)["paired"] is True


def test_no_internet(env, monkeypatch):
    app, tg, fake, api = env
    tg.pair_start(fake.token)
    app.settings.set("telegram.api_base", "http://127.0.0.1:9")  # nothing listens there
    r = poll(api)
    assert r["problem"] == "network" and r["retry"] is True and "Still trying" in r["error"]


def test_relink_without_a_token(env):
    app, tg, fake, api = env
    assert api.post("telegram/relink", {})[1] == {"ok": False, "error": "Paste your bot's token first."}
    with pytest.raises(PairingProblem):
        tg.pair_poll(wait=0)


def test_the_gateway_steps_aside_while_pairing(env):
    app, tg, fake, api = env
    assert tg.pairing() == {}
    tg.pair_start(fake.token)
    assert tg.pairing()["code"]


def test_setup_page_shows_errors_and_the_manual_message():
    js = resources.files("kurooto.web").joinpath("static", "setup.js").read_text(encoding="utf-8")
    assert "got.error" in js and "got.problem" in js and "got.retry === false" in js
    assert "If nothing happens, send this message to @" in js and "/start ${r.code}" in js
    assert '"telegram/webhook-off"' in js and '"telegram/relink"' in js and "Disconnect it" in js
    assert "Get a new link" in js and "Lost touch with Kurooto" in js
