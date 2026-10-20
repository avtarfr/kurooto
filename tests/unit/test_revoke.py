"""Leaving cleanly and new keys (core/leave.py): `kurooto uninstall --revoke` and `kurooto rotate`, with a stand-in
wrangler (a small script run in place of Node, so the real subprocess path and wrangler's own login folder are used),
a fake Google revoke endpoint and a fake Telegram. Nothing here reaches Cloudflare, Google or Telegram."""

from __future__ import annotations

import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from kurooto import cli
from kurooto.app import App
from kurooto.core import leave
from kurooto.core.health import Check
from kurooto.core.secrets import Secrets
from kurooto.modules.calls import deploy
from tests.fakes.telegram import FakeTelegram

ACCOUNT = "a" * 32
OTHER = "b" * 32
NAME = "kurooto-abc123"
URL = f"https://{NAME}.k-test.workers.dev"

WRANGLER = r"""
import json, os, sys
from pathlib import Path

here = Path(__file__).resolve().parent
st = json.loads((here / "state.json").read_text())
args = sys.argv[1:]
rec = {"args": args, "account": os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""), "home": os.environ.get("HOME", "")}
if args[:2] == ["secret", "bulk"]:
    rec["secrets"] = json.loads(sys.stdin.read())
with (here / "calls.jsonl").open("a") as f:
    f.write(json.dumps(rec) + "\n")
cmd = args[0] if args else ""
if cmd == "whoami":
    if not st.get("authed"):
        print("You are not authenticated. Please run `wrangler login`.")
    else:
        print("You are logged in with an OAuth Token.")
        for a in st["accounts"]:
            print(f"| Sam's Account | {a} |")
elif cmd == "delete":
    if st.get("delete") == "gone":
        print("X [ERROR] This Worker does not exist on your account. [code: 10007]", file=sys.stderr)
        sys.exit(1)
    if st.get("delete") == "fail":
        print("X [ERROR] A request to the Cloudflare API failed. Authentication error [code: 10000]", file=sys.stderr)
        sys.exit(1)
    print("Successfully deleted " + args[args.index("--name") + 1])
elif cmd == "logout":
    print("Successfully logged out.")
elif cmd == "deploy":
    print("Uploaded")
    sys.exit(st.get("deploy_code", 0))
elif cmd == "secret":
    print("Finished processing secrets")
    sys.exit(st.get("secret_code", 0))
"""


class Wrangler:
    """The stand-in wrangler in the call line's folder; `.state` says how it answers, `.calls()` what it was asked."""

    def __init__(self, app_dir: Path):
        self.dir = app_dir / "call-line" / "node_modules" / "wrangler" / "bin"
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "wrangler.js").write_text(WRANGLER, encoding="utf-8")
        self.set(authed=True, accounts=[ACCOUNT], delete="ok")

    def set(self, **state) -> None:
        old = json.loads((self.dir / "state.json").read_text()) if (self.dir / "state.json").exists() else {}
        (self.dir / "state.json").write_text(json.dumps({**old, **state}))

    def calls(self) -> list[dict]:
        f = self.dir / "calls.jsonl"
        return [json.loads(ln) for ln in f.read_text().splitlines()] if f.exists() else []

    def cmds(self) -> list[str]:
        return [c["args"][0] for c in self.calls()]


class FakeRevoke:
    """Google's revoke endpoint: records the tokens; `ended` ones answer 400 invalid_token."""

    def __init__(self):
        self.tokens: list[str] = []
        self.ended: set[str] = set()
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
                tok = urllib.parse.parse_qs(raw).get("token", [""])[0]
                fake.tokens.append(tok)
                code, body = (400, {"error": "invalid_token"}) if tok in fake.ended else (200, {})
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/revoke"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    monkeypatch.setenv("KUROOTO_NO_AUTOSTART", "1")
    monkeypatch.setenv("KUROOTO_NO_BROWSER", "1")
    monkeypatch.setattr(cli, "BIN", tmp_path / "bin")
    monkeypatch.setattr(leave, "find_node", lambda d: sys.executable)  # Python runs the stand-in wrangler
    return tmp_path


@pytest.fixture
def fakes():
    tg, google = FakeTelegram(), FakeRevoke()
    yield tg, google
    tg.close()
    google.close()


def set_up_everything(app, tg, google) -> None:
    """A friend's Kurooto with a call line, two Google accounts, a bot and Notes sync."""
    s, sec = app.settings, app.secrets
    s.set("you.timezone", "Europe/Berlin")
    s.set("calls.worker", {"url": URL, "name": NAME, "account": ACCOUNT})
    sec.set("gemini.api_key", "gemini-key-123")
    deploy.ensure_secrets(app)
    sec.set("telegram.token", tg.token)
    s.set("telegram.api_base", tg.base)
    s.set("google.accounts", ["main", "school"])
    s.set("google.endpoints.revoke", google.url)
    sec.set("google.client", json.dumps({"installed": {"client_id": "id", "client_secret": "cs"}}))
    sec.set("google.tokens", json.dumps({"refresh_token": "r-main", "email": "sam@home.example"}))
    sec.set("google.tokens.school", json.dumps({"refresh_token": "r-school"}))
    sec.set("notes_sync.token", "ghp-notes-token")
    sec.set("calls.github_token", "ghp-notes-token")
    s.set("notes_sync.repo", "sam/notes")


# ==================================================================================== kurooto uninstall --revoke
def test_uninstall_revoke_takes_everything_back_then_removes_kurooto(home, fakes, capsys):
    tg, google = fakes
    app = App()
    set_up_everything(app, tg, google)
    wr = Wrangler(app.paths.app)
    app.close()

    assert cli.main(["uninstall", "--revoke"]) == 0
    out = capsys.readouterr().out

    calls = wr.calls()
    assert [c["args"][0] for c in calls] == ["whoami", "delete", "logout"]
    assert calls[1]["args"] == ["delete", "--name", NAME, "--force"] and calls[1]["account"] == ACCOUNT
    assert all(Path(c["home"]) == home / "config" / "cloudflare" for c in calls)  # Kurooto's own login only
    assert sorted(google.tokens) == ["r-main", "r-school"]
    sent = dict(tg.sent)
    assert sent["deleteWebhook"] == {"drop_pending_updates": True} and "deleteMyCommands" in sent
    assert f"ok    Call line: {NAME} is deleted" in out and "signed out" in out
    assert "ok    Google: Kurooto's access is taken back" in out and "ok    Google (school)" in out
    assert "ok    Telegram: your bot's webhook, waiting messages and command menu are cleared" in out
    assert f"GitHub: delete the token you made for Kurooto (sam/notes): {leave.GITHUB_TOKENS}" in out
    assert "/deletebot to @BotFather" in out and leave.GEMINI_KEYS in out and "OAuth client" in out
    assert "keys from this computer's keychain" in out
    assert "gemini-key-123" not in out and "ghp-notes-token" not in out and "r-main" not in out  # never printed
    assert not (home / "config").exists() and "Kurooto is uninstalled" in out


def test_revoke_with_keep_data_forgets_the_keys_and_the_line(home, fakes, capsys):
    tg, google = fakes
    app = App()
    set_up_everything(app, tg, google)
    Wrangler(app.paths.app)
    app.close()

    assert cli.main(["uninstall", "--revoke", "--keep-data"]) == 0
    app = App()
    try:
        assert Secrets(app.paths.config).names() == []
        assert app.secrets.get("google.tokens.school") is None and app.secrets.get("telegram.token") is None
        assert (app.settings.get("calls.worker") or {}).get("url") == ""  # a reinstall knows there's no line
        assert app.settings.get("notes_sync.repo") == "sam/notes"  # the rest of the settings stay
        kinds = [e["kind"] for e in app.events.tail(50)]
        assert "calls_line_deleted" in kinds and "revoked" in kinds
    finally:
        app.close()


def test_plain_uninstall_takes_nothing_back(home, fakes, capsys):
    tg, google = fakes
    app = App()
    set_up_everything(app, tg, google)
    wr = Wrangler(app.paths.app)
    app.close()
    assert cli.main(["uninstall", "--keep-data"]) == 0
    assert wr.calls() == [] and google.tokens == [] and tg.sent == []


def test_an_expired_cloudflare_login_gives_the_dashboard_steps(home):
    app = App()
    try:
        app.settings.set("calls.worker", {"url": URL, "name": NAME, "account": ACCOUNT})
        wr = Wrangler(app.paths.app)
        wr.set(authed=False)
        st = leave.delete_line(app, lambda s: None)
        assert st.ok is False and "expired" in st.detail
        assert "dash.cloudflare.com" in st.by_hand and NAME in st.by_hand and "Delete" in st.by_hand
        assert wr.cmds() == ["whoami"]  # nothing deleted, no sign-in page opened
        assert app.settings.get("calls.worker")["url"] == URL
    finally:
        app.close()


def test_never_deletes_on_another_cloudflare_account(home):
    app = App()
    try:
        app.settings.set("calls.worker", {"url": URL, "name": NAME, "account": ACCOUNT})
        wr = Wrangler(app.paths.app)
        wr.set(accounts=[OTHER])
        st = leave.delete_line(app, lambda s: None)
        assert st.ok is False and "isn't for the account" in st.detail and wr.cmds() == ["whoami"]
        wr.set(accounts=[OTHER, ACCOUNT])  # several accounts: the line's own one is used
        assert leave.delete_line(app, lambda s: None, sign_out=False).ok is True
        assert wr.calls()[-1]["account"] == ACCOUNT and "logout" not in wr.cmds()
    finally:
        app.close()


def test_a_line_deleted_already_counts_and_a_refusal_gives_steps(home):
    app = App()
    try:
        wr = Wrangler(app.paths.app)
        app.settings.set("calls.worker", {"url": URL, "name": NAME, "account": ACCOUNT})
        wr.set(delete="fail")
        st = leave.delete_line(app, lambda s: None)
        assert st.ok is False and "Authentication error" in st.detail and "Workers & Pages" in st.by_hand
        assert "logout" in wr.cmds()  # Kurooto's sign-in is signed out either way
        wr.set(delete="gone")
        assert leave.delete_line(app, lambda s: None).ok is True
        assert leave.delete_line(app, lambda s: None).ok is None  # forgotten: nothing left to delete
    finally:
        app.close()


def test_without_the_cloudflare_tools_you_get_the_steps(home):
    app = App()
    try:
        app.settings.set("calls.worker", {"url": URL, "name": NAME})
        st = leave.delete_line(app, lambda s: None)  # no call-line folder: never set up on this computer
        assert st.ok is False and "aren't on this computer" in st.detail and NAME in st.by_hand
    finally:
        app.close()


def test_google_ended_and_unreachable_sign_ins(home, fakes):
    tg, google = fakes
    app = App()
    try:
        app.settings.set("google.accounts", ["main", "school"])
        app.settings.set("google.endpoints.revoke", google.url)
        app.secrets.set("google.tokens", json.dumps({"access_token": "a-main", "email": "sam@home.example"}))
        app.secrets.set("google.tokens.school", json.dumps({"refresh_token": "r-school"}))
        google.ended.add("a-main")
        main, school = leave.revoke_google(app)
        assert main.ok is True and "already ended" in main.detail
        assert school.ok is True and google.tokens == ["a-main", "r-school"]
        google.close()  # Google can't be reached
        main, school = leave.revoke_google(app)
        assert main.ok is False and "couldn't reach Google" in main.detail
        assert leave.GOOGLE_CONNECTIONS in main.by_hand and "sam@home.example" in main.by_hand
        app.secrets.delete("google.tokens")
        app.secrets.delete("google.tokens.school")
        assert [s.ok for s in leave.revoke_google(app)] == [None]
    finally:
        app.close()


def test_telegram_a_revoked_token_and_no_bot(home, fakes):
    tg, google = fakes
    app = App()
    try:
        assert leave.clear_telegram(app).ok is None
        app.secrets.set("telegram.token", tg.token)
        app.settings.set("telegram.api_base", tg.base)
        tg.fail["deleteWebhook"] = (401, "Unauthorized")
        st = leave.clear_telegram(app)
        assert st.ok is True and "no longer works" in st.detail
        tg.fail["deleteWebhook"] = (500, "Internal error")
        assert leave.clear_telegram(app).ok is False
    finally:
        app.close()


def test_a_step_that_breaks_doesnt_stop_the_others(home, fakes, monkeypatch):
    tg, google = fakes
    app = App()
    try:
        app.secrets.set("telegram.token", tg.token)
        app.settings.set("telegram.api_base", tg.base)
        monkeypatch.setattr(leave, "delete_line", lambda app, say: 1 / 0)
        steps = leave.revoke_all(app, lambda s: None)
        assert steps[0].ok is False and "ZeroDivisionError" in steps[0].detail
        assert steps[-1].what == "Telegram" and steps[-1].ok is True
    finally:
        app.close()


def test_nothing_set_up_nothing_to_take_back(home, capsys):
    assert leave.uninstall_revoke(print) is True
    out = capsys.readouterr().out
    assert "--    Call line: none was set up" in out and "--    Telegram: no bot was set up" in out
    assert "Left for you" not in out and "keychain" not in out


# =========================================================================================== kurooto rotate
@pytest.fixture
def line_app(home, monkeypatch):
    """A Kurooto with a call line, deployed through the stand-in wrangler (no Node, no npm, no Cloudflare)."""

    def prepare(self):
        self.node = sys.executable
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "wrangler.template.toml").write_text((deploy.SOURCE / "wrangler.template.toml").read_text())

    monkeypatch.setattr(deploy.Deployer, "prepare", prepare)
    monkeypatch.setattr(deploy.Deployer, "subdomain", lambda self: "k-test")

    def sign_in(self, wait_s=600):  # the real one checks first; a sign-in page must never open here
        if not self.signed_in():
            pytest.fail("opened a sign-in page")

    monkeypatch.setattr(deploy.Deployer, "sign_in", sign_in)
    monkeypatch.setattr(deploy, "health", lambda url, timeout=10: {"ok": True, "version": "x"})
    app = App()
    app.settings.set("you.timezone", "Europe/Berlin")
    app.secrets.set("gemini.api_key", "gemini-key-123")
    app.settings.set("calls.worker", {"url": URL, "name": NAME, "account": ACCOUNT})
    deploy.ensure_secrets(app)
    wr = Wrangler(app.paths.app)
    yield app, wr
    app.close()


def keys(app) -> dict:
    return {k: app.secrets.get(k) for k in leave.LINE_KEYS}


def test_rotate_makes_new_keys_and_sends_them_to_the_same_line(line_app):
    app, wr = line_app
    old = keys(app)
    ok, msg = leave.rotate_line(app, lambda s: None)
    assert ok, msg
    new = keys(app)
    assert all(new[k] and new[k] != old[k] for k in leave.LINE_KEYS)
    assert wr.cmds() == ["whoami", "deploy", "secret"]
    sent = wr.calls()[-1]["secrets"]
    assert sent["CALL_SECRET"] == new["calls.call_secret"] and sent["CONNECTOR_SECRET"] == new["calls.connector_secret"]
    assert sent["NTFY_KEY"] == new["calls.ntfy_key"] and sent["NTFY_TOPIC"] == new["calls.ntfy_topic"]
    assert sent["VAPID_PUBLIC"] == new["calls.vapid_public"] and sent["GEMINI_API_KEY"] == "gemini-key-123"
    w = app.settings.get("calls.worker")
    assert w["name"] == NAME and w["url"] == URL  # the same address: phones pair again at the same place
    assert any(e["kind"] == "line_rotated" for e in app.events.tail(20))


def test_a_failed_redeploy_puts_the_old_keys_back(line_app, monkeypatch):
    app, wr = line_app
    old = keys(app)
    wr.set(secret_code=1)
    ok, msg = leave.rotate_line(app, lambda s: None)
    assert not ok and "secrets failed" in msg and keys(app) == old
    wr.set(secret_code=0)

    def interrupted(app, progress=print, unattended=False):
        raise KeyboardInterrupt

    monkeypatch.setattr(deploy, "deploy", interrupted)
    with pytest.raises(KeyboardInterrupt):
        leave.rotate_line(app, lambda s: None)
    assert keys(app) == old


def test_rotate_command_asks_first_then_walks_you_through_pairing(line_app, capsys):
    app, wr = line_app
    app.settings.set("modules.enabled", ["calls"])
    old = keys(app)
    app.close()  # the command makes its own, as `kurooto rotate` does

    assert leave.rotate_command(False, lambda p, b: pytest.fail("asked Kurooto"), print, interactive=False) == 2
    assert leave.rotate_command(False, lambda p, b: None, print, read=lambda q: "n") == 1

    def eof(q):
        raise EOFError

    assert leave.rotate_command(False, lambda p, b: None, print, read=eof) == 1  # Ctrl-D: no
    assert "Add --yes" in capsys.readouterr().out and wr.calls() == []

    answers = iter(
        [{"ok": False, "error": "not connected to your call line"}] * 2
        + [{"ok": True, "link": URL + "/pair#c=ABCD2345"}]
    )
    asked, slept = [], []

    def ask(path, body):
        asked.append(path)
        return next(answers)

    assert leave.rotate_command(False, ask, print, read=lambda q: "yes", sleep=slept.append) == 0
    out = capsys.readouterr().out
    assert asked == ["phone/pair"] * 3 and slept == [5, 5] and "Waiting for Kurooto" in out
    assert f"Pairing link (one phone, 15 minutes): {URL}/pair#c=ABCD2345" in out
    assert "Unpair this phone" in out and "Home Screen" in out and "Settings → Devices" in out
    assert "Gemini key" in out  # the credential list: the Gemini key is set
    app = App()
    try:
        assert keys(app) != old
    finally:
        app.close()


def test_rotate_when_kurooto_isnt_running_or_calls_are_off(line_app, capsys):
    app, wr = line_app
    app.settings.set("modules.enabled", ["calls"])
    assert leave.pair_again(app, lambda p, b: None, lambda s: None) is None
    leave._pair_steps(app, None, print)
    assert "Kurooto isn't running: `kurooto start`" in capsys.readouterr().out
    app.settings.set("modules.enabled", [])
    assert leave.pair_again(app, lambda p, b: pytest.fail("asked"), lambda s: None) is None
    leave._pair_steps(app, None, print)
    assert "Phone calls is off" in capsys.readouterr().out
    clock = iter(range(0, 1000, 100))
    r = leave.pair_again(
        _On(app),
        lambda p, b: {"ok": False, "error": "not connected"},
        lambda s: None,
        wait_s=150,
        sleep=lambda s: None,
        clock=lambda: next(clock),
    )
    assert r == {"ok": False, "error": "not connected"}  # gave up after the wait; the steps say what to do


class _On:
    """An app whose Phone calls is on (pair_again only asks that)."""

    def __init__(self, app):
        self.app = app

    def is_on(self, mid):
        return True


def test_rotate_without_a_call_line(home, capsys):
    app = App()
    app.secrets.set("gemini.api_key", "k")
    app.close()
    assert cli.main(["rotate", "--yes"]) == 1
    out = capsys.readouterr().out
    assert "no call line to give new keys" in out and leave.GEMINI_KEYS in out


def test_the_keys_only_you_can_replace_come_from_the_health_registry(env, monkeypatch):
    app = env.app
    ids = [c.id for c in app.health.credentials()]
    assert ids == ["telegram"]  # the features that are on and hold a sign-in
    lines = leave.credentials_by_hand(app)
    assert lines == [leave.REPLACE["telegram"]]
    rem = app.modules["reminders"]
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "reminders"])
    monkeypatch.setattr(
        rem, "health_check", lambda: Check("addon", "Your add-on's login", kind="credential", help="Sign in again.")
    )
    app.secrets.set("gemini.api_key", "k")
    lines = leave.credentials_by_hand(app)
    assert "Your add-on's login: Sign in again." in lines and lines[-1].startswith("Gemini key:")
