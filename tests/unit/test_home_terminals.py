"""home: the dashboard's terminals: who may use them (the Linux socket-owner check, refusing when unsure), a terminal's
life (start on first open, replay for a page that opens later, output only to the pages showing it, start again after
it ends), a real program in a real pty, and the web endpoints and vendored xterm.js."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

import pytest

from kurooto.modules import catalog
from kurooto.modules.backups import Backups
from kurooto.modules.terminals import Term, Terminals, _cli_has, peer_uid, same_user


@pytest.fixture(autouse=True)
def registered(monkeypatch):
    extra = [c for c in (Backups, Terminals) if c not in catalog.CATALOG]
    monkeypatch.setattr(catalog, "CATALOG", [*catalog.CATALOG, *extra])


HEAD = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"


def row(n, local, remote, uid):
    return f"  {n}: 0100007F:{local:04X} 0100007F:{remote:04X} 01 00000000:00000000 00:00000000 00000000  {uid}  0 1\n"


def test_who_is_connecting(tmp_path):
    (tmp_path / "tcp").write_text(
        HEAD + row(0, 8770, 51000, 1000) + row(1, 51000, 8770, 1000) + row(2, 52000, 8770, 1001)
    )
    assert peer_uid(51000, 8770, str(tmp_path)) == 1000
    assert peer_uid(52000, 8770, str(tmp_path)) == 1001
    assert peer_uid(53000, 8770, str(tmp_path)) is None
    if sys.platform == "linux":
        me = os.getuid()
        (tmp_path / "tcp").write_text(HEAD + row(0, 51000, 8770, me) + row(1, 52000, 8770, me + 1))
        assert same_user(("127.0.0.1", 51000), 8770, "linux", str(tmp_path)) is True
        assert same_user(("127.0.0.1", 52000), 8770, "linux", str(tmp_path)) is False  # another account
        assert same_user(("127.0.0.1", 53000), 8770, "linux", str(tmp_path)) is False  # can't tell: refused
        assert same_user(("127.0.0.1", 51000), 8770, "linux", str(tmp_path / "missing")) is False
    assert same_user(("127.0.0.1", 1), 8770, "darwin") is True  # elsewhere: the dashboard's own protections


class FakePty:
    made: list = []

    def __init__(self, argv, cwd, env, cols, rows):
        self.argv, self.size, self.written, self.out = argv, (cols, rows), [], [b"hello\r\n"]
        self.ended = False
        FakePty.made.append(self)

    def read(self):
        while not self.out and not self.ended:
            time.sleep(0.01)
        return self.out.pop(0) if self.out else b""

    def write(self, data):
        self.written.append(data)
        self.out.append(b"echo:" + data)

    def resize(self, cols, rows):
        self.size = (cols, rows)

    def exit_code(self):
        return 0

    def kill(self):
        self.ended = True


def test_a_terminals_life():
    FakePty.made = []
    pushed = []
    t = Term(
        "shell", {"argv": ["sh"], "cwd": "/", "env": {}}, lambda n, d, v, r: pushed.append((d, set(v), r)), FakePty
    )
    t.attach("page1", 100, 30)
    assert len(FakePty.made) == 1 and FakePty.made[0].size == (100, 30)
    assert pushed[0] == (b"", {"page1"}, True)  # the replay (empty at first)
    assert wait(lambda: (b"hello\r\n", {"page1"}, False) in pushed)
    t.write(b"ls\r")
    assert wait(lambda: any(d == b"echo:ls\r" for d, _, _ in pushed))
    t.attach("page2", 80, 24)  # a page opening later gets the screen so far, only it
    assert pushed[-1][1] == {"page2"} and pushed[-1][2] is True and b"hello" in pushed[-1][0]
    assert FakePty.made[0].size == (80, 24)
    t.resize("page1", 120, 40)
    assert FakePty.made[0].size == (120, 40)
    t.resize("stranger", 20, 5)
    assert FakePty.made[0].size == (120, 40)
    t.leave("page2")
    assert t.viewers == {"page1"}
    FakePty.made[0].ended = True  # the program ends
    assert wait(lambda: not t.alive and b"press a key" in bytes(t.buf))
    t.write(b"x")  # a key starts it again
    assert len(FakePty.made) == 2 and t.alive
    t.stop()
    assert not t.alive and FakePty.made[1].ended


def wait(cond, seconds=5):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_a_missing_program_says_so():
    pushed = []

    def boom(*a):
        raise FileNotFoundError("no such program")

    t = Term("agent", {"argv": ["nope"], "cwd": "/", "env": {}}, lambda n, d, v, r: pushed.append(d), boom)
    t.attach("p", 80, 24)
    assert not t.alive and b"couldn't start nope" in bytes(t.buf)


def test_profiles(env, monkeypatch):
    app = env.app
    tm = app.modules["terminals"]
    assert tm.ready()[0]
    assert _cli_has("top") is True and _cli_has("no-such-command") is False
    names = list(tm.profiles())
    assert "shell" in names and "logs" in names
    assert ("ask" in names) == _cli_has("ask")  # only once `kurooto ask` exists
    assert tm.profiles()["logs"]["argv"][-3:] == ["kurooto", "logs", "-f"]
    assert "agent" not in names  # no AI program picked yet
    monkeypatch.setattr("kurooto.modules.terminals._cli_has", lambda c: True)
    app.settings.set("brain.main", "agy")
    from kurooto import providers

    class FakeAgy:
        kind, label, exe = "cli", "Antigravity", "/opt/agy/agy"

    monkeypatch.setattr(providers, "build", lambda a, which: FakeAgy())
    tm.refresh()
    prof = tm.profiles()
    assert list(prof)[:2] == ["agent", "shell"] and prof["agent"]["argv"] == ["/opt/agy/agy"]
    assert prof["agent"]["cwd"] == str(app.workspace) and "ask" in prof
    assert prof["shell"]["env"]["TERM"] == "xterm-256color"


PROGRAM = """import os, sys
s = os.get_terminal_size(0)
print('ready', s.columns, s.lines, 'ctty', os.tcgetpgrp(0) == os.getpgrp(), flush=True)
print('got', input(), flush=True)
input()
s = os.get_terminal_size(0)
print('size', s.columns, s.lines, flush=True)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="the Unix pty; Windows uses pywinpty")
@pytest.mark.filterwarnings("error::DeprecationWarning")  # no os.forkpty in a many-threaded process
def test_a_real_program_in_a_real_pty(env):
    app = env.app
    env.on("terminals")
    tm = app.modules["terminals"]
    tm.refresh()
    prof = {"title": "Shell", "argv": [sys.executable, "-c", PROGRAM], "cwd": str(app.workspace), "env": {**os.environ}}
    tm.profiles()["shell"] = prof
    got = []

    class Live:
        def push(self, msg, only=None):
            got.append((msg, only))

    app.live = Live()
    buf = lambda: bytes(tm.terms["shell"].buf)  # noqa: E731
    assert tm.handle("shell", "attach", {"cid": 1, "cols": 90, "rows": 20}) == (200, {"ok": True, "alive": True})
    assert wait(lambda: b"ready 90 20 ctty True" in buf()), buf()  # the pty is its controlling terminal
    tm.handle("shell", "input", {"data": "hi there\r"})
    assert wait(lambda: b"got hi there" in buf())
    tm.handle("shell", "resize", {"cid": 1, "cols": 100, "rows": 30})
    tm.handle("shell", "input", {"data": "\r"})
    assert wait(lambda: b"size 100 30" in buf()), buf()
    assert wait(lambda: b"[shell ended" in buf())
    assert all(only == {1} for _, only in got) and got[0][0]["replay"] is True
    assert tm.handle("nope", "attach", {"cid": 1})[0] == 404
    assert tm.handle("shell", "dance", {"cid": 1})[0] == 404
    assert tm.handle("shell", "input", {"data": "x" * 200_000})[0] == 413
    # Ctrl+C reaches the program through the terminal, as in any terminal window
    prof["argv"] = [sys.executable, "-c", "import time; print('sleeping', flush=True); time.sleep(60)"]
    tm.handle("shell", "restart", {})
    assert wait(lambda: b"sleeping" in buf())
    t0 = time.monotonic()
    tm.handle("shell", "input", {"data": "\x03"})
    assert wait(lambda: b"[shell ended" in buf()) and time.monotonic() - t0 < 5
    # restarting a running program hangs up on the old one
    tm.handle("shell", "restart", {})
    assert wait(lambda: b"sleeping" in buf())
    old = tm.terms["shell"].pty
    tm.handle("shell", "restart", {})
    assert old.alive() is False and wait(lambda: b"sleeping" in buf())
    tm.page_gone(1)
    assert tm.terms["shell"].viewers == set()
    app.disable("terminals")
    assert tm.terms == {}


@pytest.mark.skipif(sys.platform == "win32", reason="the Unix pty")
def test_a_missing_program_in_a_real_pty(tmp_path):
    from kurooto.modules.terminals import UnixPty

    with pytest.raises(FileNotFoundError):
        UnixPty(["definitely-not-a-program-here"], str(tmp_path), dict(os.environ), 80, 24)


def call(srv, path, body=None):
    req = urllib.request.Request(
        srv.url.rstrip("/") + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Kurooto": srv.token},
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def test_the_web_side(env, monkeypatch):
    from kurooto.web.server import start

    app = env.app
    srv = start(app, port=18920)
    try:
        assert json.loads(call(srv, "/api/term")[1]) == {"on": False, "terms": []}
        assert call(srv, "/api/term/shell/attach", {"cid": 1})[0] == 403  # off
        env.on("terminals")
        code, body = call(srv, "/api/term")
        names = [t["name"] for t in json.loads(body)["terms"]]
        assert code == 200 and "shell" in names  # this test runs as you: allowed
        monkeypatch.setattr("kurooto.web.peer.same_user", lambda *a, **k: False)
        assert call(srv, "/api/term")[0] == 403 and call(srv, "/api/term/shell/attach", {"cid": 1})[0] == 403
        monkeypatch.undo()
        code, js = call(srv, "/static/vendor/xterm/xterm.js")
        assert code == 200 and js.startswith(b"!function") and len(js) > 200_000
        assert call(srv, "/static/vendor/xterm/addon-fit.js")[0] == 200
        assert call(srv, "/static/vendor/xterm/xterm.css")[0] == 200
        assert call(srv, "/static/vendor/xterm/LICENSE")[0] == 404
        assert call(srv, "/static/vendor/../home.js")[0] == 404
        assert app.live is srv.live
    finally:
        srv.stop()
        app.modules["terminals"].shutdown()


def test_on_linux_every_page_and_api_call_must_be_this_account(env, monkeypatch):
    from kurooto.web import peer
    from kurooto.web.server import start

    app = env.app
    srv = start(app, port=18940)
    try:
        # this test runs as you: everything works (on Linux the kernel's socket table says so)
        assert call(srv, "/")[0] == 200 and call(srv, "/api/settings")[0] == 200
        assert call(srv, "/api/notify", {"text": "hi"})[0] == 200
        monkeypatch.setattr(peer, "same_user", lambda *a, **k: False)  # another account (or can't tell)
        for path in ("/", "/setup", "/api/settings", "/api/state", f"/api/stream?t={srv.token}", "/api/term"):
            assert call(srv, path)[0] == 403, path
        for path in ("/api/notify", "/api/settings", "/api/power/pause", "/api/term/shell/attach"):
            assert call(srv, path, {"text": "x"})[0] == 403, path
        assert call(srv, "/health")[0] == 200 and call(srv, "/static/home.js")[0] == 200  # nothing private
        monkeypatch.undo()
        if sys.platform == "linux":
            monkeypatch.setattr(peer, "peer_uid", lambda *a, **k: None)  # the owner can't be told: refused
            assert call(srv, "/api/settings")[0] == 403
            monkeypatch.setattr(peer, "peer_uid", lambda *a, **k: os.getuid() + 1)  # someone else
            assert call(srv, "/api/settings")[0] == 403 and call(srv, "/")[0] == 403
            monkeypatch.setattr(peer, "peer_uid", lambda *a, **k: os.getuid())
            assert call(srv, "/api/settings")[0] == 200
            monkeypatch.setattr(peer, "peer_uid", lambda *a, **k: 0)  # root can read it all anyway
            assert call(srv, "/api/settings")[0] == 200
    finally:
        srv.stop()
