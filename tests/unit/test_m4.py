"""M4: the calendar (private iCal link), Notes sync (a local bare repository stands in for GitHub) and Google
(a fake Google: OAuth with PKCE, Classroom, Gmail drafts), including the sign-in page coming back to Kurooto."""

from __future__ import annotations

import base64
import datetime as dt
import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from email import message_from_bytes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

import pytest

from kurooto.modules import calendar as cal_mod
from kurooto.modules.google import NeedsSignIn
from tests.fakes.google import FakeGoogle


def serve(routes: dict):
    """A tiny local web server: {path: (status, body bytes or dict)}."""

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            code, body = routes.get(self.path.split("?")[0], (404, b"{}"))
            body = json.dumps(body).encode() if isinstance(body, dict) else body
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}"


# ------------------------------------------------------------------------------------------- calendar
BERLIN = ZoneInfo("Europe/Berlin")


def ics_for(today: dt.date) -> str:
    d = lambda x: (today + dt.timedelta(days=x)).strftime("%Y%m%d")  # noqa: E731
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            "UID:lec",
            "SUMMARY:Lecture",
            f"DTSTART;TZID=Europe/Berlin:{d(-7)}T100000",
            f"DTEND;TZID=Europe/Berlin:{d(-7)}T113000",
            f"RRULE:FREQ=WEEKLY;UNTIL={d(30)}",
            f"EXDATE;TZID=Europe/Berlin:{d(7)}T100000",
            "BEGIN:VALARM",
            "TRIGGER:-PT10M",
            "ACTION:DISPLAY",
            "END:VALARM",
            "END:VEVENT",
            "BEGIN:VEVENT",
            "UID:lec",
            f"RECURRENCE-ID;TZID=Europe/Berlin:{d(0)}T100000",
            "SUMMARY:Lecture (moved)",
            f"DTSTART;TZID=Europe/Berlin:{d(0)}T120000",
            f"DTEND;TZID=Europe/Berlin:{d(0)}T130000",
            "END:VEVENT",
            "BEGIN:VEVENT",
            "UID:trip",
            "SUMMARY:Trip\\, all day",
            f"DTSTART;VALUE=DATE:{d(1)}",
            f"DTEND;VALUE=DATE:{d(2)}",
            "END:VEVENT",
            "BEGIN:VEVENT",
            "UID:x",
            "SUMMARY:Cancelled thing",
            f"DTSTART;TZID=Europe/Berlin:{d(0)}T150000",
            f"DTEND;TZID=Europe/Berlin:{d(0)}T160000",
            "STATUS:CANCELLED",
            "END:VEVENT",
            "BEGIN:VEVENT",
            "UID:u",
            "SUMMARY:A very long title that is fol",
            " ded across lines",
            f"DTSTART:{d(0)}T170000Z",
            "DURATION:PT45M",
            "LOCATION:Room 1",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


@pytest.fixture
def calendar(env):
    env.app.settings.set("you.timezone", "Europe/Berlin")
    env.app.settings.set("calendar.days", 15)  # the day-14 lecture stays inside the window at any time of day
    today = dt.datetime.now(BERLIN).date()
    srv, base = serve({"/cal.ics": (200, ics_for(today).encode()), "/bad.ics": (200, b"<html>nope</html>")})
    yield env, base, today
    srv.shutdown()


def test_ics_parsing_and_recurrence(calendar):
    env, base, today = calendar
    c = env.app.modules["calendar"]
    assert c.add_link(base + "/bad.ics") == (False, "Couldn't read that link: not an iCal calendar")
    ok, msg = c.add_link(base + "/cal.ics")
    assert ok and msg.startswith("Added: 5 events")
    env.on("calendar")
    titles = lambda d: [e["title"] for e in c.day(d)]  # noqa: E731
    assert titles(today) == ["Lecture (moved)", "A very long title that is folded across lines"]
    assert titles(today + dt.timedelta(days=1)) == ["Trip, all day"]
    assert "Lecture" not in titles(today + dt.timedelta(days=7))  # the EXDATE
    assert titles(today + dt.timedelta(days=14)) == ["Lecture"]
    moved = c.day(today)[0]
    assert moved["start_dt"].hour == 12 and moved["end_dt"].hour == 13
    long_one = c.day(today)[1]
    assert (long_one["end_dt"] - long_one["start_dt"]).seconds == 45 * 60 and long_one["location"] == "Room 1"
    # no calls during a (timed) event; all-day events don't block
    inside = dt.datetime.combine(today, dt.time(12, 30), BERLIN)
    reason, until = c._block(inside)
    assert reason == "in Lecture (moved)" and until == dt.datetime.combine(
        today, dt.time(13), BERLIN
    ).astimezone().replace(tzinfo=None)
    assert c._block(dt.datetime.combine(today + dt.timedelta(days=1), dt.time(12), BERLIN)) is None
    assert "Lecture (moved)" in env.say("/today")
    assert env.say("what's on tomorrow?").startswith("Tomorrow:\nall day  Trip, all day")
    assert c.call_brief()["calendar_today"][0].startswith("12:00–13:00")


def test_until_and_zone_fallbacks():
    assert cal_mod.fix_until("FREQ=WEEKLY;UNTIL=20261231") == "FREQ=WEEKLY;UNTIL=20261231T235959Z"
    assert cal_mod.fix_until("FREQ=DAILY;UNTIL=20261231T100000") == "FREQ=DAILY;UNTIL=20261231T100000Z"
    assert cal_mod.fix_until("FREQ=DAILY;UNTIL=20261231T100000Z") == "FREQ=DAILY;UNTIL=20261231T100000Z"
    ev = cal_mod.parse_ics(
        "BEGIN:VEVENT\nUID:w\nSUMMARY:x\nDTSTART;TZID=W. Europe Standard Time:20261020T090000\nEND:VEVENT", BERLIN
    )
    assert ev[0]["start"].tzinfo == BERLIN  # an Outlook zone name falls back to yours


def test_calendar_reminders(calendar):
    env, base, today = calendar
    env.app.settings.set("calendar.remind_min", 10)
    c = env.app.modules["calendar"]
    c.add_link(base + "/cal.ics")
    keys = [j.key for j in env.app.scheduler.jobs("calendar:remind:")]
    assert keys and all(k.startswith("calendar:remind:") for k in keys)
    c._remind(
        {"title": "Lecture", "start": dt.datetime.combine(today, dt.time(10), BERLIN).isoformat(), "location": ""}
    )
    assert env.fake.texts()[-1] == "Lecture at 10:00."


# ----------------------------------------------------------------------------------------- notes sync
needs_git = pytest.mark.skipif(not shutil.which("git"), reason="needs git")


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@needs_git
def test_notes_sync_round_trip_and_clash(env, tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    env.app.settings.set("notes_sync.remote", str(remote))
    ns = env.app.modules["notes_sync"]
    ws = env.app.workspace
    (ws / "a.md").write_text("# A\n\nfirst\n")
    ok, msg = ns.first_sync()
    assert ok, msg
    assert "a.md" in git(tmp_path, "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main")
    assert (ws / ".gitignore").exists()
    # another device adds a note; this computer adds one too
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(remote), str(other))
    (other / "b.md").write_text("from the phone\n")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "b")
    git(other, "push", "-q", "origin", "main")
    (ws / "c.md").write_text("from the laptop\n")
    assert ns.sync() == (True, "Synced.")
    assert (ws / "b.md").read_text() == "from the phone\n"
    assert "c.md" in git(tmp_path, "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main")
    # the same line changed in both places: both kept, the phone's in the note, this computer's in a copy
    git(other, "pull", "-q", "origin", "main")
    (other / "a.md").write_text("# A\n\nphone version\n")
    git(other, "commit", "-qam", "phone edit")
    git(other, "push", "-q", "origin", "main")
    (ws / "a.md").write_text("# A\n\nlaptop version\n")
    assert ns.sync()[0]
    assert (ws / "a.md").read_text() == "# A\n\nphone version\n"
    (copy,) = ws.glob("a (conflict, this computer, *).md")
    assert copy.read_text() == "# A\n\nlaptop version\n"
    assert "phone edit" in git(tmp_path, "--git-dir", str(remote), "log", "--format=%s", "main")
    assert git(tmp_path, "--git-dir", str(remote), "show", "main:a.md") == "# A\n\nphone version\n"
    assert copy.name in git(tmp_path, "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main")


@needs_git
def test_notes_sync_reports_an_unreachable_remote_once(env, tmp_path):
    env.app.settings.set("notes_sync.remote", str(tmp_path / "missing.git"))
    ns = env.app.modules["notes_sync"]
    (env.app.workspace / "a.md").write_text("x\n")
    ok, msg = ns.first_sync()
    assert not ok and "couldn't reach your repository" in msg
    n = len(env.fake.texts())
    assert not ns.sync()[0]
    assert len(env.fake.texts()) == n  # not told again within 6 hours


def test_notes_sync_refuses_public_or_read_only_repos(env):
    srv, base = serve(
        {
            "/repos/me/public": (200, {"private": False, "permissions": {"push": True}}),
            "/repos/me/readonly": (200, {"private": True, "permissions": {"push": False}}),
            "/repos/me/notes": (200, {"private": True, "permissions": {"push": True}, "default_branch": "trunk"}),
        }
    )
    try:
        env.app.settings.set("notes_sync.api", base)
        ns = env.app.modules["notes_sync"]
        assert "public" in ns.check_repo("me/public", "t")[1]
        assert "only read" in ns.check_repo("me/readonly", "t")[1]
        assert "no such repository" in ns.check_repo("me/none", "t")[1]
        assert "owner/name" in ns.check_repo("not a repo", "t")[1]
        assert ns.check_repo("me/notes", "t") == (True, "trunk")
        env.app.settings.set("notes_sync.remote", "")
        ok, msg = ns.connect("me/notes", "tok")
        assert env.app.settings.get("notes_sync.branch") == "trunk" and env.app.secrets.get("notes_sync.token") == "tok"
        assert env.app.settings.get("calls.notes_repo") == "me/notes"
        e = ns._env()
        assert e["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
        assert base64.b64decode(e["GIT_CONFIG_VALUE_0"].split()[-1]) == b"x-access-token:tok"
    finally:
        srv.shutdown()


# --------------------------------------------------------------------------------------------- google
@pytest.fixture
def google(env):
    g = FakeGoogle()
    env.app.settings.set("google.endpoints", g.endpoints())
    env.app.settings.set("google.gmail_drafts", True)
    env.on("deadlines")
    yield env, g, env.app.modules["google"]
    g.close()


CLIENT = json.dumps(
    {
        "installed": {
            "client_id": "cid.apps.googleusercontent.com",
            "client_secret": "csec",
            "redirect_uris": ["http://localhost"],
        }
    }
)


def sign_in(gm, fake):
    url = gm.start_signin()
    code, state = fake.issue_code(url)
    return gm.finish_signin(code, state), url


def test_google_sign_in_with_pkce_and_single_use_state(google):
    env, fake, gm = google
    assert gm.set_client(json.dumps({"web": {"client_id": "x"}}))[0] is False
    assert gm.set_client(CLIENT) == (True, "Saved your Google client. Now sign in.")
    assert gm.ready() == (False, "sign in with Google")
    url = gm.start_signin()
    assert "code_challenge_method=S256" in url and "access_type=offline" in url and "gmail.compose" in url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8770%2Foauth%2Fgoogle" in url
    code, _ = fake.issue_code(url)
    assert gm.finish_signin(code, "forged")[0] is False
    assert gm.finish_signin(code, "anything")[1].startswith("This sign-in page is out of date")  # used up
    (ok, msg), _ = sign_in(gm, fake)
    assert ok, msg
    assert gm.ready() == (True, "")
    assert fake.token_calls[-1]["code_verifier"]  # PKCE checked by the fake


def test_classroom_feeds_deadlines_and_posts(google):
    env, fake, gm = google
    gm.set_client(CLIENT)
    sign_in(gm, fake)
    env.on("google")
    r = gm.classroom_sync()
    assert r == {"deadlines": 2, "done": 1, "posts": 0}  # the first sync only learns what's there
    items = {it["title"]: it for it in env.app.modules["deadlines"].items().values()}
    assert set(items) == {"Linear Algebra: Problem set 3", "Linear Algebra: Problem set 2"}
    assert items["Linear Algebra: Problem set 2"]["status"] == "done"
    assert items["Linear Algebra: Problem set 2"]["due"].endswith("T23:59:00")  # a date only: end of that day
    fake.posts["c1"].append(
        {"id": "a2", "text": "Quiz moved to Friday", "alternateLink": "https://classroom.example.com/a2"}
    )
    assert gm.classroom_sync()["posts"] == 1
    assert env.fake.texts()[-1] == "New in Linear Algebra: Quiz moved to Friday"


def test_expired_google_access_asks_to_sign_in_again(google):
    env, fake, gm = google
    gm.set_client(CLIENT)
    sign_in(gm, fake)
    t = gm.tokens()
    gm.app.secrets.set("google.tokens", json.dumps({**t, "expires": 0}))
    assert gm.access_token() == "access-2"  # refreshed
    gm.app.secrets.set("google.tokens", json.dumps({**gm.tokens(), "expires": 0}))
    fake.refresh_ok = False
    assert gm.classroom_sync() == {"error": "needs sign-in"} or not gm.ready()[0]
    assert not gm.ready()[0] and "sign-in expired" in env.fake.texts()[-1]


def test_a_refused_access_token_is_renewed_and_keeps_the_sign_in(google):
    env, fake, gm = google
    gm.set_client(CLIENT)
    sign_in(gm, fake)
    gm.app.secrets.set("google.tokens", json.dumps({**gm.tokens(), "access_token": "stale", "expires": 2e9}))
    assert gm.api("classroom", "/courses")["courses"]  # 401 on the stale token, then a fresh one works
    assert gm.signed_in() and gm.tokens()["access_token"] == "access-2"
    gm.app.secrets.set("google.tokens", json.dumps({**gm.tokens(), "access_token": "stale", "expires": 2e9}))
    fake.refresh_ok = False  # only Google's invalid_grant on renewing it ends the sign-in
    with pytest.raises(NeedsSignIn):
        gm.api("classroom", "/courses")
    assert not gm.signed_in()


def test_gmail_drafts_are_only_drafts(google):
    env, fake, gm = google
    gm.set_client(CLIENT)
    sign_in(gm, fake)
    env.on("google")
    out = env.say("/draft prof@example.com | Extension request | Could I have two more days for PS3?")
    assert out.startswith('Draft saved in Gmail: "Extension request"')
    msg = message_from_bytes(base64.urlsafe_b64decode(fake.drafts[-1]["message"]["raw"]))
    assert msg["To"] == "prof@example.com" and msg["Subject"] == "Extension request"
    assert "two more days" in msg.get_payload()
    assert "Turn on Chat" in env.say("/draft prof@example.com ask for an extension")


def test_sign_in_page_comes_back_to_kurooto(google):
    from kurooto.web.server import start as start_web

    env, fake, gm = google
    gm.set_client(CLIENT)
    server = start_web(env.app)
    try:
        url = gm.start_signin()
        assert f"127.0.0.1%3A{server.port}%2Foauth%2Fgoogle" in url
        code, state = fake.issue_code(url)
        bad = urllib.request.Request(f"{server.url}/oauth/google?code={code}&state=forged")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(bad, timeout=10)
        assert e.value.code == 400
        url = gm.start_signin()
        code, state = fake.issue_code(url)
        with urllib.request.urlopen(f"{server.url}/oauth/google?code={code}&state={state}", timeout=10) as r:
            assert r.status == 200 and "Signed in with Google" in r.read().decode()
        assert gm.ready()[0]
    finally:
        server.stop()


def test_setup_forms_through_the_api(env, tmp_path):
    from kurooto.web.api import Api

    api = Api(env.app)
    forms = {m["id"]: m["form"] for m in api.get("state")[1]["modules"] if m["form"]}
    first = {"calendar", "notes_sync", "google", "research"}
    assert first <= set(forms)  # the Google add-ons have forms too: Save asks Google for their permission
    assert all(f["intro"] for f in forms.values()) and all(forms[k]["fields"] for k in first)
    r = api.post("modules/configure", {"id": "calendar", "values": {"link": "ftp://nope"}})[1]
    assert r["ok"] is False and "https" in r["message"]
    r = api.post("modules/configure", {"id": "google", "values": {"client": CLIENT}})[1]
    assert r["ok"] and r["open"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")


def test_google_sign_in_says_exactly_what_went_wrong(google):
    from kurooto.modules import google as gmod

    env, fake, gm = google
    gm.set_client(CLIENT)
    # a box left unticked on Google's consent page: told which part, and to tick every box
    code, state = fake.issue_code(gm.start_signin(), drop="gmail.compose")
    ok, msg = gm.finish_signin(code, state)
    assert not ok and "can't use: Gmail drafts" in msg and "tick every box" in msg  # a part Google itself needs
    assert gm.ready() == (False, "sign in again: a newly chosen part needs Google's OK")
    # the token endpoint's errors, in plain words
    code, state = fake.issue_code(gm.start_signin())
    gm._token_call = lambda form: (_ for _ in ()).throw(
        gmod.TokenError("invalid_client", "The OAuth client was not found.")
    )
    assert gm.finish_signin(code, state)[1].startswith("Google doesn't recognise this OAuth client")
    code, state = fake.issue_code(gm.start_signin())
    gm._token_call = lambda form: {"access_token": "a", "expires_in": 3600}  # no refresh token
    assert "myaccount.google.com/connections" in gm.finish_signin(code, state)[1]
    # what Google's page sends back when you press Cancel, or an admin blocks the app
    assert gmod.signin_error("access_denied").startswith("You pressed Cancel")
    assert "admin" in gmod.signin_error("admin_policy_enforced")
    assert gmod.signin_error("weird").startswith("Google's sign-in didn't finish (weird)")


def test_sign_in_page_explains_a_cancel(google):
    from kurooto.web.server import start as start_web

    env, fake, gm = google
    server = start_web(env.app)
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"{server.url}/oauth/google?error=access_denied", timeout=10)
        assert e.value.code == 400 and "You pressed Cancel" in e.value.read().decode()
    finally:
        server.stop()


def test_setup_pages_always_show_a_sign_in_link_and_the_call_steps():
    """Popup blockers stop window.open after an await: both pages show a link too (checked in a real browser; this
    keeps the pieces from going missing)."""
    from importlib import resources

    static = resources.files("kurooto.web") / "static"
    for page in ("setup.js", "home.js"):
        js = (static / page).read_text(encoding="utf-8")
        assert "Open Google sign-in" in js and "127.0.0.1 page" in js and "noopener" in js
        assert "started === false" in js  # "something is already being set up" is shown, not polled silently
        assert "even if agy or another AI answers your messages" in js
        assert "1) Download the app (Android) or Add to Home Screen (iPhone), then 2) pairing" in js
    home = (static / "home.js").read_text(encoding="utf-8")
    assert "The phone app comes from your own call line: set up Phone calls first." in home
    assert 'const kept = $("#flog")' in home  # the setup log survives a re-render
    assert "Set up now" in (static / "setup.js").read_text(encoding="utf-8")


def test_a_calendar_link_that_fails_keeps_its_last_events_while_another_works(calendar):
    env, base, today = calendar
    c = env.app.modules["calendar"]
    other = ics_for(today).replace("Lecture", "Seminar").replace("UID:", "UID:o-")
    routes = {"/cal.ics": (200, ics_for(today).encode()), "/other.ics": (200, other.encode())}
    srv, base2 = serve(routes)
    try:
        c.add_link(base + "/cal.ics")
        c.add_link(base2 + "/other.ics")
        env.on("calendar")
        c.refresh()
        both = [e["title"] for e in c.day(today)]
        assert "Seminar (moved)" in both and "Lecture (moved)" in both
        routes["/other.ics"] = (500, b"down")  # that link fails; the first still works
        c.refresh()
        assert [e["title"] for e in c.day(today)] == both  # its last good events stay, once
        c.refresh()
        assert [e["title"] for e in c.day(today)] == both
    finally:
        srv.shutdown()
