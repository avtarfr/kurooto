import pytest

from kurooto.app import App
from kurooto.modules.telegram.api import TelegramError, split_text
from tests.fakes.telegram import FakeTelegram


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    fake = FakeTelegram()
    app = App()
    app.settings.set("telegram.api_base", fake.base)
    tg = app.modules["telegram"]
    yield app, tg, fake
    fake.close()
    app.close()


def pair(app, tg, fake):
    link = tg.pair_start(fake.token)
    fake.message("hello")  # someone types before tapping the link: ignored
    fake.message(f"/start {link['code']}")
    return link, tg.pair_poll(wait=0)


def test_wrong_token_is_refused(env):
    app, tg, fake = env
    with pytest.raises(TelegramError):
        tg.check_token("999:wrong")


def test_pairing_learns_the_chat_and_says_hi(env):
    app, tg, fake = env
    assert app.enable("telegram")[0] is False
    link, got = pair(app, tg, fake)
    assert link["link"] == f"https://t.me/kurooto_test_bot?start={link['code']}"
    assert got == {"chat_id": 7, "name": "Friend"}
    assert app.settings.get("telegram.allowed_users") == [7]
    assert any("This chat is now ours" in t for t in fake.texts())
    assert app.enable("telegram") == (True, "Telegram is on")


def test_messages_route_to_commands_and_strangers_are_ignored(env):
    app, tg, fake = env
    pair(app, tg, fake)
    app.enable("telegram")
    fake.sent.clear()
    api = tg.api()
    allowed = {7}
    tg._update(api, {"update_id": 1, "message": fake.message("/hold 2h")}, allowed)
    tg._update(api, {"update_id": 2, "message": fake.message("/status")}, allowed)
    tg._update(api, {"update_id": 3, "message": fake.message("/status", user=666, chat=666)}, allowed)
    tg._update(api, {"update_id": 4, "message": fake.message("/status", chat_type="group")}, allowed)
    tg._update(api, {"update_id": 5, "message": fake.message("what's the capital of France?")}, allowed)
    texts = fake.texts()
    assert texts[0].startswith("No calls until") and texts[1].startswith("Calls: held")
    assert len(texts) == 3 and "turn on Chat" in texts[2]
    assert app.availability.quiet_until() is not None


def test_notify_goes_to_telegram_and_maps_replies(env):
    app, tg, fake = env
    pair(app, tg, fake)
    app.enable("telegram")
    mid = app.notify(
        "Due tomorrow: essay", kind="deadline", buttons=[[("Done", "dl:1:done")]], map_kind="question", map_ref="q1"
    )
    assert tg.map_get(mid) == {"kind": "question", "ref": "q1", "ts": tg.map_get(mid)["ts"]}
    last = [p for m, p in fake.sent if m == "sendMessage"][-1]
    assert last["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "dl:1:done"


def test_buttons_reach_the_module_and_answer(env):
    app, tg, fake = env
    pair(app, tg, fake)
    app.enable("telegram")
    tg._update(tg.api(), {"update_id": 9, "callback_query": {"id": "c", "from": {"id": 7}, "data": "zzz:1:x"}}, {7})
    method, params = fake.sent[-1]
    assert method == "answerCallbackQuery" and "feature that's off" in params["text"]


def test_files_land_in_the_workspace_inbox(env):
    app, tg, fake = env
    pair(app, tg, fake)
    app.enable("telegram")
    fake.files["docs/F1.pdf"] = b"%PDF-1.4 hello"
    tg._update(
        tg.api(),
        {"update_id": 10, "message": fake.message("", document={"file_id": "F1", "file_name": "notes.pdf"})},
        {7},
    )
    got = list((app.workspace / "inbox").glob("*notes.pdf"))
    assert len(got) == 1 and got[0].read_bytes() == b"%PDF-1.4 hello"


def test_focus_holds_messages_until_it_ends(env):
    app, tg, fake = env
    pair(app, tg, fake)
    app.enable("telegram")
    api = tg.api()
    tg._update(api, {"update_id": 11, "message": fake.message("/focus 2h")}, {7})
    before = len(fake.texts())
    app.notify("not urgent")
    assert len(fake.texts()) == before
    app.notify("the alarm", kind="call")
    assert len(fake.texts()) == before + 1
    tg._update(api, {"update_id": 12, "message": fake.message("/focus off")}, {7})
    assert "not urgent" in fake.texts() and "1 message waited" in fake.texts()[-1]


def test_long_text_splits_at_lines():
    parts = split_text(("line\n" * 2000).strip(), limit=3900)
    assert len(parts) == 3 and all(len(p) <= 3900 for p in parts) and not parts[1].startswith("\n")


def test_renaming_the_assistant_renames_the_bot_and_says_so_once(env):
    app, tg, fake = env
    pair(app, tg, fake)
    assert tg.name_changed() is False  # the first time it only remembers the name
    app.settings.set("you.assistant_name", "Jarvis")
    assert tg.name_changed() is True
    assert any(m == "setMyName" and p.get("name") == "Jarvis" for m, p in fake.sent)
    assert tg.name_changed() is False  # nothing new
