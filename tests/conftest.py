import os

import pytest

from tests import isolation

isolation.start()  # before anything imports kurooto: a pretend home, stand-ins on PATH, the real-install guard


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
def env(tmp_path):
    from kurooto.app import App
    from tests.fakes.telegram import FakeTelegram

    with pytest.MonkeyPatch.context() as mp:  # its own: a test's `monkeypatch.undo()` keeps KUROOTO_HOME
        mp.setenv("KUROOTO_HOME", str(tmp_path))
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
def nowhere_real(tmp_path_factory):
    """Every test gets a pretend home of its own: HOME, USERPROFILE, the XDG folders, APPDATA, LOCALAPPDATA and
    KUROOTO_HOME (unless set for the run) point into a fresh temporary folder, Path.home() follows HOME, and secrets
    go to a file. A developer's real Kurooto (its folders, systemd unit, app-menu entries, ~/.gemini, its keychain
    entries) is never read or changed, even by a test that loses KUROOTO_HOME; tests/isolation.py guards it. Its own
    MonkeyPatch: a test's `monkeypatch.undo()` keeps the pretend home."""
    with pytest.MonkeyPatch.context() as mp:
        for k, v in isolation.pretend_home(tmp_path_factory.mktemp("home")).items():
            mp.setenv(k, v)
        mp.setenv("KUROOTO_SECRETS", "file")
        yield


@pytest.fixture(autouse=True)
def no_real_zotero(monkeypatch):
    """Research's Zotero (modules/zotero.py) never reaches a developer's running Zotero app or zotero.org: a port
    nothing listens on, and a host that doesn't exist. Tests that need one point these at a fake."""
    from kurooto.modules import zotero

    monkeypatch.setattr(zotero, "LOCAL", "http://127.0.0.1:9")
    monkeypatch.setattr(zotero, "WEB", "https://zotero.invalid")


@pytest.fixture(autouse=True)
def no_desktop_popups(monkeypatch):
    """Tests never show real desktop notifications or run the real loginctl, systemctl, launchctl or kurooto:
    do-nothing notify-send/osascript/powershell and refusing stand-ins come first on PATH (a developer's machine
    would otherwise get a popup for every test that notifies). tests/isolation.py makes them."""
    path = os.environ.get("PATH", "")
    if not path.startswith(str(isolation.BIN) + os.pathsep):
        monkeypatch.setenv("PATH", str(isolation.BIN) + os.pathsep + path)


@pytest.fixture(autouse=True)
def no_path_changes(monkeypatch):
    """Tests never edit a developer's real shell startup files or user PATH (core/pathfix.py)."""
    from kurooto.core import pathfix

    monkeypatch.setattr(pathfix, "allowed", lambda: False)


@pytest.fixture(autouse=True)
def calendar_day_checkins():
    """A check-in day runs 05:00 to 05:00 (checkins.day_starts). Tests written for calendar days must pass at any
    hour, 1 am included, so here it starts at midnight; tests/unit/test_ws3.py sets 05:00 itself. Its own
    MonkeyPatch: a test's `monkeypatch.undo()` mustn't drop it halfway through."""
    from kurooto.core import config
    from kurooto.modules import checkins  # noqa: F401 (registers its defaults)

    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(config._DEFAULTS["checkins"], "day_starts", "00:00")
        yield


@pytest.fixture(autouse=True)
def no_receipts():
    """Answers end with a run receipt (jobs.receipt, on by default). Tests that check an answer's exact words run
    without it; tests/unit/test_receipt.py turns it on. Its own MonkeyPatch, like calendar_day_checkins."""
    from kurooto.core import config, jobs  # noqa: F401 (registers its defaults)

    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(config._DEFAULTS["jobs"], "receipt", False)
        yield


# ------------------------------------------------------------------------------------- the real-install guard
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    isolation.current["test"] = item.nodeid
    yield
    isolation.current["test"] = None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """A test that touched the real install fails, whatever else it asserted."""
    outcome = yield
    rep = outcome.get_result()
    found = isolation.take(item.nodeid)
    if found:
        before = f"{rep.longrepr}\n\n" if rep.failed and rep.longrepr else ""
        rep.outcome, rep.longrepr = "failed", before + isolation.describe(found)


def pytest_sessionfinish(session, exitstatus):
    if [v for v in isolation.violations if not v.get("reported")] and session.exitstatus == 0:
        session.exitstatus = 1  # outside any test (collection, session fixtures): the run fails too


def pytest_terminal_summary(terminalreporter):
    tr, left = terminalreporter, [v for v in isolation.violations if not v.get("reported")]
    tests = {v["test"] for v in isolation.violations}
    tr.write_sep("-", "real-install guard")
    tr.write_line(
        f"{len(isolation.violations)} violation(s) in {len(tests)} test(s); "
        f"{len(isolation.reads)} read(s) of the real install's folders"
    )
    if left:
        tr.write_line(isolation.describe(left))
    for test in sorted({r["test"] or "(outside a test)" for r in isolation.reads}):
        tr.write_line(f"  read: {test}")


def pytest_unconfigure(config):
    isolation.finish()
