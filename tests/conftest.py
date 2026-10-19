import pytest

from kurooto.app import App
from tests.fakes.telegram import FakeTelegram


class Env:
    """A paired assistant talking to a fake Telegram, with a helper to send it messages."""

    def __init__(self, app, tg, fake):
        self.app, self.tg, self.fake = app, tg, fake
        self.n = 1000

    def say(self, text="", **extra):
        self.n += 1
        self.tg._update(self.tg.api(), {"update_id": self.n, "message": self.fake.message(text, **extra)}, {7})
        return self.fake.texts()[-1] if self.fake.texts() else None

    def press(self, data):
        self.n += 1
        self.tg._update(
            self.tg.api(), {"update_id": self.n, "callback_query": {"id": "c", "from": {"id": 7}, "data": data}}, {7}
        )
        return [p for m, p in self.fake.sent if m == "answerCallbackQuery"][-1]["text"]

    def reply_to_last(self, text):
        mid = max(
            int(k)
            for k in (self.tg.dir / "map.json").read_text()
            and __import__("json").loads((self.tg.dir / "map.json").read_text())
        )
        return self.say(text, reply_to_message={"message_id": mid})

    def on(self, *ids):
        for i in ids:
            ok, why = self.app.enable(i)
            assert ok, why


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    fake = FakeTelegram()
    app = App()
    app.settings.set("telegram.api_base", fake.base)
    tg = app.modules["telegram"]
    link = tg.pair_start(fake.token)
    fake.message(f"/start {link['code']}")
    tg.pair_poll(wait=0)
    app.enable("telegram")
    yield Env(app, tg, fake)
    fake.close()
    app.close()


@pytest.fixture(autouse=True)
def no_desktop_popups(tmp_path_factory, monkeypatch):
    """Tests never show real desktop notifications: do-nothing notify-send/osascript/powershell come first on PATH
    (a developer's machine would otherwise get a popup for every test that notifies)."""
    import os
    import sys

    d = tmp_path_factory.mktemp("quiet-bin")
    for name in ("notify-send", "osascript"):
        f = d / name
        f.write_text("#!/bin/sh\nexit 0\n")
        f.chmod(0o755)
    if sys.platform == "win32":
        (d / "powershell.cmd").write_text("@exit /b 0\r\n")
    monkeypatch.setenv("PATH", str(d) + os.pathsep + os.environ.get("PATH", ""))


@pytest.fixture(autouse=True)
def no_path_changes(monkeypatch):
    """Tests never edit a developer's real shell startup files or user PATH (core/pathfix.py)."""
    from kurooto.core import pathfix

    monkeypatch.setattr(pathfix, "allowed", lambda: False)
